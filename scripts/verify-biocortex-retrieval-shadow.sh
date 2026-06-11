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
    and .status == "design_only"
    and .approval_state == "not_approved"
    and .runtime_adapter_approved == false
    and .default_search_order_change_allowed == false
    and .implementation_allowed == false
    and .requested_human_authorization_scope == "opt_in_experiment"
    and .requested_default_influence_scope == "none"
    and .default_memory_search_unchanged == true
    and .experiment.mode == "fts_only"
    and .experiment.affected_call_site.function == "SqliteStore::memory_search"
    and any(.experiment.unaffected_call_sites[]; .function == "SqliteStore::memory_search_hybrid" and .status == "not_authorized_not_modified")
    and any(.experiment.unaffected_call_sites[]; .function == "SqliteStore::memory_search_semantic" and .status == "not_authorized_not_modified")
    and .proposed_gates.shadow_enable_is_not_ordering_authorization == true
    and .fail_open.operator_disable == "return_baseline"
    and .human_review_boundary.requires_separate_human_decision_before_implementation == true
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

run cargo test -p ab-bridge --lib --no-default-features \
    biocortex_shadow::tests::retrieval_ -- --nocapture
run cargo test -p ab-bridge --lib --no-default-features \
    --features biocortex-retrieval-shadow \
    biocortex_retrieval_shadow_schema_is_explicit_and_readonly -- --nocapture

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
    and .approval_state == "not_approved"
    and .authorization_state == "requested_not_granted"
    and .request_scope == "opt_in_experiment"
    and .runtime_adapter_approved == false
    and .default_search_order_change_allowed == false
    and .implementation_allowed == false
    and .writes_approval == false
    and .opt_in_plan.status == "design_only"
    and .opt_in_plan.experiment.mode == "fts_only"
    and .evidence.runtime_boundary_proof.default_disabled_status == "runtime_disabled"
    and .evidence.runtime_boundary_proof.kill_switch_status == "operator_disabled"
    and .evidence.runtime_boundary_proof.enabled_shadow_status == "ok"
    and .current_permissions.may_implement_opt_in_experiment == false
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
