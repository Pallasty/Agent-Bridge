from __future__ import annotations

import importlib.util
import json
import struct
import wave
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts/story_bounded_render_acceptance_review.py"
RESULT_PATH = (
    ROOT
    / "docs/design/voice-scene/"
    "s618_story_bounded_render_acceptance_review.json"
)
SCHEMA_PATH = (
    ROOT
    / "docs/design/voice-scene/"
    "story_bounded_render_acceptance_review.schema.json"
)


def load_module():
    spec = importlib.util.spec_from_file_location(
        "story_bounded_render_acceptance_review", MODULE_PATH
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def write_wav(path: Path, samples: list[int]) -> None:
    with wave.open(str(path), "wb") as stream:
        stream.setnchannels(1)
        stream.setsampwidth(2)
        stream.setframerate(24_000)
        stream.writeframes(struct.pack(f"<{len(samples)}h", *samples))


def add_junk_chunk(source: Path, target: Path) -> None:
    payload = bytearray(source.read_bytes())
    chunk = b"JUNK" + struct.pack("<I", 4) + b"ABCD"
    rewritten = payload[:12] + chunk + payload[12:]
    struct.pack_into("<I", rewritten, 4, len(rewritten) - 8)
    target.write_bytes(rewritten)


def test_pcm_comparison_accepts_distinct_wav_containers_with_exact_samples(
    tmp_path: Path,
) -> None:
    review = load_module()
    reference = tmp_path / "reference.wav"
    candidate = tmp_path / "candidate.wav"
    write_wav(reference, [0, 100, -100, 500, -500])
    add_junk_chunk(reference, candidate)

    comparison = review.compare_pcm_wav(reference, candidate)

    assert comparison["file_sha256_equal"] is False
    assert comparison["pcm_sha256_equal"] is True
    assert comparison["format_equal"] is True
    assert comparison["sample_rate_hz"] == 24_000
    assert comparison["channels"] == 1
    assert comparison["sample_width_bytes"] == 2
    assert comparison["frames"] == 5


def test_pcm_comparison_rejects_one_sample_drift(tmp_path: Path) -> None:
    review = load_module()
    reference = tmp_path / "reference.wav"
    candidate = tmp_path / "candidate.wav"
    write_wav(reference, [0, 100, -100])
    write_wav(candidate, [0, 101, -100])

    comparison = review.compare_pcm_wav(reference, candidate)

    assert comparison["format_equal"] is True
    assert comparison["pcm_sha256_equal"] is False


def test_s618_live_review_proves_pcm_and_owner_acceptance_continuity() -> None:
    review = load_module()

    result = review.build_acceptance_review(ROOT)

    assert result["status"] == "story_bounded_render_acceptance_verified"
    assert result["decision"] == (
        "accepted_by_exact_pcm_continuity_without_new_playback"
    )
    comparison = result["comparison"]
    assert comparison["segment_count"] == 3
    assert all(row["file_sha256_equal"] for row in comparison["segments"])
    assert all(row["pcm_sha256_equal"] for row in comparison["segments"])
    assert comparison["assembly"]["file_sha256_equal"] is False
    assert comparison["assembly"]["pcm_sha256_equal"] is True
    assert comparison["assembly"]["frames"] == 165_120
    assert comparison["all_pcm_exact"] is True

    human = result["human_acceptance"]
    assert human["prior_owner_playback_completed"] is True
    assert human["prior_owner_acceptance_verified"] is True
    assert human["inheritance_basis"] == "exact_pcm_sample_sequence"
    assert human["current_playback_required"] is False
    assert human["current_playback_performed"] is False
    assert human["blind_comparison_claimed"] is False

    encoded = json.dumps(result, ensure_ascii=False, sort_keys=True)
    live_receipt = json.loads(
        Path(result["evidence"]["s617_render_receipt_path"]).read_text(
            encoding="utf-8"
        )
    )
    assert live_receipt["authorization_id"] not in encoded
    assert "authorization_id" not in encoded
    assert result["runtime_effects"] == {
        "read_secret": False,
        "consumed_nonce": False,
        "loaded_model": False,
        "executed_onnx": False,
        "rendered_audio": False,
        "played_audio": False,
        "recorded_audio": False,
        "wrote_cache": False,
        "wrote_memory": False,
    }


def test_s618_checked_in_result_is_exact_schema_valid_builder_output() -> None:
    jsonschema = pytest.importorskip("jsonschema")
    review = load_module()
    expected = review.build_acceptance_review(ROOT)
    actual = json.loads(RESULT_PATH.read_text(encoding="utf-8"))
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))

    assert list(jsonschema.Draft202012Validator(schema).iter_errors(actual)) == []
    assert actual == expected


def test_s618_implementation_has_no_playback_or_mutation_surface() -> None:
    source = MODULE_PATH.read_text(encoding="utf-8")

    for forbidden in (
        "import subprocess",
        "from subprocess",
        "Popen(",
        "os.system(",
        "paplay",
        "aplay",
        "sounddevice",
        "pyaudio",
        "sqlite3",
        "onnxruntime",
    ):
        assert forbidden not in source
    assert "write_bytes(" not in source
    assert "write_text(" not in source
    assert "open(\"w\"" not in source
