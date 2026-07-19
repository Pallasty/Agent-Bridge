#!/usr/bin/env -S -i /usr/bin/bash
# Release gate for the non-live S21B-A1 owned-lab role-build closure.
set -euo pipefail
umask 077

while IFS= read -r imported_function; do
  builtin unset -f "$imported_function"
done < <(builtin compgen -A function)

PATH="/usr/bin:/bin:/home/pallasting/.cargo/bin"
export PATH LC_ALL=C TZ=UTC
export PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1 PYTHONSAFEPATH=1
export GIT_ATTR_NOSYSTEM=1 GIT_OPTIONAL_LOCKS=0
export GIT_NO_LAZY_FETCH=1 GIT_TERMINAL_PROMPT=0 GCM_INTERACTIVE=Never
export GIT_ASKPASS=/bin/false
unset BASH_ENV ENV CDPATH LD_AUDIT LD_LIBRARY_PATH LD_PRELOAD
unset PYTHONPATH PYTHONHOME PYTHONINSPECT PYTHONSTARTUP PYTHONWARNINGS
unset PYTHONBREAKPOINT PYTHONUSERBASE
unset CARGO_ENCODED_RUSTFLAGS CARGO_HOME CARGO_TARGET_DIR RUSTFLAGS
unset RUSTUP_HOME RUSTC RUSTDOC RUSTC_WRAPPER RUSTC_WORKSPACE_WRAPPER
unset GIT_DIR GIT_WORK_TREE GIT_COMMON_DIR GIT_INDEX_FILE
unset GIT_OBJECT_DIRECTORY GIT_ALTERNATE_OBJECT_DIRECTORIES
unset GIT_REPLACE_REF_BASE GIT_CONFIG GIT_CONFIG_COUNT GIT_CONFIG_PARAMETERS
unset GIT_NAMESPACE GIT_SHALLOW_FILE GIT_CEILING_DIRECTORIES
unset GIT_DISCOVERY_ACROSS_FILESYSTEM
export GIT_CONFIG_NOSYSTEM=1 GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_SYSTEM=/dev/null

fail() {
  printf 'S21B-A1 role-build closure gate failed: %s\n' "$*" >&2
  exit 1
}

validation_tier="${1:-full-replay}"
external_receipt="${2:-}"
[[ "$#" -le 2 ]] || fail "expected a validation tier and optional external receipt path"
[[ "$#" -lt 2 || -n "$external_receipt" ]] \
  || fail "an explicitly supplied external receipt path may not be empty"
case "$validation_tier" in
  fast|full-replay) ;;
  *) fail "unknown validation tier: $validation_tier" ;;
esac
if [[ "$validation_tier" == fast && -n "$external_receipt" ]]; then
  fail "fast validation cannot persist a build receipt"
fi

required_tools=(
  /usr/bin/awk /usr/bin/basename /usr/bin/bash /usr/bin/cmp /usr/bin/dirname
  /usr/bin/env /usr/bin/find /usr/bin/git /usr/bin/grep /usr/bin/mkdir
  /usr/bin/mktemp /usr/bin/python3 /usr/bin/realpath /usr/bin/rm /usr/bin/ln
  /usr/bin/chmod
  /usr/bin/sha256sum /usr/bin/stat /usr/bin/tail /usr/bin/wc /usr/bin/bwrap
)
for tool in "${required_tools[@]}"; do
  [[ -x "$tool" ]] || fail "missing required tool: $tool"
done

