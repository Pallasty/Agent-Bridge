#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
status="$(python3 scripts/eval/biocortex_ab_track_b_t22_a0_acquire_pinned_tools_v1.py status)"
python3 - "$status" <<'PY'
import json, sys
x = json.loads(sys.argv[1])
assert x == {
    "schema": "agent_bridge.biocortex.track_b.t22_a0.pinned_tool_acquisition_status.v1",
    "status": "BLOCKED_EXACT_OWNER_SIGNATURE_REQUIRED",
    "pins_sha256": "c5f1d79dc232b1de6be2a3f4f190bd4adf4fb10425529dff1ad94747402b7dc7",
    "tool_versions": {"etcd": "3.7.0", "openbao": "2.6.0", "toxiproxy": "2.12.0"},
    "network_attempted": False,
    "owner_signature_verified": False,
    "release_artifacts_downloaded": False,
    "real_process_execution_authorized": False,
    "production_admissible": False,
}
PY
python3 scripts/eval/check_biocortex_ab_track_b_t22_a0_acquire_pinned_tools_v1_pack.py
printf 't22_a0_pinned_tool_acquisition_gate\tpass\n'
