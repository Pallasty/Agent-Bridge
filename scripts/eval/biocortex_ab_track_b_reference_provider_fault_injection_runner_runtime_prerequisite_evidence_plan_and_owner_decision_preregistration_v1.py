#!/usr/bin/env python3
"""Pure offline runtime-prerequisite plan and owner-decision preregistration.

The reviewer consumes already-public synthetic structures and performs no file,
environment, clock, process, network, dynamic-import, or random I/O. Its output
can preregister evidence requirements and fail-closed decisions, but cannot
represent positive runtime admission or unlock any side effect.
"""

from __future__ import annotations

import copy
import hashlib
import json
from dataclasses import asdict, dataclass, fields
from typing import Any, Iterable, Mapping


RECEIPT_SCHEMA = (
    "agent_bridge.biocortex_ab_track_b_reference_provider_fault_injection_runner_"
    "runtime_prerequisite_evidence_plan_and_owner_decision_preregistration_v1.receipt.v0"
)
FIXTURE_SCHEMA = (
    "agent_bridge.biocortex_ab_track_b_reference_provider_fault_injection_runner_"
    "runtime_prerequisite_evidence_plan_and_owner_decision_preregistration_v1.synthetic.v0"
)
STATUS = (
    "REFERENCE_PROVIDER_FAULT_INJECTION_RUNNER_V1_RUNTIME_PREREQUISITE_EVIDENCE_PLAN_"
    "AND_OWNER_DECISION_PREREGISTERED_PENDING_NO_AUTHORITY"
)
DECISION = (
    "RUNTIME_PREREQUISITE_EVIDENCE_PLAN_AND_OWNER_DECISION_PREREGISTERED_FAIL_CLOSED"
)
NEXT_UNIT = (
    "REFERENCE_PROVIDER_MANAGED_AND_SELF_HOSTED_FAULT_INJECTION_RUNNER_V1_"
    "RUNTIME_PREREQUISITE_EVIDENCE_PACKET_SCHEMAS_AND_OFFLINE_VALIDATOR_DOUBLES"
)
PREDECESSOR_SCHEMA = (
    "agent_bridge.biocortex_ab_track_b_reference_provider_fault_injection_runner_"
    "offline_integration_and_runtime_admission_boundary_review_v1_pack_manifest.v0"
)
PREDECESSOR_STATUS = (
    "REFERENCE_PROVIDER_FAULT_INJECTION_RUNNER_V1_OFFLINE_INTEGRATION_REVIEWED_"
    "RUNTIME_ADMISSION_BLOCKED_NO_AUTHORITY"
)
PREDECESSOR_DECISION = (
    "OFFLINE_INTEGRATION_COMPLETE_FOR_SYNTHETIC_CONFORMANCE_"
    "RUNTIME_ADMISSION_BLOCKED_FAIL_CLOSED"
)
PREDECESSOR_NEXT_UNIT = (
    "REFERENCE_PROVIDER_MANAGED_AND_SELF_HOSTED_FAULT_INJECTION_RUNNER_V1_"
    "RUNTIME_PREREQUISITE_EVIDENCE_PLAN_AND_OWNER_DECISION_PREREGISTRATION"
)
PREDECESSOR_MANIFEST_SHA256 = (
    "8a107f72023fb419ebabd771a33172fa09c9eca5d4b1e574df494d8ce3f6fdb1"
)
PLAN_SHA256 = "260036232778e6d22f2050333b0daeab7d70153a15cb7f36526f47d1514a239b"
OWNER_PREREG_SHA256 = "fe35e633f6cd2448e322e254c55ee081cdd9b9c8f783cbd691b65550950384b1"
DOWNSTREAM_GATES_SHA256 = "7bddf917ab9f16c01854d0b83032d22ede0b224b62faf15c7910f1e695f57b24"
NONCLAIMS_SHA256 = "2c41cf3017e769a398d308491f32134543e518edc20ec870ebdba7389146a41a"
EXPECTED_SHA256 = "8a25c2b22af1288b7c49720054d6117c2ceeeb96a806ed1bac7523ad8001aefb"
PREDECESSOR_BINDING_SHA256 = "10acd2979681f8584c18e394e046b0de6a7096a3be3c27c59430bcca53a0e222"
TRACKS_SHA256 = "9596196af6e1631b1a3870d9e0097535322887386d03b34469188555cb9f8716"

