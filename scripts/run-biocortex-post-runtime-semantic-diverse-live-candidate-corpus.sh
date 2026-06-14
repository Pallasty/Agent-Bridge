#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"

usage() {
    cat <<'USAGE'
usage: scripts/run-biocortex-post-runtime-semantic-diverse-live-candidate-corpus.sh [flags]

Replays the post-runtime BioCortex live-candidate runner over a manifest of
independent semantic fixture cases. Each case uses its own non-production DB
and output directory; the aggregate report contains only redacted summaries.

Flags:
  --out-dir PATH              Artifact directory. Default: target/biocortex-post-runtime-semantic-diverse-live-candidate-<utc-ts>.
  --corpus PATH               Corpus manifest JSON.
  --checkout PATH             Local biocortex-rs checkout.
  --decision-packet PATH      Runtime influence decision packet JSON.
  --readiness-packet PATH     Runtime readiness packet JSON.
  --transition-gate PATH      Runtime transition gate JSON.
  --reviewer TEXT             Reviewer label stored in redacted packets.
  --commit REF                Commit label stored in redacted packets. Default: current HEAD.
  -h, --help                  Show this help.
USAGE
}

ts="$(date -u +%Y%m%dT%H%M%SZ)"
generated_at="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
out_dir="target/biocortex-post-runtime-semantic-diverse-live-candidate-$ts"
corpus_json="docs/design/fixtures/biocortex-retrieval-post-runtime-semantic-diverse-live-candidate-corpus-2026-06-14.json"
biocortex_rs="${AB_BIOCORTEX_RS:-${BIOCORTEX_RS:-}}"
decision_packet="target/biocortex-post-runtime-evidence-20260613/03-runtime-influence-decision-packet-post-runtime.json"
readiness_packet="target/biocortex-post-runtime-evidence-20260613/07-runtime-readiness-packet-post-runtime.json"
transition_gate="target/biocortex-post-runtime-evidence-20260613/08-runtime-transition-gate-post-runtime.json"
reviewer="post-runtime-semantic-diverse-live-candidate-corpus"
commit="$(git rev-parse HEAD)"

while [[ $# -gt 0 ]]; do
    case "$1" in
        --out-dir) out_dir="$2"; shift 2 ;;
        --corpus) corpus_json="$2"; shift 2 ;;
        --checkout) biocortex_rs="$2"; shift 2 ;;
        --decision-packet) decision_packet="$2"; shift 2 ;;
        --readiness-packet) readiness_packet="$2"; shift 2 ;;
        --transition-gate) transition_gate="$2"; shift 2 ;;
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

for required in "$corpus_json" "$decision_packet" "$readiness_packet" "$transition_gate"; do
    if [[ ! -f "$required" ]]; then
        echo "required input not found: $required" >&2
        exit 2
    fi
done

fixture_count="$(jq '.fixtures | length' "$corpus_json")"
if [[ "$fixture_count" -lt 1 ]]; then
    echo "corpus manifest must contain at least one fixture" >&2
    exit 2
fi

mkdir -p "$out_dir/cases"

summary_files=()
for idx in $(seq 0 $((fixture_count - 1))); do
    case_id="$(jq -er ".fixtures[$idx].id" "$corpus_json")"
    fixture_path="$(jq -er ".fixtures[$idx].fixture" "$corpus_json")"
    case_out="$out_dir/cases/$case_id"
    printf '\n==> corpus case %s fixture=%s\n' "$case_id" "$fixture_path" >&2
    scripts/run-biocortex-post-runtime-live-candidate.sh \
        --out-dir "$case_out" \
        --checkout "$biocortex_rs" \
        --decision-packet "$decision_packet" \
        --readiness-packet "$readiness_packet" \
        --transition-gate "$transition_gate" \
        --fixture "$fixture_path" \
        --reviewer "$reviewer:$case_id" \
        --commit "$commit"
    summary_files+=("$case_out/live-candidate-runner-summary.json")
done

summary_json="$out_dir/semantic-diverse-live-candidate-corpus-summary.json"
report_md="$out_dir/SEMANTIC_DIVERSE_LIVE_CANDIDATE_REPORT.md"

