#!/usr/bin/bash
set -euo pipefail
umask 077

baseline="b15a48d17fb30b0990bf26210978f2a4f78f54cc"
baseline_tree="bc960015b06236c5f52c90dbbd9da4664c464b3e"
baseline_parents="b2dd4706bd34155a1edd6d6472ee0b32a3bb232b 27fd73aa36ac897fb817398eca3a191181d8fb5d"
feature="temporal-evidence-s15-recovered-envelope-bounded-runtime-adapter-synthetic"
checker="scripts/eval/check_memory_temporal_recovered_envelope_bounded_runtime_adapter_s15.py"
expected="scripts/eval/fixtures/memory_temporal_recovered_envelope_bounded_runtime_adapter_s15.expected.v0.tsv"
report="docs/reports/goal-c-u/2026-07-15-biocortex-ab-track-b-recovered-envelope-bounded-runtime-adapter-s15.md"
s14_integration="b2dd4706bd34155a1edd6d6472ee0b32a3bb232b"
s14_tree="56121b68928631480bf377193cbbe63933615f72"
s14_parents="b9988aa5772928fb964c8d47b4f294a69f5122ac cc8143e5ef2cc8cf00da0627f7321f714369ebb9"
s14_gate="scripts/check-memory-temporal-recovered-envelope-source-s14.sh"
s14_gate_sha256="095ae3b50ed8f10d55d20d98041aabafddef362af67b734c83c69436e98cce7e"

trusted_path="/usr/bin:/bin"
rustup_home="/home/pallasting/.rustup"
cargo_home="/home/pallasting/.cargo"
toolchain_bin="$rustup_home/toolchains/stable-x86_64-unknown-linux-gnu/bin"
trusted_cargo_path="/usr/bin:/bin:$toolchain_bin"
cargo_bin="$toolchain_bin/cargo"
rustfmt_bin="$toolchain_bin/rustfmt"
rustc_bin="$toolchain_bin/rustc"
awk_bin="/usr/bin/mawk"
cp_bin="/usr/bin/gnucp"
env_bin="/usr/lib/cargo/bin/coreutils/env"
head_bin="/usr/lib/cargo/bin/coreutils/head"
id_bin="/usr/lib/cargo/bin/coreutils/id"
mkdir_bin="/usr/lib/cargo/bin/coreutils/mkdir"
mktemp_bin="/usr/lib/cargo/bin/coreutils/mktemp"
python_bin="/usr/bin/python3.14"
rm_bin="/usr/bin/gnurm"
sha256sum_bin="/usr/lib/cargo/bin/coreutils/sha256sum"
sort_bin="/usr/lib/cargo/bin/coreutils/sort"
stat_bin="/usr/lib/cargo/bin/coreutils/stat"
tail_bin="/usr/lib/cargo/bin/coreutils/tail"
tee_bin="/usr/lib/cargo/bin/coreutils/tee"
PATH="$trusted_path"
export PATH LANG=C.UTF-8 LC_ALL=C.UTF-8
export PYTHONDONTWRITEBYTECODE=1 PYTHONHASHSEED=0

unset BASH_ENV ENV CDPATH PERL5OPT PERL5LIB PERL_UNICODE TAR_OPTIONS
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
export GIT_CONFIG_NOSYSTEM=1 GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_SYSTEM=/dev/null

source_paths=(
  "crates/store/Cargo.toml"
  "crates/store/src/temporal_replay_transport/recovered_s9_decision_reverification/recovered_envelope_delivery/recovered_envelope_source.rs"
  "crates/store/src/temporal_replay_transport/recovered_s9_decision_reverification/recovered_envelope_delivery/recovered_envelope_source/bounded_runtime_adapter.rs"
  "docs/design/MEMORY_TEMPORAL_RECOVERED_ENVELOPE_BOUNDED_RUNTIME_ADAPTER_S15_2026_07_15.md"
  "docs/design/fixtures/biocortex-ab-track-b-recovered-envelope-bounded-runtime-adapter-s15-v0.json"
  "docs/design/fixtures/biocortex-ab-track-b-successor-admission-gate-s15-v0.json"
  "$report"
  "scripts/check-memory-temporal-recovered-envelope-bounded-runtime-adapter-s15.sh"
  "$checker"
  "$expected"
)
glue_paths=(
  "crates/store/Cargo.toml"
  "crates/store/src/temporal_replay_transport/recovered_s9_decision_reverification/recovered_envelope_delivery/recovered_envelope_source.rs"
)
packet_paths=(
  "crates/store/src/temporal_replay_transport/recovered_s9_decision_reverification/recovered_envelope_delivery/recovered_envelope_source/bounded_runtime_adapter.rs"
  "docs/design/MEMORY_TEMPORAL_RECOVERED_ENVELOPE_BOUNDED_RUNTIME_ADAPTER_S15_2026_07_15.md"
  "docs/design/fixtures/biocortex-ab-track-b-recovered-envelope-bounded-runtime-adapter-s15-v0.json"
  "docs/design/fixtures/biocortex-ab-track-b-successor-admission-gate-s15-v0.json"
  "$report"
  "scripts/check-memory-temporal-recovered-envelope-bounded-runtime-adapter-s15.sh"
  "$checker"
  "$expected"
)

