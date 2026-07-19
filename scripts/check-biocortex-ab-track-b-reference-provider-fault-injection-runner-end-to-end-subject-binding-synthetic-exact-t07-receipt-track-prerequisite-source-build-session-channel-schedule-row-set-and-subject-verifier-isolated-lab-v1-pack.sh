#!/usr/bin/env bash
set -euo pipefail

export LANG=C
export LC_ALL=C
export TZ=UTC
export PYTHONDONTWRITEBYTECODE=1
umask 077

fail() {
  printf 'T08 exact end-to-end-subject-binding verifier v1 gate failed: %s\n' "$*" >&2
  exit 1
}

[[ $# -le 1 ]] || fail "usage: $0 [fast|full-replay]"
tier="${1:-fast}"
case "$tier" in
  fast|full-replay) ;;
  *) fail "unknown validation tier: $tier" ;;
esac

for tool in git python3 sha256sum cmp mktemp stat wc du awk sort; do
  command -v "$tool" >/dev/null 2>&1 || fail "required tool missing: $tool"
done

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
cd "$ROOT"
git rev-parse --is-inside-work-tree >/dev/null 2>&1 || fail "not a git worktree"
[[ -z "$(git status --porcelain=v1 --untracked-files=all)" ]] \
  || fail "worktree or index is not clean"

baseline_commit="8521ff6a9784a6d74be2b8ee0e02f3aba6b9f8a5"
baseline_tree="ca054de02381cbd1b94dab05cee5f3f8d2b8bbdd"
baseline_parent_1="6304546b0e0ffec8f6f7b9aa8afbc1c25a48f7a0"
baseline_parent_2="7dad255248e60dc8649c1e1e825a37beaeb530a8"

schema_rel="docs/design/fixtures/biocortex-ab-track-b-reference-provider-fault-injection-runner-end-to-end-subject-binding-synthetic-exact-t07-receipt-track-prerequisite-source-build-session-channel-schedule-row-set-and-subject-verifier-isolated-lab-v1.schema.json"
report_rel="docs/reports/goal-c-u/2026-07-18-biocortex-track-b-reference-provider-fault-injection-runner-end-to-end-subject-binding-synthetic-exact-t07-receipt-track-prerequisite-source-build-session-channel-schedule-row-set-and-subject-verifier-isolated-lab-v1-pack.md"
gate_rel="scripts/check-biocortex-ab-track-b-reference-provider-fault-injection-runner-end-to-end-subject-binding-synthetic-exact-t07-receipt-track-prerequisite-source-build-session-channel-schedule-row-set-and-subject-verifier-isolated-lab-v1-pack.sh"
source_rel="scripts/eval/biocortex_ab_track_b_reference_provider_fault_injection_runner_end_to_end_subject_binding_synthetic_exact_t07_receipt_track_prerequisite_source_build_session_channel_schedule_row_set_and_subject_verifier_isolated_lab_v1.py"
checker_rel="scripts/eval/check_biocortex_ab_track_b_reference_provider_fault_injection_runner_end_to_end_subject_binding_synthetic_exact_t07_receipt_track_prerequisite_source_build_session_channel_schedule_row_set_and_subject_verifier_isolated_lab_v1_pack.py"
expected_rel="scripts/eval/fixtures/biocortex_ab_track_b_reference_provider_fault_injection_runner_end_to_end_subject_binding_synthetic_exact_t07_receipt_track_prerequisite_source_build_session_channel_schedule_row_set_and_subject_verifier_isolated_lab_v1_pack.expected.v0.tsv"
fixture_rel="scripts/eval/fixtures/biocortex_ab_track_b_reference_provider_fault_injection_runner_end_to_end_subject_binding_synthetic_exact_t07_receipt_track_prerequisite_source_build_session_channel_schedule_row_set_and_subject_verifier_isolated_lab_v1_pack_synthetic_v0.json"
manifest_rel="scripts/eval/fixtures/biocortex_ab_track_b_reference_provider_fault_injection_runner_end_to_end_subject_binding_synthetic_exact_t07_receipt_track_prerequisite_source_build_session_channel_schedule_row_set_and_subject_verifier_isolated_lab_v1_pack_v0.json"
authority_gate_rel="scripts/check-biocortex-ab-track-b-reference-provider-fault-injection-runner-end-to-end-subject-binding-isolated-lab-implementation-authority-and-resource-binding-decision-v1-pack.sh"

