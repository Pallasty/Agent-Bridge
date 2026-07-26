#!/usr/bin/env python3
"""One-process D54 object-cost sample runner.

The runner executes exactly one D53-declared sample and exits.  It refuses to
run unless supplied the separately frozen D54 authorization contract.  This
source file itself confers no execution authority.
"""

from __future__ import annotations

import argparse
import gc
import hashlib
import importlib.util
import json
import os
import platform
import resource
import sys
import time
import tracemalloc
from fractions import Fraction
from pathlib import Path
from typing import Any, Mapping


HERE = Path(__file__).resolve().parent
D53_CONTRACT = HERE / "fh_l8_object_cost_measurement_d53_contract.json"
AUTHORIZATION_NAME = "fh_l8_object_cost_measurement_d54_authorization.json"


class D54RunnerError(RuntimeError):
    pass


def load(path: Path) -> Mapping[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, Mapping):
        raise D54RunnerError(f"{path.name}: JSON object required")
    return value


def digest(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            hasher.update(block)
    return hasher.hexdigest()


def owned_graph_bytes(value: Any) -> int:
    """Alias-aware recursive CPython object-graph size for allowed containers."""
    seen: set[int] = set()

    def visit(item: Any) -> int:
        identity = id(item)
        if identity in seen:
            return 0
        seen.add(identity)
        total = sys.getsizeof(item)
        if isinstance(item, dict):
            total += sum(visit(key) + visit(child) for key, child in item.items())
        elif isinstance(item, (list, tuple, set, frozenset)):
            total += sum(visit(child) for child in item)
        elif isinstance(item, Fraction):
            total += visit(item.numerator) + visit(item.denominator)
        return total

    return visit(value)


def sample_plan(d53: Mapping[str, Any]) -> list[dict[str, Any]]:
    plan: list[dict[str, Any]] = []
    warmups = d53["isolation"]["warmup_runs_per_size"]
    measured = d53["isolation"]["measured_runs_per_size"]
    for tier in d53["fixture_tiers"]:
        sizes = tier.get("sizes", tier.get("sample_prefix_sizes"))
        for size in sizes:
            for sample_kind, count in (("warmup", warmups), ("measured", measured)):
                for repetition in range(count):
                    plan.append(
                        {
                            "tier": tier["tier"],
                            "size": size,
                            "sample_kind": sample_kind,
                            "repetition": repetition,
                        }
                    )
    return plan


def validate_authorization(
    authorization: Mapping[str, Any],
    runner_path: Path,
    d53_path: Path = D53_CONTRACT,
) -> None:
    if authorization.get("authorization_id") != "FH-L8-D54-OBJECT-COST-MEASUREMENT-AUTH-V1":
        raise D54RunnerError("authorization id drift")
    if authorization.get("measurement_execution_authorized") is not True:
        raise D54RunnerError("measurement execution is not authorized")
    if authorization.get("runner_sha256") != digest(runner_path):
        raise D54RunnerError("runner source pin mismatch")
    if authorization.get("d53_contract_sha256") != digest(d53_path):
        raise D54RunnerError("D53 contract pin mismatch")
    if authorization.get("packed_q3_reads_authorized") != 0:
        raise D54RunnerError("packed-q3 authority must remain zero")
    if authorization.get("full53_execution_authorized") is not False:
        raise D54RunnerError("full53 authority unexpectedly open")


def _runtime_metrics(started_wall: int, started_cpu: int) -> dict[str, Any]:
    usage = resource.getrusage(resource.RUSAGE_SELF)
    current, peak = tracemalloc.get_traced_memory()
    return {
        "python_implementation": platform.python_implementation(),
        "python_version": platform.python_version(),
        "allocator_environment": os.environ.get("PYTHONMALLOC", "default"),
        "tracemalloc_current_bytes": current,
        "tracemalloc_peak_bytes": peak,
        "process_ru_maxrss_kib": usage.ru_maxrss,
        "wall_elapsed_ns": time.perf_counter_ns() - started_wall,
        "process_cpu_ns": time.process_time_ns() - started_cpu,
    }


def measure_synthetic(size: int) -> dict[str, Any]:
    if size not in (0, 1, 8, 32, 64, 225):
        raise D54RunnerError("synthetic size outside D53")
    gc.collect()
    tracemalloc.start()
    started_wall = time.perf_counter_ns()
    started_cpu = time.process_time_ns()
    sector = {index: index - size for index in range(size)}
    fractions = [Fraction(index + 1, size + 1) for index in range(size)]
    writers = {index: bytearray() for index in range(256)}
    heap_rows = [(index, index.to_bytes(16, "big"), index) for index in range(size)]
    owned = {
        "sector_action_dictionary_peak": owned_graph_bytes(sector),
        "fraction_object_peak": owned_graph_bytes(fractions),
        "partition_writer_state_peak": owned_graph_bytes(writers),
        "sort_key_heap_object_peak": owned_graph_bytes(heap_rows),
    }
    structural = hashlib.sha256(
        json.dumps(
            {"size": size, "sector": sorted(sector.items())},
            separators=(",", ":"),
        ).encode("ascii")
    ).hexdigest()
    metrics = _runtime_metrics(started_wall, started_cpu)
    tracemalloc.stop()
    return {
        "tier": "synthetic_object_calibration",
        "size": size,
        "owned_graph_bytes": owned,
        "operation_count": size,
        "structural_output_sha256": structural,
        "scientific_kernel_calls": 0,
        "packed_q3_reads": 0,
        **metrics,
    }


def _load_module(name: str, path: Path) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise D54RunnerError(f"cannot load {path.name}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def measure_fixed64(prefix: int) -> dict[str, Any]:
    if prefix not in (1, 8, 32, 64):
        raise D54RunnerError("fixed64 prefix outside D53")
    d5 = _load_module("d54_d5", HERE / "fh_l8_symmetry_orbit_quotient_d5_checker.py")
    d4 = _load_module("d54_d4", HERE / "fh_l8_scalar_supremum_d4_checker.py")
    backend = _load_module("d54_backend", HERE / "hubbard_strang_commutator_checker.py")
    d5_contract = load(HERE / "fh_l8_symmetry_orbit_quotient_d5_contract.json")
    symmetries, _ = d5._build_symmetries(d5_contract)
    bonds = {name: backend._hopping_bonds(8, name) for name in ("H1", "H2", "H3", "H4")}
    seed = int(d5_contract["workload"]["neel_basis_hex"], 16)

    scientific_calls = 0
    initial, _, _ = d5._reduced_column(d4, backend, bonds, seed, symmetries)
    scientific_calls += 1
    second_seed = sorted(initial)[0]
    second, _, _ = d5._reduced_column(d4, backend, bonds, second_seed, symmetries)
    scientific_calls += 1
    pool = set(initial) | set(second)
    for candidate in sorted(initial):
        if len(pool) >= 64:
            break
        child, _, _ = d5._reduced_column(d4, backend, bonds, candidate, symmetries)
        scientific_calls += 1
        pool.update(child)
    representatives = sorted(pool)[:prefix]
    if len(representatives) != prefix:
        raise D54RunnerError("fixed64 fixture construction failed")

    gc.collect()
    tracemalloc.start()
    started_wall = time.perf_counter_ns()
    started_cpu = time.process_time_ns()
    rows = []
    owned_sizes = []
    for representative in representatives:
        started = time.perf_counter_ns()
        column, orbit, dropped = d5._reduced_column(
            d4, backend, bonds, representative, symmetries
        )
        scientific_calls += 1
        owned_sizes.append(owned_graph_bytes(column))
        rows.append(
            {
                "representative_hex": hex(representative),
                "entries": len(column),
                "orbit": orbit,
                "dropped": dropped,
                "elapsed_ns": time.perf_counter_ns() - started,
            }
        )
    structural_rows = [{k: v for k, v in row.items() if k != "elapsed_ns"} for row in rows]
    structural = hashlib.sha256(
        json.dumps(structural_rows, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    metrics = _runtime_metrics(started_wall, started_cpu)
    tracemalloc.stop()
    return {
        "tier": "source_bound_fixed64_micro",
        "size": prefix,
        "reduced_column_owned_graph_bytes_min": min(owned_sizes),
        "reduced_column_owned_graph_bytes_max": max(owned_sizes),
        "operation_count": len(rows),
        "structural_output_sha256": structural,
        "scientific_kernel_calls": scientific_calls,
        "packed_q3_reads": 0,
        "rows": rows,
        **metrics,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--authorization", type=Path, required=True)
    parser.add_argument("--tier", required=True)
    parser.add_argument("--size", type=int, required=True)
    parser.add_argument("--sample-kind", choices=("warmup", "measured"), required=True)
    parser.add_argument("--repetition", type=int, required=True)
    args = parser.parse_args()
    runner_path = Path(__file__).resolve()
    validate_authorization(load(args.authorization), runner_path)
    d53 = load(D53_CONTRACT)
    requested = {
        "tier": args.tier,
        "size": args.size,
        "sample_kind": args.sample_kind,
        "repetition": args.repetition,
    }
    if requested not in sample_plan(d53):
        raise D54RunnerError("requested sample is outside D53 plan")
    if args.tier == "synthetic_object_calibration":
        result = measure_synthetic(args.size)
    elif args.tier == "source_bound_fixed64_micro":
        result = measure_fixed64(args.size)
    else:
        raise D54RunnerError("unknown measurement tier")
    print(json.dumps({**requested, **result}, sort_keys=True))


if __name__ == "__main__":
    main()
