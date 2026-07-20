#!/usr/bin/env bash
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
plan="$root/docs/design/fixtures/biocortex-ab-track-b-owned-lab-dry-run-plan-s21b-a9-v0.json"
temp_root="$(mktemp -d)"
output_dir="$temp_root/transcripts"
mkdir "$output_dir"
cleanup() {
  rm -f "$temp_root/rejected.out" "$temp_root/rejected.err"
  for directory in "$output_dir" "$temp_root/plan-digest" "$temp_root/role" "$temp_root/ordering" "$temp_root/trailing"; do
    rm -f "$directory/controller.json" "$directory/observer.json" "$directory/runner.json" "$directory/validator.json" "$directory/receipt.json"
    rmdir "$directory" 2>/dev/null || true
  done
  rmdir "$temp_root" 2>/dev/null || true
}
trap cleanup EXIT

export CARGO_BUILD_JOBS=1
export CARGO_INCREMENTAL=0
export MALLOC_ARENA_MAX=2
export PYTHONDONTWRITEBYTECODE=1
cargo test --manifest-path "$root/Cargo.toml" --locked --offline -j 1 -p ab-owned-lab-role-artifacts
cargo build --manifest-path "$root/Cargo.toml" --locked --offline -j 1 -p ab-owned-lab-role-artifacts --bins

for role in controller observer runner validator; do
  "$root/target/debug/ab-owned-lab-$role" --dry-run-plan-v1 <"$plan" >"$output_dir/$role.json"
done
python3 -I "$root/scripts/eval/build_memory_temporal_owned_lab_dry_run_chain_receipt_s21b_a10.py" "$output_dir" >"$output_dir/receipt.json"
python3 -I "$root/scripts/eval/check_memory_temporal_owned_lab_dry_run_chain_receipt_s21b_a10.py" "$output_dir" "$output_dir/receipt.json"

expect_rejected() {
  local mutation="$1"
  set +e
  python3 -I "$root/scripts/eval/build_memory_temporal_owned_lab_dry_run_chain_receipt_s21b_a10.py" "$temp_root/$mutation" >"$temp_root/rejected.out" 2>"$temp_root/rejected.err"
  local status=$?
  set -e
  test "$status" -eq 65
  test ! -s "$temp_root/rejected.out"
  test "$(cat "$temp_root/rejected.err")" = "S21B_A10_DRY_RUN_CHAIN_RECEIPT_REJECTED"
}

for mutation in plan-digest role ordering trailing; do
  cp -a "$output_dir" "$temp_root/$mutation"
done
sed -i 's/"plan_sha256":"[0-9a-f]\{64\}"/"plan_sha256":"0000000000000000000000000000000000000000000000000000000000000000"/' "$temp_root/plan-digest/controller.json"
sed -i 's/"role":"observer"/"role":"runner"/' "$temp_root/role/observer.json"
mv "$temp_root/ordering/observer.json" "$temp_root/ordering/observer-hold.json"
mv "$temp_root/ordering/runner.json" "$temp_root/ordering/observer.json"
mv "$temp_root/ordering/observer-hold.json" "$temp_root/ordering/runner.json"
printf ' ' >>"$temp_root/trailing/validator.json"
for mutation in plan-digest role ordering trailing; do
  expect_rejected "$mutation"
done
