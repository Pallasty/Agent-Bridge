#!/usr/bin/env python3
"""Build a fixed Whisper CER reference over a Qwen3-TTS baseline capture."""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import tempfile
import unicodedata
from pathlib import Path


def normalize(text: str) -> str:
    normalized = unicodedata.normalize("NFKC", text).lower()
    return "".join(char for char in normalized if char.isalnum() or "\u4e00" <= char <= "\u9fff")


def edit_distance(left: str, right: str) -> int:
    previous = list(range(len(right) + 1))
    for index, lchar in enumerate(left, 1):
        current = [index]
        for offset, rchar in enumerate(right, 1):
            current.append(min(current[-1] + 1, previous[offset] + 1,
                               previous[offset - 1] + (lchar != rchar)))
        previous = current
    return previous[-1]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", required=True, type=Path)
    parser.add_argument("--audio-dir", required=True, type=Path)
    parser.add_argument("--whisper", required=True, type=Path)
    parser.add_argument("--model", default="base")
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--timeout", type=float, default=180.0)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("refusing to overwrite output")
    baseline = json.loads(args.baseline.read_text(encoding="utf-8"))
    rows = []
    for index, source in enumerate(baseline["rows"], 1):
        case = source["case"]
        audio = args.audio_dir / f"{index:02d}-{case['id']}.wav"
        if sha256(audio) != source["audio"]["sha256"]:
            raise RuntimeError(f"audio hash mismatch: {case['id']}")
        with tempfile.TemporaryDirectory(prefix="ab-qwen3-stt-") as temp:
            command = [str(args.whisper), str(audio), "--model", args.model,
                       "--language", "zh", "--output_format", "txt",
                       "--output_dir", temp, "--fp16", "False", "--verbose", "False",
                       "--initial_prompt", "以下是普通话的简体中文句子。"]
            completed = subprocess.run(command, capture_output=True, text=True,
                                       timeout=args.timeout, check=False)
            transcript_file = Path(temp) / f"{audio.stem}.txt"
            if completed.returncode != 0 or not transcript_file.is_file():
                raise RuntimeError(f"whisper failed for {case['id']}: {(completed.stderr or '')[:300]}")
            transcript = transcript_file.read_text(encoding="utf-8").strip()
        reference_normalized = normalize(case["text"])
        transcript_normalized = normalize(transcript)
        distance = edit_distance(reference_normalized, transcript_normalized)
        cer = distance / max(1, len(reference_normalized))
        rows.append({"id": case["id"], "reference": case["text"],
                     "transcript": transcript, "reference_normalized": reference_normalized,
                     "transcript_normalized": transcript_normalized,
                     "edit_distance": distance, "cer": cer,
                     "audio_sha256": source["audio"]["sha256"]})
        print(json.dumps({"index": index, "id": case["id"], "cer": cer}, ensure_ascii=False), flush=True)
    cers = sorted(row["cer"] for row in rows)
    report = {
        "schema": "agent_bridge.qwen3_tts.stt_reference.v0",
        "status": "FP16_STT_REFERENCE_CAPTURED",
        "baseline_sha256": sha256(args.baseline),
        "whisper": {"binary": str(args.whisper), "model": args.model, "language": "zh"},
        "normalization": "unicode_nfkc_lower_keep_alnum_and_cjk_unified_ideographs",
        "summary": {"cases": len(rows), "mean_cer": sum(cers) / len(cers),
                    "median_cer": cers[len(cers) // 2], "max_cer": max(cers)},
        "rows": rows,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report["summary"], ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
