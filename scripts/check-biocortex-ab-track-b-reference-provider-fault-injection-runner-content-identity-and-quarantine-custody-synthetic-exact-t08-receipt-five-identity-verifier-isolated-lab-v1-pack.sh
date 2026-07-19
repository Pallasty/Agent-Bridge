#!/usr/bin/env bash
set -euo pipefail
export LANG=C LC_ALL=C TZ=UTC PYTHONDONTWRITEBYTECODE=1
umask 077
fail(){ printf 'T09 five-identity verifier v1 gate failed: %s\n' "$*" >&2; exit 1; }
[[ $# -le 1 ]] || fail "usage: $0 [fast|full-replay]"
tier="${1:-fast}"; [[ "$tier" == fast || "$tier" == full-replay ]] || fail "unknown tier"
for tool in git python3 sha256sum cmp mktemp stat wc du awk sort; do command -v "$tool" >/dev/null || fail "missing $tool"; done
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"; cd "$ROOT"
git rev-parse --is-inside-work-tree >/dev/null || fail "not a worktree"
[[ -z "$(git status --porcelain=v1 --untracked-files=all)" ]] || fail "worktree not clean"

baseline="35575397bfe4ec11278565e0221f46c17130efc4"
baseline_tree="0cb2a7f5ca0e896e4219c4b75bb28ac8b5653faf"
baseline_parent_1="d677e923442661a1d896185923b244d22b726319"
baseline_parent_2="3b188ff1aadc481f55a08c9eaf13d3f66a7ff1ed"
schema_rel="docs/design/fixtures/biocortex-ab-track-b-reference-provider-fault-injection-runner-content-identity-and-quarantine-custody-synthetic-exact-t08-receipt-five-identity-verifier-isolated-lab-v1.schema.json"
report_rel="docs/reports/goal-c-u/2026-07-18-biocortex-track-b-reference-provider-fault-injection-runner-content-identity-and-quarantine-custody-synthetic-exact-t08-receipt-five-identity-verifier-isolated-lab-v1-pack.md"
gate_rel="scripts/check-biocortex-ab-track-b-reference-provider-fault-injection-runner-content-identity-and-quarantine-custody-synthetic-exact-t08-receipt-five-identity-verifier-isolated-lab-v1-pack.sh"
source_rel="scripts/eval/biocortex_ab_track_b_reference_provider_fault_injection_runner_content_identity_and_quarantine_custody_synthetic_exact_t08_receipt_five_identity_verifier_isolated_lab_v1.py"
checker_rel="scripts/eval/check_biocortex_ab_track_b_reference_provider_fault_injection_runner_content_identity_and_quarantine_custody_synthetic_exact_t08_receipt_five_identity_verifier_isolated_lab_v1_pack.py"
expected_rel="scripts/eval/fixtures/biocortex_ab_track_b_reference_provider_fault_injection_runner_content_identity_and_quarantine_custody_synthetic_exact_t08_receipt_five_identity_verifier_isolated_lab_v1_pack.expected.v0.tsv"
fixture_rel="scripts/eval/fixtures/biocortex_ab_track_b_reference_provider_fault_injection_runner_content_identity_and_quarantine_custody_synthetic_exact_t08_receipt_five_identity_verifier_isolated_lab_v1_pack_synthetic_v0.json"
manifest_rel="scripts/eval/fixtures/biocortex_ab_track_b_reference_provider_fault_injection_runner_content_identity_and_quarantine_custody_synthetic_exact_t08_receipt_five_identity_verifier_isolated_lab_v1_pack_v0.json"
authority_gate="scripts/check-biocortex-ab-track-b-reference-provider-fault-injection-runner-content-identity-and-quarantine-custody-isolated-lab-implementation-authority-and-resource-binding-decision-v1-pack.sh"
manifest_sha="879bf18c29ccd7c93661e4344dba37d529fab61182af0868b961400c4ba0e923"
report_sha="87d2cb58dc98519d82f67e681cbad4ec387d3eb77bcfe9dc2ad87af2c569130b"
checker_stdout_sha="9652f827b10e748e596f9032198c0af7a7e25c809f8869583f02fa9526d6a713"
self_test_sha="b325caa309c1cc44a3b00bec9be3e39186bb2a09681bc9276b99d33d88f8a513"
packet=("$schema_rel" "$report_rel" "$gate_rel" "$source_rel" "$checker_rel" "$expected_rel" "$fixture_rel" "$manifest_rel")
tmp="$(mktemp -d "${TMPDIR:-/tmp}/ab-t09-five-identity.XXXXXX")"; trap 'rm -rf -- "$tmp"' EXIT HUP INT TERM

[[ "$(git rev-parse "$baseline^{tree}")" == "$baseline_tree" ]] || fail "baseline tree drift"
read -ra bp <<<"$(git show -s --format='%P' "$baseline")"
[[ ${#bp[@]} -eq 2 && "${bp[0]}" == "$baseline_parent_1" && "${bp[1]}" == "$baseline_parent_2" ]] || fail "baseline topology drift"
expected_delta="$tmp/expected"; {
  printf 'A\t100644\t%s\n' "$schema_rel"; printf 'A\t100644\t%s\n' "$report_rel"; printf 'A\t100755\t%s\n' "$gate_rel"
  printf 'A\t100644\t%s\n' "$source_rel"; printf 'A\t100644\t%s\n' "$checker_rel"; printf 'A\t100644\t%s\n' "$expected_rel"
  printf 'A\t100644\t%s\n' "$fixture_rel"; printf 'A\t100644\t%s\n' "$manifest_rel"
} | sort -k3,3 >"$expected_delta"
validate_delta(){
  local base="$1" tip="$2" label="$3"
  local actual="$tmp/$label"
  : >"$actual"
  while IFS=$'\t' read -r status path extra; do
    [[ "$status" == A && -n "$path" && -z "${extra:-}" ]] || fail "$label malformed"
    printf '%s\t%s\t%s\n' "$status" "$(git ls-tree "$tip" -- "$path" | awk '{print $1}')" "$path" >>"$actual"
  done < <(git diff-tree --no-commit-id --name-status -r "$base" "$tip")
  sort -k3,3 -o "$actual" "$actual"; cmp -s "$actual" "$expected_delta" || fail "$label is not exact eight-path delta"
}
head_commit="$(git rev-parse HEAD)"; head_tree="$(git rev-parse HEAD^{tree})"; read -ra hp <<<"$(git show -s --format='%P' HEAD)"
if [[ ${#hp[@]} -eq 1 && "${hp[0]}" == "$baseline" ]]; then topology=SOURCE_COMMIT; first_parent="$baseline"; source_commit="$head_commit"; validate_delta "$baseline" "$source_commit" source
elif [[ ${#hp[@]} -eq 2 ]]; then
  topology=ORDINARY_TWO_PARENT_INTEGRATION; first_parent="${hp[0]}"; source_commit="${hp[1]}"
  git merge-base --is-ancestor "$baseline" "$first_parent" || fail "first parent not descendant"
  read -ra sp <<<"$(git show -s --format='%P' "$source_commit")"; [[ ${#sp[@]} -eq 1 && "${sp[0]}" == "$baseline" ]] || fail "second parent is not exact source"
  validate_delta "$baseline" "$source_commit" source; validate_delta "$first_parent" "$head_commit" integration
  for item in "${packet[@]}"; do [[ "$(git rev-parse "$source_commit:$item")" == "$(git rev-parse "$head_commit:$item")" ]] || fail "integrated drift $item"; done
else fail "invalid topology"; fi
[[ "$tier" != full-replay || "$topology" == ORDINARY_TWO_PARENT_INTEGRATION ]] || fail "full replay requires integration"
[[ "$(sha256sum "$manifest_rel"|awk '{print $1}')" == "$manifest_sha" ]] || fail "manifest hash drift"
[[ "$(sha256sum "$report_rel"|awk '{print $1}')" == "$report_sha" ]] || fail "report hash drift"

python3 -B - "$manifest_rel" >"$tmp/catalog" <<'PY'
import hashlib,json,sys
from pathlib import Path
m=json.loads(Path(sys.argv[1]).read_text())
assert m["schema_version"]==1 and len(m["packet_path_modes"])==8
assert m["source_baseline"]["commit"]=="35575397bfe4ec11278565e0221f46c17130efc4"
assert m["expected"]["public_input_count"]==12 and m["expected"]["total_directed_negative_test_count"]==115
assert m["resource_limits"]["max_parallel_workers"]==1 and m["resource_limits"]["effective_external_paid_spend_cap"]==0
assert m["boundary"]["production_quarantine_custody_implemented"] is False
assert m["next_unit_authorized_by_this_pack"] is False
for path,value in sorted(m["raw_sha256"].items()): print(path,m["packet_path_modes"][path],value,sep="\t")
PY
while IFS=$'\t' read -r item mode digest; do
  [[ -f "$item" && ! -L "$item" ]] || fail "catalog path"
  [[ "$(git ls-tree HEAD -- "$item"|awk '{print $1}')" == "$mode" ]] || fail "mode drift $item"
  [[ "$(sha256sum "$item"|awk '{print $1}')" == "$digest" ]] || fail "hash drift $item"
done <"$tmp/catalog"

python3 -B "$checker_rel" >"$tmp/checker"
cmp -s "$tmp/checker" "$expected_rel" || fail "checker stdout drift"
[[ "$(wc -l <"$tmp/checker"|tr -d ' ')" == 50 && "$(sha256sum "$tmp/checker"|awk '{print $1}')" == "$checker_stdout_sha" ]] || fail "checker receipt drift"
python3 -B "$checker_rel" --self-test >"$tmp/self"
[[ "$(wc -l <"$tmp/self"|tr -d ' ')" == 16 && "$(sha256sum "$tmp/self"|awk '{print $1}')" == "$self_test_sha" ]] || fail "self-test drift"

auth="$tmp/authority"; git -c protocol.file.allow=always clone --quiet --no-local --no-hardlinks --no-checkout --no-tags --single-branch "$ROOT" "$auth"
git -C "$auth" sparse-checkout init --cone
git -C "$auth" sparse-checkout set scripts docs/reports/goal-c-u docs/design/fixtures
git -C "$auth" checkout --quiet --detach "$baseline"
(cd "$auth"; env -i PATH="/usr/local/bin:/usr/bin:/bin" HOME="$tmp/home" LANG=C LC_ALL=C TZ=UTC PYTHONDONTWRITEBYTECODE=1 "$authority_gate" full-replay) >"$tmp/authority.tsv"
[[ "$(wc -l <"$tmp/authority.tsv"|tr -d ' ')" == 144 ]] || fail "authority line count"
grep -Fx 'gate	PASS' "$tmp/authority.tsv" >/dev/null || fail "authority gate"
grep -Fx 'effective_authorization_state	AUTHORIZED_CONTENT_IDENTITY_AND_QUARANTINE_CUSTODY_ISOLATED_LAB_EXACT_UNIT' "$tmp/authority.tsv" >/dev/null || fail "authority state"
grep -Fx 'content_identity_and_quarantine_custody_implementation_authority_effective	true' "$tmp/authority.tsv" >/dev/null || fail "authority effectiveness"
grep -Fx 'artifact_release_evidence	true' "$tmp/authority.tsv" >/dev/null || fail "authority release"
grep -Fx 'head	35575397bfe4ec11278565e0221f46c17130efc4' "$tmp/authority.tsv" >/dev/null || fail "authority head"
scratch="$(du -sb "$tmp"|awk '{print $1}')"; [[ "$scratch" -le 67108864 ]] || fail "scratch cap: $scratch"

cat "$tmp/checker"
printf 'integration_gate\tPASS\ncontract_conformance_review\tAPPROVE\nsecurity_and_source_bound_gate_review\tAPPROVE\n'
printf 'implementation_independent_reviewer_lane_count\t2\ntopology\t%s\nbaseline_commit\t%s\nsource_commit\t%s\nhead_commit\t%s\nhead_first_parent\t%s\n' "$topology" "$baseline" "$source_commit" "$head_commit" "$first_parent"
printf 'packet_path_count\t8\nauthority_gate_invocation_count\t1\nauthority_stdout_line_count\t144\nprivate_scratch_bytes\t%s\nprivate_scratch_cap_bytes\t67108864\n' "$scratch"
printf 'max_parallel_workers\t1\nprovider_authority\tfalse\nruntime_authority\tfalse\nside_effects_unlocked\tNONE\nnext_unit_authorized\tfalse\n'
if [[ "$tier" == full-replay ]]; then
  printf 'validation_tier\tINTEGRATED_FULL_FROZEN_AUTHORITY_CHAIN_REPLAY\nartifact_release_evidence\ttrue\nimplementation_authority_consumption_state\tCONSUMED_SCOPE_COMPLETE\n'
  printf 't09_content_identity_and_quarantine_custody_released\ttrue\nisolated_lab_candidate_surface_components_implemented\t7\nlocal_threat_specifications_covered\t9\nfull_replay_gate\tVALID_T09_FIVE_IDENTITY_VERIFIER_AND_FROZEN_T08_AUTHORITY_CHAIN\n'
else
  printf 'validation_tier\tFAST_T09_FIVE_IDENTITY_AND_AUTHORITY_REPLAY\nartifact_release_evidence\tfalse\nimplementation_authority_consumption_state\tNOT_CONSUMED\n'
  printf 't09_content_identity_and_quarantine_custody_released\tfalse\nisolated_lab_candidate_surface_components_implemented\t6\nlocal_threat_specifications_covered\t8\nfast_gate\tVALID_FAST_T09_FIVE_IDENTITY_VERIFIER_NON_RELEASE\n'
fi
