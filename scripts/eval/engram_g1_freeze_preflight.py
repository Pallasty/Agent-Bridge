#!/usr/bin/env python3
"""Validate G1.1 freeze-preflight contracts and hash-only private packets.

This tool has three structural stages:

* ``validate-contract`` freezes the public amendment and its authority limits;
* ``validate-role`` checks a private role-commitment packet without emitting
  holder commitments;
* ``validate-manifest`` checks a private hash-only grouped-corpus manifest and
  emits aggregate counts only.

The validator cannot authenticate real-world identities, approve appointments,
freeze a corpus, authorize candidate code, execute BioCortex, or mutate live
retrieval. Real packets must remain untracked under the repository ``data/``
tree. Synthetic packets may be used outside that tree for contract tests.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

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
    require_number,
    require_object,
    require_sha256,
    require_string,
    sha256_bytes,
)


CONTRACT_SCHEMA = "agent_bridge.engram_g1_freeze_preflight_contract.v1"
CONTRACT_ID = "engram_g1_freeze_preflight_20260718"
CONTRACT_SHA256 = "5d4835fa2aa404224b98e7a60574121118051d771079f5a0422ab5839564e94a"
ROLE_PACKET_SCHEMA = "agent_bridge.engram_g1_role_commitment_packet.v1"
ROLE_RECEIPT_SCHEMA = "agent_bridge.engram_g1_role_commitment_receipt.v1"
MANIFEST_SCHEMA = "agent_bridge.engram_g1_private_corpus_manifest.v1"
MANIFEST_RECEIPT_SCHEMA = "agent_bridge.engram_g1_corpus_manifest_receipt.v1"
CONTRACT_RECEIPT_SCHEMA = "agent_bridge.engram_g1_freeze_preflight_receipt.v1"

EVIDENCE_CLASSES = {"synthetic_contract_test", "consumer_owned_real"}
MODES = ("fts", "hybrid", "semantic")
PROBE_CLASSES = ("exact", "related", "unrelated")
PARTITIONS = ("fit", "development", "sealed")
ELIGIBLE_SIGNATURES = {
    "overgeneralization_gap",
    "no_relevant_gap",
    "ordinary_retrieval_gap",
    "generalization_gap",
}
EXPECTED_ROLE_COUNTS = {
    "candidate_implementer": 1,
    "consumer_curator": 1,
    "freeze_reviewer": 2,
    "sealed_evaluator_custodian": 1,
}
EXPECTED_ROLE_CLASSES = {
    "candidate_implementer": "candidate_team",
    "consumer_curator": "consumer",
    "freeze_reviewer": "independent_reviewer",
    "sealed_evaluator_custodian": "independent_custodian",
}
EXPECTED_PARTITION_COUNTS = {"fit": 12, "development": 8, "sealed": 10}
EXPECTED_SIGNATURE_MINIMUMS = {
    "overgeneralization_gap": {"fit": 6, "development": 4, "sealed": 5},
    "no_relevant_gap": {"fit": 3, "development": 3, "sealed": 3},
    "ordinary_retrieval_gap": {"fit": 1, "development": 1, "sealed": 1},
}
ADMITTED_G0_GROUP_SHA256 = (
    "5bb20800cea3bdb973ea0604fcd280e89666736b7cd9e595e24c89f4b744a1fc"
)
BASELINE_SOURCE_COMMIT = "3bf8ad3a67ff02a4e717db8e29e89079f66c01cf"
BASELINE_BINARY_SHA256 = (
    "2fcd99a55acb0e433320ada9b058651d46c10500a2ec6459866c3dd504580f30"
)
BASELINE_ENVIRONMENT_SHA256 = (
    "13be7b202d061a1fd37bc2405427ecf1251f85d043b8b5341c8efbc835564f5e"
)
BASELINE_PERCEPTION_SHA256 = (
    "9569e1553c59f54bc95dc9cca9aed6cb65f1fd1b4aae2c4522629aaf63ed9b31"
)


def require_nonzero_sha256(value: Any, path: str) -> str:
    digest = require_sha256(value, path)
    if digest == "0" * 64:
        raise InputError(f"{path} must not be a placeholder")
    return digest


def require_commit(value: Any, path: str) -> str:
    commit = require_string(value, path, max_bytes=40)
    if len(commit) != 40 or any(
        character not in "0123456789abcdef" for character in commit
    ):
        raise InputError(f"{path} must be a lowercase 40-character commit")
    return commit


def find_repo_root(start: Path) -> Path:
    result = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        cwd=start,
        capture_output=True,
        text=True,
        check=False,
        timeout=10,
    )
    if result.returncode != 0:
        raise InputError("could not resolve repository root")
    return Path(result.stdout.strip()).resolve()


def ensure_real_packet_is_private(path: Path, repo_root: Path) -> None:
    resolved = path.resolve()
    data_root = (repo_root / "data").resolve()
    if not data_root.is_relative_to(repo_root):
        raise InputError("repository data/ must remain inside the repository")
    if not resolved.is_relative_to(data_root):
        raise InputError("real G1 packet must stay under the repository data/ tree")
    relative = resolved.relative_to(repo_root)
    ignored = subprocess.run(
        ["git", "check-ignore", "-q", "--no-index", "--", str(relative)],
        cwd=repo_root,
        capture_output=True,
        check=False,
        timeout=10,
    )
    if ignored.returncode != 0:
        raise InputError("real G1 packet path is not ignored by git")
    tracked = subprocess.run(
        ["git", "ls-files", "--error-unmatch", "--", str(relative)],
        cwd=repo_root,
        capture_output=True,
        check=False,
        timeout=10,
    )
    if tracked.returncode == 0:
        raise InputError("real G1 packet must not be tracked by git")
    if tracked.returncode != 1:
        raise InputError("could not prove real G1 packet is untracked")


def validate_contract(value: dict[str, Any], raw: bytes) -> dict[str, Any]:
    reject_raw_fields(value)
    if sha256_bytes(raw) != CONTRACT_SHA256:
        raise InputError(
            "freeze-preflight contract bytes do not match the registered v1"
        )
    require_exact_fields(
        value,
        {
            "schema",
            "contract_id",
            "stage",
            "predecessor",
            "amendment",
            "claim_scope",
            "application_baseline",
            "experiment_decision",
            "corpus",
            "role_commitment",
            "private_manifest",
            "resource_envelope",
            "boundaries",
        },
        "contract",
    )
    require_exact_value(value.get("schema"), CONTRACT_SCHEMA, "contract.schema")
    require_exact_value(value.get("contract_id"), CONTRACT_ID, "contract.contract_id")
    require_exact_value(
        value.get("stage"), "g1_freeze_preflight_only", "contract.stage"
    )

    predecessor = require_object(value.get("predecessor"), "contract.predecessor")
    require_exact_value(
        predecessor,
        {
            "design_id": "engram_g1_grouped_corpus_preregistration_20260717",
            "design_commit": "d8a17461858354a1b0bbd4f86c29eae75bdf0aa9",
            "design_sha256": "275ae840b62a8a5408ea11e98836aefded998d87d2a2c4846939414a3128a0f0",
            "validator_sha256": "2a408d64b34605f434377b3c11f71807f6c81068aa7bcba069c8d3a6dc44cb91",
            "immutable": True,
        },
        "contract.predecessor",
    )
    require_commit(predecessor["design_commit"], "contract.predecessor.design_commit")
    require_sha256(predecessor["design_sha256"], "contract.predecessor.design_sha256")
    require_sha256(
        predecessor["validator_sha256"], "contract.predecessor.validator_sha256"
    )

    amendment = require_object(value.get("amendment"), "contract.amendment")
    require_exact_value(
        amendment,
        {
            "reason_codes": [
                "discrete_sample_granularity",
                "comparator_roster_ambiguity",
                "family_cap_rounding",
                "role_and_manifest_custody",
            ],
            "made_before_new_corpus_observation": True,
            "replaces_rate_only_decision_rule": True,
            "changes_predecessor_bytes": False,
        },
        "contract.amendment",
    )

    claim_scope = require_object(value.get("claim_scope"), "contract.claim_scope")
    require_exact_value(
        claim_scope,
        {
            "decision_class": "deterministic_engineering_screen",
            "population_effect_claim_authority": False,
            "neuroscience_equivalence_claim_authority": False,
            "runtime_value_claim_authority": False,
        },
        "contract.claim_scope",
    )

    baseline = require_object(
        value.get("application_baseline"), "contract.application_baseline"
    )
    require_exact_value(
        baseline,
        {
            "purpose": "failure_signature_classification",
            "source_commit": BASELINE_SOURCE_COMMIT,
            "binary_sha256": BASELINE_BINARY_SHA256,
            "environment_sha256": BASELINE_ENVIRONMENT_SHA256,
            "perception_filter_state_sha256": BASELINE_PERCEPTION_SHA256,
            "embedding_transport": "loopback_delegated",
            "retrieval_modes": list(MODES),
            "aggregate_envelope": "any_mode",
            "top_k": 10,
            "deterministic_replays": 2,
            "ranks_must_match": True,
        },
        "contract.application_baseline",
    )

    decision = require_object(
        value.get("experiment_decision"), "contract.experiment_decision"
    )
    require_exact_value(
        decision,
        {
            "unit": "episode_group",
            "partition": "sealed",
            "primary_signature": "overgeneralization_gap",
            "candidate_arm": "clustered_reorganization",
            "comparator_arms": ["stable_control", "density_only"],
            "must_beat_each_comparator": True,
            "minimum_paired_primary_repairs_vs_each_comparator": 2,
            "minimum_sealed_primary_episode_groups": 5,
            "rate_statistics_are_reporting_only": True,
            "hit_guards": {
                "maximum_new_exact_misses": 0,
                "maximum_new_related_misses": 0,
                "maximum_no_relevant_gap_regressions": 0,
                "maximum_new_per_mode_unrelated_intrusions": 0,
            },
            "rank_guards": {
                "maximum_exact_mrr_absolute_loss": 0.05,
                "maximum_related_mrr_absolute_loss": 0.05,
            },
            "falsifiers": {
                "arms": ["mechanism_off", "cluster_shuffled"],
                "candidate_advantage_must_disappear_when_disabled_or_shuffled": True,
            },
        },
        "contract.experiment_decision",
    )
    require_int(
        decision["minimum_paired_primary_repairs_vs_each_comparator"],
        "contract.experiment_decision.minimum_paired_primary_repairs_vs_each_comparator",
        minimum=1,
    )
    for key, observed in decision["rank_guards"].items():
        require_number(
            observed,
            f"contract.experiment_decision.rank_guards.{key}",
            minimum=0.0,
            maximum=1.0,
        )

    corpus = require_object(value.get("corpus"), "contract.corpus")
    require_exact_fields(
        corpus,
        {
            "frozen_episode_groups",
            "intake_episode_group_hard_cap",
            "probes_per_episode_group",
            "probe_classes",
            "split_unit",
            "partitions",
            "signature_minimums",
            "ordinary_retrieval_gap_exact_count",
            "eligible_signatures",
            "excluded_signatures",
            "minimum_application_families",
            "maximum_frozen_groups_per_application_family",
            "family_cap_rounding",
            "admitted_g0_incident",
        },
        "contract.corpus",
    )
    require_exact_value(
        corpus["frozen_episode_groups"], 30, "contract.corpus.frozen_episode_groups"
    )
    require_exact_value(
        corpus["intake_episode_group_hard_cap"],
        36,
        "contract.corpus.intake_episode_group_hard_cap",
    )
    require_exact_value(
        corpus["probes_per_episode_group"],
        3,
        "contract.corpus.probes_per_episode_group",
    )
    require_exact_value(
        corpus["probe_classes"], list(PROBE_CLASSES), "contract.corpus.probe_classes"
    )
    require_exact_value(
        corpus["split_unit"], "episode_group", "contract.corpus.split_unit"
    )
    require_exact_value(
        corpus["partitions"], EXPECTED_PARTITION_COUNTS, "contract.corpus.partitions"
    )
    require_exact_value(
        corpus["signature_minimums"],
        EXPECTED_SIGNATURE_MINIMUMS,
        "contract.corpus.signature_minimums",
    )
    require_exact_value(
        corpus["ordinary_retrieval_gap_exact_count"],
        3,
        "contract.corpus.ordinary_retrieval_gap_exact_count",
    )
    require_exact_value(
        set(corpus["eligible_signatures"]),
        ELIGIBLE_SIGNATURES,
        "contract.corpus.eligible_signatures",
    )
    require_exact_value(
        corpus["excluded_signatures"],
        ["ambiguous_dual_failure"],
        "contract.corpus.excluded_signatures",
    )
    require_exact_value(
        corpus["minimum_application_families"],
        4,
        "contract.corpus.minimum_application_families",
    )
    require_exact_value(
        corpus["maximum_frozen_groups_per_application_family"],
        10,
        "contract.corpus.maximum_frozen_groups_per_application_family",
    )
    require_exact_value(
        corpus["family_cap_rounding"],
        "floor_0.35_times_30",
        "contract.corpus.family_cap_rounding",
    )
    require_exact_value(
        corpus["admitted_g0_incident"],
        {
            "episode_group_id_sha256": ADMITTED_G0_GROUP_SHA256,
            "signature": "overgeneralization_gap",
            "partition": "fit",
            "exact_count": 1,
        },
        "contract.corpus.admitted_g0_incident",
    )

    role_contract = require_object(
        value.get("role_commitment"), "contract.role_commitment"
    )
    require_exact_value(
        role_contract,
        {
            "packet_schema": ROLE_PACKET_SCHEMA,
            "required_role_counts": EXPECTED_ROLE_COUNTS,
            "all_holder_commitments_must_be_distinct": True,
            "holder_commitments_require_private_salts": True,
            "all_appointment_receipts_must_be_nonzero": True,
            "created_before_private_corpus_assembly": True,
            "candidate_may_curate": False,
            "candidate_may_review_freeze": False,
            "candidate_may_hold_sealed_custody": False,
            "validator_authenticates_real_world_identity": False,
        },
        "contract.role_commitment",
    )

    manifest_contract = require_object(
        value.get("private_manifest"), "contract.private_manifest"
    )
    require_exact_value(
        manifest_contract,
        {
            "packet_schema": MANIFEST_SCHEMA,
            "real_packets_must_be_ignored_under_data": True,
            "stores_probe_hashes_not_raw_material": True,
            "probe_and_group_commitments_require_private_salts": True,
            "stores_partition_membership_privately": True,
            "requires_role_packet_binding": True,
            "requires_role_appointment_before_manifest": True,
            "requires_consumer_owned": True,
            "requires_observed_before_candidate_lock": True,
            "forbids_candidate_authored_probes": True,
            "requires_rights_cleared": True,
            "requires_identical_baseline_replays": True,
            "redacted_receipt_contains_group_identifiers": False,
        },
        "contract.private_manifest",
    )

    resources = require_object(
        value.get("resource_envelope"), "contract.resource_envelope"
    )
    require_exact_value(
        resources,
        {
            "frozen_manifest_observations_per_replay": 270,
            "frozen_manifest_baseline_observations": 540,
            "intake_maximum_observations_per_replay": 324,
            "intake_maximum_baseline_observations": 648,
        },
        "contract.resource_envelope",
    )

    boundaries = require_object(value.get("boundaries"), "contract.boundaries")
    expected_boundaries = {
        "contains_raw_probe_material": False,
        "assigns_real_role_holders": False,
        "assembles_real_corpus": False,
        "g1_corpus_freeze_authority": False,
        "candidate_implementation_authority": False,
        "biocortex_experiment_execution_authority": False,
        "retrieval_order_mutation_authority": False,
        "live_store_write_authority": False,
        "runtime_promotion_authority": False,
    }
    require_exact_value(boundaries, expected_boundaries, "contract.boundaries")

    return {
        "contract_id": CONTRACT_ID,
        "contract_sha256": CONTRACT_SHA256,
        "corpus": corpus,
        "application_baseline": baseline,
        "experiment_decision": decision,
        "resource_envelope": resources,
        "boundaries": boundaries,
    }


def validate_role_packet(
    value: dict[str, Any],
    raw: bytes,
    contract: dict[str, Any],
    packet_path: Path,
    repo_root: Path,
) -> tuple[dict[str, Any], dict[str, Any]]:
    reject_raw_fields(value)
    require_exact_fields(
        value,
        {
            "schema",
            "contract_id",
            "contract_sha256",
            "packet_id",
            "evidence_class",
            "created_at_unix",
            "created_before_private_corpus_assembly",
            "holders",
            "attestations",
        },
        "role_packet",
    )
    require_exact_value(value.get("schema"), ROLE_PACKET_SCHEMA, "role_packet.schema")
    require_exact_value(
        value.get("contract_id"), CONTRACT_ID, "role_packet.contract_id"
    )
    require_exact_value(
        require_sha256(value.get("contract_sha256"), "role_packet.contract_sha256"),
        contract["contract_sha256"],
        "role_packet.contract_sha256",
    )
    packet_id = require_label(value.get("packet_id"), "role_packet.packet_id")
    evidence_class = require_label(
        value.get("evidence_class"), "role_packet.evidence_class"
    )
    if evidence_class not in EVIDENCE_CLASSES:
        raise InputError("role_packet.evidence_class is unsupported")
    created_at_unix = require_int(
        value.get("created_at_unix"), "role_packet.created_at_unix", minimum=1
    )
    require_exact_value(
        require_bool(
            value.get("created_before_private_corpus_assembly"),
            "role_packet.created_before_private_corpus_assembly",
        ),
        True,
        "role_packet.created_before_private_corpus_assembly",
    )

    holders = require_list(value.get("holders"), "role_packet.holders")
    if len(holders) != sum(EXPECTED_ROLE_COUNTS.values()):
        raise InputError("role_packet.holders has the wrong role count")
    role_counts: Counter[str] = Counter()
    holder_commitments: set[str] = set()
    appointment_receipts: set[str] = set()
    normalized_holders: list[dict[str, str]] = []
    for index, raw_holder in enumerate(holders):
        path = f"role_packet.holders[{index}]"
        holder = require_object(raw_holder, path)
        require_exact_fields(
            holder,
            {
                "role",
                "independence_class",
                "holder_commitment_sha256",
                "appointment_receipt_sha256",
            },
            path,
        )
        role = require_label(holder.get("role"), f"{path}.role")
        if role not in EXPECTED_ROLE_COUNTS:
            raise InputError(f"{path}.role is unsupported")
        independence_class = require_label(
            holder.get("independence_class"), f"{path}.independence_class"
        )
        require_exact_value(
            independence_class,
            EXPECTED_ROLE_CLASSES[role],
            f"{path}.independence_class",
        )
        holder_commitment = require_nonzero_sha256(
            holder.get("holder_commitment_sha256"),
            f"{path}.holder_commitment_sha256",
        )
        appointment_receipt = require_nonzero_sha256(
            holder.get("appointment_receipt_sha256"),
            f"{path}.appointment_receipt_sha256",
        )
        if holder_commitment in holder_commitments:
            raise InputError("role_packet holder commitments must be distinct")
        if appointment_receipt in appointment_receipts:
            raise InputError("role_packet appointment receipts must be distinct")
        holder_commitments.add(holder_commitment)
        appointment_receipts.add(appointment_receipt)
        role_counts[role] += 1
        normalized_holders.append(
            {
                "role": role,
                "independence_class": independence_class,
                "holder_commitment_sha256": holder_commitment,
                "appointment_receipt_sha256": appointment_receipt,
            }
        )
    if dict(role_counts) != EXPECTED_ROLE_COUNTS:
        raise InputError("role_packet role roster does not match the preregistration")

    attestations = require_object(value.get("attestations"), "role_packet.attestations")
    expected_attestations = {
        "all_holder_commitments_distinct": True,
        "holder_commitments_use_private_salts": True,
        "consumer_curator_outside_candidate_team": True,
        "freeze_reviewers_outside_candidate_team": True,
        "sealed_custodian_outside_candidate_team": True,
        "candidate_denied_private_manifest": True,
        "candidate_denied_sealed_material": True,
        "candidate_cannot_approve_freeze": True,
        "appointments_precede_corpus_assembly": True,
        "identity_truth_requires_independent_review": True,
    }
    require_exact_value(attestations, expected_attestations, "role_packet.attestations")

    if evidence_class == "consumer_owned_real":
        ensure_real_packet_is_private(packet_path, repo_root)

    normalized = {
        "packet_id": packet_id,
        "evidence_class": evidence_class,
        "created_at_unix": created_at_unix,
        "holders": normalized_holders,
        "attestations": attestations,
    }
    ready = evidence_class == "consumer_owned_real"
    receipt = {
        "schema": ROLE_RECEIPT_SCHEMA,
        "contract_id": CONTRACT_ID,
        "contract_sha256": contract["contract_sha256"],
        "packet_id": packet_id,
        "packet_sha256": sha256_bytes(raw),
        "evidence_class": evidence_class,
        "role_counts": {role: role_counts[role] for role in sorted(role_counts)},
        "distinct_holder_commitment_count": len(holder_commitments),
        "role_packet_verdict": (
            "READY_FOR_INDEPENDENT_ROLE_COMMITMENT_REVIEW"
            if ready
            else "SYNTHETIC_ROLE_PACKET_VALID"
        ),
        "ready_for_independent_role_commitment_review": ready,
        "real_world_identity_authenticated_by_validator": False,
        "private_corpus_assembly_authority": False,
        "g1_corpus_freeze_authority": False,
        "candidate_implementation_authority": False,
        "runtime_promotion_authority": False,
        "holder_commitments_in_receipt": False,
    }
    return normalized, receipt


def validate_rank_map(value: Any, path: str, top_k: int) -> dict[str, int]:
    ranks = require_object(value, path)
    require_exact_fields(ranks, set(MODES), path)
    normalized: dict[str, int] = {}
    for mode in MODES:
        rank = require_int(ranks.get(mode), f"{path}.{mode}")
        if rank > top_k:
            raise InputError(f"{path}.{mode} exceeds top_k")
        normalized[mode] = rank
    return normalized


def best_rank(ranks: dict[str, int]) -> int:
    return min((rank for rank in ranks.values() if rank > 0), default=0)


def classify_group(probes: dict[str, dict[str, Any]]) -> str:
    exact_pass = best_rank(probes["exact"]["ranks"]) > 0
    related_pass = best_rank(probes["related"]["ranks"]) > 0
    unrelated_pass = best_rank(probes["unrelated"]["ranks"]) == 0
    if not exact_pass:
        return "ordinary_retrieval_gap"
    if not related_pass and unrelated_pass:
        return "generalization_gap"
    if related_pass and not unrelated_pass:
        return "overgeneralization_gap"
    if related_pass and unrelated_pass:
        return "no_relevant_gap"
    return "ambiguous_dual_failure"


def validate_manifest_baseline(value: Any, contract: dict[str, Any]) -> dict[str, Any]:
    path = "manifest.baseline"
    baseline = require_object(value, path)
    expected = contract["application_baseline"]
    require_exact_fields(
        baseline,
        {
            "source_commit",
            "binary_sha256",
            "environment_sha256",
            "perception_filter_state_sha256",
            "embedding_transport",
            "retrieval_modes",
            "aggregate_envelope",
            "top_k",
            "deterministic_replays",
        },
        path,
    )
    require_exact_value(
        require_commit(baseline.get("source_commit"), f"{path}.source_commit"),
        expected["source_commit"],
        f"{path}.source_commit",
    )
    for key in (
        "binary_sha256",
        "environment_sha256",
        "perception_filter_state_sha256",
    ):
        require_exact_value(
            require_sha256(baseline.get(key), f"{path}.{key}"),
            expected[key],
            f"{path}.{key}",
        )
    for key in (
        "embedding_transport",
        "retrieval_modes",
        "aggregate_envelope",
        "top_k",
        "deterministic_replays",
    ):
        require_exact_value(baseline.get(key), expected[key], f"{path}.{key}")
    return baseline


def validate_replay_integrity(value: Any) -> dict[str, Any]:
    path = "manifest.replay_integrity"
    integrity = require_object(value, path)
    require_exact_fields(
        integrity,
        {
            "source_db_query_only",
            "source_db_total_changes_before",
            "source_db_total_changes_after",
            "base_snapshot_sha256_before",
            "base_snapshot_sha256_after",
            "base_snapshot_unchanged",
            "durable_state_sha256_before",
            "durable_state_sha256_after",
            "durable_state_unchanged",
            "fresh_snapshot_per_probe_mode_replay",
            "baseline_observation_count",
            "live_memory_writes",
            "candidate_mechanism_enabled",
            "biocortex_retrieval_enabled",
        },
        path,
    )
    expected_flags = {
        "source_db_query_only": True,
        "base_snapshot_unchanged": True,
        "durable_state_unchanged": True,
        "fresh_snapshot_per_probe_mode_replay": True,
        "candidate_mechanism_enabled": False,
        "biocortex_retrieval_enabled": False,
    }
    for key, expected in expected_flags.items():
        require_exact_value(
            require_bool(integrity.get(key), f"{path}.{key}"),
            expected,
            f"{path}.{key}",
        )
    for key, expected in {
        "source_db_total_changes_before": 0,
        "source_db_total_changes_after": 0,
        "baseline_observation_count": 540,
        "live_memory_writes": 0,
    }.items():
        require_exact_value(
            require_int(integrity.get(key), f"{path}.{key}"),
            expected,
            f"{path}.{key}",
        )
    base_before = require_nonzero_sha256(
        integrity.get("base_snapshot_sha256_before"),
        f"{path}.base_snapshot_sha256_before",
    )
    base_after = require_nonzero_sha256(
        integrity.get("base_snapshot_sha256_after"),
        f"{path}.base_snapshot_sha256_after",
    )
    if base_before != base_after:
        raise InputError("manifest base snapshot changed between replays")
    durable_before = require_nonzero_sha256(
        integrity.get("durable_state_sha256_before"),
        f"{path}.durable_state_sha256_before",
    )
    durable_after = require_nonzero_sha256(
        integrity.get("durable_state_sha256_after"),
        f"{path}.durable_state_sha256_after",
    )
    if durable_before != durable_after:
        raise InputError("manifest durable state changed between replays")
    return integrity


def validate_manifest_group(
    value: Any,
    index: int,
    top_k: int,
    group_commitments: set[str],
    query_commitments: set[str],
) -> dict[str, Any]:
    path = f"manifest.episode_groups[{index}]"
    group = require_object(value, path)
    require_exact_fields(
        group,
        {
            "episode_group_id_sha256",
            "application_family_id_sha256",
            "source_identity_sha256",
            "consumer_observation_receipt_sha256",
            "rights_receipt_sha256",
            "partition",
            "declared_signature",
            "is_admitted_g0_incident",
            "provenance",
            "expected_target_set_sha256",
            "probes",
        },
        path,
    )
    group_commitment = require_nonzero_sha256(
        group.get("episode_group_id_sha256"), f"{path}.episode_group_id_sha256"
    )
    if group_commitment in group_commitments:
        raise InputError("manifest episode-group commitments must be unique")
    group_commitments.add(group_commitment)
    family_commitment = require_nonzero_sha256(
        group.get("application_family_id_sha256"),
        f"{path}.application_family_id_sha256",
    )
    for key in (
        "source_identity_sha256",
        "consumer_observation_receipt_sha256",
        "rights_receipt_sha256",
    ):
        require_nonzero_sha256(group.get(key), f"{path}.{key}")
    partition = require_label(group.get("partition"), f"{path}.partition")
    if partition not in PARTITIONS:
        raise InputError(f"{path}.partition is unsupported")
    declared_signature = require_label(
        group.get("declared_signature"), f"{path}.declared_signature"
    )
    if declared_signature not in ELIGIBLE_SIGNATURES:
        raise InputError(f"{path}.declared_signature is not eligible")
    is_g0 = require_bool(
        group.get("is_admitted_g0_incident"), f"{path}.is_admitted_g0_incident"
    )
    provenance = require_object(group.get("provenance"), f"{path}.provenance")
    expected_provenance = {
        "consumer_owned": True,
        "observed_before_candidate_implementation_lock": True,
        "candidate_authored_probes": False,
        "rights_cleared": True,
    }
    require_exact_value(provenance, expected_provenance, f"{path}.provenance")
    target_set = require_nonzero_sha256(
        group.get("expected_target_set_sha256"),
        f"{path}.expected_target_set_sha256",
    )

    probes = require_list(group.get("probes"), f"{path}.probes")
    if len(probes) != len(PROBE_CLASSES):
        raise InputError(f"{path}.probes must contain exact/related/unrelated")
    normalized_probes: dict[str, dict[str, Any]] = {}
    for probe_index, raw_probe in enumerate(probes):
        probe_path = f"{path}.probes[{probe_index}]"
        probe = require_object(raw_probe, probe_path)
        require_exact_fields(
            probe,
            {
                "probe_class",
                "query_sha256",
                "expected_target_set_sha256",
                "replay_ranks",
            },
            probe_path,
        )
        probe_class = require_label(
            probe.get("probe_class"), f"{probe_path}.probe_class"
        )
        if probe_class not in PROBE_CLASSES or probe_class in normalized_probes:
            raise InputError(f"{probe_path}.probe_class is duplicate or unsupported")
        query_commitment = require_nonzero_sha256(
            probe.get("query_sha256"), f"{probe_path}.query_sha256"
        )
        if query_commitment in query_commitments:
            raise InputError("manifest query commitments must be unique")
        query_commitments.add(query_commitment)
        require_exact_value(
            require_nonzero_sha256(
                probe.get("expected_target_set_sha256"),
                f"{probe_path}.expected_target_set_sha256",
            ),
            target_set,
            f"{probe_path}.expected_target_set_sha256",
        )
        replay_ranks = require_list(
            probe.get("replay_ranks"), f"{probe_path}.replay_ranks"
        )
        if len(replay_ranks) != 2:
            raise InputError(f"{probe_path}.replay_ranks must contain two replays")
        first = validate_rank_map(
            replay_ranks[0], f"{probe_path}.replay_ranks[0]", top_k
        )
        second = validate_rank_map(
            replay_ranks[1], f"{probe_path}.replay_ranks[1]", top_k
        )
        if first != second:
            raise InputError(f"{probe_path} baseline ranks changed across replays")
        normalized_probes[probe_class] = {
            "query_sha256": query_commitment,
            "ranks": first,
        }
    if set(normalized_probes) != set(PROBE_CLASSES):
        raise InputError(f"{path}.probes is missing a required probe class")
    observed_signature = classify_group(normalized_probes)
    require_exact_value(
        observed_signature, declared_signature, f"{path}.declared_signature"
    )
    return {
        "episode_group_id_sha256": group_commitment,
        "application_family_id_sha256": family_commitment,
        "partition": partition,
        "signature": observed_signature,
        "is_admitted_g0_incident": is_g0,
    }


def validate_manifest_packet(
    value: dict[str, Any],
    raw: bytes,
    contract: dict[str, Any],
    role_value: dict[str, Any],
    role_raw: bytes,
    manifest_path: Path,
    role_path: Path,
    repo_root: Path,
) -> dict[str, Any]:
    reject_raw_fields(value)
    require_exact_fields(
        value,
        {
            "schema",
            "contract_id",
            "contract_sha256",
            "manifest_id",
            "evidence_class",
            "assembled_at_unix",
            "role_packet_sha256",
            "baseline",
            "replay_integrity",
            "episode_groups",
            "assembly_attestations",
        },
        "manifest",
    )
    require_exact_value(value.get("schema"), MANIFEST_SCHEMA, "manifest.schema")
    require_exact_value(value.get("contract_id"), CONTRACT_ID, "manifest.contract_id")
    require_exact_value(
        require_sha256(value.get("contract_sha256"), "manifest.contract_sha256"),
        contract["contract_sha256"],
        "manifest.contract_sha256",
    )
    manifest_id = require_label(value.get("manifest_id"), "manifest.manifest_id")
    evidence_class = require_label(
        value.get("evidence_class"), "manifest.evidence_class"
    )
    if evidence_class not in EVIDENCE_CLASSES:
        raise InputError("manifest.evidence_class is unsupported")
    assembled_at_unix = require_int(
        value.get("assembled_at_unix"), "manifest.assembled_at_unix", minimum=1
    )
    if assembled_at_unix <= role_value["created_at_unix"]:
        raise InputError(
            "manifest assembly must occur after the role commitment packet"
        )
    require_exact_value(
        require_sha256(value.get("role_packet_sha256"), "manifest.role_packet_sha256"),
        sha256_bytes(role_raw),
        "manifest.role_packet_sha256",
    )
    if role_value["evidence_class"] != evidence_class:
        raise InputError("manifest and role packet evidence classes must match")

    baseline = validate_manifest_baseline(value.get("baseline"), contract)
    validate_replay_integrity(value.get("replay_integrity"))
    episode_groups = require_list(
        value.get("episode_groups"), "manifest.episode_groups"
    )
    if len(episode_groups) != contract["corpus"]["frozen_episode_groups"]:
        raise InputError("manifest must contain exactly 30 frozen episode groups")

    group_commitments: set[str] = set()
    query_commitments: set[str] = set()
    normalized_groups = [
        validate_manifest_group(
            group,
            index,
            baseline["top_k"],
            group_commitments,
            query_commitments,
        )
        for index, group in enumerate(episode_groups)
    ]

    partition_counts = Counter(group["partition"] for group in normalized_groups)
    if dict(partition_counts) != EXPECTED_PARTITION_COUNTS:
        raise InputError("manifest partition counts do not match the preregistration")
    signature_counts = Counter(group["signature"] for group in normalized_groups)
    if signature_counts["ordinary_retrieval_gap"] != 3:
        raise InputError(
            "manifest must contain exactly three ordinary-retrieval controls"
        )
    partition_signature_counts: dict[str, Counter[str]] = defaultdict(Counter)
    for group in normalized_groups:
        partition_signature_counts[group["signature"]][group["partition"]] += 1
    for signature, minimums in EXPECTED_SIGNATURE_MINIMUMS.items():
        for partition, minimum in minimums.items():
            observed = partition_signature_counts[signature][partition]
            if observed < minimum:
                raise InputError(
                    f"manifest lacks {signature} minimum in {partition}: {observed} < {minimum}"
                )

    family_counts = Counter(
        group["application_family_id_sha256"] for group in normalized_groups
    )
    if len(family_counts) < contract["corpus"]["minimum_application_families"]:
        raise InputError("manifest has too few independent application families")
    maximum_family_count = max(family_counts.values(), default=0)
    if (
        maximum_family_count
        > contract["corpus"]["maximum_frozen_groups_per_application_family"]
    ):
        raise InputError("manifest exceeds the integer application-family cap")

    g0_groups = [
        group for group in normalized_groups if group["is_admitted_g0_incident"]
    ]
    if len(g0_groups) != 1:
        raise InputError("manifest must identify exactly one admitted G0 incident")
    g0_group = g0_groups[0]
    require_exact_value(
        g0_group,
        {
            "episode_group_id_sha256": ADMITTED_G0_GROUP_SHA256,
            "application_family_id_sha256": g0_group["application_family_id_sha256"],
            "partition": "fit",
            "signature": "overgeneralization_gap",
            "is_admitted_g0_incident": True,
        },
        "manifest admitted G0 incident",
    )

    attestations = require_object(
        value.get("assembly_attestations"), "manifest.assembly_attestations"
    )
    expected_attestations = {
        "candidate_has_not_seen_private_manifest": True,
        "candidate_has_not_seen_sealed_material": True,
        "partitioned_by_episode_group": True,
        "no_probe_crosses_partitions": True,
        "curation_completed_before_candidate_implementation_lock": True,
        "alternates_excluded_from_frozen_manifest": True,
        "commitment_salts_held_by_sealed_custodian": True,
        "contains_raw_queries": False,
        "freeze_review_not_yet_granted": True,
    }
    require_exact_value(
        attestations, expected_attestations, "manifest.assembly_attestations"
    )

    if evidence_class == "consumer_owned_real":
        ensure_real_packet_is_private(role_path, repo_root)
        ensure_real_packet_is_private(manifest_path, repo_root)

    ready = evidence_class == "consumer_owned_real"
    return {
        "schema": MANIFEST_RECEIPT_SCHEMA,
        "contract_id": CONTRACT_ID,
        "contract_sha256": contract["contract_sha256"],
        "manifest_id": manifest_id,
        "manifest_sha256": sha256_bytes(raw),
        "role_packet_sha256": sha256_bytes(role_raw),
        "evidence_class": evidence_class,
        "episode_group_count": len(normalized_groups),
        "partition_counts": {
            partition: partition_counts[partition] for partition in PARTITIONS
        },
        "signature_counts": {
            signature: signature_counts[signature]
            for signature in sorted(signature_counts)
        },
        "application_family_count": len(family_counts),
        "maximum_groups_in_one_application_family": maximum_family_count,
        "baseline_observation_count": 540,
        "manifest_verdict": (
            "READY_FOR_INDEPENDENT_CORPUS_FREEZE_REVIEW"
            if ready
            else "SYNTHETIC_MANIFEST_VALID"
        ),
        "ready_for_independent_corpus_freeze_review": ready,
        "group_identifiers_in_receipt": False,
        "partition_membership_in_receipt": False,
        "holder_commitments_in_receipt": False,
        "raw_content_in_receipt": False,
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
        "predecessor_design_sha256": "275ae840b62a8a5408ea11e98836aefded998d87d2a2c4846939414a3128a0f0",
        "decision_class": "deterministic_engineering_screen",
        "candidate_arm": contract["experiment_decision"]["candidate_arm"],
        "comparator_arms": contract["experiment_decision"]["comparator_arms"],
        "minimum_paired_primary_repairs_vs_each_comparator": contract[
            "experiment_decision"
        ]["minimum_paired_primary_repairs_vs_each_comparator"],
        "maximum_new_exact_misses": 0,
        "maximum_new_related_misses": 0,
        "maximum_frozen_groups_per_application_family": contract["corpus"][
            "maximum_frozen_groups_per_application_family"
        ],
        "contract_verdict": "READY_FOR_INDEPENDENT_ROLE_ASSIGNMENT",
        "ready_for_independent_role_assignment": True,
        "population_effect_claim_authority": False,
        "g1_corpus_freeze_authority": boundaries["g1_corpus_freeze_authority"],
        "candidate_implementation_authority": boundaries[
            "candidate_implementation_authority"
        ],
        "biocortex_experiment_execution_authority": boundaries[
            "biocortex_experiment_execution_authority"
        ],
        "runtime_promotion_authority": boundaries["runtime_promotion_authority"],
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    contract_parser = subparsers.add_parser("validate-contract")
    contract_parser.add_argument("--contract", type=Path, required=True)

    role_parser = subparsers.add_parser("validate-role")
    role_parser.add_argument("--contract", type=Path, required=True)
    role_parser.add_argument("--role-packet", type=Path, required=True)

    manifest_parser = subparsers.add_parser("validate-manifest")
    manifest_parser.add_argument("--contract", type=Path, required=True)
    manifest_parser.add_argument("--role-packet", type=Path, required=True)
    manifest_parser.add_argument("--manifest", type=Path, required=True)
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

        repo_root = find_repo_root(args.contract.resolve().parent)
        role_value, role_raw = read_json(args.role_packet)
        normalized_role, role_receipt = validate_role_packet(
            role_value,
            role_raw,
            contract,
            args.role_packet,
            repo_root,
        )
        if args.command == "validate-role":
            emit(role_receipt)
            return 0

        manifest_value, manifest_raw = read_json(args.manifest)
        manifest_receipt = validate_manifest_packet(
            manifest_value,
            manifest_raw,
            contract,
            normalized_role,
            role_raw,
            args.manifest,
            args.role_packet,
            repo_root,
        )
        emit(manifest_receipt)
        return 0
    except InputError as exc:
        print(f"engram G1 freeze preflight rejected: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
