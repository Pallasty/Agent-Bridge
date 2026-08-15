#!/usr/bin/env python3
from __future__ import annotations

import os
import shlex
import subprocess
import time
from hashlib import sha256
from pathlib import Path
import argparse
import json
import re
from dataclasses import dataclass
from typing import Any, Dict, Optional

try:
    from . import pipeline
except ImportError:  # direct run from source directory
    import pipeline


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _now_ms() -> int:
    return int(time.time() * 1000)


def _coerce_int(value: Any, default: Optional[int] = None) -> Optional[int]:
    if value is None:
        return default
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        s = value.strip()
        if not s:
            return default
        try:
            return int(s)
        except ValueError:
            try:
                return int(float(s))
            except ValueError:
                return default
    return default


def _coalesce_int(*values: Any) -> Optional[int]:
    for value in values:
        coerced = _coerce_int(value)
        if coerced is not None:
            return coerced
    return None


def _coerce_str(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, str):
        s = value.strip()
        return s if s else None
    return str(value).strip()


def _sha256_file(path: Path) -> Optional[str]:
    if not path.is_file():
        return None
    h = sha256()
    try:
        with path.open("rb") as f:
            for chunk in iter(lambda: f.read(1024 * 1024), b""):
                h.update(chunk)
    except OSError:
        return None
    return h.hexdigest()


def _extract_json_candidates(text: str) -> list[str]:
    candidates: list[str] = []
    for line in text.splitlines():
        s = line.strip()
        if s:
            candidates.append(s)

    in_str = False
    escape = False
    depth = 0
    start = -1
    for i, ch in enumerate(text):
        if in_str:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_str = False
            continue

        if ch == '"':
            in_str = True
            continue

        if ch == "{":
            if depth == 0:
                start = i
            depth += 1
            continue

        if ch == "}" and depth > 0:
            depth -= 1
            if depth == 0 and start >= 0:
                candidates.append(text[start : i + 1].strip())
                start = -1

    return candidates


def _parse_status_token(text: str) -> Optional[str]:
    return _coerce_str(text)


def _parse_text_key_value(text: str, key: str) -> Optional[str]:
    pattern = re.compile(rf"(?:^|[\s,;]){re.escape(key)}\\s*[:=]\\s*([^\s,;\\n]+)", re.IGNORECASE)
    matches = pattern.findall(text)
    if not matches:
        return None
    return matches[-1].strip().strip('"\'')


def _extract_freeform_receipt(text: str) -> Dict[str, Any]:
    if not isinstance(text, str):
        return {}

    return {
        "status_code": _coalesce_int(
            _parse_text_key_value(text, "status_code"),
            _parse_text_key_value(text, "code"),
            _parse_text_key_value(text, "return_code"),
            _parse_text_key_value(text, "rc"),
        ),
        "raw_status": _parse_status_token(_parse_text_key_value(text, "status"))
        or _parse_status_token(_parse_text_key_value(text, "result"))
        or _parse_status_token(_parse_text_key_value(text, "state")),
        "verify_status": _parse_status_token(_parse_text_key_value(text, "verify_status"))
        or _parse_status_token(_parse_text_key_value(text, "verify")),
        "output_file": _coerce_str(_parse_text_key_value(text, "output_file"))
        or _coerce_str(_parse_text_key_value(text, "output"))
        or _coerce_str(_parse_text_key_value(text, "file")),
        "reason": _coerce_str(_parse_text_key_value(text, "message"))
        or _coerce_str(_parse_text_key_value(text, "error")),
    }


def _parse_json_output(text: str) -> Optional[Dict[str, Any]]:
    raw = text.strip()
    if not raw:
        return None
    candidates = [raw]
    candidates.extend(_extract_json_candidates(raw))
    for candidate in candidates:
        if not candidate:
            continue
        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            return parsed
    return None


