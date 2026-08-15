#!/usr/bin/env python3
"""Validate an isolated existing-ONNX text-to-WAV trial without playback."""

from __future__ import annotations

import argparse
import array
import hashlib
import json
import math
import wave
from pathlib import Path
from typing import Any


def validate_trial(
    *,
    wav_path: Path,
    text: str,
    speaker: str,
    language: str,
    runtime: dict[str, str],
    model_snapshot: Path,
    model_variant: str,
    inference_sha256: str,
    manifest_sha256: str,
    stdout: str,
) -> dict[str, Any]:
    wav_path = wav_path.resolve()
    with wave.open(str(wav_path), "rb") as source:
        channels = source.getnchannels()
        sample_width = source.getsampwidth()
        sample_rate = source.getframerate()
        frames = source.getnframes()
        compression = source.getcomptype()
        samples_raw = source.readframes(frames)
    if (
        channels != 1
        or sample_width != 2
        or sample_rate != 24000
        or compression != "NONE"
        or frames <= 0
    ):
        raise ValueError("expected mono PCM16 24000 Hz non-empty WAV")
    samples = array.array("h")
    samples.frombytes(samples_raw)
    peak = max(abs(sample) for sample in samples) / 32768
    rms = math.sqrt(
        sum(sample * sample for sample in samples) / len(samples)
    ) / 32768
    if rms <= 1e-5 or peak <= 1e-4:
        raise ValueError("expected non-silent WAV")
    for name, digest in (
        ("inference", inference_sha256),
        ("manifest", manifest_sha256),
    ):
        if len(digest) != 64:
            raise ValueError(f"{name} SHA-256 is invalid")
    return {
        "schema": "agent_bridge.voice_existing_onnx_text_to_wav_receipt.v1",
        "status": "text_to_wav_machine_verified_no_playback",
        "request": {
            "text": text,
            "speaker": speaker,
            "language": language,
        },
        "model": {
            "snapshot": str(model_snapshot.resolve()),
            "variant": model_variant,
            "inference_sha256": inference_sha256,
            "manifest_sha256": manifest_sha256,
        },
        "runtime": runtime,
        "audio": {
            "path": str(wav_path),
            "bytes": wav_path.stat().st_size,
            "sha256": hashlib.sha256(wav_path.read_bytes()).hexdigest(),
            "sample_rate_hz": sample_rate,
            "channels": channels,
            "sample_width_bytes": sample_width,
            "frames": frames,
            "duration_seconds": frames / sample_rate,
            "rms": rms,
            "peak": peak,
        },
        "synthesis_stdout": stdout[-4000:],
        "claims": {
            "text_to_wav_machine_verified": True,
            "human_audibility_verified": False,
            "naturalness_verified": False,
            "mi50_verified": False,
            "production_admitted": False,
        },
        "runtime_effects": {
            "created_inference_sessions": True,
            "executed_onnx_graphs": True,
            "generated_codec_frames": True,
            "rendered_audio": True,
            "played_audio": False,
            "loaded_original_pytorch_model": False,
            "executed_converter": False,
            "created_onnx": False,
            "used_gpu": False,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--facts", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    facts = json.loads(args.facts.read_text())
    facts["wav_path"] = Path(facts["wav_path"])
    facts["model_snapshot"] = Path(facts["model_snapshot"])
    receipt = validate_trial(**facts)
    rendered = json.dumps(receipt, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.write_text(rendered)
    else:
        print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
