#!/usr/bin/env python3
"""Independent adversarial checker for the isolated-lab T08 verifier.

The checker owns its policy, request, receipt-boundary, JSON, source-AST,
fixture, and schema oracles.  The two positive vectors traverse the real frozen
T07 public reviewer.  Directed T08 faults replace only that public edge with a
counted receipt spy, so order, exactly-once composition, and T07-receipt-only
track identity remain observable without importing subject validation helpers.

No provider, network, credential, clock, persistence, replay ledger, runner,
fault-injection, evidence-admission, output, or production authority is used or
granted by this checker.
"""

from __future__ import annotations

import argparse
import ast
import copy
import hashlib
import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType
from typing import Any, Callable, Mapping, NoReturn


sys.dont_write_bytecode = True

ROOT = Path(__file__).resolve().parents[2]
SOURCE_REL = (
    "scripts/eval/biocortex_ab_track_b_reference_provider_fault_injection_runner_"
    "end_to_end_subject_binding_synthetic_exact_t07_receipt_track_prerequisite_"
    "source_build_session_channel_schedule_row_set_and_subject_verifier_"
    "isolated_lab_v1.py"
)
FIXTURE_REL = (
    "scripts/eval/fixtures/biocortex_ab_track_b_reference_provider_fault_injection_"
    "runner_end_to_end_subject_binding_synthetic_exact_t07_receipt_track_"
    "prerequisite_source_build_session_channel_schedule_row_set_and_subject_verifier_"
    "isolated_lab_v1_pack_synthetic_v0.json"
)
SCHEMA_REL = (
    "docs/design/fixtures/biocortex-ab-track-b-reference-provider-fault-injection-"
    "runner-end-to-end-subject-binding-synthetic-exact-t07-receipt-track-"
    "prerequisite-source-build-session-channel-schedule-row-set-and-subject-verifier-"
    "isolated-lab-v1.schema.json"
)
PREDECESSOR_SOURCE_REL = (
    "scripts/eval/biocortex_ab_track_b_reference_provider_fault_injection_runner_"
    "track_profile_binding_synthetic_exact_packet_profile_provider_or_lab_profile_"
    "namespace_configuration_sha256_and_non_substitutable_track_verifier_"
    "isolated_lab_v1.py"
)
PREDECESSOR_FIXTURE_REL = (
    "scripts/eval/fixtures/biocortex_ab_track_b_reference_provider_fault_injection_"
    "runner_track_profile_binding_synthetic_exact_packet_profile_provider_or_lab_"
    "profile_namespace_configuration_sha256_and_non_substitutable_track_verifier_"
    "isolated_lab_v1_pack_"
    "synthetic_v0.json"
)
T06_FIXTURE_REL = (
    "scripts/eval/fixtures/biocortex_ab_track_b_reference_provider_fault_injection_"
    "runner_signer_role_scope_authorization_synthetic_exact_owner_class_evidence_"
    "class_track_subject_audience_and_nonce_policy_verifier_isolated_lab_v1_pack_"
    "synthetic_v0.json"
)
T05_FIXTURE_REL = (
    "scripts/eval/fixtures/biocortex_ab_track_b_reference_provider_fault_injection_"
    "runner_bootstrap_trust_authentication_synthetic_trust_chain_exact_key_version_"
    "declared_role_and_revocation_verifier_isolated_lab_v1_pack_synthetic_v0.json"
)
OWNER_DECISION_REL = (
    "scripts/eval/fixtures/biocortex_ab_track_b_reference_provider_fault_injection_"
    "runner_end_to_end_subject_binding_isolated_lab_implementation_authority_and_"
    "resource_binding_decision_v1_pack_owner_decision_v0.json"
)
SEMANTIC_SPECIFICATION_REL = (
    "scripts/eval/fixtures/biocortex_ab_track_b_reference_provider_fault_injection_"
    "runner_runtime_prerequisite_evidence_packet_offline_integration_and_production_"
    "evidence_ingestion_boundary_review_v1_pack_synthetic_v0.json"
)

DATE = "2026-07-18"
SYNTHETIC_MODE = "SYNTHETIC_KAT"
PRODUCTION_MODE = "PRODUCTION"
POLICY_SCHEMA = (
    "agent_bridge.biocortex_ab_track_b_reference_provider_fault_injection_runner."
    "end_to_end_subject_binding_synthetic_policy_isolated_lab_kat.v1"
)
RECEIPT_SCHEMA = (
    "agent_bridge.biocortex_ab_track_b_reference_provider_fault_injection_runner."
    "end_to_end_subject_binding_synthetic_exact_t07_receipt_track_prerequisite_"
    "source_build_session_channel_schedule_row_set_and_subject_verifier_"
    "isolated_lab_v1.receipt.v0"
)
FIXTURE_SCHEMA = (
    "agent_bridge.biocortex_ab_track_b_reference_provider_fault_injection_runner."
    "end_to_end_subject_binding_synthetic_exact_t07_receipt_track_prerequisite_"
    "source_build_session_channel_schedule_row_set_and_subject_verifier_"
    "isolated_lab_v1_pack.synthetic.v0"
)
PACK_RECEIPT_SCHEMA = (
    "agent_bridge.biocortex_ab_track_b_reference_provider_fault_injection_runner."
    "end_to_end_subject_binding_synthetic_exact_t07_receipt_track_prerequisite_"
    "source_build_session_channel_schedule_row_set_and_subject_verifier_"
    "isolated_lab_v1_pack.receipt.v0"
)
STATUS = (
    "REFERENCE_PROVIDER_MANAGED_AND_SELF_HOSTED_FAULT_INJECTION_RUNNER_V1_"
    "END_TO_END_SUBJECT_BINDING_SYNTHETIC_EXACT_T07_RECEIPT_TRACK_PREREQUISITE_"
    "SOURCE_BUILD_SESSION_CHANNEL_SCHEDULE_ROW_SET_AND_SUBJECT_"
    "VERIFIED_ISOLATED_LAB_COMPONENT_ONLY_NO_PRODUCTION_AUTHORITY"
)
DECISION = (
    "T08_SYNTHETIC_EXACT_END_TO_END_SUBJECT_BINDING_COMPONENT_CONFORMANT_"
    "PRODUCTION_PATH_FAIL_CLOSED"
)
COMPONENT_STATE = (
    "BOUND_SYNTHETIC_KAT_END_TO_END_SUBJECT_LABELS_TO_EXACT_T07_RECEIPT_CHAIN_ONLY"
)
RECEIPT_DOMAIN = "AB_TRACK_B_END_TO_END_SUBJECT_BINDING_ISOLATED_LAB_KAT_RECEIPT_V1"
PACK_RECEIPT_DOMAIN = (
    "AB_TRACK_B_END_TO_END_SUBJECT_BINDING_ISOLATED_LAB_PACK_RECEIPT_V1"
)
POLICY_SHA256 = "829f8f81f4e8bc4bd5a74922e556f9d36784939773d257d2aee6e99515c0c33f"
PREDECESSOR_SOURCE_SHA256 = (
    "777bfaa0c18569e68af1cf7c6e5957f1712079bfcfe4e2085e607dba5c9fcb23"
)
PREDECESSOR_FIXTURE_SHA256 = (
    "97a45faa1a2e4d1198c5ea5222ada4d31e46093c8956ecb319a2912e46b5b4e4"
)
T06_FIXTURE_SHA256 = (
    "cb5e0950cd6ec4835f6fbbb64e80ee656ba825ec92910b4be1032761f6238ff9"
)
OWNER_DECISION_SHA256 = (
    "2fd96dd1bfc038c65ea067d69b928148763d7e8e0671ef3d378bc72118332277"
)
SEMANTIC_SPECIFICATION_SHA256 = (
    "3aee2bc2f27290e9a57789d434f4373609b720f7ee1d963871fd99a613f55ff6"
)
AUTHORITY_SOURCE_COMMIT = "7dad255248e60dc8649c1e1e825a37beaeb530a8"
AUTHORITY_INTEGRATION_COMMIT = "8521ff6a9784a6d74be2b8ee0e02f3aba6b9f8a5"
AUTHORITY_FULL_STDOUT_SHA256 = "779d124f5b71904221ede99a0199dcd53ef404ef4790aea5584f62ed93d40d99"
SOURCE_RAW_SHA256 = (
    "2752e8b4ca393f5db14d7c980e65a5a71cdbff38a4eb19c861fffe5cc3ffc7f8"
)
FIXTURE_RAW_SHA256 = (
    "ab966ecef10652730b752f3308326f8fdba9cf61a3b688cfe421efc3788567c6"
)
SCHEMA_RAW_SHA256 = (
    "40d23b17f45f0c4cec7fa83e76b6edbf3616d3cb70a5466a3a111d33bab0c841"
)

MATCHING_PROFILE = "EXACT_ALL_FIELDS_ASCII_BYTE_EQUAL"
DEFAULT_DISPOSITION = "REJECTED_FAIL_CLOSED"
REQUEST_FIELDS = (
    "prerequisite_id",
    "source_id",
    "build_id",
    "session_id",
    "channel_id",
    "schedule_id",
    "row_set_id",
    "subject",
)
MATCH_FIELDS = (
    "t07_receipt_content_sha256",
    "track_id",
    *REQUEST_FIELDS,
)
POLICY_KEYS = (
    "default_disposition",
    "matching_profile",
    "profiles",
    "reject_on_multiple_matches",
    "reject_on_zero_matches",
    "schema",
    "schema_version",
)
PROFILE_KEYS = MATCH_FIELDS
FORBIDDEN_REQUEST_FIELDS = (
    "audience",
    "configuration_sha256",
    "declared_role_class",
    "frame_sha256",
    "namespace_id",
    "nonce",
    "packet_profile_id",
    "provider_or_lab_profile_id",
    "signer_key_id",
    "signer_key_version",
    "signer_role",
    "t07_receipt",
    "t07_receipt_content_sha256",
    "track_id",
)

