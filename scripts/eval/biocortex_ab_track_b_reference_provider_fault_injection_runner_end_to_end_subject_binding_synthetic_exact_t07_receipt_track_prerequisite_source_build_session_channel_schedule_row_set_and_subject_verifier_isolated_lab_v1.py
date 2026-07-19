#!/usr/bin/env python3
"""Pure isolated-lab T08 end-to-end subject-binding verifier.

The public entrypoint accepts ten disjoint inputs.  Production, unknown, and
non-string modes are rejected before any other input is observed.  The exact
synthetic path invokes the frozen T07 track/profile-binding reviewer exactly
once, validates a separately injected closed-world two-profile T08 policy,
and observes the detached eight-field T08 request last.

The T07 receipt is the sole source of the track and predecessor identity.  A
successful local review binds that exact receipt and track by ASCII byte
equality to prerequisite, source, build, session, channel, schedule, row-set,
and subject labels.  It does not authenticate those labels or prove their
truth or currentness.

This module implements only the fixed public KAT for local T08.  It has no
provider, network, credential, clock, persistence, custody, replay ledger,
signing, fault-injection, evidence-admission, output-authority, deployment, or
runtime-registration surface.  It neither reparses the frame nor implements
T09 content identity, quarantine custody, or replay CAS.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Mapping, NoReturn

import biocortex_ab_track_b_reference_provider_fault_injection_runner_track_profile_binding_synthetic_exact_packet_profile_provider_or_lab_profile_namespace_configuration_sha256_and_non_substitutable_track_verifier_isolated_lab_v1 as predecessor


SYNTHETIC_KAT_MODE = "SYNTHETIC_KAT"
PRODUCTION_MODE = "PRODUCTION"

END_TO_END_SUBJECT_BINDING_POLICY_SCHEMA = (
    "agent_bridge.biocortex_ab_track_b_reference_provider_fault_injection_"
    "runner.end_to_end_subject_binding_synthetic_policy_isolated_lab_kat.v1"
)
RECEIPT_SCHEMA = (
    "agent_bridge.biocortex_ab_track_b_reference_provider_fault_injection_"
    "runner.end_to_end_subject_binding_synthetic_exact_t07_receipt_track_"
    "prerequisite_source_build_session_channel_schedule_row_set_and_subject_"
    "verifier_isolated_lab_v1.receipt.v0"
)
STATUS = (
    "REFERENCE_PROVIDER_MANAGED_AND_SELF_HOSTED_FAULT_INJECTION_RUNNER_V1_"
    "END_TO_END_SUBJECT_BINDING_SYNTHETIC_EXACT_T07_RECEIPT_TRACK_"
    "PREREQUISITE_SOURCE_BUILD_SESSION_CHANNEL_SCHEDULE_ROW_SET_AND_SUBJECT_"
    "VERIFIED_ISOLATED_LAB_COMPONENT_ONLY_NO_PRODUCTION_AUTHORITY"
)
COMPONENT_STATE = (
    "BOUND_SYNTHETIC_KAT_END_TO_END_SUBJECT_LABELS_TO_EXACT_T07_RECEIPT_CHAIN_ONLY"
)
RECEIPT_HASH_DOMAIN = (
    "AB_TRACK_B_END_TO_END_SUBJECT_BINDING_ISOLATED_LAB_KAT_RECEIPT_V1"
)
MATCHING_PROFILE = "EXACT_ALL_FIELDS_ASCII_BYTE_EQUAL"
DEFAULT_DISPOSITION = "REJECTED_FAIL_CLOSED"
TARGET_PRODUCTION_CONTROL = "TRACK_SUBJECT_BINDING"
TARGET_PRODUCTION_FAILURE_CODE = "E_PRODUCTION_TRACK_SUBJECT_BINDING_FAILED"

MAX_END_TO_END_SUBJECT_BINDING_POLICY_BYTES = 65_536
MAX_END_TO_END_SUBJECT_BINDING_REQUEST_BYTES = 16_384
MAX_PROFILE_STRING_UTF8_BYTES = 256
MAX_JSON_DEPTH = 32
MAX_JSON_NODES = 4_096
MAX_OBJECT_MEMBERS = 256
MAX_ARRAY_ITEMS = 64
MIN_SIGNED_INT64 = -(2**63)
MAX_SIGNED_INT64 = 2**63 - 1
HEX_32_LENGTH = 64

END_TO_END_SUBJECT_BINDING_POLICY_KEYS = (
    "default_disposition",
    "profiles",
    "reject_on_multiple_matches",
    "reject_on_zero_matches",
    "matching_profile",
    "schema",
    "schema_version",
)
END_TO_END_SUBJECT_BINDING_PROFILE_FIELDS = (
    "t07_receipt_content_sha256",
    "track_id",
    "prerequisite_id",
    "source_id",
    "build_id",
    "session_id",
    "channel_id",
    "schedule_id",
    "row_set_id",
    "subject",
)
END_TO_END_SUBJECT_BINDING_REQUEST_FIELDS = (
    "prerequisite_id",
    "source_id",
    "build_id",
    "session_id",
    "channel_id",
    "schedule_id",
    "row_set_id",
    "subject",
)


@dataclass(frozen=True)
class EndToEndSubjectBindingProfile:
    track_id: str
    t07_receipt_content_sha256: str
    prerequisite_id: str
    source_id: str
    build_id: str
    session_id: str
    channel_id: str
    schedule_id: str
    row_set_id: str
    subject: str


END_TO_END_SUBJECT_BINDING_PROFILES = (
    EndToEndSubjectBindingProfile(
        track_id="MANAGED_SPANNER_CLOUD_KMS",
        t07_receipt_content_sha256=(
            "5db2449ebf80e668ac7fc8ccaec6cc62a7461d8874809543a74ee9b7b5d725b6"
        ),
        prerequisite_id="KAT_MANAGED_T08_PREREQUISITE_V1",
        source_id="KAT_MANAGED_T08_SOURCE_V1",
        build_id="KAT_MANAGED_T08_BUILD_V1",
        session_id="KAT_MANAGED_T08_SESSION_V1",
        channel_id="KAT_MANAGED_T08_CHANNEL_V1",
        schedule_id="KAT_MANAGED_T08_SCHEDULE_V1",
        row_set_id="KAT_MANAGED_T08_ROW_SET_V1",
        subject="KAT_MANAGED_VALID_MINIMAL_FRAME_SUBJECT_V1",
    ),
    EndToEndSubjectBindingProfile(
        track_id="SELF_HOSTED_ETCD_OPENBAO",
        t07_receipt_content_sha256=(
            "3f49518a74a6a7075335db5b139035613ff992d1deedc0c31216832dd4dcb014"
        ),
        prerequisite_id="KAT_SELF_HOSTED_T08_PREREQUISITE_V1",
        source_id="KAT_SELF_HOSTED_T08_SOURCE_V1",
        build_id="KAT_SELF_HOSTED_T08_BUILD_V1",
        session_id="KAT_SELF_HOSTED_T08_SESSION_V1",
        channel_id="KAT_SELF_HOSTED_T08_CHANNEL_V1",
        schedule_id="KAT_SELF_HOSTED_T08_SCHEDULE_V1",
        row_set_id="KAT_SELF_HOSTED_T08_ROW_SET_V1",
        subject="KAT_SELF_HOSTED_VALID_MINIMAL_FRAME_SUBJECT_V1",
    ),
)


class EndToEndSubjectBindingReviewError(ValueError):
    """Fail-closed review error with stable public and detail reason codes."""

    def __init__(self, code: str, detail: str, *, detail_code: str | None = None):
        super().__init__(f"{code}: {detail}")
        self.code = code
        self.detail = detail
        self.detail_code = detail_code


def _fail(code: str, detail: str) -> NoReturn:
    raise EndToEndSubjectBindingReviewError(code, detail)


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
    except EndToEndSubjectBindingReviewError:
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
            "E_END_TO_END_SUBJECT_BINDING_MODE_UNKNOWN",
            "only exact string SYNTHETIC_KAT is reviewable",
        )
    if mode == PRODUCTION_MODE:
        _fail(
            "E_END_TO_END_SUBJECT_BINDING_PRODUCTION_MODE_NOT_AUTHORIZED",
            "production end-to-end subject binding is outside isolated-lab authority",
        )
    if mode != SYNTHETIC_KAT_MODE:
        _fail(
            "E_END_TO_END_SUBJECT_BINDING_MODE_UNKNOWN",
            "only SYNTHETIC_KAT is reviewable",
        )


def _ascii_profile_value(value: Any, *, field: str) -> str:
    _require(type(value) is str, f"E_{field.upper()}_TYPE", f"{field} must be string")
    try:
        encoded = value.encode("ascii", "strict")
    except UnicodeEncodeError as error:
        _fail(f"E_{field.upper()}_ASCII", str(error))
    _require(
        0 < len(encoded) <= MAX_PROFILE_STRING_UTF8_BYTES,
        f"E_{field.upper()}_SIZE",
        f"{field} is empty or exceeds bound",
    )
    _require(
        value == value.strip(),
        f"E_{field.upper()}_TRIM",
        f"{field} must be exactly trimmed",
    )
    _require(
        "*" not in value and "?" not in value,
        f"E_{field.upper()}_WILDCARD",
        f"{field} wildcard tokens forbidden",
    )
    return value


def _validate_lower_hex_32(value: Any, *, field: str) -> None:
    _require(
        type(value) is str
        and len(value) == HEX_32_LENGTH
        and all(character in "0123456789abcdef" for character in value),
        f"E_{field.upper()}_LOWER_HEX_32",
        f"{field} must be lowercase SHA-256 hex",
    )


def _profile_object(profile: EndToEndSubjectBindingProfile) -> dict[str, str]:
    return {
        "build_id": profile.build_id,
        "channel_id": profile.channel_id,
        "prerequisite_id": profile.prerequisite_id,
        "row_set_id": profile.row_set_id,
        "schedule_id": profile.schedule_id,
        "session_id": profile.session_id,
        "source_id": profile.source_id,
        "subject": profile.subject,
        "t07_receipt_content_sha256": profile.t07_receipt_content_sha256,
        "track_id": profile.track_id,
    }


def known_answer_end_to_end_subject_binding_policy() -> dict[str, Any]:
    """Return the exact ordered public-only two-profile T08 KAT policy."""

    return {
        "default_disposition": DEFAULT_DISPOSITION,
        "matching_profile": MATCHING_PROFILE,
        "profiles": [
            _profile_object(profile) for profile in END_TO_END_SUBJECT_BINDING_PROFILES
        ],
        "reject_on_multiple_matches": True,
        "reject_on_zero_matches": True,
        "schema": END_TO_END_SUBJECT_BINDING_POLICY_SCHEMA,
        "schema_version": 1,
    }


def known_answer_end_to_end_subject_binding_policy_bytes() -> bytes:
    return _canonical_bytes(known_answer_end_to_end_subject_binding_policy())


def known_answer_end_to_end_subject_binding_request(track_id: str) -> dict[str, str]:
    """Return one exact detached eight-field request for a frozen track."""

    profile = _profile_for_track(track_id)
    return {
        "build_id": profile.build_id,
        "channel_id": profile.channel_id,
        "prerequisite_id": profile.prerequisite_id,
        "row_set_id": profile.row_set_id,
        "schedule_id": profile.schedule_id,
        "session_id": profile.session_id,
        "source_id": profile.source_id,
        "subject": profile.subject,
    }


def known_answer_end_to_end_subject_binding_request_bytes(track_id: str) -> bytes:
    return _canonical_bytes(known_answer_end_to_end_subject_binding_request(track_id))


def _profile_for_track(track_id: str) -> EndToEndSubjectBindingProfile:
    for profile in END_TO_END_SUBJECT_BINDING_PROFILES:
        if track_id == profile.track_id:
            return profile
    _fail("E_END_TO_END_SUBJECT_BINDING_TRACK_UNKNOWN", "track is not a frozen KAT profile")


def _validate_policy(
    policy: Mapping[str, Any],
) -> tuple[Mapping[str, Any], ...]:
    _exact_keys(
        policy,
        END_TO_END_SUBJECT_BINDING_POLICY_KEYS,
        "E_END_TO_END_SUBJECT_BINDING_POLICY_FIELDS",
    )
    _require(
        type(policy["schema"]) is str
        and policy["schema"] == END_TO_END_SUBJECT_BINDING_POLICY_SCHEMA,
        "E_END_TO_END_SUBJECT_BINDING_POLICY_SCHEMA",
        "policy schema drift",
    )
    _require(
        type(policy["schema_version"]) is int and policy["schema_version"] == 1,
        "E_END_TO_END_SUBJECT_BINDING_POLICY_SCHEMA_VERSION",
        "policy schema version drift",
    )
    _require(
        type(policy["default_disposition"]) is str
        and policy["default_disposition"] == DEFAULT_DISPOSITION,
        "E_END_TO_END_SUBJECT_BINDING_POLICY_DEFAULT",
        "default disposition must be exact REJECTED_FAIL_CLOSED",
    )
    _require(
        type(policy["matching_profile"]) is str
        and policy["matching_profile"] == MATCHING_PROFILE,
        "E_END_TO_END_SUBJECT_BINDING_POLICY_MATCHING_PROFILE",
        "matching profile drift",
    )
    _require(
        policy["reject_on_zero_matches"] is True,
        "E_END_TO_END_SUBJECT_BINDING_POLICY_ZERO_MATCH",
        "zero matches must reject",
    )
    _require(
        policy["reject_on_multiple_matches"] is True,
        "E_END_TO_END_SUBJECT_BINDING_POLICY_MULTIPLE_MATCH",
        "multiple matches must reject",
    )
    profiles = policy["profiles"]
    _require(
        type(profiles) is list and len(profiles) == 2,
        "E_END_TO_END_SUBJECT_BINDING_POLICY_PROFILES",
        "exactly two ordered profiles required",
    )
    validated: list[Mapping[str, Any]] = []
    for candidate, frozen in zip(
        profiles,
        END_TO_END_SUBJECT_BINDING_PROFILES,
        strict=True,
    ):
        _require(
            type(candidate) is dict,
            "E_END_TO_END_SUBJECT_BINDING_PROFILE_OBJECT",
            "profile must be object",
        )
        _exact_keys(
            candidate,
            END_TO_END_SUBJECT_BINDING_PROFILE_FIELDS,
            "E_END_TO_END_SUBJECT_BINDING_PROFILE_FIELDS",
        )
        expected = _profile_object(frozen)
        for field in END_TO_END_SUBJECT_BINDING_PROFILE_FIELDS:
            observed = _ascii_profile_value(
                candidate[field],
                field=f"end_to_end_subject_binding_profile_{field}",
            )
            _require(
                observed.encode("ascii") == expected[field].encode("ascii"),
                f"E_END_TO_END_SUBJECT_BINDING_PROFILE_{field.upper()}_EXACT",
                f"{field} exact frozen KAT binding drift",
            )
        _validate_lower_hex_32(
            candidate["t07_receipt_content_sha256"],
            field="end_to_end_subject_binding_profile_t07_receipt_content_sha256",
        )
        validated.append(candidate)
    _require(
        profiles[0]["track_id"] != profiles[1]["track_id"],
        "E_END_TO_END_SUBJECT_BINDING_POLICY_DISTINCTNESS",
        "two distinct ordered track profiles required",
    )
    return tuple(validated)


def _validate_request(request: Mapping[str, Any]) -> Mapping[str, Any]:
    _exact_keys(
        request,
        END_TO_END_SUBJECT_BINDING_REQUEST_FIELDS,
        "E_END_TO_END_SUBJECT_BINDING_REQUEST_FIELDS",
    )
    for field in END_TO_END_SUBJECT_BINDING_REQUEST_FIELDS:
        _ascii_profile_value(
            request[field],
            field=f"end_to_end_subject_binding_request_{field}",
        )
    return request


def _select_profile(
    profiles: tuple[Mapping[str, Any], ...],
    predecessor_receipt: Mapping[str, Any],
    request: Mapping[str, Any],
) -> Mapping[str, Any]:
    match_values = {
        **{field: request[field] for field in END_TO_END_SUBJECT_BINDING_REQUEST_FIELDS},
        "t07_receipt_content_sha256": predecessor_receipt.get("content_sha256"),
        "track_id": predecessor_receipt.get("track_id"),
    }
    _require(
        type(match_values["track_id"]) is str,
        "E_PREDECESSOR_RECEIPT_TRACK_ID_BINDING",
        "T07 receipt track_id must be an exact string",
    )
    _require(
        type(match_values["t07_receipt_content_sha256"]) is str,
        "E_PREDECESSOR_RECEIPT_CONTENT_SHA256_BINDING",
        "T07 receipt content_sha256 must be an exact string",
    )
    track_profiles = [
        profile
        for profile in profiles
        if profile["track_id"].encode("ascii")
        == match_values["track_id"].encode("ascii")
    ]
    _require(
        len(track_profiles) != 0,
        "E_PREDECESSOR_RECEIPT_TRACK_ID_BINDING",
        "T07 receipt track_id is not one exact frozen policy track",
    )
    _require(
        any(
            profile["t07_receipt_content_sha256"].encode("ascii")
            == match_values["t07_receipt_content_sha256"].encode("ascii")
            for profile in track_profiles
        ),
        "E_PREDECESSOR_RECEIPT_CONTENT_SHA256_BINDING",
        "T07 receipt content identity does not bind its exact frozen track",
    )
    matches = [
        profile
        for profile in profiles
        if all(
            profile[field].encode("ascii") == match_values[field].encode("ascii")
            for field in END_TO_END_SUBJECT_BINDING_PROFILE_FIELDS
        )
    ]
    _require(
        len(matches) != 0,
        "E_END_TO_END_SUBJECT_BINDING_ZERO_MATCH_DENY",
        "default REJECTED_FAIL_CLOSED: no exact ten-dimension profile",
    )
    _require(
        len(matches) == 1,
        "E_END_TO_END_SUBJECT_BINDING_MULTIPLE_MATCH_DENY",
        "ambiguous multiple matching profiles rejected",
    )
    return matches[0]


def _bind_predecessor_receipt(
    receipt: Mapping[str, Any],
    selected_profile: Mapping[str, Any],
) -> None:
    expected_strings = {
        "content_sha256": selected_profile["t07_receipt_content_sha256"],
        "execution_mode": SYNTHETIC_KAT_MODE,
        "schema": predecessor.RECEIPT_SCHEMA,
        "track_id": selected_profile["track_id"],
    }
    for field, expected_value in expected_strings.items():
        error_code = (
            "E_PREDECESSOR_RECEIPT_CONTENT_SHA256_BINDING"
            if field == "content_sha256"
            else "E_PREDECESSOR_RECEIPT_TRACK_ID_BINDING"
            if field == "track_id"
            else f"E_T07_PREDECESSOR_RECEIPT_{field.upper()}_BINDING"
        )
        _require(
            type(receipt.get(field)) is str and receipt.get(field) == expected_value,
            error_code,
            f"T07 receipt {field} does not bind selected profile",
        )
    expected_scalars: dict[str, Any] = {
        "bootstrap_trust_authentication_implemented": True,
        "isolated_lab_candidate_surface_component_total": 5,
        "isolated_lab_candidate_surface_components_implemented": 5,
        "isolated_lab_candidate_surface_components_locally_kat_exercised": 5,
        "local_t05_specification_exercised": True,
        "local_t06_specification_exercised": True,
        "local_t07_specification_exercised": True,
        "local_t08_specification_exercised": False,
        "local_t09_specification_exercised": False,
        "local_threat_specifications_covered": 7,
        "local_threat_specifications_covered_ids": [
            "T01",
            "T02",
            "T03",
            "T04",
            "T05",
            "T06",
            "T07",
        ],
        "production_admissible": False,
        "production_track_subject_binding_implemented": False,
        "provider_authority": False,
        "runtime_authority": False,
        "signer_role_scope_authorization_isolated_lab_component_implemented": True,
        "synthetic_fixture": True,
        "track_profile_binding_isolated_lab_component_implemented": True,
        "t08_end_to_end_subject_binding_implemented": False,
        "t09_content_identity_and_quarantine_custody_implemented": False,
    }
    for field, expected_value in expected_scalars.items():
        _require(
            type(receipt.get(field)) is type(expected_value)
            and receipt.get(field) == expected_value,
            f"E_T07_PREDECESSOR_RECEIPT_{field.upper()}_BINDING",
            f"T07 receipt {field} truth drift",
        )


def _domain_sha256(domain: str, raw: bytes) -> str:
    return hashlib.sha256(domain.encode("ascii") + b"\x00" + raw).hexdigest()


def review_end_to_end_subject_binding(
    frame: bytes,
    detached_authentication_bundle: bytes,
    separately_injected_synthetic_trust_policy: bytes,
    separately_injected_synthetic_signer_authorization_policy: bytes,
    detached_authorization_request: bytes,
    separately_injected_synthetic_track_profile_binding_policy: bytes,
    detached_track_profile_binding_request: bytes,
    separately_injected_synthetic_end_to_end_subject_binding_policy: bytes,
    detached_end_to_end_subject_binding_request: bytes,
    mode: str,
) -> dict[str, Any]:
    """Review one exact isolated-lab T08 KAT or fail closed."""

    _reject_mode(mode)

    try:
        predecessor_receipt = predecessor.review_track_profile_binding(
            frame,
            detached_authentication_bundle,
            separately_injected_synthetic_trust_policy,
            separately_injected_synthetic_signer_authorization_policy,
            detached_authorization_request,
            separately_injected_synthetic_track_profile_binding_policy,
            detached_track_profile_binding_request,
            predecessor.SYNTHETIC_KAT_MODE,
        )
    except predecessor.TrackProfileBindingReviewError as error:
        raise EndToEndSubjectBindingReviewError(
            "E_PREDECESSOR_TRACK_PROFILE_BINDING_REJECTED",
            f"{error.code}: {error.detail}",
            detail_code=error.code,
        ) from error

    try:
        binding_policy = _decode_closed_json(
            separately_injected_synthetic_end_to_end_subject_binding_policy,
            limit=MAX_END_TO_END_SUBJECT_BINDING_POLICY_BYTES,
            label="END_TO_END_SUBJECT_BINDING_POLICY",
        )
        profiles = _validate_policy(binding_policy)
    except EndToEndSubjectBindingReviewError as error:
        raise EndToEndSubjectBindingReviewError(
            "E_END_TO_END_SUBJECT_BINDING_POLICY_REJECTED",
            f"{error.code}: {error.detail}",
            detail_code=error.code,
        ) from error

    try:
        binding_request = _decode_closed_json(
            detached_end_to_end_subject_binding_request,
            limit=MAX_END_TO_END_SUBJECT_BINDING_REQUEST_BYTES,
            label="END_TO_END_SUBJECT_BINDING_REQUEST",
        )
        request = _validate_request(binding_request)
        selected_profile = _select_profile(
            profiles,
            predecessor_receipt,
            request,
        )
        _bind_predecessor_receipt(predecessor_receipt, selected_profile)
    except EndToEndSubjectBindingReviewError as error:
        raise EndToEndSubjectBindingReviewError(
            "E_END_TO_END_SUBJECT_BINDING_FAILED",
            f"{error.code}: {error.detail}",
            detail_code=error.code,
        ) from error

    receipt: dict[str, Any] = {
        "action_or_resource_capability_authorized": False,
        "binding_match_count": 1,
        "binding_policy_match_dimension_count": len(
            END_TO_END_SUBJECT_BINDING_PROFILE_FIELDS
        ),
        "binding_policy_match_fields": list(END_TO_END_SUBJECT_BINDING_PROFILE_FIELDS),
        "binding_profile_count": len(profiles),
        "binding_request_field_count": len(END_TO_END_SUBJECT_BINDING_REQUEST_FIELDS),
        "binding_request_fields": list(END_TO_END_SUBJECT_BINDING_REQUEST_FIELDS),
        "bootstrap_trust_authentication_implemented": True,
        "build_id": request["build_id"],
        "build_truth_proved": False,
        "caller_supplied_predecessor_receipt_accepted": False,
        "channel_id": request["channel_id"],
        "channel_truth_proved": False,
        "component_state": COMPONENT_STATE,
        "condition_output_authorized": False,
        "content_sha256": "0" * 64,
        "default_disposition": DEFAULT_DISPOSITION,
        "downstream_gate_count": 4,
        "downstream_gates_authorized": 0,
        "durable_replay_cas_implemented": False,
        "end_to_end_subject_binding_isolated_lab_component_implemented": True,
        "end_to_end_subject_binding_policy_is_production_policy": False,
        "end_to_end_subject_binding_policy_separately_injected": True,
        "end_to_end_subject_binding_policy_sha256": hashlib.sha256(
            separately_injected_synthetic_end_to_end_subject_binding_policy
        ).hexdigest(),
        "end_to_end_subject_binding_request_detached": True,
        "end_to_end_subject_binding_request_observed_after_policy": True,
        "end_to_end_subject_binding_request_sha256": hashlib.sha256(
            detached_end_to_end_subject_binding_request
        ).hexdigest(),
        "evidence_acceptance_authorized": False,
        "execution_mode": SYNTHETIC_KAT_MODE,
        "fault_injection_authorized": False,
        "frame_reparsed_by_t08_after_t07_success": False,
        "isolated_lab_candidate_surface_component_total": 6,
        "isolated_lab_candidate_surface_components_implemented": 6,
        "isolated_lab_candidate_surface_components_locally_kat_exercised": 6,
        "local_t05_specification_exercised": True,
        "local_t06_specification_exercised": True,
        "local_t07_specification_exercised": True,
        "local_t08_specification_exercised": True,
        "local_t09_specification_exercised": False,
        "local_threat_specifications_covered": 8,
        "local_threat_specifications_covered_ids": [
            "T01",
            "T02",
            "T03",
            "T04",
            "T05",
            "T06",
            "T07",
            "T08",
        ],
        "matching_profile": MATCHING_PROFILE,
        "output_or_claim_authorized": False,
        "predecessor_receipt_and_track_non_substitutable": True,
        "predecessor_receipt_content_sha256": predecessor_receipt[
            "content_sha256"
        ],
        "predecessor_receipt_schema": predecessor.RECEIPT_SCHEMA,
        "predecessor_review_count": 1,
        "prerequisite_id": request["prerequisite_id"],
        "prerequisite_truth_proved": False,
        "production_admissible": False,
        "production_ingestion_control_count": 14,
        "production_ingestion_controls_implemented": 0,
        "production_ingestion_controls_runtime_exercised": 0,
        "production_signer_role_scope_authorization_implemented": False,
        "production_threat_specification_count": 20,
        "production_threat_specifications_runtime_exercised": 0,
        "production_track_subject_binding_implemented": False,
        "production_validated_evidence_items": 0,
        "provider_authority": False,
        "public_input_count": 10,
        "real_evidence_items_present": 0,
        "reject_on_multiple_matches": True,
        "reject_on_zero_matches": True,
        "row_set_id": request["row_set_id"],
        "row_set_truth_proved": False,
        "runtime_authority": False,
        "runtime_evidence_accepted": 0,
        "runtime_prerequisite_count": 16,
        "runtime_prerequisites_satisfied": 0,
        "schedule_id": request["schedule_id"],
        "schedule_truth_proved": False,
        "schema": RECEIPT_SCHEMA,
        "schema_version": 1,
        "session_id": request["session_id"],
        "session_truth_proved": False,
        "side_effects_unlocked": "NONE",
        "signer_role_scope_authorization_isolated_lab_component_implemented": True,
        "source_id": request["source_id"],
        "source_truth_proved": False,
        "status": STATUS,
        "subject": request["subject"],
        "subject_identity_authenticated": False,
        "subject_truth_proved": False,
        "synthetic_fixture": True,
        "t07_track_profile_binding_isolated_lab_component_implemented": True,
        "t08_end_to_end_subject_binding_implemented": True,
        "t09_content_identity_and_quarantine_custody_implemented": False,
        "target_production_control": TARGET_PRODUCTION_CONTROL,
        "target_production_failure_code": TARGET_PRODUCTION_FAILURE_CODE,
        "track_id": predecessor_receipt["track_id"],
        "track_identity_source": "T07_PREDECESSOR_RECEIPT_ONLY",
        "track_profile_binding_isolated_lab_component_implemented": True,
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
    "COMPONENT_STATE",
    "DEFAULT_DISPOSITION",
    "MATCHING_PROFILE",
    "PRODUCTION_MODE",
    "RECEIPT_SCHEMA",
    "STATUS",
    "SYNTHETIC_KAT_MODE",
    "TARGET_PRODUCTION_CONTROL",
    "TARGET_PRODUCTION_FAILURE_CODE",
    "END_TO_END_SUBJECT_BINDING_POLICY_SCHEMA",
    "END_TO_END_SUBJECT_BINDING_PROFILE_FIELDS",
    "END_TO_END_SUBJECT_BINDING_PROFILES",
    "END_TO_END_SUBJECT_BINDING_REQUEST_FIELDS",
    "EndToEndSubjectBindingReviewError",
    "known_answer_end_to_end_subject_binding_policy",
    "known_answer_end_to_end_subject_binding_policy_bytes",
    "known_answer_end_to_end_subject_binding_request",
    "known_answer_end_to_end_subject_binding_request_bytes",
    "review_end_to_end_subject_binding",
]
