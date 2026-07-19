#!/usr/bin/env bash
set -euo pipefail

task_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
cd "$task_root"
mode="${1:---source-fast}"
case "$mode" in --source-fast|--full) ;; *) exit 64 ;; esac

check_py="scripts/eval/check_biocortex_ab_track_b_reference_provider_fault_injection_runner_clock_skew_synthetic_exact_t10_receipt_track_validation_reference_time_decision_recheck_reference_time_and_maximum_clock_skew_seconds_verifier_isolated_lab_v1_pack.py"
expected="scripts/eval/fixtures/biocortex_ab_track_b_reference_provider_fault_injection_runner_clock_skew_synthetic_exact_t10_receipt_track_validation_reference_time_decision_recheck_reference_time_and_maximum_clock_skew_seconds_verifier_isolated_lab_v1_pack.expected.v0.tsv"
manifest="scripts/eval/fixtures/biocortex_ab_track_b_reference_provider_fault_injection_runner_clock_skew_synthetic_exact_t10_receipt_track_validation_reference_time_decision_recheck_reference_time_and_maximum_clock_skew_seconds_verifier_isolated_lab_v1_pack_v0.json"
baseline="66f4754fd871169f50f345e5c023c94466f8ffd4"

test "$(git rev-parse HEAD^)" = "$baseline"
git diff --no-index -- "$expected" <(PYTHONDONTWRITEBYTECODE=1 python3 "$check_py")
PYTHONDONTWRITEBYTECODE=1 python3 "$check_py" --self-test >/dev/null
jq -e '.authority.effective_state_at_source_baseline=="AUTHORIZED_T11_CLOCK_SKEW_ISOLATED_LAB_EXACT_UNIT" and .expected.public_input_count==16 and .expected.directed_negative_test_count==99 and .boundary.t11_clock_skew_implemented_after_integrated_full==true and .boundary.t12_owner_toctou_implemented==false' "$manifest" >/dev/null
while IFS=$'\t' read -r path hash; do
  test "$(sha256sum "$path" | awk '{print $1}')" = "$hash"
done < <(jq -r '.raw_sha256|to_entries[]|"\(.key)\t\(.value)"' "$manifest")
while IFS=$'\t' read -r path expected_mode; do
  test "$(git ls-files -s -- "$path" | awk '{print $1}')" = "$expected_mode"
done < <(jq -r '.packet_path_modes|to_entries[]|"\(.key)\t\(.value)"' "$manifest")

if [ "$mode" = "--full" ]; then
  set -- $(git rev-list --parents -n 1 HEAD)
  test "$#" -eq 3
  test "$3" = "$baseline" || test "$2" = "$baseline"
fi
printf 't11_clock_skew_gate\tpass\n'