def _resolve_output_file(output_file: Any, out_dir: Path) -> Optional[Path]:
    if not isinstance(output_file, str) or not output_file.strip():
        return None
    candidate = Path(output_file.strip())
    if candidate.is_absolute() and candidate.exists():
        return candidate
    if candidate.exists():
        return candidate
    fallback = out_dir / candidate
    return fallback if fallback.exists() else candidate


def _collect_output_file_fields(plan: Dict[str, Any], out_dir: Path, output_file_override: Optional[str] = None) -> Dict[str, Any]:
    tool_args = plan.get("tool_args", {})
    output_file = output_file_override
    if output_file is None and isinstance(tool_args, dict):
        output_file = tool_args.get("output_file")
    resolved_path = _resolve_output_file(output_file, out_dir)
    exists = False
    size: Optional[int] = None
    digest: Optional[str] = None
    if resolved_path:
        try:
            exists = resolved_path.is_file()
        except OSError:
            exists = False
        if exists:
            try:
                size = resolved_path.stat().st_size
            except OSError:
                size = None
            digest = _sha256_file(resolved_path)
    return {
        "output_file": str(output_file) if output_file is not None else None,
        "output_file_exists": exists,
        "output_file_size": size,
        "output_file_sha256": digest,
        "output_file_resolved": str(resolved_path) if resolved_path else None,
    }


def _is_success_status(status_code: Optional[int], proc_returncode: int, raw_status: Optional[str], verify_status: Optional[str]) -> bool:
    status_norm = (raw_status or "").strip().lower()
    verify_norm = (verify_status or "").lower()
    positive = {"ok", "success", "passed", "pass", "done", "completed", "finished", "verified"}
    negative = {"failed", "error", "rejected", "timeout", "exception", "cancelled", "mismatch", "invalid"}
    negative_verify = {"mismatch", "invalid", "failed", "error"}
    positive_verify = {"verified", "pass", "passed", "success", "ok"}

    if status_code is not None and status_code != 0:
        return False
    if proc_returncode != 0:
        return False

    if status_norm in positive and verify_norm in negative_verify:
        return False
    if status_norm in negative and verify_norm in positive_verify:
        return False

    if verify_norm in negative_verify:
        return False
    if verify_norm in positive_verify:
        return True

    if status_norm in negative:
        return False
    if status_norm in positive:
        return True

    return True


def _read_task_input(task_payload: Dict[str, Any], args: argparse.Namespace) -> Dict[str, Any]:
    # task payload shape:
    # {
    #   "input": {"path": "...", "text": "..."},
    #   "task_id": "xxx",
    #   "annotations": [...],   # optional
    #   "config": { ... }       # optional
    # }
    source_path: Optional[Path] = None
    text: Optional[str] = None
    if args.input:
        source_path = Path(args.input)
        text = source_path.read_text(encoding="utf-8")
    elif args.input_text:
        text = args.input_text
    else:
        task_input = task_payload.get("input", task_payload.get("task", {}))
        if isinstance(task_input, dict):
            if isinstance(task_input.get("text"), str):
                text = task_input["text"]
            if not text and isinstance(task_input.get("path"), str):
                source_path = Path(task_input["path"])
                text = source_path.read_text(encoding="utf-8")
    return {
        "task_id": task_payload.get("task_id") or task_payload.get("id"),
        "text": text,
        "source_path": source_path,
        "annotations": task_payload.get("annotations"),
        "config": task_payload.get("config", {}),
        "chapter": task_payload.get("chapter", 1),
    }


def _build_config(args: argparse.Namespace, task_cfg: Dict[str, Any]) -> Dict[str, Any]:
    cfg: Dict[str, Any] = dict(pipeline.DEFAULT_CONFIG)
    cfg.update(task_cfg or {})
    cfg.update(
        {
            "voice_male": args.voice_male,
            "voice_female": args.voice_female,
            "voice_narrator": args.voice_narrator,
            "voice_unknown": args.voice_unknown,
            "tts_backend": args.tts_backend,
            "segment_limit": args.segment_limit,
        }
    )
    # keep explicit CLI task-id-independent defaults stable
    return cfg


