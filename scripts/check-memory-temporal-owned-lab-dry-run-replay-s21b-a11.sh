#!/usr/bin/env bash
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
plan="$root/docs/design/fixtures/biocortex-ab-track-b-owned-lab-dry-run-plan-s21b-a9-v0.json"
temp_root="$(mktemp -d)"
transcripts="$temp_root/transcripts"
mkdir "$transcripts"

cleanup() {
  rm -f "$temp_root/rejected.out" "$temp_root/rejected.err" "$temp_root/receipt.json" "$temp_root/statement.json"
  for directory in "$transcripts" "$temp_root/receipt-body" "$temp_root/transcript" "$temp_root/receipt-extra"; do
    rm -f "$directory/controller.json" "$directory/observer.json" "$directory/runner.json" "$directory/validator.json" "$directory/receipt.json" "$directory/statement.json"
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
  "$root/target/debug/ab-owned-lab-$role" --dry-run-plan-v1 <"$plan" >"$transcripts/$role.json"
done
python3 -I "$root/scripts/eval/build_memory_temporal_owned_lab_dry_run_chain_receipt_s21b_a10.py" "$transcripts" >"$temp_root/receipt.json"
python3 -I "$root/scripts/eval/verify_memory_temporal_owned_lab_dry_run_replay_s21b_a11.py" "$transcripts" "$temp_root/receipt.json" >"$temp_root/statement.json"
python3 -I "$root/scripts/eval/check_memory_temporal_owned_lab_dry_run_replay_s21b_a11.py" "$temp_root/receipt.json" "$temp_root/statement.json"

expect_rejected() {
  local mutation="$1"
  set +e
  python3 -I "$root/scripts/eval/verify_memory_temporal_owned_lab_dry_run_replay_s21b_a11.py" "$temp_root/$mutation" "$temp_root/$mutation/receipt.json" >"$temp_root/rejected.out" 2>"$temp_root/rejected.err"
  local status=$?
  set -e
  test "$status" -eq 65
  test ! -s "$temp_root/rejected.out"
  test "$(cat "$temp_root/rejected.err")" = "S21B_A11_STATIC_REPLAY_REJECTED"
}

for mutation in receipt-body transcript receipt-extra; do
  mkdir "$temp_root/$mutation"
  cp "$transcripts"/*.json "$temp_root/$mutation/"
  cp "$temp_root/receipt.json" "$temp_root/$mutation/receipt.json"
done
sed -i 's/"plan_sha256":"[0-9a-f]\{64\}"/"plan_sha256":"0000000000000000000000000000000000000000000000000000000000000000"/' "$temp_root/receipt-body/receipt.json"
printf ' ' >>"$temp_root/transcript/validator.json"
sed -i 's/}$/,"unexpected":true}/' "$temp_root/receipt-extra/receipt.json"
for mutation in receipt-body transcript receipt-extra; do
  expect_rejected "$mutation"
done
