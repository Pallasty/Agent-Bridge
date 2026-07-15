#!/usr/bin/env bash
set -euo pipefail

baseline="2e828d7b86444770c3ef3cd40ac17f26cac6fb0e"
feature="temporal-evidence-s10-operation-recovery-synthetic"
s9_feature_commit="846ea7c92490dcd35a8a2f2aa15c99c7c87f40dc"

fail() {
  printf 'S10_GATE_FAILED\t%s\n' "$*" >&2
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
  || fail "HEAD parent is not the frozen S10 baseline"
git merge-base --is-ancestor "$s9_feature_commit" HEAD \
  || fail "historical S9 feature commit is not reachable"
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
crates/store/src/temporal_replay_transport/external_operation_recovery.rs
docs/design/MEMORY_TEMPORAL_EXTERNAL_OPERATION_RECOVERY_S10_2026_07_14.md
docs/design/fixtures/biocortex-ab-track-b-external-operation-recovery-s10-v0.json
docs/design/fixtures/biocortex-ab-track-b-successor-admission-gate-s10-v0.json
docs/reports/goal-c-u/2026-07-14-biocortex-ab-track-b-external-operation-recovery-s10.md
scripts/check-memory-temporal-external-operation-recovery-s10.sh
scripts/eval/check_memory_temporal_external_operation_recovery_s10.py
scripts/eval/fixtures/memory_temporal_external_operation_recovery_s10.expected.v0.tsv
EOF
git diff --name-only "$baseline" HEAD | LC_ALL=C sort >"$tmp/actual-paths"
diff -u "$tmp/expected-paths" "$tmp/actual-paths" \
  || fail "S10 delta path allowlist drift"

while IFS= read -r path; do
  entry="$(git ls-tree HEAD -- "$path")"
  [[ -n "$entry" ]] || fail "missing committed path: $path"
  mode="$(awk '{print $1}' <<<"$entry")"
  object_type="$(awk '{print $2}' <<<"$entry")"
  [[ "$object_type" == "blob" ]] || fail "non-blob path: $path"
  expected_mode="100644"
  [[ "$path" == "scripts/check-memory-temporal-external-operation-recovery-s10.sh" ]] \
    && expected_mode="100755"
  [[ "$mode" == "$expected_mode" ]] || fail "mode drift for $path: $mode"
done <"$tmp/expected-paths"

archive="$tmp/archive"
mkdir -m 700 "$archive"
git archive HEAD | tar -x -C "$archive"
[[ -z "$(find "$archive" -type l -print -quit)" ]] \
  || fail "archive contains a symlink"
[[ -z "$(find "$archive" -type f -links +1 -print -quit)" ]] \
  || fail "archive contains a hardlinked file"

checker="scripts/eval/check_memory_temporal_external_operation_recovery_s10.py"
expected="scripts/eval/fixtures/memory_temporal_external_operation_recovery_s10.expected.v0.tsv"
for pass in 1 2; do
  command -p env -i \
    PATH="$PATH" \
    HOME="${HOME:-/tmp}" \
    LANG=C.UTF-8 \
    LC_ALL=C.UTF-8 \
    PYTHONDONTWRITEBYTECODE=1 \
    python3 "$archive/$checker" --repo "$archive" >"$tmp/receipt-$pass.tsv"
  diff -u "$archive/$expected" "$tmp/receipt-$pass.tsv" \
    || fail "S10 receipt pass $pass drift"
done
cmp "$tmp/receipt-1.tsv" "$tmp/receipt-2.tsv" \
  || fail "S10 checker output is nondeterministic"

run_historical_checker() {
  local label="$1"
  local checker_path="$2"
  local expected_path="$3"
  shift 3
  command -p env -i \
    PATH="$PATH" \
    HOME="${HOME:-/tmp}" \
    LANG=C.UTF-8 \
    LC_ALL=C.UTF-8 \
    PYTHONDONTWRITEBYTECODE=1 \
    python3 "$archive/$checker_path" "$@" >"$tmp/$label.tsv"
  diff -u "$archive/$expected_path" "$tmp/$label.tsv" \
    || fail "historical $label checker regressed"
}

run_historical_checker s9 \
  scripts/eval/check_memory_temporal_external_authority_provider_s9.py \
  scripts/eval/fixtures/memory_temporal_external_authority_provider_s9.expected.v0.tsv \
  --repo "$archive"
run_historical_checker s8 \
  scripts/eval/check_memory_temporal_controlled_restore_key_epoch_s8.py \
  scripts/eval/fixtures/memory_temporal_controlled_restore_key_epoch_s8.expected.v0.tsv \
  --repo "$archive"
run_historical_checker s7 \
  scripts/eval/check_memory_temporal_durable_replay_s7.py \
  scripts/eval/fixtures/memory_temporal_durable_replay_s7.expected.v0.tsv \
  --repo "$archive"

command -p env -i \
  PATH="$PATH" \
  HOME="${HOME:-/tmp}" \
  LANG=C.UTF-8 \
  LC_ALL=C.UTF-8 \
  PYTHONDONTWRITEBYTECODE=1 \
  python3 "$archive/scripts/eval/check_memory_temporal_replay_transport_s6.py" \
    --repo "$archive" --git-repo "$root" >"$tmp/s6.tsv"
diff -u \
  "$archive/scripts/eval/fixtures/memory_temporal_replay_transport_s6.expected.v0.tsv" \
  "$tmp/s6.tsv" || fail "historical S6 checker regressed"

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

report="$archive/docs/reports/goal-c-u/2026-07-14-biocortex-ab-track-b-external-operation-recovery-s10.md"
while IFS= read -r path; do
  [[ "$path" == "docs/reports/goal-c-u/2026-07-14-biocortex-ab-track-b-external-operation-recovery-s10.md" ]] \
    && continue
  digest="$(sha256sum "$archive/$path" | awk '{print $1}')"
  grep -F -- "- \`$path\`: \`$digest\`" "$report" >/dev/null \
    || fail "report does not bind $path at $digest"
done <"$tmp/expected-paths"

git diff --check "$baseline" HEAD
rustfmt --edition 2021 --check \
  crates/store/src/temporal_replay_transport.rs \
  crates/store/src/temporal_replay_transport/external_operation_recovery.rs

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

run_and_require_count s10-tests 14 \
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

cat "$tmp/receipt-1.tsv"
printf 'gate\tPASS\n'
printf 'head\t%s\n' "$head_before"