jq -s \
    --arg generated_at "$generated_at" \
    --arg commit "$commit" \
    --arg checkout "$biocortex_rs" \
    --arg out_dir "$out_dir" \
    --arg corpus_json "$corpus_json" \
    --slurpfile corpus "$corpus_json" \
    '
    def sum_field(path_expr): map(path_expr) | add // 0;
    . as $cases
    | ($corpus[0]) as $manifest
    | {
        schema: "agent_bridge.biocortex_retrieval.post_runtime_semantic_diverse_live_candidate_corpus_summary.v0",
        generated_at: $generated_at,
        read_only_summary: true,
        commit: $commit,
        biocortex_rs_checkout: $checkout,
        output_dir: $out_dir,
        corpus_fixture: $corpus_json,
        source_runner: "scripts/run-biocortex-post-runtime-semantic-diverse-live-candidate-corpus.sh",
        single_fixture_runner: "scripts/run-biocortex-post-runtime-live-candidate.sh",
        authorization_scope: "explicit_opt_in_fts_runtime_influence",
        status: "computed",
        aggregate: {
            fixture_count: ($cases | length),
            total_query_count: ($cases | sum_field(.gated_batch.query_count)),
            total_baseline_empty_count: ($cases | sum_field(.gated_batch.baseline_empty_count)),
            total_actual_order_changed_count: ($cases | sum_field(.gated_batch.actual_order_changed_count)),
            total_runs_biocortex_count: ($cases | sum_field(.gated_batch.runs_biocortex_count)),
            total_side_signal_ok_count: ($cases | sum_field(.gated_batch.side_signal_ok_count)),
            total_experimental_source_count: ($cases | sum_field(.gated_batch.experimental_source_count)),
            all_cases_evidence_ready: (all($cases[]; .status == "post_runtime_live_candidate_evidence_ready")),
            all_status_surfaces_blocked: (all($cases[]; .status_surface.controlled_status == "blocked")),
            all_status_surfaces_side_effect_free: (all($cases[];
                .status_surface.status_surface_calls_memory_search == false
                and .status_surface.status_surface_runs_biocortex == false
                and .status_surface.status_surface_changes_memory_search_order == false
            )),
            all_default_calls_unchanged: (all($cases[]; .boundary.default_calls_unchanged == true)),
            all_default_order_unchanged: (all($cases[]; .boundary.default_memory_search_order_changed == false))
        },
        expected: $manifest.expected,
        expected_met: (
            ($cases | length) == ($manifest.expected.fixture_count // 0)
            and ($cases | sum_field(.gated_batch.query_count)) == ($manifest.expected.total_query_count // 0)
            and ($cases | sum_field(.gated_batch.actual_order_changed_count)) >= ($manifest.expected.min_total_actual_order_changed_count // 0)
            and ($cases | sum_field(.gated_batch.runs_biocortex_count)) >= ($manifest.expected.min_total_runs_biocortex_count // 0)
            and ($cases | sum_field(.gated_batch.side_signal_ok_count)) >= ($manifest.expected.min_total_side_signal_ok_count // 0)
            and (all($cases[]; .status == "post_runtime_live_candidate_evidence_ready"))
            and (all($cases[]; .status_surface.controlled_status == "blocked"))
            and (all($cases[]; .boundary.default_calls_unchanged == true))
            and (all($cases[]; .boundary.default_search_order_change_allowed == false))
        ),
        case_summaries: [
            range(0; $cases | length) as $i
            | {
                id: $manifest.fixtures[$i].id,
                semantic_axis: $manifest.fixtures[$i].semantic_axis,
                fixture: $manifest.fixtures[$i].fixture,
                output_dir: $cases[$i].output_dir,
                status: $cases[$i].status,
                query_count: $cases[$i].gated_batch.query_count,
                baseline_empty_count: $cases[$i].gated_batch.baseline_empty_count,
                actual_order_changed_count: $cases[$i].gated_batch.actual_order_changed_count,
                runs_biocortex_count: $cases[$i].gated_batch.runs_biocortex_count,
                side_signal_ok_count: $cases[$i].gated_batch.side_signal_ok_count,
                evidence_ready: $cases[$i].evidence_summary.evidence_ready,
                diagnostic_class: $cases[$i].evidence_summary.diagnostic_class,
                status_surface_controlled_status: $cases[$i].status_surface.controlled_status,
                status_surface_calls_memory_search: $cases[$i].status_surface.status_surface_calls_memory_search,
                status_surface_runs_biocortex: $cases[$i].status_surface.status_surface_runs_biocortex,
                status_surface_changes_memory_search_order: $cases[$i].status_surface.status_surface_changes_memory_search_order,
                default_calls_unchanged: $cases[$i].boundary.default_calls_unchanged
            }
        ],
        boundary: {
            one_non_production_db_per_fixture: true,
            writes_approval: false,
            mutates_default_agent_bridge_db: false,
            raw_queries_included: false,
            raw_keys_included: false,
            content_included: false,
            side_signal_raw_included: false,
            default_search_order_change_allowed: false,
            default_calls_unchanged: true,
            default_memory_search_order_changed: false,
            hybrid_retrieval_unchanged: true,
            semantic_retrieval_unchanged: true
        },
        next_step: "handoff_to_aio2_for_post_semantic_diverse_review"
    }
    | .status = (if .expected_met then "post_runtime_semantic_diverse_live_candidate_evidence_ready" else "post_runtime_semantic_diverse_live_candidate_evidence_incomplete" end)
    ' "${summary_files[@]}" > "$summary_json"

jq -e '
    .schema == "agent_bridge.biocortex_retrieval.post_runtime_semantic_diverse_live_candidate_corpus_summary.v0"
    and .status == "post_runtime_semantic_diverse_live_candidate_evidence_ready"
    and .expected_met == true
    and .aggregate.fixture_count == .expected.fixture_count
    and .aggregate.total_query_count == .expected.total_query_count
    and .aggregate.total_baseline_empty_count == 0
    and .aggregate.total_actual_order_changed_count >= .expected.min_total_actual_order_changed_count
    and .aggregate.total_runs_biocortex_count >= .expected.min_total_runs_biocortex_count
    and .aggregate.total_side_signal_ok_count >= .expected.min_total_side_signal_ok_count
    and .aggregate.all_cases_evidence_ready == true
    and .aggregate.all_status_surfaces_blocked == true
    and .aggregate.all_status_surfaces_side_effect_free == true
    and .aggregate.all_default_calls_unchanged == true
    and .boundary.default_search_order_change_allowed == false
    and .boundary.default_calls_unchanged == true
    and .boundary.raw_queries_included == false
    and .boundary.raw_keys_included == false
    and .boundary.content_included == false
    and .boundary.side_signal_raw_included == false
' "$summary_json" >/dev/null

{
    echo "# BioCortex Post-Runtime Semantic-Diverse Live-Candidate Corpus"
    echo
    echo "- generated_at: $(jq -r '.generated_at' "$summary_json")"
    echo "- status: $(jq -r '.status' "$summary_json")"
    echo "- commit: $(jq -r '.commit' "$summary_json")"
    echo "- output_dir: $(jq -r '.output_dir' "$summary_json")"
    echo
    echo "## Aggregate"
    echo
    echo "- fixtures: $(jq -r '.aggregate.fixture_count' "$summary_json")"
    echo "- total queries: $(jq -r '.aggregate.total_query_count' "$summary_json")"
    echo "- total BioCortex runs: $(jq -r '.aggregate.total_runs_biocortex_count' "$summary_json")"
    echo "- total side-signal ok: $(jq -r '.aggregate.total_side_signal_ok_count' "$summary_json")"
    echo "- total actual order changed: $(jq -r '.aggregate.total_actual_order_changed_count' "$summary_json")"
    echo "- total baseline empty: $(jq -r '.aggregate.total_baseline_empty_count' "$summary_json")"
    echo
    echo "## Cases"
    echo
    jq -r '.case_summaries[] | "- \(.id): queries=\(.query_count), moved=\(.actual_order_changed_count), runs_biocortex=\(.runs_biocortex_count), status_surface=\(.status_surface_controlled_status)"' "$summary_json"
    echo
    echo "## Boundary"
    echo
    echo "- one_non_production_db_per_fixture: $(jq -r '.boundary.one_non_production_db_per_fixture' "$summary_json")"
    echo "- default_search_order_change_allowed: $(jq -r '.boundary.default_search_order_change_allowed' "$summary_json")"
    echo "- default_calls_unchanged: $(jq -r '.boundary.default_calls_unchanged' "$summary_json")"
    echo "- raw_queries_included: $(jq -r '.boundary.raw_queries_included' "$summary_json")"
    echo "- raw_keys_included: $(jq -r '.boundary.raw_keys_included' "$summary_json")"
    echo "- content_included: $(jq -r '.boundary.content_included' "$summary_json")"
    echo "- side_signal_raw_included: $(jq -r '.boundary.side_signal_raw_included' "$summary_json")"
    echo
    echo "## Next Step"
    echo
    echo "- $(jq -r '.next_step' "$summary_json")"
} > "$report_md"

printf '\npost-runtime semantic-diverse live-candidate corpus complete\n' >&2
printf 'summary_json=%s\n' "$summary_json"
printf 'report_md=%s\n' "$report_md"
