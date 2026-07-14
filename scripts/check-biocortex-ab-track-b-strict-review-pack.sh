#!/usr/bin/env -S -i /usr/bin/bash
# Source-bound, descendant-compatible, non-admitting gate for the Track B
# strict-case algorithm and review-receipt schema packet.
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
    printf 'Track B strict-review gate missing trusted tool: %s\n' \
      "${absolute_tool}" >&2
    exit 2
  }
done

cd "$(/usr/bin/dirname "${BASH_SOURCE[0]}")/.."

baseline_commit="ddebacba20146a90546db9e4ea4bd2795b9ecc1a"
receipt_schema="docs/design/fixtures/biocortex-ab-track-b-review-receipt-schema-v0.json"
strict_case_algorithm="scripts/eval/biocortex_ab_track_b_strict_case_v0.py"
purpose_checker="scripts/eval/check_biocortex_ab_track_b_strict_review_pack.py"
synthetic_fixture="scripts/eval/fixtures/biocortex_ab_track_b_strict_review_pack_synthetic_v0.json"
manifest="scripts/eval/fixtures/biocortex_ab_track_b_strict_review_pack_v0.json"
expected_receipt="scripts/eval/fixtures/biocortex_ab_track_b_strict_review_pack.expected.v0.tsv"
report="docs/reports/goal-c-u/2026-07-14-biocortex-track-b-strict-review-pack.md"
gate_path="scripts/check-biocortex-ab-track-b-strict-review-pack.sh"

packet_paths=(
  "${receipt_schema}"
  "${strict_case_algorithm}"
  "${purpose_checker}"
  "${synthetic_fixture}"
  "${manifest}"
  "${expected_receipt}"
  "${report}"
  "${gate_path}"
)
packet_modes=(100644 100644 100644 100644 100644 100644 100644 100755)

# These are the complete predecessor/evidence inputs expected by the packet
# checker plus the three prerequisite gates.  Packet files are catalogued
# separately above.  Every path is bound to ordinary HEAD/index bytes before
# immutable Git-blob snapshots are supplied to the checker.
purpose_evidence_paths=(
  "docs/design/fixtures/biocortex-ab-track-b-review-command-schema-v0.json"
  "docs/design/fixtures/biocortex-ab-track-b-review-schema-v0.json"
  "docs/design/fixtures/biocortex-ab-track-b-truth-manifest-schema-v0.json"
  "docs/design/fixtures/biocortex-ab-track-b-truth-referent-schema-v0.json"
  "scripts/eval/fixtures/biocortex_ab_track_b_artifact_dependency_graph_v0.json"
  "scripts/eval/fixtures/biocortex_ab_track_b_live_binding_ledger_v0.json"
  "scripts/eval/fixtures/biocortex_ab_track_b_real_run_admission_v0.json"
  "scripts/eval/fixtures/biocortex_ab_track_b_identity_composition_pack_v0.json"
  "scripts/eval/fixtures/biocortex_ab_track_b_identity_composition_pack_synthetic_v0.json"
)
prerequisite_gate_paths=(
  "scripts/check-biocortex-ab-track-b-artifact-dependency-graph.sh"
  "scripts/check-biocortex-ab-track-b-foundational-schema-pack.sh"
  "scripts/check-biocortex-ab-track-b-identity-composition-pack.sh"
)
evidence_paths=(
  "${purpose_evidence_paths[@]}"
  "${prerequisite_gate_paths[@]}"
)
evidence_modes=(
  100644 100644 100644 100644 100644 100644 100644 100644 100644
  100755 100755 100755
)

graph_gate="scripts/check-biocortex-ab-track-b-artifact-dependency-graph.sh"
foundational_gate="scripts/check-biocortex-ab-track-b-foundational-schema-pack.sh"
identity_gate="scripts/check-biocortex-ab-track-b-identity-composition-pack.sh"
graph_gate_sha256="20e0b36d583ad729b992a423834dbb7c05245c3689a5887e53fb04103222b001"
foundational_gate_sha256="17e9c53917139b6555e1546ab8ae675f85075fc09141d5c0033c1734ae6242e5"
identity_gate_sha256="d2a84c2d4e29e7adc8900fac1565359e6b6f01106916155b6895e4782ae11af5"
self_test_expected_sha256="a87d1c277dfe0b26f2ab05a7e529f7c8c6ec8805bdaa0a37e732d28825e45fa0"

tmp="$(/usr/bin/mktemp -d)"
cleanup() {
  /usr/bin/chmod -R u+w "${tmp}" 2>/dev/null || true
  /usr/bin/rm -rf "${tmp}"
}
trap cleanup EXIT
/usr/bin/mkdir -m 0700 "${tmp}/home" "${tmp}/child-tmp"

fail() {
  printf 'Track B strict-review gate failed: %s\n' "$*" >&2
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
  [[ "$(/usr/bin/sha256sum "${identity_gate}" | /usr/bin/awk '{print $1}')" \
    == "${identity_gate_sha256}" ]] \
    || fail "identity-composition gate hash drift"
}

