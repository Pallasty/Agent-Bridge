#!/usr/bin/env python3
"""D51 static full-53 streaming lifetime and runtime-work checker."""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from typing import Any, Mapping


HERE = Path(__file__).resolve().parent
CONTRACT = HERE / "fh_l8_full53_streaming_lifetime_d51_contract.json"


class D51Error(ValueError):
    pass


def _load(path: Path) -> Mapping[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, Mapping):
        raise D51Error(f"{path.name}: JSON object required")
    return value


def _sha(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            hasher.update(block)
    return hasher.hexdigest()


def check(contract_path: Path = CONTRACT) -> dict[str, Any]:
    contract = _load(contract_path)
    if contract.get("contract_id") != "FH-L8-FULL53-STREAMING-LIFETIME-D51-V1":
        raise D51Error("contract id drift")
    if contract.get("analysis_class") != (
        "STATIC_STREAMING_LIFETIME_AND_RUNTIME_WORK_UNIT_DESIGN_NO_EXECUTION"
    ):
        raise D51Error("analysis class drift")

    pins = contract.get("source_pins")
    if not isinstance(pins, Mapping):
        raise D51Error("source_pins object required")
    for name, expected in pins.items():
        path = HERE / name
        if not path.is_file() or _sha(path) != expected:
            raise D51Error(f"source pin mismatch: {name}")

    d50 = _load(HERE / "fh_l8_full53_kernel_fanout_d50_result.json")
    d23 = _load(HERE / "fh_l8_full_resource_envelope_d23_result.json")
    d16 = _load(HERE / "fh_l8_packed_consumer_forensic_d16_contract.json")
    design = contract["streaming_design"]
    disk = contract["disk_lifetime_design"]
    runtime = contract["runtime_work_units"]

    merge = d16["clean_reexecution_protocol"]["merge"]
    limits = d16["resource_limits"]
    if design["partition_order"] != merge["partition_order"]:
        raise D51Error("partition order drift")
    if design["maximum_merge_fan_in"] != merge["maximum_fan_in"]:
        raise D51Error("merge fan-in drift")
    if design["source_read_buffer_bytes"] != limits["read_chunk_bytes"]:
        raise D51Error("source read-buffer drift")
    if design["manifest_bytes"] != limits["max_manifest_bytes"]:
        raise D51Error("manifest bound drift")
    if design["result_bytes"] != limits["max_result_bytes"]:
        raise D51Error("result bound drift")
    if design["receipt_bytes"] != limits["max_external_receipt_bytes_each"]:
        raise D51Error("receipt bound drift")
    if design["target_publication"] != (
        "stream_to_fresh_stage_then_atomic_no_replace_publish"
    ):
        raise D51Error("target publication design drift")
    if design["old_runs_deleted_before_terminal_receipt"] is not False:
        raise D51Error("pre-receipt run deletion is forbidden")

    merge_levels = math.ceil(math.log(d50["source_shards"], design["maximum_merge_fan_in"]))
    if design["merge_levels_for_53_runs"] != merge_levels:
        raise D51Error("merge-level arithmetic drift")
    known_buffer = (
        design["maximum_merge_fan_in"] * design["input_buffer_bytes_per_run"]
        + design["output_buffer_bytes"]
        + design["manifest_bytes"]
        + design["result_bytes"]
        + design["receipt_bytes"]
    )
    if design["known_buffer_subtotal_bytes"] != known_buffer:
        raise D51Error("known-buffer arithmetic drift")

    if disk["source_checkpoint_bytes"] != limits["max_source_checkpoint_bytes"]:
        raise D51Error("source checkpoint bound drift")
    if disk["structural_spill_bytes"] != d50["total_spill_bytes"]:
        raise D51Error("D50 structural spill bound drift")
    if disk["d23_registered_scratch_bytes"] != d23["required_free_scratch_bytes"]:
        raise D51Error("D23 scratch guardrail drift")
    required_scratch = (
        disk["simultaneous_spill_generations"] * disk["structural_spill_bytes"]
        + disk["source_checkpoint_bytes"]
        + disk["manifest_count"] * design["manifest_bytes"]
        + disk["receipt_count"] * design["receipt_bytes"]
        + design["result_bytes"]
    )
    if disk["design_required_scratch_bytes"] != required_scratch:
        raise D51Error("scratch lifetime arithmetic drift")
    if disk["d23_shortfall_bytes"] != (
        required_scratch - disk["d23_registered_scratch_bytes"]
    ):
        raise D51Error("D23 scratch shortfall drift")
    if disk["d23_shortfall_bytes"] <= 0:
        raise D51Error("D51 must not claim D23 scratch adequacy")

    expected_runtime = {
        "scientific_kernel_calls": d50["source_records"],
        "candidate_visits": d50["total_candidate_actions"],
        "merge_record_reads_upper": merge_levels * d50["total_candidate_actions"],
        "merge_record_writes_upper": merge_levels * d50["total_candidate_actions"],
        "merge_heap_comparisons_design_upper": (
            2
            * merge_levels
            * math.ceil(math.log2(design["maximum_merge_fan_in"]))
            * d50["total_candidate_actions"]
        ),
        "host_seconds_bound_proven": False,
    }
    if runtime != expected_runtime:
        raise D51Error("runtime work-unit arithmetic drift")

    phases = contract.get("lifetime_phases")
    expected_phases = [
        "source_admission",
        "kernel_and_spill",
        "partition_external_merge",
        "target_publication",
    ]
    if not isinstance(phases, list) or [phase.get("phase") for phase in phases] != expected_phases:
        raise D51Error("lifetime phase order drift")
    live_components = {
        component
        for phase in phases
        for component in phase.get("live_components", [])
    }
    unresolved = contract.get("unresolved_numeric_terms")
    if not isinstance(unresolved, list) or not set(unresolved).issubset(live_components | {
        "filesystem_page_cache_accounting",
        "per_operation_host_time_ns",
    }):
        raise D51Error("unresolved numeric-term coverage drift")

    authority = contract["authority"]
    false_fields = {
        "production_adapter_implemented",
        "full53_executed",
        "numeric_peak_memory_proven",
        "numeric_runtime_seconds_proven",
        "external_resource_reservation_admitted",
        "full53_execution_authorized",
    }
    if any(authority.get(field) is not False for field in false_fields):
        raise D51Error("authority unexpectedly open")
    if authority.get("packed_q3_reads") != 0:
        raise D51Error("D51 must read zero packed q3 records")
    if authority.get("scientific_kernel_calls_executed") != 0:
        raise D51Error("D51 must execute zero scientific kernel calls")

    return {
        "status": "VERIFIED_D51_STREAMING_LIFETIME_AND_WORK_UNIT_DESIGN_RESOURCE_NOT_READY",
        "source_records": d50["source_records"],
        "source_shards": d50["source_shards"],
        "structural_spill_bytes": disk["structural_spill_bytes"],
        "simultaneous_spill_generations": disk["simultaneous_spill_generations"],
        "design_required_scratch_bytes": required_scratch,
        "d23_registered_scratch_bytes": disk["d23_registered_scratch_bytes"],
        "d23_shortfall_bytes": disk["d23_shortfall_bytes"],
        "known_buffer_subtotal_bytes": known_buffer,
        **expected_runtime,
        "unresolved_numeric_terms": unresolved,
        "production_adapter_implemented": False,
        "packed_q3_reads": 0,
        "scientific_kernel_calls_executed": 0,
        "numeric_peak_memory_proven": False,
        "numeric_runtime_seconds_proven": False,
        "external_resource_reservation_admitted": False,
        "full53_execution_authorized": False,
        "next_gate": contract["next_gate"],
    }


def main() -> None:
    print(json.dumps(check(), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