fail() {
  printf 'S15_GATE_FAILED\t%s\n' "$*" >&2
  exit 1
}

for tool in "$awk_bin" /usr/bin/bash /usr/bin/cmp "$cp_bin" \
  /usr/bin/diff "$env_bin" /usr/bin/find /usr/bin/git /usr/bin/grep \
  "$head_bin" "$id_bin" "$mkdir_bin" "$mktemp_bin" "$python_bin" \
  "$rm_bin" "$sha256sum_bin" "$sort_bin" "$stat_bin" "$tail_bin" \
  "$tee_bin"; do
  [[ -f "$tool" && -x "$tool" && ! -L "$tool" ]] \
    || fail "missing or aliased trusted executable: $tool"
done
for tool in "$cargo_bin" "$rustfmt_bin" "$rustc_bin"; do
  [[ -f "$tool" && -x "$tool" && ! -L "$tool" ]] \
    || fail "missing pinned Rust toolchain executable: $tool"
done

git_clean() {
  /usr/bin/git --no-pager --no-replace-objects \
    -c core.fsmonitor=false -c core.commitGraph=false \
    -c core.hooksPath=/dev/null -c core.quotePath=true \
    -c pack.threads=1 -c pack.windowMemory=32m -c pack.packSizeLimit=64m "$@"
}

reject_cargo_configs_at_and_above() {
  local dir parent
  dir="$(cd "$1" && pwd -P)" || fail "cannot resolve Cargo search path: $1"
  while :; do
    [[ ! -e "$dir/.cargo/config" && ! -L "$dir/.cargo/config" \
      && ! -e "$dir/.cargo/config.toml" && ! -L "$dir/.cargo/config.toml" ]] \
      || fail "forbidden Cargo configuration at: $dir"
    [[ "$dir" == "/" ]] && break
    parent="${dir%/*}"
    [[ -n "$parent" ]] || parent="/"
    dir="$parent"
  done
}

root="$(git_clean rev-parse --show-toplevel 2>/dev/null)" \
  || fail "not inside a Git worktree"
cd "$root"
reject_cargo_configs_at_and_above "$root"
root_status="$(git_clean status --porcelain=v1 --untracked-files=all)" \
  || fail "cannot inspect invoking worktree"
[[ -z "$root_status" ]] || fail "worktree or index is not clean"
shallow_state="$(git_clean rev-parse --is-shallow-repository)" \
  || fail "cannot inspect shallow state"
[[ "$shallow_state" == "false" ]] || fail "shallow history is forbidden"
replace_refs="$(git_clean for-each-ref --format='%(refname)' refs/replace)" \
  || fail "cannot inspect replace refs"
[[ -z "$replace_refs" ]] || fail "replace refs are forbidden"
common_dir="$(git_clean rev-parse --path-format=absolute --git-common-dir)" \
  || fail "cannot resolve Git common directory"
[[ -d "$common_dir" && ! -L "$common_dir" ]] \
  || fail "Git common directory is missing or aliased"
[[ ! -e "$common_dir/info/grafts" && ! -L "$common_dir/info/grafts" ]] \
  || fail "grafts are forbidden"
[[ ! -e "$common_dir/objects/info/alternates" \
  && ! -L "$common_dir/objects/info/alternates" ]] \
  || fail "alternate object stores are forbidden"
[[ ! -e "$cargo_home/config" && ! -L "$cargo_home/config" \
  && ! -e "$cargo_home/config.toml" && ! -L "$cargo_home/config.toml" ]] \
  || fail "Cargo configuration injection is forbidden"