TRACKS = (
    "MANAGED_SPANNER_CLOUD_KMS",
    "SELF_HOSTED_ETCD_OPENBAO",
)
PREREQUISITES = (
    ("PRODUCTION_AUTHORITY_VERIFIER_IMPLEMENTED", "IMPLEMENTATION_OWNER", "AUDITED_PRODUCTION_VERIFIER_BUILD_AND_TEST_RECEIPT"),
    ("PRODUCTION_MANAGED_ADAPTER_SET_IMPLEMENTED", "MANAGED_PROVIDER_OPERATOR", "FOUR_MANAGED_ADAPTER_BUILD_AND_CONFORMANCE_RECEIPTS"),
    ("PRODUCTION_SELF_HOSTED_ADAPTER_SET_IMPLEMENTED", "SELF_HOSTED_LAB_OPERATOR", "FIVE_SELF_HOSTED_ADAPTER_BUILD_AND_CONFORMANCE_RECEIPTS"),
    ("PRODUCTION_STOP_CONTROL_SET_IMPLEMENTED", "SAFETY_OPERATOR", "FIVE_STOP_CONTROL_BUILD_AND_FAILURE_INJECTION_RECEIPTS"),
    ("TRUST_ROOT_AND_KEY_VERSION_POLICY_BOUND", "SECURITY_OWNER", "TRUST_ROOT_KEY_VERSION_ROLE_AND_REVOCATION_POLICY_RECEIPTS"),
    ("PROVIDER_ENDPOINT_AND_PROFILE_IDENTITY_BOUND", "PROVIDER_OPERATOR", "EXACT_ENDPOINT_PROFILE_REGION_AND_NAMESPACE_BINDING_RECEIPTS"),
    ("CREDENTIAL_BROKER_LEASE_AND_REVOCATION_BOUND", "CREDENTIAL_BROKER_OWNER", "SCOPED_LEASE_ISSUE_REVOKE_AND_ZERO_ACTIVE_COMMITMENT_RECEIPTS"),
    ("RESOURCE_SCOPE_AND_COST_BUDGET_AUTHORITY_BOUND", "RESOURCE_AND_COST_OWNER", "EXACT_RESOURCE_SCOPE_COST_CEILING_AND_BUDGET_AUTHORITY_RECEIPTS"),
    ("DURABLE_CONTROL_LEDGER_AND_ATOMIC_CAS_PROVEN", "AUTHORITY_STORE_OWNER", "DURABLE_SINGLE_USE_LEDGER_LINEARIZABILITY_AND_CAS_FAILURE_RECEIPTS"),
    ("TRUSTED_TIME_AND_CURRENTNESS_EVIDENCE_BOUND", "TIME_AUTHORITY_OWNER", "SIGNED_TRUSTED_TIME_AND_ROW_CURRENTNESS_PRODUCTION_RECEIPTS"),
    ("RUNNER_BUILD_PROCESS_SESSION_AND_CHANNEL_PROVENANCE_BOUND", "RUNNER_OPERATOR", "RUNNER_BUILD_PROCESS_SESSION_CHANNEL_AND_EXPORTER_BINDING_RECEIPTS"),
    ("FAULT_DISARM_EGRESS_ISOLATION_AND_EMERGENCY_STOP_PROVEN", "SAFETY_OPERATOR", "LIVE_DISARM_EGRESS_ISOLATION_AND_INDEPENDENT_EMERGENCY_STOP_DRILL_RECEIPTS"),
    ("DURABLE_EVIDENCE_RETENTION_AND_SCOPED_CLEANUP_PROVEN", "EVIDENCE_CUSTODIAN", "DURABLE_RETENTION_REPLAY_AND_REDUCTIVE_CLEANUP_DRILL_RECEIPTS"),
    ("REAL_PREREGISTERED_SCHEDULE_ASSIGNMENT_AND_ROW_CUSTODY_BOUND", "TRIAL_CUSTODIAN", "OWNER_PREREGISTERED_SCHEDULE_ASSIGNMENT_AND_ALL_ROW_CUSTODY_RECEIPTS"),
    ("INDEPENDENT_SECURITY_FAILURE_MODE_AND_ROLLBACK_REVIEW_APPROVED", "INDEPENDENT_REVIEWER", "INDEPENDENT_SECURITY_FAILURE_MODE_CANARY_AND_ROLLBACK_APPROVAL"),
    ("OWNER_RUNTIME_ADMISSION_DECISION_RECORDED", "OWNER", "EXPLICIT_OWNER_DECISION_BOUND_TO_ALL_PREREQUISITE_RECEIPTS"),
)
DOWNSTREAM_GATE_IDS = (
    "CONDITION_OUTPUT_GATE",
    "OUTPUT_PERMIT_GATE",
    "SCIENTIFIC_CLAIM_GATE",
    "APPLICATION_CLAIM_GATE",
)


