#!/usr/bin/env bash
set -euo pipefail

baseline="630e82dd1c3d4875bd1da081b28e06fdfe90dedf"
feature="temporal-evidence-s4-synthetic"

fail() {
  printf 'S4_GATE_FAILED\t%s\n' "$*" >&2
  exit 1
}

root="$(git rev-parse --show-toplevel 2>/dev/null)" || fail "not inside a git worktree"
cd "$root"

[[ -z "$(git status --porcelain=v1 --untracked-files=all)" ]] || fail "worktree or index is not clean"
head_before="$(git rev-parse HEAD)"
[[ "$(git rev-list --parents -n 1 HEAD | awk '{print NF}')" == "2" ]] || fail "HEAD must have exactly one parent"
[[ "$(git rev-parse HEAD^)" == "$baseline" ]] || fail "HEAD parent is not the frozen S3 baseline"
[[ -z "$(git replace -l)" ]] || fail "replace refs are forbidden"
grafts="$(git rev-parse --git-path info/grafts)"
[[ ! -s "$grafts" ]] || fail "grafts are forbidden"
shallow="$(git rev-parse --git-path shallow)"
[[ ! -s "$shallow" ]] || fail "shallow history is forbidden"

tmp="$(mktemp -d)"
chmod 700 "$tmp"
trap 'rm -rf "$tmp"' EXIT

cat >"$tmp/expected-paths" <<'EOF'
crates/bridge/Cargo.toml
crates/bridge/src/lib.rs
crates/bridge/src/memory_temporal_evidence_adapter_v1.rs
crates/store/Cargo.toml
crates/store/src/lib.rs
crates/store/src/sqlite.rs
crates/store/src/sqlite/temporal_evidence.rs
crates/store/src/sqlite/temporal_evidence/projection_v1.rs
crates/store/src/sqlite/temporal_evidence/tests.rs
docs/design/MEMORY_TEMPORAL_EVIDENCE_ADAPTER_S4_2026_07_14.md
docs/reports/goal-c-u/2026-07-14-biocortex-ab-track-b-evidence-adapter-s4.md
scripts/check-memory-temporal-evidence-adapter-s4.sh
scripts/eval/check_memory_temporal_evidence_adapter_s4.py
scripts/eval/fixtures/memory_temporal_evidence_adapter_s4.expected.v1.tsv
EOF
git diff --name-only "$baseline" HEAD | LC_ALL=C sort >"$tmp/actual-paths"
diff -u "$tmp/expected-paths" "$tmp/actual-paths" || fail "S4 delta path allowlist drift"

while IFS= read -r path; do
  entry="$(git ls-tree HEAD -- "$path")"
  [[ -n "$entry" ]] || fail "missing committed path: $path"
  mode="$(awk '{print $1}' <<<"$entry")"
  object_type="$(awk '{print $2}' <<<"$entry")"
  [[ "$object_type" == "blob" ]] || fail "non-blob path: $path"
  expected_mode="100644"
  [[ "$path" == "scripts/check-memory-temporal-evidence-adapter-s4.sh" ]] && expected_mode="100755"
  [[ "$mode" == "$expected_mode" ]] || fail "mode drift for $path: $mode"
done <"$tmp/expected-paths"

archive="$tmp/archive"
mkdir -m 700 "$archive"
git archive HEAD | tar -x -C "$archive"
[[ -z "$(find "$archive" -type l -print -quit)" ]] || fail "archive contains a symlink"
[[ -z "$(find "$archive" -type f -links +1 -print -quit)" ]] || fail "archive contains a hardlinked file"

checker="scripts/eval/check_memory_temporal_evidence_adapter_s4.py"
expected="scripts/eval/fixtures/memory_temporal_evidence_adapter_s4.expected.v1.tsv"
for pass in 1 2; do
  command -p env -i \
    PATH="$PATH" \
    HOME="${HOME:-/tmp}" \
    LANG=C.UTF-8 \
    LC_ALL=C.UTF-8 \
    PYTHONDONTWRITEBYTECODE=1 \
    python3 "$archive/$checker" --repo "$archive" >"$tmp/receipt-$pass.tsv"
  diff -u "$archive/$expected" "$tmp/receipt-$pass.tsv" || fail "receipt pass $pass drift"
done
cmp "$tmp/receipt-1.tsv" "$tmp/receipt-2.tsv" || fail "checker output is nondeterministic"

report="$archive/docs/reports/goal-c-u/2026-07-14-biocortex-ab-track-b-evidence-adapter-s4.md"
while IFS= read -r path; do
  [[ "$path" == "docs/reports/goal-c-u/2026-07-14-biocortex-ab-track-b-evidence-adapter-s4.md" ]] && continue
  digest="$(sha256sum "$archive/$path" | awk '{print $1}')"
  grep -F -- "- \`$path\`: \`$digest\`" "$report" >/dev/null \
    || fail "report does not bind $path at $digest"
done <"$tmp/expected-paths"

git diff --check "$baseline" HEAD

export CARGO_BUILD_JOBS=1
export CARGO_INCREMENTAL=0
export RUSTFLAGS="-C debuginfo=0"

run_and_require_count() {
  local label="$1"
  local expected_count="$2"
  shift 2
  "$@" 2>&1 | tee "$tmp/$label.log"
  grep -F "test result: ok. $expected_count passed; 0 failed" "$tmp/$label.log" >/dev/null \
    || fail "$label did not report $expected_count passing tests"
}

run_and_require_count s4-tests 7 \
  cargo test --locked --offline -p ab-store --no-default-features --features "$feature" \
    -j1 temporal_truth_projection_s4 -- --test-threads=1
run_and_require_count s2-regressions 14 \
  cargo test --locked --offline -p ab-store --no-default-features --features "$feature" \
    -j1 truth_evidence_s2_ -- --test-threads=1

cargo check --locked --offline -p ab-store --no-default-features --features "$feature" -j1
cargo check --locked --offline -p ab-bridge --no-default-features --features "$feature" -j1
cargo check --locked --offline -p ab-store --no-default-features -j1
cargo check --locked --offline -p ab-bridge --no-default-features -j1

[[ "$(git rev-parse HEAD)" == "$head_before" ]] || fail "HEAD changed during verification"
[[ -z "$(git status --porcelain=v1 --untracked-files=all)" ]] || fail "verification dirtied worktree or index"

cat "$tmp/receipt-1.tsv"
printf 'gate\tPASS\n'
printf 'head\t%s\n' "$head_before"
