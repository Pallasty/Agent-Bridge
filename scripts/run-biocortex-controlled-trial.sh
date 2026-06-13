#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"

usage() {
    cat <<'USAGE'
usage: scripts/run-biocortex-controlled-trial.sh [flags]

Runs the lightweight BioCortex explicit opt-in FTS controlled trial.

The runner preserves the approval chain used by the full verifier, but keeps
the scope focused on controlled ranking evidence:

  1. build baseline-preserving trial/review evidence;
  2. prepare implementation authorization and post-implementation gates;
  3. consume a runtime-influence decision fixture for explicit opt-in FTS only;
  4. seed non-production stores for movement and coverage fixtures;
  5. emit redacted JSON artifacts plus a compact Markdown report.

It writes only to the selected output directory and temporary non-production
SQLite DBs. It never writes Agent-Bridge approval state, mutates the default
Agent-Bridge DB, changes default memory_search order, or exposes raw fixture
query/key/content data in redacted outputs.

Flags:
  --out-dir PATH       Artifact directory. Default: target/biocortex-controlled-trial-<utc-ts>.
  --checkout PATH      Local biocortex-rs checkout.
  --samples N          Runtime-boundary proof latency samples. Default: 1.
  --reviewer TEXT      Reviewer label stored in redacted packets. Default: controlled-trial-runner.
  --commit REF         Commit label stored in redacted packets. Default: current HEAD.
  -h, --help           Show this help.
USAGE
}

ts="$(date -u +%Y%m%dT%H%M%SZ)"
generated_at="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
out_dir="target/biocortex-controlled-trial-$ts"
biocortex_rs="${AB_BIOCORTEX_RS:-${BIOCORTEX_RS:-}}"
samples=1
reviewer="controlled-trial-runner"
commit="$(git rev-parse HEAD)"

while [[ $# -gt 0 ]]; do
    case "$1" in
        --out-dir) out_dir="$2"; shift 2 ;;
        --checkout) biocortex_rs="$2"; shift 2 ;;
        --samples) samples="$2"; shift 2 ;;
        --reviewer) reviewer="$2"; shift 2 ;;
        --commit) commit="$2"; shift 2 ;;
        -h|--help) usage; exit 0 ;;
        *) echo "unknown flag: $1" >&2; usage >&2; exit 2 ;;
    esac
done

if [[ ! "$samples" =~ ^[0-9]+$ ]] || [[ "$samples" -lt 1 ]]; then
    echo "--samples must be a positive integer" >&2
    exit 2
fi

if [[ -z "$biocortex_rs" ]]; then
    for candidate in \
        "$repo_root/../biocortex-rs" \
        /Data/CascadeProjects/biocortex-rs \
        /Programs/Users/Pallasting/Documents/CascadeProjects/biocortex-rs
    do
        if [[ -f "$candidate/Cargo.toml" ]]; then
            biocortex_rs="$candidate"
            break
        fi
    done
fi

if [[ -z "$biocortex_rs" || ! -f "$biocortex_rs/Cargo.toml" ]]; then
    echo "Could not find biocortex-rs checkout. Use --checkout /path/to/biocortex-rs." >&2
    exit 2
fi

mkdir -p "$out_dir/inputs" "$out_dir/db"

run() {
    printf '\n==> %s\n' "$*" >&2
    "$@"
}

json_run() {
    local output="$1"
    shift
    run "$@" > "$output"
}

assert_json() {
    local expr="$1"
    local file="$2"
    jq -e "$expr" "$file" >/dev/null
}

leak_guard() {
    local file="$1"
    local pattern='controlled trial runtime query|controlled_trial_runtime_key|controlled trial runtime content|cortexdelta|cortexepsilon|cortexzeta|cortexeta|cortextheta|cortexiota|controlled_order_baseline_high|controlled_order_biocortex_target|target anchor|baseline anchor|axonalpha|axonbeta|axongamma|axondelta|axonepsilon|axonzeta|dendritealpha|dendritebeta|dendritegamma|dendritedelta|dendriteepsilon|dendritezeta|gliaalph|gliabet|gliagam|gliadel|gliaeps|gliazet|myelinalpha|myelinbeta|myelingamma|myelindelta|myelinepsilon|myelinzeta|synapsealpha|synapsebeta|synapsegamma|synapsedelta|synapseepsilon|synapsezeta|expanded_corpus_baseline_focus|expanded_corpus_target_span|baseline focus|target span'
    if grep -Eiq "$pattern" "$file"; then
        echo "redacted artifact leaked raw fixture/query/key/content data: $file" >&2
        exit 1
    fi
}

