#!/usr/bin/env -S -i /usr/bin/bash
# Source-bound, descendant-compatible, non-admitting gate for the Track B
# successor admission/map v1 source packet.
set -euo pipefail
umask 077

while IFS= read -r imported_function; do
  builtin unset -f "${imported_function}"
done < <(builtin compgen -A function)

PATH=/usr/bin:/bin
export PATH LC_ALL=C TZ=UTC
export PYTHONDONTWRITEBYTECODE=1
export PYTHONNOUSERSITE=1
export PYTHONSAFEPATH=1
export GIT_OPTIONAL_LOCKS=0
unset BASH_ENV ENV CDPATH PERL5OPT PERL5LIB PERL_UNICODE
unset LD_AUDIT LD_LIBRARY_PATH LD_PRELOAD
unset PYTHONPATH PYTHONHOME PYTHONINSPECT PYTHONSTARTUP PYTHONWARNINGS
unset PYTHONBREAKPOINT PYTHONUSERBASE
unset GIT_DIR GIT_WORK_TREE GIT_COMMON_DIR GIT_INDEX_FILE
unset GIT_OBJECT_DIRECTORY GIT_ALTERNATE_OBJECT_DIRECTORIES
unset GIT_REPLACE_REF_BASE GIT_CONFIG GIT_CONFIG_COUNT
unset GIT_CONFIG_PARAMETERS GIT_NAMESPACE GIT_SHALLOW_FILE
unset GIT_CEILING_DIRECTORIES GIT_DISCOVERY_ACROSS_FILESYSTEM
export GIT_CONFIG_NOSYSTEM=1
export GIT_CONFIG_GLOBAL=/dev/null
export GIT_CONFIG_SYSTEM=/dev/null

for absolute_tool in /usr/bin/awk /usr/bin/bash /usr/bin/cat /usr/bin/chmod \
  /usr/bin/cmp /usr/bin/dirname /usr/bin/env /usr/bin/git /usr/bin/head \
  /usr/bin/mkdir /usr/bin/mktemp /usr/bin/python3 /usr/bin/rm \
  /usr/bin/sha256sum /usr/bin/sort /usr/bin/stat /usr/bin/tar; do
  [[ -x "${absolute_tool}" ]] || {
    printf 'Track B successor admission/map v1 gate missing trusted tool: %s\n' \
      "${absolute_tool}" >&2
    exit 2
  }
done

cd "$(/usr/bin/dirname "${BASH_SOURCE[0]}")/.."

baseline_commit="2e828d7b86444770c3ef3cd40ac17f26cac6fb0e"
historical_v0_commit="59869af57f2a0b24647f3b47d7bea93839bfbefe"
admission_policy="scripts/eval/fixtures/biocortex_ab_track_b_real_run_admission_v1.json"
admission_checker="scripts/eval/check_biocortex_ab_track_b_admission_v1.py"
map_schema_v1="docs/design/fixtures/biocortex-ab-track-b-blind-map-schema-v1.json"
map_checker_v1="scripts/eval/biocortex_ab_track_b_map_bijection_v1.py"
purpose_checker="scripts/eval/check_biocortex_ab_track_b_successor_admission_map_v1_pack.py"
synthetic_fixture="scripts/eval/fixtures/biocortex_ab_track_b_successor_admission_map_v1_pack_synthetic_v0.json"
manifest="scripts/eval/fixtures/biocortex_ab_track_b_successor_admission_map_v1_pack_v0.json"
expected_result="scripts/eval/fixtures/biocortex_ab_track_b_successor_admission_map_v1_pack.expected.v0.tsv"
report="docs/reports/goal-c-u/2026-07-14-biocortex-track-b-successor-admission-map-v1-pack.md"
gate_path="scripts/check-biocortex-ab-track-b-successor-admission-map-v1-pack.sh"