class PreregistrationReviewError(ValueError):
    pass


def require(condition: bool, code: str, message: str) -> None:
    if not condition:
        raise PreregistrationReviewError(f"{code}: {message}")


def exact_keys(value: Mapping[str, Any], expected: Iterable[str], code: str) -> None:
    require(set(value) == set(expected), code, "closed-world key set drift")


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
    """Closed-world declarations proving this pack has no runtime authority."""

    provider_endpoint_bound: bool
    provider_called: bool
    wire_attempted: bool
    credentials_accessed: bool
    paid_resource_provisioned: bool
    production_authority_verifier_implemented: bool
    production_adapter_implemented: bool
    production_stop_control_implemented: bool
    real_evidence_collected: bool
    evidence_receipt_accepted: bool
    owner_decision_recorded: bool
    positive_owner_decision_representable: bool
    positive_runtime_decision_recorded: bool
    owner_decision_authority_exercised: bool
    real_runner_launched: bool
    runtime_row_created: bool
    experiment_row_created: bool
    condition_output_authorized: bool
    output_permit_defined: bool
    runtime_prerequisite_satisfied: bool
    runtime_admission_ready: bool
    runtime_admission_granted: bool
    runtime_authority: bool
    deployment_authorized: bool
    scientific_claim_authorized: bool
    application_claim_authorized: bool
    evidence_plan_is_evidence_receipt: bool
    preregistration_receipt_is_execution_authority: bool
    preregistration_receipt_is_output_permit: bool
    preregistration_is_runtime_admission: bool
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


def _validate_predecessor_manifest(manifest: Mapping[str, Any]) -> None:
    exact_keys(
        manifest,
        {
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
        },
        "E_PREDECESSOR_KEYS",
    )
    require(manifest["schema"] == PREDECESSOR_SCHEMA, "E_PREDECESSOR_SCHEMA", "schema")
    require(manifest["status"] == PREDECESSOR_STATUS, "E_PREDECESSOR_STATUS", "status")
    require(manifest["decision"] == PREDECESSOR_DECISION, "E_PREDECESSOR_DECISION", "decision")
    require(manifest["next_unit"] == PREDECESSOR_NEXT_UNIT, "E_PREDECESSOR_NEXT", "next unit")
    require(manifest["date"] == "2026-07-16", "E_PREDECESSOR_DATE", "date")
    require(sha256_value(manifest) == PREDECESSOR_MANIFEST_SHA256, "E_PREDECESSOR_HASH", "manifest")
    boundary = manifest["boundary"]
    require(type(boundary) is dict, "E_PREDECESSOR_BOUNDARY", "not object")
    for name in (
        "condition_output_authorized",
        "deployment_authorized",
        "output_permit_defined",
        "provider_called",
        "receipt_is_execution_authority",
        "receipt_is_output_permit",
        "receipt_is_runtime_admission",
        "runtime_admission_granted",
        "runtime_admission_ready",
        "runtime_authority",
        "scientific_claim_authorized",
    ):
        require(boundary.get(name) is False, "E_PREDECESSOR_BOUNDARY", name)
    require(boundary.get("production_components_bound") == 0, "E_PREDECESSOR_BOUNDARY", "production components")
    require(boundary.get("side_effects_unlocked") == "NONE", "E_PREDECESSOR_BOUNDARY", "side effects")
    results = manifest["results"]
    require(type(results) is dict, "E_PREDECESSOR_RESULTS", "not object")
    require(results.get("runtime_prerequisite_count") == 16, "E_PREDECESSOR_RESULTS", "prerequisite count")
    require(results.get("runtime_prerequisites_satisfied") == 0, "E_PREDECESSOR_RESULTS", "prerequisite state")
    require(results.get("production_components_bound") == 0, "E_PREDECESSOR_RESULTS", "production binding")


