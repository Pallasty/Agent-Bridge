#!/usr/bin/env bash
set -euo pipefail
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"; tmp="$(mktemp -d /tmp/s21b-a19.XXXXXX)"
cleanup(){ rm -f "$tmp/packet.json" "$tmp/statement.json" "$tmp/mut.json" "$tmp/out" "$tmp/err"; rmdir "$tmp" 2>/dev/null || true; }; trap cleanup EXIT
export PYTHONDONTWRITEBYTECODE=1
cp "$root/docs/design/fixtures/biocortex-ab-track-b-owned-lab-fresh-revocation-clearance-synthetic-s21b-a19-v0.json" "$tmp/packet.json"
python3 -I "$root/scripts/eval/verify_memory_temporal_owned_lab_fresh_revocation_clearance_s21b_a19.py" "$tmp/packet.json" >"$tmp/statement.json"
python3 -I "$root/scripts/eval/check_memory_temporal_owned_lab_fresh_revocation_clearance_s21b_a19.py" "$tmp/packet.json" "$tmp/statement.json"
for expr in 's/"freshness_state":"STALE"/"freshness_state":"FRESH"/' 's/"revocation_state":"NOT_CLEARED"/"revocation_state":"CLEARED"/' 's/"instantiation_allowed":false/"instantiation_allowed":true/' 's/"request_instance_issued":false/"request_instance_issued":true/'; do
 sed "$expr" "$tmp/packet.json" >"$tmp/mut.json"
 if python3 -I "$root/scripts/eval/verify_memory_temporal_owned_lab_fresh_revocation_clearance_s21b_a19.py" "$tmp/mut.json" >"$tmp/out" 2>"$tmp/err"; then exit 1; fi
 test ! -s "$tmp/out"; test "$(cat "$tmp/err")" = "S21B_A19_FRESH_REVOCATION_CLEARANCE_REJECTED"
done
printf 'S21B_A19_FRESH_REVOCATION_CLEARANCE_GATE\tPASS\n'
