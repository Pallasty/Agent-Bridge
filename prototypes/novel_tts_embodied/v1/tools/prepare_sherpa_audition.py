#!/usr/bin/env python3
"""Generate an auditable, unlabeled Sherpa-ONNX speaker audition pack.

The model's speaker IDs do not include gender metadata.  This tool deliberately
uses neutral candidate labels and writes a manifest for a human listening pass.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys


DEFAULT_SPEAKER_IDS = (0, 7, 18, 26, 42, 58, 73, 91, 108, 126, 143, 160)
DEFAULT_TEXT = "这是中文小说朗读试听样本。请根据音色、清晰度和适合作品旁白或角色配音的程度进行标注。"


def _parse_speaker_ids(raw: str) -> list[int]:
    values: list[int] = []
    seen: set[int] = set()
    for part in raw.split(","):
        part = part.strip()
        if not part:
            continue
        try:
            speaker_id = int(part)
        except ValueError as exc:
            raise ValueError(f"invalid speaker ID: {part!r}") from exc
        if speaker_id < 0:
            raise ValueError(f"speaker ID must be non-negative: {speaker_id}")
        if speaker_id not in seen:
            seen.add(speaker_id)
            values.append(speaker_id)
    if not values:
        raise ValueError("at least one speaker ID is required")
    return values


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate an unlabeled Sherpa Chinese speaker audition pack")
    parser.add_argument("--synthesizer", required=True, help="path to ab-sherpa-tts-synth")
    parser.add_argument("--model-dir", required=True, help="directory containing the Sherpa VITS model assets")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--speaker-ids", default=",".join(map(str, DEFAULT_SPEAKER_IDS)))
    parser.add_argument("--text", default=DEFAULT_TEXT)
    parser.add_argument("--speed", type=float, default=1.0)
    args = parser.parse_args()

    if args.speed <= 0:
        raise SystemExit("--speed must be positive")
    try:
        speaker_ids = _parse_speaker_ids(args.speaker_ids)
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc

    synthesizer = Path(args.synthesizer)
    model_dir = Path(args.model_dir)
    if not synthesizer.is_file():
        raise SystemExit(f"synthesizer not found: {synthesizer}")
    if not model_dir.is_dir():
        raise SystemExit(f"model directory not found: {model_dir}")

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    voice_map = ",".join(f"candidate_{speaker_id:03d}={speaker_id}" for speaker_id in speaker_ids)
    env = os.environ.copy()
    env["AB_TTS_SHERPA_MODEL_DIR"] = str(model_dir)
    env["AB_TTS_SHERPA_VOICE_MAP"] = voice_map

    samples = []
    for speaker_id in speaker_ids:
        label = f"candidate_{speaker_id:03d}"
        wav_path = out_dir / f"{label}.wav"
        proc = subprocess.run(
            [
                str(synthesizer),
                "--text",
                args.text,
                "--voice",
                label,
                "--speed",
                str(args.speed),
                "--out",
                str(wav_path),
            ],
            env=env,
            text=True,
            capture_output=True,
            check=False,
        )
        if proc.returncode != 0 or not wav_path.is_file() or wav_path.stat().st_size <= 44:
            raise SystemExit(f"synthesis failed for speaker {speaker_id}: {proc.stdout}{proc.stderr}".strip())
        samples.append(
            {
                "candidate": label,
                "speaker_id": speaker_id,
                "audio_file": wav_path.name,
                "audio_sha256": _sha256(wav_path),
                "label_status": "unreviewed",
                "gender": None,
                "recommended_role": None,
            }
        )

    manifest = {
        "schema_version": "sherpa_audition_pack:v1",
        "backend": "sherpa-vits",
        "model_dir": str(model_dir),
        "text": args.text,
        "speed": args.speed,
        "speaker_count_claimed_by_model": 174,
        "labeling_rule": "Speaker IDs are not gender labels. Assign gender or narrative roles only after human listening review.",
        "samples": samples,
    }
    manifest_path = out_dir / "audition_manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": "ok", "manifest": str(manifest_path), "samples": len(samples)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
