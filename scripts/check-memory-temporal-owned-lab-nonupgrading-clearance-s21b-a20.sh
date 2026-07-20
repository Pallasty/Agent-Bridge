#!/usr/bin/env bash
set -euo pipefail
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"; tmp="$(mktemp -d /tmp/s21b-a20.XXXXXX)"
cleanup(){ rm -f "$tmp/packet.json" "$tmp/statement.json" "$tmp/mut.json" "$tmp/out" "$tmp/err"; rmdir "$tmp" 2>/dev/null || true; }; trap cleanup EXIT
export PYTHONDONTWRITEBYTECODE=1
cp "$root/docs/design/fixtures/biocortex-ab-track-b-owned-lab-nonupgrading-clearance-synthetic-s21b-a20-v0.json" "$tmp/packet.json"
python3 -I "$root/scripts/eval/verify_memory_temporal_owned_lab_nonupgrading_clearance_s21b_a20.py" "$tmp/packet.json" >"$tmp/statement.json"
python3 -I "$root/scripts/eval/check_memory_temporal_owned_lab_nonupgrading_clearance_s21b_a20.py" "$tmp/packet.json" "$tmp/statement.json"
for expr in 's/"execution_capability_present":false/"execution_capability_present":true/' 's/"owner_authority_present":false/"owner_authority_present":true/' 's/"request_instance_issued":false/"request_instance_issued":true/' 's/"instantiation_allowed":false/"instantiation_allowed":true/' 's/"accepted_for_capability_change":false/"accepted_for_capability_change":true/'; do
 sed "$expr" "$tmp/packet.json" >"$tmp/mut.json"
 if python3 -I "$root/scripts/eval/verify_memory_temporal_owned_lab_nonupgrading_clearance_s21b_a20.py" "$tmp/mut.json" >"$tmp/out" 2>"$tmp/err"; then exit 1; fi
 test ! -s "$tmp/out"; test "$(cat "$tmp/err")" = "S21B_A20_NONUPGRADING_CLEARANCE_REJECTED"
done
printf 'S21B_A20_NONUPGRADING_CLEARANCE_GATE\tPASS\n'
