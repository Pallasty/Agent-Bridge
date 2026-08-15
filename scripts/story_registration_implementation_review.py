#!/usr/bin/env python3
"""Build the fail-closed Rust story MCP registration implementation review."""

from __future__ import annotations

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


def _hardening_valid(receipt: dict[str, Any], story_module_path: Path) -> bool:
    evidence = receipt.get("evidence", {})
    return (
        receipt.get("status") == "rust_story_preflight_adapter_hardened"
        and all(receipt.get("hardening", {}).values())
        and all(receipt.get("negative_controls", {}).values())
        and not any(receipt.get("scope", {}).values())
        and not any(receipt.get("runtime_effects", {}).values())
        and evidence.get("rust_module_sha256") == _sha256(story_module_path)
        and receipt.get("next_gate")
        == "owner_authorized_rust_story_registration_implementation_review"
    )


def build_review(
    *,
    registry_path: Path,
    lib_path: Path,
    story_module_path: Path,
    mcp_server_path: Path,
    hardening_receipt_path: Path,
    registry_worktree_overlap: bool,
    lib_worktree_overlap: bool,
) -> dict[str, Any]:
    registry_path = Path(registry_path)
    lib_path = Path(lib_path)
    story_module_path = Path(story_module_path)
    mcp_server_path = Path(mcp_server_path)
    hardening_receipt_path = Path(hardening_receipt_path)
    registry_source = registry_path.read_text(encoding="utf-8")
    lib_source = lib_path.read_text(encoding="utf-8")
    story_source = story_module_path.read_text(encoding="utf-8")
    server_source = mcp_server_path.read_text(encoding="utf-8")

    if re.search(rf"['\"]{re.escape(TOOL_NAME)}['\"]", registry_source):
        raise ValueError(f"tool name collision: {TOOL_NAME}")
    hardening = _load(hardening_receipt_path)
    if not _hardening_valid(hardening, story_module_path):
        raise ValueError("S5ZO hardening evidence invalid")

    mcp_aborts_future = all(
        marker in server_source
        for marker in ("notifications/cancelled", "h.abort();", "tool.execute(args, &ctx).await")
    )
    if not mcp_aborts_future:
        raise ValueError("MCP cancellation authority not established")
    future_drop_guard_present = (
        "impl Drop for StoryPreflightCancellation" in story_source
        or "StoryPreflightCancelOnDrop" in story_source
    )

    blockers = []
    if not future_drop_guard_present:
        blockers.append("mcp_future_drop_cancellation_guard_missing")
    if registry_worktree_overlap:
        blockers.append("registry_worktree_overlap_active")
    if lib_worktree_overlap:
        blockers.append("lib_module_tree_overlap_active")

    return {
        "schema": "agent_bridge.story_registration_implementation_review.v1",
        "status": "story_registration_implementation_review_complete",
        "decision": {
            "selected": "isolated_adapter_before_registry_wiring",
            "isolated_adapter_implementation_admitted": True,
            "registry_wiring_admitted": False,
        },
        "evidence": {
            "s5zo_hardening_verified": True,
            "current_registry_collision": False,
            "story_module_exported": bool(
                re.search(r"(?m)^\s*(?:pub\([^)]*\)\s+|pub\s+)?mod\s+story_contract\s*;", lib_source)
            ),
            "mcp_cancellation_aborts_tool_future": mcp_aborts_future,
            "future_drop_cancel_guard_present": future_drop_guard_present,
            "registry_worktree_overlap": registry_worktree_overlap,
            "lib_worktree_overlap": lib_worktree_overlap,
            "registry_path": str(registry_path.resolve()),
            "registry_sha256": _sha256(registry_path),
            "lib_path": str(lib_path.resolve()),
            "lib_sha256": _sha256(lib_path),
            "story_module_path": str(story_module_path.resolve()),
            "story_module_sha256": _sha256(story_module_path),
            "mcp_server_path": str(mcp_server_path.resolve()),
            "mcp_server_sha256": _sha256(mcp_server_path),
            "hardening_receipt_path": str(hardening_receipt_path.resolve()),
            "hardening_receipt_sha256": _sha256(hardening_receipt_path),
        },
        "blockers": blockers,
        "proposed_surface": {
            "tool_name": TOOL_NAME,
            "tier": "Niche",
            "toolset_extras": [],
            "activation_env": "AB_STORY_COMMAND_PREFLIGHT_ENABLE",
            "activation_env_required_value": "1",
            "default_exposed": False,
            "codex_essential_exposed": False,
            "codex_voice_exposed": False,
        },
        "configuration_contract": {
            "source_root_env": "AB_STORY_SOURCE_ROOT",
            "source_max_bytes_env": "AB_STORY_SOURCE_MAX_BYTES",
            "evidence_root_env": "AB_STORY_EVIDENCE_ROOT",
            "voice_plan_path_env": "AB_STORY_VOICE_PLAN_PATH",
            "voice_plan_sha256_env": "AB_STORY_VOICE_PLAN_SHA256",
            "mapping_path_env": "AB_STORY_MAPPING_PATH",
            "mapping_sha256_env": "AB_STORY_MAPPING_SHA256",
            "role_acceptance_path_env": "AB_STORY_ROLE_ACCEPTANCE_PATH",
            "role_acceptance_sha256_env": "AB_STORY_ROLE_ACCEPTANCE_SHA256",
            "continuity_path_env": "AB_STORY_CONTINUITY_PATH",
            "continuity_sha256_env": "AB_STORY_CONTINUITY_SHA256",
        },
        "adapter_contract": {
            "isolated_path": "crates/bridge/src/mcp_tools/story.rs",
            "future_drop_cancel_guard_required": True,
            "complete_config_required_before_exposure": True,
            "invalid_arguments_return_tool_error": True,
            "runtime_flags_rejected": True,
            "structured_success_result": True,
        },
        "execution_authorized": False,
        "runtime_effects": {
            "modified_module_tree": False,
            "modified_rust_registry": False,
            "registered_story_command": False,
            "deployed_binary": False,
            "refreshed_client": False,
            "loaded_model": False,
            "rendered_audio": False,
            "played_audio": False,
            "wrote_cache": False,
            "wrote_memory": False,
        },
        "next_gate": "isolated_rust_story_mcp_adapter",
    }
