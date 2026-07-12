#!/usr/bin/env python3
"""Validate the matched Fermi--Hubbard evidence manifest.

This is an orchestration layer, not a source of resource estimates. It joins
the term-sequence, first-step resource, native-transition, surface place-and-route,
and dual-observable target-R validators and checks that their identities, L, R,
and preregistered convergence policy agree. Empty templates remain unresolved;
synthetic fixtures must never be read as hardware or compiler evidence.
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
NATIVE = _load_module("native_transition_validator", HERE / "native_transition_validator.py")
SURFACE = _load_module("surface_place_route_validator", HERE / "surface_place_route_validator.py")
CONVERGENCE = _load_module("fermi_hubbard_convergence", HERE / "fermi_hubbard_convergence.py")


def _nonempty_string(value: Any, name: str, errors: List[str]) -> None:
    if not isinstance(value, str) or not value.strip():
        errors.append(f"{name} must be a non-empty string")


def validate_contract(contract: Mapping[str, Any]) -> List[str]:
    errors: List[str] = []
    surface_link: Optional[Mapping[str, Any]] = None
    if contract.get("schema_version") != 1:
        errors.append("evidence contract schema_version must be 1")
    _nonempty_string(contract.get("workload_fingerprint"), "workload_fingerprint", errors)
    for key in ("target_linear_size", "target_trotter_steps"):
        value = contract.get(key)
        if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
            errors.append(f"{key} must be a positive integer")
    convergence_policy = contract.get("convergence_workload_policy")
    if not isinstance(convergence_policy, Mapping):
        errors.append("convergence_workload_policy must be an object")
    else:
        policy_probe = {
            "schema_version": 2,
            "workload": copy.deepcopy(dict(convergence_policy)),
            "references": None,
            "required_routes": ["contract_policy_probe"],
            "routes": {},
        }
        errors.extend(
            f"convergence_workload_policy: {error}"
            for error in CONVERGENCE.validate_manifest(policy_probe)
        )
        if convergence_policy.get("target_R") != contract.get("target_trotter_steps"):
            errors.append(
                "convergence_workload_policy.target_R must match target_trotter_steps"
            )
        if convergence_policy.get("hamiltonian_fingerprint") != contract.get(
            "workload_fingerprint"
        ):
            errors.append(
                "convergence_workload_policy hamiltonian_fingerprint must match workload_fingerprint"
            )
    if contract.get("native_transition_required") is not True:
        errors.append("native_transition_required must be true")
    if contract.get("surface_place_route_required") is not True:
        errors.append("surface_place_route_required must be true")
    physical_route_map = contract.get("physical_route_map")
    if not isinstance(physical_route_map, Mapping):
        errors.append("physical_route_map must be an object")
    else:
        surface_link = physical_route_map.get("surface_place_route")
        if not isinstance(surface_link, Mapping):
            errors.append("physical_route_map.surface_place_route must be an object")
        else:
            for key in ("route", "term_route", "convergence_route"):
                _nonempty_string(
                    surface_link.get(key),
                    f"physical_route_map.surface_place_route.{key}",
                    errors,
                )
    required = contract.get("required_routes")
    if not isinstance(required, list) or not required or not all(
        isinstance(route, str) and route for route in required
    ):
        errors.append("required_routes must be a non-empty list of route names")
        required = []
    elif len(required) != len(set(required)):
        errors.append("required_routes must contain unique route names")
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
    term_routes = [
        link.get("term_route")
        for link in route_map.values()
        if isinstance(link, Mapping) and isinstance(link.get("term_route"), str)
    ]
    if len(term_routes) != len(set(term_routes)):
        errors.append("route_map term_route values must be unique")
    if isinstance(surface_link, Mapping) and not any(
        isinstance(link, Mapping)
        and link.get("term_route") == surface_link.get("term_route")
        and link.get("convergence_route") == surface_link.get("convergence_route")
        for link in route_map.values()
    ):
        errors.append(
            "physical_route_map.surface_place_route must bind an existing term/convergence route pair"
        )
    return errors


def _component_schema_status(result: Mapping[str, Any]) -> bool:
    return result.get("status") == "INVALID_SCHEMA"


def validate_manifest(
    contract: Mapping[str, Any],
    manifest: Mapping[str, Any],
    term_contract: Mapping[str, Any],
    first_step_contract: Mapping[str, Any],
    native_transition_contract: Mapping[str, Any],
    surface_place_route_contract: Mapping[str, Any],
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

    if native_transition_contract.get("workload_fingerprint") != contract.get("workload_fingerprint"):
        component_errors.append("native-transition contract workload_fingerprint does not match")
    if native_transition_contract.get("route") != "native_fermions":
        component_errors.append("native-transition contract route must be native_fermions")
    native_manifest = manifest.get("native_transition")
    if not isinstance(native_manifest, Mapping):
        component_errors.append("manifest native_transition must be an object")
        native_manifest = {}
    native_result = NATIVE.validate_ledger(native_transition_contract, native_manifest)

    surface_link = contract["physical_route_map"]["surface_place_route"]
    if surface_place_route_contract.get("workload_fingerprint") != contract.get(
        "workload_fingerprint"
    ):
        component_errors.append("surface contract workload_fingerprint does not match")
    if surface_place_route_contract.get("route") != surface_link["route"]:
        component_errors.append("surface contract route does not match physical_route_map")
    if surface_place_route_contract.get("parent_term_route") != surface_link["term_route"]:
        component_errors.append("surface parent_term_route does not match physical_route_map")
    if surface_place_route_contract.get("parent_convergence_route") != surface_link[
        "convergence_route"
    ]:
        component_errors.append("surface parent_convergence_route does not match physical_route_map")
    if surface_place_route_contract.get("target_linear_size") != contract.get(
        "target_linear_size"
    ):
        component_errors.append("surface contract target_linear_size does not match")
    if surface_place_route_contract.get("target_trotter_steps") != contract.get(
        "target_trotter_steps"
    ):
        component_errors.append("surface contract target_trotter_steps does not match")
    term_groups_per_step = term_contract.get("workload", {}).get(
        "raw_groups_per_strang_step"
    )
    if surface_place_route_contract.get("logical_events_per_trotter_step") != term_groups_per_step:
        component_errors.append(
            "surface logical_events_per_trotter_step does not match term contract"
        )
    surface_manifest = manifest.get("surface_place_route")
    if not isinstance(surface_manifest, Mapping):
        component_errors.append("manifest surface_place_route must be an object")
        surface_manifest = {}
    surface_result = SURFACE.validate_ledger(surface_place_route_contract, surface_manifest)

    convergence_manifest = manifest.get("convergence")
    if not isinstance(convergence_manifest, Mapping):
        component_errors.append("manifest convergence must be an object")
        convergence_manifest = {}
    convergence_workload = convergence_manifest.get("workload", {})
    if not isinstance(convergence_workload, Mapping) or convergence_workload != contract.get(
        "convergence_workload_policy"
    ):
        component_errors.append(
            "convergence workload must exactly match evidence convergence_workload_policy"
        )
    convergence_routes = [route_map[route]["convergence_route"] for route in required]
    unique_convergence_routes = list(dict.fromkeys(convergence_routes))
    if convergence_manifest.get("required_routes") != unique_convergence_routes:
        component_errors.append(
            "manifest convergence.required_routes do not match evidence route map"
        )
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

    if isinstance(native_manifest, Mapping):
        if isinstance(native_manifest.get("linear_size"), int) and native_manifest["linear_size"] != contract[
            "target_linear_size"
        ]:
            coherence_errors.append("native transition linear_size does not match target_linear_size")
        if isinstance(native_manifest.get("trotter_steps"), int) and native_manifest["trotter_steps"] != contract[
            "target_trotter_steps"
        ]:
            coherence_errors.append("native transition trotter_steps does not match target_trotter_steps")

    if isinstance(surface_manifest, Mapping):
        if isinstance(surface_manifest.get("linear_size"), int) and surface_manifest[
            "linear_size"
        ] != contract["target_linear_size"]:
            coherence_errors.append("surface place-route linear_size does not match target_linear_size")
        if isinstance(surface_manifest.get("trotter_steps"), int) and surface_manifest[
            "trotter_steps"
        ] != contract["target_trotter_steps"]:
            coherence_errors.append(
                "surface place-route trotter_steps does not match target_trotter_steps"
            )
    if term_result.get("status") == "MATCHED" and surface_result.get("status") in (
        "COMPLETE",
        "BOOKKEEPING_CLOSED_ESTIMATE",
    ):
        if surface_result.get("logical_sequence_fingerprint") != term_result.get(
            "common_sequence_fingerprint"
        ):
            coherence_errors.append("surface logical_sequence_fingerprint does not match term order")
        if surface_manifest.get("logical_event_count") != term_result.get("sequence_length"):
            coherence_errors.append("surface logical_event_count does not match term sequence length")

    if convergence_result.get("status") == "READY_FOR_TARGET_R":
        target_r = contract["target_trotter_steps"]
        observable_order = contract["convergence_workload_policy"]["observable_order"]
        if convergence_result.get("target_R") != target_r:
            coherence_errors.append("convergence result target_R does not match target_trotter_steps")
        if convergence_result.get("coverage_scope") != observable_order:
            coherence_errors.append("convergence coverage_scope does not match required observables")
        stable_matrix = convergence_result.get("stable_from_R_by_route_observable", {})
        for route in unique_convergence_routes:
            route_result = convergence_result.get("routes", {}).get(route, {})
            target_points = [
                point
                for point in route_result.get("points", [])
                if point.get("R") == target_r
            ]
            if len(target_points) != 1:
                coherence_errors.append(
                    f"convergence route {route} has no unique complete vector at "
                    f"target_trotter_steps={target_r}"
                )
            elif not isinstance(target_points[0].get("estimates"), Mapping) or set(
                target_points[0]["estimates"]
            ) != set(observable_order):
                coherence_errors.append(
                    f"convergence route {route} target vector does not cover required observables"
                )
            route_stability = (
                stable_matrix.get(route, {}) if isinstance(stable_matrix, Mapping) else {}
            )
            for observable in observable_order:
                stable_from_r = (
                    route_stability.get(observable)
                    if isinstance(route_stability, Mapping)
                    else None
                )
                if (
                    isinstance(stable_from_r, bool)
                    or not isinstance(stable_from_r, int)
                    or target_r < stable_from_r
                ):
                    coherence_errors.append(
                        f"convergence route {route} observable {observable} is not stable at "
                        f"target_trotter_steps={target_r}"
                    )

    if component_errors:
        errors.extend(component_errors)
    if coherence_errors:
        errors.extend(coherence_errors)

    component_statuses = {
        "term_order": term_result.get("status"),
        "first_step": first_step_result.get("status"),
        "native_transition": native_result.get("status"),
        "surface_place_route": surface_result.get("status"),
        "convergence": convergence_result.get("status"),
    }
    if any(
        _component_schema_status(result)
        for result in (
            term_result,
            first_step_result,
            native_result,
            surface_result,
            convergence_result,
        )
    ):
        status = "INVALID_SCHEMA"
    elif component_errors:
        status = "INVALID_SCHEMA"
    elif term_result.get("status") == "MISMATCH":
        status = "MISMATCH"
    elif coherence_errors:
        status = "INCONSISTENT"
    elif all(
        (
            term_result.get("status") == "MATCHED",
            first_step_result.get("status") == "COMPLETE",
            native_result.get("status") == "COMPLETE",
            surface_result.get("status") == "COMPLETE",
            convergence_result.get("status") == "READY_FOR_TARGET_R",
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
            "native_transition": native_result,
            "surface_place_route": surface_result,
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
    parser.add_argument("--native-transition-contract", type=Path, required=True)
    parser.add_argument("--surface-place-route-contract", type=Path, required=True)
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
    with args.native_transition_contract.open(encoding="utf-8") as handle:
        native_transition_contract = json.load(handle)
    with args.surface_place_route_contract.open(encoding="utf-8") as handle:
        surface_place_route_contract = json.load(handle)
    result = validate_manifest(
        contract,
        manifest,
        term_contract,
        first_step_contract,
        native_transition_contract,
        surface_place_route_contract,
    )
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
