#!/usr/bin/env bash
set -euo pipefail

repo_root="$(git rev-parse --show-toplevel)"
cd "$repo_root"

validator="scripts/eval/engram_g14_candidate_protocol_preregistration.py"
validator_helper="scripts/eval/engram_g1_corpus_design.py"
contract="scripts/eval/fixtures/engram_g14_candidate_protocol_preregistration_contract_v0.json"
predecessor_contract="scripts/eval/fixtures/engram_g1_authenticated_freeze_authority_adapter_isolated_lab_contract_v0.json"
predecessor_implementation="scripts/eval/engram_g1_authenticated_freeze_authority_adapter_isolated_lab.py"
predecessor_checker="scripts/eval/check_engram_g1_authenticated_freeze_authority_adapter_isolated_lab.py"
predecessor_shell="scripts/check-engram-g1-authenticated-freeze-authority-adapter-isolated-lab.sh"
expected_contract_sha256="dca8ac03fbc915d70c6470492136ca9e554722aeed8d789e85714ece7e60ea41"
expected_validator_sha256="9e03d53b19eb9dd273ac6dc49cde7a9a93221de50be58eede37d25729374cd1c"
scratch="$(mktemp -d)"
cleanup() {
  rm -rf "$scratch"
}
trap cleanup EXIT

python3 -m py_compile "$validator"
bash -n "$0"

actual_contract_sha256="$(shasum -a 256 "$contract" | awk '{print $1}')"
actual_validator_sha256="$(shasum -a 256 "$validator" | awk '{print $1}')"
[[ "$actual_contract_sha256" == "$expected_contract_sha256" ]]
[[ "$actual_validator_sha256" == "$expected_validator_sha256" ]]

python3 "$validator" validate-contract --contract "$contract" \
  >"$scratch/receipt.1.json"
python3 "$validator" validate-contract --contract "$contract" \
  >"$scratch/receipt.2.json"
cmp "$scratch/receipt.1.json" "$scratch/receipt.2.json"

python3 - "$scratch/receipt.1.json" "$contract" "$validator" \
  "$predecessor_contract" "$predecessor_implementation" \
  "$predecessor_checker" "$predecessor_shell" <<'PY'
import hashlib
import json
import sys
from pathlib import Path

receipt = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
contract = Path(sys.argv[2])
validator = Path(sys.argv[3])
predecessor_contract = Path(sys.argv[4])
predecessor_implementation = Path(sys.argv[5])
predecessor_checker = Path(sys.argv[6])
predecessor_shell = Path(sys.argv[7])


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


assert receipt["schema"] == (
    "agent_bridge.engram_g1_4_candidate_protocol_preregistration_receipt.v0"
)
assert receipt["contract_id"] == (
    "engram_g14_candidate_protocol_preregistration_20260718"
)
assert receipt["contract_sha256"] == digest(contract)
assert receipt["validator_sha256"] == digest(validator)
assert receipt["predecessor_commit"] == (
    "bdd0b07b5e9afcc20d030e7e3dcfd404d44e8d54"
)
assert receipt["predecessor_contract_sha256"] == digest(predecessor_contract)
assert receipt["predecessor_implementation_sha256"] == digest(
    predecessor_implementation
)
assert receipt["predecessor_checker_sha256"] == digest(predecessor_checker)
assert receipt["predecessor_shell_entrypoint_sha256"] == digest(predecessor_shell)
assert receipt["contract_verdict"] == (
    "G1_4_CANDIDATE_PROTOCOL_PREREGISTERED_DESIGN_ONLY_FAIL_CLOSED"
)
assert receipt["public_design_contract_only"] is True
assert receipt["experiment_question"] == (
    "can_clustered_reorganization_reduce_unrelated_target_intrusion_without_"
    "materially_degrading_exact_or_related_retrieval"
)
assert receipt["candidate_arm"] == "clustered_reorganization"
assert receipt["comparator_arm_count"] == 2
assert receipt["mechanism_falsifier_arm_count"] == 2
assert receipt["retrieval_mode_count"] == 3
assert receipt["top_k"] == 10
assert receipt["maximum_development_feedback_rounds"] == 2
assert receipt["sandbox_profile"] == (
    "nono_landlock_or_seatbelt_deny_by_default_offline_runner_v1"
)
assert receipt["network_access_denied_in_future_runner"] is True
assert receipt["sealed_execution_is_one_shot"] is True
assert receipt["selective_retry_forbidden"] is True
assert receipt["minimum_paired_primary_repairs_vs_each_comparator"] == 2
assert receipt["required_threat_count"] == 16
assert receipt["manual_audit_event_count"] == 8
assert receipt["routine_public_validation_requires_human_approval"] is False
assert (
    receipt[
        "unchanged_public_synthetic_validation_requires_per_run_human_approval"
    ]
    is False
)
assert receipt["reversible_failure_requires_automatic_rollback"] is True
assert receipt["rollback_failure_requires_durable_lesson"] is True
assert receipt["current_state"] == (
    "G1_4_CANDIDATE_PROTOCOL_PREREGISTERED_DESIGN_ONLY"
)
assert receipt["g1_4_design_preregistered"] is True
assert receipt["validator_implements_sandbox"] is False
assert receipt["validator_implements_protocol_runner"] is False
assert receipt["validator_executes_experiment"] is False

