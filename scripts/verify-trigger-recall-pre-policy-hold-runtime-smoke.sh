#!/usr/bin/env bash
set -euo pipefail

# Read-only runtime smoke for trigger_recall_opt_in_pre_policy_hold_simulation.
# Starts a short-lived installed-binary MCP subprocess with an explicit all/Niche
# tool profile and AB_TRIGGER_RECALL_PRE_POLICY_HOLD_OPT_IN=1. It does not change
# the current Codex tool profile, deploy binaries, write memory, write graph
# edges, reindex, or authorize production enforce_hold.

export AGENT_BRIDGE_RETRIEVAL_TRAFFIC_CLASS=eval

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
AB_BIN="${AB_BIN:-$HOME/.local/bin/agent-bridge.real}"
IMPLEMENTATION_COMMIT="${IMPLEMENTATION_COMMIT:-fbeebeb}"

if [[ ! -x "$AB_BIN" ]]; then
  echo "AB_BIN is not executable: $AB_BIN" >&2
  exit 2
fi

AB_BIN="$AB_BIN" REPO_ROOT="$REPO_ROOT" IMPLEMENTATION_COMMIT="$IMPLEMENTATION_COMMIT" python3 - <<'PY'
import json
import os
import select
import subprocess
import sys
import time


ab_bin = os.environ["AB_BIN"]
repo_root = os.environ["REPO_ROOT"]
implementation_commit = os.environ["IMPLEMENTATION_COMMIT"]
scope = f"project:{repo_root}"

held_query = "Goal C dashboard state card spacing responsive layout visual design only"
accepted_query = "LSWR G25 store write execution preflight landed output only plan next gate"

env = os.environ.copy()
env["AGENT_BRIDGE_TOOL_PROFILE"] = "all"
env["AGENT_BRIDGE_TOOLSET"] = "all"
env["AB_TRIGGER_RECALL_PRE_POLICY_HOLD_OPT_IN"] = "1"
env.pop("AB_TRIGGER_RECALL_PRE_POLICY_HOLD_DISABLE", None)


proc = subprocess.Popen(
    [ab_bin, "mcp"],
    stdin=subprocess.PIPE,
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    text=True,
    env=env,
)


def cleanup():
    try:
        if proc.stdin and not proc.stdin.closed:
            proc.stdin.close()
    except Exception:
        pass
    try:
        proc.terminate()
        proc.wait(timeout=2)
    except Exception:
        try:
            proc.kill()
        except Exception:
            pass


def fail(message):
    stderr = ""
    cleanup()
    try:
        if proc.stderr:
            stderr = proc.stderr.read()
    except Exception:
        stderr = ""
    print(f"ERROR: {message}", file=sys.stderr)
    if stderr.strip():
        print("--- mcp stderr ---", file=sys.stderr)
        print(stderr[-4000:], file=sys.stderr)
    sys.exit(1)


def send(obj):
    assert proc.stdin is not None
    proc.stdin.write(json.dumps(obj, separators=(",", ":")) + "\n")
    proc.stdin.flush()


def read_until(ids, timeout=30):
    assert proc.stdout is not None
    deadline = time.time() + timeout
    found = {}
    while time.time() < deadline and ids - set(found):
        remaining = max(0.0, deadline - time.time())
        ready, _, _ = select.select([proc.stdout], [], [], min(0.25, remaining))
        if not ready:
            if proc.poll() is not None:
                break
            continue
        line = proc.stdout.readline()
        if not line:
            if proc.poll() is not None:
                break
            continue
        try:
            msg = json.loads(line)
        except Exception:
            continue
        msg_id = msg.get("id")
        if msg_id in ids:
            found[msg_id] = msg
    return found


