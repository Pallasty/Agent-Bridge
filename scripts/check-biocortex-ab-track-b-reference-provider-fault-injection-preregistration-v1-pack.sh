#!/usr/bin/env -S -i /usr/bin/bash
# Source-bound, fail-closed Git gate for the Track B reference-provider
# fault-injection experiment v1 preregistration packet.
set -euo pipefail
umask 077

while IFS= read -r imported_function; do
  builtin unset -f "${imported_function}"
done < <(builtin compgen -A function)

rust_toolchain_bin="/home/pallasting/.cargo/bin"
PATH="/usr/bin:/bin:${rust_toolchain_bin}"
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

for absolute_tool in "${rust_toolchain_bin}/cargo" "${rust_toolchain_bin}/rustfmt" \
  /usr/bin/awk /usr/bin/bash /usr/bin/cat /usr/bin/chmod /usr/bin/cmp \
  /usr/bin/dirname /usr/bin/env /usr/bin/find /usr/bin/git /usr/bin/grep \
  /usr/bin/mkdir /usr/bin/mktemp /usr/bin/python3 /usr/bin/rm \
  /usr/bin/sha256sum /usr/bin/sort /usr/bin/stat /usr/bin/tar; do
  [[ -x "${absolute_tool}" ]] || {
    printf 'Reference-provider fault-injection preregistration v1 gate missing host tool: %s\n' \
      "${absolute_tool}" >&2
    exit 2
  }
done

cd "$(/usr/bin/dirname "${BASH_SOURCE[0]}")/.."

baseline_commit="3ca858bd6f0097dd0f7f928e7acb4aef030a47a2"
predecessor_source_commit="3054ffe692e2e8f4edf22bda86fcbe4c9e1077d2"
predecessor_gate="scripts/check-biocortex-ab-track-b-external-atomic-live-output-boundary-v1-pack.sh"
receipt_schema="docs/design/fixtures/biocortex-ab-track-b-reference-provider-fault-injection-preregistration-receipt-schema-v1.json"
observation_schema="docs/design/fixtures/biocortex-ab-track-b-reference-provider-fault-injection-pre-execution-observation-schema-v1.json"
contract="docs/design/fixtures/biocortex-ab-track-b-reference-provider-fault-injection-experiment-contract-v1.json"
source_path="scripts/eval/biocortex_ab_track_b_reference_provider_fault_injection_preregistration_v1.py"
purpose_checker="scripts/eval/check_biocortex_ab_track_b_reference_provider_fault_injection_preregistration_v1_pack.py"
observation="scripts/eval/fixtures/biocortex_ab_track_b_reference_provider_fault_injection_preregistration_v1_pack_synthetic_v0.json"
expected_result="scripts/eval/fixtures/biocortex_ab_track_b_reference_provider_fault_injection_preregistration_v1_pack.expected.v0.tsv"
manifest="scripts/eval/fixtures/biocortex_ab_track_b_reference_provider_fault_injection_preregistration_v1_pack_v0.json"
report="docs/reports/goal-c-u/2026-07-15-biocortex-track-b-reference-provider-fault-injection-preregistration-v1-pack.md"
gate_path="scripts/check-biocortex-ab-track-b-reference-provider-fault-injection-preregistration-v1-pack.sh"

packet_paths=(
  "${receipt_schema}"
  "${observation_schema}"
  "${contract}"
  "${source_path}"
  "${purpose_checker}"
  "${observation}"
  "${expected_result}"
  "${manifest}"
  "${report}"
  "${gate_path}"
)
packet_modes=(100644 100644 100644 100644 100644 100644 100644 100644 100644 100755)
predecessor_paths=(
  "docs/design/fixtures/biocortex-ab-track-b-external-atomic-live-output-boundary-design-receipt-schema-v1.json"
  "docs/design/fixtures/biocortex-ab-track-b-external-atomic-live-output-execution-boundary-contract-v1.json"
  "docs/design/fixtures/biocortex-ab-track-b-production-provider-prerequisite-observation-source-profile-schema-v1.json"
  "scripts/eval/biocortex_ab_track_b_external_atomic_live_output_boundary_v1.py"
  "scripts/eval/check_biocortex_ab_track_b_external_atomic_live_output_boundary_v1_pack.py"
  "scripts/eval/fixtures/biocortex_ab_track_b_external_atomic_live_output_boundary_v1_pack_synthetic_v0.json"
  "scripts/eval/fixtures/biocortex_ab_track_b_external_atomic_live_output_boundary_v1_pack.expected.v0.tsv"
  "scripts/eval/fixtures/biocortex_ab_track_b_external_atomic_live_output_boundary_v1_pack_v0.json"
  "docs/reports/goal-c-u/2026-07-15-biocortex-track-b-external-atomic-live-output-boundary-v1-pack.md"
  "scripts/check-biocortex-ab-track-b-external-atomic-live-output-boundary-v1-pack.sh"
)
report_bound_paths=(
  "${receipt_schema}"
  "${observation_schema}"
  "${contract}"
  "${source_path}"
  "${purpose_checker}"
  "${observation}"
  "${expected_result}"
  "${predecessor_paths[@]}"
)

