#!/usr/bin/env python3
"""Run bounded, read-only Qwen3-TTS activation calibration in a separate process."""
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import math
import random
import sys
from pathlib import Path


SCHEMA = "agent_bridge.qwen3_tts.activation_capture.v0"
PLAN_SCHEMA = "agent_bridge.qwen3_tts.activation_probe_plan.v1"
CORPUS_SCHEMA = "agent_bridge.qwen3_tts.quantization_corpus.v0"
PER_CALL_CANDIDATES = 256
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


def tensor_from(output):
    import torch

    if isinstance(output, torch.Tensor):
        return output
    if isinstance(output, (tuple, list)):
        for item in output:
            value = tensor_from(item)
            if value is not None:
                return value
    return None


def normalized_entropy(values: list[float], bins: int) -> float:
    if not values or bins < 2:
        return 0.0
    low, high = min(values), max(values)
    if low >= high:
        return 0.0
    width = high - low
    histogram = [0] * bins
    for value in values:
        index = min(int((value - low) / width * bins), bins - 1)
        histogram[index] += 1
    total = len(values)
    entropy = -sum(
        (count / total) * math.log2(count / total)
        for count in histogram
        if count
    )
    return entropy / math.log2(bins)


def sample_stats(
    samples: list[float],
    seen: int,
    calls: int,
    nonfinite: int,
    total_elements: int,
    output_signatures: set[str],
) -> dict:
    signatures = [json.loads(value) for value in sorted(output_signatures)]
    signature_sha256 = hashlib.sha256(
        "\n".join(sorted(output_signatures)).encode()
    ).hexdigest()
    if not samples:
        return {
            "sample_count": 0,
            "finite_candidate_values_seen": seen,
            "candidate_values_examined": seen + nonfinite,
            "total_elements_seen": total_elements,
            "hook_calls": calls,
            "nonfinite_candidates": nonfinite,
            "output_signatures": signatures,
            "output_signature_sha256": signature_sha256,
            "sample_min": None,
            "sample_max": None,
            "mean": None,
            "rms": None,
            "variance": None,
            "kurtosis": None,
            "zero_ratio": None,
            "median_abs": None,
            "outlier_ratio_6x_median_abs": None,
            "normalized_entropy": {"64": 0.0, "256": 0.0},
        }
    count = len(samples)
    mean = sum(samples) / count
    second = sum(value * value for value in samples) / count
    variance = sum((value - mean) ** 2 for value in samples) / count
    fourth = sum((value - mean) ** 4 for value in samples) / count
    absolute = sorted(abs(value) for value in samples)
    median_abs = absolute[round((count - 1) * 0.5)]
    threshold = max(6.0 * median_abs, 1.1920928955078125e-07)
    return {
        "sample_count": count,
        "finite_candidate_values_seen": seen,
        "candidate_values_examined": seen + nonfinite,
        "total_elements_seen": total_elements,
        "hook_calls": calls,
        "nonfinite_candidates": nonfinite,
        "output_signatures": signatures,
        "output_signature_sha256": signature_sha256,
        "sample_min": min(samples),
        "sample_max": max(samples),
        "mean": mean,
        "rms": math.sqrt(second),
        "variance": variance,
        "kurtosis": fourth / (variance * variance) if variance > 0 else 0.0,
        "zero_ratio": sum(value == 0.0 for value in samples) / count,
        "median_abs": median_abs,
        "outlier_ratio_6x_median_abs": sum(abs(value) > threshold for value in samples) / count,
        "normalized_entropy": {
            "64": normalized_entropy(samples, 64),
            "256": normalized_entropy(samples, 256),
        },
    }


def selected_cases(corpus: dict, case_ids: list[str], all_cases: bool) -> list[dict]:
    cases = corpus.get("cases", [])
    if all_cases:
        return cases
    requested = case_ids or [cases[0]["id"]]
    by_id = {case["id"]: case for case in cases}
    missing = [case_id for case_id in requested if case_id not in by_id]
    if missing:
        raise ValueError(f"case not found: {', '.join(missing)}")
    return [by_id[case_id] for case_id in requested]


