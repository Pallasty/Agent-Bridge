#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
receipt="$(mktemp)"
trap 'rm -f "$receipt"' EXIT
python3 scripts/eval/biocortex_ab_track_b_t22_a0_real_lab_preflight_v1.py >"$receipt"
python3 - "$receipt" <<'PY'
import json, sys
x=json.load(open(sys.argv[1]))
assert x["status"]=="BLOCKED_OWNER_SIGNATURE_AND_PINNED_TOOLS_REQUIRED"
assert x["physical_host_count"]==1
assert x["owner_public_key_bound"] is True
assert x["owner_signature_verified"] is False
assert x["credentials_accessed"] is False and x["network_accessed"] is False
assert x["services_started"]==x["faults_injected"]==x["real_evidence_items_created"]==0
assert x["production_admissible"] is False
PY
python3 scripts/eval/check_biocortex_ab_track_b_t22_a0_real_lab_preflight_v1_pack.py
printf 't22_a0_real_lab_preflight_gate\tpass\n'
