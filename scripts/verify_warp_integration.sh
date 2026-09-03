#!/usr/bin/env bash
# End-to-end MCP smoke test aligned with docs/DESIGN-warp-first-agent-shell.md (W8).
# Exercises: capabilities (+ can_read_output), session_lifecycle_step bootstrap,
# project_detect, changes_digest, session_handoff, plan_save/load/update,
# warp_status, agent_message/agent_inbox; asserts tools/call responses include backend_id.
#
# Usage (from any cwd):
#   /path/to/agent-bridge/scripts/verify_warp_integration.sh
# Env:
#   AGENT_BRIDGE_BIN — path to agent-bridge binary (optional)
#
# Uses a temporary SQLite DB via AGENT_BRIDGE_DB (do not point at production DB).

set -euo pipefail

export AGENT_BRIDGE_RETRIEVAL_TRAFFIC_CLASS=eval

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
export ROOT

TMPDIR_RUN="$(mktemp -d "${TMPDIR:-/tmp}/ab-verify-warp-XXXXXX")"
export TMPDIR_RUN
trap 'rm -rf "$TMPDIR_RUN"' EXIT

export AGENT_BRIDGE_DB="${TMPDIR_RUN}/verify-warp-integration.db"

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

run_mcp() {
	local inp="$1"
	local out="$2"
	timeout 120 env AGENT_BRIDGE_DB="$AGENT_BRIDGE_DB" AGENT_BRIDGE_TOOL_PROFILE=all "$AB_BIN" mcp <"$inp" >"$out" 2>"${out}.stderr" || true
}

python3 <<'PY'
import json
import os

repo = os.path.abspath(os.environ["ROOT"])
plan_id = "verify_warp_integration_plan"

msgs = [
    {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {
        "protocolVersion": "2024-11-05",
        "capabilities": {},
        "clientInfo": {"name": "verify-warp-integration", "version": "1"},
    }},
    {"jsonrpc": "2.0", "method": "notifications/initialized"},
    {"jsonrpc": "2.0", "id": 10, "method": "tools/call", "params": {
        "name": "capabilities",
        "arguments": {},
    }},
    {"jsonrpc": "2.0", "id": 11, "method": "tools/call", "params": {
        "name": "session_lifecycle_step",
        "arguments": {"step": "bootstrap", "cwd": repo, "limit": 5},
    }},
    {"jsonrpc": "2.0", "id": 12, "method": "tools/call", "params": {
        "name": "project_detect",
        "arguments": {"cwd": repo},
    }},
    {"jsonrpc": "2.0", "id": 13, "method": "tools/call", "params": {
        "name": "changes_digest",
        "arguments": {"cwd": repo, "scope": "working_tree"},
    }},
    {"jsonrpc": "2.0", "id": 14, "method": "tools/call", "params": {
        "name": "session_handoff",
        "arguments": {"cwd": repo, "max_todos": 5, "max_handoff_memories": 3},
    }},
    {"jsonrpc": "2.0", "id": 15, "method": "tools/call", "params": {
        "name": "plan_save",
        "arguments": {
            "plan_id": plan_id,
            "title": "verify_warp_integration",
            "steps": [
                {"id": "a", "desc": "step a", "status": "pending"},
                {"id": "b", "desc": "step b", "status": "pending"},
            ],
        },
    }},
    {"jsonrpc": "2.0", "id": 16, "method": "tools/call", "params": {
        "name": "plan_load",
        "arguments": {"plan_id": plan_id},
    }},
    {"jsonrpc": "2.0", "id": 17, "method": "tools/call", "params": {
        "name": "plan_update",
        # The generic Warp smoke has no trusted harness-outcome producer. Keep
        # this as a non-terminal transition; focused tests exercise the
        # fail-closed completion-evidence gate.
        "arguments": {"plan_id": plan_id, "step_id": "a", "status": "in_progress"},
    }},
    {"jsonrpc": "2.0", "id": 18, "method": "tools/call", "params": {
        "name": "warp_status",
        "arguments": {},
    }},
    {"jsonrpc": "2.0", "id": 19, "method": "tools/call", "params": {
        "name": "agent_message",
        "arguments": {
            "from_session": "verify-from",
            "to_session": "verify-to",
            "payload": {"type": "verify_warp_integration", "n": 1},
        },
    }},
    {"jsonrpc": "2.0", "id": 20, "method": "tools/call", "params": {
        "name": "agent_inbox",
        "arguments": {"to_session": "verify-to", "limit": 20},
    }},
    # terminal IPC checks (work whether or not Warp is currently running)
    {"jsonrpc": "2.0", "id": 21, "method": "tools/call", "params": {
        "name": "terminal_list",
        "arguments": {},
    }},
]

