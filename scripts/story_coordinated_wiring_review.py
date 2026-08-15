#!/usr/bin/env python3
"""Build the non-actuating S5ZR coordinated story wiring review."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any


TOOL_NAME = "story_command_preflight"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def _adapter_evidence_valid(receipt: dict[str, Any]) -> bool:
    return (
        receipt.get("status") == "isolated_rust_story_mcp_adapter_verified"
        and all(receipt.get("claims", {}).values())
        and all(receipt.get("negative_controls", {}).values())
        and not any(receipt.get("scope", {}).values())
        and not any(receipt.get("runtime_effects", {}).values())
        and receipt.get("next_gate")
        == "coordinated_story_module_and_registry_wiring_review"
    )


def build_review(
    *,
    lib_path: Path,
    registry_path: Path,
    cargo_path: Path,
    adapter_path: Path,
    story_contract_path: Path,
    adapter_receipt_path: Path,
    lib_worktree_overlap: bool,
    registry_worktree_overlap: bool,
    cargo_worktree_overlap: bool,
    active_cargo_processes: int,
) -> dict[str, Any]:
    paths = [
        Path(value)
        for value in (
            lib_path,
            registry_path,
            cargo_path,
            adapter_path,
            story_contract_path,
            adapter_receipt_path,
        )
    ]
    lib_path, registry_path, cargo_path, adapter_path, story_contract_path, adapter_receipt_path = paths

    receipt = _load(adapter_receipt_path)
    if not _adapter_evidence_valid(receipt):
        raise ValueError("S5ZQ adapter evidence invalid")

    registry_source = registry_path.read_text(encoding="utf-8")
    lib_source = lib_path.read_text(encoding="utf-8")
    adapter_source = adapter_path.read_text(encoding="utf-8")
    if re.search(rf"['\"]{re.escape(TOOL_NAME)}['\"]", registry_source):
        raise ValueError(f"tool name collision: {TOOL_NAME}")
    for marker in ("StoryCommandPreflightTool", "StoryMcpConfig", TOOL_NAME):
        if marker not in adapter_source:
            raise ValueError(f"adapter marker missing: {marker}")

    blockers = []
    if lib_worktree_overlap:
        blockers.append("lib_module_tree_overlap_active")
    if registry_worktree_overlap:
        blockers.append("registry_worktree_overlap_active")
    if cargo_worktree_overlap:
        blockers.append("cargo_manifest_overlap_active")
    if active_cargo_processes > 0:
        blockers.append("shared_cargo_activity_active")

    admitted = not blockers
    return {
        "schema": "agent_bridge.story_coordinated_wiring_review.v1",
        "status": "story_coordinated_wiring_review_complete",
        "decision": {
            "selected": (
                "admit_minimal_wiring_implementation_review"
                if admitted
                else "defer_wiring_until_shared_surfaces_clean"
            ),
            "minimal_patch_contract_admitted": True,
            "wiring_implementation_admitted": admitted,
        },
        "evidence": {
            "s5zq_adapter_verified": True,
            "registry_name_collision": False,
            "story_module_currently_exported": bool(
                re.search(r"(?m)^\s*pub\(crate\)\s+mod\s+story_contract\s*;", lib_source)
            ),
            "adapter_module_currently_declared": bool(
                re.search(r"(?m)^\s*mod\s+story\s*;", registry_source)
            ),
            "lib_sha256": _sha256(lib_path),
            "registry_sha256": _sha256(registry_path),
            "cargo_sha256": _sha256(cargo_path),
            "adapter_sha256": _sha256(adapter_path),
            "story_contract_sha256": _sha256(story_contract_path),
            "adapter_receipt_sha256": _sha256(adapter_receipt_path),
            "active_cargo_processes_observed": active_cargo_processes,
        },
        "overlap": {
            "lib_worktree_overlap": lib_worktree_overlap,
            "registry_worktree_overlap": registry_worktree_overlap,
            "cargo_worktree_overlap": cargo_worktree_overlap,
        },
        "blockers": blockers,
        "minimal_patch_contract": {
            "module_tree_declaration": "pub(crate) mod story_contract;",
            "registry_module_declaration": "mod story;",
            "registry_imports": ["StoryCommandPreflightTool", "StoryMcpConfig"],
            "tool_name": TOOL_NAME,
            "tier": "Niche",
            "activation_env": "AB_STORY_COMMAND_PREFLIGHT_ENABLE=1",
            "invalid_enabled_config": "warn_and_leave_tool_unregistered",
            "disabled_config": "leave_tool_unregistered_without_warning",
            "eager_profile_exposure": False,
            "cargo_manifest_change_required": False,
            "required_tests": [
                "disabled_tool_absent",
                "invalid_enabled_config_tool_absent",
                "complete_enabled_config_niche_visible",
                "eager_profiles_tool_absent",
            ],
        },
        "execution_authorized": False,
        "runtime_effects": {
            "modified_module_tree": False,
            "modified_rust_registry": False,
            "modified_cargo_manifest": False,
            "registered_story_command": False,
            "exposed_story_command": False,
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
            else "clean_surface_story_wiring_readiness_recheck"
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    for name in ("lib", "registry", "cargo", "adapter", "story-contract", "adapter-receipt"):
        parser.add_argument(f"--{name}", type=Path, required=True)
    parser.add_argument("--lib-worktree-overlap", action="store_true")
    parser.add_argument("--registry-worktree-overlap", action="store_true")
    parser.add_argument("--cargo-worktree-overlap", action="store_true")
    parser.add_argument("--active-cargo-processes", type=int, default=0)
    args = parser.parse_args()
    result = build_review(
        lib_path=args.lib,
        registry_path=args.registry,
        cargo_path=args.cargo,
        adapter_path=args.adapter,
        story_contract_path=args.story_contract,
        adapter_receipt_path=args.adapter_receipt,
        lib_worktree_overlap=args.lib_worktree_overlap,
        registry_worktree_overlap=args.registry_worktree_overlap,
        cargo_worktree_overlap=args.cargo_worktree_overlap,
        active_cargo_processes=args.active_cargo_processes,
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
