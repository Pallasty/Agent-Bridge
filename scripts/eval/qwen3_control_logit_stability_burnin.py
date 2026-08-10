#!/usr/bin/env python3
"""Capture a burn-in separated, control-only Qwen3-TTS stability envelope."""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import importlib.util
import json
import os
import resource
import sys
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parent
OLD_RUNNER = ROOT / "qwen3_control_logit_stability.py"
SCHEMA = "agent_bridge.qwen3_tts.control_logit_stability_burnin.v1"
POLICY_SCHEMA = "agent_bridge.qwen3_tts.control_logit_stability_policy.v1"


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_module(path: Path):
    spec = importlib.util.spec_from_file_location("qwen3_control_stability_primitives", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("unable to load stability primitives")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def exclusive_write_json(path: Path, value: dict) -> None:
    payload = (json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode()
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0), 0o600)
    try:
        with os.fdopen(descriptor, "wb", closefd=False) as stream:
            stream.write(payload)
            stream.flush()
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def validate_policy(policy: dict) -> None:
    if policy.get("schema") != POLICY_SCHEMA:
        raise ValueError("burn-in policy identity drift")
    if policy.get("burn_in_labels") != ["B0_burn_in", "B1_burn_in"] or len(policy.get("trial_labels", [])) != 6:
        raise ValueError("burn-in/measurement labels drift")
    execution = policy.get("execution", {})
    forbidden = ("worker_socket_use", "audio_decode_write_or_playback", "weight_mutation_or_proxy", "quantized_weight_writing")
    if execution.get("processes") != 1 or execution.get("model_loads") != 1 or any(execution.get(key) is not False for key in forbidden):
        raise ValueError("burn-in execution boundary drift")
    if any(policy.get("authority", {}).values()):
        raise ValueError("burn-in policy grants authority")


