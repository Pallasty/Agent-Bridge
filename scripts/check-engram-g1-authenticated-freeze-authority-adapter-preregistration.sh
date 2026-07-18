#!/usr/bin/env bash
set -euo pipefail

repo_root="$(git rev-parse --show-toplevel)"
cd "$repo_root"

validator="scripts/eval/engram_g1_authenticated_freeze_authority_adapter_preregistration.py"
validator_helper="scripts/eval/engram_g1_corpus_design.py"
contract="scripts/eval/fixtures/engram_g1_authenticated_freeze_authority_adapter_preregistration_contract_v0.json"
predecessor_contract="scripts/eval/fixtures/engram_g1_corpus_freeze_review_contract_v1.json"
predecessor_validator="scripts/eval/engram_g1_corpus_freeze_review.py"
predecessor_checker="scripts/check-engram-g1-corpus-freeze-review.sh"
expected_contract_sha256="a9d267056fac1662b478d929b011ef971b309db60182f0f1c7563624571945c0"
expected_validator_sha256="632f93b9c9bfcedeca81916ed34be6b4ce8b7b03b916c060b2d1999d06597fde"
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
  "$predecessor_contract" "$predecessor_validator" "$predecessor_checker" <<'PY'
import hashlib
import json
import sys
from pathlib import Path

receipt = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
contract = Path(sys.argv[2])
validator = Path(sys.argv[3])
predecessor_contract = Path(sys.argv[4])
predecessor_validator = Path(sys.argv[5])
predecessor_checker = Path(sys.argv[6])

digest = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()

assert receipt["schema"] == (
    "agent_bridge.engram_g1_authenticated_freeze_authority_adapter_"
    "preregistration_receipt.v0"
)
assert receipt["contract_id"] == (
    "engram_g1_authenticated_freeze_authority_adapter_preregistration_20260718"
)
assert receipt["contract_sha256"] == digest(contract)
assert receipt["validator_sha256"] == digest(validator)
assert receipt["predecessor_contract_sha256"] == digest(predecessor_contract)
assert receipt["predecessor_validator_sha256"] == digest(predecessor_validator)
assert receipt["predecessor_checker_sha256"] == digest(predecessor_checker)
assert receipt["predecessor_commit"] == (
    "7062869196d1a3ff8bb72572a39700e65130cde4"
)
assert receipt["contract_verdict"] == (
    "AUTHENTICATED_FREEZE_AUTHORITY_ADAPTER_PREREGISTERED_"
    "DESIGN_ONLY_FAIL_CLOSED"
)
assert receipt["public_design_contract_only"] is True
assert receipt["required_signature_algorithm"] == "ed25519"
assert receipt["required_signed_encoding"] == (
    "rfc8785_json_canonicalization_scheme_utf8_v1"
)
assert receipt["required_signer_count"] == 5
assert receipt["trust_ledger_rollback_protection_required"] is True
assert receipt["required_threat_count"] == 12
assert receipt["manual_audit_event_count"] == 7
assert receipt["routine_reversible_validation_requires_human_approval"] is False
assert (
    receipt["unchanged_authenticated_validation_requires_per_run_human_approval"]
    is False
)
assert receipt["reversible_failure_requires_automatic_rollback"] is True
assert receipt["rollback_failure_requires_durable_lesson"] is True
assert receipt["trusted_time_profile"] == (
    "monotonic_clock_plus_durable_boot_epoch_and_signed_time_checkpoint_v1"
)
assert receipt["durable_time_high_water_mark_required"] is True
assert receipt["bearer_capability_receipt_forbidden"] is True
assert receipt["current_state"] == "PENDING_IMPLEMENTATION_PREREQUISITES"
assert receipt["positive_authority_state_representable"] is False

