#!/usr/bin/env bash
set -euo pipefail

repo_root="$(git rev-parse --show-toplevel)"
cd "$repo_root"

implementation="scripts/eval/engram_g14_public_synthetic_business_component_harness.py"
checker="scripts/eval/check_engram_g14_public_synthetic_business_component_harness.py"

bash -n "$0"
python3 -m py_compile "$implementation" "$checker"
python3 "$checker"

if rg -n \
  'engram_g14_public_synthetic_business_component_harness|PUBLIC_SYNTHETIC_BUSINESS_COMPONENT_KAT' \
  crates; then
  echo "business component harness leaked into runtime crates" >&2
  exit 1
fi

echo "engram G1.4 public synthetic business component implementation gate: PASS (no authority)"
