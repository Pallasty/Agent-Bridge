#!/usr/bin/env python3
"""Fail-closed receiver for externally supplied FH-L8 compiler exports.

The registry deliberately begins empty.  A route is admitted only when its
declared raw JSON file has an exact hash, immutable source/version metadata,
compiler/environment custody, and passes the existing individual-term export
validator.  This program never treats a fixture, a figure reconstruction, or
an unregistered JSON file as scientific evidence.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any, Mapping


HERE = Path(__file__).resolve().parent
SHA256 = re.compile(r"^[0-9a-f]{64}$")


def load(path: Path) -> Mapping[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, Mapping):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def safe_artifact_path(root: Path, registered_path: str) -> Path:
    candidate = (root / registered_path).resolve()
    if root.resolve() not in candidate.parents:
        raise ValueError("artifact_path escapes the intake root")
    return candidate


def nonempty(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def route_admission(contract: Mapping[str, Any], root: Path, route: str, registration: Any) -> dict[str, Any]:
    if registration is None:
        return {"status": "INCOMPLETE", "errors": ["no registration submitted"], "warnings": []}
    if not isinstance(registration, Mapping):
        return {"status": "REJECTED", "errors": ["registration must be an object"], "warnings": []}
    errors: list[str] = []
    for field in contract["required_registration_fields"]:
        if not nonempty(registration.get(field)):
            errors.append(f"missing or empty registration field: {field}")
    if registration.get("route") not in (None, route):
        errors.append("registration route does not match route key")
    if not str(registration.get("source_url", "")).startswith("https://"):
        errors.append("source_url must be an https URL")
    if registration.get("evidence_class") != "PRIMARY_EXTERNAL_RAW_EXPORT":
        errors.append("evidence_class must be PRIMARY_EXTERNAL_RAW_EXPORT")
    for field in ("sha256", "compiler_configuration_sha256", "environment_lock_sha256"):
        if not SHA256.fullmatch(str(registration.get(field, ""))):
            errors.append(f"{field} must be a lowercase SHA-256 hex digest")
    if errors:
        return {"status": "REJECTED", "errors": errors, "warnings": []}
    try:
        artifact_path = safe_artifact_path(root, registration["artifact_path"])
    except ValueError as error:
        return {"status": "REJECTED", "errors": [str(error)], "warnings": []}
    if not artifact_path.is_file():
        return {"status": "INCOMPLETE", "errors": ["registered artifact file is not present"], "warnings": []}
    actual_digest = digest(artifact_path)
    if actual_digest != registration["sha256"]:
        return {"status": "REJECTED", "errors": ["raw artifact SHA-256 mismatch"], "warnings": []}
    try:
        export = load(artifact_path)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        return {"status": "REJECTED", "errors": [f"artifact is not readable JSON: {error}"], "warnings": []}
    if export.get("route") != route:
        errors.append("artifact route does not match route key")
    if export.get("linear_size") != contract["linear_size"]:
        errors.append("artifact linear_size does not match the FH-L8 contract")
    if export.get("trotter_steps") != contract["trotter_steps"]:
        errors.append("artifact trotter_steps does not match the FH-L8 contract")
    if export.get("workload_fingerprint") != contract["workload_fingerprint"]:
        errors.append("artifact workload_fingerprint does not match the contract")
    sys.path.insert(0, str(HERE))
    from term_order_validator import validate_export
    term_contract = load(HERE / "term_order_contract.json")
    validation = validate_export(term_contract, export)
    if not validation["valid"]:
        errors.extend(validation["errors"])
    if not validation["individual_term_sets_validated"]:
        errors.append("artifact lacks complete individual-term event lists")
    if errors:
        return {"status": "REJECTED", "errors": errors, "warnings": validation["warnings"]}
    return {
        "status": "ADMITTED",
        "errors": [],
        "warnings": validation["warnings"],
        "artifact_sha256": actual_digest,
        "sequence_ready": True,
    }


def assess(contract: Mapping[str, Any], registry: Mapping[str, Any], root: Path) -> dict[str, Any]:
    schema_errors: list[str] = []
    if registry.get("schema_version") != contract["schema_version"]:
        schema_errors.append("registry schema_version does not match contract")
    if registry.get("contract_id") != contract["contract_id"]:
        schema_errors.append("registry contract_id does not match contract")
    if registry.get("workload_fingerprint") != contract["workload_fingerprint"]:
        schema_errors.append("registry workload_fingerprint does not match contract")
    artifacts = registry.get("artifacts")
    if not isinstance(artifacts, Mapping):
        schema_errors.append("registry artifacts must be an object")
        artifacts = {}
    unexpected = sorted(set(artifacts) - set(contract["required_routes"]))
    if unexpected:
        schema_errors.append("unexpected registry routes: " + ", ".join(unexpected))
    if schema_errors:
        return {"status": "REJECTED", "errors": schema_errors, "routes": {}}
    routes = {route: route_admission(contract, root, route, artifacts.get(route)) for route in contract["required_routes"]}
    admitted = [route for route, detail in routes.items() if detail["status"] == "ADMITTED"]
    rejected = [route for route, detail in routes.items() if detail["status"] == "REJECTED"]
    hashes = [routes[route]["artifact_sha256"] for route in admitted]
    if len(hashes) != len(set(hashes)):
        return {"status": "REJECTED", "errors": ["a raw artifact hash is reused by multiple routes"], "routes": routes}
    if rejected:
        return {"status": "REJECTED", "errors": ["one or more submitted routes were rejected"], "routes": routes}
    if len(admitted) != len(contract["required_routes"]):
        return {"status": "INCOMPLETE", "errors": ["all five routes must be admitted before comparison"], "routes": routes}
    manifest = {
        "schema_version": contract["schema_version"],
        "workload_fingerprint": contract["workload_fingerprint"],
        "required_routes": contract["required_routes"],
        "exports": {
            route: load(safe_artifact_path(root, artifacts[route]["artifact_path"]))
            for route in contract["required_routes"]
        },
    }
    from term_order_cross_route import compare_routes
    comparison = compare_routes(load(HERE / "term_order_contract.json"), manifest)
    return {"status": "READY_FOR_CROSS_ROUTE_COMPARISON", "errors": [], "routes": routes, "comparison": comparison}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registry", type=Path, required=True)
    parser.add_argument("--intake-root", type=Path, required=True)
    args = parser.parse_args()
    contract = load(HERE / "fh_l8_external_evidence_intake_contract.json")
    result = assess(contract, load(args.registry), args.intake_root)
    print(json.dumps(result, sort_keys=True, indent=2))
    raise SystemExit(0 if result["status"] == "READY_FOR_CROSS_ROUTE_COMPARISON" else 1)


if __name__ == "__main__":
    main()