out_dir = os.environ["TMPDIR_RUN"]
# MCP requests may complete out of order. Persist prerequisites in a first
# server run so plan_load and agent_inbox cannot race plan_save/agent_message.
prerequisite_ids = {15, 19}
handshake = msgs[:2]
tool_msgs = msgs[2:]
phases = (
    ("prerequisite-in.jsonl", handshake + [m for m in tool_msgs if m.get("id") in prerequisite_ids]),
    ("in.jsonl", handshake + [m for m in tool_msgs if m.get("id") not in prerequisite_ids]),
)
for filename, phase_msgs in phases:
    with open(os.path.join(out_dir, filename), "w") as f:
        for m in phase_msgs:
            f.write(json.dumps(m) + "\n")
PY

run_mcp "${TMPDIR_RUN}/prerequisite-in.jsonl" "${TMPDIR_RUN}/prerequisite-out.jsonl"
run_mcp "${TMPDIR_RUN}/in.jsonl" "${TMPDIR_RUN}/out.jsonl"

python3 <<'PY'
import json
import os
import sys

OUT = os.path.join(os.environ["TMPDIR_RUN"], "out.jsonl")
PREREQUISITE_OUT = os.path.join(os.environ["TMPDIR_RUN"], "prerequisite-out.jsonl")


def parse_responses(path):
    by_id = {}
    for line in open(path):
        line = line.strip()
        if not line:
            continue
        try:
            d = json.loads(line)
        except json.JSONDecodeError:
            continue
        i = d.get("id")
        if i is not None:
            by_id[i] = d
    return by_id


def require_backend_id(result, msg):
    bid = result.get("backend_id")
    if not isinstance(bid, dict):
        raise AssertionError(f"{msg}: missing backend_id object, got {bid!r}")
    for k in ("terminal", "browser", "agent_runtime", "memory"):
        if k not in bid:
            raise AssertionError(f"{msg}: backend_id missing {k!r}")
        if not isinstance(bid[k], str):
            raise AssertionError(f"{msg}: backend_id[{k}] must be str")


def first_text_block(result):
    for block in result.get("content") or []:
        if block.get("type") == "text":
            return block.get("text") or ""
    return ""


def parse_inner_json(result, msg):
    text = first_text_block(result)
    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        raise AssertionError(f"{msg}: expected JSON in text block: {e}; head={text[:200]!r}")


by_id = parse_responses(PREREQUISITE_OUT)
by_id.update(parse_responses(OUT))
if not by_id:
    raw = "\n".join(open(path).read() for path in (PREREQUISITE_OUT, OUT))
    err = "\n".join(
        open(path + ".stderr").read()
        for path in (PREREQUISITE_OUT, OUT)
        if os.path.isfile(path + ".stderr")
    )
    print("FAIL: no JSON-RPC responses on stdout", file=sys.stderr)
    if raw.strip():
        print("--- stdout ---", file=sys.stderr)
        print(raw[:4000], file=sys.stderr)
    if err.strip():
        print("--- stderr ---", file=sys.stderr)
        print(err[:4000], file=sys.stderr)
    sys.exit(1)

for tid in (10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21):
    d = by_id.get(tid)
    if not d:
        print(f"FAIL: missing response id={tid}", file=sys.stderr)
        sys.exit(1)
    if d.get("error"):
        print(f"FAIL: MCP error id={tid}: {d['error']}", file=sys.stderr)
        sys.exit(1)
    result = d.get("result")
    if not isinstance(result, dict):
        print(f"FAIL: id={tid} no result", file=sys.stderr)
        sys.exit(1)
    require_backend_id(result, f"id={tid}")

# capabilities → nested terminal.can_read_output
caps = parse_inner_json(by_id[10]["result"], "capabilities")
term = caps.get("terminal")
if not isinstance(term, dict) or "can_read_output" not in term:
    print(f"FAIL: capabilities.terminal.can_read_output missing: {caps!r}", file=sys.stderr)
    sys.exit(1)
