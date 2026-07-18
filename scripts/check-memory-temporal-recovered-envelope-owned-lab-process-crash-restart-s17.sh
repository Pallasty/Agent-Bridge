#!/usr/bin/env -S -i /usr/bin/bash
# Source-bound gate for the S17 owned-lab process-crash preregistration.
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
unset GIT_NAMESPACE GIT_SHALLOW_FILE GIT_CEILING_DIRECTORIES
unset GIT_DISCOVERY_ACROSS_FILESYSTEM
export GIT_CONFIG_NOSYSTEM=1
export GIT_CONFIG_GLOBAL=/dev/null
export GIT_CONFIG_SYSTEM=/dev/null

fail() {
  printf 'S17 owned-lab process-crash preregistration gate failed: %s\n' "$*" >&2
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
  /usr/bin/dirname /usr/bin/env /usr/bin/find /usr/bin/findmnt /usr/bin/git
  /usr/bin/grep /usr/bin/mkdir /usr/bin/mktemp /usr/bin/python3 /usr/bin/rm
  /usr/bin/rmdir /usr/bin/sha256sum /usr/bin/sort /usr/bin/stat /usr/bin/tail
  /usr/bin/tar
)
for tool in "${required_tools[@]}"; do
  [[ -x "${tool}" ]] || {
    printf 'S17 owned-lab process-crash preregistration missing tool: %s\n' "${tool}" >&2
    exit 2
  }
done

