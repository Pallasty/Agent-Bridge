#!/usr/bin/env python3
"""Validate the occurrence-level native matching transition ledger."""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Any, Dict, List, Mapping


CLASS_COUNTS = {
    "H1_half": lambda r: 2,
    "H2_half": lambda r: 2 * r,
    "H3_half": lambda r: 2 * r,
    "H1_full": lambda r: r - 1,
    "H4_full": lambda r: r,
    "HU_half": lambda r: 2 * r,
}
CLASS_GROUPS = {
    "H1_half": "H1",
    "H2_half": "H2",
    "H3_half": "H3",
    "H1_full": "H1",
    "H4_full": "H4",
    "HU_half": "HU",
}
MEASUREMENT_STATUSES = {"measured", "derived", "assumed"}
TIMING_FIELDS = ("move_us", "gate_us", "cooling_echo_us", "return_us", "other_us")
TIMING_TOLERANCE_US = 1e-9


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


def _unit_interval(value: Any, name: str) -> float:
    value = _finite(value, name)
    if not 0 <= value <= 1:
        raise ValueError(f"{name} must be in [0,1]")
    return value


def _nonempty(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string")
    return value


def validate_contract(contract: Mapping[str, Any]) -> List[str]:
    errors: List[str] = []
    if contract.get("schema_version") != 1:
        errors.append("contract schema_version must be 1")
    _nonempty_value = contract.get("workload_fingerprint")
    if not isinstance(_nonempty_value, str) or not _nonempty_value.strip():
        errors.append("contract workload_fingerprint must be a non-empty string")
    if contract.get("route") != "native_fermions":
        errors.append("contract route must be native_fermions")
    formulas = contract.get("class_count_formula")
    if not isinstance(formulas, Mapping) or set(formulas) != set(CLASS_COUNTS):
        errors.append("contract class_count_formula must cover all native occurrence classes")
    return errors


def _unresolved(route: str, errors: List[str], warnings: List[str] | None = None) -> Dict[str, Any]:
    return {
        "route": route,
        "status": "UNRESOLVED",
        "errors": errors,
        "warnings": warnings or [],
        "occurrence_count": None,
        "expected_occurrence_count": None,
        "planning_circuit_us": None,
        "complete_circuit_us": None,
    }


def validate_ledger(contract: Mapping[str, Any], ledger: Mapping[str, Any]) -> Dict[str, Any]:
    schema_errors = validate_contract(contract)
    if ledger.get("schema_version") != 1:
        schema_errors.append("ledger schema_version must be 1")
    if ledger.get("workload_fingerprint") != contract.get("workload_fingerprint"):
        schema_errors.append("ledger workload_fingerprint does not match contract")
    if ledger.get("route") != contract.get("route"):
        schema_errors.append("ledger route does not match contract")
    if schema_errors:
        return {"status": "INVALID_SCHEMA", "errors": schema_errors, "routes": {}}
    try:
        l = ledger["linear_size"]
        if isinstance(l, bool) or not isinstance(l, int) or l < 3:
            raise ValueError("ledger linear_size must be an integer >= 3")
        r = ledger["trotter_steps"]
        if isinstance(r, bool) or not isinstance(r, int) or r <= 0:
            raise ValueError("ledger trotter_steps must be a positive integer")
        compiled_exact = ledger["compiled_exact"]
        if not isinstance(compiled_exact, bool):
            raise ValueError("ledger compiled_exact must be boolean")
        timing_provenance = _nonempty(ledger["timing_provenance"], "ledger.timing_provenance")
    except (KeyError, ValueError) as exc:
        return _unresolved("native_fermions", [str(exc)])

    occurrences = ledger.get("occurrences")
    if not isinstance(occurrences, list):
        return _unresolved("native_fermions", ["ledger occurrences must be a list"])
    expected_counts = {name: formula(r) for name, formula in CLASS_COUNTS.items()}
    expected_total = sum(expected_counts.values())
    route_errors: List[str] = []
    route_warnings: List[str] = []
    class_counts = {name: 0 for name in CLASS_COUNTS}
    total_us = 0.0
    component_totals = {field: 0.0 for field in TIMING_FIELDS}
    total_move_legs = 0
    max_distance_um = 0.0
    measured_all = True
    for index, occurrence in enumerate(occurrences):
        if not isinstance(occurrence, Mapping):
            route_errors.append(f"occurrence {index} must be an object")
            continue
        try:
            if occurrence.get("occurrence_index") != index:
                raise ValueError(f"occurrence {index}.occurrence_index must equal its list index")
            occurrence_class = _nonempty(occurrence["class"], f"occurrence {index}.class")
            if occurrence_class not in CLASS_COUNTS:
                raise ValueError(f"occurrence {index}.class is unknown")
            if occurrence.get("group") != CLASS_GROUPS[occurrence_class]:
                raise ValueError(f"occurrence {index}.group does not match class")
            _nonempty(occurrence["incoming_layout_id"], f"occurrence {index}.incoming_layout_id")
            _nonempty(occurrence["outgoing_layout_id"], f"occurrence {index}.outgoing_layout_id")
            move_legs = occurrence["move_legs"]
            if isinstance(move_legs, bool) or not isinstance(move_legs, int) or move_legs < 0:
                raise ValueError(f"occurrence {index}.move_legs must be a non-negative integer")
            distance = _nonnegative(occurrence["move_distance_um"], f"occurrence {index}.move_distance_um")
            parts = {
                field: _nonnegative(occurrence[field], f"occurrence {index}.{field}")
                for field in TIMING_FIELDS
            }
            transition_us = _nonnegative(occurrence["transition_us"], f"occurrence {index}.transition_us")
            if abs(transition_us - sum(parts.values())) > TIMING_TOLERANCE_US:
                raise ValueError(f"occurrence {index}.transition_us does not equal timing components")
            loss_rate = _unit_interval(occurrence["loss_rate"], f"occurrence {index}.loss_rate")
            leakage_rate = _unit_interval(occurrence["leakage_rate"], f"occurrence {index}.leakage_rate")
            measurement_status = occurrence["measurement_status"]
            if measurement_status not in MEASUREMENT_STATUSES:
                raise ValueError(f"occurrence {index}.measurement_status is invalid")
            _nonempty(occurrence["provenance"], f"occurrence {index}.provenance")
        except (KeyError, ValueError) as exc:
            route_errors.append(str(exc))
            continue
        class_counts[occurrence_class] += 1
        total_us += transition_us
        total_move_legs += move_legs
        max_distance_um = max(max_distance_um, distance)
        for field, value in parts.items():
            component_totals[field] += value
        if measurement_status != "measured":
            measured_all = False
    if len(occurrences) != expected_total:
        route_errors.append(f"expected {expected_total} occurrences, found {len(occurrences)}")
    for occurrence_class, expected in expected_counts.items():
        if class_counts[occurrence_class] != expected:
            route_errors.append(
                f"class {occurrence_class}: expected {expected}, found {class_counts[occurrence_class]}"
            )
    if route_errors:
        return {
            "route": "native_fermions",
            "status": "UNRESOLVED",
            "errors": route_errors,
            "warnings": route_warnings,
            "linear_size": l,
            "trotter_steps": r,
            "occurrence_count": len(occurrences),
            "expected_occurrence_count": expected_total,
            "class_counts": class_counts,
            "expected_class_counts": expected_counts,
            "planning_circuit_us": None,
            "complete_circuit_us": None,
        }
    if not measured_all:
        route_warnings.append("at least one occurrence is derived or assumed rather than measured")
    if not compiled_exact:
        route_warnings.append("compiled_exact=false; timing is bookkeeping-closed but not exact compiled evidence")
    status = "COMPLETE" if compiled_exact and measured_all else "BOOKKEEPING_CLOSED_ESTIMATE"
    return {
        "route": "native_fermions",
        "status": status,
        "errors": [],
        "warnings": route_warnings,
        "linear_size": l,
        "trotter_steps": r,
        "timing_provenance": timing_provenance,
        "occurrence_count": len(occurrences),
        "expected_occurrence_count": expected_total,
        "class_counts": class_counts,
        "expected_class_counts": expected_counts,
        "component_totals_us": component_totals,
        "total_move_legs": total_move_legs,
        "max_move_distance_um": max_distance_um,
        "planning_circuit_us": total_us,
        "complete_circuit_us": total_us if status == "COMPLETE" else None,
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
        print(f"# Native transition ledger: {result['status']}\n")
        print(f"- Occurrences: `{result.get('occurrence_count')}/{result.get('expected_occurrence_count')}`")
        if result.get("planning_circuit_us") is not None:
            print(f"- Planning circuit time (us): `{result['planning_circuit_us']}`")
        for error in result.get("errors", []):
            print(f"\nError: {error}")
        for warning in result.get("warnings", []):
            print(f"\nWarning: {warning}")
    else:
        print(json.dumps(result, indent=2, sort_keys=True))
    sys.exit(0 if result["status"] == "COMPLETE" else 1)


if __name__ == "__main__":
    main()
