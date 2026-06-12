#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"

biocortex_rs="${AB_BIOCORTEX_RS:-${BIOCORTEX_RS:-}}"
if [ -z "$biocortex_rs" ]; then
    for candidate in \
        "$repo_root/../biocortex-rs" \
        /Data/CascadeProjects/biocortex-rs \
        /Programs/Users/Pallasting/Documents/CascadeProjects/biocortex-rs
    do
        if [ -f "$candidate/Cargo.toml" ]; then
            biocortex_rs="$candidate"
            break
        fi
    done
fi

if [ -z "$biocortex_rs" ] || [ ! -f "$biocortex_rs/Cargo.toml" ]; then
    echo "Could not find biocortex-rs checkout. Set AB_BIOCORTEX_RS=/path/to/biocortex-rs." >&2
    exit 2
fi

tmpdir="$(mktemp -d "${TMPDIR:-/tmp}/ab-biocortex-retrieval-verify-XXXXXX")"
cleanup() {
    rm -rf "$tmpdir"
}
trap cleanup EXIT

run() {
    printf '\n==> %s\n' "$*" >&2
    "$@"
}

jq -e '
    .schema == "agent_bridge.biocortex_retrieval.runtime_approval_packet_template.v0"
    and .approval_state == "not_approved"
    and .default_decision == "keep_shadow_only"
    and .runtime_adapter_approved == false
    and .writes_approval == false
    and .approval_writes_allowed == false
    and .default_search_order_change_allowed == false
    and .requires_separate_human_approval == true
    and .approval_model.agent_technical_attestation_required == true
    and .approval_model.human_authorization_required == true
    and .approval_model.agent_attestation_can_replace_human_authorization == false
    and .agent_technical_attestation_required.can_authorize_runtime_influence == false
    and .human_authorization_required.status == "not_authorized"
    and .human_authorization_required.can_be_replaced_by_agent_attestation == false
' docs/design/fixtures/biocortex-retrieval-runtime-approval-packet-template.json >/dev/null

contract_doc="docs/design/BIOCORTEX_RETRIEVAL_DEFAULT_INFLUENCE_CONTRACT_2026_06_11.md"
grep -q '"runtime_adapter_approved": false' "$contract_doc"
grep -q '"default_search_order_change_allowed": false' "$contract_doc"
grep -q 'SqliteStore::memory_search' "$contract_doc"
grep -q 'SqliteStore::memory_search_hybrid' "$contract_doc"
grep -q 'SqliteStore::memory_search_semantic' "$contract_doc"
grep -q 'return baseline list' "$contract_doc"
grep -q 'Authorization for one mode does not imply authorization for another mode' "$contract_doc"

