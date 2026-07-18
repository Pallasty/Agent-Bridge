#!/usr/bin/env python3
"""Pure isolated-lab signer role/scope authorization verifier.

The public entrypoint accepts six disjoint inputs.  Production, unknown, and
non-string modes are rejected before any other input is observed.  The
synthetic path invokes the frozen T05 bootstrap-trust reviewer exactly once,
uses that receipt as the sole signer-identity source, validates a separately
injected closed-world two-grant authorization policy, and observes the
detached six-dimension authorization request last.

This module implements only the fixed public KAT for local T06.  It has no
provider, network, credential, clock, persistence, replay ledger, signing,
fault-injection, evidence-admission, output-authority, or runtime-registration
surface.  Exact label equality is not owner, provider, subject, audience, or
nonce truth.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Mapping, NoReturn

import biocortex_ab_track_b_reference_provider_fault_injection_runner_bootstrap_trust_authentication_synthetic_trust_chain_exact_key_version_declared_role_and_revocation_verifier_isolated_lab_v1 as predecessor


SYNTHETIC_KAT_MODE = "SYNTHETIC_KAT"
PRODUCTION_MODE = "PRODUCTION"

AUTHORIZATION_POLICY_SCHEMA = (
    "agent_bridge.biocortex_ab_track_b_reference_provider_fault_injection_"
    "runner.signer_role_scope_authorization_synthetic_policy_isolated_lab_kat.v1"
)
AUTHORIZATION_REQUEST_SCHEMA = (
    "agent_bridge.biocortex_ab_track_b_reference_provider_fault_injection_"
    "runner.signer_role_scope_authorization_detached_request_isolated_lab_kat.v1"
)
RECEIPT_SCHEMA = (
    "agent_bridge.biocortex_ab_track_b_reference_provider_fault_injection_"
    "runner.signer_role_scope_authorization_synthetic_exact_owner_class_"
    "evidence_class_track_subject_audience_and_nonce_policy_verifier_"
    "isolated_lab_v1.receipt.v0"
)
STATUS = (
    "REFERENCE_PROVIDER_MANAGED_AND_SELF_HOSTED_FAULT_INJECTION_RUNNER_V1_"
    "SIGNER_ROLE_SCOPE_AUTHORIZATION_SYNTHETIC_EXACT_OWNER_CLASS_EVIDENCE_"
    "CLASS_TRACK_SUBJECT_AUDIENCE_AND_NONCE_POLICY_VERIFIED_ISOLATED_LAB_"
    "COMPONENT_ONLY_NO_PRODUCTION_AUTHORITY"
)
COMPONENT_STATE = (
    "AUTHORIZED_SYNTHETIC_KAT_SIGNER_FOR_EXACT_FROZEN_ROLE_SCOPE_COMPONENT_ONLY"
)
RECEIPT_HASH_DOMAIN = (
    "AB_TRACK_B_SIGNER_ROLE_SCOPE_AUTHORIZATION_ISOLATED_LAB_KAT_RECEIPT_V1"
)
MATCHING_PROFILE = "EXACT_ALL_FIELDS_ASCII_BYTE_EQUAL"
DEFAULT_EFFECT = "DENY"
ALLOW_EFFECT = "ALLOW"
DECLARED_ROLE_CLASS = "SYNTHETIC_EVIDENCE_ENVELOPE_SIGNER_KAT_ONLY"
OWNER_CLASS = "SYNTHETIC_KAT_EVIDENCE_REVIEW_OWNER_CLASS_V1"
EVIDENCE_CLASS = "SYNTHETIC_PRODUCTION_EVIDENCE_ENVELOPE_KAT"
TRUST_POLICY_SHA256 = "882f37d4862ed83bb8d91b218dec8c9b40861b35e3785620f873d9250f9d51b0"
TARGET_PRODUCTION_FAILURE_CODE = "E_PRODUCTION_SIGNER_AUTHORIZATION_FAILED"

MAX_AUTHENTICATION_BUNDLE_BYTES = 65_536
MAX_TRUST_POLICY_BYTES = 65_536
MAX_AUTHORIZATION_POLICY_BYTES = 65_536
MAX_AUTHORIZATION_REQUEST_BYTES = 16_384
MAX_SCOPE_STRING_UTF8_BYTES = 256
MAX_JSON_DEPTH = 32
MAX_JSON_NODES = 4_096
MAX_OBJECT_MEMBERS = 256
MAX_ARRAY_ITEMS = 64
MIN_SIGNED_INT64 = -(2**63)
MAX_SIGNED_INT64 = 2**63 - 1

AUTHORIZATION_POLICY_KEYS = (
    "default_effect",
    "deny_on_multiple_matches",
    "deny_on_zero_matches",
    "grants",
    "matching_profile",
    "schema",
    "schema_version",
)
AUTHORIZATION_GRANT_KEYS = (
    "audience",
    "authorization_policy_revision",
    "declared_role_class",
    "effect",
    "evidence_class",
    "frame_sha256",
    "grant_id",
    "nonce_scope",
    "owner_class",
    "predecessor_receipt_content_sha256",
    "revocation_snapshot_revision",
    "signer_key_id",
    "signer_key_version",
    "signer_role",
    "subject",
    "track_id",
    "trust_policy_sha256",
    "vector_set_id",
)
AUTHORIZATION_REQUEST_KEYS = (
    "audience",
    "evidence_class",
    "nonce_scope",
    "owner_class",
    "schema",
    "schema_version",
    "subject",
    "track_id",
)
REQUEST_SCOPE_FIELDS = (
    "owner_class",
    "evidence_class",
    "track_id",
    "subject",
    "audience",
    "nonce_scope",
)
REQUEST_SIGNER_FIELDS_FORBIDDEN = (
    "declared_role_class",
    "predecessor_receipt_content_sha256",
    "signer_key_id",
    "signer_key_version",
    "signer_role",
)
HEX_32_LENGTH = 64


@dataclass(frozen=True)
class AuthorizationProfile:
    track_id: str
    grant_id: str
    authorization_policy_revision: str
    frame_sha256: str
    predecessor_receipt_content_sha256: str
    revocation_snapshot_revision: str
    signer_key_id: str
    signer_key_version: str
    signer_role: str
    subject: str
    audience: str
    nonce_scope: str
    vector_set_id: str


AUTHORIZATION_PROFILES = (
    AuthorizationProfile(
        track_id="MANAGED_SPANNER_CLOUD_KMS",
        grant_id="KAT_MANAGED_SIGNER_ROLE_SCOPE_GRANT_V1",
        authorization_policy_revision=(
            "KAT_MANAGED_SIGNER_ROLE_SCOPE_AUTHORIZATION_POLICY_REVISION_1"
        ),
        frame_sha256="e298865e753a96d58b6c23d49b58cb2c4b512a519a65666d31170325bd34d295",
        predecessor_receipt_content_sha256=(
            "46a923e510a29ed144d0de092b8346585a4a857e009d042bb68da1003f681803"
        ),
        revocation_snapshot_revision="KAT_MANAGED_REVOCATION_SNAPSHOT_REVISION_1",
        signer_key_id="KAT_MANAGED_EVIDENCE_ENVELOPE_SIGNER_V2",
        signer_key_version="KAT_MANAGED_LEAF_KEY_VERSION_2",
        signer_role="KAT_MANAGED_EVIDENCE_ENVELOPE_SIGNER",
        subject="KAT_MANAGED_VALID_MINIMAL_FRAME_SUBJECT_V1",
        audience=(
            "AB_TRACK_B_MANAGED_FAULT_INJECTION_RUNNER_ISOLATED_LAB_"
            "AUTHORIZATION_KAT_V1"
        ),
        nonce_scope="KAT_MANAGED_SIGNER_ROLE_SCOPE_NONCE_V1_0001",
        vector_set_id=(
            "KAT_MANAGED_BOOTSTRAP_TRUST_PUBLIC_ONLY_PRECOMPUTED_VECTOR_SET_V1"
        ),
    ),
    AuthorizationProfile(
        track_id="SELF_HOSTED_ETCD_OPENBAO",
        grant_id="KAT_SELF_HOSTED_SIGNER_ROLE_SCOPE_GRANT_V1",
        authorization_policy_revision=(
            "KAT_SELF_HOSTED_SIGNER_ROLE_SCOPE_AUTHORIZATION_POLICY_REVISION_1"
        ),
        frame_sha256="da147c9e4bcb4ac54e98209f5ea2970322726d3d851ac415903e1dbe311da69e",
        predecessor_receipt_content_sha256=(
            "72d1e5c86fc99027427c78f1b2792d51e02461a6cc9b120f1d8baf877472e1c1"
        ),
        revocation_snapshot_revision=(
            "KAT_SELF_HOSTED_REVOCATION_SNAPSHOT_REVISION_1"
        ),
        signer_key_id="KAT_SELF_HOSTED_EVIDENCE_ENVELOPE_SIGNER_V2",
        signer_key_version="KAT_SELF_HOSTED_LEAF_KEY_VERSION_2",
        signer_role="KAT_SELF_HOSTED_EVIDENCE_ENVELOPE_SIGNER",
        subject="KAT_SELF_HOSTED_VALID_MINIMAL_FRAME_SUBJECT_V1",
        audience=(
            "AB_TRACK_B_SELF_HOSTED_FAULT_INJECTION_RUNNER_ISOLATED_LAB_"
            "AUTHORIZATION_KAT_V1"
        ),
        nonce_scope="KAT_SELF_HOSTED_SIGNER_ROLE_SCOPE_NONCE_V1_0001",
        vector_set_id=(
            "KAT_SELF_HOSTED_BOOTSTRAP_TRUST_PUBLIC_ONLY_PRECOMPUTED_VECTOR_SET_V1"
        ),
    ),
)


class SignerAuthorizationReviewError(ValueError):
    """Fail-closed review error with stable public and detail reason codes."""

    def __init__(self, code: str, detail: str, *, detail_code: str | None = None):
        super().__init__(f"{code}: {detail}")
        self.code = code
        self.detail = detail
        self.detail_code = detail_code


def _fail(code: str, detail: str) -> NoReturn:
    raise SignerAuthorizationReviewError(code, detail)


def _require(condition: bool, code: str, detail: str) -> None:
    if not condition:
        _fail(code, detail)


def _exact_keys(value: Mapping[str, Any], expected: tuple[str, ...], code: str) -> None:
    _require(
        type(value) is dict and set(value) == set(expected),
        code,
        "closed field set drift",
    )


def _reject_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        _require(
            type(key) is str and key not in result,
            "E_JSON_DUPLICATE_KEY",
            "duplicate or nonstring object key",
        )
        result[key] = value
    return result


def _parse_constant(value: str) -> NoReturn:
    _fail("E_JSON_NONFINITE", f"nonfinite number {value!r} forbidden")


def _parse_float(value: str) -> NoReturn:
    _fail("E_JSON_FLOAT", f"floating-point number {value!r} forbidden")


def _parse_int(value: str) -> int:
    parsed = int(value, 10)
    _require(
        MIN_SIGNED_INT64 <= parsed <= MAX_SIGNED_INT64,
        "E_JSON_INT_RANGE",
        "integer outside signed int64",
    )
    return parsed


def _shape(value: Any, depth: int = 1) -> tuple[int, int]:
    _require(depth <= MAX_JSON_DEPTH, "E_JSON_DEPTH", "maximum JSON depth exceeded")
    nodes = 1
    maximum_depth = depth
    if type(value) is dict:
        _require(
            len(value) <= MAX_OBJECT_MEMBERS,
            "E_JSON_OBJECT_MEMBERS",
            "too many object members",
        )
        for child in value.values():
            child_nodes, child_depth = _shape(child, depth + 1)
            nodes += child_nodes
            maximum_depth = max(maximum_depth, child_depth)
    elif type(value) is list:
        _require(
            len(value) <= MAX_ARRAY_ITEMS,
            "E_JSON_ARRAY_ITEMS",
            "too many array items",
        )
        for child in value:
            child_nodes, child_depth = _shape(child, depth + 1)
            nodes += child_nodes
            maximum_depth = max(maximum_depth, child_depth)
    else:
        _require(
            value is None or type(value) in (str, int, bool),
            "E_JSON_VALUE_TYPE",
            "unsupported JSON value",
        )
    _require(nodes <= MAX_JSON_NODES, "E_JSON_NODES", "too many JSON nodes")
    return nodes, maximum_depth


def _canonical_bytes(value: Mapping[str, Any]) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def _decode_closed_json(raw: bytes, *, limit: int, label: str) -> dict[str, Any]:
    _require(type(raw) is bytes, f"E_{label}_TYPE", f"{label} must be exact bytes")
    _require(
        0 < len(raw) <= limit,
        f"E_{label}_SIZE",
        f"{label} is empty or exceeds bound",
    )
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
    except SignerAuthorizationReviewError:
        raise
    except (json.JSONDecodeError, RecursionError) as error:
        _fail(f"E_{label}_JSON", str(error))
    _require(
        end == len(text),
        f"E_{label}_TRAILING",
        "trailing bytes or second value forbidden",
    )
    _require(type(value) is dict, f"E_{label}_ROOT", "root must be object")
    _shape(value)
    try:
        canonical = _canonical_bytes(value)
    except UnicodeEncodeError as error:
        _fail(f"E_{label}_UNICODE_SCALAR", str(error))
    _require(
        canonical == raw,
        f"E_{label}_NONCANONICAL",
        "input is not exact compact canonical JSON",
    )
    return value


def _reject_mode(mode: str) -> None:
    if type(mode) is not str:
        _fail(
            "E_SIGNER_AUTHORIZATION_MODE_UNKNOWN",
            "only exact string SYNTHETIC_KAT is reviewable",
        )
    if mode == PRODUCTION_MODE:
        _fail(
            "E_SIGNER_AUTHORIZATION_PRODUCTION_MODE_NOT_AUTHORIZED",
            "production signer authorization is outside isolated-lab authority",
        )
    if mode != SYNTHETIC_KAT_MODE:
        _fail(
            "E_SIGNER_AUTHORIZATION_MODE_UNKNOWN",
            "only SYNTHETIC_KAT is reviewable",
        )


def _ascii_scope(value: Any, *, field: str, expected: str | None = None) -> str:
    _require(type(value) is str, f"E_{field.upper()}_TYPE", f"{field} must be string")
    try:
        encoded = value.encode("ascii", "strict")
    except UnicodeEncodeError as error:
        _fail(f"E_{field.upper()}_ASCII", str(error))
    _require(
        0 < len(encoded) <= MAX_SCOPE_STRING_UTF8_BYTES,
        f"E_{field.upper()}_SIZE",
        f"{field} is empty or exceeds bound",
    )
    _require(
        "*" not in value and "?" not in value,
        f"E_{field.upper()}_WILDCARD",
        f"{field} wildcard tokens forbidden",
    )
    if expected is not None:
        _require(
            encoded == expected.encode("ascii"),
            f"E_{field.upper()}_EXACT",
            f"{field} exact value drift",
        )
    return value


def _grant_object(profile: AuthorizationProfile) -> dict[str, Any]:
    return {
        "audience": profile.audience,
        "authorization_policy_revision": profile.authorization_policy_revision,
        "declared_role_class": DECLARED_ROLE_CLASS,
        "effect": ALLOW_EFFECT,
        "evidence_class": EVIDENCE_CLASS,
        "frame_sha256": profile.frame_sha256,
        "grant_id": profile.grant_id,
        "nonce_scope": profile.nonce_scope,
        "owner_class": OWNER_CLASS,
        "predecessor_receipt_content_sha256": (
            profile.predecessor_receipt_content_sha256
        ),
        "revocation_snapshot_revision": profile.revocation_snapshot_revision,
        "signer_key_id": profile.signer_key_id,
        "signer_key_version": profile.signer_key_version,
        "signer_role": profile.signer_role,
        "subject": profile.subject,
        "track_id": profile.track_id,
        "trust_policy_sha256": TRUST_POLICY_SHA256,
        "vector_set_id": profile.vector_set_id,
    }


def known_answer_authorization_policy() -> dict[str, Any]:
    """Return the exact ordered public-only two-grant T06 KAT policy."""

    return {
        "default_effect": DEFAULT_EFFECT,
        "deny_on_multiple_matches": True,
        "deny_on_zero_matches": True,
        "grants": [_grant_object(profile) for profile in AUTHORIZATION_PROFILES],
        "matching_profile": MATCHING_PROFILE,
        "schema": AUTHORIZATION_POLICY_SCHEMA,
        "schema_version": 1,
    }


def known_answer_authorization_policy_bytes() -> bytes:
    return _canonical_bytes(known_answer_authorization_policy())


def known_answer_authorization_request(track_id: str) -> dict[str, Any]:
    """Return one exact detached six-dimension request for a frozen track."""

    profile = _profile_for_track(track_id)
    return {
        "audience": profile.audience,
        "evidence_class": EVIDENCE_CLASS,
        "nonce_scope": profile.nonce_scope,
        "owner_class": OWNER_CLASS,
        "schema": AUTHORIZATION_REQUEST_SCHEMA,
        "schema_version": 1,
        "subject": profile.subject,
        "track_id": profile.track_id,
    }


def known_answer_authorization_request_bytes(track_id: str) -> bytes:
    return _canonical_bytes(known_answer_authorization_request(track_id))


def _profile_for_track(track_id: str) -> AuthorizationProfile:
    for profile in AUTHORIZATION_PROFILES:
        if track_id == profile.track_id:
            return profile
    _fail("E_AUTHORIZATION_TRACK_UNKNOWN", "track is not a frozen KAT profile")


def _validate_lower_hex_32(value: Any, field: str) -> None:
    _require(
        type(value) is str
        and len(value) == HEX_32_LENGTH
        and all(character in "0123456789abcdef" for character in value),
        f"E_AUTHORIZATION_GRANT_{field.upper()}",
        f"{field} must be lowercase SHA-256 hex",
    )


def _validate_policy(policy: Mapping[str, Any]) -> tuple[Mapping[str, Any], ...]:
    _exact_keys(policy, AUTHORIZATION_POLICY_KEYS, "E_AUTHORIZATION_POLICY_FIELDS")
    _require(
        policy["schema"] == AUTHORIZATION_POLICY_SCHEMA
        and type(policy["schema"]) is str,
        "E_AUTHORIZATION_POLICY_SCHEMA",
        "policy schema drift",
    )
    _require(
        type(policy["schema_version"]) is int and policy["schema_version"] == 1,
        "E_AUTHORIZATION_POLICY_SCHEMA_VERSION",
        "policy schema version drift",
    )
    _require(
        policy["default_effect"] == DEFAULT_EFFECT
        and type(policy["default_effect"]) is str,
        "E_AUTHORIZATION_POLICY_DEFAULT",
        "default effect must be exact DENY",
    )
    _require(
        policy["matching_profile"] == MATCHING_PROFILE
        and type(policy["matching_profile"]) is str,
        "E_AUTHORIZATION_POLICY_MATCHING_PROFILE",
        "matching profile drift",
    )
    _require(
        policy["deny_on_zero_matches"] is True,
        "E_AUTHORIZATION_POLICY_ZERO_MATCH",
        "zero matches must deny",
    )
    _require(
        policy["deny_on_multiple_matches"] is True,
        "E_AUTHORIZATION_POLICY_MULTIPLE_MATCH",
        "multiple matches must deny",
    )
    grants = policy["grants"]
    _require(
        type(grants) is list and len(grants) == 2,
        "E_AUTHORIZATION_POLICY_GRANTS",
        "exactly two ordered grants required",
    )
    validated: list[Mapping[str, Any]] = []
    for grant, profile in zip(grants, AUTHORIZATION_PROFILES, strict=True):
        _require(
            type(grant) is dict,
            "E_AUTHORIZATION_GRANT_OBJECT",
            "grant must be object",
        )
        _exact_keys(grant, AUTHORIZATION_GRANT_KEYS, "E_AUTHORIZATION_GRANT_FIELDS")
        expected = _grant_object(profile)
        for field, expected_value in expected.items():
            _ascii_scope(grant[field], field=f"authorization_grant_{field}")
            _require(
                grant[field].encode("ascii") == expected_value.encode("ascii"),
                f"E_AUTHORIZATION_GRANT_{field.upper()}_EXACT",
                f"{field} exact KAT binding drift",
            )
        for hash_field in (
            "frame_sha256",
            "predecessor_receipt_content_sha256",
            "trust_policy_sha256",
        ):
            _validate_lower_hex_32(grant[hash_field], hash_field)
        validated.append(grant)
    _require(
        grants[0]["track_id"] != grants[1]["track_id"]
        and grants[0]["grant_id"] != grants[1]["grant_id"],
        "E_AUTHORIZATION_POLICY_DISTINCTNESS",
        "two distinct ordered profiles required",
    )
    return tuple(validated)


def _validate_request(request: Mapping[str, Any]) -> Mapping[str, Any]:
    _exact_keys(request, AUTHORIZATION_REQUEST_KEYS, "E_AUTHORIZATION_REQUEST_FIELDS")
    _require(
        request["schema"] == AUTHORIZATION_REQUEST_SCHEMA
        and type(request["schema"]) is str,
        "E_AUTHORIZATION_REQUEST_SCHEMA",
        "request schema drift",
    )
    _require(
        type(request["schema_version"]) is int and request["schema_version"] == 1,
        "E_AUTHORIZATION_REQUEST_SCHEMA_VERSION",
        "request schema version drift",
    )
    for field in REQUEST_SCOPE_FIELDS:
        _ascii_scope(request[field], field=f"authorization_request_{field}")
    return request


def _select_grant(
    grants: tuple[Mapping[str, Any], ...],
    request: Mapping[str, Any],
) -> Mapping[str, Any]:
    matches = [
        grant
        for grant in grants
        if all(
            grant[field].encode("ascii") == request[field].encode("ascii")
            for field in REQUEST_SCOPE_FIELDS
        )
    ]
    _require(
        len(matches) != 0,
        "E_SIGNER_ROLE_SCOPE_AUTHORIZATION_ZERO_MATCH_DENY",
        "default DENY: no exact six-dimension grant",
    )
    _require(
        len(matches) == 1,
        "E_SIGNER_ROLE_SCOPE_AUTHORIZATION_MULTIPLE_MATCH_DENY",
        "ambiguous multiple matching grants denied",
    )
    return matches[0]


def _bind_predecessor_receipt(
    receipt: Mapping[str, Any],
    grant: Mapping[str, Any],
) -> None:
    expected = {
        "active_leaf_key_id": grant["signer_key_id"],
        "active_leaf_key_version": grant["signer_key_version"],
        "content_sha256": grant["predecessor_receipt_content_sha256"],
        "declared_role": grant["declared_role_class"],
        "frame_sha256": grant["frame_sha256"],
        "mapped_policy_leaf_role": grant["signer_role"],
        "revocation_snapshot_revision": grant["revocation_snapshot_revision"],
        "track_id": grant["track_id"],
        "track_leaf_role": grant["signer_role"],
        "trust_policy_sha256": grant["trust_policy_sha256"],
        "vector_set_id": grant["vector_set_id"],
    }
    for field, expected_value in expected.items():
        _require(
            receipt.get(field) == expected_value
            and type(receipt.get(field)) is str,
            f"E_PREDECESSOR_RECEIPT_{field.upper()}_BINDING",
            f"T05 receipt {field} does not bind selected grant",
        )
    expected_scalars = {
        "component_state": predecessor.COMPONENT_STATE,
        "declared_role_cryptographically_authenticated_in_kat": True,
        "declared_role_is_role_scope_authorization": False,
        "execution_mode": SYNTHETIC_KAT_MODE,
        "frozen_revocation_snapshot_is_currentness": False,
        "isolated_lab_candidate_surface_components_implemented": 3,
        "local_t05_specification_exercised": True,
        "local_t06_specification_exercised": False,
        "production_admissible": False,
        "provider_authority": False,
        "schema": predecessor.RECEIPT_SCHEMA,
        "schema_version": 1,
        "signature_verification_count": 1,
        "runtime_authority": False,
        "signer_role_scope_authorization_implemented": False,
        "synthetic_fixture": True,
    }
    for field, expected_value in expected_scalars.items():
        _require(
            type(receipt.get(field)) is type(expected_value)
            and receipt.get(field) == expected_value,
            f"E_PREDECESSOR_RECEIPT_{field.upper()}_BINDING",
            f"T05 receipt {field} truth drift",
        )


def _domain_sha256(domain: str, raw: bytes) -> str:
    return hashlib.sha256(domain.encode("ascii") + b"\x00" + raw).hexdigest()


def review_signer_role_scope_authorization(
    frame: bytes,
    detached_authentication_bundle: bytes,
    separately_injected_synthetic_trust_policy: bytes,
    separately_injected_synthetic_signer_authorization_policy: bytes,
    detached_authorization_request: bytes,
    mode: str,
) -> dict[str, Any]:
    """Review one exact isolated-lab T06 KAT or fail closed."""

    _reject_mode(mode)

    try:
        predecessor_receipt = predecessor.review_bootstrap_trust_authentication(
            frame,
            detached_authentication_bundle,
            separately_injected_synthetic_trust_policy,
            predecessor.SYNTHETIC_KAT_MODE,
        )
    except predecessor.BootstrapTrustReviewError as error:
        raise SignerAuthorizationReviewError(
            "E_PREDECESSOR_AUTHENTICATION_REJECTED",
            f"{error.code}: {error.detail}",
            detail_code=error.code,
        ) from error

    try:
        authorization_policy = _decode_closed_json(
            separately_injected_synthetic_signer_authorization_policy,
            limit=MAX_AUTHORIZATION_POLICY_BYTES,
            label="AUTHORIZATION_POLICY",
        )
        grants = _validate_policy(authorization_policy)
    except SignerAuthorizationReviewError as error:
        raise SignerAuthorizationReviewError(
            "E_SIGNER_AUTHORIZATION_POLICY_REJECTED",
            f"{error.code}: {error.detail}",
            detail_code=error.code,
        ) from error

    try:
        authorization_request = _decode_closed_json(
            detached_authorization_request,
            limit=MAX_AUTHORIZATION_REQUEST_BYTES,
            label="AUTHORIZATION_REQUEST",
        )
        request = _validate_request(authorization_request)
        selected_grant = _select_grant(grants, request)
        _bind_predecessor_receipt(predecessor_receipt, selected_grant)
    except SignerAuthorizationReviewError as error:
        raise SignerAuthorizationReviewError(
            "E_SIGNER_ROLE_SCOPE_AUTHORIZATION_FAILED",
            f"{error.code}: {error.detail}",
            detail_code=error.code,
        ) from error

    receipt: dict[str, Any] = {
        "action_or_resource_capability_authorized": False,
        "audience": request["audience"],
        "audience_identity_authenticated": False,
        "authorization_decision": ALLOW_EFFECT,
        "authorization_grant_count": len(grants),
        "authorization_match_count": 1,
        "authorization_policy_is_production_policy": False,
        "authorization_policy_revision": selected_grant[
            "authorization_policy_revision"
        ],
        "authorization_policy_separately_injected": True,
        "authorization_policy_sha256": hashlib.sha256(
            separately_injected_synthetic_signer_authorization_policy
        ).hexdigest(),
        "authorization_request_detached": True,
        "authorization_request_observed_after_policy": True,
        "authorization_request_sha256": hashlib.sha256(
            detached_authorization_request
        ).hexdigest(),
        "authorization_request_signer_field_count": 0,
        "bootstrap_trust_authentication_implemented": True,
        "caller_supplied_predecessor_receipt_accepted": False,
        "component_state": COMPONENT_STATE,
        "condition_output_authorized": False,
        "content_sha256": "0" * 64,
        "declared_role_class": predecessor_receipt["declared_role"],
        "default_effect": DEFAULT_EFFECT,
        "deny_on_multiple_matches": True,
        "deny_on_zero_matches": True,
        "detached_authentication_bundle_sha256": predecessor_receipt[
            "detached_authentication_bundle_sha256"
        ],
        "downstream_gate_count": 4,
        "downstream_gates_authorized": 0,
        "durable_replay_cas_implemented": False,
        "evidence_acceptance_authorized": False,
        "evidence_class": request["evidence_class"],
        "execution_mode": SYNTHETIC_KAT_MODE,
        "fault_injection_authorized": False,
        "frame_sha256": predecessor_receipt["frame_sha256"],
        "grant_id": selected_grant["grant_id"],
        "isolated_lab_candidate_surface_component_total": 4,
        "isolated_lab_candidate_surface_components_implemented": 4,
        "isolated_lab_candidate_surface_components_locally_kat_exercised": 4,
        "local_t05_specification_exercised": True,
        "local_t06_specification_exercised": True,
        "local_t07_specification_exercised": False,
        "local_t08_specification_exercised": False,
        "local_t09_specification_exercised": False,
        "local_threat_specifications_covered": 6,
        "local_threat_specifications_covered_ids": [
            "T01",
            "T02",
            "T03",
            "T04",
            "T05",
            "T06",
        ],
        "matching_profile": MATCHING_PROFILE,
        "nonce_fixed_public_kat_equality_only": True,
        "nonce_freshness_proved": False,
        "nonce_generation_authorized": False,
        "nonce_replay_protection_proved": False,
        "nonce_scope": request["nonce_scope"],
        "nonce_single_use_proved": False,
        "output_or_claim_authorized": False,
        "owner_class": request["owner_class"],
        "owner_class_is_authenticated_owner_identity": False,
        "predecessor_receipt_content_sha256": predecessor_receipt[
            "content_sha256"
        ],
        "predecessor_review_count": 1,
        "production_admissible": False,
        "production_ingestion_control_count": 14,
        "production_ingestion_controls_implemented": 0,
        "production_ingestion_controls_runtime_exercised": 0,
        "production_signer_role_scope_authorization_implemented": False,
        "production_threat_specification_count": 20,
        "production_threat_specifications_runtime_exercised": 0,
        "production_validated_evidence_items": 0,
        "provider_authority": False,
        "real_evidence_items_present": 0,
        "request_scope_dimension_count": len(REQUEST_SCOPE_FIELDS),
        "request_scope_fields": list(REQUEST_SCOPE_FIELDS),
        "revocation_snapshot_revision": predecessor_receipt[
            "revocation_snapshot_revision"
        ],
        "runtime_authority": False,
        "runtime_prerequisite_count": 16,
        "runtime_prerequisites_satisfied": 0,
        "schema": RECEIPT_SCHEMA,
        "schema_version": 1,
        "scope_label_truth_proved": False,
        "separately_injected_trust_policy": True,
        "side_effects_unlocked": "NONE",
        "signer_identity_source": "T05_PREDECESSOR_RECEIPT_ONLY",
        "signer_key_id": predecessor_receipt["active_leaf_key_id"],
        "signer_key_version": predecessor_receipt["active_leaf_key_version"],
        "signer_role": predecessor_receipt["track_leaf_role"],
        "signer_role_scope_authorization_isolated_lab_component_implemented": True,
        "status": STATUS,
        "subject": request["subject"],
        "subject_label_truth_proved": False,
        "synthetic_fixture": True,
        "t07_track_profile_binding_implemented": False,
        "t08_end_to_end_subject_binding_implemented": False,
        "t09_content_identity_and_quarantine_custody_implemented": False,
        "target_production_failure_code": TARGET_PRODUCTION_FAILURE_CODE,
        "target_production_control": "SIGNER_ROLE_SCOPE_AUTHORIZATION",
        "track_id": request["track_id"],
        "track_is_provider_profile_currentness": False,
        "track_subject_binding_implemented": False,
        "trust_policy_sha256": predecessor_receipt["trust_policy_sha256"],
        "upstream_decision_record_t09_replay_cas_implemented": False,
        "vector_set_id": predecessor_receipt["vector_set_id"],
        "wildcard_prefix_hierarchy_or_inheritance_authorization_implemented": False,
    }
    receipt_without_hash = dict(receipt)
    del receipt_without_hash["content_sha256"]
    receipt["content_sha256"] = _domain_sha256(
        RECEIPT_HASH_DOMAIN,
        _canonical_bytes(receipt_without_hash),
    )
    return receipt


__all__ = [
    "ALLOW_EFFECT",
    "AUTHORIZATION_POLICY_SCHEMA",
    "AUTHORIZATION_PROFILES",
    "AUTHORIZATION_REQUEST_SCHEMA",
    "COMPONENT_STATE",
    "DEFAULT_EFFECT",
    "MATCHING_PROFILE",
    "PRODUCTION_MODE",
    "RECEIPT_SCHEMA",
    "REQUEST_SCOPE_FIELDS",
    "SignerAuthorizationReviewError",
    "STATUS",
    "SYNTHETIC_KAT_MODE",
    "known_answer_authorization_policy",
    "known_answer_authorization_policy_bytes",
    "known_answer_authorization_request",
    "known_answer_authorization_request_bytes",
    "review_signer_role_scope_authorization",
]