baseline_type="$(git_clean cat-file -t "$baseline" 2>/dev/null)" \
  || fail "frozen S15 baseline is unavailable"
[[ "$baseline_type" == "commit" ]] || fail "frozen S15 baseline is not a commit"
actual_baseline_tree="$(git_clean show -s --format='%T' "$baseline")" \
  || fail "cannot inspect frozen S15 baseline tree"
[[ "$actual_baseline_tree" == "$baseline_tree" ]] \
  || fail "frozen S15 baseline tree drift"
actual_baseline_parents="$(git_clean show -s --format='%P' "$baseline")" \
  || fail "cannot inspect frozen S15 baseline topology"
[[ "$actual_baseline_parents" == "$baseline_parents" ]] \
  || fail "frozen S15 baseline topology drift"
head_before="$(git_clean rev-parse HEAD)" || fail "cannot resolve HEAD"
git_clean merge-base --is-ancestor "$baseline" "$head_before" \
  || fail "frozen S15 baseline is not an ancestor of HEAD"

source_commit=""
integration_commit=""
mode=""
head_parent_line="$(git_clean show -s --format='%P' "$head_before")" \
  || fail "cannot inspect HEAD parents"
read -r -a head_parents <<<"$head_parent_line"
if [[ "${#head_parents[@]}" == "1" && "${head_parents[0]}" == "$baseline" ]]; then
  source_commit="$head_before"
  mode="source"
else
  candidates=()
  first_parent_history="$(git_clean rev-list --first-parent "$head_before")" \
    || fail "cannot enumerate S15 first-parent history"
  while IFS= read -r candidate; do
    [[ -n "$candidate" ]] || continue
    candidate_parent_line="$(git_clean show -s --format='%P' "$candidate")" \
      || fail "cannot inspect first-parent candidate: $candidate"
    read -r -a candidate_parents <<<"$candidate_parent_line"
    [[ "${#candidate_parents[@]}" == "2" ]] || continue
    first_parent="${candidate_parents[0]}"
    possible_source="${candidate_parents[1]}"
    possible_source_parent_line="$(git_clean show -s --format='%P' "$possible_source")" \
      || fail "cannot inspect possible S15 source: $possible_source"
    read -r -a source_parents <<<"$possible_source_parent_line"
    [[ "${#source_parents[@]}" == "1" && "${source_parents[0]}" == "$baseline" ]] \
      || continue
    if git_clean merge-base --is-ancestor "$baseline" "$first_parent"; then
      :
    else
      ancestor_status="$?"
      [[ "$ancestor_status" == "1" ]] || fail "cannot inspect integration first parent"
      continue
    fi
    if git_clean merge-base --is-ancestor "$possible_source" "$first_parent"; then
      continue
    else
      ancestor_status="$?"
      [[ "$ancestor_status" == "1" ]] || fail "cannot compare source with first parent"
    fi
    candidates+=("$candidate $possible_source")
  done <<<"$first_parent_history"
  [[ "${#candidates[@]}" == "1" ]] \
    || fail "HEAD must contain exactly one ordinary S15 integration"
  read -r integration_commit source_commit <<<"${candidates[0]}"
  [[ "$head_before" == "$integration_commit" ]] \
    && mode="integrated" || mode="historical-descendant"
fi

source_parent_line="$(git_clean show -s --format='%P' "$source_commit")" \
  || fail "cannot inspect S15 source topology"
[[ "$source_parent_line" == "$baseline" ]] \
  || fail "S15 source must have exactly the frozen baseline as parent"
git_clean merge-base --is-ancestor "$source_commit" "$head_before" \
  || fail "S15 source is not an ancestor of HEAD"

integration_first_parent=""
if [[ "$mode" != "source" ]]; then
  integration_parent_line="$(git_clean show -s --format='%P' "$integration_commit")" \
    || fail "cannot inspect S15 integration topology"
  read -r -a integration_parents <<<"$integration_parent_line"
  [[ "${#integration_parents[@]}" == "2" \
    && "${integration_parents[1]}" == "$source_commit" ]] \
    || fail "S15 integration parent shape drift"
  integration_first_parent="${integration_parents[0]}"
fi

tmp_root="/Data/CascadeProjects/.ab-gate-tmp"
"$mkdir_bin" -p -m 700 "$tmp_root" || fail "cannot create gate temp root"
[[ -d "$tmp_root" && ! -L "$tmp_root" ]] || fail "gate temp root is aliased"
resolved_tmp_root="$(cd "$tmp_root" && pwd -P)" \
  || fail "cannot resolve gate temp root"
