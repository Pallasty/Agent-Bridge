#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"

tmpdir="$(mktemp -d "${TMPDIR:-/tmp}/ab-biocortex-readiness-mcp-XXXXXX")"
cleanup() {
    rm -rf "$tmpdir"
}
trap cleanup EXIT

input_jsonl="$tmpdir/in.jsonl"
output_jsonl="$tmpdir/out.jsonl"
stderr_log="$tmpdir/stderr.log"

python3 - <<'PY' "$input_jsonl"
import json
import sys

path = sys.argv[1]


def decision_fixture():
    return {
        "schema": "agent_bridge.biocortex_retrieval.opt_in_runtime_influence_decision_packet.v0",
        "read_only": True,
        "runtime_influence_decision_consumer": True,
        "authorization_scope": "explicit_opt_in_fts_runtime_influence",
        "request_summary": {
            "aggregate_backed_review_request": True,
            "redacted_evidence_aggregate_ready": True,
            "aggregate_review_evidence_state": "redacted_aggregate_ready",
            "aggregate_default_influence_ready": False,
            "default_influence_ready": False,
            "aggregate_human_review_required": True,
        },
        "input_contract": {
            "runtime_influence_decision_included": False,
            "runtime_influence_review_request_included": False,
            "redacted_evidence_aggregate_included": False,
            "raw_query_included": False,
            "raw_keys_included": False,
            "content_included": False,
            "human_decision_text_included": False,
        },
        "boundary_check": {
            "runtime_influence_authorized": True,
            "aggregate_backed_review_request": True,
            "aggregate_review_evidence_ready": True,
            "aggregate_safe_for_decision": True,
            "blockers": [],
        },
        "approval_state": "runtime_influence_review_authorized",
        "authorization_state": "authorized_for_explicit_opt_in_fts_runtime_influence",
        "runtime_adapter_approved": True,
        "ordering_behavior_connection_authorized": True,
        "default_search_order_change_allowed": False,
        "default_calls_unchanged": True,
        "calls_memory_search": False,
        "runs_biocortex": False,
        "changes_memory_search_order": False,
        "ordering_behavior_connected": False,
        "raw_query": "secret readiness decision query",
        "raw_key": "secret_readiness_decision_key",
        "content": "secret readiness decision content",
        "human_decision_text": "secret readiness human decision",
    }


def store_trial_fixture():
    return {
        "schema": "agent_bridge.biocortex_retrieval.opt_in_store_trial.v0",
        "read_only": True,
        "store_trial": True,
        "status": "completed",
        "input_contract": {
            "accepts_aggregate_backed_decision_packet": True,
            "requires_aggregate_ready_when_provided": True,
            "redacted_evidence_aggregate_included": False,
            "aggregate_evidence_summary_included": False,
            "raw_query_included": False,
            "raw_keys_included": False,
            "content_included": False,
            "side_signal_raw_included": False,
        },
        "runtime_preflight": {
            "decision_packet_authorized": True,
            "decision_packet_aggregate_backed": True,
            "decision_packet_aggregate_review_evidence_ready": True,
            "legacy_decision_packet_without_aggregate_allowed": False,
            "decision_packet_aggregate_safe_for_trial": True,
            "adapter_allowed": False,
            "blockers": ["baseline_empty"],
        },
        "baseline_order": {"completed": True, "key_count": 0},
        "side_signal": {"attempted": False, "status": "not_attempted"},
        "returned_order": {"source": "baseline", "actual_return_order_changed": False},
        "default_search_order_change_allowed": False,
        "default_calls_unchanged": True,
        "changes_memory_search_order": False,
        "raw_query_included": False,
        "raw_keys_included": False,
        "content_included": False,
        "side_signal_raw_included": False,
        "raw_query": "secret readiness store query",
        "raw_key": "secret_readiness_store_key",
        "content": "secret readiness store content",
    }


