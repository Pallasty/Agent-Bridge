#!/usr/bin/bash
set -euo pipefail
umask 077

baseline="b9988aa5772928fb964c8d47b4f294a69f5122ac"
baseline_tree="cb5717640a2061c092094f88abbe8db1c0f63409"
baseline_parents="0be03cfdbee77f0bc29559e0795fa3ec77f07357 b5f0d060736845ad9886226e4573e5385ca752b9"
feature="temporal-evidence-s14-recovered-envelope-source-synthetic"
checker="scripts/eval/check_memory_temporal_recovered_envelope_source_s14.py"
expected="scripts/eval/fixtures/memory_temporal_recovered_envelope_source_s14.expected.v0.tsv"
report="docs/reports/goal-c-u/2026-07-15-biocortex-ab-track-b-recovered-envelope-source-s14.md"
s13_gate="scripts/check-memory-temporal-recovered-envelope-delivery-s13.sh"
s13_baseline="a3cb958e36743b3ce52b86a66e99ae2366b5bc89"
s13_source="b5f0d060736845ad9886226e4573e5385ca752b9"
s13_integration="$baseline"

trusted_path="/usr/bin:/bin"
rustup_home="/home/pallasting/.rustup"
cargo_home="/home/pallasting/.cargo"
toolchain_bin="$rustup_home/toolchains/stable-x86_64-unknown-linux-gnu/bin"
trusted_cargo_path="/usr/bin:/bin:$toolchain_bin"
cargo_bin="$toolchain_bin/cargo"
rustfmt_bin="$toolchain_bin/rustfmt"
rustc_bin="$toolchain_bin/rustc"
PATH="$trusted_path"
export PATH LANG=C.UTF-8 LC_ALL=C.UTF-8
export PYTHONDONTWRITEBYTECODE=1 PYTHONHASHSEED=0

unset BASH_ENV ENV CDPATH PERL5OPT PERL5LIB PERL_UNICODE
unset TAR_OPTIONS
unset LD_AUDIT LD_LIBRARY_PATH LD_PRELOAD
unset PYTHONPATH PYTHONHOME PYTHONINSPECT PYTHONSTARTUP PYTHONWARNINGS
unset PYTHONBREAKPOINT PYTHONUSERBASE
unset GIT_DIR GIT_WORK_TREE GIT_COMMON_DIR GIT_INDEX_FILE
unset GIT_OBJECT_DIRECTORY GIT_ALTERNATE_OBJECT_DIRECTORIES
unset GIT_REPLACE_REF_BASE GIT_CONFIG GIT_CONFIG_COUNT
unset GIT_CONFIG_PARAMETERS GIT_NAMESPACE GIT_SHALLOW_FILE
unset GIT_CEILING_DIRECTORIES GIT_DISCOVERY_ACROSS_FILESYSTEM
unset GIT_EXEC_PATH GIT_EXTERNAL_DIFF GIT_DIFF_OPTS
unset RUSTC RUSTC_WRAPPER RUSTC_WORKSPACE_WRAPPER RUSTDOC RUSTDOCFLAGS
unset RUSTFLAGS CARGO CARGO_TARGET_DIR CARGO_BUILD_JOBS CARGO_INCREMENTAL
unset CARGO_ENCODED_RUSTFLAGS CARGO_HOME RUSTUP_HOME
export GIT_CONFIG_NOSYSTEM=1
export GIT_CONFIG_GLOBAL=/dev/null
export GIT_CONFIG_SYSTEM=/dev/null

source_paths=(
  "crates/store/Cargo.toml"
  "crates/store/src/temporal_replay_transport/external_operation_recovery.rs"
  "crates/store/src/temporal_replay_transport/recovered_s9_decision_reverification/recovered_envelope_delivery.rs"
  "crates/store/src/temporal_replay_transport/recovered_s9_decision_reverification/recovered_envelope_delivery/recovered_envelope_source.rs"
  "docs/design/MEMORY_TEMPORAL_RECOVERED_ENVELOPE_SOURCE_S14_2026_07_15.md"
  "docs/design/fixtures/biocortex-ab-track-b-recovered-envelope-source-s14-v0.json"
  "docs/design/fixtures/biocortex-ab-track-b-successor-admission-gate-s14-v0.json"
  "docs/reports/goal-c-u/2026-07-15-biocortex-ab-track-b-recovered-envelope-source-s14.md"
  "scripts/check-memory-temporal-recovered-envelope-source-s14.sh"
  "scripts/eval/check_memory_temporal_recovered_envelope_source_s14.py"
  "scripts/eval/fixtures/memory_temporal_recovered_envelope_source_s14.expected.v0.tsv"
)

glue_paths=(
  "crates/store/Cargo.toml"
  "crates/store/src/temporal_replay_transport/external_operation_recovery.rs"
  "crates/store/src/temporal_replay_transport/recovered_s9_decision_reverification/recovered_envelope_delivery.rs"
)

packet_paths=(
  "crates/store/src/temporal_replay_transport/recovered_s9_decision_reverification/recovered_envelope_delivery/recovered_envelope_source.rs"
  "docs/design/MEMORY_TEMPORAL_RECOVERED_ENVELOPE_SOURCE_S14_2026_07_15.md"
  "docs/design/fixtures/biocortex-ab-track-b-recovered-envelope-source-s14-v0.json"
  "docs/design/fixtures/biocortex-ab-track-b-successor-admission-gate-s14-v0.json"
  "docs/reports/goal-c-u/2026-07-15-biocortex-ab-track-b-recovered-envelope-source-s14.md"
  "scripts/check-memory-temporal-recovered-envelope-source-s14.sh"
  "scripts/eval/check_memory_temporal_recovered_envelope_source_s14.py"
  "scripts/eval/fixtures/memory_temporal_recovered_envelope_source_s14.expected.v0.tsv"
)

