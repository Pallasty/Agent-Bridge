#!/usr/bin/env python3
"""Source-pinned, non-executing D55 measurement admissibility review."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
CONTRACT = HERE / "fh_l8_measurement_admissibility_d55_contract.json"
RESULT = HERE / "fh_l8_measurement_admissibility_d55_result.json"
LEVELS = {"OBSERVATIONAL_ONLY", "NOT_SEPARATELY_IDENTIFIED", "NOT_MEASURED"}
FULL64 = "38aaeffb8f178e918e4f326888493166c21afc7fb1379e91ab965c345b4adc12"


class D55Error(RuntimeError):
    pass


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise D55Error(f"{path.name}: object required")
    return value


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def fixed64(result: dict[str, Any], size: int) -> dict[str, Any]:
    rows = result.get("fixed64_summaries", result.get("groups"))
    matches = [
        row for row in rows
        if row.get("tier") == "source_bound_fixed64_micro" and row.get("size") == size
    ]
    if len(matches) != 1:
        raise D55Error(f"fixed64/{size} summary missing")
    return matches[0]


def peak(row: dict[str, Any]) -> int:
    metrics = row.get("metrics")
    values = (
        metrics["cgroup_memory_peak_bytes"]
        if isinstance(metrics, dict)
        else row["cgroup_memory_peak_bytes"]
    )
    return values["max"]


def wall(row: dict[str, Any]) -> int:
    metrics = row.get("metrics")
    values = metrics["wall_elapsed_ns"] if isinstance(metrics, dict) else row["wall_elapsed_ns"]
    return values["max"]


def review(contract_path: Path = CONTRACT) -> dict[str, Any]:
    contract = load(contract_path)
    if contract.get("contract_id") != "FH-L8-D54-MEASUREMENT-ADMISSIBILITY-D55-V1":
        raise D55Error("contract id drift")
    pins = contract.get("source_pins")
    if not isinstance(pins, dict) or len(pins) != 11:
        raise D55Error("source pin set drift")
    for name, expected in pins.items():
        path = HERE / name
        if not path.is_file() or digest(path) != expected:
            raise D55Error(f"source pin mismatch: {name}")

    d51 = load(HERE / "fh_l8_full53_streaming_lifetime_d51_result.json")
    d53 = load(HERE / "fh_l8_object_cost_measurement_d53_contract.json")
    first = load(HERE / "fh_l8_object_cost_measurement_d54r_result.json")
    second = load(HERE / "fh_l8_object_cost_measurement_d54r2_result.json")
    decisions = contract.get("target_decisions")
    if not isinstance(decisions, dict) or set(decisions) != set(d53["measurement_targets"]):
        raise D55Error("measurement-target decision set drift")
    counts = {level: 0 for level in LEVELS}
    for decision in decisions.values():
        if set(decision) != {"level", "basis"} or decision["level"] not in LEVELS:
            raise D55Error("malformed target decision")
        counts[decision["level"]] += 1
    if counts != {
        "OBSERVATIONAL_ONLY": 6,
        "NOT_SEPARATELY_IDENTIFIED": 3,
        "NOT_MEASURED": 1,
    }:
        raise D55Error("admissibility count drift")

    if (
        first.get("sample_receipt_count") != 70
        or first.get("measured_sample_count") != 50
        or first.get("scientific_kernel_calls_total") != 791
        or second.get("raw_sample_count") != 70
        or second.get("measured_sample_count") != 50
        or second.get("scientific_kernel_calls_executed") != 791
    ):
        raise D55Error("replication count drift")
    first64, second64 = fixed64(first, 64), fixed64(second, 64)
    if {
        first64.get("structural_output_sha256"),
        second64.get("structural_output_sha256"),
    } != {FULL64}:
        raise D55Error("cross-replication structural digest drift")
    p1, p2, w1, w2 = peak(first64), peak(second64), wall(first64), wall(second64)
    assessment = contract.get("cross_replication_assessment")
    expected_assessment = {
        "fixed64_structural_digest_exact_across_replays": True,
        "sample_plan_shape_exact_across_replays": True,
        "scientific_kernel_call_count_exact_across_replays": True,
        "network_isolation_mechanism_identical": False,
        "cgroup_peak_max_difference_bytes": p2 - p1,
        "cgroup_peak_max_increase_ppm_relative_to_d54r": (p2 - p1) * 1_000_000 // p1,
        "wall_elapsed_max_difference_ns": w2 - w1,
        "wall_elapsed_max_increase_ppm_relative_to_d54r": (w2 - w1) * 1_000_000 // w1,
        "observed_spread_is_not_a_margin_rule": True,
        "observed_maximum_is_not_an_upper_bound": True,
    }
    if assessment != expected_assessment:
        raise D55Error("cross-replication assessment drift")
    authority = contract.get("authority")
    if not isinstance(authority, dict) or any(authority[key] for key in authority):
        raise D55Error("D55 authority must remain closed/zero")
    if len(contract.get("closure_requirements", [])) != 6:
        raise D55Error("closure requirement drift")
    if contract.get("next_gate") != "D56_PRODUCTION_STREAMING_ADAPTER_AND_RESOURCE_BOUND_CLOSURE_PLAN":
        raise D55Error("next gate drift")

    return {
        "closure_requirement_count": 6,
        "d23_scratch_shortfall_bytes": d51["d23_shortfall_bytes"],
        "d54r_measured_sample_count_total": 100,
        "d54r_sample_receipt_count_total": 140,
        "d54r_scientific_kernel_calls_total": 1582,
        "decision": contract["decision"],
        "external_resource_reservation_admitted": False,
        "fixed64_size64_cgroup_peak_max_bytes_observed_across_replays": max(p1, p2),
        "fixed64_size64_wall_elapsed_max_ns_observed_across_replays": max(w1, w2),
        "full53_execution_authorized": False,
        "measurement_target_count": 10,
        "not_measured_count": counts["NOT_MEASURED"],
        "not_separately_identified_count": counts["NOT_SEPARATELY_IDENTIFIED"],
        "numeric_peak_memory_proven": False,
        "numeric_runtime_seconds_proven": False,
        "object_measurements_executed_by_d55": 0,
        "observational_only_count": counts["OBSERVATIONAL_ONLY"],
        "packed_q3_reads_by_d55": 0,
        "replay_count": 2,
        "scientific_kernel_calls_executed_by_d55": 0,
        "status": "VERIFIED_D55_MEASUREMENT_ADMISSIBILITY_REVIEW_RESOURCE_BOUNDS_INCOMPLETE",
        "next_gate": contract["next_gate"],
    }


def main() -> None:
    print(json.dumps(review(), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