def batch_fixture():
    return {
        "schema": "agent_bridge.biocortex_retrieval.opt_in_batch_diagnostics.v0",
        "read_only": True,
        "batch_diagnostics": True,
        "input_contract": {
            "accepts_aggregate_backed_decision_packet": True,
            "requires_aggregate_ready_when_provided": True,
            "redacted_evidence_aggregate_included": False,
            "aggregate_evidence_summary_included": False,
            "raw_queries_included": False,
            "raw_keys_included": False,
            "content_included": False,
            "side_signal_raw_included": False,
        },
        "summary": {
            "query_count": 1,
            "baseline_completed_count": 1,
            "baseline_empty_count": 1,
            "adapter_allowed_count": 0,
            "side_signal_ok_count": 0,
            "experimental_source_count": 0,
            "actual_order_changed_count": 0,
        },
        "query_results": [
            {
                "preflight": {
                    "decision_packet_authorized": True,
                    "decision_packet_aggregate_backed": True,
                    "decision_packet_aggregate_review_evidence_ready": True,
                    "legacy_decision_packet_without_aggregate_allowed": False,
                    "decision_packet_aggregate_safe_for_trial": True,
                    "adapter_allowed": False,
                    "blocker_count": 1,
                },
                "baseline": {"key_count": 0},
                "raw_query": "secret readiness batch query",
                "raw_key": "secret_readiness_batch_key",
                "content": "secret readiness batch content",
            }
        ],
        "safety": {
            "raw_flags_all_false": True,
            "default_calls_unchanged_all": True,
        },
        "default_search_order_change_allowed": False,
        "default_calls_unchanged": True,
        "raw_queries_included": False,
        "raw_keys_included": False,
        "content_included": False,
        "side_signal_raw_included": False,
    }


def runtime_readiness_packet_fixture():
    return {
        "schema": "agent_bridge.biocortex_retrieval.opt_in_runtime_readiness_packet.v0",
        "read_only": True,
        "runtime_readiness_packet": True,
        "implementation_stage": "controlled_opt_in_runtime_readiness_packet",
        "authorization_scope": "explicit_opt_in_fts_runtime_influence",
        "status": "completed",
        "input_contract": {
            "runtime_influence_decision_packet_included": False,
            "store_trial_included": False,
            "batch_diagnostics_included": False,
            "raw_queries_included": False,
            "raw_keys_included": False,
            "content_included": False,
            "side_signal_raw_included": False,
            "human_decision_text_included": False,
        },
        "readiness": {
            "control_plane_ready": True,
            "may_accept_controlled_explicit_opt_in_fts_calls": True,
            "live_probe_state": "control_plane_ready_no_live_candidates",
            "live_probe_has_candidates": False,
            "live_order_influence_ready": False,
            "default_influence_ready": False,
            "may_change_default_memory_search_order": False,
        },
        "boundary_check": {
            "runtime_readiness_ready": True,
            "blockers": [],
            "requires_per_call_opt_in": True,
            "requires_operator_disable_absent": True,
            "requires_fail_open_to_baseline": True,
            "requires_redacted_audit_only": True,
            "requires_baseline_candidate_recall": True,
            "this_packet_grants_new_authorization": False,
            "this_packet_changes_return_order": False,
            "this_packet_allows_default_search_order_change": False,
        },
        "approval_writes_allowed": False,
        "writes_approval": False,
        "calls_memory_search": False,
        "runs_biocortex": False,
        "registers_embedding_backend": False,
        "changes_memory_search_order": False,
        "default_search_order_change_allowed": False,
        "default_calls_unchanged": True,
        "raw_queries_included": False,
        "raw_keys_included": False,
        "content_included": False,
        "side_signal_raw_included": False,
        "human_decision_text_included": False,
        "raw_query": "secret transition readiness query",
        "raw_key": "secret_transition_readiness_key",
        "content": "secret transition readiness content",
        "human_decision_text": "secret transition human decision",
    }


