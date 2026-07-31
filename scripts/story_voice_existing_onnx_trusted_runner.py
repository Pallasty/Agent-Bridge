#!/usr/bin/env python3
"""Hash-bound, offline CPU runner for the audited community ONNX pipeline."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
from typing import Any, Callable


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_pipeline(inference_path: Path, model_path: Path, tts_dir: Path):
    spec = importlib.util.spec_from_file_location(
        "audited_qwen_onnx_inference", inference_path
    )
    if spec is None or spec.loader is None:
        raise ValueError("unable to load audited inference module")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.Pipeline(str(model_path), tts_dir=str(tts_dir))


def run_trial(
    *,
    inference_path: Path,
    expected_inference_sha256: str,
    model_path: Path,
    tts_dir: Path,
    output_path: Path,
    text: str,
    speaker: str,
    language: str,
    max_new_tokens: int,
    style_instruction: str | None = None,
    pipeline_factory: Callable[..., Any] | None = None,
    tokenizer_factory: Callable[..., Any] | None = None,
    audio_writer: Callable[..., Any] | None = None,
) -> dict[str, Any]:
    inference_path = inference_path.resolve()
    actual_hash = sha256(inference_path)
    if actual_hash != expected_inference_sha256:
        raise ValueError("inference SHA-256 mismatch")
    if max_new_tokens < 1 or max_new_tokens > 100:
        raise ValueError("max_new_tokens must be between 1 and 100")
    if style_instruction is not None:
        style_instruction = style_instruction.strip()
        if not style_instruction or len(style_instruction) > 120:
            raise ValueError("style_instruction must contain 1-120 characters")
    output_path = output_path.resolve()
    if output_path.exists():
        raise ValueError("output path already exists")

    os.environ.update(
        {
            "CUDA_VISIBLE_DEVICES": "",
            "HIP_VISIBLE_DEVICES": "",
            "ROCR_VISIBLE_DEVICES": "",
            "HF_HUB_OFFLINE": "1",
            "TRANSFORMERS_OFFLINE": "1",
        }
    )
    if tokenizer_factory is None:
        from transformers import AutoTokenizer

        tokenizer_factory = AutoTokenizer.from_pretrained
    if audio_writer is None:
        import soundfile

        audio_writer = soundfile.write
    pipeline = (
        pipeline_factory(str(model_path), str(tts_dir))
        if pipeline_factory
        else _load_pipeline(inference_path, model_path, tts_dir)
    )
    pipeline._tok = tokenizer_factory(
        str(tts_dir),
        trust_remote_code=True,
        local_files_only=True,
        fix_mistral_regex=True,
    )
    codes = pipeline.generate(
        text,
        language=language,
        speaker=speaker,
        instruct=style_instruction,
        max_new_tokens=max_new_tokens,
        do_sample=False,
        sub_do_sample=False,
        seed=0,
    )
    if codes.shape[0] == 0:
        raise ValueError("generation returned no codec frames")
    if codes.shape[0] >= max_new_tokens:
        raise ValueError("generation reached frame cap before EOS")
    waveform = pipeline.decode_chunked(codes[None]).reshape(-1)
    audio_writer(output_path, waveform, 24000)
    return {
        "inference_sha256": actual_hash,
        "tokenizer_fix_mistral_regex": True,
        "local_files_only": True,
        "provider_policy": "cpu_only_gpu_hidden",
        "generated_codec_frames": codes.shape[0],
        "frame_cap": max_new_tokens,
        "stopped_before_frame_cap": True,
        "style_instruction": style_instruction,
        "output_path": str(output_path),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--inference", type=Path, required=True)
    parser.add_argument("--inference-sha256", required=True)
    parser.add_argument("--model-path", type=Path, required=True)
    parser.add_argument("--tts-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--text", required=True)
    parser.add_argument("--speaker", default="Vivian")
    parser.add_argument("--language", default="Chinese")
    parser.add_argument("--style-instruction")
    parser.add_argument("--max-new-tokens", type=int, default=40)
    args = parser.parse_args()
    result = run_trial(
        inference_path=args.inference,
        expected_inference_sha256=args.inference_sha256,
        model_path=args.model_path,
        tts_dir=args.tts_dir,
        output_path=args.output,
        text=args.text,
        speaker=args.speaker,
        language=args.language,
        style_instruction=args.style_instruction,
        max_new_tokens=args.max_new_tokens,
    )
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
