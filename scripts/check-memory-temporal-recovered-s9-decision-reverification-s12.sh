#!/usr/bin/env bash
set -euo pipefail

baseline="8daa44ee5406b700c59b57b0e44514421bc2f0ad"
feature="temporal-evidence-s12-recovered-s9-decision-reverification-synthetic"
s11_feature_commit="efe75d17a59704a4efa8e062dea9474375e600dd"

fail() {
  printf 'S12_GATE_FAILED\t%s\n' "$*" >&2
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
  || fail "HEAD parent is not the frozen S12 baseline"
git merge-base --is-ancestor "$s11_feature_commit" HEAD \
  || fail "historical S11 feature commit is not reachable"
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
crates/store/src/temporal_replay_transport/external_operation_recovery.rs
crates/store/src/temporal_replay_transport/external_restore_authority.rs
crates/store/src/temporal_replay_transport/recovered_s9_decision_reverification.rs
docs/design/MEMORY_TEMPORAL_RECOVERED_S9_DECISION_REVERIFICATION_S12_2026_07_15.md
docs/design/fixtures/biocortex-ab-track-b-recovered-s9-decision-reverification-s12-v0.json
docs/design/fixtures/biocortex-ab-track-b-successor-admission-gate-s12-v0.json
docs/reports/goal-c-u/2026-07-15-biocortex-ab-track-b-recovered-s9-decision-reverification-s12.md
scripts/check-memory-temporal-recovered-s9-decision-reverification-s12.sh
scripts/eval/check_memory_temporal_recovered_s9_decision_reverification_s12.py
scripts/eval/fixtures/memory_temporal_recovered_s9_decision_reverification_s12.expected.v0.tsv
EOF
git diff --name-only "$baseline" HEAD | LC_ALL=C sort >"$tmp/actual-paths"
diff -u "$tmp/expected-paths" "$tmp/actual-paths" \
  || fail "S12 delta path allowlist drift"

while IFS= read -r path; do
  entry="$(git ls-tree HEAD -- "$path")"
  [[ -n "$entry" ]] || fail "missing committed path: $path"
  mode="$(awk '{print $1}' <<<"$entry")"
  object_type="$(awk '{print $2}' <<<"$entry")"
  [[ "$object_type" == "blob" ]] || fail "non-blob path: $path"
  expected_mode="100644"
  [[ "$path" == "scripts/check-memory-temporal-recovered-s9-decision-reverification-s12.sh" ]] \
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

s12_checker="scripts/eval/check_memory_temporal_recovered_s9_decision_reverification_s12.py"
s12_expected="scripts/eval/fixtures/memory_temporal_recovered_s9_decision_reverification_s12.expected.v0.tsv"
for pass in 1 2; do
  command -p env -i \
    PATH="$PATH" HOME="${HOME:-/tmp}" LANG=C.UTF-8 LC_ALL=C.UTF-8 \
    PYTHONDONTWRITEBYTECODE=1 \
    python3 "$archive/$s12_checker" --repo "$archive" >"$tmp/s12-receipt-$pass.tsv"
  diff -u "$archive/$s12_expected" "$tmp/s12-receipt-$pass.tsv" \
    || fail "S12 receipt pass $pass drift"
done
cmp "$tmp/s12-receipt-1.tsv" "$tmp/s12-receipt-2.tsv" \
  || fail "S12 checker output is nondeterministic"

s11_checker="scripts/eval/check_memory_temporal_atomic_authority_operation_s11.py"
s11_expected="scripts/eval/fixtures/memory_temporal_atomic_authority_operation_s11.expected.v0.tsv"
command -p env -i \
  PATH="$PATH" HOME="${HOME:-/tmp}" LANG=C.UTF-8 LC_ALL=C.UTF-8 \
  PYTHONDONTWRITEBYTECODE=1 \
  python3 "$baseline_archive/$s11_checker" --repo "$baseline_archive" >"$tmp/s11-baseline.tsv"
diff -u "$baseline_archive/$s11_expected" "$tmp/s11-baseline.tsv" \
  || fail "historical S11 baseline checker regressed"

command -p env -i \
  PATH="$PATH" HOME="${HOME:-/tmp}" LANG=C.UTF-8 LC_ALL=C.UTF-8 \
  PYTHONDONTWRITEBYTECODE=1 \
  python3 "$archive/scripts/eval/check_biocortex_ab_track_b_context_sampling_determinism_pack.py" \
    --root "$archive" >"$tmp/context.tsv"
diff -u \
  "$archive/scripts/eval/fixtures/biocortex_ab_track_b_context_sampling_determinism_pack.expected.v0.tsv" \
  "$tmp/context.tsv" || fail "context-sampling compatibility checker regressed"

command -p env -i \
  PATH="$PATH" HOME="${HOME:-/tmp}" LANG=C.UTF-8 LC_ALL=C.UTF-8 \
  PYTHONDONTWRITEBYTECODE=1 \
  python3 "$baseline_archive/scripts/eval/check_biocortex_ab_track_b_sampling_attempt_custodian_v1_pack.py" \
    --root "$baseline_archive" >"$tmp/custodian.tsv"
diff -u \
  "$baseline_archive/scripts/eval/fixtures/biocortex_ab_track_b_sampling_attempt_custodian_v1_pack.expected.v0.tsv" \
  "$tmp/custodian.tsv" || fail "historical sampling-attempt custodian baseline regressed"

report="$archive/docs/reports/goal-c-u/2026-07-15-biocortex-ab-track-b-recovered-s9-decision-reverification-s12.md"
while IFS= read -r path; do
  [[ "$path" == "docs/reports/goal-c-u/2026-07-15-biocortex-ab-track-b-recovered-s9-decision-reverification-s12.md" ]] \
    && continue
  digest="$(sha256sum "$archive/$path" | awk '{print $1}')"
  grep -F -- "- \`$path\`: \`$digest\`" "$report" >/dev/null \
    || fail "report does not bind $path at $digest"
done <"$tmp/expected-paths"

git diff --check "$baseline" HEAD
rustfmt --edition 2021 --check \
  crates/store/src/temporal_replay_transport.rs \
  crates/store/src/temporal_replay_transport/external_restore_authority.rs \
  crates/store/src/temporal_replay_transport/external_operation_recovery.rs \
  crates/store/src/temporal_replay_transport/external_authority_operation_state_machine.rs \
  crates/store/src/temporal_replay_transport/recovered_s9_decision_reverification.rs

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

run_and_require_count s12-tests 32 \
  cargo test --locked --offline -p ab-store --no-default-features --features "$feature" \
    -j1 s12_ -- --test-threads=1
run_and_require_count s11-regressions 29 \
  cargo test --locked --offline -p ab-store --no-default-features --features "$feature" \
    -j1 'external_authority_operation_state_machine::tests::s11_' -- --test-threads=1
run_and_require_count s10-regressions 14 \
  cargo test --locked --offline -p ab-store --no-default-features --features "$feature" \
    -j1 'external_operation_recovery::tests::s10_' -- --test-threads=1
run_and_require_count s9-regressions 15 \
  cargo test --locked --offline -p ab-store --no-default-features --features "$feature" \
    -j1 'external_restore_authority::tests::s9_' -- --test-threads=1
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

cat "$tmp/s12-receipt-1.tsv"
printf 'gate\tPASS\n'
printf 'head\t%s\n' "$head_before"
