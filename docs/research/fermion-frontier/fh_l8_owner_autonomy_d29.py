#!/usr/bin/env python3
"""Minimal owner-scoped authorization policy for reversible FH-L8 research."""
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
CONTRACT = HERE / "fh_l8_owner_autonomy_d29_contract.json"


def policy() -> dict:
    value = json.loads(CONTRACT.read_text(encoding="utf-8"))
    expected = {
        "schema_version": 1,
        "contract_id": "FH-L8-INDEPENDENT-REFERENCE-D29-OWNER-AUTONOMY-V1",
        "authorization_mode": "OWNER_SCOPED_AUTONOMY_FOR_REVERSIBLE_RESEARCH",
        "supersedes_hard_external_signer_gates": ["D27", "D28", "D29-signed-bundle"],
        "minimum_controls": {"source_hash_binding": True, "action_count_cap": True, "resource_ceiling": True, "isolated_scratch": True, "receipt": True},
        "allowed_next_action": {"kernel_calls": 1, "packed_q3_reads": 0, "full_shard_runs": 0},
        "full_53_scientific_execution_authorized": False,
        "next_gate": "OWNER_SCOPED_SINGLE_MICRO_ACTION_PREFLIGHT",
    }
    if value != expected:
        raise ValueError("D29 owner autonomy contract drift")
    return {"status": "VERIFIED_D29_OWNER_SCOPED_REVERSIBLE_AUTONOMY", **value, "scientific_action_calls": 0}
