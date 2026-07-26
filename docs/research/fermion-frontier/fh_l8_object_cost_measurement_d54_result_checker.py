#!/usr/bin/env python3
"""Fail-closed checker for the committed FH-L8 D54 bounded local result."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
RESULT = HERE / "fh_l8_object_cost_measurement_d54_result.json"
FULL64 = "38aaeffb8f178e918e4f326888493166c21afc7fb1379e91ab965c345b4adc12"


class ResultError(RuntimeError):
    pass


def check(value: dict[str, Any]) -> dict[str, Any]:
    if value.get("status") != "D54_BOUNDED_LOCAL_MEASUREMENT_COMPLETE":
        raise ResultError("result status drift")
    if (value.get("raw_sample_count"), value.get("warmup_sample_count"),
            value.get("measured_sample_count")) != (70, 20, 50):
        raise ResultError("sample count drift")
    if value.get("scientific_kernel_calls_executed") != 791:
        raise ResultError("scientific call count drift")
    closed = (
        value.get("packed_q3_reads") == 0
        and value.get("full53_executed") is False
        and value.get("full53_extrapolation_performed") is False
        and value.get("numeric_worst_case_proven") is False
        and value.get("resource_authorization_conferred") is False
        and value.get("scope") == "bounded_local_empirical_observation_only"
    )
    if not closed:
        raise ResultError("authority boundary drift")
    expected = [
        *[("synthetic_object_calibration", size) for size in (0, 1, 8, 32, 64, 225)],
        *[("source_bound_fixed64_micro", size) for size in (1, 8, 32, 64)],
    ]
    groups = value.get("groups")
    if not isinstance(groups, list) or [
        (row.get("tier"), row.get("size")) for row in groups
    ] != expected:
        raise ResultError("group identity drift")
    for row in groups:
        if row.get("measured_samples") != 5:
            raise ResultError("measured repetition drift")
        metrics = row.get("metrics")
        if not isinstance(metrics, dict) or set(metrics) != {
            "tracemalloc_current_bytes", "tracemalloc_peak_bytes",
            "process_ru_maxrss_kib", "cgroup_memory_current_bytes",
            "cgroup_memory_peak_bytes", "wall_elapsed_ns", "process_cpu_ns",
        }:
            raise ResultError("metric set drift")
        for triple in metrics.values():
            if (
                not isinstance(triple, dict)
                or set(triple) != {"min", "median", "max"}
                or not all(isinstance(triple[key], int) and not isinstance(triple[key], bool)
                           for key in triple)
                or not triple["min"] <= triple["median"] <= triple["max"]
            ):
                raise ResultError("metric summary drift")
        if metrics["cgroup_memory_peak_bytes"]["max"] > 536_870_912:
            raise ResultError("memory cap exceeded")
    if groups[-1].get("structural_output_sha256") != FULL64:
        raise ResultError("fixed64 structural digest drift")
    return {
        "status": "VERIFIED_D54_BOUNDED_LOCAL_MEASUREMENT",
        "raw_sample_count": 70,
        "maximum_observed_cgroup_peak_bytes": max(
            row["metrics"]["cgroup_memory_peak_bytes"]["max"] for row in groups
        ),
        "maximum_observed_wall_elapsed_ns": max(
            row["metrics"]["wall_elapsed_ns"]["max"] for row in groups
        ),
        "full53_authority_open": False,
    }


def main() -> None:
    print(json.dumps(check(json.loads(RESULT.read_text(encoding="utf-8"))), sort_keys=True))


if __name__ == "__main__":
    main()
