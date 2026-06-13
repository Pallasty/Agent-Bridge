#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"

usage() {
    cat <<'USAGE'
usage: scripts/run-biocortex-post-runtime-live-candidate.sh [flags]

Replays the BioCortex post-runtime live-candidate proof on a caller-selected
non-production store.

The runner expects an already authorized explicit opt-in FTS runtime influence
decision plus a runtime-readiness / transition-gate pair. It then:

  1. seeds the canonical controlled-order fixture into an isolated SQLite DB;
  2. proves the protected path can call BioCortex and move explicit opt-in FTS order;
  3. proves the transition-gated store and batch surfaces carry the same movement;
  4. verifies the conservative status surface remains side-effect free;
  5. emits redacted JSON artifacts plus a compact Markdown report.

It writes only to the selected output directory and the selected non-production
SQLite DB. It never writes Agent-Bridge approval state, mutates the default
Agent-Bridge DB, changes default memory_search order, or exposes raw fixture
query/key/content data in runner summaries.

Flags:
  --out-dir PATH              Artifact directory. Default: target/biocortex-post-runtime-live-candidate-<utc-ts>.
  --checkout PATH             Local biocortex-rs checkout.
  --decision-packet PATH      Runtime influence decision packet JSON.
  --readiness-packet PATH     Runtime readiness packet JSON.
  --transition-gate PATH      Runtime transition gate JSON.
  --fixture PATH              Controlled-order fixture JSON.
  --reviewer TEXT             Reviewer label stored in redacted packets. Default: post-runtime-live-candidate-runner.
  --commit REF                Commit label stored in redacted packets. Default: current HEAD.
  -h, --help                  Show this help.
USAGE
}

ts="$(date -u +%Y%m%dT%H%M%SZ)"
generated_at="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
out_dir="target/biocortex-post-runtime-live-candidate-$ts"
biocortex_rs="${AB_BIOCORTEX_RS:-${BIOCORTEX_RS:-}}"
decision_packet="target/biocortex-post-runtime-evidence-20260613/03-runtime-influence-decision-packet-post-runtime.json"
readiness_packet="target/biocortex-post-runtime-evidence-20260613/07-runtime-readiness-packet-post-runtime.json"
transition_gate="target/biocortex-post-runtime-evidence-20260613/08-runtime-transition-gate-post-runtime.json"
fixture_json="docs/design/fixtures/biocortex-retrieval-opt-in-controlled-order-fixture-2026-06-12.json"
reviewer="post-runtime-live-candidate-runner"
commit="$(git rev-parse HEAD)"

while [[ $# -gt 0 ]]; do
    case "$1" in
        --out-dir) out_dir="$2"; shift 2 ;;
        --checkout) biocortex_rs="$2"; shift 2 ;;
        --decision-packet) decision_packet="$2"; shift 2 ;;
        --readiness-packet) readiness_packet="$2"; shift 2 ;;
        --transition-gate) transition_gate="$2"; shift 2 ;;
        --fixture) fixture_json="$2"; shift 2 ;;
        --reviewer) reviewer="$2"; shift 2 ;;
        --commit) commit="$2"; shift 2 ;;
        -h|--help) usage; exit 0 ;;
        *) echo "unknown flag: $1" >&2; usage >&2; exit 2 ;;
    esac
done

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

for required in "$decision_packet" "$readiness_packet" "$transition_gate" "$fixture_json"; do
    if [[ ! -f "$required" ]]; then
        echo "required input not found: $required" >&2
        exit 2
    fi
done

mkdir -p "$out_dir/db"

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
    local pattern='controlled trial runtime query|controlled_trial_runtime_key|controlled trial runtime content|cortexdelta|cortexepsilon|cortexzeta|cortexeta|cortextheta|cortexiota|controlled_order_baseline_high|controlled_order_biocortex_target|target anchor|baseline anchor|post_runtime_live_candidate_status_key|axonalpha|axonbeta|axongamma|axondelta|axonepsilon|axonzeta|dendritealpha|dendritebeta|dendritegamma|dendritedelta|dendriteepsilon|dendritezeta|gliaalph|gliabet|gliagam|gliadel|gliaeps|gliazet|myelinalpha|myelinbeta|myelingamma|myelindelta|myelinepsilon|myelinzeta|synapsealpha|synapsebeta|synapsegamma|synapsedelta|synapseepsilon|synapsezeta|expanded_corpus_baseline_focus|expanded_corpus_target_span|baseline focus|target span'
    if grep -Eiq "$pattern" "$file"; then
        echo "redacted artifact leaked raw fixture/query/key/content data: $file" >&2
        exit 1
    fi
}

