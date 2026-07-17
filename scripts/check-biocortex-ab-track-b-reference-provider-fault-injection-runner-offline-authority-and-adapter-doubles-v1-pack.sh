#!/usr/bin/env -S -i /usr/bin/bash
# Source-bound Git gate for the pure runner-v1 authority and adapter doubles.
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
  printf 'Runner offline authority/adapter doubles v1 gate failed: %s\n' "$*" >&2
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
  /usr/bin/dirname /usr/bin/env /usr/bin/find /usr/bin/git /usr/bin/grep
  /usr/bin/mkdir /usr/bin/mktemp /usr/bin/python3 /usr/bin/rm /usr/bin/rmdir
  /usr/bin/sha256sum /usr/bin/sort /usr/bin/stat /usr/bin/tar
)
for tool in "${required_tools[@]}"; do
  [[ -x "${tool}" ]] || {
    printf 'Runner offline authority/adapter doubles v1 gate missing tool: %s\n' "${tool}" >&2
    exit 2
  }
done

cd "$(/usr/bin/dirname "${BASH_SOURCE[0]}")/.."
repo_root="$(builtin pwd -P)"
[[ "${repo_root}" == /* && "${repo_root}" != "*" && "${repo_root}" != *$'\n'* \
  && -d "${repo_root}" && ! -L "${repo_root}" ]] \
  || fail "repository root is not an exact canonical directory"

baseline_commit="08594b04fe9e23b11c70b3a5640c43ada9911a7b"
predecessor_source_commit="8002636128b530c3f9b1989f2894785be91b7c18"
predecessor_gate="scripts/check-biocortex-ab-track-b-reference-provider-fault-injection-runner-authority-and-adapter-contract-v1-pack.sh"
predecessor_expected="scripts/eval/fixtures/biocortex_ab_track_b_reference_provider_fault_injection_runner_authority_and_adapter_contract_v1_pack.expected.v0.tsv"
source_path="scripts/eval/biocortex_ab_track_b_reference_provider_fault_injection_runner_offline_authority_and_adapter_doubles_v1.py"
checker_path="scripts/eval/check_biocortex_ab_track_b_reference_provider_fault_injection_runner_offline_authority_and_adapter_doubles_v1_pack.py"
synthetic_path="scripts/eval/fixtures/biocortex_ab_track_b_reference_provider_fault_injection_runner_offline_authority_and_adapter_doubles_v1_pack_synthetic_v0.json"
expected_path="scripts/eval/fixtures/biocortex_ab_track_b_reference_provider_fault_injection_runner_offline_authority_and_adapter_doubles_v1_pack.expected.v0.tsv"
manifest_path="scripts/eval/fixtures/biocortex_ab_track_b_reference_provider_fault_injection_runner_offline_authority_and_adapter_doubles_v1_pack_v0.json"
report_path="docs/reports/goal-c-u/2026-07-16-biocortex-track-b-reference-provider-fault-injection-runner-offline-authority-and-adapter-doubles-v1-pack.md"
gate_path="scripts/check-biocortex-ab-track-b-reference-provider-fault-injection-runner-offline-authority-and-adapter-doubles-v1-pack.sh"

packet_paths=(
  "${source_path}" "${checker_path}" "${synthetic_path}" "${expected_path}"
  "${manifest_path}" "${report_path}" "${gate_path}"
)
packet_modes=(100644 100644 100644 100644 100644 100644 100755)
predecessor_paths=(
  "docs/design/fixtures/biocortex-ab-track-b-reference-provider-fault-injection-runner-adapter-contract-v1.json"
  "docs/design/fixtures/biocortex-ab-track-b-reference-provider-fault-injection-runner-authority-receipt-schema-v1.json"
  "docs/design/fixtures/biocortex-ab-track-b-reference-provider-fault-injection-runner-stop-receipt-schema-v1.json"
  "scripts/eval/biocortex_ab_track_b_reference_provider_fault_injection_runner_authority_and_adapter_contract_v1.py"
  "scripts/eval/check_biocortex_ab_track_b_reference_provider_fault_injection_runner_authority_and_adapter_contract_v1_pack.py"
  "scripts/eval/fixtures/biocortex_ab_track_b_reference_provider_fault_injection_runner_authority_and_adapter_contract_v1_pack_synthetic_v0.json"
  "scripts/eval/fixtures/biocortex_ab_track_b_reference_provider_fault_injection_runner_authority_and_adapter_contract_v1_pack.expected.v0.tsv"
  "scripts/eval/fixtures/biocortex_ab_track_b_reference_provider_fault_injection_runner_authority_and_adapter_contract_v1_pack_v0.json"
  "docs/reports/goal-c-u/2026-07-15-biocortex-track-b-reference-provider-fault-injection-runner-authority-and-adapter-contract-v1-pack.md"
  "${predecessor_gate}"
)
report_bound_paths=(
  "${source_path}" "${checker_path}" "${synthetic_path}" "${expected_path}"
  "${predecessor_paths[0]}" "${predecessor_paths[1]}" "${predecessor_paths[2]}"
  "${predecessor_paths[3]}" "${predecessor_paths[4]}" "${predecessor_paths[5]}"
  "${predecessor_paths[6]}" "${predecessor_paths[7]}" "${predecessor_paths[8]}"
  "${predecessor_paths[9]}"
)

frozen_manifest_sha256="01f41e7a7a6760641bafc53b51fa6ea406ef18403bb7318b4f1c282f3b091d9b"
frozen_checker_sha256="ed11f6d6c31812a70520a7fe30d7a5984a4e429598e102aa8540a18f2398789b"
frozen_expected_sha256="df468939b9cd8c0d1f5df9e4ddef1e00dcd5834a6b5bbcd683e6969ae9cbf303"
frozen_baseline_tree="9b88f614835751fe9e3b00cf4f904c1d837e6fc0"
frozen_baseline_parents="a255f504b282dc28a970c7ad0653050b4cd9d326 8002636128b530c3f9b1989f2894785be91b7c18"
frozen_predecessor_fast_sha256="486f66bc2bdbc82ff26a42f8e68cb9e305de52df1e2a05e288708a19b697cbb7"
frozen_predecessor_full_sha256="9d080cc8819e812379158625c159463cdab8ea391a3399f7e62d0554b14556e8"
frozen_predecessor_receipt_sha256="2882d134d9f8645877314bcf1a75b0e900e1c7ae41c49485fd75e6c3028e22e2"

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
  IFS=' ' read -r -a source_lineage \
    < <(git_clean rev-list --parents -n 1 "${source_commit}") \
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

tmp_base="$(/usr/bin/dirname "${repo_root}")/.ab-gate-tmp"
[[ ! -L "${tmp_base}" ]] || fail "gate temp base is a symlink"
if [[ ! -e "${tmp_base}" ]]; then /usr/bin/mkdir -m 0700 "${tmp_base}"; fi
[[ -d "${tmp_base}" && ! -L "${tmp_base}" \
  && "$(/usr/bin/stat -c '%u' "${tmp_base}")" == "${EUID}" \
  && "$(/usr/bin/stat -c '%a' "${tmp_base}")" == 700 ]] \
  || fail "gate temp base owner or mode drift"
tmp="$(/usr/bin/mktemp -d "${tmp_base}/runner-offline-doubles-v1.XXXXXX")"
cleanup() {
  /usr/bin/chmod -R u+w "${tmp}" 2>/dev/null || true
  /usr/bin/rm -rf "${tmp}" 2>/dev/null || true
  /usr/bin/rmdir "${tmp_base}" 2>/dev/null || true
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
  if [[ "${expected_mode}" == 100755 ]]; then
    [[ -x "${path}" ]] || fail "protected executable bit absent: ${path}"
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
verify_hash manifest "${frozen_manifest_sha256}" "${manifest_path}"
verify_hash checker "${frozen_checker_sha256}" "${checker_path}"
verify_hash expected "${frozen_expected_sha256}" "${expected_path}"

for seed in 0 314159; do
  /usr/bin/env -i PATH="${PATH}" HOME="${tmp}/home" LC_ALL=C TZ=UTC \
    PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1 PYTHONSAFEPATH=1 \
    PYTHONHASHSEED="${seed}" \
    /usr/bin/python3 -S -P "${tmp}/source-archive/${checker_path}" \
      --root "${tmp}/source-archive" >"${tmp}/source-${seed}.tsv"
  /usr/bin/cmp -s "${tmp}/source-archive/${expected_path}" "${tmp}/source-${seed}.tsv" \
    || fail "source checker drift for hash seed ${seed}"
done
/usr/bin/env -i PATH="${PATH}" HOME="${tmp}/home" LC_ALL=C TZ=UTC \
  PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1 PYTHONSAFEPATH=1 PYTHONHASHSEED=7 \
  /usr/bin/python3 -S -P "${tmp}/source-archive/${checker_path}" \
    --root "${tmp}/source-archive" --self-test >"${tmp}/source-self-test.tsv"
/usr/bin/cmp -s "${tmp}/source-archive/${expected_path}" "${tmp}/source-self-test.tsv" \
  || fail "source self-test checker drift"
/usr/bin/cmp -s "${tmp}/source-0.tsv" "${tmp}/source-self-test.tsv" \
  || fail "source checker is nondeterministic"
if [[ "${mode}" == integrated ]]; then
  /usr/bin/env -i PATH="${PATH}" HOME="${tmp}/home" LC_ALL=C TZ=UTC \
    PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1 PYTHONSAFEPATH=1 PYTHONHASHSEED=2718 \
    /usr/bin/python3 -S -P "${tmp}/head-archive/${checker_path}" \
      --root "${tmp}/head-archive" >"${tmp}/integrated.tsv"
  /usr/bin/cmp -s "${tmp}/head-archive/${expected_path}" "${tmp}/integrated.tsv" \
    || fail "integrated checker drift"
fi

[[ "$(/usr/bin/grep -Fxc -- '## Artifact binding' "${tmp}/source-archive/${report_path}")" == 1 ]] \
  || fail "report lacks exact-once Artifact binding heading"
: >"${tmp}/expected-report-bindings"
for path in "${report_bound_paths[@]}"; do
  digest="$(/usr/bin/sha256sum "${tmp}/source-archive/${path}" | /usr/bin/awk '{print $1}')"
  printf -- '- `%s`: `%s`\n' "${path}" "${digest}" >>"${tmp}/expected-report-bindings"
done
/usr/bin/awk '
  $0 == "## Artifact binding" { in_section = 1; next }
  in_section && /^## / { in_section = 0 }
  in_section && NF { print }
' "${tmp}/source-archive/${report_path}" >"${tmp}/actual-report-bindings"
/usr/bin/cmp -s "${tmp}/expected-report-bindings" "${tmp}/actual-report-bindings" \
  || fail "report Artifact binding catalog drift"

predecessor_repo="${tmp}/predecessor-repo"
if ! git_clean clone --no-local --no-checkout --no-tags --single-branch -- . "${predecessor_repo}" \
  >"${tmp}/clone.stdout" 2>"${tmp}/clone.stderr"; then
  /usr/bin/cat "${tmp}/clone.stderr" >&2
  fail "cannot clone isolated predecessor repository"
fi
git_clean -C "${predecessor_repo}" checkout --detach "${baseline_commit}" \
  >"${tmp}/checkout.stdout" 2>"${tmp}/checkout.stderr" \
  || { /usr/bin/cat "${tmp}/checkout.stderr" >&2; fail "cannot checkout predecessor"; }
[[ "$(git_clean -C "${predecessor_repo}" rev-parse HEAD)" == "${baseline_commit}" ]] \
  || fail "isolated predecessor HEAD drift"
[[ -z "$(git_clean -C "${predecessor_repo}" status --porcelain=v1 --untracked-files=all)" ]] \
  || fail "isolated predecessor is dirty before replay"

/usr/bin/cat "${predecessor_repo}/${predecessor_expected}" \
  >"${tmp}/expected-predecessor-fast.stdout"
/usr/bin/cat >>"${tmp}/expected-predecessor-fast.stdout" <<EOF
gate	FAST_PASS_NON_RELEASE_CONTENT_IDENTITY_ONLY
mode	integrated
source_commit	${predecessor_source_commit}
head	${baseline_commit}
predecessor_replay_receipt_sha256	${frozen_predecessor_receipt_sha256}
predecessor_full_replay	false
runtime_authority	false
validation_tier	FAST_CONTENT_IDENTITY_AND_FROZEN_RECEIPT
periodic_full_replay_required	true
release_evidence	false
fast_gate	VALID_FAST_CONTENT_IDENTITY_AND_FROZEN_RECEIPT
EOF
[[ "$(/usr/bin/sha256sum "${tmp}/expected-predecessor-fast.stdout" | /usr/bin/awk '{print $1}')" \
  == "${frozen_predecessor_fast_sha256}" ]] || fail "frozen predecessor fast receipt drift"

predecessor_tier=fast
predecessor_expected_receipt="${tmp}/expected-predecessor-fast.stdout"
predecessor_expected_sha256="${frozen_predecessor_fast_sha256}"
predecessor_full_replay=false
if [[ "${validation_tier}" == full-replay ]]; then
  /usr/bin/cat "${predecessor_repo}/${predecessor_expected}" \
    >"${tmp}/expected-predecessor-full.stdout"
  /usr/bin/cat >>"${tmp}/expected-predecessor-full.stdout" <<EOF
integration_gate	VALID_INTEGRATED_BIOCORTEX_AB_TRACK_B_REFERENCE_PROVIDER_FAULT_INJECTION_RUNNER_AUTHORITY_AND_ADAPTER_CONTRACT_V1_PACK
gate	PASS
mode	integrated
source_commit	${predecessor_source_commit}
head	${baseline_commit}
predecessor_replay_receipt_sha256	${frozen_predecessor_receipt_sha256}
predecessor_full_replay	true
runtime_authority	false
validation_tier	PERIODIC_FULL_FROZEN_CHAIN_REPLAY
periodic_full_replay_required	false
release_evidence	true
full_replay_gate	VALID_PERIODIC_FULL_FROZEN_CHAIN_REPLAY
EOF
  [[ "$(/usr/bin/sha256sum "${tmp}/expected-predecessor-full.stdout" | /usr/bin/awk '{print $1}')" \
    == "${frozen_predecessor_full_sha256}" ]] || fail "frozen predecessor full receipt drift"
  predecessor_tier=full-replay
  predecessor_expected_receipt="${tmp}/expected-predecessor-full.stdout"
  predecessor_expected_sha256="${frozen_predecessor_full_sha256}"
  predecessor_full_replay=true
fi
if ! (
  cd "${predecessor_repo}"
  "${predecessor_gate}" "${predecessor_tier}"
) >"${tmp}/predecessor.stdout" 2>"${tmp}/predecessor.stderr"; then
  /usr/bin/cat "${tmp}/predecessor.stderr" >&2
  fail "predecessor ${predecessor_tier} replay failed"
fi
/usr/bin/cmp -s "${predecessor_expected_receipt}" "${tmp}/predecessor.stdout" \
  || fail "predecessor ${predecessor_tier} receipt byte drift"
[[ "$(/usr/bin/sha256sum "${tmp}/predecessor.stdout" | /usr/bin/awk '{print $1}')" \
  == "${predecessor_expected_sha256}" ]] || fail "predecessor receipt hash mismatch"
[[ -z "$(git_clean -C "${predecessor_repo}" status --porcelain=v1 --untracked-files=all)" ]] \
  || fail "predecessor replay dirtied isolated repository"

git_clean diff --check "${baseline_commit}" "${source_commit}"
[[ "$(git_clean rev-parse HEAD)" == "${head_oid}" ]] || fail "HEAD changed during gate"
[[ -z "$(git_clean status --porcelain=v1 --untracked-files=all)" ]] \
  || fail "verification dirtied worktree or index"

source_result="$(/usr/bin/cat "${tmp}/source-0.tsv")"
/usr/bin/chmod -R u+w "${tmp}" || fail "cannot make temp tree removable"
/usr/bin/rm -rf "${tmp}" || fail "cannot remove temp tree"
/usr/bin/rmdir "${tmp_base}" 2>/dev/null || true
trap - EXIT

printf '%s\n' "${source_result}"
if [[ "${validation_tier}" == full-replay ]]; then
  if [[ "${mode}" == integrated ]]; then
    printf 'integration_gate\tVALID_INTEGRATED_BIOCORTEX_AB_TRACK_B_REFERENCE_PROVIDER_FAULT_INJECTION_RUNNER_OFFLINE_AUTHORITY_AND_ADAPTER_DOUBLES_V1_PACK\n'
  else
    printf 'source_gate\tVALID_SOURCE_BIOCORTEX_AB_TRACK_B_REFERENCE_PROVIDER_FAULT_INJECTION_RUNNER_OFFLINE_AUTHORITY_AND_ADAPTER_DOUBLES_V1_PACK\n'
  fi
  printf 'gate\tPASS\n'
else
  printf 'gate\tFAST_PASS_NON_RELEASE_CONTENT_IDENTITY_ONLY\n'
fi
printf 'mode\t%s\n' "${mode}"
printf 'source_commit\t%s\n' "${source_commit}"
printf 'head\t%s\n' "${head_oid}"
printf 'predecessor_receipt_sha256\t%s\n' "${predecessor_expected_sha256}"
printf 'predecessor_full_replay\t%s\n' "${predecessor_full_replay}"
printf 'runtime_authority\tfalse\n'
if [[ "${validation_tier}" == fast ]]; then
  printf 'validation_tier\tFAST_CONTENT_IDENTITY_AND_PREDECESSOR_FAST_REPLAY\n'
  printf 'periodic_full_replay_required\ttrue\n'
  printf 'artifact_release_evidence\tfalse\n'
  printf 'fast_gate\tVALID_FAST_OFFLINE_DOUBLE_CONTENT_AND_PREDECESSOR_REPLAY\n'
else
  printf 'validation_tier\tPERIODIC_FULL_FROZEN_CHAIN_REPLAY\n'
  printf 'periodic_full_replay_required\tfalse\n'
  printf 'artifact_release_evidence\ttrue\n'
  printf 'full_replay_gate\tVALID_OFFLINE_DOUBLE_PACKET_AND_FULL_FROZEN_PREDECESSOR_CHAIN\n'
fi
