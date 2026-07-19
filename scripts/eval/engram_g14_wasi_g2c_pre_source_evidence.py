#!/usr/bin/env python3
"""Render the deterministic G2C B0 completion summary."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
CONTRACT = ROOT / "scripts/eval/fixtures/engram_g14_wasi_g2c_pre_source_evidence_v0.json"


def render(contract: dict[str, Any]) -> dict[str, Any]:
    requirements = contract["B0_requirements_in_order"]
    return {
        "schema": "agent_bridge.engram_g14_wasi_g2c_pre_source_summary.v0",
        "gate": contract["gate"],
        "status": contract["status"],
        "B0_requirement_count": len(requirements),
        "B0_closed_requirement_count": sum(row["state"].startswith("CLOSED_") for row in requirements),
        "B0_complete": contract["barriers"]["B0_PRE_SOURCE"]["complete"],
        "B1_complete": contract["barriers"]["B1_POST_SOURCE_PRE_BUILD"]["complete"],
        "B2_complete": contract["barriers"]["B2_POST_BUILD_PRE_RUN"]["complete"],
        "source_build_run_or_dependency_promotion_authorized": contract["decision"][
            "source_build_run_or_dependency_promotion_authorized"
        ],
        "next_gate": contract["decision"]["only_permitted_successor"],
        "automatic_transition": contract["next_gate"]["automatic_transition"],
    }


def main() -> None:
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    print(json.dumps(render(contract), ensure_ascii=True, sort_keys=True, separators=(",", ":")))


if __name__ == "__main__":
    main()
