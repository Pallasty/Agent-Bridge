#!/usr/bin/env python3
"""Independent checker for the isolated-lab bootstrap-trust verifier.

The checker reconstructs the two public-only known-answer vectors without
calling the subject's fixture helpers.  It independently checks the Ed25519
equations and complete success receipts, proves that non-KAT modes are rejected
before any of the other three public inputs are observed, checks predecessor
ordering, and executes a broad directed mutation catalog.

No private key material, signing, key generation, provider call, credential,
network, clock, subprocess, persistence, or ambient trust store is used.
"""

from __future__ import annotations

import argparse
import ast
import copy
import hashlib
import importlib.util
import json
import re
import sys
from pathlib import Path
from types import ModuleType
from typing import Any, Callable, Mapping, NoReturn


sys.dont_write_bytecode = True

ROOT = Path(__file__).resolve().parents[2]
SOURCE_REL = (
    "scripts/eval/biocortex_ab_track_b_reference_provider_fault_injection_runner_"
    "bootstrap_trust_authentication_synthetic_trust_chain_exact_key_version_"
    "declared_role_and_revocation_verifier_isolated_lab_v1.py"
)
PREDECESSOR_SOURCE_REL = (
    "scripts/eval/biocortex_ab_track_b_reference_provider_fault_injection_runner_"
    "production_evidence_envelope_bounded_frame_parser_and_synthetic_mode_"
    "separation_isolated_lab_v1.py"
)
SCHEMA_REL = (
    "docs/design/fixtures/biocortex-ab-track-b-reference-provider-fault-injection-"
    "runner-bootstrap-trust-authentication-isolated-lab-v1.schema.json"
)
FIXTURE_REL = (
    "scripts/eval/fixtures/biocortex_ab_track_b_reference_provider_fault_injection_"
    "runner_bootstrap_trust_authentication_synthetic_trust_chain_exact_key_version_"
    "declared_role_and_revocation_verifier_isolated_lab_v1_pack_synthetic_v0.json"
)
FIXTURE_SCHEMA = (
    "agent_bridge.biocortex_ab_track_b_reference_provider_fault_injection_runner."
    "bootstrap_trust_authentication_synthetic_trust_chain_exact_key_version_"
    "declared_role_and_revocation_verifier_isolated_lab_v1_pack.synthetic.v0"
)

DATE = "2026-07-17"
SYNTHETIC_MODE = "SYNTHETIC_KAT"
PRODUCTION_MODE = "PRODUCTION"
TRUST_POLICY_SCHEMA = (
    "agent_bridge.biocortex_ab_track_b_reference_provider_fault_injection_"
    "runner.bootstrap_trust_authentication_synthetic_trust_policy_isolated_lab_kat.v1"
)
BUNDLE_SCHEMA = (
    "agent_bridge.biocortex_ab_track_b_reference_provider_fault_injection_"
    "runner.bootstrap_trust_authentication_detached_bundle_isolated_lab_kat.v1"
)
RECEIPT_SCHEMA = (
    "agent_bridge.biocortex_ab_track_b_reference_provider_fault_injection_"
    "runner.bootstrap_trust_authentication_synthetic_trust_chain_exact_key_"
    "version_declared_role_and_revocation_verifier_isolated_lab_v1.receipt.v0"
)
PACK_RECEIPT_SCHEMA = (
    "agent_bridge.biocortex_ab_track_b_reference_provider_fault_injection_runner."
    "bootstrap_trust_authentication_synthetic_trust_chain_exact_key_version_"
    "declared_role_and_revocation_verifier_isolated_lab_v1_pack.receipt.v0"
)
STATUS = (
    "REFERENCE_PROVIDER_BOOTSTRAP_TRUST_AUTHENTICATION_ISOLATED_LAB_SYNTHETIC_"
    "KAT_VERIFIER_CONFORMANT_PRODUCTION_AUTHORITY_ZERO"
)
DECISION = (
    "T05_SYNTHETIC_BOOTSTRAP_TRUST_COMPONENT_CONFORMANT_PRODUCTION_PATH_FAIL_CLOSED"
)
COMPONENT_STATE = (
    "AUTHENTICATED_SYNTHETIC_KAT_AGAINST_FROZEN_BOOTSTRAP_TRUST_"
    "SNAPSHOT_COMPONENT_ONLY"
)
SUBJECT_STATUS = (
    "REFERENCE_PROVIDER_MANAGED_AND_SELF_HOSTED_FAULT_INJECTION_RUNNER_V1_"
    "BOOTSTRAP_TRUST_AUTHENTICATION_SYNTHETIC_TRUST_CHAIN_EXACT_KEY_VERSION_"
    "DECLARED_ROLE_AND_REVOCATION_VERIFIED_ISOLATED_LAB_COMPONENT_ONLY_"
    "NO_PRODUCTION_AUTHORITY"
)
RECEIPT_DOMAIN = (
    "AB_TRACK_B_BOOTSTRAP_TRUST_AUTHENTICATION_ISOLATED_LAB_KAT_RECEIPT_V1"
)
PACK_RECEIPT_DOMAIN = (
    "AB_TRACK_B_BOOTSTRAP_TRUST_AUTHENTICATION_ISOLATED_LAB_PACK_RECEIPT_V1"
)
TRUST_DOMAIN_FAMILY = (
    "AB_TRACK_B_BOOTSTRAP_TRUST_AUTHENTICATION_ISOLATED_LAB_KAT_SIGNATURE_FAMILY_V1"
)
SIGNATURE_SCHEME = "ED25519_PURE_RFC8032_NO_CONTEXT_NO_PREHASH"
MESSAGE_PROFILE = (
    "U64BE_LENGTH_PREFIXED_ASCII_DOMAIN_AND_EXACT_PREDECESSOR_CANONICAL_"
    "FRAME_BYTES_NO_PARSE_RESERIALIZE"
)
DECLARED_ROLE = "SYNTHETIC_EVIDENCE_ENVELOPE_SIGNER_KAT_ONLY"
ACTIVE_STATE = "ACTIVE_AT_EXACT_FROZEN_SYNTHETIC_REVISION"
REVOKED_STATE = "REVOKED_AT_OR_BEFORE_EXACT_FROZEN_SYNTHETIC_REVISION"
PUBLIC_VECTOR_BUNDLE_SHA256 = "a87e0883a42ca69fe3a0348b4ffe44c153882f8dcc93eb67db1ea048d53851d7"

ENVELOPE_SCHEMA = (
    "agent_bridge.biocortex_ab_track_b_reference_provider_fault_injection_"
    "runner.production_evidence_envelope_bounded_frame_parser_and_synthetic_"
    "mode_separation_isolated_lab_kat.v1"
)
ENVELOPE_CANONICALIZATION = "AGENT_BRIDGE_CANONICAL_JSON_V1_SORTED_KEYS_COMPACT_UTF8"
ENVELOPE_HASH_DOMAIN = "AB_TRACK_B_PRODUCTION_EVIDENCE_ENVELOPE_ISOLATED_LAB_KAT_V1"

