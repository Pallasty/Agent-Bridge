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

AB_BIOCORTEX_RS="$biocortex_rs" bash scripts/check-verification-dependencies.sh --all --quiet

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
downstream_aio_checkpoint_selection="docs/design/fixtures/biocortex-retrieval-downstream-aio-checkpoint-selection-2026-06-15.json"
downstream_aio_runtime_evidence_handoff="docs/design/fixtures/biocortex-retrieval-downstream-aio-runtime-evidence-handoff-2026-06-15.json"
ssb_lswr_action_result_review_fixture="docs/design/fixtures/biocortex-retrieval-ssb-lswr-action-result-review-fixture-2026-06-15.json"
read_only_ssb_adapter_fixture="docs/design/fixtures/biocortex-retrieval-read-only-ssb-adapter-fixture-2026-06-15.json"
live_lswr_action_result_runtime_evidence="docs/design/fixtures/biocortex-retrieval-live-lswr-action-result-runtime-evidence-2026-06-15.json"
loopback_lswr_action_result_verified_probe="docs/design/fixtures/biocortex-retrieval-loopback-lswr-action-result-verified-probe-2026-06-15.json"
loopback_lswr_host_attach_preflight="docs/design/fixtures/biocortex-retrieval-loopback-lswr-host-attach-preflight-2026-06-15.json"
onsen_step_b_source_resolution="docs/design/fixtures/biocortex-retrieval-onsen-step-b-source-resolution-2026-06-15.json"
onsen_step_b_host_launch_plan_fixture="docs/design/fixtures/biocortex-retrieval-onsen-step-b-host-launch-plan-2026-06-15.json"
onsen_step_b_host_source_probe_script="scripts/probe-onsen-step-b-host-source.sh"
onsen_step_b_host_launch_plan_script="scripts/plan-onsen-step-b-host-launch.sh"
lswr_interaction_feedback_fixture="crates/bridge/tests/fixtures/lswr_interaction_feedback_fixture_v0.json"
opt_in_batch_query_cases="docs/design/fixtures/biocortex-retrieval-opt-in-batch-diagnostic-queries-2026-06-12.json"
opt_in_controlled_order_fixture="docs/design/fixtures/biocortex-retrieval-opt-in-controlled-order-fixture-2026-06-12.json"
opt_in_expanded_corpus_fixture="docs/design/fixtures/biocortex-retrieval-opt-in-expanded-controlled-corpus-2026-06-12.json"
bash -n "$onsen_step_b_host_source_probe_script"
bash -n "$onsen_step_b_host_launch_plan_script"

tmp_lswr_feedback_consumption_preflight="$tmpdir/lswr-interaction-feedback-consumption-preflight.json"
run cargo run -q -p ab-bridge --no-default-features -- \
    bio-cortex lswr-interaction-feedback-consumption-preflight \
    --input-json "$lswr_interaction_feedback_fixture" \
    --json > "$tmp_lswr_feedback_consumption_preflight"
jq -e '
    .schema == "agent_bridge.lswr.interaction_feedback_consumption_preflight.v0"
    and .accepted == true
    and .preflight_verdict == "accepted"
    and .status == "accepted"
    and .input_kind == "fixture"
    and .source_kind == "fixture"
    and .world_verdict == "not_verified"
    and .reason == "explicit_input_consumption_preflight_passed"
    and (.failure_reasons | length) == 0
    and (.acceptance_matrix | length) == 5
    and ([.acceptance_matrix[].passed] | all(. == true))
    and .guardrails.read_only == true
    and .guardrails.writes_state == false
    and .guardrails.store_access_required == false
    and .guardrails.mcp_tool_registered == false
    and .guardrails.implicit_live_runtime_lookup_allowed == false
    and .guardrails.default_profile_exposure_allowed == false
    and .guardrails.outcome_ingestion_allowed == false
    and .implicit_live_runtime_lookup_attempted == false
' "$tmp_lswr_feedback_consumption_preflight" >/dev/null

tmp_lswr_feedback_consumption_report="$tmpdir/lswr-interaction-feedback-consumption-report.json"
run cargo run -q -p ab-bridge --example lswr_interaction_feedback_consumption_report_smoke -- \
    --format json \
    --assert-golden \
    --assert-read-only > "$tmp_lswr_feedback_consumption_report"
jq -e '
    .schema == "agent_bridge.lswr.interaction_feedback_consumption_report.v0"
    and .preflight_schema == "agent_bridge.lswr.interaction_feedback_consumption_preflight.v0"
    and .accepted == true
    and .preflight_verdict == "accepted"
    and .status == "accepted"
    and .input_kind == "fixture"
    and .source_kind == "fixture"
    and .world_verdict == "not_verified"
    and .world_result_verdict == "not_verified"
    and .json_canonical == true
    and .markdown_source == "preflight"
    and (.markdown | contains("C3 no_verification_laundering: `passed`"))
    and (.markdown | contains("revision_should_cite: `verify_patch_arrival_bath_move_001, fb_arrival_crowded_001`"))
    and .writes_state == false
    and .store_access_required == false
    and .mcp_tool_registered == false
    and .guardrails.read_only == true
    and .guardrails.writes_state == false
    and .guardrails.store_access_required == false
    and .guardrails.mcp_tool_registered == false
    and .guardrails.live_runtime_lookup_allowed == false
    and .guardrails.implicit_live_runtime_lookup_allowed == false
    and .guardrails.default_profile_exposure_allowed == false
    and .guardrails.outcome_ingestion_allowed == false
    and .preflight.implicit_live_runtime_lookup_attempted == false
' "$tmp_lswr_feedback_consumption_report" >/dev/null

run cargo test -p ab-bridge lswr_interaction_feedback_consumption_report_mcp -- --nocapture
run cargo test -p ab-bridge --test lswr_interaction_feedback_mcp_surface -- --nocapture
tmp_lswr_feedback_mcp_surface="$tmpdir/lswr-interaction-feedback-mcp-surface.json"
run cargo run -q -p ab-bridge --example lswr_interaction_feedback_mcp_surface -- \
    --format json \
    --assert-passed \
    --assert-niche-only > "$tmp_lswr_feedback_mcp_surface"
jq -e '
    .schema == "agent_bridge.lswr.interaction_feedback_consumption_report_mcp_surface_report.v0"
    and .tool == "lswr_interaction_feedback_consumption_report"
    and .verdict == "passed"
    and .visible_in == ["profile-all", "all-dev"]
    and .safety_boundary.read_only == true
    and .safety_boundary.live_runtime_lookup == false
    and .safety_boundary.store_access == false
    and .safety_boundary.memory_write == false
    and .expected_input.top_level_keys == ["report_input"]
    and .expected_input.additional_properties == false
' "$tmp_lswr_feedback_mcp_surface" >/dev/null

tmp_lswr_feedback_next_revision_plan="$tmpdir/lswr-interaction-feedback-next-revision-plan.json"
run cargo run -q -p ab-bridge --example lswr_interaction_feedback_next_revision_plan_smoke -- \
    --format json \
    --assert-ready \
    --assert-read-only > "$tmp_lswr_feedback_next_revision_plan"
jq -e '
    .schema == "agent_bridge.lswr.interaction_feedback_next_revision_plan.v0"
    and .source_schema == "agent_bridge.lswr.interaction_feedback_consumption_report.v0"
    and .source_accepted == true
    and .source_world_verdict == "not_verified"
    and .plan_verdict == "ready_for_revision"
    and .next_revision.patch_id == "patch_arrival_bath_move_002"
    and .next_revision.failed_clause_ids == ["effect_walkway_clearance_001"]
    and .next_revision.must_cite == ["verify_patch_arrival_bath_move_001", "fb_arrival_crowded_001"]
    and .next_revision.preserved_world_verdict == "not_verified"
    and .next_revision.allowed_to_apply == false
    and .next_revision.allowed_to_ingest == false
    and .agent_action_contract.do_not_rewrite_world_verdict == true
    and .guardrails.read_only == true
    and .guardrails.applies_patch == false
    and .writes_state == false
    and .store_access_required == false
    and .mcp_tool_registered == false
' "$tmp_lswr_feedback_next_revision_plan" >/dev/null

tmp_lswr_feedback_semantic_patch_draft="$tmpdir/lswr-interaction-feedback-semantic-patch-draft.json"
run cargo run -q -p ab-bridge --example lswr_interaction_feedback_semantic_patch_draft_smoke -- \
    --format json \
    --assert-drafted \
    --assert-read-only > "$tmp_lswr_feedback_semantic_patch_draft"
jq -e '
    .schema == "agent_bridge.lswr.interaction_feedback_semantic_patch_draft.v0"
    and .source_schema == "agent_bridge.lswr.interaction_feedback_next_revision_plan.v0"
    and .source_plan_verdict == "ready_for_revision"
    and .source_world_verdict == "not_verified"
    and .draft_verdict == "drafted"
    and .semantic_patch_draft.patch_id == "patch_arrival_bath_move_002"
    and .semantic_patch_draft.op == "semantic_revision"
    and .semantic_patch_draft.operation_hint == "increase_walkway_clearance_by_repositioning_entity"
    and .semantic_patch_draft.target_entities == ["bath"]
    and .semantic_patch_draft.revision_sources == ["verify_patch_arrival_bath_move_001", "fb_arrival_crowded_001"]
    and .semantic_patch_draft.constraints.failed_clause_ids == ["effect_walkway_clearance_001"]
    and .semantic_patch_draft.constraints.feedback_issue == "visual_density_too_high"
    and .semantic_patch_draft.constraints.preserve_world_verdict == "not_verified"
    and (.semantic_patch_draft.constraints.expected_effect_requirements | length) == 2
    and .semantic_patch_draft.unresolved_arguments == ["patch.args.cell"]
    and .semantic_patch_draft.requires_live_world_state_for_arguments == true
    and .semantic_patch_draft.live_world_state_queried == false
    and .semantic_patch_draft.apply_allowed == false
    and .semantic_patch_draft.ingest_allowed == false
    and .agent_action_contract.resolve_arguments_before_apply == true
    and .agent_action_contract.do_not_apply_patch == true
    and .guardrails.read_only == true
    and .guardrails.applies_patch == false
    and .guardrails.queries_live_runtime == false
    and .writes_state == false
    and .store_access_required == false
    and .mcp_tool_registered == false
' "$tmp_lswr_feedback_semantic_patch_draft" >/dev/null

tmp_lswr_feedback_patch_execution_preflight_blocked="$tmpdir/lswr-interaction-feedback-patch-execution-preflight-blocked.json"
run cargo run -q -p ab-bridge --example lswr_interaction_feedback_patch_execution_preflight_smoke -- \
    --format json \
    --assert-blocked-without-context \
    --assert-read-only > "$tmp_lswr_feedback_patch_execution_preflight_blocked"
jq -e '
    .schema == "agent_bridge.lswr.interaction_feedback_patch_execution_preflight.v0"
    and .source_schema == "agent_bridge.lswr.interaction_feedback_semantic_patch_draft.v0"
    and .source_draft_verdict == "drafted"
    and .source_world_verdict == "not_verified"
    and .preflight_verdict == "blocked"
    and .status == "blocked"
    and .reason == "explicit_argument_context_required"
    and (.failure_reasons | index("explicit_argument_context_required")) != null
    and (.failure_reasons | index("patch_args_cell_unresolved")) != null
    and .argument_context == null
    and .argument_context_status.accepted == false
    and .argument_context_status.reason == "explicit_argument_context_required"
    and .argument_context_status.live_runtime_queried_by_preflight == false
    and .resolved_patch.patch_id == "patch_arrival_bath_move_002"
    and .resolved_patch.op == "semantic_revision"
    and .resolved_patch.operation_hint == "increase_walkway_clearance_by_repositioning_entity"
    and .resolved_patch.target_entities == ["bath"]
    and .resolved_patch.args == null
    and .resolved_patch.resolved_arguments == null
    and .resolved_patch.required_citations == ["verify_patch_arrival_bath_move_001", "fb_arrival_crowded_001"]
    and .resolved_patch.ready_for_execution_request == false
    and .resolved_patch.execution_performed == false
    and .resolved_patch.apply_allowed_by_this_tool == false
    and .resolved_patch.ingest_allowed_by_this_tool == false
    and .agent_action_contract.may_request_separate_apply_after_preflight == false
    and .agent_action_contract.do_not_apply_patch == true
    and .agent_action_contract.do_not_ingest_outcome == true
    and .agent_action_contract.do_not_write_memory == true
    and .agent_action_contract.do_not_query_live_runtime == true
    and .agent_action_contract.do_not_rewrite_world_verdict == true
    and .guardrails.read_only == true
    and .guardrails.applies_patch == false
    and .guardrails.queries_live_runtime == false
    and .implicit_live_runtime_lookup_attempted == false
    and .writes_state == false
    and .store_access_required == false
    and .mcp_tool_registered == false
' "$tmp_lswr_feedback_patch_execution_preflight_blocked" >/dev/null

tmp_lswr_feedback_patch_execution_preflight_ready="$tmpdir/lswr-interaction-feedback-patch-execution-preflight-ready.json"
run cargo run -q -p ab-bridge --example lswr_interaction_feedback_patch_execution_preflight_smoke -- \
    --with-fixture-context \
    --format json \
    --assert-ready-with-context \
    --assert-read-only > "$tmp_lswr_feedback_patch_execution_preflight_ready"
jq -e '
    .schema == "agent_bridge.lswr.interaction_feedback_patch_execution_preflight.v0"
    and .source_schema == "agent_bridge.lswr.interaction_feedback_semantic_patch_draft.v0"
    and .source_draft_verdict == "drafted"
    and .source_world_verdict == "not_verified"
    and .preflight_verdict == "ready_for_execution_request"
    and .status == "ready"
    and .reason == "explicit_argument_context_execution_preflight_ready"
    and (.failure_reasons | length) == 0
    and .argument_context.schema == "agent_bridge.lswr.interaction_feedback_argument_context.v0"
    and .argument_context.source == "explicit_fixture_context"
    and .argument_context.live_runtime_queried_by_preflight == false
    and .argument_context.candidate_arguments[0].argument_path == "patch.args.cell"
    and .argument_context.candidate_arguments[0].value == [5, 2]
    and .argument_context.candidate_arguments[0].satisfies_expected_effect == true
    and .argument_context_status.accepted == true
    and .argument_context_status.reason == "explicit_argument_context_accepted"
    and .argument_context_status.live_runtime_queried_by_preflight == false
    and .resolved_patch.patch_id == "patch_arrival_bath_move_002"
    and .resolved_patch.op == "semantic_revision"
    and .resolved_patch.operation_hint == "increase_walkway_clearance_by_repositioning_entity"
    and .resolved_patch.target_entities == ["bath"]
    and .resolved_patch.args.cell == [5, 2]
    and .resolved_patch.resolved_arguments["patch.args.cell"] == [5, 2]
    and .resolved_patch.required_citations == ["verify_patch_arrival_bath_move_001", "fb_arrival_crowded_001"]
    and .resolved_patch.ready_for_execution_request == true
    and .resolved_patch.execution_performed == false
    and .resolved_patch.apply_allowed_by_this_tool == false
    and .resolved_patch.ingest_allowed_by_this_tool == false
    and .agent_action_contract.may_request_separate_apply_after_preflight == true
    and .agent_action_contract.do_not_apply_patch == true
    and .agent_action_contract.do_not_ingest_outcome == true
    and .agent_action_contract.do_not_write_memory == true
    and .agent_action_contract.do_not_query_live_runtime == true
    and .agent_action_contract.do_not_rewrite_world_verdict == true
    and .guardrails.read_only == true
    and .guardrails.applies_patch == false
    and .guardrails.queries_live_runtime == false
    and .implicit_live_runtime_lookup_attempted == false
    and .writes_state == false
    and .store_access_required == false
    and .mcp_tool_registered == false
' "$tmp_lswr_feedback_patch_execution_preflight_ready" >/dev/null

tmp_lswr_feedback_patch_apply_request_blocked="$tmpdir/lswr-interaction-feedback-patch-apply-request-blocked.json"
run cargo run -q -p ab-bridge --example lswr_interaction_feedback_patch_apply_request_smoke -- \
    --format json \
    --assert-blocked-without-ready-preflight \
    --assert-read-only > "$tmp_lswr_feedback_patch_apply_request_blocked"
jq -e '
    .schema == "agent_bridge.lswr.interaction_feedback_patch_apply_request.v0"
    and .source_schema == "agent_bridge.lswr.interaction_feedback_patch_execution_preflight.v0"
    and .source_preflight_verdict == "blocked"
    and .source_world_verdict == "not_verified"
    and .apply_request_verdict == "blocked"
    and .status == "blocked"
    and .reason == "source_preflight_not_ready"
    and (.failure_reasons | index("source_preflight_not_ready")) != null
    and (.failure_reasons | index("resolved_patch_not_ready")) != null
    and (.failure_reasons | index("resolved_patch_args_required")) != null
    and .apply_request.request_id == null
    and .apply_request.target_runtime == null
    and .apply_request.patch == null
    and .apply_request.ready_for_external_submission == false
    and .apply_request.requires_operator_gate == true
    and .apply_request.requires_external_executor == true
    and .apply_request.apply_performed == false
    and .apply_request.submitted_by_this_tool == false
    and .apply_request.outcome_ingestion_allowed_by_this_tool == false
    and .agent_action_contract.may_submit_to_separate_executor_after_operator_gate == false
    and .agent_action_contract.do_not_apply_patch == true
    and .agent_action_contract.do_not_submit_patch_from_this_tool == true
    and .agent_action_contract.do_not_ingest_outcome == true
    and .agent_action_contract.do_not_write_memory == true
    and .agent_action_contract.do_not_query_live_runtime == true
    and .agent_action_contract.do_not_rewrite_world_verdict == true
    and .agent_action_contract.external_executor_required == true
    and .guardrails.read_only == true
    and .guardrails.submits_apply_request == false
    and .guardrails.applies_patch == false
    and .guardrails.queries_live_runtime == false
    and .implicit_live_runtime_lookup_attempted == false
    and .writes_state == false
    and .store_access_required == false
    and .mcp_tool_registered == false
' "$tmp_lswr_feedback_patch_apply_request_blocked" >/dev/null

tmp_lswr_feedback_patch_apply_request_ready="$tmpdir/lswr-interaction-feedback-patch-apply-request-ready.json"
run cargo run -q -p ab-bridge --example lswr_interaction_feedback_patch_apply_request_smoke -- \
    --with-fixture-context \
    --format json \
    --assert-ready-with-context \
    --assert-read-only > "$tmp_lswr_feedback_patch_apply_request_ready"
jq -e '
    .schema == "agent_bridge.lswr.interaction_feedback_patch_apply_request.v0"
    and .source_schema == "agent_bridge.lswr.interaction_feedback_patch_execution_preflight.v0"
    and .source_preflight_verdict == "ready_for_execution_request"
    and .source_world_verdict == "not_verified"
    and .apply_request_verdict == "ready_for_external_executor"
    and .status == "ready"
    and .reason == "external_apply_request_ready"
    and (.failure_reasons | length) == 0
    and .apply_request.request_id == "apply_request_arrival_bath_move_002"
    and .apply_request.target_runtime.runtime_family == "lswr"
    and .apply_request.target_runtime.world_id == "onsen_live_session"
    and .apply_request.target_runtime.branch_id == "main"
    and .apply_request.target_runtime.executor == "separate_lswr_patch_executor"
    and .apply_request.patch.patch_id == "patch_arrival_bath_move_002"
    and .apply_request.patch.op == "semantic_revision"
    and .apply_request.patch.operation_hint == "increase_walkway_clearance_by_repositioning_entity"
    and .apply_request.patch.target_entities == ["bath"]
    and .apply_request.patch.args.cell == [5, 2]
    and .apply_request.patch.required_citations == ["verify_patch_arrival_bath_move_001", "fb_arrival_crowded_001"]
    and .apply_request.ready_for_external_submission == true
    and .apply_request.requires_operator_gate == true
    and .apply_request.requires_external_executor == true
    and .apply_request.apply_performed == false
    and .apply_request.submitted_by_this_tool == false
    and .apply_request.outcome_ingestion_allowed_by_this_tool == false
    and .agent_action_contract.may_submit_to_separate_executor_after_operator_gate == true
    and .agent_action_contract.do_not_apply_patch == true
    and .agent_action_contract.do_not_submit_patch_from_this_tool == true
    and .agent_action_contract.do_not_ingest_outcome == true
    and .agent_action_contract.do_not_write_memory == true
    and .agent_action_contract.do_not_query_live_runtime == true
    and .agent_action_contract.do_not_rewrite_world_verdict == true
    and .agent_action_contract.external_executor_required == true
    and .agent_action_contract.require_post_apply_verification == true
    and .guardrails.read_only == true
    and .guardrails.submits_apply_request == false
    and .guardrails.applies_patch == false
    and .guardrails.queries_live_runtime == false
    and .implicit_live_runtime_lookup_attempted == false
    and .writes_state == false
    and .store_access_required == false
    and .mcp_tool_registered == false
' "$tmp_lswr_feedback_patch_apply_request_ready" >/dev/null

tmp_lswr_feedback_runtime_executor_design_preflight_blocked="$tmpdir/lswr-interaction-feedback-runtime-executor-design-preflight-blocked.json"
run cargo run -q -p ab-bridge --example lswr_interaction_feedback_runtime_executor_design_preflight_smoke -- \
    --format json \
    --assert-blocked-without-ready-apply-request \
    --assert-read-only > "$tmp_lswr_feedback_runtime_executor_design_preflight_blocked"
jq -e '
    .schema == "agent_bridge.lswr.interaction_feedback_runtime_executor_design_preflight.v0"
    and .source_schema == "agent_bridge.lswr.interaction_feedback_patch_apply_request.v0"
    and .source_apply_request_verdict == "blocked"
    and .source_world_verdict == "not_verified"
    and .design_preflight_verdict == "blocked"
    and .status == "blocked"
    and .reason == "source_apply_request_not_ready"
    and (.failure_reasons | index("source_apply_request_not_ready")) != null
    and (.failure_reasons | index("external_submission_readiness_missing")) != null
    and .executor_design_request.design_request_id == null
    and .executor_design_request.source_apply_request_id == null
    and .executor_design_request.target_runtime == null
    and .executor_design_request.patch == null
    and .executor_design_request.required_design_gates == ["live_runtime_lookup_gate", "operator_submission_gate", "patch_application_gate", "post_apply_verification_gate", "outcome_ingestion_gate"]
    and .executor_design_request.ready_for_design_review == false
    and .executor_design_request.ready_for_live_runtime_lookup == false
    and .executor_design_request.ready_for_submission == false
    and .executor_design_request.ready_for_patch_application == false
    and .executor_design_request.execution_performed == false
    and .executor_design_request.outcome_ingestion_allowed_by_this_tool == false
    and .agent_action_contract.may_design_runtime_executor_after_review == false
    and .agent_action_contract.do_not_query_live_runtime == true
    and .agent_action_contract.do_not_submit_apply_request == true
    and .agent_action_contract.do_not_apply_patch == true
    and .agent_action_contract.do_not_ingest_outcome == true
    and .agent_action_contract.do_not_write_memory == true
    and .agent_action_contract.do_not_rewrite_world_verdict == true
    and .agent_action_contract.require_operator_gate_before_submission == true
    and .agent_action_contract.require_post_apply_verification_design == true
    and .agent_action_contract.require_separate_outcome_ingestion_review == true
    and .guardrails.read_only == true
    and .guardrails.runtime_executor_design_only == true
    and .guardrails.submits_apply_request == false
    and .guardrails.applies_patch == false
    and .guardrails.queries_live_runtime == false
    and .implicit_live_runtime_lookup_attempted == false
    and .writes_state == false
    and .store_access_required == false
    and .mcp_tool_registered == false
' "$tmp_lswr_feedback_runtime_executor_design_preflight_blocked" >/dev/null

tmp_lswr_feedback_runtime_executor_design_preflight_ready="$tmpdir/lswr-interaction-feedback-runtime-executor-design-preflight-ready.json"
run cargo run -q -p ab-bridge --example lswr_interaction_feedback_runtime_executor_design_preflight_smoke -- \
    --with-fixture-context \
    --format json \
    --assert-ready-for-design-review \
    --assert-read-only > "$tmp_lswr_feedback_runtime_executor_design_preflight_ready"
jq -e '
    .schema == "agent_bridge.lswr.interaction_feedback_runtime_executor_design_preflight.v0"
    and .source_schema == "agent_bridge.lswr.interaction_feedback_patch_apply_request.v0"
    and .source_apply_request_verdict == "ready_for_external_executor"
    and .source_world_verdict == "not_verified"
    and .design_preflight_verdict == "ready_for_runtime_executor_design"
    and .status == "ready"
    and .reason == "runtime_executor_design_preflight_ready"
    and (.failure_reasons | length) == 0
    and .executor_design_request.design_request_id == "runtime_executor_design_arrival_bath_move_002"
    and .executor_design_request.source_apply_request_id == "apply_request_arrival_bath_move_002"
    and .executor_design_request.target_runtime.runtime_family == "lswr"
    and .executor_design_request.target_runtime.world_id == "onsen_live_session"
    and .executor_design_request.target_runtime.branch_id == "main"
    and .executor_design_request.target_runtime.executor == "separate_lswr_patch_executor"
    and .executor_design_request.patch.patch_id == "patch_arrival_bath_move_002"
    and .executor_design_request.patch.op == "semantic_revision"
    and .executor_design_request.patch.args.cell == [5, 2]
    and .executor_design_request.patch.required_citations == ["verify_patch_arrival_bath_move_001", "fb_arrival_crowded_001"]
    and .executor_design_request.required_design_gates == ["live_runtime_lookup_gate", "operator_submission_gate", "patch_application_gate", "post_apply_verification_gate", "outcome_ingestion_gate"]
    and .executor_design_request.ready_for_design_review == true
    and .executor_design_request.ready_for_live_runtime_lookup == false
    and .executor_design_request.ready_for_submission == false
    and .executor_design_request.ready_for_patch_application == false
    and .executor_design_request.execution_performed == false
    and .executor_design_request.outcome_ingestion_allowed_by_this_tool == false
    and .executor_design_request.requires_separate_runtime_executor_approval == true
    and .agent_action_contract.may_design_runtime_executor_after_review == true
    and .agent_action_contract.do_not_query_live_runtime == true
    and .agent_action_contract.do_not_submit_apply_request == true
    and .agent_action_contract.do_not_apply_patch == true
    and .agent_action_contract.do_not_ingest_outcome == true
    and .agent_action_contract.do_not_write_memory == true
    and .agent_action_contract.do_not_rewrite_world_verdict == true
    and .agent_action_contract.require_operator_gate_before_submission == true
    and .agent_action_contract.require_post_apply_verification_design == true
    and .agent_action_contract.require_separate_outcome_ingestion_review == true
    and .guardrails.read_only == true
    and .guardrails.runtime_executor_design_only == true
    and .guardrails.submits_apply_request == false
    and .guardrails.applies_patch == false
    and .guardrails.queries_live_runtime == false
    and .implicit_live_runtime_lookup_attempted == false
    and .writes_state == false
    and .store_access_required == false
    and .mcp_tool_registered == false
' "$tmp_lswr_feedback_runtime_executor_design_preflight_ready" >/dev/null

tmp_lswr_feedback_live_runtime_lookup_design_preflight_blocked="$tmpdir/lswr-interaction-feedback-live-runtime-lookup-design-preflight-blocked.json"
run cargo run -q -p ab-bridge --example lswr_interaction_feedback_live_runtime_lookup_design_preflight_smoke -- \
    --format json \
    --assert-blocked-without-ready-design \
    --assert-read-only > "$tmp_lswr_feedback_live_runtime_lookup_design_preflight_blocked"
jq -e '
    .schema == "agent_bridge.lswr.interaction_feedback_live_runtime_lookup_design_preflight.v0"
    and .source_schema == "agent_bridge.lswr.interaction_feedback_runtime_executor_design_preflight.v0"
    and .source_design_preflight_verdict == "blocked"
    and .source_world_verdict == "not_verified"
    and .lookup_design_preflight_verdict == "blocked"
    and .status == "blocked"
    and .reason == "source_design_preflight_not_ready"
    and (.failure_reasons | index("source_design_preflight_not_ready")) != null
    and .lookup_design_request.lookup_design_request_id == null
    and .lookup_design_request.ready_for_lookup_design_review == false
    and .lookup_design_request.ready_for_live_runtime_lookup == false
    and .lookup_design_request.live_runtime_lookup_performed == false
    and .lookup_design_request.host_contact_attempted == false
    and .lookup_design_request.ready_for_submission == false
    and .lookup_design_request.ready_for_patch_application == false
    and .lookup_design_request.execution_performed == false
    and .lookup_design_request.outcome_ingestion_allowed_by_this_tool == false
    and .agent_action_contract.may_design_live_runtime_lookup_after_review == false
    and .agent_action_contract.do_not_contact_live_runtime == true
    and .agent_action_contract.do_not_open_socket == true
    and .agent_action_contract.do_not_query_live_runtime == true
    and .agent_action_contract.do_not_submit_apply_request == true
    and .agent_action_contract.do_not_apply_patch == true
    and .agent_action_contract.do_not_ingest_outcome == true
    and .agent_action_contract.do_not_write_memory == true
    and .agent_action_contract.do_not_rewrite_world_verdict == true
    and .agent_action_contract.require_operator_supplied_host == true
    and .agent_action_contract.require_timeout_budget_design == true
    and .agent_action_contract.require_post_lookup_redaction_design == true
    and .agent_action_contract.require_no_execution_design == true
    and .guardrails.read_only == true
    and .guardrails.live_runtime_lookup_design_only == true
    and .guardrails.contacts_live_runtime == false
    and .guardrails.opens_socket == false
    and .guardrails.submits_apply_request == false
    and .guardrails.applies_patch == false
    and .guardrails.queries_live_runtime == false
    and .implicit_live_runtime_lookup_attempted == false
    and .live_runtime_contact_attempted == false
    and .writes_state == false
    and .store_access_required == false
    and .mcp_tool_registered == false
' "$tmp_lswr_feedback_live_runtime_lookup_design_preflight_blocked" >/dev/null

tmp_lswr_feedback_live_runtime_lookup_design_preflight_ready="$tmpdir/lswr-interaction-feedback-live-runtime-lookup-design-preflight-ready.json"
run cargo run -q -p ab-bridge --example lswr_interaction_feedback_live_runtime_lookup_design_preflight_smoke -- \
    --with-fixture-context \
    --format json \
    --assert-ready-for-lookup-design \
    --assert-read-only > "$tmp_lswr_feedback_live_runtime_lookup_design_preflight_ready"
jq -e '
    .schema == "agent_bridge.lswr.interaction_feedback_live_runtime_lookup_design_preflight.v0"
    and .source_schema == "agent_bridge.lswr.interaction_feedback_runtime_executor_design_preflight.v0"
    and .source_design_preflight_verdict == "ready_for_runtime_executor_design"
    and .source_world_verdict == "not_verified"
    and .lookup_design_preflight_verdict == "ready_for_live_runtime_lookup_design"
    and .status == "ready"
    and .reason == "live_runtime_lookup_design_preflight_ready"
    and (.failure_reasons | length) == 0
    and .lookup_design_request.lookup_design_request_id == "live_runtime_lookup_design_arrival_bath_move_002"
    and .lookup_design_request.source_design_request_id == "runtime_executor_design_arrival_bath_move_002"
    and .lookup_design_request.target_runtime.executor == "separate_lswr_patch_executor"
    and .lookup_design_request.patch.patch_id == "patch_arrival_bath_move_002"
    and .lookup_design_request.patch.op == "semantic_revision"
    and .lookup_design_request.patch.args.cell == [5, 2]
    and .lookup_design_request.patch.required_citations == ["verify_patch_arrival_bath_move_001", "fb_arrival_crowded_001"]
    and .lookup_design_request.required_lookup_gates == ["operator_supplied_host_gate", "host_identity_gate", "timeout_budget_gate", "post_lookup_redaction_gate", "no_execution_gate"]
    and .lookup_design_request.host_binding_requirements.host_endpoint_required_from_operator == true
    and .lookup_design_request.host_binding_requirements.host_endpoint_provided == false
    and .lookup_design_request.host_binding_requirements.default_endpoint == null
    and .lookup_design_request.host_binding_requirements.network_contact_allowed_by_this_tool == false
    and .lookup_design_request.host_binding_requirements.socket_open_allowed_by_this_tool == false
    and .lookup_design_request.ready_for_lookup_design_review == true
    and .lookup_design_request.ready_for_live_runtime_lookup == false
    and .lookup_design_request.live_runtime_lookup_performed == false
    and .lookup_design_request.host_contact_attempted == false
    and .lookup_design_request.ready_for_submission == false
    and .lookup_design_request.ready_for_patch_application == false
    and .lookup_design_request.execution_performed == false
    and .lookup_design_request.outcome_ingestion_allowed_by_this_tool == false
    and .lookup_design_request.requires_separate_runtime_lookup_approval == true
    and .agent_action_contract.may_design_live_runtime_lookup_after_review == true
    and .agent_action_contract.do_not_contact_live_runtime == true
    and .agent_action_contract.do_not_open_socket == true
    and .agent_action_contract.do_not_query_live_runtime == true
    and .agent_action_contract.do_not_submit_apply_request == true
    and .agent_action_contract.do_not_apply_patch == true
    and .agent_action_contract.do_not_ingest_outcome == true
    and .agent_action_contract.do_not_write_memory == true
    and .agent_action_contract.do_not_rewrite_world_verdict == true
    and .agent_action_contract.require_operator_supplied_host == true
    and .agent_action_contract.require_timeout_budget_design == true
    and .agent_action_contract.require_post_lookup_redaction_design == true
    and .agent_action_contract.require_no_execution_design == true
    and .guardrails.read_only == true
    and .guardrails.live_runtime_lookup_design_only == true
    and .guardrails.contacts_live_runtime == false
    and .guardrails.opens_socket == false
    and .guardrails.submits_apply_request == false
    and .guardrails.applies_patch == false
    and .guardrails.queries_live_runtime == false
    and .implicit_live_runtime_lookup_attempted == false
    and .live_runtime_contact_attempted == false
    and .writes_state == false
    and .store_access_required == false
    and .mcp_tool_registered == false
' "$tmp_lswr_feedback_live_runtime_lookup_design_preflight_ready" >/dev/null

tmp_lswr_feedback_runtime_executor_live_lookup_preflight_blocked="$tmpdir/lswr-interaction-feedback-runtime-executor-live-lookup-preflight-blocked.json"
run cargo run -q -p ab-bridge --example lswr_interaction_feedback_runtime_executor_live_lookup_preflight_smoke -- \
    --format json \
    --assert-blocked-without-lookup-snapshot \
    --assert-read-only > "$tmp_lswr_feedback_runtime_executor_live_lookup_preflight_blocked"
jq -e '
    .schema == "agent_bridge.lswr.interaction_feedback_runtime_executor_live_lookup_preflight.v0"
    and .source_schema == "agent_bridge.lswr.interaction_feedback_runtime_executor_design_preflight.v0"
    and .source_design_preflight_verdict == "ready_for_runtime_executor_design"
    and .source_world_verdict == "not_verified"
    and .lookup_snapshot_schema == null
    and .lookup_preflight_verdict == "blocked"
    and .status == "blocked"
    and .reason == "explicit_lookup_snapshot_required"
    and .failure_reasons == ["explicit_lookup_snapshot_required"]
    and .lookup_evidence.lookup_evidence_id == null
    and .lookup_evidence.ready_for_operator_submission_review == false
    and .lookup_evidence.ready_for_submission == false
    and .lookup_evidence.ready_for_patch_application == false
    and .lookup_evidence.mutation_performed == false
    and .lookup_evidence.verification_performed == false
    and .lookup_evidence.outcome_ingestion_allowed == false
    and .agent_action_contract.may_review_operator_submission_after_gate == false
    and .agent_action_contract.do_not_submit_apply_request == true
    and .agent_action_contract.do_not_apply_patch == true
    and .agent_action_contract.do_not_ingest_outcome == true
    and .agent_action_contract.do_not_write_memory == true
    and .agent_action_contract.do_not_rewrite_world_verdict == true
    and .agent_action_contract.do_not_verify_post_apply_result == true
    and .agent_action_contract.require_operator_gate_before_submission == true
    and .agent_action_contract.require_patch_application_gate_after_submission == true
    and .agent_action_contract.require_post_apply_verification_after_application == true
    and .agent_action_contract.require_separate_outcome_ingestion_review == true
    and .guardrails.read_only == true
    and .guardrails.requires_explicit_lookup_snapshot == true
    and .guardrails.lookup_performed_by_this_tool == false
    and .guardrails.submits_apply_request == false
    and .guardrails.applies_patch == false
    and .guardrails.queries_live_runtime == false
    and .guardrails.verifies_post_apply_result == false
    and .implicit_live_runtime_lookup_attempted == false
    and .lookup_performed_by_this_tool == false
    and .writes_state == false
    and .store_access_required == false
    and .mcp_tool_registered == false
' "$tmp_lswr_feedback_runtime_executor_live_lookup_preflight_blocked" >/dev/null

tmp_lswr_feedback_runtime_executor_live_lookup_preflight_ready="$tmpdir/lswr-interaction-feedback-runtime-executor-live-lookup-preflight-ready.json"
run cargo run -q -p ab-bridge --example lswr_interaction_feedback_runtime_executor_live_lookup_preflight_smoke -- \
    --with-lookup-snapshot \
    --format json \
    --assert-ready-for-operator-submission-review \
    --assert-read-only > "$tmp_lswr_feedback_runtime_executor_live_lookup_preflight_ready"
