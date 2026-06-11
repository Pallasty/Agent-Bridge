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
    and .status == "dry_run_planner_implemented"
    and .approval_state == "opt_in_implementation_authorized"
    and .runtime_adapter_approved == false
    and .default_search_order_change_allowed == false
    and .implementation_allowed == true
    and .gate_skeleton_implemented == true
    and .audit_shape_implemented == true
    and .read_only_status_surface_implemented == true
    and .store_contract_implemented == true
    and .dry_run_planner_implemented == true
    and .ordering_behavior_connected == false
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
    and .current_permissions.may_implement_opt_in_experiment == false
    and .requested_permission_if_human_authorizes.may_affect_only_explicitly_opted_in_fts_calls == true
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
    and .opt_in_plan.status == "dry_run_planner_implemented"
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
    and .opt_in_plan.experiment.mode == "fts_only"
    and .evidence.runtime_boundary_proof.default_disabled_status == "runtime_disabled"
    and .evidence.runtime_boundary_proof.kill_switch_status == "operator_disabled"
    and .evidence.runtime_boundary_proof.enabled_shadow_status == "ok"
    and .current_permissions.may_implement_opt_in_experiment == true
    and .current_permissions.may_change_default_retrieval_order == false
    and .requested_permission_if_human_authorizes.may_affect_only_explicitly_opted_in_fts_calls == true
    and (.not_requested | index("default_retrieval_influence_fts"))
    and (.not_requested | index("runtime_adapter_approved"))
' "$opt_in_auth_request/opt-in-authorization-request.json" >/dev/null
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
