#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"

ts="$(date -u +%Y%m%dT%H%M%SZ)"
generated_at="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
out_dir="${TMPDIR:-/tmp}/ab-biocortex-opt-in-authorization-request-$ts"
reviewer=""
requester="codex"
runtime_proof_summary=""
runtime_trial_review_packet=""
order_diff_packet=""
plan_fixture="docs/design/fixtures/biocortex-retrieval-opt-in-experiment-plan-2026-06-11.json"
memory_key=""
forum_decision_post_id=""

usage() {
    cat <<'USAGE'
usage: scripts/prepare-biocortex-retrieval-opt-in-authorization-request.sh [flags]

Generates a local human-review request/status packet for BioCortex retrieval
opt_in_experiment authorization. This is not an approval writer: it never posts
to forum, writes memory, enables BioCortex, or changes retrieval order.

Flags:
  --out-dir PATH                 Output directory.
  --reviewer TEXT                Human reviewer identity.
  --requester TEXT               Requesting agent identity. Default: codex.
  --runtime-proof-summary PATH   proof-summary.json from prove-biocortex-retrieval-runtime-boundary.sh.
  --runtime-trial-review-packet PATH
                                 JSON from retrieval-opt-in-runtime-trial-review-packet.
  --order-diff-packet PATH       Optional JSON from retrieval-opt-in-order-diff-packet.
  --plan-fixture PATH            Opt-in experiment plan fixture.
  --memory-key KEY               Memory key to cite in generated templates.
  --forum-decision-post-id ID    Forum post id to cite in generated templates.
  -h, --help                     Show this help.
USAGE
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --out-dir) out_dir="$2"; shift 2 ;;
        --reviewer) reviewer="$2"; shift 2 ;;
        --requester) requester="$2"; shift 2 ;;
        --runtime-proof-summary) runtime_proof_summary="$2"; shift 2 ;;
        --runtime-trial-review-packet) runtime_trial_review_packet="$2"; shift 2 ;;
        --order-diff-packet) order_diff_packet="$2"; shift 2 ;;
        --plan-fixture) plan_fixture="$2"; shift 2 ;;
        --memory-key) memory_key="$2"; shift 2 ;;
        --forum-decision-post-id) forum_decision_post_id="$2"; shift 2 ;;
        -h|--help) usage; exit 0 ;;
        *) echo "unknown flag: $1" >&2; usage >&2; exit 2 ;;
    esac
done

if [[ -z "$runtime_proof_summary" ]]; then
    echo "--runtime-proof-summary is required" >&2
    exit 2
fi
if [[ ! -f "$runtime_proof_summary" ]]; then
    echo "runtime proof summary not found: $runtime_proof_summary" >&2
    exit 2
fi
if [[ -z "$runtime_trial_review_packet" ]]; then
    echo "--runtime-trial-review-packet is required" >&2
    exit 2
fi
if [[ ! -f "$runtime_trial_review_packet" ]]; then
    echo "runtime trial review packet not found: $runtime_trial_review_packet" >&2
    exit 2
fi
if [[ -n "$order_diff_packet" && ! -f "$order_diff_packet" ]]; then
    echo "order diff packet not found: $order_diff_packet" >&2
    exit 2
fi
if [[ ! -f "$plan_fixture" ]]; then
    echo "opt-in plan fixture not found: $plan_fixture" >&2
    exit 2
fi

mkdir -p "$out_dir"

order_diff_packet_for_jq="$order_diff_packet"
if [[ -z "$order_diff_packet_for_jq" ]]; then
    order_diff_packet_for_jq="$out_dir/.order-diff-packet-absent.json"
    printf 'null\n' > "$order_diff_packet_for_jq"
fi

