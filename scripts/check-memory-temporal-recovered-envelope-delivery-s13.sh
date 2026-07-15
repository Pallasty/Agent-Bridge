#!/usr/bin/env bash
set -euo pipefail

baseline="a3cb958e36743b3ce52b86a66e99ae2366b5bc89"
feature="temporal-evidence-s13-recovered-envelope-delivery-synthetic"
checker="scripts/eval/check_memory_temporal_recovered_envelope_delivery_s13.py"
expected="scripts/eval/fixtures/memory_temporal_recovered_envelope_delivery_s13.expected.v0.tsv"
report="docs/reports/goal-c-u/2026-07-15-biocortex-ab-track-b-recovered-envelope-delivery-s13.md"
s12_gate="scripts/check-memory-temporal-recovered-s9-decision-reverification-s12.sh"

fail() {
  printf 'S13_GATE_FAILED\t%s\n' "$*" >&2
  exit 1
}

root="$(git rev-parse --show-toplevel 2>/dev/null)" || fail "not inside a Git worktree"
cd "$root"
[[ -z "$(git status --porcelain=v1 --untracked-files=all)" ]] \
  || fail "worktree or index is not clean"
[[ -z "$(git replace -l)" ]] || fail "replace refs are forbidden"
grafts="$(git rev-parse --git-path info/grafts)"
[[ ! -s "$grafts" ]] || fail "grafts are forbidden"
shallow="$(git rev-parse --git-path shallow)"
[[ ! -s "$shallow" ]] || fail "shallow history is forbidden"

head_before="$(git rev-parse HEAD)"
git cat-file -e "$baseline^{commit}" || fail "frozen S13 baseline is unavailable"
git merge-base --is-ancestor "$baseline" "$head_before" \
  || fail "frozen S13 baseline is not an ancestor of HEAD"

source_commit=""
integration_commit=""
mode=""
parent_line="$(git show -s --format='%P' HEAD)"
read -r -a head_parents <<<"$parent_line"
if [[ "${#head_parents[@]}" == "1" && "${head_parents[0]}" == "$baseline" ]]; then
  source_commit="$head_before"
  mode="source"
else
  candidates=()
  while IFS= read -r candidate; do
    candidate_parent_line="$(git show -s --format='%P' "$candidate")"
    read -r -a candidate_parents <<<"$candidate_parent_line"
    [[ "${#candidate_parents[@]}" == "2" ]] || continue
    first_parent="${candidate_parents[0]}"
    possible_source="${candidate_parents[1]}"
    source_parent_line="$(git show -s --format='%P' "$possible_source")"
    read -r -a source_parents <<<"$source_parent_line"
    [[ "${#source_parents[@]}" == "1" && "${source_parents[0]}" == "$baseline" ]] \
      || continue
    git merge-base --is-ancestor "$baseline" "$first_parent" || continue
    if git merge-base --is-ancestor "$possible_source" "$first_parent"; then
      continue
    fi
    candidates+=("$candidate $possible_source")
  done < <(git rev-list --first-parent "$head_before")
  [[ "${#candidates[@]}" == "1" ]] \
    || fail "HEAD must contain exactly one ordinary S13 integration from the frozen baseline"
  read -r integration_commit source_commit <<<"${candidates[0]}"
  if [[ "$head_before" == "$integration_commit" ]]; then
    mode="integrated"
  else
    mode="historical-descendant"
  fi
fi

git merge-base --is-ancestor "$source_commit" "$head_before" \
  || fail "S13 source is not an ancestor of HEAD"
[[ "$(git show -s --format='%P' "$source_commit")" == "$baseline" ]] \
  || fail "S13 source must have exactly the frozen baseline as parent"

tmp="$(mktemp -d)"
chmod 700 "$tmp"
baseline_worktree=""
cleanup() {
  if [[ -n "$baseline_worktree" ]]; then
    git worktree remove --force "$baseline_worktree" >/dev/null 2>&1 || true
  fi
  rm -rf "$tmp"
}
trap cleanup EXIT

