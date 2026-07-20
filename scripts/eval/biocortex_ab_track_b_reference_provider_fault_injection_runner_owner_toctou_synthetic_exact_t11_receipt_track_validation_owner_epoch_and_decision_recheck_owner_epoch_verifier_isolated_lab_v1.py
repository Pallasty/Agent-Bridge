#!/usr/bin/env python3
"""Pure public isolated-lab T12 owner-TOCTOU equality verifier."""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Mapping, NoReturn

import biocortex_ab_track_b_reference_provider_fault_injection_runner_clock_skew_synthetic_exact_t10_receipt_track_validation_reference_time_decision_recheck_reference_time_and_maximum_clock_skew_seconds_verifier_isolated_lab_v1 as predecessor

SYNTHETIC_KAT_MODE = "SYNTHETIC_KAT"
PRODUCTION_MODE = "PRODUCTION"
POLICY_SCHEMA = "agent_bridge.biocortex_ab_track_b_reference_provider_fault_injection_runner.owner_toctou_synthetic_policy_isolated_lab_kat.v1"
RECEIPT_SCHEMA = "agent_bridge.biocortex_ab_track_b_reference_provider_fault_injection_runner.owner_toctou_synthetic_exact_t11_receipt_track_validation_owner_epoch_and_decision_recheck_owner_epoch_verifier_isolated_lab_v1.receipt.v0"
STATUS = "REFERENCE_PROVIDER_MANAGED_AND_SELF_HOSTED_FAULT_INJECTION_RUNNER_V1_OWNER_TOCTOU_SYNTHETIC_EXACT_T11_RECEIPT_TRACK_VALIDATION_OWNER_EPOCH_AND_DECISION_RECHECK_OWNER_EPOCH_VERIFIED_ISOLATED_LAB_COMPONENT_ONLY_NO_PRODUCTION_AUTHORITY"
COMPONENT_STATE = "BOUND_SYNTHETIC_OWNER_EPOCH_EQUALITY_TO_EXACT_T11_RECEIPT_CHAIN_ONLY"
AUTHORIZED_UNIT = "REFERENCE_PROVIDER_MANAGED_AND_SELF_HOSTED_FAULT_INJECTION_RUNNER_V1_OWNER_TOCTOU_SYNTHETIC_EXACT_T11_RECEIPT_TRACK_VALIDATION_OWNER_EPOCH_AND_DECISION_RECHECK_OWNER_EPOCH_VERIFIER_ISOLATED_LAB_IMPLEMENTATION"
RECEIPT_HASH_DOMAIN = "AB_TRACK_B_T12_OWNER_TOCTOU_ISOLATED_LAB_KAT_RECEIPT_V1"
MATCHING_PROFILE = "EXACT_ALL_FIELDS_AND_SIGNED_INT64_VALUES_EQUAL"
DEFAULT_DISPOSITION = "REJECTED_FAIL_CLOSED"
OWNER_EPOCH_RELATION = "VALIDATION_OWNER_EPOCH_EXACTLY_EQUALS_DECISION_RECHECK_OWNER_EPOCH"
TARGET_PRODUCTION_CONTROL = "OWNER_IDENTITY_ROLE_SIGNATURE_AND_DECISION_WINDOW"
TARGET_PRODUCTION_FAILURE_CODE = "E_PRODUCTION_OWNER_IDENTITY_OR_WINDOW_FAILED"
MAX_POLICY_BYTES = 65_536
MAX_REQUEST_BYTES = 16_384
MAX_SIGNED_INT64 = 2**63 - 1
POLICY_KEYS = ("default_disposition", "matching_profile", "profiles", "reject_on_multiple_matches", "reject_on_zero_matches", "schema", "schema_version")
REQUEST_FIELDS = ("validation_owner_epoch", "decision_recheck_owner_epoch")
PROFILE_FIELDS = ("t11_receipt_content_sha256", "track_id", *REQUEST_FIELDS)

@dataclass(frozen=True)
class OwnerToctouProfile:
    t11_receipt_content_sha256: str
    track_id: str
    validation_owner_epoch: int
    decision_recheck_owner_epoch: int

PROFILES = (
    OwnerToctouProfile("63f0c26f10f42c923b55c4e651c001f7c38c42d9e25d7db772b4abbeadbe2ed8", "MANAGED_SPANNER_CLOUD_KMS", 41, 41),
    OwnerToctouProfile("ce5af4f0ada753ed9a526909d071e5cb14959a6183f9169e67854d9ebcc4aee1", "SELF_HOSTED_ETCD_OPENBAO", 73, 73),
)

