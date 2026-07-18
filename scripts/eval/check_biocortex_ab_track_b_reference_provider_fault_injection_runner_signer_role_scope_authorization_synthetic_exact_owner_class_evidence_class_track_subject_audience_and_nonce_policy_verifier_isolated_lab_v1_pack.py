#!/usr/bin/env python3
"""Independent checker for the isolated-lab signer role/scope verifier.

The checker owns its policy, request, receipt, JSON, source-AST, fixture, and
schema oracles.  It invokes the frozen T05 public reviewer for the two positive
vectors, then replaces that one public edge with a counted spy for directed T06
faults.  No expected constant or validation helper is imported from the subject.

No provider, network, credential, clock, signing, persistence, replay ledger,
fault-injection, evidence admission, output authority, or runtime registration
surface is exercised or granted.
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
    "signer_role_scope_authorization_synthetic_exact_owner_class_evidence_class_"
    "track_subject_audience_and_nonce_policy_verifier_isolated_lab_v1.py"
)
FIXTURE_REL = (
    "scripts/eval/fixtures/biocortex_ab_track_b_reference_provider_fault_injection_"
    "runner_signer_role_scope_authorization_synthetic_exact_owner_class_evidence_"
    "class_track_subject_audience_and_nonce_policy_verifier_isolated_lab_v1_pack_"
    "synthetic_v0.json"
)
SCHEMA_REL = (
    "docs/design/fixtures/biocortex-ab-track-b-reference-provider-fault-injection-"
    "runner-signer-role-scope-authorization-synthetic-exact-owner-class-evidence-"
    "class-track-subject-audience-and-nonce-policy-verifier-isolated-lab-v1."
    "schema.json"
)
PREDECESSOR_SOURCE_REL = (
    "scripts/eval/biocortex_ab_track_b_reference_provider_fault_injection_runner_"
    "bootstrap_trust_authentication_synthetic_trust_chain_exact_key_version_"
    "declared_role_and_revocation_verifier_isolated_lab_v1.py"
)
PREDECESSOR_FIXTURE_REL = (
    "scripts/eval/fixtures/biocortex_ab_track_b_reference_provider_fault_injection_"
    "runner_bootstrap_trust_authentication_synthetic_trust_chain_exact_key_version_"
    "declared_role_and_revocation_verifier_isolated_lab_v1_pack_synthetic_v0.json"
)
OWNER_DECISION_REL = (
    "scripts/eval/fixtures/biocortex_ab_track_b_reference_provider_fault_injection_"
    "runner_signer_role_scope_authorization_isolated_lab_implementation_authority_"
    "and_resource_binding_decision_v1_pack_owner_decision_v0.json"
)

DATE = "2026-07-18"
SYNTHETIC_MODE = "SYNTHETIC_KAT"
PRODUCTION_MODE = "PRODUCTION"
POLICY_SCHEMA = (
    "agent_bridge.biocortex_ab_track_b_reference_provider_fault_injection_"
    "runner.signer_role_scope_authorization_synthetic_policy_isolated_lab_kat.v1"
)
REQUEST_SCHEMA = (
    "agent_bridge.biocortex_ab_track_b_reference_provider_fault_injection_"
    "runner.signer_role_scope_authorization_detached_request_isolated_lab_kat.v1"
)
RECEIPT_SCHEMA = (
    "agent_bridge.biocortex_ab_track_b_reference_provider_fault_injection_"
    "runner.signer_role_scope_authorization_synthetic_exact_owner_class_"
    "evidence_class_track_subject_audience_and_nonce_policy_verifier_"
    "isolated_lab_v1.receipt.v0"
)
FIXTURE_SCHEMA = (
    "agent_bridge.biocortex_ab_track_b_reference_provider_fault_injection_runner."
    "signer_role_scope_authorization_synthetic_exact_owner_class_evidence_class_"
    "track_subject_audience_and_nonce_policy_verifier_isolated_lab_v1_pack."
    "synthetic.v0"
)
PACK_RECEIPT_SCHEMA = (
    "agent_bridge.biocortex_ab_track_b_reference_provider_fault_injection_runner."
    "signer_role_scope_authorization_synthetic_exact_owner_class_evidence_class_"
    "track_subject_audience_and_nonce_policy_verifier_isolated_lab_v1_pack."
    "receipt.v0"
)
STATUS = (
    "REFERENCE_PROVIDER_MANAGED_AND_SELF_HOSTED_FAULT_INJECTION_RUNNER_V1_"
    "SIGNER_ROLE_SCOPE_AUTHORIZATION_SYNTHETIC_EXACT_OWNER_CLASS_EVIDENCE_"
    "CLASS_TRACK_SUBJECT_AUDIENCE_AND_NONCE_POLICY_VERIFIED_ISOLATED_LAB_"
    "COMPONENT_ONLY_NO_PRODUCTION_AUTHORITY"
)
DECISION = (
    "T06_SYNTHETIC_EXACT_SIGNER_ROLE_SCOPE_COMPONENT_CONFORMANT_"
    "PRODUCTION_PATH_FAIL_CLOSED"
)
COMPONENT_STATE = (
    "AUTHORIZED_SYNTHETIC_KAT_SIGNER_FOR_EXACT_FROZEN_ROLE_SCOPE_COMPONENT_ONLY"
)
RECEIPT_DOMAIN = (
    "AB_TRACK_B_SIGNER_ROLE_SCOPE_AUTHORIZATION_ISOLATED_LAB_KAT_RECEIPT_V1"
)
PACK_RECEIPT_DOMAIN = (
    "AB_TRACK_B_SIGNER_ROLE_SCOPE_AUTHORIZATION_ISOLATED_LAB_PACK_RECEIPT_V1"
)
POLICY_SCHEMA_PROFILE = "EXACT_ALL_FIELDS_ASCII_BYTE_EQUAL"
OWNER_CLASS = "SYNTHETIC_KAT_EVIDENCE_REVIEW_OWNER_CLASS_V1"
EVIDENCE_CLASS = "SYNTHETIC_PRODUCTION_EVIDENCE_ENVELOPE_KAT"
DECLARED_ROLE_CLASS = "SYNTHETIC_EVIDENCE_ENVELOPE_SIGNER_KAT_ONLY"
TRUST_POLICY_SHA256 = (
    "882f37d4862ed83bb8d91b218dec8c9b40861b35e3785620f873d9250f9d51b0"
)
POLICY_SHA256 = (
    "7d7fcc3174560c0d121aff8ce69e02c5facbcbe799f0ad2f523ecc108f6cb1c9"
)
PREDECESSOR_SOURCE_SHA256 = (
    "f483200c34ab570b3da8f45d6e4d0adb8e382f5d6fa815112a2c0b62c0431341"
)
PREDECESSOR_FIXTURE_SHA256 = (
    "31959b02f20278d126be3a7e18e44e220b47cffb41804f69e3ace5c93277923e"
)
OWNER_DECISION_SHA256 = (
    "ba9bf671ec4985c14089e6e68b0bda5a09c0b4b09df1582ba6b8305f5fee4ee6"
)
AUTHORITY_SOURCE_COMMIT = "4a298c5f5a8dce6c7482b46fc6b416246fb55547"
AUTHORITY_INTEGRATION_COMMIT = "9edc70a870023ebc8e081f61100577345d3c2850"
AUTHORITY_FULL_STDOUT_SHA256 = (
    "f7ebac3d39eeba74d4c8d1cd908c195b8f95340e20e4ca0a126605384d0f01ee"
)
SOURCE_RAW_SHA256 = (
    "438a0edbb9deb7d61c7bd8462b24d102123df0b6b7be46109bcf9d97ee8cade0"
)
FIXTURE_RAW_SHA256 = (
    "cb5e0950cd6ec4835f6fbbb64e80ee656ba825ec92910b4be1032761f6238ff9"
)
SCHEMA_RAW_SHA256 = (
    "8c659f8bed05e665c0e663649ec892bb3c82ff17e6ad396c79093047af7de7ca"
)

SCOPE_FIELDS = (
    "owner_class",
    "evidence_class",
    "track_id",
    "subject",
    "audience",
    "nonce_scope",
)
FORBIDDEN_REQUEST_SIGNER_FIELDS = (
    "declared_role_class",
    "predecessor_receipt_content_sha256",
    "signer_key_id",
    "signer_key_version",
    "signer_role",
)
POLICY_KEYS = (
    "default_effect",
    "deny_on_multiple_matches",
    "deny_on_zero_matches",
    "grants",
    "matching_profile",
    "schema",
    "schema_version",
)
GRANT_KEYS = (
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
REQUEST_KEYS = (
    "audience",
    "evidence_class",
    "nonce_scope",
    "owner_class",
    "schema",
    "schema_version",
    "subject",
    "track_id",
)

PROFILES: tuple[dict[str, str], ...] = (
    {
        "track_id": "MANAGED_SPANNER_CLOUD_KMS",
        "grant_id": "KAT_MANAGED_SIGNER_ROLE_SCOPE_GRANT_V1",
        "authorization_policy_revision": (
            "KAT_MANAGED_SIGNER_ROLE_SCOPE_AUTHORIZATION_POLICY_REVISION_1"
        ),
        "frame_sha256": (
            "e298865e753a96d58b6c23d49b58cb2c4b512a519a65666d31170325bd34d295"
        ),
        "predecessor_receipt_content_sha256": (
            "46a923e510a29ed144d0de092b8346585a4a857e009d042bb68da1003f681803"
        ),
        "revocation_snapshot_revision": (
            "KAT_MANAGED_REVOCATION_SNAPSHOT_REVISION_1"
        ),
        "signer_key_id": "KAT_MANAGED_EVIDENCE_ENVELOPE_SIGNER_V2",
        "signer_key_version": "KAT_MANAGED_LEAF_KEY_VERSION_2",
        "signer_role": "KAT_MANAGED_EVIDENCE_ENVELOPE_SIGNER",
        "subject": "KAT_MANAGED_VALID_MINIMAL_FRAME_SUBJECT_V1",
        "audience": (
            "AB_TRACK_B_MANAGED_FAULT_INJECTION_RUNNER_ISOLATED_LAB_"
            "AUTHORIZATION_KAT_V1"
        ),
        "nonce_scope": "KAT_MANAGED_SIGNER_ROLE_SCOPE_NONCE_V1_0001",
        "vector_set_id": (
            "KAT_MANAGED_BOOTSTRAP_TRUST_PUBLIC_ONLY_PRECOMPUTED_VECTOR_SET_V1"
        ),
        "case_id": "VALID_MANAGED_SIGNER_ROLE_SCOPE_AUTHORIZATION_V1",
        "predecessor_case_id": "VALID_MANAGED_BOOTSTRAP_TRUST_AUTHENTICATION_V1",
    },
    {
        "track_id": "SELF_HOSTED_ETCD_OPENBAO",
        "grant_id": "KAT_SELF_HOSTED_SIGNER_ROLE_SCOPE_GRANT_V1",
        "authorization_policy_revision": (
            "KAT_SELF_HOSTED_SIGNER_ROLE_SCOPE_AUTHORIZATION_POLICY_REVISION_1"
        ),
        "frame_sha256": (
            "da147c9e4bcb4ac54e98209f5ea2970322726d3d851ac415903e1dbe311da69e"
        ),
        "predecessor_receipt_content_sha256": (
            "72d1e5c86fc99027427c78f1b2792d51e02461a6cc9b120f1d8baf877472e1c1"
        ),
        "revocation_snapshot_revision": (
            "KAT_SELF_HOSTED_REVOCATION_SNAPSHOT_REVISION_1"
        ),
        "signer_key_id": "KAT_SELF_HOSTED_EVIDENCE_ENVELOPE_SIGNER_V2",
        "signer_key_version": "KAT_SELF_HOSTED_LEAF_KEY_VERSION_2",
        "signer_role": "KAT_SELF_HOSTED_EVIDENCE_ENVELOPE_SIGNER",
        "subject": "KAT_SELF_HOSTED_VALID_MINIMAL_FRAME_SUBJECT_V1",
        "audience": (
            "AB_TRACK_B_SELF_HOSTED_FAULT_INJECTION_RUNNER_ISOLATED_LAB_"
            "AUTHORIZATION_KAT_V1"
        ),
        "nonce_scope": "KAT_SELF_HOSTED_SIGNER_ROLE_SCOPE_NONCE_V1_0001",
        "vector_set_id": (
            "KAT_SELF_HOSTED_BOOTSTRAP_TRUST_PUBLIC_ONLY_PRECOMPUTED_VECTOR_SET_V1"
        ),
        "case_id": "VALID_SELF_HOSTED_SIGNER_ROLE_SCOPE_AUTHORIZATION_V1",
        "predecessor_case_id": (
            "VALID_SELF_HOSTED_BOOTSTRAP_TRUST_AUTHENTICATION_V1"
        ),
    },
)

TSV_FIELDS = (
    "schema",
    "status",
    "decision",
    "date",
    "mode",
    "component_state",
    "positive_track_count",
    "real_predecessor_review_count",
    "public_mode_pre_observation_test_count",
    "predecessor_exactly_once_order_test_count",
    "policy_json_negative_test_count",
    "request_json_negative_test_count",
    "policy_closed_world_negative_test_count",
    "request_scope_negative_test_count",
    "receipt_identity_negative_test_count",
    "default_deny_negative_test_count",
    "total_directed_negative_test_count",
    "source_ast_guard_count",
    "fixture_schema_guard_count",
    "fixture_expected_receipt_count",
    "authorization_grant_count",
    "request_scope_dimension_count",
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
    "signer_authorization_policy_sha256",
    "authorization_request_set_sha256",
    "receipt_set_sha256",
    "trust_policy_sha256",
    "schema_raw_sha256",
    "fixture_raw_sha256",
    "source_raw_sha256",
    "predecessor_source_raw_sha256",
    "predecessor_fixture_raw_sha256",
    "owner_decision_raw_sha256",
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
        return (
            set(left) == set(right)
            and all(exact_equal(left[key], right[key]) for key in left)
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
    require(
        resolved == ROOT or ROOT in resolved.parents,
        "E_PATH_ESCAPE",
        relative,
    )
    require(
        candidate.is_file() and not candidate.is_symlink(),
        "E_PATH_FILE",
        relative,
    )
    return candidate


def raw_sha256(relative: str) -> str:
    return sha256(checked_path(relative).read_bytes())


def _artifact_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        require(
            type(key) is str and key not in result,
            "E_ARTIFACT_DUPLICATE_KEY",
            repr(key),
        )
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


def grant_for(profile: Mapping[str, str]) -> dict[str, Any]:
    return {
        "audience": profile["audience"],
        "authorization_policy_revision": profile["authorization_policy_revision"],
        "declared_role_class": DECLARED_ROLE_CLASS,
        "effect": "ALLOW",
        "evidence_class": EVIDENCE_CLASS,
        "frame_sha256": profile["frame_sha256"],
        "grant_id": profile["grant_id"],
        "nonce_scope": profile["nonce_scope"],
        "owner_class": OWNER_CLASS,
        "predecessor_receipt_content_sha256": (
            profile["predecessor_receipt_content_sha256"]
        ),
        "revocation_snapshot_revision": profile["revocation_snapshot_revision"],
        "signer_key_id": profile["signer_key_id"],
        "signer_key_version": profile["signer_key_version"],
        "signer_role": profile["signer_role"],
        "subject": profile["subject"],
        "track_id": profile["track_id"],
        "trust_policy_sha256": TRUST_POLICY_SHA256,
        "vector_set_id": profile["vector_set_id"],
    }


def expected_policy() -> dict[str, Any]:
    return {
        "default_effect": "DENY",
        "deny_on_multiple_matches": True,
        "deny_on_zero_matches": True,
        "grants": [grant_for(profile) for profile in PROFILES],
        "matching_profile": POLICY_SCHEMA_PROFILE,
        "schema": POLICY_SCHEMA,
        "schema_version": 1,
    }


def expected_request(profile: Mapping[str, str]) -> dict[str, Any]:
    return {
        "audience": profile["audience"],
        "evidence_class": EVIDENCE_CLASS,
        "nonce_scope": profile["nonce_scope"],
        "owner_class": OWNER_CLASS,
        "schema": REQUEST_SCHEMA,
        "schema_version": 1,
        "subject": profile["subject"],
        "track_id": profile["track_id"],
    }


def expected_valid_case(profile: Mapping[str, str]) -> dict[str, Any]:
    return {
        "case_id": profile["case_id"],
        "detached_authorization_request": expected_request(profile),
        "predecessor_case_id": profile["predecessor_case_id"],
        "track_id": profile["track_id"],
    }


def expected_receipt(
    profile: Mapping[str, str],
    frame_raw: bytes,
    bundle_raw: bytes,
    policy_raw: bytes,
    request_raw: bytes,
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "action_or_resource_capability_authorized": False,
        "audience": profile["audience"],
        "audience_identity_authenticated": False,
        "authorization_decision": "ALLOW",
        "authorization_grant_count": 2,
        "authorization_match_count": 1,
        "authorization_policy_is_production_policy": False,
        "authorization_policy_revision": profile["authorization_policy_revision"],
        "authorization_policy_separately_injected": True,
        "authorization_policy_sha256": sha256(policy_raw),
        "authorization_request_detached": True,
        "authorization_request_observed_after_policy": True,
        "authorization_request_sha256": sha256(request_raw),
        "authorization_request_signer_field_count": 0,
        "bootstrap_trust_authentication_implemented": True,
        "caller_supplied_predecessor_receipt_accepted": False,
        "component_state": COMPONENT_STATE,
        "condition_output_authorized": False,
        "content_sha256": "0" * 64,
        "declared_role_class": DECLARED_ROLE_CLASS,
        "default_effect": "DENY",
        "deny_on_multiple_matches": True,
        "deny_on_zero_matches": True,
        "detached_authentication_bundle_sha256": sha256(bundle_raw),
        "downstream_gate_count": 4,
        "downstream_gates_authorized": 0,
        "durable_replay_cas_implemented": False,
        "evidence_acceptance_authorized": False,
        "evidence_class": EVIDENCE_CLASS,
        "execution_mode": SYNTHETIC_MODE,
        "fault_injection_authorized": False,
        "frame_sha256": sha256(frame_raw),
        "grant_id": profile["grant_id"],
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
        "matching_profile": POLICY_SCHEMA_PROFILE,
        "nonce_fixed_public_kat_equality_only": True,
        "nonce_freshness_proved": False,
        "nonce_generation_authorized": False,
        "nonce_replay_protection_proved": False,
        "nonce_scope": profile["nonce_scope"],
        "nonce_single_use_proved": False,
        "output_or_claim_authorized": False,
        "owner_class": OWNER_CLASS,
        "owner_class_is_authenticated_owner_identity": False,
        "predecessor_receipt_content_sha256": (
            profile["predecessor_receipt_content_sha256"]
        ),
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
        "request_scope_dimension_count": 6,
        "request_scope_fields": list(SCOPE_FIELDS),
        "revocation_snapshot_revision": profile["revocation_snapshot_revision"],
        "runtime_authority": False,
        "runtime_prerequisite_count": 16,
        "runtime_prerequisites_satisfied": 0,
        "schema": RECEIPT_SCHEMA,
        "schema_version": 1,
        "scope_label_truth_proved": False,
        "separately_injected_trust_policy": True,
        "side_effects_unlocked": "NONE",
        "signer_identity_source": "T05_PREDECESSOR_RECEIPT_ONLY",
        "signer_key_id": profile["signer_key_id"],
        "signer_key_version": profile["signer_key_version"],
        "signer_role": profile["signer_role"],
        "signer_role_scope_authorization_isolated_lab_component_implemented": True,
        "status": STATUS,
        "subject": profile["subject"],
        "subject_label_truth_proved": False,
        "synthetic_fixture": True,
        "t07_track_profile_binding_implemented": False,
        "t08_end_to_end_subject_binding_implemented": False,
        "t09_content_identity_and_quarantine_custody_implemented": False,
        "target_production_failure_code": (
            "E_PRODUCTION_SIGNER_AUTHORIZATION_FAILED"
        ),
        "target_production_control": "SIGNER_ROLE_SCOPE_AUTHORIZATION",
        "track_id": profile["track_id"],
        "track_is_provider_profile_currentness": False,
        "track_subject_binding_implemented": False,
        "trust_policy_sha256": TRUST_POLICY_SHA256,
        "upstream_decision_record_t09_replay_cas_implemented": False,
        "vector_set_id": profile["vector_set_id"],
        "wildcard_prefix_hierarchy_or_inheritance_authorization_implemented": False,
    }
    unsigned = dict(result)
    del unsigned["content_sha256"]
    result["content_sha256"] = domain_sha256(RECEIPT_DOMAIN, unsigned)
    return result


def load_module() -> ModuleType:
    path = checked_path(SOURCE_REL)
    module_name = "_signer_role_scope_authorization_subject_under_review"
    spec = importlib.util.spec_from_file_location(module_name, path)
    require(
        spec is not None and spec.loader is not None,
        "E_SOURCE_IMPORT_SPEC",
        SOURCE_REL,
    )
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
    """A str subclass whose comparisons must never execute."""

    events: list[str] = []

    def __eq__(self, other: object) -> bool:
        type(self).events.append("eq")
        raise AssertionError("hostile str subclass compared")

    def __ne__(self, other: object) -> bool:
        type(self).events.append("ne")
        raise AssertionError("hostile str subclass compared")

    __hash__ = str.__hash__


def expect_rejection(
    module: ModuleType,
    frame: Any,
    bundle: Any,
    trust_policy: Any,
    authorization_policy: Any,
    request: Any,
    mode: Any,
    expected_code: str,
    label: str,
    expected_detail_code: str | None = None,
) -> None:
    try:
        module.review_signer_role_scope_authorization(
            frame,
            bundle,
            trust_policy,
            authorization_policy,
            request,
            mode,
        )
    except module.SignerAuthorizationReviewError as error:
        require(
            error.code == expected_code,
            "E_REJECTION_CODE",
            f"{label}: {error.code}",
        )
        if expected_detail_code is not None:
            require(
                error.detail_code == expected_detail_code,
                "E_REJECTION_DETAIL_CODE",
                f"{label}: {error.detail_code}",
            )
    else:
        raise CheckError(f"E_MUTATION_ACCEPTED: {label}")


def positive_checks(
    module: ModuleType,
    fixture: Mapping[str, Any],
    predecessor_fixture: Mapping[str, Any],
) -> tuple[
    list[bytes],
    list[bytes],
    bytes,
    bytes,
    list[bytes],
    list[dict[str, Any]],
    list[dict[str, Any]],
    int,
]:
    policy = expected_policy()
    policy_raw = canonical_bytes(policy)
    require(sha256(policy_raw) == POLICY_SHA256, "E_POLICY_HASH_ORACLE", sha256(policy_raw))
    require(
        exact_equal(module.known_answer_authorization_policy(), policy)
        and module.known_answer_authorization_policy_bytes() == policy_raw,
        "E_POLICY_HELPER_ORACLE",
        "subject known-answer policy differs",
    )

    predecessor_cases = {
        case["case_id"]: case for case in predecessor_fixture["valid_cases"]
    }
    predecessor_receipts_by_track = {
        receipt["track_id"]: receipt
        for receipt in predecessor_fixture["expected_receipts"]
    }
    frames: list[bytes] = []
    bundles: list[bytes] = []
    requests: list[bytes] = []
    receipts: list[dict[str, Any]] = []
    predecessor_receipts: list[dict[str, Any]] = []
    trust_policy_raw = canonical_bytes(
        predecessor_fixture["separately_injected_synthetic_trust_policy"]
    )
    require(
        sha256(trust_policy_raw) == TRUST_POLICY_SHA256,
        "E_TRUST_POLICY_HASH_ORACLE",
        sha256(trust_policy_raw),
    )

    real_reviewer = module.predecessor.review_bootstrap_trust_authentication
    real_calls: list[tuple[Any, ...]] = []

    def counted_real_reviewer(*args: Any, **kwargs: Any) -> Any:
        real_calls.append(args)
        return real_reviewer(*args, **kwargs)

    module.predecessor.review_bootstrap_trust_authentication = counted_real_reviewer
    try:
        for index, profile in enumerate(PROFILES):
            predecessor_case = predecessor_cases[profile["predecessor_case_id"]]
            frame_raw = predecessor_case["frame_utf8"].encode("utf-8")
            bundle_raw = canonical_bytes(
                predecessor_case["detached_authentication_bundle"]
            )
            request = expected_request(profile)
            request_raw = canonical_bytes(request)
            predecessor_receipt = predecessor_receipts_by_track[profile["track_id"]]

            require(
                sha256(frame_raw) == profile["frame_sha256"],
                "E_FRAME_HASH_ORACLE",
                profile["track_id"],
            )
            require(
                predecessor_case["track_id"] == profile["track_id"]
                and predecessor_case["detached_authentication_bundle"]["track_id"]
                == profile["track_id"],
                "E_PREDECESSOR_CASE_TRACK",
                profile["track_id"],
            )
            require(
                predecessor_receipt["content_sha256"]
                == profile["predecessor_receipt_content_sha256"],
                "E_PREDECESSOR_RECEIPT_HASH_ORACLE",
                profile["track_id"],
            )
            require(
                predecessor_receipt["active_leaf_key_id"]
                == profile["signer_key_id"]
                and predecessor_receipt["active_leaf_key_version"]
                == profile["signer_key_version"]
                and predecessor_receipt["mapped_policy_leaf_role"]
                == profile["signer_role"]
                and predecessor_receipt["track_leaf_role"]
                == profile["signer_role"]
                and predecessor_receipt["declared_role"] == DECLARED_ROLE_CLASS,
                "E_PREDECESSOR_IDENTITY_ORACLE",
                profile["track_id"],
            )
            require(
                exact_equal(
                    module.known_answer_authorization_request(profile["track_id"]),
                    request,
                )
                and module.known_answer_authorization_request_bytes(
                    profile["track_id"]
                )
                == request_raw,
                "E_REQUEST_HELPER_ORACLE",
                profile["track_id"],
            )

            before = len(real_calls)
            subject_receipt = module.review_signer_role_scope_authorization(
                frame_raw,
                bundle_raw,
                trust_policy_raw,
                policy_raw,
                request_raw,
                SYNTHETIC_MODE,
            )
            require(
                len(real_calls) == before + 1,
                "E_POSITIVE_PREDECESSOR_CALL_COUNT",
                profile["track_id"],
            )
            oracle_receipt = expected_receipt(
                profile,
                frame_raw,
                bundle_raw,
                policy_raw,
                request_raw,
            )
            require(
                exact_equal(subject_receipt, oracle_receipt),
                "E_POSITIVE_RECEIPT",
                profile["track_id"],
            )
            require(
                exact_equal(fixture["expected_receipts"][index], oracle_receipt),
                "E_FIXTURE_EXPECTED_RECEIPT",
                profile["track_id"],
            )

            frames.append(frame_raw)
            bundles.append(bundle_raw)
            requests.append(request_raw)
            receipts.append(oracle_receipt)
            predecessor_receipts.append(copy.deepcopy(predecessor_receipt))
    finally:
        module.predecessor.review_bootstrap_trust_authentication = real_reviewer

    require(
        len(real_calls) == 2,
        "E_REAL_PREDECESSOR_TOTAL",
        str(len(real_calls)),
    )
    return (
        frames,
        bundles,
        trust_policy_raw,
        policy_raw,
        requests,
        receipts,
        predecessor_receipts,
        len(real_calls),
    )


def check_pre_observation_modes(module: ModuleType) -> int:
    original = module.predecessor.review_bootstrap_trust_authentication
    predecessor_calls: list[tuple[Any, ...]] = []

    def forbidden_predecessor(*args: Any, **kwargs: Any) -> Any:
        predecessor_calls.append(args)
        raise AssertionError("predecessor observed before mode acceptance")

    module.predecessor.review_bootstrap_trust_authentication = forbidden_predecessor
    modes: tuple[tuple[str, Any, str], ...] = (
        (
            "production",
            PRODUCTION_MODE,
            "E_SIGNER_AUTHORIZATION_PRODUCTION_MODE_NOT_AUTHORIZED",
        ),
        ("unknown_string", "SYNTHETIC", "E_SIGNER_AUTHORIZATION_MODE_UNKNOWN"),
        ("unknown_integer", 7, "E_SIGNER_AUTHORIZATION_MODE_UNKNOWN"),
        (
            "str_subclass",
            HostileStringSubclass(SYNTHETIC_MODE),
            "E_SIGNER_AUTHORIZATION_MODE_UNKNOWN",
        ),
    )
    try:
        for label, mode, code in modes:
            HostileStringSubclass.events.clear()
            bombs = tuple(
                ObservationBomb(f"{label}-{name}")
                for name in ("frame", "bundle", "trust", "policy", "request")
            )
            expect_rejection(
                module,
                bombs[0],
                bombs[1],
                bombs[2],
                bombs[3],
                bombs[4],
                mode,
                code,
                label,
            )
            require(
                all(bomb.event_count == 0 for bomb in bombs),
                "E_MODE_OBSERVED_INPUT",
                label,
            )
            require(
                not HostileStringSubclass.events,
                "E_MODE_COMPARED_STR_SUBCLASS",
                label,
            )
    finally:
        module.predecessor.review_bootstrap_trust_authentication = original
    require(
        not predecessor_calls,
        "E_MODE_PREDECESSOR_CALLED",
        str(len(predecessor_calls)),
    )
    return len(modes)


def check_predecessor_exactly_once_order(
    module: ModuleType,
    frame: bytes,
    bundle: bytes,
    trust_policy: bytes,
    policy: bytes,
    request: bytes,
    predecessor_receipt: Mapping[str, Any],
) -> int:
    original_reviewer = module.predecessor.review_bootstrap_trust_authentication
    original_decode = module._decode_closed_json
    events: list[str] = []
    reviewer_calls = 0
    behavior = "success"

    def reviewer_spy(*args: Any, **kwargs: Any) -> dict[str, Any]:
        nonlocal reviewer_calls
        reviewer_calls += 1
        events.append("t05")
        if behavior == "reject":
            raise module.predecessor.BootstrapTrustReviewError(
                "E_SPY_T05_REJECTED",
                "injected predecessor rejection",
            )
        return copy.deepcopy(predecessor_receipt)

    def decode_spy(raw: Any, *, limit: int, label: str) -> dict[str, Any]:
        events.append(f"decode:{label}")
        return original_decode(raw, limit=limit, label=label)

    module.predecessor.review_bootstrap_trust_authentication = reviewer_spy
    module._decode_closed_json = decode_spy
    tests = 0
    try:
        behavior = "reject"
        events.clear()
        before = reviewer_calls
        bombs = tuple(
            ObservationBomb(f"t05-reject-{name}")
            for name in ("frame", "bundle", "trust", "policy", "request")
        )
        expect_rejection(
            module,
            bombs[0],
            bombs[1],
            bombs[2],
            bombs[3],
            bombs[4],
            SYNTHETIC_MODE,
            "E_PREDECESSOR_AUTHENTICATION_REJECTED",
            "t05_rejection_precedes_policy_request",
            "E_SPY_T05_REJECTED",
        )
        require(
            reviewer_calls == before + 1 and events == ["t05"],
            "E_T05_REJECTION_ORDER",
            repr(events),
        )
        require(
            all(bomb.event_count == 0 for bomb in bombs),
            "E_T05_REJECTION_OBSERVATION",
            "input observed by caller",
        )
        tests += 1

        behavior = "success"
        events.clear()
        before = reviewer_calls
        request_bomb = ObservationBomb("policy-reject-request")
        expect_rejection(
            module,
            frame,
            bundle,
            trust_policy,
            b"{}",
            request_bomb,
            SYNTHETIC_MODE,
            "E_SIGNER_AUTHORIZATION_POLICY_REJECTED",
            "policy_rejection_precedes_request",
            "E_AUTHORIZATION_POLICY_FIELDS",
        )
        require(
            reviewer_calls == before + 1
            and events == ["t05", "decode:AUTHORIZATION_POLICY"]
            and request_bomb.event_count == 0,
            "E_POLICY_REQUEST_ORDER",
            repr(events),
        )
        tests += 1

        events.clear()
        before = reviewer_calls
        expect_rejection(
            module,
            frame,
            bundle,
            trust_policy,
            policy,
            b"{}",
            SYNTHETIC_MODE,
            "E_SIGNER_ROLE_SCOPE_AUTHORIZATION_FAILED",
            "request_after_policy",
            "E_AUTHORIZATION_REQUEST_FIELDS",
        )
        require(
            reviewer_calls == before + 1
            and events
            == [
                "t05",
                "decode:AUTHORIZATION_POLICY",
                "decode:AUTHORIZATION_REQUEST",
            ],
            "E_REQUEST_ORDER",
            repr(events),
        )
        tests += 1

        events.clear()
        before = reviewer_calls
        receipt = module.review_signer_role_scope_authorization(
            frame,
            bundle,
            trust_policy,
            policy,
            request,
            SYNTHETIC_MODE,
        )
        require(
            reviewer_calls == before + 1
            and events
            == [
                "t05",
                "decode:AUTHORIZATION_POLICY",
                "decode:AUTHORIZATION_REQUEST",
            ]
            and receipt["predecessor_review_count"] == 1,
            "E_SUCCESS_ORDER",
            repr(events),
        )
        tests += 1
    finally:
        module._decode_closed_json = original_decode
        module.predecessor.review_bootstrap_trust_authentication = original_reviewer
    return tests


def _mutated(
    value: Mapping[str, Any],
    operation: Callable[[dict[str, Any]], None],
) -> bytes:
    result = copy.deepcopy(value)
    operation(result)
    return canonical_bytes(result)


def _noncanonical_bytes(value: Mapping[str, Any]) -> bytes:
    reversed_items = list(value.items())[::-1]
    return json.dumps(
        dict(reversed_items),
        sort_keys=False,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
    ).encode("utf-8")


def directed_mutations(
    module: ModuleType,
    frame: bytes,
    bundle: bytes,
    trust_policy: bytes,
    policy_raw: bytes,
    request_raw: bytes,
    predecessor_receipt: Mapping[str, Any],
) -> dict[str, int]:
    policy = expected_policy()
    request = expected_request(PROFILES[0])
    original_reviewer = module.predecessor.review_bootstrap_trust_authentication
    reviewer_calls = 0
    current_receipt: Mapping[str, Any] = predecessor_receipt

    def reviewer_spy(*args: Any, **kwargs: Any) -> dict[str, Any]:
        nonlocal reviewer_calls
        reviewer_calls += 1
        return copy.deepcopy(current_receipt)

    module.predecessor.review_bootstrap_trust_authentication = reviewer_spy
    counts = {
        "policy_json": 0,
        "request_json": 0,
        "policy_closed_world": 0,
        "request_scope": 0,
        "receipt_identity": 0,
        "default_deny": 0,
    }

    def reject(
        category: str,
        name: str,
        *,
        policy_bytes: Any = policy_raw,
        request_bytes: Any = request_raw,
        code: str,
        detail: str | None = None,
    ) -> None:
        before = reviewer_calls
        expect_rejection(
            module,
            frame,
            bundle,
            trust_policy,
            policy_bytes,
            request_bytes,
            SYNTHETIC_MODE,
            code,
            f"{category}:{name}",
            detail,
        )
        require(
            reviewer_calls == before + 1,
            "E_MUTATION_PREDECESSOR_CALL_COUNT",
            f"{category}:{name}:{reviewer_calls - before}",
        )
        counts[category] += 1

    try:
        policy_json_cases: list[tuple[str, Any, str]] = [
            ("type_bytearray", bytearray(policy_raw), "E_AUTHORIZATION_POLICY_TYPE"),
            ("empty", b"", "E_AUTHORIZATION_POLICY_SIZE"),
            ("oversize", b"x" * 65_537, "E_AUTHORIZATION_POLICY_SIZE"),
            ("invalid_utf8", b"\xff", "E_AUTHORIZATION_POLICY_UTF8"),
            ("bom", b"\xef\xbb\xbf" + policy_raw, "E_AUTHORIZATION_POLICY_JSON"),
            ("trailing_newline", policy_raw + b"\n", "E_AUTHORIZATION_POLICY_TRAILING"),
            ("second_value", policy_raw + b"{}", "E_AUTHORIZATION_POLICY_TRAILING"),
            (
                "duplicate_key",
                b'{"default_effect":"DENY",' + policy_raw[1:],
                "E_JSON_DUPLICATE_KEY",
            ),
            (
                "float",
                policy_raw.replace(b'"schema_version":1', b'"schema_version":1.0'),
                "E_JSON_FLOAT",
            ),
            (
                "nonfinite",
                policy_raw.replace(b'"schema_version":1', b'"schema_version":NaN'),
                "E_JSON_NONFINITE",
            ),
            (
                "int_range",
                policy_raw.replace(
                    b'"schema_version":1',
                    b'"schema_version":9223372036854775808',
                ),
                "E_JSON_INT_RANGE",
            ),
            ("root_array", b"[]", "E_AUTHORIZATION_POLICY_ROOT"),
            ("leading_space", b" " + policy_raw, "E_AUTHORIZATION_POLICY_JSON"),
            (
                "noncanonical_order",
                _noncanonical_bytes(policy),
                "E_AUTHORIZATION_POLICY_NONCANONICAL",
            ),
            (
                "unicode_scalar",
                b'{"probe":"\\ud800",' + policy_raw[1:],
                "E_AUTHORIZATION_POLICY_UNICODE_SCALAR",
            ),
        ]
        nested: Any = "leaf"
        for _ in range(33):
            nested = {"n": nested}
        policy_json_cases.extend(
            [
                (
                    "depth",
                    canonical_bytes({"probe": nested}),
                    "E_JSON_DEPTH",
                ),
                (
                    "object_members",
                    canonical_bytes({f"k{i:03d}": i for i in range(257)}),
                    "E_JSON_OBJECT_MEMBERS",
                ),
                (
                    "array_items",
                    canonical_bytes({"probe": list(range(65))}),
                    "E_JSON_ARRAY_ITEMS",
                ),
                (
                    "nodes",
                    canonical_bytes(
                        {
                            "probe": [
                                {f"k{j:02d}": j for j in range(64)}
                                for _ in range(64)
                            ]
                        }
                    ),
                    "E_JSON_NODES",
                ),
            ]
        )
        for name, raw, detail in policy_json_cases:
            reject(
                "policy_json",
                name,
                policy_bytes=raw,
                code="E_SIGNER_AUTHORIZATION_POLICY_REJECTED",
                detail=detail,
            )

        request_json_cases: list[tuple[str, Any, str]] = [
            ("type_bytearray", bytearray(request_raw), "E_AUTHORIZATION_REQUEST_TYPE"),
            ("empty", b"", "E_AUTHORIZATION_REQUEST_SIZE"),
            ("oversize", b"x" * 16_385, "E_AUTHORIZATION_REQUEST_SIZE"),
            ("invalid_utf8", b"\xff", "E_AUTHORIZATION_REQUEST_UTF8"),
            ("bom", b"\xef\xbb\xbf" + request_raw, "E_AUTHORIZATION_REQUEST_JSON"),
            ("trailing_newline", request_raw + b"\n", "E_AUTHORIZATION_REQUEST_TRAILING"),
            ("second_value", request_raw + b"{}", "E_AUTHORIZATION_REQUEST_TRAILING"),
            (
                "duplicate_key",
                b'{"audience":"'
                + PROFILES[0]["audience"].encode("ascii")
                + b'",'
                + request_raw[1:],
                "E_JSON_DUPLICATE_KEY",
            ),
            (
                "float",
                request_raw.replace(b'"schema_version":1', b'"schema_version":1.0'),
                "E_JSON_FLOAT",
            ),
            (
                "nonfinite",
                request_raw.replace(b'"schema_version":1', b'"schema_version":Infinity'),
                "E_JSON_NONFINITE",
            ),
            (
                "int_range",
                request_raw.replace(
                    b'"schema_version":1',
                    b'"schema_version":-9223372036854775809',
                ),
                "E_JSON_INT_RANGE",
            ),
            ("root_array", b"[]", "E_AUTHORIZATION_REQUEST_ROOT"),
            ("leading_space", b" " + request_raw, "E_AUTHORIZATION_REQUEST_JSON"),
            (
                "noncanonical_order",
                _noncanonical_bytes(request),
                "E_AUTHORIZATION_REQUEST_NONCANONICAL",
            ),
            (
                "unicode_scalar",
                b'{"probe":"\\ud800",' + request_raw[1:],
                "E_AUTHORIZATION_REQUEST_UNICODE_SCALAR",
            ),
            (
                "depth",
                canonical_bytes({"probe": nested}),
                "E_JSON_DEPTH",
            ),
            (
                "object_members",
                canonical_bytes({f"k{i:03d}": i for i in range(257)}),
                "E_JSON_OBJECT_MEMBERS",
            ),
            (
                "array_items",
                canonical_bytes({"probe": list(range(65))}),
                "E_JSON_ARRAY_ITEMS",
            ),
        ]
        for name, raw, detail in request_json_cases:
            reject(
                "request_json",
                name,
                request_bytes=raw,
                code="E_SIGNER_ROLE_SCOPE_AUTHORIZATION_FAILED",
                detail=detail,
            )

        for field in POLICY_KEYS:
            reject(
                "policy_closed_world",
                f"missing_top_{field}",
                policy_bytes=_mutated(policy, lambda value, f=field: value.pop(f)),
                code="E_SIGNER_AUTHORIZATION_POLICY_REJECTED",
                detail="E_AUTHORIZATION_POLICY_FIELDS",
            )
        reject(
            "policy_closed_world",
            "extra_top",
            policy_bytes=_mutated(
                policy,
                lambda value: value.__setitem__("production_policy", True),
            ),
            code="E_SIGNER_AUTHORIZATION_POLICY_REJECTED",
            detail="E_AUTHORIZATION_POLICY_FIELDS",
        )

        top_policy_mutations: tuple[
            tuple[str, Callable[[dict[str, Any]], None]], ...
        ] = (
            (
                "schema_drift",
                lambda value: value.__setitem__("schema", POLICY_SCHEMA + ".drift"),
            ),
            (
                "schema_type",
                lambda value: value.__setitem__("schema", True),
            ),
            (
                "schema_version_drift",
                lambda value: value.__setitem__("schema_version", 2),
            ),
            (
                "schema_version_bool",
                lambda value: value.__setitem__("schema_version", True),
            ),
            (
                "default_allow",
                lambda value: value.__setitem__("default_effect", "ALLOW"),
            ),
            (
                "matching_wildcard",
                lambda value: value.__setitem__("matching_profile", "WILDCARD"),
            ),
            (
                "zero_match_not_deny",
                lambda value: value.__setitem__("deny_on_zero_matches", False),
            ),
            (
                "zero_match_integer",
                lambda value: value.__setitem__("deny_on_zero_matches", 1),
            ),
            (
                "multiple_match_not_deny",
                lambda value: value.__setitem__(
                    "deny_on_multiple_matches", False
                ),
            ),
            (
                "grants_not_list",
                lambda value: value.__setitem__("grants", {}),
            ),
            (
                "one_grant",
                lambda value: value.__setitem__("grants", value["grants"][:1]),
            ),
            (
                "three_grants",
                lambda value: value.__setitem__(
                    "grants", value["grants"] + [copy.deepcopy(value["grants"][0])]
                ),
            ),
            (
                "reversed_profiles",
                lambda value: value["grants"].reverse(),
            ),
            (
                "duplicate_profiles",
                lambda value: value["grants"].__setitem__(
                    1, copy.deepcopy(value["grants"][0])
                ),
            ),
        )
        for name, operation in top_policy_mutations:
            reject(
                "policy_closed_world",
                name,
                policy_bytes=_mutated(policy, operation),
                code="E_SIGNER_AUTHORIZATION_POLICY_REJECTED",
            )

        reject(
            "policy_closed_world",
            "grant_not_object",
            policy_bytes=_mutated(
                policy,
                lambda value: value["grants"].__setitem__(0, "grant"),
            ),
            code="E_SIGNER_AUTHORIZATION_POLICY_REJECTED",
        )
        for field in GRANT_KEYS:
            reject(
                "policy_closed_world",
                f"grant_missing_{field}",
                policy_bytes=_mutated(
                    policy,
                    lambda value, f=field: value["grants"][0].pop(f),
                ),
                code="E_SIGNER_AUTHORIZATION_POLICY_REJECTED",
                detail="E_AUTHORIZATION_GRANT_FIELDS",
            )
        reject(
            "policy_closed_world",
            "grant_extra",
            policy_bytes=_mutated(
                policy,
                lambda value: value["grants"][0].__setitem__("priority", 1),
            ),
            code="E_SIGNER_AUTHORIZATION_POLICY_REJECTED",
            detail="E_AUTHORIZATION_GRANT_FIELDS",
        )
        for field in GRANT_KEYS:
            reject(
                "policy_closed_world",
                f"grant_exact_drift_{field}",
                policy_bytes=_mutated(
                    policy,
                    lambda value, f=field: value["grants"][0].__setitem__(
                        f, str(value["grants"][0][f]) + "_DRIFT"
                    ),
                ),
                code="E_SIGNER_AUTHORIZATION_POLICY_REJECTED",
            )
        for name, operation in (
            (
                "grant_string_type",
                lambda value: value["grants"][0].__setitem__("subject", 1),
            ),
            (
                "grant_empty_scope",
                lambda value: value["grants"][0].__setitem__("subject", ""),
            ),
            (
                "grant_nonascii_scope",
                lambda value: value["grants"][0].__setitem__("subject", "角色"),
            ),
            (
                "grant_wildcard_star",
                lambda value: value["grants"][0].__setitem__("subject", "*"),
            ),
            (
                "grant_wildcard_question",
                lambda value: value["grants"][0].__setitem__("audience", "?"),
            ),
            (
                "grant_scope_oversize",
                lambda value: value["grants"][0].__setitem__("nonce_scope", "A" * 257),
            ),
        ):
            reject(
                "policy_closed_world",
                name,
                policy_bytes=_mutated(policy, operation),
                code="E_SIGNER_AUTHORIZATION_POLICY_REJECTED",
            )

        for field in REQUEST_KEYS:
            reject(
                "request_scope",
                f"missing_{field}",
                request_bytes=_mutated(request, lambda value, f=field: value.pop(f)),
                code="E_SIGNER_ROLE_SCOPE_AUTHORIZATION_FAILED",
                detail="E_AUTHORIZATION_REQUEST_FIELDS",
            )
        for field in FORBIDDEN_REQUEST_SIGNER_FIELDS + (
            "action",
            "resource",
            "capability",
            "predecessor_receipt",
        ):
            reject(
                "request_scope",
                f"forbidden_{field}",
                request_bytes=_mutated(
                    request,
                    lambda value, f=field: value.__setitem__(f, "CALLER_VALUE"),
                ),
                code="E_SIGNER_ROLE_SCOPE_AUTHORIZATION_FAILED",
                detail="E_AUTHORIZATION_REQUEST_FIELDS",
            )
        for name, operation in (
            (
                "schema_drift",
                lambda value: value.__setitem__("schema", REQUEST_SCHEMA + ".drift"),
            ),
            (
                "schema_type",
                lambda value: value.__setitem__("schema", False),
            ),
            (
                "schema_version_drift",
                lambda value: value.__setitem__("schema_version", 2),
            ),
            (
                "schema_version_bool",
                lambda value: value.__setitem__("schema_version", True),
            ),
        ):
            reject(
                "request_scope",
                name,
                request_bytes=_mutated(request, operation),
                code="E_SIGNER_ROLE_SCOPE_AUTHORIZATION_FAILED",
            )

        scope_variants: tuple[tuple[str, Callable[[str], Any]], ...] = (
            ("type", lambda original: 1),
            ("empty", lambda original: ""),
            ("wildcard_star", lambda original: original + "*"),
            ("wildcard_question", lambda original: original + "?"),
            ("nonascii", lambda original: original + "é"),
            ("oversize", lambda original: "A" * 257),
            ("prefix", lambda original: original[:-1]),
            ("hierarchy_slash", lambda original: original + "/child"),
            ("hierarchy_colon", lambda original: original + "::child"),
            ("case_fold", lambda original: original.lower()),
        )
        for field in SCOPE_FIELDS:
            for variant_name, transform in scope_variants:
                reject(
                    "request_scope",
                    f"{field}_{variant_name}",
                    request_bytes=_mutated(
                        request,
                        lambda value, f=field, fn=transform: value.__setitem__(
                            f, fn(value[f])
                        ),
                    ),
                    code="E_SIGNER_ROLE_SCOPE_AUTHORIZATION_FAILED",
                )

        for field in ("track_id", "subject", "audience", "nonce_scope"):
            reject(
                "request_scope",
                f"cross_track_{field}",
                request_bytes=_mutated(
                    request,
                    lambda value, f=field: value.__setitem__(f, PROFILES[1][f]),
                ),
                code="E_SIGNER_ROLE_SCOPE_AUTHORIZATION_FAILED",
            )

        receipt_binding_fields = (
            "active_leaf_key_id",
            "active_leaf_key_version",
            "content_sha256",
            "declared_role",
            "frame_sha256",
            "mapped_policy_leaf_role",
            "revocation_snapshot_revision",
            "track_id",
            "track_leaf_role",
            "trust_policy_sha256",
            "vector_set_id",
        )
        receipt_scalar_fields = (
            "component_state",
            "declared_role_cryptographically_authenticated_in_kat",
            "declared_role_is_role_scope_authorization",
            "execution_mode",
            "frozen_revocation_snapshot_is_currentness",
            "isolated_lab_candidate_surface_components_implemented",
            "local_t05_specification_exercised",
            "local_t06_specification_exercised",
            "production_admissible",
            "provider_authority",
            "schema",
            "schema_version",
            "signature_verification_count",
            "runtime_authority",
            "signer_role_scope_authorization_implemented",
            "synthetic_fixture",
        )

        def drift(value: Any) -> Any:
            if type(value) is bool:
                return not value
            if type(value) is int:
                return value + 1
            return str(value) + "_DRIFT"

        for field in receipt_binding_fields + receipt_scalar_fields:
            candidate = copy.deepcopy(predecessor_receipt)
            candidate[field] = drift(candidate[field])
            current_receipt = candidate
            reject(
                "receipt_identity",
                f"drift_{field}",
                code="E_SIGNER_ROLE_SCOPE_AUTHORIZATION_FAILED",
                detail=f"E_PREDECESSOR_RECEIPT_{field.upper()}_BINDING",
            )
        for field in receipt_binding_fields:
            candidate = copy.deepcopy(predecessor_receipt)
            candidate.pop(field)
            current_receipt = candidate
            reject(
                "receipt_identity",
                f"missing_{field}",
                code="E_SIGNER_ROLE_SCOPE_AUTHORIZATION_FAILED",
                detail=f"E_PREDECESSOR_RECEIPT_{field.upper()}_BINDING",
            )
        current_receipt = predecessor_receipt

        for field in SCOPE_FIELDS:
            reject(
                "default_deny",
                f"zero_match_{field}",
                request_bytes=_mutated(
                    request,
                    lambda value, f=field: value.__setitem__(
                        f, str(value[f]) + "_NO_MATCH"
                    ),
                ),
                code="E_SIGNER_ROLE_SCOPE_AUTHORIZATION_FAILED",
                detail="E_SIGNER_ROLE_SCOPE_AUTHORIZATION_ZERO_MATCH_DENY",
            )

        original_validate_policy = module._validate_policy

        def two_matching_grants(
            value: Mapping[str, Any],
        ) -> tuple[Mapping[str, Any], ...]:
            grant = grant_for(PROFILES[0])
            return (copy.deepcopy(grant), copy.deepcopy(grant))

        module._validate_policy = two_matching_grants
        try:
            reject(
                "default_deny",
                "multiple_match",
                code="E_SIGNER_ROLE_SCOPE_AUTHORIZATION_FAILED",
                detail="E_SIGNER_ROLE_SCOPE_AUTHORIZATION_MULTIPLE_MATCH_DENY",
            )
        finally:
            module._validate_policy = original_validate_policy
    finally:
        module.predecessor.review_bootstrap_trust_authentication = original_reviewer

    require(
        sum(counts.values()) >= 160,
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
    allowed_imports = {
        "__future__",
        "hashlib",
        "json",
        "dataclasses",
        "typing",
        (
            "biocortex_ab_track_b_reference_provider_fault_injection_runner_"
            "bootstrap_trust_authentication_synthetic_trust_chain_exact_key_"
            "version_declared_role_and_revocation_verifier_isolated_lab_v1"
        ),
    }
    require(
        imports == allowed_imports,
        "E_SOURCE_FORBIDDEN_IMPORT",
        repr(sorted(imports)),
    )
    checks += 1

    public = _top_level_function(tree, "review_signer_role_scope_authorization")
    args = public.args
    require(
        [arg.arg for arg in args.args]
        == [
            "frame",
            "detached_authentication_bundle",
            "separately_injected_synthetic_trust_policy",
            "separately_injected_synthetic_signer_authorization_policy",
            "detached_authorization_request",
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
        body
        and isinstance(body[0], ast.Expr)
        and isinstance(body[0].value, ast.Call),
        "E_SOURCE_FIRST_GUARD",
        "first executable statement is not a call",
    )
    first_call = body[0].value
    require(
        isinstance(first_call.func, ast.Name)
        and first_call.func.id == "_reject_mode"
        and len(first_call.args) == 1
        and isinstance(first_call.args[0], ast.Name)
        and first_call.args[0].id == "mode"
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
        and node.func.attr == "review_bootstrap_trust_authentication"
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "predecessor"
    ]
    policy_decodes = [
        node
        for node in calls
        if isinstance(node.func, ast.Name)
        and node.func.id == "_decode_closed_json"
        and any(
            keyword.arg == "label"
            and isinstance(keyword.value, ast.Constant)
            and keyword.value.value == "AUTHORIZATION_POLICY"
            for keyword in node.keywords
        )
    ]
    request_decodes = [
        node
        for node in calls
        if isinstance(node.func, ast.Name)
        and node.func.id == "_decode_closed_json"
        and any(
            keyword.arg == "label"
            and isinstance(keyword.value, ast.Constant)
            and keyword.value.value == "AUTHORIZATION_REQUEST"
            for keyword in node.keywords
        )
    ]

    def named_calls(name: str) -> list[ast.Call]:
        return [
            node
            for node in calls
            if isinstance(node.func, ast.Name) and node.func.id == name
        ]

    policy_validations = named_calls("_validate_policy")
    request_validations = named_calls("_validate_request")
    grant_selections = named_calls("_select_grant")
    receipt_bindings = named_calls("_bind_predecessor_receipt")
    require(
        len(predecessor_calls)
        == len(policy_decodes)
        == len(request_decodes)
        == len(policy_validations)
        == len(request_validations)
        == len(grant_selections)
        == len(receipt_bindings)
        == 1,
        "E_SOURCE_REVIEW_CALL_COUNTS",
        (
            f"t05={len(predecessor_calls)},policy_decode={len(policy_decodes)},"
            f"request_decode={len(request_decodes)},"
            f"policy_validate={len(policy_validations)},"
            f"request_validate={len(request_validations)},"
            f"select={len(grant_selections)},bind={len(receipt_bindings)}"
        ),
    )
    require(
        predecessor_calls[0].lineno
        < policy_decodes[0].lineno
        < policy_validations[0].lineno
        < request_decodes[0].lineno
        < request_validations[0].lineno
        < grant_selections[0].lineno
        < receipt_bindings[0].lineno,
        "E_SOURCE_REVIEW_ORDER",
        "mode -> T05 -> policy -> request -> exact match -> receipt bind",
    )
    require(
        [ast.unparse(arg) for arg in predecessor_calls[0].args]
        == [
            "frame",
            "detached_authentication_bundle",
            "separately_injected_synthetic_trust_policy",
            "predecessor.SYNTHETIC_KAT_MODE",
        ]
        and not predecessor_calls[0].keywords,
        "E_SOURCE_PREDECESSOR_CALL",
        ast.unparse(predecessor_calls[0]),
    )
    checks += 1

    require(
        tuple(_literal_assignment(tree, "REQUEST_SCOPE_FIELDS")) == SCOPE_FIELDS
        and tuple(_literal_assignment(tree, "REQUEST_SIGNER_FIELDS_FORBIDDEN"))
        == FORBIDDEN_REQUEST_SIGNER_FIELDS
        and tuple(_literal_assignment(tree, "AUTHORIZATION_POLICY_KEYS"))
        == POLICY_KEYS
        and tuple(_literal_assignment(tree, "AUTHORIZATION_GRANT_KEYS"))
        == GRANT_KEYS
        and tuple(_literal_assignment(tree, "AUTHORIZATION_REQUEST_KEYS"))
        == REQUEST_KEYS,
        "E_SOURCE_CLOSED_WORLD_LITERALS",
        "policy/request fields drift",
    )
    checks += 1

    profile_assignments = [
        node.value
        for node in tree.body
        if isinstance(node, ast.Assign)
        and any(
            isinstance(target, ast.Name) and target.id == "AUTHORIZATION_PROFILES"
            for target in node.targets
        )
    ]
    require(
        len(profile_assignments) == 1
        and isinstance(profile_assignments[0], ast.Tuple)
        and len(profile_assignments[0].elts) == 2
        and all(
            isinstance(element, ast.Call)
            and isinstance(element.func, ast.Name)
            and element.func.id == "AuthorizationProfile"
            for element in profile_assignments[0].elts
        ),
        "E_SOURCE_TWO_PROFILES",
        str(len(profile_assignments)),
    )
    checks += 1

    reject_text = ast.unparse(_top_level_function(tree, "_reject_mode"))
    require(
        "type(mode) is not str" in reject_text
        and "mode == PRODUCTION_MODE" in reject_text
        and "mode != SYNTHETIC_KAT_MODE" in reject_text,
        "E_SOURCE_REJECT_MODE_SHAPE",
        reject_text,
    )
    checks += 1

    decode_text = ast.unparse(_top_level_function(tree, "_decode_closed_json"))
    require(
        "type(raw) is bytes" in decode_text
        and (
            'raw.decode("utf-8", "strict")' in decode_text
            or "raw.decode('utf-8', 'strict')" in decode_text
        )
        and "object_pairs_hook=_reject_pairs" in decode_text
        and "parse_constant=_parse_constant" in decode_text
        and "parse_float=_parse_float" in decode_text
        and "parse_int=_parse_int" in decode_text
        and "strict=True" in decode_text
        and "canonical == raw" in decode_text,
        "E_SOURCE_STRICT_JSON",
        decode_text,
    )
    checks += 1

    ascii_text = ast.unparse(_top_level_function(tree, "_ascii_scope"))
    select_text = ast.unparse(_top_level_function(tree, "_select_grant"))
    policy_text = ast.unparse(_top_level_function(tree, "_validate_policy"))
    request_text = ast.unparse(_top_level_function(tree, "_validate_request"))
    require(
        "value.encode('ascii', 'strict')" in ascii_text
        and "'*' not in value" in ascii_text
        and "'?' not in value" in ascii_text
        and "len(grants) == 2" in policy_text
        and "REQUEST_SCOPE_FIELDS" in request_text
        and "for field in REQUEST_SCOPE_FIELDS" in select_text
        and "len(matches) != 0" in select_text
        and "len(matches) == 1" in select_text,
        "E_SOURCE_EXACT_MATCH_DEFAULT_DENY",
        "ASCII/exact/zero/multiple contract drift",
    )
    checks += 1

    binding_text = ast.unparse(
        _top_level_function(tree, "_bind_predecessor_receipt")
    )
    normalized_binding_text = binding_text.replace("'", '"')
    for token in (
        '"active_leaf_key_id": grant["signer_key_id"]',
        '"active_leaf_key_version": grant["signer_key_version"]',
        '"declared_role": grant["declared_role_class"]',
        '"mapped_policy_leaf_role": grant["signer_role"]',
        '"track_leaf_role": grant["signer_role"]',
        '"content_sha256": grant["predecessor_receipt_content_sha256"]',
        '"frame_sha256": grant["frame_sha256"]',
        '"trust_policy_sha256": grant["trust_policy_sha256"]',
        '"revocation_snapshot_revision": grant["revocation_snapshot_revision"]',
        '"vector_set_id": grant["vector_set_id"]',
        '"track_id": grant["track_id"]',
        '"signature_verification_count": 1',
        '"frozen_revocation_snapshot_is_currentness": False',
        '"signer_role_scope_authorization_implemented": False',
    ):
        require(
            token in normalized_binding_text,
            "E_SOURCE_RECEIPT_ONLY_BINDING",
            token,
        )
    require(
        "authorization_request" not in binding_text
        and "detached_authentication_bundle" not in binding_text,
        "E_SOURCE_RECEIPT_IDENTITY_CONTAMINATION",
        binding_text,
    )
    checks += 1

    dataclasses = [
        node
        for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == "AuthorizationProfile"
    ]
    require(len(dataclasses) == 1, "E_SOURCE_PROFILE_DATACLASS", str(len(dataclasses)))
    decorators = dataclasses[0].decorator_list
    require(
        len(decorators) == 1
        and isinstance(decorators[0], ast.Call)
        and isinstance(decorators[0].func, ast.Name)
        and decorators[0].func.id == "dataclass"
        and any(
            keyword.arg == "frozen"
            and isinstance(keyword.value, ast.Constant)
            and keyword.value.value is True
            for keyword in decorators[0].keywords
        ),
        "E_SOURCE_PROFILE_NOT_FROZEN",
        ast.unparse(dataclasses[0]),
    )
    checks += 1

    forbidden_name_calls = {
        "open",
        "input",
        "print",
        "exec",
        "eval",
        "compile",
        "__import__",
    }
    forbidden_attribute_calls = {
        "getenv",
        "urandom",
        "sign",
        "signing",
        "generate",
        "keygen",
        "connect",
        "request",
        "urlopen",
        "run",
        "Popen",
        "system",
        "sleep",
        "time",
        "now",
        "utcnow",
        "read_text",
        "read_bytes",
        "write_text",
        "write_bytes",
    }
    observed_forbidden: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name) and node.func.id in forbidden_name_calls:
                observed_forbidden.add(node.func.id)
            elif (
                isinstance(node.func, ast.Attribute)
                and node.func.attr in forbidden_attribute_calls
            ):
                observed_forbidden.add(node.func.attr)
    require(
        not observed_forbidden,
        "E_SOURCE_FORBIDDEN_CALL",
        repr(sorted(observed_forbidden)),
    )
    checks += 1

    mutable_module_bindings: list[str] = []
    mutable_nodes = (
        ast.Dict,
        ast.DictComp,
        ast.List,
        ast.ListComp,
        ast.Set,
        ast.SetComp,
    )
    mutable_constructor_names = {"bytearray", "dict", "list", "set"}
    mutable_or_cache_attributes = {
        "cache",
        "cached_property",
        "defaultdict",
        "deque",
        "lru_cache",
    }
    for node in tree.body:
        value: ast.expr | None = None
        targets: list[ast.expr] = []
        if isinstance(node, ast.Assign):
            value = node.value
            targets = list(node.targets)
        elif isinstance(node, ast.AnnAssign):
            value = node.value
            targets = [node.target]
        names = [
            target.id for target in targets if isinstance(target, ast.Name)
        ]
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
            mutable_module_bindings.extend(
                name for name in names if name != "__all__"
            )
    require(
        not any(
            isinstance(
                node,
                (
                    ast.Global,
                    ast.Nonlocal,
                    ast.AsyncFunctionDef,
                    ast.Await,
                    ast.Yield,
                    ast.YieldFrom,
                ),
            )
            for node in ast.walk(tree)
        )
        and not mutable_module_bindings,
        "E_SOURCE_MUTABLE_OR_ASYNC",
        repr(mutable_module_bindings),
    )
    checks += 1

    identifiers = {
        node.id for node in ast.walk(tree) if isinstance(node, ast.Name)
    } | {
        node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute)
    }
    forbidden_identifiers = {
        "cache",
        "cached_property",
        "defaultdict",
        "deque",
        "lru_cache",
        "memoize",
        "memoized",
        "private_key",
        "private_seed",
        "secret_key",
        "secret_seed",
        "credential",
        "credential_path",
        "provider_endpoint",
        "aws_access_key_id",
        "google_application_credentials",
    }
    require(
        not identifiers.intersection(forbidden_identifiers),
        "E_SOURCE_SECRET_OR_PROVIDER_IDENTIFIER",
        repr(sorted(identifiers.intersection(forbidden_identifiers))),
    )
    checks += 1

    exports = _literal_assignment(tree, "__all__")
    require(
        "review_signer_role_scope_authorization" in exports
        and "known_answer_authorization_policy_bytes" in exports
        and "known_answer_authorization_request_bytes" in exports
        and "SignerAuthorizationReviewError" in exports,
        "E_SOURCE_EXPORTS",
        repr(exports),
    )
    checks += 1

    require(
        text.count("predecessor.review_bootstrap_trust_authentication(") == 1
        and '"signer_identity_source": "T05_PREDECESSOR_RECEIPT_ONLY"' in text
        and '"authorization_request_signer_field_count": 0' in text
        and '"wildcard_prefix_hierarchy_or_inheritance_authorization_implemented": False'
        in text,
        "E_SOURCE_LEXICAL_AUTHORIZATION_BOUNDARY",
        "T05/request/wildcard boundary drift",
    )
    checks += 1
    require(
        '"production_signer_role_scope_authorization_implemented": False' in text
        and '"signer_role_scope_authorization_isolated_lab_component_implemented": True'
        in text
        and '"target_production_control": "SIGNER_ROLE_SCOPE_AUTHORIZATION"' in text
        and '"t09_content_identity_and_quarantine_custody_implemented": False'
        in text
        and '"upstream_decision_record_t09_replay_cas_implemented": False' in text
        and '"t09_replay_cas_implemented": False' not in text,
        "E_SOURCE_AUTHORITY_TRUTH",
        "production/T09 truth drift",
    )
    checks += 1
    return checks


def fixture_schema_checks() -> tuple[dict[str, Any], dict[str, Any], int]:
    require(
        raw_sha256(FIXTURE_REL) == FIXTURE_RAW_SHA256,
        "E_FIXTURE_RAW_HASH",
        raw_sha256(FIXTURE_REL),
    )
    require(
        raw_sha256(SCHEMA_REL) == SCHEMA_RAW_SHA256,
        "E_SCHEMA_RAW_HASH",
        raw_sha256(SCHEMA_REL),
    )
    require(
        raw_sha256(PREDECESSOR_SOURCE_REL) == PREDECESSOR_SOURCE_SHA256,
        "E_PREDECESSOR_SOURCE_HASH",
        raw_sha256(PREDECESSOR_SOURCE_REL),
    )
    require(
        raw_sha256(PREDECESSOR_FIXTURE_REL) == PREDECESSOR_FIXTURE_SHA256,
        "E_PREDECESSOR_FIXTURE_HASH",
        raw_sha256(PREDECESSOR_FIXTURE_REL),
    )
    require(
        raw_sha256(OWNER_DECISION_REL) == OWNER_DECISION_SHA256,
        "E_OWNER_DECISION_HASH",
        raw_sha256(OWNER_DECISION_REL),
    )
    fixture = read_artifact_json(FIXTURE_REL)
    schema = read_artifact_json(SCHEMA_REL)
    predecessor_fixture = read_artifact_json(PREDECESSOR_FIXTURE_REL)
    checks = 5

    fixture_keys = {
        "canonical_json_profile",
        "contains_private_or_seed_material",
        "date",
        "execution_mode",
        "expected_receipts",
        "public_only",
        "schema",
        "separately_injected_synthetic_signer_authorization_policy",
        "source_bindings",
        "valid_cases",
    }
    require(set(fixture) == fixture_keys, "E_FIXTURE_FIELDS", repr(set(fixture)))
    checks += 1
    require(
        fixture["canonical_json_profile"]
        == "SORTED_KEYS_COMPACT_UTF8_NO_TRAILING_BYTES"
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
        exact_equal(
            fixture["separately_injected_synthetic_signer_authorization_policy"],
            expected_policy(),
        )
        and sha256(
            canonical_bytes(
                fixture[
                    "separately_injected_synthetic_signer_authorization_policy"
                ]
            )
        )
        == POLICY_SHA256,
        "E_FIXTURE_POLICY",
        "independent policy mismatch",
    )
    checks += 1
    require(
        exact_equal(
            fixture["valid_cases"],
            [expected_valid_case(profile) for profile in PROFILES],
        ),
        "E_FIXTURE_VALID_CASES",
        "valid cases drift",
    )
    checks += 1
    require(
        type(fixture["expected_receipts"]) is list
        and len(fixture["expected_receipts"]) == 2
        and all(
            type(receipt) is dict and len(receipt) == 97
            for receipt in fixture["expected_receipts"]
        ),
        "E_FIXTURE_RECEIPT_SHAPE",
        "two exact 97-field receipts required",
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
        "signer_authorization_policy_sha256": POLICY_SHA256,
        "trust_policy_sha256": TRUST_POLICY_SHA256,
    }
    require(
        exact_equal(fixture["source_bindings"], expected_bindings),
        "E_FIXTURE_SOURCE_BINDINGS",
        "source binding drift",
    )
    checks += 1
    require(
        predecessor_fixture["contains_private_or_seed_material"] is False
        and predecessor_fixture["public_only"] is True
        and predecessor_fixture["execution_mode"] == SYNTHETIC_MODE
        and sha256(
            canonical_bytes(
                predecessor_fixture[
                    "separately_injected_synthetic_trust_policy"
                ]
            )
        )
        == TRUST_POLICY_SHA256
        and len(predecessor_fixture["valid_cases"]) == 2
        and len(predecessor_fixture["expected_receipts"]) == 2,
        "E_PREDECESSOR_FIXTURE_SEMANTICS",
        "predecessor fixture drift",
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
    require(
        "no production, provider, runtime, evidence, output, fault-injection, replay"
        in schema["description"]
        and "exactly one T05 call" in schema["$comment"]
        and "T05-receipt-only signer identity" in schema["$comment"]
        and "policy-before-request order" in schema["$comment"]
        and "zero/multiple-match denial" in schema["$comment"],
        "E_SCHEMA_NONCLAIM",
        "description/comment drift",
    )
    checks += 1

    metadata_consts = {
        "canonical_json_profile": (
            "SORTED_KEYS_COMPACT_UTF8_NO_TRAILING_BYTES"
        ),
        "contains_private_or_seed_material": False,
        "date": DATE,
        "execution_mode": SYNTHETIC_MODE,
        "public_only": True,
        "schema": FIXTURE_SCHEMA,
    }
    for field, expected in metadata_consts.items():
        require(
            exact_equal(schema["properties"][field], {"const": expected}),
            "E_SCHEMA_METADATA_CONST",
            field,
        )
    checks += 1

    expected_receipts_schema = schema["properties"]["expected_receipts"]
    require(
        expected_receipts_schema["type"] == "array"
        and expected_receipts_schema["minItems"] == 2
        and expected_receipts_schema["maxItems"] == 2
        and expected_receipts_schema["items"] is False
        and exact_equal(
            expected_receipts_schema["prefixItems"],
            [{"const": value} for value in fixture["expected_receipts"]],
        ),
        "E_SCHEMA_RECEIPT_CONSTS",
        "expected receipts schema drift",
    )
    checks += 1
    require(
        exact_equal(
            schema["properties"][
                "separately_injected_synthetic_signer_authorization_policy"
            ],
            {
                "const": fixture[
                    "separately_injected_synthetic_signer_authorization_policy"
                ]
            },
        )
        and exact_equal(
            schema["properties"]["source_bindings"],
            {"const": fixture["source_bindings"]},
        ),
        "E_SCHEMA_POLICY_BINDINGS",
        "policy/source const drift",
    )
    checks += 1
    valid_cases_schema = schema["properties"]["valid_cases"]
    require(
        valid_cases_schema["type"] == "array"
        and valid_cases_schema["minItems"] == 2
        and valid_cases_schema["maxItems"] == 2
        and valid_cases_schema["items"] is False
        and exact_equal(
            valid_cases_schema["prefixItems"],
            [{"const": value} for value in fixture["valid_cases"]],
        ),
        "E_SCHEMA_VALID_CASE_CONSTS",
        "valid cases schema drift",
    )
    checks += 1
    return fixture, predecessor_fixture, checks


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
        "mode": SYNTHETIC_MODE,
        "component_state": COMPONENT_STATE,
        "positive_track_count": 2,
        "real_predecessor_review_count": real_predecessor_reviews,
        "public_mode_pre_observation_test_count": mode_tests,
        "predecessor_exactly_once_order_test_count": order_tests,
        "policy_json_negative_test_count": mutation_counts["policy_json"],
        "request_json_negative_test_count": mutation_counts["request_json"],
        "policy_closed_world_negative_test_count": mutation_counts[
            "policy_closed_world"
        ],
        "request_scope_negative_test_count": mutation_counts["request_scope"],
        "receipt_identity_negative_test_count": mutation_counts[
            "receipt_identity"
        ],
        "default_deny_negative_test_count": mutation_counts["default_deny"],
        "total_directed_negative_test_count": total_negative,
        "source_ast_guard_count": source_checks,
        "fixture_schema_guard_count": fixture_schema_checks_count,
        "fixture_expected_receipt_count": 2,
        "authorization_grant_count": 2,
        "request_scope_dimension_count": 6,
        "isolated_lab_candidate_surface_component_total": 4,
        "isolated_lab_candidate_surface_components_implemented": 4,
        "local_threat_specifications_covered": 6,
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
        "signer_authorization_policy_sha256": sha256(policy_raw),
        "authorization_request_set_sha256": domain_sha256(
            "AB_SIGNER_ROLE_SCOPE_AUTHORIZATION_REQUEST_SET_V1",
            [sha256(raw) for raw in request_raws],
        ),
        "receipt_set_sha256": domain_sha256(
            "AB_SIGNER_ROLE_SCOPE_AUTHORIZATION_RECEIPT_SET_V1",
            receipts,
        ),
        "trust_policy_sha256": TRUST_POLICY_SHA256,
        "schema_raw_sha256": raw_sha256(SCHEMA_REL),
        "fixture_raw_sha256": raw_sha256(FIXTURE_REL),
        "source_raw_sha256": raw_sha256(SOURCE_REL),
        "predecessor_source_raw_sha256": raw_sha256(PREDECESSOR_SOURCE_REL),
        "predecessor_fixture_raw_sha256": raw_sha256(PREDECESSOR_FIXTURE_REL),
        "owner_decision_raw_sha256": raw_sha256(OWNER_DECISION_REL),
        "content_sha256": "0" * 64,
    }
    require(
        set(result) == set(TSV_FIELDS),
        "E_PACK_RECEIPT_FIELDS",
        repr(set(result) ^ set(TSV_FIELDS)),
    )
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
        require(
            "\t" not in text
            and "\n" not in text
            and "\r" not in text,
            "E_TSV_CONTROL",
            text,
        )
        return text

    return "".join(
        f"{field}\t{scalar(receipt[field])}\n" for field in TSV_FIELDS
    )


def evaluate() -> tuple[str, dict[str, int]]:
    source_checks = source_contract_checks()
    fixture, predecessor_fixture, fixture_schema_count = fixture_schema_checks()
    module = load_module()
    (
        frames,
        bundles,
        trust_policy_raw,
        policy_raw,
        requests,
        receipts,
        predecessor_receipts,
        real_predecessor_reviews,
    ) = positive_checks(module, fixture, predecessor_fixture)
    mode_tests = check_pre_observation_modes(module)
    order_tests = check_predecessor_exactly_once_order(
        module,
        frames[0],
        bundles[0],
        trust_policy_raw,
        policy_raw,
        requests[0],
        predecessor_receipts[0],
    )
    mutation_counts = directed_mutations(
        module,
        frames[0],
        bundles[0],
        trust_policy_raw,
        policy_raw,
        requests[0],
        predecessor_receipts[0],
    )
    receipt = pack_receipt(
        policy_raw,
        requests,
        receipts,
        real_predecessor_reviews,
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
    parser.add_argument(
        "--candidate",
        action="store_true",
        help="accepted for pack-gate symmetry",
    )
    args = parser.parse_args()
    try:
        rendered, counts = evaluate()
        if args.self_test:
            print("self_test\tPASS")
            for key in (
                "policy_json",
                "request_json",
                "policy_closed_world",
                "request_scope",
                "receipt_identity",
                "default_deny",
                "mode",
                "order",
                "source",
                "fixture_schema",
                "total",
            ):
                print(f"{key}_test_count\t{counts[key]}")
            print("real_positive_t05_review_count\t2")
            print("independent_receipt_oracle_field_count\t97")
            print("source_ast_purity\tPASS")
            print("signer_identity_source\tT05_PREDECESSOR_RECEIPT_ONLY")
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
        print(
            "signer role/scope isolated-lab pack check failed: " + str(error),
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
