#!/usr/bin/env python3
"""Verify D83's sealed runtime-rule inputs without measuring or mutating the host."""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any, Mapping

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
CONTRACT = HERE / "fh_l8_d60_runtime_rule_precommit_d83_contract.json"
RESULT = HERE / "fh_l8_d60_runtime_rule_precommit_d83_result.json"


class D83Error(RuntimeError):
    pass


def load(path: Path) -> Mapping[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, Mapping):
        raise D83Error(f"object required: {path.name}")
    return value


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_contract(contract: Mapping[str, Any]) -> None:
    if contract.get("contract_id") != "FH-L8-D60-RUNTIME-RULE-PRECOMMIT-D83-V1":
        raise D83Error("contract identity drift")
    baseline = str(contract.get("baseline_commit", ""))
    if subprocess.run(["git", "-C", str(ROOT), "merge-base", "--is-ancestor", baseline, "HEAD"],
                      check=False, capture_output=True).returncode:
        raise D83Error("HEAD is not descended from baseline")
    pins = contract.get("source_pins")
    if not isinstance(pins, Mapping) or len(pins) != 9:
        raise D83Error("exact source pins required")
    for name, expected in pins.items():
        if digest(HERE / str(name)) != expected:
            raise D83Error(f"source pin mismatch: {name}")
    rule = contract["frozen_runtime_rule"]
    if rule["operation_populations"] != [213099, 47947275, 95894550, 95894550, 958945500]:
        raise D83Error("operation population drift")
    if (rule["confirmatory_samples_per_operation_class"], rule["operation_class_count"],
        rule["total_confirmatory_samples"]) != (459, 5, 2295):
        raise D83Error("confirmatory population drift")
    if rule["confirmatory_sample_timeout_seconds"] != 240:
        raise D83Error("sample timeout drift")
    if rule["automatic_retry_allowed"] or rule["deadline_extension_allowed"]:
        raise D83Error("timeout fail-closed policy opened")
    authority = contract["authority"]
    closed = ("runtime_lock_precommitted", "measurement_authorized",
              "numeric_runtime_seconds_proven", "full53_execution_authorized")
    if any(authority[name] for name in closed):
        raise D83Error("authority opened in precommit contract")


def evaluate(contract: Mapping[str, Any], receipt: Mapping[str, Any] | None = None,
             environment: Mapping[str, Any] | None = None) -> dict[str, Any]:
    admission = contract["fresh_admission"]
    receipt_ok = bool(receipt) and (
        receipt.get("contract_id") == admission["receipt_contract_id"]
        and receipt.get("fresh_after_boot") is True
        and receipt.get("target_cpu") == admission["target_cpu"]
        and receipt.get("service_cgroup_path") == admission["target_service_cgroup_path"]
        and all(receipt.get("predicates", {}).get(name) is True
                for name in admission["required_green_predicates"])
    )
    environment_ok = bool(environment) and (
        environment.get("captured_inside_receipt_service") is True
        and environment.get("identity_except_cgroup_matches_d81") is True
        and environment.get("cgroup_path") == admission["target_service_cgroup_path"]
    )
    inputs_complete = bool(receipt_ok and environment_ok)
    return {
        "status": "VERIFIED_D83_RUNTIME_RULE_FROZEN_FAIL_CLOSED",
        "source_pin_count": len(contract["source_pins"]),
        "rule_structure_frozen": True,
        "owner_numeric_policy_frozen": True,
        "fresh_isolation_receipt_admitted": bool(receipt_ok),
        "environment_recapture_admitted": bool(environment_ok),
        "premeasurement_inputs_complete": inputs_complete,
        "service_only_d79_observation_admitted_as_scope_proof": False,
        "runtime_lock_precommitted": False,
        "measurement_authorized": False,
        "timing_measurements_executed": 0,
        "scientific_kernel_calls_executed": 0,
        "numeric_runtime_seconds_proven": False,
        "full53_execution_authorized": False,
        "decision": ("READY_D83_INPUTS_FOR_SEPARATE_OWNER_MEASUREMENT_AUTHORIZATION_REVIEW"
                     if inputs_complete else
                     "BLOCKED_D83_FRESH_ISOLATION_RECEIPT_AND_ENVIRONMENT_RECAPTURE_REQUIRED"),
        "next_gate": ("SEPARATE_OWNER_CONFIRMATORY_MEASUREMENT_AUTHORIZATION"
                      if inputs_complete else
                      "D82R_BOOT_RESTART_FRESH_RECEIPT_THEN_D83_REVERIFY")
    }


def verify() -> dict[str, Any]:
    contract = load(CONTRACT)
    verify_contract(contract)
    return evaluate(contract)


if __name__ == "__main__":
    print(json.dumps(verify(), indent=2))
