#!/usr/bin/env bash
set -euo pipefail
umask 077
cd "$(dirname "$0")/.."
gate_tmp=$(mktemp -d "${TMPDIR:-/tmp}/ab-s21b-a2.XXXXXX")
trap 'rm -rf "$gate_tmp"' EXIT
python3 -I scripts/eval/check_memory_temporal_owned_lab_subject_rebinding_s21b_a2.py > "$gate_tmp/rows.tsv"
python3 -I scripts/eval/check_memory_temporal_owned_lab_subject_rebinding_s21b_a2.py --self-test > "$gate_tmp/self.tsv"
cmp -s "$gate_tmp/rows.tsv" "$gate_tmp/self.tsv"
cmp -s "$gate_tmp/rows.tsv" scripts/eval/fixtures/memory_temporal_owned_lab_subject_rebinding_s21b_a2.expected.v0.tsv
cat "$gate_tmp/rows.tsv"
