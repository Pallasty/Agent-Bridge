#!/usr/bin/env -S -i /usr/bin/bash
# Source-bound, non-admitting gate for the Track B exact-artifact dependency graph.
set -euo pipefail

while IFS= read -r imported_function; do
  builtin unset -f "${imported_function}"
done < <(builtin compgen -A function)

PATH=/usr/bin:/bin
export PATH LC_ALL=C
export PYTHONDONTWRITEBYTECODE=1
export PYTHONNOUSERSITE=1
export PYTHONSAFEPATH=1
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

for absolute_tool in /usr/bin/awk /usr/bin/bash /usr/bin/chmod /usr/bin/cmp \
  /usr/bin/dirname /usr/bin/env /usr/bin/git /usr/bin/mkdir /usr/bin/mktemp \
  /usr/bin/python3 /usr/bin/rm /usr/bin/sha256sum /usr/bin/sort \
  /usr/bin/stat /usr/bin/tail; do
  [[ -x "${absolute_tool}" ]] || {
    printf 'Track B artifact dependency graph gate missing trusted tool: %s\n' \
      "${absolute_tool}" >&2
    exit 2
  }
done

cd "$(/usr/bin/dirname "${BASH_SOURCE[0]}")/.."

baseline_commit="3840fc214118f692d37a54e6abdd46ab192080ad"
graph="scripts/eval/fixtures/biocortex_ab_track_b_artifact_dependency_graph_v0.json"
expected_receipt="scripts/eval/fixtures/biocortex_ab_track_b_artifact_dependency_graph.expected.v0.tsv"
checker="scripts/eval/check_biocortex_ab_track_b_artifact_dependency_graph.py"
report="docs/reports/goal-c-u/2026-07-14-biocortex-track-b-artifact-dependency-graph.md"
gate_path="scripts/check-biocortex-ab-track-b-artifact-dependency-graph.sh"

packet_paths=(
  "${report}"
  "${gate_path}"
  "${checker}"
  "${expected_receipt}"
  "${graph}"
)
packet_modes=(100644 100755 100644 100644 100644)

evidence_paths=(
  "crates/bridge/src/memory_truth.rs"
  "crates/bridge/src/memory_truth_adapter.rs"
  "crates/store/examples/memory_reference_admission_fixture.rs"
  "scripts/eval/check_biocortex_ab_track_b_admission.py"
  "scripts/eval/check_biocortex_ab_track_b_live_binding_ledger.py"
  "scripts/eval/fixtures/biocortex_ab_track_b_live_binding_ledger_v0.json"
  "scripts/eval/fixtures/biocortex_ab_track_b_real_run_admission_v0.json"
  "scripts/eval/fixtures/portfolio_continuity_successor_v3_answer_contract.json"
  "scripts/eval/portfolio_continuity_successor_v3_trial.py"
)
evidence_modes=(100644 100644 100644 100644 100644 100644 100644 100644 100644)

tmp="$(/usr/bin/mktemp -d)"
cleanup() {
  /usr/bin/chmod -R u+w "${tmp}" 2>/dev/null || true
  /usr/bin/rm -rf "${tmp}"
}
trap cleanup EXIT
/usr/bin/mkdir -m 0700 "${tmp}/home" "${tmp}/child-tmp"

fail() {
  printf 'Track B artifact dependency graph gate failed: %s\n' "$*" >&2
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
  [[ -d "${common_dir}" ]] || fail "Git common directory is not a directory"
  grafts_path="${common_dir}/info/grafts"
  [[ ! -e "${grafts_path}" && ! -L "${grafts_path}" ]] \
    || fail "legacy Git graft metadata is present"
}

reject_symlink_components() {
  local path="$1" component cursor=""
  local -a components
  IFS=/ read -r -a components <<<"${path}"
  for component in "${components[@]}"; do
    if [[ -n "${cursor}" ]]; then
      cursor="${cursor}/${component}"
    else
      cursor="${component}"
    fi
    [[ ! -L "${cursor}" ]] \
      || fail "protected path contains a symlink: ${path}"
  done
}

verify_regular_unaliased() {
  local path="$1"
  reject_symlink_components "${path}"
  [[ -f "${path}" \
    && "$(/usr/bin/stat -c '%F' -- "${path}")" == "regular file" ]] \
    || fail "protected path is not a regular file: ${path}"
  [[ "$(/usr/bin/stat -c '%h' -- "${path}")" == 1 ]] \
    || fail "protected path has hard-link aliases: ${path}"
}

verify_packet_identity() {
  local index path expected_mode
  local index_mode index_object index_stage indexed
  local source_mode source_type source_object source_indexed
  local head_mode head_type head_object head_indexed
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
      && "${index_stage}" == 0 \
      && "${indexed}" == "${path}" \
      && "${source_indexed}" == "${path}" \
      && "${head_indexed}" == "${path}" \
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
  local index path expected_mode
  local index_mode index_object index_stage indexed
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
      && "${head_mode}" == "${expected_mode}" \
      && "${head_type}" == blob && "${index_stage}" == 0 \
      && "${indexed}" == "${path}" \
      && "${head_indexed}" == "${path}" \
      && "${index_object}" == "${head_object}" ]] \
      || fail "evidence HEAD/index Git identity or mode drift: ${path}"
    [[ "$(git_clean ls-files -v -- "${path}")" == "H ${path}" ]] \
      || fail "nondefault evidence Git index flag: ${path}"
    /usr/bin/cmp -s "${path}" <(git_clean cat-file blob "${head_object}") \
      || fail "worktree/HEAD evidence byte drift: ${path}"
  done
}