print(f"OK: capabilities terminal.backend={term.get('backend')!r} can_read_output={term.get('can_read_output')}")

# lifecycle bootstrap → primer text (empty store omits "Bootstrap" header)
boot_txt = first_text_block(by_id[11]["result"])
if not (
    "Bootstrap" in boot_txt
    or "bootstrap" in boot_txt.lower()
    or "(no scoped memories yet)" in boot_txt
    or "Session Lifecycle Reminder" in boot_txt
):
    print(f"FAIL: lifecycle bootstrap text unexpected: {boot_txt[:400]!r}", file=sys.stderr)
    sys.exit(1)
print("OK: session_lifecycle_step bootstrap")

proj = parse_inner_json(by_id[12]["result"], "project_detect")
if not proj.get("languages"):
    print(f"FAIL: project_detect languages empty: {proj!r}", file=sys.stderr)
    sys.exit(1)
print(f"OK: project_detect languages={proj.get('languages')}")

digest = parse_inner_json(by_id[13]["result"], "changes_digest")
if "files_changed" not in digest:
    print(f"FAIL: changes_digest: {digest!r}", file=sys.stderr)
    sys.exit(1)
print(f"OK: changes_digest files_changed={digest.get('files_changed')}")

handoff = parse_inner_json(by_id[14]["result"], "session_handoff")
for k in ("generated_at", "git", "pending_items"):
    if k not in handoff:
        print(f"FAIL: session_handoff missing {k}: {handoff!r}", file=sys.stderr)
        sys.exit(1)
print("OK: session_handoff")

ps = parse_inner_json(by_id[15]["result"], "plan_save")
if ps.get("status") != "ok":
    print(f"FAIL: plan_save: {ps!r}", file=sys.stderr)
    sys.exit(1)
pl = parse_inner_json(by_id[16]["result"], "plan_load")
if pl.get("plan_id") != "verify_warp_integration_plan" or not pl.get("steps"):
    print(f"FAIL: plan_load: {pl!r}", file=sys.stderr)
    sys.exit(1)
pu = parse_inner_json(by_id[17]["result"], "plan_update")
if pu.get("status") != "ok":
    print(f"FAIL: plan_update: {pu!r}", file=sys.stderr)
    sys.exit(1)
print("OK: plan_save / plan_load / plan_update")

warp = parse_inner_json(by_id[18]["result"], "warp_status")
if "configured_terminal_backend_id" not in warp:
    print(f"FAIL: warp_status: {warp!r}", file=sys.stderr)
    sys.exit(1)
print("OK: warp_status")

am = parse_inner_json(by_id[19]["result"], "agent_message")
if am.get("status") != "ok":
    print(f"FAIL: agent_message: {am!r}", file=sys.stderr)
    sys.exit(1)
ib = parse_inner_json(by_id[20]["result"], "agent_inbox")
rows = ib.get("messages")
if not isinstance(rows, list) or len(rows) < 1:
    print(f"FAIL: agent_inbox: {ib!r}", file=sys.stderr)
    sys.exit(1)
print(f"OK: agent_message + agent_inbox ({len(rows)} row(s))")

# terminal_list — always runs; result depends on whether Warp IPC socket is live
tl = parse_inner_json(by_id[21]["result"], "terminal_list")
# capabilities already fetched above; re-parse for warp_ipc_socket_ready
# warp_ipc_socket_ready is nested under terminal.capabilities in the response
warp_ipc_ready = caps.get("terminal", {}).get("capabilities", {}).get("warp_ipc_socket_ready", False)
ipc_sessions = []
if warp_ipc_ready:
    if not isinstance(tl, list):
        print(f"FAIL: terminal_list with live IPC should return a list: {tl!r}", file=sys.stderr)
        sys.exit(1)
    ipc_sessions = tl
    print(f"OK: terminal_list via Warp IPC — {len(tl)} session(s) active")
else:
    import os
    sock_path = os.path.join(
        os.environ.get("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}"),
        "warp-agent-bridge.sock",
    )
    print(f"NOTE: Warp IPC socket not ready ({sock_path}); terminal_list returned: {tl!r}")
    print("      Build Warp fork and launch it to verify full end-to-end path.")