TRACKS: tuple[dict[str, Any], ...] = (
    {
        "track_id": "MANAGED_SPANNER_CLOUD_KMS",
        "vector_set_id": "KAT_MANAGED_BOOTSTRAP_TRUST_PUBLIC_ONLY_PRECOMPUTED_VECTOR_SET_V1",
        "policy_revision": "KAT_MANAGED_TRUST_POLICY_REVISION_1",
        "revocation_revision": "KAT_MANAGED_REVOCATION_SNAPSHOT_REVISION_1",
        "signature_domain": "AB_TRACK_B_BOOTSTRAP_TRUST_AUTHENTICATION_ISOLATED_LAB_MANAGED_KAT_SIGNATURE_V1",
        "frame_bytes": 659,
        "frame_sha256": "e298865e753a96d58b6c23d49b58cb2c4b512a519a65666d31170325bd34d295",
        "message_bytes": 754,
        "message_sha256": "a52aa400add05bb7b545c9eddbf1f48e55befd393f07c5c6ba6baaefd4f5343b",
        "message_sha512": "87ad26c16adb44af213047f0465f8e4217b0f71d69a12bdf0824ba67291df667f6ca5d5455195df526b62bf7d9bac4caeae5161cc518a12122e827a369d929fd",
        "predecessor_receipt_sha256": "16ba99d94139396dd1dae80adf31dd610656042ba290523b294bbae85fd82c37",
        "root": {
            "key_id": "KAT_MANAGED_BOOTSTRAP_ROOT_V1",
            "key_version": "KAT_MANAGED_ROOT_KEY_VERSION_1",
            "role": "KAT_MANAGED_BOOTSTRAP_ROOT",
            "public_key_hex": "b8b7e8edb2a4e95bed9fb2b288e68e48f136dd25c6e9be64eaaeabc4261f5c99",
        },
        "issuer": {
            "key_id": "KAT_MANAGED_TRUST_POLICY_ISSUER_V1",
            "key_version": "KAT_MANAGED_ISSUER_KEY_VERSION_1",
            "role": "KAT_MANAGED_TRUST_POLICY_ISSUER",
            "public_key_hex": "d91db78ec3ce8f1c5b3985690b20a6f17cd9685968febc9ae13d4d2c20a66583",
        },
        "leaf": {
            "key_id": "KAT_MANAGED_EVIDENCE_ENVELOPE_SIGNER_V2",
            "key_version": "KAT_MANAGED_LEAF_KEY_VERSION_2",
            "role": "KAT_MANAGED_EVIDENCE_ENVELOPE_SIGNER",
            "public_key_hex": "3fd584089659ed90ac0947f9cd3293ace455e2c8ce4520824b8201bc7dc35ca4",
        },
        "revoked_leaf_version": "KAT_MANAGED_LEAF_KEY_VERSION_1",
        "signature_hex": "b37707af4dcea9453fb1eb8e4d12fe0848fe998c2d424a57c45de991d48d1c5de86ddfc8d683e93ccd1ada062db2912c1d991819e6198641c8320fc84c62bf06",
    },
    {
        "track_id": "SELF_HOSTED_ETCD_OPENBAO",
        "vector_set_id": "KAT_SELF_HOSTED_BOOTSTRAP_TRUST_PUBLIC_ONLY_PRECOMPUTED_VECTOR_SET_V1",
        "policy_revision": "KAT_SELF_HOSTED_TRUST_POLICY_REVISION_1",
        "revocation_revision": "KAT_SELF_HOSTED_REVOCATION_SNAPSHOT_REVISION_1",
        "signature_domain": "AB_TRACK_B_BOOTSTRAP_TRUST_AUTHENTICATION_ISOLATED_LAB_SELF_HOSTED_KAT_SIGNATURE_V1",
        "frame_bytes": 658,
        "frame_sha256": "da147c9e4bcb4ac54e98209f5ea2970322726d3d851ac415903e1dbe311da69e",
        "message_bytes": 757,
        "message_sha256": "2eb3584afe6c8f18281224785ec083e531da37eed71524f2eedbf3a8225055ac",
        "message_sha512": "ccd600e63a84e74c5c29c319486ec4333f85f465864cc3b3c8c7c90bb9ccb8c8b57d45e35c83c8bab66c4d95babda967daea12406de5684b1cee2433256207bb",
        "predecessor_receipt_sha256": "381adf1576413c94605c9e4659353daa29088c784826f6b7a018c7253600171e",
        "root": {
            "key_id": "KAT_SELF_HOSTED_BOOTSTRAP_ROOT_V1",
            "key_version": "KAT_SELF_HOSTED_ROOT_KEY_VERSION_1",
            "role": "KAT_SELF_HOSTED_BOOTSTRAP_ROOT",
            "public_key_hex": "29aa03a7e15f1fe55876c08feda304c65c1ea8d85bb7eec6bf0ae1589b4c4fb2",
        },
        "issuer": {
            "key_id": "KAT_SELF_HOSTED_TRUST_POLICY_ISSUER_V1",
            "key_version": "KAT_SELF_HOSTED_ISSUER_KEY_VERSION_1",
            "role": "KAT_SELF_HOSTED_TRUST_POLICY_ISSUER",
            "public_key_hex": "d5e9bc56ec76659ef5e961e601b130dfe62cf0c7624576ddca65fc47e05d20d0",
        },
        "leaf": {
            "key_id": "KAT_SELF_HOSTED_EVIDENCE_ENVELOPE_SIGNER_V2",
            "key_version": "KAT_SELF_HOSTED_LEAF_KEY_VERSION_2",
            "role": "KAT_SELF_HOSTED_EVIDENCE_ENVELOPE_SIGNER",
            "public_key_hex": "b706afbe337aaf6df0c9ef5f55339a8f3a32192177bbd5a409041c171b88137c",
        },
        "revoked_leaf_version": "KAT_SELF_HOSTED_LEAF_KEY_VERSION_1",
        "signature_hex": "ba382ad51b591d02845bf17bd4d1c4d480b8ca21dc2ffe611f45f496d4ae3c6d361649474b2437d82d119bcae60a51f66ff3e658aa06049f0816eb77567b7105",
    },
)

TSV_FIELDS = (
    "schema", "status", "decision", "date", "mode", "component_state",
    "positive_track_count", "positive_signature_equation_count",
    "strict_public_point_count", "strict_signature_r_point_count",
    "public_mode_pre_observation_test_count", "predecessor_order_test_count",
    "json_strictness_negative_test_count", "policy_negative_test_count",
    "bundle_negative_test_count", "frame_binding_negative_test_count",
    "total_directed_negative_test_count", "source_ast_guard_count",
    "fixture_schema_guard_count", "fixture_expected_receipt_count",
    "isolated_lab_candidate_surface_component_total",
    "isolated_lab_candidate_surface_components_implemented",
    "local_threat_specifications_covered", "production_ingestion_control_count",
    "production_ingestion_controls_implemented",
    "production_ingestion_controls_runtime_exercised",
    "production_threat_specification_count",
    "production_threat_specifications_runtime_exercised",
    "runtime_prerequisite_count", "runtime_prerequisites_satisfied",
    "real_evidence_items_present", "production_validated_evidence_items",
    "runtime_authority", "provider_authority", "side_effects_unlocked",
    "frame_set_sha256", "bundle_set_sha256", "trust_policy_sha256",
    "receipt_set_sha256", "schema_raw_sha256", "fixture_raw_sha256",
    "source_raw_sha256", "predecessor_source_raw_sha256",
    "content_sha256",
)


class CheckError(ValueError):
    """Independent checker failure."""


def require(condition: bool, code: str, detail: str) -> None:
    if not condition:
        raise CheckError(f"{code}: {detail}")


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
    ).encode("utf-8")


def sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def domain_sha256(domain: str, value: Any) -> str:
    raw = value if type(value) is bytes else canonical_bytes(value)
    return sha256(domain.encode("ascii") + b"\x00" + raw)


def exact_equal(left: Any, right: Any) -> bool:
    if type(left) is not type(right):
        return False
    if type(left) is dict:
        return set(left) == set(right) and all(exact_equal(left[key], right[key]) for key in left)
    if type(left) is list:
        return len(left) == len(right) and all(exact_equal(a, b) for a, b in zip(left, right))
    return bool(left == right)


def safe_source(relative: str) -> Path:
    path = (ROOT / relative).resolve()
    require(ROOT in path.parents and path.is_file() and not path.is_symlink(), "E_SOURCE_PATH", relative)
    return path


def _artifact_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        require(type(key) is str and key not in result, "E_ARTIFACT_DUPLICATE_KEY", key)
        result[key] = value
    return result


def _artifact_int(token: str) -> int:
    require(len(token) <= 20, "E_ARTIFACT_INT_RANGE", token)
    value = int(token, 10)
    require(-(2**63) <= value <= 2**63 - 1, "E_ARTIFACT_INT_RANGE", token)
    return value


def _artifact_float(token: str) -> NoReturn:
    raise CheckError(f"E_ARTIFACT_FLOAT: {token}")


def _artifact_constant(token: str) -> NoReturn:
    raise CheckError(f"E_ARTIFACT_NONFINITE: {token}")


def read_artifact_json(relative: str) -> dict[str, Any]:
    raw = safe_source(relative).read_bytes()
    require(len(raw) <= 8 * 1024 * 1024 and not raw.startswith(b"\xef\xbb\xbf"), "E_ARTIFACT_BYTES", relative)
    try:
        value = json.loads(
            raw.decode("utf-8", "strict"),
            object_pairs_hook=_artifact_pairs,
            parse_int=_artifact_int,
            parse_float=_artifact_float,
            parse_constant=_artifact_constant,
        )
    except UnicodeDecodeError as error:
        raise CheckError(f"E_ARTIFACT_UTF8: {relative}") from error
    require(type(value) is dict, "E_ARTIFACT_ROOT", relative)
    return value


def load_module() -> ModuleType:
    path = safe_source(SOURCE_REL)
    source_parent = str(path.parent)
    if source_parent not in sys.path:
        sys.path.insert(0, source_parent)
    spec = importlib.util.spec_from_file_location("bootstrap_trust_verifier_subject", path)
    require(spec is not None and spec.loader is not None, "E_IMPORT_SPEC", SOURCE_REL)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    require(Path(module.__file__).resolve() == path, "E_IMPORT_ORIGIN", SOURCE_REL)
    predecessor_path = Path(module.predecessor.__file__).resolve()
    require(predecessor_path == safe_source(PREDECESSOR_SOURCE_REL), "E_PREDECESSOR_ORIGIN", str(predecessor_path))
    return module


def expected_frame(track: Mapping[str, Any]) -> bytes:
    envelope = {
        "canonicalization": ENVELOPE_CANONICALIZATION,
        "fixture_case_id": "VALID_MINIMAL_FRAME_V1",
        "fixture_payload": "NONSECRET_DETERMINISTIC_UTF8_JSON_FRAME_KAT_V1",
        "hash_domain": ENVELOPE_HASH_DOMAIN,
        "packet_kind": "SYNTHETIC_PRODUCTION_EVIDENCE_ENVELOPE_KAT",
        "prerequisite_id": "FRAME_AND_PARSE",
        "production_admissible": False,
        "schema": ENVELOPE_SCHEMA,
        "schema_version": 1,
        "synthetic_fixture": True,
        "track_id": track["track_id"],
    }
    raw = canonical_bytes(envelope)
    require(len(raw) == track["frame_bytes"], "E_ORACLE_FRAME_LENGTH", track["track_id"])
    require(sha256(raw) == track["frame_sha256"], "E_ORACLE_FRAME_HASH", track["track_id"])
    return raw


def expected_message(track: Mapping[str, Any], frame: bytes) -> bytes:
    domain = track["signature_domain"].encode("ascii")
    message = len(domain).to_bytes(8, "big") + domain + len(frame).to_bytes(8, "big") + frame
    require(len(message) == track["message_bytes"], "E_ORACLE_MESSAGE_LENGTH", track["track_id"])
    require(sha256(message) == track["message_sha256"], "E_ORACLE_MESSAGE_SHA256", track["track_id"])
    require(hashlib.sha512(message).hexdigest() == track["message_sha512"], "E_ORACLE_MESSAGE_SHA512", track["track_id"])
    return message