manifest_sha256="efec8f434b3e957d8a2229cecc0172b9da69a14039dede8b94f7e137ae9d24fe"
report_sha256="0e74e74869826145ef0ccc100793bbb5bc39416398104d68587ba820afa189b9"
checker_stdout_sha256="f08708c42399e94064b1452cfbccaa287462fc18e236b9daed96217affd5f4a4"
checker_self_test_sha256="7adebf036b5f58f8591cc7585eacd3886f9e802277496d5303ee2c357c6a1c28"
authority_fast_sha256="19f63fd5a896346d5451972344abc82de187d0d1265a49fa6aad004fe01df9e8"
authority_full_sha256="779d124f5b71904221ede99a0199dcd53ef404ef4790aea5584f62ed93d40d99"

packet_paths=(
  "$schema_rel"
  "$report_rel"
  "$gate_rel"
  "$source_rel"
  "$checker_rel"
  "$expected_rel"
  "$fixture_rel"
  "$manifest_rel"
)

tmp="$(mktemp -d "${TMPDIR:-/tmp}/ab-t08-verifier-gate.XXXXXX")"
cleanup() {
  rm -rf -- "$tmp"
}
trap cleanup EXIT HUP INT TERM

expected_delta="$tmp/expected-delta.tsv"
{
  printf 'A\t100644\t%s\n' "$schema_rel"
  printf 'A\t100644\t%s\n' "$report_rel"
  printf 'A\t100755\t%s\n' "$gate_rel"
  printf 'A\t100644\t%s\n' "$source_rel"
  printf 'A\t100644\t%s\n' "$checker_rel"
  printf 'A\t100644\t%s\n' "$expected_rel"
  printf 'A\t100644\t%s\n' "$fixture_rel"
  printf 'A\t100644\t%s\n' "$manifest_rel"
} | sort -k3,3 >"$expected_delta"

validate_delta() {
  local base="$1"
  local tip="$2"
  local label="$3"
  local names="$tmp/$label.names"
  local actual="$tmp/$label.actual"
  git diff-tree --no-commit-id --name-status -r "$base" "$tip" >"$names"
  : >"$actual"
  while IFS=$'\t' read -r status path extra; do
    [[ -n "$status" && -n "$path" && -z "${extra:-}" ]] \
      || fail "malformed $label delta"
    [[ "$status" == "A" ]] || fail "$label contains non-addition: $status $path"
    mode="$(git ls-tree "$tip" -- "$path" | awk '{print $1}')"
    [[ -n "$mode" ]] || fail "$label path missing from tree: $path"
    printf '%s\t%s\t%s\n' "$status" "$mode" "$path" >>"$actual"
  done <"$names"
  sort -k3,3 -o "$actual" "$actual"
  cmp -s "$actual" "$expected_delta" || fail "$label is not the exact eight-path packet delta"
}

[[ "$(git rev-parse "$baseline_commit^{tree}")" == "$baseline_tree" ]] \
  || fail "baseline tree drift"
