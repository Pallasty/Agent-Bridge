#!/usr/bin/env python3
"""Pure isolated-lab bootstrap-trust authentication verifier.

The public entrypoint accepts four disjoint inputs: exact frame bytes, exact
detached authentication-bundle bytes, exact separately injected synthetic
trust-policy bytes, and the call mode.  Production and unknown modes are
rejected before the other three inputs are observed.  The synthetic path first
composes with the frozen predecessor frame reviewer, then validates the entire
two-track public-only trust snapshot and performs exactly one active-leaf
Ed25519 signature equation for the selected track.

This module has no signing, key generation, private seed, provider, credential,
network, clock, process, persistence, ambient trust-store, or mutable-cache
surface.  Its only successful state is a fixed nonproduction synthetic KAT
component result.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from typing import Any, Mapping, NoReturn

import biocortex_ab_track_b_reference_provider_fault_injection_runner_production_evidence_envelope_bounded_frame_parser_and_synthetic_mode_separation_isolated_lab_v1 as predecessor


SYNTHETIC_KAT_MODE = "SYNTHETIC_KAT"
PRODUCTION_MODE = "PRODUCTION"

TRUST_POLICY_SCHEMA = (
    "agent_bridge.biocortex_ab_track_b_reference_provider_fault_injection_"
    "runner.bootstrap_trust_authentication_synthetic_trust_policy_isolated_lab_kat.v1"
)
DETACHED_BUNDLE_SCHEMA = (
    "agent_bridge.biocortex_ab_track_b_reference_provider_fault_injection_"
    "runner.bootstrap_trust_authentication_detached_bundle_isolated_lab_kat.v1"
)
RECEIPT_SCHEMA = (
    "agent_bridge.biocortex_ab_track_b_reference_provider_fault_injection_"
    "runner.bootstrap_trust_authentication_synthetic_trust_chain_exact_key_"
    "version_declared_role_and_revocation_verifier_isolated_lab_v1.receipt.v0"
)
STATUS = (
    "REFERENCE_PROVIDER_MANAGED_AND_SELF_HOSTED_FAULT_INJECTION_RUNNER_V1_"
    "BOOTSTRAP_TRUST_AUTHENTICATION_SYNTHETIC_TRUST_CHAIN_EXACT_KEY_VERSION_"
    "DECLARED_ROLE_AND_REVOCATION_VERIFIED_ISOLATED_LAB_COMPONENT_ONLY_"
    "NO_PRODUCTION_AUTHORITY"
)
COMPONENT_STATE = (
    "AUTHENTICATED_SYNTHETIC_KAT_AGAINST_FROZEN_BOOTSTRAP_TRUST_"
    "SNAPSHOT_COMPONENT_ONLY"
)
RECEIPT_HASH_DOMAIN = (
    "AB_TRACK_B_BOOTSTRAP_TRUST_AUTHENTICATION_ISOLATED_LAB_KAT_RECEIPT_V1"
)
TRUST_DOMAIN_FAMILY = (
    "AB_TRACK_B_BOOTSTRAP_TRUST_AUTHENTICATION_ISOLATED_LAB_KAT_SIGNATURE_FAMILY_V1"
)
ALGORITHM = "ED25519"
SIGNATURE_SCHEME = "ED25519_PURE_RFC8032_NO_CONTEXT_NO_PREHASH"
MESSAGE_PROFILE = (
    "U64BE_LENGTH_PREFIXED_ASCII_DOMAIN_AND_EXACT_PREDECESSOR_CANONICAL_"
    "FRAME_BYTES_NO_PARSE_RESERIALIZE"
)
DECLARED_ROLE = "SYNTHETIC_EVIDENCE_ENVELOPE_SIGNER_KAT_ONLY"
ACTIVE_STATE = "ACTIVE_AT_EXACT_FROZEN_SYNTHETIC_REVISION"
REVOKED_STATE = "REVOKED_AT_OR_BEFORE_EXACT_FROZEN_SYNTHETIC_REVISION"
PUBLIC_VECTOR_BUNDLE_SHA256 = "a87e0883a42ca69fe3a0348b4ffe44c153882f8dcc93eb67db1ea048d53851d7"

MAX_AUTHENTICATION_BUNDLE_BYTES = 65_536
MAX_TRUST_POLICY_BYTES = 65_536
MAX_JSON_DEPTH = 32
MAX_JSON_NODES = 4_096
MAX_OBJECT_MEMBERS = 256
MAX_ARRAY_ITEMS = 64
MIN_SIGNED_INT64 = -(2**63)
MAX_SIGNED_INT64 = 2**63 - 1

TRUST_POLICY_KEYS = (
    "algorithm",
    "declared_role_mapping",
    "message_profile",
    "schema",
    "schema_version",
    "signature_scheme",
    "tracks",
    "trust_domain_family",
)
DECLARED_ROLE_MAPPING_KEYS = (
    "generic_declared_role_class",
    "mapping_is_role_scope_authorization",
    "track_role_map",
)
TRACK_POLICY_KEYS = (
    "active_leaf_state",
    "canonical_frame_sha256",
    "chain",
    "frozen_snapshot_is_currentness",
    "message_sha256",
    "message_sha512",
    "policy_revision",
    "revocation_snapshot_revision",
    "revoked_leaf",
    "signature_domain",
    "track_id",
    "vector_set_id",
)
CHAIN_ENTRY_KEYS = ("key_id", "key_version", "public_key_hex", "role")
REVOKED_LEAF_KEYS = ("key_id", "key_version", "state")
DETACHED_BUNDLE_KEYS = (
    "declared_role",
    "policy_revision",
    "revocation_snapshot_revision",
    "schema",
    "schema_version",
    "signature_hex",
    "signer_key_id",
    "signer_key_version",
    "track_id",
    "vector_set_id",
)

HEX_32_RE = re.compile(r"^[0-9a-f]{64}$")
HEX_64_RE = re.compile(r"^[0-9a-f]{128}$")


@dataclass(frozen=True)
class KeyProfile:
    key_id: str
    key_version: str
    role: str
    public_key_hex: str


@dataclass(frozen=True)
class TrackProfile:
    track_id: str
    vector_set_id: str
    policy_revision: str
    revocation_snapshot_revision: str
    signature_domain: str
    canonical_frame_bytes: int
    canonical_frame_sha256: str
    message_bytes: int
    message_sha256: str
    message_sha512: str
    root: KeyProfile
    issuer: KeyProfile
    leaf: KeyProfile
    revoked_leaf_key_version: str


TRACK_PROFILES = (
    TrackProfile(
        track_id="MANAGED_SPANNER_CLOUD_KMS",
        vector_set_id="KAT_MANAGED_BOOTSTRAP_TRUST_PUBLIC_ONLY_PRECOMPUTED_VECTOR_SET_V1",
        policy_revision="KAT_MANAGED_TRUST_POLICY_REVISION_1",
        revocation_snapshot_revision="KAT_MANAGED_REVOCATION_SNAPSHOT_REVISION_1",
        signature_domain="AB_TRACK_B_BOOTSTRAP_TRUST_AUTHENTICATION_ISOLATED_LAB_MANAGED_KAT_SIGNATURE_V1",
        canonical_frame_bytes=659,
        canonical_frame_sha256="e298865e753a96d58b6c23d49b58cb2c4b512a519a65666d31170325bd34d295",
        message_bytes=754,
        message_sha256="a52aa400add05bb7b545c9eddbf1f48e55befd393f07c5c6ba6baaefd4f5343b",
        message_sha512="87ad26c16adb44af213047f0465f8e4217b0f71d69a12bdf0824ba67291df667f6ca5d5455195df526b62bf7d9bac4caeae5161cc518a12122e827a369d929fd",
        root=KeyProfile("KAT_MANAGED_BOOTSTRAP_ROOT_V1", "KAT_MANAGED_ROOT_KEY_VERSION_1", "KAT_MANAGED_BOOTSTRAP_ROOT", "b8b7e8edb2a4e95bed9fb2b288e68e48f136dd25c6e9be64eaaeabc4261f5c99"),
        issuer=KeyProfile("KAT_MANAGED_TRUST_POLICY_ISSUER_V1", "KAT_MANAGED_ISSUER_KEY_VERSION_1", "KAT_MANAGED_TRUST_POLICY_ISSUER", "d91db78ec3ce8f1c5b3985690b20a6f17cd9685968febc9ae13d4d2c20a66583"),
        leaf=KeyProfile("KAT_MANAGED_EVIDENCE_ENVELOPE_SIGNER_V2", "KAT_MANAGED_LEAF_KEY_VERSION_2", "KAT_MANAGED_EVIDENCE_ENVELOPE_SIGNER", "3fd584089659ed90ac0947f9cd3293ace455e2c8ce4520824b8201bc7dc35ca4"),
        revoked_leaf_key_version="KAT_MANAGED_LEAF_KEY_VERSION_1",
    ),
    TrackProfile(
        track_id="SELF_HOSTED_ETCD_OPENBAO",
        vector_set_id="KAT_SELF_HOSTED_BOOTSTRAP_TRUST_PUBLIC_ONLY_PRECOMPUTED_VECTOR_SET_V1",
        policy_revision="KAT_SELF_HOSTED_TRUST_POLICY_REVISION_1",
        revocation_snapshot_revision="KAT_SELF_HOSTED_REVOCATION_SNAPSHOT_REVISION_1",
        signature_domain="AB_TRACK_B_BOOTSTRAP_TRUST_AUTHENTICATION_ISOLATED_LAB_SELF_HOSTED_KAT_SIGNATURE_V1",
        canonical_frame_bytes=658,
        canonical_frame_sha256="da147c9e4bcb4ac54e98209f5ea2970322726d3d851ac415903e1dbe311da69e",
        message_bytes=757,
        message_sha256="2eb3584afe6c8f18281224785ec083e531da37eed71524f2eedbf3a8225055ac",
        message_sha512="ccd600e63a84e74c5c29c319486ec4333f85f465864cc3b3c8c7c90bb9ccb8c8b57d45e35c83c8bab66c4d95babda967daea12406de5684b1cee2433256207bb",
        root=KeyProfile("KAT_SELF_HOSTED_BOOTSTRAP_ROOT_V1", "KAT_SELF_HOSTED_ROOT_KEY_VERSION_1", "KAT_SELF_HOSTED_BOOTSTRAP_ROOT", "29aa03a7e15f1fe55876c08feda304c65c1ea8d85bb7eec6bf0ae1589b4c4fb2"),
        issuer=KeyProfile("KAT_SELF_HOSTED_TRUST_POLICY_ISSUER_V1", "KAT_SELF_HOSTED_ISSUER_KEY_VERSION_1", "KAT_SELF_HOSTED_TRUST_POLICY_ISSUER", "d5e9bc56ec76659ef5e961e601b130dfe62cf0c7624576ddca65fc47e05d20d0"),
        leaf=KeyProfile("KAT_SELF_HOSTED_EVIDENCE_ENVELOPE_SIGNER_V2", "KAT_SELF_HOSTED_LEAF_KEY_VERSION_2", "KAT_SELF_HOSTED_EVIDENCE_ENVELOPE_SIGNER", "b706afbe337aaf6df0c9ef5f55339a8f3a32192177bbd5a409041c171b88137c"),
        revoked_leaf_key_version="KAT_SELF_HOSTED_LEAF_KEY_VERSION_1",
    ),
)


class BootstrapTrustReviewError(ValueError):
    """Fail-closed review error with a stable public reason code."""

    def __init__(self, code: str, detail: str, *, detail_code: str | None = None):
        super().__init__(f"{code}: {detail}")
        self.code = code
        self.detail = detail
        self.detail_code = detail_code


def _fail(code: str, detail: str) -> NoReturn:
    raise BootstrapTrustReviewError(code, detail)


def _require(condition: bool, code: str, detail: str) -> None:
    if not condition:
        _fail(code, detail)


def _exact_keys(value: Mapping[str, Any], expected: tuple[str, ...], code: str) -> None:
    _require(type(value) is dict and set(value) == set(expected), code, "closed field set drift")


def _reject_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        _require(type(key) is str and key not in result, "E_JSON_DUPLICATE_KEY", "duplicate or nonstring object key")
        result[key] = value
    return result


def _parse_constant(value: str) -> NoReturn:
    _fail("E_JSON_NONFINITE", f"nonfinite number {value!r} forbidden")


def _parse_float(value: str) -> NoReturn:
    _fail("E_JSON_FLOAT", f"floating-point number {value!r} forbidden")


def _parse_int(value: str) -> int:
    parsed = int(value, 10)
    _require(MIN_SIGNED_INT64 <= parsed <= MAX_SIGNED_INT64, "E_JSON_INT_RANGE", "integer outside signed int64")
    return parsed


def _shape(value: Any, depth: int = 1) -> tuple[int, int]:
    _require(depth <= MAX_JSON_DEPTH, "E_JSON_DEPTH", "maximum JSON depth exceeded")
    nodes = 1
    maximum_depth = depth
    if type(value) is dict:
        _require(len(value) <= MAX_OBJECT_MEMBERS, "E_JSON_OBJECT_MEMBERS", "too many object members")
        for child in value.values():
            child_nodes, child_depth = _shape(child, depth + 1)
            nodes += child_nodes
            maximum_depth = max(maximum_depth, child_depth)
    elif type(value) is list:
        _require(len(value) <= MAX_ARRAY_ITEMS, "E_JSON_ARRAY_ITEMS", "too many array items")
        for child in value:
            child_nodes, child_depth = _shape(child, depth + 1)
            nodes += child_nodes
            maximum_depth = max(maximum_depth, child_depth)
    else:
        _require(value is None or type(value) in (str, int, bool), "E_JSON_VALUE_TYPE", "unsupported JSON value")
    _require(nodes <= MAX_JSON_NODES, "E_JSON_NODES", "too many JSON nodes")
    return nodes, maximum_depth


def _canonical_bytes(value: Mapping[str, Any]) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _decode_closed_json(raw: bytes, *, limit: int, label: str) -> dict[str, Any]:
    _require(type(raw) is bytes, f"E_{label}_TYPE", f"{label} must be exact bytes")
    _require(0 < len(raw) <= limit, f"E_{label}_SIZE", f"{label} is empty or exceeds bound")
    try:
        text = raw.decode("utf-8", "strict")
    except UnicodeDecodeError as error:
        _fail(f"E_{label}_UTF8", str(error))
    decoder = json.JSONDecoder(
        object_pairs_hook=_reject_pairs,
        parse_constant=_parse_constant,
        parse_float=_parse_float,
        parse_int=_parse_int,
        strict=True,
    )
    try:
        value, end = decoder.raw_decode(text)
    except BootstrapTrustReviewError:
        raise
    except (json.JSONDecodeError, RecursionError) as error:
        _fail(f"E_{label}_JSON", str(error))
    _require(end == len(text), f"E_{label}_TRAILING", "trailing bytes or second value forbidden")
    _require(type(value) is dict, f"E_{label}_ROOT", "root must be object")
    _shape(value)
    try:
        canonical = _canonical_bytes(value)
    except UnicodeEncodeError as error:
        _fail(f"E_{label}_UNICODE_SCALAR", str(error))
    _require(canonical == raw, f"E_{label}_NONCANONICAL", "input is not exact compact canonical JSON")
    return value


def _reject_mode(mode: str) -> None:
    if type(mode) is not str:
        _fail("E_BOOTSTRAP_TRUST_MODE_UNKNOWN", "only exact string SYNTHETIC_KAT is reviewable")
    if mode == PRODUCTION_MODE:
        _fail("E_BOOTSTRAP_TRUST_PRODUCTION_MODE_NOT_AUTHORIZED", "production authentication is outside isolated-lab authority")
    if mode != SYNTHETIC_KAT_MODE:
        _fail("E_BOOTSTRAP_TRUST_MODE_UNKNOWN", "only SYNTHETIC_KAT is reviewable")


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
    _require(len(raw) == 32, "E_ED25519_POINT_LENGTH", "point must be raw32")
    encoded = int.from_bytes(raw, "little")
    y = encoded & ((1 << 255) - 1)
    sign = encoded >> 255
    _require(y < _Q, "E_ED25519_POINT_NONCANONICAL_Y", "encoded y is not canonical")
    x = _xrecover(y)
    _require(not (x == 0 and sign == 1), "E_ED25519_POINT_NEGATIVE_ZERO", "negative-zero point forbidden")
    if (x & 1) != sign:
        x = _Q - x
    point = (x, y)
    _require((-x * x + y * y - 1 - _D * x * x * y * y) % _Q == 0, "E_ED25519_POINT_OFF_CURVE", "point is not on curve")
    _require(point != _IDENTITY, "E_ED25519_POINT_IDENTITY", "identity point forbidden")
    _require(_scalarmult(point, _L) == _IDENTITY, "E_ED25519_POINT_NOT_PRIME_SUBGROUP", "point is not in prime subgroup")
    return point


def _verify(
    signature: bytes,
    message: bytes,
    key_bytes: bytes,
    point_a: tuple[int, int],
) -> bool:
    try:
        if len(signature) != 64 or len(key_bytes) != 32:
            return False
        point_r = _decodepoint(signature[:32])
        scalar_s = int.from_bytes(signature[32:], "little")
        if scalar_s >= _L:
            return False
        challenge = int.from_bytes(hashlib.sha512(signature[:32] + key_bytes + message).digest(), "little") % _L
        return _scalarmult(_B, scalar_s) == _edwards(point_r, _scalarmult(point_a, challenge))
    except BootstrapTrustReviewError:
        return False


def _key_object(profile: KeyProfile) -> dict[str, Any]:
    return {
        "key_id": profile.key_id,
        "key_version": profile.key_version,
        "public_key_hex": profile.public_key_hex,
        "role": profile.role,
    }


def known_answer_trust_policy() -> dict[str, Any]:
    """Return the exact public-only two-track synthetic trust snapshot."""

    tracks: list[dict[str, Any]] = []
    for profile in TRACK_PROFILES:
        tracks.append(
            {
                "active_leaf_state": ACTIVE_STATE,
                "canonical_frame_sha256": profile.canonical_frame_sha256,
                "chain": [_key_object(profile.root), _key_object(profile.issuer), _key_object(profile.leaf)],
                "frozen_snapshot_is_currentness": False,
                "message_sha256": profile.message_sha256,
                "message_sha512": profile.message_sha512,
                "policy_revision": profile.policy_revision,
                "revocation_snapshot_revision": profile.revocation_snapshot_revision,
                "revoked_leaf": {
                    "key_id": profile.leaf.key_id,
                    "key_version": profile.revoked_leaf_key_version,
                    "state": REVOKED_STATE,
                },
                "signature_domain": profile.signature_domain,
                "track_id": profile.track_id,
                "vector_set_id": profile.vector_set_id,
            }
        )
    return {
        "algorithm": ALGORITHM,
        "declared_role_mapping": {
            "generic_declared_role_class": DECLARED_ROLE,
            "mapping_is_role_scope_authorization": False,
            "track_role_map": {profile.track_id: profile.leaf.role for profile in TRACK_PROFILES},
        },
        "message_profile": MESSAGE_PROFILE,
        "schema": TRUST_POLICY_SCHEMA,
        "schema_version": 1,
        "signature_scheme": SIGNATURE_SCHEME,
        "tracks": tracks,
        "trust_domain_family": TRUST_DOMAIN_FAMILY,
    }


def known_answer_trust_policy_bytes() -> bytes:
    return _canonical_bytes(known_answer_trust_policy())


def _profile_for_track(track_id: str) -> TrackProfile:
    for profile in TRACK_PROFILES:
        if track_id == profile.track_id:
            return profile
    _fail("E_TRACK_UNKNOWN", "track is not one of two frozen synthetic profiles")


def _validate_policy(
    policy: Mapping[str, Any],
) -> tuple[tuple[bytes, tuple[int, int]], ...]:
    _exact_keys(policy, TRUST_POLICY_KEYS, "E_TRUST_POLICY_FIELDS")
    _require(policy["algorithm"] == ALGORITHM and type(policy["algorithm"]) is str, "E_TRUST_POLICY_ALGORITHM", "algorithm drift")
    _require(policy["message_profile"] == MESSAGE_PROFILE and type(policy["message_profile"]) is str, "E_TRUST_POLICY_MESSAGE_PROFILE", "message profile drift")
    _require(policy["schema"] == TRUST_POLICY_SCHEMA and type(policy["schema"]) is str, "E_TRUST_POLICY_SCHEMA", "schema drift")
    _require(type(policy["schema_version"]) is int and policy["schema_version"] == 1, "E_TRUST_POLICY_SCHEMA_VERSION", "schema version drift")
    _require(policy["signature_scheme"] == SIGNATURE_SCHEME and type(policy["signature_scheme"]) is str, "E_TRUST_POLICY_SIGNATURE_SCHEME", "signature scheme drift")
    _require(policy["trust_domain_family"] == TRUST_DOMAIN_FAMILY and type(policy["trust_domain_family"]) is str, "E_TRUST_POLICY_DOMAIN_FAMILY", "trust domain drift")

    mapping = policy["declared_role_mapping"]
    _require(type(mapping) is dict, "E_ROLE_MAPPING_OBJECT", "role mapping must be object")
    _exact_keys(mapping, DECLARED_ROLE_MAPPING_KEYS, "E_ROLE_MAPPING_FIELDS")
    _require(mapping["generic_declared_role_class"] == DECLARED_ROLE, "E_ROLE_MAPPING_GENERIC", "generic declared role drift")
    _require(mapping["mapping_is_role_scope_authorization"] is False, "E_ROLE_MAPPING_AUTHORIZATION", "role mapping may not authorize scope")
    expected_role_map = {profile.track_id: profile.leaf.role for profile in TRACK_PROFILES}
    _require(type(mapping["track_role_map"]) is dict and mapping["track_role_map"] == expected_role_map, "E_ROLE_MAPPING_TRACKS", "track role map drift")

    tracks = policy["tracks"]
    _require(type(tracks) is list and len(tracks) == 2, "E_TRUST_POLICY_TRACKS", "exactly two tracks required")
    public_keys: list[tuple[bytes, tuple[int, int]]] = []
    for track, profile in zip(tracks, TRACK_PROFILES, strict=True):
        _require(type(track) is dict, "E_TRACK_POLICY_OBJECT", "track policy must be object")
        _exact_keys(track, TRACK_POLICY_KEYS, "E_TRACK_POLICY_FIELDS")
        expected_scalars = {
            "active_leaf_state": ACTIVE_STATE,
            "canonical_frame_sha256": profile.canonical_frame_sha256,
            "frozen_snapshot_is_currentness": False,
            "message_sha256": profile.message_sha256,
            "message_sha512": profile.message_sha512,
            "policy_revision": profile.policy_revision,
            "revocation_snapshot_revision": profile.revocation_snapshot_revision,
            "signature_domain": profile.signature_domain,
            "track_id": profile.track_id,
            "vector_set_id": profile.vector_set_id,
        }
        for field, expected in expected_scalars.items():
            _require(type(track[field]) is type(expected) and track[field] == expected, f"E_TRACK_POLICY_{field.upper()}", f"{field} drift")
        chain = track["chain"]
        _require(type(chain) is list and len(chain) == 3, "E_TRUST_POLICY_CHAIN", "exact root/issuer/active-leaf chain required")
        for entry, expected_key in zip(chain, (profile.root, profile.issuer, profile.leaf), strict=True):
            _require(type(entry) is dict, "E_CHAIN_ENTRY_OBJECT", "chain entry must be object")
            _exact_keys(entry, CHAIN_ENTRY_KEYS, "E_CHAIN_ENTRY_FIELDS")
            _require(entry["key_id"] == expected_key.key_id and type(entry["key_id"]) is str, "E_CHAIN_KEY_ID", "key id drift")
            _require(entry["key_version"] == expected_key.key_version and type(entry["key_version"]) is str, "E_CHAIN_KEY_VERSION", "key version drift")
            _require(entry["role"] == expected_key.role and type(entry["role"]) is str, "E_CHAIN_ROLE", "role drift")
            key_hex = entry["public_key_hex"]
            _require(type(key_hex) is str and HEX_32_RE.fullmatch(key_hex) is not None, "E_CHAIN_PUBLIC_KEY_HEX", "public key must be lowercase raw32 hex")
            key = bytes.fromhex(key_hex)
            point = _decodepoint(key)
            _require(key_hex == expected_key.public_key_hex, "E_CHAIN_PUBLIC_KEY_PIN", "public key is not frozen pinned value")
            public_keys.append((key, point))
        revoked = track["revoked_leaf"]
        _require(type(revoked) is dict, "E_REVOKED_LEAF_OBJECT", "revoked leaf must be object")
        _exact_keys(revoked, REVOKED_LEAF_KEYS, "E_REVOKED_LEAF_FIELDS")
        _require(
            revoked == {"key_id": profile.leaf.key_id, "key_version": profile.revoked_leaf_key_version, "state": REVOKED_STATE},
            "E_REVOKED_LEAF_EXACT",
            "revoked leaf snapshot drift",
        )
    _require(
        len(public_keys) == 6 and len({key for key, _point in public_keys}) == 6,
        "E_TRUST_POLICY_PUBLIC_KEY_DISTINCTNESS",
        "six distinct public keys required",
    )
    return tuple(public_keys)


def _validate_bundle(bundle: Mapping[str, Any], profile: TrackProfile) -> bytes:
    _exact_keys(bundle, DETACHED_BUNDLE_KEYS, "E_AUTHENTICATION_BUNDLE_FIELDS")
    _require(bundle["schema"] == DETACHED_BUNDLE_SCHEMA and type(bundle["schema"]) is str, "E_AUTHENTICATION_BUNDLE_SCHEMA", "bundle schema drift")
    _require(type(bundle["schema_version"]) is int and bundle["schema_version"] == 1, "E_AUTHENTICATION_BUNDLE_SCHEMA_VERSION", "bundle schema version drift")
    _require(type(bundle["track_id"]) is str, "E_AUTHENTICATION_BUNDLE_TRACK_TYPE", "track id must be string")
    expected = {
        "declared_role": DECLARED_ROLE,
        "policy_revision": profile.policy_revision,
        "revocation_snapshot_revision": profile.revocation_snapshot_revision,
        "signer_key_id": profile.leaf.key_id,
        "signer_key_version": profile.leaf.key_version,
        "track_id": profile.track_id,
        "vector_set_id": profile.vector_set_id,
    }
    for field, value in expected.items():
        _require(type(bundle[field]) is str and bundle[field] == value, f"E_AUTHENTICATION_BUNDLE_{field.upper()}", f"{field} drift")
    signature_hex = bundle["signature_hex"]
    _require(type(signature_hex) is str and HEX_64_RE.fullmatch(signature_hex) is not None, "E_AUTHENTICATION_BUNDLE_SIGNATURE", "signature must be lowercase raw64 hex")
    return bytes.fromhex(signature_hex)


def _message(profile: TrackProfile, frame: bytes) -> bytes:
    _require(len(frame) == profile.canonical_frame_bytes, "E_FRAME_LENGTH_BINDING", "frame length does not match track profile")
    _require(hashlib.sha256(frame).hexdigest() == profile.canonical_frame_sha256, "E_FRAME_HASH_BINDING", "frame hash does not match track profile")
    domain = profile.signature_domain.encode("ascii")
    message = len(domain).to_bytes(8, "big") + domain + len(frame).to_bytes(8, "big") + frame
    _require(len(message) == profile.message_bytes, "E_MESSAGE_LENGTH_BINDING", "message length drift")
    _require(hashlib.sha256(message).hexdigest() == profile.message_sha256, "E_MESSAGE_SHA256_BINDING", "message SHA-256 drift")
    _require(hashlib.sha512(message).hexdigest() == profile.message_sha512, "E_MESSAGE_SHA512_BINDING", "message SHA-512 drift")
    return message


def _domain_sha256(domain: str, raw: bytes) -> str:
    return hashlib.sha256(domain.encode("ascii") + b"\x00" + raw).hexdigest()


def review_bootstrap_trust_authentication(
    frame: bytes,
    detached_authentication_bundle: bytes,
    separately_injected_synthetic_trust_policy: bytes,
    mode: str,
) -> dict[str, Any]:
    """Review one isolated-lab KAT or reject mode before observing inputs."""

    _reject_mode(mode)

    try:
        predecessor_receipt = predecessor.review_frame(frame, predecessor.SYNTHETIC_KAT_MODE)
    except predecessor.FrameReviewError as error:
        raise BootstrapTrustReviewError(
            "E_PREDECESSOR_FRAME_REJECTED",
            f"{error.code}: {error.detail}",
            detail_code=error.code,
        ) from error

    try:
        policy = _decode_closed_json(
            separately_injected_synthetic_trust_policy,
            limit=MAX_TRUST_POLICY_BYTES,
            label="TRUST_POLICY",
        )
        public_keys = _validate_policy(policy)
        profile = _profile_for_track(predecessor_receipt["track_id"])
        selected_track_index = next(
            index
            for index, candidate in enumerate(TRACK_PROFILES)
            if candidate.track_id == profile.track_id
        )
        selected_track = policy["tracks"][selected_track_index]
        _require(
            selected_track["track_id"] == profile.track_id,
            "E_TRACK_POLICY_FRAME_MISMATCH",
            "frame-selected policy track differs",
        )
    except BootstrapTrustReviewError as error:
        raise BootstrapTrustReviewError(
            "E_TRUST_POLICY_REJECTED",
            f"{error.code}: {error.detail}",
            detail_code=error.code,
        ) from error

    try:
        bundle = _decode_closed_json(
            detached_authentication_bundle,
            limit=MAX_AUTHENTICATION_BUNDLE_BYTES,
            label="AUTHENTICATION_BUNDLE",
        )
        signature = _validate_bundle(bundle, profile)
        mapped_role = policy["declared_role_mapping"]["track_role_map"][profile.track_id]
        _require(mapped_role == profile.leaf.role, "E_DECLARED_ROLE_MAPPING", "generic declared role does not map to leaf role")
        message = _message(profile, frame)
        leaf_key, leaf_point = public_keys[selected_track_index * 3 + 2]
        _require(
            _verify(signature, message, leaf_key, leaf_point),
            "E_ACTIVE_LEAF_SIGNATURE_INVALID",
            "active-leaf signature equation failed",
        )
    except BootstrapTrustReviewError as error:
        raise BootstrapTrustReviewError(
            "E_AUTHENTICATION_REJECTED",
            f"{error.code}: {error.detail}",
            detail_code=error.code,
        ) from error

    receipt: dict[str, Any] = {
        "active_leaf_key_id": profile.leaf.key_id,
        "active_leaf_key_version": profile.leaf.key_version,
        "active_leaf_state": ACTIVE_STATE,
        "algorithm": ALGORITHM,
        "authentication_metadata_detached": True,
        "boundary_threat_specifications_locally_kat_covered": 5,
        "canonical_frame_sha256": profile.canonical_frame_sha256,
        "certificate_link_signature_verification_count": 0,
        "chain_entry_count": 3,
        "component_state": COMPONENT_STATE,
        "condition_output_authorized": False,
        "content_sha256": "0" * 64,
        "declared_role": DECLARED_ROLE,
        "declared_role_cryptographically_authenticated_in_kat": True,
        "declared_role_is_role_scope_authorization": False,
        "declared_role_mapping_verified": True,
        "detached_authentication_bundle_sha256": hashlib.sha256(detached_authentication_bundle).hexdigest(),
        "downstream_gate_count": 4,
        "downstream_gates_authorized": 0,
        "evidence_acceptance_authorized": False,
        "execution_mode": SYNTHETIC_KAT_MODE,
        "fault_injection_authorized": False,
        "frame_bytes": len(frame),
        "frame_sha256": hashlib.sha256(frame).hexdigest(),
        "frozen_revocation_snapshot_is_currentness": False,
        "isolated_lab_candidate_surface_component_total": 3,
        "isolated_lab_candidate_surface_components_locally_kat_exercised": 3,
        "isolated_lab_candidate_surface_components_implemented": 3,
        "issuer_key_id": profile.issuer.key_id,
        "issuer_key_version": profile.issuer.key_version,
        "local_t05_specification_exercised": True,
        "local_t06_specification_exercised": False,
        "local_t07_specification_exercised": False,
        "local_threat_specifications_covered": 5,
        "mapped_policy_leaf_role": mapped_role,
        "message_bytes": profile.message_bytes,
        "message_profile": MESSAGE_PROFILE,
        "message_sha256": profile.message_sha256,
        "message_sha512": profile.message_sha512,
        "policy_revision": profile.policy_revision,
        "policy_track_count": 2,
        "policy_structural_chain_entry_count": 6,
        "policy_role_map_entry_count": 2,
        "policy_root_count": 2,
        "predecessor_frame_review_count": 1,
        "predecessor_receipt_content_sha256": predecessor_receipt["content_sha256"],
        "production_admissible": False,
        "production_ingestion_control_count": 14,
        "production_ingestion_controls_implemented": 0,
        "production_ingestion_controls_runtime_exercised": 0,
        "production_threat_specification_count": 20,
        "production_threat_specifications_runtime_exercised": 0,
        "production_validated_evidence_items": 0,
        "provider_authority": False,
        "public_vector_bundle_sha256": PUBLIC_VECTOR_BUNDLE_SHA256,
        "public_key_count": len(public_keys),
        "real_evidence_items_present": 0,
        "revocation_snapshot_revision": profile.revocation_snapshot_revision,
        "revoked_leaf_key_id": profile.leaf.key_id,
        "revoked_leaf_key_version": profile.revoked_leaf_key_version,
        "revoked_leaf_state": REVOKED_STATE,
        "role_scope_authorization_implemented": False,
        "root_key_id": profile.root.key_id,
        "root_key_version": profile.root.key_version,
        "runtime_authority": False,
        "runtime_prerequisite_count": 16,
        "runtime_prerequisites_satisfied": 0,
        "schema": RECEIPT_SCHEMA,
        "schema_version": 1,
        "selected_revocation_entry_count": 2,
        "separately_injected_trust_policy": True,
        "side_effects_unlocked": "NONE",
        "signature_domain": profile.signature_domain,
        "signature_scheme": SIGNATURE_SCHEME,
        "signature_verification_count": 1,
        "strict_signature_r_point_validation_count": 1,
        "signer_role_scope_authorization_implemented": False,
        "status": STATUS,
        "strict_public_key_point_validation_count": len(public_keys),
        "synthetic_fixture": True,
        "threat_case_count": 20,
        "track_id": profile.track_id,
        "track_leaf_role": profile.leaf.role,
        "track_subject_binding_implemented": False,
        "trust_policy_sha256": hashlib.sha256(separately_injected_synthetic_trust_policy).hexdigest(),
        "trust_root_count": 2,
        "vector_set_id": profile.vector_set_id,
    }
    receipt_without_hash = dict(receipt)
    del receipt_without_hash["content_sha256"]
    receipt["content_sha256"] = _domain_sha256(RECEIPT_HASH_DOMAIN, _canonical_bytes(receipt_without_hash))
    return receipt


__all__ = [
    "ACTIVE_STATE",
    "ALGORITHM",
    "BootstrapTrustReviewError",
    "COMPONENT_STATE",
    "DECLARED_ROLE",
    "DETACHED_BUNDLE_SCHEMA",
    "MESSAGE_PROFILE",
    "PRODUCTION_MODE",
    "PUBLIC_VECTOR_BUNDLE_SHA256",
    "RECEIPT_SCHEMA",
    "REVOKED_STATE",
    "SIGNATURE_SCHEME",
    "STATUS",
    "SYNTHETIC_KAT_MODE",
    "TRACK_PROFILES",
    "TRUST_DOMAIN_FAMILY",
    "TRUST_POLICY_SCHEMA",
    "known_answer_trust_policy",
    "known_answer_trust_policy_bytes",
    "review_bootstrap_trust_authentication",
]
