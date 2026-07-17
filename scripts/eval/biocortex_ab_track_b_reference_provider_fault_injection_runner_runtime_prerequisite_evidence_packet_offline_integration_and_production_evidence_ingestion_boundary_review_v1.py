#!/usr/bin/env python3
"""Pure offline aggregate and future production-ingestion boundary reviewer.

This module statically reuses the frozen predecessor public validator-double
APIs.  It accepts only a closed-world synthetic KAT aggregate request.  It has
no production-ingestion or evidence-acceptance API and performs no file,
environment, ambient-clock, process, network, provider, credential, random,
entropy, or mutable-state I/O.  A conformant aggregate remains synthetic test
data and cannot satisfy a runtime prerequisite or exercise owner authority.
"""

from __future__ import annotations

import copy
import hashlib
import json
from typing import Any, Iterable, Mapping

from biocortex_ab_track_b_reference_provider_fault_injection_runner_runtime_prerequisite_evidence_packet_schemas_and_offline_validator_doubles_v1 import (
    EvidencePacketReviewError,
    RuntimePrerequisiteEvidencePacketSchemaReviewer,
)


FIXTURE_SCHEMA = (
    "agent_bridge.biocortex_ab_track_b_reference_provider_fault_injection_runner_"
    "runtime_prerequisite_evidence_packet_offline_integration_and_production_"
    "evidence_ingestion_boundary_review_v1.synthetic.v0"
)
REQUEST_SCHEMA = (
    "agent_bridge.biocortex_ab_track_b_reference_provider_fault_injection_runner_"
    "runtime_prerequisite_evidence_packet_offline_integration_v1.request.v0"
)
RECEIPT_SCHEMA = (
    "agent_bridge.biocortex_ab_track_b_reference_provider_fault_injection_runner_"
    "runtime_prerequisite_evidence_packet_offline_integration_and_production_"
    "evidence_ingestion_boundary_review_v1.receipt.v0"
)
MODE = "SYNTHETIC_FIXED_KAT_ONLY"
DATE = "2026-07-17"
STATUS = (
    "REFERENCE_PROVIDER_FAULT_INJECTION_RUNNER_V1_RUNTIME_PREREQUISITE_"
    "EVIDENCE_PACKET_OFFLINE_AGGREGATE_INTEGRATED_PRODUCTION_INGESTION_"
    "BOUNDARY_REVIEWED_RUNTIME_EVIDENCE_ZERO_NO_AUTHORITY"
)
DECISION = (
    "OFFLINE_AGGREGATE_CONFORMANT_PRODUCTION_EVIDENCE_INGESTION_BOUNDARY_"
    "FROZEN_RUNTIME_EVIDENCE_ZERO_FAIL_CLOSED"
)
NEXT_UNIT = (
    "REFERENCE_PROVIDER_MANAGED_AND_SELF_HOSTED_FAULT_INJECTION_RUNNER_V1_"
    "PRODUCTION_EVIDENCE_INGESTION_IMPLEMENTATION_AUTHORITY_AND_RESOURCE_"
    "BINDING_DECISION"
)
REQUEST_ID_DOMAIN = (
    "AB_TRACK_B_RUNTIME_PREREQUISITE_SYNTHETIC_OFFLINE_AGGREGATE_REQUEST_V1"
)
SYNTHETIC_PACKET_SET_CANONICALIZATION = (
    "AGENT_BRIDGE_CANONICAL_JSON_V1_SORTED_KEYS_INDENT_2_LF"
)
SYNTHETIC_PACKET_SET_DOMAIN = (
    "AB_TRACK_B_RUNTIME_PREREQUISITE_SYNTHETIC_PACKET_SET_V1"
)
SYNTHETIC_PACKET_SET_SHA256 = (
    "56e9343e7e31e8a80d1a56f7ab34fc11e15412d97620c031a06f740ae29ea460"
)
PREDECESSOR_RECEIPT_CONTENT_SHA256 = (
    "c6ea1a4872acacf1faff3695598d66e1cb0096f6574239199128225dab80e3c4"
)
PREDECESSOR_EVIDENCE_SCHEMA_CANONICAL_SHA256 = (
    "a8b66deefe134afdb17e624bc821aba90c9d5a2490433f6a65276a6bfa63eaac"
)
PREDECESSOR_OWNER_SCHEMA_CANONICAL_SHA256 = (
    "99f2737282f2df568792ced2f2e16820f74eb2820bcbe240eaa97c03cc197086"
)
PREDECESSOR_SCHEMA_FIXTURE_CANONICAL_SHA256 = (
    "236839e4a8e831a84ef11c089cbd624152ddb456e583c2c414ece6c5ebb09f97"
)
FIXTURE_SHA256 = "3aee2bc2f27290e9a57789d434f4373609b720f7ee1d963871fd99a613f55ff6"