jq -e '
    .schema == "agent_bridge.lswr.interaction_feedback_runtime_executor_live_lookup_preflight.v0"
    and .source_schema == "agent_bridge.lswr.interaction_feedback_runtime_executor_design_preflight.v0"
    and .source_design_preflight_verdict == "ready_for_runtime_executor_design"
    and .source_world_verdict == "not_verified"
    and .lookup_snapshot_schema == "agent_bridge.lswr.runtime_executor.live_lookup_snapshot.v0"
    and .lookup_preflight_verdict == "ready_for_operator_submission_review"
    and .status == "ready"
    and .reason == "live_lookup_preflight_ready_for_operator_submission_review"
    and (.failure_reasons | length) == 0
    and .lookup_evidence.lookup_evidence_id == "live_lookup_arrival_bath_move_002"
    and .lookup_evidence.source_design_request_id == "runtime_executor_design_arrival_bath_move_002"
    and .lookup_evidence.source_apply_request_id == "apply_request_arrival_bath_move_002"
    and .lookup_evidence.runtime_family == "lswr"
    and .lookup_evidence.world_id == "onsen_live_session"
    and .lookup_evidence.branch_id == "main"
    and .lookup_evidence.runtime_generation == "runtime_gen_1284"
    and .lookup_evidence.patch_id == "patch_arrival_bath_move_002"
    and .lookup_evidence.target_entities == ["bath"]
    and .lookup_evidence.required_citations == ["verify_patch_arrival_bath_move_001", "fb_arrival_crowded_001"]
    and .lookup_evidence.ready_for_operator_submission_review == true
    and .lookup_evidence.ready_for_submission == false
    and .lookup_evidence.ready_for_patch_application == false
    and .lookup_evidence.mutation_performed == false
    and .lookup_evidence.verification_performed == false
    and .lookup_evidence.outcome_ingestion_allowed == false
    and .next_allowed_gate == "operator_submission_gate_review"
    and .agent_action_contract.may_review_operator_submission_after_gate == true
    and .agent_action_contract.do_not_submit_apply_request == true
    and .agent_action_contract.do_not_apply_patch == true
    and .agent_action_contract.do_not_ingest_outcome == true
    and .agent_action_contract.do_not_write_memory == true
    and .agent_action_contract.do_not_rewrite_world_verdict == true
    and .agent_action_contract.do_not_verify_post_apply_result == true
    and .agent_action_contract.require_operator_gate_before_submission == true
    and .agent_action_contract.require_patch_application_gate_after_submission == true
    and .agent_action_contract.require_post_apply_verification_after_application == true
    and .agent_action_contract.require_separate_outcome_ingestion_review == true
    and .guardrails.read_only == true
    and .guardrails.requires_explicit_lookup_snapshot == true
    and .guardrails.lookup_performed_by_this_tool == false
    and .guardrails.submits_apply_request == false
    and .guardrails.applies_patch == false
    and .guardrails.queries_live_runtime == false
    and .guardrails.verifies_post_apply_result == false
    and .implicit_live_runtime_lookup_attempted == false
    and .lookup_performed_by_this_tool == false
    and .writes_state == false
    and .store_access_required == false
    and .mcp_tool_registered == false
' "$tmp_lswr_feedback_runtime_executor_live_lookup_preflight_ready" >/dev/null

tmp_lswr_feedback_runtime_executor_operator_submission_token_preflight_blocked="$tmpdir/lswr-interaction-feedback-runtime-executor-operator-submission-token-preflight-blocked.json"
run cargo run -q -p ab-bridge --example lswr_interaction_feedback_runtime_executor_operator_submission_token_preflight_smoke -- \
    --format json \
    --assert-blocked-without-operator-decision \
    --assert-read-only > "$tmp_lswr_feedback_runtime_executor_operator_submission_token_preflight_blocked"
jq -e '
    .schema == "agent_bridge.lswr.interaction_feedback_runtime_executor_operator_submission_token_preflight.v0"
    and .source_schema == "agent_bridge.lswr.interaction_feedback_runtime_executor_live_lookup_preflight.v0"
    and .source_lookup_preflight_verdict == "ready_for_operator_submission_review"
    and .source_world_verdict == "not_verified"
    and .operator_decision_schema == null
    and .submission_token_preflight_verdict == "blocked"
    and .status == "blocked"
    and .reason == "explicit_operator_submission_decision_required"
    and .failure_reasons == ["explicit_operator_submission_decision_required"]
    and .operator_submission_token.token_id == null
    and .operator_submission_token.token_candidate_emitted_by_this_tool == false
    and .operator_submission_token.submission_token_persisted == false
    and .operator_submission_token.ready_for_patch_application_gate_review == false
    and .operator_submission_token.ready_for_executor_submission == false
    and .operator_submission_token.apply_request_submitted == false
    and .operator_submission_token.patch_application_performed == false
    and .operator_submission_token.verification_performed == false
    and .operator_submission_token.outcome_ingestion_allowed == false
    and .next_allowed_gate == "repair_operator_submission_input"
    and .agent_action_contract.may_review_patch_application_after_gate == false
    and .agent_action_contract.do_not_submit_apply_request == true
    and .agent_action_contract.do_not_apply_patch == true
    and .agent_action_contract.do_not_ingest_outcome == true
    and .agent_action_contract.do_not_write_memory == true
    and .agent_action_contract.do_not_rewrite_world_verdict == true
    and .agent_action_contract.do_not_verify_post_apply_result == true
    and .agent_action_contract.do_not_persist_submission_token == true
    and .agent_action_contract.require_patch_application_gate_after_submission_token == true
    and .agent_action_contract.require_post_apply_verification_after_application == true
    and .agent_action_contract.require_separate_outcome_ingestion_review == true
    and .guardrails.read_only == true
    and .guardrails.requires_ready_live_lookup_preflight == true
    and .guardrails.requires_explicit_operator_decision == true
    and .guardrails.operator_authority_scope == "operator_submission_token_only"
    and .guardrails.submits_apply_request == false
    and .guardrails.applies_patch == false
    and .guardrails.verifies_post_apply_result == false
    and .guardrails.outcome_ingestion_allowed == false
    and .guardrails.persists_submission_token == false
    and .submission_performed_by_this_tool == false
    and .apply_request_submitted_by_this_tool == false
    and .patch_application_performed_by_this_tool == false
    and .writes_state == false
    and .store_access_required == false
    and .mcp_tool_registered == false
' "$tmp_lswr_feedback_runtime_executor_operator_submission_token_preflight_blocked" >/dev/null

tmp_lswr_feedback_runtime_executor_operator_submission_token_preflight_ready="$tmpdir/lswr-interaction-feedback-runtime-executor-operator-submission-token-preflight-ready.json"
run cargo run -q -p ab-bridge --example lswr_interaction_feedback_runtime_executor_operator_submission_token_preflight_smoke -- \
    --with-operator-decision \
    --format json \
    --assert-ready-for-patch-application-gate-review \
    --assert-read-only > "$tmp_lswr_feedback_runtime_executor_operator_submission_token_preflight_ready"
jq -e '
    .schema == "agent_bridge.lswr.interaction_feedback_runtime_executor_operator_submission_token_preflight.v0"
    and .source_schema == "agent_bridge.lswr.interaction_feedback_runtime_executor_live_lookup_preflight.v0"
    and .source_lookup_preflight_verdict == "ready_for_operator_submission_review"
    and .source_world_verdict == "not_verified"
    and .operator_decision_schema == "agent_bridge.lswr.runtime_executor.operator_submission_decision.v0"
    and .submission_token_preflight_verdict == "ready_for_patch_application_gate_review"
    and .status == "ready"
    and .reason == "operator_submission_token_preflight_ready_for_patch_application_gate_review"
    and (.failure_reasons | length) == 0
    and .operator_submission_token.token_id == "submit_patch_arrival_bath_move_002"
    and .operator_submission_token.token_type == "operator_submission_gate_token"
    and .operator_submission_token.operator_decision_id == "operator_decision_arrival_bath_move_002"
    and .operator_submission_token.operator_id == "human:owner"
    and .operator_submission_token.lookup_evidence_id == "live_lookup_arrival_bath_move_002"
    and .operator_submission_token.source_design_request_id == "runtime_executor_design_arrival_bath_move_002"
    and .operator_submission_token.source_apply_request_id == "apply_request_arrival_bath_move_002"
    and .operator_submission_token.world_id == "onsen_live_session"
    and .operator_submission_token.branch_id == "main"
    and .operator_submission_token.runtime_generation == "runtime_gen_1284"
    and .operator_submission_token.patch_id == "patch_arrival_bath_move_002"
    and .operator_submission_token.target_entities == ["bath"]
    and .operator_submission_token.idempotency_key == "patch_arrival_bath_move_002/runtime_gen_1284/operator_decision_arrival_bath_move_002"
    and .operator_submission_token.replay_guard.runtime_generation_required == true
    and .operator_submission_token.replay_guard.single_use_intent == true
    and .operator_submission_token.replay_guard.requires_fresh_g1_lookup_evidence == true
    and .operator_submission_token.token_candidate_emitted_by_this_tool == true
    and .operator_submission_token.submission_token_persisted == false
    and .operator_submission_token.ready_for_patch_application_gate_review == true
    and .operator_submission_token.ready_for_executor_submission == false
    and .operator_submission_token.apply_request_submitted == false
    and .operator_submission_token.patch_application_performed == false
    and .operator_submission_token.verification_performed == false
    and .operator_submission_token.outcome_ingestion_allowed == false
    and .next_allowed_gate == "patch_application_gate_review"
    and .agent_action_contract.may_review_patch_application_after_gate == true
    and .agent_action_contract.do_not_submit_apply_request == true
    and .agent_action_contract.do_not_apply_patch == true
    and .agent_action_contract.do_not_ingest_outcome == true
    and .agent_action_contract.do_not_write_memory == true
    and .agent_action_contract.do_not_rewrite_world_verdict == true
    and .agent_action_contract.do_not_verify_post_apply_result == true
    and .agent_action_contract.do_not_persist_submission_token == true
    and .agent_action_contract.require_patch_application_gate_after_submission_token == true
    and .agent_action_contract.require_post_apply_verification_after_application == true
    and .agent_action_contract.require_separate_outcome_ingestion_review == true
    and .guardrails.read_only == true
    and .guardrails.requires_ready_live_lookup_preflight == true
    and .guardrails.requires_explicit_operator_decision == true
    and .guardrails.operator_authority_scope == "operator_submission_token_only"
    and .guardrails.submits_apply_request == false
    and .guardrails.applies_patch == false
    and .guardrails.verifies_post_apply_result == false
    and .guardrails.outcome_ingestion_allowed == false
    and .guardrails.persists_submission_token == false
    and .submission_performed_by_this_tool == false
    and .apply_request_submitted_by_this_tool == false
    and .patch_application_performed_by_this_tool == false
    and .writes_state == false
    and .store_access_required == false
    and .mcp_tool_registered == false
' "$tmp_lswr_feedback_runtime_executor_operator_submission_token_preflight_ready" >/dev/null

tmp_lswr_feedback_runtime_executor_patch_application_gate_preflight_blocked="$tmpdir/lswr-interaction-feedback-runtime-executor-patch-application-gate-preflight-blocked.json"
run cargo run -q -p ab-bridge --example lswr_interaction_feedback_runtime_executor_patch_application_gate_preflight_smoke -- \
    --format json \
    --assert-blocked-without-patch-application-gate-decision \
    --assert-read-only > "$tmp_lswr_feedback_runtime_executor_patch_application_gate_preflight_blocked"
jq -e '
    .schema == "agent_bridge.lswr.interaction_feedback_runtime_executor_patch_application_gate_preflight.v0"
    and .source_schema == "agent_bridge.lswr.interaction_feedback_runtime_executor_operator_submission_token_preflight.v0"
    and .source_submission_token_preflight_verdict == "ready_for_patch_application_gate_review"
    and .source_world_verdict == "not_verified"
    and .patch_application_gate_decision_schema == null
    and .patch_application_gate_preflight_verdict == "blocked"
    and .status == "blocked"
    and .reason == "explicit_patch_application_gate_decision_required"
    and .failure_reasons == ["explicit_patch_application_gate_decision_required"]
    and .patch_application_gate.gate_id == null
    and .patch_application_gate.ready_for_separate_patch_executor_invocation == false
    and .patch_application_gate.separate_patch_executor_invocation_allowed_after_this_gate == false
    and .patch_application_gate.executor_invocation_performed_by_this_tool == false
    and .patch_application_gate.apply_request_submitted == false
    and .patch_application_gate.patch_application_performed == false
    and .patch_application_gate.verification_performed == false
    and .patch_application_gate.outcome_ingestion_allowed == false
    and .next_allowed_gate == "repair_patch_application_gate_input"
    and .agent_action_contract.may_invoke_separate_patch_executor_after_gate == false
    and .agent_action_contract.do_not_invoke_patch_executor == true
    and .agent_action_contract.do_not_submit_apply_request == true
    and .agent_action_contract.do_not_apply_patch == true
    and .agent_action_contract.do_not_ingest_outcome == true
    and .agent_action_contract.do_not_write_memory == true
    and .agent_action_contract.do_not_rewrite_world_verdict == true
    and .agent_action_contract.do_not_verify_post_apply_result == true
    and .agent_action_contract.do_not_persist_submission_token == true
    and .agent_action_contract.require_post_apply_verification_after_application == true
    and .agent_action_contract.require_separate_outcome_ingestion_review == true
    and .guardrails.read_only == true
    and .guardrails.requires_ready_operator_submission_token_preflight == true
    and .guardrails.requires_explicit_patch_application_gate_decision == true
    and .guardrails.patch_application_authority_scope == "patch_application_executor_invocation_gate_only"
    and .guardrails.invokes_patch_executor == false
    and .guardrails.submits_apply_request == false
    and .guardrails.applies_patch == false
    and .guardrails.verifies_post_apply_result == false
    and .guardrails.outcome_ingestion_allowed == false
    and .guardrails.persists_submission_token == false
    and .executor_invocation_performed_by_this_tool == false
    and .apply_request_submitted_by_this_tool == false
    and .patch_application_performed_by_this_tool == false
    and .writes_state == false
    and .store_access_required == false
    and .mcp_tool_registered == false
' "$tmp_lswr_feedback_runtime_executor_patch_application_gate_preflight_blocked" >/dev/null

tmp_lswr_feedback_runtime_executor_patch_application_gate_preflight_ready="$tmpdir/lswr-interaction-feedback-runtime-executor-patch-application-gate-preflight-ready.json"
run cargo run -q -p ab-bridge --example lswr_interaction_feedback_runtime_executor_patch_application_gate_preflight_smoke -- \
    --with-patch-application-gate-decision \
    --format json \
    --assert-ready-for-separate-executor-invocation \
    --assert-read-only > "$tmp_lswr_feedback_runtime_executor_patch_application_gate_preflight_ready"
jq -e '
    .schema == "agent_bridge.lswr.interaction_feedback_runtime_executor_patch_application_gate_preflight.v0"
    and .source_schema == "agent_bridge.lswr.interaction_feedback_runtime_executor_operator_submission_token_preflight.v0"
    and .source_submission_token_preflight_verdict == "ready_for_patch_application_gate_review"
    and .source_world_verdict == "not_verified"
    and .patch_application_gate_decision_schema == "agent_bridge.lswr.runtime_executor.patch_application_gate_decision.v0"
    and .patch_application_gate_preflight_verdict == "ready_for_separate_executor_invocation"
    and .status == "ready"
    and .reason == "patch_application_gate_preflight_ready_for_separate_executor_invocation"
    and (.failure_reasons | length) == 0
    and .patch_application_gate.gate_id == "patch_application_gate_arrival_bath_move_002"
    and .patch_application_gate.gate_type == "patch_application_executor_invocation_gate"
    and .patch_application_gate.gate_decision_id == "patch_application_gate_decision_arrival_bath_move_002"
    and .patch_application_gate.operator_id == "human:owner"
    and .patch_application_gate.operator_submission_token_id == "submit_patch_arrival_bath_move_002"
    and .patch_application_gate.operator_submission_token_idempotency_key == "patch_arrival_bath_move_002/runtime_gen_1284/operator_decision_arrival_bath_move_002"
    and .patch_application_gate.operator_submission_decision_id == "operator_decision_arrival_bath_move_002"
    and .patch_application_gate.lookup_evidence_id == "live_lookup_arrival_bath_move_002"
    and .patch_application_gate.source_apply_request_id == "apply_request_arrival_bath_move_002"
    and .patch_application_gate.world_id == "onsen_live_session"
    and .patch_application_gate.branch_id == "main"
    and .patch_application_gate.runtime_generation == "runtime_gen_1284"
    and .patch_application_gate.patch_id == "patch_arrival_bath_move_002"
    and .patch_application_gate.target_entities == ["bath"]
    and .patch_application_gate.idempotency_key == "patch_arrival_bath_move_002/runtime_gen_1284/submit_patch_arrival_bath_move_002/patch_application_gate_decision_arrival_bath_move_002"
    and .patch_application_gate.replay_guard.runtime_generation_required == true
    and .patch_application_gate.replay_guard.single_use_intent == true
    and .patch_application_gate.replay_guard.requires_fresh_g2_submission_token_preflight == true
    and .patch_application_gate.ready_for_separate_patch_executor_invocation == true
    and .patch_application_gate.separate_patch_executor_invocation_allowed_after_this_gate == true
    and .patch_application_gate.executor_invocation_performed_by_this_tool == false
    and .patch_application_gate.apply_request_submitted == false
    and .patch_application_gate.patch_application_performed == false
    and .patch_application_gate.verification_performed == false
    and .patch_application_gate.outcome_ingestion_allowed == false
    and .next_allowed_gate == "separate_patch_application_executor_invocation"
    and .agent_action_contract.may_invoke_separate_patch_executor_after_gate == true
    and .agent_action_contract.do_not_invoke_patch_executor == true
    and .agent_action_contract.do_not_submit_apply_request == true
    and .agent_action_contract.do_not_apply_patch == true
    and .agent_action_contract.do_not_ingest_outcome == true
    and .agent_action_contract.do_not_write_memory == true
    and .agent_action_contract.do_not_rewrite_world_verdict == true
    and .agent_action_contract.do_not_verify_post_apply_result == true
    and .agent_action_contract.do_not_persist_submission_token == true
    and .agent_action_contract.require_post_apply_verification_after_application == true
    and .agent_action_contract.require_separate_outcome_ingestion_review == true
    and .guardrails.read_only == true
    and .guardrails.requires_ready_operator_submission_token_preflight == true
    and .guardrails.requires_explicit_patch_application_gate_decision == true
    and .guardrails.patch_application_authority_scope == "patch_application_executor_invocation_gate_only"
    and .guardrails.invokes_patch_executor == false
    and .guardrails.submits_apply_request == false
    and .guardrails.applies_patch == false
    and .guardrails.verifies_post_apply_result == false
    and .guardrails.outcome_ingestion_allowed == false
    and .guardrails.persists_submission_token == false
    and .executor_invocation_performed_by_this_tool == false
    and .apply_request_submitted_by_this_tool == false
    and .patch_application_performed_by_this_tool == false
    and .writes_state == false
    and .store_access_required == false
    and .mcp_tool_registered == false
' "$tmp_lswr_feedback_runtime_executor_patch_application_gate_preflight_ready" >/dev/null

tmp_missing_lswr_feedback_input="$tmpdir/missing-lswr-interaction-feedback-input.json"
printf '{}\n' > "$tmp_missing_lswr_feedback_input"
tmp_missing_lswr_feedback_consumption_preflight="$tmpdir/missing-lswr-interaction-feedback-consumption-preflight.json"
run cargo run -q -p ab-bridge --no-default-features -- \
    bio-cortex lswr-interaction-feedback-consumption-preflight \
    --input-json "$tmp_missing_lswr_feedback_input" \
    --json > "$tmp_missing_lswr_feedback_consumption_preflight"
jq -e '
    .schema == "agent_bridge.lswr.interaction_feedback_consumption_preflight.v0"
    and .accepted == false
    and .preflight_verdict == "blocked"
    and .status == "blocked"
    and .input_kind == "missing_or_invalid"
    and .source_kind == "none"
    and .world_verdict == "not_verified"
    and .reason == "C1:explicit_input_only"
    and (.blockers | index("explicit_packet_or_fixture_required")) != null
    and .packet == null
    and .guardrails.read_only == true
    and .guardrails.writes_state == false
    and .guardrails.store_access_required == false
    and .guardrails.mcp_tool_registered == false
    and .guardrails.implicit_live_runtime_lookup_allowed == false
    and .implicit_live_runtime_lookup_attempted == false
' "$tmp_missing_lswr_feedback_consumption_preflight" >/dev/null

jq -e '
    .schema == "agent_bridge.biocortex_retrieval.opt_in_batch_diagnostic_query_cases.v0"
    and .read_only == true
    and .input_boundary.raw_queries_are_fixture_inputs == true
    and .input_boundary.raw_queries_may_be_read_by_cli == true
    and .input_boundary.raw_queries_must_not_be_returned_by_batch_diagnostics == true
    and .input_boundary.raw_keys_included == false
    and .input_boundary.content_included == false
    and .input_boundary.side_signal_raw_included == false
    and .input_boundary.decision_packet_included == false
    and (.query_cases | length) == 6
    and ([.query_cases[].class_label] | sort) == ["approval_gate","baseline_retrieval","fail_open","mcp_surface","rank_movement","runtime_adapter"]
    and .expected_batch_contract.schema == "agent_bridge.biocortex_retrieval.opt_in_batch_diagnostics.v0"
    and .expected_batch_contract.query_count == 6
    and .expected_batch_contract.raw_queries_included == false
    and .expected_batch_contract.raw_keys_included == false
    and .expected_batch_contract.content_included == false
    and .expected_batch_contract.side_signal_raw_included == false
    and .expected_batch_contract.default_search_order_change_allowed == false
    and .expected_batch_contract.default_calls_unchanged == true
' "$opt_in_batch_query_cases" >/dev/null
jq -e '
    .schema == "agent_bridge.biocortex_retrieval.opt_in_controlled_order_fixture.v0"
    and .read_only == false
    and .safety_boundary.requires_agent_bridge_db_override == true
    and .safety_boundary.requires_non_production_store_write_ack == true
    and .safety_boundary.writes_only_fixture_memories == true
    and .safety_boundary.writes_approval == false
    and .safety_boundary.registers_embedding_backend == false
    and .safety_boundary.raw_queries_are_fixture_inputs == true
    and .safety_boundary.raw_queries_must_not_be_returned_by_runner == true
    and .safety_boundary.raw_keys_must_not_be_returned_by_runner == true
    and .safety_boundary.content_must_not_be_returned_by_runner == true
    and .safety_boundary.side_signal_raw_must_not_be_returned_by_runner == true
    and .safety_boundary.default_search_order_change_allowed == false
    and .safety_boundary.default_calls_unchanged == true
    and (.memory_records | length) == 10
    and (.query_cases | length) == 5
    and .expected.min_actual_order_changed_count == 0
    and .expected.min_experimental_source_count == 5
    and .expected.min_side_signal_ok_count == 5
' "$opt_in_expanded_corpus_fixture" >/dev/null
jq -e '
    .schema == "agent_bridge.biocortex_retrieval.opt_in_controlled_order_fixture.v0"
    and .read_only == false
    and .safety_boundary.requires_agent_bridge_db_override == true
    and .safety_boundary.requires_non_production_store_write_ack == true
    and .safety_boundary.writes_only_fixture_memories == true
    and .safety_boundary.writes_approval == false
    and .safety_boundary.registers_embedding_backend == false
    and .safety_boundary.raw_queries_are_fixture_inputs == true
    and .safety_boundary.raw_queries_must_not_be_returned_by_runner == true
    and .safety_boundary.raw_keys_must_not_be_returned_by_runner == true
    and .safety_boundary.content_must_not_be_returned_by_runner == true
    and .safety_boundary.side_signal_raw_must_not_be_returned_by_runner == true
    and .safety_boundary.default_search_order_change_allowed == false
    and .safety_boundary.default_calls_unchanged == true
    and (.memory_records | length) == 2
    and (.query_cases | length) == 1
    and .query_cases[0].class_label == "controlled_rank_movement"
    and .expected.min_actual_order_changed_count == 1
    and .expected.min_experimental_source_count == 1
    and .expected.min_side_signal_ok_count == 1
