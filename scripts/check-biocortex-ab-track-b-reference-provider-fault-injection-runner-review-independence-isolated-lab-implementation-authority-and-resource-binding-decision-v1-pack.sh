#!/usr/bin/env bash
set -euo pipefail
PATH=/usr/bin:/bin;export PATH LC_ALL=C TZ=UTC PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1 PYTHONSAFEPATH=1
unset BASH_ENV ENV CDPATH PYTHONPATH PYTHONHOME GIT_DIR GIT_WORK_TREE GIT_INDEX_FILE GIT_OBJECT_DIRECTORY GIT_ALTERNATE_OBJECT_DIRECTORIES GIT_REPLACE_REF_BASE
fail(){ printf 'T18 review-independence authority gate failed: %s\n' "$*" >&2;exit 1; };tier="${1:-full-replay}";[[ "$#" -le 1 ]]||fail args;case "$tier" in fast|full-replay);;*)fail tier;;esac
cd "$(dirname "${BASH_SOURCE[0]}")/..";base=3ff026ae7a8e068744ee739f2b60054fd218518a;stem=biocortex_ab_track_b_reference_provider_fault_injection_runner_review_independence_isolated_lab_implementation_authority_and_resource_binding_decision_v1_pack
paths=("docs/reports/goal-c-u/2026-07-20-biocortex-track-b-reference-provider-fault-injection-runner-review-independence-isolated-lab-implementation-authority-and-resource-binding-decision-v1-pack.md" "scripts/check-biocortex-ab-track-b-reference-provider-fault-injection-runner-review-independence-isolated-lab-implementation-authority-and-resource-binding-decision-v1-pack.sh" "scripts/eval/${stem%_pack}.py" "scripts/eval/check_${stem}.py" "scripts/eval/fixtures/${stem}.expected.v0.tsv" "scripts/eval/fixtures/${stem}_owner_decision_v0.json" "scripts/eval/fixtures/${stem}_v0.json");modes=(100644 100755 100644 100644 100644 100644 100644)
[[ -z "$(git status --porcelain --untracked-files=all)" ]]||fail dirty;head=$(git rev-parse HEAD);read -r -a l<<<"$(git rev-list --parents -n1 "$head")";p=("${l[@]:1}");if [[ ${#p[@]} == 1 && "${p[0]}" == "$base" ]];then mode=source;src=$head;elif [[ ${#p[@]} == 2 ]];then mode=integrated;src=${p[1]};[[ "$(git show -s --format=%P "$src")" == "$base" ]]||fail source-shape;else fail topology;fi;[[ "$tier" != full-replay || "$mode" == integrated ]]||fail full
tmp=$(mktemp -d);trap 'rm -rf "$tmp"' EXIT;for x in "${paths[@]}";do printf 'A\t%s\n' "$x";done|sort>"$tmp/w";git diff-tree --no-commit-id --name-status -r "$base" "$src"|sort>"$tmp/a";cmp -s "$tmp/w" "$tmp/a"||fail delta
for i in "${!paths[@]}";do read -r m _ _ x< <(git ls-files --stage -- "${paths[$i]}");[[ "$m" == "${modes[$i]}" && "$x" == "${paths[$i]}" && -f "$x" && ! -L "$x" ]]||fail path;done
python3 "scripts/eval/check_${stem}.py">"$tmp/o";cmp -s "scripts/eval/fixtures/${stem}.expected.v0.tsv" "$tmp/o"||fail expected;python3 "scripts/eval/check_${stem}.py" --self-test|grep -qx $'self_test_boundary\tpass'||fail self-test
python3 - "scripts/eval/fixtures/${stem}_v0.json" <<'PY'
import json,pathlib,sys
m=json.loads(pathlib.Path(sys.argv[1]).read_text());assert m['state']['decision_consumes_authority']is False;assert m['boundary']['t18_implemented']is False and m['boundary']['t19_authorized']is False
PY
printf 't18_review_independence_authority_gate\tpass\nvalidation_tier\t%s\nrelease_topology\t%s\npacket_path_count\t7\ndecision_implements_components\t0\ndecision_consumes_authority\tfalse\n' "$tier" "$mode"