[[ "$resolved_tmp_root" == "/Data/CascadeProjects/.ab-gate-tmp" ]] \
  || fail "gate temp root resolved outside /Data"
tmp_root_mode="$("$stat_bin" -c '%a' "$tmp_root")" \
  || fail "cannot inspect gate temp root permissions"
[[ "$tmp_root_mode" == "700" ]] || fail "gate temp root permissions must be 0700"
tmp_root_owner="$("$stat_bin" -c '%u' "$tmp_root")" \
  || fail "cannot inspect gate temp root owner"
current_uid="$("$id_bin" -u)" || fail "cannot inspect current uid"
[[ "$tmp_root_owner" == "$current_uid" ]] \
  || fail "gate temp root must be owned by the invoking uid"
tmp="$("$mktemp_bin" -d "$tmp_root/s15-gate.XXXXXXXX")" \
  || fail "cannot create private gate temp directory"
cleanup() { "$rm_bin" -rf -- "$tmp"; }
trap cleanup EXIT
"$mkdir_bin" -m 700 "$tmp/home" "$tmp/cargo-tmp" "$tmp/s14-tmp"
"$mkdir_bin" -m 700 "$tmp/cargo-home"
[[ -d "$cargo_home/registry" && ! -L "$cargo_home/registry" ]] \
  || fail "trusted offline Cargo registry is missing or aliased"
"$cp_bin" -a --no-preserve=ownership -- "$cargo_home/registry" \
  "$tmp/cargo-home/registry" \
  || fail "cannot create private offline Cargo registry snapshot"
private_registry_link="$(/usr/bin/find "$tmp/cargo-home/registry" \
  -type l -print -quit)" \
  || fail "cannot inspect private Cargo registry snapshot"
[[ -z "$private_registry_link" ]] \
  || fail "private Cargo registry snapshot contains a symbolic link"
shared_registry_identity="$("$stat_bin" -c '%d:%i' "$cargo_home/registry")" \
  || fail "cannot record shared Cargo registry identity"
private_registry_identity="$("$stat_bin" -c '%d:%i' \
  "$tmp/cargo-home/registry")" \
  || fail "cannot record private Cargo registry identity"
[[ "$private_registry_identity" != "$shared_registry_identity" ]] \
  || fail "private Cargo registry aliases the shared registry"

verify_private_cargo_home() {
  [[ -d "$tmp/cargo-home" && ! -L "$tmp/cargo-home" ]] \
    || fail "private Cargo home is missing or aliased"
  [[ -d "$tmp/cargo-home/registry" && ! -L "$tmp/cargo-home/registry" ]] \
    || fail "private Cargo registry snapshot is missing or aliased"
  current_private_registry_identity="$("$stat_bin" -c '%d:%i' \
    "$tmp/cargo-home/registry")" \
    || fail "cannot inspect private Cargo registry identity"
  [[ "$current_private_registry_identity" == "$private_registry_identity" ]] \
    || fail "private Cargo registry identity drift"
  [[ ! -e "$tmp/cargo-home/config" && ! -L "$tmp/cargo-home/config" \
    && ! -e "$tmp/cargo-home/config.toml" && ! -L "$tmp/cargo-home/config.toml" ]] \
    || fail "private Cargo configuration appeared"
}
verify_private_cargo_home

printf '%s\n' "${source_paths[@]}" | "$sort_bin" >"$tmp/expected-paths"
git_clean diff --no-renames --no-ext-diff --no-textconv --name-only \
  "$baseline" "$source_commit" \
  | "$sort_bin" >"$tmp/actual-paths"
/usr/bin/diff -u "$tmp/expected-paths" "$tmp/actual-paths" \
  || fail "S15 source delta path allowlist drift"
[[ "${#source_paths[@]}" == "10" && "${#glue_paths[@]}" == "2" \
  && "${#packet_paths[@]}" == "8" ]] \
  || fail "S15 source/glue/packet catalog cardinality drift"

