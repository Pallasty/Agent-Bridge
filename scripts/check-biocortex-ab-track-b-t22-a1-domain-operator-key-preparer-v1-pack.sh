#!/usr/bin/env bash
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
output="$(python3 "$root/scripts/eval/check_biocortex_ab_track_b_t22_a1_domain_operator_key_preparer_v1_pack.py")"
printf '%s\n' "$output"
grep -Fqx $'t22_a1_domain_operator_key_preparer_check\tpass' <<<"$output"
grep -Fqx $'synthetic_dedicated_domain_key_success_count\t1' <<<"$output"
grep -Fqx $'directed_negative_test_count\t6' <<<"$output"
grep -Fqx $'real_key_items_created\t0' <<<"$output"
grep -Fqx $'stable_host_identity_read\tfalse' <<<"$output"
grep -Fqx $'ambient_or_existing_credentials_accessed\tfalse' <<<"$output"
grep -Fqx $'network_accessed\tfalse' <<<"$output"
grep -Fqx $'external_hosts_contacted\t0' <<<"$output"
grep -Fqx $'services_started\t0' <<<"$output"
grep -Fqx $'faults_injected\t0' <<<"$output"
grep -Fqx $'production_admissible\tfalse' <<<"$output"
printf 't22_a1_domain_operator_key_preparer_gate pass\n'