mapfile -t baseline_parents < <(git show -s --format='%P' "$baseline_commit" | tr ' ' '\n')
[[ ${#baseline_parents[@]} -eq 2
   && "${baseline_parents[0]}" == "$baseline_parent_1"
   && "${baseline_parents[1]}" == "$baseline_parent_2" ]] \
  || fail "baseline parent topology drift"

head_commit="$(git rev-parse HEAD)"
head_tree="$(git rev-parse HEAD^{tree})"
mapfile -t head_parents < <(git show -s --format='%P' HEAD | tr ' ' '\n')
topology=""
first_parent=""
source_commit=""

if [[ ${#head_parents[@]} -eq 1 && "${head_parents[0]}" == "$baseline_commit" ]]; then
  topology="SOURCE_COMMIT"
  first_parent="$baseline_commit"
  source_commit="$head_commit"
  validate_delta "$baseline_commit" "$source_commit" source
elif [[ ${#head_parents[@]} -eq 2 ]]; then
  topology="ORDINARY_TWO_PARENT_INTEGRATION"
  first_parent="${head_parents[0]}"
  source_commit="${head_parents[1]}"
  git merge-base --is-ancestor "$baseline_commit" "$first_parent" \
    || fail "integration first parent does not descend from the frozen baseline"
  mapfile -t source_parents < <(git show -s --format='%P' "$source_commit" | tr ' ' '\n')
  [[ ${#source_parents[@]} -eq 1 && "${source_parents[0]}" == "$baseline_commit" ]] \
    || fail "second parent is not the exact source commit"
  validate_delta "$baseline_commit" "$source_commit" source
  validate_delta "$first_parent" "$head_commit" integration
  for path in "${packet_paths[@]}"; do
    [[ "$(git rev-parse "$source_commit:$path")" == "$(git rev-parse "$head_commit:$path")" ]] \
      || fail "integrated packet differs from source commit: $path"
  done
else
  fail "HEAD is neither the authorized source topology nor an ordinary two-parent integration"
fi

if [[ "$tier" == "full-replay" && "$topology" != "ORDINARY_TWO_PARENT_INTEGRATION" ]]; then
  fail "full-replay releases only from the ordinary two-parent integration topology"
fi

[[ "$(sha256sum "$manifest_rel" | awk '{print $1}')" == "$manifest_sha256" ]] \
  || fail "manifest raw hash drift"
[[ "$(sha256sum "$report_rel" | awk '{print $1}')" == "$report_sha256" ]] \
  || fail "report raw hash drift"

manifest_catalog="$tmp/manifest-catalog.tsv"
python3 -B - "$manifest_rel" >"$manifest_catalog" <<'PY'
import json
import sys
from pathlib import Path

manifest = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
expected_packet = {
    "docs/design/fixtures/biocortex-ab-track-b-reference-provider-fault-injection-runner-end-to-end-subject-binding-synthetic-exact-t07-receipt-track-prerequisite-source-build-session-channel-schedule-row-set-and-subject-verifier-isolated-lab-v1.schema.json": "100644",
    "docs/reports/goal-c-u/2026-07-18-biocortex-track-b-reference-provider-fault-injection-runner-end-to-end-subject-binding-synthetic-exact-t07-receipt-track-prerequisite-source-build-session-channel-schedule-row-set-and-subject-verifier-isolated-lab-v1-pack.md": "100644",
    "scripts/check-biocortex-ab-track-b-reference-provider-fault-injection-runner-end-to-end-subject-binding-synthetic-exact-t07-receipt-track-prerequisite-source-build-session-channel-schedule-row-set-and-subject-verifier-isolated-lab-v1-pack.sh": "100755",
    "scripts/eval/biocortex_ab_track_b_reference_provider_fault_injection_runner_end_to_end_subject_binding_synthetic_exact_t07_receipt_track_prerequisite_source_build_session_channel_schedule_row_set_and_subject_verifier_isolated_lab_v1.py": "100644",
    "scripts/eval/check_biocortex_ab_track_b_reference_provider_fault_injection_runner_end_to_end_subject_binding_synthetic_exact_t07_receipt_track_prerequisite_source_build_session_channel_schedule_row_set_and_subject_verifier_isolated_lab_v1_pack.py": "100644",
    "scripts/eval/fixtures/biocortex_ab_track_b_reference_provider_fault_injection_runner_end_to_end_subject_binding_synthetic_exact_t07_receipt_track_prerequisite_source_build_session_channel_schedule_row_set_and_subject_verifier_isolated_lab_v1_pack.expected.v0.tsv": "100644",
    "scripts/eval/fixtures/biocortex_ab_track_b_reference_provider_fault_injection_runner_end_to_end_subject_binding_synthetic_exact_t07_receipt_track_prerequisite_source_build_session_channel_schedule_row_set_and_subject_verifier_isolated_lab_v1_pack_synthetic_v0.json": "100644",
    "scripts/eval/fixtures/biocortex_ab_track_b_reference_provider_fault_injection_runner_end_to_end_subject_binding_synthetic_exact_t07_receipt_track_prerequisite_source_build_session_channel_schedule_row_set_and_subject_verifier_isolated_lab_v1_pack_v0.json": "100644",
}
assert manifest["schema_version"] == 1
assert manifest["authorized_unit"].endswith("_VERIFIER_ISOLATED_LAB_IMPLEMENTATION")
assert manifest["packet_path_modes"] == expected_packet
assert manifest["dependency_topology"] == {
    "authority_decision_pack_artifact_count": 7,
    "direct_dependency_artifact_count": 16,
    "only_current_t08_authority_gate_executed": True,
    "owned_packet_path_count": 8,
    "predecessor_t07_pack_artifact_count": 8,
    "protected_archive_path_count": 24,
    "semantic_specification_artifact_count": 1,
    "t07_gate_not_separately_executed": True,
    "t08_authority_gate_owns_t07_replay": True,
}
assert len(manifest["dependency_artifact_modes"]) == 16
assert set(manifest["dependency_artifact_modes"]) == set(manifest["dependency_artifact_raw_sha256"])
assert manifest["authority"]["decision_fast_stdout_line_count"] == 144
assert manifest["authority"]["decision_fast_stdout_sha256"] == "19f63fd5a896346d5451972344abc82de187d0d1265a49fa6aad004fe01df9e8"
assert manifest["authority"]["decision_full_stdout_line_count"] == 145
assert manifest["authority"]["decision_full_stdout_sha256"] == "779d124f5b71904221ede99a0199dcd53ef404ef4790aea5584f62ed93d40d99"
assert manifest["authority"]["decision_full_gate_consumes_new_authority"] is False
assert manifest["expected"]["checker_stdout_line_count"] == 48
assert manifest["expected"]["checker_stdout_sha256"] == "f08708c42399e94064b1452cfbccaa287462fc18e236b9daed96217affd5f4a4"
assert manifest["expected"]["checker_self_test_stdout_line_count"] == 16
assert manifest["expected"]["checker_self_test_stdout_sha256"] == "7adebf036b5f58f8591cc7585eacd3886f9e802277496d5303ee2c357c6a1c28"
assert manifest["expected"]["positive_track_count"] == 2
assert manifest["expected"]["total_directed_negative_test_count"] == 167
assert manifest["expected"]["fixture_expected_receipt_field_count"] == 93
assert manifest["expected"]["policy_match_dimension_count"] == 10
assert manifest["resource_limits"]["max_parallel_workers"] == 1
assert manifest["resource_limits"]["effective_external_paid_spend_cap"] == 0
assert manifest["boundary"]["isolated_lab_candidate_surface_component_total"] == 6
assert manifest["boundary"]["t09_content_identity_and_quarantine_custody_implemented"] is False
assert manifest["boundary"]["side_effects_unlocked"] == "NONE"
assert manifest["next_unit_authorized_by_this_pack"] is False
assert manifest["state"]["implementation_authority_consumed_only_by_exact_integrated_full_gate"] is True
assert manifest["state"]["source_fast_consumes_implementation_authority"] is False
assert manifest["state"]["integrated_fast_consumes_implementation_authority"] is False
assert set(manifest["raw_sha256"]) == {
    next(path for path in expected_packet if path.endswith(".schema.json")),
    next(path for path in expected_packet if path.endswith("_v1.py")),
    next(path for path in expected_packet if path.endswith("_pack.py")),
    next(path for path in expected_packet if path.endswith(".expected.v0.tsv")),
    next(path for path in expected_packet if path.endswith("_synthetic_v0.json")),
}
for path in sorted(manifest["dependency_artifact_modes"]):
    print(path, manifest["dependency_artifact_modes"][path],
          manifest["dependency_artifact_raw_sha256"][path], sep="\t")
for path in sorted(manifest["raw_sha256"]):
    print(path, expected_packet[path], manifest["raw_sha256"][path], sep="\t")
PY

while IFS=$'\t' read -r path expected_mode expected_hash; do
  [[ -f "$path" && ! -L "$path" ]] || fail "catalog path is not a regular file: $path"
  mode="$(git ls-tree HEAD -- "$path" | awk '{print $1}')"
  [[ "$mode" == "$expected_mode" ]] || fail "catalog mode drift: $path"
  [[ "$(sha256sum "$path" | awk '{print $1}')" == "$expected_hash" ]] \
    || fail "catalog raw hash drift: $path"
done <"$manifest_catalog"

checker_out="$tmp/checker.tsv"
self_test_out="$tmp/self-test.tsv"
python3 -B "$checker_rel" --candidate >"$checker_out"
cmp -s "$checker_out" "$expected_rel" || fail "checker stdout differs from frozen expected TSV"
[[ "$(wc -l <"$checker_out" | tr -d ' ')" == "48" ]] || fail "checker stdout line-count drift"
[[ "$(sha256sum "$checker_out" | awk '{print $1}')" == "$checker_stdout_sha256" ]] \
  || fail "checker stdout hash drift"
python3 -B "$checker_rel" --self-test >"$self_test_out"
[[ "$(wc -l <"$self_test_out" | tr -d ' ')" == "16" ]] || fail "checker self-test line-count drift"
[[ "$(sha256sum "$self_test_out" | awk '{print $1}')" == "$checker_self_test_sha256" ]] \
  || fail "checker self-test hash drift"

auth_repo="$tmp/authority-repo"
git -c protocol.file.allow=always clone --quiet --no-local --no-hardlinks \
  --no-checkout --no-tags --single-branch "$ROOT" "$auth_repo"
git -C "$auth_repo" sparse-checkout init --cone
git -C "$auth_repo" sparse-checkout set scripts docs/reports/goal-c-u docs/design/fixtures
git -C "$auth_repo" checkout --quiet --detach "$baseline_commit"
[[ -z "$(git -C "$auth_repo" status --porcelain=v1 --untracked-files=all)" ]] \
  || fail "protected authority checkout is not clean"

authority_out="$tmp/authority.tsv"
authority_arg="fast"
authority_hash="$authority_fast_sha256"
authority_lines="144"
if [[ "$tier" == "full-replay" ]]; then
  authority_arg="full-replay"
  authority_hash="$authority_full_sha256"
  authority_lines="145"
fi
(
  cd "$auth_repo"
  env -i \
    PATH="/usr/local/bin:/usr/bin:/bin" \
    HOME="$tmp/home" \
    LANG=C LC_ALL=C TZ=UTC \
    PYTHONDONTWRITEBYTECODE=1 \
    "$authority_gate_rel" "$authority_arg"
) >"$authority_out"
[[ "$(wc -l <"$authority_out" | tr -d ' ')" == "$authority_lines" ]] \
  || fail "authority stdout line-count drift"
[[ "$(sha256sum "$authority_out" | awk '{print $1}')" == "$authority_hash" ]] \
  || fail "authority stdout hash drift"
scratch_bytes="$(du -sb "$tmp" | awk '{print $1}')"
[[ "$scratch_bytes" -le 67108864 ]] || fail "private scratch cap exceeded"

cat "$checker_out"
printf 'integration_gate\tPASS\n'
printf 'contract_conformance_review\tAPPROVE\n'
printf 'security_and_source_bound_gate_review\tAPPROVE\n'
printf 'implementation_independent_reviewer_lane_count\t2\n'
printf 'independent_human_reviewer_identity_count_claimed\t0\n'
printf 'topology\t%s\n' "$topology"
printf 'baseline_commit\t%s\n' "$baseline_commit"
printf 'baseline_tree\t%s\n' "$baseline_tree"
printf 'source_commit\t%s\n' "$source_commit"
printf 'source_tree\t%s\n' "$(git rev-parse "$source_commit^{tree}")"
printf 'head_commit\t%s\n' "$head_commit"
printf 'head_tree\t%s\n' "$head_tree"
printf 'head_first_parent\t%s\n' "$first_parent"
printf 'packet_path_count\t8\n'
printf 'direct_dependency_artifact_count\t16\n'
printf 'protected_archive_path_count\t24\n'
printf 'authority_gate_invocation_count\t1\n'
printf 't07_gate_separate_invocation_count\t0\n'
printf 'authority_stdout_line_count\t%s\n' "$authority_lines"
printf 'authority_stdout_sha256\t%s\n' "$authority_hash"
printf 'private_scratch_bytes\t%s\n' "$scratch_bytes"
printf 'private_scratch_cap_bytes\t67108864\n'
printf 'max_parallel_workers\t1\n'
printf 'provider_authority\tfalse\n'
printf 'runtime_authority\tfalse\n'
printf 'side_effects_unlocked\tNONE\n'
printf 't09_content_identity_and_quarantine_custody_implemented\tfalse\n'
printf 'next_unit_authorized\tfalse\n'

if [[ "$tier" == "full-replay" ]]; then
  printf 'validation_tier\tINTEGRATED_FULL_FROZEN_AUTHORITY_CHAIN_REPLAY\n'
  printf 'artifact_release_evidence\ttrue\n'
  printf 'implementation_authority_consumption_state\tCONSUMED_SCOPE_COMPLETE\n'
  printf 't08_end_to_end_subject_binding_released\ttrue\n'
  printf 'isolated_lab_candidate_surface_components_implemented\t6\n'
  printf 'local_threat_specifications_covered\t8\n'
  printf 'periodic_full_replay_required\tfalse\n'
  printf 'full_replay_gate\tVALID_T08_END_TO_END_SUBJECT_BINDING_SYNTHETIC_EXACT_VERIFIER_AND_FULL_FROZEN_AUTHORITY_T07_T06_T05_CHAIN\n'
else
  printf 'validation_tier\tFAST_CONTENT_IDENTITY_AND_AUTHORITY_FAST_REPLAY\n'
  printf 'artifact_release_evidence\tfalse\n'
  printf 'implementation_authority_consumption_state\tNOT_CONSUMED\n'
  printf 't08_end_to_end_subject_binding_released\tfalse\n'
  printf 'isolated_lab_candidate_surface_components_implemented\t5\n'
  printf 'local_threat_specifications_covered\t7\n'
  printf 'periodic_full_replay_required\ttrue\n'
  printf 'fast_gate\tVALID_FAST_T08_END_TO_END_SUBJECT_BINDING_SYNTHETIC_EXACT_VERIFIER_AND_AUTHORITY_REPLAY_NON_RELEASE\n'
fi