def verify_model_assets(model_root: Path, plan: dict) -> list[dict]:
    verified = []
    for expected in plan.get("source_assets", []):
        partition = expected.get("partition")
        relative = ASSET_RELATIVE_PATHS.get(partition)
        if relative is None:
            continue
        path = model_root / relative
        if not path.is_file():
            raise ValueError(f"missing pinned {partition} asset: {path}")
        observed_bytes = path.stat().st_size
        observed_sha256 = sha256(path)
        if observed_bytes != expected.get("bytes") or observed_sha256 != expected.get("sha256"):
            raise ValueError(f"pinned {partition} asset does not match activation plan")
        verified.append(
            {
                "partition": partition,
                "relative_path": str(relative),
                "bytes": observed_bytes,
                "sha256": observed_sha256,
            }
        )
    if {row["partition"] for row in verified} != set(ASSET_RELATIVE_PATHS):
        raise ValueError("activation plan does not pin both talker and codec assets")
    return verified


def resolve_plan_bindings(runtime_model, planned: list[dict], runtime_dtype: str) -> tuple[dict, list[dict]]:
    named_modules = dict(runtime_model.named_modules())
    named_parameters = dict(runtime_model.named_parameters())
    module_names = [row.get("module") for row in planned]
    tensor_names = [row.get("tensor") for row in planned]
    if len(set(module_names)) != len(module_names):
        raise ValueError("activation plan contains duplicate module names")
    if len(set(tensor_names)) != len(tensor_names):
        raise ValueError("activation plan contains duplicate tensor names")
    resolved = {}
    metadata = []
    for row in planned:
        module_name = row.get("module")
        tensor_name = row.get("tensor")
        module = named_modules.get(module_name)
        parameter = named_parameters.get(tensor_name)
        if module is None:
            raise ValueError(f"planned module did not resolve: {module_name}")
        if parameter is None:
            raise ValueError(f"planned tensor did not resolve: {tensor_name}")
        if getattr(module, "weight", None) is not parameter:
            raise ValueError(f"planned tensor is not the resolved module weight: {tensor_name}")
        observed_shape = list(parameter.shape)
        if observed_shape != row.get("shape"):
            raise ValueError(f"planned tensor shape mismatch: {tensor_name}")
        if parameter.numel() != row.get("elements"):
            raise ValueError(f"planned tensor element count mismatch: {tensor_name}")
        observed_dtype = str(parameter.dtype).removeprefix("torch.")
        if observed_dtype != runtime_dtype:
            raise ValueError(
                f"planned tensor runtime dtype mismatch: {tensor_name} "
                f"(expected {runtime_dtype}, observed {observed_dtype})"
            )
        if not row.get("source_dtype"):
            raise ValueError(f"planned tensor lacks pinned source dtype: {tensor_name}")
        resolved[module_name] = module
        metadata.append(
            {
                "module": module_name,
                "tensor": tensor_name,
                "module_class": f"{type(module).__module__}.{type(module).__qualname__}",
                "shape": observed_shape,
                "elements": parameter.numel(),
                "source_dtype": row["source_dtype"],
                "runtime_dtype": observed_dtype,
                "weight_identity_verified": True,
            }
        )
    return resolved, metadata


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", required=True, type=Path)
    parser.add_argument("--corpus", required=True, type=Path)
    parser.add_argument("--model", required=True)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--case-id", action="append", default=[])
    parser.add_argument("--all-cases", action="store_true")
    parser.add_argument("--max-modules", type=int, default=8)
    parser.add_argument("--device", choices=["mps", "cpu"], default="mps")
    args = parser.parse_args()
    if args.output.exists():
        parser.error("refusing to overwrite output")
    if args.all_cases and args.case_id:
        parser.error("--all-cases and --case-id are mutually exclusive")
    if args.max_modules < 1:
        parser.error("--max-modules must be positive")
    if not args.plan.is_file() or not args.corpus.is_file():
        parser.error("plan and corpus must exist")
    plan = json.loads(args.plan.read_text(encoding="utf-8"))
    corpus = json.loads(args.corpus.read_text(encoding="utf-8"))
    if plan.get("schema") != PLAN_SCHEMA:
        parser.error("unexpected activation plan schema")
    if corpus.get("schema") != CORPUS_SCHEMA:
        parser.error("unexpected corpus schema")
    if args.max_modules > len(plan.get("modules", [])):
        parser.error("--max-modules exceeds planned modules")
    try:
        cases = selected_cases(corpus, args.case_id, args.all_cases)
    except ValueError as error:
        parser.error(str(error))
    sample_limit = int(plan.get("capture_budget", {}).get("values_per_module_max", 4096))
    if not 1 <= sample_limit <= 65536:
        parser.error("invalid plan sample budget")
    plan_hash = sha256(args.plan)
    model_root = Path(args.model).expanduser().resolve()
    if not model_root.is_dir():
        parser.error("--model must be a complete local snapshot directory")
    try:
        model_assets = verify_model_assets(model_root, plan)
    except ValueError as error:
        parser.error(str(error))

    import torch
    from qwen_tts import Qwen3TTSModel

    dtype = torch.float16 if args.device == "mps" else torch.float32
    model = Qwen3TTSModel.from_pretrained(
        str(model_root),
        device_map=args.device,
        dtype=dtype,
    )
    planned = plan["modules"][: args.max_modules]
    runtime_dtype = str(dtype).removeprefix("torch.")
    try:
        named, resolved_bindings = resolve_plan_bindings(
            model.model,
            planned,
            runtime_dtype,
        )
    except ValueError as error:
        parser.error(str(error))

    active_state: dict[str, dict] = {}
    handles = []
    for row in planned:
        name = row["module"]

        def hook(_module, _inputs, output, module_name=name):
            value = tensor_from(output)
            state = active_state.get(module_name)
            if value is None or state is None:
                return
            flat = value.detach().reshape(-1)
            state["calls"] += 1
            state["total_elements"] += flat.numel()
            state["output_signatures"].add(
                json.dumps(
                    {
                        "shape": list(value.shape),
                        "dtype": str(value.dtype).removeprefix("torch."),
                    },
                    separators=(",", ":"),
                    sort_keys=True,
                )
            )
            take = min(PER_CALL_CANDIDATES, flat.numel())
            if take == 0:
                return
            stride = max(1, math.ceil(flat.numel() / take))
            candidates = flat[::stride][:take].to(device="cpu", dtype=torch.float32).tolist()
            for candidate in candidates:
                if not math.isfinite(candidate):
                    state["nonfinite"] += 1
                    continue
                state["seen"] += 1
                if len(state["samples"]) < sample_limit:
                    state["samples"].append(candidate)
                else:
                    replacement = state["rng"].randrange(state["seen"])
                    if replacement < sample_limit:
                        state["samples"][replacement] = candidate

        handles.append(named[name].register_forward_hook(hook))

    case_reports = []
    try:
        for case in cases:
            active_state.clear()
            for row in planned:
                name = row["module"]
                seed_material = f"{case['id']}\0{name}\0{plan_hash}".encode()
                seed = int.from_bytes(hashlib.sha256(seed_material).digest()[:8], "big")
                active_state[name] = {
                    "samples": [],
                    "seen": 0,
                    "calls": 0,
                    "nonfinite": 0,
                    "total_elements": 0,
                    "output_signatures": set(),
                    "rng": random.Random(seed),
                }
            with torch.inference_mode():
                generated = model.generate_custom_voice(
                    text=case["text"],
                    language="Chinese",
                    speaker=case["speaker"],
                    instruct=case.get("instruct") or None,
                )
            del generated
            rows = []
            for planned_row in planned:
                name = planned_row["module"]
                state = active_state[name]
                samples = state["samples"]
                stats = sample_stats(
                    samples,
                    state["seen"],
                    state["calls"],
                    state["nonfinite"],
                    state["total_elements"],
                    state["output_signatures"],
                )
                stats.update(
                    {
                        "module": name,
                        "tensor": planned_row["tensor"],
                        "family": planned_row["family"],
                        "static_q8_nrmse": planned_row.get("static_q8_nrmse"),
                        "static_entropy_256": planned_row.get("static_entropy_256"),
                        "sample_sha256": hashlib.sha256(
                            json.dumps(samples, separators=(",", ":")).encode()
                        ).hexdigest(),
                    }
                )
                rows.append(stats)
            case_reports.append({"case": case, "rows": rows})
            print(
                json.dumps(
                    {
                        "progress": "case_complete",
                        "case_id": case["id"],
                        "cases_completed": len(case_reports),
                        "cases_total": len(cases),
                    },
                    ensure_ascii=False,
                ),
                flush=True,
            )
    finally:
        for handle in handles:
            handle.remove()

    empty = [
        f"{case_report['case']['id']}:{row['module']}"
        for case_report in case_reports
        for row in case_report["rows"]
        if row["sample_count"] == 0
    ]
    nonfinite = [
        f"{case_report['case']['id']}:{row['module']}:{row['nonfinite_candidates']}"
        for case_report in case_reports
        for row in case_report["rows"]
        if row["nonfinite_candidates"] > 0
    ]
    full_case_ids = [case["id"] for case in corpus["cases"]]
    observed_case_ids = [case_report["case"]["id"] for case_report in case_reports]
    is_full_calibration = (
        args.max_modules == len(plan["modules"])
        and len(plan["modules"]) == plan["selection"]["selected_count"]
        and observed_case_ids == full_case_ids
    )
    if empty:
        status = "INCOMPLETE_EMPTY_ACTIVATIONS"
    elif nonfinite:
        status = "INCOMPLETE_NONFINITE_ACTIVATIONS"
    elif is_full_calibration:
        status = "CAPTURED_READ_ONLY_FULL"
    else:
        status = "CAPTURED_READ_ONLY_SMOKE"
    report = {
        "schema": SCHEMA,
        "status": status,
        "plan_sha256": plan_hash,
        "corpus_sha256": sha256(args.corpus),
        "model": str(model_root),
        "model_assets": model_assets,
        "runtime": {
            "python": sys.version.split()[0],
            "torch": torch.__version__,
            "qwen_tts": importlib.metadata.version("qwen-tts"),
            "generation_api": "generate_custom_voice",
            "language": "Chinese",
            "seed": "unsupported_by_runtime",
        },
        "device": args.device,
        "dtype": runtime_dtype,
        "planned_modules": args.max_modules,
        "resolved_modules": len(planned),
        "resolved_bindings": resolved_bindings,
        "cases_requested": len(cases),
        "cases_completed": len(case_reports),
        "sampling": {
            "algorithm": "deterministic_bounded_reservoir_over_even_per_call_candidates",
            "values_per_module_case_max": sample_limit,
            "candidate_values_per_hook_call_max": PER_CALL_CANDIDATES,
            "retains_full_activations": False,
            "range_boundary": "sample_only_not_full_activation_extrema",
            "entropy_boundary": "sample_normalized_per_module_case_not_fixed_global_edges",
        },
        "writes_audio": False,
        "mutates_weights": False,
        "allows_candidate_generation": False,
        "allows_runtime_wiring_or_promotion": False,
        "empty_activations": empty,
        "nonfinite_activations": nonfinite,
        "cases": case_reports,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "status": status,
                "resolved_modules": len(planned),
                "cases_completed": len(case_reports),
                "empty_activations": len(empty),
                "nonfinite_activations": len(nonfinite),
            },
            ensure_ascii=False,
        )
    )
    return 0 if status in {"CAPTURED_READ_ONLY_SMOKE", "CAPTURED_READ_ONLY_FULL"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