cd "$(/usr/bin/dirname "${BASH_SOURCE[0]}")/.."
repo_root="$(builtin pwd -P)"
[[ "${repo_root}" == /* && "${repo_root}" != "*" && "${repo_root}" != *$'\n'* \
  && -d "${repo_root}" && ! -L "${repo_root}" ]] \
  || fail "repository root is not one canonical directory"

baseline_commit="d5bbe55d5d95b1163e287415f437cf77c594135d"
frozen_baseline_tree="6fd22d3e8abba06ae5eab26c9c9ce2af5672ada9"
frozen_baseline_parents="3d03193b645ded944b10a310633be8d6a2c1ab1b 0268990ee74a6a958269d1c07f7d575d0284e6bf"
s16_integration_commit="d7f3e206169227905dbd320f1876de46e3facfea"
s16_source_commit="dca7436a9d9df990355d67e374184202332f0354"
s16_gate="scripts/check-memory-temporal-recovered-envelope-durability-fault-model-s16.sh"
runtime_boundary_gate="scripts/check-biocortex-ab-track-b-reference-provider-fault-injection-runner-runtime-prerequisite-evidence-packet-offline-integration-and-production-evidence-ingestion-boundary-review-v1-pack.sh"
frozen_s16_gate_sha256="207f4d3d98f7152efe37645a78e66cd8afc3ed6983f412d15c206129b60b5007"
frozen_runtime_boundary_gate_sha256="e2a3e5fd49ebd58697838bc3f7e1860ce511f225a4bdd11ac8f2772bd8087cf7"

design_path="docs/design/MEMORY_TEMPORAL_RECOVERED_ENVELOPE_OWNED_LAB_PROCESS_CRASH_RESTART_PREREGISTRATION_S17_2026_07_17.md"
plan_path="docs/design/fixtures/biocortex-ab-track-b-recovered-envelope-owned-lab-process-crash-restart-plan-s17-v0.json"
observation_schema_path="docs/design/fixtures/biocortex-ab-track-b-recovered-envelope-owned-lab-process-crash-restart-observation-schema-s17-v0.json"
owner_schema_path="docs/design/fixtures/biocortex-ab-track-b-recovered-envelope-owned-lab-owner-resource-decision-schema-s17-v0.json"
successor_gate_path="docs/design/fixtures/biocortex-ab-track-b-successor-admission-gate-s17-v0.json"
report_path="docs/reports/goal-c-u/2026-07-17-biocortex-ab-track-b-recovered-envelope-owned-lab-process-crash-restart-preregistration-s17.md"
checker_path="scripts/eval/check_memory_temporal_recovered_envelope_owned_lab_process_crash_restart_s17.py"
synthetic_fixture_path="scripts/eval/fixtures/memory_temporal_recovered_envelope_owned_lab_process_crash_restart_s17.synthetic.v0.json"
expected_path="scripts/eval/fixtures/memory_temporal_recovered_envelope_owned_lab_process_crash_restart_s17.expected.v0.tsv"
gate_path="scripts/check-memory-temporal-recovered-envelope-owned-lab-process-crash-restart-s17.sh"

packet_paths=(
  "${design_path}" "${plan_path}" "${observation_schema_path}"
  "${owner_schema_path}" "${successor_gate_path}" "${report_path}"
  "${checker_path}" "${synthetic_fixture_path}" "${expected_path}"
  "${gate_path}"
)
packet_modes=(100644 100644 100644 100644 100644 100644 100644 100644 100644 100755)

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
for commit in "${baseline_commit}" "${s16_integration_commit}" "${s16_source_commit}"; do
  [[ "$(git_clean cat-file -t "${commit}")" == commit ]] \
    || fail "frozen commit is unavailable: ${commit}"
done
[[ "$(git_clean show -s --format='%T' "${baseline_commit}")" == "${frozen_baseline_tree}" ]] \
  || fail "baseline tree drift"
[[ "$(git_clean show -s --format='%P' "${baseline_commit}")" == "${frozen_baseline_parents}" ]] \
  || fail "baseline parent topology drift"
git_clean merge-base --is-ancestor "${s16_integration_commit}" "${baseline_commit}" \
  || fail "S16 integration is not retained by the source baseline"
[[ "$(git_clean show "${baseline_commit}:${s16_gate}" | /usr/bin/sha256sum \
  | /usr/bin/awk '{print $1}')" == "${frozen_s16_gate_sha256}" ]] \
  || fail "frozen S16 gate bytes drift"
[[ "$(git_clean show "${baseline_commit}:${runtime_boundary_gate}" | /usr/bin/sha256sum \
  | /usr/bin/awk '{print $1}')" == "${frozen_runtime_boundary_gate_sha256}" ]] \
  || fail "frozen runtime-boundary gate bytes drift"

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
    fail "integrated first parent already contains the S17 packet"
  else
    source_exclusion_status=$?
    [[ "${source_exclusion_status}" == 1 ]] || fail "cannot establish source exclusion"
  fi
else
  fail "HEAD is neither exact source nor ordinary two-parent integration"
fi

[[ "${#packet_paths[@]}" == 10 && "${#packet_modes[@]}" == 10 ]] \
  || fail "S17 packet catalog cardinality drift"

tmp_base="/Data/CascadeProjects/.ab-gate-tmp"
tmp_base_created=false
if [[ ! -e "${tmp_base}" ]]; then
  /usr/bin/mkdir -m 0700 "${tmp_base}"
  tmp_base_created=true
fi
[[ -d "${tmp_base}" && ! -L "${tmp_base}" \
  && "$(cd "${tmp_base}" && builtin pwd -P)" == "${tmp_base}" \
  && "$(/usr/bin/stat -c '%u' "${tmp_base}")" == "${EUID}" \
  && "$(/usr/bin/stat -c '%a' "${tmp_base}")" == 700 ]] \
  || fail "gate scratch root owner, mode, type, or canonical path drift"
scratch_fstype="$(/usr/bin/findmnt -T "${tmp_base}" -n -o FSTYPE)" \
  || fail "cannot resolve gate scratch filesystem"
case "${scratch_fstype,,}" in
  tmpfs|ramfs|fuse*) fail "gate scratch requires persistent non-FUSE storage" ;;
esac
tmp="$(/usr/bin/mktemp -d "${tmp_base}/s17-prereg.XXXXXXXX")"
cleanup() {
  /usr/bin/chmod -R u+w "${tmp}" 2>/dev/null || true
  /usr/bin/rm -rf "${tmp}" 2>/dev/null || true
  if [[ "${tmp_base_created}" == true ]]; then
    /usr/bin/rmdir "${tmp_base}" 2>/dev/null || true
  fi
}
trap cleanup EXIT
/usr/bin/mkdir -m 0700 "${tmp}/source" "${tmp}/head" "${tmp}/history"

: >"${tmp}/expected-delta"
for path in "${packet_paths[@]}"; do
  printf 'A\t%s\n' "${path}" >>"${tmp}/expected-delta"
done
/usr/bin/sort "${tmp}/expected-delta" -o "${tmp}/expected-delta"
git_clean diff-tree --no-commit-id --name-status -r \
  "${baseline_commit}" "${source_commit}" | /usr/bin/sort >"${tmp}/actual-source-delta"
/usr/bin/cmp -s "${tmp}/expected-delta" "${tmp}/actual-source-delta" \
  || fail "source is not the exact ten-path all-add packet"
if [[ "${mode}" == integrated ]]; then
  git_clean diff-tree --no-commit-id --name-status -r \
    "${first_parent}" "${head_oid}" | /usr/bin/sort >"${tmp}/actual-integration-delta"
  /usr/bin/cmp -s "${tmp}/expected-delta" "${tmp}/actual-integration-delta" \
    || fail "integration is not the exact ten-path all-add packet over its first parent"
fi

for index in "${!packet_paths[@]}"; do
  path="${packet_paths[${index}]}"
  expected_mode="${packet_modes[${index}]}"
  if git_clean cat-file -e "${baseline_commit}:${path}" 2>/dev/null; then
    fail "S17 packet path already exists at baseline: ${path}"
  fi
  source_entry="$(git_clean ls-tree "${source_commit}" -- "${path}")"
  [[ "${source_entry}" == "${expected_mode} blob "* ]] \
    || fail "S17 source path mode or type drift: ${path}"
  head_entry="$(git_clean ls-tree "${head_oid}" -- "${path}")"
  [[ "${head_entry}" == "${source_entry}" ]] \
    || fail "S17 source/head mode, type, blob, or path entry differs: ${path}"
  [[ "$(git_clean rev-parse "${source_commit}:${path}")" \
    == "$(git_clean rev-parse "${head_oid}:${path}")" ]] \
    || fail "S17 source bytes changed at HEAD: ${path}"
  if [[ "${mode}" == integrated ]]; then
    if git_clean cat-file -e "${first_parent}:${path}" 2>/dev/null; then
      fail "integration first parent already contains S17 path: ${path}"
    fi
  fi
done

git_clean archive --format=tar "${source_commit}" | /usr/bin/tar -xf - -C "${tmp}/source"
git_clean archive --format=tar "${head_oid}" | /usr/bin/tar -xf - -C "${tmp}/head"
for path in "${packet_paths[@]}"; do
  /usr/bin/cmp -s "${tmp}/source/${path}" "${tmp}/head/${path}" \
    || fail "source/head archive bytes differ: ${path}"
done

for seed in 1 777; do
  (
    cd "${tmp}/head"
    /usr/bin/env -i PATH=/usr/bin:/bin LC_ALL=C TZ=UTC \
      PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1 PYTHONSAFEPATH=1 \
      PYTHONHASHSEED="${seed}" /usr/bin/python3 -S -P "${checker_path}"
  ) >"${tmp}/checker-${seed}.tsv" \
    || fail "S17 independent checker failed for hash seed ${seed}"
  /usr/bin/cmp -s "${tmp}/checker-${seed}.tsv" "${tmp}/head/${expected_path}" \
    || fail "S17 checker output differs from frozen oracle for seed ${seed}"
done
/usr/bin/cmp -s "${tmp}/checker-1.tsv" "${tmp}/checker-777.tsv" \
  || fail "S17 checker output is nondeterministic"
(
  cd "${tmp}/head"
  /usr/bin/env -i PATH=/usr/bin:/bin LC_ALL=C TZ=UTC \
    PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1 PYTHONSAFEPATH=1 \
    PYTHONHASHSEED=31337 /usr/bin/python3 -S -P "${checker_path}" --self-test \
    >"${tmp}/self-test.tsv"
) || fail "S17 directed mutation self-test failed"

for path in "${plan_path}" "${observation_schema_path}" "${owner_schema_path}" \
  "${successor_gate_path}" "${synthetic_fixture_path}" "${checker_path}" \
  "${expected_path}" "${gate_path}"; do
  digest="$(/usr/bin/sha256sum "${tmp}/head/${path}" | /usr/bin/awk '{print $1}')"
  /usr/bin/grep -Fq -- "\`${path}\`: \`${digest}\`" "${tmp}/head/${report_path}" \
    || fail "report does not bind protected artifact path and digest on one line: ${path}"
done

frozen_s16_replay="NOT_RUN_FAST_TIER"
frozen_runtime_boundary_replay="NOT_RUN_FAST_TIER"
if [[ "${validation_tier}" == full-replay ]]; then
  /usr/bin/git clone --quiet --no-local --no-hardlinks --no-tags \
    "${repo_root}" "${tmp}/history/repo" \
    || fail "cannot create isolated predecessor replay repository"
  [[ ! -e "${tmp}/history/repo/.git/objects/info/alternates" ]] \
    || fail "isolated predecessor replay repository uses alternates"
  (
    cd "${tmp}/history/repo"
    /usr/bin/git checkout --quiet --detach "${baseline_commit}"
    /usr/bin/bash "${runtime_boundary_gate}" full-replay \
      >"${tmp}/runtime-boundary-replay.log" 2>&1
  ) || {
    /usr/bin/tail -n 80 "${tmp}/runtime-boundary-replay.log" >&2 || true
    fail "frozen runtime-ingestion boundary replay failed"
  }
  frozen_runtime_boundary_replay="PASS"
  (
    cd "${tmp}/history/repo"
    /usr/bin/git checkout --quiet --detach "${s16_integration_commit}"
    /usr/bin/bash "${s16_gate}" \
      >"${tmp}/s16-replay.log" 2>&1
  ) || {
    /usr/bin/tail -n 80 "${tmp}/s16-replay.log" >&2 || true
    fail "frozen S16 integrated gate replay failed"
  }
  frozen_s16_replay="PASS"
fi

[[ "$(git_clean rev-parse HEAD)" == "${head_oid}" ]] \
  || fail "HEAD changed during verification"
[[ -z "$(git_clean status --porcelain=v1 --untracked-files=all)" ]] \
  || fail "verification dirtied worktree or index"

/usr/bin/cat "${tmp}/checker-1.tsv"
if [[ "${mode}" == source ]]; then
  printf 'source_gate\tVALID_SOURCE_BIOCORTEX_AB_TRACK_B_RECOVERED_ENVELOPE_OWNED_LAB_PROCESS_CRASH_RESTART_PREREGISTRATION_S17\n'
else
  printf 'integration_gate\tVALID_INTEGRATED_BIOCORTEX_AB_TRACK_B_RECOVERED_ENVELOPE_OWNED_LAB_PROCESS_CRASH_RESTART_PREREGISTRATION_S17\n'
fi
printf 'frozen_runtime_ingestion_boundary_replay\t%s\n' "${frozen_runtime_boundary_replay}"
printf 'frozen_s16_integrated_gate_replay\t%s\n' "${frozen_s16_replay}"
if [[ "${validation_tier}" == fast ]]; then
  printf 'validation_tier\tFAST_CONTENT_IDENTITY_ONLY_NO_PREDECESSOR_REPLAY\n'
  printf 'periodic_full_replay_required\ttrue\n'
  printf 'release_status\tNON_RELEASE\n'
  printf 'gate\tFAST_PASS_NON_RELEASE_CONTENT_IDENTITY_ONLY\n'
else
  printf 'validation_tier\tFULL_TWO_DIRECT_PREDECESSOR_CHAIN_REPLAY\n'
  printf 'periodic_full_replay_required\tfalse\n'
  printf 'release_status\tRELEASE_VALIDATION_PASS\n'
  printf 'gate\tPASS\n'
fi
printf 'mode\t%s\n' "${mode}"
printf 'baseline\t%s\n' "${baseline_commit}"
printf 'source_commit\t%s\n' "${source_commit}"
if [[ "${mode}" == integrated ]]; then
  printf 'integration_commit\t%s\n' "${head_oid}"
fi
printf 'head\t%s\n' "${head_oid}"
printf 'gate_sha256\t%s\n' "$(/usr/bin/sha256sum "${gate_path}" | /usr/bin/awk '{print $1}')"
