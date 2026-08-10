#!/usr/bin/env python3
"""Capture pinned CAM++ embeddings and cross-run speaker-consistency reference."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path


SCHEMA = "agent_bridge.qwen3_tts.speaker_reference.v0"
REQUIRED_ANCHORS = ("configuration.json", "campplus_cn_common.bin")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def cosine(left: list[float], right: list[float]) -> float:
    if len(left) != len(right) or not left:
        raise ValueError("embeddings must be non-empty and equal-sized")
    denominator = math.sqrt(sum(value * value for value in left) * sum(value * value for value in right))
    if denominator == 0:
        raise ValueError("embedding norm must be non-zero")
    return sum(a * b for a, b in zip(left, right)) / denominator


def vector_from_result(result: list[dict]) -> list[float]:
    if len(result) != 1 or "spk_embedding" not in result[0]:
        raise ValueError("expected exactly one speaker embedding")
    embedding = result[0]["spk_embedding"].detach().cpu().reshape(-1).tolist()
    if not embedding:
        raise ValueError("speaker embedding was empty")
    return [float(value) for value in embedding]


def parse_run(value: str) -> tuple[Path, Path]:
    try:
        report, audio = value.split("=", 1)
    except ValueError as error:
        raise argparse.ArgumentTypeError("run must be BASELINE_REPORT=AUDIO_DIRECTORY") from error
    return Path(report), Path(audio)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", action="append", required=True, type=parse_run)
    parser.add_argument("--model-path", required=True, type=Path)
    parser.add_argument("--model-id", required=True)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("refusing to overwrite output")
    if len(args.run) < 2:
        parser.error("at least two FP16 runs are required")
    missing = [name for name in REQUIRED_ANCHORS if not (args.model_path / name).is_file()]
    if missing:
        parser.error(f"incomplete speaker model snapshot: missing {', '.join(missing)}")

    run_inputs = []
    for report_path, audio_dir in args.run:
        if not report_path.is_file() or not audio_dir.is_dir():
            parser.error("every run needs an existing report and audio directory")
        report = json.loads(report_path.read_text(encoding="utf-8"))
        if report.get("schema") != "agent_bridge.qwen3_tts.fp16_baseline.v0" or report.get("summary", {}).get("failed") != 0:
            parser.error(f"invalid FP16 baseline: {report_path}")
        run_inputs.append((report_path, audio_dir, report))
    case_ids = [row["case"]["id"] for row in run_inputs[0][2]["rows"]]
    if any([row["case"]["id"] for row in report["rows"]] != case_ids for _, _, report in run_inputs[1:]):
        parser.error("FP16 runs must have matching case order")

    from funasr import AutoModel
    model = AutoModel(model=str(args.model_path), device="cpu", disable_update=True)
    runs = []
    for report_path, audio_dir, report in run_inputs:
        rows = []
        for index, baseline_row in enumerate(report["rows"], start=1):
            case_id = baseline_row["case"]["id"]
            wav = audio_dir / f"{index:02d}-{case_id}.wav"
            if not wav.is_file():
                parser.error(f"missing expected baseline WAV: {wav}")
            vector = vector_from_result(model.generate(input=str(wav)))
            rows.append({"case_id": case_id, "audio_sha256": sha256(wav), "embedding": vector})
        runs.append({"baseline_report_sha256": sha256(report_path), "audio_dir": str(audio_dir), "rows": rows})

    comparisons = []
    all_scores = []
    for index, case_id in enumerate(case_ids):
        reference = runs[0]["rows"][index]["embedding"]
        scores = [cosine(reference, run["rows"][index]["embedding"]) for run in runs[1:]]
        all_scores.extend(scores)
        comparisons.append({"case_id": case_id, "cosine_to_first_run": scores, "min_cosine": min(scores), "mean_cosine": sum(scores) / len(scores)})
    report = {
        "schema": SCHEMA,
        "status": "SPEAKER_REFERENCE_CAPTURED",
        "model": {"id": args.model_id, "path": str(args.model_path), "weights_sha256": sha256(args.model_path / "campplus_cn_common.bin")},
        "execution": {"runtime": "FunASR", "device": "cpu", "comparison": "cosine(first_run_embedding, repeat_run_embedding)"},
        "runs": runs,
        "comparisons": comparisons,
        "summary": {"cases": len(case_ids), "runs": len(runs), "pairwise_scores": len(all_scores), "min_cosine": min(all_scores), "mean_cosine": sum(all_scores) / len(all_scores)},
        "metric_boundary": "Cross-run same-case speaker embedding consistency only; no enrolled named-voice identity, human listening, expression adherence, or promotion authorization.",
        "allows_candidate_generation": False,
        "allows_runtime_wiring_or_promotion": False,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": report["status"], **report["summary"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
