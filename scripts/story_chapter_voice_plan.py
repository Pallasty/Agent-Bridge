#!/usr/bin/env python3
"""Build a non-actuating, provenance-bound chapter voice render plan."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any


TRANSITIONS = {
    "same_paragraph",
    "speaker_turn",
    "paragraph_break",
    "scene_break",
}
LINE_RE = re.compile(r"(?:^|;)line=(\d+)(?:;|$)")
ATTRIBUTED_DIALOGUE_RE = re.compile(r"(?:说|说道|问|答道|回答|喊道|低声说)[：:]?[“\"]")


def _digest(value: Any) -> str:
    payload = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _line_number(event: dict[str, Any]) -> int:
    locator = event.get("source_ref", {}).get("locator", "")
    match = LINE_RE.search(locator)
    if match is None:
        raise ValueError(f"event source line missing:{event.get('event_id', '')}")
    return int(match.group(1))


def _chapter_id(plan: dict[str, Any], line: int) -> str:
    matches = [
        row["chapter_id"]
        for row in plan["chapters"]
        if row.get("selected") is True
        and row["source_span"]["line_start"] <= line
        <= row["source_span"]["line_end"]
    ]
    if len(matches) != 1:
        raise ValueError(f"selected chapter unresolved for line:{line}")
    return matches[0]


def _transition(
    plan: dict[str, Any], current: dict[str, Any], following: dict[str, Any]
) -> str:
    current_line = _line_number(current)
    next_line = _line_number(following)
    if next_line <= current_line:
        raise ValueError("timeline source lines must be strictly increasing")
    if _chapter_id(plan, current_line) != _chapter_id(plan, next_line):
        return "scene_break"
    if next_line - current_line > 1:
        return "paragraph_break"
    if (
        current["utterance"]["speaker_id"]
        != following["utterance"]["speaker_id"]
    ):
        return "speaker_turn"
    return "same_paragraph"


def build_chapter_voice_plan(
    plan: dict[str, Any],
    mapping: dict[str, Any],
    role_acceptance: dict[str, Any],
    pacing_acceptance: dict[str, Any],
) -> dict[str, Any]:
    if plan.get("status") != "story_plan_reviewable":
        raise ValueError("story plan not reviewable")
    if plan["source"]["sha256"] != mapping["source_sha256"]:
        raise ValueError("source SHA-256 mismatch")
    if mapping["mapping_sha256"] != role_acceptance["mapping_sha256"]:
        raise ValueError("mapping SHA-256 mismatch")
    role_claims = role_acceptance.get("claims", {})
    if not all(
        role_claims.get(name) is True
        for name in (
            "owner_accepted_both",
            "voices_distinguishable",
            "chapter_render_ready",
        )
    ):
        raise ValueError("role voices not accepted")
    if pacing_acceptance.get("claims", {}).get("owner_pacing_accepted") is not True:
        raise ValueError("pacing policy not accepted")
    policy_receipt = pacing_acceptance.get("policy", {})
    metadata_keys = {"selection_authority", "freeform_model_guessing"}
    if (
        set(policy_receipt) != TRANSITIONS | metadata_keys
        or policy_receipt.get("selection_authority")
        != "explicit_structural_label"
        or policy_receipt.get("freeform_model_guessing") is not False
    ):
        raise ValueError("pause policy invalid")
    pause_policy = {name: policy_receipt[name] for name in TRANSITIONS}
    if any(
        not isinstance(value, (int, float)) or value < 0 or value > 3
        for value in pause_policy.values()
    ):
        raise ValueError("pause policy invalid")

    roles = {row["speaker_id"]: row for row in mapping["roles"]}
    timeline = sorted(
        plan["voice_scene"]["timeline"], key=lambda row: row["sequence"]
    )
    if not timeline:
        raise ValueError("chapter timeline empty")
    segments = []
    review_queue = []
    for index, event in enumerate(timeline):
        speaker_id = event["utterance"]["speaker_id"]
        role = roles.get(speaker_id)
        if role is None:
            raise ValueError(f"voice mapping missing:{speaker_id}")
        text = event["utterance"]["text"]
        if role.get("role_kind") != "narrator" and ATTRIBUTED_DIALOGUE_RE.search(text):
            review_queue.append(
                {
                    "event_id": event["event_id"],
                    "reason": "attributed_dialogue_requires_source_grounded_split",
                }
            )
        row = {
            "segment_index": index,
            "event_id": event["event_id"],
            "sequence": event["sequence"],
            "source_line": _line_number(event),
            "speaker_id": speaker_id,
            "display_name": role["display_name"],
            "qwen_speaker": role["qwen_speaker"],
            "style_instruction": role["style_instruction"],
            "voice_profile_version": role["voice_profile_version"],
            "text": text,
        }
        if index + 1 < len(timeline):
            transition = _transition(plan, event, timeline[index + 1])
            row["transition_after"] = transition
            row["pause_after_seconds"] = pause_policy[transition]
        segments.append(row)

    chapter_render_ready = not review_queue
    bound = {
        "source_sha256": plan["source"]["sha256"],
        "mapping_sha256": mapping["mapping_sha256"],
        "pause_policy": pause_policy,
        "segments": segments,
        "review_queue": review_queue,
        "chapter_render_ready": chapter_render_ready,
    }
    return {
        "schema": "agent_bridge.story_chapter_voice_plan.v1",
        "status": "chapter_voice_plan_reviewable",
        **bound,
        "plan_sha256": _digest(bound),
        "runtime_effects": {
            "loaded_model": False,
            "rendered_audio": False,
            "played_audio": False,
            "registered_story_command": False,
        },
        "next_gate": (
            "bounded_first_chapter_qwen_render"
            if chapter_render_ready
            else "source_grounded_utterance_segmentation"
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--story-plan", type=Path, required=True)
    parser.add_argument("--mapping", type=Path, required=True)
    parser.add_argument("--role-acceptance", type=Path, required=True)
    parser.add_argument("--pacing-acceptance", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = build_chapter_voice_plan(
        json.loads(args.story_plan.read_text()),
        json.loads(args.mapping.read_text()),
        json.loads(args.role_acceptance.read_text()),
        json.loads(args.pacing_acceptance.read_text()),
    )
    rendered = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.write_text(rendered)
    else:
        print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