if [[ "$mode" != "source" ]]; then
  git_clean diff --no-renames --no-ext-diff --no-textconv --name-only \
    "$integration_first_parent" "$integration_commit" \
    | "$sort_bin" >"$tmp/integration-paths" \
    || fail "cannot inspect S15 integration delta"
  /usr/bin/diff -u "$tmp/expected-paths" "$tmp/integration-paths" \
    || fail "S15 integration delta escaped source path allowlist"
  for path in "${packet_paths[@]}"; do
    first_parent_entry="$(git_clean ls-tree "$integration_first_parent" -- "$path")" \
      || fail "cannot inspect integration first-parent packet: $path"
    [[ -z "$first_parent_entry" ]] \
      || fail "integration first parent already contains S15 packet: $path"
  done
  for path in "${source_paths[@]}"; do
    source_entry="$(git_clean ls-tree "$source_commit" -- "$path")" \
      || fail "cannot inspect source integration blob: $path"
    integration_entry="$(git_clean ls-tree "$integration_commit" -- "$path")" \
      || fail "cannot inspect integrated S15 blob: $path"
    [[ -n "$source_entry" && "$source_entry" == "$integration_entry" ]] \
      || fail "S15 integration changed source blob: $path"
  done
fi

for path in "${glue_paths[@]}"; do
  baseline_entry="$(git_clean ls-tree "$baseline" -- "$path")" \
    || fail "cannot inspect baseline S15 glue: $path"
  source_entry="$(git_clean ls-tree "$source_commit" -- "$path")" \
    || fail "cannot inspect source S15 glue: $path"
  [[ -n "$baseline_entry" && -n "$source_entry" ]] \
    || fail "missing S15 glue path: $path"
done
for path in "${packet_paths[@]}"; do
  baseline_entry="$(git_clean ls-tree "$baseline" -- "$path")" \
    || fail "cannot inspect baseline S15 packet: $path"
  [[ -z "$baseline_entry" ]] || fail "S15 packet path already exists at baseline: $path"
  source_entry="$(git_clean ls-tree "$source_commit" -- "$path")" \
    || fail "cannot inspect source S15 packet: $path"
  head_entry="$(git_clean ls-tree "$head_before" -- "$path")" \
    || fail "cannot inspect HEAD S15 packet: $path"
  [[ -n "$source_entry" && "$source_entry" == "$head_entry" ]] \
    || fail "S15 packet is missing or changed at HEAD: $path"
done
for path in "${source_paths[@]}"; do
  entry="$(git_clean ls-tree "$source_commit" -- "$path")" \
    || fail "cannot inspect protected S15 source path: $path"
  [[ -n "$entry" ]] || fail "missing protected S15 source path: $path"
  mode_bits="$("$awk_bin" '{print $1}' <<<"$entry")"
  expected_mode="100644"
  [[ "$path" == "scripts/check-memory-temporal-recovered-envelope-bounded-runtime-adapter-s15.sh" ]] \
    && expected_mode="100755"
  [[ "$mode_bits" == "$expected_mode" ]] \
    || fail "protected S15 source mode drift: $path"
done

git_clean diff --no-renames --no-ext-diff --no-textconv \
  --check "$baseline" "$source_commit"
if [[ "$mode" == "historical-descendant" ]]; then
  descendant_history="$(git_clean rev-list --first-parent \
    "$integration_commit..$head_before")" \
    || fail "cannot enumerate S15 historical descendants"
  while IFS= read -r descendant; do
    [[ -n "$descendant" ]] || continue
    changed="$(git_clean diff-tree --no-commit-id --name-only -r \
      "$descendant^1" "$descendant" -- "${packet_paths[@]}")" \
      || fail "cannot inspect historical S15 packet trajectory"
    [[ -z "$changed" ]] \
      || fail "historical descendant modified frozen S15 packet: $descendant"
  done <<<"$descendant_history"
  git_clean diff --no-renames --no-ext-diff --no-textconv \
    --check "$integration_commit" "$head_before"
fi

build_repo="$tmp/s15-build-repo"
git_clean clone --no-local --no-hardlinks --no-checkout --no-tags \
  "$root" "$build_repo" >/dev/null 2>&1 \
  || fail "cannot create independent S15 build repository"
[[ ! -e "$build_repo/.git/objects/info/alternates" \
  && ! -L "$build_repo/.git/objects/info/alternates" ]] \
  || fail "independent S15 build repository uses object alternates"
git_clean -C "$build_repo" checkout --detach "$head_before" >/dev/null 2>&1 \
  || fail "cannot check out exact S15 verification HEAD"
