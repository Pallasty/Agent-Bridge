#!/usr/bin/bash
set -euo pipefail
umask 077

baseline="a152b26ed839d4b96f669552f090ec55bc066ca9"
baseline_tree="dc02d96d21bbb80f45507c2ac97849ee1a9f613f"
baseline_parents="91853814b9b50dead726ac7599dc17baf675f312"
feature="temporal-evidence-s16-recovered-envelope-durability-fault-model-synthetic"
checker="scripts/eval/check_memory_temporal_recovered_envelope_durability_fault_model_s16.py"
expected="scripts/eval/fixtures/memory_temporal_recovered_envelope_durability_fault_model_s16.expected.v0.tsv"
report="docs/reports/goal-c-u/2026-07-17-biocortex-ab-track-b-recovered-envelope-durability-fault-model-s16.md"
s15_integration="80fdb9b5d5f4be5f9663f30cd686cd5fb6bdfd35"
s15_tree="1a9f128f19df6bdca66e648e6dddcc058b9f4251"
s15_parents="b15a48d17fb30b0990bf26210978f2a4f78f54cc 413ac9e94e457d31ae297647c2110768e05acc15"
s15_gate="scripts/check-memory-temporal-recovered-envelope-bounded-runtime-adapter-s15.sh"
s15_gate_sha256="01baf4f105189c1a7ce583e0814969903ef5bc4834df6ade9fd53e70fcf30eaa"

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
  "crates/store/src/temporal_replay_transport/recovered_s9_decision_reverification/recovered_envelope_delivery/recovered_envelope_source/bounded_runtime_adapter.rs"
  "crates/store/src/temporal_replay_transport/recovered_s9_decision_reverification/recovered_envelope_delivery/recovered_envelope_source/bounded_runtime_adapter/durability_fault_model.rs"
  "docs/design/MEMORY_TEMPORAL_RECOVERED_ENVELOPE_DURABILITY_FAULT_MODEL_S16_2026_07_17.md"
  "docs/design/fixtures/biocortex-ab-track-b-recovered-envelope-durability-fault-model-s16-v0.json"
  "docs/design/fixtures/biocortex-ab-track-b-successor-admission-gate-s16-v0.json"
  "$report"
  "scripts/check-memory-temporal-recovered-envelope-durability-fault-model-s16.sh"
  "$checker"
  "$expected"
)
glue_paths=(
  "crates/store/Cargo.toml"
  "crates/store/src/temporal_replay_transport/recovered_s9_decision_reverification/recovered_envelope_delivery/recovered_envelope_source/bounded_runtime_adapter.rs"
)
packet_paths=(
  "crates/store/src/temporal_replay_transport/recovered_s9_decision_reverification/recovered_envelope_delivery/recovered_envelope_source/bounded_runtime_adapter/durability_fault_model.rs"
  "docs/design/MEMORY_TEMPORAL_RECOVERED_ENVELOPE_DURABILITY_FAULT_MODEL_S16_2026_07_17.md"
  "docs/design/fixtures/biocortex-ab-track-b-recovered-envelope-durability-fault-model-s16-v0.json"
  "docs/design/fixtures/biocortex-ab-track-b-successor-admission-gate-s16-v0.json"
  "$report"
  "scripts/check-memory-temporal-recovered-envelope-durability-fault-model-s16.sh"
  "$checker"
  "$expected"
)

