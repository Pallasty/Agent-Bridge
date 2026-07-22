#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
receipt="$(mktemp)"
trap 'rm -f "$receipt"' EXIT
PYTHONDONTWRITEBYTECODE=1 python3 scripts/eval/biocortex_ab_track_b_t22_a1_private_runtime_contracts_v1.py >"$receipt"
python3 - "$receipt" <<'PY'
import json, sys
x=json.load(open(sys.argv[1]))
assert x["status"]=="PRIVATE_RUNTIME_SCHEMAS_READY_REAL_MANIFESTS_AND_OWNER_EXECUTION_SIGNATURE_REQUIRED"
assert x["private_manifest_instances_read"] is False
assert x["credential_files_read"] is False and x["ambient_credentials_accessed"] is False
assert x["network_accessed"] is False
assert x["listeners_started"]==x["external_hosts_contacted"]==0
assert x["services_started"]==x["faults_injected"]==0
assert x["execution_authorized"] is False and x["production_admissible"] is False
PY
PYTHONDONTWRITEBYTECODE=1 python3 scripts/eval/check_biocortex_ab_track_b_t22_a1_private_runtime_contracts_v1_pack.py
printf 't22_a1_private_runtime_contracts_gate\tpass\n'