class OwnerToctouReviewError(ValueError):
    def __init__(self, code: str, detail: str, *, detail_code: str | None = None):
        super().__init__(f"{code}: {detail}")
        self.code, self.detail, self.detail_code = code, detail, detail_code

def _fail(code: str, detail: str) -> NoReturn:
    raise OwnerToctouReviewError(code, detail)

def _require(ok: bool, code: str, detail: str) -> None:
    if not ok: _fail(code, detail)

def _reject_mode(mode: str) -> None:
    if type(mode) is not str: _fail("E_OWNER_TOCTOU_MODE_UNKNOWN", "mode must be exact string")
    if mode == PRODUCTION_MODE: _fail("E_OWNER_TOCTOU_PRODUCTION_MODE_NOT_AUTHORIZED", "production owner state is outside isolated-lab authority")
    if mode != SYNTHETIC_KAT_MODE: _fail("E_OWNER_TOCTOU_MODE_UNKNOWN", "only SYNTHETIC_KAT is reviewable")

def _pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in items:
        _require(type(key) is str and key not in out, "E_JSON_DUPLICATE_KEY", "duplicate or nonstring key")
        out[key] = value
    return out

def _no_number(value: str) -> NoReturn:
    _fail("E_JSON_NON_INTEGER_NUMBER", value)

def _parse_int(value: str) -> int:
    parsed = int(value)
    _require(-(2**63) <= parsed <= MAX_SIGNED_INT64, "E_JSON_INT_RANGE", "outside signed int64")
    return parsed

def _canonical(value: Mapping[str, Any]) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()

def _decode(raw: bytes, *, limit: int, label: str) -> dict[str, Any]:
    _require(type(raw) is bytes, f"E_{label}_TYPE", "must be exact bytes")
    _require(0 < len(raw) <= limit, f"E_{label}_SIZE", "size bound")
    try: text = raw.decode("utf-8", "strict")
    except UnicodeDecodeError as error: _fail(f"E_{label}_UTF8", str(error))
    decoder = json.JSONDecoder(object_pairs_hook=_pairs, parse_int=_parse_int, parse_float=_no_number, parse_constant=_no_number, strict=True)
    try: value, end = decoder.raw_decode(text)
    except OwnerToctouReviewError: raise
    except (json.JSONDecodeError, RecursionError) as error: _fail(f"E_{label}_JSON", str(error))
    _require(end == len(text) and type(value) is dict, f"E_{label}_ROOT_OR_TRAILING", "closed object required")
    _require(_canonical(value) == raw, f"E_{label}_NONCANONICAL", "canonical JSON required")
    return value

def _exact_keys(value: Mapping[str, Any], keys: tuple[str, ...], code: str) -> None:
    _require(type(value) is dict and set(value) == set(keys), code, "closed field set drift")

def _epoch(value: Any, field: str) -> int:
    _require(type(value) is int, f"E_{field.upper()}_TYPE", "exact integer required")
    _require(0 <= value <= MAX_SIGNED_INT64, f"E_{field.upper()}_RANGE", "nonnegative signed int64 required")
    return value

def _profile_dict(profile: OwnerToctouProfile) -> dict[str, Any]:
    return {field: getattr(profile, field) for field in PROFILE_FIELDS}

def known_answer_owner_toctou_policy() -> dict[str, Any]:
    return {"default_disposition": DEFAULT_DISPOSITION, "matching_profile": MATCHING_PROFILE, "profiles": [_profile_dict(p) for p in PROFILES], "reject_on_multiple_matches": True, "reject_on_zero_matches": True, "schema": POLICY_SCHEMA, "schema_version": 1}

def known_answer_owner_toctou_policy_bytes() -> bytes:
    return _canonical(known_answer_owner_toctou_policy())

def known_answer_owner_toctou_request(track_id: str) -> dict[str, int]:
    for profile in PROFILES:
        if profile.track_id == track_id:
            return {field: getattr(profile, field) for field in REQUEST_FIELDS}
    _fail("E_OWNER_TOCTOU_TRACK_UNKNOWN", "unknown track")

def known_answer_owner_toctou_request_bytes(track_id: str) -> bytes:
    return _canonical(known_answer_owner_toctou_request(track_id))

