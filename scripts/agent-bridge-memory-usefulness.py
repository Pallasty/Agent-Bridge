#!/usr/bin/env python3
"""Minimal local ledger for real-task memory usefulness dogfooding."""

from __future__ import annotations

import argparse
import fcntl
import json
import os
import re
import stat
import sys
import time
import uuid
from pathlib import Path
from typing import Any

SCHEMA = "agent_bridge.memory_usefulness_task.v1"
REPORT_SCHEMA = "agent_bridge.memory_usefulness_report.v1"
OUTCOMES = ("used", "no_recall", "missing", "stale", "harmful")
UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$"
)
TASK_KINDS = (
    "repo_truth",
    "implementation",
    "debugging",
    "review",
    "deployment",
    "research_triage",
    "documentation",
    "other",
)
REQUIRED_KEYS = {
    "schema",
    "task_id",
    "task_kind",
    "observed_at",
    "recall_outcome",
    "repeated_explanations",
    "real_task_attested",
}
OPTIONAL_KEYS = {"recovery_seconds", "retrieval_payload_bytes"}
MAX_LEDGER_BYTES = 16_000_000


class LedgerError(Exception):
    """Structured ledger failure without sensitive detail."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def default_log_path() -> Path:
    explicit = os.environ.get("AGENT_BRIDGE_STATE_DIR")
    if explicit:
        root = Path(explicit).expanduser()
    elif sys.platform == "darwin":
        root = Path.home() / "Library/Application Support/agent-bridge"
    else:
        root = (
            Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local/state"))
            / "agent-bridge"
        )
    return root / "dogfood" / "memory-usefulness-r1.jsonl"


def _validate_int(value: Any, *, low: int, high: int, code: str) -> int:
    if type(value) is not int or not low <= value <= high:
        raise LedgerError(code)
    return value


def validate_row(row: Any) -> dict[str, Any]:
    if type(row) is not dict:
        raise LedgerError("INVALID_ROW_TYPE")
    keys = set(row)
    if not REQUIRED_KEYS.issubset(keys) or not keys.issubset(
        REQUIRED_KEYS | OPTIONAL_KEYS
    ):
        raise LedgerError("INVALID_ROW_KEYS")
    if row.get("schema") != SCHEMA:
        raise LedgerError("INVALID_SCHEMA")
    task_id = row.get("task_id")
    if type(task_id) is not str or UUID_RE.fullmatch(task_id) is None:
        raise LedgerError("INVALID_TASK_ID")
    if row.get("task_kind") not in TASK_KINDS:
        raise LedgerError("INVALID_TASK_KIND")
    _validate_int(
        row.get("observed_at"), low=1, high=2**63 - 1, code="INVALID_OBSERVED_AT"
    )
    if row.get("recall_outcome") not in OUTCOMES:
        raise LedgerError("INVALID_RECALL_OUTCOME")
    if row.get("real_task_attested") is not True:
        raise LedgerError("REAL_TASK_ATTESTATION_REQUIRED")
    _validate_int(
        row.get("repeated_explanations"),
        low=0,
        high=20,
        code="INVALID_REPEATED_EXPLANATIONS",
    )
    if "recovery_seconds" in row:
        _validate_int(
            row["recovery_seconds"], low=0, high=86_400, code="INVALID_RECOVERY_SECONDS"
        )
    if "retrieval_payload_bytes" in row:
        _validate_int(
            row["retrieval_payload_bytes"],
            low=0,
            high=10_000_000,
            code="INVALID_RETRIEVAL_PAYLOAD_BYTES",
        )
    return row


def _flags(write: bool) -> int:
    if not hasattr(os, "O_NOFOLLOW"):
        raise LedgerError("NOFOLLOW_UNAVAILABLE")
    flags = os.O_RDWR | os.O_CREAT | os.O_APPEND if write else os.O_RDONLY
    flags |= os.O_NOFOLLOW
    return flags


def _verify_file(fd: int) -> None:
    info = os.fstat(fd)
    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
        raise LedgerError("UNSAFE_LEDGER_FILE")
    if stat.S_IMODE(info.st_mode) != 0o600:
        raise LedgerError("INSECURE_LEDGER_PERMISSIONS")
    if info.st_size > MAX_LEDGER_BYTES:
        raise LedgerError("LEDGER_TOO_LARGE")


def _write_all(fd: int, payload: bytes) -> None:
    offset = 0
    while offset < len(payload):
        written = os.write(fd, payload[offset:])
        if written <= 0:
            raise LedgerError("LEDGER_WRITE_FAILED")
        offset += written


def _read_exact(fd: int, size: int) -> bytes:
    chunks: list[bytes] = []
    remaining = size
    while remaining:
        chunk = os.read(fd, remaining)
        if not chunk:
            raise LedgerError("LEDGER_SHORT_READ")
        chunks.append(chunk)
        remaining -= len(chunk)
    return b"".join(chunks)


def _decode_rows(raw: bytes) -> list[dict[str, Any]]:
    if not raw:
        return []
    if not raw.endswith(b"\n"):
        raise LedgerError("UNTERMINATED_LEDGER_ROW")
    rows: list[dict[str, Any]] = []
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise LedgerError("INVALID_LEDGER_ENCODING") from exc
    for line in text.splitlines():
        if not line:
            raise LedgerError("INVALID_EMPTY_ROW")
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise LedgerError("INVALID_LEDGER_JSON") from exc
        rows.append(validate_row(row))
    if len({row["task_id"] for row in rows}) != len(rows):
        raise LedgerError("DUPLICATE_TASK_ID_IN_LEDGER")
    return rows


def _prepare_parent(path: Path) -> None:
    try:
        path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        if path.parent.is_symlink():
            raise LedgerError("UNSAFE_LEDGER_DIRECTORY")
        if stat.S_IMODE(path.parent.stat().st_mode) != 0o700:
            raise LedgerError("INSECURE_LEDGER_DIRECTORY_PERMISSIONS")
    except LedgerError:
        raise
    except OSError as exc:
        raise LedgerError("LEDGER_DIRECTORY_FAILED") from exc


def record_task(path: Path, row: dict[str, Any]) -> dict[str, Any]:
    validate_row(row)
    _prepare_parent(path)
    try:
        fd = os.open(path, _flags(write=True), 0o600)
    except OSError as exc:
        raise LedgerError("LEDGER_OPEN_FAILED") from exc
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX)
            _verify_file(fd)
            original_size = os.fstat(fd).st_size
            os.lseek(fd, 0, os.SEEK_SET)
            rows = _decode_rows(_read_exact(fd, original_size))
        except LedgerError:
            raise
        except OSError as exc:
            raise LedgerError("LEDGER_READ_FAILED") from exc
        if any(existing["task_id"] == row["task_id"] for existing in rows):
            raise LedgerError("TASK_ID_ALREADY_RECORDED")
        payload = (
            json.dumps(row, sort_keys=True, separators=(",", ":")).encode() + b"\n"
        )
        if original_size + len(payload) > MAX_LEDGER_BYTES:
            raise LedgerError("LEDGER_TOO_LARGE")
        try:
            _write_all(fd, payload)
            os.fsync(fd)
        except (LedgerError, OSError) as exc:
            try:
                os.ftruncate(fd, original_size)
                os.fsync(fd)
            except OSError as rollback_exc:
                raise LedgerError("LEDGER_WRITE_UNCERTAIN") from rollback_exc
            raise LedgerError("LEDGER_WRITE_FAILED") from exc
        return {
            "status": "RECORDED",
            "task_id": row["task_id"],
            "task_count": len(rows) + 1,
        }
    finally:
        try:
            os.close(fd)
        except OSError:
            pass


def read_rows(path: Path) -> list[dict[str, Any]]:
    if not os.path.lexists(path):
        return []
    try:
        fd = os.open(path, _flags(write=False))
    except OSError as exc:
        raise LedgerError("LEDGER_OPEN_FAILED") from exc
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_SH)
            _verify_file(fd)
            size = os.fstat(fd).st_size
            return _decode_rows(_read_exact(fd, size))
        except LedgerError:
            raise
        except OSError as exc:
            raise LedgerError("LEDGER_READ_FAILED") from exc
    finally:
        try:
            os.close(fd)
        except OSError:
            pass


def _average(values: list[int]) -> float | None:
    return round(sum(values) / len(values), 2) if values else None


def build_report(rows: list[dict[str, Any]], target: int) -> dict[str, Any]:
    if not 20 <= target <= 10_000:
        raise LedgerError("INVALID_TARGET")
    for row in rows:
        validate_row(row)
    if len({row["task_id"] for row in rows}) != len(rows):
        raise LedgerError("DUPLICATE_TASK_ID_IN_LEDGER")
    counts = {
        outcome: sum(row["recall_outcome"] == outcome for row in rows)
        for outcome in OUTCOMES
    }
    recovery = [row["recovery_seconds"] for row in rows if "recovery_seconds" in row]
    payloads = [
        row["retrieval_payload_bytes"]
        for row in rows
        if "retrieval_payload_bytes" in row
    ]
    repeated = [row["repeated_explanations"] for row in rows]
    total = len(rows)
    negative = counts["stale"] + counts["harmful"]
    return {
        "schema": REPORT_SCHEMA,
        "verdict": (
            "READY_FOR_PRODUCT_DECISION" if total >= target else "COLLECTING_REAL_TASKS"
        ),
        "target_tasks": target,
        "observed_tasks": total,
        "remaining_tasks": max(0, target - total),
        "outcomes": counts,
        "used_task_rate": round(counts["used"] / total, 3) if total else None,
        "negative_recall_count": negative,
        "tasks_with_repeated_explanation": sum(value > 0 for value in repeated),
        "average_repeated_explanations": _average(repeated),
        "average_recovery_seconds": _average(recovery),
        "average_retrieval_payload_bytes": _average(payloads),
        "metric_coverage": {
            "recovery_seconds_tasks": len(recovery),
            "retrieval_payload_bytes_tasks": len(payloads),
        },
        "privacy": {
            "task_text_stored": False,
            "prompt_or_transcript_stored": False,
            "memory_content_or_key_stored": False,
            "free_text_fields_present": False,
        },
        "nonclaims": [
            "task-level observations do not prove memory caused the outcome",
            "real-task provenance is operator-attested and not technically verified",
            "missing optional metrics remain missing and are never imputed",
            "the report does not change retrieval, ranking, memory, or runtime behavior",
        ],
    }


def _emit(value: dict[str, Any]) -> None:
    print(json.dumps(value, sort_keys=True, separators=(",", ":")))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--log", type=Path, default=default_log_path())
    subparsers = parser.add_subparsers(dest="command", required=True)
    record = subparsers.add_parser("record")
    record.add_argument("--task-id", default=None)
    record.add_argument("--task-kind", required=True, choices=TASK_KINDS)
    record.add_argument("--attest-real-task", required=True, action="store_true")
    record.add_argument("--recall-outcome", required=True, choices=OUTCOMES)
    record.add_argument("--repeated-explanations", required=True, type=int)
    record.add_argument("--recovery-seconds", type=int)
    record.add_argument("--retrieval-payload-bytes", type=int)
    report = subparsers.add_parser("report")
    report.add_argument("--target", type=int, default=20)
    args = parser.parse_args()
    try:
        if args.command == "record":
            row: dict[str, Any] = {
                "schema": SCHEMA,
                "task_id": args.task_id or str(uuid.uuid4()),
                "task_kind": args.task_kind,
                "observed_at": int(time.time()),
                "recall_outcome": args.recall_outcome,
                "repeated_explanations": args.repeated_explanations,
                "real_task_attested": args.attest_real_task,
            }
            if args.recovery_seconds is not None:
                row["recovery_seconds"] = args.recovery_seconds
            if args.retrieval_payload_bytes is not None:
                row["retrieval_payload_bytes"] = args.retrieval_payload_bytes
            _emit(record_task(args.log, row))
            return 0
        result = build_report(read_rows(args.log), args.target)
        _emit(result)
        return 0 if result["verdict"] == "READY_FOR_PRODUCT_DECISION" else 4
    except LedgerError as exc:
        _emit(
            {
                "schema": REPORT_SCHEMA,
                "verdict": "HOLD_INVALID_LEDGER",
                "error_code": exc.code,
            }
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
