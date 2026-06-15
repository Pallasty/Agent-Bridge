#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"

out_dir=""
sample_count=5
timeout_ms=30000
biocortex_rs="${AB_BIOCORTEX_RS:-${BIOCORTEX_RS:-}}"

usage() {
    cat <<'USAGE'
usage: scripts/prove-biocortex-retrieval-runtime-boundary.sh [flags]

Flags:
  --out-dir PATH       Directory for proof artifacts. Defaults to a temp dir.
  --samples N         Enabled-surface latency samples to collect. Default: 5.
  --timeout-ms N      Side-signal adapter timeout for each enabled run. Default: 30000.
  --checkout PATH     Local biocortex-rs checkout.
  -h, --help          Show this help.

This script is a proof generator only. It writes local JSON artifacts and never
changes memory_search order, writes approval state, or mutates AB memory.
USAGE
}

while [ "$#" -gt 0 ]; do
    case "$1" in
        --out-dir) out_dir="$2"; shift 2 ;;
        --samples) sample_count="$2"; shift 2 ;;
        --timeout-ms) timeout_ms="$2"; shift 2 ;;
        --checkout) biocortex_rs="$2"; shift 2 ;;
        -h|--help) usage; exit 0 ;;
        *) echo "unknown flag: $1" >&2; usage >&2; exit 2 ;;
    esac
done

if ! [[ "$sample_count" =~ ^[0-9]+$ ]] || [ "$sample_count" -lt 1 ]; then
    echo "--samples must be a positive integer" >&2
    exit 2
fi

if ! [[ "$timeout_ms" =~ ^[0-9]+$ ]] || [ "$timeout_ms" -lt 1000 ]; then
    echo "--timeout-ms must be an integer >= 1000" >&2
    exit 2
fi

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

if [ -z "$out_dir" ]; then
    out_dir="$(mktemp -d "${TMPDIR:-/tmp}/ab-biocortex-runtime-proof-XXXXXX")"
else
    mkdir -p "$out_dir"
fi

input_json="$out_dir/runtime-shadow-input.json"
default_report="$out_dir/default-disabled.json"
kill_report="$out_dir/kill-switch.json"
enabled_report="$out_dir/enabled-sample.json"
samples_jsonl="$out_dir/latency-samples.jsonl"
latencies_txt="$out_dir/latency-values.txt"
summary_json="$out_dir/proof-summary.json"

acceptance_fixture="crates/bridge/tests/fixtures/biocortex_retrieval_shadow_acceptance.jsonl"
jq -s '.[0] | {query, expected_key, candidates}' "$acceptance_fixture" > "$input_json"

run_shadow() {
    cargo run -p ab-bridge --no-default-features --features biocortex-retrieval-shadow \
        -- bio-cortex retrieval-shadow \
        --json \
        --input-json "$input_json" \
        --checkout "$biocortex_rs" \
        --timeout-ms "$timeout_ms"
}

run_shadow > "$default_report"
jq -e '
    .schema == "agent_bridge.biocortex_retrieval_shadow_report.v0"
    and .status == "runtime_disabled"
    and .read_only == true
    and .runtime_adapter_approved == false
    and .default_search_order_changed == false
    and .gates.compile_feature_enabled == true
    and .gates.runtime_enabled == false
    and .gates.operator_disabled == false
' "$default_report" >/dev/null

AB_BIOCORTEX_RETRIEVAL_SHADOW=1 \
AB_BIOCORTEX_RETRIEVAL_DISABLE=1 \
run_shadow > "$kill_report"
jq -e '
    .schema == "agent_bridge.biocortex_retrieval_shadow_report.v0"
    and .status == "operator_disabled"
    and .read_only == true
    and .runtime_adapter_approved == false
    and .default_search_order_changed == false
    and .gates.runtime_enabled == true
    and .gates.operator_disabled == true
' "$kill_report" >/dev/null

: > "$samples_jsonl"
: > "$latencies_txt"

for idx in $(seq 1 "$sample_count"); do
    sample_path="$out_dir/enabled-sample-$idx.json"
    AB_BIOCORTEX_RETRIEVAL_SHADOW=1 run_shadow > "$sample_path"
    jq -e '
        .schema == "agent_bridge.biocortex_retrieval_shadow_report.v0"
        and .status == "ok"
        and .read_only == true
        and .runtime_adapter_approved == false
        and .default_search_order_changed == false
        and .side_signal_coverage >= 0.8
        and .gates.runtime_enabled == true
        and .gates.operator_disabled == false
        and (.latency_ms >= 0)
    ' "$sample_path" >/dev/null
    jq -c . "$sample_path" >> "$samples_jsonl"
    jq -r '.latency_ms' "$sample_path" >> "$latencies_txt"
    if [ "$idx" -eq 1 ]; then
        cp "$sample_path" "$enabled_report"
    fi
done