verify_descendant_integration_shape() {
  local merge_oid other_parent parent found=0
  local -a merge_candidates parents
  [[ "${head_oid}" != "${source_commit}" ]] || return 0
  mapfile -t merge_candidates < <(
    git_clean rev-list --ancestry-path --merges \
      "${source_commit}..${head_oid}"
  )
  for merge_oid in "${merge_candidates[@]}"; do
    parents=()
    mapfile -t parents < <(
      git_clean cat-file commit "${merge_oid}" \
        | /usr/bin/awk '
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
    git_clean merge-base --is-ancestor "${baseline_commit}" "${other_parent}" \
      || continue
    if git_clean merge-base --is-ancestor "${source_commit}" "${other_parent}"; then
      continue
    fi
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
  local output="$1" error="$2"
  (
    cd "${tmp}/snapshot"
    HOME="${tmp}/home" TMPDIR="${tmp}/child-tmp" \
      /usr/bin/python3 "${tmp}/snapshot/${purpose_checker}" \
        --root "${tmp}/snapshot"
  ) >"${output}" 2>"${error}"
}

run_purpose_self_test() {
  local output="$1" error="$2"
  (
    cd "${tmp}/snapshot"
    HOME="${tmp}/home" TMPDIR="${tmp}/child-tmp" \
      /usr/bin/python3 "${tmp}/snapshot/${purpose_checker}" \
        --root "${tmp}/snapshot" --self-test
  ) >"${output}" 2>"${error}"
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
  || fail "strict-review manifest must have exactly one add commit"
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
  || fail "raw strict-review source commit must have exactly the frozen integrated baseline as parent"
git_clean merge-base --is-ancestor "${source_commit}" "${head_oid}" \
  || fail "strict-review source commit is not an ancestor of HEAD"
verify_descendant_integration_shape

{
  for path in "${packet_paths[@]}"; do
    printf 'A\t%s\n' "${path}"
  done
} | /usr/bin/sort >"${tmp}/expected-source-delta"
git_clean diff-tree --no-commit-id --no-renames --name-status \
  -r "${source_commit}" | /usr/bin/sort >"${tmp}/actual-source-delta"
/usr/bin/cmp -s "${tmp}/expected-source-delta" "${tmp}/actual-source-delta" \
  || fail "source commit is not the exact eight-path all-add strict-review packet"

verify_packet_identity
verify_evidence_identity
verify_prerequisite_gate_hashes

run_required_gate "${graph_gate}" \
  "VALID_INTEGRATED_BIOCORTEX_AB_TRACK_B_ARTIFACT_DEPENDENCY_GRAPH" \
  "artifact-dependency-graph"
run_required_gate "${foundational_gate}" \
  "VALID_INTEGRATED_BIOCORTEX_AB_TRACK_B_FOUNDATIONAL_SCHEMA_PACK" \
  "foundational-schema-pack"
run_required_gate "${identity_gate}" \
  "VALID_INTEGRATED_BIOCORTEX_AB_TRACK_B_IDENTITY_COMPOSITION_PACK" \
  "identity-composition-pack"

/usr/bin/mkdir -m 0700 "${tmp}/snapshot"
for path in "${packet_paths[@]}"; do
  snapshot_blob "${path}"
done
for path in "${purpose_evidence_paths[@]}"; do
  snapshot_blob "${path}"
done
/usr/bin/chmod -R a-w "${tmp}/snapshot"

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
  || fail "fixed strict-review receipt drift"

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
[[ -s "${tmp}/self-test-one.out" \
  && "$(/usr/bin/awk -F '\t' 'NR == 1 { print $1 }' \
    "${tmp}/self-test-one.out")" == "SELF_TEST_OK" ]] \
  || fail "purpose checker self-test marker drift"
[[ "$(/usr/bin/sha256sum "${tmp}/self-test-one.out" \
  | /usr/bin/awk '{print $1}')" == "${self_test_expected_sha256}" ]] \
  || fail "purpose checker self-test output hash drift"

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
  marker="BOUND_TO_HEAD_BIOCORTEX_AB_TRACK_B_STRICT_REVIEW_PACK"
  integration_status="BOUND_TO_HEAD"
else
  marker="VALID_INTEGRATED_BIOCORTEX_AB_TRACK_B_STRICT_REVIEW_PACK"
  integration_status="VALID_INTEGRATED"
fi
printf '%s\n' "${marker}"
printf 'integration_status=%s\n' "${integration_status}"
printf 'admission_status=SOURCE_VALIDATION_ONLY_NOT_LIVE_ADMISSION\n'
printf 'score_claim_status=NOT_CREATED\n'
printf 'head=%s\n' "${head_oid}"
printf 'source_commit=%s\n' "${source_commit}"
printf 'baseline_commit=%s\n' "${baseline_commit}"
printf 'graph_gate_status=VALID_INTEGRATED\n'
printf 'foundational_gate_status=VALID_INTEGRATED\n'
printf 'identity_gate_status=VALID_INTEGRATED\n'
printf 'expected_receipt_sha256=%s\n' \
  "$(/usr/bin/sha256sum "${tmp}/snapshot/${expected_receipt}" \
    | /usr/bin/awk '{print $1}')"
printf 'self_test_sha256=%s\n' \
  "$(/usr/bin/sha256sum "${tmp}/self-test-one.out" \
    | /usr/bin/awk '{print $1}')"
while IFS= read -r row; do
  printf '%s\n' "${row}"
done <"${tmp}/run-one.out"
