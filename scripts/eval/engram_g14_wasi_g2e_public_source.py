#!/usr/bin/env python3
"""Emit a deterministic, source-only G2E public evidence receipt.

This program reads committed text.  It neither invokes Cargo nor builds or
executes the fixture; a PASS is static evidence only.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CONTRACT = ROOT / "scripts/eval/fixtures/engram_g14_wasi_g2e_public_source_v0.json"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    contract = json.loads(CONTRACT.read_text())
    paths = [ROOT / value for value in contract["source_paths_in_order"]]
    receipt = {
        "schema": "agent_bridge.engram_g14_wasi_g2e_public_source.receipt.v0",
        "gate": contract["gate"],
        "mode": contract["mode"],
        "source_sha256": {str(path.relative_to(ROOT)): digest(path) for path in paths},
        "compiled_or_built_proof": False,
        "build_authority_granted": False,
        "verdict": contract["decision"]["verdict"],
    }
    print(json.dumps(receipt, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
