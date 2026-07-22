#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
status="$(python3 scripts/eval/biocortex_ab_track_b_t22_a0_real_process_runner_v1.py status)"
python3 - "$status" <<'PY'
import json, sys
from pathlib import Path
x = json.loads(sys.argv[1])
tools_present = Path("/Data/CascadeProjects/.artifacts/agent-bridge/biocortex-track-b-t22-a0-real-lab/tools/acquisition-receipt.json").is_file()
assert x == {
    "schema": "agent_bridge.biocortex.track_b.t22_a0.real_process_runner_status.v1",
    "status": "BLOCKED_EXACT_SIGNED_PAYLOAD_AND_SOURCE_BOUND_TOOL_RECEIPT_REQUIRED" if tools_present else "BLOCKED_EXACT_SIGNED_PAYLOAD_AND_PINNED_TOOLS_REQUIRED",
    "proposal_sha256": "854862a6dd71935590ef0f01072b25dd289221b296c7979964afa7155faaa92b",
    "execution_contract_sha256": "f84fe9ea9d8948afa7eca516f486bb40d690acfd19437a7b3469af8c4dc37616",
    "owner_trust_anchor_present": True,
    "owner_trust_anchor_valid": True,
    "owner_signature_verified": False,
    "pinned_tools_present": tools_present,
    "network_attempted": False,
    "processes_started": 0,
    "faults_injected": 0,
    "real_evidence_items_created": 0,
    "production_admissible": False,
}
PY
python3 scripts/eval/check_biocortex_ab_track_b_t22_a0_real_process_runner_v1_pack.py
printf 't22_a0_real_process_runner_gate\tpass\n'