PROFILES: tuple[dict[str, str], ...] = (
    {
        "build_id": "KAT_MANAGED_T08_BUILD_V1",
        "channel_id": "KAT_MANAGED_T08_CHANNEL_V1",
        "prerequisite_id": "KAT_MANAGED_T08_PREREQUISITE_V1",
        "row_set_id": "KAT_MANAGED_T08_ROW_SET_V1",
        "schedule_id": "KAT_MANAGED_T08_SCHEDULE_V1",
        "session_id": "KAT_MANAGED_T08_SESSION_V1",
        "source_id": "KAT_MANAGED_T08_SOURCE_V1",
        "subject": "KAT_MANAGED_VALID_MINIMAL_FRAME_SUBJECT_V1",
        "t07_receipt_content_sha256": (
            "5db2449ebf80e668ac7fc8ccaec6cc62a7461d8874809543a74ee9b7b5d725b6"
        ),
        "track_id": "MANAGED_SPANNER_CLOUD_KMS",
        "case_id": "VALID_MANAGED_END_TO_END_SUBJECT_BINDING_V1",
        "predecessor_case_id": "VALID_MANAGED_TRACK_PROFILE_BINDING_V1",
    },
    {
        "build_id": "KAT_SELF_HOSTED_T08_BUILD_V1",
        "channel_id": "KAT_SELF_HOSTED_T08_CHANNEL_V1",
        "prerequisite_id": "KAT_SELF_HOSTED_T08_PREREQUISITE_V1",
        "row_set_id": "KAT_SELF_HOSTED_T08_ROW_SET_V1",
        "schedule_id": "KAT_SELF_HOSTED_T08_SCHEDULE_V1",
        "session_id": "KAT_SELF_HOSTED_T08_SESSION_V1",
        "source_id": "KAT_SELF_HOSTED_T08_SOURCE_V1",
        "subject": "KAT_SELF_HOSTED_VALID_MINIMAL_FRAME_SUBJECT_V1",
        "t07_receipt_content_sha256": (
            "3f49518a74a6a7075335db5b139035613ff992d1deedc0c31216832dd4dcb014"
        ),
        "track_id": "SELF_HOSTED_ETCD_OPENBAO",
        "case_id": "VALID_SELF_HOSTED_END_TO_END_SUBJECT_BINDING_V1",
        "predecessor_case_id": "VALID_SELF_HOSTED_TRACK_PROFILE_BINDING_V1",
    },
)

RECEIPT_KEYS = (
    "action_or_resource_capability_authorized",
    "binding_match_count",
    "binding_policy_match_dimension_count",
    "binding_policy_match_fields",
    "binding_profile_count",
    "binding_request_field_count",
    "binding_request_fields",
    "bootstrap_trust_authentication_implemented",
    "build_id",
    "build_truth_proved",
    "caller_supplied_predecessor_receipt_accepted",
    "channel_id",
    "channel_truth_proved",
    "component_state",
    "condition_output_authorized",
    "content_sha256",
    "default_disposition",
    "downstream_gate_count",
    "downstream_gates_authorized",
    "durable_replay_cas_implemented",
    "end_to_end_subject_binding_isolated_lab_component_implemented",
    "end_to_end_subject_binding_policy_is_production_policy",
    "end_to_end_subject_binding_policy_separately_injected",
    "end_to_end_subject_binding_policy_sha256",
    "end_to_end_subject_binding_request_detached",
    "end_to_end_subject_binding_request_observed_after_policy",
    "end_to_end_subject_binding_request_sha256",
    "evidence_acceptance_authorized",
    "execution_mode",
    "fault_injection_authorized",
    "frame_reparsed_by_t08_after_t07_success",
    "isolated_lab_candidate_surface_component_total",
    "isolated_lab_candidate_surface_components_implemented",
    "isolated_lab_candidate_surface_components_locally_kat_exercised",
    "local_t05_specification_exercised",
    "local_t06_specification_exercised",
    "local_t07_specification_exercised",
    "local_t08_specification_exercised",
    "local_t09_specification_exercised",
    "local_threat_specifications_covered",
    "local_threat_specifications_covered_ids",
    "matching_profile",
    "output_or_claim_authorized",
    "predecessor_receipt_and_track_non_substitutable",
    "predecessor_receipt_content_sha256",
    "predecessor_receipt_schema",
    "predecessor_review_count",
    "prerequisite_id",
    "prerequisite_truth_proved",
    "production_admissible",
    "production_ingestion_control_count",
    "production_ingestion_controls_implemented",
    "production_ingestion_controls_runtime_exercised",
    "production_signer_role_scope_authorization_implemented",
    "production_threat_specification_count",
    "production_threat_specifications_runtime_exercised",
    "production_track_subject_binding_implemented",
    "production_validated_evidence_items",
    "provider_authority",
    "public_input_count",
    "real_evidence_items_present",
    "reject_on_multiple_matches",
    "reject_on_zero_matches",
    "row_set_id",
    "row_set_truth_proved",
    "runtime_authority",
    "runtime_evidence_accepted",
    "runtime_prerequisite_count",
    "runtime_prerequisites_satisfied",
    "schedule_id",
    "schedule_truth_proved",
    "schema",
    "schema_version",
    "session_id",
    "session_truth_proved",
    "side_effects_unlocked",
    "signer_role_scope_authorization_isolated_lab_component_implemented",
    "source_id",
    "source_truth_proved",
    "status",
    "subject",
    "subject_identity_authenticated",
    "subject_truth_proved",
    "synthetic_fixture",
    "t07_track_profile_binding_isolated_lab_component_implemented",
    "t08_end_to_end_subject_binding_implemented",
    "t09_content_identity_and_quarantine_custody_implemented",
    "target_production_control",
    "target_production_failure_code",
    "track_id",
    "track_identity_source",
    "track_profile_binding_isolated_lab_component_implemented",
    "wildcard_prefix_hierarchy_or_inheritance_authorization_implemented",
)

TSV_FIELDS = (
    "schema",
    "status",
    "decision",
    "date",
    "component_mode",
    "component_state",
    "positive_track_count",
    "real_predecessor_review_count",
    "public_mode_pre_observation_test_count",
    "predecessor_exactly_once_order_test_count",
    "policy_json_negative_test_count",
    "request_json_negative_test_count",
    "policy_closed_world_negative_test_count",
    "request_exact_field_negative_test_count",
    "predecessor_receipt_binding_negative_test_count",
    "default_deny_negative_test_count",
    "total_directed_negative_test_count",
    "source_ast_guard_count",
    "fixture_schema_guard_count",
    "fixture_expected_receipt_count",
    "binding_profile_count",
    "request_field_count",
    "policy_match_dimension_count",
    "isolated_lab_candidate_surface_component_total",
    "isolated_lab_candidate_surface_components_implemented",
    "local_threat_specifications_covered",
    "production_ingestion_control_count",
    "production_ingestion_controls_implemented",
    "production_threat_specification_count",
    "production_threat_specifications_runtime_exercised",
    "runtime_prerequisite_count",
    "runtime_prerequisites_satisfied",
    "real_evidence_items_present",
    "production_validated_evidence_items",
    "runtime_authority",
    "provider_authority",
    "side_effects_unlocked",
    "end_to_end_subject_binding_policy_sha256",
    "end_to_end_subject_binding_request_set_sha256",
    "receipt_set_sha256",
    "schema_raw_sha256",
    "fixture_raw_sha256",
    "source_raw_sha256",
    "predecessor_source_raw_sha256",
    "predecessor_fixture_raw_sha256",
    "owner_decision_raw_sha256",
    "t07_semantic_specification_raw_sha256",
    "content_sha256",
)


class CheckError(ValueError):
    """Independent checker failure."""


def require(condition: bool, code: str, detail: str) -> None:
    if not condition:
        raise CheckError(f"{code}: {detail}")


def exact_equal(left: Any, right: Any) -> bool:
    if type(left) is not type(right):
        return False
    if type(left) is dict:
        return set(left) == set(right) and all(
            exact_equal(left[key], right[key]) for key in left
        )
    if type(left) in (list, tuple):
        return len(left) == len(right) and all(
            exact_equal(a, b) for a, b in zip(left, right, strict=True)
        )
    return bool(left == right)


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
    return sha256(domain.encode("ascii") + b"\x00" + canonical_bytes(value))


def checked_path(relative: str) -> Path:
    require(
        type(relative) is str
        and relative
        and not relative.startswith("/")
        and "\\" not in relative
        and "\x00" not in relative
        and all(part not in ("", ".", "..") for part in relative.split("/")),
        "E_PATH",
        repr(relative),
    )
    candidate = ROOT.joinpath(*relative.split("/"))
    resolved = candidate.resolve(strict=True)
    require(resolved == ROOT or ROOT in resolved.parents, "E_PATH_ESCAPE", relative)
    require(candidate.is_file() and not candidate.is_symlink(), "E_PATH_FILE", relative)
    return candidate


def raw_sha256(relative: str) -> str:
    return sha256(checked_path(relative).read_bytes())


def _artifact_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        require(type(key) is str and key not in result, "E_ARTIFACT_DUPLICATE_KEY", repr(key))
        result[key] = value
    return result


def _artifact_int(token: str) -> int:
    value = int(token, 10)
    require(-(2**63) <= value <= 2**63 - 1, "E_ARTIFACT_INT", token)
    return value


def _artifact_float(token: str) -> NoReturn:
    raise CheckError(f"E_ARTIFACT_FLOAT: {token}")


def _artifact_constant(token: str) -> NoReturn:
    raise CheckError(f"E_ARTIFACT_NONFINITE: {token}")