packet_paths=(
  "${admission_policy}"
  "${admission_checker}"
  "${map_schema_v1}"
  "${map_checker_v1}"
  "${purpose_checker}"
  "${synthetic_fixture}"
  "${manifest}"
  "${expected_result}"
  "${report}"
  "${gate_path}"
)
packet_modes=(100644 100644 100644 100644 100644 100644 100644 100644 100644 100755)

purpose_evidence_paths=(
  "docs/design/fixtures/biocortex-ab-track-b-blind-map-schema-v0.json"
  "docs/design/fixtures/biocortex-ab-track-b-sampling-contract-digest-profile-v0.json"
  "docs/design/fixtures/biocortex-ab-track-b-sampling-receipt-schema-v0.json"
  "docs/design/fixtures/biocortex-ab-track-b-sampling-receipt-schema-v1.json"
  "scripts/eval/biocortex_ab_track_b_sampling_receipt_writer_v0.py"
  "scripts/eval/biocortex_ab_track_b_sampling_seed_derivation_v0.py"
  "scripts/eval/biocortex_ab_track_b_sampling_selection_v0.py"
  "scripts/eval/biocortex_ab_track_b_map_bijection_v0.py"
  "scripts/eval/check_biocortex_ab_track_b_admission.py"
  "scripts/eval/fixtures/biocortex_ab_track_b_artifact_dependency_graph_v0.json"
  "scripts/eval/fixtures/biocortex_ab_track_b_live_binding_ledger_v0.json"
  "scripts/eval/fixtures/biocortex_ab_track_b_real_run_admission_v0.json"
  "scripts/eval/fixtures/biocortex_ab_track_b_identity_composition_pack_synthetic_v0.json"
  "scripts/eval/fixtures/biocortex_ab_track_b_sampling_receipt_writer_pack_synthetic_v0.json"
)
prerequisite_gate_paths=(
  "scripts/check-biocortex-ab-track-b-sampling-receipt-writer-pack.sh"
)
evidence_paths=("${purpose_evidence_paths[@]}" "${prerequisite_gate_paths[@]}")
evidence_modes=(100644 100644 100644 100644 100644 100644 100644 100644
  100644 100644 100644 100644 100644 100644 100755)