def expected_policy() -> dict[str, Any]:
    tracks: list[dict[str, Any]] = []
    for track in TRACKS:
        tracks.append(
            {
                "active_leaf_state": ACTIVE_STATE,
                "canonical_frame_sha256": track["frame_sha256"],
                "chain": [copy.deepcopy(track[name]) for name in ("root", "issuer", "leaf")],
                "frozen_snapshot_is_currentness": False,
                "message_sha256": track["message_sha256"],
                "message_sha512": track["message_sha512"],
                "policy_revision": track["policy_revision"],
                "revocation_snapshot_revision": track["revocation_revision"],
                "revoked_leaf": {
                    "key_id": track["leaf"]["key_id"],
                    "key_version": track["revoked_leaf_version"],
                    "state": REVOKED_STATE,
                },
                "signature_domain": track["signature_domain"],
                "track_id": track["track_id"],
                "vector_set_id": track["vector_set_id"],
            }
        )
    return {
        "algorithm": "ED25519",
        "declared_role_mapping": {
            "generic_declared_role_class": DECLARED_ROLE,
            "mapping_is_role_scope_authorization": False,
            "track_role_map": {track["track_id"]: track["leaf"]["role"] for track in TRACKS},
        },
        "message_profile": MESSAGE_PROFILE,
        "schema": TRUST_POLICY_SCHEMA,
        "schema_version": 1,
        "signature_scheme": SIGNATURE_SCHEME,
        "tracks": tracks,
        "trust_domain_family": TRUST_DOMAIN_FAMILY,
    }


def expected_bundle(track: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "declared_role": DECLARED_ROLE,
        "policy_revision": track["policy_revision"],
        "revocation_snapshot_revision": track["revocation_revision"],
        "schema": BUNDLE_SCHEMA,
        "schema_version": 1,
        "signature_hex": track["signature_hex"],
        "signer_key_id": track["leaf"]["key_id"],
        "signer_key_version": track["leaf"]["key_version"],
        "track_id": track["track_id"],
        "vector_set_id": track["vector_set_id"],
    }


# Independent strict Ed25519 verifier used only as a public-vector oracle.
_Q = 2**255 - 19
_L = 2**252 + 27742317777372353535851937790883648493


def _oracle_inv(value: int) -> int:
    return pow(value, _Q - 2, _Q)


