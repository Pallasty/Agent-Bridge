#!/usr/bin/env bash
# MCP-level E2E for Warp IPC + terminal_read_output.
# Spins up a local Unix-socket stub that implements Warp bridge RPC:
#   list_sessions, send_text, read_scrollback
# Then runs `agent-bridge mcp` with backend forced to Warp and asserts:
#   - capabilities.terminal.can_read_output == true
#   - terminal_list returns the IPC session id
#   - terminal_read_output returns expected lines

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

TMPDIR_RUN="$(mktemp -d "${TMPDIR:-/tmp}/ab-warp-read-e2e-XXXXXX")"
trap 'rm -rf "$TMPDIR_RUN"' EXIT
export TMPDIR_RUN

SOCK="${TMPDIR_RUN}/warp-agent-bridge.sock"
DB="${TMPDIR_RUN}/state.db"
export SOCK

if [[ -n "${AGENT_BRIDGE_BIN:-}" ]]; then
  AB_BIN="${AGENT_BRIDGE_BIN}"
elif [[ -x "${ROOT}/target/release/agent-bridge" ]]; then
  AB_BIN="${ROOT}/target/release/agent-bridge"
elif [[ -x "${ROOT}/target/debug/agent-bridge" ]]; then
  AB_BIN="${ROOT}/target/debug/agent-bridge"
elif command -v agent-bridge &>/dev/null; then
  AB_BIN="$(command -v agent-bridge)"
else
  echo "FAIL: agent-bridge binary not found; run: cargo build -p ab-bridge --bin agent-bridge" >&2
  exit 1
fi

python3 <<'PY' &
import json
import os
import socket

sock_path = os.environ["SOCK"]
if os.path.exists(sock_path):
    os.remove(sock_path)

srv = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
srv.bind(sock_path)
srv.listen(8)
srv.settimeout(1.0)

while True:
    try:
        conn, _ = srv.accept()
    except socket.timeout:
        break
    with conn:
        buf = b""
        while not buf.endswith(b"\n"):
            chunk = conn.recv(4096)
            if not chunk:
                break
            buf += chunk
        req = json.loads(buf.decode("utf-8").strip() or "{}")
        method = req.get("method")
        if method == "list_sessions":
            result = [{"session_id": "e2e-session", "title": "Warp E2E", "cwd": "/tmp"}]
            err = None
        elif method == "read_scrollback":
            result = ["e2e line 1", "e2e line 2"]
            err = None
        elif method == "send_text":
            result = {"ok": True}
            err = None
        else:
            result = None
            err = {"code": -32601, "message": f"unknown method: {method}"}
        resp = {"id": req.get("id", ""), "result": result, "error": err}
        conn.sendall((json.dumps(resp) + "\n").encode("utf-8"))

srv.close()
PY
SERVER_PID=$!

python3 <<'PY'
import json
import os

msgs = [
    {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {
        "protocolVersion": "2024-11-05",
        "capabilities": {},
        "clientInfo": {"name": "verify-warp-read-e2e", "version": "1"},
    }},
    {"jsonrpc": "2.0", "method": "notifications/initialized"},
    {"jsonrpc": "2.0", "id": 10, "method": "tools/call", "params": {"name": "capabilities", "arguments": {}}},
    {"jsonrpc": "2.0", "id": 11, "method": "tools/call", "params": {"name": "terminal_list", "arguments": {}}},
    {"jsonrpc": "2.0", "id": 12, "method": "tools/call", "params": {
        "name": "terminal_read_output",
        "arguments": {"pane": "warp:e2e-session", "last_n_lines": 10}
    }},
]
inp = os.path.join(os.environ["TMPDIR_RUN"], "in.jsonl")
with open(inp, "w") as f:
    for m in msgs:
        f.write(json.dumps(m) + "\n")
PY

timeout 120 env \
  AGENT_BRIDGE_TERMINAL=warp \
  AGENT_BRIDGE_WARP_IPC_SOCKET="${SOCK}" \
  AGENT_BRIDGE_DB="${DB}" \
  "${AB_BIN}" mcp <"${TMPDIR_RUN}/in.jsonl" >"${TMPDIR_RUN}/out.jsonl" 2>"${TMPDIR_RUN}/out.stderr" || true

python3 <<'PY'
import json
import os
import sys

out = os.path.join(os.environ["TMPDIR_RUN"], "out.jsonl")

rows = {}
for line in open(out):
    line = line.strip()
    if not line:
        continue
    try:
        d = json.loads(line)
    except Exception:
        continue
    if "id" in d:
        rows[d["id"]] = d

for i in (10, 11, 12):
    if i not in rows:
        print(f"FAIL: missing response id={i}", file=sys.stderr)
        sys.exit(1)
    if rows[i].get("error"):
        print(f"FAIL: MCP error id={i}: {rows[i]['error']}", file=sys.stderr)
        sys.exit(1)

caps_text = rows[10]["result"]["content"][0]["text"]
caps = json.loads(caps_text)
if not caps.get("terminal", {}).get("can_read_output"):
    print(f"FAIL: expected can_read_output=true, got {caps!r}", file=sys.stderr)
    sys.exit(1)

list_text = rows[11]["result"]["content"][0]["text"]
lst = json.loads(list_text)
if not isinstance(lst, list) or not lst or lst[0].get("id") != "warp:e2e-session":
    print(f"FAIL: terminal_list unexpected: {lst!r}", file=sys.stderr)
    sys.exit(1)

read_text = rows[12]["result"]["content"][0]["text"]
read = json.loads(read_text)
lines = read.get("lines", [])
if lines != ["e2e line 1", "e2e line 2"]:
    print(f"FAIL: terminal_read_output lines mismatch: {read!r}", file=sys.stderr)
    sys.exit(1)

print("verify_warp_terminal_read_output_e2e.sh: all checks passed")
PY

wait "${SERVER_PID}" || true
