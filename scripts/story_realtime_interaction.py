#!/usr/bin/env python3
"""S4 owner-gated push-to-talk orchestration for Voice Scene story sessions."""

from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
from typing import Any, Callable


TURN_SCHEMA = "agent_bridge.story_realtime_turn.v1"
RETENTION_POLICIES = {"none", "session", "durable_with_owner_review"}


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


def _character_state_module():
    path = Path(__file__).with_name("story_character_state.py")
    spec = importlib.util.spec_from_file_location(
        "story_character_state_for_realtime", path
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("character_state_module_unavailable")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def route_character(
    transcript: str,
    *,
    default_character_id: str,
) -> dict[str, Any]:
    """Use an explicit addressee when known, otherwise retain session default."""

    display_hints = {
        "林默": "character_lin",
        "苏岚": "character_su",
    }
    for name, character_id in display_hints.items():
        if name in transcript:
            return {
                "character_id": character_id,
                "basis": "explicit_name",
                "matched_text": name,
            }
    return {
        "character_id": default_character_id,
        "basis": "session_default",
        "matched_text": None,
    }


def _retention_projection(
    policy: str,
    capture_receipt: dict[str, Any],
    transcript: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    if policy not in RETENTION_POLICIES:
        raise ValueError(f"retention_policy_invalid:{policy}")
    projected = dict(transcript)
    if policy == "none":
        path = Path(str(capture_receipt.get("path", "")))
        if path.is_file():
            path.unlink()
        projected["text"] = None
        return (
            {
                "policy": policy,
                "capture_retained": False,
                "transcript_retained": False,
                "withdrawal_available": False,
            },
            projected,
        )
    return (
        {
            "policy": policy,
            "capture_retained": True,
            "transcript_retained": True,
            "withdrawal_available": True,
        },
        projected,
    )


def withdraw_artifacts(
    paths: list[Path],
    *,
    owner_authorized: bool,
) -> dict[str, Any]:
    """Delete only explicitly named session artifacts after owner authorization."""

    if not owner_authorized:
        raise PermissionError("withdrawal_owner_authorization_required")
    removed: list[str] = []
    missing: list[str] = []
    for path in dict.fromkeys(Path(item) for item in paths):
        if path.is_dir():
            raise ValueError(f"withdrawal_directory_forbidden:{path}")
        if path.is_file():
            path.unlink()
            removed.append(str(path))
        else:
            missing.append(str(path))
    return {
        "schema": "agent_bridge.story_artifact_withdrawal.v1",
        "status": "withdrawn",
        "removed_count": len(removed),
        "removed_paths": removed,
        "missing_paths": missing,
    }


def _failure_receipt(
    *,
    turn_id: str,
    session_id: str,
    player_position_ms: int,
    cursor_sequence: int,
    stage: str,
    error: str,
    capture_receipt: dict[str, Any],
    transcript: dict[str, Any],
    retention_policy: str,
) -> dict[str, Any]:
    retention, projected_transcript = _retention_projection(
        retention_policy, capture_receipt, transcript
    )
    return {
        "schema": TURN_SCHEMA,
        "turn_id": turn_id,
        "session_id": session_id,
        "status": "failed_recovered",
        "cursor_sequence": cursor_sequence,
        "failure": {"stage": stage, "error": error},
        "transcript": projected_transcript,
        "retention": retention,
        "playback": {
            "paused_at_ms": player_position_ms,
            "resumed_at_ms": player_position_ms,
        },
        "overlap_detected": False,
        "memory_proposal": None,
    }


def run_turn(
    *,
    session_id: str,
    player_position_ms: int,
    cursor_sequence: int,
    canon: list[dict[str, Any]],
    default_character_id: str,
    owner_microphone_authorized: bool,
    owner_output_authorized: bool,
    retention_policy: str,
    capture: Callable[[dict[str, Any]], dict[str, Any]],
    asr: Callable[[dict[str, Any]], dict[str, Any]],
    generate_response: Callable[[dict[str, Any]], str],
    tts: Callable[[dict[str, Any]], dict[str, Any]],
    player: Any,
) -> dict[str, Any]:
    """Execute one bounded PTT turn and always restore the exact story position."""

    if not owner_microphone_authorized:
        raise PermissionError("microphone_owner_authorization_required")
    if retention_policy not in RETENTION_POLICIES:
        raise ValueError(f"retention_policy_invalid:{retention_policy}")

    turn_seed = {
        "session_id": session_id,
        "player_position_ms": player_position_ms,
        "cursor_sequence": cursor_sequence,
    }
    turn_id = deterministic_id("turn", turn_seed)
    timeline = ["story_playing"]
    capture_receipt: dict[str, Any] = {}
    transcript: dict[str, Any] = {
        "ok": False,
        "text": None,
        "language": None,
        "stability": "unavailable",
        "confidence": 0.0,
        "source_audio_sha256": None,
    }

    player.pause(player_position_ms)
    timeline.extend(["story_paused", "capture_requested"])
    current_stage = "capture"
    try:
        capture_receipt = capture(
            {
                "session_id": session_id,
                "turn_id": turn_id,
                "capture_mode": "push_to_talk",
                "owner_authorized": True,
                "open_microphone": False,
            }
        )
        if capture_receipt.get("ok") is not True:
            player.resume(player_position_ms)
            return _failure_receipt(
                turn_id=turn_id,
                session_id=session_id,
                player_position_ms=player_position_ms,
                cursor_sequence=cursor_sequence,
                stage="capture",
                error=str(capture_receipt.get("error", "capture_failed")),
                capture_receipt=capture_receipt,
                transcript=transcript,
                retention_policy=retention_policy,
            )
        timeline.extend(["capture_complete", "asr_requested"])
        current_stage = "asr"
        transcript = asr(capture_receipt)
        if transcript.get("ok") is not True:
            player.resume(player_position_ms)
            return _failure_receipt(
                turn_id=turn_id,
                session_id=session_id,
                player_position_ms=player_position_ms,
                cursor_sequence=cursor_sequence,
                stage="asr",
                error=str(transcript.get("error", "asr_failed")),
                capture_receipt=capture_receipt,
                transcript=transcript,
                retention_policy=retention_policy,
            )

        transcript_text = str(transcript.get("text", "")).strip()
        if not transcript_text:
            player.resume(player_position_ms)
            return _failure_receipt(
                turn_id=turn_id,
                session_id=session_id,
                player_position_ms=player_position_ms,
                cursor_sequence=cursor_sequence,
                stage="asr",
                error="asr_empty_transcript",
                capture_receipt=capture_receipt,
                transcript=transcript,
                retention_policy=retention_policy,
            )
        timeline.extend(["asr_complete", "character_routed"])
        route = route_character(
            transcript_text,
            default_character_id=default_character_id,
        )
        routed_question = transcript_text
        if route["matched_text"]:
            routed_question = routed_question.replace(route["matched_text"], "", 1)
            routed_question = routed_question.lstrip("，,：: ")
        character_state = _character_state_module()
        grounded = character_state.story_ask(
            canon,
            character_id=route["character_id"],
            question=routed_question,
            cursor_sequence=cursor_sequence,
        )
        timeline.append("knowledge_gate_complete")
        candidate = generate_response(
            {
                "turn_id": turn_id,
                "character_id": route["character_id"],
                "question": routed_question,
                "grounded_answer": grounded["answer"],
                "evidence_event_ids": grounded["evidence_event_ids"],
                "claim_kind": grounded["claim_kind"],
            }
        )
        falsifier = character_state.spoiler_falsifier(
            candidate,
            canon,
            character_id=route["character_id"],
            cursor_sequence=cursor_sequence,
        )
        response_text = falsifier["safe_response"]
        response_claim_kind = (
            "observation" if falsifier["violations"] else grounded["claim_kind"]
        )
        timeline.extend(["spoiler_gate_complete", "tts_requested"])
        current_stage = "tts"
        tts_receipt = tts(
            {
                "turn_id": turn_id,
                "character_id": route["character_id"],
                "text": response_text,
                "evidence_event_ids": grounded["evidence_event_ids"],
                "claim_kind": response_claim_kind,
            }
        )
        if tts_receipt.get("ok") is not True:
            player.resume(player_position_ms)
            return _failure_receipt(
                turn_id=turn_id,
                session_id=session_id,
                player_position_ms=player_position_ms,
                cursor_sequence=cursor_sequence,
                stage="tts",
                error=str(tts_receipt.get("error", "tts_failed")),
                capture_receipt=capture_receipt,
                transcript=transcript,
                retention_policy=retention_policy,
            )
        if tts_receipt.get("verified_to") != "machine_audio_artifact":
            player.resume(player_position_ms)
            return _failure_receipt(
                turn_id=turn_id,
                session_id=session_id,
                player_position_ms=player_position_ms,
                cursor_sequence=cursor_sequence,
                stage="tts",
                error="tts_receipt_not_machine_verified",
                capture_receipt=capture_receipt,
                transcript=transcript,
                retention_policy=retention_policy,
            )
        timeline.append("tts_complete")
        audio_emitted = False
        if owner_output_authorized:
            player.emit_response(tts_receipt["path"])
            audio_emitted = True
            timeline.append("response_emitted")
        else:
            timeline.append("response_output_gated")
        player.resume(player_position_ms)
        timeline.append("story_resumed")
    except TimeoutError as error:
        player.resume(player_position_ms)
        return _failure_receipt(
            turn_id=turn_id,
            session_id=session_id,
            player_position_ms=player_position_ms,
            cursor_sequence=cursor_sequence,
            stage=current_stage,
            error=str(error) or f"{current_stage}_timeout",
            capture_receipt=capture_receipt,
            transcript=transcript,
            retention_policy=retention_policy,
        )
    except Exception:
        player.resume(player_position_ms)
        raise

    branch_id = deterministic_id(
        "branch_interaction", {"session_id": session_id, "turn_id": turn_id}
    )
    memory_proposal = {
        "event_id": deterministic_id(
            "interaction", {"turn_id": turn_id, "text": transcript_text}
        ),
        "kind": "interaction",
        "branch_id": branch_id,
        "target_branch_id": branch_id,
        "character_id": route["character_id"],
        "listener_text": transcript_text,
        "response_text": response_text,
        "evidence_event_ids": grounded["evidence_event_ids"],
        "idempotency_key": f"{session_id}:{turn_id}",
        "writes_canon": False,
        "write_posture": "proposal_only_owner_review_required",
    }
    retention, projected_transcript = _retention_projection(
        retention_policy, capture_receipt, transcript
    )
    return {
        "schema": TURN_SCHEMA,
        "turn_id": turn_id,
        "session_id": session_id,
        "status": (
            "completed"
            if audio_emitted
            else "response_rendered_output_gated"
        ),
        "cursor_sequence": cursor_sequence,
        "capture": {
            "mode": "push_to_talk",
            "owner_authorized": True,
            "sha256": capture_receipt["sha256"],
            "duration_ms": capture_receipt["duration_ms"],
        },
        "transcript": projected_transcript,
        "route": route,
        "response": {
            "text": response_text,
            "claim_kind": response_claim_kind,
            "evidence_event_ids": grounded["evidence_event_ids"],
            "spoiler_blocked": bool(falsifier["violations"]),
            "audio_emitted": audio_emitted,
            "artifact_sha256": tts_receipt["sha256"],
            "backend": tts_receipt["backend"],
            "model": tts_receipt["model"],
            "voice_profile_version": tts_receipt["voice_profile_version"],
            "human_audibility": "pending" if audio_emitted else "not_emitted",
        },
        "playback": {
            "paused_at_ms": player_position_ms,
            "resumed_at_ms": player_position_ms,
        },
        "timeline": timeline,
        "overlap_detected": False,
        "retention": retention,
        "memory_proposal": memory_proposal,
    }
