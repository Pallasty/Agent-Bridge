#!/usr/bin/env -S -i /usr/bin/bash
# Source-bound gate for the S18 authenticated-unclaimed owner envelope verifier.
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
unset CARGO_ENCODED_RUSTFLAGS CARGO_HOME RUSTUP_HOME RUSTC_WRAPPER RUSTC_WORKSPACE_WRAPPER
unset GIT_DIR GIT_WORK_TREE GIT_COMMON_DIR GIT_INDEX_FILE
unset GIT_OBJECT_DIRECTORY GIT_ALTERNATE_OBJECT_DIRECTORIES
unset GIT_REPLACE_REF_BASE GIT_CONFIG GIT_CONFIG_COUNT GIT_CONFIG_PARAMETERS
unset GIT_NAMESPACE GIT_SHALLOW_FILE GIT_CEILING_DIRECTORIES
unset GIT_DISCOVERY_ACROSS_FILESYSTEM
export GIT_CONFIG_NOSYSTEM=1
export GIT_CONFIG_GLOBAL=/dev/null
export GIT_CONFIG_SYSTEM=/dev/null

fail() {
  printf 'S18 owned-lab authorization verifier gate failed: %s\n' "$*" >&2
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
  /usr/bin/cp /usr/bin/dirname /usr/bin/env /usr/bin/find /usr/bin/findmnt
  /usr/bin/git /usr/bin/grep /usr/bin/mkdir /usr/bin/mktemp /usr/bin/python3
  /usr/bin/rm /usr/bin/rmdir /usr/bin/sha256sum /usr/bin/sort /usr/bin/stat
  /usr/bin/tail /usr/bin/tar /home/pallasting/.cargo/bin/cargo
  /home/pallasting/.cargo/bin/rustc /home/pallasting/.cargo/bin/rustfmt
)
for tool in "${required_tools[@]}"; do
  [[ -x "${tool}" ]] || fail "missing required tool: ${tool}"
done