' "$opt_in_controlled_order_fixture" >/dev/null
jq -e '
    .schema == "agent_bridge.biocortex_retrieval.opt_in_experiment_plan.v0"
    and .status == "loopback_lswr_host_attach_preflight_blocked"
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
    and .runtime_readiness_packet_implemented == true
    and .downstream_aio_integration_checkpoint_selected == true
    and .downstream_aio_runtime_evidence_handoff_ready == true
    and .ssb_lswr_action_result_review_fixture_ready == true
    and .read_only_ssb_adapter_fixture_ready == true
    and .live_lswr_action_result_runtime_evidence_observed_not_verified == true
    and .loopback_lswr_action_result_verified_fixture_host_observed == true
    and .loopback_lswr_host_attach_preflight_blocked == true
    and .onsen_step_b_source_resolution_blocked == true
    and .onsen_step_b_host_source_probe_script_ready == true
    and .onsen_step_b_host_launch_plan_script_ready == true
    and .onsen_step_b_host_launch_plan_recorded == true
    and .downstream_aio_checkpoint_selection.selection_status == "downstream_aio_integration_checkpoint_selected"
    and .downstream_aio_checkpoint_selection.selected_checkpoint == "semantic_system_bus_lswr_action_result_runtime_evidence_checkpoint"
    and .downstream_aio_checkpoint_selection.selected_checkpoint_family == "semantic_system_bus"
    and .downstream_aio_checkpoint_selection.selected_surface == "lswr_action_result_runtime_evidence"
    and .downstream_aio_checkpoint_selection.direct_aiot_consumption_selected == false
    and .downstream_aio_checkpoint_selection.checkpoint_must_be_read_only == true
    and .downstream_aio_checkpoint_selection.first_handoff_schema == "agent_bridge.biocortex_retrieval.downstream_aio_runtime_evidence_handoff.v0"
    and .downstream_aio_checkpoint_selection.default_search_order_change_allowed == false
    and .downstream_aio_checkpoint_selection.writes_approval == false
    and .downstream_aio_runtime_evidence_handoff.status == "ready"
    and .downstream_aio_runtime_evidence_handoff.schema == "agent_bridge.biocortex_retrieval.downstream_aio_runtime_evidence_handoff.v0"
    and .downstream_aio_runtime_evidence_handoff.handoff_ready == true
    and .downstream_aio_runtime_evidence_handoff.selected_checkpoint == "semantic_system_bus_lswr_action_result_runtime_evidence_checkpoint"
    and .downstream_aio_runtime_evidence_handoff.target_schema_family == "agent_bridge.semantic_bus.action_result.v0"
    and .downstream_aio_runtime_evidence_handoff.may_compare_against_ssb_runtime_evidence_contract == true
    and .downstream_aio_runtime_evidence_handoff.may_emit_ssb_adapter_fixture == true
    and .downstream_aio_runtime_evidence_handoff.may_execute_lswr_actions == false
    and .downstream_aio_runtime_evidence_handoff.may_call_aiot_runtime == false
    and .downstream_aio_runtime_evidence_handoff.calls_memory_search == false
    and .downstream_aio_runtime_evidence_handoff.runs_biocortex == false
    and .downstream_aio_runtime_evidence_handoff.writes_approval == false
    and .downstream_aio_runtime_evidence_handoff.default_search_order_change_allowed == false
    and .ssb_lswr_action_result_review_fixture.status == "ready"
    and .ssb_lswr_action_result_review_fixture.schema == "agent_bridge.biocortex_retrieval.ssb_lswr_action_result_review_fixture.v0"
    and .ssb_lswr_action_result_review_fixture.review_fixture_ready == true
    and .ssb_lswr_action_result_review_fixture.target_schema_family == "agent_bridge.semantic_bus.action_result.v0"
    and .ssb_lswr_action_result_review_fixture.emits_action_result == false
    and .ssb_lswr_action_result_review_fixture.executes_lswr_actions == false
    and .ssb_lswr_action_result_review_fixture.calls_aiot_runtime == false
    and .ssb_lswr_action_result_review_fixture.calls_memory_search == false
    and .ssb_lswr_action_result_review_fixture.runs_biocortex == false
    and .ssb_lswr_action_result_review_fixture.writes_approval == false
    and .ssb_lswr_action_result_review_fixture.default_search_order_change_allowed == false
    and .read_only_ssb_adapter_fixture.status == "ready"
    and .read_only_ssb_adapter_fixture.schema == "agent_bridge.biocortex_retrieval.read_only_ssb_adapter_fixture.v0"
    and .read_only_ssb_adapter_fixture.fixture_ready == true
    and .read_only_ssb_adapter_fixture.target_schema_family == "agent_bridge.semantic_bus.action_result.v0"
    and .read_only_ssb_adapter_fixture.candidate_action_result_schema == "agent_bridge.semantic_bus.action_result.v0"
    and .read_only_ssb_adapter_fixture.fixture_only == true
    and .read_only_ssb_adapter_fixture.runtime_executed == false
    and .read_only_ssb_adapter_fixture.emits_runtime_action_result == false
    and .read_only_ssb_adapter_fixture.executes_lswr_actions == false
    and .read_only_ssb_adapter_fixture.calls_aiot_runtime == false
    and .read_only_ssb_adapter_fixture.calls_memory_search == false
    and .read_only_ssb_adapter_fixture.runs_biocortex == false
    and .read_only_ssb_adapter_fixture.writes_approval == false
    and .read_only_ssb_adapter_fixture.default_search_order_change_allowed == false
    and .live_lswr_action_result_runtime_evidence.status == "observed_not_verified"
    and .live_lswr_action_result_runtime_evidence.schema == "agent_bridge.biocortex_retrieval.live_lswr_action_result_runtime_evidence.v0"
    and .live_lswr_action_result_runtime_evidence.read_only == true
    and .live_lswr_action_result_runtime_evidence.target_schema_family == "agent_bridge.semantic_bus.action_result.v0"
    and .live_lswr_action_result_runtime_evidence.action_result_schema == "agent_bridge.semantic_bus.action_result.v0"
    and .live_lswr_action_result_runtime_evidence.world_tool == "world_visibility_query"
    and .live_lswr_action_result_runtime_evidence.mcp_tool_profile == "all"
    and .live_lswr_action_result_runtime_evidence.mcp_tool_listed == true
    and .live_lswr_action_result_runtime_evidence.mcp_world_tool_call_executed == true
    and .live_lswr_action_result_runtime_evidence.runtime_host_reached == false
    and .live_lswr_action_result_runtime_evidence.action_result_verdict == "not_verified"
    and .live_lswr_action_result_runtime_evidence.action_result_reason == "world_host_unreachable"
    and .live_lswr_action_result_runtime_evidence.verified_to == null
    and .live_lswr_action_result_runtime_evidence.recover == "inspect_host_or_visibility_evidence"
    and .live_lswr_action_result_runtime_evidence.raw_available == false
    and .live_lswr_action_result_runtime_evidence.host_response_field_present == false
    and .live_lswr_action_result_runtime_evidence.host_response_is_null == false
    and .live_lswr_action_result_runtime_evidence.host_response_included == false
    and .live_lswr_action_result_runtime_evidence.verified_runtime_action_result_collected == false
    and .live_lswr_action_result_runtime_evidence.not_verified_runtime_action_result_collected == true
    and .live_lswr_action_result_runtime_evidence.executes_lswr_actions == false
    and .live_lswr_action_result_runtime_evidence.emits_durable_runtime_action_result == false
    and .live_lswr_action_result_runtime_evidence.calls_aiot_runtime == false
    and .live_lswr_action_result_runtime_evidence.calls_memory_search == false
    and .live_lswr_action_result_runtime_evidence.runs_biocortex == false
    and .live_lswr_action_result_runtime_evidence.writes_approval == false
    and .live_lswr_action_result_runtime_evidence.default_search_order_change_allowed == false
    and .loopback_lswr_action_result_verified_probe.status == "verified_fixture_host_observed"
    and .loopback_lswr_action_result_verified_probe.schema == "agent_bridge.biocortex_retrieval.loopback_lswr_action_result_verified_probe.v0"
    and .loopback_lswr_action_result_verified_probe.read_only == true
    and .loopback_lswr_action_result_verified_probe.world_tool == "world_visibility_query"
    and .loopback_lswr_action_result_verified_probe.mcp_tool_profile == "all"
    and .loopback_lswr_action_result_verified_probe.mcp_tool_listed == true
    and .loopback_lswr_action_result_verified_probe.mcp_world_tool_call_executed == true
    and .loopback_lswr_action_result_verified_probe.loopback_host_reached == true
    and .loopback_lswr_action_result_verified_probe.fixture_host == true
    and .loopback_lswr_action_result_verified_probe.real_onsen_runtime == false
    and .loopback_lswr_action_result_verified_probe.human_visible_viewport_verified == false
    and .loopback_lswr_action_result_verified_probe.action_result_verdict == "verified"
    and .loopback_lswr_action_result_verified_probe.verified_to == "onsen_live_root_viewport"
    and .loopback_lswr_action_result_verified_probe.raw_available == true
    and .loopback_lswr_action_result_verified_probe.verified_fixture_action_result_collected == true
    and .loopback_lswr_action_result_verified_probe.verified_real_onsen_action_result_collected == false
    and .loopback_lswr_action_result_verified_probe.calls_memory_search == false
    and .loopback_lswr_action_result_verified_probe.runs_biocortex == false
    and .loopback_lswr_action_result_verified_probe.writes_approval == false
    and .loopback_lswr_action_result_verified_probe.default_search_order_change_allowed == false
    and .loopback_lswr_host_attach_preflight.status == "blocked_missing_loopback_host_checkout"
    and .loopback_lswr_host_attach_preflight.schema == "agent_bridge.biocortex_retrieval.loopback_lswr_host_attach_preflight.v0"
    and .loopback_lswr_host_attach_preflight.read_only == true
    and .loopback_lswr_host_attach_preflight.target_endpoint == "127.0.0.1:37691"
    and .loopback_lswr_host_attach_preflight.target_protocol == "newline_json_tcp"
    and .loopback_lswr_host_attach_preflight.world_visibility_query_present == true
    and .loopback_lswr_host_attach_preflight.mcp_tool_profile == "all"
    and .loopback_lswr_host_attach_preflight.port_37691_listening == false
    and .loopback_lswr_host_attach_preflight.onsen_step_b_checkout_present == false
    and .loopback_lswr_host_attach_preflight.web_prototype_is_loopback_lsswr_host == false
    and .loopback_lswr_host_attach_preflight.can_rerun_live_probe == true
    and .loopback_lswr_host_attach_preflight.can_collect_verified_runtime_action_result_now == false
    and .loopback_lswr_host_attach_preflight.calls_memory_search == false
    and .loopback_lswr_host_attach_preflight.runs_biocortex == false
    and .loopback_lswr_host_attach_preflight.writes_approval == false
    and .loopback_lswr_host_attach_preflight.default_search_order_change_allowed == false
    and .loopback_lswr_host_attach_preflight.next_step == "completed_by_onsen_step_b_source_resolution"
    and .loopback_lswr_host_attach_preflight.next_step_completed == true
    and .onsen_step_b_source_resolution.status == "blocked_missing_onsen_step_b_source"
    and .onsen_step_b_source_resolution.schema == "agent_bridge.biocortex_retrieval.onsen_step_b_source_resolution.v0"
    and .onsen_step_b_source_resolution.read_only == true
    and .onsen_step_b_source_resolution.documented_worktree == "/Users/pallasting/Projects/onsen-hd-live-semantic-phase0"
    and .onsen_step_b_source_resolution.documented_branch == "codex/live-semantic-phase0-t1"
    and .onsen_step_b_source_resolution.documented_head == "10d58ee"
    and .onsen_step_b_source_resolution.expected_endpoint == "127.0.0.1:37691"
    and .onsen_step_b_source_resolution.expected_protocol == "newline_json_tcp"
    and .onsen_step_b_source_resolution.linux_candidate_worktree_present == false
    and .onsen_step_b_source_resolution.port_37691_listening == false
    and .onsen_step_b_source_resolution.remote_resolution_attempted == true
    and .onsen_step_b_source_resolution.usable_remote_found == false
    and .onsen_step_b_source_resolution.onsen_hd_remote_checked == true
    and .onsen_step_b_source_resolution.onsen_hd_remote_accessible == true
    and .onsen_step_b_source_resolution.onsen_hd_remote_head == "79993b494cf6e41fbacb33f2ab2c6ea9ea544771"
    and .onsen_step_b_source_resolution.onsen_hd_remote_is_accepted_step_b_source == false
    and .onsen_step_b_source_resolution.onsen_hd_remote_has_expected_branch == false
    and .onsen_step_b_source_resolution.onsen_hd_remote_has_documented_head == false
    and .onsen_step_b_source_resolution.onsen_hd_remote_has_world_tool_host_contract == false
    and .onsen_step_b_source_resolution.real_onsen_step_b_host_source_found == false
    and .onsen_step_b_source_resolution.can_launch_real_onsen_step_b_host_now == false
    and .onsen_step_b_source_resolution.can_collect_verified_runtime_action_result_now == false
    and .onsen_step_b_source_resolution.blocked_by == "missing_checkout_or_accessible_repository_url"
    and .onsen_step_b_source_resolution.recovery_probe_script == "scripts/probe-onsen-step-b-host-source.sh"
    and .onsen_step_b_source_resolution.recovery_probe_ready == true
    and .onsen_step_b_source_resolution.host_launch_plan_script == "scripts/plan-onsen-step-b-host-launch.sh"
    and .onsen_step_b_source_resolution.host_launch_plan_ready == true
    and .onsen_step_b_source_resolution.host_launch_plan_does_not_start_host == true
    and .onsen_step_b_source_resolution.host_launch_plan_operator_launch_required == true
    and .onsen_step_b_source_resolution.host_launch_plan_fixture == "docs/design/fixtures/biocortex-retrieval-onsen-step-b-host-launch-plan-2026-06-15.json"
    and .onsen_step_b_source_resolution.host_launch_plan_status == "blocked_missing_onsen_step_b_source"
    and .onsen_step_b_source_resolution.host_launch_plan_fixture_recorded == true
    and .onsen_step_b_source_resolution.recovery_probe_requires_checkout_branch_or_head_match == true
    and .onsen_step_b_source_resolution.recovery_probe_rejects_nonmatching_git_checkout == true
    and .onsen_step_b_host_launch_plan.status == "blocked_missing_onsen_step_b_source"
    and .onsen_step_b_host_launch_plan.schema == "agent_bridge.biocortex_retrieval.onsen_step_b_host_launch_plan.v0"
    and .onsen_step_b_host_launch_plan.read_only == true
    and .onsen_step_b_host_launch_plan.source_found == false
    and .onsen_step_b_host_launch_plan.ready_for_live_probe == false
    and .onsen_step_b_host_launch_plan.operator_action_required == false
    and .onsen_step_b_host_launch_plan.agent_bridge_starts_host == false
    and .onsen_step_b_host_launch_plan.expected_endpoint == "127.0.0.1:37691"
    and .onsen_step_b_host_launch_plan.required_world_tool == "world_visibility_query"
    and .onsen_step_b_host_launch_plan.starts_host == false
    and .onsen_step_b_host_launch_plan.clones_repository == false
    and .onsen_step_b_host_launch_plan.executes_lswr_actions == false
    and .onsen_step_b_host_launch_plan.calls_memory_search == false
    and .onsen_step_b_host_launch_plan.runs_biocortex == false
    and .onsen_step_b_host_launch_plan.writes_approval == false
    and .onsen_step_b_host_launch_plan.default_search_order_change_allowed == false
    and .onsen_step_b_host_launch_plan.next_step == "provide_or_sync_onsen_step_b_checkout_or_repository_url"
    and .onsen_step_b_source_resolution.calls_memory_search == false
    and .onsen_step_b_source_resolution.runs_biocortex == false
    and .onsen_step_b_source_resolution.writes_approval == false
    and .onsen_step_b_source_resolution.default_search_order_change_allowed == false
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
    and .implemented_store_opt_in_runtime_adapter_connection.cli == "agent-bridge bio-cortex retrieval-opt-in-store-trial"
    and .implemented_store_opt_in_runtime_adapter_connection.mcp_tool == "biocortex_retrieval_opt_in_store_trial"
    and .implemented_store_opt_in_runtime_adapter_connection.schema == "agent_bridge.biocortex_retrieval.opt_in_store_trial.v0"
    and .implemented_store_opt_in_runtime_adapter_connection.implementation_stage == "store_opt_in_runtime_adapter_connection"
    and .implemented_store_opt_in_runtime_adapter_connection.authorized_scope == "explicit_opt_in_fts_runtime_influence"
    and .implemented_store_opt_in_runtime_adapter_connection.authorized_mode == "fts"
    and .implemented_store_opt_in_runtime_adapter_connection.requires_runtime_influence_decision_packet == true
    and .implemented_store_opt_in_runtime_adapter_connection.requires_decision_packet_runtime_adapter_approved == true
    and .implemented_store_opt_in_runtime_adapter_connection.requires_decision_packet_ordering_connection_authorized == true
    and .implemented_store_opt_in_runtime_adapter_connection.accepts_aggregate_backed_decision_packet == true
    and .implemented_store_opt_in_runtime_adapter_connection.requires_aggregate_ready_when_provided == true
    and .implemented_store_opt_in_runtime_adapter_connection.legacy_decision_packet_without_aggregate_allowed == true
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
    and .implemented_store_opt_in_runtime_adapter_connection.redacted_evidence_aggregate_included == false
    and .implemented_store_opt_in_runtime_adapter_connection.aggregate_evidence_summary_included == false
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
    and .implemented_store_opt_in_batch_diagnostics.cli == "agent-bridge bio-cortex retrieval-opt-in-batch-diagnostics"
    and .implemented_store_opt_in_batch_diagnostics.cli_accepts_query_cases_json == true
    and .implemented_store_opt_in_batch_diagnostics.query_cases_fixture == "docs/design/fixtures/biocortex-retrieval-opt-in-batch-diagnostic-queries-2026-06-12.json"
    and .implemented_store_opt_in_batch_diagnostics.mcp_tool == "biocortex_retrieval_opt_in_batch_diagnostics"
    and .implemented_store_opt_in_batch_diagnostics.schema == "agent_bridge.biocortex_retrieval.opt_in_batch_diagnostics.v0"
    and .implemented_store_opt_in_batch_diagnostics.implementation_stage == "store_opt_in_batch_diagnostics"
    and .implemented_store_opt_in_batch_diagnostics.authorized_scope == "explicit_opt_in_fts_runtime_influence"
    and .implemented_store_opt_in_batch_diagnostics.reuses_store_trial_gate == true
    and .implemented_store_opt_in_batch_diagnostics.accepts_aggregate_backed_decision_packet == true
    and .implemented_store_opt_in_batch_diagnostics.requires_aggregate_ready_when_provided == true
    and .implemented_store_opt_in_batch_diagnostics.legacy_decision_packet_without_aggregate_allowed == true
    and .implemented_store_opt_in_batch_diagnostics.calls_memory_search == true
    and .implemented_store_opt_in_batch_diagnostics.runs_biocortex_only_when_store_trial_allows == true
    and .implemented_store_opt_in_batch_diagnostics.calls_store_opt_in_wrapper == true
    and .implemented_store_opt_in_batch_diagnostics.returns_batch_summary == true
    and .implemented_store_opt_in_batch_diagnostics.returns_bucket_summary == true
    and .implemented_store_opt_in_batch_diagnostics.returns_per_query_hashes == true
    and .implemented_store_opt_in_batch_diagnostics.returns_movement_classes == true
    and .implemented_store_opt_in_batch_diagnostics.raw_queries_included == false
    and .implemented_store_opt_in_batch_diagnostics.raw_keys_included == false
    and .implemented_store_opt_in_batch_diagnostics.content_included == false
    and .implemented_store_opt_in_batch_diagnostics.side_signal_raw_included == false
    and .implemented_store_opt_in_batch_diagnostics.mutates_ab_memory == false
    and .implemented_store_opt_in_batch_diagnostics.registers_embedding_backend == false
    and .implemented_store_opt_in_batch_diagnostics.writes_approval == false
    and .implemented_store_opt_in_batch_diagnostics.redacted_evidence_aggregate_included == false
    and .implemented_store_opt_in_batch_diagnostics.aggregate_evidence_summary_included == false
    and .implemented_store_opt_in_batch_diagnostics.default_memory_search_unchanged == true
    and .implemented_store_opt_in_batch_diagnostics.default_search_order_change_allowed == false
    and .implemented_store_opt_in_batch_diagnostics.default_calls_unchanged == true
    and .implemented_runtime_readiness_packet.cli == "agent-bridge bio-cortex retrieval-opt-in-runtime-readiness-packet"
    and .implemented_runtime_readiness_packet.schema == "agent_bridge.biocortex_retrieval.opt_in_runtime_readiness_packet.v0"
    and .implemented_runtime_readiness_packet.implementation_stage == "controlled_opt_in_runtime_readiness_packet"
    and .implemented_runtime_readiness_packet.authorized_scope == "explicit_opt_in_fts_runtime_influence"
    and .implemented_runtime_readiness_packet.consumes_aggregate_backed_decision_packet_summary == true
    and .implemented_runtime_readiness_packet.consumes_store_trial_summary == true
    and .implemented_runtime_readiness_packet.consumes_batch_diagnostics_summary == true
    and .implemented_runtime_readiness_packet.requires_aggregate_backed_decision_packet == true
    and .implemented_runtime_readiness_packet.requires_downstream_aggregate_preflight == true
    and .implemented_runtime_readiness_packet.distinguishes_empty_live_probe_from_blocked_control_plane == true
    and .implemented_runtime_readiness_packet.can_report_control_plane_ready_without_live_candidates == true
    and .implemented_runtime_readiness_packet.can_grant_new_authorization == false
    and .implemented_runtime_readiness_packet.may_change_default_memory_search_order == false
    and .implemented_runtime_readiness_packet.default_influence_ready == false
    and .implemented_runtime_readiness_packet.runtime_influence_decision_packet_included == false
    and .implemented_runtime_readiness_packet.store_trial_included == false
    and .implemented_runtime_readiness_packet.batch_diagnostics_included == false
    and .implemented_runtime_readiness_packet.raw_queries_included == false
    and .implemented_runtime_readiness_packet.raw_keys_included == false
    and .implemented_runtime_readiness_packet.content_included == false
    and .implemented_runtime_readiness_packet.side_signal_raw_included == false
    and .implemented_runtime_readiness_packet.human_decision_text_included == false
    and .implemented_runtime_readiness_packet.calls_memory_search == false
    and .implemented_runtime_readiness_packet.runs_biocortex == false
    and .implemented_runtime_readiness_packet.registers_embedding_backend == false
    and .implemented_runtime_readiness_packet.changes_memory_search_order == false
    and .implemented_runtime_readiness_packet.writes_approval == false
    and .implemented_runtime_readiness_packet.default_search_order_change_allowed == false
    and .implemented_runtime_readiness_packet.default_calls_unchanged == true
    and .implemented_store_opt_in_controlled_order_fixture.cli == "agent-bridge bio-cortex retrieval-opt-in-controlled-order-fixture"
    and .implemented_store_opt_in_controlled_order_fixture.fixture == "docs/design/fixtures/biocortex-retrieval-opt-in-controlled-order-fixture-2026-06-12.json"
    and .implemented_store_opt_in_controlled_order_fixture.schema == "agent_bridge.biocortex_retrieval.opt_in_controlled_order_fixture_run.v0"
    and .implemented_store_opt_in_controlled_order_fixture.implementation_stage == "store_opt_in_controlled_order_fixture"
    and .implemented_store_opt_in_controlled_order_fixture.authorized_scope == "explicit_opt_in_fts_runtime_influence"
    and .implemented_store_opt_in_controlled_order_fixture.requires_agent_bridge_db_override == true
    and .implemented_store_opt_in_controlled_order_fixture.requires_non_production_store_write_ack == true
    and .implemented_store_opt_in_controlled_order_fixture.writes_only_fixture_memories == true
    and .implemented_store_opt_in_controlled_order_fixture.reuses_store_trial_gate == true
    and .implemented_store_opt_in_controlled_order_fixture.proves_actual_order_movement == true
    and .implemented_store_opt_in_controlled_order_fixture.raw_queries_included == false
    and .implemented_store_opt_in_controlled_order_fixture.raw_keys_included == false
    and .implemented_store_opt_in_controlled_order_fixture.content_included == false
    and .implemented_store_opt_in_controlled_order_fixture.side_signal_raw_included == false
    and .implemented_store_opt_in_controlled_order_fixture.writes_approval == false
    and .implemented_store_opt_in_controlled_order_fixture.registers_embedding_backend == false
    and .implemented_store_opt_in_controlled_order_fixture.default_search_order_change_allowed == false
    and .implemented_store_opt_in_controlled_order_fixture.default_calls_unchanged == true
    and .implemented_store_opt_in_evidence_summary.cli == "agent-bridge bio-cortex retrieval-opt-in-evidence-summary"
    and .implemented_store_opt_in_evidence_summary.schema == "agent_bridge.biocortex_retrieval.opt_in_evidence_summary.v0"
    and .implemented_store_opt_in_evidence_summary.implementation_stage == "post_runtime_evidence_summary"
    and .implemented_store_opt_in_evidence_summary.authorized_scope == "explicit_opt_in_fts_runtime_influence"
    and .implemented_store_opt_in_evidence_summary.consumes_batch_diagnostics == true
    and .implemented_store_opt_in_evidence_summary.consumes_controlled_order_fixture_run == true
    and .implemented_store_opt_in_evidence_summary.batch_diagnostics_included == false
    and .implemented_store_opt_in_evidence_summary.controlled_order_fixture_run_included == false
    and .implemented_store_opt_in_evidence_summary.separates_batch_alignment_from_controlled_movement == true
    and .implemented_store_opt_in_evidence_summary.can_recommend_expand_non_production_corpus == true
    and .implemented_store_opt_in_evidence_summary.can_grant_runtime_influence == false
    and .implemented_store_opt_in_evidence_summary.raw_queries_included == false
    and .implemented_store_opt_in_evidence_summary.raw_keys_included == false
    and .implemented_store_opt_in_evidence_summary.content_included == false
    and .implemented_store_opt_in_evidence_summary.side_signal_raw_included == false
    and .implemented_store_opt_in_evidence_summary.writes_approval == false
    and .implemented_store_opt_in_evidence_summary.calls_memory_search == false
    and .implemented_store_opt_in_evidence_summary.runs_biocortex == false
    and .implemented_store_opt_in_evidence_summary.registers_embedding_backend == false
    and .implemented_store_opt_in_evidence_summary.default_search_order_change_allowed == false
    and .implemented_store_opt_in_evidence_summary.default_calls_unchanged == true
    and .implemented_store_opt_in_expanded_non_production_corpus.fixture == "docs/design/fixtures/biocortex-retrieval-opt-in-expanded-controlled-corpus-2026-06-12.json"
    and .implemented_store_opt_in_expanded_non_production_corpus.reuses_cli == "agent-bridge bio-cortex retrieval-opt-in-controlled-order-fixture"
    and .implemented_store_opt_in_expanded_non_production_corpus.reuses_evidence_summary_cli == "agent-bridge bio-cortex retrieval-opt-in-evidence-summary"
    and .implemented_store_opt_in_expanded_non_production_corpus.schema == "agent_bridge.biocortex_retrieval.opt_in_controlled_order_fixture_run.v0"
    and .implemented_store_opt_in_expanded_non_production_corpus.implementation_stage == "expanded_non_production_adapter_coverage"
    and .implemented_store_opt_in_expanded_non_production_corpus.authorized_scope == "explicit_opt_in_fts_runtime_influence"
    and .implemented_store_opt_in_expanded_non_production_corpus.memory_record_count == 10
    and .implemented_store_opt_in_expanded_non_production_corpus.query_count == 5
    and .implemented_store_opt_in_expanded_non_production_corpus.expected_min_actual_order_changed_count == 0
    and .implemented_store_opt_in_expanded_non_production_corpus.expected_min_experimental_source_count == 5
    and .implemented_store_opt_in_expanded_non_production_corpus.expected_min_side_signal_ok_count == 5
    and .implemented_store_opt_in_expanded_non_production_corpus.proves_multi_bucket_adapter_coverage == true
    and .implemented_store_opt_in_expanded_non_production_corpus.proves_additional_rank_movement == false
    and .implemented_store_opt_in_expanded_non_production_corpus.canonical_rank_movement_fixture == "docs/design/fixtures/biocortex-retrieval-opt-in-controlled-order-fixture-2026-06-12.json"
    and .implemented_store_opt_in_expanded_non_production_corpus.writes_only_fixture_memories == true
    and .implemented_store_opt_in_expanded_non_production_corpus.uses_non_production_store_only == true
    and .implemented_store_opt_in_expanded_non_production_corpus.uses_redacted_evidence_summary == true
    and .implemented_store_opt_in_expanded_non_production_corpus.raw_queries_included == false
    and .implemented_store_opt_in_expanded_non_production_corpus.raw_keys_included == false
    and .implemented_store_opt_in_expanded_non_production_corpus.content_included == false
    and .implemented_store_opt_in_expanded_non_production_corpus.side_signal_raw_included == false
    and .implemented_store_opt_in_expanded_non_production_corpus.writes_approval == false
    and .implemented_store_opt_in_expanded_non_production_corpus.calls_memory_search == true
    and .implemented_store_opt_in_expanded_non_production_corpus.runs_biocortex == true
    and .implemented_store_opt_in_expanded_non_production_corpus.registers_embedding_backend == false
    and .implemented_store_opt_in_expanded_non_production_corpus.can_grant_runtime_influence == false
    and .implemented_store_opt_in_expanded_non_production_corpus.default_search_order_change_allowed == false
    and .implemented_store_opt_in_expanded_non_production_corpus.default_calls_unchanged == true
    and .implemented_store_opt_in_redacted_evidence_aggregate.cli == "agent-bridge bio-cortex retrieval-opt-in-redacted-evidence-aggregate"
    and .implemented_store_opt_in_redacted_evidence_aggregate.schema == "agent_bridge.biocortex_retrieval.opt_in_redacted_evidence_aggregate.v0"
    and .implemented_store_opt_in_redacted_evidence_aggregate.implementation_stage == "post_runtime_redacted_evidence_aggregate"
    and .implemented_store_opt_in_redacted_evidence_aggregate.authorized_scope == "explicit_opt_in_fts_runtime_influence"
    and .implemented_store_opt_in_redacted_evidence_aggregate.consumes_movement_fixture_run == true
    and .implemented_store_opt_in_redacted_evidence_aggregate.consumes_expanded_coverage_fixture_run == true
    and .implemented_store_opt_in_redacted_evidence_aggregate.movement_fixture_run_included == false
    and .implemented_store_opt_in_redacted_evidence_aggregate.coverage_fixture_run_included == false
    and .implemented_store_opt_in_redacted_evidence_aggregate.combines_rank_movement_and_adapter_coverage == true
    and .implemented_store_opt_in_redacted_evidence_aggregate.requires_controlled_rank_movement == true
    and .implemented_store_opt_in_redacted_evidence_aggregate.requires_expanded_coverage_without_additional_movement == true
    and .implemented_store_opt_in_redacted_evidence_aggregate.can_recommend_human_runtime_influence_review_request == true
    and .implemented_store_opt_in_redacted_evidence_aggregate.can_grant_runtime_influence == false
    and .implemented_store_opt_in_redacted_evidence_aggregate.raw_queries_included == false
    and .implemented_store_opt_in_redacted_evidence_aggregate.raw_keys_included == false
    and .implemented_store_opt_in_redacted_evidence_aggregate.content_included == false
    and .implemented_store_opt_in_redacted_evidence_aggregate.side_signal_raw_included == false
    and .implemented_store_opt_in_redacted_evidence_aggregate.writes_approval == false
    and .implemented_store_opt_in_redacted_evidence_aggregate.calls_memory_search == false
    and .implemented_store_opt_in_redacted_evidence_aggregate.runs_biocortex == false
    and .implemented_store_opt_in_redacted_evidence_aggregate.registers_embedding_backend == false
    and .implemented_store_opt_in_redacted_evidence_aggregate.default_search_order_change_allowed == false
    and .implemented_store_opt_in_redacted_evidence_aggregate.default_calls_unchanged == true
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
    and .implemented_runtime_influence_review_request.accepts_redacted_evidence_aggregate_summary == true
    and .implemented_runtime_influence_review_request.requires_aggregate_ready_when_provided == true
    and .implemented_runtime_influence_review_request.post_implementation_review_gate_included == false
    and .implemented_runtime_influence_review_request.redacted_order_artifact_included == false
    and .implemented_runtime_influence_review_request.redacted_evidence_aggregate_included == false
    and .implemented_runtime_influence_review_request.keeps_default_influence_unready == true
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
    and .implemented_runtime_influence_decision_packet.accepts_aggregate_backed_review_request == true
    and .implemented_runtime_influence_decision_packet.requires_aggregate_ready_when_provided == true
    and .implemented_runtime_influence_decision_packet.legacy_review_request_without_aggregate_allowed == true
    and .implemented_runtime_influence_decision_packet.runtime_influence_review_request_included == false
    and .implemented_runtime_influence_decision_packet.runtime_influence_decision_included == false
    and .implemented_runtime_influence_decision_packet.redacted_evidence_aggregate_included == false
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
jq -e '
    .schema == "agent_bridge.biocortex_retrieval.downstream_aio_checkpoint_selection.v0"
    and .status == "downstream_aio_integration_checkpoint_selected"
    and .source_review.source_status == "post_semantic_diverse_review_recorded"
    and .source_review.evidence_accepted == true
    and .source_review.ready_for_downstream_aio_checkpoint_selection == true
    and .selected_checkpoint.id == "semantic_system_bus_lswr_action_result_runtime_evidence_checkpoint"
    and .selected_checkpoint.family == "semantic_system_bus"
    and .selected_checkpoint.surface == "lswr_action_result_runtime_evidence"
    and .selected_checkpoint.first_consumer == "agent_bridge_semantic_system_bus"
    and .selected_checkpoint.direct_aiot_consumption_selected == false
    and .accepted_evidence_summary.fixture_count == 4
    and .accepted_evidence_summary.total_query_count == 8
    and .accepted_evidence_summary.total_runs_biocortex_count == 8
    and .accepted_evidence_summary.total_actual_order_changed_count == 8
    and .accepted_evidence_summary.expected_met == true
    and .checkpoint_contract.checkpoint_must_be_read_only == true
    and .checkpoint_contract.first_handoff_schema == "agent_bridge.biocortex_retrieval.downstream_aio_runtime_evidence_handoff.v0"
    and .checkpoint_contract.may_build_handoff_packet == true
    and .checkpoint_contract.may_compare_against_ssb_runtime_evidence_contract == true
    and .checkpoint_contract.may_enable_default_retrieval == false
    and .checkpoint_contract.may_enable_hybrid_retrieval == false
    and .checkpoint_contract.may_enable_semantic_retrieval == false
    and .checkpoint_contract.may_write_approval == false
    and .checkpoint_contract.may_call_aiot_runtime == false
    and .checkpoint_contract.may_execute_lswr_actions_from_biocortex_evidence == false
    and .ssb_alignment.runtime_backed_evidence == true
    and .ssb_alignment.no_laundering_boundary_required == true
    and .boundary.default_search_order_change_allowed == false
    and .boundary.default_retrieval_influence_authorized == false
    and .boundary.hybrid_retrieval_influence_authorized == false
    and .boundary.semantic_retrieval_influence_authorized == false
    and .boundary.direct_aiot_runtime_use_authorized == false
    and .boundary.raw_queries_included == false
    and .boundary.raw_keys_included == false
    and .boundary.content_included == false
    and .boundary.side_signal_raw_included == false
    and .next_step == "build_downstream_aio_runtime_evidence_handoff_packet"
' "$downstream_aio_checkpoint_selection" >/dev/null
jq -e '
    .schema == "agent_bridge.biocortex_retrieval.downstream_aio_runtime_evidence_handoff.v0"
    and .status == "ready"
    and .read_only == true
    and .downstream_aio_runtime_evidence_handoff == true
    and .implementation_stage == "downstream_aio_runtime_evidence_handoff_packet"
    and .authorization_scope == "explicit_opt_in_fts_runtime_influence"
    and .input_contract.checkpoint_selection_schema == "agent_bridge.biocortex_retrieval.downstream_aio_checkpoint_selection.v0"
    and .input_contract.post_semantic_diverse_review_schema == "agent_bridge.biocortex_retrieval.post_semantic_diverse_review.v0"
    and .input_contract.checkpoint_selection_included == false
    and .input_contract.post_semantic_diverse_review_included == false
    and .input_contract.raw_queries_included == false
    and .input_contract.raw_keys_included == false
    and .input_contract.content_included == false
    and .input_contract.side_signal_raw_included == false
    and .checkpoint_summary.selected_checkpoint == "semantic_system_bus_lswr_action_result_runtime_evidence_checkpoint"
    and .checkpoint_summary.selected_checkpoint_family == "semantic_system_bus"
    and .checkpoint_summary.selected_surface == "lswr_action_result_runtime_evidence"
    and .checkpoint_summary.first_consumer == "agent_bridge_semantic_system_bus"
    and .checkpoint_summary.direct_aiot_consumption_selected == false
    and .checkpoint_summary.boundary_safe == true
    and .source_review_summary.review_status == "post_semantic_diverse_review_recorded"
    and .source_review_summary.evidence_accepted == true
    and .source_review_summary.default_boundary_safe == true
    and .redacted_evidence_summary.fixture_count == 4
    and .redacted_evidence_summary.total_query_count == 8
    and .redacted_evidence_summary.total_runs_biocortex_count == 8
    and .redacted_evidence_summary.total_actual_order_changed_count == 8
    and .redacted_evidence_summary.raw_queries_included == false
    and .redacted_evidence_summary.raw_keys_included == false
    and .redacted_evidence_summary.content_included == false
    and .redacted_evidence_summary.side_signal_raw_included == false
    and .ssb_handoff.target_schema_family == "agent_bridge.semantic_bus.action_result.v0"
    and .ssb_handoff.target_checkpoint == "semantic_system_bus_lswr_action_result_runtime_evidence_checkpoint"
    and .ssb_handoff.recover == "proceed_to_read_only_ssb_review"
    and .ssb_handoff.may_compare_against_ssb_runtime_evidence_contract == true
    and .ssb_handoff.may_emit_ssb_adapter_fixture == true
    and .ssb_handoff.may_execute_lswr_actions == false
    and .ssb_handoff.may_call_aiot_runtime == false
    and .boundary_check.handoff_ready == true
    and (.boundary_check.blockers | length) == 0
    and .boundary_check.this_packet_calls_memory_search == false
    and .boundary_check.this_packet_runs_biocortex == false
    and .boundary_check.this_packet_calls_aiot_runtime == false
    and .boundary_check.this_packet_executes_lswr_actions == false
    and .calls_memory_search == false
    and .runs_biocortex == false
    and .writes_approval == false
    and .changes_memory_search_order == false
    and .default_search_order_change_allowed == false
    and .next_step == "connect_handoff_packet_to_ssb_lswr_action_result_review_fixture"
' "$downstream_aio_runtime_evidence_handoff" >/dev/null
jq -e '
    .schema == "agent_bridge.biocortex_retrieval.ssb_lswr_action_result_review_fixture.v0"
    and .status == "ready"
    and .read_only == true
    and .implementation_stage == "ssb_lswr_action_result_review_fixture"
    and .source_handoff.schema == "agent_bridge.biocortex_retrieval.downstream_aio_runtime_evidence_handoff.v0"
    and .source_handoff.status == "ready"
    and .source_handoff.fixture == "docs/design/fixtures/biocortex-retrieval-downstream-aio-runtime-evidence-handoff-2026-06-15.json"
    and .input_contract.handoff_included == false
    and .input_contract.raw_queries_included == false
    and .input_contract.raw_keys_included == false
    and .input_contract.content_included == false
    and .input_contract.side_signal_raw_included == false
    and .ssb_action_result_contract.schema == "agent_bridge.semantic_bus.action_result.v0"
    and .ssb_action_result_contract.source_schema_expected == "agent_bridge.world_tool.v0"
    and (.ssb_action_result_contract.required_fields | index("recover") != null)
    and (.ssb_action_result_contract.verdict_vocabulary | sort) == ["blocked","not_verified","verified"]
    and (.ssb_action_result_contract.recover_vocabulary | sort) == ["inspect_host_or_visibility_evidence","proceed","replan"]
    and .handoff_alignment.selected_checkpoint == "semantic_system_bus_lswr_action_result_runtime_evidence_checkpoint"
    and .handoff_alignment.target_schema_family == "agent_bridge.semantic_bus.action_result.v0"
    and .handoff_alignment.runtime_backed_evidence == true
    and .handoff_alignment.verification_boundary_required == true
    and .handoff_alignment.no_laundering_boundary_required == true
    and .handoff_alignment.redacted_evidence_ready == true
    and .handoff_alignment.fixture_count == 4
    and .handoff_alignment.total_query_count == 8
    and .handoff_alignment.total_actual_order_changed_count == 8
    and .review_fixture.review_fixture_ready == true
    and .review_fixture.can_compare_handoff_to_ssb_action_result_contract == true
    and .review_fixture.adapter_fixture_required == true
    and .review_fixture.emits_action_result == false
    and .review_fixture.fabricates_lswr_result == false
    and .review_fixture.executes_lswr_actions == false
    and .gap_matrix.bio_cortex_handoff_is_not_lswr_action_result == true
    and .gap_matrix.requires_future_ssb_adapter_fixture == true
    and (.gap_matrix.fields_requiring_adapter_fixture | index("world_tool") != null)
    and (.gap_matrix.fields_requiring_adapter_fixture | index("verification_method") != null)
    and .boundary.calls_memory_search == false
    and .boundary.runs_biocortex == false
    and .boundary.writes_approval == false
    and .boundary.changes_memory_search_order == false
    and .boundary.default_search_order_change_allowed == false
    and .boundary.calls_aiot_runtime == false
    and .boundary.executes_lswr_actions == false
    and .boundary.emits_action_result == false
    and .boundary.raw_queries_included == false
    and .boundary.raw_keys_included == false
    and .boundary.content_included == false
    and .boundary.side_signal_raw_included == false
    and .next_step == "build_read_only_ssb_adapter_fixture_from_handoff"
' "$ssb_lswr_action_result_review_fixture" >/dev/null
jq -e '
    .schema == "agent_bridge.biocortex_retrieval.read_only_ssb_adapter_fixture.v0"
    and .status == "ready"
    and .read_only == true
    and .implementation_stage == "read_only_ssb_adapter_fixture_from_handoff"
    and .source_review_fixture.schema == "agent_bridge.biocortex_retrieval.ssb_lswr_action_result_review_fixture.v0"
    and .source_review_fixture.status == "ready"
    and .source_review_fixture.fixture == "docs/design/fixtures/biocortex-retrieval-ssb-lswr-action-result-review-fixture-2026-06-15.json"
    and .input_contract.review_fixture_included == false
    and .input_contract.raw_queries_included == false
    and .input_contract.raw_keys_included == false
    and .input_contract.content_included == false
    and .input_contract.side_signal_raw_included == false
    and .adapter_fixture.fixture_ready == true
    and .adapter_fixture.fixture_only == true
    and .adapter_fixture.runtime_executed == false
    and .adapter_fixture.executes_lswr_actions == false
    and .adapter_fixture.emits_runtime_action_result == false
    and .adapter_fixture.requires_live_lswr_evidence_before_verified == true
    and .candidate_action_result.schema == "agent_bridge.semantic_bus.action_result.v0"
    and .candidate_action_result.source_schema == "agent_bridge.world_tool.v0"
    and .candidate_action_result.adapter == "biocortex.downstream_aio.read_only_fixture"
    and .candidate_action_result.world_tool == "world_visibility_query"
    and .candidate_action_result.action_type == "world.visibility.query"
    and .candidate_action_result.action_id == "biocortex:ssb-lswr-runtime-evidence:read-only-fixture"
    and .candidate_action_result.request_id == "biocortex-ssb-lswr-action-result-review-20260615"
    and .candidate_action_result.subject_id == "semantic_system_bus_lswr_action_result_runtime_evidence_checkpoint"
    and (.candidate_action_result.event_ids | length) == 1
    and .candidate_action_result.verdict == "not_verified"
    and .candidate_action_result.reason == "fixture_only_no_lswr_runtime_execution"
    and .candidate_action_result.verified_to == null
    and .candidate_action_result.verification_method == "read_only_contract_projection"
    and .candidate_action_result.recover == "inspect_host_or_visibility_evidence"
    and .candidate_action_result.raw_available == false
    and .action_result_boundary.fixture_only == true
    and .action_result_boundary.must_not_be_ingested_as_runtime_evidence == true
    and .action_result_boundary.must_not_be_used_for_training == true
    and .action_result_boundary.requires_future_live_runtime_evidence == true
    and .handoff_evidence_projection.fixture_count == 4
    and .handoff_evidence_projection.total_query_count == 8
    and .handoff_evidence_projection.total_actual_order_changed_count == 8
    and .boundary.calls_memory_search == false
    and .boundary.runs_biocortex == false
    and .boundary.writes_approval == false
    and .boundary.changes_memory_search_order == false
    and .boundary.default_search_order_change_allowed == false
    and .boundary.calls_aiot_runtime == false
    and .boundary.executes_lswr_actions == false
    and .boundary.emits_runtime_action_result == false
    and .boundary.raw_queries_included == false
    and .boundary.raw_keys_included == false
    and .boundary.content_included == false
    and .boundary.side_signal_raw_included == false
    and .next_step == "completed_by_live_lswr_action_result_runtime_evidence_observation"
    and .next_step_completed == true
' "$read_only_ssb_adapter_fixture" >/dev/null
jq -e '
    .schema == "agent_bridge.biocortex_retrieval.live_lswr_action_result_runtime_evidence.v0"
    and .status == "observed_not_verified"
    and .read_only == true
    and .implementation_stage == "live_lswr_action_result_runtime_evidence_collection"
    and .source_adapter_fixture.schema == "agent_bridge.biocortex_retrieval.read_only_ssb_adapter_fixture.v0"
    and .source_adapter_fixture.status == "ready"
    and .source_adapter_fixture.fixture == "docs/design/fixtures/biocortex-retrieval-read-only-ssb-adapter-fixture-2026-06-15.json"
    and .source_adapter_fixture.included == false
    and .mcp_probe.tool_profile == "all"
    and .mcp_probe.tools_count == 240
    and .mcp_probe.tool_listed == true
    and .mcp_probe.tool == "world_visibility_query"
    and .mcp_probe.call_executed == true
    and .mcp_probe.include_raw == false
    and .live_observation.schema == "agent_bridge.world_tool.v0"
    and .live_observation.ok == false
    and .live_observation.verified == false
    and .live_observation.reason == "world_host_unreachable"
    and .live_observation.endpoint.host == "127.0.0.1"
    and .live_observation.endpoint.port == 37691
    and .live_observation.endpoint.timeout_ms == 750
    and .live_observation.request.request_id == "biocortex-live-lswr-evidence-20260615"
    and .live_observation.request.world_tool == "world_visibility_query"
    and (.live_observation.request.entities | length) == 1
    and .live_observation.verify.method == "live_viewport_pixel_coverage"
    and .live_observation.verify.verified_to == null
    and .live_observation.verify.host_reason == "world_host_unreachable"
    and .live_observation.host_response_field_present == false
    and .live_observation.host_response_is_null == false
    and .live_observation.host_response_payload_present == false
    and .action_result.schema == "agent_bridge.semantic_bus.action_result.v0"
    and .action_result.source_schema == "agent_bridge.world_tool.v0"
    and .action_result.adapter == "lswr.onsen"
    and .action_result.world_tool == "world_visibility_query"
    and .action_result.action_type == "world.visibility.query"
    and .action_result.action_id == "lswr:world_visibility_query:biocortex-live-lswr-evidence-20260615:result"
    and .action_result.request_id == "biocortex-live-lswr-evidence-20260615"
    and .action_result.subject_id == "lswr:onsen:world"
    and (.action_result.event_ids | length) == 1
    and .action_result.verdict == "not_verified"
    and .action_result.reason == "world_host_unreachable"
    and .action_result.verified_to == null
    and .action_result.verification_method == "live_viewport_pixel_coverage"
    and .action_result.recover == "inspect_host_or_visibility_evidence"
    and .action_result.raw_available == false
    and .evidence_boundary.live_mcp_call_attempted == true
    and .evidence_boundary.runtime_host_reached == false
    and .evidence_boundary.verified_runtime_action_result_collected == false
    and .evidence_boundary.not_verified_runtime_action_result_collected == true
    and .evidence_boundary.must_not_be_ingested_as_verified_runtime_evidence == true
    and .evidence_boundary.must_not_be_used_for_training == true
    and .evidence_boundary.requires_live_host_before_verified == true
    and .boundary.calls_memory_search == false
    and .boundary.runs_biocortex == false
    and .boundary.writes_approval == false
    and .boundary.changes_memory_search_order == false
    and .boundary.default_search_order_change_allowed == false
    and .boundary.calls_aiot_runtime == false
    and .boundary.executes_lswr_actions == false
    and .boundary.emits_durable_runtime_action_result == false
    and .boundary.mutates_default_agent_bridge_db == false
    and .boundary.host_response_included == false
    and .boundary.raw_queries_included == false
    and .boundary.raw_keys_included == false
    and .boundary.content_included == false
    and .boundary.side_signal_raw_included == false
    and .boundary.human_decision_text_included == false
    and .next_step == "completed_by_loopback_lswr_action_result_verified_fixture_host_probe"
    and .next_step_completed == true
