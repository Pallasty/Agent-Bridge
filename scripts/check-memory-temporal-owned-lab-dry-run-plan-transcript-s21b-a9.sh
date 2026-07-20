#!/usr/bin/env bash
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
plan="$root/docs/design/fixtures/biocortex-ab-track-b-owned-lab-dry-run-plan-s21b-a9-v0.json"
output_dir="$(mktemp -d)"
trap 'rm -f "$output_dir"/*; rmdir "$output_dir"' EXIT

export CARGO_BUILD_JOBS=1
export CARGO_INCREMENTAL=0
export MALLOC_ARENA_MAX=2
cargo test --manifest-path "$root/Cargo.toml" --locked --offline -j 1 -p ab-owned-lab-role-artifacts
cargo build --manifest-path "$root/Cargo.toml" --locked --offline -j 1 -p ab-owned-lab-role-artifacts --bins

for role in controller observer runner validator; do
  "$root/target/debug/ab-owned-lab-$role" --dry-run-plan-v1 <"$plan" >"$output_dir/$role.json"
done

expect_rejected() {
  local input="$1"
  set +e
  "$root/target/debug/ab-owned-lab-controller" --dry-run-plan-v1 <"$input" >"$output_dir/rejected.out" 2>"$output_dir/rejected.err"
  local status=$?
  set -e
  test "$status" -eq 65
  test ! -s "$output_dir/rejected.out"
  test "$(cat "$output_dir/rejected.err")" = "S21B_A9_DRY_RUN_PLAN_REJECTED"
}

: >"$output_dir/empty"
head -c 370 "$plan" >"$output_dir/truncated"
cp "$plan" "$output_dir/appended"
printf ' ' >>"$output_dir/appended"
sed 's/"allow_live_execution":false/"allow_live_execution":true/' "$plan" >"$output_dir/live-enabled"
printf '{}\n' >"$output_dir/unknown"
for mutation in empty truncated appended live-enabled unknown; do
  expect_rejected "$output_dir/$mutation"
done

python3 -I "$root/scripts/eval/check_memory_temporal_owned_lab_dry_run_plan_transcript_s21b_a9.py" "$output_dir"
