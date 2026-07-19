#!/usr/bin/env bash
set -euo pipefail
export PYTHONDONTWRITEBYTECODE=1

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

assert_no_python_cache() {
  local residue
  residue="$(find . -path './.git' -prune -o \( -type d -name __pycache__ -o -type f -name '*.pyc' \) -print -quit)"
  if [[ -n "$residue" ]]; then
    echo "Python cache residue is forbidden: $residue" >&2
    exit 1
  fi
}

assert_no_python_cache

implementation="scripts/eval/engram_g14_native_sandbox_adapter_kat.py"
checker="scripts/eval/check_engram_g14_native_sandbox_adapter_kat.py"
contract="scripts/eval/fixtures/engram_g14_native_sandbox_adapter_kat_contract_v0.json"
fixture="scripts/eval/fixtures/engram_g14_native_sandbox_adapter_kat_fixture_v0.json"
probe="scripts/eval/fixtures/engram_g14_native_sandbox_adapter_probe_v0.c"
predecessor_contract="scripts/eval/fixtures/engram_g14_native_sandbox_adapter_preregistration_contract_v0.json"
predecessor_validator="scripts/eval/engram_g14_native_sandbox_adapter_preregistration.py"
predecessor_checker="scripts/eval/check_engram_g14_native_sandbox_adapter_preregistration.py"
predecessor_shell="scripts/check-engram-g14-native-sandbox-adapter-preregistration.sh"
integration_base="d677e923442661a1d896185923b244d22b726319"
predecessor_commit="908412b8209056a90b3be5c2f93896c763d31311"

expected_implementation_sha256="1f79379ef480c3f0c21b901b292990460cd330ee2a627082ed2a94b8094e7c1f"
expected_checker_sha256="d20e681f9824d0cd561f9e3d311cfc129aed1a7fe0f24b9eb6a2785fe79ab41e"
expected_contract_sha256="7018486db2dc3f3e751d66547828756e6d61aea91df7b3f12b7bccc9cd78615d"
expected_fixture_sha256="e4e23d1a6aea78ee60047c96f76249137b2c139ced18d6731754dca229b6b239"
expected_probe_sha256="0824beab20f922548f0033910e1ad3eb55695c0bb802488d0e9e531279199d12"
expected_predecessor_contract_sha256="075dd9be4f6097e539db62025e6420b9add0efc030c528c065b612a77f5d78e0"
expected_predecessor_validator_sha256="91587985f1add6d71daf6e07b3b7289d33950f97b18ff810bfe20d7d23a6800c"
expected_predecessor_checker_sha256="b4227c3559701d458a36053ca9def72c20b71b06735d84a364feb840056f472e"
expected_predecessor_shell_sha256="65e49095cd05c5f119a51ee46a57f64b291a264ff224ecf6a1edd3ebbcd3648e"

bash -n "$0"
python3 - "$implementation" "$checker" <<'PY'
import sys
from pathlib import Path

for value in sys.argv[1:]:
    path = Path(value)
    compile(path.read_text(encoding="utf-8"), str(path), "exec")
PY

digest() {
  python3 - "$1" <<'PY'
import hashlib
import sys
from pathlib import Path

print(hashlib.sha256(Path(sys.argv[1]).read_bytes()).hexdigest())
PY
}

[[ "$(digest "$implementation")" == "$expected_implementation_sha256" ]]
[[ "$(digest "$checker")" == "$expected_checker_sha256" ]]
[[ "$(digest "$contract")" == "$expected_contract_sha256" ]]
[[ "$(digest "$fixture")" == "$expected_fixture_sha256" ]]
[[ "$(digest "$probe")" == "$expected_probe_sha256" ]]
[[ "$(digest "$predecessor_contract")" == "$expected_predecessor_contract_sha256" ]]
[[ "$(digest "$predecessor_validator")" == "$expected_predecessor_validator_sha256" ]]
[[ "$(digest "$predecessor_checker")" == "$expected_predecessor_checker_sha256" ]]
[[ "$(digest "$predecessor_shell")" == "$expected_predecessor_shell_sha256" ]]

