#!/usr/bin/env python3
"""Render the deterministic public receipt for the G1.4 clock review.

This module performs no native policy application, process launch, network
access, clock read, entropy read, or repository write.  It loads one fixed
public JSON contract and emits one bounded deterministic receipt.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
CONTRACT_PATH = (
    REPO_ROOT / "scripts/eval/fixtures/engram_g14_strong_clock_isolation_review_v0.json"
)
CONTRACT_SCHEMA = "agent_bridge.engram_g14_strong_clock_isolation_review.v0"
RECEIPT_SCHEMA = "agent_bridge.engram_g14_strong_clock_isolation_review_receipt.v0"


class ReviewError(RuntimeError):
    """Closed validation error for the static review renderer."""


def canonical_json(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def load_contract() -> dict[str, Any]:
    raw = CONTRACT_PATH.read_bytes()
    value = json.loads(raw)
    if not isinstance(value, dict):
        raise ReviewError("contract must be a JSON object")
    if value.get("schema") != CONTRACT_SCHEMA:
        raise ReviewError("unexpected contract schema")
    return value


def render_receipt(contract: dict[str, Any]) -> dict[str, Any]:
    matrix = contract["candidate_matrix_in_order"]
    rejected = [
        row
        for row in matrix
        if isinstance(row.get("decision"), str) and row["decision"].startswith("REJECT")
    ]
    feasibility = [
        row
        for row in matrix
        if row.get("decision")
        in {
            "PRIMARY_SYNTHETIC_FEASIBILITY_CANDIDATE",
            "NATIVE_COMPATIBILITY_FALLBACK_CANDIDATE",
        }
    ]
    decision = contract["decision"]
    scope = contract["scope"]
    acceptance = contract["acceptance_integrity"]
    return {
        "schema": RECEIPT_SCHEMA,
        "mode": contract["mode"],
        "verdict": decision["verdict"],
        "authority_class": scope["authority_class"],
        "contract_sha256": hashlib.sha256(canonical_json(contract)).hexdigest(),
        "reviewed_candidate_count": len(matrix),
        "rejected_candidate_count": len(rejected),
        "conditional_feasibility_candidate_count": len(feasibility),
        "primary_candidate": decision["primary_candidate"],
        "native_compatibility_fallback": decision["native_compatibility_fallback"],
        "mandatory_overlay": decision["mandatory_overlay"],
        "current_wall_clock_deny_canary": decision["current_wall_clock_deny_canary"],
        "human_security_audit_required_before_adoption": decision[
            "semantic_change_requires_human_security_audit"
        ],
        "checker_self_authenticating": acceptance["checker_self_authenticating"],
        "standalone_checker_result_is_acceptance_authority": acceptance[
            "standalone_checker_result_is_acceptance_authority"
        ],
        "out_of_band_acceptance_pin_required": acceptance[
            "independent_out_of_band_commit_and_file_hash_pin_required"
        ],
        "no_authority_before_verified_pin": acceptance[
            "no_authority_before_verified_pin"
        ],
        "implementation_authorized": decision["implementation_authorized"],
        "synthetic_feasibility_run_authorized": decision[
            "synthetic_feasibility_run_authorized"
        ],
        "production_admissible": scope["production_admissible"],
        "g1_4_execution_open": decision["g1_4_execution_open"],
    }


def main(argv: list[str]) -> int:
    if argv:
        raise ReviewError("this renderer accepts no arguments")
    contract = load_contract()
    receipt = render_receipt(contract)
    encoded = canonical_json(receipt)
    if len(encoded) > 2048:
        raise ReviewError("receipt exceeds the 2048-byte public bound")
    sys.stdout.buffer.write(encoded + b"\n")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main(sys.argv[1:]))
    except (OSError, ValueError, KeyError, TypeError, ReviewError) as exc:
        print(f"engram G1.4 clock review: invalid: {exc}", file=sys.stderr)
        raise SystemExit(2) from None
