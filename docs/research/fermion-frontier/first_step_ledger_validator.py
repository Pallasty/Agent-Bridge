#!/usr/bin/env python3
"""Validate first-step and timing ledgers without upgrading approximations to exact totals."""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional


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


def _nonnegative_int(value: Any, name: str, allow_null: bool = False) -> Optional[int]:
    if value is None and allow_null:
        return None
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{name} must be a non-negative integer")
    return value


def _positive_int(value: Any, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{name} must be a positive integer")
    return value


def _nonempty(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string")
    return value


def _optional_timing(value: Any, name: str) -> Optional[float]:
    if value is None:
        return None
    return _nonnegative(value, name)


def validate_contract(contract: Mapping[str, Any]) -> List[str]:
    errors: List[str] = []
    if contract.get("schema_version") != 1:
        errors.append("contract schema_version must be 1")
    if not isinstance(contract.get("workload_fingerprint"), str):
        errors.append("contract workload_fingerprint must be a string")
    routes = contract.get("required_routes")
    if not isinstance(routes, list) or not routes or not all(isinstance(x, str) for x in routes):
        errors.append("contract required_routes must be a non-empty list of strings")
    return errors


def _route_result(route_name: str, route: Mapping[str, Any], contract: Mapping[str, Any]) -> Dict[str, Any]:
    errors: List[str] = []
    warnings: List[str] = []
    try:
        r = _positive_int(route["R"], f"{route_name}.R")
        steady_count = _nonnegative_int(route["steady_count_per_step"], f"{route_name}.steady_count_per_step")
        steady_depth = _nonnegative_int(route["steady_depth_per_step"], f"{route_name}.steady_depth_per_step")
        extra_count = _nonnegative_int(route.get("first_step_extra_count"), f"{route_name}.first_step_extra_count", True)
        extra_depth = _nonnegative_int(route.get("first_step_extra_depth"), f"{route_name}.first_step_extra_depth", True)
        compiled_exact = route["compiled_exact"]
        if not isinstance(compiled_exact, bool):
            raise ValueError(f"{route_name}.compiled_exact must be boolean")
        provenance = _nonempty(route["provenance"], f"{route_name}.provenance")
    except (KeyError, ValueError) as exc:
        return {
            "route": route_name,
            "status": "UNRESOLVED",
            "errors": [str(exc)],
            "warnings": [],
            "complete_count": None,
            "complete_depth": None,
            "complete_circuit_us": None,
        }

    timing = route.get("timing", {})
    if not isinstance(timing, Mapping):
        errors.append("timing must be an object")
        timing = {}
    cnot_layer = None
    non_cnot = None
    extra_non_cnot = None
    for key, target in (
        ("cnot_layer_us", "cnot_layer"),
        ("non_cnot_us_per_steady_step", "non_cnot"),
        ("first_step_extra_non_cnot_us", "extra_non_cnot"),
    ):
        try:
            value = _optional_timing(timing.get(key), f"{route_name}.timing.{key}")
        except ValueError as exc:
            errors.append(str(exc))
            value = None
        if target == "cnot_layer":
            cnot_layer = value
        elif target == "non_cnot":
            non_cnot = value
        else:
            extra_non_cnot = value
    timing_provenance = timing.get("timing_provenance")
    if timing_provenance is None or not isinstance(timing_provenance, str) or not timing_provenance.strip():
        errors.append(f"{route_name}.timing.timing_provenance must be a non-empty string")

    bookkeeping_complete = (
        extra_count is not None
        and extra_depth is not None
        and cnot_layer is not None
        and non_cnot is not None
        and extra_non_cnot is not None
    )
    complete_count = None if extra_count is None else r * steady_count + extra_count
    complete_depth = None if extra_depth is None else r * steady_depth + extra_depth
    planning_time = None
    if bookkeeping_complete:
        planning_time = complete_depth * cnot_layer + r * non_cnot + extra_non_cnot
    if not bookkeeping_complete:
        status = "UNRESOLVED"
        warnings.append("first-step count/depth or route timing is incomplete")
    elif errors:
        status = "UNRESOLVED"
    elif not compiled_exact:
        status = "BOOKKEEPING_CLOSED_ESTIMATE"
        warnings.append("steady-state inputs are leading/candidate values, not exact compiled resources")
    else:
        status = "COMPLETE"
    return {
        "route": route_name,
        "status": status,
        "errors": errors,
        "warnings": warnings,
        "provenance": provenance,
        "R": r,
        "steady_count_per_step": steady_count,
        "steady_depth_per_step": steady_depth,
        "first_step_extra_count": extra_count,
        "first_step_extra_depth": extra_depth,
        "compiled_exact": compiled_exact,
        "complete_count": complete_count,
        "complete_depth": complete_depth,
        "planning_circuit_us": planning_time,
        "complete_circuit_us": planning_time if status == "COMPLETE" else None,
    }


def validate_ledger(contract: Mapping[str, Any], ledger: Mapping[str, Any]) -> Dict[str, Any]:
    errors = validate_contract(contract)
    if ledger.get("schema_version") != 1:
        errors.append("ledger schema_version must be 1")
    if ledger.get("workload_fingerprint") != contract.get("workload_fingerprint"):
        errors.append("ledger workload_fingerprint does not match contract")
    routes = ledger.get("routes")
    if not isinstance(routes, Mapping):
        errors.append("ledger routes must be an object")
        routes = {}
    if errors:
        return {"status": "INVALID_SCHEMA", "errors": errors, "routes": {}}
    results: Dict[str, Any] = {}
    missing: List[str] = []
    for route_name in contract["required_routes"]:
        if route_name not in routes:
            missing.append(route_name)
        elif not isinstance(routes[route_name], Mapping):
            results[route_name] = {"route": route_name, "status": "UNRESOLVED", "errors": ["route entry must be an object"]}
        else:
            results[route_name] = _route_result(route_name, routes[route_name], contract)
    if missing:
        errors.append(f"missing required routes: {', '.join(missing)}")
    if any(result.get("status") != "COMPLETE" for result in results.values()):
        errors.append("one or more routes are not COMPLETE")
    return {
        "status": "COMPLETE" if not errors else "UNRESOLVED",
        "errors": errors,
        "routes": results,
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
        print(f"# First-step ledger: {result['status']}\n")
        for name, route in result.get("routes", {}).items():
            print(f"- `{name}`: {route['status']}")
        for error in result.get("errors", []):
            print(f"\nError: {error}")
    else:
        print(json.dumps(result, indent=2, sort_keys=True))
    sys.exit(0 if result["status"] != "INVALID_SCHEMA" else 1)


if __name__ == "__main__":
    main()
