#!/usr/bin/env python3
"""S5 static Chinese multi-speaker audition planning and review gates."""

from __future__ import annotations

import argparse
import hashlib
import json
import unicodedata
from pathlib import Path
from typing import Any


SCHEMA = "agent_bridge.story_voice_audition_plan.v1"
REQUIRED_ROLES = {"narrator", "character_lin", "character_su"}
MIN_HUMAN_SCORE = 3
MAX_CER = 0.2


def canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def deterministic_id(prefix: str, value: Any) -> str:
    digest = hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()[:20]
    return f"{prefix}_{digest}"


def validate_backend_matrix(matrix: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    backends = matrix.get("backends")
    if not isinstance(backends, list) or not backends:
        return ["backends_required"]
    ids: set[str] = set()
    for row in backends:
        backend_id = row.get("backend_id")
        if not isinstance(backend_id, str) or not backend_id:
            errors.append("backend_id_required")
            continue
        if backend_id in ids:
            errors.append(f"backend_id_duplicate:{backend_id}")
        ids.add(backend_id)
        if row.get("runtime", {}).get("default_enabled") is not False:
            errors.append(f"default_enabled_forbidden:{backend_id}")
        if row.get("speaker_metadata", {}).get("gender_inference_allowed") is not False:
            errors.append(f"gender_inference_forbidden:{backend_id}")
        license_status = row.get("license", {}).get("status")
        if license_status not in {"verified", "unverified", "restricted"}:
            errors.append(f"license_status_invalid:{backend_id}")
        production_eligible = row.get("promotion", {}).get("production_eligible")
        if license_status != "verified" and production_eligible is not False:
            errors.append(f"unknown_license_must_block_promotion:{backend_id}")
        if not isinstance(row.get("capabilities"), dict):
            errors.append(f"capabilities_required:{backend_id}")
        source = row.get("model_source", {})
        if not source.get("url") or not source.get("artifact_identity"):
            errors.append(f"model_provenance_required:{backend_id}")
    return sorted(set(errors))


def build_audition_plan(request: dict[str, Any]) -> dict[str, Any]:
    roles = request.get("roles", [])
    role_ids = {row.get("role_id") for row in roles}
    if len(roles) != 3 or role_ids != REQUIRED_ROLES:
        raise ValueError("narrator_and_two_characters_required")
    speaker_ids = [row.get("speaker_id") for row in roles]
    if len(set(speaker_ids)) != len(speaker_ids):
        raise ValueError("speaker_id_must_be_distinct")
    if not all(isinstance(item, int) and item >= 0 for item in speaker_ids):
        raise ValueError("speaker_id_must_be_nonnegative_integer")
    version = request.get("voice_profile_version")
    if not isinstance(version, int) or version < 1:
        raise ValueError("voice_profile_version_invalid")
    digest = request.get("model_artifact_sha256")
    if not isinstance(digest, str) or len(digest) != 64:
        raise ValueError("model_artifact_sha256_invalid")
    reference_text = str(request.get("reference_text", "")).strip()
    if not reference_text:
        raise ValueError("reference_text_required")

    role_order = {"narrator": 0, "character_lin": 1, "character_su": 2}
    ordered = sorted(roles, key=lambda row: role_order[row["role_id"]])
    items = []
    for index, row in enumerate(ordered):
        items.append(
            {
                "blind_label": f"voice_{chr(ord('a') + index)}",
                "role_id": row["role_id"],
                "speaker_id": row["speaker_id"],
                "voice_profile_version": version,
                "text": reference_text,
                "render_status": "pending",
            }
        )
    seed = {
        "scene_id": request["scene_id"],
        "backend_id": request["backend_id"],
        "model_artifact_sha256": digest,
        "voice_profile_version": version,
        "items": items,
    }
    return {
        "schema": SCHEMA,
        "plan_id": deterministic_id("audition_plan", seed),
        "status": "audition_plan_ready_no_audio",
        "scene_id": request["scene_id"],
        "backend_id": request["backend_id"],
        "model_artifact_sha256": digest,
        "voice_profile_version": version,
        "items": items,
        "acceptance": {
            "minimum_human_score": MIN_HUMAN_SCORE,
            "maximum_asr_cer": MAX_CER,
            "all_voice_pairs_distinguishable": True,
            "owner_confirmation_required": True,
            "real_person_voice_clone_forbidden": True,
        },
        "runtime_effects": {
            "downloads_models": False,
            "renders_audio": False,
            "plays_audio": False,
            "writes_memory": False,
        },
    }


def _normalized_characters(text: str) -> list[str]:
    return [
        character.casefold()
        for character in unicodedata.normalize("NFKC", text)
        if not character.isspace() and not unicodedata.category(character).startswith("P")
    ]


def character_error_rate(reference: str, transcript: str) -> float:
    expected = _normalized_characters(reference)
    actual = _normalized_characters(transcript)
    if not expected:
        return 0.0 if not actual else 1.0
    previous = list(range(len(actual) + 1))
    for expected_character in expected:
        current = [previous[0] + 1]
        for index, actual_character in enumerate(actual, start=1):
            current.append(
                min(
                    current[-1] + 1,
                    previous[index] + 1,
                    previous[index - 1]
                    + (expected_character != actual_character),
                )
            )
        previous = current
    return previous[-1] / len(expected)


def evaluate_review(review: dict[str, Any]) -> dict[str, Any]:
    blockers: list[str] = []
    items = review.get("items", [])
    required_pairs = {
        frozenset(pair)
        for pair in (
            ("voice_a", "voice_b"),
            ("voice_a", "voice_c"),
            ("voice_b", "voice_c"),
        )
    }
    observed_pairs = {
        frozenset(pair)
        for pair in review.get("pairwise_distinguishable", [])
        if isinstance(pair, list) and len(pair) == 2
    }
    if review.get("owner_confirmed") is not True:
        blockers.append("owner_confirmation_missing")
    if review.get("real_person_voice_clone") is not False:
        blockers.append("real_person_voice_clone_forbidden")
    if len(items) != 3 or {row.get("role_id") for row in items} != REQUIRED_ROLES:
        blockers.append("narrator_and_two_characters_required")
    if len({row.get("speaker_id") for row in items}) != len(items):
        blockers.append("speaker_ids_not_distinct")
    if not required_pairs.issubset(observed_pairs):
        blockers.append("all_voice_pairs_not_distinguishable")

    cers: list[float] = []
    for row in items:
        label = str(row.get("blind_label", "unknown"))
        human = row.get("human", {})
        if human.get("audible") is not True:
            blockers.append(f"human_audibility_missing:{label}")
        for field in ("intelligibility", "naturalness", "role_fit"):
            if human.get(field, 0) < MIN_HUMAN_SCORE:
                blockers.append(f"human_score_below_threshold:{label}:{field}")
        asr = row.get("asr", {})
        cer = character_error_rate(
            str(asr.get("reference", "")),
            str(asr.get("transcript", "")),
        )
        cers.append(cer)
        if cer > MAX_CER:
            blockers.append(f"asr_cer_above_threshold:{label}")
        artifact_sha = row.get("artifact_sha256")
        if not isinstance(artifact_sha, str) or len(artifact_sha) != 64:
            blockers.append(f"artifact_provenance_missing:{label}")

    blockers = sorted(set(blockers))
    return {
        "schema": "agent_bridge.story_voice_audition_review.v1",
        "plan_id": review.get("plan_id"),
        "status": (
            "story_chinese_multispeaker_verified"
            if not blockers
            else "review_incomplete"
        ),
        "blockers": blockers,
        "verified_role_count": len(items) if not blockers else 0,
        "all_pairs_distinguishable": required_pairs.issubset(observed_pairs),
        "max_cer": max(cers, default=1.0),
        "writes_canon": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    for name in ("validate-matrix", "plan", "evaluate"):
        command = subparsers.add_parser(name)
        command.add_argument("input", type=Path)
    args = parser.parse_args()
    value = json.loads(args.input.read_text(encoding="utf-8"))
    if args.command == "validate-matrix":
        errors = validate_backend_matrix(value)
        result = {"valid": not errors, "errors": errors}
    elif args.command == "plan":
        result = build_audition_plan(value)
    else:
        result = evaluate_review(value)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))
    return 0 if result.get("valid", not result.get("blockers")) else 1


if __name__ == "__main__":
    raise SystemExit(main())