opt_in_plan="docs/design/fixtures/biocortex-retrieval-opt-in-experiment-plan-2026-06-11.json"
jq -e '
    .schema == "agent_bridge.biocortex_retrieval.opt_in_experiment_plan.v0"
    and .status == "store_opt_in_runtime_adapter_connection_implemented"
    and .approval_state == "opt_in_implementation_authorized"
    and .runtime_adapter_approved == false
    and .default_search_order_change_allowed == false
    and .implementation_allowed == true
    and .gate_skeleton_implemented == true
    and .audit_shape_implemented == true
    and .read_only_status_surface_implemented == true
    and .store_contract_implemented == true
    and .dry_run_planner_implemented == true
    and .review_packet_consumer_implemented == true
    and .execution_packet_contract_implemented == true
    and .runtime_trial_implemented == true
    and .runtime_trial_review_packet_implemented == true
    and .authorization_request_runtime_trial_review_evidence_implemented == true
    and .order_diff_packet_implemented == true
    and .authorization_request_order_diff_evidence_implemented == true
    and .redacted_order_artifact_implemented == true
    and .authorization_request_redacted_order_artifact_evidence_implemented == true
    and .store_opt_in_search_wrapper_implemented == true
    and .authorization_decision_consumer_implemented == true
    and .post_implementation_review_gate_implemented == true
    and .runtime_influence_review_request_implemented == true
    and .runtime_influence_decision_packet_implemented == true
    and .store_opt_in_order_connection_implemented == true
    and .store_opt_in_runtime_adapter_connection_implemented == true
    and .ordering_behavior_connected == false
    and .explicit_opt_in_fts_ordering_behavior_connected == true
    and .explicit_opt_in_fts_runtime_adapter_connected == true
    and .requested_human_authorization_scope == "opt_in_experiment"
    and .requested_default_influence_scope == "none"
    and .default_memory_search_unchanged == true
    and .experiment.mode == "fts_only"
    and .experiment.affected_call_site.function == "SqliteStore::memory_search"
    and any(.experiment.unaffected_call_sites[]; .function == "SqliteStore::memory_search_hybrid" and .status == "not_authorized_not_modified")
    and any(.experiment.unaffected_call_sites[]; .function == "SqliteStore::memory_search_semantic" and .status == "not_authorized_not_modified")
    and .proposed_gates.shadow_enable_is_not_ordering_authorization == true
    and .implemented_gate_skeleton.schema == "agent_bridge.biocortex_retrieval.opt_in_gate.v0"
    and .implemented_gate_skeleton.feature == "biocortex-retrieval-opt-in"
    and .implemented_gate_skeleton.runtime_enable_env == "AB_BIOCORTEX_RETRIEVAL_OPT_IN"
    and .implemented_gate_skeleton.operator_disable_env == "AB_BIOCORTEX_RETRIEVAL_DISABLE"
    and .implemented_gate_skeleton.ordering_behavior_connected == false
    and .implemented_gate_skeleton.may_change_search_order_now == false
    and .implemented_audit_shape.schema == "agent_bridge.biocortex_retrieval.opt_in_call_audit.v0"
    and .implemented_audit_shape.implementation_stage == "audit_shape_only"
    and .implemented_audit_shape.per_call_opt_in_source == "explicit_call_argument_reserved"
    and .implemented_audit_shape.raw_keys_included == false
    and .implemented_audit_shape.content_included == false
    and .implemented_audit_shape.experimental_order_available == false
    and .implemented_audit_shape.returned_order_source == "baseline"
    and .implemented_audit_shape.fallback_reason_required == true
    and .implemented_audit_shape.hybrid_and_semantic_authorized == false
    and .implemented_audit_shape.ordering_behavior_connected == false
    and .implemented_audit_shape.may_change_search_order_now == false
    and .implemented_status_surface.cli == "agent-bridge bio-cortex retrieval-opt-in-status"
    and .implemented_status_surface.mcp_tool == "biocortex_retrieval_opt_in_status"
    and .implemented_status_surface.schema == "agent_bridge.biocortex_retrieval.opt_in_call_audit.v0"
    and .implemented_status_surface.read_only == true
    and .implemented_status_surface.calls_memory_search == false
    and .implemented_status_surface.runs_biocortex == false
    and .implemented_status_surface.raw_keys_included == false
    and .implemented_status_surface.content_included == false
    and .implemented_status_surface.ordering_behavior_connected == false
    and .implemented_status_surface.may_change_search_order_now == false
    and .implemented_store_contract.schema == "agent_bridge.store.memory_search.biocortex_opt_in_contract.v0"
    and .implemented_store_contract.request_type == "BioCortexRetrievalOptInRequest"
    and .implemented_store_contract.decision_type == "BioCortexRetrievalOptInDecision"
    and .implemented_store_contract.response_type == "BioCortexRetrievalOptInResponseContract"
    and .implemented_store_contract.authorized_mode == "fts"
    and .implemented_store_contract.baseline_completed_required == true
    and .implemented_store_contract.zero_hit_baseline_is_completed == true
    and .implemented_store_contract.fallback_returns_baseline == true
    and .implemented_store_contract.fallback_reason_required == true
    and .implemented_store_contract.raw_query_included == false
    and .implemented_store_contract.raw_keys_included == false
    and .implemented_store_contract.content_included == false
    and .implemented_store_contract.ordering_behavior_connected == false
    and .implemented_store_contract.may_change_search_order_now == false
    and .implemented_store_opt_in_search_wrapper.method == "StateStore::memory_search_biocortex_opt_in"
    and .implemented_store_opt_in_search_wrapper.options_type == "BioCortexRetrievalOptInSearchOptions"
    and .implemented_store_opt_in_search_wrapper.outcome_type == "BioCortexRetrievalOptInSearchOutcome"
    and .implemented_store_opt_in_search_wrapper.redacted_audit_type == "BioCortexRetrievalOptInSearchAudit"
    and .implemented_store_opt_in_search_wrapper.redacted_audit_schema == "agent_bridge.store.memory_search.biocortex_opt_in_search_audit.v0"
    and .implemented_store_opt_in_search_wrapper.calls_existing_memory_search == true
    and .implemented_store_opt_in_search_wrapper.uses_existing_store_contract == true
    and .implemented_store_opt_in_search_wrapper.returns_baseline_order == true
    and .implemented_store_opt_in_search_wrapper.redacted_audit_only == true
    and .implemented_store_opt_in_search_wrapper.raw_query_included_in_audit == false
    and .implemented_store_opt_in_search_wrapper.raw_keys_included_in_audit == false
    and .implemented_store_opt_in_search_wrapper.content_included_in_audit == false
    and .implemented_store_opt_in_search_wrapper.runs_biocortex == false
    and .implemented_store_opt_in_search_wrapper.registers_embedding_backend == false
    and .implemented_store_opt_in_search_wrapper.runtime_adapter_approved == false
    and .implemented_store_opt_in_search_wrapper.changes_memory_search_order == false
    and .implemented_store_opt_in_search_wrapper.ordering_behavior_connected == false
    and .implemented_store_opt_in_search_wrapper.default_calls_unchanged == true
    and .implemented_store_opt_in_search_wrapper.may_implement_ordering_now == false
    and .implemented_store_opt_in_order_connection.method == "StateStore::memory_search_biocortex_opt_in"
    and .implemented_store_opt_in_order_connection.options_type == "BioCortexRetrievalOptInSearchOptions"
    and .implemented_store_opt_in_order_connection.side_signal_type == "BioCortexRetrievalOptInSideSignal"
    and .implemented_store_opt_in_order_connection.side_signal_summary_type == "BioCortexRetrievalOptInSideSignalSummary"
    and .implemented_store_opt_in_order_connection.implementation_stage == "store_opt_in_order_connection"
    and .implemented_store_opt_in_order_connection.authorized_scope == "explicit_opt_in_fts_runtime_influence"
    and .implemented_store_opt_in_order_connection.authorized_mode == "fts"
    and .implemented_store_opt_in_order_connection.requires_per_call_opt_in == true
    and .implemented_store_opt_in_order_connection.requires_compile_feature_enabled == true
    and .implemented_store_opt_in_order_connection.requires_runtime_enabled == true
    and .implemented_store_opt_in_order_connection.requires_runtime_adapter_approved == true
    and .implemented_store_opt_in_order_connection.requires_ordering_behavior_connected == true
    and .implemented_store_opt_in_order_connection.requires_operator_disable_absent == true
    and .implemented_store_opt_in_order_connection.requires_side_signal_coverage_threshold == true
    and .implemented_store_opt_in_order_connection.default_side_signal_coverage_threshold == 0.8
    and .implemented_store_opt_in_order_connection.default_blend_alpha == 0.8
    and .implemented_store_opt_in_order_connection.returns_experimental_order_when_all_gates_pass == true
    and .implemented_store_opt_in_order_connection.fallback_returns_baseline == true
    and .implemented_store_opt_in_order_connection.baseline_candidate_recall_source == "memory_search"
    and .implemented_store_opt_in_order_connection.side_signal_join_key == "candidate_key"
    and .implemented_store_opt_in_order_connection.side_signal_scores_in_audit == false
    and .implemented_store_opt_in_order_connection.raw_query_included_in_audit == false
    and .implemented_store_opt_in_order_connection.raw_keys_included_in_audit == false
    and .implemented_store_opt_in_order_connection.content_included_in_audit == false
    and .implemented_store_opt_in_order_connection.runs_biocortex == false
    and .implemented_store_opt_in_order_connection.registers_embedding_backend == false
    and .implemented_store_opt_in_order_connection.default_memory_search_unchanged == true
    and .implemented_store_opt_in_order_connection.hybrid_and_semantic_unchanged == true
    and .implemented_store_opt_in_order_connection.default_search_order_change_allowed == false
    and .implemented_store_opt_in_order_connection.explicit_opt_in_fts_ordering_behavior_connected == true
    and .implemented_store_opt_in_runtime_adapter_connection.mcp_tool == "biocortex_retrieval_opt_in_store_trial"
    and .implemented_store_opt_in_runtime_adapter_connection.schema == "agent_bridge.biocortex_retrieval.opt_in_store_trial.v0"
    and .implemented_store_opt_in_runtime_adapter_connection.implementation_stage == "store_opt_in_runtime_adapter_connection"
    and .implemented_store_opt_in_runtime_adapter_connection.authorized_scope == "explicit_opt_in_fts_runtime_influence"
    and .implemented_store_opt_in_runtime_adapter_connection.authorized_mode == "fts"
    and .implemented_store_opt_in_runtime_adapter_connection.requires_runtime_influence_decision_packet == true
    and .implemented_store_opt_in_runtime_adapter_connection.requires_decision_packet_runtime_adapter_approved == true
    and .implemented_store_opt_in_runtime_adapter_connection.requires_decision_packet_ordering_connection_authorized == true
    and .implemented_store_opt_in_runtime_adapter_connection.requires_per_call_opt_in == true
    and .implemented_store_opt_in_runtime_adapter_connection.requires_compile_feature_enabled == true
    and .implemented_store_opt_in_runtime_adapter_connection.requires_runtime_enabled == true
    and .implemented_store_opt_in_runtime_adapter_connection.requires_operator_disable_absent == true
    and .implemented_store_opt_in_runtime_adapter_connection.requires_side_signal_coverage_threshold == true
    and .implemented_store_opt_in_runtime_adapter_connection.baseline_candidate_recall_source == "store_memory_search_baseline_only"
    and .implemented_store_opt_in_runtime_adapter_connection.calls_memory_search == true
    and .implemented_store_opt_in_runtime_adapter_connection.runs_biocortex == true
    and .implemented_store_opt_in_runtime_adapter_connection.calls_store_opt_in_wrapper == true
    and .implemented_store_opt_in_runtime_adapter_connection.store_wrapper_method == "StateStore::memory_search_biocortex_opt_in"
    and .implemented_store_opt_in_runtime_adapter_connection.side_signal_join_key == "candidate_key"
    and .implemented_store_opt_in_runtime_adapter_connection.can_add_new_candidates == false
    and .implemented_store_opt_in_runtime_adapter_connection.mutates_ab_memory == false
    and .implemented_store_opt_in_runtime_adapter_connection.registers_embedding_backend == false
    and .implemented_store_opt_in_runtime_adapter_connection.writes_approval == false
    and .implemented_store_opt_in_runtime_adapter_connection.raw_query_included == false
    and .implemented_store_opt_in_runtime_adapter_connection.raw_keys_included == false
    and .implemented_store_opt_in_runtime_adapter_connection.content_included == false
    and .implemented_store_opt_in_runtime_adapter_connection.side_signal_raw_included == false
    and .implemented_store_opt_in_runtime_adapter_connection.returns_redacted_order_summary == true
    and .implemented_store_opt_in_runtime_adapter_connection.returns_redacted_store_wrapper_audit == true
    and .implemented_store_opt_in_runtime_adapter_connection.fallback_returns_baseline == true
    and .implemented_store_opt_in_runtime_adapter_connection.default_memory_search_unchanged == true
    and .implemented_store_opt_in_runtime_adapter_connection.hybrid_and_semantic_unchanged == true
    and .implemented_store_opt_in_runtime_adapter_connection.default_search_order_change_allowed == false
    and .implemented_store_opt_in_runtime_adapter_connection.default_calls_unchanged == true
    and .implemented_store_opt_in_runtime_adapter_connection.explicit_opt_in_fts_runtime_adapter_connected == true
    and .implemented_authorization_decision_consumer.cli == "agent-bridge bio-cortex retrieval-opt-in-authorization-decision-packet"
    and .implemented_authorization_decision_consumer.mcp_tool == "biocortex_retrieval_opt_in_authorization_decision_packet"
    and .implemented_authorization_decision_consumer.schema == "agent_bridge.biocortex_retrieval.opt_in_authorization_decision_packet.v0"
    and .implemented_authorization_decision_consumer.read_only == true
    and .implemented_authorization_decision_consumer.authorization_decision_consumer == true
    and .implemented_authorization_decision_consumer.implementation_stage == "authorization_decision_consumer_only"
    and .implemented_authorization_decision_consumer.consumes_authorization_request_summary == true
    and .implemented_authorization_decision_consumer.consumes_authorization_decision_summary == true
    and .implemented_authorization_decision_consumer.authorization_request_included == false
    and .implemented_authorization_decision_consumer.authorization_decision_included == false
    and .implemented_authorization_decision_consumer.raw_query_included == false
    and .implemented_authorization_decision_consumer.raw_keys_included == false
    and .implemented_authorization_decision_consumer.content_included == false
    and .implemented_authorization_decision_consumer.implementation_allowed == true
    and .implemented_authorization_decision_consumer.approval_state == "opt_in_implementation_authorized"
    and .implemented_authorization_decision_consumer.authorization_state == "authorized_for_opt_in_implementation"
    and .implemented_authorization_decision_consumer.runtime_adapter_approved == false
    and .implemented_authorization_decision_consumer.default_search_order_change_allowed == false
    and .implemented_authorization_decision_consumer.requires_post_implementation_review_before_use == true
    and .implemented_authorization_decision_consumer.approval_writes_allowed == false
    and .implemented_authorization_decision_consumer.writes_approval == false
    and .implemented_authorization_decision_consumer.calls_memory_search == false
    and .implemented_authorization_decision_consumer.runs_biocortex == false
    and .implemented_authorization_decision_consumer.registers_embedding_backend == false
    and .implemented_authorization_decision_consumer.changes_memory_search_order == false
    and .implemented_authorization_decision_consumer.ordering_behavior_connected == false
    and .implemented_authorization_decision_consumer.may_change_search_order_now == false
    and .implemented_authorization_decision_consumer.may_implement_ordering_now == false
    and .implemented_post_implementation_review_gate.cli == "agent-bridge bio-cortex retrieval-opt-in-post-implementation-review-gate"
    and .implemented_post_implementation_review_gate.mcp_tool == "biocortex_retrieval_opt_in_post_implementation_review_gate"
    and .implemented_post_implementation_review_gate.schema == "agent_bridge.biocortex_retrieval.opt_in_post_implementation_review_gate.v0"
    and .implemented_post_implementation_review_gate.read_only == true
    and .implemented_post_implementation_review_gate.post_implementation_review_gate == true
    and .implemented_post_implementation_review_gate.implementation_stage == "post_implementation_review_gate_only"
    and .implemented_post_implementation_review_gate.consumes_authorization_decision_packet_summary == true
    and .implemented_post_implementation_review_gate.consumes_opt_in_plan_summary == true
    and .implemented_post_implementation_review_gate.authorization_decision_packet_included == false
    and .implemented_post_implementation_review_gate.opt_in_plan_included == false
    and .implemented_post_implementation_review_gate.raw_query_included == false
    and .implemented_post_implementation_review_gate.raw_keys_included == false
    and .implemented_post_implementation_review_gate.content_included == false
    and .implemented_post_implementation_review_gate.ready_for_human_runtime_influence_review == true
    and .implemented_post_implementation_review_gate.post_implementation_review_completed == false
    and .implemented_post_implementation_review_gate.runtime_adapter_review_completed == false
    and .implemented_post_implementation_review_gate.ordering_behavior_review_completed == false
    and .implemented_post_implementation_review_gate.approval_state == "not_approved"
    and .implemented_post_implementation_review_gate.authorization_state == "requires_separate_human_runtime_influence_review"
    and .implemented_post_implementation_review_gate.implementation_allowed == false
    and .implemented_post_implementation_review_gate.runtime_adapter_approved == false
    and .implemented_post_implementation_review_gate.default_search_order_change_allowed == false
    and .implemented_post_implementation_review_gate.requires_separate_runtime_influence_review == true
    and .implemented_post_implementation_review_gate.approval_writes_allowed == false
    and .implemented_post_implementation_review_gate.writes_approval == false
    and .implemented_post_implementation_review_gate.calls_memory_search == false
    and .implemented_post_implementation_review_gate.runs_biocortex == false
    and .implemented_post_implementation_review_gate.registers_embedding_backend == false
    and .implemented_post_implementation_review_gate.changes_memory_search_order == false
    and .implemented_post_implementation_review_gate.ordering_behavior_connected == false
    and .implemented_post_implementation_review_gate.may_change_search_order_now == false
    and .implemented_post_implementation_review_gate.may_implement_ordering_now == false
    and .implemented_runtime_influence_review_request.cli == "agent-bridge bio-cortex retrieval-opt-in-runtime-influence-review-request"
    and .implemented_runtime_influence_review_request.mcp_tool == "biocortex_retrieval_opt_in_runtime_influence_review_request"
    and .implemented_runtime_influence_review_request.schema == "agent_bridge.biocortex_retrieval.opt_in_runtime_influence_review_request.v0"
    and .implemented_runtime_influence_review_request.read_only == true
    and .implemented_runtime_influence_review_request.runtime_influence_review_request == true
    and .implemented_runtime_influence_review_request.implementation_stage == "runtime_influence_review_request_only"
    and .implemented_runtime_influence_review_request.consumes_post_implementation_review_gate_summary == true
    and .implemented_runtime_influence_review_request.consumes_redacted_order_artifact_summary == true
    and .implemented_runtime_influence_review_request.post_implementation_review_gate_included == false
    and .implemented_runtime_influence_review_request.redacted_order_artifact_included == false
    and .implemented_runtime_influence_review_request.raw_query_included == false
    and .implemented_runtime_influence_review_request.raw_keys_included == false
    and .implemented_runtime_influence_review_request.content_included == false
    and .implemented_runtime_influence_review_request.request_scope == "explicit_opt_in_fts_runtime_influence_review"
    and .implemented_runtime_influence_review_request.request_runtime_adapter_review == true
    and .implemented_runtime_influence_review_request.request_ordering_behavior_connection_review == true
    and .implemented_runtime_influence_review_request.request_default_search_order_change == false
    and .implemented_runtime_influence_review_request.request_hybrid_retrieval_influence == false
    and .implemented_runtime_influence_review_request.request_semantic_retrieval_influence == false
    and .implemented_runtime_influence_review_request.this_packet_grants_request == false
    and .implemented_runtime_influence_review_request.approval_state == "not_approved"
    and .implemented_runtime_influence_review_request.authorization_state == "runtime_influence_review_requested_not_granted"
    and .implemented_runtime_influence_review_request.implementation_allowed == false
    and .implemented_runtime_influence_review_request.runtime_adapter_approved == false
    and .implemented_runtime_influence_review_request.default_search_order_change_allowed == false
    and .implemented_runtime_influence_review_request.approval_writes_allowed == false
    and .implemented_runtime_influence_review_request.writes_approval == false
    and .implemented_runtime_influence_review_request.calls_memory_search == false
    and .implemented_runtime_influence_review_request.runs_biocortex == false
    and .implemented_runtime_influence_review_request.registers_embedding_backend == false
    and .implemented_runtime_influence_review_request.changes_memory_search_order == false
    and .implemented_runtime_influence_review_request.ordering_behavior_connected == false
    and .implemented_runtime_influence_review_request.may_change_search_order_now == false
    and .implemented_runtime_influence_review_request.may_implement_ordering_now == false
    and .implemented_runtime_influence_decision_packet.cli == "agent-bridge bio-cortex retrieval-opt-in-runtime-influence-decision-packet"
    and .implemented_runtime_influence_decision_packet.mcp_tool == "biocortex_retrieval_opt_in_runtime_influence_decision_packet"
    and .implemented_runtime_influence_decision_packet.schema == "agent_bridge.biocortex_retrieval.opt_in_runtime_influence_decision_packet.v0"
    and .implemented_runtime_influence_decision_packet.read_only == true
    and .implemented_runtime_influence_decision_packet.runtime_influence_decision_consumer == true
    and .implemented_runtime_influence_decision_packet.implementation_stage == "runtime_influence_decision_consumer_only"
    and .implemented_runtime_influence_decision_packet.consumes_runtime_influence_review_request_summary == true
    and .implemented_runtime_influence_decision_packet.consumes_runtime_influence_decision_summary == true
    and .implemented_runtime_influence_decision_packet.runtime_influence_review_request_included == false
    and .implemented_runtime_influence_decision_packet.runtime_influence_decision_included == false
    and .implemented_runtime_influence_decision_packet.human_decision_text_included == false
    and .implemented_runtime_influence_decision_packet.raw_query_included == false
    and .implemented_runtime_influence_decision_packet.raw_keys_included == false
    and .implemented_runtime_influence_decision_packet.content_included == false
    and .implemented_runtime_influence_decision_packet.authorization_scope == "explicit_opt_in_fts_runtime_influence"
    and .implemented_runtime_influence_decision_packet.can_authorize_explicit_opt_in_fts_runtime_adapter == true
    and .implemented_runtime_influence_decision_packet.can_authorize_explicit_opt_in_fts_ordering_connection == true
    and .implemented_runtime_influence_decision_packet.default_search_order_change_allowed == false
    and .implemented_runtime_influence_decision_packet.default_retrieval_influence_authorized == false
    and .implemented_runtime_influence_decision_packet.hybrid_retrieval_influence_authorized == false
    and .implemented_runtime_influence_decision_packet.semantic_retrieval_influence_authorized == false
    and .implemented_runtime_influence_decision_packet.approval_writes_allowed == false
    and .implemented_runtime_influence_decision_packet.writes_approval == false
    and .implemented_runtime_influence_decision_packet.calls_memory_search == false
    and .implemented_runtime_influence_decision_packet.runs_biocortex == false
    and .implemented_runtime_influence_decision_packet.registers_embedding_backend == false
    and .implemented_runtime_influence_decision_packet.changes_memory_search_order == false
    and .implemented_runtime_influence_decision_packet.ordering_behavior_connected == false
    and .implemented_runtime_influence_decision_packet.may_change_search_order_now == false
    and .implemented_runtime_influence_decision_packet.requires_separate_connection_implementation == true
    and .implemented_runtime_influence_decision_packet.this_packet_connects_ordering_behavior == false
    and .implemented_runtime_influence_decision_packet.this_packet_changes_return_order == false
    and .implemented_dry_run_planner.cli == "agent-bridge bio-cortex retrieval-opt-in-dry-run"
    and .implemented_dry_run_planner.mcp_tool == "biocortex_retrieval_opt_in_dry_run"
    and .implemented_dry_run_planner.schema == "agent_bridge.biocortex_retrieval.opt_in_dry_run_plan.v0"
    and .implemented_dry_run_planner.read_only == true
    and .implemented_dry_run_planner.dry_run == true
    and .implemented_dry_run_planner.calls_memory_search == false
    and .implemented_dry_run_planner.runs_biocortex == false
    and .implemented_dry_run_planner.registers_embedding_backend == false
    and .implemented_dry_run_planner.raw_query_included == false
    and .implemented_dry_run_planner.raw_keys_included == false
    and .implemented_dry_run_planner.content_included == false
    and .implemented_dry_run_planner.includes_store_contract == true
    and (.implemented_dry_run_planner.planned_steps | index("baseline_fts_memory_search"))
    and (.implemented_dry_run_planner.planned_steps | index("biocortex_side_signal"))
    and (.implemented_dry_run_planner.planned_steps | index("return_order"))
    and .implemented_dry_run_planner.ordering_behavior_connected == false
    and .implemented_dry_run_planner.may_change_search_order_now == false
    and .implemented_review_packet_consumer.cli == "agent-bridge bio-cortex retrieval-opt-in-review-packet"
    and .implemented_review_packet_consumer.mcp_tool == "biocortex_retrieval_opt_in_review_packet"
    and .implemented_review_packet_consumer.schema == "agent_bridge.biocortex_retrieval.opt_in_review_packet.v0"
    and .implemented_review_packet_consumer.read_only == true
    and .implemented_review_packet_consumer.dry_run_consumer == true
    and .implemented_review_packet_consumer.raw_dry_run_plan_included == false
    and .implemented_review_packet_consumer.raw_query_included == false
    and .implemented_review_packet_consumer.raw_keys_included == false
    and .implemented_review_packet_consumer.content_included == false
    and .implemented_review_packet_consumer.reports_boundary_violations == true
    and .implemented_review_packet_consumer.approval_state == "not_approved"
    and .implemented_review_packet_consumer.runtime_adapter_approved == false
    and .implemented_review_packet_consumer.approval_writes_allowed == false
    and .implemented_review_packet_consumer.calls_memory_search == false
    and .implemented_review_packet_consumer.runs_biocortex == false
    and .implemented_review_packet_consumer.registers_embedding_backend == false
    and .implemented_review_packet_consumer.changes_memory_search_order == false
    and .implemented_review_packet_consumer.ordering_behavior_connected == false
    and .implemented_review_packet_consumer.may_implement_ordering_now == false
    and .implemented_execution_packet_contract.cli == "agent-bridge bio-cortex retrieval-opt-in-execution-packet"
    and .implemented_execution_packet_contract.mcp_tool == "biocortex_retrieval_opt_in_execution_packet"
    and .implemented_execution_packet_contract.schema == "agent_bridge.biocortex_retrieval.opt_in_execution_packet.v0"
    and .implemented_execution_packet_contract.read_only == true
    and .implemented_execution_packet_contract.execution_packet == true
    and .implemented_execution_packet_contract.review_packet_included == false
    and .implemented_execution_packet_contract.raw_query_included == false
    and .implemented_execution_packet_contract.raw_keys_included == false
    and .implemented_execution_packet_contract.content_included == false
    and .implemented_execution_packet_contract.rebuilds_store_contract == true
    and .implemented_execution_packet_contract.protected_adapter_contract == true
    and .implemented_execution_packet_contract.candidate_recall_source == "baseline_only"
    and .implemented_execution_packet_contract.join_key == "candidate_key"
    and .implemented_execution_packet_contract.can_add_new_candidates == false
    and .implemented_execution_packet_contract.execution_allowed == false
    and .implemented_execution_packet_contract.approval_state == "not_approved"
    and .implemented_execution_packet_contract.runtime_adapter_approved == false
    and .implemented_execution_packet_contract.approval_writes_allowed == false
    and .implemented_execution_packet_contract.calls_memory_search == false
    and .implemented_execution_packet_contract.runs_biocortex == false
    and .implemented_execution_packet_contract.registers_embedding_backend == false
    and .implemented_execution_packet_contract.changes_memory_search_order == false
    and .implemented_execution_packet_contract.ordering_behavior_connected == false
    and .implemented_execution_packet_contract.may_implement_ordering_now == false
    and .implemented_runtime_trial.cli == "agent-bridge bio-cortex retrieval-opt-in-runtime-trial"
    and .implemented_runtime_trial.mcp_tool == "biocortex_retrieval_opt_in_runtime_trial"
    and .implemented_runtime_trial.schema == "agent_bridge.biocortex_retrieval.opt_in_runtime_trial.v0"
    and .implemented_runtime_trial.read_only == true
    and .implemented_runtime_trial.runtime_trial == true
    and .implemented_runtime_trial.execution_packet_included == false
    and .implemented_runtime_trial.consumes_execution_packet_summary == true
    and .implemented_runtime_trial.calls_memory_search == false
    and .implemented_runtime_trial.runs_biocortex == true
    and .implemented_runtime_trial.runs_biocortex_only_when_gate_ready == true
    and .implemented_runtime_trial.writes_temp_corpus == true
    and .implemented_runtime_trial.mutates_ab_memory == false
    and .implemented_runtime_trial.registers_embedding_backend == false
    and .implemented_runtime_trial.candidate_recall_source == "baseline_only"
    and .implemented_runtime_trial.join_key == "candidate_key"
    and .implemented_runtime_trial.can_add_new_candidates == false
    and .implemented_runtime_trial.raw_query_included == false
    and .implemented_runtime_trial.raw_keys_included == false
    and .implemented_runtime_trial.content_included == false
    and .implemented_runtime_trial.side_signal_raw_included == false
    and .implemented_runtime_trial.returned_order_source == "baseline"
    and .implemented_runtime_trial.baseline_returned == true
    and .implemented_runtime_trial.changes_memory_search_order == false
    and .implemented_runtime_trial.ordering_behavior_connected == false
    and .implemented_runtime_trial.runtime_adapter_approved == false
    and .implemented_runtime_trial.default_search_order_change_allowed == false
    and .implemented_runtime_trial.approval_writes_allowed == false
    and .implemented_runtime_trial.may_change_search_order_now == false
    and .implemented_runtime_trial.may_implement_ordering_now == false
    and .implemented_runtime_trial_review_packet.cli == "agent-bridge bio-cortex retrieval-opt-in-runtime-trial-review-packet"
    and .implemented_runtime_trial_review_packet.mcp_tool == "biocortex_retrieval_opt_in_runtime_trial_review_packet"
    and .implemented_runtime_trial_review_packet.schema == "agent_bridge.biocortex_retrieval.opt_in_runtime_trial_review_packet.v0"
    and .implemented_runtime_trial_review_packet.read_only == true
    and .implemented_runtime_trial_review_packet.runtime_trial_consumer == true
    and .implemented_runtime_trial_review_packet.runtime_trial_packet_included == false
    and .implemented_runtime_trial_review_packet.raw_query_included == false
    and .implemented_runtime_trial_review_packet.raw_keys_included == false
    and .implemented_runtime_trial_review_packet.content_included == false
    and .implemented_runtime_trial_review_packet.side_signal_raw_included == false
    and .implemented_runtime_trial_review_packet.reports_boundary_violations == true
    and .implemented_runtime_trial_review_packet.review_scope == "baseline_preserving_runtime_trial_only"
    and .implemented_runtime_trial_review_packet.review_ready_does_not_approve_runtime_influence == true
    and .implemented_runtime_trial_review_packet.approval_state == "not_approved"
    and .implemented_runtime_trial_review_packet.runtime_adapter_approved == false
    and .implemented_runtime_trial_review_packet.approval_writes_allowed == false
    and .implemented_runtime_trial_review_packet.writes_approval == false
    and .implemented_runtime_trial_review_packet.calls_memory_search == false
    and .implemented_runtime_trial_review_packet.runs_biocortex == false
    and .implemented_runtime_trial_review_packet.registers_embedding_backend == false
    and .implemented_runtime_trial_review_packet.changes_memory_search_order == false
    and .implemented_runtime_trial_review_packet.ordering_behavior_connected == false
    and .implemented_runtime_trial_review_packet.may_implement_ordering_now == false
    and .implemented_authorization_request_runtime_trial_review_evidence.script == "scripts/prepare-biocortex-retrieval-opt-in-authorization-request.sh"
    and .implemented_authorization_request_runtime_trial_review_evidence.request_schema == "agent_bridge.biocortex_retrieval.opt_in_authorization_request.v0"
    and .implemented_authorization_request_runtime_trial_review_evidence.required_input == "agent_bridge.biocortex_retrieval.opt_in_runtime_trial_review_packet.v0"
    and .implemented_authorization_request_runtime_trial_review_evidence.evidence_path == "evidence.runtime_trial_review_packet"
    and .implemented_authorization_request_runtime_trial_review_evidence.read_only == true
    and .implemented_authorization_request_runtime_trial_review_evidence.runtime_trial_packet_included == false
    and .implemented_authorization_request_runtime_trial_review_evidence.raw_query_included == false
    and .implemented_authorization_request_runtime_trial_review_evidence.raw_keys_included == false
    and .implemented_authorization_request_runtime_trial_review_evidence.content_included == false
    and .implemented_authorization_request_runtime_trial_review_evidence.side_signal_raw_included == false
    and .implemented_authorization_request_runtime_trial_review_evidence.requires_review_ready_for_baseline_runtime_trial == true
    and .implemented_authorization_request_runtime_trial_review_evidence.requires_zero_boundary_violations == true
    and .implemented_authorization_request_runtime_trial_review_evidence.approval_state == "not_approved"
    and .implemented_authorization_request_runtime_trial_review_evidence.runtime_adapter_approved == false
    and .implemented_authorization_request_runtime_trial_review_evidence.approval_writes_allowed == false
    and .implemented_authorization_request_runtime_trial_review_evidence.writes_approval == false
    and .implemented_authorization_request_runtime_trial_review_evidence.calls_memory_search == false
    and .implemented_authorization_request_runtime_trial_review_evidence.runs_biocortex == false
    and .implemented_authorization_request_runtime_trial_review_evidence.registers_embedding_backend == false
    and .implemented_authorization_request_runtime_trial_review_evidence.changes_memory_search_order == false
    and .implemented_authorization_request_runtime_trial_review_evidence.ordering_behavior_connected == false
    and .implemented_authorization_request_runtime_trial_review_evidence.may_implement_ordering_now == false
    and .implemented_order_diff_packet.cli == "agent-bridge bio-cortex retrieval-opt-in-order-diff-packet"
    and .implemented_order_diff_packet.mcp_tool == "biocortex_retrieval_opt_in_order_diff_packet"
    and .implemented_order_diff_packet.schema == "agent_bridge.biocortex_retrieval.opt_in_order_diff_packet.v0"
    and .implemented_order_diff_packet.read_only == true
    and .implemented_order_diff_packet.order_diff_packet == true
    and .implemented_order_diff_packet.source_packet_consumer == true
    and (.implemented_order_diff_packet.accepted_source_schemas | index("agent_bridge.biocortex_retrieval.opt_in_runtime_trial.v0"))
    and (.implemented_order_diff_packet.accepted_source_schemas | index("agent_bridge.biocortex_retrieval.opt_in_runtime_trial_review_packet.v0"))
    and .implemented_order_diff_packet.source_packet_included == false
    and .implemented_order_diff_packet.raw_query_included == false
    and .implemented_order_diff_packet.raw_keys_included == false
    and .implemented_order_diff_packet.content_included == false
    and .implemented_order_diff_packet.side_signal_raw_included == false
    and .implemented_order_diff_packet.compares_baseline_vs_advisory_hash_only == true
    and .implemented_order_diff_packet.reports_order_hash_changed == true
    and .implemented_order_diff_packet.reports_top_key_changed == true
    and .implemented_order_diff_packet.reports_expected_rank_delta == true
    and .implemented_order_diff_packet.full_top_k_overlap_available == false
    and .implemented_order_diff_packet.per_key_movements_available == false
    and .implemented_order_diff_packet.calls_memory_search == false
    and .implemented_order_diff_packet.runs_biocortex == false
    and .implemented_order_diff_packet.registers_embedding_backend == false
    and .implemented_order_diff_packet.changes_memory_search_order == false
    and .implemented_order_diff_packet.ordering_behavior_connected == false
    and .implemented_order_diff_packet.actual_return_order_changed == false
    and .implemented_order_diff_packet.approval_state == "not_approved"
    and .implemented_order_diff_packet.runtime_adapter_approved == false
    and .implemented_order_diff_packet.approval_writes_allowed == false
    and .implemented_order_diff_packet.writes_approval == false
    and .implemented_order_diff_packet.may_implement_ordering_now == false
    and .implemented_redacted_order_artifact.cli == "agent-bridge bio-cortex retrieval-opt-in-redacted-order-artifact"
    and .implemented_redacted_order_artifact.mcp_tool == "biocortex_retrieval_opt_in_redacted_order_artifact"
    and .implemented_redacted_order_artifact.schema == "agent_bridge.biocortex_retrieval.opt_in_redacted_order_artifact.v0"
    and .implemented_redacted_order_artifact.read_only == true
    and .implemented_redacted_order_artifact.redacted_order_artifact == true
    and .implemented_redacted_order_artifact.source_packet_consumer == true
    and (.implemented_redacted_order_artifact.accepted_source_schemas | index("agent_bridge.biocortex_retrieval.opt_in_runtime_trial.v0"))
    and (.implemented_redacted_order_artifact.accepted_source_schemas | index("agent_bridge.biocortex_retrieval.opt_in_runtime_trial_review_packet.v0"))
    and .implemented_redacted_order_artifact.source_packet_included == false
    and .implemented_redacted_order_artifact.raw_query_included == false
    and .implemented_redacted_order_artifact.raw_keys_included == false
    and .implemented_redacted_order_artifact.raw_order_keys_included == false
    and .implemented_redacted_order_artifact.content_included == false
    and .implemented_redacted_order_artifact.side_signal_raw_included == false
    and .implemented_redacted_order_artifact.redacted_key_hashes_included == true
    and .implemented_redacted_order_artifact.computes_top_k_overlap == true
    and .implemented_redacted_order_artifact.computes_rank_delta_distribution == true
    and .implemented_redacted_order_artifact.computes_per_key_movements == true
    and .implemented_redacted_order_artifact.copies_raw_hashes == false
    and .implemented_redacted_order_artifact.copies_raw_order_keys == false
    and .implemented_redacted_order_artifact.calls_memory_search == false
    and .implemented_redacted_order_artifact.runs_biocortex == false
    and .implemented_redacted_order_artifact.registers_embedding_backend == false
    and .implemented_redacted_order_artifact.changes_memory_search_order == false
    and .implemented_redacted_order_artifact.ordering_behavior_connected == false
    and .implemented_redacted_order_artifact.actual_return_order_changed == false
    and .implemented_redacted_order_artifact.approval_state == "not_approved"
    and .implemented_redacted_order_artifact.runtime_adapter_approved == false
    and .implemented_redacted_order_artifact.approval_writes_allowed == false
    and .implemented_redacted_order_artifact.writes_approval == false
    and .implemented_redacted_order_artifact.may_implement_ordering_now == false
    and .implemented_authorization_request_order_diff_evidence.script == "scripts/prepare-biocortex-retrieval-opt-in-authorization-request.sh"
    and .implemented_authorization_request_order_diff_evidence.request_schema == "agent_bridge.biocortex_retrieval.opt_in_authorization_request.v0"
    and .implemented_authorization_request_order_diff_evidence.optional_input == "agent_bridge.biocortex_retrieval.opt_in_order_diff_packet.v0"
    and .implemented_authorization_request_order_diff_evidence.evidence_path == "evidence.order_diff_packet"
    and .implemented_authorization_request_order_diff_evidence.required == false
    and .implemented_authorization_request_order_diff_evidence.read_only == true
    and .implemented_authorization_request_order_diff_evidence.order_diff_packet_included == false
    and .implemented_authorization_request_order_diff_evidence.raw_query_included == false
    and .implemented_authorization_request_order_diff_evidence.raw_keys_included == false
    and .implemented_authorization_request_order_diff_evidence.content_included == false
    and .implemented_authorization_request_order_diff_evidence.side_signal_raw_included == false
    and .implemented_authorization_request_order_diff_evidence.requires_diff_ready_when_provided == true
    and .implemented_authorization_request_order_diff_evidence.requires_zero_boundary_violations_when_provided == true
    and .implemented_authorization_request_order_diff_evidence.hash_only_summary == true
    and .implemented_authorization_request_order_diff_evidence.copies_raw_hashes == false
    and .implemented_authorization_request_order_diff_evidence.copies_raw_order_keys == false
    and .implemented_authorization_request_order_diff_evidence.reports_order_hash_changed == true
    and .implemented_authorization_request_order_diff_evidence.reports_top_key_changed == true
    and .implemented_authorization_request_order_diff_evidence.reports_expected_rank_delta == true
    and .implemented_authorization_request_order_diff_evidence.approval_state == "not_approved"
    and .implemented_authorization_request_order_diff_evidence.runtime_adapter_approved == false
    and .implemented_authorization_request_order_diff_evidence.approval_writes_allowed == false
    and .implemented_authorization_request_order_diff_evidence.writes_approval == false
    and .implemented_authorization_request_order_diff_evidence.calls_memory_search == false
    and .implemented_authorization_request_order_diff_evidence.runs_biocortex == false
    and .implemented_authorization_request_order_diff_evidence.registers_embedding_backend == false
    and .implemented_authorization_request_order_diff_evidence.changes_memory_search_order == false
    and .implemented_authorization_request_order_diff_evidence.ordering_behavior_connected == false
    and .implemented_authorization_request_order_diff_evidence.actual_return_order_changed == false
    and .implemented_authorization_request_order_diff_evidence.may_implement_ordering_now == false
    and .implemented_authorization_request_redacted_order_artifact_evidence.script == "scripts/prepare-biocortex-retrieval-opt-in-authorization-request.sh"
    and .implemented_authorization_request_redacted_order_artifact_evidence.request_schema == "agent_bridge.biocortex_retrieval.opt_in_authorization_request.v0"
    and .implemented_authorization_request_redacted_order_artifact_evidence.optional_input == "agent_bridge.biocortex_retrieval.opt_in_redacted_order_artifact.v0"
    and .implemented_authorization_request_redacted_order_artifact_evidence.evidence_path == "evidence.redacted_order_artifact"
    and .implemented_authorization_request_redacted_order_artifact_evidence.required == false
    and .implemented_authorization_request_redacted_order_artifact_evidence.read_only == true
    and .implemented_authorization_request_redacted_order_artifact_evidence.summary_only == true
    and .implemented_authorization_request_redacted_order_artifact_evidence.artifact_included == false
    and .implemented_authorization_request_redacted_order_artifact_evidence.requires_artifact_ready_when_provided == true
    and .implemented_authorization_request_redacted_order_artifact_evidence.requires_zero_boundary_violations_when_provided == true
    and .implemented_authorization_request_redacted_order_artifact_evidence.requires_redacted_rows_comparable_when_provided == true
    and .implemented_authorization_request_redacted_order_artifact_evidence.reports_top_k_overlap == true
    and .implemented_authorization_request_redacted_order_artifact_evidence.reports_rank_delta_distribution == true
    and .implemented_authorization_request_redacted_order_artifact_evidence.reports_per_key_movement_count == true
    and .implemented_authorization_request_redacted_order_artifact_evidence.copies_key_hashes == false
    and .implemented_authorization_request_redacted_order_artifact_evidence.copies_redacted_rank_rows == false
    and .implemented_authorization_request_redacted_order_artifact_evidence.copies_raw_order_keys == false
    and .implemented_authorization_request_redacted_order_artifact_evidence.raw_query_included == false
    and .implemented_authorization_request_redacted_order_artifact_evidence.raw_keys_included == false
    and .implemented_authorization_request_redacted_order_artifact_evidence.raw_order_keys_included == false
    and .implemented_authorization_request_redacted_order_artifact_evidence.content_included == false
    and .implemented_authorization_request_redacted_order_artifact_evidence.side_signal_raw_included == false
    and .implemented_authorization_request_redacted_order_artifact_evidence.approval_state == "not_approved"
    and .implemented_authorization_request_redacted_order_artifact_evidence.runtime_adapter_approved == false
    and .implemented_authorization_request_redacted_order_artifact_evidence.approval_writes_allowed == false
    and .implemented_authorization_request_redacted_order_artifact_evidence.writes_approval == false
    and .implemented_authorization_request_redacted_order_artifact_evidence.calls_memory_search == false
    and .implemented_authorization_request_redacted_order_artifact_evidence.runs_biocortex == false
    and .implemented_authorization_request_redacted_order_artifact_evidence.registers_embedding_backend == false
    and .implemented_authorization_request_redacted_order_artifact_evidence.changes_memory_search_order == false
    and .implemented_authorization_request_redacted_order_artifact_evidence.ordering_behavior_connected == false
    and .implemented_authorization_request_redacted_order_artifact_evidence.actual_return_order_changed == false
    and .implemented_authorization_request_redacted_order_artifact_evidence.may_implement_ordering_now == false
    and .fail_open.operator_disable == "return_baseline"
    and .human_review_boundary.authorization_decision_recorded == true
    and .human_review_boundary.requires_separate_human_decision_before_implementation == false
    and .human_review_boundary.requires_post_implementation_review_before_ordering_use == true
