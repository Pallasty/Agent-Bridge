#!/usr/bin/env bash
set -euo pipefail

baseline="0dad535e2cfd1a911c139d053409e0c02a7a8a0c"
feature="temporal-evidence-s11-atomic-authority-operation-synthetic"
s10_feature_commit="4bc142e6182be4fa66a7b1542535314490dc714c"

fail() {
  printf 'S11_GATE_FAILED\t%s\n' "$*" >&2
  exit 1
}

root="$(git rev-parse --show-toplevel 2>/dev/null)" || fail "not inside a git worktree"
cd "$root"

[[ -z "$(git status --porcelain=v1 --untracked-files=all)" ]] \
  || fail "worktree or index is not clean"
head_before="$(git rev-parse HEAD)"
[[ "$(git rev-list --parents -n 1 HEAD | awk '{print NF}')" == "2" ]] \
  || fail "HEAD must have exactly one parent"
[[ "$(git rev-parse HEAD^)" == "$baseline" ]] \
  || fail "HEAD parent is not the frozen S11 baseline"
git merge-base --is-ancestor "$s10_feature_commit" HEAD \
  || fail "historical S10 feature commit is not reachable"
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
crates/store/src/temporal_replay_transport.rs
crates/store/src/temporal_replay_transport/external_authority_operation_state_machine.rs
docs/design/MEMORY_TEMPORAL_ATOMIC_AUTHORITY_OPERATION_S11_2026_07_14.md
docs/design/fixtures/biocortex-ab-track-b-atomic-authority-operation-s11-v0.json
docs/design/fixtures/biocortex-ab-track-b-successor-admission-gate-s11-v0.json
docs/reports/goal-c-u/2026-07-14-biocortex-ab-track-b-atomic-authority-operation-s11.md
scripts/check-memory-temporal-atomic-authority-operation-s11.sh
scripts/eval/check_memory_temporal_atomic_authority_operation_s11.py
scripts/eval/fixtures/memory_temporal_atomic_authority_operation_s11.expected.v0.tsv
EOF
git diff --name-only "$baseline" HEAD | LC_ALL=C sort >"$tmp/actual-paths"
diff -u "$tmp/expected-paths" "$tmp/actual-paths" \
  || fail "S11 delta path allowlist drift"

while IFS= read -r path; do
  entry="$(git ls-tree HEAD -- "$path")"
  [[ -n "$entry" ]] || fail "missing committed path: $path"
  mode="$(awk '{print $1}' <<<"$entry")"
  object_type="$(awk '{print $2}' <<<"$entry")"
  [[ "$object_type" == "blob" ]] || fail "non-blob path: $path"
  expected_mode="100644"
  [[ "$path" == "scripts/check-memory-temporal-atomic-authority-operation-s11.sh" ]] \
    && expected_mode="100755"
  [[ "$mode" == "$expected_mode" ]] || fail "mode drift for $path: $mode"
done <"$tmp/expected-paths"

archive="$tmp/archive"
baseline_archive="$tmp/baseline-archive"
mkdir -m 700 "$archive" "$baseline_archive"
git archive HEAD | tar -x -C "$archive"
git archive "$baseline" | tar -x -C "$baseline_archive"
for archived_tree in "$archive" "$baseline_archive"; do
  [[ -z "$(find "$archived_tree" -type l -print -quit)" ]] \
    || fail "archive contains a symlink"
  [[ -z "$(find "$archived_tree" -type f -links +1 -print -quit)" ]] \
    || fail "archive contains a hardlinked file"
done

s11_checker="scripts/eval/check_memory_temporal_atomic_authority_operation_s11.py"
s11_expected="scripts/eval/fixtures/memory_temporal_atomic_authority_operation_s11.expected.v0.tsv"
for pass in 1 2; do
  command -p env -i \
    PATH="$PATH" \
    HOME="${HOME:-/tmp}" \
    LANG=C.UTF-8 \
    LC_ALL=C.UTF-8 \
    PYTHONDONTWRITEBYTECODE=1 \
    python3 "$archive/$s11_checker" --repo "$archive" >"$tmp/s11-receipt-$pass.tsv"
  diff -u "$archive/$s11_expected" "$tmp/s11-receipt-$pass.tsv" \
    || fail "S11 receipt pass $pass drift"