for field, value in receipt.items():
    if (
        field.endswith("_authority")
        or field.endswith("_verified")
        or field.endswith("_implemented")
        or field.endswith("_present")
        or field.startswith("ready_for_")
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
spec = importlib.util.spec_from_file_location("engram_g1_adapter_prereg", validator_path)
assert spec is not None and spec.loader is not None
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def set_path(value, path, replacement):
    cursor = value
    for component in path[:-1]:
        cursor = cursor[component]
    cursor[path[-1]] = replacement


def path_text(path):
    rendered = "contract"
    for component in path:
        if isinstance(component, int):
            rendered += f"[{component}]"
        else:
            rendered += f".{component}"
    return rendered


cases = [
    ("scope-kind", ["scope", "artifact_kind"], "runtime_adapter"),
    ("private-load", ["scope", "loads_private_packets"], True),
    ("adapter-implementation", ["scope", "implements_adapter"], True),
    ("successor-widening", ["scope", "permitted_next_action"], "open_g1_4"),
    ("signature-algorithm", ["future_trust_model", "signature_algorithm"], "hmac"),
    ("canonicalization", ["future_trust_model", "canonical_signed_encoding"], "json"),
    ("packet-trust-root", ["future_trust_model", "packet_may_define_or_replace_trust_root"], True),
    ("partial-role-list", ["future_trust_model", "required_signer_roles_in_order"], contract["future_trust_model"]["required_signer_roles_in_order"][:-1]),
    ("partial-quorum", ["future_trust_model", "required_signature_count"], 4),
    ("duplicate-signer", ["future_trust_model", "all_signers_must_be_distinct"], False),
    ("key-scope", ["future_trust_model", "key_id_epoch_and_role_scope_required"], False),
    ("revocation", ["future_trust_model", "current_non_revoked_key_required_at_claim"], False),
    ("ledger-rollback", ["future_trust_model", "trust_ledger_revision_monotonic_and_rollback_protected"], False),
    ("trust-implemented", ["future_trust_model", "implemented_by_this_gate"], True),
    ("path-resolve-shortcut", ["future_secure_custody", "path_resolution_profile"], "pathlib_resolve_then_open"),
    ("root-descriptor", ["future_secure_custody", "retain_repository_root_descriptor_through_validation"], False),
    ("file-descriptor", ["future_secure_custody", "retain_file_descriptors_through_validation"], False),
    ("descriptor-hash", ["future_secure_custody", "hash_bytes_from_retained_file_descriptors"], False),
    ("fstat-stability", ["future_secure_custody", "fstat_before_and_after_must_match"], False),
    ("final-inode", ["future_secure_custody", "final_name_to_inode_recheck_from_retained_parent_required"], False),
    ("hardlinks-allowed", ["future_secure_custody", "hardlinks_forbidden"], False),
    ("link-count", ["future_secure_custody", "required_file_link_count"], 2),
    ("repository-identity", ["future_secure_custody", "repository_identity_profile"], "path_only"),
    ("mount-identity", ["future_secure_custody", "mount_identity_required"], False),
    ("remote-filesystem-allowed", ["future_secure_custody", "network_fuse_and_remote_filesystems_forbidden"], False),
    ("custody-implemented", ["future_secure_custody", "implemented_by_this_gate"], True),
    ("custody-verified", ["future_secure_custody", "secure_custody_capture_verified"], True),
    ("g13-binding", ["future_authenticated_envelope", "binds_exact_g1_3_contract_validator_and_checker"], False),
    ("manifest-binding", ["future_authenticated_envelope", "binds_exact_private_manifest_bytes"], False),
    ("digest-alias", ["future_authenticated_envelope", "private_digest_values_must_not_alias_public_bindings"], False),
    ("cross-scope-replay", ["future_authenticated_envelope", "cross_stage_cross_scope_or_cross_repository_use_forbidden"], False),
    ("label-laundering", ["future_authenticated_envelope", "label_only_or_claimed_real_evidence_forbidden"], False),
    ("envelope-implemented", ["future_authenticated_envelope", "implemented_by_this_gate"], True),
    ("short-nonce", ["future_replay_lifecycle", "minimum_nonce_bytes"], 16),
    ("non-monotonic-sequence", ["future_replay_lifecycle", "sequence_monotonic_per_repository_scope"], False),
    ("trusted-time", ["future_replay_lifecycle", "trusted_monotonic_time_required"], False),
    ("time-profile", ["future_replay_lifecycle", "trusted_time_profile"], "local_wall_clock"),
    ("time-high-water", ["future_replay_lifecycle", "durable_time_high_water_mark_required"], False),
    ("boot-epoch", ["future_replay_lifecycle", "boot_epoch_change_requires_fresh_signed_envelope"], False),
    ("clock-regression", ["future_replay_lifecycle", "clock_regression_fails_closed"], False),
    ("local-time-only", ["future_replay_lifecycle", "local_wall_clock_alone_is_forbidden"], False),
    ("append-ledger", ["future_replay_lifecycle", "durable_append_only_claim_ledger_required"], False),
    ("non-atomic-claim", ["future_replay_lifecycle", "single_use_compare_and_swap_claim_required"], False),
    ("claim-binding", ["future_replay_lifecycle", "claim_receipt_binds_envelope_nonce_sequence_scope_and_digest"], False),
    ("post-denial-replay", ["future_replay_lifecycle", "replay_after_success_or_fail_closed_denial_forbidden"], False),
    ("claim-revocation", ["future_replay_lifecycle", "key_revocation_and_currentness_rechecked_at_claim"], False),
    ("replay-implemented", ["future_replay_lifecycle", "implemented_by_this_gate"], True),
    ("raw-receipt", ["future_capability_receipt", "receipt_contains_raw_identity_query_or_manifest_material"], True),
    ("reusable-receipt", ["future_capability_receipt", "receipt_is_single_use"], False),
    ("bearer-receipt", ["future_capability_receipt", "bearer_receipt_forbidden"], False),
    ("consumer-binding", ["future_capability_receipt", "receipt_binds_authorized_consumer_key_and_process_identity"], False),
    ("receipt-scope", ["future_capability_receipt", "receipt_scope_must_equal_authenticated_envelope_scope"], False),
    ("runtime-successor", ["future_capability_receipt", "only_permitted_successor"], "enable_runtime"),
    ("routine-human-gate", ["human_audit_policy", "routine_reversible_validation_requires_human_approval"], True),
    ("unchanged-human-gate", ["human_audit_policy", "unchanged_authenticated_validation_requires_per_run_human_approval"], True),
    ("denial-human-gate", ["human_audit_policy", "fail_closed_denial_requires_human_approval"], True),
    ("rollback-disabled", ["human_audit_policy", "reversible_failure_requires_automatic_rollback"], False),
    ("rollback-lesson-disabled", ["human_audit_policy", "rollback_failure_requires_durable_lesson"], False),
    ("manual-audit-per-run", ["human_audit_policy", "manual_safety_audit_is_a_per_run_gate"], True),
    ("manual-audit-event-removed", ["human_audit_policy", "manual_safety_audit_required_for"], contract["human_audit_policy"]["manual_safety_audit_required_for"][:-1]),
    ("audit-inference", ["human_audit_policy", "manual_audit_outcome_may_be_inferred_by_structural_validator"], True),
    ("threat-controls-current", ["threat_model", "all_controls_are_future_requirements_not_current_implementation"], False),
    ("positive-threat-verdict", ["threat_model", "unimplemented_control_verdict"], "APPROVED"),
    ("weakened-threat-control", ["threat_model", "required_threats", 0, "required_control"], "label_only"),
    ("implemented-threat-control", ["threat_model", "required_threats", 0, "current_status"], "implemented"),
    ("positive-current-state", ["state_machine", "current_state"], "AUTHORIZED"),
    ("positive-state-list", ["state_machine", "representable_current_states"], ["AUTHORIZED"]),
    ("positive-state-representable", ["state_machine", "positive_authority_state_representable"], True),
    ("adapter-present", ["state_machine", "adapter_implementation_present"], True),
    ("g14-open", ["state_machine", "g1_4_candidate_protocol_preregistration_open"], True),
    ("predecessor-commit", ["predecessor", "commit"], "0" * 40),
    ("predecessor-contract", ["predecessor", "contract_sha256"], "0" * 64),
    ("predecessor-validator", ["predecessor", "validator_sha256"], "0" * 64),
    ("predecessor-checker", ["predecessor", "checker_sha256"], "0" * 64),
]

for field in sorted(contract["boundaries"]):
    cases.append((f"boundary-{field}", ["boundaries", field], True))
for field in sorted(contract["future_capability_receipt"]):
    if field.startswith("grants_"):
        cases.append((f"capability-{field}", ["future_capability_receipt", field], True))

assert len(cases) >= 90
for label, path, replacement in cases:
    candidate = copy.deepcopy(contract)
    set_path(candidate, path, replacement)
    try:
        module.validate_contract_semantics(candidate)
    except module.InputError as exc:
        assert path_text(path) in str(exc), (label, path_text(path), str(exc))
    else:
        raise AssertionError(f"semantic mutation accepted: {label}")

extra = copy.deepcopy(contract)
extra["unexpected_authority_surface"] = False
try:
    module.validate_contract_semantics(extra)
except module.InputError as exc:
    assert "contract fields mismatch" in str(exc)
else:
    raise AssertionError("unexpected top-level field accepted")

byte_drift = copy.deepcopy(contract)
byte_drift["scope"]["implements_adapter"] = True
byte_drift_path = scratch / "byte-drift.json"
byte_drift_path.write_text(json.dumps(byte_drift, indent=2) + "\n", encoding="utf-8")
result = subprocess.run(
    [sys.executable, str(validator_path), "validate-contract", "--contract", str(byte_drift_path)],
    text=True,
    capture_output=True,
    check=False,
)
assert result.returncode == 2
assert "contract bytes do not match v0" in result.stderr

raw = contract_path.read_text(encoding="utf-8")
duplicate = raw.replace(
    '  "schema": "agent_bridge.engram_g1_authenticated_freeze_authority_adapter_preregistration_contract.v0",',
    '  "schema": "agent_bridge.engram_g1_authenticated_freeze_authority_adapter_preregistration_contract.v0",\n'
    '  "schema": "agent_bridge.engram_g1_authenticated_freeze_authority_adapter_preregistration_contract.v0",',
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
assert receipt["secure_custody_capture_verified"] is False
assert receipt["secure_custody_capture_implemented"] is False
assert receipt["authenticated_freeze_authority_verified"] is False
PY

ln -s "$repo_root/$contract" "$scratch/contract-symlink.json"
if python3 "$validator" validate-contract \
  --contract "$scratch/contract-symlink.json" \
  >"$scratch/symlink.stdout" 2>"$scratch/symlink.stderr"; then
  echo "expected public contract symlink to fail closed" >&2
  exit 1
fi
grep -q "failed to open design" "$scratch/symlink.stderr"

echo "engram G1 authenticated freeze authority adapter preregistration: PASS"
