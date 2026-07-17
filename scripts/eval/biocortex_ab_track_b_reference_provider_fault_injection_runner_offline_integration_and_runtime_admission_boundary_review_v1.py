#!/usr/bin/env python3
"""Deterministic offline integration and runtime-admission boundary review.

This module accepts already-public synthetic predecessor structures and emits a
review receipt. It performs no file, environment, clock, process, network, or
random I/O. A positive offline-integration result is deliberately separate
from runtime admission, execution authority, and downstream output authority.
"""

from __future__ import annotations

import copy
import hashlib
import json
from dataclasses import asdict, dataclass, fields
from typing import Any, Iterable, Mapping


RECEIPT_SCHEMA = (
    "agent_bridge.biocortex_ab_track_b_reference_provider_fault_injection_runner_"
    "offline_integration_and_runtime_admission_boundary_review_v1.receipt.v0"
)
FIXTURE_SCHEMA = (
    "agent_bridge.biocortex_ab_track_b_reference_provider_fault_injection_runner_"
    "offline_integration_and_runtime_admission_boundary_review_v1.synthetic.v0"
)
STATUS = (
    "REFERENCE_PROVIDER_FAULT_INJECTION_RUNNER_V1_OFFLINE_INTEGRATION_REVIEWED_"
    "RUNTIME_ADMISSION_BLOCKED_NO_AUTHORITY"
)
DECISION = (
    "OFFLINE_INTEGRATION_COMPLETE_FOR_SYNTHETIC_CONFORMANCE_"
    "RUNTIME_ADMISSION_BLOCKED_FAIL_CLOSED"
)
NEXT_UNIT = (
    "REFERENCE_PROVIDER_MANAGED_AND_SELF_HOSTED_FAULT_INJECTION_RUNNER_V1_"
    "RUNTIME_PREREQUISITE_EVIDENCE_PLAN_AND_OWNER_DECISION_PREREGISTRATION"
)
PREDECESSOR_SCHEMA = (
    "agent_bridge.biocortex_ab_track_b_reference_provider_fault_injection_runner_"
    "offline_authority_and_adapter_doubles_v1_pack_manifest.v0"
)
PREDECESSOR_STATUS = (
    "REFERENCE_PROVIDER_FAULT_INJECTION_RUNNER_V1_OFFLINE_AUTHORITY_VERIFIER_AND_"
    "ADAPTER_DOUBLES_IMPLEMENTED_NO_PROVIDER_NO_CREDENTIAL_NO_PERMIT"
)
PREDECESSOR_DECISION = (
    "OFFLINE_AUTHORITY_VERIFIER_AND_ADAPTER_DOUBLES_PASS_RUNTIME_EXECUTION_"
    "REMAINS_BLOCKED"
)
PREDECESSOR_NEXT_UNIT = (
    "REFERENCE_PROVIDER_MANAGED_AND_SELF_HOSTED_FAULT_INJECTION_RUNNER_V1_"
    "OFFLINE_INTEGRATION_AND_RUNTIME_ADMISSION_BOUNDARY_REVIEW"
)

TRACKS = (
    "MANAGED_SPANNER_CLOUD_KMS",
    "SELF_HOSTED_ETCD_OPENBAO",
)
ADAPTER_IDS = (
    "SPANNER_AUTHORITY_ADAPTER",
    "CLOUD_KMS_SIGNER_ADAPTER",
    "MANAGED_FAULT_PROXY_ADAPTER",
    "MANAGED_EVIDENCE_COLLECTOR_ADAPTER",
    "ETCD_AUTHORITY_ADAPTER",
    "OPENBAO_TRANSIT_ADAPTER",
    "EXTERNAL_RESTORE_WITNESS_ADAPTER",
    "LAB_FAULT_CONTROLLER_ADAPTER",
    "SELF_HOSTED_EVIDENCE_COLLECTOR_ADAPTER",
)
STOP_CONTROL_IDS = (
    "CAPABILITY_FENCE_CONTROL",
    "FAULT_DISARM_AND_EGRESS_ISOLATION_CONTROL",
    "CREDENTIAL_BROKER_REVOCATION_CONTROL",
    "DURABLE_EVIDENCE_RETENTION_CONTROL",
    "SCOPED_RESOURCE_CLEANUP_CONTROL",
)

