#!/usr/bin/env bash
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
output="$(python3 "$root/scripts/eval/check_biocortex_ab_track_b_t22_a1_authenticated_domain_lane_v1_pack.py")"
printf '%s\n' "$output"
grep -Fqx $'t22_a1_authenticated_domain_lane_check\tpass' <<<"$output"
grep -Fqx $'signed_fixed_command_roundtrip_count\t23' <<<"$output"
grep -Fqx $'memory_only_bootstrap_publish_count\t1' <<<"$output"
grep -Fqx $'memory_only_bootstrap_consume_count\t3' <<<"$output"
grep -Fqx $'signed_emergency_cleanup_count\t1' <<<"$output"
grep -Fqx $'kat_exact_evidence_finalization_count\t1' <<<"$output"
grep -Fqx $'kat_atomic_evidence_file_count\t65' <<<"$output"
grep -Fqx $'directed_negative_test_count\t9' <<<"$output"
grep -Fqx $'real_private_inputs_read\t0' <<<"$output"
grep -Fqx $'real_certificate_or_key_files_read\t0' <<<"$output"
grep -Fqx $'network_accessed\tfalse' <<<"$output"
grep -Fqx $'listeners_started\t0' <<<"$output"
grep -Fqx $'service_processes_started\t0' <<<"$output"
grep -Fqx $'faults_injected\t0' <<<"$output"
grep -Fqx $'secret_frames_persisted\t0' <<<"$output"
grep -Fqx $'production_admissible\tfalse' <<<"$output"
printf 't22_a1_authenticated_domain_lane_gate pass\n'