opt_in_cmd=(cargo run -p ab-bridge --no-default-features --features biocortex-retrieval-opt-in --)
live_db="$out_dir/db/live-candidate.db"
query="$(jq -er '.query_cases[0].query' "$fixture_json")"

controlled_fixture="$out_dir/01-controlled-order-fixture-post-runtime.json"
gated_store="$out_dir/02-gated-store-trial-live-candidate.json"
gated_batch="$out_dir/03-gated-batch-live-candidate.json"
status_surface="$out_dir/04-status-live-candidate.json"
evidence_summary="$out_dir/05-live-candidate-evidence-summary.json"
summary_json="$out_dir/live-candidate-runner-summary.json"
report_md="$out_dir/LIVE_CANDIDATE_REPORT.md"

json_run "$controlled_fixture" env AGENT_BRIDGE_DB="$live_db" AB_BIOCORTEX_RETRIEVAL_OPT_IN=1 \
    "${opt_in_cmd[@]}" \
    bio-cortex retrieval-opt-in-controlled-order-fixture \
    --runtime-influence-decision-packet-json "$decision_packet" \
    --fixture-json "$fixture_json" \
    --allow-non-production-store-writes \
    --per-call-opt-in \
    --checkout "$biocortex_rs" \
    --limit 3 \
    --coverage-threshold 0.5 \
    --attempt-id post-runtime-live-candidate-seed \
    --commit "$commit" \
    --json
assert_json '.schema == "agent_bridge.biocortex_retrieval.opt_in_controlled_order_fixture_run.v0" and .status == "completed" and .expected.met == true and .attempt.seeded_memory_count >= 2 and .diagnostics.summary.query_count >= 1 and .diagnostics.summary.baseline_empty_count == 0 and .diagnostics.summary.adapter_allowed_count >= 1 and .diagnostics.summary.side_signal_ok_count >= 1 and .diagnostics.summary.experimental_source_count >= 1 and .diagnostics.summary.actual_order_changed_count >= 1 and .diagnostics.summary.runs_biocortex_count >= 1 and .diagnostics.safety.raw_flags_all_false == true and .default_search_order_change_allowed == false and .default_calls_unchanged == true' "$controlled_fixture"
leak_guard "$controlled_fixture"

json_run "$gated_store" env AGENT_BRIDGE_DB="$live_db" AB_BIOCORTEX_RETRIEVAL_OPT_IN=1 \
    "${opt_in_cmd[@]}" \
    bio-cortex retrieval-opt-in-gated-store-trial \
    --runtime-transition-gate-json "$transition_gate" \
    --runtime-influence-decision-packet-json "$decision_packet" \
    --query "$query" \
    --per-call-opt-in \
    --checkout "$biocortex_rs" \
    --limit 3 \
    --coverage-threshold 0.5 \
    --attempt-id post-runtime-live-candidate-gated-store \
    --commit "$commit" \
    --json
assert_json '.schema == "agent_bridge.biocortex_retrieval.opt_in_gated_store_trial.v0" and .status == "transition_gate_consumed" and .runtime_transition_preflight.transition_gate_allowed == true and .runtime_transition_preflight.gate_post_runtime_evidence_summary_ready == true and .store_trial_summary.status == "experimental_order_returned" and .store_trial_summary.runtime_adapter_allowed == true and .store_trial_summary.baseline_key_count >= 1 and .store_trial_summary.side_signal_status == "ok" and .store_trial_summary.actual_return_order_changed == true and .store_trial_summary.returned_order_source == "experimental" and .calls_memory_search == true and .runs_biocortex == true and .changes_memory_search_order == true and .default_calls_unchanged == true and .raw_queries_included == false and .raw_keys_included == false and .content_included == false and .side_signal_raw_included == false' "$gated_store"
leak_guard "$gated_store"

json_run "$gated_batch" env AGENT_BRIDGE_DB="$live_db" AB_BIOCORTEX_RETRIEVAL_OPT_IN=1 \
    "${opt_in_cmd[@]}" \
    bio-cortex retrieval-opt-in-gated-batch-diagnostics \
    --runtime-transition-gate-json "$transition_gate" \
    --runtime-influence-decision-packet-json "$decision_packet" \
    --query-cases-json "$fixture_json" \
    --per-call-opt-in \
    --checkout "$biocortex_rs" \
    --limit 3 \
    --coverage-threshold 0.5 \
    --attempt-id post-runtime-live-candidate-gated-batch \
    --commit "$commit" \
    --json
