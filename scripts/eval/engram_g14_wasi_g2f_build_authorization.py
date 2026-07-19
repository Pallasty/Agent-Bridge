#!/usr/bin/env python3
"""Emit the deterministic G2F decision receipt; it never invokes Cargo."""
from __future__ import annotations
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CONTRACT = ROOT / "scripts/eval/fixtures/engram_g14_wasi_g2f_build_authorization_v0.json"

def main() -> int:
    contract = json.loads(CONTRACT.read_text())
    print(json.dumps({"gate": contract["gate"], "status": contract["status"], "build_authorized": contract["authorized_successor"]["build_authorized"], "run_authorized": contract["authorized_successor"]["run_authorized"], "verdict": "G2F_DECISION_COMPLETE_AWAITING_G2G_BUILD"}, sort_keys=True, separators=(",", ":")))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
