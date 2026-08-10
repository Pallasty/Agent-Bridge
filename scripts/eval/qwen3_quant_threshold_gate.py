#!/usr/bin/env python3
"""Fail-closed pre-candidate gate for Qwen3-TTS quantization evidence."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate_baseline(baseline: dict, expected: dict, integrity: dict, label: str) -> list[str]:
    failures = []
    if baseline.get("schema") != "agent_bridge.qwen3_tts.fp16_baseline.v0":
        failures.append(f"{label}:unexpected_baseline_schema")
    if baseline.get("corpus", {}).get("sha256") != expected["corpus_sha256"]:
        failures.append(f"{label}:corpus_hash_mismatch")
    health = baseline.get("worker_health", {})
    for field in ("engine", "device", "dtype"):
        if health.get(field) != expected[field]:
            failures.append(f"{label}:worker_{field}_mismatch")
    if baseline.get("summary", {}).get("succeeded") != expected["cases"]:
        failures.append(f"{label}:baseline_not_all_cases_succeeded")
    for row in baseline.get("rows", []):
        audio = row.get("audio", {})
        case_id = row.get("case", {}).get("id", "unknown")
        if row.get("status") != "ok":
            failures.append(f"{label}:case_failed:{case_id}")
        if audio.get("sample_rate") != integrity["wav_sample_rate_exact"]:
            failures.append(f"{label}:wav_sample_rate_mismatch:{case_id}")
        if audio.get("channels") != integrity["wav_channels_exact"]:
            failures.append(f"{label}:wav_channels_mismatch:{case_id}")
        if audio.get("sample_width_bytes") != integrity["wav_sample_width_bytes_exact"]:
            failures.append(f"{label}:wav_sample_width_mismatch:{case_id}")
    return failures


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--thresholds", required=True, type=Path)
    parser.add_argument("--baseline", required=True, type=Path)
    parser.add_argument("--repeat-baseline", action="append", default=[], type=Path)
    parser.add_argument("--stt-reference", type=Path)
    parser.add_argument("--speaker-expression-reference", type=Path)
    parser.add_argument("--blinded-review-protocol", type=Path)
    args = parser.parse_args()
    thresholds = json.loads(args.thresholds.read_text(encoding="utf-8"))
    baseline_paths = [args.baseline, *args.repeat_baseline]
    baselines = [json.loads(path.read_text(encoding="utf-8")) for path in baseline_paths]
    baseline = baselines[0]
    failures = []
    blockers = []
    expected = thresholds["source_baseline"]
    integrity = thresholds["hard_gates"]["artifact_integrity"]
    for index, item in enumerate(baselines, 1):
        failures.extend(validate_baseline(item, expected, integrity, f"baseline_{index}"))
    for name in ("intelligibility", "speaker_and_expression", "human_exact_artifact"):
        status = thresholds["hard_gates"][name].get("status", "")
        if status.startswith("BLOCKED_"):
            blockers.append(f"{name}:{status}")
    expected_stt = thresholds.get("source_stt_reference")
    if expected_stt:
        if args.stt_reference is None:
            blockers.append("stt_reference:not_supplied")
        else:
            stt = json.loads(args.stt_reference.read_text(encoding="utf-8"))
            if sha256(args.stt_reference) != expected_stt["report_sha256"]:
                failures.append("stt_reference_hash_mismatch")
            if stt.get("summary", {}).get("cases") != expected_stt["cases"]:
                failures.append("stt_reference_case_count_mismatch")
    expected_speaker_expression = thresholds.get("source_speaker_expression_reference")
    if expected_speaker_expression:
        if args.speaker_expression_reference is None:
            blockers.append("speaker_expression_reference:not_supplied")
        else:
            reference = json.loads(args.speaker_expression_reference.read_text(encoding="utf-8"))
            if sha256(args.speaker_expression_reference) != expected_speaker_expression["report_sha256"]:
                failures.append("speaker_expression_reference_hash_mismatch")
            if reference.get("schema") != expected_speaker_expression["schema"]:
                failures.append("speaker_expression_reference_schema_mismatch")
            summary = reference.get("summary", {})
            if summary.get("cases") != expected_speaker_expression["cases"] or summary.get("fp16_runs") != expected_speaker_expression["fp16_runs"]:
                failures.append("speaker_expression_reference_coverage_mismatch")
    expected_review = thresholds.get("blinded_review_protocol")
    if expected_review:
        if args.blinded_review_protocol is None:
            blockers.append("blinded_review_protocol:not_supplied")
        elif sha256(args.blinded_review_protocol) != expected_review["sha256"]:
            failures.append("blinded_review_protocol_hash_mismatch")
    required_repetitions = thresholds["comparison_protocol"]["required_repetitions_per_case"]
    if len(baselines) < required_repetitions:
        blockers.append(f"fp16_repetitions:{required_repetitions}_required_{len(baselines)}_observed")
    state = "INVALID_BASELINE" if failures else ("BLOCKED_PENDING_REFERENCE_EVIDENCE" if blockers else "READY_FOR_CANDIDATE_REVIEW")
    result = {
        "schema": "agent_bridge.qwen3_tts.quantization_pre_candidate_gate.v0",
        "state": state,
        "thresholds_sha256": sha256(args.thresholds),
        "baseline_sha256": sha256(args.baseline),
        "baseline_repetition_sha256": [sha256(path) for path in baseline_paths],
        "failures": sorted(set(failures)),
        "blockers": blockers,
        "allows_candidate_generation": False,
        "allows_runtime_wiring_or_promotion": False,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 2 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
