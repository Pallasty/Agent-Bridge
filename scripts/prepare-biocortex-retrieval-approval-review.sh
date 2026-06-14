#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"

ts="$(date -u +%Y%m%dT%H%M%SZ)"
out_dir="${TMPDIR:-/tmp}/ab-biocortex-retrieval-approval-review-$ts"
reviewer=""
agent_attestor="codex"
agent_attestation_decision="technical_review_pending"
agent_attestation_summary=""
human_authorization_scope="none"
verification_log=""
memory_key=""
forum_decision_post_id=""
side_signal_p95=""
default_search_latency="0"
exact_call_site=""
fail_open_behavior="baseline-only fallback; BioCortex absence, slowness, or errors must not block default memory_search"
rollback_command="AB_BIOCORTEX_RETRIEVAL_DISABLE=1"

usage() {
    cat <<'USAGE'
usage: scripts/prepare-biocortex-retrieval-approval-review.sh [flags]

Generates a local BioCortex runtime approval review-prep bundle. This is not an
approval writer: it never posts to forum, writes memory, enables BioCortex, or
changes retrieval order.

Flags:
  --out-dir PATH                         Output directory.
  --reviewer TEXT                        Human reviewer identity.
  --agent-attestor TEXT                  Agent technical attestor identity.
  --agent-attestation-decision TEXT      Agent decision: approve, reject, defer, or technical_review_pending.
  --agent-attestation-summary TEXT       Agent technical attestation summary.
  --human-authorization-scope TEXT       Human authorization scope; default: none.
  --verification-log PATH                Log from verify-biocortex-retrieval-shadow.sh.
  --memory-key KEY                       Memory key to cite in generated templates.
  --forum-decision-post-id ID            Forum post id to cite in generated templates.
  --side-signal-p95-ms VALUE             Measured p95 side-signal latency.
  --default-memory-search-added-latency-ms VALUE
                                         Measured added default memory_search latency.
  --exact-call-site TEXT                 Proposed ordering-change call site.
  --fail-open-behavior TEXT              Proposed fail-open behavior.
  --rollback-command TEXT                Rollback command.
  -h, --help                             Show this help.
USAGE
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --out-dir) out_dir="$2"; shift 2 ;;
        --reviewer) reviewer="$2"; shift 2 ;;
        --agent-attestor) agent_attestor="$2"; shift 2 ;;
        --agent-attestation-decision) agent_attestation_decision="$2"; shift 2 ;;
        --agent-attestation-summary) agent_attestation_summary="$2"; shift 2 ;;
        --human-authorization-scope) human_authorization_scope="$2"; shift 2 ;;
        --verification-log) verification_log="$2"; shift 2 ;;
        --memory-key) memory_key="$2"; shift 2 ;;
        --forum-decision-post-id) forum_decision_post_id="$2"; shift 2 ;;
        --side-signal-p95-ms) side_signal_p95="$2"; shift 2 ;;
        --default-memory-search-added-latency-ms) default_search_latency="$2"; shift 2 ;;
        --exact-call-site) exact_call_site="$2"; shift 2 ;;
        --fail-open-behavior) fail_open_behavior="$2"; shift 2 ;;
        --rollback-command) rollback_command="$2"; shift 2 ;;
        -h|--help) usage; exit 0 ;;
        *) echo "unknown flag: $1" >&2; usage >&2; exit 2 ;;
    esac
done

mkdir -p "$out_dir"

target_host="$(hostname 2>/dev/null || printf 'unknown-host')"
branch="$(git rev-parse --abbrev-ref HEAD 2>/dev/null || printf '<required>')"
commit="$(git rev-parse HEAD 2>/dev/null || printf '<required>')"
verification_status=""
verification_captured_at=""
current_gate_status=""
hard_gate_status=""

if [[ -n "$verification_log" ]]; then
    if [[ ! -f "$verification_log" ]]; then
        echo "verification log not found: $verification_log" >&2
        exit 2
    fi
    cp "$verification_log" "$out_dir/verification.log"
    verification_captured_at="$(date -u -r "$verification_log" +%Y-%m-%dT%H:%M:%SZ 2>/dev/null || date -u +%Y-%m-%dT%H:%M:%SZ)"
    if grep -q "verify-biocortex-retrieval-shadow.sh: all checks passed" "$verification_log"; then
        verification_status="pass"
        current_gate_status="side_signal_passes_offline_gate"
        hard_gate_status="side_signal_passes_offline_gate"
    fi
