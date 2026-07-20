#!/usr/bin/env bash
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
tmp="$(mktemp -d /tmp/s21b-a18-crosscheck.XXXXXX)"
cleanup() {
  rm -f "$tmp/audit.json" "$tmp/register.json" "$tmp/templates.json" "$tmp/matrix.json" \
    "$tmp/review.json" "$tmp/statement.json" "$tmp/matrix-mut.json" "$tmp/review-mut.json" \
    "$tmp/out" "$tmp/err"
  rmdir "$tmp" 2>/dev/null || true
}
trap cleanup EXIT
export PYTHONDONTWRITEBYTECODE=1

python3 -I "$root/scripts/eval/build_memory_temporal_owned_lab_static_reachability_audit_s21b_a13.py" >"$tmp/audit.json"
python3 -I "$root/scripts/eval/build_memory_temporal_owned_lab_proof_boundary_s21b_a14.py" "$tmp/audit.json" >"$tmp/register.json"
python3 -I "$root/scripts/eval/build_memory_temporal_owned_lab_evidence_request_templates_s21b_a15.py" "$tmp/register.json" >"$tmp/templates.json"
python3 -I "$root/scripts/eval/build_memory_temporal_owned_lab_request_instantiation_preconditions_s21b_a16.py" "$tmp/templates.json" >"$tmp/matrix.json"
cp "$root/docs/design/fixtures/biocortex-ab-track-b-owned-lab-independent-review-synthetic-s21b-a17-v0.json" "$tmp/review.json"

python3 -I "$root/scripts/eval/verify_memory_temporal_owned_lab_review_precondition_crosscheck_s21b_a18.py" "$tmp/matrix.json" "$tmp/review.json" >"$tmp/statement.json"
python3 -I "$root/scripts/eval/check_memory_temporal_owned_lab_review_precondition_crosscheck_s21b_a18.py" "$tmp/matrix.json" "$tmp/statement.json"

sed 's/"instantiation_allowed":false/"instantiation_allowed":true/' "$tmp/matrix.json" >"$tmp/matrix-mut.json"
if python3 -I "$root/scripts/eval/verify_memory_temporal_owned_lab_review_precondition_crosscheck_s21b_a18.py" "$tmp/matrix-mut.json" "$tmp/review.json" >"$tmp/out" 2>"$tmp/err"; then exit 1; fi
test ! -s "$tmp/out"
test "$(cat "$tmp/err")" = "S21B_A18_REVIEW_PRECONDITION_CROSSCHECK_REJECTED"

sed 's/"subject_identity_sha256":"b\{64\}"/"subject_identity_sha256":"a\{64\}"/' "$tmp/review.json" >"$tmp/review-mut.json"
if python3 -I "$root/scripts/eval/verify_memory_temporal_owned_lab_review_precondition_crosscheck_s21b_a18.py" "$tmp/matrix.json" "$tmp/review-mut.json" >"$tmp/out" 2>"$tmp/err"; then exit 1; fi
test ! -s "$tmp/out"
test "$(cat "$tmp/err")" = "S21B_A18_REVIEW_PRECONDITION_CROSSCHECK_REJECTED"

sed 's/"accepted":false/"accepted":true/' "$tmp/review.json" >"$tmp/review-mut.json"
if python3 -I "$root/scripts/eval/verify_memory_temporal_owned_lab_review_precondition_crosscheck_s21b_a18.py" "$tmp/matrix.json" "$tmp/review-mut.json" >"$tmp/out" 2>"$tmp/err"; then exit 1; fi
test ! -s "$tmp/out"
test "$(cat "$tmp/err")" = "S21B_A18_REVIEW_PRECONDITION_CROSSCHECK_REJECTED"

sed 's/"fresh_bindings_all_present":false/"fresh_bindings_all_present":true/' "$tmp/statement.json" >"$tmp/review-mut.json"
if python3 -I "$root/scripts/eval/check_memory_temporal_owned_lab_review_precondition_crosscheck_s21b_a18.py" "$tmp/matrix.json" "$tmp/review-mut.json" >"$tmp/out" 2>"$tmp/err"; then exit 1; fi
test ! -s "$tmp/out"

printf 'S21B_A18_REVIEW_PRECONDITION_CROSSCHECK_GATE\tPASS\n'