declare -A evidence_sha256=(
  ["docs/design/fixtures/biocortex-ab-track-b-blind-map-schema-v0.json"]="ad40df50eec68fa192c79e6699a8d2da2a9c3925a387eaa7427f7e19f996d783"
  ["docs/design/fixtures/biocortex-ab-track-b-sampling-contract-digest-profile-v0.json"]="a8972ad5e75b30634931fee84f08226e2660413b45cf9dfea948089d61160243"
  ["docs/design/fixtures/biocortex-ab-track-b-sampling-receipt-schema-v0.json"]="9e73afee2f6366a241b155680b4f77341adeb7c4e341ab91b8d4b1499b5aacbd"
  ["docs/design/fixtures/biocortex-ab-track-b-sampling-receipt-schema-v1.json"]="e418b58246eaf183b5624c7eb12299caeea933c83a07584faa915651b3cd48d4"
  ["scripts/eval/biocortex_ab_track_b_sampling_receipt_writer_v0.py"]="a8642d2b524183e060eb2f2c16d3a4bba4bca43c8e18b8524bc14738d4f6d975"
  ["scripts/eval/biocortex_ab_track_b_sampling_seed_derivation_v0.py"]="4f51781ff707e89b4c09adffeafbdaacd75c7e1571d1a86e45d336aace888a3f"
  ["scripts/eval/biocortex_ab_track_b_sampling_selection_v0.py"]="e327faf2ad73718dc33f68fdb66a89abf0ac84fbbf8d828ff79fa0e8b75772ec"
  ["scripts/eval/biocortex_ab_track_b_map_bijection_v0.py"]="45f55cea933ee12df402fbb55d27ea7c6cd08ba8eef9d9868e4e491dd62a2cd2"
  ["scripts/eval/check_biocortex_ab_track_b_admission.py"]="b09b10243f195299dc226b5d8d2b484ec74f5eecd49bb487296c391f6f193b13"
  ["scripts/eval/fixtures/biocortex_ab_track_b_artifact_dependency_graph_v0.json"]="8f618659cb90cc311ef79aafa3fc536bacc3f428f82291998174a0e374d993af"
  ["scripts/eval/fixtures/biocortex_ab_track_b_live_binding_ledger_v0.json"]="764f063fefe0e516547f9bd1e71417242daf292d57e480ae39b73df8bcda341a"
  ["scripts/eval/fixtures/biocortex_ab_track_b_real_run_admission_v0.json"]="1508c0c990ccf9ce26fa0eb524194bb587816cc78d4546236c8d9c00dd3b306e"
  ["scripts/eval/fixtures/biocortex_ab_track_b_identity_composition_pack_synthetic_v0.json"]="094a7343543be2a9b32fc996dc3e7006bc9d02f87f8cc9bdd269ef9fb61a341a"
  ["scripts/eval/fixtures/biocortex_ab_track_b_sampling_receipt_writer_pack_synthetic_v0.json"]="79bdb87f5fdaeb72423ff12002f4cf9a0deca2e9cd9b86e820321357a0641b8a"
  ["scripts/check-biocortex-ab-track-b-sampling-receipt-writer-pack.sh"]="62006c057f8304733227402d105d8b37d033ad7253e7c4433fa58433196992d3"
)
writer_gate="scripts/check-biocortex-ab-track-b-sampling-receipt-writer-pack.sh"
self_test_expected_sha256="84ddcc09147c6a04e343d491d7adfb2d6c0bc0706dc70d831e70f15d20d2bb67"

tmp="$(/usr/bin/mktemp -d)"
cleanup() {
  /usr/bin/chmod -R u+w "${tmp}" 2>/dev/null || true
  /usr/bin/rm -rf "${tmp}"
}
trap cleanup EXIT
/usr/bin/mkdir -m 0700 "${tmp}/home" "${tmp}/child-tmp"

fail() {
  printf 'Track B successor admission/map v1 gate failed: %s\n' "$*" >&2
  exit 1
}

git_clean() {
  /usr/bin/git --no-pager --no-replace-objects -c core.fsmonitor=false \
    -c core.commitGraph=false -c core.hooksPath=/dev/null "$@"
}

verify_history_metadata() {
  local common_dir grafts_path
  [[ -z "$(git_clean for-each-ref --format='%(refname)' refs/replace)" ]] \
    || fail "Git replace refs are present"
  [[ "$(git_clean rev-parse --is-shallow-repository)" == false ]] \
    || fail "shallow repository history is not admissible"
  common_dir="$(git_clean rev-parse --path-format=absolute --git-common-dir)" \
    || fail "cannot resolve absolute Git common directory"
  [[ -d "${common_dir}" && ! -L "${common_dir}" ]] \
    || fail "Git common directory is missing or is a symlink"
  grafts_path="${common_dir}/info/grafts"
  [[ ! -e "${grafts_path}" && ! -L "${grafts_path}" ]] \
    || fail "legacy Git graft metadata is present"
}

reject_symlink_components() {
  local path="$1" component cursor=""
  local -a components
  IFS=/ read -r -a components <<<"${path}"
  for component in "${components[@]}"; do
    if [[ -n "${cursor}" ]]; then cursor="${cursor}/${component}"; else cursor="${component}"; fi
    [[ ! -L "${cursor}" ]] || fail "protected path contains a symlink: ${path}"
  done
}

verify_regular_unaliased() {
  local path="$1"
  reject_symlink_components "${path}"
  [[ -f "${path}" && "$(/usr/bin/stat -c '%F' -- "${path}")" == "regular file" ]] \
    || fail "protected path is not a regular file: ${path}"
  [[ "$(/usr/bin/stat -c '%h' -- "${path}")" == 1 ]] \
    || fail "protected path has hard-link aliases: ${path}"
}

