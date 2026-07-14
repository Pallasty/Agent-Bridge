#!/usr/bin/env -S -i /usr/bin/bash
# Clean-HEAD, source-bound gate for the synthetic-only S2 storage mechanism.

set -euo pipefail

while IFS= read -r imported_function; do
  builtin unset -f "$imported_function"
done < <(builtin compgen -A function)

PATH=/usr/bin:/bin
export PATH LC_ALL=C
export GIT_CONFIG_NOSYSTEM=1
export GIT_CONFIG_GLOBAL=/dev/null
export GIT_CONFIG_SYSTEM=/dev/null
unset BASH_ENV ENV CDPATH PERL5OPT PERL5LIB PERL_UNICODE
unset PYTHONPATH PYTHONHOME PYTHONINSPECT PYTHONSTARTUP PYTHONWARNINGS
unset PYTHONBREAKPOINT PYTHONUSERBASE
unset GIT_DIR GIT_WORK_TREE GIT_COMMON_DIR GIT_INDEX_FILE
unset GIT_OBJECT_DIRECTORY GIT_ALTERNATE_OBJECT_DIRECTORIES GIT_REPLACE_REF_BASE
unset GIT_CONFIG GIT_CONFIG_COUNT GIT_CONFIG_PARAMETERS GIT_NAMESPACE
unset GIT_SHALLOW_FILE GIT_CEILING_DIRECTORIES GIT_DISCOVERY_ACROSS_FILESYSTEM
unset LD_AUDIT LD_LIBRARY_PATH LD_PRELOAD

