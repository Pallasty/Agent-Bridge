#!/usr/bin/env python3
"""PROBE (B / human-mediated cross-process control plane, 2026-06-01).

Stage a ``kind=steer`` pending so "process A" can queue a SESSION INJECTION for a
human to release from the presence dock. It writes a pending host-confirm record
whose payload names the target tmux session + the EXACT text to inject. The dock
surfaces it legibly; a human approves (recorded to dock_decisions/); then
``steer_release.py`` (the agent-reader) consumes the single-use token and performs
the injection via the same tmux primitive ``agent_steer`` uses.

Feasibility probe only — it does NOT widen the gate. Staging writes a pending and
acts on nothing; the release path is an agent-run one-shot, not a standing
executor. If the probe shows value, the gated dock-server-executes path for
kind=steer earns a full security review (option 3). See the dock project memory.
"""
import argparse
import json
import os
import pathlib
import sys
import time

# import the canonical store (same one the host-confirm gate uses)
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))  # scripts/
from desktop_confirm_store import DEFAULT_CONFIRM_TTL, mint_token, write_pending  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser(description="stage a kind=steer pending for dock approval (probe)")
    ap.add_argument("--session", required=True, help="target tmux session (e.g. ab__proj__role)")
    ap.add_argument("--text", required=True, help="exact text to inject into the session")
    ap.add_argument("--submit", action="store_true", help="press Enter after the text")
    ap.add_argument("--ttl", type=int, default=DEFAULT_CONFIRM_TTL, help="seconds the token stays valid")
    ap.add_argument("--by", default=os.environ.get("AB_SESSION_IDENTITY", "unknown"),
                    help="who is staging this (for legibility/audit)")
    a = ap.parse_args()

    token = mint_token()
    payload = {
        "session": a.session,
        "text": a.text,
        "submit": bool(a.submit),
        "staged_by": a.by,
    }
    submit_note = " ⏎" if a.submit else ""
    summary = f"steer → 注入会话 {a.session}: {a.text!r}{submit_note}"
    write_pending(token, "steer", payload, summary, int(time.time()) + a.ttl)
    print(json.dumps(
        {"ok": True, "token": token, "kind": "steer", "session": a.session,
         "submit": bool(a.submit), "expires_in_s": a.ttl, "summary": summary},
        ensure_ascii=False))


if __name__ == "__main__":
    main()
