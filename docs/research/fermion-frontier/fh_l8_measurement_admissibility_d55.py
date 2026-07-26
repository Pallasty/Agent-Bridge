#!/usr/bin/env python3
"""Validate the source-pinned D55 measurement-admissibility decision."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping


HERE = Path(__file__).resolve().parent
CONTRACT = HERE / "fh_l8_measurement_admissibility_d55_contract.json"
RESULT = HERE / "fh_l8_measurement_admissibility_d55_result.json"


class D55Error(RuntimeError):
    pass


def load(path: Path) -> Mapping[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, Mapping):
        raise D55Error(f"{path.name}: object required")
    return value


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def fixed64_64_d54r(result: Mapping[str, Any]) -> Mapping[str, Any]:
    rows = result.get("fixed64_summaries")
    if not isinstance(rows, list) or [row.get("size") for row in rows] != [1, 8, 32, 64]:
        raise D55Error("D54R fixed64 coverage drift")
    return rows[-1]


def fixed64_64_d54r2(result: Mapping[str, Any]) -> Mapping[str, Any]:
    rows = [
        row
        for row in result.get("groups", [])
        if row.get("tier") == "source_bound_fixed64_micro"
    ]
    if [row.get("size") for row in rows] != [1, 8, 32, 64]:
        raise D55Error("D54R2 fixed64 coverage drift")
    return rows[-1]


def validate(contract: Mapping[str, Any]) -> dict[str, Any]:
    if contract.get("contract_id") != "FH-L8-D54-MEASUREMENT-ADMISSIBILITY-D55-V1":
        raise D55Error("contract id drift")
    pins = contract.get("source_pins")
    if not isinstance(pins, Mapping) or not pins:
        raise D55Error("source pins missing")
    for name, expected in pins.items():
        if digest(HERE / name) != expected:
            raise D55Error(f"source pin mismatch: {name}")

    d51 = load(HERE / "fh_l8_full53_streaming_lifetime_d51_result.json")
    d52 = load(HERE / "fh_l8_full53_adapter_static_cost_d52_contract.json")
    d53 = load(HERE / "fh_l8_object_cost_measurement_d53_contract.json")
    d54r = load(HERE / "fh_l8_object_cost_measurement_d54r_result.json")
    d54r2 = load(HERE / "fh_l8_object_cost_measurement_d54r2_result.json")
    decisions = contract.get("target_decisions")
    if not isinstance(decisions, Mapping) or set(decisions) != set(d53["measurement_targets"]):
        raise D55Error("target-decision coverage drift")
    levels = set(contract["admissibility_levels"])
    counts = {level: 0 for level in levels}
    for target, decision in decisions.items():
        if not isinstance(decision, Mapping) or decision.get("level") not in levels:
            raise D55Error(f"invalid decision level: {target}")
        if not decision.get("basis"):
            raise D55Error(f"decision basis missing: {target}")
        counts[decision["level"]] += 1
    if set(d52["unresolved_allocation_costs"]) - set(d53["upstream_term_mapping"]):
        raise D55Error("D52 unresolved term is unmapped")
    if (
        d54r["sample_receipt_count"] != 70
        or d54r["measured_sample_count"] != 50
        or d54r["claims"]["numeric_peak_memory_proven"] is not False
        or d54r["claims"]["numeric_runtime_seconds_proven"] is not False
        or d54r["claims"]["full53_execution_authorized"] is not False
        or d54r["claims"]["full53_extrapolation_forbidden"] is not True
    ):
        raise D55Error("D54R completeness or claim boundary drift")
    if (
        d54r2["raw_sample_count"] != 70
        or d54r2["measured_sample_count"] != 50
        or d54r2["numeric_worst_case_proven"] is not False
        or d54r2["resource_authorization_conferred"] is not False
    ):
        raise D55Error("D54R2 completeness or claim boundary drift")
    if d54r["packed_q3_reads"] != 0 or d54r2["packed_q3_reads"] != 0:
        raise D55Error("packed-q3 boundary drift")

    authority = contract.get("authority")
    closed = (
        "numeric_peak_memory_proven",
        "numeric_runtime_seconds_proven",
        "external_resource_reservation_admitted",
        "full53_execution_authorized",
    )
    if not isinstance(authority, Mapping) or any(authority.get(key) is not False for key in closed):
        raise D55Error("resource authority unexpectedly open")
    if any(
        authority.get(key) != 0
        for key in (
            "scientific_kernel_calls_executed",
            "object_measurements_executed",
            "packed_q3_reads",
        )
    ):
        raise D55Error("D55 must remain review-only")
    if d51["d23_shortfall_bytes"] != 359759114:
        raise D55Error("D51 scratch shortfall drift")

    r1 = fixed64_64_d54r(d54r)
    r2 = fixed64_64_d54r2(d54r2)
    return {
        "status": "VERIFIED_D55_MEASUREMENT_ADMISSIBILITY_REVIEW_RESOURCE_BOUNDS_INCOMPLETE",
        "measurement_target_count": len(decisions),
        "observational_only_count": counts["OBSERVATIONAL_ONLY"],
        "not_separately_identified_count": counts["NOT_SEPARATELY_IDENTIFIED"],
        "not_measured_count": counts["NOT_MEASURED"],
        "replay_count": 2,
        "d54r_sample_receipt_count_total": d54r["sample_receipt_count"]
        + d54r2["raw_sample_count"],
        "d54r_measured_sample_count_total": d54r["measured_sample_count"]
        + d54r2["measured_sample_count"],
        "d54r_scientific_kernel_calls_total": d54r["scientific_kernel_calls_total"]
        + d54r2["scientific_kernel_calls_executed"],
        "fixed64_size64_cgroup_peak_max_bytes_observed_across_replays": max(
            r1["cgroup_memory_peak_bytes"]["max"],
            r2["metrics"]["cgroup_memory_peak_bytes"]["max"],
        ),
        "fixed64_size64_wall_elapsed_max_ns_observed_across_replays": max(
            r1["wall_elapsed_ns"]["max"], r2["metrics"]["wall_elapsed_ns"]["max"]
        ),
        "d23_scratch_shortfall_bytes": d51["d23_shortfall_bytes"],
        "closure_requirement_count": len(contract["closure_requirements"]),
        "scientific_kernel_calls_executed_by_d55": 0,
        "object_measurements_executed_by_d55": 0,
        "packed_q3_reads_by_d55": 0,
        "numeric_peak_memory_proven": False,
        "numeric_runtime_seconds_proven": False,
        "external_resource_reservation_admitted": False,
        "full53_execution_authorized": False,
        "decision": contract["decision"],
        "next_gate": contract["next_gate"],
    }


def verify() -> dict[str, Any]:
    expected = validate(load(CONTRACT))
    if load(RESULT) != expected:
        raise D55Error("committed result drift")
    return expected


if __name__ == "__main__":
    print(json.dumps(verify(), indent=2, sort_keys=True))
