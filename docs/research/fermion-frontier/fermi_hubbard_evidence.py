#!/usr/bin/env python3
"""Validate the matched Fermi--Hubbard evidence manifest.

This is an orchestration layer, not a source of resource estimates. It joins
the term-sequence, first-step resource, and common-R convergence validators and
checks that their route names, workload fingerprint, L, and R agree. Empty
templates remain unresolved; synthetic fixtures must never be read as hardware
or compiler evidence.
"""

from __future__ import annotations

import argparse
import copy
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional


HERE = Path(__file__).resolve().parent


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load {name} from {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


TERM = _load_module("term_order_cross_route", HERE / "term_order_cross_route.py")
FIRST_STEP = _load_module("first_step_ledger_validator", HERE / "first_step_ledger_validator.py")
CONVERGENCE = _load_module("fermi_hubbard_convergence", HERE / "fermi_hubbard_convergence.py")


def _nonempty_string(value: Any, name: str, errors: List[str]) -> None:
    if not isinstance(value, str) or not value.strip():
        errors.append(f"{name} must be a non-empty string")


def validate_contract(contract: Mapping[str, Any]) -> List[str]:
    errors: List[str] = []
    if contract.get("schema_version") != 1:
        errors.append("evidence contract schema_version must be 1")
    _nonempty_string(contract.get("workload_fingerprint"), "workload_fingerprint", errors)
    for key in ("target_linear_size", "target_trotter_steps"):
        value = contract.get(key)
        if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
            errors.append(f"{key} must be a positive integer")
    required = contract.get("required_routes")
    if not isinstance(required, list) or not required or not all(
        isinstance(route, str) and route for route in required
    ):
        errors.append("required_routes must be a non-empty list of route names")
        required = []
    route_map = contract.get("route_map")
    if not isinstance(route_map, Mapping):
        errors.append("route_map must be an object keyed by required route")
        route_map = {}
    if set(route_map) != set(required):
        errors.append("route_map keys must exactly match required_routes")
    for route in required:
        link = route_map.get(route)
        if not isinstance(link, Mapping):
            errors.append(f"route_map.{route} must be an object")
            continue
        _nonempty_string(link.get("term_route"), f"route_map.{route}.term_route", errors)
        _nonempty_string(
            link.get("convergence_route"), f"route_map.{route}.convergence_route", errors
        )
    return errors


def _component_schema_status(result: Mapping[str, Any]) -> bool:
    return result.get("status") == "INVALID_SCHEMA"


def validate_manifest(
    contract: Mapping[str, Any],
    manifest: Mapping[str, Any],
    term_contract: Mapping[str, Any],
    first_step_contract: Mapping[str, Any],
) -> Dict[str, Any]:
    errors = validate_contract(contract)
    if manifest.get("schema_version") != 1:
        errors.append("manifest schema_version must be 1")
    if manifest.get("workload_fingerprint") != contract.get("workload_fingerprint"):
        errors.append("manifest workload_fingerprint does not match evidence contract")
    if errors:
        return {"status": "INVALID_SCHEMA", "errors": errors, "components": {}}

    required = contract["required_routes"]
    route_map = contract["route_map"]
    component_errors: List[str] = []

    if term_contract.get("required_routes") != [route_map[route]["term_route"] for route in required]:
        component_errors.append("term contract required_routes do not match evidence route map")
    term_manifest = manifest.get("term_order")
    if not isinstance(term_manifest, Mapping):
        component_errors.append("manifest term_order must be an object")
        term_manifest = {}
    else:
        if term_manifest.get("required_routes") != term_contract.get("required_routes"):
            component_errors.append("manifest term_order.required_routes do not match term contract")
        if term_manifest.get("workload_fingerprint") not in (
            None,
            contract.get("workload_fingerprint"),
        ):
            component_errors.append("manifest term_order workload_fingerprint does not match")
    term_result = TERM.compare_routes(term_contract, term_manifest)

    if first_step_contract.get("workload_fingerprint") != contract.get("workload_fingerprint"):
        component_errors.append("first-step contract workload_fingerprint does not match")
    if first_step_contract.get("required_routes") != required:
        component_errors.append("first-step contract required_routes do not match evidence contract")
    first_step_manifest = manifest.get("first_step")
    if not isinstance(first_step_manifest, Mapping):
        component_errors.append("manifest first_step must be an object")
        first_step_manifest = {}
    first_step_result = FIRST_STEP.validate_ledger(first_step_contract, first_step_manifest)

    convergence_manifest = manifest.get("convergence")
    if not isinstance(convergence_manifest, Mapping):
        component_errors.append("manifest convergence must be an object")
        convergence_manifest = {}
    convergence_workload = convergence_manifest.get("workload", {})
    if not isinstance(convergence_workload, Mapping) or convergence_workload.get(
        "hamiltonian_fingerprint"
    ) != contract.get("workload_fingerprint"):
        component_errors.append("convergence workload fingerprint does not match evidence contract")
    convergence_routes = [route_map[route]["convergence_route"] for route in required]
    unique_convergence_routes = list(dict.fromkeys(convergence_routes))
    core_convergence_manifest = copy.deepcopy(dict(convergence_manifest))
    core_convergence_manifest["required_routes"] = unique_convergence_routes
    convergence_result = CONVERGENCE.assess_manifest(core_convergence_manifest)

    coherence_errors: List[str] = []
    term_exports = term_manifest.get("exports", {})
    first_routes = first_step_manifest.get("routes", {})
    if isinstance(term_exports, Mapping) and isinstance(first_routes, Mapping):
        for route in required:
            term_route = route_map[route]["term_route"]
            if term_route not in term_exports or route not in first_routes:
                continue
            term_export = term_exports[term_route]
            ledger_route = first_routes[route]
            if not isinstance(term_export, Mapping) or not isinstance(ledger_route, Mapping):
                continue
            if isinstance(term_export.get("linear_size"), int) and term_export["linear_size"] != contract[
                "target_linear_size"
            ]:
                coherence_errors.append(
                    f"{route}: term export linear_size does not match target_linear_size"
                )
            if isinstance(term_export.get("trotter_steps"), int) and isinstance(
                ledger_route.get("R"), int
            ):
                if term_export["trotter_steps"] != ledger_route["R"]:
                    coherence_errors.append(f"{route}: term export trotter_steps does not match ledger R")
            if isinstance(ledger_route.get("R"), int) and ledger_route["R"] != contract[
                "target_trotter_steps"
            ]:
                coherence_errors.append(f"{route}: ledger R does not match target_trotter_steps")

    if component_errors:
        errors.extend(component_errors)
    if coherence_errors:
        errors.extend(coherence_errors)

    component_statuses = {
        "term_order": term_result.get("status"),
        "first_step": first_step_result.get("status"),
        "convergence": convergence_result.get("status"),
    }
    if any(_component_schema_status(result) for result in (term_result, first_step_result, convergence_result)):
        status = "INVALID_SCHEMA"
    elif coherence_errors:
        status = "INCONSISTENT"
    elif term_result.get("status") == "MISMATCH":
        status = "MISMATCH"
    elif all(
        (
            term_result.get("status") == "MATCHED",
            first_step_result.get("status") == "COMPLETE",
            convergence_result.get("status") == "READY_FOR_COMMON_R",
        )
    ):
        status = "READY_FOR_BENCHMARK"
    else:
        status = "UNRESOLVED"
    return {
        "status": status,
        "errors": errors,
        "components": {
            "term_order": term_result,
            "first_step": first_step_result,
            "convergence": convergence_result,
        },
        "component_statuses": component_statuses,
        "coherence_errors": coherence_errors,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--contract", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--term-contract", type=Path, required=True)
    parser.add_argument("--first-step-contract", type=Path, required=True)
    parser.add_argument("--format", choices=("json", "markdown"), default="json")
    args = parser.parse_args()
    with args.contract.open(encoding="utf-8") as handle:
        contract = json.load(handle)
    with args.manifest.open(encoding="utf-8") as handle:
        manifest = json.load(handle)
    with args.term_contract.open(encoding="utf-8") as handle:
        term_contract = json.load(handle)
    with args.first_step_contract.open(encoding="utf-8") as handle:
        first_step_contract = json.load(handle)
    result = validate_manifest(contract, manifest, term_contract, first_step_contract)
    if args.format == "markdown":
        print(f"# Fermi-Hubbard evidence manifest: {result['status']}\n")
        for name, status in result.get("component_statuses", {}).items():
            print(f"- `{name}`: {status}")
        for error in result.get("errors", []):
            print(f"\nError: {error}")
    else:
        print(json.dumps(result, indent=2, sort_keys=True))
    sys.exit(0 if result["status"] == "READY_FOR_BENCHMARK" else 1)


if __name__ == "__main__":
    main()
