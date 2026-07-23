#!/usr/bin/env bash
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
output="$(python3 "$root/scripts/eval/check_biocortex_ab_track_b_t22_a1_exact_launch_binding_v1_pack.py")"
printf '%s\n' "$output"
grep -Fqx $'t22_a1_exact_launch_binding_check\tpass' <<<"$output"
grep -Fqx $'synthetic_exact_readiness_signature_reverification_count\t1' <<<"$output"
grep -Fqx $'synthetic_domain_reservation_before_listener_count\t1' <<<"$output"
grep -Fqx $'synthetic_coordinator_post_reservation_lazy_load_count\t1' <<<"$output"
grep -Fqx $'directed_negative_test_count\t6' <<<"$output"
grep -Fqx $'real_private_inputs_read\t0' <<<"$output"
grep -Fqx $'credential_files_read\t0' <<<"$output"
grep -Fqx $'network_accessed\tfalse' <<<"$output"
grep -Fqx $'listeners_started\t0' <<<"$output"
grep -Fqx $'processes_started\t0' <<<"$output"
grep -Fqx $'faults_injected\t0' <<<"$output"
grep -Fqx $'production_admissible\tfalse' <<<"$output"
printf 't22_a1_exact_launch_binding_gate pass\n'