' "$live_lswr_action_result_runtime_evidence" >/dev/null
jq -e '
    .schema == "agent_bridge.biocortex_retrieval.loopback_lswr_action_result_verified_probe.v0"
    and .status == "verified_fixture_host_observed"
    and .read_only == true
    and .implementation_stage == "loopback_lswr_action_result_verified_probe"
    and .source_live_observation_fixture.schema == "agent_bridge.biocortex_retrieval.live_lswr_action_result_runtime_evidence.v0"
    and .source_live_observation_fixture.status == "observed_not_verified"
    and .source_live_observation_fixture.fixture == "docs/design/fixtures/biocortex-retrieval-live-lswr-action-result-runtime-evidence-2026-06-15.json"
    and .mcp_probe.tool_profile == "all"
    and .mcp_probe.tools_count == 240
    and .mcp_probe.tool_listed == true
    and .mcp_probe.tool == "world_visibility_query"
    and .mcp_probe.call_executed == true
    and .mcp_probe.include_raw == true
    and .mcp_probe.request_id == "biocortex-loopback-lswr-evidence-20260615"
    and .mcp_probe.endpoint.host == "127.0.0.1"
    and .mcp_probe.endpoint.port_is_ephemeral_single_run == true
    and .loopback_host.kind == "one_shot_fixture_host"
    and .loopback_host.served_single_request == true
    and .loopback_host.real_onsen_runtime == false
    and .loopback_host.human_visible_viewport == false
    and .loopback_host.fixture_host_not_training_eligible == true
    and .live_observation.schema == "agent_bridge.world_tool.v0"
    and .live_observation.ok == true
    and .live_observation.verified == true
    and .live_observation.reason == null
    and .live_observation.request.request_id == "biocortex-loopback-lswr-evidence-20260615"
    and .live_observation.request.world_tool == "world_visibility_query"
    and (.live_observation.request.entities | length) == 1
    and .live_observation.verify.method == "live_viewport_pixel_coverage"
    and .live_observation.verify.verified_to == "onsen_live_root_viewport"
    and .live_observation.host_response_field_present == true
    and .live_observation.host_response_payload_present == true
    and .action_result.schema == "agent_bridge.semantic_bus.action_result.v0"
    and .action_result.source_schema == "agent_bridge.world_tool.v0"
    and .action_result.adapter == "lswr.onsen"
    and .action_result.world_tool == "world_visibility_query"
    and .action_result.action_type == "world.visibility.query"
    and .action_result.request_id == "biocortex-loopback-lswr-evidence-20260615"
    and .action_result.verdict == "verified"
    and .action_result.reason == null
    and .action_result.verified_to == "onsen_live_root_viewport"
    and .action_result.recover == "proceed"
    and .action_result.raw_available == true
    and .evidence_boundary.loopback_host_reached == true
    and .evidence_boundary.verified_fixture_action_result_collected == true
    and .evidence_boundary.verified_real_onsen_action_result_collected == false
    and .evidence_boundary.real_onsen_runtime_verified == false
    and .evidence_boundary.human_visible_viewport_verified == false
    and .evidence_boundary.must_not_be_ingested_as_real_onsen_runtime_evidence == true
    and .evidence_boundary.must_not_be_used_for_training == true
    and .boundary.calls_memory_search == false
    and .boundary.runs_biocortex == false
    and .boundary.writes_approval == false
    and .boundary.changes_memory_search_order == false
    and .boundary.default_search_order_change_allowed == false
    and .boundary.calls_aiot_runtime == false
    and .boundary.executes_lswr_actions == false
    and .boundary.emits_durable_runtime_action_result == false
    and .boundary.mutates_default_agent_bridge_db == false
    and .boundary.host_response_included == true
    and .boundary.raw_queries_included == false
    and .boundary.raw_keys_included == false
    and .boundary.content_included == false
    and .boundary.side_signal_raw_included == false
    and .boundary.human_decision_text_included == false
    and .next_step == "completed_by_loopback_lswr_host_attach_preflight"
    and .next_step_completed == true
' "$loopback_lswr_action_result_verified_probe" >/dev/null
jq -e '
    .schema == "agent_bridge.biocortex_retrieval.loopback_lswr_host_attach_preflight.v0"
    and .status == "blocked_missing_loopback_host_checkout"
    and .read_only == true
    and .implementation_stage == "loopback_lswr_host_attach_preflight"
    and .source_loopback_fixture_probe.schema == "agent_bridge.biocortex_retrieval.loopback_lswr_action_result_verified_probe.v0"
    and .source_loopback_fixture_probe.status == "verified_fixture_host_observed"
    and .source_loopback_fixture_probe.fixture == "docs/design/fixtures/biocortex-retrieval-loopback-lswr-action-result-verified-probe-2026-06-15.json"
    and .target_endpoint.host == "127.0.0.1"
    and .target_endpoint.port == 37691
    and .target_endpoint.protocol == "newline_json_tcp"
    and .observed_listener.port_37691_listening == false
    and .observed_listener.connect_attempted == true
    and .observed_listener.connect_succeeded == false
    and .local_checkout_scan.onsen_step_b_checkout_present == false
    and .local_checkout_scan.documented_macos_checkout_present_on_this_host == false
    and .local_checkout_scan.candidate_linux_checkout_present == false
    and .agent_bridge_client_surface.world_visibility_query_present == true
    and .agent_bridge_client_surface.mcp_profile_required == "all"
    and .agent_bridge_client_surface.client_side_ready == true
    and .prototype_assessment.present == true
    and .prototype_assessment.web_prototype_is_loopback_lsswr_host == false
    and .result.can_rerun_live_probe == true
    and .result.can_collect_verified_runtime_action_result_now == false
    and .result.blocked_by_missing_real_onsen_host == true
    and .result.fixture_host_probe_completed == true
    and .result.real_onsen_runtime_verified == false
    and .result.human_visible_viewport_verified == false
    and .boundary.calls_memory_search == false
    and .boundary.runs_biocortex == false
    and .boundary.writes_approval == false
    and .boundary.changes_memory_search_order == false
    and .boundary.default_search_order_change_allowed == false
    and .boundary.calls_aiot_runtime == false
    and .boundary.executes_lswr_actions == false
    and .boundary.emits_durable_runtime_action_result == false
    and .boundary.mutates_default_agent_bridge_db == false
    and .boundary.host_response_included == false
    and .boundary.raw_queries_included == false
    and .boundary.raw_keys_included == false
    and .boundary.content_included == false
    and .boundary.side_signal_raw_included == false
    and .boundary.human_decision_text_included == false
    and .next_step == "completed_by_onsen_step_b_source_resolution"
' "$loopback_lswr_host_attach_preflight" >/dev/null
jq -e '
    .schema == "agent_bridge.biocortex_retrieval.onsen_step_b_source_resolution.v0"
    and .status == "blocked_missing_onsen_step_b_source"
    and .read_only == true
    and .implementation_stage == "onsen_step_b_source_resolution"
    and .source_preflight.schema == "agent_bridge.biocortex_retrieval.loopback_lswr_host_attach_preflight.v0"
    and .source_preflight.status == "blocked_missing_loopback_host_checkout"
    and .source_preflight.fixture == "docs/design/fixtures/biocortex-retrieval-loopback-lswr-host-attach-preflight-2026-06-15.json"
    and .accepted_onsen_step_b_runtime.documented_worktree == "/Users/pallasting/Projects/onsen-hd-live-semantic-phase0"
    and .accepted_onsen_step_b_runtime.documented_branch == "codex/live-semantic-phase0-t1"
    and .accepted_onsen_step_b_runtime.documented_head == "10d58ee"
    and (.accepted_onsen_step_b_runtime.documented_commits | length) == 3
    and .accepted_onsen_step_b_runtime.expected_endpoint == "127.0.0.1:37691"
    and .accepted_onsen_step_b_runtime.expected_protocol == "newline_json_tcp"
    and (.accepted_onsen_step_b_runtime.expected_tools | sort) == ["world_patch","world_query","world_visibility_query"]
    and .local_resolution.linux_candidate_worktree_present == false
    and .local_resolution.documented_macos_worktree_present_on_this_host == false
    and .local_resolution.port_37691_listening == false
    and .local_resolution.prototype_present == true
    and .local_resolution.prototype_is_required_step_b_host == false
    and .remote_resolution.attempted == true
    and (.remote_resolution.git_ssh_candidates | length) == 3
    and (.remote_resolution.git_ssh_candidates[] | select(.url == "git@github.com:pallasting/Onsen-HD.git") | .result) == "repository_accessible_but_not_accepted_step_b_source"
    and .remote_resolution.additional_candidate_inspection.candidate == "git@github.com:pallasting/Onsen-HD.git"
    and .remote_resolution.additional_candidate_inspection.local_checkout == "/Data/CascadeProjects/Onsen-HD"
    and .remote_resolution.additional_candidate_inspection.head == "79993b494cf6e41fbacb33f2ab2c6ea9ea544771"
    and .remote_resolution.additional_candidate_inspection.accepted_branch_found == false
    and .remote_resolution.additional_candidate_inspection.accepted_head_found == false
    and .remote_resolution.additional_candidate_inspection.world_tool_host_contract_found == false
    and .remote_resolution.additional_candidate_inspection.expected_port_found == false
    and .remote_resolution.additional_candidate_inspection.result == "not_accepted_step_b_host_source"
    and .remote_resolution.usable_remote_found == false
    and .result.agent_bridge_client_side_ready == true
    and .result.real_onsen_step_b_host_source_found == false
    and .result.can_launch_real_onsen_step_b_host_now == false
    and .result.can_collect_verified_runtime_action_result_now == false
    and .result.blocked_by == "missing_checkout_or_accessible_repository_url"
    and .result.required_input == "provide_or_sync_onsen_step_b_checkout_or_repository_url"
    and .recovery_probe.script == "scripts/probe-onsen-step-b-host-source.sh"
    and .recovery_probe.schema == "agent_bridge.biocortex_retrieval.onsen_step_b_host_source_probe.v0"
    and .recovery_probe.ready == true
    and .recovery_probe.read_only == true
    and .recovery_probe.supports_no_remote_mode == true
    and .recovery_probe.supports_strict_mode == true
    and .recovery_probe.does_not_clone == true
    and .recovery_probe.does_not_start_host == true
    and .recovery_probe.requires_checkout_branch_or_head_match == true
    and .recovery_probe.distinguishes_reachable_nonmatching_remote == true
    and .recovery_probe.nonmatching_git_checkout_is_not_source_found == true
    and .host_launch_plan.script == "scripts/plan-onsen-step-b-host-launch.sh"
    and .host_launch_plan.schema == "agent_bridge.biocortex_retrieval.onsen_step_b_host_launch_plan.v0"
    and .host_launch_plan.doc == "docs/design/BIOCORTEX_RETRIEVAL_ONSEN_STEP_B_HOST_LAUNCH_PLAN_2026_06_15.md"
    and .host_launch_plan.fixture == "docs/design/fixtures/biocortex-retrieval-onsen-step-b-host-launch-plan-2026-06-15.json"
    and .host_launch_plan.status == "blocked_missing_onsen_step_b_source"
    and .host_launch_plan.ready == true
    and .host_launch_plan.read_only == true
    and .host_launch_plan.uses_source_probe == true
    and .host_launch_plan.does_not_clone == true
    and .host_launch_plan.does_not_start_host == true
    and .host_launch_plan.operator_launch_required == true
    and .host_launch_plan.agent_bridge_client_only == true
    and .host_launch_plan.fixture_recorded == true
    and .boundary.calls_memory_search == false
    and .boundary.runs_biocortex == false
    and .boundary.writes_approval == false
    and .boundary.changes_memory_search_order == false
    and .boundary.default_search_order_change_allowed == false
    and .boundary.calls_aiot_runtime == false
    and .boundary.executes_lswr_actions == false
    and .boundary.emits_durable_runtime_action_result == false
    and .boundary.mutates_default_agent_bridge_db == false
    and .boundary.host_response_included == false
    and .boundary.raw_queries_included == false
    and .boundary.raw_keys_included == false
    and .boundary.content_included == false
    and .boundary.side_signal_raw_included == false
    and .boundary.human_decision_text_included == false
    and .next_step == "provide_or_sync_onsen_step_b_checkout_or_repository_url_then_launch_dev_host"
' "$onsen_step_b_source_resolution" >/dev/null

jq -e '
    .schema == "agent_bridge.biocortex_retrieval.onsen_step_b_host_launch_plan.v0"
    and .status == "blocked_missing_onsen_step_b_source"
    and .read_only == true
    and .source_probe.script == "scripts/probe-onsen-step-b-host-source.sh"
    and .source_probe.source_found == false
    and .source_probe.ready_for_live_probe == false
    and .source_probe.requires_checkout_branch_or_head_match == true
    and .source_probe.rejects_nonmatching_git_checkout == true
    and .accepted_source.checkout == "/Data/CascadeProjects/onsen-hd-live-semantic-phase0"
    and .accepted_source.documented_macos_worktree == "/Users/pallasting/Projects/onsen-hd-live-semantic-phase0"
    and .accepted_source.branch == "codex/live-semantic-phase0-t1"
    and .accepted_source.head == "10d58ee"
    and .accepted_source.present_on_this_host == false
    and .expected_host.host == "127.0.0.1"
    and .expected_host.port == 37691
    and .expected_host.protocol == "newline_json_tcp"
    and .expected_host.required_world_tool == "world_visibility_query"
    and .expected_host.listening == false
    and .launch_plan.action == "none"
    and .launch_plan.operator_action_required == false
    and .launch_plan.agent_bridge_starts_host == false
    and .launch_plan.dev_or_probe_flag_required == true
    and .launch_plan.onsen_runtime_must_own_launch == true
    and .launch_plan.source_must_be_available_before_launch == true
    and .boundary.starts_host == false
    and .boundary.clones_repository == false
    and .boundary.executes_lswr_actions == false
    and .boundary.calls_memory_search == false
    and .boundary.runs_biocortex == false
    and .boundary.writes_approval == false
    and .boundary.changes_memory_search_order == false
    and .boundary.default_search_order_change_allowed == false
    and .boundary.calls_aiot_runtime == false
    and .boundary.emits_durable_runtime_action_result == false
    and .boundary.mutates_default_agent_bridge_db == false
    and .next_step == "provide_or_sync_onsen_step_b_checkout_or_repository_url"
' "$onsen_step_b_host_launch_plan_fixture" >/dev/null

tmp_onsen_step_b_host_source_probe="$tmpdir/onsen-step-b-host-source-probe.json"
"$onsen_step_b_host_source_probe_script" \
    --no-remote \
    --checkout "$tmpdir/missing-onsen-step-b-checkout" \
    --out "$tmp_onsen_step_b_host_source_probe"
jq -e '
    .schema == "agent_bridge.biocortex_retrieval.onsen_step_b_host_source_probe.v0"
    and .status == "blocked_missing_onsen_step_b_source"
    and .read_only == true
    and .expected.branch == "codex/live-semantic-phase0-t1"
    and .expected.head == "10d58ee"
    and .expected.endpoint.host == "127.0.0.1"
    and .expected.endpoint.port == 37691
    and .expected.endpoint.protocol == "newline_json_tcp"
    and .expected.world_tool == "world_visibility_query"
    and .checkout.present == false
    and .checkout.is_git == false
    and .remote_resolution.attempted == false
    and .remote_resolution.usable_remote_found == false
    and (.remote_resolution.candidates | length) == 0
    and .result.source_found == false
    and .result.ready_for_live_probe == false
    and .result.blocked_by == "missing_checkout_or_accessible_repository_url"
    and .result.next_step == "provide_or_sync_onsen_step_b_checkout_or_repository_url"
    and .boundary.clones_repository == false
    and .boundary.starts_host == false
    and .boundary.calls_memory_search == false
    and .boundary.runs_biocortex == false
    and .boundary.writes_approval == false
    and .boundary.changes_memory_search_order == false
    and .boundary.default_search_order_change_allowed == false
    and .boundary.calls_aiot_runtime == false
    and .boundary.executes_lswr_actions == false
    and .boundary.emits_durable_runtime_action_result == false
    and .boundary.mutates_default_agent_bridge_db == false
' "$tmp_onsen_step_b_host_source_probe" >/dev/null

tmp_onsen_step_b_host_launch_plan="$tmpdir/onsen-step-b-host-launch-plan.json"
"$onsen_step_b_host_launch_plan_script" \
    --no-remote \
    --checkout "$tmpdir/missing-onsen-step-b-checkout" \
    --out "$tmp_onsen_step_b_host_launch_plan"
jq -e '
    .schema == "agent_bridge.biocortex_retrieval.onsen_step_b_host_launch_plan.v0"
    and .status == "blocked_missing_onsen_step_b_source"
    and .read_only == true
    and .source_probe.script == "scripts/probe-onsen-step-b-host-source.sh"
    and .source_probe.source_found == false
    and .source_probe.ready_for_live_probe == false
    and .accepted_source.branch == "codex/live-semantic-phase0-t1"
    and .accepted_source.head == "10d58ee"
    and .expected_host.host == "127.0.0.1"
    and .expected_host.port == 37691
    and .expected_host.protocol == "newline_json_tcp"
    and .expected_host.required_world_tool == "world_visibility_query"
    and .launch_plan.action == "none"
    and .launch_plan.operator_action_required == false
    and .launch_plan.agent_bridge_starts_host == false
    and .launch_plan.dev_or_probe_flag_required == true
    and .launch_plan.onsen_runtime_must_own_launch == true
    and .boundary.starts_host == false
    and .boundary.clones_repository == false
    and .boundary.executes_lswr_actions == false
    and .boundary.calls_memory_search == false
    and .boundary.runs_biocortex == false
    and .boundary.writes_approval == false
    and .boundary.changes_memory_search_order == false
    and .boundary.default_search_order_change_allowed == false
    and .boundary.calls_aiot_runtime == false
    and .boundary.emits_durable_runtime_action_result == false
    and .boundary.mutates_default_agent_bridge_db == false
    and .next_step == "provide_or_sync_onsen_step_b_checkout_or_repository_url"
' "$tmp_onsen_step_b_host_launch_plan" >/dev/null
jq -e --slurpfile fixture "$onsen_step_b_host_launch_plan_fixture" '
    .schema == $fixture[0].schema
    and .status == $fixture[0].status
    and .read_only == $fixture[0].read_only
    and .source_probe.source_found == $fixture[0].source_probe.source_found
    and .source_probe.ready_for_live_probe == $fixture[0].source_probe.ready_for_live_probe
    and .accepted_source.branch == $fixture[0].accepted_source.branch
    and .accepted_source.head == $fixture[0].accepted_source.head
    and .expected_host.host == $fixture[0].expected_host.host
    and .expected_host.port == $fixture[0].expected_host.port
    and .expected_host.protocol == $fixture[0].expected_host.protocol
    and .expected_host.required_world_tool == $fixture[0].expected_host.required_world_tool
    and .launch_plan.action == $fixture[0].launch_plan.action
    and .launch_plan.agent_bridge_starts_host == $fixture[0].launch_plan.agent_bridge_starts_host
    and .boundary.starts_host == $fixture[0].boundary.starts_host
    and .boundary.clones_repository == $fixture[0].boundary.clones_repository
    and .boundary.executes_lswr_actions == $fixture[0].boundary.executes_lswr_actions
    and .next_step == $fixture[0].next_step
' "$tmp_onsen_step_b_host_launch_plan" >/dev/null

tmp_mismatched_onsen_checkout="$tmpdir/mismatched-onsen-step-b-checkout"
mkdir -p "$tmp_mismatched_onsen_checkout"
git -C "$tmp_mismatched_onsen_checkout" init -q
git -C "$tmp_mismatched_onsen_checkout" config user.email verify@example.invalid
git -C "$tmp_mismatched_onsen_checkout" config user.name "verify bundle"
git -C "$tmp_mismatched_onsen_checkout" checkout -q -B unrelated-main
git -C "$tmp_mismatched_onsen_checkout" commit --allow-empty -q -m "verify mismatched onsen checkout"
tmp_mismatched_onsen_probe="$tmpdir/mismatched-onsen-step-b-host-source-probe.json"
"$onsen_step_b_host_source_probe_script" \
    --no-remote \
    --checkout "$tmp_mismatched_onsen_checkout" \
    --out "$tmp_mismatched_onsen_probe"
jq -e '
    .status == "blocked_missing_onsen_step_b_source"
    and .checkout.present == true
    and .checkout.is_git == true
    and .checkout.branch == "unrelated-main"
    and .checkout.branch_matches_expected == false
    and .checkout.head_matches_expected == false
    and .remote_resolution.attempted == false
    and .remote_resolution.usable_remote_found == false
    and .result.source_found == false
    and .result.ready_for_live_probe == false
    and .result.blocked_by == "missing_checkout_or_accessible_repository_url"
    and .result.next_step == "provide_or_sync_onsen_step_b_checkout_or_repository_url"
' "$tmp_mismatched_onsen_probe" >/dev/null

tmp_mismatched_onsen_launch_plan="$tmpdir/mismatched-onsen-step-b-host-launch-plan.json"
"$onsen_step_b_host_launch_plan_script" \
    --probe-json "$tmp_mismatched_onsen_probe" \
    --out "$tmp_mismatched_onsen_launch_plan"
jq -e '
    .schema == "agent_bridge.biocortex_retrieval.onsen_step_b_host_launch_plan.v0"
    and .status == "blocked_missing_onsen_step_b_source"
    and .source_probe.source_found == false
    and .source_probe.ready_for_live_probe == false
    and .launch_plan.action == "none"
    and .launch_plan.agent_bridge_starts_host == false
    and .boundary.starts_host == false
    and .boundary.executes_lswr_actions == false
    and .next_step == "provide_or_sync_onsen_step_b_checkout_or_repository_url"
' "$tmp_mismatched_onsen_launch_plan" >/dev/null

tmp_downstream_aio_runtime_evidence_handoff="$tmpdir/downstream-aio-runtime-evidence-handoff.json"
run cargo run -p ab-bridge --no-default-features -- \
    bio-cortex retrieval-downstream-aio-runtime-evidence-handoff \
    --checkpoint-selection-json "$downstream_aio_checkpoint_selection" \
    --post-semantic-diverse-review-json docs/design/fixtures/biocortex-retrieval-post-semantic-diverse-review-2026-06-15.json \
    --reviewer verify-bundle \
    --commit verify-handoff-commit \
    --forum-post-id verify-forum-post \
    --memory-key verify-memory-key \
    --json > "$tmp_downstream_aio_runtime_evidence_handoff"
jq -e '
    .schema == "agent_bridge.biocortex_retrieval.downstream_aio_runtime_evidence_handoff.v0"
    and .status == "ready"
    and .boundary_check.handoff_ready == true
    and (.boundary_check.blockers | length) == 0
    and .ssb_handoff.target_checkpoint == "semantic_system_bus_lswr_action_result_runtime_evidence_checkpoint"
    and .ssb_handoff.may_compare_against_ssb_runtime_evidence_contract == true
    and .ssb_handoff.may_execute_lswr_actions == false
    and .ssb_handoff.may_call_aiot_runtime == false
    and .calls_memory_search == false
    and .runs_biocortex == false
    and .writes_approval == false
    and .changes_memory_search_order == false
    and .default_search_order_change_allowed == false
    and .raw_queries_included == false
    and .raw_keys_included == false
    and .content_included == false
    and .side_signal_raw_included == false
' "$tmp_downstream_aio_runtime_evidence_handoff" >/dev/null

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
run bash scripts/prepare-biocortex-retrieval-approval-review.sh \
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
run cargo test -p ab-bridge --lib --no-default-features \
    biocortex_retrieval_opt_in_runtime_readiness_packet_ -- --nocapture
run cargo test -p ab-bridge --lib --no-default-features \
    opt_in_runtime_transition_gate_ -- --nocapture
run cargo test -p ab-bridge --lib --no-default-features \
    biocortex_retrieval_opt_in_runtime_transition_gate_ -- --nocapture
run cargo test -p ab-bridge --lib --no-default-features \
    opt_in_gated_store_trial_ -- --nocapture
run "$repo_root/scripts/verify-biocortex-runtime-readiness-mcp.sh"

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
run bash scripts/prove-biocortex-retrieval-runtime-boundary.sh \
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
run bash scripts/prepare-biocortex-retrieval-opt-in-authorization-request.sh \
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
    and .opt_in_plan.status == "loopback_lswr_host_attach_preflight_blocked"
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
    and .opt_in_plan.runtime_readiness_packet_implemented == true
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
    and .opt_in_plan.implemented_store_opt_in_runtime_adapter_connection.cli == "agent-bridge bio-cortex retrieval-opt-in-store-trial"
    and .opt_in_plan.implemented_store_opt_in_runtime_adapter_connection.mcp_tool == "biocortex_retrieval_opt_in_store_trial"
    and .opt_in_plan.implemented_store_opt_in_runtime_adapter_connection.schema == "agent_bridge.biocortex_retrieval.opt_in_store_trial.v0"
    and .opt_in_plan.implemented_store_opt_in_runtime_adapter_connection.implementation_stage == "store_opt_in_runtime_adapter_connection"
    and .opt_in_plan.implemented_store_opt_in_runtime_adapter_connection.authorized_scope == "explicit_opt_in_fts_runtime_influence"
    and .opt_in_plan.implemented_store_opt_in_runtime_adapter_connection.authorized_mode == "fts"
    and .opt_in_plan.implemented_store_opt_in_runtime_adapter_connection.requires_runtime_influence_decision_packet == true
    and .opt_in_plan.implemented_store_opt_in_runtime_adapter_connection.requires_decision_packet_runtime_adapter_approved == true
    and .opt_in_plan.implemented_store_opt_in_runtime_adapter_connection.requires_decision_packet_ordering_connection_authorized == true
    and .opt_in_plan.implemented_store_opt_in_runtime_adapter_connection.accepts_aggregate_backed_decision_packet == true
    and .opt_in_plan.implemented_store_opt_in_runtime_adapter_connection.requires_aggregate_ready_when_provided == true
    and .opt_in_plan.implemented_store_opt_in_runtime_adapter_connection.legacy_decision_packet_without_aggregate_allowed == true
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
    and .opt_in_plan.implemented_store_opt_in_runtime_adapter_connection.redacted_evidence_aggregate_included == false
    and .opt_in_plan.implemented_store_opt_in_runtime_adapter_connection.aggregate_evidence_summary_included == false
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
    and .opt_in_plan.implemented_store_opt_in_batch_diagnostics.cli == "agent-bridge bio-cortex retrieval-opt-in-batch-diagnostics"
    and .opt_in_plan.implemented_store_opt_in_batch_diagnostics.cli_accepts_query_cases_json == true
    and .opt_in_plan.implemented_store_opt_in_batch_diagnostics.query_cases_fixture == "docs/design/fixtures/biocortex-retrieval-opt-in-batch-diagnostic-queries-2026-06-12.json"
    and .opt_in_plan.implemented_store_opt_in_batch_diagnostics.mcp_tool == "biocortex_retrieval_opt_in_batch_diagnostics"
    and .opt_in_plan.implemented_store_opt_in_batch_diagnostics.schema == "agent_bridge.biocortex_retrieval.opt_in_batch_diagnostics.v0"
    and .opt_in_plan.implemented_store_opt_in_batch_diagnostics.implementation_stage == "store_opt_in_batch_diagnostics"
    and .opt_in_plan.implemented_store_opt_in_batch_diagnostics.authorized_scope == "explicit_opt_in_fts_runtime_influence"
    and .opt_in_plan.implemented_store_opt_in_batch_diagnostics.reuses_store_trial_gate == true
    and .opt_in_plan.implemented_store_opt_in_batch_diagnostics.accepts_aggregate_backed_decision_packet == true
    and .opt_in_plan.implemented_store_opt_in_batch_diagnostics.requires_aggregate_ready_when_provided == true
    and .opt_in_plan.implemented_store_opt_in_batch_diagnostics.legacy_decision_packet_without_aggregate_allowed == true
    and .opt_in_plan.implemented_store_opt_in_batch_diagnostics.calls_memory_search == true
    and .opt_in_plan.implemented_store_opt_in_batch_diagnostics.runs_biocortex_only_when_store_trial_allows == true
    and .opt_in_plan.implemented_store_opt_in_batch_diagnostics.calls_store_opt_in_wrapper == true
    and .opt_in_plan.implemented_store_opt_in_batch_diagnostics.returns_batch_summary == true
    and .opt_in_plan.implemented_store_opt_in_batch_diagnostics.returns_bucket_summary == true
    and .opt_in_plan.implemented_store_opt_in_batch_diagnostics.returns_per_query_hashes == true
    and .opt_in_plan.implemented_store_opt_in_batch_diagnostics.returns_movement_classes == true
    and .opt_in_plan.implemented_store_opt_in_batch_diagnostics.raw_queries_included == false
    and .opt_in_plan.implemented_store_opt_in_batch_diagnostics.raw_keys_included == false
    and .opt_in_plan.implemented_store_opt_in_batch_diagnostics.content_included == false
    and .opt_in_plan.implemented_store_opt_in_batch_diagnostics.side_signal_raw_included == false
    and .opt_in_plan.implemented_store_opt_in_batch_diagnostics.mutates_ab_memory == false
    and .opt_in_plan.implemented_store_opt_in_batch_diagnostics.registers_embedding_backend == false
    and .opt_in_plan.implemented_store_opt_in_batch_diagnostics.writes_approval == false
    and .opt_in_plan.implemented_store_opt_in_batch_diagnostics.redacted_evidence_aggregate_included == false
    and .opt_in_plan.implemented_store_opt_in_batch_diagnostics.aggregate_evidence_summary_included == false
    and .opt_in_plan.implemented_store_opt_in_batch_diagnostics.default_memory_search_unchanged == true
    and .opt_in_plan.implemented_store_opt_in_batch_diagnostics.default_search_order_change_allowed == false
    and .opt_in_plan.implemented_store_opt_in_batch_diagnostics.default_calls_unchanged == true
    and .opt_in_plan.implemented_runtime_readiness_packet.cli == "agent-bridge bio-cortex retrieval-opt-in-runtime-readiness-packet"
    and .opt_in_plan.implemented_runtime_readiness_packet.schema == "agent_bridge.biocortex_retrieval.opt_in_runtime_readiness_packet.v0"
    and .opt_in_plan.implemented_runtime_readiness_packet.implementation_stage == "controlled_opt_in_runtime_readiness_packet"
    and .opt_in_plan.implemented_runtime_readiness_packet.authorized_scope == "explicit_opt_in_fts_runtime_influence"
    and .opt_in_plan.implemented_runtime_readiness_packet.consumes_aggregate_backed_decision_packet_summary == true
    and .opt_in_plan.implemented_runtime_readiness_packet.consumes_store_trial_summary == true
    and .opt_in_plan.implemented_runtime_readiness_packet.consumes_batch_diagnostics_summary == true
    and .opt_in_plan.implemented_runtime_readiness_packet.requires_aggregate_backed_decision_packet == true
    and .opt_in_plan.implemented_runtime_readiness_packet.requires_downstream_aggregate_preflight == true
    and .opt_in_plan.implemented_runtime_readiness_packet.distinguishes_empty_live_probe_from_blocked_control_plane == true
    and .opt_in_plan.implemented_runtime_readiness_packet.can_report_control_plane_ready_without_live_candidates == true
    and .opt_in_plan.implemented_runtime_readiness_packet.can_grant_new_authorization == false
    and .opt_in_plan.implemented_runtime_readiness_packet.may_change_default_memory_search_order == false
    and .opt_in_plan.implemented_runtime_readiness_packet.default_influence_ready == false
    and .opt_in_plan.implemented_runtime_readiness_packet.runtime_influence_decision_packet_included == false
    and .opt_in_plan.implemented_runtime_readiness_packet.store_trial_included == false
    and .opt_in_plan.implemented_runtime_readiness_packet.batch_diagnostics_included == false
    and .opt_in_plan.implemented_runtime_readiness_packet.raw_queries_included == false
    and .opt_in_plan.implemented_runtime_readiness_packet.raw_keys_included == false
    and .opt_in_plan.implemented_runtime_readiness_packet.content_included == false
    and .opt_in_plan.implemented_runtime_readiness_packet.side_signal_raw_included == false
    and .opt_in_plan.implemented_runtime_readiness_packet.human_decision_text_included == false
    and .opt_in_plan.implemented_runtime_readiness_packet.calls_memory_search == false
    and .opt_in_plan.implemented_runtime_readiness_packet.runs_biocortex == false
    and .opt_in_plan.implemented_runtime_readiness_packet.registers_embedding_backend == false
    and .opt_in_plan.implemented_runtime_readiness_packet.changes_memory_search_order == false
    and .opt_in_plan.implemented_runtime_readiness_packet.writes_approval == false
    and .opt_in_plan.implemented_runtime_readiness_packet.default_search_order_change_allowed == false
    and .opt_in_plan.implemented_runtime_readiness_packet.default_calls_unchanged == true
    and .opt_in_plan.implemented_store_opt_in_controlled_order_fixture.cli == "agent-bridge bio-cortex retrieval-opt-in-controlled-order-fixture"
    and .opt_in_plan.implemented_store_opt_in_controlled_order_fixture.fixture == "docs/design/fixtures/biocortex-retrieval-opt-in-controlled-order-fixture-2026-06-12.json"
    and .opt_in_plan.implemented_store_opt_in_controlled_order_fixture.schema == "agent_bridge.biocortex_retrieval.opt_in_controlled_order_fixture_run.v0"
    and .opt_in_plan.implemented_store_opt_in_controlled_order_fixture.implementation_stage == "store_opt_in_controlled_order_fixture"
    and .opt_in_plan.implemented_store_opt_in_controlled_order_fixture.authorized_scope == "explicit_opt_in_fts_runtime_influence"
    and .opt_in_plan.implemented_store_opt_in_controlled_order_fixture.requires_agent_bridge_db_override == true
    and .opt_in_plan.implemented_store_opt_in_controlled_order_fixture.requires_non_production_store_write_ack == true
    and .opt_in_plan.implemented_store_opt_in_controlled_order_fixture.writes_only_fixture_memories == true
    and .opt_in_plan.implemented_store_opt_in_controlled_order_fixture.reuses_store_trial_gate == true
    and .opt_in_plan.implemented_store_opt_in_controlled_order_fixture.proves_actual_order_movement == true
    and .opt_in_plan.implemented_store_opt_in_controlled_order_fixture.raw_queries_included == false
    and .opt_in_plan.implemented_store_opt_in_controlled_order_fixture.raw_keys_included == false
    and .opt_in_plan.implemented_store_opt_in_controlled_order_fixture.content_included == false
    and .opt_in_plan.implemented_store_opt_in_controlled_order_fixture.side_signal_raw_included == false
    and .opt_in_plan.implemented_store_opt_in_controlled_order_fixture.writes_approval == false
    and .opt_in_plan.implemented_store_opt_in_controlled_order_fixture.registers_embedding_backend == false
    and .opt_in_plan.implemented_store_opt_in_controlled_order_fixture.default_search_order_change_allowed == false
    and .opt_in_plan.implemented_store_opt_in_controlled_order_fixture.default_calls_unchanged == true
    and .opt_in_plan.implemented_store_opt_in_evidence_summary.cli == "agent-bridge bio-cortex retrieval-opt-in-evidence-summary"
    and .opt_in_plan.implemented_store_opt_in_evidence_summary.schema == "agent_bridge.biocortex_retrieval.opt_in_evidence_summary.v0"
    and .opt_in_plan.implemented_store_opt_in_evidence_summary.implementation_stage == "post_runtime_evidence_summary"
    and .opt_in_plan.implemented_store_opt_in_evidence_summary.authorized_scope == "explicit_opt_in_fts_runtime_influence"
    and .opt_in_plan.implemented_store_opt_in_evidence_summary.consumes_batch_diagnostics == true
    and .opt_in_plan.implemented_store_opt_in_evidence_summary.consumes_controlled_order_fixture_run == true
    and .opt_in_plan.implemented_store_opt_in_evidence_summary.batch_diagnostics_included == false
    and .opt_in_plan.implemented_store_opt_in_evidence_summary.controlled_order_fixture_run_included == false
    and .opt_in_plan.implemented_store_opt_in_evidence_summary.separates_batch_alignment_from_controlled_movement == true
    and .opt_in_plan.implemented_store_opt_in_evidence_summary.can_recommend_expand_non_production_corpus == true
    and .opt_in_plan.implemented_store_opt_in_evidence_summary.can_grant_runtime_influence == false
    and .opt_in_plan.implemented_store_opt_in_evidence_summary.raw_queries_included == false
    and .opt_in_plan.implemented_store_opt_in_evidence_summary.raw_keys_included == false
    and .opt_in_plan.implemented_store_opt_in_evidence_summary.content_included == false
    and .opt_in_plan.implemented_store_opt_in_evidence_summary.side_signal_raw_included == false
    and .opt_in_plan.implemented_store_opt_in_evidence_summary.writes_approval == false
    and .opt_in_plan.implemented_store_opt_in_evidence_summary.calls_memory_search == false
    and .opt_in_plan.implemented_store_opt_in_evidence_summary.runs_biocortex == false
    and .opt_in_plan.implemented_store_opt_in_evidence_summary.registers_embedding_backend == false
    and .opt_in_plan.implemented_store_opt_in_evidence_summary.default_search_order_change_allowed == false
    and .opt_in_plan.implemented_store_opt_in_evidence_summary.default_calls_unchanged == true
    and .opt_in_plan.implemented_store_opt_in_expanded_non_production_corpus.fixture == "docs/design/fixtures/biocortex-retrieval-opt-in-expanded-controlled-corpus-2026-06-12.json"
    and .opt_in_plan.implemented_store_opt_in_expanded_non_production_corpus.reuses_cli == "agent-bridge bio-cortex retrieval-opt-in-controlled-order-fixture"
    and .opt_in_plan.implemented_store_opt_in_expanded_non_production_corpus.reuses_evidence_summary_cli == "agent-bridge bio-cortex retrieval-opt-in-evidence-summary"
    and .opt_in_plan.implemented_store_opt_in_expanded_non_production_corpus.schema == "agent_bridge.biocortex_retrieval.opt_in_controlled_order_fixture_run.v0"
    and .opt_in_plan.implemented_store_opt_in_expanded_non_production_corpus.implementation_stage == "expanded_non_production_adapter_coverage"
    and .opt_in_plan.implemented_store_opt_in_expanded_non_production_corpus.authorized_scope == "explicit_opt_in_fts_runtime_influence"
    and .opt_in_plan.implemented_store_opt_in_expanded_non_production_corpus.memory_record_count == 10
    and .opt_in_plan.implemented_store_opt_in_expanded_non_production_corpus.query_count == 5
    and .opt_in_plan.implemented_store_opt_in_expanded_non_production_corpus.expected_min_actual_order_changed_count == 0
    and .opt_in_plan.implemented_store_opt_in_expanded_non_production_corpus.expected_min_experimental_source_count == 5
    and .opt_in_plan.implemented_store_opt_in_expanded_non_production_corpus.expected_min_side_signal_ok_count == 5
    and .opt_in_plan.implemented_store_opt_in_expanded_non_production_corpus.proves_multi_bucket_adapter_coverage == true
    and .opt_in_plan.implemented_store_opt_in_expanded_non_production_corpus.proves_additional_rank_movement == false
    and .opt_in_plan.implemented_store_opt_in_expanded_non_production_corpus.canonical_rank_movement_fixture == "docs/design/fixtures/biocortex-retrieval-opt-in-controlled-order-fixture-2026-06-12.json"
    and .opt_in_plan.implemented_store_opt_in_expanded_non_production_corpus.writes_only_fixture_memories == true
    and .opt_in_plan.implemented_store_opt_in_expanded_non_production_corpus.uses_non_production_store_only == true
    and .opt_in_plan.implemented_store_opt_in_expanded_non_production_corpus.uses_redacted_evidence_summary == true
    and .opt_in_plan.implemented_store_opt_in_expanded_non_production_corpus.raw_queries_included == false
    and .opt_in_plan.implemented_store_opt_in_expanded_non_production_corpus.raw_keys_included == false
    and .opt_in_plan.implemented_store_opt_in_expanded_non_production_corpus.content_included == false
    and .opt_in_plan.implemented_store_opt_in_expanded_non_production_corpus.side_signal_raw_included == false
    and .opt_in_plan.implemented_store_opt_in_expanded_non_production_corpus.writes_approval == false
    and .opt_in_plan.implemented_store_opt_in_expanded_non_production_corpus.calls_memory_search == true
    and .opt_in_plan.implemented_store_opt_in_expanded_non_production_corpus.runs_biocortex == true
    and .opt_in_plan.implemented_store_opt_in_expanded_non_production_corpus.registers_embedding_backend == false
    and .opt_in_plan.implemented_store_opt_in_expanded_non_production_corpus.can_grant_runtime_influence == false
    and .opt_in_plan.implemented_store_opt_in_expanded_non_production_corpus.default_search_order_change_allowed == false
    and .opt_in_plan.implemented_store_opt_in_expanded_non_production_corpus.default_calls_unchanged == true
    and .opt_in_plan.implemented_store_opt_in_redacted_evidence_aggregate.cli == "agent-bridge bio-cortex retrieval-opt-in-redacted-evidence-aggregate"
    and .opt_in_plan.implemented_store_opt_in_redacted_evidence_aggregate.schema == "agent_bridge.biocortex_retrieval.opt_in_redacted_evidence_aggregate.v0"
    and .opt_in_plan.implemented_store_opt_in_redacted_evidence_aggregate.implementation_stage == "post_runtime_redacted_evidence_aggregate"
    and .opt_in_plan.implemented_store_opt_in_redacted_evidence_aggregate.authorized_scope == "explicit_opt_in_fts_runtime_influence"
    and .opt_in_plan.implemented_store_opt_in_redacted_evidence_aggregate.consumes_movement_fixture_run == true
    and .opt_in_plan.implemented_store_opt_in_redacted_evidence_aggregate.consumes_expanded_coverage_fixture_run == true
    and .opt_in_plan.implemented_store_opt_in_redacted_evidence_aggregate.movement_fixture_run_included == false
    and .opt_in_plan.implemented_store_opt_in_redacted_evidence_aggregate.coverage_fixture_run_included == false
    and .opt_in_plan.implemented_store_opt_in_redacted_evidence_aggregate.combines_rank_movement_and_adapter_coverage == true
    and .opt_in_plan.implemented_store_opt_in_redacted_evidence_aggregate.requires_controlled_rank_movement == true
    and .opt_in_plan.implemented_store_opt_in_redacted_evidence_aggregate.requires_expanded_coverage_without_additional_movement == true
    and .opt_in_plan.implemented_store_opt_in_redacted_evidence_aggregate.can_recommend_human_runtime_influence_review_request == true
    and .opt_in_plan.implemented_store_opt_in_redacted_evidence_aggregate.can_grant_runtime_influence == false
    and .opt_in_plan.implemented_store_opt_in_redacted_evidence_aggregate.raw_queries_included == false
    and .opt_in_plan.implemented_store_opt_in_redacted_evidence_aggregate.raw_keys_included == false
    and .opt_in_plan.implemented_store_opt_in_redacted_evidence_aggregate.content_included == false
    and .opt_in_plan.implemented_store_opt_in_redacted_evidence_aggregate.side_signal_raw_included == false
    and .opt_in_plan.implemented_store_opt_in_redacted_evidence_aggregate.writes_approval == false
    and .opt_in_plan.implemented_store_opt_in_redacted_evidence_aggregate.calls_memory_search == false
    and .opt_in_plan.implemented_store_opt_in_redacted_evidence_aggregate.runs_biocortex == false
    and .opt_in_plan.implemented_store_opt_in_redacted_evidence_aggregate.registers_embedding_backend == false
    and .opt_in_plan.implemented_store_opt_in_redacted_evidence_aggregate.default_search_order_change_allowed == false
    and .opt_in_plan.implemented_store_opt_in_redacted_evidence_aggregate.default_calls_unchanged == true
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
    and .opt_in_plan.implemented_runtime_influence_review_request.accepts_redacted_evidence_aggregate_summary == true
    and .opt_in_plan.implemented_runtime_influence_review_request.requires_aggregate_ready_when_provided == true
    and .opt_in_plan.implemented_runtime_influence_review_request.post_implementation_review_gate_included == false
    and .opt_in_plan.implemented_runtime_influence_review_request.redacted_order_artifact_included == false
    and .opt_in_plan.implemented_runtime_influence_review_request.redacted_evidence_aggregate_included == false
    and .opt_in_plan.implemented_runtime_influence_review_request.keeps_default_influence_unready == true
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
    and .opt_in_plan.implemented_runtime_influence_decision_packet.accepts_aggregate_backed_review_request == true
    and .opt_in_plan.implemented_runtime_influence_decision_packet.requires_aggregate_ready_when_provided == true
    and .opt_in_plan.implemented_runtime_influence_decision_packet.legacy_review_request_without_aggregate_allowed == true
    and .opt_in_plan.implemented_runtime_influence_decision_packet.runtime_influence_review_request_included == false
    and .opt_in_plan.implemented_runtime_influence_decision_packet.runtime_influence_decision_included == false
    and .opt_in_plan.implemented_runtime_influence_decision_packet.redacted_evidence_aggregate_included == false
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
    and .request_summary.opt_in_plan_status == "loopback_lswr_host_attach_preflight_blocked"
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
    and .plan_summary.status == "loopback_lswr_host_attach_preflight_blocked"
    and .plan_summary.implementation_allowed == true
    and .plan_summary.store_opt_in_search_wrapper_implemented == true
    and .plan_summary.authorization_decision_consumer_implemented == true
    and .plan_summary.post_implementation_review_gate_implemented == true
    and .plan_summary.runtime_influence_review_request_implemented == true
    and .plan_summary.runtime_influence_decision_packet_implemented == true
    and .plan_summary.store_opt_in_order_connection_implemented == true
    and .plan_summary.store_opt_in_runtime_adapter_connection_implemented == true
    and .plan_summary.runtime_readiness_packet_implemented == true
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
    and .input_contract.redacted_evidence_aggregate_schema == null
    and .input_contract.accepts_optional_redacted_evidence_aggregate == true
    and .input_contract.requires_aggregate_ready_when_provided == true
    and .input_contract.post_implementation_review_gate_included == false
    and .input_contract.redacted_order_artifact_included == false
    and .input_contract.redacted_evidence_aggregate_included == false
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
    and .requested_authorization.accepts_redacted_evidence_aggregate == true
    and .requested_authorization.requires_redacted_evidence_aggregate == false
    and .requested_authorization.this_packet_grants_request == false
    and .evidence_summary.post_implementation_gate_ready == true
    and .evidence_summary.gate_review_state == "ready_for_human_runtime_influence_review"
    and .evidence_summary.redacted_order_artifact_ready == true
    and .evidence_summary.redacted_rows_comparable == true
    and .evidence_summary.baseline_returned == true
    and .evidence_summary.actual_return_order_changed == false
    and .evidence_summary.redacted_evidence_aggregate_provided == false
    and .evidence_summary.redacted_evidence_aggregate_ready == false
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
    and .boundary_check.redacted_evidence_aggregate_provided == false
    and .boundary_check.redacted_evidence_aggregate_ready == false
    and .boundary_check.aggregate_safe_for_review == true
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
    and .input_contract.accepts_aggregate_backed_review_request == true
    and .input_contract.requires_aggregate_ready_when_provided == true
    and .input_contract.redacted_evidence_aggregate_included == false
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
    and .request_summary.aggregate_backed_review_request == false
    and .request_summary.aggregate_review_evidence_state == "not_provided_legacy_compatible"
    and .request_summary.redacted_evidence_aggregate_provided == false
    and .request_summary.default_influence_ready == false
    and .request_summary.redacted_evidence_aggregate_summary_included == false
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
    and .boundary_check.aggregate_backed_review_request == false
    and .boundary_check.aggregate_review_evidence_ready == false
    and .boundary_check.legacy_review_request_without_aggregate_allowed == true
    and .boundary_check.aggregate_contract_ok == true
    and .boundary_check.aggregate_summary_redacted == true
    and .boundary_check.aggregate_safe_for_decision == true
    and .boundary_check.aggregate_default_influence_still_not_ready == true
    and .boundary_check.aggregate_human_review_required == true
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