target_host="$(hostname 2>/dev/null || printf 'unknown-host')"
branch="$(git rev-parse --abbrev-ref HEAD 2>/dev/null || printf '<required>')"
commit="$(git rev-parse HEAD 2>/dev/null || printf '<required>')"
request_packet="$out_dir/opt-in-authorization-request.json"
plan_implementation_allowed="$(jq -r '.implementation_allowed // false' "$plan_fixture")"
plan_approval_state="$(jq -r '.approval_state // "not_approved"' "$plan_fixture")"
plan_authorization_state="requested_not_granted"
if [[ "$plan_implementation_allowed" == "true" ]]; then
    plan_authorization_state="authorized_for_opt_in_implementation"
fi

jq -n \
    --slurpfile plan "$plan_fixture" \
    --slurpfile proof "$runtime_proof_summary" \
    --slurpfile trial_review "$runtime_trial_review_packet" \
    --slurpfile order_diff "$order_diff_packet_for_jq" \
    --arg generated_at "$generated_at" \
    --arg target_host "$target_host" \
    --arg branch "$branch" \
    --arg commit "$commit" \
    --arg reviewer "$reviewer" \
    --arg requester "$requester" \
    --arg memory_key "$memory_key" \
    --arg forum_decision_post_id "$forum_decision_post_id" \
    --arg plan_approval_state "$plan_approval_state" \
    --arg plan_authorization_state "$plan_authorization_state" \
    --argjson plan_implementation_allowed "$plan_implementation_allowed" \
    '{
        schema: "agent_bridge.biocortex_retrieval.opt_in_authorization_request.v0",
        generated_at: $generated_at,
        status: "request_prepared",
        approval_state: $plan_approval_state,
        authorization_state: $plan_authorization_state,
        request_scope: "opt_in_experiment",
        runtime_adapter_approved: false,
        default_search_order_change_allowed: false,
        implementation_allowed: $plan_implementation_allowed,
        writes_approval: false,
        accepts_optional_order_diff_packet: true,
        requester: $requester,
        reviewer: (if ($reviewer | length) == 0 then "<required>" else $reviewer end),
        target_host: $target_host,
        branch: $branch,
        commit_under_review: $commit,
        audit_links: {
            forum_decision_post_id: (if ($forum_decision_post_id | length) == 0 then "<required>" else $forum_decision_post_id end),
            memory_key: (if ($memory_key | length) == 0 then "<required>" else $memory_key end)
        },
        opt_in_plan: $plan[0],
        evidence: {
            runtime_boundary_proof: {
                schema: $proof[0].schema,
                read_only: $proof[0].read_only,
                runtime_adapter_approved: $proof[0].runtime_adapter_approved,
                default_search_order_changed: $proof[0].default_search_order_changed,
                default_disabled_status: $proof[0].proof.default_disabled.status,
                kill_switch_status: $proof[0].proof.kill_switch.status,
                enabled_shadow_status: $proof[0].proof.enabled_shadow.status,
                p95_ms: $proof[0].latency.p95_ms,
                sample_count: $proof[0].latency.sample_count
            },
            runtime_trial_review_packet: {
                provided: true,
                schema: $trial_review[0].schema,
                read_only: $trial_review[0].read_only,
                runtime_trial_consumer: $trial_review[0].runtime_trial_consumer,
                review_scope: $trial_review[0].review_scope,
                review_ready_for_baseline_runtime_trial:
                    $trial_review[0].boundary_check.review_ready_for_baseline_runtime_trial,
                violation_count: ($trial_review[0].boundary_check.violations | length),
                side_signal_status: $trial_review[0].runtime_trial_summary.side_signal.status,
                side_signal_coverage: $trial_review[0].runtime_trial_summary.side_signal.coverage,
                side_signal_latency_ms: $trial_review[0].runtime_trial_summary.side_signal.latency_ms,
                returned_order_source: $trial_review[0].runtime_trial_summary.returned_order.source,
                baseline_returned: $trial_review[0].runtime_trial_summary.returned_order.baseline_returned,
                hash_matches_baseline: $trial_review[0].runtime_trial_summary.returned_order.hash_matches_baseline,
                raw_query_included: $trial_review[0].input_contract.raw_query_included,
                raw_keys_included: $trial_review[0].input_contract.raw_keys_included,
                content_included: $trial_review[0].input_contract.content_included,
                side_signal_raw_included: $trial_review[0].input_contract.side_signal_raw_included,
                approval_state: $trial_review[0].approval_state,
                runtime_adapter_approved: $trial_review[0].runtime_adapter_approved,
                approval_writes_allowed: $trial_review[0].approval_writes_allowed,
                writes_approval: $trial_review[0].writes_approval,
                calls_memory_search: $trial_review[0].calls_memory_search,
                runs_biocortex: $trial_review[0].runs_biocortex,
                registers_embedding_backend: $trial_review[0].registers_embedding_backend,
                changes_memory_search_order: $trial_review[0].changes_memory_search_order,
                ordering_behavior_connected: $trial_review[0].ordering_behavior_connected,
                may_implement_ordering_now: $trial_review[0].may_implement_ordering_now
            },
            order_diff_packet:
                if $order_diff[0] == null then
                    {
                        provided: false,
                        required: false,
                        note: "optional_hash_only_evidence_not_provided"
                    }
                else
                    {
                        provided: true,
                        required: false,
                        schema: $order_diff[0].schema,
                        read_only: $order_diff[0].read_only,
                        order_diff_packet: $order_diff[0].order_diff_packet,
                        source_packet_consumer: $order_diff[0].source_packet_consumer,
                        comparison_scope: $order_diff[0].comparison_scope,
                        source_kind: $order_diff[0].review_target.source_kind,
                        diff_ready: $order_diff[0].boundary_check.diff_ready,
                        violation_count: ($order_diff[0].boundary_check.violations | length),
                        order_hashes_comparable:
                            $order_diff[0].order_comparison.hash_diff.order_hashes_comparable,
                        order_hash_changed:
                            $order_diff[0].order_comparison.hash_diff.order_hash_changed,
                        top_key_hashes_comparable:
                            $order_diff[0].order_comparison.hash_diff.top_key_hashes_comparable,
                        top_key_changed:
                            $order_diff[0].order_comparison.hash_diff.top_key_changed,
                        expected_rank_delta_advisory_minus_baseline:
                            $order_diff[0].order_comparison.expected_key_rank.rank_delta_advisory_minus_baseline,
                        expected_rank_direction:
                            $order_diff[0].order_comparison.expected_key_rank.direction,
                        expected_regressed:
                            $order_diff[0].order_comparison.expected_key_rank.regressed,
                        returned_order_source:
                            $order_diff[0].order_comparison.returned_order.source,
                        baseline_returned:
                            $order_diff[0].order_comparison.returned_order.baseline_returned,
                        hash_matches_baseline:
                            $order_diff[0].order_comparison.returned_order.hash_matches_baseline,
                        actual_return_order_changed:
                            $order_diff[0].order_comparison.returned_order.actual_return_order_changed,
                        top_k_overlap:
                            $order_diff[0].order_comparison.unavailable_metrics.top_k_overlap,
                        per_key_movements:
                            $order_diff[0].order_comparison.unavailable_metrics.per_key_movements,
                        raw_query_included: $order_diff[0].input_contract.raw_query_included,
                        raw_keys_included: $order_diff[0].input_contract.raw_keys_included,
                        content_included: $order_diff[0].input_contract.content_included,
                        side_signal_raw_included: $order_diff[0].input_contract.side_signal_raw_included,
                        approval_state: $order_diff[0].approval_state,
                        runtime_adapter_approved: $order_diff[0].runtime_adapter_approved,
                        approval_writes_allowed: $order_diff[0].approval_writes_allowed,
                        writes_approval: $order_diff[0].writes_approval,
                        calls_memory_search: $order_diff[0].calls_memory_search,
                        runs_biocortex: $order_diff[0].runs_biocortex,
                        registers_embedding_backend: $order_diff[0].registers_embedding_backend,
                        changes_memory_search_order: $order_diff[0].changes_memory_search_order,
                        ordering_behavior_connected: $order_diff[0].ordering_behavior_connected,
                        may_implement_ordering_now: $order_diff[0].may_implement_ordering_now
                    }
                end,
            docs: {
                runtime_proof: "docs/design/BIOCORTEX_RETRIEVAL_RUNTIME_PROOF_2026_06_11.md",
                default_influence_contract: "docs/design/BIOCORTEX_RETRIEVAL_DEFAULT_INFLUENCE_CONTRACT_2026_06_11.md",
                opt_in_experiment_plan: "docs/design/BIOCORTEX_RETRIEVAL_OPT_IN_EXPERIMENT_PLAN_2026_06_11.md"
            }
        },
        current_permissions: {
            may_implement_opt_in_experiment: $plan_implementation_allowed,
            may_change_default_calls_without_opt_in: false,
            may_change_default_retrieval_order: false,
            may_affect_hybrid_or_semantic: false
        },
        requested_permission_if_human_authorizes: {
            may_implement_feature_gate: "biocortex-retrieval-opt-in",
            may_add_runtime_enable_env: "AB_BIOCORTEX_RETRIEVAL_OPT_IN",
            may_add_per_call_opt_in_surface: true,
            may_affect_only_explicitly_opted_in_fts_calls: true,
            must_keep_operator_disable: "AB_BIOCORTEX_RETRIEVAL_DISABLE",
            must_return_baseline_without_per_call_opt_in: true,
            must_return_baseline_on_absent_error_timeout_low_coverage_malformed_rows: true,
            requires_post_implementation_review_before_use: true,
            requires_runtime_trial_review_packet: true
        },
        not_requested: [
            "default_retrieval_influence_fts",
            "default_retrieval_influence_hybrid",
            "default_retrieval_influence_semantic",
            "default_search_order_change_allowed",
            "runtime_adapter_approved"
        ],
        human_decision_options: [
            "authorize_opt_in_experiment_implementation",
            "reject_opt_in_experiment",
            "request_more_evidence"
        ],
        valid_authorization_text_must_include: [
            "opt_in_experiment",
            "commit_under_review",
            "no_default_retrieval_influence",
            "AB_BIOCORTEX_RETRIEVAL_DISABLE_remains_kill_switch"
        ]
    }' > "$request_packet"

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
    and .opt_in_plan.status == "redacted_order_artifact_implemented"
    and .opt_in_plan.approval_state == "opt_in_implementation_authorized"
    and .opt_in_plan.order_diff_packet_implemented == true
    and .opt_in_plan.authorization_request_order_diff_evidence_implemented == true
    and .opt_in_plan.redacted_order_artifact_implemented == true
    and .opt_in_plan.implemented_gate_skeleton.ordering_behavior_connected == false
    and .opt_in_plan.implemented_gate_skeleton.may_change_search_order_now == false
    and .opt_in_plan.implemented_audit_shape.schema == "agent_bridge.biocortex_retrieval.opt_in_call_audit.v0"
    and .opt_in_plan.implemented_audit_shape.raw_keys_included == false
    and .opt_in_plan.implemented_audit_shape.content_included == false
    and .opt_in_plan.implemented_audit_shape.ordering_behavior_connected == false
    and .opt_in_plan.implemented_status_surface.mcp_tool == "biocortex_retrieval_opt_in_status"
    and .opt_in_plan.implemented_status_surface.raw_keys_included == false
    and .opt_in_plan.implemented_status_surface.content_included == false
    and .opt_in_plan.implemented_status_surface.ordering_behavior_connected == false
    and .opt_in_plan.implemented_store_contract.schema == "agent_bridge.store.memory_search.biocortex_opt_in_contract.v0"
    and .opt_in_plan.implemented_store_contract.authorized_mode == "fts"
    and .opt_in_plan.implemented_store_contract.baseline_completed_required == true
    and .opt_in_plan.implemented_store_contract.zero_hit_baseline_is_completed == true
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
    and .opt_in_plan.implemented_review_packet_consumer.mcp_tool == "biocortex_retrieval_opt_in_review_packet"
    and .opt_in_plan.implemented_review_packet_consumer.schema == "agent_bridge.biocortex_retrieval.opt_in_review_packet.v0"
    and .opt_in_plan.implemented_review_packet_consumer.read_only == true
    and .opt_in_plan.implemented_review_packet_consumer.dry_run_consumer == true
    and .opt_in_plan.implemented_review_packet_consumer.raw_dry_run_plan_included == false
    and .opt_in_plan.implemented_review_packet_consumer.raw_query_included == false
    and .opt_in_plan.implemented_review_packet_consumer.raw_keys_included == false
    and .opt_in_plan.implemented_review_packet_consumer.content_included == false
    and .opt_in_plan.implemented_review_packet_consumer.reports_boundary_violations == true
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
    and .opt_in_plan.experiment.mode == "fts_only"
    and .opt_in_plan.experiment.affected_call_site.function == "SqliteStore::memory_search"
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
    and (
        .evidence.order_diff_packet.provided == false
        or (
            .evidence.order_diff_packet.required == false
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
        )
    )
    and .current_permissions.may_implement_opt_in_experiment == true
    and .current_permissions.may_change_default_retrieval_order == false
    and .requested_permission_if_human_authorizes.may_affect_only_explicitly_opted_in_fts_calls == true
    and .requested_permission_if_human_authorizes.requires_runtime_trial_review_packet == true
    and (.not_requested | index("default_retrieval_influence_fts"))
    and (.not_requested | index("runtime_adapter_approved"))