def _validate_plan(plan: Any) -> list[dict[str, Any]]:
    require(type(plan) is list, "E_PLAN", "not list")
    require(len(plan) == len(PREREQUISITES), "E_PLAN_COUNT", "count")
    require(sha256_value(plan) == PLAN_SHA256, "E_PLAN_HASH", "frozen plan drift")
    expected_keys = {
        "collection_method",
        "depends_on",
        "evidence_class",
        "evidence_present",
        "evidence_required",
        "freshness_rule",
        "owner_class",
        "plan_status",
        "prerequisite_id",
        "rejection_reasons",
        "satisfied",
        "validation_rule",
    }
    seen: list[str] = []
    evidence_classes: set[str] = set()
    for index, (row, expected) in enumerate(zip(plan, PREREQUISITES, strict=True)):
        require(type(row) is dict, "E_PLAN_ROW", str(index))
        exact_keys(row, expected_keys, "E_PLAN_ROW_KEYS")
        prerequisite_id, owner_class, evidence_required = expected
        require(row["prerequisite_id"] == prerequisite_id, "E_PLAN_ID", str(index))
        require(row["owner_class"] == owner_class, "E_PLAN_OWNER", prerequisite_id)
        require(row["evidence_required"] == evidence_required, "E_PLAN_EVIDENCE", prerequisite_id)
        require(type(row["evidence_class"]) is str and row["evidence_class"], "E_PLAN_CLASS", prerequisite_id)
        require(row["evidence_class"] not in evidence_classes, "E_PLAN_CLASS", "duplicate")
        evidence_classes.add(row["evidence_class"])
        require(type(row["collection_method"]) is str and row["collection_method"].startswith("FUTURE_"), "E_PLAN_COLLECTION", prerequisite_id)
        require(type(row["freshness_rule"]) is str and row["freshness_rule"], "E_PLAN_FRESHNESS", prerequisite_id)
        require(type(row["validation_rule"]) is str and row["validation_rule"].startswith("VERIFY_"), "E_PLAN_VALIDATION", prerequisite_id)
        require(row["plan_status"] == "PREREGISTERED_NOT_COLLECTED", "E_PLAN_STATUS", prerequisite_id)
        require(row["evidence_present"] is False, "E_PLAN_EVIDENCE_PRESENT", prerequisite_id)
        require(row["satisfied"] is False, "E_PLAN_SATISFIED", prerequisite_id)
        reasons = row["rejection_reasons"]
        require(type(reasons) is list and len(reasons) == 4, "E_PLAN_REJECTIONS", prerequisite_id)
        require(all(type(reason) is str and reason for reason in reasons), "E_PLAN_REJECTIONS", prerequisite_id)
        require(len(reasons) == len(set(reasons)), "E_PLAN_REJECTIONS", "duplicate")
        dependencies = row["depends_on"]
        require(type(dependencies) is list, "E_PLAN_DEPENDENCIES", prerequisite_id)
        require(len(dependencies) == len(set(dependencies)), "E_PLAN_DEPENDENCIES", "duplicate")
        require(all(dependency in seen for dependency in dependencies), "E_PLAN_DEPENDENCIES", prerequisite_id)
        seen.append(prerequisite_id)
    require(len(evidence_classes) == 16, "E_PLAN_CLASS", "count")
    require(plan[-1]["depends_on"] == seen[:-1], "E_OWNER_DEPENDENCIES", "must depend on first fifteen")
    return copy.deepcopy(plan)