opt_in_store_trial_disabled="$tmpdir/opt-in-store-trial-disabled.json"
run env AGENT_BRIDGE_DB="$tmpdir/opt-in-store-trial-disabled.db" \
    cargo run -p ab-bridge --no-default-features -- \
    bio-cortex retrieval-opt-in-store-trial \
    --runtime-influence-decision-packet-json "$opt_in_runtime_influence_decision_packet" \
    --query "verify store trial secret query" \
    --per-call-opt-in \
    --limit 3 \
    --attempt-id verify-store-trial-disabled \
    --commit verify-dry-run-commit \
    --json > "$opt_in_store_trial_disabled"
jq -e '
    .schema == "agent_bridge.biocortex_retrieval.opt_in_store_trial.v0"
    and .implementation_stage == "store_opt_in_runtime_adapter_connection"
    and .authorization_scope == "explicit_opt_in_fts_runtime_influence"
    and .input_contract.accepts_aggregate_backed_decision_packet == true
    and .input_contract.requires_aggregate_ready_when_provided == true
    and .input_contract.redacted_evidence_aggregate_included == false
    and .input_contract.aggregate_evidence_summary_included == false
    and .runtime_preflight.adapter_allowed == false
    and (.runtime_preflight.blockers | index("compile_feature_disabled"))
    and (.runtime_preflight.blockers | index("runtime_disabled"))
    and (.runtime_preflight.blockers | index("baseline_empty"))
    and .runtime_preflight.decision_packet_authorized == true
    and .runtime_preflight.decision_packet_aggregate_backed == false
    and .runtime_preflight.decision_packet_aggregate_review_evidence_ready == false
    and .runtime_preflight.legacy_decision_packet_without_aggregate_allowed == true
    and .runtime_preflight.decision_packet_aggregate_contract_ok == true
    and .runtime_preflight.decision_packet_aggregate_summary_redacted == true
    and .runtime_preflight.decision_packet_aggregate_safe_for_trial == true
    and .runtime_preflight.decision_packet_aggregate_default_influence_ready == false
    and .runtime_preflight.decision_packet_aggregate_human_review_required == true
    and .runtime_preflight.baseline_completed == true
    and .baseline_order.key_count == 0
    and .baseline_order.raw_keys_included == false
    and .baseline_order.content_included == false
    and .side_signal.attempted == false
    and .side_signal.raw_included == false
    and .protected_adapter_contract.raw_query_included == false
    and .protected_adapter_contract.raw_keys_included == false
    and .protected_adapter_contract.content_included == false
    and .store_wrapper.called == true
    and .returned_order.baseline_returned == true
    and .returned_order.actual_return_order_changed == false
    and .returned_order.raw_keys_included == false
    and .returned_order.content_included == false
    and .calls_memory_search == true
    and .runs_biocortex == false
    and .registers_embedding_backend == false
    and .default_search_order_change_allowed == false
    and .default_calls_unchanged == true
' "$opt_in_store_trial_disabled" >/dev/null
if grep -q 'verify store trial secret query\|verify_runtime_trial_secret_key\|verify runtime trial secret content' "$opt_in_store_trial_disabled"; then
    echo "opt-in store trial disabled path leaked raw query/key/content data" >&2
    exit 1
fi

opt_in_store_trial_empty="$tmpdir/opt-in-store-trial-empty.json"
run env AGENT_BRIDGE_DB="$tmpdir/opt-in-store-trial-empty.db" \
    AB_BIOCORTEX_RETRIEVAL_OPT_IN=1 \
    cargo run -p ab-bridge --no-default-features --features biocortex-retrieval-opt-in -- \
    bio-cortex retrieval-opt-in-store-trial \
    --runtime-influence-decision-packet-json "$opt_in_runtime_influence_decision_packet" \
    --query "verify store trial ready secret query" \
    --per-call-opt-in \
    --checkout "$biocortex_rs" \
    --limit 3 \
    --attempt-id verify-store-trial-empty \
    --commit verify-dry-run-commit \
    --json > "$opt_in_store_trial_empty"
jq -e '
    .schema == "agent_bridge.biocortex_retrieval.opt_in_store_trial.v0"
    and .input_contract.accepts_aggregate_backed_decision_packet == true
    and .input_contract.requires_aggregate_ready_when_provided == true
    and .input_contract.redacted_evidence_aggregate_included == false
    and .input_contract.aggregate_evidence_summary_included == false
    and .runtime_preflight.compile_feature_enabled == true
    and .runtime_preflight.runtime_enabled == true
    and .runtime_preflight.operator_disabled == false
    and .runtime_preflight.decision_packet_authorized == true
    and .runtime_preflight.decision_packet_aggregate_backed == false
    and .runtime_preflight.decision_packet_aggregate_review_evidence_ready == false
    and .runtime_preflight.legacy_decision_packet_without_aggregate_allowed == true
    and .runtime_preflight.decision_packet_aggregate_safe_for_trial == true
    and .runtime_preflight.adapter_allowed == false
    and (.runtime_preflight.blockers | index("baseline_empty"))
    and .baseline_order.completed == true
    and .baseline_order.key_count == 0
    and .side_signal.attempted == false
    and .store_wrapper.called == true
    and .returned_order.baseline_returned == true
    and .returned_order.actual_return_order_changed == false
    and .calls_memory_search == true
    and .runs_biocortex == false
    and .raw_query_included == false
    and .raw_keys_included == false
    and .content_included == false
    and .side_signal_raw_included == false
    and .default_search_order_change_allowed == false
    and .default_calls_unchanged == true
' "$opt_in_store_trial_empty" >/dev/null
if grep -q 'verify store trial ready secret query\|verify_runtime_trial_secret_key\|verify runtime trial secret content' "$opt_in_store_trial_empty"; then
    echo "opt-in store trial empty path leaked raw query/key/content data" >&2
    exit 1
fi

opt_in_batch_diagnostics_disabled="$tmpdir/opt-in-batch-diagnostics-disabled.json"
run env AGENT_BRIDGE_DB="$tmpdir/opt-in-batch-diagnostics-disabled.db" \
    cargo run -p ab-bridge --no-default-features -- \
    bio-cortex retrieval-opt-in-batch-diagnostics \
    --runtime-influence-decision-packet-json "$opt_in_runtime_influence_decision_packet" \
    --query-cases-json "$opt_in_batch_query_cases" \
    --per-call-opt-in \
    --limit 3 \
    --attempt-id verify-batch-diagnostics-disabled \
    --commit verify-dry-run-commit \
    --json > "$opt_in_batch_diagnostics_disabled"
jq -e '
    .schema == "agent_bridge.biocortex_retrieval.opt_in_batch_diagnostics.v0"
    and .implementation_stage == "store_opt_in_batch_diagnostics"
    and .status == "completed"
    and .attempt.query_count == 6
    and .input_contract.runtime_influence_decision_packet_included == false
    and .input_contract.accepts_aggregate_backed_decision_packet == true
    and .input_contract.requires_aggregate_ready_when_provided == true
    and .input_contract.redacted_evidence_aggregate_included == false
    and .input_contract.aggregate_evidence_summary_included == false
    and .input_contract.raw_queries_included == false
    and .input_contract.raw_keys_included == false
    and .input_contract.content_included == false
    and .input_contract.side_signal_raw_included == false
    and .summary.query_count == 6
    and .summary.baseline_completed_count == 6
    and .summary.baseline_empty_count == 6
    and .summary.adapter_allowed_count == 0
    and .summary.side_signal_attempted_count == 0
    and .summary.side_signal_ok_count == 0
    and .summary.actual_order_changed_count == 0
    and .summary.raw_flagged_count == 0
    and (.bucket_summary | length) == 6
    and ([.bucket_summary[].class_label] | sort) == ["approval_gate","baseline_retrieval","fail_open","mcp_surface","rank_movement","runtime_adapter"]
    and (.query_results | length) == 6
    and ([.query_results[].movement_class] | unique) == ["preflight_blocked"]
    and ([.query_results[].preflight.adapter_allowed] | unique) == [false]
    and ([.query_results[].preflight.decision_packet_aggregate_backed] | unique) == [false]
    and ([.query_results[].preflight.decision_packet_aggregate_review_evidence_ready] | unique) == [false]
    and ([.query_results[].preflight.legacy_decision_packet_without_aggregate_allowed] | unique) == [true]
    and ([.query_results[].preflight.decision_packet_aggregate_safe_for_trial] | unique) == [true]
    and ([.query_results[].baseline.key_count] | unique) == [0]
    and ([.query_results[].raw_query_included] | unique) == [false]
    and ([.query_results[].raw_keys_included] | unique) == [false]
    and ([.query_results[].content_included] | unique) == [false]
    and .safety.calls_memory_search_all == true
    and .safety.runs_biocortex_any == false
    and .safety.actual_return_order_changed_any == false
    and .safety.raw_flags_all_false == true
    and .raw_queries_included == false
    and .raw_keys_included == false
    and .content_included == false
    and .side_signal_raw_included == false
    and .default_search_order_change_allowed == false
    and .default_calls_unchanged == true
' "$opt_in_batch_diagnostics_disabled" >/dev/null
if grep -q 'biocortex opt-in runtime adapter\|runtime influence decision packet\|memory search baseline recall\|redacted order artifact movement\|agent bridge mcp tool registry\|agent bridge mcp\|verify_runtime_trial_secret_key\|verify runtime trial secret content' "$opt_in_batch_diagnostics_disabled"; then
    echo "opt-in batch diagnostics disabled path leaked raw query/key/content data" >&2
    exit 1
fi

opt_in_batch_diagnostics_empty="$tmpdir/opt-in-batch-diagnostics-empty.json"
run env AGENT_BRIDGE_DB="$tmpdir/opt-in-batch-diagnostics-empty.db" \
    AB_BIOCORTEX_RETRIEVAL_OPT_IN=1 \
    cargo run -p ab-bridge --no-default-features --features biocortex-retrieval-opt-in -- \
    bio-cortex retrieval-opt-in-batch-diagnostics \
    --runtime-influence-decision-packet-json "$opt_in_runtime_influence_decision_packet" \
    --query-cases-json "$opt_in_batch_query_cases" \
    --per-call-opt-in \
    --checkout "$biocortex_rs" \
    --limit 3 \
    --attempt-id verify-batch-diagnostics-empty \
    --commit verify-dry-run-commit \
    --json > "$opt_in_batch_diagnostics_empty"
jq -e '
    .schema == "agent_bridge.biocortex_retrieval.opt_in_batch_diagnostics.v0"
    and .input_contract.accepts_aggregate_backed_decision_packet == true
    and .input_contract.requires_aggregate_ready_when_provided == true
    and .input_contract.redacted_evidence_aggregate_included == false
    and .input_contract.aggregate_evidence_summary_included == false
    and .summary.query_count == 6
    and .summary.baseline_completed_count == 6
    and .summary.baseline_empty_count == 6
    and .summary.adapter_allowed_count == 0
    and .summary.side_signal_attempted_count == 0
    and .summary.runs_biocortex_count == 0
    and .summary.default_calls_unchanged_count == 6
    and ([.query_results[].class_label] | sort) == ["approval_gate","baseline_retrieval","fail_open","mcp_surface","rank_movement","runtime_adapter"]
    and ([.query_results[].movement_class] | unique) == ["preflight_blocked"]
    and ([.query_results[].preflight.compile_feature_enabled] | unique) == [true]
    and ([.query_results[].preflight.runtime_enabled] | unique) == [true]
    and ([.query_results[].preflight.operator_disabled] | unique) == [false]
    and ([.query_results[].preflight.decision_packet_authorized] | unique) == [true]
    and ([.query_results[].preflight.decision_packet_aggregate_backed] | unique) == [false]
    and ([.query_results[].preflight.decision_packet_aggregate_review_evidence_ready] | unique) == [false]
    and ([.query_results[].preflight.legacy_decision_packet_without_aggregate_allowed] | unique) == [true]
    and ([.query_results[].preflight.decision_packet_aggregate_safe_for_trial] | unique) == [true]
    and ([.query_results[].side_signal.attempted] | unique) == [false]
    and ([.query_results[].runs_biocortex] | unique) == [false]
    and .safety.calls_memory_search_all == true
    and .safety.runs_biocortex_any == false
    and .safety.raw_flags_all_false == true
    and .default_search_order_change_allowed == false
    and .default_calls_unchanged == true
' "$opt_in_batch_diagnostics_empty" >/dev/null
if grep -q 'biocortex opt-in runtime adapter\|runtime influence decision packet\|memory search baseline recall\|redacted order artifact movement\|agent bridge mcp tool registry\|agent bridge mcp\|verify_runtime_trial_secret_key\|verify runtime trial secret content' "$opt_in_batch_diagnostics_empty"; then
    echo "opt-in batch diagnostics empty path leaked raw query/key/content data" >&2
    exit 1
fi

opt_in_controlled_order="$tmpdir/opt-in-controlled-order-fixture.json"
run env AGENT_BRIDGE_DB="$tmpdir/opt-in-controlled-order-fixture.db" \
    AB_BIOCORTEX_RETRIEVAL_OPT_IN=1 \
    cargo run -p ab-bridge --no-default-features --features biocortex-retrieval-opt-in -- \
    bio-cortex retrieval-opt-in-controlled-order-fixture \
    --runtime-influence-decision-packet-json "$opt_in_runtime_influence_decision_packet" \
    --fixture-json "$opt_in_controlled_order_fixture" \
    --allow-non-production-store-writes \
    --per-call-opt-in \
    --checkout "$biocortex_rs" \
    --limit 5 \
    --coverage-threshold 0.5 \
    --attempt-id verify-controlled-order-fixture \
    --commit verify-dry-run-commit \
    --json > "$opt_in_controlled_order"
jq -e '
    .schema == "agent_bridge.biocortex_retrieval.opt_in_controlled_order_fixture_run.v0"
    and .controlled_order_fixture == true
    and .implementation_stage == "store_opt_in_controlled_order_fixture"
    and .status == "completed"
    and .expected.met == true
    and .attempt.seeded_memory_count == 2
    and .attempt.query_count == 1
    and .fixture_contract.requires_agent_bridge_db_override == true
    and .fixture_contract.requires_non_production_store_write_ack == true
    and .fixture_contract.writes_ab_store == true
    and .fixture_contract.writes_approval == false
    and .fixture_contract.registers_embedding_backend == false
    and .fixture_contract.raw_queries_included == false
    and .fixture_contract.raw_keys_included == false
    and .fixture_contract.content_included == false
    and .fixture_contract.side_signal_raw_included == false
    and .diagnostics.schema == "agent_bridge.biocortex_retrieval.opt_in_batch_diagnostics.v0"
    and .diagnostics.summary.query_count == 1
    and .diagnostics.summary.baseline_completed_count == 1
    and .diagnostics.summary.baseline_empty_count == 0
    and .diagnostics.summary.adapter_allowed_count == 1
    and .diagnostics.summary.side_signal_attempted_count == 1
    and .diagnostics.summary.side_signal_ok_count == 1
    and .diagnostics.summary.experimental_source_count == 1
    and .diagnostics.summary.actual_order_changed_count == 1
    and .diagnostics.summary.raw_flagged_count == 0
    and .diagnostics.query_results[0].movement_class == "experimental_moved_order"
    and .diagnostics.query_results[0].returned_order.actual_return_order_changed == true
    and .diagnostics.query_results[0].returned_order.hash_matches_baseline == false
    and .diagnostics.query_results[0].raw_query_included == false
    and .diagnostics.query_results[0].raw_keys_included == false
    and .diagnostics.query_results[0].content_included == false
    and .diagnostics.query_results[0].side_signal_raw_included == false
    and .diagnostics.safety.calls_memory_search_all == true
    and .diagnostics.safety.runs_biocortex_any == true
    and .diagnostics.safety.actual_return_order_changed_any == true
    and .diagnostics.safety.raw_flags_all_false == true
    and .raw_queries_included == false
    and .raw_keys_included == false
    and .content_included == false
    and .side_signal_raw_included == false
    and .default_search_order_change_allowed == false
    and .default_calls_unchanged == true
' "$opt_in_controlled_order" >/dev/null
if grep -q 'cortexdelta\|cortexepsilon\|cortexzeta\|cortexeta\|cortextheta\|cortexiota\|controlled_order_baseline_high\|controlled_order_biocortex_target\|target anchor\|baseline anchor' "$opt_in_controlled_order"; then
    echo "opt-in controlled order fixture leaked raw query/key/content data" >&2
    exit 1
fi

opt_in_evidence_summary="$tmpdir/opt-in-evidence-summary.json"
run cargo run -p ab-bridge --no-default-features --features biocortex-retrieval-opt-in -- \
    bio-cortex retrieval-opt-in-evidence-summary \
    --batch-diagnostics-json "$opt_in_batch_diagnostics_empty" \
    --controlled-order-fixture-run-json "$opt_in_controlled_order" \
    --reviewer verify-bundle \
    --commit verify-dry-run-commit \
    --forum-post-id verify-forum-post \
    --memory-key verify-memory-key \
    --json > "$opt_in_evidence_summary"
jq -e '
    .schema == "agent_bridge.biocortex_retrieval.opt_in_evidence_summary.v0"
    and .read_only == true
    and .evidence_summary == true
    and .implementation_stage == "post_runtime_evidence_summary"
    and .authorization_scope == "explicit_opt_in_fts_runtime_influence"
    and .input_contract.batch_diagnostics_schema == "agent_bridge.biocortex_retrieval.opt_in_batch_diagnostics.v0"
    and .input_contract.controlled_order_fixture_run_schema == "agent_bridge.biocortex_retrieval.opt_in_controlled_order_fixture_run.v0"
    and .input_contract.batch_diagnostics_included == false
    and .input_contract.controlled_order_fixture_run_included == false
    and .input_contract.raw_queries_included == false
    and .input_contract.raw_keys_included == false
    and .input_contract.content_included == false
    and .input_contract.side_signal_raw_included == false
    and .batch_diagnostics.schema_ok == true
    and .batch_diagnostics.query_count == 6
    and .batch_diagnostics.baseline_completed_count == 6
    and .batch_diagnostics.baseline_empty_count == 6
    and .batch_diagnostics.adapter_allowed_count == 0
    and .batch_diagnostics.actual_order_changed_count == 0
    and .batch_diagnostics.raw_flags_all_false == true
    and .batch_diagnostics.movement_observed == false
    and .batch_diagnostics.diagnostic_class == "preflight_or_baseline_empty"
    and .controlled_order.schema_ok == true
    and .controlled_order.expected_met == true
    and .controlled_order.seeded_memory_count == 2
    and .controlled_order.query_count == 1
    and .controlled_order.adapter_allowed_count == 1
    and .controlled_order.side_signal_ok_count == 1
    and .controlled_order.experimental_source_count == 1
    and .controlled_order.actual_order_changed_count == 1
    and .controlled_order.raw_flags_all_false == true
    and .controlled_order.movement_observed == true
    and .interpretation.batch_diagnostics_raw_safe == true
    and .interpretation.controlled_order_raw_safe == true
    and .interpretation.runtime_adapter_connection_evidence == true
    and .interpretation.batch_alignment_or_preflight_evidence == true
    and .interpretation.controlled_rank_movement_observed == true
    and .interpretation.evidence_ready == true
    and .interpretation.default_influence_ready == false
    and .interpretation.recommended_next_step == "expand_non_production_corpus"
    and .interpretation.review_state == "post_runtime_evidence_ready"
    and .approval_state == "evidence_summary_only"
    and .authorization_state == "does_not_grant_runtime_influence"
    and .approval_writes_allowed == false
    and .writes_approval == false
    and .calls_memory_search == false
    and .runs_biocortex == false
    and .registers_embedding_backend == false
    and .changes_memory_search_order == false
    and .default_search_order_change_allowed == false
    and .default_calls_unchanged == true
    and .raw_queries_included == false
    and .raw_keys_included == false
    and .content_included == false
    and .side_signal_raw_included == false
' "$opt_in_evidence_summary" >/dev/null
if grep -q 'cortexdelta\|cortexepsilon\|cortexzeta\|cortexeta\|cortextheta\|cortexiota\|controlled_order_baseline_high\|controlled_order_biocortex_target\|target anchor\|baseline anchor\|biocortex opt-in runtime adapter\|runtime influence decision packet\|memory search baseline recall\|redacted order artifact movement\|agent bridge mcp tool registry\|agent bridge mcp\|verify_runtime_trial_secret_key\|verify runtime trial secret content' "$opt_in_evidence_summary"; then
    echo "opt-in evidence summary leaked raw query/key/content data" >&2
    exit 1
fi

opt_in_expanded_corpus="$tmpdir/opt-in-expanded-controlled-corpus.json"
run env AGENT_BRIDGE_DB="$tmpdir/opt-in-expanded-controlled-corpus.db" \
    AB_BIOCORTEX_RETRIEVAL_OPT_IN=1 \
    cargo run -p ab-bridge --no-default-features --features biocortex-retrieval-opt-in -- \
    bio-cortex retrieval-opt-in-controlled-order-fixture \
    --runtime-influence-decision-packet-json "$opt_in_runtime_influence_decision_packet" \
    --fixture-json "$opt_in_expanded_corpus_fixture" \
    --allow-non-production-store-writes \
    --per-call-opt-in \
    --checkout "$biocortex_rs" \
    --limit 5 \
    --coverage-threshold 0.5 \
    --attempt-id verify-expanded-controlled-corpus \
    --commit verify-dry-run-commit \
    --json > "$opt_in_expanded_corpus"
jq -e '
    .schema == "agent_bridge.biocortex_retrieval.opt_in_controlled_order_fixture_run.v0"
    and .controlled_order_fixture == true
    and .implementation_stage == "store_opt_in_controlled_order_fixture"
    and .status == "completed"
    and .expected.met == true
    and .attempt.seeded_memory_count == 10
    and .attempt.query_count == 5
    and .fixture_contract.requires_agent_bridge_db_override == true
    and .fixture_contract.requires_non_production_store_write_ack == true
    and .fixture_contract.writes_ab_store == true
    and .fixture_contract.writes_approval == false
    and .fixture_contract.registers_embedding_backend == false
    and .fixture_contract.raw_queries_included == false
    and .fixture_contract.raw_keys_included == false
    and .fixture_contract.content_included == false
    and .fixture_contract.side_signal_raw_included == false
    and .diagnostics.schema == "agent_bridge.biocortex_retrieval.opt_in_batch_diagnostics.v0"
    and .diagnostics.summary.query_count == 5
    and .diagnostics.summary.baseline_completed_count == 5
    and .diagnostics.summary.baseline_empty_count == 0
    and .diagnostics.summary.adapter_allowed_count == 5
    and .diagnostics.summary.side_signal_attempted_count == 5
    and .diagnostics.summary.side_signal_ok_count == 5
    and .diagnostics.summary.experimental_source_count == 5
    and .diagnostics.summary.actual_order_changed_count == 0
    and .diagnostics.summary.hash_matches_baseline_count == 5
    and .diagnostics.summary.raw_flagged_count == 0
    and .diagnostics.summary.runs_biocortex_count == 5
    and (.diagnostics.query_results | length) == 5
    and ([.diagnostics.query_results[].movement_class] | unique) == ["experimental_aligned_with_baseline"]
    and ([.diagnostics.query_results[].returned_order.actual_return_order_changed] | unique) == [false]
    and ([.diagnostics.query_results[].returned_order.hash_matches_baseline] | unique) == [true]
    and ([.diagnostics.query_results[].raw_query_included] | unique) == [false]
    and ([.diagnostics.query_results[].raw_keys_included] | unique) == [false]
    and ([.diagnostics.query_results[].content_included] | unique) == [false]
    and ([.diagnostics.query_results[].side_signal_raw_included] | unique) == [false]
    and .diagnostics.safety.calls_memory_search_all == true
    and .diagnostics.safety.runs_biocortex_any == true
    and .diagnostics.safety.actual_return_order_changed_any == false
    and .diagnostics.safety.raw_flags_all_false == true
    and .raw_queries_included == false
    and .raw_keys_included == false
    and .content_included == false
    and .side_signal_raw_included == false
    and .default_search_order_change_allowed == false
    and .default_calls_unchanged == true
' "$opt_in_expanded_corpus" >/dev/null
if grep -q 'axonalpha\|axonbeta\|axongamma\|axondelta\|axonepsilon\|axonzeta\|dendritealpha\|dendritebeta\|dendritegamma\|dendritedelta\|dendriteepsilon\|dendritezeta\|gliaalph\|gliabet\|gliagam\|gliadel\|gliaeps\|gliazet\|myelinalpha\|myelinbeta\|myelingamma\|myelindelta\|myelinepsilon\|myelinzeta\|synapsealpha\|synapsebeta\|synapsegamma\|synapsedelta\|synapseepsilon\|synapsezeta\|expanded_corpus_baseline_focus\|expanded_corpus_target_span\|baseline focus\|target span' "$opt_in_expanded_corpus"; then
    echo "opt-in expanded controlled corpus leaked raw query/key/content data" >&2
    exit 1
fi

opt_in_expanded_evidence_summary="$tmpdir/opt-in-expanded-evidence-summary.json"
run cargo run -p ab-bridge --no-default-features --features biocortex-retrieval-opt-in -- \
    bio-cortex retrieval-opt-in-evidence-summary \
    --batch-diagnostics-json "$opt_in_batch_diagnostics_empty" \
    --controlled-order-fixture-run-json "$opt_in_expanded_corpus" \
    --reviewer verify-bundle \
    --commit verify-dry-run-commit \
    --forum-post-id verify-forum-post \
    --memory-key verify-memory-key \
    --json > "$opt_in_expanded_evidence_summary"
jq -e '
    .schema == "agent_bridge.biocortex_retrieval.opt_in_evidence_summary.v0"
    and .read_only == true
    and .evidence_summary == true
    and .implementation_stage == "post_runtime_evidence_summary"
    and .batch_diagnostics.query_count == 6
    and .batch_diagnostics.raw_flags_all_false == true
    and .controlled_order.schema_ok == true
    and .controlled_order.expected_met == true
    and .controlled_order.seeded_memory_count == 10
    and .controlled_order.query_count == 5
    and .controlled_order.adapter_allowed_count == 5
    and .controlled_order.side_signal_ok_count == 5
    and .controlled_order.experimental_source_count == 5
    and .controlled_order.actual_order_changed_count == 0
    and .controlled_order.raw_flags_all_false == true
    and .controlled_order.movement_observed == false
    and .interpretation.batch_diagnostics_raw_safe == true
    and .interpretation.controlled_order_raw_safe == true
    and .interpretation.runtime_adapter_connection_evidence == true
    and .interpretation.controlled_rank_movement_observed == false
    and .interpretation.evidence_ready == false
    and .interpretation.default_influence_ready == false
    and .interpretation.recommended_next_step == "collect_missing_redacted_evidence"
    and .interpretation.review_state == "post_runtime_evidence_incomplete"
    and .approval_state == "evidence_summary_only"
    and .authorization_state == "does_not_grant_runtime_influence"
    and .approval_writes_allowed == false
    and .writes_approval == false
    and .calls_memory_search == false
    and .runs_biocortex == false
    and .registers_embedding_backend == false
    and .changes_memory_search_order == false
    and .default_search_order_change_allowed == false
    and .default_calls_unchanged == true
    and .raw_queries_included == false
    and .raw_keys_included == false
    and .content_included == false
    and .side_signal_raw_included == false
' "$opt_in_expanded_evidence_summary" >/dev/null
if grep -q 'axonalpha\|axonbeta\|axongamma\|axondelta\|axonepsilon\|axonzeta\|dendritealpha\|dendritebeta\|dendritegamma\|dendritedelta\|dendriteepsilon\|dendritezeta\|gliaalph\|gliabet\|gliagam\|gliadel\|gliaeps\|gliazet\|myelinalpha\|myelinbeta\|myelingamma\|myelindelta\|myelinepsilon\|myelinzeta\|synapsealpha\|synapsebeta\|synapsegamma\|synapsedelta\|synapseepsilon\|synapsezeta\|expanded_corpus_baseline_focus\|expanded_corpus_target_span\|baseline focus\|target span\|biocortex opt-in runtime adapter\|runtime influence decision packet\|memory search baseline recall\|redacted order artifact movement\|agent bridge mcp tool registry\|agent bridge mcp\|verify_runtime_trial_secret_key\|verify runtime trial secret content' "$opt_in_expanded_evidence_summary"; then
    echo "opt-in expanded evidence summary leaked raw query/key/content data" >&2
    exit 1
fi

opt_in_redacted_evidence_aggregate="$tmpdir/opt-in-redacted-evidence-aggregate.json"
run cargo run -p ab-bridge --no-default-features --features biocortex-retrieval-opt-in -- \
    bio-cortex retrieval-opt-in-redacted-evidence-aggregate \
    --movement-fixture-run-json "$opt_in_controlled_order" \
    --coverage-fixture-run-json "$opt_in_expanded_corpus" \
    --reviewer verify-bundle \
    --commit verify-dry-run-commit \
    --forum-post-id verify-forum-post \
    --memory-key verify-memory-key \
    --json > "$opt_in_redacted_evidence_aggregate"
