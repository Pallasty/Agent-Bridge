#!/usr/bin/env bash
set -euo pipefail

repo_root="$(git rev-parse --show-toplevel)"
cd "$repo_root"

validator="scripts/eval/engram_g1_secure_custody_retained_descriptor_shadow.py"
contract="scripts/eval/fixtures/engram_g1_secure_custody_retained_descriptor_shadow_contract_v0.json"
module="crates/store/src/engram_g1_secure_custody_shadow.rs"
lib="crates/store/src/lib.rs"
cargo="crates/store/Cargo.toml"
predecessor_checker="scripts/check-engram-g1-authenticated-freeze-authority-envelope-shadow.sh"
expected_contract_sha256="782fafff5b456d2ddd5fbe95d833525a1e62e4d5416ddf481d9ba3e36e582a84"
expected_validator_sha256="25badec3b0ca55f2a07f8038177a33306a56345fe670bff5c4784b586a3b3e5a"
expected_module_sha256="ef516c9e8784eac869de38aa11c217de1602f7a9d47719216b620b6401356b82"
predecessor_commit="2cca958844bc4ddf06954737775d40560119b8d1"
integrated_master="1f44c69d31ae29d0cd6c90e84294b3ad0407d9a0"
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
rustfmt --edition 2021 --check "$module" "$lib"
git diff --check

actual_contract_sha256="$(shasum -a 256 "$contract" | awk '{print $1}')"
actual_validator_sha256="$(shasum -a 256 "$validator" | awk '{print $1}')"
actual_module_sha256="$(shasum -a 256 "$module" | awk '{print $1}')"
[[ "$actual_contract_sha256" == "$expected_contract_sha256" ]]
[[ "$actual_validator_sha256" == "$expected_validator_sha256" ]]
[[ "$actual_module_sha256" == "$expected_module_sha256" ]]

git merge-base --is-ancestor "$predecessor_commit" HEAD
git merge-base --is-ancestor "$integrated_master" HEAD

python3 "$validator" validate-contract --contract "$contract" \
  >"$scratch/receipt.1.json"
python3 "$validator" validate-contract --contract "$contract" \
  >"$scratch/receipt.2.json"
cmp "$scratch/receipt.1.json" "$scratch/receipt.2.json"

python3 - "$scratch/receipt.1.json" "$contract" "$validator" "$module" <<'PY'
import hashlib
import json
import sys
from pathlib import Path

receipt = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
contract = Path(sys.argv[2])
validator = Path(sys.argv[3])
module = Path(sys.argv[4])
digest = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()

assert receipt["schema"] == (
    "agent_bridge.engram_g1_secure_custody_retained_descriptor_shadow_"
    "contract_receipt.v0"
)
assert receipt["contract_id"] == (
    "engram_g1_secure_custody_retained_descriptor_shadow_20260718"
)
assert receipt["contract_sha256"] == digest(contract)
assert receipt["validator_sha256"] == digest(validator)
assert receipt["module_source_sha256"] == digest(module)
assert receipt["predecessor_commit"] == (
    "2cca958844bc4ddf06954737775d40560119b8d1"
)
assert receipt["contract_verdict"] == (
    "SYNTHETIC_RETAINED_DESCRIPTOR_CUSTODY_SHADOW_CONTRACT_"
    "VALIDATED_NO_AUTHORITY"
)
assert receipt["cargo_feature"] == (
    "engram-g1-secure-custody-shadow-synthetic"
)
assert receipt["feature_enabled_by_default"] is False
assert receipt["module_exported_publicly"] is False
assert receipt["runtime_entrypoint_present"] is False
assert receipt["supported_os"] == "macos"
assert receipt["supported_filesystem"] == "local_apfs_only"
assert receipt["test_only_permit"] is True
assert receipt["synthetic_disposable_tree_only"] is True
assert receipt["open_directory_flags"] == (
    "O_RDONLY|O_DIRECTORY|O_NOFOLLOW|O_CLOEXEC|O_NONBLOCK"
)
assert receipt["open_file_flags"] == (
    "O_RDONLY|O_NOFOLLOW|O_CLOEXEC|O_NONBLOCK|DARWIN_O_UNIQUE"
)
assert receipt["maximum_synthetic_file_bytes"] == 1048576
assert receipt["required_attack_test_count"] == 13
assert receipt["required_threat_count"] == 10
assert receipt["current_state"] == (
    "SYNTHETIC_RETAINED_DESCRIPTOR_SHADOW_IMPLEMENTED_NO_AUTHORITY"
)
assert receipt["real_adapter_state"] == "PENDING_IMPLEMENTATION_PREREQUISITES"
assert receipt["positive_secure_custody_state_representable"] is False
assert receipt["permitted_next_action"] == (
    "preregister_separate_atomic_envelope_and_custody_composition_shadow_gate"
)
assert receipt["real_private_corpus_loading_permitted"] is False
assert receipt["real_trust_root_provisioning_permitted"] is False