assert_json '.schema == "agent_bridge.biocortex_retrieval.opt_in_gated_batch_diagnostics.v0" and .status == "completed" and .summary.query_count >= 1 and .summary.transition_gate_allowed_count == .summary.query_count and .summary.transition_gate_blocked_count == 0 and .summary.store_trial_called_count == .summary.query_count and .summary.calls_memory_search_count == .summary.query_count and .summary.baseline_empty_count == 0 and .summary.store_trial_adapter_allowed_count >= 1 and .summary.side_signal_ok_count >= 1 and .summary.experimental_source_count >= 1 and .summary.actual_order_changed_count >= 1 and .summary.runs_biocortex_count >= 1 and .safety.transition_gate_allowed_all == true and .safety.store_trial_called_all == true and .safety.calls_memory_search_all == true and .safety.runs_biocortex_any == true and .safety.raw_flags_all_false == true and .safety.default_calls_unchanged_all == true and .default_search_order_change_allowed == false and .default_calls_unchanged == true' "$gated_batch"
leak_guard "$gated_batch"

json_run "$status_surface" env AB_BIOCORTEX_RETRIEVAL_OPT_IN=1 \
    "${opt_in_cmd[@]}" \
    bio-cortex retrieval-opt-in-status \
    --mode fts \
    --per-call-opt-in \
    --query "$query" \
    --baseline-key post_runtime_live_candidate_status_key \
    --runtime-readiness-packet-json "$readiness_packet" \
    --runtime-transition-gate-json "$transition_gate" \
    --gated-store-trial-json "$gated_store" \
    --gated-batch-diagnostics-json "$gated_batch" \
    --json
assert_json '.schema == "agent_bridge.biocortex_retrieval.opt_in_call_audit.v0" and .controlled_trial_readiness.schema == "agent_bridge.biocortex_retrieval.controlled_trial_readiness_summary.v0" and .controlled_trial_readiness.status == "blocked" and .controlled_trial_readiness.ready_for_controlled_trial == false and (.controlled_trial_readiness.blockers | index("gated_store_trial_not_consumed")) != null and (.controlled_trial_readiness.blockers | index("gated_batch_diagnostics_not_ready")) != null and .controlled_trial_readiness.runtime_readiness_packet.ready == true and .controlled_trial_readiness.runtime_transition_gate.transition_allowed == true and .controlled_trial_readiness.gated_store_trial.runs_biocortex == true and .controlled_trial_readiness.gated_batch_diagnostics.runs_biocortex_any == true and .controlled_trial_readiness.status_surface_calls_memory_search == false and .controlled_trial_readiness.status_surface_runs_biocortex == false and .controlled_trial_readiness.status_surface_changes_memory_search_order == false and .controlled_trial_readiness.raw_queries_included == false and .controlled_trial_readiness.raw_keys_included == false and .controlled_trial_readiness.content_included == false and .boundary.changes_memory_search_order == false and .changes_memory_search_order == false and .default_search_order_change_allowed == false and .default_calls_unchanged == true' "$status_surface"
leak_guard "$status_surface"

json_run "$evidence_summary" "${opt_in_cmd[@]}" \
    bio-cortex retrieval-opt-in-evidence-summary \
    --batch-diagnostics-json "$gated_batch" \
    --controlled-order-fixture-run-json "$controlled_fixture" \
    --runtime-readiness-packet-json "$readiness_packet" \
    --reviewer "$reviewer" \
    --commit "$commit" \
    --forum-post-id post-runtime-live-candidate-runner-local \
    --memory-key post-runtime-live-candidate-runner-local \
    --json
assert_json '.schema == "agent_bridge.biocortex_retrieval.opt_in_evidence_summary.v0" and .status == "completed" and .interpretation.evidence_ready == true and .interpretation.review_state == "post_runtime_evidence_ready" and .interpretation.runtime_adapter_connection_evidence == true and .batch_diagnostics.diagnostic_class == "movement_observed" and .batch_diagnostics.movement_observed == true and .batch_diagnostics.actual_order_changed_count >= 1 and .batch_diagnostics.transition_gate_ok == true and .controlled_order.expected_met == true and .controlled_order.movement_observed == true and .runtime_readiness.gated_batch_evidence_ready == true and .interpretation.default_influence_ready == false and .changes_memory_search_order == false and .default_search_order_change_allowed == false and .default_calls_unchanged == true and .raw_queries_included == false and .raw_keys_included == false and .content_included == false and .side_signal_raw_included == false' "$evidence_summary"
leak_guard "$evidence_summary"

