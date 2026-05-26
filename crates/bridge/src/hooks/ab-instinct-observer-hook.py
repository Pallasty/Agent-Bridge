#!/usr/bin/env python3
"""ab-instinct-observer-hook — delta① Phase-0b density-audit sidecar.

Pure append-only observability. Captures the Claude Code session stream so we
can LATER count mineable signals (user corrections + tool error-resolutions)
per session, to decide whether an auto-miner is worth building
(docs/design/ECC_INSTINCT_MINING_PROBE_2026_05_24.md).

Contract:
  - ZERO DB writes. Appends one JSONL line to a wipeable sidecar log.
  - Sidecar directory/file are private by default (0700 dir, 0600 JSONL).
  - NEVER blocks or fails the session: any error → silent exit 0, no output.
  - Registered on PostToolUse (tool outcomes / errors) + UserPromptSubmit
    (prompt text, for correction detection).

Wipe anytime:  rm -f ~/.cache/agent-bridge/instinct-probe/observations.jsonl
Disable:       set AB_INSTINCT_OBSERVER=0  (hook becomes a no-op)
"""
import os
import sys
import json
import time

LOG_DIR = os.path.expanduser("~/.cache/agent-bridge/instinct-probe")
LOG = os.path.join(LOG_DIR, "observations.jsonl")
MAX_BYTES = 8 * 1024 * 1024  # self-cap; stop appending past 8 MiB (probe, not prod)
DIR_MODE = 0o700
FILE_MODE = 0o600


def _brief(obj, n=240):
    try:
        s = obj if isinstance(obj, str) else json.dumps(obj, ensure_ascii=False)
    except Exception:
        s = str(obj)
    s = " ".join(s.split())
    return s[:n]


def _clean_error(resp):
    """Return (is_error, source) without treating stderr as failure.

    Many successful tools write progress or warnings to stderr (`git`, `cargo`,
    `maturin`, test runners). Using stderr as an error signal polluted the
    Phase-0b density audit, so only explicit error/status fields count here.
    """
    if not isinstance(resp, dict):
        return False, None
    for key in ("is_error", "error", "interrupted"):
        if resp.get(key):
            return True, key
    for key in ("exit_code", "exitCode", "returncode", "return_code"):
        value = resp.get(key)
        if isinstance(value, bool):
            continue
        if isinstance(value, int) and value != 0:
            return True, key
        if isinstance(value, str):
            try:
                if int(value.strip()) != 0:
                    return True, key
            except ValueError:
                pass
    status = resp.get("status")
    if isinstance(status, str) and status.lower() in {"error", "failed", "failure"}:
        return True, "status"
    return False, None


def _ensure_private_sidecar():
    os.makedirs(LOG_DIR, mode=DIR_MODE, exist_ok=True)
    try:
        os.chmod(LOG_DIR, DIR_MODE)
    except OSError:
        pass


def _append_private_jsonl(record):
    flags = os.O_WRONLY | os.O_APPEND | os.O_CREAT
    fd = os.open(LOG, flags, FILE_MODE)
    try:
        try:
            os.chmod(LOG, FILE_MODE)
        except OSError:
            pass
        with os.fdopen(fd, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception:
        try:
            os.close(fd)
        except OSError:
            pass
        raise


def main():
    if os.environ.get("AB_INSTINCT_OBSERVER", "1") == "0":
        return
    raw = sys.stdin.read()
    if not raw.strip():
        return
    data = json.loads(raw)
    ev = data.get("hook_event_name", "")
    rec = {
        "ts": time.time(),
        "sid": data.get("session_id", "?"),
        "cwd": data.get("cwd", ""),
        "ev": ev,
    }
    if ev == "PostToolUse":
        resp = data.get("tool_response", data.get("tool_result"))
        err, err_source = _clean_error(resp)
        rec["tool"] = data.get("tool_name", "?")
        rec["err"] = err
        rec["err_source"] = err_source
        if isinstance(resp, dict):
            stderr = resp.get("stderr")
            rec["stderr_nonempty"] = isinstance(stderr, str) and bool(stderr.strip())
        rec["in"] = _brief(data.get("tool_input", ""))
        rec["out"] = _brief(resp, 200)
    elif ev == "UserPromptSubmit":
        rec["prompt"] = _brief(data.get("prompt", ""), 600)
    else:
        rec["raw"] = _brief(data, 200)

    _ensure_private_sidecar()
    try:
        if os.path.getsize(LOG) >= MAX_BYTES:
            return
    except OSError:
        pass
    _append_private_jsonl(rec)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass  # never disrupt the session
    sys.exit(0)