' "$opt_in_plan" >/dev/null

opt_in_auth_template="docs/design/fixtures/biocortex-retrieval-opt-in-authorization-request-template-2026-06-11.json"
jq -e '
    .schema == "agent_bridge.biocortex_retrieval.opt_in_authorization_request.v0"
    and .status == "template_only"
    and .approval_state == "not_approved"
    and .authorization_state == "requested_not_granted"
    and .request_scope == "opt_in_experiment"
    and .runtime_adapter_approved == false
    and .default_search_order_change_allowed == false
    and .implementation_allowed == false
    and .writes_approval == false
    and .requires_runtime_trial_review_packet == true
    and .requires_order_diff_packet == false
    and .accepts_optional_order_diff_packet == true
    and .accepts_optional_redacted_order_artifact == true
    and .evidence.runtime_trial_review_packet.required_schema == "agent_bridge.biocortex_retrieval.opt_in_runtime_trial_review_packet.v0"
    and .evidence.runtime_trial_review_packet.required_review_ready_for_baseline_runtime_trial == true
    and .evidence.runtime_trial_review_packet.required_violation_count == 0
    and .evidence.runtime_trial_review_packet.raw_query_included == false
    and .evidence.runtime_trial_review_packet.raw_keys_included == false
    and .evidence.runtime_trial_review_packet.content_included == false
    and .evidence.runtime_trial_review_packet.side_signal_raw_included == false
    and .evidence.runtime_trial_review_packet.approval_state == "not_approved"
    and .evidence.runtime_trial_review_packet.runtime_adapter_approved == false
    and .evidence.runtime_trial_review_packet.changes_memory_search_order == false
    and .evidence.runtime_trial_review_packet.ordering_behavior_connected == false
    and .evidence.order_diff_packet.required == false
    and .evidence.order_diff_packet.required_schema_when_provided == "agent_bridge.biocortex_retrieval.opt_in_order_diff_packet.v0"
    and .evidence.order_diff_packet.required_diff_ready_when_provided == true
    and .evidence.order_diff_packet.required_violation_count_when_provided == 0
    and .evidence.order_diff_packet.raw_query_included == false
    and .evidence.order_diff_packet.raw_keys_included == false
    and .evidence.order_diff_packet.content_included == false
    and .evidence.order_diff_packet.side_signal_raw_included == false
    and .evidence.order_diff_packet.raw_order_keys_included == false
    and .evidence.order_diff_packet.copies_raw_hashes == false
    and .evidence.order_diff_packet.reports_order_hash_changed == true
    and .evidence.order_diff_packet.reports_top_key_changed == true
    and .evidence.order_diff_packet.reports_expected_rank_delta == true
    and .evidence.order_diff_packet.actual_return_order_changed == false
    and .evidence.order_diff_packet.approval_state == "not_approved"
    and .evidence.order_diff_packet.runtime_adapter_approved == false
    and .evidence.order_diff_packet.calls_memory_search == false
    and .evidence.order_diff_packet.runs_biocortex == false
    and .evidence.order_diff_packet.changes_memory_search_order == false
    and .evidence.order_diff_packet.ordering_behavior_connected == false
    and .evidence.redacted_order_artifact.required == false
    and .evidence.redacted_order_artifact.required_schema_when_provided == "agent_bridge.biocortex_retrieval.opt_in_redacted_order_artifact.v0"
    and .evidence.redacted_order_artifact.required_artifact_ready_when_provided == true
    and .evidence.redacted_order_artifact.required_violation_count_when_provided == 0
    and .evidence.redacted_order_artifact.required_redacted_rows_comparable_when_provided == true
    and .evidence.redacted_order_artifact.summary_only == true
    and .evidence.redacted_order_artifact.reports_top_k_overlap == true
    and .evidence.redacted_order_artifact.reports_rank_delta_distribution == true
    and .evidence.redacted_order_artifact.reports_per_key_movement_count == true
    and .evidence.redacted_order_artifact.raw_query_included == false
    and .evidence.redacted_order_artifact.raw_keys_included == false
    and .evidence.redacted_order_artifact.raw_order_keys_included == false
    and .evidence.redacted_order_artifact.content_included == false
    and .evidence.redacted_order_artifact.side_signal_raw_included == false
    and .evidence.redacted_order_artifact.redacted_key_hashes_in_artifact == true
    and .evidence.redacted_order_artifact.copies_key_hashes_to_request == false
    and .evidence.redacted_order_artifact.copies_redacted_rank_rows == false
    and .evidence.redacted_order_artifact.actual_return_order_changed == false
    and .evidence.redacted_order_artifact.approval_state == "not_approved"
    and .evidence.redacted_order_artifact.runtime_adapter_approved == false
    and .evidence.redacted_order_artifact.calls_memory_search == false
    and .evidence.redacted_order_artifact.runs_biocortex == false
    and .evidence.redacted_order_artifact.changes_memory_search_order == false
    and .evidence.redacted_order_artifact.ordering_behavior_connected == false
    and .current_permissions.may_implement_opt_in_experiment == false
    and .requested_permission_if_human_authorizes.may_affect_only_explicitly_opted_in_fts_calls == true
    and .requested_permission_if_human_authorizes.requires_runtime_trial_review_packet == true
    and .requested_permission_if_human_authorizes.accepts_optional_order_diff_packet == true
    and .requested_permission_if_human_authorizes.accepts_optional_redacted_order_artifact == true
    and (.not_requested | index("default_retrieval_influence_fts"))
    and (.not_requested | index("runtime_adapter_approved"))
' "$opt_in_auth_template" >/dev/null

opt_in_auth_decision="docs/design/fixtures/biocortex-retrieval-opt-in-authorization-decision-2026-06-11.json"
jq -e '
    .schema == "agent_bridge.biocortex_retrieval.opt_in_authorization_decision.v0"
    and .decision == "authorized"
    and .authorization_state == "authorized"
    and .authorized_scope == "opt_in_experiment"
    and .implementation_allowed == true
    and .runtime_adapter_approved == false
    and .default_search_order_change_allowed == false
    and .default_retrieval_influence_authorized == false
    and .hybrid_retrieval_influence_authorized == false
    and .semantic_retrieval_influence_authorized == false
    and .authorized_implementation.may_add_cargo_feature == "biocortex-retrieval-opt-in"
    and .authorized_implementation.may_add_runtime_enable_env == "AB_BIOCORTEX_RETRIEVAL_OPT_IN"
    and .authorized_implementation.may_affect_only_explicitly_opted_in_fts_calls == true
    and .authorized_implementation.must_keep_operator_disable == "AB_BIOCORTEX_RETRIEVAL_DISABLE"
    and .authorized_implementation.must_return_baseline_without_per_call_opt_in == true
    and (.not_authorized | index("runtime_adapter_approved"))
    and (.not_authorized | index("default_search_order_change_allowed"))
    and .requires_post_implementation_review_before_use == true
' "$opt_in_auth_decision" >/dev/null

jq -e '
    .schema == "agent_bridge.biocortex_retrieval.runtime_approval_packet_preview.v0"
    and .approval_state == "not_approved"
    and .runtime_adapter_approved == false
    and .writes_approval == false
    and .approval_writes_allowed == false
    and .default_search_order_change_allowed == false
    and .ready_for_human_approval_review == false
    and .approval_model.agent_technical_attestation_required == true
    and .approval_model.human_authorization_required == true
    and .approval_model.agent_attestation_can_replace_human_authorization == false
    and .agent_technical_attestation.attestor == "codex"
    and .agent_technical_attestation.decision == "approve_continue_design"
    and .agent_technical_attestation.can_authorize_runtime_influence == false
    and .human_authorization.status == "not_authorized"
    and .human_authorization.scope == "none"
    and .human_authorization.can_be_replaced_by_agent_attestation == false
    and .requires_separate_human_approval == true
    and .evidence.audit_links.memory_key == "biocortex_agent_technical_attestation_20260611"
    and (.missing_evidence | length) > 0
' docs/design/fixtures/biocortex-retrieval-agent-technical-attestation-2026-06-11.json >/dev/null

extract_json_summary() {
    awk '
        /^```json$/ { in_json=1; next }
        /^```$/ && in_json { in_json=0; next }
        in_json { print }
    ' "$1"
}

assert_summary_pass() {
    local report="$1"
    local expected_status="$2"
    local label="$3"
    local summary="$tmpdir/${label}.summary.json"
    extract_json_summary "$report" > "$summary"
    jq -e --arg status "$expected_status" '
        .status == $status
        and .read_only == true
        and .gate.runtime_adapter_approved == false
        and .gate.requires_human_review == true
        and .side_signal_coverage >= 0.8
        and .regressions == 0
        and .mrr_delta > 0
    ' "$summary" >/dev/null
}

run cargo check -p ab-bridge --no-default-features

approval_packet="$tmpdir/runtime-approval-packet-preview.json"
run cargo run -p ab-bridge --no-default-features \
    -- bio-cortex retrieval-approval-packet --json > "$approval_packet"
jq -e '
    .schema == "agent_bridge.biocortex_retrieval.runtime_approval_packet_preview.v0"
    and .approval_state == "not_approved"
    and .default_decision == "keep_shadow_only"
    and .runtime_adapter_approved == false
    and .writes_approval == false
    and .approval_writes_allowed == false
    and .default_search_order_change_allowed == false
    and .requires_separate_human_approval == true
    and .ready_for_human_approval_review == false
    and .approval_model.agent_technical_attestation_required == true
    and .approval_model.human_authorization_required == true
    and .approval_model.agent_attestation_can_replace_human_authorization == false
    and .agent_technical_attestation.can_authorize_runtime_influence == false
    and .human_authorization.status == "not_authorized"
    and .human_authorization.can_be_replaced_by_agent_attestation == false
    and (.missing_evidence | length) > 0
' "$approval_packet" >/dev/null

review_bundle="$tmpdir/runtime-approval-review"
run scripts/prepare-biocortex-retrieval-approval-review.sh \
    --out-dir "$review_bundle" \
    --reviewer "verify-bundle" \
    --agent-attestor "verify-bundle" \
    --agent-attestation-decision "technical_review_pending" \
    --human-authorization-scope "none" \
    --memory-key "verify_bundle_memory_placeholder" \
    --forum-decision-post-id "verify_bundle_forum_placeholder"
jq -e '
    .schema == "agent_bridge.biocortex_retrieval.runtime_approval_packet_preview.v0"
    and .approval_state == "not_approved"
    and .runtime_adapter_approved == false
    and .approval_writes_allowed == false
    and .default_search_order_change_allowed == false
    and .ready_for_human_approval_review == false
    and .approval_model.agent_technical_attestation_required == true
    and .approval_model.human_authorization_required == true
    and .approval_model.agent_attestation_can_replace_human_authorization == false
    and .agent_technical_attestation.can_authorize_runtime_influence == false
    and .human_authorization.status == "not_authorized"
    and .human_authorization.scope == "none"
    and .human_authorization.can_be_replaced_by_agent_attestation == false
    and (.missing_evidence | length) > 0
' "$review_bundle/approval-packet-preview.json" >/dev/null
test -s "$review_bundle/forum-post-template.md"
test -s "$review_bundle/memory-note-template.md"

run cargo check -p ab-bridge --no-default-features --features biocortex-retrieval-shadow
run cargo check -p ab-bridge --no-default-features --features biocortex-retrieval-opt-in

run cargo test -p ab-store --lib --no-default-features \
    biocortex_contract_ -- --nocapture
run cargo test -p ab-store --lib --no-default-features \
    memory_search_biocortex_opt_in_wrapper_ -- --nocapture --test-threads=1
run cargo test -p ab-bridge --lib --no-default-features \
    biocortex_shadow::tests::retrieval_ -- --nocapture
run cargo test -p ab-bridge --lib --no-default-features \
    --features biocortex-retrieval-shadow \
    biocortex_retrieval_shadow_schema_is_explicit_and_readonly -- --nocapture
run cargo test -p ab-bridge --lib --no-default-features \
    --features biocortex-retrieval-opt-in \
    biocortex_shadow::tests::retrieval_opt_in_gate_requires_feature_runtime_and_call_opt_in -- --nocapture
run cargo test -p ab-bridge --lib --no-default-features \
    opt_in_audit_ -- --nocapture --test-threads=1
run cargo test -p ab-bridge --lib --no-default-features \
    --features biocortex-retrieval-opt-in \
    opt_in_audit_ -- --nocapture --test-threads=1
run cargo test -p ab-bridge --lib --no-default-features \
    biocortex_retrieval_opt_in_status_ -- --nocapture
run cargo test -p ab-bridge --lib --no-default-features \
    biocortex_retrieval_opt_in_dry_run_ -- --nocapture
run cargo test -p ab-bridge --lib --no-default-features \
    opt_in_review_packet_ -- --nocapture --test-threads=1
run cargo test -p ab-bridge --lib --no-default-features \
    opt_in_execution_packet_ -- --nocapture --test-threads=1
run cargo test -p ab-bridge --lib --no-default-features \
    opt_in_runtime_trial_ -- --nocapture --test-threads=1
run cargo test -p ab-bridge --lib --no-default-features \
    opt_in_runtime_trial_review_packet_ -- --nocapture --test-threads=1
run cargo test -p ab-bridge --lib --no-default-features \
    biocortex_retrieval_opt_in_runtime_trial_review_packet_ -- --nocapture
run cargo test -p ab-bridge --lib --no-default-features \
    opt_in_order_diff_packet_ -- --nocapture --test-threads=1
run cargo test -p ab-bridge --lib --no-default-features \
    biocortex_retrieval_opt_in_order_diff_packet_ -- --nocapture
run cargo test -p ab-bridge --lib --no-default-features \
    opt_in_redacted_order_artifact_ -- --nocapture --test-threads=1
run cargo test -p ab-bridge --lib --no-default-features \
    biocortex_retrieval_opt_in_redacted_order_artifact_ -- --nocapture
run cargo test -p ab-bridge --lib --no-default-features \
    opt_in_authorization_decision_packet_ -- --nocapture --test-threads=1
run cargo test -p ab-bridge --lib --no-default-features \
    biocortex_retrieval_opt_in_authorization_decision_packet_ -- --nocapture
run cargo test -p ab-bridge --lib --no-default-features \
    opt_in_post_implementation_review_gate_ -- --nocapture --test-threads=1
run cargo test -p ab-bridge --lib --no-default-features \
    biocortex_retrieval_opt_in_post_implementation_review_gate_ -- --nocapture
run cargo test -p ab-bridge --lib --no-default-features \
    opt_in_runtime_influence_review_request_ -- --nocapture --test-threads=1
run cargo test -p ab-bridge --lib --no-default-features \
    biocortex_retrieval_opt_in_runtime_influence_review_request_ -- --nocapture
run cargo test -p ab-bridge --lib --no-default-features \
    opt_in_runtime_influence_decision_packet_ -- --nocapture --test-threads=1
run cargo test -p ab-bridge --lib --no-default-features \
    biocortex_retrieval_opt_in_runtime_influence_decision_packet_ -- --nocapture
run cargo test -p ab-bridge --lib --no-default-features \
    biocortex_retrieval_opt_in_store_trial_ -- --nocapture --test-threads=1
run env AB_BIOCORTEX_RS="$biocortex_rs" AB_BIOCORTEX_RETRIEVAL_OPT_IN=1 \
    cargo test -p ab-bridge --lib --no-default-features --features biocortex-retrieval-opt-in \
    biocortex_retrieval_opt_in_store_trial_ -- --nocapture --test-threads=1

opt_in_status_disabled="$tmpdir/opt-in-status-disabled.json"
run cargo run -p ab-bridge --no-default-features -- \
    bio-cortex retrieval-opt-in-status \
    --mode hybrid \
    --per-call-opt-in \
    --query "verify secret query text" \
    --baseline-key verify_secret_key_a \
    --baseline-key verify_secret_key_b \
    --latency-ms 1.23456 \
    --json > "$opt_in_status_disabled"
jq -e '
    .schema == "agent_bridge.biocortex_retrieval.opt_in_call_audit.v0"
    and .mode == "hybrid"
    and .mode_authorized == false
    and .baseline_order.key_count == 2
    and .baseline_order.raw_keys_included == false
    and .baseline_order.content_included == false
    and .fallback.reason == "mode_not_authorized"
    and .store_contract.schema == "agent_bridge.store.memory_search.biocortex_opt_in_contract.v0"
    and .store_contract.returned_order_source == "baseline"
    and .store_contract.baseline_returned == true
    and .store_contract.fallback_reason == "mode_not_authorized"
    and .store_contract.changes_memory_search_order == false
    and .store_contract.decision.mode_authorized == false
    and .store_contract.decision.audit_requirements.raw_keys_included == false
    and .store_contract.decision.audit_requirements.content_included == false
    and .ordering_behavior_connected == false
    and .may_change_search_order_now == false
    and .changes_memory_search_order == false
' "$opt_in_status_disabled" >/dev/null
if grep -q 'verify secret query text\|verify_secret_key_a\|verify_secret_key_b' "$opt_in_status_disabled"; then
    echo "opt-in status leaked raw query/key data" >&2
    exit 1
fi