def _validate_owner_preregistration(value: Any, plan: list[dict[str, Any]]) -> dict[str, Any]:
    require(type(value) is dict, "E_OWNER_PREREG", "not object")
    exact_keys(
        value,
        {
            "allowed_current_decisions",
            "authority_owner_class",
            "current_decision_recorded",
            "current_evidence_set_hash",
            "current_state",
            "decision_binding_rule",
            "decision_prerequisite_id",
            "delegated_agent_authority",
            "evidence_prerequisite_ids",
            "fail_closed_transitions",
            "owner_identity_bound",
            "positive_decision_representable",
            "quorum_rule",
            "required_total_prerequisite_count_after_decision",
            "required_validated_evidence_count_before_decision",
            "schema",
            "side_effects_unlocked",
        },
        "E_OWNER_PREREG_KEYS",
    )
    require(sha256_value(value) == OWNER_PREREG_SHA256, "E_OWNER_PREREG_HASH", "frozen preregistration drift")
    require(value["allowed_current_decisions"] == ["PENDING_PREREQUISITE_EVIDENCE", "REJECTED_FAIL_CLOSED"], "E_OWNER_DECISIONS", "vocabulary")
    require(value["current_state"] == "PENDING_PREREQUISITE_EVIDENCE", "E_OWNER_STATE", "state")
    require(value["current_decision_recorded"] is False, "E_OWNER_STATE", "decision recorded")
    require(value["current_evidence_set_hash"] == "NONE", "E_OWNER_STATE", "evidence hash")
    require(value["owner_identity_bound"] is False, "E_OWNER_AUTHORITY", "identity")
    require(value["delegated_agent_authority"] is False, "E_OWNER_AUTHORITY", "delegation")
    require(value["positive_decision_representable"] is False, "E_OWNER_POSITIVE", "representation")
    require(value["authority_owner_class"] == "OWNER", "E_OWNER_AUTHORITY", "class")
    require(value["evidence_prerequisite_ids"] == [row["prerequisite_id"] for row in plan[:-1]], "E_OWNER_EVIDENCE_IDS", "ids")
    require(value["decision_prerequisite_id"] == plan[-1]["prerequisite_id"], "E_OWNER_DECISION_ID", "id")
    require(value["required_validated_evidence_count_before_decision"] == 15, "E_OWNER_COUNT", "before decision")
    require(value["required_total_prerequisite_count_after_decision"] == 16, "E_OWNER_COUNT", "after decision")
    require("NO_AGENT_SUBSTITUTE" in value["quorum_rule"], "E_OWNER_QUORUM", "agent substitution")
    require(value["side_effects_unlocked"] == "NONE", "E_OWNER_SIDE_EFFECTS", "side effects")
    transitions = value["fail_closed_transitions"]
    require(type(transitions) is list and len(transitions) == 6, "E_OWNER_TRANSITIONS", "count")
    for transition in transitions:
        require(type(transition) is dict, "E_OWNER_TRANSITION", "not object")
        exact_keys(transition, {"reason_code", "result", "when"}, "E_OWNER_TRANSITION_KEYS")
        require(transition["result"] in value["allowed_current_decisions"], "E_OWNER_TRANSITION_RESULT", "result")
    positive = [item for item in transitions if item["when"] == "POSITIVE_RUNTIME_DECISION_REQUESTED_IN_THIS_SCHEMA"]
    require(len(positive) == 1 and positive[0]["result"] == "REJECTED_FAIL_CLOSED", "E_OWNER_POSITIVE_TRANSITION", "positive request")
    return copy.deepcopy(value)


def _validate_downstream_gates(value: Any) -> list[dict[str, Any]]:
    require(type(value) is list, "E_DOWNSTREAM_GATES", "not list")
    require(sha256_value(value) == DOWNSTREAM_GATES_SHA256, "E_DOWNSTREAM_GATES_HASH", "catalog")
    require(len(value) == len(DOWNSTREAM_GATE_IDS), "E_DOWNSTREAM_GATES", "count")
    for row, gate_id in zip(value, DOWNSTREAM_GATE_IDS, strict=True):
        require(row == {"authorized": False, "gate_id": gate_id, "status": "SEPARATE_NOT_AUTHORIZED"}, "E_DOWNSTREAM_GATE", gate_id)
    return copy.deepcopy(value)


