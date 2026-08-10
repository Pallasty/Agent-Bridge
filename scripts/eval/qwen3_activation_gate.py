#!/usr/bin/env python3
"""Fail closed over a frozen Qwen3-TTS activation-calibration receipt."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


SCHEMA = "agent_bridge.qwen3_tts.activation_calibration_gate.v0"
POLICY_SCHEMA = "agent_bridge.qwen3_tts.activation_calibration_policy.v0"
PLAN_SCHEMA = "agent_bridge.qwen3_tts.activation_probe_plan.v1"
CAPTURE_SCHEMA = "agent_bridge.qwen3_tts.activation_capture.v0"
CORPUS_SCHEMA = "agent_bridge.qwen3_tts.quantization_corpus.v0"
LADDER_SCHEMA = "agent_bridge.qwen3_tts.activation_resource_ladder.v0"
READY = "READY_FOR_FUNCTIONAL_SENSITIVITY_DESIGN"
BLOCKED = "BLOCKED_ACTIVATION_CALIBRATION_EVIDENCE"


def is_sha256(value) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def evaluate(
    policy: dict,
    plan: dict,
    capture: dict,
    corpus: dict,
    resource_ladder: dict,
    policy_hash: str,
    plan_hash: str,
    capture_hash: str,
    corpus_hash: str,
    resource_ladder_hash: str,
) -> dict:
    failures: list[str] = []

    def require(condition: bool, code: str) -> None:
        if not condition:
            failures.append(code)

    plan_policy = policy.get("activation_plan", {})
    corpus_policy = policy.get("corpus", {})
    requirements = policy.get("capture_requirements", {})
    model_policy = policy.get("source_model", {})
    ladder_policy = policy.get("resource_ladder", {})
    expected_modules = int(plan_policy.get("selected_modules", 0))
    minimum_samples = int(requirements.get("minimum_samples_per_module_case", 0))

    require(policy.get("schema") == POLICY_SCHEMA, "policy_schema_mismatch")
    require(plan.get("schema") == PLAN_SCHEMA, "plan_schema_mismatch")
    require(capture.get("schema") == CAPTURE_SCHEMA, "capture_schema_mismatch")
    require(corpus.get("schema") == CORPUS_SCHEMA, "corpus_schema_mismatch")
    require(resource_ladder.get("schema") == LADDER_SCHEMA, "resource_ladder_schema_mismatch")
    require(plan_hash == plan_policy.get("sha256"), "plan_hash_not_frozen")
    require(corpus_hash == corpus_policy.get("sha256"), "corpus_hash_not_frozen")
    require(
        plan.get("static_report_sha256") == plan_policy.get("static_report_sha256"),
        "static_report_hash_mismatch",
    )
    require(
        plan.get("selection", {}).get("algorithm") == plan_policy.get("selection_algorithm"),
        "selection_algorithm_mismatch",
    )
    require(
        len(plan.get("modules", [])) == expected_modules
        and plan.get("selection", {}).get("selected_count") == expected_modules,
        "planned_module_count_mismatch",
    )
    require(capture.get("status") == "CAPTURED_READ_ONLY_FULL", "capture_not_full")
    require(capture.get("plan_sha256") == plan_hash, "capture_plan_hash_mismatch")
    require(capture.get("corpus_sha256") == corpus_hash, "capture_corpus_hash_mismatch")
    require(capture.get("device") == model_policy.get("device"), "capture_device_mismatch")
    require(capture.get("dtype") == model_policy.get("runtime_dtype"), "capture_dtype_mismatch")
    expected_runtime = model_policy.get("runtime", {})
    observed_runtime = capture.get("runtime", {})
    for field in ("python", "torch", "qwen_tts", "generation_api", "language"):
        require(
            observed_runtime.get(field) == expected_runtime.get(field),
            f"capture_runtime_mismatch:{field}",
        )
    require(capture.get("planned_modules") == expected_modules, "capture_planned_count_mismatch")
    require(capture.get("resolved_modules") == expected_modules, "capture_resolved_count_mismatch")
    require(not capture.get("empty_activations"), "empty_activations_present")
    require(not capture.get("nonfinite_activations"), "nonfinite_activations_present")
    require(capture.get("writes_audio") is False, "capture_writes_audio")
    require(capture.get("mutates_weights") is False, "capture_mutates_weights")
    require(
        capture.get("allows_candidate_generation") is False,
        "capture_allows_candidate_generation",
    )
    require(
        capture.get("allows_runtime_wiring_or_promotion") is False,
        "capture_allows_runtime_wiring_or_promotion",
    )

    require(
        resource_ladder_hash == ladder_policy.get("receipt_sha256"),
        "resource_ladder_hash_not_frozen",
    )
    require(
        resource_ladder.get("activation_plan_sha256") == plan_hash,
        "resource_ladder_plan_hash_mismatch",
    )
    require(
        resource_ladder.get("corpus_sha256") == corpus_hash,
        "resource_ladder_corpus_hash_mismatch",
    )
    ladder_runs = resource_ladder.get("runs", [])
    expected_ladder = ladder_policy.get("module_counts", [])
    require(
        [row.get("modules") for row in ladder_runs] == expected_ladder,
        "resource_ladder_module_order_mismatch",
    )
    require(
        [row.get("capture_status") for row in ladder_runs]
        == [
            "CAPTURED_READ_ONLY_SMOKE",
            "CAPTURED_READ_ONLY_SMOKE",
            "CAPTURED_READ_ONLY_SMOKE",
            "CAPTURED_READ_ONLY_FULL",
        ],
        "resource_ladder_status_mismatch",
    )
    require(
        bool(ladder_runs) and ladder_runs[-1].get("report_sha256") == capture_hash,
        "resource_ladder_full_capture_hash_mismatch",
    )
    require(
        all(row.get("swaps") == 0 for row in ladder_runs),
        "resource_ladder_swaps_present",
    )
    require(
        all(row.get("empty_activations") == 0 for row in ladder_runs),
        "resource_ladder_empty_activations_present",
    )
    require(
        all(row.get("nonfinite_activations") == 0 for row in ladder_runs),
        "resource_ladder_nonfinite_activations_present",
    )
    require(
        all(is_sha256(row.get("report_sha256")) for row in ladder_runs),
        "resource_ladder_report_hash_missing",
    )
    require(
        all(is_sha256(row.get("time_log_sha256")) for row in ladder_runs),
        "resource_ladder_time_log_hash_missing",
    )
    for field in (
        "allows_fake_quant_execution",
        "allows_quantized_weight_writing",
        "allows_runtime_candidate_generation",
        "allows_runtime_wiring_or_promotion",
    ):
        require(resource_ladder.get(field) is False, f"resource_ladder_authority:{field}")

    expected_assets = {
        row.get("partition"): (row.get("bytes"), row.get("sha256"))
        for row in policy.get("source_assets", [])
    }
    captured_assets = {
        row.get("partition"): (row.get("bytes"), row.get("sha256"))
        for row in capture.get("model_assets", [])
    }
    require(captured_assets == expected_assets, "source_asset_binding_mismatch")

    plan_by_module = {row.get("module"): row for row in plan.get("modules", [])}
    bindings = capture.get("resolved_bindings", [])
    binding_by_module = {row.get("module"): row for row in bindings}
    require(len(bindings) == expected_modules, "binding_count_mismatch")
    require(set(binding_by_module) == set(plan_by_module), "binding_module_set_mismatch")
    for module, planned in plan_by_module.items():
        binding = binding_by_module.get(module, {})
        require(binding.get("tensor") == planned.get("tensor"), f"binding_tensor_mismatch:{module}")
        require(binding.get("shape") == planned.get("shape"), f"binding_shape_mismatch:{module}")
        require(
            binding.get("source_dtype") == planned.get("source_dtype"),
            f"binding_source_dtype_mismatch:{module}",
        )
        require(
            binding.get("weight_identity_verified") is True,
            f"binding_weight_identity_unverified:{module}",
        )

    expected_cases = corpus.get("cases", [])
    case_reports = capture.get("cases", [])
    require(capture.get("cases_requested") == len(expected_cases), "case_request_count_mismatch")
    require(capture.get("cases_completed") == len(expected_cases), "case_completion_count_mismatch")
    require(
        [row.get("case") for row in case_reports] == expected_cases,
        "case_order_or_content_mismatch",
    )
    expected_module_order = [row.get("module") for row in plan.get("modules", [])]
    for case_report in case_reports:
        case_id = case_report.get("case", {}).get("id", "unknown")
        rows = case_report.get("rows", [])
        require(
            [row.get("module") for row in rows] == expected_module_order,
            f"module_order_mismatch:{case_id}",
        )
        for row in rows:
            module = row.get("module", "unknown")
            require(
                row.get("sample_count", 0) >= minimum_samples,
                f"insufficient_samples:{case_id}:{module}",
            )
            require(
                row.get("nonfinite_candidates") == 0,
                f"nonfinite_candidates:{case_id}:{module}",
            )
            require(
                row.get("total_elements_seen", 0) >= row.get("sample_count", 0),
                f"invalid_element_accounting:{case_id}:{module}",
            )
            require(
                bool(row.get("output_signature_sha256")),
                f"missing_output_signature:{case_id}:{module}",
            )

    failures = sorted(set(failures))
    ready = not failures
    return {
        "schema": SCHEMA,
        "status": READY if ready else BLOCKED,
        "policy_sha256": policy_hash,
        "activation_plan_sha256": plan_hash,
        "activation_capture_sha256": capture_hash,
        "corpus_sha256": corpus_hash,
        "resource_ladder_sha256": resource_ladder_hash,
        "summary": {
            "planned_modules": expected_modules,
            "captured_cases": len(case_reports),
            "module_case_observations": sum(
                len(case_report.get("rows", [])) for case_report in case_reports
            ),
            "minimum_samples_per_module_case": minimum_samples,
            "failure_count": len(failures),
        },
        "failures": failures,
        "activation_calibration_accepted_for_planning": ready,
        "allows_functional_sensitivity_design": ready,
        "allows_fake_quant_execution": False,
        "allows_quantized_weight_writing": False,
        "allows_runtime_candidate_generation": False,
        "allows_runtime_wiring_or_promotion": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--policy", required=True, type=Path)
    parser.add_argument("--plan", required=True, type=Path)
    parser.add_argument("--capture", required=True, type=Path)
    parser.add_argument("--corpus", required=True, type=Path)
    parser.add_argument("--resource-ladder", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    paths = (args.policy, args.plan, args.capture, args.corpus, args.resource_ladder)
    if not all(path.is_file() for path in paths):
        parser.error("policy, plan, capture, corpus, and resource ladder must exist")
    if args.output.exists():
        parser.error("refusing to overwrite output")
    policy = json.loads(args.policy.read_text(encoding="utf-8"))
    plan = json.loads(args.plan.read_text(encoding="utf-8"))
    capture = json.loads(args.capture.read_text(encoding="utf-8"))
    corpus = json.loads(args.corpus.read_text(encoding="utf-8"))
    resource_ladder = json.loads(args.resource_ladder.read_text(encoding="utf-8"))
    report = evaluate(
        policy,
        plan,
        capture,
        corpus,
        resource_ladder,
        sha256(args.policy),
        sha256(args.plan),
        sha256(args.capture),
        sha256(args.corpus),
        sha256(args.resource_ladder),
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"status": report["status"], **report["summary"]}, ensure_ascii=False))
    return 0 if report["status"] == READY else 2


if __name__ == "__main__":
    raise SystemExit(main())