def _validate_policy(policy: Mapping[str, Any]) -> tuple[Mapping[str, Any], ...]:
    _exact_keys(policy, POLICY_KEYS, "E_OWNER_TOCTOU_POLICY_FIELDS")
    _require(policy["schema"] == POLICY_SCHEMA and type(policy["schema"]) is str, "E_OWNER_TOCTOU_POLICY_SCHEMA", "schema drift")
    _require(type(policy["schema_version"]) is int and policy["schema_version"] == 1, "E_OWNER_TOCTOU_POLICY_VERSION", "version drift")
    _require(policy["default_disposition"] == DEFAULT_DISPOSITION and policy["matching_profile"] == MATCHING_PROFILE, "E_OWNER_TOCTOU_POLICY_MATCHING", "default-deny exact matching required")
    _require(policy["reject_on_zero_matches"] is True and policy["reject_on_multiple_matches"] is True, "E_OWNER_TOCTOU_POLICY_AMBIGUITY", "zero/multiple must reject")
    profiles = policy["profiles"]
    _require(type(profiles) is list and len(profiles) == 2, "E_OWNER_TOCTOU_POLICY_PROFILES", "two ordered profiles required")
    for candidate, frozen in zip(profiles, PROFILES, strict=True):
        _exact_keys(candidate, PROFILE_FIELDS, "E_OWNER_TOCTOU_PROFILE_FIELDS")
        expected = _profile_dict(frozen)
        for field in REQUEST_FIELDS: _epoch(candidate[field], field)
        _require(type(candidate["track_id"]) is str and type(candidate["t11_receipt_content_sha256"]) is str, "E_OWNER_TOCTOU_PROFILE_STRING", "exact strings required")
        _require(candidate == expected, "E_OWNER_TOCTOU_PROFILE_EXACT", "frozen profile/order drift")
    return tuple(profiles)

def _validate_request(request: Mapping[str, Any]) -> Mapping[str, int]:
    _exact_keys(request, REQUEST_FIELDS, "E_OWNER_TOCTOU_REQUEST_FIELDS")
    for field in REQUEST_FIELDS: _epoch(request[field], field)
    return request

