#!/usr/bin/env python3
"""Validate and decide one preregistered mobile-text real-task dogfood record."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


SCHEMA = "agent_bridge.mobile_text_real_dogfood_scorecard.v1"
TOP_LEVEL_KEYS = {
    "schema",
    "trial_id",
    "preregistered",
    "workflow",
    "baseline",
    "trial",
    "authority",
    "cleanup",
    "evidence",
}
WORKFLOW_KEYS = {"real_task", "task_reference", "needed_fact_declared_before_submit"}
METRIC_KEYS = {"desktop_surface_switches", "desktop_text_or_copy_actions"}
TRIAL_KEYS = {
    *METRIC_KEYS,
    "foreground_user_confirmed",
    "background_capture",
    "implicit_control",
    "unique_observations_accepted",
    "deduplicated_retries",
    "consumed_via_exact_session_status",
    "affected_real_decision",
    "full_text_persisted_outside_mcp_process",
}
AUTHORITY_KEYS = {
    "phone_connection_separately_authorized",
    "apk_mutation_performed",
    "apk_mutation_separately_authorized",
    "runtime_deployment_performed",
    "runtime_deployment_separately_authorized",
    "merge_or_push_performed",
    "merge_or_push_separately_authorized",
}
CLEANUP_KEYS = {"projection_stopped", "fresh_mcp_cannot_retrieve_session"}
EVIDENCE_KEYS = {
    "baseline_reference",
    "acceptance_reference",
    "consumption_reference",
    "decision_reference",
    "cleanup_reference",
}


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


def _is_bool(value: Any) -> bool:
    return isinstance(value, bool)


def _is_count(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def validate(record: Any) -> dict[str, Any]:
    root = _exact_keys(record, TOP_LEVEL_KEYS, "record")
    if root["schema"] != SCHEMA:
        raise InvalidRecord(f"schema must be {SCHEMA}")
    if not isinstance(root["trial_id"], str) or not root["trial_id"].strip():
        raise InvalidRecord("trial_id must be a non-empty string")
    if not _is_bool(root["preregistered"]):
        raise InvalidRecord("preregistered must be boolean")

    workflow = _exact_keys(root["workflow"], WORKFLOW_KEYS, "workflow")
    baseline = _exact_keys(root["baseline"], METRIC_KEYS, "baseline")
    trial = _exact_keys(root["trial"], TRIAL_KEYS, "trial")
    authority = _exact_keys(root["authority"], AUTHORITY_KEYS, "authority")
    cleanup = _exact_keys(root["cleanup"], CLEANUP_KEYS, "cleanup")
    evidence = _exact_keys(root["evidence"], EVIDENCE_KEYS, "evidence")

    for key in ("real_task", "needed_fact_declared_before_submit"):
        if not _is_bool(workflow[key]):
            raise InvalidRecord(f"workflow.{key} must be boolean")
    if not isinstance(workflow["task_reference"], str) or not workflow["task_reference"].strip():
        raise InvalidRecord("workflow.task_reference must be a non-empty string")
    for label, metrics in (("baseline", baseline), ("trial", trial)):
        for key in METRIC_KEYS:
            if not _is_count(metrics[key]):
                raise InvalidRecord(f"{label}.{key} must be a non-negative integer")
    for key in TRIAL_KEYS - METRIC_KEYS - {"unique_observations_accepted", "deduplicated_retries"}:
        if not _is_bool(trial[key]):
            raise InvalidRecord(f"trial.{key} must be boolean")
    for key in ("unique_observations_accepted", "deduplicated_retries"):
        if not _is_count(trial[key]):
            raise InvalidRecord(f"trial.{key} must be a non-negative integer")
    for key, value in authority.items():
        if not _is_bool(value):
            raise InvalidRecord(f"authority.{key} must be boolean")
    for key, value in cleanup.items():
        if not _is_bool(value):
            raise InvalidRecord(f"cleanup.{key} must be boolean")
    for key, value in evidence.items():
        if not isinstance(value, str) or not value.strip():
            raise InvalidRecord(f"evidence.{key} must be a non-empty reference")
    return root


def decide(record: dict[str, Any]) -> dict[str, Any]:
    workflow = record["workflow"]
    baseline = record["baseline"]
    trial = record["trial"]
    authority = record["authority"]
    cleanup = record["cleanup"]

    crossed_authority = any(
        authority[performed] and not authority[authorized]
        for performed, authorized in (
            ("apk_mutation_performed", "apk_mutation_separately_authorized"),
            ("runtime_deployment_performed", "runtime_deployment_separately_authorized"),
            ("merge_or_push_performed", "merge_or_push_separately_authorized"),
        )
    )
    safety_failures = []
    if trial["background_capture"]:
        safety_failures.append("background_capture")
    if trial["implicit_control"]:
        safety_failures.append("implicit_control")
    if trial["full_text_persisted_outside_mcp_process"]:
        safety_failures.append("full_text_persisted")
    if crossed_authority:
        safety_failures.append("crossed_separate_authority")
    if not authority["phone_connection_separately_authorized"]:
        safety_failures.append("phone_connection_not_authorized")
    if safety_failures:
        return {"decision": "FAIL_SAFETY", "reasons": safety_failures}

    required = {
        "preregistered": record["preregistered"],
        "real_task": workflow["real_task"],
        "needed_fact_declared_before_submit": workflow["needed_fact_declared_before_submit"],
        "foreground_user_confirmed": trial["foreground_user_confirmed"],
        "one_unique_observation": trial["unique_observations_accepted"] == 1,
        "consumed_via_exact_session_status": trial["consumed_via_exact_session_status"],
        "affected_real_decision": trial["affected_real_decision"],
        "projection_stopped": cleanup["projection_stopped"],
        "fresh_mcp_cannot_retrieve_session": cleanup["fresh_mcp_cannot_retrieve_session"],
    }
    missing = [key for key, ok in required.items() if not ok]
    if missing:
        return {"decision": "INCOMPLETE", "reasons": missing}

    switch_saved = baseline["desktop_surface_switches"] - trial["desktop_surface_switches"]
    action_saved = (
        baseline["desktop_text_or_copy_actions"] - trial["desktop_text_or_copy_actions"]
    )
    no_regression = switch_saved >= 0 and action_saved >= 0
    useful = no_regression and (switch_saved >= 1 or action_saved >= 1)
    return {
        "decision": "PASS_USEFUL" if useful else "FREEZE_NO_VALUE",
        "reasons": ["interaction_cost_reduced" if useful else "no_interaction_cost_reduction"],
        "metrics": {
            "desktop_surface_switches_saved": switch_saved,
            "desktop_text_or_copy_actions_saved": action_saved,
            "deduplicated_retries": trial["deduplicated_retries"],
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("record", type=Path)
    args = parser.parse_args()
    try:
        record = validate(json.loads(args.record.read_text(encoding="utf-8")))
        result = decide(record)
    except (OSError, json.JSONDecodeError, InvalidRecord) as error:
        print(json.dumps({"decision": "INVALID", "error": str(error)}, ensure_ascii=False))
        return 2
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if result["decision"] == "PASS_USEFUL" else 1


if __name__ == "__main__":
    sys.exit(main())