validation_one="$(python3 "$implementation" validate-artifacts)"
validation_two="$(python3 "$implementation" validate-artifacts)"
[[ "$validation_one" == "$validation_two" ]]
python3 - "$validation_one" <<'PY'
import json
import sys

receipt = json.loads(sys.argv[1])
assert receipt["verdict"] == "VALIDATED_ARTIFACTS_NO_EXECUTION_NO_AUTHORITY"
assert receipt["default_off"] is True
assert receipt["native_adapter_implemented"] is False
assert receipt["g1_4_execution_open"] is False
PY

python3 "$checker"
assert_no_python_cache

git merge-base --is-ancestor "$predecessor_commit" HEAD
git merge-base --is-ancestor "$integration_base" HEAD

expected_change_scope="$(printf '%s\n' \
  "docs/design/ENGRAM_G1_4_NATIVE_SANDBOX_ADAPTER_KAT_2026_07_18.md" \
  "docs/design/ENGRAM_G1_4_NATIVE_SANDBOX_ADAPTER_KAT_RESULT_2026_07_18.md" \
  "scripts/check-engram-g14-native-sandbox-adapter-kat.sh" \
  "scripts/eval/README.md" \
  "scripts/eval/check_engram_g14_native_sandbox_adapter_kat.py" \
  "scripts/eval/engram_g14_native_sandbox_adapter_kat.py" \
  "scripts/eval/fixtures/engram_g14_native_sandbox_adapter_kat_contract_v0.json" \
  "scripts/eval/fixtures/engram_g14_native_sandbox_adapter_kat_fixture_v0.json" \
  "scripts/eval/fixtures/engram_g14_native_sandbox_adapter_probe_v0.c" \
  | LC_ALL=C sort -u)"

case "$phase" in
  precommit)
    actual_change_scope="$({
      git diff --name-only "$integration_base" --
      git ls-files --others --exclude-standard
    } | LC_ALL=C sort -u)"
    ;;
  postcommit)
    [[ "$(git rev-parse HEAD)" != "$integration_base" ]]
    git diff --quiet HEAD --
    git diff --cached --quiet
    [[ -z "$(git ls-files --others --exclude-standard)" ]]
    actual_change_scope="$(git diff --name-only "$integration_base" HEAD -- | LC_ALL=C sort -u)"
    ;;
esac
[[ "$actual_change_scope" == "$expected_change_scope" ]]

git diff --check "$integration_base" --

python3 - "$implementation" "$checker" "$contract" "$fixture" "$probe" <<'PY'
import sys
from pathlib import Path

runtime_needles = (
    b"engram_g14_native_sandbox_adapter_kat",
    b"PUBLIC_SYNTHETIC_NATIVE_SANDBOX_ADAPTER_KAT",
)
for path in Path("crates").rglob("*"):
    if path.is_file():
        raw = path.read_bytes()
        if any(needle in raw for needle in runtime_needles):
            raise SystemExit(f"G1.4 native KAT leaked into runtime crates: {path}")

surface_paths = [Path(value) for value in sys.argv[1:]]
surface_raw = b"\n".join(path.read_bytes() for path in surface_paths)
forbidden_needles = (
    b"candidate_manifest",
    b"fit_partition",
    b"development_partition",
    b"sealed_partition",
    b"private_corpus",
    b"real_freeze_capability",
)
if any(needle in surface_raw for needle in forbidden_needles):
    raise SystemExit("G1.4 public native KAT contains forbidden candidate/private surface")

required_needles = (
    b"REJECTED_FAIL_CLOSED_WALL_CLOCK_UNCONFINED_NO_AUTHORITY",
    b'"native_adapter_implemented": false',
    b'"g1_4_execution_open": false',
    b"rollback_lessons_v0",
    b'"crate": "nono"',
    b'"version": "0.53.0"',
)
if any(needle not in surface_raw for needle in required_needles):
    raise SystemExit("G1.4 native KAT required closed-surface marker missing")
PY

assert_no_python_cache

echo "engram G1.4 native sandbox adapter KAT: VALIDATED NEGATIVE (unsupported; no authority; phase=$phase)"
