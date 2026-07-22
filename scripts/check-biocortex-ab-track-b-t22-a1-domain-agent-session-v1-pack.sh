#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
receipt="$(mktemp)"
trap 'rm -f "$receipt"' EXIT
PYTHONDONTWRITEBYTECODE=1 python3 scripts/eval/biocortex_ab_track_b_t22_a1_domain_agent_session_v1.py >"$receipt"
python3 - "$receipt" <<'PY'
import json, sys
x=json.load(open(sys.argv[1]))
assert x["status"]=="OFFLINE_AGENT_SESSION_CORE_READY_REAL_RUNTIME_INPUTS_AND_OWNER_EXECUTION_SIGNATURE_REQUIRED"
assert x["message_instances_read"] is False
assert x["public_keys_read"] is False and x["private_keys_read"] is False
assert x["credential_manifest_read"] is False and x["credential_files_read"] is False
assert x["network_accessed"] is False and x["listeners_started"]==0
assert x["commands_executed"]==x["services_started"]==x["faults_injected"]==0
assert x["execution_authorized"] is False and x["production_admissible"] is False
PY
PYTHONDONTWRITEBYTECODE=1 python3 scripts/eval/check_biocortex_ab_track_b_t22_a1_domain_agent_session_v1_pack.py
printf 't22_a1_domain_agent_session_gate\tpass\n'
