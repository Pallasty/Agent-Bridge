#!/usr/bin/env python3
"""Session-local presentation dedupe for bootstrap media-recovery hints.

This filter never reads the operation journal and never invokes an action.  It
only remembers which read-only hint a frontend session has already seen.
"""

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import sys
import tempfile
import time

SCHEMA = "agent_bridge.app_control.recovery_hint_presentation.v0"
HEADER_PREFIXES = (
    "=== Media recovery candidates (",
    "=== Durable Media Recovery Candidates (",
)
END_PREFIX = "Next: explicitly review one candidate"
OP_RE = re.compile(r"operation_id=(ab-episode-[0-9a-f]{32})\b")
SHA_RE = re.compile(r"record_sha256=([0-9a-f]{64})\b")
REMAINING_RE = re.compile(r"remaining≈([0-9]+)s\b")
MAX_STATE_FILES = 256
MAX_STATE_AGE_SECS = 7 * 24 * 60 * 60


def _extract_block(text):
    lines = text.splitlines(keepends=True)
    start = next((i for i, line in enumerate(lines) if line.startswith(HEADER_PREFIXES)), None)
    if start is None:
        return None
    end = next((i + 1 for i in range(start, len(lines)) if lines[i].startswith(END_PREFIX)), None)
    if end is None:
        return None
    while end < len(lines) and not lines[end].strip():
        end += 1
    block = "".join(lines[start:end])
    operations = OP_RE.findall(block)
    records = SHA_RE.findall(block)
    remaining = [int(value) for value in REMAINING_RE.findall(block)]
    if not operations or len(operations) != len(records) or len(operations) != len(remaining):
        return None
    stable = sorted(zip(operations, records))
    fingerprint = hashlib.sha256(
        json.dumps(stable, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    least_remaining = min(remaining)
    urgency = "urgent" if least_remaining <= 60 else "soon" if least_remaining <= 300 else "normal"
    return {
        "start": start,
        "end": end,
        "lines": lines,
        "fingerprint": fingerprint,
        "urgency": urgency,
        "candidate_count": len(operations),
    }


def _secure_state_dir(path):
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    info = path.lstat()
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid():
        raise OSError("unsafe recovery-hint state directory")
    if info.st_mode & 0o077:
        path.chmod(0o700)
    return path


def _state_path(state_dir, session_id):
    key = hashlib.sha256(session_id.encode("utf-8")).hexdigest()
    return state_dir / f"{key}.json"


def _read_state(path):
    try:
        info = path.lstat()
        if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077:
            return None
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if value.get("schema") == SCHEMA else None
    except (OSError, ValueError, TypeError, AttributeError):
        return None


def _write_state(path, value):
    payload = json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n"
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        directory_fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    finally:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass


def _prune(state_dir, now):
    files = []
    for path in state_dir.glob("*.json"):
        try:
            info = path.lstat()
            if stat.S_ISREG(info.st_mode) and info.st_uid == os.getuid():
                files.append((info.st_mtime, path))
        except OSError:
            continue
    files.sort(reverse=True)
    for modified, path in files[MAX_STATE_FILES:]:
        try:
            path.unlink()
        except OSError:
            pass
    for modified, path in files[:MAX_STATE_FILES]:
        if now - modified > MAX_STATE_AGE_SECS:
            try:
                path.unlink()
            except OSError:
                pass


def filter_hint(text, state_dir, session_id, now=None):
    """Return filtered text; on state failure, preserve the original hint."""
    if not session_id or len(session_id) > 512:
        return text
    now = time.time() if now is None else float(now)
    try:
        state_dir = _secure_state_dir(Path(state_dir))
        state_path = _state_path(state_dir, session_id)
        previous = _read_state(state_path)
        block = _extract_block(text)
        if block is None:
            if previous and previous.get("active") is True:
                notice = (
                    "\n=== Media recovery candidate update ===\n"
                    "Previously surfaced candidate(s) are not present in this bootstrap output. "
                    "No action was executed; automatic recovery remains forbidden.\n"
                )
                _write_state(state_path, {
                    "schema": SCHEMA, "active": False, "updated_at": now,
                })
                _prune(state_dir, now)
                return text.rstrip() + "\n" + notice
            return text
        current = {
            "schema": SCHEMA,
            "active": True,
            "fingerprint": block["fingerprint"],
            "urgency": block["urgency"],
            "candidate_count": block["candidate_count"],
            "updated_at": now,
        }
        unchanged = previous and previous.get("active") is True \
            and previous.get("fingerprint") == current["fingerprint"] \
            and previous.get("urgency") == current["urgency"]
        if unchanged:
            kept = block["lines"][:block["start"]] + block["lines"][block["end"]:]
            return "".join(kept).rstrip() + "\n"
        _write_state(state_path, current)
        _prune(state_dir, now)
        return text
    except OSError:
        return text


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--state-dir", required=True)
    parser.add_argument("--session-id", required=True)
    parser.add_argument("--now", type=float)
    args = parser.parse_args()
    text = sys.stdin.read()
    sys.stdout.write(filter_hint(text, args.state_dir, args.session_id, args.now))


if __name__ == "__main__":
    main()
