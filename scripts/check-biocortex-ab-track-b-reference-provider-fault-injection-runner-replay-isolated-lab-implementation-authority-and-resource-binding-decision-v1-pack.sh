#!/usr/bin/env -S -i /usr/bin/bash
set -euo pipefail
umask 077
PATH=/usr/bin:/bin;export PATH LC_ALL=C TZ=UTC PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1 PYTHONSAFEPATH=1
unset BASH_ENV ENV CDPATH PYTHONPATH PYTHONHOME GIT_DIR GIT_WORK_TREE GIT_INDEX_FILE GIT_OBJECT_DIRECTORY GIT_ALTERNATE_OBJECT_DIRECTORIES GIT_REPLACE_REF_BASE
fail(){ printf 'T13 replay authority decision gate failed: %s\n' "$*" >&2;exit 1; }
tier="${1:-full-replay}";[[ "$#" -le 1 ]]||fail "at most one tier";case "$tier" in fast|full-replay);;*)fail "unknown tier";;esac
cd "$(/usr/bin/dirname "${BASH_SOURCE[0]}")/..";root="$(pwd -P)"
baseline=01da2b0af37fd73e4edd1ceb6183b0a6cf87224d;baseline_tree=cb87cc15c99dbb0feedf3b204de4ae4d726b8bbb
report=docs/reports/goal-c-u/2026-07-19-biocortex-track-b-reference-provider-fault-injection-runner-replay-isolated-lab-implementation-authority-and-resource-binding-decision-v1-pack.md
gate=scripts/check-biocortex-ab-track-b-reference-provider-fault-injection-runner-replay-isolated-lab-implementation-authority-and-resource-binding-decision-v1-pack.sh
reviewer=scripts/eval/biocortex_ab_track_b_reference_provider_fault_injection_runner_replay_isolated_lab_implementation_authority_and_resource_binding_decision_v1.py
checker=scripts/eval/check_biocortex_ab_track_b_reference_provider_fault_injection_runner_replay_isolated_lab_implementation_authority_and_resource_binding_decision_v1_pack.py
expected=scripts/eval/fixtures/biocortex_ab_track_b_reference_provider_fault_injection_runner_replay_isolated_lab_implementation_authority_and_resource_binding_decision_v1_pack.expected.v0.tsv
owner=scripts/eval/fixtures/biocortex_ab_track_b_reference_provider_fault_injection_runner_replay_isolated_lab_implementation_authority_and_resource_binding_decision_v1_pack_owner_decision_v0.json
manifest=scripts/eval/fixtures/biocortex_ab_track_b_reference_provider_fault_injection_runner_replay_isolated_lab_implementation_authority_and_resource_binding_decision_v1_pack_v0.json
paths=("$report" "$gate" "$reviewer" "$checker" "$expected" "$owner" "$manifest");modes=(100644 100755 100644 100644 100644 100644 100644)
gitc(){ /usr/bin/git --no-pager --no-replace-objects -c core.fsmonitor=false -c core.hooksPath=/dev/null -c safe.directory="$root" "$@"; }
[[ "$(gitc show -s --format=%T "$baseline")" == "$baseline_tree" ]]||fail "baseline tree"
[[ -z "$(gitc status --porcelain=v1 --untracked-files=all)" ]]||fail "dirty tree"
head="$(gitc rev-parse HEAD)";read -r -a line<<<"$(gitc rev-list --parents -n1 "$head")";parents=("${line[@]:1}");mode= first= source=
if [[ "${#parents[@]}" == 1 && "${parents[0]}" == "$baseline" ]];then mode=source;source="$head"
elif [[ "${#parents[@]}" == 2 ]];then mode=integrated;first="${parents[0]}";source="${parents[1]}";read -r -a sl<<<"$(gitc rev-list --parents -n1 "$source")";sp=("${sl[@]:1}");[[ "${#sp[@]}" == 1 && "${sp[0]}" == "$baseline" ]]||fail "source shape";gitc merge-base --is-ancestor "$baseline" "$first"||fail "first parent"
else fail "release topology";fi
[[ "$tier" != full-replay || "$mode" == integrated ]]||fail "full requires integration"
tmp="$(/usr/bin/mktemp -d)";trap '/usr/bin/rm -rf "$tmp"' EXIT
for p in "${paths[@]}";do printf 'A\t%s\n' "$p";done|/usr/bin/sort>"$tmp/want"
gitc diff-tree --no-commit-id --name-status -r "$baseline" "$source"|/usr/bin/sort>"$tmp/source";/usr/bin/cmp -s "$tmp/want" "$tmp/source"||fail "not exact seven-path source"
if [[ "$mode" == integrated ]];then gitc diff-tree --no-commit-id --name-status -r "$first" "$head"|/usr/bin/sort>"$tmp/full";/usr/bin/cmp -s "$tmp/want" "$tmp/full"||fail "integration delta";fi
for i in "${!paths[@]}";do p="${paths[$i]}";read -r actual _ _ indexed< <(gitc ls-files --stage -- "$p");[[ "$actual" == "${modes[$i]}" && "$indexed" == "$p" && -f "$p" && ! -L "$p" ]]||fail "path/mode $p";done
/usr/bin/python3 "$checker">"$tmp/actual";/usr/bin/cmp -s "$expected" "$tmp/actual"||fail "receipt drift";/usr/bin/python3 "$checker" --self-test>"$tmp/self";/usr/bin/grep -qx $'self_test_boundary\tpass' "$tmp/self"||fail "self-test"
/usr/bin/python3 - "$manifest" <<'PY'
import hashlib,json,pathlib,sys
m=json.loads(pathlib.Path(sys.argv[1]).read_text())
assert m["source_baseline"]=={"commit":"01da2b0af37fd73e4edd1ceb6183b0a6cf87224d","tree":"cb87cc15c99dbb0feedf3b204de4ae4d726b8bbb"}
assert m["boundary"]=={"current_component_total":10,"decision_implements_components":0,"future_component_total":11,"t13_implemented":False,"t14_authorized":False}
assert m["state"]["decision_consumes_authority"] is False
for p,h in m["raw_sha256"].items():assert hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()==h,p
PY
printf 't13_replay_authority_gate\tpass\nvalidation_tier\t%s\nrelease_topology\t%s\npacket_path_count\t7\ndecision_implements_components\t0\ndecision_consumes_authority\tfalse\nauthorized_next_unit\tT13_REPLAY_ISOLATED_LAB_IMPLEMENTATION\n' "$tier" "$mode"