def read_artifact_json(relative: str) -> dict[str, Any]:
    raw = checked_path(relative).read_bytes()
    require(0 < len(raw) <= 8 * 1024 * 1024, "E_ARTIFACT_SIZE", relative)
    require(not raw.startswith(b"\xef\xbb\xbf"), "E_ARTIFACT_BOM", relative)
    text = raw.decode("utf-8", "strict")
    decoder = json.JSONDecoder(
        object_pairs_hook=_artifact_pairs,
        parse_int=_artifact_int,
        parse_float=_artifact_float,
        parse_constant=_artifact_constant,
        strict=True,
    )
    try:
        value, end = decoder.raw_decode(text)
    except (json.JSONDecodeError, RecursionError) as error:
        raise CheckError(f"E_ARTIFACT_JSON: {relative}: {error}") from error
    require(not text[end:].strip(), "E_ARTIFACT_TRAILING", relative)
    require(type(value) is dict, "E_ARTIFACT_ROOT", relative)
    return value


def expected_policy() -> dict[str, Any]:
    profiles = [{key: profile[key] for key in PROFILE_KEYS} for profile in PROFILES]
    result = {
        "default_disposition": DEFAULT_DISPOSITION,
        "matching_profile": MATCHING_PROFILE,
        "profiles": profiles,
        "reject_on_multiple_matches": True,
        "reject_on_zero_matches": True,
        "schema": POLICY_SCHEMA,
        "schema_version": 1,
    }
    require(sha256(canonical_bytes(result)) == POLICY_SHA256, "E_POLICY_HASH_ORACLE", sha256(canonical_bytes(result)))
    return result


def expected_request(profile: Mapping[str, str]) -> dict[str, Any]:
    return {key: profile[key] for key in REQUEST_FIELDS}


def expected_valid_case(profile: Mapping[str, str]) -> dict[str, Any]:
    return {
        "case_id": profile["case_id"],
        "detached_end_to_end_subject_binding_request": expected_request(profile),
        "predecessor_case_id": profile["predecessor_case_id"],
        "track_id": profile["track_id"],
    }


def load_module() -> ModuleType:
    path = checked_path(SOURCE_REL)
    module_name = "_end_to_end_subject_binding_subject_under_review"
    spec = importlib.util.spec_from_file_location(module_name, path)
    require(spec is not None and spec.loader is not None, "E_SOURCE_IMPORT_SPEC", SOURCE_REL)
    eval_dir = str(path.parent)
    inserted = eval_dir not in sys.path
    if inserted:
        sys.path.insert(0, eval_dir)
    try:
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)
    finally:
        if inserted:
            sys.path.remove(eval_dir)
    return module


class ObservationBomb:
    """Record and abort every observation except reading event_count."""

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
    events: list[str] = []

    def __eq__(self, other: object) -> bool:
        type(self).events.append("eq")
        raise AssertionError("hostile str subclass compared")

    def __ne__(self, other: object) -> bool:
        type(self).events.append("ne")
        raise AssertionError("hostile str subclass compared")

    __hash__ = str.__hash__


def call_review(
    module: ModuleType,
    frame: Any,
    bundle: Any,
    trust_policy: Any,
    signer_policy: Any,
    authorization_request: Any,
    track_profile_binding_policy: Any,
    track_profile_binding_request: Any,
    end_to_end_subject_binding_policy: Any,
    end_to_end_subject_binding_request: Any,
    mode: Any,
) -> Any:
    return module.review_end_to_end_subject_binding(
        frame,
        bundle,
        trust_policy,
        signer_policy,
        authorization_request,
        track_profile_binding_policy,
        track_profile_binding_request,
        end_to_end_subject_binding_policy,
        end_to_end_subject_binding_request,
        mode,
    )


def expect_rejection(
    module: ModuleType,
    inputs: tuple[Any, Any, Any, Any, Any, Any, Any, Any, Any],
    mode: Any,
    label: str,
    expected_code: str | None = None,
    expected_detail_code: str | None = None,
) -> None:
    try:
        call_review(module, *inputs, mode)
    except module.EndToEndSubjectBindingReviewError as error:
        if expected_code is not None:
            require(error.code == expected_code, "E_REJECTION_CODE", f"{label}:{error.code}")
        if expected_detail_code is not None:
            require(error.detail_code == expected_detail_code, "E_REJECTION_DETAIL_CODE", f"{label}:{error.detail_code}")
    else:
        raise CheckError(f"E_MUTATION_ACCEPTED: {label}")


def _mutated(value: Mapping[str, Any], operation: Callable[[dict[str, Any]], None]) -> bytes:
    result = copy.deepcopy(value)
    operation(result)
    return canonical_bytes(result)


def _noncanonical_bytes(value: Mapping[str, Any]) -> bytes:
    return json.dumps(
        dict(list(value.items())[::-1]),
        sort_keys=False,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
    ).encode("utf-8")


def positive_checks(
    module: ModuleType,
    fixture: Mapping[str, Any],
    predecessor_fixture: Mapping[str, Any],
    t06_fixture: Mapping[str, Any],
    t05_fixture: Mapping[str, Any],
) -> tuple[
    tuple[bytes, bytes, bytes, bytes, bytes, bytes, bytes, bytes, bytes],
    list[bytes],
    list[dict[str, Any]],
    list[dict[str, Any]],
    int,
]:
    policy = expected_policy()
    policy_raw = canonical_bytes(policy)
    require(
        exact_equal(module.known_answer_end_to_end_subject_binding_policy(), policy)
        and module.known_answer_end_to_end_subject_binding_policy_bytes() == policy_raw,
        "E_POLICY_HELPER_ORACLE",
        "subject known-answer policy differs",
    )

    predecessor_cases = {
        case["case_id"]: case for case in predecessor_fixture["valid_cases"]
    }
    t06_cases = {case["case_id"]: case for case in t06_fixture["valid_cases"]}
    t05_cases = {case["case_id"]: case for case in t05_fixture["valid_cases"]}
    predecessor_receipts = {
        receipt["track_id"]: receipt
        for receipt in predecessor_fixture["expected_receipts"]
    }
    trust_policy_raw = canonical_bytes(
        t05_fixture["separately_injected_synthetic_trust_policy"]
    )
    signer_policy_raw = canonical_bytes(
        t06_fixture[
            "separately_injected_synthetic_signer_authorization_policy"
        ]
    )
    predecessor_policy_raw = canonical_bytes(
        predecessor_fixture[
            "separately_injected_synthetic_track_profile_binding_policy"
        ]
    )

    real_reviewer = module.predecessor.review_track_profile_binding
    real_calls: list[tuple[Any, ...]] = []

    def counted_real_reviewer(*args: Any, **kwargs: Any) -> Any:
        real_calls.append(args)
        return real_reviewer(*args, **kwargs)

    module.predecessor.review_track_profile_binding = counted_real_reviewer
    request_raws: list[bytes] = []
    receipts: list[dict[str, Any]] = []
    t07_receipts: list[dict[str, Any]] = []
    first_inputs: tuple[
        bytes, bytes, bytes, bytes, bytes, bytes, bytes, bytes, bytes
    ] | None = None
    try:
        for index, profile in enumerate(PROFILES):
            t07_case = predecessor_cases[profile["predecessor_case_id"]]
            t06_case = t06_cases[t07_case["predecessor_case_id"]]
            t05_case = t05_cases[t06_case["predecessor_case_id"]]
            frame_raw = t05_case["frame_utf8"].encode("utf-8")
            bundle_raw = canonical_bytes(t05_case["detached_authentication_bundle"])
            authorization_request_raw = canonical_bytes(
                t06_case["detached_authorization_request"]
            )
            request = expected_request(profile)
            request_raw = canonical_bytes(request)
            predecessor_request_raw = canonical_bytes(
                t07_case["detached_track_profile_binding_request"]
            )

            require(
                t05_case["track_id"]
                == t06_case["track_id"]
                == t07_case["track_id"]
                == profile["track_id"],
                "E_PREDECESSOR_CASE_TRACK",
                profile["track_id"],
            )
            require(
                predecessor_receipts[profile["track_id"]]["content_sha256"]
                == profile["t07_receipt_content_sha256"],
                "E_T07_RECEIPT_HASH_ORACLE",
                profile["track_id"],
            )
            require(
                exact_equal(
                    module.known_answer_end_to_end_subject_binding_request(
                        profile["track_id"]
                    ),
                    request,
                )
                and module.known_answer_end_to_end_subject_binding_request_bytes(
                    profile["track_id"]
                )
                == request_raw,
                "E_REQUEST_HELPER_ORACLE",
                profile["track_id"],
            )

            inputs = (
                frame_raw,
                bundle_raw,
                trust_policy_raw,
                signer_policy_raw,
                authorization_request_raw,
                predecessor_policy_raw,
                predecessor_request_raw,
                policy_raw,
                request_raw,
            )
            before = len(real_calls)
            subject_receipt = call_review(module, *inputs, SYNTHETIC_MODE)
            require(
                len(real_calls) == before + 1,
                "E_POSITIVE_PREDECESSOR_CALL_COUNT",
                profile["track_id"],
            )
            require(
                exact_equal(subject_receipt, fixture["expected_receipts"][index]),
                "E_FIXTURE_EXPECTED_RECEIPT",
                profile["track_id"],
            )
            validate_receipt_oracle(
                subject_receipt,
                profile,
                policy_raw,
                request_raw,
            )
            if first_inputs is None:
                first_inputs = inputs
            request_raws.append(request_raw)
            receipts.append(copy.deepcopy(subject_receipt))
            t07_receipts.append(copy.deepcopy(predecessor_receipts[profile["track_id"]]))
    finally:
        module.predecessor.review_track_profile_binding = real_reviewer

    require(first_inputs is not None, "E_POSITIVE_VECTOR", "no positive vector")
    require(len(real_calls) == 2, "E_REAL_PREDECESSOR_TOTAL", str(len(real_calls)))
    return first_inputs, request_raws, receipts, t07_receipts, len(real_calls)


