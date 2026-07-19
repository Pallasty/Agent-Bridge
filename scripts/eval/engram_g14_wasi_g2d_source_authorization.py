#!/usr/bin/env python3
"""Render the deterministic G2D source-authorization summary."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CONTRACT = ROOT / "scripts/eval/fixtures/engram_g14_wasi_g2d_source_authorization_v0.json"


def render(contract: dict) -> dict:
    return {
        "schema": "agent_bridge.engram_g14_wasi_g2d_source_authorization_summary.v0",
        "gate": contract["gate"],
        "status": contract["status"],
        "owner_authorization_post": contract["predecessor"]["owner_authorization_post"],
        "G2E_source_path_count": len(contract["authorized_successor"]["allowed_source_paths_in_order"]),
        "source_authoring_authorized": contract["authorized_successor"]["source_authoring_authorized"],
        "build_or_run_authorized": contract["next_gate"]["build_or_run_authorized"],
        "next_gate": contract["next_gate"]["id"],
    }


if __name__ == "__main__":
    print(json.dumps(render(json.loads(CONTRACT.read_text(encoding="utf-8"))), ensure_ascii=True, sort_keys=True, separators=(",", ":")))
