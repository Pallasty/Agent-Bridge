#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
PYTHONDONTWRITEBYTECODE=1 python3 scripts/eval/check_biocortex_ab_track_b_t22_a1_distributed_contract_schemas_v1_pack.py
printf 't22_a1_distributed_contract_schemas_gate\tpass\n'