frozen_manifest_sha256="4f15f205539796213ee6f7d0694b7c6bcaf69dae6014b1d084d66228b96486df"
frozen_purpose_checker_sha256="874f5f5ac44e4a481f99fd7c23755067c2dba9d848df5ad5a43cb5f26ba422f8"
frozen_expected_result_sha256="11e7e716d799966d1d29d00ee6368260b97f3814ae99c7fceed2fbfd31837f14"

fail() {
  printf 'Reference-provider fault-injection preregistration v1 gate failed: %s\n' "$*" >&2
  exit 1
}

git_clean() {
  /usr/bin/git --no-pager --no-replace-objects -c core.fsmonitor=false \
    -c core.commitGraph=false -c core.hooksPath=/dev/null "$@"
}

[[ -z "$(git_clean status --porcelain=v1 --untracked-files=all)" ]] \
  || fail "worktree or index is not clean"
head_oid="$(git_clean rev-parse HEAD)" || fail "cannot resolve HEAD"
[[ -z "$(git_clean for-each-ref --format='%(refname)' refs/replace)" ]] \
  || fail "Git replace refs are present"
[[ "$(git_clean rev-parse --is-shallow-repository)" == false ]] \
  || fail "shallow history is not admissible"
common_dir="$(git_clean rev-parse --path-format=absolute --git-common-dir)" \
  || fail "cannot resolve Git common directory"
[[ -d "${common_dir}" && ! -L "${common_dir}" ]] \
  || fail "Git common directory is missing or a symlink"
grafts_path="${common_dir}/info/grafts"
[[ ! -e "${grafts_path}" && ! -L "${grafts_path}" ]] \
  || fail "legacy Git graft metadata is present"

mapfile -t head_parents < <(
  git_clean cat-file commit "${head_oid}" | /usr/bin/awk '
    BEGIN { in_headers = 1 }
    in_headers && $0 == "" { in_headers = 0 }
    in_headers && $1 == "parent" { print $2 }
  '
)
mode=""
source_commit=""
first_parent=""
if [[ "${#head_parents[@]}" == 1 && "${head_parents[0]}" == "${baseline_commit}" ]]; then
  mode="source"
  source_commit="${head_oid}"
elif [[ "${#head_parents[@]}" == 2 ]]; then
  mode="integrated"
  first_parent="${head_parents[0]}"
  source_commit="${head_parents[1]}"
  mapfile -t source_parents < <(
    git_clean cat-file commit "${source_commit}" | /usr/bin/awk '
      BEGIN { in_headers = 1 }
      in_headers && $0 == "" { in_headers = 0 }
      in_headers && $1 == "parent" { print $2 }
    '
  )
  [[ "${#source_parents[@]}" == 1 && "${source_parents[0]}" == "${baseline_commit}" ]] \
    || fail "integrated second parent is not the exact source shape"
  git_clean merge-base --is-ancestor "${baseline_commit}" "${first_parent}" \
    || fail "integrated first parent does not descend from the baseline"
  ! git_clean merge-base --is-ancestor "${source_commit}" "${first_parent}" \
    || fail "integrated first parent already contains the source commit"
else
  fail "HEAD is neither the exact source shape nor an ordinary two-parent integration"
fi

project_parent="$(/usr/bin/dirname "$(/usr/bin/dirname "${common_dir}")")"
tmp_base="${project_parent}/.ab-gate-tmp"
[[ ! -L "${tmp_base}" ]] || fail "gate temp base is a symlink"
if [[ ! -e "${tmp_base}" ]]; then
  /usr/bin/mkdir -m 0700 "${tmp_base}"
