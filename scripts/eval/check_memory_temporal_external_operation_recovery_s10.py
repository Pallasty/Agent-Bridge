#!/usr/bin/env python3
"""Fail-closed checker for the frozen S10 lookup-only recovery tree.

Future successor trees must run this full-digest checker against an archived
S10 integration tree and separately validate their retained S10 projection.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import re
import sys
import tomllib
from pathlib import Path
from types import ModuleType
from typing import Any


STATUS = (
    "LOOKUP_ONLY_OPERATION_RECOVERY_PROTOCOL_PREREGISTERED_SYNTHETIC_JOURNAL_"
    "NO_PROVIDER_NO_OWNER_TRUST_ANCHOR_NOT_AUTHORIZED_NOT_TRANSPORT"
)
DECISION = "BLOCKED_FAIL_CLOSED"
FEATURE = "temporal-evidence-s10-operation-recovery-synthetic"
S9_FEATURE = "temporal-evidence-s9-external-authority-provider-synthetic"
BASE_COMMIT = "2e828d7b86444770c3ef3cd40ac17f26cac6fb0e"
S9_FEATURE_COMMIT = "846ea7c92490dcd35a8a2f2aa15c99c7c87f40dc"

CONTRACT_PATH = (
    "docs/design/fixtures/biocortex-ab-track-b-external-operation-recovery-s10-v0.json"
)
GATE_PATH = "docs/design/fixtures/biocortex-ab-track-b-successor-admission-gate-s10-v0.json"
SOURCE_PATH = "crates/store/src/temporal_replay_transport/external_operation_recovery.rs"
STORE_CARGO_PATH = "crates/store/Cargo.toml"
PARENT_MODULE_PATH = "crates/store/src/temporal_replay_transport.rs"
CONTRACT_SHA256 = "da3566f13df522958f05c871ad4679d89cda9b888ba8aa4eb4caaee4c457fb88"
GATE_SHA256 = "9bedb7ef289f31a6b9409875d3b8e6fb3b4784aa972a329de229565caa5b1eb7"
SOURCE_SHA256 = "850ddf4c47c76e9008671d44c47ba944b384744a4c50640e134e6c24008d90e4"
STORE_CARGO_SHA256 = "028c36cdd328c5256067f19a1ada948bb1150705a2f7d1b7c4b2da3e16f40a88"
PARENT_MODULE_SHA256 = "31bd2379dc47454d78a7f1f9fa0a2df6d663d7eebfaeca6be4b9b410afbcaddf"

S9_CONTRACT_PATH = (
    "docs/design/fixtures/biocortex-ab-track-b-external-authority-provider-s9-v0.json"
)
S9_GATE_PATH = "docs/design/fixtures/biocortex-ab-track-b-successor-admission-gate-s9-v0.json"
S9_SOURCE_PATH = "crates/store/src/temporal_replay_transport/external_restore_authority.rs"
S9_CHECKER_PATH = "scripts/eval/check_memory_temporal_external_authority_provider_s9.py"
S9_CONTRACT_SHA256 = "d537b80ce0d2bbb3c4d01a988a9685432672078eae07d0b976b1268a27526fc4"
S9_GATE_SHA256 = "2181254b1e66444445734edb2f7dab70a85c0be5316d449f7152559d7e6428e5"
S9_SOURCE_SHA256 = "dd92c2b064c1a4c1e5a4119777f1b5bf21a46d0fc9cb77656845f05e48655d9b"
S9_CHECKER_SHA256 = "ad7e373f539b780dd71af7f226464412442e3274ce98b0246329c0401a42995f"

POLICY = b"agent-bridge/track-b/external-operation-recovery/v1"
QUERY_DOMAIN = b"agent-bridge/track-b/external-operation-recovery/lookup-query/v1"
OBSERVATION_DOMAIN = (
    b"agent-bridge/track-b/external-operation-recovery/lookup-observation/v1"
)
RESULT_ID_DOMAIN = b"agent-bridge/track-b/external-operation-recovery/result-id/v1"
ALGORITHM = b"Ed25519"
LOOKUP_PROFILE = b"LOOKUP_ONLY_IDEMPOTENT_NO_SUBMIT_NO_RETRY_NO_CACHE_NO_WALL_CLOCK"
S9_CONTRACT = bytes.fromhex(S9_CONTRACT_SHA256)
RFC8032_SEED = bytes.fromhex(
    "9d61b19deffd5a60ba844af492ec2cc44449c5697b326919703bac031cae7f60"
)
RFC8032_PUBLIC_KEY = bytes.fromhex(
    "d75a980182b10ab7d54bfed3c964073a0ee172f3daa62325af021a68f707511a"
)

RECOVERY_STATES = ("COMMITTED", "NOT_FOUND", "PENDING", "CONFLICT", "INDETERMINATE")
REMAINING_GAPS = (
    "AUTHORITY_POLICY_CUSTODY_UNRESOLVED",
    "CAPTURE_PROVENANCE_UNATTESTED",
    "CROSS_BIOCORTEX_OPAQUE_HANDLE_TRANSPORT_UNIMPLEMENTED",
    "PHYSICAL_PRIVACY_DELETION_UNRESOLVED",
    "PRODUCTION_PRODUCER_PROFILE_UNADMITTED",
)
OPERATIONAL_GAPS = (
    "CURRENTNESS_CHALLENGE_UNIQUENESS_UNATTESTED",
    "EXPECTED_EPOCH_CURRENTNESS_EXTERNAL_CUSTODY_UNATTESTED",
    "INSTANT_REVOCATION_UNAVAILABLE_WITH_LOCAL_CONSUME",
    "OLD_EPOCH_KEY_DESTRUCTION_UNATTESTED",
    "SAME_EPOCH_RESTORE_DETECTION_UNAVAILABLE",
    "DURABLE_CHALLENGE_UNIQUENESS_UNAVAILABLE",
    "EXTERNAL_AUTHORITY_PROVIDER_UNIMPLEMENTED",
    "EXTERNAL_KEY_CUSTODIAN_UNIMPLEMENTED",
    "OWNER_PINNED_TRUST_ANCHOR_UNAVAILABLE",
    "PROVIDER_CLOCK_AND_FRESHNESS_UNATTESTED",
    "PROVIDER_FAILURE_RESULT_AMBIGUITY_UNRESOLVED",
    "PROVIDER_KEY_ROTATION_AND_REVOCATION_UNATTESTED",
    "PROVIDER_LINEARIZABILITY_UNATTESTED",
    "PROVIDER_SPLIT_BRAIN_FENCING_UNATTESTED",
    "PROVIDER_STATE_ROLLBACK_UNATTESTED",
    "RECOVERY_JOURNAL_EXTERNAL_DURABILITY_UNATTESTED",
    "RECOVERY_LOOKUP_LINEARIZABILITY_UNATTESTED",
    "RECOVERY_OPERATION_SUBMISSION_ATOMICITY_UNIMPLEMENTED",
    "RECOVERY_OBSERVATION_TO_S9_REVERIFICATION_UNIMPLEMENTED",
)

CONTRACT_BOUNDARY_KEYS = (
    "biocortex_runtime_influence",
    "bridge_feature_forwarding_present",
    "bridge_runtime_caller_present",
    "cross_repository_transport_authorized",
    "external_durable_journal_present",
    "external_owner_trust_anchor_present",
    "network_client_present",
    "production_constructor_present",
    "production_provider_adapter_present",
    "recovered_currentness_token_present",
    "state_store_surface_present",
    "successor_payload_admitted",
)
CONTRACT_FAILURE_KEYS = (
    "conflict_returns_observation",
    "indeterminate_returns_observation",
    "invalid_signature_returns_observation",
    "malformed_response_returns_observation",
    "not_found_resubmits_currentness",
    "not_found_returns_observation",
    "pending_returns_observation",
    "provider_failure_uses_local_fallback",
    "query_binding_mismatch_returns_observation",
    "timeout_or_unavailable_returns_observation",
)
CONTRACT_NEGATIVE_EVIDENCE_KEYS = (
    "adapter_reconstruction_with_shared_journal_proves_external_durability",
    "external_journal_linearizability_proved",
    "journal_loss_distinguishes_not_executed_from_rollback",
    "journal_loss_returns_observation",
    "lookup_closes_provider_failure_ambiguity",
    "lookup_is_admission_or_currentness",
    "post_lookup_revocation_can_recall_observation",
    "production_adapter_lookup_side_effect_freedom_proved",
    "same_epoch_restore_detected",
    "synthetic_signature_proves_owner_trust",
)
CONTRACT_TEST_MATRIX_KEYS = (
    "adapter_reconstruction_shared_journal_sequence_model",
    "all_non_committed_outcomes_fail_closed",
    "all_provider_failures_no_fallback",
    "committed_exact_result_private_non_admission_observation",
    "deterministic_ed25519_known_answer",
    "exact_repeat_lookup_read_only_and_stable",
    "journal_loss_ambiguity_negative_evidence",
    "lookup_never_submits_or_retries_currentness",
    "operation_request_conflict_fail_closed",
    "post_lookup_revocation_recall_negative_evidence",
    "query_field_tamper_rejection",
    "receipt_field_and_signature_tamper_rejection",
    "trust_pin_signer_and_provider_identity_rejection",
    "zero_clock_cache_network_serializable_token_or_production_constructor",
)
GATE_AUTHORIZATION_KEYS = (
    "lookup_observation_is_not_admission_or_currentness",
    "lookup_only_trait_does_not_prove_adapter_side_effect_freedom",
    "not_found_does_not_authorize_resubmission",
    "owner_pin_must_be_external_to_signed_response",
    "recovery_contract_does_not_authorize_transport",
    "repository_owner_research_permission_is_not_provider_trust_or_durability_attestation",
    "synthetic_journal_is_not_external_durability_evidence",
    "synthetic_test_key_is_not_owner_pinned_production_trust",
)
CONTRACT_TOP_LEVEL_KEYS = (
    "boundary",
    "decision",
    "dependency",
    "failure_semantics",
    "implementation",
    "known_vector",
    "negative_evidence",
    "operational_gap_codes",
    "predecessor",
    "protocol",
    "remaining_gap_codes",
    "schema",
    "status",
    "test_matrix",
)
GATE_TOP_LEVEL_KEYS = (
    "admission",
    "authorization_semantics",
    "boundary",
    "decision",
    "operational_gap_codes",
    "predecessor",
    "recovery_preregistration",
    "remaining_gap_codes",
    "required_successor_identity",
    "schema",
    "status",
)


class CheckFailure(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise CheckFailure(message)


def read_bytes(repo: Path, relative: str) -> bytes:
    path = repo / relative
    require(path.is_file() and not path.is_symlink(), f"missing/non-regular artifact: {relative}")
    return path.read_bytes()


def read_text(repo: Path, relative: str) -> str:
    return read_bytes(repo, relative).decode("utf-8")


def sha256(repo: Path, relative: str) -> str:
    return hashlib.sha256(read_bytes(repo, relative)).hexdigest()


def reject_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    output: dict[str, Any] = {}
    for key, value in pairs:
        require(key not in output, f"duplicate JSON key: {key}")
        output[key] = value
    return output


def load_json(repo: Path, relative: str) -> dict[str, Any]:
    try:
        value = json.loads(read_text(repo, relative), object_pairs_hook=reject_duplicates)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CheckFailure(f"invalid JSON {relative}: {exc}") from exc
    require(isinstance(value, dict), f"top-level JSON object required: {relative}")
    return value


def require_exact_boolean_map(
    value: Any, expected_keys: tuple[str, ...], expected_value: bool, message: str
) -> None:
    require(isinstance(value, dict), message)
    require(set(value) == set(expected_keys), message)
    require(all(value[key] is expected_value for key in expected_keys), message)


def type_strict_equal(actual: Any, expected: Any) -> bool:
    if type(actual) is not type(expected):
        return False
    if isinstance(expected, dict):
        return set(actual) == set(expected) and all(
            type_strict_equal(actual[key], expected[key]) for key in expected
        )
    if isinstance(expected, list):
        return len(actual) == len(expected) and all(
            type_strict_equal(left, right) for left, right in zip(actual, expected)
        )
    return bool(actual == expected)


def require_exact_value(actual: Any, expected: Any, message: str) -> None:
    require(type_strict_equal(actual, expected), message)


def feature_is_reachable(features: dict[str, Any], roots: list[str], target: str) -> bool:
    """Follow only local feature aliases; dependency feature syntax is not a local edge."""
    pending = list(roots)
    visited: set[str] = set()
    while pending:
        feature = pending.pop()
        if feature == target:
            return True
        if feature in visited or feature not in features:
            continue
        visited.add(feature)
        edges = features[feature]
        require(isinstance(edges, list), f"Cargo feature is not a list: {feature}")
        for edge in edges:
            require(isinstance(edge, str), f"Cargo feature edge is not a string: {feature}")
            if edge in features:
                pending.append(edge)
            elif edge == target:
                return True
    return False


def import_s9_reference(repo: Path) -> ModuleType:
    require(sha256(repo, S9_CHECKER_PATH) == S9_CHECKER_SHA256, "S9 checker digest drift")
    path = repo / S9_CHECKER_PATH
    spec = importlib.util.spec_from_file_location("s10_pinned_s9_ed25519_reference", path)
    require(spec is not None and spec.loader is not None, "cannot load pinned S9 reference")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def known_vector(repo: Path) -> dict[str, str | int]:
    reference = import_s9_reference(repo)
    repeated = lambda value: bytes([value]) * 32
    provider_incarnation = repeated(0x61)
    lookup_query_id = repeated(0x31)
    lookup_challenge = repeated(0x32)
    original_operation_id = repeated(0x21)
    original_challenge = repeated(0x22)
    original_request = repeated(0x23)
    trust_policy = repeated(0x71)
    journal_generation = repeated(0x72)
    original_decision = repeated(0x24)

    query_message = reference.framed_message(
        QUERY_DOMAIN,
        [
            POLICY,
            ALGORITHM,
            LOOKUP_PROFILE,
            S9_CONTRACT,
            b"owner-selected-provider-v1",
            b"track-b-authority",
            b"tenant-a",
            b"agent-bridge-store",
            b"authority-cluster-a",
            provider_incarnation,
            lookup_query_id,
            lookup_challenge,
            original_operation_id,
            original_challenge,
            original_request,
            trust_policy,
        ],
    )
    query_sha256 = hashlib.sha256(query_message).digest()
    operation_committed_revision = (43).to_bytes(8, "big")
    observed_journal_revision = (43).to_bytes(8, "big")
    record_sequence = (9).to_bytes(8, "big")
    result_id = reference.framed_digest(
        RESULT_ID_DOMAIN,
        [
            POLICY,
            S9_CONTRACT,
            original_operation_id,
            original_challenge,
            original_request,
            operation_committed_revision,
            journal_generation,
            record_sequence,
            original_decision,
        ],
    )
    observation_message = reference.framed_message(
        OBSERVATION_DOMAIN,
        [
            POLICY,
            ALGORITHM,
            LOOKUP_PROFILE,
            S9_CONTRACT,
            query_sha256,
            b"COMMITTED",
            original_operation_id,
            original_challenge,
            original_request,
            b"authority-cluster-a",
            provider_incarnation,
            (7).to_bytes(8, "big"),
            operation_committed_revision,
            observed_journal_revision,
            journal_generation,
            record_sequence,
            original_decision,
            result_id,
            b"authority-signer",
            (3).to_bytes(8, "big"),
        ],
    )
    public_key = reference.ed25519_public_key(RFC8032_SEED)
    signature = reference.ed25519_sign(RFC8032_SEED, observation_message)
    require(public_key == RFC8032_PUBLIC_KEY, "independent Ed25519 public-key drift")
    require(
        reference.ed25519_verify(public_key, observation_message, signature),
        "independent Ed25519 signature did not verify",
    )
    return {
        "ed25519_public_key": public_key.hex(),
        "ed25519_signature": signature.hex(),
        "observed_journal_revision": 43,
        "operation_committed_revision": 43,
        "query_sha256": query_sha256.hex(),
        "receipt_message_sha256": hashlib.sha256(observation_message).hexdigest(),
        "result_id": result_id.hex(),
        "stored_s9_decision_sha256": original_decision.hex(),
        "stored_s9_request_sha256": original_request.hex(),
    }


def check_predecessor(repo: Path) -> None:
    require(sha256(repo, S9_CONTRACT_PATH) == S9_CONTRACT_SHA256, "S9 contract digest drift")
    require(sha256(repo, S9_GATE_PATH) == S9_GATE_SHA256, "S9 gate digest drift")
    require(sha256(repo, S9_SOURCE_PATH) == S9_SOURCE_SHA256, "S9 source digest drift")


def check_contract(repo: Path, vectors: dict[str, str | int]) -> None:
    require(sha256(repo, CONTRACT_PATH) == CONTRACT_SHA256, "S10 contract digest drift")
    contract = load_json(repo, CONTRACT_PATH)
    require(set(contract) == set(CONTRACT_TOP_LEVEL_KEYS), "S10 top-level contract keys drift")
    require(
        contract["schema"]
        == "agent_bridge.memory_temporal_external_operation_recovery_contract_s10.v0",
        "S10 schema drift",
    )
    require(contract["status"] == STATUS and contract["decision"] == DECISION, "S10 outcome drift")
    require_exact_value(
        contract["dependency"],
        {
            "default_enabled": False,
            "depends_on_feature": S9_FEATURE,
            "feature": FEATURE,
        },
        "S10 feature dependency drift",
    )
    require_exact_boolean_map(contract["boundary"], CONTRACT_BOUNDARY_KEYS, False, "S10 boundary drift")
    require_exact_boolean_map(
        contract["failure_semantics"], CONTRACT_FAILURE_KEYS, False, "S10 failure semantics drift"
    )
    require_exact_value(
        contract["implementation"],
        {
            "module_path": SOURCE_PATH,
            "module_visibility": "private_child_of_private_s6_module",
            "network_or_transport": False,
            "production_lookup_implementation": False,
            "recovery_permit_constructor_scope": "cfg_test_only",
            "signed_response_verification": "exact_framed_ed25519",
            "state_store_integration": False,
            "synthetic_journal_scope": "SHARED_PROCESS_MEMORY_SEQUENCE_MODEL_NOT_DURABILITY_EVIDENCE",
        },
        "S10 implementation declaration drift",
    )
    require_exact_value(contract["known_vector"], vectors, "S10 independent known vector drift")
    require_exact_boolean_map(
        contract["negative_evidence"],
        CONTRACT_NEGATIVE_EVIDENCE_KEYS,
        False,
        "S10 negative-evidence drift",
    )
    require(contract["remaining_gap_codes"] == list(REMAINING_GAPS), "remaining gaps drift")
    require(contract["operational_gap_codes"] == list(OPERATIONAL_GAPS), "operational gaps drift")
    require_exact_value(
        contract["predecessor"],
        {
            "s9_contract_sha256": S9_CONTRACT_SHA256,
            "s9_feature_commit": S9_FEATURE_COMMIT,
            "s9_integration_commit": BASE_COMMIT,
            "s9_source_sha256": S9_SOURCE_SHA256,
            "s9_successor_gate_sha256": S9_GATE_SHA256,
        },
        "S10 predecessor binding drift",
    )
    require_exact_value(
        contract["protocol"],
        {
            "admission_token_returned": False,
            "allowed_outcomes": list(RECOVERY_STATES),
            "committed_output": "PRIVATE_RECOVERY_OBSERVATION_NOT_ADMISSION",
            "exact_lookup_key": "OPERATION_ID_PLUS_S9_REQUEST_SHA256",
            "lookup_can_submit_or_mutate": False,
            "lookup_profile": LOOKUP_PROFILE.decode(),
            "not_found_requires_new_admission_attempt": True,
            "repeated_exact_lookup_must_be_read_only": True,
            "s9_currentness_retried": False,
        },
        "S10 lookup protocol drift",
    )
    require_exact_boolean_map(
        contract["test_matrix"], CONTRACT_TEST_MATRIX_KEYS, True, "S10 test-matrix drift"
    )


def check_gate(repo: Path) -> None:
    require(sha256(repo, GATE_PATH) == GATE_SHA256, "S10 successor-gate digest drift")
    gate = load_json(repo, GATE_PATH)
    require(set(gate) == set(GATE_TOP_LEVEL_KEYS), "S10 top-level gate keys drift")
    require(
        gate["schema"] == "agent_bridge.memory_temporal_successor_admission_gate_s10.v0",
        "S10 successor schema drift",
    )
    require(gate["status"] == "NOT_ADMITTED" and gate["decision"] == DECISION, "gate opened")
    require_exact_value(
        gate["admission"],
        {
            "admitted": False,
            "admission_artifact_must_be_external_to_packet": True,
            "authority_decision_receipt": None,
            "authority_policy_custodian_receipt": None,
            "build_attestation": None,
            "capture_authorization_receipt": None,
            "capture_provenance_receipt": None,
            "deletion_mechanism_receipt": None,
            "destination_receiver_identity": None,
            "durable_challenge_uniqueness_receipt": None,
            "external_currentness_provider_receipt": None,
            "external_key_custodian_receipt": None,
            "external_operation_recovery_receipt": None,
            "externally_pinned_allowlist_receipt": None,
            "key_custody_receipts": None,
            "old_key_destruction_receipt": None,
            "owner_pinned_provider_trust_anchor": None,
            "producer_runtime_identity": None,
            "provider_linearizability_receipt": None,
            "provider_rollback_protection_receipt": None,
            "provider_split_brain_fencing_receipt": None,
            "recovery_journal_durability_receipt": None,
            "revocation_state_receipt": None,
        },
        "admission receipt set drift",
    )
    require_exact_boolean_map(
        gate["authorization_semantics"],
        GATE_AUTHORIZATION_KEYS,
        True,
        "authorization caveat drift",
    )
    require_exact_value(
        gate["boundary"],
        {
            "biocortex_runtime_influence": False,
            "bridge_runtime_caller_present": False,
            "cross_repository_transport_authorized": False,
            "external_currentness_provider_present": False,
            "external_key_custodian_present": False,
            "external_operation_recovery_provider_present": False,
            "external_owner_trust_anchor_present": False,
            "live_binding_satisfied": False,
            "production_profile_active": False,
            "recovery_observation_admits": False,
            "side_effects_unlocked": "NONE",
        },
        "successor boundary opened",
    )
    require(gate["remaining_gap_codes"] == list(REMAINING_GAPS), "gate remaining gaps drift")
    require(gate["operational_gap_codes"] == list(OPERATIONAL_GAPS), "gate operational gaps drift")
    require_exact_value(
        gate["predecessor"],
        {
            "s9_contract_sha256": S9_CONTRACT_SHA256,
            "s9_feature_commit": S9_FEATURE_COMMIT,
            "s9_integration_commit": BASE_COMMIT,
            "s9_source_sha256": S9_SOURCE_SHA256,
            "s9_successor_gate_sha256": S9_GATE_SHA256,
        },
        "gate predecessor binding drift",
    )
    require_exact_value(
        gate["recovery_preregistration"],
        {
            "contract_sha256": CONTRACT_SHA256,
            "contract_status": STATUS,
            "external_durable_journal_present": False,
            "lookup_can_submit_or_retry": False,
            "lookup_profile": LOOKUP_PROFILE.decode(),
            "private_observation_is_admission": False,
            "production_provider_present": False,
            "synthetic_journal_is_production_evidence": False,
        },
        "recovery preregistration drift",
    )
    require_exact_value(
        gate["required_successor_identity"],
        {
            "candidate_id_must_change": True,
            "exact_schema_digest_required": True,
            "independent_authentication_domain_required": True,
            "independent_payload_profile_required": True,
            "new_schema_id_required": True,
            "new_version_required": True,
            "successor_candidate_id": None,
            "successor_payload_profile_sha256": None,
            "successor_schema_id": None,
            "successor_schema_sha256": None,
            "successor_transport_domain": None,
        },
        "successor identity requirements drift",
    )


def strip_rust_comments(source: str) -> str:
    source = re.sub(r"(?s)/\*.*?\*/", "", source)
    return re.sub(r"(?m)//.*$", "", source)


def struct_fields(source: str, name: str) -> list[str]:
    match = re.search(rf"(?ms)^struct {re.escape(name)} \{{\n(?P<body>.*?)^\}}", source)
    require(match is not None, f"missing Rust struct: {name}")
    return re.findall(r"(?m)^    ([a-z][a-z0-9_]*):", match.group("body"))


def rust_u8_array(source: str, name: str, length: int) -> bytes:
    match = re.search(
        rf"(?ms)^    const {re.escape(name)}: \[u8; {length}\] = \[(?P<body>.*?)^    \];",
        source,
    )
    require(match is not None, f"missing Rust byte vector: {name}")
    values = bytes(int(value, 16) for value in re.findall(r"0x([0-9a-fA-F]{2})", match.group("body")))
    require(len(values) == length, f"Rust byte-vector length drift: {name}")
    return values


def bridge_surface_text(repo: Path) -> str:
    root = repo / "crates/bridge"
    require(root.is_dir() and not root.is_symlink(), "missing/non-regular Bridge crate")
    chunks: list[str] = []
    for directory, directory_names, file_names in os.walk(root, followlinks=False):
        base = Path(directory)
        for name in directory_names:
            require(not (base / name).is_symlink(), f"symlink in Bridge source tree: {base / name}")
        for name in sorted(file_names):
            path = base / name
            if path.suffix not in {".rs", ".toml"}:
                continue
            require(path.is_file() and not path.is_symlink(), f"non-regular Bridge source: {path}")
            chunks.append(path.read_text(encoding="utf-8"))
    return "\n".join(chunks)


def check_source(repo: Path, vectors: dict[str, str | int]) -> int:
    require(sha256(repo, SOURCE_PATH) == SOURCE_SHA256, "S10 Rust source digest drift")
    require(sha256(repo, STORE_CARGO_PATH) == STORE_CARGO_SHA256, "Store Cargo digest drift")
    require(sha256(repo, PARENT_MODULE_PATH) == PARENT_MODULE_SHA256, "S10 parent-module digest drift")
    cargo = tomllib.loads(read_text(repo, STORE_CARGO_PATH))
    features = cargo.get("features", {})
    require(isinstance(features, dict), "Cargo features table missing")
    require(features.get(FEATURE) == [S9_FEATURE], "S10 feature dependency drift")
    default_features = features.get("default", [])
    require(isinstance(default_features, list), "Cargo default feature list drift")
    require(
        not feature_is_reachable(features, default_features, FEATURE),
        "S10 feature became transitively default",
    )

    parent = read_text(repo, PARENT_MODULE_PATH)
    library = read_text(repo, "crates/store/src/lib.rs")
    bridge = bridge_surface_text(repo)
    source = read_text(repo, SOURCE_PATH)
    require(
        f'#[cfg(feature = "{FEATURE}")]\nmod external_operation_recovery;' in parent,
        "private S10 module gate missing",
    )
    require("pub mod external_operation_recovery" not in parent, "S10 module became public")
    require("pub use external_operation_recovery" not in parent + library, "S10 re-export forbidden")
    require(
        FEATURE not in library + bridge and "external_operation_recovery" not in library + bridge,
        "S10 leaked to library or Bridge surface",
    )

    split = source.split("#[cfg(test)]\nmod tests", 1)
    require(len(split) == 2, "S10 synthetic implementation is not cfg(test)-isolated")
    production, tests = split
    code = strip_rust_comments(production)
    for forbidden in (
        "StateStore",
        "std::net",
        "tokio::net",
        "reqwest::",
        "hyper::",
        "tonic::",
        "TcpStream",
        "UdpSocket",
        "UnixStream",
        "SocketAddr",
        "std::fs",
        "OpenOptions",
        "SystemTime",
        "Instant::now",
        "std::time",
        "serde::",
        "Serialize",
    ):
        require(forbidden not in code, f"forbidden S10 production surface: {forbidden}")
    require("impl ExternalOperationRecoveryTrustPermitV1" not in production, "production permit constructor added")
    require("impl recovery_provider_seal::Sealed" not in production, "production provider added")
    require("fn permit_for(" in tests, "test-only permit constructor missing")
    require("struct SyntheticLookupOnlyProviderV1" in tests, "synthetic lookup provider missing")
    require("struct SyntheticJournalV1" in tests, "synthetic journal missing")
    require("Arc<Mutex<SyntheticJournalV1>>" in tests, "shared-process sequence model missing")

    require(source.count("pub(super) trait Sealed {}") == 1, "sealed-interface count drift")
    require(
        "trait ExternalOperationRecoveryProviderV1: recovery_provider_seal::Sealed" in source,
        "recovery lookup interface is not sealed",
    )
    trait_match = re.search(
        r"(?ms)^trait ExternalOperationRecoveryProviderV1.*?\{(?P<body>.*?)^\}", source
    )
    require(trait_match is not None, "recovery trait body missing")
    require(
        re.findall(r"\bfn\s+([a-zA-Z0-9_]+)", trait_match.group("body")) == ["lookup_operation"],
        "recovery trait gained a non-lookup method",
    )
    require(
        not re.search(r"\bfn\s+(submit|retry|request_currentness|consume|activate|mutate)\b", code),
        "S10 production code gained submit/currentness mutation",
    )

    require(
        struct_fields(source, "ExternalOperationRecoveryQueryV1")
        == [
            "provider_profile_id",
            "authority_namespace_id",
            "tenant_id",
            "audience",
            "provider_cluster_id",
            "provider_incarnation",
            "lookup_query_id",
            "lookup_challenge",
            "original_operation_id",
            "original_challenge",
            "original_request_sha256",
            "trust_policy_sha256",
        ],
        "lookup query field shape drift",
    )
    require(
        struct_fields(source, "SignedExternalOperationRecoveryObservationV1")
        == [
            "lookup_query_sha256",
            "state",
            "original_operation_id",
            "original_challenge",
            "original_request_sha256",
            "provider_cluster_id",
            "provider_incarnation",
            "leader_term",
            "operation_committed_revision",
            "observed_journal_revision",
            "journal_generation_id",
            "journal_record_sequence",
            "original_decision_sha256",
            "result_id",
            "signer_key_id",
            "signer_key_version",
            "ed25519_signature",
        ],
        "signed recovery observation field shape drift",
    )
    require(
        struct_fields(source, "VerifiedExternalOperationRecoveryObservationV1")
        == [
            "lookup_query_sha256",
            "observation_sha256",
            "original_decision_sha256",
            "result_id",
            "operation_committed_revision",
            "observed_journal_revision",
            "journal_generation_id",
            "journal_record_sequence",
        ],
        "private recovery evidence field shape drift",
    )
    state_match = re.search(
        r"(?ms)^enum ExternalOperationRecoveryStateV1 \{(?P<body>.*?)^\}", source
    )
    require(state_match is not None, "recovery state enum missing")
    variants = re.findall(r"(?m)^    ([A-Z][A-Za-z0-9]+),$", state_match.group("body"))
    require(variants == ["Committed", "NotFound", "Pending", "Conflict", "Indeterminate"], "state vocabulary drift")
    require("Revoked" not in production, "currentness revocation entered recovery vocabulary")
    require("#[must_use]\nstruct VerifiedExternalOperationRecoveryObservationV1" in source, "private evidence shape drift")
    require("pub(crate)" not in source and "pub fn" not in source, "S10 capability became crate-public")
    require("serde::" not in source and "Serialize" not in source, "S10 evidence became serializable")
    require(LOOKUP_PROFILE.decode() in production, "lookup profile drift")

    test_count = len(re.findall(r"(?m)^    fn s10_[a-z0-9_]+\(\)", source))
    require(test_count == 14, f"S10 Rust test count drift: {test_count}")
    require(
        "UNRESOLVED: synthetic journal loss cannot distinguish absence from rollback." in source,
        "journal-loss negative evidence missing",
    )
    require(
        "UNRESOLVED: returned observational evidence has no recall/consume API;" in source,
        "observation-recall negative evidence missing",
    )
    require(source.count("UNRESOLVED:") == 2, "S10 unresolved-evidence count drift")
    require(rust_u8_array(source, "RFC8032_SEED", 32) == RFC8032_SEED, "Rust seed vector drift")
    require(rust_u8_array(source, "RFC8032_PUBLIC_KEY", 32) == RFC8032_PUBLIC_KEY, "Rust public key drift")
    hardcoded_hex = re.findall(r'"([0-9a-f]{64}|[0-9a-f]{128})"', source)
    require(
        hardcoded_hex
        == [
            str(vectors["query_sha256"]),
            str(vectors["receipt_message_sha256"]),
            str(vectors["ed25519_signature"]),
        ],
        "Rust hardcoded known vectors drift",
    )
    return test_count


def receipt(test_count: int, vectors: dict[str, str | int]) -> str:
    rows = [
        ("schema", "agent_bridge.memory_temporal_external_operation_recovery_s10_receipt.v0"),
        ("status", STATUS),
        ("decision", DECISION),
        ("base_commit", BASE_COMMIT),
        ("s9_feature_commit", S9_FEATURE_COMMIT),
        ("s9_contract_sha256", S9_CONTRACT_SHA256),
        ("s9_successor_gate_sha256", S9_GATE_SHA256),
        ("s9_source_sha256", S9_SOURCE_SHA256),
        ("s10_contract_sha256", CONTRACT_SHA256),
        ("s10_successor_gate_sha256", GATE_SHA256),
        ("s10_source_sha256", SOURCE_SHA256),
        ("s10_store_cargo_sha256", STORE_CARGO_SHA256),
        ("s10_parent_module_sha256", PARENT_MODULE_SHA256),
        (
            "glue_validation_scope",
            "FROZEN_S10_TREE_FULL_DIGEST_SUCCESSOR_TREE_REQUIRES_SEPARATE_PROJECTION_CHECK",
        ),
        ("feature", FEATURE),
        ("depends_on_feature", S9_FEATURE),
        ("feature_default_enabled", "false"),
        ("ed25519_public_key", vectors["ed25519_public_key"]),
        ("known_query_sha256", vectors["query_sha256"]),
        ("known_observation_message_sha256", vectors["receipt_message_sha256"]),
        ("known_ed25519_signature", vectors["ed25519_signature"]),
        ("known_result_id", vectors["result_id"]),
        ("known_operation_committed_revision", vectors["operation_committed_revision"]),
        ("known_observed_journal_revision", vectors["observed_journal_revision"]),
        ("stored_s9_request_sha256", vectors["stored_s9_request_sha256"]),
        ("stored_s9_decision_sha256", vectors["stored_s9_decision_sha256"]),
        ("s10_nonignored_rust_tests", str(test_count)),
        ("lookup_profile", LOOKUP_PROFILE.decode()),
        ("lookup_interface", "SEALED_PRIVATE_LOOKUP_ONLY"),
        ("recovery_states", ",".join(RECOVERY_STATES)),
        ("committed_output", "PRIVATE_RECOVERY_OBSERVATION_NOT_ADMISSION"),
        ("submit_or_currentness_method_present", "false"),
        ("production_provider_present", "false"),
        ("production_constructor_present", "false"),
        ("external_durable_journal_present", "false"),
        ("owner_pinned_public_key_present", "false"),
        ("network_client_present", "false"),
        ("state_store_surface_present", "false"),
        ("adapter_reconstruction_sequence_model", "true"),
        ("external_crash_durability_proved", "false"),
        ("journal_loss_ambiguity_negative_evidence", "true"),
        ("provider_failure_ambiguity_resolved", "false"),
        ("successor_payload_admitted", "false"),
        ("cross_repository_transport_authorized", "false"),
        ("bridge_runtime_caller_present", "false"),
        ("biocortex_runtime_influence", "false"),
        ("remaining_gaps", ",".join(REMAINING_GAPS)),
        ("operational_gaps", ",".join(OPERATIONAL_GAPS)),
        ("side_effects_unlocked", "NONE"),
    ]
    return "".join(f"{key}\t{value}\n" for key, value in rows)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, required=True)
    args = parser.parse_args()
    repo = args.repo.resolve()
    try:
        check_predecessor(repo)
        vectors = known_vector(repo)
        check_contract(repo, vectors)
        check_gate(repo)
        test_count = check_source(repo, vectors)
    except (CheckFailure, KeyError, TypeError, ValueError, OSError) as exc:
        print(f"S10_CHECK_FAILED\t{exc}", file=sys.stderr)
        return 1
    sys.stdout.write(receipt(test_count, vectors))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