_D = (-121665 * _oracle_inv(121666)) % _Q
_I = pow(2, (_Q - 1) // 4, _Q)


def _oracle_xrecover(y: int) -> int:
    xx = (y * y - 1) * _oracle_inv(_D * y * y + 1) % _Q
    x = pow(xx, (_Q + 3) // 8, _Q)
    if (x * x - xx) % _Q:
        x = x * _I % _Q
    require((x * x - xx) % _Q == 0, "E_ORACLE_POINT_OFF_CURVE", "sqrt")
    return _Q - x if x & 1 else x


_BY = 4 * _oracle_inv(5) % _Q
_B = (_oracle_xrecover(_BY), _BY)
_IDENTITY = (0, 1)


def _oracle_add(left: tuple[int, int], right: tuple[int, int]) -> tuple[int, int]:
    x1, y1 = left
    x2, y2 = right
    product = _D * x1 * x2 * y1 * y2 % _Q
    return (
        (x1 * y2 + x2 * y1) * _oracle_inv(1 + product) % _Q,
        (y1 * y2 + x1 * x2) * _oracle_inv(1 - product) % _Q,
    )


def _oracle_mult(point: tuple[int, int], scalar: int) -> tuple[int, int]:
    result = _IDENTITY
    addend = point
    while scalar:
        if scalar & 1:
            result = _oracle_add(result, addend)
        addend = _oracle_add(addend, addend)
        scalar >>= 1
    return result


def _oracle_point(raw: bytes) -> tuple[int, int]:
    require(len(raw) == 32, "E_ORACLE_POINT_LENGTH", str(len(raw)))
    encoded = int.from_bytes(raw, "little")
    y = encoded & ((1 << 255) - 1)
    sign = encoded >> 255
    require(y < _Q, "E_ORACLE_POINT_Y", raw.hex())
    x = _oracle_xrecover(y)
    require(not (x == 0 and sign == 1), "E_ORACLE_POINT_NEGATIVE_ZERO", raw.hex())
    if (x & 1) != sign:
        x = _Q - x
    point = (x, y)
    require(point != _IDENTITY, "E_ORACLE_POINT_IDENTITY", raw.hex())
    require(_oracle_mult(point, _L) == _IDENTITY, "E_ORACLE_POINT_SUBGROUP", raw.hex())
    return point


def independent_verify(signature: bytes, message: bytes, public_key: bytes) -> bool:
    if len(signature) != 64 or len(public_key) != 32:
        return False
    try:
        point_a = _oracle_point(public_key)
        point_r = _oracle_point(signature[:32])
    except CheckError:
        return False
    scalar_s = int.from_bytes(signature[32:], "little")
    if scalar_s >= _L:
        return False
    challenge = int.from_bytes(
        hashlib.sha512(signature[:32] + public_key + message).digest(), "little"
    ) % _L
    return _oracle_mult(_B, scalar_s) == _oracle_add(point_r, _oracle_mult(point_a, challenge))


def expected_receipt(
    track: Mapping[str, Any], frame: bytes, bundle_raw: bytes, policy_raw: bytes
) -> dict[str, Any]:
    receipt: dict[str, Any] = {
        "active_leaf_key_id": track["leaf"]["key_id"],
        "active_leaf_key_version": track["leaf"]["key_version"],
        "active_leaf_state": ACTIVE_STATE,
        "algorithm": "ED25519",
        "authentication_metadata_detached": True,
        "boundary_threat_specifications_locally_kat_covered": 5,
        "canonical_frame_sha256": track["frame_sha256"],
        "certificate_link_signature_verification_count": 0,
        "chain_entry_count": 3,
        "component_state": COMPONENT_STATE,
        "condition_output_authorized": False,
        "content_sha256": "0" * 64,
        "declared_role": DECLARED_ROLE,
        "declared_role_cryptographically_authenticated_in_kat": True,
        "declared_role_is_role_scope_authorization": False,
        "declared_role_mapping_verified": True,
        "detached_authentication_bundle_sha256": sha256(bundle_raw),
        "downstream_gate_count": 4,
        "downstream_gates_authorized": 0,
        "evidence_acceptance_authorized": False,
        "execution_mode": SYNTHETIC_MODE,
        "fault_injection_authorized": False,
        "frame_bytes": len(frame),
        "frame_sha256": sha256(frame),
        "frozen_revocation_snapshot_is_currentness": False,
        "isolated_lab_candidate_surface_component_total": 3,
        "isolated_lab_candidate_surface_components_locally_kat_exercised": 3,
        "isolated_lab_candidate_surface_components_implemented": 3,
        "issuer_key_id": track["issuer"]["key_id"],
        "issuer_key_version": track["issuer"]["key_version"],
        "local_t05_specification_exercised": True,
        "local_t06_specification_exercised": False,
        "local_t07_specification_exercised": False,
        "local_threat_specifications_covered": 5,
        "mapped_policy_leaf_role": track["leaf"]["role"],
        "message_bytes": track["message_bytes"],
        "message_profile": MESSAGE_PROFILE,
        "message_sha256": track["message_sha256"],
        "message_sha512": track["message_sha512"],
        "policy_revision": track["policy_revision"],
        "policy_track_count": 2,
        "policy_structural_chain_entry_count": 6,
        "policy_role_map_entry_count": 2,
        "policy_root_count": 2,
        "predecessor_frame_review_count": 1,
        "predecessor_receipt_content_sha256": track["predecessor_receipt_sha256"],
        "production_admissible": False,
        "production_ingestion_control_count": 14,
        "production_ingestion_controls_implemented": 0,
        "production_ingestion_controls_runtime_exercised": 0,
        "production_threat_specification_count": 20,
        "production_threat_specifications_runtime_exercised": 0,
        "production_validated_evidence_items": 0,
        "provider_authority": False,
        "public_vector_bundle_sha256": PUBLIC_VECTOR_BUNDLE_SHA256,
        "public_key_count": 6,
        "real_evidence_items_present": 0,
        "revocation_snapshot_revision": track["revocation_revision"],
        "revoked_leaf_key_id": track["leaf"]["key_id"],
        "revoked_leaf_key_version": track["revoked_leaf_version"],
        "revoked_leaf_state": REVOKED_STATE,
        "role_scope_authorization_implemented": False,
        "root_key_id": track["root"]["key_id"],
        "root_key_version": track["root"]["key_version"],
        "runtime_authority": False,
        "runtime_prerequisite_count": 16,
        "runtime_prerequisites_satisfied": 0,
        "schema": RECEIPT_SCHEMA,
        "schema_version": 1,
        "selected_revocation_entry_count": 2,
        "separately_injected_trust_policy": True,
        "side_effects_unlocked": "NONE",
        "signature_domain": track["signature_domain"],
        "signature_scheme": SIGNATURE_SCHEME,
        "signature_verification_count": 1,
        "strict_signature_r_point_validation_count": 1,
        "signer_role_scope_authorization_implemented": False,
        "status": SUBJECT_STATUS,
        "strict_public_key_point_validation_count": 6,
        "synthetic_fixture": True,
        "threat_case_count": 20,
        "track_id": track["track_id"],
        "track_leaf_role": track["leaf"]["role"],
        "track_subject_binding_implemented": False,
        "trust_policy_sha256": sha256(policy_raw),
        "trust_root_count": 2,
        "vector_set_id": track["vector_set_id"],
    }
    unsigned = dict(receipt)
    del unsigned["content_sha256"]
    receipt["content_sha256"] = domain_sha256(RECEIPT_DOMAIN, unsigned)
    return receipt


class ObservationBomb:
    """Object that records and aborts every observation except count access."""

    def __init__(self, label: str) -> None:
        object.__setattr__(self, "_label", label)
        object.__setattr__(self, "_events", [])

    @property
    def event_count(self) -> int:
        return len(object.__getattribute__(self, "_events"))

    def _explode(self, operation: str) -> NoReturn:
        events = object.__getattribute__(self, "_events")
        label = object.__getattribute__(self, "_label")
        events.append(operation)
        raise AssertionError(f"observation bomb {label}: {operation}")

    def __getattribute__(self, name: str) -> Any:
        if name in {"_label", "_events", "event_count", "_explode", "__class__"}:
            return object.__getattribute__(self, name)
        return object.__getattribute__(self, "_explode")(f"getattr:{name}")

    def __bytes__(self) -> bytes:
        self._explode("bytes")

    def __len__(self) -> int:
        self._explode("len")

    def __iter__(self) -> Any:
        self._explode("iter")

    def __bool__(self) -> bool:
        self._explode("bool")

    def __str__(self) -> str:
        self._explode("str")

    def __repr__(self) -> str:
        self._explode("repr")

    def __eq__(self, other: object) -> bool:
        self._explode("eq")


class HostileStringSubclass(str):
    """A str subclass whose comparisons must not run."""

    events: list[str] = []

    def __eq__(self, other: object) -> bool:
        type(self).events.append("eq")
        raise AssertionError("str subclass was compared")

    def __ne__(self, other: object) -> bool:
        type(self).events.append("ne")
        raise AssertionError("str subclass was compared")

    __hash__ = str.__hash__


def expect_rejection(
    module: ModuleType,
    frame: Any,
    bundle: Any,
    policy: Any,
    mode: Any,
    expected_code: str,
    label: str,
    expected_detail_code: str | None = None,
) -> None:
    try:
        module.review_bootstrap_trust_authentication(frame, bundle, policy, mode)
    except module.BootstrapTrustReviewError as error:
        require(error.code == expected_code, "E_REJECTION_CODE", f"{label}: {error.code}")
        if expected_detail_code is not None:
            require(
                error.detail_code == expected_detail_code,
                "E_REJECTION_DETAIL_CODE",
                f"{label}: {error.detail_code}",
            )
    else:
        raise CheckError(f"E_MUTATION_ACCEPTED: {label}")


def check_pre_observation_modes(module: ModuleType) -> int:
    modes: tuple[tuple[str, Any, str], ...] = (
        ("production", PRODUCTION_MODE, "E_BOOTSTRAP_TRUST_PRODUCTION_MODE_NOT_AUTHORIZED"),
        ("unknown_string", "SYNTHETIC", "E_BOOTSTRAP_TRUST_MODE_UNKNOWN"),
        ("unknown_integer", 7, "E_BOOTSTRAP_TRUST_MODE_UNKNOWN"),
        ("str_subclass", HostileStringSubclass(SYNTHETIC_MODE), "E_BOOTSTRAP_TRUST_MODE_UNKNOWN"),
    )
    for label, mode, code in modes:
        HostileStringSubclass.events.clear()
        bombs = tuple(ObservationBomb(f"{label}-{name}") for name in ("frame", "bundle", "policy"))
        expect_rejection(module, bombs[0], bombs[1], bombs[2], mode, code, label)
        require(all(bomb.event_count == 0 for bomb in bombs), "E_MODE_OBSERVED_INPUT", label)
        require(not HostileStringSubclass.events, "E_MODE_COMPARED_STR_SUBCLASS", label)
    return len(modes)


def check_predecessor_order(module: ModuleType, frame: bytes, bundle: bytes, policy: bytes) -> int:
    bundle_bomb = ObservationBomb("invalid-frame-bundle")
    policy_bomb = ObservationBomb("invalid-frame-policy")
    expect_rejection(
        module,
        b"{}",
        bundle_bomb,
        policy_bomb,
        SYNTHETIC_MODE,
        "E_PREDECESSOR_FRAME_REJECTED",
        "predecessor_before_policy_and_bundle",
    )
    require(bundle_bomb.event_count == policy_bomb.event_count == 0, "E_PREDECESSOR_ORDER", "other inputs observed")

    bundle_bomb = ObservationBomb("invalid-policy-bundle")
    expect_rejection(
        module,
        frame,
        bundle_bomb,
        b"{}",
        SYNTHETIC_MODE,
        "E_TRUST_POLICY_REJECTED",
        "policy_before_bundle",
    )
    require(bundle_bomb.event_count == 0, "E_POLICY_ORDER", "bundle observed before policy accepted")
    return 2


def _mutated(value: dict[str, Any], operation: Callable[[dict[str, Any]], None]) -> bytes:
    result = copy.deepcopy(value)
    operation(result)
    return canonical_bytes(result)


def directed_mutations(
    module: ModuleType,
    frames: list[bytes],
    bundles: list[bytes],
    policy_raw: bytes,
) -> dict[str, int]:
    policy = expected_policy()
    managed_bundle = expected_bundle(TRACKS[0])
    self_bundle = expected_bundle(TRACKS[1])
    cases: list[tuple[str, str, Any, Any, Any, str, str | None]] = []

    def add(
        category: str,
        name: str,
        *,
        frame: Any = frames[0],
        bundle: Any = bundles[0],
        policy_bytes: Any = policy_raw,
        code: str = "E_TRUST_POLICY_REJECTED",
        detail: str | None = None,
    ) -> None:
        cases.append((category, name, frame, bundle, policy_bytes, code, detail))

    # Decoder/canonicalization cases are deliberately raw rather than object mutations.
    add("json", "policy_nonbytes", policy_bytes="{}", detail="E_TRUST_POLICY_TYPE")
    add("json", "policy_empty", policy_bytes=b"", detail="E_TRUST_POLICY_SIZE")
    add("json", "policy_oversize", policy_bytes=b"x" * 65_537, detail="E_TRUST_POLICY_SIZE")
    add("json", "policy_invalid_utf8", policy_bytes=b"\xff", detail="E_TRUST_POLICY_UTF8")
    add("json", "policy_root_array", policy_bytes=b"[]", detail="E_TRUST_POLICY_ROOT")
    add("json", "policy_duplicate_key", policy_bytes=b'{"algorithm":"ED25519",' + policy_raw[1:], detail="E_JSON_DUPLICATE_KEY")
    add("json", "policy_float", policy_bytes=policy_raw.replace(b'"schema_version":1', b'"schema_version":1.0'), detail="E_JSON_FLOAT")
    add("json", "policy_nonfinite", policy_bytes=policy_raw.replace(b'"schema_version":1', b'"schema_version":NaN'), detail="E_JSON_NONFINITE")
    add("json", "policy_int_overflow", policy_bytes=policy_raw.replace(b'"schema_version":1', b'"schema_version":9223372036854775808'), detail="E_JSON_INT_RANGE")
    add("json", "policy_leading_whitespace", policy_bytes=b" " + policy_raw, detail="E_TRUST_POLICY_JSON")
    add("json", "policy_trailing_lf", policy_bytes=policy_raw + b"\n", detail="E_TRUST_POLICY_TRAILING")
    add("json", "policy_second_value", policy_bytes=policy_raw + b"{}", detail="E_TRUST_POLICY_TRAILING")
    add("json", "policy_pretty", policy_bytes=json.dumps(policy, sort_keys=True, indent=2).encode(), detail="E_TRUST_POLICY_NONCANONICAL")
    add("json", "policy_bom", policy_bytes=b"\xef\xbb\xbf" + policy_raw)
    add("json", "policy_unicode_escape", policy_bytes=policy_raw.replace(b"ED25519", b"ED\\u003235519", 1), detail="E_TRUST_POLICY_NONCANONICAL")
    reversed_policy = dict(reversed(list(policy.items())))
    add("json", "policy_key_order", policy_bytes=json.dumps(reversed_policy, separators=(",", ":")).encode(), detail="E_TRUST_POLICY_NONCANONICAL")
    deep_policy = copy.deepcopy(policy)
    nested: Any = "ED25519"
    for _ in range(33):
        nested = [nested]
    deep_policy["algorithm"] = nested
    add("json", "policy_depth", policy_bytes=canonical_bytes(deep_policy), detail="E_JSON_DEPTH")
    wide_policy = {f"k{index:03d}": index for index in range(257)}
    add("json", "policy_object_members", policy_bytes=canonical_bytes(wide_policy), detail="E_JSON_OBJECT_MEMBERS")
    array_policy = copy.deepcopy(policy)
    array_policy["tracks"] = [None] * 65
    add("json", "policy_array_items", policy_bytes=canonical_bytes(array_policy), detail="E_JSON_ARRAY_ITEMS")
    node_policy = copy.deepcopy(policy)
    node_policy["algorithm"] = [[0] * 64 for _ in range(64)]
    add("json", "policy_nodes", policy_bytes=canonical_bytes(node_policy), detail="E_JSON_NODES")
    add("json", "bundle_nonbytes", bundle="{}", code="E_AUTHENTICATION_REJECTED", detail="E_AUTHENTICATION_BUNDLE_TYPE")
    add("json", "bundle_empty", bundle=b"", code="E_AUTHENTICATION_REJECTED", detail="E_AUTHENTICATION_BUNDLE_SIZE")
    add("json", "bundle_invalid_utf8", bundle=b"\xff", code="E_AUTHENTICATION_REJECTED", detail="E_AUTHENTICATION_BUNDLE_UTF8")
    add("json", "bundle_duplicate", bundle=b'{"declared_role":"x",' + bundles[0][1:], code="E_AUTHENTICATION_REJECTED", detail="E_JSON_DUPLICATE_KEY")
    add("json", "bundle_trailing", bundle=bundles[0] + b"\n", code="E_AUTHENTICATION_REJECTED", detail="E_AUTHENTICATION_BUNDLE_TRAILING")
    add("json", "bundle_pretty", bundle=json.dumps(managed_bundle, sort_keys=True, indent=2).encode(), code="E_AUTHENTICATION_REJECTED", detail="E_AUTHENTICATION_BUNDLE_NONCANONICAL")

    policy_ops: list[tuple[str, Callable[[dict[str, Any]], None]]] = [
        ("top_missing_algorithm", lambda p: p.pop("algorithm")),
        ("top_extra", lambda p: p.__setitem__("extra", False)),
        ("algorithm", lambda p: p.__setitem__("algorithm", "ED448")),
        ("message_profile", lambda p: p.__setitem__("message_profile", "PARSE_RESERIALIZE")),
        ("schema", lambda p: p.__setitem__("schema", p["schema"] + ".drift")),
        ("schema_version_bool", lambda p: p.__setitem__("schema_version", True)),
        ("schema_version_two", lambda p: p.__setitem__("schema_version", 2)),
        ("signature_scheme", lambda p: p.__setitem__("signature_scheme", "ED25519PH")),
        ("trust_domain_family", lambda p: p.__setitem__("trust_domain_family", "OTHER")),
        ("role_mapping_not_object", lambda p: p.__setitem__("declared_role_mapping", [])),
        ("role_mapping_missing", lambda p: p["declared_role_mapping"].pop("track_role_map")),
        ("generic_role", lambda p: p["declared_role_mapping"].__setitem__("generic_declared_role_class", "ADMIN")),
        ("role_mapping_authorizes", lambda p: p["declared_role_mapping"].__setitem__("mapping_is_role_scope_authorization", True)),
        ("role_map_missing_track", lambda p: p["declared_role_mapping"]["track_role_map"].pop(TRACKS[1]["track_id"])),
        ("role_map_wrong_leaf", lambda p: p["declared_role_mapping"]["track_role_map"].__setitem__(TRACKS[0]["track_id"], TRACKS[0]["issuer"]["role"])),
        ("tracks_not_array", lambda p: p.__setitem__("tracks", {})),
        ("tracks_one", lambda p: p.__setitem__("tracks", p["tracks"][:1])),
        ("tracks_reversed", lambda p: p["tracks"].reverse()),
        ("track_not_object", lambda p: p["tracks"].__setitem__(0, [])),
        ("track_extra", lambda p: p["tracks"][0].__setitem__("extra", False)),
        ("active_state", lambda p: p["tracks"][0].__setitem__("active_leaf_state", REVOKED_STATE)),
        ("canonical_frame_hash", lambda p: p["tracks"][0].__setitem__("canonical_frame_sha256", "0" * 64)),
        ("currentness_true", lambda p: p["tracks"][0].__setitem__("frozen_snapshot_is_currentness", True)),
        ("message_sha256", lambda p: p["tracks"][0].__setitem__("message_sha256", "0" * 64)),
        ("message_sha512", lambda p: p["tracks"][0].__setitem__("message_sha512", "0" * 128)),
        ("policy_revision", lambda p: p["tracks"][0].__setitem__("policy_revision", "LATEST")),
        ("revocation_revision", lambda p: p["tracks"][0].__setitem__("revocation_snapshot_revision", "LATEST")),
        ("signature_domain", lambda p: p["tracks"][0].__setitem__("signature_domain", TRACKS[1]["signature_domain"])),
        ("track_id", lambda p: p["tracks"][0].__setitem__("track_id", TRACKS[1]["track_id"])),
        ("vector_set", lambda p: p["tracks"][0].__setitem__("vector_set_id", "LATEST")),
        ("chain_not_array", lambda p: p["tracks"][0].__setitem__("chain", {})),
        ("chain_short", lambda p: p["tracks"][0].__setitem__("chain", p["tracks"][0]["chain"][:2])),
        ("chain_order", lambda p: p["tracks"][0]["chain"].reverse()),
        ("chain_entry_not_object", lambda p: p["tracks"][0]["chain"].__setitem__(0, [])),
        ("chain_entry_extra", lambda p: p["tracks"][0]["chain"][0].__setitem__("state", ACTIVE_STATE)),
        ("root_key_id", lambda p: p["tracks"][0]["chain"][0].__setitem__("key_id", "OTHER")),
        ("root_key_version_latest", lambda p: p["tracks"][0]["chain"][0].__setitem__("key_version", "LATEST")),
        ("root_key_version_zero", lambda p: p["tracks"][0]["chain"][0].__setitem__("key_version", "0")),
        ("root_role", lambda p: p["tracks"][0]["chain"][0].__setitem__("role", TRACKS[0]["leaf"]["role"])),
        ("root_key_uppercase", lambda p: p["tracks"][0]["chain"][0].__setitem__("public_key_hex", p["tracks"][0]["chain"][0]["public_key_hex"].upper())),
        ("root_key_short", lambda p: p["tracks"][0]["chain"][0].__setitem__("public_key_hex", "00")),
        ("root_key_nonhex", lambda p: p["tracks"][0]["chain"][0].__setitem__("public_key_hex", "g" * 64)),
        ("root_key_other_pinned", lambda p: p["tracks"][0]["chain"][0].__setitem__("public_key_hex", TRACKS[1]["root"]["public_key_hex"])),
        ("issuer_key_substitution", lambda p: p["tracks"][0]["chain"][1].__setitem__("public_key_hex", TRACKS[0]["root"]["public_key_hex"])),
        ("leaf_key_substitution", lambda p: p["tracks"][0]["chain"][2].__setitem__("public_key_hex", TRACKS[0]["issuer"]["public_key_hex"])),
        ("identity_point", lambda p: p["tracks"][0]["chain"][0].__setitem__("public_key_hex", (b"\x01" + b"\0" * 31).hex())),
        ("negative_zero_point", lambda p: p["tracks"][0]["chain"][0].__setitem__("public_key_hex", ((1 | (1 << 255)).to_bytes(32, "little")).hex())),
        ("noncanonical_y_point", lambda p: p["tracks"][0]["chain"][0].__setitem__("public_key_hex", (_Q.to_bytes(32, "little")).hex())),
        ("small_order_point", lambda p: p["tracks"][0]["chain"][0].__setitem__("public_key_hex", "00" * 32)),
        ("revoked_not_object", lambda p: p["tracks"][0].__setitem__("revoked_leaf", [])),
        ("revoked_missing", lambda p: p["tracks"][0]["revoked_leaf"].pop("state")),
        ("revoked_key_id", lambda p: p["tracks"][0]["revoked_leaf"].__setitem__("key_id", TRACKS[0]["root"]["key_id"])),
        ("revoked_version_active", lambda p: p["tracks"][0]["revoked_leaf"].__setitem__("key_version", TRACKS[0]["leaf"]["key_version"])),
        ("revoked_version_latest", lambda p: p["tracks"][0]["revoked_leaf"].__setitem__("key_version", "LATEST")),
        ("revoked_state_active", lambda p: p["tracks"][0]["revoked_leaf"].__setitem__("state", ACTIVE_STATE)),
    ]
    for name, operation in policy_ops:
        add("policy", name, policy_bytes=_mutated(policy, operation))

    off_curve_point = b"\x02" + b"\0" * 31
    try:
        _oracle_point(off_curve_point)
    except CheckError as error:
        require(
            str(error).startswith("E_ORACLE_POINT_OFF_CURVE:"),
            "E_OFF_CURVE_ORACLE_CLASSIFICATION",
            str(error),
        )
    else:
        raise CheckError("E_OFF_CURVE_ORACLE_ACCEPTED: deterministic point")
    off_curve_policy = copy.deepcopy(policy)
    off_curve_policy["tracks"][0]["chain"][0]["public_key_hex"] = off_curve_point.hex()
    add(
        "policy",
        "off_curve_point",
        policy_bytes=canonical_bytes(off_curve_policy),
        detail="E_ED25519_POINT_OFF_CURVE",
    )

    bundle_ops: list[tuple[str, Callable[[dict[str, Any]], None]]] = [
        ("missing_field", lambda b: b.pop("declared_role")),
        ("embedded_public_key", lambda b: b.__setitem__("public_key_hex", TRACKS[0]["leaf"]["public_key_hex"])),
        ("schema", lambda b: b.__setitem__("schema", b["schema"] + ".drift")),
        ("schema_version_bool", lambda b: b.__setitem__("schema_version", True)),
        ("unknown_track", lambda b: b.__setitem__("track_id", "UNKNOWN")),
        ("declared_role", lambda b: b.__setitem__("declared_role", "ADMIN")),
        ("policy_revision", lambda b: b.__setitem__("policy_revision", "LATEST")),
        ("revocation_revision", lambda b: b.__setitem__("revocation_snapshot_revision", "LATEST")),
        ("signer_root_id", lambda b: b.__setitem__("signer_key_id", TRACKS[0]["root"]["key_id"])),
        ("signer_revoked_version", lambda b: b.__setitem__("signer_key_version", TRACKS[0]["revoked_leaf_version"])),
        ("signer_latest_version", lambda b: b.__setitem__("signer_key_version", "LATEST")),
        ("signer_zero_version", lambda b: b.__setitem__("signer_key_version", "0")),
        ("vector_set", lambda b: b.__setitem__("vector_set_id", "LATEST")),
        ("signature_uppercase", lambda b: b.__setitem__("signature_hex", b["signature_hex"].upper())),
        ("signature_short", lambda b: b.__setitem__("signature_hex", "00")),
        ("signature_nonhex", lambda b: b.__setitem__("signature_hex", "g" * 128)),
        ("signature_bitflip", lambda b: b.__setitem__("signature_hex", ("0" if b["signature_hex"][0] != "0" else "1") + b["signature_hex"][1:])),
        ("signature_cross_track", lambda b: b.__setitem__("signature_hex", TRACKS[1]["signature_hex"])),
        ("signature_r_identity", lambda b: b.__setitem__("signature_hex", (b"\x01" + b"\0" * 31).hex() + b["signature_hex"][64:])),
        ("signature_r_negative_zero", lambda b: b.__setitem__("signature_hex", ((1 | (1 << 255)).to_bytes(32, "little")).hex() + b["signature_hex"][64:])),
        ("signature_s_equal_l", lambda b: b.__setitem__("signature_hex", b["signature_hex"][:64] + _L.to_bytes(32, "little").hex())),
    ]
    for name, operation in bundle_ops:
        add(
            "bundle",
            name,
            bundle=_mutated(managed_bundle, operation),
            code="E_AUTHENTICATION_REJECTED",
        )

    add("bundle", "managed_frame_self_bundle", bundle=bundles[1], code="E_AUTHENTICATION_REJECTED", detail="E_AUTHENTICATION_BUNDLE_POLICY_REVISION")
    add("bundle", "self_frame_managed_bundle", frame=frames[1], code="E_AUTHENTICATION_REJECTED", detail="E_AUTHENTICATION_BUNDLE_POLICY_REVISION")
    cross_bundle = copy.deepcopy(self_bundle)
    cross_bundle["signature_hex"] = TRACKS[0]["signature_hex"]
    add("bundle", "self_metadata_managed_signature", frame=frames[1], bundle=canonical_bytes(cross_bundle), code="E_AUTHENTICATION_REJECTED")

    add("frame", "frame_nonbytes", frame="{}", code="E_PREDECESSOR_FRAME_REJECTED")
    add("frame", "frame_bytearray", frame=bytearray(frames[0]), code="E_PREDECESSOR_FRAME_REJECTED")
    add("frame", "frame_one_byte_flip", frame=frames[0][:-1] + b"!", code="E_PREDECESSOR_FRAME_REJECTED")
    add("frame", "frame_trailing_lf", frame=frames[0] + b"\n", code="E_PREDECESSOR_FRAME_REJECTED")

    names = [f"{case[0]}:{case[1]}" for case in cases]
    require(len(names) == len(set(names)), "E_MUTATION_NAMES", "duplicate mutation name")
    counts = {"json": 0, "policy": 0, "bundle": 0, "frame": 0}
    for category, name, frame, bundle, policy_bytes, code, detail in cases:
        expect_rejection(
            module,
            frame,
            bundle,
            policy_bytes,
            SYNTHETIC_MODE,
            code,
            f"{category}:{name}",
            detail,
        )
        counts[category] += 1
    require(sum(counts.values()) >= 60, "E_MUTATION_COVERAGE", str(counts))
    return counts


def source_contract_checks() -> int:
    path = safe_source(SOURCE_REL)
    raw = path.read_bytes()
    require(not raw.startswith(b"\xef\xbb\xbf"), "E_SOURCE_BOM", SOURCE_REL)
    text = raw.decode("utf-8", "strict")
    tree = ast.parse(text, filename=str(path))
    checks = 0

    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module.split(".")[0])
    allowed_imports = {
        "__future__",
        "hashlib",
        "json",
        "re",
        "dataclasses",
        "typing",
        (
            "biocortex_ab_track_b_reference_provider_fault_injection_runner_"
            "production_evidence_envelope_bounded_frame_parser_and_synthetic_"
            "mode_separation_isolated_lab_v1"
        ),
    }
    require(imports == allowed_imports, "E_SOURCE_FORBIDDEN_IMPORT", str(sorted(imports)))
    checks += 1

    public_functions = [
        node for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name == "review_bootstrap_trust_authentication"
    ]
    require(len(public_functions) == 1, "E_SOURCE_PUBLIC_FUNCTION", str(len(public_functions)))
    public = public_functions[0]
    assert isinstance(public, ast.FunctionDef)
    args = public.args
    require(
        [arg.arg for arg in args.args] == [
            "frame", "detached_authentication_bundle",
            "separately_injected_synthetic_trust_policy", "mode",
        ]
        and not args.defaults and args.vararg is None and args.kwarg is None
        and not args.kwonlyargs and args.posonlyargs == [],
        "E_SOURCE_PUBLIC_SIGNATURE",
        ast.unparse(args),
    )
    checks += 1

    body = list(public.body)
    if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant) and type(body[0].value.value) is str:
        body = body[1:]
    require(body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Call), "E_SOURCE_FIRST_GUARD", "not call")
    first_call = body[0].value
    require(
        isinstance(first_call.func, ast.Name) and first_call.func.id == "_reject_mode"
        and len(first_call.args) == 1 and isinstance(first_call.args[0], ast.Name)
        and first_call.args[0].id == "mode" and not first_call.keywords,
        "E_SOURCE_FIRST_GUARD",
        ast.unparse(first_call),
    )
    checks += 1

    calls = [node for node in ast.walk(public) if isinstance(node, ast.Call)]
    verify_calls = [node for node in calls if isinstance(node.func, ast.Name) and node.func.id == "_verify"]
    leaf_unpack_assignments = [
        node for node in ast.walk(public)
        if isinstance(node, ast.Assign)
        and len(node.targets) == 1
        and isinstance(node.targets[0], ast.Tuple)
        and [element.id if isinstance(element, ast.Name) else None for element in node.targets[0].elts]
        == ["leaf_key", "leaf_point"]
    ]
    require(
        len(verify_calls) == 1
        and [ast.unparse(arg) for arg in verify_calls[0].args]
        == ["signature", "message", "leaf_key", "leaf_point"]
        and not verify_calls[0].keywords
        and len(leaf_unpack_assignments) == 1
        and ast.unparse(leaf_unpack_assignments[0].value)
        == "public_keys[selected_track_index * 3 + 2]",
        "E_SOURCE_VERIFY_CALL_COUNT",
        (
            f"calls={len(verify_calls)};"
            f"unpacks={len(leaf_unpack_assignments)};"
            f"call={ast.unparse(verify_calls[0]) if len(verify_calls) == 1 else 'INVALID'};"
            f"unpack={ast.unparse(leaf_unpack_assignments[0]) if len(leaf_unpack_assignments) == 1 else 'INVALID'}"
        ),
    )
    checks += 1
    predecessor_calls = [
        node for node in calls
        if isinstance(node.func, ast.Attribute) and node.func.attr == "review_frame"
        and isinstance(node.func.value, ast.Name) and node.func.value.id == "predecessor"
    ]
    policy_decode_calls = [
        node for node in calls
        if isinstance(node.func, ast.Name) and node.func.id == "_decode_closed_json"
        and any(keyword.arg == "label" and isinstance(keyword.value, ast.Constant)
                and keyword.value.value == "TRUST_POLICY" for keyword in node.keywords)
    ]
    bundle_decode_calls = [
        node for node in calls
        if isinstance(node.func, ast.Name) and node.func.id == "_decode_closed_json"
        and any(keyword.arg == "label" and isinstance(keyword.value, ast.Constant)
                and keyword.value.value == "AUTHENTICATION_BUNDLE" for keyword in node.keywords)
    ]
    require(
        len(predecessor_calls) == len(policy_decode_calls) == len(bundle_decode_calls) == 1
        and predecessor_calls[0].lineno < policy_decode_calls[0].lineno < bundle_decode_calls[0].lineno,
        "E_SOURCE_REVIEW_ORDER",
        "mode -> predecessor -> separate policy -> bundle",
    )
    checks += 1

    forbidden_name_calls = {
        "open", "input", "print", "exec", "eval", "compile", "__import__",
    }
    forbidden_attribute_calls = {
        "getenv", "urandom",
        "sign", "signing", "generate", "keygen", "connect", "request", "urlopen",
        "run", "Popen", "system", "sleep", "time", "now", "utcnow",
    }
    observed_forbidden: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name) and node.func.id in forbidden_name_calls:
                observed_forbidden.add(node.func.id)
            elif isinstance(node.func, ast.Attribute) and node.func.attr in forbidden_attribute_calls:
                observed_forbidden.add(node.func.attr)
    require(not observed_forbidden, "E_SOURCE_FORBIDDEN_CALL", str(sorted(observed_forbidden)))
    checks += 1
    mutable_module_bindings: list[str] = []
    mutable_nodes = (
        ast.Dict, ast.DictComp, ast.List, ast.ListComp, ast.Set, ast.SetComp,
    )
    mutable_constructor_names = {"bytearray", "dict", "list", "set"}
    mutable_or_cache_attributes = {"cache", "cached_property", "defaultdict", "deque", "lru_cache"}
    for node in tree.body:
        value: ast.expr | None = None
        targets: list[ast.expr] = []
        if isinstance(node, ast.Assign):
            value = node.value
            targets = list(node.targets)
        elif isinstance(node, ast.AnnAssign):
            value = node.value
            targets = [node.target]
        names = [target.id for target in targets if isinstance(target, ast.Name)]
        has_mutable_constructor = value is not None and any(
            isinstance(descendant, ast.Call)
            and (
                (
                    isinstance(descendant.func, ast.Name)
                    and descendant.func.id in mutable_constructor_names
                )
                or (
                    isinstance(descendant.func, ast.Attribute)
                    and descendant.func.attr in mutable_or_cache_attributes
                )
            )
            for descendant in ast.walk(value)
        )
        if isinstance(value, mutable_nodes) or has_mutable_constructor:
            mutable_module_bindings.extend(name for name in names if name != "__all__")
    require(
        not any(
            isinstance(
                node,
                (ast.Global, ast.Nonlocal, ast.AsyncFunctionDef, ast.Await, ast.Yield, ast.YieldFrom),
            )
            for node in ast.walk(tree)
        )
        and not mutable_module_bindings,
        "E_SOURCE_MUTABLE_OR_ASYNC",
        f"global/nonlocal/async/yield/mutable-module={mutable_module_bindings}",
    )
    checks += 1

    identifiers = {
        node.id for node in ast.walk(tree) if isinstance(node, ast.Name)
    } | {
        node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute)
    }
    forbidden_identifiers = {
        "cache", "cached_property", "defaultdict", "deque", "lru_cache",
        "memoize", "memoized",
        "private_key", "private_seed", "secret_key", "secret_seed", "credential",
        "credential_path", "provider_endpoint", "aws_access_key_id",
        "google_application_credentials",
    }
    require(not identifiers.intersection(forbidden_identifiers), "E_SOURCE_SECRET_OR_PROVIDER_IDENTIFIER", str(sorted(identifiers.intersection(forbidden_identifiers))))
    checks += 1

    reject_functions = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "_reject_mode"]
    require(len(reject_functions) == 1, "E_SOURCE_REJECT_MODE", str(len(reject_functions)))
    reject_text = ast.unparse(reject_functions[0])
    require("type(mode) is not str" in reject_text and "mode == PRODUCTION_MODE" in reject_text and "mode != SYNTHETIC_KAT_MODE" in reject_text, "E_SOURCE_REJECT_MODE_SHAPE", reject_text)
    checks += 1

    verify_functions = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "_verify"]
    require(len(verify_functions) == 1, "E_SOURCE_VERIFY_FUNCTION", str(len(verify_functions)))
    verify_text = ast.unparse(verify_functions[0])
    require("scalar_s >= _L" in verify_text and "_decodepoint(signature[:32])" in verify_text and "hashlib.sha512" in verify_text, "E_SOURCE_STRICT_VERIFY", verify_text)
    checks += 1

    policy_functions = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "_validate_policy"]
    require(len(policy_functions) == 1, "E_SOURCE_POLICY_FUNCTION", str(len(policy_functions)))
    policy_text = ast.unparse(policy_functions[0])
    require("len(public_keys) == 6" in policy_text and "len({key for key, _point in public_keys}) == 6" in policy_text, "E_SOURCE_SIX_POINTS", policy_text)
    checks += 1

    exports = next(
        (node for node in tree.body if isinstance(node, ast.Assign)
         and any(isinstance(target, ast.Name) and target.id == "__all__" for target in node.targets)),
        None,
    )
    require(exports is not None, "E_SOURCE_EXPORTS", "missing __all__")
    exports_value = ast.literal_eval(exports.value)
    require("review_bootstrap_trust_authentication" in exports_value and "known_answer_trust_policy_bytes" in exports_value, "E_SOURCE_EXPORTS", str(exports_value))
    checks += 1

    require(text.count("_verify(") == 2, "E_SOURCE_VERIFY_LEXICAL_COUNT", str(text.count("_verify(")))
    checks += 1
    require("mapping_is_role_scope_authorization\": False" in text or "mapping_is_role_scope_authorization\": False" in text, "E_SOURCE_ROLE_NONAUTH", "missing false role-scope mapping")
    checks += 1
    require("production_ingestion_controls_implemented\": 0" in text and "runtime_prerequisites_satisfied\": 0" in text, "E_SOURCE_ZERO_COUNTERS", "production/runtime counters")
    checks += 1
    return checks


