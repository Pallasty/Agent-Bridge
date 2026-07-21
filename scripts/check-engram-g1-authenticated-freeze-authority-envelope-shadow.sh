#!/usr/bin/env bash
set -euo pipefail

repo_root="$(git rev-parse --show-toplevel)"
cd "$repo_root"

validator="scripts/eval/engram_g1_authenticated_freeze_authority_envelope_shadow.py"
validator_helper="scripts/eval/engram_g1_corpus_design.py"
contract="scripts/eval/fixtures/engram_g1_authenticated_freeze_authority_envelope_shadow_contract_v0.json"
module="crates/store/src/engram_g1_authenticated_envelope_shadow.rs"
predecessor_checker="scripts/check-engram-g1-authenticated-freeze-authority-adapter-preregistration.sh"
expected_contract_sha256="066c77027635ef6f0ab388e9bee9cf094a597c7cc1a23cd867aa83d78d8bf6d7"
expected_validator_sha256="57e0b30fb459c1ac3ec2d9a0eff9ee6673fbd704f2b94702d5a5ebc35df76fe0"
expected_module_sha256="5f3285482c27a73b768ca3c0726031184cb022516d9d48c4abe4258c4ed117ef"
scratch="$(mktemp -d)"
cleanup() {
  rm -rf "$scratch"
}
trap cleanup EXIT

python3 -m py_compile "$validator"
bash -n "$0"

actual_contract_sha256="$(shasum -a 256 "$contract" | awk '{print $1}')"
actual_validator_sha256="$(shasum -a 256 "$validator" | awk '{print $1}')"
actual_module_sha256="$(shasum -a 256 "$module" | awk '{print $1}')"
[[ "$actual_contract_sha256" == "$expected_contract_sha256" ]]
[[ "$actual_validator_sha256" == "$expected_validator_sha256" ]]
[[ "$actual_module_sha256" == "$expected_module_sha256" ]]

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
    "agent_bridge.engram_g1_authenticated_freeze_authority_envelope_shadow_"
    "contract_receipt.v0"
)
assert receipt["contract_id"] == (
    "engram_g1_authenticated_freeze_authority_envelope_shadow_20260718"
)
assert receipt["contract_sha256"] == digest(contract)
assert receipt["validator_sha256"] == digest(validator)
assert receipt["module_source_sha256"] == digest(module)
assert receipt["predecessor_commit"] == (
    "632918db75f65030d3ac15bc991b51a9c938cba6"
)
assert receipt["contract_verdict"] == (
    "SYNTHETIC_AUTHENTICATED_ENVELOPE_SHADOW_CONTRACT_"
    "VALIDATED_NO_AUTHORITY"
)
assert receipt["cargo_feature"] == (
    "engram-g1-authenticated-envelope-shadow-synthetic"
)
assert receipt["feature_enabled_by_default"] is False
assert receipt["module_exported_publicly"] is False
assert receipt["runtime_entrypoint_present"] is False
assert receipt["synthetic_test_vectors_only"] is True
assert receipt["canonicalization_profile"] == (
    "agent_bridge_rfc8785_compatible_ascii_safe_integer_subset_v1"
)
assert receipt["restricted_exact_subset_not_full_jcs"] is True
assert receipt["required_signature_count"] == 5
assert receipt["required_threat_count"] == 9
assert receipt["current_state"] == (
    "SYNTHETIC_ENVELOPE_SHADOW_IMPLEMENTED_NO_AUTHORITY"
)
assert receipt["real_adapter_state"] == "PENDING_IMPLEMENTATION_PREREQUISITES"
assert receipt["positive_freeze_authority_state_representable"] is False
assert receipt["real_trust_root_provisioning_permitted"] is False
assert receipt["real_private_corpus_loading_permitted"] is False
assert receipt["permitted_next_action"] == (
    "prepare_separate_secure_custody_retained_descriptor_shadow_"
    "implementation_gate"
)