def review_owner_toctou(
    frame: bytes, detached_authentication_bundle: bytes,
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
    separately_injected_synthetic_owner_toctou_policy: bytes,
    detached_owner_toctou_request: bytes,
    mode: str,
) -> dict[str, Any]:
    _reject_mode(mode)
    try:
        prior = predecessor.review_clock_skew(frame, detached_authentication_bundle, separately_injected_synthetic_trust_policy, separately_injected_synthetic_signer_authorization_policy, detached_authorization_request, separately_injected_synthetic_track_profile_binding_policy, detached_track_profile_binding_request, separately_injected_synthetic_end_to_end_subject_binding_policy, detached_end_to_end_subject_binding_request, separately_injected_synthetic_content_identity_and_quarantine_custody_policy, detached_content_identity_and_quarantine_custody_request, separately_injected_synthetic_freshness_policy, detached_freshness_request, separately_injected_synthetic_clock_skew_policy, detached_clock_skew_request, predecessor.SYNTHETIC_KAT_MODE)
    except predecessor.ClockSkewReviewError as error:
        raise OwnerToctouReviewError("E_PREDECESSOR_CLOCK_SKEW_REJECTED", f"{error.code}: {error.detail}", detail_code=error.code) from error
    try:
        profiles = _validate_policy(_decode(separately_injected_synthetic_owner_toctou_policy, limit=MAX_POLICY_BYTES, label="OWNER_TOCTOU_POLICY"))
    except OwnerToctouReviewError as error:
        raise OwnerToctouReviewError("E_OWNER_TOCTOU_POLICY_REJECTED", f"{error.code}: {error.detail}", detail_code=error.code) from error
    try:
        request = _validate_request(_decode(detached_owner_toctou_request, limit=MAX_REQUEST_BYTES, label="OWNER_TOCTOU_REQUEST"))
        values = {"t11_receipt_content_sha256": prior.get("content_sha256"), "track_id": prior.get("track_id"), **request}
        matches = [profile for profile in profiles if all(type(profile[k]) is type(values[k]) and profile[k] == values[k] for k in PROFILE_FIELDS)]
        _require(len(matches) == 1, "E_OWNER_TOCTOU_EXACT_MATCH", "exactly one four-dimension profile required")
        _require(prior.get("schema") == predecessor.RECEIPT_SCHEMA and prior.get("t11_clock_skew_implemented") is True and prior.get("t12_owner_toctou_implemented") is False, "E_T11_RECEIPT_TRUTH", "T11 truth drift")
        _require(prior.get("isolated_lab_candidate_surface_component_total") == 9, "E_T11_RECEIPT_COMPONENT_TOTAL", "T11 component total drift")
        _require(request["validation_owner_epoch"] == request["decision_recheck_owner_epoch"], "E_OWNER_EPOCH_CHANGED", "owner epoch changed after validation")
    except OwnerToctouReviewError as error:
        raise OwnerToctouReviewError(TARGET_PRODUCTION_FAILURE_CODE, f"{error.code}: {error.detail}", detail_code=error.code) from error
    receipt: dict[str, Any] = {
        "action_or_resource_capability_authorized": False, "authority_decision_exact_source_commit": "42563ea784858454bbd478e5e890b639bdeca793", "authority_decision_release_commit": "e75f72c0d020dec5c957d3edb7344350bda20dcd", "authorized_unit": AUTHORIZED_UNIT,
        "binding_match_count": 1, "binding_policy_match_dimension_count": 4, "binding_policy_match_fields": list(PROFILE_FIELDS), "binding_profile_count": 2, "binding_request_field_count": 2, "binding_request_fields": list(REQUEST_FIELDS),
        "caller_supplied_predecessor_receipt_accepted": False, "component_state": COMPONENT_STATE, "content_sha256": "0"*64, "default_disposition": DEFAULT_DISPOSITION,
        "decision_recheck_owner_epoch": request["decision_recheck_owner_epoch"], "durable_custody_implemented": False, "evidence_acceptance_authorized": False, "execution_mode": SYNTHETIC_KAT_MODE,
        "implementation_authority_single_use_consumed": True, "isolated_lab_candidate_surface_component_total": 10, "isolated_lab_candidate_surface_components_implemented": 10, "isolated_lab_candidate_surface_components_locally_kat_exercised": 10,
        "local_threat_specifications_covered": 12, "local_threat_specifications_covered_ids": [f"T{i:02d}" for i in range(1,13)], "matching_profile": MATCHING_PROFILE,
        "network_accessed": False, "owner_epoch_relation": OWNER_EPOCH_RELATION, "owner_epoch_labels_are_real_identity_or_authorization": False,
        "owner_epoch_policy_is_production_policy": False, "owner_epoch_policy_separately_injected": True, "owner_epoch_policy_sha256": hashlib.sha256(separately_injected_synthetic_owner_toctou_policy).hexdigest(),
        "owner_epoch_request_detached": True, "owner_epoch_request_observed_after_policy": True, "owner_epoch_request_sha256": hashlib.sha256(detached_owner_toctou_request).hexdigest(),
        "predecessor_receipt_and_track_non_substitutable": True, "predecessor_receipt_content_sha256": prior["content_sha256"], "predecessor_receipt_schema": predecessor.RECEIPT_SCHEMA, "predecessor_review_count": 1,
        "production_admissible": False, "production_ingestion_control_count": 14, "production_ingestion_controls_implemented": 0, "production_threat_specification_count": 20, "production_threat_specifications_runtime_exercised": 0,
        "production_validated_evidence_items": 0, "provider_authority": False, "public_input_count": 18, "real_evidence_items_present": 0, "reject_on_multiple_matches": True, "reject_on_zero_matches": True,
        "runtime_authority": False, "runtime_evidence_accepted": 0, "runtime_prerequisite_count": 16, "runtime_prerequisites_satisfied": 0, "schema": RECEIPT_SCHEMA, "schema_version": 1,
        "side_effects_unlocked": "NONE", "status": STATUS, "synthetic_fixture": True, "t11_clock_skew_implemented": True, "t12_owner_toctou_implemented": True, "t13_authorized": False,
        "target_production_control": TARGET_PRODUCTION_CONTROL, "target_production_failure_code": TARGET_PRODUCTION_FAILURE_CODE, "track_id": prior["track_id"], "track_identity_source": "T11_PREDECESSOR_RECEIPT_ONLY", "validation_owner_epoch": request["validation_owner_epoch"],
    }
    without = dict(receipt); del without["content_sha256"]
    receipt["content_sha256"] = hashlib.sha256(RECEIPT_HASH_DOMAIN.encode()+b"\0"+_canonical(without)).hexdigest()
    return receipt

__all__ = ["AUTHORIZED_UNIT", "COMPONENT_STATE", "DEFAULT_DISPOSITION", "MATCHING_PROFILE", "OWNER_EPOCH_RELATION", "POLICY_SCHEMA", "PRODUCTION_MODE", "PROFILES", "PROFILE_FIELDS", "RECEIPT_SCHEMA", "REQUEST_FIELDS", "STATUS", "SYNTHETIC_KAT_MODE", "TARGET_PRODUCTION_CONTROL", "TARGET_PRODUCTION_FAILURE_CODE", "OwnerToctouProfile", "OwnerToctouReviewError", "known_answer_owner_toctou_policy", "known_answer_owner_toctou_policy_bytes", "known_answer_owner_toctou_request", "known_answer_owner_toctou_request_bytes", "review_owner_toctou"]
