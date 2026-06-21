#!/usr/bin/env bash
set -euo pipefail

# Read-only MCP smoke for the T6 aggregate-only recall summary and human-review chain.
# Verifies tools/list schema + tools/call behavior without writing memory or
# granting candidate-set/runtime authority.

AB_BIN="${AB_BIN:-/Users/pallasting/.local/bin/agent-bridge.real}"

if [[ ! -x "$AB_BIN" ]]; then
  echo "AB_BIN is not executable: $AB_BIN" >&2
  exit 2
fi

AB_BIN="$AB_BIN" python3 - <<'PY'
import json
import os
import subprocess
import sys
import time

ab_bin = os.environ["AB_BIN"]
env = os.environ.copy()
env.setdefault("AGENT_BRIDGE_TOOL_PROFILE", "all")
env.setdefault("AGENT_BRIDGE_TOOLSET", "all")

proc = subprocess.Popen(
    [ab_bin, "mcp"],
    stdin=subprocess.PIPE,
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    text=True,
    env=env,
)


def fail(message):
    try:
        proc.terminate()
        proc.wait(timeout=2)
    except Exception:
        try:
            proc.kill()
        except Exception:
            pass
    print(f"ERROR: {message}", file=sys.stderr)
    sys.exit(1)


def send(obj):
    proc.stdin.write(json.dumps(obj, separators=(",", ":")) + "\n")
    proc.stdin.flush()


def read_until(ids, timeout=30):
    deadline = time.time() + timeout
    found = {}
    while time.time() < deadline and ids - found.keys():
        line = proc.stdout.readline()
        if not line:
            break
        try:
            msg = json.loads(line)
        except Exception:
            continue
        msg_id = msg.get("id")
        if msg_id in ids:
            found[msg_id] = msg
    return found


def text_json(call_msg):
    result = call_msg.get("result") or {}
    for item in result.get("content") or []:
        if item.get("type") == "text":
            try:
                return json.loads(item.get("text") or "{}")
            except Exception as exc:
                fail(f"tools/call text content is not JSON: {exc}")
    fail("tools/call response has no text JSON content")


