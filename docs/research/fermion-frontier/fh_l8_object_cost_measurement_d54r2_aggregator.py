#!/usr/bin/env python3
"""Independent verifier/aggregator for a complete FH-L8 D54 receipt set."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import statistics
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location(
    "fh_l8_d54_launcher", HERE / "fh_l8_object_cost_measurement_d54r2_launcher.py"
)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("cannot load D54 launcher")
launcher = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(launcher)


class AggregateError(RuntimeError):
    pass


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def summary(values: list[int]) -> dict[str, int]:
    if not values or any(isinstance(value, bool) or not isinstance(value, int) for value in values):
        raise AggregateError("nonempty integer metric required")
    return {"min": min(values), "median": int(statistics.median(values)), "max": max(values)}


def aggregate(root: Path) -> dict[str, Any]:
    state_raw = (root / "launcher-state.json").read_bytes()
    state = json.loads(state_raw)
    expected = launcher.plan()
    if state.get("status") != "D54_RAW_SAMPLE_SET_COMPLETE" or state.get("sample_count") != 70:
        raise AggregateError("launcher state is not complete")
    if state.get("packed_q3_reads") != 0 or state.get("full53_executed") is not False:
        raise AggregateError("authority boundary drift")
    if len(state.get("receipts", [])) != len(expected):
        raise AggregateError("receipt count drift")
    observed: list[dict[str, Any]] = []
    for sample, identity in zip(expected, state["receipts"]):
        if any(identity.get(key) != value for key, value in sample.items()):
            raise AggregateError("receipt order/identity drift")
        path = root / "receipts" / identity["path"]
        raw = path.read_bytes()
        if len(raw) != identity["bytes"] or sha(raw) != identity["sha256"]:
            raise AggregateError("receipt hash drift")
        envelope = json.loads(raw)
        if envelope.get("sample") != sample:
            raise AggregateError("sample envelope drift")
        if envelope.get("cgroup_swap_current_bytes") != 0:
            raise AggregateError("nonzero swap")
        events = envelope.get("cgroup_memory_events_delta", {})
        if events.get("oom") != 0 or events.get("oom_kill") != 0:
            raise AggregateError("OOM event")
        result = envelope["result"]
        if result.get("packed_q3_reads") != 0:
            raise AggregateError("packed-q3 read")
        observed.append(envelope)
    groups: list[dict[str, Any]] = []
    for tier, sizes in (
        ("synthetic_object_calibration", (0, 1, 8, 32, 64, 225)),
        ("source_bound_fixed64_micro", (1, 8, 32, 64)),
    ):
        for size in sizes:
            rows = [item for item in observed if item["sample"]["tier"] == tier
                    and item["sample"]["size"] == size]
            digests = {item["result"]["structural_output_sha256"] for item in rows}
            if len(rows) != 7 or len(digests) != 1:
                raise AggregateError("missing sample or structural digest drift")
            if tier == "source_bound_fixed64_micro" and size == 64 and digests != {
                "38aaeffb8f178e918e4f326888493166c21afc7fb1379e91ab965c345b4adc12"
            }:
                raise AggregateError("full64 structural digest mismatch")
            measured = [item for item in rows if item["sample"]["sample_kind"] == "measured"]
            metrics = {}
            for field in (
                "tracemalloc_current_bytes", "tracemalloc_peak_bytes",
                "process_ru_maxrss_kib", "wall_elapsed_ns", "process_cpu_ns",
            ):
                metrics[field] = summary([item["result"][field] for item in measured])
            for field in ("cgroup_memory_current_bytes", "cgroup_memory_peak_bytes"):
                metrics[field] = summary([item[field] for item in measured])
            groups.append({"tier": tier, "size": size, "measured_samples": 5,
                           "structural_output_sha256": next(iter(digests)), "metrics": metrics})
    return {
        "schema_version": 1, "status": "D54R2_BOUNDED_LOCAL_MEASUREMENT_COMPLETE",
        "source_commit": state["source_commit"], "launcher_state_sha256": sha(state_raw),
        "raw_sample_count": len(observed), "measured_sample_count": 50,
        "warmup_sample_count": 20, "groups": groups,
        "scientific_kernel_calls_executed": sum(
            item["result"]["scientific_kernel_calls"] for item in observed
        ),
        "packed_q3_reads": 0, "full53_executed": False,
        "full53_extrapolation_performed": False,
        "numeric_worst_case_proven": False, "resource_authorization_conferred": False,
        "scope": "bounded_local_empirical_observation_only",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scratch", type=Path, default=launcher.ROOT)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        result = aggregate(args.scratch)
        raw = launcher.canonical(result)
        if args.output:
            launcher.publish(args.output, raw)
        print(raw.decode("ascii"), end="")
        return 0
    except Exception as exc:
        print(launcher.canonical({"status": "INDETERMINATE_MEASUREMENT_FAILURE",
                                  "error": f"{type(exc).__name__}: {exc}"}).decode("ascii"), end="")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
