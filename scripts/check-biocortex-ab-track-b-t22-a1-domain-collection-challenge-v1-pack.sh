#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
receipt="$(mktemp)"
trap 'rm -f "$receipt"' EXIT
PYTHONDONTWRITEBYTECODE=1 python3 scripts/eval/biocortex_ab_track_b_t22_a1_domain_collection_challenge_v1.py status >"$receipt"
python3 - "$receipt" <<'PY'
import json, sys
x=json.load(open(sys.argv[1]))
assert x["status"]=="BLOCKED_T22_A1_OWNER_TRUST_ANCHOR_REQUIRED"
assert x["owner_trust_anchor_present"] is False
assert x["stable_host_identity_read"] is False
assert x["credentials_accessed"] is False and x["network_accessed"] is False
assert x["external_hosts_contacted"]==x["services_started"]==x["faults_injected"]==0
assert x["attestation_items_created"]==0
assert x["execution_authorized"] is False and x["production_admissible"] is False
PY
PYTHONDONTWRITEBYTECODE=1 python3 scripts/eval/check_biocortex_ab_track_b_t22_a1_domain_collection_challenge_v1_pack.py
printf 't22_a1_domain_collection_challenge_gate\tpass\n'