done
cmp "$tmp/s11-receipt-1.tsv" "$tmp/s11-receipt-2.tsv" \
  || fail "S11 checker output is nondeterministic"

s10_checker="scripts/eval/check_memory_temporal_external_operation_recovery_s10.py"
s10_expected="scripts/eval/fixtures/memory_temporal_external_operation_recovery_s10.expected.v0.tsv"
command -p env -i \
  PATH="$PATH" \
  HOME="${HOME:-/tmp}" \
  LANG=C.UTF-8 \
  LC_ALL=C.UTF-8 \
  PYTHONDONTWRITEBYTECODE=1 \
  python3 "$baseline_archive/$s10_checker" \
    --repo "$baseline_archive" >"$tmp/s10-baseline.tsv"
diff -u "$baseline_archive/$s10_expected" "$tmp/s10-baseline.tsv" \
  || fail "historical S10 baseline checker regressed"

command -p env -i \
  PATH="$PATH" \
  HOME="${HOME:-/tmp}" \
  LANG=C.UTF-8 \
  LC_ALL=C.UTF-8 \
  PYTHONDONTWRITEBYTECODE=1 \
  python3 "$archive/scripts/eval/check_biocortex_ab_track_b_context_sampling_determinism_pack.py" \
    --root "$archive" >"$tmp/context.tsv"
diff -u \
  "$archive/scripts/eval/fixtures/biocortex_ab_track_b_context_sampling_determinism_pack.expected.v0.tsv" \
  "$tmp/context.tsv" || fail "context-sampling compatibility checker regressed"

report="$archive/docs/reports/goal-c-u/2026-07-14-biocortex-ab-track-b-atomic-authority-operation-s11.md"
while IFS= read -r path; do
  [[ "$path" == "docs/reports/goal-c-u/2026-07-14-biocortex-ab-track-b-atomic-authority-operation-s11.md" ]] \
    && continue
  digest="$(sha256sum "$archive/$path" | awk '{print $1}')"
  grep -F -- "- \`$path\`: \`$digest\`" "$report" >/dev/null \
    || fail "report does not bind $path at $digest"
done <"$tmp/expected-paths"

git diff --check "$baseline" HEAD
rustfmt --edition 2021 --check \
  crates/store/src/temporal_replay_transport.rs \
  crates/store/src/temporal_replay_transport/external_authority_operation_state_machine.rs

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

run_and_require_count s11-tests 29 \
  cargo test --locked --offline -p ab-store --no-default-features --features "$feature" \
    -j1 s11_ -- --test-threads=1
run_and_require_count s10-regressions 14 \
  cargo test --locked --offline -p ab-store --no-default-features --features "$feature" \
    -j1 s10_ -- --test-threads=1
run_and_require_count s9-regressions 14 \
  cargo test --locked --offline -p ab-store --no-default-features --features "$feature" \
    -j1 s9_ -- --test-threads=1
run_and_require_count s8-regressions 14 \
  cargo test --locked --offline -p ab-store --no-default-features --features "$feature" \
    -j1 s8_ -- --test-threads=1
run_and_require_count s7-regressions 13 \
  cargo test --locked --offline -p ab-store --no-default-features --features "$feature" \
    -j1 s7_ -- --test-threads=1
run_and_require_count s6-regressions 7 \
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

[[ "$(git rev-parse HEAD)" == "$head_before" ]] \
  || fail "HEAD changed during verification"
[[ -z "$(git status --porcelain=v1 --untracked-files=all)" ]] \
  || fail "verification dirtied worktree or index"

cat "$tmp/s11-receipt-1.tsv"
printf 'gate\tPASS\n'
printf 'head\t%s\n' "$head_before"