send(
    {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {
                "name": "agent-bridge-t6-aggregate-summary-smoke",
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

tools = {
    tool.get("name"): tool
    for tool in (messages[2].get("result") or {}).get("tools", [])
}
summary_tool = tools.get("memory_biocortex_recall_expansion_summary")
report_tool = tools.get("memory_biocortex_t6_candidate_expansion_dry_run_report")
human_review_tool = tools.get("memory_biocortex_t6_candidate_expansion_human_review_packet")
owner_decision_tool = tools.get("memory_biocortex_t6_candidate_expansion_owner_decision_record")
runtime_gate_preflight_tool = tools.get(
    "memory_biocortex_t6_candidate_expansion_runtime_gate_preflight"
)
if not summary_tool:
    fail("memory_biocortex_recall_expansion_summary missing from tools/list")
if not report_tool:
    fail("memory_biocortex_t6_candidate_expansion_dry_run_report missing from tools/list")
if not human_review_tool:
    fail("memory_biocortex_t6_candidate_expansion_human_review_packet missing from tools/list")
if not owner_decision_tool:
    fail("memory_biocortex_t6_candidate_expansion_owner_decision_record missing from tools/list")
if not runtime_gate_preflight_tool:
    fail("memory_biocortex_t6_candidate_expansion_runtime_gate_preflight missing from tools/list")

summary_props = (summary_tool.get("inputSchema") or {}).get("properties") or {}
if "include_case_rows" not in summary_props:
    fail("include_case_rows missing from recall summary schema")

send(
    {
        "jsonrpc": "2.0",
        "id": 3,
        "method": "tools/call",
        "params": {
            "name": "memory_biocortex_recall_expansion_summary",
            "arguments": {
                "query_cases": [
                    {
                        "query": "agent bridge semantic memory continuity smoke",
                        "relevant_keys": ["nonexistent:codex_smoke_relevant_key"],
                        "class_label": "mcp_smoke",
                    }
                ],
                "limit": 1,
                "neighbor_limit": 2,
                "include_case_rows": False,
            },
        },
    }
)
messages = read_until({3})
if 3 not in messages:
    fail("missing recall summary response")
if "error" in messages[3]:
    fail(f"recall summary call error: {messages[3]['error']}")
summary = text_json(messages[3])
if summary.get("schema") != "agent_bridge.memory_biocortex.recall_expansion_summary.v0":
    fail("unexpected recall summary schema")
if summary.get("input_contract", {}).get("case_rows_included") is not False:
    fail("recall summary did not declare case_rows_included=false")
if "case_rows" in summary:
    fail("recall summary leaked top-level case_rows")
if summary.get("metrics", {}).get("evaluated_count") != 1:
    fail("recall summary did not evaluate exactly one smoke case")

plan = {
    "schema": "agent_bridge.memory_biocortex_t6_candidate_expansion_dry_run_plan.v0",
    "read_only": True,
    "dry_run_plan": {
        "ready": True,
        "block_reasons": [],
        "sampling_contract": {
            "min_dry_run_cases": 1,
            "requires_less_handpicked_baseline_miss_corpus": True,
            "requires_negative_controls": True,
            "requires_trigger_projection_stratum": True,
        },
    },
    "experiment_contract": {
        "candidate_expansion_experiment_approved": False,
        "may_run_candidate_expansion_dry_run_now": False,
        "may_expand_candidate_set_now": False,
        "changes_candidate_set_now": False,
        "runtime_influence_approved": False,
        "may_change_search_order_now": False,
    },
    "input_contract": {
        "review_packet_included": False,
        "source_gate_included": False,
        "recall_expansion_summary_included": False,
        "case_rows_included": False,
        "raw_query_included": False,
        "raw_queries_included": False,
        "raw_keys_included": False,
        "content_included": False,
    },
}
send(
    {
        "jsonrpc": "2.0",
        "id": 4,
        "method": "tools/call",
        "params": {
            "name": "memory_biocortex_t6_candidate_expansion_dry_run_report",
            "arguments": {
                "candidate_expansion_dry_run_plan": plan,
                "recall_expansion_summary": summary,
                "reviewer": "mcp-smoke",
            },
        },
    }
)
messages = read_until({4})
if 4 not in messages:
    fail("missing dry-run report response")
if "error" in messages[4]:
    fail(f"dry-run report call error: {messages[4]['error']}")
report = text_json(messages[4])
if report.get("schema") != "agent_bridge.memory_biocortex_t6_candidate_expansion_dry_run_report.v0":
    fail("unexpected dry-run report schema")
if report.get("input_contract", {}).get("case_rows_included") is not False:
    fail("dry-run report did not declare case_rows_included=false")
if report.get("input_contract", {}).get("recall_expansion_summary_included") is not False:
    fail("dry-run report echoed source recall_expansion_summary")
if report.get("experiment_contract", {}).get("may_expand_candidate_set_now") is not False:
    fail("dry-run report granted candidate expansion authority")
if "case_rows" in report:
    fail("dry-run report leaked top-level case_rows")
if "recall_expansion_summary" in report:
    fail("dry-run report leaked source recall_expansion_summary")

send(
    {
        "jsonrpc": "2.0",
        "id": 5,
        "method": "tools/call",
        "params": {
            "name": "memory_biocortex_t6_candidate_expansion_human_review_packet",
            "arguments": {
                "candidate_expansion_dry_run_report": report,
                "reviewer": "mcp-smoke",
            },
        },
    }
)
messages = read_until({5})
if 5 not in messages:
    fail("missing human-review packet response")
if "error" in messages[5]:
    fail(f"human-review packet call error: {messages[5]['error']}")
human_review_packet = text_json(messages[5])
if (
    human_review_packet.get("schema")
    != "agent_bridge.memory_biocortex_t6_candidate_expansion_human_review_packet.v0"
):
    fail("unexpected human-review packet schema")
if human_review_packet.get("input_contract", {}).get("dry_run_report_included") is not False:
    fail("human-review packet echoed source dry-run report")
if (
    human_review_packet.get("review_contract", {}).get("may_expand_candidate_set_now")
    is not False
):
    fail("human-review packet granted candidate expansion authority")
if (
    human_review_packet.get("review_contract", {}).get("may_run_candidate_expansion_dry_run_now")
    is not False
):
    fail("human-review packet granted dry-run execution authority")
if "candidate_expansion_dry_run_report" in human_review_packet:
    fail("human-review packet leaked source dry-run report")
if "case_rows" in human_review_packet:
    fail("human-review packet leaked top-level case_rows")

send(
    {
        "jsonrpc": "2.0",
        "id": 6,
        "method": "tools/call",
        "params": {
            "name": "memory_biocortex_t6_candidate_expansion_owner_decision_record",
            "arguments": {
                "human_review_packet": human_review_packet,
                "owner_decision": "request_more_redacted_dry_run_evidence",
                "owner": "mcp-smoke",
                "decision_source": "synthetic:mcp-smoke",
                "reviewer": "mcp-smoke",
            },
        },
    }
)
messages = read_until({6})
if 6 not in messages:
    fail("missing owner-decision record response")
if "error" in messages[6]:
    fail(f"owner-decision record call error: {messages[6]['error']}")
owner_decision_record = text_json(messages[6])
if (
    owner_decision_record.get("schema")
    != "agent_bridge.memory_biocortex_t6_candidate_expansion_owner_decision_record.v0"
):
    fail("unexpected owner-decision record schema")
if owner_decision_record.get("input_contract", {}).get("human_review_packet_included") is not False:
    fail("owner-decision record echoed source human-review packet")
if (
    owner_decision_record.get("decision_contract", {}).get("may_prepare_candidate_expansion_design_gate")
    is not False
):
    fail("synthetic owner-decision smoke should not request the next design gate")
if (
    owner_decision_record.get("decision_contract", {}).get("may_expand_candidate_set_now")
    is not False
):
    fail("owner-decision record granted candidate expansion authority")
if (
    owner_decision_record.get("decision_contract", {}).get("may_run_candidate_expansion_dry_run_now")
    is not False
):
    fail("owner-decision record granted dry-run execution authority")
if "human_review_packet" in owner_decision_record:
    fail("owner-decision record leaked source human-review packet")
if "case_rows" in owner_decision_record:
    fail("owner-decision record leaked top-level case_rows")

send(
    {
        "jsonrpc": "2.0",
        "id": 7,
        "method": "tools/call",
        "params": {
            "name": "memory_biocortex_t6_candidate_expansion_runtime_gate_preflight",
            "arguments": {
                "owner_decision_record": owner_decision_record,
                "reviewer": "mcp-smoke",
            },
        },
    }
)
messages = read_until({7})
if 7 not in messages:
    fail("missing runtime-gate preflight response")
if "error" in messages[7]:
    fail(f"runtime-gate preflight call error: {messages[7]['error']}")
runtime_gate_preflight = text_json(messages[7])
if (
    runtime_gate_preflight.get("schema")
    != "agent_bridge.memory_biocortex_t6_candidate_expansion_runtime_gate_preflight.v0"
):
    fail("unexpected runtime-gate preflight schema")
if (
    runtime_gate_preflight.get("input_contract", {}).get("owner_decision_record_included")
    is not False
):
    fail("runtime-gate preflight echoed source owner-decision record")
if runtime_gate_preflight.get("runtime_gate_preflight", {}).get("ready") is not False:
    fail("synthetic owner-decision smoke should not make runtime-gate preflight ready")
if (
    "source_owner_decision_not_approved_for_design_gate"
    not in runtime_gate_preflight.get("runtime_gate_preflight", {}).get("block_reasons", [])
):
    fail("runtime-gate preflight did not block on missing design-gate approval")
if (
    runtime_gate_preflight.get("preflight_contract", {}).get("may_prepare_runtime_gate_design_artifact")
    is not False
):
    fail("runtime-gate preflight granted design-prep authority from synthetic evidence-request decision")
if (
    runtime_gate_preflight.get("preflight_contract", {}).get("may_expand_candidate_set_now")
    is not False
):
    fail("runtime-gate preflight granted candidate expansion authority")
if (
    runtime_gate_preflight.get("preflight_contract", {}).get("may_implement_runtime_gate_code_now")
    is not False
):
    fail("runtime-gate preflight granted runtime implementation authority")
if "owner_decision_record" in runtime_gate_preflight:
    fail("runtime-gate preflight leaked source owner-decision record")
if "case_rows" in runtime_gate_preflight:
    fail("runtime-gate preflight leaked top-level case_rows")

print(
    json.dumps(
        {
            "ok": True,
            "binary": ab_bin,
            "tools_listed": len(tools),
            "include_case_rows_schema": True,
            "summary_evaluated_count": summary["metrics"]["evaluated_count"],
            "summary_case_rows_present": "case_rows" in summary,
            "report_ready": report["dry_run_report"]["ready"],
            "report_block_reasons": report["dry_run_report"]["block_reasons"],
            "may_expand_candidate_set_now": report["experiment_contract"][
                "may_expand_candidate_set_now"
            ],
            "human_review_ready": human_review_packet["human_review_packet"]["ready"],
            "human_review_may_expand_candidate_set_now": human_review_packet[
                "review_contract"
            ]["may_expand_candidate_set_now"],
            "owner_decision_ready": owner_decision_record["owner_decision_record"]["ready"],
            "owner_decision_next_design_gate_requested": owner_decision_record[
                "decision_contract"
            ]["next_design_gate_requested"],
            "owner_decision_may_expand_candidate_set_now": owner_decision_record[
                "decision_contract"
            ]["may_expand_candidate_set_now"],
            "runtime_gate_preflight_ready": runtime_gate_preflight[
                "runtime_gate_preflight"
            ]["ready"],
            "runtime_gate_preflight_may_prepare_design": runtime_gate_preflight[
                "preflight_contract"
            ]["may_prepare_runtime_gate_design_artifact"],
            "runtime_gate_preflight_may_expand_candidate_set_now": runtime_gate_preflight[
                "preflight_contract"
            ]["may_expand_candidate_set_now"],
        },
        indent=2,
        sort_keys=True,
    )
)

proc.terminate()
try:
    proc.wait(timeout=2)
except subprocess.TimeoutExpired:
    proc.kill()
PY
