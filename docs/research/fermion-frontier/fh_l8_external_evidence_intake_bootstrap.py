#!/usr/bin/env python3
"""Bootstrap helper for FH-L8 external evidence intake.

Scans an intake directory for candidate raw exports and emits a draft registry
that captures discovered route/file path + sha256 plus required skeleton fields.
The output is intentionally incomplete by default; human review of provenance and
source fields is required before admission.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import defaultdict
from pathlib import Path
from typing import Any, Mapping


HERE = Path(__file__).resolve().parent


def _load(path: Path) -> Mapping[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, Mapping):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def _digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _looks_like_candidate(route: str, payload: Any, contract: Mapping[str, Any]) -> bool:
    if not isinstance(payload, Mapping):
        return False
    if payload.get("route") != route:
        return False
    if payload.get("linear_size") != contract["linear_size"]:
        return False
    if payload.get("trotter_steps") != contract["trotter_steps"]:
        return False
    if payload.get("workload_fingerprint") != contract["workload_fingerprint"]:
        return False
    steps = payload.get("steps")
    return isinstance(steps, list) and bool(steps)


def find_candidates(intake_root: Path, contract: Mapping[str, Any]) -> dict[str, list[Path]]:
    by_route: dict[str, list[Path]] = defaultdict(list)
    for path in intake_root.rglob("*.json"):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError, json.JSONDecodeError):
            continue
        route = payload.get("route") if isinstance(payload, Mapping) else None
        if route in contract["required_routes"] and _looks_like_candidate(route, payload, contract):
            by_route[route].append(path)
    return dict(by_route)


def build_registry(
    contract_path: Path,
    intake_root: Path,
    selected: Mapping[str, Path],
) -> dict:
    contract = _load(contract_path)
    registry = {
        "schema_version": contract["schema_version"],
        "contract_id": contract["contract_id"],
        "workload_fingerprint": contract["workload_fingerprint"],
        "artifacts": {},
    }
    for route, file_path in selected.items():
        relative_path = str(file_path.relative_to(intake_root))
        registration = {
            "artifact_path": relative_path,
            "sha256": _digest(file_path),
            "source_url": "",
            "release_or_commit": "",
            "evidence_class": "PRIMARY_EXTERNAL_RAW_EXPORT",
            "provenance_attestation": "",
            "compiler_identity": "",
            "compiler_version": "",
            "compiler_configuration_sha256": "",
            "environment_lock_sha256": "",
            "route": route,
        }
        # required-registration contract does not include route today, but keeping it in
        # bootstrap output can make manual completion safer.
        registry["artifacts"][route] = registration
    return registry


def summarize(
    candidates: Mapping[str, list[Path]],
    contract: Mapping[str, Any],
    registry: Mapping[str, Any] | None = None,
) -> str:
    lines: list[str] = []
    present = sorted(registry["artifacts"].keys()) if registry else []
    for route in contract["required_routes"]:
        found = sorted(candidates.get(route, []))
        count = len(found)
        if count == 0:
            lines.append(f"{route}: MISSING")
        elif count == 1:
            status = "SELECTED" if route in present else "UNSELECTED"
            lines.append(f"{route}: {status} {found[0]}")
        else:
            listing = ", ".join(str(path) for path in found)
            lines.append(f"{route}: MULTIPLE [{listing}]")
    return "\n".join(lines)


def parse_select_route_file_specs(
    specs: list[str],
    intake_root: Path,
    contract: Mapping[str, Any],
) -> dict[str, Path]:
    selections: dict[str, Path] = {}
    resolved_root = intake_root.resolve()
    for spec in specs:
        route, sep, file_path = spec.partition(":")
        if not sep:
            raise ValueError(f"--select-route-file requires ROUTE:PATH form, got {spec!r}")
        if route not in contract["required_routes"]:
            raise ValueError(f"unknown route in --select-route-file: {route}")
        if route in selections:
            raise ValueError(f"route selected more than once: {route}")
        path = (intake_root / file_path).resolve()
        if not path.is_relative_to(resolved_root):
            raise ValueError(f"selected path must be under intake root: {path}")
        if not path.is_file():
            raise ValueError(f"selected path does not exist: {path}")
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError, json.JSONDecodeError) as error:
            raise ValueError(f"selected path is not readable JSON: {path}: {error}") from error
        if not _looks_like_candidate(route, payload, contract):
            raise ValueError(
                f"selected path does not match route/workload/step candidate shape: {path}"
            )
        selections[route] = path
    return selections


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--contract", type=Path, default=HERE / "fh_l8_external_evidence_intake_contract.json")
    parser.add_argument("--intake-root", type=Path, required=True)
    parser.add_argument(
        "--select-route-file",
        action="append",
        default=[],
        metavar="ROUTE:PATH",
        help="optional fixed selection for a route",
    )
    parser.add_argument("--emit-registry", type=Path)
    parser.add_argument("--no-summary", action="store_true")
    args = parser.parse_args()

    contract = _load(args.contract)
    candidates = find_candidates(args.intake_root, contract)
    selections = parse_select_route_file_specs(
        args.select_route_file, args.intake_root, contract
    )

    registry = build_registry(args.contract, args.intake_root, selections)
    if not args.no_summary:
        print(summarize(candidates, contract, registry))
        print()
        if selections:
            print(f"selected routes: {', '.join(sorted(selections))}")
            print(f"selected count: {len(selections)}")
        missing = [r for r in contract["required_routes"] if r not in selections]
        if missing:
            print(f"missing selections: {', '.join(missing)}")
        else:
            print("all required routes currently selected")
    if args.emit_registry is not None:
        args.emit_registry.write_text(json.dumps(registry, indent=2, sort_keys=True), encoding="utf-8")


if __name__ == "__main__":
    main()
