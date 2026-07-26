#!/usr/bin/env python3
"""Verify D54 bounded measurement authorization without consuming it."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping


HERE = Path(__file__).resolve().parent
AUTHORIZATION = HERE / "fh_l8_object_cost_measurement_d54_authorization.json"
RUNNER = HERE / "fh_l8_object_cost_measurement_d54_runner.py"
D53_CONTRACT = HERE / "fh_l8_object_cost_measurement_d53_contract.json"
D53_RESULT = HERE / "fh_l8_object_cost_measurement_d53_result.json"


class D54AuthorizationError(ValueError):
    pass


def load(path: Path) -> Mapping[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, Mapping):
        raise D54AuthorizationError(f"{path.name}: JSON object required")
    return value


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check(path: Path = AUTHORIZATION) -> dict[str, Any]:
    authorization = load(path)
    if authorization.get("authorization_id") != (
        "FH-L8-D54-OBJECT-COST-MEASUREMENT-AUTH-V1"
    ):
        raise D54AuthorizationError("authorization id drift")
    d53 = load(D53_CONTRACT)
    if authorization.get("parent_protocol_id") != d53["contract_id"]:
        raise D54AuthorizationError("parent protocol drift")
    pins = {
        "runner_sha256": digest(RUNNER),
        "d53_contract_sha256": digest(D53_CONTRACT),
        "d53_result_sha256": digest(D53_RESULT),
    }
    for field, expected in pins.items():
        if authorization.get(field) != expected:
            raise D54AuthorizationError(f"{field} drift")
    if authorization.get("measurement_execution_authorized") is not True:
        raise D54AuthorizationError("bounded measurement authority is not open")

    warmups = d53["isolation"]["warmup_runs_per_size"]
    measured = d53["isolation"]["measured_runs_per_size"]
    synthetic_sizes = len(d53["fixture_tiers"][0]["sizes"])
    fixed_sizes = len(d53["fixture_tiers"][1]["sample_prefix_sizes"])
    plan = authorization["sample_plan"]
    expected_plan = {
        "total_fresh_processes": (synthetic_sizes + fixed_sizes) * (warmups + measured),
        "synthetic_processes": synthetic_sizes * (warmups + measured),
        "fixed64_processes": fixed_sizes * (warmups + measured),
        "warmup_processes": (synthetic_sizes + fixed_sizes) * warmups,
        "measured_processes": (synthetic_sizes + fixed_sizes) * measured,
        "maximum_scientific_kernel_calls_per_process": 67,
        "maximum_scientific_kernel_calls_total": (4 + 11 + 35 + 67)
        * (warmups + measured),
        "maximum_object_measurements_total": (synthetic_sizes + fixed_sizes)
        * (warmups + measured),
    }
    if plan != expected_plan:
        raise D54AuthorizationError("sample-plan arithmetic drift")

    isolation = authorization["isolation"]
    d53_isolation = d53["isolation"]
    if isolation["cpu_affinity"] != d53_isolation["cpu_affinity"]:
        raise D54AuthorizationError("CPU affinity drift")
    if isolation["memory_max_bytes"] != d53_isolation["memory_max_bytes"]:
        raise D54AuthorizationError("memory max drift")
    if isolation["memory_high_bytes"] != d53_isolation["memory_high_bytes"]:
        raise D54AuthorizationError("memory high drift")
    if isolation["swap_max_bytes"] != 0:
        raise D54AuthorizationError("swap authority must remain zero")
    if isolation["network_allowed"] is not False:
        raise D54AuthorizationError("network must remain closed")
    if isolation["writes_outside_scratch_allowed"] is not False:
        raise D54AuthorizationError("writes outside scratch must remain closed")
    if isolation["scratch_must_be_absent_before_launch"] is not True:
        raise D54AuthorizationError("fresh scratch precondition drift")

    authority = authorization["authority"]
    if authority["packed_q3_reads_authorized"] != 0:
        raise D54AuthorizationError("packed-q3 authority must remain zero")
    for field in (
        "full53_execution_authorized",
        "numeric_peak_memory_proven",
        "numeric_runtime_seconds_proven",
        "external_resource_reservation_admitted",
    ):
        if authority.get(field) is not False:
            raise D54AuthorizationError(f"authority unexpectedly open: {field}")
    if authority.get("full53_extrapolation_forbidden") is not True:
        raise D54AuthorizationError("full53 extrapolation boundary drift")

    state = authorization["execution_state"]
    expected_state = {
        "scratch_created": False,
        "samples_started": 0,
        "samples_completed": 0,
        "object_measurements_executed": 0,
        "scientific_kernel_calls_executed": 0,
        "packed_q3_reads": 0,
    }
    if state != expected_state:
        raise D54AuthorizationError("authorization must be result-blind and unused")

    return {
        "status": "AUTHORIZED_D54_BOUNDED_OBJECT_COST_MEASUREMENT_NOT_EXECUTED",
        **expected_plan,
        "measurement_execution_authorized": True,
        "scratch_created": False,
        "samples_started": 0,
        "samples_completed": 0,
        "object_measurements_executed": 0,
        "scientific_kernel_calls_executed": 0,
        "packed_q3_reads": 0,
        "full53_execution_authorized": False,
        "numeric_peak_memory_proven": False,
        "numeric_runtime_seconds_proven": False,
        "full53_extrapolation_forbidden": True,
        "next_gate": authorization["next_gate"],
    }


def main() -> None:
    print(json.dumps(check(), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
