#!/usr/bin/env python3
"""Aggregate FH-L8 external-evidence intake + unified manifest validation."""

from __future__ import annotations

import argparse
import json
import importlib.util
import sys
from pathlib import Path


HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import fh_l8_external_evidence_intake as intake


def _load_json(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must be a JSON object")
    return value


def _load_validator(name: str, module_path: str):
    path = HERE / module_path
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load {name} from {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


EVIDENCE = _load_validator("evidence", "fermi_hubbard_evidence.py")
_TERM = _load_validator("term_order_cross_route", "term_order_cross_route.py")


def evaluate_bridge(
    registry: Path,
    intake_root: Path,
    evidence_manifest: Path,
) -> dict:
    """Run intake + evidence-manifest checks and return raw outputs."""
    intake_contract = _load_json(HERE / "fh_l8_external_evidence_intake_contract.json")
    evidence_contract = _load_json(HERE / "evidence_manifest_contract.json")
    registry_payload = _load_json(registry)
    manifest = _load_json(evidence_manifest)

    intake_result = intake.assess(intake_contract, registry_payload, intake_root)
    term_order_manifest = _load_json(HERE / "term_order_cross_route_template.json")
    term_contract = _load_json(HERE / "term_order_contract.json")
    cross_route_snapshot = _TERM.compare_routes(term_contract, term_order_manifest)

    evidence_result = EVIDENCE.validate_manifest(
        evidence_contract,
        manifest,
        term_contract,
        _load_json(HERE / "first_step_contract.json"),
        _load_json(HERE / "native_transition_contract.json"),
        _load_json(HERE / "surface_place_route_contract.json"),
    )
    next_actions = _next_actions(intake_result, cross_route_snapshot, evidence_result)
    return {
        "intake": intake_result,
        "cross_route_snapshot": cross_route_snapshot,
        "evidence": evidence_result,
        "next_actions": next_actions,
        "summary": {
            "intake_status": intake_result["status"],
            "evidence_status": evidence_result["status"],
            "cross_route_status": cross_route_snapshot["status"],
        },
    }


def _next_actions(
    intake_result: dict,
    cross_route_snapshot: dict,
    evidence_result: dict,
) -> list[dict[str, str]]:
    actions: list[dict[str, str]] = []

    for route, detail in intake_result.get("routes", {}).items():
        status = detail.get("status")
        if status == "INCOMPLETE":
            actions.append(
                {
                    "priority": "1",
                    "area": "intake",
                    "route": route,
                    "status": status,
                    "next_action": (
                        f"submit intake registration for {route} and place admissible raw export JSON under the intake root"
                    ),
                }
            )
        elif status == "REJECTED":
            first_error = detail.get("errors", ["registration rejected"])[0]
            actions.append(
                {
                    "priority": "1",
                    "area": "intake",
                    "route": route,
                    "status": status,
                    "next_action": f"fix {route} registration/export rejection: {first_error}",
                }
            )

    if intake_result.get("status") != "READY_FOR_CROSS_ROUTE_COMPARISON":
        if not any(action["area"] == "intake" for action in actions):
            actions.append(
                {
                    "priority": "1",
                    "area": "intake",
                    "route": "*",
                    "status": intake_result.get("status", "UNKNOWN"),
                    "next_action": "complete intake admission for all five routes before comparison",
                }
            )

    if cross_route_snapshot.get("status") != "MATCHED":
        if cross_route_snapshot.get("status") == "MISMATCH":
            actions.append(
                {
                    "priority": "2",
                    "area": "term-order",
                    "route": "all",
                    "status": cross_route_snapshot.get("status", "UNKNOWN"),
                    "next_action": (
                        "repair admissible route exports so individual-term sequences are identical across all five routes"
                    ),
                }
            )
        else:
            actions.append(
                {
                    "priority": "2",
                    "area": "term-order",
                    "route": "all",
                    "status": cross_route_snapshot.get("status", "UNKNOWN"),
                    "next_action": (
                        "admit all five real route exports, then run cross-route comparison"
                    ),
                }
            )

    for component, status in evidence_result.get("component_statuses", {}).items():
        if status == "UNRESOLVED":
            actions.append(
                {
                    "priority": "3",
                    "area": "evidence",
                    "route": component,
                    "status": status,
                    "next_action": f"resolve component '{component}' evidence in its contract-defined sources",
                }
            )

    if evidence_result.get("status") != "READY_FOR_BENCHMARK":
        if not actions:
            actions.append(
                {
                    "priority": "4",
                    "area": "evidence",
                    "route": "aggregate",
                    "status": evidence_result.get("status", "UNKNOWN"),
                    "next_action": "re-check component gates after cross-route and intake are complete",
                }
            )

    return sorted(actions, key=lambda action: (int(action["priority"]), action["area"], action["route"]))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registry", type=Path, required=True)
    parser.add_argument("--intake-root", type=Path, required=True)
    parser.add_argument(
        "--evidence-manifest",
        type=Path,
        default=HERE / "evidence_manifest_source_snapshot.json",
    )
    parser.add_argument(
        "--next-actions-only",
        action="store_true",
        help="emit only next_actions (one action per line)",
    )
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    result = evaluate_bridge(args.registry, args.intake_root, args.evidence_manifest)
    if args.output is not None and not args.next_actions_only:
        args.output.write_text(
            json.dumps(result, indent=2, sort_keys=True),
            encoding="utf-8",
        )
    if args.next_actions_only:
        for action in result["next_actions"]:
            print(
                f'[{action["priority"]}] {action["area"]:>10} {action["route"]}: {action["next_action"]} '
                f'({action["status"]})'
            )
    else:
        print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