fail() {
  printf 'S16_GATE_FAILED\t%s\n' "$*" >&2
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
[[ "$(git_clean rev-parse --is-shallow-repository)" == "false" ]] \
  || fail "shallow history is forbidden"
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

[[ "$(git_clean cat-file -t "$baseline" 2>/dev/null)" == "commit" ]] \
  || fail "frozen S16 baseline is unavailable"
[[ "$(git_clean show -s --format='%T' "$baseline")" == "$baseline_tree" ]] \
  || fail "frozen S16 baseline tree drift"
[[ "$(git_clean show -s --format='%P' "$baseline")" == "$baseline_parents" ]] \
  || fail "frozen S16 baseline topology drift"
head_before="$(git_clean rev-parse HEAD)" || fail "cannot resolve HEAD"
git_clean merge-base --is-ancestor "$baseline" "$head_before" \
  || fail "frozen S16 baseline is not an ancestor of HEAD"

tmp_root="/Data/CascadeProjects/.ab-gate-tmp"
"$mkdir_bin" -p -m 700 "$tmp_root" || fail "cannot create gate temp root"
[[ -d "$tmp_root" && ! -L "$tmp_root" ]] || fail "gate temp root is aliased"
[[ "$(cd "$tmp_root" && pwd -P)" == "$tmp_root" ]] \
  || fail "gate temp root resolved outside /Data"
[[ "$("$stat_bin" -c '%a' "$tmp_root")" == "700" ]] \
  || fail "gate temp root permissions must be 0700"
[[ "$("$stat_bin" -c '%u' "$tmp_root")" == "$("$id_bin" -u)" ]] \
  || fail "gate temp root must be owned by the invoking uid"
tmp="$("$mktemp_bin" -d "$tmp_root/s16-gate.XXXXXXXX")" \
  || fail "cannot create private gate temp directory"
cleanup() { "$rm_bin" -rf -- "$tmp"; }
trap cleanup EXIT
"$mkdir_bin" -m 700 "$tmp/home" "$tmp/cargo-tmp" "$tmp/s15-tmp" \
  "$tmp/cargo-home"

[[ "${#source_paths[@]}" == "10" && "${#glue_paths[@]}" == "2" \
  && "${#packet_paths[@]}" == "8" ]] \
  || fail "S16 source/glue/packet catalog cardinality drift"
printf '%s\n' "${source_paths[@]}" | "$sort_bin" >"$tmp/expected-paths"

source_commit=""
integration_commit=""
integration_first_parent=""
mode=""
head_parents="$(git_clean show -s --format='%P' "$head_before")" \
  || fail "cannot inspect HEAD topology"
if [[ "$head_parents" == "$baseline" ]]; then
  source_commit="$head_before"
  mode="source"
else
  candidates=()
  candidate_history="$(git_clean rev-list --first-parent --merges \
    "$baseline..$head_before")" \
    || fail "cannot enumerate S16 integration candidates"
  while IFS= read -r candidate; do
    [[ -n "$candidate" ]] || continue
    parent_line="$(git_clean show -s --format='%P' "$candidate")" \
      || fail "cannot inspect integration candidate: $candidate"
    read -r -a parents <<<"$parent_line"
    [[ "${#parents[@]}" == "2" ]] || continue
    first_parent="${parents[0]}"
    possible_source="${parents[1]}"
    [[ "$(git_clean show -s --format='%P' "$possible_source")" == "$baseline" ]] \
      || continue
    if git_clean merge-base --is-ancestor "$baseline" "$first_parent"; then
      :
    else
      ancestor_status="$?"
      [[ "$ancestor_status" == "1" ]] \
        || fail "cannot inspect S16 integration first parent"
      continue
    fi
    if git_clean merge-base --is-ancestor "$possible_source" "$first_parent"; then
      continue
    else
      ancestor_status="$?"
      [[ "$ancestor_status" == "1" ]] \
        || fail "cannot compare S16 source with integration first parent"
    fi
    git_clean diff --no-renames --no-ext-diff --no-textconv --name-only \
      "$first_parent" "$candidate" | "$sort_bin" \
      >"$tmp/candidate-integration-paths" \
      || fail "cannot inspect S16 integration candidate delta"
    /usr/bin/cmp -s "$tmp/expected-paths" "$tmp/candidate-integration-paths" \
      || continue
    candidates+=("$candidate $possible_source $first_parent")
  done <<<"$candidate_history"
  [[ "${#candidates[@]}" == "1" ]] \
    || fail "HEAD must be one ordinary source-bound S16 integration"
  read -r integration_commit source_commit integration_first_parent \
    <<<"${candidates[0]}"
  [[ "$head_before" == "$integration_commit" ]] \
    || fail "S16 integrated gate only accepts the integration commit itself"
  mode="integrated"
fi

[[ "$(git_clean show -s --format='%P' "$source_commit")" == "$baseline" ]] \
  || fail "S16 source must be a direct child of the frozen baseline"
git_clean diff --no-renames --no-ext-diff --no-textconv --name-only \
  "$baseline" "$source_commit" | "$sort_bin" >"$tmp/source-paths" \
  || fail "cannot inspect S16 source delta"
/usr/bin/diff -u "$tmp/expected-paths" "$tmp/source-paths" \
  || fail "S16 source delta path allowlist drift"
git_clean merge-base --is-ancestor "$source_commit" "$head_before" \
  || fail "S16 source is not an ancestor of HEAD"

if [[ "$mode" == "integrated" ]]; then
  integration_parents="$(git_clean show -s --format='%P' "$integration_commit")" \
    || fail "cannot inspect S16 integration topology"
  [[ "$integration_parents" == "$integration_first_parent $source_commit" ]] \
    || fail "S16 integration parent topology drift"
  for path in "${packet_paths[@]}"; do
    [[ -z "$(git_clean ls-tree "$integration_first_parent" -- "$path")" ]] \
      || fail "integration first parent already contains S16 packet: $path"
  done
  for path in "${source_paths[@]}"; do
    source_entry="$(git_clean ls-tree "$source_commit" -- "$path")" \
      || fail "cannot inspect S16 source blob: $path"
    integrated_entry="$(git_clean ls-tree "$integration_commit" -- "$path")" \
      || fail "cannot inspect integrated S16 blob: $path"
    [[ -n "$source_entry" && "$source_entry" == "$integrated_entry" ]] \
      || fail "S16 integration changed source blob: $path"
  done
fi

for path in "${glue_paths[@]}"; do
  [[ -n "$(git_clean ls-tree "$baseline" -- "$path")" \
    && -n "$(git_clean ls-tree "$source_commit" -- "$path")" ]] \
    || fail "missing S16 glue path: $path"
done
for path in "${packet_paths[@]}"; do
  [[ -z "$(git_clean ls-tree "$baseline" -- "$path")" ]] \
    || fail "S16 packet path already exists at baseline: $path"
  source_entry="$(git_clean ls-tree "$source_commit" -- "$path")" \
    || fail "cannot inspect source S16 packet: $path"
  head_entry="$(git_clean ls-tree "$head_before" -- "$path")" \
    || fail "cannot inspect HEAD S16 packet: $path"
  [[ -n "$source_entry" && "$source_entry" == "$head_entry" ]] \
    || fail "S16 packet is missing or changed at HEAD: $path"
done
for path in "${source_paths[@]}"; do
  entry="$(git_clean ls-tree "$source_commit" -- "$path")" \
    || fail "cannot inspect protected S16 source path: $path"
  mode_bits="$("$awk_bin" '{print $1}' <<<"$entry")"
  expected_mode="100644"
  [[ "$path" == "scripts/check-memory-temporal-recovered-envelope-durability-fault-model-s16.sh" ]] \
    && expected_mode="100755"
  [[ "$mode_bits" == "$expected_mode" ]] \
    || fail "protected S16 source mode drift: $path"
done
git_clean diff --no-renames --no-ext-diff --no-textconv \
  --check "$baseline" "$source_commit"

build_repo="$tmp/s16-build-repo"
git_clean clone --no-local --no-hardlinks --no-checkout --no-tags \
  "$root" "$build_repo" >/dev/null 2>&1 \
  || fail "cannot create independent S16 build repository"
[[ ! -e "$build_repo/.git/objects/info/alternates" \
  && ! -L "$build_repo/.git/objects/info/alternates" ]] \
  || fail "independent S16 build repository uses object alternates"
git_clean -C "$build_repo" checkout --detach "$head_before" >/dev/null 2>&1 \
  || fail "cannot check out exact S16 verification HEAD"
reject_cargo_configs_at_and_above "$build_repo"
[[ "$(git_clean -C "$build_repo" rev-parse HEAD)" == "$head_before" ]] \
  || fail "independent S16 build HEAD drift"
[[ -z "$(git_clean -C "$build_repo" status --porcelain=v1 --untracked-files=all)" ]] \
  || fail "independent S16 build repository is not clean"

for pass in 1 2; do
  "$mkdir_bin" -m 700 "$tmp/checker-home-$pass" "$tmp/checker-tmp-$pass"
  "$env_bin" -i PATH=/usr/bin:/bin HOME="$tmp/checker-home-$pass" \
    TMPDIR="$tmp/checker-tmp-$pass" LANG=C.UTF-8 LC_ALL=C.UTF-8 \
    PYTHONDONTWRITEBYTECODE=1 PYTHONHASHSEED=0 \
    "$python_bin" -S -P "$build_repo/$checker" --repo "$build_repo" \
    >"$tmp/s16-receipt-$pass.tsv" \
    || fail "S16 independent checker pass $pass failed"
  /usr/bin/diff -u "$build_repo/$expected" "$tmp/s16-receipt-$pass.tsv" \
    || fail "S16 independent checker pass $pass drift"
done
/usr/bin/cmp "$tmp/s16-receipt-1.tsv" "$tmp/s16-receipt-2.tsv" \
  || fail "S16 independent checker output is nondeterministic"
[[ -z "$(git_clean -C "$build_repo" status --porcelain=v1 --untracked-files=all)" ]] \
  || fail "S16 checker dirtied independent build repository"

for path in "${source_paths[@]}"; do
  [[ "$path" == "$report" ]] && continue
  digest="$(git_clean show "$source_commit:$path" | "$sha256sum_bin" \
    | "$awk_bin" '{print $1}')" \
    || fail "cannot hash protected S16 source blob: $path"
  /usr/bin/grep -Fx -- "- \`$path\`: \`$digest\`" \
    "$build_repo/$report" >/dev/null \
    || fail "S16 report does not bind $path at $digest"
done
catalog_message_len="$($awk_bin -F '\t' '
  $1 == "catalog_message_len" { if (++count > 1) exit 2; value = $2 }
  END { if (count != 1) exit 1; print value }
' "$tmp/s16-receipt-1.tsv")" \
  || fail "cannot read unique catalog_message_len from S16 receipt"
catalog_sha256="$($awk_bin -F '\t' '
  $1 == "catalog_sha256" { if (++count > 1) exit 2; value = $2 }
  END { if (count != 1) exit 1; print value }
' "$tmp/s16-receipt-1.tsv")" \
  || fail "cannot read unique catalog_sha256 from S16 receipt"
/usr/bin/grep -Fx -- "- catalog_message_len: \`$catalog_message_len\`" \
  "$build_repo/$report" >/dev/null \
  || fail "S16 report does not bind catalog_message_len"
/usr/bin/grep -Fx -- "- catalog_sha256: \`$catalog_sha256\`" \
  "$build_repo/$report" >/dev/null \
  || fail "S16 report does not bind catalog_sha256"

s15_repo="$tmp/s15-replay-repo"
git_clean clone --no-local --no-hardlinks --no-checkout --no-tags \
  "$root" "$s15_repo" >/dev/null 2>&1 \
  || fail "cannot create independent frozen S15 replay repository"
[[ ! -e "$s15_repo/.git/objects/info/alternates" \
  && ! -L "$s15_repo/.git/objects/info/alternates" ]] \
  || fail "frozen S15 replay repository uses object alternates"
git_clean -C "$s15_repo" checkout --detach "$s15_integration" >/dev/null 2>&1 \
  || fail "cannot check out frozen S15 integration"
reject_cargo_configs_at_and_above "$s15_repo"
[[ "$(git_clean -C "$s15_repo" rev-parse HEAD)" == "$s15_integration" ]] \
  || fail "frozen S15 replay HEAD drift"
[[ "$(git_clean -C "$s15_repo" show -s --format='%T' HEAD)" == "$s15_tree" ]] \
  || fail "frozen S15 integration tree drift"
[[ "$(git_clean -C "$s15_repo" show -s --format='%P' HEAD)" == "$s15_parents" ]] \
  || fail "frozen S15 integration topology drift"
[[ -z "$(git_clean -C "$s15_repo" status --porcelain=v1 --untracked-files=all)" ]] \
  || fail "frozen S15 replay repository is not clean"
actual_s15_gate_sha256="$("$sha256sum_bin" "$s15_repo/$s15_gate" \
  | "$awk_bin" '{print $1}')" \
  || fail "cannot hash frozen S15 gate"
[[ "$actual_s15_gate_sha256" == "$s15_gate_sha256" ]] \
  || fail "frozen S15 gate digest drift"
if ! (
  cd "$s15_repo" || exit 1
  "$env_bin" -i PATH="$trusted_cargo_path" HOME="$tmp/home" \
    TMPDIR="$tmp/s15-tmp" LANG=C.UTF-8 LC_ALL=C.UTF-8 \
    PYTHONDONTWRITEBYTECODE=1 PYTHONHASHSEED=0 RUSTUP_HOME="$rustup_home" \
    CARGO_HOME="$cargo_home" RUSTC="$rustc_bin" \
    GIT_CONFIG_NOSYSTEM=1 GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_SYSTEM=/dev/null \
    CARGO_BUILD_JOBS=1 CARGO_INCREMENTAL=0 RUSTFLAGS="-C debuginfo=0" \
    /usr/bin/bash "./$s15_gate"
) >"$tmp/s15-replay.log" 2>&1; then
  "$tail_bin" -n 120 "$tmp/s15-replay.log" >&2 || true
  fail "frozen S15 integrated gate replay failed"
fi
/usr/bin/grep -Fx $'integration_gate\tVALID_INTEGRATED_BIOCORTEX_AB_TRACK_B_RECOVERED_ENVELOPE_BOUNDED_RUNTIME_ADAPTER_S15' \
  "$tmp/s15-replay.log" >/dev/null \
  || fail "frozen S15 replay did not emit its integrated marker"
/usr/bin/grep -Fx $'frozen_s14_integrated_gate_replay\tPASS' \
  "$tmp/s15-replay.log" >/dev/null \
  || fail "frozen S15 replay did not preserve its S14 replay"
/usr/bin/grep -Fx $'gate\tPASS' "$tmp/s15-replay.log" >/dev/null \
  || fail "frozen S15 replay did not emit PASS"
/usr/bin/grep -Fx $'mode\tintegrated' "$tmp/s15-replay.log" >/dev/null \
  || fail "frozen S15 replay did not run in integrated mode"
/usr/bin/grep -Fx $'head\t'"$s15_integration" "$tmp/s15-replay.log" >/dev/null \
  || fail "frozen S15 replay HEAD drift"
[[ -z "$(git_clean -C "$s15_repo" status --porcelain=v1 --untracked-files=all)" ]] \
  || fail "frozen S15 replay dirtied its repository"

[[ -d "$cargo_home/registry" && ! -L "$cargo_home/registry" ]] \
  || fail "trusted offline Cargo registry is missing or aliased"
"$cp_bin" -a --no-preserve=ownership -- "$cargo_home/registry" \
  "$tmp/cargo-home/registry" \
  || fail "cannot create private offline Cargo registry snapshot"
[[ -z "$(/usr/bin/find "$tmp/cargo-home/registry" -type l -print -quit)" ]] \
  || fail "private Cargo registry snapshot contains a symbolic link"
[[ -d "$tmp/cargo-home" && ! -L "$tmp/cargo-home" ]] \
  || fail "private Cargo home is missing or aliased"
private_cargo_home_identity="$("$stat_bin" -c '%d:%i' "$tmp/cargo-home")" \
  || fail "cannot record private Cargo home identity"
private_registry_identity="$("$stat_bin" -c '%d:%i' "$tmp/cargo-home/registry")" \
  || fail "cannot record private Cargo registry identity"
[[ "$private_registry_identity" != "$("$stat_bin" -c '%d:%i' "$cargo_home/registry")" ]] \
  || fail "private Cargo registry aliases the shared registry"

verify_private_cargo_home() {
  [[ -d "$tmp/cargo-home" && ! -L "$tmp/cargo-home" ]] \
    || fail "private Cargo home is missing or aliased"
  [[ "$("$stat_bin" -c '%d:%i' "$tmp/cargo-home")" \
    == "$private_cargo_home_identity" ]] \
    || fail "private Cargo home identity drift"
  [[ -d "$tmp/cargo-home/registry" && ! -L "$tmp/cargo-home/registry" ]] \
    || fail "private Cargo registry snapshot is missing or aliased"
  [[ "$("$stat_bin" -c '%d:%i' "$tmp/cargo-home/registry")" \
    == "$private_registry_identity" ]] \
    || fail "private Cargo registry identity drift"
  [[ -z "$(/usr/bin/find "$tmp/cargo-home/registry" -type l -print -quit)" ]] \
    || fail "private Cargo registry snapshot gained a symbolic link"
  [[ ! -e "$tmp/cargo-home/config" && ! -L "$tmp/cargo-home/config" \
    && ! -e "$tmp/cargo-home/config.toml" && ! -L "$tmp/cargo-home/config.toml" ]] \
    || fail "private Cargo configuration appeared"
}

run_in_build_env() {
  (
    cd "$build_repo" || fail "cannot enter independent S16 build repository"
    reject_cargo_configs_at_and_above "$build_repo"
    verify_private_cargo_home
    "$env_bin" -i PATH="$trusted_cargo_path" HOME="$tmp/home" \
      TMPDIR="$tmp/cargo-tmp" LANG=C.UTF-8 LC_ALL=C.UTF-8 \
      PYTHONDONTWRITEBYTECODE=1 PYTHONHASHSEED=0 RUSTUP_HOME="$rustup_home" \
      CARGO_HOME="$tmp/cargo-home" CARGO_TARGET_DIR="$tmp/cargo-target" \
      CARGO_BUILD_JOBS=1 CARGO_INCREMENTAL=0 CARGO_NET_OFFLINE=true \
      CARGO_TERM_COLOR=never RUSTC="$rustc_bin" RUSTFLAGS="-C debuginfo=0" \
      GIT_CONFIG_NOSYSTEM=1 GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_SYSTEM=/dev/null \
      "$@"
  )
}

run_in_build_env "$rustfmt_bin" --edition 2021 --check \
  crates/store/src/temporal_replay_transport/recovered_s9_decision_reverification/recovered_envelope_delivery/recovered_envelope_source/bounded_runtime_adapter.rs \
  crates/store/src/temporal_replay_transport/recovered_s9_decision_reverification/recovered_envelope_delivery/recovered_envelope_source/bounded_runtime_adapter/durability_fault_model.rs

run_and_require_count() {
  local label="$1" expected_count="$2"
  shift 2
  "$@" 2>&1 | "$tee_bin" "$tmp/$label.log"
  /usr/bin/grep -F "test result: ok. $expected_count passed; 0 failed" \
    "$tmp/$label.log" >/dev/null \
    || fail "$label did not report $expected_count passing tests"
}

run_and_require_count s16-tests 20 \
  run_in_build_env "$cargo_bin" test --locked --offline \
    -p ab-store --no-default-features --features "$feature" -j1 \
    'durability_fault_model::tests::s16_' -- --test-threads=1
run_and_require_count s15-regressions 13 \
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
[[ "$(git_clean -C "$build_repo" rev-parse HEAD)" == "$head_before" ]] \
  || fail "independent S16 build HEAD changed during verification"
[[ -z "$(git_clean -C "$build_repo" status --porcelain=v1 --untracked-files=all)" ]] \
  || fail "verification dirtied independent S16 build repository"
[[ "$(git_clean rev-parse HEAD)" == "$head_before" ]] \
  || fail "verification changed invoking HEAD"
[[ -z "$(git_clean status --porcelain=v1 --untracked-files=all)" ]] \
  || fail "verification dirtied invoking worktree"

"$head_bin" -n 120 "$tmp/s16-receipt-1.tsv"
case "$mode" in
  source)
    printf 'source_gate\tVALID_SOURCE_BIOCORTEX_AB_TRACK_B_RECOVERED_ENVELOPE_DURABILITY_FAULT_MODEL_S16\n'
    ;;
  integrated)
    printf 'integration_gate\tVALID_INTEGRATED_BIOCORTEX_AB_TRACK_B_RECOVERED_ENVELOPE_DURABILITY_FAULT_MODEL_S16\n'
    ;;
esac
printf 'frozen_s15_integrated_gate_replay\tPASS\n'
printf 'gate\tPASS\n'
printf 'mode\t%s\n' "$mode"
printf 'baseline\t%s\n' "$baseline"
printf 'source_commit\t%s\n' "$source_commit"
[[ -z "$integration_commit" ]] || printf 'integration_commit\t%s\n' "$integration_commit"
printf 'head\t%s\n' "$head_before"
gate_sha256="$("$sha256sum_bin" \
  "$root/scripts/check-memory-temporal-recovered-envelope-durability-fault-model-s16.sh" \
  | "$awk_bin" '{print $1}')" \
  || fail "cannot hash S16 gate"
printf 'gate_sha256\t%s\n' "$gate_sha256"