opt_in_status_ready="$tmpdir/opt-in-status-ready.json"
run env AB_BIOCORTEX_RETRIEVAL_OPT_IN=1 \
    cargo run -p ab-bridge --no-default-features --features biocortex-retrieval-opt-in -- \
    bio-cortex retrieval-opt-in-status \
    --mode fts \
    --per-call-opt-in \
    --query "verify ready secret query" \
    --baseline-key verify_ready_secret_key \
    --json > "$opt_in_status_ready"
jq -e '
    .schema == "agent_bridge.biocortex_retrieval.opt_in_call_audit.v0"
    and .mode == "fts"
    and .mode_authorized == true
    and .gate.status == "ready_for_explicit_opt_in_experiment"
    and .gate.ready_for_explicit_opt_in_experiment == true
    and .baseline_order.key_count == 1
    and .fallback.reason == "ordering_behavior_not_connected"
    and .store_contract.schema == "agent_bridge.store.memory_search.biocortex_opt_in_contract.v0"
    and .store_contract.returned_order_source == "baseline"
    and .store_contract.baseline_returned == true
    and .store_contract.fallback_reason == "ordering_behavior_not_connected"
    and any(.store_contract.decision.blocking_reasons[]; . == "runtime_adapter_not_approved")
    and .store_contract.changes_memory_search_order == false
    and .store_contract.decision.mode_authorized == true
    and .side_signal.status == "not_run_ordering_behavior_not_connected"
    and .ordering_behavior_connected == false
    and .may_change_search_order_now == false
    and .changes_memory_search_order == false
' "$opt_in_status_ready" >/dev/null
if grep -q 'verify ready secret query\|verify_ready_secret_key' "$opt_in_status_ready"; then
    echo "opt-in ready status leaked raw query/key data" >&2
    exit 1
fi

opt_in_dry_run_disabled="$tmpdir/opt-in-dry-run-disabled.json"
run cargo run -p ab-bridge --no-default-features -- \
    bio-cortex retrieval-opt-in-dry-run \
    --mode semantic \
    --per-call-opt-in \
    --query "verify dry secret query text" \
    --baseline-key verify_dry_secret_key_a \
    --baseline-key verify_dry_secret_key_b \
    --timeout-ms 777 \
    --coverage-threshold 0.75 \
    --json > "$opt_in_dry_run_disabled"
jq -e '
    .schema == "agent_bridge.biocortex_retrieval.opt_in_dry_run_plan.v0"
    and .read_only == true
    and .dry_run == true
    and .mode == "semantic"
    and .mode_authorized == false
    and .baseline_order.key_count == 2
    and .baseline_order.raw_keys_included == false
    and .baseline_order.content_included == false
    and .planner_result.returned_order_source == "baseline"
    and .planner_result.fallback_reason == "mode_not_authorized"
    and .planned_side_signal.status == "not_run_dry_run"
    and .planned_side_signal.timeout_ms == 777
    and .planned_side_signal.coverage_threshold == 0.75
    and .store_contract.schema == "agent_bridge.store.memory_search.biocortex_opt_in_contract.v0"
    and .store_contract.returned_order_source == "baseline"
    and .store_contract.fallback_reason == "mode_not_authorized"
    and .store_contract.changes_memory_search_order == false
    and .calls_memory_search == false
    and .runs_biocortex == false
    and .changes_memory_search_order == false
    and .ordering_behavior_connected == false
' "$opt_in_dry_run_disabled" >/dev/null
if grep -q 'verify dry secret query text\|verify_dry_secret_key_a\|verify_dry_secret_key_b' "$opt_in_dry_run_disabled"; then
    echo "opt-in dry-run leaked raw query/key data" >&2
    exit 1
fi

opt_in_dry_run_ready="$tmpdir/opt-in-dry-run-ready.json"
run env AB_BIOCORTEX_RETRIEVAL_OPT_IN=1 \
    cargo run -p ab-bridge --no-default-features --features biocortex-retrieval-opt-in -- \
    bio-cortex retrieval-opt-in-dry-run \
    --mode fts \
    --per-call-opt-in \
    --query "verify dry ready query" \
    --baseline-key verify_dry_ready_key \
    --json > "$opt_in_dry_run_ready"
jq -e '
    .schema == "agent_bridge.biocortex_retrieval.opt_in_dry_run_plan.v0"
    and .read_only == true
    and .dry_run == true
    and .mode == "fts"
    and .mode_authorized == true
    and .gate.status == "ready_for_explicit_opt_in_experiment"
    and .baseline_order.key_count == 1
    and .planner_result.returned_order_source == "baseline"
    and .planner_result.fallback_reason == "ordering_behavior_not_connected"
    and any(.planner_result.blocking_reasons[]; . == "runtime_adapter_not_approved")
    and .planned_side_signal.status == "not_run_dry_run"
    and .store_contract.schema == "agent_bridge.store.memory_search.biocortex_opt_in_contract.v0"
    and .store_contract.returned_order_source == "baseline"
    and .store_contract.fallback_reason == "ordering_behavior_not_connected"
    and .store_contract.changes_memory_search_order == false
    and .calls_memory_search == false
    and .runs_biocortex == false
    and .changes_memory_search_order == false
    and .ordering_behavior_connected == false
' "$opt_in_dry_run_ready" >/dev/null
if grep -q 'verify dry ready query\|verify_dry_ready_key' "$opt_in_dry_run_ready"; then
    echo "opt-in dry-run ready leaked raw query/key data" >&2
    exit 1
fi

opt_in_review_packet="$tmpdir/opt-in-review-packet.json"
run cargo run -p ab-bridge --no-default-features -- \
    bio-cortex retrieval-opt-in-review-packet \
    --dry-run-json "$opt_in_dry_run_ready" \
    --reviewer verify-bundle \
    --commit verify-dry-run-commit \
    --forum-post-id verify-forum-post \
    --memory-key verify-memory-key \
    --json > "$opt_in_review_packet"
jq -e '
    .schema == "agent_bridge.biocortex_retrieval.opt_in_review_packet.v0"
    and .read_only == true
    and .dry_run_consumer == true
    and .implementation_stage == "review_packet_consumer_only"
    and .input_contract.source_schema == "agent_bridge.biocortex_retrieval.opt_in_dry_run_plan.v0"
    and .input_contract.dry_run_plan_included == false
    and .input_contract.raw_query_included == false
    and .input_contract.raw_keys_included == false
    and .input_contract.content_included == false
    and .review_target.mode == "fts"
    and .review_target.mode_authorized == true
    and .dry_run_summary.baseline_order.key_count == 1
    and .dry_run_summary.baseline_order.raw_keys_included == false
    and .dry_run_summary.baseline_order.content_included == false
    and .dry_run_summary.planner_result.returned_order_source == "baseline"
    and .dry_run_summary.planner_result.fallback_reason == "ordering_behavior_not_connected"
    and .dry_run_summary.planned_side_signal.status == "not_run_dry_run"
    and .dry_run_summary.planned_side_signal.raw_included == false
    and .boundary_check.review_ready == true
    and (.boundary_check.violations | length) == 0
    and .approval_state == "not_approved"
    and .runtime_adapter_approved == false
    and .approval_writes_allowed == false
    and .writes_approval == false
    and .calls_memory_search == false
    and .runs_biocortex == false
    and .registers_embedding_backend == false
    and .changes_memory_search_order == false
    and .ordering_behavior_connected == false
    and .may_implement_ordering_now == false
' "$opt_in_review_packet" >/dev/null
if grep -q 'verify dry ready query\|verify_dry_ready_key' "$opt_in_review_packet"; then
    echo "opt-in review packet leaked raw query/key data" >&2
    exit 1
fi

opt_in_execution_packet="$tmpdir/opt-in-execution-packet.json"
run cargo run -p ab-bridge --no-default-features -- \
    bio-cortex retrieval-opt-in-execution-packet \
    --review-packet-json "$opt_in_review_packet" \
    --per-call-opt-in \
    --attempt-id verify-execution-attempt \
    --commit verify-dry-run-commit \
    --json > "$opt_in_execution_packet"
jq -e '
    .schema == "agent_bridge.biocortex_retrieval.opt_in_execution_packet.v0"
    and .read_only == true
    and .execution_packet == true
    and .implementation_stage == "execution_packet_contract_only"
    and .input_contract.source_schema == "agent_bridge.biocortex_retrieval.opt_in_review_packet.v0"
    and .input_contract.review_packet_included == false
    and .input_contract.raw_query_included == false
    and .input_contract.raw_keys_included == false
    and .input_contract.content_included == false
    and .review_summary.review_ready == true
    and .review_summary.review_violation_count == 0
    and .review_summary.baseline_order.key_count == 1
    and .review_summary.baseline_order.raw_keys_included == false
    and .review_summary.baseline_order.content_included == false
    and .protected_adapter_contract.candidate_recall_source == "baseline_only"
    and .protected_adapter_contract.can_add_new_candidates == false
    and .protected_adapter_contract.join_key == "candidate_key"
    and .protected_adapter_contract.fail_open_return == "baseline"
    and .preflight.preflight_passed_for_baseline_only_contract == true
    and .preflight.execution_allowed == false
    and (.preflight.packet_blockers | length) == 0
    and .store_contract.schema == "agent_bridge.store.memory_search.biocortex_opt_in_contract.v0"
    and .store_contract.returned_order_source == "baseline"
    and .store_contract.changes_memory_search_order == false
    and .execution_decision.returned_order_source == "baseline"
    and .execution_decision.baseline_returned == true
    and .execution_decision.calls_memory_search_now == false
    and .execution_decision.runs_biocortex_now == false
    and .approval_state == "not_approved"
    and .runtime_adapter_approved == false
    and .approval_writes_allowed == false
    and .calls_memory_search == false
    and .runs_biocortex == false
    and .registers_embedding_backend == false
    and .changes_memory_search_order == false
    and .ordering_behavior_connected == false
    and .may_implement_ordering_now == false
' "$opt_in_execution_packet" >/dev/null
if grep -q 'verify dry ready query\|verify_dry_ready_key' "$opt_in_execution_packet"; then
    echo "opt-in execution packet leaked raw query/key data" >&2
    exit 1
fi

opt_in_runtime_trial_input="$tmpdir/opt-in-runtime-trial-input.json"
jq -n '{
    query: "verify runtime trial secret query",
    expected_key: "verify_runtime_trial_secret_key",
    candidates: [
        {
            key: "verify_runtime_trial_secret_key",
            content: "verify runtime trial secret content"
        }
    ]
}' > "$opt_in_runtime_trial_input"
opt_in_runtime_trial="$tmpdir/opt-in-runtime-trial.json"
run env AB_BIOCORTEX_RETRIEVAL_OPT_IN=1 \
    cargo run -p ab-bridge --no-default-features --features biocortex-retrieval-opt-in -- \
    bio-cortex retrieval-opt-in-runtime-trial \
    --execution-packet-json "$opt_in_execution_packet" \
    --input-json "$opt_in_runtime_trial_input" \
    --checkout "$biocortex_rs" \
    --timeout-ms 30000 \
    --coverage-threshold 0.5 \
    --attempt-id verify-runtime-trial-attempt \
    --commit verify-dry-run-commit \
    --json > "$opt_in_runtime_trial"
jq -e '
    .schema == "agent_bridge.biocortex_retrieval.opt_in_runtime_trial.v0"
    and .read_only == true
    and .runtime_trial == true
    and .implementation_stage == "baseline_preserving_runtime_trial"
    and .input_contract.source_schema == "agent_bridge.biocortex_retrieval.opt_in_execution_packet.v0"
    and .input_contract.execution_packet_included == false
    and .input_contract.raw_query_included == false
    and .input_contract.raw_keys_included == false
    and .input_contract.content_included == false
    and .runtime_preflight.side_signal_trial_allowed == true
    and (.runtime_preflight.blockers | length) == 0
    and .runtime_preflight.execution_packet_preflight_passed == true
    and .runtime_preflight.gate_ready == true
    and .runtime_preflight.candidate_count_matches_packet == true
    and .runtime_preflight.ordering_execution_allowed == false
    and .protected_adapter_contract.candidate_recall_source == "baseline_only"
    and .protected_adapter_contract.can_add_new_candidates == false
    and .protected_adapter_contract.join_key == "candidate_key"
    and .protected_adapter_contract.calls_memory_search == false
    and .protected_adapter_contract.writes_temp_corpus == true
    and .protected_adapter_contract.mutates_ab_memory == false
    and .protected_adapter_contract.registers_embedding_backend == false
    and .protected_adapter_contract.raw_query_included == false
    and .protected_adapter_contract.raw_keys_included == false
    and .protected_adapter_contract.content_included == false
    and .protected_adapter_contract.side_signal_raw_included == false
    and .baseline_order.key_count == 1
    and .baseline_order.redacted_rank_rows_included == true
    and (.baseline_order.redacted_rank_rows | length) == 1
    and (.baseline_order.redacted_rank_rows[0].key_hash | startswith("sha256:"))
    and .baseline_order.redacted_rank_rows[0].baseline_rank == 1
    and .baseline_order.raw_keys_included == false
    and .baseline_order.raw_order_keys_included == false
    and .baseline_order.content_included == false
    and .side_signal.attempted == true
    and .side_signal.status == "ok"
    and .side_signal.row_count >= 1
    and .side_signal.matched_candidate_count == 1
    and .side_signal.coverage >= 0.5
    and .side_signal.raw_included == false
    and .side_signal.candidate_keys_included == false
    and .side_signal.content_included == false
    and .advisory_result.available == true
    and .advisory_result.used_for_return_order == false
    and .advisory_result.redacted_rank_rows_included == true
    and (.advisory_result.redacted_rank_rows | length) == 1
    and (.advisory_result.redacted_rank_rows[0].key_hash | startswith("sha256:"))
    and .advisory_result.redacted_rank_rows[0].advisory_rank == 1
    and .advisory_result.raw_keys_included == false
    and .advisory_result.raw_order_keys_included == false
    and .advisory_result.content_included == false
    and .advisory_result.side_signal_raw_included == false
    and .returned_order.source == "baseline"
    and .returned_order.baseline_returned == true
    and .returned_order.hash_matches_baseline == true
    and .store_contract.returned_order_source == "baseline"
    and .store_contract.changes_memory_search_order == false
    and .approval_state == "not_approved"
    and .runtime_adapter_approved == false
    and .approval_writes_allowed == false
    and .calls_memory_search == false
    and .runs_biocortex == true
    and .registers_embedding_backend == false
    and .changes_memory_search_order == false
    and .ordering_behavior_connected == false
    and .may_implement_ordering_now == false
    and .boundary.runs_external_side_signal == true
    and .boundary.writes_temp_corpus == true
    and .boundary.calls_memory_search == false
    and .boundary.changes_memory_search_order == false
' "$opt_in_runtime_trial" >/dev/null
if grep -q 'verify runtime trial secret query\|verify_runtime_trial_secret_key\|verify runtime trial secret content' "$opt_in_runtime_trial"; then
    echo "opt-in runtime trial leaked raw query/key/content data" >&2
    exit 1
fi

opt_in_runtime_trial_review_packet="$tmpdir/opt-in-runtime-trial-review-packet.json"
run cargo run -p ab-bridge --no-default-features -- \
    bio-cortex retrieval-opt-in-runtime-trial-review-packet \
    --runtime-trial-json "$opt_in_runtime_trial" \
    --reviewer verify-bundle \
    --commit verify-dry-run-commit \
    --forum-post-id verify-forum-post \
    --memory-key verify-memory-key \
    --json > "$opt_in_runtime_trial_review_packet"
jq -e '
    .schema == "agent_bridge.biocortex_retrieval.opt_in_runtime_trial_review_packet.v0"
    and .read_only == true
    and .runtime_trial_consumer == true
    and .implementation_stage == "runtime_trial_review_packet_only"
    and .input_contract.source_schema == "agent_bridge.biocortex_retrieval.opt_in_runtime_trial.v0"
    and .input_contract.runtime_trial_packet_included == false
    and .input_contract.raw_query_included == false
    and .input_contract.raw_keys_included == false
    and .input_contract.content_included == false
    and .input_contract.side_signal_raw_included == false
    and .review_target.mode == "fts"
    and .review_target.per_call_opt_in == true
    and .review_target.commit == "verify-dry-run-commit"
    and .runtime_trial_summary.side_signal.attempted == true
    and .runtime_trial_summary.side_signal.status == "ok"
    and .runtime_trial_summary.side_signal.coverage >= 0.5
    and .runtime_trial_summary.side_signal.raw_included == false
    and .runtime_trial_summary.side_signal.candidate_keys_included == false
    and .runtime_trial_summary.side_signal.content_included == false
    and .runtime_trial_summary.advisory_result.used_for_return_order == false
    and .runtime_trial_summary.baseline_order.redacted_rank_rows_included == true
    and (.runtime_trial_summary.baseline_order.redacted_rank_rows | length) == 1
    and (.runtime_trial_summary.baseline_order.redacted_rank_rows[0].key_hash | startswith("sha256:"))
    and .runtime_trial_summary.baseline_order.redacted_rank_rows[0].baseline_rank == 1
    and .runtime_trial_summary.baseline_order.raw_order_keys_included == false
    and .runtime_trial_summary.advisory_result.redacted_rank_rows_included == true
    and (.runtime_trial_summary.advisory_result.redacted_rank_rows | length) == 1
    and (.runtime_trial_summary.advisory_result.redacted_rank_rows[0].key_hash | startswith("sha256:"))
    and .runtime_trial_summary.advisory_result.redacted_rank_rows[0].advisory_rank == 1
    and .runtime_trial_summary.advisory_result.raw_keys_included == false
    and .runtime_trial_summary.advisory_result.raw_order_keys_included == false
    and .runtime_trial_summary.advisory_result.content_included == false
    and .runtime_trial_summary.advisory_result.side_signal_raw_included == false
    and .runtime_trial_summary.returned_order.source == "baseline"
    and .runtime_trial_summary.returned_order.baseline_returned == true
    and .runtime_trial_summary.returned_order.hash_matches_baseline == true
    and .boundary_check.review_ready_for_baseline_runtime_trial == true
    and (.boundary_check.violations | length) == 0
    and .approval_state == "not_approved"
    and .runtime_adapter_approved == false
    and .approval_writes_allowed == false
    and .writes_approval == false
    and .calls_memory_search == false
    and .runs_biocortex == false
    and .registers_embedding_backend == false
    and .changes_memory_search_order == false
    and .ordering_behavior_connected == false
    and .may_implement_ordering_now == false
' "$opt_in_runtime_trial_review_packet" >/dev/null
if grep -q 'verify runtime trial secret query\|verify_runtime_trial_secret_key\|verify runtime trial secret content' "$opt_in_runtime_trial_review_packet"; then
    echo "opt-in runtime trial review packet leaked raw query/key/content data" >&2
    exit 1
fi

opt_in_order_diff_packet="$tmpdir/opt-in-order-diff-packet.json"
run cargo run -p ab-bridge --no-default-features -- \
    bio-cortex retrieval-opt-in-order-diff-packet \
    --source-json "$opt_in_runtime_trial_review_packet" \
    --reviewer verify-bundle \
    --commit verify-dry-run-commit \
    --forum-post-id verify-forum-post \
    --memory-key verify-memory-key \
    --json > "$opt_in_order_diff_packet"
jq -e '
    .schema == "agent_bridge.biocortex_retrieval.opt_in_order_diff_packet.v0"
    and .read_only == true
    and .order_diff_packet == true
    and .source_packet_consumer == true
    and .implementation_stage == "order_diff_review_packet_only"
    and .input_contract.source_schema == "agent_bridge.biocortex_retrieval.opt_in_runtime_trial_review_packet.v0"
    and .input_contract.source_packet_included == false
    and .input_contract.raw_query_included == false
    and .input_contract.raw_keys_included == false
    and .input_contract.content_included == false
    and .input_contract.side_signal_raw_included == false
    and .review_target.source_kind == "runtime_trial_review_packet"
    and .order_comparison.baseline_order.key_count == 1
    and .order_comparison.baseline_order.raw_keys_included == false
    and .order_comparison.baseline_order.content_included == false
    and .order_comparison.advisory_order.available == true
    and .order_comparison.advisory_order.used_for_return_order == false
    and .order_comparison.advisory_order.raw_keys_included == false
    and .order_comparison.advisory_order.content_included == false
    and .order_comparison.advisory_order.side_signal_raw_included == false
    and .order_comparison.hash_diff.order_hashes_comparable == true
    and (.order_comparison.hash_diff.order_hash_changed | type) == "boolean"
    and .order_comparison.hash_diff.top_key_hashes_comparable == true
    and (.order_comparison.hash_diff.top_key_changed | type) == "boolean"
    and .order_comparison.expected_key_rank.rank_delta_advisory_minus_baseline == 0
    and .order_comparison.expected_key_rank.direction == "unchanged"
    and .order_comparison.returned_order.source == "baseline"
    and .order_comparison.returned_order.baseline_returned == true
    and .order_comparison.returned_order.hash_matches_baseline == true
    and .order_comparison.returned_order.actual_return_order_changed == false
    and .order_comparison.unavailable_metrics.top_k_overlap == "not_computed_no_raw_order_keys"
    and .order_comparison.unavailable_metrics.rank_delta_distribution == "not_computed_no_raw_order_keys"
    and .order_comparison.unavailable_metrics.per_key_movements == "not_computed_no_raw_order_keys"
    and .boundary_check.diff_ready == true
    and (.boundary_check.violations | length) == 0
    and .source_execution_summary.source_runs_biocortex == false
    and .source_execution_summary.order_diff_packet_runs_biocortex == false
    and .source_execution_summary.order_diff_packet_calls_memory_search == false
    and .approval_state == "not_approved"
    and .runtime_adapter_approved == false
    and .approval_writes_allowed == false
    and .writes_approval == false
    and .calls_memory_search == false
    and .runs_biocortex == false
    and .registers_embedding_backend == false
    and .changes_memory_search_order == false
    and .ordering_behavior_connected == false
    and .may_implement_ordering_now == false