base_cmd=(cargo run -p ab-bridge --no-default-features --)
opt_in_cmd=(cargo run -p ab-bridge --no-default-features --features biocortex-retrieval-opt-in --)

opt_in_plan="docs/design/fixtures/biocortex-retrieval-opt-in-experiment-plan-2026-06-11.json"
auth_decision="docs/design/fixtures/biocortex-retrieval-opt-in-authorization-decision-2026-06-11.json"
movement_fixture="docs/design/fixtures/biocortex-retrieval-opt-in-controlled-order-fixture-2026-06-12.json"
coverage_fixture="docs/design/fixtures/biocortex-retrieval-opt-in-expanded-controlled-corpus-2026-06-12.json"

for required in "$opt_in_plan" "$auth_decision" "$movement_fixture" "$coverage_fixture"; do
    if [[ ! -f "$required" ]]; then
        echo "required fixture not found: $required" >&2
        exit 2
    fi
done

dry_run="$out_dir/01-dry-run.json"
review_packet="$out_dir/02-review-packet.json"
execution_packet="$out_dir/03-execution-packet.json"
runtime_trial_input="$out_dir/inputs/runtime-trial-input.json"
runtime_trial="$out_dir/04-runtime-trial.json"
runtime_trial_review="$out_dir/05-runtime-trial-review-packet.json"
order_diff="$out_dir/06-order-diff-packet.json"
redacted_order="$out_dir/07-redacted-order-artifact.json"
runtime_proof_dir="$out_dir/runtime-boundary-proof"
auth_request_dir="$out_dir/authorization-request"
auth_decision_packet="$out_dir/08-authorization-decision-packet.json"
post_impl_gate="$out_dir/09-post-implementation-review-gate.json"
runtime_review_request="$out_dir/10-runtime-influence-review-request.json"
runtime_influence_decision="$out_dir/inputs/runtime-influence-decision.json"
runtime_decision_packet="$out_dir/11-runtime-influence-decision-packet.json"
movement_run="$out_dir/12-controlled-order-movement.json"
coverage_run="$out_dir/13-expanded-coverage.json"
evidence_aggregate="$out_dir/14-redacted-evidence-aggregate.json"
runtime_review_request_with_aggregate="$out_dir/15-runtime-influence-review-request-with-aggregate.json"
runtime_decision_packet_with_aggregate="$out_dir/16-runtime-influence-decision-packet-with-aggregate.json"
summary_json="$out_dir/controlled-trial-summary.json"
report_md="$out_dir/CONTROLLED_TRIAL_REPORT.md"

json_run "$dry_run" env AB_BIOCORTEX_RETRIEVAL_OPT_IN=1 \
    "${opt_in_cmd[@]}" \
    bio-cortex retrieval-opt-in-dry-run \
    --mode fts \
    --per-call-opt-in \
    --query "controlled trial dry run query" \
    --baseline-key controlled_trial_baseline_key \
    --baseline-completed \
    --coverage-threshold 0.5 \
    --json
assert_json '.schema == "agent_bridge.biocortex_retrieval.opt_in_dry_run_plan.v0" and .gate.status == "ready_for_explicit_opt_in_experiment" and .baseline_order.raw_keys_included == false and .baseline_order.content_included == false' "$dry_run"
leak_guard "$dry_run"

json_run "$review_packet" "${base_cmd[@]}" \
    bio-cortex retrieval-opt-in-review-packet \
    --dry-run-json "$dry_run" \
    --reviewer "$reviewer" \
    --commit "$commit" \
    --forum-post-id controlled-trial-local \
    --memory-key controlled-trial-local \
    --json
assert_json '.schema == "agent_bridge.biocortex_retrieval.opt_in_review_packet.v0" and .boundary_check.review_ready == true and (.boundary_check.violations | length) == 0 and .input_contract.raw_query_included == false and .input_contract.raw_keys_included == false and .input_contract.content_included == false' "$review_packet"
leak_guard "$review_packet"

