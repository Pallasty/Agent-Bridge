#!/usr/bin/env python3
"""Build a deterministic story-role to Qwen CustomVoice mapping."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


QWEN_CUSTOM_VOICES = {
    "Vivian",
    "Serena",
    "Uncle_Fu",
    "Dylan",
    "Eric",
    "Ryan",
    "Aiden",
    "Ono_Anna",
    "Sohee",
}


def _digest(payload: Any) -> str:
    encoded = json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode()
    return hashlib.sha256(encoded).hexdigest()


def build_mapping(
    plan: dict[str, Any],
    assignments: dict[str, dict[str, str]],
    *,
    approved_qwen_speakers: set[str],
) -> dict[str, Any]:
    cast = plan["cast_registry"]
    expected = {row["speaker_id"] for row in cast}
    missing = sorted(expected - set(assignments))
    extra = sorted(set(assignments) - expected)
    if missing:
        raise ValueError(f"missing voice assignment: {missing}")
    if extra:
        raise ValueError(f"unknown voice assignment: {extra}")

    used: set[str] = set()
    roles = []
    for character in cast:
        assignment = assignments[character["speaker_id"]]
        qwen_speaker = assignment.get("qwen_speaker", "")
        instruction = assignment.get("style_instruction", "").strip()
        if qwen_speaker not in QWEN_CUSTOM_VOICES:
            raise ValueError(f"unsupported Qwen speaker: {qwen_speaker}")
        if qwen_speaker in used:
            raise ValueError(f"qwen speaker reused: {qwen_speaker}")
        if not instruction or len(instruction) > 120:
            raise ValueError("style instruction must contain 1-120 characters")
        used.add(qwen_speaker)
        prior_version = int(character["voice_profile"]["version"])
        authorized = qwen_speaker in approved_qwen_speakers
        roles.append(
            {
                "speaker_id": character["speaker_id"],
                "display_name": character["display_name"],
                "role_kind": character["kind"],
                "qwen_speaker": qwen_speaker,
                "style_instruction": instruction,
                "language": "Chinese",
                "voice_profile_version": prior_version + 1,
                "audition_status": (
                    "owner_accepted" if authorized else "audition_pending"
                ),
                "render_authorized": authorized,
                "stability_key": _digest(
                    {
                        "source_sha256": plan["source"]["sha256"],
                        "speaker_id": character["speaker_id"],
                        "qwen_speaker": qwen_speaker,
                        "profile_version": prior_version + 1,
                    }
                ),
            }
        )
    pending = sorted(
        row["qwen_speaker"]
        for row in roles
        if not row["render_authorized"]
    )
    mapping_payload = {
        "source_sha256": plan["source"]["sha256"],
        "roles": roles,
    }
    return {
        "schema": "agent_bridge.story_voice_mapping.v1",
        "status": (
            "mapping_render_ready"
            if not pending
            else "mapping_reviewable_auditions_pending"
        ),
        "source_sha256": plan["source"]["sha256"],
        "backend": "qwen3_tts_existing_onnx_cpu_int4",
        "model": "Qwen3-TTS-12Hz-1.7B-CustomVoice",
        "mapping_sha256": _digest(mapping_payload),
        "roles": roles,
        "pending_auditions": pending,
        "chapter_render_ready": not pending,
        "fallback_policy": {
            "missing_role": "fail_closed_no_audio",
            "unapproved_voice": "fail_closed_no_audio",
            "generation_reaches_frame_cap": "fail_closed_no_wav",
            "asr_incomplete": "reject_segment",
            "profile_change": "increment_version_and_reaudition",
        },
        "runtime_effects": {
            "loaded_model": False,
            "executed_onnx": False,
            "rendered_audio": False,
            "played_audio": False,
            "wrote_story_plan": False,
            "used_gpu": False,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--assignments", type=Path, required=True)
    parser.add_argument("--approved-speaker", action="append", default=[])
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = build_mapping(
        json.loads(args.plan.read_text()),
        json.loads(args.assignments.read_text()),
        approved_qwen_speakers=set(args.approved_speaker),
    )
    rendered = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.write_text(rendered)
    else:
        print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
