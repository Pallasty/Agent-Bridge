#!/usr/bin/env python3
"""Capture a pinned, offline emotion-classification reference for FP16 WAVs."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


SCHEMA = "agent_bridge.qwen3_tts.emotion_reference.v0"
REQUIRED_ANCHORS = ("configuration.json", "model.pt")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def classify_result(result: list[dict]) -> dict:
    if len(result) != 1 or not isinstance(result[0], dict):
        raise ValueError("expected exactly one FunASR result")
    row = result[0]
    labels, scores = row.get("labels"), row.get("scores")
    if not isinstance(labels, list) or not isinstance(scores, list) or len(labels) != len(scores) or not labels:
        raise ValueError("FunASR result lacks aligned labels and scores")
    values = [float(score) for score in scores]
    top_index = max(range(len(values)), key=values.__getitem__)
    return {"labels": labels, "scores": values, "top_label": labels[top_index], "top_score": values[top_index]}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline-report", required=True, type=Path)
    parser.add_argument("--audio-dir", required=True, type=Path)
    parser.add_argument("--model-path", required=True, type=Path)
    parser.add_argument("--model-id", required=True)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("refusing to overwrite output")
    if not args.baseline_report.is_file() or not args.audio_dir.is_dir():
        parser.error("baseline report and audio directory must exist")
    missing = [name for name in REQUIRED_ANCHORS if not (args.model_path / name).is_file()]
    if missing:
        parser.error(f"incomplete emotion model snapshot: missing {', '.join(missing)}")
    baseline = json.loads(args.baseline_report.read_text(encoding="utf-8"))
    if baseline.get("schema") != "agent_bridge.qwen3_tts.fp16_baseline.v0":
        parser.error("unexpected baseline schema")
    if baseline.get("summary", {}).get("failed") != 0:
        parser.error("baseline contains failed rows")

    from funasr import AutoModel
    model = AutoModel(model=str(args.model_path), device="cpu", disable_update=True)
    rows = []
    for baseline_row in baseline["rows"]:
        case_id = baseline_row["case"]["id"]
        wav = args.audio_dir / f"{len(rows) + 1:02d}-{case_id}.wav"
        if not wav.is_file():
            parser.error(f"missing expected baseline WAV: {wav}")
        result = model.generate(input=str(wav), granularity="utterance", extract_embedding=False)
        rows.append({
            "case_id": case_id,
            "audio_sha256": sha256(wav),
            "classification": classify_result(result),
        })
    report = {
        "schema": SCHEMA,
        "status": "EMOTION_REFERENCE_CAPTURED",
        "baseline_report_sha256": sha256(args.baseline_report),
        "model": {"id": args.model_id, "path": str(args.model_path), "model_pt_sha256": sha256(args.model_path / "model.pt")},
        "execution": {"runtime": "FunASR", "device": "cpu", "granularity": "utterance", "extract_embedding": False},
        "summary": {"cases": len(rows), "succeeded": len(rows), "failed": 0},
        "rows": rows,
        "metric_boundary": "Reference categorical emotion output only; it is not a speaker metric, human listening result, or candidate-promotion authorization.",
        "allows_candidate_generation": False,
        "allows_runtime_wiring_or_promotion": False,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": report["status"], "cases": len(rows), "model_id": args.model_id}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
