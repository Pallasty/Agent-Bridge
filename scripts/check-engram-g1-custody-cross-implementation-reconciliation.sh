#!/usr/bin/env bash
set -euo pipefail

repo_root="$(git rev-parse --show-toplevel)"
cd "$repo_root"

validator="scripts/eval/engram_g1_custody_cross_implementation_reconciliation.py"
contract="scripts/eval/fixtures/engram_g1_custody_cross_implementation_reconciliation_contract_v0.json"
rust_module="crates/store/src/engram_g1_secure_custody_shadow.rs"
rust_contract="scripts/eval/fixtures/engram_g1_secure_custody_retained_descriptor_shadow_contract_v0.json"
rust_validator="scripts/eval/engram_g1_secure_custody_retained_descriptor_shadow.py"
rust_checker="scripts/check-engram-g1-secure-custody-retained-descriptor-shadow.sh"
python_implementation="scripts/eval/engram_g1_authenticated_freeze_authority_adapter_isolated_lab.py"
python_contract="scripts/eval/fixtures/engram_g1_authenticated_freeze_authority_adapter_isolated_lab_contract_v0.json"
python_checker="scripts/eval/check_engram_g1_authenticated_freeze_authority_adapter_isolated_lab.py"
python_shell="scripts/check-engram-g1-authenticated-freeze-authority-adapter-isolated-lab.sh"

expected_contract_sha256="d0ea62745ff239c988e5725240e0a0e44796cbce5c1b5e5a4dc499c7afa84fbc"
expected_validator_sha256="1ec29777abe0d6ed5624f654aad5c685196f1a30b451241470714319c5c78c38"
expected_rust_module_sha256="ef516c9e8784eac869de38aa11c217de1602f7a9d47719216b620b6401356b82"
expected_rust_contract_sha256="782fafff5b456d2ddd5fbe95d833525a1e62e4d5416ddf481d9ba3e36e582a84"
expected_rust_validator_sha256="25badec3b0ca55f2a07f8038177a33306a56345fe670bff5c4784b586a3b3e5a"
expected_rust_checker_sha256="331736d1244584c25cff50e1c77d93c38668bf9a93543c7ce14602326b699138"
expected_python_implementation_sha256="50e35469af07a81b6eef85fba5c83c92076efe1931b2ee932d8e2d05907ebc94"
expected_python_contract_sha256="f9b913c50eaf477c58a11bbf9526070c43137fe91098388d8260f84eb51a3b14"
expected_python_checker_sha256="e9aec0676148591e44181b36bf6f0a3ad62f130e1c92ed88bdd3cf7519b4c69e"
expected_python_shell_sha256="6f81855d87d348e1e096adad9df2b271385edea3eed52695532155bac06e4895"

rust_commit="db27075ff3eb473b5ca779b57bd86094290dc1c6"
python_commit="bdd0b07b5e9afcc20d030e7e3dcfd404d44e8d54"
integrated_master="33c2c4df78ef302fd0538986b95fa40a3711ba86"
scratch="$(mktemp -d)"
cleanup() {
  rm -rf "$scratch"
}
trap cleanup EXIT

python3 -m py_compile "$validator"
python3 -m black --check "$validator"
python3 -m pyflakes "$validator"
python3 -m json.tool "$contract" >"$scratch/contract.pretty.json"
bash -n "$0"
git diff --check

assert_sha256() {
  artifact="$1"
  expected="$2"
  actual="$(shasum -a 256 "$artifact" | awk '{print $1}')"
  [[ "$actual" == "$expected" ]]
}
assert_sha256 "$contract" "$expected_contract_sha256"
assert_sha256 "$validator" "$expected_validator_sha256"
assert_sha256 "$rust_module" "$expected_rust_module_sha256"
assert_sha256 "$rust_contract" "$expected_rust_contract_sha256"
assert_sha256 "$rust_validator" "$expected_rust_validator_sha256"
assert_sha256 "$rust_checker" "$expected_rust_checker_sha256"
assert_sha256 "$python_implementation" "$expected_python_implementation_sha256"
assert_sha256 "$python_contract" "$expected_python_contract_sha256"
assert_sha256 "$python_checker" "$expected_python_checker_sha256"
assert_sha256 "$python_shell" "$expected_python_shell_sha256"

git merge-base --is-ancestor "$rust_commit" HEAD
git merge-base --is-ancestor "$python_commit" HEAD
git merge-base --is-ancestor "$integrated_master" HEAD

python3 "$validator" validate-contract --contract "$contract" \
  >"$scratch/receipt.1.json"
python3 "$validator" validate-contract --contract "$contract" \
  >"$scratch/receipt.2.json"
cmp "$scratch/receipt.1.json" "$scratch/receipt.2.json"

python3 - "$scratch/receipt.1.json" "$contract" "$validator" <<'PY'
import hashlib
import json
import sys
from pathlib import Path

receipt = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
contract = Path(sys.argv[2])
validator = Path(sys.argv[3])
digest = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()

