#!/usr/bin/env bash
set -euo pipefail

if [[ "$#" -ne 2 || "$1" != "--phase" ]]; then
  echo "usage: $0 --phase precommit|postcommit" >&2
  exit 64
fi
phase="$2"
case "$phase" in
  precommit | postcommit) ;;
  *)
    echo "invalid phase: $phase" >&2
    exit 64
    ;;
esac

repo_root="$(git rev-parse --show-toplevel)"
cd "$repo_root"

validator="scripts/eval/engram_g14_native_sandbox_adapter_preregistration.py"
checker="scripts/eval/check_engram_g14_native_sandbox_adapter_preregistration.py"
contract="scripts/eval/fixtures/engram_g14_native_sandbox_adapter_preregistration_contract_v0.json"
validator_helper="scripts/eval/engram_g1_corpus_design.py"
predecessor_shell="scripts/check-engram-g14-public-synthetic-protocol-harness.sh"
design_base_commit="36d3e8a4f05caa2731dc8224b035e2f1ac4f4d73"
expected_validator_sha256="91587985f1add6d71daf6e07b3b7289d33950f97b18ff810bfe20d7d23a6800c"
expected_checker_sha256="b4227c3559701d458a36053ca9def72c20b71b06735d84a364feb840056f472e"
expected_contract_sha256="075dd9be4f6097e539db62025e6420b9add0efc030c528c065b612a77f5d78e0"
expected_validator_helper_sha256="2a408d64b34605f434377b3c11f71807f6c81068aa7bcba069c8d3a6dc44cb91"
expected_predecessor_shell_sha256="c236e05e22413a0cf0027a2b40e556deec7fb3c6a8319ec04d8c7d7919927425"
scratch="$(mktemp -d)"
cleanup() {
  rm -rf "$scratch"
}
trap cleanup EXIT

bash -n "$0"
python3 -m py_compile "$validator" "$checker"

actual_validator_sha256="$(shasum -a 256 "$validator" | awk '{print $1}')"
actual_checker_sha256="$(shasum -a 256 "$checker" | awk '{print $1}')"
actual_contract_sha256="$(shasum -a 256 "$contract" | awk '{print $1}')"
actual_validator_helper_sha256="$(shasum -a 256 "$validator_helper" | awk '{print $1}')"
actual_predecessor_shell_sha256="$(shasum -a 256 "$predecessor_shell" | awk '{print $1}')"
[[ "$actual_validator_sha256" == "$expected_validator_sha256" ]]
[[ "$actual_checker_sha256" == "$expected_checker_sha256" ]]
[[ "$actual_contract_sha256" == "$expected_contract_sha256" ]]
[[ "$actual_validator_helper_sha256" == "$expected_validator_helper_sha256" ]]
[[ "$actual_predecessor_shell_sha256" == "$expected_predecessor_shell_sha256" ]]

python3 "$validator" validate-contract --contract "$contract" \
  >"$scratch/receipt.1.json"
python3 "$validator" validate-contract --contract "$contract" \
  >"$scratch/receipt.2.json"
cmp "$scratch/receipt.1.json" "$scratch/receipt.2.json"

python3 "$checker"

git merge-base --is-ancestor "$design_base_commit" HEAD
printf '%s\n' \
  "docs/design/ENGRAM_G1_4_NATIVE_SANDBOX_ADAPTER_PREREGISTRATION_2026_07_18.md" \
  "docs/design/ENGRAM_G1_4_NATIVE_SANDBOX_ADAPTER_PREREGISTRATION_RESULT_2026_07_18.md" \
  "scripts/check-engram-g14-native-sandbox-adapter-preregistration.sh" \
  "scripts/eval/README.md" \
  "scripts/eval/check_engram_g14_native_sandbox_adapter_preregistration.py" \
  "scripts/eval/engram_g14_native_sandbox_adapter_preregistration.py" \
  "scripts/eval/fixtures/engram_g14_native_sandbox_adapter_preregistration_contract_v0.json" \
  | LC_ALL=C sort -u >"$scratch/expected-change-scope.txt"

case "$phase" in
  precommit)
    {
      git diff --name-only "$design_base_commit" --
      git ls-files --others --exclude-standard
    } | LC_ALL=C sort -u >"$scratch/actual-change-scope.txt"
    ;;
  postcommit)
    [[ "$(git rev-parse HEAD)" != "$design_base_commit" ]]
    git diff --quiet HEAD --
    git diff --cached --quiet
    [[ -z "$(git ls-files --others --exclude-standard)" ]]
    git diff --name-only "$design_base_commit" HEAD -- \
      | LC_ALL=C sort -u >"$scratch/actual-change-scope.txt"
    ;;
esac
cmp "$scratch/expected-change-scope.txt" "$scratch/actual-change-scope.txt"

if rg -n \
  'engram_g14_native_sandbox_adapter|PUBLIC_SYNTHETIC_NATIVE_SANDBOX_ADAPTER_KAT' \
  crates >"$scratch/runtime-surface.txt"; then
  cat "$scratch/runtime-surface.txt" >&2
  echo "G1.4 native-adapter preregistration leaked into runtime crates" >&2
  exit 1
fi

echo "engram G1.4 native sandbox adapter preregistration: VALIDATED (design only; no authority; phase=$phase)"
