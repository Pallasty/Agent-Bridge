#!/usr/bin/env python3
"""Run FH-L8 external evidence intake and optionally emit a JSON receipt."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import fh_l8_external_evidence_intake as intake


def run(registry: Path, intake_root: Path, output: Path | None = None) -> dict:
    """Evaluate registry + route exports."""
    contract = intake.load(HERE / "fh_l8_external_evidence_intake_contract.json")
    registry_payload = intake.load(registry)
    result = intake.assess(contract, registry_payload, intake_root)
    if output is not None:
        output.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registry", type=Path, required=True)
    parser.add_argument("--intake-root", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = run(args.registry, args.intake_root, args.output)
    print(json.dumps(result, indent=2, sort_keys=True))
    raise SystemExit(0 if result["status"] == "READY_FOR_CROSS_ROUTE_COMPARISON" else 1)


if __name__ == "__main__":
    main()
