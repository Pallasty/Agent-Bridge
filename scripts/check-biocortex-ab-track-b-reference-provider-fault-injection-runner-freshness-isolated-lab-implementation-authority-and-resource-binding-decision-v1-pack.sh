#!/usr/bin/env bash
set -euo pipefail
export LANG=C LC_ALL=C TZ=UTC PYTHONDONTWRITEBYTECODE=1
umask 077
fail(){ printf 'T10 freshness authority decision v1 gate failed: %s\n' "$*" >&2; exit 1; }
[[ $# -le 1 ]] || fail "usage: $0 [fast|full-replay]"
tier="${1:-fast}"; [[ "$tier" == fast || "$tier" == full-replay ]] || fail "unknown tier"
for tool in git python3 sha256sum cmp mktemp stat wc du awk sort grep; do command -v "$tool" >/dev/null || fail "missing $tool"; done
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"; cd "$ROOT"
git rev-parse --is-inside-work-tree >/dev/null || fail "not a worktree"
[[ -z "$(git status --porcelain=v1 --untracked-files=all)" ]] || fail "worktree not clean"

baseline="80d78735ebda85c62be0af82c0afb18b23bed975"
baseline_tree="3f40474c9fcb40eb596b6dbf8537e27d9ac0bd06"
baseline_parent_1="92fe2facf6f27c85ec0a34a8c46e045b1aaf67e1"
baseline_parent_2="43a8d3bf88ac4e6b9271d5c9bda6766d867879a6"
report_rel="docs/reports/goal-c-u/2026-07-19-biocortex-track-b-reference-provider-fault-injection-runner-freshness-isolated-lab-implementation-authority-and-resource-binding-decision-v1-pack.md"
gate_rel="scripts/check-biocortex-ab-track-b-reference-provider-fault-injection-runner-freshness-isolated-lab-implementation-authority-and-resource-binding-decision-v1-pack.sh"
reviewer_rel="scripts/eval/biocortex_ab_track_b_reference_provider_fault_injection_runner_freshness_isolated_lab_implementation_authority_and_resource_binding_decision_v1.py"
checker_rel="scripts/eval/check_biocortex_ab_track_b_reference_provider_fault_injection_runner_freshness_isolated_lab_implementation_authority_and_resource_binding_decision_v1_pack.py"
expected_rel="scripts/eval/fixtures/biocortex_ab_track_b_reference_provider_fault_injection_runner_freshness_isolated_lab_implementation_authority_and_resource_binding_decision_v1_pack.expected.v0.tsv"
owner_rel="scripts/eval/fixtures/biocortex_ab_track_b_reference_provider_fault_injection_runner_freshness_isolated_lab_implementation_authority_and_resource_binding_decision_v1_pack_owner_decision_v0.json"
manifest_rel="scripts/eval/fixtures/biocortex_ab_track_b_reference_provider_fault_injection_runner_freshness_isolated_lab_implementation_authority_and_resource_binding_decision_v1_pack_v0.json"
semantic_rel="scripts/eval/fixtures/biocortex_ab_track_b_reference_provider_fault_injection_runner_runtime_prerequisite_evidence_packet_offline_integration_and_production_evidence_ingestion_boundary_review_v1_pack_synthetic_v0.json"
predecessor_gate="scripts/check-biocortex-ab-track-b-reference-provider-fault-injection-runner-content-identity-and-quarantine-custody-synthetic-exact-t08-receipt-five-identity-verifier-isolated-lab-v1-pack.sh"
manifest_sha="d48a456ae7e3d2b6507767b9a458a78eeb4c202a6f854afc8ad5a4aa8e9fbb40"
report_sha="0f91c34bb280160e0b3964ff639d83089133aa724b9ce9a6e61f7c3c9c916f79"
checker_stdout_sha="66c3819a558632ed9e75bcea89a80dec891de4ed3599341a51ea82d660006a9f"
self_test_sha="9d7065f422552d91f1b6afa3f5171f5f4c1837ebe88a7fd537357ddc87eed6d6"
packet=("$report_rel" "$gate_rel" "$reviewer_rel" "$checker_rel" "$expected_rel" "$owner_rel" "$manifest_rel")
tmp="$(mktemp -d "${TMPDIR:-/tmp}/ab-t10-freshness-authority.XXXXXX")"; trap 'rm -rf -- "$tmp"' EXIT HUP INT TERM
mkdir -p "$tmp/home"

[[ "$(git rev-parse "$baseline^{tree}")" == "$baseline_tree" ]] || fail "baseline tree drift"
read -ra bp <<<"$(git show -s --format='%P' "$baseline")"
[[ ${#bp[@]} -eq 2 && "${bp[0]}" == "$baseline_parent_1" && "${bp[1]}" == "$baseline_parent_2" ]] || fail "baseline topology drift"
expected_delta="$tmp/expected"; {
  printf 'A\t100644\t%s\n' "$report_rel"; printf 'A\t100755\t%s\n' "$gate_rel"
  printf 'A\t100644\t%s\n' "$reviewer_rel"; printf 'A\t100644\t%s\n' "$checker_rel"
  printf 'A\t100644\t%s\n' "$expected_rel"; printf 'A\t100644\t%s\n' "$owner_rel"
  printf 'A\t100644\t%s\n' "$manifest_rel"
} | sort -k3,3 >"$expected_delta"
validate_delta(){
  local base="$1" tip="$2" label="$3" actual="$tmp/$3"
  : >"$actual"
  while IFS=$'\t' read -r status path extra; do
    [[ "$status" == A && -n "$path" && -z "${extra:-}" ]] || fail "$label malformed"
    printf '%s\t%s\t%s\n' "$status" "$(git ls-tree "$tip" -- "$path" | awk '{print $1}')" "$path" >>"$actual"
  done < <(git diff-tree --no-commit-id --name-status -r "$base" "$tip")
  sort -k3,3 -o "$actual" "$actual"; cmp -s "$actual" "$expected_delta" || fail "$label is not exact seven-path delta"
}
head_commit="$(git rev-parse HEAD)"; head_tree="$(git rev-parse HEAD^{tree})"; read -ra hp <<<"$(git show -s --format='%P' HEAD)"
if [[ ${#hp[@]} -eq 1 && "${hp[0]}" == "$baseline" ]]; then
  topology=SOURCE_COMMIT; first_parent="$baseline"; source_commit="$head_commit"; validate_delta "$baseline" "$source_commit" source
elif [[ ${#hp[@]} -eq 2 ]]; then
  topology=ORDINARY_TWO_PARENT_INTEGRATION; first_parent="${hp[0]}"; source_commit="${hp[1]}"
  git merge-base --is-ancestor "$baseline" "$first_parent" || fail "first parent not descendant of baseline"
  read -ra sp <<<"$(git show -s --format='%P' "$source_commit")"; [[ ${#sp[@]} -eq 1 && "${sp[0]}" == "$baseline" ]] || fail "second parent is not exact source"
  validate_delta "$baseline" "$source_commit" source; validate_delta "$first_parent" "$head_commit" integration
  for item in "${packet[@]}"; do [[ "$(git rev-parse "$source_commit:$item")" == "$(git rev-parse "$head_commit:$item")" ]] || fail "integrated drift $item"; done
else fail "invalid topology"; fi
[[ "$tier" != full-replay || "$topology" == ORDINARY_TWO_PARENT_INTEGRATION ]] || fail "full replay requires ordinary two-parent integration"
[[ "$(sha256sum "$manifest_rel"|awk '{print $1}')" == "$manifest_sha" ]] || fail "manifest hash drift"
[[ "$(sha256sum "$report_rel"|awk '{print $1}')" == "$report_sha" ]] || fail "report hash drift"

python3 -B - "$manifest_rel" >"$tmp/catalog" <<'PY'
import json,sys
from pathlib import Path
m=json.loads(Path(sys.argv[1]).read_text())
assert m["schema_version"]==1 and len(m["packet_path_modes"])==7
assert m["source_baseline"]=={"commit":"80d78735ebda85c62be0af82c0afb18b23bed975","parents":["92fe2facf6f27c85ec0a34a8c46e045b1aaf67e1","43a8d3bf88ac4e6b9271d5c9bda6766d867879a6"],"tree":"3f40474c9fcb40eb596b6dbf8537e27d9ac0bd06"}
assert m["expected"]=={"binding_profile_count":2,"checker_self_test_stdout_line_count":16,"checker_stdout_line_count":55,"directed_negative_test_count":49,"policy_match_dimension_count":7,"public_input_count":14,"request_field_count":5,"source_ast_guard_count":12}
assert m["resource_limits"]["max_parallel_workers"]==1 and m["resource_limits"]["max_predecessor_review_calls"]==1 and m["resource_limits"]["effective_external_paid_spend_cap"]==0
assert m["boundary"]["decision_implements_component_count"]==0 and m["boundary"]["current_released_component_total"]==7 and m["boundary"]["t10_implemented"] is False
assert m["state"]["decision_full_gate_consumes_new_authority"] is False and m["state"]["global_single_use_proved"] is False
for path,value in sorted(m["raw_sha256"].items()): print("packet",path,m["packet_path_modes"][path],value,sep="\t")
for path,value in sorted(m["predecessor_artifact_raw_sha256"].items()): print("predecessor",path,"-",value,sep="\t")
print("semantic","scripts/eval/fixtures/biocortex_ab_track_b_reference_provider_fault_injection_runner_runtime_prerequisite_evidence_packet_offline_integration_and_production_evidence_ingestion_boundary_review_v1_pack_synthetic_v0.json","-",m["semantic_specification_raw_sha256"],sep="\t")
PY
while IFS=$'\t' read -r kind item mode digest; do
  [[ -f "$item" && ! -L "$item" ]] || fail "catalog path $item"
  if [[ "$kind" == packet ]]; then
    [[ "$(git ls-tree HEAD -- "$item"|awk '{print $1}')" == "$mode" ]] || fail "mode drift $item"
  else
    [[ "$(git ls-tree "$baseline" -- "$item"|awk '{print $1}')" == 100644 || "$(git ls-tree "$baseline" -- "$item"|awk '{print $1}')" == 100755 ]] || fail "baseline archive path $item"
  fi
  [[ "$(sha256sum "$item"|awk '{print $1}')" == "$digest" ]] || fail "hash drift $item"
done <"$tmp/catalog"

python3 -B "$checker_rel" >"$tmp/checker"
cmp -s "$tmp/checker" "$expected_rel" || fail "checker stdout drift"
[[ "$(wc -l <"$tmp/checker"|tr -d ' ')" == 55 && "$(sha256sum "$tmp/checker"|awk '{print $1}')" == "$checker_stdout_sha" ]] || fail "checker receipt drift"
python3 -B "$checker_rel" --self-test >"$tmp/self"
[[ "$(wc -l <"$tmp/self"|tr -d ' ')" == 16 && "$(sha256sum "$tmp/self"|awk '{print $1}')" == "$self_test_sha" ]] || fail "self-test drift"

archive="$tmp/predecessor"; git -c protocol.file.allow=always clone --quiet --no-local --no-hardlinks --no-checkout --no-tags --single-branch "$ROOT" "$archive"
git -C "$archive" sparse-checkout init --cone
git -C "$archive" sparse-checkout set scripts docs/reports/goal-c-u docs/design/fixtures
git -C "$archive" checkout --quiet --detach "$baseline"
(cd "$archive"; env -i PATH="/usr/local/bin:/usr/bin:/bin" HOME="$tmp/home" LANG=C LC_ALL=C TZ=UTC PYTHONDONTWRITEBYTECODE=1 "$predecessor_gate" full-replay) >"$tmp/predecessor.tsv"
[[ "$(wc -l <"$tmp/predecessor.tsv"|tr -d ' ')" == 76 ]] || fail "predecessor line count"
grep -Fx $'integration_gate\tPASS' "$tmp/predecessor.tsv" >/dev/null || fail "predecessor gate"
grep -Fx $'artifact_release_evidence\ttrue' "$tmp/predecessor.tsv" >/dev/null || fail "predecessor release"
grep -Fx $'implementation_authority_consumption_state\tCONSUMED_SCOPE_COMPLETE' "$tmp/predecessor.tsv" >/dev/null || fail "predecessor authority consumption"
grep -Fx $'t09_content_identity_and_quarantine_custody_released\ttrue' "$tmp/predecessor.tsv" >/dev/null || fail "predecessor T09 release"
grep -Fx $'head_commit\t80d78735ebda85c62be0af82c0afb18b23bed975' "$tmp/predecessor.tsv" >/dev/null || fail "predecessor head"
scratch="$(du -sb "$tmp"|awk '{print $1}')"; [[ "$scratch" -le 67108864 ]] || fail "scratch cap: $scratch"

cat "$tmp/checker"
printf 'integration_gate\tPASS\ncontract_conformance_review\tAPPROVE\nsecurity_and_source_bound_gate_review\tAPPROVE\n'
printf 'decision_independent_reviewer_lane_count\t2\ntopology\t%s\nbaseline_commit\t%s\nsource_commit\t%s\nhead_commit\t%s\nhead_tree\t%s\nhead_first_parent\t%s\n' "$topology" "$baseline" "$source_commit" "$head_commit" "$head_tree" "$first_parent"
printf 'packet_path_count\t7\npredecessor_gate_invocation_count\t1\npredecessor_stdout_line_count\t76\nprivate_scratch_bytes\t%s\nprivate_scratch_cap_bytes\t67108864\n' "$scratch"
printf 'max_parallel_workers\t1\nprovider_authority\tfalse\nruntime_authority\tfalse\ndecision_full_gate_consumes_new_authority\tfalse\nimplementation_authority_single_use_consumed\tfalse\nside_effects_unlocked\tREVERSIBLE_LOCAL_CODE_SCHEMA_TEST_DOCS_FOR_EXACT_NEXT_UNIT_ONLY\n'
if [[ "$tier" == full-replay ]]; then
  printf 'validation_tier\tINTEGRATED_FULL_FROZEN_T10_FRESHNESS_AUTHORITY_AND_T09_RELEASE_CHAIN_REPLAY\nartifact_release_evidence\ttrue\n'
  printf 'effective_authorization_state\tAUTHORIZED_T10_FRESHNESS_ISOLATED_LAB_EXACT_UNIT\nfreshness_implementation_authority_effective\ttrue\n'
  printf 't10_freshness_implemented\tfalse\ncurrent_released_component_total\t7\nfuture_component_total_after_exact_integrated_full_gate\t8\nfull_replay_gate\tVALID_T10_FRESHNESS_AUTHORITY_DECISION_AND_FROZEN_T09_RELEASE_CHAIN\n'
else
  printf 'validation_tier\tFAST_T10_FRESHNESS_AUTHORITY_CANDIDATE_AND_T09_RELEASE_REPLAY\nartifact_release_evidence\tfalse\n'
  printf 'effective_authorization_state\tUNRECORDED_NO_AUTHORITY\nfreshness_implementation_authority_effective\tfalse\n'
  printf 't10_freshness_implemented\tfalse\ncurrent_released_component_total\t7\nfuture_component_total_after_exact_integrated_full_gate\t8\nfast_gate\tVALID_FAST_T10_FRESHNESS_AUTHORITY_CANDIDATE_NON_RELEASE\n'
fi