json_run "$execution_packet" "${base_cmd[@]}" \
    bio-cortex retrieval-opt-in-execution-packet \
    --review-packet-json "$review_packet" \
    --per-call-opt-in \
    --attempt-id controlled-trial-execution \
    --commit "$commit" \
    --json
assert_json '.schema == "agent_bridge.biocortex_retrieval.opt_in_execution_packet.v0" and .preflight.preflight_passed_for_baseline_only_contract == true and .changes_memory_search_order == false' "$execution_packet"
leak_guard "$execution_packet"

jq -n '{
    query: "controlled trial runtime query",
    expected_key: "controlled_trial_runtime_key",
    candidates: [
        {
            key: "controlled_trial_runtime_key",
            content: "controlled trial runtime content"
        }
    ]
}' > "$runtime_trial_input"

json_run "$runtime_trial" env AB_BIOCORTEX_RETRIEVAL_OPT_IN=1 \
    "${opt_in_cmd[@]}" \
    bio-cortex retrieval-opt-in-runtime-trial \
    --execution-packet-json "$execution_packet" \
    --input-json "$runtime_trial_input" \
    --checkout "$biocortex_rs" \
    --timeout-ms 30000 \
    --coverage-threshold 0.5 \
    --attempt-id controlled-trial-runtime \
    --commit "$commit" \
    --json
assert_json '.schema == "agent_bridge.biocortex_retrieval.opt_in_runtime_trial.v0" and .runtime_preflight.side_signal_trial_allowed == true and .returned_order.source == "baseline" and .changes_memory_search_order == false and .input_contract.raw_query_included == false and .input_contract.raw_keys_included == false and .input_contract.content_included == false and .protected_adapter_contract.raw_query_included == false and .protected_adapter_contract.raw_keys_included == false and .protected_adapter_contract.content_included == false' "$runtime_trial"
leak_guard "$runtime_trial"

json_run "$runtime_trial_review" "${base_cmd[@]}" \
    bio-cortex retrieval-opt-in-runtime-trial-review-packet \
    --runtime-trial-json "$runtime_trial" \
    --reviewer "$reviewer" \
    --commit "$commit" \
    --forum-post-id controlled-trial-local \
    --memory-key controlled-trial-local \
    --json
assert_json '.schema == "agent_bridge.biocortex_retrieval.opt_in_runtime_trial_review_packet.v0" and .boundary_check.review_ready_for_baseline_runtime_trial == true and (.boundary_check.violations | length) == 0 and .input_contract.raw_query_included == false and .input_contract.raw_keys_included == false and .input_contract.content_included == false and .input_contract.side_signal_raw_included == false' "$runtime_trial_review"
leak_guard "$runtime_trial_review"

json_run "$order_diff" "${base_cmd[@]}" \
    bio-cortex retrieval-opt-in-order-diff-packet \
    --source-json "$runtime_trial_review" \
    --reviewer "$reviewer" \
    --commit "$commit" \
    --forum-post-id controlled-trial-local \
    --memory-key controlled-trial-local \
    --json
assert_json '.schema == "agent_bridge.biocortex_retrieval.opt_in_order_diff_packet.v0" and .boundary_check.diff_ready == true and .calls_memory_search == false and .runs_biocortex == false' "$order_diff"
leak_guard "$order_diff"

json_run "$redacted_order" "${base_cmd[@]}" \
    bio-cortex retrieval-opt-in-redacted-order-artifact \
    --source-json "$runtime_trial_review" \
    --reviewer "$reviewer" \
    --commit "$commit" \
    --forum-post-id controlled-trial-local \
    --memory-key controlled-trial-local \
    --json
assert_json '.schema == "agent_bridge.biocortex_retrieval.opt_in_redacted_order_artifact.v0" and .boundary_check.artifact_ready == true and .input_contract.raw_query_included == false and .input_contract.raw_order_keys_included == false' "$redacted_order"
leak_guard "$redacted_order"

run scripts/prove-biocortex-retrieval-runtime-boundary.sh \
    --out-dir "$runtime_proof_dir" \
    --checkout "$biocortex_rs" \
    --samples "$samples"
