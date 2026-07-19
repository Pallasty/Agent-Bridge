#!/usr/bin/env python3
"""Render the deterministic G2B artifact-ordering repair receipt."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
CONTRACT_PATH = REPO_ROOT / "scripts/eval/fixtures/engram_g14_wasi_g2b_ordering_repair_v0.json"


def canonical_json(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode("utf-8")


def render(contract: dict[str, Any]) -> dict[str, Any]:
    barriers = contract["barriers_in_order"]
    return {
        "schema": "agent_bridge.engram_g14_wasi_g2b_ordering_repair_receipt.v0",
        "gate": contract["gate"],
        "status": contract["status"],
        "contract_sha256": hashlib.sha256(canonical_json(contract)).hexdigest(),
        "current_state": contract["current_state"],
        "barriers_in_order": [row["id"] for row in barriers],
        "complete_barrier_count": sum(row["currently_complete"] for row in barriers),
        "next_gate": contract["next_gate"]["id"],
        "source_build_run_authority": False,
    }


def main(argv: list[str]) -> int:
    if argv:
        raise ValueError("renderer accepts no arguments")
    contract = json.loads(CONTRACT_PATH.read_bytes())
    sys.stdout.buffer.write(canonical_json(render(contract)) + b"\n")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main(sys.argv[1:]))
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f"engram G2B ordering repair: invalid: {exc}", file=sys.stderr)
        raise SystemExit(2) from None
