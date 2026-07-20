#!/usr/bin/env -S -i /usr/bin/bash
set -euo pipefail
umask 077
PATH=/usr/bin:/bin; export PATH LC_ALL=C TZ=UTC PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1 PYTHONSAFEPATH=1
unset BASH_ENV ENV CDPATH PYTHONPATH PYTHONHOME GIT_DIR GIT_WORK_TREE GIT_INDEX_FILE GIT_OBJECT_DIRECTORY GIT_ALTERNATE_OBJECT_DIRECTORIES GIT_REPLACE_REF_BASE
fail(){ printf 'T12 owner-TOCTOU verifier gate failed: %s\n' "$*" >&2; exit 1; }
tier="${1:-full-replay}"; [[ "$#" -le 1 ]] || fail "at most one tier"
case "${tier}" in fast|full-replay);; *) fail "unknown tier";; esac
cd "$(/usr/bin/dirname "${BASH_SOURCE[0]}")/.."; root="$(pwd -P)"
baseline=e75f72c0d020dec5c957d3edb7344350bda20dcd; baseline_tree=54c65b6e6c88ce86a87c88c022aab3af5a45d4fb
schema=docs/design/fixtures/biocortex-ab-track-b-reference-provider-fault-injection-runner-owner-toctou-synthetic-exact-t11-receipt-track-validation-owner-epoch-and-decision-recheck-owner-epoch-verifier-isolated-lab-v1.schema.json
report=docs/reports/goal-c-u/2026-07-19-biocortex-track-b-reference-provider-fault-injection-runner-owner-toctou-synthetic-exact-t11-receipt-track-validation-owner-epoch-and-decision-recheck-owner-epoch-verifier-isolated-lab-v1-pack.md
gate=scripts/check-biocortex-ab-track-b-reference-provider-fault-injection-runner-owner-toctou-synthetic-exact-t11-receipt-track-validation-owner-epoch-and-decision-recheck-owner-epoch-verifier-isolated-lab-v1-pack.sh
source=scripts/eval/biocortex_ab_track_b_reference_provider_fault_injection_runner_owner_toctou_synthetic_exact_t11_receipt_track_validation_owner_epoch_and_decision_recheck_owner_epoch_verifier_isolated_lab_v1.py
checker=scripts/eval/check_biocortex_ab_track_b_reference_provider_fault_injection_runner_owner_toctou_synthetic_exact_t11_receipt_track_validation_owner_epoch_and_decision_recheck_owner_epoch_verifier_isolated_lab_v1_pack.py
expected=scripts/eval/fixtures/biocortex_ab_track_b_reference_provider_fault_injection_runner_owner_toctou_synthetic_exact_t11_receipt_track_validation_owner_epoch_and_decision_recheck_owner_epoch_verifier_isolated_lab_v1_pack.expected.v0.tsv
fixture=scripts/eval/fixtures/biocortex_ab_track_b_reference_provider_fault_injection_runner_owner_toctou_synthetic_exact_t11_receipt_track_validation_owner_epoch_and_decision_recheck_owner_epoch_verifier_isolated_lab_v1_pack_synthetic_v0.json
manifest=scripts/eval/fixtures/biocortex_ab_track_b_reference_provider_fault_injection_runner_owner_toctou_synthetic_exact_t11_receipt_track_validation_owner_epoch_and_decision_recheck_owner_epoch_verifier_isolated_lab_v1_pack_v0.json
paths=("$schema" "$report" "$gate" "$source" "$checker" "$expected" "$fixture" "$manifest"); modes=(100644 100644 100755 100644 100644 100644 100644 100644)
gitc(){ /usr/bin/git --no-pager --no-replace-objects -c core.fsmonitor=false -c core.hooksPath=/dev/null -c safe.directory="$root" "$@"; }
[[ "$(gitc show -s --format=%T "$baseline")" == "$baseline_tree" ]] || fail "baseline tree drift"
[[ -z "$(gitc status --porcelain=v1 --untracked-files=all)" ]] || fail "dirty tree"
head="$(gitc rev-parse HEAD)"; read -r -a line <<<"$(gitc rev-list --parents -n1 "$head")"; parents=("${line[@]:1}"); mode= first= source_commit=
if [[ "${#parents[@]}" == 1 && "${parents[0]}" == "$baseline" ]]; then mode=source; source_commit="$head"
elif [[ "${#parents[@]}" == 2 ]]; then mode=integrated; first="${parents[0]}"; source_commit="${parents[1]}"; read -r -a sl <<<"$(gitc rev-list --parents -n1 "$source_commit")"; sp=("${sl[@]:1}"); [[ "${#sp[@]}" == 1 && "${sp[0]}" == "$baseline" ]] || fail "source shape"; gitc merge-base --is-ancestor "$baseline" "$first" || fail "first-parent baseline"
else fail "invalid release topology"; fi
[[ "$tier" != full-replay || "$mode" == integrated ]] || fail "full requires integration"
tmp="$(/usr/bin/mktemp -d)"; trap '/usr/bin/rm -rf "$tmp"' EXIT
for p in "${paths[@]}"; do printf 'A\t%s\n' "$p"; done | /usr/bin/sort >"$tmp/want"
gitc diff-tree --no-commit-id --name-status -r "$baseline" "$source_commit" | /usr/bin/sort >"$tmp/source"
/usr/bin/cmp -s "$tmp/want" "$tmp/source" || fail "not exact eight-path source"
if [[ "$mode" == integrated ]]; then gitc diff-tree --no-commit-id --name-status -r "$first" "$head" | /usr/bin/sort >"$tmp/full"; /usr/bin/cmp -s "$tmp/want" "$tmp/full" || fail "integration delta"; fi
for i in "${!paths[@]}"; do p="${paths[$i]}"; read -r actual _ _ indexed < <(gitc ls-files --stage -- "$p"); [[ "$actual" == "${modes[$i]}" && "$indexed" == "$p" && -f "$p" && ! -L "$p" ]] || fail "path/mode: $p"; done
/usr/bin/python3 "$checker" >"$tmp/actual"; /usr/bin/cmp -s "$expected" "$tmp/actual" || fail "receipt drift"
/usr/bin/python3 "$checker" --self-test >"$tmp/self"; /usr/bin/grep -qx $'self_test_boundary\tpass' "$tmp/self" || fail "self-test"
/usr/bin/python3 - "$manifest" <<'PY'
import hashlib,json,pathlib,sys
m=json.loads(pathlib.Path(sys.argv[1]).read_text())
assert m["source_baseline"]=={"commit":"e75f72c0d020dec5c957d3edb7344350bda20dcd","tree":"54c65b6e6c88ce86a87c88c022aab3af5a45d4fb"}
assert m["authority"]["implementation_consumes_authority_after_integrated_full"] is True
assert m["boundary"]["component_total_after_integrated_full"]==10 and m["boundary"]["t13_authorized"] is False
for path,digest in m["raw_sha256"].items(): assert hashlib.sha256(pathlib.Path(path).read_bytes()).hexdigest()==digest,path
PY
printf 't12_owner_toctou_verifier_gate\tpass\nvalidation_tier\t%s\nrelease_topology\t%s\npacket_path_count\t8\npredecessor_review_count_per_case\t1\nimplementation_authority_single_use_consumed\ttrue\nisolated_lab_candidate_surface_component_total\t10\nt13_authorized\tfalse\n' "$tier" "$mode"
