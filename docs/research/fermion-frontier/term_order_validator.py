#!/usr/bin/env python3
"""Validate a route's raw group-level Strang export against the common contract."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Mapping


GROUP_ORDER = ["H1", "H2", "HU", "H3", "H4", "H4", "H3", "HU", "H2", "H1"]


def _hopping_terms(group: str, l: int) -> List[str]:
    terms: List[str] = []
    if group in ("H1", "H2"):
        parity = 0 if group == "H1" else 1
        for r in range(l):
            for c in range(parity, l - 1, 2):
                for spin in ("up", "down"):
                    terms.append(f"{group}_r{r}_c{c}_{spin}")
    elif group in ("H3", "H4"):
        parity = 1 if group == "H3" else 0
        for r in range(parity, l - 1, 2):
            for c in range(l):
                for spin in ("up", "down"):
                    terms.append(f"{group}_r{r}_c{c}_{spin}")
    else:
        raise ValueError(f"unknown hopping group {group}")
    return terms


def expected_terms(l: int) -> Dict[str, List[str]]:
    if not isinstance(l, int) or l < 3:
        raise ValueError("linear_size must be an integer >= 3")
    return {
        **{group: _hopping_terms(group, l) for group in ("H1", "H2", "H3", "H4")},
        "HU": [f"HU_r{r}_c{c}" for r in range(l) for c in range(l)],
    }


def _error(errors: List[str], message: str) -> None:
    errors.append(message)


def validate_export(contract: Mapping[str, Any], export: Mapping[str, Any]) -> Dict[str, Any]:
    errors: List[str] = []
    warnings: List[str] = []
    if export.get("schema_version") != contract.get("schema_version"):
        _error(errors, "schema_version does not match the contract")
    if contract.get("workload", {}).get("group_order") != GROUP_ORDER:
        _error(errors, "contract group_order is not the validator's pinned order")
    l = export.get("linear_size")
    r = export.get("trotter_steps")
    try:
        terms_by_group = expected_terms(l)
    except (TypeError, ValueError) as exc:
        _error(errors, str(exc))
        terms_by_group = {}
    if not isinstance(r, int) or r <= 0:
        _error(errors, "trotter_steps must be a positive integer")
        r = 0
    steps = export.get("steps")
    if not isinstance(steps, list):
        _error(errors, "steps must be a list")
        steps = []
    if len(steps) != r:
        _error(errors, f"expected {r} steps, found {len(steps)}")

    term_sets_present = True
    for step_index, step in enumerate(steps):
        if not isinstance(step, Mapping):
            _error(errors, f"step {step_index} is not an object")
            continue
        events = step.get("events")
        if not isinstance(events, list):
            _error(errors, f"step {step_index}.events must be a list")
            continue
        groups = [event.get("group") for event in events if isinstance(event, Mapping)]
        if groups != GROUP_ORDER:
            _error(
                errors,
                f"step {step_index} group order mismatch: expected {GROUP_ORDER}, found {groups}",
            )
        for event_index, event in enumerate(events):
            if not isinstance(event, Mapping):
                _error(errors, f"step {step_index} event {event_index} is not an object")
                continue
            group = event.get("group")
            if group not in terms_by_group:
                _error(errors, f"step {step_index} event {event_index} has unknown group {group}")
                continue
            if "terms" not in event:
                term_sets_present = False
                continue
            actual = event.get("terms")
            if not isinstance(actual, list) or sorted(actual) != sorted(terms_by_group[group]):
                _error(
                    errors,
                    f"step {step_index} event {event_index} term set does not match {group}",
                )
    if not term_sets_present:
        warnings.append("group-level validation passed without individual-term lists")

    g1 = len(terms_by_group.get("H1", []))
    g4 = len(terms_by_group.get("H4", []))
    v = len(terms_by_group.get("HU", []))
    raw_event_count = len(steps) * len(GROUP_ORDER)
    within_fusions = len(steps)
    across_fusions = max(0, len(steps) - 1)
    fused_event_count = raw_event_count - within_fusions - across_fusions
    raw_term_calls = len(steps) * (2 * (g1 + len(terms_by_group.get("H2", [])) + len(terms_by_group.get("H3", [])) + g4) + 2 * v)
    fused_term_calls = raw_term_calls - len(steps) * g4 - across_fusions * g1
    return {
        "valid": not errors,
        "route": export.get("route"),
        "linear_size": l,
        "trotter_steps": len(steps),
        "group_order_validated": not any("group order mismatch" in e for e in errors),
        "individual_term_sets_validated": term_sets_present and not any("term set" in e for e in errors),
        "raw_group_events": raw_event_count,
        "within_step_H4_fusions": within_fusions,
        "across_step_H1_fusions": across_fusions,
        "fused_group_events": fused_event_count,
        "raw_term_calls": raw_term_calls,
        "fused_term_calls": fused_term_calls,
        "matching_sizes": {"H1": g1, "H2": len(terms_by_group.get("H2", [])), "H3": len(terms_by_group.get("H3", [])), "H4": g4, "HU": v},
        "errors": errors,
        "warnings": warnings,
        "status": "VALIDATED" if not errors else "INVALID",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--contract", type=Path, required=True)
    parser.add_argument("--export", type=Path, required=True)
    parser.add_argument("--format", choices=("json", "markdown"), default="json")
    args = parser.parse_args()
    with args.contract.open(encoding="utf-8") as handle:
        contract = json.load(handle)
    with args.export.open(encoding="utf-8") as handle:
        export = json.load(handle)
    result = validate_export(contract, export)
    if args.format == "markdown":
        print(f"# Term-order validation: {result['status']}\n")
        print(f"Route: `{result['route']}`, L={result['linear_size']}, R={result['trotter_steps']}\n")
        print(f"- Group order: `{result['group_order_validated']}`")
        print(f"- Individual term sets: `{result['individual_term_sets_validated']}`")
        print(f"- Fused group events: `{result['fused_group_events']}`")
        if result["errors"]:
            print("\nErrors:\n" + "\n".join(f"- {item}" for item in result["errors"]))
        if result["warnings"]:
            print("\nWarnings:\n" + "\n".join(f"- {item}" for item in result["warnings"]))
    else:
        print(json.dumps(result, indent=2, sort_keys=True))
    sys.exit(0 if result["valid"] else 1)


if __name__ == "__main__":
    main()