' "$opt_in_order_diff_packet" >/dev/null
if grep -q 'verify runtime trial secret query\|verify_runtime_trial_secret_key\|verify runtime trial secret content' "$opt_in_order_diff_packet"; then
    echo "opt-in order diff packet leaked raw query/key/content data" >&2
    exit 1
fi

opt_in_redacted_order_artifact="$tmpdir/opt-in-redacted-order-artifact.json"
run cargo run -p ab-bridge --no-default-features -- \
    bio-cortex retrieval-opt-in-redacted-order-artifact \
    --source-json "$opt_in_runtime_trial_review_packet" \
    --reviewer verify-bundle \
    --commit verify-dry-run-commit \
    --forum-post-id verify-forum-post \
    --memory-key verify-memory-key \
    --json > "$opt_in_redacted_order_artifact"
jq -e '
    .schema == "agent_bridge.biocortex_retrieval.opt_in_redacted_order_artifact.v0"
    and .read_only == true
    and .redacted_order_artifact == true
    and .source_packet_consumer == true
    and .implementation_stage == "redacted_order_review_artifact_only"
    and .input_contract.source_schema == "agent_bridge.biocortex_retrieval.opt_in_runtime_trial_review_packet.v0"
    and .input_contract.source_packet_included == false
    and .input_contract.raw_query_included == false
    and .input_contract.raw_keys_included == false
    and .input_contract.raw_order_keys_included == false
    and .input_contract.content_included == false
    and .input_contract.side_signal_raw_included == false
    and .input_contract.hashes_included == true
    and .review_target.source_kind == "runtime_trial_review_packet"
    and .redacted_order_comparison.baseline_order.key_count == 1
    and .redacted_order_comparison.baseline_order.redacted_rank_rows_included == true
    and (.redacted_order_comparison.baseline_order.rank_rows | length) == 1
    and (.redacted_order_comparison.baseline_order.rank_rows[0].key_hash | startswith("sha256:"))
    and .redacted_order_comparison.baseline_order.rank_rows[0].baseline_rank == 1
    and .redacted_order_comparison.baseline_order.raw_keys_included == false
    and .redacted_order_comparison.baseline_order.raw_order_keys_included == false
    and .redacted_order_comparison.baseline_order.content_included == false
    and .redacted_order_comparison.advisory_order.available == true
    and .redacted_order_comparison.advisory_order.used_for_return_order == false
    and .redacted_order_comparison.advisory_order.redacted_rank_rows_included == true
    and (.redacted_order_comparison.advisory_order.rank_rows | length) == 1
    and (.redacted_order_comparison.advisory_order.rank_rows[0].key_hash | startswith("sha256:"))
    and .redacted_order_comparison.advisory_order.rank_rows[0].advisory_rank == 1
    and .redacted_order_comparison.advisory_order.raw_keys_included == false
    and .redacted_order_comparison.advisory_order.raw_order_keys_included == false
    and .redacted_order_comparison.advisory_order.content_included == false
    and .redacted_order_comparison.advisory_order.side_signal_raw_included == false
    and (.redacted_order_comparison.top_k_overlap[] | select(.k == 1) | .overlap_count) == 1
    and (.redacted_order_comparison.top_k_overlap[] | select(.k == 1) | .jaccard) == 1
    and .redacted_order_comparison.rank_delta_distribution.improved_count == 0
    and .redacted_order_comparison.rank_delta_distribution.regressed_count == 0
    and .redacted_order_comparison.rank_delta_distribution.unchanged_count == 1
    and .redacted_order_comparison.rank_delta_distribution.max_abs_delta == 0
    and (.redacted_order_comparison.per_key_movements | length) == 1
    and .redacted_order_comparison.per_key_movements[0].rank_delta_advisory_minus_baseline == 0
    and .redacted_order_comparison.per_key_movements[0].direction == "unchanged"
    and .redacted_order_comparison.returned_order.source == "baseline"
    and .redacted_order_comparison.returned_order.baseline_returned == true
    and .redacted_order_comparison.returned_order.hash_matches_baseline == true
    and .redacted_order_comparison.returned_order.actual_return_order_changed == false
    and .boundary_check.artifact_ready == true
    and (.boundary_check.violations | length) == 0
    and .boundary_check.redacted_rows_comparable == true
    and .source_execution_summary.redacted_order_artifact_runs_biocortex == false
    and .source_execution_summary.redacted_order_artifact_calls_memory_search == false
    and .approval_state == "not_approved"
    and .runtime_adapter_approved == false
    and .approval_writes_allowed == false
    and .writes_approval == false
    and .calls_memory_search == false
    and .runs_biocortex == false
    and .registers_embedding_backend == false
    and .changes_memory_search_order == false
    and .actual_return_order_changed == false
    and .ordering_behavior_connected == false
    and .may_implement_ordering_now == false
' "$opt_in_redacted_order_artifact" >/dev/null
if grep -q 'verify runtime trial secret query\|verify_runtime_trial_secret_key\|verify runtime trial secret content' "$opt_in_redacted_order_artifact"; then
    echo "opt-in redacted order artifact leaked raw query/key/content data" >&2
    exit 1
fi

run env AB_BIOCORTEX_RS="$biocortex_rs" CARGO_INCREMENTAL=0 \
    cargo run -p ab-bridge \
    --example biocortex_retrieval_shadow_acceptance \
    --features biocortex-retrieval-shadow

runtime_proof="$tmpdir/runtime-boundary-proof"
run scripts/prove-biocortex-retrieval-runtime-boundary.sh \
    --out-dir "$runtime_proof" \
    --checkout "$biocortex_rs" \
    --samples 3
jq -e '
    .schema == "agent_bridge.biocortex_retrieval.runtime_boundary_proof.v0"
    and .read_only == true
    and .writes_approval == false
    and .runtime_adapter_approved == false
    and .default_search_order_changed == false
    and .proof.default_disabled.status == "runtime_disabled"
    and .proof.kill_switch.status == "operator_disabled"
    and .proof.enabled_shadow.status == "ok"
    and .latency.sample_count == 3
    and .boundary.calls_memory_search == false
    and .boundary.changes_memory_search_order == false
' "$runtime_proof/proof-summary.json" >/dev/null

opt_in_auth_request="$tmpdir/opt-in-authorization-request"
run scripts/prepare-biocortex-retrieval-opt-in-authorization-request.sh \
    --out-dir "$opt_in_auth_request" \
    --reviewer "verify-bundle" \
    --runtime-proof-summary "$runtime_proof/proof-summary.json" \
    --runtime-trial-review-packet "$opt_in_runtime_trial_review_packet" \
    --order-diff-packet "$opt_in_order_diff_packet" \
    --redacted-order-artifact "$opt_in_redacted_order_artifact" \
    --memory-key "verify_bundle_memory_placeholder" \
    --forum-decision-post-id "verify_bundle_forum_placeholder"