RUNTIME_PREREQUISITES = (
    (
        "PRODUCTION_AUTHORITY_VERIFIER_IMPLEMENTED",
        "IMPLEMENTATION_OWNER",
        "AUDITED_PRODUCTION_VERIFIER_BUILD_AND_TEST_RECEIPT",
        "MISSING_NOT_IMPLEMENTED",
    ),
    (
        "PRODUCTION_MANAGED_ADAPTER_SET_IMPLEMENTED",
        "MANAGED_PROVIDER_OPERATOR",
        "FOUR_MANAGED_ADAPTER_BUILD_AND_CONFORMANCE_RECEIPTS",
        "MISSING_NOT_IMPLEMENTED",
    ),
    (
        "PRODUCTION_SELF_HOSTED_ADAPTER_SET_IMPLEMENTED",
        "SELF_HOSTED_LAB_OPERATOR",
        "FIVE_SELF_HOSTED_ADAPTER_BUILD_AND_CONFORMANCE_RECEIPTS",
        "MISSING_NOT_IMPLEMENTED",
    ),
    (
        "PRODUCTION_STOP_CONTROL_SET_IMPLEMENTED",
        "SAFETY_OPERATOR",
        "FIVE_STOP_CONTROL_BUILD_AND_FAILURE_INJECTION_RECEIPTS",
        "MISSING_NOT_IMPLEMENTED",
    ),
    (
        "TRUST_ROOT_AND_KEY_VERSION_POLICY_BOUND",
        "SECURITY_OWNER",
        "TRUST_ROOT_KEY_VERSION_ROLE_AND_REVOCATION_POLICY_RECEIPTS",
        "MISSING_NOT_BOUND",
    ),
    (
        "PROVIDER_ENDPOINT_AND_PROFILE_IDENTITY_BOUND",
        "PROVIDER_OPERATOR",
        "EXACT_ENDPOINT_PROFILE_REGION_AND_NAMESPACE_BINDING_RECEIPTS",
        "MISSING_NOT_BOUND",
    ),
    (
        "CREDENTIAL_BROKER_LEASE_AND_REVOCATION_BOUND",
        "CREDENTIAL_BROKER_OWNER",
        "SCOPED_LEASE_ISSUE_REVOKE_AND_ZERO_ACTIVE_COMMITMENT_RECEIPTS",
        "MISSING_NOT_BOUND",
    ),
    (
        "RESOURCE_SCOPE_AND_COST_BUDGET_AUTHORITY_BOUND",
        "RESOURCE_AND_COST_OWNER",
        "EXACT_RESOURCE_SCOPE_COST_CEILING_AND_BUDGET_AUTHORITY_RECEIPTS",
        "MISSING_NOT_BOUND",
    ),
    (
        "DURABLE_CONTROL_LEDGER_AND_ATOMIC_CAS_PROVEN",
        "AUTHORITY_STORE_OWNER",
        "DURABLE_SINGLE_USE_LEDGER_LINEARIZABILITY_AND_CAS_FAILURE_RECEIPTS",
        "MISSING_NOT_PROVEN",
    ),
    (
        "TRUSTED_TIME_AND_CURRENTNESS_EVIDENCE_BOUND",
        "TIME_AUTHORITY_OWNER",
        "SIGNED_TRUSTED_TIME_AND_ROW_CURRENTNESS_PRODUCTION_RECEIPTS",
        "MISSING_NOT_BOUND",
    ),
    (
        "RUNNER_BUILD_PROCESS_SESSION_AND_CHANNEL_PROVENANCE_BOUND",
        "RUNNER_OPERATOR",
        "RUNNER_BUILD_PROCESS_SESSION_CHANNEL_AND_EXPORTER_BINDING_RECEIPTS",
        "MISSING_NOT_BOUND",
    ),
    (
        "FAULT_DISARM_EGRESS_ISOLATION_AND_EMERGENCY_STOP_PROVEN",
        "SAFETY_OPERATOR",
        "LIVE_DISARM_EGRESS_ISOLATION_AND_INDEPENDENT_EMERGENCY_STOP_DRILL_RECEIPTS",
        "MISSING_NOT_PROVEN",
    ),
    (
        "DURABLE_EVIDENCE_RETENTION_AND_SCOPED_CLEANUP_PROVEN",
        "EVIDENCE_CUSTODIAN",
        "DURABLE_RETENTION_REPLAY_AND_REDUCTIVE_CLEANUP_DRILL_RECEIPTS",
        "MISSING_NOT_PROVEN",
    ),
    (
        "REAL_PREREGISTERED_SCHEDULE_ASSIGNMENT_AND_ROW_CUSTODY_BOUND",
        "TRIAL_CUSTODIAN",
        "OWNER_PREREGISTERED_SCHEDULE_ASSIGNMENT_AND_ALL_ROW_CUSTODY_RECEIPTS",
        "MISSING_NOT_BOUND",
    ),
    (
        "INDEPENDENT_SECURITY_FAILURE_MODE_AND_ROLLBACK_REVIEW_APPROVED",
        "INDEPENDENT_REVIEWER",
        "INDEPENDENT_SECURITY_FAILURE_MODE_CANARY_AND_ROLLBACK_APPROVAL",
        "MISSING_NOT_APPROVED",
    ),
    (
        "OWNER_RUNTIME_ADMISSION_DECISION_RECORDED",
        "OWNER",
        "EXPLICIT_OWNER_DECISION_BOUND_TO_ALL_PREREQUISITE_RECEIPTS",
        "MISSING_OWNER_DECISION",
    ),
)