def _validate_fixture(fixture: Mapping[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Any], list[dict[str, Any]], BoundaryNonClaims]:
    exact_keys(
        fixture,
        {
            "date",
            "downstream_separate_gates",
            "expected",
            "nonclaims",
            "owner_decision_preregistration",
            "predecessor",
            "prerequisite_evidence_plan",
            "schema",
            "synthetic_only",
            "tracks",
        },
        "E_FIXTURE_KEYS",
    )
    require(fixture["schema"] == FIXTURE_SCHEMA, "E_FIXTURE_SCHEMA", "schema")
    require(fixture["date"] == "2026-07-16", "E_FIXTURE_DATE", "date")
    require(fixture["synthetic_only"] is True, "E_FIXTURE_SYNTHETIC", "flag")
    require(fixture["tracks"] == list(TRACKS), "E_TRACKS", "catalog")
    require(sha256_value(fixture["tracks"]) == TRACKS_SHA256, "E_TRACKS_HASH", "catalog")
    require(sha256_value(fixture["predecessor"]) == PREDECESSOR_BINDING_SHA256, "E_PREDECESSOR_BINDING", "binding")
    predecessor = fixture["predecessor"]
    require(predecessor["integration_commit"] == "c9c50917687c7715b031a6bfe8dd7801bfd737ee", "E_PREDECESSOR_INTEGRATION", "commit")
    require(predecessor["source_commit"] == "9a0f50ec378385be9ff0eda62a46666d04e04a97", "E_PREDECESSOR_SOURCE", "commit")
    require(predecessor["manifest_sha256"] == PREDECESSOR_MANIFEST_SHA256, "E_PREDECESSOR_BINDING", "manifest hash")
    expected = fixture["expected"]
    require(type(expected) is dict, "E_EXPECTED", "not object")
    require(sha256_value(expected) == EXPECTED_SHA256, "E_EXPECTED_HASH", "oracle")
    plan = _validate_plan(fixture["prerequisite_evidence_plan"])
    owner = _validate_owner_preregistration(fixture["owner_decision_preregistration"], plan)
    downstream = _validate_downstream_gates(fixture["downstream_separate_gates"])
    nonclaims_raw = fixture["nonclaims"]
    require(type(nonclaims_raw) is dict, "E_NONCLAIMS", "not object")
    require(sha256_value(nonclaims_raw) == NONCLAIMS_SHA256, "E_NONCLAIMS_HASH", "frozen nonclaims drift")
    nonclaims = BoundaryNonClaims.from_mapping(nonclaims_raw)
    require(nonclaims.all_explicit(), "E_NONCLAIMS", "nonclaim escalation")
    return plan, owner, downstream, nonclaims


