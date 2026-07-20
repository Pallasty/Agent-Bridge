#!/usr/bin/env bash
set -euo pipefail
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"; temp_root="$(mktemp -d)"
cleanup(){ rm -f "$temp_root/packet.json" "$temp_root/statement.json" "$temp_root/same-subject.json" "$temp_root/accepted.json" "$temp_root/rejected.out" "$temp_root/rejected.err"; rmdir "$temp_root" 2>/dev/null || true; }; trap cleanup EXIT
export PYTHONDONTWRITEBYTECODE=1
cp "$root/docs/design/fixtures/biocortex-ab-track-b-owned-lab-independent-review-synthetic-s21b-a17-v0.json" "$temp_root/packet.json"
python3 -I "$root/scripts/eval/verify_memory_temporal_owned_lab_independent_review_s21b_a17.py" "$temp_root/packet.json" >"$temp_root/statement.json"
python3 -I "$root/scripts/eval/check_memory_temporal_owned_lab_independent_review_s21b_a17.py" "$temp_root/packet.json" "$temp_root/statement.json"
sed 's/"subject_identity_sha256":"b\{64\}"/"subject_identity_sha256":"a\{64\}"/' "$temp_root/packet.json" >"$temp_root/same-subject.json"
set +e
python3 -I "$root/scripts/eval/verify_memory_temporal_owned_lab_independent_review_s21b_a17.py" "$temp_root/same-subject.json" >"$temp_root/rejected.out" 2>"$temp_root/rejected.err"; status=$?
set -e
test "$status" -eq 65; test ! -s "$temp_root/rejected.out"; test "$(cat "$temp_root/rejected.err")" = "S21B_A17_INDEPENDENT_REVIEW_REJECTED"
sed 's/"accepted_for_capability_change":false/"accepted_for_capability_change":true/' "$temp_root/packet.json" >"$temp_root/accepted.json"
set +e
python3 -I "$root/scripts/eval/verify_memory_temporal_owned_lab_independent_review_s21b_a17.py" "$temp_root/accepted.json" >"$temp_root/rejected.out" 2>"$temp_root/rejected.err"; status=$?
set -e
test "$status" -eq 65; test ! -s "$temp_root/rejected.out"
