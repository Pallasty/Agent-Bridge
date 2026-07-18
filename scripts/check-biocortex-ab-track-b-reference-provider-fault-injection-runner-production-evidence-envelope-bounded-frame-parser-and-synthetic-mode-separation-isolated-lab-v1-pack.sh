#!/usr/bin/env -S -i /usr/bin/bash
# Source-bound Git gate for the bounded production-evidence envelope frame
# parser and synthetic/production mode-separation isolated-lab pack.
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
  printf 'Runner production-evidence frame/mode isolated-lab v1 gate failed: %s\n' "$*" >&2
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
  /usr/bin/dirname /usr/bin/du /usr/bin/env /usr/bin/find /usr/bin/findmnt /usr/bin/git
  /usr/bin/grep /usr/bin/mkdir /usr/bin/mktemp /usr/bin/python3 /usr/bin/rm
  /usr/bin/rmdir /usr/bin/sha256sum /usr/bin/sort /usr/bin/stat /usr/bin/tar
)
for tool in "${required_tools[@]}"; do
  [[ -x "${tool}" ]] || {
    printf 'Runner production-evidence frame/mode isolated-lab v1 gate missing tool: %s\n' "${tool}" >&2
    exit 2
  }
done

cd "$(/usr/bin/dirname "${BASH_SOURCE[0]}")/.."
repo_root="$(builtin pwd -P)"
[[ "${repo_root}" == /* && "${repo_root}" != "*" && "${repo_root}" != *$'\n'* \
  && -d "${repo_root}" && ! -L "${repo_root}" ]] \
  || fail "repository root is not an exact canonical directory"

baseline_commit="fa0cb9f088e0da2c55c92efde860d9521d4b7493"
frozen_baseline_tree="7bafdda577cd79e364bac6af1b779374a3a7a52b"
frozen_baseline_parent="58ab80243bc1e9484a4c4ac65dba978f35307abf"
predecessor_integration_commit="58ab80243bc1e9484a4c4ac65dba978f35307abf"
predecessor_integration_first_parent="d5bbe55d5d95b1163e287415f437cf77c594135d"
predecessor_source_commit="5d46f0ac978548c4373c5db89ae8c8557048df44"
predecessor_source_parent="d5bbe55d5d95b1163e287415f437cf77c594135d"

predecessor_gate="scripts/check-biocortex-ab-track-b-reference-provider-fault-injection-runner-production-evidence-ingestion-implementation-authority-and-resource-binding-decision-v1-pack.sh"
predecessor_expected="scripts/eval/fixtures/biocortex_ab_track_b_reference_provider_fault_injection_runner_production_evidence_ingestion_implementation_authority_and_resource_binding_decision_v1_pack.expected.v0.tsv"
frozen_predecessor_gate_sha256="743fb03730df6e2717b95da8dfcbb8d94a2b83ba2b7442b6b2cf3d95f39a73cd"
frozen_predecessor_fast_stdout_sha256="8c8d5ae7aa23405cf370bcfb85c49bbad735e12f087edb5e9632dbd411c168ba"

schema_path="docs/design/fixtures/biocortex-ab-track-b-reference-provider-fault-injection-runner-production-evidence-envelope-v1.schema.json"
source_path="scripts/eval/biocortex_ab_track_b_reference_provider_fault_injection_runner_production_evidence_envelope_bounded_frame_parser_and_synthetic_mode_separation_isolated_lab_v1.py"
checker_path="scripts/eval/check_biocortex_ab_track_b_reference_provider_fault_injection_runner_production_evidence_envelope_bounded_frame_parser_and_synthetic_mode_separation_isolated_lab_v1_pack.py"
fixture_path="scripts/eval/fixtures/biocortex_ab_track_b_reference_provider_fault_injection_runner_production_evidence_envelope_bounded_frame_parser_and_synthetic_mode_separation_isolated_lab_v1_pack_synthetic_v0.json"
expected_path="scripts/eval/fixtures/biocortex_ab_track_b_reference_provider_fault_injection_runner_production_evidence_envelope_bounded_frame_parser_and_synthetic_mode_separation_isolated_lab_v1_pack.expected.v0.tsv"
manifest_path="scripts/eval/fixtures/biocortex_ab_track_b_reference_provider_fault_injection_runner_production_evidence_envelope_bounded_frame_parser_and_synthetic_mode_separation_isolated_lab_v1_pack_v0.json"
report_path="docs/reports/goal-c-u/2026-07-17-biocortex-track-b-reference-provider-fault-injection-runner-production-evidence-envelope-bounded-frame-parser-and-synthetic-mode-separation-isolated-lab-v1-pack.md"
gate_path="scripts/check-biocortex-ab-track-b-reference-provider-fault-injection-runner-production-evidence-envelope-bounded-frame-parser-and-synthetic-mode-separation-isolated-lab-v1-pack.sh"

packet_paths=(
  "${schema_path}" "${source_path}" "${checker_path}" "${fixture_path}"
  "${expected_path}" "${manifest_path}" "${report_path}" "${gate_path}"
)
packet_modes=(100644 100644 100644 100644 100644 100644 100644 100755)
predecessor_paths=(
  "docs/reports/goal-c-u/2026-07-17-biocortex-track-b-reference-provider-fault-injection-runner-production-evidence-ingestion-implementation-authority-and-resource-binding-decision-v1-pack.md"
  "${predecessor_gate}"
  "scripts/eval/biocortex_ab_track_b_reference_provider_fault_injection_runner_production_evidence_ingestion_implementation_authority_and_resource_binding_decision_v1.py"
  "scripts/eval/check_biocortex_ab_track_b_reference_provider_fault_injection_runner_production_evidence_ingestion_implementation_authority_and_resource_binding_decision_v1_pack.py"
  "${predecessor_expected}"
  "scripts/eval/fixtures/biocortex_ab_track_b_reference_provider_fault_injection_runner_production_evidence_ingestion_implementation_authority_and_resource_binding_decision_v1_pack_owner_decision_v0.json"
  "scripts/eval/fixtures/biocortex_ab_track_b_reference_provider_fault_injection_runner_production_evidence_ingestion_implementation_authority_and_resource_binding_decision_v1_pack_v0.json"
)
predecessor_raw_sha256=(
  "27e7a5662fcc1861f6dfef7026389bb185854171fe81767f4c6b1c0292d3e6ea"
  "743fb03730df6e2717b95da8dfcbb8d94a2b83ba2b7442b6b2cf3d95f39a73cd"
  "8d3357d85513d4715553b363ebeca8ae825f92776f674ebd35acb8437c4684fa"
  "e7194d800ec811612ca7f003f1a1c29cde07ee3e9788ec8d3632c0eb4853ade0"
  "cb9aca5ec6bf5fe9889d37adffb509b6249752de913356ebf4eece51993f815e"
  "69e2976c1298263240e384817df3a172686e80b8a7c57359829d9e50dda5e3c3"
  "86a03cc5c97729a1b7b8ca35885e98840cb72fda44eff8a789fa9b7520de3150"
)

frozen_schema_sha256="e8cb4964f86de39b16d553537467006454c720dc8bfa8d36e370189627328f55"
frozen_source_sha256="bfa3badbe2b467fbed610d5acb42ef21f1aec2ceb2d5ccf2c218fecfe438eed1"
frozen_checker_sha256="76e0960cb9afa0e4e655ec122b600fe489a31acd5a7edf659d2fff4727ef0dcf"
frozen_fixture_sha256="324379e6e4fcae9db3af3b55d9caacbcb77f56f6c57b110d0ced2987749910b9"
frozen_expected_sha256="775ecfa5169509a5fe0e5a900d8644f47b6b4cf64a1778c7d4ed52214115c847"
frozen_manifest_sha256="9c7ba09368ebd610452ca2799226c1f57dcb63fedabb0319f4b39bc071277d04"
frozen_report_sha256="a93fd00b9dc43f8b9d3717fd07bf3a2eef734724834d75d122d2e8bbbe6e3149"
frozen_normal_stdout_sha256="775ecfa5169509a5fe0e5a900d8644f47b6b4cf64a1778c7d4ed52214115c847"
frozen_self_test_stdout_sha256="7f78dc16429ab778e6fb1b07c6be68630114b9daac4310da94c21c348c98f620"

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
[[ "$(git_clean show -s --format='%P' "${baseline_commit}")" == "${frozen_baseline_parent}" ]] \
  || fail "baseline parent topology drift"
[[ "${frozen_baseline_parent}" == "${predecessor_integration_commit}" ]] \
  || fail "baseline is not directly based on the authority integration"
[[ "$(git_clean show -s --format='%P' "${predecessor_integration_commit}")" \
  == "${predecessor_integration_first_parent} ${predecessor_source_commit}" ]] \
  || fail "predecessor integration topology drift"
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
tmp="$(/usr/bin/mktemp -d "${tmp_base}/runner-production-envelope-frame-mode-v1.XXXXXX")"
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
max_private_scratch_bytes=67108864
check_private_scratch_limit() {
  local scratch_bytes
  scratch_bytes="$(/usr/bin/du -sb -- "${tmp}" | /usr/bin/awk '{print $1}')"
  [[ "${scratch_bytes}" =~ ^[0-9]+$ \
    && "${scratch_bytes}" -le "${max_private_scratch_bytes}" ]] \
    || fail "private scratch exceeds ${max_private_scratch_bytes} bytes"
}

[[ "${#packet_paths[@]}" == 8 && "${#packet_modes[@]}" == 8 ]] \
  || fail "successor eight-path catalog cardinality drift"
[[ "${#predecessor_paths[@]}" == 7 && "${#predecessor_raw_sha256[@]}" == 7 ]] \
  || fail "predecessor seven-path/hash catalog cardinality drift"

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
  || fail "predecessor source is not the exact seven-path all-add delta"
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
  || fail "source is not the exact eight-path all-add delta"
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

for index in "${!predecessor_paths[@]}"; do
  path="${predecessor_paths[$index]}"
  expected_predecessor_sha256="${predecessor_raw_sha256[$index]}"
  predecessor_entry="$(git_clean ls-tree "${predecessor_integration_commit}" -- "${path}")"
  baseline_entry="$(git_clean ls-tree "${baseline_commit}" -- "${path}")"
  source_entry="$(git_clean ls-tree "${source_commit}" -- "${path}")"
  head_entry="$(git_clean ls-tree "${head_oid}" -- "${path}")"
  [[ -n "${predecessor_entry}" && "${baseline_entry}" == "${predecessor_entry}" \
    && "${source_entry}" == "${predecessor_entry}" \
    && "${head_entry}" == "${predecessor_entry}" ]] \
    || fail "frozen predecessor identity drift: ${path}"
  [[ "$(/usr/bin/sha256sum "${path}" | /usr/bin/awk '{print $1}')" \
    == "${expected_predecessor_sha256}" ]] \
    || fail "frozen predecessor raw hash drift: ${path}"
done
[[ "$(/usr/bin/sha256sum "${predecessor_gate}" | /usr/bin/awk '{print $1}')" \
  == "${frozen_predecessor_gate_sha256}" ]] || fail "frozen predecessor gate raw hash drift"

archive_paths=("${packet_paths[@]}" "${predecessor_paths[@]}")
git_clean archive --format=tar "${source_commit}" -- "${archive_paths[@]}" \
  | /usr/bin/tar -x -C "${tmp}/artifact-archive"
[[ -z "$(/usr/bin/find "${tmp}/artifact-archive" -type l -print -quit)" ]] \
  || fail "artifact archive contains a symlink"
[[ -z "$(/usr/bin/find "${tmp}/artifact-archive" -type f -links +1 -print -quit)" ]] \
  || fail "artifact archive contains a hardlinked file"
for index in "${!predecessor_paths[@]}"; do
  path="${predecessor_paths[$index]}"
  expected_predecessor_sha256="${predecessor_raw_sha256[$index]}"
  [[ "$(/usr/bin/sha256sum "${tmp}/artifact-archive/${path}" | /usr/bin/awk '{print $1}')" \
    == "${expected_predecessor_sha256}" ]] \
    || fail "archive predecessor raw hash drift: ${path}"
done
check_private_scratch_limit

verify_hash() {
  local label="$1" expected="$2" path="$3" actual
  actual="$(/usr/bin/sha256sum "${tmp}/artifact-archive/${path}" | /usr/bin/awk '{print $1}')"
  [[ "${actual}" == "${expected}" ]] || fail "${label} SHA-256 drift: ${path}"
}
verify_hash schema "${frozen_schema_sha256}" "${schema_path}"
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
for path in "${schema_path}" "${source_path}" "${checker_path}" "${fixture_path}" \
  "${expected_path}" "${manifest_path}"; do
  digest="$(/usr/bin/sha256sum "${tmp}/artifact-archive/${path}" | /usr/bin/awk '{print $1}')"
  [[ "$(/usr/bin/grep -Foc -- "${digest}" "${tmp}/artifact-archive/${report_path}")" == 1 ]] \
    || fail "report does not bind exact artifact hash: ${path}"
done

predecessor_repo="${tmp}/predecessor-repo"
if ! git_clean clone --no-local --no-hardlinks --no-checkout --no-tags --single-branch \
  -- . "${predecessor_repo}" >"${tmp}/clone.stdout" 2>"${tmp}/clone.stderr"; then
  /usr/bin/cat "${tmp}/clone.stderr" >&2
  fail "cannot clone isolated predecessor repository"
fi
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
check_private_scratch_limit
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
expected_predecessor_stdout_sha256="${frozen_predecessor_fast_stdout_sha256}"
expected_predecessor_line_count=96
if [[ "${validation_tier}" == full-replay ]]; then
  predecessor_full_replay=true
  expected_predecessor_stdout_sha256=""
  expected_predecessor_line_count=97
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
if [[ -n "${expected_predecessor_stdout_sha256}" ]]; then
  [[ "$(/usr/bin/sha256sum "${tmp}/predecessor.stdout" | /usr/bin/awk '{print $1}')" \
    == "${expected_predecessor_stdout_sha256}" ]] || fail "predecessor stdout SHA-256 drift"
fi

predecessor_tsv_lines="$(/usr/bin/awk 'END {print NR}' \
  "${predecessor_repo}/${predecessor_expected}")"
[[ "${predecessor_tsv_lines}" == 56 ]] || fail "predecessor TSV line-count drift"
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
  $1 == "predecessor_receipt_sha256" && length($2) == 64 && $2 !~ /[^0-9a-f]/ {count++}
  END {exit count == 1 ? 0 : 1}
' "${tmp}/predecessor.stdout" || fail "predecessor nested receipt digest drift"

for field_value in \
  $'implementation_authority_recorded\ttrue' \
  $'implementation_scope_decision_recorded\ttrue' \
  $'implementation_resource_binding_recorded\ttrue' \
  $'production_shaped_component_code_authorized\ttrue' \
  $'production_environment_implementation_authorized\tfalse' \
  $'owner_supplied_numeric_budget_cap\tfalse' \
  $'external_paid_spend_cap\t0' \
  $'provider_endpoint_count\t0' \
  $'credential_handle_count\t0' \
  $'component_runtime_network\tfalse' \
  $'global_single_use_proved\tfalse' \
  $'production_ingestion_implemented\tfalse' \
  $'production_ingestion_enabled\tfalse' \
  $'production_ingestion_controls_implemented\t0' \
  $'production_ingestion_controls_runtime_exercised\t0' \
  $'real_evidence_items_present\t0' \
  $'production_validated_evidence_items\t0' \
  $'runtime_evidence_accepted\t0' \
  $'runtime_prerequisites_satisfied\t0' \
  $'runtime_owner_identity_bound\tfalse' \
  $'runtime_owner_decision_recorded\tfalse' \
  $'runtime_admission_ready\tfalse' \
  $'runtime_admission_granted\tfalse' \
  $'runtime_authority\tfalse' \
  $'provider_authority\tfalse' \
  $'downstream_gates_authorized\t0' \
  $'runtime_side_effects_unlocked\tNONE' \
  $'implementation_side_effects_unlocked\tREVERSIBLE_LOCAL_CODE_SCHEMA_TEST_DOCS_FOR_EXACT_NEXT_UNIT_ONLY'; do
  [[ "$(/usr/bin/grep -Fxc -- "${field_value}" "${tmp}/predecessor.stdout")" == 2 ]] \
    || fail "predecessor duplicated TSV/footer boundary count drift: ${field_value}"
done
for field_value in \
  $'decision_scope\tISOLATED_LAB_FIRST' \
  $'real_evidence_collected\tfalse' \
  $'content_sha256\t48f4eee93f565005ffa79a119529d58e5d61eb947754d4672c96541001268463'; do
  [[ "$(/usr/bin/grep -Fxc -- "${field_value}" "${tmp}/predecessor.stdout")" == 1 ]] \
    || fail "predecessor exact-once boundary count drift: ${field_value}"
done

if [[ "${validation_tier}" == full-replay ]]; then
  for field_value in \
    $'integration_gate\tVALID_INTEGRATED_BIOCORTEX_AB_TRACK_B_RUNNER_PRODUCTION_EVIDENCE_INGESTION_IMPLEMENTATION_AUTHORITY_AND_RESOURCE_BINDING_DECISION_V1_PACK' \
    $'gate\tPASS' \
    $'predecessor_full_replay\ttrue' \
    $'validation_tier\tPERIODIC_FULL_FROZEN_CHAIN_REPLAY' \
    $'periodic_full_replay_required\tfalse' \
    $'artifact_release_evidence\ttrue' \
    $'full_replay_gate\tVALID_PRODUCTION_INGESTION_AUTHORITY_RESOURCE_DECISION_AND_FULL_FROZEN_PREDECESSOR_CHAIN'; do
    [[ "$(/usr/bin/grep -Fxc -- "${field_value}" "${tmp}/predecessor.stdout")" == 1 ]] \
      || fail "predecessor full replay receipt drift: ${field_value}"
  done
  [[ "$(/usr/bin/grep -Fxc -- $'gate\tFAST_PASS_NON_RELEASE_CONTENT_IDENTITY_ONLY' \
    "${tmp}/predecessor.stdout")" == 0 ]] || fail "predecessor full replay contains fast gate marker"
  [[ "$(/usr/bin/grep -Fxc -- $'fast_gate\tVALID_FAST_PRODUCTION_INGESTION_AUTHORITY_RESOURCE_DECISION_AND_PREDECESSOR_REPLAY' \
    "${tmp}/predecessor.stdout")" == 0 ]] || fail "predecessor full replay contains fast receipt"
else
  for field_value in \
    $'gate\tFAST_PASS_NON_RELEASE_CONTENT_IDENTITY_ONLY' \
    $'predecessor_full_replay\tfalse' \
    $'validation_tier\tFAST_CONTENT_IDENTITY_AND_PREDECESSOR_FAST_REPLAY' \
    $'periodic_full_replay_required\ttrue' \
    $'artifact_release_evidence\tfalse' \
    $'fast_gate\tVALID_FAST_PRODUCTION_INGESTION_AUTHORITY_RESOURCE_DECISION_AND_PREDECESSOR_REPLAY'; do
    [[ "$(/usr/bin/grep -Fxc -- "${field_value}" "${tmp}/predecessor.stdout")" == 1 ]] \
      || fail "predecessor fast replay receipt drift: ${field_value}"
  done
  [[ "$(/usr/bin/grep -Fxc -- $'gate\tPASS' "${tmp}/predecessor.stdout")" == 0 ]] \
    || fail "predecessor fast replay contains release gate marker"
  [[ "$(/usr/bin/grep -Fxc -- $'integration_gate\tVALID_INTEGRATED_BIOCORTEX_AB_TRACK_B_RUNNER_PRODUCTION_EVIDENCE_INGESTION_IMPLEMENTATION_AUTHORITY_AND_RESOURCE_BINDING_DECISION_V1_PACK' \
    "${tmp}/predecessor.stdout")" == 0 ]] || fail "predecessor fast replay contains integration receipt"
fi
predecessor_receipt_sha256="$(/usr/bin/sha256sum "${tmp}/predecessor.stdout" | /usr/bin/awk '{print $1}')"
check_private_scratch_limit
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
  printf 'integration_gate\tVALID_INTEGRATED_BIOCORTEX_AB_TRACK_B_RUNNER_PRODUCTION_EVIDENCE_ENVELOPE_BOUNDED_FRAME_PARSER_AND_SYNTHETIC_MODE_SEPARATION_ISOLATED_LAB_V1_PACK\n'
  printf 'gate\tPASS\n'
  printf 'authorization_consumption_state\tCONSUMED_SCOPE_COMPLETE\n'
  printf 'implementation_authority_single_use_consumed\ttrue\n'
else
  printf 'gate\tFAST_PASS_NON_RELEASE_CONTENT_IDENTITY_ONLY\n'
  printf 'authorization_consumption_state\tAUTHORIZED_ISOLATED_LAB_FIRST_EXACT_UNIT_PENDING_INTEGRATED_FULL_GATE\n'
  printf 'implementation_authority_single_use_consumed\tfalse\n'
fi
printf 'mode\t%s\n' "${mode}"
printf 'source_commit\t%s\n' "${source_commit}"
printf 'head\t%s\n' "${head_oid}"
printf 'predecessor_receipt_sha256\t%s\n' "${predecessor_receipt_sha256}"
printf 'predecessor_full_replay\t%s\n' "${predecessor_full_replay}"
printf 'isolated_lab_candidate_component_count\t2\n'
printf 'isolated_lab_candidate_components_implemented\t2\n'
printf 'isolated_lab_candidate_components_locally_kat_exercised\t2\n'
printf 'boundary_threat_specifications_locally_kat_covered\t4\n'
printf 'production_ingestion_control_count\t14\n'
printf 'production_ingestion_controls_implemented\t0\n'
printf 'production_ingestion_controls_runtime_exercised\t0\n'
printf 'production_threat_case_count\t20\n'
printf 'production_threat_cases_runtime_exercised\t0\n'
printf 'real_evidence_collected\tfalse\n'
printf 'real_evidence_items_present\t0\n'
printf 'production_validated_evidence_items\t0\n'
printf 'runtime_evidence_accepted\t0\n'
printf 'runtime_prerequisites_satisfied\t0\n'
printf 'provider_endpoint_count\t0\n'
printf 'credential_handle_count\t0\n'
printf 'credential_path_count\t0\n'
printf 'component_runtime_network\tfalse\n'
printf 'external_paid_spend_cap\t0\n'
printf 'max_private_scratch_bytes\t67108864\n'
printf 'private_scratch_limit_enforced\ttrue\n'
printf 'predecessor_checkout_shape\tSINGLE_SPARSE_CHECKOUT\n'
printf 'runtime_owner_identity_bound\tfalse\n'
printf 'runtime_owner_decision_recorded\tfalse\n'
printf 'runtime_admission_ready\tfalse\n'
printf 'runtime_admission_granted\tfalse\n'
printf 'runtime_authority\tfalse\n'
printf 'provider_authority\tfalse\n'
printf 'downstream_gates_authorized\t0\n'
printf 'runtime_side_effects_unlocked\tNONE\n'
if [[ "${validation_tier}" == fast ]]; then
  printf 'validation_tier\tFAST_CONTENT_IDENTITY_AND_PREDECESSOR_FAST_REPLAY\n'
  printf 'periodic_full_replay_required\ttrue\n'
  printf 'artifact_release_evidence\tfalse\n'
  printf 'fast_gate\tVALID_FAST_PRODUCTION_EVIDENCE_ENVELOPE_FRAME_MODE_ISOLATED_LAB_AND_AUTHORITY_PREDECESSOR_REPLAY\n'
else
  printf 'validation_tier\tPERIODIC_FULL_FROZEN_CHAIN_REPLAY\n'
  printf 'periodic_full_replay_required\tfalse\n'
  printf 'artifact_release_evidence\ttrue\n'
  printf 'full_replay_gate\tVALID_PRODUCTION_EVIDENCE_ENVELOPE_FRAME_MODE_ISOLATED_LAB_AND_FULL_FROZEN_PREDECESSOR_CHAIN\n'
fi