run_checker() {
  local output="$1" error="$2"
  HOME="${tmp}/home" TMPDIR="${tmp}/child-tmp" \
    /usr/bin/python3 "${tmp}/snapshot/${checker}" \
      --root "${tmp}/snapshot" >"${output}" 2>"${error}"
}

verify_history_metadata
head_oid="$(git_clean rev-parse --verify 'HEAD^{commit}')" \
  || fail "cannot resolve HEAD"
git_clean merge-base --is-ancestor "${baseline_commit}" "${head_oid}" \
  || fail "frozen ledger commit is not an ancestor of HEAD"
[[ -z "$(git_clean status --porcelain=v1 --untracked-files=all \
  --ignore-submodules=none)" ]] || fail "worktree must be clean"
git_clean ls-files -v | /usr/bin/awk 'substr($0, 1, 1) != "H" {exit 1}' \
  || fail "nondefault Git index flags are present"

source_commit="$(
  git_clean log "${head_oid}" --diff-filter=A --format='%H' -- "${graph}" \
    | /usr/bin/tail -n 1
)"
[[ -n "${source_commit}" ]] || fail "cannot locate graph source commit"
raw_parent_headers="$(
  git_clean cat-file commit "${source_commit}" \
    | /usr/bin/awk '
        BEGIN { in_headers = 1 }
        in_headers && $0 == "" { in_headers = 0 }
        in_headers && $1 == "parent" { print $2 }
      '
)"
[[ "${raw_parent_headers}" == "${baseline_commit}" ]] \
  || fail "raw graph source commit must have exactly the frozen ledger commit as parent"
git_clean merge-base --is-ancestor "${source_commit}" "${head_oid}" \
  || fail "graph source commit is not an ancestor of HEAD"

{
  for path in "${packet_paths[@]}"; do
    printf '%s\n' "${path}"
  done
} | /usr/bin/sort >"${tmp}/expected-paths"
git_clean diff-tree --no-commit-id --name-only -r "${source_commit}" \
  | /usr/bin/sort >"${tmp}/actual-paths"
/usr/bin/cmp -s "${tmp}/expected-paths" "${tmp}/actual-paths" \
  || fail "source commit changed paths outside the exact graph packet"

verify_packet_identity
verify_evidence_identity

snapshot_paths=("${checker}" "${expected_receipt}" "${graph}")
/usr/bin/mkdir -m 0700 "${tmp}/snapshot"
for path in "${snapshot_paths[@]}"; do
  /usr/bin/mkdir -p "${tmp}/snapshot/$(/usr/bin/dirname "${path}")"
  git_clean cat-file blob "${head_oid}:${path}" >"${tmp}/snapshot/${path}" \
    || fail "cannot materialize immutable HEAD packet input: ${path}"
done
for path in "${evidence_paths[@]}"; do
  /usr/bin/mkdir -p "${tmp}/snapshot/$(/usr/bin/dirname "${path}")"
  git_clean cat-file blob "${head_oid}:${path}" >"${tmp}/snapshot/${path}" \
    || fail "cannot materialize immutable HEAD evidence: ${path}"
done

run_checker "${tmp}/run-one.out" "${tmp}/run-one.err"
run_checker "${tmp}/run-two.out" "${tmp}/run-two.err"
[[ ! -s "${tmp}/run-one.err" && ! -s "${tmp}/run-two.err" ]] \
  || fail "valid checker emitted stderr"
/usr/bin/cmp -s "${tmp}/run-one.out" "${tmp}/run-two.out" \
  || fail "graph checker is nondeterministic"
/usr/bin/cmp -s "${tmp}/run-one.out" \
  "${tmp}/snapshot/${expected_receipt}" \
  || fail "fixed graph receipt drift"

HOME="${tmp}/home" TMPDIR="${tmp}/child-tmp" \
  /usr/bin/python3 "${tmp}/snapshot/${checker}" \
    --root "${tmp}/snapshot" --self-test \
    >"${tmp}/self-test.out" 2>"${tmp}/self-test.err"
[[ ! -s "${tmp}/self-test.err" ]] || fail "graph self-test emitted stderr"
[[ "$(<"${tmp}/self-test.out")" == \
  $'SELF_TEST_OK\tgraph_mutations_rejected=44\tsource_mutations_rejected=4\ttotal_mutations_rejected=48' ]] \
  || fail "adversarial self-test result drift"

[[ "$(git_clean rev-parse --verify 'HEAD^{commit}')" == "${head_oid}" ]] \
  || fail "HEAD changed while the gate was running"
verify_history_metadata
[[ -z "$(git_clean status --porcelain=v1 --untracked-files=all \
  --ignore-submodules=none)" ]] || fail "worktree changed while the gate was running"
git_clean ls-files -v | /usr/bin/awk 'substr($0, 1, 1) != "H" {exit 1}' \
  || fail "nondefault Git index flags appeared while the gate was running"
verify_packet_identity
verify_evidence_identity

if [[ "${head_oid}" == "${source_commit}" ]]; then
  printf 'BOUND_TO_HEAD_BIOCORTEX_AB_TRACK_B_ARTIFACT_DEPENDENCY_GRAPH\n'
else
  printf 'VALID_INTEGRATED_BIOCORTEX_AB_TRACK_B_ARTIFACT_DEPENDENCY_GRAPH\n'
fi
printf 'head=%s\n' "${head_oid}"
printf 'source_commit=%s\n' "${source_commit}"
printf 'baseline_commit=%s\n' "${baseline_commit}"
printf 'expected_receipt_sha256=%s\n' \
  "$(/usr/bin/sha256sum "${tmp}/snapshot/${expected_receipt}" \
    | /usr/bin/awk '{print $1}')"
printf 'adversarial_mutations_rejected=48\n'
while IFS= read -r row; do
  printf '%s\n' "${row}"
done <"${tmp}/run-one.out"
