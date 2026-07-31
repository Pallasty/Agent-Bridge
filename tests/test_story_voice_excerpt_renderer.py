from __future__ import annotations

import importlib.util
import wave
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "story_voice_excerpt_renderer.py"


def load_module():
    spec = importlib.util.spec_from_file_location(
        "story_voice_excerpt_renderer", MODULE_PATH
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def mapping() -> dict:
    return {
        "mapping_sha256": "a" * 64,
        "roles": [
            {
                "speaker_id": "narrator",
                "display_name": "旁白",
                "qwen_speaker": "Vivian",
                "style_instruction": "温柔、清晰、克制地叙述。",
                "render_authorized": True,
            },
            {
                "speaker_id": "lin",
                "display_name": "林默",
                "qwen_speaker": "Dylan",
                "style_instruction": "冷静而坚定。",
                "render_authorized": False,
            },
            {
                "speaker_id": "su",
                "display_name": "苏岚",
                "qwen_speaker": "Serena",
                "style_instruction": "温暖而警觉。",
                "render_authorized": False,
            },
        ],
    }


def acceptance(*, accepted: bool = True) -> dict:
    return {
        "mapping_sha256": "a" * 64,
        "claims": {
            "owner_accepted_both": accepted,
            "voices_distinguishable": accepted,
            "chapter_render_ready": accepted,
        },
    }


def excerpt() -> list[dict[str, str]]:
    return [
        {
            "speaker_id": "narrator",
            "text": "雨声渐近。",
            "transition_after": "paragraph_break",
        },
        {
            "speaker_id": "lin",
            "text": "我们得马上离开。",
            "transition_after": "speaker_turn",
        },
        {"speaker_id": "su", "text": "等等，我听见钟声了。"},
    ]


def test_build_plan_binds_accepted_mapping_and_preserves_order() -> None:
    plan = load_module().build_render_plan(mapping(), acceptance(), excerpt())

    assert plan[0]["qwen_speaker"] == "Vivian"
    assert plan[1]["qwen_speaker"] == "Dylan"
    assert plan[2]["qwen_speaker"] == "Serena"
    assert [row["segment_index"] for row in plan] == [0, 1, 2]
    assert all(row["style_instruction"] for row in plan)
    assert [row.get("pause_after_seconds") for row in plan] == [1.4, 1.0, None]


def test_pause_policy_is_explicit_bounded_and_rejects_unknown_labels() -> None:
    module = load_module()

    assert module.PAUSE_SECONDS == {
        "same_paragraph": 0.65,
        "speaker_turn": 1.0,
        "paragraph_break": 1.4,
        "scene_break": 2.2,
    }
    invalid = excerpt()
    invalid[0]["transition_after"] = "dramatic_guess"
    with pytest.raises(ValueError, match="unknown transition_after"):
        module.build_render_plan(mapping(), acceptance(), invalid)


def test_build_plan_fails_closed_on_unaccepted_or_mismatched_mapping() -> None:
    with pytest.raises(ValueError, match="chapter render not authorized"):
        load_module().build_render_plan(
            mapping(), acceptance(accepted=False), excerpt()
        )

    mismatched = acceptance()
    mismatched["mapping_sha256"] = "b" * 64
    with pytest.raises(ValueError, match="mapping SHA-256 mismatch"):
        load_module().build_render_plan(mapping(), mismatched, excerpt())


def _write_wav(path: Path, samples: bytes) -> None:
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(24000)
        wav.writeframes(samples)


def test_concatenate_wavs_inserts_exact_bounded_silence(tmp_path: Path) -> None:
    first = tmp_path / "first.wav"
    second = tmp_path / "second.wav"
    output = tmp_path / "excerpt.wav"
    _write_wav(first, b"\x01\x00" * 10)
    _write_wav(second, b"\x02\x00" * 20)

    result = load_module().concatenate_wavs(
        [first, second], output, gap_seconds=0.5
    )

    assert result["sample_rate_hz"] == 24000
    assert result["gap_frames"] == 12000
    assert result["audio_frames"] == 30
    assert result["total_frames"] == 12030
    with wave.open(str(output), "rb") as wav:
        payload = wav.readframes(wav.getnframes())
    assert payload == (
        b"\x01\x00" * 10 + b"\x00\x00" * 12000 + b"\x02\x00" * 20
    )


def test_concatenate_wavs_rejects_format_mismatch(tmp_path: Path) -> None:
    first = tmp_path / "first.wav"
    second = tmp_path / "second.wav"
    _write_wav(first, b"\x01\x00" * 10)
    with wave.open(str(second), "wb") as wav:
        wav.setnchannels(2)
        wav.setsampwidth(2)
        wav.setframerate(24000)
        wav.writeframes(b"\x00\x00" * 20)

    with pytest.raises(ValueError, match="WAV format mismatch"):
        load_module().concatenate_wavs(
            [first, second], tmp_path / "out.wav", gap_seconds=0.5
        )


def test_concatenate_wavs_supports_one_gap_per_transition(tmp_path: Path) -> None:
    paths = [tmp_path / f"{index}.wav" for index in range(3)]
    for path in paths:
        _write_wav(path, b"\x01\x00" * 10)

    result = load_module().concatenate_wavs(
        paths,
        tmp_path / "dynamic.wav",
        gap_seconds=[0.65, 1.4],
    )

    assert result["gap_seconds"] == [0.65, 1.4]
    assert result["gap_frames"] == [15600, 33600]
    assert result["total_frames"] == 49230

    with pytest.raises(ValueError, match="one gap per transition"):
        load_module().concatenate_wavs(
            paths,
            tmp_path / "invalid.wav",
            gap_seconds=[0.65],
        )
