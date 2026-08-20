#!/usr/bin/env python3
"""Reduce frozen codec runtime evidence into a non-authorizing route decision."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path


SCHEMAS = {
    "packed": "agent_bridge.qwen3_tts.codec_linear_packed_q8_feasibility.v1",
    "coreml": "agent_bridge.qwen3_tts.codec_linear_coreml_probe.v1",
    "e2e": "agent_bridge.qwen3_tts.codec_scope3_e2e_reduction.v1",
}
OUTPUT_SCHEMA = "agent_bridge.qwen3_tts.codec_runtime_route_decision.v1"
AUTHORIZATION = {
    "allows_checkpoint_rewrite": False,
    "allows_custom_kernel_build": False,
    "allows_runtime_wiring": False,
    "allows_deployment": False,
    "allows_promotion": False,
}


class RouteError(ValueError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RouteError(message)


def load(path: Path, expected_schema: str) -> tuple[dict, bytes]:
    require(path.is_file() and not path.is_symlink(), f"input_not_regular_file:{path}")
    raw = path.read_bytes()
    try:
        value = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise RouteError(f"invalid_json:{path}") from error
    require(isinstance(value, dict), f"expected_object:{path}")
    require(value.get("schema") == expected_schema, f"schema_mismatch:{path}")
    return value, raw


def number(value: object, name: str) -> float:
    require(isinstance(value, (int, float)) and not isinstance(value, bool), f"{name}:number")
    result = float(value)
    require(math.isfinite(result), f"{name}:finite")
    return result


def object_value(value: object, name: str) -> dict:
    require(isinstance(value, dict), f"{name}:object")
    return value


def rows_value(value: object, name: str) -> list[dict]:
    require(isinstance(value, list) and value, f"{name}:nonempty_array")
    require(all(isinstance(row, dict) for row in value), f"{name}:object_rows")
    return value


def write_exclusive(path: Path, payload: bytes) -> None:
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(payload)
    except BaseException:
        try:
            path.unlink()
        except FileNotFoundError:
            pass
        raise


def build(args: argparse.Namespace) -> tuple[dict, dict[str, bytes]]:
    packed, packed_raw = load(args.packed, SCHEMAS["packed"])
    coreml, coreml_raw = load(args.coreml, SCHEMAS["coreml"])
    e2e, e2e_raw = load(args.e2e, SCHEMAS["e2e"])
    packed_rows = rows_value(packed.get("rows"), "packed.rows")
    coreml_latency = object_value(coreml.get("latency_ms"), "coreml.latency_ms")
    coreml_numeric = object_value(coreml.get("numeric"), "coreml.numeric")
    e2e_rows = rows_value(e2e.get("cases"), "e2e.cases")
    memory = object_value(e2e.get("memory"), "e2e.memory")
    packed_slowdown = max(number(row.get("slowdown"), "packed.slowdown") for row in packed_rows)
    coreml_ratio = number(coreml_latency.get("fastest_coreml_q8_vs_mps_fake"), "coreml.ratio")
    coreml_nrmse = number(coreml_numeric.get("coreml_q8_vs_frozen_fake_q8_nrmse"), "coreml.nrmse")
    e2e_ratio = max(number(row.get("q8_to_fp16_ratio"), "e2e.ratio") for row in e2e_rows)
    fp16_steady = number(memory.get("fp16_steady_bytes"), "e2e.fp16_steady_bytes")
    original_scope_raw = memory.get("original_fp16_scope_parameter_bytes_retained")
    original_scope = number(original_scope_raw, "e2e.original_scope")
    sidecar = number(memory.get("sidecar_bytes"), "e2e.sidecar_bytes")
    memory_delta_raw = memory.get("q8_minus_fp16_bytes")
    number(memory_delta_raw, "e2e.memory_delta")
    require(fp16_steady > 0 and original_scope >= 0 and sidecar >= 0, "e2e.memory:range")
    theoretical_fraction = max(0.0, original_scope - sidecar) / fp16_steady
    inputs = {"packed.json": packed_raw, "coreml.json": coreml_raw, "e2e.json": e2e_raw}
    decision = {
        "schema": OUTPUT_SCHEMA,
        "status": "PAUSE_CURRENT_CODEC_RUNTIME_ROUTES",
        "inputs": {name: {"path": f"inputs/{name}", "sha256": hashlib.sha256(raw).hexdigest()}
                   for name, raw in inputs.items()},
        "thresholds": {
            "max_latency_ratio": 1.05,
            "max_kernel_nrmse": 0.002,
            "minimum_model_memory_saving_fraction_for_checkpoint_rewrite": 0.05,
        },
        "routes": [
            {"route": "reversible_sidecar", "decision": "reject",
             "observed_max_latency_ratio": e2e_ratio,
             "observed_runtime_memory_delta_bytes": memory_delta_raw,
             "retained_fp16_scope_parameter_bytes": original_scope_raw,
             "reason": "original_fp16_weights_retained_and_sidecar_added"},
            {"route": "current_packed_mps_kernel", "decision": "reject",
             "observed_max_module_slowdown": packed_slowdown,
             "reason": "packed_kernel_exceeds_latency_limit"},
            {"route": "current_coreml_handoff", "decision": "reject",
             "observed_latency_ratio": coreml_ratio, "observed_kernel_nrmse": coreml_nrmse,
             "reason": "handoff_exceeds_latency_and_numeric_limits"},
            {"route": "three_module_checkpoint_rewrite", "decision": "defer",
             "theoretical_model_memory_saving_fraction": theoretical_fraction,
             "reason": "scope_benefit_below_checkpoint_rewrite_minimum"},
        ],
        "reopen_requirements": [
            "native_fused_kernel_or_equivalent_runtime_without_fp16_weight_retention",
            "projected_model_memory_saving_fraction_at_least_0.05",
            "full_frozen_corpus_runtime_coverage",
            "end_to_end_latency_ratio_at_most_1.05",
            "runtime_memory_delta_bytes_below_0",
            "fresh_waveform_and_blind_listening_evidence",
        ],
        "authorization": dict(AUTHORIZATION),
    }
    return decision, inputs


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--packed", required=True, type=Path)
    parser.add_argument("--coreml", required=True, type=Path)
    parser.add_argument("--e2e", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    try:
        require(not args.output_dir.exists() and not args.output_dir.is_symlink(),
                f"output_directory_exists:{args.output_dir}")
        decision, inputs = build(args)
        os.mkdir(args.output_dir, 0o700)
        os.mkdir(args.output_dir / "inputs", 0o700)
        for name, raw in inputs.items():
            write_exclusive(args.output_dir / "inputs" / name, raw)
        rendered = (json.dumps(decision, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode()
        write_exclusive(args.output_dir / "decision.json", rendered)
    except (RouteError, OSError) as error:
        parser.error(str(error))
    print(json.dumps({"status": decision["status"], "output": str(args.output_dir)}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