verify_packet_identity() {
  local index path expected_mode
  local index_mode index_object index_stage indexed
  local source_mode source_type source_object source_indexed
  local head_mode head_type head_object head_indexed
  [[ "${#packet_paths[@]}" == "${#packet_modes[@]}" ]] \
    || fail "packet path/mode catalog length drift"
  for index in "${!packet_paths[@]}"; do
    path="${packet_paths[$index]}"
    expected_mode="${packet_modes[$index]}"
    verify_regular_unaliased "${path}"
    read -r index_mode index_object index_stage indexed \
      < <(git_clean ls-files --stage -- "${path}")
    read -r source_mode source_type source_object source_indexed \
      < <(git_clean ls-tree "${source_commit}" -- "${path}")
    read -r head_mode head_type head_object head_indexed \
      < <(git_clean ls-tree "${head_oid}" -- "${path}")
    [[ "${index_mode}" == "${expected_mode}" \
      && "${source_mode}" == "${expected_mode}" \
      && "${head_mode}" == "${expected_mode}" \
      && "${source_type}" == blob && "${head_type}" == blob \
      && "${index_stage}" == 0 && "${indexed}" == "${path}" \
      && "${source_indexed}" == "${path}" && "${head_indexed}" == "${path}" \
      && "${index_object}" == "${source_object}" \
      && "${head_object}" == "${source_object}" ]] \
      || fail "source/HEAD/index Git identity drift: ${path}"
    [[ "$(git_clean ls-files -v -- "${path}")" == "H ${path}" ]] \
      || fail "nondefault Git index flag: ${path}"
    /usr/bin/cmp -s "${path}" <(git_clean cat-file blob "${source_object}") \
      || fail "worktree/source-commit byte drift: ${path}"
  done
}

verify_evidence_identity() {
  local index path expected_mode index_mode index_object index_stage indexed
  local head_mode head_type head_object head_indexed
  [[ "${#evidence_paths[@]}" == "${#evidence_modes[@]}" ]] \
    || fail "evidence path/mode catalog length drift"
  for index in "${!evidence_paths[@]}"; do
    path="${evidence_paths[$index]}"
    expected_mode="${evidence_modes[$index]}"
    verify_regular_unaliased "${path}"
    read -r index_mode index_object index_stage indexed \
      < <(git_clean ls-files --stage -- "${path}")
    read -r head_mode head_type head_object head_indexed \
      < <(git_clean ls-tree "${head_oid}" -- "${path}")
    [[ "${index_mode}" == "${expected_mode}" \
      && "${head_mode}" == "${expected_mode}" && "${head_type}" == blob \
      && "${index_stage}" == 0 && "${indexed}" == "${path}" \
      && "${head_indexed}" == "${path}" && "${index_object}" == "${head_object}" ]] \
      || fail "evidence HEAD/index Git identity or mode drift: ${path}"
    [[ "$(git_clean ls-files -v -- "${path}")" == "H ${path}" ]] \
      || fail "nondefault evidence Git index flag: ${path}"
    /usr/bin/cmp -s "${path}" <(git_clean cat-file blob "${head_object}") \
      || fail "worktree/HEAD evidence byte drift: ${path}"
  done
}

verify_evidence_hashes() {
  local path
  for path in "${evidence_paths[@]}"; do
    [[ "$(/usr/bin/sha256sum "${path}" | /usr/bin/awk '{print $1}')" == "${evidence_sha256[${path}]}" ]] \
      || fail "immutable evidence hash drift: ${path}"
  done
}