jq -e '
    .schema == "agent_bridge.biocortex_retrieval.opt_in_authorization_request.v0"
    and .status == "request_prepared"
    and .approval_state == "opt_in_implementation_authorized"
    and .authorization_state == "authorized_for_opt_in_implementation"
    and .request_scope == "opt_in_experiment"
    and .runtime_adapter_approved == false
    and .default_search_order_change_allowed == false
    and .implementation_allowed == true
    and .writes_approval == false
    and .accepts_optional_order_diff_packet == true
    and .accepts_optional_redacted_order_artifact == true
    and .opt_in_plan.status == "store_opt_in_runtime_adapter_connection_implemented"
    and .opt_in_plan.order_diff_packet_implemented == true
    and .opt_in_plan.authorization_request_order_diff_evidence_implemented == true
    and .opt_in_plan.redacted_order_artifact_implemented == true
    and .opt_in_plan.authorization_request_redacted_order_artifact_evidence_implemented == true
    and .opt_in_plan.store_opt_in_search_wrapper_implemented == true
    and .opt_in_plan.authorization_decision_consumer_implemented == true
    and .opt_in_plan.post_implementation_review_gate_implemented == true
    and .opt_in_plan.runtime_influence_review_request_implemented == true
    and .opt_in_plan.runtime_influence_decision_packet_implemented == true
    and .opt_in_plan.store_opt_in_order_connection_implemented == true
    and .opt_in_plan.store_opt_in_runtime_adapter_connection_implemented == true
    and .opt_in_plan.ordering_behavior_connected == false
    and .opt_in_plan.explicit_opt_in_fts_ordering_behavior_connected == true
    and .opt_in_plan.explicit_opt_in_fts_runtime_adapter_connected == true
    and .opt_in_plan.implemented_gate_skeleton.ordering_behavior_connected == false
    and .opt_in_plan.implemented_gate_skeleton.may_change_search_order_now == false
    and .opt_in_plan.implemented_audit_shape.ordering_behavior_connected == false
    and .opt_in_plan.implemented_audit_shape.raw_keys_included == false
    and .opt_in_plan.implemented_audit_shape.content_included == false
    and .opt_in_plan.implemented_status_surface.mcp_tool == "biocortex_retrieval_opt_in_status"
    and .opt_in_plan.implemented_status_surface.raw_keys_included == false
    and .opt_in_plan.implemented_status_surface.content_included == false
    and .opt_in_plan.implemented_status_surface.ordering_behavior_connected == false
    and .opt_in_plan.implemented_store_contract.schema == "agent_bridge.store.memory_search.biocortex_opt_in_contract.v0"
    and .opt_in_plan.implemented_store_contract.authorized_mode == "fts"
    and .opt_in_plan.implemented_store_contract.fallback_returns_baseline == true
    and .opt_in_plan.implemented_store_contract.raw_query_included == false
    and .opt_in_plan.implemented_store_contract.raw_keys_included == false
    and .opt_in_plan.implemented_store_contract.content_included == false
    and .opt_in_plan.implemented_store_contract.ordering_behavior_connected == false
    and .opt_in_plan.implemented_store_opt_in_search_wrapper.method == "StateStore::memory_search_biocortex_opt_in"
    and .opt_in_plan.implemented_store_opt_in_search_wrapper.options_type == "BioCortexRetrievalOptInSearchOptions"
    and .opt_in_plan.implemented_store_opt_in_search_wrapper.outcome_type == "BioCortexRetrievalOptInSearchOutcome"
    and .opt_in_plan.implemented_store_opt_in_search_wrapper.redacted_audit_type == "BioCortexRetrievalOptInSearchAudit"
    and .opt_in_plan.implemented_store_opt_in_search_wrapper.redacted_audit_schema == "agent_bridge.store.memory_search.biocortex_opt_in_search_audit.v0"
    and .opt_in_plan.implemented_store_opt_in_search_wrapper.calls_existing_memory_search == true
    and .opt_in_plan.implemented_store_opt_in_search_wrapper.uses_existing_store_contract == true
    and .opt_in_plan.implemented_store_opt_in_search_wrapper.returns_baseline_order == true
    and .opt_in_plan.implemented_store_opt_in_search_wrapper.redacted_audit_only == true
    and .opt_in_plan.implemented_store_opt_in_search_wrapper.raw_query_included_in_audit == false
    and .opt_in_plan.implemented_store_opt_in_search_wrapper.raw_keys_included_in_audit == false
    and .opt_in_plan.implemented_store_opt_in_search_wrapper.content_included_in_audit == false
    and .opt_in_plan.implemented_store_opt_in_search_wrapper.runs_biocortex == false
    and .opt_in_plan.implemented_store_opt_in_search_wrapper.registers_embedding_backend == false
    and .opt_in_plan.implemented_store_opt_in_search_wrapper.runtime_adapter_approved == false
    and .opt_in_plan.implemented_store_opt_in_search_wrapper.changes_memory_search_order == false
    and .opt_in_plan.implemented_store_opt_in_search_wrapper.ordering_behavior_connected == false
    and .opt_in_plan.implemented_store_opt_in_search_wrapper.default_calls_unchanged == true
    and .opt_in_plan.implemented_store_opt_in_search_wrapper.may_implement_ordering_now == false
    and .opt_in_plan.implemented_store_opt_in_order_connection.method == "StateStore::memory_search_biocortex_opt_in"
    and .opt_in_plan.implemented_store_opt_in_order_connection.options_type == "BioCortexRetrievalOptInSearchOptions"
    and .opt_in_plan.implemented_store_opt_in_order_connection.side_signal_type == "BioCortexRetrievalOptInSideSignal"
    and .opt_in_plan.implemented_store_opt_in_order_connection.side_signal_summary_type == "BioCortexRetrievalOptInSideSignalSummary"
    and .opt_in_plan.implemented_store_opt_in_order_connection.implementation_stage == "store_opt_in_order_connection"
    and .opt_in_plan.implemented_store_opt_in_order_connection.authorized_scope == "explicit_opt_in_fts_runtime_influence"
    and .opt_in_plan.implemented_store_opt_in_order_connection.authorized_mode == "fts"
    and .opt_in_plan.implemented_store_opt_in_order_connection.requires_per_call_opt_in == true
    and .opt_in_plan.implemented_store_opt_in_order_connection.requires_compile_feature_enabled == true
    and .opt_in_plan.implemented_store_opt_in_order_connection.requires_runtime_enabled == true
    and .opt_in_plan.implemented_store_opt_in_order_connection.requires_runtime_adapter_approved == true
    and .opt_in_plan.implemented_store_opt_in_order_connection.requires_ordering_behavior_connected == true
    and .opt_in_plan.implemented_store_opt_in_order_connection.requires_operator_disable_absent == true
    and .opt_in_plan.implemented_store_opt_in_order_connection.requires_side_signal_coverage_threshold == true
    and .opt_in_plan.implemented_store_opt_in_order_connection.default_side_signal_coverage_threshold == 0.8
    and .opt_in_plan.implemented_store_opt_in_order_connection.default_blend_alpha == 0.8
    and .opt_in_plan.implemented_store_opt_in_order_connection.returns_experimental_order_when_all_gates_pass == true
    and .opt_in_plan.implemented_store_opt_in_order_connection.fallback_returns_baseline == true
    and .opt_in_plan.implemented_store_opt_in_order_connection.baseline_candidate_recall_source == "memory_search"
    and .opt_in_plan.implemented_store_opt_in_order_connection.side_signal_join_key == "candidate_key"
    and .opt_in_plan.implemented_store_opt_in_order_connection.side_signal_scores_in_audit == false
    and .opt_in_plan.implemented_store_opt_in_order_connection.raw_query_included_in_audit == false
    and .opt_in_plan.implemented_store_opt_in_order_connection.raw_keys_included_in_audit == false
    and .opt_in_plan.implemented_store_opt_in_order_connection.content_included_in_audit == false
    and .opt_in_plan.implemented_store_opt_in_order_connection.runs_biocortex == false
    and .opt_in_plan.implemented_store_opt_in_order_connection.registers_embedding_backend == false
    and .opt_in_plan.implemented_store_opt_in_order_connection.default_memory_search_unchanged == true
    and .opt_in_plan.implemented_store_opt_in_order_connection.hybrid_and_semantic_unchanged == true
    and .opt_in_plan.implemented_store_opt_in_order_connection.default_search_order_change_allowed == false
    and .opt_in_plan.implemented_store_opt_in_order_connection.explicit_opt_in_fts_ordering_behavior_connected == true
    and .opt_in_plan.implemented_store_opt_in_runtime_adapter_connection.mcp_tool == "biocortex_retrieval_opt_in_store_trial"
    and .opt_in_plan.implemented_store_opt_in_runtime_adapter_connection.schema == "agent_bridge.biocortex_retrieval.opt_in_store_trial.v0"
    and .opt_in_plan.implemented_store_opt_in_runtime_adapter_connection.implementation_stage == "store_opt_in_runtime_adapter_connection"
    and .opt_in_plan.implemented_store_opt_in_runtime_adapter_connection.authorized_scope == "explicit_opt_in_fts_runtime_influence"
    and .opt_in_plan.implemented_store_opt_in_runtime_adapter_connection.authorized_mode == "fts"
    and .opt_in_plan.implemented_store_opt_in_runtime_adapter_connection.requires_runtime_influence_decision_packet == true
    and .opt_in_plan.implemented_store_opt_in_runtime_adapter_connection.requires_decision_packet_runtime_adapter_approved == true
    and .opt_in_plan.implemented_store_opt_in_runtime_adapter_connection.requires_decision_packet_ordering_connection_authorized == true
    and .opt_in_plan.implemented_store_opt_in_runtime_adapter_connection.requires_per_call_opt_in == true
    and .opt_in_plan.implemented_store_opt_in_runtime_adapter_connection.requires_compile_feature_enabled == true
    and .opt_in_plan.implemented_store_opt_in_runtime_adapter_connection.requires_runtime_enabled == true
    and .opt_in_plan.implemented_store_opt_in_runtime_adapter_connection.requires_operator_disable_absent == true
    and .opt_in_plan.implemented_store_opt_in_runtime_adapter_connection.requires_side_signal_coverage_threshold == true
    and .opt_in_plan.implemented_store_opt_in_runtime_adapter_connection.baseline_candidate_recall_source == "store_memory_search_baseline_only"
    and .opt_in_plan.implemented_store_opt_in_runtime_adapter_connection.calls_memory_search == true
    and .opt_in_plan.implemented_store_opt_in_runtime_adapter_connection.runs_biocortex == true
    and .opt_in_plan.implemented_store_opt_in_runtime_adapter_connection.calls_store_opt_in_wrapper == true
    and .opt_in_plan.implemented_store_opt_in_runtime_adapter_connection.store_wrapper_method == "StateStore::memory_search_biocortex_opt_in"
    and .opt_in_plan.implemented_store_opt_in_runtime_adapter_connection.side_signal_join_key == "candidate_key"
    and .opt_in_plan.implemented_store_opt_in_runtime_adapter_connection.can_add_new_candidates == false
    and .opt_in_plan.implemented_store_opt_in_runtime_adapter_connection.mutates_ab_memory == false
    and .opt_in_plan.implemented_store_opt_in_runtime_adapter_connection.registers_embedding_backend == false
    and .opt_in_plan.implemented_store_opt_in_runtime_adapter_connection.writes_approval == false
    and .opt_in_plan.implemented_store_opt_in_runtime_adapter_connection.raw_query_included == false
    and .opt_in_plan.implemented_store_opt_in_runtime_adapter_connection.raw_keys_included == false
    and .opt_in_plan.implemented_store_opt_in_runtime_adapter_connection.content_included == false
    and .opt_in_plan.implemented_store_opt_in_runtime_adapter_connection.side_signal_raw_included == false
    and .opt_in_plan.implemented_store_opt_in_runtime_adapter_connection.returns_redacted_order_summary == true
    and .opt_in_plan.implemented_store_opt_in_runtime_adapter_connection.returns_redacted_store_wrapper_audit == true
    and .opt_in_plan.implemented_store_opt_in_runtime_adapter_connection.fallback_returns_baseline == true
    and .opt_in_plan.implemented_store_opt_in_runtime_adapter_connection.default_memory_search_unchanged == true
    and .opt_in_plan.implemented_store_opt_in_runtime_adapter_connection.hybrid_and_semantic_unchanged == true
    and .opt_in_plan.implemented_store_opt_in_runtime_adapter_connection.default_search_order_change_allowed == false
    and .opt_in_plan.implemented_store_opt_in_runtime_adapter_connection.default_calls_unchanged == true
    and .opt_in_plan.implemented_store_opt_in_runtime_adapter_connection.explicit_opt_in_fts_runtime_adapter_connected == true
    and .opt_in_plan.implemented_authorization_decision_consumer.cli == "agent-bridge bio-cortex retrieval-opt-in-authorization-decision-packet"
    and .opt_in_plan.implemented_authorization_decision_consumer.mcp_tool == "biocortex_retrieval_opt_in_authorization_decision_packet"
    and .opt_in_plan.implemented_authorization_decision_consumer.schema == "agent_bridge.biocortex_retrieval.opt_in_authorization_decision_packet.v0"
    and .opt_in_plan.implemented_authorization_decision_consumer.read_only == true
    and .opt_in_plan.implemented_authorization_decision_consumer.authorization_decision_consumer == true
    and .opt_in_plan.implemented_authorization_decision_consumer.implementation_stage == "authorization_decision_consumer_only"
    and .opt_in_plan.implemented_authorization_decision_consumer.consumes_authorization_request_summary == true
    and .opt_in_plan.implemented_authorization_decision_consumer.consumes_authorization_decision_summary == true
    and .opt_in_plan.implemented_authorization_decision_consumer.authorization_request_included == false
    and .opt_in_plan.implemented_authorization_decision_consumer.authorization_decision_included == false
    and .opt_in_plan.implemented_authorization_decision_consumer.raw_query_included == false
    and .opt_in_plan.implemented_authorization_decision_consumer.raw_keys_included == false
    and .opt_in_plan.implemented_authorization_decision_consumer.content_included == false
    and .opt_in_plan.implemented_authorization_decision_consumer.implementation_allowed == true
    and .opt_in_plan.implemented_authorization_decision_consumer.approval_state == "opt_in_implementation_authorized"
    and .opt_in_plan.implemented_authorization_decision_consumer.authorization_state == "authorized_for_opt_in_implementation"
    and .opt_in_plan.implemented_authorization_decision_consumer.runtime_adapter_approved == false
    and .opt_in_plan.implemented_authorization_decision_consumer.default_search_order_change_allowed == false
    and .opt_in_plan.implemented_authorization_decision_consumer.requires_post_implementation_review_before_use == true
    and .opt_in_plan.implemented_authorization_decision_consumer.approval_writes_allowed == false
    and .opt_in_plan.implemented_authorization_decision_consumer.writes_approval == false
    and .opt_in_plan.implemented_authorization_decision_consumer.calls_memory_search == false
    and .opt_in_plan.implemented_authorization_decision_consumer.runs_biocortex == false
    and .opt_in_plan.implemented_authorization_decision_consumer.registers_embedding_backend == false
    and .opt_in_plan.implemented_authorization_decision_consumer.changes_memory_search_order == false
    and .opt_in_plan.implemented_authorization_decision_consumer.ordering_behavior_connected == false
    and .opt_in_plan.implemented_authorization_decision_consumer.may_change_search_order_now == false
    and .opt_in_plan.implemented_authorization_decision_consumer.may_implement_ordering_now == false
    and .opt_in_plan.implemented_post_implementation_review_gate.cli == "agent-bridge bio-cortex retrieval-opt-in-post-implementation-review-gate"
    and .opt_in_plan.implemented_post_implementation_review_gate.mcp_tool == "biocortex_retrieval_opt_in_post_implementation_review_gate"
    and .opt_in_plan.implemented_post_implementation_review_gate.schema == "agent_bridge.biocortex_retrieval.opt_in_post_implementation_review_gate.v0"
    and .opt_in_plan.implemented_post_implementation_review_gate.read_only == true
    and .opt_in_plan.implemented_post_implementation_review_gate.post_implementation_review_gate == true
    and .opt_in_plan.implemented_post_implementation_review_gate.implementation_stage == "post_implementation_review_gate_only"
    and .opt_in_plan.implemented_post_implementation_review_gate.consumes_authorization_decision_packet_summary == true
    and .opt_in_plan.implemented_post_implementation_review_gate.consumes_opt_in_plan_summary == true
    and .opt_in_plan.implemented_post_implementation_review_gate.authorization_decision_packet_included == false
    and .opt_in_plan.implemented_post_implementation_review_gate.opt_in_plan_included == false
    and .opt_in_plan.implemented_post_implementation_review_gate.raw_query_included == false
    and .opt_in_plan.implemented_post_implementation_review_gate.raw_keys_included == false
    and .opt_in_plan.implemented_post_implementation_review_gate.content_included == false
    and .opt_in_plan.implemented_post_implementation_review_gate.ready_for_human_runtime_influence_review == true
    and .opt_in_plan.implemented_post_implementation_review_gate.post_implementation_review_completed == false
    and .opt_in_plan.implemented_post_implementation_review_gate.runtime_adapter_review_completed == false
    and .opt_in_plan.implemented_post_implementation_review_gate.ordering_behavior_review_completed == false
    and .opt_in_plan.implemented_post_implementation_review_gate.approval_state == "not_approved"
    and .opt_in_plan.implemented_post_implementation_review_gate.authorization_state == "requires_separate_human_runtime_influence_review"
    and .opt_in_plan.implemented_post_implementation_review_gate.implementation_allowed == false
    and .opt_in_plan.implemented_post_implementation_review_gate.runtime_adapter_approved == false
    and .opt_in_plan.implemented_post_implementation_review_gate.default_search_order_change_allowed == false
    and .opt_in_plan.implemented_post_implementation_review_gate.requires_separate_runtime_influence_review == true
    and .opt_in_plan.implemented_post_implementation_review_gate.approval_writes_allowed == false
    and .opt_in_plan.implemented_post_implementation_review_gate.writes_approval == false
    and .opt_in_plan.implemented_post_implementation_review_gate.calls_memory_search == false
    and .opt_in_plan.implemented_post_implementation_review_gate.runs_biocortex == false
    and .opt_in_plan.implemented_post_implementation_review_gate.registers_embedding_backend == false
    and .opt_in_plan.implemented_post_implementation_review_gate.changes_memory_search_order == false
    and .opt_in_plan.implemented_post_implementation_review_gate.ordering_behavior_connected == false
    and .opt_in_plan.implemented_post_implementation_review_gate.may_change_search_order_now == false
    and .opt_in_plan.implemented_post_implementation_review_gate.may_implement_ordering_now == false
    and .opt_in_plan.implemented_runtime_influence_review_request.cli == "agent-bridge bio-cortex retrieval-opt-in-runtime-influence-review-request"
    and .opt_in_plan.implemented_runtime_influence_review_request.mcp_tool == "biocortex_retrieval_opt_in_runtime_influence_review_request"
    and .opt_in_plan.implemented_runtime_influence_review_request.schema == "agent_bridge.biocortex_retrieval.opt_in_runtime_influence_review_request.v0"
    and .opt_in_plan.implemented_runtime_influence_review_request.read_only == true
    and .opt_in_plan.implemented_runtime_influence_review_request.runtime_influence_review_request == true
    and .opt_in_plan.implemented_runtime_influence_review_request.implementation_stage == "runtime_influence_review_request_only"
    and .opt_in_plan.implemented_runtime_influence_review_request.consumes_post_implementation_review_gate_summary == true
    and .opt_in_plan.implemented_runtime_influence_review_request.consumes_redacted_order_artifact_summary == true
    and .opt_in_plan.implemented_runtime_influence_review_request.post_implementation_review_gate_included == false
    and .opt_in_plan.implemented_runtime_influence_review_request.redacted_order_artifact_included == false
    and .opt_in_plan.implemented_runtime_influence_review_request.raw_query_included == false
    and .opt_in_plan.implemented_runtime_influence_review_request.raw_keys_included == false
    and .opt_in_plan.implemented_runtime_influence_review_request.content_included == false
    and .opt_in_plan.implemented_runtime_influence_review_request.request_scope == "explicit_opt_in_fts_runtime_influence_review"
    and .opt_in_plan.implemented_runtime_influence_review_request.request_runtime_adapter_review == true
    and .opt_in_plan.implemented_runtime_influence_review_request.request_ordering_behavior_connection_review == true
    and .opt_in_plan.implemented_runtime_influence_review_request.request_default_search_order_change == false
    and .opt_in_plan.implemented_runtime_influence_review_request.request_hybrid_retrieval_influence == false
    and .opt_in_plan.implemented_runtime_influence_review_request.request_semantic_retrieval_influence == false
    and .opt_in_plan.implemented_runtime_influence_review_request.this_packet_grants_request == false
    and .opt_in_plan.implemented_runtime_influence_review_request.approval_state == "not_approved"
    and .opt_in_plan.implemented_runtime_influence_review_request.authorization_state == "runtime_influence_review_requested_not_granted"
    and .opt_in_plan.implemented_runtime_influence_review_request.implementation_allowed == false
    and .opt_in_plan.implemented_runtime_influence_review_request.runtime_adapter_approved == false
    and .opt_in_plan.implemented_runtime_influence_review_request.default_search_order_change_allowed == false
    and .opt_in_plan.implemented_runtime_influence_review_request.approval_writes_allowed == false
    and .opt_in_plan.implemented_runtime_influence_review_request.writes_approval == false
    and .opt_in_plan.implemented_runtime_influence_review_request.calls_memory_search == false
    and .opt_in_plan.implemented_runtime_influence_review_request.runs_biocortex == false
    and .opt_in_plan.implemented_runtime_influence_review_request.registers_embedding_backend == false
    and .opt_in_plan.implemented_runtime_influence_review_request.changes_memory_search_order == false
    and .opt_in_plan.implemented_runtime_influence_review_request.ordering_behavior_connected == false
    and .opt_in_plan.implemented_runtime_influence_review_request.may_change_search_order_now == false
    and .opt_in_plan.implemented_runtime_influence_review_request.may_implement_ordering_now == false
    and .opt_in_plan.implemented_runtime_influence_decision_packet.cli == "agent-bridge bio-cortex retrieval-opt-in-runtime-influence-decision-packet"
    and .opt_in_plan.implemented_runtime_influence_decision_packet.mcp_tool == "biocortex_retrieval_opt_in_runtime_influence_decision_packet"
    and .opt_in_plan.implemented_runtime_influence_decision_packet.schema == "agent_bridge.biocortex_retrieval.opt_in_runtime_influence_decision_packet.v0"
    and .opt_in_plan.implemented_runtime_influence_decision_packet.read_only == true
    and .opt_in_plan.implemented_runtime_influence_decision_packet.runtime_influence_decision_consumer == true
    and .opt_in_plan.implemented_runtime_influence_decision_packet.implementation_stage == "runtime_influence_decision_consumer_only"
    and .opt_in_plan.implemented_runtime_influence_decision_packet.consumes_runtime_influence_review_request_summary == true
    and .opt_in_plan.implemented_runtime_influence_decision_packet.consumes_runtime_influence_decision_summary == true
    and .opt_in_plan.implemented_runtime_influence_decision_packet.runtime_influence_review_request_included == false
    and .opt_in_plan.implemented_runtime_influence_decision_packet.runtime_influence_decision_included == false
    and .opt_in_plan.implemented_runtime_influence_decision_packet.human_decision_text_included == false
    and .opt_in_plan.implemented_runtime_influence_decision_packet.raw_query_included == false
    and .opt_in_plan.implemented_runtime_influence_decision_packet.raw_keys_included == false
    and .opt_in_plan.implemented_runtime_influence_decision_packet.content_included == false
    and .opt_in_plan.implemented_runtime_influence_decision_packet.authorization_scope == "explicit_opt_in_fts_runtime_influence"
    and .opt_in_plan.implemented_runtime_influence_decision_packet.can_authorize_explicit_opt_in_fts_runtime_adapter == true
    and .opt_in_plan.implemented_runtime_influence_decision_packet.can_authorize_explicit_opt_in_fts_ordering_connection == true
    and .opt_in_plan.implemented_runtime_influence_decision_packet.default_search_order_change_allowed == false
    and .opt_in_plan.implemented_runtime_influence_decision_packet.default_retrieval_influence_authorized == false
    and .opt_in_plan.implemented_runtime_influence_decision_packet.hybrid_retrieval_influence_authorized == false
    and .opt_in_plan.implemented_runtime_influence_decision_packet.semantic_retrieval_influence_authorized == false
    and .opt_in_plan.implemented_runtime_influence_decision_packet.approval_writes_allowed == false
    and .opt_in_plan.implemented_runtime_influence_decision_packet.writes_approval == false
    and .opt_in_plan.implemented_runtime_influence_decision_packet.calls_memory_search == false
    and .opt_in_plan.implemented_runtime_influence_decision_packet.runs_biocortex == false
    and .opt_in_plan.implemented_runtime_influence_decision_packet.registers_embedding_backend == false
    and .opt_in_plan.implemented_runtime_influence_decision_packet.changes_memory_search_order == false
    and .opt_in_plan.implemented_runtime_influence_decision_packet.ordering_behavior_connected == false
    and .opt_in_plan.implemented_runtime_influence_decision_packet.may_change_search_order_now == false
    and .opt_in_plan.implemented_runtime_influence_decision_packet.requires_separate_connection_implementation == true
    and .opt_in_plan.implemented_runtime_influence_decision_packet.this_packet_connects_ordering_behavior == false
    and .opt_in_plan.implemented_runtime_influence_decision_packet.this_packet_changes_return_order == false
    and .opt_in_plan.implemented_dry_run_planner.mcp_tool == "biocortex_retrieval_opt_in_dry_run"
    and .opt_in_plan.implemented_dry_run_planner.schema == "agent_bridge.biocortex_retrieval.opt_in_dry_run_plan.v0"
    and .opt_in_plan.implemented_dry_run_planner.read_only == true
    and .opt_in_plan.implemented_dry_run_planner.dry_run == true
    and .opt_in_plan.implemented_dry_run_planner.calls_memory_search == false
    and .opt_in_plan.implemented_dry_run_planner.runs_biocortex == false
    and .opt_in_plan.implemented_dry_run_planner.raw_query_included == false
    and .opt_in_plan.implemented_dry_run_planner.raw_keys_included == false
    and .opt_in_plan.implemented_dry_run_planner.content_included == false
    and .opt_in_plan.implemented_dry_run_planner.includes_store_contract == true
    and .opt_in_plan.implemented_dry_run_planner.ordering_behavior_connected == false
    and .opt_in_plan.implemented_review_packet_consumer.mcp_tool == "biocortex_retrieval_opt_in_review_packet"
    and .opt_in_plan.implemented_review_packet_consumer.schema == "agent_bridge.biocortex_retrieval.opt_in_review_packet.v0"
    and .opt_in_plan.implemented_review_packet_consumer.read_only == true
    and .opt_in_plan.implemented_review_packet_consumer.dry_run_consumer == true
    and .opt_in_plan.implemented_review_packet_consumer.raw_dry_run_plan_included == false
    and .opt_in_plan.implemented_review_packet_consumer.raw_query_included == false
    and .opt_in_plan.implemented_review_packet_consumer.raw_keys_included == false
    and .opt_in_plan.implemented_review_packet_consumer.content_included == false
    and .opt_in_plan.implemented_review_packet_consumer.approval_state == "not_approved"
    and .opt_in_plan.implemented_review_packet_consumer.approval_writes_allowed == false
    and .opt_in_plan.implemented_review_packet_consumer.changes_memory_search_order == false
    and .opt_in_plan.implemented_review_packet_consumer.ordering_behavior_connected == false
    and .opt_in_plan.implemented_review_packet_consumer.may_implement_ordering_now == false
    and .opt_in_plan.implemented_execution_packet_contract.cli == "agent-bridge bio-cortex retrieval-opt-in-execution-packet"
    and .opt_in_plan.implemented_execution_packet_contract.mcp_tool == "biocortex_retrieval_opt_in_execution_packet"
    and .opt_in_plan.implemented_execution_packet_contract.schema == "agent_bridge.biocortex_retrieval.opt_in_execution_packet.v0"
    and .opt_in_plan.implemented_execution_packet_contract.read_only == true
    and .opt_in_plan.implemented_execution_packet_contract.execution_packet == true
    and .opt_in_plan.implemented_execution_packet_contract.review_packet_included == false
    and .opt_in_plan.implemented_execution_packet_contract.raw_query_included == false
    and .opt_in_plan.implemented_execution_packet_contract.raw_keys_included == false
    and .opt_in_plan.implemented_execution_packet_contract.content_included == false
    and .opt_in_plan.implemented_execution_packet_contract.rebuilds_store_contract == true
    and .opt_in_plan.implemented_execution_packet_contract.protected_adapter_contract == true
    and .opt_in_plan.implemented_execution_packet_contract.candidate_recall_source == "baseline_only"
    and .opt_in_plan.implemented_execution_packet_contract.join_key == "candidate_key"
    and .opt_in_plan.implemented_execution_packet_contract.can_add_new_candidates == false
    and .opt_in_plan.implemented_execution_packet_contract.execution_allowed == false
    and .opt_in_plan.implemented_execution_packet_contract.approval_state == "not_approved"
    and .opt_in_plan.implemented_execution_packet_contract.runtime_adapter_approved == false
    and .opt_in_plan.implemented_execution_packet_contract.approval_writes_allowed == false
    and .opt_in_plan.implemented_execution_packet_contract.calls_memory_search == false
    and .opt_in_plan.implemented_execution_packet_contract.runs_biocortex == false
    and .opt_in_plan.implemented_execution_packet_contract.registers_embedding_backend == false
    and .opt_in_plan.implemented_execution_packet_contract.changes_memory_search_order == false
    and .opt_in_plan.implemented_execution_packet_contract.ordering_behavior_connected == false
    and .opt_in_plan.implemented_execution_packet_contract.may_implement_ordering_now == false
    and .opt_in_plan.implemented_runtime_trial.cli == "agent-bridge bio-cortex retrieval-opt-in-runtime-trial"
    and .opt_in_plan.implemented_runtime_trial.mcp_tool == "biocortex_retrieval_opt_in_runtime_trial"
    and .opt_in_plan.implemented_runtime_trial.schema == "agent_bridge.biocortex_retrieval.opt_in_runtime_trial.v0"
    and .opt_in_plan.implemented_runtime_trial.read_only == true
    and .opt_in_plan.implemented_runtime_trial.runtime_trial == true
    and .opt_in_plan.implemented_runtime_trial.execution_packet_included == false
    and .opt_in_plan.implemented_runtime_trial.consumes_execution_packet_summary == true
    and .opt_in_plan.implemented_runtime_trial.calls_memory_search == false
    and .opt_in_plan.implemented_runtime_trial.runs_biocortex == true
    and .opt_in_plan.implemented_runtime_trial.runs_biocortex_only_when_gate_ready == true
    and .opt_in_plan.implemented_runtime_trial.writes_temp_corpus == true
    and .opt_in_plan.implemented_runtime_trial.mutates_ab_memory == false
    and .opt_in_plan.implemented_runtime_trial.registers_embedding_backend == false
    and .opt_in_plan.implemented_runtime_trial.candidate_recall_source == "baseline_only"
    and .opt_in_plan.implemented_runtime_trial.join_key == "candidate_key"
    and .opt_in_plan.implemented_runtime_trial.can_add_new_candidates == false
    and .opt_in_plan.implemented_runtime_trial.raw_query_included == false
    and .opt_in_plan.implemented_runtime_trial.raw_keys_included == false
    and .opt_in_plan.implemented_runtime_trial.content_included == false
    and .opt_in_plan.implemented_runtime_trial.side_signal_raw_included == false
    and .opt_in_plan.implemented_runtime_trial.returned_order_source == "baseline"
    and .opt_in_plan.implemented_runtime_trial.baseline_returned == true
    and .opt_in_plan.implemented_runtime_trial.changes_memory_search_order == false
    and .opt_in_plan.implemented_runtime_trial.ordering_behavior_connected == false
    and .opt_in_plan.implemented_runtime_trial.runtime_adapter_approved == false
    and .opt_in_plan.implemented_runtime_trial.default_search_order_change_allowed == false
    and .opt_in_plan.implemented_runtime_trial.approval_writes_allowed == false
    and .opt_in_plan.implemented_runtime_trial.may_change_search_order_now == false
    and .opt_in_plan.implemented_runtime_trial.may_implement_ordering_now == false
    and .opt_in_plan.implemented_runtime_trial_review_packet.cli == "agent-bridge bio-cortex retrieval-opt-in-runtime-trial-review-packet"
    and .opt_in_plan.implemented_runtime_trial_review_packet.mcp_tool == "biocortex_retrieval_opt_in_runtime_trial_review_packet"
    and .opt_in_plan.implemented_runtime_trial_review_packet.schema == "agent_bridge.biocortex_retrieval.opt_in_runtime_trial_review_packet.v0"
    and .opt_in_plan.implemented_runtime_trial_review_packet.read_only == true
    and .opt_in_plan.implemented_runtime_trial_review_packet.runtime_trial_consumer == true
    and .opt_in_plan.implemented_runtime_trial_review_packet.runtime_trial_packet_included == false
    and .opt_in_plan.implemented_runtime_trial_review_packet.raw_query_included == false
    and .opt_in_plan.implemented_runtime_trial_review_packet.raw_keys_included == false
    and .opt_in_plan.implemented_runtime_trial_review_packet.content_included == false
    and .opt_in_plan.implemented_runtime_trial_review_packet.side_signal_raw_included == false
    and .opt_in_plan.implemented_runtime_trial_review_packet.reports_boundary_violations == true
    and .opt_in_plan.implemented_runtime_trial_review_packet.review_scope == "baseline_preserving_runtime_trial_only"
    and .opt_in_plan.implemented_runtime_trial_review_packet.review_ready_does_not_approve_runtime_influence == true
    and .opt_in_plan.implemented_runtime_trial_review_packet.approval_state == "not_approved"
    and .opt_in_plan.implemented_runtime_trial_review_packet.runtime_adapter_approved == false
    and .opt_in_plan.implemented_runtime_trial_review_packet.approval_writes_allowed == false
    and .opt_in_plan.implemented_runtime_trial_review_packet.writes_approval == false
    and .opt_in_plan.implemented_runtime_trial_review_packet.calls_memory_search == false
    and .opt_in_plan.implemented_runtime_trial_review_packet.runs_biocortex == false
    and .opt_in_plan.implemented_runtime_trial_review_packet.registers_embedding_backend == false
    and .opt_in_plan.implemented_runtime_trial_review_packet.changes_memory_search_order == false
    and .opt_in_plan.implemented_runtime_trial_review_packet.ordering_behavior_connected == false
    and .opt_in_plan.implemented_runtime_trial_review_packet.may_implement_ordering_now == false
    and .opt_in_plan.implemented_authorization_request_runtime_trial_review_evidence.script == "scripts/prepare-biocortex-retrieval-opt-in-authorization-request.sh"
    and .opt_in_plan.implemented_authorization_request_runtime_trial_review_evidence.request_schema == "agent_bridge.biocortex_retrieval.opt_in_authorization_request.v0"
    and .opt_in_plan.implemented_authorization_request_runtime_trial_review_evidence.required_input == "agent_bridge.biocortex_retrieval.opt_in_runtime_trial_review_packet.v0"
    and .opt_in_plan.implemented_authorization_request_runtime_trial_review_evidence.evidence_path == "evidence.runtime_trial_review_packet"
    and .opt_in_plan.implemented_authorization_request_runtime_trial_review_evidence.read_only == true
    and .opt_in_plan.implemented_authorization_request_runtime_trial_review_evidence.raw_query_included == false
    and .opt_in_plan.implemented_authorization_request_runtime_trial_review_evidence.raw_keys_included == false
    and .opt_in_plan.implemented_authorization_request_runtime_trial_review_evidence.content_included == false
    and .opt_in_plan.implemented_authorization_request_runtime_trial_review_evidence.side_signal_raw_included == false
    and .opt_in_plan.implemented_authorization_request_runtime_trial_review_evidence.requires_review_ready_for_baseline_runtime_trial == true
    and .opt_in_plan.implemented_authorization_request_runtime_trial_review_evidence.requires_zero_boundary_violations == true
    and .opt_in_plan.implemented_authorization_request_runtime_trial_review_evidence.approval_state == "not_approved"
    and .opt_in_plan.implemented_authorization_request_runtime_trial_review_evidence.runtime_adapter_approved == false
    and .opt_in_plan.implemented_authorization_request_runtime_trial_review_evidence.approval_writes_allowed == false
    and .opt_in_plan.implemented_authorization_request_runtime_trial_review_evidence.writes_approval == false
    and .opt_in_plan.implemented_authorization_request_runtime_trial_review_evidence.calls_memory_search == false
    and .opt_in_plan.implemented_authorization_request_runtime_trial_review_evidence.runs_biocortex == false
    and .opt_in_plan.implemented_authorization_request_runtime_trial_review_evidence.registers_embedding_backend == false
    and .opt_in_plan.implemented_authorization_request_runtime_trial_review_evidence.changes_memory_search_order == false
    and .opt_in_plan.implemented_authorization_request_runtime_trial_review_evidence.ordering_behavior_connected == false
    and .opt_in_plan.implemented_authorization_request_runtime_trial_review_evidence.may_implement_ordering_now == false
    and .opt_in_plan.implemented_order_diff_packet.cli == "agent-bridge bio-cortex retrieval-opt-in-order-diff-packet"
    and .opt_in_plan.implemented_order_diff_packet.mcp_tool == "biocortex_retrieval_opt_in_order_diff_packet"
    and .opt_in_plan.implemented_order_diff_packet.schema == "agent_bridge.biocortex_retrieval.opt_in_order_diff_packet.v0"
    and .opt_in_plan.implemented_order_diff_packet.read_only == true
    and .opt_in_plan.implemented_order_diff_packet.order_diff_packet == true
    and .opt_in_plan.implemented_order_diff_packet.source_packet_consumer == true
    and .opt_in_plan.implemented_order_diff_packet.source_packet_included == false
    and .opt_in_plan.implemented_order_diff_packet.raw_query_included == false
    and .opt_in_plan.implemented_order_diff_packet.raw_keys_included == false
    and .opt_in_plan.implemented_order_diff_packet.content_included == false
    and .opt_in_plan.implemented_order_diff_packet.side_signal_raw_included == false
    and .opt_in_plan.implemented_order_diff_packet.compares_baseline_vs_advisory_hash_only == true
    and .opt_in_plan.implemented_order_diff_packet.full_top_k_overlap_available == false
    and .opt_in_plan.implemented_order_diff_packet.per_key_movements_available == false
    and .opt_in_plan.implemented_order_diff_packet.calls_memory_search == false
    and .opt_in_plan.implemented_order_diff_packet.runs_biocortex == false
    and .opt_in_plan.implemented_order_diff_packet.changes_memory_search_order == false
    and .opt_in_plan.implemented_order_diff_packet.ordering_behavior_connected == false
    and .opt_in_plan.implemented_order_diff_packet.actual_return_order_changed == false
    and .opt_in_plan.implemented_order_diff_packet.approval_state == "not_approved"
    and .opt_in_plan.implemented_order_diff_packet.runtime_adapter_approved == false
    and .opt_in_plan.implemented_order_diff_packet.may_implement_ordering_now == false
    and .opt_in_plan.implemented_redacted_order_artifact.cli == "agent-bridge bio-cortex retrieval-opt-in-redacted-order-artifact"
    and .opt_in_plan.implemented_redacted_order_artifact.mcp_tool == "biocortex_retrieval_opt_in_redacted_order_artifact"
    and .opt_in_plan.implemented_redacted_order_artifact.schema == "agent_bridge.biocortex_retrieval.opt_in_redacted_order_artifact.v0"
    and .opt_in_plan.implemented_redacted_order_artifact.read_only == true
    and .opt_in_plan.implemented_redacted_order_artifact.redacted_order_artifact == true
    and .opt_in_plan.implemented_redacted_order_artifact.source_packet_consumer == true
    and .opt_in_plan.implemented_redacted_order_artifact.raw_query_included == false
    and .opt_in_plan.implemented_redacted_order_artifact.raw_keys_included == false
    and .opt_in_plan.implemented_redacted_order_artifact.raw_order_keys_included == false
    and .opt_in_plan.implemented_redacted_order_artifact.content_included == false
    and .opt_in_plan.implemented_redacted_order_artifact.side_signal_raw_included == false
    and .opt_in_plan.implemented_redacted_order_artifact.computes_top_k_overlap == true
    and .opt_in_plan.implemented_redacted_order_artifact.computes_rank_delta_distribution == true
    and .opt_in_plan.implemented_redacted_order_artifact.computes_per_key_movements == true
    and .opt_in_plan.implemented_redacted_order_artifact.calls_memory_search == false
    and .opt_in_plan.implemented_redacted_order_artifact.runs_biocortex == false
    and .opt_in_plan.implemented_redacted_order_artifact.changes_memory_search_order == false
    and .opt_in_plan.implemented_redacted_order_artifact.ordering_behavior_connected == false
    and .opt_in_plan.implemented_redacted_order_artifact.actual_return_order_changed == false
    and .opt_in_plan.implemented_redacted_order_artifact.approval_state == "not_approved"
    and .opt_in_plan.implemented_redacted_order_artifact.runtime_adapter_approved == false
    and .opt_in_plan.implemented_redacted_order_artifact.may_implement_ordering_now == false
    and .opt_in_plan.implemented_authorization_request_order_diff_evidence.script == "scripts/prepare-biocortex-retrieval-opt-in-authorization-request.sh"
    and .opt_in_plan.implemented_authorization_request_order_diff_evidence.optional_input == "agent_bridge.biocortex_retrieval.opt_in_order_diff_packet.v0"
    and .opt_in_plan.implemented_authorization_request_order_diff_evidence.evidence_path == "evidence.order_diff_packet"
    and .opt_in_plan.implemented_authorization_request_order_diff_evidence.required == false
    and .opt_in_plan.implemented_authorization_request_order_diff_evidence.hash_only_summary == true
    and .opt_in_plan.implemented_authorization_request_order_diff_evidence.copies_raw_hashes == false
    and .opt_in_plan.implemented_authorization_request_order_diff_evidence.copies_raw_order_keys == false
    and .opt_in_plan.implemented_authorization_request_order_diff_evidence.approval_state == "not_approved"
    and .opt_in_plan.implemented_authorization_request_order_diff_evidence.runtime_adapter_approved == false
    and .opt_in_plan.implemented_authorization_request_order_diff_evidence.calls_memory_search == false
    and .opt_in_plan.implemented_authorization_request_order_diff_evidence.runs_biocortex == false
    and .opt_in_plan.implemented_authorization_request_order_diff_evidence.changes_memory_search_order == false
    and .opt_in_plan.implemented_authorization_request_order_diff_evidence.ordering_behavior_connected == false
    and .opt_in_plan.implemented_authorization_request_redacted_order_artifact_evidence.script == "scripts/prepare-biocortex-retrieval-opt-in-authorization-request.sh"
    and .opt_in_plan.implemented_authorization_request_redacted_order_artifact_evidence.request_schema == "agent_bridge.biocortex_retrieval.opt_in_authorization_request.v0"
    and .opt_in_plan.implemented_authorization_request_redacted_order_artifact_evidence.optional_input == "agent_bridge.biocortex_retrieval.opt_in_redacted_order_artifact.v0"
    and .opt_in_plan.implemented_authorization_request_redacted_order_artifact_evidence.evidence_path == "evidence.redacted_order_artifact"
    and .opt_in_plan.implemented_authorization_request_redacted_order_artifact_evidence.required == false
    and .opt_in_plan.implemented_authorization_request_redacted_order_artifact_evidence.read_only == true
    and .opt_in_plan.implemented_authorization_request_redacted_order_artifact_evidence.summary_only == true
    and .opt_in_plan.implemented_authorization_request_redacted_order_artifact_evidence.artifact_included == false
    and .opt_in_plan.implemented_authorization_request_redacted_order_artifact_evidence.requires_artifact_ready_when_provided == true
    and .opt_in_plan.implemented_authorization_request_redacted_order_artifact_evidence.requires_zero_boundary_violations_when_provided == true
    and .opt_in_plan.implemented_authorization_request_redacted_order_artifact_evidence.requires_redacted_rows_comparable_when_provided == true
    and .opt_in_plan.implemented_authorization_request_redacted_order_artifact_evidence.reports_top_k_overlap == true
    and .opt_in_plan.implemented_authorization_request_redacted_order_artifact_evidence.reports_rank_delta_distribution == true
    and .opt_in_plan.implemented_authorization_request_redacted_order_artifact_evidence.reports_per_key_movement_count == true
    and .opt_in_plan.implemented_authorization_request_redacted_order_artifact_evidence.copies_key_hashes == false
    and .opt_in_plan.implemented_authorization_request_redacted_order_artifact_evidence.copies_redacted_rank_rows == false
    and .opt_in_plan.implemented_authorization_request_redacted_order_artifact_evidence.copies_raw_order_keys == false
    and .opt_in_plan.implemented_authorization_request_redacted_order_artifact_evidence.raw_query_included == false
    and .opt_in_plan.implemented_authorization_request_redacted_order_artifact_evidence.raw_keys_included == false
    and .opt_in_plan.implemented_authorization_request_redacted_order_artifact_evidence.raw_order_keys_included == false
    and .opt_in_plan.implemented_authorization_request_redacted_order_artifact_evidence.content_included == false
    and .opt_in_plan.implemented_authorization_request_redacted_order_artifact_evidence.side_signal_raw_included == false
    and .opt_in_plan.implemented_authorization_request_redacted_order_artifact_evidence.approval_state == "not_approved"
    and .opt_in_plan.implemented_authorization_request_redacted_order_artifact_evidence.runtime_adapter_approved == false
    and .opt_in_plan.implemented_authorization_request_redacted_order_artifact_evidence.approval_writes_allowed == false
    and .opt_in_plan.implemented_authorization_request_redacted_order_artifact_evidence.writes_approval == false
    and .opt_in_plan.implemented_authorization_request_redacted_order_artifact_evidence.calls_memory_search == false
    and .opt_in_plan.implemented_authorization_request_redacted_order_artifact_evidence.runs_biocortex == false
    and .opt_in_plan.implemented_authorization_request_redacted_order_artifact_evidence.registers_embedding_backend == false
    and .opt_in_plan.implemented_authorization_request_redacted_order_artifact_evidence.changes_memory_search_order == false
    and .opt_in_plan.implemented_authorization_request_redacted_order_artifact_evidence.ordering_behavior_connected == false
    and .opt_in_plan.implemented_authorization_request_redacted_order_artifact_evidence.actual_return_order_changed == false
    and .opt_in_plan.implemented_authorization_request_redacted_order_artifact_evidence.may_implement_ordering_now == false
    and .opt_in_plan.experiment.mode == "fts_only"
    and .evidence.runtime_boundary_proof.default_disabled_status == "runtime_disabled"
    and .evidence.runtime_boundary_proof.kill_switch_status == "operator_disabled"
    and .evidence.runtime_boundary_proof.enabled_shadow_status == "ok"
    and .evidence.runtime_trial_review_packet.provided == true
    and .evidence.runtime_trial_review_packet.schema == "agent_bridge.biocortex_retrieval.opt_in_runtime_trial_review_packet.v0"
    and .evidence.runtime_trial_review_packet.read_only == true
    and .evidence.runtime_trial_review_packet.runtime_trial_consumer == true
    and .evidence.runtime_trial_review_packet.review_scope == "baseline_preserving_runtime_trial_only"
    and .evidence.runtime_trial_review_packet.review_ready_for_baseline_runtime_trial == true
    and .evidence.runtime_trial_review_packet.violation_count == 0
    and .evidence.runtime_trial_review_packet.side_signal_status == "ok"
    and .evidence.runtime_trial_review_packet.side_signal_coverage >= 0.5
    and .evidence.runtime_trial_review_packet.returned_order_source == "baseline"
    and .evidence.runtime_trial_review_packet.baseline_returned == true
    and .evidence.runtime_trial_review_packet.hash_matches_baseline == true
    and .evidence.runtime_trial_review_packet.raw_query_included == false
    and .evidence.runtime_trial_review_packet.raw_keys_included == false
    and .evidence.runtime_trial_review_packet.content_included == false
    and .evidence.runtime_trial_review_packet.side_signal_raw_included == false
    and .evidence.runtime_trial_review_packet.approval_state == "not_approved"
    and .evidence.runtime_trial_review_packet.runtime_adapter_approved == false
    and .evidence.runtime_trial_review_packet.approval_writes_allowed == false
    and .evidence.runtime_trial_review_packet.writes_approval == false
    and .evidence.runtime_trial_review_packet.calls_memory_search == false
    and .evidence.runtime_trial_review_packet.runs_biocortex == false
    and .evidence.runtime_trial_review_packet.registers_embedding_backend == false
    and .evidence.runtime_trial_review_packet.changes_memory_search_order == false
    and .evidence.runtime_trial_review_packet.ordering_behavior_connected == false
    and .evidence.runtime_trial_review_packet.may_implement_ordering_now == false
    and .evidence.order_diff_packet.provided == true
    and .evidence.order_diff_packet.required == false
    and .evidence.order_diff_packet.schema == "agent_bridge.biocortex_retrieval.opt_in_order_diff_packet.v0"
    and .evidence.order_diff_packet.read_only == true
    and .evidence.order_diff_packet.order_diff_packet == true
    and .evidence.order_diff_packet.source_packet_consumer == true
    and .evidence.order_diff_packet.source_kind == "runtime_trial_review_packet"
    and .evidence.order_diff_packet.diff_ready == true
    and .evidence.order_diff_packet.violation_count == 0
    and .evidence.order_diff_packet.order_hashes_comparable == true
    and (.evidence.order_diff_packet.order_hash_changed | type) == "boolean"
    and .evidence.order_diff_packet.top_key_hashes_comparable == true
    and (.evidence.order_diff_packet.top_key_changed | type) == "boolean"
    and .evidence.order_diff_packet.expected_rank_delta_advisory_minus_baseline == 0
    and .evidence.order_diff_packet.expected_rank_direction == "unchanged"
    and .evidence.order_diff_packet.returned_order_source == "baseline"
    and .evidence.order_diff_packet.baseline_returned == true
    and .evidence.order_diff_packet.hash_matches_baseline == true
    and .evidence.order_diff_packet.actual_return_order_changed == false
    and .evidence.order_diff_packet.top_k_overlap == "not_computed_no_raw_order_keys"
    and .evidence.order_diff_packet.per_key_movements == "not_computed_no_raw_order_keys"
    and .evidence.order_diff_packet.raw_query_included == false
    and .evidence.order_diff_packet.raw_keys_included == false
    and .evidence.order_diff_packet.content_included == false
    and .evidence.order_diff_packet.side_signal_raw_included == false
    and .evidence.order_diff_packet.approval_state == "not_approved"
    and .evidence.order_diff_packet.runtime_adapter_approved == false
    and .evidence.order_diff_packet.approval_writes_allowed == false
    and .evidence.order_diff_packet.writes_approval == false
    and .evidence.order_diff_packet.calls_memory_search == false
    and .evidence.order_diff_packet.runs_biocortex == false
    and .evidence.order_diff_packet.registers_embedding_backend == false
    and .evidence.order_diff_packet.changes_memory_search_order == false
    and .evidence.order_diff_packet.ordering_behavior_connected == false
    and .evidence.order_diff_packet.may_implement_ordering_now == false
    and .evidence.redacted_order_artifact.provided == true
    and .evidence.redacted_order_artifact.required == false
    and .evidence.redacted_order_artifact.schema == "agent_bridge.biocortex_retrieval.opt_in_redacted_order_artifact.v0"
    and .evidence.redacted_order_artifact.read_only == true
    and .evidence.redacted_order_artifact.redacted_order_artifact == true
    and .evidence.redacted_order_artifact.source_packet_consumer == true
    and .evidence.redacted_order_artifact.source_kind == "runtime_trial_review_packet"
    and .evidence.redacted_order_artifact.artifact_ready == true
    and .evidence.redacted_order_artifact.violation_count == 0
    and .evidence.redacted_order_artifact.redacted_rows_comparable == true
    and .evidence.redacted_order_artifact.baseline_rank_row_count == 1
    and .evidence.redacted_order_artifact.advisory_rank_row_count == 1
    and .evidence.redacted_order_artifact.top1_overlap_count == 1
    and .evidence.redacted_order_artifact.top1_jaccard == 1
    and .evidence.redacted_order_artifact.top3_overlap_count == 1
    and .evidence.redacted_order_artifact.top3_jaccard == 1
    and .evidence.redacted_order_artifact.improved_count == 0
    and .evidence.redacted_order_artifact.regressed_count == 0
    and .evidence.redacted_order_artifact.unchanged_count == 1
    and .evidence.redacted_order_artifact.missing_baseline_count == 0
    and .evidence.redacted_order_artifact.missing_advisory_count == 0
    and .evidence.redacted_order_artifact.max_abs_delta == 0
    and .evidence.redacted_order_artifact.comparable_key_count == 1
    and .evidence.redacted_order_artifact.per_key_movement_count == 1
    and .evidence.redacted_order_artifact.returned_order_source == "baseline"
    and .evidence.redacted_order_artifact.baseline_returned == true
    and .evidence.redacted_order_artifact.hash_matches_baseline == true
    and .evidence.redacted_order_artifact.actual_return_order_changed == false
    and .evidence.redacted_order_artifact.raw_query_included == false
    and .evidence.redacted_order_artifact.raw_keys_included == false
    and .evidence.redacted_order_artifact.raw_order_keys_included == false
    and .evidence.redacted_order_artifact.content_included == false
    and .evidence.redacted_order_artifact.side_signal_raw_included == false
    and .evidence.redacted_order_artifact.redacted_key_hashes_in_artifact == true
    and .evidence.redacted_order_artifact.copies_key_hashes_to_request == false
    and .evidence.redacted_order_artifact.copies_redacted_rank_rows == false
    and .evidence.redacted_order_artifact.approval_state == "not_approved"
    and .evidence.redacted_order_artifact.runtime_adapter_approved == false
    and .evidence.redacted_order_artifact.approval_writes_allowed == false
    and .evidence.redacted_order_artifact.writes_approval == false
    and .evidence.redacted_order_artifact.calls_memory_search == false
    and .evidence.redacted_order_artifact.runs_biocortex == false
    and .evidence.redacted_order_artifact.registers_embedding_backend == false
    and .evidence.redacted_order_artifact.changes_memory_search_order == false
    and .evidence.redacted_order_artifact.ordering_behavior_connected == false
    and .evidence.redacted_order_artifact.may_implement_ordering_now == false
    and .current_permissions.may_implement_opt_in_experiment == true
    and .current_permissions.may_change_default_retrieval_order == false
    and .requested_permission_if_human_authorizes.may_affect_only_explicitly_opted_in_fts_calls == true
    and .requested_permission_if_human_authorizes.requires_runtime_trial_review_packet == true
    and .requested_permission_if_human_authorizes.accepts_optional_order_diff_packet == true
    and .requested_permission_if_human_authorizes.accepts_optional_redacted_order_artifact == true
    and (.not_requested | index("default_retrieval_influence_fts"))
    and (.not_requested | index("runtime_adapter_approved"))
