#!/usr/bin/env python3
"""Validate the ordered FH-L8 D56 resource-closure plan."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping


HERE = Path(__file__).resolve().parent
CONTRACT = HERE / "fh_l8_resource_closure_plan_d56_contract.json"
RESULT = HERE / "fh_l8_resource_closure_plan_d56_result.json"


class D56Error(RuntimeError):
    pass


def load(path: Path) -> Mapping[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, Mapping):
        raise D56Error(f"{path.name}: object required")
    return value


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate(contract: Mapping[str, Any]) -> dict[str, Any]:
    if contract.get("contract_id") != "FH-L8-PRODUCTION-ADAPTER-RESOURCE-CLOSURE-PLAN-D56-V1":
        raise D56Error("contract id drift")
    pins = contract.get("source_pins")
    if not isinstance(pins, Mapping) or not pins:
        raise D56Error("source pins missing")
    for name, expected in pins.items():
        if digest(HERE / name) != expected:
            raise D56Error(f"source pin mismatch: {name}")

    d55_contract = load(HERE / "fh_l8_measurement_admissibility_d55_contract.json")
    d55_result = load(HERE / "fh_l8_measurement_admissibility_d55_result.json")
    if d55_result["next_gate"] != "D56_PRODUCTION_STREAMING_ADAPTER_AND_RESOURCE_BOUND_CLOSURE_PLAN":
        raise D56Error("D55 handoff drift")
    packages = contract.get("work_packages")
    if not isinstance(packages, list) or len(packages) != 6:
        raise D56Error("work-package count drift")
    gates = [package.get("gate") for package in packages]
    expected_gates = [
        "D57_PRODUCTION_STREAMING_ADAPTER_IMPLEMENTATION_CONTRACT",
        "D58_LIVE_ALLOCATION_CLASS_STATIC_BOUND",
        "D59_PRODUCTION_IO_PAGE_CACHE_BOUND",
        "D60_RUNTIME_BOUND_OR_PRECOMMITTED_MARGIN_RULE",
        "D61_INTEGRATED_RESOURCE_ENVELOPE_RECONCILIATION",
        "D62_EXTERNAL_RESERVATION_AND_FULL53_AUTHORIZATION_DECISION",
    ]
    if gates != expected_gates or len(set(gates)) != len(gates):
        raise D56Error("gate order or identity drift")
    requirements = [package.get("closes_requirement") for package in packages]
    if requirements != d55_contract["closure_requirements"]:
        raise D56Error("D55 closure-requirement mapping drift")
    seen: set[str] = set()
    for package in packages:
        dependencies = package.get("depends_on")
        if not isinstance(dependencies, list) or any(item not in seen for item in dependencies):
            raise D56Error(f"forward or unknown dependency: {package.get('gate')}")
        if not package.get("deliverables") or not package.get("acceptance"):
            raise D56Error(f"incomplete package: {package.get('gate')}")
        seen.add(package["gate"])

    parallel = contract.get("parallelism")
    if not isinstance(parallel, Mapping):
        raise D56Error("parallelism contract missing")
    if parallel.get("after_D57_may_run_in_parallel") != expected_gates[1:4]:
        raise D56Error("parallel gate set drift")
    if parallel.get("D61_requires_all_parallel_gates") is not True:
        raise D56Error("D61 join drift")
    if parallel.get("D62_requires_D61") is not True:
        raise D56Error("D62 dependency drift")
    if packages[4]["depends_on"] != expected_gates[1:4]:
        raise D56Error("D61 dependencies incomplete")
    if packages[5]["depends_on"] != [expected_gates[4]]:
        raise D56Error("D62 dependency incomplete")

    stops = contract.get("global_stop_conditions")
    if not isinstance(stops, list) or len(stops) != len(set(stops)) or not stops:
        raise D56Error("stop-condition set invalid")
    authority = contract.get("authority")
    false_fields = (
        "production_adapter_implemented",
        "numeric_peak_memory_proven",
        "numeric_runtime_seconds_proven",
        "external_resource_reservation_admitted",
        "full53_execution_authorized",
    )
    if not isinstance(authority, Mapping) or any(authority.get(key) is not False for key in false_fields):
        raise D56Error("authority unexpectedly open")
    zero_fields = (
        "scientific_kernel_calls_executed",
        "object_measurements_executed",
        "packed_q3_reads",
    )
    if any(authority.get(key) != 0 for key in zero_fields):
        raise D56Error("D56 must remain plan-only")

    return {
        "status": "VERIFIED_D56_ORDERED_PRODUCTION_ADAPTER_AND_RESOURCE_BOUND_CLOSURE_PLAN",
        "work_package_count": len(packages),
        "closure_requirement_count": len(requirements),
        "deliverable_count": sum(len(package["deliverables"]) for package in packages),
        "acceptance_check_count": sum(len(package["acceptance"]) for package in packages),
        "parallel_gate_count_after_d57": len(parallel["after_D57_may_run_in_parallel"]),
        "global_stop_condition_count": len(stops),
        **{key: authority[key] for key in false_fields},
        **{key: authority[key] for key in zero_fields},
        "next_gate": contract["next_gate"],
    }


def verify() -> dict[str, Any]:
    expected = validate(load(CONTRACT))
    if load(RESULT) != expected:
        raise D56Error("committed result drift")
    return expected


if __name__ == "__main__":
    print(json.dumps(verify(), indent=2, sort_keys=True))
