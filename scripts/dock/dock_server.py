#!/usr/bin/env python3
"""Dock server (option 3) — static files + a localhost-only DECISION+EXECUTE endpoint.

Serves the dock dir over http (so the panel's fetch works) AND handles
``POST /api/decide {token, decision}`` to RELEASE a human's approve/reject for a
pending host-confirm token:

  - reject  -> reject_pending(token): transition pending->rejected. Shells NOTHING;
               pure capability subtraction.
  - approve -> shell the EXACT blessed phase-2 executor by the pending's kind
               (action->desktop_action.py, invoke->desktop_invoke.py,
                steer->desktop_steer.py) with ``--confirm-token``. Single-use + TTL +
               kind are enforced solely by load_and_consume_pending INSIDE those
               executors; the dock invents zero token lifecycle.

POSTURE — this is the deliberate flip from the records-only Slice-1a dock: the dock is
now a host-action EXECUTOR, not just a mirror. Honest model (mirrors present_approval.rs /
host-confirm path A): it puts a human CLICK in front of an out-of-band-minted host action
and defends against SILENT / accidental mutation. It is NOT agent-proof — a shell-capable
local process can already shell the executors / delete the pending — and it does not defend
a SOCIALLY-ENGINEERED human. The localhost POST is a human-click TRANSPORT, not a trust
boundary. For kind=steer the released action injects into ANOTHER session, so the dock
renders the exact text+session+staged_by (aggregate.py) before the human approves.

GET is delegated to SimpleHTTPRequestHandler rooted at this dir (no arbitrary files).
Only POST /api/decide mutates, behind: loopback-peer + Host-pin (anti DNS-rebind) +
same-origin + X-AB-Dock header (anti-CSRF) + JSON content-type + body cap + a hex token
hard-gate before any filesystem touch + a per-process lock (anti-TOCTOU).
"""
import json
import os
import pathlib
import re
import subprocess
import sys
import threading
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

DOCK_DIR = pathlib.Path(__file__).resolve().parent
REPO = os.environ.get("AB_REPO_ROOT", "/Data/CascadeProjects/agent-bridge")
PORT = int(sys.argv[1]) if len(sys.argv) > 1 else int(os.environ.get("AB_DOCK_PORT", "8777"))
HOST = "127.0.0.1"
HEX32 = re.compile(r"^[0-9a-f]{32}$")
MAX_BODY = 1024

# blessed phase-2 executor per kind (the ONLY scripts an approve may shell)
KIND_SCRIPT = {
    "action": "desktop_action.py",
    "invoke": "desktop_invoke.py",
    "steer": "desktop_steer.py",
}

# Resolve the store helper: a copy DEPLOYED beside this server (DOCK_DIR is sys.path[0])
# wins so the dock doesn't depend on the checkout being synced; else the repo's scripts/.
sys.path.append(os.path.join(REPO, "scripts"))
from desktop_confirm_store import peek_kind, reject_pending  # noqa: E402

_LOCK = threading.Lock()


class Handler(SimpleHTTPRequestHandler):
    # GET inherited from SimpleHTTPRequestHandler, rooted at DOCK_DIR (directory=).

    def log_message(self, *a):  # keep the dock quiet
        pass

    def _json(self, code, obj):
        b = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def _loopback(self):
        ip = self.client_address[0]
        return ip == "::1" or ip.startswith("127.")

    def _host_ok(self):
        h = (self.headers.get("Host") or "").lower()
        return h in (f"127.0.0.1:{PORT}", f"localhost:{PORT}")

    def _origin_ok(self):
        o = self.headers.get("Origin")
        if o and o.lower() not in (f"http://127.0.0.1:{PORT}", f"http://localhost:{PORT}"):
            return False
        return self.headers.get("X-AB-Dock") == "1"  # dock fetch sets this; a CSRF form cannot

    def do_POST(self):
        if self.path.split("?")[0] != "/api/decide":
            return self._json(404, {"ok": False, "reason": "not found"})
        if not self._loopback():
            return self._json(403, {"ok": False, "reason": "non-loopback"})
        if not self._host_ok():
            return self._json(421, {"ok": False, "reason": "bad host"})
        if not self._origin_ok():
            return self._json(403, {"ok": False, "reason": "origin/header"})
        if (self.headers.get("Content-Type") or "").split(";")[0].strip() != "application/json":
            return self._json(415, {"ok": False, "reason": "need json"})
        try:
            n = int(self.headers.get("Content-Length", ""))
        except ValueError:
            return self._json(411, {"ok": False, "reason": "need length"})
        if n <= 0 or n > MAX_BODY:
            return self._json(413, {"ok": False, "reason": "body size"})
        try:
            body = json.loads(self.rfile.read(n).decode("utf-8"))
        except Exception:  # noqa: BLE001
            return self._json(400, {"ok": False, "reason": "bad json"})
        token = body.get("token", "") if isinstance(body, dict) else ""
        decision = body.get("decision", "") if isinstance(body, dict) else ""
        if not isinstance(token, str) or not HEX32.match(token):
            return self._json(400, {"ok": False, "reason": "bad token shape"})
        if decision not in ("approve", "reject"):
            return self._json(400, {"ok": False, "reason": "bad decision"})

        with _LOCK:
            kind = peek_kind(token)
            if kind is None:
                return self._json(409, {"ok": False, "reason": "no live pending (used/expired/never issued)"})
            if decision == "reject":
                ok, why = reject_pending(token)
                return self._json(200 if ok else 409,
                                  {"ok": ok, "decision": "reject", "reason": why,
                                   "status": "rejected" if ok else None})
            # approve -> shell the EXACT blessed executor by kind (mirror desktop_confirm)
            script_name = KIND_SCRIPT.get(kind)
            if script_name is None:
                return self._json(422, {"ok": False, "decision": "approve",
                                        "reason": f"no executor for kind {kind!r}"})
            script = os.path.join(REPO, "scripts", script_name)
            try:
                cp = subprocess.run(
                    ["python3", script, "--confirm-token", token],
                    cwd=REPO, capture_output=True, text=True, timeout=12,
                )
            except subprocess.TimeoutExpired:
                return self._json(200, {"ok": False, "decision": "approve", "rc": 124,
                                        "reason": "executor timeout"})
            except OSError as exc:
                return self._json(200, {"ok": False, "decision": "approve", "rc": 127,
                                        "reason": f"executor not runnable: {exc}"})
            try:
                rec = json.loads((cp.stdout or "").strip().splitlines()[-1])
            except Exception:  # noqa: BLE001
                rec = {"rc": cp.returncode, "error": ((cp.stderr or cp.stdout) or "")[-300:]}
            rc = rec.get("rc", cp.returncode)
            return self._json(200, {"ok": rc == 0, "decision": "approve", "rc": rc, "kind": kind,
                                    "reason": rec.get("error") or rec.get("detail") or ("ok" if rc == 0 else "failed"),
                                    "status": "consumed"})


if __name__ == "__main__":
    httpd = ThreadingHTTPServer((HOST, PORT), partial(Handler, directory=str(DOCK_DIR)))
    httpd.serve_forever()