verify_descendant_integration_shape() {
  local merge_oid other_parent parent found=0
  local -a merge_candidates parents
  [[ "${head_oid}" != "${source_commit}" ]] || return 0
  mapfile -t merge_candidates < <(
    git_clean rev-list --ancestry-path --merges "${source_commit}..${head_oid}"
  )
  for merge_oid in "${merge_candidates[@]}"; do
    parents=()
    mapfile -t parents < <(
      git_clean cat-file commit "${merge_oid}" | /usr/bin/awk '
        BEGIN { in_headers = 1 }
        in_headers && $0 == "" { in_headers = 0 }
        in_headers && $1 == "parent" { print $2 }
      '
    )
    [[ "${#parents[@]}" == 2 ]] || continue
    if [[ "${parents[0]}" == "${source_commit}" ]]; then
      other_parent="${parents[1]}"
    elif [[ "${parents[1]}" == "${source_commit}" ]]; then
      other_parent="${parents[0]}"
    else
      continue
    fi
    git_clean merge-base --is-ancestor "${baseline_commit}" "${other_parent}" || continue
    if git_clean merge-base --is-ancestor "${source_commit}" "${other_parent}"; then continue; fi
    found=1
    break
  done
  [[ "${found}" == 1 ]] \
    || fail "descendant HEAD lacks an ordinary two-parent merge of the exact source commit"
}

snapshot_blob() {
  local path="$1" target="${tmp}/snapshot/${path}"
  /usr/bin/mkdir -p "$(/usr/bin/dirname "${target}")"
  git_clean cat-file blob "${head_oid}:${path}" >"${target}" \
    || fail "cannot materialize immutable HEAD input: ${path}"
}

run_purpose_checker() {
  local output="$1" error="$2" hash_seed="$3"
  (
    cd "${tmp}/snapshot"
    HOME="${tmp}/home" TMPDIR="${tmp}/child-tmp" PYTHONHASHSEED="${hash_seed}" \
      /usr/bin/python3 -S -P "${tmp}/snapshot/${purpose_checker}" --root "${tmp}/snapshot"
  ) >"${output}" 2>"${error}"
}

run_purpose_self_test() {
  local output="$1" error="$2" hash_seed="$3"
  (
    cd "${tmp}/snapshot"
    HOME="${tmp}/home" TMPDIR="${tmp}/child-tmp" PYTHONHASHSEED="${hash_seed}" \
      /usr/bin/python3 -S -P "${tmp}/snapshot/${purpose_checker}" \
        --root "${tmp}/snapshot" --self-test
  ) >"${output}" 2>"${error}"
}

run_required_gate() {
  local path="$1" expected_marker="$2" label="$3"
  if ! "${path}" >"${tmp}/${label}.out" 2>"${tmp}/${label}.err"; then
    /usr/bin/cat "${tmp}/${label}.err" >&2
    fail "required ${label} gate failed"
  fi
  [[ ! -s "${tmp}/${label}.err" ]] || fail "required ${label} gate emitted stderr"
  [[ "$(/usr/bin/head -n 1 "${tmp}/${label}.out")" == "${expected_marker}" ]] \
    || fail "required ${label} gate marker drift"
}

run_historical_v0_admission_replay() {
  local historical_root="${tmp}/historical-v0"
  /usr/bin/mkdir -m 0700 "${historical_root}"
  git_clean archive --format=tar "${historical_v0_commit}" \
    | /usr/bin/tar -xf - -C "${historical_root}" \
    || fail "cannot materialize frozen v0 replay commit"
  (
    cd "${historical_root}"
    HOME="${tmp}/home" TMPDIR="${tmp}/child-tmp" PYTHONHASHSEED=0 \
      /usr/bin/python3 -S -P \
        "${historical_root}/scripts/eval/check_biocortex_ab_track_b_admission.py" \
        --root "${historical_root}"
  ) >"${tmp}/historical-v0.out" 2>"${tmp}/historical-v0.err" \
    || { /usr/bin/cat "${tmp}/historical-v0.err" >&2; fail "historical v0 admission replay failed"; }
  [[ ! -s "${tmp}/historical-v0.err" ]] \
    || fail "historical v0 admission replay emitted stderr"
  /usr/bin/cmp -s \
    "${tmp}/historical-v0.out" \
    "${historical_root}/scripts/eval/fixtures/biocortex_ab_track_b_real_run_admission.expected.v0.tsv" \
    || fail "historical v0 admission replay output drift"
}