fail() {
  printf 'S14_GATE_FAILED\t%s\n' "$*" >&2
  exit 1
}

for tool in /usr/bin/awk /usr/bin/bash /usr/bin/cat /usr/bin/chmod /usr/bin/cmp \
  /usr/bin/diff /usr/bin/env /usr/bin/find /usr/bin/git /usr/bin/grep \
  /usr/bin/ln /usr/bin/mkdir /usr/bin/mktemp /usr/bin/python3 \
  /usr/bin/readlink /usr/bin/rm \
  /usr/bin/sha256sum /usr/bin/sort /usr/bin/stat /usr/bin/tail \
  /usr/bin/tar /usr/bin/tee; do
  [[ -x "$tool" ]] || fail "missing trusted executable: $tool"
done
for tool in "$cargo_bin" "$rustfmt_bin" "$rustc_bin"; do
  [[ -f "$tool" && -x "$tool" && ! -L "$tool" ]] \
    || fail "missing pinned Rust toolchain executable: $tool"
done

git_clean() {
  /usr/bin/git --no-pager --no-replace-objects \
    -c core.fsmonitor=false -c core.commitGraph=false \
    -c core.hooksPath=/dev/null -c core.quotePath=true -c pack.threads=1 \
    -c pack.windowMemory=32m -c pack.packSizeLimit=64m "$@"
}

root="$(git_clean rev-parse --show-toplevel 2>/dev/null)" \
  || fail "not inside a Git worktree"
cd "$root"

assert_absent_even_if_dangling() {
  local path="$1"
  [[ ! -e "$path" && ! -L "$path" ]] \
    || fail "forbidden configuration path: $path"
}

reject_cargo_configs_at_and_above() {
  local dir parent
  dir="$(cd "$1" && pwd -P)" || fail "cannot resolve Cargo search path: $1"
  while :; do
    assert_absent_even_if_dangling "$dir/.cargo/config"
    assert_absent_even_if_dangling "$dir/.cargo/config.toml"
    [[ "$dir" == "/" ]] && break
    parent="${dir%/*}"
    [[ -n "$parent" ]] || parent="/"
    dir="$parent"
  done
}

assert_absent_even_if_dangling "$cargo_home/config"
assert_absent_even_if_dangling "$cargo_home/config.toml"
for shadow in /usr/bin/cargo /usr/bin/rustc /usr/bin/rustfmt \
  /bin/cargo /bin/rustc /bin/rustfmt; do
  assert_absent_even_if_dangling "$shadow"
done
reject_cargo_configs_at_and_above "$root"

root_status="$(git_clean status --porcelain=v1 --untracked-files=all)" \
  || fail "cannot inspect initial worktree or index state"
[[ -z "$root_status" ]] \
  || fail "worktree or index is not clean"
replace_refs="$(git_clean for-each-ref --format='%(refname)' refs/replace)" \
  || fail "cannot inspect replace refs"
[[ -z "$replace_refs" ]] \
  || fail "replace refs are forbidden"
shallow_state="$(git_clean rev-parse --is-shallow-repository)" \
  || fail "cannot inspect shallow repository state"
[[ "$shallow_state" == "false" ]] \
  || fail "shallow history is forbidden"
common_dir="$(git_clean rev-parse --path-format=absolute --git-common-dir)" \
  || fail "cannot resolve Git common directory"
[[ -d "$common_dir" && ! -L "$common_dir" ]] \
  || fail "Git common directory is missing or aliased"
[[ ! -e "$common_dir/info/grafts" && ! -L "$common_dir/info/grafts" ]] \
  || fail "grafts are forbidden"
[[ ! -e "$common_dir/objects/info/alternates" \
  && ! -L "$common_dir/objects/info/alternates" ]] \
  || fail "alternate object stores are forbidden"

head_before="$(git_clean rev-parse HEAD)" || fail "cannot resolve verification HEAD"
baseline_type="$(git_clean cat-file -t "$baseline" 2>/dev/null)" \
  || fail "frozen S14 baseline is unavailable"
[[ "$baseline_type" == "commit" ]] \
  || fail "frozen S14 baseline is unavailable"
actual_baseline_tree="$(git_clean show -s --format='%T' "$baseline")" \
  || fail "cannot inspect frozen S14 baseline tree"
[[ "$actual_baseline_tree" == "$baseline_tree" ]] \
  || fail "frozen S14 baseline tree drift"
actual_baseline_parents="$(git_clean show -s --format='%P' "$baseline")" \
  || fail "cannot inspect frozen S14 baseline topology"
[[ "$actual_baseline_parents" == "$baseline_parents" ]] \
  || fail "frozen S14 baseline parent topology drift"
git_clean merge-base --is-ancestor "$baseline" "$head_before" \
  || fail "frozen S14 baseline is not an ancestor of HEAD"