cd "$(/usr/bin/dirname "${BASH_SOURCE[0]}")/.."
repo_root="$(builtin pwd -P)"
[[ "${repo_root}" == /* && -d "${repo_root}" && ! -L "${repo_root}" ]] \
  || fail "repository root is not one canonical directory"

baseline_commit="d0356dbdbd7239ffab972ee21da81891210a055b"
frozen_baseline_tree="b40c36c5fe73af3079bf3a81d69480d2555271d8"
frozen_baseline_parents="3bf8ad3a67ff02a4e717db8e29e89079f66c01cf 20368c626bf34c5a1edd07391014ab8716536e7e"
s17_gate="scripts/check-memory-temporal-recovered-envelope-owned-lab-process-crash-restart-s17.sh"
frozen_s17_gate_sha256="00b93ec57bbb60695061caf31152d97454936aa1ee7100cff0e6aa6a2f469687"
feature="temporal-evidence-s18-owned-lab-authorization-verifier-synthetic"

cargo_path="crates/store/Cargo.toml"
parent_module_path="crates/store/src/temporal_replay_transport/recovered_s9_decision_reverification/recovered_envelope_delivery/recovered_envelope_source/bounded_runtime_adapter/durability_fault_model.rs"
rust_source_path="crates/store/src/temporal_replay_transport/recovered_s9_decision_reverification/recovered_envelope_delivery/recovered_envelope_source/bounded_runtime_adapter/durability_fault_model/owned_lab_owner_resource_authorization.rs"
design_path="docs/design/MEMORY_TEMPORAL_OWNED_LAB_AUTHORIZATION_ENVELOPE_VERIFIER_S18_2026_07_17.md"
contract_path="docs/design/fixtures/biocortex-ab-track-b-owned-lab-authorization-validator-contract-s18-v0.json"
status_path="docs/design/fixtures/biocortex-ab-track-b-owned-lab-authorization-validator-status-s18-v0.json"
anchor_schema_path="docs/design/fixtures/biocortex-ab-track-b-owned-lab-owner-trust-anchor-schema-s18-v0.json"
envelope_schema_path="docs/design/fixtures/biocortex-ab-track-b-owned-lab-owner-authorization-envelope-schema-s18-v0.json"
successor_path="docs/design/fixtures/biocortex-ab-track-b-successor-admission-gate-s18-v0.json"
report_path="docs/reports/goal-c-u/2026-07-17-biocortex-ab-track-b-owned-lab-authorization-envelope-verifier-s18.md"
checker_path="scripts/eval/check_memory_temporal_owned_lab_authorization_envelope_verifier_s18.py"
expected_path="scripts/eval/fixtures/memory_temporal_owned_lab_authorization_envelope_verifier_s18.expected.v0.tsv"
gate_path="scripts/check-memory-temporal-owned-lab-authorization-envelope-verifier-s18.sh"

packet_paths=(
  "${cargo_path}" "${parent_module_path}" "${rust_source_path}" "${design_path}"
  "${contract_path}" "${status_path}" "${anchor_schema_path}"
  "${envelope_schema_path}" "${successor_path}" "${report_path}"
  "${checker_path}" "${expected_path}" "${gate_path}"
)
packet_modes=(100644 100644 100644 100644 100644 100644 100644 100644 100644 100644 100644 100644 100755)
frozen_s17_head_paths=(
  "docs/design/fixtures/biocortex-ab-track-b-recovered-envelope-owned-lab-process-crash-restart-plan-s17-v0.json"
  "docs/design/fixtures/biocortex-ab-track-b-recovered-envelope-owned-lab-process-crash-restart-observation-schema-s17-v0.json"
  "docs/design/fixtures/biocortex-ab-track-b-recovered-envelope-owned-lab-owner-resource-decision-schema-s17-v0.json"
  "docs/design/fixtures/biocortex-ab-track-b-successor-admission-gate-s17-v0.json"
  "scripts/eval/check_memory_temporal_recovered_envelope_owned_lab_process_crash_restart_s17.py"
  "scripts/check-memory-temporal-recovered-envelope-owned-lab-process-crash-restart-s17.sh"
  "scripts/eval/check_memory_temporal_recovered_envelope_durability_fault_model_s16.py"
  "scripts/eval/check_memory_temporal_recovered_envelope_source_s14.py"
  "scripts/eval/check_memory_temporal_recovered_s9_decision_reverification_s12.py"
  "scripts/eval/check_memory_temporal_external_authority_provider_s9.py"
)

git_clean() {
  /usr/bin/git --no-pager --no-replace-objects -c core.fsmonitor=false \
    -c core.attributesFile=/dev/null -c core.commitGraph=false \
    -c core.hooksPath=/dev/null -c safe.directory="${repo_root}" "$@"
}

[[ "$(git_clean config --get-all safe.directory)" == "${repo_root}" ]] \
  || fail "Git trust scope is not the exact repository root"
head_oid="$(git_clean rev-parse HEAD)" || fail "cannot resolve HEAD"
[[ "$(git_clean rev-parse --is-shallow-repository)" == false ]] || fail "shallow history"
[[ -z "$(git_clean for-each-ref --format='%(refname)' refs/replace)" ]] || fail "Git replace refs"
[[ "$(git_clean cat-file -t "${baseline_commit}")" == commit ]] || fail "baseline unavailable"
[[ "$(git_clean show -s --format='%T' "${baseline_commit}")" == "${frozen_baseline_tree}" ]] || fail "baseline tree drift"
[[ "$(git_clean show -s --format='%P' "${baseline_commit}")" == "${frozen_baseline_parents}" ]] || fail "baseline topology drift"
[[ "$(git_clean show "${baseline_commit}:${s17_gate}" | /usr/bin/sha256sum | /usr/bin/awk '{print $1}')" == "${frozen_s17_gate_sha256}" ]] || fail "frozen S17 gate drift"
[[ -z "$(git_clean status --porcelain=v1 --untracked-files=all)" ]] || fail "worktree or index is not clean"

head_lineage=()
IFS=' ' read -r -a head_lineage < <(git_clean rev-list --parents -n 1 "${head_oid}") || fail "cannot resolve HEAD topology"
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
  [[ "$(git_clean show -s --format='%P' "${source_commit}")" == "${baseline_commit}" ]] || fail "integrated second parent is not exact source"
  git_clean merge-base --is-ancestor "${baseline_commit}" "${first_parent}" || fail "first parent does not descend from baseline"
  if git_clean merge-base --is-ancestor "${source_commit}" "${first_parent}"; then
    fail "first parent already contains source"
  else
    [[ "$?" == 1 ]] || fail "cannot establish source exclusion"
  fi
else
  fail "HEAD is neither exact source nor ordinary two-parent integration"
fi

[[ "${#packet_paths[@]}" == 13 && "${#packet_modes[@]}" == 13 ]] || fail "packet catalog cardinality drift"
tmp_base="/Data/CascadeProjects/.ab-gate-tmp"
tmp_base_created=false
if [[ ! -e "${tmp_base}" ]]; then
  /usr/bin/mkdir -m 0700 "${tmp_base}"
  tmp_base_created=true
fi
[[ -d "${tmp_base}" && ! -L "${tmp_base}" && "$(/usr/bin/stat -c '%u' "${tmp_base}")" == "${EUID}" && "$(/usr/bin/stat -c '%a' "${tmp_base}")" == 700 ]] || fail "scratch root drift"
scratch_fstype="$(/usr/bin/findmnt -T "${tmp_base}" -n -o FSTYPE)" || fail "cannot resolve scratch filesystem"
case "${scratch_fstype,,}" in tmpfs|ramfs|fuse*) fail "persistent non-FUSE scratch required" ;; esac
tmp="$(/usr/bin/mktemp -d "${tmp_base}/s18-auth.XXXXXXXX")"
cleanup() {
  /usr/bin/chmod -R u+w "${tmp}" 2>/dev/null || true
  /usr/bin/rm -rf "${tmp}" 2>/dev/null || true
  if [[ "${tmp_base_created}" == true ]]; then /usr/bin/rmdir "${tmp_base}" 2>/dev/null || true; fi
}
trap cleanup EXIT
/usr/bin/mkdir -m 0700 "${tmp}/source" "${tmp}/head" "${tmp}/history" "${tmp}/home" "${tmp}/cargo-tmp"

: >"${tmp}/expected-delta"
printf 'M\t%s\n' "${cargo_path}" "${parent_module_path}" >>"${tmp}/expected-delta"
for path in "${packet_paths[@]:2}"; do printf 'A\t%s\n' "${path}" >>"${tmp}/expected-delta"; done
/usr/bin/sort "${tmp}/expected-delta" -o "${tmp}/expected-delta"
git_clean diff-tree --no-commit-id --name-status -r "${baseline_commit}" "${source_commit}" | /usr/bin/sort >"${tmp}/actual-source-delta"
/usr/bin/cmp -s "${tmp}/expected-delta" "${tmp}/actual-source-delta" || fail "source is not exact 13-path delta"
if [[ "${mode}" == integrated ]]; then
  git_clean diff-tree --no-commit-id --name-status -r "${first_parent}" "${head_oid}" | /usr/bin/sort >"${tmp}/actual-integration-delta"
  /usr/bin/cmp -s "${tmp}/expected-delta" "${tmp}/actual-integration-delta" || fail "integration is not exact 13-path delta"
fi

for index in "${!packet_paths[@]}"; do
  path="${packet_paths[${index}]}"
  expected_mode="${packet_modes[${index}]}"
  if (( index < 2 )); then
    git_clean cat-file -e "${baseline_commit}:${path}" || fail "modified baseline path missing: ${path}"
  elif git_clean cat-file -e "${baseline_commit}:${path}" 2>/dev/null; then
    fail "new S18 path already exists at baseline: ${path}"
  fi
  source_entry="$(git_clean ls-tree "${source_commit}" -- "${path}")"
  [[ "${source_entry}" == "${expected_mode} blob "* ]] || fail "source path mode/type drift: ${path}"
  head_entry="$(git_clean ls-tree "${head_oid}" -- "${path}")"
  [[ "${head_entry}" == "${source_entry}" ]] || fail "source/head entry differs: ${path}"
  if [[ "${mode}" == integrated && $index -ge 2 ]] && git_clean cat-file -e "${first_parent}:${path}" 2>/dev/null; then
    fail "integration first parent already has new S18 path: ${path}"
  fi
done

git_clean archive --format=tar "${source_commit}" | /usr/bin/tar -xf - -C "${tmp}/source"
git_clean archive --format=tar "${head_oid}" | /usr/bin/tar -xf - -C "${tmp}/head"
for path in "${packet_paths[@]}"; do /usr/bin/cmp -s "${tmp}/source/${path}" "${tmp}/head/${path}" || fail "source/head bytes differ: ${path}"; done
for path in "${frozen_s17_head_paths[@]}"; do
  [[ -f "${tmp}/head/${path}" && ! -L "${tmp}/head/${path}" ]] || fail "frozen S17 HEAD path is not a regular file: ${path}"
  git_clean show "${baseline_commit}:${path}" | /usr/bin/cmp -s - "${tmp}/head/${path}" \
    || fail "frozen S17 HEAD path differs from baseline before Python execution: ${path}"
done

for seed in 1 777; do
  (
    cd "${tmp}/head"
    /usr/bin/env -i PATH=/usr/bin:/bin LC_ALL=C TZ=UTC PYTHONDONTWRITEBYTECODE=1 \
      PYTHONNOUSERSITE=1 PYTHONSAFEPATH=1 PYTHONHASHSEED="${seed}" \
      /usr/bin/python3 -S -P "${checker_path}"
  ) >"${tmp}/checker-${seed}.tsv" || fail "checker failed for hash seed ${seed}"
  /usr/bin/cmp -s "${tmp}/checker-${seed}.tsv" "${tmp}/head/${expected_path}" || fail "checker differs from frozen oracle for seed ${seed}"
done
/usr/bin/cmp -s "${tmp}/checker-1.tsv" "${tmp}/checker-777.tsv" || fail "checker output is nondeterministic"
(
  cd "${tmp}/head"
  /usr/bin/env -i PATH=/usr/bin:/bin LC_ALL=C TZ=UTC PYTHONDONTWRITEBYTECODE=1 \
    PYTHONNOUSERSITE=1 PYTHONSAFEPATH=1 PYTHONHASHSEED=31337 \
    /usr/bin/python3 -S -P "${checker_path}" --self-test >"${tmp}/self-test.tsv"
) || fail "directed mutation self-test failed"

(
  cd "${tmp}/head"
  /usr/bin/env -i PATH=/usr/bin:/bin LC_ALL=C TZ=UTC PYTHONNOUSERSITE=1 \
    /usr/bin/python3 -P - "${anchor_schema_path}" "${envelope_schema_path}" <<'PY'
import json, sys
from jsonschema import Draft202012Validator
for path in sys.argv[1:]:
    with open(path, "r", encoding="utf-8") as handle:
        schema = json.load(handle)
    Draft202012Validator.check_schema(schema)
PY
) || fail "official Draft 2020-12 metaschema validation failed"

for path in "${cargo_path}" "${parent_module_path}" "${design_path}" \
  "${contract_path}" "${status_path}" "${anchor_schema_path}" \
  "${envelope_schema_path}" "${successor_path}" "${rust_source_path}" \
  "${checker_path}" "${expected_path}" "${gate_path}"; do
  digest="$(/usr/bin/sha256sum "${tmp}/head/${path}" | /usr/bin/awk '{print $1}')"
  /usr/bin/grep -Fq -- "- \`${path}\`: \`${digest}\`" "${tmp}/head/${report_path}" || fail "report does not bind ${path}"
done

rust_verifier_replay="NOT_RUN_FAST_TIER"
frozen_s17_replay="NOT_RUN_FAST_TIER"
if [[ "${validation_tier}" == full-replay ]]; then
  build_repo="${tmp}/build-repo"
  git_clean clone --quiet --no-local --no-hardlinks --no-checkout --no-tags "${repo_root}" "${build_repo}" || fail "cannot create build repository"
  [[ ! -e "${build_repo}/.git/objects/info/alternates" ]] || fail "build repository uses alternates"
  git_clean -C "${build_repo}" checkout --quiet --detach "${head_oid}" || fail "cannot checkout build HEAD"
  /usr/bin/mkdir -m 0700 "${tmp}/cargo-home" "${tmp}/cargo-target"
  [[ -d /home/pallasting/.cargo/registry && ! -L /home/pallasting/.cargo/registry ]] || fail "trusted offline Cargo registry missing"
  /usr/bin/cp -a --no-preserve=ownership /home/pallasting/.cargo/registry "${tmp}/cargo-home/registry" || fail "cannot snapshot Cargo registry"
  [[ -z "$(/usr/bin/find "${tmp}/cargo-home/registry" -type l -print -quit)" ]] || fail "Cargo snapshot contains symlink"
  rust_env=(/usr/bin/env -i PATH=/usr/bin:/bin:/home/pallasting/.cargo/bin HOME="${tmp}/home" TMPDIR="${tmp}/cargo-tmp" LANG=C.UTF-8 LC_ALL=C.UTF-8 TZ=UTC RUSTUP_HOME=/home/pallasting/.rustup CARGO_HOME="${tmp}/cargo-home" CARGO_TARGET_DIR="${tmp}/cargo-target" CARGO_BUILD_JOBS=1 CARGO_INCREMENTAL=0 CARGO_NET_OFFLINE=true CARGO_TERM_COLOR=never RUSTC=/home/pallasting/.cargo/bin/rustc RUSTFLAGS=-C\ debuginfo=0 GIT_CONFIG_NOSYSTEM=1 GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_SYSTEM=/dev/null)
  (
    cd "${build_repo}"
    "${rust_env[@]}" /home/pallasting/.cargo/bin/rustfmt --edition 2021 --check "${parent_module_path}" "${rust_source_path}"
    "${rust_env[@]}" /home/pallasting/.cargo/bin/cargo test --locked --offline -p ab-store --no-default-features --features "${feature}" -j1 s18_ -- --test-threads=1
  ) >"${tmp}/rust.log" 2>&1 || { /usr/bin/tail -n 120 "${tmp}/rust.log" >&2 || true; fail "Rust S18 verifier replay failed"; }
  rust_test_count="$(/usr/bin/awk -F '\t' '$1=="rust_s18_test_count" {print $2}' "${tmp}/checker-1.tsv")"
  /usr/bin/grep -F "test result: ok. ${rust_test_count} passed; 0 failed" "${tmp}/rust.log" >/dev/null || fail "Rust test count receipt mismatch"
  rust_verifier_replay="PASS"

  s17_repo="${tmp}/history/s17-repo"
  git_clean clone --quiet --no-local --no-hardlinks --no-checkout --no-tags "${repo_root}" "${s17_repo}" || fail "cannot create S17 replay repository"
  [[ ! -e "${s17_repo}/.git/objects/info/alternates" ]] || fail "S17 replay uses alternates"
  git_clean -C "${s17_repo}" checkout --quiet --detach "${baseline_commit}" || fail "cannot checkout frozen S17 integration"
  (
    cd "${s17_repo}"
    /usr/bin/env -i PATH=/usr/bin:/bin:/home/pallasting/.cargo/bin LC_ALL=C TZ=UTC \
      HOME=/home/pallasting PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1 \
      PYTHONSAFEPATH=1 RUSTUP_HOME=/home/pallasting/.rustup \
      /usr/bin/bash "${s17_gate}" full-replay
  ) >"${tmp}/s17.log" 2>&1 || { /usr/bin/tail -n 120 "${tmp}/s17.log" >&2 || true; fail "frozen S17 full replay failed"; }
  /usr/bin/grep -Fx $'gate\tPASS' "${tmp}/s17.log" >/dev/null || fail "S17 replay did not PASS"
  /usr/bin/grep -Fx $'mode\tintegrated' "${tmp}/s17.log" >/dev/null || fail "S17 replay mode drift"
  /usr/bin/grep -Fx $'head\t'"${baseline_commit}" "${tmp}/s17.log" >/dev/null || fail "S17 replay HEAD drift"
  frozen_s17_replay="PASS"
fi

[[ "$(git_clean rev-parse HEAD)" == "${head_oid}" ]] || fail "HEAD changed during verification"
[[ -z "$(git_clean status --porcelain=v1 --untracked-files=all)" ]] || fail "verification dirtied worktree"

/usr/bin/cat "${tmp}/checker-1.tsv"
if [[ "${mode}" == source ]]; then
  printf 'source_gate\tVALID_SOURCE_BIOCORTEX_AB_TRACK_B_OWNED_LAB_AUTHORIZATION_ENVELOPE_VERIFIER_S18\n'
else
  printf 'integration_gate\tVALID_INTEGRATED_BIOCORTEX_AB_TRACK_B_OWNED_LAB_AUTHORIZATION_ENVELOPE_VERIFIER_S18\n'
fi
printf 'rust_active_ed25519_verifier_replay\t%s\n' "${rust_verifier_replay}"
printf 'frozen_s17_full_replay\t%s\n' "${frozen_s17_replay}"
if [[ "${validation_tier}" == fast ]]; then
  printf 'validation_tier\tFAST_CONTENT_IDENTITY_ONLY_NO_RUST_OR_PREDECESSOR_REPLAY\n'
  printf 'periodic_full_replay_required\ttrue\n'
  printf 'release_status\tNON_RELEASE\n'
  printf 'gate\tFAST_PASS_NON_RELEASE_CONTENT_IDENTITY_ONLY\n'
else
  printf 'validation_tier\tFULL_RUST_ACTIVE_SIGNATURE_AND_S17_CHAIN_REPLAY\n'
  printf 'periodic_full_replay_required\tfalse\n'
  printf 'release_status\tRELEASE_VALIDATION_PASS\n'
  printf 'gate\tPASS\n'
fi
printf 'mode\t%s\n' "${mode}"
printf 'baseline\t%s\n' "${baseline_commit}"
printf 'source_commit\t%s\n' "${source_commit}"
if [[ "${mode}" == integrated ]]; then printf 'integration_commit\t%s\n' "${head_oid}"; fi
printf 'head\t%s\n' "${head_oid}"
printf 'gate_sha256\t%s\n' "$(/usr/bin/sha256sum "${gate_path}" | /usr/bin/awk '{print $1}')"