jq -n \
    --arg generated_at "$generated_at" \
    --arg commit "$commit" \
    --arg checkout "$biocortex_rs" \
    --arg out_dir "$out_dir" \
    --arg fixture "$(basename "$fixture_json")" \
    --slurpfile controlled "$controlled_fixture" \
    --slurpfile store "$gated_store" \
    --slurpfile batch "$gated_batch" \
    --slurpfile status "$status_surface" \
    --slurpfile evidence "$evidence_summary" \
    '{
        schema: "agent_bridge.biocortex_retrieval.post_runtime_live_candidate_runner_summary.v0",
        generated_at: $generated_at,
        read_only_summary: true,
        commit: $commit,
        biocortex_rs_checkout: $checkout,
        output_dir: $out_dir,
        fixture: $fixture,
        status: (if $evidence[0].interpretation.evidence_ready == true then "post_runtime_live_candidate_evidence_ready" else "post_runtime_live_candidate_evidence_incomplete" end),
        controlled_fixture: {
            expected_met: $controlled[0].expected.met,
            seeded_memory_count: $controlled[0].attempt.seeded_memory_count,
            query_count: $controlled[0].diagnostics.summary.query_count,
            adapter_allowed_count: $controlled[0].diagnostics.summary.adapter_allowed_count,
            side_signal_ok_count: $controlled[0].diagnostics.summary.side_signal_ok_count,
            experimental_source_count: $controlled[0].diagnostics.summary.experimental_source_count,
            actual_order_changed_count: $controlled[0].diagnostics.summary.actual_order_changed_count,
            runs_biocortex_count: $controlled[0].diagnostics.summary.runs_biocortex_count,
            raw_flags_all_false: $controlled[0].diagnostics.safety.raw_flags_all_false
        },
        gated_store: {
            status: $store[0].status,
            transition_gate_allowed: $store[0].runtime_transition_preflight.transition_gate_allowed,
            store_trial_status: $store[0].store_trial_summary.status,
            baseline_key_count: $store[0].store_trial_summary.baseline_key_count,
            runtime_adapter_allowed: $store[0].store_trial_summary.runtime_adapter_allowed,
            side_signal_status: $store[0].store_trial_summary.side_signal_status,
            actual_return_order_changed: $store[0].store_trial_summary.actual_return_order_changed,
            calls_memory_search: $store[0].calls_memory_search,
            runs_biocortex: $store[0].runs_biocortex,
            changes_memory_search_order: $store[0].changes_memory_search_order,
            default_calls_unchanged: $store[0].default_calls_unchanged
        },
        gated_batch: {
            query_count: $batch[0].summary.query_count,
            transition_gate_allowed_count: $batch[0].summary.transition_gate_allowed_count,
            transition_gate_blocked_count: $batch[0].summary.transition_gate_blocked_count,
            store_trial_called_count: $batch[0].summary.store_trial_called_count,
            calls_memory_search_count: $batch[0].summary.calls_memory_search_count,
            baseline_empty_count: $batch[0].summary.baseline_empty_count,
            adapter_allowed_count: $batch[0].summary.store_trial_adapter_allowed_count,
            side_signal_ok_count: $batch[0].summary.side_signal_ok_count,
            experimental_source_count: $batch[0].summary.experimental_source_count,
            actual_order_changed_count: $batch[0].summary.actual_order_changed_count,
            runs_biocortex_count: $batch[0].summary.runs_biocortex_count,
            raw_flags_all_false: $batch[0].safety.raw_flags_all_false,
            default_calls_unchanged_all: $batch[0].safety.default_calls_unchanged_all
        },
        status_surface: {
            schema: $status[0].schema,
            controlled_status: $status[0].controlled_trial_readiness.status,
            blockers: $status[0].controlled_trial_readiness.blockers,
            status_surface_calls_memory_search: $status[0].controlled_trial_readiness.status_surface_calls_memory_search,
            status_surface_runs_biocortex: $status[0].controlled_trial_readiness.status_surface_runs_biocortex,
            status_surface_changes_memory_search_order: $status[0].controlled_trial_readiness.status_surface_changes_memory_search_order,
            default_calls_unchanged: $status[0].default_calls_unchanged,
            default_search_order_change_allowed: $status[0].default_search_order_change_allowed
        },
        evidence_summary: {
            review_state: $evidence[0].interpretation.review_state,
            evidence_ready: $evidence[0].interpretation.evidence_ready,
            diagnostic_class: $evidence[0].batch_diagnostics.diagnostic_class,
            movement_observed: $evidence[0].batch_diagnostics.movement_observed,
            runtime_adapter_connection_evidence: $evidence[0].interpretation.runtime_adapter_connection_evidence,
            runtime_readiness_requirement_met: $evidence[0].interpretation.runtime_readiness_requirement_met,
            readiness_gated_batch_evidence_ready: $evidence[0].interpretation.readiness_gated_batch_evidence_ready,
            recommended_next_step: $evidence[0].interpretation.recommended_next_step
        },
        boundary: {
            writes_approval: false,
            mutates_default_agent_bridge_db: false,
            raw_queries_included: false,
            raw_keys_included: false,
            content_included: false,
            side_signal_raw_included: false,
            default_search_order_change_allowed: false,
            default_calls_unchanged: true,
            default_memory_search_order_changed: false
        },
        artifacts: {
            controlled_fixture: "01-controlled-order-fixture-post-runtime.json",
            gated_store: "02-gated-store-trial-live-candidate.json",
            gated_batch: "03-gated-batch-live-candidate.json",
            status_surface: "04-status-live-candidate.json",
            evidence_summary: "05-live-candidate-evidence-summary.json"
        }
    }' > "$summary_json"