allowed_true_boundary = "g1_4_design_preregistered"
for field, value in receipt.items():
    if field == allowed_true_boundary:
        continue
    if (
        field.endswith("_authority")
        or field.endswith("_verified")
        or field.endswith("_implemented")
        or field.endswith("_present")
        or field.startswith("ready_for_")
        or field.startswith("validator_implements_")
        or field.startswith("validator_executes_")
    ):
        assert value is False, field
PY

python3 - "$contract" "$validator" "$validator_helper" "$scratch" <<'PY'
import ast
import copy
import importlib.util
import json
import re
import subprocess
import sys
from pathlib import Path

contract_path = Path(sys.argv[1])
validator_path = Path(sys.argv[2])
helper_path = Path(sys.argv[3])
scratch = Path(sys.argv[4])
contract = json.loads(contract_path.read_text(encoding="utf-8"))

sys.path.insert(0, str(validator_path.parent))
spec = importlib.util.spec_from_file_location("engram_g14_prereg", validator_path)
assert spec is not None and spec.loader is not None
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def path_text(path):
    rendered = "contract"
    for component in path:
        if isinstance(component, int):
            rendered += f"[{component}]"
        else:
            rendered += f".{component}"
    return rendered


def get_path(value, path):
    cursor = value
    for component in path:
        cursor = cursor[component]
    return cursor


def set_path(value, path, replacement):
    if not path:
        return replacement
    cursor = value
    for component in path[:-1]:
        cursor = cursor[component]
    cursor[path[-1]] = replacement
    return value


def reject_mutation(label, path, replacement, expected_path=None):
    candidate = copy.deepcopy(contract)
    candidate = set_path(candidate, path, replacement)
    expected = path_text(path if expected_path is None else expected_path)
    try:
        module.validate_contract_semantics(candidate)
    except module.InputError as exc:
        assert expected in str(exc), (label, expected, str(exc))
    else:
        raise AssertionError(f"semantic mutation accepted: {label}")


def walk(value, path=()):
    yield path, value
    if isinstance(value, dict):
        for key, child in value.items():
            yield from walk(child, path + (key,))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from walk(child, path + (index,))


module.validate_contract_semantics(copy.deepcopy(contract))
mutation_count = 0
for path, value in list(walk(contract)):
    label = path_text(path)
    if isinstance(value, dict):
        if path:
            reject_mutation(f"{label}:object-type", path, [], path)
            mutation_count += 1
        if value:
            removed = copy.deepcopy(value)
            removed.pop(next(iter(removed)))
            reject_mutation(f"{label}:field-removed", path, removed, path)
            mutation_count += 1
        added = copy.deepcopy(value)
        added["unexpected_field"] = False
        reject_mutation(f"{label}:field-added", path, added, path)
        mutation_count += 1
    elif isinstance(value, list):
        reject_mutation(f"{label}:array-type", path, {}, path)
        mutation_count += 1
        shortened = copy.deepcopy(value[:-1]) if value else ["unexpected"]
        reject_mutation(f"{label}:array-length", path, shortened, path)
        mutation_count += 1
        if len(value) > 1:
            reject_mutation(f"{label}:array-order", path, list(reversed(value)), path)
            mutation_count += 1
    elif isinstance(value, bool):
        reject_mutation(f"{label}:boolean-value", path, not value)
        reject_mutation(f"{label}:boolean-type", path, int(value))
        mutation_count += 2
    elif isinstance(value, int):
        reject_mutation(f"{label}:integer-value", path, value + 1)
        reject_mutation(f"{label}:integer-type", path, str(value))
        mutation_count += 2
    elif isinstance(value, str):
        reject_mutation(f"{label}:string-value", path, value + "_mutated")
        reject_mutation(f"{label}:string-type", path, False)
        mutation_count += 2
    else:
        raise AssertionError(f"unsupported preregistered type at {label}")