TRACKS = (
    "MANAGED_SPANNER_CLOUD_KMS",
    "SELF_HOSTED_ETCD_OPENBAO",
)
DOWNSTREAM_GATES = (
    "CONDITION_OUTPUT_GATE",
    "OUTPUT_PERMIT_GATE",
    "SCIENTIFIC_CLAIM_GATE",
    "APPLICATION_CLAIM_GATE",
)
TRUST_DOMAINS = (
    "AB_TRACK_B_RUNTIME_PREREQUISITE_SYNTHETIC_PACKET_SET_V1",
    "AB_TRACK_B_RUNTIME_PREREQUISITE_PRODUCTION_EVIDENCE_ENVELOPE_SIGNATURE_V1",
    "AB_TRACK_B_RUNTIME_PREREQUISITE_PRODUCTION_REVIEW_SUBJECT_SET_V1",
    "AB_TRACK_B_RUNTIME_PREREQUISITE_PRODUCTION_OWNER_HANDOFF_SET_V1",
    "AB_TRACK_B_RUNTIME_PREREQUISITE_PRODUCTION_OWNER_DECISION_SIGNATURE_V1",
)
CONTROL_IDS = (
    "FRAME_AND_PARSE",
    "SYNTHETIC_PRODUCTION_MODE_SEPARATION",
    "BOOTSTRAP_TRUST_AUTHENTICATION",
    "SIGNER_ROLE_SCOPE_AUTHORIZATION",
    "TRACK_SUBJECT_BINDING",
    "QUARANTINE_CUSTODY",
    "SEMANTIC_VALIDATION",
    "TRUSTED_TIME_FRESHNESS",
    "DURABLE_REPLAY_CAS",
    "VALIDATION_RECEIPT_BINDING",
    "INDEPENDENT_REVIEW_BINDING",
    "OWNER_HANDOFF_SET",
    "OWNER_IDENTITY_DECISION",
    "DOWNSTREAM_GATE_SEPARATION",
)
OWNER_HANDOFF_REQUIREMENT_IDS = (
    "ALL_FIFTEEN_PRODUCTION_VALIDATED",
    "PACKET15_BINDS_ORDERED_ONE_TO_FOURTEEN",
    "OWNER_SET_BINDS_ORDERED_ONE_TO_FIFTEEN",
    "SAME_VALIDATED_SET_HASH",
    "TRUSTED_FINAL_VALIDATION_TIME",
    "OWNER_WINDOW_LESS_THAN_1800_SECONDS",
    "EFFECTIVE_DEADLINE_IS_MINIMUM_EXPIRY",
    "DECISION_TIME_RECHECKS_PASS",
    "OWNER_IDENTITY_AND_ROLE_AUTHENTICATED",
    "SEPARATE_POSITIVE_OWNER_SCHEMA_REQUIRED",
)
FRESHNESS_IDS = (
    "EXACT_BINDING_ONLY",
    "PROVIDER_IDENTITY_MAX_86400",
    "CREDENTIAL_LIFECYCLE_MAX_3600",
    "RESOURCE_BUDGET_MAX_86400",
    "TRUSTED_TIME_MAX_300",
    "SAFETY_STOP_DRILL_MAX_604800",
    "RETENTION_CLEANUP_MAX_604800",
    "OWNER_HANDOFF_MAX_1800",
)


class OfflineIntegrationBoundaryReviewError(ValueError):
    """Fail-closed review error with a stable reason code."""


