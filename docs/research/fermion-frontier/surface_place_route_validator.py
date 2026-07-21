#!/usr/bin/env python3
"""Validate a surface-code place-and-route schedule and active volume."""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Mapping, Set


SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
BOUNDARY_DELTAS = {"N": (-1, 0), "E": (0, 1), "S": (1, 0), "W": (0, -1)}
EXPECTED_CYCLE_US = 1.0
EXPECTED_LOGICAL_FAILURE_BUDGET = 0.005


def _finite(value: Any, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be finite")
    value = float(value)
    if not math.isfinite(value):
        raise ValueError(f"{name} must be finite")
    return value


def _nonnegative(value: Any, name: str) -> float:
    value = _finite(value, name)
    if value < 0:
        raise ValueError(f"{name} must be non-negative")
    return value


def _positive(value: Any, name: str) -> float:
    value = _finite(value, name)
    if value <= 0:
        raise ValueError(f"{name} must be positive")
    return value


def _positive_int(value: Any, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{name} must be a positive integer")
    return value


def _nonnegative_int(value: Any, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{name} must be a non-negative integer")
    return value


def _nonempty(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string")
    return value


def _unique_string_list(value: Any, name: str) -> List[str]:
    if not isinstance(value, list) or not all(
        isinstance(item, str) and item.strip() for item in value
    ):
        raise ValueError(f"{name} must be a unique list of non-empty strings")
    if len(value) != len(set(value)):
        raise ValueError(f"{name} must be a unique list of non-empty strings")
    return value


def _connected_patch_path(
    patch_ids: List[str], placement_map: Mapping[str, Mapping[str, Any]]
) -> bool:
    if len(patch_ids) <= 1:
        return True
    if any(patch_id not in placement_map for patch_id in patch_ids):
        return False
    remaining = set(patch_ids)
    frontier = [remaining.pop()]
    while frontier:
        current = frontier.pop()
        current_placement = placement_map[current]
        adjacent = {
            candidate
            for candidate in remaining
            if abs(placement_map[candidate]["row"] - current_placement["row"])
            + abs(placement_map[candidate]["col"] - current_placement["col"])
            == 1
        }
        remaining.difference_update(adjacent)
        frontier.extend(adjacent)
    return not remaining


def _string_set(value: Any) -> Set[str]:
    if not isinstance(value, list):
        return set()
    return {item for item in value if isinstance(item, str)}


def validate_contract(contract: Mapping[str, Any]) -> List[str]:
    errors: List[str] = []
    if contract.get("schema_version") != 1:
        errors.append("contract schema_version must be 1")
    if contract.get("route") != "dynamic_jw_surface_code":
        errors.append("contract route must be dynamic_jw_surface_code")
    if contract.get("parent_term_route") != "dynamic_jw_local_grid_source_leading":
        errors.append("contract parent_term_route must be dynamic_jw_local_grid_source_leading")
    if contract.get("parent_convergence_route") != "dynamic_jw_local_grid":
        errors.append("contract parent_convergence_route must be dynamic_jw_local_grid")
    for key in ("workload_fingerprint", "patch_model"):
        if not isinstance(contract.get(key), str) or not contract[key].strip():
            errors.append(f"contract {key} must be a non-empty string")
    for key in (
        "target_linear_size",
        "target_trotter_steps",
        "logical_events_per_trotter_step",
        "max_logical_events_per_operation",
    ):
        try:
            _positive_int(contract[key], f"contract.{key}")
        except (KeyError, ValueError) as exc:
            errors.append(str(exc))
    if contract.get("max_logical_events_per_operation") != 1:
        errors.append("contract max_logical_events_per_operation must be 1")
    for key in (
        "allowed_patch_roles",
        "allowed_operation_kinds",
        "allowed_evidence_statuses",
        "exact_evidence_statuses",
        "allowed_boundaries",
        "allowed_orientations",
        "required_operation_kinds",
        "logical_event_operation_kinds",
        "non_logical_event_operation_kinds",
        "required_live_patch_roles",
        "required_patch_roles",
        "allowed_corridor_patch_roles",
    ):
        value = contract.get(key)
        if not isinstance(value, list) or not value or not all(
            isinstance(item, str) and item for item in value
        ) or len(value) != len(set(value)):
            errors.append(f"contract {key} must be a non-empty list of strings")
    if contract.get("distance_rule") != "odd positive integer":
        errors.append("contract distance_rule must be odd positive integer")
    if contract.get("physical_qubits_per_patch_rule") != "2d^2-1":
        errors.append("contract physical_qubits_per_patch_rule must be 2d^2-1")
    if contract.get("operation_timing_rule") != (
        "integer start_offset_cycles >= 0 and positive duration_cycles contained within the "
        "interval; operations sharing a participant or corridor patch cannot overlap"
    ):
        errors.append("contract operation_timing_rule is invalid")
    try:
        contract_cycle_us = _positive(contract["cycle_us"], "contract.cycle_us")
        if not math.isclose(
            contract_cycle_us, EXPECTED_CYCLE_US, rel_tol=0.0, abs_tol=1e-15
        ):
            raise ValueError(f"contract.cycle_us must equal {EXPECTED_CYCLE_US}")
        contract_failure_budget = _nonnegative(
            contract["logical_failure_budget"], "contract.logical_failure_budget"
        )
        if contract_failure_budget > 1:
            raise ValueError("contract.logical_failure_budget must be in [0,1]")
        if not math.isclose(
            contract_failure_budget,
            EXPECTED_LOGICAL_FAILURE_BUDGET,
            rel_tol=0.0,
            abs_tol=1e-15,
        ):
            raise ValueError(
                "contract.logical_failure_budget must equal "
                f"{EXPECTED_LOGICAL_FAILURE_BUDGET}"
            )
    except (KeyError, ValueError) as exc:
        errors.append(str(exc))
    allowed_patch_roles = _string_set(contract.get("allowed_patch_roles"))
    allowed_operation_kinds = _string_set(contract.get("allowed_operation_kinds"))
    allowed_evidence = _string_set(contract.get("allowed_evidence_statuses"))
    exact_evidence = _string_set(contract.get("exact_evidence_statuses"))
    if not exact_evidence.issubset(allowed_evidence):
        errors.append("contract exact_evidence_statuses must be a subset of allowed evidence")
    if exact_evidence != {"compiler_export", "measured"}:
        errors.append("contract exact_evidence_statuses must be compiler_export and measured")
    if not _string_set(contract.get("required_operation_kinds")).issubset(
        allowed_operation_kinds
    ):
        errors.append("contract required_operation_kinds must be a subset of allowed operations")
    if _string_set(contract.get("required_operation_kinds")) != {
        "ladder_joint_measurement",
        "rotation",
        "distill",
        "buffer",
        "inject",
    }:
        errors.append("contract required_operation_kinds is invalid")
    if not _string_set(contract.get("logical_event_operation_kinds")).issubset(
        allowed_operation_kinds
    ):
        errors.append("contract logical_event_operation_kinds must be allowed operations")
    if _string_set(contract.get("logical_event_operation_kinds")) != {
        "ladder_joint_measurement"
    }:
        errors.append("contract logical_event_operation_kinds is invalid")
    if not _string_set(contract.get("non_logical_event_operation_kinds")).issubset(
        allowed_operation_kinds
    ):
        errors.append(
            "contract non_logical_event_operation_kinds must be a subset of allowed operations"
        )
    if not _string_set(contract.get("required_live_patch_roles")).issubset(
        allowed_patch_roles
    ):
        errors.append("contract required_live_patch_roles must be a subset of allowed patch roles")
    if _string_set(contract.get("required_live_patch_roles")) != {
        "data",
        "factory",
        "buffer",
    }:
        errors.append("contract required_live_patch_roles is invalid")
    if not _string_set(contract.get("required_patch_roles")).issubset(allowed_patch_roles):
        errors.append("contract required_patch_roles must be a subset of allowed patch roles")
    if _string_set(contract.get("required_patch_roles")) != {
        "data",
        "auxiliary",
        "factory",
        "buffer",
    }:
        errors.append("contract required_patch_roles is invalid")
    if not _string_set(contract.get("allowed_corridor_patch_roles")).issubset(
        allowed_patch_roles
    ):
        errors.append("contract allowed_corridor_patch_roles must be a subset of allowed patch roles")
    return errors


def _result(status: str, errors: List[str], warnings: List[str] | None = None) -> Dict[str, Any]:
    return {
        "route": "dynamic_jw_surface_code",
        "status": status,
        "errors": errors,
        "warnings": warnings or [],
        "planning_total_cycles": None,
        "planning_active_physical_qubit_cycles": None,
        "complete_total_cycles": None,
        "complete_active_physical_qubit_cycles": None,
    }


def validate_ledger(contract: Mapping[str, Any], ledger: Mapping[str, Any]) -> Dict[str, Any]:
    schema_errors = validate_contract(contract)
    if ledger.get("schema_version") != 1:
        schema_errors.append("ledger schema_version must be 1")
    if ledger.get("workload_fingerprint") != contract.get("workload_fingerprint"):
        schema_errors.append("ledger workload_fingerprint does not match contract")
    if ledger.get("route") != contract.get("route"):
        schema_errors.append("ledger route does not match contract")
    if ledger.get("patch_model") != contract.get("patch_model"):
        schema_errors.append("ledger patch_model does not match contract")
    if schema_errors:
        return _result("INVALID_SCHEMA", schema_errors)

    errors: List[str] = []
    warnings: List[str] = []
    try:
        l = _positive_int(ledger["linear_size"], "ledger.linear_size")
        r = _positive_int(ledger["trotter_steps"], "ledger.trotter_steps")
        logical_event_count = _positive_int(ledger["logical_event_count"], "ledger.logical_event_count")
        distance = _positive_int(ledger["distance"], "ledger.distance")
        cycle_us = _positive(ledger["cycle_us"], "ledger.cycle_us")
        failure_budget = _nonnegative(ledger["logical_failure_budget"], "ledger.logical_failure_budget")
        compiled_exact = ledger["compiled_exact"]
        place_route_validated = ledger["place_route_validated"]
        if not isinstance(compiled_exact, bool) or not isinstance(place_route_validated, bool):
            raise ValueError("compiled_exact and place_route_validated must be boolean")
        sequence_fingerprint = _nonempty(
            ledger["logical_sequence_fingerprint"], "ledger.logical_sequence_fingerprint"
        )
        if not SHA256_RE.fullmatch(sequence_fingerprint):
            raise ValueError("ledger.logical_sequence_fingerprint must be a lowercase SHA-256")
        timing_status = _nonempty(ledger["timing_evidence_status"], "ledger.timing_evidence_status")
        error_status = _nonempty(ledger["error_evidence_status"], "ledger.error_evidence_status")
        _nonempty(ledger["schedule_provenance"], "ledger.schedule_provenance")
        _nonempty(ledger["timing_provenance"], "ledger.timing_provenance")
        _nonempty(ledger["error_model_provenance"], "ledger.error_model_provenance")
    except (KeyError, ValueError) as exc:
        return _result("UNRESOLVED", [str(exc)])
    if l != contract["target_linear_size"]:
        errors.append("ledger linear_size does not match contract target")
    if r != contract["target_trotter_steps"]:
        errors.append("ledger trotter_steps does not match contract target")
    expected_events = r * contract["logical_events_per_trotter_step"]
    if logical_event_count != expected_events:
        errors.append(f"logical_event_count must equal {expected_events}")
    if distance % 2 == 0:
        errors.append("ledger.distance must be odd for the contracted surface-code patch model")
    if not math.isclose(cycle_us, float(contract["cycle_us"]), rel_tol=0.0, abs_tol=1e-15):
        errors.append("ledger cycle_us does not match contract cycle_us")
    if failure_budget > 1:
        errors.append("logical_failure_budget must be in [0,1]")
    if not math.isclose(
        failure_budget,
        float(contract["logical_failure_budget"]),
        rel_tol=0.0,
        abs_tol=1e-15,
    ):
        errors.append("ledger logical failure budget does not match contract failure budget")
    allowed_evidence = set(contract["allowed_evidence_statuses"])
    exact_evidence = set(contract["exact_evidence_statuses"])
    for name, value in (("timing_evidence_status", timing_status), ("error_evidence_status", error_status)):
        if value not in allowed_evidence:
            errors.append(f"{name} is invalid")

    patches = ledger.get("patches")
    patch_map: Dict[str, Mapping[str, Any]] = {}
    if not isinstance(patches, list) or not patches:
        errors.append("patches must be a non-empty list")
        patches = []
    for index, patch in enumerate(patches):
        if not isinstance(patch, Mapping):
            errors.append(f"patch {index} must be an object")
            continue
        try:
            patch_id = _nonempty(patch["patch_id"], f"patch {index}.patch_id")
            role = _nonempty(patch["role"], f"patch {index}.role")
            physical_qubits = _positive_int(patch["physical_qubits"], f"patch {index}.physical_qubits")
        except (KeyError, ValueError) as exc:
            errors.append(str(exc))
            continue
        if patch_id in patch_map:
            errors.append(f"duplicate patch_id {patch_id}")
        if role not in contract["allowed_patch_roles"]:
            errors.append(f"patch {patch_id} has invalid role")
        expected_physical_qubits = 2 * distance * distance - 1
        if physical_qubits != expected_physical_qubits:
            errors.append(
                f"patch {patch_id}.physical_qubits must equal 2d^2-1={expected_physical_qubits}"
            )
        patch_map[patch_id] = {**patch, "physical_qubits": physical_qubits}
    data_count = sum(1 for patch in patch_map.values() if patch.get("role") == "data")
    if data_count != 2 * l * l:
        errors.append(f"expected {2*l*l} data patches, found {data_count}")
    present_roles = {str(patch.get("role")) for patch in patch_map.values()}
    missing_patch_roles = set(contract["required_patch_roles"]) - present_roles
    if missing_patch_roles:
        errors.append("required patch roles are missing: " + ", ".join(sorted(missing_patch_roles)))

    layouts = ledger.get("layouts")
    layout_map: Dict[str, Dict[str, Any]] = {}
    if not isinstance(layouts, list) or not layouts:
        errors.append("layouts must be a non-empty list")
        layouts = []
    for index, layout in enumerate(layouts):
        if not isinstance(layout, Mapping):
            errors.append(f"layout {index} must be an object")
            continue
        try:
            layout_id = _nonempty(layout["layout_id"], f"layout {index}.layout_id")
        except (KeyError, ValueError) as exc:
            errors.append(str(exc))
            continue
        placements = layout.get("placements")
        if not isinstance(placements, list):
            errors.append(f"layout {layout_id}.placements must be a list")
            continue
        placement_map: Dict[str, Mapping[str, Any]] = {}
        occupied_tiles: Set[tuple[int, int]] = set()
        for placement_index, placement in enumerate(placements):
            if not isinstance(placement, Mapping):
                errors.append(f"layout {layout_id} placement {placement_index} must be an object")
                continue
            try:
                patch_id = _nonempty(
                    placement["patch_id"], f"layout {layout_id} placement {placement_index}.patch_id"
                )
                row = _nonnegative_int(placement["row"], f"layout {layout_id}.{patch_id}.row")
                col = _nonnegative_int(placement["col"], f"layout {layout_id}.{patch_id}.col")
                orientation = _nonempty(
                    placement["orientation"], f"layout {layout_id}.{patch_id}.orientation"
                )
                boundaries = placement["available_boundaries"]
                if not isinstance(boundaries, list) or not all(
                    boundary in contract["allowed_boundaries"] for boundary in boundaries
                ):
                    raise ValueError(f"layout {layout_id}.{patch_id}.available_boundaries is invalid")
            except (KeyError, ValueError) as exc:
                errors.append(str(exc))
                continue
            if patch_id not in patch_map:
                errors.append(f"layout {layout_id} references unknown patch {patch_id}")
            if patch_id in placement_map:
                errors.append(f"layout {layout_id} duplicates patch {patch_id}")
            if (row, col) in occupied_tiles:
                errors.append(f"layout {layout_id} has a tile conflict at ({row},{col})")
            if orientation not in contract["allowed_orientations"]:
                errors.append(f"layout {layout_id}.{patch_id} has invalid orientation")
            occupied_tiles.add((row, col))
            placement_map[patch_id] = placement
        if layout_id in layout_map:
            errors.append(f"duplicate layout_id {layout_id}")
        layout_map[layout_id] = {"placements": placement_map}

    intervals = ledger.get("intervals")
    if not isinstance(intervals, list) or not intervals:
        errors.append("intervals must be a non-empty list")
        intervals = []
    expected_start = 0
    active_volume = 0
    peak_physical_qubits = 0
    operation_locations: Dict[str, int] = {}
    operation_kinds: Dict[str, str] = {}
    operation_dependencies: Dict[str, List[str]] = {}
    dependencies: List[tuple[str, str, int]] = []
    covered_events: Set[int] = set()
    event_windows: Dict[int, tuple[int, int, str]] = {}
    seen_operation_kinds: Set[str] = set()
    failure_sum = 0.0
    previous_live_positions: Dict[str, tuple[int, int]] = {}
    all_evidence_exact = timing_status in exact_evidence and error_status in exact_evidence
    for interval_index, interval in enumerate(intervals):
        if not isinstance(interval, Mapping):
            errors.append(f"interval {interval_index} must be an object")
            continue
        try:
            if interval.get("interval_index") != interval_index:
                raise ValueError(f"interval {interval_index}.interval_index must equal list index")
            start = _nonnegative_int(interval["start_cycle"], f"interval {interval_index}.start_cycle")
            duration = _positive_int(interval["duration_cycles"], f"interval {interval_index}.duration_cycles")
            layout_id = _nonempty(interval["layout_id"], f"interval {interval_index}.layout_id")
        except (KeyError, ValueError) as exc:
            errors.append(str(exc))
            continue
        if start != expected_start:
            errors.append(
                f"interval {interval_index} starts at {start}; expected {expected_start} (gap or overlap)"
            )
        expected_start = start + duration
        if layout_id not in layout_map:
            errors.append(f"interval {interval_index} references unknown layout {layout_id}")
            placement_map = {}
        else:
            placement_map = layout_map[layout_id]["placements"]
        try:
            live = _unique_string_list(
                interval.get("live_patch_ids"), f"interval {interval_index}.live_patch_ids"
            )
        except ValueError as exc:
            errors.append(str(exc))
            live = []
        live_set = set(live)
        for patch_id in live:
            if patch_id not in patch_map:
                errors.append(f"interval {interval_index} references unknown live patch {patch_id}")
            if patch_id not in placement_map:
                errors.append(f"interval {interval_index} live patch {patch_id} is not placed")
        required_live_roles = set(contract["required_live_patch_roles"])
        required_live = {
            patch_id
            for patch_id, patch in patch_map.items()
            if patch.get("role") in required_live_roles
        }
        missing_required_live = sorted(required_live - live_set)
        if missing_required_live:
            errors.append(
                f"interval {interval_index} data patches and other required-role patches "
                "must remain live; "
                f"missing {', '.join(missing_required_live)}"
            )
        current_live_positions = {
            patch_id: (placement_map[patch_id]["row"], placement_map[patch_id]["col"])
            for patch_id in live
            if patch_id in placement_map
        }
        for patch_id, position in current_live_positions.items():
            if patch_id in previous_live_positions and previous_live_positions[patch_id] != position:
                errors.append(
                    f"interval {interval_index} moves live patch {patch_id} without a modeled transition"
                )
        previous_live_positions = current_live_positions
        live_qubits = sum(
            patch_map[patch_id]["physical_qubits"] for patch_id in live if patch_id in patch_map
        )
        active_volume += duration * live_qubits
        peak_physical_qubits = max(peak_physical_qubits, live_qubits)
        operations = interval.get("operations")
        if not isinstance(operations, list):
            errors.append(f"interval {interval_index}.operations must be a list")
            operations = []
        resource_windows: Dict[str, List[tuple[int, int, str]]] = {}
        for operation_index, operation in enumerate(operations):
            if not isinstance(operation, Mapping):
                errors.append(f"interval {interval_index} operation {operation_index} must be an object")
                continue
            try:
                operation_id = _nonempty(
                    operation["operation_id"],
                    f"interval {interval_index} operation {operation_index}.operation_id",
                )
                kind = _nonempty(operation["kind"], f"operation {operation_id}.kind")
                evidence_status = _nonempty(
                    operation["evidence_status"], f"operation {operation_id}.evidence_status"
                )
                _nonempty(operation["provenance"], f"operation {operation_id}.provenance")
                failure = _nonnegative(
                    operation["logical_failure_probability"],
                    f"operation {operation_id}.logical_failure_probability",
                )
                if failure > 1:
                    raise ValueError(f"operation {operation_id}.logical_failure_probability must be <= 1")
                operation_start = _nonnegative_int(
                    operation["start_offset_cycles"],
                    f"operation {operation_id}.start_offset_cycles",
                )
                operation_duration = _positive_int(
                    operation["duration_cycles"], f"operation {operation_id}.duration_cycles"
                )
            except (KeyError, ValueError) as exc:
                errors.append(str(exc))
                continue
            operation_end = operation_start + operation_duration
            if operation_end > duration:
                errors.append(f"operation {operation_id} extends beyond its interval")
            if operation_id in operation_locations:
                errors.append(f"duplicate operation_id {operation_id}")
            else:
                operation_locations[operation_id] = interval_index
                operation_kinds[operation_id] = kind
            if kind not in contract["allowed_operation_kinds"]:
                errors.append(f"operation {operation_id} has invalid kind")
            else:
                seen_operation_kinds.add(kind)
            if evidence_status not in allowed_evidence:
                errors.append(f"operation {operation_id} has invalid evidence_status")
            if evidence_status not in exact_evidence:
                all_evidence_exact = False
            failure_sum += failure
            try:
                participants = _unique_string_list(
                    operation.get("participant_patch_ids"),
                    f"operation {operation_id}.participant_patch_ids",
                )
            except ValueError as exc:
                errors.append(str(exc))
                participants = []
            try:
                corridors = _unique_string_list(
                    operation.get("corridor_patch_ids"),
                    f"operation {operation_id}.corridor_patch_ids",
                )
            except ValueError as exc:
                errors.append(str(exc))
                corridors = []
            for patch_ids in (participants, corridors):
                for patch_id in patch_ids:
                    if patch_id not in live_set:
                        errors.append(f"operation {operation_id} references non-live patch {patch_id}")
            if set(participants) & set(corridors):
                errors.append(f"operation {operation_id} participants and corridors must be disjoint")
            allowed_corridor_roles = set(contract["allowed_corridor_patch_roles"])
            for patch_id in corridors:
                if patch_id in patch_map and patch_map[patch_id].get("role") not in allowed_corridor_roles:
                    errors.append(f"operation {operation_id} corridor patch {patch_id} has invalid role")
            path_ids = participants + corridors
            participant_roles = {
                str(patch_map[patch_id].get("role"))
                for patch_id in participants
                if patch_id in patch_map
            }
            if kind in {"ladder_joint_measurement", "distill"} and operation_duration < distance:
                errors.append(
                    f"operation {operation_id} duration must be at least distance={distance}"
                )
            if kind == "ladder_joint_measurement":
                if len(participants) < 2 or "data" not in participant_roles or not (
                    {"auxiliary", "routing"} & participant_roles
                ):
                    errors.append(
                        f"operation {operation_id} ladder measurement needs data and auxiliary/routing participants"
                    )
            elif kind == "rotation" and "data" not in participant_roles:
                errors.append(f"operation {operation_id} rotation needs a data participant")
            elif kind == "distill" and "factory" not in participant_roles:
                errors.append(f"operation {operation_id} distill needs a factory participant")
            elif kind == "buffer" and not {"factory", "buffer"}.issubset(participant_roles):
                errors.append(f"operation {operation_id} buffer needs factory and buffer participants")
            elif kind == "inject" and not {"buffer", "data"}.issubset(participant_roles):
                errors.append(f"operation {operation_id} inject needs buffer and data participants")
            if len(participants) >= 2 and not _connected_patch_path(path_ids, placement_map):
                errors.append(
                    f"operation {operation_id} participant/corridor tiles must form a contiguous path"
                )
            for patch_id in set(path_ids):
                for other_start, other_end, other_operation in resource_windows.get(patch_id, []):
                    if operation_start < other_end and other_start < operation_end:
                        errors.append(
                            f"operation {operation_id} overlaps {other_operation} on patch {patch_id}"
                        )
                resource_windows.setdefault(patch_id, []).append(
                    (operation_start, operation_end, operation_id)
                )
            required_boundaries = operation.get("required_boundaries")
            if not isinstance(required_boundaries, list):
                errors.append(f"operation {operation_id}.required_boundaries must be a list")
                required_boundaries = []
            boundary_patch_ids: Set[str] = set()
            for requirement in required_boundaries:
                if not isinstance(requirement, Mapping):
                    errors.append(f"operation {operation_id} has invalid boundary requirement")
                    continue
                patch_id = requirement.get("patch_id")
                boundary = requirement.get("boundary")
                if not isinstance(patch_id, str) or not patch_id.strip():
                    errors.append(f"operation {operation_id} has invalid boundary patch_id")
                    continue
                if patch_id not in set(path_ids):
                    errors.append(
                        f"operation {operation_id} boundary patch {patch_id} is not a participant/corridor"
                    )
                    continue
                boundary_patch_ids.add(patch_id)
                placement = placement_map.get(patch_id, {})
                if boundary not in placement.get("available_boundaries", []):
                    errors.append(
                        f"operation {operation_id} requires unavailable boundary {boundary} on {patch_id}"
                    )
                    continue
                if boundary in BOUNDARY_DELTAS:
                    row_delta, col_delta = BOUNDARY_DELTAS[boundary]
                    facing_tile = (
                        placement.get("row", -2) + row_delta,
                        placement.get("col", -2) + col_delta,
                    )
                    path_tiles = {
                        (placement_map[other]["row"], placement_map[other]["col"])
                        for other in path_ids
                        if other != patch_id and other in placement_map
                    }
                    if facing_tile not in path_tiles:
                        errors.append(
                            f"operation {operation_id} boundary {boundary} on {patch_id} "
                            "does not face another path patch"
                        )
            if len(participants) >= 2 and not set(participants).issubset(boundary_patch_ids):
                errors.append(
                    f"operation {operation_id} must declare a facing boundary for every participant"
                )
            event_ids = operation.get("logical_event_ids")
            if not isinstance(event_ids, list) or not all(
                isinstance(event, int) and not isinstance(event, bool) for event in event_ids
            ):
                errors.append(
                    f"operation {operation_id}.logical_event_ids must be a list of integers"
                )
            else:
                if len(event_ids) != len(set(event_ids)):
                    errors.append(f"operation {operation_id}.logical_event_ids must be unique")
                if len(event_ids) > contract["max_logical_events_per_operation"]:
                    errors.append(
                        f"operation {operation_id} exceeds max_logical_events_per_operation"
                    )
                if event_ids and kind in contract["non_logical_event_operation_kinds"]:
                    errors.append(f"operation {operation_id} kind cannot bind logical events")
                if event_ids and kind not in contract["logical_event_operation_kinds"]:
                    errors.append(f"operation {operation_id} kind cannot implement logical events")
                if event_ids and not participants:
                    errors.append(f"operation {operation_id} binds events without participants")
                for event in event_ids:
                    if not 0 <= event < logical_event_count:
                        errors.append(f"operation {operation_id} has out-of-range logical event {event}")
                    elif event in covered_events:
                        errors.append(f"logical event {event} is bound by more than one operation")
                    else:
                        covered_events.add(event)
                        event_windows[event] = (
                            start + operation_start,
                            start + operation_end,
                            operation_id,
                        )
            depends_on = operation.get("depends_on")
            try:
                depends_on = _unique_string_list(
                    depends_on, f"operation {operation_id}.depends_on"
                )
            except ValueError as exc:
                errors.append(str(exc))
                depends_on = []
            operation_dependencies[operation_id] = depends_on
            dependencies.extend((operation_id, dep, interval_index) for dep in depends_on)
    for operation_id, dependency, interval_index in dependencies:
        dependency_interval = operation_locations.get(dependency)
        if dependency_interval is None:
            errors.append(f"operation {operation_id} depends on unknown operation {dependency}")
        elif dependency_interval >= interval_index:
            errors.append(f"operation {operation_id} dependency {dependency} is not in a prior interval")
    prerequisite_kinds = {
        "buffer": {"distill"},
        "inject": {"buffer"},
        "rotation": {"inject"},
    }
    for operation_id, kind in operation_kinds.items():
        if kind not in prerequisite_kinds:
            continue
        operation_interval = operation_locations[operation_id]
        if not any(
            operation_kinds.get(dependency) in prerequisite_kinds[kind]
            and operation_locations.get(dependency, operation_interval) < operation_interval
            for dependency in operation_dependencies.get(operation_id, [])
        ):
            errors.append(
                f"{kind} operation {operation_id} must depend on a prior "
                f"{'/'.join(sorted(prerequisite_kinds[kind]))} operation"
            )
    missing_operation_kinds = set(contract["required_operation_kinds"]) - seen_operation_kinds
    if missing_operation_kinds:
        errors.append(
            "required operation kinds are missing: " + ", ".join(sorted(missing_operation_kinds))
        )
    expected_event_set = set(range(logical_event_count))
    if covered_events != expected_event_set:
        missing = len(expected_event_set - covered_events)
        errors.append(f"logical event coverage is incomplete; {missing} events missing")
    for event in range(logical_event_count - 1):
        if event not in event_windows or event + 1 not in event_windows:
            continue
        current_end = event_windows[event][1]
        next_start = event_windows[event + 1][0]
        if current_end > next_start:
            errors.append(
                f"logical event {event} must finish before logical event {event + 1} starts"
            )
    if 0 in event_windows:
        first_event_operation = event_windows[0][2]
        if not any(
            operation_kinds.get(dependency) == "rotation"
            and operation_locations.get(dependency, operation_locations[first_event_operation])
            < operation_locations[first_event_operation]
            for dependency in operation_dependencies.get(first_event_operation, [])
        ):
            errors.append("logical event 0 must depend on a prior rotation operation")
    if failure_sum > failure_budget + 1e-15:
        errors.append("logical failure union bound exceeds logical_failure_budget")
    if errors:
        return {
            **_result("UNRESOLVED", errors, warnings),
            "planning_total_cycles": None,
            "planning_active_physical_qubit_cycles": None,
            "failure_union_bound": failure_sum,
        }
    if not compiled_exact:
        warnings.append("compiled_exact=false")
    if not place_route_validated:
        warnings.append("place_route_validated=false")
    if not all_evidence_exact:
        warnings.append("derived or assumed evidence remains")
    status = (
        "COMPLETE"
        if compiled_exact and place_route_validated and all_evidence_exact
        else "BOOKKEEPING_CLOSED_ESTIMATE"
    )
    complete = status == "COMPLETE"
    return {
        "route": "dynamic_jw_surface_code",
        "status": status,
        "errors": [],
        "warnings": warnings,
        "linear_size": l,
        "trotter_steps": r,
        "logical_sequence_fingerprint": sequence_fingerprint,
        "total_cycles": expected_start,
        "total_time_us": expected_start * cycle_us,
        "peak_physical_qubits": peak_physical_qubits,
        "failure_union_bound": failure_sum,
        "planning_total_cycles": expected_start,
        "planning_active_physical_qubit_cycles": active_volume,
        "complete_total_cycles": expected_start if complete else None,
        "complete_active_physical_qubit_cycles": active_volume if complete else None,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--contract", type=Path, required=True)
    parser.add_argument("--ledger", type=Path, required=True)
    parser.add_argument("--format", choices=("json", "markdown"), default="json")
    args = parser.parse_args()
    with args.contract.open(encoding="utf-8") as handle:
        contract = json.load(handle)
    with args.ledger.open(encoding="utf-8") as handle:
        ledger = json.load(handle)
    result = validate_ledger(contract, ledger)
    if args.format == "markdown":
        print(f"# Surface place-and-route ledger: {result['status']}\n")
        print(f"- Planning cycles: `{result.get('planning_total_cycles')}`")
        print(
            "- Planning active physical-qubit-cycles: "
            f"`{result.get('planning_active_physical_qubit_cycles')}`"
        )
        for error in result.get("errors", []):
            print(f"\nError: {error}")
        for warning in result.get("warnings", []):
            print(f"\nWarning: {warning}")
    else:
        print(json.dumps(result, indent=2, sort_keys=True))
    sys.exit(0 if result["status"] == "COMPLETE" else 1)


if __name__ == "__main__":
    main()
