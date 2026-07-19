#!/usr/bin/env bash
set -euo pipefail

repo_root="$(git rev-parse --show-toplevel)"
cd "$repo_root"

contract="scripts/eval/fixtures/engram_g1_custody_cross_implementation_differential_harness_contract_v0.json"
harness="scripts/eval/engram_g1_custody_cross_implementation_differential_harness.py"
predecessor="scripts/check-engram-g1-custody-cross-implementation-reconciliation.sh"
scratch="$(mktemp -d)"
cleanup() {
  rm -rf "$scratch"
}
trap cleanup EXIT

python3 -m py_compile "$harness"
python3 -m black --check "$harness"
python3 -m pyflakes "$harness"
python3 -m json.tool "$contract" >"$scratch/contract.pretty.json"
bash -n "$0"
git diff --check

python3 - "$contract" "$harness" "$0" <<'PY'
import hashlib
import importlib.util
import json
import re
import sys
from pathlib import Path

contract_path, harness_path, checker_path = map(Path, sys.argv[1:])
spec = importlib.util.spec_from_file_location("g1_diff", harness_path)
assert spec is not None and spec.loader is not None
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
contract = json.loads(contract_path.read_text(encoding="utf-8"))
assert hashlib.sha256(contract_path.read_bytes()).hexdigest() == module.CONTRACT_SHA256
checker_sha256 = contract["checker_sha256"]
assert re.fullmatch(r"[0-9a-f]{64}", checker_sha256)
assert hashlib.sha256(checker_path.read_bytes()).hexdigest() == checker_sha256
PY

git merge-base --is-ancestor 382f94e597c9ccad748a271665973e01d7c78f9c HEAD
"$predecessor"

python3 "$harness" --contract "$contract" >"$scratch/receipt.1.json"
python3 "$harness" --contract "$contract" >"$scratch/receipt.2.json"
cmp "$scratch/receipt.1.json" "$scratch/receipt.2.json"

python3 - "$scratch/receipt.1.json" "$contract" <<'PY'
import hashlib
import json
import sys
from pathlib import Path

receipt = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
contract = Path(sys.argv[2])
assert receipt["schema"] == (
    "agent_bridge.engram_g1_custody_cross_implementation_"
    "differential_harness_receipt.v0"
)
assert receipt["contract_sha256"] == hashlib.sha256(contract.read_bytes()).hexdigest()
assert receipt["predecessor_commit"] == "382f94e597c9ccad748a271665973e01d7c78f9c"
assert receipt["verdict"] == "PASS_SYNTHETIC_DIFFERENTIAL_OBSERVATIONS_NO_AUTHORITY"
assert receipt["probe_count"] == 18
assert receipt["dynamic_rust_probe_count"] == 7
assert receipt["rust_dynamic_test_count"] == 7
assert receipt["dynamic_python_probe_count"] == 8
assert receipt["unresolved_shared_gap_count"] == 4
for field in ("implementation_equivalence_claimed", "production_custody_claimed", "authority_claimed", "g1_4_open", "runtime_authority"):
    assert receipt[field] is False, field
assert [item["id"] for item in receipt["probe_results"]] == [
    "P01_RAW_PATH_SPELLING", "P02_ABSOLUTE_ANCESTOR_SWAP", "P03_PRIVATE_PARENT_SWAP",
    "P04_PRIVATE_DIRECTORY_METADATA_DRIFT", "P05_HARDLINK_BEFORE_OPEN",
    "P06_HARDLINK_OPEN_RACE", "P07_FIFO_OR_DEVICE_SUBSTITUTION",
    "P08_FILE_REBIND_AFTER_READ", "P09_IN_PLACE_BYTE_MUTATION",
    "P10_LOCAL_NON_APFS_FILESYSTEM", "P11_MOUNT_FINGERPRINT_DRIFT",
    "P12_EXTENDED_METADATA_DRIFT", "P13_PUBLIC_ARTIFACT_NAME_REBIND",
    "P14_SQLITE_PATH_REOPEN_SWAP", "P15_AFTER_PRECOMMIT_BEFORE_COMMIT_MUTATION",
    "P16_POSTCOMMIT_FILESYSTEM_MUTATION", "P17_DARWIN_ACL_PRESENT", "P18_APFS_COPY_ALIAS",
]
for item in receipt["probe_results"]:
    assert item["authority_if_pass"] is False
    assert item["classification"] != "EQUIVALENT"
    assert "/" not in item["rust_outcome"]
    assert "/" not in item["python_outcome"]
assert receipt["probe_results"][2]["python_outcome"] == "ACCEPTED_RETAINED_PARENT_FD_WITHOUT_NAME_CHAIN_RECHECK"
assert receipt["probe_results"][3]["python_outcome"] == "ACCEPTED_DIRECTORY_MODE_DRIFT_AT_CLAIM_TIME"
PY

python3 - "$contract" "$harness" <<'PY'
import copy
import importlib.util
import json
import sys
from pathlib import Path

contract_path = Path(sys.argv[1])
harness_path = Path(sys.argv[2])
spec = importlib.util.spec_from_file_location("g1_diff", harness_path)
assert spec is not None and spec.loader is not None
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
contract = json.loads(contract_path.read_text(encoding="utf-8"))
for path in [
    ("execution", "authority_claimed"),
    ("execution", "implementation_equivalence_claimed"),
    ("boundaries", "runtime_authority"),
    ("probe_plan", 0, "rust_mode"),
    ("probe_plan", 17, "classification"),
]:
    candidate = copy.deepcopy(contract)
    target = candidate
    for key in path[:-1]:
        target = target[key]
    old = target[path[-1]]
    target[path[-1]] = (not old) if type(old) is bool else str(old) + "_drift"
    try:
        module.validate_contract_semantics(candidate)
    except module.GateError:
        pass
    else:
        raise AssertionError(f"semantic drift accepted: {path}")
candidate = copy.deepcopy(contract)
candidate["probe_plan"].pop()
try:
    module.validate_contract_semantics(candidate)
except module.GateError:
    pass
else:
    raise AssertionError("probe truncation accepted")

sys.path.insert(0, str(harness_path.parent))
isolated = importlib.import_module("engram_g1_authenticated_freeze_authority_adapter_isolated_lab")
isolated_checker = importlib.import_module(
    "check_engram_g1_authenticated_freeze_authority_adapter_isolated_lab"
)
isolated_checker.module = isolated
private_dir = ledger_dir = None
try:
    with module.disposable_harness(isolated_checker) as fixture:
        private_dir = fixture.private_dir
        ledger_dir = fixture.ledger_dir
        raise RuntimeError("synthetic exception-cleanup canary")
except RuntimeError as exc:
    assert str(exc) == "synthetic exception-cleanup canary"
assert private_dir is not None and ledger_dir is not None
assert not private_dir.exists()
assert not ledger_dir.exists()
PY