def validate_receipt_oracle(
    receipt: Mapping[str, Any],
    profile: Mapping[str, str],
    policy_raw: bytes,
    request_raw: bytes,
) -> None:
    require(type(receipt) is dict, "E_RECEIPT_TYPE", type(receipt).__name__)
    require(set(receipt) == set(RECEIPT_KEYS), "E_RECEIPT_FIELDS", repr(set(receipt) ^ set(RECEIPT_KEYS)))
    exact_values: dict[str, Any] = {
        "schema": RECEIPT_SCHEMA,
        "schema_version": 1,
        "status": STATUS,
        "component_state": COMPONENT_STATE,
        "execution_mode": SYNTHETIC_MODE,
        "default_disposition": DEFAULT_DISPOSITION,
        "matching_profile": MATCHING_PROFILE,
        "binding_profile_count": 2,
        "binding_match_count": 1,
        "binding_policy_match_dimension_count": 10,
        "binding_request_field_count": 8,
        "binding_request_fields": list(REQUEST_FIELDS),
        "binding_policy_match_fields": list(MATCH_FIELDS),
        "predecessor_review_count": 1,
        "track_identity_source": "T07_PREDECESSOR_RECEIPT_ONLY",
        "track_id": profile["track_id"],
        "predecessor_receipt_content_sha256": profile["t07_receipt_content_sha256"],
        **{field: profile[field] for field in REQUEST_FIELDS},
        "end_to_end_subject_binding_policy_sha256": sha256(policy_raw),
        "end_to_end_subject_binding_request_sha256": sha256(request_raw),
        "end_to_end_subject_binding_policy_is_production_policy": False,
        "end_to_end_subject_binding_policy_separately_injected": True,
        "end_to_end_subject_binding_request_detached": True,
        "end_to_end_subject_binding_request_observed_after_policy": True,
        "isolated_lab_candidate_surface_component_total": 6,
        "isolated_lab_candidate_surface_components_implemented": 6,
        "isolated_lab_candidate_surface_components_locally_kat_exercised": 6,
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
        "bootstrap_trust_authentication_implemented": True,
        "local_t05_specification_exercised": True,
        "local_t06_specification_exercised": True,
        "local_t07_specification_exercised": True,
        "local_t08_specification_exercised": True,
        "local_t09_specification_exercised": False,
        "end_to_end_subject_binding_isolated_lab_component_implemented": True,
        "t07_track_profile_binding_isolated_lab_component_implemented": True,
        "track_profile_binding_isolated_lab_component_implemented": True,
        "t08_end_to_end_subject_binding_implemented": True,
        "t09_content_identity_and_quarantine_custody_implemented": False,
        "target_production_control": "TRACK_SUBJECT_BINDING",
        "target_production_failure_code": "E_PRODUCTION_TRACK_SUBJECT_BINDING_FAILED",
        "production_track_subject_binding_implemented": False,
        "production_signer_role_scope_authorization_implemented": False,
        "production_admissible": False,
        "production_ingestion_control_count": 14,
        "production_ingestion_controls_implemented": 0,
        "production_ingestion_controls_runtime_exercised": 0,
        "production_threat_specification_count": 20,
        "production_threat_specifications_runtime_exercised": 0,
        "production_validated_evidence_items": 0,
        "runtime_prerequisite_count": 16,
        "runtime_prerequisites_satisfied": 0,
        "runtime_evidence_accepted": 0,
        "real_evidence_items_present": 0,
        "public_input_count": 10,
        "downstream_gate_count": 4,
        "downstream_gates_authorized": 0,
        "reject_on_zero_matches": True,
        "reject_on_multiple_matches": True,
        "synthetic_fixture": True,
        "predecessor_receipt_and_track_non_substitutable": True,
        "predecessor_receipt_schema": (
            "agent_bridge.biocortex_ab_track_b_reference_provider_fault_injection_"
            "runner.track_profile_binding_synthetic_exact_packet_profile_provider_"
            "or_lab_profile_namespace_configuration_sha256_and_non_substitutable_"
            "track_verifier_"
            "isolated_lab_v1.receipt.v0"
        ),
        "signer_role_scope_authorization_isolated_lab_component_implemented": True,
        "runtime_authority": False,
        "provider_authority": False,
        "evidence_acceptance_authorized": False,
        "output_or_claim_authorized": False,
        "fault_injection_authorized": False,
        "side_effects_unlocked": "NONE",
    }
    missing = set(exact_values) - set(receipt)
    require(not missing, "E_RECEIPT_REQUIRED_FIELDS", repr(sorted(missing)))
    for field, expected in exact_values.items():
        require(exact_equal(receipt[field], expected), "E_RECEIPT_VALUE", field)

    false_nonclaims = {
        "action_or_resource_capability_authorized",
        "build_truth_proved",
        "caller_supplied_predecessor_receipt_accepted",
        "channel_truth_proved",
        "condition_output_authorized",
        "durable_replay_cas_implemented",
        "frame_reparsed_by_t08_after_t07_success",
        "prerequisite_truth_proved",
        "row_set_truth_proved",
        "schedule_truth_proved",
        "session_truth_proved",
        "source_truth_proved",
        "subject_identity_authenticated",
        "subject_truth_proved",
        "wildcard_prefix_hierarchy_or_inheritance_authorization_implemented",
    }
    missing_nonclaims = false_nonclaims - set(receipt)
    require(not missing_nonclaims, "E_RECEIPT_NONCLAIM_FIELDS", repr(sorted(missing_nonclaims)))
    require(
        all(receipt[field] is False for field in false_nonclaims),
        "E_RECEIPT_NONCLAIM_TRUE",
        repr(sorted(field for field in false_nonclaims if receipt[field] is not False)),
    )
    require(type(receipt.get("content_sha256")) is str, "E_RECEIPT_CONTENT_TYPE", repr(receipt.get("content_sha256")))
    unsigned = dict(receipt)
    observed = unsigned.pop("content_sha256")
    require(observed == domain_sha256(RECEIPT_DOMAIN, unsigned), "E_RECEIPT_CONTENT_HASH", str(observed))


def check_pre_observation_modes(module: ModuleType) -> int:
    original = module.predecessor.review_track_profile_binding
    predecessor_calls: list[tuple[Any, ...]] = []

    def forbidden_predecessor(*args: Any, **kwargs: Any) -> Any:
        predecessor_calls.append(args)
        raise AssertionError("predecessor observed before mode acceptance")

    module.predecessor.review_track_profile_binding = forbidden_predecessor
    modes: tuple[tuple[str, Any, str], ...] = (
        ("production", PRODUCTION_MODE, "E_END_TO_END_SUBJECT_BINDING_PRODUCTION_MODE_NOT_AUTHORIZED"),
        ("unknown_string", "SYNTHETIC", "E_END_TO_END_SUBJECT_BINDING_MODE_UNKNOWN"),
        ("unknown_integer", 7, "E_END_TO_END_SUBJECT_BINDING_MODE_UNKNOWN"),
        ("str_subclass", HostileStringSubclass(SYNTHETIC_MODE), "E_END_TO_END_SUBJECT_BINDING_MODE_UNKNOWN"),
    )
    try:
        for label, mode, code in modes:
            HostileStringSubclass.events.clear()
            bombs = tuple(
                ObservationBomb(f"{label}-{name}")
                for name in (
                    "frame",
                    "bundle",
                    "trust",
                    "signer-policy",
                    "authorization-request",
                    "track-profile-policy",
                    "track-profile-request",
                    "end-to-end-policy",
                    "end-to-end-request",
                )
            )
            expect_rejection(module, bombs, mode, label, code)
            require(all(bomb.event_count == 0 for bomb in bombs), "E_MODE_OBSERVED_INPUT", label)
            require(not HostileStringSubclass.events, "E_MODE_COMPARED_STR_SUBCLASS", label)
    finally:
        module.predecessor.review_track_profile_binding = original
    require(not predecessor_calls, "E_MODE_PREDECESSOR_CALLED", str(len(predecessor_calls)))
    return len(modes)


def check_predecessor_exactly_once_order(
    module: ModuleType,
    inputs: tuple[bytes, bytes, bytes, bytes, bytes, bytes, bytes, bytes, bytes],
    predecessor_receipt: Mapping[str, Any],
) -> int:
    original_reviewer = module.predecessor.review_track_profile_binding
    original_decode = module._decode_closed_json
    events: list[str] = []
    reviewer_calls = 0
    behavior = "success"

    def reviewer_spy(*args: Any, **kwargs: Any) -> dict[str, Any]:
        nonlocal reviewer_calls
        reviewer_calls += 1
        events.append("t07")
        if behavior == "reject":
            raise module.predecessor.TrackProfileBindingReviewError(
                "E_SPY_T07_REJECTED",
                "injected predecessor rejection",
            )
        return copy.deepcopy(predecessor_receipt)

    def decode_spy(raw: Any, *, limit: int, label: str) -> dict[str, Any]:
        events.append(f"decode:{label}")
        return original_decode(raw, limit=limit, label=label)

    module.predecessor.review_track_profile_binding = reviewer_spy
    module._decode_closed_json = decode_spy
    tests = 0
    try:
        behavior = "reject"
        events.clear()
        before = reviewer_calls
        bombs = tuple(ObservationBomb(f"t07-reject-{index}") for index in range(9))
        expect_rejection(
            module,
            bombs,
            SYNTHETIC_MODE,
            "t07_rejection_precedes_policy_request",
            "E_PREDECESSOR_TRACK_PROFILE_BINDING_REJECTED",
            "E_SPY_T07_REJECTED",
        )
        require(reviewer_calls == before + 1 and events == ["t07"], "E_T07_REJECTION_ORDER", repr(events))
        require(all(bomb.event_count == 0 for bomb in bombs), "E_T07_REJECTION_OBSERVATION", "caller observed an input")
        tests += 1

        behavior = "success"
        events.clear()
        before = reviewer_calls
        policy_reject_inputs = (
            *inputs[:7],
            b"{}",
            ObservationBomb("policy-reject-request"),
        )
        request_bomb = policy_reject_inputs[-1]
        expect_rejection(
            module,
            policy_reject_inputs,
            SYNTHETIC_MODE,
            "policy_rejection_precedes_request",
            "E_END_TO_END_SUBJECT_BINDING_POLICY_REJECTED",
        )
        require(
            reviewer_calls == before + 1
            and events == ["t07", "decode:END_TO_END_SUBJECT_BINDING_POLICY"]
            and request_bomb.event_count == 0,
            "E_POLICY_REQUEST_ORDER",
            repr(events),
        )
        tests += 1

        events.clear()
        before = reviewer_calls
        expect_rejection(
            module,
            (*inputs[:8], b"{}"),
            SYNTHETIC_MODE,
            "request_after_policy",
            "E_END_TO_END_SUBJECT_BINDING_FAILED",
        )
        require(
            reviewer_calls == before + 1
            and events
            == [
                "t07",
                "decode:END_TO_END_SUBJECT_BINDING_POLICY",
                "decode:END_TO_END_SUBJECT_BINDING_REQUEST",
            ],
            "E_REQUEST_ORDER",
            repr(events),
        )
        tests += 1

        events.clear()
        before = reviewer_calls
        receipt = call_review(module, *inputs, SYNTHETIC_MODE)
        require(
            reviewer_calls == before + 1
            and events
            == [
                "t07",
                "decode:END_TO_END_SUBJECT_BINDING_POLICY",
                "decode:END_TO_END_SUBJECT_BINDING_REQUEST",
            ]
            and receipt["predecessor_review_count"] == 1,
            "E_SUCCESS_ORDER",
            repr(events),
        )
        tests += 1
    finally:
        module._decode_closed_json = original_decode
        module.predecessor.review_track_profile_binding = original_reviewer
    return tests