messages = [
    {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {
                "name": "verify-biocortex-runtime-readiness-mcp",
                "version": "1",
            },
        },
    },
    {"jsonrpc": "2.0", "method": "notifications/initialized"},
    {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
    {
        "jsonrpc": "2.0",
        "id": 3,
        "method": "tools/call",
        "params": {
            "name": "biocortex_retrieval_opt_in_runtime_readiness_packet",
            "arguments": {
                "runtime_influence_decision_packet": decision_fixture(),
                "store_trial": store_trial_fixture(),
                "batch_diagnostics": batch_fixture(),
                "reviewer": "verify-biocortex-runtime-readiness-mcp",
                "commit": "mcp-smoke",
                "forum_post_id": "mcp-smoke",
                "memory_key": "mcp-smoke",
            },
        },
    },
    {
        "jsonrpc": "2.0",
        "id": 4,
        "method": "tools/call",
        "params": {
            "name": "biocortex_retrieval_opt_in_runtime_transition_gate",
            "arguments": {
                "runtime_readiness_packet": runtime_readiness_packet_fixture(),
                "mode": "fts",
                "per_call_opt_in": True,
                "reviewer": "verify-biocortex-runtime-readiness-mcp",
                "commit": "mcp-smoke",
                "forum_post_id": "mcp-smoke",
                "memory_key": "mcp-smoke",
            },
        },
    },
    {
        "jsonrpc": "2.0",
        "id": 5,
        "method": "tools/call",
        "params": {
            "name": "biocortex_retrieval_opt_in_runtime_transition_gate",
            "arguments": {
                "runtime_readiness_packet": runtime_readiness_packet_fixture(),
                "mode": "hybrid",
                "operator_disabled": True,
            },
        },
    },
]

with open(path, "w", encoding="utf-8") as f:
    for message in messages:
        f.write(json.dumps(message, separators=(",", ":")) + "\n")
PY

timeout "${AB_MCP_SMOKE_TIMEOUT_SECS:-180}" \
    env AGENT_BRIDGE_TOOL_PROFILE="${AGENT_BRIDGE_TOOL_PROFILE:-standard}" \
    cargo run -q -p ab-bridge --no-default-features -- mcp \
    <"$input_jsonl" >"$output_jsonl" 2>"$stderr_log" || {
        echo "FAIL: MCP smoke command failed" >&2
        tail -200 "$stderr_log" >&2 || true
        exit 1
    }

python3 - <<'PY' "$output_jsonl" "$stderr_log"
import json
import sys

output_path, stderr_path = sys.argv[1:3]
readiness_tool_name = "biocortex_retrieval_opt_in_runtime_readiness_packet"
transition_tool_name = "biocortex_retrieval_opt_in_runtime_transition_gate"
listed_tools = []
call_texts = {}
errors = []

with open(output_path, encoding="utf-8", errors="replace") as f:
    for line in f:
        line = line.strip()
        if not line:
            continue
        try:
            message = json.loads(line)
        except json.JSONDecodeError:
            continue
        if message.get("id") == 2:
            if message.get("error"):
                errors.append(f"tools/list error: {message['error']}")
            listed_tools = [
                tool.get("name")
                for tool in message.get("result", {}).get("tools", [])
                if isinstance(tool, dict)
            ]
        if message.get("id") in {3, 4, 5}:
            if message.get("error"):
                errors.append(f"tools/call error: {message['error']}")
            for item in message.get("result", {}).get("content", []):
                if isinstance(item, dict) and isinstance(item.get("text"), str):
                    call_texts[message["id"]] = item["text"]
                    break

for tool_name in [readiness_tool_name, transition_tool_name]:
    if tool_name not in listed_tools:
        errors.append(f"{tool_name} missing from tools/list")
for message_id in [3, 4, 5]:
    if message_id not in call_texts:
        errors.append(f"missing tools/call text result for id={message_id}")
