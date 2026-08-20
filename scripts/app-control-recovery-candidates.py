#!/usr/bin/env python3
"""Discover bounded durable media recovery candidates without observing media."""
from __future__ import annotations

import argparse
import errno
import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import stat
import sys
import time
from typing import Any

SCHEMA = "agent_bridge.app_control.recovery_candidates.v0"
OPAQUE_ID_RE = re.compile(r"ab-episode-[0-9a-f]{32}")
FILE_RE = re.compile(r"[0-9a-f]{64}\.json")
MAX_RECORDS = 64


def _load_backend():
    path = Path(__file__).with_name("app_control.py")
    spec = importlib.util.spec_from_file_location("app_control_recovery_backend", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("backend_import_unavailable")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _secure_file(fd: int, mode: int) -> bool:
    metadata = os.fstat(fd)
    return stat.S_ISREG(metadata.st_mode) and metadata.st_uid == os.getuid() and stat.S_IMODE(metadata.st_mode) == mode


def discover(directory: Path, *, now: float | None = None, minimum_recovery_secs: float = 5.0) -> dict[str, Any]:
    now = time.time() if now is None else now
    result: dict[str, Any] = {
        "schema": SCHEMA, "status": "verified", "verdict": "verified", "recover": "proceed",
        "read_only": True, "observed_at_unix_seconds": now,
        "journal_path_sha256": hashlib.sha256(str(directory).encode()).hexdigest(),
        "candidate_count": 0, "candidates": [], "skipped_count": 0,
        "blocked_count": 0, "blocked_operation_id_sha256": [],
        "minimum_recovery_secs": minimum_recovery_secs,
        "scan_complete": True, "media_observed": False, "action_invoked": False,
        "automatic_recovery_authorized": False,
    }
    try:
        metadata = os.lstat(directory)
        if not stat.S_ISDIR(metadata.st_mode) or metadata.st_uid != os.getuid() or stat.S_IMODE(metadata.st_mode) != 0o700:
            raise OSError("journal_must_be_owner_only_0700_directory")
        names = sorted(name for name in os.listdir(directory) if FILE_RE.fullmatch(name))
        if len(names) > MAX_RECORDS:
            raise OSError("journal_record_limit_exceeded")
        backend = _load_backend()
        for name in names:
            record_path = directory / name
            lock_path = directory / f"{name[:-5]}.lock"
            lock_fd = record_fd = -1
            locked = False
            try:
                flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
                lock_fd = os.open(lock_path, flags)
                if not _secure_file(lock_fd, 0o600): raise OSError("unsafe_lock")
                try:
                    fcntl.flock(lock_fd, fcntl.LOCK_SH | fcntl.LOCK_NB); locked = True
                except OSError as exc:
                    if exc.errno in (errno.EACCES, errno.EAGAIN):
                        result["skipped_count"] += 1; continue
                    raise
                record_fd = os.open(record_path, flags)
                if not _secure_file(record_fd, 0o600): raise OSError("unsafe_record")
                raw = os.read(record_fd, 256 * 1024 + 1)
                if len(raw) > 256 * 1024: raise OSError("record_too_large")
                record = json.loads(raw)
                operation_id = record.get("operation_id") if isinstance(record, dict) else None
                expires_at = record.get("expires_at") if isinstance(record, dict) else None
                if not (isinstance(operation_id, str) and OPAQUE_ID_RE.fullmatch(operation_id)):
                    result["skipped_count"] += 1; continue
                if hashlib.sha256(operation_id.encode("ascii")).hexdigest() != name[:-5]:
                    raise OSError("record_filename_identity_mismatch")
                if not backend.dispatch_started_record_valid(record):
                    result["skipped_count"] += 1; continue
                if type(expires_at) not in (int, float) or isinstance(expires_at, bool) or float(expires_at) <= now:
                    result["skipped_count"] += 1; continue
                request = record.get("request")
                ttl = request.get("operation_ttl_secs") if isinstance(request, dict) else None
                selector = request.get("player_selector") if isinstance(request, dict) else None
                canonical_request = backend.operation_request("next", selector, ttl) if type(ttl) is int else None
                canonical_digest = backend.operation_request_digest("next", selector, ttl) if type(ttl) is int else None
                if (
                    not isinstance(request, dict)
                    or request != canonical_request
                    or request.get("schema") != backend.SCHEMA
                    or request.get("action") != "next"
                    or not isinstance(selector, str) or not selector
                    or type(ttl) is not int
                    or not (backend.MIN_OPERATION_TTL_SECS <= ttl <= backend.MAX_OPERATION_TTL_SECS)
                    or record.get("request_digest") != canonical_digest
                ):
                    result["skipped_count"] += 1; continue
                remaining_secs = max(0.0, float(expires_at) - now)
                if remaining_secs < minimum_recovery_secs:
                    result["blocked_count"] += 1
                    result["blocked_operation_id_sha256"].append(hashlib.sha256(operation_id.encode("ascii")).hexdigest())
                    continue
                result["candidates"].append({
                    "operation_id": operation_id,
                    "request": canonical_request,
                    "request_digest": canonical_digest,
                    "expires_at": float(expires_at),
                    "remaining_secs": remaining_secs,
                    "phase": "dispatch_started", "dispatch_count": 1,
                    "record_sha256": hashlib.sha256(raw).hexdigest(),
                    "discovery_only": True, "revalidation_required": True,
                    "recommended_next": "explicitly_review_then_call_same_canonical_request",
                    "automatic_execution_allowed": False,
                })
            except (OSError, ValueError, json.JSONDecodeError):
                result["status"] = "error"; result["verdict"] = "error"; result["recover"] = "replan"
                result["scan_complete"] = False; result["candidates"] = []; result["candidate_count"] = 0
                result["error"] = {"code": "journal_scan_incomplete"}
                return result
            finally:
                if locked:
                    fcntl.flock(lock_fd, fcntl.LOCK_UN)
                if record_fd >= 0: os.close(record_fd)
                if lock_fd >= 0: os.close(lock_fd)
        result["candidate_count"] = len(result["candidates"])
        if result["candidate_count"]:
            result["admission"] = "eligible_candidate_present"
            result["recover"] = "proceed"
        elif result["blocked_count"]:
            result["admission"] = "blocked_insufficient_recovery_window"
            result["recover"] = "replan"
        else:
            result["admission"] = "no_recovery_candidate"
            result["recover"] = "replan"
        return result
    except OSError:
        result.update(status="error", verdict="error", recover="replan", scan_complete=False)
        result["error"] = {"code": "journal_unavailable"}
        return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--journal", required=True)
    parser.add_argument("--minimum-recovery-secs", type=float, default=5.0)
    args = parser.parse_args()
    directory = Path(args.journal)
    if not directory.is_absolute():
        print(json.dumps({"schema": SCHEMA, "status": "error", "verdict": "error", "recover": "replan", "read_only": True, "error": {"code": "journal_path_not_absolute"}}, separators=(",", ":")))
        return 3
    if not (0.0 <= args.minimum_recovery_secs <= 86400.0):
        print(json.dumps({"schema": SCHEMA, "status": "error", "verdict": "error", "recover": "replan", "read_only": True, "error": {"code": "invalid_minimum_recovery_secs"}}, separators=(",", ":")))
        return 3
    result = discover(directory, minimum_recovery_secs=args.minimum_recovery_secs)
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))
    return 0 if result["verdict"] == "verified" else 3


if __name__ == "__main__": raise SystemExit(main())
