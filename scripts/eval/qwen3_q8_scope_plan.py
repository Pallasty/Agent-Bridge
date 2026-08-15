#!/usr/bin/env python3
"""Build a deterministic, non-writing fake-Q8 perturbation order from calibration."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import statistics
from pathlib import Path


SCHEMA = "agent_bridge.qwen3_tts.q8_perturbation_scope_plan.v0"
CAPTURE_SCHEMA = "agent_bridge.qwen3_tts.activation_capture.v0"
PLAN_SCHEMA = "agent_bridge.qwen3_tts.activation_probe_plan.v1"
GATE_SCHEMA = "agent_bridge.qwen3_tts.activation_calibration_gate.v0"
GATE_STATUS = "READY_FOR_FUNCTIONAL_SENSITIVITY_DESIGN"
RISK_WEIGHTS = {
    "static_q8_nrmse": 0.25,
    "activation_outlier": 0.20,
    "activation_kurtosis": 0.20,
    "activation_rms_cv": 0.15,
    "activation_entropy_256": 0.10,
    "static_entropy_256": 0.10,
}
TARGET_PERTURBATION_MODULES = 48
MIN_SAMPLES_PER_MODULE_CASE = 1024
GROUP_SIZE = 128
SCALE_BYTES = 2


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def percentile_ranks(rows: list[dict], field: str) -> dict[str, float]:
    ordered = sorted(rows, key=lambda row: (row[field], row["module"]))
    denominator = max(1, len(ordered) - 1)
    return {row["module"]: index / denominator for index, row in enumerate(ordered)}


def aggregate(plan: dict, capture: dict) -> list[dict]:
    per_module: dict[str, list[dict]] = {}
    for case_report in capture["cases"]:
        for row in case_report["rows"]:
            per_module.setdefault(row["module"], []).append(row)
    rows = []
    planned_by_name = {row["module"]: row for row in plan["modules"][: capture["planned_modules"]]}
    for module, planned in planned_by_name.items():
        observations = per_module.get(module, [])
        rms_values = [row["rms"] for row in observations if row["rms"] is not None]
        rms_mean = statistics.fmean(rms_values) if rms_values else math.inf
        rms_cv = statistics.pstdev(rms_values) / rms_mean if rms_values and rms_mean > 0 else math.inf
        rows.append(
            {
                "module": module,
                "tensor": planned["tensor"],
                "family": planned["family"],
                "elements": planned["elements"],
                "case_count": len(observations),
                "min_sample_count": min((row["sample_count"] for row in observations), default=0),
                "nonfinite_candidates": sum(row["nonfinite_candidates"] for row in observations),
                "static_q8_nrmse": float(planned["static_q8_nrmse"]),
                "static_entropy_256": float(planned["static_entropy_256"]),
                "activation_outlier": max((row["outlier_ratio_6x_median_abs"] for row in observations), default=math.inf),
                "activation_kurtosis": max((row["kurtosis"] for row in observations), default=math.inf),
                "activation_rms_cv": rms_cv,
                "activation_entropy_256": statistics.fmean(
                    row["normalized_entropy"]["256"] for row in observations
                )
                if observations
                else math.inf,
            }
        )
    return rows


def build_scope(
    plan: dict,
    capture: dict,
    plan_hash: str,
    capture_hash: str,
    gate_hash: str,
) -> dict:
    rows = aggregate(plan, capture)
    fields = list(RISK_WEIGHTS)
    ranks = {field: percentile_ranks(rows, field) for field in fields}
    for row in rows:
        row["risk_components"] = {field: ranks[field][row["module"]] for field in fields}
        row["joint_risk_score"] = sum(
            RISK_WEIGHTS[field] * row["risk_components"][field] for field in fields
        )
        row["eligible_for_future_perturbation_design"] = (
            row["case_count"] == capture["cases_completed"]
            and row["min_sample_count"] >= MIN_SAMPLES_PER_MODULE_CASE
            and row["nonfinite_candidates"] == 0
            and all(math.isfinite(row[field]) for field in fields)
        )
    qualified = sorted(
        (row for row in rows if row["eligible_for_future_perturbation_design"]),
        key=lambda row: (row["joint_risk_score"], row["module"]),
    )
    perturbation_scope = qualified[:TARGET_PERTURBATION_MODULES]
    perturbation_names = {row["module"] for row in perturbation_scope}
    for row in rows:
        row["proposed_mode_if_separately_authorized"] = (
            "ONE_MODULE_AT_A_TIME_FAKE_Q8_GROUPWISE_SYMMETRIC"
            if row["module"] in perturbation_names
            else "BF16_CONTROL_NOT_IN_FIRST_PERTURBATION_SET"
        )
        row["decision_reason"] = (
            "lowest_joint_risk_preregistered_first_functional_sensitivity_set"
            if row["module"] in perturbation_names
            else "conservative_holdback_or_insufficient_activation_evidence"
        )
    source_bytes = sum(row["elements"] * 2 for row in perturbation_scope)
    packed_bytes = sum(
        row["elements"] + math.ceil(row["elements"] / GROUP_SIZE) * SCALE_BYTES
        for row in perturbation_scope
    )
    ready = len(perturbation_scope) == TARGET_PERTURBATION_MODULES
    return {
        "schema": SCHEMA,
        "status": (
            "Q8_PERTURBATION_SCOPE_PLANNED_DEFAULT_OFF"
            if ready
            else "BLOCKED_INSUFFICIENT_CALIBRATION_COVERAGE"
        ),
        "activation_plan_sha256": plan_hash,
        "activation_capture_sha256": capture_hash,
        "activation_gate_sha256": gate_hash,
        "policy": {
            "target_perturbation_modules": TARGET_PERTURBATION_MODULES,
            "minimum_samples_per_module_case": MIN_SAMPLES_PER_MODULE_CASE,
            "risk_weights": RISK_WEIGHTS,
            "selection": (
                "lowest joint-risk qualified modules with deterministic module-name tie "
                "break, evaluated one module at a time against the unchanged FP16 control"
            ),
            "fake_q8_group_size": GROUP_SIZE,
            "hypothetical_q8_scale_bytes": SCALE_BYTES,
            "untouched_partitions": [
                "speech_tokenizer_codec",
                "text_embedding",
                "code_predictor",
                "norm_scale_or_bias",
                "all_talker_matrices_outside_the_selected_96",
            ],
        },
        "summary": {
            "calibrated_modules": len(rows),
            "activation_evidence_eligible_modules": len(qualified),
            "first_perturbation_scope_modules": len(perturbation_scope),
            "bf16_control_modules_within_plan": len(rows) - len(perturbation_scope),
            "eligible_but_not_calibrated_modules": plan["selection"]["eligible_count"] - len(rows),
            "hypothetical_scope_source_bytes": source_bytes,
            "hypothetical_scope_packed_bytes": packed_bytes,
            "hypothetical_scope_savings_bytes": source_bytes - packed_bytes,
            "hypothetical_scope_savings_fraction": (source_bytes - packed_bytes) / source_bytes
            if source_bytes
            else 0.0,
        },
        "modules": sorted(rows, key=lambda row: row["module"]),
        "authorization": {
            "allows_fake_quant_execution": False,
            "allows_quantized_weight_writing": False,
            "allows_candidate_generation": False,
            "allows_runtime_wiring_or_promotion": False,
        },
        "functional_sensitivity_executed": False,
        "writes_quantized_weights": False,
        "creates_runtime_candidate": False,
        "allows_fake_quant_execution": False,
        "allows_quantized_weight_writing": False,
        "allows_runtime_wiring_or_promotion": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", required=True, type=Path)
    parser.add_argument("--capture", required=True, type=Path)
    parser.add_argument("--gate", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("refusing to overwrite output")
    plan = json.loads(args.plan.read_text(encoding="utf-8"))
    capture = json.loads(args.capture.read_text(encoding="utf-8"))
    gate = json.loads(args.gate.read_text(encoding="utf-8"))
    if plan.get("schema") != PLAN_SCHEMA or capture.get("schema") != CAPTURE_SCHEMA:
        parser.error("unexpected plan or capture schema")
    if gate.get("schema") != GATE_SCHEMA or gate.get("status") != GATE_STATUS:
        parser.error("accepted activation-calibration gate is required")
    if capture.get("status") != "CAPTURED_READ_ONLY_FULL":
        parser.error("full 96-module frozen-corpus activation capture is required")
    plan_hash = sha256(args.plan)
    capture_hash = sha256(args.capture)
    if capture.get("plan_sha256") != plan_hash:
        parser.error("capture does not bind the supplied activation plan")
    if gate.get("activation_plan_sha256") != plan_hash:
        parser.error("activation gate does not bind the supplied plan")
    if gate.get("activation_capture_sha256") != capture_hash:
        parser.error("activation gate does not bind the supplied capture")
    if gate.get("allows_functional_sensitivity_design") is not True:
        parser.error("activation gate does not admit functional-sensitivity design")
    report = build_scope(plan, capture, plan_hash, capture_hash, sha256(args.gate))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"status": report["status"], **report["summary"]}, ensure_ascii=False))
    return 0 if report["status"] == "Q8_PERTURBATION_SCOPE_PLANNED_DEFAULT_OFF" else 2


if __name__ == "__main__":
    raise SystemExit(main())