tmp="$(/usr/bin/mktemp -d)" || fail "cannot allocate private verification directory"
/usr/bin/chmod 700 "$tmp"
cleanup() {
  /usr/bin/rm -rf "$tmp"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
/usr/bin/mkdir -m 700 \
  "$tmp/home" "$tmp/cargo-tmp" \
  "$tmp/s13-home" "$tmp/s13-tmp" \
  "$tmp/checker-home-1" "$tmp/checker-tmp-1" \
  "$tmp/checker-home-2" "$tmp/checker-tmp-2" \
  "$tmp/glue-home" "$tmp/glue-tmp"

[[ "${#source_paths[@]}" == "11" \
  && "${#glue_paths[@]}" == "3" \
  && "${#packet_paths[@]}" == "8" ]] \
  || fail "S14 source/glue/packet catalog cardinality drift"
printf '%s\n' "${source_paths[@]}" | /usr/bin/sort >"$tmp/expected-paths"
for path in "${packet_paths[@]}"; do
  packet_entry="$(git_clean ls-tree "$baseline" -- "$path")" \
    || fail "cannot inspect frozen baseline packet path: $path"
  [[ -z "$packet_entry" ]] \
    || fail "S14 packet path already exists at the frozen baseline: $path"
done

expected_mode_for() {
  local path="$1"
  if [[ "$path" == "scripts/check-memory-temporal-recovered-envelope-source-s14.sh" ]]; then
    printf '100755\n'
  else
    printf '100644\n'
  fi
}

source_shape_is_valid() {
  local commit="$1" object_type parent_line path entry mode type expected_mode
  object_type="$(git_clean cat-file -t "$commit" 2>/dev/null)" || return 1
  [[ "$object_type" == "commit" ]] || return 1
  parent_line="$(git_clean show -s --format='%P' "$commit")" || return 1
  [[ "$parent_line" == "$baseline" ]] || return 1
  if ! git_clean diff --no-renames --no-ext-diff --no-textconv \
    --name-only "$baseline" "$commit" \
    | /usr/bin/sort >"$tmp/candidate-paths"; then
    return 1
  fi
  /usr/bin/cmp -s "$tmp/expected-paths" "$tmp/candidate-paths" || return 1
  while IFS= read -r path; do
    entry="$(git_clean ls-tree "$commit" -- "$path")" || return 1
    [[ -n "$entry" ]] || return 1
    mode="$(/usr/bin/awk '{print $1}' <<<"$entry")" || return 1
    type="$(/usr/bin/awk '{print $2}' <<<"$entry")" || return 1
    expected_mode="$(expected_mode_for "$path")" || return 1
    [[ "$mode" == "$expected_mode" && "$type" == "blob" ]] \
      || return 1
  done <"$tmp/expected-paths"
}

integration_preserves_source() {
  local integration="$1" source="$2" path integration_blob source_blob
  while IFS= read -r path; do
    integration_blob="$(git_clean rev-parse "$integration:$path" 2>/dev/null)" \
      || return 1
    source_blob="$(git_clean rev-parse "$source:$path" 2>/dev/null)" \
      || return 1
    [[ "$integration_blob" == "$source_blob" ]] || return 1
  done <"$tmp/expected-paths"
}

integration_shape_is_valid() {
  local integration="$1" first_parent="$2" path packet_entry
  if ! git_clean diff --no-renames --no-ext-diff --no-textconv \
    --name-only "$first_parent" "$integration" \
    | /usr/bin/sort >"$tmp/integration-paths"; then
    return 1
  fi
  while IFS= read -r path; do
    /usr/bin/grep -Fx -- "$path" "$tmp/expected-paths" >/dev/null \
      || return 1
  done <"$tmp/integration-paths"
  for path in "${packet_paths[@]}"; do
    packet_entry="$(git_clean ls-tree "$first_parent" -- "$path")" || return 1
    [[ -z "$packet_entry" ]] || return 1
  done
}

source_commit=""
integration_commit=""
mode=""
if source_shape_is_valid "$head_before"; then
  source_commit="$head_before"
  mode="source"
else
  candidates=()
  candidate_history="$tmp/s14-first-parent-merges.txt"
  git_clean rev-list --first-parent --merges \
    "$baseline..$head_before" >"$candidate_history" \
    || fail "cannot enumerate S14 integration candidates"
  while IFS= read -r candidate; do
    candidate_parent_line="$(git_clean show -s --format='%P' "$candidate")" \
      || fail "cannot inspect S14 integration candidate: $candidate"
    read -r -a parents <<<"$candidate_parent_line"
    [[ "${#parents[@]}" == "2" ]] || continue
    first_parent="${parents[0]}"
    possible_source="${parents[1]}"
    source_shape_is_valid "$possible_source" || continue
    if git_clean merge-base --is-ancestor "$baseline" "$first_parent"; then
      :
    else
      ancestor_status="$?"
      [[ "$ancestor_status" == "1" ]] && continue
      fail "cannot verify baseline ancestry for S14 candidate: $candidate"
    fi
    if git_clean merge-base --is-ancestor "$possible_source" "$first_parent"; then
      continue
    else
      ancestor_status="$?"
      [[ "$ancestor_status" == "1" ]] \
        || fail "cannot verify source ancestry for S14 candidate: $candidate"
    fi
    integration_shape_is_valid "$candidate" "$first_parent" || continue
    integration_preserves_source "$candidate" "$possible_source" || continue
    candidates+=("$candidate $possible_source")
  done <"$candidate_history"
  [[ "${#candidates[@]}" == "1" ]] \
    || fail "HEAD must contain exactly one source-bound ordinary S14 integration"
  read -r integration_commit source_commit <<<"${candidates[0]}"
  if [[ "$head_before" == "$integration_commit" ]]; then
    mode="integrated"
  else
    mode="historical-descendant"
  fi
fi

git_clean merge-base --is-ancestor "$source_commit" "$head_before" \
  || fail "S14 source is not an ancestor of HEAD"

verify_blob() {
  local ref="$1" path="$2" expected_mode entry mode type
  expected_mode="$(expected_mode_for "$path")" \
    || fail "cannot resolve protected path mode: $path"
  entry="$(git_clean ls-tree "$ref" -- "$path")" \
    || fail "cannot inspect protected path at $ref: $path"
  [[ -n "$entry" ]] || fail "missing protected path at $ref: $path"
  mode="$(/usr/bin/awk '{print $1}' <<<"$entry")" \
    || fail "cannot parse protected path mode at $ref: $path"
  type="$(/usr/bin/awk '{print $2}' <<<"$entry")" \
    || fail "cannot parse protected path type at $ref: $path"
  [[ "$mode" == "$expected_mode" && "$type" == "blob" ]] \
    || fail "protected path mode or object type drift at $ref: $path"
}

while IFS= read -r path; do
  verify_blob "$source_commit" "$path"
  if [[ "$mode" == "source" ]]; then
    continue
  fi
  verify_blob "$integration_commit" "$path"
  source_blob="$(git_clean rev-parse "$source_commit:$path")" \
    || fail "cannot resolve protected source blob: $path"
  integration_blob="$(git_clean rev-parse "$integration_commit:$path")" \
    || fail "cannot resolve protected integration blob: $path"
  [[ "$source_blob" == "$integration_blob" ]] \
    || fail "S14 integration changed source blob: $path"
done <"$tmp/expected-paths"

if [[ "$mode" == "integrated" ]]; then
  while IFS= read -r path; do
    source_blob="$(git_clean rev-parse "$source_commit:$path")" \
      || fail "cannot resolve integrated source blob: $path"
    head_blob="$(git_clean rev-parse "$head_before:$path")" \
      || fail "cannot resolve integrated HEAD blob: $path"
    [[ "$source_blob" == "$head_blob" ]] \
      || fail "integrated HEAD changed S14 source blob: $path"
  done <"$tmp/expected-paths"
elif [[ "$mode" == "historical-descendant" ]]; then
  for path in "${packet_paths[@]}"; do
    verify_blob "$head_before" "$path"
    source_blob="$(git_clean rev-parse "$source_commit:$path")" \
      || fail "cannot resolve historical source packet: $path"
    head_blob="$(git_clean rev-parse "$head_before:$path")" \
      || fail "cannot resolve historical HEAD packet: $path"
    [[ "$source_blob" == "$head_blob" ]] \
      || fail "historical descendant changed frozen S14 packet: $path"
  done
  for path in "${glue_paths[@]}"; do
    verify_blob "$head_before" "$path"
  done
  descendant_history="$tmp/s14-historical-first-parent-commits.txt"
  git_clean rev-list --first-parent \
    "$integration_commit..$head_before" >"$descendant_history" \
    || fail "cannot enumerate the S14 historical-descendant trajectory"
  while IFS= read -r descendant; do
    git_clean diff --quiet --no-renames --no-ext-diff --no-textconv \
      "$descendant^1" "$descendant" -- "${packet_paths[@]}" \
      || fail "historical descendant modified an immutable S14 packet: $descendant"
  done <"$descendant_history"
fi

verify_archive_tree_safety() {
  local archive="$1" symlink_hit hardlink_hit
  symlink_hit="$(/usr/bin/find "$archive" -type l -print -quit)" \
    || fail "cannot inspect S14 source archive for symlinks: $archive"
  [[ -z "$symlink_hit" ]] \
    || fail "S14 source archive contains a symlink: $archive"
  hardlink_hit="$(/usr/bin/find "$archive" -type f -links +1 -print -quit)" \
    || fail "cannot inspect S14 source archive for hard links: $archive"
  [[ -z "$hardlink_hit" ]] \
    || fail "S14 source archive contains a hard-linked file: $archive"
}

materialize_source_archive() {
  local archive="$1"
  /usr/bin/mkdir -m 700 "$archive"
  git_clean archive "$source_commit" \
    | /usr/bin/env -i PATH=/usr/bin:/bin \
      /usr/bin/tar -xf - -C "$archive" \
    || fail "cannot independently materialize S14 source archive: $archive"
  verify_archive_tree_safety "$archive"
}

protected_archive_manifest() {
  local archive="$1" path mode digest
  verify_archive_tree_safety "$archive"
  while IFS= read -r path; do
    [[ -f "$archive/$path" && ! -L "$archive/$path" ]] \
      || fail "protected S14 archive path is not a regular file: $path"
    mode="$(/usr/bin/stat -c '%a' -- "$archive/$path")" \
      || fail "cannot inspect protected S14 archive mode: $path"
    digest="$(/usr/bin/sha256sum "$archive/$path" \
      | /usr/bin/awk '{print $1}')" \
      || fail "cannot hash protected S14 archive path: $path"
    printf '%s\t%s\t%s\n' "$mode" "$digest" "$path"
  done <"$tmp/expected-paths"
}

source_blob_digest() {
  local path="$1"
  git_clean cat-file blob "$source_commit:$path" \
    | /usr/bin/sha256sum | /usr/bin/awk '{print $1}'
}

trusted_expected="$tmp/trusted-expected.tsv"
trusted_report="$tmp/trusted-report.md"
git_clean cat-file blob "$source_commit:$expected" >"$trusted_expected" \
  || fail "cannot materialize trusted S14 expected receipt"
git_clean cat-file blob "$source_commit:$report" >"$trusted_report" \
  || fail "cannot materialize trusted S14 report"
/usr/bin/chmod 400 "$trusted_expected" "$trusted_report"
trusted_expected_digest="$(/usr/bin/sha256sum "$trusted_expected" \
  | /usr/bin/awk '{print $1}')" \
  || fail "cannot hash trusted S14 expected receipt"
trusted_report_digest="$(/usr/bin/sha256sum "$trusted_report" \
  | /usr/bin/awk '{print $1}')" \
  || fail "cannot hash trusted S14 report"

if [[ "$mode" == "historical-descendant" ]]; then
  glue_archive="$tmp/glue-source-archive"
  materialize_source_archive "$glue_archive"
  protected_archive_manifest "$glue_archive" >"$tmp/glue-manifest-before.tsv"
  printf 'glue_check\tPASS\n' >"$tmp/expected-glue-check.tsv"
  /usr/bin/env -i \
    PATH=/usr/bin:/bin HOME="$tmp/glue-home" TMPDIR="$tmp/glue-tmp" \
    LANG=C.UTF-8 LC_ALL=C.UTF-8 PYTHONDONTWRITEBYTECODE=1 PYTHONHASHSEED=0 \
    /usr/bin/python3 -S -P "$glue_archive/$checker" \
      --repo "$root" --glue-only >"$tmp/glue-check.tsv" \
    || fail "S14 historical descendant glue check failed"
  protected_archive_manifest "$glue_archive" >"$tmp/glue-manifest-after.tsv"
  /usr/bin/cmp "$tmp/glue-manifest-before.tsv" "$tmp/glue-manifest-after.tsv" \
    || fail "S14 historical glue checker modified its source archive"
  /usr/bin/diff -u "$tmp/expected-glue-check.tsv" "$tmp/glue-check.tsv" \
    || fail "S14 historical descendant glue receipt drift"
fi

for pass in 1 2; do
  archive="$tmp/source-archive-$pass"
  materialize_source_archive "$archive"
  protected_archive_manifest "$archive" >"$tmp/archive-manifest-$pass-before.tsv"
  /usr/bin/env -i \
    PATH=/usr/bin:/bin HOME="$tmp/checker-home-$pass" \
    TMPDIR="$tmp/checker-tmp-$pass" LANG=C.UTF-8 LC_ALL=C.UTF-8 \
    PYTHONDONTWRITEBYTECODE=1 PYTHONHASHSEED=0 \
    /usr/bin/python3 -S -P "$archive/$checker" --repo "$archive" \
    >"$tmp/s14-receipt-$pass.tsv" \
    || fail "S14 independent checker pass $pass failed"
  protected_archive_manifest "$archive" >"$tmp/archive-manifest-$pass-after.tsv"
  /usr/bin/cmp "$tmp/archive-manifest-$pass-before.tsv" \
    "$tmp/archive-manifest-$pass-after.tsv" \
    || fail "S14 checker pass $pass modified its source archive"
  /usr/bin/diff -u "$trusted_expected" "$tmp/s14-receipt-$pass.tsv" \
    || fail "S14 independent checker pass $pass drift"
done
/usr/bin/cmp "$tmp/s14-receipt-1.tsv" "$tmp/s14-receipt-2.tsv" \
  || fail "S14 independent checker output is nondeterministic"
actual_expected_digest="$(/usr/bin/sha256sum "$trusted_expected" \
  | /usr/bin/awk '{print $1}')" \
  || fail "cannot re-hash trusted S14 expected receipt"
[[ "$actual_expected_digest" == "$trusted_expected_digest" ]] \
  || fail "trusted S14 expected receipt changed during checker execution"
actual_report_digest="$(/usr/bin/sha256sum "$trusted_report" \
  | /usr/bin/awk '{print $1}')" \
  || fail "cannot re-hash trusted S14 report"
[[ "$actual_report_digest" == "$trusted_report_digest" ]] \
  || fail "trusted S14 report changed during checker execution"

while IFS= read -r path; do
  [[ "$path" == "$report" ]] && continue
  digest="$(source_blob_digest "$path")" \
    || fail "cannot hash protected source blob: $path"
  /usr/bin/grep -Fx -- "- \`$path\`: \`$digest\`" "$trusted_report" >/dev/null \
    || fail "S14 report does not bind $path at $digest"
done <"$tmp/expected-paths"

git_clean diff --no-renames --no-ext-diff --no-textconv \
  --check "$baseline" "$source_commit"
if [[ "$mode" == "historical-descendant" ]]; then
  git_clean diff --no-renames --no-ext-diff --no-textconv \
    --check "$integration_commit" "$head_before"
fi

s13_repo="$tmp/s13-replay-repo"
git_clean clone --no-local --no-hardlinks --no-checkout --no-tags \
  "$root" "$s13_repo" >/dev/null 2>&1 \
  || fail "cannot create independent S13 replay repository"
[[ ! -e "$s13_repo/.git/objects/info/alternates" \
  && ! -L "$s13_repo/.git/objects/info/alternates" ]] \
  || fail "independent S13 replay repository uses object alternates"
git_clean -C "$s13_repo" checkout --detach "$s13_integration" >/dev/null 2>&1 \
  || fail "cannot check out frozen S13 integration"
s13_actual_parents="$(git_clean -C "$s13_repo" show -s --format='%P' HEAD)" \
  || fail "cannot inspect independent S13 replay topology"
[[ "$s13_actual_parents" \
  == "0be03cfdbee77f0bc29559e0795fa3ec77f07357 $s13_source" ]] \
  || fail "independent S13 replay topology drift"
for ref in "$s13_baseline" "$s13_integration"; do
  for config_path in .cargo/config .cargo/config.toml; do
    config_entry="$(git_clean -C "$s13_repo" \
      ls-tree "$ref" -- "$config_path")" \
      || fail "cannot inspect predecessor Cargo config: $ref:$config_path"
    [[ -z "$config_entry" ]] \
      || fail "frozen predecessor contains forbidden Cargo config: $ref:$config_path"
  done
done
assert_absent_even_if_dangling "$cargo_home/config"
assert_absent_even_if_dangling "$cargo_home/config.toml"
reject_cargo_configs_at_and_above "$s13_repo"

# The frozen S12 gate contains one historical env-i replay that intentionally
# derives CARGO_HOME from HOME.  Immediately before that replay, give it only
# the already-validated offline registry cache while keeping its HOME and
# top-level writable Cargo state private to this gate.
/usr/bin/mkdir -m 700 "$tmp/s13-home/.cargo" \
  || fail "cannot create private Cargo home for frozen replay"
[[ -d "$cargo_home" && ! -L "$cargo_home" ]] \
  || fail "trusted Cargo home is missing or aliased"
assert_absent_even_if_dangling "$cargo_home/config"
assert_absent_even_if_dangling "$cargo_home/config.toml"
declare -A frozen_cache_target_identity=()
declare -A frozen_cache_link_identity=()
for cache_dir in registry; do
  [[ -d "$cargo_home/$cache_dir" && ! -L "$cargo_home/$cache_dir" ]] \
    || fail "trusted Cargo $cache_dir cache is missing or aliased"
  assert_absent_even_if_dangling "$tmp/s13-home/.cargo/$cache_dir"
  /usr/bin/ln -s -- "$cargo_home/$cache_dir" \
    "$tmp/s13-home/.cargo/$cache_dir" \
    || fail "cannot expose trusted Cargo $cache_dir cache to frozen replay"
  frozen_cache_target_identity["$cache_dir"]="$(
    /usr/bin/stat -Lc '%d:%i' -- "$cargo_home/$cache_dir"
  )" || fail "cannot record trusted Cargo $cache_dir cache identity"
  frozen_cache_link_identity["$cache_dir"]="$(
    /usr/bin/stat -c '%d:%i' -- "$tmp/s13-home/.cargo/$cache_dir"
  )" || fail "cannot record frozen replay Cargo $cache_dir link identity"
