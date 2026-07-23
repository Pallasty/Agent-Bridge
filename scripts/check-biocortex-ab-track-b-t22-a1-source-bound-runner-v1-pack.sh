#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

python3 scripts/eval/check_biocortex_ab_track_b_t22_a1_source_bound_runner_v1_pack.py
printf '%s\n' 't22_a1_source_bound_runner_gate pass'