reject_cargo_configs_at_and_above "$build_repo"
build_head_before="$(git_clean -C "$build_repo" rev-parse HEAD)" \
  || fail "cannot inspect independent S15 build HEAD"
[[ "$build_head_before" == "$head_before" ]] \
  || fail "independent S15 build HEAD drift"
build_status="$(git_clean -C "$build_repo" \
  status --porcelain=v1 --untracked-files=all)" \
  || fail "cannot inspect independent S15 build repository"
[[ -z "$build_status" ]] \
  || fail "independent S15 build repository is not clean"

for pass in 1 2; do
  "$mkdir_bin" -m 700 "$tmp/checker-home-$pass" "$tmp/checker-tmp-$pass"
  "$env_bin" -i \
    PATH=/usr/bin:/bin HOME="$tmp/checker-home-$pass" \
    TMPDIR="$tmp/checker-tmp-$pass" LANG=C.UTF-8 LC_ALL=C.UTF-8 \
    PYTHONDONTWRITEBYTECODE=1 PYTHONHASHSEED=0 \
    "$python_bin" -S -P "$build_repo/$checker" --repo "$build_repo" \
    >"$tmp/s15-receipt-$pass.tsv" \
    || fail "S15 independent checker pass $pass failed"
  /usr/bin/diff -u "$build_repo/$expected" "$tmp/s15-receipt-$pass.tsv" \
    || fail "S15 independent checker pass $pass drift"
done
/usr/bin/cmp "$tmp/s15-receipt-1.tsv" "$tmp/s15-receipt-2.tsv" \
  || fail "S15 independent checker output is nondeterministic"
build_status="$(git_clean -C "$build_repo" \
  status --porcelain=v1 --untracked-files=all)" \
  || fail "cannot inspect S15 checker repository state"
[[ -z "$build_status" ]] \
  || fail "S15 checker dirtied independent build repository"
for path in "${source_paths[@]}"; do
  [[ "$path" == "$report" ]] && continue
  digest="$(git_clean show "$source_commit:$path" | "$sha256sum_bin" \
    | "$awk_bin" '{print $1}')" \
    || fail "cannot hash protected S15 source blob: $path"
  /usr/bin/grep -Fx -- "- \`$path\`: \`$digest\`" \
    "$build_repo/$report" >/dev/null \
    || fail "S15 report does not bind $path at $digest"
done

s14_repo="$tmp/s14-replay-repo"
git_clean clone --no-local --no-hardlinks --no-checkout --no-tags \
  "$root" "$s14_repo" >/dev/null 2>&1 \
  || fail "cannot create independent frozen S14 replay repository"
[[ ! -e "$s14_repo/.git/objects/info/alternates" \
  && ! -L "$s14_repo/.git/objects/info/alternates" ]] \
  || fail "frozen S14 replay repository uses object alternates"
git_clean -C "$s14_repo" checkout --detach "$s14_integration" >/dev/null 2>&1 \
  || fail "cannot check out frozen S14 integration"
reject_cargo_configs_at_and_above "$s14_repo"
s14_head="$(git_clean -C "$s14_repo" rev-parse HEAD)" \
  || fail "cannot inspect frozen S14 replay HEAD"
[[ "$s14_head" == "$s14_integration" ]] \
  || fail "frozen S14 replay HEAD drift"
actual_s14_tree="$(git_clean -C "$s14_repo" show -s --format='%T' HEAD)" \
  || fail "cannot inspect frozen S14 integration tree"
[[ "$actual_s14_tree" == "$s14_tree" ]] \
  || fail "frozen S14 integration tree drift"
actual_s14_parents="$(git_clean -C "$s14_repo" show -s --format='%P' HEAD)" \
  || fail "cannot inspect frozen S14 integration topology"
[[ "$actual_s14_parents" == "$s14_parents" ]] \
  || fail "frozen S14 integration topology drift"
s14_status="$(git_clean -C "$s14_repo" \
  status --porcelain=v1 --untracked-files=all)" \
  || fail "cannot inspect frozen S14 replay repository"
[[ -z "$s14_status" ]] || fail "frozen S14 replay repository is not clean"
actual_s14_gate_sha256="$("$sha256sum_bin" "$s14_repo/$s14_gate" \
  | "$awk_bin" '{print $1}')" \
  || fail "cannot hash frozen S14 gate"
[[ "$actual_s14_gate_sha256" == "$s14_gate_sha256" ]] \
  || fail "frozen S14 gate digest drift"