' "$opt_in_auth_request/opt-in-authorization-request.json" >/dev/null
if grep -q 'verify runtime trial secret query\|verify_runtime_trial_secret_key\|verify runtime trial secret content' "$opt_in_auth_request/opt-in-authorization-request.json"; then
    echo "opt-in authorization request leaked raw query/key/content data" >&2
    exit 1
fi
if grep -q 'sha256:' "$opt_in_auth_request/opt-in-authorization-request.json"; then
    echo "opt-in authorization request copied redacted key hashes" >&2
    exit 1
fi

opt_in_auth_decision_packet="$tmpdir/opt-in-authorization-decision-packet.json"
run cargo run -p ab-bridge --no-default-features -- \
    bio-cortex retrieval-opt-in-authorization-decision-packet \
    --authorization-request-json "$opt_in_auth_request/opt-in-authorization-request.json" \
    --authorization-decision-json "docs/design/fixtures/biocortex-retrieval-opt-in-authorization-decision-2026-06-11.json" \
    --reviewer verify-bundle \
    --commit verify-dry-run-commit \
    --forum-post-id verify-forum-post \
    --memory-key verify-memory-key \
    --json > "$opt_in_auth_decision_packet"
jq -e '
    .schema == "agent_bridge.biocortex_retrieval.opt_in_authorization_decision_packet.v0"
    and .read_only == true
    and .authorization_decision_consumer == true
    and .implementation_stage == "authorization_decision_consumer_only"
    and .authorization_scope == "opt_in_experiment"
    and .input_contract.authorization_decision_included == false
    and .input_contract.authorization_request_included == false
    and .input_contract.raw_query_included == false
    and .input_contract.raw_keys_included == false
    and .input_contract.content_included == false
    and .decision_summary.decision == "authorized"
    and .decision_summary.authorization_state == "authorized"
    and .decision_summary.authorized_scope == "opt_in_experiment"
    and .decision_summary.implementation_allowed == true
    and .decision_summary.runtime_adapter_approved == false
    and .decision_summary.default_search_order_change_allowed == false
    and .decision_summary.default_retrieval_influence_authorized == false
    and .decision_summary.hybrid_retrieval_influence_authorized == false
    and .decision_summary.semantic_retrieval_influence_authorized == false
    and .decision_summary.requires_post_implementation_review_before_use == true
    and .request_summary.approval_state == "opt_in_implementation_authorized"
    and .request_summary.authorization_state == "authorized_for_opt_in_implementation"
    and .request_summary.request_scope == "opt_in_experiment"
    and .request_summary.implementation_allowed == true
    and .request_summary.runtime_adapter_approved == false
    and .request_summary.default_search_order_change_allowed == false
    and .request_summary.writes_approval == false
    and .request_summary.opt_in_plan_status == "store_opt_in_runtime_adapter_connection_implemented"
    and .authorized_implementation.may_implement_opt_in_experiment == true
    and .authorized_implementation.may_add_runtime_enable_env == "AB_BIOCORTEX_RETRIEVAL_OPT_IN"
    and .authorized_implementation.may_add_per_call_opt_in_surface == true
    and .authorized_implementation.may_affect_only_explicitly_opted_in_fts_calls == true
    and .authorized_implementation.must_keep_operator_disable == "AB_BIOCORTEX_RETRIEVAL_DISABLE"
    and .authorized_implementation.must_return_baseline_without_per_call_opt_in == true
    and .authorized_implementation.must_return_baseline_on_absent_error_timeout_low_coverage_malformed_rows == true
    and .authorized_implementation.requires_post_implementation_review_before_use == true
    and (.not_authorized | index("runtime_adapter_approved"))
    and (.not_authorized | index("default_search_order_change_allowed"))
    and (.not_authorized | index("production_use_without_post_implementation_review"))
    and .boundary_check.implementation_authorized == true
    and (.boundary_check.blockers | length) == 0
    and .boundary_check.runtime_adapter_still_not_approved == true
    and .boundary_check.default_order_still_not_allowed == true
    and .required_next_gate.post_implementation_review_before_use == true
    and .required_next_gate.runtime_adapter_approval_required == true
    and .required_next_gate.ordering_behavior_connection_required == true
    and .required_next_gate.this_packet_approves_runtime_adapter == false
    and .required_next_gate.this_packet_connects_ordering_behavior == false
    and .approval_state == "opt_in_implementation_authorized"
    and .authorization_state == "authorized_for_opt_in_implementation"
    and .runtime_adapter_approved == false
    and .approval_writes_allowed == false
    and .writes_approval == false
    and .calls_memory_search == false
    and .runs_biocortex == false
    and .registers_embedding_backend == false
    and .changes_memory_search_order == false
    and .default_search_order_change_allowed == false
    and .ordering_behavior_connected == false
    and .may_change_search_order_now == false
    and .may_implement_ordering_now == false
