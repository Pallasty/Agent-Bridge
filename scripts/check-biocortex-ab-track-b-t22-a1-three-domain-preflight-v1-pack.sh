#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
receipt="$(mktemp)"
trap 'rm -f "$receipt"' EXIT
PYTHONDONTWRITEBYTECODE=1 python3 scripts/eval/biocortex_ab_track_b_t22_a1_three_domain_preflight_v1.py >"$receipt"
python3 - "$receipt" <<'PY'
import json, sys
x=json.load(open(sys.argv[1]))
assert x["status"]=="BLOCKED_REMOTE_ATTESTATIONS_THIRD_DOMAIN_MODE_ENDPOINT_SET_AND_EXACT_OWNER_DECISION_REQUIRED"
assert x["local_coordinator_observed"] is True
assert x["stable_host_identity_read"] is False
assert x["required_domain_count"]==3 and x["current_validated_domain_count"]==1
assert x["missing_current_domain_attestation_count"]==2
assert x["known_distinct_physical_host_candidate_upper_bound"]==2
assert x["aio2_and_tb14_counted_as_one_domain"] is True
assert x["alias_equivalence_is_physical_proof"] is False
assert x["credentials_accessed"] is False and x["network_accessed"] is False
assert x["external_hosts_contacted"]==x["provider_apis_accessed"]==0
assert x["spend_usd"]==x["services_started"]==x["faults_injected"]==0
assert x["public_transparency_entries_created"]==0
assert x["three_failure_domain_evidence"] is False
assert x["external_anti_rollback_evidence"] is False
assert x["production_admissible"] is False
PY
PYTHONDONTWRITEBYTECODE=1 python3 scripts/eval/check_biocortex_ab_track_b_t22_a1_three_domain_preflight_v1_pack.py
printf 't22_a1_three_domain_preflight_gate\tpass\n'