cat >"$tmp/expected-paths" <<'EOF'
crates/store/Cargo.toml
crates/store/src/temporal_replay_transport/external_authority_operation_state_machine.rs
crates/store/src/temporal_replay_transport/external_operation_recovery.rs
crates/store/src/temporal_replay_transport/recovered_s9_decision_reverification.rs
crates/store/src/temporal_replay_transport/recovered_s9_decision_reverification/recovered_envelope_delivery.rs
docs/design/MEMORY_TEMPORAL_RECOVERED_ENVELOPE_DELIVERY_S13_2026_07_15.md
docs/design/fixtures/biocortex-ab-track-b-recovered-envelope-delivery-s13-v0.json
docs/design/fixtures/biocortex-ab-track-b-successor-admission-gate-s13-v0.json
docs/reports/goal-c-u/2026-07-15-biocortex-ab-track-b-recovered-envelope-delivery-s13.md
scripts/check-memory-temporal-recovered-envelope-delivery-s13.sh
scripts/eval/check_memory_temporal_recovered_envelope_delivery_s13.py
scripts/eval/fixtures/memory_temporal_recovered_envelope_delivery_s13.expected.v0.tsv
EOF
LC_ALL=C sort -o "$tmp/expected-paths" "$tmp/expected-paths"
git diff --name-only "$baseline" "$source_commit" | LC_ALL=C sort >"$tmp/actual-paths"
diff -u "$tmp/expected-paths" "$tmp/actual-paths" \
  || fail "S13 source delta path allowlist drift"

while IFS= read -r path; do
  source_entry="$(git ls-tree "$source_commit" -- "$path")"
  head_entry="$(git ls-tree "$head_before" -- "$path")"
  [[ -n "$source_entry" && -n "$head_entry" ]] || fail "missing protected path: $path"
  source_mode="$(awk '{print $1}' <<<"$source_entry")"
  source_type="$(awk '{print $2}' <<<"$source_entry")"
  source_object="$(awk '{print $3}' <<<"$source_entry")"
  head_mode="$(awk '{print $1}' <<<"$head_entry")"
  head_type="$(awk '{print $2}' <<<"$head_entry")"
  head_object="$(awk '{print $3}' <<<"$head_entry")"
  expected_mode="100644"
  [[ "$path" == "scripts/check-memory-temporal-recovered-envelope-delivery-s13.sh" ]] \
    && expected_mode="100755"
  [[ "$source_mode" == "$expected_mode" && "$head_mode" == "$expected_mode" \
    && "$source_type" == "blob" && "$head_type" == "blob" \
    && "$source_object" == "$head_object" ]] \
    || fail "protected source/HEAD blob or mode drift: $path"
done <"$tmp/expected-paths"

archive="$tmp/source-archive"
mkdir -m 700 "$archive"
git archive "$source_commit" | tar -x -C "$archive"
[[ -z "$(find "$archive" -type l -print -quit)" ]] || fail "source archive contains a symlink"
[[ -z "$(find "$archive" -type f -links +1 -print -quit)" ]] \
  || fail "source archive contains a hard-linked file"

for pass in 1 2; do
  command -p env -i \
    PATH="$PATH" HOME="${HOME:-/tmp}" LANG=C.UTF-8 LC_ALL=C.UTF-8 \
    PYTHONDONTWRITEBYTECODE=1 \
    python3 "$archive/$checker" --repo "$archive" >"$tmp/s13-receipt-$pass.tsv"
  diff -u "$archive/$expected" "$tmp/s13-receipt-$pass.tsv" \
    || fail "S13 independent receipt pass $pass drift"
done
cmp "$tmp/s13-receipt-1.tsv" "$tmp/s13-receipt-2.tsv" \
  || fail "S13 checker output is nondeterministic"

while IFS= read -r path; do
  [[ "$path" == "$report" ]] && continue
  digest="$(sha256sum "$archive/$path" | awk '{print $1}')"
  grep -F -- "- \`$path\`: \`$digest\`" "$archive/$report" >/dev/null \
    || fail "S13 report does not bind $path at $digest"
done <"$tmp/expected-paths"

git diff --check "$baseline" "$source_commit"
if [[ "$head_before" != "$source_commit" ]]; then
  git diff --check "$integration_commit" "$head_before"
fi
rustfmt --edition 2021 --check \
  crates/store/src/temporal_replay_transport/external_authority_operation_state_machine.rs \
  crates/store/src/temporal_replay_transport/external_operation_recovery.rs \
  crates/store/src/temporal_replay_transport/recovered_s9_decision_reverification.rs \
  crates/store/src/temporal_replay_transport/recovered_s9_decision_reverification/recovered_envelope_delivery.rs

