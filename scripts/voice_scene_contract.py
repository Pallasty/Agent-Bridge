#!/usr/bin/env python3
"""Static Voice Scene S0 contract planner and validator.

This module is deliberately non-actuating. It reads JSON and returns validation
or plan projections; it never plays or records audio, writes Agent-Bridge
memory/forum state, mutates runtime configuration, or downloads models.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


SCHEMA_ID = "agent_bridge.voice_scene.v0"
PLAN_SCHEMA_ID = "agent_bridge.voice_scene.plan.v0"
CLAIM_KINDS = (
    "source_truth",
    "observation",
    "inference",
    "simulation_branch",
)
RUNTIME_EFFECT_FIELDS = (
    "emits_audio",
    "records_audio",
    "writes_memory",
    "writes_forum",
    "mutates_runtime",
    "downloads_models",
)


def canonical_json(value: Any) -> str:
    """Return the canonical JSON representation used for stable identifiers."""

    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def deterministic_id(prefix: str, value: Any) -> str:
    """Build a stable content-derived identifier with a bounded readable prefix."""

    normalized_prefix = "".join(
        character if character.isalnum() or character == "_" else "_"
        for character in prefix.strip().lower()
    ).strip("_")
    if not normalized_prefix:
        raise ValueError("identifier prefix must contain an alphanumeric character")
    digest = hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()[:20]
    return f"{normalized_prefix}_{digest}"


def source_fingerprint(content: bytes, *, version: str = "") -> str:
    """Fingerprint exact source bytes plus an explicit edition/version label."""

    digest = hashlib.sha256()
    digest.update(content)
    digest.update(b"\0voice-scene-source-version\0")
    digest.update(version.encode("utf-8"))
    return digest.hexdigest()


def _duplicate_values(rows: list[dict[str, Any]], field: str) -> set[str]:
    seen: set[str] = set()
    duplicates: set[str] = set()
    for row in rows:
        value = row.get(field)
        if not isinstance(value, str):
            continue
        if value in seen:
            duplicates.add(value)
        seen.add(value)
    return duplicates


def _validate_runtime_boundary(scene: dict[str, Any], errors: list[str]) -> None:
    boundary = scene.get("runtime_boundary")
    if not isinstance(boundary, dict):
        errors.append("runtime_boundary_missing")
        return
    for field in RUNTIME_EFFECT_FIELDS:
        if boundary.get(field) is not False:
            errors.append(f"runtime_boundary_forbidden:{field}")


def _validate_branches(
    scene: dict[str, Any],
    event_by_id: dict[str, dict[str, Any]],
    errors: list[str],
) -> tuple[dict[str, dict[str, Any]], str]:
    rows = scene.get("branches")
    branches = rows if isinstance(rows, list) else []
    for duplicate in sorted(_duplicate_values(branches, "branch_id")):
        errors.append(f"duplicate_branch_id:{duplicate}")
    branch_by_id = {
        row["branch_id"]: row
        for row in branches
        if isinstance(row, dict) and isinstance(row.get("branch_id"), str)
    }
    canonical_branch_id = (
        scene.get("scene", {}).get("canonical_branch_id")
        if isinstance(scene.get("scene"), dict)
        else None
    )
    if not isinstance(canonical_branch_id, str) or canonical_branch_id not in branch_by_id:
        errors.append("canonical_branch_missing")
        canonical_branch_id = ""
    elif branch_by_id[canonical_branch_id].get("kind") != "canonical":
        errors.append("canonical_branch_kind_invalid")

    for branch_id, branch in branch_by_id.items():
        parent = branch.get("parent_branch_id")
        fork_event_id = branch.get("fork_event_id")
        if branch.get("kind") == "canonical":
            if parent is not None or fork_event_id is not None:
                errors.append(f"canonical_branch_has_parent:{branch_id}")
            continue
        if not isinstance(parent, str) or parent not in branch_by_id:
            errors.append(f"branch_parent_unknown:{branch_id}")
        if not isinstance(fork_event_id, str) or fork_event_id not in event_by_id:
            errors.append(f"branch_fork_event_unknown:{branch_id}")

        visited = {branch_id}
        cursor = parent
        while isinstance(cursor, str) and cursor in branch_by_id:
            if cursor in visited:
                errors.append(f"branch_cycle:{branch_id}")
                break
            visited.add(cursor)
            cursor = branch_by_id[cursor].get("parent_branch_id")

    return branch_by_id, canonical_branch_id


def _validate_timeline(
    scene: dict[str, Any],
    source_ids: set[str],
    errors: list[str],
) -> dict[str, dict[str, Any]]:
    rows = scene.get("timeline")
    timeline = rows if isinstance(rows, list) else []
    sequences = [row.get("sequence") for row in timeline if isinstance(row, dict)]
    if sequences != list(range(1, len(timeline) + 1)):
        errors.append("timeline_sequence_not_contiguous")
    for field in ("event_id", "idempotency_key"):
        for duplicate in sorted(_duplicate_values(timeline, field)):
            errors.append(f"duplicate_{field}:{duplicate}")

    event_by_id = {
        row["event_id"]: row
        for row in timeline
        if isinstance(row, dict) and isinstance(row.get("event_id"), str)
    }
    for event_id, event in event_by_id.items():
        source_ref = event.get("source_ref")
        if source_ref is not None:
            source_id = (
                source_ref.get("source_id") if isinstance(source_ref, dict) else None
            )
            if source_id not in source_ids:
                errors.append(f"event_source_unknown:{event_id}")
    return event_by_id


def _validate_claims(
    scene: dict[str, Any],
    event_by_id: dict[str, dict[str, Any]],
    branch_by_id: dict[str, dict[str, Any]],
    canonical_branch_id: str,
    errors: list[str],
) -> None:
    rows = scene.get("claims")
    claims = rows if isinstance(rows, list) else []
    for duplicate in sorted(_duplicate_values(claims, "claim_id")):
        errors.append(f"duplicate_claim_id:{duplicate}")
    claim_by_id = {
        row["claim_id"]: row
        for row in claims
        if isinstance(row, dict) and isinstance(row.get("claim_id"), str)
    }

    for claim_id, claim in claim_by_id.items():
        kind = claim.get("kind")
        if kind not in CLAIM_KINDS:
            errors.append(f"claim_kind_invalid:{claim_id}")
        branch_id = claim.get("branch_id")
        if branch_id not in branch_by_id:
            errors.append(f"claim_branch_unknown:{claim_id}")
        evidence_refs = claim.get("evidence_refs")
        if not isinstance(evidence_refs, list) or not evidence_refs:
            errors.append(f"claim_evidence_missing:{claim_id}")
        else:
            for event_id in evidence_refs:
                if event_id not in event_by_id:
                    errors.append(f"claim_evidence_unknown:{claim_id}:{event_id}")

        derived_ids = claim.get("derived_from_claim_ids", [])
        if not isinstance(derived_ids, list):
            errors.append(f"claim_derivation_invalid:{claim_id}")
            continue
        parent_kinds: list[str] = []
        for parent_id in derived_ids:
            parent = claim_by_id.get(parent_id)
            if parent is None:
                errors.append(f"claim_parent_unknown:{claim_id}:{parent_id}")
            else:
                parent_kinds.append(str(parent.get("kind")))
        if kind == "source_truth" and any(
            parent_kind != "source_truth" for parent_kind in parent_kinds
        ):
            errors.append(f"claim_kind_upgrade_forbidden:{claim_id}")
        if kind == "simulation_branch":
            branch = branch_by_id.get(str(branch_id), {})
            if branch_id == canonical_branch_id or branch.get("kind") != "simulation":
                errors.append(f"simulation_claim_requires_simulation_branch:{claim_id}")


def validate_scene(scene: Any) -> list[str]:
    """Return deterministic semantic contract errors for one Voice Scene packet."""

    if not isinstance(scene, dict):
        return ["scene_document_must_be_object"]
    errors: list[str] = []
    if scene.get("schema") != SCHEMA_ID:
        errors.append("schema_id_invalid")

    sources = scene.get("sources")
    source_rows = sources if isinstance(sources, list) else []
    for duplicate in sorted(_duplicate_values(source_rows, "source_id")):
        errors.append(f"duplicate_source_id:{duplicate}")
    source_ids = {
        row["source_id"]
        for row in source_rows
        if isinstance(row, dict) and isinstance(row.get("source_id"), str)
    }

    event_by_id = _validate_timeline(scene, source_ids, errors)
    branch_by_id, canonical_branch_id = _validate_branches(
        scene, event_by_id, errors
    )
    for event_id, event in event_by_id.items():
        branch_id = event.get("branch_id")
        if branch_id not in branch_by_id:
            errors.append(f"event_branch_unknown:{event_id}")
            continue
        target_branch_id = event.get("target_branch_id")
        if (
            branch_by_id[branch_id].get("kind") == "simulation"
            and target_branch_id == canonical_branch_id
        ):
            errors.append(
                f"simulation_writeback_to_canonical_forbidden:{event_id}"
            )

    speakers = scene.get("speakers")
    speaker_rows = speakers if isinstance(speakers, list) else []
    for duplicate in sorted(_duplicate_values(speaker_rows, "speaker_id")):
        errors.append(f"duplicate_speaker_id:{duplicate}")
    speaker_ids = {
        row["speaker_id"]
        for row in speaker_rows
        if isinstance(row, dict) and isinstance(row.get("speaker_id"), str)
    }
    voice_profiles = scene.get("voice_profiles")
    profile_rows = voice_profiles if isinstance(voice_profiles, list) else []
    for duplicate in sorted(_duplicate_values(profile_rows, "voice_profile_id")):
        errors.append(f"duplicate_voice_profile_id:{duplicate}")
    for profile in profile_rows:
        if isinstance(profile, dict) and profile.get("speaker_id") not in speaker_ids:
            errors.append(
                f"voice_profile_speaker_unknown:{profile.get('voice_profile_id', '?')}"
            )

    _validate_claims(
        scene,
        event_by_id,
        branch_by_id,
        canonical_branch_id,
        errors,
    )
    _validate_runtime_boundary(scene, errors)
    return sorted(set(errors))


def plan_summary(scene: dict[str, Any]) -> dict[str, Any]:
    """Return a bounded, non-actuating plan projection for a valid scene."""

    errors = validate_scene(scene)
    if errors:
        raise ValueError("invalid voice scene: " + "; ".join(errors))
    claim_counts = {kind: 0 for kind in CLAIM_KINDS}
    for claim in scene.get("claims", []):
        claim_counts[claim["kind"]] += 1
    boundary = scene["runtime_boundary"]
    return {
        "schema": PLAN_SCHEMA_ID,
        "status": "contract_ready_no_runtime",
        "scene_id": scene["scene"]["scene_id"],
        "mode": scene["scene"]["mode"],
        "source_count": len(scene["sources"]),
        "speaker_count": len(scene["speakers"]),
        "branch_count": len(scene["branches"]),
        "timeline_event_count": len(scene["timeline"]),
        "claim_counts": claim_counts,
        "runtime_effects_enabled": [
            field for field in RUNTIME_EFFECT_FIELDS if boundary.get(field) is True
        ],
    }


def _load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except OSError as error:
        raise ValueError(f"cannot read {path}: {error}") from error
    except json.JSONDecodeError as error:
        raise ValueError(f"invalid JSON in {path}: {error}") from error


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Static Voice Scene S0 contract planner/validator"
    )
    parser.add_argument("operation", choices=("validate", "plan"))
    parser.add_argument("input", type=Path)
    parser.add_argument("--pretty", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    try:
        scene = _load_json(args.input)
        errors = validate_scene(scene)
        if args.operation == "validate":
            payload: dict[str, Any] = {
                "schema": "agent_bridge.voice_scene.validation.v0",
                "valid": not errors,
                "errors": errors,
                "runtime_effects": "none",
            }
            exit_code = 0 if not errors else 1
        elif errors:
            payload = {
                "schema": PLAN_SCHEMA_ID,
                "status": "invalid",
                "errors": errors,
                "runtime_effects": "none",
            }
            exit_code = 1
        else:
            payload = plan_summary(scene)
            exit_code = 0
    except ValueError as error:
        payload = {
            "schema": "agent_bridge.voice_scene.validation.v0",
            "valid": False,
            "errors": [str(error)],
            "runtime_effects": "none",
        }
        exit_code = 1
    print(
        json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            indent=2 if args.pretty else None,
        )
    )
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
