#!/usr/bin/env python3
"""Observe Qwen3-TTS talker codes at the pre-codec boundary without decoding audio."""
from __future__ import annotations

import argparse
import fcntl
import hashlib
import importlib.metadata
import inspect
import json
import os
import sys
from contextlib import contextmanager
from pathlib import Path


SCHEMA = "agent_bridge.qwen3_tts.token_boundary_probe.v0"
PLAN_SCHEMA = "agent_bridge.qwen3_tts.activation_probe_plan.v1"
GATE_SCHEMA = "agent_bridge.qwen3_tts.activation_calibration_gate.v0"
CORPUS_SCHEMA = "agent_bridge.qwen3_tts.quantization_corpus.v0"
POLICY_SCHEMA = "agent_bridge.qwen3_tts.activation_calibration_policy.v0"
MANIFEST_SCHEMA = "agent_bridge.qwen3_tts.inference_critical_manifest.v0"
READY_GATE_STATUS = "READY_FOR_FUNCTIONAL_SENSITIVITY_DESIGN"
ASSET_RELATIVE_PATHS = {
    "talker": Path("model.safetensors"),
    "speech_tokenizer_codec": Path("speech_tokenizer") / "model.safetensors",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def is_within(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def validate_output_path(output: Path, forbidden_roots: list[Path]) -> None:
    if output.exists() or output.is_symlink():
        raise ValueError("refusing to overwrite or follow an existing output path")
    if not output.parent.is_dir():
        raise ValueError("output parent directory must already exist")
    resolved = output.resolve(strict=False)
    for root in forbidden_roots:
        if is_within(resolved, root.resolve()):
            raise ValueError(f"output is forbidden under runtime/model root: {root}")


def exclusive_write_json(path: Path, report: dict) -> None:
    payload = (json.dumps(report, ensure_ascii=False, indent=2) + "\n").encode()
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "wb", closefd=False) as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
    finally:
        os.close(descriptor)


def acquire_process_lock(path: Path):
    descriptor = os.open(path, os.O_RDWR | os.O_CREAT, 0o600)
    os.fchmod(descriptor, 0o600)
    stream = os.fdopen(descriptor, "r+")
    try:
        fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        stream.close()
        raise ValueError("another Qwen3 evaluation process holds the owner lock") from None
    return stream


def verify_critical_manifest(
    manifest: dict,
    runtime_root: Path,
    model_root: Path,
    observed_packages: dict,
) -> tuple[list[dict], list[dict]]:
    if manifest.get("schema") != MANIFEST_SCHEMA:
        raise ValueError("unexpected inference-critical manifest schema")
    if manifest.get("packages") != observed_packages:
        raise ValueError("inference-critical package versions do not match")

    def verify_rows(root: Path, rows: list[dict], label: str) -> list[dict]:
        verified = []
        for row in rows:
            relative = Path(row.get("relative_path", ""))
            path = root / relative
            if not path.is_file() or sha256(path) != row.get("sha256"):
                raise ValueError(f"inference-critical {label} file mismatch: {relative}")
            verified.append(
                {
                    "relative_path": str(relative),
                    "path": str(path.resolve()),
                    "sha256": row["sha256"],
                }
            )
        return verified

    runtime_files = verify_rows(
        runtime_root,
        manifest.get("runtime_files", []),
        "runtime",
    )
    model_files = verify_rows(
        model_root,
        manifest.get("model_files", []),
        "model",
    )
    if not runtime_files or not model_files:
        raise ValueError("inference-critical manifest must pin runtime and model files")
    return runtime_files, model_files


def select_case(corpus: dict, case_id: str) -> dict:
    matches = [case for case in corpus.get("cases", []) if case.get("id") == case_id]
    if len(matches) != 1:
        raise ValueError(f"expected exactly one frozen case named {case_id}")
    return matches[0]


def verify_model_assets(model_root: Path, plan: dict) -> list[dict]:
    expected_by_partition = {
        row.get("partition"): row for row in plan.get("source_assets", [])
    }
    verified = []
    for partition, relative_path in ASSET_RELATIVE_PATHS.items():
        expected = expected_by_partition.get(partition)
        if expected is None:
            raise ValueError(f"activation plan does not pin {partition}")
        path = model_root / relative_path
        if not path.is_file():
            raise ValueError(f"missing pinned asset: {path}")
        observed_bytes = path.stat().st_size
        observed_hash = sha256(path)
        if (
            observed_bytes != expected.get("bytes")
            or observed_hash != expected.get("sha256")
        ):
            raise ValueError(f"pinned {partition} asset does not match activation plan")
        verified.append(
            {
                "partition": partition,
                "relative_path": str(relative_path),
                "bytes": observed_bytes,
                "sha256": observed_hash,
            }
        )
    return verified


@contextmanager
def temporary_instance_override(instance, name: str, value, restoration: dict):
    had_instance_value = name in instance.__dict__
    previous_instance_value = instance.__dict__.get(name)
    setattr(instance, name, value)
    try:
        yield
    finally:
        if had_instance_value:
            setattr(instance, name, previous_instance_value)
        else:
            delattr(instance, name)
        restoration[name] = (
            name in instance.__dict__
        ) == had_instance_value and (
            not had_instance_value
            or instance.__dict__.get(name) is previous_instance_value
        )


def tensor_summary(tensor) -> dict:
    import torch

    cpu = tensor.detach().to(device="cpu").contiguous()
    raw = cpu.view(torch.uint8).numpy().tobytes()
    shape = list(cpu.shape)
    return {
        "shape": shape,
        "dtype": str(cpu.dtype).removeprefix("torch."),
        "elements": cpu.numel(),
        "time_steps": shape[0] if shape else 0,
        "codebooks": shape[1] if len(shape) == 2 else None,
        "min": int(cpu.min().item()) if cpu.numel() else None,
        "max": int(cpu.max().item()) if cpu.numel() else None,
        "sha256": hashlib.sha256(raw).hexdigest(),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", required=True, type=Path)
    parser.add_argument("--gate", required=True, type=Path)
    parser.add_argument("--activation-policy", required=True, type=Path)
    parser.add_argument("--runtime-manifest", required=True, type=Path)
    parser.add_argument("--corpus", required=True, type=Path)
    parser.add_argument("--case-id", required=True)
    parser.add_argument("--model", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--device", choices=["mps"], default="mps")
    parser.add_argument("--max-new-tokens", type=int, default=256)
    args = parser.parse_args()
    if not 2 <= args.max_new_tokens <= 512:
        parser.error("--max-new-tokens must be between 2 and 512")
    inputs = (
        args.plan,
        args.gate,
        args.activation_policy,
        args.runtime_manifest,
        args.corpus,
    )
    if not all(path.is_file() for path in inputs):
        parser.error("plan, gate, activation policy, runtime manifest, and corpus must exist")
    model_root = args.model.expanduser().resolve()
    if not model_root.is_dir():
        parser.error("--model must be a complete local snapshot directory")
    worker_runtime_root = (
        Path.home() / ".cache" / "agent-bridge" / "qwen3"
    ).resolve()
    try:
        validate_output_path(args.output, [model_root, worker_runtime_root])
    except ValueError as error:
        parser.error(str(error))

    plan = json.loads(args.plan.read_text(encoding="utf-8"))
    gate = json.loads(args.gate.read_text(encoding="utf-8"))
    activation_policy = json.loads(args.activation_policy.read_text(encoding="utf-8"))
    runtime_manifest = json.loads(args.runtime_manifest.read_text(encoding="utf-8"))
    corpus = json.loads(args.corpus.read_text(encoding="utf-8"))
    plan_hash = sha256(args.plan)
    corpus_hash = sha256(args.corpus)
    if plan.get("schema") != PLAN_SCHEMA:
        parser.error("unexpected activation plan schema")
    if gate.get("schema") != GATE_SCHEMA or gate.get("status") != READY_GATE_STATUS:
        parser.error("accepted activation-calibration design gate is required")
    if activation_policy.get("schema") != POLICY_SCHEMA:
        parser.error("unexpected activation-calibration policy schema")
    if runtime_manifest.get("schema") != MANIFEST_SCHEMA:
        parser.error("unexpected inference-critical manifest schema")
    if corpus.get("schema") != CORPUS_SCHEMA:
        parser.error("unexpected corpus schema")
    if gate.get("activation_plan_sha256") != plan_hash:
        parser.error("gate does not bind the supplied activation plan")
    if gate.get("corpus_sha256") != corpus_hash:
        parser.error("gate does not bind the supplied corpus")
    if gate.get("policy_sha256") != sha256(args.activation_policy):
        parser.error("gate does not bind the supplied activation policy")
    if gate.get("allows_functional_sensitivity_design") is not True:
        parser.error("gate does not admit functional-sensitivity design")
    for field in (
        "allows_fake_quant_execution",
        "allows_quantized_weight_writing",
        "allows_runtime_candidate_generation",
        "allows_runtime_wiring_or_promotion",
    ):
        if gate.get(field) is not False:
            parser.error(f"token probe requires gate {field}=false")
    source_model_policy = activation_policy.get("source_model", {})
    if (
        source_model_policy.get("device") != "mps"
        or source_model_policy.get("runtime_dtype") != "float16"
    ):
        parser.error("activation policy does not freeze MPS/float16")
    try:
        case = select_case(corpus, args.case_id)
        model_assets = verify_model_assets(model_root, plan)
    except ValueError as error:
        parser.error(str(error))

    import numpy as np
    import torch
    import qwen_tts
    from qwen_tts import Qwen3TTSModel
    observed_packages = {
        "python": sys.version.split()[0],
        "torch": torch.__version__,
        "qwen_tts": importlib.metadata.version("qwen-tts"),
        "transformers": importlib.metadata.version("transformers"),
    }
    runtime_root = Path(inspect.getfile(qwen_tts)).resolve().parent
    try:
        runtime_sources, model_inference_files = verify_critical_manifest(
            runtime_manifest,
            runtime_root,
            model_root,
            observed_packages,
        )
    except ValueError as error:
        parser.error(str(error))
    expected_runtime = source_model_policy.get("runtime", {})
    if any(
        observed_packages[key] != expected_runtime.get(key)
        for key in ("python", "torch", "qwen_tts")
    ) or expected_runtime.get("generation_api") != "generate_custom_voice" or (
        expected_runtime.get("language") != "Chinese"
    ):
        parser.error("activation policy runtime identity does not match")
    manifest_boundary = runtime_manifest.get("execution_boundary", {})
    expected_manifest_boundary = {
        "local_snapshot_required": True,
        "device": "mps",
        "runtime_dtype": "float16",
        "network_download_allowed": False,
        "audio_decode_allowed": False,
        "audio_write_allowed": False,
        "weight_mutation_allowed": False,
        "candidate_generation_allowed": False,
        "runtime_wiring_or_promotion_allowed": False,
    }
    if manifest_boundary != expected_manifest_boundary:
        parser.error("inference-critical manifest execution boundary mismatch")

    dtype = torch.float16
    try:
        lock_stream = acquire_process_lock(
            Path("/private/tmp/agent-bridge-qwen3-evaluation.lock")
        )
    except ValueError as error:
        parser.error(str(error))
    try:
        model = Qwen3TTSModel.from_pretrained(
            str(model_root),
            device_map=args.device,
            dtype=dtype,
        )
    except BaseException:
        lock_stream.close()
        raise
    inner = model.model
    tokenizer = inner.speech_tokenizer
    model_contract = runtime_manifest.get("model_contract", {})
    observed_model_contract = {
        "talker_layers": len(inner.talker.model.layers),
        "talker_hidden_size": int(inner.config.talker_config.hidden_size),
        "codebooks": int(inner.config.talker_config.num_code_groups),
        "codec_eos_token_id": int(inner.config.talker_config.codec_eos_token_id),
        "sample_rate": int(tokenizer.get_output_sample_rate()),
    }
    if observed_model_contract != model_contract:
        lock_stream.close()
        parser.error("loaded model contract does not match inference-critical manifest")
    original_generate = inner.generate
    sample_rate = int(tokenizer.get_output_sample_rate())
    captured: dict[str, object] = {
        "generate_calls": 0,
        "decode_intercept_calls": 0,
        "generated_codes": [],
        "decode_codes": [],
        "hidden_shapes": [],
    }
    restoration: dict[str, bool] = {}

    def capture_generate(*call_args, **call_kwargs):
        codes, hidden_states = original_generate(*call_args, **call_kwargs)
        captured["generate_calls"] += 1
        captured["generated_codes"] = [tensor.detach().to("cpu").clone() for tensor in codes]
        captured["hidden_shapes"] = [list(tensor.shape) for tensor in hidden_states]
        return codes, hidden_states

    def intercept_decode(items):
        captured["decode_intercept_calls"] += 1
        captured["decode_codes"] = [
            item["audio_codes"].detach().to("cpu").clone() for item in items
        ]
        return [np.empty((0,), dtype=np.float32) for _ in items], sample_rate

    inference_error = None
    returned_wave_samples = None
    returned_sample_rate = None
    try:
        with temporary_instance_override(
            inner,
            "generate",
            capture_generate,
            restoration,
        ), temporary_instance_override(
            tokenizer,
            "decode",
            intercept_decode,
            restoration,
        ):
            with torch.inference_mode():
                wavs, returned_sample_rate = model.generate_custom_voice(
                    text=case["text"],
                    language="Chinese",
                    speaker=case["speaker"],
                    instruct=case.get("instruct") or None,
                    do_sample=False,
                    subtalker_dosample=False,
                    max_new_tokens=args.max_new_tokens,
                )
            returned_wave_samples = [int(wav.shape[0]) for wav in wavs]
    except Exception as error:  # noqa: BLE001 - the receipt must preserve fail-closed state.
        inference_error = f"{type(error).__name__}: {error}"
    finally:
        lock_stream.close()

    generated_summaries = [
        tensor_summary(tensor) for tensor in captured["generated_codes"]
    ]
    decode_summaries = [tensor_summary(tensor) for tensor in captured["decode_codes"]]
    expected_codebooks = int(inner.config.talker_config.num_code_groups)
    boundary_observed = (
        inference_error is None
        and captured["generate_calls"] == 1
        and captured["decode_intercept_calls"] == 1
        and len(generated_summaries) == 1
        and generated_summaries == decode_summaries
        and generated_summaries[0]["time_steps"] > 0
        and generated_summaries[0]["codebooks"] == expected_codebooks
        and returned_wave_samples == [0]
        and returned_sample_rate == sample_rate
        and all(restoration.values())
        and len(restoration) == 2
    )
    status = (
        "TOKEN_CODE_BOUNDARY_OBSERVED_READ_ONLY"
        if boundary_observed
        else "BLOCKED_TOKEN_CODE_BOUNDARY_NOT_PROVEN"
    )
    report = {
        "schema": SCHEMA,
        "status": status,
        "activation_plan_sha256": plan_hash,
        "activation_gate_sha256": sha256(args.gate),
        "activation_policy_sha256": sha256(args.activation_policy),
        "runtime_manifest_sha256": sha256(args.runtime_manifest),
        "corpus_sha256": corpus_hash,
        "case": case,
        "model": str(model_root),
        "model_assets": model_assets,
        "runtime": {
            "python": sys.version.split()[0],
            "torch": torch.__version__,
            "qwen_tts": importlib.metadata.version("qwen-tts"),
            "qwen_tts_package": str(Path(inspect.getfile(qwen_tts)).resolve()),
            "device": args.device,
            "dtype": str(dtype).removeprefix("torch."),
            "generation_api": "generate_custom_voice",
            "do_sample": False,
            "subtalker_dosample": False,
            "max_new_tokens": args.max_new_tokens,
        },
        "runtime_sources": runtime_sources,
        "model_inference_files": model_inference_files,
        "model_contract": observed_model_contract,
        "boundary": {
            "producer": "Qwen3TTSForConditionalGeneration.generate talker_codes_list",
            "consumer": "speech_tokenizer.decode audio_codes",
            "expected_codebooks": expected_codebooks,
            "generate_calls": captured["generate_calls"],
            "decode_intercept_calls": captured["decode_intercept_calls"],
            "generated_codes": generated_summaries,
            "decode_codes": decode_summaries,
            "hidden_shapes": captured["hidden_shapes"],
            "exact_generate_to_decode_match": generated_summaries == decode_summaries,
            "decode_was_intercepted": captured["decode_intercept_calls"] == 1,
            "returned_wave_samples": returned_wave_samples,
            "returned_sample_rate": returned_sample_rate,
            "overrides_restored": restoration,
        },
        "distribution_metrics": {
            "logit_kl": "NOT_CAPTURED_BY_V0_BOUNDARY_PROBE",
            "topk_retention": "NOT_CAPTURED_BY_V0_BOUNDARY_PROBE",
            "future_access_path": "bounded wrappers around talker.generate and code_predictor.generate",
        },
        "inference_error": inference_error,
        "writes_audio": False,
        "decodes_audio": False,
        "mutates_weights": False,
        "allows_fake_quant_execution": False,
        "allows_quantized_weight_writing": False,
        "allows_runtime_candidate_generation": False,
        "allows_runtime_wiring_or_promotion": False,
    }
    try:
        exclusive_write_json(args.output, report)
    except (FileExistsError, OSError) as error:
        parser.error(f"exclusive owner-only report write failed: {error}")
    print(
        json.dumps(
            {
                "status": status,
                "time_steps": (
                    generated_summaries[0]["time_steps"] if generated_summaries else 0
                ),
                "codebooks": (
                    generated_summaries[0]["codebooks"] if generated_summaries else None
                ),
                "code_sha256": (
                    generated_summaries[0]["sha256"] if generated_summaries else None
                ),
                "inference_error": inference_error,
            },
            ensure_ascii=False,
        )
    )
    return 0 if boundary_observed else 2


if __name__ == "__main__":
    raise SystemExit(main())
