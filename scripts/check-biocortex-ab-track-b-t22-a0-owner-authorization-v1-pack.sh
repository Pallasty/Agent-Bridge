#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
status="$(python3 scripts/eval/biocortex_ab_track_b_t22_a0_owner_authorization_v1.py status)"
python3 - "$status" <<'PY'
import json, sys
x=json.loads(sys.argv[1])
assert x=={"schema":"agent_bridge.biocortex.track_b.t22_a0.owner_authorization_status.v0","status":"BLOCKED_OWNER_TRUST_ANCHOR_REQUIRED","owner_trust_anchor_present":False,"owner_trust_anchor_valid":False,"owner_signature_verified":False,"real_process_execution_authorized":False}
PY
python3 scripts/eval/check_biocortex_ab_track_b_t22_a0_owner_authorization_v1_pack.py
printf 't22_a0_owner_authorization_gate\tpass\n'
