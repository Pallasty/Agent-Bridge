#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for raw in f:
            raw = raw.strip()
            if not raw:
                continue
            rows.append(json.loads(raw))
    return rows


def _validate_manifest(manifest: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    required = {"version", "created_at", "input", "segments_path", "fallback_stats", "segments", "summary"}
    missing = required.difference(manifest.keys())
    if missing:
        errors.append(f"manifest missing fields: {sorted(missing)}")
        return errors

    required_summary = {"segment_count", "total_chars", "estimated_total_sec", "duration_sec"}
    if not isinstance(manifest.get("summary"), dict):
        errors.append("manifest.summary must be object")
    else:
        missing_summary = required_summary.difference(manifest["summary"].keys())
        if missing_summary:
            errors.append(f"manifest.summary missing fields: {sorted(missing_summary)}")

    fallback = manifest.get("fallback_stats")
    if not isinstance(fallback, dict):
        errors.append("manifest.fallback_stats must be object")
    else:
        for key in ("fallback_segments", "needs_review", "failed_segments"):
            if not isinstance(fallback.get(key), int):
                errors.append(f"manifest.fallback_stats.{key} must be int")

    ann = manifest.get("annotation_issues")
    if ann is not None and not isinstance(ann, dict):
        errors.append("manifest.annotation_issues must be object if present")
    return errors


def _validate_segment_row(row: dict[str, Any], idx: int) -> list[str]:
    errors: list[str] = []
    required = {
        "segment_id",
        "chapter",
        "index",
        "text",
        "speaker",
        "emotion",
        "voice_profile",
        "status",
        "audio_plan",
    }
    if missing := required.difference(row.keys()):
        errors.append(f"segments[{idx}] missing fields: {sorted(missing)}")

    speaker = row.get("speaker")
    if isinstance(speaker, dict):
        for field in ("id", "name", "gender", "confidence"):
            if field not in speaker:
                errors.append(f"segments[{idx}] speaker missing {field}")
        if speaker.get("gender") not in {"unknown", "male", "female", "narrator"}:
            errors.append(f"segments[{idx}] speaker.gender invalid")
        conf = speaker.get("confidence")
        if not isinstance(conf, (int, float)):
            errors.append(f"segments[{idx}] speaker.confidence must be number")
    else:
        errors.append(f"segments[{idx}].speaker must be object")

    emotion = row.get("emotion")
    if isinstance(emotion, dict):
        for field in ("label", "intensity", "confidence"):
            if field not in emotion:
                errors.append(f"segments[{idx}] emotion missing {field}")
        if emotion.get("label") not in {"neutral", "calm", "happy", "sad", "angry", "tense"}:
            errors.append(f"segments[{idx}] emotion.label invalid")
        intensity = emotion.get("intensity")
        if not isinstance(intensity, int) or not (0 <= intensity <= 2):
            errors.append(f"segments[{idx}] emotion.intensity out of range")
    else:
        errors.append(f"segments[{idx}].emotion must be object")

    voice = row.get("voice_profile")
    if isinstance(voice, dict):
        for field in ("voice_key", "backend", "speed", "pause_ms", "gain_db", "pitch_shift"):
            if field not in voice:
                errors.append(f"segments[{idx}] voice_profile missing {field}")
    else:
        errors.append(f"segments[{idx}].voice_profile must be object")

    plan = row.get("audio_plan")
    if isinstance(plan, dict):
        for field in ("segment_hash", "output_file", "estimated_duration_sec", "cached"):
            if field not in plan:
                errors.append(f"segments[{idx}] audio_plan missing {field}")
    else:
        errors.append(f"segments[{idx}].audio_plan must be object")
    return errors


def _validate_segments(path: Path, expect_count: int | None = None) -> list[str]:
    rows = _read_jsonl(path)
    errors: list[str] = []
    if expect_count is not None and len(rows) != expect_count:
        errors.append(f"segments count mismatch: expected={expect_count}, actual={len(rows)}")
    for idx, row in enumerate(rows):
        if not isinstance(row, dict):
            errors.append(f"segments[{idx}] not object")
            continue
        errors.extend(_validate_segment_row(row, idx))
    return errors


def _validate_plan_row(row: dict[str, Any], idx: int, segment: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    prefix = f"embodiment_plan[{idx}]"
    required = {"task_id", "order", "segment_id", "tool", "priority", "retry_policy", "tool_args", "segment_status"}
    if missing := required.difference(row.keys()):
        errors.append(f"{prefix} missing fields: {sorted(missing)}")
        return errors

    if not isinstance(row["task_id"], str):
        errors.append(f"{prefix}.task_id must be string")
    if not isinstance(row["order"], int) or row["order"] != idx + 1:
        errors.append(f"{prefix}.order must equal {idx + 1}")
    if row["segment_id"] != segment.get("segment_id"):
        errors.append(f"{prefix}.segment_id does not match segments[{idx}]")
    if row["tool"] != "present_voice":
        errors.append(f"{prefix}.tool must be present_voice")
    if row["priority"] not in {"low", "normal", "high", "critical"}:
        errors.append(f"{prefix}.priority invalid")
    if row["segment_status"] != segment.get("status"):
        errors.append(f"{prefix}.segment_status does not match segments[{idx}]")

    retry = row["retry_policy"]
    if not isinstance(retry, dict):
        errors.append(f"{prefix}.retry_policy must be object")
    else:
        for field in ("retry_limit", "cooldown_ms", "backoff_ms"):
            value = retry.get(field)
            if not isinstance(value, int) or value < 0:
                errors.append(f"{prefix}.retry_policy.{field} must be non-negative int")

    args = row["tool_args"]
    if not isinstance(args, dict):
        errors.append(f"{prefix}.tool_args must be object")
        return errors
    required_args = {"backend", "text", "voice", "speed", "pause_ms", "gain_db", "pitch_shift", "output_file", "segment_hash", "estimated_duration_sec"}
    if missing := required_args.difference(args.keys()):
        errors.append(f"{prefix}.tool_args missing fields: {sorted(missing)}")
        return errors
    for field in ("backend", "text", "voice", "output_file", "segment_hash"):
        if not isinstance(args[field], str) or not args[field]:
            errors.append(f"{prefix}.tool_args.{field} must be non-empty string")
    for field, minimum, maximum in (("speed", 0.5, 2.0), ("pause_ms", 0, 3000), ("gain_db", -6, 6), ("pitch_shift", -6, 6)):
        value = args[field]
        if not isinstance(value, (int, float)) or not minimum <= value <= maximum:
            errors.append(f"{prefix}.tool_args.{field} out of range")
    duration = args["estimated_duration_sec"]
    if not isinstance(duration, (int, float)) or duration < 0:
        errors.append(f"{prefix}.tool_args.estimated_duration_sec must be non-negative number")

    audio_plan = segment.get("audio_plan") if isinstance(segment.get("audio_plan"), dict) else {}
    voice_profile = segment.get("voice_profile") if isinstance(segment.get("voice_profile"), dict) else {}
    for field in ("output_file", "segment_hash", "estimated_duration_sec"):
        if args.get(field) != audio_plan.get(field):
            errors.append(f"{prefix}.tool_args.{field} does not match segments[{idx}].audio_plan")
    for plan_field, segment_field in (("text", "text"), ("voice", "voice_key"), ("speed", "speed"), ("pause_ms", "pause_ms"), ("gain_db", "gain_db"), ("pitch_shift", "pitch_shift")):
        expected = segment.get(segment_field) if plan_field == "text" else voice_profile.get(segment_field)
        if args.get(plan_field) != expected:
            errors.append(f"{prefix}.tool_args.{plan_field} does not match segments[{idx}]")
    return errors


def _validate_plan(path: Path, segments: list[dict[str, Any]]) -> list[str]:
    rows = _read_jsonl(path)
    errors: list[str] = []
    if len(rows) != len(segments):
        errors.append(f"embodiment_plan count mismatch: expected={len(segments)}, actual={len(rows)}")
    for idx, row in enumerate(rows):
        if not isinstance(row, dict):
            errors.append(f"embodiment_plan[{idx}] not object")
        elif idx < len(segments):
            errors.extend(_validate_plan_row(row, idx, segments[idx]))
    return errors


def _ensure_manifest_paths(manifest: dict[str, Any], output_dir: Path) -> list[str]:
    errors: list[str] = []
    for key in ("segments_path",):
        p = output_dir / Path(manifest.get(key) or "")
        if not p.is_file():
            if isinstance(manifest.get(key), str):
                p = Path(manifest[key])
            if not p.exists():
                errors.append(f"manifest[{key}] missing: {manifest.get(key)}")
    plan = output_dir / "embodiment_plan.jsonl"
    if not plan.exists():
        errors.append("embodiment_plan.jsonl missing")
    return errors


def _validate_result(path: Path, manifest_path: str, segment_path: str) -> list[str]:
    errors: list[str] = []
    payload = _read_json(path)
    if not isinstance(payload, dict):
        return ["result.json must be object"]

    if payload.get("manifest_path") != manifest_path:
        errors.append("result.manifest_path mismatch")
    if payload.get("segments_path") != segment_path:
        errors.append("result.segments_path mismatch")

    for key in ("status", "summary", "segment_count", "needs_review_count"):
        if key not in payload:
            errors.append(f"result missing {key}")
    return errors


def run_validation(output_dir: Path, require_plan: bool = False) -> int:
    errors: list[str] = []

    seg_path = output_dir / "segments.jsonl"
    manifest_path = output_dir / "manifest.json"
    result_path = output_dir / "result.json"

    for p, name in ((seg_path, "segments.jsonl"), (manifest_path, "manifest.json")):
        if not p.exists():
            errors.append(f"missing {name}")

    if errors:
        print("\n".join(errors))
        return 1

    manifest = _read_json(manifest_path)
    errors.extend(_validate_manifest(manifest))

    plan_path = output_dir / "embodiment_plan.jsonl"
    if require_plan and not plan_path.exists():
        errors.append("missing embodiment_plan.jsonl (require-plan enabled)")

    seg_rows = _read_jsonl(seg_path)
    errors.extend(_validate_segments(seg_path, expect_count=manifest["summary"]["segment_count"]))
    if plan_path.exists():
        errors.extend(_validate_plan(plan_path, seg_rows))

    errors.extend(_ensure_manifest_paths(manifest, output_dir))

    if result_path.exists():
        errors.extend(
            _validate_result(
                result_path,
                manifest_path=str(manifest_path),
                segment_path=str(seg_path),
            )
        )

    # 如果存在回执文件，确认执行器输出结构基础字段可读
    results_path = output_dir / "present_voice_results.jsonl"
    if results_path.exists():
        with results_path.open("r", encoding="utf-8") as f:
            for line_no, raw in enumerate(f, start=1):
                raw = raw.strip()
                if not raw:
                    continue
                try:
                    row = json.loads(raw)
                except json.JSONDecodeError:
                    errors.append(f"present_voice_results[{line_no}] not json")
                    break
                if not isinstance(row, dict):
                    errors.append(f"present_voice_results[{line_no}] should be object")
                for field in ("status", "segment_id", "action_id", "attempts"):
                    if field not in row:
                        errors.append(f"present_voice_results[{line_no}] missing {field}")
                of = row.get("output_file")
                if of and not Path(of).is_absolute():
                    of = str((output_dir / of))
                if of and not Path(of).exists():
                    # 非硬判错：允许执行器不落盘，仅记录状态
                    pass

    if errors:
        print("\n".join(errors))
        return 1

    print("validation ok")
    return 0


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Validate novel_tts_embodied pipeline outputs")
    ap.add_argument("--output-dir", required=True)
    ap.add_argument("--require-plan", action="store_true", help="fail when embodiment_plan.jsonl missing")
    return ap.parse_args()


def main() -> None:
    args = parse_args()
    output_dir = Path(args.output_dir)
    code = run_validation(output_dir=output_dir, require_plan=args.require_plan)
    raise SystemExit(code)


if __name__ == "__main__":
    main()
