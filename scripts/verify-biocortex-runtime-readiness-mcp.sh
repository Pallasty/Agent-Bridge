#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"

tmpdir="$(mktemp -d "${TMPDIR:-/tmp}/ab-biocortex-readiness-mcp-XXXXXX")"
cleanup() {
    rm -rf "$tmpdir"
}
trap cleanup EXIT

run_with_timeout() {
    local timeout_secs="$1"
    shift
    if command -v timeout >/dev/null 2>&1; then
        timeout "$timeout_secs" "$@"
    elif command -v gtimeout >/dev/null 2>&1; then
        gtimeout "$timeout_secs" "$@"
    else
        python3 -c '
import subprocess
import sys

timeout_secs = float(sys.argv[1])
cmd = sys.argv[2:]
cmd_display = " ".join(cmd)
try:
    raise SystemExit(subprocess.run(cmd, timeout=timeout_secs).returncode)
except subprocess.TimeoutExpired:
    print(f"timeout after {timeout_secs:g}s: {cmd_display}", file=sys.stderr)
    raise SystemExit(124)
' "$timeout_secs" "$@"
    fi
}

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


def gated_batch_fixture():
    return {
        "schema": "agent_bridge.biocortex_retrieval.opt_in_gated_batch_diagnostics.v0",
        "gated_batch_diagnostics": True,
        "implementation_stage": "runtime_transition_gated_batch_diagnostics",
        "status": "completed",
        "input_contract": {
            "runtime_transition_gate_included": False,
            "runtime_influence_decision_packet_included": False,
            "requires_transition_gate_allowed": True,
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
            "transition_gate_allowed_count": 1,
            "transition_gate_blocked_count": 0,
            "store_trial_called_count": 1,
            "store_trial_adapter_allowed_count": 0,
            "baseline_completed_count": 1,
            "baseline_empty_count": 1,
            "side_signal_ok_count": 0,
            "experimental_source_count": 0,
            "actual_order_changed_count": 0,
            "calls_memory_search_count": 1,
            "default_calls_unchanged_count": 1,
        },
        "query_results": [
            {
                "transition_preflight": {
                    "transition_gate_allowed": True,
                    "blocker_count": 0,
                },
                "store_trial": {
                    "called": True,
                    "runtime_adapter_allowed": False,
                    "runtime_preflight_blocker_count": 1,
                    "baseline_completed": True,
                    "baseline_key_count": 0,
                    "side_signal_status": "not_attempted",
                    "returned_order_source": "baseline",
                    "actual_return_order_changed": False,
                },
                "calls_memory_search": True,
                "runs_biocortex": False,
                "changes_memory_search_order": False,
                "default_calls_unchanged": True,
                "raw_query": "secret readiness gated batch query",
                "raw_key": "secret_readiness_gated_batch_key",
                "content": "secret readiness gated batch content",
            }
        ],
        "safety": {
            "transition_gate_allowed_all": True,
            "transition_gate_blocked_all": False,
            "store_trial_called_all": True,
            "calls_memory_search_all": True,
            "runs_biocortex_any": False,
            "default_calls_unchanged_all": True,
            "raw_flags_all_false": True,
        },
        "boundary": {
            "gate_consumed": True,
            "calls_memory_search": True,
        },
        "calls_memory_search": True,
        "runs_biocortex": False,
        "changes_memory_search_order": False,
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


def blocked_runtime_transition_gate_fixture():
    return {
        "schema": "agent_bridge.biocortex_retrieval.opt_in_runtime_transition_gate.v0",
        "read_only": True,
        "runtime_transition_gate": True,
        "implementation_stage": "readiness_gated_runtime_transition_gate",
        "authorization_scope": "explicit_opt_in_fts_runtime_influence",
        "status": "blocked",
        "input_contract": {
            "runtime_readiness_packet_included": False,
            "raw_queries_included": False,
            "raw_keys_included": False,
            "content_included": False,
            "side_signal_raw_included": False,
            "human_decision_text_included": False,
        },
        "requested_transition": {
            "mode": "hybrid",
            "mode_authorized": False,
            "per_call_opt_in": False,
            "operator_disabled": True,
            "default_search_order_change_requested": False,
            "hybrid_retrieval_influence_requested": True,
            "semantic_retrieval_influence_requested": False,
        },
        "transition": {
            "transition_allowed": False,
            "may_call_controlled_store_trial": False,
            "may_run_runtime_adapter_for_explicit_opt_in_fts": False,
            "may_connect_ordering_behavior_for_explicit_opt_in_fts": False,
            "may_affect_only_explicitly_opted_in_fts_calls": False,
            "requires_per_call_opt_in": True,
            "must_keep_operator_disable": "AB_BIOCORTEX_RETRIEVAL_DISABLE",
            "must_return_baseline_without_per_call_opt_in": True,
            "must_fail_open_to_baseline": True,
            "must_keep_redacted_audit_only": True,
            "must_keep_baseline_candidate_recall": True,
            "may_change_default_memory_search_order": False,
            "default_influence_ready": False,
        },
        "boundary_check": {
            "runtime_transition_allowed": False,
            "blockers": [
                "requested_mode_not_authorized",
                "per_call_opt_in_missing",
                "operator_disabled",
            ],
            "this_packet_grants_new_authorization": False,
            "this_packet_calls_memory_search": False,
            "this_packet_runs_biocortex": False,
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
        "raw_query": "secret gated transition gate query",
        "raw_key": "secret_gated_transition_gate_key",
        "content": "secret gated transition gate content",
    }


def post_runtime_decision_fixture():
    decision = decision_fixture()
    decision["request_summary"].update(
        {
            "redacted_evidence_aggregate_summary_included": False,
            "post_runtime_evidence_summary_backed_review_request": True,
            "post_runtime_evidence_summary_provided": True,
            "post_runtime_evidence_summary_ready": True,
            "post_runtime_evidence_summary_review_state": "post_runtime_evidence_ready",
            "post_runtime_evidence_summary_state": "post_runtime_evidence_ready",
            "post_runtime_evidence_summary_default_influence_ready": False,
            "post_runtime_runtime_readiness_requirement_met": True,
            "post_runtime_readiness_gated_batch_evidence_ready": True,
            "post_runtime_batch_transition_gated": True,
            "post_runtime_batch_evidence_source": "runtime_transition_gated_batch_diagnostics",
            "post_runtime_evidence_summary_included": False,
        }
    )
    decision["input_contract"].update(
        {
            "accepts_post_runtime_evidence_summary_review_request": True,
            "requires_post_runtime_evidence_summary_ready_when_provided": True,
            "post_runtime_evidence_summary_included": False,
        }
    )
    decision["boundary_check"].update(
        {
            "aggregate_summary_redacted": True,
            "post_runtime_evidence_summary_backed_review_request": True,
            "post_runtime_evidence_summary_ready": True,
            "post_runtime_evidence_summary_safe_for_decision": True,
            "post_runtime_runtime_readiness_requirement_met": True,
            "post_runtime_readiness_gated_batch_evidence_ready": True,
            "post_runtime_batch_transition_gated": True,
            "post_runtime_evidence_summary_redacted": True,
        }
    )
    decision.update(
        {
            "raw_query": "secret post runtime decision query",
            "raw_key": "secret_post_runtime_decision_key",
            "content": "secret post runtime decision content",
            "human_decision_text": "secret post runtime decision human decision",
        }
    )
    return decision


def post_runtime_store_trial_fixture():
    trial = store_trial_fixture()
    trial["input_contract"].update(
        {
            "accepts_post_runtime_evidence_summary_decision_packet": True,
            "requires_post_runtime_evidence_summary_ready_when_provided": True,
            "post_runtime_evidence_summary_included": False,
        }
    )
    trial["runtime_preflight"].update(
        {
            "decision_packet_post_runtime_evidence_summary_backed": True,
            "decision_packet_post_runtime_evidence_summary_ready": True,
            "legacy_decision_packet_without_post_runtime_evidence_summary_allowed": False,
            "decision_packet_post_runtime_evidence_summary_contract_ok": True,
            "decision_packet_post_runtime_evidence_summary_redacted": True,
            "decision_packet_post_runtime_evidence_summary_safe_for_trial": True,
            "decision_packet_post_runtime_evidence_summary_state": "post_runtime_evidence_ready",
            "decision_packet_post_runtime_evidence_summary_default_influence_ready": False,
            "decision_packet_post_runtime_readiness_requirement_met": True,
            "decision_packet_post_runtime_gated_batch_evidence_ready": True,
            "decision_packet_post_runtime_batch_transition_gated": True,
        }
    )
    trial.update(
        {
            "raw_query": "secret post runtime store query",
            "raw_key": "secret_post_runtime_store_key",
            "content": "secret post runtime store content",
        }
    )
    return trial


def post_runtime_gated_batch_fixture():
    batch = gated_batch_fixture()
    batch["input_contract"].update(
        {
            "accepts_post_runtime_evidence_summary_decision_packet": True,
            "requires_post_runtime_evidence_summary_ready_when_provided": True,
            "post_runtime_evidence_summary_included": False,
        }
    )
    row = batch["query_results"][0]
    row["transition_preflight"].update(
        {
            "gate_post_runtime_evidence_summary_backed": True,
            "gate_post_runtime_evidence_summary_ready": True,
            "gate_legacy_decision_packet_without_post_runtime_evidence_summary_allowed": False,
            "gate_post_runtime_evidence_summary_state": "post_runtime_evidence_ready",
            "gate_post_runtime_batch_evidence_source": "runtime_transition_gated_batch_diagnostics",
            "gate_post_runtime_readiness_gated_batch_evidence_ready": True,
            "gate_post_runtime_batch_transition_gated": True,
            "gate_store_post_runtime_evidence_preflight_ok": True,
            "gate_batch_post_runtime_evidence_preflight_ok": True,
        }
    )
    row["store_trial"].update(
        {
            "decision_packet_post_runtime_evidence_summary_backed": True,
            "decision_packet_post_runtime_evidence_summary_ready": True,
            "legacy_decision_packet_without_post_runtime_evidence_summary_allowed": False,
            "decision_packet_post_runtime_evidence_summary_safe_for_trial": True,
            "decision_packet_post_runtime_evidence_summary_state": "post_runtime_evidence_ready",
        }
    )
    row.update(
        {
            "raw_query": "secret post runtime gated batch query",
            "raw_key": "secret_post_runtime_gated_batch_key",
            "content": "secret post runtime gated batch content",
        }
    )
    return batch


def post_runtime_readiness_packet_fixture():
    packet = runtime_readiness_packet_fixture()
    packet["input_contract"].update(
        {
            "batch_diagnostics_evidence_source": "runtime_transition_gated_batch_diagnostics",
            "batch_diagnostics_transition_gated": True,
            "accepts_post_runtime_evidence_summary_decision_packet": True,
            "requires_post_runtime_evidence_summary_ready_when_provided": True,
            "post_runtime_evidence_summary_included": False,
        }
    )
    packet["readiness"].update(
        {
            "live_order_influence_ready": False,
            "may_change_default_memory_search_order": False,
        }
    )
    packet["decision_summary"] = {
        "post_runtime_evidence_summary_backed_review_request": True,
        "post_runtime_evidence_summary_ready": True,
        "legacy_decision_packet_without_post_runtime_evidence_summary_allowed": False,
        "post_runtime_evidence_summary_safe_for_decision": True,
        "post_runtime_evidence_summary_default_influence_ready": False,
        "post_runtime_runtime_readiness_requirement_met": True,
        "post_runtime_readiness_gated_batch_evidence_ready": True,
        "post_runtime_batch_transition_gated": True,
        "post_runtime_batch_evidence_source": "runtime_transition_gated_batch_diagnostics",
        "post_runtime_evidence_summary_state": "post_runtime_evidence_ready",
    }
    packet["store_trial_summary"] = {
        "post_runtime_evidence_preflight_ok": True,
    }
    packet["batch_summary"] = {
        "evidence_source": "runtime_transition_gated_batch_diagnostics",
        "transition_gated": True,
        "transition_gate_ok": True,
        "post_runtime_evidence_preflight_ok": True,
        "transition_gate_allowed_count": 1,
        "transition_gate_blocked_count": 0,
        "store_trial_called_count": 1,
        "calls_memory_search_count": 1,
    }
    packet.update(
        {
            "raw_query": "secret post runtime readiness query",
            "raw_key": "secret_post_runtime_readiness_key",
            "content": "secret post runtime readiness content",
            "human_decision_text": "secret post runtime readiness human decision",
        }
    )
    return packet


def post_runtime_transition_gate_fixture():
    gate = blocked_runtime_transition_gate_fixture()
    gate["status"] = "transition_allowed"
    gate["requested_transition"].update(
        {
            "mode": "fts",
            "mode_authorized": True,
            "per_call_opt_in": True,
            "operator_disabled": False,
            "hybrid_retrieval_influence_requested": False,
            "semantic_retrieval_influence_requested": False,
        }
    )
    gate["readiness_summary"] = {
        "post_runtime_evidence_summary_backed": True,
        "post_runtime_evidence_summary_ready": True,
        "legacy_decision_packet_without_post_runtime_evidence_summary_allowed": False,
        "post_runtime_evidence_summary_state": "post_runtime_evidence_ready",
        "post_runtime_batch_evidence_source": "runtime_transition_gated_batch_diagnostics",
        "post_runtime_readiness_gated_batch_evidence_ready": True,
        "post_runtime_batch_transition_gated": True,
        "store_post_runtime_evidence_preflight_ok": True,
        "batch_post_runtime_evidence_preflight_ok": True,
    }
    gate["transition"].update(
        {
            "transition_allowed": True,
            "may_call_controlled_store_trial": True,
            "may_run_runtime_adapter_for_explicit_opt_in_fts": True,
            "may_connect_ordering_behavior_for_explicit_opt_in_fts": True,
            "may_affect_only_explicitly_opted_in_fts_calls": True,
        }
    )
    gate["boundary_check"].update(
        {
            "runtime_transition_allowed": True,
            "blockers": [],
        }
    )
    gate.update(
        {
            "registers_embedding_backend": False,
            "raw_query": "secret post runtime transition gate query",
            "raw_key": "secret_post_runtime_transition_gate_key",
            "content": "secret post runtime transition gate content",
        }
    )
    return gate


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
    {
        "jsonrpc": "2.0",
        "id": 6,
        "method": "tools/call",
        "params": {
            "name": "biocortex_retrieval_opt_in_gated_store_trial",
            "arguments": {
                "runtime_transition_gate": blocked_runtime_transition_gate_fixture(),
                "runtime_influence_decision_packet": decision_fixture(),
                "query": "secret gated mcp smoke query",
                "mode": "hybrid",
                "per_call_opt_in": False,
                "attempt_id": "mcp-smoke-blocked-gated-store-trial",
            },
        },
    },
    {
        "jsonrpc": "2.0",
        "id": 7,
        "method": "tools/call",
        "params": {
            "name": "biocortex_retrieval_opt_in_gated_batch_diagnostics",
            "arguments": {
                "runtime_transition_gate": blocked_runtime_transition_gate_fixture(),
                "runtime_influence_decision_packet": decision_fixture(),
                "queries": ["secret gated batch mcp smoke query"],
                "mode": "hybrid",
                "per_call_opt_in": False,
                "attempt_id": "mcp-smoke-blocked-gated-batch-diagnostics",
            },
        },
    },
    {
        "jsonrpc": "2.0",
        "id": 8,
        "method": "tools/call",
        "params": {
            "name": "biocortex_retrieval_opt_in_runtime_readiness_packet",
            "arguments": {
                "runtime_influence_decision_packet": decision_fixture(),
                "store_trial": store_trial_fixture(),
                "batch_diagnostics": gated_batch_fixture(),
                "reviewer": "verify-biocortex-runtime-readiness-mcp",
                "commit": "mcp-smoke-gated-batch-readiness",
                "forum_post_id": "mcp-smoke-gated-batch-readiness",
                "memory_key": "mcp-smoke-gated-batch-readiness",
            },
        },
    },
    {
        "jsonrpc": "2.0",
        "id": 9,
        "method": "tools/call",
        "params": {
            "name": "biocortex_retrieval_opt_in_runtime_readiness_packet",
            "arguments": {
                "runtime_influence_decision_packet": post_runtime_decision_fixture(),
                "store_trial": post_runtime_store_trial_fixture(),
                "batch_diagnostics": post_runtime_gated_batch_fixture(),
                "reviewer": "verify-biocortex-runtime-readiness-mcp",
                "commit": "mcp-smoke-post-runtime-readiness",
                "forum_post_id": "mcp-smoke-post-runtime-readiness",
                "memory_key": "mcp-smoke-post-runtime-readiness",
            },
        },
    },
    {
        "jsonrpc": "2.0",
        "id": 10,
        "method": "tools/call",
        "params": {
            "name": "biocortex_retrieval_opt_in_runtime_transition_gate",
            "arguments": {
                "runtime_readiness_packet": post_runtime_readiness_packet_fixture(),
                "mode": "fts",
                "per_call_opt_in": True,
                "reviewer": "verify-biocortex-runtime-readiness-mcp",
                "commit": "mcp-smoke-post-runtime-transition",
                "forum_post_id": "mcp-smoke-post-runtime-transition",
                "memory_key": "mcp-smoke-post-runtime-transition",
            },
        },
    },
    {
        "jsonrpc": "2.0",
        "id": 11,
        "method": "tools/call",
        "params": {
            "name": "biocortex_retrieval_opt_in_gated_store_trial",
            "arguments": {
                "runtime_transition_gate": post_runtime_transition_gate_fixture(),
                "runtime_influence_decision_packet": post_runtime_decision_fixture(),
                "query": "secret post runtime gated store mcp smoke query",
                "mode": "fts",
                "per_call_opt_in": True,
                "attempt_id": "mcp-smoke-post-runtime-gated-store-trial",
            },
        },
    },
    {
        "jsonrpc": "2.0",
        "id": 12,
        "method": "tools/call",
        "params": {
            "name": "biocortex_retrieval_opt_in_gated_batch_diagnostics",
            "arguments": {
                "runtime_transition_gate": post_runtime_transition_gate_fixture(),
                "runtime_influence_decision_packet": post_runtime_decision_fixture(),
                "queries": ["secret post runtime gated batch mcp smoke query"],
                "mode": "fts",
                "per_call_opt_in": True,
                "attempt_id": "mcp-smoke-post-runtime-gated-batch-diagnostics",
            },
        },
    },
]

with open(path, "w", encoding="utf-8") as f:
    for message in messages:
        f.write(json.dumps(message, separators=(",", ":")) + "\n")
PY

run_with_timeout "${AB_MCP_SMOKE_TIMEOUT_SECS:-180}" \
    env -u AB_BIOCORTEX_RETRIEVAL_DISABLE \
    AGENT_BRIDGE_TOOL_PROFILE="${AGENT_BRIDGE_TOOL_PROFILE:-standard}" \
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
gated_tool_name = "biocortex_retrieval_opt_in_gated_store_trial"
gated_batch_tool_name = "biocortex_retrieval_opt_in_gated_batch_diagnostics"
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
        if message.get("id") in {3, 4, 5, 6, 7, 8, 9, 10, 11, 12}:
            if message.get("error"):
                errors.append(f"tools/call error: {message['error']}")
            for item in message.get("result", {}).get("content", []):
                if isinstance(item, dict) and isinstance(item.get("text"), str):
                    call_texts[message["id"]] = item["text"]
                    break

for tool_name in [
    readiness_tool_name,
    transition_tool_name,
    gated_tool_name,
    gated_batch_tool_name,
]:
    if tool_name not in listed_tools:
        errors.append(f"{tool_name} missing from tools/list")
for message_id in [3, 4, 5, 6, 7, 8, 9, 10, 11, 12]:
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
    "secret gated transition gate query",
    "secret_gated_transition_gate_key",
    "secret gated transition gate content",
    "secret gated mcp smoke query",
    "secret gated batch mcp smoke query",
    "secret readiness gated batch query",
    "secret_readiness_gated_batch_key",
    "secret readiness gated batch content",
    "secret post runtime decision query",
    "secret_post_runtime_decision_key",
    "secret post runtime decision content",
    "secret post runtime decision human decision",
    "secret post runtime store query",
    "secret_post_runtime_store_key",
    "secret post runtime store content",
    "secret post runtime gated batch query",
    "secret_post_runtime_gated_batch_key",
    "secret post runtime gated batch content",
    "secret post runtime readiness query",
    "secret_post_runtime_readiness_key",
    "secret post runtime readiness content",
    "secret post runtime readiness human decision",
    "secret post runtime transition gate query",
    "secret_post_runtime_transition_gate_key",
    "secret post runtime transition gate content",
    "secret post runtime gated store mcp smoke query",
    "secret post runtime gated batch mcp smoke query",
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

gated_readiness_payload = json.loads(call_texts[8])
gated_readiness_expected = {
    "schema": "agent_bridge.biocortex_retrieval.opt_in_runtime_readiness_packet.v0",
    "control_plane_ready": True,
    "batch_evidence_source": "runtime_transition_gated_batch_diagnostics",
    "batch_transition_gated": True,
    "batch_gated_schema_ok": True,
    "batch_transition_gate_ok": True,
    "batch_transition_gate_allowed_count": 1,
    "batch_transition_gate_blocked_count": 0,
    "batch_store_trial_called_count": 1,
    "batch_calls_memory_search_count": 1,
    "runtime_readiness_ready": True,
    "blockers": [],
    "calls_memory_search": False,
    "runs_biocortex": False,
    "changes_memory_search_order": False,
    "default_search_order_change_allowed": False,
}
gated_readiness_actual = {
    "schema": gated_readiness_payload.get("schema"),
    "control_plane_ready": gated_readiness_payload.get("readiness", {}).get(
        "control_plane_ready"
    ),
    "batch_evidence_source": gated_readiness_payload.get("batch_summary", {}).get(
        "evidence_source"
    ),
    "batch_transition_gated": gated_readiness_payload.get("batch_summary", {}).get(
        "transition_gated"
    ),
    "batch_gated_schema_ok": gated_readiness_payload.get("batch_summary", {}).get(
        "gated_schema_ok"
    ),
    "batch_transition_gate_ok": gated_readiness_payload.get("batch_summary", {}).get(
        "transition_gate_ok"
    ),
    "batch_transition_gate_allowed_count": gated_readiness_payload.get(
        "batch_summary", {}
    ).get("transition_gate_allowed_count"),
    "batch_transition_gate_blocked_count": gated_readiness_payload.get(
        "batch_summary", {}
    ).get("transition_gate_blocked_count"),
    "batch_store_trial_called_count": gated_readiness_payload.get("batch_summary", {}).get(
        "store_trial_called_count"
    ),
    "batch_calls_memory_search_count": gated_readiness_payload.get(
        "batch_summary", {}
    ).get("calls_memory_search_count"),
    "runtime_readiness_ready": gated_readiness_payload.get("boundary_check", {}).get(
        "runtime_readiness_ready"
    ),
    "blockers": gated_readiness_payload.get("boundary_check", {}).get("blockers"),
    "calls_memory_search": gated_readiness_payload.get("calls_memory_search"),
    "runs_biocortex": gated_readiness_payload.get("runs_biocortex"),
    "changes_memory_search_order": gated_readiness_payload.get(
        "changes_memory_search_order"
    ),
    "default_search_order_change_allowed": gated_readiness_payload.get(
        "default_search_order_change_allowed"
    ),
}
if gated_readiness_actual != gated_readiness_expected:
    print("FAIL: unexpected MCP gated-batch readiness payload", file=sys.stderr)
    print(
        json.dumps(
            {"actual": gated_readiness_actual, "expected": gated_readiness_expected},
            indent=2,
        ),
        file=sys.stderr,
    )
    sys.exit(1)

post_runtime_readiness_payload = json.loads(call_texts[9])
post_runtime_readiness_expected = {
    "schema": "agent_bridge.biocortex_retrieval.opt_in_runtime_readiness_packet.v0",
    "status": "completed",
    "control_plane_ready": True,
    "post_runtime_evidence_backed": True,
    "post_runtime_evidence_ready": True,
    "legacy_post_runtime_allowed": False,
    "post_runtime_safe_for_decision": True,
    "post_runtime_readiness_requirement_met": True,
    "post_runtime_gated_batch_ready": True,
    "post_runtime_batch_transition_gated": True,
    "post_runtime_state": "post_runtime_evidence_ready",
    "store_post_runtime_preflight_ok": True,
    "batch_post_runtime_preflight_ok": True,
    "batch_evidence_source": "runtime_transition_gated_batch_diagnostics",
    "runtime_readiness_ready": True,
    "blockers": [],
    "calls_memory_search": False,
    "runs_biocortex": False,
    "changes_memory_search_order": False,
    "default_search_order_change_allowed": False,
}
post_runtime_readiness_actual = {
    "schema": post_runtime_readiness_payload.get("schema"),
    "status": post_runtime_readiness_payload.get("status"),
    "control_plane_ready": post_runtime_readiness_payload.get("readiness", {}).get(
        "control_plane_ready"
    ),
    "post_runtime_evidence_backed": post_runtime_readiness_payload.get(
        "decision_summary", {}
    ).get("post_runtime_evidence_summary_backed_review_request"),
    "post_runtime_evidence_ready": post_runtime_readiness_payload.get(
        "decision_summary", {}
    ).get("post_runtime_evidence_summary_ready"),
    "legacy_post_runtime_allowed": post_runtime_readiness_payload.get(
        "decision_summary", {}
    ).get("legacy_decision_packet_without_post_runtime_evidence_summary_allowed"),
    "post_runtime_safe_for_decision": post_runtime_readiness_payload.get(
        "decision_summary", {}
    ).get("post_runtime_evidence_summary_safe_for_decision"),
    "post_runtime_readiness_requirement_met": post_runtime_readiness_payload.get(
        "decision_summary", {}
    ).get("post_runtime_runtime_readiness_requirement_met"),
    "post_runtime_gated_batch_ready": post_runtime_readiness_payload.get(
        "decision_summary", {}
    ).get("post_runtime_readiness_gated_batch_evidence_ready"),
    "post_runtime_batch_transition_gated": post_runtime_readiness_payload.get(
        "decision_summary", {}
    ).get("post_runtime_batch_transition_gated"),
    "post_runtime_state": post_runtime_readiness_payload.get("decision_summary", {}).get(
        "post_runtime_evidence_summary_state"
    ),
    "store_post_runtime_preflight_ok": post_runtime_readiness_payload.get(
        "store_trial_summary", {}
    ).get("post_runtime_evidence_preflight_ok"),
    "batch_post_runtime_preflight_ok": post_runtime_readiness_payload.get(
        "batch_summary", {}
    ).get("post_runtime_evidence_preflight_ok"),
    "batch_evidence_source": post_runtime_readiness_payload.get("batch_summary", {}).get(
        "evidence_source"
    ),
    "runtime_readiness_ready": post_runtime_readiness_payload.get(
        "boundary_check", {}
    ).get("runtime_readiness_ready"),
    "blockers": post_runtime_readiness_payload.get("boundary_check", {}).get("blockers"),
    "calls_memory_search": post_runtime_readiness_payload.get("calls_memory_search"),
    "runs_biocortex": post_runtime_readiness_payload.get("runs_biocortex"),
    "changes_memory_search_order": post_runtime_readiness_payload.get(
        "changes_memory_search_order"
    ),
    "default_search_order_change_allowed": post_runtime_readiness_payload.get(
        "default_search_order_change_allowed"
    ),
}
if post_runtime_readiness_actual != post_runtime_readiness_expected:
    print("FAIL: unexpected MCP post-runtime readiness payload", file=sys.stderr)
    print(
        json.dumps(
            {
                "actual": post_runtime_readiness_actual,
                "expected": post_runtime_readiness_expected,
            },
            indent=2,
        ),
        file=sys.stderr,
    )
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

post_runtime_transition_payload = json.loads(call_texts[10])
post_runtime_transition_expected = {
    "schema": "agent_bridge.biocortex_retrieval.opt_in_runtime_transition_gate.v0",
    "status": "transition_allowed",
    "transition_allowed": True,
    "runtime_transition_allowed": True,
    "post_runtime_evidence_backed": True,
    "post_runtime_evidence_ready": True,
    "legacy_post_runtime_allowed": False,
    "post_runtime_state": "post_runtime_evidence_ready",
    "post_runtime_batch_evidence_source": "runtime_transition_gated_batch_diagnostics",
    "post_runtime_gated_batch_ready": True,
    "post_runtime_batch_transition_gated": True,
    "store_post_runtime_preflight_ok": True,
    "batch_post_runtime_preflight_ok": True,
    "blockers": [],
    "calls_memory_search": False,
    "runs_biocortex": False,
    "changes_memory_search_order": False,
    "default_search_order_change_allowed": False,
}
post_runtime_transition_actual = {
    "schema": post_runtime_transition_payload.get("schema"),
    "status": post_runtime_transition_payload.get("status"),
    "transition_allowed": post_runtime_transition_payload.get("transition", {}).get(
        "transition_allowed"
    ),
    "runtime_transition_allowed": post_runtime_transition_payload.get(
        "boundary_check", {}
    ).get("runtime_transition_allowed"),
    "post_runtime_evidence_backed": post_runtime_transition_payload.get(
        "readiness_summary", {}
    ).get("post_runtime_evidence_summary_backed"),
    "post_runtime_evidence_ready": post_runtime_transition_payload.get(
        "readiness_summary", {}
    ).get("post_runtime_evidence_summary_ready"),
    "legacy_post_runtime_allowed": post_runtime_transition_payload.get(
        "readiness_summary", {}
    ).get("legacy_decision_packet_without_post_runtime_evidence_summary_allowed"),
    "post_runtime_state": post_runtime_transition_payload.get("readiness_summary", {}).get(
        "post_runtime_evidence_summary_state"
    ),
    "post_runtime_batch_evidence_source": post_runtime_transition_payload.get(
        "readiness_summary", {}
    ).get("post_runtime_batch_evidence_source"),
    "post_runtime_gated_batch_ready": post_runtime_transition_payload.get(
        "readiness_summary", {}
    ).get("post_runtime_readiness_gated_batch_evidence_ready"),
    "post_runtime_batch_transition_gated": post_runtime_transition_payload.get(
        "readiness_summary", {}
    ).get("post_runtime_batch_transition_gated"),
    "store_post_runtime_preflight_ok": post_runtime_transition_payload.get(
        "readiness_summary", {}
    ).get("store_post_runtime_evidence_preflight_ok"),
    "batch_post_runtime_preflight_ok": post_runtime_transition_payload.get(
        "readiness_summary", {}
    ).get("batch_post_runtime_evidence_preflight_ok"),
    "blockers": post_runtime_transition_payload.get("boundary_check", {}).get("blockers"),
    "calls_memory_search": post_runtime_transition_payload.get("calls_memory_search"),
    "runs_biocortex": post_runtime_transition_payload.get("runs_biocortex"),
    "changes_memory_search_order": post_runtime_transition_payload.get(
        "changes_memory_search_order"
    ),
    "default_search_order_change_allowed": post_runtime_transition_payload.get(
        "default_search_order_change_allowed"
    ),
}
if post_runtime_transition_actual != post_runtime_transition_expected:
    print("FAIL: unexpected MCP post-runtime transition payload", file=sys.stderr)
    print(
        json.dumps(
            {
                "actual": post_runtime_transition_actual,
                "expected": post_runtime_transition_expected,
            },
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

gated_payload = json.loads(call_texts[6])
gated_blockers = gated_payload.get("runtime_transition_preflight", {}).get("blockers") or []
gated_required = [
    "transition_gate_status_not_allowed",
    "transition_gate_boundary_not_allowed",
    "transition_gate_boundary_has_blockers",
    "transition_gate_transition_not_allowed",
    "transition_gate_may_not_call_store_trial",
    "transition_gate_mode_not_authorized",
    "mode_not_authorized",
    "per_call_opt_in_missing",
]
gated_expected = {
    "schema": "agent_bridge.biocortex_retrieval.opt_in_gated_store_trial.v0",
    "status": "transition_gate_blocked",
    "transition_gate_allowed": False,
    "required_blockers_present": all(item in gated_blockers for item in gated_required),
    "store_trial_called": False,
    "calls_memory_search": False,
    "runs_biocortex": False,
    "changes_memory_search_order": False,
    "default_search_order_change_allowed": False,
    "default_calls_unchanged": True,
    "raw_query_included": False,
    "raw_keys_included": False,
    "content_included": False,
}
gated_actual = {
    "schema": gated_payload.get("schema"),
    "status": gated_payload.get("status"),
    "transition_gate_allowed": gated_payload.get("runtime_transition_preflight", {}).get(
        "transition_gate_allowed"
    ),
    "required_blockers_present": all(item in gated_blockers for item in gated_required),
    "store_trial_called": gated_payload.get("store_trial_called"),
    "calls_memory_search": gated_payload.get("calls_memory_search"),
    "runs_biocortex": gated_payload.get("runs_biocortex"),
    "changes_memory_search_order": gated_payload.get("changes_memory_search_order"),
    "default_search_order_change_allowed": gated_payload.get(
        "default_search_order_change_allowed"
    ),
    "default_calls_unchanged": gated_payload.get("default_calls_unchanged"),
    "raw_query_included": gated_payload.get("raw_query_included"),
    "raw_keys_included": gated_payload.get("raw_keys_included"),
    "content_included": gated_payload.get("content_included"),
}
if gated_actual != gated_expected:
    print("FAIL: unexpected MCP gated store trial blocked payload", file=sys.stderr)
    print(
        json.dumps({"actual": gated_actual, "expected": gated_expected}, indent=2),
        file=sys.stderr,
    )
    sys.exit(1)

post_runtime_gated_payload = json.loads(call_texts[11])
post_runtime_gated_expected = {
    "schema": "agent_bridge.biocortex_retrieval.opt_in_gated_store_trial.v0",
    "status": "transition_gate_consumed",
    "transition_gate_allowed": True,
    "blockers": [],
    "gate_post_runtime_evidence_backed": True,
    "gate_post_runtime_evidence_ready": True,
    "gate_legacy_post_runtime_allowed": False,
    "gate_post_runtime_state": "post_runtime_evidence_ready",
    "gate_post_runtime_batch_evidence_source": "runtime_transition_gated_batch_diagnostics",
    "gate_post_runtime_gated_batch_ready": True,
    "gate_post_runtime_batch_transition_gated": True,
    "gate_store_post_runtime_preflight_ok": True,
    "gate_batch_post_runtime_preflight_ok": True,
    "store_trial_called": True,
    "decision_packet_post_runtime_evidence_backed": True,
    "decision_packet_post_runtime_evidence_ready": True,
    "calls_memory_search": True,
    "runs_biocortex": False,
    "changes_memory_search_order": False,
    "default_search_order_change_allowed": False,
    "default_calls_unchanged": True,
    "raw_query_included": False,
    "raw_keys_included": False,
    "content_included": False,
}
post_runtime_gated_actual = {
    "schema": post_runtime_gated_payload.get("schema"),
    "status": post_runtime_gated_payload.get("status"),
    "transition_gate_allowed": post_runtime_gated_payload.get(
        "runtime_transition_preflight", {}
    ).get("transition_gate_allowed"),
    "blockers": post_runtime_gated_payload.get("runtime_transition_preflight", {}).get(
        "blockers"
    ),
    "gate_post_runtime_evidence_backed": post_runtime_gated_payload.get(
        "runtime_transition_preflight", {}
    ).get("gate_post_runtime_evidence_summary_backed"),
    "gate_post_runtime_evidence_ready": post_runtime_gated_payload.get(
        "runtime_transition_preflight", {}
    ).get("gate_post_runtime_evidence_summary_ready"),
    "gate_legacy_post_runtime_allowed": post_runtime_gated_payload.get(
        "runtime_transition_preflight", {}
    ).get("gate_legacy_decision_packet_without_post_runtime_evidence_summary_allowed"),
    "gate_post_runtime_state": post_runtime_gated_payload.get(
        "runtime_transition_preflight", {}
    ).get("gate_post_runtime_evidence_summary_state"),
    "gate_post_runtime_batch_evidence_source": post_runtime_gated_payload.get(
        "runtime_transition_preflight", {}
    ).get("gate_post_runtime_batch_evidence_source"),
    "gate_post_runtime_gated_batch_ready": post_runtime_gated_payload.get(
        "runtime_transition_preflight", {}
    ).get("gate_post_runtime_readiness_gated_batch_evidence_ready"),
    "gate_post_runtime_batch_transition_gated": post_runtime_gated_payload.get(
        "runtime_transition_preflight", {}
    ).get("gate_post_runtime_batch_transition_gated"),
    "gate_store_post_runtime_preflight_ok": post_runtime_gated_payload.get(
        "runtime_transition_preflight", {}
    ).get("gate_store_post_runtime_evidence_preflight_ok"),
    "gate_batch_post_runtime_preflight_ok": post_runtime_gated_payload.get(
        "runtime_transition_preflight", {}
    ).get("gate_batch_post_runtime_evidence_preflight_ok"),
    "store_trial_called": post_runtime_gated_payload.get("store_trial_called"),
    "decision_packet_post_runtime_evidence_backed": post_runtime_gated_payload.get(
        "store_trial_summary", {}
    ).get("decision_packet_post_runtime_evidence_summary_backed"),
    "decision_packet_post_runtime_evidence_ready": post_runtime_gated_payload.get(
        "store_trial_summary", {}
    ).get("decision_packet_post_runtime_evidence_summary_ready"),
    "calls_memory_search": post_runtime_gated_payload.get("calls_memory_search"),
    "runs_biocortex": post_runtime_gated_payload.get("runs_biocortex"),
    "changes_memory_search_order": post_runtime_gated_payload.get(
        "changes_memory_search_order"
    ),
    "default_search_order_change_allowed": post_runtime_gated_payload.get(
        "default_search_order_change_allowed"
    ),
    "default_calls_unchanged": post_runtime_gated_payload.get("default_calls_unchanged"),
    "raw_query_included": post_runtime_gated_payload.get("raw_query_included"),
    "raw_keys_included": post_runtime_gated_payload.get("raw_keys_included"),
    "content_included": post_runtime_gated_payload.get("content_included"),
}
if post_runtime_gated_actual != post_runtime_gated_expected:
    print("FAIL: unexpected MCP post-runtime gated store trial payload", file=sys.stderr)
    print(
        json.dumps(
            {
                "actual": post_runtime_gated_actual,
                "expected": post_runtime_gated_expected,
            },
            indent=2,
        ),
        file=sys.stderr,
    )
    sys.exit(1)

gated_batch_payload = json.loads(call_texts[7])
gated_batch_expected = {
    "schema": "agent_bridge.biocortex_retrieval.opt_in_gated_batch_diagnostics.v0",
    "status": "transition_gate_blocked",
    "query_count": 1,
    "transition_gate_blocked_count": 1,
    "store_trial_called_count": 0,
    "calls_memory_search_count": 0,
    "transition_gate_blocked_all": True,
    "store_trial_called_any": False,
    "calls_memory_search": False,
    "runs_biocortex": False,
    "changes_memory_search_order": False,
    "default_search_order_change_allowed": False,
    "default_calls_unchanged": True,
    "raw_queries_included": False,
    "raw_keys_included": False,
    "content_included": False,
}
gated_batch_actual = {
    "schema": gated_batch_payload.get("schema"),
    "status": gated_batch_payload.get("status"),
    "query_count": gated_batch_payload.get("summary", {}).get("query_count"),
    "transition_gate_blocked_count": gated_batch_payload.get("summary", {}).get(
        "transition_gate_blocked_count"
    ),
    "store_trial_called_count": gated_batch_payload.get("summary", {}).get(
        "store_trial_called_count"
    ),
    "calls_memory_search_count": gated_batch_payload.get("summary", {}).get(
        "calls_memory_search_count"
    ),
    "transition_gate_blocked_all": gated_batch_payload.get("safety", {}).get(
        "transition_gate_blocked_all"
    ),
    "store_trial_called_any": gated_batch_payload.get("safety", {}).get(
        "store_trial_called_any"
    ),
    "calls_memory_search": gated_batch_payload.get("calls_memory_search"),
    "runs_biocortex": gated_batch_payload.get("runs_biocortex"),
    "changes_memory_search_order": gated_batch_payload.get("changes_memory_search_order"),
    "default_search_order_change_allowed": gated_batch_payload.get(
        "default_search_order_change_allowed"
    ),
    "default_calls_unchanged": gated_batch_payload.get("default_calls_unchanged"),
    "raw_queries_included": gated_batch_payload.get("raw_queries_included"),
    "raw_keys_included": gated_batch_payload.get("raw_keys_included"),
    "content_included": gated_batch_payload.get("content_included"),
}
if gated_batch_actual != gated_batch_expected:
    print("FAIL: unexpected MCP gated batch diagnostics blocked payload", file=sys.stderr)
    print(
        json.dumps(
            {"actual": gated_batch_actual, "expected": gated_batch_expected},
            indent=2,
        ),
        file=sys.stderr,
    )
    sys.exit(1)

post_runtime_gated_batch_payload = json.loads(call_texts[12])
post_runtime_gated_batch_first = (
    post_runtime_gated_batch_payload.get("query_results") or [{}]
)[0]
post_runtime_gated_batch_expected = {
    "schema": "agent_bridge.biocortex_retrieval.opt_in_gated_batch_diagnostics.v0",
    "status": "completed",
    "query_count": 1,
    "transition_gate_allowed_count": 1,
    "transition_gate_blocked_count": 0,
    "store_trial_called_count": 1,
    "calls_memory_search_count": 1,
    "transition_gate_allowed_all": True,
    "store_trial_called_all": True,
    "calls_memory_search_all": True,
    "first_transition_gate_allowed": True,
    "first_gate_post_runtime_evidence_backed": True,
    "first_gate_post_runtime_evidence_ready": True,
    "first_gate_post_runtime_state": "post_runtime_evidence_ready",
    "first_gate_post_runtime_batch_evidence_source": "runtime_transition_gated_batch_diagnostics",
    "first_gate_store_post_runtime_preflight_ok": True,
    "first_gate_batch_post_runtime_preflight_ok": True,
    "first_store_trial_called": True,
    "first_decision_packet_post_runtime_evidence_backed": True,
    "first_decision_packet_post_runtime_evidence_ready": True,
    "calls_memory_search": True,
    "runs_biocortex": False,
    "changes_memory_search_order": False,
    "default_search_order_change_allowed": False,
    "default_calls_unchanged": True,
    "raw_queries_included": False,
    "raw_keys_included": False,
    "content_included": False,
}
post_runtime_gated_batch_actual = {
    "schema": post_runtime_gated_batch_payload.get("schema"),
    "status": post_runtime_gated_batch_payload.get("status"),
    "query_count": post_runtime_gated_batch_payload.get("summary", {}).get("query_count"),
    "transition_gate_allowed_count": post_runtime_gated_batch_payload.get(
        "summary", {}
    ).get("transition_gate_allowed_count"),
    "transition_gate_blocked_count": post_runtime_gated_batch_payload.get(
        "summary", {}
    ).get("transition_gate_blocked_count"),
    "store_trial_called_count": post_runtime_gated_batch_payload.get("summary", {}).get(
        "store_trial_called_count"
    ),
    "calls_memory_search_count": post_runtime_gated_batch_payload.get(
        "summary", {}
    ).get("calls_memory_search_count"),
    "transition_gate_allowed_all": post_runtime_gated_batch_payload.get("safety", {}).get(
        "transition_gate_allowed_all"
    ),
    "store_trial_called_all": post_runtime_gated_batch_payload.get("safety", {}).get(
        "store_trial_called_all"
    ),
    "calls_memory_search_all": post_runtime_gated_batch_payload.get("safety", {}).get(
        "calls_memory_search_all"
    ),
    "first_transition_gate_allowed": post_runtime_gated_batch_first.get(
        "transition_preflight", {}
    ).get("transition_gate_allowed"),
    "first_gate_post_runtime_evidence_backed": post_runtime_gated_batch_first.get(
        "transition_preflight", {}
    ).get("gate_post_runtime_evidence_summary_backed"),
    "first_gate_post_runtime_evidence_ready": post_runtime_gated_batch_first.get(
        "transition_preflight", {}
    ).get("gate_post_runtime_evidence_summary_ready"),
    "first_gate_post_runtime_state": post_runtime_gated_batch_first.get(
        "transition_preflight", {}
    ).get("gate_post_runtime_evidence_summary_state"),
    "first_gate_post_runtime_batch_evidence_source": post_runtime_gated_batch_first.get(
        "transition_preflight", {}
    ).get("gate_post_runtime_batch_evidence_source"),
    "first_gate_store_post_runtime_preflight_ok": post_runtime_gated_batch_first.get(
        "transition_preflight", {}
    ).get("gate_store_post_runtime_evidence_preflight_ok"),
    "first_gate_batch_post_runtime_preflight_ok": post_runtime_gated_batch_first.get(
        "transition_preflight", {}
    ).get("gate_batch_post_runtime_evidence_preflight_ok"),
    "first_store_trial_called": post_runtime_gated_batch_first.get("store_trial", {}).get(
        "called"
    ),
    "first_decision_packet_post_runtime_evidence_backed": post_runtime_gated_batch_first.get(
        "store_trial", {}
    ).get("decision_packet_post_runtime_evidence_summary_backed"),
    "first_decision_packet_post_runtime_evidence_ready": post_runtime_gated_batch_first.get(
        "store_trial", {}
    ).get("decision_packet_post_runtime_evidence_summary_ready"),
    "calls_memory_search": post_runtime_gated_batch_payload.get("calls_memory_search"),
    "runs_biocortex": post_runtime_gated_batch_payload.get("runs_biocortex"),
    "changes_memory_search_order": post_runtime_gated_batch_payload.get(
        "changes_memory_search_order"
    ),
    "default_search_order_change_allowed": post_runtime_gated_batch_payload.get(
        "default_search_order_change_allowed"
    ),
    "default_calls_unchanged": post_runtime_gated_batch_payload.get(
        "default_calls_unchanged"
    ),
    "raw_queries_included": post_runtime_gated_batch_payload.get("raw_queries_included"),
    "raw_keys_included": post_runtime_gated_batch_payload.get("raw_keys_included"),
    "content_included": post_runtime_gated_batch_payload.get("content_included"),
}
if post_runtime_gated_batch_actual != post_runtime_gated_batch_expected:
    print(
        "FAIL: unexpected MCP post-runtime gated batch diagnostics payload",
        file=sys.stderr,
    )
    print(
        json.dumps(
            {
                "actual": post_runtime_gated_batch_actual,
                "expected": post_runtime_gated_batch_expected,
            },
            indent=2,
        ),
        file=sys.stderr,
    )
    sys.exit(1)

print(
    "OK: BioCortex runtime readiness + transition + gated store/batch + post-runtime evidence MCP tools/list and tools/call smoke passed "
    f"(tools={len(listed_tools)})"
)
PY