def fixture_schema_checks() -> tuple[dict[str, Any], int]:
    fixture = read_artifact_json(FIXTURE_REL)
    schema = read_artifact_json(SCHEMA_REL)
    checks = 0
    fixture_keys = {
        "canonical_json_profile", "contains_private_or_seed_material", "date",
        "execution_mode", "expected_receipts", "public_only", "schema",
        "separately_injected_synthetic_trust_policy", "source_bindings", "valid_cases",
    }
    require(set(fixture) == fixture_keys, "E_FIXTURE_FIELDS", str(set(fixture) ^ fixture_keys))
    checks += 1
    require(
        fixture["canonical_json_profile"] == "SORTED_KEYS_COMPACT_UTF8_NO_TRAILING_BYTES"
        and fixture["contains_private_or_seed_material"] is False
        and fixture["date"] == DATE
        and fixture["execution_mode"] == SYNTHETIC_MODE
        and fixture["public_only"] is True
        and fixture["schema"] == FIXTURE_SCHEMA,
        "E_FIXTURE_IDENTITY",
        "top-level identity or nonclaim drift",
    )
    checks += 1
    require(
        exact_equal(fixture["separately_injected_synthetic_trust_policy"], expected_policy()),
        "E_FIXTURE_POLICY",
        "policy differs from independent oracle",
    )
    checks += 1

    expected_bindings = {
        "authority_integration_commit": "b4126a4192137e741e32ebb86170884b81185cbf",
        "predecessor_frame_fixture_path": (
            "scripts/eval/fixtures/biocortex_ab_track_b_reference_provider_fault_"
            "injection_runner_production_evidence_envelope_bounded_frame_parser_and_"
            "synthetic_mode_separation_isolated_lab_v1_pack_synthetic_v0.json"
        ),
        "predecessor_frame_fixture_sha256": "324379e6e4fcae9db3af3b55d9caacbcb77f56f6c57b110d0ced2987749910b9",
        "public_vector_bundle_bytes": 3784,
        "public_vector_bundle_path": (
            "scripts/eval/fixtures/biocortex_ab_track_b_bootstrap_trust_public_only_"
            "vector_supply_and_generation_provenance_receipt_freeze_v1_pack_public_"
            "vector_bundle_v0.json"
        ),
        "public_vector_bundle_sha256": PUBLIC_VECTOR_BUNDLE_SHA256,
        "public_vector_source_is_public_only": True,
        "public_vector_supply_integration_commit": "61585e655f7bfd537f8a123141e4e39a590a66d8",
    }
    require(exact_equal(fixture["source_bindings"], expected_bindings), "E_FIXTURE_SOURCE_BINDINGS", "binding drift")
    checks += 1
    predecessor_fixture = safe_source(expected_bindings["predecessor_frame_fixture_path"]).read_bytes()
    public_vectors = safe_source(expected_bindings["public_vector_bundle_path"]).read_bytes()
    require(
        sha256(predecessor_fixture) == expected_bindings["predecessor_frame_fixture_sha256"],
        "E_FIXTURE_PREDECESSOR_HASH",
        expected_bindings["predecessor_frame_fixture_path"],
    )
    require(
        len(public_vectors) == expected_bindings["public_vector_bundle_bytes"]
        and sha256(public_vectors) == expected_bindings["public_vector_bundle_sha256"],
        "E_FIXTURE_PUBLIC_VECTOR_HASH",
        expected_bindings["public_vector_bundle_path"],
    )
    checks += 2

    valid_cases = fixture["valid_cases"]
    require(type(valid_cases) is list and len(valid_cases) == 2, "E_FIXTURE_VALID_CASES", "exactly two")
    expected_case_ids = (
        "VALID_MANAGED_BOOTSTRAP_TRUST_AUTHENTICATION_V1",
        "VALID_SELF_HOSTED_BOOTSTRAP_TRUST_AUTHENTICATION_V1",
    )
    for index, (case, track) in enumerate(zip(valid_cases, TRACKS, strict=True)):
        require(
            type(case) is dict
            and set(case) == {"case_id", "detached_authentication_bundle", "frame_utf8", "track_id"},
            "E_FIXTURE_CASE_FIELDS",
            str(index),
        )
        require(
            case["case_id"] == expected_case_ids[index]
            and case["track_id"] == track["track_id"]
            and type(case["frame_utf8"]) is str
            and case["frame_utf8"].encode("utf-8") == expected_frame(track)
            and exact_equal(case["detached_authentication_bundle"], expected_bundle(track)),
            "E_FIXTURE_CASE",
            track["track_id"],
        )
    checks += 2
    require(
        type(fixture["expected_receipts"]) is list and len(fixture["expected_receipts"]) == 2,
        "E_FIXTURE_RECEIPTS",
        "exactly two",
    )
    checks += 1

    schema_top = {
        "$schema", "title", "description", "$comment", "type", "required",
        "properties", "additionalProperties", "unevaluatedProperties",
        "minProperties", "maxProperties", "$defs",
    }
    require(set(schema) == schema_top, "E_SCHEMA_FIELDS", str(set(schema) ^ schema_top))
    require(
        schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
        and schema["type"] == "object"
        and schema["additionalProperties"] is False
        and schema["unevaluatedProperties"] is False
        and schema["minProperties"] == schema["maxProperties"] == 10
        and set(schema["required"]) == fixture_keys
        and set(schema["properties"]) == fixture_keys,
        "E_SCHEMA_TOP_CONTRACT",
        "closed 10-field wrapper",
    )
    checks += 2
    require(
        schema["properties"]["schema"] == {"const": FIXTURE_SCHEMA}
        and schema["properties"]["date"] == {"const": DATE}
        and schema["properties"]["execution_mode"] == {"const": SYNTHETIC_MODE}
        and schema["properties"]["public_only"] == {"const": True}
        and schema["properties"]["contains_private_or_seed_material"] == {"const": False},
        "E_SCHEMA_TOP_CONSTANTS",
        "identity/nonclaim constants",
    )
    checks += 1
    expected_defs = {
        "sha256", "sha512", "trackId", "sourceBindings", "keyEntry", "revokedLeaf",
        "trustTrack", "trustPolicy", "detachedBundle", "validCase", "receipt",
    }
    definitions = schema["$defs"]
    require(type(definitions) is dict and set(definitions) == expected_defs, "E_SCHEMA_DEFS", str(set(definitions) ^ expected_defs))
    checks += 1
    expected_cardinality = {
        "sourceBindings": 8, "keyEntry": 4, "revokedLeaf": 3, "trustTrack": 12,
        "trustPolicy": 8, "detachedBundle": 10, "validCase": 4, "receipt": 87,
    }
    for name, cardinality in expected_cardinality.items():
        definition = definitions[name]
        require(
            definition["type"] == "object"
            and definition["additionalProperties"] is False
            and definition["unevaluatedProperties"] is False
            and definition["minProperties"] == definition["maxProperties"] == cardinality
            and len(definition["required"]) == cardinality
            and set(definition["required"]) == set(definition["properties"]),
            "E_SCHEMA_DEF_CLOSED",
            name,
        )
    checks += len(expected_cardinality)
    receipt_keys = set(fixture["expected_receipts"][0])
    require(
        len(receipt_keys) == 87
        and receipt_keys == set(definitions["receipt"]["required"])
        and set(fixture["expected_receipts"][1]) == receipt_keys,
        "E_SCHEMA_RECEIPT_FIELDS",
        "receipt schema/fixture mismatch",
    )
    checks += 1
    require(
        "never grants production" in schema["description"]
        and "exactly one active-leaf signature equation" in schema["$comment"],
        "E_SCHEMA_NONCLAIM",
        "description/comment",
    )
    checks += 1
    return fixture, checks


