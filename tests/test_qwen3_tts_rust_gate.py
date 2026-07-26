import hashlib
import subprocess
import sys
import wave
from pathlib import Path
from types import SimpleNamespace


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import qwen3_tts_rust_gate as gate  # noqa: E402


def tiny_specs():
    model = b"model"
    tokenizer = b"tokenizer"
    return {
        "model.safetensors": {
            "size": len(model),
            "sha256": hashlib.sha256(model).hexdigest(),
        },
        "speech_tokenizer/model.safetensors": {
            "size": len(tokenizer),
            "sha256": hashlib.sha256(tokenizer).hexdigest(),
        },
    }, model, tokenizer


def write_tiny_model(root: Path):
    specs, model, tokenizer = tiny_specs()
    (root / "speech_tokenizer").mkdir(parents=True)
    (root / "model.safetensors").write_bytes(model)
    (root / "speech_tokenizer/model.safetensors").write_bytes(tokenizer)
    return specs


def test_integrity_gate_rejects_missing_and_wrong_size_without_execution(tmp_path):
    called = False

    def runner(*args, **kwargs):
        nonlocal called
        called = True
        raise AssertionError("runner must not be called")

    specs, _, _ = tiny_specs()
    report = gate.run_gate(
        tmp_path / "missing-bin",
        tmp_path / "model",
        tmp_path / "out.wav",
        specs=specs,
        runner=runner,
    )
    assert report["reason"] == "model_integrity_failed"
    assert not report["execution"]["attempted"]
    assert not called

    model_dir = tmp_path / "model"
    write_tiny_model(model_dir)
    (model_dir / "model.safetensors").write_bytes(b"wrong-size")
    report = gate.run_gate(
        tmp_path / "missing-bin",
        model_dir,
        tmp_path / "out.wav",
        specs=specs,
        runner=runner,
    )
    assert report["reason"] == "model_integrity_failed"
    assert report["model_files"][0]["reason"] == "size_mismatch"
    assert not called


def test_integrity_gate_rejects_same_size_wrong_sha(tmp_path):
    model_dir = tmp_path / "model"
    specs = write_tiny_model(model_dir)
    (model_dir / "model.safetensors").write_bytes(b"xxxxx")
    rows = gate.verify_model_files(model_dir, specs)
    assert rows[0]["reason"] == "sha256_mismatch"
    assert rows[0]["sha256"] == hashlib.sha256(b"xxxxx").hexdigest()
    assert rows[1]["verified"]


def test_command_is_fixed_to_metal_f16_and_local_model(tmp_path):
    command = gate.build_command(
        tmp_path / "qwen-tts",
        tmp_path / "model",
        tmp_path / "out.wav",
        "你好",
        "Serena",
        128,
        42,
    )
    assert command[command.index("--device") + 1] == "metal"
    assert command[command.index("--dtype") + 1] == "f16"
    assert command[command.index("--model-path") + 1] == str(tmp_path / "model")
    assert "--model" not in command
    assert command[-3:] == ["custom-voice", "--speaker", "Serena"]


def test_success_requires_and_attests_a_nonempty_wav(tmp_path):
    model_dir = tmp_path / "model"
    specs = write_tiny_model(model_dir)
    binary = tmp_path / "qwen-tts"
    binary.write_text("#!/bin/sh\n")
    binary.chmod(0o755)
    output = tmp_path / "out.wav"

    def runner(command, **kwargs):
        assert kwargs["timeout"] == 900
        with wave.open(str(output), "wb") as audio:
            audio.setnchannels(1)
            audio.setsampwidth(2)
            audio.setframerate(24000)
            audio.writeframes(b"\x00\x01" * 240)
        return SimpleNamespace(returncode=0, stdout="ok", stderr="")

    report = gate.run_gate(
        binary,
        model_dir,
        output,
        specs=specs,
        runner=runner,
    )
    assert report["verified"]
    assert report["verified_to"] == "qwen3_rust_synthesized_wav"
    assert report["output_evidence"]["sample_rate"] == 24000
    assert report["output_evidence"]["frames"] == 240
    assert len(report["output_evidence"]["sha256"]) == 64


def test_existing_output_is_never_overwritten(tmp_path):
    model_dir = tmp_path / "model"
    specs = write_tiny_model(model_dir)
    binary = tmp_path / "qwen-tts"
    binary.write_text("#!/bin/sh\n")
    binary.chmod(0o755)
    output = tmp_path / "out.wav"
    output.write_bytes(b"keep")

    report = gate.run_gate(binary, model_dir, output, specs=specs)
    assert report["reason"] == "output_already_exists"
    assert output.read_bytes() == b"keep"
    assert not report["execution"]["attempted"]


def test_timeout_is_not_reported_as_success(tmp_path):
    model_dir = tmp_path / "model"
    specs = write_tiny_model(model_dir)
    binary = tmp_path / "qwen-tts"
    binary.write_text("#!/bin/sh\n")
    binary.chmod(0o755)

    def runner(*args, **kwargs):
        raise subprocess.TimeoutExpired(args[0], kwargs["timeout"])

    report = gate.run_gate(
        binary,
        model_dir,
        tmp_path / "out.wav",
        specs=specs,
        runner=runner,
    )
    assert report["reason"] == "inference_timeout"
    assert not report["verified"]
