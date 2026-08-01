#!/usr/bin/env python3
"""Build a non-actuating Story MCP deployment-adoption decision."""

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


def _source_valid(source: dict[str, Any]) -> bool:
    return (
        source.get("status") == "story_mcp_source_wiring_verified"
        and source.get("source", {}).get("source_registration_wired") is True
        and source.get("execution_authorized") is False
        and not any(source.get("runtime_effects", {}).values())
        and source.get("next_gate") == "story_mcp_deployment_adoption_review"
    )


def build_review(
    *,
    source_receipt_path: Path,
    source_commit: str,
    origin_commit: str,
    source_commit_in_origin: bool,
    installed_binary_sha256: str,
    installed_binary_version: str,
    installed_binary_has_story_marker: bool,
    wrapper_has_story_activation: bool,
    machine_env_has_story_activation: bool,
    installed_mcp_processes: int,
    installed_mcp_processes_with_story_binary: int,
    live_client_tool_observed: bool,
) -> dict[str, Any]:
    source_receipt_path = Path(source_receipt_path)
    source = _load(source_receipt_path)
    if not _source_valid(source):
        raise ValueError("S5ZT source authority invalid")
    for name, value in (
        ("installed_mcp_processes", installed_mcp_processes),
        (
            "installed_mcp_processes_with_story_binary",
            installed_mcp_processes_with_story_binary,
        ),
    ):
        if value < 0:
            raise ValueError(f"{name} cannot be negative")
    if installed_mcp_processes_with_story_binary > installed_mcp_processes:
        raise ValueError("story process count exceeds installed MCP process count")

    activation_configured = (
        wrapper_has_story_activation or machine_env_has_story_activation
    )
    blockers = []
    if not source_commit_in_origin:
        blockers.append("source_commit_not_in_origin_master")
    if not installed_binary_has_story_marker:
        blockers.append("installed_binary_missing_story_marker")
    if not activation_configured:
        blockers.append("story_activation_not_configured")
    if (
        installed_mcp_processes > 0
        and installed_mcp_processes_with_story_binary < installed_mcp_processes
    ):
        blockers.append("running_mcp_processes_use_pre_story_binary")
    if not live_client_tool_observed:
        blockers.append("live_client_tool_not_observed")

    admitted = not blockers
    return {
        "schema": "agent_bridge.story_mcp_deployment_adoption_review.v1",
        "status": "story_mcp_deployment_adoption_review_complete",
        "decision": {
            "selected": (
                "admit_client_refresh_review"
                if admitted
                else "defer_deployment_until_source_and_configuration_adopted"
            ),
            "deployment_admitted": admitted,
            "client_refresh_admitted": admitted,
        },
        "source_adoption": {
            "source_commit": source_commit,
            "origin_master_commit": origin_commit,
            "source_commit_in_origin_master": source_commit_in_origin,
            "source_receipt_sha256": _sha256(source_receipt_path),
        },
        "binary_adoption": {
            "installed_binary_sha256": installed_binary_sha256,
            "installed_binary_version": installed_binary_version,
            "installed_binary_has_story_marker": installed_binary_has_story_marker,
        },
        "configuration_adoption": {
            "wrapper_has_story_activation": wrapper_has_story_activation,
            "machine_env_has_story_activation": machine_env_has_story_activation,
            "activation_configured": activation_configured,
        },
        "client_adoption": {
            "installed_mcp_processes": installed_mcp_processes,
            "installed_mcp_processes_with_story_binary": installed_mcp_processes_with_story_binary,
            "live_client_tool_observed": live_client_tool_observed,
        },
        "blockers": blockers,
        "execution_authorized": False,
        "runtime_effects": {
            "fetched_remote": False,
            "built_release_binary": False,
            "backed_up_binary": False,
            "deployed_binary": False,
            "modified_wrapper": False,
            "modified_machine_env": False,
            "restarted_mcp": False,
            "refreshed_client": False,
            "called_story_tool": False,
            "rendered_audio": False,
            "played_audio": False,
            "wrote_memory": False,
        },
        "next_gate": (
            "owner_authorized_story_mcp_client_refresh"
            if admitted
            else "story_source_origin_and_configuration_adoption"
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-receipt", type=Path, required=True)
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--origin-commit", required=True)
    parser.add_argument("--source-commit-in-origin", action="store_true")
    parser.add_argument("--installed-binary-sha256", required=True)
    parser.add_argument("--installed-binary-version", required=True)
    parser.add_argument("--installed-binary-has-story-marker", action="store_true")
    parser.add_argument("--wrapper-has-story-activation", action="store_true")
    parser.add_argument("--machine-env-has-story-activation", action="store_true")
    parser.add_argument("--installed-mcp-processes", type=int, required=True)
    parser.add_argument(
        "--installed-mcp-processes-with-story-binary", type=int, required=True
    )
    parser.add_argument("--live-client-tool-observed", action="store_true")
    args = parser.parse_args()
    result = build_review(
        source_receipt_path=args.source_receipt,
        source_commit=args.source_commit,
        origin_commit=args.origin_commit,
        source_commit_in_origin=args.source_commit_in_origin,
        installed_binary_sha256=args.installed_binary_sha256,
        installed_binary_version=args.installed_binary_version,
        installed_binary_has_story_marker=args.installed_binary_has_story_marker,
        wrapper_has_story_activation=args.wrapper_has_story_activation,
        machine_env_has_story_activation=args.machine_env_has_story_activation,
        installed_mcp_processes=args.installed_mcp_processes,
        installed_mcp_processes_with_story_binary=args.installed_mcp_processes_with_story_binary,
        live_client_tool_observed=args.live_client_tool_observed,
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
