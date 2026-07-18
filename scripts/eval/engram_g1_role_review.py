#!/usr/bin/env python3
"""Validate the G1.2 role-review and application-owner decision chain.

This gate sits between the G1.1 role packet and any private corpus assembly.
It checks salted reviewer commitments, reviewer/holder separation, chronology,
packet-byte bindings, and an exact proposed assembly scope. It does not
authenticate people or appointment evidence. Synthetic packets exercise the
contract but can never grant authority. Real packets must remain untracked
below the repository ``data/`` tree.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import engram_g1_freeze_preflight as freeze_preflight
from engram_g1_corpus_design import (
    InputError,
    read_json,
    reject_raw_fields,
    require_bool,
    require_exact_fields,
    require_exact_value,
    require_int,
    require_label,
    require_object,
    require_sha256,
    sha256_bytes,
)


CONTRACT_SCHEMA = "agent_bridge.engram_g1_role_review_contract.v1"
CONTRACT_RECEIPT_SCHEMA = "agent_bridge.engram_g1_role_review_contract_receipt.v1"
CONTRACT_ID = "engram_g1_role_review_20260718"
CONTRACT_SHA256 = "842a86010b61a030993d37e6cc2b06206315a22a5b319c79dfaf07ed32522c09"
REVIEW_PACKET_SCHEMA = "agent_bridge.engram_g1_role_review_packet.v1"
REVIEW_RECEIPT_SCHEMA = "agent_bridge.engram_g1_role_review_receipt.v1"
OWNER_DECISION_PACKET_SCHEMA = "agent_bridge.engram_g1_role_owner_decision_packet.v1"
OWNER_DECISION_RECEIPT_SCHEMA = "agent_bridge.engram_g1_role_owner_decision_receipt.v1"

PREDECESSOR_COMMIT = "3256fe024c2a280bcd4ac0fee4ff79563c0cc36a"
PREDECESSOR_CONTRACT_ID = "engram_g1_freeze_preflight_20260718"
PREDECESSOR_CONTRACT_SHA256 = (
    "5d4835fa2aa404224b98e7a60574121118051d771079f5a0422ab5839564e94a"
)
PREDECESSOR_VALIDATOR_SHA256 = (
    "f276765f22ee5b2f69e24cf7a79bd9a30e8291f900973d89c06f17d1d0468cdc"
)

EVIDENCE_CLASSES = {"synthetic_contract_test", "consumer_owned_real"}
REVIEW_DECISIONS = {"approve", "reject"}
OWNER_DECISIONS = {
    "endorse_private_corpus_assembly_for_authentication",
    "reject_role_roster",
}

EXPECTED_PROPOSED_ASSEMBLY_SCOPE = {
    "executor_role": "consumer_curator",
    "custody_role": "sealed_evaluator_custodian",
    "permitted_actions": [
        "create_private_corpus_intake_under_ignored_data",
        "perform_read_only_baseline_replay_on_disposable_snapshots",
        "prepare_hash_only_manifest_for_freeze_review",
    ],
    "maximum_intake_episode_groups": 36,
    "candidate_lane_may_execute": False,
    "writes_live_store": False,
    "mutates_retrieval_order": False,
    "grants_corpus_freeze": False,
    "grants_candidate_implementation": False,
    "grants_biocortex_execution": False,
    "grants_runtime_promotion": False,
    "currently_authorized": False,
    "requires_authenticated_owner_and_auditor_evidence": True,
}

EXPECTED_BOUNDARIES = {
    "observes_real_role_evidence": False,
    "assigns_real_role_holders": False,
    "current_private_corpus_assembly_authority": False,
    "g1_corpus_freeze_authority": False,
    "candidate_implementation_authority": False,
    "biocortex_experiment_execution_authority": False,
    "retrieval_order_mutation_authority": False,
    "live_store_write_authority": False,
    "runtime_promotion_authority": False,
}

RAW_IDENTITY_FIELDS = {
    "address",
    "contact",
    "email",
    "handle",
    "identity",
    "name",
    "person",
    "phone",
    "username",
}


def require_nonzero_sha256(value: Any, path: str) -> str:
    digest = require_sha256(value, path)
    if digest == "0" * 64:
        raise InputError(f"{path} must not be a placeholder")
    return digest


def reject_private_commitment_alias(
    identifier: str, private_values: set[str], path: str
) -> None:
    if identifier in private_values:
        raise InputError(f"{path} must not alias a private commitment or receipt")


def reject_raw_identities(value: Any, path: str) -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            if key.lower() in RAW_IDENTITY_FIELDS:
                raise InputError(f"{path}.{key} is a forbidden raw-identity field")
            reject_raw_identities(child, f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            reject_raw_identities(child, f"{path}[{index}]")


def validate_contract(value: dict[str, Any], raw: bytes) -> dict[str, Any]:
    reject_raw_fields(value)
    reject_raw_identities(value, "contract")
    if sha256_bytes(raw) != CONTRACT_SHA256:
        raise InputError("role-review contract bytes do not match the registered v1")
    require_exact_fields(
        value,
        {
            "schema",
            "contract_id",
            "stage",
            "predecessor",
            "role_review",
            "owner_decision",
            "proposed_assembly_scope",
            "privacy",
            "boundaries",
        },
        "contract",
    )
    require_exact_value(value.get("schema"), CONTRACT_SCHEMA, "contract.schema")
    require_exact_value(value.get("contract_id"), CONTRACT_ID, "contract.contract_id")
    require_exact_value(
        value.get("stage"),
        "g1_role_appointment_review_only",
        "contract.stage",
    )

    predecessor = require_object(value.get("predecessor"), "contract.predecessor")
    require_exact_value(
        predecessor,
        {
            "commit": PREDECESSOR_COMMIT,
            "contract_id": PREDECESSOR_CONTRACT_ID,
            "contract_sha256": PREDECESSOR_CONTRACT_SHA256,
            "validator_sha256": PREDECESSOR_VALIDATOR_SHA256,
            "immutable": True,
        },
        "contract.predecessor",
    )

    role_review = require_object(value.get("role_review"), "contract.role_review")
    require_exact_value(
        role_review,
        {
            "packet_schema": REVIEW_PACKET_SCHEMA,
            "evidence_classes": [
                "synthetic_contract_test",
                "consumer_owned_real",
            ],
            "reviewer_roles": ["application_owner", "independence_auditor"],
            "application_owner_may_equal_consumer_curator": True,
            "application_owner_may_equal_any_other_holder": False,
            "independence_auditor_must_be_outside_all_role_holders": True,
            "reviewer_commitments_require_private_salts": True,
            "review_receipts_must_be_nonzero": True,
            "review_must_follow_role_packet": True,
            "candidate_may_author_or_approve_review": False,
            "accepted_decisions": ["approve", "reject"],
            "both_reviews_must_approve_for_owner_endorsement": True,
            "validator_authenticates_real_world_identity": False,
        },
        "contract.role_review",
    )

    owner_decision = require_object(
        value.get("owner_decision"), "contract.owner_decision"
    )
    require_exact_value(
        owner_decision,
        {
            "packet_schema": OWNER_DECISION_PACKET_SCHEMA,
            "owner_commitment_must_match_review": True,
            "decision_must_follow_completed_review": True,
            "accepted_decisions": [
                "endorse_private_corpus_assembly_for_authentication",
                "reject_role_roster",
            ],
            "endorsement_requires_both_reviews_approved": True,
            "endorsement_receipt_must_be_nonzero": True,
            "candidate_may_author_owner_decision": False,
            "validator_authenticates_owner_identity": False,
            "structural_endorsement_grants_assembly_authority": False,
            "authenticated_authority_required_before_assembly": True,
        },
        "contract.owner_decision",
    )

    proposed_scope = require_object(
        value.get("proposed_assembly_scope"), "contract.proposed_assembly_scope"
    )
    require_exact_value(
        proposed_scope,
        EXPECTED_PROPOSED_ASSEMBLY_SCOPE,
        "contract.proposed_assembly_scope",
    )
    privacy = require_object(value.get("privacy"), "contract.privacy")
    require_exact_value(
        privacy,
        {
            "real_packets_must_be_ignored_under_data": True,
            "raw_identities_forbidden": True,
            "raw_queries_forbidden": True,
            "packet_identifiers_must_be_opaque_sha256": True,
            "packet_identifiers_must_not_alias_private_commitments_or_receipts": True,
            "redacted_receipt_contains_packet_identifiers": False,
            "redacted_receipt_contains_holder_commitments": False,
            "redacted_receipt_contains_reviewer_commitments": False,
            "redacted_receipt_contains_appointment_or_review_receipts": False,
        },
        "contract.privacy",
    )
    boundaries = require_object(value.get("boundaries"), "contract.boundaries")
    require_exact_value(boundaries, EXPECTED_BOUNDARIES, "contract.boundaries")
    return {
        "contract_sha256": CONTRACT_SHA256,
        "predecessor": predecessor,
        "proposed_assembly_scope": proposed_scope,
        "boundaries": boundaries,
    }


def validate_predecessor_contract(
    path: Path,
) -> tuple[dict[str, Any], bytes]:
    value, raw = read_json(path)
    if sha256_bytes(raw) != PREDECESSOR_CONTRACT_SHA256:
        raise InputError("predecessor contract bytes do not match the G1.1 binding")
    normalized = freeze_preflight.validate_contract(value, raw)
    require_exact_value(
        normalized["contract_id"],
        PREDECESSOR_CONTRACT_ID,
        "predecessor.contract_id",
    )
    validator_path = Path(freeze_preflight.__file__).resolve()
    if sha256_bytes(validator_path.read_bytes()) != PREDECESSOR_VALIDATOR_SHA256:
        raise InputError("loaded G1.1 validator bytes do not match the binding")
    return normalized, raw


def holder_commitments_by_role(
    role: dict[str, Any],
) -> dict[str, list[str]]:
    result: dict[str, list[str]] = {}
    for holder in role["holders"]:
        result.setdefault(holder["role"], []).append(holder["holder_commitment_sha256"])
    return result


def validate_owner_review(
    value: Any,
    holders: dict[str, list[str]],
) -> dict[str, Any]:
    path = "review_packet.application_owner_review"
    review = require_object(value, path)
    require_exact_fields(
        review,
        {
            "reviewer_role",
            "reviewer_commitment_sha256",
            "review_receipt_sha256",
            "decision",
            "owner_is_consumer_curator",
            "appointment_evidence_complete",
            "consumer_ownership_confirmed",
            "workflow_authority_confirmed",
        },
        path,
    )
    require_exact_value(
        review.get("reviewer_role"), "application_owner", f"{path}.reviewer_role"
    )
    commitment = require_nonzero_sha256(
        review.get("reviewer_commitment_sha256"),
        f"{path}.reviewer_commitment_sha256",
    )
    receipt = require_nonzero_sha256(
        review.get("review_receipt_sha256"), f"{path}.review_receipt_sha256"
    )
    decision = require_label(review.get("decision"), f"{path}.decision")
    if decision not in REVIEW_DECISIONS:
        raise InputError(f"{path}.decision is unsupported")
    owner_is_curator = require_bool(
        review.get("owner_is_consumer_curator"),
        f"{path}.owner_is_consumer_curator",
    )
    evidence_flags = {
        key: require_bool(review.get(key), f"{path}.{key}")
        for key in (
            "appointment_evidence_complete",
            "consumer_ownership_confirmed",
            "workflow_authority_confirmed",
        )
    }
    if decision == "approve" and not all(evidence_flags.values()):
        raise InputError("application-owner approval requires complete evidence")

    all_holders = {
        commitment
        for role_commitments in holders.values()
        for commitment in role_commitments
    }
    curator = holders["consumer_curator"][0]
    forbidden_owner_holders = {
        *holders["candidate_implementer"],
        *holders["freeze_reviewer"],
        *holders["sealed_evaluator_custodian"],
    }
    if commitment in forbidden_owner_holders:
        raise InputError("application owner overlaps a forbidden role holder")
    if owner_is_curator:
        if commitment != curator:
            raise InputError("application owner does not match the consumer curator")
    elif commitment in all_holders:
        raise InputError("non-curator application owner must be outside all holders")

    return {
        "commitment": commitment,
        "receipt": receipt,
        "decision": decision,
        "owner_is_consumer_curator": owner_is_curator,
    }


def validate_independence_audit(
    value: Any,
    holders: dict[str, list[str]],
    owner_commitment: str,
) -> dict[str, Any]:
    path = "review_packet.independence_audit"
    audit = require_object(value, path)
    require_exact_fields(
        audit,
        {
            "reviewer_role",
            "auditor_commitment_sha256",
            "audit_receipt_sha256",
            "decision",
            "all_role_holders_distinct",
            "owner_overlap_rule_reviewed",
            "candidate_exclusions_reviewed",
            "sealed_custody_reviewed",
            "salt_custody_reviewed",
            "appointment_chronology_reviewed",
        },
        path,
    )
    require_exact_value(
        audit.get("reviewer_role"),
        "independence_auditor",
        f"{path}.reviewer_role",
    )
    commitment = require_nonzero_sha256(
        audit.get("auditor_commitment_sha256"),
        f"{path}.auditor_commitment_sha256",
    )
    receipt = require_nonzero_sha256(
        audit.get("audit_receipt_sha256"), f"{path}.audit_receipt_sha256"
    )
    decision = require_label(audit.get("decision"), f"{path}.decision")
    if decision not in REVIEW_DECISIONS:
        raise InputError(f"{path}.decision is unsupported")
    review_flags = {
        key: require_bool(audit.get(key), f"{path}.{key}")
        for key in (
            "all_role_holders_distinct",
            "owner_overlap_rule_reviewed",
            "candidate_exclusions_reviewed",
            "sealed_custody_reviewed",
            "salt_custody_reviewed",
            "appointment_chronology_reviewed",
        )
    }
    if decision == "approve" and not all(review_flags.values()):
        raise InputError("independence-auditor approval requires all checks")
    all_holders = {
        holder for role_commitments in holders.values() for holder in role_commitments
    }
    if commitment in all_holders:
        raise InputError("independence auditor must be outside all role holders")
    if commitment == owner_commitment:
        raise InputError("independence auditor must differ from the application owner")
    return {"commitment": commitment, "receipt": receipt, "decision": decision}


def validate_review_packet(
    value: dict[str, Any],
    raw: bytes,
    contract: dict[str, Any],
    role: dict[str, Any],
    role_raw: bytes,
    review_path: Path,
    role_path: Path,
    repo_root: Path,
) -> tuple[dict[str, Any], dict[str, Any]]:
    reject_raw_fields(value)
    reject_raw_identities(value, "review_packet")
    require_exact_fields(
        value,
        {
            "schema",
            "contract_id",
            "contract_sha256",
            "packet_id",
            "evidence_class",
            "role_packet_sha256",
            "review_started_at_unix",
            "review_completed_at_unix",
            "application_owner_review",
            "independence_audit",
            "attestations",
        },
        "review_packet",
    )
    require_exact_value(
        value.get("schema"), REVIEW_PACKET_SCHEMA, "review_packet.schema"
    )
    require_exact_value(
        value.get("contract_id"), CONTRACT_ID, "review_packet.contract_id"
    )
    require_exact_value(
        require_sha256(value.get("contract_sha256"), "review_packet.contract_sha256"),
        contract["contract_sha256"],
        "review_packet.contract_sha256",
    )
    packet_id = require_nonzero_sha256(
        value.get("packet_id"), "review_packet.packet_id"
    )
    evidence_class = require_label(
        value.get("evidence_class"), "review_packet.evidence_class"
    )
    if evidence_class not in EVIDENCE_CLASSES:
        raise InputError("review_packet.evidence_class is unsupported")
    if evidence_class != role["evidence_class"]:
        raise InputError("review and role packet evidence classes must match")
    require_exact_value(
        require_sha256(
            value.get("role_packet_sha256"), "review_packet.role_packet_sha256"
        ),
        sha256_bytes(role_raw),
        "review_packet.role_packet_sha256",
    )
    started_at = require_int(
        value.get("review_started_at_unix"),
        "review_packet.review_started_at_unix",
        minimum=1,
    )
    completed_at = require_int(
        value.get("review_completed_at_unix"),
        "review_packet.review_completed_at_unix",
        minimum=1,
    )
    if started_at <= role["created_at_unix"]:
        raise InputError("role review must start after the role packet")
    if completed_at < started_at:
        raise InputError("role review completion precedes its start")

    holders = holder_commitments_by_role(role)
    owner = validate_owner_review(value.get("application_owner_review"), holders)
    auditor = validate_independence_audit(
        value.get("independence_audit"), holders, owner["commitment"]
    )
    if owner["receipt"] == auditor["receipt"]:
        raise InputError("owner and auditor receipts must be distinct")
    private_commitments = {
        value
        for holder in role["holders"]
        for value in (
            holder["holder_commitment_sha256"],
            holder["appointment_receipt_sha256"],
        )
    }
    private_commitments.update(
        {
            owner["commitment"],
            owner["receipt"],
            auditor["commitment"],
            auditor["receipt"],
        }
    )
    reject_private_commitment_alias(
        packet_id, private_commitments, "review_packet.packet_id"
    )

    attestations = require_object(
        value.get("attestations"), "review_packet.attestations"
    )
    require_exact_value(
        attestations,
        {
            "reviewer_commitments_use_private_salts": True,
            "candidate_did_not_author_review": True,
            "candidate_did_not_see_raw_review_evidence": True,
            "raw_identities_absent": True,
            "external_identity_truth_not_authenticated_by_validator": True,
        },
        "review_packet.attestations",
    )

    if evidence_class == "consumer_owned_real":
        freeze_preflight.ensure_real_packet_is_private(role_path, repo_root)
        freeze_preflight.ensure_real_packet_is_private(review_path, repo_root)

    both_approved = owner["decision"] == "approve" and auditor["decision"] == "approve"
    real = evidence_class == "consumer_owned_real"
    if real and both_approved:
        verdict = "CLAIMED_REAL_REVIEW_READY_FOR_OWNER_ENDORSEMENT"
    elif real:
        verdict = "ROLE_REVIEW_REJECTED"
    elif both_approved:
        verdict = "SYNTHETIC_REVIEW_APPROVAL_VALID"
    else:
        verdict = "SYNTHETIC_REVIEW_REJECTION_VALID"

    normalized = {
        "evidence_class": evidence_class,
        "completed_at_unix": completed_at,
        "owner_commitment": owner["commitment"],
        "owner_decision": owner["decision"],
        "auditor_decision": auditor["decision"],
        "both_approved": both_approved,
        "private_commitments": private_commitments,
    }
    receipt = {
        "schema": REVIEW_RECEIPT_SCHEMA,
        "contract_id": CONTRACT_ID,
        "contract_sha256": contract["contract_sha256"],
        "packet_sha256": sha256_bytes(raw),
        "role_packet_sha256": sha256_bytes(role_raw),
        "evidence_class": evidence_class,
        "application_owner_decision": owner["decision"],
        "independence_audit_decision": auditor["decision"],
        "both_reviews_approved": both_approved,
        "owner_is_consumer_curator": owner["owner_is_consumer_curator"],
        "role_review_verdict": verdict,
        "ready_for_structural_owner_endorsement": real and both_approved,
        "authenticated_authority_verified": False,
        "real_world_identity_authenticated_by_validator": False,
        "holder_commitments_in_receipt": False,
        "reviewer_commitments_in_receipt": False,
        "appointment_or_review_receipts_in_receipt": False,
        "private_corpus_assembly_authority": False,
        "g1_corpus_freeze_authority": False,
        "candidate_implementation_authority": False,
        "biocortex_experiment_execution_authority": False,
        "retrieval_order_mutation_authority": False,
        "live_store_write_authority": False,
        "runtime_promotion_authority": False,
    }
    return normalized, receipt


def validate_owner_decision_packet(
    value: dict[str, Any],
    raw: bytes,
    contract: dict[str, Any],
    role: dict[str, Any],
    role_raw: bytes,
    review: dict[str, Any],
    review_raw: bytes,
    decision_path: Path,
    role_path: Path,
    review_path: Path,
    repo_root: Path,
) -> dict[str, Any]:
    reject_raw_fields(value)
    reject_raw_identities(value, "owner_decision")
    require_exact_fields(
        value,
        {
            "schema",
            "contract_id",
            "contract_sha256",
            "decision_id",
            "evidence_class",
            "role_packet_sha256",
            "review_packet_sha256",
            "owner_commitment_sha256",
            "decided_at_unix",
            "decision",
            "owner_endorsement_receipt_sha256",
            "proposed_assembly_scope",
            "attestations",
        },
        "owner_decision",
    )
    require_exact_value(
        value.get("schema"), OWNER_DECISION_PACKET_SCHEMA, "owner_decision.schema"
    )
    require_exact_value(
        value.get("contract_id"), CONTRACT_ID, "owner_decision.contract_id"
    )
    require_exact_value(
        require_sha256(value.get("contract_sha256"), "owner_decision.contract_sha256"),
        contract["contract_sha256"],
        "owner_decision.contract_sha256",
    )
    decision_id = require_nonzero_sha256(
        value.get("decision_id"), "owner_decision.decision_id"
    )
    evidence_class = require_label(
        value.get("evidence_class"), "owner_decision.evidence_class"
    )
    if evidence_class not in EVIDENCE_CLASSES:
        raise InputError("owner_decision.evidence_class is unsupported")
    if (
        evidence_class != role["evidence_class"]
        or evidence_class != review["evidence_class"]
    ):
        raise InputError("owner decision evidence class does not match its inputs")
    require_exact_value(
        require_sha256(
            value.get("role_packet_sha256"), "owner_decision.role_packet_sha256"
        ),
        sha256_bytes(role_raw),
        "owner_decision.role_packet_sha256",
    )
    require_exact_value(
        require_sha256(
            value.get("review_packet_sha256"),
            "owner_decision.review_packet_sha256",
        ),
        sha256_bytes(review_raw),
        "owner_decision.review_packet_sha256",
    )
    owner_commitment = require_nonzero_sha256(
        value.get("owner_commitment_sha256"),
        "owner_decision.owner_commitment_sha256",
    )
    require_exact_value(
        owner_commitment,
        review["owner_commitment"],
        "owner_decision.owner_commitment_sha256",
    )
    decided_at = require_int(
        value.get("decided_at_unix"), "owner_decision.decided_at_unix", minimum=1
    )
    if decided_at <= review["completed_at_unix"]:
        raise InputError("owner decision must follow the completed role review")
    decision = require_label(value.get("decision"), "owner_decision.decision")
    if decision not in OWNER_DECISIONS:
        raise InputError("owner_decision.decision is unsupported")
    endorsement_receipt = require_nonzero_sha256(
        value.get("owner_endorsement_receipt_sha256"),
        "owner_decision.owner_endorsement_receipt_sha256",
    )
    reject_private_commitment_alias(
        decision_id,
        {*review["private_commitments"], owner_commitment, endorsement_receipt},
        "owner_decision.decision_id",
    )
    scope = require_object(
        value.get("proposed_assembly_scope"),
        "owner_decision.proposed_assembly_scope",
    )
    require_exact_value(
        scope,
        contract["proposed_assembly_scope"],
        "owner_decision.proposed_assembly_scope",
    )
    attestations = require_object(
        value.get("attestations"), "owner_decision.attestations"
    )
    require_exact_value(
        attestations,
        {
            "application_owner_authored_endorsement": True,
            "candidate_did_not_author_decision": True,
            "candidate_did_not_see_raw_decision_evidence": True,
            "owner_commitment_uses_private_salt": True,
            "raw_identities_absent": True,
            "validator_does_not_authenticate_owner_identity": True,
        },
        "owner_decision.attestations",
    )

    endorsing = decision == "endorse_private_corpus_assembly_for_authentication"
    if endorsing and not review["both_approved"]:
        raise InputError("owner endorsement requires both role reviews to approve")
    if evidence_class == "consumer_owned_real":
        freeze_preflight.ensure_real_packet_is_private(role_path, repo_root)
        freeze_preflight.ensure_real_packet_is_private(review_path, repo_root)
        freeze_preflight.ensure_real_packet_is_private(decision_path, repo_root)

    structural_real_endorsement = evidence_class == "consumer_owned_real" and endorsing
    if structural_real_endorsement:
        verdict = "CLAIMED_REAL_ENDORSEMENT_READY_FOR_AUTHENTICATION"
    elif evidence_class == "consumer_owned_real":
        verdict = "ROLE_ROSTER_REJECTED"
    elif endorsing:
        verdict = "SYNTHETIC_ENDORSEMENT_VALID_NO_AUTHORITY"
    else:
        verdict = "SYNTHETIC_REJECTION_VALID_NO_AUTHORITY"

    return {
        "schema": OWNER_DECISION_RECEIPT_SCHEMA,
        "contract_id": CONTRACT_ID,
        "contract_sha256": contract["contract_sha256"],
        "owner_decision_sha256": sha256_bytes(raw),
        "role_packet_sha256": sha256_bytes(role_raw),
        "review_packet_sha256": sha256_bytes(review_raw),
        "evidence_class": evidence_class,
        "decision": decision,
        "both_reviews_approved": review["both_approved"],
        "structure_valid_for_authentication": endorsing and review["both_approved"],
        "owner_decision_verdict": verdict,
        "ready_for_authenticated_authority_review": structural_real_endorsement,
        "ready_for_private_corpus_assembly": False,
        "proposed_executor_role": scope["executor_role"],
        "proposed_custody_role": scope["custody_role"],
        "proposed_maximum_intake_episode_groups": scope[
            "maximum_intake_episode_groups"
        ],
        "authenticated_authority_verified": False,
        "real_world_identity_authenticated_by_validator": False,
        "holder_commitments_in_receipt": False,
        "reviewer_commitments_in_receipt": False,
        "appointment_review_or_endorsement_receipts_in_receipt": False,
        "private_corpus_assembly_authority": False,
        "candidate_lane_may_execute": False,
        "g1_corpus_freeze_authority": False,
        "candidate_implementation_authority": False,
        "biocortex_experiment_execution_authority": False,
        "retrieval_order_mutation_authority": False,
        "live_store_write_authority": False,
        "runtime_promotion_authority": False,
    }


def contract_receipt(contract: dict[str, Any]) -> dict[str, Any]:
    boundaries = contract["boundaries"]
    return {
        "schema": CONTRACT_RECEIPT_SCHEMA,
        "contract_id": CONTRACT_ID,
        "contract_sha256": CONTRACT_SHA256,
        "predecessor_commit": PREDECESSOR_COMMIT,
        "predecessor_contract_sha256": PREDECESSOR_CONTRACT_SHA256,
        "predecessor_validator_sha256": PREDECESSOR_VALIDATOR_SHA256,
        "contract_verdict": "READY_FOR_PRIVATE_ROLE_REVIEW_PACKET_NO_AUTHORITY",
        "ready_for_private_role_review_packet": True,
        "authenticated_authority_required_before_assembly": True,
        "application_owner_may_equal_consumer_curator": True,
        "independence_auditor_must_be_outside_all_role_holders": True,
        "proposed_maximum_intake_episode_groups": contract["proposed_assembly_scope"][
            "maximum_intake_episode_groups"
        ],
        "current_private_corpus_assembly_authority": boundaries[
            "current_private_corpus_assembly_authority"
        ],
        "g1_corpus_freeze_authority": boundaries["g1_corpus_freeze_authority"],
        "candidate_implementation_authority": boundaries[
            "candidate_implementation_authority"
        ],
        "biocortex_experiment_execution_authority": boundaries[
            "biocortex_experiment_execution_authority"
        ],
        "retrieval_order_mutation_authority": boundaries[
            "retrieval_order_mutation_authority"
        ],
        "live_store_write_authority": boundaries["live_store_write_authority"],
        "runtime_promotion_authority": boundaries["runtime_promotion_authority"],
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    contract_parser = subparsers.add_parser("validate-contract")
    contract_parser.add_argument("--contract", type=Path, required=True)

    review_parser = subparsers.add_parser("validate-review")
    review_parser.add_argument("--contract", type=Path, required=True)
    review_parser.add_argument("--preflight-contract", type=Path, required=True)
    review_parser.add_argument("--role-packet", type=Path, required=True)
    review_parser.add_argument("--review-packet", type=Path, required=True)

    decision_parser = subparsers.add_parser("validate-owner-decision")
    decision_parser.add_argument("--contract", type=Path, required=True)
    decision_parser.add_argument("--preflight-contract", type=Path, required=True)
    decision_parser.add_argument("--role-packet", type=Path, required=True)
    decision_parser.add_argument("--review-packet", type=Path, required=True)
    decision_parser.add_argument("--owner-decision", type=Path, required=True)
    return parser


def emit(value: dict[str, Any]) -> None:
    print(
        json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False)
    )


def main() -> int:
    args = build_parser().parse_args()
    try:
        contract_value, contract_raw = read_json(args.contract)
        contract = validate_contract(contract_value, contract_raw)
        if args.command == "validate-contract":
            emit(contract_receipt(contract))
            return 0

        repo_root = freeze_preflight.find_repo_root(Path(__file__).resolve().parent)
        preflight_contract, _ = validate_predecessor_contract(args.preflight_contract)
        role_value, role_raw = read_json(args.role_packet)
        role, _ = freeze_preflight.validate_role_packet(
            role_value,
            role_raw,
            preflight_contract,
            args.role_packet,
            repo_root,
        )
        review_value, review_raw = read_json(args.review_packet)
        review, review_receipt = validate_review_packet(
            review_value,
            review_raw,
            contract,
            role,
            role_raw,
            args.review_packet,
            args.role_packet,
            repo_root,
        )
        if args.command == "validate-review":
            emit(review_receipt)
            return 0

        decision_value, decision_raw = read_json(args.owner_decision)
        decision_receipt = validate_owner_decision_packet(
            decision_value,
            decision_raw,
            contract,
            role,
            role_raw,
            review,
            review_raw,
            args.owner_decision,
            args.role_packet,
            args.review_packet,
            repo_root,
        )
        emit(decision_receipt)
        return 0
    except InputError as exc:
        print(f"engram G1 role review rejected: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
