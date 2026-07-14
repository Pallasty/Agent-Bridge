#!/usr/bin/env bash
set -euo pipefail

baseline="ddebacba20146a90546db9e4ea4bd2795b9ecc1a"
feature="temporal-evidence-s6-detached-verifier-synthetic"
s5_commit="8739b69fb59fd704dacfe1a44bfc411ed9ebb913"

fail() {
  printf 'S6_GATE_FAILED\t%s\n' "$*" >&2
  exit 1
}

root="$(git rev-parse --show-toplevel 2>/dev/null)" || fail "not inside a git worktree"
cd "$root"

[[ -z "$(git status --porcelain=v1 --untracked-files=all)" ]] || fail "worktree or index is not clean"
head_before="$(git rev-parse HEAD)"
[[ "$(git rev-list --parents -n 1 HEAD | awk '{print NF}')" == "2" ]] \
  || fail "HEAD must have exactly one parent"
[[ "$(git rev-parse HEAD^)" == "$baseline" ]] || fail "HEAD parent is not the frozen S6 baseline"
git merge-base --is-ancestor "$s5_commit" HEAD || fail "historical S5 feature commit is not reachable"
[[ -z "$(git replace -l)" ]] || fail "replace refs are forbidden"
grafts="$(git rev-parse --git-path info/grafts)"
[[ ! -s "$grafts" ]] || fail "grafts are forbidden"
shallow="$(git rev-parse --git-path shallow)"
[[ ! -s "$shallow" ]] || fail "shallow history is forbidden"

tmp="$(mktemp -d)"
chmod 700 "$tmp"
trap 'rm -rf "$tmp"' EXIT

cat >"$tmp/expected-paths" <<'EOF'
crates/store/Cargo.toml
crates/store/src/lib.rs
crates/store/src/temporal_replay_transport.rs
docs/design/MEMORY_TEMPORAL_REPLAY_TRANSPORT_S6_2026_07_14.md
docs/design/fixtures/biocortex-ab-track-b-candidate-exact-payload-profile-v0.json
docs/design/fixtures/biocortex-ab-track-b-replay-transport-contract-v0.json
docs/reports/goal-c-u/2026-07-14-biocortex-ab-track-b-replay-transport-s6.md
scripts/check-memory-temporal-replay-transport-s6.sh
scripts/eval/check_memory_temporal_replay_transport_s6.py
scripts/eval/fixtures/memory_temporal_replay_transport_s6.expected.v0.tsv
scripts/eval/fixtures/memory_temporal_replay_transport_s6_s5_source_manifest_v0.json
scripts/eval/fixtures/memory_temporal_replay_transport_s6_synthetic_v0.json
EOF
git diff --name-only "$baseline" HEAD | LC_ALL=C sort >"$tmp/actual-paths"
diff -u "$tmp/expected-paths" "$tmp/actual-paths" || fail "S6 delta path allowlist drift"

while IFS= read -r path; do
  entry="$(git ls-tree HEAD -- "$path")"
  [[ -n "$entry" ]] || fail "missing committed path: $path"
  mode="$(awk '{print $1}' <<<"$entry")"
  object_type="$(awk '{print $2}' <<<"$entry")"
  [[ "$object_type" == "blob" ]] || fail "non-blob path: $path"
  expected_mode="100644"
  [[ "$path" == "scripts/check-memory-temporal-replay-transport-s6.sh" ]] \
    && expected_mode="100755"
  [[ "$mode" == "$expected_mode" ]] || fail "mode drift for $path: $mode"
done <"$tmp/expected-paths"

archive="$tmp/archive"
mkdir -m 700 "$archive"
git archive HEAD | tar -x -C "$archive"
[[ -z "$(find "$archive" -type l -print -quit)" ]] || fail "archive contains a symlink"
[[ -z "$(find "$archive" -type f -links +1 -print -quit)" ]] || fail "archive contains a hardlinked file"

checker="scripts/eval/check_memory_temporal_replay_transport_s6.py"
expected="scripts/eval/fixtures/memory_temporal_replay_transport_s6.expected.v0.tsv"
for pass in 1 2; do
  command -p env -i \
    PATH="$PATH" \
    HOME="${HOME:-/tmp}" \
    LANG=C.UTF-8 \
    LC_ALL=C.UTF-8 \
    PYTHONDONTWRITEBYTECODE=1 \
    python3 "$archive/$checker" --repo "$archive" --git-repo "$root" \
      >"$tmp/receipt-$pass.tsv"
  diff -u "$archive/$expected" "$tmp/receipt-$pass.tsv" \
    || fail "S6 receipt pass $pass drift"
done
cmp "$tmp/receipt-1.tsv" "$tmp/receipt-2.tsv" || fail "S6 checker output is nondeterministic"

command -p env -i \
  PATH="$PATH" \
  HOME="${HOME:-/tmp}" \
  LANG=C.UTF-8 \
  LC_ALL=C.UTF-8 \
  PYTHONDONTWRITEBYTECODE=1 \
  python3 "$archive/scripts/eval/check_memory_temporal_candidate_binding_s5.py" \
    --repo "$archive" >"$tmp/s5-receipt.tsv"
diff -u \
  "$archive/scripts/eval/fixtures/memory_temporal_candidate_binding_s5.expected.v0.tsv" \
  "$tmp/s5-receipt.tsv" || fail "S5 purpose checker regressed"

report="$archive/docs/reports/goal-c-u/2026-07-14-biocortex-ab-track-b-replay-transport-s6.md"
while IFS= read -r path; do
  [[ "$path" == "docs/reports/goal-c-u/2026-07-14-biocortex-ab-track-b-replay-transport-s6.md" ]] \
    && continue
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

run_and_require_count s6-tests 7 \
  cargo test --locked --offline -p ab-store --no-default-features --features "$feature" \
    -j1 temporal_truth_replay_transport_s6_ -- --test-threads=1
run_and_require_count s5-regressions 7 \
  cargo test --locked --offline -p ab-store --no-default-features --features "$feature" \
    -j1 temporal_truth_candidate_binding_s5_ -- --test-threads=1
run_and_require_count s4-regressions 7 \
  cargo test --locked --offline -p ab-store --no-default-features --features "$feature" \
    -j1 temporal_truth_projection_s4 -- --test-threads=1
run_and_require_count s2-regressions 14 \
  cargo test --locked --offline -p ab-store --no-default-features --features "$feature" \
    -j1 truth_evidence_s2_ -- --test-threads=1

cargo check --locked --offline -p ab-store --no-default-features --features "$feature" -j1
cargo check --locked --offline -p ab-store --no-default-features -j1
cargo check --locked --offline -p ab-bridge --no-default-features \
  --features temporal-evidence-s5-candidate-synthetic -j1
cargo check --locked --offline -p ab-bridge --no-default-features -j1

[[ "$(git rev-parse HEAD)" == "$head_before" ]] || fail "HEAD changed during verification"
[[ -z "$(git status --porcelain=v1 --untracked-files=all)" ]] \
  || fail "verification dirtied worktree or index"

cat "$tmp/receipt-1.tsv"
printf 'gate\tPASS\n'
printf 'head\t%s\n' "$head_before"