assert mutation_count >= 500, mutation_count

raw_drift_path = scratch / "byte-drift.json"
raw_drift_path.write_bytes(contract_path.read_bytes() + b"\n")
result = subprocess.run(
    [
        sys.executable,
        str(validator_path),
        "validate-contract",
        "--contract",
        str(raw_drift_path),
    ],
    text=True,
    capture_output=True,
    check=False,
)
assert result.returncode == 2
assert "contract bytes do not match v0" in result.stderr

raw = contract_path.read_text(encoding="utf-8")
schema_line = (
    '  "schema": '
    '"agent_bridge.engram_g1_4_candidate_protocol_preregistration_contract.v0",'
)
duplicate = raw.replace(schema_line, f"{schema_line}\n{schema_line}", 1)
assert duplicate != raw
duplicate_path = scratch / "duplicate-field.json"
duplicate_path.write_text(duplicate, encoding="utf-8")
result = subprocess.run(
    [
        sys.executable,
        str(validator_path),
        "validate-contract",
        "--contract",
        str(duplicate_path),
    ],
    text=True,
    capture_output=True,
    check=False,
)
assert result.returncode == 2
assert "duplicate field" in result.stderr

key_pattern = re.compile(r"^[a-z0-9_]+$")
for path, value in walk(contract):
    if isinstance(value, dict):
        for key in value:
            assert key_pattern.fullmatch(key), (path_text(path), key)
threats = contract["threat_model"]["required_threats"]
assert len(threats) == 16
assert len({item["threat"] for item in threats}) == len(threats)
manual_events = contract["human_audit_policy"][
    "manual_safety_audit_required_for"
]
assert len(manual_events) == 8
assert len(set(manual_events)) == len(manual_events)
assert contract["future_decision_rule"]["maximum_exact_mrr_absolute_loss"] == "0.05"
assert contract["future_decision_rule"]["maximum_related_mrr_absolute_loss"] == "0.05"

banned_import_roots = {
    "cryptography",
    "ctypes",
    "nacl",
    "requests",
    "socket",
    "sqlite3",
    "subprocess",
    "urllib",
}
for source_path in (validator_path, helper_path):
    source = source_path.read_text(encoding="utf-8")
    tree = ast.parse(source)
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
print(f"semantic adversarial mutations rejected: {mutation_count}")
PY

ln "$contract" "$scratch/contract-hardlink.json"
python3 "$validator" validate-contract \
  --contract "$scratch/contract-hardlink.json" \
  >"$scratch/hardlink-receipt.json"
python3 - "$scratch/hardlink-receipt.json" <<'PY'
import json
import sys
from pathlib import Path

receipt = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
assert receipt["public_design_contract_only"] is True
assert receipt["g1_4_design_preregistered"] is True
assert receipt["protocol_runner_implementation_authority"] is False
assert receipt["protocol_execution_authority"] is False
assert receipt["candidate_sealed_access_authority"] is False
assert receipt["runtime_promotion_authority"] is False
PY

ln -s "$repo_root/$contract" "$scratch/contract-symlink.json"
if python3 "$validator" validate-contract \
  --contract "$scratch/contract-symlink.json" \
  >"$scratch/symlink.stdout" 2>"$scratch/symlink.stderr"; then
  echo "expected public contract symlink to fail closed" >&2
  exit 1
fi
grep -q "failed to open design" "$scratch/symlink.stderr"

if rg -n 'engram_g14|G1_4_CANDIDATE_PROTOCOL' crates \
  >"$scratch/runtime-surface.txt"; then
  cat "$scratch/runtime-surface.txt" >&2
  echo "G1.4 design preregistration leaked into runtime crates" >&2
  exit 1
fi

echo "engram G1.4 candidate protocol preregistration: PASS"
