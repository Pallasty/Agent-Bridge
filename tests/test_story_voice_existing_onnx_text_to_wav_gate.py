from __future__ import annotations

import importlib.util
import json
import wave
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = (
    ROOT / "scripts" / "story_voice_existing_onnx_text_to_wav_gate.py"
)
SCHEMA_PATH = (
    ROOT
    / "docs"
    / "design"
    / "voice-scene"
    / "voice_existing_onnx_text_to_wav_receipt.schema.json"
)


def load_module():
    spec = importlib.util.spec_from_file_location(
        "story_voice_existing_onnx_text_to_wav_gate", MODULE_PATH
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def write_wav(path: Path, *, frames: int = 2400, rate: int = 24000) -> None:
    with wave.open(str(path), "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(rate)
        output.writeframes((1000).to_bytes(2, "little", signed=True) * frames)


def facts(tmp_path: Path) -> dict:
    wav = tmp_path / "trial.wav"
    write_wav(wav)
    return {
        "wav_path": wav,
        "text": "你好。",
        "speaker": "Vivian",
        "language": "Chinese",
        "runtime": {
            "python": "3.14.4",
            "onnxruntime": "1.28.0",
            "transformers": "4.57.3",
            "soundfile": "0.13.1",
        },
        "model_snapshot": Path("/models/community"),
        "model_variant": "cpu_int4",
        "inference_sha256": "a" * 64,
        "manifest_sha256": "b" * 64,
        "stdout": "generated 8 frames\nwrote trial.wav (0.64s)",
    }


def test_valid_pcm16_mono_24khz_wav_is_machine_accepted(
    tmp_path: Path,
) -> None:
    receipt = load_module().validate_trial(**facts(tmp_path))

    assert receipt["status"] == "text_to_wav_machine_verified_no_playback"
    assert receipt["audio"]["sample_rate_hz"] == 24000
    assert receipt["audio"]["channels"] == 1
    assert receipt["audio"]["sample_width_bytes"] == 2
    assert receipt["audio"]["duration_seconds"] == pytest.approx(0.1)
    assert len(receipt["audio"]["sha256"]) == 64


def test_wrong_wav_shape_fails_closed(tmp_path: Path) -> None:
    inputs = facts(tmp_path)
    write_wav(inputs["wav_path"], rate=16000)
    with pytest.raises(ValueError, match="expected mono PCM16 24000 Hz"):
        load_module().validate_trial(**inputs)


def test_silent_wav_fails_closed(tmp_path: Path) -> None:
    inputs = facts(tmp_path)
    with wave.open(str(inputs["wav_path"]), "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(24000)
        output.writeframes(b"\x00\x00" * 2400)
    with pytest.raises(ValueError, match="non-silent"):
        load_module().validate_trial(**inputs)


def test_receipt_keeps_playback_mi50_and_production_blocked(
    tmp_path: Path,
) -> None:
    receipt = load_module().validate_trial(**facts(tmp_path))

    assert receipt["claims"] == {
        "text_to_wav_machine_verified": True,
        "human_audibility_verified": False,
        "naturalness_verified": False,
        "mi50_verified": False,
        "production_admitted": False,
    }
    assert receipt["runtime_effects"]["played_audio"] is False
    assert receipt["runtime_effects"]["used_gpu"] is False


def test_repository_shape_validates_against_schema(tmp_path: Path) -> None:
    jsonschema = pytest.importorskip("jsonschema")
    receipt = load_module().validate_trial(**facts(tmp_path))
    jsonschema.validate(receipt, json.loads(SCHEMA_PATH.read_text()))
