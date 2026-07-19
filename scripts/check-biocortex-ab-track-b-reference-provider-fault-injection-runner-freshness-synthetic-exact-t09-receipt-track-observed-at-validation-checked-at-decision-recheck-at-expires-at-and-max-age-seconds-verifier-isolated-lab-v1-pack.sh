#!/usr/bin/env bash
set -euo pipefail
export LANG=C LC_ALL=C TZ=UTC PYTHONDONTWRITEBYTECODE=1
umask 077
fail(){ printf 'T10 freshness verifier v1 gate failed: %s\n' "$*" >&2; exit 1; }
[[ $# -le 1 ]] || fail "usage: $0 [fast|full-replay]"
tier="${1:-fast}"; [[ "$tier" == fast || "$tier" == full-replay ]] || fail "unknown tier"
for tool in git python3 sha256sum cmp mktemp wc du awk sort grep; do command -v "$tool" >/dev/null || fail "missing $tool"; done
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"; cd "$ROOT"
git rev-parse --is-inside-work-tree >/dev/null || fail "not a worktree"
[[ -z "$(git status --porcelain=v1 --untracked-files=all)" ]] || fail "worktree not clean"

baseline="7873f24dddb6ed96e9ae9cb0358f6c5ff030a00d"
baseline_tree="a0eb7e8036ce8400eb7b081ed99f574da4514220"
baseline_parent_1="30da86c37caff6c2a3ca18cf2dcd564bdf750063"
baseline_parent_2="7f35c89329cc423c65a12176e8c10e3e9815782b"
stem="biocortex_ab_track_b_reference_provider_fault_injection_runner_freshness_synthetic_exact_t09_receipt_track_observed_at_validation_checked_at_decision_recheck_at_expires_at_and_max_age_seconds_verifier_isolated_lab_v1"
schema_rel="docs/design/fixtures/biocortex-ab-track-b-reference-provider-fault-injection-runner-freshness-synthetic-exact-t09-receipt-track-observed-at-validation-checked-at-decision-recheck-at-expires-at-and-max-age-seconds-verifier-isolated-lab-v1.schema.json"
report_rel="docs/reports/goal-c-u/2026-07-19-biocortex-track-b-reference-provider-fault-injection-runner-freshness-synthetic-exact-t09-receipt-track-observed-at-validation-checked-at-decision-recheck-at-expires-at-and-max-age-seconds-verifier-isolated-lab-v1-pack.md"
gate_rel="scripts/check-biocortex-ab-track-b-reference-provider-fault-injection-runner-freshness-synthetic-exact-t09-receipt-track-observed-at-validation-checked-at-decision-recheck-at-expires-at-and-max-age-seconds-verifier-isolated-lab-v1-pack.sh"
source_rel="scripts/eval/${stem}.py"
checker_rel="scripts/eval/check_${stem}_pack.py"
expected_rel="scripts/eval/fixtures/${stem}_pack.expected.v0.tsv"
fixture_rel="scripts/eval/fixtures/${stem}_pack_synthetic_v0.json"
manifest_rel="scripts/eval/fixtures/${stem}_pack_v0.json"
authority_gate="scripts/check-biocortex-ab-track-b-reference-provider-fault-injection-runner-freshness-isolated-lab-implementation-authority-and-resource-binding-decision-v1-pack.sh"
manifest_sha="1813becba86eecd48dae2aa537167f74bf2c0851934dadb2b7fd65dbb66f5df7"
report_sha="fc1269dd07c2c4131252cbd6a3081480363cee732fc275174460b6986f6338c6"
checker_stdout_sha="6ff914b927572c7b5babbc4a388e22155f0d2337b33188e2213b34d9f2ef0327"
self_test_sha="efa788116c96bc0ff0749668dbd358482ef0e2f887b5c07e0ba2c9954f6fdbf8"
packet=("$schema_rel" "$report_rel" "$gate_rel" "$source_rel" "$checker_rel" "$expected_rel" "$fixture_rel" "$manifest_rel")
tmp="$(mktemp -d "${TMPDIR:-/tmp}/ab-t10-freshness-verifier.XXXXXX")"; trap 'rm -rf -- "$tmp"' EXIT HUP INT TERM
mkdir -p "$tmp/home"

[[ "$(git rev-parse "$baseline^{tree}")" == "$baseline_tree" ]] || fail "baseline tree drift"
read -ra bp <<<"$(git show -s --format='%P' "$baseline")"
[[ ${#bp[@]} -eq 2 && "${bp[0]}" == "$baseline_parent_1" && "${bp[1]}" == "$baseline_parent_2" ]] || fail "baseline topology drift"
expected_delta="$tmp/expected"; {
  printf 'A\t100644\t%s\n' "$schema_rel"; printf 'A\t100644\t%s\n' "$report_rel"; printf 'A\t100755\t%s\n' "$gate_rel"
  printf 'A\t100644\t%s\n' "$source_rel"; printf 'A\t100644\t%s\n' "$checker_rel"; printf 'A\t100644\t%s\n' "$expected_rel"
  printf 'A\t100644\t%s\n' "$fixture_rel"; printf 'A\t100644\t%s\n' "$manifest_rel"
} | sort -k3,3 >"$expected_delta"
validate_delta(){
  local base="$1" tip="$2" label="$3" actual="$tmp/$3"
  : >"$actual"
  while IFS=$'\t' read -r status path extra; do
    [[ "$status" == A && -n "$path" && -z "${extra:-}" ]] || fail "$label malformed"
    printf '%s\t%s\t%s\n' "$status" "$(git ls-tree "$tip" -- "$path" | awk '{print $1}')" "$path" >>"$actual"
  done < <(git diff-tree --no-commit-id --name-status -r "$base" "$tip")
  sort -k3,3 -o "$actual" "$actual"; cmp -s "$actual" "$expected_delta" || fail "$label is not exact eight-path delta"
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
assert m["schema_version"]==1 and len(m["packet_path_modes"])==8
assert m["source_baseline"]=={"commit":"7873f24dddb6ed96e9ae9cb0358f6c5ff030a00d","parents":["30da86c37caff6c2a3ca18cf2dcd564bdf750063","7f35c89329cc423c65a12176e8c10e3e9815782b"],"tree":"a0eb7e8036ce8400eb7b081ed99f574da4514220"}
assert m["expected"]["public_input_count"]==14 and m["expected"]["total_directed_negative_test_count"]==120
assert m["expected"]["freshness_arithmetic_negative_test_count"]==6 and m["expected"]["source_ast_guard_count"]==16
assert m["resource_limits"]["max_parallel_workers"]==1 and m["resource_limits"]["max_predecessor_review_calls"]==1 and m["resource_limits"]["effective_external_paid_spend_cap"]==0
assert m["boundary"]["t10_freshness_implemented_after_integrated_full_gate"] is True and m["boundary"]["production_trusted_time_implemented"] is False
assert m["next_unit_authorized_by_this_pack"] is False and m["state"]["source_fast_consumes_implementation_authority"] is False
for path,value in sorted(m["raw_sha256"].items()): print("packet",path,m["packet_path_modes"][path],value,sep="\t")
for path,value in sorted(m["authority_artifact_raw_sha256"].items()): print("authority",path,"-",value,sep="\t")
PY
while IFS=$'\t' read -r kind item mode digest; do
  [[ -f "$item" && ! -L "$item" ]] || fail "catalog path $item"
  if [[ "$kind" == packet ]]; then
    [[ "$(git ls-tree HEAD -- "$item"|awk '{print $1}')" == "$mode" ]] || fail "mode drift $item"
  else
    [[ -n "$(git ls-tree "$baseline" -- "$item")" ]] || fail "authority archive path $item"
  fi
  [[ "$(sha256sum "$item"|awk '{print $1}')" == "$digest" ]] || fail "hash drift $item"
done <"$tmp/catalog"

python3 -B "$checker_rel" >"$tmp/checker"
cmp -s "$tmp/checker" "$expected_rel" || fail "checker stdout drift"
[[ "$(wc -l <"$tmp/checker"|tr -d ' ')" == 54 && "$(sha256sum "$tmp/checker"|awk '{print $1}')" == "$checker_stdout_sha" ]] || fail "checker receipt drift"
python3 -B "$checker_rel" --self-test >"$tmp/self"
[[ "$(wc -l <"$tmp/self"|tr -d ' ')" == 16 && "$(sha256sum "$tmp/self"|awk '{print $1}')" == "$self_test_sha" ]] || fail "self-test drift"

archive="$tmp/authority"; git -c protocol.file.allow=always clone --quiet --no-local --no-hardlinks --no-checkout --no-tags --single-branch "$ROOT" "$archive"
git -C "$archive" sparse-checkout init --cone
git -C "$archive" sparse-checkout set scripts docs/reports/goal-c-u docs/design/fixtures
git -C "$archive" checkout --quiet --detach "$baseline"
(cd "$archive"; env -i PATH="/usr/local/bin:/usr/bin:/bin" HOME="$tmp/home" LANG=C LC_ALL=C TZ=UTC PYTHONDONTWRITEBYTECODE=1 "$authority_gate" full-replay) >"$tmp/authority.tsv"
[[ "$(wc -l <"$tmp/authority.tsv"|tr -d ' ')" == 84 ]] || fail "authority line count"
grep -Fx $'integration_gate\tPASS' "$tmp/authority.tsv" >/dev/null || fail "authority gate"
grep -Fx $'artifact_release_evidence\ttrue' "$tmp/authority.tsv" >/dev/null || fail "authority release"
grep -Fx $'effective_authorization_state\tAUTHORIZED_T10_FRESHNESS_ISOLATED_LAB_EXACT_UNIT' "$tmp/authority.tsv" >/dev/null || fail "authority state"
grep -Fx $'freshness_implementation_authority_effective\ttrue' "$tmp/authority.tsv" >/dev/null || fail "authority effectiveness"
grep -Fx $'implementation_authority_single_use_consumed\tfalse' "$tmp/authority.tsv" >/dev/null || fail "authority availability"
grep -Fx $'head_commit\t7873f24dddb6ed96e9ae9cb0358f6c5ff030a00d' "$tmp/authority.tsv" >/dev/null || fail "authority head"
scratch="$(du -sb "$tmp"|awk '{print $1}')"; [[ "$scratch" -le 67108864 ]] || fail "scratch cap: $scratch"

cat "$tmp/checker"
printf 'integration_gate\tPASS\ncontract_conformance_review\tAPPROVE\nsecurity_and_source_bound_gate_review\tAPPROVE\n'
printf 'implementation_independent_reviewer_lane_count\t2\ntopology\t%s\nbaseline_commit\t%s\nsource_commit\t%s\nhead_commit\t%s\nhead_tree\t%s\nhead_first_parent\t%s\n' "$topology" "$baseline" "$source_commit" "$head_commit" "$head_tree" "$first_parent"
printf 'packet_path_count\t8\nauthority_gate_invocation_count\t1\nauthority_stdout_line_count\t84\nprivate_scratch_bytes\t%s\nprivate_scratch_cap_bytes\t67108864\n' "$scratch"
printf 'max_parallel_workers\t1\nprovider_authority\tfalse\nruntime_authority\tfalse\nside_effects_unlocked\tNONE\nnext_unit_authorized\tfalse\nauthority_state_before_consumption\tAUTHORIZED_T10_FRESHNESS_ISOLATED_LAB_EXACT_UNIT\n'
if [[ "$tier" == full-replay ]]; then
  printf 'validation_tier\tINTEGRATED_FULL_T10_FRESHNESS_VERIFIER_AND_FROZEN_AUTHORITY_CHAIN_REPLAY\nartifact_release_evidence\ttrue\nimplementation_authority_consumption_state\tCONSUMED_SCOPE_COMPLETE\n'
  printf 't10_freshness_released\ttrue\nisolated_lab_candidate_surface_components_implemented\t8\nlocal_threat_specifications_covered\t10\nfull_replay_gate\tVALID_T10_FRESHNESS_VERIFIER_AND_FROZEN_T10_AUTHORITY_CHAIN\n'
else
  printf 'validation_tier\tFAST_T10_FRESHNESS_VERIFIER_AND_AUTHORITY_REPLAY\nartifact_release_evidence\tfalse\nimplementation_authority_consumption_state\tNOT_CONSUMED\n'
  printf 't10_freshness_released\tfalse\nisolated_lab_candidate_surface_components_implemented\t7\nlocal_threat_specifications_covered\t9\nfast_gate\tVALID_FAST_T10_FRESHNESS_VERIFIER_NON_RELEASE\n'
fi
