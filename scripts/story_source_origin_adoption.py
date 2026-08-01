#!/usr/bin/env python3
"""Record dual-remote adoption of the Story source/configuration bundle."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_adoption(
    *,
    local_head: str,
    gitlab_head: str,
    github_head: str,
    configuration_fragment_path: Path,
) -> dict[str, Any]:
    if not (local_head == gitlab_head == github_head):
        raise ValueError("remote adoption mismatch")
    if len(local_head) != 40:
        raise ValueError("expected full commit hash")
    fragment = Path(configuration_fragment_path)
    if not fragment.is_file():
        raise ValueError("configuration fragment missing")

    return {
        "schema": "agent_bridge.story_source_origin_adoption.v1",
        "status": "story_source_origin_adopted",
        "decision": {
            "source_adopted": True,
            "configuration_installed": False,
            "deployment_dry_run_admitted": False,
        },
        "remotes": {
            "adopted_source_tip": local_head,
            "gitlab_master_observed": gitlab_head,
            "github_master_observed": github_head,
            "all_equal": True,
        },
        "configuration": {
            "fragment_path": str(fragment.resolve()),
            "fragment_sha256": _sha256(fragment),
            "fixture_pilot_only": True,
            "installed": False,
        },
        "execution_authorized": False,
        "runtime_effects": {
            "modified_machine_env": False,
            "built_release_binary": False,
            "deployed_binary": False,
            "restarted_mcp": False,
            "refreshed_client": False,
            "called_story_tool": False,
            "rendered_audio": False,
            "played_audio": False,
            "wrote_memory": False,
        },
        "next_gate": "story_fixture_configuration_installation_review",
    }