# Store session list for second-pass read_blocks test
import json as _json
with open(os.path.join(os.environ["TMPDIR_RUN"], "ipc_sessions.json"), "w") as _f:
    _json.dump(ipc_sessions, _f)

print("")
print("verify_warp_integration.sh: all checks passed")
PY

# ── Second-pass: terminal_read_blocks (only when Warp IPC has live sessions) ───
python3 <<'PY2'
import json, os, sys, subprocess, tempfile

out_dir = os.environ["TMPDIR_RUN"]
root    = os.environ["ROOT"]
ab_bin  = os.environ.get("AGENT_BRIDGE_BIN") or (
    f"{root}/target/release/agent-bridge" if os.path.exists(f"{root}/target/release/agent-bridge")
    else f"{root}/target/debug/agent-bridge"
)
db      = os.environ["AGENT_BRIDGE_DB"]

sessions = json.load(open(os.path.join(out_dir, "ipc_sessions.json")))
if not sessions:
    print("SKIP: terminal_read_blocks — no live Warp IPC sessions")
    sys.exit(0)

pane_id = sessions[0].get("id") or sessions[0].get("session_id", "")
if not pane_id:
    print(f"SKIP: terminal_read_blocks — could not extract pane id from {sessions[0]!r}")
    sys.exit(0)

msgs = [
    {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {
        "protocolVersion": "2024-11-05",
        "capabilities": {},
        "clientInfo": {"name": "verify-read-blocks", "version": "1"},
    }},
    {"jsonrpc": "2.0", "method": "notifications/initialized"},
    {"jsonrpc": "2.0", "id": 30, "method": "tools/call", "params": {
        "name": "terminal_read_blocks",
        "arguments": {"pane": pane_id, "limit": 5},
    }},
]

inp = os.path.join(out_dir, "rb_in.jsonl")
out = os.path.join(out_dir, "rb_out.jsonl")
with open(inp, "w") as f:
    for m in msgs:
        f.write(json.dumps(m) + "\n")

subprocess.run(
    [ab_bin, "mcp"],
    stdin=open(inp), stdout=open(out, "w"),
    stderr=subprocess.DEVNULL,
    env={**os.environ, "AGENT_BRIDGE_DB": db, "AGENT_BRIDGE_TOOL_PROFILE": "all"},
    timeout=30,
)

by_id = {}
for line in open(out):
    line = line.strip()
    if not line: continue
    try:
        d = json.loads(line)
    except Exception:
        continue
    if d.get("id") is not None:
        by_id[d["id"]] = d

resp = by_id.get(30)
if resp is None:
    print("FAIL: terminal_read_blocks — no response received", file=sys.stderr)
    sys.exit(1)
if resp.get("error"):
    print(f"FAIL: terminal_read_blocks MCP error: {resp['error']}", file=sys.stderr)
    sys.exit(1)

result = resp.get("result", {})
content = result.get("content", [{}])
text = content[0].get("text", "{}") if content else "{}"
try:
    data = json.loads(text)
except Exception:
    print(f"FAIL: terminal_read_blocks — non-JSON result: {text[:200]!r}", file=sys.stderr)
    sys.exit(1)

if "error" in data:
    print(f"FAIL: terminal_read_blocks tool error: {data['error']!r}", file=sys.stderr)
    sys.exit(1)

blocks = data.get("blocks")
if not isinstance(blocks, list):
    print(f"FAIL: terminal_read_blocks — expected 'blocks' list, got: {data!r}", file=sys.stderr)
    sys.exit(1)

# Validate timestamp fields when blocks are present
for b in blocks:
    for ts_key in ("start_ms", "end_ms"):
        if ts_key in b and not isinstance(b[ts_key], int):
            print(f"FAIL: terminal_read_blocks — {ts_key} must be int, got {b[ts_key]!r}", file=sys.stderr)
            sys.exit(1)
    if "duration_ms" in b and not isinstance(b["duration_ms"], int):
        print(f"FAIL: terminal_read_blocks — duration_ms must be int, got {b['duration_ms']!r}", file=sys.stderr)
        sys.exit(1)

ts_present = sum(1 for b in blocks if "start_ms" in b)
print(f"OK: terminal_read_blocks — {len(blocks)} block(s), {ts_present} with timestamps")
PY2
