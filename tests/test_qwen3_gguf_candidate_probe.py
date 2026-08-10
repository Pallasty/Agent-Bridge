import importlib.util
import struct
from pathlib import Path


_PATH = Path(__file__).parents[1] / "scripts" / "qwen3_gguf_candidate_probe.py"
_SPEC = importlib.util.spec_from_file_location("qwen3_gguf_candidate_probe", _PATH)
assert _SPEC and _SPEC.loader
probe = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(probe)


def test_command_is_explicit_same_family_and_never_auto_downloads(tmp_path):
    command = probe.build_command(
        tmp_path / "crispasr", tmp_path / "talker.gguf", tmp_path / "codec.gguf",
        "vivian", "你好", tmp_path / "out.wav", "温暖平静", 42,
    )
    assert command[1:5] == [
        "--backend", "qwen3-tts-1.7b-customvoice", "-m", str(tmp_path / "talker.gguf"),
    ]
    assert "auto" not in command
    assert ["--instruct", "温暖平静"] == command[-2:]


def test_command_omits_empty_instruction(tmp_path):
    command = probe.build_command(tmp_path / "r", tmp_path / "t", tmp_path / "c",
                                  "serena", "你好", tmp_path / "out.wav", "", 7)
    assert "--instruct" not in command
    assert command[-2:] == ["--seed", "7"]


def test_wav_sample_rate_reads_standard_fmt_chunk(tmp_path):
    wav = tmp_path / "candidate.wav"
    payload = struct.pack("<HHIIHH", 1, 1, 24000, 48000, 2, 16)
    wav.write_bytes(b"RIFF" + struct.pack("<I", 36) + b"WAVEfmt " + struct.pack("<I", len(payload)) + payload)
    assert probe.wav_sample_rate(wav) == 24000


def test_validate_paths_requires_absolute_output(tmp_path):
    errors = probe.validate_paths(tmp_path / "missing", tmp_path / "talker", tmp_path / "codec", Path("out.wav"))
    assert "output must be an absolute path" in errors