jq -e '
    .schema == "agent_bridge.biocortex_retrieval.opt_in_redacted_evidence_aggregate.v0"
    and .read_only == true
    and .redacted_evidence_aggregate == true
    and .implementation_stage == "post_runtime_redacted_evidence_aggregate"
    and .authorization_scope == "explicit_opt_in_fts_runtime_influence"
    and .input_contract.movement_fixture_run_schema == "agent_bridge.biocortex_retrieval.opt_in_controlled_order_fixture_run.v0"
    and .input_contract.coverage_fixture_run_schema == "agent_bridge.biocortex_retrieval.opt_in_controlled_order_fixture_run.v0"
    and .input_contract.movement_fixture_run_included == false
    and .input_contract.coverage_fixture_run_included == false
    and .input_contract.raw_queries_included == false
    and .input_contract.raw_keys_included == false
    and .input_contract.content_included == false
    and .input_contract.side_signal_raw_included == false
    and .movement_evidence.schema_ok == true
    and .movement_evidence.expected_met == true
    and .movement_evidence.seeded_memory_count == 2
    and .movement_evidence.query_count == 1
    and .movement_evidence.adapter_allowed_count == 1
    and .movement_evidence.side_signal_ok_count == 1
    and .movement_evidence.experimental_source_count == 1
    and .movement_evidence.actual_order_changed_count == 1
    and .movement_evidence.raw_flags_all_false == true
    and .movement_evidence.movement_observed == true
    and .movement_evidence.expanded_coverage_observed == false
    and .coverage_evidence.schema_ok == true
    and .coverage_evidence.expected_met == true
    and .coverage_evidence.seeded_memory_count == 10
    and .coverage_evidence.query_count == 5
    and .coverage_evidence.adapter_allowed_count == 5
    and .coverage_evidence.side_signal_ok_count == 5
    and .coverage_evidence.experimental_source_count == 5
    and .coverage_evidence.actual_order_changed_count == 0
    and .coverage_evidence.hash_matches_baseline_count == 5
    and .coverage_evidence.raw_flags_all_false == true
    and .coverage_evidence.movement_observed == false
    and .coverage_evidence.expanded_coverage_observed == true
    and .interpretation.movement_redacted_evidence_ready == true
    and .interpretation.expanded_coverage_redacted_evidence_ready == true
    and .interpretation.runtime_adapter_connection_evidence == true
    and .interpretation.controlled_rank_movement_observed == true
    and .interpretation.expanded_coverage_without_additional_movement == true
    and .interpretation.aggregate_evidence_ready == true
    and .interpretation.default_influence_ready == false
    and .interpretation.human_review_required == true
    and .interpretation.recommended_next_step == "prepare_human_runtime_influence_review_request"
    and .interpretation.review_state == "redacted_aggregate_ready"
    and .approval_state == "evidence_aggregate_only"
    and .authorization_state == "does_not_grant_runtime_influence"
    and .approval_writes_allowed == false
    and .writes_approval == false
    and .calls_memory_search == false
    and .runs_biocortex == false
    and .registers_embedding_backend == false
    and .changes_memory_search_order == false
    and .default_search_order_change_allowed == false
    and .default_calls_unchanged == true
    and .raw_queries_included == false
    and .raw_keys_included == false
    and .content_included == false
    and .side_signal_raw_included == false
' "$opt_in_redacted_evidence_aggregate" >/dev/null
if grep -q 'cortexdelta\|cortexepsilon\|cortexzeta\|cortexeta\|cortextheta\|cortexiota\|controlled_order_baseline_high\|controlled_order_biocortex_target\|target anchor\|baseline anchor\|axonalpha\|axonbeta\|axongamma\|axondelta\|axonepsilon\|axonzeta\|dendritealpha\|dendritebeta\|dendritegamma\|dendritedelta\|dendriteepsilon\|dendritezeta\|gliaalph\|gliabet\|gliagam\|gliadel\|gliaeps\|gliazet\|myelinalpha\|myelinbeta\|myelingamma\|myelindelta\|myelinepsilon\|myelinzeta\|synapsealpha\|synapsebeta\|synapsegamma\|synapsedelta\|synapseepsilon\|synapsezeta\|expanded_corpus_baseline_focus\|expanded_corpus_target_span\|baseline focus\|target span\|biocortex opt-in runtime adapter\|runtime influence decision packet\|memory search baseline recall\|redacted order artifact movement\|agent bridge mcp tool registry\|agent bridge mcp\|verify_runtime_trial_secret_key\|verify runtime trial secret content' "$opt_in_redacted_evidence_aggregate"; then
    echo "opt-in redacted evidence aggregate leaked raw query/key/content data" >&2
    exit 1
fi

opt_in_runtime_influence_review_request_with_aggregate="$tmpdir/opt-in-runtime-influence-review-request-with-aggregate.json"
run cargo run -p ab-bridge --no-default-features -- \
    bio-cortex retrieval-opt-in-runtime-influence-review-request \
    --post-implementation-review-gate-json "$opt_in_post_implementation_review_gate" \
    --redacted-order-artifact-json "$opt_in_redacted_order_artifact" \
    --redacted-evidence-aggregate-json "$opt_in_redacted_evidence_aggregate" \
    --reviewer verify-bundle \
    --commit verify-dry-run-commit \
    --forum-post-id verify-forum-post \
    --memory-key verify-memory-key \
    --json > "$opt_in_runtime_influence_review_request_with_aggregate"
jq -e '
    .schema == "agent_bridge.biocortex_retrieval.opt_in_runtime_influence_review_request.v0"
    and .read_only == true
    and .runtime_influence_review_request == true
    and .implementation_stage == "runtime_influence_review_request_only"
    and .input_contract.post_implementation_review_gate_schema == "agent_bridge.biocortex_retrieval.opt_in_post_implementation_review_gate.v0"
    and .input_contract.redacted_order_artifact_schema == "agent_bridge.biocortex_retrieval.opt_in_redacted_order_artifact.v0"
    and .input_contract.redacted_evidence_aggregate_schema == "agent_bridge.biocortex_retrieval.opt_in_redacted_evidence_aggregate.v0"
    and .input_contract.accepts_optional_redacted_evidence_aggregate == true
    and .input_contract.requires_aggregate_ready_when_provided == true
    and .input_contract.post_implementation_review_gate_included == false
    and .input_contract.redacted_order_artifact_included == false
    and .input_contract.redacted_evidence_aggregate_included == false
    and .input_contract.raw_query_included == false
    and .input_contract.raw_keys_included == false
    and .input_contract.content_included == false
    and .requested_authorization.accepts_redacted_evidence_aggregate == true
    and .requested_authorization.requires_redacted_evidence_aggregate == false
    and .requested_authorization.this_packet_grants_request == false
    and .evidence_summary.post_implementation_gate_ready == true
    and .evidence_summary.redacted_order_artifact_ready == true
    and .evidence_summary.redacted_evidence_aggregate_provided == true
    and .evidence_summary.redacted_evidence_aggregate_ready == true
    and .evidence_summary.aggregate_review_state == "redacted_aggregate_ready"
    and .evidence_summary.controlled_rank_movement_observed == true
    and .evidence_summary.expanded_coverage_without_additional_movement == true
    and .evidence_summary.aggregate_default_influence_ready == false
    and .evidence_summary.default_influence_ready == false
    and .evidence_summary.aggregate_human_review_required == true
    and .evidence_summary.redacted_evidence_aggregate_summary_included == false
    and .evidence_summary.runtime_adapter_approved == false
    and .evidence_summary.default_search_order_change_allowed == false
    and .evidence_summary.ordering_behavior_connected == false
    and .boundary_check.runtime_influence_review_request_ready == true
    and (.boundary_check.blockers | length) == 0
    and .boundary_check.redacted_evidence_aggregate_provided == true
    and .boundary_check.redacted_evidence_aggregate_ready == true
    and .boundary_check.aggregate_schema_ok == true
    and .boundary_check.aggregate_safe_for_review == true
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
' "$opt_in_runtime_influence_review_request_with_aggregate" >/dev/null
if grep -q 'cortexdelta\|cortexepsilon\|cortexzeta\|cortexeta\|cortextheta\|cortexiota\|controlled_order_baseline_high\|controlled_order_biocortex_target\|target anchor\|baseline anchor\|axonalpha\|axonbeta\|axongamma\|axondelta\|axonepsilon\|axonzeta\|dendritealpha\|dendritebeta\|dendritegamma\|dendritedelta\|dendriteepsilon\|dendritezeta\|gliaalph\|gliabet\|gliagam\|gliadel\|gliaeps\|gliazet\|myelinalpha\|myelinbeta\|myelingamma\|myelindelta\|myelinepsilon\|myelinzeta\|synapsealpha\|synapsebeta\|synapsegamma\|synapsedelta\|synapseepsilon\|synapsezeta\|expanded_corpus_baseline_focus\|expanded_corpus_target_span\|baseline focus\|target span\|biocortex opt-in runtime adapter\|runtime influence decision packet\|memory search baseline recall\|redacted order artifact movement\|agent bridge mcp tool registry\|agent bridge mcp\|verify_runtime_trial_secret_key\|verify runtime trial secret content' "$opt_in_runtime_influence_review_request_with_aggregate"; then
    echo "opt-in aggregate-backed runtime influence review request leaked raw query/key/content data" >&2
    exit 1
fi

opt_in_runtime_influence_decision_packet_with_aggregate="$tmpdir/opt-in-runtime-influence-decision-packet-with-aggregate.json"
run cargo run -p ab-bridge --no-default-features -- \
    bio-cortex retrieval-opt-in-runtime-influence-decision-packet \
    --runtime-influence-review-request-json "$opt_in_runtime_influence_review_request_with_aggregate" \
    --runtime-influence-decision-json "$opt_in_runtime_influence_decision" \
    --reviewer verify-bundle \
    --commit verify-dry-run-commit \
    --forum-post-id verify-forum-post \
    --memory-key verify-memory-key \
    --json > "$opt_in_runtime_influence_decision_packet_with_aggregate"
jq -e '
    .schema == "agent_bridge.biocortex_retrieval.opt_in_runtime_influence_decision_packet.v0"
    and .read_only == true
    and .runtime_influence_decision_consumer == true
    and .implementation_stage == "runtime_influence_decision_consumer_only"
    and .authorization_scope == "explicit_opt_in_fts_runtime_influence"
    and .input_contract.runtime_influence_review_request_included == false
    and .input_contract.runtime_influence_decision_included == false
    and .input_contract.accepts_aggregate_backed_review_request == true
    and .input_contract.requires_aggregate_ready_when_provided == true
    and .input_contract.redacted_evidence_aggregate_included == false
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
    and .request_summary.aggregate_backed_review_request == true
    and .request_summary.aggregate_review_evidence_state == "redacted_aggregate_ready"
    and .request_summary.redacted_evidence_aggregate_provided == true
    and .request_summary.redacted_evidence_aggregate_ready == true
    and .request_summary.aggregate_review_state == "redacted_aggregate_ready"
    and .request_summary.controlled_rank_movement_observed == true
    and .request_summary.expanded_coverage_without_additional_movement == true
    and .request_summary.aggregate_default_influence_ready == false
    and .request_summary.default_influence_ready == false
    and .request_summary.aggregate_human_review_required == true
    and .request_summary.redacted_evidence_aggregate_summary_included == false
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
    and .boundary_check.aggregate_backed_review_request == true
    and .boundary_check.aggregate_review_evidence_ready == true
    and .boundary_check.legacy_review_request_without_aggregate_allowed == false
    and .boundary_check.aggregate_contract_ok == true
    and .boundary_check.aggregate_summary_redacted == true
    and .boundary_check.aggregate_safe_for_decision == true
    and .boundary_check.aggregate_default_influence_still_not_ready == true
    and .boundary_check.aggregate_human_review_required == true
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
' "$opt_in_runtime_influence_decision_packet_with_aggregate" >/dev/null
if grep -q 'cortexdelta\|cortexepsilon\|cortexzeta\|cortexeta\|cortextheta\|cortexiota\|controlled_order_baseline_high\|controlled_order_biocortex_target\|target anchor\|baseline anchor\|axonalpha\|axonbeta\|axongamma\|axondelta\|axonepsilon\|axonzeta\|dendritealpha\|dendritebeta\|dendritegamma\|dendritedelta\|dendriteepsilon\|dendritezeta\|gliaalph\|gliabet\|gliagam\|gliadel\|gliaeps\|gliazet\|myelinalpha\|myelinbeta\|myelingamma\|myelindelta\|myelinepsilon\|myelinzeta\|synapsealpha\|synapsebeta\|synapsegamma\|synapsedelta\|synapseepsilon\|synapsezeta\|expanded_corpus_baseline_focus\|expanded_corpus_target_span\|baseline focus\|target span\|biocortex opt-in runtime adapter\|runtime influence decision packet\|memory search baseline recall\|redacted order artifact movement\|agent bridge mcp tool registry\|agent bridge mcp\|verify runtime influence decision secret wording\|verify runtime influence decision secret query\|verify_runtime_influence_decision_secret_key\|verify runtime influence decision secret content\|verify_runtime_trial_secret_key\|verify runtime trial secret content' "$opt_in_runtime_influence_decision_packet_with_aggregate"; then
    echo "opt-in aggregate-backed runtime influence decision packet leaked raw query/key/content data" >&2
    exit 1
fi

opt_in_store_trial_empty_with_aggregate="$tmpdir/opt-in-store-trial-empty-with-aggregate.json"
run env AGENT_BRIDGE_DB="$tmpdir/opt-in-store-trial-empty-with-aggregate.db" \
    AB_BIOCORTEX_RETRIEVAL_OPT_IN=1 \
    cargo run -p ab-bridge --no-default-features --features biocortex-retrieval-opt-in -- \
    bio-cortex retrieval-opt-in-store-trial \
    --runtime-influence-decision-packet-json "$opt_in_runtime_influence_decision_packet_with_aggregate" \
    --query "verify aggregate-backed store trial ready secret query" \
    --per-call-opt-in \
    --checkout "$biocortex_rs" \
    --limit 3 \
    --attempt-id verify-store-trial-empty-with-aggregate \
    --commit verify-dry-run-commit \
    --json > "$opt_in_store_trial_empty_with_aggregate"
jq -e '
    .schema == "agent_bridge.biocortex_retrieval.opt_in_store_trial.v0"
    and .input_contract.accepts_aggregate_backed_decision_packet == true
    and .input_contract.requires_aggregate_ready_when_provided == true
    and .input_contract.redacted_evidence_aggregate_included == false
    and .input_contract.aggregate_evidence_summary_included == false
    and .runtime_preflight.compile_feature_enabled == true
    and .runtime_preflight.runtime_enabled == true
    and .runtime_preflight.operator_disabled == false
    and .runtime_preflight.decision_packet_authorized == true
    and .runtime_preflight.decision_packet_aggregate_backed == true
    and .runtime_preflight.decision_packet_aggregate_review_evidence_ready == true
    and .runtime_preflight.legacy_decision_packet_without_aggregate_allowed == false
    and .runtime_preflight.decision_packet_aggregate_contract_ok == true
    and .runtime_preflight.decision_packet_aggregate_summary_redacted == true
    and .runtime_preflight.decision_packet_aggregate_safe_for_trial == true
    and .runtime_preflight.decision_packet_aggregate_review_evidence_state == "redacted_aggregate_ready"
    and .runtime_preflight.decision_packet_aggregate_default_influence_ready == false
    and .runtime_preflight.decision_packet_aggregate_human_review_required == true
    and .runtime_preflight.adapter_allowed == false
    and (.runtime_preflight.blockers | index("baseline_empty"))
    and .side_signal.attempted == false
    and .runs_biocortex == false
    and .raw_query_included == false
    and .raw_keys_included == false
    and .content_included == false
    and .default_search_order_change_allowed == false
    and .default_calls_unchanged == true
' "$opt_in_store_trial_empty_with_aggregate" >/dev/null
if grep -q 'verify aggregate-backed store trial ready secret query\|cortexdelta\|axonalpha\|expanded_corpus_baseline_focus\|verify_runtime_trial_secret_key\|verify runtime trial secret content' "$opt_in_store_trial_empty_with_aggregate"; then
    echo "opt-in aggregate-backed store trial empty path leaked raw query/key/content data" >&2
    exit 1
fi

opt_in_batch_diagnostics_empty_with_aggregate="$tmpdir/opt-in-batch-diagnostics-empty-with-aggregate.json"
run env AGENT_BRIDGE_DB="$tmpdir/opt-in-batch-diagnostics-empty-with-aggregate.db" \
    AB_BIOCORTEX_RETRIEVAL_OPT_IN=1 \
    cargo run -p ab-bridge --no-default-features --features biocortex-retrieval-opt-in -- \
    bio-cortex retrieval-opt-in-batch-diagnostics \
    --runtime-influence-decision-packet-json "$opt_in_runtime_influence_decision_packet_with_aggregate" \
    --query-cases-json "$opt_in_batch_query_cases" \
    --per-call-opt-in \
    --checkout "$biocortex_rs" \
    --limit 3 \
    --attempt-id verify-batch-diagnostics-empty-with-aggregate \
    --commit verify-dry-run-commit \
    --json > "$opt_in_batch_diagnostics_empty_with_aggregate"
jq -e '
    .schema == "agent_bridge.biocortex_retrieval.opt_in_batch_diagnostics.v0"
    and .input_contract.accepts_aggregate_backed_decision_packet == true
    and .input_contract.requires_aggregate_ready_when_provided == true
    and .input_contract.redacted_evidence_aggregate_included == false
    and .input_contract.aggregate_evidence_summary_included == false
    and .summary.query_count == 6
    and .summary.baseline_completed_count == 6
    and .summary.baseline_empty_count == 6
    and .summary.adapter_allowed_count == 0
    and .summary.side_signal_attempted_count == 0
    and .summary.runs_biocortex_count == 0
    and ([.query_results[].preflight.decision_packet_authorized] | unique) == [true]
    and ([.query_results[].preflight.decision_packet_aggregate_backed] | unique) == [true]
    and ([.query_results[].preflight.decision_packet_aggregate_review_evidence_ready] | unique) == [true]
    and ([.query_results[].preflight.legacy_decision_packet_without_aggregate_allowed] | unique) == [false]
    and ([.query_results[].preflight.decision_packet_aggregate_safe_for_trial] | unique) == [true]
    and ([.query_results[].preflight.adapter_allowed] | unique) == [false]
    and ([.query_results[].side_signal.attempted] | unique) == [false]
    and ([.query_results[].runs_biocortex] | unique) == [false]
    and .safety.calls_memory_search_all == true
    and .safety.runs_biocortex_any == false
    and .safety.raw_flags_all_false == true
    and .default_search_order_change_allowed == false
    and .default_calls_unchanged == true
' "$opt_in_batch_diagnostics_empty_with_aggregate" >/dev/null
if grep -q 'biocortex opt-in runtime adapter\|runtime influence decision packet\|memory search baseline recall\|redacted order artifact movement\|agent bridge mcp tool registry\|agent bridge mcp\|verify runtime influence decision secret wording\|verify runtime influence decision secret query\|verify_runtime_influence_decision_secret_key\|verify runtime influence decision secret content\|verify_runtime_trial_secret_key\|verify runtime trial secret content' "$opt_in_batch_diagnostics_empty_with_aggregate"; then
    echo "opt-in aggregate-backed batch diagnostics empty path leaked raw query/key/content data" >&2
    exit 1
fi

opt_in_runtime_readiness_packet="$tmpdir/opt-in-runtime-readiness-packet.json"
run cargo run -p ab-bridge --no-default-features -- \
    bio-cortex retrieval-opt-in-runtime-readiness-packet \
    --runtime-influence-decision-packet-json "$opt_in_runtime_influence_decision_packet_with_aggregate" \
    --store-trial-json "$opt_in_store_trial_empty_with_aggregate" \
    --batch-diagnostics-json "$opt_in_batch_diagnostics_empty_with_aggregate" \
    --reviewer verify-bundle \
    --commit verify-dry-run-commit \
    --forum-post-id verify-forum-post \
    --memory-key verify-memory-key \
    --json > "$opt_in_runtime_readiness_packet"
jq -e '
    .schema == "agent_bridge.biocortex_retrieval.opt_in_runtime_readiness_packet.v0"
    and .read_only == true
    and .runtime_readiness_packet == true
    and .implementation_stage == "controlled_opt_in_runtime_readiness_packet"
    and .input_contract.runtime_influence_decision_packet_included == false
    and .input_contract.store_trial_included == false
    and .input_contract.batch_diagnostics_included == false
    and .input_contract.batch_diagnostics_evidence_source == "store_opt_in_batch_diagnostics"
    and .input_contract.batch_diagnostics_transition_gated == false
    and .input_contract.requires_aggregate_backed_decision_packet == true
    and .input_contract.requires_downstream_aggregate_preflight == true
    and .input_contract.raw_queries_included == false
    and .input_contract.raw_keys_included == false
    and .input_contract.content_included == false
    and .input_contract.side_signal_raw_included == false
    and .input_contract.human_decision_text_included == false
    and .decision_summary.runtime_influence_authorized == true
    and .decision_summary.aggregate_backed_review_request == true
    and .decision_summary.aggregate_review_evidence_ready == true
    and .decision_summary.aggregate_safe_for_decision == true
    and .decision_summary.aggregate_default_influence_ready == false
    and .decision_summary.aggregate_human_review_required == true
    and .store_trial_summary.aggregate_preflight_ok == true
    and .store_trial_summary.preflight_acceptable == true
    and .store_trial_summary.blockers == ["baseline_empty"]
    and .store_trial_summary.blockers_without_live_data == []
    and .batch_summary.aggregate_preflight_ok == true
    and .batch_summary.preflight_acceptable == true
    and .batch_summary.evidence_source == "store_opt_in_batch_diagnostics"
    and .batch_summary.transition_gated == false
    and .batch_summary.legacy_schema_ok == true
    and .batch_summary.gated_schema_ok == false
    and .batch_summary.transition_gate_ok == true
    and .batch_summary.query_count == 6
    and .batch_summary.baseline_empty_count == 6
    and .batch_summary.adapter_allowed_count == 0
    and .batch_summary.side_signal_ok_count == 0
    and .readiness.control_plane_ready == true
    and .readiness.live_probe_state == "control_plane_ready_no_live_candidates"
    and .readiness.live_probe_has_candidates == false
    and .readiness.live_order_influence_ready == false
    and .readiness.may_accept_controlled_explicit_opt_in_fts_calls == true
    and .readiness.may_change_default_memory_search_order == false
    and .readiness.default_influence_ready == false
    and .boundary_check.runtime_readiness_ready == true
    and .boundary_check.blockers == []
    and .boundary_check.this_packet_grants_new_authorization == false
    and .boundary_check.this_packet_changes_return_order == false
    and .boundary_check.this_packet_allows_default_search_order_change == false
    and .approval_state == "runtime_readiness_only"
    and .approval_writes_allowed == false
    and .writes_approval == false
    and .calls_memory_search == false
    and .runs_biocortex == false
    and .registers_embedding_backend == false
    and .changes_memory_search_order == false
    and .default_search_order_change_allowed == false
    and .default_calls_unchanged == true
    and .raw_queries_included == false
    and .raw_keys_included == false
    and .content_included == false
    and .side_signal_raw_included == false
' "$opt_in_runtime_readiness_packet" >/dev/null
if grep -q 'verify aggregate-backed store trial ready secret query\|biocortex opt-in runtime adapter\|runtime influence decision packet\|memory search baseline recall\|redacted order artifact movement\|agent bridge mcp tool registry\|agent bridge mcp\|verify runtime influence decision secret wording\|verify runtime influence decision secret query\|verify_runtime_influence_decision_secret_key\|verify runtime influence decision secret content\|verify_runtime_trial_secret_key\|verify runtime trial secret content' "$opt_in_runtime_readiness_packet"; then
    echo "opt-in runtime readiness packet leaked raw query/key/content data" >&2
    exit 1
fi

opt_in_runtime_transition_gate="$tmpdir/opt-in-runtime-transition-gate.json"
run cargo run -p ab-bridge --no-default-features -- \
    bio-cortex retrieval-opt-in-runtime-transition-gate \
    --runtime-readiness-packet-json "$opt_in_runtime_readiness_packet" \
    --mode fts \
    --per-call-opt-in \
    --reviewer verify-bundle \
    --commit verify-dry-run-commit \
    --forum-post-id verify-forum-post \
    --memory-key verify-memory-key \
    --json > "$opt_in_runtime_transition_gate"
jq -e '
    .schema == "agent_bridge.biocortex_retrieval.opt_in_runtime_transition_gate.v0"
    and .read_only == true
    and .runtime_transition_gate == true
    and .implementation_stage == "readiness_gated_runtime_transition_gate"
    and .status == "transition_allowed"
    and .input_contract.runtime_readiness_packet_included == false
    and .input_contract.requires_runtime_readiness_packet == true
    and .input_contract.requires_control_plane_ready == true
    and .input_contract.requires_per_call_opt_in == true
    and .input_contract.requires_mode_fts == true
    and .input_contract.requires_operator_disable_absent == true
    and .input_contract.raw_queries_included == false
    and .input_contract.raw_keys_included == false
    and .input_contract.content_included == false
    and .input_contract.side_signal_raw_included == false
    and .input_contract.human_decision_text_included == false
    and .requested_transition.mode == "fts"
    and .requested_transition.mode_authorized == true
    and .requested_transition.per_call_opt_in == true
    and .requested_transition.operator_disabled == false
    and .requested_transition.default_search_order_change_requested == false
    and .requested_transition.hybrid_retrieval_influence_requested == false
    and .requested_transition.semantic_retrieval_influence_requested == false
    and .readiness_summary.control_plane_ready == true
    and .readiness_summary.may_accept_controlled_explicit_opt_in_fts_calls == true
    and .readiness_summary.live_probe_state == "control_plane_ready_no_live_candidates"
    and .readiness_summary.default_influence_ready == false
    and .readiness_summary.boundary_ready == true
    and .readiness_summary.readiness_blockers == []
    and .readiness_summary.raw_inputs_absent == true
    and .readiness_summary.side_effects_absent == true
    and .transition.transition_allowed == true
    and .transition.may_call_controlled_store_trial == true
    and .transition.may_run_runtime_adapter_for_explicit_opt_in_fts == true
    and .transition.may_connect_ordering_behavior_for_explicit_opt_in_fts == true
    and .transition.may_affect_only_explicitly_opted_in_fts_calls == true
    and .transition.must_keep_operator_disable == "AB_BIOCORTEX_RETRIEVAL_DISABLE"
    and .transition.must_return_baseline_without_per_call_opt_in == true
    and .transition.must_fail_open_to_baseline == true
    and .transition.must_keep_redacted_audit_only == true
    and .transition.must_keep_baseline_candidate_recall == true
    and .transition.may_change_default_memory_search_order == false
    and .transition.default_influence_ready == false
    and .boundary_check.runtime_transition_allowed == true
    and .boundary_check.blockers == []
    and .boundary_check.this_packet_grants_new_authorization == false
    and .boundary_check.this_packet_calls_memory_search == false
    and .boundary_check.this_packet_runs_biocortex == false
    and .boundary_check.this_packet_changes_return_order == false
    and .boundary_check.this_packet_allows_default_search_order_change == false
    and .approval_state == "runtime_transition_gate_only"
    and .approval_writes_allowed == false
    and .writes_approval == false
    and .calls_memory_search == false
    and .runs_biocortex == false
    and .registers_embedding_backend == false
    and .changes_memory_search_order == false
    and .default_search_order_change_allowed == false
    and .default_calls_unchanged == true
    and .raw_queries_included == false
    and .raw_keys_included == false
    and .content_included == false
    and .side_signal_raw_included == false
' "$opt_in_runtime_transition_gate" >/dev/null
if grep -q 'verify aggregate-backed store trial ready secret query\|biocortex opt-in runtime adapter\|runtime influence decision packet\|memory search baseline recall\|redacted order artifact movement\|agent bridge mcp tool registry\|agent bridge mcp\|verify runtime influence decision secret wording\|verify runtime influence decision secret query\|verify_runtime_influence_decision_secret_key\|verify runtime influence decision secret content\|verify_runtime_trial_secret_key\|verify runtime trial secret content' "$opt_in_runtime_transition_gate"; then
    echo "opt-in runtime transition gate leaked raw query/key/content data" >&2
    exit 1
fi

opt_in_runtime_transition_gate_blocked="$tmpdir/opt-in-runtime-transition-gate-blocked.json"
run cargo run -p ab-bridge --no-default-features -- \
    bio-cortex retrieval-opt-in-runtime-transition-gate \
    --runtime-readiness-packet-json "$opt_in_runtime_readiness_packet" \
    --mode hybrid \
    --operator-disabled \
    --json > "$opt_in_runtime_transition_gate_blocked"
jq -e '
    .schema == "agent_bridge.biocortex_retrieval.opt_in_runtime_transition_gate.v0"
    and .status == "blocked"
    and .requested_transition.mode == "hybrid"
    and .requested_transition.mode_authorized == false
    and .requested_transition.per_call_opt_in == false
    and .requested_transition.operator_disabled == true
    and .requested_transition.hybrid_retrieval_influence_requested == true
    and .requested_transition.semantic_retrieval_influence_requested == false
    and .transition.transition_allowed == false
    and .boundary_check.runtime_transition_allowed == false
    and (.boundary_check.blockers | index("requested_mode_not_authorized"))
    and (.boundary_check.blockers | index("per_call_opt_in_missing"))
    and (.boundary_check.blockers | index("operator_disabled"))
    and .calls_memory_search == false
    and .runs_biocortex == false
    and .changes_memory_search_order == false
    and .default_search_order_change_allowed == false
' "$opt_in_runtime_transition_gate_blocked" >/dev/null

opt_in_gated_store_trial_empty_with_aggregate="$tmpdir/opt-in-gated-store-trial-empty-with-aggregate.json"
run env AGENT_BRIDGE_DB="$tmpdir/opt-in-gated-store-trial-empty-with-aggregate.db" \
    AB_BIOCORTEX_RETRIEVAL_OPT_IN=1 \
    cargo run -p ab-bridge --no-default-features --features biocortex-retrieval-opt-in -- \
    bio-cortex retrieval-opt-in-gated-store-trial \
    --runtime-transition-gate-json "$opt_in_runtime_transition_gate" \
    --runtime-influence-decision-packet-json "$opt_in_runtime_influence_decision_packet_with_aggregate" \
    --query "verify gated store trial allowed secret query" \
    --per-call-opt-in \
    --checkout "$biocortex_rs" \
    --limit 3 \
    --attempt-id verify-gated-store-trial-empty-with-aggregate \
    --commit verify-dry-run-commit \
    --json > "$opt_in_gated_store_trial_empty_with_aggregate"
jq -e '
    .schema == "agent_bridge.biocortex_retrieval.opt_in_gated_store_trial.v0"
    and .gated_store_trial == true
    and .implementation_stage == "runtime_transition_gated_store_trial"
    and .status == "transition_gate_consumed"
    and .input_contract.runtime_transition_gate_included == false
    and .input_contract.runtime_influence_decision_packet_included == false
    and .input_contract.store_trial_included == false
    and .input_contract.requires_transition_gate_allowed == true
    and .input_contract.raw_query_included == false
    and .input_contract.raw_keys_included == false
    and .input_contract.content_included == false
    and .runtime_transition_preflight.transition_gate_allowed == true
    and .runtime_transition_preflight.blockers == []
    and .runtime_transition_preflight.gate_may_call_controlled_store_trial == true
    and .runtime_transition_preflight.gate_may_run_runtime_adapter_for_explicit_opt_in_fts == true
    and .runtime_transition_preflight.gate_may_connect_ordering_behavior_for_explicit_opt_in_fts == true
    and .runtime_transition_preflight.operator_disabled_now == false
    and .runtime_transition_preflight.query_present == true
    and .store_trial_called == true
    and .store_trial_summary.schema == "agent_bridge.biocortex_retrieval.opt_in_store_trial.v0"
    and .store_trial_summary.status == "baseline_returned"
    and .store_trial_summary.runtime_adapter_allowed == false
    and .store_trial_summary.runtime_preflight_blocker_count == 1
    and .store_trial_summary.compile_feature_enabled == true
    and .store_trial_summary.runtime_enabled == true
    and .store_trial_summary.operator_disabled == false
    and .store_trial_summary.decision_packet_authorized == true
    and .store_trial_summary.baseline_completed == true
    and .store_trial_summary.baseline_key_count == 0
    and .store_trial_summary.side_signal_attempted == false
    and .store_trial_summary.store_wrapper_called == true
    and .store_trial_summary.store_trial_included == false
    and .calls_memory_search == true
    and .runs_biocortex == false
    and .changes_memory_search_order == false
    and .default_search_order_change_allowed == false
    and .default_calls_unchanged == true
    and .raw_query_included == false
    and .raw_keys_included == false
    and .content_included == false
    and .side_signal_raw_included == false
    and .boundary.gate_consumed == true
    and .boundary.calls_memory_search == true
' "$opt_in_gated_store_trial_empty_with_aggregate" >/dev/null
if grep -q 'verify gated store trial allowed secret query\|verify aggregate-backed store trial ready secret query\|cortexdelta\|axonalpha\|expanded_corpus_baseline_focus\|verify_runtime_trial_secret_key\|verify runtime trial secret content' "$opt_in_gated_store_trial_empty_with_aggregate"; then
    echo "opt-in gated store trial allowed path leaked raw query/key/content data" >&2
    exit 1
fi

opt_in_gated_store_trial_blocked="$tmpdir/opt-in-gated-store-trial-blocked.json"
run env AGENT_BRIDGE_DB="$tmpdir/opt-in-gated-store-trial-blocked.db" \
    cargo run -p ab-bridge --no-default-features -- \
    bio-cortex retrieval-opt-in-gated-store-trial \
    --runtime-transition-gate-json "$opt_in_runtime_transition_gate_blocked" \
    --runtime-influence-decision-packet-json "$opt_in_runtime_influence_decision_packet_with_aggregate" \
    --query "verify gated store trial blocked secret query" \
    --mode hybrid \
    --json > "$opt_in_gated_store_trial_blocked"
jq -e '
    .schema == "agent_bridge.biocortex_retrieval.opt_in_gated_store_trial.v0"
    and .status == "transition_gate_blocked"
    and .runtime_transition_preflight.transition_gate_allowed == false
    and (.runtime_transition_preflight.blockers | index("transition_gate_status_not_allowed"))
    and (.runtime_transition_preflight.blockers | index("transition_gate_boundary_not_allowed"))
    and (.runtime_transition_preflight.blockers | index("transition_gate_boundary_has_blockers"))
    and (.runtime_transition_preflight.blockers | index("transition_gate_transition_not_allowed"))
    and (.runtime_transition_preflight.blockers | index("transition_gate_may_not_call_store_trial"))
    and (.runtime_transition_preflight.blockers | index("transition_gate_mode_not_authorized"))
    and (.runtime_transition_preflight.blockers | index("mode_not_authorized"))
    and (.runtime_transition_preflight.blockers | index("per_call_opt_in_missing"))
    and .store_trial_called == false
    and .calls_memory_search == false
    and .runs_biocortex == false
    and .changes_memory_search_order == false
    and .default_search_order_change_allowed == false
    and .default_calls_unchanged == true
    and .raw_query_included == false
    and .raw_keys_included == false
    and .content_included == false
    and .side_signal_raw_included == false
    and .boundary.gate_consumed == false
    and .boundary.calls_memory_search == false
' "$opt_in_gated_store_trial_blocked" >/dev/null
if grep -q 'verify gated store trial blocked secret query\|verify aggregate-backed store trial ready secret query\|cortexdelta\|axonalpha\|expanded_corpus_baseline_focus\|verify_runtime_trial_secret_key\|verify runtime trial secret content' "$opt_in_gated_store_trial_blocked"; then
    echo "opt-in gated store trial blocked path leaked raw query/key/content data" >&2
    exit 1
fi

opt_in_gated_batch_diagnostics_empty_with_aggregate="$tmpdir/opt-in-gated-batch-diagnostics-empty-with-aggregate.json"
run env AGENT_BRIDGE_DB="$tmpdir/opt-in-gated-batch-diagnostics-empty-with-aggregate.db" \
    AB_BIOCORTEX_RETRIEVAL_OPT_IN=1 \
    cargo run -p ab-bridge --no-default-features --features biocortex-retrieval-opt-in -- \
    bio-cortex retrieval-opt-in-gated-batch-diagnostics \
    --runtime-transition-gate-json "$opt_in_runtime_transition_gate" \
    --runtime-influence-decision-packet-json "$opt_in_runtime_influence_decision_packet_with_aggregate" \
    --query "verify gated batch allowed secret query one" \
    --query-class "allowed one" \
    --query "verify gated batch allowed secret query two" \
    --query-class "allowed two" \
    --per-call-opt-in \
    --checkout "$biocortex_rs" \
    --limit 3 \
    --attempt-id verify-gated-batch-diagnostics-empty-with-aggregate \
    --commit verify-dry-run-commit \
    --json > "$opt_in_gated_batch_diagnostics_empty_with_aggregate"
