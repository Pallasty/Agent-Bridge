#!/usr/bin/env python3
"""Independently aggregate a complete D54 receipt directory."""

from __future__ import annotations

import json
import statistics
from collections import defaultdict
from pathlib import Path
from typing import Any, Mapping

from fh_l8_object_cost_measurement_d54_launcher import (
    AUTHORIZATION,
    LauncherError,
    load,
    plan,
    validate_receipt,
)


def aggregate(scratch: Path) -> dict[str, Any]:
    auth = load(AUTHORIZATION)
    samples = plan()
    receipts = []
    for index, requested in enumerate(samples):
        path = scratch / "samples" / f"{index:03d}.json"
        if not path.is_file():
            raise LauncherError(f"missing sample receipt: {index:03d}")
        receipt = load(path)
        validate_receipt(receipt, requested, auth)
        receipts.append(receipt)
    groups: dict[tuple[str, int], list[Mapping[str, Any]]] = defaultdict(list)
    for receipt in receipts:
        runner = receipt["runner"]
        if runner["sample_kind"] == "measured":
            groups[(runner["tier"], runner["size"])].append(receipt)
    summaries = []
    for (tier, size), rows in sorted(groups.items()):
        structural = {row["runner"]["structural_output_sha256"] for row in rows}
        if len(structural) != 1:
            raise LauncherError(f"structural digest mismatch: {tier}/{size}")
        peaks = [row["cgroup"]["memory_peak_bytes"] for row in rows]
        elapsed = [row["runner"]["wall_elapsed_ns"] for row in rows]
        summaries.append(
            {
                "tier": tier,
                "size": size,
                "measured_samples": len(rows),
                "structural_output_sha256": next(iter(structural)),
                "cgroup_memory_peak_bytes": {
                    "min": min(peaks),
                    "median": int(statistics.median(peaks)),
                    "max": max(peaks),
                },
                "wall_elapsed_ns": {
                    "min": min(elapsed),
                    "median": int(statistics.median(elapsed)),
                    "max": max(elapsed),
                },
            }
        )
    return {
        "status": "COMPLETED_D54_FIXED64_INSTRUMENTED_OBJECT_COST_MEASUREMENTS",
        "sample_count": len(receipts),
        "measured_sample_count": sum(
            row["runner"]["sample_kind"] == "measured" for row in receipts
        ),
        "scientific_kernel_calls_total": sum(
            row["runner"].get("scientific_kernel_calls", 0) for row in receipts
        ),
        "packed_q3_reads": 0,
        "full53_extrapolation_forbidden": True,
        "numeric_peak_memory_proven": False,
        "numeric_runtime_seconds_proven": False,
        "full53_execution_authorized": False,
        "summaries": summaries,
        "next_gate": "D55_D54_MEASUREMENT_REVIEW_AND_BOUND_ADMISSIBILITY_DECISION",
    }


if __name__ == "__main__":
    auth = load(AUTHORIZATION)
    print(json.dumps(aggregate(Path(auth["isolation"]["scratch_root"])), indent=2, sort_keys=True))