assert_json '.schema == "agent_bridge.biocortex_retrieval.runtime_boundary_proof.v0" and .boundary.changes_memory_search_order == false and .runtime_adapter_approved == false' "$runtime_proof_dir/proof-summary.json"

run scripts/prepare-biocortex-retrieval-opt-in-authorization-request.sh \
    --out-dir "$auth_request_dir" \
    --reviewer "$reviewer" \
    --runtime-proof-summary "$runtime_proof_dir/proof-summary.json" \
    --runtime-trial-review-packet "$runtime_trial_review" \
    --order-diff-packet "$order_diff" \
    --redacted-order-artifact "$redacted_order" \
    --memory-key controlled-trial-local \
    --forum-decision-post-id controlled-trial-local
assert_json '.schema == "agent_bridge.biocortex_retrieval.opt_in_authorization_request.v0" and .implementation_allowed == true and .runtime_adapter_approved == false and .default_search_order_change_allowed == false' "$auth_request_dir/opt-in-authorization-request.json"
leak_guard "$auth_request_dir/opt-in-authorization-request.json"

json_run "$auth_decision_packet" "${base_cmd[@]}" \
    bio-cortex retrieval-opt-in-authorization-decision-packet \
    --authorization-request-json "$auth_request_dir/opt-in-authorization-request.json" \
    --authorization-decision-json "$auth_decision" \
    --reviewer "$reviewer" \
    --commit "$commit" \
    --forum-post-id controlled-trial-local \
    --memory-key controlled-trial-local \
    --json
assert_json '.schema == "agent_bridge.biocortex_retrieval.opt_in_authorization_decision_packet.v0" and .decision_summary.implementation_allowed == true and .request_summary.implementation_allowed == true and .runtime_adapter_approved == false and .default_search_order_change_allowed == false and .input_contract.raw_query_included == false and .input_contract.raw_keys_included == false and .input_contract.content_included == false' "$auth_decision_packet"
leak_guard "$auth_decision_packet"

json_run "$post_impl_gate" "${base_cmd[@]}" \
    bio-cortex retrieval-opt-in-post-implementation-review-gate \
    --authorization-decision-packet-json "$auth_decision_packet" \
    --opt-in-plan-json "$opt_in_plan" \
    --reviewer "$reviewer" \
    --commit "$commit" \
    --forum-post-id controlled-trial-local \
    --memory-key controlled-trial-local \
    --json
assert_json '.schema == "agent_bridge.biocortex_retrieval.opt_in_post_implementation_review_gate.v0" and .boundary_check.ready_for_human_runtime_influence_review == true and .runtime_adapter_approved == false and .default_search_order_change_allowed == false' "$post_impl_gate"
leak_guard "$post_impl_gate"

json_run "$runtime_review_request" "${base_cmd[@]}" \
    bio-cortex retrieval-opt-in-runtime-influence-review-request \
    --post-implementation-review-gate-json "$post_impl_gate" \
    --redacted-order-artifact-json "$redacted_order" \
    --reviewer "$reviewer" \
    --commit "$commit" \
    --forum-post-id controlled-trial-local \
    --memory-key controlled-trial-local \
    --json
assert_json '.schema == "agent_bridge.biocortex_retrieval.opt_in_runtime_influence_review_request.v0" and .boundary_check.runtime_influence_review_request_ready == true and .implementation_allowed == false and .runtime_adapter_approved == false' "$runtime_review_request"
leak_guard "$runtime_review_request"

jq -n '{
    schema: "agent_bridge.biocortex_retrieval.opt_in_runtime_influence_review_decision.v0",
    decision: "authorized",
    authorization_state: "authorized",
    authorized_scope: "explicit_opt_in_fts_runtime_influence",
    human_decision_text: "controlled trial runner local runtime-influence decision fixture",
    runtime_adapter_approved: true,
    ordering_behavior_connection_authorized: true,
    default_search_order_change_allowed: false,
    default_retrieval_influence_authorized: false,
    hybrid_retrieval_influence_authorized: false,
    semantic_retrieval_influence_authorized: false,
    authorized_runtime_influence: {
        may_run_runtime_adapter_for_explicit_opt_in_fts: true,
        may_connect_ordering_behavior_for_explicit_opt_in_fts: true,
        may_affect_only_explicitly_opted_in_fts_calls: true,
        requires_per_call_opt_in: true,
        must_keep_baseline_candidate_recall: true,
        must_keep_default_calls_unchanged: true,
        must_keep_redacted_audit_only: true,
        must_keep_operator_disable: "AB_BIOCORTEX_RETRIEVAL_DISABLE",
        must_return_baseline_without_per_call_opt_in: true,
        must_fail_open_to_baseline: true
    },
    not_authorized: [
        "default_search_order_change_allowed",
        "default_retrieval_influence_fts",
        "default_retrieval_influence_hybrid",
        "default_retrieval_influence_semantic",
        "hybrid_retrieval_influence",
        "semantic_retrieval_influence",
        "affecting_calls_without_explicit_opt_in"
    ]
}' > "$runtime_influence_decision"