done

verify_frozen_replay_cache_links() {
  local cache_dir cache_link cache_target target_identity
  local followed_link_identity link_identity
  [[ -d "$cargo_home" && ! -L "$cargo_home" ]] \
    || fail "trusted Cargo home changed or became aliased"
  assert_absent_even_if_dangling "$cargo_home/config"
  assert_absent_even_if_dangling "$cargo_home/config.toml"
  for cache_dir in registry; do
    cache_link="$tmp/s13-home/.cargo/$cache_dir"
    [[ -L "$cache_link" && -d "$cache_link" ]] \
      || fail "frozen replay Cargo $cache_dir cache link drift"
    cache_target="$(/usr/bin/readlink -- "$cache_link")" \
      || fail "cannot inspect frozen replay Cargo $cache_dir cache link"
    [[ "$cache_target" == "$cargo_home/$cache_dir" ]] \
      || fail "frozen replay Cargo $cache_dir cache target drift"
    [[ -d "$cargo_home/$cache_dir" && ! -L "$cargo_home/$cache_dir" ]] \
      || fail "trusted Cargo $cache_dir cache changed or became aliased"
    target_identity="$(
      /usr/bin/stat -Lc '%d:%i' -- "$cargo_home/$cache_dir"
    )" || fail "cannot recheck trusted Cargo $cache_dir cache identity"
    followed_link_identity="$(
      /usr/bin/stat -Lc '%d:%i' -- "$cache_link"
    )" || fail "cannot recheck frozen replay Cargo $cache_dir target identity"
    link_identity="$(
      /usr/bin/stat -c '%d:%i' -- "$cache_link"
    )" || fail "cannot recheck frozen replay Cargo $cache_dir link identity"
    [[ "$target_identity" == "${frozen_cache_target_identity[$cache_dir]}" \
      && "$followed_link_identity" == "${frozen_cache_target_identity[$cache_dir]}" \
      && "$link_identity" == "${frozen_cache_link_identity[$cache_dir]}" ]] \
      || fail "frozen replay Cargo $cache_dir identity drift"
  done
  assert_absent_even_if_dangling "$tmp/s13-home/.cargo/config"
  assert_absent_even_if_dangling "$tmp/s13-home/.cargo/config.toml"
}
verify_frozen_replay_cache_links
if ! (
  cd "$s13_repo" || fail "cannot enter independent S13 replay repository"
  /usr/bin/env -i \
    PATH="$trusted_cargo_path" HOME="$tmp/s13-home" TMPDIR="$tmp/s13-tmp" \
    LANG=C.UTF-8 LC_ALL=C.UTF-8 PYTHONDONTWRITEBYTECODE=1 PYTHONHASHSEED=0 \
    RUSTUP_HOME="$rustup_home" CARGO_HOME="$cargo_home" \
    RUSTC="$rustc_bin" \
    GIT_CONFIG_NOSYSTEM=1 GIT_CONFIG_GLOBAL=/dev/null \
    GIT_CONFIG_SYSTEM=/dev/null \
    CARGO_BUILD_JOBS=1 CARGO_INCREMENTAL=0 RUSTFLAGS="-C debuginfo=0" \
    /usr/bin/bash "$s13_gate"
) >"$tmp/s13-replay.log" 2>&1; then
  verify_frozen_replay_cache_links
  /usr/bin/tail -n 80 "$tmp/s13-replay.log" >&2 || true
  fail "frozen S13 integration gate replay failed"