def directed_mutations(
    module: ModuleType,
    inputs: tuple[bytes, bytes, bytes, bytes, bytes, bytes, bytes, bytes, bytes],
    predecessor_receipt: Mapping[str, Any],
) -> dict[str, int]:
    original_reviewer = module.predecessor.review_track_profile_binding
    reviewer_calls = 0

    def reviewer_spy(*args: Any, **kwargs: Any) -> dict[str, Any]:
        nonlocal reviewer_calls
        reviewer_calls += 1
        return copy.deepcopy(predecessor_receipt)

    module.predecessor.review_track_profile_binding = reviewer_spy
    policy = expected_policy()
    request = expected_request(PROFILES[0])
    counts = {
        "policy_json": 0,
        "request_json": 0,
        "policy_closed_world": 0,
        "request_exact_field": 0,
        "predecessor_receipt_binding": 0,
        "default_deny": 0,
    }

    def reject_with(
        label: str,
        *,
        policy_raw: Any = inputs[7],
        request_raw: Any = inputs[8],
        category: str,
        expected_code: str | None = None,
        expected_detail_code: str | None = None,
    ) -> None:
        before = reviewer_calls
        expect_rejection(
            module,
            (*inputs[:7], policy_raw, request_raw),
            SYNTHETIC_MODE,
            label,
            expected_code,
            expected_detail_code,
        )
        require(
            reviewer_calls == before + 1,
            "E_MUTATION_PREDECESSOR_CALL_COUNT",
            label,
        )
        counts[category] += 1

    try:
        deep: Any = "leaf"
        for _ in range(34):
            deep = {"x": deep}
        policy_json_cases: list[tuple[str, Any]] = [
            ("policy_empty", b""),
            ("policy_whitespace", b" "),
            ("policy_bom", b"\xef\xbb\xbf" + inputs[7]),
            ("policy_invalid_utf8", b"\xff"),
            ("policy_array_root", b"[]"),
            ("policy_null_root", b"null"),
            ("policy_trailing", inputs[7] + b"\n{}"),
            ("policy_duplicate", b'{"schema":"duplicate",' + inputs[7][1:]),
            ("policy_noncanonical", _noncanonical_bytes(policy)),
            ("policy_float", b'{"x":1.0}'),
            ("policy_nonfinite", b'{"x":NaN}'),
            ("policy_depth", canonical_bytes(deep)),
            (
                "policy_nodes",
                canonical_bytes({"x": [[0] * 64 for _ in range(64)]}),
            ),
            ("policy_members", canonical_bytes({f"k{i}": i for i in range(257)})),
            ("policy_array_limit", canonical_bytes({"x": list(range(65))})),
            ("policy_int64", b'{"x":9223372036854775808}'),
            ("policy_size", b" " * 65537),
            ("policy_text_not_bytes", inputs[7].decode("utf-8")),
            ("policy_bytearray", bytearray(inputs[7])),
        ]
        for label, raw in policy_json_cases:
            reject_with(label, policy_raw=raw, category="policy_json")

        request_json_cases: list[tuple[str, Any]] = [
            ("request_empty", b""),
            ("request_whitespace", b" "),
            ("request_bom", b"\xef\xbb\xbf" + inputs[8]),
            ("request_invalid_utf8", b"\xff"),
            ("request_array_root", b"[]"),
            ("request_null_root", b"null"),
            ("request_trailing", inputs[8] + b"\n{}"),
            (
                "request_duplicate",
                b'{"prerequisite_id":"duplicate",' + inputs[8][1:],
            ),
            ("request_noncanonical", _noncanonical_bytes(request)),
            ("request_float", b'{"x":1.0}'),
            ("request_nonfinite", b'{"x":Infinity}'),
            ("request_depth", canonical_bytes(deep)),
            (
                "request_nodes",
                canonical_bytes({"x": [[0] * 64 for _ in range(64)]}),
            ),
            ("request_members", canonical_bytes({f"k{i}": i for i in range(257)})),
            ("request_array_limit", canonical_bytes({"x": list(range(65))})),
            ("request_int64", b'{"x":-9223372036854775809}'),
            ("request_size", b" " * 16385),
            ("request_text_not_bytes", inputs[8].decode("utf-8")),
            ("request_bytearray", bytearray(inputs[8])),
        ]
        for label, raw in request_json_cases:
            reject_with(label, request_raw=raw, category="request_json")

        for key in POLICY_KEYS:
            reject_with(
                f"policy_missing_{key}",
                policy_raw=_mutated(policy, lambda value, key=key: value.pop(key)),
                category="policy_closed_world",
            )
        reject_with(
            "policy_extra",
            policy_raw=_mutated(policy, lambda value: value.__setitem__("extra", False)),
            category="policy_closed_world",
        )
        policy_top_mutations: tuple[tuple[str, Callable[[dict[str, Any]], None]], ...] = (
            ("schema", lambda value: value.__setitem__("schema", POLICY_SCHEMA + ".drift")),
            ("schema_version", lambda value: value.__setitem__("schema_version", True)),
            ("matching_profile", lambda value: value.__setitem__("matching_profile", "PREFIX")),
            ("default", lambda value: value.__setitem__("default_disposition", "ALLOW")),
            ("zero_bool", lambda value: value.__setitem__("reject_on_zero_matches", 1)),
            ("multiple_bool", lambda value: value.__setitem__("reject_on_multiple_matches", 1)),
            ("profiles_type", lambda value: value.__setitem__("profiles", {})),
            ("profiles_order", lambda value: value.__setitem__("profiles", list(reversed(value["profiles"])))),
        )
        for label, operation in policy_top_mutations:
            reject_with(
                f"policy_{label}",
                policy_raw=_mutated(policy, operation),
                category="policy_closed_world",
            )
        for profile_index in range(2):
            for key in PROFILE_KEYS:
                reject_with(
                    f"profile_{profile_index}_missing_{key}",
                    policy_raw=_mutated(
                        policy,
                        lambda value, profile_index=profile_index, key=key: value[
                            "profiles"
                        ][profile_index].pop(key),
                    ),
                    category="policy_closed_world",
                )
                replacement = (
                    "0" * 64
                    if key == "t07_receipt_content_sha256"
                    else "DRIFT"
                )
                reject_with(
                    f"profile_{profile_index}_drift_{key}",
                    policy_raw=_mutated(
                        policy,
                        lambda value, profile_index=profile_index, key=key, replacement=replacement: value[
                            "profiles"
                        ][profile_index].__setitem__(key, replacement),
                    ),
                    category="policy_closed_world",
                )
            reject_with(
                f"profile_{profile_index}_extra",
                policy_raw=_mutated(
                    policy,
                    lambda value, profile_index=profile_index: value["profiles"][
                        profile_index
                    ].__setitem__("extra", "FORBIDDEN"),
                ),
                category="policy_closed_world",
            )
        reject_with(
            "policy_non_ascii_profile",
            policy_raw=_mutated(
                policy,
                lambda value: value["profiles"][0].__setitem__("subject", "主题"),
            ),
            category="policy_closed_world",
        )
        reject_with(
            "policy_profile_string_too_long",
            policy_raw=_mutated(
                policy,
                lambda value: value["profiles"][0].__setitem__("subject", "A" * 257),
            ),
            category="policy_closed_world",
        )

        for key in REQUEST_FIELDS:
            reject_with(
                f"request_missing_{key}",
                request_raw=_mutated(request, lambda value, key=key: value.pop(key)),
                category="request_exact_field",
            )
            reject_with(
                f"request_wrong_type_{key}",
                request_raw=_mutated(request, lambda value, key=key: value.__setitem__(key, 1)),
                category="request_exact_field",
            )
            replacement = "DRIFT"
            reject_with(
                f"request_mismatch_{key}",
                request_raw=_mutated(
                    request,
                    lambda value, key=key, replacement=replacement: value.__setitem__(key, replacement),
                ),
                category="request_exact_field",
            )
        for key in FORBIDDEN_REQUEST_FIELDS:
            reject_with(
                f"request_forbidden_{key}",
                request_raw=_mutated(
                    request,
                    lambda value, key=key: value.__setitem__(key, "FORBIDDEN"),
                ),
                category="request_exact_field",
            )
        for key in ("schema", "schema_version", "owner_class", "evidence_class", "audience", "nonce_scope"):
            reject_with(
                f"request_adjacent_identity_{key}",
                request_raw=_mutated(
                    request,
                    lambda value, key=key: value.__setitem__(key, "FORBIDDEN"),
                ),
                category="request_exact_field",
            )
        request_value_mutations: tuple[tuple[str, Callable[[dict[str, Any]], None]], ...] = (
            ("empty", lambda value: value.__setitem__("subject", "")),
            ("non_ascii", lambda value: value.__setitem__("subject", "主题")),
            ("too_long", lambda value: value.__setitem__("subject", "A" * 257)),
            ("untrimmed", lambda value: value.__setitem__("subject", " SUBJECT")),
            ("wildcard", lambda value: value.__setitem__("subject", "SUBJECT*")),
        )
        for label, operation in request_value_mutations:
            reject_with(
                f"request_{label}",
                request_raw=_mutated(request, operation),
                category="request_exact_field",
            )

        # A valid request for the other track must not substitute for T07 identity.
        reject_with(
            "cross_track_request_substitution",
            request_raw=canonical_bytes(expected_request(PROFILES[1])),
            category="default_deny",
            expected_code="E_END_TO_END_SUBJECT_BINDING_FAILED",
            expected_detail_code="E_END_TO_END_SUBJECT_BINDING_ZERO_MATCH_DENY",
        )
        reject_with(
            "zero_profile",
            policy_raw=_mutated(policy, lambda value: value.__setitem__("profiles", [])),
            category="default_deny",
        )
        reject_with(
            "multiple_exact_profiles",
            policy_raw=_mutated(
                policy,
                lambda value: value.__setitem__(
                    "profiles", [copy.deepcopy(value["profiles"][0])] * 2
                ),
            ),
            category="default_deny",
        )

        original_validate_policy = module._validate_policy

        def duplicate_profile_policy(value: Mapping[str, Any]) -> tuple[Mapping[str, Any], ...]:
            validated = original_validate_policy(value)
            return (copy.deepcopy(validated[0]), copy.deepcopy(validated[0]))

        module._validate_policy = duplicate_profile_policy
        try:
            reject_with(
                "directed_multiple_match_detail_code",
                category="default_deny",
                expected_code="E_END_TO_END_SUBJECT_BINDING_FAILED",
                expected_detail_code="E_END_TO_END_SUBJECT_BINDING_MULTIPLE_MATCH_DENY",
            )
        finally:
            module._validate_policy = original_validate_policy

        def receipt_rejection(
            label: str,
            operation: Callable[[dict[str, Any]], None],
            expected_detail_code: str | None = None,
        ) -> None:
            nonlocal predecessor_receipt, reviewer_calls
            mutated_receipt = copy.deepcopy(predecessor_receipt)
            operation(mutated_receipt)

            def mutated_reviewer(*args: Any, **kwargs: Any) -> dict[str, Any]:
                nonlocal reviewer_calls
                reviewer_calls += 1
                return copy.deepcopy(mutated_receipt)

            module.predecessor.review_track_profile_binding = mutated_reviewer
            reject_with(
                label,
                category="predecessor_receipt_binding",
                expected_code="E_END_TO_END_SUBJECT_BINDING_FAILED",
                expected_detail_code=expected_detail_code,
            )

        receipt_mutations: tuple[tuple[str, Callable[[dict[str, Any]], None], str | None], ...] = (
            ("receipt_missing_track", lambda value: value.pop("track_id"), "E_PREDECESSOR_RECEIPT_TRACK_ID_BINDING"),
            ("receipt_missing_content", lambda value: value.pop("content_sha256"), "E_PREDECESSOR_RECEIPT_CONTENT_SHA256_BINDING"),
            ("receipt_track_type", lambda value: value.__setitem__("track_id", 1), "E_PREDECESSOR_RECEIPT_TRACK_ID_BINDING"),
            ("receipt_content_type", lambda value: value.__setitem__("content_sha256", 1), "E_PREDECESSOR_RECEIPT_CONTENT_SHA256_BINDING"),
            ("receipt_track_unknown", lambda value: value.__setitem__("track_id", "UNKNOWN_TRACK"), "E_PREDECESSOR_RECEIPT_TRACK_ID_BINDING"),
            ("receipt_track_cross", lambda value: value.__setitem__("track_id", PROFILES[1]["track_id"]), "E_PREDECESSOR_RECEIPT_CONTENT_SHA256_BINDING"),
            ("receipt_content_unknown", lambda value: value.__setitem__("content_sha256", "0" * 64), "E_PREDECESSOR_RECEIPT_CONTENT_SHA256_BINDING"),
            (
                "receipt_content_cross",
                lambda value: value.__setitem__(
                    "content_sha256", PROFILES[1]["t07_receipt_content_sha256"]
                ),
                "E_PREDECESSOR_RECEIPT_CONTENT_SHA256_BINDING",
            ),
        )
        for label, operation, detail_code in receipt_mutations:
            receipt_rejection(label, operation, detail_code)
    finally:
        module.predecessor.review_track_profile_binding = original_reviewer

    require(
        counts["policy_json"] >= 19
        and counts["request_json"] >= 19
        and counts["policy_closed_world"] >= 35
        and counts["request_exact_field"] >= 35
        and counts["predecessor_receipt_binding"] >= 8
        and counts["default_deny"] >= 3,
        "E_MUTATION_COVERAGE",
        repr(counts),
    )
    return counts


