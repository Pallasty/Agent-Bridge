#!/usr/bin/env -S -i /usr/bin/bash
set -euo pipefail
umask 077

PATH=/usr/bin:/bin
export PATH LC_ALL=C TZ=UTC PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1 PYTHONSAFEPATH=1
unset BASH_ENV ENV CDPATH PYTHONPATH PYTHONHOME GIT_DIR GIT_WORK_TREE GIT_INDEX_FILE
unset GIT_OBJECT_DIRECTORY GIT_ALTERNATE_OBJECT_DIRECTORIES GIT_REPLACE_REF_BASE

fail() { printf 'T12 owner-TOCTOU authority decision gate failed: %s\n' "$*" >&2; exit 1; }
tier="${1:-full-replay}"
[[ "$#" -le 1 ]] || fail "expected at most one validation tier"
case "${tier}" in fast|full-replay) ;; *) fail "unknown validation tier: ${tier}" ;; esac

cd "$(/usr/bin/dirname "${BASH_SOURCE[0]}")/.."
root="$(pwd -P)"
baseline=3df8536c841390fdc593fa4a518885b3f2291fc6
baseline_tree=bdccc42dc1d4e4c30f57f0d464fc5a58f832b0d6
reviewer=scripts/eval/biocortex_ab_track_b_reference_provider_fault_injection_runner_owner_toctou_isolated_lab_implementation_authority_and_resource_binding_decision_v1.py
checker=scripts/eval/check_biocortex_ab_track_b_reference_provider_fault_injection_runner_owner_toctou_isolated_lab_implementation_authority_and_resource_binding_decision_v1_pack.py
owner=scripts/eval/fixtures/biocortex_ab_track_b_reference_provider_fault_injection_runner_owner_toctou_isolated_lab_implementation_authority_and_resource_binding_decision_v1_pack_owner_decision_v0.json
expected=scripts/eval/fixtures/biocortex_ab_track_b_reference_provider_fault_injection_runner_owner_toctou_isolated_lab_implementation_authority_and_resource_binding_decision_v1_pack.expected.v0.tsv
manifest=scripts/eval/fixtures/biocortex_ab_track_b_reference_provider_fault_injection_runner_owner_toctou_isolated_lab_implementation_authority_and_resource_binding_decision_v1_pack_v0.json
report=docs/reports/goal-c-u/2026-07-19-biocortex-track-b-reference-provider-fault-injection-runner-owner-toctou-isolated-lab-implementation-authority-and-resource-binding-decision-v1-pack.md
gate=scripts/check-biocortex-ab-track-b-reference-provider-fault-injection-runner-owner-toctou-isolated-lab-implementation-authority-and-resource-binding-decision-v1-pack.sh
paths=("${reviewer}" "${checker}" "${owner}" "${expected}" "${manifest}" "${report}" "${gate}")
modes=(100644 100644 100644 100644 100644 100644 100755)

gitc() { /usr/bin/git --no-pager --no-replace-objects -c core.fsmonitor=false -c core.hooksPath=/dev/null -c safe.directory="${root}" "$@"; }
[[ "$(gitc show -s --format=%T "${baseline}")" == "${baseline_tree}" ]] || fail "baseline tree drift"
[[ "$(gitc rev-parse --is-shallow-repository)" == false ]] || fail "shallow history"
[[ -z "$(gitc status --porcelain=v1 --untracked-files=all)" ]] || fail "worktree or index is not clean"
head="$(gitc rev-parse HEAD)"
read -r -a lineage <<<"$(gitc rev-list --parents -n 1 "${head}")"
parents=("${lineage[@]:1}")
mode= source= first_parent=
if [[ "${#parents[@]}" == 1 && "${parents[0]}" == "${baseline}" ]]; then
  mode=source; source="${head}"
elif [[ "${#parents[@]}" == 2 ]]; then
  mode=integrated; first_parent="${parents[0]}"; source="${parents[1]}"
  read -r -a source_lineage <<<"$(gitc rev-list --parents -n 1 "${source}")"
  source_parents=("${source_lineage[@]:1}")
  [[ "${#source_parents[@]}" == 1 && "${source_parents[0]}" == "${baseline}" ]] || fail "second parent is not the exact source shape"
  gitc merge-base --is-ancestor "${baseline}" "${first_parent}" || fail "first parent does not descend from baseline"
else
  fail "HEAD is neither exact source nor ordinary two-parent integration"
fi
[[ "${tier}" != full-replay || "${mode}" == integrated ]] || fail "full replay requires ordinary integration"

tmp="$(/usr/bin/mktemp -d)"; trap '/usr/bin/rm -rf "${tmp}"' EXIT
for p in "${paths[@]}"; do printf 'A\t%s\n' "${p}"; done | /usr/bin/sort >"${tmp}/expected-delta"
gitc diff-tree --no-commit-id --name-status -r "${baseline}" "${source}" | /usr/bin/sort >"${tmp}/source-delta"
/usr/bin/cmp -s "${tmp}/expected-delta" "${tmp}/source-delta" || fail "source is not the exact seven-path all-add delta"
if [[ "${mode}" == integrated ]]; then
  gitc diff-tree --no-commit-id --name-status -r "${first_parent}" "${head}" | /usr/bin/sort >"${tmp}/integration-delta"
  /usr/bin/cmp -s "${tmp}/expected-delta" "${tmp}/integration-delta" || fail "integration first-parent delta drift"
fi
for i in "${!paths[@]}"; do
  p="${paths[$i]}"; wanted="${modes[$i]}"
  read -r actual _ _ indexed < <(gitc ls-files --stage -- "${p}")
  [[ "${actual}" == "${wanted}" && "${indexed}" == "${p}" && -f "${p}" && ! -L "${p}" ]] || fail "path identity or mode drift: ${p}"
done

/usr/bin/python3 "${checker}" >"${tmp}/actual.tsv"
/usr/bin/cmp -s "${expected}" "${tmp}/actual.tsv" || fail "checker receipt drift"
/usr/bin/python3 "${checker}" --self-test >"${tmp}/self-test.tsv"
/usr/bin/grep -qx $'self_test_boundary\tpass' "${tmp}/self-test.tsv" || fail "checker self-test failed"
/usr/bin/python3 - "${manifest}" <<'PY'
import hashlib, json, pathlib, sys
m = json.loads(pathlib.Path(sys.argv[1]).read_text())
assert m["source_baseline"] == {"commit": "3df8536c841390fdc593fa4a518885b3f2291fc6", "tree": "bdccc42dc1d4e4c30f57f0d464fc5a58f832b0d6"}
assert m["boundary"] == {"current_component_total": 9, "decision_implements_components": 0, "future_component_total": 10, "t12_implemented": False}
assert m["state"]["decision_consumes_authority"] is False
for path, digest in m["raw_sha256"].items():
    assert hashlib.sha256(pathlib.Path(path).read_bytes()).hexdigest() == digest, path
PY

printf 't12_owner_toctou_authority_gate\tpass\n'
printf 'validation_tier\t%s\n' "${tier}"
printf 'release_topology\t%s\n' "${mode}"
printf 'packet_path_count\t7\n'
printf 'decision_implements_components\t0\n'
printf 'decision_consumes_authority\tfalse\n'
printf 'authorized_next_unit\tT12_OWNER_TOCTOU_ISOLATED_LAB_IMPLEMENTATION\n'
