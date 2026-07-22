#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
actual=$(mktemp); trap 'rm -f "$actual"' EXIT
python3 scripts/eval/biocortex_ab_track_b_t21_terminal_governance_offline_application_audit_v1.py >"$actual"
grep -q $'^status\tPASS_OFFLINE_APPLICATIONS_ONLY$' "$actual"
grep -q $'^covered_unit_count\t20$' "$actual"
grep -q $'^real_production_control\tfalse$' "$actual"
grep -q $'^downstream_execution\tfalse$' "$actual"
python3 scripts/eval/check_biocortex_ab_track_b_t21_terminal_governance_offline_application_audit_v1_pack.py
printf 't21_terminal_governance_offline_application_audit_gate\tpass\n'
