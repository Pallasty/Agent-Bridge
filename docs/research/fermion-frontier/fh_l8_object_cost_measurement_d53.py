#!/usr/bin/env python3
"""Validate the FH-L8 D53 object/allocation cost measurement protocol."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping


HERE = Path(__file__).resolve().parent
CONTRACT = HERE / "fh_l8_object_cost_measurement_d53_contract.json"
RESULT = HERE / "fh_l8_object_cost_measurement_d53_result.json"


class D53Error(ValueError):
    pass


def load(path: Path) -> Mapping[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, Mapping):
        raise D53Error(f"{path.name}: JSON object required")
    return value


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check(contract_path: Path = CONTRACT) -> dict[str, Any]:
    contract = load(contract_path)
    if contract.get("contract_id") != "FH-L8-OBJECT-COST-MEASUREMENT-D53-V1":
        raise D53Error("contract id drift")
    if contract.get("analysis_class") != (
        "MEASUREMENT_PROTOCOL_DESIGN_NO_OBJECT_OR_KERNEL_MEASUREMENT"
    ):
        raise D53Error("analysis class drift")
    pins = contract.get("source_pins")
    if not isinstance(pins, Mapping) or len(pins) != 7:
        raise D53Error("source pin set drift")
    for name, expected in pins.items():
        path = HERE / name
        if not path.is_file() or digest(path) != expected:
            raise D53Error(f"source pin mismatch: {name}")

    d52 = load(HERE / "fh_l8_full53_adapter_static_cost_d52_result.json")
    d51 = load(HERE / "fh_l8_full53_streaming_lifetime_d51_result.json")
    d49 = load(HERE / "fh_l8_controlled_resource_stability_d49_result.json")
    if d52.get("next_gate") != "D53_OBJECT_ALLOCATION_AND_OPERATION_COST_MEASUREMENT_PROTOCOL_DESIGN":
        raise D53Error("D52 next-gate drift")
    if d49.get("full53_extrapolation_forbidden") is not True:
        raise D53Error("D49 non-extrapolation boundary drift")

    targets = contract.get("measurement_targets")
    expected_targets = {
        "python_runtime_base_peak",
        "sector_action_dictionary_peak",
        "canonical_info_transient_peak",
        "basis_images_transient_peak",
        "fraction_object_peak",
        "reduced_column_dictionary_peak",
        "partition_writer_state_peak",
        "sort_key_heap_object_peak",
        "filesystem_page_cache_accounting",
        "per_operation_host_time_ns",
    }
    if not isinstance(targets, list) or set(targets) != expected_targets:
        raise D53Error("measurement target coverage drift")
    mapping = contract.get("upstream_term_mapping")
    upstream_terms = set(d51["unresolved_numeric_terms"]) | set(
        load(HERE / "fh_l8_full53_adapter_static_cost_d52_contract.json")[
            "unresolved_allocation_costs"
        ]
    )
    if not isinstance(mapping, Mapping) or set(mapping) != upstream_terms:
        raise D53Error("upstream unresolved-term mapping drift")
    if not set(mapping.values()).issubset(expected_targets):
        raise D53Error("upstream term maps outside measurement targets")

    tiers = contract.get("fixture_tiers")
    if not isinstance(tiers, list) or [tier.get("tier") for tier in tiers] != [
        "synthetic_object_calibration",
        "source_bound_fixed64_micro",
    ]:
        raise D53Error("fixture tier drift")
    synthetic, source_bound = tiers
    if synthetic.get("sizes") != [0, 1, 8, 32, 64, 225]:
        raise D53Error("synthetic calibration size drift")
    if synthetic.get("scientific_kernel_calls_per_sample") != 0:
        raise D53Error("synthetic tier must call no scientific kernel")
    if source_bound.get("sample_prefix_sizes") != [1, 8, 32, 64]:
        raise D53Error("source-bound prefix design drift")
    if source_bound.get("required_structural_digest") != d49["structural_rows_sha256"]:
        raise D53Error("fixed64 structural digest drift")
    if source_bound.get("maximum_scientific_kernel_calls_per_run") != d49["scientific_action_calls"]:
        raise D53Error("fixed64 scientific-call cap drift")
    if source_bound.get("full53_extrapolation_forbidden") is not True:
        raise D53Error("source-bound tier must forbid full53 extrapolation")
    if source_bound.get("execution_authorized_by_d53") is not False:
        raise D53Error("D53 must not authorize measurement execution")

    isolation = contract.get("isolation")
    expected_isolation = {
        "fresh_process_per_measured_sample": True,
        "cpu_affinity": "cpu0",
        "memory_max_bytes": 536870912,
        "memory_high_bytes": 402653184,
        "swap_max_bytes": 0,
        "warmup_runs_per_size": 2,
        "measured_runs_per_size": 5,
        "garbage_collection_before_baseline": True,
        "network_allowed": False,
        "external_writes_allowed": False,
    }
    if isolation != expected_isolation:
        raise D53Error("isolation design drift")

    metrics = contract.get("required_metrics")
    if not isinstance(metrics, list) or len(metrics) != 14 or len(set(metrics)) != len(metrics):
        raise D53Error("required metric set drift")
    for required in (
        "tracemalloc_peak_bytes",
        "process_ru_maxrss_kib",
        "cgroup_memory_peak_bytes",
        "cgroup_memory_events_delta",
        "wall_elapsed_ns",
        "process_cpu_ns",
        "operation_count",
        "structural_output_sha256",
    ):
        if required not in metrics:
            raise D53Error(f"missing required metric: {required}")

    sequence = contract.get("measurement_sequence")
    if not isinstance(sequence, list) or len(sequence) != 10:
        raise D53Error("measurement sequence drift")
    if sequence[-1] != "exit_without_promoting_any_full53_bound":
        raise D53Error("measurement sequence does not close authority")
    failures = contract.get("fail_closed_conditions")
    if not isinstance(failures, list) or len(failures) != 8:
        raise D53Error("fail-closed condition coverage drift")

    aggregation = contract.get("aggregation")
    if not isinstance(aggregation, Mapping):
        raise D53Error("aggregation policy missing")
    if aggregation.get("subtract_runtime_baseline_only_for_tracemalloc_metrics") is not True:
        raise D53Error("baseline subtraction scope drift")
    if aggregation.get("ru_maxrss_and_cgroup_peak_are_not_baseline_subtracted") is not True:
        raise D53Error("peak metric subtraction boundary drift")

    authority = contract.get("authority")
    false_fields = {
        "measurement_runner_implemented",
        "full53_executed",
        "numeric_peak_memory_proven",
        "numeric_runtime_seconds_proven",
        "external_resource_reservation_admitted",
        "full53_execution_authorized",
    }
    if not isinstance(authority, Mapping) or any(
        authority.get(field) is not False for field in false_fields
    ):
        raise D53Error("authority unexpectedly open")
    for field in ("object_measurements_executed", "packed_q3_reads", "scientific_kernel_calls_executed"):
        if authority.get(field) != 0:
            raise D53Error("D53 must execute no measurement or scientific action")

    return {
        "status": "VERIFIED_D53_OBJECT_COST_MEASUREMENT_PROTOCOL_DESIGN_NO_EXECUTION",
        "measurement_target_count": len(targets),
        "fixture_tier_count": len(tiers),
        "synthetic_size_count": len(synthetic["sizes"]),
        "source_bound_prefix_count": len(source_bound["sample_prefix_sizes"]),
        "required_metric_count": len(metrics),
        "warmup_runs_per_size": isolation["warmup_runs_per_size"],
        "measured_runs_per_size": isolation["measured_runs_per_size"],
        "memory_max_bytes": isolation["memory_max_bytes"],
        "swap_max_bytes": isolation["swap_max_bytes"],
        "fixed64_structural_digest": source_bound["required_structural_digest"],
        "maximum_scientific_kernel_calls_per_run": source_bound[
            "maximum_scientific_kernel_calls_per_run"
        ],
        "measurement_runner_implemented": False,
        "object_measurements_executed": 0,
        "packed_q3_reads": 0,
        "scientific_kernel_calls_executed": 0,
        "numeric_peak_memory_proven": False,
        "numeric_runtime_seconds_proven": False,
        "external_resource_reservation_admitted": False,
        "full53_execution_authorized": False,
        "next_gate": contract["next_gate"],
    }


def main() -> None:
    result = check()
    if load(RESULT) != result:
        raise D53Error("committed result drift")
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
