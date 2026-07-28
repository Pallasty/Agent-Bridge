#!/usr/bin/env python3
"""Verify the committed D54R result against the complete external receipt set."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

from fh_l8_object_cost_measurement_d54_aggregate import aggregate
from fh_l8_object_cost_measurement_d54_launcher import AUTHORIZATION, load


HERE = Path(__file__).resolve().parent
RESULT = HERE / "fh_l8_object_cost_measurement_d54r_result.json"


class ResultError(RuntimeError):
    pass


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def receipt_set_identity(scratch: Path, count: int) -> str:
    digests = [digest(scratch / "samples" / f"{index:03d}.json") for index in range(count)]
    joined = "\n".join(digests).encode("ascii")
    return hashlib.sha256(joined).hexdigest()


def observed_result() -> dict[str, Any]:
    auth = load(AUTHORIZATION)
    scratch = Path(auth["isolation"]["scratch_root"])
    summary = aggregate(scratch)
    count = int(summary["sample_count"])
    receipt_set_sha256 = receipt_set_identity(scratch, count)
    fixed64 = [
        row
        for row in summary["summaries"]
        if row["tier"] == "source_bound_fixed64_micro"
    ]
    return {
        "schema_version": 1,
        "status": summary["status"],
        "authorization_id": auth["authorization_id"],
        "authorization_sha256": digest(AUTHORIZATION),
        "scratch_manifest_sha256": digest(scratch / "manifest.json"),
        "sample_receipt_count": count,
        "sample_receipt_set_sha256": receipt_set_sha256,
        "measured_sample_count": summary["measured_sample_count"],
        "scientific_kernel_calls_total": summary["scientific_kernel_calls_total"],
        "packed_q3_reads": summary["packed_q3_reads"],
        "fixed64_summaries": fixed64,
        "claims": {
            "full53_extrapolation_forbidden": summary["full53_extrapolation_forbidden"],
            "numeric_peak_memory_proven": summary["numeric_peak_memory_proven"],
            "numeric_runtime_seconds_proven": summary["numeric_runtime_seconds_proven"],
            "full53_execution_authorized": summary["full53_execution_authorized"],
        },
        "next_gate": summary["next_gate"],
    }


def verify(committed: Mapping[str, Any]) -> dict[str, Any]:
    observed = observed_result()
    if committed != observed:
        raise ResultError("committed D54R result differs from the complete receipt set")
    return observed


if __name__ == "__main__":
    verified = verify(load(RESULT))
    print(
        json.dumps(
            {
                "status": "VERIFIED_D54R_COMPLETE_RECEIPT_AGGREGATION",
                "sample_receipt_count": verified["sample_receipt_count"],
                "sample_receipt_set_sha256": verified["sample_receipt_set_sha256"],
                "next_gate": verified["next_gate"],
            },
            sort_keys=True,
        )
    )
