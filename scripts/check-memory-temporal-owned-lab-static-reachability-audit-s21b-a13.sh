#!/usr/bin/env bash
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
temp_root="$(mktemp -d)"
cleanup() {
  rm -f "$temp_root/audit.json" "$temp_root/tampered-audit.json" "$temp_root/unexpected.out" "$temp_root/unexpected.err"
  rmdir "$temp_root" 2>/dev/null || true
}
trap cleanup EXIT

export PYTHONDONTWRITEBYTECODE=1
python3 -I "$root/scripts/eval/build_memory_temporal_owned_lab_static_reachability_audit_s21b_a13.py" >"$temp_root/audit.json"
python3 -I "$root/scripts/eval/check_memory_temporal_owned_lab_static_reachability_audit_s21b_a13.py" "$temp_root/audit.json"

sed 's/"execution_capability_reachable":false/"execution_capability_reachable":true/' "$temp_root/audit.json" >"$temp_root/tampered-audit.json"
set +e
python3 -I "$root/scripts/eval/check_memory_temporal_owned_lab_static_reachability_audit_s21b_a13.py" "$temp_root/tampered-audit.json" >"$temp_root/unexpected.out" 2>"$temp_root/unexpected.err"
status=$?
set -e
test "$status" -ne 0
test ! -s "$temp_root/unexpected.out"
