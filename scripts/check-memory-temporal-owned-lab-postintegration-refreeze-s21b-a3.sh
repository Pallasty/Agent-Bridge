#!/usr/bin/env bash
set -euo pipefail
umask 077
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
EVAL="$ROOT/scripts/eval/check_memory_temporal_owned_lab_postintegration_refreeze_s21b_a3.py"
EXPECTED="$ROOT/scripts/eval/expected-memory-temporal-owned-lab-postintegration-refreeze-s21b-a3.tsv"
actual="$(mktemp)"
trap 'rm -f "$actual"' EXIT
python3 -I "$EVAL" >"$actual"
cmp -s "$actual" "$EXPECTED"
printf 'S21B_A3_STATIC_GATE\tPASS\n'