fi
verify_frozen_replay_cache_links
/usr/bin/grep -Fx $'integration_gate\tVALID_INTEGRATED_BIOCORTEX_AB_TRACK_B_RECOVERED_ENVELOPE_DELIVERY_S13' \
  "$tmp/s13-replay.log" >/dev/null \
  || fail "frozen S13 replay did not emit its integrated marker"
/usr/bin/grep -Fx $'s12_baseline_gate\tPASS' "$tmp/s13-replay.log" >/dev/null \
  || fail "frozen S13 replay did not preserve the S12 baseline gate"
/usr/bin/grep -Fx $'gate\tPASS' "$tmp/s13-replay.log" >/dev/null \
  || fail "frozen S13 replay did not emit PASS"
/usr/bin/grep -Fx $'mode\tintegrated' "$tmp/s13-replay.log" >/dev/null \
  || fail "frozen S13 replay did not run in integrated mode"
/usr/bin/grep -Fx $'baseline\t'"$s13_baseline" "$tmp/s13-replay.log" >/dev/null \
  || fail "frozen S13 replay baseline drift"
/usr/bin/grep -Fx $'source_commit\t'"$s13_source" "$tmp/s13-replay.log" >/dev/null \
  || fail "frozen S13 replay source drift"
/usr/bin/grep -Fx $'integration_commit\t'"$s13_integration" "$tmp/s13-replay.log" >/dev/null \
  || fail "frozen S13 replay integration drift"
