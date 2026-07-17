#!/usr/bin/env -S -i /usr/bin/bash
# Source-bound Git gate for the runtime-prerequisite evidence validator doubles pack.
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
  printf 'Runner runtime-prerequisite evidence validator doubles v1 gate failed: %s\n' "$*" >&2
  exit 1
}

validation_tier="${1:-full-replay}"
[[ "$#" -le 1 ]] || fail "expected at most one validation tier"
case "${validation_tier}" in
  fast|full-replay) ;;
  *) fail "unknown validation tier: ${validation_tier}" ;;
esac

required_tools=(
  /usr/bin/awk /usr/bin/bash /usr/bin/bwrap /usr/bin/cat /usr/bin/chmod /usr/bin/cmp
  /usr/bin/dirname /usr/bin/env /usr/bin/find /usr/bin/findmnt /usr/bin/git /usr/bin/grep
  /usr/bin/mkdir /usr/bin/mktemp /usr/bin/python3 /usr/bin/rm /usr/bin/rmdir
  /usr/bin/sha256sum /usr/bin/sort /usr/bin/stat /usr/bin/tar
)
for tool in "${required_tools[@]}"; do
  [[ -x "${tool}" ]] || {
    printf 'Runner runtime-prerequisite evidence validator doubles v1 gate missing tool: %s\n' "${tool}" >&2
    exit 2
  }
done