def require(condition: bool, code: str, message: str) -> None:
    if not condition:
        raise OfflineIntegrationBoundaryReviewError(f"{code}: {message}")


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


def without_key(value: Mapping[str, Any], key: str) -> dict[str, Any]:
    result = copy.deepcopy(dict(value))
    del result[key]
    return result


def is_sha256(value: Any) -> bool:
    return (
        type(value) is str
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def _derive_synthetic_packet_set_sha256(packet_ids: list[str]) -> str:
    require(
        len(packet_ids) == 15
        and len(set(packet_ids)) == 15
        and all(is_sha256(item) for item in packet_ids),
        "E_AGGREGATE_SET_HASH",
        "ordered packet ids",
    )
    return sha256_value(
        {
            "canonicalization": SYNTHETIC_PACKET_SET_CANONICALIZATION,
            "domain": SYNTHETIC_PACKET_SET_DOMAIN,
            "ordered_packet_id_sha256": packet_ids,
        }
    )


def _derive_request_id(request: Mapping[str, Any]) -> str:
    return sha256_value(
        {
            "domain": REQUEST_ID_DOMAIN,
            "request": without_key(request, "request_id_sha256"),
        }
    )


def _validate_boundary_fixture(fixture: Mapping[str, Any]) -> None:
    require(type(fixture) is dict, "E_BOUNDARY_FIXTURE", "not object")
    require(
        sha256_value(fixture) == FIXTURE_SHA256,
        "E_BOUNDARY_FIXTURE_HASH",
        "canonical fixture drift",
    )
    exact_keys(
        fixture,
        (
            "date",
            "downstream_separate_gates",
            "expected",
            "freshness_requirements",
            "nonclaims",
            "owner_handoff_requirements",
            "predecessor",
            "production_ingestion_controls",
            "schema",
            "synthetic_only",
            "threat_cases",
            "tracks",
            "trust_domains",
        ),
        "E_BOUNDARY_FIXTURE_KEYS",
    )
    require(fixture["schema"] == FIXTURE_SCHEMA, "E_BOUNDARY_FIXTURE_SCHEMA", "schema")
    require(fixture["date"] == DATE, "E_BOUNDARY_FIXTURE_DATE", "date")
    require(fixture["synthetic_only"] is True, "E_BOUNDARY_FIXTURE_MODE", "synthetic")
    require(fixture["tracks"] == list(TRACKS), "E_BOUNDARY_TRACKS", "tracks")
    require(
        fixture["downstream_separate_gates"] == list(DOWNSTREAM_GATES),
        "E_BOUNDARY_DOWNSTREAM_GATES",
        "gates",
    )

    predecessor = fixture["predecessor"]
    require(type(predecessor) is dict, "E_BOUNDARY_PREDECESSOR", "not object")
    expected_predecessor = {
        "evidence_schema_canonical_json_sha256": PREDECESSOR_EVIDENCE_SCHEMA_CANONICAL_SHA256,
        "evidence_schema_file_bytes_sha256": "121c66331f159539722acb8f173696811487d8b76b9da07ab9d83340e28277d3",
        "integration_commit": "3d03193b645ded944b10a310633be8d6a2c1ab1b",
        "owner_schema_canonical_json_sha256": PREDECESSOR_OWNER_SCHEMA_CANONICAL_SHA256,
        "owner_schema_file_bytes_sha256": "7845de2ac7d1f069fd550f5625a1593c0a093563acbe1be1855bf7df0f3d4436",
        "receipt_content_sha256": PREDECESSOR_RECEIPT_CONTENT_SHA256,
        "reviewer_file_bytes_sha256": "29a4b67049429c09981f1742f072a3fe382f381259fa238b69041b3d46939351",
        "schema_fixture_canonical_json_sha256": PREDECESSOR_SCHEMA_FIXTURE_CANONICAL_SHA256,
        "source_commit": "151c3294c92e79759401cf86e8f36263bbf17ade",
        "synthetic_packet_set_sha256": SYNTHETIC_PACKET_SET_SHA256,
    }
    require(predecessor == expected_predecessor, "E_BOUNDARY_PREDECESSOR", "binding")

    domains = fixture["trust_domains"]
    require(type(domains) is list and len(domains) == 5, "E_TRUST_DOMAIN_COUNT", "count")
    domain_keys = (
        "cross_domain_substitution_allowed",
        "domain_id",
        "offline_usable",
        "production_implemented",
        "purpose",
    )
    require(
        [row.get("domain_id") for row in domains] == list(TRUST_DOMAINS),
        "E_TRUST_DOMAIN_ORDER",
        "domain ids",
    )
    for index, row in enumerate(domains):
        require(type(row) is dict, "E_TRUST_DOMAIN", str(index))
        exact_keys(row, domain_keys, "E_TRUST_DOMAIN_KEYS")
        require(type(row["purpose"]) is str and row["purpose"], "E_TRUST_DOMAIN", "purpose")
        require(row["production_implemented"] is False, "E_TRUST_DOMAIN", "implemented")
        require(
            row["cross_domain_substitution_allowed"] is False,
            "E_TRUST_DOMAIN",
            "substitution",
        )
        require(
            row["offline_usable"] is (index == 0),
            "E_TRUST_DOMAIN",
            "offline usability",
        )

    controls = fixture["production_ingestion_controls"]
    require(type(controls) is list and len(controls) == 14, "E_CONTROL_COUNT", "count")
    control_keys = (
        "control_id",
        "implemented",
        "mandatory_check",
        "primary_failure_code",
        "required_future_artifact",
        "runtime_exercised",
        "satisfiable_by_offline",
        "stage_ordinal",
    )
    require(
        [row.get("control_id") for row in controls] == list(CONTROL_IDS),
        "E_CONTROL_ORDER",
        "control ids",
    )
    for ordinal, row in enumerate(controls, start=1):
        require(type(row) is dict, "E_CONTROL", str(ordinal))
        exact_keys(row, control_keys, "E_CONTROL_KEYS")
        require(row["stage_ordinal"] == ordinal, "E_CONTROL_ORDER", str(ordinal))
        for name in ("mandatory_check", "primary_failure_code", "required_future_artifact"):
            require(type(row[name]) is str and row[name], "E_CONTROL", name)
        for name in ("implemented", "runtime_exercised", "satisfiable_by_offline"):
            require(row[name] is False, "E_CONTROL_BOUNDARY", f"{ordinal}:{name}")

    threats = fixture["threat_cases"]
    require(type(threats) is list and len(threats) == 20, "E_THREAT_COUNT", "count")
    threat_keys = (
        "case_id",
        "expected_disposition",
        "expected_reason_code",
        "mutation",
        "threat_class",
    )
    require(
        [row.get("case_id") for row in threats]
        == [f"T{index:02d}" for index in range(1, 21)],
        "E_THREAT_ORDER",
        "case ids",
    )
    for row in threats:
        require(type(row) is dict, "E_THREAT", "not object")
        exact_keys(row, threat_keys, "E_THREAT_KEYS")
        require(
            row["expected_disposition"] == "REJECTED_FAIL_CLOSED",
            "E_THREAT_DISPOSITION",
            row["case_id"],
        )
        for name in ("expected_reason_code", "mutation", "threat_class"):
            require(type(row[name]) is str and row[name], "E_THREAT", name)

    owner_requirements = fixture["owner_handoff_requirements"]
    require(
        type(owner_requirements) is list and len(owner_requirements) == 10,
        "E_OWNER_HANDOFF_REQUIREMENT_COUNT",
        "count",
    )
    owner_keys = (
        "offline_substitution_allowed",
        "production_implemented",
        "requirement",
        "requirement_id",
        "satisfied",
    )
    require(
        [row.get("requirement_id") for row in owner_requirements]
        == list(OWNER_HANDOFF_REQUIREMENT_IDS),
        "E_OWNER_HANDOFF_REQUIREMENT_ORDER",
        "ids",
    )
    for row in owner_requirements:
        require(type(row) is dict, "E_OWNER_HANDOFF_REQUIREMENT", "not object")
        exact_keys(row, owner_keys, "E_OWNER_HANDOFF_REQUIREMENT_KEYS")
        require(type(row["requirement"]) is str and row["requirement"], "E_OWNER_HANDOFF_REQUIREMENT", "text")
        for name in ("offline_substitution_allowed", "production_implemented", "satisfied"):
            require(row[name] is False, "E_OWNER_HANDOFF_BOUNDARY", name)

    freshness = fixture["freshness_requirements"]
    require(type(freshness) is list and len(freshness) == 8, "E_FRESHNESS_COUNT", "count")
    freshness_keys = (
        "additional_requirement",
        "decision_recheck_required",
        "freshness_id",
        "max_age_seconds",
        "prerequisite_ids",
        "production_implemented",
        "real_currentness_proved",
    )
    require(
        [row.get("freshness_id") for row in freshness] == list(FRESHNESS_IDS),
        "E_FRESHNESS_ORDER",
        "ids",
    )
    expected_max_age = (None, 86400, 3600, 86400, 300, 604800, 604800, 1800)
    expected_recheck = (False, True, True, True, True, False, False, True)
    for index, row in enumerate(freshness):
        require(type(row) is dict, "E_FRESHNESS", str(index))
        exact_keys(row, freshness_keys, "E_FRESHNESS_KEYS")
        require(type(row["prerequisite_ids"]) is list and row["prerequisite_ids"], "E_FRESHNESS", "ids")
        require(row["max_age_seconds"] == expected_max_age[index], "E_FRESHNESS", "max age")
        require(
            row["decision_recheck_required"] is expected_recheck[index],
            "E_FRESHNESS",
            "recheck",
        )
        require(type(row["additional_requirement"]) is str and row["additional_requirement"], "E_FRESHNESS", "requirement")
        require(row["production_implemented"] is False, "E_FRESHNESS", "implemented")
        require(row["real_currentness_proved"] is False, "E_FRESHNESS", "currentness")

    nonclaims = fixture["nonclaims"]
    require(type(nonclaims) is dict and len(nonclaims) == 52, "E_NONCLAIM_COUNT", "count")
    for name, value in nonclaims.items():
        if name == "side_effects_unlocked":
            require(value == "NONE", "E_NONCLAIM_VALUE", name)
        else:
            require(type(value) is bool and value is False, "E_NONCLAIM_VALUE", name)

    expected = fixture["expected"]
    require(type(expected) is dict, "E_EXPECTED", "not object")
    exact_keys(
        expected,
        (
            "aggregate_case_result_count",
            "aggregate_evidence_packet_count",
            "downstream_gate_count",
            "freshness_requirement_count",
            "nonclaim_field_count",
            "offline_double_conformant_count",
            "owner_handoff_eligible",
            "owner_handoff_requirement_count",
            "owner_packet_count",
            "production_ingestion_control_count",
            "production_ingestion_controls_implemented",
            "production_validated_evidence_items",
            "real_evidence_items_present",
            "runtime_prerequisites_satisfied",
            "synthetic_packet_set_sha256",
            "threat_case_count",
            "tracks_represented",
            "trust_domain_count",
            "valid_owner_state_reason_combination_count",
        ),
        "E_EXPECTED_KEYS",
    )
    exact_expected = {
        "aggregate_case_result_count": 16,
        "aggregate_evidence_packet_count": 15,
        "downstream_gate_count": 4,
        "freshness_requirement_count": 8,
        "nonclaim_field_count": 52,
        "offline_double_conformant_count": 16,
        "owner_handoff_eligible": False,
        "owner_handoff_requirement_count": 10,
        "owner_packet_count": 1,
        "production_ingestion_control_count": 14,
        "production_ingestion_controls_implemented": 0,
        "production_validated_evidence_items": 0,
        "real_evidence_items_present": 0,
        "runtime_prerequisites_satisfied": 0,
        "synthetic_packet_set_sha256": SYNTHETIC_PACKET_SET_SHA256,
        "threat_case_count": 20,
        "tracks_represented": 2,
        "trust_domain_count": 5,
        "valid_owner_state_reason_combination_count": 6,
    }
    require(expected == exact_expected, "E_EXPECTED", "boundary expectations")


class RuntimePrerequisiteEvidencePacketOfflineIntegrationBoundaryReviewer:
    """Integrate exact synthetic KAT packets and review a future boundary."""

    def __init__(self) -> None:
        self._predecessor = RuntimePrerequisiteEvidencePacketSchemaReviewer()

    def known_answer_aggregate_request(
        self,
        predecessor_manifest: Mapping[str, Any],
        predecessor_fixture: Mapping[str, Any],
        evidence_schema: Mapping[str, Any],
        owner_schema: Mapping[str, Any],
        schema_fixture: Mapping[str, Any],
        boundary_fixture: Mapping[str, Any],
    ) -> dict[str, Any]:
        """Return the one exact synthetic aggregate request; no real evidence."""

        _validate_boundary_fixture(boundary_fixture)
        suite = self._predecessor.known_answer_packet_suite(
            predecessor_manifest,
            predecessor_fixture,
            evidence_schema,
            owner_schema,
            schema_fixture,
        )
        request: dict[str, Any] = {
            "evidence_packets": copy.deepcopy(suite["evidence_packets"]),
            "mode": MODE,
            "owner_packet": copy.deepcopy(suite["owner_packet"]),
            "request_id_sha256": "0" * 64,
            "schema": REQUEST_SCHEMA,
            "schema_version": 1,
            "synthetic_context_sha256": sha256_value(
                schema_fixture["synthetic_context"]
            ),
        }
        request["request_id_sha256"] = _derive_request_id(request)
        return request

    def validate_aggregate_request(
        self,
        predecessor_manifest: Mapping[str, Any],
        predecessor_fixture: Mapping[str, Any],
        evidence_schema: Mapping[str, Any],
        owner_schema: Mapping[str, Any],
        schema_fixture: Mapping[str, Any],
        boundary_fixture: Mapping[str, Any],
        aggregate_request: Mapping[str, Any],
    ) -> dict[str, Any]:
        """Validate one synthetic-only aggregate and return a zero-authority receipt."""

        _validate_boundary_fixture(boundary_fixture)
        require(type(aggregate_request) is dict, "E_AGGREGATE_REQUEST", "not object")
        exact_keys(
            aggregate_request,
            (
                "evidence_packets",
                "mode",
                "owner_packet",
                "request_id_sha256",
                "schema",
                "schema_version",
                "synthetic_context_sha256",
            ),
            "E_AGGREGATE_KEYS",
        )
        require(aggregate_request["schema"] == REQUEST_SCHEMA, "E_AGGREGATE_SCHEMA", "schema")
        require(
            type(aggregate_request["schema_version"]) is int
            and aggregate_request["schema_version"] == 1,
            "E_AGGREGATE_SCHEMA",
            "version",
        )
        require(aggregate_request["mode"] == MODE, "E_AGGREGATE_MODE", "synthetic mode only")
        require(
            aggregate_request["synthetic_context_sha256"]
            == sha256_value(schema_fixture["synthetic_context"]),
            "E_AGGREGATE_CONTEXT",
            "context binding",
        )
        require(
            aggregate_request["request_id_sha256"]
            == _derive_request_id(aggregate_request),
            "E_AGGREGATE_REQUEST_ID",
            "content-derived request id",
        )

        predecessor_receipt = self._predecessor.review(
            predecessor_manifest,
            predecessor_fixture,
            evidence_schema,
            owner_schema,
            schema_fixture,
        )
        require(
            predecessor_receipt["content_sha256"] == PREDECESSOR_RECEIPT_CONTENT_SHA256,
            "E_PREDECESSOR_RECEIPT",
            "content binding",
        )
        require(
            sha256_value(evidence_schema) == PREDECESSOR_EVIDENCE_SCHEMA_CANONICAL_SHA256,
            "E_PREDECESSOR_EVIDENCE_SCHEMA",
            "canonical binding",
        )
        require(
            sha256_value(owner_schema) == PREDECESSOR_OWNER_SCHEMA_CANONICAL_SHA256,
            "E_PREDECESSOR_OWNER_SCHEMA",
            "canonical binding",
        )
        require(
            sha256_value(schema_fixture) == PREDECESSOR_SCHEMA_FIXTURE_CANONICAL_SHA256,
            "E_PREDECESSOR_SCHEMA_FIXTURE",
            "canonical binding",
        )

        evidence_packets = aggregate_request["evidence_packets"]
        require(
            type(evidence_packets) is list and len(evidence_packets) == 15,
            "E_AGGREGATE_CARDINALITY",
            "fifteen evidence packets",
        )
        plan = predecessor_fixture["prerequisite_evidence_plan"]
        expected_ids = [row["prerequisite_id"] for row in plan[:15]]
        actual_ids = []
        packet_ids = []
        for packet in evidence_packets:
            require(type(packet) is dict, "E_AGGREGATE_PACKET", "not object")
            actual_ids.append(packet.get("prerequisite_id"))
            packet_ids.append(packet.get("packet_id_sha256"))
        require(actual_ids == expected_ids, "E_AGGREGATE_ORDER", "prerequisite order")
        require(
            all(is_sha256(item) for item in packet_ids),
            "E_AGGREGATE_PACKET_ID",
            "packet id format",
        )
        require(len(set(packet_ids)) == 15, "E_AGGREGATE_DUPLICATE", "packet ids")

        case_results = []
        try:
            for packet_index, packet in enumerate(evidence_packets):
                case_results.append(
                    self._predecessor.validate_evidence_packet_double(
                        predecessor_manifest,
                        predecessor_fixture,
                        evidence_schema,
                        owner_schema,
                        schema_fixture,
                        packet_index,
                        packet,
                    )
                )
            owner_packet = aggregate_request["owner_packet"]
            require(type(owner_packet) is dict, "E_AGGREGATE_OWNER", "not object")
            case_results.append(
                self._predecessor.validate_owner_packet_double(
                    predecessor_manifest,
                    predecessor_fixture,
                    evidence_schema,
                    owner_schema,
                    schema_fixture,
                    owner_packet,
                )
            )
        except EvidencePacketReviewError as error:
            raise OfflineIntegrationBoundaryReviewError(
                f"E_AGGREGATE_PREDECESSOR_VALIDATION: {error}"
            ) from error
        require(len(case_results) == 16, "E_AGGREGATE_RESULT_COUNT", "sixteen results")

        packet_set_sha256 = _derive_synthetic_packet_set_sha256(packet_ids)
        require(
            packet_set_sha256 == SYNTHETIC_PACKET_SET_SHA256,
            "E_AGGREGATE_SET_HASH",
            "frozen synthetic packet set",
        )
        nonclaims = boundary_fixture["nonclaims"]
        controls = boundary_fixture["production_ingestion_controls"]
        threats = boundary_fixture["threat_cases"]
        freshness = boundary_fixture["freshness_requirements"]
        owner_requirements = boundary_fixture["owner_handoff_requirements"]
        domains = boundary_fixture["trust_domains"]
        receipt: dict[str, Any] = {
            "aggregate_case_result_count": len(case_results),
            "aggregate_request_id_sha256": aggregate_request["request_id_sha256"],
            "all_nonclaims_explicit": True,
            "boundary_fixture_sha256": FIXTURE_SHA256,
            "case_results": case_results,
            "case_results_sha256": sha256_value(case_results),
            "content_sha256": "0" * 64,
            "date": DATE,
            "decision": DECISION,
            "dependency_topology_conformant": True,
            "downstream_gates_authorized": 0,
            "downstream_separate_gate_count": len(DOWNSTREAM_GATES),
            "evidence_packet_count": len(evidence_packets),
            "freshness_arithmetic_conformant_count": 15,
            "freshness_requirement_count": len(freshness),
            "mode": MODE,
            "next_unit": NEXT_UNIT,
            "nonclaim_field_count": len(nonclaims),
            "nonclaims_sha256": sha256_value(nonclaims),
            "offline_double_conformant_count": len(case_results),
            "ordered_packet_id_sha256": packet_ids,
            "owner_decision_recorded": False,
            "owner_handoff_eligible": False,
            "owner_handoff_requirement_count": len(owner_requirements),
            "owner_handoff_set_sha256": "NONE",
            "owner_identity_bound": False,
            "owner_packet_count": 1,
            "positive_decision_representable": False,
            "predecessor_receipt_content_sha256": predecessor_receipt["content_sha256"],
            "production_evidence_ingestion_implemented": False,
            "production_ingestion_control_count": len(controls),
            "production_ingestion_controls_implemented": 0,
            "production_review_subject_set_sha256": "NONE",
            "production_validated_evidence_items": 0,
            "real_currentness_proved": False,
            "real_evidence_items_present": 0,
            "runtime_admission_granted": False,
            "runtime_admission_ready": False,
            "runtime_authority": False,
            "runtime_evidence_accepted": 0,
            "runtime_prerequisites_satisfied": 0,
            "schema": RECEIPT_SCHEMA,
            "side_effects_unlocked": "NONE",
            "status": STATUS,
            "synthetic_packet_set_sha256": packet_set_sha256,
            "threat_case_count": len(threats),
            "track_separation_conformant": True,
            "tracks_represented": len(TRACKS),
            "trust_domain_count": len(domains),
            "valid_owner_state_reason_combination_count": 6,
        }
        content = copy.deepcopy(receipt)
        del content["content_sha256"]
        receipt["content_sha256"] = sha256_value(content)
        return receipt

    def review(
        self,
        predecessor_manifest: Mapping[str, Any],
        predecessor_fixture: Mapping[str, Any],
        evidence_schema: Mapping[str, Any],
        owner_schema: Mapping[str, Any],
        schema_fixture: Mapping[str, Any],
        boundary_fixture: Mapping[str, Any],
    ) -> dict[str, Any]:
        """Generate then validate the exact synthetic aggregate known answer."""

        request = self.known_answer_aggregate_request(
            predecessor_manifest,
            predecessor_fixture,
            evidence_schema,
            owner_schema,
            schema_fixture,
            boundary_fixture,
        )
        return self.validate_aggregate_request(
            predecessor_manifest,
            predecessor_fixture,
            evidence_schema,
            owner_schema,
            schema_fixture,
            boundary_fixture,
            request,
        )


TSV_FIELDS = (
    "schema",
    "status",
    "decision",
    "date",
    "mode",
    "next_unit",
    "tracks_represented",
    "evidence_packet_count",
    "owner_packet_count",
    "aggregate_case_result_count",
    "offline_double_conformant_count",
    "freshness_arithmetic_conformant_count",
    "dependency_topology_conformant",
    "track_separation_conformant",
    "synthetic_packet_set_sha256",
    "case_results_sha256",
    "aggregate_request_id_sha256",
    "predecessor_receipt_content_sha256",
    "boundary_fixture_sha256",
    "trust_domain_count",
    "production_ingestion_control_count",
    "production_ingestion_controls_implemented",
    "threat_case_count",
    "freshness_requirement_count",
    "owner_handoff_requirement_count",
    "valid_owner_state_reason_combination_count",
    "nonclaim_field_count",
    "nonclaims_sha256",
    "all_nonclaims_explicit",
    "real_evidence_items_present",
    "production_validated_evidence_items",
    "runtime_evidence_accepted",
    "runtime_prerequisites_satisfied",
    "real_currentness_proved",
    "production_evidence_ingestion_implemented",
    "production_review_subject_set_sha256",
    "owner_handoff_set_sha256",
    "owner_handoff_eligible",
    "owner_identity_bound",
    "owner_decision_recorded",
    "positive_decision_representable",
    "runtime_admission_ready",
    "runtime_admission_granted",
    "runtime_authority",
    "downstream_separate_gate_count",
    "downstream_gates_authorized",
    "side_effects_unlocked",
    "content_sha256",
)


def render_tsv(receipt: Mapping[str, Any]) -> str:
    """Render the scalar receipt oracle; nested results stay hash-bound."""

    exact_keys(
        receipt,
        set(TSV_FIELDS) | {"case_results", "ordered_packet_id_sha256"},
        "E_RECEIPT_KEYS",
    )
    lines = []
    for field in TSV_FIELDS:
        require(field in receipt, "E_TSV_FIELD", field)
        value = receipt[field]
        require(type(value) in (str, int, bool), "E_TSV_VALUE", field)
        if type(value) is bool:
            rendered = "true" if value else "false"
        else:
            rendered = str(value)
        lines.append(f"{field}\t{rendered}")
    return "\n".join(lines) + "\n"