def _coalesce_annotations(args: argparse.Namespace, task_annotations: Any) -> Any:
    if args.annotation_json:
        return load_json(Path(args.annotation_json))
    return task_annotations


def _write_needs_review_file(segments: list, out_dir: Path) -> Optional[Path]:
    review = [s for s in segments if s["status"] == "needs_review"]
    if not review:
        return None
    out = out_dir / "needs_review.jsonl"
    with out.open("w", encoding="utf-8") as f:
        for row in review:
            f.write(json.dumps(row, ensure_ascii=False))
            f.write("\n")
    return out


@dataclass
class VoiceActionResult:
    segment_id: str
    status: str
    action_id: str
    attempts: int
    plan: Dict[str, Any]
    started_at_ms: Optional[int] = None
    finished_at_ms: Optional[int] = None
    latency_ms: Optional[int] = None
    status_code: Optional[int] = None
    raw_status: Optional[str] = None
    verify_status: Optional[str] = None
    executed: bool = False
    reason: str = ""
    output_file: Optional[str] = None
    output_file_exists: Optional[bool] = None
    output_file_size: Optional[int] = None
    output_file_sha256: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "segment_id": self.segment_id,
            "action_id": self.action_id,
            "status": self.status,
            "attempts": self.attempts,
            "started_at_ms": self.started_at_ms,
            "finished_at_ms": self.finished_at_ms,
            "latency_ms": self.latency_ms,
            "status_code": self.status_code,
            "raw_status": self.raw_status,
            "verify_status": self.verify_status,
            "executed": self.executed,
            "reason": self.reason,
            "plan": self.plan,
            "output_file": self.output_file,
            "output_file_exists": self.output_file_exists,
            "output_file_size": self.output_file_size,
            "output_file_sha256": self.output_file_sha256,
        }