cd "$(/usr/bin/dirname "${BASH_SOURCE[0]}")/.."
repo_root="$(builtin pwd -P)"
[[ "$repo_root" == /* && -d "$repo_root" && ! -L "$repo_root" ]] \
  || fail "repository root is not one canonical directory"

# Immutable construction base: the exact, already integrated S21B-A0 closure.
packet_base_commit="d677e923442661a1d896185923b244d22b726319"
packet_base_tree="4534149eb9c8057d4980f008897c9587bd253c7f"
packet_base_first_parent="908412b8209056a90b3be5c2f93896c763d31311"
packet_base_second_parent="4f627b0f1be2c858615906e5170055d92b5632b3"
packet_base_archive_sha256="6d2163035d98bb64a76fcbcb1c725d315cada415814f7a0cf82c7afc89c1cac8"
packet_base_archive_byte_count="48793600"
packet_base_cargo_lock_sha256="a0ba6e432b188cbd0e3157693cb586bb950584860f036f83ee535fe67284b709"
source_base_commit="a5c70f235cf4e1bffa26253e2618e0a0903c9a16"
source_base_tree="35987f0ca61b200a34aa82b099482b791ed06bca"
source_base_first_parent="66f4754fd871169f50f345e5c023c94466f8ffd4"
source_base_second_parent="dc71c6f27aa1b9f310e5fff9e4e855011104dc96"
source_base_cargo_lock_sha256="452da4a2c2e4712251ad7a4076a3966222507eaf1695ff3d4ecab13084d732d2"
release_source_tag="v0.14.0"
release_source_tag_oid="3ebcd0755df49fee3608b033c480d4272733bb34"
release_source_tag_commit="c74bf3360502ffbc1a7c9a471d939617cc028422"
release_truth_helper_blob_oid="7db3f57086652e1cf46b72e0ad50ccba5dd6d938"
release_truth_helper_sha256="6e4047c08d878d757bbd346abb5837dc02d1e54f20f0cfbfd6c8098a2f74b8fd"

cargo_lock_path="Cargo.lock"
workspace_manifest_path="Cargo.toml"
rust_toolchain_path="rust-toolchain.toml"
release_truth_gate_path="scripts/verify-agent-bridge-release-truth-gate.sh"
release_truth_helper_path="scripts/agent-bridge-release-truth-gate.py"
role_manifest_path="crates/owned-lab-role-artifacts/Cargo.toml"
role_lib_path="crates/owned-lab-role-artifacts/src/lib.rs"
controller_path="crates/owned-lab-role-artifacts/src/bin/controller.rs"
observer_path="crates/owned-lab-role-artifacts/src/bin/observer.rs"
runner_path="crates/owned-lab-role-artifacts/src/bin/runner.rs"
validator_path="crates/owned-lab-role-artifacts/src/bin/validator.rs"
design_path="docs/design/MEMORY_TEMPORAL_OWNED_LAB_ROLE_BUILD_CLOSURE_S21B_A1_2026_07_18.md"
fixture_prefix="docs/design/fixtures/biocortex-ab-track-b-owned-lab-role-build"
contract_path="${fixture_prefix}-contract-s21b-a1-v0.json"
feature_path="${fixture_prefix}-feature-set-s21b-a1-v0.json"
receipt_schema_path="${fixture_prefix}-receipt-schema-s21b-a1-v0.json"
synthetic_receipt_path="${fixture_prefix}-receipt-synthetic-s21b-a1-v0.json"
recipes_path="${fixture_prefix}-recipes-s21b-a1-v0.json"
schema_set_path="${fixture_prefix}-schema-set-s21b-a1-v0.json"
status_path="${fixture_prefix}-status-s21b-a1-v0.json"
successor_path="${fixture_prefix}-successor-gate-s21b-a1-v0.json"
toolchain_manifest_path="${fixture_prefix}-toolchain-manifest-s21b-a1-v0.json"
report_path="docs/reports/goal-c-u/2026-07-18-biocortex-ab-track-b-owned-lab-role-build-closure-s21b-a1-prereg.md"
builder_path="scripts/eval/build_memory_temporal_owned_lab_role_artifacts_s21b_a1.py"
checker_path="scripts/eval/check_memory_temporal_owned_lab_role_build_s21b_a1.py"
expected_path="scripts/eval/fixtures/memory_temporal_owned_lab_role_build_s21b_a1.expected.v0.tsv"
gate_path="scripts/check-memory-temporal-owned-lab-role-build-s21b-a1.sh"
a0_gate_path="scripts/check-memory-temporal-owned-lab-presign-closure-s21b-a0.sh"
flatten_argv_receipt_ere=$'^argv_sha256\t[0-9a-f]{64}$'

packet_paths=(
  "$cargo_lock_path" "$workspace_manifest_path" "$rust_toolchain_path"
  "$release_truth_gate_path" "$role_manifest_path" "$role_lib_path"
  "$controller_path" "$observer_path" "$runner_path" "$validator_path"
  "$design_path" "$contract_path" "$feature_path" "$receipt_schema_path"
  "$synthetic_receipt_path" "$recipes_path" "$schema_set_path" "$status_path"
  "$successor_path" "$toolchain_manifest_path" "$report_path" "$builder_path"
  "$checker_path" "$expected_path" "$gate_path"
)
packet_modes=(
  100644 100644 100644 100755 100644 100644 100644 100644 100644 100644
  100644 100644 100644 100644 100644 100644 100644 100644 100644 100644
  100644 100755 100755 100644 100755
)
report_binding_paths=(
  "$cargo_lock_path" "$workspace_manifest_path" "$rust_toolchain_path"
  "$release_truth_gate_path" "$role_manifest_path" "$role_lib_path"
  "$controller_path" "$observer_path" "$runner_path" "$validator_path"
  "$design_path" "$contract_path" "$feature_path" "$receipt_schema_path"
  "$synthetic_receipt_path" "$recipes_path" "$schema_set_path" "$status_path"
  "$successor_path" "$toolchain_manifest_path" "$builder_path" "$checker_path"
  "$expected_path" "$gate_path"
)

git_clean() {
  /usr/bin/git --no-pager --no-replace-objects -c core.fsmonitor=false \
    -c core.attributesFile=/dev/null -c core.commitGraph=false \
    -c core.hooksPath=/dev/null -c safe.directory="$repo_root" "$@"
}

git_private() {
  local private_repo="$1"
  shift
  /usr/bin/git --no-pager --no-replace-objects -C "$private_repo" \
    -c core.fsmonitor=false -c core.attributesFile=/dev/null \
    -c core.commitGraph=false -c core.hooksPath=/dev/null \
    -c safe.directory="$private_repo" "$@"
}

raw_blob_sha256() {
  local commit="$1" path="$2"
  git_clean cat-file blob "$commit:$path" | /usr/bin/sha256sum | /usr/bin/awk '{print $1}'
}

[[ "$(git_clean config --get-all safe.directory)" == "$repo_root" ]] \
  || fail "Git trust scope is not the exact repository root"
[[ "$(git_clean rev-parse --is-shallow-repository)" == false ]] || fail "shallow history"
common_dir="$(git_clean rev-parse --path-format=absolute --git-common-dir)"
[[ "$common_dir" == /* && -d "$common_dir" && ! -L "$common_dir" ]] \
  || fail "non-canonical Git common directory"
git_dir="$(git_clean rev-parse --path-format=absolute --absolute-git-dir)"
[[ "$git_dir" == /* && -d "$git_dir" && ! -L "$git_dir" ]] \
  || fail "non-canonical Git worktree directory"
trusted_tmp_parent="/Data/.ab-gate-tmp"
[[ -d "$trusted_tmp_parent" && ! -L "$trusted_tmp_parent" ]] \
  || fail "trusted gate scratch parent absent"
/usr/bin/python3 -I - "$repo_root" "$git_dir" "$common_dir" \
  "$trusted_tmp_parent" <<'PY' || fail "unsafe gate repository or scratch ancestry"
import os
import pathlib
import stat
import sys

euid = os.geteuid()

def validate(path_text: str, exact_mode: int | None = None) -> None:
    supplied = pathlib.Path(path_text)
    resolved = supplied.resolve(strict=True)
    assert supplied.absolute() == resolved and resolved.is_dir() and not resolved.is_symlink()
    current = pathlib.Path(resolved.anchor)
    members = [current]
    for part in resolved.parts[1:]:
        current /= part
        members.append(current)
    for member in members:
        observed = member.lstat()
        assert stat.S_ISDIR(observed.st_mode) and not member.is_symlink()
        assert observed.st_uid in (0, euid)
        writable = observed.st_mode & (stat.S_IWGRP | stat.S_IWOTH)
        sticky_root = observed.st_uid == 0 and bool(observed.st_mode & stat.S_ISVTX)
        assert not writable or sticky_root, member
    final = resolved.lstat()
    if exact_mode is not None:
        assert final.st_uid == euid and stat.S_IMODE(final.st_mode) == exact_mode

validate(sys.argv[1])
validate(sys.argv[2])
validate(sys.argv[3])
validate(sys.argv[4], 0o700)
PY
[[ ! -e "$common_dir/shallow" && ! -L "$common_dir/shallow" && \
    ! -e "$common_dir/info/grafts" && ! -L "$common_dir/info/grafts" ]] \
  || fail "shallow or graft state present"
[[ ! -e "$common_dir/objects/info/alternates" && \
    ! -L "$common_dir/objects/info/alternates" ]] || fail "Git alternates present"
[[ ! -e "$common_dir/info/attributes" && ! -L "$common_dir/info/attributes" ]] \
  || fail "repository-local Git attributes are forbidden"
[[ -z "$(git_clean for-each-ref --format='%(refname)' refs/replace)" ]] \
  || fail "Git replace refs"
[[ -z "$(git_clean config --local --get extensions.partialClone || true)" ]] \
  || fail "Git partial-clone extension present"
[[ -z "$(git_clean config --local --get-regexp '^remote\..*\.(promisor|partialclonefilter)$' || true)" ]] \
  || fail "Git promisor or partial-clone remote present"
[[ -z "$(git_clean status --porcelain=v1 --untracked-files=all)" ]] \
  || fail "worktree or index is not clean"

[[ "$(git_clean cat-file -t "$packet_base_commit")" == commit ]] \
  || fail "exact S21B-A0 base commit absent"
[[ "$(git_clean show -s --format='%T' "$packet_base_commit")" == "$packet_base_tree" ]] \
  || fail "S21B-A0 base tree drift"
[[ "$(git_clean show -s --format='%P' "$packet_base_commit")" == \
    "$packet_base_first_parent $packet_base_second_parent" ]] \
  || fail "S21B-A0 base parent topology drift"
[[ "$(raw_blob_sha256 "$packet_base_commit" "$cargo_lock_path")" == \
    "$packet_base_cargo_lock_sha256" ]] || fail "S21B-A0 base Cargo.lock drift"
[[ "$(git_clean cat-file -t "$source_base_commit")" == commit ]] \
  || fail "exact A1 source-base commit absent"
[[ "$(git_clean show -s --format='%T' "$source_base_commit")" == \
    "$source_base_tree" ]] || fail "A1 source-base tree drift"
[[ "$(git_clean show -s --format='%P' "$source_base_commit")" == \
    "$source_base_first_parent $source_base_second_parent" ]] \
  || fail "A1 source-base parent topology drift"
[[ "$(raw_blob_sha256 "$source_base_commit" "$cargo_lock_path")" == \
    "$source_base_cargo_lock_sha256" ]] || fail "A1 source-base Cargo.lock drift"
git_clean merge-base --is-ancestor "$packet_base_commit" "$source_base_commit" \
  || fail "A1 source base does not descend from the exact A0 predecessor"

# The late read-only release-truth replay requires the real annotated source
# marker. Validate its ref identity, object kind, peeled commit, and semantic
# ordering before any expensive predecessor replay or Rust build begins.
[[ "$(git_clean rev-parse --verify "refs/tags/$release_source_tag")" == \
    "$release_source_tag_oid" ]] || fail "release source tag ref absent or drifted"
[[ "$(git_clean cat-file -t "refs/tags/$release_source_tag")" == tag ]] \
  || fail "release source marker is not the pinned annotated tag"
[[ "$(git_clean rev-parse --verify "refs/tags/$release_source_tag^{}")" == \
    "$release_source_tag_commit" ]] || fail "release source tag peeled commit drift"

head_oid="$(git_clean rev-parse --verify HEAD)" || fail "cannot resolve HEAD"
head_lineage=()
IFS=' ' read -r -a head_lineage < <(git_clean rev-list --parents -n 1 "$head_oid") \
  || fail "cannot resolve HEAD topology"
head_parents=("${head_lineage[@]:1}")
source_commit=""
head_topology=""
if [[ "${#head_parents[@]}" == 1 && "${head_parents[0]}" == "$source_base_commit" ]]; then
  source_commit="$head_oid"
  head_topology="SOURCE"
elif [[ "${#head_parents[@]}" == 2 ]]; then
  first_parent="${head_parents[0]}"
  source_commit="${head_parents[1]}"
  source_lineage=()
  IFS=' ' read -r -a source_lineage < <(git_clean rev-list --parents -n 1 "$source_commit") \
    || fail "cannot resolve A1 packet source topology"
  source_parents=("${source_lineage[@]:1}")
  [[ "${#source_parents[@]}" == 1 && "${source_parents[0]}" == "$source_base_commit" ]] \
    || fail "integration second parent is not the exact refrozen A1 packet source"
  [[ "$first_parent" == "$source_base_commit" ]] \
    || fail "integration first parent is not the exact A1 source base"
  if git_clean merge-base --is-ancestor "$source_commit" "$first_parent"; then
    fail "integration first parent already contains the A1 packet source"
  fi
  head_topology="INTEGRATION"
else
  fail "HEAD must be the exact one-commit A1 source or an ordinary two-parent integration"
fi
[[ "$(git_clean rev-list --count "$source_base_commit..$source_commit")" == 1 ]] \
  || fail "A1 packet source is not one exact commit over the refrozen source base"

verify_exact_a1_delta() {
  local left="$1" right="$2" label="$3"
  local delta_status delta_path delta_extra actual_delta_count=0
  declare -A expected_delta=(
    ["$cargo_lock_path"]="M" ["$workspace_manifest_path"]="M"
    ["$rust_toolchain_path"]="M" ["$release_truth_gate_path"]="M"
    ["$role_manifest_path"]="A" ["$role_lib_path"]="A"
    ["$controller_path"]="A" ["$observer_path"]="A" ["$runner_path"]="A"
    ["$validator_path"]="A" ["$design_path"]="A" ["$contract_path"]="A"
    ["$feature_path"]="A" ["$receipt_schema_path"]="A"
    ["$synthetic_receipt_path"]="A" ["$recipes_path"]="A"
    ["$schema_set_path"]="A" ["$status_path"]="A" ["$successor_path"]="A"
    ["$toolchain_manifest_path"]="A" ["$report_path"]="A" ["$builder_path"]="A"
    ["$checker_path"]="A" ["$expected_path"]="A" ["$gate_path"]="A"
  )
  while IFS=$'\t' read -r delta_status delta_path delta_extra; do
    [[ -n "$delta_status" && -n "$delta_path" && -z "${delta_extra:-}" ]] \
      || fail "$label: malformed A1 packet delta row"
    [[ -v "expected_delta[$delta_path]" ]] \
      || fail "$label: unexpected A1 packet delta path: $delta_path"
    [[ "${expected_delta[$delta_path]}" == "$delta_status" ]] \
      || fail "$label: wrong A1 packet delta status: $delta_path"
    unset 'expected_delta[$delta_path]'
    actual_delta_count=$((actual_delta_count + 1))
  done < <(git_clean diff-tree --no-commit-id --name-status --no-renames -r \
    "$left" "$right")
  [[ "$actual_delta_count" == 25 && "${#expected_delta[@]}" == 0 ]] \
    || fail "$label: A1 packet delta is not exact 4M+21A"
}

verify_exact_a1_delta "$source_base_commit" "$source_commit" "source delta"
if [[ "$head_topology" == INTEGRATION ]]; then
  verify_exact_a1_delta "$first_parent" "$head_oid" "integration delta"
fi

for index in "${!packet_paths[@]}"; do
  path="${packet_paths[$index]}" expected_mode="${packet_modes[$index]}"
  source_entry="$(git_clean ls-tree "$source_commit" -- "$path")"
  [[ -n "$source_entry" && "${source_entry%% *}" == "$expected_mode" ]] \
    || fail "A1 packet path or mode drift: $path"
  [[ "$source_entry" == "$(git_clean ls-tree "$head_oid" -- "$path")" ]] \
    || fail "source/HEAD A1 packet blob or mode mismatch: $path"
done
[[ -z "$(git_clean ls-tree -r "$head_oid" -- .cargo)" ]] \
  || fail "target-local .cargo configuration is outside the frozen build recipe"

# Only execute the shared release-truth parser after topology and the exact A1
# delta are authenticated. Its non-packet blob is pinned to the audited A0
# helper and must remain byte-identical in both source and integration HEAD.
release_truth_helper="$repo_root/$release_truth_helper_path"
expected_release_truth_helper_entry="100755 blob $release_truth_helper_blob_oid"$'\t'"$release_truth_helper_path"
[[ "$(git_clean ls-tree "$source_commit" -- "$release_truth_helper_path")" == \
    "$expected_release_truth_helper_entry" ]] \
  || fail "source release-truth helper blob or mode drift"
[[ "$(git_clean ls-tree "$head_oid" -- "$release_truth_helper_path")" == \
    "$expected_release_truth_helper_entry" ]] \
  || fail "HEAD release-truth helper blob or mode drift"
[[ "$(raw_blob_sha256 "$source_commit" "$release_truth_helper_path")" == \
    "$release_truth_helper_sha256" ]] \
  || fail "source release-truth helper content drift"
[[ -f "$release_truth_helper" && ! -L "$release_truth_helper" && \
    "$(/usr/bin/stat -c '%a:%h' "$release_truth_helper")" == 755:1 && \
    "$(/usr/bin/sha256sum "$release_truth_helper" | /usr/bin/awk '{print $1}')" == \
      "$release_truth_helper_sha256" ]] \
  || fail "worktree release-truth helper identity drift"
latest_semantic_version_tag="$(
  /usr/bin/python3 -I - "$release_truth_helper" "$repo_root" <<'PY'
import pathlib
import runpy
import sys
import tomllib

namespace = runpy.run_path(sys.argv[1], run_name="a1_release_truth_tag_preflight")
print(namespace["latest_version_tag"](pathlib.Path(sys.argv[2])))
PY
)" || fail "cannot derive latest semantic release source tag"
[[ "$latest_semantic_version_tag" == "$release_source_tag" ]] \
  || fail "latest semantic release source tag drift"

if [[ -n "$external_receipt" ]]; then
  [[ "$head_topology" == INTEGRATION ]] \
    || fail "a source HEAD may not persist a provisional build receipt"
  [[ "$external_receipt" == /* && "$external_receipt" != *$'\n'* && \
      "$external_receipt" != */ ]] || fail "external receipt path is not an absolute file path"
  [[ ! -e "$external_receipt" && ! -L "$external_receipt" ]] \
    || fail "external receipt path already exists; overwrite is forbidden"
  external_parent="$(/usr/bin/dirname -- "$external_receipt")"
  external_name="$(/usr/bin/basename -- "$external_receipt")"
  [[ "$external_name" != . && "$external_name" != .. ]] \
    || fail "external receipt basename is invalid"
  canonical_parent="$(/usr/bin/realpath -e -- "$external_parent")" \
    || fail "external receipt parent does not exist"
  [[ -d "$canonical_parent" && ! -L "$canonical_parent" ]] \
    || fail "external receipt parent is not canonical"
  canonical_external_receipt="$canonical_parent/$external_name"
  [[ "$external_receipt" == "$canonical_external_receipt" ]] \
    || fail "external receipt path must already be canonical"
  case "$canonical_external_receipt" in
    "$repo_root"|"$repo_root"/*|"$common_dir"|"$common_dir"/*)
      fail "receipt output must be outside the repository and Git common directory" ;;
  esac
fi

tmp="$(/usr/bin/mktemp -d -p "$trusted_tmp_parent" .ab-s21b-a1-gate.XXXXXXXX)" \
  || fail "cannot allocate bounded scratch under /Data"
tmp_identity="$(/usr/bin/stat -c '%d:%i:%u:%a' "$tmp")"
expected_tmp_identity="$(/usr/bin/stat -c '%d:%i' "$tmp"):$(/usr/bin/python3 -I -c 'import os; print(os.geteuid())'):700"
[[ "$tmp_identity" == "$expected_tmp_identity" ]] || fail "private gate scratch identity invalid"
assert_tmp_identity() {
  [[ ! -L "$tmp" && -d "$tmp" && \
      "$(/usr/bin/stat -c '%d:%i:%u:%a' "$tmp")" == "$tmp_identity" ]] \
    || fail "private gate scratch identity changed"
}
cleanup() {
  local original_status="$?"
  trap - EXIT HUP INT TERM
  if [[ ! -L "$tmp" && -d "$tmp" && \
        "$(/usr/bin/stat -c '%d:%i:%u:%a' "$tmp")" == "$tmp_identity" ]]; then
    /usr/bin/find "$tmp" -xdev -type d -exec /usr/bin/chmod u+rwx -- {} + \
      || { printf 'S21B-A1 role-build closure gate failed: cannot prepare pinned scratch for cleanup\n' >&2; exit 1; }
    /usr/bin/rm -rf -- "$tmp" \
      || { printf 'S21B-A1 role-build closure gate failed: cannot remove pinned scratch\n' >&2; exit 1; }
    [[ ! -e "$tmp" && ! -L "$tmp" ]] \
      || { printf 'S21B-A1 role-build closure gate failed: pinned scratch remains after cleanup\n' >&2; exit 1; }
  else
    printf 'S21B-A1 role-build closure gate failed: pinned scratch identity changed before cleanup\n' >&2
    exit 1
  fi
  exit "$original_status"
}
trap cleanup EXIT
trap 'exit 129' HUP
trap 'exit 130' INT
trap 'exit 143' TERM
assert_tmp_identity

git_clean -c tar.umask=0022 archive --format=tar "$packet_base_commit" \
  >"$tmp/a0-base.tar" || fail "cannot reconstruct exact S21B-A0 base archive"
[[ "$(/usr/bin/sha256sum "$tmp/a0-base.tar" | /usr/bin/awk '{print $1}')" == \
    "$packet_base_archive_sha256" ]] || fail "S21B-A0 base archive digest drift"
[[ "$(/usr/bin/wc -c <"$tmp/a0-base.tar" | /usr/bin/awk '{print $1}')" == \
    "$packet_base_archive_byte_count" ]] || fail "S21B-A0 base archive byte count drift"
/usr/bin/rm -f -- "$tmp/a0-base.tar"

builder="$repo_root/$builder_path"
[[ -f "$builder" && ! -L "$builder" ]] || fail "A1 reproducible builder absent"
gate_toolchain="$tmp/secure-toolchain"
gate_cargo_home="$tmp/secure-cargo-home"
predecessor_cargo_home="$tmp/predecessor-cargo-home"
runtime_root_cargo_home="$tmp/runtime-root-cargo-home"
runtime_root_registry_shell="$tmp/runtime-root-registry-shell"
runtime_root_registry_src="$tmp/runtime-root-registry-src"
runtime_user_registry_src="$tmp/runtime-user-registry-src"
/usr/bin/python3 -I - "$builder" "$repo_root" "$gate_toolchain" \
  "$gate_cargo_home" <<'PY' || fail "cannot create verified private toolchain/Cargo snapshot"
import json
import pathlib
import runpy
import sys
import tomllib

builder_path = pathlib.Path(sys.argv[1])
repo = pathlib.Path(sys.argv[2])
toolchain_destination = pathlib.Path(sys.argv[3])
cargo_home = pathlib.Path(sys.argv[4])
namespace = runpy.run_path(str(builder_path), run_name="a1_gate_snapshot")
manifest_path = repo / namespace["TOOLCHAIN_MANIFEST_REL"]
manifest = json.loads(manifest_path.read_bytes())
namespace["copy_secure_toolchain"](
    namespace["TOOLCHAIN_HOST_ROOT"],
    toolchain_destination,
    manifest["toolchain_tree_catalog"],
)
lock = tomllib.loads((repo / "Cargo.lock").read_text(encoding="utf-8"))
names = sorted(
    {
        package["name"]
        for package in lock["package"]
        if package.get("source") == namespace["SPARSE_INDEX_SOURCE_ID"]
    },
    key=lambda value: value.encode("ascii"),
)
assert len(names) == 531
observed, selected = namespace["sparse_index_observation"](names)
assert observed == manifest["cargo_registry_sparse_index"]
cargo_home.mkdir(mode=0o700)
namespace["copy_sparse_index"](cargo_home, selected)
namespace["validate_sparse_index_copy"](cargo_home, observed, selected)
observed_after, _ = namespace["sparse_index_observation"](names)
assert observed_after == observed
PY
assert_tmp_identity
gate_sparse_index="$gate_cargo_home/registry/index/index.crates.io-1949cf8c6b5b557f"
[[ -d "$gate_toolchain" && ! -L "$gate_toolchain" && \
    -d "$gate_sparse_index" && ! -L "$gate_sparse_index" ]] \
  || fail "verified private toolchain/Cargo snapshot absent"

checker="$repo_root/$checker_path"
expected="$repo_root/$expected_path"
[[ -f "$checker" && ! -L "$checker" && -f "$expected" && ! -L "$expected" ]] \
  || fail "A1 checker or expected receipt absent"
for seed in 22121 22199 22217; do
  /usr/bin/env -i PATH=/usr/bin:/bin LC_ALL=C TZ=UTC PYTHONDONTWRITEBYTECODE=1 \
    PYTHONNOUSERSITE=1 PYTHONSAFEPATH=1 \
    /usr/bin/python3 -I "$checker" --repo "$repo_root" --seed "$seed" \
    --toolchain-root "$gate_toolchain" --sparse-index-root "$gate_sparse_index" \
    >"$tmp/checker-$seed.tsv" || fail "A1 checker seed $seed failed"
done
/usr/bin/env -i PATH=/usr/bin:/bin LC_ALL=C TZ=UTC PYTHONDONTWRITEBYTECODE=1 \
  PYTHONNOUSERSITE=1 PYTHONSAFEPATH=1 \
  /usr/bin/python3 -I "$checker" --repo "$repo_root" --seed 22177 --self-test \
  --toolchain-root "$gate_toolchain" --sparse-index-root "$gate_sparse_index" \
  >"$tmp/checker-self.tsv" || fail "A1 checker mutation self-test failed"
for receipt in "$tmp/checker-22199.tsv" "$tmp/checker-22217.tsv" "$tmp/checker-self.tsv"; do
  /usr/bin/cmp -s "$tmp/checker-22121.tsv" "$receipt" \
    || fail "A1 checker output is seed-dependent or mutation self-test drifted"
done
/usr/bin/cmp -s "$tmp/checker-22121.tsv" "$expected" || fail "A1 expected checker receipt mismatch"

required_checker_rows=(
  $'stage\tS21B_A1_DEFINE_AND_BUILD_FOUR_NAMED_NON_LIVE_ROLE_ARTIFACTS_AND_REPRODUCIBLE_CLOSURES'
  $'status\tS21B_A1_TOOLING_COMPLETE_PENDING_POST_INTEGRATION_DOUBLE_REBUILD'
  $'decision\tS21B_A1_ADVANCE_ONLY_TO_SEPARATE_UNSIGNED_SUBJECT_CONTRACT_REBINDING_AND_GENERATION_REVIEW_NO_OWNER_SIGNING_REQUEST'
  $'cargo_binary_target_count\t4'
  $'cargo_library_target_count\t1'
  $'cargo_direct_dependency_count\t0'
  $'rust_build_or_test_run\tfalse'
  $'network_access_authorized\tfalse'
  $'candidate_supplied_digest_authoritative\tfalse'
  $'owner_private_key_read\tfalse'
  $'owner_signature_generated\tfalse'
  $'live_action_count\t0'
  $'side_effects_unlocked\tNONE'
  $'gate\tPASS_S21B_A1_STATIC_ROLE_BUILD_CLOSURE_NON_LIVE_ONLY'
)
for row in "${required_checker_rows[@]}"; do
  /usr/bin/grep -Fx "$row" "$expected" >/dev/null \
    || fail "A1 checker receipt boundary missing: $row"
done

flatten_receipt_regex_kat="$tmp/flatten-receipt-regex.kat"
builtin printf -v valid_flatten_argv_digest '%064d' 0
builtin printf 'argv_sha256\t%s\n' "$valid_flatten_argv_digest" \
  >"$flatten_receipt_regex_kat"
/usr/bin/grep -Eq "$flatten_argv_receipt_ere" "$flatten_receipt_regex_kat" \
  || fail "predecessor bwrap flatten argv receipt positive KAT failed"
invalid_flatten_argv_rows=(
  "argv_sha256\\t$valid_flatten_argv_digest"
  $'argv_sha256\t'"${valid_flatten_argv_digest:1}"
  $'argv_sha256\t'"${valid_flatten_argv_digest}0"
  $'argv_sha256\t'"A${valid_flatten_argv_digest:1}"
  $'argv_sha256\t'"g${valid_flatten_argv_digest:1}"
  $'xargv_sha256\t'"$valid_flatten_argv_digest"
  $'argv_sha256\t'"${valid_flatten_argv_digest}x"
)
for invalid_flatten_argv_row in "${invalid_flatten_argv_rows[@]}"; do
  builtin printf '%s\n' "$invalid_flatten_argv_row" \
    >"$flatten_receipt_regex_kat"
  if /usr/bin/grep -Eq "$flatten_argv_receipt_ere" \
      "$flatten_receipt_regex_kat"; then
    fail "predecessor bwrap flatten argv receipt negative KAT failed"
  fi
done
/usr/bin/rm -f -- "$flatten_receipt_regex_kat"

report="$repo_root/$report_path"
[[ -f "$report" && ! -L "$report" ]] || fail "A1 report absent"
/usr/bin/grep -Fx 'Hash table state: **FINAL_CLOSED_WORLD_BOUND**' "$report" >/dev/null \
  || fail "A1 report final-state token absent"
/usr/bin/grep -Fx '## Final artifact digest table' "$report" >/dev/null \
  || fail "A1 report digest-table heading absent"
! /usr/bin/grep -E 'TODO_FINAL_SHA256|IMPLEMENTATION_PENDING|TODO markers|\| PENDING \|' "$report" >/dev/null \
  || fail "A1 report contains non-final markers"
report_binding_count="$(/usr/bin/grep -Ec '^\| [^|]+ \| [0-9a-f]{64} \|$' "$report")"
[[ "$report_binding_count" == "${#report_binding_paths[@]}" ]] \
  || fail "A1 report digest table is not exact ${#report_binding_paths[@]} rows"
for path in "${report_binding_paths[@]}"; do
  digest="$(raw_blob_sha256 "$source_commit" "$path")"
  [[ "$(/usr/bin/grep -Fxc -- "| $path | $digest |" "$report")" == 1 ]] \
    || fail "A1 report lacks exact path/hash binding: $path"
done

# Fast and full tiers both exercise the exact baseline workspace-member
# insertion and the trusted post-payload sparse-index and copied-registry
# cleanup primitives. The real replay applies the former cleanup only after the
# Landlock payload, forbidden-metadata comparison, and residual-process check;
# the latter stacks its own exact-parent Landlock domain before changing any
# copied directory mode.
/usr/bin/python3 -I - "$builder" "$tmp/retired-index-cleanup-kat" \
  "$contract_path" "$repo_root" "$source_commit" <<'PY' \
  || fail "builder source-graph and cleanup compatibility KAT failed"
import ast
import contextlib
import hashlib
import inspect
import io
import json
import os
import pathlib
import runpy
import stat
import sys

namespace = runpy.run_path(sys.argv[1], run_name="a1_retired_index_cleanup_kat")
# Bind every statically direct call to a top-level builder function against
# that function's real Python signature. This makes argument-count and
# keyword-only API drift a fast-tier failure instead of a late rebuild error.
builder_path = pathlib.Path(sys.argv[1])
builder_tree = ast.parse(
    builder_path.read_text(encoding="utf-8"),
    filename=str(builder_path),
)
builder_functions = {
    node.name
    for node in builder_tree.body
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
}
direct_call_binding_errors = []
skipped_direct_calls = []
audited_direct_call_count = 0
for node in ast.walk(builder_tree):
    if not (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id in builder_functions
    ):
        continue
    if (
        any(isinstance(argument, ast.Starred) for argument in node.args)
        or any(keyword.arg is None for keyword in node.keywords)
    ):
        skipped_direct_calls.append((node.lineno, node.func.id))
        continue
    audited_direct_call_count += 1
    try:
        inspect.signature(namespace[node.func.id]).bind(
            *([None] * len(node.args)),
            **{keyword.arg: None for keyword in node.keywords},
        )
    except TypeError as exc:
        direct_call_binding_errors.append((node.lineno, node.func.id, str(exc)))
assert audited_direct_call_count >= 600
assert not skipped_direct_calls, skipped_direct_calls
assert not direct_call_binding_errors, direct_call_binding_errors
repo = pathlib.Path(sys.argv[4])
namespace["validate_source_graph"](repo, repo, sys.argv[5])
flatten_launcher_payload = namespace["PREDECESSOR_BWRAP_FLATTEN_LAUNCHER"]
assert hashlib.sha256(flatten_launcher_payload).hexdigest() == namespace[
    "PREDECESSOR_BWRAP_FLATTEN_LAUNCHER_SHA256"
]
host_rm_alias = pathlib.Path("/usr/bin/rm")
host_rm_observed = host_rm_alias.lstat()
assert (
    stat.S_ISLNK(host_rm_observed.st_mode)
    and host_rm_observed.st_uid == 0
    and host_rm_observed.st_gid == 0
    and host_rm_observed.st_nlink == 1
    and stat.S_IMODE(host_rm_observed.st_mode) == 0o777
    and os.readlink(host_rm_alias) == "gnurm"
    and host_rm_alias.samefile("/usr/bin/gnurm")
)
kat_root = pathlib.Path(sys.argv[2])
contract = json.loads(pathlib.Path(sys.argv[3]).read_bytes())
rebuild_contract = contract["double_rebuild_contract"]
assert rebuild_contract["predecessor_frozen_s15_s16_cleanup_dispatcher_profile"] == namespace[
    "PREDECESSOR_FROZEN_GATE_SCRATCH_CLEANUP_PROFILE"
]
assert rebuild_contract["predecessor_private_real_gnurm_sha256"] == namespace[
    "PREDECESSOR_REAL_GNURM_SHA256"
]
kat_root.mkdir(mode=0o700)
sentinel = kat_root / "outside-sentinel"
sentinel.write_bytes(b"outside\n")
os.chmod(sentinel, 0o400)

members = {
    "config.json": b'{"dl":"https://example.invalid"}\n',
    ".cache/ka/t-/kat-member": b"opaque sparse cache bytes\x00\x01",
}

def create_tree(
    container: pathlib.Path,
    *,
    add_symlink: bool = False,
    add_empty_directory: bool = False,
) -> dict[str, object]:
    container.mkdir(mode=0o700, parents=True)
    index_root = container / "index.crates.io-1949cf8c6b5b557f"
    index_root.mkdir(mode=0o700)
    rows = []
    total = 0
    for relative, payload in members.items():
        path = index_root.joinpath(*pathlib.PurePosixPath(relative).parts)
        path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        path.write_bytes(payload)
        os.chmod(path, 0o444)
        rows.append(
            f"{relative}\t{len(payload)}\t{hashlib.sha256(payload).hexdigest()}\n".encode("ascii")
        )
        total += len(payload)
    if add_symlink:
        os.symlink(sentinel, index_root / "forbidden-link")
    if add_empty_directory:
        (index_root / "forbidden-empty").mkdir(mode=0o700)
    directories = [index_root] + [path for path in index_root.rglob("*") if path.is_dir()]
    for directory in sorted(directories, key=lambda item: len(item.parts), reverse=True):
        os.chmod(directory, 0o555)
    rows.sort(key=lambda row: row.split(b"\t", 1)[0])
    return {
        "catalog_sha256": hashlib.sha256(b"".join(rows)).hexdigest(),
        "file_count": len(rows),
        "total_byte_count": total,
    }

good = kat_root / "good-index"
expected = create_tree(good)
namespace["_adapter_prepare_retired_sparse_index_tree_for_cleanup"](
    good,
    good.lstat().st_dev,
    expected,
)
good_root = good / "index.crates.io-1949cf8c6b5b557f"
assert all(
    stat.S_IMODE(path.lstat().st_mode) == 0o700
    for path in [good_root] + [member for member in good_root.rglob("*") if member.is_dir()]
)
assert all(
    stat.S_IMODE(path.lstat().st_mode) == 0o444
    for path in good_root.rglob("*") if path.is_file()
)
assert stat.S_IMODE(sentinel.lstat().st_mode) == 0o400

bad = kat_root / "bad-index"
bad_expected = create_tree(bad, add_symlink=True)
denial = io.StringIO()
with contextlib.redirect_stderr(denial):
    try:
        namespace["_adapter_prepare_retired_sparse_index_tree_for_cleanup"](
            bad,
            bad.lstat().st_dev,
            bad_expected,
        )
    except SystemExit as exc:
        assert exc.code == 125
    else:
        raise AssertionError("retired sparse-index cleanup helper accepted a symlink")
assert "special or mutable file" in denial.getvalue()
assert stat.S_IMODE(sentinel.lstat().st_mode) == 0o400

empty = kat_root / "empty-index"
empty_expected = create_tree(empty, add_empty_directory=True)
empty_denial = io.StringIO()
with contextlib.redirect_stderr(empty_denial):
    try:
        namespace["_adapter_prepare_retired_sparse_index_tree_for_cleanup"](
            empty,
            empty.lstat().st_dev,
            empty_expected,
        )
    except SystemExit as exc:
        assert exc.code == 125
    else:
        raise AssertionError("retired sparse-index cleanup helper accepted an empty directory")
assert "contains an empty directory" in empty_denial.getvalue()
assert stat.S_IMODE(sentinel.lstat().st_mode) == 0o400

cleanup_good = kat_root / "frozen-cleanup-good"
cleanup_good.mkdir(mode=0o700)
cleanup_nested = cleanup_good / "readonly" / "nested"
cleanup_nested.mkdir(mode=0o700, parents=True)
cleanup_file = cleanup_nested / "member"
cleanup_file.write_bytes(b"cleanup member\n")
os.chmod(cleanup_file, 0o444)
cleanup_link = cleanup_good / "outside-link"
os.symlink(sentinel, cleanup_link)
os.chmod(cleanup_nested, 0o555)
os.chmod(cleanup_nested.parent, 0o555)
os.chmod(cleanup_good, 0o555)
directory_count = namespace["_adapter_prepare_owned_registry_tree_for_removal"](
    cleanup_good
)
assert directory_count == 3
assert all(
    stat.S_IMODE(path.lstat().st_mode) == 0o755
    for path in (cleanup_good, cleanup_nested.parent, cleanup_nested)
)
assert stat.S_IMODE(cleanup_file.lstat().st_mode) == 0o444
assert cleanup_link.is_symlink() and os.readlink(cleanup_link) == os.fspath(sentinel)
assert stat.S_IMODE(sentinel.lstat().st_mode) == 0o400

cleanup_alias = kat_root / "frozen-cleanup-root-alias"
os.symlink(cleanup_good, cleanup_alias)
cleanup_alias_denial = io.StringIO()
with contextlib.redirect_stderr(cleanup_alias_denial):
    try:
        namespace["_adapter_prepare_owned_registry_tree_for_removal"](
            cleanup_alias
        )
    except SystemExit as exc:
        assert exc.code == 125
    else:
        raise AssertionError("frozen cleanup helper accepted an aliased registry root")
assert "copied registry identity drift" in cleanup_alias_denial.getvalue()
assert stat.S_IMODE(sentinel.lstat().st_mode) == 0o400

cleanup_bad = kat_root / "frozen-cleanup-special-mode"
cleanup_bad.mkdir(mode=0o700)
cleanup_bad_child = cleanup_bad / "setgid-directory"
cleanup_bad_child.mkdir(mode=0o700)
os.chmod(cleanup_bad_child, 0o2700)
cleanup_bad_denial = io.StringIO()
with contextlib.redirect_stderr(cleanup_bad_denial):
    try:
        namespace["_adapter_prepare_owned_registry_tree_for_removal"](cleanup_bad)
    except SystemExit as exc:
        assert exc.code == 125
    else:
        raise AssertionError("frozen cleanup helper accepted a special-mode directory")
assert "directory identity drift" in cleanup_bad_denial.getvalue()
assert stat.S_IMODE(sentinel.lstat().st_mode) == 0o400

cleanup_writable = kat_root / "frozen-cleanup-group-writable"
cleanup_writable.mkdir(mode=0o700)
cleanup_writable_child = cleanup_writable / "group-writable-directory"
cleanup_writable_child.mkdir(mode=0o700)
os.chmod(cleanup_writable_child, 0o770)
cleanup_writable_denial = io.StringIO()
with contextlib.redirect_stderr(cleanup_writable_denial):
    try:
        namespace["_adapter_prepare_owned_registry_tree_for_removal"](
            cleanup_writable
        )
    except SystemExit as exc:
        assert exc.code == 125
    else:
        raise AssertionError("frozen cleanup helper accepted a group-writable directory")
assert "directory identity drift" in cleanup_writable_denial.getvalue()
assert stat.S_IMODE(sentinel.lstat().st_mode) == 0o400
PY

if [[ "$validation_tier" == fast ]]; then
  printf '%s\n' \
    $'validation_tier\tFAST_IDENTITY_SCHEMA_SEMANTIC_PREREG_CARGO_METADATA_ONLY_NO_BUILD_OR_TEST' \
    $'release_qualification\tNON_RELEASE' \
    $'head_topology\t'"$head_topology" \
    $'a0_predecessor_replay\tNOT_RUN' \
    $'a1_target_sparse_index\tPRIVATE_532_FILE_CATALOG_VERIFIED_SEPARATE_FROM_PREDECESSOR' \
    $'role_rust_checks\tNOT_RUN' \
    $'release_truth_gate\tNOT_RUN' \
    $'double_rebuild\tNOT_RUN' \
    $'receipt_target\tNOT_RUN' \
    $'receipt_persistence\tNOT_RUN' \
    $'owner_signature\tNOT_REQUESTED' \
    $'live_canary\tNOT_RUN' \
    $'side_effects_unlocked\tNONE' \
    $'gate\tFAST_PASS_NON_LIVE_ROLE_BUILD_PREREG_ONLY'
  exit 0
fi

# Full replay first creates a physically separate 523-file sparse-index and
# exact 555-archive Cargo snapshot from the immutable A0 lock.  The 532-file
# A1 target index above must never be mounted into the predecessor namespace.
# The replay also creates an independent runtime
# root Cargo home because frozen env-i gates running as namespace UID 0 derive
# /root/.cargo, plus an independent user Cargo home for S14--S16's explicit
# CARGO_HOME.  Both receive the predecessor index/archive snapshot through
# nested read-only mounts and keep disposable generated state separate.
assert_tmp_identity
/usr/bin/git --no-pager --no-replace-objects -c safe.directory="$repo_root" \
  cat-file blob "$packet_base_commit:$cargo_lock_path" >"$tmp/a0-Cargo.lock" \
  || fail "cannot materialize exact A0 Cargo.lock"
/usr/bin/chmod 0600 "$tmp/a0-Cargo.lock"
[[ "$(/usr/bin/sha256sum "$tmp/a0-Cargo.lock" | /usr/bin/awk '{print $1}')" == \
    "$packet_base_cargo_lock_sha256" ]] || fail "materialized A0 Cargo.lock drift"
/usr/bin/python3 -I - "$builder" "$tmp/a0-Cargo.lock" "$predecessor_cargo_home" \
  "$runtime_root_cargo_home" "$runtime_root_registry_shell" \
  "$runtime_root_registry_src" "$runtime_user_registry_src" <<'PY' \
  || fail "cannot create verified private predecessor registry archive snapshot"
import pathlib
import runpy
import sys
import tomllib

builder_path = pathlib.Path(sys.argv[1])
a0_lock = pathlib.Path(sys.argv[2])
cargo_home = pathlib.Path(sys.argv[3])
runtime_cargo_home = pathlib.Path(sys.argv[4])
runtime_registry_shell = pathlib.Path(sys.argv[5])
runtime_registry_src = pathlib.Path(sys.argv[6])
runtime_user_registry_src = pathlib.Path(sys.argv[7])
namespace = runpy.run_path(str(builder_path), run_name="a1_gate_registry_snapshot")
lock = tomllib.loads(a0_lock.read_text(encoding="utf-8"))
names = sorted(
    {
        package["name"]
        for package in lock["package"]
        if package.get("source") == namespace["SPARSE_INDEX_SOURCE_ID"]
    },
    key=lambda value: value.encode("ascii"),
)
assert len(names) == 522
sparse_observed, sparse_selected = namespace["sparse_index_observation"](names)
assert {
    key: sparse_observed[key]
    for key in ("catalog_sha256", "file_count", "total_byte_count")
} == namespace["PREDECESSOR_SPARSE_INDEX_CATALOG"]
cargo_home.mkdir(mode=0o700)
namespace["copy_sparse_index"](cargo_home, sparse_selected)
namespace["validate_sparse_index_copy"](cargo_home, sparse_observed, sparse_selected)
observed = namespace["copy_locked_registry_archive_snapshot"](
    a0_lock,
    cargo_home / "registry/cache",
)
assert observed == {
    "archive_count": 555,
    "total_byte_count": 85385269,
    "tuple_catalog_sha256": "4ca4d49308fbf6c2e5d6952feca4c7079e24e2be88fa1b1d5b9ee11278137ed8",
}
runtime_cargo_home.mkdir(mode=0o700)
registry = runtime_cargo_home / "registry"
registry.mkdir(mode=0o700)
runtime_registry_shell.mkdir(mode=0o700)
for name in ("index", "cache", "src"):
    (runtime_registry_shell / name).mkdir(mode=0o700)
cache_tag = runtime_registry_shell / "CACHEDIR.TAG"
cache_tag.write_bytes(namespace["PREDECESSOR_CARGO_CACHE_TAG"])
cache_tag.chmod(0o444)
runtime_registry_shell.chmod(0o555)
runtime_registry_src.mkdir(mode=0o700)
runtime_user_registry_src.mkdir(mode=0o700)
PY
assert_tmp_identity

# Full replay then proves the immutable predecessor with its own gate.  The
# host kernel forbids nested unprivileged user namespaces, so the frozen four
# inner bwrap invocations are flattened only after an exact argv/environment
# allowlist match.  One outer namespace supplies the stronger common controls:
# no network or IPC, read-only root, no capabilities, private f2fs scratch/home,
# a private /run with exactly one pinned real GNURM and no socket, a private
# read-only root home with an independently
# seeded disposable root and user Cargo overlays for the two frozen lookup
# profiles, and catalog-verified read-only toolchain/registry inputs. Each accepted
# payload then receives its own Landlock write domain.
assert_tmp_identity
a0_repo="$tmp/a0-integration"
git_clean clone --quiet --no-hardlinks "$repo_root" "$a0_repo" \
  || fail "cannot clone immutable S21B-A0 predecessor"
[[ ! -s "$a0_repo/.git/objects/info/alternates" ]] \
  || fail "S21B-A0 predecessor replay clone uses alternates"
git_private "$a0_repo" checkout --quiet --detach "$packet_base_commit" \
  || fail "cannot checkout immutable S21B-A0 predecessor"
legacy_cascade="$tmp/legacy-cascade"
legacy_tmp="$tmp/legacy-tmp"
legacy_home="$tmp/legacy-home"
secure_proxy_dir="$tmp/secure-cargo-bin"
flatten_control="$tmp/predecessor-flatten-control"
flatten_launcher="$tmp/predecessor-bwrap-flatten-launcher.py"
cleanup_launcher="$tmp/predecessor-gnurm-cleanup-launcher.py"
real_gnurm="$tmp/predecessor-real-gnurm"
/usr/bin/mkdir -m 0700 \
  "$legacy_cascade" "$legacy_tmp" "$legacy_home" "$secure_proxy_dir" \
  "$flatten_control"
/usr/bin/chmod 1777 "$legacy_tmp"
/usr/bin/mkdir -m 0700 \
  "$legacy_home/.cargo" "$legacy_home/.rustup" "$legacy_home/.cache"
/usr/bin/mkdir -m 0700 \
  "$legacy_home/.cargo/bin" "$legacy_home/.cargo/registry" \
  "$legacy_home/.rustup/toolchains"
/usr/bin/mkdir -m 0700 \
  "$legacy_home/.rustup/toolchains/1.96.0-x86_64-unknown-linux-gnu" \
  "$legacy_home/.rustup/toolchains/stable-x86_64-unknown-linux-gnu"
for proxy in cargo rustc rustdoc rustfmt; do
  /usr/bin/ln -s \
    "/home/pallasting/.rustup/toolchains/1.96.0-x86_64-unknown-linux-gnu/bin/$proxy" \
    "$secure_proxy_dir/$proxy"
done
/usr/bin/python3 -I - "$builder" "$flatten_launcher" <<'PY' \
  || fail "cannot create predecessor bwrap flatten launcher"
import hashlib
import os
import pathlib
import runpy
import stat
import sys

namespace = runpy.run_path(sys.argv[1], run_name="a1_gate_bwrap_flatten_launcher")
payload = namespace["PREDECESSOR_BWRAP_FLATTEN_LAUNCHER"]
expected_digest = namespace["PREDECESSOR_BWRAP_FLATTEN_LAUNCHER_SHA256"]
assert hashlib.sha256(payload).hexdigest() == expected_digest
destination = pathlib.Path(sys.argv[2])
parent_descriptor = os.open(
    destination.parent,
    os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC,
)
try:
    descriptor = os.open(
        destination.name,
        os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC,
        0o500,
        dir_fd=parent_descriptor,
    )
    try:
        view = memoryview(payload)
        while view:
            written = os.write(descriptor, view)
            assert written > 0
            view = view[written:]
        os.fchmod(descriptor, 0o500)
        os.fsync(descriptor)
        observed = os.fstat(descriptor)
        assert (
            stat.S_ISREG(observed.st_mode)
            and stat.S_IMODE(observed.st_mode) == 0o500
            and observed.st_uid == os.geteuid()
            and observed.st_gid == os.getegid()
            and observed.st_nlink == 1
        )
    finally:
        os.close(descriptor)
    os.fsync(parent_descriptor)
finally:
    os.close(parent_descriptor)
PY
[[ -f "$flatten_launcher" && ! -L "$flatten_launcher" && \
  "$(/usr/bin/stat -c '%u:%g:%a:%h' "$flatten_launcher")" == \
    "$(/usr/bin/python3 -I -c 'import os; print(f"{os.geteuid()}:{os.getegid()}")'):500:1" && \
  "$(/usr/bin/sha256sum "$flatten_launcher" | /usr/bin/awk '{print $1}')" == \
  "22f0d16e7d0caae1642088a3b9736d21391e8fcc508edbabe8044f791fc85a83" ]] \
  || fail "predecessor bwrap flatten launcher identity drift"
/usr/bin/python3 -I - "$builder" "$cleanup_launcher" <<'PY' \
  || fail "cannot create predecessor gnurm cleanup launcher"
import os
import pathlib
import runpy
import stat
import sys

namespace = runpy.run_path(sys.argv[1], run_name="a1_gate_gnurm_cleanup_launcher")
payload = namespace["PREDECESSOR_GNURM_CLEANUP_LAUNCHER"]
destination = pathlib.Path(sys.argv[2])
parent_descriptor = os.open(
    destination.parent,
    os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC,
)
try:
    descriptor = os.open(
        destination.name,
        os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC,
        0o500,
        dir_fd=parent_descriptor,
    )
    try:
        view = memoryview(payload)
        while view:
            written = os.write(descriptor, view)
            assert written > 0
            view = view[written:]
        os.fchmod(descriptor, 0o500)
        os.fsync(descriptor)
        observed = os.fstat(descriptor)
        assert (
            stat.S_ISREG(observed.st_mode)
            and stat.S_IMODE(observed.st_mode) == 0o500
            and observed.st_nlink == 1
        )
    finally:
        os.close(descriptor)
    os.fsync(parent_descriptor)
finally:
    os.close(parent_descriptor)
PY
[[ "$(/usr/bin/sha256sum "$cleanup_launcher" | /usr/bin/awk '{print $1}')" == \
  "a3125b7a06201d141b509d7a15aaf51f9432886c9e5e64e2f4263836ded3d996" ]] \
  || fail "predecessor gnurm cleanup launcher digest drift"
/usr/bin/python3 -I - "$builder" "$real_gnurm" <<'PY' \
  || fail "cannot create pinned private real gnurm"
import hashlib
import os
import pathlib
import runpy
import stat
import sys

namespace = runpy.run_path(sys.argv[1], run_name="a1_gate_real_gnurm_snapshot")
expected_digest = namespace["PREDECESSOR_REAL_GNURM_SHA256"]
source = pathlib.Path("/usr/bin/gnurm")
destination = pathlib.Path(sys.argv[2])
rm_alias = pathlib.Path("/usr/bin/rm")
alias_observed = rm_alias.lstat()
assert (
    stat.S_ISLNK(alias_observed.st_mode)
    and alias_observed.st_uid == 0
    and alias_observed.st_gid == 0
    and alias_observed.st_nlink == 1
    and stat.S_IMODE(alias_observed.st_mode) == 0o777
    and os.readlink(rm_alias) == "gnurm"
    and rm_alias.samefile(source)
)
source_before = source.lstat()
assert (
    not source.is_symlink()
    and stat.S_ISREG(source_before.st_mode)
    and source_before.st_uid == 0
    and source_before.st_gid == 0
    and source_before.st_nlink == 1
    and stat.S_IMODE(source_before.st_mode) == 0o755
)
source_descriptor = os.open(
    source,
    os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC,
)
parent_descriptor = os.open(
    destination.parent,
    os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC,
)
try:
    opened_source = os.fstat(source_descriptor)
    source_identity = (
        source_before.st_dev,
        source_before.st_ino,
        source_before.st_mode,
        source_before.st_uid,
        source_before.st_gid,
        source_before.st_nlink,
        source_before.st_size,
        source_before.st_mtime_ns,
    )
    assert (
        opened_source.st_dev,
        opened_source.st_ino,
        opened_source.st_mode,
        opened_source.st_uid,
        opened_source.st_gid,
        opened_source.st_nlink,
        opened_source.st_size,
        opened_source.st_mtime_ns,
    ) == source_identity
    destination_descriptor = os.open(
        destination.name,
        os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC,
        0o700,
        dir_fd=parent_descriptor,
    )
    digest = hashlib.sha256()
    copied = 0
    try:
        while True:
            block = os.read(source_descriptor, 1024 * 1024)
            if not block:
                break
            digest.update(block)
            copied += len(block)
            view = memoryview(block)
            while view:
                written = os.write(destination_descriptor, view)
                assert written > 0
                view = view[written:]
        os.fchmod(destination_descriptor, 0o755)
        os.fsync(destination_descriptor)
        destination_observed = os.fstat(destination_descriptor)
        assert (
            stat.S_ISREG(destination_observed.st_mode)
            and stat.S_IMODE(destination_observed.st_mode) == 0o755
            and destination_observed.st_uid == os.geteuid()
            and destination_observed.st_gid == os.getegid()
            and destination_observed.st_nlink == 1
            and destination_observed.st_size == copied == source_before.st_size
            and digest.hexdigest() == expected_digest
        )
    finally:
        os.close(destination_descriptor)
    source_after = os.fstat(source_descriptor)
    assert (
        source_after.st_dev,
        source_after.st_ino,
        source_after.st_mode,
        source_after.st_uid,
        source_after.st_gid,
        source_after.st_nlink,
        source_after.st_size,
        source_after.st_mtime_ns,
    ) == source_identity
    os.fsync(parent_descriptor)
finally:
    os.close(parent_descriptor)
    os.close(source_descriptor)
PY
[[ "$(/usr/bin/sha256sum "$real_gnurm" | /usr/bin/awk '{print $1}')" == \
  "175a15a35617f84bb86692b50a3e21b41d8e21fdea242e952b31f1e2e80b1a54" ]] \
  || fail "private real gnurm digest drift"
assert_tmp_identity
/usr/bin/env -i PATH=/usr/bin:/bin LC_ALL=C TZ=UTC \
  /usr/bin/bwrap --die-with-parent --new-session --unshare-net --unshare-pid \
    --unshare-ipc \
    --uid 0 --gid 0 --cap-drop ALL \
    --ro-bind / / \
    --tmpfs /run \
    --ro-bind "$real_gnurm" /run/a1-real-gnurm \
    --tmpfs /root \
    --dir /root/.cargo \
    --remount-ro /root \
    --bind "$runtime_root_cargo_home" /root/.cargo \
    --ro-bind "$runtime_root_registry_shell" /root/.cargo/registry \
    --ro-bind "$predecessor_cargo_home/registry/index" \
      /root/.cargo/registry/index \
    --ro-bind "$predecessor_cargo_home/registry/cache" \
      /root/.cargo/registry/cache \
    --bind "$runtime_root_registry_src" /root/.cargo/registry/src \
    --bind "$legacy_tmp" /tmp \
    --bind "$legacy_cascade" /Data/CascadeProjects \
    --bind "$legacy_home" /home/pallasting \
    --ro-bind "$legacy_home/.cargo" /home/pallasting/.cargo \
    --ro-bind "$secure_proxy_dir" /home/pallasting/.cargo/bin \
    --ro-bind "$runtime_root_registry_shell" /home/pallasting/.cargo/registry \
    --ro-bind "$predecessor_cargo_home/registry/index" \
      /home/pallasting/.cargo/registry/index \
    --ro-bind "$predecessor_cargo_home/registry/cache" \
      /home/pallasting/.cargo/registry/cache \
    --bind "$runtime_user_registry_src" /home/pallasting/.cargo/registry/src \
    --ro-bind "$legacy_home/.rustup" /home/pallasting/.rustup \
    --ro-bind "$gate_toolchain" \
      /home/pallasting/.rustup/toolchains/1.96.0-x86_64-unknown-linux-gnu \
    --ro-bind "$gate_toolchain" \
      /home/pallasting/.rustup/toolchains/stable-x86_64-unknown-linux-gnu \
    --ro-bind "$repo_root" /opt \
    --ro-bind "$tmp/a0-Cargo.lock" /opt/Cargo.lock \
    --ro-bind "$flatten_launcher" /usr/bin/bwrap \
    --ro-bind "$cleanup_launcher" /usr/bin/gnurm \
    --bind "$flatten_control" /mnt \
    --dev /dev --proc /proc --clearenv \
    --setenv PATH /usr/bin:/bin:/home/pallasting/.cargo/bin \
    --setenv LC_ALL C --setenv TZ UTC \
    --setenv CARGO_BUILD_JOBS 1 --setenv RUST_TEST_THREADS 1 \
    --chdir "$a0_repo" /usr/bin/python3 -I -c \
      'import errno,os,pathlib,subprocess,sys
assert os.statvfs(sys.argv[1]).f_flag & os.ST_RDONLY
assert os.statvfs(sys.argv[2]).f_flag & os.ST_RDONLY
canonical_toolchain = pathlib.Path("/home/pallasting/.rustup/toolchains/1.96.0-x86_64-unknown-linux-gnu")
stable_toolchain = pathlib.Path("/home/pallasting/.rustup/toolchains/stable-x86_64-unknown-linux-gnu")
for relative in (".", "bin/cargo", "bin/rustc", "bin/rustdoc", "bin/rustfmt", "lib/rustlib/x86_64-unknown-linux-gnu/lib"):
    assert (canonical_toolchain / relative).samefile(stable_toolchain / relative), relative
for relative in ("bin/cargo", "bin/rustc", "bin/rustdoc", "bin/rustfmt"):
    member = stable_toolchain / relative
    assert member.is_file() and not member.is_symlink() and os.access(member, os.X_OK)
stable_sysroot = subprocess.check_output(
    [stable_toolchain / "bin/rustc", "--print", "sysroot"],
    env={"PATH": "/usr/bin:/bin", "LC_ALL": "C", "TZ": "UTC"},
    text=True,
).strip()
assert pathlib.Path(stable_sysroot) == stable_toolchain
assert os.statvfs("/root").f_flag & os.ST_RDONLY
assert not os.statvfs("/root/.cargo").f_flag & os.ST_RDONLY
assert os.statvfs("/root/.cargo/registry/index").f_flag & os.ST_RDONLY
assert os.statvfs("/root/.cargo/registry/cache").f_flag & os.ST_RDONLY
assert os.statvfs("/home/pallasting/.cargo").f_flag & os.ST_RDONLY
assert os.statvfs("/home/pallasting/.cargo/registry").f_flag & os.ST_RDONLY
assert os.statvfs("/home/pallasting/.cargo/registry/index").f_flag & os.ST_RDONLY
assert os.statvfs("/home/pallasting/.cargo/registry/cache").f_flag & os.ST_RDONLY
assert not os.statvfs("/home/pallasting/.cargo/registry/src").f_flag & os.ST_RDONLY
assert sorted(os.listdir("/root"), key=os.fsencode) == [".cargo"]
denied = (
    pathlib.Path("/root/.a1-denied-probe"),
    pathlib.Path("/root/.cargo/registry/.a1-denied-probe"),
    pathlib.Path("/root/.cargo/registry/index/.a1-denied-probe"),
    pathlib.Path("/root/.cargo/registry/cache/.a1-denied-probe"),
    pathlib.Path("/home/pallasting/.cargo/registry/.a1-denied-probe"),
    pathlib.Path("/home/pallasting/.cargo/registry/index/.a1-denied-probe"),
    pathlib.Path("/home/pallasting/.cargo/registry/cache/.a1-denied-probe"),
    pathlib.Path("/home/pallasting/.cargo/.a1-denied-probe"),
    pathlib.Path("/home/pallasting/.cargo/bin/.a1-denied-probe"),
)
for path in denied:
    assert not path.exists() and not path.is_symlink()
    try:
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    except OSError as error:
        assert error.errno == errno.EROFS, (path, error.errno)
    else:
        os.close(descriptor)
        raise AssertionError(f"read-only boundary accepted write: {path}")
probe = pathlib.Path("/root/.cargo/.a1-write-probe")
descriptor = os.open(probe, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
os.close(descriptor)
probe.unlink()
source_probe = pathlib.Path("/root/.cargo/registry/src/.a1-write-probe")
descriptor = os.open(source_probe, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
os.close(descriptor)
source_probe.unlink()
user_source_probe = pathlib.Path("/home/pallasting/.cargo/registry/src/.a1-write-probe")
descriptor = os.open(user_source_probe, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
os.close(descriptor)
user_source_probe.unlink()
assert sorted(os.listdir("/root"), key=os.fsencode) == [".cargo"]
os.execv(sys.argv[3], [sys.argv[3], sys.argv[4]])' \
      "$gate_toolchain" "$predecessor_cargo_home/registry" \
      "$a0_repo/$a0_gate_path" full-replay \
    </dev/null >"$tmp/a0.log" 2>&1 || {
      /usr/bin/tail -n 200 "$tmp/a0.log" >&2 || true
      fail "immutable S21B-A0 serial offline full replay failed"
    }
assert_tmp_identity
[[ -f "$flatten_launcher" && ! -L "$flatten_launcher" && \
  "$(/usr/bin/stat -c '%u:%g:%a:%h' "$flatten_launcher")" == \
    "$(/usr/bin/python3 -I -c 'import os; print(f"{os.geteuid()}:{os.getegid()}")'):500:1" && \
  "$(/usr/bin/sha256sum "$flatten_launcher" | /usr/bin/awk '{print $1}')" == \
    "22f0d16e7d0caae1642088a3b9736d21391e8fcc508edbabe8044f791fc85a83" ]] \
  || fail "predecessor bwrap flatten launcher changed during replay"
[[ -f "$cleanup_launcher" && ! -L "$cleanup_launcher" && \
  "$(/usr/bin/stat -c '%u:%g:%a:%h' "$cleanup_launcher")" == \
    "$(/usr/bin/python3 -I -c 'import os; print(f"{os.geteuid()}:{os.getegid()}")'):500:1" && \
  "$(/usr/bin/sha256sum "$cleanup_launcher" | /usr/bin/awk '{print $1}')" == \
    "a3125b7a06201d141b509d7a15aaf51f9432886c9e5e64e2f4263836ded3d996" ]] \
  || fail "predecessor gnurm cleanup launcher changed during replay"
[[ -f "$real_gnurm" && ! -L "$real_gnurm" && \
  "$(/usr/bin/stat -c '%u:%g:%a:%h' "$real_gnurm")" == \
    "$(/usr/bin/python3 -I -c 'import os; print(f"{os.geteuid()}:{os.getegid()}")'):755:1" && \
  "$(/usr/bin/sha256sum "$real_gnurm" | /usr/bin/awk '{print $1}')" == \
    "175a15a35617f84bb86692b50a3e21b41d8e21fdea242e952b31f1e2e80b1a54" ]] \
  || fail "private real gnurm changed during replay"
flatten_stages=(s21a s20b s20 runtime-prerequisite)
[[ "$({ /usr/bin/find "$flatten_control" -mindepth 1 -maxdepth 1 -type f -print; } | \
    /usr/bin/wc -l | /usr/bin/awk '{print $1}')" == 4 ]] \
  || fail "predecessor bwrap flatten receipt file count drift"
[[ -z "$(/usr/bin/find "$flatten_control" -mindepth 1 -maxdepth 1 \
    \( ! -type f -o -type l \) -print -quit)" ]] \
  || fail "predecessor bwrap flatten control contains a special entry"
for flatten_stage in "${flatten_stages[@]}"; do
  flatten_receipt="$flatten_control/flattened-$flatten_stage.receipt"
  [[ -f "$flatten_receipt" && ! -L "$flatten_receipt" && \
    "$(/usr/bin/stat -c '%u:%g:%a:%h' "$flatten_receipt")" == \
      "$(/usr/bin/python3 -I -c 'import os; print(f"{os.geteuid()}:{os.getegid()}")'):600:1" ]] \
    || fail "predecessor bwrap flatten receipt identity drift: $flatten_stage"
  [[ "$(/usr/bin/wc -l <"$flatten_receipt" | /usr/bin/awk '{print $1}')" == 4 ]] \
    || fail "predecessor bwrap flatten receipt row count drift: $flatten_stage"
  /usr/bin/grep -Fx $'stage\t'"$flatten_stage" "$flatten_receipt" >/dev/null \
    || fail "predecessor bwrap flatten stage receipt drift: $flatten_stage"
  /usr/bin/grep -Fx $'mode\tFLATTENED_ALREADY_SANDBOXED_PREDECESSOR_REPLAY' \
    "$flatten_receipt" >/dev/null \
    || fail "predecessor bwrap flatten mode receipt drift: $flatten_stage"
  /usr/bin/grep -Eq "$flatten_argv_receipt_ere" "$flatten_receipt" \
    || fail "predecessor bwrap flatten argv receipt drift: $flatten_stage"
  /usr/bin/grep -Fx $'gate\tPASS_STRICT_ALLOWLIST_AND_LANDLOCK_BEFORE_EXEC' \
    "$flatten_receipt" >/dev/null \
    || fail "predecessor bwrap flatten gate receipt drift: $flatten_stage"
done
a0_required_receipts=(
  $'validation_tier\tFULL_REPLAY_SERIAL_OFFLINE_IMMUTABLE_S21A_GATE_ONLY'
  $'release_qualification\tRELEASE_VALIDATION_PASS_NON_LIVE_BLOCKED_ONLY'
  $'s21a_full_replay\tPASS'
  $'presign_closure_status\tBLOCKED'
  $'owner_signature\tNOT_REQUESTED'
  $'live_canary\tNOT_RUN'
  $'side_effects_unlocked\tNONE'
  $'gate\tFULL_REPLAY_PASS_NON_LIVE_BLOCKED_PRESIGN_CLOSURE_ONLY'
)
for row in "${a0_required_receipts[@]}"; do
  /usr/bin/grep -Fx "$row" "$tmp/a0.log" >/dev/null \
    || fail "immutable S21B-A0 predecessor receipt incomplete: $row"
done
[[ -d "$legacy_home/.cache" && ! -L "$legacy_home/.cache" && \
    "$(/usr/bin/stat -c '%u:%a' "$legacy_home/.cache")" == \
      "$(/usr/bin/python3 -I -c 'import os; print(os.geteuid())'):700" && \
    ! -e "$legacy_home/.cache.a1-empty" && ! -L "$legacy_home/.cache.a1-empty" && \
    -z "$(/usr/bin/find "$legacy_home/.cache" -mindepth 1 -print -quit)" ]] \
  || fail "predecessor compatibility cache was not restored empty"
[[ -z "$(/usr/bin/find "$legacy_cascade" -mindepth 1 -print -quit)" ]] \
  || fail "predecessor legacy CascadeProjects scratch residue observed"
[[ -z "$(/usr/bin/find "$legacy_tmp" -mindepth 1 -print -quit)" ]] \
  || fail "predecessor legacy /tmp scratch residue observed"
/usr/bin/python3 -I - "$builder" "$repo_root" "$gate_toolchain" \
  "$predecessor_cargo_home" "$gate_cargo_home" "$tmp/a0-Cargo.lock" \
  "$runtime_root_cargo_home" \
  "$runtime_root_registry_shell" "$runtime_root_registry_src" \
  "$legacy_home/.cargo" "$runtime_user_registry_src" \
  "$secure_proxy_dir" <<'PY' \
  || fail "private predecessor inputs drifted during replay"
import json
import os
import pathlib
import runpy
import sys
import tomllib

builder_path = pathlib.Path(sys.argv[1])
repo = pathlib.Path(sys.argv[2])
toolchain = pathlib.Path(sys.argv[3])
predecessor_cargo_home = pathlib.Path(sys.argv[4])
target_cargo_home = pathlib.Path(sys.argv[5])
a0_lock = pathlib.Path(sys.argv[6])
runtime_cargo_home = pathlib.Path(sys.argv[7])
runtime_registry_shell = pathlib.Path(sys.argv[8])
runtime_registry_src = pathlib.Path(sys.argv[9])
runtime_user_cargo_home = pathlib.Path(sys.argv[10])
runtime_user_registry_src = pathlib.Path(sys.argv[11])
secure_proxy_dir = pathlib.Path(sys.argv[12])
namespace = runpy.run_path(str(builder_path), run_name="a1_gate_post_predecessor_snapshot")
manifest = json.loads((repo / namespace["TOOLCHAIN_MANIFEST_REL"]).read_bytes())
assert namespace["toolchain_tree_catalog"](toolchain) == manifest["toolchain_tree_catalog"]
archive_observation, _ = namespace["observe_locked_registry_archives"](
    a0_lock,
    predecessor_cargo_home / "registry/cache",
)
assert archive_observation == {
    "archive_count": 555,
    "total_byte_count": 85385269,
    "tuple_catalog_sha256": "4ca4d49308fbf6c2e5d6952feca4c7079e24e2be88fa1b1d5b9ee11278137ed8",
}
a0 = tomllib.loads(a0_lock.read_text(encoding="utf-8"))
a0_names = sorted(
    {
        package["name"]
        for package in a0["package"]
        if package.get("source") == namespace["SPARSE_INDEX_SOURCE_ID"]
    },
    key=lambda value: value.encode("ascii"),
)
sparse_observation, selected = namespace["sparse_index_observation"](a0_names)
assert {
    key: sparse_observation[key]
    for key in ("catalog_sha256", "file_count", "total_byte_count")
} == namespace["PREDECESSOR_SPARSE_INDEX_CATALOG"]
namespace["validate_sparse_index_copy"](
    predecessor_cargo_home,
    sparse_observation,
    selected,
)
target_lock = tomllib.loads((repo / "Cargo.lock").read_text(encoding="utf-8"))
target_names = sorted(
    {
        package["name"]
        for package in target_lock["package"]
        if package.get("source") == namespace["SPARSE_INDEX_SOURCE_ID"]
    },
    key=lambda value: value.encode("ascii"),
)
target_sparse_observation, target_selected = namespace["sparse_index_observation"](
    target_names
)
assert target_sparse_observation == manifest["cargo_registry_sparse_index"]
namespace["validate_sparse_index_copy"](
    target_cargo_home,
    target_sparse_observation,
    target_selected,
)
for cargo_root, source_root in (
    (runtime_cargo_home, runtime_registry_src),
    (runtime_user_cargo_home, runtime_user_registry_src),
):
    for path in (cargo_root, cargo_root / "registry", source_root):
        observed = path.lstat()
        assert path.is_dir() and not path.is_symlink()
        assert observed.st_uid == os.geteuid() and observed.st_gid == os.getegid()
        assert observed.st_mode & 0o777 == 0o700
    assert not any((cargo_root / "registry").iterdir())
assert not any((runtime_user_cargo_home / "bin").iterdir())
assert not runtime_registry_src.samefile(runtime_user_registry_src)
proxy_bin = secure_proxy_dir
assert proxy_bin.is_dir() and not proxy_bin.is_symlink()
assert sorted(os.listdir(proxy_bin), key=os.fsencode) == ["cargo", "rustc", "rustdoc", "rustfmt"]
for name in ("cargo", "rustc", "rustdoc", "rustfmt"):
    path = proxy_bin / name
    assert path.is_symlink()
    assert os.readlink(path) == (
        "/home/pallasting/.rustup/toolchains/1.96.0-x86_64-unknown-linux-gnu/bin/" + name
    )
shell_observed = runtime_registry_shell.lstat()
assert runtime_registry_shell.is_dir() and not runtime_registry_shell.is_symlink()
assert shell_observed.st_uid == os.geteuid() and shell_observed.st_gid == os.getegid()
assert shell_observed.st_mode & 0o777 == 0o555
assert sorted(path.name for path in runtime_registry_shell.iterdir()) == [
    "CACHEDIR.TAG", "cache", "index", "src"
]
for mountpoint in ("cache", "index", "src"):
    path = runtime_registry_shell / mountpoint
    assert path.is_dir() and not path.is_symlink() and not any(path.iterdir())
assert (runtime_registry_shell / "CACHEDIR.TAG").read_bytes() == namespace[
    "PREDECESSOR_CARGO_CACHE_TAG"
]
PY
assert_tmp_identity

# Work only in a private no-hardlink clone. A source HEAD gets a deterministic,
# temporary ordinary two-parent integration object whose tree is the source tree.
assert_tmp_identity
a1_repo="$tmp/a1-target"
git_clean clone --quiet --no-hardlinks "$repo_root" "$a1_repo" \
  || fail "cannot create private A1 validation clone"
[[ ! -s "$a1_repo/.git/objects/info/alternates" ]] \
  || fail "A1 validation clone uses alternates"
git_private "$a1_repo" remote set-url origin 'git@github.com:pallasting/Agent-Bridge.git' \
  || fail "cannot bind private clone to canonical remote identity"

receipt_target="HEAD_INTEGRATION"
full_validation_tier="FULL_REPLAY_SERIAL_OFFLINE_FINAL_INTEGRATION_DOUBLE_REBUILD"
release_qualification="RELEASE_VALIDATION_PASS_NON_LIVE_ROLE_BUILD_CLOSURE_ONLY"
gate_result="FULL_PASS_NON_LIVE_ROLE_BUILD_CLOSURE_ONLY"
build_target="$head_oid"
if [[ "$head_topology" == SOURCE ]]; then
  source_tree="$(git_private "$a1_repo" show -s --format='%T' "$source_commit")"
  build_target="$(
    GIT_AUTHOR_NAME='Agent-Bridge S21B-A1 Provisional Gate' \
    GIT_AUTHOR_EMAIL='s21b-a1-provisional-gate@invalid' \
    GIT_AUTHOR_DATE='946684800 +0000' \
    GIT_COMMITTER_NAME='Agent-Bridge S21B-A1 Provisional Gate' \
    GIT_COMMITTER_EMAIL='s21b-a1-provisional-gate@invalid' \
    GIT_COMMITTER_DATE='946684800 +0000' \
    git_private "$a1_repo" -c commit.gpgsign=false commit-tree "$source_tree" \
      -p "$source_base_commit" -p "$source_commit" <<'EOF'
S21B-A1 private provisional integration for non-release validation only
EOF
  )" || fail "cannot create private provisional A1 integration"
  [[ "$build_target" =~ ^[0-9a-f]{40}$ ]] || fail "provisional integration OID invalid"
  receipt_target="PROVISIONAL_PRIVATE_INTEGRATION"
  full_validation_tier="FULL_REPLAY_SERIAL_OFFLINE_PROVISIONAL_INTEGRATION_DOUBLE_REBUILD"
  release_qualification="PROVISIONAL_SOURCE_VALIDATION_PASS_NON_RELEASE"
  gate_result="FULL_PROVISIONAL_PASS_NON_LIVE_ROLE_BUILD_CLOSURE_ONLY"
fi
git_private "$a1_repo" checkout --quiet --detach "$build_target" \
  || fail "cannot checkout private A1 validation target"
[[ -z "$(git_private "$a1_repo" status --porcelain=v1 --untracked-files=all)" ]] \
  || fail "private A1 validation target is not clean"
assert_tmp_identity

toolchain_root="$gate_toolchain"
cargo="$toolchain_root/bin/cargo"
rustc="$toolchain_root/bin/rustc"
rustdoc="$toolchain_root/bin/rustdoc"
rustfmt="$toolchain_root/bin/rustfmt"
for tool in "$cargo" "$rustc" "$rustdoc" "$rustfmt"; do
  [[ -x "$tool" ]] || fail "fixed Rust toolchain member absent: $tool"
done
/usr/bin/mkdir -m 0700 "$tmp/role-cargo-target" "$tmp/home" "$tmp/runtime-tmp"
target_epoch="$(git_private "$a1_repo" show -s --format='%ct' "$build_target")"
rust_env=(
  /usr/bin/env -i
  PATH="$toolchain_root/bin:/usr/bin:/bin"
  HOME="$tmp/home" TMPDIR="$tmp/runtime-tmp" LC_ALL=C TZ=UTC
  PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1 PYTHONSAFEPATH=1
  CARGO_HOME="$gate_cargo_home" CARGO_NET_OFFLINE=true
  CARGO_TARGET_DIR="$tmp/role-cargo-target" CARGO_INCREMENTAL=0
  CARGO_BUILD_JOBS=1 RUST_TEST_THREADS=1
  RUSTC="$rustc" RUSTDOC="$rustdoc" RUSTFMT="$rustfmt"
  SOURCE_DATE_EPOCH="$target_epoch"
)
"${rust_env[@]}" "$cargo" test --manifest-path "$a1_repo/$role_manifest_path" \
  --frozen --locked --offline --no-default-features \
  --target x86_64-unknown-linux-gnu -j 1 >"$tmp/role-test.log" 2>&1 || {
    /usr/bin/tail -n 200 "$tmp/role-test.log" >&2 || true
    fail "serial frozen offline role crate tests failed"
  }
"${rust_env[@]}" "$cargo" --frozen --offline fmt \
  --manifest-path "$a1_repo/$role_manifest_path" \
  -- --check >"$tmp/role-fmt.log" 2>&1 || {
    /usr/bin/tail -n 200 "$tmp/role-fmt.log" >&2 || true
    fail "role crate rustfmt check failed"
  }
"${rust_env[@]}" "$cargo" metadata --manifest-path "$a1_repo/$workspace_manifest_path" \
  --format-version=1 --frozen --locked --offline --no-deps \
  >"$tmp/role-metadata.json" 2>"$tmp/role-metadata.err" || {
    /usr/bin/tail -n 200 "$tmp/role-metadata.err" >&2 || true
    fail "frozen offline role crate metadata failed"
  }
/usr/bin/python3 -I - "$tmp/role-metadata.json" "$a1_repo/$role_manifest_path" <<'PY' \
  || fail "role crate metadata boundary drift"
import json
import pathlib
import sys

metadata = json.loads(pathlib.Path(sys.argv[1]).read_text(encoding="utf-8"))
manifest = pathlib.Path(sys.argv[2]).resolve(strict=True)
packages = [item for item in metadata["packages"] if item["name"] == "ab-owned-lab-role-artifacts"]
assert len(packages) == 1
package = packages[0]
assert pathlib.Path(package["manifest_path"]).resolve(strict=True) == manifest
assert package["dependencies"] == []
assert package["features"] == {"default": []}
assert package["publish"] == []
assert package["id"] in metadata["workspace_members"]
assert package["id"] not in metadata["workspace_default_members"]
targets = {(item["name"], tuple(item["kind"]), tuple(item["crate_types"])) for item in package["targets"]}
assert targets == {
    ("ab_owned_lab_role_artifacts", ("lib",), ("lib",)),
    ("ab-owned-lab-controller", ("bin",), ("bin",)),
    ("ab-owned-lab-observer", ("bin",), ("bin",)),
    ("ab-owned-lab-runner", ("bin",), ("bin",)),
    ("ab-owned-lab-validator", ("bin",), ("bin",)),
}
PY
[[ -z "$(git_private "$a1_repo" status --porcelain=v1 --untracked-files=all)" ]] \
  || fail "role checks modified the private A1 source tree"

release_truth_gate="$a1_repo/$release_truth_gate_path"
[[ -x "$release_truth_gate" && ! -L "$release_truth_gate" ]] \
  || fail "release-truth gate absent or non-executable"
"${rust_env[@]}" "$release_truth_gate" >"$tmp/release-truth.log" 2>&1 || {
  /usr/bin/tail -n 200 "$tmp/release-truth.log" >&2 || true
  fail "read-only release-truth gate failed"
}
release_truth_rows=(
  'Agent-Bridge release truth JSON verification passed'
  'Agent-Bridge release and embedding documentation verification passed'
  'Agent-Bridge release truth report verification passed'
)
for row in "${release_truth_rows[@]}"; do
  /usr/bin/grep -Fx "$row" "$tmp/release-truth.log" >/dev/null \
    || fail "release-truth gate receipt incomplete: $row"
done
[[ -z "$(git_private "$a1_repo" status --porcelain=v1 --untracked-files=all)" ]] \
  || fail "release-truth gate modified the private A1 source tree"
assert_tmp_identity

builder="$a1_repo/$builder_path"
[[ -f "$builder" && ! -L "$builder" ]] || fail "A1 reproducible builder absent"
builder_scratch="$tmp/builder-scratch"
builder_receipt="$tmp/role-build-receipt.json"
/usr/bin/env -i PATH=/usr/bin:/bin LC_ALL=C TZ=UTC PYTHONDONTWRITEBYTECODE=1 \
  PYTHONNOUSERSITE=1 PYTHONSAFEPATH=1 \
  /usr/bin/python3 -I "$builder" --repo "$a1_repo" --target "$build_target" \
  --scratch "$builder_scratch" --output "$builder_receipt" \
  >"$tmp/builder.stdout" 2>"$tmp/builder.stderr" || {
    /usr/bin/tail -n 200 "$tmp/builder.stderr" >&2 || true
    fail "A1 clean-archive double rebuild failed"
  }
assert_tmp_identity
[[ ! -s "$tmp/builder.stderr" ]] || fail "A1 builder emitted stderr on success"
[[ -f "$builder_receipt" && ! -L "$builder_receipt" ]] \
  || fail "A1 builder did not emit one regular receipt"

build_target_tree="$(git_private "$a1_repo" show -s --format='%T' "$build_target")"
build_target_lineage=()
IFS=' ' read -r -a build_target_lineage \
  < <(git_private "$a1_repo" rev-list --parents -n 1 "$build_target") \
  || fail "cannot resolve validated build-target topology"
build_target_parents=("${build_target_lineage[@]:1}")
[[ "${#build_target_parents[@]}" == 2 && "${build_target_parents[1]}" == "$source_commit" ]] \
  || fail "validated build-target parent topology drift"
build_target_first_parent="${build_target_parents[0]}"
source_tree="$(git_private "$a1_repo" show -s --format='%T' "$source_commit")"
git_private "$a1_repo" -c tar.umask=0022 archive --format=tar "$build_target" \
  >"$tmp/gate-target.tar" || fail "cannot independently reconstruct A1 target archive"
gate_target_archive_sha256="$(/usr/bin/sha256sum "$tmp/gate-target.tar" | /usr/bin/awk '{print $1}')"
gate_target_archive_byte_count="$(/usr/bin/wc -c <"$tmp/gate-target.tar" | /usr/bin/awk '{print $1}')"
/usr/bin/rm -f -- "$tmp/gate-target.tar"
gate_target_cargo_lock_sha256="$({
  git_private "$a1_repo" cat-file blob "$build_target:$cargo_lock_path"
} | /usr/bin/sha256sum | /usr/bin/awk '{print $1}')"

/usr/bin/python3 -I - "$a1_repo/$receipt_schema_path" "$builder_receipt" \
  "$build_target" "$source_commit" "$source_base_commit" "$packet_base_commit" \
  "$build_target_tree" "$build_target_first_parent" "$source_tree" \
  "$source_base_tree" "$target_epoch" \
  "$gate_target_archive_sha256" "$gate_target_archive_byte_count" \
  "$gate_target_cargo_lock_sha256" >"$tmp/receipt-self-sha256" <<'PY' \
  || fail "A1 real receipt schema or semantic validation failed"
import hashlib
import json
import pathlib
import struct
import sys

from jsonschema import Draft202012Validator

schema_path, receipt_path = map(pathlib.Path, sys.argv[1:3])
target, source, source_base, a0_base = sys.argv[3:7]
target_tree, target_first_parent, source_tree, source_base_tree = sys.argv[7:11]
target_epoch = int(sys.argv[11])
target_archive_sha256, target_archive_byte_count, target_cargo_lock_sha256 = (
    sys.argv[12], int(sys.argv[13]), sys.argv[14]
)

def no_duplicates(pairs):
    result = {}
    for key, value in pairs:
        assert key not in result
        result[key] = value
    return result

raw = receipt_path.read_bytes()
assert raw.endswith(b"\n") and not raw.endswith(b"\n\n")
assert raw[:-1].isascii()
receipt = json.loads(raw[:-1], object_pairs_hook=no_duplicates, parse_float=lambda _: (_ for _ in ()).throw(AssertionError()))
canonical = json.dumps(receipt, ensure_ascii=True, allow_nan=False, sort_keys=True, separators=(",", ":")).encode("ascii")
assert raw == canonical + b"\n"
schema = json.loads(schema_path.read_text(encoding="ascii"), object_pairs_hook=no_duplicates)
Draft202012Validator.check_schema(schema)
Draft202012Validator(schema).validate(receipt)

domain = b"agent-bridge/biocortex/owned-lab/s21b-a1/role-build-receipt/v1"
payload_object = dict(receipt)
claimed = payload_object.pop("role_build_receipt_sha256")
payload = json.dumps(payload_object, ensure_ascii=True, allow_nan=False, sort_keys=True, separators=(",", ":")).encode("ascii")
computed = hashlib.sha256(struct.pack(">I", len(domain)) + domain + struct.pack(">Q", len(payload)) + payload).hexdigest()
assert claimed == computed and claimed != "0" * 64

assert receipt["schema"] == "agent_bridge.memory_temporal_owned_lab_role_build_receipt_s21b_a1.v0"
assert receipt["packet_kind"] == "S21B_A1_ROLE_BUILD_CLOSURE_RECEIPT"
assert receipt["status"] == "S21B_A1_POST_INTEGRATION_ROLE_BUILD_CLOSURE_VERIFIED_NON_LIVE"
assert receipt["receipt_state"] == "POST_INTEGRATION_DOUBLE_REBUILD_VERIFIED_NON_LIVE"
assert receipt["test_only"] is False and receipt["synthetic"] is False
binding = receipt["target_binding"]
assert binding["a0_integration_commit"] == a0_base
assert binding["source_commit"] == source
assert binding["source_tree"] == source_tree
assert binding["source_parent_commit"] == source_base
assert binding["source_parent_tree"] == source_base_tree
assert binding["integration_commit"] == target
assert binding["integration_tree"] == target_tree
assert binding["integration_first_parent"] == target_first_parent
assert binding["integration_second_parent"] == source
assert binding["target_committer_epoch"] == target_epoch
assert binding["integrated_archive_sha256"] == target_archive_sha256
assert binding["integrated_archive_byte_count"] == target_archive_byte_count
assert binding["cargo_lock_sha256"] == target_cargo_lock_sha256
assert binding["target_refrozen"] is True
assert binding["candidate_supplied_target_used"] is False

closures = receipt["closure_bindings"]
assert closures["candidate_supplied_expected_digests_used"] is False
for key in ("toolchain_manifest", "feature_set", "schema_set", "build_recipes"):
    item = closures[key]
    assert item["definition_present"] is True
    assert item["independently_recomputed_in_build_a"] is True
    assert item["independently_recomputed_in_build_b"] is True
    assert item["rebuild_values_equal"] is True
    assert isinstance(item["manifest_sha256"], str) and item["manifest_sha256"] != "0" * 64
assert isinstance(closures["schema_set"]["content_set_sha256"], str)

rebuilds = receipt["rebuilds"]
for key in ("build_roots_distinct", "target_directories_distinct", "all_role_outputs_byte_equal", "all_closure_digests_equal", "schema_content_set_digests_equal"):
    assert rebuilds[key] is True
for label, key in (("A", "build_a"), ("B", "build_b")):
    build = rebuilds[key]
    assert build["build_label"] == label and build["completed"] is True
    assert build["clean_archive_root_fresh"] is True and build["target_directory_fresh"] is True
    assert build["network_disabled"] is True and build["incremental_state_shared"] is False
    assert build["candidate_supplied_expected_digests_used"] is False
    assert build["source_archive_sha256"] == target_archive_sha256
    assert build["source_archive_byte_count"] == target_archive_byte_count
    assert build["cargo_lock_sha256"] == target_cargo_lock_sha256
    for digest_key in ("source_archive_sha256", "cargo_lock_sha256", "toolchain_manifest_sha256", "feature_set_sha256", "schema_set_sha256", "schema_content_set_sha256", "build_recipes_sha256"):
        assert isinstance(build[digest_key], str) and len(build[digest_key]) == 64 and build[digest_key] != "0" * 64
assert rebuilds["build_a"]["toolchain_manifest_sha256"] == rebuilds["build_b"]["toolchain_manifest_sha256"] == closures["toolchain_manifest"]["manifest_sha256"]
assert rebuilds["build_a"]["feature_set_sha256"] == rebuilds["build_b"]["feature_set_sha256"] == closures["feature_set"]["manifest_sha256"]
assert rebuilds["build_a"]["schema_set_sha256"] == rebuilds["build_b"]["schema_set_sha256"] == closures["schema_set"]["manifest_sha256"]
assert rebuilds["build_a"]["schema_content_set_sha256"] == rebuilds["build_b"]["schema_content_set_sha256"] == closures["schema_set"]["content_set_sha256"]
assert rebuilds["build_a"]["build_recipes_sha256"] == rebuilds["build_b"]["build_recipes_sha256"] == closures["build_recipes"]["manifest_sha256"]

roles = receipt["role_artifacts"]
assert roles["required_role_count"] == 4 and roles["completed_role_count"] == 4
for key in ("raw_sha256_pairwise_distinct", "identity_sha256_pairwise_distinct", "build_recipe_sha256_pairwise_distinct"):
    assert roles[key] is True
assert roles["private_library_or_test_binary_used"] is False
assert roles["arbitrary_digest_substitution_used"] is False
expected_bins = {
    "controller": "ab-owned-lab-controller",
    "observer": "ab-owned-lab-observer",
    "runner": "ab-owned-lab-runner",
    "validator": "ab-owned-lab-validator",
}
raw_digests = set()
identity_digests = set()
recipe_digests = set()
for role, binary in expected_bins.items():
    item = roles[role]
    assert item["role"] == role and item["cargo_binary_target"] == binary
    assert item["raw_bytes_equal"] is True and item["raw_sha256_equal"] is True
    assert item["identity_sha256_equal"] is True and item["build_recipe_sha256_equal"] is True
    a, b = item["build_a"], item["build_b"]
    for observation in (a, b):
        assert observation["artifact_present"] is True and observation["regular_file"] is True
        assert observation["executable"] is True and observation["observed_mode_octal"] == "0755"
        assert observation["identity_packet_kind"] == "S21B_A1_NON_LIVE_ROLE_ARTIFACT_IDENTITY"
        assert observation["identity_terminal_lf_count"] == 1
    for key in ("raw_sha256", "identity_sha256", "build_recipe_sha256"):
        assert a[key] == b[key] and isinstance(a[key], str) and a[key] != "0" * 64
    assert a["byte_count"] == b["byte_count"] and a["byte_count"] > 0
    raw_digests.add(a["raw_sha256"])
    identity_digests.add(a["identity_sha256"])
    recipe_digests.add(a["build_recipe_sha256"])
assert len(raw_digests) == len(identity_digests) == len(recipe_digests) == 4

forbidden = receipt["forbidden_outputs"]
for key, value in forbidden.items():
    if key == "live_action_count":
        assert value == 0
    elif key.endswith("_sha256"):
        assert value is None
    else:
        assert value is False
result = receipt["result"]
assert result["role_build_closure_complete"] is True
assert result["separate_unsigned_subject_contract_stage_may_begin"] is True
assert result["next_action"] == "BEGIN_SEPARATE_UNSIGNED_SUBJECT_CONTRACT_REBINDING_AND_GENERATION_REVIEW"
assert result["unsigned_final_subject_may_be_generated_by_this_stage"] is False
assert result["owner_signature_may_be_requested"] is False
assert result["owner_interaction_required_now"] is False
assert result["live_execution_may_begin"] is False
assert result["terminal_hard_lock"] is False
assert result["side_effects_unlocked"] == "NONE"
for key, value in receipt["nonclaims"].items():
    if key == "side_effects_unlocked":
        assert value == "NONE"
    elif key == "synthetic_fixture_is_real_build_evidence":
        assert value is False
    else:
        assert value is False
print(computed)
PY
receipt_self_sha256="$(/usr/bin/awk 'NR == 1 { print $1 }' "$tmp/receipt-self-sha256")"
[[ "$receipt_self_sha256" =~ ^[0-9a-f]{64}$ ]] || fail "validated receipt self digest absent"
expected_builder_stdout="S21B_A1_ROLE_BUILD_RECEIPT_WRITTEN path=$builder_receipt sha256=$receipt_self_sha256"
[[ "$(/usr/bin/wc -l <"$tmp/builder.stdout" | /usr/bin/awk '{print $1}')" == 1 ]] \
  || fail "A1 builder success output is not exactly one line"
/usr/bin/grep -Fx "$expected_builder_stdout" "$tmp/builder.stdout" >/dev/null \
  || fail "A1 builder success output does not bind the validated receipt"

receipt_persistence="EPHEMERAL_VALIDATED_REMOVED"
if [[ -n "$external_receipt" ]]; then
  /usr/bin/python3 -I - "$builder_receipt" "$external_receipt" \
    "$repo_root" "$common_dir" <<'PY' \
    || fail "cannot persist validated A1 receipt without overwrite"
import os
import pathlib
import stat
import sys

source = pathlib.Path(sys.argv[1])
destination = pathlib.Path(sys.argv[2])
repo = pathlib.Path(sys.argv[3]).resolve(strict=True)
common = pathlib.Path(sys.argv[4]).resolve(strict=True)

parent_input = destination.parent.absolute()
parent = destination.parent.resolve(strict=True)
assert parent_input == parent and parent.is_dir() and not parent.is_symlink()
assert destination == parent / destination.name
assert destination.name not in ("", ".", "..")

current = pathlib.Path(parent.anchor)
members = [current]
for part in parent.parts[1:]:
    current /= part
    members.append(current)
for member in members:
    observed = member.lstat()
    assert stat.S_ISDIR(observed.st_mode) and not member.is_symlink()
    assert observed.st_uid in (0, os.geteuid())
    writable = observed.st_mode & (stat.S_IWGRP | stat.S_IWOTH)
    sticky_root = observed.st_uid == 0 and bool(observed.st_mode & stat.S_ISVTX)
    assert not writable or sticky_root

def within(path: pathlib.Path, boundary: pathlib.Path) -> bool:
    try:
        path.relative_to(boundary)
    except ValueError:
        return False
    return True

assert not within(destination, repo) and not within(destination, common)
parent_before = os.stat(parent, follow_symlinks=False)
assert stat.S_ISDIR(parent_before.st_mode)
parent_fd = os.open(
    parent,
    os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC,
)
created_identity = None
try:
    parent_pinned = os.fstat(parent_fd)
    parent_identity = (parent_pinned.st_dev, parent_pinned.st_ino)
    assert stat.S_ISDIR(parent_pinned.st_mode)
    assert parent_identity == (parent_before.st_dev, parent_before.st_ino)
    try:
        os.stat(destination.name, dir_fd=parent_fd, follow_symlinks=False)
    except FileNotFoundError:
        pass
    else:
        raise FileExistsError(destination)

    source_fd = os.open(source, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC)
    try:
        source_stat = os.fstat(source_fd)
        assert stat.S_ISREG(source_stat.st_mode)
        raw = bytearray()
        while True:
            block = os.read(source_fd, 1024 * 1024)
            if not block:
                break
            raw.extend(block)
        destination_fd = os.open(
            destination.name,
            os.O_RDWR | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC,
            0o600,
            dir_fd=parent_fd,
        )
        try:
            created = os.fstat(destination_fd)
            assert stat.S_ISREG(created.st_mode)
            created_identity = (created.st_dev, created.st_ino)
            view = memoryview(raw)
            while view:
                written = os.write(destination_fd, view)
                assert written > 0
                view = view[written:]
            os.fchmod(destination_fd, 0o600)
            os.fsync(destination_fd)
            os.lseek(destination_fd, 0, os.SEEK_SET)
            observed = bytearray()
            while len(observed) < len(raw):
                block = os.read(destination_fd, min(1024 * 1024, len(raw) - len(observed)))
                assert block
                observed.extend(block)
            assert os.read(destination_fd, 1) == b""
            assert observed == raw
            final_file = os.fstat(destination_fd)
            assert stat.S_IMODE(final_file.st_mode) == 0o600
            entry = os.stat(destination.name, dir_fd=parent_fd, follow_symlinks=False)
            assert stat.S_ISREG(entry.st_mode)
            assert (entry.st_dev, entry.st_ino) == created_identity
        finally:
            os.close(destination_fd)
    finally:
        os.close(source_fd)
    os.fsync(parent_fd)
    parent_after = os.stat(parent, follow_symlinks=False)
    assert stat.S_ISDIR(parent_after.st_mode)
    assert (parent_after.st_dev, parent_after.st_ino) == parent_identity
except BaseException:
    if created_identity is not None:
        try:
            entry = os.stat(destination.name, dir_fd=parent_fd, follow_symlinks=False)
            if (entry.st_dev, entry.st_ino) == created_identity:
                os.unlink(destination.name, dir_fd=parent_fd)
                os.fsync(parent_fd)
        except FileNotFoundError:
            pass
    raise
finally:
    os.close(parent_fd)
PY
  [[ -f "$external_receipt" && ! -L "$external_receipt" ]] \
    || fail "persisted external A1 receipt is not a regular file"
  [[ "$(/usr/bin/stat -c '%a' "$external_receipt")" == 600 ]] \
    || fail "persisted external A1 receipt mode is not 0600"
  /usr/bin/cmp -s "$builder_receipt" "$external_receipt" \
    || fail "persisted external A1 receipt bytes drifted"
  receipt_persistence="PERSISTED_EXTERNAL_NO_OVERWRITE"
fi

if [[ "$head_topology" == SOURCE ]]; then
  [[ -z "$external_receipt" ]] || fail "provisional source receipt persistence invariant failed"
fi

printf '%s\n' \
  $'validation_tier\t'"$full_validation_tier" \
  $'release_qualification\t'"$release_qualification" \
  $'head_topology\t'"$head_topology" \
  $'a0_predecessor_replay\tPASS' \
  $'a0_predecessor_namespace\tSINGLE_OUTER_NETWORKLESS_READ_ONLY_ROOT_STRICT_FOUR_CALL_FLATTEN_ADAPTER' \
  $'a0_predecessor_registry\tPRIVATE_PRIMARY_PLUS_DEDICATED_RUNTIME_555_ARCHIVE_523_INDEX_CATALOG_VERIFIED_NESTED_READ_ONLY' \
  $'a1_target_sparse_index\tPRIVATE_532_FILE_CATALOG_VERIFIED_SEPARATE_FROM_PREDECESSOR' \
  $'role_rust_checks\tPASS' \
  $'release_truth_gate\tPASS' \
  $'double_rebuild\tPASS' \
  $'receipt_target\t'"$receipt_target" \
  $'receipt_persistence\t'"$receipt_persistence" \
  $'owner_signature\tNOT_REQUESTED' \
  $'live_canary\tNOT_RUN' \
  $'side_effects_unlocked\tNONE' \
  $'gate\t'"$gate_result"
