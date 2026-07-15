#!/usr/bin/env python3
"""Fail-closed checker for the private S14 recovered-envelope source.

The checker independently rebuilds the exact E9, E10, capture-provenance,
outer-record, and historical-source-chain known answers.  It also freezes the
private/default-off Rust boundary and the negative authorization claims.  The
receipt is synthetic historical evidence only: it is not runtime deployment,
durability, currentness, replay consumption, object-selection authorization,
or admission.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import re
import sys
import tomllib
from pathlib import Path
from types import ModuleType
from typing import Any


sys.dont_write_bytecode = True

STATUS = (
    "RECOVERED_ENVELOPE_SOURCE_PREREGISTERED_SYNTHETIC_STRICT_BYTE_ONLY_"
    "SOURCE_SIGNED_RAW_S9_RAW_S10_LOCAL_REVERIFY_HISTORICAL_ONLY_NO_RUNTIME_"
    "ADAPTER_NO_DURABILITY_PROOF_NO_CURRENTNESS_NO_ADMISSION"
)
DECISION = "BLOCKED_FAIL_CLOSED"
FEATURE = "temporal-evidence-s14-recovered-envelope-source-synthetic"
S13_FEATURE = "temporal-evidence-s13-recovered-envelope-delivery-synthetic"

CONTRACT_PATH = (
    "docs/design/fixtures/"
    "biocortex-ab-track-b-recovered-envelope-source-s14-v0.json"
)
GATE_PATH = "docs/design/fixtures/biocortex-ab-track-b-successor-admission-gate-s14-v0.json"
DESIGN_PATH = "docs/design/MEMORY_TEMPORAL_RECOVERED_ENVELOPE_SOURCE_S14_2026_07_15.md"
STORE_CARGO_PATH = "crates/store/Cargo.toml"
S14_SOURCE_PATH = (
    "crates/store/src/temporal_replay_transport/"
    "recovered_s9_decision_reverification/recovered_envelope_delivery/"
    "recovered_envelope_source.rs"
)
S13_SOURCE_PATH = (
    "crates/store/src/temporal_replay_transport/"
    "recovered_s9_decision_reverification/recovered_envelope_delivery.rs"
)
S12_SOURCE_PATH = (
    "crates/store/src/temporal_replay_transport/"
    "recovered_s9_decision_reverification.rs"
)
S10_SOURCE_PATH = "crates/store/src/temporal_replay_transport/external_operation_recovery.rs"
S12_CHECKER_PATH = "scripts/eval/check_memory_temporal_recovered_s9_decision_reverification_s12.py"

S9_CONTRACT_PATH = (
    "docs/design/fixtures/biocortex-ab-track-b-external-authority-provider-s9-v0.json"
)
S10_CONTRACT_PATH = (
    "docs/design/fixtures/biocortex-ab-track-b-external-operation-recovery-s10-v0.json"
)
S11_CONTRACT_PATH = (
    "docs/design/fixtures/biocortex-ab-track-b-atomic-authority-operation-s11-v0.json"
)
S12_CONTRACT_PATH = (
    "docs/design/fixtures/biocortex-ab-track-b-recovered-s9-decision-reverification-s12-v0.json"
)
S13_CONTRACT_PATH = (
    "docs/design/fixtures/biocortex-ab-track-b-recovered-envelope-delivery-s13-v0.json"
)

S9_CONTRACT_SHA256 = "d537b80ce0d2bbb3c4d01a988a9685432672078eae07d0b976b1268a27526fc4"
S10_CONTRACT_SHA256 = "da3566f13df522958f05c871ad4679d89cda9b888ba8aa4eb4caaee4c457fb88"
S11_CONTRACT_SHA256 = "eaca1280836bb31a3e1d0ce11173c6e34dbddf24a19e270af21d579428327db2"
S12_CONTRACT_SHA256 = "4efa9dc533cfca6c98473ae20cf8fc983292362e92b669575a81e80e189b1303"
S13_CONTRACT_SHA256 = "6bb6176822dac0bcf72a634ad4fc109cb7eed1d8b9d6e4b3d2e774852074b6a6"

POLICY = b"agent-bridge/track-b/recovered-envelope-source/v1"
PROFILE = b"STRICT_BYTE_ONLY_SOURCE_SIGNED_CAPTURE_RAW_S9_RAW_S10_LOCAL_REVERIFY_HISTORICAL_ONLY"
SOURCE_RECORD_SCHEMA = b"agent-bridge/track-b/recovered-envelope-source-record/v1"
S9_WIRE_SCHEMA = b"agent-bridge/track-b/recovered-s9-byte-wire/v1"
S10_WIRE_SCHEMA = b"agent-bridge/track-b/recovered-s10-byte-wire/v1"
PROVENANCE_SCHEMA = b"agent-bridge/track-b/recovered-envelope-capture-provenance/v1"
SOURCE_RECORD_DOMAIN = b"agent-bridge/track-b/recovered-envelope-source/source-record/v1"
S9_WIRE_DOMAIN = b"agent-bridge/track-b/recovered-envelope-source/s9-wire/v1"
S10_WIRE_DOMAIN = b"agent-bridge/track-b/recovered-envelope-source/s10-wire/v1"
PROVENANCE_DOMAIN = b"agent-bridge/track-b/recovered-envelope-source/capture-provenance/v1"
RAW_OBJECT_DOMAIN = b"agent-bridge/track-b/recovered-envelope-source/raw-object/v1"
HISTORICAL_SOURCE_DOMAIN = (
    b"agent-bridge/track-b/recovered-envelope-source/historical-source-chain/v1"
)

S13_POLICY = b"agent-bridge/track-b/recovered-envelope-delivery/v1"
S13_PROFILE = (
    b"OWNED_EXACT_S9_ENVELOPE_PLUS_LEXICAL_VERIFIED_S10_PROJECTION_HISTORICAL_ONLY"
)
S13_ENVELOPE_SCHEMA = b"agent-bridge/track-b/recovered-s9-envelope/v1"
S13_ENVELOPE_DOMAIN = (
    b"agent-bridge/track-b/recovered-envelope-delivery/envelope-digest/v1"
)

MAX_CANONICAL_MESSAGE_BYTES = 65_536
MAX_EVIDENCE_COMPONENT_BYTES = 131_072
MAX_S9_WIRE_BYTES = 135_168
MAX_S10_WIRE_BYTES = 135_168
MAX_PROVENANCE_BYTES = 4_096
MAX_SOURCE_RECORD_BYTES = 278_528
MAX_LABEL_BYTES = 128
SIGNATURE_BYTES = 64
SOURCE_RECORD_FRAMES = 9
S9_WIRE_FRAMES = 12
S10_WIRE_FRAMES = 10
PROVENANCE_FRAMES = 32
S9_REQUEST_FRAMES = 18
S9_DECISION_FRAMES = 22
S10_QUERY_FRAMES = 17
S10_OBSERVATION_FRAMES = 21

SOURCE_SEED = bytes.fromhex(
    "f5e5767cf153319517630f226876b86c8160cc583bc013744c6bf255f5cc0ee5"
)

OPERATIONAL_GAPS = (
    "RECOVERED_S9_DECISION_EXTERNAL_RUNTIME_CARRIER_UNIMPLEMENTED",
    "RECOVERED_S9_DECISION_BYTES_AVAILABILITY_UNATTESTED",
    "RECOVERED_S9_RAW_DECISION_EXTERNAL_DURABILITY_UNATTESTED",
    "RECOVERED_ENVELOPE_EXTERNAL_DURABLE_SOURCE_RUNTIME_UNIMPLEMENTED",
    "RECOVERED_ENVELOPE_BOUNDED_STREAM_RUNTIME_ADAPTER_UNIMPLEMENTED",
    "RECOVERED_ENVELOPE_CAPTURE_PROVENANCE_RUNTIME_UNATTESTED",
    "RECOVERED_ENVELOPE_CAPTURE_SIGNER_CUSTODY_UNATTESTED",
    "RECOVERED_ENVELOPE_CAPTURE_SIGNER_ROLE_SEPARATION_UNATTESTED",
    "RECOVERED_ENVELOPE_EXACT_LOOKUP_OWNER_AUTHORIZATION_UNATTESTED",
    "RECOVERED_ENVELOPE_SOURCE_ROLLBACK_AND_EQUIVOCATION_UNATTESTED",
    "RECOVERED_S10_RAW_EVIDENCE_RUNTIME_DELIVERY_UNIMPLEMENTED",
    "RECOVERED_HANDOFF_PROCESS_RESTART_UNAVAILABLE",
    "RECOVERED_HANDOFF_NOT_GLOBAL_REPLAY_FENCE",
    "RECOVERED_S9_DECISION_HISTORICAL_ONLY_NOT_CURRENT_AT_USE",
    "OWNER_PINNED_TRUST_ANCHOR_UNAVAILABLE",
    "PROVIDER_LINEARIZABILITY_UNATTESTED",
    "PROVIDER_SPLIT_BRAIN_FENCING_UNATTESTED",
    "PROVIDER_STATE_ROLLBACK_UNATTESTED",
    "ATOMIC_AUTHORITY_OPERATION_EXTERNAL_DATABASE_UNIMPLEMENTED",
    "DATABASE_KMS_CROSS_SERVICE_ATOMICITY_UNATTESTED",
    "CURRENTNESS_AT_DOWNSTREAM_USE_UNATTESTED",
)
REMAINING_GAPS = (
    "AUTHORITY_POLICY_CUSTODY_UNRESOLVED",
    "CAPTURE_PROVENANCE_UNATTESTED",
    "CROSS_BIOCORTEX_OPAQUE_HANDLE_TRANSPORT_UNIMPLEMENTED",
    "PHYSICAL_PRIVACY_DELETION_UNRESOLVED",
    "PRODUCTION_PRODUCER_PROFILE_UNADMITTED",
)

TEST_NAMES = (
    "s14_known_answer_record_provenance_and_historical_chains_are_stable",
    "s14_exact_source_is_read_once_into_one_owned_snapshot",
    "s14_repeated_record_can_be_reverified_and_is_not_a_replay_fence",
    "s14_ingress_accepts_exact_cap_and_rejects_max_plus_one_before_extend",
    "s14_every_source_failure_is_one_read_no_retry_no_fallback",
    "s14_record_digest_mismatch_rejects_before_decode",
    "s14_every_record_truncation_and_trailing_byte_rejects",
    "s14_record_duplicate_reordered_or_unknown_frame_rejects",
    "s14_length_prefix_overflow_zero_and_remaining_bounds_reject",
    "s14_label_128_passes_and_129_or_nonascii_rejects_before_string_allocation",
    "s14_fixed_width_and_signature_63_65_reject",
    "s14_s9_and_s10_inner_truncation_or_append_rejects",
    "s14_invalid_source_permit_metadata_and_revision_floor_reject",
    "s14_provenance_exact_framing_sequence_and_evidence_caps_reject",
    "s14_schema_policy_profile_or_contract_drift_rejects",
    "s14_source_signature_tamper_and_wrong_public_key_reject",
    "s14_lookup_or_source_permit_scope_substitution_rejects",
    "s14_resigned_provenance_semantic_mismatch_still_rejects",
    "s14_validly_resigned_cross_fixture_s9_s10_mix_fails_final_cross_binding",
    "s14_s9_or_s10_signature_tamper_can_be_captured_but_not_locally_verified",
    "s14_noncommitted_s10_is_strictly_decodable_but_fails_local_reverification",
    "s14_two_signed_same_revision_objects_show_no_equivocation_or_rollback_proof",
    "s14_mixed_snapshot_toctou_bytes_reject",
    "s14_debug_and_source_keep_every_capability_private_and_detached",
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


def artifact_sha256(repo: Path, relative: str) -> str:
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


def strict_equal(actual: Any, expected: Any) -> bool:
    if type(actual) is not type(expected):
        return False
    if isinstance(expected, dict):
        return set(actual) == set(expected) and all(
            strict_equal(actual[key], expected[key]) for key in expected
        )
    if isinstance(expected, list):
        return len(actual) == len(expected) and all(
            strict_equal(left, right) for left, right in zip(actual, expected)
        )
    return bool(actual == expected)


def require_exact(actual: Any, expected: Any, message: str) -> None:
    require(strict_equal(actual, expected), message)


def import_module(path: Path, name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    require(spec is not None and spec.loader is not None, f"cannot load module: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def rust_fn_body(source: str, name: str) -> str:
    match = re.search(rf"\bfn\s+{re.escape(name)}(?:<[^>]*>)?\s*\(", source)
    require(match is not None, f"missing Rust function: {name}")
    opening = source.find("{", match.end())
    require(opening >= 0, f"missing Rust function body: {name}")
    depth = 0
    for index in range(opening, len(source)):
        if source[index] == "{":
            depth += 1
        elif source[index] == "}":
            depth -= 1
            if depth == 0:
                return source[opening + 1 : index]
    raise CheckFailure(f"unterminated Rust function body: {name}")


def rust_struct_body(source: str, name: str) -> str:
    match = re.search(rf"\bstruct\s+{re.escape(name)}\s*\{{", source)
    require(match is not None, f"missing Rust struct: {name}")
    end = source.find("\n}", match.end())
    require(end >= 0, f"unterminated Rust struct: {name}")
    return source[match.end() : end]


def feature_is_reachable(features: dict[str, Any], roots: list[str], target: str) -> bool:
    pending = list(roots)
    visited: set[str] = set()
    while pending:
        current = pending.pop()
        if current == target:
            return True
        if current in visited or current not in features:
            continue
        visited.add(current)
        edges = features[current]
        require(isinstance(edges, list), f"Cargo feature is not a list: {current}")
        for edge in edges:
            require(isinstance(edge, str), f"Cargo feature edge is not a string: {current}")
            if edge in features or edge == target:
                pending.append(edge)
    return False


def independent_vectors(repo: Path) -> dict[str, bytes | int]:
    """Rebuild every S14 byte layer without importing the S13 checker."""

    s12 = import_module(repo / S12_CHECKER_PATH, "s12_reference_for_s14")
    upstream = s12.independent_vectors(repo)
    ref = s12.import_s9_reference(repo)
    framed_message = ref.framed_message
    framed_digest = ref.framed_digest
    repeated = lambda value: bytes([value]) * 32
    u64 = lambda value: value.to_bytes(8, "big")

    for name, expected in (
        ("S9_CONTRACT_SHA256", S9_CONTRACT_SHA256),
        ("S10_CONTRACT_SHA256", S10_CONTRACT_SHA256),
        ("S11_CONTRACT_SHA256", S11_CONTRACT_SHA256),
    ):
        require(getattr(s12, name) == expected, f"S12 predecessor pin drift: {name}")

    s9_contract = bytes.fromhex(S9_CONTRACT_SHA256)
    s10_contract = bytes.fromhex(S10_CONTRACT_SHA256)
    s11_contract = bytes.fromhex(S11_CONTRACT_SHA256)
    s12_contract = bytes.fromhex(S12_CONTRACT_SHA256)
    s13_contract = bytes.fromhex(S13_CONTRACT_SHA256)

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
            s12.S9_KEY_REF_DOMAIN,
            [
                s12.S9_POLICY,
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
        s12.S9_KEYSET_DOMAIN,
        [
            s12.S9_POLICY,
            opaque_key_ref(b"handle-key", 11, b"HANDLE"),
            opaque_key_ref(b"inner-key", 12, b"INNER_TRANSPORT"),
            opaque_key_ref(b"outer-key", 13, b"OUTER_CHANNEL"),
        ],
    )
    s9_request = framed_message(
        s12.S9_REQUEST_DOMAIN,
        [
            s12.S9_POLICY,
            s12.ALGORITHM,
            s12.S9_LEASE,
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
    s9_request_sha = hashlib.sha256(s9_request).digest()
    revocation = framed_digest(s12.S9_REVOCATION_DOMAIN, [s9_request_sha, u64(42)])
    custody = framed_digest(s12.S9_CUSTODY_DOMAIN, [keyset, u64(2), u64(42)])
    use_denied = framed_digest(s12.S9_USE_DENIED_DOMAIN, [epoch_record, u64(2), u64(42)])
    decision_id = framed_digest(s12.S9_DECISION_ID_DOMAIN, [operation, challenge, u64(42)])
    s9_decision = framed_message(
        s12.S9_DECISION_DOMAIN,
        [
            s12.S9_POLICY,
            s12.ALGORITHM,
            s12.S9_LEASE,
            s9_request_sha,
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
    s9_decision_sha = hashlib.sha256(s9_decision).digest()
    s9_signature = ref.ed25519_sign(s12.S9_SEED, s9_decision)

    journal_generation = repeated(0x72)
    s10_query = framed_message(
        s12.S10_QUERY_DOMAIN,
        [
            s12.S10_POLICY,
            s12.ALGORITHM,
            s12.S10_PROFILE,
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
            s9_request_sha,
            trust_policy,
        ],
    )
    s10_query_sha = hashlib.sha256(s10_query).digest()
    s10_result_id = framed_digest(
        s12.S10_RESULT_DOMAIN,
        [
            s12.S10_POLICY,
            s9_contract,
            operation,
            challenge,
            s9_request_sha,
            u64(43),
            journal_generation,
            u64(10),
            s9_decision_sha,
        ],
    )
    s10_observation = framed_message(
        s12.S10_OBSERVATION_DOMAIN,
        [
            s12.S10_POLICY,
            s12.ALGORITHM,
            s12.S10_PROFILE,
            s9_contract,
            s10_query_sha,
            b"COMMITTED",
            operation,
            challenge,
            s9_request_sha,
            cluster,
            incarnation,
            u64(7),
            u64(43),
            u64(50),
            journal_generation,
            u64(10),
            s9_decision_sha,
            s10_result_id,
            b"recovery-signer-a",
            u64(4),
        ],
    )
    s10_observation_sha = hashlib.sha256(s10_observation).digest()
    s10_signature = ref.ed25519_sign(s12.S10_SEED, s10_observation)

    s13_envelope_sha = framed_digest(
        S13_ENVELOPE_DOMAIN,
        [
            S13_POLICY,
            S13_PROFILE,
            S13_ENVELOPE_SCHEMA,
            s9_contract,
            s10_contract,
            s11_contract,
            s12_contract,
            s9_request,
            s9_decision,
            s9_signature,
        ],
    )
    s9_wire = framed_message(
        S9_WIRE_DOMAIN,
        [
            POLICY,
            PROFILE,
            S9_WIRE_SCHEMA,
            s9_contract,
            s10_contract,
            s11_contract,
            s12_contract,
            s13_contract,
            s9_request,
            s9_decision,
            s9_signature,
        ],
    )
    s10_wire = framed_message(
        S10_WIRE_DOMAIN,
        [
            POLICY,
            PROFILE,
            S10_WIRE_SCHEMA,
            s9_contract,
            s10_contract,
            s13_contract,
            s10_query,
            s10_observation,
            s10_signature,
        ],
    )
    s9_wire_sha = hashlib.sha256(s9_wire).digest()
    s10_wire_sha = hashlib.sha256(s10_wire).digest()
    evidence_payload_size = len(s9_wire) + len(s10_wire)
    raw_object_sha = framed_digest(RAW_OBJECT_DOMAIN, [s9_wire, s10_wire])

    source_profile = b"durable-source-profile-a"
    source_namespace = b"durable-source-namespace-a"
    source_cluster = b"durable-source-cluster-a"
    provenance = framed_message(
        PROVENANCE_DOMAIN,
        [
            POLICY,
            PROFILE,
            PROVENANCE_SCHEMA,
            source_profile,
            source_namespace,
            tenant,
            audience,
            source_cluster,
            repeated(0x81),
            repeated(0x82),
            repeated(0x83),
            u64(17),
            u64(evidence_payload_size),
            raw_object_sha,
            u64(len(s9_wire)),
            s9_wire_sha,
            u64(len(s10_wire)),
            s10_wire_sha,
            s13_envelope_sha,
            s9_request_sha,
            s9_decision_sha,
            s10_query_sha,
            s10_observation_sha,
            repeated(0x84),
            u64(1),
            repeated(0x85),
            repeated(0x86),
            repeated(0x87),
            bytes(32),
            b"capture-signer-a",
            u64(2),
        ],
    )
    source_public_key = ref.ed25519_public_key(SOURCE_SEED)
    source_signature = ref.ed25519_sign(SOURCE_SEED, provenance)
    record = framed_message(
        SOURCE_RECORD_DOMAIN,
        [
            POLICY,
            PROFILE,
            SOURCE_RECORD_SCHEMA,
            s13_contract,
            s9_wire,
            s10_wire,
            provenance,
            source_signature,
        ],
    )
    record_sha = hashlib.sha256(record).digest()
    provenance_sha = hashlib.sha256(provenance).digest()
    historical_chain = bytes.fromhex(str(upstream["historical_chain_sha256"]))
    historical_source_chain = framed_digest(
        HISTORICAL_SOURCE_DOMAIN,
        [
            POLICY,
            PROFILE,
            SOURCE_RECORD_SCHEMA,
            s13_contract,
            record_sha,
            provenance_sha,
            s9_wire_sha,
            s10_wire_sha,
            raw_object_sha,
            historical_chain,
        ],
    )

    for actual, expected, label in (
        (s9_request_sha.hex(), str(upstream["s9_request_sha256"]), "S9 request"),
        (s9_decision_sha.hex(), str(upstream["s9_decision_message_sha256"]), "S9 decision"),
        (s9_signature.hex(), str(upstream["s9_ed25519_signature"]), "S9 signature"),
        (s10_query_sha.hex(), str(upstream["s10_lookup_query_sha256"]), "S10 query"),
        (s10_observation_sha.hex(), str(upstream["s10_observation_sha256"]), "S10 observation"),
        (s10_signature.hex(), str(upstream["s10_ed25519_signature"]), "S10 signature"),
    ):
        require(actual == expected, f"independent predecessor KAT drift: {label}")
    for public_key, message, signature, label in (
        (ref.ed25519_public_key(s12.S9_SEED), s9_decision, s9_signature, "S9"),
        (ref.ed25519_public_key(s12.S10_SEED), s10_observation, s10_signature, "S10"),
        (source_public_key, provenance, source_signature, "source"),
    ):
        require(ref.ed25519_verify(public_key, message, signature), f"{label} Ed25519 KAT failed")
        changed = bytearray(signature)
        changed[0] ^= 1
        require(
            not ref.ed25519_verify(public_key, message, bytes(changed)),
            f"{label} tampered Ed25519 signature accepted",
        )
    require(
        not ref.ed25519_verify(ref.ed25519_public_key(s12.S9_SEED), provenance, source_signature),
        "source fixture signature accepted under the S9 fixture key",
    )
    require(evidence_payload_size != len(record), "E9+E10 payload size aliased outer R size")
    require(raw_object_sha != record_sha, "E9+E10 payload digest aliased outer R digest")

    return {
        "s9_request": s9_request,
        "s9_decision": s9_decision,
        "s9_signature": s9_signature,
        "s10_query": s10_query,
        "s10_observation": s10_observation,
        "s10_signature": s10_signature,
        "s13_envelope_sha256": s13_envelope_sha,
        "s9_wire": s9_wire,
        "s10_wire": s10_wire,
        "evidence_payload_size": evidence_payload_size,
        "raw_object_sha256": raw_object_sha,
        "provenance": provenance,
        "source_public_key": source_public_key,
        "source_signature": source_signature,
        "record": record,
        "historical_chain_sha256": historical_chain,
        "historical_source_chain_sha256": historical_source_chain,
    }


def known_vector_json(vectors: dict[str, bytes | int]) -> dict[str, str | int]:
    as_bytes = lambda name: bytes(vectors[name])
    return {
        "historical_chain_sha256": as_bytes("historical_chain_sha256").hex(),
        "historical_source_chain_sha256": as_bytes("historical_source_chain_sha256").hex(),
        "provenance_len": len(as_bytes("provenance")),
        "provenance_sha256": hashlib.sha256(as_bytes("provenance")).hexdigest(),
        "record_len": len(as_bytes("record")),
        "record_sha256": hashlib.sha256(as_bytes("record")).hexdigest(),
        "s10_observation_message_len": len(as_bytes("s10_observation")),
        "s10_observation_message_sha256": hashlib.sha256(as_bytes("s10_observation")).hexdigest(),
        "s10_query_message_len": len(as_bytes("s10_query")),
        "s10_query_message_sha256": hashlib.sha256(as_bytes("s10_query")).hexdigest(),
        "s10_wire_len": len(as_bytes("s10_wire")),
        "s10_wire_sha256": hashlib.sha256(as_bytes("s10_wire")).hexdigest(),
        "s13_envelope_sha256": as_bytes("s13_envelope_sha256").hex(),
        "s9_wire_len": len(as_bytes("s9_wire")),
        "s9_wire_sha256": hashlib.sha256(as_bytes("s9_wire")).hexdigest(),
        "source_ed25519_public_key": as_bytes("source_public_key").hex(),
        "source_ed25519_signature": as_bytes("source_signature").hex(),
    }


def check_predecessors(repo: Path) -> None:
    for path, expected, label in (
        (S9_CONTRACT_PATH, S9_CONTRACT_SHA256, "S9 contract"),
        (S10_CONTRACT_PATH, S10_CONTRACT_SHA256, "S10 contract"),
        (S11_CONTRACT_PATH, S11_CONTRACT_SHA256, "S11 contract"),
        (S12_CONTRACT_PATH, S12_CONTRACT_SHA256, "S12 contract"),
        (S13_CONTRACT_PATH, S13_CONTRACT_SHA256, "S13 contract"),
    ):
        require(artifact_sha256(repo, path) == expected, f"{label} digest drift")


def check_contract(repo: Path, vectors: dict[str, bytes | int]) -> None:
    contract = load_json(repo, CONTRACT_PATH)
    require_exact(
        set(contract),
        {
            "boundary",
            "capture_provenance",
            "decision",
            "dependency",
            "ingress",
            "known_vector",
            "negative_evidence",
            "operational_gap_codes",
            "policy",
            "profile",
            "remaining_gap_codes",
            "schema",
            "source_contract",
            "status",
            "test_matrix",
            "wire",
        },
        "contract top-level keys drift",
    )
    require_exact(contract["schema"], "agent_bridge.memory_temporal_recovered_envelope_source_s14.v0", "contract schema drift")
    require_exact(contract["status"], STATUS, "contract status drift")
    require_exact(contract["decision"], DECISION, "contract decision drift")
    require_exact(contract["policy"], POLICY.decode(), "contract policy drift")
    require_exact(contract["profile"], PROFILE.decode(), "contract profile drift")
    require_exact(
        contract["dependency"],
        {
            "feature": FEATURE,
            "feature_default_enabled": False,
            "requires_feature": S13_FEATURE,
            "s10_query_digest_known_answer_unchanged": True,
            "s13_handoff_visibility_widened": False,
        },
        "contract dependency drift",
    )
    require_exact(
        contract["boundary"],
        {
            "bridge_or_state_store_caller": False,
            "byte_only_decoder_preregistered": True,
            "capture_provenance_runtime_attested": False,
            "currentness_or_admission_issued": False,
            "external_durable_source_runtime_implemented": False,
            "runtime_adapter_present": False,
            "side_effects_unlocked": "NONE",
            "streaming_bounded_ingress_preregistered": True,
        },
        "contract boundary drift",
    )
    require_exact(
        contract["ingress"],
        {
            "allocation_uses_try_reserve": True,
            "empty_record_rejected": True,
            "max_source_record_bytes": MAX_SOURCE_RECORD_BYTES,
            "max_plus_one_rejected_before_extend": True,
            "source_returns_preallocated_unbounded_box": False,
            "source_streams_into_private_sink": True,
        },
        "contract ingress drift",
    )
    require_exact(
        contract["wire"],
        {
            "canonicalization": "u64be_length_prefixed_fixed_position_exact_frame_count_exact_eof",
            "provenance_frame_count": PROVENANCE_FRAMES,
            "provenance_max_bytes": MAX_PROVENANCE_BYTES,
            "s10_wire_frame_count": S10_WIRE_FRAMES,
            "s10_wire_max_bytes": MAX_S10_WIRE_BYTES,
            "s9_wire_frame_count": S9_WIRE_FRAMES,
            "s9_wire_max_bytes": MAX_S9_WIRE_BYTES,
            "serde_or_json_used": False,
            "source_record_frame_count": SOURCE_RECORD_FRAMES,
            "unknown_duplicate_alias_default_or_trailing_fields_allowed": False,
        },
        "contract wire drift",
    )
    require_exact(
        contract["source_contract"],
        {
            "cache_or_fallback_available": False,
            "exact_generation_object_revision_and_digest_required": True,
            "latest_list_retry_write_or_delete_available": False,
            "private_sealed_trait": True,
            "production_implementation_present": False,
            "single_exact_read_per_attempt": True,
        },
        "source contract drift",
    )
    require_exact(
        contract["capture_provenance"],
        {
            "binds_exact_s9_and_s10_wire": True,
            "binds_exact_source_generation_object_and_revision": True,
            "binds_s13_envelope_and_inner_message_digests": True,
            "debug_redacted": True,
            "evidence_payload_size_and_hash_bind_e9_e10_not_outer_record": True,
            "move_only_verified_capture_claim": True,
            "outer_record_digest_pinned_by_exact_lookup": True,
            "production_trust_permit_constructor_present": False,
            "source_signature_algorithm": "Ed25519",
            "source_signature_proves_actual_capture_or_durability": False,
            "source_signer_key_independence_enforced_or_attested": False,
            "source_signer_logical_role_separately_pinned": True,
        },
        "capture-provenance contract drift",
    )
    require_exact(
        contract["negative_evidence"],
        {
            "capture_sequence_is_current_chain_head": False,
            "exact_read_is_global_replay_consumption": False,
            "exact_lookup_is_owner_authorized_runtime_object_selection": False,
            "feature_flag_is_authorization": False,
            "historical_source_chain_is_admission": False,
            "source_revision_proves_no_rollback": False,
            "source_signature_proves_external_durability": False,
            "source_signature_proves_non_equivocation": False,
            "streaming_contract_proves_runtime_adapter": False,
        },
        "negative-evidence contract drift",
    )
    require_exact(contract["known_vector"], known_vector_json(vectors), "known-vector contract drift")
    require_exact(contract["operational_gap_codes"], list(OPERATIONAL_GAPS), "contract operational gaps drift")
    require_exact(contract["remaining_gap_codes"], list(REMAINING_GAPS), "contract remaining gaps drift")
    require(len(contract["test_matrix"]) == 21, "contract test matrix size drift")
    require(all(value is True for value in contract["test_matrix"].values()), "contract test matrix incomplete")


def check_gate(repo: Path) -> None:
    gate = load_json(repo, GATE_PATH)
    require_exact(
        set(gate),
        {
            "admission",
            "authorization_semantics",
            "boundary",
            "decision",
            "local_preregistration",
            "operational_gap_codes",
            "remaining_gap_codes",
            "required_successor_identity",
            "schema",
            "status",
        },
        "successor gate top-level keys drift",
    )
    require_exact(gate["schema"], "agent_bridge.memory_temporal_successor_admission_gate_s14.v0", "gate schema drift")
    require_exact(gate["status"], STATUS, "gate status drift")
    require_exact(gate["decision"], DECISION, "gate decision drift")
    require_exact(gate["operational_gap_codes"], list(OPERATIONAL_GAPS), "gate operational gaps drift")
    require_exact(gate["remaining_gap_codes"], list(REMAINING_GAPS), "gate remaining gaps drift")
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
            "capture_signature_proves_actual_capture": False,
            "capture_signature_proves_external_durability": False,
            "exact_source_read_is_global_replay_fence": False,
            "exact_lookup_is_owner_authorized_runtime_object_selection": False,
            "feature_flag_is_authorization": False,
            "historical_source_chain_is_admission_capability": False,
            "source_signer_key_independence_enforced_or_attested": False,
            "source_revision_is_currentness": False,
            "streaming_contract_is_runtime_deployment": False,
        },
        "gate authorization semantics drift",
    )
    require_exact(
        gate["boundary"],
        {
            "capture_provenance_runtime_attested": False,
            "currentness_and_consume_atomic": False,
            "external_durable_source_runtime_available": False,
            "owner_pinned_production_source_permit_available": False,
            "provider_rollback_and_split_brain_proved": False,
            "runtime_bounded_source_adapter_available": False,
            "runtime_recovered_bytes_available": False,
            "runtime_s10_delivery_available": False,
        },
        "gate runtime boundary drift",
    )
    require_exact(
        gate["local_preregistration"],
        {
            "bounded_streaming_ingress": True,
            "exact_source_object_lookup": True,
            "private_sealed_source_contract": True,
            "raw_s10_wire_representable": True,
            "s10_projection_lexical_only": True,
            "source_signed_capture_claim_verified": True,
            "strict_byte_only_decoder": True,
            "strict_s9_s10_reencode_equality": True,
        },
        "gate local preregistration drift",
    )
    require_exact(
        gate["required_successor_identity"],
        {
            "admission_receipt": None,
            "crash_restart_external_durability_evidence": True,
            "currentness_and_consume_atomicity": True,
            "owner_authorized_exact_object_selection": True,
            "owner_pinned_production_source_and_authority_permits": True,
            "provider_and_source_rollback_split_brain_evidence": True,
            "runtime_bounded_exact_source_adapter": True,
            "runtime_capture_attestation_and_signer_custody": True,
            "runtime_capture_signer_role_separation_evidence": True,
            "runtime_s10_delivery_and_local_reverification": True,
        },
        "gate successor requirements drift",
    )


def check_glue(repo: Path) -> tuple[str, str]:
    """Check only current descendant wiring; do not touch frozen predecessors."""

    cargo = tomllib.loads(read_text(repo, STORE_CARGO_PATH))
    features = cargo.get("features")
    require(isinstance(features, dict), "Cargo features table missing")
    require_exact(features.get(FEATURE), [S13_FEATURE], "S14 feature dependency drift")
    defaults = features.get("default", [])
    require(isinstance(defaults, list), "Cargo default feature list missing")
    require(not feature_is_reachable(features, defaults, FEATURE), "S14 became default-reachable")

    parent = read_text(repo, S13_SOURCE_PATH)
    s10 = read_text(repo, S10_SOURCE_PATH)
    require(
        f'#[cfg(feature = "{FEATURE}")]\nmod recovered_envelope_source;' in parent,
        "private S14 child module wiring drift",
    )
    require(parent.count("mod recovered_envelope_source;") == 1, "S14 module wiring duplicated")
    require("pub mod recovered_envelope_source" not in parent, "S14 module visibility widened")

    raw_query_match = re.search(r"(?m)^fn lookup_query_message\s*\(", s10)
    require(raw_query_match is not None, "S10 raw query framer is not private")
    require(re.search(r"pub\(super\)\s+fn\s+lookup_query_message", s10) is None, "S10 raw query framer visibility widened")
    require("pub(super) fn validated_lookup_query_message" in s10, "S10 validated query seam missing")
    validated_query = rust_fn_body(s10, "validated_lookup_query_message")
    require(validated_query.find("validate_query(query)?") < validated_query.find("lookup_query_message(query)"), "S10 query validation/framing order drift")
    lookup_digest = rust_fn_body(s10, "lookup_query_digest")
    require("validated_lookup_query_message(query)?" in lookup_digest, "S10 query digest bypassed validated message")
    return parent, s10


def check_rust(repo: Path) -> int:
    parent, s10 = check_glue(repo)
    source = read_text(repo, S14_SOURCE_PATH)
    production_marker = "#[cfg(test)]\nmod tests"
    require(production_marker in source, "S14 production/test split missing")
    production, tests = source.split(production_marker, 1)

    for forbidden in (
        "serde::",
        "Serialize",
        "Deserialize",
        "#[derive(Clone",
        "#[derive(Copy",
        "pub(crate)",
        "pub struct",
        "pub enum",
        "pub trait",
        "pub fn",
        "StateStore",
        "Bridge",
        "std::fs",
        "std::net",
        "tokio::",
        "rusqlite",
        "reqwest",
        ".lookup_operation(",
        ".request_currentness(",
    ):
        require(forbidden not in production, f"forbidden S14 production surface: {forbidden}")
    require(
        re.search(r"impl\s+(?:From|Into)<[^>]+>\s+for", production) is None,
        "S14 historical wrapper gained a conversion capability",
    )
    require(production.count("pub(super)") == 1, "S14 sibling visibility surface drift")
    require("pub(super) trait Sealed {}" in production, "private source seal drift")
    require(
        "trait ExternalRecoveredEnvelopeSourceV1: recovered_source_seal::Sealed" in production,
        "sealed exact source trait drift",
    )
    require("fn read_exact(" in production, "exact source read method missing")
    require("impl ExternalRecoveredEnvelopeSourceV1 for" not in production, "production source implementation appeared")
    require("fn test_only_new(" in production and "#[cfg(test)]" in production, "permit lost test-only constructor")
    require("fn new(" not in rust_struct_body(production, "ExternalRecoveredEnvelopeSourceTrustPermitV1"), "production permit constructor appeared")

    parser_body = rust_fn_body(production, "parse_framed_message")
    compact_parser = re.sub(r"\s+", " ", parser_body).replace(" .", ".")
    for required in (
        "cursor.checked_add(8)",
        "usize::try_from(length_u64)",
        "prefix_end.checked_add(length)",
        "raw.get(prefix_end..frame_end)",
        "if length == 0",
        "if cursor != raw.len()",
    ):
        require(required in compact_parser, f"strict parser hardening drift: {required}")

    sink_body = rust_fn_body(production, "push_chunk")
    compact_sink = re.sub(r"\s+", " ", sink_body).replace(" .", ".")
    positions = [
        compact_sink.find("checked_add(chunk.len())"),
        compact_sink.find("if new_len > MAX_SOURCE_RECORD_BYTES"),
        compact_sink.find("try_reserve(chunk.len())"),
        compact_sink.find("extend_from_slice(chunk)"),
    ]
    require(all(position >= 0 for position in positions), "bounded ingress operation missing")
    require(positions == sorted(positions), "bounded ingress check/reserve/extend ordering drift")
    finish_body = rust_fn_body(production, "finish")
    require("self.bytes.is_empty()" in finish_body, "empty source record no longer rejected")

    for name, value in (
        ("MAX_CANONICAL_MESSAGE_BYTES", "64 * 1024"),
        ("MAX_EVIDENCE_COMPONENT_BYTES", "128 * 1024"),
        ("MAX_S9_WIRE_BYTES", "132 * 1024"),
        ("MAX_S10_WIRE_BYTES", "132 * 1024"),
        ("MAX_PROVENANCE_MESSAGE_BYTES", "4 * 1024"),
        ("MAX_SOURCE_RECORD_BYTES", "272 * 1024"),
        ("MAX_LABEL_BYTES", "128"),
        ("ED25519_SIGNATURE_BYTES", "64"),
        ("SOURCE_RECORD_FRAME_COUNT", "9"),
        ("S9_WIRE_FRAME_COUNT", "12"),
        ("S10_WIRE_FRAME_COUNT", "10"),
        ("CAPTURE_PROVENANCE_FRAME_COUNT", "32"),
        ("S9_REQUEST_FRAME_COUNT", "18"),
        ("S9_DECISION_FRAME_COUNT", "22"),
        ("S10_QUERY_FRAME_COUNT", "17"),
        ("S10_OBSERVATION_FRAME_COUNT", "21"),
    ):
        require(f"const {name}: usize = {value};" in production, f"Rust bound/frame constant drift: {name}")

    for decoder, framer in (
        ("decode_s9_request_message", "super::s9_request_message"),
        ("decode_s9_decision_message", "super::validated_s9_decision_message"),
        ("decode_s10_query_message", "validated_lookup_query_message"),
        ("decode_s10_observation_message", "validated_observation_message"),
    ):
        body = rust_fn_body(production, decoder)
        require(framer in body and "exact_message_identity(" in body, f"strict typed re-encoding drift: {decoder}")
    require("VerifiedExternalOperationRecoveryObservationV1" not in production, "verified S10 projection escaped lexical handoff")
    require("RecoveredEvidenceHandoffV1::new(" in production, "S13 handoff construction missing")
    require(".handoff\n            .consume(" in production, "S13 consuming handoff missing")

    permit_body = rust_fn_body(production, "validate_source_permit")
    for required in (
        "permit.source_profile_id.as_bytes()",
        "permit.source_namespace_id.as_bytes()",
        "permit.tenant_id.as_bytes()",
        "permit.audience.as_bytes()",
        "permit.source_cluster_id.as_bytes()",
        "permit.signer_key_id.as_bytes()",
        "!nonzero(&permit.source_incarnation)",
        "!nonzero(&permit.source_generation_id)",
        "!nonzero(&permit.capture_policy_sha256)",
        "!nonzero(&permit.ed25519_public_key)",
        "permit.signer_key_version == 0",
        "permit.minimum_object_revision == 0",
    ):
        require(required in permit_body, f"source permit validation drift: {required}")
    verify_body = rust_fn_body(production, "verify_capture_claim")
    require(verify_body.lstrip().startswith("validate_source_permit(permit)?;"), "source permit is not validated first")
    require("claim.object_revision < permit.minimum_object_revision" in verify_body, "permit revision floor missing")
    require("s9_wire.len().checked_add(s10_wire.len())" in verify_body, "E9+E10 payload size binding missing")
    require("framed_digest(RAW_OBJECT_DOMAIN, &[s9_wire, s10_wire])" in verify_body, "E9+E10 payload digest binding missing")
    require("record_sha256" not in verify_body, "E9+E10 payload binding aliased outer R digest")
    require(verify_body.count("signer_key_id") == 2, "source signer role comparison surface drift")
    require(verify_body.count("signer_key_version") == 2, "source signer version comparison surface drift")
    for forbidden in (
        "decoded_s9.envelope.decision.signer_key",
        "decoded_s10.observation.signer_key",
        "s9_permit.ed25519_public_key",
        "s10_permit.ed25519_public_key",
        "s11_permit.ed25519_public_key",
    ):
        require(forbidden not in verify_body, "S14 unexpectedly claims cryptographic signer independence")

    claim_body = rust_struct_body(production, "CaptureProvenanceClaimV1")
    require("E9+E10 evidence payload, not the full outer" in claim_body, "payload-vs-record Rust comment missing")
    require("size is len(E9)+len(E10)" in claim_body and "RAW_OBJECT_DOMAIN" in claim_body, "payload size/hash semantics missing")
    require("ExactRecoveredEnvelopeLookupV1::expected_record_sha256" in claim_body, "outer R lookup distinction missing")
    decode_body = rust_fn_body(production, "decode_and_verify_source_record_v1")
    require(decode_body.find("record_sha256 != lookup.expected_record_sha256") < decode_body.find("decode_s9_wire"), "outer R digest must precede inner decode")
    final_fields = {
        line.strip().rstrip(",")
        for line in rust_struct_body(production, "SourcedHistoricalRecoveredEnvelopeV1").splitlines()
        if ":" in line
    }
    require_exact(
        final_fields,
        {
            "historical_source_chain_sha256: [u8; 32]",
            "historical_chain_sha256: [u8; 32]",
            "record_sha256: [u8; 32]",
            "provenance_message_sha256: [u8; 32]",
        },
        "final historical wrapper capability surface drift",
    )

    found_tests = tuple(re.findall(r"#\[test\]\s*fn\s+(s14_[a-z0-9_]+)", tests))
    require_exact(found_tests, TEST_NAMES, "S14 Rust test set/count drift")
    require("#[ignore]" not in tests, "S14 test became ignored")
    inner = rust_fn_body(tests, "s14_s9_and_s10_inner_truncation_or_append_rejects")
    for token in (
        "frames[9][..frames[9].len() - 1]",
        "frames[10][..frames[10].len() - 1]",
        "s10_frames[7][..s10_frames[7].len() - 1]",
        "s10_frames[8][..s10_frames[8].len() - 1]",
        "appended_request.push(0)",
        "appended_decision.push(0)",
        "appended_query.push(0)",
        "appended_observation.push(0)",
        'b"active"',
        'b"committed"',
        'b"alias"',
    ):
        require(token in inner, f"inner strict-framing regression drift: {token}")
    invalid_permit = rust_fn_body(tests, "s14_invalid_source_permit_metadata_and_revision_floor_reject")
    for token in (
        "source_profile_id.clear()",
        "source_incarnation = [0; 32]",
        "source_generation_id = [0; 32]",
        "signer_key_version = 0",
        "capture_policy_sha256 = [0; 32]",
        "minimum_object_revision = 0",
        "ed25519_public_key = [0; 32]",
        "object_revision + 1",
    ):
        require(token in invalid_permit, f"invalid permit regression drift: {token}")
    permit_factory = rust_fn_body(tests, "source_permit_for")
    require("claim.object_revision" in permit_factory, "valid equal revision floor fixture drift")
    cross_mix = rust_fn_body(tests, "s14_validly_resigned_cross_fixture_s9_s10_mix_fails_final_cross_binding")
    for token in (
        "verify_external_currentness_decision_v1(",
        "verify_external_operation_recovery_observation_v1(",
        "resign_s10(&mut independent_s10.observation)",
        "decode_and_verify_source_record_v1",
        ".consume_historical(",
        '"track_b_recovered_envelope_source_v1_local_reverification"',
    ):
        require(token in cross_mix, f"validly resigned cross-fixture regression drift: {token}")

    bridge_root = repo / "crates/bridge"
    for path in bridge_root.rglob("*.rs"):
        require(FEATURE not in path.read_text(encoding="utf-8"), "S14 feature wired into Bridge")
    return len(found_tests)


def check_design(repo: Path) -> None:
    design = read_text(repo, DESIGN_PATH)
    for required in (
        "Decision: `BLOCKED_FAIL_CLOSED`",
        "There is no production source implementation",
        "`object_size` is `len(E9) + len(E10)`",
        "`raw_object_sha256` is the\ndomain-framed E9+E10 evidence-payload digest",
        "Neither names the complete outer\nR bytes",
        "does not enforce or\nattest that its key material differs cryptographically",
        "owner-authorized runtime object selection",
        "capture signer custody or cryptographic role-separation evidence",
        "NOT durability · NOT currentness · NOT admission",
    ):
        require(required in design, f"design negative claim drift: {required}")


def receipt(repo: Path, vectors: dict[str, bytes | int], s14_tests: int) -> str:
    known = known_vector_json(vectors)
    rows: list[tuple[str, str]] = [
        ("schema", "agent_bridge.memory_temporal_recovered_envelope_source_s14_receipt.v0"),
        ("status", STATUS),
        ("decision", DECISION),
        ("feature", FEATURE),
        ("depends_on_feature", S13_FEATURE),
        ("feature_default_reachable", "false"),
        ("policy", POLICY.decode()),
        ("profile", PROFILE.decode()),
        ("source_record_schema", SOURCE_RECORD_SCHEMA.decode()),
        ("source_record_frame_count", str(SOURCE_RECORD_FRAMES)),
        ("s9_wire_frame_count", str(S9_WIRE_FRAMES)),
        ("s10_wire_frame_count", str(S10_WIRE_FRAMES)),
        ("provenance_frame_count", str(PROVENANCE_FRAMES)),
        ("s9_request_frame_count", str(S9_REQUEST_FRAMES)),
        ("s9_decision_frame_count", str(S9_DECISION_FRAMES)),
        ("s10_query_frame_count", str(S10_QUERY_FRAMES)),
        ("s10_observation_frame_count", str(S10_OBSERVATION_FRAMES)),
        ("max_canonical_message_bytes", str(MAX_CANONICAL_MESSAGE_BYTES)),
        ("max_evidence_component_bytes", str(MAX_EVIDENCE_COMPONENT_BYTES)),
        ("max_s9_wire_bytes", str(MAX_S9_WIRE_BYTES)),
        ("max_s10_wire_bytes", str(MAX_S10_WIRE_BYTES)),
        ("max_provenance_bytes", str(MAX_PROVENANCE_BYTES)),
        ("max_source_record_bytes", str(MAX_SOURCE_RECORD_BYTES)),
        ("max_label_bytes", str(MAX_LABEL_BYTES)),
        ("signature_bytes", str(SIGNATURE_BYTES)),
        ("known_s9_wire_len", str(known["s9_wire_len"])),
        ("known_s9_wire_sha256", str(known["s9_wire_sha256"])),
        ("known_s10_wire_len", str(known["s10_wire_len"])),
        ("known_s10_wire_sha256", str(known["s10_wire_sha256"])),
        ("known_s10_query_message_len", str(known["s10_query_message_len"])),
        ("known_s10_query_message_sha256", str(known["s10_query_message_sha256"])),
        ("known_s10_observation_message_len", str(known["s10_observation_message_len"])),
        ("known_s10_observation_message_sha256", str(known["s10_observation_message_sha256"])),
        ("known_evidence_payload_len", str(vectors["evidence_payload_size"])),
        ("known_evidence_payload_sha256", bytes(vectors["raw_object_sha256"]).hex()),
        ("known_provenance_len", str(known["provenance_len"])),
        ("known_provenance_sha256", str(known["provenance_sha256"])),
        ("known_source_ed25519_public_key", str(known["source_ed25519_public_key"])),
        ("known_source_ed25519_signature", str(known["source_ed25519_signature"])),
        ("known_record_len", str(known["record_len"])),
        ("known_record_sha256", str(known["record_sha256"])),
        ("known_s13_envelope_sha256", str(known["s13_envelope_sha256"])),
        ("known_historical_chain_sha256", str(known["historical_chain_sha256"])),
        ("known_historical_source_chain_sha256", str(known["historical_source_chain_sha256"])),
        ("s14_nonignored_rust_tests", str(s14_tests)),
        ("private_sealed_source_contract", "true"),
        ("production_source_implementation_present", "false"),
        ("production_trust_permit_constructor_present", "false"),
        ("strict_byte_only_fixed_frame_exact_eof", "true"),
        ("bounded_streaming_ingress_preregistered", "true"),
        ("source_permit_validated_before_capture_binding", "true"),
        ("evidence_payload_is_e9_plus_e10_not_outer_record", "true"),
        ("source_signer_logical_role_separately_pinned", "true"),
        ("source_signer_key_independence_enforced_or_attested", "false"),
        ("exact_lookup_is_owner_authorized_runtime_object_selection", "false"),
        ("s10_projection_lexical_only", "true"),
        ("external_durable_source_runtime_present", "false"),
        ("runtime_adapter_present", "false"),
        ("capture_provenance_runtime_attested", "false"),
        ("global_replay_fence_or_currentness", "false"),
        ("currentness_or_admission_issued", "false"),
        ("bridge_or_state_store_caller", "false"),
        ("side_effects_unlocked", "NONE"),
        ("operational_gaps", ",".join(OPERATIONAL_GAPS)),
        ("remaining_gaps", ",".join(REMAINING_GAPS)),
    ]
    for label, path in (
        ("contract_sha256", CONTRACT_PATH),
        ("successor_gate_sha256", GATE_PATH),
        ("design_sha256", DESIGN_PATH),
        ("store_cargo_sha256", STORE_CARGO_PATH),
        ("s14_source_sha256", S14_SOURCE_PATH),
        ("s13_source_sha256", S13_SOURCE_PATH),
        ("s12_source_sha256", S12_SOURCE_PATH),
        ("s10_source_sha256", S10_SOURCE_PATH),
    ):
        rows.append((label, artifact_sha256(repo, path)))
    return "".join(f"{key}\t{value}\n" for key, value in rows)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    parser.add_argument("--glue-only", action="store_true")
    args = parser.parse_args()
    repo = args.repo.resolve()
    try:
        if args.glue_only:
            check_glue(repo)
            sys.stdout.write("glue_check\tPASS\n")
            return 0
        check_predecessors(repo)
        vectors = independent_vectors(repo)
        check_contract(repo, vectors)
        check_gate(repo)
        s14_tests = check_rust(repo)
        check_design(repo)
        sys.stdout.write(receipt(repo, vectors, s14_tests))
    except (CheckFailure, OSError, UnicodeDecodeError, tomllib.TOMLDecodeError) as exc:
        print(f"S14_CHECK_FAILED\t{exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
