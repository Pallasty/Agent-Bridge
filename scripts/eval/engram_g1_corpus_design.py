#!/usr/bin/env python3
"""Validate the G1 grouped-corpus preregistration without assembling a corpus.

The checked design contains aggregate counts, fixed thresholds, provenance
rules, and authority boundaries only. It must not contain raw probes, episode
keys, or partition membership. A valid receipt permits independent consumer
corpus assembly *review*; it does not freeze a corpus or authorize candidate
implementation, retrieval mutation, experiment execution, or promotion.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import stat
import sys
from pathlib import Path
from typing import Any


DESIGN_SCHEMA = "agent_bridge.engram_g1_grouped_corpus_design.v0"
RECEIPT_SCHEMA = "agent_bridge.engram_g1_grouped_corpus_design_receipt.v0"
MAX_JSON_INPUT_BYTES = 512 * 1024
LABEL_RE = re.compile(r"^[a-z0-9][a-z0-9_.:-]{0,127}$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")

EXPECTED_G0_BINDING = {
    "contract_id": "engram_g0_real_failure_intake_20260717",
    "contract_sha256": "0490e0db9fcc5681ca44229f3f2178a19d8dda08f8acf72f006cd211d6175de8",
    "packet_id": "hard_miss_cohort_20260622_23_g0",
    "packet_sha256": "feb5c8c639f48a6179144cfbe6b16a548aef91a127840c37640b7673a88c97e1",
    "g0_verdict": "PASS_OBSERVED_RELEVANT_FAILURE",
    "admitted_signature": "overgeneralization_gap",
    "admitted_episode_group_id": "remote_session_steering_gap",
    "consumer_review_receipt_sha256": "6a45b042bc978e19dade66ff95d8846ece4c18985e51622296febc99fdfef711",
}
EXPECTED_MODES = ["fts", "hybrid", "semantic"]
EXPECTED_PROBE_CLASSES = ["exact", "related", "unrelated"]
EXPECTED_ARMS = [
    "stable_control",
    "density_only",
    "clustered_reorganization",
    "mechanism_off",
    "cluster_shuffled",
]
RAW_FIELDS = {
    "content",
    "contents",
    "episode_key",
    "episode_keys",
    "expected_key",
    "expected_keys",
    "expected_target_keys",
    "memory_key",
    "memory_keys",
    "partition_members",
    "prompt",
    "prompts",
    "query",
    "queries",
    "raw_content",
    "raw_prompt",
    "raw_query",
    "text",
}


class InputError(ValueError):
    """Raised when a G1 design violates its preregistered boundary."""


def reject_json_constant(value: str) -> None:
    raise InputError(f"non-standard JSON constant is forbidden: {value}")


def reject_duplicate_json_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise InputError("JSON object contains a duplicate field")
        result[key] = value
    return result


def read_stable_bounded_file(path: Path) -> bytes:
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags)
    except OSError as exc:
        raise InputError(f"failed to open design: {exc}") from exc
    try:
        before = os.fstat(descriptor)
        if not stat.S_ISREG(before.st_mode):
            raise InputError("design must be a regular file")
        if before.st_size < 1 or before.st_size > MAX_JSON_INPUT_BYTES:
            raise InputError("design exceeds the bounded size")
        chunks: list[bytes] = []
        remaining = before.st_size
        while remaining:
            chunk = os.read(descriptor, min(64 * 1024, remaining))
            if not chunk:
                raise InputError("design ended during capture")
            chunks.append(chunk)
            remaining -= len(chunk)
        raw = b"".join(chunks)
        after = os.fstat(descriptor)
    finally:
        os.close(descriptor)
    before_identity = (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns)
    after_identity = (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns)
    if before_identity != after_identity or len(raw) != before.st_size:
        raise InputError("design changed during capture")
    return raw


def read_json(path: Path) -> tuple[dict[str, Any], bytes]:
    raw = read_stable_bounded_file(path)
    try:
        value = json.loads(
            raw.decode("utf-8", errors="strict"),
            parse_constant=reject_json_constant,
            object_pairs_hook=reject_duplicate_json_keys,
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise InputError(f"failed to parse design: {exc}") from exc
    return require_object(value, "design"), raw


def render_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_canonical(value: Any) -> str:
    return sha256_bytes(render_json(value).encode("utf-8"))


def require_object(value: Any, path: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise InputError(f"{path} must be an object")
    return value


def require_list(value: Any, path: str) -> list[Any]:
    if not isinstance(value, list):
        raise InputError(f"{path} must be an array")
    return value


def require_string(value: Any, path: str, *, max_bytes: int = 256) -> str:
    if not isinstance(value, str):
        raise InputError(f"{path} must be a string")
    if not value or len(value.encode("utf-8")) > max_bytes:
        raise InputError(f"{path} must be a bounded non-empty string")
    return value


def require_label(value: Any, path: str) -> str:
    label = require_string(value, path, max_bytes=128)
    if not LABEL_RE.fullmatch(label):
        raise InputError(f"{path} must be a lowercase label")
    return label


def require_sha256(value: Any, path: str) -> str:
    digest = require_string(value, path, max_bytes=64)
    if not SHA256_RE.fullmatch(digest):
        raise InputError(f"{path} must be a lowercase SHA-256")
    return digest


def require_bool(value: Any, path: str) -> bool:
    if not isinstance(value, bool):
        raise InputError(f"{path} must be boolean")
    return value


def require_int(value: Any, path: str, *, minimum: int = 0) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise InputError(f"{path} must be an integer >= {minimum}")
    return value


def require_number(value: Any, path: str, *, minimum: float, maximum: float) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise InputError(f"{path} must be numeric")
    number = float(value)
    if not math.isfinite(number) or number < minimum or number > maximum:
        raise InputError(f"{path} must be finite and between {minimum} and {maximum}")
    return number


def require_exact_fields(value: dict[str, Any], expected: set[str], path: str) -> None:
    actual = set(value)
    if actual != expected:
        missing = sorted(expected - actual)
        extra = sorted(actual - expected)
        raise InputError(f"{path} fields mismatch: missing={missing}, extra={extra}")


def require_exact_value(value: Any, expected: Any, path: str) -> None:
    if value != expected:
        raise InputError(f"{path} must remain preregistered as {expected!r}")


def reject_raw_fields(value: Any, path: str = "design") -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            if key.lower() in RAW_FIELDS:
                raise InputError(f"{path}.{key} is a forbidden raw-content field")
            reject_raw_fields(child, f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            reject_raw_fields(child, f"{path}[{index}]")


def validate_g0_binding(value: Any) -> dict[str, Any]:
    binding = require_object(value, "design.g0_receipt_binding")
    require_exact_fields(binding, set(EXPECTED_G0_BINDING), "design.g0_receipt_binding")
    for key, expected in EXPECTED_G0_BINDING.items():
        path = f"design.g0_receipt_binding.{key}"
        if key.endswith("sha256"):
            require_sha256(binding.get(key), path)
        else:
            require_string(binding.get(key), path)
        require_exact_value(binding.get(key), expected, path)
    return binding


def validate_objective(value: Any) -> dict[str, Any]:
    objective = require_object(value, "design.objective")
    require_exact_fields(
        objective,
        {"primary_failure", "primary_metric", "direction", "preservation_metrics"},
        "design.objective",
    )
    require_exact_value(
        objective.get("primary_failure"),
        "overgeneralization_gap",
        "design.objective.primary_failure",
    )
    require_exact_value(
        objective.get("primary_metric"),
        "unrelated_target_intrusion_rate_at_10",
        "design.objective.primary_metric",
    )
    require_exact_value(
        objective.get("direction"), "lower_is_better", "design.objective.direction"
    )
    preservation = require_list(
        objective.get("preservation_metrics"), "design.objective.preservation_metrics"
    )
    require_exact_value(
        preservation,
        ["exact_hit_at_10", "related_hit_at_10", "exact_mrr", "related_mrr"],
        "design.objective.preservation_metrics",
    )
    return objective


def validate_partitions(value: Any) -> dict[str, Any]:
    partitions = require_object(value, "design.corpus.partitions")
    require_exact_fields(
        partitions, {"fit", "development", "sealed"}, "design.corpus.partitions"
    )
    expected = {
        "fit": (12, "candidate_visible"),
        "development": (8, "reviewer_mediated"),
        "sealed": (10, "custodian_only"),
    }
    for partition, (count, visibility) in expected.items():
        item = require_object(
            partitions.get(partition), f"design.corpus.partitions.{partition}"
        )
        require_exact_fields(
            item,
            {"episode_groups", "visibility"},
            f"design.corpus.partitions.{partition}",
        )
        require_exact_value(
            require_int(
                item.get("episode_groups"),
                f"design.corpus.partitions.{partition}.episode_groups",
            ),
            count,
            f"design.corpus.partitions.{partition}.episode_groups",
        )
        require_exact_value(
            require_label(
                item.get("visibility"),
                f"design.corpus.partitions.{partition}.visibility",
            ),
            visibility,
            f"design.corpus.partitions.{partition}.visibility",
        )
    return partitions


def validate_signature_strata(value: Any) -> int:
    strata = require_list(value, "design.corpus.signature_strata")
    expected = [
        (
            "overgeneralization_gap",
            "primary",
            15,
            {"fit": 6, "development": 4, "sealed": 5},
        ),
        (
            "no_relevant_gap",
            "stability_control",
            9,
            {"fit": 3, "development": 3, "sealed": 3},
        ),
        (
            "ordinary_retrieval_gap",
            "exclusion_control",
            3,
            {"fit": 1, "development": 1, "sealed": 1},
        ),
    ]
    if len(strata) != len(expected):
        raise InputError(
            "design.corpus.signature_strata must contain exactly three preregistered strata"
        )
    total_minimum = 0
    for index, (signature, role, minimum, allocations) in enumerate(expected):
        path = f"design.corpus.signature_strata[{index}]"
        item = require_object(strata[index], path)
        require_exact_fields(
            item,
            {"signature", "role", "minimum_episode_groups", "partition_minimums"},
            path,
        )
        require_exact_value(
            require_label(item.get("signature"), f"{path}.signature"),
            signature,
            f"{path}.signature",
        )
        require_exact_value(
            require_label(item.get("role"), f"{path}.role"), role, f"{path}.role"
        )
        observed_minimum = require_int(
            item.get("minimum_episode_groups"), f"{path}.minimum_episode_groups"
        )
        require_exact_value(observed_minimum, minimum, f"{path}.minimum_episode_groups")
        split = require_object(
            item.get("partition_minimums"), f"{path}.partition_minimums"
        )
        require_exact_fields(split, set(allocations), f"{path}.partition_minimums")
        observed_allocations = {
            partition: require_int(
                split.get(partition), f"{path}.partition_minimums.{partition}"
            )
            for partition in allocations
        }
        require_exact_value(
            observed_allocations, allocations, f"{path}.partition_minimums"
        )
        if sum(observed_allocations.values()) != observed_minimum:
            raise InputError(f"{path} partition minima do not sum to its minimum")
        total_minimum += observed_minimum
    return total_minimum


def validate_corpus(value: Any) -> tuple[dict[str, Any], int]:
    corpus = require_object(value, "design.corpus")
    require_exact_fields(
        corpus,
        {
            "episode_group_target",
            "episode_group_hard_cap",
            "frozen_scored_group_count",
            "probes_per_episode_group",
            "probe_classes",
            "split_unit",
            "keep_group_probes_together",
            "partitions",
            "g0_incident_handling",
            "signature_strata",
            "excluded_signatures",
            "conditionally_eligible_signatures",
            "minimum_application_families",
            "maximum_fraction_per_application_family",
        },
        "design.corpus",
    )
    target = require_int(
        corpus.get("episode_group_target"),
        "design.corpus.episode_group_target",
        minimum=1,
    )
    hard_cap = require_int(
        corpus.get("episode_group_hard_cap"),
        "design.corpus.episode_group_hard_cap",
        minimum=1,
    )
    frozen_count = require_int(
        corpus.get("frozen_scored_group_count"),
        "design.corpus.frozen_scored_group_count",
        minimum=1,
    )
    require_exact_value(target, 30, "design.corpus.episode_group_target")
    require_exact_value(hard_cap, 36, "design.corpus.episode_group_hard_cap")
    require_exact_value(frozen_count, 30, "design.corpus.frozen_scored_group_count")
    if not frozen_count == target <= hard_cap:
        raise InputError("design.corpus target/frozen/hard-cap relationship is invalid")
    require_exact_value(
        require_int(
            corpus.get("probes_per_episode_group"),
            "design.corpus.probes_per_episode_group",
            minimum=1,
        ),
        3,
        "design.corpus.probes_per_episode_group",
    )
    require_exact_value(
        require_list(corpus.get("probe_classes"), "design.corpus.probe_classes"),
        EXPECTED_PROBE_CLASSES,
        "design.corpus.probe_classes",
    )
    require_exact_value(
        require_label(corpus.get("split_unit"), "design.corpus.split_unit"),
        "episode_group",
        "design.corpus.split_unit",
    )
    require_exact_value(
        require_bool(
            corpus.get("keep_group_probes_together"),
            "design.corpus.keep_group_probes_together",
        ),
        True,
        "design.corpus.keep_group_probes_together",
    )
    partitions = validate_partitions(corpus.get("partitions"))
    if sum(item["episode_groups"] for item in partitions.values()) != frozen_count:
        raise InputError(
            "design.corpus partition counts do not equal the frozen scored count"
        )
    incident = require_object(
        corpus.get("g0_incident_handling"), "design.corpus.g0_incident_handling"
    )
    require_exact_fields(
        incident,
        {
            "partition",
            "counts_toward_signature_minimum",
            "excluded_from_development",
            "excluded_from_sealed",
        },
        "design.corpus.g0_incident_handling",
    )
    expected_incident = {
        "partition": "fit",
        "counts_toward_signature_minimum": True,
        "excluded_from_development": True,
        "excluded_from_sealed": True,
    }
    require_exact_value(
        incident, expected_incident, "design.corpus.g0_incident_handling"
    )
    total_minimum = validate_signature_strata(corpus.get("signature_strata"))
    if total_minimum > target:
        raise InputError("design.corpus signature minima exceed the target")
    require_exact_value(
        require_list(
            corpus.get("excluded_signatures"), "design.corpus.excluded_signatures"
        ),
        ["ambiguous_dual_failure"],
        "design.corpus.excluded_signatures",
    )
    require_exact_value(
        require_list(
            corpus.get("conditionally_eligible_signatures"),
            "design.corpus.conditionally_eligible_signatures",
        ),
        ["generalization_gap"],
        "design.corpus.conditionally_eligible_signatures",
    )
    require_exact_value(
        require_int(
            corpus.get("minimum_application_families"),
            "design.corpus.minimum_application_families",
            minimum=1,
        ),
        4,
        "design.corpus.minimum_application_families",
    )
    require_exact_value(
        require_number(
            corpus.get("maximum_fraction_per_application_family"),
            "design.corpus.maximum_fraction_per_application_family",
            minimum=0.0,
            maximum=1.0,
        ),
        0.35,
        "design.corpus.maximum_fraction_per_application_family",
    )
    return corpus, total_minimum


def validate_provenance(value: Any) -> dict[str, Any]:
    provenance = require_object(value, "design.provenance")
    expected = {
        "consumer_owned_required": True,
        "observed_before_candidate_implementation_lock": True,
        "candidate_authored_probes_forbidden": True,
        "candidate_team_may_curate_probes": False,
        "rights_cleared_required": True,
        "minimum_independent_consumer_reviewers": 2,
    }
    require_exact_fields(provenance, set(expected), "design.provenance")
    for key, expected_value in expected.items():
        observed = (
            require_int(provenance.get(key), f"design.provenance.{key}", minimum=1)
            if key.startswith("minimum_")
            else require_bool(provenance.get(key), f"design.provenance.{key}")
        )
        require_exact_value(observed, expected_value, f"design.provenance.{key}")
    return provenance


def validate_baseline(value: Any) -> dict[str, Any]:
    baseline = require_object(value, "design.baseline")
    expected = {
        "retrieval_modes",
        "aggregate_envelope",
        "top_k",
        "deterministic_replay_count_before_freeze_review",
        "require_identical_ranks_across_replays",
        "require_frozen_environment_receipt",
    }
    require_exact_fields(baseline, expected, "design.baseline")
    require_exact_value(
        require_list(
            baseline.get("retrieval_modes"), "design.baseline.retrieval_modes"
        ),
        EXPECTED_MODES,
        "design.baseline.retrieval_modes",
    )
    require_exact_value(
        require_label(
            baseline.get("aggregate_envelope"), "design.baseline.aggregate_envelope"
        ),
        "any_mode",
        "design.baseline.aggregate_envelope",
    )
    require_exact_value(
        require_int(baseline.get("top_k"), "design.baseline.top_k", minimum=1),
        10,
        "design.baseline.top_k",
    )
    require_exact_value(
        require_int(
            baseline.get("deterministic_replay_count_before_freeze_review"),
            "design.baseline.deterministic_replay_count_before_freeze_review",
            minimum=1,
        ),
        2,
        "design.baseline.deterministic_replay_count_before_freeze_review",
    )
    require_exact_value(
        require_bool(
            baseline.get("require_identical_ranks_across_replays"),
            "design.baseline.require_identical_ranks_across_replays",
        ),
        True,
        "design.baseline.require_identical_ranks_across_replays",
    )
    require_exact_value(
        require_bool(
            baseline.get("require_frozen_environment_receipt"),
            "design.baseline.require_frozen_environment_receipt",
        ),
        True,
        "design.baseline.require_frozen_environment_receipt",
    )
    return baseline


def validate_metrics(value: Any) -> dict[str, Any]:
    metrics = require_object(value, "design.metrics")
    require_exact_fields(
        metrics,
        {
            "decision_partition",
            "unit_of_analysis",
            "primary",
            "noninferiority",
            "specificity_guards",
        },
        "design.metrics",
    )
    require_exact_value(
        require_label(
            metrics.get("decision_partition"), "design.metrics.decision_partition"
        ),
        "sealed",
        "design.metrics.decision_partition",
    )
    require_exact_value(
        require_label(
            metrics.get("unit_of_analysis"), "design.metrics.unit_of_analysis"
        ),
        "episode_group",
        "design.metrics.unit_of_analysis",
    )
    primary = require_object(metrics.get("primary"), "design.metrics.primary")
    expected_primary = {
        "metric": "unrelated_target_intrusion_rate_at_10",
        "stratum": "overgeneralization_gap",
        "aggregation": "any_mode",
        "comparison_baseline": "strongest_preregistered_baseline",
        "strongest_baseline_selection": "lowest_intrusion_rate",
    }
    require_exact_fields(
        primary,
        set(expected_primary) | {"minimum_absolute_reduction"},
        "design.metrics.primary",
    )
    for key, expected in expected_primary.items():
        require_exact_value(
            require_label(primary.get(key), f"design.metrics.primary.{key}"),
            expected,
            f"design.metrics.primary.{key}",
        )
    require_exact_value(
        require_number(
            primary.get("minimum_absolute_reduction"),
            "design.metrics.primary.minimum_absolute_reduction",
            minimum=0.0,
            maximum=1.0,
        ),
        0.2,
        "design.metrics.primary.minimum_absolute_reduction",
    )
    noninferiority = require_object(
        metrics.get("noninferiority"), "design.metrics.noninferiority"
    )
    expected_noninferiority = {
        "exact_hit_at_10_maximum_absolute_loss": 0.02,
        "related_hit_at_10_maximum_absolute_loss": 0.02,
        "exact_mrr_maximum_absolute_loss": 0.05,
        "related_mrr_maximum_absolute_loss": 0.05,
    }
    require_exact_fields(
        noninferiority, set(expected_noninferiority), "design.metrics.noninferiority"
    )
    for key, expected in expected_noninferiority.items():
        require_exact_value(
            require_number(
                noninferiority.get(key),
                f"design.metrics.noninferiority.{key}",
                minimum=0.0,
                maximum=1.0,
            ),
            expected,
            f"design.metrics.noninferiority.{key}",
        )
    guards = require_object(
        metrics.get("specificity_guards"), "design.metrics.specificity_guards"
    )
    expected_guards = {
        "per_mode_unrelated_intrusion_maximum_absolute_increase": 0.05,
        "no_relevant_gap_control_maximum_absolute_regression": 0.02,
    }
    require_exact_fields(
        guards, set(expected_guards), "design.metrics.specificity_guards"
    )
    for key, expected in expected_guards.items():
        require_exact_value(
            require_number(
                guards.get(key),
                f"design.metrics.specificity_guards.{key}",
                minimum=0.0,
                maximum=1.0,
            ),
            expected,
            f"design.metrics.specificity_guards.{key}",
        )
    return metrics


def validate_custody(value: Any) -> dict[str, Any]:
    custody = require_object(value, "design.custody")
    expected = {
        "consumer_curator_role": "consumer_curator",
        "candidate_implementer_role": "candidate_implementer",
        "sealed_evaluator_role": "sealed_evaluator_custodian",
        "require_role_separation": True,
        "same_person_may_hold_multiple_roles": False,
        "minimum_independent_freeze_reviewers": 2,
        "fit_visibility": "candidate_visible",
        "development_visibility": "reviewer_mediated",
        "sealed_raw_material_visibility": "custodian_only",
    }
    require_exact_fields(custody, set(expected), "design.custody")
    for key, expected_value in expected.items():
        path = f"design.custody.{key}"
        if isinstance(expected_value, bool):
            observed = require_bool(custody.get(key), path)
        elif isinstance(expected_value, int):
            observed = require_int(custody.get(key), path, minimum=1)
        else:
            observed = require_label(custody.get(key), path)
        require_exact_value(observed, expected_value, path)
    return custody


def validate_sealed_evaluation(value: Any) -> dict[str, Any]:
    sealed = require_object(value, "design.sealed_evaluation")
    expected = {
        "maximum_attempts": 1,
        "requires_candidate_hash_lock": True,
        "raw_material_hidden_from_candidate": True,
        "partition_membership_hidden_from_candidate": True,
        "labels_hidden_from_candidate": True,
        "one_shot_after_candidate_lock": True,
    }
    require_exact_fields(sealed, set(expected), "design.sealed_evaluation")
    for key, expected_value in expected.items():
        path = f"design.sealed_evaluation.{key}"
        observed = (
            require_int(sealed.get(key), path, minimum=1)
            if key == "maximum_attempts"
            else require_bool(sealed.get(key), path)
        )
        require_exact_value(observed, expected_value, path)
    return sealed


def validate_experiment_design(value: Any) -> dict[str, Any]:
    experiment = require_object(value, "design.experiment_design")
    expected_fields = {
        "arms",
        "equal_growth_budget",
        "deterministic",
        "opt_in",
        "runtime_api_change",
        "arms_are_design_declarations_only",
    }
    require_exact_fields(experiment, expected_fields, "design.experiment_design")
    require_exact_value(
        require_list(experiment.get("arms"), "design.experiment_design.arms"),
        EXPECTED_ARMS,
        "design.experiment_design.arms",
    )
    expected_flags = {
        "equal_growth_budget": True,
        "deterministic": True,
        "opt_in": True,
        "runtime_api_change": False,
        "arms_are_design_declarations_only": True,
    }
    for key, expected in expected_flags.items():
        require_exact_value(
            require_bool(experiment.get(key), f"design.experiment_design.{key}"),
            expected,
            f"design.experiment_design.{key}",
        )
    return experiment


def validate_resource_envelope(value: Any) -> dict[str, Any]:
    envelope = require_object(value, "design.resource_envelope")
    expected = {
        "maximum_episode_groups": 36,
        "probes_per_episode_group": 3,
        "retrieval_modes": 3,
        "maximum_observations_per_replay": 324,
        "baseline_replay_count": 2,
        "maximum_baseline_observations": 648,
    }
    require_exact_fields(envelope, set(expected), "design.resource_envelope")
    for key, expected_value in expected.items():
        require_exact_value(
            require_int(
                envelope.get(key), f"design.resource_envelope.{key}", minimum=1
            ),
            expected_value,
            f"design.resource_envelope.{key}",
        )
    calculated = (
        envelope["maximum_episode_groups"]
        * envelope["probes_per_episode_group"]
        * envelope["retrieval_modes"]
    )
    if calculated != envelope["maximum_observations_per_replay"]:
        raise InputError(
            "design.resource_envelope per-replay calculation is inconsistent"
        )
    if (
        calculated * envelope["baseline_replay_count"]
        != envelope["maximum_baseline_observations"]
    ):
        raise InputError(
            "design.resource_envelope baseline calculation is inconsistent"
        )
    return envelope


def validate_boundaries(value: Any) -> dict[str, Any]:
    boundaries = require_object(value, "design.boundaries")
    expected = {
        "contains_raw_queries": False,
        "contains_episode_keys": False,
        "contains_partition_membership": False,
        "writes_live_store": False,
        "mutates_retrieval_order": False,
        "g1_corpus_freeze_authority": False,
        "candidate_implementation_authority": False,
        "biocortex_experiment_execution_authority": False,
        "runtime_promotion_authority": False,
    }
    require_exact_fields(boundaries, set(expected), "design.boundaries")
    for key, expected_value in expected.items():
        require_exact_value(
            require_bool(boundaries.get(key), f"design.boundaries.{key}"),
            expected_value,
            f"design.boundaries.{key}",
        )
    return boundaries


def validate_design(value: dict[str, Any], raw: bytes) -> dict[str, Any]:
    reject_raw_fields(value)
    require_exact_fields(
        value,
        {
            "schema",
            "design_id",
            "stage",
            "g0_receipt_binding",
            "objective",
            "corpus",
            "provenance",
            "baseline",
            "metrics",
            "custody",
            "sealed_evaluation",
            "experiment_design",
            "resource_envelope",
            "boundaries",
        },
        "design",
    )
    require_exact_value(
        require_string(value.get("schema"), "design.schema"),
        DESIGN_SCHEMA,
        "design.schema",
    )
    design_id = require_label(value.get("design_id"), "design.design_id")
    require_exact_value(
        design_id,
        "engram_g1_grouped_corpus_preregistration_20260717",
        "design.design_id",
    )
    require_exact_value(
        require_label(value.get("stage"), "design.stage"),
        "g1_grouped_corpus_design_only",
        "design.stage",
    )
    binding = validate_g0_binding(value.get("g0_receipt_binding"))
    objective = validate_objective(value.get("objective"))
    corpus, total_minimum = validate_corpus(value.get("corpus"))
    validate_provenance(value.get("provenance"))
    baseline = validate_baseline(value.get("baseline"))
    metrics = validate_metrics(value.get("metrics"))
    validate_custody(value.get("custody"))
    validate_sealed_evaluation(value.get("sealed_evaluation"))
    validate_experiment_design(value.get("experiment_design"))
    envelope = validate_resource_envelope(value.get("resource_envelope"))
    boundaries = validate_boundaries(value.get("boundaries"))

    receipt = {
        "schema": RECEIPT_SCHEMA,
        "design_id": design_id,
        "design_sha256": sha256_bytes(raw),
        "canonical_design_sha256": sha256_canonical(value),
        "g0_binding_sha256": sha256_canonical(binding),
        "g0_verdict": binding["g0_verdict"],
        "admitted_signature": binding["admitted_signature"],
        "primary_failure": objective["primary_failure"],
        "primary_metric": objective["primary_metric"],
        "decision_partition": metrics["decision_partition"],
        "unit_of_analysis": metrics["unit_of_analysis"],
        "episode_group_target": corpus["episode_group_target"],
        "episode_group_hard_cap": corpus["episode_group_hard_cap"],
        "preregistered_signature_minimum_count": total_minimum,
        "unallocated_target_slots": corpus["episode_group_target"] - total_minimum,
        "partition_counts": {
            key: corpus["partitions"][key]["episode_groups"]
            for key in ("fit", "development", "sealed")
        },
        "baseline_modes": baseline["retrieval_modes"],
        "maximum_observations_per_replay": envelope["maximum_observations_per_replay"],
        "maximum_baseline_observations": envelope["maximum_baseline_observations"],
        "design_verdict": "READY_FOR_CONSUMER_CORPUS_ASSEMBLY_REVIEW",
        "ready_for_consumer_corpus_assembly_review": True,
        "raw_content_in_receipt": False,
        "g1_corpus_freeze_authority": boundaries["g1_corpus_freeze_authority"],
        "candidate_implementation_authority": boundaries[
            "candidate_implementation_authority"
        ],
        "retrieval_order_mutation_authority": boundaries["mutates_retrieval_order"],
        "biocortex_experiment_execution_authority": boundaries[
            "biocortex_experiment_execution_authority"
        ],
        "runtime_promotion_authority": boundaries["runtime_promotion_authority"],
    }
    return receipt


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--design", type=Path, required=True)
    parser.add_argument("--require-assembly-review-ready", action="store_true")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        value, raw = read_json(args.design)
        receipt = validate_design(value, raw)
        if (
            args.require_assembly_review_ready
            and not receipt["ready_for_consumer_corpus_assembly_review"]
        ):
            raise InputError("design is not ready for consumer corpus assembly review")
        print(
            json.dumps(
                receipt, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False
            )
        )
        return 0
    except InputError as exc:
        print(f"engram G1 design rejected: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