class RuntimePrerequisiteEvidencePlanReviewer:
    """Review an offline evidence plan and fail-closed decision preregistration."""

    def review(
        self,
        predecessor_manifest: Mapping[str, Any],
        fixture: Mapping[str, Any],
    ) -> dict[str, Any]:
        _validate_predecessor_manifest(predecessor_manifest)
        plan, owner, downstream, nonclaims = _validate_fixture(fixture)
        evidence_present = sum(row["evidence_present"] is True for row in plan)
        satisfied = sum(row["satisfied"] is True for row in plan)
        expected = fixture["expected"]
        owner_classes = {row["owner_class"] for row in plan}
        evidence_classes = {row["evidence_class"] for row in plan}
        require(evidence_present == expected["evidence_items_present"] == 0, "E_EVIDENCE_PRESENT", "count")
        require(satisfied == expected["prerequisites_satisfied"] == 0, "E_PREREQUISITE_SATISFIED", "count")
        require(len(owner_classes) == expected["distinct_owner_class_count"] == 15, "E_OWNER_CLASS_COUNT", "count")
        require(len(evidence_classes) == expected["distinct_evidence_class_count"] == 16, "E_EVIDENCE_CLASS_COUNT", "count")
        require(len(downstream) == expected["downstream_separate_gate_count"] == 4, "E_DOWNSTREAM_COUNT", "count")
        require(len(nonclaims.as_dict()) == expected["nonclaim_field_count"] == 31, "E_NONCLAIM_COUNT", "count")
        require(owner["current_decision_recorded"] == expected["owner_decision_recorded"] is False, "E_OWNER_RECORDED", "state")
        require(owner["positive_decision_representable"] == expected["positive_decision_representable"] is False, "E_OWNER_POSITIVE", "state")

        receipt: dict[str, Any] = {
            "all_nonclaims_explicit": nonclaims.all_explicit(),
            "allowed_current_decision_count": len(owner["allowed_current_decisions"]),
            "condition_outputs": 0,
            "content_sha256": "0" * 64,
            "credentials_accessed": 0,
            "date": "2026-07-16",
            "decision": DECISION,
            "distinct_evidence_class_count": len(evidence_classes),
            "distinct_owner_class_count": len(owner_classes),
            "downstream_separate_gate_count": len(downstream),
            "downstream_separate_gates": downstream,
            "downstream_separate_gates_sha256": sha256_value(downstream),
            "evidence_items_present": evidence_present,
            "evidence_plan_is_evidence_receipt": False,
            "evidence_plan_preregistered": True,
            "evidence_prerequisite_count": len(plan) - 1,
            "experiment_rows": 0,
            "fail_closed_transition_count": len(owner["fail_closed_transitions"]),
            "next_unit": NEXT_UNIT,
            "nonclaim_field_count": len(nonclaims.as_dict()),
            "nonclaims": nonclaims.as_dict(),
            "nonclaims_sha256": sha256_value(nonclaims.as_dict()),
            "output_permits": 0,
            "owner_decision_current_state": owner["current_state"],
            "owner_decision_preregistered": True,
            "owner_decision_preregistration": owner,
            "owner_decision_preregistration_sha256": sha256_value(owner),
            "owner_decision_prerequisite_count": 1,
            "owner_decision_recorded": owner["current_decision_recorded"],
            "paid_resources_provisioned": 0,
            "positive_decision_representable": owner["positive_decision_representable"],
            "predecessor_manifest_sha256": sha256_value(predecessor_manifest),
            "prerequisite_evidence_plan": plan,
            "prerequisite_evidence_plan_sha256": sha256_value(plan),
            "prerequisite_plan_count": len(plan),
            "prerequisites_missing": len(plan) - satisfied,
            "prerequisites_satisfied": satisfied,
            "preregistration_is_runtime_admission": False,
            "preregistration_receipt_is_execution_authority": False,
            "preregistration_receipt_is_output_permit": False,
            "provider_calls": 0,
            "receipt_is_evidence_receipt": False,
            "runtime_admission_granted": False,
            "runtime_admission_ready": False,
            "runtime_authority": False,
            "runtime_rows": 0,
            "schema": RECEIPT_SCHEMA,
            "side_effects_unlocked": "NONE",
            "status": STATUS,
            "tracks_preregistered": len(TRACKS),
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
    "tracks_preregistered",
    "prerequisite_plan_count",
    "evidence_prerequisite_count",
    "owner_decision_prerequisite_count",
    "distinct_owner_class_count",
    "distinct_evidence_class_count",
    "evidence_items_present",
    "prerequisites_satisfied",
    "prerequisites_missing",
    "evidence_plan_preregistered",
    "owner_decision_preregistered",
    "owner_decision_current_state",
    "owner_decision_recorded",
    "positive_decision_representable",
    "allowed_current_decision_count",
    "fail_closed_transition_count",
    "downstream_separate_gate_count",
    "nonclaim_field_count",
    "all_nonclaims_explicit",
    "provider_calls",
    "wire_attempts",
    "credentials_accessed",
    "paid_resources_provisioned",
    "runtime_rows",
    "experiment_rows",
    "condition_outputs",
    "output_permits",
    "runtime_admission_ready",
    "runtime_admission_granted",
    "runtime_authority",
    "evidence_plan_is_evidence_receipt",
    "receipt_is_evidence_receipt",
    "preregistration_receipt_is_execution_authority",
    "preregistration_receipt_is_output_permit",
    "preregistration_is_runtime_admission",
    "side_effects_unlocked",
    "predecessor_manifest_sha256",
    "prerequisite_evidence_plan_sha256",
    "owner_decision_preregistration_sha256",
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
        rendered = "true" if value is True else "false" if value is False else str(value)
        require("\t" not in rendered and "\n" not in rendered, "E_TSV_VALUE", field)
        rows.append(f"{field}\t{rendered}")
    return "\n".join(rows) + "\n"
