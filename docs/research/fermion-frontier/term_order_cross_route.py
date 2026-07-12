#!/usr/bin/env python3
"""Compare individual-term sequences across matched Hubbard route exports.

The existing term-order validator intentionally accepts group-only exports. This
tool is stricter: every required route must include individual ``terms`` lists,
and the normalized raw sequence must match exactly before it reports a match.
Missing exports or group-only fixtures remain unresolved rather than being
treated as evidence of cross-compiler equality.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Mapping, Sequence, Tuple


SPEC = Path(__file__).resolve().parent


def _load(path: Path) -> Mapping[str, Any]:
    with path.open(encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, Mapping):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def _sequence(export: Mapping[str, Any]) -> Tuple[Tuple[str, Tuple[str, ...]], ...]:
    sequence: List[Tuple[str, Tuple[str, ...]]] = []
    for step in export.get("steps", []):
        for event in step.get("events", []):
            sequence.append((event["group"], tuple(event["terms"])))
    return tuple(sequence)


def _fingerprint(sequence: Sequence[Tuple[str, Sequence[str]]]) -> str:
    payload = json.dumps(sequence, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def compare_routes(
    contract: Mapping[str, Any], manifest: Mapping[str, Any]
) -> Dict[str, Any]:
    errors: List[str] = []
    required = contract.get("required_routes")
    if not isinstance(required, list) or not required or not all(
        isinstance(route, str) and route for route in required
    ):
        errors.append("contract required_routes must be a non-empty list of route names")
        required = []
    if manifest.get("schema_version") != 1:
        errors.append("manifest schema_version must be 1")
    if manifest.get("required_routes") != required:
        errors.append("manifest required_routes must exactly match the contract")
    exports = manifest.get("exports")
    if not isinstance(exports, Mapping):
        errors.append("manifest exports must be an object keyed by route name")
        exports = {}
    if errors:
        return {"status": "INVALID_SCHEMA", "errors": errors, "routes": {}}

    if str(SPEC) not in sys.path:
        sys.path.insert(0, str(SPEC))
    from term_order_validator import validate_export

    route_results: Dict[str, Any] = {}
    missing: List[str] = []
    valid_sequences: Dict[str, Tuple[Tuple[str, Tuple[str, ...]], ...]] = {}
    for route in required:
        if route not in exports:
            missing.append(route)
            continue
        export = exports[route]
        if not isinstance(export, Mapping):
            route_results[route] = {
                "status": "UNRESOLVED",
                "errors": ["route export must be an object"],
            }
            continue
        validation = validate_export(contract, export)
        route_result: Dict[str, Any] = {
            "status": "UNRESOLVED",
            "validator_status": validation["status"],
            "individual_term_sets_validated": validation["individual_term_sets_validated"],
            "errors": list(validation["errors"]),
            "warnings": list(validation["warnings"]),
        }
        if not validation["valid"]:
            route_result["errors"].append("route export failed term-order validation")
        elif not validation["individual_term_sets_validated"]:
            route_result["warnings"].append(
                "individual-term lists are required for exact cross-route comparison"
            )
        else:
            sequence = _sequence(export)
            valid_sequences[route] = sequence
            route_result["status"] = "READY_FOR_COMPARISON"
            route_result["sequence_fingerprint"] = _fingerprint(sequence)
        route_results[route] = route_result

    if missing:
        errors.append(f"missing required route exports: {', '.join(missing)}")
    unresolved = [
        route
        for route in required
        if route not in valid_sequences
    ]
    if unresolved:
        errors.append(
            "individual-term sequence comparison unresolved for: " + ", ".join(unresolved)
        )
        return {"status": "UNRESOLVED", "errors": errors, "routes": route_results}

    reference_route = required[0]
    reference_sequence = valid_sequences[reference_route]
    mismatches: Dict[str, Dict[str, Any]] = {}
    for route in required[1:]:
        sequence = valid_sequences[route]
        if sequence != reference_sequence:
            first_difference = next(
                (
                    index
                    for index, (left, right) in enumerate(zip(reference_sequence, sequence))
                    if left != right
                ),
                min(len(reference_sequence), len(sequence)),
            )
            mismatches[route] = {
                "reference_route": reference_route,
                "first_difference_index": first_difference,
                "reference_fingerprint": _fingerprint(reference_sequence),
                "route_fingerprint": _fingerprint(sequence),
            }
    if mismatches:
        errors.append("individual-term sequences differ across required routes")
        return {
            "status": "MISMATCH",
            "errors": errors,
            "routes": route_results,
            "mismatches": mismatches,
            "reference_route": reference_route,
        }
    return {
        "status": "MATCHED",
        "errors": [],
        "routes": route_results,
        "reference_route": reference_route,
        "common_sequence_fingerprint": _fingerprint(reference_sequence),
        "sequence_length": len(reference_sequence),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--contract", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--format", choices=("json", "markdown"), default="json")
    args = parser.parse_args()
    sys.path.insert(0, str(SPEC))
    result = compare_routes(_load(args.contract), _load(args.manifest))
    if args.format == "markdown":
        print(f"# Cross-route term-order comparison: {result['status']}\n")
        for route, detail in result.get("routes", {}).items():
            print(f"- `{route}`: {detail['status']}")
        for error in result.get("errors", []):
            print(f"\nError: {error}")
    else:
        print(json.dumps(result, indent=2, sort_keys=True))
    sys.exit(0 if result["status"] == "MATCHED" else 1)


if __name__ == "__main__":
    main()