assert receipt["schema"] == (
    "agent_bridge.engram_g1_custody_cross_implementation_reconciliation_"
    "receipt.v0"
)
assert receipt["contract_id"] == (
    "engram_g1_custody_cross_implementation_reconciliation_20260718"
)
assert receipt["contract_sha256"] == digest(contract)
assert receipt["validator_sha256"] == digest(validator)
assert receipt["contract_verdict"] == (
    "CROSS_IMPLEMENTATION_CUSTODY_RECONCILIATION_PREREGISTERED_"
    "DESIGN_ONLY_NO_AUTHORITY"
)
assert receipt["rust_custody_commit"] == (
    "db27075ff3eb473b5ca779b57bd86094290dc1c6"
)
assert receipt["python_isolated_lab_commit"] == (
    "bdd0b07b5e9afcc20d030e7e3dcfd404d44e8d54"
)
assert receipt["integrated_master"] == (
    "33c2c4df78ef302fd0538986b95fa40a3711ba86"
)
assert receipt["source_pinned"] is True
assert receipt["design_only"] is True
assert receipt["comparison_row_count"] == 28
assert receipt["required_probe_count"] == 18
assert receipt["classification_count"] == 6
assert receipt["exact_equivalence_row_count"] == 0
assert receipt["differential_harness_implemented"] is False
assert receipt["implementation_equivalence_claimed"] is False
assert receipt["automatic_union_permitted"] is False
assert receipt["shared_atomic_linearization_point_proven"] is False
assert receipt["descriptor_native_sqlite_open_proven"] is False
assert receipt["postcommit_custody_revalidation_present"] is False
assert receipt["may_select_strongest_control_by_union"] is False
assert receipt["current_state"] == "SOURCE_PINNED_MATRIX_VALIDATED_NO_AUTHORITY"
assert receipt["positive_equivalence_state_representable"] is False
assert receipt["production_custody_state_representable"] is False
assert receipt["permitted_next_action"] == (
    "implement_separate_synthetic_cross_implementation_differential_"
    "harness_after_independent_threat_review"
)
assert receipt["design_review_required_before_implementation"] is True

for field, value in receipt.items():
    if (
        field.endswith("_permitted")
        or field.endswith("_claimed")
        or field.endswith("_proven")
        or field.endswith("_representable")
        or field == "runtime_authority"
    ):
        assert value is False, field
PY

python3 - "$contract" "$validator" "$scratch" <<'PY'
import ast
import copy
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

contract_path = Path(sys.argv[1])
validator_path = Path(sys.argv[2])
scratch = Path(sys.argv[3])
contract = json.loads(contract_path.read_text(encoding="utf-8"))

sys.path.insert(0, str(validator_path.parent))
spec = importlib.util.spec_from_file_location("engram_g1_reconciliation", validator_path)
assert spec is not None and spec.loader is not None
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def leaf_paths(value, prefix=()):
    if isinstance(value, dict):
        for key, item in value.items():
            yield from leaf_paths(item, prefix + (key,))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            yield from leaf_paths(item, prefix + (index,))
    else:
        yield prefix


def path_text(path):
    rendered = "contract"
    for component in path:
        if isinstance(component, int):
            rendered += f"[{component}]"
        else:
            rendered += f".{component}"
    return rendered


def mutate_leaf(value, path):
    cursor = value
    for component in path[:-1]:
        cursor = cursor[component]
    leaf = cursor[path[-1]]
    if type(leaf) is bool:
        replacement = not leaf
    elif type(leaf) is int:
        replacement = leaf + 1
    elif type(leaf) is str:
        replacement = leaf + "_drift"
    else:
        raise AssertionError((path, type(leaf)))
    cursor[path[-1]] = replacement


paths = list(leaf_paths(contract))
assert len(paths) >= 375, len(paths)
for path in paths:
    candidate = copy.deepcopy(contract)
    mutate_leaf(candidate, path)
    try:
        module.validate_contract_semantics(candidate)
    except module.InputError as exc:
        assert path_text(path) in str(exc), (path_text(path), str(exc))
    else:
        raise AssertionError(f"semantic mutation accepted: {path_text(path)}")

for list_path in [
    ("classification_vocabulary", "allowed"),
    ("comparison_matrix",),
    ("required_future_differential_probes",),
    ("linearization_model", "ordered_events"),
    ("state_machine", "representable_states"),
]:
    candidate = copy.deepcopy(contract)
    target = candidate
    for component in list_path:
        target = target[component]
    target.pop()
    try:
        module.validate_contract_semantics(candidate)
    except module.InputError as exc:
        assert path_text(list_path) in str(exc)
    else:
        raise AssertionError(f"list truncation accepted: {path_text(list_path)}")

candidate = copy.deepcopy(contract)
candidate["classification_vocabulary"]["exact_equivalence_rows"].append(
    "UNREGISTERED_EQUIVALENCE"
)
try:
    module.validate_contract_semantics(candidate)
except module.InputError as exc:
    assert "contract.classification_vocabulary.exact_equivalence_rows" in str(exc)
else:
    raise AssertionError("exact-equivalence insertion accepted")

extra = copy.deepcopy(contract)
extra["unexpected_authority_surface"] = False
try:
    module.validate_contract_semantics(extra)