json_run "$runtime_decision_packet" "${base_cmd[@]}" \
    bio-cortex retrieval-opt-in-runtime-influence-decision-packet \
    --runtime-influence-review-request-json "$runtime_review_request" \
    --runtime-influence-decision-json "$runtime_influence_decision" \
    --reviewer "$reviewer" \
    --commit "$commit" \
    --forum-post-id controlled-trial-local \
    --memory-key controlled-trial-local \
    --json
assert_json '.schema == "agent_bridge.biocortex_retrieval.opt_in_runtime_influence_decision_packet.v0" and .implementation_allowed == true and .runtime_adapter_approved == true and .default_search_order_change_allowed == false and .default_calls_unchanged == true' "$runtime_decision_packet"
leak_guard "$runtime_decision_packet"

json_run "$movement_run" env AGENT_BRIDGE_DB="$out_dir/db/movement.db" AB_BIOCORTEX_RETRIEVAL_OPT_IN=1 \
    "${opt_in_cmd[@]}" \
    bio-cortex retrieval-opt-in-controlled-order-fixture \
    --runtime-influence-decision-packet-json "$runtime_decision_packet" \
    --fixture-json "$movement_fixture" \
    --allow-non-production-store-writes \
    --per-call-opt-in \
    --checkout "$biocortex_rs" \
    --limit 5 \
    --coverage-threshold 0.5 \
    --attempt-id controlled-trial-movement \
    --commit "$commit" \
    --json
assert_json '.schema == "agent_bridge.biocortex_retrieval.opt_in_controlled_order_fixture_run.v0" and .expected.met == true and .diagnostics.summary.actual_order_changed_count >= 1 and .default_search_order_change_allowed == false and .default_calls_unchanged == true' "$movement_run"
leak_guard "$movement_run"

json_run "$coverage_run" env AGENT_BRIDGE_DB="$out_dir/db/coverage.db" AB_BIOCORTEX_RETRIEVAL_OPT_IN=1 \
    "${opt_in_cmd[@]}" \
    bio-cortex retrieval-opt-in-controlled-order-fixture \
    --runtime-influence-decision-packet-json "$runtime_decision_packet" \
    --fixture-json "$coverage_fixture" \
    --allow-non-production-store-writes \
    --per-call-opt-in \
    --checkout "$biocortex_rs" \
    --limit 5 \
    --coverage-threshold 0.5 \
    --attempt-id controlled-trial-coverage \
    --commit "$commit" \
    --json
assert_json '.schema == "agent_bridge.biocortex_retrieval.opt_in_controlled_order_fixture_run.v0" and .expected.met == true and .diagnostics.summary.query_count >= 5 and .diagnostics.summary.experimental_source_count == .diagnostics.summary.query_count and .default_search_order_change_allowed == false and .default_calls_unchanged == true' "$coverage_run"
leak_guard "$coverage_run"

json_run "$evidence_aggregate" "${base_cmd[@]}" \
    bio-cortex retrieval-opt-in-redacted-evidence-aggregate \
    --movement-fixture-run-json "$movement_run" \
    --coverage-fixture-run-json "$coverage_run" \
    --reviewer "$reviewer" \
    --commit "$commit" \
    --forum-post-id controlled-trial-local \
    --memory-key controlled-trial-local \
    --json
assert_json '.schema == "agent_bridge.biocortex_retrieval.opt_in_redacted_evidence_aggregate.v0" and .interpretation.aggregate_evidence_ready == true and .interpretation.controlled_rank_movement_observed == true and .interpretation.expanded_coverage_without_additional_movement == true and .default_search_order_change_allowed == false' "$evidence_aggregate"
leak_guard "$evidence_aggregate"

