#!/usr/bin/env python3
"""Dock server (Slice 1a) — static files + a localhost-only decision endpoint.

Serves the dock dir over http (so the panel's fetch works) AND accepts
``POST /api/decide {token, decision}`` to RECORD a human's approve/reject for a
pending host-confirm token.

SAFETY — this server NEVER executes a host action. It only writes the human's
verdict to ``~/.cache/agent-bridge/dock_decisions/<token>.json``. The canonical,
gated executor (Rust ``desktop_confirm`` / ``load_and_consume_pending``) still
owns single-use consumption + execution. The dock is purely the human-input
surface — the same split as ``present_await_decision`` (human decides in the
DOM, the gated path executes). A decision is only recorded for a token that
actually exists as a pending record, so the dock can't fabricate approvals.
"""
import json
import os
import pathlib
import re
import sys
import time
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

HOME = pathlib.Path.home()
PENDING_DIR = HOME / ".cache/agent-bridge/desktop_pending"
DECISIONS_DIR = HOME / ".cache/agent-bridge/dock_decisions"
DOCK_DIR = pathlib.Path(__file__).resolve().parent


def safe_token(t: str) -> str:
    return re.sub(r"[^A-Za-z0-9_-]", "_", str(t))[:128]


def pending_token_exists(token: str) -> bool:
    """True iff `token` matches the `token` field of a still-pending record."""
    if not token or not PENDING_DIR.exists():
        return False
    for f in PENDING_DIR.glob("*.json"):
        try:
            rec = json.loads(f.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if rec.get("token") == token and rec.get("status") == "pending":
            return True
    return False


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *a, **k):
        super().__init__(*a, directory=str(DOCK_DIR), **k)

    def log_message(self, *a):
        pass  # keep the dock quiet

    def _json(self, code, obj):
        body = json.dumps(obj).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        if self.path.split("?")[0] != "/api/decide":
            return self._json(404, {"ok": False, "error": "not found"})
        try:
            n = int(self.headers.get("Content-Length") or 0)
            req = json.loads(self.rfile.read(n) or b"{}")
        except Exception as exc:
            return self._json(400, {"ok": False, "error": f"bad body: {exc}"})
        token = str(req.get("token") or "")
        decision = str(req.get("decision") or "")
        if decision not in ("approve", "reject"):
            return self._json(400, {"ok": False, "error": "decision must be approve|reject"})
        if not pending_token_exists(token):
            return self._json(404, {"ok": False, "error": "no such pending token"})
        DECISIONS_DIR.mkdir(parents=True, exist_ok=True)
        rec = {"token": token, "decision": decision, "ts": int(time.time()), "source": "dock"}
        (DECISIONS_DIR / f"{safe_token(token)}.json").write_text(
            json.dumps(rec, ensure_ascii=False), encoding="utf-8"
        )
        return self._json(200, {"ok": True, "decision": decision})


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else int(os.environ.get("AB_DOCK_PORT", "8777"))
    ThreadingHTTPServer(("127.0.0.1", port), Handler).serve_forever()
