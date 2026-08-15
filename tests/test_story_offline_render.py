from __future__ import annotations

import importlib.util
import json
import math
import struct
import wave
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "story_offline_render.py"
SCHEMA_PATH = (
    ROOT
    / "docs"
    / "design"
    / "voice-scene"
    / "story_render_manifest.schema.json"
)


def load_module():
    spec = importlib.util.spec_from_file_location("story_offline_render", MODULE_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def write_wav(path: Path, *, frequency: float = 440.0, duration: float = 0.08) -> None:
    sample_rate = 16000
    frames = [
        int(8000 * math.sin(2 * math.pi * frequency * index / sample_rate))
        for index in range(int(sample_rate * duration))
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        wav.writeframes(b"".join(struct.pack("<h", sample) for sample in frames))


def story_plan() -> dict:
    return {
        "schema": "agent_bridge.story_plan.v1",
        "status": "story_plan_reviewable",
        "source": {"sha256": "1" * 64, "version": "source-v1"},
        "selection": {"first_chapter": 1},
        "voice_scene": {
            "scene": {"scene_id": "scene_demo"},
            "timeline": [
                {
                    "event_id": "event_1",
                    "sequence": 1,
                    "utterance": {
                        "speaker_id": "speaker_narrator",
                        "text": "First segment.",
                    },
                },
                {
                    "event_id": "event_2",
                    "sequence": 2,
                    "utterance": {
                        "speaker_id": "speaker_character",
                        "text": "Second segment.",
                    },
                },
            ],
            "voice_profiles": [
                {
                    "voice_profile_id": "voice_narrator_v1",
                    "speaker_id": "speaker_narrator",
                    "version": 1,
                    "backend": "kokoro",
                    "model": "kokoro-v1.0",
                    "voice": "af_sarah",
                    "language": "en",
                    "audition_status": "human_confirmed",
                },
                {
                    "voice_profile_id": "voice_character_v1",
                    "speaker_id": "speaker_character",
                    "version": 1,
                    "backend": "kokoro",
                    "model": "kokoro-v1.0",
                    "voice": "af_bella",
                    "language": "en",
                    "audition_status": "human_confirmed",
                },
            ],
        },
    }


def backend() -> dict:
    return {
        "backend": "kokoro",
        "model_id": "kokoro-v1.0",
        "model_sha256": "2" * 64,
        "binary_sha256": "3" * 64,
        "capabilities": {
            "speed": True,
            "gain": True,
            "pause": True,
            "pitch": False,
        },
    }


class FakeRenderer:
    def __init__(self, *, fail_first: bool = False) -> None:
        self.calls: list[str] = []
        self.fail_first = fail_first

    def __call__(self, request: dict, output: Path) -> dict:
        self.calls.append(request["event_id"])
        if self.fail_first and len(self.calls) == 1:
            return {"ok": False, "error": "transient"}
        frequency = 440.0 if request["event_id"] == "event_1" else 660.0
        write_wav(output, frequency=frequency)
        return {
            "ok": True,
            "backend": "kokoro",
            "model_id": "kokoro-v1.0",
            "voice": request["voice"],
            "output_file": str(output),
        }


def test_cache_key_binds_source_model_profile_and_settings() -> None:
    render = load_module()
    base = {
        "source_sha256": "1" * 64,
        "text": "hello",
        "model_sha256": "2" * 64,
        "voice_profile_id": "voice_a",
        "voice_profile_version": 1,
        "speed": 1.0,
        "gain_db": 0.0,
        "pause_ms": 100,
    }

    assert render.render_cache_key(base) == render.render_cache_key(dict(base))
    for field, changed in [
        ("source_sha256", "9" * 64),
        ("model_sha256", "8" * 64),
        ("voice_profile_version", 2),
        ("speed", 1.1),
    ]:
        variant = dict(base)
        variant[field] = changed
        assert render.render_cache_key(base) != render.render_cache_key(variant)


def test_wav_validator_rejects_header_only_and_silence(tmp_path: Path) -> None:
    render = load_module()
    header_only = tmp_path / "header.wav"
    header_only.write_bytes(b"RIFF\x00\x00\x00\x00WAVEfmt \x10\x00\x00\x00")
    silent = tmp_path / "silent.wav"
    with wave.open(str(silent), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(16000)
        wav.writeframes(b"\0\0" * 1600)

    assert render.validate_wav(header_only)["valid"] is False
    assert render.validate_wav(silent)["valid"] is False
    assert render.validate_wav(silent)["reason"] == "wav_silent"


def test_render_retries_one_failed_segment_and_builds_verified_chapter(
    tmp_path: Path,
) -> None:
    render = load_module()
    renderer = FakeRenderer(fail_first=True)

    manifest = render.render_chapter(
        story_plan(), tmp_path, backend(), renderer, retry_limit=1
    )

    assert renderer.calls == ["event_1", "event_1", "event_2"]
    assert manifest["status"] == "rendered_verified"
    assert manifest["segment_summary"] == {
        "count": 2,
        "rendered": 2,
        "cache_hits": 0,
        "attempts": 3,
    }
    assert Path(manifest["chapter_artifact"]["path"]).is_file()
    assert render.verify_chapter_manifest(manifest)["valid"] is True


def test_second_render_hits_cache_without_calling_backend(tmp_path: Path) -> None:
    render = load_module()
    first_renderer = FakeRenderer()
    render.render_chapter(story_plan(), tmp_path, backend(), first_renderer)
    second_renderer = FakeRenderer()

    manifest = render.render_chapter(
        story_plan(), tmp_path, backend(), second_renderer
    )

    assert second_renderer.calls == []
    assert manifest["segment_summary"]["cache_hits"] == 2


def test_profile_version_change_invalidates_only_that_segment(tmp_path: Path) -> None:
    render = load_module()
    render.render_chapter(story_plan(), tmp_path, backend(), FakeRenderer())
    changed = story_plan()
    changed["voice_scene"]["voice_profiles"][1]["version"] = 2
    renderer = FakeRenderer()

    manifest = render.render_chapter(changed, tmp_path, backend(), renderer)

    assert renderer.calls == ["event_2"]
    assert manifest["segment_summary"]["cache_hits"] == 1


def test_gain_control_changes_assembled_pcm_level(tmp_path: Path) -> None:
    render = load_module()
    quiet = render.render_chapter(
        story_plan(), tmp_path / "quiet", backend(), FakeRenderer(), gain_db=-6.0
    )
    loud = render.render_chapter(
        story_plan(), tmp_path / "loud", backend(), FakeRenderer(), gain_db=6.0
    )

    quiet_wav = render.validate_wav(Path(quiet["chapter_artifact"]["path"]))
    loud_wav = render.validate_wav(Path(loud["chapter_artifact"]["path"]))

    assert loud_wav["rms"] > quiet_wav["rms"] * 3.5
    assert loud["chapter_artifact"]["sha256"] != quiet["chapter_artifact"]["sha256"]


def test_missing_or_reordered_segment_breaks_integrity(tmp_path: Path) -> None:
    render = load_module()
    manifest = render.render_chapter(
        story_plan(), tmp_path, backend(), FakeRenderer()
    )
    manifest["segments"].reverse()

    result = render.verify_chapter_manifest(manifest)

    assert result["valid"] is False
    assert "segment_order_mismatch" in result["errors"]


def test_player_requires_owner_gate_and_tracks_pause_resume_rewind(
    tmp_path: Path,
) -> None:
    render = load_module()
    manifest = render.render_chapter(
        story_plan(), tmp_path / "render", backend(), FakeRenderer()
    )
    player = render.ChapterPlayer(tmp_path / "player.json")

    with pytest.raises(PermissionError, match="owner_authorization_required"):
        player.start(manifest, owner_authorized=False)
    assert not (tmp_path / "player.json").exists()

    assert player.start(manifest, owner_authorized=True, emit_audio=False)["state"] == "playing"
    assert player.pause(position_ms=900)["state"] == "paused"
    assert player.rewind(milliseconds=250)["position_ms"] == 650
    assert player.resume(owner_authorized=True, emit_audio=False)["state"] == "playing"
    assert player.status()["audio_emitted"] is False


def test_render_manifest_validates_against_s2_schema(tmp_path: Path) -> None:
    jsonschema = pytest.importorskip("jsonschema")
    render = load_module()
    manifest = render.render_chapter(
        story_plan(), tmp_path, backend(), FakeRenderer()
    )
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))

    assert list(jsonschema.Draft202012Validator(schema).iter_errors(manifest)) == []