json_run "$runtime_review_request_with_aggregate" "${base_cmd[@]}" \
    bio-cortex retrieval-opt-in-runtime-influence-review-request \
    --post-implementation-review-gate-json "$post_impl_gate" \
    --redacted-order-artifact-json "$redacted_order" \
    --redacted-evidence-aggregate-json "$evidence_aggregate" \
    --reviewer "$reviewer" \
    --commit "$commit" \
    --forum-post-id controlled-trial-local \
    --memory-key controlled-trial-local \
    --json
assert_json '.schema == "agent_bridge.biocortex_retrieval.opt_in_runtime_influence_review_request.v0" and .evidence_summary.redacted_evidence_aggregate_ready == true and .boundary_check.runtime_influence_review_request_ready == true and .default_search_order_change_allowed == false' "$runtime_review_request_with_aggregate"
leak_guard "$runtime_review_request_with_aggregate"

json_run "$runtime_decision_packet_with_aggregate" "${base_cmd[@]}" \
    bio-cortex retrieval-opt-in-runtime-influence-decision-packet \
    --runtime-influence-review-request-json "$runtime_review_request_with_aggregate" \
    --runtime-influence-decision-json "$runtime_influence_decision" \
    --reviewer "$reviewer" \
    --commit "$commit" \
    --forum-post-id controlled-trial-local \
    --memory-key controlled-trial-local \
    --json
assert_json '.schema == "agent_bridge.biocortex_retrieval.opt_in_runtime_influence_decision_packet.v0" and .request_summary.redacted_evidence_aggregate_ready == true and .implementation_allowed == true and .runtime_adapter_approved == true and .default_search_order_change_allowed == false and .default_calls_unchanged == true' "$runtime_decision_packet_with_aggregate"
leak_guard "$runtime_decision_packet_with_aggregate"

jq -n \
    --arg generated_at "$generated_at" \
    --arg commit "$commit" \
    --arg checkout "$biocortex_rs" \
    --arg out_dir "$out_dir" \
    --slurpfile movement "$movement_run" \
    --slurpfile coverage "$coverage_run" \
    --slurpfile aggregate "$evidence_aggregate" \
    --slurpfile review "$runtime_review_request_with_aggregate" \
    --slurpfile decision "$runtime_decision_packet_with_aggregate" \
    '{
        schema: "agent_bridge.biocortex_retrieval.controlled_trial_run_summary.v0",
        generated_at: $generated_at,
        read_only_summary: true,
        commit: $commit,
        biocortex_rs_checkout: $checkout,
        output_dir: $out_dir,
        status: (if $aggregate[0].interpretation.aggregate_evidence_ready == true then "controlled_trial_redacted_evidence_ready" else "controlled_trial_redacted_evidence_incomplete" end),
        movement: {
            expected_met: $movement[0].expected.met,
            seeded_memory_count: $movement[0].attempt.seeded_memory_count,
            query_count: $movement[0].diagnostics.summary.query_count,
            experimental_source_count: $movement[0].diagnostics.summary.experimental_source_count,
            actual_order_changed_count: $movement[0].diagnostics.summary.actual_order_changed_count,
            raw_flags_all_false: $movement[0].diagnostics.safety.raw_flags_all_false
        },
        coverage: {
            expected_met: $coverage[0].expected.met,
            seeded_memory_count: $coverage[0].attempt.seeded_memory_count,
            query_count: $coverage[0].diagnostics.summary.query_count,
            experimental_source_count: $coverage[0].diagnostics.summary.experimental_source_count,
            actual_order_changed_count: $coverage[0].diagnostics.summary.actual_order_changed_count,
            hash_matches_baseline_count: $coverage[0].diagnostics.summary.hash_matches_baseline_count,
            raw_flags_all_false: $coverage[0].diagnostics.safety.raw_flags_all_false
        },
        aggregate: {
            review_state: $aggregate[0].interpretation.review_state,
            aggregate_evidence_ready: $aggregate[0].interpretation.aggregate_evidence_ready,
            controlled_rank_movement_observed: $aggregate[0].interpretation.controlled_rank_movement_observed,
            expanded_coverage_without_additional_movement: $aggregate[0].interpretation.expanded_coverage_without_additional_movement,
            default_influence_ready: $aggregate[0].interpretation.default_influence_ready,
            human_review_required: $aggregate[0].interpretation.human_review_required,
            recommended_next_step: $aggregate[0].interpretation.recommended_next_step
        },
        runtime_review_request: {
            ready: $review[0].boundary_check.runtime_influence_review_request_ready,
            aggregate_ready: $review[0].evidence_summary.redacted_evidence_aggregate_ready,
            grants_request: $review[0].requested_authorization.this_packet_grants_request
        },
        runtime_decision_packet: {
            implementation_allowed: $decision[0].implementation_allowed,
            runtime_adapter_approved: $decision[0].runtime_adapter_approved,
            ordering_behavior_connection_authorized: $decision[0].ordering_behavior_connection_authorized,
            default_search_order_change_allowed: $decision[0].default_search_order_change_allowed,
            default_calls_unchanged: $decision[0].default_calls_unchanged
        },
        safety: {
            writes_approval: false,
            mutates_default_agent_bridge_db: false,
            raw_queries_included: false,
            raw_keys_included: false,
            content_included: false,
            side_signal_raw_included: false,
            default_search_order_change_allowed: false,
            default_calls_unchanged: true
        },
        artifacts: {
            movement_run: "12-controlled-order-movement.json",
            coverage_run: "13-expanded-coverage.json",
            redacted_evidence_aggregate: "14-redacted-evidence-aggregate.json",
            runtime_review_request_with_aggregate: "15-runtime-influence-review-request-with-aggregate.json",
            runtime_decision_packet_with_aggregate: "16-runtime-influence-decision-packet-with-aggregate.json"
        }
    }' > "$summary_json"
