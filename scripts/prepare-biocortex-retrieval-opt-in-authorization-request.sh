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
plan_fixture="docs/design/fixtures/biocortex-retrieval-opt-in-experiment-plan-2026-06-11.json"
memory_key=""
forum_decision_post_id=""

usage() {
    cat <<'USAGE'
usage: scripts/prepare-biocortex-retrieval-opt-in-authorization-request.sh [flags]

Generates a local human-review request packet for BioCortex retrieval
opt_in_experiment authorization. This is not an approval writer: it never posts
to forum, writes memory, enables BioCortex, or changes retrieval order.

Flags:
  --out-dir PATH                 Output directory.
  --reviewer TEXT                Human reviewer identity.
  --requester TEXT               Requesting agent identity. Default: codex.
  --runtime-proof-summary PATH   proof-summary.json from prove-biocortex-retrieval-runtime-boundary.sh.
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
if [[ ! -f "$plan_fixture" ]]; then
    echo "opt-in plan fixture not found: $plan_fixture" >&2
    exit 2
fi

mkdir -p "$out_dir"

target_host="$(hostname 2>/dev/null || printf 'unknown-host')"
branch="$(git rev-parse --abbrev-ref HEAD 2>/dev/null || printf '<required>')"
commit="$(git rev-parse HEAD 2>/dev/null || printf '<required>')"
request_packet="$out_dir/opt-in-authorization-request.json"

jq -n \
    --slurpfile plan "$plan_fixture" \
    --slurpfile proof "$runtime_proof_summary" \
    --arg generated_at "$generated_at" \
    --arg target_host "$target_host" \
    --arg branch "$branch" \
    --arg commit "$commit" \
    --arg reviewer "$reviewer" \
    --arg requester "$requester" \
    --arg memory_key "$memory_key" \
    --arg forum_decision_post_id "$forum_decision_post_id" \
    '{
        schema: "agent_bridge.biocortex_retrieval.opt_in_authorization_request.v0",
        generated_at: $generated_at,
        status: "request_prepared",
        approval_state: "not_approved",
        authorization_state: "requested_not_granted",
        request_scope: "opt_in_experiment",
        runtime_adapter_approved: false,
        default_search_order_change_allowed: false,
        implementation_allowed: false,
        writes_approval: false,
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
            docs: {
                runtime_proof: "docs/design/BIOCORTEX_RETRIEVAL_RUNTIME_PROOF_2026_06_11.md",
                default_influence_contract: "docs/design/BIOCORTEX_RETRIEVAL_DEFAULT_INFLUENCE_CONTRACT_2026_06_11.md",
                opt_in_experiment_plan: "docs/design/BIOCORTEX_RETRIEVAL_OPT_IN_EXPERIMENT_PLAN_2026_06_11.md"
            }
        },
        current_permissions: {
            may_implement_opt_in_experiment: false,
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
            requires_post_implementation_review_before_use: true
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
    and .approval_state == "not_approved"
    and .authorization_state == "requested_not_granted"
    and .request_scope == "opt_in_experiment"
    and .runtime_adapter_approved == false
    and .default_search_order_change_allowed == false
    and .implementation_allowed == false
    and .writes_approval == false
    and .opt_in_plan.status == "design_only"
    and .opt_in_plan.approval_state == "not_approved"
    and .opt_in_plan.experiment.mode == "fts_only"
    and .opt_in_plan.experiment.affected_call_site.function == "SqliteStore::memory_search"
    and .evidence.runtime_boundary_proof.default_disabled_status == "runtime_disabled"
    and .evidence.runtime_boundary_proof.kill_switch_status == "operator_disabled"
    and .evidence.runtime_boundary_proof.enabled_shadow_status == "ok"
    and .current_permissions.may_implement_opt_in_experiment == false
    and .requested_permission_if_human_authorizes.may_affect_only_explicitly_opted_in_fts_calls == true
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

This is not approval state. It keeps:
- approval_state=not_approved
- authorization_state=requested_not_granted
- runtime_adapter_approved=false
- default_search_order_change_allowed=false
- implementation_allowed=false

If a human later authorizes this request, the allowed implementation scope is
only an FTS-only, per-call opt-in experiment behind a new feature/runtime gate.
It does not authorize default retrieval influence, hybrid influence, semantic
influence, or any behavior without explicit per-call opt-in.
EOF

cat > "$out_dir/memory-note-template.md" <<EOF
BioCortex opt-in experiment authorization request prepared for commit $commit.

Status: request prepared, not approved. The request preserves
runtime_adapter_approved=false, default_search_order_change_allowed=false, and
implementation_allowed=false.

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
not change retrieval behavior.
EOF

printf 'authorization_request_bundle=%s\n' "$out_dir"
printf 'request_packet=%s\n' "$request_packet"