if ! (
  cd "$s14_repo" || exit 1
  "$env_bin" -i \
    PATH="$trusted_cargo_path" HOME="$tmp/home" TMPDIR="$tmp/s14-tmp" \
    LANG=C.UTF-8 LC_ALL=C.UTF-8 PYTHONDONTWRITEBYTECODE=1 PYTHONHASHSEED=0 \
    RUSTUP_HOME="$rustup_home" CARGO_HOME="$cargo_home" RUSTC="$rustc_bin" \
    GIT_CONFIG_NOSYSTEM=1 GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_SYSTEM=/dev/null \
    CARGO_BUILD_JOBS=1 CARGO_INCREMENTAL=0 RUSTFLAGS="-C debuginfo=0" \
    /usr/bin/bash "./$s14_gate"
) >"$tmp/s14-replay.log" 2>&1; then
  "$tail_bin" -n 100 "$tmp/s14-replay.log" >&2 || true
  fail "frozen S14 integrated gate replay failed"
fi
/usr/bin/grep -Fx $'integration_gate\tVALID_INTEGRATED_BIOCORTEX_AB_TRACK_B_RECOVERED_ENVELOPE_SOURCE_S14' \
  "$tmp/s14-replay.log" >/dev/null \
  || fail "frozen S14 replay did not emit its integrated marker"
/usr/bin/grep -Fx $'gate\tPASS' "$tmp/s14-replay.log" >/dev/null \
  || fail "frozen S14 replay did not emit PASS"
/usr/bin/grep -Fx $'mode\tintegrated' "$tmp/s14-replay.log" >/dev/null \
  || fail "frozen S14 replay did not run in integrated mode"
/usr/bin/grep -Fx $'head\t'"$s14_integration" "$tmp/s14-replay.log" >/dev/null \
  || fail "frozen S14 replay HEAD drift"
s14_status="$(git_clean -C "$s14_repo" \
  status --porcelain=v1 --untracked-files=all)" \
  || fail "cannot inspect frozen S14 replay repository after gate"
[[ -z "$s14_status" ]] \
  || fail "frozen S14 replay dirtied its repository"
reject_cargo_configs_at_and_above "$s14_repo"

run_in_build_env() {
  (
    cd "$build_repo" || fail "cannot enter independent S15 build repository"
    reject_cargo_configs_at_and_above "$build_repo"
    verify_private_cargo_home
    "$env_bin" -i \
      PATH="$trusted_cargo_path" HOME="$tmp/home" TMPDIR="$tmp/cargo-tmp" \
      LANG=C.UTF-8 LC_ALL=C.UTF-8 PYTHONDONTWRITEBYTECODE=1 PYTHONHASHSEED=0 \
      RUSTUP_HOME="$rustup_home" CARGO_HOME="$tmp/cargo-home" \
      CARGO_TARGET_DIR="$tmp/cargo-target" CARGO_BUILD_JOBS=1 \
      CARGO_INCREMENTAL=0 CARGO_NET_OFFLINE=true CARGO_TERM_COLOR=never \
      RUSTC="$rustc_bin" RUSTFLAGS="-C debuginfo=0" \
      GIT_CONFIG_NOSYSTEM=1 GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_SYSTEM=/dev/null \
      "$@"
  )
}

run_in_build_env "$rustfmt_bin" --edition 2021 --check \
  crates/store/src/temporal_replay_transport/recovered_s9_decision_reverification/recovered_envelope_delivery/recovered_envelope_source.rs \
  crates/store/src/temporal_replay_transport/recovered_s9_decision_reverification/recovered_envelope_delivery/recovered_envelope_source/bounded_runtime_adapter.rs

run_and_require_count() {
  local label="$1"
  local expected_count="$2"
  shift 2
  "$@" 2>&1 | "$tee_bin" "$tmp/$label.log"
  /usr/bin/grep -F "test result: ok. $expected_count passed; 0 failed" \
    "$tmp/$label.log" >/dev/null \
    || fail "$label did not report $expected_count passing tests"
}

run_and_require_count s15-tests 13 \
  run_in_build_env "$cargo_bin" test --locked --offline \
    -p ab-store --no-default-features --features "$feature" -j1 \
    'bounded_runtime_adapter::tests::s15_' -- --test-threads=1
