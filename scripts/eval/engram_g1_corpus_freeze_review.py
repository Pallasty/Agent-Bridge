#!/usr/bin/env python3
"""Validate the G1.3 private-corpus freeze-review chain.

The gate binds the G1.2 owner-authorized assembly chain, the exact G1.1
30-group manifest, both appointed freeze reviewers, and the sealed custodian.
Synthetic packets exercise structure but can never freeze a corpus. Real
packets must remain untracked below the repository ``data/`` tree. A real pass
freezes only the exact manifest bytes and opens candidate-protocol
preregistration; it does not authorize candidate code, data access, BioCortex,
retrieval mutation, live writes, or runtime promotion.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

import engram_g1_freeze_preflight as freeze_preflight
import engram_g1_role_review as role_review
from engram_g1_corpus_design import (
    InputError,
    read_json,
    reject_raw_fields,
    require_bool,
    require_exact_fields,
    require_exact_value,
    require_int,
    require_label,
    require_list,
    require_object,
    require_sha256,
    sha256_bytes,
)


CONTRACT_SCHEMA = "agent_bridge.engram_g1_corpus_freeze_review_contract.v1"
CONTRACT_RECEIPT_SCHEMA = (
    "agent_bridge.engram_g1_corpus_freeze_review_contract_receipt.v1"
)
CHAIN_RECEIPT_SCHEMA = "agent_bridge.engram_g1_corpus_freeze_chain_receipt.v1"
FREEZE_REVIEW_PACKET_SCHEMA = "agent_bridge.engram_g1_corpus_freeze_review_packet.v1"
FREEZE_RECEIPT_SCHEMA = "agent_bridge.engram_g1_corpus_freeze_receipt.v1"
CONTRACT_ID = "engram_g1_corpus_freeze_review_20260718"
CONTRACT_SHA256 = "885ad2c0a0590631b1a4c33e168bffd5e1153039a1b5325a24c343599c5c35b5"

PREFLIGHT_COMMIT = "3256fe024c2a280bcd4ac0fee4ff79563c0cc36a"
PREFLIGHT_CONTRACT_ID = "engram_g1_freeze_preflight_20260718"
PREFLIGHT_CONTRACT_SHA256 = (
    "5d4835fa2aa404224b98e7a60574121118051d771079f5a0422ab5839564e94a"
)
PREFLIGHT_VALIDATOR_SHA256 = (
    "f276765f22ee5b2f69e24cf7a79bd9a30e8291f900973d89c06f17d1d0468cdc"
)
ROLE_REVIEW_COMMIT = "426560f67369ec5851b4813fe31a3fe12ae4adde"
ROLE_REVIEW_CONTRACT_ID = "engram_g1_role_review_20260718"
ROLE_REVIEW_CONTRACT_SHA256 = (
    "efb7464e2922d0dd2645698435272714316d07f786bd5a56114e900b99e31f6c"
)
ROLE_REVIEW_VALIDATOR_SHA256 = (
    "5efe72815341492b84a4bd0dee487d1eb572e60e7938f3df7e5cb9710ef8706f"
)

EVIDENCE_CLASSES = {"synthetic_contract_test", "consumer_owned_real"}
REVIEW_DECISIONS = {"approve", "reject"}
REQUIRED_OWNER_DECISION = "approve_private_corpus_assembly"

EXPECTED_APPROVED_FREEZE_SCOPE = {
    "frozen_object": "exact_private_manifest_bytes",
    "frozen_episode_groups": 30,
    "permits_group_addition": False,
    "permits_group_removal": False,
    "permits_group_substitution": False,
    "permits_repartition": False,
    "permits_relabel": False,
    "requires_new_review_for_any_manifest_change": True,
    "permitted_next_action": "prepare_candidate_protocol_preregistration",
    "grants_corpus_freeze": True,
    "grants_candidate_manifest_access": False,
    "grants_candidate_fit_access": False,
    "grants_candidate_implementation": False,
    "grants_biocortex_execution": False,
    "mutates_retrieval_order": False,
    "writes_live_store": False,
    "grants_runtime_promotion": False,
}

EXPECTED_BOUNDARIES = {
    "observes_real_role_or_corpus_evidence": False,
    "freezes_real_corpus": False,
    "current_g1_corpus_freeze_authority": False,
    "candidate_manifest_access_authority": False,
    "candidate_fit_access_authority": False,
    "candidate_implementation_authority": False,
    "biocortex_experiment_execution_authority": False,
    "retrieval_order_mutation_authority": False,
    "live_store_write_authority": False,
    "runtime_promotion_authority": False,
}

REVIEW_CHECK_FIELDS = (
    "exact_manifest_bytes_reviewed",
    "roster_and_partition_counts_reviewed",
    "provenance_receipts_reviewed",
    "replay_integrity_reviewed",
    "application_family_cap_reviewed",
    "admitted_g0_fit_only_reviewed",
    "candidate_exclusions_reviewed",
    "sealed_raw_material_not_received",
)


def require_nonzero_sha256(value: Any, path: str) -> str:
    digest = require_sha256(value, path)
    if digest == "0" * 64:
        raise InputError(f"{path} must not be a placeholder")
    return digest


def validate_contract(value: dict[str, Any], raw: bytes) -> dict[str, Any]:
    reject_raw_fields(value)
    role_review.reject_raw_identities(value, "contract")
    if sha256_bytes(raw) != CONTRACT_SHA256:
        raise InputError(
            "corpus-freeze-review contract bytes do not match the registered v1"
        )
    require_exact_fields(
        value,
        {
            "schema",
            "contract_id",
            "stage",
            "predecessors",
            "input_chain",
            "freeze_review",
            "custody",
            "approved_freeze_scope",
            "privacy",
            "boundaries",
        },
        "contract",
    )
    require_exact_value(value.get("schema"), CONTRACT_SCHEMA, "contract.schema")
    require_exact_value(value.get("contract_id"), CONTRACT_ID, "contract.contract_id")
    require_exact_value(
        value.get("stage"), "g1_corpus_freeze_review_only", "contract.stage"
    )

    predecessors = require_object(value.get("predecessors"), "contract.predecessors")
    require_exact_value(
        predecessors,
        {
            "freeze_preflight": {
                "commit": PREFLIGHT_COMMIT,
                "contract_id": PREFLIGHT_CONTRACT_ID,
                "contract_sha256": PREFLIGHT_CONTRACT_SHA256,
                "validator_sha256": PREFLIGHT_VALIDATOR_SHA256,
                "immutable": True,
            },
            "role_review": {
                "commit": ROLE_REVIEW_COMMIT,
                "contract_id": ROLE_REVIEW_CONTRACT_ID,
                "contract_sha256": ROLE_REVIEW_CONTRACT_SHA256,
                "validator_sha256": ROLE_REVIEW_VALIDATOR_SHA256,
                "immutable": True,
            },
        },
        "contract.predecessors",
    )

    input_chain = require_object(value.get("input_chain"), "contract.input_chain")
    require_exact_value(
        input_chain,
        {
            "evidence_classes": [
                "synthetic_contract_test",
                "consumer_owned_real",
            ],
            "role_packet_schema": freeze_preflight.ROLE_PACKET_SCHEMA,
            "role_review_packet_schema": role_review.REVIEW_PACKET_SCHEMA,
            "owner_decision_packet_schema": role_review.OWNER_DECISION_PACKET_SCHEMA,
            "manifest_schema": freeze_preflight.MANIFEST_SCHEMA,
            "exact_packet_byte_binding_required": True,
            "all_evidence_classes_must_match": True,
            "required_owner_decision": REQUIRED_OWNER_DECISION,
            "owner_decision_must_precede_manifest_assembly": True,
            "real_owner_decision_must_grant_private_assembly": True,
            "manifest_must_pass_freeze_preflight": True,
            "real_packets_must_be_ignored_under_data": True,
        },
        "contract.input_chain",
    )

    freeze_review_contract = require_object(
        value.get("freeze_review"), "contract.freeze_review"
    )
    require_exact_value(
        freeze_review_contract,
        {
            "packet_schema": FREEZE_REVIEW_PACKET_SCHEMA,
            "required_freeze_reviewer_count": 2,
            "reviewer_commitments_must_match_role_packet": True,
            "each_freeze_reviewer_used_exactly_once": True,
            "accepted_decisions": ["approve", "reject"],
            "both_reviewers_must_approve_for_freeze": True,
            "review_must_follow_manifest_assembly": True,
            "review_must_follow_owner_decision": True,
            "review_receipts_must_be_nonzero_and_distinct": True,
            "candidate_may_author_or_approve_review": False,
            "reviewers_receive_hash_only_material": True,
            "validator_authenticates_real_world_identity": False,
        },
        "contract.freeze_review",
    )

    custody = require_object(value.get("custody"), "contract.custody")
    require_exact_value(
        custody,
        {
            "required_role": "sealed_evaluator_custodian",
            "custodian_commitment_must_match_role_packet": True,
            "custody_receipt_must_be_nonzero": True,
            "custody_receipt_must_be_distinct_from_freeze_review_receipts": True,
            "exact_manifest_bytes_remain_in_custody": True,
            "commitment_salts_remain_in_custody": True,
            "sealed_raw_material_visibility": "custodian_only",
            "candidate_receives_manifest_or_sealed_material": False,
            "freeze_reviewers_receive_sealed_raw_material": False,
        },
        "contract.custody",
    )

    approved_scope = require_object(
        value.get("approved_freeze_scope"), "contract.approved_freeze_scope"
    )
    require_exact_value(
        approved_scope,
        EXPECTED_APPROVED_FREEZE_SCOPE,
        "contract.approved_freeze_scope",
    )
    privacy = require_object(value.get("privacy"), "contract.privacy")
    require_exact_value(
        privacy,
        {
            "raw_identities_forbidden": True,
            "raw_queries_forbidden": True,
            "redacted_receipt_contains_group_identifiers": False,
            "redacted_receipt_contains_partition_membership": False,
            "redacted_receipt_contains_holder_or_reviewer_commitments": False,
            "redacted_receipt_contains_appointment_review_or_custody_receipts": False,
        },
        "contract.privacy",
    )
    boundaries = require_object(value.get("boundaries"), "contract.boundaries")
    require_exact_value(boundaries, EXPECTED_BOUNDARIES, "contract.boundaries")
    return {
        "contract_sha256": CONTRACT_SHA256,
        "approved_freeze_scope": approved_scope,
        "boundaries": boundaries,
    }


def validate_predecessors(
    preflight_contract_path: Path,
    role_review_contract_path: Path,
) -> tuple[dict[str, Any], dict[str, Any]]:
    preflight_value, preflight_raw = read_json(preflight_contract_path)
    if sha256_bytes(preflight_raw) != PREFLIGHT_CONTRACT_SHA256:
        raise InputError("G1.1 contract bytes do not match the predecessor binding")
    preflight_contract = freeze_preflight.validate_contract(
        preflight_value, preflight_raw
    )
    require_exact_value(
        preflight_contract["contract_id"],
        PREFLIGHT_CONTRACT_ID,
        "predecessors.freeze_preflight.contract_id",
    )
    preflight_validator_path = Path(freeze_preflight.__file__).resolve()
    if (
        sha256_bytes(preflight_validator_path.read_bytes())
        != PREFLIGHT_VALIDATOR_SHA256
    ):
        raise InputError("loaded G1.1 validator bytes do not match the binding")

    role_review_value, role_review_raw = read_json(role_review_contract_path)
    if sha256_bytes(role_review_raw) != ROLE_REVIEW_CONTRACT_SHA256:
        raise InputError("G1.2 contract bytes do not match the predecessor binding")
    role_review_contract = role_review.validate_contract(
        role_review_value, role_review_raw
    )
    role_review_validator_path = Path(role_review.__file__).resolve()
    if (
        sha256_bytes(role_review_validator_path.read_bytes())
        != ROLE_REVIEW_VALIDATOR_SHA256
    ):
        raise InputError("loaded G1.2 validator bytes do not match the binding")
    return preflight_contract, role_review_contract


def validate_input_chain(
    preflight_contract: dict[str, Any],
    role_review_contract: dict[str, Any],
    role_path: Path,
    role_review_path: Path,
    owner_decision_path: Path,
    manifest_path: Path,
    repo_root: Path,
) -> dict[str, Any]:
    role_value, role_raw = read_json(role_path)
    normalized_role, _ = freeze_preflight.validate_role_packet(
        role_value,
        role_raw,
        preflight_contract,
        role_path,
        repo_root,
    )

    review_value, review_raw = read_json(role_review_path)
    normalized_review, _ = role_review.validate_review_packet(
        review_value,
        review_raw,
        role_review_contract,
        normalized_role,
        role_raw,
        role_review_path,
        role_path,
        repo_root,
    )

    owner_value, owner_raw = read_json(owner_decision_path)
    owner_receipt = role_review.validate_owner_decision_packet(
        owner_value,
        owner_raw,
        role_review_contract,
        normalized_role,
        role_raw,
        normalized_review,
        review_raw,
        owner_decision_path,
        role_path,
        role_review_path,
        repo_root,
    )
    require_exact_value(
        owner_value.get("decision"),
        REQUIRED_OWNER_DECISION,
        "owner_decision.decision",
    )
    require_exact_value(
        owner_receipt["structurally_approvable"],
        True,
        "owner_decision.structurally_approvable",
    )
    decided_at = require_int(
        owner_value.get("decided_at_unix"),
        "owner_decision.decided_at_unix",
        minimum=1,
    )

    manifest_value, manifest_raw = read_json(manifest_path)
    manifest_receipt = freeze_preflight.validate_manifest_packet(
        manifest_value,
        manifest_raw,
        preflight_contract,
        normalized_role,
        role_raw,
        manifest_path,
        role_path,
        repo_root,
    )
    assembled_at = require_int(
        manifest_value.get("assembled_at_unix"),
        "manifest.assembled_at_unix",
        minimum=1,
    )
    if assembled_at <= decided_at:
        raise InputError("manifest assembly must follow the G1.2 owner approval")

    evidence_class = normalized_role["evidence_class"]
    observed_classes = {
        evidence_class,
        normalized_review["evidence_class"],
        owner_receipt["evidence_class"],
        manifest_receipt["evidence_class"],
    }
    if len(observed_classes) != 1:
        raise InputError("input-chain evidence classes must match")
    if evidence_class not in EVIDENCE_CLASSES:
        raise InputError("input-chain evidence class is unsupported")
    if evidence_class == "consumer_owned_real":
        require_exact_value(
            owner_receipt["private_corpus_assembly_authority"],
            True,
            "owner_decision.private_corpus_assembly_authority",
        )
        require_exact_value(
            manifest_receipt["ready_for_independent_corpus_freeze_review"],
            True,
            "manifest.ready_for_independent_corpus_freeze_review",
        )

    return {
        "evidence_class": evidence_class,
        "role": normalized_role,
        "role_raw": role_raw,
        "role_review_raw": review_raw,
        "owner_decision_raw": owner_raw,
        "owner_decided_at_unix": decided_at,
        "manifest_raw": manifest_raw,
        "manifest_assembled_at_unix": assembled_at,
        "manifest_receipt": manifest_receipt,
    }


def chain_receipt(contract: dict[str, Any], chain: dict[str, Any]) -> dict[str, Any]:
    manifest = chain["manifest_receipt"]
    real = chain["evidence_class"] == "consumer_owned_real"
    return {
        "schema": CHAIN_RECEIPT_SCHEMA,
        "contract_id": CONTRACT_ID,
        "contract_sha256": contract["contract_sha256"],
        "evidence_class": chain["evidence_class"],
        "role_packet_sha256": sha256_bytes(chain["role_raw"]),
        "role_review_packet_sha256": sha256_bytes(chain["role_review_raw"]),
        "owner_decision_packet_sha256": sha256_bytes(chain["owner_decision_raw"]),
        "manifest_sha256": sha256_bytes(chain["manifest_raw"]),
        "episode_group_count": manifest["episode_group_count"],
        "partition_counts": manifest["partition_counts"],
        "signature_counts": manifest["signature_counts"],
        "application_family_count": manifest["application_family_count"],
        "maximum_groups_in_one_application_family": manifest[
            "maximum_groups_in_one_application_family"
        ],
        "input_chain_verdict": (
            "READY_FOR_PRIVATE_CORPUS_FREEZE_REVIEW"
            if real
            else "SYNTHETIC_FREEZE_CHAIN_VALID"
        ),
        "ready_for_private_corpus_freeze_review": real,
        "real_world_identity_authenticated_by_validator": False,
        "group_identifiers_in_receipt": False,
        "partition_membership_in_receipt": False,
        "holder_or_reviewer_commitments_in_receipt": False,
        "appointment_review_or_custody_receipts_in_receipt": False,
        "g1_corpus_freeze_authority": False,
        "candidate_manifest_access_authority": False,
        "candidate_fit_access_authority": False,
        "candidate_implementation_authority": False,
        "biocortex_experiment_execution_authority": False,
        "retrieval_order_mutation_authority": False,
        "live_store_write_authority": False,
        "runtime_promotion_authority": False,
    }


def validate_reviewer_review(
    value: Any,
    index: int,
    expected_commitments: set[str],
    observed_commitments: set[str],
    observed_receipts: set[str],
) -> str:
    path = f"freeze_review.reviewer_reviews[{index}]"
    review = require_object(value, path)
    require_exact_fields(
        review,
        {
            "reviewer_role",
            "reviewer_commitment_sha256",
            "freeze_review_receipt_sha256",
            "decision",
            *REVIEW_CHECK_FIELDS,
        },
        path,
    )
    require_exact_value(
        review.get("reviewer_role"), "freeze_reviewer", f"{path}.reviewer_role"
    )
    commitment = require_nonzero_sha256(
        review.get("reviewer_commitment_sha256"),
        f"{path}.reviewer_commitment_sha256",
    )
    if commitment not in expected_commitments:
        raise InputError(f"{path} is not an appointed freeze reviewer")
    if commitment in observed_commitments:
        raise InputError("each appointed freeze reviewer must appear exactly once")
    observed_commitments.add(commitment)
    receipt = require_nonzero_sha256(
        review.get("freeze_review_receipt_sha256"),
        f"{path}.freeze_review_receipt_sha256",
    )
    if receipt in observed_receipts:
        raise InputError("freeze-review receipts must be distinct")
    observed_receipts.add(receipt)
    decision = require_label(review.get("decision"), f"{path}.decision")
    if decision not in REVIEW_DECISIONS:
        raise InputError(f"{path}.decision is unsupported")
    checks = [
        require_bool(review.get(field), f"{path}.{field}")
        for field in REVIEW_CHECK_FIELDS
    ]
    if decision == "approve" and not all(checks):
        raise InputError("freeze-review approval requires every registered check")
    return decision


def validate_custodian_attestation(
    value: Any,
    expected_commitment: str,
    review_receipts: set[str],
) -> str:
    path = "freeze_review.custodian_attestation"
    custody = require_object(value, path)
    require_exact_fields(
        custody,
        {
            "custodian_role",
            "custodian_commitment_sha256",
            "custody_receipt_sha256",
            "exact_manifest_in_custody",
            "commitment_salts_in_custody",
            "manifest_bytes_unchanged_during_review",
            "freeze_reviewers_received_hash_only_material_only",
            "sealed_raw_material_not_disclosed_to_candidate",
            "partition_membership_not_disclosed_to_candidate",
            "labels_not_disclosed_to_candidate",
            "sealed_raw_material_not_disclosed_to_freeze_reviewers",
        },
        path,
    )
    require_exact_value(
        custody.get("custodian_role"),
        "sealed_evaluator_custodian",
        f"{path}.custodian_role",
    )
    commitment = require_nonzero_sha256(
        custody.get("custodian_commitment_sha256"),
        f"{path}.custodian_commitment_sha256",
    )
    require_exact_value(
        commitment, expected_commitment, f"{path}.custodian_commitment_sha256"
    )
    receipt = require_nonzero_sha256(
        custody.get("custody_receipt_sha256"), f"{path}.custody_receipt_sha256"
    )
    if receipt in review_receipts:
        raise InputError("custody and freeze-review receipts must be distinct")
    expected_flags = {
        "exact_manifest_in_custody": True,
        "commitment_salts_in_custody": True,
        "manifest_bytes_unchanged_during_review": True,
        "freeze_reviewers_received_hash_only_material_only": True,
        "sealed_raw_material_not_disclosed_to_candidate": True,
        "partition_membership_not_disclosed_to_candidate": True,
        "labels_not_disclosed_to_candidate": True,
        "sealed_raw_material_not_disclosed_to_freeze_reviewers": True,
    }
    for field, expected in expected_flags.items():
        require_exact_value(
            require_bool(custody.get(field), f"{path}.{field}"),
            expected,
            f"{path}.{field}",
        )
    return receipt


def validate_freeze_review_packet(
    value: dict[str, Any],
    raw: bytes,
    contract: dict[str, Any],
    chain: dict[str, Any],
    packet_path: Path,
    repo_root: Path,
) -> dict[str, Any]:
    reject_raw_fields(value)
    role_review.reject_raw_identities(value, "freeze_review")
    require_exact_fields(
        value,
        {
            "schema",
            "contract_id",
            "contract_sha256",
            "packet_id",
            "evidence_class",
            "role_packet_sha256",
            "role_review_packet_sha256",
            "owner_decision_packet_sha256",
            "manifest_sha256",
            "review_started_at_unix",
            "review_completed_at_unix",
            "reviewer_reviews",
            "custodian_attestation",
            "attestations",
        },
        "freeze_review",
    )
    require_exact_value(
        value.get("schema"), FREEZE_REVIEW_PACKET_SCHEMA, "freeze_review.schema"
    )
    require_exact_value(
        value.get("contract_id"), CONTRACT_ID, "freeze_review.contract_id"
    )
    require_exact_value(
        require_sha256(value.get("contract_sha256"), "freeze_review.contract_sha256"),
        contract["contract_sha256"],
        "freeze_review.contract_sha256",
    )
    packet_id = require_label(value.get("packet_id"), "freeze_review.packet_id")
    evidence_class = require_label(
        value.get("evidence_class"), "freeze_review.evidence_class"
    )
    if evidence_class != chain["evidence_class"]:
        raise InputError("freeze-review and input-chain evidence classes must match")
    for field, chain_field in (
        ("role_packet_sha256", "role_raw"),
        ("role_review_packet_sha256", "role_review_raw"),
        ("owner_decision_packet_sha256", "owner_decision_raw"),
        ("manifest_sha256", "manifest_raw"),
    ):
        require_exact_value(
            require_sha256(value.get(field), f"freeze_review.{field}"),
            sha256_bytes(chain[chain_field]),
            f"freeze_review.{field}",
        )
    started_at = require_int(
        value.get("review_started_at_unix"),
        "freeze_review.review_started_at_unix",
        minimum=1,
    )
    completed_at = require_int(
        value.get("review_completed_at_unix"),
        "freeze_review.review_completed_at_unix",
        minimum=1,
    )
    if started_at <= chain["manifest_assembled_at_unix"]:
        raise InputError("freeze review must start after manifest assembly")
    if started_at <= chain["owner_decided_at_unix"]:
        raise InputError("freeze review must start after owner approval")
    if completed_at < started_at:
        raise InputError("freeze-review completion precedes its start")

    holder_commitments = role_review.holder_commitments_by_role(chain["role"])
    expected_reviewers = set(holder_commitments["freeze_reviewer"])
    reviewer_reviews = require_list(
        value.get("reviewer_reviews"), "freeze_review.reviewer_reviews"
    )
    if len(reviewer_reviews) != 2:
        raise InputError("freeze review requires exactly two reviewer decisions")
    observed_reviewers: set[str] = set()
    review_receipts: set[str] = set()
    decisions = [
        validate_reviewer_review(
            review,
            index,
            expected_reviewers,
            observed_reviewers,
            review_receipts,
        )
        for index, review in enumerate(reviewer_reviews)
    ]
    if observed_reviewers != expected_reviewers:
        raise InputError("freeze review does not cover both appointed reviewers")
    validate_custodian_attestation(
        value.get("custodian_attestation"),
        holder_commitments["sealed_evaluator_custodian"][0],
        review_receipts,
    )

    attestations = require_object(
        value.get("attestations"), "freeze_review.attestations"
    )
    require_exact_value(
        attestations,
        {
            "reviewer_commitments_use_private_salts": True,
            "candidate_did_not_author_or_approve_freeze_review": True,
            "candidate_did_not_receive_private_manifest": True,
            "candidate_did_not_receive_sealed_material": True,
            "raw_identities_absent": True,
            "raw_queries_absent": True,
            "external_identity_and_evidence_truth_not_authenticated_by_validator": True,
        },
        "freeze_review.attestations",
    )
    if evidence_class == "consumer_owned_real":
        freeze_preflight.ensure_real_packet_is_private(packet_path, repo_root)

    decision_counts = Counter(decisions)
    both_approved = decision_counts["approve"] == 2
    real_freeze = evidence_class == "consumer_owned_real" and both_approved
    if real_freeze:
        verdict = "G1_CORPUS_FREEZE_AUTHORIZED_FOR_EXACT_MANIFEST"
    elif evidence_class == "consumer_owned_real":
        verdict = "G1_CORPUS_FREEZE_REJECTED"
    elif both_approved:
        verdict = "SYNTHETIC_FREEZE_APPROVAL_VALID_NO_AUTHORITY"
    else:
        verdict = "SYNTHETIC_FREEZE_REJECTION_VALID_NO_AUTHORITY"

    manifest = chain["manifest_receipt"]
    scope = contract["approved_freeze_scope"]
    return {
        "schema": FREEZE_RECEIPT_SCHEMA,
        "contract_id": CONTRACT_ID,
        "contract_sha256": contract["contract_sha256"],
        "packet_id": packet_id,
        "freeze_review_sha256": sha256_bytes(raw),
        "manifest_sha256": sha256_bytes(chain["manifest_raw"]),
        "owner_decision_packet_sha256": sha256_bytes(chain["owner_decision_raw"]),
        "evidence_class": evidence_class,
        "freeze_reviewer_approve_count": decision_counts["approve"],
        "freeze_reviewer_reject_count": decision_counts["reject"],
        "episode_group_count": manifest["episode_group_count"],
        "partition_counts": manifest["partition_counts"],
        "signature_counts": manifest["signature_counts"],
        "application_family_count": manifest["application_family_count"],
        "maximum_groups_in_one_application_family": manifest[
            "maximum_groups_in_one_application_family"
        ],
        "structurally_freezable": both_approved,
        "freeze_review_verdict": verdict,
        "ready_for_candidate_protocol_preregistration": real_freeze,
        "frozen_object": scope["frozen_object"],
        "requires_new_review_for_any_manifest_change": scope[
            "requires_new_review_for_any_manifest_change"
        ],
        "real_world_identity_authenticated_by_validator": False,
        "group_identifiers_in_receipt": False,
        "partition_membership_in_receipt": False,
        "holder_or_reviewer_commitments_in_receipt": False,
        "appointment_review_or_custody_receipts_in_receipt": False,
        "g1_corpus_freeze_authority": real_freeze,
        "candidate_manifest_access_authority": False,
        "candidate_fit_access_authority": False,
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
        "preflight_contract_sha256": PREFLIGHT_CONTRACT_SHA256,
        "preflight_validator_sha256": PREFLIGHT_VALIDATOR_SHA256,
        "role_review_contract_sha256": ROLE_REVIEW_CONTRACT_SHA256,
        "role_review_validator_sha256": ROLE_REVIEW_VALIDATOR_SHA256,
        "contract_verdict": "READY_FOR_PRIVATE_CORPUS_FREEZE_REVIEW_PACKET",
        "ready_for_private_corpus_freeze_review_packet": True,
        "required_freeze_reviewer_count": 2,
        "frozen_episode_groups": contract["approved_freeze_scope"][
            "frozen_episode_groups"
        ],
        "requires_new_review_for_any_manifest_change": True,
        "current_g1_corpus_freeze_authority": boundaries[
            "current_g1_corpus_freeze_authority"
        ],
        "candidate_manifest_access_authority": boundaries[
            "candidate_manifest_access_authority"
        ],
        "candidate_fit_access_authority": boundaries["candidate_fit_access_authority"],
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


def add_chain_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--contract", type=Path, required=True)
    parser.add_argument("--preflight-contract", type=Path, required=True)
    parser.add_argument("--role-review-contract", type=Path, required=True)
    parser.add_argument("--role-packet", type=Path, required=True)
    parser.add_argument("--role-review-packet", type=Path, required=True)
    parser.add_argument("--owner-decision", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    contract_parser = subparsers.add_parser("validate-contract")
    contract_parser.add_argument("--contract", type=Path, required=True)

    chain_parser = subparsers.add_parser("validate-chain")
    add_chain_arguments(chain_parser)

    review_parser = subparsers.add_parser("validate-freeze-review")
    add_chain_arguments(review_parser)
    review_parser.add_argument("--freeze-review", type=Path, required=True)
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

        repo_root = freeze_preflight.find_repo_root(args.contract.resolve().parent)
        preflight_contract, role_review_contract = validate_predecessors(
            args.preflight_contract,
            args.role_review_contract,
        )
        chain = validate_input_chain(
            preflight_contract,
            role_review_contract,
            args.role_packet,
            args.role_review_packet,
            args.owner_decision,
            args.manifest,
            repo_root,
        )
        if args.command == "validate-chain":
            emit(chain_receipt(contract, chain))
            return 0

        freeze_review_value, freeze_review_raw = read_json(args.freeze_review)
        receipt = validate_freeze_review_packet(
            freeze_review_value,
            freeze_review_raw,
            contract,
            chain,
            args.freeze_review,
            repo_root,
        )
        emit(receipt)
        return 0
    except InputError as exc:
        print(f"engram G1 corpus freeze review rejected: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