def positive_checks(
    module: ModuleType, fixture: Mapping[str, Any]
) -> tuple[list[bytes], list[bytes], bytes, list[dict[str, Any]]]:
    policy = expected_policy()
    policy_raw = canonical_bytes(policy)
    require(module.known_answer_trust_policy_bytes() == policy_raw, "E_POLICY_ORACLE", "subject helper differs")
    frames: list[bytes] = []
    bundles: list[bytes] = []
    receipts: list[dict[str, Any]] = []
    public_keys: list[bytes] = []
    for track in TRACKS:
        for name in ("root", "issuer", "leaf"):
            point_raw = bytes.fromhex(track[name]["public_key_hex"])
            _oracle_point(point_raw)
            public_keys.append(point_raw)
    require(len(public_keys) == len(set(public_keys)) == 6, "E_ORACLE_PUBLIC_KEYS", "six distinct strict points")

    for index, track in enumerate(TRACKS):
        frame = expected_frame(track)
        bundle_raw = canonical_bytes(expected_bundle(track))
        message = expected_message(track, frame)
        signature = bytes.fromhex(track["signature_hex"])
        public_key = bytes.fromhex(track["leaf"]["public_key_hex"])
        require(independent_verify(signature, message, public_key), "E_ORACLE_SIGNATURE", track["track_id"])
        subject = module.review_bootstrap_trust_authentication(frame, bundle_raw, policy_raw, SYNTHETIC_MODE)
        oracle = expected_receipt(track, frame, bundle_raw, policy_raw)
        require(exact_equal(subject, oracle), "E_POSITIVE_RECEIPT", track["track_id"])
        require(
            exact_equal(fixture["expected_receipts"][index], oracle),
            "E_FIXTURE_EXPECTED_RECEIPT",
            track["track_id"],
        )
        frames.append(frame)
        bundles.append(bundle_raw)
        receipts.append(oracle)
    return frames, bundles, policy_raw, receipts


