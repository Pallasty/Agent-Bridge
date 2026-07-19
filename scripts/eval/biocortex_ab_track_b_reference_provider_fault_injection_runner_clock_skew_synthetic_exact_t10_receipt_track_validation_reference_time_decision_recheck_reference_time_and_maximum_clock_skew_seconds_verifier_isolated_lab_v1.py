#!/usr/bin/env python3
"""Pure isolated-lab T11 clock-skew verifier over fixed public integer labels.

The sixteen-input entrypoint observes ``mode`` first, invokes the frozen T10
public reviewer exactly once, validates a separately injected closed-world
two-profile policy, and observes the detached clock-skew request last.

This component performs deterministic signed-int64 arithmetic for public KAT
labels.  It never reads a clock and proves neither trusted time nor production
currentness.  T12 owner TOCTOU remains outside scope.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Mapping, NoReturn

import biocortex_ab_track_b_reference_provider_fault_injection_runner_freshness_synthetic_exact_t09_receipt_track_observed_at_validation_checked_at_decision_recheck_at_expires_at_and_max_age_seconds_verifier_isolated_lab_v1 as predecessor


SYNTHETIC_KAT_MODE = "SYNTHETIC_KAT"
PRODUCTION_MODE = "PRODUCTION"
POLICY_SCHEMA = (
    "agent_bridge.biocortex_ab_track_b_reference_provider_fault_injection_"
    "runner.clock_skew_synthetic_policy_isolated_lab_kat.v1"
)
RECEIPT_SCHEMA = (
    "agent_bridge.biocortex_ab_track_b_reference_provider_fault_injection_"
    "runner.clock_skew_synthetic_exact_t10_receipt_track_validation_reference_"
    "time_decision_recheck_reference_time_and_maximum_clock_skew_seconds_"
    "verifier_isolated_lab_v1.receipt.v0"
)
STATUS = (
    "REFERENCE_PROVIDER_MANAGED_AND_SELF_HOSTED_FAULT_INJECTION_RUNNER_V1_"
    "CLOCK_SKEW_SYNTHETIC_EXACT_T10_RECEIPT_TRACK_VALIDATION_REFERENCE_TIME_"
    "DECISION_RECHECK_REFERENCE_TIME_AND_MAXIMUM_CLOCK_SKEW_SECONDS_"
    "VERIFIED_ISOLATED_LAB_COMPONENT_ONLY_NO_PRODUCTION_AUTHORITY"
)
COMPONENT_STATE = "BOUND_SYNTHETIC_CLOCK_SKEW_LABELS_TO_EXACT_T10_RECEIPT_CHAIN_ONLY"
AUTHORIZED_UNIT = (
    "REFERENCE_PROVIDER_MANAGED_AND_SELF_HOSTED_FAULT_INJECTION_RUNNER_V1_"
    "CLOCK_SKEW_SYNTHETIC_EXACT_T10_RECEIPT_TRACK_VALIDATION_REFERENCE_TIME_"
    "DECISION_RECHECK_REFERENCE_TIME_AND_MAXIMUM_CLOCK_SKEW_SECONDS_"
    "VERIFIER_ISOLATED_LAB_IMPLEMENTATION"
)
RECEIPT_HASH_DOMAIN = "AB_TRACK_B_T11_CLOCK_SKEW_ISOLATED_LAB_KAT_RECEIPT_V1"
MATCHING_PROFILE = "EXACT_ALL_FIELDS_AND_SIGNED_INT64_VALUES_EQUAL"
DEFAULT_DISPOSITION = "REJECTED_FAIL_CLOSED"
CLOCK_SKEW_RELATION = (
    "VALIDATION_REFERENCE_LE_DECISION_REFERENCE_AND_ABSOLUTE_T10_VALIDATION_"
    "AND_DECISION_LABEL_SKEW_LE_MAXIMUM_AND_POSITIVE_FUTURE_OBSERVATION_"
    "OFFSETS_LE_MAXIMUM"
)
TARGET_PRODUCTION_CONTROL = "TRUSTED_TIME_FRESHNESS"
TARGET_PRODUCTION_FAILURE_CODE = "E_PRODUCTION_FRESHNESS_FAILED"

MAX_POLICY_BYTES = 65_536
MAX_REQUEST_BYTES = 16_384
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
REQUEST_FIELDS = (
    "validation_reference_time_unix_seconds",
    "decision_recheck_reference_time_unix_seconds",
    "maximum_clock_skew_seconds",
)
PROFILE_FIELDS = ("t10_receipt_content_sha256", "track_id", *REQUEST_FIELDS)


@dataclass(frozen=True)
class ClockSkewProfile:
    t10_receipt_content_sha256: str
    track_id: str
    validation_reference_time_unix_seconds: int
    decision_recheck_reference_time_unix_seconds: int
    maximum_clock_skew_seconds: int


PROFILES = (
    ClockSkewProfile(
        t10_receipt_content_sha256="620dc08e2f8b41cac5bf0944b50ecc9d2435e59fb5c01e68544270ca94d03714",
        track_id="MANAGED_SPANNER_CLOUD_KMS",
        validation_reference_time_unix_seconds=1_999_999_995,
        decision_recheck_reference_time_unix_seconds=2_000_000_115,
        maximum_clock_skew_seconds=90,
    ),
    ClockSkewProfile(
        t10_receipt_content_sha256="16c7b9228bf36329723376aba4f273f9356759037b4f31ca5a4adbf810bee14d",
        track_id="SELF_HOSTED_ETCD_OPENBAO",
        validation_reference_time_unix_seconds=2_100_000_065,
        decision_recheck_reference_time_unix_seconds=2_100_000_125,
        maximum_clock_skew_seconds=90,
    ),
)


class ClockSkewReviewError(ValueError):
    """Fail-closed error with stable public and nested detail codes."""

    def __init__(self, code: str, detail: str, *, detail_code: str | None = None):
        super().__init__(f"{code}: {detail}")
        self.code = code
        self.detail = detail
        self.detail_code = detail_code


def _fail(code: str, detail: str) -> NoReturn:
    raise ClockSkewReviewError(code, detail)


def _require(condition: bool, code: str, detail: str) -> None:
    if not condition:
        _fail(code, detail)


def _reject_mode(mode: str) -> None:
    if type(mode) is not str:
        _fail("E_CLOCK_SKEW_MODE_UNKNOWN", "mode must be exact string SYNTHETIC_KAT")
    if mode == PRODUCTION_MODE:
        _fail(
            "E_CLOCK_SKEW_PRODUCTION_MODE_NOT_AUTHORIZED",
            "production trusted-time clock_skew is outside isolated-lab authority",
        )
    if mode != SYNTHETIC_KAT_MODE:
        _fail("E_CLOCK_SKEW_MODE_UNKNOWN", "only SYNTHETIC_KAT is reviewable")


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
    except ClockSkewReviewError:
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
    _require(len(observed) == 64 and all(character in "0123456789abcdef" for character in observed), f"E_{field.upper()}_LOWER_SHA256", f"{field} must be lowercase SHA-256 hex")
    return observed


def _nonnegative_int64(value: Any, *, field: str) -> int:
    _require(type(value) is int, f"E_{field.upper()}_TYPE", f"{field} must be exact integer")
    _require(0 <= value <= MAX_SIGNED_INT64, f"E_{field.upper()}_RANGE", f"{field} must be nonnegative signed int64")
    return value


def _profile_object(profile: ClockSkewProfile) -> dict[str, Any]:
    return {field: getattr(profile, field) for field in PROFILE_FIELDS}


def known_answer_clock_skew_policy() -> dict[str, Any]:
    return {
        "default_disposition": DEFAULT_DISPOSITION,
        "matching_profile": MATCHING_PROFILE,
        "profiles": [_profile_object(profile) for profile in PROFILES],
        "reject_on_multiple_matches": True,
        "reject_on_zero_matches": True,
        "schema": POLICY_SCHEMA,
        "schema_version": 1,
    }


def known_answer_clock_skew_policy_bytes() -> bytes:
    return _canonical_bytes(known_answer_clock_skew_policy())


def _profile_for_track(track_id: str) -> ClockSkewProfile:
    for profile in PROFILES:
        if profile.track_id == track_id:
            return profile
    _fail("E_CLOCK_SKEW_TRACK_UNKNOWN", "track is not a frozen KAT profile")


def known_answer_clock_skew_request(track_id: str) -> dict[str, int]:
    profile = _profile_for_track(track_id)
    return {field: getattr(profile, field) for field in REQUEST_FIELDS}


def known_answer_clock_skew_request_bytes(track_id: str) -> bytes:
    return _canonical_bytes(known_answer_clock_skew_request(track_id))


def _validate_policy(policy: Mapping[str, Any]) -> tuple[Mapping[str, Any], ...]:
    _exact_keys(policy, POLICY_KEYS, "E_CLOCK_SKEW_POLICY_FIELDS")
    _require(type(policy["schema"]) is str and policy["schema"] == POLICY_SCHEMA, "E_CLOCK_SKEW_POLICY_SCHEMA", "schema drift")
    _require(type(policy["schema_version"]) is int and policy["schema_version"] == 1, "E_CLOCK_SKEW_POLICY_SCHEMA_VERSION", "version drift")
    _require(type(policy["default_disposition"]) is str and policy["default_disposition"] == DEFAULT_DISPOSITION, "E_CLOCK_SKEW_POLICY_DEFAULT", "default deny required")
    _require(type(policy["matching_profile"]) is str and policy["matching_profile"] == MATCHING_PROFILE, "E_CLOCK_SKEW_POLICY_MATCHING", "exact matching required")
    _require(policy["reject_on_zero_matches"] is True, "E_CLOCK_SKEW_POLICY_ZERO_MATCH", "zero matches must reject")
    _require(policy["reject_on_multiple_matches"] is True, "E_CLOCK_SKEW_POLICY_MULTIPLE_MATCH", "multiple matches must reject")
    profiles = policy["profiles"]
    _require(type(profiles) is list and len(profiles) == 2, "E_CLOCK_SKEW_POLICY_PROFILES", "two ordered profiles required")
    for candidate, frozen in zip(profiles, PROFILES, strict=True):
        _require(type(candidate) is dict, "E_CLOCK_SKEW_PROFILE_OBJECT", "profile must be object")
        _exact_keys(candidate, PROFILE_FIELDS, "E_CLOCK_SKEW_PROFILE_FIELDS")
        expected = _profile_object(frozen)
        _lower_sha256(candidate["t10_receipt_content_sha256"], field="clock_skew_profile_t10_receipt_content_sha256")
        _ascii(candidate["track_id"], field="clock_skew_profile_track_id")
        for field in REQUEST_FIELDS:
            _nonnegative_int64(candidate[field], field=f"clock_skew_profile_{field}")
        for field in PROFILE_FIELDS:
            _require(type(candidate[field]) is type(expected[field]) and candidate[field] == expected[field], f"E_CLOCK_SKEW_PROFILE_{field.upper()}_EXACT", "frozen profile drift")
    _require(profiles[0]["track_id"] != profiles[1]["track_id"], "E_CLOCK_SKEW_POLICY_DISTINCTNESS", "distinct profiles required")
    return tuple(profiles)


def _validate_request(request: Mapping[str, Any]) -> Mapping[str, int]:
    _exact_keys(request, REQUEST_FIELDS, "E_CLOCK_SKEW_REQUEST_FIELDS")
    for field in REQUEST_FIELDS:
        _nonnegative_int64(request[field], field=f"clock_skew_request_{field}")
    return request


def _select_profile(
    profiles: tuple[Mapping[str, Any], ...],
    predecessor_receipt: Mapping[str, Any],
    request: Mapping[str, int],
) -> Mapping[str, Any]:
    match_values: dict[str, Any] = {
        "t10_receipt_content_sha256": predecessor_receipt.get("content_sha256"),
        "track_id": predecessor_receipt.get("track_id"),
        **{field: request[field] for field in REQUEST_FIELDS},
    }
    matches = [
        profile
        for profile in profiles
        if all(type(profile[field]) is type(match_values[field]) and profile[field] == match_values[field] for field in PROFILE_FIELDS)
    ]
    _require(len(matches) != 0, "E_CLOCK_SKEW_ZERO_MATCH_DENY", "no exact five-dimension profile")
    _require(len(matches) == 1, "E_CLOCK_SKEW_MULTIPLE_MATCH_DENY", "ambiguous profiles rejected")
    return matches[0]


def _validate_clock_skew_arithmetic(
    predecessor_receipt: Mapping[str, Any],
    request: Mapping[str, int],
) -> None:
    observed = predecessor_receipt.get("observed_at_unix_seconds")
    validation = predecessor_receipt.get("validation_checked_at_unix_seconds")
    decision = predecessor_receipt.get("decision_recheck_at_unix_seconds")
    for field, value in (
        ("observed_at_unix_seconds", observed),
        ("validation_checked_at_unix_seconds", validation),
        ("decision_recheck_at_unix_seconds", decision),
    ):
        _nonnegative_int64(value, field=f"t10_receipt_{field}")
    validation_reference = request["validation_reference_time_unix_seconds"]
    decision_reference = request["decision_recheck_reference_time_unix_seconds"]
    maximum = request["maximum_clock_skew_seconds"]
    _require(maximum <= 300, "E_CLOCK_SKEW_MAXIMUM_BOUND", "maximum clock skew exceeds 300 seconds")
    _require(
        validation_reference <= decision_reference,
        "E_CLOCK_SKEW_REFERENCE_ORDER",
        "validation reference is later than decision reference",
    )
    _require(
        abs(validation - validation_reference) <= maximum,
        "E_CLOCK_SKEW_VALIDATION_REFERENCE_EXCEEDED",
        "T10 validation label exceeds symmetric skew bound",
    )
    _require(
        abs(decision - decision_reference) <= maximum,
        "E_CLOCK_SKEW_DECISION_REFERENCE_EXCEEDED",
        "T10 decision label exceeds symmetric skew bound",
    )
    _require(
        max(0, observed - validation_reference) <= maximum,
        "E_CLOCK_SKEW_OBSERVATION_FUTURE_OF_VALIDATION_REFERENCE",
        "T10 observation is too far future-dated against validation reference",
    )
    _require(
        max(0, observed - decision_reference) <= maximum,
        "E_CLOCK_SKEW_OBSERVATION_FUTURE_OF_DECISION_REFERENCE",
        "T10 observation is too far future-dated against decision reference",
    )


def _bind_predecessor_receipt(receipt: Mapping[str, Any], profile: Mapping[str, Any]) -> None:
    expected_strings = {
        "content_sha256": profile["t10_receipt_content_sha256"],
        "execution_mode": SYNTHETIC_KAT_MODE,
        "schema": predecessor.RECEIPT_SCHEMA,
        "track_id": profile["track_id"],
    }
    for field, expected in expected_strings.items():
        _require(type(receipt.get(field)) is str and receipt.get(field) == expected, f"E_T10_RECEIPT_{field.upper()}_BINDING", f"T10 {field} drift")
    expected_scalars: dict[str, Any] = {
        "freshness_policy_separately_injected": True,
        "isolated_lab_candidate_surface_component_total": 8,
        "isolated_lab_candidate_surface_components_implemented": 8,
        "local_t09_specification_exercised": True,
        "local_t10_specification_exercised": True,
        "local_t11_specification_exercised": False,
        "production_admissible": False,
        "production_currentness_proved": False,
        "provider_authority": False,
        "runtime_authority": False,
        "t10_freshness_implemented": True,
    }
    for field, expected in expected_scalars.items():
        _require(type(receipt.get(field)) is type(expected) and receipt.get(field) == expected, f"E_T10_RECEIPT_{field.upper()}_BINDING", f"T10 {field} truth drift")


def _domain_sha256(domain: str, raw: bytes) -> str:
    return hashlib.sha256(domain.encode("ascii") + b"\x00" + raw).hexdigest()


def review_clock_skew(
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
    separately_injected_synthetic_freshness_policy: bytes,
    detached_freshness_request: bytes,
    separately_injected_synthetic_clock_skew_policy: bytes,
    detached_clock_skew_request: bytes,
    mode: str,
) -> dict[str, Any]:
    """Review one exact isolated-lab T11 clock-skew KAT or fail closed."""

    _reject_mode(mode)
    try:
        predecessor_receipt = predecessor.review_freshness(
            frame,
            detached_authentication_bundle,
            separately_injected_synthetic_trust_policy,
            separately_injected_synthetic_signer_authorization_policy,
            detached_authorization_request,
            separately_injected_synthetic_track_profile_binding_policy,
            detached_track_profile_binding_request,
            separately_injected_synthetic_end_to_end_subject_binding_policy,
            detached_end_to_end_subject_binding_request,
            separately_injected_synthetic_content_identity_and_quarantine_custody_policy,
            detached_content_identity_and_quarantine_custody_request,
            separately_injected_synthetic_freshness_policy,
            detached_freshness_request,
            predecessor.SYNTHETIC_KAT_MODE,
        )
    except predecessor.FreshnessReviewError as error:
        raise ClockSkewReviewError(
            "E_PREDECESSOR_FRESHNESS_REJECTED",
            f"{error.code}: {error.detail}",
            detail_code=error.code,
        ) from error

    try:
        policy = _decode_closed_json(
            separately_injected_synthetic_clock_skew_policy,
            limit=MAX_POLICY_BYTES,
            label="CLOCK_SKEW_POLICY",
        )
        profiles = _validate_policy(policy)
    except ClockSkewReviewError as error:
        raise ClockSkewReviewError(
            "E_CLOCK_SKEW_POLICY_REJECTED",
            f"{error.code}: {error.detail}",
            detail_code=error.code,
        ) from error

    try:
        request_object = _decode_closed_json(
            detached_clock_skew_request,
            limit=MAX_REQUEST_BYTES,
            label="CLOCK_SKEW_REQUEST",
        )
        request = _validate_request(request_object)
        selected = _select_profile(profiles, predecessor_receipt, request)
        _bind_predecessor_receipt(predecessor_receipt, selected)
        _validate_clock_skew_arithmetic(predecessor_receipt, request)
    except ClockSkewReviewError as error:
        raise ClockSkewReviewError(
            TARGET_PRODUCTION_FAILURE_CODE,
            f"{error.code}: {error.detail}",
            detail_code=error.code,
        ) from error

    observed = predecessor_receipt["observed_at_unix_seconds"]
    validation = predecessor_receipt["validation_checked_at_unix_seconds"]
    decision = predecessor_receipt["decision_recheck_at_unix_seconds"]
    validation_reference = request["validation_reference_time_unix_seconds"]
    decision_reference = request["decision_recheck_reference_time_unix_seconds"]
    maximum = request["maximum_clock_skew_seconds"]
    receipt: dict[str, Any] = {
        "action_or_resource_capability_authorized": False,
        "authority_decision_exact_source_commit": "e867ac4169ce4c4d1ae3dbe2dc6b12ad38ffad72",
        "authority_decision_release_commit": "66f4754fd871169f50f345e5c023c94466f8ffd4",
        "authorized_unit": AUTHORIZED_UNIT,
        "binding_match_count": 1,
        "binding_policy_match_dimension_count": len(PROFILE_FIELDS),
        "binding_policy_match_fields": list(PROFILE_FIELDS),
        "binding_profile_count": len(profiles),
        "binding_request_field_count": len(REQUEST_FIELDS),
        "binding_request_fields": list(REQUEST_FIELDS),
        "caller_supplied_predecessor_receipt_accepted": False,
        "component_state": COMPONENT_STATE,
        "condition_output_authorized": False,
        "content_sha256": "0" * 64,
        "decision_clock_skew_seconds": abs(decision - decision_reference),
        "decision_recheck_reference_time_unix_seconds": decision_reference,
        "default_disposition": DEFAULT_DISPOSITION,
        "downstream_gate_count": 4,
        "downstream_gates_authorized": 0,
        "durable_custody_implemented": False,
        "durable_replay_cas_implemented": False,
        "evidence_acceptance_authorized": False,
        "execution_mode": SYNTHETIC_KAT_MODE,
        "fault_injection_authorized": False,
        "future_date_offsets_within_maximum_clock_skew": True,
        "clock_skew_arithmetic_relation": CLOCK_SKEW_RELATION,
        "clock_skew_integer_labels_are_trusted_time": False,
        "clock_skew_policy_is_production_policy": False,
        "clock_skew_policy_separately_injected": True,
        "clock_skew_policy_sha256": hashlib.sha256(separately_injected_synthetic_clock_skew_policy).hexdigest(),
        "clock_skew_request_detached": True,
        "clock_skew_request_observed_after_policy": True,
        "clock_skew_request_sha256": hashlib.sha256(detached_clock_skew_request).hexdigest(),
        "implementation_authority_single_use_consumed": True,
        "isolated_lab_candidate_surface_component_total": 9,
        "isolated_lab_candidate_surface_components_implemented": 9,
        "isolated_lab_candidate_surface_components_locally_kat_exercised": 9,
        "local_t09_specification_exercised": True,
        "local_t10_specification_exercised": True,
        "local_t11_specification_exercised": True,
        "local_threat_specifications_covered": 11,
        "local_threat_specifications_covered_ids": [f"T{value:02d}" for value in range(1, 12)],
        "matching_profile": MATCHING_PROFILE,
        "maximum_clock_skew_seconds": maximum,
        "maximum_clock_skew_seconds_upper_bound": 300,
        "network_time_accessed": False,
        "observation_future_of_decision_reference_seconds": max(0, observed - decision_reference),
        "observation_future_of_validation_reference_seconds": max(0, observed - validation_reference),
        "output_or_claim_authorized": False,
        "predecessor_receipt_and_track_non_substitutable": True,
        "predecessor_receipt_content_sha256": predecessor_receipt["content_sha256"],
        "predecessor_receipt_schema": predecessor.RECEIPT_SCHEMA,
        "predecessor_review_count": 1,
        "production_admissible": False,
        "production_currentness_proved": False,
        "production_ingestion_control_count": 14,
        "production_ingestion_controls_implemented": 0,
        "production_ingestion_controls_runtime_exercised": 0,
        "production_threat_specification_count": 20,
        "production_threat_specifications_runtime_exercised": 0,
        "production_trusted_time_implemented": False,
        "production_validated_evidence_items": 0,
        "provider_authority": False,
        "public_input_count": 16,
        "real_evidence_items_present": 0,
        "reference_time_order_valid": validation_reference <= decision_reference,
        "reject_on_multiple_matches": True,
        "reject_on_zero_matches": True,
        "retention_record_implemented": False,
        "runtime_authority": False,
        "runtime_evidence_accepted": 0,
        "runtime_prerequisite_count": 16,
        "runtime_prerequisites_satisfied": 0,
        "schema": RECEIPT_SCHEMA,
        "schema_version": 1,
        "signed_trusted_time_bound": False,
        "side_effects_unlocked": "NONE",
        "status": STATUS,
        "symmetric_clock_skew_within_maximum": True,
        "synthetic_fixture": True,
        "synthetic_reference_time_labels_are_trusted_time": False,
        "t09_content_identity_and_quarantine_custody_implemented": True,
        "t10_freshness_implemented": True,
        "t10_decision_recheck_at_unix_seconds": decision,
        "t10_observed_at_unix_seconds": observed,
        "t10_validation_checked_at_unix_seconds": validation,
        "t11_clock_skew_implemented": True,
        "t12_owner_toctou_implemented": False,
        "target_production_control": TARGET_PRODUCTION_CONTROL,
        "target_production_failure_code": TARGET_PRODUCTION_FAILURE_CODE,
        "tombstone_record_implemented": False,
        "track_id": predecessor_receipt["track_id"],
        "track_identity_source": "T10_PREDECESSOR_RECEIPT_ONLY",
        "trusted_time_source_accessed": False,
        "validation_clock_skew_seconds": abs(validation - validation_reference),
        "validation_reference_time_unix_seconds": validation_reference,
        "wall_or_monotonic_clock_accessed": False,
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
    "CLOCK_SKEW_RELATION",
    "MATCHING_PROFILE",
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
    "ClockSkewProfile",
    "ClockSkewReviewError",
    "known_answer_clock_skew_policy",
    "known_answer_clock_skew_policy_bytes",
    "known_answer_clock_skew_request",
    "known_answer_clock_skew_request_bytes",
    "review_clock_skew",
]