run_and_require_count s14-regressions 24 \
  run_in_build_env "$cargo_bin" test --locked --offline \
    -p ab-store --no-default-features --features "$feature" -j1 \
    'recovered_envelope_source::tests::s14_' -- --test-threads=1
run_and_require_count s13-regressions 15 \
  run_in_build_env "$cargo_bin" test --locked --offline \
    -p ab-store --no-default-features --features "$feature" -j1 \
    'recovered_envelope_delivery::tests::s13_' -- --test-threads=1
run_and_require_count s12-regressions 32 \
  run_in_build_env "$cargo_bin" test --locked --offline \
    -p ab-store --no-default-features --features "$feature" -j1 \
    'recovered_s9_decision_reverification::tests::s12_' -- --test-threads=1
run_and_require_count s11-regressions 30 \
  run_in_build_env "$cargo_bin" test --locked --offline \
    -p ab-store --no-default-features --features "$feature" -j1 \
    'external_authority_operation_state_machine::tests::s11_' -- --test-threads=1
run_and_require_count s10-regressions 15 \
  run_in_build_env "$cargo_bin" test --locked --offline \
    -p ab-store --no-default-features --features "$feature" -j1 \
    'external_operation_recovery::tests::s10_' -- --test-threads=1
run_and_require_count s9-regressions 15 \
  run_in_build_env "$cargo_bin" test --locked --offline \
    -p ab-store --no-default-features --features "$feature" -j1 \
    'external_restore_authority::tests::s9_' -- --test-threads=1

run_in_build_env "$cargo_bin" check --locked --offline \
  -p ab-store --no-default-features -j1
run_in_build_env "$cargo_bin" check --locked --offline \
  -p ab-store --no-default-features --features "$feature" -j1
run_in_build_env "$cargo_bin" check --locked --offline \
  -p ab-bridge --no-default-features -j1

verify_private_cargo_home
reject_cargo_configs_at_and_above "$build_repo"
build_status="$(git_clean -C "$build_repo" \
  status --porcelain=v1 --untracked-files=all)" \
  || fail "cannot inspect verified S15 build repository"
[[ -z "$build_status" ]] \
  || fail "verification dirtied independent S15 build repository"
build_head_after="$(git_clean -C "$build_repo" rev-parse HEAD)" \
  || fail "cannot inspect verified S15 build HEAD"
[[ "$build_head_after" == "$head_before" ]] \
  || fail "independent S15 build HEAD changed during verification"
root_head_after="$(git_clean rev-parse HEAD)" \
  || fail "cannot inspect invoking HEAD after verification"
[[ "$root_head_after" == "$head_before" ]] \
  || fail "verification HEAD changed during gate"
root_status="$(git_clean status --porcelain=v1 --untracked-files=all)" \
  || fail "cannot inspect invoking worktree after verification"
[[ -z "$root_status" ]] \
  || fail "verification dirtied invoking worktree"

"$head_bin" -n 80 "$tmp/s15-receipt-1.tsv"
case "$mode" in
  source)
    printf 'source_gate\tVALID_SOURCE_BIOCORTEX_AB_TRACK_B_RECOVERED_ENVELOPE_BOUNDED_RUNTIME_ADAPTER_S15\n'
    ;;
  integrated)
    printf 'integration_gate\tVALID_INTEGRATED_BIOCORTEX_AB_TRACK_B_RECOVERED_ENVELOPE_BOUNDED_RUNTIME_ADAPTER_S15\n'
    ;;
  historical-descendant)
    printf 'historical_descendant_gate\tVALID_HISTORICAL_DESCENDANT_BIOCORTEX_AB_TRACK_B_RECOVERED_ENVELOPE_BOUNDED_RUNTIME_ADAPTER_S15\n'
    ;;
esac
printf 'frozen_s14_integrated_gate_replay\tPASS\n'
printf 'gate\tPASS\n'
printf 'mode\t%s\n' "$mode"
printf 'baseline\t%s\n' "$baseline"
printf 'source_commit\t%s\n' "$source_commit"
[[ -z "$integration_commit" ]] || printf 'integration_commit\t%s\n' "$integration_commit"
printf 'head\t%s\n' "$head_before"
gate_sha256="$("$sha256sum_bin" \
  "$root/scripts/check-memory-temporal-recovered-envelope-bounded-runtime-adapter-s15.sh" \
  | "$awk_bin" '{print $1}')" \
  || fail "cannot hash S15 gate"
printf 'gate_sha256\t%s\n' "$gate_sha256"
