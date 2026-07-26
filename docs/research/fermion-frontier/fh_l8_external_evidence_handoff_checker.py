#!/usr/bin/env python3
"""Verify the static FH-L8 five-route external-evidence handoff package."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping


HERE = Path(__file__).resolve().parent
DEFAULT_PACKAGE = HERE / "fh_l8_external_evidence_handoff"


def load(path: Path) -> Mapping[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, Mapping):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def digest(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def validate(package_root: Path = DEFAULT_PACKAGE, source_root: Path = HERE) -> dict[str, Any]:
    errors: list[str] = []
    try:
        manifest = load(package_root / "manifest.json")
        contract = load(source_root / "fh_l8_external_evidence_intake_contract.json")
        plan = load(source_root / "fh_l8_external_source_acquisition_plan.json")
    except (OSError, ValueError, json.JSONDecodeError) as error:
        return {"status": "REJECTED", "errors": [str(error)], "route_count": 0}

    if manifest.get("schema_version") != 1:
        errors.append("manifest schema_version must be 1")
    if manifest.get("package_id") != "FH-L8-EXTERNAL-EVIDENCE-HANDOFF-V1":
        errors.append("unexpected package_id")
    if manifest.get("intake_contract_id") != contract.get("contract_id"):
        errors.append("intake contract id drift")
    if manifest.get("acquisition_plan_id") != plan.get("plan_id"):
        errors.append("acquisition plan id drift")
    for field in ("workload_fingerprint", "linear_size", "trotter_steps"):
        if manifest.get(field) != contract.get(field):
            errors.append(f"manifest {field} does not match intake contract")

    routes = manifest.get("routes")
    required_routes = contract.get("required_routes")
    if not isinstance(routes, list) or routes != required_routes:
        errors.append("manifest routes must exactly match the ordered intake route set")
        routes = []
    plan_routes = {
        request.get("route"): request
        for request in plan.get("route_requests", [])
        if isinstance(request, Mapping)
    }
    if set(plan_routes) != set(required_routes):
        errors.append("acquisition plan route set does not match intake contract")

    source_pins = manifest.get("source_pins")
    if not isinstance(source_pins, Mapping):
        errors.append("source_pins must be an object")
        source_pins = {}
    expected_source_files = {
        "fh_l8_external_evidence_intake_contract.json",
        "fh_l8_external_source_acquisition_plan.json",
        "fh_l8_external_evidence_intake.py",
        "fh_l8_external_evidence_intake_bootstrap.py",
    }
    if set(source_pins) != expected_source_files:
        errors.append("source_pins file set drift")
    for name in sorted(expected_source_files & set(source_pins)):
        path = source_root / name
        if not path.is_file() or digest(path) != source_pins[name]:
            errors.append(f"source pin mismatch: {name}")

    required_fields = set(contract.get("required_registration_fields", []))
    expected_files = {"README.md", "manifest.json"}
    for route in routes:
        expected_files.update(
            {
                f"{route}/REQUEST.md",
                f"{route}/registration.template.json",
            }
        )
        request_path = package_root / route / "REQUEST.md"
        template_path = package_root / route / "registration.template.json"
        try:
            request_text = request_path.read_text(encoding="utf-8")
            registration = load(template_path)
        except (OSError, ValueError, json.JSONDecodeError) as error:
            errors.append(f"{route}: unreadable handoff file: {error}")
            continue
        if route not in request_text:
            errors.append(f"{route}: request does not name its route")
        if contract["workload_fingerprint"] not in request_text:
            errors.append(f"{route}: request does not bind the workload")
        for url in plan_routes.get(route, {}).get("primary_sources", []):
            if url not in request_text:
                errors.append(f"{route}: request omits primary source {url}")
        if registration.get("route") != route:
            errors.append(f"{route}: registration route mismatch")
        if registration.get("artifact_path") != f"exports/{route}.json":
            errors.append(f"{route}: artifact_path placeholder drift")
        if registration.get("evidence_class") != "PRIMARY_EXTERNAL_RAW_EXPORT":
            errors.append(f"{route}: evidence_class placeholder drift")
        if not required_fields.issubset(registration):
            errors.append(f"{route}: registration template omits required fields")
        for field in required_fields - {"artifact_path", "evidence_class"}:
            if registration.get(field) != "":
                errors.append(f"{route}: custody placeholder must remain blank: {field}")

    actual_files = {
        str(path.relative_to(package_root))
        for path in package_root.rglob("*")
        if path.is_file() and "__pycache__" not in path.parts
    }
    if actual_files != expected_files:
        errors.append("handoff package file set drift")

    commands = manifest.get("receiver_commands")
    if not isinstance(commands, Mapping) or set(commands) != {
        "package_check",
        "bootstrap",
        "intake",
    }:
        errors.append("receiver command set drift")
    else:
        if "--select-unique-candidates" not in commands["bootstrap"]:
            errors.append("bootstrap command must opt in to unique-candidate selection")
        if "--registry" not in commands["intake"] or "--intake-root" not in commands["intake"]:
            errors.append("intake command is incomplete")

    nonclaims = manifest.get("nonclaims")
    if not isinstance(nonclaims, list) or len(nonclaims) < 4:
        errors.append("explicit nonclaims are incomplete")

    return {
        "status": "VERIFIED_FH_L8_EXTERNAL_EVIDENCE_HANDOFF_PACKAGE" if not errors else "REJECTED",
        "errors": errors,
        "route_count": len(routes),
        "real_exports_included": False,
        "routes_admitted": 0,
        "cross_route_comparison_authorized": False,
        "full_53_authorized": False,
        "ready_for_benchmark": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package-root", type=Path, default=DEFAULT_PACKAGE)
    args = parser.parse_args()
    result = validate(args.package_root)
    print(json.dumps(result, indent=2, sort_keys=True))
    raise SystemExit(0 if result["status"].startswith("VERIFIED_") else 1)


if __name__ == "__main__":
    main()