DOWNSTREAM_SEPARATE_GATES = (
    "CONDITION_OUTPUT_GATE",
    "OUTPUT_PERMIT_GATE",
    "SCIENTIFIC_CLAIM_GATE",
    "APPLICATION_CLAIM_GATE",
)


class BoundaryReviewError(ValueError):
    pass


def require(condition: bool, code: str, message: str) -> None:
    if not condition:
        raise BoundaryReviewError(f"{code}: {message}")


def exact_keys(value: Mapping[str, Any], expected: Iterable[str], code: str) -> None:
    expected_set = set(expected)
    actual_set = set(value)
    require(actual_set == expected_set, code, "closed-world key set drift")


def canonical_bytes(value: Any) -> bytes:
    return (
        json.dumps(
            value,
            sort_keys=True,
            indent=2,
            ensure_ascii=False,
            allow_nan=False,
            separators=(",", ": "),
        )
        + "\n"
    ).encode("utf-8")


def sha256_value(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


@dataclass(frozen=True)
class BoundaryNonClaims:
    """Every review-only nonclaim is explicit and machine-checkable."""

    provider_endpoint_bound: bool
    provider_called: bool
    wire_attempted: bool
    credentials_accessed: bool
    paid_resource_provisioned: bool
    production_authority_verifier_implemented: bool
    production_adapter_implemented: bool
    production_stop_control_implemented: bool
    real_runner_launched: bool
    runtime_row_created: bool
    experiment_row_created: bool
    condition_output_authorized: bool
    output_permit_defined: bool
    runtime_admission_ready: bool
    runtime_admission_granted: bool
    runtime_authority: bool
    deployment_authorized: bool
    scientific_claim_authorized: bool
    application_claim_authorized: bool
    review_receipt_is_execution_authority: bool
    review_receipt_is_output_permit: bool
    offline_review_is_runtime_admission: bool
    side_effects_unlocked: str

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "BoundaryNonClaims":
        names = tuple(field.name for field in fields(cls))
        exact_keys(value, names, "E_NONCLAIM_KEYS")
        for name in names:
            item = value[name]
            if name == "side_effects_unlocked":
                require(type(item) is str, "E_NONCLAIM_TYPE", name)
            else:
                require(type(item) is bool, "E_NONCLAIM_TYPE", name)
        return cls(**dict(value))

    def all_explicit(self) -> bool:
        values = asdict(self)
        if set(values) != {field.name for field in fields(self)}:
            return False
        for name, value in values.items():
            if name == "side_effects_unlocked":
                if value != "NONE":
                    return False
            elif type(value) is not bool or value:
                return False
        return True

    def as_dict(self) -> dict[str, object]:
        return asdict(self)


def _expected_prerequisite_rows() -> list[dict[str, Any]]:
    return [
        {
            "evidence_required": evidence,
            "owner_class": owner,
            "prerequisite_id": prerequisite_id,
            "satisfied": False,
            "status": status,
        }
        for prerequisite_id, owner, evidence, status in RUNTIME_PREREQUISITES
    ]


def _expected_downstream_gates() -> list[dict[str, Any]]:
    return [
        {
            "authorized": False,
            "gate_id": gate_id,
            "status": "SEPARATE_NOT_AUTHORIZED",
        }
        for gate_id in DOWNSTREAM_SEPARATE_GATES
    ]


EXPECTED_PREDECESSOR_BOUNDARY: dict[str, Any] = {
    "condition_output_authorized": False,
    "credentials_accessed": False,
    "execution_capability_emitted": False,
    "experiment_executed": False,
    "live_endpoint_bound": False,
    "offline_adapter_doubles_implemented": 9,
    "offline_authority_verifier_implemented": True,
    "offline_stop_control_doubles_implemented": 5,
    "output_permit_defined": False,
    "paid_resources_provisioned": False,
    "production_adapter_implemented": False,
    "provider_called": False,
    "receipt_is_execution_authority": False,
    "receipt_is_output_permit": False,
    "runtime_authority": False,
    "side_effects_unlocked": "NONE",
    "synthetic_private_capability_consumed": True,
}

EXPECTED_PREDECESSOR_RECEIPT: dict[str, Any] = {
    "schema": (
        "agent_bridge.biocortex_ab_track_b_reference_provider_fault_injection_runner_"
        "offline_authority_and_adapter_doubles_v1.conformance_receipt.v0"
    ),
    "status": PREDECESSOR_STATUS,
    "decision": PREDECESSOR_DECISION,
    "authority_bundles_verified": 9,
    "scope_signature_receipts_verified": 45,
    "control_evidence_receipts_verified": 18,
    "private_capability_commitments_verified": 9,
    "control_ledger_start_cas": 9,
    "adapter_calls": 9,
    "adapter_forbidden_rejections": 9,
    "adapter_cross_scope_rejections": 9,
    "adapter_duplicate_rejections": 9,
    "stop_sequences_absorbing_complete": 1,
    "stop_sequences_failed_quarantined": 5,
    "stop_control_operation_receipts": 6,
    "provider_calls": 0,
    "wire_attempts": 0,
    "credentials_accessed": 0,
    "paid_resources_provisioned": 0,
    "runtime_rows": 0,
    "experiment_rows": 0,
    "condition_outputs": 0,
    "output_permits": 0,
    "side_effects_unlocked": "NONE",
    "receipt_is_execution_authority": False,
    "receipt_is_output_permit": False,
    "runtime_authority": False,
    "content_sha256": "e35b9ce29df31b68ef67b1c19f6ff256b361106dc4946452ad585d604b49b899",
    "next_unit": PREDECESSOR_NEXT_UNIT,
    "directed_negative_tests": 115,
    "source_ast_purity": "PASS",
}


def _validate_predecessor_manifest(manifest: Mapping[str, Any]) -> None:
    expected_keys = {
        "boundary",
        "date",
        "decision",
        "evidence_sha256",
        "logical_baseline_commit",
        "next_unit",
        "packet",
        "predecessor",
        "results",
        "schema",
        "status",
        "test_oracle",
        "tracks",
    }
    exact_keys(manifest, expected_keys, "E_PREDECESSOR_MANIFEST_KEYS")
    require(manifest["schema"] == PREDECESSOR_SCHEMA, "E_PREDECESSOR_SCHEMA", "schema")
    require(manifest["status"] == PREDECESSOR_STATUS, "E_PREDECESSOR_STATUS", "status")
    require(
        manifest["decision"] == PREDECESSOR_DECISION,
        "E_PREDECESSOR_DECISION",
        "decision",
    )
    require(
        manifest["next_unit"] == PREDECESSOR_NEXT_UNIT,
        "E_PREDECESSOR_NEXT_UNIT",
        "next unit",
    )
    boundary = manifest["boundary"]
    require(type(boundary) is dict, "E_PREDECESSOR_BOUNDARY", "not object")
    require(
        boundary == EXPECTED_PREDECESSOR_BOUNDARY,
        "E_PREDECESSOR_BOUNDARY",
        "boundary drift",
    )
    tracks = manifest["tracks"]
    require(
        tracks
        == {
            TRACKS[0]: "OFFLINE_DOUBLE_CONFORMANCE_ONLY_NO_RUNTIME",
            TRACKS[1]: "OFFLINE_DOUBLE_CONFORMANCE_ONLY_NO_RUNTIME",
        },
        "E_PREDECESSOR_TRACKS",
        "track decision drift",
    )
    results = manifest["results"]
    require(type(results) is dict, "E_PREDECESSOR_RESULTS", "not object")
    required_results = {
        "adapter_calls": 9,
        "authority_bundles_verified": 9,
        "control_evidence_receipts_verified": 18,
        "experiment_rows": 0,
        "private_capability_commitments_verified": 9,
        "provider_calls": 0,
        "runtime_rows": 0,
        "scope_signature_receipts_verified": 45,
        "stop_sequences_absorbing_complete": 1,
        "stop_sequences_failed_quarantined": 5,
        "wire_attempts": 0,
    }
    for name, expected in required_results.items():
        require(results.get(name) == expected, "E_PREDECESSOR_RESULTS", name)
    require(
        results.get("conformance_content_sha256")
        == EXPECTED_PREDECESSOR_RECEIPT["content_sha256"],
        "E_PREDECESSOR_CONTENT",
        "content hash mismatch",
    )


def _validate_predecessor_receipt(receipt: Mapping[str, Any]) -> None:
    require(
        dict(receipt) == EXPECTED_PREDECESSOR_RECEIPT,
        "E_PREDECESSOR_RECEIPT",
        "deterministic receipt drift",
    )


def _validate_fixture(fixture: Mapping[str, Any]) -> BoundaryNonClaims:
    exact_keys(
        fixture,
        {
            "date",
            "downstream_separate_gates",
            "expected",
            "nonclaims",
            "predecessor",
            "review_scope",
            "runtime_prerequisites",
            "schema",
            "synthetic_only",
        },
        "E_FIXTURE_KEYS",
    )
    require(fixture["schema"] == FIXTURE_SCHEMA, "E_FIXTURE_SCHEMA", "schema")
    require(fixture["date"] == "2026-07-16", "E_FIXTURE_DATE", "date")
    require(fixture["synthetic_only"] is True, "E_FIXTURE_SYNTHETIC", "flag")
    predecessor = fixture["predecessor"]
    require(type(predecessor) is dict, "E_FIXTURE_PREDECESSOR", "not object")
    exact_keys(
        predecessor,
        {
            "checker_path",
            "checker_sha256",
            "expected_path",
            "expected_sha256",
            "gate_path",
            "gate_sha256",
            "integration_commit",
            "manifest_path",
            "manifest_sha256",
            "module_path",
            "module_sha256",
            "report_path",
            "report_sha256",
            "source_commit",
        },
        "E_FIXTURE_PREDECESSOR_KEYS",
    )
    require(
        predecessor["integration_commit"]
        == "a1c9469e9a14cd73159d34974f0e99714ce5a1f0",
        "E_FIXTURE_INTEGRATION_COMMIT",
        "commit",
    )
    require(
        predecessor["source_commit"]
        == "425ce42fa4f2bc1bbf2ce072c7a8b3407cd8bbb1",
        "E_FIXTURE_SOURCE_COMMIT",
        "commit",
    )
    scope = fixture["review_scope"]
    require(type(scope) is dict, "E_SCOPE", "not object")
    exact_keys(scope, {"adapter_ids", "stop_control_ids", "tracks"}, "E_SCOPE_KEYS")
    require(scope["tracks"] == list(TRACKS), "E_SCOPE_TRACKS", "track catalog")
    require(scope["adapter_ids"] == list(ADAPTER_IDS), "E_SCOPE_ADAPTERS", "adapter catalog")
    require(
        scope["stop_control_ids"] == list(STOP_CONTROL_IDS),
        "E_SCOPE_STOP_CONTROLS",
        "STOP catalog",
    )
    require(
        fixture["runtime_prerequisites"] == _expected_prerequisite_rows(),
        "E_RUNTIME_PREREQUISITES",
        "prerequisite catalog drift",
    )
    require(
        fixture["downstream_separate_gates"] == _expected_downstream_gates(),
        "E_DOWNSTREAM_GATES",
        "downstream gate catalog drift",
    )
    expected = fixture["expected"]
    require(type(expected) is dict, "E_EXPECTED", "not object")
    required_expected = {
        "adapter_doubles_reviewed": 9,
        "all_nonclaims_explicit": True,
        "downstream_separate_gate_count": 4,
        "integration_component_count": 15,
        "nonclaim_field_count": 23,
        "production_components_bound": 0,
        "runtime_prerequisite_count": 16,
        "runtime_prerequisites_satisfied": 0,
        "stop_control_doubles_reviewed": 5,
        "synthetic_components_complete": 15,
        "track_count": 2,
    }
    require(expected == required_expected, "E_EXPECTED", "oracle drift")
    nonclaims_raw = fixture["nonclaims"]
    require(type(nonclaims_raw) is dict, "E_NONCLAIMS", "not object")
    nonclaims = BoundaryNonClaims.from_mapping(nonclaims_raw)
    require(nonclaims.all_explicit(), "E_NONCLAIMS", "nonclaim escalation")
    return nonclaims


def _integration_matrix() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = [
        {
            "component_id": "OFFLINE_AUTHORITY_VERIFIER",
            "component_kind": "AUTHORITY_VERIFIER",
            "production_bound": False,
            "runtime_authority_contribution": False,
            "status": "SYNTHETIC_CONFORMANCE_COMPLETE_PRODUCTION_BINDING_MISSING",
            "synthetic_implemented": True,
            "track_scope": "BOTH_TRACKS",
        }
    ]
    for index, adapter_id in enumerate(ADAPTER_IDS):
        rows.append(
            {
                "component_id": adapter_id,
                "component_kind": "EXPERIMENT_ADAPTER_DOUBLE",
                "production_bound": False,
                "runtime_authority_contribution": False,
                "status": "SYNTHETIC_CONFORMANCE_COMPLETE_PRODUCTION_BINDING_MISSING",
                "synthetic_implemented": True,
                "track_scope": TRACKS[0] if index < 4 else TRACKS[1],
            }
        )
    for control_id in STOP_CONTROL_IDS:
        rows.append(
            {
                "component_id": control_id,
                "component_kind": "STOP_CONTROL_DOUBLE",
                "production_bound": False,
                "runtime_authority_contribution": False,
                "status": "SYNTHETIC_CONFORMANCE_COMPLETE_PRODUCTION_BINDING_MISSING",
                "synthetic_implemented": True,
                "track_scope": "BOTH_TRACKS",
            }
        )
    return rows


class OfflineIntegrationRuntimeAdmissionBoundaryReviewer:
    """Compose a fail-closed review from exact synthetic predecessor evidence."""

    def review(
        self,
        predecessor_manifest: Mapping[str, Any],
        predecessor_receipt: Mapping[str, Any],
        fixture: Mapping[str, Any],
    ) -> dict[str, Any]:
        _validate_predecessor_manifest(predecessor_manifest)
        _validate_predecessor_receipt(predecessor_receipt)
        nonclaims = _validate_fixture(fixture)

        matrix = _integration_matrix()
        prerequisites = _expected_prerequisite_rows()
        downstream_gates = _expected_downstream_gates()
        synthetic_complete = sum(row["synthetic_implemented"] is True for row in matrix)
        production_bound = sum(row["production_bound"] is True for row in matrix)
        prerequisites_satisfied = sum(row["satisfied"] is True for row in prerequisites)
        downstream_authorized = sum(row["authorized"] is True for row in downstream_gates)
        expected = fixture["expected"]

        require(len(matrix) == expected["integration_component_count"], "E_MATRIX_COUNT", "count")
        require(
            synthetic_complete == expected["synthetic_components_complete"],
            "E_SYNTHETIC_COMPLETE",
            "count",
        )
        require(
            production_bound == expected["production_components_bound"],
            "E_PRODUCTION_BOUND",
            "count",
        )
        require(
            prerequisites_satisfied == expected["runtime_prerequisites_satisfied"],
            "E_PREREQUISITE_SATISFIED",
            "count",
        )
        require(downstream_authorized == 0, "E_DOWNSTREAM_AUTHORITY", "authorization")

        receipt: dict[str, Any] = {
            "adapter_doubles_reviewed": len(ADAPTER_IDS),
            "all_nonclaims_explicit": nonclaims.all_explicit(),
            "condition_outputs": 0,
            "content_sha256": "0" * 64,
            "credentials_accessed": 0,
            "date": "2026-07-16",
            "decision": DECISION,
            "downstream_separate_gate_count": len(downstream_gates),
            "downstream_separate_gates": downstream_gates,
            "downstream_separate_gates_sha256": sha256_value(downstream_gates),
            "experiment_rows": 0,
            "integration_component_count": len(matrix),
            "integration_matrix": matrix,
            "integration_matrix_sha256": sha256_value(matrix),
            "next_unit": NEXT_UNIT,
            "nonclaim_field_count": len(nonclaims.as_dict()),
            "nonclaims": nonclaims.as_dict(),
            "nonclaims_sha256": sha256_value(nonclaims.as_dict()),
            "offline_integration_reviewed": True,
            "offline_synthetic_conformance_complete": True,
            "output_permits": 0,
            "paid_resources_provisioned": 0,
            "predecessor_manifest_sha256": sha256_value(predecessor_manifest),
            "predecessor_receipt_sha256": sha256_value(predecessor_receipt),
            "production_components_bound": production_bound,
            "provider_calls": 0,
            "receipt_is_execution_authority": False,
            "receipt_is_output_permit": False,
            "receipt_is_runtime_admission": False,
            "runtime_admission_granted": False,
            "runtime_admission_ready": False,
            "runtime_authority": False,
            "runtime_prerequisite_count": len(prerequisites),
            "runtime_prerequisites": prerequisites,
            "runtime_prerequisites_missing": len(prerequisites) - prerequisites_satisfied,
            "runtime_prerequisites_satisfied": prerequisites_satisfied,
            "runtime_prerequisites_sha256": sha256_value(prerequisites),
            "runtime_rows": 0,
            "schema": RECEIPT_SCHEMA,
            "side_effects_unlocked": "NONE",
            "status": STATUS,
            "stop_control_doubles_reviewed": len(STOP_CONTROL_IDS),
            "synthetic_components_complete": synthetic_complete,
            "tracks_reviewed": len(TRACKS),
            "wire_attempts": 0,
        }
        content = copy.deepcopy(receipt)
        del content["content_sha256"]
        receipt["content_sha256"] = sha256_value(content)
        return receipt


TSV_FIELDS = (
    "schema",
    "status",
    "decision",
    "date",
    "tracks_reviewed",
    "integration_component_count",
    "synthetic_components_complete",
    "production_components_bound",
    "adapter_doubles_reviewed",
    "stop_control_doubles_reviewed",
    "runtime_prerequisite_count",
    "runtime_prerequisites_satisfied",
    "runtime_prerequisites_missing",
    "downstream_separate_gate_count",
    "nonclaim_field_count",
    "all_nonclaims_explicit",
    "offline_integration_reviewed",
    "offline_synthetic_conformance_complete",
    "runtime_admission_ready",
    "runtime_admission_granted",
    "provider_calls",
    "wire_attempts",
    "credentials_accessed",
    "paid_resources_provisioned",
    "runtime_rows",
    "experiment_rows",
    "condition_outputs",
    "output_permits",
    "side_effects_unlocked",
    "receipt_is_execution_authority",
    "receipt_is_output_permit",
    "receipt_is_runtime_admission",
    "runtime_authority",
    "predecessor_manifest_sha256",
    "predecessor_receipt_sha256",
    "integration_matrix_sha256",
    "runtime_prerequisites_sha256",
    "downstream_separate_gates_sha256",
    "nonclaims_sha256",
    "content_sha256",
    "next_unit",
)


def render_tsv(receipt: Mapping[str, Any]) -> str:
    rows: list[str] = []
    for field in TSV_FIELDS:
        require(field in receipt, "E_TSV_FIELD", field)
        value = receipt[field]
        if type(value) is bool:
            rendered = "true" if value else "false"
        else:
            rendered = str(value)
        require("\t" not in rendered and "\n" not in rendered, "E_TSV_VALUE", field)
        rows.append(f"{field}\t{rendered}")
    return "\n".join(rows) + "\n"
