#!/usr/bin/env python3
"""Bind pinned speaker and emotion references into one fail-closed evidence receipt."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


SCHEMA = "agent_bridge.qwen3_tts.speaker_expression_reference.v0"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--speaker-reference", required=True, type=Path)
    parser.add_argument("--emotion-reference", required=True, action="append", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("refusing to overwrite output")
    if len(args.emotion_reference) != 3:
        parser.error("exactly three emotion references are required")
    if not args.speaker_reference.is_file() or any(not path.is_file() for path in args.emotion_reference):
        parser.error("all reference reports must exist")
    speaker = json.loads(args.speaker_reference.read_text(encoding="utf-8"))
    emotions = [json.loads(path.read_text(encoding="utf-8")) for path in args.emotion_reference]
    if speaker.get("schema") != "agent_bridge.qwen3_tts.speaker_reference.v0" or speaker.get("summary", {}).get("runs") != 3 or speaker.get("summary", {}).get("cases") != 16:
        parser.error("speaker reference is incomplete")
    if any(report.get("schema") != "agent_bridge.qwen3_tts.emotion_reference.v0" or report.get("summary", {}).get("cases") != 16 for report in emotions):
        parser.error("emotion reference is incomplete")
    speaker_baselines = [run["baseline_report_sha256"] for run in speaker["runs"]]
    emotion_baselines = [report["baseline_report_sha256"] for report in emotions]
    if speaker_baselines != emotion_baselines:
        parser.error("speaker and emotion references must cover identical baseline order")
    receipt = {
        "schema": SCHEMA,
        "status": "FP16_SPEAKER_EXPRESSION_REFERENCE_CAPTURED",
        "baseline_report_sha256": speaker_baselines,
        "speaker_reference_sha256": sha256(args.speaker_reference),
        "emotion_reference_sha256": [sha256(path) for path in args.emotion_reference],
        "summary": {"cases": 16, "fp16_runs": 3, "speaker_pairwise_scores": speaker["summary"]["pairwise_scores"], "speaker_min_cosine": speaker["summary"]["min_cosine"], "speaker_mean_cosine": speaker["summary"]["mean_cosine"]},
        "metric_boundary": "Pinned FP16 reference only; candidate comparison and human exact-artifact review remain separate gates.",
        "allows_candidate_generation": False,
        "allows_runtime_wiring_or_promotion": False,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": receipt["status"], **receipt["summary"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