def _top_level_function(tree: ast.Module, name: str) -> ast.FunctionDef:
    matches = [
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == name
    ]
    require(len(matches) == 1, "E_SOURCE_FUNCTION", f"{name}:{len(matches)}")
    return matches[0]


def _literal_assignment(tree: ast.Module, name: str) -> Any:
    matches: list[ast.expr] = []
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == name
            for target in node.targets
        ):
            matches.append(node.value)
        elif (
            isinstance(node, ast.AnnAssign)
            and isinstance(node.target, ast.Name)
            and node.target.id == name
            and node.value is not None
        ):
            matches.append(node.value)
    require(len(matches) == 1, "E_SOURCE_ASSIGNMENT", f"{name}:{len(matches)}")
    try:
        return ast.literal_eval(matches[0])
    except (ValueError, TypeError) as error:
        raise CheckError(f"E_SOURCE_LITERAL: {name}: {error}") from error


def source_contract_checks() -> int:
    path = checked_path(SOURCE_REL)
    raw = path.read_bytes()
    require(sha256(raw) == SOURCE_RAW_SHA256, "E_SOURCE_RAW_HASH", sha256(raw))
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
    predecessor_module = (
        "biocortex_ab_track_b_reference_provider_fault_injection_runner_"
        "track_profile_binding_synthetic_exact_packet_profile_provider_or_lab_"
        "profile_namespace_configuration_sha256_and_non_substitutable_track_"
        "verifier_isolated_lab_v1"
    )
    require(
        imports == {"__future__", "dataclasses", "hashlib", "json", "typing", predecessor_module},
        "E_SOURCE_FORBIDDEN_IMPORT",
        repr(sorted(imports)),
    )
    checks += 1

    public = _top_level_function(tree, "review_end_to_end_subject_binding")
    args = public.args
    require(
        [arg.arg for arg in args.args]
        == [
            "frame",
            "detached_authentication_bundle",
            "separately_injected_synthetic_trust_policy",
            "separately_injected_synthetic_signer_authorization_policy",
            "detached_authorization_request",
            "separately_injected_synthetic_track_profile_binding_policy",
            "detached_track_profile_binding_request",
            "separately_injected_synthetic_end_to_end_subject_binding_policy",
            "detached_end_to_end_subject_binding_request",
            "mode",
        ]
        and not args.defaults
        and args.vararg is None
        and args.kwarg is None
        and not args.kwonlyargs
        and not args.posonlyargs,
        "E_SOURCE_PUBLIC_SIGNATURE",
        ast.unparse(args),
    )
    checks += 1

    body = list(public.body)
    if (
        body
        and isinstance(body[0], ast.Expr)
        and isinstance(body[0].value, ast.Constant)
        and type(body[0].value.value) is str
    ):
        body = body[1:]
    require(
        body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Call),
        "E_SOURCE_FIRST_GUARD",
        "first executable statement is not a call",
    )
    first_call = body[0].value
    require(
        isinstance(first_call.func, ast.Name)
        and first_call.func.id == "_reject_mode"
        and [ast.unparse(arg) for arg in first_call.args] == ["mode"]
        and not first_call.keywords,
        "E_SOURCE_FIRST_GUARD",
        ast.unparse(first_call),
    )
    checks += 1

    calls = [node for node in ast.walk(public) if isinstance(node, ast.Call)]
    predecessor_calls = [
        node
        for node in calls
        if isinstance(node.func, ast.Attribute)
        and node.func.attr == "review_track_profile_binding"
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "predecessor"
    ]

    def named_calls(name: str) -> list[ast.Call]:
        return [
            node
            for node in calls
            if isinstance(node.func, ast.Name) and node.func.id == name
        ]

    policy_decodes = [
        node
        for node in named_calls("_decode_closed_json")
        if any(
            keyword.arg == "label"
            and isinstance(keyword.value, ast.Constant)
            and keyword.value.value == "END_TO_END_SUBJECT_BINDING_POLICY"
            for keyword in node.keywords
        )
    ]
    request_decodes = [
        node
        for node in named_calls("_decode_closed_json")
        if any(
            keyword.arg == "label"
            and isinstance(keyword.value, ast.Constant)
            and keyword.value.value == "END_TO_END_SUBJECT_BINDING_REQUEST"
            for keyword in node.keywords
        )
    ]
    policy_validations = named_calls("_validate_policy")
    request_validations = named_calls("_validate_request")
    selections = named_calls("_select_profile")
    receipt_bindings = named_calls("_bind_predecessor_receipt")
    require(
        len(predecessor_calls)
        == len(policy_decodes)
        == len(request_decodes)
        == len(policy_validations)
        == len(request_validations)
        == len(selections)
        == len(receipt_bindings)
        == 1,
        "E_SOURCE_REVIEW_CALL_COUNTS",
        (
            f"t07={len(predecessor_calls)},policy_decode={len(policy_decodes)},"
            f"request_decode={len(request_decodes)},select={len(selections)}"
        ),
    )
    require(
        predecessor_calls[0].lineno
        < policy_decodes[0].lineno
        < policy_validations[0].lineno
        < request_decodes[0].lineno
        < request_validations[0].lineno
        < selections[0].lineno
        < receipt_bindings[0].lineno,
        "E_SOURCE_REVIEW_ORDER",
        "mode -> T07 -> separate policy -> detached request last -> exact match",
    )
    require(
        [ast.unparse(arg) for arg in predecessor_calls[0].args]
        == [
            "frame",
            "detached_authentication_bundle",
            "separately_injected_synthetic_trust_policy",
            "separately_injected_synthetic_signer_authorization_policy",
            "detached_authorization_request",
            "separately_injected_synthetic_track_profile_binding_policy",
            "detached_track_profile_binding_request",
            "predecessor.SYNTHETIC_KAT_MODE",
        ]
        and not predecessor_calls[0].keywords,
        "E_SOURCE_PREDECESSOR_CALL",
        ast.unparse(predecessor_calls[0]),
    )
    checks += 1

    require(
        tuple(_literal_assignment(tree, "END_TO_END_SUBJECT_BINDING_POLICY_KEYS"))
        == (
            "default_disposition",
            "profiles",
            "reject_on_multiple_matches",
            "reject_on_zero_matches",
            "matching_profile",
            "schema",
            "schema_version",
        )
        and tuple(_literal_assignment(tree, "END_TO_END_SUBJECT_BINDING_PROFILE_FIELDS"))
        == MATCH_FIELDS
        and tuple(_literal_assignment(tree, "END_TO_END_SUBJECT_BINDING_REQUEST_FIELDS"))
        == REQUEST_FIELDS,
        "E_SOURCE_FIELD_CONSTANTS",
        "policy/profile/request field closure drift",
    )
    checks += 1

    # T08 may pass the first seven inputs only to T07, then observe policy/request.
    loaded_names = [
        node.id
        for node in ast.walk(public)
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load)
    ]
    expected_observation_counts = {
        "frame": 1,
        "detached_authentication_bundle": 1,
        "separately_injected_synthetic_trust_policy": 1,
        "separately_injected_synthetic_signer_authorization_policy": 1,
        "detached_authorization_request": 1,
        "separately_injected_synthetic_track_profile_binding_policy": 1,
        "detached_track_profile_binding_request": 1,
        # Each T08 byte input is decoded once and hashed once for the receipt.
        "separately_injected_synthetic_end_to_end_subject_binding_policy": 2,
        "detached_end_to_end_subject_binding_request": 2,
        "mode": 1,
    }
    for input_name, expected_count in expected_observation_counts.items():
        require(
            loaded_names.count(input_name) == expected_count,
            "E_SOURCE_INPUT_OBSERVATION_COUNT",
            f"{input_name}:{loaded_names.count(input_name)}",
        )
    checks += 1

    forbidden_calls = {
        "compile",
        "eval",
        "exec",
        "globals",
        "input",
        "locals",
        "open",
        "__import__",
    }
    forbidden_attributes = {
        "connect",
        "create_connection",
        "fork",
        "getenv",
        "popen",
        "read_bytes",
        "read_text",
        "request",
        "run",
        "sleep",
        "system",
        "time",
        "urlopen",
        "write_bytes",
        "write_text",
    }
    observed_forbidden: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name) and node.func.id in forbidden_calls:
                observed_forbidden.add(node.func.id)
            elif isinstance(node.func, ast.Attribute) and node.func.attr in forbidden_attributes:
                observed_forbidden.add(node.func.attr)
    require(not observed_forbidden, "E_SOURCE_FORBIDDEN_CALL", repr(sorted(observed_forbidden)))
    checks += 1

    require(
        not any(
            isinstance(
                node,
                (ast.Global, ast.Nonlocal, ast.AsyncFunctionDef, ast.Await, ast.Yield, ast.YieldFrom),
            )
            for node in ast.walk(tree)
        ),
        "E_SOURCE_MUTABLE_OR_ASYNC",
        "global/nonlocal/async/generator surface present",
    )
    checks += 1

    identifiers = {
        node.id for node in ast.walk(tree) if isinstance(node, ast.Name)
    } | {node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute)}
    forbidden_identifiers = {
        "credential",
        "credential_path",
        "private_key",
        "private_seed",
        "provider_endpoint",
        "secret_key",
        "secret_seed",
    }
    require(
        not identifiers.intersection(forbidden_identifiers),
        "E_SOURCE_SECRET_PROVIDER_OR_T08_IDENTIFIER",
        repr(sorted(identifiers.intersection(forbidden_identifiers))),
    )
    checks += 1

    exports = _literal_assignment(tree, "__all__")
    require(
        "review_end_to_end_subject_binding" in exports
        and "known_answer_end_to_end_subject_binding_policy_bytes" in exports
        and "known_answer_end_to_end_subject_binding_request_bytes" in exports
        and "EndToEndSubjectBindingReviewError" in exports,
        "E_SOURCE_EXPORTS",
        repr(exports),
    )
    checks += 1

    require(
        text.count("predecessor.review_track_profile_binding(") == 1
        and '"track_identity_source": "T07_PREDECESSOR_RECEIPT_ONLY"' in text
        and '"frame_reparsed_by_t08_after_t07_success": False' in text
        and '"wildcard_prefix_hierarchy_or_inheritance_authorization_implemented": False' in text,
        "E_SOURCE_LEXICAL_BINDING_BOUNDARY",
        "predecessor/track/frame/wildcard boundary drift",
    )
    checks += 1
    require(
        '"production_track_subject_binding_implemented": False' in text
        and '"end_to_end_subject_binding_isolated_lab_component_implemented": True' in text
        and '"target_production_control": TARGET_PRODUCTION_CONTROL' in text
        and '"t08_end_to_end_subject_binding_implemented": True' in text
        and '"t09_content_identity_and_quarantine_custody_implemented": False' in text,
        "E_SOURCE_AUTHORITY_TRUTH",
        "production/T08/T09 truth drift",
    )
    checks += 1
    return checks


