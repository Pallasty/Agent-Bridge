#!/usr/bin/env bash
set -euo pipefail

repo_root="$(git rev-parse --show-toplevel)"
cd "$repo_root"

base="${1:-${GOVERNANCE_BASE_SHA:-}}"
head="${2:-HEAD}"
if [[ -z "$base" ]]; then
  echo "usage: $0 <base-ref> [head-ref]" >&2
  echo "or set GOVERNANCE_BASE_SHA" >&2
  exit 2
fi

python3 scripts/eval/cli_composition_root_governance.py self-test
python3 -m unittest discover -s tests -p test_cli_composition_root_governance.py
python3 -m unittest discover -s tests -p test_cli_governance_evidence.py
python3 -m unittest discover -s tests -p test_cli_governance_live.py
python3 scripts/eval/cli_composition_root_governance.py validate \
  --base "$base" \
  --head "$head"

# Read revision-bound evidence; actual behavior execution is explicit or pre-commit.
python3 scripts/eval/cli_governance_evidence.py --base "$base" --head "$head"
