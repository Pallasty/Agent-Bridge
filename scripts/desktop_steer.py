#!/usr/bin/env python3
"""Blessed phase-2 executor for ``kind=steer`` host-confirm (cross-process control plane).

Mirrors desktop_action.py / desktop_invoke.py: takes a single-use ``--confirm-token``,
validates + CONSUMES it via ``load_and_consume_pending(expect_kind="steer")`` BEFORE acting,
then injects the staged text into the target tmux session via the same primitive
remote_steer.rs builds — ``send-keys -t SESS -l -- TEXT`` (+ Enter if submit), honoring
``AB_TMUX_BIN`` (rmux drop-in).

Only the GATED paths invoke this: the dock_server on a human approve, or (later) the Rust
``desktop_confirm`` MCP tool. It is never the staging surface — staging is stage_steer.py /
a process queuing a pending. Prints one JSON line ending in ``{"rc":N}``; rc=0 = success.

Honest threat model (mirrors host-confirm path A / present_approval): this prevents SILENT /
accidental cross-process injection (single-use + TTL + the human sees text+session+staged_by
on the dock before approving). It is NOT agent-proof — a shell-capable local process can
already inject directly — and it does not defend against a SOCIALLY-ENGINEERED human who
approves a malicious-but-plausible payload. The token lifecycle is owned solely by
load_and_consume_pending; this executor invents none of it.
"""
import argparse
import json
import os
import pathlib
import subprocess
import sys

# the store lives beside us in scripts/ (this file is scripts/desktop_steer.py)
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from desktop_confirm_store import load_and_consume_pending  # noqa: E402

TMUX = os.environ.get("AB_TMUX_BIN", "tmux")


def _emit(rc: int, **kw) -> None:
    print(json.dumps({"schema": "desktop_steer.v0", "rc": rc, "ok": rc == 0, **kw}, ensure_ascii=False))
    sys.exit(rc)


def main() -> None:
    ap = argparse.ArgumentParser(description="execute a human-approved kind=steer pending (gated phase 2)")
    ap.add_argument("--confirm-token", dest="token", required=True,
                    help="single-use token minted when the steer was staged")
    ap.add_argument("--wait", type=float, default=0.0, help="accepted for parity with desktop_confirm; unused")
    a = ap.parse_args()

    # consume FIRST (single-use, marked consumed before we inject → a failed inject can't replay)
    rec, why = load_and_consume_pending(a.token, expect_kind="steer")
    if rec is None:
        _emit(2, error=why, code="token_invalid")

    pl = rec.get("payload") or {}
    session = pl.get("session") or ""
    text = pl.get("text")
    submit = bool(pl.get("submit"))
    if not session or text is None:
        _emit(3, error="pending missing session/text", code="bad_payload")

    try:
        r1 = subprocess.run([TMUX, "send-keys", "-t", session, "-l", "--", text],
                            capture_output=True, text=True, timeout=8)
    except (OSError, subprocess.SubprocessError) as exc:
        _emit(4, error=f"tmux not runnable: {exc}", code="executor_unrunnable")
    if r1.returncode != 0:
        _emit(5, error=(r1.stderr or "send-keys -l failed").strip(), code="inject_failed", session=session)
    if submit:
        r2 = subprocess.run([TMUX, "send-keys", "-t", session, "Enter"],
                            capture_output=True, text=True, timeout=8)
        if r2.returncode != 0:
            # The text already landed (r1 succeeded) but Enter failed, and the single-use
            # token is already consumed → un-retriable via the gate. Surface the partial
            # state so the caller knows the literal text is sitting in the target buffer
            # unsubmitted (re-stage + re-approve needed, not a no-op retry).
            _emit(6, error=(r2.stderr or "Enter failed").strip(), code="submit_failed",
                  session=session, injected_without_submit=True, injected=text)

    _emit(0, detail="injected", kind="steer", session=session, injected=text, submit=submit)


if __name__ == "__main__":
    main()
