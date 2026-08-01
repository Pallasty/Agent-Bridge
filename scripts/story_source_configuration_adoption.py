#!/usr/bin/env python3
"""Build a hash-bound, non-installed fixture Story configuration packet."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _quote(value: str) -> str:
    return "'" + value.replace("'", "'\"'\"'") + "'"


def render_env(environment: dict[str, str]) -> str:
    return "".join(
        f"export {key}={_quote(value)}\n" for key, value in environment.items()
    )


def build_adoption(
    *,
    source_root: Path,
    evidence_root: Path,
    voice_plan_path: Path,
    mapping_path: Path,
    role_acceptance_path: Path,
    continuity_path: Path,
    source_commit: str,
    origin_commit: str,
    source_commit_in_origin: bool,
    max_source_bytes: int,
    expected_mapping_sha256: str | None = None,
) -> dict[str, Any]:
    source_root = Path(source_root).resolve()
    evidence_root = Path(evidence_root).resolve()
    if not source_root.is_dir():
        raise ValueError(f"source root is not a directory: {source_root}")
    if not evidence_root.is_dir():
        raise ValueError(f"evidence root is not a directory: {evidence_root}")
    if not 1 <= max_source_bytes <= 16 * 1024 * 1024:
        raise ValueError("max source bytes outside bounded pilot range")

    paths = [
        ("VOICE_PLAN", Path(voice_plan_path).resolve()),
        ("MAPPING", Path(mapping_path).resolve()),
        ("ROLE_ACCEPTANCE", Path(role_acceptance_path).resolve()),
        ("CONTINUITY", Path(continuity_path).resolve()),
    ]
    evidence_files = []
    for role, path in paths:
        if not path.is_file() or not path.is_relative_to(evidence_root):
            raise ValueError(f"evidence file is missing or outside evidence root: {path}")
        digest = _sha256(path)
        if role == "MAPPING" and expected_mapping_sha256 not in (None, digest):
            raise ValueError("evidence SHA-256 mismatch: MAPPING")
        evidence_files.append(
            {
                "role": role.lower(),
                "path": str(path),
                "sha256": digest,
                "sha256_verified": True,
            }
        )

    environment: dict[str, str] = {
        "AB_STORY_COMMAND_PREFLIGHT_ENABLE": "1",
        "AB_STORY_SOURCE_ROOT": str(source_root),
        "AB_STORY_SOURCE_MAX_BYTES": str(max_source_bytes),
        "AB_STORY_EVIDENCE_ROOT": str(evidence_root),
    }
    for (role, _), evidence in zip(paths, evidence_files, strict=True):
        environment[f"AB_STORY_{role}_PATH"] = evidence["path"]
        environment[f"AB_STORY_{role}_SHA256"] = evidence["sha256"]

    blockers = [] if source_commit_in_origin else ["source_commit_not_in_origin_master"]
    return {
        "schema": "agent_bridge.story_source_configuration_adoption.v1",
        "status": (
            "story_fixture_configuration_and_source_ready"
            if source_commit_in_origin
            else "story_fixture_configuration_ready_source_pending"
        ),
        "decision": {
            "configuration_adoptable": True,
            "source_adopted": source_commit_in_origin,
            "deployment_dry_run_admitted": source_commit_in_origin,
        },
        "source": {
            "source_commit": source_commit,
            "origin_master_commit": origin_commit,
            "source_commit_in_origin_master": source_commit_in_origin,
        },
        "scope": {
            "fixture_pilot_only": True,
            "general_novel_library_admitted": False,
            "source_root": str(source_root),
            "max_source_bytes": max_source_bytes,
        },
        "environment": environment,
        "evidence_files": evidence_files,
        "blockers": blockers,
        "execution_authorized": False,
        "runtime_effects": {
            "pushed_source": False,
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
        "next_gate": (
            "story_deployment_dry_run_review"
            if source_commit_in_origin
            else "story_source_origin_adoption"
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    for name in (
        "source-root",
        "evidence-root",
        "voice-plan-path",
        "mapping-path",
        "role-acceptance-path",
        "continuity-path",
    ):
        parser.add_argument(f"--{name}", type=Path, required=True)
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--origin-commit", required=True)
    parser.add_argument("--source-commit-in-origin", action="store_true")
    parser.add_argument("--max-source-bytes", type=int, default=1048576)
    parser.add_argument("--render-env", action="store_true")
    args = parser.parse_args()
    result = build_adoption(
        source_root=args.source_root,
        evidence_root=args.evidence_root,
        voice_plan_path=args.voice_plan_path,
        mapping_path=args.mapping_path,
        role_acceptance_path=args.role_acceptance_path,
        continuity_path=args.continuity_path,
        source_commit=args.source_commit,
        origin_commit=args.origin_commit,
        source_commit_in_origin=args.source_commit_in_origin,
        max_source_bytes=args.max_source_bytes,
    )
    print(render_env(result["environment"]) if args.render_env else json.dumps(result, indent=2, ensure_ascii=False), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