/usr/bin/grep -Fx $'head\t'"$s13_integration" "$tmp/s13-replay.log" >/dev/null \
  || fail "frozen S13 replay HEAD drift"

build_repo="$tmp/s14-build-repo"
git_clean clone --no-local --no-hardlinks --no-checkout --no-tags \
  "$root" "$build_repo" >/dev/null 2>&1 \
  || fail "cannot create independent S14 build repository"
[[ ! -e "$build_repo/.git/objects/info/alternates" \
  && ! -L "$build_repo/.git/objects/info/alternates" ]] \
  || fail "independent S14 build repository uses object alternates"
git_clean -C "$build_repo" checkout --detach "$head_before" >/dev/null 2>&1 \
  || fail "cannot check out exact S14 verification HEAD"
build_head="$(git_clean -C "$build_repo" rev-parse HEAD)" \
  || fail "cannot resolve independent S14 build HEAD"
[[ "$build_head" == "$head_before" ]] \
  || fail "independent S14 build repository HEAD drift"
build_status="$(git_clean -C "$build_repo" status \
  --porcelain=v1 --untracked-files=all)" \
  || fail "cannot inspect independent S14 build repository state"
[[ -z "$build_status" ]] \
  || fail "independent S14 build repository is not clean"
assert_absent_even_if_dangling "$cargo_home/config"
assert_absent_even_if_dangling "$cargo_home/config.toml"
reject_cargo_configs_at_and_above "$root"
reject_cargo_configs_at_and_above "$build_repo"
reject_cargo_configs_at_and_above "$s13_repo"

