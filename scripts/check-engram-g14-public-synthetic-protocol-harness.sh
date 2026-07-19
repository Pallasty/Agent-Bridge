#!/usr/bin/env bash
set -euo pipefail

repo_root="$(git rev-parse --show-toplevel)"
cd "$repo_root"

implementation="scripts/eval/engram_g14_public_synthetic_protocol_harness.py"
checker="scripts/eval/check_engram_g14_public_synthetic_protocol_harness.py"
contract="scripts/eval/fixtures/engram_g14_public_synthetic_protocol_harness_contract_v0.json"
fixture="scripts/eval/fixtures/engram_g14_public_synthetic_protocol_harness_fixture_v0.json"
expected_implementation_sha256="52cc851419880f93d8585fee1a4378788564bbcadbeb84161d4e40e67c51ed05"
expected_checker_sha256="bc896b9d284cc644be965dcb7fa20ea80ff5629783922ce7b54bfedd3ed9df10"
expected_contract_sha256="6fae57e239594978810d03d2aee33133d3af8439527dd6aadef6884d5bba1b9d"
expected_fixture_sha256="477cf9b326f52fc3f8ce9138346bb55e2692e5b473ac5f0c5d9b24e457350607"
scratch="$(mktemp -d)"
cleanup() {
  rm -rf "$scratch"
}
trap cleanup EXIT

bash -n "$0"
python3 -m py_compile "$implementation" "$checker"

actual_implementation_sha256="$(shasum -a 256 "$implementation" | awk '{print $1}')"
actual_checker_sha256="$(shasum -a 256 "$checker" | awk '{print $1}')"
actual_contract_sha256="$(shasum -a 256 "$contract" | awk '{print $1}')"
actual_fixture_sha256="$(shasum -a 256 "$fixture" | awk '{print $1}')"
[[ "$actual_implementation_sha256" == "$expected_implementation_sha256" ]]
[[ "$actual_checker_sha256" == "$expected_checker_sha256" ]]
[[ "$actual_contract_sha256" == "$expected_contract_sha256" ]]
[[ "$actual_fixture_sha256" == "$expected_fixture_sha256" ]]

python3 "$implementation" validate-contract >"$scratch/contract.1.json"
python3 "$implementation" validate-contract >"$scratch/contract.2.json"
cmp "$scratch/contract.1.json" "$scratch/contract.2.json"

python3 "$implementation" exercise --enable-public-synthetic \
  >"$scratch/exercise.1.json"
python3 "$implementation" exercise --enable-public-synthetic \
  >"$scratch/exercise.2.json"
cmp "$scratch/exercise.1.json" "$scratch/exercise.2.json"

if python3 "$implementation" exercise \
  >"$scratch/default-off.stdout" 2>"$scratch/default-off.stderr"; then
  echo "expected public synthetic harness to remain default-off" >&2
  exit 1
fi
grep -q "E_DEFAULT_OFF" "$scratch/default-off.stderr"

python3 "$checker"

if rg -n \
  'engram_g14_public_synthetic_protocol_harness|PUBLIC_SYNTHETIC_PROTOCOL_KAT' \
  crates >"$scratch/runtime-surface.txt"; then
  cat "$scratch/runtime-surface.txt" >&2
  echo "G1.4 public synthetic harness leaked into runtime crates" >&2
  exit 1
fi

echo "engram G1.4 public synthetic protocol harness: PASS (no authority)"