assert_json '.schema == "agent_bridge.biocortex_retrieval.post_runtime_live_candidate_runner_summary.v0" and .status == "post_runtime_live_candidate_evidence_ready" and .controlled_fixture.actual_order_changed_count >= 1 and .gated_store.runs_biocortex == true and .gated_store.changes_memory_search_order == true and .gated_batch.actual_order_changed_count >= 1 and .gated_batch.runs_biocortex_count >= 1 and .status_surface.controlled_status == "blocked" and .status_surface.status_surface_calls_memory_search == false and .evidence_summary.evidence_ready == true and .evidence_summary.diagnostic_class == "movement_observed" and .boundary.default_search_order_change_allowed == false and .boundary.default_calls_unchanged == true' "$summary_json"
leak_guard "$summary_json"

{
    echo "# BioCortex Post-Runtime Live-Candidate Runner"
    echo
    echo "- generated_at: $(jq -r '.generated_at' "$summary_json")"
    echo "- status: $(jq -r '.status' "$summary_json")"
    echo "- commit: $(jq -r '.commit' "$summary_json")"
    echo "- output_dir: $(jq -r '.output_dir' "$summary_json")"
    echo
    echo "## Result"
    echo
    echo "- controlled fixture movement: $(jq -r '.controlled_fixture.actual_order_changed_count' "$summary_json")"
    echo "- gated store runs_biocortex: $(jq -r '.gated_store.runs_biocortex' "$summary_json")"
    echo "- gated store order changed: $(jq -r '.gated_store.changes_memory_search_order' "$summary_json")"
    echo "- gated batch queries: $(jq -r '.gated_batch.query_count' "$summary_json")"
    echo "- gated batch movement: $(jq -r '.gated_batch.actual_order_changed_count' "$summary_json")"
    echo "- evidence review_state: $(jq -r '.evidence_summary.review_state' "$summary_json")"
    echo "- recommended_next_step: $(jq -r '.evidence_summary.recommended_next_step' "$summary_json")"
    echo
    echo "## Status Surface"
    echo
    echo "- controlled_status: $(jq -r '.status_surface.controlled_status' "$summary_json")"
    echo "- status_surface_calls_memory_search: $(jq -r '.status_surface.status_surface_calls_memory_search' "$summary_json")"
    echo "- status_surface_runs_biocortex: $(jq -r '.status_surface.status_surface_runs_biocortex' "$summary_json")"
    echo "- status_surface_changes_memory_search_order: $(jq -r '.status_surface.status_surface_changes_memory_search_order' "$summary_json")"
    echo
    echo "## Boundary"
    echo
    echo "- default_search_order_change_allowed: $(jq -r '.boundary.default_search_order_change_allowed' "$summary_json")"
    echo "- default_calls_unchanged: $(jq -r '.boundary.default_calls_unchanged' "$summary_json")"
    echo "- raw_queries_included: $(jq -r '.boundary.raw_queries_included' "$summary_json")"
    echo "- raw_keys_included: $(jq -r '.boundary.raw_keys_included' "$summary_json")"
    echo "- content_included: $(jq -r '.boundary.content_included' "$summary_json")"
    echo "- side_signal_raw_included: $(jq -r '.boundary.side_signal_raw_included' "$summary_json")"
    echo
    echo "## Artifacts"
    echo
    jq -r '.artifacts | to_entries[] | "- \(.key): `\(.value)`"' "$summary_json"
} > "$report_md"
leak_guard "$report_md"

printf '\npost-runtime live-candidate runner complete\n' >&2
printf 'summary_json=%s\n' "$summary_json"
printf 'report_md=%s\n' "$report_md"
