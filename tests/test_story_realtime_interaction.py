from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "story_realtime_interaction.py"
SCHEMA_PATH = (
    ROOT
    / "docs"
    / "design"
    / "voice-scene"
    / "realtime_interaction.schema.json"
)


def load_module():
    spec = importlib.util.spec_from_file_location(
        "story_realtime_interaction", MODULE_PATH
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def canon() -> list[dict]:
    return [
        {
            "event_id": "canon_001",
            "sequence": 1,
            "branch_id": "branch_canonical",
            "kind": "canon",
            "text": "林默走进旧车站。",
            "known_by": ["character_lin"],
            "source_ref": {
                "source_id": "source_story",
                "locator": "chapter=1;line=3",
                "digest": "1" * 64,
            },
        },
        {
            "event_id": "canon_002",
            "sequence": 2,
            "branch_id": "branch_canonical",
            "kind": "canon",
            "text": "钥匙藏在车站时钟下面。",
            "known_by": ["character_lin"],
            "source_ref": {
                "source_id": "source_story",
                "locator": "chapter=1;line=5",
                "digest": "2" * 64,
            },
        },
        {
            "event_id": "canon_003",
            "sequence": 3,
            "branch_id": "branch_canonical",
            "kind": "canon",
            "text": "沈川是林默失散多年的父亲。",
            "known_by": ["character_su"],
            "source_ref": {
                "source_id": "source_story",
                "locator": "chapter=3;line=8",
                "digest": "3" * 64,
            },
        },
    ]


class Recorder:
    def __init__(self, root: Path, calls: list[str]) -> None:
        self.root = root
        self.calls = calls

    def __call__(self, request: dict) -> dict:
        self.calls.append("capture")
        path = self.root / "listener.wav"
        path.write_bytes(b"captured-audio")
        return {
            "ok": True,
            "path": str(path),
            "sha256": "4" * 64,
            "duration_ms": 900,
            "capture_mode": "push_to_talk",
        }


class Player:
    def __init__(self, calls: list[str]) -> None:
        self.calls = calls

    def pause(self, position_ms: int) -> None:
        self.calls.append(f"pause:{position_ms}")

    def emit_response(self, path: str) -> None:
        self.calls.append(f"emit:{Path(path).name}")

    def resume(self, position_ms: int) -> None:
        self.calls.append(f"resume:{position_ms}")


def successful_asr(calls: list[str]):
    def run(receipt: dict) -> dict:
        calls.append("asr")
        return {
            "ok": True,
            "text": "林默，钥匙在哪里？",
            "language": "zh",
            "stability": "stable",
            "confidence": 0.94,
            "source_audio_sha256": receipt["sha256"],
        }

    return run


def successful_tts(root: Path, calls: list[str]):
    def run(request: dict) -> dict:
        calls.append("tts")
        path = root / "response.wav"
        path.write_bytes(b"real-render-receipt-fixture")
        return {
            "ok": True,
            "path": str(path),
            "sha256": "5" * 64,
            "backend": "fixture-tts",
            "model": "fixture-model-v1",
            "voice_profile_version": 1,
            "verified_to": "machine_audio_artifact",
        }

    return run


def test_capture_is_never_called_without_explicit_owner_authorization(
    tmp_path: Path,
) -> None:
    interaction = load_module()
    calls: list[str] = []

    with pytest.raises(PermissionError, match="microphone_owner_authorization_required"):
        interaction.run_turn(
            session_id="session-a",
            player_position_ms=1200,
            cursor_sequence=2,
            canon=canon(),
            default_character_id="character_lin",
            owner_microphone_authorized=False,
            owner_output_authorized=True,
            retention_policy="session",
            capture=Recorder(tmp_path, calls),
            asr=successful_asr(calls),
            generate_response=lambda request: request["grounded_answer"],
            tts=successful_tts(tmp_path, calls),
            player=Player(calls),
        )

    assert calls == []
    assert list(tmp_path.iterdir()) == []


def test_successful_turn_pauses_captures_routes_grounds_speaks_and_resumes(
    tmp_path: Path,
) -> None:
    interaction = load_module()
    calls: list[str] = []

    result = interaction.run_turn(
        session_id="session-a",
        player_position_ms=1200,
        cursor_sequence=2,
        canon=canon(),
        default_character_id="character_lin",
        owner_microphone_authorized=True,
        owner_output_authorized=True,
        retention_policy="session",
        capture=Recorder(tmp_path, calls),
        asr=successful_asr(calls),
        generate_response=lambda request: request["grounded_answer"],
        tts=successful_tts(tmp_path, calls),
        player=Player(calls),
    )

    assert calls == [
        "pause:1200",
        "capture",
        "asr",
        "tts",
        "emit:response.wav",
        "resume:1200",
    ]
    assert result["status"] == "completed"
    assert result["route"]["character_id"] == "character_lin"
    assert result["response"]["text"] == "钥匙藏在车站时钟下面。"
    assert result["response"]["evidence_event_ids"] == ["canon_002"]
    assert result["playback"]["resumed_at_ms"] == 1200
    assert result["overlap_detected"] is False


def test_asr_failure_still_resumes_exact_position_and_skips_tts(
    tmp_path: Path,
) -> None:
    interaction = load_module()
    calls: list[str] = []

    def failed_asr(_receipt: dict) -> dict:
        calls.append("asr")
        return {"ok": False, "error": "asr_timeout"}

    result = interaction.run_turn(
        session_id="session-a",
        player_position_ms=2400,
        cursor_sequence=2,
        canon=canon(),
        default_character_id="character_lin",
        owner_microphone_authorized=True,
        owner_output_authorized=True,
        retention_policy="none",
        capture=Recorder(tmp_path, calls),
        asr=failed_asr,
        generate_response=lambda request: request["grounded_answer"],
        tts=successful_tts(tmp_path, calls),
        player=Player(calls),
    )

    assert result["status"] == "failed_recovered"
    assert result["failure"]["stage"] == "asr"
    assert calls == ["pause:2400", "capture", "asr", "resume:2400"]
    assert result["playback"]["resumed_at_ms"] == 2400


def test_capture_timeout_is_typed_and_recovers_playback(tmp_path: Path) -> None:
    interaction = load_module()
    calls: list[str] = []

    def timed_out_capture(_request: dict) -> dict:
        calls.append("capture")
        raise TimeoutError("ptt_timeout")

    result = interaction.run_turn(
        session_id="session-a",
        player_position_ms=3600,
        cursor_sequence=2,
        canon=canon(),
        default_character_id="character_lin",
        owner_microphone_authorized=True,
        owner_output_authorized=True,
        retention_policy="none",
        capture=timed_out_capture,
        asr=successful_asr(calls),
        generate_response=lambda request: request["grounded_answer"],
        tts=successful_tts(tmp_path, calls),
        player=Player(calls),
    )

    assert result["status"] == "failed_recovered"
    assert result["failure"] == {"stage": "capture", "error": "ptt_timeout"}
    assert calls == ["pause:3600", "capture", "resume:3600"]


def test_generated_spoiler_is_replaced_before_tts(tmp_path: Path) -> None:
    interaction = load_module()
    calls: list[str] = []
    seen_tts: list[dict] = []

    def leaking_response(_request: dict) -> str:
        return "沈川是林默失散多年的父亲。"

    def inspect_tts(request: dict) -> dict:
        seen_tts.append(request)
        return successful_tts(tmp_path, calls)(request)

    result = interaction.run_turn(
        session_id="session-a",
        player_position_ms=1200,
        cursor_sequence=2,
        canon=canon(),
        default_character_id="character_lin",
        owner_microphone_authorized=True,
        owner_output_authorized=True,
        retention_policy="session",
        capture=Recorder(tmp_path, calls),
        asr=successful_asr(calls),
        generate_response=leaking_response,
        tts=inspect_tts,
        player=Player(calls),
    )

    assert seen_tts[0]["text"] == "以我目前知道的事情，还无法回答。"
    assert result["response"]["spoiler_blocked"] is True
    assert result["response"]["claim_kind"] == "observation"


def test_output_is_not_emitted_without_separate_output_authorization(
    tmp_path: Path,
) -> None:
    interaction = load_module()
    calls: list[str] = []

    result = interaction.run_turn(
        session_id="session-a",
        player_position_ms=1200,
        cursor_sequence=2,
        canon=canon(),
        default_character_id="character_lin",
        owner_microphone_authorized=True,
        owner_output_authorized=False,
        retention_policy="session",
        capture=Recorder(tmp_path, calls),
        asr=successful_asr(calls),
        generate_response=lambda request: request["grounded_answer"],
        tts=successful_tts(tmp_path, calls),
        player=Player(calls),
    )

    assert "emit:response.wav" not in calls
    assert result["response"]["audio_emitted"] is False
    assert result["status"] == "response_rendered_output_gated"


def test_interaction_memory_event_is_proposal_on_simulation_branch(
    tmp_path: Path,
) -> None:
    interaction = load_module()
    calls: list[str] = []

    result = interaction.run_turn(
        session_id="session-a",
        player_position_ms=1200,
        cursor_sequence=2,
        canon=canon(),
        default_character_id="character_lin",
        owner_microphone_authorized=True,
        owner_output_authorized=False,
        retention_policy="session",
        capture=Recorder(tmp_path, calls),
        asr=successful_asr(calls),
        generate_response=lambda request: request["grounded_answer"],
        tts=successful_tts(tmp_path, calls),
        player=Player(calls),
    )

    proposal = result["memory_proposal"]
    assert proposal["branch_id"].startswith("branch_interaction_")
    assert proposal["target_branch_id"] == proposal["branch_id"]
    assert proposal["write_posture"] == "proposal_only_owner_review_required"
    assert proposal["writes_canon"] is False


def test_retention_none_removes_capture_and_transcript_after_turn(
    tmp_path: Path,
) -> None:
    interaction = load_module()
    calls: list[str] = []

    result = interaction.run_turn(
        session_id="session-a",
        player_position_ms=1200,
        cursor_sequence=2,
        canon=canon(),
        default_character_id="character_lin",
        owner_microphone_authorized=True,
        owner_output_authorized=False,
        retention_policy="none",
        capture=Recorder(tmp_path, calls),
        asr=successful_asr(calls),
        generate_response=lambda request: request["grounded_answer"],
        tts=successful_tts(tmp_path, calls),
        player=Player(calls),
    )

    assert not (tmp_path / "listener.wav").exists()
    assert result["retention"]["capture_retained"] is False
    assert result["retention"]["transcript_retained"] is False
    assert result["transcript"]["text"] is None


def test_withdrawal_requires_owner_and_removes_only_named_artifacts(
    tmp_path: Path,
) -> None:
    interaction = load_module()
    capture = tmp_path / "capture.wav"
    response = tmp_path / "response.wav"
    unrelated = tmp_path / "keep.txt"
    capture.write_bytes(b"capture")
    response.write_bytes(b"response")
    unrelated.write_text("keep", encoding="utf-8")

    with pytest.raises(PermissionError, match="withdrawal_owner_authorization_required"):
        interaction.withdraw_artifacts(
            [capture, response], owner_authorized=False
        )

    receipt = interaction.withdraw_artifacts(
        [capture, response], owner_authorized=True
    )

    assert receipt["status"] == "withdrawn"
    assert receipt["removed_count"] == 2
    assert not capture.exists()
    assert not response.exists()
    assert unrelated.exists()


def test_turn_receipt_validates_against_s4_schema(tmp_path: Path) -> None:
    jsonschema = pytest.importorskip("jsonschema")
    interaction = load_module()
    calls: list[str] = []
    result = interaction.run_turn(
        session_id="session-a",
        player_position_ms=1200,
        cursor_sequence=2,
        canon=canon(),
        default_character_id="character_lin",
        owner_microphone_authorized=True,
        owner_output_authorized=True,
        retention_policy="session",
        capture=Recorder(tmp_path, calls),
        asr=successful_asr(calls),
        generate_response=lambda request: request["grounded_answer"],
        tts=successful_tts(tmp_path, calls),
        player=Player(calls),
    )
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))

    assert list(jsonschema.Draft202012Validator(schema).iter_errors(result)) == []