verify_history_metadata
head_oid="$(git_clean rev-parse --verify 'HEAD^{commit}')" || fail "cannot resolve HEAD"
git_clean cat-file -e "${baseline_commit}^{commit}" || fail "cannot resolve frozen baseline"
git_clean cat-file -e "${historical_v0_commit}^{commit}" \
  || fail "cannot resolve frozen v0 replay commit"
git_clean merge-base --is-ancestor "${baseline_commit}" "${head_oid}" \
  || fail "frozen baseline is not an ancestor of HEAD"
[[ -z "$(git_clean status --porcelain=v1 --untracked-files=all --ignore-submodules=none)" ]] \
  || fail "worktree must be clean"
git_clean ls-files -v | /usr/bin/awk 'substr($0, 1, 1) != "H" {exit 1}' \
  || fail "nondefault Git index flags are present"

source_candidates=()
mapfile -t source_candidates < <(
  git_clean log "${head_oid}" --diff-filter=A --format='%H' -- "${manifest}"
)
[[ "${#source_candidates[@]}" == 1 ]] \
  || fail "successor admission/map manifest must have exactly one add commit"
source_commit="${source_candidates[0]}"
raw_parent_headers="$(
  git_clean cat-file commit "${source_commit}" | /usr/bin/awk '
    BEGIN { in_headers = 1 }
    in_headers && $0 == "" { in_headers = 0 }
    in_headers && $1 == "parent" { print $2 }
  '
)"
[[ "${raw_parent_headers}" == "${baseline_commit}" ]] \
  || fail "raw source commit must have exactly the frozen baseline as parent"
git_clean merge-base --is-ancestor "${source_commit}" "${head_oid}" \
  || fail "source commit is not an ancestor of HEAD"
verify_descendant_integration_shape

{
  for path in "${packet_paths[@]}"; do printf 'A\t%s\n' "${path}"; done
} | /usr/bin/sort >"${tmp}/expected-source-delta"
git_clean diff-tree --no-commit-id --no-renames --name-status -r "${source_commit}" \
  | /usr/bin/sort >"${tmp}/actual-source-delta"
/usr/bin/cmp -s "${tmp}/expected-source-delta" "${tmp}/actual-source-delta" \
  || fail "source commit is not the exact ten-path all-add packet"

verify_packet_identity
verify_evidence_identity
verify_evidence_hashes
run_required_gate "${writer_gate}" \
  "VALID_INTEGRATED_BIOCORTEX_AB_TRACK_B_SAMPLING_RECEIPT_WRITER_PACK" \
  "sampling-receipt-writer-pack"
run_historical_v0_admission_replay

/usr/bin/mkdir -m 0700 "${tmp}/snapshot"
for path in "${packet_paths[@]}"; do snapshot_blob "${path}"; done
for path in "${evidence_paths[@]}"; do snapshot_blob "${path}"; done
/usr/bin/chmod -R a-w "${tmp}/snapshot"

run_purpose_checker "${tmp}/normal-zero.out" "${tmp}/normal-zero.err" 0 \
  || { /usr/bin/cat "${tmp}/normal-zero.err" >&2; fail "normal checker failed"; }
run_purpose_checker "${tmp}/normal-alt.out" "${tmp}/normal-alt.err" 314159 \
  || { /usr/bin/cat "${tmp}/normal-alt.err" >&2; fail "alternate-hash checker failed"; }