fi
[[ -d "${tmp_base}" && ! -L "${tmp_base}" ]] \
  || fail "gate temp base is not a real directory"
[[ "$(/usr/bin/stat -c '%u' "${tmp_base}")" == "${EUID}" ]] \
  || fail "gate temp base is not owned by the effective user"
[[ "$(/usr/bin/stat -c '%a' "${tmp_base}")" == 700 ]] \
  || fail "gate temp base mode is not 0700"
tmp="$(/usr/bin/mktemp -d "${tmp_base}/provider-prereg-v1.XXXXXX")"
[[ -d "${tmp}" && ! -L "${tmp}" ]] || fail "gate temp directory is invalid"
[[ "$(/usr/bin/stat -c '%u' "${tmp}")" == "${EUID}" ]] \
  || fail "gate temp directory owner drift"
[[ "$(/usr/bin/stat -c '%a' "${tmp}")" == 700 ]] \
  || fail "gate temp directory mode drift"
baseline_worktree=""
cleanup() {
  if [[ -n "${baseline_worktree}" ]]; then
    git_clean worktree remove --force "${baseline_worktree}" >/dev/null 2>&1 || true
  fi
  /usr/bin/chmod -R u+w "${tmp}" 2>/dev/null || true
  /usr/bin/rm -rf "${tmp}"
}
trap cleanup EXIT
/usr/bin/mkdir -m 0700 "${tmp}/home" "${tmp}/child-tmp" \
  "${tmp}/source-archive" "${tmp}/head-archive" "${tmp}/baseline-cargo-target"

/usr/bin/cat >"${tmp}/expected-paths" <<'EOF'
docs/design/fixtures/biocortex-ab-track-b-reference-provider-fault-injection-preregistration-receipt-schema-v1.json
docs/design/fixtures/biocortex-ab-track-b-reference-provider-fault-injection-pre-execution-observation-schema-v1.json
docs/design/fixtures/biocortex-ab-track-b-reference-provider-fault-injection-experiment-contract-v1.json
scripts/eval/biocortex_ab_track_b_reference_provider_fault_injection_preregistration_v1.py
scripts/eval/check_biocortex_ab_track_b_reference_provider_fault_injection_preregistration_v1_pack.py
scripts/eval/fixtures/biocortex_ab_track_b_reference_provider_fault_injection_preregistration_v1_pack_synthetic_v0.json
scripts/eval/fixtures/biocortex_ab_track_b_reference_provider_fault_injection_preregistration_v1_pack.expected.v0.tsv
scripts/eval/fixtures/biocortex_ab_track_b_reference_provider_fault_injection_preregistration_v1_pack_v0.json
docs/reports/goal-c-u/2026-07-15-biocortex-track-b-reference-provider-fault-injection-preregistration-v1-pack.md
scripts/check-biocortex-ab-track-b-reference-provider-fault-injection-preregistration-v1-pack.sh
EOF

git_clean diff-tree --no-commit-id --name-status -r "${baseline_commit}" "${source_commit}" \
  | LC_ALL=C /usr/bin/sort >"${tmp}/actual-delta"
/usr/bin/awk '{ print "A\t" $0 }' "${tmp}/expected-paths" \
  | LC_ALL=C /usr/bin/sort >"${tmp}/expected-delta"
/usr/bin/cmp -s "${tmp}/expected-delta" "${tmp}/actual-delta" \
  || fail "source commit is not the exact ten-path all-add delta"

if [[ "${mode}" == integrated ]]; then
  for path in "${packet_paths[@]}"; do
    [[ -z "$(git_clean ls-tree "${first_parent}" -- "${path}")" ]] \
      || fail "integrated first parent already contains packet path: ${path}"
  done
  git_clean diff-tree --no-commit-id --name-status -r "${first_parent}" "${head_oid}" \
    | LC_ALL=C /usr/bin/sort >"${tmp}/integrated-delta"
  /usr/bin/cmp -s "${tmp}/expected-delta" "${tmp}/integrated-delta" \
    || fail "integrated first-parent delta is not the exact ten-path packet"
fi

reject_symlink_components() {
  local path="$1" component cursor=""
  local -a components
  IFS=/ read -r -a components <<<"${path}"
  for component in "${components[@]}"; do
    if [[ -n "${cursor}" ]]; then cursor="${cursor}/${component}"; else cursor="${component}"; fi
    [[ ! -L "${cursor}" ]] || fail "protected path contains a symlink: ${path}"
  done
}