run_in_build_env() {
  assert_absent_even_if_dangling "$cargo_home/config"
  assert_absent_even_if_dangling "$cargo_home/config.toml"
  reject_cargo_configs_at_and_above "$build_repo"
  (
    cd "$build_repo" || fail "cannot enter independent S14 build repository"
    /usr/bin/env -i \
      PATH="$trusted_cargo_path" HOME="$tmp/home" TMPDIR="$tmp/cargo-tmp" \
      LANG=C.UTF-8 LC_ALL=C.UTF-8 RUSTUP_HOME="$rustup_home" \
      CARGO_HOME="$cargo_home" CARGO_TARGET_DIR="$tmp/cargo-target" \
      CARGO_BUILD_JOBS=1 CARGO_INCREMENTAL=0 CARGO_NET_OFFLINE=true \
      CARGO_TERM_COLOR=never RUSTC="$rustc_bin" RUSTFLAGS="-C debuginfo=0" \
      GIT_CONFIG_NOSYSTEM=1 GIT_CONFIG_GLOBAL=/dev/null \
      GIT_CONFIG_SYSTEM=/dev/null \
      "$@"
  )
}

run_in_build_env "$rustfmt_bin" --edition 2021 --check \
  crates/store/src/temporal_replay_transport/external_operation_recovery.rs \
  crates/store/src/temporal_replay_transport/recovered_s9_decision_reverification/recovered_envelope_delivery.rs \
  crates/store/src/temporal_replay_transport/recovered_s9_decision_reverification/recovered_envelope_delivery/recovered_envelope_source.rs

