#!/usr/bin/env bash
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
output="$(python3 "$root/scripts/eval/check_biocortex_ab_track_b_t22_a1_exact_evidence_finalizer_v1_pack.py")"
printf '%s\n' "$output"
grep -Fqx $'t22_a1_exact_evidence_finalizer_check\tpass' <<<"$output"
grep -Fqx $'synthetic_exact_transcript_command_count\t23' <<<"$output"
grep -Fqx $'directed_negative_test_count\t6' <<<"$output"
grep -Fqx $'early_failure_secret_zeroization_count\t1' <<<"$output"
grep -Fqx $'single_attempt_rejection_count\t1' <<<"$output"
grep -Fqx $'real_private_inputs_read\t0' <<<"$output"
grep -Fqx $'persistent_evidence_sets_created\t0' <<<"$output"
grep -Fqx $'network_accessed\tfalse' <<<"$output"
grep -Fqx $'listeners_started\t0' <<<"$output"
grep -Fqx $'processes_started\t0' <<<"$output"
grep -Fqx $'faults_injected\t0' <<<"$output"
grep -Fqx $'production_admissible\tfalse' <<<"$output"
printf 't22_a1_exact_evidence_finalizer_gate pass\n'
