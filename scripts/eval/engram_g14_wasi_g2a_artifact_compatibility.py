#!/usr/bin/env python3
"""Render the bounded receipt for the public-static G2A evidence review."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
CONTRACT_PATH = REPO_ROOT / "scripts/eval/fixtures/engram_g14_wasi_g2a_artifact_compatibility_v0.json"
CONTRACT_SCHEMA = "agent_bridge.engram_g14_wasi_g2a_artifact_compatibility.v0"
RECEIPT_SCHEMA = "agent_bridge.engram_g14_wasi_g2a_artifact_compatibility_receipt.v0"


class ReviewError(RuntimeError):
    """Closed validation error for this no-run renderer."""


def canonical_json(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode("utf-8")


def load_contract() -> dict[str, Any]:
    value = json.loads(CONTRACT_PATH.read_bytes())
    if not isinstance(value, dict) or value.get("schema") != CONTRACT_SCHEMA:
        raise ReviewError("unexpected contract schema")
    return value


def render_receipt(contract: dict[str, Any]) -> dict[str, Any]:
    decision = contract["decision"]
    evidence = contract["ordered_requirement_review"]
    return {
        "schema": RECEIPT_SCHEMA,
        "gate": contract["gate"],
        "status": contract["status"],
        "verdict": decision["verdict"],
        "contract_sha256": hashlib.sha256(canonical_json(contract)).hexdigest(),
        "requirement_count": len(evidence),
        "closed_count": sum(row["state"] == "CLOSED_STATIC" for row in evidence),
        "partial_count": sum(row["state"] == "PARTIAL" for row in evidence),
        "conditional_count": sum(row["state"] == "CONDITIONAL" for row in evidence),
        "missing_count": sum(row["state"] == "MISSING" for row in evidence),
        "ordered_gate_satisfiable_before_source": contract["causal_order_audit"]["ordered_gate_satisfiable_before_source"],
        "component_source_present": contract["scope"]["component_source_present"],
        "component_built_or_run": contract["scope"]["component_built_or_run"],
        "runtime_or_dependency_adopted": contract["scope"]["runtime_or_dependency_adopted"],
        "authority_class": contract["scope"]["authority_class"],
        "only_permitted_successor": decision["only_permitted_successor"],
    }


def main(argv: list[str]) -> int:
    if argv:
        raise ReviewError("renderer accepts no arguments")
    encoded = canonical_json(render_receipt(load_contract()))
    if len(encoded) > 4096:
        raise ReviewError("receipt exceeds public bound")
    sys.stdout.buffer.write(encoded + b"\n")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main(sys.argv[1:]))
    except (OSError, ValueError, KeyError, TypeError, ReviewError) as exc:
        print(f"engram G1.4 G2A review: invalid: {exc}", file=sys.stderr)
        raise SystemExit(2) from None
