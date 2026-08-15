#!/usr/bin/env python3
"""Build a provenance-bound, non-actuating `/story` integration preflight."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent


def _load_sibling(name: str):
    path = SCRIPT_DIR / f"{name}.py"
    spec = importlib.util.spec_from_file_location(f"_{name}_for_preflight", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load sibling module:{name}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _digest(value: Any) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def segment_cache_key(
    *,
    source_sha256: str,
    voice_plan_sha256: str,
    event_id: str,
    text: str,
    qwen_speaker: str,
    style_instruction: str,
    voice_profile_version: int,
    model_inference_sha256: str,
) -> str:
    """Bind a prospective cache entry to content, voice, and model provenance."""

    return _digest(
        {
            "source_sha256": source_sha256,
            "voice_plan_sha256": voice_plan_sha256,
            "event_id": event_id,
            "text": text,
            "qwen_speaker": qwen_speaker,
            "style_instruction": style_instruction,
            "voice_profile_version": voice_profile_version,
            "model_inference_sha256": model_inference_sha256,
        }
    )


def _validate_evidence(
    *,
    source_sha256: str,
    voice_plan: dict[str, Any],
    mapping: dict[str, Any],
    role_acceptance: dict[str, Any],
    continuity_acceptance: dict[str, Any],
) -> None:
    if voice_plan.get("source_sha256") != source_sha256:
        raise ValueError("story source SHA-256 mismatch")
    if mapping.get("source_sha256") != source_sha256:
        raise ValueError("voice mapping source SHA-256 mismatch")
    if voice_plan.get("mapping_sha256") != mapping.get("mapping_sha256"):
        raise ValueError("voice plan mapping SHA-256 mismatch")
    mapping_payload = {
        "source_sha256": mapping.get("source_sha256"),
        "roles": mapping.get("roles"),
    }
    if _digest(mapping_payload) != mapping.get("mapping_sha256"):
        raise ValueError("voice mapping digest invalid")
    if role_acceptance.get("mapping_sha256") != mapping.get("mapping_sha256"):
        raise ValueError("role acceptance mapping SHA-256 mismatch")
    role_claims = role_acceptance.get("claims", {})
    if not all(
        role_claims.get(claim) is True
        for claim in (
            "owner_accepted_both",
            "voices_distinguishable",
            "chapter_render_ready",
        )
    ):
        raise ValueError("role voices not accepted")
    plan_bound = {
        "source_sha256": voice_plan.get("source_sha256"),
        "mapping_sha256": voice_plan.get("mapping_sha256"),
        "pause_policy": voice_plan.get("pause_policy"),
        "segments": voice_plan.get("segments"),
        "review_queue": voice_plan.get("review_queue"),
        "chapter_render_ready": voice_plan.get("chapter_render_ready"),
    }
    if _digest(plan_bound) != voice_plan.get("plan_sha256"):
        raise ValueError("chapter voice plan digest invalid")
    continuity_claims = continuity_acceptance.get("claims", {})
    if (
        continuity_acceptance.get("status") != "owner_accepted"
        or continuity_acceptance.get("voice_plan_sha256")
        != voice_plan.get("plan_sha256")
        or continuity_claims.get("owner_accepted") is not True
        or continuity_claims.get("cross_chapter_continuity_admitted") is not True
    ):
        raise ValueError("cross-chapter continuity not accepted")


def build_story_command_preflight(
    command: str,
    *,
    voice_plan: dict[str, Any],
    mapping: dict[str, Any],
    role_acceptance: dict[str, Any],
    continuity_acceptance: dict[str, Any],
) -> dict[str, Any]:
    """Resolve one command into render requests without authorizing execution."""

    ingest = _load_sibling("story_static_ingest")
    chapter_render = _load_sibling("story_bounded_chapter_render")
    parsed = ingest.parse_story_command(command)
    source_plan = ingest.ingest_story(Path(parsed["path"]), start=parsed["start"])
    _validate_evidence(
        source_sha256=source_plan["source"]["sha256"],
        voice_plan=voice_plan,
        mapping=mapping,
        role_acceptance=role_acceptance,
        continuity_acceptance=continuity_acceptance,
    )
    chapter_number = (
        source_plan["selection"]["first_chapter"]
        if parsed["start"]["kind"] == "chapter"
        else source_plan["chapters"][0]["ordinal"]
    )
    selected = chapter_render.build_chapter_requests(
        voice_plan, chapter_number=chapter_number
    )
    roles_by_voice = {row["qwen_speaker"]: row for row in mapping["roles"]}
    if len(roles_by_voice) != len(mapping["roles"]):
        raise ValueError("Qwen speaker mapping must be unique")
    model_hash = continuity_acceptance.get("model", {}).get(
        "inference_sha256", ""
    )
    if len(model_hash) != 64:
        raise ValueError("model inference SHA-256 missing")
    render_requests = []
    for request in selected["requests"]:
        role = roles_by_voice.get(request["qwen_speaker"])
        if role is None:
            raise ValueError(f"voice role unresolved:{request['event_id']}")
        if role.get("audition_status") != "owner_accepted":
            accepted_candidates = {
                row.get("qwen_speaker")
                for row in role_acceptance.get("candidates", [])
            }
            if request["qwen_speaker"] not in accepted_candidates:
                raise ValueError(f"voice role not accepted:{request['event_id']}")
        render_requests.append(
            {
                **request,
                "voice_profile_version": role["voice_profile_version"],
                "cache_key": segment_cache_key(
                    source_sha256=source_plan["source"]["sha256"],
                    voice_plan_sha256=voice_plan["plan_sha256"],
                    event_id=request["event_id"],
                    text=request["text"],
                    qwen_speaker=request["qwen_speaker"],
                    style_instruction=request["style_instruction"],
                    voice_profile_version=role["voice_profile_version"],
                    model_inference_sha256=model_hash,
                ),
            }
        )
    bound = {
        "source_sha256": source_plan["source"]["sha256"],
        "mapping_sha256": mapping["mapping_sha256"],
        "voice_plan_sha256": voice_plan["plan_sha256"],
        "model_inference_sha256": model_hash,
        "chapter_number": chapter_number,
        "render_requests": render_requests,
        "assembly_gap_seconds": selected["assembly_gap_seconds"],
        "preceding_scene_gap_seconds": selected["preceding_scene_gap_seconds"],
    }
    return {
        "schema": "agent_bridge.story_command_integration_preflight.v1",
        "status": "story_command_integration_preflight_reviewable",
        "command": {
            "raw": command,
            "source_path": source_plan["source"]["uri"],
            "start": parsed["start"],
            "chapter_number": chapter_number,
            "dry_run": True,
        },
        "provenance": {
            "source_sha256": bound["source_sha256"],
            "mapping_sha256": bound["mapping_sha256"],
            "voice_plan_sha256": bound["voice_plan_sha256"],
            "model_inference_sha256": model_hash,
            "continuity_receipt_status": continuity_acceptance["status"],
        },
        "selection": {
            "selected_segments": len(render_requests),
            "excluded_earlier_segments": selected["excluded_earlier_segments"],
            "excluded_later_segments": selected["excluded_later_segments"],
            "assembly_gap_seconds": selected["assembly_gap_seconds"],
            "preceding_scene_gap_seconds": selected["preceding_scene_gap_seconds"],
        },
        "render_requests": render_requests,
        "preflight_sha256": _digest(bound),
        "execution_authorized": False,
        "runtime_effects": {
            "registered_story_command": False,
            "loaded_model": False,
            "executed_onnx": False,
            "rendered_audio": False,
            "played_audio": False,
            "wrote_memory": False,
            "wrote_cache": False,
        },
        "next_gate": "story_command_static_registration_contract",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--command", required=True)
    parser.add_argument("--voice-plan", type=Path, required=True)
    parser.add_argument("--mapping", type=Path, required=True)
    parser.add_argument("--role-acceptance", type=Path, required=True)
    parser.add_argument("--continuity-acceptance", type=Path, required=True)
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()
    result = build_story_command_preflight(
        args.command,
        voice_plan=json.loads(args.voice_plan.read_text(encoding="utf-8")),
        mapping=json.loads(args.mapping.read_text(encoding="utf-8")),
        role_acceptance=json.loads(args.role_acceptance.read_text(encoding="utf-8")),
        continuity_acceptance=json.loads(
            args.continuity_acceptance.read_text(encoding="utf-8")
        ),
    )
    print(
        json.dumps(
            result,
            ensure_ascii=False,
            indent=2 if args.pretty else None,
            separators=None if args.pretty else (",", ":"),
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
