#!/usr/bin/env -S -i /usr/bin/bash
# Source-bound, non-admitting gate for the Track B identity-composition pack.
set -euo pipefail

while IFS= read -r imported_function; do
  builtin unset -f "${imported_function}"
done < <(builtin compgen -A function)

PATH=/usr/bin:/bin
export PATH LC_ALL=C TZ=UTC
export PYTHONDONTWRITEBYTECODE=1
export PYTHONHASHSEED=0
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
  /usr/bin/sha256sum /usr/bin/sort /usr/bin/stat; do
  [[ -x "${absolute_tool}" ]] || {
    printf 'Track B identity-composition gate missing trusted tool: %s\n' \
      "${absolute_tool}" >&2
    exit 2
  }
done

cd "$(/usr/bin/dirname "${BASH_SOURCE[0]}")/.."

baseline_commit="c8e070de0de2abca764c5060b5fba91a64b6f189"
review_schema="docs/design/fixtures/biocortex-ab-track-b-review-schema-v0.json"
truth_manifest_schema="docs/design/fixtures/biocortex-ab-track-b-truth-manifest-schema-v0.json"
report="docs/reports/goal-c-u/2026-07-14-biocortex-track-b-identity-composition-pack.md"
gate_path="scripts/check-biocortex-ab-track-b-identity-composition-pack.sh"
map_bijection_checker="scripts/eval/biocortex_ab_track_b_map_bijection_v0.py"
purpose_checker="scripts/eval/check_biocortex_ab_track_b_identity_composition_pack.py"
expected_receipt="scripts/eval/fixtures/biocortex_ab_track_b_identity_composition_pack.expected.v0.tsv"
synthetic_fixture="scripts/eval/fixtures/biocortex_ab_track_b_identity_composition_pack_synthetic_v0.json"
manifest="scripts/eval/fixtures/biocortex_ab_track_b_identity_composition_pack_v0.json"

packet_paths=(
  "${review_schema}"
  "${truth_manifest_schema}"
  "${report}"
  "${gate_path}"
  "${map_bijection_checker}"
  "${purpose_checker}"
  "${expected_receipt}"
  "${synthetic_fixture}"
  "${manifest}"
)
packet_modes=(100644 100644 100644 100755 100644 100644 100644 100644 100644)

# These 16 paths are exact public inputs to the purpose checker.  The four
# following data files are prerequisite-gate inputs, while the final two paths
# are the prerequisite gates themselves.  All 22 are Git/file identity checked;
# the two executable gates also have frozen SHA-256 values below.
purpose_evidence_paths=(
  "crates/bridge/src/memory_truth.rs"
  "crates/bridge/src/memory_truth_adapter.rs"
  "docs/design/MEMORY_TEMPORAL_EVIDENCE_SUBSTRATE_S2_2026_07_14.md"
  "docs/design/fixtures/biocortex-ab-track-b-blind-map-schema-v0.json"
  "docs/design/fixtures/biocortex-ab-track-b-review-command-schema-v0.json"
  "docs/design/fixtures/biocortex-ab-track-b-sampling-receipt-schema-v0.json"
  "docs/design/fixtures/biocortex-ab-track-b-truth-referent-schema-v0.json"
  "scripts/eval/check_biocortex_ab_track_b_foundational_schema_pack.py"
  "scripts/eval/fixtures/biocortex_ab_track_b_artifact_dependency_graph_v0.json"
  "scripts/eval/fixtures/biocortex_ab_track_b_foundational_schema_pack_v0.json"
  "scripts/eval/fixtures/biocortex_ab_track_b_live_binding_ledger_v0.json"
  "scripts/eval/fixtures/biocortex_ab_track_b_real_run_admission_v0.json"
  "scripts/eval/fixtures/memory_temporal_evidence_adapter_s3_contract_v0.json"
  "scripts/eval/fixtures/memory_temporal_evidence_substrate_s2_contract_v0.json"
  "scripts/eval/fixtures/portfolio_continuity_successor_v3_answer_contract.json"
  "scripts/eval/portfolio_continuity_successor_v3_trial.py"
)
prerequisite_evidence_paths=(
  "docs/reports/goal-c-u/2026-07-14-biocortex-ab-track-b-evidence-substrate-s2.md"
  "scripts/eval/check_biocortex_ab_track_b_admission.py"
  "scripts/eval/fixtures/biocortex_ab_track_b_foundational_schema_pack.expected.v0.tsv"
  "scripts/eval/fixtures/biocortex_ab_track_b_foundational_schema_pack_synthetic_v0.json"
  "scripts/check-biocortex-ab-track-b-artifact-dependency-graph.sh"
  "scripts/check-biocortex-ab-track-b-foundational-schema-pack.sh"
)
evidence_paths=(
  "${purpose_evidence_paths[@]}"
  "${prerequisite_evidence_paths[@]}"
)
evidence_modes=(
  100644 100644 100644 100644 100644 100644 100644
  100644 100644 100644 100644 100644 100644 100644
  100644 100644 100644 100644 100644 100644 100755
  100755
)

