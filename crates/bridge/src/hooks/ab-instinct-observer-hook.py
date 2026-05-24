#!/usr/bin/env python3
"""ab-instinct-observer-hook — delta① Phase-0b density-audit sidecar.

Pure append-only observability. Captures the Claude Code session stream so we
can LATER count mineable signals (user corrections + tool error-resolutions)
per session, to decide whether an auto-miner is worth building
(docs/design/ECC_INSTINCT_MINING_PROBE_2026_05_24.md).

Contract:
  - ZERO DB writes. Appends one JSONL line to a wipeable sidecar log.
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


def _brief(obj, n=240):
    try:
        s = obj if isinstance(obj, str) else json.dumps(obj, ensure_ascii=False)
    except Exception:
        s = str(obj)
    s = " ".join(s.split())
    return s[:n]


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
        # best-effort error flag — analysis pass refines; we only need a hint
        err = False
        if isinstance(resp, dict):
            if resp.get("is_error") or resp.get("error") or resp.get("interrupted"):
                err = True
            stderr = resp.get("stderr")
            if isinstance(stderr, str) and stderr.strip():
                err = True
        rec["tool"] = data.get("tool_name", "?")
        rec["err"] = err
        rec["in"] = _brief(data.get("tool_input", ""))
        rec["out"] = _brief(resp, 200)
    elif ev == "UserPromptSubmit":
        rec["prompt"] = _brief(data.get("prompt", ""), 600)
    else:
        rec["raw"] = _brief(data, 200)

    os.makedirs(LOG_DIR, exist_ok=True)
    try:
        if os.path.getsize(LOG) >= MAX_BYTES:
            return
    except OSError:
        pass
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass  # never disrupt the session
    sys.exit(0)
