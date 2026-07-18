#!/usr/bin/env -S -i /usr/bin/bash
# Source-bound Git gate for the signer role/scope authorization isolated-lab
# implementation-authority and resource-binding decision pack.
set -euo pipefail
umask 077

while IFS= read -r imported_function; do
  builtin unset -f "${imported_function}"
done < <(builtin compgen -A function)

PATH="/usr/bin:/bin:/home/pallasting/.cargo/bin"
export PATH LC_ALL=C TZ=UTC
export PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1 PYTHONSAFEPATH=1
export GIT_ATTR_NOSYSTEM=1 GIT_OPTIONAL_LOCKS=0
unset BASH_ENV ENV CDPATH LD_AUDIT LD_LIBRARY_PATH LD_PRELOAD
unset PYTHONPATH PYTHONHOME PYTHONINSPECT PYTHONSTARTUP PYTHONWARNINGS
unset PYTHONBREAKPOINT PYTHONUSERBASE
unset GIT_DIR GIT_WORK_TREE GIT_COMMON_DIR GIT_INDEX_FILE
unset GIT_OBJECT_DIRECTORY GIT_ALTERNATE_OBJECT_DIRECTORIES
unset GIT_REPLACE_REF_BASE GIT_CONFIG GIT_CONFIG_COUNT GIT_CONFIG_PARAMETERS
unset GIT_NAMESPACE GIT_SHALLOW_FILE GIT_CEILING_DIRECTORIES GIT_DISCOVERY_ACROSS_FILESYSTEM
export GIT_CONFIG_NOSYSTEM=1
export GIT_CONFIG_GLOBAL=/dev/null
export GIT_CONFIG_SYSTEM=/dev/null

fail() {
  printf 'Runner signer role/scope authorization authority/resource decision v1 gate failed: %s\n' "$*" >&2
  exit 1
}

validation_tier="${1:-full-replay}"
[[ "$#" -le 1 ]] || fail "expected at most one validation tier"
case "${validation_tier}" in
  fast|full-replay) ;;
  *) fail "unknown validation tier: ${validation_tier}" ;;
esac

required_tools=(
  /usr/bin/awk /usr/bin/bash /usr/bin/cat /usr/bin/chmod /usr/bin/cmp
  /usr/bin/dirname /usr/bin/du /usr/bin/env /usr/bin/find /usr/bin/findmnt
  /usr/bin/git /usr/bin/grep /usr/bin/mkdir /usr/bin/mktemp /usr/bin/python3
  /usr/bin/rm /usr/bin/rmdir /usr/bin/sha256sum /usr/bin/sort /usr/bin/stat
  /usr/bin/tar
)
for tool in "${required_tools[@]}"; do
  [[ -x "${tool}" ]] || {
    printf 'Runner signer role/scope authorization authority/resource decision v1 gate missing tool: %s\n' "${tool}" >&2
    exit 2
  }
done

