#!/usr/bin/env bash
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
plan="$root/docs/design/fixtures/biocortex-ab-track-b-owned-lab-dry-run-plan-s21b-a9-v0.json"
temp_root="$(mktemp -d)"
transcripts="$temp_root/transcripts"
mkdir "$transcripts"

cleanup() {
  rm -f "$temp_root/rejected.out" "$temp_root/rejected.err" "$temp_root/receipt.json" "$temp_root/statement.json" "$temp_root/index.json"
  for directory in "$transcripts" "$temp_root/statement-body" "$temp_root/statement-extra" "$temp_root/index-body"; do
    rm -f "$directory/controller.json" "$directory/observer.json" "$directory/runner.json" "$directory/validator.json" "$directory/receipt.json" "$directory/statement.json" "$directory/index.json"
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
python3 -I "$root/scripts/eval/build_memory_temporal_owned_lab_nonupgrading_audit_index_s21b_a12.py" "$temp_root/statement.json" >"$temp_root/index.json"
python3 -I "$root/scripts/eval/check_memory_temporal_owned_lab_nonupgrading_audit_index_s21b_a12.py" "$temp_root/statement.json" "$temp_root/index.json"

expect_builder_rejected() {
  local mutation="$1"
  set +e
  python3 -I "$root/scripts/eval/build_memory_temporal_owned_lab_nonupgrading_audit_index_s21b_a12.py" "$temp_root/$mutation/statement.json" >"$temp_root/rejected.out" 2>"$temp_root/rejected.err"
  local status=$?
  set -e
  test "$status" -eq 65
  test ! -s "$temp_root/rejected.out"
  test "$(cat "$temp_root/rejected.err")" = "S21B_A12_NONUPGRADING_AUDIT_INDEX_REJECTED"
}

for mutation in statement-body statement-extra index-body; do
  mkdir "$temp_root/$mutation"
  cp "$temp_root/statement.json" "$temp_root/$mutation/statement.json"
  cp "$temp_root/index.json" "$temp_root/$mutation/index.json"
done
sed -i 's/"test_only":true/"test_only":false/' "$temp_root/statement-body/statement.json"
sed -i 's/}$/,"execution_capability_present":true}/' "$temp_root/statement-extra/statement.json"
sed -i 's/"execution_capability_present":false/"execution_capability_present":true/' "$temp_root/index-body/index.json"
expect_builder_rejected statement-body
expect_builder_rejected statement-extra
set +e
python3 -I "$root/scripts/eval/check_memory_temporal_owned_lab_nonupgrading_audit_index_s21b_a12.py" "$temp_root/index-body/statement.json" "$temp_root/index-body/index.json" >"$temp_root/rejected.out" 2>"$temp_root/rejected.err"
status=$?
set -e
test "$status" -ne 0