def fixture_schema_checks() -> tuple[
    dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any], int
]:
    require(raw_sha256(FIXTURE_REL) == FIXTURE_RAW_SHA256, "E_FIXTURE_RAW_HASH", raw_sha256(FIXTURE_REL))
    require(raw_sha256(SCHEMA_REL) == SCHEMA_RAW_SHA256, "E_SCHEMA_RAW_HASH", raw_sha256(SCHEMA_REL))
    require(raw_sha256(PREDECESSOR_SOURCE_REL) == PREDECESSOR_SOURCE_SHA256, "E_PREDECESSOR_SOURCE_HASH", raw_sha256(PREDECESSOR_SOURCE_REL))
    require(raw_sha256(PREDECESSOR_FIXTURE_REL) == PREDECESSOR_FIXTURE_SHA256, "E_PREDECESSOR_FIXTURE_HASH", raw_sha256(PREDECESSOR_FIXTURE_REL))
    require(raw_sha256(T06_FIXTURE_REL) == T06_FIXTURE_SHA256, "E_T06_FIXTURE_HASH", raw_sha256(T06_FIXTURE_REL))
    require(raw_sha256(OWNER_DECISION_REL) == OWNER_DECISION_SHA256, "E_OWNER_DECISION_HASH", raw_sha256(OWNER_DECISION_REL))
    require(raw_sha256(SEMANTIC_SPECIFICATION_REL) == SEMANTIC_SPECIFICATION_SHA256, "E_SEMANTIC_SPECIFICATION_HASH", raw_sha256(SEMANTIC_SPECIFICATION_REL))
    fixture = read_artifact_json(FIXTURE_REL)
    schema = read_artifact_json(SCHEMA_REL)
    predecessor_fixture = read_artifact_json(PREDECESSOR_FIXTURE_REL)
    t06_fixture = read_artifact_json(T06_FIXTURE_REL)
    t05_fixture = read_artifact_json(T05_FIXTURE_REL)
    checks = 7

    fixture_keys = {
        "canonical_json_profile",
        "contains_private_or_seed_material",
        "date",
        "execution_mode",
        "expected_receipts",
        "public_only",
        "schema",
        "separately_injected_synthetic_end_to_end_subject_binding_policy",
        "source_bindings",
        "valid_cases",
    }
    require(set(fixture) == fixture_keys, "E_FIXTURE_FIELDS", repr(set(fixture)))
    checks += 1
    require(
        fixture["canonical_json_profile"] == "SORTED_KEYS_COMPACT_UTF8_NO_TRAILING_BYTES"
        and fixture["contains_private_or_seed_material"] is False
        and fixture["date"] == DATE
        and fixture["execution_mode"] == SYNTHETIC_MODE
        and fixture["public_only"] is True
        and fixture["schema"] == FIXTURE_SCHEMA,
        "E_FIXTURE_METADATA",
        "metadata drift",
    )
    checks += 1
    require(
        exact_equal(fixture["separately_injected_synthetic_end_to_end_subject_binding_policy"], expected_policy())
        and sha256(canonical_bytes(fixture["separately_injected_synthetic_end_to_end_subject_binding_policy"])) == POLICY_SHA256,
        "E_FIXTURE_POLICY",
        "independent policy mismatch",
    )
    checks += 1
    require(
        exact_equal(fixture["valid_cases"], [expected_valid_case(profile) for profile in PROFILES]),
        "E_FIXTURE_VALID_CASES",
        "valid cases drift",
    )
    checks += 1
    require(
        type(fixture["expected_receipts"]) is list
        and len(fixture["expected_receipts"]) == 2
        and all(type(receipt) is dict and set(receipt) == set(RECEIPT_KEYS) for receipt in fixture["expected_receipts"]),
        "E_FIXTURE_RECEIPT_SHAPE",
        "two exact closed 88-field receipts required",
    )
    checks += 1

    expected_bindings = {
        "authority_decision_integration_commit": AUTHORITY_INTEGRATION_COMMIT,
        "authority_decision_source_commit": AUTHORITY_SOURCE_COMMIT,
        "authority_integrated_full_stdout_sha256": AUTHORITY_FULL_STDOUT_SHA256,
        "owner_decision_path": OWNER_DECISION_REL,
        "owner_decision_sha256": OWNER_DECISION_SHA256,
        "predecessor_fixture_path": PREDECESSOR_FIXTURE_REL,
        "predecessor_fixture_sha256": PREDECESSOR_FIXTURE_SHA256,
        "predecessor_source_path": PREDECESSOR_SOURCE_REL,
        "predecessor_source_sha256": PREDECESSOR_SOURCE_SHA256,
        "t06_fixture_path": T06_FIXTURE_REL,
        "t06_fixture_sha256": T06_FIXTURE_SHA256,
        "t07_semantic_specification_path": SEMANTIC_SPECIFICATION_REL,
        "t07_semantic_specification_sha256": SEMANTIC_SPECIFICATION_SHA256,
        "end_to_end_subject_binding_policy_sha256": POLICY_SHA256,
    }
    require(exact_equal(fixture["source_bindings"], expected_bindings), "E_FIXTURE_SOURCE_BINDINGS", "source binding drift")
    checks += 1
    require(
        predecessor_fixture["contains_private_or_seed_material"] is False
        and predecessor_fixture["public_only"] is True
        and predecessor_fixture["execution_mode"] == SYNTHETIC_MODE
        and len(predecessor_fixture["valid_cases"]) == 2
        and len(predecessor_fixture["expected_receipts"]) == 2
        and t06_fixture["contains_private_or_seed_material"] is False
        and t06_fixture["public_only"] is True
        and len(t06_fixture["valid_cases"]) == 2
        and t05_fixture["contains_private_or_seed_material"] is False
        and t05_fixture["public_only"] is True
        and len(t05_fixture["valid_cases"]) == 2,
        "E_PREDECESSOR_FIXTURE_SEMANTICS",
        "T07/T06/T05 fixture drift",
    )
    checks += 1

    schema_keys = {
        "$schema",
        "title",
        "description",
        "$comment",
        "type",
        "required",
        "properties",
        "additionalProperties",
        "unevaluatedProperties",
        "minProperties",
        "maxProperties",
    }
    require(set(schema) == schema_keys, "E_SCHEMA_FIELDS", repr(set(schema)))
    checks += 1
    require(
        schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
        and schema["type"] == "object"
        and schema["additionalProperties"] is False
        and schema["unevaluatedProperties"] is False
        and schema["minProperties"] == schema["maxProperties"] == 10
        and set(schema["required"]) == fixture_keys
        and set(schema["properties"]) == fixture_keys,
        "E_SCHEMA_CLOSED_WORLD",
        "root closure drift",
    )
    checks += 1
    metadata_consts = {
        "canonical_json_profile": "SORTED_KEYS_COMPACT_UTF8_NO_TRAILING_BYTES",
        "contains_private_or_seed_material": False,
        "date": DATE,
        "execution_mode": SYNTHETIC_MODE,
        "public_only": True,
        "schema": FIXTURE_SCHEMA,
    }
    for field, expected in metadata_consts.items():
        require(exact_equal(schema["properties"][field], {"const": expected}), "E_SCHEMA_METADATA_CONST", field)
    checks += 1
    require(
        exact_equal(
            schema["properties"]["separately_injected_synthetic_end_to_end_subject_binding_policy"],
            {"const": fixture["separately_injected_synthetic_end_to_end_subject_binding_policy"]},
        )
        and exact_equal(schema["properties"]["source_bindings"], {"const": fixture["source_bindings"]}),
        "E_SCHEMA_POLICY_BINDINGS",
        "policy/source const drift",
    )
    checks += 1
    for field in ("valid_cases", "expected_receipts"):
        value_schema = schema["properties"][field]
        require(
            value_schema["type"] == "array"
            and value_schema["minItems"] == 2
            and value_schema["maxItems"] == 2
            and value_schema["items"] is False
            and exact_equal(value_schema["prefixItems"], [{"const": value} for value in fixture[field]]),
            "E_SCHEMA_VECTOR_CONSTS",
            field,
        )
    checks += 1
    return fixture, predecessor_fixture, t06_fixture, t05_fixture, checks


