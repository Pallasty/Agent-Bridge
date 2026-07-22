#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
receipt="$(mktemp)"
trap 'rm -f "$receipt"' EXIT
PYTHONDONTWRITEBYTECODE=1 python3 scripts/eval/biocortex_ab_track_b_t22_a1_runtime_material_preparer_v1.py status >"$receipt"
python3 - "$receipt" <<'PY'
import json, sys
x=json.load(open(sys.argv[1]))
assert x["status"]=="BLOCKED_T22_A1_OWNER_TRUST_ANCHOR_REQUIRED"
assert x["owner_trust_anchor_present"] is False and x["owner_trust_anchor_valid"] is False
assert x["private_endpoint_manifest_instance_read"] is False
assert x["runtime_credential_files_read"] is False and x["runtime_material_generated"] is False
assert x["ambient_or_preexisting_credentials_accessed"] is False
assert x["network_accessed"] is False
assert x["external_hosts_contacted"]==x["listeners_started"]==0
assert x["services_started"]==x["faults_injected"]==x["spend_usd_cents"]==0
assert x["execution_authorized"] is False and x["production_admissible"] is False
PY
PYTHONDONTWRITEBYTECODE=1 python3 scripts/eval/check_biocortex_ab_track_b_t22_a1_runtime_material_preparer_v1_pack.py
printf 't22_a1_runtime_material_preparer_gate\tpass\n'