graph_gate="scripts/check-biocortex-ab-track-b-artifact-dependency-graph.sh"
foundational_gate="scripts/check-biocortex-ab-track-b-foundational-schema-pack.sh"
graph_gate_sha256="20e0b36d583ad729b992a423834dbb7c05245c3689a5887e53fb04103222b001"
foundational_gate_sha256="17e9c53917139b6555e1546ab8ae675f85075fc09141d5c0033c1734ae6242e5"

tmp="$(/usr/bin/mktemp -d)"
cleanup() {
  /usr/bin/chmod -R u+w "${tmp}" 2>/dev/null || true
  /usr/bin/rm -rf "${tmp}"
}
trap cleanup EXIT
/usr/bin/mkdir -m 0700 "${tmp}/home" "${tmp}/child-tmp"

fail() {
  printf 'Track B identity-composition gate failed: %s\n' "$*" >&2
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

verify_prerequisite_gate_hashes() {
  [[ "$(/usr/bin/sha256sum "${graph_gate}" | /usr/bin/awk '{print $1}')" \
    == "${graph_gate_sha256}" ]] \
    || fail "artifact-dependency graph gate hash drift"
  [[ "$(/usr/bin/sha256sum "${foundational_gate}" | /usr/bin/awk '{print $1}')" \
    == "${foundational_gate_sha256}" ]] \
    || fail "foundational-schema gate hash drift"
}

snapshot_blob() {
  local path="$1" target="${tmp}/snapshot/${path}"
  /usr/bin/mkdir -p "$(/usr/bin/dirname "${target}")"
  git_clean cat-file blob "${head_oid}:${path}" >"${target}" \
    || fail "cannot materialize immutable HEAD input: ${path}"
}

run_purpose_checker() {
  local output="$1" error="$2"
  HOME="${tmp}/home" TMPDIR="${tmp}/child-tmp" \
    /usr/bin/python3 "${tmp}/snapshot/${purpose_checker}" \
      --root "${tmp}/snapshot" >"${output}" 2>"${error}"
}

run_purpose_self_test() {
  local output="$1" error="$2"
  HOME="${tmp}/home" TMPDIR="${tmp}/child-tmp" \
    /usr/bin/python3 "${tmp}/snapshot/${purpose_checker}" \
      --root "${tmp}/snapshot" --self-test >"${output}" 2>"${error}"
}

run_required_gate() {
  local path="$1" expected_marker="$2" label="$3"
  if ! "${path}" >"${tmp}/${label}.out" 2>"${tmp}/${label}.err"; then
    /usr/bin/cat "${tmp}/${label}.err" >&2
    fail "required ${label} gate failed"
  fi
  [[ ! -s "${tmp}/${label}.err" ]] \
    || fail "required ${label} gate emitted stderr"
  [[ "$(/usr/bin/head -n 1 "${tmp}/${label}.out")" == "${expected_marker}" ]] \
    || fail "required ${label} gate marker drift"
}

verify_history_metadata
head_oid="$(git_clean rev-parse --verify 'HEAD^{commit}')" \
  || fail "cannot resolve HEAD"
git_clean cat-file -e "${baseline_commit}^{commit}" \
  || fail "cannot resolve frozen integrated baseline"
git_clean merge-base --is-ancestor "${baseline_commit}" "${head_oid}" \
  || fail "frozen integrated baseline is not an ancestor of HEAD"
[[ -z "$(git_clean status --porcelain=v1 --untracked-files=all \
  --ignore-submodules=none)" ]] || fail "worktree must be clean"
git_clean ls-files -v | /usr/bin/awk 'substr($0, 1, 1) != "H" {exit 1}' \
  || fail "nondefault Git index flags are present"

source_candidates=()
mapfile -t source_candidates < <(
  git_clean log "${head_oid}" --diff-filter=A --format='%H' -- "${manifest}"
)
[[ "${#source_candidates[@]}" == 1 ]] \
  || fail "identity-composition manifest must have exactly one add commit"
source_commit="${source_candidates[0]}"

raw_parent_headers="$(
  git_clean cat-file commit "${source_commit}" \
    | /usr/bin/awk '
        BEGIN { in_headers = 1 }
        in_headers && $0 == "" { in_headers = 0 }
        in_headers && $1 == "parent" { print $2 }
      '
)"
[[ "${raw_parent_headers}" == "${baseline_commit}" ]] \
  || fail "raw identity-composition source commit must have exactly the frozen integrated baseline as parent"
git_clean merge-base --is-ancestor "${source_commit}" "${head_oid}" \
  || fail "identity-composition source commit is not an ancestor of HEAD"

{
  for path in "${packet_paths[@]}"; do
    printf 'A\t%s\n' "${path}"
  done
} | /usr/bin/sort >"${tmp}/expected-source-delta"
git_clean diff-tree --no-commit-id --no-renames --name-status \
  -r "${source_commit}" | /usr/bin/sort >"${tmp}/actual-source-delta"
/usr/bin/cmp -s "${tmp}/expected-source-delta" "${tmp}/actual-source-delta" \
  || fail "source commit is not the exact nine-path all-add identity-composition packet"

