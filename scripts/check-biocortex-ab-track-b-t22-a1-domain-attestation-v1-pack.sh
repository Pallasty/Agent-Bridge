#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
receipt="$(mktemp)"
trap 'rm -f "$receipt"' EXIT
PYTHONDONTWRITEBYTECODE=1 python3 scripts/eval/biocortex_ab_track_b_t22_a1_domain_attestation_v1.py status >"$receipt"
python3 - "$receipt" <<'PY'
import json, sys
x=json.load(open(sys.argv[1]))
assert x["status"]=="BLOCKED_EXACT_THREE_PRIVATE_ATTESTATION_BUNDLE_AND_OWNER_COUNTERSIGNATURE_REQUIRED"
assert x["stable_host_identity_read"] is False
assert x["private_bundle_read"] is False
assert x["credentials_accessed"] is False and x["network_accessed"] is False
assert x["external_hosts_contacted"]==x["services_started"]==x["faults_injected"]==0
assert x["execution_authorized"] is False and x["production_admissible"] is False
PY
PYTHONDONTWRITEBYTECODE=1 python3 scripts/eval/check_biocortex_ab_track_b_t22_a1_domain_attestation_v1_pack.py
printf 't22_a1_domain_attestation_gate\tpass\n'