run_and_require_count() {
  local label="$1"
  local expected_count="$2"
  shift 2
  "$@" 2>&1 | /usr/bin/tee "$tmp/$label.log"
  /usr/bin/grep -F \
    "test result: ok. $expected_count passed; 0 failed" \
    "$tmp/$label.log" >/dev/null \
    || fail "$label did not report $expected_count passing tests"
}

run_and_require_count s14-tests 24 \
  run_in_build_env "$cargo_bin" test --locked --offline \
    -p ab-store --no-default-features \
    --features "$feature" -j1 \
    'recovered_envelope_source::tests::s14_' -- --test-threads=1
run_and_require_count s13-regressions 15 \
  run_in_build_env "$cargo_bin" test --locked --offline \
    -p ab-store --no-default-features \
    --features "$feature" -j1 \
    'recovered_envelope_delivery::tests::s13_' -- --test-threads=1
run_and_require_count s12-regressions 32 \
  run_in_build_env "$cargo_bin" test --locked --offline \
    -p ab-store --no-default-features \
    --features "$feature" -j1 \
    'recovered_s9_decision_reverification::tests::s12_' -- --test-threads=1
run_and_require_count s11-regressions 30 \
  run_in_build_env "$cargo_bin" test --locked --offline \
    -p ab-store --no-default-features \
    --features "$feature" -j1 \
    'external_authority_operation_state_machine::tests::s11_' -- --test-threads=1
run_and_require_count s10-regressions 15 \
  run_in_build_env "$cargo_bin" test --locked --offline \
    -p ab-store --no-default-features \
    --features "$feature" -j1 \
    'external_operation_recovery::tests::s10_' -- --test-threads=1
run_and_require_count s9-regressions 15 \
  run_in_build_env "$cargo_bin" test --locked --offline \
    -p ab-store --no-default-features \
    --features "$feature" -j1 \
    'external_restore_authority::tests::s9_' -- --test-threads=1

run_in_build_env "$cargo_bin" check --locked --offline \
  -p ab-store --no-default-features --features "$feature" -j1
run_in_build_env "$cargo_bin" check --locked --offline \
  -p ab-store --no-default-features -j1
run_in_build_env "$cargo_bin" check --locked --offline \
  -p ab-bridge --no-default-features -j1

final_root_head="$(git_clean rev-parse HEAD)" \
  || fail "cannot resolve final verification HEAD"
[[ "$final_root_head" == "$head_before" ]] \
  || fail "HEAD changed during verification"
final_root_status="$(git_clean status --porcelain=v1 --untracked-files=all)" \
  || fail "cannot inspect final worktree or index state"
[[ -z "$final_root_status" ]] \
  || fail "verification dirtied worktree or index"
final_build_head="$(git_clean -C "$build_repo" rev-parse HEAD)" \
  || fail "cannot resolve final independent S14 build HEAD"
[[ "$final_build_head" == "$head_before" ]] \
  || fail "independent S14 build HEAD changed during verification"
final_build_status="$(git_clean -C "$build_repo" status \
  --porcelain=v1 --untracked-files=all)" \
  || fail "cannot inspect final independent S14 build state"
[[ -z "$final_build_status" ]] \
  || fail "verification dirtied independent S14 build repository"
final_s13_head="$(git_clean -C "$s13_repo" rev-parse HEAD)" \
  || fail "cannot resolve final independent S13 replay HEAD"
[[ "$final_s13_head" == "$s13_integration" ]] \
  || fail "independent S13 replay HEAD changed during verification"
final_s13_status="$(git_clean -C "$s13_repo" status \
  --porcelain=v1 --untracked-files=all)" \
  || fail "cannot inspect final independent S13 replay state"
[[ -z "$final_s13_status" ]] \
  || fail "verification dirtied independent S13 replay repository"
assert_absent_even_if_dangling "$cargo_home/config"
assert_absent_even_if_dangling "$cargo_home/config.toml"
reject_cargo_configs_at_and_above "$root"
reject_cargo_configs_at_and_above "$build_repo"
reject_cargo_configs_at_and_above "$s13_repo"

/usr/bin/cat "$tmp/s14-receipt-1.tsv"
case "$mode" in
  source)
    printf 'source_gate\tVALID_SOURCE_BIOCORTEX_AB_TRACK_B_RECOVERED_ENVELOPE_SOURCE_S14\n'
    ;;
  integrated)
    printf 'integration_gate\tVALID_INTEGRATED_BIOCORTEX_AB_TRACK_B_RECOVERED_ENVELOPE_SOURCE_S14\n'
    ;;
  historical-descendant)
    printf 'historical_descendant_gate\tVALID_HISTORICAL_DESCENDANT_BIOCORTEX_AB_TRACK_B_RECOVERED_ENVELOPE_SOURCE_S14\n'
    ;;
esac
printf 's13_baseline_gate\tPASS\n'
printf 'gate\tPASS\n'
printf 'mode\t%s\n' "$mode"
printf 'baseline\t%s\n' "$baseline"
printf 'source_commit\t%s\n' "$source_commit"
[[ -z "$integration_commit" ]] || printf 'integration_commit\t%s\n' "$integration_commit"
printf 'head\t%s\n' "$head_before"