baseline_worktree="$tmp/s12-baseline"
mkdir -m 700 "$tmp/s12-tmp"
git worktree add --detach "$baseline_worktree" "$baseline" >/dev/null
if ! (
    cd "$baseline_worktree"
    TMPDIR="$tmp/s12-tmp" PYTHONDONTWRITEBYTECODE=1 \
      "$s12_gate"
  ) >"$tmp/s12-baseline.log" 2>&1; then
  tail -n 80 "$tmp/s12-baseline.log" >&2 || true
  fail "frozen S12 baseline gate replay failed"
fi
grep -Fx $'historical_descendant_gate\tVALID_HISTORICAL_DESCENDANT_BIOCORTEX_AB_TRACK_B_RECOVERED_S9_DECISION_REVERIFICATION_S12' \
  "$tmp/s12-baseline.log" >/dev/null \
  || fail "frozen S12 baseline gate did not emit its historical-descendant marker"
grep -Fx $'gate\tPASS' "$tmp/s12-baseline.log" >/dev/null \
  || fail "frozen S12 baseline gate did not emit PASS"

export CARGO_BUILD_JOBS=1
export CARGO_INCREMENTAL=0
export CARGO_TARGET_DIR="$tmp/cargo-target"
export RUSTFLAGS="-C debuginfo=0"

run_and_require_count() {
  local label="$1"
  local expected_count="$2"
  shift 2
  "$@" 2>&1 | tee "$tmp/$label.log"
  grep -F "test result: ok. $expected_count passed; 0 failed" "$tmp/$label.log" >/dev/null \
    || fail "$label did not report $expected_count passing tests"
}

run_and_require_count s13-tests 15 \
  cargo test --locked --offline -p ab-store --no-default-features --features "$feature" \
    -j1 s13_ -- --test-threads=1
run_and_require_count s12-regressions 32 \
  cargo test --locked --offline -p ab-store --no-default-features --features "$feature" \
    -j1 s12_ -- --test-threads=1
run_and_require_count s11-regressions 30 \
  cargo test --locked --offline -p ab-store --no-default-features --features "$feature" \
    -j1 'external_authority_operation_state_machine::tests::s11_' -- --test-threads=1
run_and_require_count s10-regressions 15 \
  cargo test --locked --offline -p ab-store --no-default-features --features "$feature" \
    -j1 'external_operation_recovery::tests::s10_' -- --test-threads=1
run_and_require_count s9-regressions 15 \
  cargo test --locked --offline -p ab-store --no-default-features --features "$feature" \
    -j1 'external_restore_authority::tests::s9_' -- --test-threads=1

cargo check --locked --offline -p ab-store --no-default-features --features "$feature" -j1
cargo check --locked --offline -p ab-store --no-default-features -j1
cargo check --locked --offline -p ab-bridge --no-default-features -j1

[[ "$(git rev-parse HEAD)" == "$head_before" ]] || fail "HEAD changed during verification"
[[ -z "$(git status --porcelain=v1 --untracked-files=all)" ]] \
  || fail "verification dirtied worktree or index"

cat "$tmp/s13-receipt-1.tsv"
case "$mode" in
  source)
    printf 'source_gate\tVALID_SOURCE_BIOCORTEX_AB_TRACK_B_RECOVERED_ENVELOPE_DELIVERY_S13\n'
    ;;
  integrated)
    printf 'integration_gate\tVALID_INTEGRATED_BIOCORTEX_AB_TRACK_B_RECOVERED_ENVELOPE_DELIVERY_S13\n'
    ;;
  historical-descendant)
    printf 'historical_descendant_gate\tVALID_HISTORICAL_DESCENDANT_BIOCORTEX_AB_TRACK_B_RECOVERED_ENVELOPE_DELIVERY_S13\n'
    ;;
esac
printf 's12_baseline_gate\tPASS\n'
printf 'gate\tPASS\n'
printf 'mode\t%s\n' "$mode"
printf 'baseline\t%s\n' "$baseline"
printf 'source_commit\t%s\n' "$source_commit"
[[ -z "$integration_commit" ]] || printf 'integration_commit\t%s\n' "$integration_commit"
printf 'head\t%s\n' "$head_before"
