#!/usr/bin/env -S -i /usr/bin/bash
set -euo pipefail;umask 077
PATH=/usr/bin:/bin;export PATH LC_ALL=C TZ=UTC PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1 PYTHONSAFEPATH=1
unset BASH_ENV ENV CDPATH PYTHONPATH PYTHONHOME GIT_DIR GIT_WORK_TREE GIT_INDEX_FILE GIT_OBJECT_DIRECTORY GIT_ALTERNATE_OBJECT_DIRECTORIES GIT_REPLACE_REF_BASE
fail(){ printf 'T16 owner-set verifier gate failed: %s\n' "$*" >&2;exit 1; };tier="${1:-full-replay}";[[ "$#" -le 1 ]]||fail args;case "$tier" in fast|full-replay);;*)fail tier;;esac
cd "$(/usr/bin/dirname "${BASH_SOURCE[0]}")/..";root="$(pwd -P)";baseline=1dcdc2656de913bc0fefd2eb5cae89808a9a7a67;tree=a8dad21d19cc05f197112ad9db41c414469d6a88
stem=owner-set-synthetic-exact-t15-receipt-track-and-ordered-owner-entry-t01-through-t15-verifier-isolated-lab-v1;ustem=${stem//-/_}
schema="docs/design/fixtures/biocortex-ab-track-b-reference-provider-fault-injection-runner-${stem}.schema.json";report="docs/reports/goal-c-u/2026-07-20-biocortex-track-b-reference-provider-fault-injection-runner-${stem}-pack.md";gate="scripts/check-biocortex-ab-track-b-reference-provider-fault-injection-runner-${stem}-pack.sh";source="scripts/eval/biocortex_ab_track_b_reference_provider_fault_injection_runner_${ustem}.py";checker="scripts/eval/check_biocortex_ab_track_b_reference_provider_fault_injection_runner_${ustem}_pack.py";expected="scripts/eval/fixtures/biocortex_ab_track_b_reference_provider_fault_injection_runner_${ustem}_pack.expected.v0.tsv";fixture="scripts/eval/fixtures/biocortex_ab_track_b_reference_provider_fault_injection_runner_${ustem}_pack_synthetic_v0.json";manifest="scripts/eval/fixtures/biocortex_ab_track_b_reference_provider_fault_injection_runner_${ustem}_pack_v0.json"
paths=("$schema" "$report" "$gate" "$source" "$checker" "$expected" "$fixture" "$manifest");modes=(100644 100644 100755 100644 100644 100644 100644 100644)
gitc(){ /usr/bin/git --no-pager --no-replace-objects -c core.fsmonitor=false -c core.hooksPath=/dev/null -c safe.directory="$root" "$@"; };[[ "$(gitc show -s --format=%T "$baseline")" == "$tree" ]]||fail baseline;[[ -z "$(gitc status --porcelain=v1 --untracked-files=all)" ]]||fail dirty
head="$(gitc rev-parse HEAD)";read -r -a l<<<"$(gitc rev-list --parents -n1 "$head")";p=("${l[@]:1}");mode= first= src=
if [[ "${#p[@]}" == 1 && "${p[0]}" == "$baseline" ]];then mode=source;src="$head";elif [[ "${#p[@]}" == 2 ]];then mode=integrated;first="${p[0]}";src="${p[1]}";read -r -a sl<<<"$(gitc rev-list --parents -n1 "$src")";sp=("${sl[@]:1}");[[ "${#sp[@]}" == 1 && "${sp[0]}" == "$baseline" ]]||fail source-shape;gitc merge-base --is-ancestor "$baseline" "$first"||fail first-parent;else fail topology;fi;[[ "$tier" != full-replay || "$mode" == integrated ]]||fail full
tmp="$(/usr/bin/mktemp -d)";trap '/usr/bin/rm -rf "$tmp"' EXIT;for x in "${paths[@]}";do printf 'A\t%s\n' "$x";done|sort>"$tmp/w";gitc diff-tree --no-commit-id --name-status -r "$baseline" "$src"|sort>"$tmp/s";cmp -s "$tmp/w" "$tmp/s"||fail delta
for i in "${!paths[@]}";do x="${paths[$i]}";read -r actual _ _ indexed< <(gitc ls-files --stage -- "$x");[[ "$actual" == "${modes[$i]}" && "$indexed" == "$x" && -f "$x" && ! -L "$x" ]]||fail path;done
python3 "$checker">"$tmp/a";cmp -s "$expected" "$tmp/a"||fail receipt;python3 "$checker" --self-test>"$tmp/t";grep -qx $'self_test_boundary\tpass' "$tmp/t"||fail self-test
python3 - "$manifest" <<'PY'
import json,pathlib,sys
m=json.loads(pathlib.Path(sys.argv[1]).read_text());assert m["authority"]["implementation_consumes_authority_after_integrated_full"]is True
PY
printf 't16_owner_set_verifier_gate\tpass\nvalidation_tier\t%s\nrelease_topology\t%s\npacket_path_count\t8\npredecessor_review_count_per_case\t1\nimplementation_authority_single_use_consumed\ttrue\nisolated_lab_candidate_surface_component_total\t14\nt17_authorized\tfalse\n' "$tier" "$mode"