cd "$(/usr/bin/dirname "${BASH_SOURCE[0]}")/.."
repo_root="$(builtin pwd -P)"
[[ "${repo_root}" == /* && "${repo_root}" != "*" && "${repo_root}" != *$'\n'* \
  && -d "${repo_root}" && ! -L "${repo_root}" ]] \
  || fail "repository root is not an exact canonical directory"

baseline_commit="8af4af0e5ceea8062b65ac06870cabf789567053"
predecessor_source_commit="ca939cd3e097ebadb6adbea6d2778e2eff71da73"
predecessor_gate="scripts/check-biocortex-ab-track-b-reference-provider-fault-injection-runner-runtime-prerequisite-evidence-plan-and-owner-decision-preregistration-v1-pack.sh"
evidence_packet_schema="docs/design/fixtures/biocortex-ab-track-b-reference-provider-fault-injection-runner-runtime-prerequisite-evidence-packet-schema-v1.json"
owner_decision_packet_schema="docs/design/fixtures/biocortex-ab-track-b-reference-provider-fault-injection-runner-owner-decision-packet-schema-v1.json"
source_path="scripts/eval/biocortex_ab_track_b_reference_provider_fault_injection_runner_runtime_prerequisite_evidence_packet_schemas_and_offline_validator_doubles_v1.py"
checker_path="scripts/eval/check_biocortex_ab_track_b_reference_provider_fault_injection_runner_runtime_prerequisite_evidence_packet_schemas_and_offline_validator_doubles_v1_pack.py"
synthetic_path="scripts/eval/fixtures/biocortex_ab_track_b_reference_provider_fault_injection_runner_runtime_prerequisite_evidence_packet_schemas_and_offline_validator_doubles_v1_pack_synthetic_v0.json"
expected_path="scripts/eval/fixtures/biocortex_ab_track_b_reference_provider_fault_injection_runner_runtime_prerequisite_evidence_packet_schemas_and_offline_validator_doubles_v1_pack.expected.v0.tsv"
manifest_path="scripts/eval/fixtures/biocortex_ab_track_b_reference_provider_fault_injection_runner_runtime_prerequisite_evidence_packet_schemas_and_offline_validator_doubles_v1_pack_v0.json"
report_path="docs/reports/goal-c-u/2026-07-17-biocortex-track-b-reference-provider-fault-injection-runner-runtime-prerequisite-evidence-packet-schemas-and-offline-validator-doubles-v1-pack.md"
gate_path="scripts/check-biocortex-ab-track-b-reference-provider-fault-injection-runner-runtime-prerequisite-evidence-packet-schemas-and-offline-validator-doubles-v1-pack.sh"

packet_paths=(
  "${evidence_packet_schema}" "${owner_decision_packet_schema}"
  "${source_path}" "${checker_path}" "${synthetic_path}" "${expected_path}"
  "${manifest_path}" "${report_path}" "${gate_path}"
)
packet_modes=(100644 100644 100644 100644 100644 100644 100644 100644 100755)
predecessor_paths=(
  "scripts/eval/biocortex_ab_track_b_reference_provider_fault_injection_runner_runtime_prerequisite_evidence_plan_and_owner_decision_preregistration_v1.py"
  "scripts/eval/check_biocortex_ab_track_b_reference_provider_fault_injection_runner_runtime_prerequisite_evidence_plan_and_owner_decision_preregistration_v1_pack.py"
  "scripts/eval/fixtures/biocortex_ab_track_b_reference_provider_fault_injection_runner_runtime_prerequisite_evidence_plan_and_owner_decision_preregistration_v1_pack_synthetic_v0.json"
  "scripts/eval/fixtures/biocortex_ab_track_b_reference_provider_fault_injection_runner_runtime_prerequisite_evidence_plan_and_owner_decision_preregistration_v1_pack.expected.v0.tsv"
  "scripts/eval/fixtures/biocortex_ab_track_b_reference_provider_fault_injection_runner_runtime_prerequisite_evidence_plan_and_owner_decision_preregistration_v1_pack_v0.json"
  "docs/reports/goal-c-u/2026-07-16-biocortex-track-b-reference-provider-fault-injection-runner-runtime-prerequisite-evidence-plan-and-owner-decision-preregistration-v1-pack.md"
  "${predecessor_gate}"
)

frozen_manifest_sha256="c5d448a121b58549a62e20ec7b241386ad73c9685ae9a981223a591555e2bd47"
frozen_source_sha256="29a4b67049429c09981f1742f072a3fe382f381259fa238b69041b3d46939351"
frozen_checker_sha256="d1f3f93a8808cce859415282fc757ef2a11a64fde165f7c37247437c8ea5cee7"
frozen_synthetic_sha256="236839e4a8e831a84ef11c089cbd624152ddb456e583c2c414ece6c5ebb09f97"
frozen_expected_sha256="24317b383b71933f206331f5629e1e6e0ea09a8e0ba8372ee6fb2b40a64c4210"
frozen_report_sha256="e431866b9545cade47aeb9b94f75638bb22dbd43b2c01c9c672acaff3e3de593"
frozen_evidence_packet_schema_sha256="121c66331f159539722acb8f173696811487d8b76b9da07ab9d83340e28277d3"
frozen_owner_decision_packet_schema_sha256="7845de2ac7d1f069fd550f5625a1593c0a093563acbe1be1855bf7df0f3d4436"
frozen_normal_stdout_sha256="24317b383b71933f206331f5629e1e6e0ea09a8e0ba8372ee6fb2b40a64c4210"
frozen_self_test_stdout_sha256="e06d7fa4d172908df0b16799fbb4d8dee94518412b2b57ab762b3da0edb677e9"
frozen_baseline_tree="c27c4cbbbc51892db99700f862b96927f944f09c"
frozen_baseline_parents="c9c50917687c7715b031a6bfe8dd7801bfd737ee ca939cd3e097ebadb6adbea6d2778e2eff71da73"

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
[[ "$(git_clean cat-file -t "${baseline_commit}")" == commit ]] \
  || fail "baseline commit is unavailable"
[[ "$(git_clean show -s --format='%T' "${baseline_commit}")" == "${frozen_baseline_tree}" ]] \
  || fail "baseline tree drift"
[[ "$(git_clean show -s --format='%P' "${baseline_commit}")" == "${frozen_baseline_parents}" ]] \
  || fail "baseline parent topology drift"

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

tmp_base="/tmp"
[[ -d "${tmp_base}" && ! -L "${tmp_base}" \
  && "$(/usr/bin/stat -c '%F' "${tmp_base}")" == directory \
  && "$(/usr/bin/stat -c '%u' "${tmp_base}")" == 0 \
  && "$(/usr/bin/stat -c '%a' "${tmp_base}")" == 1777 ]] \
  || fail "gate temp base owner, type, or mode drift"
tmp="$(/usr/bin/mktemp -d "${tmp_base}/agent-bridge-runner-runtime-prerequisite-evidence-validator-v1.XXXXXX")"
[[ -d "${tmp}" && ! -L "${tmp}" \
  && "$(/usr/bin/stat -c '%u' "${tmp}")" == "${EUID}" \
  && "$(/usr/bin/stat -c '%a' "${tmp}")" == 700 ]] \
  || fail "private gate temp directory owner or mode drift"
predecessor_cache_parent="$(/usr/bin/dirname "$(/usr/bin/dirname "${common_dir}")")/.ab-gate-tmp"
predecessor_cache_parent_created=false
if [[ ! -e "${predecessor_cache_parent}" ]]; then
  /usr/bin/mkdir -m 0700 "${predecessor_cache_parent}"
  predecessor_cache_parent_created=true
fi
[[ -d "${predecessor_cache_parent}" && ! -L "${predecessor_cache_parent}" \
  && "$(/usr/bin/stat -c '%u' "${predecessor_cache_parent}")" == "${EUID}" \
  && "$(/usr/bin/stat -c '%a' "${predecessor_cache_parent}")" == 700 ]] \
  || fail "predecessor cache parent owner or mode drift"
predecessor_cache_fstype="$(/usr/bin/findmnt -T "${predecessor_cache_parent}" -n -o FSTYPE)" \
  || fail "cannot resolve predecessor cache filesystem"
[[ "${predecessor_cache_fstype}" != tmpfs \
  && "${predecessor_cache_fstype}" != fuseblk ]] \
  || fail "predecessor cache requires a persistent POSIX filesystem"
predecessor_cache="$(/usr/bin/mktemp -d "${predecessor_cache_parent}/runner-runtime-evidence-predecessor-cache.XXXXXX")"
[[ -d "${predecessor_cache}" && ! -L "${predecessor_cache}" \
  && "$(/usr/bin/stat -c '%u' "${predecessor_cache}")" == "${EUID}" \
  && "$(/usr/bin/stat -c '%a' "${predecessor_cache}")" == 700 ]] \
  || fail "private predecessor cache owner or mode drift"
cleanup() {
  /usr/bin/chmod -R u+w "${tmp}" 2>/dev/null || true
  /usr/bin/rm -rf "${tmp}" 2>/dev/null || true
  /usr/bin/chmod -R u+w "${predecessor_cache}" 2>/dev/null || true
  /usr/bin/rm -rf "${predecessor_cache}" 2>/dev/null || true
  if [[ "${predecessor_cache_parent_created}" == true ]]; then
    /usr/bin/rmdir "${predecessor_cache_parent}" 2>/dev/null || true
  fi
}
trap cleanup EXIT
/usr/bin/mkdir -m 0700 "${tmp}/home" "${tmp}/source-archive" "${tmp}/head-archive"

: >"${tmp}/expected-paths"
for path in "${packet_paths[@]}"; do printf '%s\n' "${path}" >>"${tmp}/expected-paths"; done
git_clean diff-tree --no-commit-id --name-status -r "${baseline_commit}" "${source_commit}" \
  | LC_ALL=C /usr/bin/sort >"${tmp}/actual-source-delta"
/usr/bin/awk '{print "A\t" $0}' "${tmp}/expected-paths" \
  | LC_ALL=C /usr/bin/sort >"${tmp}/expected-source-delta"
/usr/bin/cmp -s "${tmp}/expected-source-delta" "${tmp}/actual-source-delta" \
  || fail "source is not the exact nine-path all-add delta"
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
for path in "${predecessor_paths[@]}"; do
  [[ "$(git_clean ls-tree "${head_oid}" -- "${path}")" \
    == "$(git_clean ls-tree "${baseline_commit}" -- "${path}")" ]] \
    || fail "predecessor identity drift: ${path}"
done

git_clean archive --format=tar "${source_commit}" | /usr/bin/tar -x -C "${tmp}/source-archive"
git_clean archive --format=tar "${head_oid}" | /usr/bin/tar -x -C "${tmp}/head-archive"
for archive in "${tmp}/source-archive" "${tmp}/head-archive"; do
  [[ -z "$(/usr/bin/find "${archive}" -type l -print -quit)" ]] \
    || fail "archive contains a symlink"
  [[ -z "$(/usr/bin/find "${archive}" -type f -links +1 -print -quit)" ]] \
    || fail "archive contains a hardlinked file"
done

verify_hash() {
  local label="$1" expected="$2" path="$3" actual
  actual="$(/usr/bin/sha256sum "${tmp}/source-archive/${path}" | /usr/bin/awk '{print $1}')"
  [[ "${actual}" == "${expected}" ]] || fail "${label} SHA-256 drift: ${path}"
}
verify_hash evidence-packet-schema "${frozen_evidence_packet_schema_sha256}" "${evidence_packet_schema}"
verify_hash owner-decision-packet-schema "${frozen_owner_decision_packet_schema_sha256}" "${owner_decision_packet_schema}"
verify_hash manifest "${frozen_manifest_sha256}" "${manifest_path}"
verify_hash source "${frozen_source_sha256}" "${source_path}"
verify_hash checker "${frozen_checker_sha256}" "${checker_path}"
verify_hash synthetic "${frozen_synthetic_sha256}" "${synthetic_path}"
verify_hash expected "${frozen_expected_sha256}" "${expected_path}"
verify_hash report "${frozen_report_sha256}" "${report_path}"

for seed in 0 314159; do
  /usr/bin/env -i PATH="${PATH}" HOME="${tmp}/home" LC_ALL=C TZ=UTC \
    PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1 PYTHONSAFEPATH=1 \
    PYTHONHASHSEED="${seed}" \
    /usr/bin/python3 -S -P "${tmp}/source-archive/${checker_path}" \
      >"${tmp}/source-${seed}.stdout"
  [[ "$(/usr/bin/sha256sum "${tmp}/source-${seed}.stdout" | /usr/bin/awk '{print $1}')" \
    == "${frozen_normal_stdout_sha256}" ]] \
    || fail "source checker drift for hash seed ${seed}"
done
/usr/bin/env -i PATH="${PATH}" HOME="${tmp}/home" LC_ALL=C TZ=UTC \
  PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1 PYTHONSAFEPATH=1 PYTHONHASHSEED=7 \
  /usr/bin/python3 -S -P "${tmp}/source-archive/${checker_path}" --self-test \
    >"${tmp}/source-self-test.stdout"
[[ "$(/usr/bin/sha256sum "${tmp}/source-self-test.stdout" | /usr/bin/awk '{print $1}')" \
  == "${frozen_self_test_stdout_sha256}" ]] || fail "source self-test checker drift"
if [[ "${mode}" == integrated ]]; then
  /usr/bin/env -i PATH="${PATH}" HOME="${tmp}/home" LC_ALL=C TZ=UTC \
    PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1 PYTHONSAFEPATH=1 PYTHONHASHSEED=2718 \
    /usr/bin/python3 -S -P "${tmp}/head-archive/${checker_path}" \
      >"${tmp}/integrated.stdout"
  /usr/bin/cmp -s "${tmp}/source-0.stdout" "${tmp}/integrated.stdout" \
    || fail "integrated checker drift"
fi

[[ "$(/usr/bin/grep -Fxc -- '## Artifact binding' "${tmp}/source-archive/${report_path}")" == 1 ]] \
  || fail "report lacks exact-once Artifact binding heading"
for path in "${evidence_packet_schema}" "${owner_decision_packet_schema}" \
  "${source_path}" "${checker_path}" "${synthetic_path}" "${expected_path}"; do
  digest="$(/usr/bin/sha256sum "${tmp}/source-archive/${path}" | /usr/bin/awk '{print $1}')"
  [[ "$(/usr/bin/grep -Foc -- "${digest}" "${tmp}/source-archive/${report_path}")" == 1 ]] \
    || fail "report does not bind exact artifact hash: ${path}"
done

predecessor_repo="${tmp}/predecessor-repo"
if ! git_clean clone --no-local --no-checkout --no-tags --single-branch -- . "${predecessor_repo}" \
  >"${tmp}/clone.stdout" 2>"${tmp}/clone.stderr"; then
  /usr/bin/cat "${tmp}/clone.stderr" >&2
  fail "cannot clone isolated predecessor repository"
fi
/usr/bin/git --no-pager --no-replace-objects -c safe.directory="${predecessor_repo}" \
  -C "${predecessor_repo}" checkout --detach "${baseline_commit}" \
  >"${tmp}/checkout.stdout" 2>"${tmp}/checkout.stderr" \
  || { /usr/bin/cat "${tmp}/checkout.stderr" >&2; fail "cannot checkout predecessor"; }
[[ "$(/usr/bin/git -c safe.directory="${predecessor_repo}" -C "${predecessor_repo}" rev-parse HEAD)" \
  == "${baseline_commit}" ]] || fail "isolated predecessor HEAD drift"
[[ -z "$(/usr/bin/git -c safe.directory="${predecessor_repo}" -C "${predecessor_repo}" status --porcelain=v1 --untracked-files=all)" ]] \
  || fail "isolated predecessor is dirty before replay"

# Frozen predecessor gates retain their exact bytes and hard-coded /home cache
# paths.  The host projects /home ownership and modes through FUSE, so replay
# them in a no-network mount namespace whose cache target is this private,
# non-tmpfs POSIX directory.

predecessor_tier=fast
predecessor_full_replay=false
if [[ "${validation_tier}" == full-replay ]]; then
  predecessor_tier=full-replay
  predecessor_full_replay=true
fi
if ! (
  /usr/bin/bwrap --die-with-parent --new-session --unshare-net \
    --ro-bind / / --dev-bind /dev /dev --proc /proc \
    --bind /tmp /tmp \
    --bind "${predecessor_cache}" /home/pallasting/.cache \
    --chdir "${predecessor_repo}" \
    "${predecessor_repo}/${predecessor_gate}" "${predecessor_tier}"
) >"${tmp}/predecessor.stdout" 2>"${tmp}/predecessor.stderr"; then
  /usr/bin/cat "${tmp}/predecessor.stderr" >&2
  fail "predecessor ${predecessor_tier} replay failed"
fi
[[ "$(/usr/bin/grep -Fxc -- "mode"$'\t'"integrated" "${tmp}/predecessor.stdout")" == 1 ]] \
  || fail "predecessor mode receipt drift"
[[ "$(/usr/bin/grep -Fxc -- "source_commit"$'\t'"${predecessor_source_commit}" "${tmp}/predecessor.stdout")" == 1 ]] \
  || fail "predecessor source receipt drift"
[[ "$(/usr/bin/grep -Fxc -- "head"$'\t'"${baseline_commit}" "${tmp}/predecessor.stdout")" == 1 ]] \
  || fail "predecessor head receipt drift"
[[ "$(/usr/bin/grep -Fxc -- $'runtime_authority\tfalse' "${tmp}/predecessor.stdout")" == 1 ]] \
  || fail "predecessor runtime-authority receipt drift"
[[ "$(/usr/bin/grep -Fxc -- $'runtime_admission_granted\tfalse' "${tmp}/predecessor.stdout")" == 1 ]] \
  || fail "predecessor runtime-admission receipt drift"
if [[ "${validation_tier}" == full-replay ]]; then
  [[ "$(/usr/bin/grep -Fxc -- $'gate\tPASS' "${tmp}/predecessor.stdout")" == 1 ]] \
    || fail "predecessor full gate receipt drift"
  [[ "$(/usr/bin/grep -Fxc -- $'artifact_release_evidence\ttrue' "${tmp}/predecessor.stdout")" == 1 ]] \
    || fail "predecessor release receipt drift"
else
  [[ "$(/usr/bin/grep -Fxc -- $'gate\tFAST_PASS_NON_RELEASE_CONTENT_IDENTITY_ONLY' "${tmp}/predecessor.stdout")" == 1 ]] \
    || fail "predecessor fast gate receipt drift"
  [[ "$(/usr/bin/grep -Fxc -- $'artifact_release_evidence\tfalse' "${tmp}/predecessor.stdout")" == 1 ]] \
    || fail "predecessor non-release receipt drift"
fi
predecessor_receipt_sha256="$(/usr/bin/sha256sum "${tmp}/predecessor.stdout" | /usr/bin/awk '{print $1}')"
[[ -z "$(/usr/bin/find "${predecessor_cache}" -mindepth 1 -print -quit)" ]] \
  || fail "predecessor replay left private cache residue"
[[ -z "$(/usr/bin/git -c safe.directory="${predecessor_repo}" -C "${predecessor_repo}" status --porcelain=v1 --untracked-files=all)" ]] \
  || fail "predecessor replay dirtied isolated repository"

git_clean diff --check "${baseline_commit}" "${source_commit}"
[[ "$(git_clean rev-parse HEAD)" == "${head_oid}" ]] || fail "HEAD changed during gate"
[[ -z "$(git_clean status --porcelain=v1 --untracked-files=all)" ]] \
  || fail "verification dirtied worktree or index"

source_result="$(/usr/bin/cat "${tmp}/source-0.stdout")"
/usr/bin/chmod -R u+w "${tmp}" || fail "cannot make temp tree removable"
/usr/bin/rm -rf "${tmp}" || fail "cannot remove temp tree"
/usr/bin/chmod -R u+w "${predecessor_cache}" \
  || fail "cannot make predecessor cache removable"
/usr/bin/rm -rf "${predecessor_cache}" || fail "cannot remove predecessor cache"
if [[ "${predecessor_cache_parent_created}" == true ]]; then
  /usr/bin/rmdir "${predecessor_cache_parent}" 2>/dev/null || true
fi
trap - EXIT

printf '%s\n' "${source_result}"
if [[ "${validation_tier}" == full-replay ]]; then
  if [[ "${mode}" == integrated ]]; then
    printf 'integration_gate\tVALID_INTEGRATED_BIOCORTEX_AB_TRACK_B_RUNNER_RUNTIME_PREREQUISITE_EVIDENCE_PACKET_SCHEMAS_AND_OFFLINE_VALIDATOR_DOUBLES_V1_PACK\n'
  else
    printf 'source_gate\tVALID_SOURCE_BIOCORTEX_AB_TRACK_B_RUNNER_RUNTIME_PREREQUISITE_EVIDENCE_PACKET_SCHEMAS_AND_OFFLINE_VALIDATOR_DOUBLES_V1_PACK\n'
  fi
  printf 'gate\tPASS\n'
else
  printf 'gate\tFAST_PASS_NON_RELEASE_CONTENT_IDENTITY_ONLY\n'
fi
printf 'mode\t%s\n' "${mode}"
printf 'source_commit\t%s\n' "${source_commit}"
printf 'head\t%s\n' "${head_oid}"
printf 'predecessor_receipt_sha256\t%s\n' "${predecessor_receipt_sha256}"
printf 'predecessor_full_replay\t%s\n' "${predecessor_full_replay}"
printf 'runtime_authority\tfalse\n'
printf 'runtime_admission_granted\tfalse\n'
printf 'positive_decision_representable\tfalse\n'
printf 'owner_decision_recorded\tfalse\n'
printf 'real_evidence_collected\tfalse\n'
printf 'runtime_prerequisites_satisfied\t0\n'
if [[ "${validation_tier}" == fast ]]; then
  printf 'validation_tier\tFAST_CONTENT_IDENTITY_AND_PREDECESSOR_FAST_REPLAY\n'
  printf 'periodic_full_replay_required\ttrue\n'
  printf 'artifact_release_evidence\tfalse\n'
  printf 'fast_gate\tVALID_FAST_RUNTIME_PREREQUISITE_EVIDENCE_PACKET_VALIDATOR_DOUBLES_AND_PREDECESSOR_REPLAY\n'
else
  printf 'validation_tier\tPERIODIC_FULL_FROZEN_CHAIN_REPLAY\n'
  printf 'periodic_full_replay_required\tfalse\n'
  printf 'artifact_release_evidence\ttrue\n'
  printf 'full_replay_gate\tVALID_RUNTIME_PREREQUISITE_EVIDENCE_PACKET_VALIDATOR_DOUBLES_AND_FULL_FROZEN_PREDECESSOR_CHAIN\n'
fi