if errors:
    print("FAIL: " + "; ".join(errors), file=sys.stderr)
    print(open(stderr_path, encoding="utf-8", errors="replace").read()[-4000:], file=sys.stderr)
    sys.exit(1)

for forbidden in [
    "secret readiness decision query",
    "secret_readiness_decision_key",
    "secret readiness decision content",
    "secret readiness human decision",
    "secret readiness store query",
    "secret_readiness_store_key",
    "secret readiness store content",
    "secret readiness batch query",
    "secret_readiness_batch_key",
    "secret readiness batch content",
    "secret transition readiness query",
    "secret_transition_readiness_key",
    "secret transition readiness content",
    "secret transition human decision",
]:
    for message_id, call_text in call_texts.items():
        if forbidden in call_text:
            print(f"FAIL: MCP output id={message_id} leaked {forbidden}", file=sys.stderr)
            sys.exit(1)

payload = json.loads(call_texts[3])
expected = {
    "schema": "agent_bridge.biocortex_retrieval.opt_in_runtime_readiness_packet.v0",
    "read_only": True,
    "runtime_readiness_packet": True,
    "control_plane_ready": True,
    "live_probe_state": "control_plane_ready_no_live_candidates",
    "may_accept_controlled_explicit_opt_in_fts_calls": True,
    "runtime_readiness_ready": True,
    "blockers": [],
    "calls_memory_search": False,
    "runs_biocortex": False,
    "changes_memory_search_order": False,
    "default_search_order_change_allowed": False,
}
actual = {
    "schema": payload.get("schema"),
    "read_only": payload.get("read_only"),
    "runtime_readiness_packet": payload.get("runtime_readiness_packet"),
    "control_plane_ready": payload.get("readiness", {}).get("control_plane_ready"),
    "live_probe_state": payload.get("readiness", {}).get("live_probe_state"),
    "may_accept_controlled_explicit_opt_in_fts_calls": payload.get("readiness", {}).get(
        "may_accept_controlled_explicit_opt_in_fts_calls"
    ),
    "runtime_readiness_ready": payload.get("boundary_check", {}).get("runtime_readiness_ready"),
    "blockers": payload.get("boundary_check", {}).get("blockers"),
    "calls_memory_search": payload.get("calls_memory_search"),
    "runs_biocortex": payload.get("runs_biocortex"),
    "changes_memory_search_order": payload.get("changes_memory_search_order"),
    "default_search_order_change_allowed": payload.get("default_search_order_change_allowed"),
}
if actual != expected:
    print("FAIL: unexpected MCP readiness payload", file=sys.stderr)
    print(json.dumps({"actual": actual, "expected": expected}, indent=2), file=sys.stderr)
    sys.exit(1)

