#!/usr/bin/env python3
"""Pure isolated-lab T09 five-identity verifier.

The twelve-input public entrypoint observes ``mode`` first, invokes the frozen
T08 public reviewer exactly once, derives five identities from the unchanged
accepted frame and the real T08 receipt, validates a separately injected
closed-world two-profile policy, and observes the detached T09 request last.

This is a public-only synthetic KAT.  It binds identity labels; it does not
authenticate real content, canonicalize production payloads, create custody,
retention, tombstone or replay storage, or grant provider/runtime authority.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Mapping, NoReturn

import biocortex_ab_track_b_reference_provider_fault_injection_runner_end_to_end_subject_binding_synthetic_exact_t07_receipt_track_prerequisite_source_build_session_channel_schedule_row_set_and_subject_verifier_isolated_lab_v1 as predecessor


SYNTHETIC_KAT_MODE = "SYNTHETIC_KAT"
PRODUCTION_MODE = "PRODUCTION"
POLICY_SCHEMA = (
    "agent_bridge.biocortex_ab_track_b_reference_provider_fault_injection_"
    "runner.content_identity_and_quarantine_custody_synthetic_policy_"
    "isolated_lab_kat.v1"
)
RECEIPT_SCHEMA = (
    "agent_bridge.biocortex_ab_track_b_reference_provider_fault_injection_"
    "runner.content_identity_and_quarantine_custody_synthetic_exact_t08_"
    "receipt_five_identity_verifier_isolated_lab_v1.receipt.v0"
)
STATUS = (
    "REFERENCE_PROVIDER_MANAGED_AND_SELF_HOSTED_FAULT_INJECTION_RUNNER_V1_"
    "CONTENT_IDENTITY_AND_QUARANTINE_CUSTODY_SYNTHETIC_EXACT_T08_RECEIPT_"
    "RAW_FRAME_SHA256_CANONICAL_FRAME_SHA256_PACKET_ID_SHA256_SIGNATURE_"
    "SUBJECT_SHA256_AND_VALIDATION_SUBJECT_SHA256_VERIFIED_ISOLATED_LAB_"
    "COMPONENT_ONLY_NO_PRODUCTION_AUTHORITY"
)
COMPONENT_STATE = (
    "BOUND_FIVE_SYNTHETIC_CONTENT_IDENTITIES_TO_EXACT_FRAME_AND_T08_"
    "RECEIPT_CHAIN_ONLY"
)
AUTHORIZED_UNIT = (
    "REFERENCE_PROVIDER_MANAGED_AND_SELF_HOSTED_FAULT_INJECTION_RUNNER_V1_"
    "CONTENT_IDENTITY_AND_QUARANTINE_CUSTODY_SYNTHETIC_EXACT_T08_RECEIPT_"
    "RAW_FRAME_SHA256_CANONICAL_FRAME_SHA256_PACKET_ID_SHA256_SIGNATURE_"
    "SUBJECT_SHA256_AND_VALIDATION_SUBJECT_SHA256_VERIFIER_ISOLATED_LAB_"
    "IMPLEMENTATION"
)
RECEIPT_HASH_DOMAIN = "AB_TRACK_B_T09_ISOLATED_LAB_KAT_RECEIPT_V1"
PACKET_ID_DOMAIN = "AB_TRACK_B_T09_SYNTHETIC_PACKET_ID_V1"
MATCHING_PROFILE = "EXACT_ALL_FIELDS_ASCII_BYTE_EQUAL"
DEFAULT_DISPOSITION = "REJECTED_FAIL_CLOSED"
TARGET_PRODUCTION_CONTROL = "QUARANTINE_CUSTODY"
TARGET_PRODUCTION_FAILURE_CODE = "E_PRODUCTION_CUSTODY_FAILED"

MAX_POLICY_BYTES = 65_536
MAX_REQUEST_BYTES = 16_384
MAX_INPUT_FRAME_BYTES = 1_048_576
MAX_PROFILE_STRING_UTF8_BYTES = 256
MAX_JSON_DEPTH = 32
MAX_JSON_NODES = 4_096
MAX_OBJECT_MEMBERS = 256
MAX_ARRAY_ITEMS = 64
MIN_SIGNED_INT64 = -(2**63)
MAX_SIGNED_INT64 = 2**63 - 1

POLICY_KEYS = (
    "default_disposition",
    "matching_profile",
    "profiles",
    "reject_on_multiple_matches",
    "reject_on_zero_matches",
    "schema",
    "schema_version",
)
PROFILE_FIELDS = (
    "t08_receipt_content_sha256",
    "track_id",
    "raw_frame_sha256",
    "canonical_frame_sha256",
    "packet_id_sha256",
    "signature_subject_sha256",
    "validation_subject_sha256",
)
REQUEST_FIELDS = (
    "raw_frame_sha256",
    "canonical_frame_sha256",
    "packet_id_sha256",
    "signature_subject_sha256",
    "validation_subject_sha256",
)


@dataclass(frozen=True)
class ContentIdentityProfile:
    track_id: str
    t08_receipt_content_sha256: str
    raw_frame_sha256: str
    canonical_frame_sha256: str
    packet_id_sha256: str
    signature_subject_sha256: str
    validation_subject_sha256: str
    signature_domain: str


PROFILES = (
    ContentIdentityProfile(
        track_id="MANAGED_SPANNER_CLOUD_KMS",
        t08_receipt_content_sha256=(
            "7bf4b4151a12428da34eb5a095d340a4b5a1c531381385bf262cb1d5df7415b9"
        ),
        raw_frame_sha256=(
            "e298865e753a96d58b6c23d49b58cb2c4b512a519a65666d31170325bd34d295"
        ),
        canonical_frame_sha256=(
            "e298865e753a96d58b6c23d49b58cb2c4b512a519a65666d31170325bd34d295"
        ),
        packet_id_sha256=(
            "f89f204c4dcb19e078a4448d8824ca8e7435688e06c5e57265789e273104571e"
        ),
        signature_subject_sha256=(
            "a52aa400add05bb7b545c9eddbf1f48e55befd393f07c5c6ba6baaefd4f5343b"
        ),
        validation_subject_sha256=(
            "7bf4b4151a12428da34eb5a095d340a4b5a1c531381385bf262cb1d5df7415b9"
        ),
        signature_domain=(
            "AB_TRACK_B_BOOTSTRAP_TRUST_AUTHENTICATION_ISOLATED_LAB_MANAGED_"
            "KAT_SIGNATURE_V1"
        ),
    ),
    ContentIdentityProfile(
        track_id="SELF_HOSTED_ETCD_OPENBAO",
        t08_receipt_content_sha256=(
            "77e9eadcc83235e9f5b0357e9ca15b046c4044d36e764583b481bc7fb2c29865"
        ),
        raw_frame_sha256=(
            "da147c9e4bcb4ac54e98209f5ea2970322726d3d851ac415903e1dbe311da69e"
        ),
        canonical_frame_sha256=(
            "da147c9e4bcb4ac54e98209f5ea2970322726d3d851ac415903e1dbe311da69e"
        ),
        packet_id_sha256=(
            "16f3d9bb3c69666d374e72f16036f5fe152ab73d864c051e57429fe4f09308bc"
        ),
        signature_subject_sha256=(
            "2eb3584afe6c8f18281224785ec083e531da37eed71524f2eedbf3a8225055ac"
        ),
        validation_subject_sha256=(
            "77e9eadcc83235e9f5b0357e9ca15b046c4044d36e764583b481bc7fb2c29865"
        ),
        signature_domain=(
            "AB_TRACK_B_BOOTSTRAP_TRUST_AUTHENTICATION_ISOLATED_LAB_SELF_"
            "HOSTED_KAT_SIGNATURE_V1"
        ),
    ),
)


class ContentIdentityReviewError(ValueError):
    """Fail-closed error with stable public and nested detail codes."""

    def __init__(self, code: str, detail: str, *, detail_code: str | None = None):
        super().__init__(f"{code}: {detail}")
        self.code = code
        self.detail = detail
        self.detail_code = detail_code


def _fail(code: str, detail: str) -> NoReturn:
    raise ContentIdentityReviewError(code, detail)


def _require(condition: bool, code: str, detail: str) -> None:
    if not condition:
        _fail(code, detail)


def _reject_mode(mode: str) -> None:
    if type(mode) is not str:
        _fail("E_CONTENT_IDENTITY_MODE_UNKNOWN", "mode must be exact string SYNTHETIC_KAT")
    if mode == PRODUCTION_MODE:
        _fail(
            "E_CONTENT_IDENTITY_PRODUCTION_MODE_NOT_AUTHORIZED",
            "production custody is outside isolated-lab authority",
        )
    if mode != SYNTHETIC_KAT_MODE:
        _fail("E_CONTENT_IDENTITY_MODE_UNKNOWN", "only SYNTHETIC_KAT is reviewable")


def _exact_keys(value: Mapping[str, Any], expected: tuple[str, ...], code: str) -> None:
    _require(type(value) is dict and set(value) == set(expected), code, "closed field set drift")


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
        _require(
            value is None or type(value) in (str, int, bool),
            "E_JSON_VALUE_TYPE",
            "unsupported JSON value",
        )
    _require(nodes <= MAX_JSON_NODES, "E_JSON_NODES", "too many JSON nodes")
    return nodes, maximum_depth


def _canonical_bytes(value: Mapping[str, Any]) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _decode_closed_json(raw: bytes, *, limit: int, label: str) -> dict[str, Any]:
    _require(type(raw) is bytes, f"E_{label}_TYPE", f"{label} must be exact bytes")
    _require(0 < len(raw) <= limit, f"E_{label}_SIZE", f"{label} exceeds bound")
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
    except ContentIdentityReviewError:
        raise
    except (json.JSONDecodeError, RecursionError) as error:
        _fail(f"E_{label}_JSON", str(error))
    _require(end == len(text), f"E_{label}_TRAILING", "trailing bytes forbidden")
    _require(type(value) is dict, f"E_{label}_ROOT", "root must be object")
    _shape(value)
    try:
        canonical = _canonical_bytes(value)
    except UnicodeEncodeError as error:
        _fail(f"E_{label}_UNICODE_SCALAR", str(error))
    _require(canonical == raw, f"E_{label}_NONCANONICAL", "exact canonical JSON required")
    return value


def _ascii(value: Any, *, field: str) -> str:
    _require(type(value) is str, f"E_{field.upper()}_TYPE", f"{field} must be string")
    try:
        encoded = value.encode("ascii", "strict")
    except UnicodeEncodeError as error:
        _fail(f"E_{field.upper()}_ASCII", str(error))
    _require(0 < len(encoded) <= MAX_PROFILE_STRING_UTF8_BYTES, f"E_{field.upper()}_SIZE", "value size drift")
    _require(value == value.strip(), f"E_{field.upper()}_TRIM", "value must be trimmed")
    _require("*" not in value and "?" not in value, f"E_{field.upper()}_WILDCARD", "wildcards forbidden")
    return value


def _lower_sha256(value: Any, *, field: str) -> str:
    observed = _ascii(value, field=field)
    _require(
        len(observed) == 64 and all(character in "0123456789abcdef" for character in observed),
        f"E_{field.upper()}_LOWER_SHA256",
        f"{field} must be lowercase SHA-256 hex",
    )
    return observed


def _profile_object(profile: ContentIdentityProfile) -> dict[str, str]:
    return {field: getattr(profile, field) for field in PROFILE_FIELDS}


def known_answer_content_identity_policy() -> dict[str, Any]:
    return {
        "default_disposition": DEFAULT_DISPOSITION,
        "matching_profile": MATCHING_PROFILE,
        "profiles": [_profile_object(profile) for profile in PROFILES],
        "reject_on_multiple_matches": True,
        "reject_on_zero_matches": True,
        "schema": POLICY_SCHEMA,
        "schema_version": 1,
    }


def known_answer_content_identity_policy_bytes() -> bytes:
    return _canonical_bytes(known_answer_content_identity_policy())


def _profile_for_track(track_id: str) -> ContentIdentityProfile:
    for profile in PROFILES:
        if profile.track_id == track_id:
            return profile
    _fail("E_CONTENT_IDENTITY_TRACK_UNKNOWN", "track is not a frozen KAT profile")


def known_answer_content_identity_request(track_id: str) -> dict[str, str]:
    profile = _profile_for_track(track_id)
    return {field: getattr(profile, field) for field in REQUEST_FIELDS}


def known_answer_content_identity_request_bytes(track_id: str) -> bytes:
    return _canonical_bytes(known_answer_content_identity_request(track_id))


def _validate_policy(policy: Mapping[str, Any]) -> tuple[Mapping[str, Any], ...]:
    _exact_keys(policy, POLICY_KEYS, "E_CONTENT_IDENTITY_POLICY_FIELDS")
    _require(type(policy["schema"]) is str and policy["schema"] == POLICY_SCHEMA, "E_CONTENT_IDENTITY_POLICY_SCHEMA", "schema drift")
    _require(type(policy["schema_version"]) is int and policy["schema_version"] == 1, "E_CONTENT_IDENTITY_POLICY_SCHEMA_VERSION", "version drift")
    _require(type(policy["default_disposition"]) is str and policy["default_disposition"] == DEFAULT_DISPOSITION, "E_CONTENT_IDENTITY_POLICY_DEFAULT", "default deny required")
    _require(type(policy["matching_profile"]) is str and policy["matching_profile"] == MATCHING_PROFILE, "E_CONTENT_IDENTITY_POLICY_MATCHING", "exact matching required")
    _require(policy["reject_on_zero_matches"] is True, "E_CONTENT_IDENTITY_POLICY_ZERO_MATCH", "zero matches must reject")
    _require(policy["reject_on_multiple_matches"] is True, "E_CONTENT_IDENTITY_POLICY_MULTIPLE_MATCH", "multiple matches must reject")
    profiles = policy["profiles"]
    _require(type(profiles) is list and len(profiles) == 2, "E_CONTENT_IDENTITY_POLICY_PROFILES", "two ordered profiles required")
    for candidate, frozen in zip(profiles, PROFILES, strict=True):
        _require(type(candidate) is dict, "E_CONTENT_IDENTITY_PROFILE_OBJECT", "profile must be object")
        _exact_keys(candidate, PROFILE_FIELDS, "E_CONTENT_IDENTITY_PROFILE_FIELDS")
        expected = _profile_object(frozen)
        for field in PROFILE_FIELDS:
            observed = _ascii(candidate[field], field=f"content_identity_profile_{field}")
            _require(observed.encode("ascii") == expected[field].encode("ascii"), f"E_CONTENT_IDENTITY_PROFILE_{field.upper()}_EXACT", "frozen profile drift")
        for field in PROFILE_FIELDS:
            if field != "track_id":
                _lower_sha256(candidate[field], field=f"content_identity_profile_{field}")
    _require(profiles[0]["track_id"] != profiles[1]["track_id"], "E_CONTENT_IDENTITY_POLICY_DISTINCTNESS", "distinct profiles required")
    return tuple(profiles)


def _validate_request(request: Mapping[str, Any]) -> Mapping[str, Any]:
    _exact_keys(request, REQUEST_FIELDS, "E_CONTENT_IDENTITY_REQUEST_FIELDS")
    for field in REQUEST_FIELDS:
        _lower_sha256(request[field], field=f"content_identity_request_{field}")
    return request


def _length_prefixed_subject(domain: str, frame: bytes) -> bytes:
    encoded_domain = domain.encode("ascii")
    return (
        len(encoded_domain).to_bytes(8, "big")
        + encoded_domain
        + len(frame).to_bytes(8, "big")
        + frame
    )


def _derive_identities(frame: bytes, predecessor_receipt: Mapping[str, Any]) -> dict[str, str]:
    _require(type(frame) is bytes and len(frame) <= MAX_INPUT_FRAME_BYTES, "E_FRAME_BINDING", "exact bounded frame required")
    track_id = predecessor_receipt.get("track_id")
    content_sha256 = predecessor_receipt.get("content_sha256")
    _require(type(track_id) is str, "E_T08_RECEIPT_TRACK_ID_BINDING", "T08 track missing")
    _require(type(content_sha256) is str, "E_T08_RECEIPT_CONTENT_SHA256_BINDING", "T08 content identity missing")
    profile = _profile_for_track(track_id)
    raw_sha256 = hashlib.sha256(frame).hexdigest()
    return {
        "raw_frame_sha256": raw_sha256,
        "canonical_frame_sha256": raw_sha256,
        "packet_id_sha256": hashlib.sha256(_length_prefixed_subject(PACKET_ID_DOMAIN, frame)).hexdigest(),
        "signature_subject_sha256": hashlib.sha256(_length_prefixed_subject(profile.signature_domain, frame)).hexdigest(),
        "validation_subject_sha256": content_sha256,
    }


def _select_profile(
    profiles: tuple[Mapping[str, Any], ...],
    predecessor_receipt: Mapping[str, Any],
    derived: Mapping[str, str],
    request: Mapping[str, Any],
) -> Mapping[str, Any]:
    match_values = {
        "t08_receipt_content_sha256": predecessor_receipt.get("content_sha256"),
        "track_id": predecessor_receipt.get("track_id"),
        **{field: request[field] for field in REQUEST_FIELDS},
    }
    for field in REQUEST_FIELDS:
        _require(request[field] == derived[field], f"E_CONTENT_IDENTITY_DERIVED_{field.upper()}_BINDING", "detached identity differs from exact derived identity")
    matches = [
        profile
        for profile in profiles
        if all(profile[field].encode("ascii") == match_values[field].encode("ascii") for field in PROFILE_FIELDS)
    ]
    _require(len(matches) != 0, "E_CONTENT_IDENTITY_ZERO_MATCH_DENY", "no exact seven-dimension profile")
    _require(len(matches) == 1, "E_CONTENT_IDENTITY_MULTIPLE_MATCH_DENY", "ambiguous profiles rejected")
    return matches[0]


def _bind_predecessor_receipt(receipt: Mapping[str, Any], profile: Mapping[str, Any]) -> None:
    expected_strings = {
        "content_sha256": profile["t08_receipt_content_sha256"],
        "execution_mode": SYNTHETIC_KAT_MODE,
        "schema": predecessor.RECEIPT_SCHEMA,
        "track_id": profile["track_id"],
    }
    for field, expected in expected_strings.items():
        _require(type(receipt.get(field)) is str and receipt.get(field) == expected, f"E_T08_RECEIPT_{field.upper()}_BINDING", f"T08 {field} drift")
    expected_scalars: dict[str, Any] = {
        "end_to_end_subject_binding_isolated_lab_component_implemented": True,
        "isolated_lab_candidate_surface_component_total": 6,
        "isolated_lab_candidate_surface_components_implemented": 6,
        "local_t08_specification_exercised": True,
        "local_t09_specification_exercised": False,
        "production_admissible": False,
        "production_track_subject_binding_implemented": False,
        "provider_authority": False,
        "runtime_authority": False,
        "t08_end_to_end_subject_binding_implemented": True,
        "t09_content_identity_and_quarantine_custody_implemented": False,
    }
    for field, expected in expected_scalars.items():
        _require(type(receipt.get(field)) is type(expected) and receipt.get(field) == expected, f"E_T08_RECEIPT_{field.upper()}_BINDING", f"T08 {field} truth drift")


def _domain_sha256(domain: str, raw: bytes) -> str:
    return hashlib.sha256(domain.encode("ascii") + b"\x00" + raw).hexdigest()


def review_content_identity_and_quarantine_custody(
    frame: bytes,
    detached_authentication_bundle: bytes,
    separately_injected_synthetic_trust_policy: bytes,
    separately_injected_synthetic_signer_authorization_policy: bytes,
    detached_authorization_request: bytes,
    separately_injected_synthetic_track_profile_binding_policy: bytes,
    detached_track_profile_binding_request: bytes,
    separately_injected_synthetic_end_to_end_subject_binding_policy: bytes,
    detached_end_to_end_subject_binding_request: bytes,
    separately_injected_synthetic_content_identity_and_quarantine_custody_policy: bytes,
    detached_content_identity_and_quarantine_custody_request: bytes,
    mode: str,
) -> dict[str, Any]:
    """Review one exact isolated-lab T09 KAT or fail closed."""

    _reject_mode(mode)
    try:
        predecessor_receipt = predecessor.review_end_to_end_subject_binding(
            frame,
            detached_authentication_bundle,
            separately_injected_synthetic_trust_policy,
            separately_injected_synthetic_signer_authorization_policy,
            detached_authorization_request,
            separately_injected_synthetic_track_profile_binding_policy,
            detached_track_profile_binding_request,
            separately_injected_synthetic_end_to_end_subject_binding_policy,
            detached_end_to_end_subject_binding_request,
            predecessor.SYNTHETIC_KAT_MODE,
        )
    except predecessor.EndToEndSubjectBindingReviewError as error:
        raise ContentIdentityReviewError(
            "E_PREDECESSOR_END_TO_END_SUBJECT_BINDING_REJECTED",
            f"{error.code}: {error.detail}",
            detail_code=error.code,
        ) from error

    derived = _derive_identities(frame, predecessor_receipt)
    try:
        policy = _decode_closed_json(
            separately_injected_synthetic_content_identity_and_quarantine_custody_policy,
            limit=MAX_POLICY_BYTES,
            label="CONTENT_IDENTITY_POLICY",
        )
        profiles = _validate_policy(policy)
    except ContentIdentityReviewError as error:
        raise ContentIdentityReviewError(
            "E_CONTENT_IDENTITY_POLICY_REJECTED",
            f"{error.code}: {error.detail}",
            detail_code=error.code,
        ) from error

    try:
        request_object = _decode_closed_json(
            detached_content_identity_and_quarantine_custody_request,
            limit=MAX_REQUEST_BYTES,
            label="CONTENT_IDENTITY_REQUEST",
        )
        request = _validate_request(request_object)
        selected = _select_profile(profiles, predecessor_receipt, derived, request)
        _bind_predecessor_receipt(predecessor_receipt, selected)
    except ContentIdentityReviewError as error:
        raise ContentIdentityReviewError(
            "E_CONTENT_IDENTITY_AND_QUARANTINE_CUSTODY_FAILED",
            f"{error.code}: {error.detail}",
            detail_code=error.code,
        ) from error

    receipt: dict[str, Any] = {
        "action_or_resource_capability_authorized": False,
        "authorized_unit": AUTHORIZED_UNIT,
        "binding_match_count": 1,
        "binding_policy_match_dimension_count": len(PROFILE_FIELDS),
        "binding_policy_match_fields": list(PROFILE_FIELDS),
        "binding_profile_count": len(profiles),
        "binding_request_field_count": len(REQUEST_FIELDS),
        "binding_request_fields": list(REQUEST_FIELDS),
        "caller_supplied_predecessor_receipt_accepted": False,
        "canonical_frame_sha256": derived["canonical_frame_sha256"],
        "canonicalization_generalized_beyond_exact_kat_frame": False,
        "component_state": COMPONENT_STATE,
        "condition_output_authorized": False,
        "content_identity_and_quarantine_custody_policy_is_production_policy": False,
        "content_identity_and_quarantine_custody_policy_separately_injected": True,
        "content_identity_and_quarantine_custody_policy_sha256": hashlib.sha256(separately_injected_synthetic_content_identity_and_quarantine_custody_policy).hexdigest(),
        "content_identity_and_quarantine_custody_request_detached": True,
        "content_identity_and_quarantine_custody_request_observed_after_policy": True,
        "content_identity_and_quarantine_custody_request_sha256": hashlib.sha256(detached_content_identity_and_quarantine_custody_request).hexdigest(),
        "content_identity_truth_proved": False,
        "content_sha256": "0" * 64,
        "default_disposition": DEFAULT_DISPOSITION,
        "downstream_gate_count": 4,
        "downstream_gates_authorized": 0,
        "durable_custody_implemented": False,
        "durable_replay_cas_implemented": False,
        "evidence_acceptance_authorized": False,
        "execution_mode": SYNTHETIC_KAT_MODE,
        "fault_injection_authorized": False,
        "frame_reparsed_by_t09_after_t08_success": False,
        "isolated_lab_candidate_surface_component_total": 7,
        "isolated_lab_candidate_surface_components_implemented": 7,
        "isolated_lab_candidate_surface_components_locally_kat_exercised": 7,
        "local_t08_specification_exercised": True,
        "local_t09_specification_exercised": True,
        "local_t10_specification_exercised": False,
        "local_threat_specifications_covered": 9,
        "local_threat_specifications_covered_ids": [f"T{value:02d}" for value in range(1, 10)],
        "matching_profile": MATCHING_PROFILE,
        "output_or_claim_authorized": False,
        "packet_id_sha256": derived["packet_id_sha256"],
        "packet_identity_authenticated": False,
        "predecessor_receipt_and_track_non_substitutable": True,
        "predecessor_receipt_content_sha256": predecessor_receipt["content_sha256"],
        "predecessor_receipt_schema": predecessor.RECEIPT_SCHEMA,
        "predecessor_review_count": 1,
        "production_admissible": False,
        "production_canonicalization_implemented": False,
        "production_ingestion_control_count": 14,
        "production_ingestion_controls_implemented": 0,
        "production_ingestion_controls_runtime_exercised": 0,
        "production_quarantine_custody_implemented": False,
        "production_threat_specification_count": 20,
        "production_threat_specifications_runtime_exercised": 0,
        "production_validated_evidence_items": 0,
        "provider_authority": False,
        "public_input_count": 12,
        "raw_and_canonical_hash_equal_only_for_exact_frozen_kat": True,
        "raw_frame_sha256": derived["raw_frame_sha256"],
        "real_evidence_items_present": 0,
        "reject_on_multiple_matches": True,
        "reject_on_zero_matches": True,
        "retention_record_implemented": False,
        "runtime_authority": False,
        "runtime_evidence_accepted": 0,
        "runtime_prerequisite_count": 16,
        "runtime_prerequisites_satisfied": 0,
        "schema": RECEIPT_SCHEMA,
        "schema_version": 1,
        "side_effects_unlocked": "NONE",
        "signature_subject_identity_authenticated": False,
        "signature_subject_sha256": derived["signature_subject_sha256"],
        "status": STATUS,
        "synthetic_fixture": True,
        "t08_end_to_end_subject_binding_implemented": True,
        "t09_content_identity_and_quarantine_custody_implemented": True,
        "target_production_control": TARGET_PRODUCTION_CONTROL,
        "target_production_failure_code": TARGET_PRODUCTION_FAILURE_CODE,
        "tombstone_record_implemented": False,
        "track_id": predecessor_receipt["track_id"],
        "track_identity_source": "T08_PREDECESSOR_RECEIPT_ONLY",
        "validation_subject_identity_authenticated": False,
        "validation_subject_sha256": derived["validation_subject_sha256"],
        "wildcard_prefix_hierarchy_or_inheritance_authorization_implemented": False,
    }
    receipt_without_hash = dict(receipt)
    del receipt_without_hash["content_sha256"]
    receipt["content_sha256"] = _domain_sha256(RECEIPT_HASH_DOMAIN, _canonical_bytes(receipt_without_hash))
    return receipt


__all__ = [
    "AUTHORIZED_UNIT",
    "COMPONENT_STATE",
    "DEFAULT_DISPOSITION",
    "MATCHING_PROFILE",
    "PACKET_ID_DOMAIN",
    "POLICY_SCHEMA",
    "PRODUCTION_MODE",
    "PROFILES",
    "PROFILE_FIELDS",
    "RECEIPT_SCHEMA",
    "REQUEST_FIELDS",
    "STATUS",
    "SYNTHETIC_KAT_MODE",
    "TARGET_PRODUCTION_CONTROL",
    "TARGET_PRODUCTION_FAILURE_CODE",
    "ContentIdentityReviewError",
    "known_answer_content_identity_policy",
    "known_answer_content_identity_policy_bytes",
    "known_answer_content_identity_request",
    "known_answer_content_identity_request_bytes",
    "review_content_identity_and_quarantine_custody",
]