fi

packet="$out_dir/approval-packet-preview.json"
args=(
    cargo run -p ab-bridge --no-default-features --
    bio-cortex retrieval-approval-packet --json
    --target-host "$target_host"
    --branch "$branch"
    --commit "$commit"
    --default-memory-search-added-latency-ms "$default_search_latency"
    --fail-open-behavior "$fail_open_behavior"
    --rollback-command "$rollback_command"
    --agent-attestor "$agent_attestor"
    --agent-attestation-decision "$agent_attestation_decision"
    --human-authorization-scope "$human_authorization_scope"
)

[[ -n "$reviewer" ]] && args+=(--reviewer "$reviewer")
[[ -n "$agent_attestation_summary" ]] && args+=(--agent-attestation-summary "$agent_attestation_summary")
[[ -n "$verification_status" ]] && args+=(--verification-status "$verification_status")
[[ -n "$verification_captured_at" ]] && args+=(--verification-captured-at "$verification_captured_at")
[[ -n "$current_gate_status" ]] && args+=(--current-gate-status "$current_gate_status")
[[ -n "$hard_gate_status" ]] && args+=(--hard-holdout-gate-status "$hard_gate_status")
[[ -n "$side_signal_p95" ]] && args+=(--side-signal-p95-ms-for-5-candidates "$side_signal_p95")
[[ -n "$exact_call_site" ]] && args+=(--exact-call-site "$exact_call_site")
[[ -n "$forum_decision_post_id" ]] && args+=(--forum-decision-post-id "$forum_decision_post_id")
[[ -n "$memory_key" ]] && args+=(--memory-key "$memory_key")

"${args[@]}" > "$packet"

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
    and .human_authorization.scope == "none"
    and .human_authorization.can_be_replaced_by_agent_attestation == false
' "$packet" >/dev/null

missing_count="$(jq '.missing_evidence | length' "$packet")"

cat > "$out_dir/forum-post-template.md" <<EOF
BioCortex runtime approval review-prep packet generated.

Packet: approval-packet-preview.json
Commit under review: $commit
Branch: $branch
Host: $target_host
Reviewer: ${reviewer:-<required>}
Agent technical attestor: $agent_attestor
Agent technical decision: $agent_attestation_decision
Human authorization scope: $human_authorization_scope
Verification log: ${verification_log:-<required>}
Missing evidence count: $missing_count

This is not approval state. The packet keeps:
- approval_state=not_approved
- runtime_adapter_approved=false
- writes_approval=false
- approval_writes_allowed=false
- default_search_order_change_allowed=false
- ready_for_human_approval_review=false
- agent_technical_attestation.can_authorize_runtime_influence=false
- human_authorization.status=not_authorized

Agent technical attestation can recommend approve/reject/defer, but cannot
replace human authorization. Human approval, if ever granted, must be a separate
decision that explicitly allows a scope and names the reviewed implementation
commit.
EOF

cat > "$out_dir/memory-note-template.md" <<EOF
BioCortex runtime approval review-prep packet generated for commit $commit.

Status: not approved. The packet preserves runtime_adapter_approved=false,
approval_writes_allowed=false, default_search_order_change_allowed=false, and
ready_for_human_approval_review=false.
Agent technical attestor: $agent_attestor
Agent technical decision: $agent_attestation_decision
Human authorization scope: $human_authorization_scope
Agent technical attestation cannot replace human authorization.

Packet path at generation time: $packet
Forum decision post id: ${forum_decision_post_id:-<required>}
Memory key: ${memory_key:-<required>}
Missing evidence count: $missing_count
EOF

cat > "$out_dir/README.md" <<EOF
# BioCortex Retrieval Approval Review Prep

Generated: $ts

Files:
- approval-packet-preview.json
- forum-post-template.md
- memory-note-template.md
$(if [[ -n "$verification_log" ]]; then printf '%s\n' "- verification.log"; fi)

This bundle is review preparation only. It is not approval state and it does
not change retrieval behavior.
EOF

printf 'review_bundle=%s\n' "$out_dir"
printf 'packet=%s\n' "$packet"
printf 'missing_evidence_count=%s\n' "$missing_count"
