#!/usr/bin/env python3
"""PROBE agent-reader release for ``kind=steer`` (B / cross-process control plane).

Reads the human decisions the dock RECORDS (dock_decisions/<token>.json) and, for
each APPROVE that still maps to a live pending steer token:

  1. load_and_consume_pending(token, expect_kind="steer")  — single-use, marked
     consumed BEFORE injection, so a failed inject can never be replayed (by design);
  2. inject the payload text into the target tmux session via the SAME primitive
     agent_steer uses — ``tmux send-keys -t <sess> -l -- <text>`` (+ Enter if submit),
     honoring AB_TMUX_BIN (rmux drop-in).

This is the AGENT-READER release: an agent runs it on demand. It adds NO standing
executor and NO new trust surface — the dock only RECORDS; the canonical single-use
consume still gates execution. Reject is left to the gated phase (reject_pending).
``--dry-run`` prints what would happen without consuming or injecting.
"""
import argparse
import glob
import json
import os
import pathlib
import re
import subprocess
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))  # scripts/
from desktop_confirm_store import load_and_consume_pending, peek_kind  # noqa: E402

HOME = pathlib.Path.home()
DECISIONS_DIR = HOME / ".cache/agent-bridge/dock_decisions"
HEX32 = re.compile(r"^[0-9a-f]{32}$")
TMUX = os.environ.get("AB_TMUX_BIN", "tmux")


def inject(session: str, text: str, submit: bool) -> tuple[bool, str]:
    """The exact primitive remote_steer.rs builds: send literal text to a session,
    then optionally Enter. Returns (ok, note)."""
    if not session:
        return False, "no target session"
    try:
        r1 = subprocess.run([TMUX, "send-keys", "-t", session, "-l", "--", text],
                            capture_output=True, text=True, timeout=8)
    except (OSError, subprocess.SubprocessError) as exc:
        return False, f"tmux not runnable: {exc}"
    if r1.returncode != 0:
        return False, (r1.stderr or "send-keys -l failed").strip()
    if submit:
        r2 = subprocess.run([TMUX, "send-keys", "-t", session, "Enter"],
                            capture_output=True, text=True, timeout=8)
        if r2.returncode != 0:
            return False, (r2.stderr or "send-keys Enter failed").strip()
    return True, "injected"


def main() -> None:
    ap = argparse.ArgumentParser(description="release human-approved kind=steer pendings (probe)")
    ap.add_argument("--dry-run", action="store_true", help="show what would run; consume nothing")
    ap.add_argument("--token", help="only act on this token")
    a = ap.parse_args()

    if not DECISIONS_DIR.exists():
        print(json.dumps({"ok": True, "acted": 0, "results": [], "note": "no decisions dir"}))
        return

    results = []
    for f in sorted(glob.glob(str(DECISIONS_DIR / "*.json"))):
        try:
            dec = json.loads(pathlib.Path(f).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        token = str(dec.get("token") or "")
        if not HEX32.match(token):
            continue
        if a.token and token != a.token:
            continue
        if dec.get("decision") != "approve":
            continue
        # this probe only releases steer; any other kind stays the gated desktop_confirm's job
        if peek_kind(token) != "steer":
            continue
        if a.dry_run:
            results.append({"token": token, "would": "consume+inject", "dry_run": True})
            continue
        rec, why = load_and_consume_pending(token, expect_kind="steer")
        if rec is None:
            results.append({"token": token, "ok": False, "reason": why})  # e.g. already consumed → no replay
            continue
        pl = rec.get("payload") or {}
        ok, note = inject(pl.get("session", ""), pl.get("text", ""), bool(pl.get("submit")))
        results.append({"token": token, "ok": ok, "session": pl.get("session"),
                        "injected": pl.get("text") if ok else None, "reason": note})

    print(json.dumps({"ok": True, "acted": len(results), "results": results}, ensure_ascii=False))


if __name__ == "__main__":
    main()
