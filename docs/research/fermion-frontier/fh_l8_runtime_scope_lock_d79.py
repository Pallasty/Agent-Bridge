#!/usr/bin/env python3
"""Verify D79 runtime scope-lock precheck result."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping


HERE = Path(__file__).resolve().parent
CONTRACT = HERE / "fh_l8_runtime_scope_lock_d79_contract.json"
RESULT = HERE / "fh_l8_runtime_scope_lock_d79_result.json"


class D79Error(RuntimeError):
    pass


def load(path: Path) -> Mapping[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, Mapping):
        raise D79Error("object required")
    return value


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate_contract(contract: Mapping[str, Any]) -> dict[str, Any]:
    if contract.get("contract_id") != "FH-L8-RUNTIME-SCOPE-LOCK-D79-V1":
        raise D79Error("id drift")
    if contract.get("schema_version") != 1:
        raise D79Error("schema drift")

    for name, expected in contract.get("source_pins", {}).items():
        path = HERE / name
        if not path.exists():
            raise D79Error(f"pinned path missing: {name}")
        if digest(path) != expected:
            raise D79Error(f"source pin drift: {name}")

    probe = contract.get("probe_definition")
    if not isinstance(probe, Mapping):
        raise D79Error("probe definition drift")
    for mode in ("scope", "service"):
        cfg = probe.get(mode)
        if (
            not isinstance(cfg, Mapping)
            or not cfg.get("command")
            or not cfg.get("unit_prefix")
            or cfg.get("requested_memory_max") != "1073741824"
            or cfg.get("requested_memory_high") != "805306368"
            or cfg.get("requested_memory_swap_max") != "0"
        ):
            raise D79Error(f"probe drift: {mode}")

    if contract.get("decision") != "NO_GO_D79_RUNTIME_SCOPE_LOCK_INCOMPLETE":
        raise D79Error("decision drift")
    if contract.get("next_gate") != "D60_RUNTIME_BOUND_OR_PRECOMMITTED_MARGIN_RULE":
        raise D79Error("next gate drift")

    authority = contract.get("authority", {})
    if not isinstance(authority, Mapping):
        raise D79Error("authority missing")
    required_false = (
        "scope_probe_executed",
        "service_probe_executed",
        "runtime_lock_precommitted",
        "d59_request_issued",
        "external_request_sent",
        "d60_environment_fixed",
        "full53_execution_authorized",
    )
    if any(authority.get(name) is not False for name in required_false):
        raise D79Error("contract authority not fail-closed")

    return {
        "contract_id": contract["contract_id"],
        "decision": contract["decision"],
        "next_gate": contract["next_gate"],
    }


def validate_result(result: Mapping[str, Any]) -> dict[str, Any]:
    if result.get("status") != "VERIFIED_D79_RUNTIME_SCOPE_LOCK_INCOMPLETE":
        raise D79Error("result status drift")
    if result.get("decision") != "NO_GO_D79_RUNTIME_SCOPE_LOCK_INCOMPLETE":
        raise D79Error("result decision drift")
    if result.get("next_gate") != "D60_RUNTIME_BOUND_OR_PRECOMMITTED_MARGIN_RULE":
        raise D79Error("result next gate drift")

    probe = result.get("probe_execution")
    if not isinstance(probe, Mapping):
        raise D79Error("probe execution missing")

    scope = probe.get("scope")
    service = probe.get("service")
    if not isinstance(scope, Mapping) or not isinstance(service, Mapping):
        raise D79Error("probe mode missing")
    if scope.get("scope_memory_controller_present") is not False:
        raise D79Error("unexpected scope controller capability")
    if scope.get("runtime_lock_candidate") != "NOT_ADMISSIBLE":
        raise D79Error("scope mode should be not admissible")
    if service.get("observed_memory_max") != "1073741824":
        raise D79Error("service memory.max drift")
    if service.get("observed_memory_high") != "805306368":
        raise D79Error("service memory.high drift")
    if service.get("observed_memory_swap_max") != "0":
        raise D79Error("service memory.swap.max drift")
    if service.get("runtime_lock_candidate") != "MEMORY_LIMIT_VISIBLE_SERVICE_ONLY":
        raise D79Error("service mode drift")

    authority = result.get("authority")
    if not isinstance(authority, Mapping):
        raise D79Error("authority missing")
    required_true = ("scope_probe_executed", "service_probe_executed", "service_memory_limits_verified")
    if any(authority.get(name) is not True for name in required_true):
        raise D79Error("authority fail-open")
    required_false = (
        "scope_memory_limits_verified",
        "runtime_lock_precommitted",
        "d59_request_issued",
        "external_request_sent",
        "d60_environment_fixed",
        "full53_execution_authorized",
    )
    if any(authority.get(name) is not False for name in required_false):
        raise D79Error("authority not closed")

    return {
        "status": result["status"],
        "scope_mode_admissible": scope.get("scope_memory_controller_present"),
        "service_memory_max": service["observed_memory_max"],
        "scope_probe_exit_code": scope["launch_exit_code"],
        "service_probe_exit_code": service["launch_exit_code"],
        "next_gate": result["next_gate"],
        "authority": authority,
    }


def verify() -> dict[str, Any]:
    contract_summary = validate_contract(load(CONTRACT))
    result_summary = validate_result(load(RESULT))
    return {
        "verification": "D79_RUNTIME_SCOPE_LOCK_PRECHECK",
        "status": result_summary["status"],
        "contract_id": contract_summary["contract_id"],
        "contract_decision": contract_summary["decision"],
        "result_decision": result_summary["status"],
        "scope_mode_admissible": result_summary["scope_mode_admissible"],
        "service_memory_max": result_summary["service_memory_max"],
        "scope_probe_exit_code": result_summary["scope_probe_exit_code"],
        "service_probe_exit_code": result_summary["service_probe_exit_code"],
        "next_gate": contract_summary["next_gate"],
        "authority": result_summary["authority"],
    }


if __name__ == "__main__":
    print(json.dumps(verify(), indent=2, sort_keys=True))
