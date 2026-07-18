#!/usr/bin/env bash
set -euo pipefail

repo_root="$(git rev-parse --show-toplevel)"
cd "$repo_root"

implementation="scripts/eval/engram_g1_authenticated_freeze_authority_adapter_isolated_lab.py"
checker="scripts/eval/check_engram_g1_authenticated_freeze_authority_adapter_isolated_lab.py"

bash -n "$0"
python3 -m py_compile "$implementation" "$checker"
python3 "$checker"