script_dir="$(cd "$(/usr/bin/dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(/usr/bin/git -C "$script_dir/.." rev-parse --show-toplevel)"
baseline="1c1770579c46f325ef4a1dee3f870bfe20a5a09a"
contract_rel="scripts/eval/fixtures/memory_temporal_evidence_substrate_s2_contract_v0.json"
fixture_rel="scripts/eval/fixtures/memory_temporal_evidence_substrate_s2_synthetic_v0.json"
expected_rel="scripts/eval/fixtures/memory_temporal_evidence_substrate_s2.expected.v0.tsv"
checker_rel="scripts/eval/check_memory_temporal_evidence_substrate_s2.py"
gate_rel="scripts/check-memory-temporal-evidence-substrate-s2.sh"
design_rel="docs/design/MEMORY_TEMPORAL_EVIDENCE_SUBSTRATE_S2_2026_07_14.md"
report_rel="docs/reports/goal-c-u/2026-07-14-biocortex-ab-track-b-evidence-substrate-s2.md"
module_rel="crates/store/src/sqlite/temporal_evidence.rs"
tests_rel="crates/store/src/sqlite/temporal_evidence/tests.rs"
sqlite_rel="crates/store/src/sqlite.rs"
manifest_rel="crates/store/Cargo.toml"
lock_rel="Cargo.lock"

paths=(
  "$lock_rel"
  "$manifest_rel"
  "$sqlite_rel"
  "$module_rel"
  "$tests_rel"
  "$design_rel"
  "$report_rel"
  "$gate_rel"
  "$checker_rel"
  "$expected_rel"
  "$contract_rel"
  "$fixture_rel"
)
modes=(100644 100644 100644 100644 100644 100644 100644 100755 100644 100644 100644 100644)

status_before="$(/usr/bin/git -C "$repo_root" status --porcelain=v1 --untracked-files=all --ignore-submodules=none)"
[[ -z "$status_before" ]] || {
  echo "S2 gate requires a clean worktree and index" >&2
  exit 3
}
head_before="$(/usr/bin/git -C "$repo_root" rev-parse --verify HEAD^{commit})"
/usr/bin/git -C "$repo_root" cat-file -e "$baseline^{commit}"
/usr/bin/git -C "$repo_root" merge-base --is-ancestor "$baseline" "$head_before" || {
  echo "S2 baseline is not an ancestor of HEAD" >&2
  exit 1
}

for index in "${!paths[@]}"; do
  path="${paths[$index]}"
  actual_mode="$(/usr/bin/git -C "$repo_root" ls-tree "$head_before" -- "$path" | /usr/bin/awk '{print $1}')"
  [[ "$actual_mode" == "${modes[$index]}" ]] || {
    echo "S2 source/packet mode drifted for $path: $actual_mode" >&2
    exit 1
  }
done

expected_delta=(
  "Cargo.lock"
  "crates/store/Cargo.toml"
  "crates/store/src/sqlite.rs"
  "crates/store/src/sqlite/temporal_evidence.rs"
  "crates/store/src/sqlite/temporal_evidence/tests.rs"
  "docs/design/MEMORY_TEMPORAL_EVIDENCE_SUBSTRATE_S2_2026_07_14.md"
  "docs/reports/goal-c-u/2026-07-14-biocortex-ab-track-b-evidence-substrate-s2.md"
  "scripts/check-memory-temporal-evidence-substrate-s2.sh"
  "scripts/eval/check_memory_temporal_evidence_substrate_s2.py"
  "scripts/eval/fixtures/memory_temporal_evidence_substrate_s2.expected.v0.tsv"
  "scripts/eval/fixtures/memory_temporal_evidence_substrate_s2_contract_v0.json"
  "scripts/eval/fixtures/memory_temporal_evidence_substrate_s2_synthetic_v0.json"
)
actual_delta=()
while IFS= read -r path; do
  [[ -z "$path" ]] || actual_delta+=("$path")
done < <(/usr/bin/git -C "$repo_root" diff --name-only --diff-filter=ACDMRTUXB "$baseline" "$head_before" -- | /usr/bin/sort)
[[ "${actual_delta[*]}" == "${expected_delta[*]}" ]] || {
  echo "S2 tranche contains paths outside the reviewed allowlist" >&2
  /usr/bin/printf 'actual: %s\n' "${actual_delta[*]}" >&2
  exit 1
}

tmp="$(/usr/bin/mktemp -d)"
cleanup() {
  /usr/bin/chmod -R u+w "$tmp" 2>/dev/null || true
  /usr/bin/rm -rf "$tmp"
}
trap cleanup EXIT
/usr/bin/mkdir -m 0700 "$tmp/home" "$tmp/snapshot"
/usr/bin/git -C "$repo_root" archive --format=tar "$head_before" | /usr/bin/tar -xf - -C "$tmp/snapshot"

for path in "${paths[@]}"; do
  [[ -f "$tmp/snapshot/$path" && ! -L "$tmp/snapshot/$path" ]] || {
    echo "S2 archived source/packet member is missing or symlinked: $path" >&2
    exit 1
  }
done

sha() {
  /usr/bin/sha256sum "$1" | /usr/bin/awk '{print $1}'
}

for path in "$design_rel" "$contract_rel" "$fixture_rel" "$checker_rel" \
  "$expected_rel" "$gate_rel" "$module_rel" "$tests_rel" "$sqlite_rel" "$manifest_rel" "$lock_rel"; do
  digest="$(sha "$tmp/snapshot/$path")"
  /usr/bin/grep -Fq "$digest" "$tmp/snapshot/$report_rel" || {
    echo "S2 report does not bind $path at $digest" >&2
    exit 1
  }
done

run_checker() (
  while IFS= read -r name; do
    builtin unset "$name" 2>/dev/null || true
  done < <(builtin compgen -e)
  export PATH=/usr/bin:/bin
  export HOME="$tmp/home"
  export LC_ALL=C
  export TZ=UTC
  export PYTHONDONTWRITEBYTECODE=1
  export PYTHONHASHSEED=0
  export PYTHONNOUSERSITE=1
  export PYTHONSAFEPATH=1
  /usr/bin/python3 "$tmp/snapshot/$checker_rel" \
    --contract "$tmp/snapshot/$contract_rel" \
    --fixture "$tmp/snapshot/$fixture_rel" \
    --source-root "$tmp/snapshot"
)

AB_EVIDENCE_SUBSTRATE_SENTINEL=poison \
AGENT_BRIDGE_EVIDENCE_SUBSTRATE_SENTINEL=poison \
PYTHONINSPECT=1 \
  run_checker >"$tmp/run-one.tsv" 2>"$tmp/run-one.err"
AB_EVIDENCE_SUBSTRATE_SENTINEL=poison \
AGENT_BRIDGE_EVIDENCE_SUBSTRATE_SENTINEL=poison \
PYTHONINSPECT=1 \
  run_checker >"$tmp/run-two.tsv" 2>"$tmp/run-two.err"

[[ ! -s "$tmp/run-one.err" && ! -s "$tmp/run-two.err" ]] || {
  echo "S2 checker wrote unexpected stderr" >&2
  /usr/bin/cat "$tmp/run-one.err" "$tmp/run-two.err" >&2
  exit 1
}
/usr/bin/cmp -s "$tmp/run-one.tsv" "$tmp/run-two.tsv" || {
  echo "S2 checker is nondeterministic" >&2
  exit 1
}
/usr/bin/cmp -s "$tmp/run-one.tsv" "$tmp/snapshot/$expected_rel" || {
  echo "S2 receipt drifted" >&2
  /usr/bin/diff -u "$tmp/snapshot/$expected_rel" "$tmp/run-one.tsv" >&2 || true
  exit 1
}

tool_home="$(/usr/bin/getent passwd "$(/usr/bin/id -u)" | /usr/bin/awk -F: '{print $6}')"
cargo_bin="$tool_home/.cargo/bin/cargo"
[[ -x "$cargo_bin" ]] || {
  echo "offline Cargo toolchain not found at $cargo_bin" >&2
  exit 1
}

run_cargo() (
  while IFS= read -r name; do
    builtin unset "$name" 2>/dev/null || true
  done < <(builtin compgen -e)
  export PATH="$tool_home/.cargo/bin:/usr/bin:/bin"
  export HOME="$tmp/home"
  export CARGO_HOME="$tool_home/.cargo"
  export RUSTUP_HOME="$tool_home/.rustup"
  export CARGO_BUILD_JOBS=1
  export CARGO_INCREMENTAL=0
  export CARGO_NET_OFFLINE=true
  export CARGO_TARGET_DIR="$repo_root/target/evidence-substrate-s2"
  export CARGO_TERM_COLOR=never
  export LC_ALL=C
  export TZ=UTC
  cd "$tmp/snapshot"
  "$cargo_bin" test --offline --locked -j 1 -p ab-store --lib \
    --no-default-features truth_evidence_s2_ -- --test-threads=1
)

run_cargo >"$tmp/cargo.out" 2>"$tmp/cargo.err" || {
  echo "S2 low-memory Rust tests failed" >&2
  /usr/bin/cat "$tmp/cargo.out" "$tmp/cargo.err" >&2
  exit 1
}
/usr/bin/grep -Eq 'test result: ok\. ([6-9]|[1-9][0-9]+) passed' "$tmp/cargo.out" || {
  echo "S2 Rust filter did not execute at least six passing tests" >&2
  /usr/bin/cat "$tmp/cargo.out" >&2
  exit 1
}

head_after="$(/usr/bin/git -C "$repo_root" rev-parse --verify HEAD^{commit})"
status_after="$(/usr/bin/git -C "$repo_root" status --porcelain=v1 --untracked-files=all --ignore-submodules=none)"
[[ "$head_after" == "$head_before" && "$status_after" == "$status_before" ]] || {
  echo "HEAD, worktree, or index changed while S2 gate ran" >&2
  exit 1
}
/usr/bin/git -C "$repo_root" diff --quiet -- .
/usr/bin/git -C "$repo_root" diff --cached --quiet -- .

/usr/bin/printf 'BOUND_TO_HEAD_MEMORY_TEMPORAL_EVIDENCE_SUBSTRATE_S2\n'
/usr/bin/printf 'head=%s\n' "$head_before"
/usr/bin/printf 'design_sha256=%s\n' "$(sha "$repo_root/$design_rel")"
/usr/bin/printf 'contract_sha256=%s\n' "$(sha "$repo_root/$contract_rel")"
/usr/bin/printf 'fixture_sha256=%s\n' "$(sha "$repo_root/$fixture_rel")"
/usr/bin/printf 'checker_sha256=%s\n' "$(sha "$repo_root/$checker_rel")"
/usr/bin/printf 'receipt_sha256=%s\n' "$(sha "$repo_root/$expected_rel")"
/usr/bin/printf 'report_sha256=%s\n' "$(sha "$repo_root/$report_rel")"
/usr/bin/printf 'module_sha256=%s\n' "$(sha "$repo_root/$module_rel")"
/usr/bin/printf 'tests_sha256=%s\n' "$(sha "$repo_root/$tests_rel")"
/usr/bin/printf 'schema_version=43\n'
/usr/bin/printf 'schema_sha256=%s\n' "$(/usr/bin/awk -F '\t' '$1=="schema_sha256" {print $2}' "$tmp/run-one.tsv")"
/usr/bin/printf 'migration_sha256=%s\n' "$(/usr/bin/awk -F '\t' '$1=="migration_sha256" {print $2}' "$tmp/run-one.tsv")"
/usr/bin/printf 'rust_tests=truth_evidence_s2_\n'
/usr/bin/printf 's1_packet_unchanged=true\n'
/usr/bin/printf 'mutable_profile_gap_count=8\n'
/usr/bin/printf 'store_adapter_present=false\n'
/usr/bin/printf 'real_capture_authorized=false\n'
/usr/bin/printf 'biocortex_runtime_influence=false\n'
/usr/bin/printf 'decision=BLOCKED_FAIL_CLOSED\n'