' "$opt_in_auth_decision_packet" >/dev/null
if grep -q '很好！我授权\|verify runtime trial secret query\|verify_runtime_trial_secret_key\|verify runtime trial secret content' "$opt_in_auth_decision_packet"; then
    echo "opt-in authorization decision packet leaked raw decision/request data" >&2
    exit 1
fi

opt_in_post_implementation_review_gate="$tmpdir/opt-in-post-implementation-review-gate.json"
run cargo run -p ab-bridge --no-default-features -- \
    bio-cortex retrieval-opt-in-post-implementation-review-gate \
    --authorization-decision-packet-json "$opt_in_auth_decision_packet" \
    --opt-in-plan-json "$opt_in_plan" \
    --reviewer verify-bundle \
    --commit verify-dry-run-commit \
    --forum-post-id verify-forum-post \
    --memory-key verify-memory-key \
    --json > "$opt_in_post_implementation_review_gate"
jq -e '
    .schema == "agent_bridge.biocortex_retrieval.opt_in_post_implementation_review_gate.v0"
    and .read_only == true
    and .post_implementation_review_gate == true
    and .implementation_stage == "post_implementation_review_gate_only"
    and .authorization_scope == "opt_in_experiment"
    and .input_contract.authorization_decision_packet_schema == "agent_bridge.biocortex_retrieval.opt_in_authorization_decision_packet.v0"
    and .input_contract.opt_in_plan_schema == "agent_bridge.biocortex_retrieval.opt_in_experiment_plan.v0"
    and .input_contract.authorization_decision_packet_included == false
    and .input_contract.opt_in_plan_included == false
    and .input_contract.raw_query_included == false
    and .input_contract.raw_keys_included == false
    and .input_contract.content_included == false
    and .evidence_summary.authorization_decision_consumer == true
    and .evidence_summary.implementation_authorized == true
    and .evidence_summary.approval_state == "opt_in_implementation_authorized"
    and .evidence_summary.authorization_state == "authorized_for_opt_in_implementation"
    and .evidence_summary.runtime_adapter_approved == false
    and .evidence_summary.default_search_order_change_allowed == false
    and .evidence_summary.ordering_behavior_connected == false
    and .evidence_summary.post_implementation_review_required == true
    and .plan_summary.status == "store_opt_in_runtime_adapter_connection_implemented"
    and .plan_summary.implementation_allowed == true
    and .plan_summary.store_opt_in_search_wrapper_implemented == true
    and .plan_summary.authorization_decision_consumer_implemented == true
    and .plan_summary.post_implementation_review_gate_implemented == true
    and .plan_summary.runtime_influence_review_request_implemented == true
    and .plan_summary.runtime_influence_decision_packet_implemented == true
    and .plan_summary.store_opt_in_order_connection_implemented == true
    and .plan_summary.store_opt_in_runtime_adapter_connection_implemented == true
    and .plan_summary.explicit_opt_in_fts_runtime_adapter_connected == true
    and .plan_summary.default_memory_search_unchanged == true
    and .plan_summary.runtime_adapter_approved == false
    and .plan_summary.default_search_order_change_allowed == false
    and .plan_summary.ordering_behavior_connected == false
    and .review_readiness.ready_for_human_runtime_influence_review == true
    and .review_readiness.post_implementation_review_completed == false
    and .review_readiness.runtime_adapter_review_completed == false
    and .review_readiness.ordering_behavior_review_completed == false
    and .review_readiness.this_packet_approves_runtime_adapter == false
    and .review_readiness.this_packet_allows_default_search_order_change == false
    and .review_readiness.this_packet_connects_ordering_behavior == false
    and .boundary_check.ready_for_human_runtime_influence_review == true
    and (.boundary_check.blockers | length) == 0
    and .boundary_check.packet_runtime_adapter_still_not_approved == true
    and .boundary_check.packet_default_order_still_not_allowed == true
    and .boundary_check.plan_runtime_adapter_still_not_approved == true
    and .boundary_check.plan_default_order_still_not_allowed == true
    and .boundary_check.plan_ordering_behavior_connected_false == true
    and .required_next_gate.human_runtime_influence_review_required == true
    and .required_next_gate.runtime_adapter_approval_required == true
    and .required_next_gate.ordering_behavior_connection_required == true
    and .required_next_gate.this_packet_approves_runtime_adapter == false
    and .required_next_gate.this_packet_connects_ordering_behavior == false
    and .required_next_gate.this_packet_allows_default_search_order_change == false
    and .review_state == "ready_for_human_runtime_influence_review"
    and .approval_state == "not_approved"
    and .authorization_state == "requires_separate_human_runtime_influence_review"
    and .implementation_allowed == false
    and .runtime_adapter_approved == false
    and .approval_writes_allowed == false
    and .writes_approval == false
    and .calls_memory_search == false
    and .runs_biocortex == false
    and .registers_embedding_backend == false
    and .changes_memory_search_order == false
    and .default_search_order_change_allowed == false
    and .ordering_behavior_connected == false
    and .may_change_search_order_now == false
    and .may_implement_ordering_now == false
' "$opt_in_post_implementation_review_gate" >/dev/null
if grep -q '很好！我授权\|verify runtime trial secret query\|verify_runtime_trial_secret_key\|verify runtime trial secret content' "$opt_in_post_implementation_review_gate"; then
    echo "opt-in post-implementation review gate leaked raw decision/request data" >&2
    exit 1
fi

opt_in_runtime_influence_review_request="$tmpdir/opt-in-runtime-influence-review-request.json"
run cargo run -p ab-bridge --no-default-features -- \
    bio-cortex retrieval-opt-in-runtime-influence-review-request \
    --post-implementation-review-gate-json "$opt_in_post_implementation_review_gate" \
    --redacted-order-artifact-json "$opt_in_redacted_order_artifact" \
    --reviewer verify-bundle \
    --commit verify-dry-run-commit \
    --forum-post-id verify-forum-post \
    --memory-key verify-memory-key \
    --json > "$opt_in_runtime_influence_review_request"
jq -e '
    .schema == "agent_bridge.biocortex_retrieval.opt_in_runtime_influence_review_request.v0"
    and .read_only == true
    and .runtime_influence_review_request == true
    and .implementation_stage == "runtime_influence_review_request_only"
    and .request_scope == "explicit_opt_in_fts_runtime_influence_review"
    and .input_contract.post_implementation_review_gate_schema == "agent_bridge.biocortex_retrieval.opt_in_post_implementation_review_gate.v0"
    and .input_contract.redacted_order_artifact_schema == "agent_bridge.biocortex_retrieval.opt_in_redacted_order_artifact.v0"
    and .input_contract.post_implementation_review_gate_included == false
    and .input_contract.redacted_order_artifact_included == false
    and .input_contract.raw_query_included == false
    and .input_contract.raw_keys_included == false
    and .input_contract.content_included == false
    and .requested_authorization.requested_scope == "explicit_opt_in_fts_runtime_influence_review"
    and .requested_authorization.request_runtime_adapter_review == true
    and .requested_authorization.request_ordering_behavior_connection_review == true
    and .requested_authorization.request_default_search_order_change == false
    and .requested_authorization.request_hybrid_retrieval_influence == false
    and .requested_authorization.request_semantic_retrieval_influence == false
    and .requested_authorization.must_keep_per_call_opt_in_required == true
    and .requested_authorization.must_keep_operator_disable == "AB_BIOCORTEX_RETRIEVAL_DISABLE"
    and .requested_authorization.must_return_baseline_without_per_call_opt_in == true
    and .requested_authorization.must_fail_open_to_baseline == true
    and .requested_authorization.this_packet_grants_request == false
    and .evidence_summary.post_implementation_gate_ready == true
    and .evidence_summary.gate_review_state == "ready_for_human_runtime_influence_review"
    and .evidence_summary.redacted_order_artifact_ready == true
    and .evidence_summary.redacted_rows_comparable == true
    and .evidence_summary.baseline_returned == true
    and .evidence_summary.actual_return_order_changed == false
    and .evidence_summary.runtime_adapter_approved == false
    and .evidence_summary.default_search_order_change_allowed == false
    and .evidence_summary.ordering_behavior_connected == false
    and .boundary_check.runtime_influence_review_request_ready == true
    and (.boundary_check.blockers | length) == 0
    and .boundary_check.gate_schema_ok == true
    and .boundary_check.gate_ready == true
    and .boundary_check.gate_runtime_adapter_still_not_approved == true
    and .boundary_check.gate_default_order_still_not_allowed == true
    and .boundary_check.artifact_schema_ok == true
    and .boundary_check.artifact_ready == true
    and .boundary_check.artifact_redacted_rows_comparable == true
    and .boundary_check.artifact_returned_baseline == true
    and .boundary_check.artifact_return_order_unchanged == true
    and .required_human_decision.decision_schema == "agent_bridge.biocortex_retrieval.opt_in_runtime_influence_review_decision.v0"
    and .required_human_decision.decision_required_before_runtime_adapter == true
    and .required_human_decision.decision_required_before_ordering_connection == true
    and .required_human_decision.must_state_scope_explicit_opt_in_fts_only == true
    and .required_human_decision.must_keep_default_search_order_change_allowed_false == true
    and .required_human_decision.must_keep_hybrid_semantic_not_authorized == true
    and .review_request_state == "ready_for_human_runtime_influence_review"
    and .approval_state == "not_approved"
    and .authorization_state == "runtime_influence_review_requested_not_granted"
    and .implementation_allowed == false
    and .runtime_adapter_approved == false
    and .approval_writes_allowed == false
    and .writes_approval == false
    and .calls_memory_search == false
    and .runs_biocortex == false
    and .registers_embedding_backend == false
    and .changes_memory_search_order == false
    and .default_search_order_change_allowed == false
    and .ordering_behavior_connected == false
    and .may_change_search_order_now == false
    and .may_implement_ordering_now == false
    and .default_calls_unchanged == true
' "$opt_in_runtime_influence_review_request" >/dev/null
if grep -q '很好！我授权\|verify runtime trial secret query\|verify_runtime_trial_secret_key\|verify runtime trial secret content' "$opt_in_runtime_influence_review_request"; then
    echo "opt-in runtime influence review request leaked raw decision/request data" >&2
    exit 1
fi

opt_in_runtime_influence_decision="$tmpdir/opt-in-runtime-influence-decision.json"
cat > "$opt_in_runtime_influence_decision" <<'JSON'
{
  "schema": "agent_bridge.biocortex_retrieval.opt_in_runtime_influence_review_decision.v0",
  "decision": "authorized",
  "authorization_state": "authorized",
  "authorized_scope": "explicit_opt_in_fts_runtime_influence",
  "human_decision_text": "verify runtime influence decision secret wording",
  "runtime_adapter_approved": true,
  "ordering_behavior_connection_authorized": true,
  "default_search_order_change_allowed": false,
  "default_retrieval_influence_authorized": false,
  "hybrid_retrieval_influence_authorized": false,
  "semantic_retrieval_influence_authorized": false,
  "authorized_runtime_influence": {
    "may_run_runtime_adapter_for_explicit_opt_in_fts": true,
    "may_connect_ordering_behavior_for_explicit_opt_in_fts": true,
    "may_affect_only_explicitly_opted_in_fts_calls": true,
    "requires_per_call_opt_in": true,
    "must_keep_baseline_candidate_recall": true,
    "must_keep_default_calls_unchanged": true,
    "must_keep_redacted_audit_only": true,
    "must_keep_operator_disable": "AB_BIOCORTEX_RETRIEVAL_DISABLE",
    "must_return_baseline_without_per_call_opt_in": true,
    "must_fail_open_to_baseline": true
  },
  "not_authorized": [
    "default_search_order_change_allowed",
    "default_retrieval_influence_fts",
    "default_retrieval_influence_hybrid",
    "default_retrieval_influence_semantic",
    "hybrid_retrieval_influence",
    "semantic_retrieval_influence",
    "affecting_calls_without_explicit_opt_in"
  ],
  "raw_query": "verify runtime influence decision secret query",
  "raw_key": "verify_runtime_influence_decision_secret_key",
  "content": "verify runtime influence decision secret content"
}
JSON

opt_in_runtime_influence_decision_packet="$tmpdir/opt-in-runtime-influence-decision-packet.json"
run cargo run -p ab-bridge --no-default-features -- \
    bio-cortex retrieval-opt-in-runtime-influence-decision-packet \
    --runtime-influence-review-request-json "$opt_in_runtime_influence_review_request" \
    --runtime-influence-decision-json "$opt_in_runtime_influence_decision" \
    --reviewer verify-bundle \
    --commit verify-dry-run-commit \
    --forum-post-id verify-forum-post \
    --memory-key verify-memory-key \
    --json > "$opt_in_runtime_influence_decision_packet"
jq -e '
    .schema == "agent_bridge.biocortex_retrieval.opt_in_runtime_influence_decision_packet.v0"
    and .read_only == true
    and .runtime_influence_decision_consumer == true
    and .implementation_stage == "runtime_influence_decision_consumer_only"
    and .authorization_scope == "explicit_opt_in_fts_runtime_influence"
    and .input_contract.runtime_influence_review_request_schema == "agent_bridge.biocortex_retrieval.opt_in_runtime_influence_review_request.v0"
    and .input_contract.runtime_influence_decision_schema == "agent_bridge.biocortex_retrieval.opt_in_runtime_influence_review_decision.v0"
    and .input_contract.runtime_influence_review_request_included == false
    and .input_contract.runtime_influence_decision_included == false
    and .input_contract.human_decision_text_included == false
    and .input_contract.raw_query_included == false
    and .input_contract.raw_keys_included == false
    and .input_contract.content_included == false
    and .decision_summary.decision == "authorized"
    and .decision_summary.authorization_state == "authorized"
    and .decision_summary.authorized_scope == "explicit_opt_in_fts_runtime_influence"
    and .decision_summary.runtime_adapter_approved == true
    and .decision_summary.ordering_behavior_connection_authorized == true
    and .decision_summary.default_search_order_change_allowed == false
    and .decision_summary.default_retrieval_influence_authorized == false
    and .decision_summary.hybrid_retrieval_influence_authorized == false
    and .decision_summary.semantic_retrieval_influence_authorized == false
    and .request_summary.request_scope == "explicit_opt_in_fts_runtime_influence_review"
    and .request_summary.review_request_state == "ready_for_human_runtime_influence_review"
    and .request_summary.runtime_influence_review_request_ready == true
    and .request_summary.requested_runtime_adapter_review == true
    and .request_summary.requested_ordering_behavior_connection_review == true
    and .request_summary.requested_default_search_order_change == false
    and .request_summary.requested_hybrid_retrieval_influence == false
    and .request_summary.requested_semantic_retrieval_influence == false
    and .request_summary.request_packet_granted_nothing == true
    and .authorized_runtime_influence.may_run_runtime_adapter_for_explicit_opt_in_fts == true
    and .authorized_runtime_influence.may_connect_ordering_behavior_for_explicit_opt_in_fts == true
    and .authorized_runtime_influence.may_affect_only_explicitly_opted_in_fts_calls == true
    and .authorized_runtime_influence.requires_per_call_opt_in == true
    and .authorized_runtime_influence.must_keep_baseline_candidate_recall == true
    and .authorized_runtime_influence.must_keep_default_calls_unchanged == true
    and .authorized_runtime_influence.must_keep_redacted_audit_only == true
    and .authorized_runtime_influence.must_keep_operator_disable == "AB_BIOCORTEX_RETRIEVAL_DISABLE"
    and .authorized_runtime_influence.must_return_baseline_without_per_call_opt_in == true
    and .authorized_runtime_influence.must_fail_open_to_baseline == true
    and .boundary_check.runtime_influence_authorized == true
    and (.boundary_check.blockers | length) == 0
    and .boundary_check.decision_schema_ok == true
    and .boundary_check.decision_authorized == true
    and .boundary_check.decision_scope_ok == true
    and .boundary_check.decision_runtime_adapter_approved == true
    and .boundary_check.decision_ordering_connection_authorized == true
    and .boundary_check.decision_default_order_still_not_allowed == true
    and .boundary_check.request_schema_ok == true
    and .boundary_check.request_ready == true
    and .boundary_check.request_grants_nothing == true
    and .boundary_check.request_runtime_adapter_still_not_approved == true
    and .boundary_check.request_default_order_still_not_allowed == true
    and .boundary_check.request_ordering_behavior_connected_false == true
    and .boundary_check.request_return_order_unchanged == true
    and .required_next_gate.implementation_may_add_runtime_adapter_for_explicit_opt_in_fts == true
    and .required_next_gate.implementation_may_connect_ordering_behavior_for_explicit_opt_in_fts == true
    and .required_next_gate.post_connection_verification_required == true
    and .required_next_gate.this_packet_connects_ordering_behavior == false
    and .required_next_gate.this_packet_changes_return_order == false
    and .required_next_gate.this_packet_allows_default_search_order_change == false
    and .approval_state == "runtime_influence_review_authorized"
    and .authorization_state == "authorized_for_explicit_opt_in_fts_runtime_influence"
    and .implementation_allowed == true
    and .runtime_adapter_approved == true
    and .ordering_behavior_connection_authorized == true
    and .approval_writes_allowed == false
    and .writes_approval == false
    and .calls_memory_search == false
    and .runs_biocortex == false
    and .registers_embedding_backend == false
    and .changes_memory_search_order == false
    and .default_search_order_change_allowed == false
    and .ordering_behavior_connected == false
    and .may_change_search_order_now == false
    and .may_implement_ordering_now == true
    and .default_calls_unchanged == true
' "$opt_in_runtime_influence_decision_packet" >/dev/null
if grep -q 'verify runtime influence decision secret wording\|verify runtime influence decision secret query\|verify_runtime_influence_decision_secret_key\|verify runtime influence decision secret content\|verify runtime trial secret query\|verify_runtime_trial_secret_key\|verify runtime trial secret content' "$opt_in_runtime_influence_decision_packet"; then
    echo "opt-in runtime influence decision packet leaked raw decision/request data" >&2
    exit 1
fi
test -s "$opt_in_auth_request/forum-post-template.md"
test -s "$opt_in_auth_request/memory-note-template.md"

current_corpus="crates/bridge/tests/fixtures/biocortex_retrieval_gate_corpus.jsonl"
hard_corpus="crates/bridge/tests/fixtures/biocortex_retrieval_gate_hard_holdout_corpus.jsonl"
current_side="$tmpdir/current-side-signal.jsonl"
hard_side="$tmpdir/hard-side-signal.jsonl"
current_report="$tmpdir/current-report.md"
hard_report="$tmpdir/hard-report.md"

run cargo run --manifest-path "$biocortex_rs/Cargo.toml" \
    --example ab_retrieval_side_signal_adapter \
    -- "$repo_root/$current_corpus" > "$current_side"
run env BIOCORTEX_RETRIEVAL_ALPHA_POLICY=candidate-strong \
    BIOCORTEX_RETRIEVAL_SIDE_SIGNAL="$current_side" \
    cargo run -p ab-bridge --example biocortex_retrieval_gate_eval > "$current_report"
assert_summary_pass "$current_report" "side_signal_passes_offline_gate" "current"

run cargo run --manifest-path "$biocortex_rs/Cargo.toml" \
    --example ab_retrieval_side_signal_adapter \
    -- "$repo_root/$hard_corpus" > "$hard_side"
run env BIOCORTEX_RETRIEVAL_CORPUS="$hard_corpus" \
    BIOCORTEX_RETRIEVAL_ALPHA_POLICY=candidate-strong \
    BIOCORTEX_RETRIEVAL_SIDE_SIGNAL="$hard_side" \
    cargo run -p ab-bridge --example biocortex_retrieval_gate_eval > "$hard_report"
assert_summary_pass "$hard_report" "side_signal_passes_offline_gate" "hard"

printf '\nverify-biocortex-retrieval-shadow.sh: all checks passed\n'
printf 'biocortex_rs=%s\n' "$biocortex_rs"