for index in "${!packet_paths[@]}"; do
  path="${packet_paths[$index]}"
  expected_mode="${packet_modes[$index]}"
  reject_symlink_components "${path}"
  [[ -f "${path}" && "$(/usr/bin/stat -c '%F' -- "${path}")" == "regular file" ]] \
    || fail "protected path is not a regular file: ${path}"
  [[ "$(/usr/bin/stat -c '%h' -- "${path}")" == 1 ]] \
    || fail "protected path has hard-link aliases: ${path}"
  read -r index_mode index_object index_stage indexed \
    < <(git_clean ls-files --stage -- "${path}") \
    || fail "cannot resolve index identity: ${path}"
  read -r source_mode source_type source_object source_indexed \
    < <(git_clean ls-tree "${source_commit}" -- "${path}") \
    || fail "cannot resolve source identity: ${path}"
  read -r head_mode head_type head_object head_indexed \
    < <(git_clean ls-tree "${head_oid}" -- "${path}") \
    || fail "cannot resolve HEAD identity: ${path}"
  [[ "${index_mode}" == "${expected_mode}" \
    && "${source_mode}" == "${expected_mode}" \
    && "${head_mode}" == "${expected_mode}" \
    && "${source_type}" == blob && "${head_type}" == blob \
    && "${index_stage}" == 0 && "${indexed}" == "${path}" \
    && "${source_indexed}" == "${path}" && "${head_indexed}" == "${path}" \
    && "${index_object}" == "${source_object}" \
    && "${head_object}" == "${source_object}" ]] \
    || fail "source/HEAD/index identity or mode drift: ${path}"
  [[ "$(git_clean ls-files -v -- "${path}")" == "H ${path}" ]] \
    || fail "nondefault Git index flag: ${path}"
  /usr/bin/cmp -s "${path}" <(git_clean cat-file blob "${source_object}") \
    || fail "worktree/source-commit byte drift: ${path}"
done

for path in "${predecessor_paths[@]}"; do
  baseline_entry="$(git_clean ls-tree "${baseline_commit}" -- "${path}")"
  head_entry="$(git_clean ls-tree "${head_oid}" -- "${path}")"
  [[ -n "${baseline_entry}" && "${head_entry}" == "${baseline_entry}" ]] \
    || fail "predecessor path identity drift from frozen baseline: ${path}"
done

git_clean archive --format=tar "${source_commit}" \
  | /usr/bin/tar -x -C "${tmp}/source-archive"
git_clean archive --format=tar "${head_oid}" \
  | /usr/bin/tar -x -C "${tmp}/head-archive"
for archive in "${tmp}/source-archive" "${tmp}/head-archive"; do
  [[ -z "$(/usr/bin/find "${archive}" -type l -print -quit)" ]] \
    || fail "archive contains a symlink"
  [[ -z "$(/usr/bin/find "${archive}" -type f -links +1 -print -quit)" ]] \
    || fail "archive contains a hardlinked file"
done

verify_frozen_sha256() {
  local label="$1" expected="$2" path="$3" actual
  actual="$(/usr/bin/sha256sum "${tmp}/source-archive/${path}" | /usr/bin/awk '{print $1}')"
  [[ "${actual}" == "${expected}" ]] \
    || fail "${label} frozen SHA-256 drift: ${path}"
}
verify_frozen_sha256 manifest "${frozen_manifest_sha256}" "${manifest}"
verify_frozen_sha256 purpose-checker "${frozen_purpose_checker_sha256}" "${purpose_checker}"
verify_frozen_sha256 expected-result "${frozen_expected_result_sha256}" "${expected_result}"

for seed in 0 314159; do
  for self_test in normal self-test; do
    args=()
    [[ "${self_test}" == self-test ]] && args+=(--self-test)
    /usr/bin/env -i PATH="${PATH}" HOME="${tmp}/home" LC_ALL=C TZ=UTC \
      PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1 PYTHONSAFEPATH=1 \
      PYTHONHASHSEED="${seed}" \
      /usr/bin/python3 "${tmp}/source-archive/${purpose_checker}" \
        --root "${tmp}/source-archive" "${args[@]}" \
        >"${tmp}/source-${seed}-${self_test}.tsv"
    /usr/bin/cmp -s "${tmp}/source-archive/${expected_result}" \
      "${tmp}/source-${seed}-${self_test}.tsv" \
      || fail "source archive checker drift for seed ${seed} ${self_test}"
  done