except module.InputError as exc:
    assert "contract fields mismatch" in str(exc)
else:
    raise AssertionError("unexpected top-level field accepted")

raw = contract_path.read_text(encoding="utf-8")
byte_drift = scratch / "byte-drift.json"
byte_drift.write_bytes(raw.replace("\n", "\r\n").encode("utf-8"))
result = subprocess.run(
    [sys.executable, str(validator_path), "validate-contract", "--contract", str(byte_drift)],
    text=True,
    capture_output=True,
    check=False,
)
assert result.returncode == 2
assert "contract bytes do not match v0" in result.stderr

duplicate = raw.replace(
    '  "schema": "agent_bridge.engram_g1_custody_cross_implementation_reconciliation_contract.v0",',
    '  "schema": "agent_bridge.engram_g1_custody_cross_implementation_reconciliation_contract.v0",\n'
    '  "schema": "agent_bridge.engram_g1_custody_cross_implementation_reconciliation_contract.v0",',
    1,
)
duplicate_path = scratch / "duplicate-field.json"
duplicate_path.write_text(duplicate, encoding="utf-8")
result = subprocess.run(
    [sys.executable, str(validator_path), "validate-contract", "--contract", str(duplicate_path)],
    text=True,
    capture_output=True,
    check=False,
)
assert result.returncode == 2
assert "duplicate field" in result.stderr

banned_import_roots = {
    "cryptography",
    "nacl",
    "requests",
    "socket",
    "sqlite3",
    "subprocess",
    "urllib",
}
tree = ast.parse(validator_path.read_text(encoding="utf-8"))
for node in ast.walk(tree):
    if isinstance(node, ast.Import):
        for alias in node.names:
            assert alias.name.split(".", 1)[0] not in banned_import_roots
    elif isinstance(node, ast.ImportFrom) and node.module:
        assert node.module.split(".", 1)[0] not in banned_import_roots

source = validator_path.read_text(encoding="utf-8")
assert "--private" not in source
assert "--key" not in source
assert "data/" not in source
PY

ln -s "$repo_root/$contract" "$scratch/contract-symlink.json"
if python3 "$validator" validate-contract \
  --contract "$scratch/contract-symlink.json" \
  >"$scratch/symlink.stdout" 2>"$scratch/symlink.stderr"; then
  echo "expected reconciliation contract symlink to fail closed" >&2
  exit 1
fi
grep -q "failed to open" "$scratch/symlink.stderr"

python3 - "$rust_module" "$python_implementation" <<'PY'
import ast
import sys
from pathlib import Path

rust_path = Path(sys.argv[1])
python_path = Path(sys.argv[2])
rust = rust_path.read_text(encoding="utf-8")
python = python_path.read_text(encoding="utf-8")

for required in [
    "DARWIN_O_UNIQUE",
    "libc::O_NONBLOCK",
    "absolute_root_components",
    "AT_SYMLINK_NOFOLLOW",
    "private_custody_directory",
    "mount.fs_type_name() != b\"apfs\"",
]:
    assert required in rust, required
assert "os.O_NONBLOCK" not in python
assert "O_UNIQUE" not in python

tree = ast.parse(python)


def source_for_function(name):
    matches = [node for node in ast.walk(tree) if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name]
    assert len(matches) == 1, (name, len(matches))
    segment = ast.get_source_segment(python, matches[0])
    assert segment is not None
    return segment


def source_for_method(class_name, method_name):
    classes = [
        node for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == class_name
    ]
    assert len(classes) == 1, (class_name, len(classes))
    matches = [
        node for node in classes[0].body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name == method_name
    ]
    assert len(matches) == 1, (class_name, method_name, len(matches))
    segment = ast.get_source_segment(python, matches[0])
    assert segment is not None
    return segment


absolute_open = source_for_function("_open_absolute_directory")
assert "path.parts[1:]" in absolute_open
assert "os.close(fd)" in absolute_open

same_stat = source_for_function("_same_stat")
for present in ["st_dev", "st_ino", "st_mode", "st_uid", "st_nlink", "st_size", "st_mtime_ns", "st_ctime_ns"]:
    assert present in same_stat, present
for absent in ["st_gid", "st_rdev", "st_blocks", "st_birthtime", "st_flags", "st_gen"]:
    assert absent not in same_stat, absent

open_existing = source_for_method("PrivateTrustLedgerDouble", "_open_existing")
assert "sentinel_fd = os.open" in open_existing
assert "sqlite3.connect" in open_existing
assert "self.path.as_uri()" in open_existing

claim = source_for_method("PrivateTrustLedgerDouble", "claim")
assert claim.index("precommit()") < claim.index('connection.execute("COMMIT")')
assert "postcommit" not in claim.lower()
PY

if rg -l "engram_g1_custody_cross_implementation_reconciliation" crates \
  >"$scratch/runtime-surface.txt"; then
  echo "unexpected crate/runtime surface for design-only reconciliation" >&2
  cat "$scratch/runtime-surface.txt" >&2
  exit 1
fi

"$rust_checker"
"$python_shell"

echo "engram G1 custody cross-implementation reconciliation preregistration: PASS"
