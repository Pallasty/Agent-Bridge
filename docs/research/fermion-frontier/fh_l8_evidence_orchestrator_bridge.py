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

    return {
        "intake": intake_result,
        "cross_route_snapshot": cross_route_snapshot,
        "evidence": evidence_result,
        "summary": {
            "intake_status": intake_result["status"],
            "evidence_status": evidence_result["status"],
            "cross_route_status": cross_route_snapshot["status"],
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registry", type=Path, required=True)
    parser.add_argument("--intake-root", type=Path, required=True)
    parser.add_argument(
        "--evidence-manifest",
        type=Path,
        default=HERE / "evidence_manifest_source_snapshot.json",
    )
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    result = evaluate_bridge(args.registry, args.intake_root, args.evidence_manifest)
    if args.output is not None:
        args.output.write_text(
            json.dumps(result, indent=2, sort_keys=True),
            encoding="utf-8",
        )
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