transition_payload = json.loads(call_texts[4])
transition_expected = {
    "schema": "agent_bridge.biocortex_retrieval.opt_in_runtime_transition_gate.v0",
    "read_only": True,
    "runtime_transition_gate": True,
    "status": "transition_allowed",
    "mode": "fts",
    "mode_authorized": True,
    "per_call_opt_in": True,
    "operator_disabled": False,
    "transition_allowed": True,
    "may_run_runtime_adapter_for_explicit_opt_in_fts": True,
    "runtime_transition_allowed": True,
    "blockers": [],
    "calls_memory_search": False,
    "runs_biocortex": False,
    "changes_memory_search_order": False,
    "default_search_order_change_allowed": False,
}
transition_actual = {
    "schema": transition_payload.get("schema"),
    "read_only": transition_payload.get("read_only"),
    "runtime_transition_gate": transition_payload.get("runtime_transition_gate"),
    "status": transition_payload.get("status"),
    "mode": transition_payload.get("requested_transition", {}).get("mode"),
    "mode_authorized": transition_payload.get("requested_transition", {}).get("mode_authorized"),
    "per_call_opt_in": transition_payload.get("requested_transition", {}).get("per_call_opt_in"),
    "operator_disabled": transition_payload.get("requested_transition", {}).get("operator_disabled"),
    "transition_allowed": transition_payload.get("transition", {}).get("transition_allowed"),
    "may_run_runtime_adapter_for_explicit_opt_in_fts": transition_payload.get("transition", {}).get(
        "may_run_runtime_adapter_for_explicit_opt_in_fts"
    ),
    "runtime_transition_allowed": transition_payload.get("boundary_check", {}).get(
        "runtime_transition_allowed"
    ),
    "blockers": transition_payload.get("boundary_check", {}).get("blockers"),
    "calls_memory_search": transition_payload.get("calls_memory_search"),
    "runs_biocortex": transition_payload.get("runs_biocortex"),
    "changes_memory_search_order": transition_payload.get("changes_memory_search_order"),
    "default_search_order_change_allowed": transition_payload.get(
        "default_search_order_change_allowed"
    ),
}
if transition_actual != transition_expected:
    print("FAIL: unexpected MCP transition allowed payload", file=sys.stderr)
    print(
        json.dumps(
            {"actual": transition_actual, "expected": transition_expected},
            indent=2,
        ),
        file=sys.stderr,
    )
    sys.exit(1)

blocked_payload = json.loads(call_texts[5])
blocked_blockers = blocked_payload.get("boundary_check", {}).get("blockers") or []
blocked_required = [
    "requested_mode_not_authorized",
    "per_call_opt_in_missing",
    "operator_disabled",
]
blocked_expected = {
    "schema": "agent_bridge.biocortex_retrieval.opt_in_runtime_transition_gate.v0",
    "status": "blocked",
    "mode": "hybrid",
    "mode_authorized": False,
    "per_call_opt_in": False,
    "operator_disabled": True,
    "hybrid_requested": True,
    "transition_allowed": False,
    "runtime_transition_allowed": False,
    "required_blockers_present": all(item in blocked_blockers for item in blocked_required),
    "calls_memory_search": False,
    "runs_biocortex": False,
    "changes_memory_search_order": False,
    "default_search_order_change_allowed": False,
}
blocked_actual = {
    "schema": blocked_payload.get("schema"),
    "status": blocked_payload.get("status"),
    "mode": blocked_payload.get("requested_transition", {}).get("mode"),
    "mode_authorized": blocked_payload.get("requested_transition", {}).get("mode_authorized"),
    "per_call_opt_in": blocked_payload.get("requested_transition", {}).get("per_call_opt_in"),
    "operator_disabled": blocked_payload.get("requested_transition", {}).get("operator_disabled"),
    "hybrid_requested": blocked_payload.get("requested_transition", {}).get(
        "hybrid_retrieval_influence_requested"
    ),
    "transition_allowed": blocked_payload.get("transition", {}).get("transition_allowed"),
    "runtime_transition_allowed": blocked_payload.get("boundary_check", {}).get(
        "runtime_transition_allowed"
    ),
    "required_blockers_present": all(item in blocked_blockers for item in blocked_required),
    "calls_memory_search": blocked_payload.get("calls_memory_search"),
    "runs_biocortex": blocked_payload.get("runs_biocortex"),
    "changes_memory_search_order": blocked_payload.get("changes_memory_search_order"),
    "default_search_order_change_allowed": blocked_payload.get(
        "default_search_order_change_allowed"
    ),
}
if blocked_actual != blocked_expected:
    print("FAIL: unexpected MCP transition blocked payload", file=sys.stderr)
    print(
        json.dumps({"actual": blocked_actual, "expected": blocked_expected}, indent=2),
        file=sys.stderr,
    )
    sys.exit(1)

print(
    "OK: BioCortex runtime readiness + transition MCP tools/list and tools/call smoke passed "
    f"(tools={len(listed_tools)})"
)
PY