jq -e '
    .schema == "agent_bridge.biocortex_retrieval.opt_in_gated_batch_diagnostics.v0"
    and .gated_batch_diagnostics == true
    and .implementation_stage == "runtime_transition_gated_batch_diagnostics"
    and .status == "completed"
    and .input_contract.runtime_transition_gate_included == false
    and .input_contract.runtime_influence_decision_packet_included == false
    and .input_contract.requires_transition_gate_allowed == true
    and .input_contract.raw_queries_included == false
    and .input_contract.raw_keys_included == false
    and .input_contract.content_included == false
    and .summary.query_count == 2
    and .summary.transition_gate_allowed_count == 2
    and .summary.transition_gate_blocked_count == 0
    and .summary.store_trial_called_count == 2
    and .summary.calls_memory_search_count == 2
    and .summary.runs_biocortex_count == 0
    and .summary.default_calls_unchanged_count == 2
    and .safety.transition_gate_allowed_all == true
    and .safety.store_trial_called_all == true
    and .safety.calls_memory_search_all == true
    and .safety.runs_biocortex_any == false
    and .safety.raw_flags_all_false == true
    and ([.query_results[].transition_preflight.transition_gate_allowed] | unique) == [true]
    and ([.query_results[].store_trial.called] | unique) == [true]
    and ([.query_results[].calls_memory_search] | unique) == [true]
    and .calls_memory_search == true
    and .runs_biocortex == false
    and .changes_memory_search_order == false
    and .default_search_order_change_allowed == false
    and .default_calls_unchanged == true
    and .raw_queries_included == false
    and .raw_keys_included == false
    and .content_included == false
    and .side_signal_raw_included == false
    and .boundary.gate_consumed == true
    and .boundary.calls_memory_search == true
' "$opt_in_gated_batch_diagnostics_empty_with_aggregate" >/dev/null
if grep -q 'verify gated batch allowed secret query one\|verify gated batch allowed secret query two\|verify gated store trial allowed secret query\|verify aggregate-backed store trial ready secret query\|cortexdelta\|axonalpha\|expanded_corpus_baseline_focus\|verify_runtime_trial_secret_key\|verify runtime trial secret content' "$opt_in_gated_batch_diagnostics_empty_with_aggregate"; then
    echo "opt-in gated batch diagnostics allowed path leaked raw query/key/content data" >&2
    exit 1
fi

opt_in_runtime_readiness_packet_with_gated_batch="$tmpdir/opt-in-runtime-readiness-packet-with-gated-batch.json"
run cargo run -p ab-bridge --no-default-features -- \
    bio-cortex retrieval-opt-in-runtime-readiness-packet \
    --runtime-influence-decision-packet-json "$opt_in_runtime_influence_decision_packet_with_aggregate" \
    --store-trial-json "$opt_in_store_trial_empty_with_aggregate" \
    --batch-diagnostics-json "$opt_in_gated_batch_diagnostics_empty_with_aggregate" \
    --reviewer verify-bundle \
    --commit verify-dry-run-commit \
    --forum-post-id verify-forum-post \
    --memory-key verify-memory-key-gated-batch \
    --json > "$opt_in_runtime_readiness_packet_with_gated_batch"
jq -e '
    .schema == "agent_bridge.biocortex_retrieval.opt_in_runtime_readiness_packet.v0"
    and .read_only == true
    and .runtime_readiness_packet == true
    and .status == "completed"
    and .input_contract.runtime_influence_decision_packet_included == false
    and .input_contract.store_trial_included == false
    and .input_contract.batch_diagnostics_included == false
    and .input_contract.batch_diagnostics_evidence_source == "runtime_transition_gated_batch_diagnostics"
    and .input_contract.batch_diagnostics_transition_gated == true
    and .input_contract.raw_queries_included == false
    and .input_contract.raw_keys_included == false
    and .input_contract.content_included == false
    and .input_contract.side_signal_raw_included == false
    and .batch_summary.schema_ok == true
    and .batch_summary.legacy_schema_ok == false
    and .batch_summary.gated_schema_ok == true
    and .batch_summary.evidence_source == "runtime_transition_gated_batch_diagnostics"
    and .batch_summary.transition_gated == true
    and .batch_summary.transition_gate_ok == true
    and .batch_summary.transition_gate_allowed_count == 2
    and .batch_summary.transition_gate_blocked_count == 0
    and .batch_summary.store_trial_called_count == 2
    and .batch_summary.calls_memory_search_count == 2
    and .batch_summary.aggregate_preflight_ok == true
    and .batch_summary.preflight_acceptable == true
    and .batch_summary.query_count == 2
    and .batch_summary.baseline_empty_count == 2
    and .readiness.control_plane_ready == true
    and .readiness.live_probe_state == "control_plane_ready_no_live_candidates"
    and .readiness.live_order_influence_ready == false
    and .readiness.may_accept_controlled_explicit_opt_in_fts_calls == true
    and .boundary_check.runtime_readiness_ready == true
    and .boundary_check.blockers == []
    and .calls_memory_search == false
    and .runs_biocortex == false
    and .changes_memory_search_order == false
    and .default_search_order_change_allowed == false
    and .default_calls_unchanged == true
    and .raw_queries_included == false
    and .raw_keys_included == false
    and .content_included == false
    and .side_signal_raw_included == false
' "$opt_in_runtime_readiness_packet_with_gated_batch" >/dev/null
if grep -q 'verify gated batch allowed secret query one\|verify gated batch allowed secret query two\|verify gated store trial allowed secret query\|verify aggregate-backed store trial ready secret query\|cortexdelta\|axonalpha\|expanded_corpus_baseline_focus\|verify_runtime_trial_secret_key\|verify runtime trial secret content' "$opt_in_runtime_readiness_packet_with_gated_batch"; then
    echo "opt-in runtime readiness packet with gated batch leaked raw query/key/content data" >&2
    exit 1
fi

opt_in_evidence_summary_with_gated_readiness="$tmpdir/opt-in-evidence-summary-with-gated-readiness.json"
run cargo run -p ab-bridge --no-default-features --features biocortex-retrieval-opt-in -- \
    bio-cortex retrieval-opt-in-evidence-summary \
    --batch-diagnostics-json "$opt_in_gated_batch_diagnostics_empty_with_aggregate" \
    --controlled-order-fixture-run-json "$opt_in_controlled_order" \
    --runtime-readiness-packet-json "$opt_in_runtime_readiness_packet_with_gated_batch" \
    --reviewer verify-bundle \
    --commit verify-dry-run-commit \
    --forum-post-id verify-forum-post \
    --memory-key verify-memory-key-gated-readiness-summary \
    --json > "$opt_in_evidence_summary_with_gated_readiness"
jq -e '
    .schema == "agent_bridge.biocortex_retrieval.opt_in_evidence_summary.v0"
    and .read_only == true
    and .evidence_summary == true
    and .implementation_stage == "post_runtime_evidence_summary"
    and .authorization_scope == "explicit_opt_in_fts_runtime_influence"
    and .input_contract.batch_diagnostics_schema == "agent_bridge.biocortex_retrieval.opt_in_gated_batch_diagnostics.v0"
    and .input_contract.batch_diagnostics_legacy_schema_ok == false
    and .input_contract.batch_diagnostics_gated_schema_ok == true
    and .input_contract.batch_diagnostics_evidence_source == "runtime_transition_gated_batch_diagnostics"
    and .input_contract.batch_diagnostics_transition_gated == true
    and .input_contract.controlled_order_fixture_run_schema == "agent_bridge.biocortex_retrieval.opt_in_controlled_order_fixture_run.v0"
    and .input_contract.runtime_readiness_packet_schema == "agent_bridge.biocortex_retrieval.opt_in_runtime_readiness_packet.v0"
    and .input_contract.batch_diagnostics_included == false
    and .input_contract.controlled_order_fixture_run_included == false
    and .input_contract.runtime_readiness_packet_included == false
    and .input_contract.runtime_readiness_packet_provided == true
    and .input_contract.raw_queries_included == false
    and .input_contract.raw_keys_included == false
    and .input_contract.content_included == false
    and .input_contract.side_signal_raw_included == false
    and .batch_diagnostics.schema_ok == true
    and .batch_diagnostics.legacy_schema_ok == false
    and .batch_diagnostics.gated_schema_ok == true
    and .batch_diagnostics.evidence_source == "runtime_transition_gated_batch_diagnostics"
    and .batch_diagnostics.transition_gated == true
    and .batch_diagnostics.transition_gate_ok == true
    and .batch_diagnostics.transition_gate_allowed_count == 2
    and .batch_diagnostics.transition_gate_blocked_count == 0
    and .batch_diagnostics.store_trial_called_count == 2
    and .batch_diagnostics.calls_memory_search_count == 2
    and .batch_diagnostics.query_count == 2
    and .batch_diagnostics.baseline_empty_count == 2
    and .batch_diagnostics.adapter_allowed_count == 0
    and .batch_diagnostics.actual_order_changed_count == 0
    and .batch_diagnostics.raw_flags_all_false == true
    and .batch_diagnostics.movement_observed == false
    and .batch_diagnostics.diagnostic_class == "preflight_or_baseline_empty"
    and .controlled_order.schema_ok == true
    and .controlled_order.expected_met == true
    and .controlled_order.seeded_memory_count == 2
    and .controlled_order.query_count == 1
    and .controlled_order.adapter_allowed_count == 1
    and .controlled_order.side_signal_ok_count == 1
    and .controlled_order.experimental_source_count == 1
    and .controlled_order.actual_order_changed_count == 1
    and .controlled_order.raw_flags_all_false == true
    and .controlled_order.movement_observed == true
    and .runtime_readiness.provided == true
    and .runtime_readiness.schema_ok == true
    and .runtime_readiness.runtime_readiness_packet == true
    and .runtime_readiness.runtime_readiness_ready == true
    and .runtime_readiness.control_plane_ready == true
    and .runtime_readiness.live_order_influence_ready == false
    and .runtime_readiness.may_accept_controlled_explicit_opt_in_fts_calls == true
    and .runtime_readiness.default_influence_ready == false
    and .runtime_readiness.batch_evidence_source == "runtime_transition_gated_batch_diagnostics"
    and .runtime_readiness.batch_transition_gated == true
    and .runtime_readiness.batch_schema_ok == true
    and .runtime_readiness.batch_transition_gate_ok == true
    and .runtime_readiness.raw_flags_all_false == true
    and .runtime_readiness.default_order_safe == true
    and .runtime_readiness.matches_batch_diagnostics == true
    and .runtime_readiness.gated_batch_evidence_ready == true
    and .interpretation.batch_diagnostics_raw_safe == true
    and .interpretation.batch_diagnostics_transition_gated == true
    and .interpretation.batch_diagnostics_evidence_source == "runtime_transition_gated_batch_diagnostics"
    and .interpretation.gated_batch_diagnostics_ready == true
    and .interpretation.controlled_order_raw_safe == true
    and .interpretation.runtime_readiness_packet_provided == true
    and .interpretation.runtime_readiness_packet_ready == true
    and .interpretation.runtime_readiness_requirement_met == true
    and .interpretation.readiness_batch_evidence_source == "runtime_transition_gated_batch_diagnostics"
    and .interpretation.readiness_batch_transition_gated == true
    and .interpretation.readiness_matches_batch_diagnostics == true
    and .interpretation.readiness_gated_batch_evidence_ready == true
    and .interpretation.runtime_adapter_connection_evidence == true
    and .interpretation.controlled_rank_movement_observed == true
    and .interpretation.evidence_ready == true
    and .interpretation.default_influence_ready == false
    and .interpretation.recommended_next_step == "expand_non_production_corpus"
    and .interpretation.review_state == "post_runtime_evidence_ready"
    and .approval_state == "evidence_summary_only"
    and .authorization_state == "does_not_grant_runtime_influence"
    and .approval_writes_allowed == false
    and .writes_approval == false
    and .calls_memory_search == false
    and .runs_biocortex == false
    and .registers_embedding_backend == false
    and .changes_memory_search_order == false
    and .default_search_order_change_allowed == false
    and .default_calls_unchanged == true
    and .raw_queries_included == false
    and .raw_keys_included == false
    and .content_included == false
    and .side_signal_raw_included == false
' "$opt_in_evidence_summary_with_gated_readiness" >/dev/null
if grep -q 'verify gated batch allowed secret query one\|verify gated batch allowed secret query two\|verify gated store trial allowed secret query\|verify aggregate-backed store trial ready secret query\|cortexdelta\|cortexepsilon\|cortexzeta\|cortexeta\|cortextheta\|cortexiota\|controlled_order_baseline_high\|controlled_order_biocortex_target\|target anchor\|baseline anchor\|axonalpha\|expanded_corpus_baseline_focus\|verify_runtime_trial_secret_key\|verify runtime trial secret content' "$opt_in_evidence_summary_with_gated_readiness"; then
    echo "opt-in evidence summary with gated readiness leaked raw query/key/content data" >&2
    exit 1
fi

opt_in_runtime_influence_review_request_with_evidence_summary="$tmpdir/opt-in-runtime-influence-review-request-with-evidence-summary.json"
run cargo run -p ab-bridge --no-default-features -- \
    bio-cortex retrieval-opt-in-runtime-influence-review-request \
    --post-implementation-review-gate-json "$opt_in_post_implementation_review_gate" \
    --redacted-order-artifact-json "$opt_in_redacted_order_artifact" \
    --redacted-evidence-aggregate-json "$opt_in_redacted_evidence_aggregate" \
    --evidence-summary-json "$opt_in_evidence_summary_with_gated_readiness" \
    --reviewer verify-bundle \
    --commit verify-dry-run-commit \
    --forum-post-id verify-forum-post \
    --memory-key verify-memory-key-evidence-summary-review \
    --json > "$opt_in_runtime_influence_review_request_with_evidence_summary"
jq -e '
    .schema == "agent_bridge.biocortex_retrieval.opt_in_runtime_influence_review_request.v0"
    and .read_only == true
    and .runtime_influence_review_request == true
    and .implementation_stage == "runtime_influence_review_request_only"
    and .input_contract.post_implementation_review_gate_schema == "agent_bridge.biocortex_retrieval.opt_in_post_implementation_review_gate.v0"
    and .input_contract.redacted_order_artifact_schema == "agent_bridge.biocortex_retrieval.opt_in_redacted_order_artifact.v0"
    and .input_contract.redacted_evidence_aggregate_schema == "agent_bridge.biocortex_retrieval.opt_in_redacted_evidence_aggregate.v0"
    and .input_contract.post_runtime_evidence_summary_schema == "agent_bridge.biocortex_retrieval.opt_in_evidence_summary.v0"
    and .input_contract.accepts_optional_redacted_evidence_aggregate == true
    and .input_contract.requires_aggregate_ready_when_provided == true
    and .input_contract.accepts_optional_post_runtime_evidence_summary == true
    and .input_contract.requires_post_runtime_evidence_summary_ready_when_provided == true
    and .input_contract.post_implementation_review_gate_included == false
    and .input_contract.redacted_order_artifact_included == false
    and .input_contract.redacted_evidence_aggregate_included == false
    and .input_contract.post_runtime_evidence_summary_included == false
    and .input_contract.raw_query_included == false
    and .input_contract.raw_queries_included == false
    and .input_contract.raw_keys_included == false
    and .input_contract.content_included == false
    and .input_contract.side_signal_raw_included == false
    and .requested_authorization.accepts_redacted_evidence_aggregate == true
    and .requested_authorization.requires_redacted_evidence_aggregate == false
    and .requested_authorization.accepts_post_runtime_evidence_summary == true
    and .requested_authorization.requires_post_runtime_evidence_summary == false
    and .requested_authorization.this_packet_grants_request == false
    and .evidence_summary.post_implementation_gate_ready == true
    and .evidence_summary.redacted_order_artifact_ready == true
    and .evidence_summary.redacted_evidence_aggregate_provided == true
    and .evidence_summary.redacted_evidence_aggregate_ready == true
    and .evidence_summary.aggregate_review_state == "redacted_aggregate_ready"
    and .evidence_summary.controlled_rank_movement_observed == true
    and .evidence_summary.expanded_coverage_without_additional_movement == true
    and .evidence_summary.aggregate_default_influence_ready == false
    and .evidence_summary.default_influence_ready == false
    and .evidence_summary.aggregate_human_review_required == true
    and .evidence_summary.redacted_evidence_aggregate_summary_included == false
    and .evidence_summary.post_runtime_evidence_summary_provided == true
    and .evidence_summary.post_runtime_evidence_summary_ready == true
    and .evidence_summary.post_runtime_evidence_summary_review_state == "post_runtime_evidence_ready"
    and .evidence_summary.post_runtime_evidence_summary_default_influence_ready == false
    and .evidence_summary.post_runtime_controlled_rank_movement_observed == true
    and .evidence_summary.post_runtime_runtime_readiness_packet_provided == true
    and .evidence_summary.post_runtime_runtime_readiness_requirement_met == true
    and .evidence_summary.post_runtime_readiness_gated_batch_evidence_ready == true
    and .evidence_summary.post_runtime_batch_transition_gated == true
    and .evidence_summary.post_runtime_batch_evidence_source == "runtime_transition_gated_batch_diagnostics"
    and .evidence_summary.post_runtime_evidence_summary_included == false
    and .evidence_summary.runtime_adapter_approved == false
    and .evidence_summary.default_search_order_change_allowed == false
    and .evidence_summary.ordering_behavior_connected == false
    and .boundary_check.runtime_influence_review_request_ready == true
    and (.boundary_check.blockers | length) == 0
    and .boundary_check.redacted_evidence_aggregate_provided == true
    and .boundary_check.redacted_evidence_aggregate_ready == true
    and .boundary_check.aggregate_schema_ok == true
    and .boundary_check.aggregate_safe_for_review == true
    and .boundary_check.post_runtime_evidence_summary_provided == true
    and .boundary_check.post_runtime_evidence_summary_ready == true
    and .boundary_check.post_runtime_evidence_summary_schema_ok == true
    and .boundary_check.post_runtime_evidence_summary_safe_for_review == true
    and .boundary_check.post_runtime_evidence_summary_gated_readiness_ready == true
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
' "$opt_in_runtime_influence_review_request_with_evidence_summary" >/dev/null
if grep -q 'verify gated batch allowed secret query one\|verify gated batch allowed secret query two\|verify gated store trial allowed secret query\|verify aggregate-backed store trial ready secret query\|cortexdelta\|cortexepsilon\|cortexzeta\|cortexeta\|cortextheta\|cortexiota\|controlled_order_baseline_high\|controlled_order_biocortex_target\|target anchor\|baseline anchor\|axonalpha\|axonbeta\|axongamma\|axondelta\|axonepsilon\|axonzeta\|dendritealpha\|dendritebeta\|dendritegamma\|dendritedelta\|dendriteepsilon\|dendritezeta\|gliaalph\|gliabet\|gliagam\|gliadel\|gliaeps\|gliazet\|myelinalpha\|myelinbeta\|myelingamma\|myelindelta\|myelinepsilon\|myelinzeta\|synapsealpha\|synapsebeta\|synapsegamma\|synapsedelta\|synapseepsilon\|synapsezeta\|expanded_corpus_baseline_focus\|expanded_corpus_target_span\|baseline focus\|target span\|biocortex opt-in runtime adapter\|runtime influence decision packet\|memory search baseline recall\|redacted order artifact movement\|agent bridge mcp tool registry\|agent bridge mcp\|verify_runtime_trial_secret_key\|verify runtime trial secret content' "$opt_in_runtime_influence_review_request_with_evidence_summary"; then
    echo "opt-in runtime influence review request with evidence summary leaked raw query/key/content data" >&2
    exit 1
fi

opt_in_runtime_influence_decision_packet_with_evidence_summary="$tmpdir/opt-in-runtime-influence-decision-packet-with-evidence-summary.json"
run cargo run -p ab-bridge --no-default-features -- \
    bio-cortex retrieval-opt-in-runtime-influence-decision-packet \
    --runtime-influence-review-request-json "$opt_in_runtime_influence_review_request_with_evidence_summary" \
    --runtime-influence-decision-json "$opt_in_runtime_influence_decision" \
    --reviewer verify-bundle \
    --commit verify-dry-run-commit \
    --forum-post-id verify-forum-post \
    --memory-key verify-memory-key-evidence-summary-decision \
    --json > "$opt_in_runtime_influence_decision_packet_with_evidence_summary"
jq -e '
    .schema == "agent_bridge.biocortex_retrieval.opt_in_runtime_influence_decision_packet.v0"
    and .read_only == true
    and .runtime_influence_decision_consumer == true
    and .implementation_stage == "runtime_influence_decision_consumer_only"
    and .authorization_scope == "explicit_opt_in_fts_runtime_influence"
    and .input_contract.runtime_influence_review_request_included == false
    and .input_contract.runtime_influence_decision_included == false
    and .input_contract.accepts_aggregate_backed_review_request == true
    and .input_contract.requires_aggregate_ready_when_provided == true
    and .input_contract.redacted_evidence_aggregate_included == false
    and .input_contract.accepts_post_runtime_evidence_summary_review_request == true
    and .input_contract.requires_post_runtime_evidence_summary_ready_when_provided == true
    and .input_contract.post_runtime_evidence_summary_included == false
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
    and .request_summary.aggregate_backed_review_request == true
    and .request_summary.aggregate_review_evidence_state == "redacted_aggregate_ready"
    and .request_summary.redacted_evidence_aggregate_provided == true
    and .request_summary.redacted_evidence_aggregate_ready == true
    and .request_summary.aggregate_review_state == "redacted_aggregate_ready"
    and .request_summary.controlled_rank_movement_observed == true
    and .request_summary.expanded_coverage_without_additional_movement == true
    and .request_summary.aggregate_default_influence_ready == false
    and .request_summary.default_influence_ready == false
    and .request_summary.aggregate_human_review_required == true
    and .request_summary.redacted_evidence_aggregate_summary_included == false
    and .request_summary.post_runtime_evidence_summary_backed_review_request == true
    and .request_summary.post_runtime_evidence_summary_state == "post_runtime_evidence_ready"
    and .request_summary.post_runtime_evidence_summary_provided == true
    and .request_summary.post_runtime_evidence_summary_ready == true
    and .request_summary.post_runtime_evidence_summary_review_state == "post_runtime_evidence_ready"
    and .request_summary.post_runtime_controlled_rank_movement_observed == true
    and .request_summary.post_runtime_runtime_readiness_packet_provided == true
    and .request_summary.post_runtime_runtime_readiness_requirement_met == true
    and .request_summary.post_runtime_readiness_gated_batch_evidence_ready == true
    and .request_summary.post_runtime_batch_transition_gated == true
    and .request_summary.post_runtime_batch_evidence_source == "runtime_transition_gated_batch_diagnostics"
    and .request_summary.post_runtime_evidence_summary_default_influence_ready == false
    and .request_summary.post_runtime_evidence_summary_included == false
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
    and .boundary_check.aggregate_backed_review_request == true
    and .boundary_check.aggregate_review_evidence_ready == true
    and .boundary_check.legacy_review_request_without_aggregate_allowed == false
    and .boundary_check.aggregate_contract_ok == true
    and .boundary_check.aggregate_summary_redacted == true
    and .boundary_check.aggregate_safe_for_decision == true
    and .boundary_check.aggregate_default_influence_still_not_ready == true
    and .boundary_check.aggregate_human_review_required == true
    and .boundary_check.post_runtime_evidence_summary_backed_review_request == true
    and .boundary_check.post_runtime_evidence_summary_ready == true
    and .boundary_check.legacy_review_request_without_post_runtime_evidence_summary_allowed == false
    and .boundary_check.post_runtime_evidence_summary_contract_ok == true
    and .boundary_check.post_runtime_evidence_summary_redacted == true
    and .boundary_check.post_runtime_evidence_summary_safe_for_decision == true
    and .boundary_check.post_runtime_evidence_summary_default_influence_still_not_ready == true
    and .boundary_check.post_runtime_runtime_readiness_requirement_met == true
    and .boundary_check.post_runtime_readiness_gated_batch_evidence_ready == true
    and .boundary_check.post_runtime_batch_transition_gated == true
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
' "$opt_in_runtime_influence_decision_packet_with_evidence_summary" >/dev/null
if grep -q 'verify gated batch allowed secret query one\|verify gated batch allowed secret query two\|verify gated store trial allowed secret query\|verify aggregate-backed store trial ready secret query\|cortexdelta\|cortexepsilon\|cortexzeta\|cortexeta\|cortextheta\|cortexiota\|controlled_order_baseline_high\|controlled_order_biocortex_target\|target anchor\|baseline anchor\|axonalpha\|axonbeta\|axongamma\|axondelta\|axonepsilon\|axonzeta\|dendritealpha\|dendritebeta\|dendritegamma\|dendritedelta\|dendriteepsilon\|dendritezeta\|gliaalph\|gliabet\|gliagam\|gliadel\|gliaeps\|gliazet\|myelinalpha\|myelinbeta\|myelingamma\|myelindelta\|myelinepsilon\|myelinzeta\|synapsealpha\|synapsebeta\|synapsegamma\|synapsedelta\|synapseepsilon\|synapsezeta\|expanded_corpus_baseline_focus\|expanded_corpus_target_span\|baseline focus\|target span\|biocortex opt-in runtime adapter\|runtime influence decision packet\|memory search baseline recall\|redacted order artifact movement\|agent bridge mcp tool registry\|agent bridge mcp\|verify runtime influence decision secret wording\|verify runtime influence decision secret query\|verify_runtime_influence_decision_secret_key\|verify runtime influence decision secret content\|verify_runtime_trial_secret_key\|verify runtime trial secret content' "$opt_in_runtime_influence_decision_packet_with_evidence_summary"; then
    echo "opt-in runtime influence decision packet with evidence summary leaked raw query/key/content data" >&2
    exit 1
fi

opt_in_store_trial_empty_with_evidence_summary="$tmpdir/opt-in-store-trial-empty-with-evidence-summary.json"
run env AGENT_BRIDGE_DB="$tmpdir/opt-in-store-trial-empty-with-evidence-summary.db" \
    AB_BIOCORTEX_RETRIEVAL_OPT_IN=1 \
    cargo run -p ab-bridge --no-default-features --features biocortex-retrieval-opt-in -- \
    bio-cortex retrieval-opt-in-store-trial \
    --runtime-influence-decision-packet-json "$opt_in_runtime_influence_decision_packet_with_evidence_summary" \
    --query "verify evidence-summary store trial ready secret query" \
    --per-call-opt-in \
    --checkout "$biocortex_rs" \
    --limit 3 \
    --attempt-id verify-store-trial-empty-with-evidence-summary \
    --commit verify-dry-run-commit \
    --json > "$opt_in_store_trial_empty_with_evidence_summary"
jq -e '
    .schema == "agent_bridge.biocortex_retrieval.opt_in_store_trial.v0"
    and .input_contract.accepts_post_runtime_evidence_summary_decision_packet == true
    and .input_contract.requires_post_runtime_evidence_summary_ready_when_provided == true
    and .input_contract.post_runtime_evidence_summary_included == false
    and .runtime_preflight.compile_feature_enabled == true
    and .runtime_preflight.runtime_enabled == true
    and .runtime_preflight.operator_disabled == false
    and .runtime_preflight.decision_packet_authorized == true
    and .runtime_preflight.decision_packet_aggregate_backed == true
    and .runtime_preflight.decision_packet_aggregate_review_evidence_ready == true
    and .runtime_preflight.legacy_decision_packet_without_aggregate_allowed == false
    and .runtime_preflight.decision_packet_aggregate_safe_for_trial == true
    and .runtime_preflight.decision_packet_post_runtime_evidence_summary_backed == true
    and .runtime_preflight.decision_packet_post_runtime_evidence_summary_ready == true
    and .runtime_preflight.legacy_decision_packet_without_post_runtime_evidence_summary_allowed == false
    and .runtime_preflight.decision_packet_post_runtime_evidence_summary_contract_ok == true
    and .runtime_preflight.decision_packet_post_runtime_evidence_summary_redacted == true
    and .runtime_preflight.decision_packet_post_runtime_evidence_summary_safe_for_trial == true
    and .runtime_preflight.decision_packet_post_runtime_evidence_summary_state == "post_runtime_evidence_ready"
    and .runtime_preflight.decision_packet_post_runtime_evidence_summary_default_influence_ready == false
    and .runtime_preflight.decision_packet_post_runtime_readiness_requirement_met == true
    and .runtime_preflight.decision_packet_post_runtime_gated_batch_evidence_ready == true
    and .runtime_preflight.decision_packet_post_runtime_batch_transition_gated == true
    and .runtime_preflight.adapter_allowed == false
    and (.runtime_preflight.blockers | index("baseline_empty"))
    and .side_signal.attempted == false
    and .runs_biocortex == false
    and .raw_query_included == false
    and .raw_keys_included == false
    and .content_included == false
    and .default_search_order_change_allowed == false
    and .default_calls_unchanged == true
' "$opt_in_store_trial_empty_with_evidence_summary" >/dev/null
if grep -q 'verify evidence-summary store trial ready secret query\|secret evidence summary raw query\|secret_evidence_summary_key\|secret evidence summary content\|verify gated batch allowed secret query one\|verify gated batch allowed secret query two\|verify gated store trial allowed secret query\|verify aggregate-backed store trial ready secret query\|cortexdelta\|axonalpha\|expanded_corpus_baseline_focus\|verify_runtime_trial_secret_key\|verify runtime trial secret content' "$opt_in_store_trial_empty_with_evidence_summary"; then
    echo "opt-in store trial evidence-summary path leaked raw query/key/content data" >&2
    exit 1
fi

opt_in_gated_store_trial_empty_with_evidence_summary="$tmpdir/opt-in-gated-store-trial-empty-with-evidence-summary.json"
run env AGENT_BRIDGE_DB="$tmpdir/opt-in-gated-store-trial-empty-with-evidence-summary.db" \
    AB_BIOCORTEX_RETRIEVAL_OPT_IN=1 \
    cargo run -p ab-bridge --no-default-features --features biocortex-retrieval-opt-in -- \
    bio-cortex retrieval-opt-in-gated-store-trial \
    --runtime-transition-gate-json "$opt_in_runtime_transition_gate" \
    --runtime-influence-decision-packet-json "$opt_in_runtime_influence_decision_packet_with_evidence_summary" \
    --query "verify evidence-summary gated store trial secret query" \
    --per-call-opt-in \
    --checkout "$biocortex_rs" \
    --limit 3 \
    --attempt-id verify-gated-store-trial-empty-with-evidence-summary \
    --commit verify-dry-run-commit \
    --json > "$opt_in_gated_store_trial_empty_with_evidence_summary"
jq -e '
    .schema == "agent_bridge.biocortex_retrieval.opt_in_gated_store_trial.v0"
    and .gated_store_trial == true
    and .implementation_stage == "runtime_transition_gated_store_trial"
    and .status == "transition_gate_consumed"
    and .input_contract.runtime_transition_gate_included == false
    and .input_contract.runtime_influence_decision_packet_included == false
    and .input_contract.store_trial_included == false
    and .input_contract.requires_transition_gate_allowed == true
    and .input_contract.accepts_post_runtime_evidence_summary_decision_packet == true
    and .input_contract.requires_post_runtime_evidence_summary_ready_when_provided == true
    and .input_contract.post_runtime_evidence_summary_included == false
    and .input_contract.raw_query_included == false
    and .input_contract.raw_keys_included == false
    and .input_contract.content_included == false
    and .runtime_transition_preflight.transition_gate_allowed == true
    and .runtime_transition_preflight.blockers == []
    and .runtime_transition_preflight.gate_may_call_controlled_store_trial == true
    and .runtime_transition_preflight.gate_may_run_runtime_adapter_for_explicit_opt_in_fts == true
    and .runtime_transition_preflight.gate_may_connect_ordering_behavior_for_explicit_opt_in_fts == true
    and .runtime_transition_preflight.operator_disabled_now == false
    and .runtime_transition_preflight.query_present == true
    and .store_trial_called == true
    and .store_trial_summary.schema == "agent_bridge.biocortex_retrieval.opt_in_store_trial.v0"
    and .store_trial_summary.status == "baseline_returned"
    and .store_trial_summary.runtime_adapter_allowed == false
    and .store_trial_summary.runtime_preflight_blocker_count == 1
    and .store_trial_summary.compile_feature_enabled == true
    and .store_trial_summary.runtime_enabled == true
    and .store_trial_summary.operator_disabled == false
    and .store_trial_summary.decision_packet_authorized == true
    and .store_trial_summary.decision_packet_post_runtime_evidence_summary_backed == true
    and .store_trial_summary.decision_packet_post_runtime_evidence_summary_ready == true
    and .store_trial_summary.legacy_decision_packet_without_post_runtime_evidence_summary_allowed == false
    and .store_trial_summary.decision_packet_post_runtime_evidence_summary_safe_for_trial == true
    and .store_trial_summary.decision_packet_post_runtime_evidence_summary_state == "post_runtime_evidence_ready"
    and .store_trial_summary.baseline_completed == true
    and .store_trial_summary.baseline_key_count == 0
    and .store_trial_summary.side_signal_attempted == false
    and .store_trial_summary.store_wrapper_called == true
    and .store_trial_summary.store_trial_included == false
    and .calls_memory_search == true
    and .runs_biocortex == false
    and .changes_memory_search_order == false
    and .default_search_order_change_allowed == false
    and .default_calls_unchanged == true
    and .raw_query_included == false
    and .raw_keys_included == false
    and .content_included == false
    and .side_signal_raw_included == false
    and .boundary.gate_consumed == true
    and .boundary.calls_memory_search == true
' "$opt_in_gated_store_trial_empty_with_evidence_summary" >/dev/null
if grep -q 'verify evidence-summary gated store trial secret query\|verify gated batch allowed secret query one\|verify gated batch allowed secret query two\|verify gated store trial allowed secret query\|verify aggregate-backed store trial ready secret query\|secret evidence summary raw query\|secret_evidence_summary_key\|secret evidence summary content\|cortexdelta\|axonalpha\|expanded_corpus_baseline_focus\|verify_runtime_trial_secret_key\|verify runtime trial secret content' "$opt_in_gated_store_trial_empty_with_evidence_summary"; then
    echo "opt-in gated store trial evidence-summary path leaked raw query/key/content data" >&2
    exit 1
fi

opt_in_gated_batch_diagnostics_empty_with_evidence_summary="$tmpdir/opt-in-gated-batch-diagnostics-empty-with-evidence-summary.json"
run env AGENT_BRIDGE_DB="$tmpdir/opt-in-gated-batch-diagnostics-empty-with-evidence-summary.db" \
    AB_BIOCORTEX_RETRIEVAL_OPT_IN=1 \
    cargo run -p ab-bridge --no-default-features --features biocortex-retrieval-opt-in -- \
    bio-cortex retrieval-opt-in-gated-batch-diagnostics \
    --runtime-transition-gate-json "$opt_in_runtime_transition_gate" \
    --runtime-influence-decision-packet-json "$opt_in_runtime_influence_decision_packet_with_evidence_summary" \
    --query "verify evidence-summary gated batch secret query one" \
    --query-class "evidence summary one" \
    --query "verify evidence-summary gated batch secret query two" \
    --query-class "evidence summary two" \
    --per-call-opt-in \
    --checkout "$biocortex_rs" \
    --limit 3 \
    --attempt-id verify-gated-batch-diagnostics-empty-with-evidence-summary \
    --commit verify-dry-run-commit \
    --json > "$opt_in_gated_batch_diagnostics_empty_with_evidence_summary"
jq -e '
    .schema == "agent_bridge.biocortex_retrieval.opt_in_gated_batch_diagnostics.v0"
    and .gated_batch_diagnostics == true
    and .implementation_stage == "runtime_transition_gated_batch_diagnostics"
    and .status == "completed"
    and .input_contract.runtime_transition_gate_included == false
    and .input_contract.runtime_influence_decision_packet_included == false
    and .input_contract.requires_transition_gate_allowed == true
    and .input_contract.accepts_post_runtime_evidence_summary_decision_packet == true
    and .input_contract.requires_post_runtime_evidence_summary_ready_when_provided == true
    and .input_contract.post_runtime_evidence_summary_included == false
    and .input_contract.raw_queries_included == false
    and .input_contract.raw_keys_included == false
    and .input_contract.content_included == false
    and .summary.query_count == 2
    and .summary.transition_gate_allowed_count == 2
    and .summary.transition_gate_blocked_count == 0
    and .summary.store_trial_called_count == 2
    and .summary.calls_memory_search_count == 2
    and .summary.runs_biocortex_count == 0
    and .summary.default_calls_unchanged_count == 2
    and .safety.transition_gate_allowed_all == true
    and .safety.store_trial_called_all == true
    and .safety.calls_memory_search_all == true
    and .safety.runs_biocortex_any == false
    and .safety.raw_flags_all_false == true
    and ([.query_results[].transition_preflight.transition_gate_allowed] | unique) == [true]
    and ([.query_results[].store_trial.called] | unique) == [true]
    and ([.query_results[].store_trial.decision_packet_post_runtime_evidence_summary_backed] | unique) == [true]
    and ([.query_results[].store_trial.decision_packet_post_runtime_evidence_summary_ready] | unique) == [true]
    and ([.query_results[].store_trial.legacy_decision_packet_without_post_runtime_evidence_summary_allowed] | unique) == [false]
    and ([.query_results[].store_trial.decision_packet_post_runtime_evidence_summary_safe_for_trial] | unique) == [true]
    and ([.query_results[].store_trial.decision_packet_post_runtime_evidence_summary_state] | unique) == ["post_runtime_evidence_ready"]
    and ([.query_results[].calls_memory_search] | unique) == [true]
    and .calls_memory_search == true
    and .runs_biocortex == false
    and .changes_memory_search_order == false
    and .default_search_order_change_allowed == false
    and .default_calls_unchanged == true
    and .raw_queries_included == false
    and .raw_keys_included == false
    and .content_included == false
    and .side_signal_raw_included == false
    and .boundary.gate_consumed == true
    and .boundary.calls_memory_search == true