def pack_receipt(
    frames: list[bytes],
    bundles: list[bytes],
    policy_raw: bytes,
    receipts: list[dict[str, Any]],
    mode_tests: int,
    order_tests: int,
    mutation_counts: Mapping[str, int],
    source_checks: int,
    fixture_schema_guard_count: int,
) -> dict[str, Any]:
    total_negative = mode_tests + order_tests + sum(mutation_counts.values())
    result: dict[str, Any] = {
        "schema": PACK_RECEIPT_SCHEMA,
        "status": STATUS,
        "decision": DECISION,
        "date": DATE,
        "mode": SYNTHETIC_MODE,
        "component_state": COMPONENT_STATE,
        "positive_track_count": 2,
        "positive_signature_equation_count": 2,
        "strict_public_point_count": 6,
        "strict_signature_r_point_count": 2,
        "public_mode_pre_observation_test_count": mode_tests,
        "predecessor_order_test_count": order_tests,
        "json_strictness_negative_test_count": mutation_counts["json"],
        "policy_negative_test_count": mutation_counts["policy"],
        "bundle_negative_test_count": mutation_counts["bundle"],
        "frame_binding_negative_test_count": mutation_counts["frame"],
        "total_directed_negative_test_count": total_negative,
        "source_ast_guard_count": source_checks,
        "fixture_schema_guard_count": fixture_schema_guard_count,
        "fixture_expected_receipt_count": 2,
        "isolated_lab_candidate_surface_component_total": 3,
        "isolated_lab_candidate_surface_components_implemented": 3,
        "local_threat_specifications_covered": 5,
        "production_ingestion_control_count": 14,
        "production_ingestion_controls_implemented": 0,
        "production_ingestion_controls_runtime_exercised": 0,
        "production_threat_specification_count": 20,
        "production_threat_specifications_runtime_exercised": 0,
        "runtime_prerequisite_count": 16,
        "runtime_prerequisites_satisfied": 0,
        "real_evidence_items_present": 0,
        "production_validated_evidence_items": 0,
        "runtime_authority": False,
        "provider_authority": False,
        "side_effects_unlocked": "NONE",
        "frame_set_sha256": domain_sha256(
            "AB_BOOTSTRAP_TRUST_FRAME_SET_V1", [sha256(frame) for frame in frames]
        ),
        "bundle_set_sha256": domain_sha256(
            "AB_BOOTSTRAP_TRUST_BUNDLE_SET_V1", [sha256(bundle) for bundle in bundles]
        ),
        "trust_policy_sha256": sha256(policy_raw),
        "receipt_set_sha256": domain_sha256("AB_BOOTSTRAP_TRUST_RECEIPT_SET_V1", receipts),
        "schema_raw_sha256": sha256(safe_source(SCHEMA_REL).read_bytes()),
        "fixture_raw_sha256": sha256(safe_source(FIXTURE_REL).read_bytes()),
        "source_raw_sha256": sha256(safe_source(SOURCE_REL).read_bytes()),
        "predecessor_source_raw_sha256": sha256(safe_source(PREDECESSOR_SOURCE_REL).read_bytes()),
        "content_sha256": "0" * 64,
    }
    require(set(result) == set(TSV_FIELDS), "E_PACK_RECEIPT_FIELDS", str(set(result) ^ set(TSV_FIELDS)))
    unsigned = dict(result)
    del unsigned["content_sha256"]
    result["content_sha256"] = domain_sha256(PACK_RECEIPT_DOMAIN, unsigned)
    return {field: result[field] for field in TSV_FIELDS}


