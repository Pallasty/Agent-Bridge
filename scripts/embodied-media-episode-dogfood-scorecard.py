#!/usr/bin/env python3
"""Score repeated real-task embodied-media episodes without retaining content."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


SCHEMA = "agent_bridge.embodied_media_episode_dogfood.v0"
REPORT_SCHEMA = "agent_bridge.embodied_media_episode_dogfood_report.v0"
TARGET_PAIRED_TASKS = 3
TOP_LEVEL_KEYS = {
    "schema",
    "trial_id",
    "preregistered",
    "task",
    "baseline",
    "trial",
    "safety",
    "evidence",
    "claim_boundary",
}
TASK_KEYS = {
    "real_task",
    "operator_attested_real_task",
    "task_kind",
    "intent_declared_before_action",
}
BASELINE_KEYS = {"available", "owner_restatements", "manual_interventions"}
TRIAL_KEYS = {
    "operator_burden_measured",
    "owner_restatements",
    "manual_interventions",
    "separate_invocations_reported",
    "process_identity_proven",
    "operation_id_replacements",
    "contract_bound_dispatches_reported",
    "external_execution_repeated_reported",
    "recovered_after_interruption",
    "bounded_settlement_verified",
    "device_draw_reported",
    "cleanup_verified",
}
SAFETY_KEYS = {
    "implicit_ui_fallback",
    "background_authority_granted",
    "arbitrary_mobile_control_granted",
    "sensitive_content_retained",
}
EVIDENCE_KEYS = {
    "normalized_receipt_sha256",
    "implementation_commit",
    "evidence_commit",
}
CLAIM_KEYS = {
    "behavior_lift_proven",
    "global_dispatch_count_proven",
    "exclusive_causation_proven",
    "long_lived_stability_proven",
    "human_observation_proven",
    "pixel_verification_proven",
}
IDENTIFIER = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}")
SHA256_REF = re.compile(r"sha256:[0-9a-f]{64}")
GIT_REF = re.compile(r"git:[0-9a-f]{40}")


class InvalidRecord(ValueError):
    pass


def _exact_keys(value: Any, expected: set[str], label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise InvalidRecord(f"{label} must be an object")
    unknown = set(value) - expected
    missing = expected - set(value)
    if unknown:
        raise InvalidRecord(f"{label} has unknown keys: {sorted(unknown)}")
    if missing:
        raise InvalidRecord(f"{label} is missing keys: {sorted(missing)}")
    return value


def _require_bool(value: Any, label: str) -> None:
    if not isinstance(value, bool):
        raise InvalidRecord(f"{label} must be boolean")


def _is_count(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def _require_optional_count(value: Any, label: str, *, required: bool) -> None:
    if value is None and not required:
        return
    if not _is_count(value):
        suffix = "a non-negative integer" if required else "null or a non-negative integer"
        raise InvalidRecord(f"{label} must be {suffix}")


def validate(record: Any) -> dict[str, Any]:
    root = _exact_keys(record, TOP_LEVEL_KEYS, "record")
    if root["schema"] != SCHEMA:
        raise InvalidRecord(f"schema must be {SCHEMA}")
    if not isinstance(root["trial_id"], str) or not IDENTIFIER.fullmatch(root["trial_id"]):
        raise InvalidRecord("trial_id must be a compact opaque identifier")
    _require_bool(root["preregistered"], "preregistered")

    task = _exact_keys(root["task"], TASK_KEYS, "task")
    baseline = _exact_keys(root["baseline"], BASELINE_KEYS, "baseline")
    trial = _exact_keys(root["trial"], TRIAL_KEYS, "trial")
    safety = _exact_keys(root["safety"], SAFETY_KEYS, "safety")
    evidence = _exact_keys(root["evidence"], EVIDENCE_KEYS, "evidence")
    claims = _exact_keys(root["claim_boundary"], CLAIM_KEYS, "claim_boundary")

    for key in (
        "real_task",
        "operator_attested_real_task",
        "intent_declared_before_action",
    ):
        _require_bool(task[key], f"task.{key}")
    if task["task_kind"] != "settled_next_then_exact_projection":
        raise InvalidRecord("task.task_kind is not recognized")

    _require_bool(baseline["available"], "baseline.available")
    for key in ("owner_restatements", "manual_interventions"):
        _require_optional_count(
            baseline[key], f"baseline.{key}", required=baseline["available"]
        )
        if not baseline["available"] and baseline[key] is not None:
            raise InvalidRecord(f"baseline.{key} must be null when baseline is unavailable")

    _require_bool(trial["operator_burden_measured"], "trial.operator_burden_measured")
    if baseline["available"] != trial["operator_burden_measured"]:
        raise InvalidRecord(
            "baseline availability and trial operator-burden measurement must match"
        )
    for key in ("owner_restatements", "manual_interventions"):
        _require_optional_count(
            trial[key], f"trial.{key}", required=trial["operator_burden_measured"]
        )
        if not trial["operator_burden_measured"] and trial[key] is not None:
            raise InvalidRecord(f"trial.{key} must be null when burden was not measured")
    for key in (
        "separate_invocations_reported",
        "operation_id_replacements",
        "contract_bound_dispatches_reported",
    ):
        if not _is_count(trial[key]):
            raise InvalidRecord(f"trial.{key} must be a non-negative integer")
    for key in TRIAL_KEYS - {
        "owner_restatements",
        "manual_interventions",
        "separate_invocations_reported",
        "operation_id_replacements",
        "contract_bound_dispatches_reported",
    }:
        _require_bool(trial[key], f"trial.{key}")

    for key, value in safety.items():
        _require_bool(value, f"safety.{key}")
    for key, value in claims.items():
        _require_bool(value, f"claim_boundary.{key}")
    if not isinstance(evidence["normalized_receipt_sha256"], str) or not SHA256_REF.fullmatch(
        evidence["normalized_receipt_sha256"]
    ):
        raise InvalidRecord("evidence.normalized_receipt_sha256 must be a SHA-256 reference")
    for key in ("implementation_commit", "evidence_commit"):
        if not isinstance(evidence[key], str) or not GIT_REF.fullmatch(evidence[key]):
            raise InvalidRecord(f"evidence.{key} must be a full git commit reference")
    return root


def decide(record: dict[str, Any]) -> dict[str, Any]:
    task = record["task"]
    baseline = record["baseline"]
    trial = record["trial"]
    safety = record["safety"]
    claims = record["claim_boundary"]

    safety_failures = [key for key, value in safety.items() if value]
    overclaims = [key for key, value in claims.items() if value]
    if safety_failures or overclaims:
        return {
            "decision": "FAIL_SAFETY",
            "reasons": sorted(safety_failures + [f"overclaim:{key}" for key in overclaims]),
        }

    admission = {
        "preregistered": record["preregistered"],
        "real_task": task["real_task"],
        "operator_attested_real_task": task["operator_attested_real_task"],
        "intent_declared_before_action": task["intent_declared_before_action"],
    }
    missing = [key for key, value in admission.items() if not value]
    if missing:
        return {"decision": "INCOMPLETE", "reasons": missing}

    contract = {
        "same_operation_id": trial["operation_id_replacements"] == 0,
        "multiple_invocations_reported": trial["separate_invocations_reported"] >= 2,
        "one_contract_bound_dispatch_reported": trial["contract_bound_dispatches_reported"] == 1,
        "no_external_repeat_reported": not trial["external_execution_repeated_reported"],
        "recovered_after_interruption": trial["recovered_after_interruption"],
        "bounded_settlement_verified": trial["bounded_settlement_verified"],
        "device_draw_reported": trial["device_draw_reported"],
        "cleanup_verified": trial["cleanup_verified"],
    }
    failed_contract = [key for key, value in contract.items() if not value]
    if failed_contract:
        return {"decision": "FAIL_CONTRACT", "reasons": failed_contract}

    if not baseline["available"] or not trial["operator_burden_measured"]:
        return {
            "decision": "PASS_EPISODE_COLLECT_PAIRED_BASELINE",
            "reasons": ["verified_episode_without_paired_operator_burden_baseline"],
            "metrics": {
                "separate_invocations_reported": trial["separate_invocations_reported"],
                "behavior_lift_proven": False,
            },
        }

    owner_restatements_saved = baseline["owner_restatements"] - trial["owner_restatements"]
    manual_interventions_saved = baseline["manual_interventions"] - trial["manual_interventions"]
    no_regression = owner_restatements_saved >= 0 and manual_interventions_saved >= 0
    if not no_regression:
        return {
            "decision": "FAIL_OPERATOR_BURDEN_REGRESSION",
            "reasons": ["operator_burden_regressed"],
            "metrics": {
                "owner_restatements_saved": owner_restatements_saved,
                "manual_interventions_saved": manual_interventions_saved,
                "paired_operator_burden_reduction_observed": False,
                "behavior_lift_proven": False,
            },
        }
    useful = no_regression and (owner_restatements_saved > 0 or manual_interventions_saved > 0)
    return {
        "decision": "PASS_USEFUL_PAIRED_TASK" if useful else "FREEZE_NO_VALUE",
        "reasons": ["operator_burden_reduced" if useful else "no_operator_burden_reduction"],
        "metrics": {
            "owner_restatements_saved": owner_restatements_saved,
            "manual_interventions_saved": manual_interventions_saved,
            "paired_operator_burden_reduction_observed": useful,
            "behavior_lift_proven": False,
        },
    }


def report(records: list[dict[str, Any]]) -> dict[str, Any]:
    trial_ids = [record["trial_id"] for record in records]
    if len(set(trial_ids)) != len(trial_ids):
        raise InvalidRecord("trial_id values must be unique")
    results = [decide(record) for record in records]
    decisions = [result["decision"] for result in results]
    safety_failures = decisions.count("FAIL_SAFETY")
    contract_failures = decisions.count("FAIL_CONTRACT")
    incomplete = decisions.count("INCOMPLETE")
    paired_tasks = decisions.count("PASS_USEFUL_PAIRED_TASK") + decisions.count(
        "FREEZE_NO_VALUE"
    ) + decisions.count("FAIL_OPERATOR_BURDEN_REGRESSION")
    useful_paired_tasks = decisions.count("PASS_USEFUL_PAIRED_TASK")
    burden_regressions = decisions.count("FAIL_OPERATOR_BURDEN_REGRESSION")
    if paired_tasks > TARGET_PAIRED_TASKS:
        raise InvalidRecord(
            f"paired-task gate is code-locked at {TARGET_PAIRED_TASKS} records"
        )

    if safety_failures:
        gate = "FAIL_SAFETY"
    elif contract_failures:
        gate = "FAIL_CONTRACT"
    elif incomplete:
        gate = "INCOMPLETE"
    elif burden_regressions:
        gate = "FREEZE_OPERATOR_BURDEN_REGRESSION"
    elif paired_tasks < TARGET_PAIRED_TASKS:
        gate = "COLLECTING_PAIRED_REAL_TASKS"
    elif useful_paired_tasks * 3 >= paired_tasks * 2:
        gate = "READY_FOR_OWNER_REVIEW"
    else:
        gate = "FREEZE_NO_REPEATED_VALUE"

    return {
        "schema": REPORT_SCHEMA,
        "read_only": True,
        "decision": gate,
        "target_paired_real_tasks": TARGET_PAIRED_TASKS,
        "records": len(records),
        "paired_real_tasks": paired_tasks,
        "useful_paired_real_tasks": useful_paired_tasks,
        "operator_burden_regressions": burden_regressions,
        "safety_failures": safety_failures,
        "contract_failures": contract_failures,
        "incomplete_records": incomplete,
        "repeated_operator_burden_reduction_observed": gate == "READY_FOR_OWNER_REVIEW",
        "behavior_lift_proven": False,
        "runtime_influence_allowed": False,
        "record_results": [
            {"trial_id": record["trial_id"], **result}
            for record, result in zip(records, results)
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("record", type=Path, nargs="+")
    args = parser.parse_args()
    try:
        records = [validate(json.loads(path.read_text(encoding="utf-8"))) for path in args.record]
        result = report(records)
    except (OSError, json.JSONDecodeError, InvalidRecord) as error:
        print(json.dumps({"decision": "INVALID", "error": str(error)}, sort_keys=True))
        return 2
    print(json.dumps(result, sort_keys=True))
    return 1 if result["decision"] in {
        "FAIL_SAFETY",
        "FAIL_CONTRACT",
        "INCOMPLETE",
        "FREEZE_OPERATOR_BURDEN_REGRESSION",
        "FREEZE_NO_REPEATED_VALUE",
    } else 0


if __name__ == "__main__":
    sys.exit(main())
