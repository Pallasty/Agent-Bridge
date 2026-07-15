#!/usr/bin/env python3
"""Fail-closed checker for the frozen S11 atomic authority-operation tree.

The S11 construction is a private, synthetic two-linearization-point sequence
model.  This checker deliberately does not turn its local checksum, test key,
or in-process journal into evidence of external database durability, database /
KMS atomicity, signer non-equivocation, owner trust, or transport admission.
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

# The pinned S9 reference is imported dynamically; validation must not dirty an
# otherwise clean integration tree with an untracked ``__pycache__`` directory.
sys.dont_write_bytecode = True


STATUS = (
    "ATOMIC_AUTHORITY_OPERATION_OUTBOX_PREREGISTERED_SYNTHETIC_DB_ONLY_DB_KMS_"
    "NON_ATOMIC_EXACTLY_ONCE_UNPROVED_NO_PROVIDER_NO_CUSTODIAN_NO_OWNER_TRUST_"
    "ANCHOR_NOT_AUTHORIZED_NOT_TRANSPORT"
)
DECISION = "BLOCKED_FAIL_CLOSED"
FEATURE = "temporal-evidence-s11-atomic-authority-operation-synthetic"
S10_FEATURE = "temporal-evidence-s10-operation-recovery-synthetic"
S9_FEATURE = "temporal-evidence-s9-external-authority-provider-synthetic"
BASE_COMMIT = "0dad535e2cfd1a911c139d053409e0c02a7a8a0c"
S10_FEATURE_COMMIT = "4bc142e6182be4fa66a7b1542535314490dc714c"

CONTRACT_PATH = (
    "docs/design/fixtures/biocortex-ab-track-b-atomic-authority-operation-s11-v0.json"
)
GATE_PATH = "docs/design/fixtures/biocortex-ab-track-b-successor-admission-gate-s11-v0.json"
SOURCE_PATH = (
    "crates/store/src/temporal_replay_transport/"
    "external_authority_operation_state_machine.rs"
)
STORE_CARGO_PATH = "crates/store/Cargo.toml"
PARENT_MODULE_PATH = "crates/store/src/temporal_replay_transport.rs"

# Frozen only after every S11 artifact reached its final reviewed form.
CONTRACT_SHA256 = "eaca1280836bb31a3e1d0ce11173c6e34dbddf24a19e270af21d579428327db2"
GATE_SHA256 = "2d932c2b82fa41478ad42630bc9bae60467088027d046e7c14bed6a776d69cac"
SOURCE_SHA256 = "ffe01c13aadec867921ffd23f39f3ecc5d443bc44d30654f7fcd0be10e04793c"
STORE_CARGO_SHA256 = "bff674220aafad7d9db2f91c71f59348f7a3b316eb0ac5f78adf4d811f8f79ee"
PARENT_MODULE_SHA256 = "1880e0f1a95dd962cc611f19139da5b74e4c5a991fe89d482ad032677827ed8a"

S10_CONTRACT_PATH = (
    "docs/design/fixtures/biocortex-ab-track-b-external-operation-recovery-s10-v0.json"
)
S10_GATE_PATH = (
    "docs/design/fixtures/biocortex-ab-track-b-successor-admission-gate-s10-v0.json"
)
S10_SOURCE_PATH = "crates/store/src/temporal_replay_transport/external_operation_recovery.rs"
S10_CHECKER_PATH = "scripts/eval/check_memory_temporal_external_operation_recovery_s10.py"
S10_CONTRACT_SHA256 = "da3566f13df522958f05c871ad4679d89cda9b888ba8aa4eb4caaee4c457fb88"
S10_GATE_SHA256 = "9bedb7ef289f31a6b9409875d3b8e6fb3b4784aa972a329de229565caa5b1eb7"
S10_SOURCE_SHA256 = "850ddf4c47c76e9008671d44c47ba944b384744a4c50640e134e6c24008d90e4"
S10_CHECKER_SHA256 = "43ef19fce89e6cc6febcd7d774d5fac7d147ebcbcb21034e41dadf6978e0a096"

S9_CONTRACT_PATH = (
    "docs/design/fixtures/biocortex-ab-track-b-external-authority-provider-s9-v0.json"
)
S9_CHECKER_PATH = "scripts/eval/check_memory_temporal_external_authority_provider_s9.py"
S9_CONTRACT_SHA256 = "d537b80ce0d2bbb3c4d01a988a9685432672078eae07d0b976b1268a27526fc4"
S9_CHECKER_SHA256 = "ad7e373f539b780dd71af7f226464412442e3274ce98b0246329c0401a42995f"

POLICY = b"agent-bridge/track-b/atomic-authority-operation/v1"
PROFILE = b"DB_L1_ATOMIC_OUTBOX_EXACT_VERSION_RESIGN_DB_L2_VERIFIED_CAS_NO_KEY_FALLBACK"
ALGORITHM = b"Ed25519"
REQUEST_DOMAIN = b"agent-bridge/track-b/atomic-authority-operation/request/v1"
PREPARED_RECORD_DOMAIN = (
    b"agent-bridge/track-b/atomic-authority-operation/prepared-record/v1"
)
SIGN_JOB_DOMAIN = b"agent-bridge/track-b/atomic-authority-operation/sign-job/v1"
STABLE_RESULT_DOMAIN = b"agent-bridge/track-b/atomic-authority-operation/stable-result/v1"
DECISION_MESSAGE_DOMAIN = (
    b"agent-bridge/track-b/atomic-authority-operation/decision-message/v1"
)
LOCAL_L2_COMMITMENT_DOMAIN = (
    b"agent-bridge/track-b/atomic-authority-operation/synthetic-l2-record/v1"
)
RFC8032_SEED = bytes.fromhex(
    "9d61b19deffd5a60ba844af492ec2cc44449c5697b326919703bac031cae7f60"
)
RFC8032_PUBLIC_KEY = bytes.fromhex(
    "d75a980182b10ab7d54bfed3c964073a0ee172f3daa62325af021a68f707511a"
)

PERSISTENT_STATES = ("DECISION_COMMITTED_UNSIGNED", "SIGNED_COMMITTED")
LOOKUP_OUTCOMES = ("NOT_FOUND", "PENDING", "COMMITTED")
FAULT_CUT_POINTS = (
    "BEFORE_L1",
    "DURING_L1_BEFORE_COMMIT",
    "L1_COMMITTED_ACK_LOST",
    "AFTER_L1_BEFORE_SIGN_REQUEST",
    "SIGN_REQUEST_SENT_BEFORE_EXECUTION",
    "SIGN_EXECUTED_RESPONSE_LOST_OR_TIMEOUT",
    "SIGN_RESPONSE_BEFORE_INTEGRITY_AND_SIGNATURE_VERIFY",
    "SIGNATURE_VERIFIED_BEFORE_L2",
    "KEY_STATE_CHANGED_BEFORE_L2",
    "DURING_L2_BEFORE_COMMIT",
    "L2_COMMITTED_ACK_LOST",
    "L2_COMMITTED_CALLER_RESPONSE_LOST_OR_DUPLICATED",
    "DATABASE_OR_SIGNER_SNAPSHOT_ROLLBACK_OR_BRANCH_MERGE",
)
INJECTED_FAILURE_CUTS = (
    "L1_BEFORE_COMMIT",
    "L1_ACK_LOST_AFTER_COMMIT",
    "SIGNER_TIMEOUT_AFTER_EXECUTION",
    "VERIFIED_SIGNATURE_LOST_BEFORE_L2",
    "L2_BEFORE_COMMIT",
    "L2_ACK_LOST_AFTER_COMMIT",
)
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
    "ATOMIC_AUTHORITY_OPERATION_EXTERNAL_DATABASE_UNIMPLEMENTED",
    "DATABASE_KMS_CROSS_SERVICE_ATOMICITY_UNATTESTED",
    "KMS_EXACTLY_ONCE_SIGNING_UNPROVED",
    "EXACT_VERSION_SIGNING_CUSTODY_UNATTESTED",
    "OPERATION_OUTBOX_EXTERNAL_DURABILITY_UNATTESTED",
    "SIGNATURE_PERSISTENCE_EXTERNAL_DURABILITY_UNATTESTED",
    "SIGNER_NON_EQUIVOCATION_UNATTESTED",
    "CURRENTNESS_AT_DOWNSTREAM_USE_UNATTESTED",
)

CONTRACT_TOP_LEVEL_KEYS = (
    "boundary",
    "decision",
    "dependency",
    "evidence_boundary",
    "enumerated_threat_scenarios",
    "failure_semantics",
    "implementation",
    "injected_failure_cuts",
    "known_vector",
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
    "atomic_operation_preregistration",
    "authorization_semantics",
    "boundary",
    "decision",
    "operational_gap_codes",
    "predecessor",
    "remaining_gap_codes",
    "required_successor_identity",
    "schema",
    "status",
)

# Calibrated against the final architecture source, not an intermediate file.
S11_TEST_COUNT = 29


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


def require_frozen_digest(value: str, label: str) -> None:
    require(
        re.fullmatch(r"[0-9a-f]{64}", value) is not None,
        f"{label} checker digest is not frozen: {value}",
    )


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


def require_exact_boolean_map(
    value: Any, expected_keys: tuple[str, ...], expected_value: bool, message: str
) -> None:
    require(isinstance(value, dict), message)
    require(set(value) == set(expected_keys), message)
    require(all(value[key] is expected_value for key in expected_keys), message)


def feature_is_reachable(features: dict[str, Any], roots: list[str], target: str) -> bool:
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
            if edge in features or edge == target:
                pending.append(edge)
    return False


def import_s9_reference(repo: Path) -> ModuleType:
    require(sha256(repo, S9_CHECKER_PATH) == S9_CHECKER_SHA256, "S9 checker digest drift")
    path = repo / S9_CHECKER_PATH
    spec = importlib.util.spec_from_file_location("s11_pinned_s9_ed25519_reference", path)
    require(spec is not None and spec.loader is not None, "cannot load pinned S9 reference")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    for name in ("framed_message", "framed_digest", "ed25519_public_key", "ed25519_sign", "ed25519_verify"):
        require(callable(getattr(module, name, None)), f"pinned S9 reference missing: {name}")
    return module


def known_vector(repo: Path) -> dict[str, str | int]:
    reference = import_s9_reference(repo)
    repeated = lambda value: bytes([value]) * 32
    u64 = lambda value: value.to_bytes(8, "big")
    s9_contract = bytes.fromhex(S9_CONTRACT_SHA256)
    s10_contract = bytes.fromhex(S10_CONTRACT_SHA256)

    request_sha256 = reference.framed_digest(
        REQUEST_DOMAIN,
        [
            POLICY,
            PROFILE,
            ALGORITHM,
            s9_contract,
            s10_contract,
            b"owner-selected-provider-v1",
            b"track-b-authority",
            b"tenant-a",
            b"agent-bridge-store",
            b"authority-cluster-a",
            repeated(0x61),
            repeated(0x72),
            repeated(0x21),
            repeated(0x22),
            repeated(0x23),
            repeated(0x25),
            repeated(0x26),
            repeated(0x24),
            repeated(0x71),
            b"authority-signer",
            u64(3),
        ],
    )
    prepared_record_sha256 = reference.framed_digest(
        PREPARED_RECORD_DOMAIN,
        [POLICY, b"DECISION_COMMITTED_UNSIGNED", request_sha256, u64(7), u64(41), u64(9)],
    )
    sign_job = reference.framed_digest(
        SIGN_JOB_DOMAIN,
        [POLICY, prepared_record_sha256, b"authority-signer", u64(3)],
    )
    stable_result = reference.framed_digest(
        STABLE_RESULT_DOMAIN, [POLICY, prepared_record_sha256, sign_job]
    )
    decision_message = reference.framed_message(
        DECISION_MESSAGE_DOMAIN,
        [
            POLICY,
            PROFILE,
            ALGORITHM,
            s9_contract,
            s10_contract,
            request_sha256,
            repeated(0x21),
            repeated(0x22),
            repeated(0x23),
            repeated(0x25),
            repeated(0x26),
            repeated(0x24),
            b"authority-cluster-a",
            repeated(0x61),
            repeated(0x72),
            u64(7),
            u64(41),
            u64(9),
            prepared_record_sha256,
            sign_job,
            stable_result,
            b"authority-signer",
            u64(3),
            repeated(0x71),
        ],
    )
    decision_message_sha256 = hashlib.sha256(decision_message).digest()
    public_key = reference.ed25519_public_key(RFC8032_SEED)
    signature = reference.ed25519_sign(RFC8032_SEED, decision_message)
    require(public_key == RFC8032_PUBLIC_KEY, "independent Ed25519 public-key drift")
    require(
        reference.ed25519_verify(public_key, decision_message, signature),
        "independent Ed25519 signature did not verify",
    )
    local_l2_commitment = reference.framed_digest(
        LOCAL_L2_COMMITMENT_DOMAIN,
        [POLICY, b"SIGNED_COMMITTED", stable_result, decision_message_sha256, signature, u64(42)],
    )
    return {
        "decision_message_sha256": decision_message_sha256.hex(),
        "ed25519_public_key": public_key.hex(),
        "ed25519_signature": signature.hex(),
        "local_l2_commitment_sha256": local_l2_commitment.hex(),
        "l1_operation_committed_revision": 41,
        "l2_synthetic_revision": 42,
        "prepared_record_sha256": prepared_record_sha256.hex(),
        "record_sequence": 9,
        "request_sha256": request_sha256.hex(),
        "sign_job_id": sign_job.hex(),
        "stable_result_id": stable_result.hex(),
    }


def check_predecessor(repo: Path) -> None:
    require(sha256(repo, S9_CONTRACT_PATH) == S9_CONTRACT_SHA256, "S9 contract digest drift")
    require(sha256(repo, S10_CONTRACT_PATH) == S10_CONTRACT_SHA256, "S10 contract digest drift")
    require(sha256(repo, S10_GATE_PATH) == S10_GATE_SHA256, "S10 gate digest drift")
    require(sha256(repo, S10_SOURCE_PATH) == S10_SOURCE_SHA256, "S10 source digest drift")
    require(sha256(repo, S10_CHECKER_PATH) == S10_CHECKER_SHA256, "S10 checker digest drift")


def contract_known_vector(vectors: dict[str, str | int]) -> dict[str, str | int]:
    return {
        "decision_message_sha256": str(vectors["decision_message_sha256"]),
        "ed25519_public_key": str(vectors["ed25519_public_key"]),
        "ed25519_signature": str(vectors["ed25519_signature"]),
        "operation_committed_revision": vectors["l1_operation_committed_revision"],
        "prepared_record_sha256": str(vectors["prepared_record_sha256"]),
        "record_sequence": vectors["record_sequence"],
        "request_sha256": str(vectors["request_sha256"]),
        "sign_job_id": str(vectors["sign_job_id"]),
        "stable_result_id": str(vectors["stable_result_id"]),
        "synthetic_l2_record_sha256": str(vectors["local_l2_commitment_sha256"]),
        "synthetic_l2_revision": vectors["l2_synthetic_revision"],
    }


def check_contract(repo: Path, vectors: dict[str, str | int], test_count: int) -> None:
    require_frozen_digest(CONTRACT_SHA256, "S11 contract")
    require(sha256(repo, CONTRACT_PATH) == CONTRACT_SHA256, "S11 contract digest drift")
    contract = load_json(repo, CONTRACT_PATH)
    require(set(contract) == set(CONTRACT_TOP_LEVEL_KEYS), "S11 top-level contract keys drift")
    require(
        contract["schema"]
        == "agent_bridge.memory_temporal_atomic_authority_operation_contract_s11.v0",
        "S11 schema drift",
    )
    require(contract["status"] == STATUS and contract["decision"] == DECISION, "S11 outcome drift")
    require_exact_value(
        contract["dependency"],
        {
            "baseline_integration_commit": BASE_COMMIT,
            "default_enabled": False,
            "depends_on_feature": S10_FEATURE,
            "feature": FEATURE,
            "s10_feature_commit": S10_FEATURE_COMMIT,
        },
        "S11 dependency drift",
    )
    require_exact_boolean_map(
        contract["boundary"],
        (
            "biocortex_runtime_influence",
            "bridge_feature_forwarding_present",
            "bridge_runtime_caller_present",
            "cross_repository_transport_authorized",
            "database_driver_present",
            "external_database_present",
            "external_key_custodian_present",
            "external_owner_trust_anchor_present",
            "kms_client_present",
            "network_client_present",
            "production_constructor_present",
            "production_provider_adapter_present",
            "state_store_surface_present",
            "successor_payload_admitted",
        ),
        False,
        "S11 boundary drift",
    )
    require_exact_value(
        contract["evidence_boundary"],
        {
            "currentness_at_downstream_use_proved": False,
            "database_kms_cross_service_atomicity_proved": False,
            "ed25519_authenticates_frozen_l1_decision_only": True,
            "exactly_once_signing_proved": False,
            "external_database_durability_proved": False,
            "owner_trust_proved": False,
            "provider_rollback_protection_proved": False,
            "provider_split_brain_fencing_proved": False,
            "signer_non_equivocation_proved": False,
            "synthetic_l2_checksum_authenticates_database_persistence": False,
            "synthetic_l2_revision_authenticated_by_ed25519": False,
            "synthetic_claim": "SYNTHETIC_TWO_LEVEL_OUTBOX_SEQUENCE_AND_FAULT_MODEL_EVIDENCE",
        },
        "S11 evidence boundary drift",
    )
    require_exact_boolean_map(
        contract["failure_semantics"],
        (
            "ambiguous_database_commit_blindly_resubmits",
            "decision_committed_unsigned_returns_observation",
            "conflict_returns_observation",
            "identity_released_after_signer_timeout",
            "indeterminate_returns_observation",
            "invalid_signature_can_finalize",
            "kms_timeout_returns_observation",
            "local_fallback_allowed",
            "signed_committed_record_can_regress",
            "signer_key_version_substitution_allowed",
            "split_branch_returns_observation",
        ),
        False,
        "S11 failure semantics drift",
    )
    require_exact_value(
        contract["enumerated_threat_scenarios"],
        list(FAULT_CUT_POINTS),
        "enumerated threat scenarios drift",
    )
    require_exact_value(
        contract["injected_failure_cuts"],
        list(INJECTED_FAILURE_CUTS),
        "injected failure cuts drift",
    )
    require_exact_value(
        contract["implementation"],
        {
            "database_or_kms_adapter": False,
            "module_path": SOURCE_PATH,
            "module_visibility": "private_child_of_private_s6_module",
            "network_or_transport": False,
            "persistent_state_count": 2,
            "production_implementation": False,
            "signer_response_executable_shape": (
                "SYNTHETIC_KEY_ID_KEY_VERSION_MESSAGE_SHA256_AND_ED25519_SIGNATURE_ONLY"
            ),
            "state_store_integration": False,
            "synthetic_database_scope": (
                "SHARED_PROCESS_MEMORY_TWO_LEVEL_OUTBOX_SEQUENCE_MODEL_NOT_DURABILITY_EVIDENCE"
            ),
            "synthetic_journal_owned_l1_commitments": [
                "JOURNAL_GENERATION",
                "PROVIDER_CLUSTER_AND_INCARNATION",
                "AUTHORITY_SNAPSHOT_SHA256",
                "CANONICAL_DECISION_SHA256",
                "TRUST_POLICY_SHA256",
                "SIGNER_KEY_ID_AND_EXACT_VERSION",
            ],
            "synthetic_l2_checksum_publicly_recomputable": True,
            "typed_lookup_outcomes": [
                "NOT_FOUND",
                "PENDING_WITH_L1_WITNESS",
                "COMMITTED_WITH_SYNTHETIC_RECORD",
            ],
        },
        "S11 implementation declaration drift",
    )
    require_exact_value(contract["known_vector"], contract_known_vector(vectors), "known vector drift")
    require_exact_value(contract["remaining_gap_codes"], list(REMAINING_GAPS), "remaining gaps drift")
    require_exact_value(
        contract["operational_gap_codes"], list(OPERATIONAL_GAPS), "operational gaps drift"
    )
    require_exact_value(
        contract["predecessor"],
        {
            "s10_contract_sha256": S10_CONTRACT_SHA256,
            "s10_feature_commit": S10_FEATURE_COMMIT,
            "s10_integration_commit": BASE_COMMIT,
            "s10_source_sha256": S10_SOURCE_SHA256,
            "s10_successor_gate_sha256": S10_GATE_SHA256,
        },
        "S11 predecessor binding drift",
    )
    require_exact_value(
        contract["protocol"],
        {
            "begin_exact_once_is_create_only": True,
            "committed_output": (
                "PRIVATE_NON_ADMISSION_L1_SIGNATURE_OBSERVATION_WITH_"
                "UNAUTHENTICATED_SYNTHETIC_L2_METADATA"
            ),
            "conflict_and_indeterminate_are_fail_closed_errors_not_persistent_states": True,
            "ed25519_authenticated_fields": "EXACT_FROZEN_L1_DECISION_MESSAGE_ONLY",
            "exact_duplicate_committed_action": (
                "RETURN_STORED_SYNTHETIC_RECORD_WITHOUT_MUTATION"
            ),
            "exact_duplicate_unsigned_action": (
                "LOOKUP_PENDING_AND_RESUME_WITH_EXACT_TYPED_L1_WITNESS_ONLY"
            ),
            "exact_resume_recomputes_decision": False,
            "exact_resume_reuses_sign_job_id": True,
            "kms_call_inside_database_transaction": False,
            "l1": (
                "SYNTHETIC_JOURNAL_LOCK_VALIDATE_OWNED_COMMITMENTS_RESERVE_OPERATION_"
                "AND_CHALLENGE_CONSUME_REPLAY_AND_FREEZE_L1_MESSAGE"
            ),
            "l1_derives_or_reverifies_raw_s9_decision_bytes": False,
            "l1_witness_fields": (
                "OPERATION_REQUEST_GENERATION_L1_RECORD_SIGN_JOB_STABLE_RESULT_REVISION_SEQUENCE"
            ),
            "l2": (
                "VERIFY_SYNTHETIC_SIGNER_RESPONSE_AND_CAS_STORE_SIGNATURE_WITH_"
                "UNAUTHENTICATED_PUBLIC_L2_CHECKSUM"
            ),
            "persistent_states": list(PERSISTENT_STATES),
            "signature_observed_is_persistent_state": False,
            "state_transition": "ABSENT_TO_DECISION_COMMITTED_UNSIGNED_TO_SIGNED_COMMITTED",
            "synthetic_l2_checksum_is_external_database_receipt": False,
            "typed_lookup": "NOT_FOUND_OR_PENDING_L1_WITNESS_OR_COMMITTED_SYNTHETIC_RECORD",
            "timeout_releases_consumed_identity": False,
        },
        "S11 protocol drift",
    )
    require_exact_value(
        contract["test_matrix"],
        {
            "all_non_committed_or_ambiguous_states_fail_closed": True,
            "committed_synthetic_record_stable_and_read_only": True,
            "concurrent_l1_create_only_winner": True,
            "concurrent_exact_workers_one_shared_journal_sequence": True,
            "currentness_and_replay_consume_interleavings": True,
            "enumerated_threat_scenario_count": 13,
            "deterministic_known_answer": True,
            "exact_duplicate_three_phase_behavior": True,
            "exact_resume_same_message_and_key_version": True,
            "injected_failure_cut_count": 6,
            "impossible_phase_and_index_combinations_fail_closed": True,
            "journal_owned_l1_commitment_substitution_rejection": True,
            "l1_all_or_none_operation_challenge_replay_indexes": True,
            "l2_all_or_none_signature_state_and_public_checksum": True,
            "local_journal_disappearance_with_retained_l1_witness_is_indeterminate": True,
            "selected_operation_request_challenge_replay_conflicts": True,
            "persistent_state_count": 2,
            "signer_non_equivocation_proved": False,
            "signer_rollback_simulated": False,
            "split_branch_simulated": False,
            "synthetic_l2_checksum_malleability_negative_evidence": True,
            "test_count": test_count,
            "synthetic_signer_key_message_and_signature_binding": True,
            "response_delivery_loss_recovers_without_resign": True,
            "wrong_public_key_fast_paths_reject": True,
            "zero_network_bridge_state_store_or_production_constructor": True,
        },
        "S11 test matrix drift",
    )


def check_gate(repo: Path) -> None:
    require_frozen_digest(GATE_SHA256, "S11 gate")
    gate = load_json(repo, GATE_PATH)
    require(sha256(repo, GATE_PATH) == GATE_SHA256, "S11 gate digest drift")
    require(set(gate) == set(GATE_TOP_LEVEL_KEYS), "S11 top-level gate keys drift")
    require(
        gate["schema"] == "agent_bridge.memory_temporal_successor_admission_gate_s11.v0",
        "S11 successor schema drift",
    )
    require(gate["status"] == "NOT_ADMITTED" and gate["decision"] == DECISION, "gate opened")
    require_exact_value(
        gate["admission"],
        {
            "admitted": False,
            "admission_artifact_must_be_external_to_packet": True,
            "atomic_authority_operation_receipt": None,
            "atomic_replay_consume_receipt": None,
            "authority_decision_receipt": None,
            "authority_policy_custodian_receipt": None,
            "build_attestation": None,
            "capture_authorization_receipt": None,
            "capture_provenance_receipt": None,
            "currentness_at_downstream_use_receipt": None,
            "database_kms_cross_service_atomicity_receipt": None,
            "deletion_mechanism_receipt": None,
            "destination_receiver_identity": None,
            "durable_challenge_uniqueness_receipt": None,
            "exact_version_kms_signing_receipt": None,
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
            "signature_persistence_durability_receipt": None,
            "signer_non_equivocation_receipt": None,
        },
        "S11 admission receipt set drift",
    )
    require_exact_value(
        gate["atomic_operation_preregistration"],
        {
            "contract_sha256": CONTRACT_SHA256,
            "contract_status": STATUS,
            "database_kms_cross_service_atomicity_proved": False,
            "ed25519_authenticates_frozen_l1_decision_only": True,
            "ed25519_authenticates_l2_persistence": False,
            "exactly_once_signing_proved": False,
            "external_database_present": False,
            "l1_l2_persistent_states": list(PERSISTENT_STATES),
            "private_receipt_is_admission": False,
            "production_provider_or_custodian_present": False,
            "synthetic_l2_checksum_is_authenticated_database_receipt": False,
            "synthetic_model_is_production_evidence": False,
            "typed_lookup_and_l1_witness_recovery_present": True,
        },
        "S11 preregistration drift",
    )
    require_exact_boolean_map(
        gate["authorization_semantics"],
        (
            "committed_operation_receipt_is_not_admission_or_currentness_at_use",
            "exact_re_sign_is_not_exactly_once_signing_proof",
            "l1_journal_commitments_are_not_independent_s9_decision_verification",
            "owner_pin_must_be_external_to_signed_response",
            "preregistration_does_not_authorize_transport",
            "repository_owner_research_permission_is_not_provider_or_custodian_attestation",
            "synthetic_database_is_not_external_durability_or_linearizability_evidence",
            "synthetic_l2_revision_and_checksum_are_unauthenticated_metadata",
            "synthetic_test_key_is_not_owner_pinned_production_trust",
        ),
        True,
        "S11 authorization caveat drift",
    )
    require_exact_value(
        gate["boundary"],
        {
            "biocortex_runtime_influence": False,
            "bridge_runtime_caller_present": False,
            "cross_repository_transport_authorized": False,
            "external_currentness_provider_present": False,
            "external_database_present": False,
            "external_key_custodian_present": False,
            "external_operation_recovery_provider_present": False,
            "external_owner_trust_anchor_present": False,
            "live_binding_satisfied": False,
            "production_profile_active": False,
            "s11_receipt_admits": False,
            "side_effects_unlocked": "NONE",
        },
        "S11 successor boundary opened",
    )
    require_exact_value(gate["remaining_gap_codes"], list(REMAINING_GAPS), "gate gaps drift")
    require_exact_value(
        gate["operational_gap_codes"], list(OPERATIONAL_GAPS), "gate operational gaps drift"
    )
    require_exact_value(
        gate["predecessor"],
        {
            "s10_contract_sha256": S10_CONTRACT_SHA256,
            "s10_feature_commit": S10_FEATURE_COMMIT,
            "s10_integration_commit": BASE_COMMIT,
            "s10_source_sha256": S10_SOURCE_SHA256,
            "s10_successor_gate_sha256": S10_GATE_SHA256,
        },
        "gate predecessor binding drift",
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


def enum_body(source: str, name: str) -> str:
    match = re.search(rf"(?ms)^enum {re.escape(name)} \{{(?P<body>.*?)^\}}", source)
    require(match is not None, f"missing Rust enum: {name}")
    return match.group("body")


def rust_u8_array(source: str, name: str, length: int) -> bytes:
    match = re.search(
        rf"(?ms)^    const {re.escape(name)}: \[u8; {length}\] = \[(?P<body>.*?)^    \];",
        source,
    )
    require(match is not None, f"missing Rust byte vector: {name}")
    values = bytes(int(value, 16) for value in re.findall(r"0x([0-9a-fA-F]{2})", match.group("body")))
    require(len(values) == length, f"Rust byte-vector length drift: {name}")
    return values


def rust_root_u8_array(source: str, name: str, length: int) -> bytes:
    match = re.search(
        rf"(?ms)^const {re.escape(name)}: \[u8; {length}\] = \[(?P<body>.*?)^\];",
        source,
    )
    require(match is not None, f"missing Rust root byte vector: {name}")
    values = bytes(int(value, 16) for value in re.findall(r"0x([0-9a-fA-F]{2})", match.group("body")))
    require(len(values) == length, f"Rust root byte-vector length drift: {name}")
    return values


def bridge_has_surface(repo: Path, needles: tuple[str, ...]) -> bool:
    root = repo / "crates/bridge"
    require(root.is_dir() and not root.is_symlink(), "missing/non-regular Bridge crate")
    for directory, directory_names, file_names in os.walk(root, followlinks=False):
        base = Path(directory)
        for name in directory_names:
            require(not (base / name).is_symlink(), f"symlink in Bridge source tree: {base / name}")
        for name in sorted(file_names):
            path = base / name
            if path.suffix not in {".rs", ".toml"}:
                continue
            require(path.is_file() and not path.is_symlink(), f"non-regular Bridge source: {path}")
            text = path.read_text(encoding="utf-8")
            if any(needle in text for needle in needles):
                return True
    return False


def check_source(repo: Path, vectors: dict[str, str | int]) -> int:
    for digest, label in (
        (SOURCE_SHA256, "S11 source"),
        (STORE_CARGO_SHA256, "S11 Store Cargo"),
        (PARENT_MODULE_SHA256, "S11 parent module"),
    ):
        require_frozen_digest(digest, label)
    require(sha256(repo, SOURCE_PATH) == SOURCE_SHA256, "S11 Rust source digest drift")
    require(sha256(repo, STORE_CARGO_PATH) == STORE_CARGO_SHA256, "Store Cargo digest drift")
    require(sha256(repo, PARENT_MODULE_PATH) == PARENT_MODULE_SHA256, "parent module digest drift")

    cargo = tomllib.loads(read_text(repo, STORE_CARGO_PATH))
    features = cargo.get("features", {})
    require(isinstance(features, dict), "Cargo features table missing")
    require(features.get(S10_FEATURE) == [S9_FEATURE], "retained S10 feature projection drift")
    require(features.get(FEATURE) == [S10_FEATURE], "S11 feature dependency drift")
    default_features = features.get("default", [])
    require(isinstance(default_features, list), "Cargo default feature list drift")
    require(not feature_is_reachable(features, default_features, FEATURE), "S11 became default")

    parent = read_text(repo, PARENT_MODULE_PATH)
    library = read_text(repo, "crates/store/src/lib.rs")
    source = read_text(repo, SOURCE_PATH)
    module_name = "external_authority_operation_state_machine"
    expected_gate = f'#[cfg(feature = "{FEATURE}")]\nmod {module_name};'
    require(parent.count(expected_gate) == 1, "private S11 module gate missing or duplicated")
    require(f"pub mod {module_name}" not in parent, "S11 module became public")
    require(f"pub use {module_name}" not in parent + library, "S11 re-export forbidden")
    require(FEATURE not in library and module_name not in library, "S11 leaked to Store library")
    require(
        not bridge_has_surface(repo, (FEATURE, module_name, "ExternalAtomicAuthorityOperationProviderV1")),
        "S11 leaked to Bridge surface",
    )

    split = source.split("#[cfg(test)]\nmod tests", 1)
    require(len(split) == 2, "S11 synthetic implementation is not cfg(test)-isolated")
    production, tests = split
    code = strip_rust_comments(production)
    for forbidden in (
        "StateStore",
        "Bridge",
        "tokio::",
        "std::net",
        "reqwest::",
        "hyper::",
        "tonic::",
        "TcpStream",
        "UdpSocket",
        "UnixStream",
        "SocketAddr",
        "rusqlite",
        "tokio_rusqlite",
        "sqlx::",
        "postgres::",
        "mysql::",
        "redis::",
        "aws_sdk_kms",
        "std::fs",
        "OpenOptions",
        "SystemTime",
        "Instant::now",
        "std::time",
        "serde::",
        "Serialize",
    ):
        require(forbidden not in code, f"forbidden S11 production surface: {forbidden}")
    require(
        "impl AtomicAuthorityOperationTrustPermitV1" not in production,
        "production trust-permit constructor added",
    )
    require(
        "impl atomic_operation_provider_seal::Sealed" not in production,
        "production provider adapter added",
    )
    require(
        "impl ExternalAtomicAuthorityOperationProviderV1 for" not in production,
        "production operation provider added",
    )
    public_code = code.replace("pub(super) trait Sealed {}", "")
    require(source.count("pub(super)") == 1, "unexpected pub(super) S11 surface")
    require(
        not re.search(r"\bpub(?:\(crate\))?\s+(?:fn|struct|enum|trait|use|mod)\b", public_code),
        "S11 capability became public or crate-public",
    )
    require("serde::" not in source and "Serialize" not in source, "S11 evidence became serializable")
    require("fn permit(" in tests, "test-only trust permit missing")
    require("struct SyntheticJournalV1" in tests, "synthetic journal missing")
    require("struct SyntheticSignerV1" in tests, "synthetic signer missing")
    require("Arc<Mutex<SyntheticJournalV1>>" in tests, "shared-process sequence model missing")
    require(source.count("pub(super) trait Sealed {}") == 1, "sealed-interface count drift")

    require(
        struct_fields(source, "AtomicAuthorityOperationRequestV1")
        == [
            "provider_profile_id",
            "authority_namespace_id",
            "tenant_id",
            "audience",
            "provider_cluster_id",
            "provider_incarnation",
            "journal_generation_id",
            "operation_id",
            "original_challenge",
            "original_request_sha256",
            "concrete_replay_identity_sha256",
            "authority_snapshot_sha256",
            "canonical_decision_sha256",
            "trust_policy_sha256",
            "signer_key_id",
            "signer_key_version",
        ],
        "S11 request field shape drift",
    )
    require(
        struct_fields(source, "AtomicAuthorityOperationL1WitnessV1")
        == [
            "operation_id",
            "request_sha256",
            "journal_generation_id",
            "prepared_record_sha256",
            "sign_job_id",
            "stable_result_id",
            "operation_committed_revision",
            "record_sequence",
        ],
        "typed L1 witness field shape drift",
    )
    require(
        struct_fields(source, "AtomicAuthorityOperationTrustPermitV1")
        == [
            "provider_profile_id",
            "authority_namespace_id",
            "tenant_id",
            "audience",
            "provider_cluster_id",
            "provider_incarnation",
            "journal_generation_id",
            "signer_key_id",
            "signer_key_version",
            "trust_policy_sha256",
            "minimum_leader_term",
            "minimum_operation_committed_revision",
            "ed25519_public_key",
        ],
        "S11 trust-permit field shape drift",
    )
    require(
        struct_fields(source, "SignedCommittedAuthorityOperationV1")
        == [
            "request_sha256",
            "state",
            "provider_cluster_id",
            "provider_incarnation",
            "journal_generation_id",
            "leader_term",
            "operation_committed_revision",
            "record_sequence",
            "prepared_record_sha256",
            "sign_job_id",
            "stable_result_id",
            "decision_message_sha256",
            "signer_key_id",
            "signer_key_version",
            "synthetic_l2_revision",
            "ed25519_signature",
            "synthetic_l2_record_sha256",
        ],
        "signed synthetic-record field shape drift",
    )
    require(
        struct_fields(source, "VerifiedAtomicAuthorityOperationObservationV1")
        == [
            "stable_result_id",
            "decision_message_sha256",
            "operation_committed_revision",
            "record_sequence",
        ],
        "private verified observation field shape drift",
    )
    state_variants = re.findall(
        r"(?m)^    ([A-Z][A-Za-z0-9]+),$",
        enum_body(source, "AtomicAuthorityOperationPersistentStateV1"),
    )
    require(state_variants == ["DecisionCommittedUnsigned", "SignedCommitted"], "state drift")
    outcome = re.sub(r"\s+", "", enum_body(source, "AtomicAuthorityOperationLookupOutcomeV1"))
    require(
        outcome
        == (
            "NotFound,Pending(AtomicAuthorityOperationL1WitnessV1),"
            "Committed(SignedCommittedAuthorityOperationV1),"
        ),
        "lookup must expose typed NotFound/Pending/Committed outcomes",
    )
    require(
        "fn lookup_exact(" in production
        and "OperationResult<AtomicAuthorityOperationLookupOutcomeV1>" in production,
        "sealed provider lacks explicit typed lookup outcome",
    )
    trait_match = re.search(
        r"(?ms)^trait ExternalAtomicAuthorityOperationProviderV1.*?\{(?P<body>.*?)^\}",
        source,
    )
    require(trait_match is not None, "sealed S11 provider trait missing")
    require(
        re.findall(r"\bfn\s+([a-zA-Z0-9_]+)", trait_match.group("body"))
        == ["begin_exact_once", "lookup_exact", "resume_exact_from_l1"],
        "sealed S11 provider method set drift",
    )
    require(
        "witness: &AtomicAuthorityOperationL1WitnessV1" in production,
        "resume API lacks typed retained L1 witness",
    )
    require(
        "#[must_use]\nstruct VerifiedAtomicAuthorityOperationObservationV1" in source,
        "private verified observation shape drift",
    )
    require(PROFILE.decode() in production, "S11 profile drift")
    require(
        "fn synthetic_l2_record_digest(" in production,
        "local L2 sequence commitment function missing",
    )
    require(
        "not part of the Ed25519 message" in source
        and "authenticated database-persistence receipt" in source,
        "local L2 commitment caveat missing",
    )
    require(
        "UNRESOLVED:" in tests,
        "rollback/signer negative evidence must remain explicit",
    )

    test_count = len(re.findall(r"(?m)^    fn s11_[a-z0-9_]+\(\)", source))
    require(test_count == S11_TEST_COUNT, f"S11 Rust test count drift: {test_count}")
    require(rust_u8_array(source, "RFC8032_SEED", 32) == RFC8032_SEED, "Rust seed drift")
    require(
        rust_u8_array(source, "RFC8032_PUBLIC_KEY", 32) == RFC8032_PUBLIC_KEY,
        "Rust public key drift",
    )
    require(
        rust_root_u8_array(source, "S9_CONTRACT_SHA256", 32)
        == bytes.fromhex(S9_CONTRACT_SHA256),
        "Rust S9 contract binding drift",
    )
    require(
        rust_root_u8_array(source, "S10_CONTRACT_SHA256", 32)
        == bytes.fromhex(S10_CONTRACT_SHA256),
        "Rust S10 contract binding drift",
    )
    hardcoded_hex = re.findall(r'"([0-9a-f]{64}|[0-9a-f]{128})"', source)
    require(
        hardcoded_hex
        == [
            str(vectors["request_sha256"]),
            str(vectors["prepared_record_sha256"]),
            str(vectors["sign_job_id"]),
            str(vectors["stable_result_id"]),
            str(vectors["decision_message_sha256"]),
            str(vectors["ed25519_signature"]),
            str(vectors["local_l2_commitment_sha256"]),
        ],
        "Rust hardcoded independent known vectors drift",
    )
    for value in (
        "request_sha256",
        "prepared_record_sha256",
        "sign_job_id",
        "stable_result_id",
        "decision_message_sha256",
        "ed25519_signature",
        "local_l2_commitment_sha256",
    ):
        require(re.fullmatch(r"[0-9a-f]+", str(vectors[value])) is not None, f"vector drift: {value}")
    return test_count


def receipt(test_count: int, vectors: dict[str, str | int]) -> str:
    rows = [
        ("schema", "agent_bridge.memory_temporal_atomic_authority_operation_s11_receipt.v0"),
        ("status", STATUS),
        ("decision", DECISION),
        ("base_commit", BASE_COMMIT),
        ("s10_feature_commit", S10_FEATURE_COMMIT),
        ("s9_contract_sha256", S9_CONTRACT_SHA256),
        ("s10_contract_sha256", S10_CONTRACT_SHA256),
        ("s10_successor_gate_sha256", S10_GATE_SHA256),
        ("s10_source_sha256", S10_SOURCE_SHA256),
        ("s10_checker_sha256", S10_CHECKER_SHA256),
        ("s11_contract_sha256", CONTRACT_SHA256),
        ("s11_successor_gate_sha256", GATE_SHA256),
        ("s11_source_sha256", SOURCE_SHA256),
        ("s11_store_cargo_sha256", STORE_CARGO_SHA256),
        ("s11_parent_module_sha256", PARENT_MODULE_SHA256),
        (
            "glue_validation_scope",
            "FROZEN_S11_TREE_FULL_DIGEST_PRIVATE_SYNTHETIC_SEQUENCE_MODEL_ONLY",
        ),
        ("feature", FEATURE),
        ("depends_on_feature", S10_FEATURE),
        ("feature_default_enabled", "false"),
        ("ed25519_public_key", vectors["ed25519_public_key"]),
        ("known_request_sha256", vectors["request_sha256"]),
        ("known_prepared_record_sha256", vectors["prepared_record_sha256"]),
        ("known_sign_job_id", vectors["sign_job_id"]),
        ("known_stable_result_id", vectors["stable_result_id"]),
        ("known_decision_message_sha256", vectors["decision_message_sha256"]),
        ("known_ed25519_signature", vectors["ed25519_signature"]),
        ("known_local_l2_commitment_sha256", vectors["local_l2_commitment_sha256"]),
        ("known_l1_operation_committed_revision", vectors["l1_operation_committed_revision"]),
        ("known_l2_synthetic_revision", vectors["l2_synthetic_revision"]),
        ("known_record_sequence", vectors["record_sequence"]),
        ("s11_nonignored_rust_tests", str(test_count)),
        ("profile", PROFILE.decode()),
        ("persistent_states", ",".join(PERSISTENT_STATES)),
        ("lookup_outcomes", ",".join(LOOKUP_OUTCOMES)),
        ("typed_l1_witness_required", "true"),
        ("sealed_private_provider_interface", "true"),
        ("production_provider_present", "false"),
        ("production_constructor_present", "false"),
        ("external_database_present", "false"),
        ("database_or_kms_adapter_present", "false"),
        ("network_client_present", "false"),
        ("state_store_surface_present", "false"),
        ("bridge_runtime_caller_present", "false"),
        ("biocortex_runtime_influence", "false"),
        ("local_l2_commitment_is_authenticated_persistence_receipt", "false"),
        ("database_kms_cross_service_atomicity_proved", "false"),
        ("exactly_once_signing_proved", "false"),
        ("signer_non_equivocation_proved", "false"),
        ("owner_trust_proved", "false"),
        ("successor_payload_admitted", "false"),
        ("cross_repository_transport_authorized", "false"),
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
        test_count = check_source(repo, vectors)
        check_contract(repo, vectors, test_count)
        check_gate(repo)
    except (CheckFailure, KeyError, TypeError, ValueError, OSError, tomllib.TOMLDecodeError) as exc:
        print(f"S11_CHECK_FAILED\t{exc}", file=sys.stderr)
        return 1
    sys.stdout.write(receipt(test_count, vectors))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
