#!/usr/bin/env -S -i /usr/bin/bash
# Source-bound, fail-closed Git gate for the Track B reference-provider
# fault-injection runner v1 authority and adapter contract packet.
set -euo pipefail
umask 077

while IFS= read -r imported_function; do
  builtin unset -f "${imported_function}"
done < <(builtin compgen -A function)

rust_toolchain_bin="/home/pallasting/.cargo/bin"
PATH="/usr/bin:/bin:${rust_toolchain_bin}"
export PATH LC_ALL=C TZ=UTC
export PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1 PYTHONSAFEPATH=1
export GIT_ATTR_NOSYSTEM=1 GIT_OPTIONAL_LOCKS=0
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
    printf 'Reference-provider runner authority and adapter contract v1 gate missing host tool: %s\n' \
      "${absolute_tool}" >&2
    exit 2
  }
done

cd "$(/usr/bin/dirname "${BASH_SOURCE[0]}")/.."
repo_root="$(builtin pwd -P)"
[[ "${repo_root}" == /* && "${repo_root}" != "*" && "${repo_root}" != *$'\n'* \
  && -d "${repo_root}" && ! -L "${repo_root}" ]] || {
  printf 'Reference-provider runner authority and adapter contract v1 gate failed: repository root is not an exact canonical directory\n' >&2
  exit 1
}

baseline_commit="b15a48d17fb30b0990bf26210978f2a4f78f54cc"
predecessor_source_commit="27fd73aa36ac897fb817398eca3a191181d8fb5d"
predecessor_gate="scripts/check-biocortex-ab-track-b-reference-provider-fault-injection-offline-harness-v1-pack.sh"
authority_receipt_schema="docs/design/fixtures/biocortex-ab-track-b-reference-provider-fault-injection-runner-authority-receipt-schema-v1.json"
adapter_contract="docs/design/fixtures/biocortex-ab-track-b-reference-provider-fault-injection-runner-adapter-contract-v1.json"
stop_receipt_schema="docs/design/fixtures/biocortex-ab-track-b-reference-provider-fault-injection-runner-stop-receipt-schema-v1.json"
source_path="scripts/eval/biocortex_ab_track_b_reference_provider_fault_injection_runner_authority_and_adapter_contract_v1.py"
purpose_checker="scripts/eval/check_biocortex_ab_track_b_reference_provider_fault_injection_runner_authority_and_adapter_contract_v1_pack.py"
synthetic_fixture="scripts/eval/fixtures/biocortex_ab_track_b_reference_provider_fault_injection_runner_authority_and_adapter_contract_v1_pack_synthetic_v0.json"
expected_result="scripts/eval/fixtures/biocortex_ab_track_b_reference_provider_fault_injection_runner_authority_and_adapter_contract_v1_pack.expected.v0.tsv"
manifest="scripts/eval/fixtures/biocortex_ab_track_b_reference_provider_fault_injection_runner_authority_and_adapter_contract_v1_pack_v0.json"
report="docs/reports/goal-c-u/2026-07-15-biocortex-track-b-reference-provider-fault-injection-runner-authority-and-adapter-contract-v1-pack.md"
gate_path="scripts/check-biocortex-ab-track-b-reference-provider-fault-injection-runner-authority-and-adapter-contract-v1-pack.sh"

packet_paths=(
  "${authority_receipt_schema}"
  "${adapter_contract}"
  "${stop_receipt_schema}"
  "${source_path}"
  "${purpose_checker}"
  "${synthetic_fixture}"
  "${expected_result}"
  "${manifest}"
  "${report}"
  "${gate_path}"
)
packet_modes=(100644 100644 100644 100644 100644 100644 100644 100644 100644 100755)
predecessor_paths=(
  "docs/design/fixtures/biocortex-ab-track-b-reference-provider-fault-injection-offline-schedule-entry-schema-v1.json"
  "docs/design/fixtures/biocortex-ab-track-b-reference-provider-fault-injection-offline-run-row-schema-v1.json"
  "docs/design/fixtures/biocortex-ab-track-b-reference-provider-fault-injection-offline-harness-suite-receipt-schema-v1.json"
  "scripts/eval/biocortex_ab_track_b_reference_provider_fault_injection_harness_v1.py"
  "scripts/eval/check_biocortex_ab_track_b_reference_provider_fault_injection_offline_harness_v1_pack.py"
  "scripts/eval/fixtures/biocortex_ab_track_b_reference_provider_fault_injection_offline_harness_v1_pack_synthetic_v0.json"
  "scripts/eval/fixtures/biocortex_ab_track_b_reference_provider_fault_injection_offline_harness_v1_pack.expected.v0.tsv"
  "scripts/eval/fixtures/biocortex_ab_track_b_reference_provider_fault_injection_offline_harness_v1_pack_v0.json"
  "docs/reports/goal-c-u/2026-07-15-biocortex-track-b-reference-provider-fault-injection-offline-harness-v1-pack.md"
  "${predecessor_gate}"
)
report_bound_paths=(
  "${authority_receipt_schema}"
  "${adapter_contract}"
  "${stop_receipt_schema}"
  "${source_path}"
  "${purpose_checker}"
  "${synthetic_fixture}"
  "${expected_result}"
  "${predecessor_paths[@]}"
)

frozen_manifest_sha256="cefb64a0ac444c537833b6bbb8aed0819840d762c7e27d809248ab17ff24a482"
frozen_purpose_checker_sha256="c8f2258f9f8bac956958d6ebd011790814b6df3bad7f72213dd8241add7b4605"
frozen_expected_result_sha256="948842558a2be55a10660305758db5532ae89ec8b3340338c989befb26d5ce4b"

fail() {
  printf 'Reference-provider runner authority and adapter contract v1 gate failed: %s\n' "$*" >&2
  exit 1
}

git_clean() {
  /usr/bin/git --no-pager --no-replace-objects -c core.fsmonitor=false \
    -c core.attributesFile=/dev/null -c core.commitGraph=false \
    -c core.hooksPath=/dev/null -c safe.directory="${repo_root}" "$@"
}

[[ "$(git_clean config --get-all safe.directory)" == "${repo_root}" ]] \
  || fail "Git trust scope is not the exact repository root"

head_oid="$(git_clean rev-parse HEAD)" || fail "cannot resolve HEAD"
replace_refs="$(git_clean for-each-ref --format='%(refname)' refs/replace)" \
  || fail "cannot enumerate Git replace refs"
[[ -z "${replace_refs}" ]] \
  || fail "Git replace refs are present"
shallow_state="$(git_clean rev-parse --is-shallow-repository)" \
  || fail "cannot resolve shallow-repository state"
[[ "${shallow_state}" == false ]] \
  || fail "shallow history is not admissible"
common_dir="$(git_clean rev-parse --path-format=absolute --git-common-dir)" \
  || fail "cannot resolve Git common directory"
[[ -d "${common_dir}" && ! -L "${common_dir}" ]] \
  || fail "Git common directory is missing or a symlink"
git_dir="$(git_clean rev-parse --path-format=absolute --git-dir)" \
  || fail "cannot resolve Git directory"
[[ -d "${git_dir}" && ! -L "${git_dir}" ]] \
  || fail "Git directory is missing or a symlink"
case "${git_dir}" in
  "${common_dir}"|"${common_dir}"/worktrees/*) ;;
  *) fail "Git directory is outside the exact common-directory lineage" ;;
esac
[[ ! -e "${common_dir}/info/grafts" && ! -L "${common_dir}/info/grafts" ]] \
  || fail "legacy Git graft metadata is present"
[[ ! -e "${common_dir}/info/attributes" \
  && ! -L "${common_dir}/info/attributes" ]] \
  || fail "Git common info attributes are not admissible"
local_config_names="$(
  git_clean config --local --includes --name-only --list
)" || fail "cannot inspect repository-local Git configuration"
while IFS= read -r config_key; do
  case "${config_key,,}" in
    filter.*|diff.*|merge.*|core.attributesfile|include.*|includeif.*)
      fail "executable or external Git configuration is not admissible: ${config_key}"
      ;;
  esac
done <<<"${local_config_names}"
working_tree_attributes="$(
  /usr/bin/find . -name .gitattributes -print -quit
)" || fail "cannot inspect working-tree attributes"
[[ -z "${working_tree_attributes}" ]] \
  || fail "working-tree .gitattributes files are not admissible"
initial_status="$(git_clean status --porcelain=v1 --untracked-files=all)" \
  || fail "cannot inspect initial worktree and index status"
[[ -z "${initial_status}" ]] \
  || fail "worktree or index is not clean"

head_lineage=()
IFS=' ' read -r -a head_lineage \
  < <(git_clean rev-list --parents -n 1 "${head_oid}") \
  || fail "cannot resolve HEAD parent topology"
[[ "${#head_lineage[@]}" -ge 1 && "${head_lineage[0]}" == "${head_oid}" ]] \
  || fail "HEAD parent topology output is malformed"
head_parents=("${head_lineage[@]:1}")
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
  source_lineage=()
  IFS=' ' read -r -a source_lineage \
    < <(git_clean rev-list --parents -n 1 "${source_commit}") \
    || fail "cannot resolve source parent topology"
  [[ "${#source_lineage[@]}" -ge 1 \
    && "${source_lineage[0]}" == "${source_commit}" ]] \
    || fail "source parent topology output is malformed"
  source_parents=("${source_lineage[@]:1}")
  [[ "${#source_parents[@]}" == 1 && "${source_parents[0]}" == "${baseline_commit}" ]] \
    || fail "integrated second parent is not the exact source shape"
  git_clean merge-base --is-ancestor "${baseline_commit}" "${first_parent}" \
    || fail "integrated first parent does not descend from baseline"
  if git_clean merge-base --is-ancestor "${source_commit}" "${first_parent}"; then
    fail "integrated first parent already contains source"
  else
    merge_base_status=$?
    [[ "${merge_base_status}" == 1 ]] \
      || fail "cannot establish source exclusion from integrated first parent"
  fi
else
  fail "HEAD is neither the exact source shape nor an ordinary two-parent integration"
fi

project_parent="$(/usr/bin/dirname "${repo_root}")"
tmp_base="${project_parent}/.ab-gate-tmp"
[[ ! -L "${tmp_base}" ]] || fail "gate temp base is a symlink"
if [[ ! -e "${tmp_base}" ]]; then
  /usr/bin/mkdir -m 0700 "${tmp_base}"
fi
[[ -d "${tmp_base}" && ! -L "${tmp_base}" ]] || fail "gate temp base is invalid"
[[ "$(/usr/bin/stat -c '%u' "${tmp_base}")" == "${EUID}" ]] \
  || fail "gate temp base owner drift"
[[ "$(/usr/bin/stat -c '%a' "${tmp_base}")" == 700 ]] \
  || fail "gate temp base mode drift"
tmp="$(/usr/bin/mktemp -d "${tmp_base}/provider-runner-contract-v1.XXXXXX")"
[[ -d "${tmp}" && ! -L "${tmp}" ]] || fail "gate temp directory is invalid"
[[ "$(/usr/bin/stat -c '%u' "${tmp}")" == "${EUID}" ]] \
  || fail "gate temp directory owner drift"
[[ "$(/usr/bin/stat -c '%a' "${tmp}")" == 700 ]] \
  || fail "gate temp directory mode drift"
cleanup() {
  /usr/bin/chmod -R u+w "${tmp}" 2>/dev/null || true
  /usr/bin/rm -rf "${tmp}" 2>/dev/null || true
}
trap cleanup EXIT
/usr/bin/mkdir -m 0700 "${tmp}/home" "${tmp}/child-tmp" \
  "${tmp}/source-archive" "${tmp}/head-archive" "${tmp}/baseline-cargo-target"

/usr/bin/cat >"${tmp}/expected-paths" <<'EOF'
docs/design/fixtures/biocortex-ab-track-b-reference-provider-fault-injection-runner-authority-receipt-schema-v1.json
docs/design/fixtures/biocortex-ab-track-b-reference-provider-fault-injection-runner-adapter-contract-v1.json
docs/design/fixtures/biocortex-ab-track-b-reference-provider-fault-injection-runner-stop-receipt-schema-v1.json
scripts/eval/biocortex_ab_track_b_reference_provider_fault_injection_runner_authority_and_adapter_contract_v1.py
scripts/eval/check_biocortex_ab_track_b_reference_provider_fault_injection_runner_authority_and_adapter_contract_v1_pack.py
scripts/eval/fixtures/biocortex_ab_track_b_reference_provider_fault_injection_runner_authority_and_adapter_contract_v1_pack_synthetic_v0.json
scripts/eval/fixtures/biocortex_ab_track_b_reference_provider_fault_injection_runner_authority_and_adapter_contract_v1_pack.expected.v0.tsv
scripts/eval/fixtures/biocortex_ab_track_b_reference_provider_fault_injection_runner_authority_and_adapter_contract_v1_pack_v0.json
docs/reports/goal-c-u/2026-07-15-biocortex-track-b-reference-provider-fault-injection-runner-authority-and-adapter-contract-v1-pack.md
scripts/check-biocortex-ab-track-b-reference-provider-fault-injection-runner-authority-and-adapter-contract-v1-pack.sh
EOF

git_clean diff-tree --no-commit-id --name-status -r "${baseline_commit}" "${source_commit}" \
  | LC_ALL=C /usr/bin/sort >"${tmp}/actual-delta"
/usr/bin/awk '{ print "A\t" $0 }' "${tmp}/expected-paths" \
  | LC_ALL=C /usr/bin/sort >"${tmp}/expected-delta"
/usr/bin/cmp -s "${tmp}/expected-delta" "${tmp}/actual-delta" \
  || fail "source commit is not the exact ten-path all-add delta"

if [[ "${mode}" == integrated ]]; then
  : >"${tmp}/expected-integrated-delta"
  for path in "${packet_paths[@]}"; do
    first_parent_entry="$(git_clean ls-tree "${first_parent}" -- "${path}")" \
      || fail "cannot inspect integrated first-parent path: ${path}"
    source_entry="$(git_clean ls-tree "${source_commit}" -- "${path}")" \
      || fail "cannot inspect integrated source path: ${path}"
    if [[ "${path}" == "${gate_path}" ]]; then
      [[ -n "${first_parent_entry}" && "${first_parent_entry}" != "${source_entry}" ]] \
        || fail "integrated first parent lacks the distinct predecessor gate"
      printf 'M\t%s\n' "${path}" >"${tmp}/expected-integrated-delta"
    else
      [[ "${first_parent_entry}" == "${source_entry}" ]] \
        || fail "integrated first parent packet identity drift: ${path}"
    fi
  done
  git_clean diff-tree --no-commit-id --name-status -r "${first_parent}" "${head_oid}" \
    | LC_ALL=C /usr/bin/sort >"${tmp}/integrated-delta"
  /usr/bin/cmp -s "${tmp}/expected-integrated-delta" "${tmp}/integrated-delta" \
    || fail "integrated first-parent delta is not the exact gate maintenance change"
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
  if [[ "${expected_mode}" == 100755 ]]; then
    [[ -x "${path}" ]] || fail "protected executable bit is absent: ${path}"
  else
    [[ ! -x "${path}" ]] || fail "protected data path is executable: ${path}"
  fi
  read -r index_mode index_object index_stage indexed \
    < <(git_clean ls-files --stage -- "${path}") \
    || fail "cannot resolve index identity: ${path}"
  read -r source_mode source_type source_object source_indexed \
    < <(git_clean ls-tree "${source_commit}" -- "${path}") \
    || fail "cannot resolve source identity: ${path}"
  read -r head_mode head_type head_object head_indexed \
    < <(git_clean ls-tree "${head_oid}" -- "${path}") \
    || fail "cannot resolve HEAD identity: ${path}"
  [[ "${index_mode}" == "${expected_mode}" && "${source_mode}" == "${expected_mode}" \
    && "${head_mode}" == "${expected_mode}" && "${source_type}" == blob \
    && "${head_type}" == blob && "${index_stage}" == 0 \
    && "${indexed}" == "${path}" && "${source_indexed}" == "${path}" \
    && "${head_indexed}" == "${path}" && "${index_object}" == "${source_object}" \
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
    || fail "predecessor path identity drift: ${path}"
done

git_clean archive --format=tar "${source_commit}" | /usr/bin/tar -x -C "${tmp}/source-archive"
git_clean archive --format=tar "${head_oid}" | /usr/bin/tar -x -C "${tmp}/head-archive"
for archive in "${tmp}/source-archive" "${tmp}/head-archive"; do
  archive_symlink="$(/usr/bin/find "${archive}" -type l -print -quit)" \
    || fail "cannot inspect archive symlinks"
  [[ -z "${archive_symlink}" ]] || fail "archive contains a symlink"
  archive_hardlink="$(/usr/bin/find "${archive}" -type f -links +1 -print -quit)" \
    || fail "cannot inspect archive hard links"
  [[ -z "${archive_hardlink}" ]] || fail "archive contains a hardlinked file"
done

verify_frozen_sha256() {
  local label="$1" expected="$2" path="$3" actual
  actual="$(/usr/bin/sha256sum "${tmp}/source-archive/${path}" | /usr/bin/awk '{print $1}')"
  [[ "${actual}" == "${expected}" ]] || fail "${label} frozen SHA-256 drift: ${path}"
}
verify_frozen_sha256 manifest "${frozen_manifest_sha256}" "${manifest}"
verify_frozen_sha256 purpose-checker "${frozen_purpose_checker_sha256}" "${purpose_checker}"
verify_frozen_sha256 expected-result "${frozen_expected_result_sha256}" "${expected_result}"

for seed in 0 314159; do
  for test_mode in normal self-test; do
    args=()
    [[ "${test_mode}" == self-test ]] && args+=(--self-test)
    /usr/bin/env -i PATH="${PATH}" HOME="${tmp}/home" LC_ALL=C TZ=UTC \
      PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1 PYTHONSAFEPATH=1 \
      PYTHONHASHSEED="${seed}" \
      /usr/bin/python3 -S -P "${tmp}/source-archive/${purpose_checker}" \
        --root "${tmp}/source-archive" "${args[@]}" \
        >"${tmp}/source-${seed}-${test_mode}.tsv"
    /usr/bin/cmp -s "${tmp}/source-archive/${expected_result}" \
      "${tmp}/source-${seed}-${test_mode}.tsv" \
      || fail "source checker drift for seed ${seed} ${test_mode}"
  done
done
/usr/bin/cmp -s "${tmp}/source-0-normal.tsv" "${tmp}/source-314159-self-test.tsv" \
  || fail "source checker is hash-seed or self-test nondeterministic"

if [[ "${mode}" == integrated ]]; then
  for seed in 0 314159; do
    /usr/bin/env -i PATH="${PATH}" HOME="${tmp}/home" LC_ALL=C TZ=UTC \
      PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1 PYTHONSAFEPATH=1 \
      PYTHONHASHSEED="${seed}" \
      /usr/bin/python3 -S -P "${tmp}/head-archive/${purpose_checker}" \
        --root "${tmp}/head-archive" --self-test \
        >"${tmp}/integrated-${seed}.tsv"
    /usr/bin/cmp -s "${tmp}/head-archive/${expected_result}" \
      "${tmp}/integrated-${seed}.tsv" \
      || fail "integrated checker drift for seed ${seed}"
  done
fi

[[ "$(/usr/bin/grep -Fxc -- '## Artifact binding' \
  "${tmp}/source-archive/${report}")" == 1 ]] \
  || fail "report lacks an exact-once Artifact binding heading"
: >"${tmp}/expected-report-bindings"
for path in "${report_bound_paths[@]}"; do
  digest="$(
    /usr/bin/sha256sum "${tmp}/source-archive/${path}" \
      | /usr/bin/awk '{print $1}'
  )" || fail "cannot hash report-bound artifact: ${path}"
  printf -- '- `%s`: `%s`\n' "${path}" "${digest}" \
    >>"${tmp}/expected-report-bindings"
done
/usr/bin/awk '
  $0 == "## Artifact binding" { in_section = 1; next }
  in_section && /^## / { in_section = 0 }
  in_section && NF { print }
' "${tmp}/source-archive/${report}" >"${tmp}/actual-report-bindings"
/usr/bin/cmp -s "${tmp}/expected-report-bindings" \
  "${tmp}/actual-report-bindings" \
  || fail "report Artifact binding section is not the exact ordered catalog"

predecessor_repo="${tmp}/predecessor-repo"
if ! git_clean clone --no-local --no-checkout --no-tags --single-branch -- \
  . "${predecessor_repo}" \
  >"${tmp}/predecessor-clone.stdout" 2>"${tmp}/predecessor-clone.stderr"; then
  /usr/bin/cat "${tmp}/predecessor-clone.stderr" >&2
  fail "cannot create isolated predecessor repository"
fi
if ! git_clean -C "${predecessor_repo}" checkout --detach "${baseline_commit}" \
  >"${tmp}/predecessor-checkout.stdout" 2>"${tmp}/predecessor-checkout.stderr"; then
  /usr/bin/cat "${tmp}/predecessor-checkout.stderr" >&2
  fail "cannot check out predecessor baseline in isolated repository"
fi
isolated_head_oid="$(git_clean -C "${predecessor_repo}" rev-parse HEAD)" \
  || fail "cannot resolve isolated predecessor HEAD"
[[ "${isolated_head_oid}" == "${baseline_commit}" ]] \
  || fail "isolated predecessor baseline HEAD drift"
predecessor_status_before="$(
  git_clean -C "${predecessor_repo}" status --porcelain=v1 --untracked-files=all
)" || fail "cannot inspect predecessor baseline status before replay"
[[ -z "${predecessor_status_before}" ]] \
  || fail "predecessor baseline dirty before replay"
read -r predecessor_gate_mode predecessor_gate_type predecessor_gate_object \
  predecessor_gate_indexed \
  < <(git_clean -C "${predecessor_repo}" ls-tree \
    "${baseline_commit}" -- "${predecessor_gate}") \
  || fail "cannot resolve predecessor gate object"
[[ "${predecessor_gate_mode}" == 100755 \
  && "${predecessor_gate_type}" == blob \
  && "${predecessor_gate_indexed}" == "${predecessor_gate}" ]] \
  || fail "predecessor gate identity or mode drift"
/usr/bin/cmp -s "${predecessor_repo}/${predecessor_gate}" \
  <(git_clean -C "${predecessor_repo}" cat-file blob "${predecessor_gate_object}") \
  || fail "executable predecessor gate bytes differ from baseline blob"
git_clean -C "${predecessor_repo}" worktree list --porcelain \
  >"${tmp}/worktrees-before-predecessor"
predecessor_gate_tmp_base="${tmp}/.ab-gate-tmp"
[[ ! -e "${predecessor_gate_tmp_base}" && ! -L "${predecessor_gate_tmp_base}" ]] \
  || fail "isolated predecessor gate temp base exists before replay"
if ! (
  cd "${predecessor_repo}"
  TMPDIR="${tmp}/child-tmp" CARGO_TARGET_DIR="${tmp}/baseline-cargo-target" \
    PYTHONDONTWRITEBYTECODE=1 "${predecessor_gate}"
) >"${tmp}/predecessor-gate.stdout" 2>"${tmp}/predecessor-gate.stderr"; then
  /usr/bin/cat "${tmp}/predecessor-gate.stderr" >&2
  fail "predecessor integration gate replay failed"
fi
git_clean -C "${predecessor_repo}" worktree list --porcelain \
  >"${tmp}/worktrees-after-predecessor"
/usr/bin/cmp -s "${tmp}/worktrees-before-predecessor" \
  "${tmp}/worktrees-after-predecessor" \
  || fail "predecessor replay changed isolated worktree registrations"
if [[ -e "${predecessor_gate_tmp_base}" \
  || -L "${predecessor_gate_tmp_base}" ]]; then
  [[ -d "${predecessor_gate_tmp_base}" \
    && ! -L "${predecessor_gate_tmp_base}" ]] \
    || fail "isolated predecessor gate temp base is invalid after replay"
  [[ "$(/usr/bin/stat -c '%u' "${predecessor_gate_tmp_base}")" == "${EUID}" \
    && "$(/usr/bin/stat -c '%a' "${predecessor_gate_tmp_base}")" == 700 ]] \
    || fail "isolated predecessor gate temp base owner or mode drift"
  predecessor_temp_residue="$(
    /usr/bin/find "${predecessor_gate_tmp_base}" -mindepth 1 -print -quit
  )" || fail "cannot inspect isolated predecessor gate temp residue"
  [[ -z "${predecessor_temp_residue}" ]] \
    || fail "predecessor replay left isolated gate temp residue"
fi
for expected_line in \
  $'integration_gate\tVALID_INTEGRATED_BIOCORTEX_AB_TRACK_B_REFERENCE_PROVIDER_FAULT_INJECTION_OFFLINE_HARNESS_V1_PACK' \
  $'gate\tPASS' \
  $'mode\tintegrated' \
  $'source_commit\t'"${predecessor_source_commit}" \
  $'head\t'"${baseline_commit}"; do
  [[ "$(/usr/bin/grep -Fxc -- "${expected_line}" "${tmp}/predecessor-gate.stdout")" == 1 ]] \
    || fail "predecessor output lacks exact-once binding: ${expected_line}"
done
predecessor_status_after="$(
  git_clean -C "${predecessor_repo}" status --porcelain=v1 --untracked-files=all
)" || fail "cannot inspect predecessor baseline status after replay"
[[ -z "${predecessor_status_after}" ]] \
  || fail "predecessor replay dirtied worktree"

git_clean diff --check "${baseline_commit}" "${source_commit}"
final_head_oid="$(git_clean rev-parse HEAD)" || fail "cannot resolve final HEAD"
[[ "${final_head_oid}" == "${head_oid}" ]] || fail "HEAD changed during gate"
final_status="$(git_clean status --porcelain=v1 --untracked-files=all)" \
  || fail "cannot inspect final worktree and index status"
[[ -z "${final_status}" ]] \
  || fail "verification dirtied worktree or index"

source_result="$(/usr/bin/cat "${tmp}/source-0-normal.tsv")"
/usr/bin/chmod -R u+w "${tmp}" \
  || fail "cannot make gate temp tree removable"
/usr/bin/rm -rf "${tmp}" \
  || fail "cannot remove gate temp tree"
[[ ! -e "${tmp}" && ! -L "${tmp}" ]] \
  || fail "gate temp tree survived removal"
trap - EXIT

printf '%s\n' "${source_result}"
if [[ "${mode}" == integrated ]]; then
  printf 'integration_gate\tVALID_INTEGRATED_BIOCORTEX_AB_TRACK_B_REFERENCE_PROVIDER_FAULT_INJECTION_RUNNER_AUTHORITY_AND_ADAPTER_CONTRACT_V1_PACK\n'
else
  printf 'source_gate\tVALID_SOURCE_BIOCORTEX_AB_TRACK_B_REFERENCE_PROVIDER_FAULT_INJECTION_RUNNER_AUTHORITY_AND_ADAPTER_CONTRACT_V1_PACK\n'
fi
printf 'gate\tPASS\n'
printf 'mode\t%s\n' "${mode}"
printf 'source_commit\t%s\n' "${source_commit}"
printf 'head\t%s\n' "${head_oid}"