verify_packet_identity
verify_evidence_identity
verify_prerequisite_gate_hashes

run_required_gate "${graph_gate}" \
  "VALID_INTEGRATED_BIOCORTEX_AB_TRACK_B_ARTIFACT_DEPENDENCY_GRAPH" \
  "artifact-dependency-graph"
run_required_gate "${foundational_gate}" \
  "VALID_INTEGRATED_BIOCORTEX_AB_TRACK_B_FOUNDATIONAL_SCHEMA_PACK" \
  "foundational-schema-pack"

snapshot_paths=(
  "${purpose_checker}"
  "${expected_receipt}"
  "${manifest}"
  "${synthetic_fixture}"
  "${review_schema}"
  "${truth_manifest_schema}"
  "${map_bijection_checker}"
)
/usr/bin/mkdir -m 0700 "${tmp}/snapshot"
for path in "${snapshot_paths[@]}"; do
  snapshot_blob "${path}"
done
for path in "${evidence_paths[@]}"; do
  snapshot_blob "${path}"
done

if ! run_purpose_checker "${tmp}/run-one.out" "${tmp}/run-one.err"; then
  /usr/bin/cat "${tmp}/run-one.err" >&2
  fail "valid purpose checker run failed"
fi
if ! run_purpose_checker "${tmp}/run-two.out" "${tmp}/run-two.err"; then
  /usr/bin/cat "${tmp}/run-two.err" >&2
  fail "second valid purpose checker run failed"
fi
[[ ! -s "${tmp}/run-one.err" && ! -s "${tmp}/run-two.err" ]] \
  || fail "valid purpose checker emitted stderr"
/usr/bin/cmp -s "${tmp}/run-one.out" "${tmp}/run-two.out" \
  || fail "purpose checker is nondeterministic"
/usr/bin/cmp -s "${tmp}/run-one.out" \
  "${tmp}/snapshot/${expected_receipt}" \
  || fail "fixed identity-composition receipt drift"

if ! run_purpose_self_test "${tmp}/self-test-one.out" "${tmp}/self-test-one.err"; then
  /usr/bin/cat "${tmp}/self-test-one.err" >&2
  fail "purpose checker self-test failed"
fi
if ! run_purpose_self_test "${tmp}/self-test-two.out" "${tmp}/self-test-two.err"; then
  /usr/bin/cat "${tmp}/self-test-two.err" >&2
  fail "second purpose checker self-test failed"
fi
[[ ! -s "${tmp}/self-test-one.err" && ! -s "${tmp}/self-test-two.err" ]] \
  || fail "purpose checker self-test emitted stderr"
/usr/bin/cmp -s "${tmp}/self-test-one.out" "${tmp}/self-test-two.out" \
  || fail "purpose checker self-test is nondeterministic"
[[ "$(/usr/bin/awk 'END { print NR }' "${tmp}/self-test-one.out")" == 1 \
  && "$(/usr/bin/awk -F '\t' 'NR == 1 { print $1 }' \
    "${tmp}/self-test-one.out")" == "SELF_TEST_OK" ]] \
  || fail "purpose checker self-test marker drift"

[[ "$(git_clean rev-parse --verify 'HEAD^{commit}')" == "${head_oid}" ]] \
  || fail "HEAD changed while the gate was running"
verify_history_metadata
[[ -z "$(git_clean status --porcelain=v1 --untracked-files=all \
  --ignore-submodules=none)" ]] || fail "worktree changed while the gate was running"
git_clean ls-files -v | /usr/bin/awk 'substr($0, 1, 1) != "H" {exit 1}' \
  || fail "nondefault Git index flags appeared while the gate was running"
verify_packet_identity
verify_evidence_identity
verify_prerequisite_gate_hashes

if [[ "${head_oid}" == "${source_commit}" ]]; then
  marker="BOUND_TO_HEAD_BIOCORTEX_AB_TRACK_B_IDENTITY_COMPOSITION_PACK"
  integration_status="BOUND_TO_HEAD"
else
  marker="VALID_INTEGRATED_BIOCORTEX_AB_TRACK_B_IDENTITY_COMPOSITION_PACK"
  integration_status="VALID_INTEGRATED"
fi
printf '%s\n' "${marker}"
printf 'integration_status=%s\n' "${integration_status}"
printf 'head=%s\n' "${head_oid}"
printf 'source_commit=%s\n' "${source_commit}"
printf 'baseline_commit=%s\n' "${baseline_commit}"
printf 'graph_gate_status=VALID_INTEGRATED\n'
printf 'foundational_gate_status=VALID_INTEGRATED\n'
printf 'expected_receipt_sha256=%s\n' \
  "$(/usr/bin/sha256sum "${tmp}/snapshot/${expected_receipt}" \
    | /usr/bin/awk '{print $1}')"
printf 'self_test_sha256=%s\n' \
  "$(/usr/bin/sha256sum "${tmp}/self-test-one.out" \
    | /usr/bin/awk '{print $1}')"
while IFS= read -r row; do
  printf '%s\n' "${row}"
done <"${tmp}/run-one.out"