cd "$(/usr/bin/dirname "${BASH_SOURCE[0]}")/.."
repo_root="$(builtin pwd -P)"
[[ "${repo_root}" == /* && "${repo_root}" != "*" && "${repo_root}" != *$'\n'* \
  && -d "${repo_root}" && ! -L "${repo_root}" ]] \
  || fail "repository root is not an exact canonical directory"

baseline_commit="7df72e2d49bbc25580d4dcb63bc1a183120bba77"
frozen_baseline_tree="7fc4786b814d81d97e8672bcae484c07e180f04a"
frozen_baseline_parents="2707996e0616885fa51da9b908764f017a67299f 2a26de5b99886922240350fadefa07bc8f4c5dcd"
predecessor_integration_commit="7df72e2d49bbc25580d4dcb63bc1a183120bba77"
predecessor_integration_first_parent="2707996e0616885fa51da9b908764f017a67299f"
predecessor_integration_tree="7fc4786b814d81d97e8672bcae484c07e180f04a"
predecessor_source_commit="2a26de5b99886922240350fadefa07bc8f4c5dcd"
predecessor_source_parent="61585e655f7bfd537f8a123141e4e39a590a66d8"
predecessor_source_tree="596c6b7d8bdf18b844c6e24a664213fc23fd9772"

predecessor_gate="scripts/check-biocortex-ab-track-b-reference-provider-fault-injection-runner-bootstrap-trust-authentication-synthetic-trust-chain-exact-key-version-declared-role-and-revocation-verifier-isolated-lab-v1-pack.sh"
predecessor_expected="scripts/eval/fixtures/biocortex_ab_track_b_reference_provider_fault_injection_runner_bootstrap_trust_authentication_synthetic_trust_chain_exact_key_version_declared_role_and_revocation_verifier_isolated_lab_v1_pack.expected.v0.tsv"
t06_semantic_fixture="scripts/eval/fixtures/biocortex_ab_track_b_reference_provider_fault_injection_runner_runtime_prerequisite_evidence_packet_offline_integration_and_production_evidence_ingestion_boundary_review_v1_pack_synthetic_v0.json"
frozen_predecessor_gate_sha256="aaa66cd7b2045571a766839aea8e2f269bbaab9c15ba7607da0d57fe253fb061"
frozen_predecessor_fast_stdout_sha256="3881e2fbeacfa584098233cae7f7b8cbb56e4f5abb6d7dfb7c75fc59420b7f1b"
frozen_predecessor_full_stdout_sha256="baf76dca1f7ff58da7c352665b88ef39503a5765d102f885d29777a3c7d1e0ed"
frozen_t06_semantic_fixture_sha256="3aee2bc2f27290e9a57789d434f4373609b720f7ee1d963871fd99a613f55ff6"

source_path="scripts/eval/biocortex_ab_track_b_reference_provider_fault_injection_runner_signer_role_scope_authorization_isolated_lab_implementation_authority_and_resource_binding_decision_v1.py"
checker_path="scripts/eval/check_biocortex_ab_track_b_reference_provider_fault_injection_runner_signer_role_scope_authorization_isolated_lab_implementation_authority_and_resource_binding_decision_v1_pack.py"
fixture_path="scripts/eval/fixtures/biocortex_ab_track_b_reference_provider_fault_injection_runner_signer_role_scope_authorization_isolated_lab_implementation_authority_and_resource_binding_decision_v1_pack_owner_decision_v0.json"
expected_path="scripts/eval/fixtures/biocortex_ab_track_b_reference_provider_fault_injection_runner_signer_role_scope_authorization_isolated_lab_implementation_authority_and_resource_binding_decision_v1_pack.expected.v0.tsv"
manifest_path="scripts/eval/fixtures/biocortex_ab_track_b_reference_provider_fault_injection_runner_signer_role_scope_authorization_isolated_lab_implementation_authority_and_resource_binding_decision_v1_pack_v0.json"
report_path="docs/reports/goal-c-u/2026-07-18-biocortex-track-b-reference-provider-fault-injection-runner-signer-role-scope-authorization-isolated-lab-implementation-authority-and-resource-binding-decision-v1-pack.md"
gate_path="scripts/check-biocortex-ab-track-b-reference-provider-fault-injection-runner-signer-role-scope-authorization-isolated-lab-implementation-authority-and-resource-binding-decision-v1-pack.sh"

packet_paths=(
  "${source_path}" "${checker_path}" "${fixture_path}" "${expected_path}"
  "${manifest_path}" "${report_path}" "${gate_path}"
)
packet_modes=(100644 100644 100644 100644 100644 100644 100755)
predecessor_paths=(
  "docs/design/fixtures/biocortex-ab-track-b-reference-provider-fault-injection-runner-bootstrap-trust-authentication-isolated-lab-v1.schema.json"
  "scripts/eval/biocortex_ab_track_b_reference_provider_fault_injection_runner_bootstrap_trust_authentication_synthetic_trust_chain_exact_key_version_declared_role_and_revocation_verifier_isolated_lab_v1.py"
  "scripts/eval/check_biocortex_ab_track_b_reference_provider_fault_injection_runner_bootstrap_trust_authentication_synthetic_trust_chain_exact_key_version_declared_role_and_revocation_verifier_isolated_lab_v1_pack.py"
  "scripts/eval/fixtures/biocortex_ab_track_b_reference_provider_fault_injection_runner_bootstrap_trust_authentication_synthetic_trust_chain_exact_key_version_declared_role_and_revocation_verifier_isolated_lab_v1_pack_synthetic_v0.json"
  "${predecessor_expected}"
  "scripts/eval/fixtures/biocortex_ab_track_b_reference_provider_fault_injection_runner_bootstrap_trust_authentication_synthetic_trust_chain_exact_key_version_declared_role_and_revocation_verifier_isolated_lab_v1_pack_v0.json"
  "docs/reports/goal-c-u/2026-07-17-biocortex-track-b-reference-provider-fault-injection-runner-bootstrap-trust-authentication-synthetic-trust-chain-exact-key-version-declared-role-and-revocation-verifier-isolated-lab-v1-pack.md"
  "${predecessor_gate}"
)
predecessor_raw_sha256=(
  "d078513da9cabad07fb000485fdcb663ede13993341917d56792a8a1c909901c"
  "f483200c34ab570b3da8f45d6e4d0adb8e382f5d6fa815112a2c0b62c0431341"
  "bcfe18cb20733392fb4f494e9783ca99d90afc52429024f2f88cfd2163d29e20"
  "31959b02f20278d126be3a7e18e44e220b47cffb41804f69e3ace5c93277923e"
  "0085ddde9579cfaa0050cd71c07bc26fd0dc34d2c144400ad16535dd480aaa36"
  "bd0cca68c7edf8d992a7ec27cb4c700cd97cf61c4a2557ad56aca5f996a6744b"
  "9da0b11bfc86011ca792a6c0b2836c53c55837c17ac680296f5ad595b1a32ef0"
  "aaa66cd7b2045571a766839aea8e2f269bbaab9c15ba7607da0d57fe253fb061"
)
dependency_paths=("${predecessor_paths[@]}" "${t06_semantic_fixture}")
dependency_raw_sha256=("${predecessor_raw_sha256[@]}" "${frozen_t06_semantic_fixture_sha256}")

frozen_source_sha256="3cd07ed34e3aa9a9b6933ccba69a2da1f20c302c5e7f510f13e539b326f16db5"
frozen_checker_sha256="18cb9e5d8eb63c5bbc0d930035923504b9a3efb89df67dbbf5741aba3cbc10e7"
frozen_fixture_sha256="ba9bf671ec4985c14089e6e68b0bda5a09c0b4b09df1582ba6b8305f5fee4ee6"
frozen_expected_sha256="6da905a6d05660647ba92b9acf1d494fa277f66bc31b6d0afa07faef9e9e7d45"
frozen_manifest_sha256="95185cd5a0f7f7fc1b49c1ac92c17cdd6b90dddcf3d00b9251e3ae7832bb8f82"
frozen_report_sha256="c92c8ab419ab1aa937b00b358bebb7e66ba6ac7d205de863d7cc32813b855d25"
frozen_normal_stdout_sha256="6da905a6d05660647ba92b9acf1d494fa277f66bc31b6d0afa07faef9e9e7d45"
frozen_self_test_stdout_sha256="551930dae5673ab8c70147f0e7d2a300cf6e9ebda424086413d7ef07448ddf3b"

for unresolved_digest in \
  "${frozen_predecessor_fast_stdout_sha256}" \
  "${frozen_predecessor_full_stdout_sha256}" \
  "${frozen_source_sha256}" "${frozen_checker_sha256}" \
  "${frozen_fixture_sha256}" "${frozen_expected_sha256}" \
  "${frozen_manifest_sha256}" "${frozen_report_sha256}" \
  "${frozen_normal_stdout_sha256}" "${frozen_self_test_stdout_sha256}"; do
  [[ "${unresolved_digest}" != __FILL_*__ ]] \
    || fail "unresolved frozen SHA-256 placeholder: ${unresolved_digest}"
  [[ "${unresolved_digest}" =~ ^[0-9a-f]{64}$ ]] \
    || fail "malformed frozen SHA-256 value"
done

git_clean() {
  /usr/bin/git --no-pager --no-replace-objects -c core.fsmonitor=false \
    -c core.attributesFile=/dev/null -c core.commitGraph=false \
    -c core.hooksPath=/dev/null -c safe.directory="${repo_root}" "$@"
}

[[ "$(git_clean config --get-all safe.directory)" == "${repo_root}" ]] \
  || fail "Git trust scope is not the exact repository root"
head_oid="$(git_clean rev-parse HEAD)" || fail "cannot resolve HEAD"
[[ "$(git_clean rev-parse --is-shallow-repository)" == false ]] \
  || fail "shallow history is not admissible"
[[ -z "$(git_clean for-each-ref --format='%(refname)' refs/replace)" ]] \
  || fail "Git replace refs are present"
for commit in "${baseline_commit}" "${predecessor_integration_commit}" \
  "${predecessor_integration_first_parent}" "${predecessor_source_commit}" \
  "${predecessor_source_parent}"; do
  [[ "$(git_clean cat-file -t "${commit}")" == commit ]] \
    || fail "frozen commit is unavailable: ${commit}"
done
[[ "$(git_clean show -s --format='%T' "${baseline_commit}")" == "${frozen_baseline_tree}" ]] \
  || fail "baseline tree drift"
[[ "$(git_clean show -s --format='%P' "${baseline_commit}")" == "${frozen_baseline_parents}" ]] \
  || fail "baseline parent topology drift"
[[ "${baseline_commit}" == "${predecessor_integration_commit}" ]] \
  || fail "baseline is not the exact T05 verifier predecessor integration"
[[ "$(git_clean show -s --format='%T' "${predecessor_integration_commit}")" \
  == "${predecessor_integration_tree}" ]] || fail "predecessor integration tree drift"
[[ "$(git_clean show -s --format='%P' "${predecessor_integration_commit}")" \
  == "${predecessor_integration_first_parent} ${predecessor_source_commit}" ]] \
  || fail "predecessor integration topology drift"
[[ "$(git_clean show -s --format='%T' "${predecessor_source_commit}")" \
  == "${predecessor_source_tree}" ]] || fail "predecessor source tree drift"
[[ "$(git_clean show -s --format='%P' "${predecessor_source_commit}")" \
  == "${predecessor_source_parent}" ]] || fail "predecessor source topology drift"

common_dir="$(git_clean rev-parse --path-format=absolute --git-common-dir)" \
  || fail "cannot resolve Git common directory"
git_dir="$(git_clean rev-parse --path-format=absolute --git-dir)" \
  || fail "cannot resolve Git directory"
[[ -d "${common_dir}" && ! -L "${common_dir}" && -d "${git_dir}" && ! -L "${git_dir}" ]] \
  || fail "Git directory lineage is invalid"
case "${git_dir}" in
  "${common_dir}"|"${common_dir}"/worktrees/*) ;;
  *) fail "Git directory is outside the common-directory lineage" ;;
esac
[[ ! -e "${common_dir}/info/grafts" && ! -L "${common_dir}/info/grafts" ]] \
  || fail "legacy graft metadata is present"
[[ ! -e "${common_dir}/info/attributes" && ! -L "${common_dir}/info/attributes" ]] \
  || fail "common info attributes are not admissible"
[[ ! -e "${common_dir}/objects/info/alternates" \
  && ! -L "${common_dir}/objects/info/alternates" ]] \
  || fail "alternate object stores are not admissible"
while IFS= read -r config_key; do
  case "${config_key,,}" in
    filter.*|diff.*|merge.*|core.attributesfile|include.*|includeif.*)
      fail "executable or external Git configuration is not admissible: ${config_key}"
      ;;
  esac
done < <(git_clean config --local --includes --name-only --list)
[[ -z "$(/usr/bin/find . -name .gitattributes -print -quit)" ]] \
  || fail "working-tree .gitattributes files are not admissible"
[[ -z "$(git_clean status --porcelain=v1 --untracked-files=all)" ]] \
  || fail "worktree or index is not clean"

tmp_base="/Data/CascadeProjects/.ab-gate-tmp"
tmp_base_created=false
if [[ ! -e "${tmp_base}" ]]; then
  /usr/bin/mkdir -m 0700 "${tmp_base}"
  tmp_base_created=true
fi
[[ -d "${tmp_base}" && ! -L "${tmp_base}" \
  && "$(cd "${tmp_base}" && builtin pwd -P)" == "${tmp_base}" \
  && "$(/usr/bin/stat -c '%F' "${tmp_base}")" == directory \
  && "$(/usr/bin/stat -c '%u' "${tmp_base}")" == "${EUID}" \
  && "$(/usr/bin/stat -c '%a' "${tmp_base}")" == 700 ]] \
  || fail "gate scratch root owner, mode, type, or canonical path drift"
scratch_fstype="$(/usr/bin/findmnt -T "${tmp_base}" -n -o FSTYPE)" \
  || fail "cannot resolve gate scratch filesystem"
case "${scratch_fstype,,}" in
  tmpfs|fuse*) fail "gate scratch requires a persistent non-FUSE POSIX filesystem" ;;
esac
tmp="$(/usr/bin/mktemp -d "${tmp_base}/runner-signer-role-scope-auth-decision-v1.XXXXXX")"
[[ -d "${tmp}" && ! -L "${tmp}" \
  && "$(/usr/bin/stat -c '%u' "${tmp}")" == "${EUID}" \
  && "$(/usr/bin/stat -c '%a' "${tmp}")" == 700 ]] \
  || fail "private gate scratch directory owner or mode drift"
cleanup() {
  /usr/bin/chmod -R u+w "${tmp}" 2>/dev/null || true
  /usr/bin/rm -rf "${tmp}" 2>/dev/null || true
  if [[ "${tmp_base_created}" == true ]]; then
    /usr/bin/rmdir "${tmp_base}" 2>/dev/null || true
  fi
}
trap cleanup EXIT
/usr/bin/mkdir -m 0700 "${tmp}/home" "${tmp}/artifact-archive"

private_scratch_checkpoint_cap_bytes=67108864
check_private_scratch_checkpoint() {
  local scratch_bytes
  scratch_bytes="$(/usr/bin/du -sb -- "${tmp}" | /usr/bin/awk '{print $1}')"
  [[ "${scratch_bytes}" =~ ^[0-9]+$ ]] || fail "cannot measure private scratch checkpoint"
  [[ "${scratch_bytes}" -le "${private_scratch_checkpoint_cap_bytes}" ]] \
    || fail "private scratch checkpoint exceeds ${private_scratch_checkpoint_cap_bytes} bytes"
}

[[ "${#packet_paths[@]}" == 7 && "${#packet_modes[@]}" == 7 ]] \
  || fail "successor seven-path catalog cardinality drift"
[[ "${#predecessor_paths[@]}" == 8 && "${#predecessor_raw_sha256[@]}" == 8 ]] \
  || fail "T05 predecessor eight-path/hash catalog cardinality drift"
[[ "${#dependency_paths[@]}" == 9 && "${#dependency_raw_sha256[@]}" == 9 ]] \
  || fail "T05 plus T06 dependency catalog cardinality drift"
printf '%s\n' "${packet_paths[@]}" "${dependency_paths[@]}" \
  | /usr/bin/sort >"${tmp}/protected-paths"
[[ "$(/usr/bin/awk 'END {print NR}' "${tmp}/protected-paths")" == 16 \
  && "$(/usr/bin/sort -u "${tmp}/protected-paths" | /usr/bin/awk 'END {print NR}')" == 16 ]] \
  || fail "protected path cardinality or uniqueness drift"

: >"${tmp}/predecessor-paths"
for path in "${predecessor_paths[@]}"; do printf '%s\n' "${path}" >>"${tmp}/predecessor-paths"; done
/usr/bin/sort "${tmp}/predecessor-paths" >"${tmp}/predecessor-paths.sorted"
/usr/bin/awk '{print "A\t" $0}' "${tmp}/predecessor-paths.sorted" \
  >"${tmp}/expected-predecessor-delta"
git_clean diff-tree --no-commit-id --name-status -r \
  "${predecessor_source_parent}" "${predecessor_source_commit}" \
  | LC_ALL=C /usr/bin/sort >"${tmp}/actual-predecessor-source-delta"
/usr/bin/cmp -s "${tmp}/expected-predecessor-delta" \
  "${tmp}/actual-predecessor-source-delta" \
  || fail "predecessor source is not the exact eight-path all-add delta"
git_clean diff-tree --no-commit-id --name-status -r \
  "${predecessor_integration_first_parent}" "${predecessor_integration_commit}" \
  | LC_ALL=C /usr/bin/sort >"${tmp}/actual-predecessor-integration-delta"
/usr/bin/cmp -s "${tmp}/expected-predecessor-delta" \
  "${tmp}/actual-predecessor-integration-delta" \
  || fail "predecessor integration first-parent delta drift"

head_lineage=()
IFS=' ' read -r -a head_lineage < <(git_clean rev-list --parents -n 1 "${head_oid}") \
  || fail "cannot resolve HEAD topology"
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
  IFS=' ' read -r -a source_lineage < <(git_clean rev-list --parents -n 1 "${source_commit}") \
    || fail "cannot resolve source topology"
  source_parents=("${source_lineage[@]:1}")
  [[ "${#source_parents[@]}" == 1 && "${source_parents[0]}" == "${baseline_commit}" ]] \
    || fail "integrated second parent is not the exact source shape"
  git_clean merge-base --is-ancestor "${baseline_commit}" "${first_parent}" \
    || fail "integrated first parent does not descend from baseline"
  if git_clean merge-base --is-ancestor "${source_commit}" "${first_parent}"; then
    fail "integrated first parent already contains source"
  else
    merge_base_status=$?
    [[ "${merge_base_status}" == 1 ]] || fail "cannot establish source exclusion"
  fi
else
  fail "HEAD is neither exact source nor ordinary two-parent integration"
fi
if [[ "${validation_tier}" == full-replay && "${mode}" != integrated ]]; then
  fail "full replay is release evidence and is permitted only on ordinary integration"
fi

: >"${tmp}/expected-paths"
for path in "${packet_paths[@]}"; do printf '%s\n' "${path}" >>"${tmp}/expected-paths"; done
git_clean diff-tree --no-commit-id --name-status -r "${baseline_commit}" "${source_commit}" \
  | LC_ALL=C /usr/bin/sort >"${tmp}/actual-source-delta"
/usr/bin/awk '{print "A\t" $0}' "${tmp}/expected-paths" \
  | LC_ALL=C /usr/bin/sort >"${tmp}/expected-source-delta"
/usr/bin/cmp -s "${tmp}/expected-source-delta" "${tmp}/actual-source-delta" \
  || fail "source is not the exact seven-path all-add delta"
if [[ "${mode}" == integrated ]]; then
  git_clean diff-tree --no-commit-id --name-status -r "${first_parent}" "${head_oid}" \
    | LC_ALL=C /usr/bin/sort >"${tmp}/actual-integrated-delta"
  /usr/bin/cmp -s "${tmp}/expected-source-delta" "${tmp}/actual-integrated-delta" \
    || fail "integrated first-parent delta is not the exact packet"
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
  [[ -f "${path}" && "$(/usr/bin/stat -c '%F' -- "${path}")" == "regular file" \
    && "$(/usr/bin/stat -c '%h' -- "${path}")" == 1 ]] \
    || fail "protected path type or link count drift: ${path}"
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
    || fail "nondefault index flag: ${path}"
  /usr/bin/cmp -s "${path}" <(git_clean cat-file blob "${source_object}") \
    || fail "worktree/source byte drift: ${path}"
done

for index in "${!dependency_paths[@]}"; do
  path="${dependency_paths[$index]}"
  expected_dependency_sha256="${dependency_raw_sha256[$index]}"
  expected_dependency_mode=100644
  [[ "${path}" != "${predecessor_gate}" ]] || expected_dependency_mode=100755
  reject_symlink_components "${path}"
  [[ -f "${path}" && ! -L "${path}" \
    && "$(/usr/bin/stat -c '%F' -- "${path}")" == "regular file" \
    && "$(/usr/bin/stat -c '%h' -- "${path}")" == 1 ]] \
    || fail "dependency path type or link-count drift: ${path}"
  read -r dependency_index_mode dependency_index_object dependency_index_stage dependency_indexed \
    < <(git_clean ls-files --stage -- "${path}") \
    || fail "cannot resolve dependency index identity: ${path}"
  read -r predecessor_mode predecessor_type predecessor_object predecessor_indexed \
    < <(git_clean ls-tree "${predecessor_integration_commit}" -- "${path}") \
    || fail "cannot resolve predecessor dependency identity: ${path}"
  read -r baseline_mode baseline_type baseline_object baseline_indexed \
    < <(git_clean ls-tree "${baseline_commit}" -- "${path}") \
    || fail "cannot resolve baseline dependency identity: ${path}"
  read -r dependency_source_mode dependency_source_type dependency_source_object dependency_source_indexed \
    < <(git_clean ls-tree "${source_commit}" -- "${path}") \
    || fail "cannot resolve source dependency identity: ${path}"
  read -r dependency_head_mode dependency_head_type dependency_head_object dependency_head_indexed \
    < <(git_clean ls-tree "${head_oid}" -- "${path}") \
    || fail "cannot resolve HEAD dependency identity: ${path}"
  [[ "${dependency_index_mode}" == "${expected_dependency_mode}" \
    && "${predecessor_mode}" == "${expected_dependency_mode}" \
    && "${baseline_mode}" == "${expected_dependency_mode}" \
    && "${dependency_source_mode}" == "${expected_dependency_mode}" \
    && "${dependency_head_mode}" == "${expected_dependency_mode}" \
    && "${dependency_index_stage}" == 0 \
    && "${predecessor_type}" == blob && "${baseline_type}" == blob \
    && "${dependency_source_type}" == blob && "${dependency_head_type}" == blob \
    && "${dependency_indexed}" == "${path}" && "${predecessor_indexed}" == "${path}" \
    && "${baseline_indexed}" == "${path}" && "${dependency_source_indexed}" == "${path}" \
    && "${dependency_head_indexed}" == "${path}" \
    && "${dependency_index_object}" == "${predecessor_object}" \
    && "${baseline_object}" == "${predecessor_object}" \
    && "${dependency_source_object}" == "${predecessor_object}" \
    && "${dependency_head_object}" == "${predecessor_object}" ]] \
    || fail "frozen predecessor or T06 semantic dependency identity drift: ${path}"
  [[ "$(git_clean ls-files -v -- "${path}")" == "H ${path}" ]] \
    || fail "nondefault dependency index flag: ${path}"
  /usr/bin/cmp -s "${path}" <(git_clean cat-file blob "${predecessor_object}") \
    || fail "worktree/predecessor dependency byte drift: ${path}"
  [[ "$(/usr/bin/sha256sum "${path}" | /usr/bin/awk '{print $1}')" \
    == "${expected_dependency_sha256}" ]] \
    || fail "frozen predecessor or T06 semantic dependency raw hash drift: ${path}"
done
[[ "$(/usr/bin/sha256sum "${predecessor_gate}" | /usr/bin/awk '{print $1}')" \
  == "${frozen_predecessor_gate_sha256}" ]] || fail "frozen predecessor gate raw hash drift"

archive_paths=("${packet_paths[@]}" "${dependency_paths[@]}")
git_clean archive --format=tar "${source_commit}" -- "${archive_paths[@]}" \
  | /usr/bin/tar -x -C "${tmp}/artifact-archive"
[[ -z "$(/usr/bin/find "${tmp}/artifact-archive" -type l -print -quit)" ]] \
  || fail "artifact archive contains a symlink"
[[ -z "$(/usr/bin/find "${tmp}/artifact-archive" -type f -links +1 -print -quit)" ]] \
  || fail "artifact archive contains a hardlinked file"
for index in "${!dependency_paths[@]}"; do
  path="${dependency_paths[$index]}"
  expected_dependency_sha256="${dependency_raw_sha256[$index]}"
  [[ "$(/usr/bin/sha256sum "${tmp}/artifact-archive/${path}" | /usr/bin/awk '{print $1}')" \
    == "${expected_dependency_sha256}" ]] \
    || fail "archive predecessor or T06 semantic dependency raw hash drift: ${path}"
done
check_private_scratch_checkpoint

/usr/bin/env -i PATH="${PATH}" HOME="${tmp}/home" LC_ALL=C TZ=UTC \
  PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1 PYTHONSAFEPATH=1 PYTHONHASHSEED=0 \
  /usr/bin/python3 -S -P - "${tmp}/artifact-archive/${t06_semantic_fixture}" <<'PY'
import json
import sys

def reject_duplicate(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result

with open(sys.argv[1], "r", encoding="utf-8") as handle:
    document = json.load(
        handle,
        object_pairs_hook=reject_duplicate,
        parse_float=lambda _value: (_ for _ in ()).throw(ValueError("float forbidden")),
        parse_constant=lambda _value: (_ for _ in ()).throw(ValueError("constant forbidden")),
    )
if document.get("schema") != (
    "agent_bridge.biocortex_ab_track_b_reference_provider_fault_injection_runner_"
    "runtime_prerequisite_evidence_packet_offline_integration_and_production_"
    "evidence_ingestion_boundary_review_v1.synthetic.v0"
):
    raise SystemExit("T06 semantic schema drift")
if document.get("synthetic_only") is not True:
    raise SystemExit("T06 semantic fixture is not synthetic-only")
controls = [
    row for row in document.get("production_ingestion_controls", [])
    if row.get("control_id") == "SIGNER_ROLE_SCOPE_AUTHORIZATION"
]
threats = [row for row in document.get("threat_cases", []) if row.get("case_id") == "T06"]
expected_control = {
    "control_id": "SIGNER_ROLE_SCOPE_AUTHORIZATION",
    "implemented": False,
    "mandatory_check": (
        "Authorize signer identity to the exact owner class, evidence class, "
        "track, subject, audience, and nonce scope."
    ),
    "primary_failure_code": "E_PRODUCTION_SIGNER_AUTHORIZATION_FAILED",
    "required_future_artifact": (
        "Signer authorization registry scoped to owner class, evidence class, "
        "track, and subject."
    ),
    "runtime_exercised": False,
    "satisfiable_by_offline": False,
    "stage_ordinal": 4,
}
expected_threat = {
    "case_id": "T06",
    "expected_disposition": "REJECTED_FAIL_CLOSED",
    "expected_reason_code": "E_PRODUCTION_SIGNER_AUTHORIZATION_FAILED",
    "mutation": (
        "Signer role is not authorized for owner class, evidence class, track, "
        "or subject"
    ),
    "threat_class": "AUTHORIZATION",
}
if len(document.get("production_ingestion_controls", [])) != 14 or controls != [expected_control]:
    raise SystemExit("T06 authorization control semantics drift")
if len(document.get("threat_cases", [])) != 20 or threats != [expected_threat]:
    raise SystemExit("T06 threat semantics drift")
PY

verify_hash() {
  local label="$1" expected="$2" path="$3" actual
  actual="$(/usr/bin/sha256sum "${tmp}/artifact-archive/${path}" | /usr/bin/awk '{print $1}')"
  [[ "${actual}" == "${expected}" ]] || fail "${label} SHA-256 drift: ${path}"
}
verify_hash source "${frozen_source_sha256}" "${source_path}"
verify_hash checker "${frozen_checker_sha256}" "${checker_path}"
verify_hash fixture "${frozen_fixture_sha256}" "${fixture_path}"
verify_hash expected "${frozen_expected_sha256}" "${expected_path}"
verify_hash manifest "${frozen_manifest_sha256}" "${manifest_path}"
verify_hash report "${frozen_report_sha256}" "${report_path}"

for seed in 0 314159; do
  /usr/bin/env -i PATH="${PATH}" HOME="${tmp}/home" LC_ALL=C TZ=UTC \
    PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1 PYTHONSAFEPATH=1 \
    PYTHONHASHSEED="${seed}" \
    /usr/bin/python3 -S -P "${tmp}/artifact-archive/${checker_path}" \
      >"${tmp}/source-${seed}.stdout"
  [[ "$(/usr/bin/sha256sum "${tmp}/source-${seed}.stdout" | /usr/bin/awk '{print $1}')" \
    == "${frozen_normal_stdout_sha256}" ]] \
    || fail "source checker drift for hash seed ${seed}"
done
/usr/bin/cmp -s "${tmp}/source-0.stdout" "${tmp}/artifact-archive/${expected_path}" \
  || fail "source checker output is not the exact frozen TSV"
/usr/bin/env -i PATH="${PATH}" HOME="${tmp}/home" LC_ALL=C TZ=UTC \
  PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1 PYTHONSAFEPATH=1 PYTHONHASHSEED=7 \
  /usr/bin/python3 -S -P "${tmp}/artifact-archive/${checker_path}" --self-test \
    >"${tmp}/source-self-test.stdout"
[[ "$(/usr/bin/sha256sum "${tmp}/source-self-test.stdout" | /usr/bin/awk '{print $1}')" \
  == "${frozen_self_test_stdout_sha256}" ]] || fail "source self-test checker drift"
if [[ "${mode}" == integrated ]]; then
  /usr/bin/env -i PATH="${PATH}" HOME="${tmp}/home" LC_ALL=C TZ=UTC \
    PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1 PYTHONSAFEPATH=1 PYTHONHASHSEED=2718 \
    /usr/bin/python3 -S -P "${tmp}/artifact-archive/${checker_path}" \
      >"${tmp}/integrated.stdout"
  /usr/bin/cmp -s "${tmp}/source-0.stdout" "${tmp}/integrated.stdout" \
    || fail "integrated checker drift"
fi

[[ "$(/usr/bin/grep -Fxc -- '## Artifact binding' "${tmp}/artifact-archive/${report_path}")" == 1 ]] \
  || fail "report lacks exact-once Artifact binding heading"
for path in "${source_path}" "${checker_path}" "${fixture_path}" \
  "${expected_path}" "${manifest_path}"; do
  digest="$(/usr/bin/sha256sum "${tmp}/artifact-archive/${path}" | /usr/bin/awk '{print $1}')"
  [[ "$(/usr/bin/grep -Foc -- "${digest}" "${tmp}/artifact-archive/${report_path}")" == 1 ]] \
    || fail "report does not bind exact artifact hash: ${path}"
done
for index in "${!dependency_paths[@]}"; do
  path="${dependency_paths[$index]}"
  digest="${dependency_raw_sha256[$index]}"
  [[ "$(/usr/bin/grep -Foc -- "${digest}" "${tmp}/artifact-archive/${report_path}")" -ge 1 ]] \
    || fail "report does not bind frozen predecessor or T06 semantic hash: ${path}"
done

predecessor_repo="${tmp}/predecessor-repo"
if ! git_clean clone --no-local --no-hardlinks --no-checkout --no-tags --single-branch \
  -- . "${predecessor_repo}" >"${tmp}/clone.stdout" 2>"${tmp}/clone.stderr"; then
  /usr/bin/cat "${tmp}/clone.stderr" >&2
  fail "cannot clone isolated predecessor repository"
fi
check_private_scratch_checkpoint
/usr/bin/git --no-pager --no-replace-objects -c safe.directory="${predecessor_repo}" \
  -C "${predecessor_repo}" sparse-checkout init --cone \
  >"${tmp}/sparse-init.stdout" 2>"${tmp}/sparse-init.stderr" \
  || { /usr/bin/cat "${tmp}/sparse-init.stderr" >&2; fail "cannot initialize predecessor sparse checkout"; }
/usr/bin/git --no-pager --no-replace-objects -c safe.directory="${predecessor_repo}" \
  -C "${predecessor_repo}" sparse-checkout set \
    scripts docs/reports/goal-c-u docs/design/fixtures \
  >"${tmp}/sparse-set.stdout" 2>"${tmp}/sparse-set.stderr" \
  || { /usr/bin/cat "${tmp}/sparse-set.stderr" >&2; fail "cannot bind predecessor sparse paths"; }
/usr/bin/git --no-pager --no-replace-objects -c safe.directory="${predecessor_repo}" \
  -C "${predecessor_repo}" checkout --detach "${predecessor_integration_commit}" \
  >"${tmp}/checkout.stdout" 2>"${tmp}/checkout.stderr" \
  || { /usr/bin/cat "${tmp}/checkout.stderr" >&2; fail "cannot checkout predecessor"; }
[[ "$(/usr/bin/git -c safe.directory="${predecessor_repo}" -C "${predecessor_repo}" rev-parse HEAD)" \
  == "${predecessor_integration_commit}" ]] || fail "isolated predecessor HEAD drift"
[[ -z "$(/usr/bin/git -c safe.directory="${predecessor_repo}" -C "${predecessor_repo}" \
  status --porcelain=v1 --untracked-files=all)" ]] \
  || fail "isolated predecessor is dirty before replay"
check_private_scratch_checkpoint
read -r cloned_gate_mode cloned_gate_object cloned_gate_stage cloned_gate_path \
  < <(/usr/bin/git -c safe.directory="${predecessor_repo}" -C "${predecessor_repo}" \
    ls-files --stage -- "${predecessor_gate}") \
  || fail "cannot resolve isolated predecessor gate index identity"
[[ "${cloned_gate_mode}" == 100755 && "${cloned_gate_stage}" == 0 \
  && "${cloned_gate_path}" == "${predecessor_gate}" \
  && -f "${predecessor_repo}/${predecessor_gate}" \
  && ! -L "${predecessor_repo}/${predecessor_gate}" \
  && -x "${predecessor_repo}/${predecessor_gate}" \
  && "$(/usr/bin/stat -c '%F' "${predecessor_repo}/${predecessor_gate}")" == "regular file" \
  && "$(/usr/bin/stat -c '%h' "${predecessor_repo}/${predecessor_gate}")" == 1 \
  && "$(/usr/bin/sha256sum "${predecessor_repo}/${predecessor_gate}" | /usr/bin/awk '{print $1}')" \
    == "${frozen_predecessor_gate_sha256}" ]] \
  || fail "isolated predecessor gate index mode, type, executability, or raw hash drift"

predecessor_full_replay=false
predecessor_authorization_consumption_verified=false
expected_predecessor_stdout_sha256="${frozen_predecessor_fast_stdout_sha256}"
expected_predecessor_line_count=95
if [[ "${validation_tier}" == full-replay ]]; then
  predecessor_full_replay=true
  expected_predecessor_stdout_sha256="${frozen_predecessor_full_stdout_sha256}"
  expected_predecessor_line_count=96
fi
# Invoke the frozen gate directly. It owns its deeper replay/isolation model;
# an outer namespace would create unsupported nesting and duplicate resources.
if ! "${predecessor_repo}/${predecessor_gate}" "${validation_tier}" \
  >"${tmp}/predecessor.stdout" 2>"${tmp}/predecessor.stderr"; then
  /usr/bin/cat "${tmp}/predecessor.stderr" >&2
  fail "predecessor ${validation_tier} replay failed"
fi
[[ ! -s "${tmp}/predecessor.stderr" ]] || fail "predecessor replay emitted stderr"
[[ "$(/usr/bin/awk 'END {print NR}' "${tmp}/predecessor.stdout")" \
  == "${expected_predecessor_line_count}" ]] || fail "predecessor stdout line-count drift"
[[ "$(/usr/bin/sha256sum "${tmp}/predecessor.stdout" | /usr/bin/awk '{print $1}')" \
  == "${expected_predecessor_stdout_sha256}" ]] || fail "predecessor stdout SHA-256 drift"

predecessor_tsv_lines="$(/usr/bin/awk 'END {print NR}' \
  "${predecessor_repo}/${predecessor_expected}")"
[[ "${predecessor_tsv_lines}" == 44 ]] || fail "predecessor TSV line-count drift"
/usr/bin/awk -v limit="${predecessor_tsv_lines}" 'NR <= limit {print}' \
  "${tmp}/predecessor.stdout" >"${tmp}/predecessor-prefix.tsv"
/usr/bin/cmp -s "${predecessor_repo}/${predecessor_expected}" \
  "${tmp}/predecessor-prefix.tsv" || fail "predecessor TSV prefix drift"
[[ "$(/usr/bin/grep -Fxc -- "mode"$'\t'"integrated" "${tmp}/predecessor.stdout")" == 1 ]] \
  || fail "predecessor mode receipt drift"
[[ "$(/usr/bin/grep -Fxc -- "source_commit"$'\t'"${predecessor_source_commit}" \
  "${tmp}/predecessor.stdout")" == 1 ]] || fail "predecessor source receipt drift"
[[ "$(/usr/bin/grep -Fxc -- "head"$'\t'"${predecessor_integration_commit}" \
  "${tmp}/predecessor.stdout")" == 1 ]] || fail "predecessor head receipt drift"
/usr/bin/awk -F '\t' '
  $1 == "upstream_supply_receipt_sha256" && length($2) == 64 && $2 !~ /[^0-9a-f]/ {count++}
  END {exit count == 1 ? 0 : 1}
' "${tmp}/predecessor.stdout" || fail "predecessor upstream supply receipt digest drift"

for field_value in \
  $'production_ingestion_controls_implemented\t0' \
  $'production_ingestion_controls_runtime_exercised\t0' \
  $'production_threat_specifications_runtime_exercised\t0' \
  $'real_evidence_items_present\t0' \
  $'runtime_prerequisites_satisfied\t0'; do
  [[ "$(/usr/bin/grep -Fxc -- "${field_value}" "${tmp}/predecessor.stdout")" == 2 ]] \
    || fail "predecessor duplicated TSV/footer boundary count drift: ${field_value}"
done
for field_value in \
  $'production_ingestion_control_count\t14' \
  $'production_validated_evidence_items\t0' \
  $'runtime_authority\tfalse' \
  $'provider_authority\tfalse' \
  $'side_effects_unlocked\tNONE' \
  $'component_state\tAUTHENTICATED_SYNTHETIC_KAT_AGAINST_FROZEN_BOOTSTRAP_TRUST_SNAPSHOT_COMPONENT_ONLY' \
  $'content_sha256\t899a27ce565d0a8159334513edba2c166b6b6d56f8b74587a6d5e89be6408715' \
  $'local_t05_specification_exercised\ttrue' \
  $'local_t06_specification_exercised\tfalse' \
  $'declared_role_is_scope_authorization\tfalse' \
  $'track_subject_binding_implemented\tfalse' \
  $'implementation_authority_replay_authorizes_another_successor\tfalse'; do
  [[ "$(/usr/bin/grep -Fxc -- "${field_value}" "${tmp}/predecessor.stdout")" == 1 ]] \
    || fail "predecessor exact-once boundary count drift: ${field_value}"
done

if [[ "${validation_tier}" == full-replay ]]; then
  for field_value in \
    $'integration_gate\tVALID_INTEGRATED_BIOCORTEX_AB_TRACK_B_BOOTSTRAP_TRUST_AUTHENTICATION_SYNTHETIC_VERIFIER_ISOLATED_LAB_V1_PACK' \
    $'gate\tPASS' \
    $'authorization_consumption_state\tCONSUMED_SCOPE_COMPLETE' \
    $'implementation_authority_single_use_consumed\ttrue' \
    $'upstream_implementation_authority_full_replay_verified\ttrue' \
    $'upstream_implementation_authority_effective_before_consumption\ttrue' \
    $'validation_tier\tPERIODIC_FULL_FROZEN_CHAIN_REPLAY' \
    $'periodic_full_replay_required\tfalse' \
    $'artifact_release_evidence\ttrue' \
    $'full_replay_gate\tVALID_BOOTSTRAP_TRUST_AUTHENTICATION_SYNTHETIC_VERIFIER_AND_FULL_FROZEN_SUPPLY_AUTHORITY_FRAME_CHAIN'; do
    [[ "$(/usr/bin/grep -Fxc -- "${field_value}" "${tmp}/predecessor.stdout")" == 1 ]] \
      || fail "predecessor full replay or consumed-authorization receipt drift: ${field_value}"
  done
  [[ "$(/usr/bin/grep -Fxc -- $'gate\tFAST_PASS_NON_RELEASE_CONTENT_IDENTITY_ONLY' \
    "${tmp}/predecessor.stdout")" == 0 ]] || fail "predecessor full replay contains fast gate marker"
  predecessor_authorization_consumption_verified=true
else
  for field_value in \
    $'gate\tFAST_PASS_NON_RELEASE_CONTENT_IDENTITY_ONLY' \
    $'authorization_consumption_state\tAUTHORIZED_BOOTSTRAP_TRUST_AUTHENTICATION_ISOLATED_LAB_EXACT_UNIT_PENDING_INTEGRATED_FULL_GATE' \
    $'implementation_authority_single_use_consumed\tfalse' \
    $'upstream_implementation_authority_full_replay_verified\tfalse' \
    $'upstream_implementation_authority_effective_before_consumption\tfalse' \
    $'validation_tier\tFAST_CONTENT_IDENTITY_AND_PREDECESSOR_FAST_REPLAY' \
    $'periodic_full_replay_required\ttrue' \
    $'artifact_release_evidence\tfalse' \
    $'fast_gate\tVALID_FAST_BOOTSTRAP_TRUST_AUTHENTICATION_SYNTHETIC_VERIFIER_AND_SUPPLY_CHAIN_IDENTITY'; do
    [[ "$(/usr/bin/grep -Fxc -- "${field_value}" "${tmp}/predecessor.stdout")" == 1 ]] \
      || fail "predecessor fast non-release receipt drift: ${field_value}"
  done
  [[ "$(/usr/bin/grep -Fxc -- $'gate\tPASS' "${tmp}/predecessor.stdout")" == 0 ]] \
    || fail "predecessor fast replay contains release gate marker"
  [[ "$(/usr/bin/grep -Fxc -- $'authorization_consumption_state\tCONSUMED_SCOPE_COMPLETE' \
    "${tmp}/predecessor.stdout")" == 0 ]] \
    || fail "predecessor fast replay claims consumed release authority"
fi
predecessor_receipt_sha256="$(/usr/bin/sha256sum "${tmp}/predecessor.stdout" | /usr/bin/awk '{print $1}')"
check_private_scratch_checkpoint
[[ -z "$(/usr/bin/git -c safe.directory="${predecessor_repo}" -C "${predecessor_repo}" \
  status --porcelain=v1 --untracked-files=all)" ]] \
  || fail "predecessor replay dirtied isolated repository"

git_clean diff --check "${baseline_commit}" "${source_commit}"
[[ "$(git_clean rev-parse HEAD)" == "${head_oid}" ]] || fail "HEAD changed during gate"
[[ -z "$(git_clean status --porcelain=v1 --untracked-files=all)" ]] \
  || fail "verification dirtied worktree or index"

source_result="$(/usr/bin/cat "${tmp}/source-0.stdout")"
/usr/bin/chmod -R u+w "${tmp}" || fail "cannot make scratch tree removable"
/usr/bin/rm -rf "${tmp}" || fail "cannot remove scratch tree"
if [[ "${tmp_base_created}" == true ]]; then
  /usr/bin/rmdir "${tmp_base}" 2>/dev/null || true
fi
trap - EXIT

printf '%s\n' "${source_result}"
if [[ "${validation_tier}" == full-replay ]]; then
  [[ "${predecessor_authorization_consumption_verified}" == true ]] \
    || fail "effective authority requires verified predecessor consumption"
  printf 'integration_gate\tVALID_INTEGRATED_BIOCORTEX_AB_TRACK_B_RUNNER_SIGNER_ROLE_SCOPE_AUTHORIZATION_ISOLATED_LAB_IMPLEMENTATION_AUTHORITY_AND_RESOURCE_BINDING_DECISION_V1_PACK\n'
  printf 'gate\tPASS\n'
  printf 'effective_authorization_state\tAUTHORIZED_SIGNER_ROLE_SCOPE_AUTHORIZATION_ISOLATED_LAB_EXACT_UNIT\n'
  printf 'signer_role_scope_authorization_implementation_authority_effective\ttrue\n'
  printf 'effective_implementation_authority_recorded\ttrue\n'
  printf 'effective_implementation_side_effects_unlocked\tREVERSIBLE_LOCAL_CODE_SCHEMA_TEST_DOCS_FOR_EXACT_NEXT_UNIT_ONLY\n'
  printf 'predecessor_authorization_consumption_state\tCONSUMED_SCOPE_COMPLETE\n'
else
  printf 'gate\tFAST_PASS_NON_RELEASE_CONTENT_IDENTITY_ONLY\n'
  printf 'effective_authorization_state\tUNRECORDED_NO_AUTHORITY_PENDING_DECISION_INTEGRATED_FULL_GATE\n'
  printf 'signer_role_scope_authorization_implementation_authority_effective\tfalse\n'
  printf 'effective_implementation_authority_recorded\tfalse\n'
  printf 'effective_implementation_side_effects_unlocked\tNONE\n'
  printf 'predecessor_authorization_consumption_state\tREQUIRES_INTEGRATED_FULL_REPLAY_VERIFICATION\n'
fi
printf 'implementation_authority_single_use_consumed\tfalse\n'
printf 'decision_full_gate_consumes_new_authority\tfalse\n'
printf 'implementation_authority_non_transitive\ttrue\n'
printf 'implementation_authority_subdelegation_authorized\tfalse\n'
printf 'global_single_use_proved\tfalse\n'
printf 'mode\t%s\n' "${mode}"
printf 'baseline_commit\t%s\n' "${baseline_commit}"
printf 'source_commit\t%s\n' "${source_commit}"
printf 'source_parent\t%s\n' "${baseline_commit}"
printf 'head\t%s\n' "${head_oid}"
printf 'head_tree\t%s\n' "$(git_clean show -s --format='%T' "${head_oid}")"
printf 'head_parents\t%s\n' "$(git_clean show -s --format='%P' "${head_oid}")"
printf 'packet_path_count\t7\n'
printf 'predecessor_receipt_sha256\t%s\n' "${predecessor_receipt_sha256}"
printf 'predecessor_full_replay\t%s\n' "${predecessor_full_replay}"
printf 'required_predecessor_authorization_consumption_state\tCONSUMED_SCOPE_COMPLETE\n'
printf 'predecessor_authorization_consumption_verified\t%s\n' "${predecessor_authorization_consumption_verified}"
printf 'decision_scope\tSIGNER_ROLE_SCOPE_AUTHORIZATION_ISOLATED_LAB_EXACT_UNIT_SINGLE_USE_NON_TRANSITIVE\n'
printf 'predecessor_packet_artifact_count\t8\n'
printf 't06_semantic_specification_artifact_count\t1\n'
printf 'dependency_artifact_count\t9\n'
printf 'protected_archive_path_count\t16\n'
printf 't06_semantic_specification_raw_sha256\t%s\n' "${frozen_t06_semantic_fixture_sha256}"
printf 't06_semantic_specification_verified\ttrue\n'
printf 'authorized_candidate_surface_component_count\t1\n'
printf 'authorized_local_threat_specifications\tT06\n'
printf 'bootstrap_trust_authentication_implemented\ttrue\n'
printf 'signer_role_scope_authorization_implemented\tfalse\n'
printf 'track_subject_binding_implemented\tfalse\n'
printf 'local_t06_specification_exercised\tfalse\n'
printf 'local_t07_specification_exercised\tfalse\n'
printf 'isolated_lab_predecessor_surface_components_implemented\t3\n'
printf 'local_predecessor_threat_specifications_covered\t5\n'
printf 'declared_role_is_scope_authorization\tfalse\n'
printf 'nonce_freshness_proved\tfalse\n'
printf 'nonce_replay_protection_proved\tfalse\n'
printf 'production_environment_implementation_authorized\tfalse\n'
printf 'owner_supplied_numeric_budget_cap\tfalse\n'
printf 'external_paid_spend_cap\t0\n'
printf 'provider_endpoint_count\t0\n'
printf 'credential_handle_count\t0\n'
printf 'credential_path_count\t0\n'
printf 'production_trust_root_count\t0\n'
printf 'production_signer_count\t0\n'
printf 'production_key_version_count\t0\n'
printf 'component_runtime_network\tfalse\n'
printf 'production_ingestion_implemented\tfalse\n'
printf 'production_ingestion_enabled\tfalse\n'
printf 'production_ingestion_controls_implemented\t0\n'
printf 'production_ingestion_controls_runtime_exercised\t0\n'
printf 'real_evidence_collected\tfalse\n'
printf 'real_evidence_items_present\t0\n'
printf 'production_validated_evidence_items\t0\n'
printf 'runtime_evidence_accepted\t0\n'
printf 'runtime_prerequisites_satisfied\t0\n'
printf 'runtime_owner_identity_bound\tfalse\n'
printf 'runtime_owner_decision_recorded\tfalse\n'
printf 'runtime_admission_ready\tfalse\n'
printf 'runtime_admission_granted\tfalse\n'
printf 'runtime_authority\tfalse\n'
printf 'provider_authority\tfalse\n'
printf 'downstream_gates_authorized\t0\n'
printf 'runtime_side_effects_unlocked\tNONE\n'
printf 'private_scratch_checkpoint_cap_bytes\t%s\n' "${private_scratch_checkpoint_cap_bytes}"
printf 'private_scratch_checkpoint_cap_passed\ttrue\n'
printf 'private_scratch_checkpoint_scope\tSUCCESSOR_GATE_TREE_ONLY_AFTER_PROTECTED_ARCHIVE_CLONE_CHECKOUT_AND_PREDECESSOR_REPLAY\n'
printf 'private_scratch_quota_enforced\tfalse\n'
printf 'predecessor_checkout_shape\tSINGLE_SPARSE_CHECKOUT\n'
if [[ "${validation_tier}" == fast ]]; then
  printf 'validation_tier\tFAST_CONTENT_IDENTITY_AND_PREDECESSOR_FAST_REPLAY\n'
  printf 'periodic_full_replay_required\ttrue\n'
  printf 'artifact_release_evidence\tfalse\n'
  printf 'fast_gate\tVALID_FAST_SIGNER_ROLE_SCOPE_AUTHORIZATION_ISOLATED_LAB_AUTHORITY_RESOURCE_DECISION_AND_T05_PREDECESSOR_REPLAY\n'
else
  printf 'validation_tier\tPERIODIC_FULL_FROZEN_CHAIN_REPLAY\n'
  printf 'periodic_full_replay_required\tfalse\n'
  printf 'artifact_release_evidence\ttrue\n'
  printf 'full_replay_gate\tVALID_SIGNER_ROLE_SCOPE_AUTHORIZATION_ISOLATED_LAB_AUTHORITY_RESOURCE_DECISION_AND_FULL_FROZEN_T05_CHAIN\n'
fi
