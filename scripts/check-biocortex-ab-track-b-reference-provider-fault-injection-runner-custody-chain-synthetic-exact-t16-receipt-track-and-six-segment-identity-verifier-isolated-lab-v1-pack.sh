#!/usr/bin/env bash
set -euo pipefail
PATH=/usr/bin:/bin;export PATH LC_ALL=C TZ=UTC PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1 PYTHONSAFEPATH=1
unset BASH_ENV ENV CDPATH PYTHONPATH PYTHONHOME GIT_DIR GIT_WORK_TREE GIT_INDEX_FILE GIT_OBJECT_DIRECTORY GIT_ALTERNATE_OBJECT_DIRECTORIES GIT_REPLACE_REF_BASE
fail(){ printf 'T17 custody-chain verifier gate failed: %s\n' "$*" >&2;exit 1; }
tier="${1:-full-replay}";[[ "$#" -le 1 ]]||fail args;case "$tier" in fast|full-replay);;*)fail tier;;esac
cd "$(dirname "${BASH_SOURCE[0]}")/..";base=108816d8541ebdb001818cef36425723dc127b79;stem=biocortex_ab_track_b_reference_provider_fault_injection_runner_custody_chain_synthetic_exact_t16_receipt_track_and_six_segment_identity_verifier_isolated_lab_v1
paths=("docs/reports/goal-c-u/2026-07-20-biocortex-track-b-reference-provider-fault-injection-runner-custody-chain-synthetic-exact-t16-receipt-track-and-six-segment-identity-verifier-isolated-lab-v1-pack.md" "scripts/check-biocortex-ab-track-b-reference-provider-fault-injection-runner-custody-chain-synthetic-exact-t16-receipt-track-and-six-segment-identity-verifier-isolated-lab-v1-pack.sh" "scripts/eval/${stem}.py" "scripts/eval/check_${stem}_pack.py" "scripts/eval/fixtures/${stem}_pack.expected.v0.tsv" "scripts/eval/fixtures/${stem}_pack_synthetic_v0.json" "scripts/eval/fixtures/${stem}_pack_v0.json");modes=(100644 100755 100644 100644 100644 100644 100644)
[[ -z "$(git status --porcelain --untracked-files=all)" ]]||fail dirty;head=$(git rev-parse HEAD);read -r -a l<<<"$(git rev-list --parents -n1 "$head")";p=("${l[@]:1}");mode= src=
if [[ ${#p[@]} == 1 && "${p[0]}" == "$base" ]];then mode=source;src=$head;elif [[ ${#p[@]} == 2 ]];then mode=integrated;src=${p[1]};[[ "$(git show -s --format=%P "$src")" == "$base" ]]||fail source-shape;else fail topology;fi;[[ "$tier" != full-replay || "$mode" == integrated ]]||fail full-replay-requires-integration
tmp=$(mktemp -d);trap 'rm -rf "$tmp"' EXIT;for x in "${paths[@]}";do printf 'A\t%s\n' "$x";done|sort>"$tmp/w";git diff-tree --no-commit-id --name-status -r "$base" "$src"|sort>"$tmp/a";cmp -s "$tmp/w" "$tmp/a"||fail delta
for i in "${!paths[@]}";do read -r m _ _ x< <(git ls-files --stage -- "${paths[$i]}");[[ "$m" == "${modes[$i]}" && "$x" == "${paths[$i]}" && -f "$x" && ! -L "$x" ]]||fail path;done
python3 "scripts/eval/check_${stem}_pack.py">"$tmp/o";cmp -s "scripts/eval/fixtures/${stem}_pack.expected.v0.tsv" "$tmp/o"||fail expected;python3 "scripts/eval/check_${stem}_pack.py" --self-test|grep -qx $'self_test_boundary\tpass'||fail self-test
python3 - "scripts/eval/fixtures/${stem}_pack_v0.json" <<'PY'
import json,pathlib,sys
m=json.loads(pathlib.Path(sys.argv[1]).read_text());assert m['authority']['implementation_consumes_authority_after_integrated_full'] is True;assert m['boundary']['t18_authorized'] is False;assert m['boundary']['runtime_authority'] is False and m['boundary']['provider_authority'] is False
PY
printf 't17_custody_chain_verifier_gate\tpass\nvalidation_tier\t%s\nrelease_topology\t%s\npacket_path_count\t7\npredecessor_review_count_per_case\t1\nimplementation_authority_single_use_consumed\ttrue\nisolated_lab_candidate_surface_component_total\t15\nt18_authorized\tfalse\n' "$tier" "$mode"
