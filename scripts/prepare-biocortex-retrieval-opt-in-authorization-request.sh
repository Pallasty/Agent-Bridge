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
redacted_order_artifact=""
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
  --redacted-order-artifact PATH Optional JSON from retrieval-opt-in-redacted-order-artifact.
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
        --redacted-order-artifact) redacted_order_artifact="$2"; shift 2 ;;
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
if [[ -n "$redacted_order_artifact" && ! -f "$redacted_order_artifact" ]]; then
    echo "redacted order artifact not found: $redacted_order_artifact" >&2
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
redacted_order_artifact_for_jq="$redacted_order_artifact"
if [[ -z "$redacted_order_artifact_for_jq" ]]; then
    redacted_order_artifact_for_jq="$out_dir/.redacted-order-artifact-absent.json"
    printf 'null\n' > "$redacted_order_artifact_for_jq"
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
    --slurpfile redacted_order "$redacted_order_artifact_for_jq" \
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
        accepts_optional_redacted_order_artifact: true,
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
            redacted_order_artifact:
                if $redacted_order[0] == null then
                    {
                        provided: false,
                        required: false,
                        note: "optional_redacted_order_artifact_not_provided"
                    }
                else
                    {
                        provided: true,
                        required: false,
                        schema: $redacted_order[0].schema,
                        read_only: $redacted_order[0].read_only,
                        redacted_order_artifact: $redacted_order[0].redacted_order_artifact,
                        source_packet_consumer: $redacted_order[0].source_packet_consumer,
                        comparison_scope: $redacted_order[0].comparison_scope,
                        source_kind: $redacted_order[0].review_target.source_kind,
                        artifact_ready: $redacted_order[0].boundary_check.artifact_ready,
                        violation_count: ($redacted_order[0].boundary_check.violations | length),
                        redacted_rows_comparable:
                            $redacted_order[0].boundary_check.redacted_rows_comparable,
                        baseline_rank_row_count:
                            ($redacted_order[0].redacted_order_comparison.baseline_order.rank_rows | length),
                        advisory_rank_row_count:
                            ($redacted_order[0].redacted_order_comparison.advisory_order.rank_rows | length),
                        top1_overlap_count:
                            ([$redacted_order[0].redacted_order_comparison.top_k_overlap[]? | select(.k == 1) | .overlap_count][0] // null),
                        top1_jaccard:
                            ([$redacted_order[0].redacted_order_comparison.top_k_overlap[]? | select(.k == 1) | .jaccard][0] // null),
                        top3_overlap_count:
                            ([$redacted_order[0].redacted_order_comparison.top_k_overlap[]? | select(.k == 3) | .overlap_count][0] // null),
                        top3_jaccard:
                            ([$redacted_order[0].redacted_order_comparison.top_k_overlap[]? | select(.k == 3) | .jaccard][0] // null),
                        improved_count:
                            $redacted_order[0].redacted_order_comparison.rank_delta_distribution.improved_count,
                        regressed_count:
                            $redacted_order[0].redacted_order_comparison.rank_delta_distribution.regressed_count,
                        unchanged_count:
                            $redacted_order[0].redacted_order_comparison.rank_delta_distribution.unchanged_count,
                        missing_baseline_count:
                            $redacted_order[0].redacted_order_comparison.rank_delta_distribution.missing_baseline_count,
                        missing_advisory_count:
                            $redacted_order[0].redacted_order_comparison.rank_delta_distribution.missing_advisory_count,
                        max_abs_delta:
                            $redacted_order[0].redacted_order_comparison.rank_delta_distribution.max_abs_delta,
                        comparable_key_count:
                            $redacted_order[0].redacted_order_comparison.rank_delta_distribution.comparable_key_count,
                        per_key_movement_count:
                            ($redacted_order[0].redacted_order_comparison.per_key_movements | length),
                        returned_order_source:
                            $redacted_order[0].redacted_order_comparison.returned_order.source,
                        baseline_returned:
                            $redacted_order[0].redacted_order_comparison.returned_order.baseline_returned,
                        hash_matches_baseline:
                            $redacted_order[0].redacted_order_comparison.returned_order.hash_matches_baseline,
                        actual_return_order_changed:
                            $redacted_order[0].redacted_order_comparison.returned_order.actual_return_order_changed,
                        raw_query_included: $redacted_order[0].input_contract.raw_query_included,
                        raw_keys_included: $redacted_order[0].input_contract.raw_keys_included,
                        raw_order_keys_included: $redacted_order[0].input_contract.raw_order_keys_included,
                        content_included: $redacted_order[0].input_contract.content_included,
                        side_signal_raw_included: $redacted_order[0].input_contract.side_signal_raw_included,
                        redacted_key_hashes_in_artifact:
                            $redacted_order[0].input_contract.hashes_included,
                        copies_key_hashes_to_request: false,
                        copies_redacted_rank_rows: false,
                        approval_state: $redacted_order[0].approval_state,
                        runtime_adapter_approved: $redacted_order[0].runtime_adapter_approved,
                        approval_writes_allowed: $redacted_order[0].approval_writes_allowed,
                        writes_approval: $redacted_order[0].writes_approval,
                        calls_memory_search: $redacted_order[0].calls_memory_search,
                        runs_biocortex: $redacted_order[0].runs_biocortex,
                        registers_embedding_backend: $redacted_order[0].registers_embedding_backend,
                        changes_memory_search_order: $redacted_order[0].changes_memory_search_order,
                        ordering_behavior_connected: $redacted_order[0].ordering_behavior_connected,
                        may_implement_ordering_now: $redacted_order[0].may_implement_ordering_now
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
            requires_runtime_trial_review_packet: true,
            accepts_optional_order_diff_packet: true,
            accepts_optional_redacted_order_artifact: true
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
    and .accepts_optional_redacted_order_artifact == true
    and .opt_in_plan.status == "runtime_readiness_packet_implemented"
    and .opt_in_plan.approval_state == "opt_in_implementation_authorized"
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
    and .opt_in_plan.implemented_authorization_request_redacted_order_artifact_evidence.script == "scripts/prepare-biocortex-retrieval-opt-in-authorization-request.sh"
    and .opt_in_plan.implemented_authorization_request_redacted_order_artifact_evidence.optional_input == "agent_bridge.biocortex_retrieval.opt_in_redacted_order_artifact.v0"
    and .opt_in_plan.implemented_authorization_request_redacted_order_artifact_evidence.evidence_path == "evidence.redacted_order_artifact"
    and .opt_in_plan.implemented_authorization_request_redacted_order_artifact_evidence.required == false
    and .opt_in_plan.implemented_authorization_request_redacted_order_artifact_evidence.summary_only == true
    and .opt_in_plan.implemented_authorization_request_redacted_order_artifact_evidence.copies_key_hashes == false
    and .opt_in_plan.implemented_authorization_request_redacted_order_artifact_evidence.copies_redacted_rank_rows == false
    and .opt_in_plan.implemented_authorization_request_redacted_order_artifact_evidence.reports_top_k_overlap == true
    and .opt_in_plan.implemented_authorization_request_redacted_order_artifact_evidence.reports_rank_delta_distribution == true
    and .opt_in_plan.implemented_authorization_request_redacted_order_artifact_evidence.approval_state == "not_approved"
    and .opt_in_plan.implemented_authorization_request_redacted_order_artifact_evidence.runtime_adapter_approved == false
    and .opt_in_plan.implemented_authorization_request_redacted_order_artifact_evidence.calls_memory_search == false
    and .opt_in_plan.implemented_authorization_request_redacted_order_artifact_evidence.runs_biocortex == false
    and .opt_in_plan.implemented_authorization_request_redacted_order_artifact_evidence.changes_memory_search_order == false
    and .opt_in_plan.implemented_authorization_request_redacted_order_artifact_evidence.ordering_behavior_connected == false
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
    and (
        .evidence.redacted_order_artifact.provided == false
        or (
            .evidence.redacted_order_artifact.required == false
            and .evidence.redacted_order_artifact.schema == "agent_bridge.biocortex_retrieval.opt_in_redacted_order_artifact.v0"
            and .evidence.redacted_order_artifact.read_only == true
            and .evidence.redacted_order_artifact.redacted_order_artifact == true
            and .evidence.redacted_order_artifact.source_packet_consumer == true
            and .evidence.redacted_order_artifact.source_kind == "runtime_trial_review_packet"
            and .evidence.redacted_order_artifact.artifact_ready == true
            and .evidence.redacted_order_artifact.violation_count == 0
            and .evidence.redacted_order_artifact.redacted_rows_comparable == true
            and (.evidence.redacted_order_artifact.baseline_rank_row_count | type) == "number"
            and (.evidence.redacted_order_artifact.advisory_rank_row_count | type) == "number"
            and (.evidence.redacted_order_artifact.top1_overlap_count | type) == "number"
            and ((.evidence.redacted_order_artifact.top1_jaccard | type) == "number" or .evidence.redacted_order_artifact.top1_jaccard == null)
            and (.evidence.redacted_order_artifact.per_key_movement_count | type) == "number"
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
        )
    )
    and .current_permissions.may_implement_opt_in_experiment == true
    and .current_permissions.may_change_default_retrieval_order == false
    and .requested_permission_if_human_authorizes.may_affect_only_explicitly_opted_in_fts_calls == true
    and .requested_permission_if_human_authorizes.requires_runtime_trial_review_packet == true
    and .requested_permission_if_human_authorizes.accepts_optional_order_diff_packet == true
    and .requested_permission_if_human_authorizes.accepts_optional_redacted_order_artifact == true
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
- redacted order artifact included=$(if [[ -n "$redacted_order_artifact" ]]; then printf 'true'; else printf 'false'; fi)

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
Redacted order artifact evidence included: $(if [[ -n "$redacted_order_artifact" ]]; then printf 'true'; else printf 'false'; fi).

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
provided, order-diff evidence is hash-only and optional. When provided,
redacted-order artifact evidence is summary-only and does not copy key hashes
or redacted rank rows into the request packet.
EOF

printf 'authorization_request_bundle=%s\n' "$out_dir"
printf 'request_packet=%s\n' "$request_packet"