' "$opt_in_gated_batch_diagnostics_empty_with_evidence_summary" >/dev/null
if grep -q 'verify evidence-summary gated batch secret query one\|verify evidence-summary gated batch secret query two\|verify evidence-summary gated store trial secret query\|verify gated batch allowed secret query one\|verify gated batch allowed secret query two\|verify gated store trial allowed secret query\|verify aggregate-backed store trial ready secret query\|secret evidence summary raw query\|secret_evidence_summary_key\|secret evidence summary content\|cortexdelta\|axonalpha\|expanded_corpus_baseline_focus\|verify_runtime_trial_secret_key\|verify runtime trial secret content' "$opt_in_gated_batch_diagnostics_empty_with_evidence_summary"; then
    echo "opt-in gated batch diagnostics evidence-summary path leaked raw query/key/content data" >&2
    exit 1
fi

opt_in_runtime_readiness_packet_with_evidence_summary="$tmpdir/opt-in-runtime-readiness-packet-with-evidence-summary.json"
run cargo run -p ab-bridge --no-default-features -- \
    bio-cortex retrieval-opt-in-runtime-readiness-packet \
    --runtime-influence-decision-packet-json "$opt_in_runtime_influence_decision_packet_with_evidence_summary" \
    --store-trial-json "$opt_in_store_trial_empty_with_evidence_summary" \
    --batch-diagnostics-json "$opt_in_gated_batch_diagnostics_empty_with_evidence_summary" \
    --reviewer verify-bundle \
    --commit verify-dry-run-commit \
    --forum-post-id verify-forum-post \
    --memory-key verify-memory-key-evidence-summary-readiness \
    --json > "$opt_in_runtime_readiness_packet_with_evidence_summary"
jq -e '
    .schema == "agent_bridge.biocortex_retrieval.opt_in_runtime_readiness_packet.v0"
    and .read_only == true
    and .runtime_readiness_packet == true
    and .status == "completed"
    and .input_contract.runtime_influence_decision_packet_included == false
    and .input_contract.store_trial_included == false
    and .input_contract.batch_diagnostics_included == false
    and .input_contract.batch_diagnostics_evidence_source == "runtime_transition_gated_batch_diagnostics"
    and .input_contract.batch_diagnostics_transition_gated == true
    and .input_contract.accepts_post_runtime_evidence_summary_decision_packet == true
    and .input_contract.requires_post_runtime_evidence_summary_ready_when_provided == true
    and .input_contract.post_runtime_evidence_summary_included == false
    and .input_contract.raw_queries_included == false
    and .input_contract.raw_keys_included == false
    and .input_contract.content_included == false
    and .input_contract.side_signal_raw_included == false
    and .decision_summary.runtime_influence_authorized == true
    and .decision_summary.aggregate_backed_review_request == true
    and .decision_summary.aggregate_review_evidence_ready == true
    and .decision_summary.aggregate_safe_for_decision == true
    and .decision_summary.post_runtime_evidence_summary_backed_review_request == true
    and .decision_summary.post_runtime_evidence_summary_ready == true
    and .decision_summary.legacy_decision_packet_without_post_runtime_evidence_summary_allowed == false
    and .decision_summary.post_runtime_evidence_summary_safe_for_decision == true
    and .decision_summary.post_runtime_evidence_summary_default_influence_ready == false
    and .decision_summary.post_runtime_runtime_readiness_requirement_met == true
    and .decision_summary.post_runtime_readiness_gated_batch_evidence_ready == true
    and .decision_summary.post_runtime_batch_transition_gated == true
    and .decision_summary.post_runtime_batch_evidence_source == "runtime_transition_gated_batch_diagnostics"
    and .decision_summary.post_runtime_evidence_summary_state == "post_runtime_evidence_ready"
    and .store_trial_summary.aggregate_preflight_ok == true
    and .store_trial_summary.post_runtime_evidence_preflight_ok == true
    and .store_trial_summary.preflight_acceptable == true
    and .store_trial_summary.blockers == ["baseline_empty"]
    and .store_trial_summary.blockers_without_live_data == []
    and .batch_summary.schema_ok == true
    and .batch_summary.gated_schema_ok == true
    and .batch_summary.evidence_source == "runtime_transition_gated_batch_diagnostics"
    and .batch_summary.transition_gated == true
    and .batch_summary.transition_gate_ok == true
    and .batch_summary.aggregate_preflight_ok == true
    and .batch_summary.post_runtime_evidence_preflight_ok == true
    and .batch_summary.preflight_acceptable == true
    and .batch_summary.query_count == 2
    and .batch_summary.baseline_empty_count == 2
    and .batch_summary.transition_gate_allowed_count == 2
    and .batch_summary.store_trial_called_count == 2
    and .readiness.control_plane_ready == true
    and .readiness.live_probe_state == "control_plane_ready_no_live_candidates"
    and .readiness.live_order_influence_ready == false
    and .readiness.may_accept_controlled_explicit_opt_in_fts_calls == true
    and .boundary_check.runtime_readiness_ready == true
    and .boundary_check.blockers == []
    and .calls_memory_search == false
    and .runs_biocortex == false
    and .changes_memory_search_order == false
    and .default_search_order_change_allowed == false
    and .default_calls_unchanged == true
    and .raw_queries_included == false
    and .raw_keys_included == false
    and .content_included == false
    and .side_signal_raw_included == false
' "$opt_in_runtime_readiness_packet_with_evidence_summary" >/dev/null
if grep -q 'verify evidence-summary store trial ready secret query\|verify evidence-summary gated batch secret query one\|verify evidence-summary gated batch secret query two\|verify evidence-summary gated store trial secret query\|secret evidence summary raw query\|secret_evidence_summary_key\|secret evidence summary content\|verify gated batch allowed secret query one\|verify gated batch allowed secret query two\|verify gated store trial allowed secret query\|verify aggregate-backed store trial ready secret query\|cortexdelta\|axonalpha\|expanded_corpus_baseline_focus\|verify_runtime_trial_secret_key\|verify runtime trial secret content' "$opt_in_runtime_readiness_packet_with_evidence_summary"; then
    echo "opt-in runtime readiness packet evidence-summary path leaked raw query/key/content data" >&2
    exit 1
fi

opt_in_runtime_transition_gate_with_evidence_summary="$tmpdir/opt-in-runtime-transition-gate-with-evidence-summary.json"
run cargo run -p ab-bridge --no-default-features -- \
    bio-cortex retrieval-opt-in-runtime-transition-gate \
    --runtime-readiness-packet-json "$opt_in_runtime_readiness_packet_with_evidence_summary" \
    --mode fts \
    --per-call-opt-in \
    --reviewer verify-bundle \
    --commit verify-dry-run-commit \
    --forum-post-id verify-forum-post \
    --memory-key verify-memory-key-evidence-summary-transition \
    --json > "$opt_in_runtime_transition_gate_with_evidence_summary"
jq -e '
    .schema == "agent_bridge.biocortex_retrieval.opt_in_runtime_transition_gate.v0"
    and .read_only == true
    and .runtime_transition_gate == true
    and .status == "transition_allowed"
    and .requested_transition.mode == "fts"
    and .requested_transition.mode_authorized == true
    and .requested_transition.per_call_opt_in == true
    and .requested_transition.operator_disabled == false
    and .readiness_summary.control_plane_ready == true
    and .readiness_summary.may_accept_controlled_explicit_opt_in_fts_calls == true
    and .readiness_summary.post_runtime_evidence_summary_backed == true
    and .readiness_summary.post_runtime_evidence_summary_ready == true
    and .readiness_summary.legacy_decision_packet_without_post_runtime_evidence_summary_allowed == false
    and .readiness_summary.post_runtime_evidence_summary_state == "post_runtime_evidence_ready"
    and .readiness_summary.post_runtime_batch_evidence_source == "runtime_transition_gated_batch_diagnostics"
    and .readiness_summary.post_runtime_readiness_gated_batch_evidence_ready == true
    and .readiness_summary.post_runtime_batch_transition_gated == true
    and .readiness_summary.store_post_runtime_evidence_preflight_ok == true
    and .readiness_summary.batch_post_runtime_evidence_preflight_ok == true
    and .readiness_summary.boundary_ready == true
    and .readiness_summary.readiness_blockers == []
    and .readiness_summary.raw_inputs_absent == true
    and .readiness_summary.side_effects_absent == true
    and .transition.transition_allowed == true
    and .transition.may_call_controlled_store_trial == true
    and .transition.may_run_runtime_adapter_for_explicit_opt_in_fts == true
    and .transition.may_connect_ordering_behavior_for_explicit_opt_in_fts == true
    and .transition.may_affect_only_explicitly_opted_in_fts_calls == true
    and .transition.may_change_default_memory_search_order == false
    and .transition.default_influence_ready == false
    and .boundary_check.runtime_transition_allowed == true
    and .boundary_check.blockers == []
    and .boundary_check.this_packet_calls_memory_search == false
    and .boundary_check.this_packet_runs_biocortex == false
    and .boundary_check.this_packet_changes_return_order == false
    and .boundary_check.this_packet_allows_default_search_order_change == false
    and .calls_memory_search == false
    and .runs_biocortex == false
    and .changes_memory_search_order == false
    and .default_search_order_change_allowed == false
    and .default_calls_unchanged == true
    and .raw_queries_included == false
    and .raw_keys_included == false
    and .content_included == false
    and .side_signal_raw_included == false
' "$opt_in_runtime_transition_gate_with_evidence_summary" >/dev/null
if grep -q 'verify evidence-summary store trial ready secret query\|verify evidence-summary gated batch secret query one\|verify evidence-summary gated batch secret query two\|verify evidence-summary gated store trial secret query\|secret evidence summary raw query\|secret_evidence_summary_key\|secret evidence summary content\|verify gated batch allowed secret query one\|verify gated batch allowed secret query two\|verify gated store trial allowed secret query\|verify aggregate-backed store trial ready secret query\|cortexdelta\|axonalpha\|expanded_corpus_baseline_focus\|verify_runtime_trial_secret_key\|verify runtime trial secret content' "$opt_in_runtime_transition_gate_with_evidence_summary"; then
    echo "opt-in runtime transition gate evidence-summary path leaked raw query/key/content data" >&2
    exit 1
fi

opt_in_gated_store_trial_with_evidence_summary_transition="$tmpdir/opt-in-gated-store-trial-with-evidence-summary-transition.json"
run env AGENT_BRIDGE_DB="$tmpdir/opt-in-gated-store-trial-with-evidence-summary-transition.db" \
    AB_BIOCORTEX_RETRIEVAL_OPT_IN=1 \
    cargo run -p ab-bridge --no-default-features --features biocortex-retrieval-opt-in -- \
    bio-cortex retrieval-opt-in-gated-store-trial \
    --runtime-transition-gate-json "$opt_in_runtime_transition_gate_with_evidence_summary" \
    --runtime-influence-decision-packet-json "$opt_in_runtime_influence_decision_packet_with_evidence_summary" \
    --query "verify evidence-summary transition gated store trial secret query" \
    --per-call-opt-in \
    --checkout "$biocortex_rs" \
    --limit 3 \
    --attempt-id verify-gated-store-trial-with-evidence-summary-transition \
    --commit verify-dry-run-commit \
    --json > "$opt_in_gated_store_trial_with_evidence_summary_transition"
jq -e '
    .schema == "agent_bridge.biocortex_retrieval.opt_in_gated_store_trial.v0"
    and .status == "transition_gate_consumed"
    and .runtime_transition_preflight.transition_gate_allowed == true
    and .runtime_transition_preflight.blockers == []
    and .runtime_transition_preflight.gate_post_runtime_evidence_summary_backed == true
    and .runtime_transition_preflight.gate_post_runtime_evidence_summary_ready == true
    and .runtime_transition_preflight.gate_legacy_decision_packet_without_post_runtime_evidence_summary_allowed == false
    and .runtime_transition_preflight.gate_post_runtime_evidence_summary_state == "post_runtime_evidence_ready"
    and .runtime_transition_preflight.gate_post_runtime_batch_evidence_source == "runtime_transition_gated_batch_diagnostics"
    and .runtime_transition_preflight.gate_post_runtime_readiness_gated_batch_evidence_ready == true
    and .runtime_transition_preflight.gate_post_runtime_batch_transition_gated == true
    and .runtime_transition_preflight.gate_store_post_runtime_evidence_preflight_ok == true
    and .runtime_transition_preflight.gate_batch_post_runtime_evidence_preflight_ok == true
    and .store_trial_summary.decision_packet_post_runtime_evidence_summary_backed == true
    and .store_trial_summary.decision_packet_post_runtime_evidence_summary_ready == true
    and .store_trial_summary.legacy_decision_packet_without_post_runtime_evidence_summary_allowed == false
    and .store_trial_summary.decision_packet_post_runtime_evidence_summary_safe_for_trial == true
    and .store_trial_summary.decision_packet_post_runtime_evidence_summary_state == "post_runtime_evidence_ready"
    and .store_trial_called == true
    and .calls_memory_search == true
    and .runs_biocortex == false
    and .changes_memory_search_order == false
    and .default_search_order_change_allowed == false
    and .default_calls_unchanged == true
    and .raw_query_included == false
    and .raw_keys_included == false
    and .content_included == false
    and .side_signal_raw_included == false
' "$opt_in_gated_store_trial_with_evidence_summary_transition" >/dev/null
if grep -q 'verify evidence-summary transition gated store trial secret query\|verify evidence-summary store trial ready secret query\|verify evidence-summary gated batch secret query one\|verify evidence-summary gated batch secret query two\|verify evidence-summary gated store trial secret query\|secret evidence summary raw query\|secret_evidence_summary_key\|secret evidence summary content\|verify gated batch allowed secret query one\|verify gated batch allowed secret query two\|verify gated store trial allowed secret query\|verify aggregate-backed store trial ready secret query\|cortexdelta\|axonalpha\|expanded_corpus_baseline_focus\|verify_runtime_trial_secret_key\|verify runtime trial secret content' "$opt_in_gated_store_trial_with_evidence_summary_transition"; then
    echo "opt-in gated store trial evidence-summary transition path leaked raw query/key/content data" >&2
    exit 1
fi

opt_in_gated_batch_diagnostics_with_evidence_summary_transition="$tmpdir/opt-in-gated-batch-diagnostics-with-evidence-summary-transition.json"
run env AGENT_BRIDGE_DB="$tmpdir/opt-in-gated-batch-diagnostics-with-evidence-summary-transition.db" \
    AB_BIOCORTEX_RETRIEVAL_OPT_IN=1 \
    cargo run -p ab-bridge --no-default-features --features biocortex-retrieval-opt-in -- \
    bio-cortex retrieval-opt-in-gated-batch-diagnostics \
    --runtime-transition-gate-json "$opt_in_runtime_transition_gate_with_evidence_summary" \
    --runtime-influence-decision-packet-json "$opt_in_runtime_influence_decision_packet_with_evidence_summary" \
    --query "verify evidence-summary transition gated batch secret query" \
    --query-class "evidence summary transition" \
    --per-call-opt-in \
    --checkout "$biocortex_rs" \
    --limit 3 \
    --attempt-id verify-gated-batch-diagnostics-with-evidence-summary-transition \
    --commit verify-dry-run-commit \
    --json > "$opt_in_gated_batch_diagnostics_with_evidence_summary_transition"
jq -e '
    .schema == "agent_bridge.biocortex_retrieval.opt_in_gated_batch_diagnostics.v0"
    and .status == "completed"
    and .summary.query_count == 1
    and .summary.transition_gate_allowed_count == 1
    and .summary.store_trial_called_count == 1
    and .summary.calls_memory_search_count == 1
    and .safety.transition_gate_allowed_all == true
    and .safety.store_trial_called_all == true
    and .safety.raw_flags_all_false == true
    and .query_results[0].transition_preflight.gate_post_runtime_evidence_summary_backed == true
    and .query_results[0].transition_preflight.gate_post_runtime_evidence_summary_ready == true
    and .query_results[0].transition_preflight.gate_legacy_decision_packet_without_post_runtime_evidence_summary_allowed == false
    and .query_results[0].transition_preflight.gate_post_runtime_evidence_summary_state == "post_runtime_evidence_ready"
    and .query_results[0].transition_preflight.gate_post_runtime_batch_evidence_source == "runtime_transition_gated_batch_diagnostics"
    and .query_results[0].transition_preflight.gate_store_post_runtime_evidence_preflight_ok == true
    and .query_results[0].transition_preflight.gate_batch_post_runtime_evidence_preflight_ok == true
    and .query_results[0].store_trial.decision_packet_post_runtime_evidence_summary_backed == true
    and .query_results[0].store_trial.decision_packet_post_runtime_evidence_summary_ready == true
    and .query_results[0].calls_memory_search == true
    and .calls_memory_search == true
    and .runs_biocortex == false
    and .changes_memory_search_order == false
    and .default_search_order_change_allowed == false
    and .default_calls_unchanged == true
    and .raw_queries_included == false
    and .raw_keys_included == false
    and .content_included == false
    and .side_signal_raw_included == false
' "$opt_in_gated_batch_diagnostics_with_evidence_summary_transition" >/dev/null
if grep -q 'verify evidence-summary transition gated batch secret query\|verify evidence-summary transition gated store trial secret query\|verify evidence-summary store trial ready secret query\|verify evidence-summary gated batch secret query one\|verify evidence-summary gated batch secret query two\|verify evidence-summary gated store trial secret query\|secret evidence summary raw query\|secret_evidence_summary_key\|secret evidence summary content\|verify gated batch allowed secret query one\|verify gated batch allowed secret query two\|verify gated store trial allowed secret query\|verify aggregate-backed store trial ready secret query\|cortexdelta\|axonalpha\|expanded_corpus_baseline_focus\|verify_runtime_trial_secret_key\|verify runtime trial secret content' "$opt_in_gated_batch_diagnostics_with_evidence_summary_transition"; then
    echo "opt-in gated batch diagnostics evidence-summary transition path leaked raw query/key/content data" >&2
    exit 1
fi

opt_in_status_controlled_trial_readiness="$tmpdir/opt-in-status-controlled-trial-readiness.json"
run env AB_BIOCORTEX_RETRIEVAL_OPT_IN=1 \
    cargo run -p ab-bridge --no-default-features --features biocortex-retrieval-opt-in -- \
    bio-cortex retrieval-opt-in-status \
    --mode fts \
    --per-call-opt-in \
    --query "verify controlled status secret query" \
    --baseline-key verify_controlled_status_secret_key \
    --runtime-readiness-packet-json "$opt_in_runtime_readiness_packet_with_evidence_summary" \
    --runtime-transition-gate-json "$opt_in_runtime_transition_gate_with_evidence_summary" \
    --gated-store-trial-json "$opt_in_gated_store_trial_with_evidence_summary_transition" \
    --gated-batch-diagnostics-json "$opt_in_gated_batch_diagnostics_with_evidence_summary_transition" \
    --json > "$opt_in_status_controlled_trial_readiness"
jq -e '
    .schema == "agent_bridge.biocortex_retrieval.opt_in_call_audit.v0"
    and .mode == "fts"
    and .mode_authorized == true
    and .gate.status == "ready_for_explicit_opt_in_experiment"
    and .controlled_trial_readiness.schema == "agent_bridge.biocortex_retrieval.controlled_trial_readiness_summary.v0"
    and .controlled_trial_readiness.evidence_provided == true
    and .controlled_trial_readiness.status == "ready_for_controlled_explicit_opt_in_fts_trial"
    and .controlled_trial_readiness.ready_for_controlled_trial == true
    and .controlled_trial_readiness.blockers == []
    and .controlled_trial_readiness.requested_mode == "fts"
    and .controlled_trial_readiness.requested_per_call_opt_in == true
    and .controlled_trial_readiness.status_request_ok == true
    and .controlled_trial_readiness.runtime_readiness_packet.provided == true
    and .controlled_trial_readiness.runtime_readiness_packet.schema_ok == true
    and .controlled_trial_readiness.runtime_readiness_packet.control_plane_ready == true
    and .controlled_trial_readiness.runtime_readiness_packet.boundary_ready == true
    and .controlled_trial_readiness.runtime_readiness_packet.side_effects_absent == true
    and .controlled_trial_readiness.runtime_readiness_packet.ready == true
    and .controlled_trial_readiness.runtime_readiness_packet.post_runtime_evidence_summary_backed == true
    and .controlled_trial_readiness.runtime_readiness_packet.post_runtime_evidence_summary_ready == true
    and .controlled_trial_readiness.runtime_readiness_packet.post_runtime_evidence_summary_state == "post_runtime_evidence_ready"
    and .controlled_trial_readiness.runtime_readiness_packet.post_runtime_batch_evidence_source == "runtime_transition_gated_batch_diagnostics"
    and .controlled_trial_readiness.runtime_transition_gate.provided == true
    and .controlled_trial_readiness.runtime_transition_gate.schema_ok == true
    and .controlled_trial_readiness.runtime_transition_gate.request_ok == true
    and .controlled_trial_readiness.runtime_transition_gate.transition_allowed == true
    and .controlled_trial_readiness.runtime_transition_gate.side_effects_absent == true
    and .controlled_trial_readiness.runtime_transition_gate.ready == true
    and .controlled_trial_readiness.runtime_transition_gate.post_runtime_evidence_summary_backed == true
    and .controlled_trial_readiness.runtime_transition_gate.post_runtime_evidence_summary_ready == true
    and .controlled_trial_readiness.runtime_transition_gate.post_runtime_evidence_summary_state == "post_runtime_evidence_ready"
    and .controlled_trial_readiness.runtime_transition_gate.post_runtime_batch_evidence_source == "runtime_transition_gated_batch_diagnostics"
    and .controlled_trial_readiness.gated_store_trial.provided == true
    and .controlled_trial_readiness.gated_store_trial.schema_ok == true
    and .controlled_trial_readiness.gated_store_trial.gate_consumed == true
    and .controlled_trial_readiness.gated_store_trial.ready == true
    and .controlled_trial_readiness.gated_store_trial.post_runtime_evidence_summary_ready == true
    and .controlled_trial_readiness.gated_store_trial.store_trial_called == true
    and .controlled_trial_readiness.gated_store_trial.calls_memory_search == true
    and .controlled_trial_readiness.gated_store_trial.changes_memory_search_order == false
    and .controlled_trial_readiness.gated_batch_diagnostics.provided == true
    and .controlled_trial_readiness.gated_batch_diagnostics.schema_ok == true
    and .controlled_trial_readiness.gated_batch_diagnostics.ready == true
    and .controlled_trial_readiness.gated_batch_diagnostics.post_runtime_evidence_summary_ready == true
    and .controlled_trial_readiness.gated_batch_diagnostics.query_count == 1
    and .controlled_trial_readiness.gated_batch_diagnostics.transition_gate_allowed_count == 1
    and .controlled_trial_readiness.gated_batch_diagnostics.store_trial_called_count == 1
    and .controlled_trial_readiness.gated_batch_diagnostics.calls_memory_search_count == 1
    and .controlled_trial_readiness.status_surface_calls_memory_search == false
    and .controlled_trial_readiness.status_surface_runs_biocortex == false
    and .controlled_trial_readiness.status_surface_changes_memory_search_order == false
    and .controlled_trial_readiness.raw_packets_included == false
    and .controlled_trial_readiness.raw_queries_included == false
    and .controlled_trial_readiness.raw_keys_included == false
    and .controlled_trial_readiness.content_included == false
    and .changes_memory_search_order == false
    and .default_search_order_change_allowed == false
    and .default_calls_unchanged == true
' "$opt_in_status_controlled_trial_readiness" >/dev/null
if grep -q 'verify controlled status secret query\|verify_controlled_status_secret_key\|verify evidence-summary transition gated batch secret query\|verify evidence-summary transition gated store trial secret query\|verify evidence-summary store trial ready secret query\|verify evidence-summary gated batch secret query one\|verify evidence-summary gated batch secret query two\|verify evidence-summary gated store trial secret query\|secret evidence summary raw query\|secret_evidence_summary_key\|secret evidence summary content\|verify gated batch allowed secret query one\|verify gated batch allowed secret query two\|verify gated store trial allowed secret query\|verify aggregate-backed store trial ready secret query\|cortexdelta\|axonalpha\|expanded_corpus_baseline_focus\|verify_runtime_trial_secret_key\|verify runtime trial secret content' "$opt_in_status_controlled_trial_readiness"; then
    echo "opt-in status controlled trial readiness leaked raw query/key/content data" >&2
    exit 1
fi

opt_in_gated_batch_diagnostics_blocked="$tmpdir/opt-in-gated-batch-diagnostics-blocked.json"
run env AGENT_BRIDGE_DB="$tmpdir/opt-in-gated-batch-diagnostics-blocked.db" \
    cargo run -p ab-bridge --no-default-features -- \
    bio-cortex retrieval-opt-in-gated-batch-diagnostics \
    --runtime-transition-gate-json "$opt_in_runtime_transition_gate_blocked" \
    --runtime-influence-decision-packet-json "$opt_in_runtime_influence_decision_packet_with_aggregate" \
    --query "verify gated batch blocked secret query" \
    --mode hybrid \
    --json > "$opt_in_gated_batch_diagnostics_blocked"
jq -e '
    .schema == "agent_bridge.biocortex_retrieval.opt_in_gated_batch_diagnostics.v0"
    and .status == "transition_gate_blocked"
    and .summary.query_count == 1
    and .summary.transition_gate_allowed_count == 0
    and .summary.transition_gate_blocked_count == 1
    and .summary.store_trial_called_count == 0
    and .summary.calls_memory_search_count == 0
    and .summary.runs_biocortex_count == 0
    and .safety.transition_gate_blocked_all == true
    and .safety.store_trial_called_any == false
    and .safety.calls_memory_search_any == false
    and .safety.raw_flags_all_false == true
    and .query_results[0].movement_class == "transition_gate_blocked"
    and .query_results[0].transition_preflight.transition_gate_allowed == false
    and .query_results[0].store_trial.called == false
    and .calls_memory_search == false
    and .runs_biocortex == false
    and .changes_memory_search_order == false
    and .default_search_order_change_allowed == false
    and .default_calls_unchanged == true
    and .raw_queries_included == false
    and .raw_keys_included == false
    and .content_included == false
    and .side_signal_raw_included == false
    and .boundary.gate_consumed == false
    and .boundary.calls_memory_search == false
' "$opt_in_gated_batch_diagnostics_blocked" >/dev/null
if grep -q 'verify gated batch blocked secret query\|verify gated store trial blocked secret query\|verify aggregate-backed store trial ready secret query\|cortexdelta\|axonalpha\|expanded_corpus_baseline_focus\|verify_runtime_trial_secret_key\|verify runtime trial secret content' "$opt_in_gated_batch_diagnostics_blocked"; then
    echo "opt-in gated batch diagnostics blocked path leaked raw query/key/content data" >&2
    exit 1
fi
test -s "$opt_in_auth_request/forum-post-template.md"
test -s "$opt_in_auth_request/memory-note-template.md"

run cargo test -p ab-bridge --test lswr_interaction_feedback_fixture \
    interaction_feedback_runtime_executor_durable_outcome_ingestion_execution_preflight \
    -- --nocapture
run cargo run -q -p ab-bridge \
    --example lswr_interaction_feedback_runtime_executor_durable_outcome_ingestion_execution_preflight_smoke \
    -- \
    --format json \
    --assert-blocked-without-durable-outcome-ingestion-execution-decision \
    --assert-read-only >/dev/null
run cargo run -q -p ab-bridge \
    --example lswr_interaction_feedback_runtime_executor_durable_outcome_ingestion_execution_preflight_smoke \
    -- \
    --with-durable-outcome-ingestion-execution-decision \
    --format json \
    --assert-ready-for-durable-outcome-ingestion-write-implementation \
    --assert-read-only >/dev/null
run cargo test -p ab-bridge --test lswr_interaction_feedback_fixture \
    interaction_feedback_runtime_executor_durable_outcome_write_implementation_preflight \
    -- --nocapture
run cargo run -q -p ab-bridge \
    --example lswr_interaction_feedback_runtime_executor_durable_outcome_write_implementation_preflight_smoke \
    -- \
    --format json \
    --assert-blocked-without-durable-outcome-write-implementation-decision \
    --assert-read-only >/dev/null
run cargo run -q -p ab-bridge \
    --example lswr_interaction_feedback_runtime_executor_durable_outcome_write_implementation_preflight_smoke \
    -- \
    --with-durable-outcome-write-implementation-decision \
    --format json \
    --assert-ready-for-durable-outcome-record-write \
    --assert-read-only >/dev/null
run cargo test -p ab-bridge --test lswr_interaction_feedback_fixture \
    interaction_feedback_runtime_executor_durable_outcome_record_write_preflight \
    -- --nocapture
run cargo run -q -p ab-bridge \
    --example lswr_interaction_feedback_runtime_executor_durable_outcome_record_write_preflight_smoke \
    -- \
    --format json \
    --assert-blocked-without-durable-outcome-record-write-decision \
    --assert-read-only >/dev/null
run cargo run -q -p ab-bridge \
    --example lswr_interaction_feedback_runtime_executor_durable_outcome_record_write_preflight_smoke \
    -- \
    --with-durable-outcome-record-write-decision \
    --format json \
    --assert-ready-for-durable-outcome-record-write-execution \
    --assert-read-only >/dev/null
run cargo test -p ab-bridge --test lswr_interaction_feedback_fixture \
    interaction_feedback_runtime_executor_durable_outcome_record_write_execution_preflight \
    -- --nocapture
run cargo run -q -p ab-bridge \
    --example lswr_interaction_feedback_runtime_executor_durable_outcome_record_write_execution_preflight_smoke \
    -- \
    --format json \
    --assert-blocked-without-durable-outcome-record-write-execution-decision \
    --assert-read-only >/dev/null
run cargo run -q -p ab-bridge \
    --example lswr_interaction_feedback_runtime_executor_durable_outcome_record_write_execution_preflight_smoke \
    -- \
    --with-durable-outcome-record-write-execution-decision \
    --format json \
    --assert-ready-for-durable-outcome-record-persistence \
    --assert-read-only >/dev/null
run cargo test -p ab-bridge --test lswr_interaction_feedback_fixture \
    interaction_feedback_runtime_executor_durable_outcome_record_persistence_preflight \
    -- --nocapture
run cargo run -q -p ab-bridge \
    --example lswr_interaction_feedback_runtime_executor_durable_outcome_record_persistence_preflight_smoke \
    -- \
    --format json \
    --assert-blocked-without-durable-outcome-record-persistence-decision \
    --assert-read-only >/dev/null
run cargo run -q -p ab-bridge \
    --example lswr_interaction_feedback_runtime_executor_durable_outcome_record_persistence_preflight_smoke \
    -- \
    --with-durable-outcome-record-persistence-decision \
    --format json \
    --assert-ready-for-durable-outcome-record-store-write \
    --assert-read-only >/dev/null
run cargo test -p ab-bridge --test lswr_interaction_feedback_fixture \
    interaction_feedback_runtime_executor_durable_outcome_record_store_write_execution_preflight \
    -- --nocapture
run cargo run -q -p ab-bridge \
    --example lswr_interaction_feedback_runtime_executor_durable_outcome_record_store_write_execution_preflight_smoke \
    -- \
    --format json \
    --assert-blocked-without-durable-outcome-record-store-write-execution-decision \
    --assert-read-only >/dev/null
run cargo run -q -p ab-bridge \
    --example lswr_interaction_feedback_runtime_executor_durable_outcome_record_store_write_execution_preflight_smoke \
    -- \
    --with-durable-outcome-record-store-write-execution-decision \
    --format json \
    --assert-ready-for-durable-outcome-record-write-evidence \
    --assert-read-only >/dev/null
run cargo test -p ab-bridge --test lswr_interaction_feedback_fixture \
    interaction_feedback_runtime_executor_durable_outcome_record_write_evidence_preflight \
    -- --nocapture
run cargo run -q -p ab-bridge \
    --example lswr_interaction_feedback_runtime_executor_durable_outcome_record_write_evidence_preflight_smoke \
    -- \
    --format json \
    --assert-blocked-without-durable-outcome-record-write-evidence \
    --assert-read-only >/dev/null
run cargo run -q -p ab-bridge \
    --example lswr_interaction_feedback_runtime_executor_durable_outcome_record_write_evidence_preflight_smoke \
    -- \
    --with-durable-outcome-record-write-evidence \
    --format json \
    --assert-ready-for-durable-outcome-record-write-evidence-review \
    --assert-read-only >/dev/null
run cargo test -p ab-bridge --test lswr_interaction_feedback_fixture \
    interaction_feedback_runtime_executor_durable_outcome_record_write_evidence_review_preflight \
    -- --nocapture
run cargo run -q -p ab-bridge \
    --example lswr_interaction_feedback_runtime_executor_durable_outcome_record_write_evidence_review_preflight_smoke \
    -- \
    --format json \
    --assert-blocked-without-durable-outcome-record-write-evidence-review-decision \
    --assert-read-only >/dev/null
run cargo run -q -p ab-bridge \
    --example lswr_interaction_feedback_runtime_executor_durable_outcome_record_write_evidence_review_preflight_smoke \
    -- \
    --with-durable-outcome-record-write-evidence-review-decision \
    --format json \
    --assert-ready-for-world-verdict-rewrite-gate \
    --assert-read-only >/dev/null
run cargo test -p ab-bridge --test lswr_interaction_feedback_fixture \
    interaction_feedback_runtime_executor_world_verdict_rewrite_gate \
    -- --nocapture
run cargo run -q -p ab-bridge \
    --example lswr_interaction_feedback_runtime_executor_world_verdict_rewrite_gate_smoke \
    -- \
    --format json \
    --assert-blocked-without-world-verdict-rewrite-decision \
    --assert-output-only >/dev/null
run cargo run -q -p ab-bridge \
    --example lswr_interaction_feedback_runtime_executor_world_verdict_rewrite_gate_smoke \
    -- \
    --with-world-verdict-rewrite-decision \
    --format json \
    --assert-ready-for-verified-outcome-ingestion-gate \
    --assert-output-only >/dev/null
run cargo test -p ab-bridge --test lswr_interaction_feedback_fixture \
    interaction_feedback_runtime_executor_verified_outcome_ingestion_gate \
    -- --nocapture
run cargo run -q -p ab-bridge \
    --example lswr_interaction_feedback_runtime_executor_verified_outcome_ingestion_gate_smoke \
    -- \
    --format json \
    --assert-blocked-without-verified-outcome-ingestion-decision \
    --assert-output-only >/dev/null
run cargo run -q -p ab-bridge \
    --example lswr_interaction_feedback_runtime_executor_verified_outcome_ingestion_gate_smoke \
    -- \
    --with-verified-outcome-ingestion-decision \
    --format json \
    --assert-ready-for-verified-outcome-admission \
    --assert-output-only >/dev/null
run cargo test -p ab-bridge --test lswr_interaction_feedback_fixture \
    interaction_feedback_runtime_executor_verified_outcome_ingestion_execution_preflight \
    -- --nocapture
run cargo run -q -p ab-bridge \
    --example lswr_interaction_feedback_runtime_executor_verified_outcome_ingestion_execution_preflight_smoke \
    -- \
    --format json \
    --assert-blocked-without-verified-outcome-ingestion-execution-decision \
    --assert-output-only >/dev/null
run cargo run -q -p ab-bridge \
    --example lswr_interaction_feedback_runtime_executor_verified_outcome_ingestion_execution_preflight_smoke \
    -- \
    --with-verified-outcome-ingestion-execution-decision \
    --format json \
    --assert-ready-for-verified-outcome-ingestion-execution-commit \
    --assert-output-only >/dev/null
run cargo test -p ab-bridge --test lswr_interaction_feedback_fixture \
    interaction_feedback_runtime_executor_verified_outcome_ingestion_execution_commit \
    -- --nocapture
run cargo run -q -p ab-bridge \
    --example lswr_interaction_feedback_runtime_executor_verified_outcome_ingestion_execution_commit_smoke \
    -- \
    --format json \
    --assert-blocked-without-verified-outcome-ingestion-execution-commit-decision \
    --assert-output-only >/dev/null
run cargo run -q -p ab-bridge \
    --example lswr_interaction_feedback_runtime_executor_verified_outcome_ingestion_execution_commit_smoke \
    -- \
    --with-verified-outcome-ingestion-execution-commit-decision \
    --format json \
    --assert-ready-for-verified-outcome-ingestion-apply \
    --assert-output-only >/dev/null
run cargo test -p ab-bridge --test lswr_interaction_feedback_fixture \
    interaction_feedback_runtime_executor_verified_outcome_ingestion_apply_gate \
    -- --nocapture
run cargo run -q -p ab-bridge \
    --example lswr_interaction_feedback_runtime_executor_verified_outcome_ingestion_apply_gate_smoke \
    -- \
    --format json \
    --assert-blocked-without-verified-outcome-ingestion-apply-decision \
    --assert-output-only >/dev/null
run cargo run -q -p ab-bridge \
    --example lswr_interaction_feedback_runtime_executor_verified_outcome_ingestion_apply_gate_smoke \
    -- \
    --with-verified-outcome-ingestion-apply-decision \
    --format json \
    --assert-ready-for-verified-outcome-ingestion-writer \
    --assert-output-only >/dev/null
run cargo test -p ab-bridge --test lswr_interaction_feedback_fixture \
    interaction_feedback_runtime_executor_verified_outcome_ingestion_writer \
    -- --nocapture
run cargo run -q -p ab-bridge \
    --example lswr_interaction_feedback_runtime_executor_verified_outcome_ingestion_writer_smoke \
    -- \
    --format json \
    --assert-blocked-without-verified-outcome-ingestion-writer-decision \
    --assert-output-only >/dev/null
run cargo run -q -p ab-bridge \
    --example lswr_interaction_feedback_runtime_executor_verified_outcome_ingestion_writer_smoke \
    -- \
    --with-verified-outcome-ingestion-writer-decision \
    --format json \
    --assert-ready-for-verified-outcome-ingestion-writer-execution \
    --assert-output-only >/dev/null

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