for field, value in receipt.items():
    if (
        field.endswith("_authority")
        or field.endswith("_verified")
        or field.startswith("ready_for_")
        or field.endswith("_permitted")
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
spec = importlib.util.spec_from_file_location("engram_g1_custody_shadow", validator_path)
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
assert len(paths) >= 175, len(paths)
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
    ("deterministic_attack_tests", "required_cases"),
    ("state_machine", "representable_states"),
    ("threat_model", "required_cases"),
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
    '  "schema": "agent_bridge.engram_g1_secure_custody_retained_descriptor_shadow_contract.v0",',
    '  "schema": "agent_bridge.engram_g1_secure_custody_retained_descriptor_shadow_contract.v0",\n'
    '  "schema": "agent_bridge.engram_g1_secure_custody_retained_descriptor_shadow_contract.v0",',
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
  echo "expected public contract symlink to fail closed" >&2
  exit 1
fi
grep -q "failed to open" "$scratch/symlink.stderr"

python3 - "$module" "$lib" "$cargo" <<'PY'
import re
import sys
from pathlib import Path

module = Path(sys.argv[1]).read_text(encoding="utf-8")
lib = Path(sys.argv[2]).read_text(encoding="utf-8")
cargo = Path(sys.argv[3]).read_text(encoding="utf-8")
production, tests = module.split("#[cfg(test)]\nmod tests", 1)

for forbidden in [
    "std::env",
    "std::net",
    "std::process",
    "std::time",
    "rusqlite",
    "tokio::",
    "engram_g1_authenticated_envelope_shadow",
]:
    assert forbidden not in production, forbidden
assert "pub mod engram_g1_secure_custody_shadow" not in lib
assert re.search(
    r'#\[cfg\(all\(\n'
    r'    feature = "engram-g1-secure-custody-shadow-synthetic",\n'
    r'    target_os = "macos"\n'
    r'\)\)\]\n'
    r'mod engram_g1_secure_custody_shadow;',
    lib,
)
assert (
    'engram-g1-secure-custody-shadow-synthetic = ["dep:libc"]' in cargo
)
assert 'libc = { version = "0.2", optional = true }' in cargo
default_block = cargo.split("default =", 1)[1].split("\n", 1)[0]
assert "engram-g1-secure-custody-shadow-synthetic" not in default_block
assert re.search(
    r'#\[cfg\(test\)\]\nfn synthetic_test_permit_v1\(\)',
    production,
)
assert "_permit: &SyntheticCustodyPermitV1" in production
assert "O_NOFOLLOW" in production
assert "O_DIRECTORY" in production
assert "AT_SYMLINK_NOFOLLOW" in production
assert "DARWIN_O_UNIQUE" in production
assert "snapshot.nlink != 1" in production
assert "libc::MNT_LOCAL" in production
assert 'mount.fs_type_name() != b"apfs"' in production
assert "owner_only_modes_verified" not in production
assert "effective_uid_and_exact_posix_modes_verified: true" in production
assert "secure_custody_capture_verified: false" in production
assert "authenticated_envelope_composed: false" in production
assert "capability_minted: false" in production
assert "freeze_authority_verified: false" in production
assert "ready_for_g1_4_candidate_protocol_preregistration: false" in production
assert "runtime_authority: false" in production
assert production.count("unsafe {") <= production.count("// SAFETY:")
assert tests.count("#[test]") == 13
PY

python3 - "$module" <<'PY'
import subprocess
import sys
from pathlib import Path

module = Path(sys.argv[1]).resolve()
repo = module.parents[3]
result = subprocess.run(
    [
        "rg",
        "-l",
        "engram_g1_secure_custody_shadow|engram-g1-secure-custody-shadow-synthetic",
        "crates",
    ],
    cwd=repo,
    text=True,
    capture_output=True,
    check=True,
)
observed = {line for line in result.stdout.splitlines() if line}
expected = {
    "crates/store/Cargo.toml",
    "crates/store/src/engram_g1_secure_custody_shadow.rs",
    "crates/store/src/lib.rs",
}
assert observed == expected, observed
PY

cargo test -p ab-store --no-default-features \
  --features engram-g1-secure-custody-shadow-synthetic \
  engram_g1_secure_custody_shadow 2>&1 | tee "$scratch/cargo-test.log"
grep -q "test result: ok. 13 passed; 0 failed" "$scratch/cargo-test.log"

cargo check -p ab-store --no-default-features
"$predecessor_checker"

echo "engram G1 secure custody retained-descriptor shadow: PASS"
