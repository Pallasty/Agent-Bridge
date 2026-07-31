#!/usr/bin/env python3
"""Authorize and assemble a bounded, multi-role story voice excerpt."""

from __future__ import annotations

import argparse
import hashlib
import json
import wave
from pathlib import Path
from typing import Any


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_render_plan(
    mapping: dict[str, Any],
    acceptance: dict[str, Any],
    excerpt: list[dict[str, str]],
) -> list[dict[str, Any]]:
    if mapping["mapping_sha256"] != acceptance["mapping_sha256"]:
        raise ValueError("mapping SHA-256 mismatch")
    claims = acceptance.get("claims", {})
    required_claims = (
        "owner_accepted_both",
        "voices_distinguishable",
        "chapter_render_ready",
    )
    if not all(claims.get(name) is True for name in required_claims):
        raise ValueError("chapter render not authorized")

    roles = {row["speaker_id"]: row for row in mapping["roles"]}
    plan = []
    for index, segment in enumerate(excerpt):
        speaker_id = segment.get("speaker_id", "")
        text = segment.get("text", "").strip()
        if speaker_id not in roles:
            raise ValueError(f"unknown excerpt speaker: {speaker_id}")
        if not text or len(text) > 200:
            raise ValueError("excerpt text must contain 1-200 characters")
        role = roles[speaker_id]
        plan.append(
            {
                "segment_index": index,
                "speaker_id": speaker_id,
                "display_name": role["display_name"],
                "qwen_speaker": role["qwen_speaker"],
                "style_instruction": role["style_instruction"],
                "text": text,
            }
        )
    if not plan:
        raise ValueError("excerpt must contain at least one segment")
    return plan


def concatenate_wavs(
    paths: list[Path], output_path: Path, *, gap_seconds: float
) -> dict[str, Any]:
    if not paths:
        raise ValueError("at least one WAV is required")
    if gap_seconds < 0 or gap_seconds > 2:
        raise ValueError("gap_seconds must be between 0 and 2")
    if output_path.exists():
        raise ValueError("output path already exists")

    expected_format: tuple[int, int, int] | None = None
    payloads: list[bytes] = []
    audio_frames = 0
    for path in paths:
        with wave.open(str(path), "rb") as wav:
            current_format = (
                wav.getnchannels(),
                wav.getsampwidth(),
                wav.getframerate(),
            )
            if expected_format is None:
                expected_format = current_format
            elif current_format != expected_format:
                raise ValueError("WAV format mismatch")
            frames = wav.getnframes()
            audio_frames += frames
            payloads.append(wav.readframes(frames))

    assert expected_format is not None
    channels, sample_width, sample_rate = expected_format
    if expected_format != (1, 2, 24000):
        raise ValueError("WAV format mismatch: expected mono PCM16 24 kHz")
    gap_frames = round(gap_seconds * sample_rate)
    silence = b"\x00" * gap_frames * channels * sample_width
    combined = silence.join(payloads)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(output_path), "wb") as wav:
        wav.setnchannels(channels)
        wav.setsampwidth(sample_width)
        wav.setframerate(sample_rate)
        wav.writeframes(combined)

    total_frames = audio_frames + gap_frames * (len(paths) - 1)
    return {
        "output_path": str(output_path.resolve()),
        "sha256": sha256(output_path),
        "sample_rate_hz": sample_rate,
        "channels": channels,
        "sample_width_bytes": sample_width,
        "segment_count": len(paths),
        "gap_seconds": gap_seconds,
        "gap_frames": gap_frames,
        "audio_frames": audio_frames,
        "total_frames": total_frames,
        "duration_seconds": total_frames / sample_rate,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mapping", type=Path, required=True)
    parser.add_argument("--acceptance", type=Path, required=True)
    parser.add_argument("--excerpt", type=Path, required=True)
    parser.add_argument("--plan-output", type=Path, required=True)
    parser.add_argument("--segment-wav", action="append", type=Path, default=[])
    parser.add_argument("--output", type=Path)
    parser.add_argument("--gap-seconds", type=float, default=0.8)
    args = parser.parse_args()

    plan = build_render_plan(
        json.loads(args.mapping.read_text()),
        json.loads(args.acceptance.read_text()),
        json.loads(args.excerpt.read_text()),
    )
    args.plan_output.write_text(
        json.dumps(plan, ensure_ascii=False, indent=2) + "\n"
    )
    result: dict[str, Any] = {"render_plan": plan}
    if args.segment_wav:
        if args.output is None:
            parser.error("--output is required with --segment-wav")
        result["audio"] = concatenate_wavs(
            args.segment_wav, args.output, gap_seconds=args.gap_seconds
        )
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
