#!/usr/bin/env python3
"""Fail-closed checker for the frozen S12 recovered-S9 re-verification tree.

S12 is a private, default-off, synthetic construction.  The checker validates
the exact S9/S10/S11 glue, independently rebuilds all framed known-answer
messages, and verifies the S9, S10, and S11 Ed25519 test signatures without
sharing Rust implementation code.  Its output is historical evidence only:
it is not currentness, admission, owner approval, durability, or transport.
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
from collections import Counter
from pathlib import Path
from types import ModuleType
from typing import Any


# Loading the frozen S9 reference must not create __pycache__ in an archive or
# in a clean integration tree.
sys.dont_write_bytecode = True

STATUS = (
    "RECOVERED_S9_DECISION_PURE_REVERIFICATION_PREREGISTERED_SYNTHETIC_"
    "DUAL_SIGNATURE_HISTORICAL_ONLY_NO_CURRENTNESS_RETRY_NO_ADMISSION_NO_"
    "PROVIDER_NO_OWNER_TRUST_ANCHOR_NOT_AUTHORIZED_NOT_TRANSPORT"
)
DECISION = "BLOCKED_FAIL_CLOSED"
FEATURE = "temporal-evidence-s12-recovered-s9-decision-reverification-synthetic"
S11_FEATURE = "temporal-evidence-s11-atomic-authority-operation-synthetic"
S10_FEATURE = "temporal-evidence-s10-operation-recovery-synthetic"
S9_FEATURE = "temporal-evidence-s9-external-authority-provider-synthetic"
BASE_COMMIT = "8daa44ee5406b700c59b57b0e44514421bc2f0ad"
S11_FEATURE_COMMIT = "efe75d17a59704a4efa8e062dea9474375e600dd"

CONTRACT_PATH = (
    "docs/design/fixtures/"
    "biocortex-ab-track-b-recovered-s9-decision-reverification-s12-v0.json"
)
GATE_PATH = "docs/design/fixtures/biocortex-ab-track-b-successor-admission-gate-s12-v0.json"
SOURCE_PATH = (
    "crates/store/src/temporal_replay_transport/"
    "recovered_s9_decision_reverification.rs"
)
STORE_CARGO_PATH = "crates/store/Cargo.toml"
PARENT_MODULE_PATH = "crates/store/src/temporal_replay_transport.rs"
S9_SOURCE_PATH = "crates/store/src/temporal_replay_transport/external_restore_authority.rs"
S10_SOURCE_PATH = "crates/store/src/temporal_replay_transport/external_operation_recovery.rs"
S11_SOURCE_PATH = (
    "crates/store/src/temporal_replay_transport/"
    "external_authority_operation_state_machine.rs"
)

# Freeze these only after the implementation and contracts are reviewed.  They
# intentionally do not include this checker: a checker must not self-authenticate.
CONTRACT_SHA256 = "4efa9dc533cfca6c98473ae20cf8fc983292362e92b669575a81e80e189b1303"
GATE_SHA256 = "7a580c64ae736a3dd8257af8fd2a81a027ecfe4cbf85fb3205bd25b6a25d9eb6"
SOURCE_SHA256 = "1665def3ed58292d49980b71a2d5bfb9ced0e071542f7bfffb391054b058e3c2"
STORE_CARGO_SHA256 = "40bbcc10effa7137a5c0b08d2b89c70285b4b1503b441c732398b803d01e96dc"
PARENT_MODULE_SHA256 = "f47f6ca04f347cc8b8c2d5f44308906f953ad78656fc27cfc141873a5c8f7f91"
S9_SOURCE_SHA256 = "431c5d145682d4b13b244c7dcf6fefba0252f1d212e64a5593625b3088ff5322"
S10_SOURCE_SHA256 = "f9a27f30f7928dd97de2bc7bc4a0d550bd957feb7dd7125dccfde7d40188da27"
S11_SOURCE_SHA256 = "61ba010375d465ef36ef35cff4c8315ca2a577bae1d030ba085c4aec6d68ea1c"

S9_CONTRACT_PATH = (
    "docs/design/fixtures/biocortex-ab-track-b-external-authority-provider-s9-v0.json"
)
S10_CONTRACT_PATH = (
    "docs/design/fixtures/biocortex-ab-track-b-external-operation-recovery-s10-v0.json"
)
S11_CONTRACT_PATH = (
    "docs/design/fixtures/biocortex-ab-track-b-atomic-authority-operation-s11-v0.json"
)
S11_GATE_PATH = "docs/design/fixtures/biocortex-ab-track-b-successor-admission-gate-s11-v0.json"
S9_CHECKER_PATH = "scripts/eval/check_memory_temporal_external_authority_provider_s9.py"
S10_CHECKER_PATH = "scripts/eval/check_memory_temporal_external_operation_recovery_s10.py"
S11_CHECKER_PATH = "scripts/eval/check_memory_temporal_atomic_authority_operation_s11.py"
S9_CONTRACT_SHA256 = "d537b80ce0d2bbb3c4d01a988a9685432672078eae07d0b976b1268a27526fc4"
S10_CONTRACT_SHA256 = "da3566f13df522958f05c871ad4679d89cda9b888ba8aa4eb4caaee4c457fb88"
S11_CONTRACT_SHA256 = "eaca1280836bb31a3e1d0ce11173c6e34dbddf24a19e270af21d579428327db2"
S11_GATE_SHA256 = "2d932c2b82fa41478ad42630bc9bae60467088027d046e7c14bed6a776d69cac"
S9_CHECKER_SHA256 = "ad7e373f539b780dd71af7f226464412442e3274ce98b0246329c0401a42995f"
S10_CHECKER_SHA256 = "43ef19fce89e6cc6febcd7d774d5fac7d147ebcbcb21034e41dadf6978e0a096"
S11_CHECKER_SHA256 = "bb92bad4648d865a3cf72b6c00c4f6bfaad07b6f3a3e0ece48e938c85c1b45a7"
S9_HISTORICAL_SOURCE_SHA256 = "dd92c2b064c1a4c1e5a4119777f1b5bf21a46d0fc9cb77656845f05e48655d9b"
S10_HISTORICAL_SOURCE_SHA256 = "850ddf4c47c76e9008671d44c47ba944b384744a4c50640e134e6c24008d90e4"
S11_HISTORICAL_SOURCE_SHA256 = "ffe01c13aadec867921ffd23f39f3ecc5d443bc44d30654f7fcd0be10e04793c"

POLICY = b"agent-bridge/track-b/recovered-s9-decision-reverification/v1"
PROFILE = (
    b"PURE_DETACHED_S9_PLUS_VERIFIED_S10_RECOVERY_PLUS_SIGNED_S11_L1_"
    b"HISTORICAL_ONLY"
)
AUTHORITY_SNAPSHOT_DOMAIN = (
    b"agent-bridge/track-b/recovered-s9-decision-reverification/authority-snapshot/v1"
)
HISTORICAL_CHAIN_DOMAIN = (
    b"agent-bridge/track-b/recovered-s9-decision-reverification/historical-chain/v1"
)
MAX_CANONICAL_MESSAGE_BYTES = 65536

S9_POLICY = b"agent-bridge/track-b/external-authority-provider/v1"
S9_REQUEST_DOMAIN = (
    b"agent-bridge/track-b/external-authority-provider/currentness-request/v1"
)
S9_DECISION_DOMAIN = (
    b"agent-bridge/track-b/external-authority-provider/currentness-decision/v1"
)
S9_KEY_REF_DOMAIN = b"agent-bridge/track-b/external-authority-provider/opaque-key-ref/v1"
S9_KEYSET_DOMAIN = b"agent-bridge/track-b/external-authority-provider/opaque-keyset/v1"
S9_REVOCATION_DOMAIN = (
    b"agent-bridge/track-b/external-authority-provider/revocation-checkpoint/v1"
)
S9_CUSTODY_DOMAIN = b"agent-bridge/track-b/external-authority-provider/custody-claim/v1"
S9_USE_DENIED_DOMAIN = (
    b"agent-bridge/track-b/external-authority-provider/use-denied-claim/v1"
)
S9_DECISION_ID_DOMAIN = b"agent-bridge/track-b/external-authority-provider/decision-id/v1"

S10_POLICY = b"agent-bridge/track-b/external-operation-recovery/v1"
S10_PROFILE = b"LOOKUP_ONLY_IDEMPOTENT_NO_SUBMIT_NO_RETRY_NO_CACHE_NO_WALL_CLOCK"
S10_QUERY_DOMAIN = b"agent-bridge/track-b/external-operation-recovery/lookup-query/v1"
S10_OBSERVATION_DOMAIN = (
    b"agent-bridge/track-b/external-operation-recovery/lookup-observation/v1"
)
S10_RESULT_DOMAIN = b"agent-bridge/track-b/external-operation-recovery/result-id/v1"

S11_POLICY = b"agent-bridge/track-b/atomic-authority-operation/v1"
S11_PROFILE = (
    b"DB_L1_ATOMIC_OUTBOX_EXACT_VERSION_RESIGN_DB_L2_VERIFIED_CAS_NO_KEY_FALLBACK"
)
S11_REQUEST_DOMAIN = b"agent-bridge/track-b/atomic-authority-operation/request/v1"
S11_PREPARED_DOMAIN = (
    b"agent-bridge/track-b/atomic-authority-operation/prepared-record/v1"
)
S11_SIGN_JOB_DOMAIN = b"agent-bridge/track-b/atomic-authority-operation/sign-job/v1"
S11_STABLE_DOMAIN = b"agent-bridge/track-b/atomic-authority-operation/stable-result/v1"
S11_DECISION_DOMAIN = (
    b"agent-bridge/track-b/atomic-authority-operation/decision-message/v1"
)
S11_L2_DOMAIN = b"agent-bridge/track-b/atomic-authority-operation/synthetic-l2-record/v1"
ALGORITHM = b"Ed25519"
S9_LEASE = b"ONE_ATTEMPT_NO_CACHE_NO_WALL_CLOCK"

S9_SEED = bytes.fromhex(
    "9d61b19deffd5a60ba844af492ec2cc44449c5697b326919703bac031cae7f60"
)
S10_SEED = bytes.fromhex(
    "c5aa8df43f9f837bedb7442f31dcb7b166d38535076f094b85ce3a2e0b4458f7"
)
S11_SEED = bytes.fromhex(
    "4ccd089b28ff96da9db6c346ec114e0f5b8a319f35aba624da8cf6ed4fb8a6fb"
)
S9_PUBLIC_KEY = bytes.fromhex(
    "d75a980182b10ab7d54bfed3c964073a0ee172f3daa62325af021a68f707511a"
)
S10_PUBLIC_KEY = bytes.fromhex(
    "fc51cd8e6218a1a38da47ed00230f0580816ed13ba3303ac5deb911548908025"
)
S11_PUBLIC_KEY = bytes.fromhex(
    "3d4017c3e843895a92b70aa74d1b7ebc9c982ccf2ec4968cc0cd55f12af4660c"
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
    "RECOVERED_S9_DECISION_EXTERNAL_CARRIER_UNIMPLEMENTED",
    "RECOVERED_S9_DECISION_BYTES_AVAILABILITY_UNATTESTED",
    "RECOVERED_S9_RAW_DECISION_EXTERNAL_DURABILITY_UNATTESTED",
    "RECOVERED_S10_VERIFIED_PROJECTION_RUNTIME_DELIVERY_UNIMPLEMENTED",
    "RECOVERED_S9_DECISION_HISTORICAL_ONLY_NOT_CURRENT_AT_USE",
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
    "remaining_gap_codes",
    "required_successor_identity",
    "reverification_preregistration",
    "schema",
    "status",
)
S12_TEST_COUNT = 32
S9_RETAINED_TEST_COUNT = 15
CONTRACT_TEST_MATRIX_KEYS = (
    "appended_decision_bytes_reject",
    "appended_request_bytes_reject",
    "authority_snapshot_recompute_required",
    "carrier_bounds_reject",
    "corrupt_l2_metadata_ignored",
    "deterministic_pure_reverification",
    "historical_output_non_admission",
    "journal_generation_cross_binding",
    "known_answer_three_link_chain",
    "l2_rewrite_does_not_change_chain",
    "later_revocation_does_not_upgrade_history",
    "non_active_states_reject",
    "oversized_typed_decision_label_rejects_before_framing",
    "s10_operation_challenge_binding",
    "s10_request_decision_binding",
    "s10_s11_nonregressing_term_and_exact_revision_sequence",
    "s10_scope_provider_trust_binding",
    "s11_operation_challenge_binding",
    "s11_owner_pin_required",
    "s11_request_decision_binding",
    "s11_scope_binding",
    "s11_signature_required",
    "s9_and_s11_key_ids_distinct",
    "s9_and_s11_public_keys_distinct",
    "s9_floor_epoch_generation_keyset_revocation",
    "s9_operation_binding",
    "s9_owner_pin_required",
    "s9_scope_binding",
    "s9_signature_required",
    "swapped_permits_reject",
    "truncated_decision_bytes_reject",
    "truncated_request_bytes_reject",
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


def require_exact(actual: Any, expected: Any, message: str) -> None:
    require(type_strict_equal(actual, expected), message)


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
    spec = importlib.util.spec_from_file_location(
        "s12_pinned_s9_ed25519_reference", repo / S9_CHECKER_PATH
    )
    require(spec is not None and spec.loader is not None, "cannot load pinned S9 reference")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    for name in (
        "framed_message",
        "framed_digest",
        "ed25519_public_key",
        "ed25519_sign",
        "ed25519_verify",
    ):
        require(callable(getattr(module, name, None)), f"pinned S9 reference missing: {name}")
    return module


def independent_vectors(repo: Path) -> dict[str, str | int]:
    ref = import_s9_reference(repo)
    framed_message = ref.framed_message
    framed_digest = ref.framed_digest
    repeated = lambda value: bytes([value]) * 32
    u64 = lambda value: value.to_bytes(8, "big")

    s9_contract = bytes.fromhex(S9_CONTRACT_SHA256)
    s10_contract = bytes.fromhex(S10_CONTRACT_SHA256)
    s11_contract = bytes.fromhex(S11_CONTRACT_SHA256)
    provider_profile = b"owner-selected-provider-v1"
    namespace = b"agent-bridge-research-prod"
    tenant = b"agent-bridge"
    audience = b"ab-store-restore-admission"
    cluster = b"authority-cluster-a"
    incarnation = repeated(0x61)
    operation = repeated(0x21)
    challenge = repeated(0x31)
    epoch_record = repeated(0x41)
    generation = repeated(0x42)
    trust_policy = repeated(0x71)

    def opaque_key_ref(key_id: bytes, version: int, role: bytes) -> bytes:
        return framed_digest(
            S9_KEY_REF_DOMAIN,
            [
                S9_POLICY,
                provider_profile,
                namespace,
                cluster,
                incarnation,
                key_id,
                u64(version),
                role,
                b"hmac-sha-256",
            ],
        )

    keyset = framed_digest(
        S9_KEYSET_DOMAIN,
        [
            S9_POLICY,
            opaque_key_ref(b"handle-key", 11, b"HANDLE"),
            opaque_key_ref(b"inner-key", 12, b"INNER_TRANSPORT"),
            opaque_key_ref(b"outer-key", 13, b"OUTER_CHANNEL"),
        ],
    )
    s9_request_message = framed_message(
        S9_REQUEST_DOMAIN,
        [
            S9_POLICY,
            ALGORITHM,
            S9_LEASE,
            provider_profile,
            namespace,
            tenant,
            audience,
            operation,
            challenge,
            u64(2),
            epoch_record,
            generation,
            repeated(0x43),
            repeated(0x44),
            repeated(0x45),
            keyset,
            trust_policy,
        ],
    )
    s9_request_sha256 = hashlib.sha256(s9_request_message).digest()
    revocation = framed_digest(S9_REVOCATION_DOMAIN, [s9_request_sha256, u64(42)])
    custody = framed_digest(S9_CUSTODY_DOMAIN, [keyset, u64(2), u64(42)])
    use_denied = framed_digest(S9_USE_DENIED_DOMAIN, [epoch_record, u64(2), u64(42)])
    decision_id = framed_digest(S9_DECISION_ID_DOMAIN, [operation, challenge, u64(42)])
    s9_decision_message = framed_message(
        S9_DECISION_DOMAIN,
        [
            S9_POLICY,
            ALGORITHM,
            S9_LEASE,
            s9_request_sha256,
            b"ACTIVE",
            cluster,
            incarnation,
            u64(7),
            u64(42),
            u64(1),
            u64(2),
            epoch_record,
            generation,
            keyset,
            revocation,
            u64(1),
            custody,
            use_denied,
            decision_id,
            b"currentness-signer-a",
            u64(3),
        ],
    )
    s9_decision_sha256 = hashlib.sha256(s9_decision_message).digest()
    s9_public_key = ref.ed25519_public_key(S9_SEED)
    s9_signature = ref.ed25519_sign(S9_SEED, s9_decision_message)

    journal_generation = repeated(0x72)
    s10_query_sha256 = framed_digest(
        S10_QUERY_DOMAIN,
        [
            S10_POLICY,
            ALGORITHM,
            S10_PROFILE,
            s9_contract,
            provider_profile,
            namespace,
            tenant,
            audience,
            cluster,
            incarnation,
            repeated(0x51),
            repeated(0x52),
            operation,
            challenge,
            s9_request_sha256,
            trust_policy,
        ],
    )
    s10_result_id = framed_digest(
        S10_RESULT_DOMAIN,
        [
            S10_POLICY,
            s9_contract,
            operation,
            challenge,
            s9_request_sha256,
            u64(43),
            journal_generation,
            u64(10),
            s9_decision_sha256,
        ],
    )
    s10_observation_message = framed_message(
        S10_OBSERVATION_DOMAIN,
        [
            S10_POLICY,
            ALGORITHM,
            S10_PROFILE,
            s9_contract,
            s10_query_sha256,
            b"COMMITTED",
            operation,
            challenge,
            s9_request_sha256,
            cluster,
            incarnation,
            u64(7),
            u64(43),
            u64(50),
            journal_generation,
            u64(10),
            s9_decision_sha256,
            s10_result_id,
            b"recovery-signer-a",
            u64(4),
        ],
    )
    s10_observation_sha256 = hashlib.sha256(s10_observation_message).digest()
    s10_public_key = ref.ed25519_public_key(S10_SEED)
    s10_signature = ref.ed25519_sign(S10_SEED, s10_observation_message)

    authority_snapshot = framed_digest(
        AUTHORITY_SNAPSHOT_DOMAIN,
        [
            POLICY,
            s9_contract,
            s9_request_sha256,
            s9_decision_sha256,
            provider_profile,
            namespace,
            tenant,
            audience,
            operation,
            challenge,
            cluster,
            incarnation,
            u64(7),
            u64(42),
            u64(1),
            u64(2),
            epoch_record,
            generation,
            keyset,
            revocation,
            u64(1),
            custody,
            use_denied,
            decision_id,
            b"currentness-signer-a",
            u64(3),
            trust_policy,
        ],
    )

    concrete_replay = repeated(0x25)
    s11_request_sha256 = framed_digest(
        S11_REQUEST_DOMAIN,
        [
            S11_POLICY,
            S11_PROFILE,
            ALGORITHM,
            s9_contract,
            s10_contract,
            provider_profile,
            namespace,
            tenant,
            audience,
            cluster,
            incarnation,
            journal_generation,
            operation,
            challenge,
            s9_request_sha256,
            concrete_replay,
            authority_snapshot,
            s9_decision_sha256,
            trust_policy,
            b"authority-operation-signer-a",
            u64(5),
        ],
    )
    prepared = framed_digest(
        S11_PREPARED_DOMAIN,
        [S11_POLICY, b"DECISION_COMMITTED_UNSIGNED", s11_request_sha256, u64(7), u64(43), u64(10)],
    )
    sign_job = framed_digest(
        S11_SIGN_JOB_DOMAIN,
        [S11_POLICY, prepared, b"authority-operation-signer-a", u64(5)],
    )
    stable = framed_digest(S11_STABLE_DOMAIN, [S11_POLICY, prepared, sign_job])
    s11_decision_message = framed_message(
        S11_DECISION_DOMAIN,
        [
            S11_POLICY,
            S11_PROFILE,
            ALGORITHM,
            s9_contract,
            s10_contract,
            s11_request_sha256,
            operation,
            challenge,
            s9_request_sha256,
            concrete_replay,
            authority_snapshot,
            s9_decision_sha256,
            cluster,
            incarnation,
            journal_generation,
            u64(7),
            u64(43),
            u64(10),
            prepared,
            sign_job,
            stable,
            b"authority-operation-signer-a",
            u64(5),
            trust_policy,
        ],
    )
    s11_decision_sha256 = hashlib.sha256(s11_decision_message).digest()
    s11_public_key = ref.ed25519_public_key(S11_SEED)
    s11_signature = ref.ed25519_sign(S11_SEED, s11_decision_message)
    l2_revision_52 = framed_digest(
        S11_L2_DOMAIN,
        [S11_POLICY, b"SIGNED_COMMITTED", stable, s11_decision_sha256, s11_signature, u64(52)],
    )
    l2_revision_99 = framed_digest(
        S11_L2_DOMAIN,
        [S11_POLICY, b"SIGNED_COMMITTED", stable, s11_decision_sha256, s11_signature, u64(99)],
    )

    historical_chain = framed_digest(
        HISTORICAL_CHAIN_DOMAIN,
        [
            POLICY,
            PROFILE,
            s9_contract,
            s10_contract,
            s11_contract,
            provider_profile,
            namespace,
            tenant,
            audience,
            cluster,
            incarnation,
            operation,
            challenge,
            trust_policy,
            s9_request_sha256,
            s9_decision_sha256,
            decision_id,
            u64(1),
            u64(42),
            u64(2),
            generation,
            authority_snapshot,
            s10_query_sha256,
            s10_observation_sha256,
            s10_result_id,
            u64(7),
            u64(43),
            u64(50),
            journal_generation,
            u64(10),
            concrete_replay,
            s11_request_sha256,
            prepared,
            sign_job,
            stable,
            s11_decision_sha256,
            u64(7),
            u64(43),
            u64(10),
            b"currentness-signer-a",
            u64(3),
            b"authority-operation-signer-a",
            u64(5),
        ],
    )

    for actual, expected, label in (
        (s9_public_key, S9_PUBLIC_KEY, "S9 public key"),
        (s10_public_key, S10_PUBLIC_KEY, "S10 public key"),
        (s11_public_key, S11_PUBLIC_KEY, "S11 public key"),
    ):
        require(actual == expected, f"{label} drift")
    for public_key, message, signature, label in (
        (s9_public_key, s9_decision_message, s9_signature, "S9"),
        (s10_public_key, s10_observation_message, s10_signature, "S10"),
        (s11_public_key, s11_decision_message, s11_signature, "S11"),
    ):
        require(ref.ed25519_verify(public_key, message, signature), f"{label} signature failed")
        changed = bytearray(signature)
        changed[0] ^= 1
        require(
            not ref.ed25519_verify(public_key, message, bytes(changed)),
            f"{label} tampered signature accepted",
        )
    require(
        not ref.ed25519_verify(s11_public_key, s9_decision_message, s9_signature),
        "S9 signature accepted under S11 pin",
    )
    require(
        not ref.ed25519_verify(s9_public_key, s11_decision_message, s11_signature),
        "S11 signature accepted under S9 pin",
    )

    return {
        "authority_snapshot_sha256": authority_snapshot.hex(),
        "historical_chain_sha256": historical_chain.hex(),
        "s10_ed25519_public_key": s10_public_key.hex(),
        "s10_ed25519_signature": s10_signature.hex(),
        "s10_lookup_query_sha256": s10_query_sha256.hex(),
        "s10_observation_sha256": s10_observation_sha256.hex(),
        "s10_result_id": s10_result_id.hex(),
        "s11_decision_message_sha256": s11_decision_sha256.hex(),
        "s11_ed25519_public_key": s11_public_key.hex(),
        "s11_ed25519_signature": s11_signature.hex(),
        "s11_prepared_record_sha256": prepared.hex(),
        "s11_request_sha256": s11_request_sha256.hex(),
        "s11_sign_job_id": sign_job.hex(),
        "s11_stable_result_id": stable.hex(),
        "s11_synthetic_l2_record_sha256_at_revision_52": l2_revision_52.hex(),
        "s11_synthetic_l2_record_sha256_at_revision_99": l2_revision_99.hex(),
        "s9_decision_id": decision_id.hex(),
        "s9_decision_message_sha256": s9_decision_sha256.hex(),
        "s9_ed25519_public_key": s9_public_key.hex(),
        "s9_ed25519_signature": s9_signature.hex(),
        "s9_request_sha256": s9_request_sha256.hex(),
    }


def contract_vector(vectors: dict[str, str | int]) -> dict[str, str]:
    excluded = {"s10_ed25519_public_key", "s10_ed25519_signature"}
    return {key: str(value) for key, value in vectors.items() if key not in excluded}


def check_predecessors(repo: Path) -> None:
    for path, expected, label in (
        (S9_CONTRACT_PATH, S9_CONTRACT_SHA256, "S9 contract"),
        (S10_CONTRACT_PATH, S10_CONTRACT_SHA256, "S10 contract"),
        (S11_CONTRACT_PATH, S11_CONTRACT_SHA256, "S11 contract"),
        (S11_GATE_PATH, S11_GATE_SHA256, "S11 gate"),
        (S9_CHECKER_PATH, S9_CHECKER_SHA256, "S9 checker"),
        (S10_CHECKER_PATH, S10_CHECKER_SHA256, "S10 checker"),
        (S11_CHECKER_PATH, S11_CHECKER_SHA256, "S11 checker"),
    ):
        require(sha256(repo, path) == expected, f"{label} digest drift")


def check_contract(repo: Path, vectors: dict[str, str | int]) -> None:
    require(sha256(repo, CONTRACT_PATH) == CONTRACT_SHA256, "S12 contract digest drift")
    contract = load_json(repo, CONTRACT_PATH)
    require(set(contract) == set(CONTRACT_TOP_LEVEL_KEYS), "S12 contract top-level keys drift")
    require_exact(
        contract["schema"],
        "agent_bridge.memory_temporal_recovered_s9_decision_reverification_contract_s12.v0",
        "S12 contract schema drift",
    )
    require_exact(contract["status"], STATUS, "S12 contract status drift")
    require_exact(contract["decision"], DECISION, "S12 contract decision drift")
    require_exact(
        contract["dependency"],
        {"default_enabled": False, "depends_on_feature": S11_FEATURE, "feature": FEATURE},
        "S12 dependency drift",
    )
    require_exact(
        contract["boundary"],
        {
            "bridge_integration": False,
            "currentness_at_downstream_use_attested": False,
            "external_carrier_implemented": False,
            "external_database_or_kms_integrated": False,
            "network_or_provider_call": False,
            "owner_approval_receipt_present": False,
            "production_admission_authorized": False,
            "state_store_integration": False,
            "transport_implemented": False,
        },
        "S12 boundary drift",
    )
    require_exact(
        contract["evidence_boundary"],
        {
            "authority_snapshot_formula_recomputed": True,
            "canonical_raw_s9_bytes_required": True,
            "historical_commitment_is_a_signature": False,
            "historical_observation_is_admission": False,
            "historical_observation_is_currentness": False,
            "s10_verified_committed_projection_required": True,
            "s11_l1_signature_reverified": True,
            "s11_l2_metadata_authenticated": False,
            "s11_l2_metadata_in_historical_commitment": False,
            "s9_original_signature_reverified": True,
            "s9_one_attempt_token_recovered": False,
        },
        "S12 evidence boundary drift",
    )
    require_exact(
        contract["failure_semantics"],
        {
            "ambiguous_or_conflicting_input_returns_evidence": False,
            "malformed_or_noncanonical_bytes_return_evidence": False,
            "missing_s10_projection_returns_evidence": False,
            "non_active_s9_decision_returns_evidence": False,
            "signature_or_permit_failure_returns_evidence": False,
            "unknown_or_trailing_input_returns_evidence": False,
        },
        "S12 failure semantics drift",
    )
    require_exact(
        contract["implementation"],
        {
            "authority_snapshot_domain": AUTHORITY_SNAPSHOT_DOMAIN.decode(),
            "external_carrier": False,
            "historical_chain_domain": HISTORICAL_CHAIN_DOMAIN.decode(),
            "max_canonical_message_bytes": MAX_CANONICAL_MESSAGE_BYTES,
            "module_path": SOURCE_PATH,
            "module_visibility": "private_child_of_private_s6_module",
            "production_constructor": False,
            "provider_call": False,
            "s10_raw_signature_reverified_in_s12": False,
            "s10_verified_projection_runtime_delivery": False,
            "s11_shared_verifier_profile": "AUTHENTICATED_L1_ONLY_L2_UNREAD",
            "s9_shared_verifier_profile": "PURE_DETACHED_EXACT_DECISION",
            "serde_or_wire_schema": False,
            "side_effects_unlocked": "NONE",
        },
        "S12 implementation boundary drift",
    )
    require_exact(contract["known_vector"], contract_vector(vectors), "S12 known vector drift")
    require_exact(contract["remaining_gap_codes"], list(REMAINING_GAPS), "remaining gaps drift")
    require_exact(contract["operational_gap_codes"], list(OPERATIONAL_GAPS), "operational gaps drift")
    require_exact(
        contract["predecessor"],
        {
            "baseline_merge_commit": BASE_COMMIT,
            "s11_feature_commit": S11_FEATURE_COMMIT,
            "s9": {
                "checker_sha256": S9_CHECKER_SHA256,
                "contract_sha256": S9_CONTRACT_SHA256,
                "historical_source_sha256": S9_HISTORICAL_SOURCE_SHA256,
            },
            "s10": {
                "checker_sha256": S10_CHECKER_SHA256,
                "contract_sha256": S10_CONTRACT_SHA256,
                "historical_source_sha256": S10_HISTORICAL_SOURCE_SHA256,
            },
            "s11": {
                "checker_sha256": S11_CHECKER_SHA256,
                "contract_sha256": S11_CONTRACT_SHA256,
                "historical_source_sha256": S11_HISTORICAL_SOURCE_SHA256,
            },
        },
        "S12 predecessor binding drift",
    )
    require_exact(
        contract["protocol"],
        {
            "authority_snapshot_profile": "EXACT_S9_SCOPE_STATE_IDENTITY_SEQUENCE_AND_REVOCATION_COMMITMENTS",
            "historical_chain_profile": "LOCAL_DETERMINISTIC_COMMITMENT_NOT_SIGNATURE_NOT_ADMISSION",
            "policy": POLICY.decode(),
            "profile": PROFILE.decode(),
            "signature_algorithm": "Ed25519",
            "signature_roles": [
                "S9_CURRENTNESS_DECISION_SIGNER_OWNER_PIN_REQUIRED",
                "S11_ATOMIC_OPERATION_L1_SIGNER_OWNER_PIN_REQUIRED",
            ],
            "state_transition": "UNTRUSTED_RECOVERED_BUNDLE_TO_PRIVATE_HISTORICAL_OBSERVATION_OR_NO_OUTPUT",
            "u64_encoding": "BIG_ENDIAN_8_BYTES",
            "value_framing": "U64BE_LENGTH_THEN_EXACT_BYTES",
        },
        "S12 protocol drift",
    )
    require(isinstance(contract["test_matrix"], dict), "S12 test matrix missing")
    require(
        set(contract["test_matrix"]) == set(CONTRACT_TEST_MATRIX_KEYS),
        "S12 test matrix obligation keys drift",
    )
    require(all(value is True for value in contract["test_matrix"].values()), "S12 tests not required")
    require_exact(
        contract["negative_evidence"],
        {
            "corrupt_s11_l2_metadata_does_not_change_historical_chain": True,
            "historical_active_decision_cannot_be_upgraded_after_later_revocation": True,
            "provider_or_network_independence_is_executable": True,
            "runtime_recovery_bytes_available": False,
            "s10_lookup_linearizability_proved": False,
            "s11_l2_persistence_proved": False,
            "synthetic_test_pins_are_owner_approval": False,
        },
        "S12 negative evidence drift",
    )


def check_gate(repo: Path) -> None:
    require(sha256(repo, GATE_PATH) == GATE_SHA256, "S12 successor gate digest drift")
    gate = load_json(repo, GATE_PATH)
    require(set(gate) == set(GATE_TOP_LEVEL_KEYS), "S12 gate top-level keys drift")
    require_exact(
        gate["schema"],
        "agent_bridge.memory_temporal_successor_admission_gate_s12.v0",
        "S12 gate schema drift",
    )
    require_exact(gate["status"], STATUS, "S12 gate status drift")
    require_exact(gate["decision"], DECISION, "S12 gate decision drift")
    require_exact(gate["remaining_gap_codes"], list(REMAINING_GAPS), "gate remaining gaps drift")
    require_exact(gate["operational_gap_codes"], list(OPERATIONAL_GAPS), "gate operational gaps drift")
    require_exact(
        gate["predecessor"],
        {
            "baseline_merge_commit": BASE_COMMIT,
            "s11_contract_sha256": S11_CONTRACT_SHA256,
            "s11_feature_commit": S11_FEATURE_COMMIT,
        },
        "gate predecessor drift",
    )
    require_exact(
        gate["admission"],
        {
            "bridge_or_state_store_enabled": False,
            "currentness_token_issued": False,
            "owner_approval_receipt": None,
            "production_authorized": False,
            "successor_payload_admitted": False,
            "transport_enabled": False,
        },
        "gate admission drift",
    )
    require_exact(
        gate["authorization_semantics"],
        {
            "historical_chain_is_admission_capability": False,
            "historical_s9_active_means_current_at_use": False,
            "s10_verified_projection_proves_external_durability": False,
            "s11_l1_signature_proves_l2_persistence": False,
            "synthetic_test_keys_are_owner_approval": False,
        },
        "gate authorization semantics drift",
    )
    require_exact(
        gate["boundary"],
        {
            "currentness_and_consume_atomic": False,
            "external_carrier_available": False,
            "owner_pinned_production_permits_available": False,
            "provider_linearizability_attested": False,
            "provider_rollback_or_split_brain_protected": False,
            "runtime_recovered_bytes_available": False,
        },
        "gate boundary drift",
    )
    require_exact(
        gate["reverification_preregistration"],
        {
            "canonical_raw_s9_bytes_required": True,
            "historical_chain_known_answer_frozen": True,
            "s10_verified_projection_required": True,
            "s11_l1_only_reverified": True,
            "s9_detached_verifier_shared": True,
            "synthetic_gap_closure_only": True,
        },
        "gate preregistration drift",
    )
    require_exact(
        gate["required_successor_identity"],
        {
            "admission_receipt": None,
            "external_carrier_and_durable_exact_s9_envelope": True,
            "external_currentness_and_consume_atomicity": True,
            "owner_pinned_production_permits": True,
            "provider_rollback_split_brain_and_rotation_evidence": True,
            "runtime_s10_verified_projection_delivery": True,
        },
        "gate successor requirements drift",
    )


def strip_rust_comments(source: str) -> str:
    source = re.sub(r"(?s)/\*.*?\*/", "", source)
    return re.sub(r"(?m)//.*$", "", source)


def struct_fields(source: str, name: str) -> list[str]:
    match = re.search(
        rf"(?ms)^(?:pub\(super\) )?struct {re.escape(name)}(?:<'[^>]+>)? \{{\n(?P<body>.*?)^\}}",
        source,
    )
    require(match is not None, f"missing Rust struct: {name}")
    return re.findall(r"(?m)^    (?:pub\(super\) )?([a-z][a-z0-9_]*):", match.group("body"))


def pub_super_struct_fields(source: str, name: str) -> list[str]:
    match = re.search(
        rf"(?ms)^(?:pub\(super\) )?struct {re.escape(name)}(?:<'[^>]+>)? \{{\n(?P<body>.*?)^\}}",
        source,
    )
    require(match is not None, f"missing Rust struct: {name}")
    return re.findall(r"(?m)^    pub\(super\) ([a-z][a-z0-9_]*):", match.group("body"))


def permit_impl_methods(source: str, name: str) -> tuple[list[str], str]:
    marker = f"impl {name} {{"
    require(source.count(marker) == 1, f"permit impl count drift: {name}")
    tail = source.split(marker, 1)[1]
    end = f"\n}}\n\nimpl fmt::Debug for {name}"
    require(end in tail, f"cannot delimit permit impl: {name}")
    body = tail.split(end, 1)[0]
    return re.findall(r"(?m)^    pub\(super\) fn ([a-z][a-z0-9_]*)\(", body), body


def shared_items(source: str) -> list[str]:
    return re.findall(
        r"(?m)^pub\(super\) (?:struct|enum|type|fn) ([A-Za-z_][A-Za-z0-9_]*)",
        source,
    )


def rust_u8_array(source: str, name: str, length: int) -> bytes:
    match = re.search(
        rf"(?ms)^    const {re.escape(name)}: \[u8; {length}\] = \[(?P<body>.*?)^    \];",
        source,
    )
    require(match is not None, f"missing Rust byte vector: {name}")
    value = bytes(int(item, 16) for item in re.findall(r"0x([0-9a-fA-F]{2})", match.group("body")))
    require(len(value) == length, f"Rust vector length drift: {name}")
    return value


def rust_root_u8_array(source: str, name: str, length: int) -> bytes:
    match = re.search(
        rf"(?ms)^const {re.escape(name)}: \[u8; {length}\] = \[(?P<body>.*?)^\];",
        source,
    )
    require(match is not None, f"missing Rust root vector: {name}")
    value = bytes(int(item, 16) for item in re.findall(r"0x([0-9a-fA-F]{2})", match.group("body")))
    require(len(value) == length, f"Rust root vector length drift: {name}")
    return value


def bridge_has_surface(repo: Path, needles: tuple[str, ...]) -> bool:
    root = repo / "crates/bridge"
    require(root.is_dir() and not root.is_symlink(), "missing/non-regular Bridge crate")
    for directory, directory_names, file_names in os.walk(root, followlinks=False):
        base = Path(directory)
        for name in directory_names:
            require(not (base / name).is_symlink(), f"symlink in Bridge tree: {base / name}")
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
    for path, expected, label in (
        (CONTRACT_PATH, CONTRACT_SHA256, "S12 contract"),
        (GATE_PATH, GATE_SHA256, "S12 gate"),
        (SOURCE_PATH, SOURCE_SHA256, "S12 source"),
        (STORE_CARGO_PATH, STORE_CARGO_SHA256, "Store Cargo"),
        (PARENT_MODULE_PATH, PARENT_MODULE_SHA256, "parent module"),
        (S9_SOURCE_PATH, S9_SOURCE_SHA256, "S9 glue"),
        (S10_SOURCE_PATH, S10_SOURCE_SHA256, "S10 glue"),
        (S11_SOURCE_PATH, S11_SOURCE_SHA256, "S11 glue"),
    ):
        require(sha256(repo, path) == expected, f"{label} digest drift")

    cargo = tomllib.loads(read_text(repo, STORE_CARGO_PATH))
    features = cargo.get("features", {})
    require(isinstance(features, dict), "Cargo feature table missing")
    require(features.get(S10_FEATURE) == [S9_FEATURE], "retained S10 dependency drift")
    require(features.get(S11_FEATURE) == [S10_FEATURE], "retained S11 dependency drift")
    require(features.get(FEATURE) == [S11_FEATURE], "S12 feature dependency drift")
    defaults = features.get("default", [])
    require(isinstance(defaults, list), "Cargo default feature list drift")
    require(not feature_is_reachable(features, defaults, FEATURE), "S12 became default")

    parent = read_text(repo, PARENT_MODULE_PATH)
    library = read_text(repo, "crates/store/src/lib.rs")
    module_name = "recovered_s9_decision_reverification"
    expected_gate = f'#[cfg(feature = "{FEATURE}")]\nmod {module_name};'
    require(parent.count(expected_gate) == 1, "private S12 module gate missing/duplicated")
    require(f"pub mod {module_name}" not in parent, "S12 module became public")
    require(f"pub use {module_name}" not in parent + library, "S12 re-export forbidden")
    require(FEATURE not in library and module_name not in library, "S12 leaked to Store library")
    require(
        not bridge_has_surface(repo, (FEATURE, module_name, "PurelyReverifiedRecoveredS9DecisionV1")),
        "S12 leaked to Bridge surface",
    )

    source = read_text(repo, SOURCE_PATH)
    split = source.split("#[cfg(test)]\nmod tests", 1)
    require(len(split) == 2, "S12 test implementation is not cfg(test)-isolated")
    production, tests = split
    code = strip_rust_comments(production)
    for forbidden in (
        "StateStore",
        "Bridge",
        "request_currentness",
        "lookup_operation",
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
        "sqlx::",
        "postgres::",
        "redis::",
        "aws_sdk_kms",
        "std::fs",
        "SystemTime",
        "Instant::now",
        "std::time",
        "serde::",
        "Serialize",
        "synthetic_l2_revision",
        "synthetic_l2_record_sha256",
    ):
        require(forbidden not in code, f"forbidden S12 production surface: {forbidden}")
    require("pub(super)" not in code, "S12 introduced a sibling-visible capability")
    require(
        not re.search(r"\bpub(?:\(crate\))?\s+(?:fn|struct|enum|trait|use|mod)\b", code),
        "S12 capability became public/crate-public",
    )
    require("serde::" not in source and "Serialize" not in source, "S12 evidence became serializable")
    require("impl RecoveredS9DecisionBundleV1" not in production, "production carrier constructor added")
    require("impl PurelyReverifiedRecoveredS9DecisionV1" not in production, "capability conversion added")
    require(
        struct_fields(source, "RecoveredS9DecisionBundleV1")
        == ["request", "canonical_request_bytes", "decision", "canonical_decision_message_bytes"],
        "S12 recovered bundle shape drift",
    )
    require(
        struct_fields(source, "PurelyReverifiedRecoveredS9DecisionV1")
        == [
            "historical_chain_sha256",
            "s9_request_sha256",
            "s9_decision_message_sha256",
            "s9_decision_id",
            "s10_recovery_result_id",
            "s11_stable_result_id",
            "authority_sequence",
            "s9_committed_revision",
            "active_epoch",
            "registry_generation_id",
        ],
        "S12 output shape drift",
    )
    require(
        "#[must_use]\nstruct PurelyReverifiedRecoveredS9DecisionV1" in source,
        "S12 output lost private must-use shape",
    )
    for required in (
        "fn authority_snapshot_digest(",
        "fn historical_chain_digest(",
        "fn verify_recovered_s9_decision_v1(",
        "verify_external_currentness_decision_v1(",
        "verify_signed_committed_operation_l1_v1(",
        "validated_s9_decision_message(",
        "S9 currentness and S11 operation authentication roles must be independently pinned",
        "s11_verified.operation_committed_revision() != s10_verified.operation_committed_revision()",
        "s11_verified.record_sequence() != s10_verified.journal_record_sequence()",
        "s10_verified.leader_term() < s11_record.leader_term",
        "s11_verified.operation_committed_revision() > s10_verified.observed_journal_revision()",
        "s10_verified.journal_generation_id() != s11_request.journal_generation_id",
    ):
        require(required in source, f"missing S12 invariant: {required}")
    require(PROFILE.decode() in production, "S12 profile drift")
    require(AUTHORITY_SNAPSHOT_DOMAIN.decode() in production, "authority snapshot domain drift")
    require(HISTORICAL_CHAIN_DOMAIN.decode() in production, "historical chain domain drift")

    s9_source = read_text(repo, S9_SOURCE_PATH)
    s10_source = read_text(repo, S10_SOURCE_PATH)
    s11_source = read_text(repo, S11_SOURCE_PATH)
    for glue, label in ((s9_source, "S9"), (s10_source, "S10"), (s11_source, "S11")):
        glue_code = strip_rust_comments(glue.split("#[cfg(test)]\nmod tests", 1)[0])
        require("serde::" not in glue_code and "Serialize" not in glue_code, f"{label} glue serialized")
        require(
            not re.search(r"\bpub(?:\(crate\))?\s+(?:fn|struct|enum|trait|use|mod)\b", glue_code),
            f"{label} glue became public/crate-public",
        )

    require(
        shared_items(s9_source)
        == [
            "ExternalAuthorityContractV1Error",
            "ContractResult",
            "ExternalCurrentnessRequestV1",
            "request_message",
            "request_digest",
            "ExternalAuthorityStateV1",
            "SignedExternalCurrentnessDecisionV1",
            "validated_decision_message",
            "ExternalAuthorityTrustPermitV1",
            "VerifiedExternalCurrentnessDecisionV1",
            "verify_external_currentness_decision_v1",
        ],
        "S9 shared surface drift",
    )
    require(
        struct_fields(s9_source, "VerifiedExternalCurrentnessDecisionV1")
        == [
            "request_sha256",
            "decision_sha256",
            "decision_id",
            "authority_sequence",
            "committed_revision",
            "active_epoch",
            "registry_generation_id",
        ],
        "S9 historical projection drift",
    )
    require(
        "pub(super) fn decision_message(" not in s9_source
        and "fn decision_message(decision: &SignedExternalCurrentnessDecisionV1)" in s9_source,
        "raw S9 decision framer became sibling-visible or disappeared",
    )
    require(
        pub_super_struct_fields(s9_source, "ExternalAuthorityTrustPermitV1") == [],
        "S9 owner-pin permit fields became sibling-visible",
    )
    s9_permit_methods, s9_permit_impl = permit_impl_methods(
        s9_source, "ExternalAuthorityTrustPermitV1"
    )
    require(
        s9_permit_methods == ["signer_key_id", "ed25519_public_key", "test_only_new"],
        "S9 permit getter/factory surface drift",
    )
    require(
        "#[cfg(test)]\n    #[allow(clippy::too_many_arguments)]\n    pub(super) fn test_only_new("
        in s9_permit_impl,
        "S9 permit factory is not test-only",
    )
    require(
        "let verified = verify_external_currentness_decision_v1(request, permit, &decision)?;"
        in s9_source,
        "S9 online verifier does not delegate to shared detached verifier",
    )
    s9_test_count = len(re.findall(r"(?m)^    fn s9_[a-z0-9_]+\(\)", s9_source))
    require(s9_test_count == S9_RETAINED_TEST_COUNT, f"S9 retained Rust test count drift: {s9_test_count}")
    require(
        "fn s9_oversized_decision_label_rejects_before_message_allocation()" in s9_source,
        "S9 direct oversized-label regression missing",
    )

    require(
        shared_items(s10_source)
        == [
            "ExternalOperationRecoveryV1Error",
            "RecoveryResult",
            "ExternalOperationRecoveryQueryV1",
            "lookup_query_digest",
            "ExternalOperationRecoveryStateV1",
            "SignedExternalOperationRecoveryObservationV1",
            "observation_message",
            "result_id",
            "ExternalOperationRecoveryTrustPermitV1",
            "VerifiedExternalOperationRecoveryObservationV1",
            "verify_external_operation_recovery_observation_v1",
        ],
        "S10 shared surface drift",
    )
    require(
        struct_fields(s10_source, "VerifiedExternalOperationRecoveryObservationV1")
        == [
            "provider_profile_id",
            "authority_namespace_id",
            "tenant_id",
            "audience",
            "provider_cluster_id",
            "provider_incarnation",
            "trust_policy_sha256",
            "original_operation_id",
            "original_challenge",
            "original_request_sha256",
            "lookup_query_sha256",
            "observation_sha256",
            "original_decision_sha256",
            "result_id",
            "leader_term",
            "operation_committed_revision",
            "observed_journal_revision",
            "journal_generation_id",
            "journal_record_sequence",
        ],
        "S10 verified recovery projection drift",
    )
    require(
        pub_super_struct_fields(s10_source, "ExternalOperationRecoveryTrustPermitV1") == [],
        "S10 owner-pin permit fields became sibling-visible",
    )
    s10_permit_methods, s10_permit_impl = permit_impl_methods(
        s10_source, "ExternalOperationRecoveryTrustPermitV1"
    )
    require(s10_permit_methods == ["test_only_new"], "S10 permit factory surface drift")
    require(
        "#[cfg(test)]\n    #[allow(clippy::too_many_arguments)]\n    pub(super) fn test_only_new("
        in s10_permit_impl,
        "S10 permit factory is not test-only",
    )
    require(
        "verify_external_operation_recovery_observation_v1(query, permit, &observation)"
        in s10_source,
        "S10 online verifier does not delegate to pure observation verifier",
    )

    require(
        shared_items(s11_source)
        == [
            "AtomicAuthorityOperationV1Error",
            "OperationResult",
            "AtomicAuthorityOperationRequestV1",
            "request_digest",
            "AtomicAuthorityOperationPersistentStateV1",
            "AtomicAuthorityOperationTrustPermitV1",
            "prepared_record_digest",
            "sign_job_id",
            "stable_result_id",
            "decision_message",
            "synthetic_l2_record_digest",
            "SignedCommittedAuthorityOperationV1",
            "VerifiedAtomicAuthorityOperationObservationV1",
            "verify_signed_committed_operation_l1_v1",
        ],
        "S11 shared surface drift",
    )
    require(
        struct_fields(s11_source, "VerifiedAtomicAuthorityOperationObservationV1")
        == ["stable_result_id", "decision_message_sha256", "operation_committed_revision", "record_sequence"],
        "S11 L1 projection drift",
    )
    require(
        pub_super_struct_fields(s11_source, "AtomicAuthorityOperationTrustPermitV1") == [],
        "S11 owner-pin permit fields became sibling-visible",
    )
    s11_permit_methods, s11_permit_impl = permit_impl_methods(
        s11_source, "AtomicAuthorityOperationTrustPermitV1"
    )
    require(
        s11_permit_methods == ["signer_key_id", "ed25519_public_key", "test_only_new"],
        "S11 permit getter/factory surface drift",
    )
    require(
        "#[cfg(test)]\n    #[allow(clippy::too_many_arguments)]\n    pub(super) fn test_only_new("
        in s11_permit_impl,
        "S11 permit factory is not test-only",
    )
    require(
        "verify_signed_committed_operation_core_v1(request, permit, record, false)" in s11_source
        and "verify_signed_committed_operation_core_v1(request, permit, record, true)?" in s11_source,
        "S11 L1/full verifiers do not share the exact authenticated core",
    )
    l1_match = re.search(
        r"(?ms)^pub\(super\) fn verify_signed_committed_operation_l1_v1\(.*?^\}",
        s11_source,
    )
    require(l1_match is not None, "S11 L1 verifier missing")
    require(
        "synthetic_l2_revision" not in l1_match.group(0)
        and "synthetic_l2_record_sha256" not in l1_match.group(0),
        "S11 authenticated L1 verifier reads unauthenticated L2 metadata",
    )

    require(rust_u8_array(source, "S9_SEED", 32) == S9_SEED, "Rust S9 seed drift")
    require(rust_u8_array(source, "S10_SEED", 32) == S10_SEED, "Rust S10 seed drift")
    require(rust_u8_array(source, "S11_SEED", 32) == S11_SEED, "Rust S11 seed drift")
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
    require(
        rust_root_u8_array(source, "S11_CONTRACT_SHA256", 32)
        == bytes.fromhex(S11_CONTRACT_SHA256),
        "Rust S11 contract binding drift",
    )

    expected_literals = Counter(
        [
            "9c457bfc43b6dfd010c25f0564ae57e4d0725004eb59f1bea31763b9caa32674",
            "9c457bfc43b6dfd010c25f0564ae57e4d0725004eb59f1bea31763b9caa32674",
            "7de88b53712a7cc3bd068aef5d08023cfe803864a03023bf3ba27707c1849f2a",
            "b657851893471a671c341f7c22c8e1a883fef5e67d3ca48d7e13794cde76f34e",
            "b31cc3f4041e0fdd9c2e55269a0133f6d5e660a6228166976f7244d3c4a908af",
            str(vectors["s9_decision_id"]),
            str(vectors["s9_request_sha256"]),
            str(vectors["s9_decision_message_sha256"]),
            str(vectors["s9_ed25519_signature"]),
            str(vectors["s10_lookup_query_sha256"]),
            str(vectors["s10_observation_sha256"]),
            str(vectors["s10_result_id"]),
            str(vectors["authority_snapshot_sha256"]),
            str(vectors["s11_request_sha256"]),
            str(vectors["s11_prepared_record_sha256"]),
            str(vectors["s11_sign_job_id"]),
            str(vectors["s11_stable_result_id"]),
            str(vectors["s11_decision_message_sha256"]),
            str(vectors["s11_ed25519_signature"]),
            str(vectors["s11_synthetic_l2_record_sha256_at_revision_52"]),
            str(vectors["historical_chain_sha256"]),
            str(vectors["s11_synthetic_l2_record_sha256_at_revision_99"]),
        ]
    )
    actual_literals = Counter(re.findall(r'"([0-9a-f]{64}|[0-9a-f]{128})"', source))
    require(actual_literals == expected_literals, "Rust hardcoded independent vectors drift")

    test_count = len(re.findall(r"(?m)^    fn s12_[a-z0-9_]+\(\)", source))
    require(test_count == S12_TEST_COUNT, f"S12 Rust test count drift: {test_count}")
    require("#[ignore" not in tests and "#[should_panic" not in tests, "S12 tests were weakened")
    return test_count


def receipt(test_count: int, vectors: dict[str, str | int]) -> str:
    rows = [
        ("schema", "agent_bridge.memory_temporal_recovered_s9_decision_reverification_s12_receipt.v0"),
        ("status", STATUS),
        ("decision", DECISION),
        ("base_commit", BASE_COMMIT),
        ("s11_feature_commit", S11_FEATURE_COMMIT),
        ("s9_contract_sha256", S9_CONTRACT_SHA256),
        ("s10_contract_sha256", S10_CONTRACT_SHA256),
        ("s11_contract_sha256", S11_CONTRACT_SHA256),
        ("s11_successor_gate_sha256", S11_GATE_SHA256),
        ("s9_checker_sha256", S9_CHECKER_SHA256),
        ("s10_checker_sha256", S10_CHECKER_SHA256),
        ("s11_checker_sha256", S11_CHECKER_SHA256),
        ("s12_contract_sha256", CONTRACT_SHA256),
        ("s12_successor_gate_sha256", GATE_SHA256),
        ("s12_source_sha256", SOURCE_SHA256),
        ("s12_store_cargo_sha256", STORE_CARGO_SHA256),
        ("s12_parent_module_sha256", PARENT_MODULE_SHA256),
        ("s12_s9_glue_sha256", S9_SOURCE_SHA256),
        ("s12_s10_glue_sha256", S10_SOURCE_SHA256),
        ("s12_s11_glue_sha256", S11_SOURCE_SHA256),
        ("glue_validation_scope", "FROZEN_S12_TREE_PRIVATE_SYNTHETIC_THREE_LINK_HISTORICAL_ONLY"),
        ("feature", FEATURE),
        ("depends_on_feature", S11_FEATURE),
        ("feature_default_enabled", "false"),
        ("policy", POLICY.decode()),
        ("profile", PROFILE.decode()),
        ("authority_snapshot_domain", AUTHORITY_SNAPSHOT_DOMAIN.decode()),
        ("historical_chain_domain", HISTORICAL_CHAIN_DOMAIN.decode()),
        ("max_canonical_message_bytes", str(MAX_CANONICAL_MESSAGE_BYTES)),
        ("known_s9_public_key", vectors["s9_ed25519_public_key"]),
        ("known_s9_request_sha256", vectors["s9_request_sha256"]),
        ("known_s9_decision_message_sha256", vectors["s9_decision_message_sha256"]),
        ("known_s9_decision_id", vectors["s9_decision_id"]),
        ("known_s9_signature", vectors["s9_ed25519_signature"]),
        ("known_s10_projection_public_key", vectors["s10_ed25519_public_key"]),
        ("known_s10_lookup_query_sha256", vectors["s10_lookup_query_sha256"]),
        ("known_s10_observation_sha256", vectors["s10_observation_sha256"]),
        ("known_s10_result_id", vectors["s10_result_id"]),
        ("known_s10_projection_signature", vectors["s10_ed25519_signature"]),
        ("known_authority_snapshot_sha256", vectors["authority_snapshot_sha256"]),
        ("known_s11_public_key", vectors["s11_ed25519_public_key"]),
        ("known_s11_request_sha256", vectors["s11_request_sha256"]),
        ("known_s11_prepared_record_sha256", vectors["s11_prepared_record_sha256"]),
        ("known_s11_sign_job_id", vectors["s11_sign_job_id"]),
        ("known_s11_stable_result_id", vectors["s11_stable_result_id"]),
        ("known_s11_decision_message_sha256", vectors["s11_decision_message_sha256"]),
        ("known_s11_signature", vectors["s11_ed25519_signature"]),
        ("known_s11_l2_revision_52_checksum", vectors["s11_synthetic_l2_record_sha256_at_revision_52"]),
        ("known_s11_l2_revision_99_checksum", vectors["s11_synthetic_l2_record_sha256_at_revision_99"]),
        ("known_historical_chain_sha256", vectors["historical_chain_sha256"]),
        ("s12_nonignored_rust_tests", str(test_count)),
        ("dual_signature_keys_distinct", "true"),
        ("canonical_raw_s9_bytes_required", "true"),
        ("verified_s10_projection_required", "true"),
        ("s10_raw_signature_reverified_in_s12", "false"),
        ("s9_shared_detached_verifier", "true"),
        ("s11_shared_l1_only_verifier", "true"),
        ("s11_l2_metadata_in_historical_chain", "false"),
        ("provider_call_present", "false"),
        ("network_clock_cache_or_retry_present", "false"),
        ("serde_or_wire_schema_present", "false"),
        ("production_constructor_present", "false"),
        ("state_store_surface_present", "false"),
        ("bridge_runtime_caller_present", "false"),
        ("historical_observation_is_currentness", "false"),
        ("historical_observation_is_admission", "false"),
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
        check_predecessors(repo)
        vectors = independent_vectors(repo)
        check_contract(repo, vectors)
        check_gate(repo)
        test_count = check_source(repo, vectors)
    except (CheckFailure, KeyError, TypeError, ValueError, OSError, tomllib.TOMLDecodeError) as exc:
        print(f"S12_CHECK_FAILED\t{exc}", file=sys.stderr)
        return 1
    sys.stdout.write(receipt(test_count, vectors))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