def text_packet(call_msg):
    if "error" in call_msg:
        fail(f"tools/call error: {call_msg['error']}")
    result = call_msg.get("result") or {}
    for item in result.get("content") or []:
        if item.get("type") == "text":
            try:
                return json.loads(item.get("text") or "{}")
            except Exception as exc:
                fail(f"tools/call text content is not JSON: {exc}")
    fail("tools/call response has no text JSON content")


def approval_packet():
    return {
        "schema": "agent_bridge.memory.trigger_recall.pre_policy_hold_approval_packet.v0",
        "packet_status": "approved_for_pre_policy_hold_simulation",
        "approved_mode": "pre_policy_hold_simulation",
        "implementation_commit": implementation_commit,
        "regression_anchor": "aio2_trigger_recall_baseline_acceptance_shadow_20260623",
        "default_memory_search_unchanged": True,
        "raw_query_included": False,
        "raw_keys_included": False,
        "content_included": False,
        "rollback": "disable AB_TRIGGER_RECALL_PRE_POLICY_HOLD_OPT_IN or redeploy previous .real backup",
    }


def call_args(query, *, packet=True, operator_disabled=False):
    return {
        "approval_packet": approval_packet() if packet else None,
        "query": query,
        "mode": "fts",
        "scope": scope,
        "scope_mode": "local_only",
        "per_call_opt_in": True,
        "operator_disabled": operator_disabled,
        "limit": 5,
        "commit": implementation_commit,
    }


