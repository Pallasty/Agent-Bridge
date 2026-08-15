from __future__ import annotations

import hashlib
import importlib.util
import json
import subprocess
import wave
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "story_sherpa_render_gate.py"
SCHEMA_PATH = (
    ROOT
    / "docs"
    / "design"
    / "voice-scene"
    / "sherpa_render_pack.schema.json"
)


def load_module():
    spec = importlib.util.spec_from_file_location(
        "story_sherpa_render_gate", MODULE_PATH
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def tiny_specs() -> dict:
    return {
        "model.onnx": {
            "size": 5,
            "sha256": hashlib.sha256(b"model").hexdigest(),
        },
        "tokens.txt": {
            "size": 6,
            "sha256": hashlib.sha256(b"tokens").hexdigest(),
        },
    }


def write_tiny_model(root: Path) -> None:
    root.mkdir()
    (root / "model.onnx").write_bytes(b"model")
    (root / "tokens.txt").write_bytes(b"tokens")


def plan() -> dict:
    return {
        "schema": "agent_bridge.story_voice_audition_plan.v1",
        "plan_id": "audition_plan_0123456789abcdef0123",
        "status": "audition_plan_ready_no_audio",
        "scene_id": "scene_story_zh_s5",
        "backend_id": "sherpa-aishell3",
        "model_artifact_sha256": "a" * 64,
        "voice_profile_version": 1,
        "items": [
            {
                "blind_label": "voice_a",
                "role_id": "narrator",
                "speaker_id": 10,
                "voice_profile_version": 1,
                "text": "旧车站的钟声响了。",
                "render_status": "pending",
            },
            {
                "blind_label": "voice_b",
                "role_id": "character_lin",
                "speaker_id": 33,
                "voice_profile_version": 1,
                "text": "旧车站的钟声响了。",
                "render_status": "pending",
            },
            {
                "blind_label": "voice_c",
                "role_id": "character_su",
                "speaker_id": 99,
                "voice_profile_version": 1,
                "text": "旧车站的钟声响了。",
                "render_status": "pending",
            },
        ],
    }


def write_wav(path: Path, *, sample_rate: int = 8000) -> None:
    with wave.open(str(path), "wb") as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(sample_rate)
        audio.writeframes(b"\x01\x02" * sample_rate)


def test_model_integrity_failure_prevents_execution(tmp_path: Path) -> None:
    gate = load_module()
    called = False

    def runner(*_args, **_kwargs):
        nonlocal called
        called = True
        raise AssertionError("runner must not execute")

    report = gate.render_pack(
        plan(),
        binary=tmp_path / "missing-bin",
        model_dir=tmp_path / "missing-model",
        output_dir=tmp_path / "output",
        specs=tiny_specs(),
        runner=runner,
    )

    assert report["status"] == "blocked"
    assert report["blockers"] == ["model_integrity_failed"]
    assert report["execution"]["attempted"] is False
    assert called is False
    assert not (tmp_path / "output").exists()


def test_same_size_wrong_hash_is_rejected(tmp_path: Path) -> None:
    gate = load_module()
    model_dir = tmp_path / "model"
    write_tiny_model(model_dir)
    (model_dir / "model.onnx").write_bytes(b"wrong")

    rows = gate.verify_model_dir(model_dir, specs=tiny_specs())

    assert rows[0]["path"] == "model.onnx"
    assert rows[0]["reason"] == "sha256_mismatch"
    assert rows[1]["verified"] is True


def test_existing_output_directory_is_never_overwritten(tmp_path: Path) -> None:
    gate = load_module()
    model_dir = tmp_path / "model"
    write_tiny_model(model_dir)
    binary = tmp_path / "synth"
    binary.write_text("#!/bin/sh\n")
    binary.chmod(0o755)
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    marker = output_dir / "keep.txt"
    marker.write_text("keep")

    report = gate.render_pack(
        plan(),
        binary=binary,
        model_dir=model_dir,
        output_dir=output_dir,
        specs=tiny_specs(),
    )

    assert report["status"] == "blocked"
    assert report["blockers"] == ["output_dir_already_exists"]
    assert marker.read_text() == "keep"


def test_three_voice_pack_is_atomic_hash_bound_and_asr_verified(
    tmp_path: Path,
) -> None:
    jsonschema = __import__("jsonschema")
    gate = load_module()
    model_dir = tmp_path / "model"
    write_tiny_model(model_dir)
    binary = tmp_path / "synth"
    binary.write_text("#!/bin/sh\n")
    binary.chmod(0o755)
    calls: list[list[str]] = []

    def runner(command, **kwargs):
        calls.append(command)
        assert kwargs["shell"] is False
        write_wav(Path(command[command.index("--out") + 1]))
        receipt = {
            "ok": True,
            "backend": "sherpa-vits",
            "voice": command[command.index("--voice") + 1],
            "sample_rate": 8000,
            "speakers": 174,
        }
        return SimpleNamespace(
            returncode=0,
            stdout=json.dumps(receipt),
            stderr="",
        )

    def asr(audio_path: Path, reference: str) -> dict:
        assert audio_path.is_file()
        return {
            "ok": True,
            "transcript": reference,
            "model": "whisper-tiny-multilingual",
            "model_sha256": "b" * 64,
        }

    output_dir = tmp_path / "output"
    report = gate.render_pack(
        plan(),
        binary=binary,
        model_dir=model_dir,
        output_dir=output_dir,
        specs=tiny_specs(),
        runner=runner,
        asr=asr,
    )

    assert report["status"] == "three_voice_render_asr_verified"
    assert report["blockers"] == []
    assert len(calls) == 3
    assert [row["blind_label"] for row in report["artifacts"]] == [
        "voice_a",
        "voice_b",
        "voice_c",
    ]
    assert all(row["wav"]["valid"] for row in report["artifacts"])
    assert all(len(row["wav"]["sha256"]) == 64 for row in report["artifacts"])
    assert all(row["asr"]["cer"] == 0.0 for row in report["artifacts"])
    assert (output_dir / "render_receipt.json").is_file()
    assert not list(tmp_path.glob(".output.partial-*"))
    assert report["runtime_effects"]["plays_audio"] is False
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    jsonschema.validate(report, schema)


def test_asr_quality_failure_is_preserved_as_review_blocker(tmp_path: Path) -> None:
    gate = load_module()
    model_dir = tmp_path / "model"
    write_tiny_model(model_dir)
    binary = tmp_path / "synth"
    binary.write_text("#!/bin/sh\n")
    binary.chmod(0o755)

    def runner(command, **_kwargs):
        write_wav(Path(command[command.index("--out") + 1]))
        return SimpleNamespace(
            returncode=0,
            stdout=json.dumps(
                {
                    "ok": True,
                    "backend": "sherpa-vits",
                    "sample_rate": 8000,
                    "speakers": 174,
                }
            ),
            stderr="",
        )

    def weak_asr(_audio_path: Path, _reference: str) -> dict:
        return {
            "ok": True,
            "transcript": "完全不同",
            "model": "fixture",
            "model_sha256": "b" * 64,
        }

    report = gate.render_pack(
        plan(),
        binary=binary,
        model_dir=model_dir,
        output_dir=tmp_path / "output",
        specs=tiny_specs(),
        runner=runner,
        asr=weak_asr,
    )

    assert report["status"] == "three_voice_rendered_asr_review_failed"
    assert report["blockers"] == [
        "asr_cer_above_threshold:voice_a",
        "asr_cer_above_threshold:voice_b",
        "asr_cer_above_threshold:voice_c",
    ]


def test_render_failure_leaves_no_partial_or_final_pack(tmp_path: Path) -> None:
    gate = load_module()
    model_dir = tmp_path / "model"
    write_tiny_model(model_dir)
    binary = tmp_path / "synth"
    binary.write_text("#!/bin/sh\n")
    binary.chmod(0o755)

    def runner(command, **_kwargs):
        if "voice_b" in command:
            return SimpleNamespace(returncode=2, stdout="", stderr="failed")
        write_wav(Path(command[command.index("--out") + 1]))
        return SimpleNamespace(
            returncode=0,
            stdout='{"ok":true,"speakers":174}',
            stderr="",
        )

    output_dir = tmp_path / "output"
    report = gate.render_pack(
        plan(),
        binary=binary,
        model_dir=model_dir,
        output_dir=output_dir,
        specs=tiny_specs(),
        runner=runner,
    )

    assert report["status"] == "failed"
    assert report["blockers"] == ["render_failed:voice_b"]
    assert not output_dir.exists()
    assert not list(tmp_path.glob(".output.partial-*"))


def test_timeout_is_not_reported_as_render_success(tmp_path: Path) -> None:
    gate = load_module()
    model_dir = tmp_path / "model"
    write_tiny_model(model_dir)
    binary = tmp_path / "synth"
    binary.write_text("#!/bin/sh\n")
    binary.chmod(0o755)

    def runner(command, **kwargs):
        raise subprocess.TimeoutExpired(command, kwargs["timeout"])

    report = gate.render_pack(
        plan(),
        binary=binary,
        model_dir=model_dir,
        output_dir=tmp_path / "output",
        specs=tiny_specs(),
        runner=runner,
    )

    assert report["status"] == "failed"
    assert report["blockers"] == ["render_timeout:voice_a"]


def test_sherpa_whisper_asr_is_integrity_gated_and_parses_json(
    tmp_path: Path,
) -> None:
    gate = load_module()
    binary = tmp_path / "sherpa-onnx-offline"
    binary.write_text("#!/bin/sh\n")
    binary.chmod(0o755)
    model_dir = tmp_path / "asr-model"
    model_dir.mkdir()
    (model_dir / "encoder.onnx").write_bytes(b"encoder")
    (model_dir / "decoder.onnx").write_bytes(b"decoder")
    (model_dir / "tokens.txt").write_bytes(b"tokens")
    specs = {
        "encoder.onnx": {
            "size": 7,
            "sha256": hashlib.sha256(b"encoder").hexdigest(),
        },
        "decoder.onnx": {
            "size": 7,
            "sha256": hashlib.sha256(b"decoder").hexdigest(),
        },
        "tokens.txt": {
            "size": 6,
            "sha256": hashlib.sha256(b"tokens").hexdigest(),
        },
    }
    calls = []

    def runner(command, **kwargs):
        calls.append((command, kwargs))
        return SimpleNamespace(
            returncode=0,
            stdout='Started\n{"lang":"zh","text":"旧车站的钟声响了。"}\n',
            stderr="",
        )

    asr = gate.SherpaWhisperAsr(
        binary=binary,
        runtime_lib_dir=tmp_path / "lib",
        model_dir=model_dir,
        binary_sha256=hashlib.sha256(binary.read_bytes()).hexdigest(),
        specs=specs,
        encoder_name="encoder.onnx",
        decoder_name="decoder.onnx",
        tokens_name="tokens.txt",
        runner=runner,
    )
    receipt = asr(tmp_path / "voice.wav", "旧车站的钟声响了。")

    assert receipt["ok"] is True
    assert receipt["transcript"] == "旧车站的钟声响了。"
    assert receipt["model"] == "sherpa-onnx-whisper-tiny-int8"
    assert len(receipt["model_sha256"]) == 64
    command, kwargs = calls[0]
    assert "--whisper-language=zh" in command
    assert "--model-type=whisper" in command
    assert command[-1] == str(tmp_path / "voice.wav")
    assert kwargs["env"]["LD_LIBRARY_PATH"] == str(tmp_path / "lib")


def test_sherpa_whisper_asr_rejects_binary_or_model_drift(tmp_path: Path) -> None:
    gate = load_module()
    binary = tmp_path / "sherpa-onnx-offline"
    binary.write_text("#!/bin/sh\n")
    binary.chmod(0o755)
    model_dir = tmp_path / "model"
    model_dir.mkdir()
    (model_dir / "encoder.onnx").write_bytes(b"encoder")
    specs = {
        "encoder.onnx": {
            "size": 7,
            "sha256": hashlib.sha256(b"encoder").hexdigest(),
        }
    }

    try:
        gate.SherpaWhisperAsr(
            binary=binary,
            runtime_lib_dir=tmp_path / "lib",
            model_dir=model_dir,
            binary_sha256="0" * 64,
            specs=specs,
            encoder_name="encoder.onnx",
            decoder_name="encoder.onnx",
            tokens_name="encoder.onnx",
        )
    except ValueError as error:
        assert str(error) == "sherpa_asr_binary_integrity_failed"
    else:
        raise AssertionError("binary drift must fail")

    (model_dir / "encoder.onnx").write_bytes(b"changed")
    try:
        gate.SherpaWhisperAsr(
            binary=binary,
            runtime_lib_dir=tmp_path / "lib",
            model_dir=model_dir,
            binary_sha256=hashlib.sha256(binary.read_bytes()).hexdigest(),
            specs=specs,
            encoder_name="encoder.onnx",
            decoder_name="encoder.onnx",
            tokens_name="encoder.onnx",
        )
    except ValueError as error:
        assert str(error) == "sherpa_asr_model_integrity_failed"
    else:
        raise AssertionError("model drift must fail")


def test_sherpa_sense_voice_asr_is_integrity_gated_and_parses_json(
    tmp_path: Path,
) -> None:
    gate = load_module()
    binary = tmp_path / "sherpa-onnx-offline"
    binary.write_text("#!/bin/sh\n")
    binary.chmod(0o755)
    model_dir = tmp_path / "sense-model"
    model_dir.mkdir()
    (model_dir / "model.int8.onnx").write_bytes(b"model")
    (model_dir / "tokens.txt").write_bytes(b"tokens")
    specs = {
        "model.int8.onnx": {
            "size": 5,
            "sha256": hashlib.sha256(b"model").hexdigest(),
        },
        "tokens.txt": {
            "size": 6,
            "sha256": hashlib.sha256(b"tokens").hexdigest(),
        },
    }

    def runner(command, **kwargs):
        assert "--sense-voice-language=zh" in command
        assert "--sense-voice-use-itn=true" in command
        assert "--model-type=sense_voice" in command
        assert kwargs["env"]["LD_LIBRARY_PATH"] == str(tmp_path / "lib")
        return SimpleNamespace(
            returncode=0,
            stdout='{"lang":"<|zh|>","text":"今天阳光很好，我们一起回家。"}\n',
            stderr="",
        )

    asr = gate.SherpaSenseVoiceAsr(
        binary=binary,
        runtime_lib_dir=tmp_path / "lib",
        model_dir=model_dir,
        binary_sha256=hashlib.sha256(binary.read_bytes()).hexdigest(),
        specs=specs,
        runner=runner,
    )
    receipt = asr(tmp_path / "voice.wav", "今天阳光很好，我们一起回家。")

    assert receipt["ok"] is True
    assert receipt["transcript"] == "今天阳光很好，我们一起回家。"
    assert receipt["model"] == "sherpa-onnx-sense-voice-int8-2024-07-17"
    assert len(receipt["model_sha256"]) == 64
