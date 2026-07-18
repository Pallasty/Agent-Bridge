#!/usr/bin/env python3
"""Freeze and validate the public-only bootstrap-trust KAT vector supply.

This module has no key-generation, signing, provider, credential, or network
surface.  It accepts only the two public custodian outputs plus the already
frozen predecessor frame fixture, validates their closed-world contract, and
emits a deterministic public receipt.
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any


SCHEMA = (
    "agent_bridge.biocortex_ab_track_b.bootstrap_trust_public_only_vector_"
    "supply_and_generation_provenance_receipt_freeze.v1"
)
VECTOR_SCHEMA = (
    "agent_bridge.biocortex_ab_track_b.bootstrap_trust_public_only_vector_bundle.v1"
)
AUTHORITY_INTEGRATION_COMMIT = "b4126a4192137e741e32ebb86170884b81185cbf"
AUTHORITY_GATE_SHA256 = (
    "21c5aa21cebf7e37767a2ec0bcd38bd8b28839bd9b825c86e81920a2ce20aef0"
)
AUTHORITY_FULL_RECEIPT_SHA256 = (
    "a40e9a208209de3a24904dc0957515e11f247ee7e07c070ff2306f32e553d77f"
)
VECTOR_BUNDLE_RAW_SHA256 = (
    "a87e0883a42ca69fe3a0348b4ffe44c153882f8dcc93eb67db1ea048d53851d7"
)
GENERATION_RECEIPT_RAW_SHA256 = (
    "bdd85c98b7adfddf5eff5202984862c29b95f17b152a621198ac405d81ba1ee0"
)
GENERATOR_SOURCE_SHA256 = (
    "62a8e32eef9e9a5560cd6dacfce5a181761196cef18a77508eb8552c1e20f083"
)
FRAME_FIXTURE_RAW_SHA256 = (
    "324379e6e4fcae9db3af3b55d9caacbcb77f56f6c57b110d0ced2987749910b9"
)
GENERATOR_RUNTIME_PIN = (
    "rustc 1.96.0 (ac68faa20 2026-05-25); "
    "cargo 1.96.0 (30a34c682 2026-05-25); host x86_64-unknown-linux-gnu"
)
ALGORITHM = "ED25519"
SIGNATURE_SCHEME = "ED25519_PURE_RFC8032_NO_CONTEXT_NO_PREHASH"
MESSAGE_PROFILE = "U64BE_LENGTH_PREFIXED_ASCII_DOMAIN_AND_EXACT_RAW_CANONICAL_FRAME"
CONSUMPTION_EVENT = "FIXTURE_CUSTODIAN_PROCESS_STARTED_BEFORE_RANDOMNESS_OR_KEYGEN"
AUTHORITY_STATE_BEFORE_ENTRY = "AUTHORIZED_ONE_SHOT_FIXTURE_CUSTODIAN_PENDING_PROCESS_START"
CONSUMED_STATE = "CONSUMED_SCOPE_COMPLETE_PUBLIC_OUTPUT_AVAILABLE"
NEXT_UNIT = (
    "REFERENCE_PROVIDER_MANAGED_AND_SELF_HOSTED_FAULT_INJECTION_RUNNER_V1_"
    "BOOTSTRAP_TRUST_AUTHENTICATION_SYNTHETIC_TRUST_CHAIN_EXACT_KEY_VERSION_"
    "DECLARED_ROLE_AND_REVOCATION_VERIFIER_ISOLATED_LAB_IMPLEMENTATION"
)

MAX_JSON_BYTES = 65_536
HEX_32_RE = re.compile(r"^[0-9a-f]{64}$")
HEX_64_RE = re.compile(r"^[0-9a-f]{128}$")
HEX_SHA_RE = re.compile(r"^[0-9a-f]{64}$")

VECTOR_FIELDS = {
    "algorithm",
    "authority_integration_commit",
    "message_profile",
    "schema",
    "schema_version",
    "signature_scheme",
    "tracks",
}
TRACK_FIELDS = {
    "canonical_frame_sha256",
    "chain",
    "message_sha256",
    "message_sha512",
    "policy_revision",
    "revocation_snapshot_revision",
    "revoked_leaf",
    "signature_domain",
    "signature_hex",
    "track_id",
    "vector_set_id",
}
CHAIN_FIELDS = {"key_id", "key_version", "public_key_hex", "role"}
REVOKED_FIELDS = {"key_id", "key_version", "state"}
RECEIPT_FIELDS = {
    "authority_consumption_event",
    "authority_gate_sha256",
    "authority_integration_commit",
    "authority_single_use_consumed",
    "authority_state_before_process_entry",
    "cargo_net_offline",
    "committed_private_material_count",
    "credential_access_count",
    "custodian_semantic_label",
    "ephemeral_generator_source_sha256",
    "generator_dependency",
    "generator_namespace_cleanup_complete",
    "generator_runtime_pin",
    "keypair_generation_count",
    "network_attempt_count",
    "private_material_file_write_count",
    "process_entry_count",
    "provider_call_count",
    "public_key_count",
    "retry_count",
    "secure_erasure_claimed",
    "signature_count",
    "signature_generation_count",
    "vector_bundle_sha256",
}
FORBIDDEN_FIELD_NAMES = {
    "active_now",
    "credential",
    "endpoint",
    "pem",
    "pkcs8",
    "private_key",
    "seed",
    "current_revocation_state",
}

TRACK_PROFILES = [
    {
        "canonical_frame_bytes": 659,
        "canonical_frame_sha256": "e298865e753a96d58b6c23d49b58cb2c4b512a519a65666d31170325bd34d295",
        "chain": [
            ("KAT_MANAGED_BOOTSTRAP_ROOT_V1", "KAT_MANAGED_ROOT_KEY_VERSION_1", "KAT_MANAGED_BOOTSTRAP_ROOT"),
            ("KAT_MANAGED_TRUST_POLICY_ISSUER_V1", "KAT_MANAGED_ISSUER_KEY_VERSION_1", "KAT_MANAGED_TRUST_POLICY_ISSUER"),
            ("KAT_MANAGED_EVIDENCE_ENVELOPE_SIGNER_V2", "KAT_MANAGED_LEAF_KEY_VERSION_2", "KAT_MANAGED_EVIDENCE_ENVELOPE_SIGNER"),
        ],
        "domain": "AB_TRACK_B_BOOTSTRAP_TRUST_AUTHENTICATION_ISOLATED_LAB_MANAGED_KAT_SIGNATURE_V1",
        "message_bytes": 754,
        "message_sha256": "a52aa400add05bb7b545c9eddbf1f48e55befd393f07c5c6ba6baaefd4f5343b",
        "message_sha512": "87ad26c16adb44af213047f0465f8e4217b0f71d69a12bdf0824ba67291df667f6ca5d5455195df526b62bf7d9bac4caeae5161cc518a12122e827a369d929fd",
        "policy_revision": "KAT_MANAGED_TRUST_POLICY_REVISION_1",
        "revocation_snapshot_revision": "KAT_MANAGED_REVOCATION_SNAPSHOT_REVISION_1",
        "revoked_key_version": "KAT_MANAGED_LEAF_KEY_VERSION_1",
        "track_id": "MANAGED_SPANNER_CLOUD_KMS",
        "vector_set_id": "KAT_MANAGED_BOOTSTRAP_TRUST_PUBLIC_ONLY_PRECOMPUTED_VECTOR_SET_V1",
    },
    {
        "canonical_frame_bytes": 658,
        "canonical_frame_sha256": "da147c9e4bcb4ac54e98209f5ea2970322726d3d851ac415903e1dbe311da69e",
        "chain": [
            ("KAT_SELF_HOSTED_BOOTSTRAP_ROOT_V1", "KAT_SELF_HOSTED_ROOT_KEY_VERSION_1", "KAT_SELF_HOSTED_BOOTSTRAP_ROOT"),
            ("KAT_SELF_HOSTED_TRUST_POLICY_ISSUER_V1", "KAT_SELF_HOSTED_ISSUER_KEY_VERSION_1", "KAT_SELF_HOSTED_TRUST_POLICY_ISSUER"),
            ("KAT_SELF_HOSTED_EVIDENCE_ENVELOPE_SIGNER_V2", "KAT_SELF_HOSTED_LEAF_KEY_VERSION_2", "KAT_SELF_HOSTED_EVIDENCE_ENVELOPE_SIGNER"),
        ],
        "domain": "AB_TRACK_B_BOOTSTRAP_TRUST_AUTHENTICATION_ISOLATED_LAB_SELF_HOSTED_KAT_SIGNATURE_V1",
        "message_bytes": 757,
        "message_sha256": "2eb3584afe6c8f18281224785ec083e531da37eed71524f2eedbf3a8225055ac",
        "message_sha512": "ccd600e63a84e74c5c29c319486ec4333f85f465864cc3b3c8c7c90bb9ccb8c8b57d45e35c83c8bab66c4d95babda967daea12406de5684b1cee2433256207bb",
        "policy_revision": "KAT_SELF_HOSTED_TRUST_POLICY_REVISION_1",
        "revocation_snapshot_revision": "KAT_SELF_HOSTED_REVOCATION_SNAPSHOT_REVISION_1",
        "revoked_key_version": "KAT_SELF_HOSTED_LEAF_KEY_VERSION_1",
        "track_id": "SELF_HOSTED_ETCD_OPENBAO",
        "vector_set_id": "KAT_SELF_HOSTED_BOOTSTRAP_TRUST_PUBLIC_ONLY_PRECOMPUTED_VECTOR_SET_V1",
    },
]


class SupplyError(ValueError):
    """Closed-world public supply validation failure."""


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise SupplyError(code)


def _pairs_no_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise SupplyError("DUPLICATE_JSON_KEY")
        result[key] = value
    return result


def _canonical_json(raw: bytes, label: str) -> dict[str, Any]:
    _require(type(raw) is bytes and 0 < len(raw) <= MAX_JSON_BYTES, f"{label}_SIZE")
    _require(raw.endswith(b"\n") and not raw.endswith(b"\n\n"), f"{label}_LF")
    try:
        text = raw.decode("utf-8", "strict")
        value = json.loads(text, object_pairs_hook=_pairs_no_duplicates)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SupplyError(f"{label}_JSON") from exc
    _require(type(value) is dict, f"{label}_OBJECT")
    encoded = (json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n").encode("utf-8")
    _require(encoded == raw, f"{label}_CANONICAL")
    return value


def _exact_fields(value: dict[str, Any], fields: set[str], code: str) -> None:
    _require(set(value) == fields, code)


def _reject_forbidden_fields(value: Any) -> None:
    if type(value) is dict:
        _require(not (set(value) & FORBIDDEN_FIELD_NAMES), "FORBIDDEN_PRIVATE_OR_LIVE_FIELD")
        for child in value.values():
            _reject_forbidden_fields(child)
    elif type(value) is list:
        for child in value:
            _reject_forbidden_fields(child)


_Q = 2**255 - 19
_L = 2**252 + 27742317777372353535851937790883648493


def _inv(value: int) -> int:
    return pow(value, _Q - 2, _Q)


_D = (-121665 * _inv(121666)) % _Q
_I = pow(2, (_Q - 1) // 4, _Q)


def _xrecover(y: int) -> int:
    xx = (y * y - 1) * _inv(_D * y * y + 1)
    x = pow(xx, (_Q + 3) // 8, _Q)
    if (x * x - xx) % _Q != 0:
        x = (x * _I) % _Q
    if x & 1:
        x = _Q - x
    return x


_BY = (4 * _inv(5)) % _Q
_B = (_xrecover(_BY), _BY)
_IDENTITY = (0, 1)


def _edwards(left: tuple[int, int], right: tuple[int, int]) -> tuple[int, int]:
    x1, y1 = left
    x2, y2 = right
    product = (_D * x1 * x2 * y1 * y2) % _Q
    return (
        (x1 * y2 + x2 * y1) * _inv(1 + product) % _Q,
        (y1 * y2 + x1 * x2) * _inv(1 - product) % _Q,
    )


def _scalarmult(point: tuple[int, int], scalar: int) -> tuple[int, int]:
    result = _IDENTITY
    addend = point
    remaining = scalar
    while remaining:
        if remaining & 1:
            result = _edwards(result, addend)
        addend = _edwards(addend, addend)
        remaining >>= 1
    return result


def _decodepoint(raw: bytes) -> tuple[int, int]:
    _require(len(raw) == 32, "ED25519_POINT_LENGTH")
    encoded = int.from_bytes(raw, "little")
    y = encoded & ((1 << 255) - 1)
    sign = encoded >> 255
    _require(y < _Q, "ED25519_POINT_NONCANONICAL_Y")
    x = _xrecover(y)
    _require(not (x == 0 and sign == 1), "ED25519_POINT_NONCANONICAL_SIGN")
    if (x & 1) != sign:
        x = _Q - x
    point = (x, y)
    _require((-x * x + y * y - 1 - _D * x * x * y * y) % _Q == 0, "ED25519_POINT_OFF_CURVE")
    _require(point != _IDENTITY, "ED25519_POINT_IDENTITY")
    _require(_scalarmult(point, _L) == _IDENTITY, "ED25519_POINT_NOT_PRIME_SUBGROUP")
    return point


def _verify(signature: bytes, message: bytes, public_key: bytes) -> bool:
    try:
        if len(signature) != 64 or len(public_key) != 32:
            return False
        point_r = _decodepoint(signature[:32])
        point_a = _decodepoint(public_key)
        scalar_s = int.from_bytes(signature[32:], "little")
        if scalar_s >= _L:
            return False
        challenge = int.from_bytes(hashlib.sha512(signature[:32] + public_key + message).digest(), "little") % _L
        return _scalarmult(_B, scalar_s) == _edwards(point_r, _scalarmult(point_a, challenge))
    except SupplyError:
        return False


def _frame_map(frame_fixture_raw: bytes) -> dict[str, bytes]:
    _require(hashlib.sha256(frame_fixture_raw).hexdigest() == FRAME_FIXTURE_RAW_SHA256, "FRAME_FIXTURE_RAW_SHA256")
    try:
        fixture = json.loads(
            frame_fixture_raw.decode("utf-8", "strict"),
            object_pairs_hook=_pairs_no_duplicates,
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SupplyError("FRAME_FIXTURE_JSON") from exc
    _require(type(fixture) is dict, "FRAME_FIXTURE_OBJECT")
    frames = fixture.get("valid_frames")
    _require(type(frames) is list and len(frames) == 2, "FRAME_FIXTURE_VALID_FRAMES")
    result: dict[str, bytes] = {}
    for item in frames:
        _require(type(item) is dict and set(item) == {"frame_utf8", "track_id"}, "FRAME_FIXTURE_ENTRY")
        track_id = item["track_id"]
        frame_text = item["frame_utf8"]
        _require(type(track_id) is str and type(frame_text) is str and track_id not in result, "FRAME_FIXTURE_ENTRY_TYPE")
        result[track_id] = frame_text.encode("utf-8")
    _require(list(result) == [profile["track_id"] for profile in TRACK_PROFILES], "FRAME_FIXTURE_TRACK_ORDER")
    return result


def _validate_receipt(receipt: dict[str, Any], vector_raw: bytes) -> None:
    _exact_fields(receipt, RECEIPT_FIELDS, "RECEIPT_FIELDS")
    expected: dict[str, Any] = {
        "authority_consumption_event": CONSUMPTION_EVENT,
        "authority_gate_sha256": AUTHORITY_GATE_SHA256,
        "authority_integration_commit": AUTHORITY_INTEGRATION_COMMIT,
        "authority_single_use_consumed": True,
        "authority_state_before_process_entry": AUTHORITY_STATE_BEFORE_ENTRY,
        "cargo_net_offline": True,
        "committed_private_material_count": 0,
        "credential_access_count": 0,
        "custodian_semantic_label": "FIXTURE_CUSTODIAN",
        "ephemeral_generator_source_sha256": GENERATOR_SOURCE_SHA256,
        "generator_dependency": "ring 0.17.14",
        "generator_namespace_cleanup_complete": True,
        "generator_runtime_pin": GENERATOR_RUNTIME_PIN,
        "keypair_generation_count": 6,
        "network_attempt_count": 0,
        "private_material_file_write_count": 0,
        "process_entry_count": 1,
        "provider_call_count": 0,
        "public_key_count": 6,
        "retry_count": 0,
        "secure_erasure_claimed": False,
        "signature_count": 2,
        "signature_generation_count": 2,
        "vector_bundle_sha256": hashlib.sha256(vector_raw).hexdigest(),
    }
    _require(receipt == expected, "RECEIPT_EXACT_CONTRACT")


def _validate_vector(vector: dict[str, Any], frames: dict[str, bytes]) -> tuple[int, int]:
    _exact_fields(vector, VECTOR_FIELDS, "VECTOR_FIELDS")
    _reject_forbidden_fields(vector)
    _require(vector["algorithm"] == ALGORITHM, "VECTOR_ALGORITHM")
    _require(vector["authority_integration_commit"] == AUTHORITY_INTEGRATION_COMMIT, "VECTOR_AUTHORITY_COMMIT")
    _require(vector["message_profile"] == MESSAGE_PROFILE, "VECTOR_MESSAGE_PROFILE")
    _require(vector["schema"] == VECTOR_SCHEMA and type(vector["schema_version"]) is int and vector["schema_version"] == 1, "VECTOR_SCHEMA")
    _require(vector["signature_scheme"] == SIGNATURE_SCHEME, "VECTOR_SIGNATURE_SCHEME")
    tracks = vector["tracks"]
    _require(type(tracks) is list and len(tracks) == 2, "VECTOR_TRACKS")

    public_keys: list[bytes] = []
    signature_verifications = 0
    for track, profile in zip(tracks, TRACK_PROFILES, strict=True):
        _require(type(track) is dict, "TRACK_OBJECT")
        _exact_fields(track, TRACK_FIELDS, "TRACK_FIELDS")
        _require(track["track_id"] == profile["track_id"], "TRACK_ORDER_OR_ID")
        _require(track["vector_set_id"] == profile["vector_set_id"], "TRACK_VECTOR_SET")
        _require(track["policy_revision"] == profile["policy_revision"], "TRACK_POLICY_REVISION")
        _require(track["revocation_snapshot_revision"] == profile["revocation_snapshot_revision"], "TRACK_REVOCATION_REVISION")
        _require(track["signature_domain"] == profile["domain"], "TRACK_SIGNATURE_DOMAIN")
        _require(track["canonical_frame_sha256"] == profile["canonical_frame_sha256"], "TRACK_FRAME_SHA256")
        _require(track["message_sha256"] == profile["message_sha256"], "TRACK_MESSAGE_SHA256")
        _require(track["message_sha512"] == profile["message_sha512"], "TRACK_MESSAGE_SHA512")

        frame = frames.get(profile["track_id"])
        _require(type(frame) is bytes and len(frame) == profile["canonical_frame_bytes"], "TRACK_FRAME_BYTES")
        _require(hashlib.sha256(frame).hexdigest() == profile["canonical_frame_sha256"], "TRACK_FRAME_CONTENT")
        domain = profile["domain"].encode("ascii")
        message = len(domain).to_bytes(8, "big") + domain + len(frame).to_bytes(8, "big") + frame
        _require(len(message) == profile["message_bytes"], "TRACK_MESSAGE_BYTES")
        _require(hashlib.sha256(message).hexdigest() == profile["message_sha256"], "TRACK_REBUILT_MESSAGE_SHA256")
        _require(hashlib.sha512(message).hexdigest() == profile["message_sha512"], "TRACK_REBUILT_MESSAGE_SHA512")

        chain = track["chain"]
        _require(type(chain) is list and len(chain) == 3, "TRACK_CHAIN_LENGTH")
        for entry, expected in zip(chain, profile["chain"], strict=True):
            _require(type(entry) is dict, "CHAIN_ENTRY_OBJECT")
            _exact_fields(entry, CHAIN_FIELDS, "CHAIN_ENTRY_FIELDS")
            _require((entry["key_id"], entry["key_version"], entry["role"]) == expected, "CHAIN_ENTRY_ID_VERSION_ROLE")
            key_hex = entry["public_key_hex"]
            _require(type(key_hex) is str and HEX_32_RE.fullmatch(key_hex) is not None, "CHAIN_PUBLIC_KEY_HEX")
            key = bytes.fromhex(key_hex)
            _decodepoint(key)
            public_keys.append(key)

        revoked = track["revoked_leaf"]
        _require(type(revoked) is dict, "REVOKED_LEAF_OBJECT")
        _exact_fields(revoked, REVOKED_FIELDS, "REVOKED_LEAF_FIELDS")
        _require(
            revoked == {
                "key_id": profile["chain"][2][0],
                "key_version": profile["revoked_key_version"],
                "state": "REVOKED_AT_OR_BEFORE_EXACT_FROZEN_SYNTHETIC_REVISION",
            },
            "REVOKED_LEAF_EXACT",
        )
        signature_hex = track["signature_hex"]
        _require(type(signature_hex) is str and HEX_64_RE.fullmatch(signature_hex) is not None, "TRACK_SIGNATURE_HEX")
        _require(_verify(bytes.fromhex(signature_hex), message, public_keys[-1]), "TRACK_SIGNATURE_VERIFY")
        signature_verifications += 1

    _require(len(public_keys) == 6 and len(set(public_keys)) == 6, "PUBLIC_KEY_COUNT_OR_DISTINCTNESS")
    _require(signature_verifications == 2, "SIGNATURE_VERIFICATION_COUNT")
    return len(public_keys), signature_verifications


def review_supply(
    vector_raw: bytes,
    receipt_raw: bytes,
    frame_fixture_raw: bytes,
    *,
    enforce_frozen_raw_hashes: bool = True,
) -> dict[str, str]:
    if enforce_frozen_raw_hashes:
        _require(hashlib.sha256(vector_raw).hexdigest() == VECTOR_BUNDLE_RAW_SHA256, "VECTOR_RAW_SHA256")
        _require(hashlib.sha256(receipt_raw).hexdigest() == GENERATION_RECEIPT_RAW_SHA256, "RECEIPT_RAW_SHA256")
    vector = _canonical_json(vector_raw, "VECTOR")
    receipt = _canonical_json(receipt_raw, "RECEIPT")
    frames = _frame_map(frame_fixture_raw)
    _validate_receipt(receipt, vector_raw)
    public_key_count, verification_count = _validate_vector(vector, frames)
    return {
        "schema": SCHEMA,
        "status": "BOOTSTRAP_TRUST_PUBLIC_ONLY_VECTOR_SUPPLY_AND_GENERATION_PROVENANCE_RECEIPT_FREEZE_PASS",
        "authority_integration_commit": AUTHORITY_INTEGRATION_COMMIT,
        "authority_gate_sha256": AUTHORITY_GATE_SHA256,
        "authority_full_receipt_sha256": AUTHORITY_FULL_RECEIPT_SHA256,
        "fixture_generation_authority_single_use_consumed": "true",
        "fixture_generation_process_entry_count": "1",
        "fixture_generation_retry_count": "0",
        "fixture_generation_keypair_count": "6",
        "fixture_generation_signature_count": "2",
        "fixture_generation_revoked_leaf_keypair_count": "0",
        "fixture_generation_certificate_link_signature_count": "0",
        "custodian_semantic_label": "FIXTURE_CUSTODIAN",
        "generator_source_sha256": GENERATOR_SOURCE_SHA256,
        "generator_dependency": "ring 0.17.14",
        "generator_runtime_pin": GENERATOR_RUNTIME_PIN,
        "cargo_net_offline": "true",
        "network_attempt_count": "0",
        "provider_call_count": "0",
        "credential_access_count": "0",
        "private_material_file_write_count": "0",
        "committed_private_material_count": "0",
        "generator_namespace_cleanup_complete": "true",
        "secure_erasure_claimed": "false",
        "vector_bundle_sha256": hashlib.sha256(vector_raw).hexdigest(),
        "generation_receipt_sha256": hashlib.sha256(receipt_raw).hexdigest(),
        "track_count": "2",
        "public_key_count": str(public_key_count),
        "distinct_public_key_count": str(public_key_count),
        "strict_public_point_validation_count": str(public_key_count),
        "strict_signature_verification_count": str(verification_count),
        "chain_entry_count_per_track": "3",
        "positive_signature_verification_count_per_track": "1",
        "underlying_implementation_authority_effective": "true",
        "underlying_implementation_authority_single_use_consumed": "false",
        "fixture_generation_authority_state": CONSUMED_STATE,
        "next_unit": NEXT_UNIT,
        "production_ingestion_controls_implemented": "0",
        "production_threat_specifications_runtime_exercised": "0",
        "runtime_prerequisites_satisfied": "0",
        "real_evidence_items_present": "0",
    }


def _render(receipt: dict[str, str]) -> str:
    return "".join(f"{key}\t{value}\n" for key, value in receipt.items())


def main(argv: list[str]) -> int:
    if len(argv) != 4:
        print("usage: validator VECTOR_JSON RECEIPT_JSON PREDECESSOR_FRAME_FIXTURE_JSON", file=sys.stderr)
        return 2
    try:
        result = review_supply(Path(argv[1]).read_bytes(), Path(argv[2]).read_bytes(), Path(argv[3]).read_bytes())
    except (OSError, SupplyError) as exc:
        print(f"FAIL\t{exc}", file=sys.stderr)
        return 1
    sys.stdout.write(_render(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