[[ ! -s "${tmp}/normal-zero.err" && ! -s "${tmp}/normal-alt.err" ]] \
  || fail "normal checker emitted stderr"
/usr/bin/cmp -s "${tmp}/normal-zero.out" "${tmp}/normal-alt.out" \
  || fail "normal output depends on PYTHONHASHSEED"
/usr/bin/cmp -s "${tmp}/normal-zero.out" "${tmp}/snapshot/${expected_result}" \
  || fail "fixed successor admission/map result drift"

run_purpose_self_test "${tmp}/self-zero.out" "${tmp}/self-zero.err" 0 \
  || { /usr/bin/cat "${tmp}/self-zero.err" >&2; fail "self-test failed"; }
run_purpose_self_test "${tmp}/self-alt.out" "${tmp}/self-alt.err" 314159 \
  || { /usr/bin/cat "${tmp}/self-alt.err" >&2; fail "alternate-hash self-test failed"; }
[[ ! -s "${tmp}/self-zero.err" && ! -s "${tmp}/self-alt.err" ]] \
  || fail "self-test emitted stderr"
/usr/bin/cmp -s "${tmp}/self-zero.out" "${tmp}/self-alt.out" \
  || fail "self-test depends on PYTHONHASHSEED"
[[ "$(/usr/bin/head -n 1 "${tmp}/self-zero.out" | /usr/bin/awk -F '\t' '{print $1}')" == "SELF_TEST_OK" ]] \
  || fail "self-test marker drift"
[[ "$(/usr/bin/sha256sum "${tmp}/self-zero.out" | /usr/bin/awk '{print $1}')" == "${self_test_expected_sha256}" ]] \
  || fail "self-test output hash drift"

[[ "$(git_clean rev-parse --verify 'HEAD^{commit}')" == "${head_oid}" ]] \
  || fail "HEAD changed while gate was running"
verify_history_metadata
[[ -z "$(git_clean status --porcelain=v1 --untracked-files=all --ignore-submodules=none)" ]] \
  || fail "worktree changed while gate was running"
git_clean ls-files -v | /usr/bin/awk 'substr($0, 1, 1) != "H" {exit 1}' \
  || fail "nondefault Git index flags appeared while gate was running"
verify_packet_identity
verify_evidence_identity
verify_evidence_hashes

if [[ "${head_oid}" == "${source_commit}" ]]; then
  marker="BOUND_TO_HEAD_BIOCORTEX_AB_TRACK_B_SUCCESSOR_ADMISSION_MAP_V1_PACK"
  integration_status="BOUND_TO_HEAD"
else
  marker="VALID_INTEGRATED_BIOCORTEX_AB_TRACK_B_SUCCESSOR_ADMISSION_MAP_V1_PACK"
  integration_status="VALID_INTEGRATED"
fi
printf '%s\n' "${marker}"
printf 'integration_status=%s\n' "${integration_status}"
printf 'admission_status=SUCCESSOR_V1_SOURCE_COMPATIBILITY_ONLY_NOT_LIVE_ADMISSION\n'
printf 'condition_output_status=NOT_AUTHORIZED\n'
printf 'head=%s\n' "${head_oid}"
printf 'source_commit=%s\n' "${source_commit}"
printf 'baseline_commit=%s\n' "${baseline_commit}"
printf 'sampling_receipt_writer_gate_status=VALID_INTEGRATED\n'
printf 'historical_v0_admission_replay_status=PASS_VALIDATION_ONLY\n'
printf 'expected_result_sha256=%s\n' \
  "$(/usr/bin/sha256sum "${tmp}/snapshot/${expected_result}" | /usr/bin/awk '{print $1}')"
printf 'self_test_sha256=%s\n' \
  "$(/usr/bin/sha256sum "${tmp}/self-zero.out" | /usr/bin/awk '{print $1}')"
while IFS= read -r row; do printf '%s\n' "${row}"; done <"${tmp}/normal-zero.out"
