#!/usr/bin/env python3
"""Assess common-R convergence evidence for the matched Hubbard workload.

The tool is intentionally conservative: it distinguishes schema errors from an
unresolved result, propagates reported standard errors into pairwise checks, and
never invents a reference value or a missing route.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional


def _number(value: Any, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be finite")
    value = float(value)
    if not math.isfinite(value):
        raise ValueError(f"{name} must be finite")
    return value


def _positive(value: Any, name: str) -> float:
    value = _number(value, name)
    if value <= 0:
        raise ValueError(f"{name} must be positive")
    return value


def _nonnegative(value: Any, name: str) -> float:
    value = _number(value, name)
    if value < 0:
        raise ValueError(f"{name} must be non-negative")
    return value


def _positive_int(value: Any, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{name} must be a positive integer")
    return value


def _metadata_mismatches(expected: Mapping[str, Any], actual: Mapping[str, Any]) -> List[str]:
    errors = []
    for key in ("observable", "initial_state", "hamiltonian_fingerprint", "trotter_formula"):
        if actual.get(key) != expected.get(key):
            errors.append(f"metadata.{key} does not match the manifest")
    return errors


def validate_manifest(manifest: Mapping[str, Any]) -> List[str]:
    errors: List[str] = []
    if manifest.get("schema_version") != 1:
        errors.append("schema_version must be 1")
    workload = manifest.get("workload")
    if not isinstance(workload, Mapping):
        return ["workload must be an object"]
    for key in ("observable", "initial_state", "hamiltonian_fingerprint", "trotter_formula"):
        if not isinstance(workload.get(key), str) or not workload[key].strip():
            errors.append(f"workload.{key} must be a non-empty string")
    try:
        _positive(workload["algorithmic_error_budget"], "workload.algorithmic_error_budget")
    except (KeyError, ValueError) as exc:
        errors.append(str(exc))
    try:
        _nonnegative(workload["statistical_error_budget"], "workload.statistical_error_budget")
    except (KeyError, ValueError) as exc:
        errors.append(str(exc))
    try:
        _positive(workload["confidence_z"], "workload.confidence_z")
    except (KeyError, ValueError) as exc:
        errors.append(str(exc))
    required = manifest.get("required_routes")
    if not isinstance(required, list) or not required or not all(isinstance(x, str) for x in required):
        errors.append("required_routes must be a non-empty list of route names")
    routes = manifest.get("routes")
    if not isinstance(routes, Mapping):
        errors.append("routes must be an object keyed by route name")
    else:
        for route_name, route in routes.items():
            if not isinstance(route_name, str) or not isinstance(route, Mapping):
                errors.append("each routes entry must be a named object")
    reference = manifest.get("reference")
    if reference is not None:
        if not isinstance(reference, Mapping):
            errors.append("reference must be null or an object")
        else:
            try:
                _number(reference["value"], "reference.value")
            except (KeyError, ValueError) as exc:
                errors.append(str(exc))
    return errors


def assess_route(
    manifest: Mapping[str, Any], route_name: str, route: Mapping[str, Any]
) -> Dict[str, Any]:
    workload = manifest["workload"]
    errors = _metadata_mismatches(workload, route.get("metadata", {}))
    warnings: List[str] = []
    points = route.get("points")
    if not isinstance(points, list) or not points:
        return {
            "route": route_name,
            "status": "UNRESOLVED_NO_POINTS",
            "errors": errors,
            "warnings": ["no R-grid points supplied"],
            "stable_from_R": None,
            "points": [],
        }
    normalized = []
    seen = set()
    for index, point in enumerate(points):
        if not isinstance(point, Mapping):
            errors.append(f"point {index} is not an object")
            continue
        try:
            r = _positive_int(point["R"], f"{route_name}.points[{index}].R")
            estimate = _number(point["estimate"], f"{route_name}.points[{index}].estimate")
            standard_error = _nonnegative(
                point["standard_error"],
                f"{route_name}.points[{index}].standard_error",
            )
        except (KeyError, ValueError) as exc:
            errors.append(str(exc))
            continue
        if r in seen:
            errors.append(f"duplicate R={r}")
        seen.add(r)
        normalized.append({"R": r, "estimate": estimate, "standard_error": standard_error})
    normalized.sort(key=lambda point: point["R"])
    if len(normalized) < 3:
        warnings.append("at least three R points are required for a two-interval stability window")
    algorithmic_budget = float(workload["algorithmic_error_budget"])
    statistical_budget = float(workload["statistical_error_budget"])
    z = float(workload["confidence_z"])
    pair_checks = []
    for left, right in zip(normalized, normalized[1:]):
        combined_se = math.sqrt(left["standard_error"] ** 2 + right["standard_error"] ** 2)
        bound = abs(right["estimate"] - left["estimate"]) + z * combined_se
        pair_checks.append(
            {
                "from_R": left["R"],
                "to_R": right["R"],
                "absolute_delta": abs(right["estimate"] - left["estimate"]),
                "confidence_bound": bound,
                "passes_algorithmic_budget": bound <= algorithmic_budget,
            }
        )
    reference_checks = []
    reference = manifest.get("reference")
    if reference is not None and isinstance(reference, Mapping):
        reference_value = float(reference["value"])
        for point in normalized:
            bound = abs(point["estimate"] - reference_value) + z * point["standard_error"]
            reference_checks.append(
                {
                    "R": point["R"],
                    "confidence_bound": bound,
                    "passes_algorithmic_budget": bound <= algorithmic_budget,
                }
            )
    stable_from_R: Optional[int] = None
    # Require two adjacent refinement intervals. If a reference is supplied,
    # require all later reference checks as well as the two-interval window.
    for start in range(max(0, len(normalized) - 2)):
        later_pairs = pair_checks[start:]
        if len(later_pairs) < 2 or not all(item["passes_algorithmic_budget"] for item in later_pairs):
            continue
        later_points = normalized[start:]
        if not all(point["standard_error"] <= statistical_budget for point in later_points):
            continue
        if reference_checks and not all(
            item["passes_algorithmic_budget"] for item in reference_checks[start:]
        ):
            continue
        stable_from_R = later_points[0]["R"]
        break
    if stable_from_R is None:
        warnings.append(
            "no two-interval R window satisfies the algorithmic and statistical budgets"
        )
    status = "VALIDATED" if not errors and stable_from_R is not None else "UNRESOLVED"
    return {
        "route": route_name,
        "status": status,
        "errors": errors,
        "warnings": warnings,
        "points": normalized,
        "pair_checks": pair_checks,
        "reference_checks": reference_checks,
        "stable_from_R": stable_from_R,
    }


def assess_manifest(manifest: Mapping[str, Any]) -> Dict[str, Any]:
    schema_errors = validate_manifest(manifest)
    if schema_errors:
        return {"status": "INVALID_SCHEMA", "errors": schema_errors, "routes": {}}
    required = manifest["required_routes"]
    routes = manifest["routes"]
    route_results: Dict[str, Any] = {}
    missing = []
    for route_name in required:
        if route_name not in routes:
            missing.append(route_name)
        else:
            route_results[route_name] = assess_route(manifest, route_name, routes[route_name])
    stable = {
        name: result["stable_from_R"]
        for name, result in route_results.items()
        if result["stable_from_R"] is not None and not result["errors"]
    }
    common_R: Optional[int] = None
    common_errors: List[str] = []
    if missing:
        common_errors.append(f"missing required routes: {', '.join(missing)}")
    if len(stable) != len(required):
        unresolved = [name for name in required if name not in stable]
        common_errors.append(f"routes without validated stability window: {', '.join(unresolved)}")
    if not common_errors:
        common_R = max(stable.values())
        for name in required:
            point_Rs = {point["R"] for point in route_results[name]["points"]}
            if common_R not in point_Rs:
                common_errors.append(f"route {name} has no result at common R={common_R}")
    status = "READY_FOR_COMMON_R" if not common_errors else "UNRESOLVED"
    return {
        "status": status,
        "errors": [],
        "common_R": common_R,
        "route_stable_from_R": stable,
        "common_errors": common_errors,
        "routes": route_results,
        "reference_used": manifest.get("reference") is not None,
        "workload_identity": manifest["workload"],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--format", choices=("json", "markdown"), default="json")
    args = parser.parse_args()
    with args.manifest.open(encoding="utf-8") as handle:
        manifest = json.load(handle)
    result = assess_manifest(manifest)
    if args.format == "markdown":
        print(f"# Common-R convergence assessment: {result['status']}\n")
        print(f"Recommended common R: `{result.get('common_R')}`\n")
        if result.get("common_errors"):
            print("Unresolved conditions:\n" + "\n".join(f"- {item}" for item in result["common_errors"]))
        for name, route in result.get("routes", {}).items():
            print(f"\n## {name}: {route['status']}\n")
            print(f"Stable from R: `{route['stable_from_R']}`")
            for warning in route.get("warnings", []):
                print(f"\nWarning: {warning}")
    else:
        print(json.dumps(result, indent=2, sort_keys=True))
    sys.exit(0 if result.get("status") != "INVALID_SCHEMA" else 1)


if __name__ == "__main__":
    main()