done
/usr/bin/cmp -s "${tmp}/source-0-normal.tsv" "${tmp}/source-314159-self-test.tsv" \
  || fail "source checker is hash-seed or self-test nondeterministic"

if [[ "${mode}" == integrated ]]; then
  for seed in 0 314159; do
    /usr/bin/env -i PATH="${PATH}" HOME="${tmp}/home" LC_ALL=C TZ=UTC \
      PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1 PYTHONSAFEPATH=1 \
      PYTHONHASHSEED="${seed}" \
      /usr/bin/python3 "${tmp}/head-archive/${purpose_checker}" \
        --root "${tmp}/head-archive" --self-test \
        >"${tmp}/integrated-${seed}.tsv"
    /usr/bin/cmp -s "${tmp}/head-archive/${expected_result}" \
      "${tmp}/integrated-${seed}.tsv" \
      || fail "integrated checker drift for seed ${seed}"
  done
fi

for path in "${report_bound_paths[@]}"; do
  digest="$(/usr/bin/sha256sum "${tmp}/source-archive/${path}" | /usr/bin/awk '{print $1}')"
  /usr/bin/grep -F -- "- \`${path}\`: \`${digest}\`" \
    "${tmp}/source-archive/${report}" >/dev/null \
    || fail "report does not bind ${path} at ${digest}"
done

baseline_worktree="${tmp}/predecessor-baseline"
git_clean worktree add --detach "${baseline_worktree}" "${baseline_commit}" >/dev/null
[[ "$(git_clean -C "${baseline_worktree}" rev-parse HEAD)" == "${baseline_commit}" ]] \
  || fail "predecessor baseline worktree HEAD drift"
[[ -z "$(git_clean -C "${baseline_worktree}" status --porcelain=v1 --untracked-files=all)" ]] \
  || fail "predecessor baseline worktree is dirty before replay"
if ! (
  cd "${baseline_worktree}"
  TMPDIR="${tmp}/child-tmp" CARGO_TARGET_DIR="${tmp}/baseline-cargo-target" \
    PYTHONDONTWRITEBYTECODE=1 "${predecessor_gate}"
) >"${tmp}/predecessor-gate.stdout" 2>"${tmp}/predecessor-gate.stderr"; then
  /usr/bin/cat "${tmp}/predecessor-gate.stderr" >&2
  fail "predecessor integration gate replay failed"
fi
for expected_line in \
  $'integration_gate\tVALID_INTEGRATED_BIOCORTEX_AB_TRACK_B_EXTERNAL_ATOMIC_LIVE_OUTPUT_BOUNDARY_V1_PACK' \
  $'gate\tPASS' \
  $'mode\tintegrated' \
  $'source_commit\t3054ffe692e2e8f4edf22bda86fcbe4c9e1077d2' \
  $'head\t3ca858bd6f0097dd0f7f928e7acb4aef030a47a2'; do
  [[ "$(/usr/bin/grep -Fxc -- "${expected_line}" "${tmp}/predecessor-gate.stdout")" == 1 ]] \
    || fail "predecessor output lacks exact-once binding: ${expected_line}"
done
[[ -z "$(git_clean -C "${baseline_worktree}" status --porcelain=v1 --untracked-files=all)" ]] \
  || fail "predecessor gate replay dirtied its worktree"

git_clean diff --check "${baseline_commit}" "${source_commit}"
[[ "$(git_clean rev-parse HEAD)" == "${head_oid}" ]] \
  || fail "HEAD changed during verification"
[[ -z "$(git_clean status --porcelain=v1 --untracked-files=all)" ]] \
  || fail "verification dirtied worktree or index"

/usr/bin/cat "${tmp}/source-0-normal.tsv"
if [[ "${mode}" == integrated ]]; then
  printf 'integration_gate\tVALID_INTEGRATED_BIOCORTEX_AB_TRACK_B_REFERENCE_PROVIDER_FAULT_INJECTION_PREREGISTRATION_V1_PACK\n'
else
  printf 'source_gate\tVALID_SOURCE_BIOCORTEX_AB_TRACK_B_REFERENCE_PROVIDER_FAULT_INJECTION_PREREGISTRATION_V1_PACK\n'
fi
printf 'gate\tPASS\n'
printf 'mode\t%s\n' "${mode}"
printf 'source_commit\t%s\n' "${source_commit}"
printf 'head\t%s\n' "${head_oid}"