def pack_receipt(
    policy_raw: bytes,
    request_raws: list[bytes],
    receipts: list[dict[str, Any]],
    real_predecessor_reviews: int,
    mode_tests: int,
    order_tests: int,
    mutation_counts: Mapping[str, int],
    source_checks: int,
    fixture_schema_checks_count: int,
) -> dict[str, Any]:
    total_negative = mode_tests + order_tests + sum(mutation_counts.values())
    result: dict[str, Any] = {
        "schema": PACK_RECEIPT_SCHEMA,
        "status": STATUS,
        "decision": DECISION,
        "date": DATE,
        "component_mode": SYNTHETIC_MODE,
        "component_state": COMPONENT_STATE,
        "positive_track_count": 2,
        "real_predecessor_review_count": real_predecessor_reviews,
        "public_mode_pre_observation_test_count": mode_tests,
        "predecessor_exactly_once_order_test_count": order_tests,
        "policy_json_negative_test_count": mutation_counts["policy_json"],
        "request_json_negative_test_count": mutation_counts["request_json"],
        "policy_closed_world_negative_test_count": mutation_counts["policy_closed_world"],
        "request_exact_field_negative_test_count": mutation_counts["request_exact_field"],
        "predecessor_receipt_binding_negative_test_count": mutation_counts["predecessor_receipt_binding"],
        "default_deny_negative_test_count": mutation_counts["default_deny"],
        "total_directed_negative_test_count": total_negative,
        "source_ast_guard_count": source_checks,
        "fixture_schema_guard_count": fixture_schema_checks_count,
        "fixture_expected_receipt_count": 2,
        "binding_profile_count": 2,
        "request_field_count": 8,
        "policy_match_dimension_count": 10,
        "isolated_lab_candidate_surface_component_total": 6,
        "isolated_lab_candidate_surface_components_implemented": 6,
        "local_threat_specifications_covered": 8,
        "production_ingestion_control_count": 14,
        "production_ingestion_controls_implemented": 0,
        "production_threat_specification_count": 20,
        "production_threat_specifications_runtime_exercised": 0,
        "runtime_prerequisite_count": 16,
        "runtime_prerequisites_satisfied": 0,
        "real_evidence_items_present": 0,
        "production_validated_evidence_items": 0,
        "runtime_authority": False,
        "provider_authority": False,
        "side_effects_unlocked": "NONE",
        "end_to_end_subject_binding_policy_sha256": sha256(policy_raw),
        "end_to_end_subject_binding_request_set_sha256": domain_sha256(
            "AB_END_TO_END_SUBJECT_BINDING_REQUEST_SET_V1",
            [sha256(raw) for raw in request_raws],
        ),
        "receipt_set_sha256": domain_sha256(
            "AB_END_TO_END_SUBJECT_BINDING_RECEIPT_SET_V1",
            receipts,
        ),
        "schema_raw_sha256": raw_sha256(SCHEMA_REL),
        "fixture_raw_sha256": raw_sha256(FIXTURE_REL),
        "source_raw_sha256": raw_sha256(SOURCE_REL),
        "predecessor_source_raw_sha256": raw_sha256(PREDECESSOR_SOURCE_REL),
        "predecessor_fixture_raw_sha256": raw_sha256(PREDECESSOR_FIXTURE_REL),
        "owner_decision_raw_sha256": raw_sha256(OWNER_DECISION_REL),
        "t07_semantic_specification_raw_sha256": raw_sha256(SEMANTIC_SPECIFICATION_REL),
        "content_sha256": "0" * 64,
    }
    require(set(result) == set(TSV_FIELDS), "E_PACK_RECEIPT_FIELDS", repr(set(result) ^ set(TSV_FIELDS)))
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
        rendered = str(value)
        require(
            "\t" not in rendered and "\n" not in rendered and "\r" not in rendered,
            "E_TSV_CONTROL",
            rendered,
        )
        return rendered

    return "".join(f"{field}\t{scalar(receipt[field])}\n" for field in TSV_FIELDS)


def evaluate() -> tuple[str, dict[str, int]]:
    source_checks = source_contract_checks()
    (
        fixture,
        predecessor_fixture,
        t06_fixture,
        t05_fixture,
        fixture_schema_count,
    ) = fixture_schema_checks()
    module = load_module()
    inputs, request_raws, receipts, predecessor_receipts, real_reviews = positive_checks(
        module,
        fixture,
        predecessor_fixture,
        t06_fixture,
        t05_fixture,
    )
    mode_tests = check_pre_observation_modes(module)
    order_tests = check_predecessor_exactly_once_order(module, inputs, predecessor_receipts[0])
    mutation_counts = directed_mutations(module, inputs, predecessor_receipts[0])
    receipt = pack_receipt(
        inputs[7],
        request_raws,
        receipts,
        real_reviews,
        mode_tests,
        order_tests,
        mutation_counts,
        source_checks,
        fixture_schema_count,
    )
    counts = dict(mutation_counts)
    counts["mode"] = mode_tests
    counts["order"] = order_tests
    counts["source"] = source_checks
    counts["fixture_schema"] = fixture_schema_count
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
            for key in (
                "policy_json",
                "request_json",
                "policy_closed_world",
                "request_exact_field",
                "predecessor_receipt_binding",
                "default_deny",
                "mode",
                "order",
                "source",
                "fixture_schema",
                "total",
            ):
                print(f"{key}_test_count\t{counts[key]}")
            print("real_positive_t07_review_count\t2")
            print(f"independent_receipt_oracle_field_count\t{len(RECEIPT_KEYS)}")
            print("source_ast_purity\tPASS")
            print("track_identity_source\tT07_PREDECESSOR_RECEIPT_ONLY")
        else:
            print(rendered, end="")
    except (
        CheckError,
        AssertionError,
        ValueError,
        TypeError,
        KeyError,
        OSError,
        SyntaxError,
        UnicodeError,
        RecursionError,
    ) as error:
        print("end-to-end subject binding isolated-lab pack check failed: " + str(error), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