assert_json '.schema == "agent_bridge.biocortex_retrieval.controlled_trial_run_summary.v0" and .status == "controlled_trial_redacted_evidence_ready" and .movement.actual_order_changed_count >= 1 and .coverage.query_count >= 5 and .aggregate.aggregate_evidence_ready == true and .safety.default_search_order_change_allowed == false and .safety.default_calls_unchanged == true' "$summary_json"
leak_guard "$summary_json"

{
    echo "# BioCortex Controlled Opt-In Trial"
    echo
    echo "- generated_at: $(jq -r '.generated_at' "$summary_json")"
    echo "- status: $(jq -r '.status' "$summary_json")"
    echo "- commit: $(jq -r '.commit' "$summary_json")"
    echo "- output_dir: $(jq -r '.output_dir' "$summary_json")"
    echo
    echo "## Result"
    echo
    echo "- movement actual_order_changed_count: $(jq -r '.movement.actual_order_changed_count' "$summary_json")"
    echo "- coverage queries: $(jq -r '.coverage.query_count' "$summary_json")"
    echo "- coverage experimental_source_count: $(jq -r '.coverage.experimental_source_count' "$summary_json")"
    echo "- aggregate_evidence_ready: $(jq -r '.aggregate.aggregate_evidence_ready' "$summary_json")"
    echo "- recommended_next_step: $(jq -r '.aggregate.recommended_next_step' "$summary_json")"
    echo
    echo "## Boundary"
    echo
    echo "- default_search_order_change_allowed: $(jq -r '.safety.default_search_order_change_allowed' "$summary_json")"
    echo "- default_calls_unchanged: $(jq -r '.safety.default_calls_unchanged' "$summary_json")"
    echo "- raw_queries_included: $(jq -r '.safety.raw_queries_included' "$summary_json")"
    echo "- raw_keys_included: $(jq -r '.safety.raw_keys_included' "$summary_json")"
    echo "- content_included: $(jq -r '.safety.content_included' "$summary_json")"
    echo "- side_signal_raw_included: $(jq -r '.safety.side_signal_raw_included' "$summary_json")"
    echo
    echo "## Artifacts"
    echo
    jq -r '.artifacts | to_entries[] | "- \(.key): `\(.value)`"' "$summary_json"
} > "$report_md"
leak_guard "$report_md"

printf '\ncontrolled trial complete\n' >&2
printf 'summary_json=%s\n' "$summary_json"
printf 'report_md=%s\n' "$report_md"