' "$request_packet" >/dev/null

cat > "$out_dir/forum-post-template.md" <<EOF
BioCortex opt-in experiment authorization request prepared.

Request packet: opt-in-authorization-request.json
Commit under review: $commit
Branch: $branch
Host: $target_host
Reviewer: ${reviewer:-<required>}
Requester: $requester
Requested scope: opt_in_experiment

This packet is not an approval writer. It reflects:
- approval_state=$plan_approval_state
- authorization_state=$plan_authorization_state
- runtime_adapter_approved=false
- default_search_order_change_allowed=false
- implementation_allowed=$plan_implementation_allowed
- runtime trial review packet included=true
- order diff packet included=$(if [[ -n "$order_diff_packet" ]]; then printf 'true'; else printf 'false'; fi)

The allowed implementation scope is only an FTS-only, per-call opt-in
experiment behind a feature/runtime gate. It does not authorize default
retrieval influence, hybrid influence, semantic influence, or any behavior
without explicit per-call opt-in.
EOF

cat > "$out_dir/memory-note-template.md" <<EOF
BioCortex opt-in experiment authorization request prepared for commit $commit.

Status: request prepared/status reflected. The packet preserves
runtime_adapter_approved=false, default_search_order_change_allowed=false, and
implementation_allowed=$plan_implementation_allowed.

Runtime trial review packet evidence included: true.
Order diff packet evidence included: $(if [[ -n "$order_diff_packet" ]]; then printf 'true'; else printf 'false'; fi).

Requested scope: opt_in_experiment.
Not requested: default retrieval influence, hybrid influence, semantic influence.

Packet path at generation time: $request_packet
Forum decision post id: ${forum_decision_post_id:-<required>}
Memory key: ${memory_key:-<required>}
EOF

cat > "$out_dir/README.md" <<EOF
# BioCortex Opt-In Authorization Request

Generated: $ts

Files:
- opt-in-authorization-request.json
- forum-post-template.md
- memory-note-template.md

This bundle is review preparation only. It is not approval state and it does
not change retrieval behavior. It includes runtime trial review evidence, but
that evidence does not approve runtime influence or ordering behavior. When
provided, order-diff evidence is hash-only and optional.
EOF

printf 'authorization_request_bundle=%s\n' "$out_dir"
printf 'request_packet=%s\n' "$request_packet"
