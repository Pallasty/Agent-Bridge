#!/usr/bin/env python3
"""Fail-closed checker for the S9 external-authority provider contract."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import tomllib
from pathlib import Path
from typing import Any


STATUS = (
    "PROVIDER_NEUTRAL_ED25519_CURRENTNESS_AND_CUSTODY_CONTRACT_PREREGISTERED_"
    "NO_PROVIDER_NO_OWNER_TRUST_ANCHOR_NOT_AUTHORIZED_NOT_TRANSPORT"
)
DECISION = "BLOCKED_FAIL_CLOSED"
FEATURE = "temporal-evidence-s9-external-authority-provider-synthetic"
S8_FEATURE = "temporal-evidence-s8-restore-bound-key-epoch-synthetic"
BASE_COMMIT = "ad3500c831228b1f0e7e1ff2330c515aa997fa7b"
S8_FEATURE_COMMIT = "1b303902a91e841bb52bd2fe4807e84320bbb852"

S8_CONTRACT_PATH = (
    "docs/design/fixtures/biocortex-ab-track-b-controlled-restore-key-epoch-s8-v0.json"
)
S8_GATE_PATH = (
    "docs/design/fixtures/biocortex-ab-track-b-successor-admission-gate-s8-v0.json"
)
S8_SOURCE_PATH = "crates/store/src/temporal_replay_transport/restore_bound_key_epoch.rs"
S8_CONTRACT_SHA256 = "039ec8237afa9b2ea3340918a2924f78f89223abbd4034d41c6d82a2e1519573"
S8_GATE_SHA256 = "c01e686d104392269d57c39a9a240b203016639c65f379f992e74d30248c5817"
S8_SOURCE_SHA256 = "a252459ec21df5f2c4ecb251e61433017d5a2a44e9f14b1b886452da485f43b4"

CONTRACT_PATH = (
    "docs/design/fixtures/biocortex-ab-track-b-external-authority-provider-s9-v0.json"
)
GATE_PATH = "docs/design/fixtures/biocortex-ab-track-b-successor-admission-gate-s9-v0.json"
SOURCE_PATH = "crates/store/src/temporal_replay_transport/external_restore_authority.rs"
CONTRACT_SHA256 = "d537b80ce0d2bbb3c4d01a988a9685432672078eae07d0b976b1268a27526fc4"
GATE_SHA256 = "2181254b1e66444445734edb2f7dab70a85c0be5316d449f7152559d7e6428e5"
SOURCE_SHA256 = "dd92c2b064c1a4c1e5a4119777f1b5bf21a46d0fc9cb77656845f05e48655d9b"

POLICY = b"agent-bridge/track-b/external-authority-provider/v1"
REQUEST_DOMAIN = b"agent-bridge/track-b/external-authority-provider/currentness-request/v1"
DECISION_DOMAIN = b"agent-bridge/track-b/external-authority-provider/currentness-decision/v1"
KEY_REF_DOMAIN = b"agent-bridge/track-b/external-authority-provider/opaque-key-ref/v1"
KEYSET_DOMAIN = b"agent-bridge/track-b/external-authority-provider/opaque-keyset/v1"
REVOCATION_DOMAIN = (
    b"agent-bridge/track-b/external-authority-provider/revocation-checkpoint/v1"
)
CUSTODY_DOMAIN = b"agent-bridge/track-b/external-authority-provider/custody-claim/v1"
USE_DENIED_DOMAIN = b"agent-bridge/track-b/external-authority-provider/use-denied-claim/v1"
DECISION_ID_DOMAIN = b"agent-bridge/track-b/external-authority-provider/decision-id/v1"
ALGORITHM = b"Ed25519"
LEASE = b"ONE_ATTEMPT_NO_CACHE_NO_WALL_CLOCK"

RFC8032_SEED = bytes.fromhex(
    "9d61b19deffd5a60ba844af492ec2cc44449c5697b326919703bac031cae7f60"
)
RFC8032_PUBLIC_KEY = bytes.fromhex(
    "d75a980182b10ab7d54bfed3c964073a0ee172f3daa62325af021a68f707511a"
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
        if key in output:
            raise CheckFailure(f"duplicate JSON key: {key}")
        output[key] = value
    return output


def load_json(repo: Path, relative: str) -> dict[str, Any]:
    try:
        value = json.loads(read_text(repo, relative), object_pairs_hook=reject_duplicates)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CheckFailure(f"invalid JSON {relative}: {exc}") from exc
    require(isinstance(value, dict), f"top-level JSON object required: {relative}")
    return value


def frame(value: bytes) -> bytes:
    return len(value).to_bytes(8, "big") + value


def framed_message(domain: bytes, fields: list[bytes]) -> bytes:
    return frame(domain) + b"".join(frame(field) for field in fields)


def framed_digest(domain: bytes, fields: list[bytes]) -> bytes:
    return hashlib.sha256(framed_message(domain, fields)).digest()


# Minimal, dependency-free RFC 8032 reference arithmetic. This deliberately
# does not share implementation code with ring, which produces the Rust vector.
ED25519_Q = 2**255 - 19
ED25519_L = 2**252 + 27742317777372353535851937790883648493
ED25519_D = (-121665 * pow(121666, ED25519_Q - 2, ED25519_Q)) % ED25519_Q
ED25519_I = pow(2, (ED25519_Q - 1) // 4, ED25519_Q)


def ed25519_xrecover(y: int) -> int:
    xx = (y * y - 1) * pow(ED25519_D * y * y + 1, ED25519_Q - 2, ED25519_Q)
    x = pow(xx % ED25519_Q, (ED25519_Q + 3) // 8, ED25519_Q)
    if (x * x - xx) % ED25519_Q != 0:
        x = (x * ED25519_I) % ED25519_Q
    require((x * x - xx) % ED25519_Q == 0, "invalid Ed25519 square root")
    return ED25519_Q - x if x & 1 else x


ED25519_BY = (4 * pow(5, ED25519_Q - 2, ED25519_Q)) % ED25519_Q
ED25519_B = (ed25519_xrecover(ED25519_BY), ED25519_BY)
ED25519_IDENTITY = (0, 1)


def ed25519_add(left: tuple[int, int], right: tuple[int, int]) -> tuple[int, int]:
    x1, y1 = left
    x2, y2 = right
    product = (ED25519_D * x1 * x2 * y1 * y2) % ED25519_Q
    x3 = (x1 * y2 + x2 * y1) * pow(1 + product, ED25519_Q - 2, ED25519_Q)
    y3 = (y1 * y2 + x1 * x2) * pow(1 - product, ED25519_Q - 2, ED25519_Q)
    return x3 % ED25519_Q, y3 % ED25519_Q


def ed25519_scalar_mult(point: tuple[int, int], scalar: int) -> tuple[int, int]:
    result = ED25519_IDENTITY
    addend = point
    while scalar:
        if scalar & 1:
            result = ed25519_add(result, addend)
        addend = ed25519_add(addend, addend)
        scalar >>= 1
    return result


def ed25519_encode(point: tuple[int, int]) -> bytes:
    x, y = point
    encoded = y | ((x & 1) << 255)
    return encoded.to_bytes(32, "little")


def ed25519_decode(encoded: bytes) -> tuple[int, int]:
    require(len(encoded) == 32, "Ed25519 point length drift")
    integer = int.from_bytes(encoded, "little")
    sign = integer >> 255
    y = integer & ((1 << 255) - 1)
    require(y < ED25519_Q, "noncanonical Ed25519 point")
    x = ed25519_xrecover(y)
    if (x & 1) != sign:
        x = ED25519_Q - x
    require(not (x == 0 and sign == 1), "noncanonical Ed25519 sign bit")
    require(
        (-x * x + y * y - 1 - ED25519_D * x * x * y * y) % ED25519_Q == 0,
        "Ed25519 point is not on curve",
    )
    return x, y


def ed25519_secret_scalar(seed: bytes) -> tuple[int, bytes]:
    require(len(seed) == 32, "Ed25519 seed length drift")
    digest = hashlib.sha512(seed).digest()
    scalar = int.from_bytes(digest[:32], "little")
    scalar &= (1 << 254) - 8
    scalar |= 1 << 254
    return scalar, digest[32:]


def ed25519_public_key(seed: bytes) -> bytes:
    scalar, _ = ed25519_secret_scalar(seed)
    return ed25519_encode(ed25519_scalar_mult(ED25519_B, scalar))


def ed25519_sign(seed: bytes, message: bytes) -> bytes:
    scalar, prefix = ed25519_secret_scalar(seed)
    public_key = ed25519_public_key(seed)
    nonce = int.from_bytes(hashlib.sha512(prefix + message).digest(), "little") % ED25519_L
    encoded_r = ed25519_encode(ed25519_scalar_mult(ED25519_B, nonce))
    challenge = int.from_bytes(
        hashlib.sha512(encoded_r + public_key + message).digest(), "little"
    ) % ED25519_L
    encoded_s = ((nonce + challenge * scalar) % ED25519_L).to_bytes(32, "little")
    return encoded_r + encoded_s


def ed25519_verify(public_key: bytes, message: bytes, signature: bytes) -> bool:
    if len(public_key) != 32 or len(signature) != 64:
        return False
    try:
        point_a = ed25519_decode(public_key)
        point_r = ed25519_decode(signature[:32])
    except CheckFailure:
        return False
    scalar_s = int.from_bytes(signature[32:], "little")
    if scalar_s >= ED25519_L:
        return False
    challenge = int.from_bytes(
        hashlib.sha512(signature[:32] + public_key + message).digest(), "little"
    ) % ED25519_L
    return ed25519_scalar_mult(ED25519_B, scalar_s) == ed25519_add(
        point_r, ed25519_scalar_mult(point_a, challenge)
    )


def opaque_key_ref(
    provider_profile_id: bytes,
    authority_namespace_id: bytes,
    provider_cluster_id: bytes,
    provider_incarnation: bytes,
    key_id: bytes,
    key_version: int,
    role: bytes,
) -> bytes:
    return framed_digest(
        KEY_REF_DOMAIN,
        [
            POLICY,
            provider_profile_id,
            authority_namespace_id,
            provider_cluster_id,
            provider_incarnation,
            key_id,
            key_version.to_bytes(8, "big"),
            role,
            b"hmac-sha-256",
        ],
    )


def independent_vectors() -> dict[str, str | bytes]:
    provider_profile_id = b"owner-selected-provider-v1"
    authority_namespace_id = b"agent-bridge-research-prod"
    provider_cluster_id = b"authority-cluster-a"
    provider_incarnation = bytes([0x61]) * 32
    handle = opaque_key_ref(
        provider_profile_id,
        authority_namespace_id,
        provider_cluster_id,
        provider_incarnation,
        b"handle-key",
        11,
        b"HANDLE",
    )
    inner = opaque_key_ref(
        provider_profile_id,
        authority_namespace_id,
        provider_cluster_id,
        provider_incarnation,
        b"inner-key",
        12,
        b"INNER_TRANSPORT",
    )
    outer = opaque_key_ref(
        provider_profile_id,
        authority_namespace_id,
        provider_cluster_id,
        provider_incarnation,
        b"outer-key",
        13,
        b"OUTER_CHANNEL",
    )
    keyset = framed_digest(KEYSET_DOMAIN, [POLICY, handle, inner, outer])

    operation_id = bytes([0x21]) * 32
    challenge = bytes([0x31]) * 32
    epoch = (2).to_bytes(8, "big")
    epoch_record = bytes([0x41]) * 32
    generation = bytes([0x42]) * 32
    request_message = framed_message(
        REQUEST_DOMAIN,
        [
            POLICY,
            ALGORITHM,
            LEASE,
            provider_profile_id,
            authority_namespace_id,
            b"agent-bridge",
            b"ab-store-restore-admission",
            operation_id,
            challenge,
            epoch,
            epoch_record,
            generation,
            bytes([0x43]) * 32,
            bytes([0x44]) * 32,
            bytes([0x45]) * 32,
            keyset,
            bytes([0x71]) * 32,
        ],
    )
    request_sha256 = hashlib.sha256(request_message).digest()
    revision = (42).to_bytes(8, "big")
    revocation_checkpoint = framed_digest(REVOCATION_DOMAIN, [request_sha256, revision])
    custody_receipt = framed_digest(CUSTODY_DOMAIN, [keyset, epoch, revision])
    old_key_use_denied = framed_digest(USE_DENIED_DOMAIN, [epoch_record, epoch, revision])
    decision_id = framed_digest(DECISION_ID_DOMAIN, [operation_id, challenge, revision])
    decision_message = framed_message(
        DECISION_DOMAIN,
        [
            POLICY,
            ALGORITHM,
            LEASE,
            request_sha256,
            b"ACTIVE",
            provider_cluster_id,
            provider_incarnation,
            (7).to_bytes(8, "big"),
            revision,
            (1).to_bytes(8, "big"),
            epoch,
            epoch_record,
            generation,
            keyset,
            revocation_checkpoint,
            (1).to_bytes(8, "big"),
            custody_receipt,
            old_key_use_denied,
            decision_id,
            b"currentness-signer-a",
            (3).to_bytes(8, "big"),
        ],
    )
    public_key = ed25519_public_key(RFC8032_SEED)
    signature = ed25519_sign(RFC8032_SEED, decision_message)
    require(public_key == RFC8032_PUBLIC_KEY, "RFC8032 public-key reference mismatch")
    require(ed25519_verify(public_key, decision_message, signature), "Ed25519 vector does not verify")
    tampered = bytearray(signature)
    tampered[0] ^= 1
    require(
        not ed25519_verify(public_key, decision_message, bytes(tampered)),
        "Ed25519 reference accepted a tampered signature",
    )
    return {
        "public_key": public_key.hex(),
        "request_sha256": request_sha256.hex(),
        "decision_message_sha256": hashlib.sha256(decision_message).hexdigest(),
        "signature": signature.hex(),
        "request_message": request_message,
        "decision_message": decision_message,
    }


def check_predecessor(repo: Path) -> None:
    require(sha256(repo, S8_CONTRACT_PATH) == S8_CONTRACT_SHA256, "S8 contract digest drift")
    require(sha256(repo, S8_GATE_PATH) == S8_GATE_SHA256, "S8 successor gate digest drift")
    require(sha256(repo, S8_SOURCE_PATH) == S8_SOURCE_SHA256, "S8 Rust source digest drift")


def check_contracts(
    repo: Path, vectors: dict[str, str | bytes]
) -> tuple[dict[str, Any], dict[str, Any]]:
    require(sha256(repo, CONTRACT_PATH) == CONTRACT_SHA256, "S9 contract digest drift")
    require(sha256(repo, GATE_PATH) == GATE_SHA256, "S9 successor gate digest drift")
    contract = load_json(repo, CONTRACT_PATH)
    gate = load_json(repo, GATE_PATH)

    require(
        set(contract)
        == {
            "boundary",
            "contract_binding",
            "currentness_profile",
            "decision",
            "dependency",
            "failure_semantics",
            "implementation",
            "interfaces",
            "known_vector",
            "negative_evidence",
            "operational_gap_codes",
            "provider_identity",
            "remaining_gap_codes",
            "schema",
            "signed_response",
            "status",
            "test_matrix",
        },
        "S9 contract top-level shape drift",
    )
    require(
        contract["schema"]
        == "agent_bridge.memory_temporal_external_authority_provider_contract_s9.v0",
        "S9 contract schema drift",
    )
    require(contract["status"] == STATUS and contract["decision"] == DECISION, "S9 outcome drift")
    require(
        contract["dependency"]
        == {
            "default_enabled": False,
            "depends_on_feature": S8_FEATURE,
            "feature": FEATURE,
        },
        "S9 feature declaration drift",
    )
    require(
        all(value is False for value in contract["boundary"].values()),
        "S9 boundary silently opened",
    )
    require(
        all(value is True for value in contract["contract_binding"].values()),
        "S9 exact binding requirement weakened",
    )
    require(
        contract["currentness_profile"]
        == {
            "attempts_per_admission": 1,
            "cache_allowed": False,
            "challenge_durable_uniqueness_attested": False,
            "challenge_durable_uniqueness_required_of_production_provider": True,
            "lease": "ONE_ATTEMPT_NO_CACHE_NO_WALL_CLOCK",
            "local_s8_fallback_allowed": False,
            "response_reusable_across_attempts": False,
            "retry_with_same_challenge_allowed": False,
            "wall_clock_used": False,
        },
        "S9 one-attempt/no-cache profile drift",
    )
    require(
        all(value is False for value in contract["failure_semantics"].values()),
        "S9 failure path can return a token",
    )
    require(
        contract["interfaces"]
        == {
            "currentness": {
                "interface": "ExternalCurrentnessProvider",
                "module_visibility": "private",
                "network_adapter": False,
                "production_implementation": False,
                "test_only_deterministic_implementation": True,
            },
            "key_custody": {
                "interface": "ExternalKeyCustodian",
                "key_reference_mutable": False,
                "key_reference_profile": "OPAQUE_IMMUTABLE_PROVIDER_SCOPED_REFERENCE",
                "module_visibility": "private",
                "production_implementation": False,
                "raw_key_accepted": False,
                "raw_key_returned": False,
                "test_only_deterministic_implementation": False,
            },
        },
        "S9 sealed-interface contract drift",
    )
    require(
        contract["implementation"]
        == {
            "currentness_permit_constructor_scope": "cfg_test_only",
            "currentness_response_verification": "exact_framed_ed25519",
            "independent_custodian_authentication_verified": False,
            "key_custody_verification_status": (
                "INTERFACE_AND_OPAQUE_IDENTITY_ONLY_NOT_PRODUCTION_ATTESTATION"
            ),
            "module_path": SOURCE_PATH,
            "module_visibility": "private_child_of_private_s6_module",
            "network_or_transport": False,
            "s8_verifier_integration": False,
            "state_store_integration": False,
        },
        "S9 implementation boundary drift",
    )
    expected_vector = {
        "authority_sequence": 1,
        "committed_revision": 42,
        "decision_message_sha256": vectors["decision_message_sha256"],
        "ed25519_public_key": vectors["public_key"],
        "ed25519_seed_profile": "RFC8032_TEST_VECTOR_1_SEED_TEST_ONLY",
        "ed25519_signature": vectors["signature"],
        "expected_epoch": 2,
        "request_sha256": vectors["request_sha256"],
    }
    require(contract["known_vector"] == expected_vector, "S9 independent known vector drift")
    require(len(contract["test_matrix"]) == 14, "S9 test-matrix cardinality drift")
    require(all(contract["test_matrix"].values()), "S9 test matrix contains an unclaimed case")
    negative = contract["negative_evidence"]
    require(
        set(key for key, value in negative.items() if value is True)
        == {
            "challenge_reuse_after_synthetic_provider_reconstruction_demonstrated",
            "revocation_after_verified_snapshot_cannot_recall_token_demonstrated",
        },
        "S9 negative-evidence demonstrations drift",
    )
    require(
        all(value is False for value in negative.values() if value is not True),
        "S9 unresolved property silently closed",
    )
    require(
        contract["provider_identity"]
        == {
            "algorithm": "Ed25519",
            "in_band_self_asserted_public_key_accepted": False,
            "owner_pin_external_to_response_required": True,
            "owner_pinned_public_key_present": False,
            "public_key_bytes": 32,
            "rotation_authorized_in_band": False,
            "rotation_requires_new_out_of_band_owner_pin": True,
            "signature_bytes": 64,
            "synthetic_test_pin_is_owner_attestation": False,
        },
        "S9 provider-identity pinning drift",
    )
    require(
        contract["signed_response"]
        == {
            "currentness_provider_custody_claim_is_kms_proof": False,
            "exact_framed_bytes_verified": True,
            "currentness_provider_old_key_use_denied_claim_is_destruction_proof": False,
            "independent_custodian_receipt_verified": False,
            "provider_status_must_be_current": True,
            "signature_algorithm": "Ed25519",
            "unknown_or_non_current_status_accepted": False,
        },
        "S9 signed-response semantics drift",
    )
    require(contract["remaining_gap_codes"] == list(REMAINING_GAPS), "remaining gaps drift")
    require(contract["operational_gap_codes"] == list(OPERATIONAL_GAPS), "operational gaps drift")

    require(
        set(gate)
        == {
            "admission",
            "authorization_semantics",
            "boundary",
            "decision",
            "external_authority_preregistration",
            "operational_gap_codes",
            "predecessor",
            "remaining_gap_codes",
            "required_successor_identity",
            "schema",
            "status",
        },
        "S9 successor gate top-level shape drift",
    )
    require(
        gate["schema"] == "agent_bridge.memory_temporal_successor_admission_gate_s9.v0",
        "S9 successor schema drift",
    )
    require(gate["status"] == "NOT_ADMITTED" and gate["decision"] == DECISION, "gate opened")
    admission = gate["admission"]
    require(admission["admitted"] is False, "successor payload silently admitted")
    require(
        admission["admission_artifact_must_be_external_to_packet"] is True,
        "external admission-artifact requirement weakened",
    )
    require(
        all(
            value is None
            for key, value in admission.items()
            if key not in {"admitted", "admission_artifact_must_be_external_to_packet"}
        ),
        "invented S9 admission receipt",
    )
    require(
        all(value is True for value in gate["authorization_semantics"].values()),
        "S9 non-authorization semantics weakened",
    )
    require(
        all(
            value is False
            for key, value in gate["boundary"].items()
            if key != "side_effects_unlocked"
        ),
        "S9 successor boundary silently opened",
    )
    require(gate["boundary"]["side_effects_unlocked"] == "NONE", "side effects unlocked")
    registration = gate["external_authority_preregistration"]
    require(registration["contract_sha256"] == CONTRACT_SHA256, "gate does not bind S9 contract")
    require(registration["contract_status"] == STATUS, "gate S9 status binding drift")
    require(registration["currentness_profile"] == LEASE.decode(), "gate lease profile drift")
    require(registration["external_currentness_provider_interface_frozen"] is True, "currentness interface not frozen")
    require(registration["external_key_custodian_interface_frozen"] is True, "custodian interface not frozen")
    require(registration["opaque_immutable_key_references_only"] is True, "raw key reference admitted")
    require(registration["production_provider_present"] is False, "production provider invented")
    require(registration["raw_key_returned"] is False, "raw key return admitted")
    require(registration["synthetic_provider_is_production_evidence"] is False, "synthetic evidence elevated")
    require(
        gate["predecessor"]
        == {
            "base_commit": BASE_COMMIT,
            "s8_contract_sha256": S8_CONTRACT_SHA256,
            "s8_feature_commit": S8_FEATURE_COMMIT,
            "s8_successor_gate_sha256": S8_GATE_SHA256,
        },
        "S9 predecessor binding drift",
    )
    successor = gate["required_successor_identity"]
    require(
        all(value is True for key, value in successor.items() if key.endswith("_required") or key == "candidate_id_must_change"),
        "successor identity requirement weakened",
    )
    require(
        all(value is None for key, value in successor.items() if not (key.endswith("_required") or key == "candidate_id_must_change")),
        "successor identity was silently populated",
    )
    require(gate["remaining_gap_codes"] == list(REMAINING_GAPS), "gate remaining gaps drift")
    require(gate["operational_gap_codes"] == list(OPERATIONAL_GAPS), "gate operational gaps drift")
    return contract, gate


def strip_rust_comments(source: str) -> str:
    without_blocks = re.sub(r"/\*.*?\*/", "", source, flags=re.DOTALL)
    return re.sub(r"//[^\n]*", "", without_blocks)


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


def check_source(repo: Path, vectors: dict[str, str | bytes]) -> int:
    require(sha256(repo, SOURCE_PATH) == SOURCE_SHA256, "S9 Rust source digest drift")
    cargo = tomllib.loads(read_text(repo, "crates/store/Cargo.toml"))
    features = cargo.get("features", {})
    require(features.get(FEATURE) == [S8_FEATURE], "S9 feature dependency drift")
    require(FEATURE not in features.get("default", []), "S9 feature became default")

    parent = read_text(repo, "crates/store/src/temporal_replay_transport.rs")
    library = read_text(repo, "crates/store/src/lib.rs")
    bridge = bridge_surface_text(repo)
    source = read_text(repo, SOURCE_PATH)
    require(
        f'#[cfg(feature = "{FEATURE}")]\nmod external_restore_authority;' in parent,
        "private S9 module gate missing",
    )
    require("pub mod external_restore_authority" not in parent, "S9 module became public")
    require("pub use external_restore_authority" not in parent + library, "S9 re-export forbidden")
    require(
        FEATURE not in library + bridge and "external_restore_authority" not in library + bridge,
        "S9 leaked to library or Bridge surface",
    )

    split = source.split("#[cfg(test)]\nmod tests", 1)
    require(len(split) == 2, "S9 synthetic implementation is not cfg(test)-isolated")
    production, tests = split
    code = strip_rust_comments(production)
    require("StateStore" not in code, "S9 entered StateStore")
    for forbidden in (
        "std::net",
        "tokio::net",
        "reqwest::",
        "hyper::",
        "tonic::",
        "TcpStream",
        "UdpSocket",
        "UnixStream",
        "SocketAddr",
    ):
        require(forbidden not in code, f"S9 implemented network I/O: {forbidden}")
    require(
        all(clock not in code for clock in ("SystemTime", "Instant::now", "std::time")),
        "wall clock entered S9 currentness",
    )
    require("impl ExternalAuthorityTrustPermitV1" not in production, "production permit constructor added")
    require(
        "impl currentness_provider_seal::Sealed" not in production
        and "impl key_custodian_seal::Sealed" not in production,
        "production provider/custodian implementation added",
    )
    require("fn permit_for(" in tests, "test-only owner-pin constructor missing")
    require("struct SyntheticConformingExternalProviderV1" in tests, "synthetic provider missing")
    require("struct SyntheticOpaqueKeyCustodianV1" not in tests, "synthetic custodian was elevated")
    require(
        "struct ExternalKeyStateObservationV1" in production
        and "Untrusted provider observation shape" in production,
        "untrusted key-custody observation boundary missing",
    )

    require(source.count("pub(super) trait Sealed {}") == 2, "sealed-interface count drift")
    require(source.count("mod currentness_provider_seal") == 1, "currentness seal drift")
    require(source.count("mod key_custodian_seal") == 1, "custodian seal drift")
    require(
        "trait ExternalCurrentnessProviderV1: currentness_provider_seal::Sealed" in source,
        "currentness interface is not sealed",
    )
    require(
        "trait ExternalKeyCustodianV1: key_custodian_seal::Sealed" in source,
        "custodian interface is not sealed",
    )
    require("pub trait ExternalCurrentnessProviderV1" not in source, "currentness interface became public")
    require("pub trait ExternalKeyCustodianV1" not in source, "custodian interface became public")

    require(
        struct_fields(source, "OpaqueKeyVersionRefV1")
        == [
            "provider_profile_id",
            "authority_namespace_id",
            "provider_cluster_id",
            "provider_incarnation",
            "key_id",
            "key_version",
            "role",
            "algorithm",
            "identity_sha256",
        ],
        "opaque key-reference field shape drift",
    )
    require(
        struct_fields(source, "ExternalKeysetIdentityV1")
        == ["handle", "inner_transport", "outer_channel", "identity_sha256"],
        "opaque keyset field shape drift",
    )
    opaque_body = re.search(
        r"(?ms)^struct OpaqueKeyVersionRefV1 \{\n(?P<body>.*?)^\}", source
    )
    require(opaque_body is not None, "opaque key-reference body missing")
    require(
        not re.search(r"(?i)\b(raw|secret|private|material|key_bytes)\w*\s*:", opaque_body.group("body")),
        "raw/secret key field entered opaque reference",
    )
    require("ONE_ATTEMPT_NO_CACHE_NO_WALL_CLOCK" in production, "S9 lease constant drift")
    require("#[must_use]\nstruct VerifiedExternalCurrentnessV1" in source, "private token shape drift")
    require("pub(crate)" not in source and "pub fn" not in source, "S9 capability became crate-public")
    require("serde::" not in source and "Serialize" not in source, "S9 token became serializable")

    test_count = len(re.findall(r"(?m)^    fn s9_[a-z0-9_]+\(\)", source))
    require(test_count == 14, f"S9 Rust test count drift: {test_count}")
    require(
        "UNRESOLVED: in-memory challenge history is lost on provider reconstruction" in source,
        "challenge-reconstruction negative evidence missing",
    )
    require(
        "UNRESOLVED: a later REVOKED response cannot recall an already returned token."
        in source,
        "currentness-to-consume negative evidence missing",
    )
    require(source.count("UNRESOLVED:") == 2, "S9 UNRESOLVED evidence count drift")

    require(rust_u8_array(source, "RFC8032_SEED", 32) == RFC8032_SEED, "Rust seed vector drift")
    require(
        rust_u8_array(source, "RFC8032_PUBLIC_KEY", 32) == bytes.fromhex(str(vectors["public_key"])),
        "Rust public-key vector drift",
    )
    hardcoded_hex = re.findall(r'"([0-9a-f]{64}|[0-9a-f]{128})"', source)
    require(
        hardcoded_hex
        == [
            str(vectors["request_sha256"]),
            str(vectors["decision_message_sha256"]),
            str(vectors["signature"]),
        ],
        "Rust hardcoded request/decision/signature vectors drift",
    )
    return test_count


def receipt(test_count: int, vectors: dict[str, str | bytes]) -> str:
    rows = [
        ("schema", "agent_bridge.memory_temporal_external_authority_provider_s9_receipt.v0"),
        ("status", STATUS),
        ("decision", DECISION),
        ("base_commit", BASE_COMMIT),
        ("s8_feature_commit", S8_FEATURE_COMMIT),
        ("s8_contract_sha256", S8_CONTRACT_SHA256),
        ("s8_successor_gate_sha256", S8_GATE_SHA256),
        ("s8_source_sha256", S8_SOURCE_SHA256),
        ("s9_contract_sha256", CONTRACT_SHA256),
        ("s9_successor_gate_sha256", GATE_SHA256),
        ("s9_source_sha256", SOURCE_SHA256),
        ("feature", FEATURE),
        ("depends_on_feature", S8_FEATURE),
        ("feature_default_enabled", "false"),
        ("ed25519_public_key", str(vectors["public_key"])),
        ("known_request_sha256", str(vectors["request_sha256"])),
        ("known_decision_message_sha256", str(vectors["decision_message_sha256"])),
        ("known_ed25519_signature", str(vectors["signature"])),
        ("s9_nonignored_rust_tests", str(test_count)),
        ("currentness_provider_interface", "SEALED_PRIVATE"),
        ("key_custodian_interface", "SEALED_PRIVATE"),
        ("key_reference_profile", "OPAQUE_IMMUTABLE_PROVIDER_SCOPED_REFERENCE"),
        ("lease", LEASE.decode()),
        ("production_provider_present", "false"),
        ("production_constructor_present", "false"),
        ("owner_pinned_public_key_present", "false"),
        ("network_client_present", "false"),
        ("state_store_surface_present", "false"),
        ("durable_challenge_uniqueness_attested", "false"),
        ("challenge_reconstruction_negative_evidence", "true"),
        ("post_snapshot_token_recall_negative_evidence", "true"),
        ("external_key_custody_attested", "false"),
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
    parser.add_argument("--repo", required=True, type=Path)
    args = parser.parse_args()
    repo = args.repo.resolve()
    try:
        vectors = independent_vectors()
        check_predecessor(repo)
        check_contracts(repo, vectors)
        test_count = check_source(repo, vectors)
    except (CheckFailure, OSError, KeyError, TypeError, ValueError, tomllib.TOMLDecodeError) as exc:
        print(f"S9_CHECK_FAILED\t{exc}", file=sys.stderr)
        return 1
    sys.stdout.write(receipt(test_count, vectors))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