def _normalize_plan_rows(rows: list[Dict[str, Any]]) -> list[Dict[str, Any]]:
    normalized: list[Dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        if "segment_id" not in row or "tool" not in row:
            continue
        normalized.append(row)
    return normalized


def _action_id_for(segment_id: str, order: int, task_id: str = "") -> str:
    suffix = task_id.strip() if task_id else "local"
    return f"{suffix}-{order:03d}-{segment_id}"


def _exec_present_voice(
    row: Dict[str, Any],
    executor: Optional[str],
    dry_run: bool = False,
    out_dir: Optional[Path] = None,
) -> VoiceActionResult:
    action_id = row.get("action_id") or ""
    segment_id = row.get("segment_id", "unknown")
    started_at_ms = _now_ms()
    out_dir = out_dir or Path(".")
    output_file_payload = _collect_output_file_fields(row, out_dir)

    retry_policy = row.get("retry_policy", {})
    retry_limit = _coerce_int(retry_policy.get("retry_limit"), default=0)
    cooldown_ms = max(0, _coerce_int(retry_policy.get("cooldown_ms"), default=0))
    backoff_ms = max(0, _coerce_int(retry_policy.get("backoff_ms"), default=0))
    max_attempts = 1 + max(0, retry_limit)

    if dry_run or not executor:
        status = "queued" if dry_run else "skipped"
        reason = "dry_run_no_call" if dry_run else "no_executor_configured"
        finished_at_ms = _now_ms()
        return VoiceActionResult(
            segment_id=segment_id,
            status=status,
            action_id=action_id,
            attempts=0,
            plan=row,
            started_at_ms=started_at_ms,
            finished_at_ms=finished_at_ms,
            latency_ms=max(0, finished_at_ms - started_at_ms),
            reason=reason,
            executed=False,
            output_file=_coerce_str(output_file_payload.get("output_file")),
            output_file_exists=output_file_payload.get("output_file_exists"),
            output_file_size=output_file_payload.get("output_file_size"),
            output_file_sha256=output_file_payload.get("output_file_sha256"),
        )

    last_status = "failed"
    last_status_code: Optional[int] = None
    last_raw_status: Optional[str] = None
    last_verify_status: Optional[str] = None
    last_reason = "unknown_error"
    attempts = 0
    executed = False
    tool_args = row.get("tool_args", {})
    if not isinstance(tool_args, dict):
        tool_args = {}
    exec_cmd = shlex.split(executor or "")
    try:
        for attempt in range(1, max_attempts + 1):
            attempts = attempt
            if not exec_cmd:
                last_status_code = None
                last_raw_status = "error"
                last_verify_status = None
                last_reason = "executor_invalid_command"
                break
            try:
                proc = subprocess.run(
                    exec_cmd,
                    input=json.dumps(tool_args, ensure_ascii=False),
                    text=True,
                    capture_output=True,
                    timeout=60,
                    check=False,
                )
                executed = True
            except Exception as exc:
                last_status_code = None
                last_raw_status = "error"
                last_verify_status = None
                last_reason = f"executor_error: {exc}"
                if attempt < max_attempts:
                    time.sleep((cooldown_ms + attempt * backoff_ms) / 1000)
                    continue
                break

            payload = _parse_json_output(proc.stdout or "")
            freeform = _extract_freeform_receipt((proc.stdout or "") + "\n" + (proc.stderr or ""))
            if payload is None:
                payload = {}

            raw_status_val = payload.get("status") if isinstance(payload, dict) else None
            verify_status_val = payload.get("verify_status") if isinstance(payload, dict) else None
            payload_output_file = payload.get("output_file") if isinstance(payload, dict) else None
            message = payload.get("message") if isinstance(payload, dict) else None

            last_status_code = _coerce_int(payload.get("status_code"), default=None)
            if last_status_code is None:
                last_status_code = freeform.get("status_code")

            last_raw_status = _coerce_str(raw_status_val) or _coerce_str(freeform.get("raw_status"))
            last_verify_status = _coerce_str(verify_status_val) or _coerce_str(freeform.get("verify_status"))

            output_file_payload = _collect_output_file_fields(
                row,
                out_dir,
                output_file_override=_coerce_str(payload_output_file) or _coerce_str(freeform.get("output_file")),
            )

            combined_output = (proc.stdout or "").strip() or (proc.stderr or "").strip()
            if isinstance(message, str) and message.strip():
                last_reason = message.strip()
            elif freeform.get("reason"):
                last_reason = str(freeform["reason"]).strip()
            elif combined_output:
                last_reason = combined_output[:600]
            else:
                last_reason = "present_voice_executed"

            last_status = "ok" if _is_success_status(last_status_code, proc.returncode, last_raw_status, last_verify_status) else "failed"
            if last_status == "ok" or attempt >= max_attempts:
                break

            time.sleep((cooldown_ms + attempt * backoff_ms) / 1000)
    except Exception as exc:
        last_status = "failed"
        last_reason = f"runner_error: {exc}"

    finished_at_ms = _now_ms()
    return VoiceActionResult(
        segment_id=segment_id,
        status=last_status,
        action_id=action_id,
        attempts=attempts,
        plan=row,
        started_at_ms=started_at_ms,
        finished_at_ms=finished_at_ms,
        latency_ms=max(0, finished_at_ms - started_at_ms),
        status_code=last_status_code,
        raw_status=last_raw_status,
        verify_status=last_verify_status,
        executed=executed,
        reason=last_reason,
        output_file=output_file_payload.get("output_file"),
        output_file_exists=output_file_payload.get("output_file_exists"),
        output_file_size=output_file_payload.get("output_file_size"),
        output_file_sha256=output_file_payload.get("output_file_sha256"),
    )


def _emit_voice_actions(
    segments: list[Dict[str, Any]],
    cfg: Dict[str, Any],
    task_id: str,
    out_dir: Path,
    dry_run: bool = False,
) -> tuple[Path, Path, Dict[str, Any]]:
    plan_rows = pipeline.build_replay_plan(segments=segments, cfg=cfg, task_id=task_id)
    plan_rows = _normalize_plan_rows(plan_rows)

    calls_path = out_dir / "present_voice_calls.jsonl"
    results_path = out_dir / "present_voice_results.jsonl"

    calls = []
    results = []
    executor = os.environ.get("NOVEL_PRESENT_VOICE_EXECUTOR")
    for row in plan_rows:
        row["action_id"] = _action_id_for(row["segment_id"], int(row["order"]), task_id or "local")
        calls.append(row)
        result = _exec_present_voice(row, executor=executor, dry_run=dry_run, out_dir=out_dir)
        results.append(result.to_dict())

    with calls_path.open("w", encoding="utf-8") as f:
        for row in calls:
            f.write(json.dumps(row, ensure_ascii=False))
            f.write("\n")
    with results_path.open("w", encoding="utf-8") as f:
        for row in results:
            f.write(json.dumps(row, ensure_ascii=False))
            f.write("\n")

    status_counts: Dict[str, int] = {}
    verify_counts: Dict[str, int] = {}
    status_code_counts: Dict[str, int] = {}
    total_attempts = 0
    executed_count = 0
    latency_values = []
    output_exists_count = 0
    failed_segments = []
    ok_segments = []
    for r in results:
        status = r.get("status", "unknown")
        status_counts[status] = status_counts.get(status, 0) + 1
        verify = r.get("verify_status")
        if verify is not None:
            verify_counts[str(verify)] = verify_counts.get(str(verify), 0) + 1
        status_code = r.get("status_code")
        key = str(status_code) if status_code is not None else "null"
        status_code_counts[key] = status_code_counts.get(key, 0) + 1
        total_attempts += _coerce_int(r.get("attempts"), default=0) or 0
        if r.get("executed") is True:
            executed_count += 1
        latency = r.get("latency_ms")
        if isinstance(latency, (int, float)):
            latency_values.append(latency)
        if r.get("output_file_exists"):
            output_exists_count += 1
        if status == "failed":
            failed_segments.append(r["segment_id"])
        if status == "ok":
            ok_segments.append(r["segment_id"])

    latency_summary = {}
    if latency_values:
        latency_summary = {
            "min": min(latency_values),
            "max": max(latency_values),
            "avg": round(sum(latency_values) / len(latency_values), 3),
            "total": sum(latency_values),
        }

    summary = {
        "status_counts": status_counts,
        "verify_status_counts": verify_counts,
        "status_code_counts": status_code_counts,
        "segments": len(results),
        "attempts": total_attempts,
        "executed_count": executed_count,
        "ok_count": status_counts.get("ok", 0),
        "output_file_exists_count": output_exists_count,
        "latency_ms": latency_summary,
        "failed_segments": failed_segments,
        "ok_segments": ok_segments,
    }

    return calls_path, results_path, summary


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(
        description="AB runner for the novel TTS embodied prototype."
    )
    ap.add_argument("--input", help="小说文本文件（与 --input-text 二选一）")
    ap.add_argument("--input-text", help="直接传入小说文本")
    ap.add_argument("--task-json", help="AB 任务输入 JSON")
    ap.add_argument("--output-dir", required=True)

    ap.add_argument("--voice-male", default=pipeline.DEFAULT_CONFIG["voice_male"])
    ap.add_argument("--voice-female", default=pipeline.DEFAULT_CONFIG["voice_female"])
    ap.add_argument("--voice-narrator", default=pipeline.DEFAULT_CONFIG["voice_narrator"])
    ap.add_argument("--voice-unknown", default=pipeline.DEFAULT_CONFIG["voice_unknown"])
    ap.add_argument("--tts-backend", default=pipeline.DEFAULT_CONFIG["tts_backend"])
    ap.add_argument("--chapter", type=int, default=1)
    ap.add_argument("--segment-limit", type=int, default=pipeline.DEFAULT_CONFIG["segment_limit"])
    ap.add_argument("--annotation-json", help="模型/子代理输出的 segment-level 标注文件（speaker/emotion）")
    ap.add_argument("--emit-voice", action="store_true", help="在 AB action 层准备 per-segment present_voice 调用记录")
    ap.add_argument("--plan-priority", default=None)
    ap.add_argument("--plan-retry-limit", type=int, default=None)
    ap.add_argument("--plan-cooldown-ms", type=int, default=None)
    ap.add_argument("--plan-backoff-ms", type=int, default=None)
    ap.add_argument("--no-emit-plan", dest="emit_plan", action="store_false", default=True)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--result-json", dest="result_json", action="store_true", default=True)
    ap.add_argument("--no-result-json", dest="result_json", action="store_false")
    return ap.parse_args()


def main() -> None:
    args = parse_args()

    task_payload: Dict[str, Any] = {}
    if args.task_json:
        task_payload = load_json(Path(args.task_json))

    task_input = _read_task_input(task_payload, args)
    if task_input["text"] is None:
        raise SystemExit("未提供可用输入：请传 --input 或 --input-text，或在 --task-json 的 input 中提供 path/text。")

    cfg = _build_config(args, task_payload.get("config", {}) if isinstance(task_payload, dict) else {})
    if args.plan_priority is not None:
        cfg["plan_priority"] = args.plan_priority
    if args.plan_retry_limit is not None:
        cfg["plan_retry_limit"] = args.plan_retry_limit
    if args.plan_cooldown_ms is not None:
        cfg["plan_cooldown_ms"] = args.plan_cooldown_ms
    if args.plan_backoff_ms is not None:
        cfg["plan_backoff_ms"] = args.plan_backoff_ms
    annotations = _coalesce_annotations(args, task_input["annotations"])
    if isinstance(task_input["chapter"], int):
        chapter = task_input["chapter"]
    else:
        chapter = args.chapter

    output_dir = Path(args.output_dir)
    emit_plan = bool(args.emit_plan or args.emit_voice)
    segments, manifest, result, _ = pipeline.run_pipeline(
        text=task_input["text"],
        output_dir=output_dir,
        config=cfg,
        chapter=chapter,
        source_path=task_input["source_path"],
        task_id=task_input["task_id"],
        annotation_payload=annotations,
        emit_plan=emit_plan,
        dry_run=args.dry_run,
        version="novel_tts_embodied:v1.1",
    )

    needs_review_file = _write_needs_review_file(segments, output_dir)
    result["needs_review_file"] = str(needs_review_file) if needs_review_file else None

    if args.emit_voice:
        calls_file, results_file, voice_summary = _emit_voice_actions(
            segments=segments,
            cfg=cfg,
            task_id=task_input["task_id"] or "",
            out_dir=output_dir,
            dry_run=args.dry_run,
        )
        result["present_voice_calls"] = str(calls_file)
        result["present_voice_results"] = str(results_file)
        result["present_voice_ok_count"] = voice_summary["ok_count"]
        result["present_voice_total"] = len(segments)
        result["present_voice_summary"] = voice_summary
        if args.dry_run:
            result["present_voice_status"] = "queued"
        elif voice_summary["ok_count"] == len(segments):
            result["present_voice_status"] = "ok"
        elif voice_summary["ok_count"] > 0:
            result["present_voice_status"] = "partial"
        else:
            if voice_summary["status_counts"].get("failed", 0) > 0:
                result["present_voice_status"] = "failed"
            else:
                result["present_voice_status"] = "pending"
        result["present_voice_executor"] = os.environ.get("NOVEL_PRESENT_VOICE_EXECUTOR", "unset")

    if not args.dry_run:
        (output_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    if args.result_json:
        result_file = output_dir / "result.json"
        payload = dict(result)
        payload.update({
            "mode": "ab_runner_v1",
            "ab_task_id": task_input["task_id"],
            "config": cfg,
            "source": {
                "path": str(task_input["source_path"]) if task_input["source_path"] else None,
                "had_inline_input": task_input["source_path"] is None,
            },
        })
        result_file.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"result_json={result_file}")
    print(json.dumps({"status": result["status"], "manifest": result["manifest_path"], "segments": result["segments_path"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