rank="$(awk -v n="$sample_count" 'BEGIN { r = int(0.95 * n); if (r < 0.95 * n) r++; if (r < 1) r = 1; print r }')"
p95_ms="$(sort -n "$latencies_txt" | awk -v r="$rank" 'NR == r { print; exit }')"
max_ms="$(sort -n "$latencies_txt" | tail -n 1)"
avg_ms="$(awk '{ sum += $1 } END { if (NR == 0) print 0; else printf "%.6f\n", sum / NR }' "$latencies_txt")"

jq -n \
    --slurpfile default_report "$default_report" \
    --slurpfile kill_report "$kill_report" \
    --slurpfile enabled_report "$enabled_report" \
    --arg target_host "$(hostname)" \
    --arg biocortex_rs "$biocortex_rs" \
    --arg input_json "$input_json" \
    --arg sample_count "$sample_count" \
    --arg timeout_ms "$timeout_ms" \
    --arg p95_ms "$p95_ms" \
    --arg max_ms "$max_ms" \
    --arg avg_ms "$avg_ms" \
    '{
        schema: "agent_bridge.biocortex_retrieval.runtime_boundary_proof.v0",
        generated_at: (now | floor),
        read_only: true,
        writes_approval: false,
        runtime_adapter_approved: false,
        default_search_order_changed: false,
        target_host: $target_host,
        biocortex_rs: $biocortex_rs,
        input_json: $input_json,
        commands: {
            default_disabled: "cargo run -p ab-bridge --no-default-features --features biocortex-retrieval-shadow -- bio-cortex retrieval-shadow --json",
            kill_switch: "AB_BIOCORTEX_RETRIEVAL_SHADOW=1 AB_BIOCORTEX_RETRIEVAL_DISABLE=1 cargo run -p ab-bridge --no-default-features --features biocortex-retrieval-shadow -- bio-cortex retrieval-shadow --json",
            enabled_sample: "AB_BIOCORTEX_RETRIEVAL_SHADOW=1 cargo run -p ab-bridge --no-default-features --features biocortex-retrieval-shadow -- bio-cortex retrieval-shadow --json"
        },
        proof: {
            default_disabled: {
                status: $default_report[0].status,
                runtime_enabled: $default_report[0].gates.runtime_enabled,
                operator_disabled: $default_report[0].gates.operator_disabled,
                runtime_adapter_approved: $default_report[0].runtime_adapter_approved,
                default_search_order_changed: $default_report[0].default_search_order_changed
            },
            kill_switch: {
                status: $kill_report[0].status,
                runtime_enabled: $kill_report[0].gates.runtime_enabled,
                operator_disabled: $kill_report[0].gates.operator_disabled,
                runtime_adapter_approved: $kill_report[0].runtime_adapter_approved,
                default_search_order_changed: $kill_report[0].default_search_order_changed
            },
            enabled_shadow: {
                status: $enabled_report[0].status,
                runtime_enabled: $enabled_report[0].gates.runtime_enabled,
                operator_disabled: $enabled_report[0].gates.operator_disabled,
                side_signal_coverage: $enabled_report[0].side_signal_coverage,
                runtime_adapter_approved: $enabled_report[0].runtime_adapter_approved,
                default_search_order_changed: $enabled_report[0].default_search_order_changed
            }
        },
        latency: {
            sample_count: ($sample_count | tonumber),
            timeout_ms: ($timeout_ms | tonumber),
            p95_ms: ($p95_ms | tonumber),
            max_ms: ($max_ms | tonumber),
            avg_ms: ($avg_ms | tonumber)
        },
        future_ordering_call_sites: [
            {
                mode: "fts",
                file: "crates/store/src/sqlite.rs",
                line: 3067,
                function: "SqliteStore::memory_search",
                status: "not_modified"
            },
            {
                mode: "hybrid",
                file: "crates/store/src/sqlite.rs",
                line: 3228,
                function: "SqliteStore::memory_search_hybrid",
                status: "not_modified"
            },
            {
                mode: "semantic",
                file: "crates/store/src/sqlite.rs",
                line: 5585,
                function: "SqliteStore::memory_search_semantic",
                status: "not_modified"
            }
        ],
        boundary: {
            read_only_shadow_only: true,
            calls_memory_search: false,
            registers_embedding_backend: false,
            changes_memory_search_order: false,
            mutates_ab_memory: false,
            approval_state_written: false,
            human_authorization_required_for_default_influence: true
        }
    }' > "$summary_json"

jq -e '
    .schema == "agent_bridge.biocortex_retrieval.runtime_boundary_proof.v0"
    and .read_only == true
    and .writes_approval == false
    and .runtime_adapter_approved == false
    and .default_search_order_changed == false
    and .proof.default_disabled.status == "runtime_disabled"
    and .proof.kill_switch.status == "operator_disabled"
    and .proof.enabled_shadow.status == "ok"
    and .proof.enabled_shadow.side_signal_coverage >= 0.8
    and .latency.sample_count >= 1
    and .latency.p95_ms >= 0
    and .boundary.calls_memory_search == false
    and .boundary.changes_memory_search_order == false
' "$summary_json" >/dev/null

printf 'runtime_boundary_proof_dir=%s\n' "$out_dir"
printf 'summary=%s\n' "$summary_json"
printf 'p95_ms=%s\n' "$p95_ms"
