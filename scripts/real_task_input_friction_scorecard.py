#!/usr/bin/env python3
"""Evaluate a metadata-only real-task input-friction dogfood record."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any


SCHEMA = "agent_bridge.real_task_input_friction_scorecard.v0"
METRIC_KEYS = {
    "context_recovery_actions",
    "desktop_surface_switches",
    "desktop_text_or_copy_actions",
}
FAILURE_CLASSES = {
    "none",
    "authority_crossed",
    "unsafe_capture_or_retention",
    "evidence_missing",
    "input_not_consumed",
    "context_not_recovered",
    "decision_unchanged",
    "cleanup_incomplete",
    "no_interaction_cost_reduction",
    "provider_timeout",
    "provider_lifecycle",
}
DIAGNOSIS_STAGES = {
    "preregistration",
    "input",
    "consumption",
    "context",
    "decision",
    "cleanup",
}
REFERENCE_PATTERN = re.compile(r"([a-z][a-z0-9+.-]*):([A-Za-z0-9._~/#?=&%-]{1,127})")
IDENTIFIER_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}")
TOP_LEVEL_KEYS = {
    "schema",
    "trial_id",
    "preregistered",
    "task",
    "baseline",
    "trial",
    "safety",
    "diagnosis",
    "evidence",
}
TASK_KEYS = {"real_task", "task_reference", "needed_context_declared_before_input"}
TRIAL_KEYS = {
    *METRIC_KEYS,
    "foreground_user_confirmed",
    "unique_input_accepted",
    "consumed_via_exact_session_status",
    "context_recovered",
    "affected_real_decision",
    "upstream_failure_class",
}
SAFETY_KEYS = {
    "background_capture",
    "implicit_control",
    "full_text_persisted",
    "ungranted_phone_or_runtime_action",
    "projection_stopped",
    "fresh_process_cannot_retrieve_input",
}
DIAGNOSIS_KEYS = {
    "failure_class",
    "stage",
    "persisted",
    "persistence_reference",
    "evidence_digest_sha256",
    "retry_recommended",
}
EVIDENCE_KEYS = {
    "baseline_reference",
    "input_reference",
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


def _is_count(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def _require_bool(value: Any, label: str) -> None:
    if not isinstance(value, bool):
        raise InvalidRecord(f"{label} must be boolean")


def _require_identifier(value: Any, label: str) -> None:
    if not isinstance(value, str) or not IDENTIFIER_PATTERN.fullmatch(value):
        raise InvalidRecord(f"{label} must be a compact identifier")


def _require_reference(
    value: Any,
    label: str,
    *,
    schemes: set[str],
    allow_empty: bool = False,
) -> None:
    if allow_empty and value == "":
        return
    match = REFERENCE_PATTERN.fullmatch(value) if isinstance(value, str) else None
    if match is None or match.group(1) not in schemes:
        raise InvalidRecord(f"{label} must be an opaque metadata reference")


def validate(record: Any) -> dict[str, Any]:
    root = _exact_keys(record, TOP_LEVEL_KEYS, "record")
    if root["schema"] != SCHEMA:
        raise InvalidRecord(f"schema must be {SCHEMA}")
    _require_identifier(root["trial_id"], "trial_id")
    _require_bool(root["preregistered"], "preregistered")

    task = _exact_keys(root["task"], TASK_KEYS, "task")
    baseline = _exact_keys(root["baseline"], METRIC_KEYS, "baseline")
    trial = _exact_keys(root["trial"], TRIAL_KEYS, "trial")
    safety = _exact_keys(root["safety"], SAFETY_KEYS, "safety")
    diagnosis = _exact_keys(root["diagnosis"], DIAGNOSIS_KEYS, "diagnosis")
    evidence = _exact_keys(root["evidence"], EVIDENCE_KEYS, "evidence")

    for key in ("real_task", "needed_context_declared_before_input"):
        _require_bool(task[key], f"task.{key}")
    _require_reference(task["task_reference"], "task.task_reference", schemes={"task"})
    for label, metrics in (("baseline", baseline), ("trial", trial)):
        for key in METRIC_KEYS:
            if not _is_count(metrics[key]):
                raise InvalidRecord(f"{label}.{key} must be a non-negative integer")
    for key in TRIAL_KEYS - METRIC_KEYS - {"unique_input_accepted"}:
        if key == "upstream_failure_class":
            continue
        _require_bool(trial[key], f"trial.{key}")
    if not _is_count(trial["unique_input_accepted"]):
        raise InvalidRecord(
            "trial.unique_input_accepted must be a non-negative integer"
        )
    if trial["upstream_failure_class"] not in {
        "none",
        "provider_timeout",
        "provider_lifecycle",
    }:
        raise InvalidRecord("trial.upstream_failure_class is not recognized")
    for key, value in safety.items():
        _require_bool(value, f"safety.{key}")
    if diagnosis["failure_class"] not in FAILURE_CLASSES:
        raise InvalidRecord("diagnosis.failure_class is not recognized")
    if diagnosis["stage"] not in DIAGNOSIS_STAGES:
        raise InvalidRecord("diagnosis.stage is not recognized")
    for key in ("persisted", "retry_recommended"):
        _require_bool(diagnosis[key], f"diagnosis.{key}")
    _require_reference(
        diagnosis["persistence_reference"],
        "diagnosis.persistence_reference",
        schemes={"ledger"},
        allow_empty=True,
    )
    if not isinstance(diagnosis["evidence_digest_sha256"], str):
        raise InvalidRecord("diagnosis.evidence_digest_sha256 must be a string")
    for key, value in evidence.items():
        schemes = {"sha256"} if key == "input_reference" else {"receipt"}
        _require_reference(value, f"evidence.{key}", schemes=schemes)
    if not re.fullmatch(r"sha256:[0-9a-f]{64}", evidence["input_reference"]):
        raise InvalidRecord(
            "evidence.input_reference must contain only a SHA-256 digest"
        )
    return root


def _classify(record: dict[str, Any]) -> tuple[str, str]:
    task, trial, safety = record["task"], record["trial"], record["safety"]
    if safety["ungranted_phone_or_runtime_action"]:
        return "FAIL_SAFETY", "authority_crossed"
    if (
        safety["background_capture"]
        or safety["implicit_control"]
        or safety["full_text_persisted"]
    ):
        return "FAIL_SAFETY", "unsafe_capture_or_retention"
    if (
        not record["preregistered"]
        or not task["real_task"]
        or not task["needed_context_declared_before_input"]
    ):
        return "INCOMPLETE", "evidence_missing"
    if trial["upstream_failure_class"] != "none":
        return "INCOMPLETE", trial["upstream_failure_class"]
    if not trial["foreground_user_confirmed"]:
        return "INCOMPLETE", "evidence_missing"
    if (
        trial["unique_input_accepted"] != 1
        or not trial["consumed_via_exact_session_status"]
    ):
        return "INCOMPLETE", "input_not_consumed"
    if not trial["context_recovered"]:
        return "INCOMPLETE", "context_not_recovered"
    if not trial["affected_real_decision"]:
        return "INCOMPLETE", "decision_unchanged"
    if (
        not safety["projection_stopped"]
        or not safety["fresh_process_cannot_retrieve_input"]
    ):
        return "INCOMPLETE", "cleanup_incomplete"

    savings = {key: record["baseline"][key] - trial[key] for key in METRIC_KEYS}
    useful = all(value >= 0 for value in savings.values()) and any(
        value >= 1 for value in savings.values()
    )
    if useful:
        return "PASS_USEFUL", "none"
    return "FREEZE_NO_VALUE", "no_interaction_cost_reduction"


def _diagnosis_digest(record: dict[str, Any], failure_class: str) -> str:
    evidence = json.dumps(
        record["evidence"], ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    material = f"{record['trial_id']}\n{failure_class}\n{evidence}".encode()
    return hashlib.sha256(material).hexdigest()


def decide(record: dict[str, Any]) -> dict[str, Any]:
    decision, failure_class = _classify(record)
    diagnosis = record["diagnosis"]
    if diagnosis["failure_class"] != failure_class:
        raise InvalidRecord(
            "diagnosis.failure_class does not match computed failure class "
            f"{failure_class}"
        )
    if failure_class == "none":
        if (
            diagnosis["persisted"]
            or diagnosis["persistence_reference"]
            or diagnosis["evidence_digest_sha256"]
        ):
            raise InvalidRecord(
                "passing records must not claim a persisted failure diagnosis"
            )
        if diagnosis["retry_recommended"]:
            raise InvalidRecord("passing records cannot recommend a retry")
    else:
        if not diagnosis["persisted"] or not diagnosis["persistence_reference"].strip():
            raise InvalidRecord(
                "non-passing records require a persisted diagnosis reference"
            )
        expected_digest = _diagnosis_digest(record, failure_class)
        if not re.fullmatch(r"[0-9a-f]{64}", diagnosis["evidence_digest_sha256"]):
            raise InvalidRecord(
                "diagnosis.evidence_digest_sha256 must be lowercase SHA-256"
            )
        if diagnosis["evidence_digest_sha256"] != expected_digest:
            raise InvalidRecord(
                "diagnosis evidence digest does not bind trial, class, and evidence"
            )
        if (
            failure_class in {"provider_timeout", "provider_lifecycle"}
            and diagnosis["retry_recommended"]
        ):
            raise InvalidRecord("provider failures cannot recommend an automatic retry")

    savings = {
        f"{key}_saved": record["baseline"][key] - record["trial"][key]
        for key in METRIC_KEYS
    }
    return {
        "schema": "agent_bridge.real_task_input_friction_result.v0",
        "trial_id": record["trial_id"],
        "decision": decision,
        "failure_class": failure_class,
        "metrics": savings,
        "diagnosis": {
            "stage": diagnosis["stage"],
            "persisted": diagnosis["persisted"],
            "persistence_reference": diagnosis["persistence_reference"],
            "evidence_digest_sha256": diagnosis["evidence_digest_sha256"],
            "retry_recommended": diagnosis["retry_recommended"],
        },
        "retains_input_text": False,
        "read_only_evaluation": True,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("record", type=Path)
    args = parser.parse_args()
    try:
        record = validate(json.loads(args.record.read_text(encoding="utf-8")))
        result = decide(record)
    except (OSError, json.JSONDecodeError, InvalidRecord) as error:
        print(
            json.dumps({"decision": "INVALID", "error": str(error)}, ensure_ascii=False)
        )
        return 2
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if result["decision"] == "PASS_USEFUL" else 1


if __name__ == "__main__":
    sys.exit(main())