def verify_assets(model_root: Path, manifest: dict) -> list[dict]:
    evidence = []
    for asset in manifest["model"]["assets"]:
        path = model_root / asset["relative_path"]
        if not path.is_file() or path.is_symlink() or path.stat().st_size != asset["bytes"] or sha256(path) != asset["sha256"]:
            raise ValueError(f"model asset drift: {asset['relative_path']}")
        evidence.append({"relative_path": asset["relative_path"], "bytes": asset["bytes"], "sha256": asset["sha256"]})
    return evidence


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("policy", "asset_manifest", "corpus", "model", "trial_module", "output"):
        parser.add_argument(f"--{name.replace('_', '-')}", required=True, type=Path)
    parser.add_argument("--execute-controls", action="store_true")
    args = parser.parse_args()
    if not args.execute_controls:
        parser.error("--execute-controls is required")
    if args.output.exists() or args.output.is_symlink() or not args.output.parent.is_dir():
        parser.error("output must be a new file below an existing directory")
    os.umask(0o077)
    os.environ.update({"HF_HUB_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1", "HF_HUB_DISABLE_TELEMETRY": "1"})
    sys.dont_write_bytecode = True
    policy = load_json(args.policy)
    manifest = load_json(args.asset_manifest)
    corpus = load_json(args.corpus)
    validate_policy(policy)
    model_root = args.model.expanduser().resolve(strict=True)
    assets = verify_assets(model_root, manifest)
    case = next((row for row in corpus.get("cases", []) if row.get("id") == policy["case_id"]), None)
    if case is None:
        raise ValueError("frozen control case missing")
    primitives = load_module(OLD_RUNNER)
    trial_module = load_module(args.trial_module.resolve(strict=True))
    import torch
    from qwen_tts import Qwen3TTSModel

    if not torch.backends.mps.is_available():
        raise RuntimeError("MPS is unavailable")
    model = Qwen3TTSModel.from_pretrained(str(model_root), device_map="mps", dtype=torch.float16)
    burn_in = []
    measured = []
    try:
        for label in policy["burn_in_labels"]:
            torch.mps.synchronize()
            started = time.perf_counter()
            trial = trial_module.run_token_trial(model, case, policy["execution"]["max_new_tokens"], capture_logits=False)
            torch.mps.synchronize()
            burn_in.append({"label": label, "elapsed_seconds": time.perf_counter() - started, "codes": trial["code_summary"], "boundary": trial["boundary"]})
        for label in policy["trial_labels"]:
            torch.mps.synchronize()
            started = time.perf_counter()
            trial = trial_module.run_token_trial(model, case, policy["execution"]["max_new_tokens"], capture_logits=True)
            torch.mps.synchronize()
            trial["label"] = label
            trial["elapsed_seconds"] = time.perf_counter() - started
            measured.append(trial)
        reference = measured[0]["codes"]
        codes_exact = all(trial_module.code_divergence_metrics(reference, row["codes"])["exact_equal"] for row in measured[1:])
        labels = policy["trial_labels"]
        paths = {
            "talker_generated_rows": primitives.summarize_path(measured, lambda row: row["logits"]["talker"][: row["codes"].shape[0]], labels),
            "talker_terminal_decision": primitives.summarize_path(measured, lambda row: row["logits"]["talker"][row["codes"].shape[0] : row["codes"].shape[0] + 1], labels),
            "predictor_head_0": primitives.summarize_path(measured, lambda row: row["logits"]["predictors"][0], labels),
        }
        heads = {f"head_{index}": primitives.summarize_path(measured, lambda row, index=index: row["logits"]["predictors"][index], labels) for index in range(1, 15)}
        classes = {item["classification"] for item in heads.values()}
        paths["predictor_heads_1_through_14"] = {"classification": "UNSTABLE" if "UNSTABLE" in classes else "NUMERICALLY_STABLE_WITHIN_CONTROL_ENVELOPE" if "NUMERICALLY_STABLE_WITHIN_CONTROL_ENVELOPE" in classes else "BIT_EXACT", "heads": heads, "retains_full_logits": False}
        cleanup_exact = all(row["boundary"].get("cleanup_proven") is True for row in burn_in + measured)
        stable = codes_exact and cleanup_exact and all(path["classification"] == "BIT_EXACT" for path in paths.values())
        report = {
            "schema": SCHEMA,
            "status": "CONTROL_STABILITY_ENVELOPE_CAPTURED" if stable else "CONTROL_STABILITY_UNSTABLE",
            "frozen_inputs": {"policy_sha256": sha256(args.policy), "asset_manifest_sha256": sha256(args.asset_manifest), "corpus_sha256": sha256(args.corpus), "trial_module_sha256": sha256(args.trial_module)},
            "runtime": {"python": sys.version.split()[0], "torch": torch.__version__, "qwen_tts": importlib.metadata.version("qwen-tts"), "device": "mps", "dtype": "float16", "offline": True},
            "model_assets": assets,
            "case": {"id": case["id"], "speaker": case["speaker"], "text_sha256": hashlib.sha256(case["text"].encode()).hexdigest()},
            "burn_in": [{"label": row["label"], "elapsed_seconds": row["elapsed_seconds"], "codes": row["codes"], "boundary": row["boundary"]} for row in burn_in],
            "measured": [{"label": row["label"], "elapsed_seconds": row["elapsed_seconds"], "codes": row["code_summary"], "boundary": row["boundary"], "logit_capture": row["logit_capture_summary"]} for row in measured],
            "control_invariants": {"codes_exact": codes_exact, "measured_count": len(measured), "cleanup_exact": cleanup_exact},
            "paths": paths,
            "max_rss_bytes": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
            "retains_full_logits": False, "writes_audio": False, "mutates_weights": False, "writes_quantized_weights": False, "uses_worker_socket": False,
            "allows_fake_q8": False, "allows_runtime_wiring_or_promotion": False,
            "next_gate": "separately_authorize_one_fake_q8_trial" if stable else "investigate_post_burnin_control_instability_without_quantization",
        }
    finally:
        del burn_in, measured, model
        torch.mps.empty_cache()
    exclusive_write_json(args.output, report)
    print(json.dumps({"status": report["status"], "output": str(args.output), "path_classes": {key: value["classification"] for key, value in report["paths"].items()}}, ensure_ascii=False))
    return 0 if report["status"] == "CONTROL_STABILITY_ENVELOPE_CAPTURED" else 2


if __name__ == "__main__":
    raise SystemExit(main())
