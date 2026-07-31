from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = (
    ROOT / "scripts" / "story_voice_existing_onnx_trusted_runner.py"
)


def load_module():
    spec = importlib.util.spec_from_file_location(
        "story_voice_existing_onnx_trusted_runner", MODULE_PATH
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class FakePipeline:
    def __init__(self, frames: int = 24) -> None:
        self._tok = None
        self.frames = frames

    def generate(self, *args, **kwargs):
        assert self._tok == "fixed-tokenizer"
        assert kwargs["do_sample"] is False
        assert kwargs["sub_do_sample"] is False
        return FakeArray((self.frames, 16))

    def decode_chunked(self, codes):
        assert codes.shape == (1, self.frames, 16)
        return FakeArray((1, 1, 24000))


class FakeArray:
    def __init__(self, shape) -> None:
        self.shape = shape

    def __getitem__(self, item):
        if item is None:
            return FakeArray((1, *self.shape))
        raise AssertionError(item)

    def reshape(self, *_shape):
        return FakeArray((24000,))


def test_runner_hash_binds_inference_and_fixes_tokenizer(tmp_path: Path) -> None:
    inference = tmp_path / "inference.py"
    inference.write_text("trusted fixture")
    module = load_module()
    expected = module.sha256(inference)
    tokenizer_calls = []
    written = []

    def tokenizer_factory(path, **kwargs):
        tokenizer_calls.append((path, kwargs))
        return "fixed-tokenizer"

    receipt = module.run_trial(
        inference_path=inference,
        expected_inference_sha256=expected,
        model_path=tmp_path / "cpu_int4",
        tts_dir=tmp_path / "original",
        output_path=tmp_path / "candidate.wav",
        text="你好。",
        speaker="Vivian",
        language="Chinese",
        max_new_tokens=25,
        pipeline_factory=lambda *_: FakePipeline(),
        tokenizer_factory=tokenizer_factory,
        audio_writer=lambda path, wav, rate: written.append(
            (path, wav.shape, rate)
        ),
    )

    assert tokenizer_calls == [
        (
            str(tmp_path / "original"),
            {
                "trust_remote_code": True,
                "local_files_only": True,
                "fix_mistral_regex": True,
            },
        )
    ]
    assert written == [(tmp_path / "candidate.wav", (24000,), 24000)]
    assert receipt["tokenizer_fix_mistral_regex"] is True
    assert receipt["generated_codec_frames"] == 24
    assert receipt["stopped_before_frame_cap"] is True


def test_runner_rejects_frame_cap_as_truncated(tmp_path: Path) -> None:
    inference = tmp_path / "inference.py"
    inference.write_text("trusted fixture")
    module = load_module()
    written = []

    with pytest.raises(ValueError, match="generation reached frame cap"):
        module.run_trial(
            inference_path=inference,
            expected_inference_sha256=module.sha256(inference),
            model_path=tmp_path / "model",
            tts_dir=tmp_path / "original",
            output_path=tmp_path / "candidate.wav",
            text="你好。",
            speaker="Vivian",
            language="Chinese",
            max_new_tokens=25,
            pipeline_factory=lambda *_: FakePipeline(frames=25),
            tokenizer_factory=lambda *_args, **_kwargs: "fixed-tokenizer",
            audio_writer=lambda *_: written.append(True),
        )
    assert written == []


def test_runner_rejects_inference_hash_mismatch(tmp_path: Path) -> None:
    inference = tmp_path / "inference.py"
    inference.write_text("changed")

    with pytest.raises(ValueError, match="inference SHA-256 mismatch"):
        load_module().run_trial(
            inference_path=inference,
            expected_inference_sha256="0" * 64,
            model_path=tmp_path / "model",
            tts_dir=tmp_path / "original",
            output_path=tmp_path / "candidate.wav",
            text="你好。",
            speaker="Vivian",
            language="Chinese",
            max_new_tokens=25,
            pipeline_factory=lambda *_: FakePipeline(),
            tokenizer_factory=lambda *_args, **_kwargs: "fixed-tokenizer",
            audio_writer=lambda *_: None,
        )
