#!/usr/bin/env python3
"""Capture a control-only C0 cold plus C1-C5 warm Qwen3-TTS logit envelope."""

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
from itertools import combinations
from pathlib import Path


SCHEMA = "agent_bridge.qwen3_tts.control_logit_stability.v0"
POLICY_SCHEMA = "agent_bridge.qwen3_tts.control_logit_stability_policy.v0"
TRIAL_LABELS = ["C0_cold", "C1_warm", "C2_warm", "C3_warm", "C4_warm", "C5_warm"]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


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


def load_trial_module(path: Path):
    spec = importlib.util.spec_from_file_location("qwen3_fake_q8_control_primitives", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("unable to load frozen token-trial primitives")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _ordered_float_bits(values):
    import numpy as np

    array = np.ascontiguousarray(values)
    if array.dtype == np.float16:
        bits = array.view(np.uint16).astype(np.uint32)
        sign = np.uint32(0x8000)
        mask = np.uint32(0xFFFF)
    elif array.dtype == np.float32:
        bits = array.view(np.uint32).astype(np.uint64)
        sign = np.uint64(0x80000000)
        mask = np.uint64(0xFFFFFFFF)
    else:
        raise ValueError("ULP metrics require float16 or float32 logits")
    return np.where((bits & sign) != 0, mask - bits, bits + sign)


def compare_logit_arrays(left, right, *, top_k: int = 8) -> dict:
    import numpy as np

    left = np.asarray(left)
    right = np.asarray(right)
    if left.shape != right.shape or left.dtype != right.dtype or left.ndim != 2:
        return {"compatible": False, "exact": False, "finite": False}
    if left.shape[0] == 0 or left.shape[1] < top_k:
        raise ValueError("logit comparison requires rows and a sufficient vocabulary")
    finite = bool(np.all(np.isfinite(left)) and np.all(np.isfinite(right)))
    if not finite:
        return {"compatible": True, "exact": False, "finite": False}
    exact = bool(np.array_equal(left, right))
    changed = left != right
    delta = np.abs(left.astype(np.float64) - right.astype(np.float64))
    centered_left = left.astype(np.float64) - np.mean(left.astype(np.float64), axis=1, keepdims=True)
    centered_right = right.astype(np.float64) - np.mean(right.astype(np.float64), axis=1, keepdims=True)
    denominator = float(np.sqrt(np.mean(centered_left**2)))
    centered_nrmse = float(np.sqrt(np.mean((centered_left - centered_right) ** 2)) / denominator) if denominator else 0.0
    left_top = np.argpartition(left, -top_k, axis=1)[:, -top_k:]
    right_top = np.argpartition(right, -top_k, axis=1)[:, -top_k:]
    top_retention = [len(set(a.tolist()) & set(b.tolist())) / top_k for a, b in zip(left_top, right_top)]
    top1_equal = np.argmax(left, axis=1) == np.argmax(right, axis=1)
    changed_rows = np.flatnonzero(np.any(changed, axis=1)).astype(int).tolist()
    top1_mismatch_rows = np.flatnonzero(~top1_equal).astype(int).tolist()
    top8_mismatch_rows = [index for index, retention in enumerate(top_retention) if retention != 1.0]
    ulp = np.abs(_ordered_float_bits(left).astype(np.int64) - _ordered_float_bits(right).astype(np.int64))
    return {
        "compatible": True,
        "exact": exact,
        "finite": True,
        "elements": int(left.size),
        "changed_elements": int(np.count_nonzero(changed)),
        "changed_fraction": float(np.mean(changed)),
        "changed_rows": changed_rows,
        "max_abs_delta": float(np.max(delta)),
        "mean_abs_delta": float(np.mean(delta)),
        "max_ulp_delta": int(np.max(ulp)),
        "mean_ulp_delta": float(np.mean(ulp)),
        "centered_logit_nrmse": centered_nrmse,
        "top1_agreement": float(np.mean(top1_equal)),
        "top8_retention": float(np.mean(top_retention)),
        "top1_mismatch_rows": top1_mismatch_rows,
        "top8_mismatch_rows": top8_mismatch_rows,
    }


def classify_path(pair_metrics: list[dict]) -> str:
    if not pair_metrics or any(not row.get("compatible") or not row.get("finite") for row in pair_metrics):
        return "UNSTABLE"
    if all(row.get("exact") is True for row in pair_metrics):
        return "BIT_EXACT"
    if all(row.get("top1_agreement") == 1.0 and row.get("top8_retention") == 1.0 for row in pair_metrics):
        return "NUMERICALLY_STABLE_WITHIN_CONTROL_ENVELOPE"
    return "UNSTABLE"


def summarize_path(trials: list[dict], selector, labels: list[str] | None = None) -> dict:
    labels = labels or TRIAL_LABELS
    rows = []
    for left_index, right_index in combinations(range(len(trials)), 2):
        metrics = compare_logit_arrays(selector(trials[left_index]), selector(trials[right_index]))
        rows.append({"pair": [labels[left_index], labels[right_index]], **metrics})
    compatible = [row for row in rows if row.get("compatible") and row.get("finite")]
    warm_rows = [row for row in rows if "C0_cold" not in row["pair"]]
    return {
        "classification": classify_path(rows),
        "warm_only_classification": classify_path(warm_rows),
        "pair_count": len(rows),
        "exact_pair_count": sum(row.get("exact") is True for row in rows),
        "envelope": {
            "max_changed_fraction": max((row["changed_fraction"] for row in compatible), default=None),
            "max_abs_delta": max((row["max_abs_delta"] for row in compatible), default=None),
            "max_ulp_delta": max((row["max_ulp_delta"] for row in compatible), default=None),
            "max_centered_logit_nrmse": max((row["centered_logit_nrmse"] for row in compatible), default=None),
            "min_top1_agreement": min((row["top1_agreement"] for row in compatible), default=None),
            "min_top8_retention": min((row["top8_retention"] for row in compatible), default=None),
        },
        "pairs": rows,
        "retains_full_logits": False,
    }


def validate_policy(policy: dict) -> None:
    if policy.get("schema") != POLICY_SCHEMA or policy.get("trial_labels") != TRIAL_LABELS:
        raise ValueError("control stability policy identity drift")
    execution = policy.get("execution", {})
    required_false = ("worker_socket_use", "audio_decode_write_or_playback", "weight_mutation_or_proxy", "quantized_weight_writing")
    if execution.get("processes") != 1 or execution.get("model_loads") != 1 or any(execution.get(key) is not False for key in required_false):
        raise ValueError("control stability execution boundary drift")
    if any(policy.get("authority", {}).values()):
        raise ValueError("control stability policy grants authority")


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
    parser.add_argument("--policy", required=True, type=Path)
    parser.add_argument("--asset-manifest", required=True, type=Path)
    parser.add_argument("--corpus", required=True, type=Path)
    parser.add_argument("--model", required=True, type=Path)
    parser.add_argument("--trial-module", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
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
    asset_manifest = load_json(args.asset_manifest)
    corpus = load_json(args.corpus)
    validate_policy(policy)
    model_root = args.model.expanduser().resolve(strict=True)
    assets = verify_assets(model_root, asset_manifest)
    case = next((row for row in corpus.get("cases", []) if row.get("id") == policy["case_id"]), None)
    if case is None:
        raise ValueError("frozen control case missing")
    trial_module = load_trial_module(args.trial_module.resolve(strict=True))
    import torch
    from qwen_tts import Qwen3TTSModel

    if not torch.backends.mps.is_available():
        raise RuntimeError("MPS is unavailable")
    model = Qwen3TTSModel.from_pretrained(str(model_root), device_map="mps", dtype=torch.float16)
    trials = []
    trial_receipts = []
    try:
        for label in TRIAL_LABELS:
            torch.mps.synchronize()
            started = time.perf_counter()
            trial = trial_module.run_token_trial(model, case, policy["execution"]["max_new_tokens"], capture_logits=True)
            torch.mps.synchronize()
            trials.append(trial)
            trial_receipts.append({
                "label": label,
                "elapsed_seconds": time.perf_counter() - started,
                "codes": trial["code_summary"],
                "boundary": trial["boundary"],
                "logit_capture": trial["logit_capture_summary"],
            })
        reference_codes = trials[0]["codes"]
        codes_exact = all(trial_module.code_divergence_metrics(reference_codes, trial["codes"])["exact_equal"] for trial in trials[1:])
        time_steps = [int(trial["codes"].shape[0]) for trial in trials]
        paths = {
            "talker_generated_rows": summarize_path(trials, lambda trial: trial["logits"]["talker"][: trial["codes"].shape[0]]),
            "talker_terminal_decision": summarize_path(trials, lambda trial: trial["logits"]["talker"][trial["codes"].shape[0] : trial["codes"].shape[0] + 1]),
            "predictor_head_0": summarize_path(trials, lambda trial: trial["logits"]["predictors"][0]),
        }
        head_summaries = {f"head_{index}": summarize_path(trials, lambda trial, index=index: trial["logits"]["predictors"][index]) for index in range(1, 15)}
        head_classes = {item["classification"] for item in head_summaries.values()}
        paths["predictor_heads_1_through_14"] = {
            "classification": "UNSTABLE" if "UNSTABLE" in head_classes else "NUMERICALLY_STABLE_WITHIN_CONTROL_ENVELOPE" if "NUMERICALLY_STABLE_WITHIN_CONTROL_ENVELOPE" in head_classes else "BIT_EXACT",
            "heads": head_summaries,
            "retains_full_logits": False,
        }
        cleanup_exact = all(trial["boundary"].get("cleanup_proven") is True for trial in trials)
        path_classes = [value["classification"] for value in paths.values()]
        stable = codes_exact and len(set(time_steps)) == 1 and cleanup_exact and "UNSTABLE" not in path_classes
        report = {
            "schema": SCHEMA,
            "status": "CONTROL_STABILITY_ENVELOPE_CAPTURED" if stable else "CONTROL_STABILITY_UNSTABLE",
            "frozen_inputs": {"policy_sha256": sha256(args.policy), "asset_manifest_sha256": sha256(args.asset_manifest), "corpus_sha256": sha256(args.corpus), "trial_module_sha256": sha256(args.trial_module)},
            "runtime": {"python": sys.version.split()[0], "torch": torch.__version__, "qwen_tts": importlib.metadata.version("qwen-tts"), "device": "mps", "dtype": "float16", "offline": True},
            "model_assets": assets,
            "case": {"id": case["id"], "speaker": case["speaker"], "text_sha256": hashlib.sha256(case["text"].encode()).hexdigest()},
            "trials": trial_receipts,
            "control_invariants": {"codes_exact": codes_exact, "time_steps": time_steps, "length_exact": len(set(time_steps)) == 1, "cleanup_exact": cleanup_exact},
            "paths": paths,
            "max_rss_bytes": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
            "retains_full_logits": False,
            "writes_audio": False,
            "mutates_weights": False,
            "writes_quantized_weights": False,
            "uses_worker_socket": False,
            "allows_fake_q8": False,
            "allows_runtime_wiring_or_promotion": False,
            "next_gate": "freeze_control_envelope_then_separately_authorize_one_fake_q8_trial" if stable else "investigate_control_instability_without_quantization",
        }
    finally:
        del trials
        del model
        torch.mps.empty_cache()
    exclusive_write_json(args.output, report)
    print(json.dumps({"status": report["status"], "output": str(args.output), "path_classes": {key: value["classification"] for key, value in report["paths"].items()}}, ensure_ascii=False))
    return 0 if report["status"] == "CONTROL_STABILITY_ENVELOPE_CAPTURED" else 2


if __name__ == "__main__":
    raise SystemExit(main())