def render_tsv(receipt: Mapping[str, Any]) -> str:
    def scalar(value: Any) -> str:
        if value is True:
            return "true"
        if value is False:
            return "false"
        require(type(value) in (str, int), "E_TSV_VALUE", repr(value))
        text = str(value)
        require("\t" not in text and "\n" not in text and "\r" not in text, "E_TSV_CONTROL", text)
        return text

    return "".join(f"{field}\t{scalar(receipt[field])}\n" for field in TSV_FIELDS)


def evaluate() -> tuple[str, dict[str, int]]:
    source_checks = source_contract_checks()
    fixture, fixture_schema_guard_count = fixture_schema_checks()
    module = load_module()
    frames, bundles, policy_raw, receipts = positive_checks(module, fixture)
    mode_tests = check_pre_observation_modes(module)
    order_tests = check_predecessor_order(module, frames[0], bundles[0], policy_raw)
    mutation_counts = directed_mutations(module, frames, bundles, policy_raw)
    receipt = pack_receipt(
        frames, bundles, policy_raw, receipts,
        mode_tests, order_tests, mutation_counts, source_checks,
        fixture_schema_guard_count,
    )
    counts = dict(mutation_counts)
    counts["mode"] = mode_tests
    counts["order"] = order_tests
    counts["source"] = source_checks
    counts["fixture_schema"] = fixture_schema_guard_count
    counts["total"] = mode_tests + order_tests + sum(mutation_counts.values())
    return render_tsv(receipt), counts


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--candidate", action="store_true", help="accepted for pack-gate symmetry")
    args = parser.parse_args()
    try:
        rendered, counts = evaluate()
        if args.self_test:
            print("self_test\tPASS")
            for key in ("json", "policy", "bundle", "frame", "mode", "order", "source", "fixture_schema", "total"):
                print(f"{key}_test_count\t{counts[key]}")
            print("independent_positive_signature_equations\t2")
            print("independent_strict_public_points\t6")
            print("source_ast_purity\tPASS")
        else:
            print(rendered, end="")
    except (CheckError, AssertionError, ValueError, TypeError, KeyError, OSError,
            SyntaxError, UnicodeError, RecursionError) as error:
        print(f"bootstrap-trust isolated-lab pack check failed: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
