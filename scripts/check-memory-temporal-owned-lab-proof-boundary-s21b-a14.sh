#!/usr/bin/env bash
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
temp_root="$(mktemp -d)"
cleanup() {
  rm -f "$temp_root/audit.json" "$temp_root/register.json" "$temp_root/tampered-audit.json" "$temp_root/tampered-register.json" "$temp_root/rejected.out" "$temp_root/rejected.err"
  rmdir "$temp_root" 2>/dev/null || true
}
trap cleanup EXIT

export PYTHONDONTWRITEBYTECODE=1
python3 -I "$root/scripts/eval/build_memory_temporal_owned_lab_static_reachability_audit_s21b_a13.py" >"$temp_root/audit.json"
python3 -I "$root/scripts/eval/build_memory_temporal_owned_lab_proof_boundary_s21b_a14.py" "$temp_root/audit.json" >"$temp_root/register.json"
python3 -I "$root/scripts/eval/check_memory_temporal_owned_lab_proof_boundary_s21b_a14.py" "$temp_root/audit.json" "$temp_root/register.json"

sed 's/"owner_authority_reachable":false/"owner_authority_reachable":true/' "$temp_root/audit.json" >"$temp_root/tampered-audit.json"
set +e
python3 -I "$root/scripts/eval/build_memory_temporal_owned_lab_proof_boundary_s21b_a14.py" "$temp_root/tampered-audit.json" >"$temp_root/rejected.out" 2>"$temp_root/rejected.err"
status=$?
set -e
test "$status" -eq 65
test ! -s "$temp_root/rejected.out"
test "$(cat "$temp_root/rejected.err")" = "S21B_A14_PROOF_BOUNDARY_REGISTER_REJECTED"

sed 's/"UNPROVEN_REQUIRED_FOR_CAPABILITY_CHANGE"/"SATISFIED"/' "$temp_root/register.json" >"$temp_root/tampered-register.json"
set +e
python3 -I "$root/scripts/eval/check_memory_temporal_owned_lab_proof_boundary_s21b_a14.py" "$temp_root/audit.json" "$temp_root/tampered-register.json" >"$temp_root/rejected.out" 2>"$temp_root/rejected.err"
status=$?
set -e
test "$status" -ne 0
test ! -s "$temp_root/rejected.out"