send(
    {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {
                "name": "trigger-recall-pre-policy-hold-runtime-smoke",
                "version": "0",
            },
        },
    }
)
send({"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}})
send({"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}})

messages = read_until({1, 2})
if 2 not in messages:
    fail("missing tools/list response")
if "error" in messages[2]:
    fail(f"tools/list error: {messages[2]['error']}")

tools = (messages[2].get("result") or {}).get("tools") or []
target = "trigger_recall_opt_in_pre_policy_hold_simulation"
target_tool = next((tool for tool in tools if tool.get("name") == target), None)
if target_tool is None:
    fail(f"{target} missing from all-profile tools/list")
props = (target_tool.get("inputSchema") or {}).get("properties") or {}
for required_prop in [
    "approval_packet",
    "query",
    "per_call_opt_in",
    "include_baseline_counts",
]:
    if required_prop not in props:
        fail(f"{target} schema missing {required_prop}")

cases = [
    (3, "held", call_args(held_query)),
    (4, "accepted", call_args(accepted_query)),
    (5, "missing_approval", call_args(held_query, packet=False)),
    (6, "operator_disabled", call_args(accepted_query, operator_disabled=True)),
]
for msg_id, label, args in cases:
    args["attempt_id"] = f"repeatable-runtime-smoke-{label}-20260623"
    send(
        {
            "jsonrpc": "2.0",
            "id": msg_id,
            "method": "tools/call",
            "params": {"name": target, "arguments": args},
        }
    )

messages.update(read_until({3, 4, 5, 6}))
missing = [msg_id for msg_id, _, _ in cases if msg_id not in messages]
if missing:
    fail(f"missing tools/call response ids: {missing}")

packets = {label: text_packet(messages[msg_id]) for msg_id, label, _ in cases}

expected_status = {
    "held": "held_by_query_intent",
    "accepted": "returned_accepted",
    "missing_approval": "blocked_to_baseline",
    "operator_disabled": "operator_disabled",
}
for label, expected in expected_status.items():
    status = packets[label].get("status")
    if status != expected:
        fail(f"{label} status {status!r}, expected {expected!r}")

if packets["held"].get("baseline", {}).get("store_search_called") is not False:
    fail("held path called store search, expected false")
if packets["accepted"].get("baseline", {}).get("store_search_called") is not True:
    fail("accepted path did not call store search, expected true")
if packets["missing_approval"].get("baseline", {}).get("store_search_called") is not True:
    fail("missing approval path did not fail open through store search")
if packets["operator_disabled"].get("baseline", {}).get("store_search_called") is not True:
    fail("operator disabled path did not fail open through store search")

for label, packet in packets.items():
    if packet.get("read_only") is not True:
        fail(f"{label} packet read_only is not true")
    baseline = packet.get("baseline") or {}
    side_effects = packet.get("side_effects") or {}
    decision = packet.get("decision") or {}
    if baseline.get("memory_search_mcp_called") is not False:
        fail(f"{label} memory_search_mcp_called is not false")
    if side_effects.get("calls_memory_search") is not False:
        fail(f"{label} calls_memory_search is not false")
    if side_effects.get("calls_memory_search_mcp") is not False:
        fail(f"{label} calls_memory_search_mcp is not false")
    if side_effects.get("records_coactivation") is not False:
        fail(f"{label} records_coactivation is not false")
    if side_effects.get("writes_memory") is not False:
        fail(f"{label} writes_memory is not false")
    if side_effects.get("writes_graph_edges") is not False:
        fail(f"{label} writes_graph_edges is not false")
    if side_effects.get("changes_memory_search_order") is not False:
        fail(f"{label} changes_memory_search_order is not false")
    if side_effects.get("changes_default_memory_search_schema") is not False:
        fail(f"{label} changes_default_memory_search_schema is not false")
    if side_effects.get("changes_production_retrieval_default") is not False:
        fail(f"{label} changes_production_retrieval_default is not false")
    if side_effects.get("runs_semantic_retrieval") is not False:
        fail(f"{label} runs_semantic_retrieval is not false")
    if side_effects.get("runs_graph_retrieval") is not False:
        fail(f"{label} runs_graph_retrieval is not false")
    if side_effects.get("may_enforce_hold") is not False:
        fail(f"{label} may_enforce_hold is not false")
    if decision.get("candidate_only") is not True:
        fail(f"{label} candidate_only is not true")

raw_text = json.dumps(packets, sort_keys=True)
raw_payload_leak_check = not any(
    secret in raw_text for secret in [held_query, accepted_query, scope]
)
if not raw_payload_leak_check:
    fail("raw query text or exact local scope leaked in smoke payload")

try:
    if proc.stdin and not proc.stdin.closed:
        proc.stdin.close()
    proc.wait(timeout=3)
except Exception:
    cleanup()

summary = {
    "schema": "agent_bridge.trigger_recall.pre_policy_hold_runtime_smoke_script.v0",
    "status": "passed",
    "ab_bin": ab_bin,
    "implementation_commit": implementation_commit,
    "tool_count_all_profile": len(tools),
    "tools_list_contains_target": True,
    "held_status": packets["held"].get("status"),
    "held_store_search_called": packets["held"].get("baseline", {}).get("store_search_called"),
    "accepted_status": packets["accepted"].get("status"),
    "accepted_store_search_called": packets["accepted"].get("baseline", {}).get("store_search_called"),
    "missing_approval_status": packets["missing_approval"].get("status"),
    "missing_approval_store_search_called": packets["missing_approval"].get("baseline", {}).get("store_search_called"),
    "operator_disabled_status": packets["operator_disabled"].get("status"),
    "operator_disabled_store_search_called": packets["operator_disabled"].get("baseline", {}).get("store_search_called"),
    "all_memory_search_mcp_called_false": all(
        packet.get("baseline", {}).get("memory_search_mcp_called") is False
        for packet in packets.values()
    ),
    "all_read_only": all(packet.get("read_only") is True for packet in packets.values()),
    "raw_payload_leak_check": raw_payload_leak_check,
    "boundaries": {
        "default_memory_search_changed": False,
        "production_enforce_hold_authorized": False,
        "memory_writes": False,
        "graph_writes": False,
        "semantic_retrieval": False,
        "graph_retrieval": False,
        "reindex": False,
    },
}

print(json.dumps(summary, indent=2, sort_keys=True))
print("OK: trigger recall pre-policy hold runtime smoke passed", file=sys.stderr)
PY