for field, value in receipt.items():
    if (
        field.endswith("_authority")
        or field.endswith("_verified")
        or field.startswith("ready_for_")
        or field.endswith("_permitted")
    ):
        assert value is False, field
PY

python3 - "$contract" "$validator" "$validator_helper" "$scratch" <<'PY'
import ast
import copy
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

contract_path = Path(sys.argv[1])
validator_path = Path(sys.argv[2])
helper_path = Path(sys.argv[3])
scratch = Path(sys.argv[4])
contract = json.loads(contract_path.read_text(encoding="utf-8"))

sys.path.insert(0, str(validator_path.parent))
spec = importlib.util.spec_from_file_location("engram_g1_envelope_shadow", validator_path)
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
assert len(paths) >= 145, len(paths)
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
    ("implemented_shadow_checks", "required_roles_in_order"),
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
    '  "schema": "agent_bridge.engram_g1_authenticated_freeze_authority_envelope_shadow_contract.v0",',
    '  "schema": "agent_bridge.engram_g1_authenticated_freeze_authority_envelope_shadow_contract.v0",\n'
    '  "schema": "agent_bridge.engram_g1_authenticated_freeze_authority_envelope_shadow_contract.v0",',
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
for source_path in (validator_path, helper_path):
    tree = ast.parse(source_path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert alias.name.split(".", 1)[0] not in banned_import_roots
        elif isinstance(node, ast.ImportFrom) and node.module:
            assert node.module.split(".", 1)[0] not in banned_import_roots

validator_source = validator_path.read_text(encoding="utf-8")
assert "--private" not in validator_source
assert "--key" not in validator_source
assert "data/" not in validator_source
PY

ln -s "$repo_root/$contract" "$scratch/contract-symlink.json"
if python3 "$validator" validate-contract \
  --contract "$scratch/contract-symlink.json" \
  >"$scratch/symlink.stdout" 2>"$scratch/symlink.stderr"; then
  echo "expected public contract symlink to fail closed" >&2
  exit 1
fi
grep -q "failed to open" "$scratch/symlink.stderr"

python3 - "$module" "crates/store/src/lib.rs" "crates/store/Cargo.toml" <<'PY'
import re
import sys
from pathlib import Path

module = Path(sys.argv[1]).read_text(encoding="utf-8")
lib = Path(sys.argv[2]).read_text(encoding="utf-8")
cargo = Path(sys.argv[3]).read_text(encoding="utf-8")

for forbidden in [
    "std::env",
    "std::fs",
    "std::net",
    "std::process",
    "std::time",
    "rusqlite",
    "tokio::",
]:
    assert forbidden not in module, forbidden
assert "pub mod engram_g1_authenticated_envelope_shadow" not in lib
assert re.search(
    r'#\[cfg\(feature = "engram-g1-authenticated-envelope-shadow-synthetic"\)\]\n'
    r'mod engram_g1_authenticated_envelope_shadow;',
    lib,
)
assert (
    'engram-g1-authenticated-envelope-shadow-synthetic = ["dep:ring"]' in cargo
)
default_block = cargo.split("default =", 1)[1].split("\n", 1)[0]
assert "engram-g1-authenticated-envelope-shadow-synthetic" not in default_block
assert "public_key_carried_by_envelope" not in module
assert "capability_minted: false" in module
assert "freeze_authority_verified: false" in module
assert "ready_for_g1_4_candidate_protocol_preregistration: false" in module
assert "runtime_authority: false" in module
PY

cargo test -p ab-store --no-default-features \
  --features engram-g1-authenticated-envelope-shadow-synthetic \
  engram_g1_auth_envelope_shadow

if cargo tree -p ab-store --no-default-features -e normal --prefix none \
  | grep -Eq '^ring '; then
  echo "ring unexpectedly reachable with ab-store default features disabled" >&2
  exit 1
fi

"$predecessor_checker"

echo "engram G1 authenticated freeze authority envelope shadow: PASS"
