#!/usr/bin/env python3
"""Recheck S5ZR shared-surface freshness without modifying Rust wiring."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def _prior_valid(prior: dict[str, Any]) -> bool:
    decision = prior.get("decision", {})
    return (
        prior.get("status") == "story_coordinated_wiring_review_complete"
        and decision.get("minimal_patch_contract_admitted") is True
        and decision.get("wiring_implementation_admitted") is False
        and prior.get("execution_authorized") is False
        and not any(prior.get("runtime_effects", {}).values())
        and prior.get("next_gate")
        == "clean_surface_story_wiring_readiness_recheck"
    )


def build_recheck(
    *,
    prior_receipt_path: Path,
    lib_path: Path,
    registry_path: Path,
    cargo_path: Path,
    lib_worktree_clean: bool,
    registry_worktree_clean: bool,
    cargo_worktree_clean: bool,
    active_agent_bridge_cargo_processes: int,
) -> dict[str, Any]:
    prior_receipt_path = Path(prior_receipt_path)
    lib_path = Path(lib_path)
    registry_path = Path(registry_path)
    cargo_path = Path(cargo_path)
    prior = _load(prior_receipt_path)
    if not _prior_valid(prior):
        raise ValueError("S5ZR authority invalid")
    if active_agent_bridge_cargo_processes < 0:
        raise ValueError("active process count cannot be negative")

    evidence = prior.get("evidence", {})
    current_hashes = {
        "lib": _sha256(lib_path),
        "registry": _sha256(registry_path),
        "cargo": _sha256(cargo_path),
    }
    unchanged = {
        "lib_hash_unchanged": current_hashes["lib"] == evidence.get("lib_sha256"),
        "registry_hash_unchanged": current_hashes["registry"]
        == evidence.get("registry_sha256"),
        "cargo_hash_unchanged": current_hashes["cargo"]
        == evidence.get("cargo_sha256"),
    }
    unchanged["all_shared_surface_hashes_unchanged"] = all(unchanged.values())

    blockers = []
    if not unchanged["all_shared_surface_hashes_unchanged"]:
        blockers.append("shared_surface_provenance_drift")
    if not lib_worktree_clean:
        blockers.append("lib_module_tree_not_clean")
    if not registry_worktree_clean:
        blockers.append("registry_not_clean")
    if not cargo_worktree_clean:
        blockers.append("cargo_manifest_not_clean")
    if active_agent_bridge_cargo_processes:
        blockers.append("agent_bridge_cargo_activity_active")

    admitted = not blockers
    return {
        "schema": "agent_bridge.story_wiring_readiness_recheck.v1",
        "status": "story_wiring_readiness_recheck_complete",
        "decision": {
            "selected": (
                "admit_minimal_story_wiring_review"
                if admitted
                else "keep_wiring_deferred_shared_surfaces_not_clean"
            ),
            "wiring_implementation_admitted": admitted,
        },
        "freshness": unchanged,
        "evidence": {
            "prior_receipt_sha256": _sha256(prior_receipt_path),
            "current_lib_sha256": current_hashes["lib"],
            "current_registry_sha256": current_hashes["registry"],
            "current_cargo_sha256": current_hashes["cargo"],
            "active_agent_bridge_cargo_processes": active_agent_bridge_cargo_processes,
        },
        "cleanliness": {
            "lib_worktree_clean": lib_worktree_clean,
            "registry_worktree_clean": registry_worktree_clean,
            "cargo_worktree_clean": cargo_worktree_clean,
        },
        "blockers": blockers,
        "execution_authorized": False,
        "runtime_effects": {
            "modified_module_tree": False,
            "modified_rust_registry": False,
            "modified_cargo_manifest": False,
            "registered_story_command": False,
            "deployed": False,
            "client_refreshed": False,
            "loaded_model": False,
            "rendered_audio": False,
            "played_audio": False,
            "wrote_memory": False,
        },
        "next_gate": (
            "minimal_story_wiring_implementation_review"
            if admitted
            else "shared_surface_cleanliness_recheck"
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--prior-receipt", type=Path, required=True)
    parser.add_argument("--lib", type=Path, required=True)
    parser.add_argument("--registry", type=Path, required=True)
    parser.add_argument("--cargo", type=Path, required=True)
    parser.add_argument("--lib-worktree-clean", action="store_true")
    parser.add_argument("--registry-worktree-clean", action="store_true")
    parser.add_argument("--cargo-worktree-clean", action="store_true")
    parser.add_argument("--active-agent-bridge-cargo-processes", type=int, default=0)
    args = parser.parse_args()
    result = build_recheck(
        prior_receipt_path=args.prior_receipt,
        lib_path=args.lib,
        registry_path=args.registry,
        cargo_path=args.cargo,
        lib_worktree_clean=args.lib_worktree_clean,
        registry_worktree_clean=args.registry_worktree_clean,
        cargo_worktree_clean=args.cargo_worktree_clean,
        active_agent_bridge_cargo_processes=args.active_agent_bridge_cargo_processes,
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
