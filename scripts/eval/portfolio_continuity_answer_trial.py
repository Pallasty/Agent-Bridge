#!/usr/bin/env python3
"""Capture, blind, and score the portfolio-continuity answer-stage trial.

Real prompts, contexts, answers, condition mappings, and owner reviews stay in
gitignored data/. Checked-in inputs contain only the preregistered contract and
synthetic verifier data.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import shutil
import sqlite3
import subprocess
import tempfile
import time
from collections import Counter
from pathlib import Path
from typing import Any, Callable

import portfolio_continuity_ab_trial as surface


CONTRACT_SCHEMA = "agent_bridge.portfolio_continuity_answer_contract.v0"
CONTRACT_SCHEMA_V1 = "agent_bridge.portfolio_continuity_answer_contract.v1"
SPEC_SCHEMA = "agent_bridge.portfolio_continuity_answer_spec.v0"
SPEC_SCHEMA_V1 = "agent_bridge.portfolio_continuity_answer_spec.v1"
CAPTURE_SCHEMA = "agent_bridge.portfolio_continuity_answer_capture.v0"
CAPTURE_SCHEMA_V1 = "agent_bridge.portfolio_continuity_answer_capture.v1"
CAPTURE_REDACTED_SCHEMA = "agent_bridge.portfolio_continuity_answer_capture_redacted.v0"
CAPTURE_REDACTED_SCHEMA_V1 = "agent_bridge.portfolio_continuity_answer_capture_redacted.v1"
GENERATION_SCHEMA = "agent_bridge.portfolio_continuity_answer_generation.v0"
GENERATION_SCHEMA_V1 = "agent_bridge.portfolio_continuity_answer_generation.v1"
BLIND_PACKET_SCHEMA = "agent_bridge.portfolio_continuity_answer_blind_packet.v0"
BLIND_PACKET_SCHEMA_V1 = "agent_bridge.portfolio_continuity_answer_blind_packet.v1"
BLIND_MAP_SCHEMA = "agent_bridge.portfolio_continuity_answer_blind_map.v0"
BLIND_MAP_SCHEMA_V1 = "agent_bridge.portfolio_continuity_answer_blind_map.v1"
REVIEW_SCHEMA = "agent_bridge.portfolio_continuity_answer_review.v0"
REVIEW_SCHEMA_V1 = "agent_bridge.portfolio_continuity_answer_review.v1"
GENERATION_REDACTED_SCHEMA = (
    "agent_bridge.portfolio_continuity_answer_generation_redacted.v0"
)
GENERATION_REDACTED_SCHEMA_V1 = (
    "agent_bridge.portfolio_continuity_answer_generation_redacted.v1"
)
SCORE_SCHEMA = "agent_bridge.portfolio_continuity_answer_score.v0"
SCORE_SCHEMA_V1 = "agent_bridge.portfolio_continuity_answer_score.v1"

CONDITIONS = (
    "hybrid_retrieval",
    "compact_then_get_top2",
    "session_bootstrap",
    "portfolio_digest",
)
EXPANDED_CONDITIONS = ("hybrid_retrieval", "portfolio_digest")
EXPANDED_STRATA = {
    "portfolio_status",
    "portfolio_retrospective",
    "portfolio_planning",
    "dependency_risk",
    "stale_state",
    "cross_project_conflict",
}
REFERENCE_CONDITION = "hybrid_retrieval"
COMPACT_CONDITION = "compact_then_get_top2"
LABEL_RE = re.compile(r"^[a-z0-9][a-z0-9_.-]{0,63}$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")
MODEL_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}$")
HEX64_RE = re.compile(r"^[0-9a-f]{64}$")
COMPACT_FIELDS = {
    "key",
    "kind",
    "tags",
    "importance",
    "score",
    "cosine",
    "content_preview",
    "content_chars",
    "content_truncated",
}
COMPACT_REQUIRED_FIELDS = COMPACT_FIELDS - {"cosine"}
TOOL_EVENT_MARKERS = {
    "command_execution",
    "file_change",
    "mcp_tool_call",
    "tool_call",
    "web_search",
    "browser_action",
}

TrialError = surface.TrialError


def contract_conditions(contract: dict[str, Any]) -> tuple[str, ...]:
    return tuple(row["condition_id"] for row in contract["conditions"])


def versioned_schema(contract: dict[str, Any], v0: str, v1: str) -> str:
    return v1 if contract["version"] == 1 else v0


def read_json(path: Path) -> tuple[dict[str, Any], bytes]:
    return surface.read_json(path)


def write_json(
    path: Path,
    value: dict[str, Any],
    *,
    protected_paths: tuple[Path, ...] = (),
) -> bytes:
    return surface.write_json(path, value, protected_paths=protected_paths)


def sha256_bytes(value: bytes) -> str:
    return surface.sha256_bytes(value)


def sha256_text(value: str) -> str:
    return surface.sha256_text(value)


def require_object(value: Any, path: str) -> dict[str, Any]:
    return surface.require_object(value, path)


def require_list(value: Any, path: str) -> list[Any]:
    return surface.require_list(value, path)


def require_string(value: Any, path: str, *, max_chars: int = 262_144) -> str:
    text = surface.require_string(value, path)
    if len(text) > max_chars:
        raise TrialError(f"{path} exceeds its character limit")
    return text


def require_label(value: Any, path: str) -> str:
    label = require_string(value, path, max_chars=64)
    if not LABEL_RE.fullmatch(label):
        raise TrialError(f"{path} must be a bounded machine label")
    return label


def require_bool(value: Any, path: str) -> bool:
    return surface.require_bool(value, path)


def require_nonnegative_int(value: Any, path: str) -> int:
    return surface.require_nonnegative_int(value, path)


def require_finite(value: Any, path: str, *, minimum: float = 0.0) -> float:
    number = surface.require_finite_number(value, path)
    if number < minimum:
        raise TrialError(f"{path} is below its minimum")
    return number


def reject_unknown_fields(value: dict[str, Any], allowed: set[str], path: str) -> None:
    surface.reject_unknown_fields(value, allowed, path)


def require_sha256(value: Any, path: str) -> str:
    digest = require_string(value, path, max_chars=64)
    if not SHA256_RE.fullmatch(digest):
        raise TrialError(f"{path} must be a lowercase SHA-256")
    return digest


def require_commit(value: Any, path: str) -> str:
    commit = require_string(value, path, max_chars=40)
    if not COMMIT_RE.fullmatch(commit):
        raise TrialError(f"{path} must be a full lowercase git SHA")
    return commit


def validate_claims(value: Any, path: str, *, allow_empty: bool = False) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for index, raw in enumerate(require_list(value, path)):
        item_path = f"{path}[{index}]"
        row = require_object(raw, item_path)
        reject_unknown_fields(row, {"claim_id", "weight"}, item_path)
        claim_id = require_label(row.get("claim_id"), f"{item_path}.claim_id")
        if claim_id in seen:
            raise TrialError(f"{path} contains duplicate claim ids")
        seen.add(claim_id)
        weight = require_finite(row.get("weight"), f"{item_path}.weight", minimum=0.000001)
        rows.append({"claim_id": claim_id, "weight": weight})
    if not allow_empty and not rows:
        raise TrialError(f"{path} must not be empty")
    return rows


def validate_contract(value: dict[str, Any]) -> dict[str, Any]:
    schema = value.get("schema")
    if schema not in {CONTRACT_SCHEMA, CONTRACT_SCHEMA_V1}:
        raise TrialError(
            f"contract schema must be {CONTRACT_SCHEMA} or {CONTRACT_SCHEMA_V1}"
        )
    version = 1 if schema == CONTRACT_SCHEMA_V1 else 0
    contract_fields = {
        "schema",
        "contract_id",
        "prereg_base_commit",
        "runtime_source_commit",
        "conditions",
        "search",
        "generation",
        "blinding",
        "review",
        "thresholds",
        "cases",
        "boundaries",
    }
    if version == 0:
        contract_fields.add("bootstrap")
    else:
        contract_fields.update(
            {
                "harness_source_sha256",
                "surface_source_sha256",
                "digest_key_sha256",
            }
        )
    reject_unknown_fields(value, contract_fields, "contract")
    contract_id = require_label(value.get("contract_id"), "contract.contract_id")
    prereg_base_commit = require_commit(
        value.get("prereg_base_commit"), "contract.prereg_base_commit"
    )
    runtime_source_commit = require_commit(
        value.get("runtime_source_commit"), "contract.runtime_source_commit"
    )
    harness_source_sha256: str | None = None
    surface_source_sha256: str | None = None
    digest_key_sha256: str | None = None
    if version == 1:
        harness_source_sha256 = require_sha256(
            value.get("harness_source_sha256"), "contract.harness_source_sha256"
        )
        if surface.sha256_file(Path(__file__)) != harness_source_sha256:
            raise TrialError("v1 harness source hash does not match the contract")
        surface_source_sha256 = require_sha256(
            value.get("surface_source_sha256"), "contract.surface_source_sha256"
        )
        if surface.sha256_file(Path(surface.__file__)) != surface_source_sha256:
            raise TrialError("v1 surface helper source hash does not match the contract")
        digest_key_sha256 = require_sha256(
            value.get("digest_key_sha256"), "contract.digest_key_sha256"
        )

    raw_conditions = require_list(value.get("conditions"), "contract.conditions")
    condition_ids: list[str] = []
    conditions: list[dict[str, str]] = []
    for index, raw in enumerate(raw_conditions):
        path = f"contract.conditions[{index}]"
        row = require_object(raw, path)
        reject_unknown_fields(row, {"condition_id", "capture"}, path)
        condition_id = require_label(row.get("condition_id"), f"{path}.condition_id")
        capture = require_label(row.get("capture"), f"{path}.capture")
        condition_ids.append(condition_id)
        conditions.append({"condition_id": condition_id, "capture": capture})
    fixed_conditions = EXPANDED_CONDITIONS if version == 1 else CONDITIONS
    if tuple(condition_ids) != fixed_conditions:
        raise TrialError("contract.conditions must match the fixed condition order")
    expected_capture = {
        "hybrid_retrieval": "hybrid_full",
        "compact_then_get_top2": "hybrid_compact_top2_get",
        "session_bootstrap": "session_bootstrap",
        "portfolio_digest": "memory_get_digest",
    }
    if any(row["capture"] != expected_capture[row["condition_id"]] for row in conditions):
        raise TrialError("contract.conditions contains an unsupported capture policy")

    search = require_object(value.get("search"), "contract.search")
    search_fields = {"mode", "limit", "exclude_kinds"}
    if version == 0:
        search_fields.add("compact_get_top_k")
    reject_unknown_fields(search, search_fields, "contract.search")
    mode = require_label(search.get("mode"), "contract.search.mode")
    if mode != "hybrid":
        raise TrialError("contract.search.mode must be hybrid")
    limit = require_nonnegative_int(search.get("limit"), "contract.search.limit")
    if not 2 <= limit <= 100:
        raise TrialError("contract.search.limit must be between 2 and 100")
    top_k: int | None = None
    if version == 0:
        top_k = require_nonnegative_int(
            search.get("compact_get_top_k"), "contract.search.compact_get_top_k"
        )
        if top_k != 2 or top_k > limit:
            raise TrialError("contract compact selection must be deterministic top-2")
    exclude_kinds = [
        require_label(item, f"contract.search.exclude_kinds[{index}]")
        for index, item in enumerate(
            require_list(search.get("exclude_kinds"), "contract.search.exclude_kinds")
        )
    ]
    if len(exclude_kinds) != len(set(exclude_kinds)):
        raise TrialError("contract.search.exclude_kinds contains duplicates")

    bootstrap_limit: int | None = None
    frontend: str | None = None
    if version == 0:
        bootstrap = require_object(value.get("bootstrap"), "contract.bootstrap")
        reject_unknown_fields(bootstrap, {"limit", "frontend"}, "contract.bootstrap")
        bootstrap_limit = require_nonnegative_int(
            bootstrap.get("limit"), "contract.bootstrap.limit"
        )
        if not 1 <= bootstrap_limit <= 100:
            raise TrialError("contract.bootstrap.limit must be between 1 and 100")
        frontend = require_label(bootstrap.get("frontend"), "contract.bootstrap.frontend")
        if frontend not in {"claude-code", "cursor", "warp"}:
            raise TrialError("contract.bootstrap.frontend is unsupported")

    generation = require_object(value.get("generation"), "contract.generation")
    reject_unknown_fields(
        generation,
        {
            "model",
            "reasoning_effort",
            "cli_version",
            "max_answer_chars",
            "answer_instruction",
            "independent_invocations",
            "ephemeral_workspace",
            "tool_use_allowed",
            "external_facts_allowed",
        },
        "contract.generation",
    )
    model = require_string(generation.get("model"), "contract.generation.model", max_chars=128)
    if not MODEL_RE.fullmatch(model):
        raise TrialError("contract.generation.model is malformed")
    reasoning_effort = require_label(
        generation.get("reasoning_effort"), "contract.generation.reasoning_effort"
    )
    if reasoning_effort not in {"low", "medium", "high"}:
        raise TrialError("contract.generation.reasoning_effort is unsupported")
    cli_version = require_string(
        generation.get("cli_version"), "contract.generation.cli_version", max_chars=128
    )
    max_answer_chars = require_nonnegative_int(
        generation.get("max_answer_chars"), "contract.generation.max_answer_chars"
    )
    if not 200 <= max_answer_chars <= 12_000:
        raise TrialError("contract.generation.max_answer_chars is outside bounds")
    answer_instruction = require_string(
        generation.get("answer_instruction"),
        "contract.generation.answer_instruction",
        max_chars=8_000,
    )
    if not require_bool(
        generation.get("independent_invocations"),
        "contract.generation.independent_invocations",
    ):
        raise TrialError("answer generation must use independent invocations")
    if not require_bool(
        generation.get("ephemeral_workspace"), "contract.generation.ephemeral_workspace"
    ):
        raise TrialError("answer generation must use ephemeral workspaces")
    if require_bool(generation.get("tool_use_allowed"), "contract.generation.tool_use_allowed"):
        raise TrialError("answer generation tool use must be disabled")
    if require_bool(
        generation.get("external_facts_allowed"),
        "contract.generation.external_facts_allowed",
    ):
        raise TrialError("answer generation external facts must be disabled")

    blinding = require_object(value.get("blinding"), "contract.blinding")
    reject_unknown_fields(
        blinding,
        {
            "seed_sha256",
            "mapping_private",
            "reviewer_sees_condition",
            "reveal_after_complete_review",
        },
        "contract.blinding",
    )
    seed_sha256 = require_sha256(blinding.get("seed_sha256"), "contract.blinding.seed_sha256")
    for key, expected in {
        "mapping_private": True,
        "reviewer_sees_condition": False,
        "reveal_after_complete_review": True,
    }.items():
        if require_bool(blinding.get(key), f"contract.blinding.{key}") is not expected:
            raise TrialError(f"contract.blinding.{key} violates the blind-review boundary")

    review = require_object(value.get("review"), "contract.review")
    reject_unknown_fields(
        review,
        {
            "claim_score_values",
            "currentness_values",
            "usefulness_min",
            "usefulness_max",
            "preference_tie_label",
            *(
                {
                    "required_reviewer_count",
                    "independent_reviewers",
                    "abstention_values",
                }
                if version == 1
                else set()
            ),
        },
        "contract.review",
    )
    claim_score_values = require_list(
        review.get("claim_score_values"), "contract.review.claim_score_values"
    )
    if claim_score_values != [0, 1, 2]:
        raise TrialError("contract.review.claim_score_values must be [0, 1, 2]")
    currentness_values = [
        require_label(item, f"contract.review.currentness_values[{index}]")
        for index, item in enumerate(
            require_list(
                review.get("currentness_values"), "contract.review.currentness_values"
            )
        )
    ]
    if currentness_values != ["pass", "uncertain", "fail"]:
        raise TrialError("contract.review.currentness_values is not fixed")
    usefulness_min = require_nonnegative_int(
        review.get("usefulness_min"), "contract.review.usefulness_min"
    )
    usefulness_max = require_nonnegative_int(
        review.get("usefulness_max"), "contract.review.usefulness_max"
    )
    if (usefulness_min, usefulness_max) != (1, 5):
        raise TrialError("contract.review usefulness scale must be 1..5")
    preference_tie_label = require_label(
        review.get("preference_tie_label"), "contract.review.preference_tie_label"
    )
    if preference_tie_label != "tie":
        raise TrialError("contract.review preference tie label must be tie")
    abstention_values: list[Any] = []
    if version == 1:
        if require_nonnegative_int(
            review.get("required_reviewer_count"),
            "contract.review.required_reviewer_count",
        ) != 2:
            raise TrialError("v1 requires exactly two independent reviewers")
        if not require_bool(
            review.get("independent_reviewers"),
            "contract.review.independent_reviewers",
        ):
            raise TrialError("v1 reviewers must be independent")
        abstention_values = require_list(
            review.get("abstention_values"),
            "contract.review.abstention_values",
        )
        if abstention_values != [False, True]:
            raise TrialError("v1 abstention values are not fixed")

    thresholds = require_object(value.get("thresholds"), "contract.thresholds")
    threshold_fields = {
        "min_weighted_claim_completeness",
        "max_currentness_failures",
        "max_currentness_uncertain",
        "max_unsupported_assertions",
        "min_mean_usefulness",
        "min_case_usefulness",
        "max_completeness_drop_vs_reference",
        "max_usefulness_drop_vs_reference",
        "min_context_token_reduction_vs_reference",
        "candidate_conditions",
        "recommendation_scope",
    }
    if version == 1:
        threshold_fields.update({"aggregation", "max_abstention_failures"})
    reject_unknown_fields(thresholds, threshold_fields, "contract.thresholds")
    ratio_fields = {
        "min_weighted_claim_completeness",
        "max_completeness_drop_vs_reference",
        "min_context_token_reduction_vs_reference",
    }
    normalized_thresholds: dict[str, Any] = {}
    for key in ratio_fields:
        number = require_finite(thresholds.get(key), f"contract.thresholds.{key}")
        if number > 1:
            raise TrialError(f"contract.thresholds.{key} must be between 0 and 1")
        normalized_thresholds[key] = number
    for key in {
        "max_currentness_failures",
        "max_currentness_uncertain",
        "max_unsupported_assertions",
        "min_case_usefulness",
        *({"max_abstention_failures"} if version == 1 else set()),
    }:
        normalized_thresholds[key] = require_nonnegative_int(
            thresholds.get(key), f"contract.thresholds.{key}"
        )
    mean_usefulness = require_finite(
        thresholds.get("min_mean_usefulness"),
        "contract.thresholds.min_mean_usefulness",
    )
    usefulness_drop = require_finite(
        thresholds.get("max_usefulness_drop_vs_reference"),
        "contract.thresholds.max_usefulness_drop_vs_reference",
    )
    if not usefulness_min <= mean_usefulness <= usefulness_max:
        raise TrialError("contract threshold mean usefulness is outside the review scale")
    if usefulness_drop > usefulness_max - usefulness_min:
        raise TrialError("contract threshold usefulness drop is outside the review scale")
    normalized_thresholds["min_mean_usefulness"] = mean_usefulness
    normalized_thresholds["max_usefulness_drop_vs_reference"] = usefulness_drop
    candidate_conditions = [
        require_label(item, f"contract.thresholds.candidate_conditions[{index}]")
        for index, item in enumerate(
            require_list(
                thresholds.get("candidate_conditions"),
                "contract.thresholds.candidate_conditions",
            )
        )
    ]
    expected_candidates = (
        ["portfolio_digest"]
        if version == 1
        else [COMPACT_CONDITION, "portfolio_digest"]
    )
    if candidate_conditions != expected_candidates:
        raise TrialError("contract candidate conditions are not fixed")
    recommendation_scope = require_label(
        thresholds.get("recommendation_scope"),
        "contract.thresholds.recommendation_scope",
    )
    expected_scope = "write_side_trial_only" if version == 1 else "expanded_trial_only"
    if recommendation_scope != expected_scope:
        raise TrialError(
            f"contract recommendation scope must remain {expected_scope}"
        )
    normalized_thresholds["candidate_conditions"] = candidate_conditions
    normalized_thresholds["recommendation_scope"] = recommendation_scope
    if version == 1:
        aggregation = require_object(
            thresholds.get("aggregation"), "contract.thresholds.aggregation"
        )
        reject_unknown_fields(
            aggregation,
            {"reviewer_gate", "stratum_gate"},
            "contract.thresholds.aggregation",
        )
        normalized_aggregation = {
            "reviewer_gate": require_label(
                aggregation.get("reviewer_gate"),
                "contract.thresholds.aggregation.reviewer_gate",
            ),
            "stratum_gate": require_label(
                aggregation.get("stratum_gate"),
                "contract.thresholds.aggregation.stratum_gate",
            ),
        }
        if normalized_aggregation != {"reviewer_gate": "all", "stratum_gate": "all"}:
            raise TrialError("v1 aggregation gates must both be all")
        normalized_thresholds["aggregation"] = normalized_aggregation
        if normalized_thresholds["max_abstention_failures"] != 0:
            raise TrialError("v1 max_abstention_failures must be zero")

    cases: list[dict[str, Any]] = []
    case_ids: set[str] = set()
    for index, raw in enumerate(require_list(value.get("cases"), "contract.cases")):
        path = f"contract.cases[{index}]"
        case = require_object(raw, path)
        reject_unknown_fields(
            case,
            {
                "case_id",
                "prompt_class",
                "prompt_sha256",
                "required_claims",
                "optional_claims",
                "forbidden_claim_ids",
                *(
                    {"prompt_variant", "requires_abstention"}
                    if version == 1
                    else set()
                ),
            },
            path,
        )
        case_id = require_label(case.get("case_id"), f"{path}.case_id")
        if case_id in case_ids:
            raise TrialError("contract contains duplicate case ids")
        case_ids.add(case_id)
        prompt_class = require_label(case.get("prompt_class"), f"{path}.prompt_class")
        prompt_variant = (
            require_label(case.get("prompt_variant"), f"{path}.prompt_variant")
            if version == 1
            else "legacy"
        )
        if version == 1 and prompt_variant not in {"direct", "heldout"}:
            raise TrialError("v1 prompt_variant must be direct or heldout")
        prompt_sha256 = require_sha256(case.get("prompt_sha256"), f"{path}.prompt_sha256")
        requires_abstention = (
            require_bool(case.get("requires_abstention"), f"{path}.requires_abstention")
            if version == 1
            else False
        )
        required_claims = validate_claims(
            case.get("required_claims"),
            f"{path}.required_claims",
            allow_empty=requires_abstention,
        )
        if version == 1 and requires_abstention and required_claims:
            raise TrialError("v1 abstention cases must have required_claims=[]")
        if version == 1 and not requires_abstention and not required_claims:
            raise TrialError("v1 non-abstention cases require claims")
        optional_claims = validate_claims(
            case.get("optional_claims"), f"{path}.optional_claims", allow_empty=True
        )
        forbidden = [
            require_label(item, f"{path}.forbidden_claim_ids[{item_index}]")
            for item_index, item in enumerate(
                require_list(case.get("forbidden_claim_ids"), f"{path}.forbidden_claim_ids")
            )
        ]
        all_claim_ids = {row["claim_id"] for row in required_claims + optional_claims}
        if len(forbidden) != len(set(forbidden)) or all_claim_ids & set(forbidden):
            raise TrialError(f"{path} has duplicate or overlapping claim ids")
        cases.append(
            {
                "case_id": case_id,
                "prompt_class": prompt_class,
                "prompt_variant": prompt_variant,
                "prompt_sha256": prompt_sha256,
                "required_claims": required_claims,
                "optional_claims": optional_claims,
                "forbidden_claim_ids": forbidden,
                "requires_abstention": requires_abstention,
            }
        )
    if version == 0 and len(cases) != 2:
        raise TrialError("contract must contain exactly two preregistered cases")
    if version == 1:
        if len(cases) != 12:
            raise TrialError("v1 contract must contain exactly 12 preregistered cases")
        strata = Counter(case["prompt_class"] for case in cases)
        if set(strata) != EXPANDED_STRATA or set(strata.values()) != {2}:
            raise TrialError(
                "v1 contract must contain the six fixed prompt strata with two cases each"
            )
        variants_by_stratum = {
            stratum: {
                case["prompt_variant"]
                for case in cases
                if case["prompt_class"] == stratum
            }
            for stratum in strata
        }
        if any(
            variants != {"direct", "heldout"}
            for variants in variants_by_stratum.values()
        ):
            raise TrialError("v1 strata must each contain direct and heldout variants")
        if any(
            all(
                case["requires_abstention"]
                for case in cases
                if case["prompt_class"] == stratum
            )
            for stratum in strata
        ):
            raise TrialError("v1 strata must retain a non-abstention completeness case")
        if sum(case["requires_abstention"] for case in cases) != 2:
            raise TrialError("v1 contract requires exactly two abstention cases")

    boundaries = require_object(value.get("boundaries"), "contract.boundaries")
    expected_boundaries = {
        "raw_artifacts_in_git": False,
        "writes_live_ab_store": False,
        "llm_judge": False,
        "automatic_unblinding": False,
        "runtime_promotion_allowed": False,
        "automatic_digest_regeneration_allowed": False,
        "compact_default_change_allowed": False,
        "benchmark_claim_allowed": False,
        "version_or_tag_change_allowed": False,
        **(
            {"release_action_allowed": False, "ci_action_allowed": False}
            if version == 1
            else {}
        ),
    }
    reject_unknown_fields(boundaries, set(expected_boundaries), "contract.boundaries")
    for key, expected in expected_boundaries.items():
        if require_bool(boundaries.get(key), f"contract.boundaries.{key}") is not expected:
            raise TrialError(f"contract.boundaries.{key} violates the preregistration")

    return {
        "version": version,
        "schema": schema,
        "contract_id": contract_id,
        "prereg_base_commit": prereg_base_commit,
        "runtime_source_commit": runtime_source_commit,
        **(
            {
                "harness_source_sha256": harness_source_sha256,
                "surface_source_sha256": surface_source_sha256,
                "digest_key_sha256": digest_key_sha256,
            }
            if version == 1
            else {}
        ),
        "conditions": conditions,
        "search": {
            "mode": mode,
            "limit": limit,
            "exclude_kinds": exclude_kinds,
            **({"compact_get_top_k": top_k} if version == 0 else {}),
        },
        **(
            {"bootstrap": {"limit": bootstrap_limit, "frontend": frontend}}
            if version == 0
            else {}
        ),
        "generation": {
            "model": model,
            "reasoning_effort": reasoning_effort,
            "cli_version": cli_version,
            "max_answer_chars": max_answer_chars,
            "answer_instruction": answer_instruction,
        },
        "blinding": {"seed_sha256": seed_sha256},
        "review": {
            "claim_score_values": claim_score_values,
            "currentness_values": currentness_values,
            "usefulness_min": usefulness_min,
            "usefulness_max": usefulness_max,
            "preference_tie_label": preference_tie_label,
            **(
                {"required_reviewer_count": 2, "independent_reviewers": True}
                if version == 1
                else {}
            ),
            **({"abstention_values": abstention_values} if version == 1 else {}),
        },
        "thresholds": normalized_thresholds,
        "cases": cases,
        "boundaries": expected_boundaries,
    }


def load_contract(path: Path) -> tuple[dict[str, Any], str]:
    raw, raw_bytes = read_json(path)
    return validate_contract(raw), sha256_bytes(raw_bytes)


def validate_spec(
    value: dict[str, Any], contract: dict[str, Any], contract_sha256: str
) -> dict[str, Any]:
    expected_schema = versioned_schema(contract, SPEC_SCHEMA, SPEC_SCHEMA_V1)
    if value.get("schema") != expected_schema:
        raise TrialError(f"spec schema must be {expected_schema}")
    reject_unknown_fields(
        value,
        {
            "schema",
            "trial_id",
            "contract_sha256",
            "contract_commit",
            "repo",
            "digest_key",
            "blind_seed",
            "cases",
        },
        "spec",
    )
    trial_id = require_label(value.get("trial_id"), "spec.trial_id")
    if require_sha256(value.get("contract_sha256"), "spec.contract_sha256") != contract_sha256:
        raise TrialError("spec.contract_sha256 does not match the checked-in contract")
    contract_commit = require_commit(value.get("contract_commit"), "spec.contract_commit")
    repo = Path(require_string(value.get("repo"), "spec.repo", max_chars=4096))
    if not repo.is_absolute() or not repo.is_dir():
        raise TrialError("spec.repo must be an existing absolute directory")
    digest_key = require_string(value.get("digest_key"), "spec.digest_key", max_chars=256)
    if contract["version"] == 1 and sha256_text(digest_key) != contract[
        "digest_key_sha256"
    ]:
        raise TrialError("spec.digest_key does not match the v1 contract commitment")
    blind_seed = require_string(value.get("blind_seed"), "spec.blind_seed", max_chars=64)
    if not HEX64_RE.fullmatch(blind_seed):
        raise TrialError("spec.blind_seed must be 32 lowercase hex bytes")
    if sha256_text(blind_seed) != contract["blinding"]["seed_sha256"]:
        raise TrialError("spec.blind_seed does not match the preregistered commitment")

    raw_cases = require_list(value.get("cases"), "spec.cases")
    if len(raw_cases) != len(contract["cases"]):
        raise TrialError("spec.cases does not match the contract")
    cases: list[dict[str, Any]] = []
    for index, (raw, contract_case) in enumerate(zip(raw_cases, contract["cases"], strict=True)):
        path = f"spec.cases[{index}]"
        case = require_object(raw, path)
        reject_unknown_fields(case, {"case_id", "prompt"}, path)
        case_id = require_label(case.get("case_id"), f"{path}.case_id")
        if case_id != contract_case["case_id"]:
            raise TrialError("spec case order/id does not match the contract")
        prompt = require_string(case.get("prompt"), f"{path}.prompt", max_chars=16_000)
        if sha256_text(prompt) != contract_case["prompt_sha256"]:
            raise TrialError("spec prompt does not match its preregistered hash")
        cases.append({**contract_case, "prompt": prompt})
    return {
        "trial_id": trial_id,
        "contract_commit": contract_commit,
        "repo": repo,
        "digest_key": digest_key,
        "blind_seed": blind_seed,
        "cases": cases,
    }


def git_head(repo: Path) -> str:
    try:
        completed = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=repo,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise TrialError(f"failed to read repository HEAD: {exc}") from exc
    head = completed.stdout.strip()
    if completed.returncode != 0 or not COMMIT_RE.fullmatch(head):
        raise TrialError("failed to resolve repository HEAD")
    return head


def require_committed_file(
    repo: Path, commit: str, path: Path, label: str
) -> None:
    resolved_repo = repo.resolve()
    resolved_path = path.resolve(strict=True)
    if not resolved_path.is_file() or not resolved_path.is_relative_to(resolved_repo):
        raise TrialError(f"{label} must be a tracked file inside spec.repo")
    relative = resolved_path.relative_to(resolved_repo).as_posix()
    try:
        completed = subprocess.run(
            ["git", "show", f"{commit}:{relative}"],
            cwd=resolved_repo,
            capture_output=True,
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise TrialError(f"failed to verify committed {label}: {exc}") from exc
    if completed.returncode != 0:
        raise TrialError(f"{label} is not tracked at spec.contract_commit")
    if completed.stdout != resolved_path.read_bytes():
        raise TrialError(f"{label} bytes differ from spec.contract_commit")


def require_ignored_data_path(repo: Path, path: Path, label: str) -> Path:
    resolved_repo = repo.resolve()
    resolved_path = path.resolve(strict=False)
    data_root = (resolved_repo / "data").resolve(strict=False)
    if not resolved_path.is_relative_to(data_root):
        raise TrialError(f"{label} must stay under repository data/")
    relative = resolved_path.relative_to(resolved_repo)
    try:
        ignored = subprocess.run(
            ["git", "check-ignore", "-q", "--no-index", "--", str(relative)],
            cwd=resolved_repo,
            capture_output=True,
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise TrialError(f"failed to verify {label} ignore policy: {exc}") from exc
    if ignored.returncode != 0:
        raise TrialError(f"{label} is not ignored by git")
    return resolved_path


def require_distinct_paths(paths: dict[str, Path]) -> None:
    resolved = {label: path.resolve(strict=False) for label, path in paths.items()}
    if len(set(resolved.values())) != len(resolved):
        raise TrialError("trial input/output paths must be distinct")
    identities: dict[tuple[int, int], str] = {}
    for label, path in paths.items():
        try:
            stat = path.stat()
        except FileNotFoundError:
            continue
        except OSError as exc:
            raise TrialError(f"failed to inspect trial path {label}: {exc}") from exc
        identity = surface.file_identity(stat)
        if identity in identities:
            raise TrialError("trial input/output file identities must be distinct")
        identities[identity] = label


def parse_nested_json(text: str, path: str) -> Any:
    try:
        return json.loads(
            text,
            parse_constant=surface.reject_json_constant,
            object_pairs_hook=surface.reject_duplicate_json_keys,
        )
    except json.JSONDecodeError as exc:
        raise TrialError(f"{path} returned invalid nested JSON") from exc


def normalize_compact_search(text: str, limit: int) -> list[dict[str, Any]]:
    raw_hits = require_list(parse_nested_json(text, "compact memory_search"), "compact hits")
    if not 2 <= len(raw_hits) <= limit:
        raise TrialError("compact memory_search returned an unexpected hit count")
    rows: list[dict[str, Any]] = []
    keys: set[str] = set()
    for index, raw in enumerate(raw_hits, start=1):
        path = f"compact hit {index}"
        row = require_object(raw, path)
        reject_unknown_fields(row, COMPACT_FIELDS, path)
        if not COMPACT_REQUIRED_FIELDS.issubset(row):
            raise TrialError("compact hit is missing a required projection field")
        if "record" in row or "content" in row:
            raise TrialError("compact hit leaked a full record/body")
        key = require_string(row.get("key"), f"{path}.key", max_chars=256)
        if key in keys:
            raise TrialError("compact memory_search returned duplicate keys")
        keys.add(key)
        kind = require_string(row.get("kind"), f"{path}.kind", max_chars=128)
        tags = [
            require_string(item, f"{path}.tags[{tag_index}]", max_chars=256)
            for tag_index, item in enumerate(require_list(row.get("tags"), f"{path}.tags"))
        ]
        importance = require_finite(row.get("importance"), f"{path}.importance")
        score = require_finite(row.get("score"), f"{path}.score")
        cosine = row.get("cosine")
        if cosine is not None:
            cosine = require_finite(cosine, f"{path}.cosine")
        preview = row.get("content_preview")
        if not isinstance(preview, str):
            raise TrialError("compact content_preview must be a string")
        content_chars = require_nonnegative_int(row.get("content_chars"), f"{path}.content_chars")
        truncated = require_bool(row.get("content_truncated"), f"{path}.content_truncated")
        expected_preview_chars = min(200, content_chars)
        if len(preview) != expected_preview_chars:
            raise TrialError("compact preview length does not match content_chars")
        if truncated is not (content_chars > 200):
            raise TrialError("compact truncation flag is inconsistent")
        normalized = {
            "key": key,
            "kind": kind,
            "tags": tags,
            "importance": importance,
            "score": score,
            "content_preview": preview,
            "content_chars": content_chars,
            "content_truncated": truncated,
        }
        if cosine is not None:
            normalized["cosine"] = cosine
        rows.append(normalized)
    return rows


def make_context(text: str, latency_ms: float, raw_result: Any) -> dict[str, Any]:
    return {
        "context": text,
        "context_sha256": sha256_text(text),
        "context_bytes": len(text.encode("utf-8")),
        "context_tokens_estimate": surface.estimate_tokens(text),
        "latency_ms": round(latency_ms, 3),
        "raw_result": raw_result,
    }


def initialize_client(client: surface.McpClient) -> dict[str, Any]:
    initialized, _ = client.request(
        "initialize",
        {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {
                "name": "portfolio-continuity-answer-trial",
                "version": "1",
            },
        },
    )
    client.notify("notifications/initialized")
    return require_object(initialized.get("serverInfo"), "initialize.serverInfo")


def run_isolated_mcp(
    *,
    base_snapshot: Path,
    tmpdir: Path,
    run_id: str,
    binary: Path,
    repo: Path,
    timeout: float,
    operation: Callable[[surface.McpClient], dict[str, Any]],
) -> tuple[dict[str, Any], dict[str, Any]]:
    run_db = tmpdir / f"{run_id}.db"
    stderr_path = tmpdir / f"{run_id}.stderr.log"
    try:
        shutil.copyfile(base_snapshot, run_db)
    except OSError as exc:
        raise TrialError(f"failed to clone isolated trial snapshot: {exc}") from exc
    before = surface.sha256_file(run_db)
    client = surface.McpClient(binary, repo, run_db, stderr_path, timeout)
    close_error: TrialError | None = None
    try:
        server_info = initialize_client(client)
        result = operation(client)
    finally:
        try:
            client.close()
        except TrialError as exc:
            close_error = exc
    if close_error is not None:
        raise close_error
    try:
        stderr_bytes = stderr_path.read_bytes()
    except OSError as exc:
        raise TrialError(f"failed to read isolated MCP stderr: {exc}") from exc
    confirmed = str(run_db).encode("utf-8") in stderr_bytes
    if not confirmed:
        raise TrialError("MCP child did not confirm its isolated snapshot path")
    after = surface.sha256_file(run_db)
    metadata = {
        "snapshot_sha256_before": before,
        "snapshot_sha256_after": after,
        "snapshot_path_confirmed": True,
        "stderr_sha256": sha256_bytes(stderr_bytes),
        "stderr_bytes": len(stderr_bytes),
        "server_name": server_info.get("name"),
        "server_version": server_info.get("version"),
    }
    return result, metadata


def capture_trial(
    contract_path: Path,
    spec_path: Path,
    source_db: Path,
    binary: Path,
    raw_output: Path,
    redacted_output: Path,
    timeout: float,
) -> dict[str, Any]:
    protected_inputs = (
        contract_path,
        spec_path,
        source_db,
        binary,
        Path(__file__),
        Path(surface.__file__),
    )
    require_distinct_paths(
        {
            "contract": contract_path,
            "spec": spec_path,
            "source_db": source_db,
            "agent_bridge_binary": binary,
            "harness_source": Path(__file__),
            "surface_source": Path(surface.__file__),
            "raw_output": raw_output,
            "redacted_output": redacted_output,
        }
    )
    contract, contract_sha = load_contract(contract_path)
    conditions = contract_conditions(contract)
    spec_raw, _ = read_json(spec_path)
    spec = validate_spec(spec_raw, contract, contract_sha)
    repo: Path = spec["repo"]
    if git_head(repo) != spec["contract_commit"]:
        raise TrialError("repository HEAD does not match spec.contract_commit")
    if contract["version"] == 1:
        require_committed_file(
            repo, spec["contract_commit"], contract_path, "v1 contract"
        )
        require_committed_file(
            repo, spec["contract_commit"], Path(__file__), "v1 harness source"
        )
        require_committed_file(
            repo,
            spec["contract_commit"],
            Path(surface.__file__),
            "v1 surface helper source",
        )
    if not binary.is_file() or not os.access(binary, os.X_OK):
        raise TrialError("Agent-Bridge binary must be executable")
    if not source_db.is_file():
        raise TrialError("source SQLite database does not exist")
    require_ignored_data_path(repo, raw_output, "raw capture output")
    require_ignored_data_path(repo, redacted_output, "redacted capture output")
    binary_observation = surface.observe_binary_identity(
        binary, repo, contract["runtime_source_commit"], timeout
    )
    captured_at = int(time.time())

    with tempfile.TemporaryDirectory(prefix="ab-answer-trial-") as temporary:
        tmpdir = Path(temporary)
        base_snapshot = tmpdir / "base.snapshot.db"
        surface.sqlite_backup(source_db, base_snapshot)
        if os.path.samefile(source_db, base_snapshot):
            raise TrialError("source DB and base snapshot must differ")
        base_snapshot_sha = surface.sha256_file(base_snapshot)
        cases: list[dict[str, Any]] = []
        runs: list[dict[str, Any]] = []

        for case_index, case in enumerate(spec["cases"], start=1):
            prompt = case["prompt"]

            def full_search(client: surface.McpClient) -> dict[str, Any]:
                result, latency = client.request(
                    "tools/call",
                    {
                        "name": "memory_search",
                        "arguments": {
                            "query": prompt,
                            "mode": contract["search"]["mode"],
                            "compact": False,
                            "limit": contract["search"]["limit"],
                            "exclude_kinds": contract["search"]["exclude_kinds"],
                        },
                    },
                )
                text = surface.mcp_text(result, "full memory_search")
                hits, _ = surface.normalize_search(text)
                keys = [require_string(hit["record"].get("key"), "full hit key") for hit in hits]
                return {"condition": make_context(text, latency, hits), "ranked_keys": keys}

            full_result, full_run = run_isolated_mcp(
                base_snapshot=base_snapshot,
                tmpdir=tmpdir,
                run_id=f"c{case_index}-hybrid-full",
                binary=binary,
                repo=repo,
                timeout=timeout,
                operation=full_search,
            )
            runs.append({"case_id": case["case_id"], "condition": CONDITIONS[0], **full_run})

            def compact_search(client: surface.McpClient) -> dict[str, Any]:
                result, search_latency = client.request(
                    "tools/call",
                    {
                        "name": "memory_search",
                        "arguments": {
                            "query": prompt,
                            "mode": contract["search"]["mode"],
                            "compact": True,
                            "limit": contract["search"]["limit"],
                            "exclude_kinds": contract["search"]["exclude_kinds"],
                        },
                    },
                )
                compact_text = surface.mcp_text(result, "compact memory_search")
                compact_hits = normalize_compact_search(
                    compact_text, contract["search"]["limit"]
                )
                selected_keys = [
                    row["key"]
                    for row in compact_hits[: contract["search"]["compact_get_top_k"]]
                ]
                get_rows: list[dict[str, Any]] = []
                get_texts: list[str] = []
                total_latency = search_latency
                for rank, key in enumerate(selected_keys, start=1):
                    get_result, get_latency = client.request(
                        "tools/call",
                        {"name": "memory_get", "arguments": {"key": key}},
                    )
                    get_text = surface.mcp_text(get_result, f"memory_get rank {rank}")
                    record, _ = surface.normalize_memory_get(get_text)
                    if record.get("key") != key:
                        raise TrialError("compact follow-up memory_get returned the wrong key")
                    total_latency += get_latency
                    get_rows.append(record)
                    get_texts.append(get_text)
                sections = ["=== COMPACT MEMORY SEARCH ===", compact_text]
                for rank, get_text in enumerate(get_texts, start=1):
                    sections.extend([f"=== MEMORY GET RANK {rank} ===", get_text])
                context = "\n".join(sections)
                raw_result = {
                    "compact_hits": compact_hits,
                    "selected_keys": selected_keys,
                    "fetched_records": get_rows,
                    "search_latency_ms": round(search_latency, 3),
                }
                return {
                    "condition": make_context(context, total_latency, raw_result),
                    "ranked_keys": [row["key"] for row in compact_hits],
                    "selected_keys": selected_keys,
                }

            compact_result: dict[str, Any] | None = None
            if COMPACT_CONDITION in conditions:
                compact_result, compact_run = run_isolated_mcp(
                    base_snapshot=base_snapshot,
                    tmpdir=tmpdir,
                    run_id=f"c{case_index}-compact-top2",
                    binary=binary,
                    repo=repo,
                    timeout=timeout,
                    operation=compact_search,
                )
                runs.append(
                    {
                        "case_id": case["case_id"],
                        "condition": COMPACT_CONDITION,
                        **compact_run,
                    }
                )
                if full_result["ranked_keys"] != compact_result["ranked_keys"]:
                    raise TrialError("full and compact hybrid rankings differ")
                if compact_result["selected_keys"] != full_result["ranked_keys"][:2]:
                    raise TrialError("compact follow-up selection is not full-ranking top-2")

            def bootstrap(client: surface.McpClient) -> dict[str, Any]:
                result, latency = client.request(
                    "tools/call",
                    {
                        "name": "session_bootstrap",
                        "arguments": {
                            "cwd": str(repo),
                            "query": prompt,
                            "limit": contract["bootstrap"]["limit"],
                            "frontend": contract["bootstrap"]["frontend"],
                        },
                    },
                )
                text = surface.mcp_text(result, "session_bootstrap")
                blocks = surface.bootstrap_evidence(text)
                return {"condition": make_context(text, latency, {"text": text}), "blocks": len(blocks)}

            bootstrap_result: dict[str, Any] | None = None
            if "session_bootstrap" in conditions:
                bootstrap_result, bootstrap_run = run_isolated_mcp(
                    base_snapshot=base_snapshot,
                    tmpdir=tmpdir,
                    run_id=f"c{case_index}-bootstrap",
                    binary=binary,
                    repo=repo,
                    timeout=timeout,
                    operation=bootstrap,
                )
                runs.append(
                    {
                        "case_id": case["case_id"],
                        "condition": "session_bootstrap",
                        **bootstrap_run,
                    }
                )

            def digest(client: surface.McpClient) -> dict[str, Any]:
                result, latency = client.request(
                    "tools/call",
                    {"name": "memory_get", "arguments": {"key": spec["digest_key"]}},
                )
                text = surface.mcp_text(result, "portfolio digest memory_get")
                record, _ = surface.normalize_memory_get(text)
                if record.get("key") != spec["digest_key"]:
                    raise TrialError("portfolio digest memory_get returned the wrong key")
                return {"condition": make_context(text, latency, record)}

            digest_result, digest_run = run_isolated_mcp(
                base_snapshot=base_snapshot,
                tmpdir=tmpdir,
                run_id=f"c{case_index}-digest",
                binary=binary,
                repo=repo,
                timeout=timeout,
                operation=digest,
            )
            runs.append({"case_id": case["case_id"], "condition": CONDITIONS[3], **digest_run})

            condition_rows = {
                REFERENCE_CONDITION: full_result["condition"],
                "portfolio_digest": digest_result["condition"],
            }
            if compact_result is not None:
                condition_rows[COMPACT_CONDITION] = compact_result["condition"]
            if bootstrap_result is not None:
                condition_rows["session_bootstrap"] = bootstrap_result["condition"]
            cases.append(
                {
                    "case_id": case["case_id"],
                    "prompt_class": case["prompt_class"],
                    **(
                        {"prompt_variant": case["prompt_variant"]}
                        if contract["version"] == 1
                        else {}
                    ),
                    "prompt": prompt,
                    "prompt_sha256": case["prompt_sha256"],
                    "required_claims": case["required_claims"],
                    "optional_claims": case["optional_claims"],
                    "forbidden_claim_ids": case["forbidden_claim_ids"],
                    **(
                        {"requires_abstention": case["requires_abstention"]}
                        if contract["version"] == 1
                        else {}
                    ),
                    "ranking_projection_invariant": COMPACT_CONDITION in conditions,
                    "conditions": {
                        condition: condition_rows[condition] for condition in conditions
                    },
                }
            )

    if any(run["snapshot_sha256_before"] != base_snapshot_sha for run in runs):
        raise TrialError("an isolated condition did not start from the shared base snapshot")
    capture = {
        "schema": versioned_schema(contract, CAPTURE_SCHEMA, CAPTURE_SCHEMA_V1),
        "trial_id": spec["trial_id"],
        "contract_sha256": contract_sha,
        "contract_commit": spec["contract_commit"],
        "captured_at": captured_at,
        "runtime_source_commit": contract["runtime_source_commit"],
        "binary_observation": binary_observation,
        "base_snapshot_sha256": base_snapshot_sha,
        "runs": runs,
        "cases": cases,
        "boundary": {
            "source_db_opened_read_only": True,
            "source_db_passed_to_child": False,
            "one_shared_base_snapshot": True,
            "condition_snapshots_isolated": True,
            "condition_snapshot_paths_confirmed": True,
            "temporary_snapshots_removed": True,
            "writes_live_ab_store": False,
            "calls_llm": False,
            "raw_capture_private": True,
            "ranking_projection_invariant_required": COMPACT_CONDITION in conditions,
        },
    }
    rendered_capture = surface.render_json(capture)
    validate_capture(capture, rendered_capture, contract, contract_sha)
    raw_bytes = write_json(raw_output, capture, protected_paths=protected_inputs)
    if raw_bytes != rendered_capture:
        raise TrialError("capture serialization drifted after validation")
    redacted_cases = []
    for case in cases:
        condition_rows = {}
        for condition in conditions:
            row = case["conditions"][condition]
            raw_result = row["raw_result"]
            if condition == REFERENCE_CONDITION:
                observed_count = len(raw_result)
            elif condition == COMPACT_CONDITION:
                observed_count = len(raw_result["compact_hits"])
            elif condition == "session_bootstrap":
                observed_count = len(surface.bootstrap_evidence(raw_result["text"]))
            else:
                observed_count = 1
            condition_rows[condition] = {
                "context_sha256": row["context_sha256"],
                "context_bytes": row["context_bytes"],
                "context_tokens_estimate": row["context_tokens_estimate"],
                "latency_ms": row["latency_ms"],
                "observed_items": observed_count,
            }
            if condition == COMPACT_CONDITION:
                condition_rows[condition]["memory_get_count"] = len(
                    raw_result["selected_keys"]
                )
        redacted_cases.append(
            {
                "case_id": case["case_id"],
                "prompt_class": case["prompt_class"],
                **(
                    {"prompt_variant": case["prompt_variant"]}
                    if contract["version"] == 1
                    else {}
                ),
                "prompt_sha256": case["prompt_sha256"],
                "ranking_projection_invariant": COMPACT_CONDITION in conditions,
                "conditions": condition_rows,
            }
        )
    redacted = {
        "schema": versioned_schema(
            contract, CAPTURE_REDACTED_SCHEMA, CAPTURE_REDACTED_SCHEMA_V1
        ),
        "trial_id": spec["trial_id"],
        "contract_sha256": contract_sha,
        "contract_commit": spec["contract_commit"],
        "capture_sha256": sha256_bytes(raw_bytes),
        "captured_at": captured_at,
        "runtime_source_commit": contract["runtime_source_commit"],
        "binary_observation": binary_observation,
        "base_snapshot_sha256": base_snapshot_sha,
        "case_count": len(cases),
        "condition_run_count": len(runs),
        "cases": redacted_cases,
        "boundary": {
            "raw_prompt_in_packet": False,
            "raw_context_in_packet": False,
            "raw_memory_key_in_packet": False,
            "writes_live_ab_store": False,
            "calls_llm": False,
        },
    }
    write_json(redacted_output, redacted, protected_paths=protected_inputs)
    return redacted


def validate_capture(
    value: dict[str, Any], capture_bytes: bytes, contract: dict[str, Any], contract_sha: str
) -> dict[str, Any]:
    expected_schema = versioned_schema(contract, CAPTURE_SCHEMA, CAPTURE_SCHEMA_V1)
    if value.get("schema") != expected_schema:
        raise TrialError(f"capture schema must be {expected_schema}")
    condition_ids = contract_conditions(contract)
    reject_unknown_fields(
        value,
        {
            "schema",
            "trial_id",
            "contract_sha256",
            "contract_commit",
            "captured_at",
            "runtime_source_commit",
            "binary_observation",
            "base_snapshot_sha256",
            "runs",
            "cases",
            "boundary",
        },
        "capture",
    )
    if require_sha256(value.get("contract_sha256"), "capture.contract_sha256") != contract_sha:
        raise TrialError("capture contract hash mismatch")
    trial_id = require_label(value.get("trial_id"), "capture.trial_id")
    contract_commit = require_commit(value.get("contract_commit"), "capture.contract_commit")
    captured_at = require_nonnegative_int(value.get("captured_at"), "capture.captured_at")
    if require_commit(
        value.get("runtime_source_commit"), "capture.runtime_source_commit"
    ) != contract["runtime_source_commit"]:
        raise TrialError("capture runtime source does not match the contract")
    require_string(value.get("binary_observation"), "capture.binary_observation", max_chars=4096)
    base_snapshot_sha = require_sha256(
        value.get("base_snapshot_sha256"), "capture.base_snapshot_sha256"
    )
    boundary = require_object(value.get("boundary"), "capture.boundary")
    expected_boundary = {
        "source_db_opened_read_only": True,
        "source_db_passed_to_child": False,
        "one_shared_base_snapshot": True,
        "condition_snapshots_isolated": True,
        "condition_snapshot_paths_confirmed": True,
        "temporary_snapshots_removed": True,
        "writes_live_ab_store": False,
        "calls_llm": False,
        "raw_capture_private": True,
        "ranking_projection_invariant_required": COMPACT_CONDITION in condition_ids,
    }
    reject_unknown_fields(boundary, set(expected_boundary), "capture.boundary")
    if boundary != expected_boundary:
        raise TrialError("capture isolation boundary is incomplete")

    expected_runs = {
        (case["case_id"], condition)
        for case in contract["cases"]
        for condition in condition_ids
    }
    runs = require_list(value.get("runs"), "capture.runs")
    if len(runs) != len(expected_runs):
        raise TrialError("capture isolated run count mismatch")
    seen_runs: set[tuple[str, str]] = set()
    for raw_run in runs:
        run = require_object(raw_run, "capture run")
        reject_unknown_fields(
            run,
            {
                "case_id",
                "condition",
                "snapshot_sha256_before",
                "snapshot_sha256_after",
                "snapshot_path_confirmed",
                "stderr_sha256",
                "stderr_bytes",
                "server_name",
                "server_version",
            },
            "capture run",
        )
        case_id = require_label(run.get("case_id"), "capture run.case_id")
        condition = require_label(run.get("condition"), "capture run.condition")
        identity = (case_id, condition)
        if identity not in expected_runs or identity in seen_runs:
            raise TrialError("capture contains an unknown/duplicate isolated run")
        seen_runs.add(identity)
        if require_sha256(
            run.get("snapshot_sha256_before"), "capture run.snapshot_sha256_before"
        ) != base_snapshot_sha:
            raise TrialError("capture isolated run did not start from the shared snapshot")
        require_sha256(run.get("snapshot_sha256_after"), "capture run.snapshot_sha256_after")
        if require_bool(
            run.get("snapshot_path_confirmed"), "capture run.snapshot_path_confirmed"
        ) is not True:
            raise TrialError("capture isolated run path was not confirmed")
        require_sha256(run.get("stderr_sha256"), "capture run.stderr_sha256")
        require_nonnegative_int(run.get("stderr_bytes"), "capture run.stderr_bytes")
        if run.get("server_name") is not None:
            require_string(run.get("server_name"), "capture run.server_name", max_chars=256)
        if run.get("server_version") is not None:
            require_string(run.get("server_version"), "capture run.server_version", max_chars=256)
    if seen_runs != expected_runs:
        raise TrialError("capture isolated run matrix is incomplete")

    raw_cases = require_list(value.get("cases"), "capture.cases")
    if len(raw_cases) != len(contract["cases"]):
        raise TrialError("capture case count mismatch")
    cases: list[dict[str, Any]] = []
    for raw, contract_case in zip(raw_cases, contract["cases"], strict=True):
        case = require_object(raw, "capture case")
        reject_unknown_fields(
            case,
            {
                "case_id",
                "prompt_class",
                "prompt",
                "prompt_sha256",
                "required_claims",
                "optional_claims",
                "forbidden_claim_ids",
                "ranking_projection_invariant",
                "conditions",
                *(
                    {"prompt_variant", "requires_abstention"}
                    if contract["version"] == 1
                    else set()
                ),
            },
            "capture case",
        )
        if require_label(case.get("case_id"), "capture case_id") != contract_case["case_id"]:
            raise TrialError("capture case id/order mismatch")
        if require_label(case.get("prompt_class"), "capture prompt_class") != contract_case[
            "prompt_class"
        ]:
            raise TrialError("capture prompt class mismatch")
        if contract["version"] == 1 and require_label(
            case.get("prompt_variant"), "capture prompt_variant"
        ) != contract_case["prompt_variant"]:
            raise TrialError("capture prompt variant mismatch")
        prompt = require_string(case.get("prompt"), "capture prompt", max_chars=16_000)
        if sha256_text(prompt) != contract_case["prompt_sha256"]:
            raise TrialError("capture prompt hash mismatch")
        if require_sha256(case.get("prompt_sha256"), "capture prompt_sha256") != contract_case[
            "prompt_sha256"
        ]:
            raise TrialError("capture stored prompt hash mismatch")
        required_claims = validate_claims(
            case.get("required_claims"),
            "capture required_claims",
            allow_empty=contract_case["requires_abstention"],
        )
        optional_claims = validate_claims(
            case.get("optional_claims"), "capture optional_claims", allow_empty=True
        )
        forbidden_claims = [
            require_label(item, f"capture forbidden_claim_ids[{index}]")
            for index, item in enumerate(
                require_list(case.get("forbidden_claim_ids"), "capture forbidden_claim_ids")
            )
        ]
        if (
            required_claims != contract_case["required_claims"]
            or optional_claims != contract_case["optional_claims"]
            or forbidden_claims != contract_case["forbidden_claim_ids"]
        ):
            raise TrialError("capture claim rubric does not match the contract")
        if contract["version"] == 1 and require_bool(
            case.get("requires_abstention"), "capture requires_abstention"
        ) != contract_case["requires_abstention"]:
            raise TrialError("capture abstention flag does not match the contract")
        if case.get("ranking_projection_invariant") is not (
            COMPACT_CONDITION in condition_ids
        ):
            raise TrialError("capture ranking projection invariant failed")
        condition_obj = require_object(case.get("conditions"), "capture conditions")
        if set(condition_obj) != set(condition_ids):
            raise TrialError("capture condition set mismatch")
        conditions: dict[str, dict[str, Any]] = {}
        for condition in condition_ids:
            row = require_object(condition_obj[condition], f"capture condition {condition}")
            reject_unknown_fields(
                row,
                {
                    "context",
                    "context_sha256",
                    "context_bytes",
                    "context_tokens_estimate",
                    "latency_ms",
                    "raw_result",
                },
                f"capture condition {condition}",
            )
            context = require_string(row.get("context"), f"capture {condition}.context")
            context_sha = require_sha256(
                row.get("context_sha256"), f"capture {condition}.context_sha256"
            )
            if sha256_text(context) != context_sha:
                raise TrialError("capture context hash mismatch")
            context_bytes = require_nonnegative_int(
                row.get("context_bytes"), f"capture {condition}.context_bytes"
            )
            if context_bytes != len(context.encode("utf-8")):
                raise TrialError("capture context byte count drifted")
            tokens = require_nonnegative_int(
                row.get("context_tokens_estimate"), f"capture {condition}.tokens"
            )
            if tokens != surface.estimate_tokens(context):
                raise TrialError("capture context token estimate drifted")
            conditions[condition] = {
                **row,
                "context": context,
                "context_sha256": context_sha,
                "context_bytes": context_bytes,
                "context_tokens_estimate": tokens,
                "latency_ms": require_finite(
                    row.get("latency_ms"), f"capture {condition}.latency_ms"
                ),
            }

        full_context = conditions[REFERENCE_CONDITION]["context"]
        full_hits, _ = surface.normalize_search(full_context)
        if conditions[REFERENCE_CONDITION]["raw_result"] != full_hits:
            raise TrialError("capture full-search raw result does not match its context")
        full_keys = [
            require_string(hit["record"].get("key"), "capture full-search key", max_chars=256)
            for hit in full_hits
        ]
        if len(full_keys) != len(set(full_keys)) or (
            COMPACT_CONDITION in condition_ids and len(full_keys) < 2
        ):
            raise TrialError("capture full-search ranking is too short or contains duplicates")

        if COMPACT_CONDITION in condition_ids:
            compact_row = conditions[COMPACT_CONDITION]
            compact_raw = require_object(
                compact_row.get("raw_result"), "capture compact raw_result"
            )
            reject_unknown_fields(
                compact_raw,
                {"compact_hits", "selected_keys", "fetched_records", "search_latency_ms"},
                "capture compact raw_result",
            )
            compact_prefix = "=== COMPACT MEMORY SEARCH ===\n"
            if not compact_row["context"].startswith(compact_prefix):
                raise TrialError("capture compact context framing is malformed")
            compact_body = compact_row["context"][len(compact_prefix) :]
            get_one_marker = "\n=== MEMORY GET RANK 1 ===\n"
            get_two_marker = "\n=== MEMORY GET RANK 2 ===\n"
            if get_one_marker not in compact_body or get_two_marker not in compact_body:
                raise TrialError("capture compact context is missing top-2 follow-up sections")
            compact_text, gets_text = compact_body.split(get_one_marker, 1)
            get_one_text, get_two_text = gets_text.split(get_two_marker, 1)
            compact_hits = normalize_compact_search(compact_text, contract["search"]["limit"])
            if compact_raw.get("compact_hits") != compact_hits:
                raise TrialError("capture compact raw hits do not match the context")
            compact_keys = [row["key"] for row in compact_hits]
            if compact_keys != full_keys:
                raise TrialError("capture full and compact rankings differ")
            selected_keys = [
                require_string(item, f"capture compact selected_keys[{index}]", max_chars=256)
                for index, item in enumerate(
                    require_list(
                        compact_raw.get("selected_keys"),
                        "capture compact selected_keys",
                    )
                )
            ]
            if selected_keys != compact_keys[:2]:
                raise TrialError("capture compact follow-up selection is not rank-only top-2")
            fetched_records = require_list(
                compact_raw.get("fetched_records"), "capture compact fetched_records"
            )
            if len(fetched_records) != 2:
                raise TrialError("capture compact follow-up record count is not two")
            parsed_gets = [
                surface.normalize_memory_get(get_one_text)[0],
                surface.normalize_memory_get(get_two_text)[0],
            ]
            if fetched_records != parsed_gets:
                raise TrialError("capture compact fetched records do not match the context")
            if [record.get("key") for record in parsed_gets] != selected_keys:
                raise TrialError("capture compact fetched record keys do not match top-2")
            require_finite(
                compact_raw.get("search_latency_ms"), "capture compact search_latency_ms"
            )

        if "session_bootstrap" in condition_ids:
            bootstrap_raw = require_object(
                conditions["session_bootstrap"].get("raw_result"),
                "capture bootstrap raw_result",
            )
            reject_unknown_fields(bootstrap_raw, {"text"}, "capture bootstrap raw_result")
            if bootstrap_raw.get("text") != conditions["session_bootstrap"]["context"]:
                raise TrialError("capture bootstrap raw result does not match its context")
            surface.bootstrap_evidence(conditions["session_bootstrap"]["context"])

        digest_raw = require_object(
            conditions["portfolio_digest"].get("raw_result"), "capture digest raw_result"
        )
        digest_context = require_object(
            parse_nested_json(conditions["portfolio_digest"]["context"], "capture digest"),
            "capture digest context",
        )
        if digest_raw != digest_context:
            raise TrialError("capture digest raw result does not match its context")
        digest_key = require_string(
            digest_raw.get("key"), "capture digest key", max_chars=256
        )
        if contract["version"] == 1 and sha256_text(digest_key) != contract[
            "digest_key_sha256"
        ]:
            raise TrialError("capture digest key does not match the v1 commitment")
        require_string(digest_raw.get("content"), "capture digest content")

        cases.append({**contract_case, "prompt": prompt, "conditions": conditions})
    return {
        "trial_id": trial_id,
        "contract_commit": contract_commit,
        "captured_at": captured_at,
        "capture_sha256": sha256_bytes(capture_bytes),
        "cases": cases,
    }


def observe_codex_identity(binary: Path, expected: str, timeout: float) -> str:
    if not binary.is_file() or not os.access(binary, os.X_OK):
        raise TrialError("Codex binary must be executable")
    try:
        completed = subprocess.run(
            [str(binary), "--version"],
            env=os.environ.copy(),
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=min(timeout, 30.0),
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise TrialError(f"failed to observe Codex identity: {exc}") from exc
    observation = "\n".join(
        part.strip() for part in (completed.stdout, completed.stderr) if part.strip()
    )
    if completed.returncode != 0 or observation != expected:
        raise TrialError("Codex identity does not match the preregistered version")
    return observation


def contains_tool_event(value: Any) -> bool:
    if isinstance(value, dict):
        for key, child in value.items():
            if key == "type" and isinstance(child, str) and child in TOOL_EVENT_MARKERS:
                return True
            if contains_tool_event(child):
                return True
    elif isinstance(value, list):
        return any(contains_tool_event(child) for child in value)
    return False


def parse_codex_events(stdout: str) -> Counter[str]:
    counts: Counter[str] = Counter()
    for index, line in enumerate(stdout.splitlines(), start=1):
        if not line.strip():
            continue
        try:
            event = json.loads(
                line,
                parse_constant=surface.reject_json_constant,
                object_pairs_hook=surface.reject_duplicate_json_keys,
            )
        except json.JSONDecodeError as exc:
            raise TrialError("Codex JSONL event stream is malformed") from exc
        event = require_object(event, f"Codex event {index}")
        event_type = event.get("type")
        if isinstance(event_type, str):
            counts[event_type] += 1
        if contains_tool_event(event):
            raise TrialError("Codex generation attempted tool use")
    if not counts:
        raise TrialError("Codex generation returned no JSONL events")
    return counts


def codex_env() -> dict[str, str]:
    denied_prefixes = ("AGENT_BRIDGE_", "MCP_")
    env = {
        key: value
        for key, value in os.environ.items()
        if not key.startswith(denied_prefixes)
    }
    env["NO_COLOR"] = "1"
    return env


def build_generation_prompt(contract: dict[str, Any], question: str, context: str) -> str:
    return (
        contract["generation"]["answer_instruction"].rstrip()
        + "\n\n=== QUESTION ===\n"
        + question
        + "\n\n=== EVIDENCE CONTEXT ===\n"
        + context
        + "\n\n=== END EVIDENCE CONTEXT ===\n"
    )


def generate_one_answer(
    *,
    codex_binary: Path,
    contract: dict[str, Any],
    question: str,
    context: str,
    extra_forbidden_markers: set[str] | None,
    timeout: float,
) -> dict[str, Any]:
    generation = contract["generation"]
    prompt = build_generation_prompt(contract, question, context)
    with tempfile.TemporaryDirectory(prefix="ab-answer-generation-") as temporary:
        tmpdir = Path(temporary)
        schema_path = tmpdir / "answer.schema.json"
        output_path = tmpdir / "answer.json"
        write_json(
            schema_path,
            {
                "type": "object",
                "additionalProperties": False,
                "required": ["answer_markdown"],
                "properties": {
                    "answer_markdown": {
                        "type": "string",
                        "minLength": 1,
                        "maxLength": generation["max_answer_chars"],
                    }
                },
            },
        )
        command = [
            str(codex_binary),
            "exec",
            "--json",
            "--ephemeral",
            "--ignore-user-config",
            "--ignore-rules",
            "--skip-git-repo-check",
            "--sandbox",
            "read-only",
            "--color",
            "never",
            "--model",
            generation["model"],
            "-c",
            f'model_reasoning_effort="{generation["reasoning_effort"]}"',
            "--output-schema",
            str(schema_path),
            "--output-last-message",
            str(output_path),
            "-C",
            str(tmpdir),
            "-",
        ]
        started = time.perf_counter()
        try:
            completed = subprocess.run(
                command,
                input=prompt,
                env=codex_env(),
                capture_output=True,
                text=True,
                encoding="utf-8",
                timeout=timeout,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise TrialError(f"Codex generation failed to complete: {exc}") from exc
        latency_ms = (time.perf_counter() - started) * 1000.0
        if completed.returncode != 0:
            raise TrialError("Codex generation exited unsuccessfully")
        if len(completed.stdout.encode("utf-8")) > 2_000_000:
            raise TrialError("Codex JSONL event stream is unexpectedly large")
        if len(completed.stderr.encode("utf-8")) > 256_000:
            raise TrialError("Codex stderr is unexpectedly large")
        event_counts = parse_codex_events(completed.stdout)
        answer_packet, answer_bytes = read_json(output_path)
        reject_unknown_fields(answer_packet, {"answer_markdown"}, "Codex answer")
        answer = require_string(
            answer_packet.get("answer_markdown"),
            "Codex answer.answer_markdown",
            max_chars=generation["max_answer_chars"],
        ).strip()
        forbidden_markers = set(CONDITIONS) | {
            "portfolio_state_digest",
            "=== EVIDENCE CONTEXT ===",
        }
        if extra_forbidden_markers is not None:
            forbidden_markers.update(extra_forbidden_markers)
        if any(marker in answer for marker in forbidden_markers):
            raise TrialError("Codex answer leaked a condition/evidence marker")
        return {
            "answer_markdown": answer,
            "answer_sha256": sha256_text(answer),
            "answer_chars": len(answer),
            "latency_ms": round(latency_ms, 3),
            "prompt_sha256": sha256_text(prompt),
            "output_packet_sha256": sha256_bytes(answer_bytes),
            "event_counts": dict(sorted(event_counts.items())),
            "stdout_jsonl": completed.stdout,
            "stdout_sha256": sha256_text(completed.stdout),
            "stderr": completed.stderr,
            "stderr_sha256": sha256_text(completed.stderr),
            "stderr_bytes": len(completed.stderr.encode("utf-8")),
        }


def answer_id(seed: str, case_id: str, condition: str) -> str:
    return "ans_" + sha256_text(f"{seed}\0answer-id\0{case_id}\0{condition}")[:24]


def blind_order(seed: str, case_id: str, condition: str) -> str:
    return sha256_text(f"{seed}\0blind-order\0{case_id}\0{condition}")


def generation_order(seed: str, case_id: str, condition: str) -> str:
    return sha256_text(f"{seed}\0generation-order\0{case_id}\0{condition}")


def generate_trial(
    contract_path: Path,
    spec_path: Path,
    capture_path: Path,
    codex_binary: Path,
    generation_output: Path,
    blind_output: Path,
    map_output: Path,
    review_template_output: Path,
    redacted_output: Path,
    timeout: float,
) -> dict[str, Any]:
    protected_inputs = (
        contract_path,
        spec_path,
        capture_path,
        codex_binary,
        Path(__file__),
        Path(surface.__file__),
    )
    output_paths = {
        "generation_output": generation_output,
        "blind_output": blind_output,
        "map_output": map_output,
        "review_template_output": review_template_output,
        "redacted_output": redacted_output,
    }
    require_distinct_paths(
        {
            "contract": contract_path,
            "spec": spec_path,
            "capture": capture_path,
            "codex_binary": codex_binary,
            "harness_source": Path(__file__),
            "surface_source": Path(surface.__file__),
            **output_paths,
        }
    )
    contract, contract_sha = load_contract(contract_path)
    conditions = contract_conditions(contract)
    spec_raw, _ = read_json(spec_path)
    spec = validate_spec(spec_raw, contract, contract_sha)
    capture_raw, capture_bytes = read_json(capture_path)
    capture = validate_capture(capture_raw, capture_bytes, contract, contract_sha)
    if capture["trial_id"] != spec["trial_id"] or capture["contract_commit"] != spec["contract_commit"]:
        raise TrialError("capture/spec trial identity mismatch")
    repo: Path = spec["repo"]
    if git_head(repo) != spec["contract_commit"]:
        raise TrialError("repository HEAD does not match the preregistered capture commit")
    if contract["version"] == 1:
        require_committed_file(
            repo, spec["contract_commit"], contract_path, "v1 contract"
        )
        require_committed_file(
            repo, spec["contract_commit"], Path(__file__), "v1 harness source"
        )
        require_committed_file(
            repo,
            spec["contract_commit"],
            Path(surface.__file__),
            "v1 surface helper source",
        )
    for label, path in output_paths.items():
        require_ignored_data_path(repo, path, label)
    codex_observation = observe_codex_identity(
        codex_binary, contract["generation"]["cli_version"], timeout
    )

    jobs = [
        (case, condition)
        for case in capture["cases"]
        for condition in conditions
    ]
    jobs.sort(key=lambda item: generation_order(spec["blind_seed"], item[0]["case_id"], item[1]))
    answers_by_case: dict[str, dict[str, dict[str, Any]]] = {
        case["case_id"]: {} for case in capture["cases"]
    }
    for invocation_index, (case, condition) in enumerate(jobs, start=1):
        generated = generate_one_answer(
            codex_binary=codex_binary,
            contract=contract,
            question=case["prompt"],
            context=case["conditions"][condition]["context"],
            extra_forbidden_markers=(
                {spec["digest_key"]} if contract["version"] == 1 else None
            ),
            timeout=timeout,
        )
        generated["invocation_index"] = invocation_index
        generated["context_sha256"] = case["conditions"][condition]["context_sha256"]
        generated["context_tokens_estimate"] = case["conditions"][condition][
            "context_tokens_estimate"
        ]
        answers_by_case[case["case_id"]][condition] = generated

    generated_at = int(time.time())
    generation_cases = []
    for case in capture["cases"]:
        generation_cases.append(
            {
                "case_id": case["case_id"],
                "prompt_class": case["prompt_class"],
                **(
                    {"prompt_variant": case["prompt_variant"]}
                    if contract["version"] == 1
                    else {}
                ),
                "prompt": case["prompt"],
                "prompt_sha256": case["prompt_sha256"],
                "required_claims": case["required_claims"],
                "optional_claims": case["optional_claims"],
                "forbidden_claim_ids": case["forbidden_claim_ids"],
                "answers": {
                    condition: answers_by_case[case["case_id"]][condition]
                    for condition in conditions
                },
                **(
                    {"requires_abstention": case["requires_abstention"]}
                    if contract["version"] == 1
                    else {}
                ),
            }
        )
    generation_packet = {
        "schema": versioned_schema(contract, GENERATION_SCHEMA, GENERATION_SCHEMA_V1),
        "trial_id": spec["trial_id"],
        "contract_sha256": contract_sha,
        "contract_commit": spec["contract_commit"],
        "capture_sha256": capture["capture_sha256"],
        "generated_at": generated_at,
        "codex_observation": codex_observation,
        "model": contract["generation"]["model"],
        "reasoning_effort": contract["generation"]["reasoning_effort"],
        "cases": generation_cases,
        "boundary": {
            "independent_invocations": True,
            "ephemeral_empty_workspaces": True,
            "read_only_sandbox": True,
            "user_config_ignored": True,
            "project_rules_ignored": True,
            "tool_events_observed": False,
            "external_facts_allowed": False,
            "raw_generation_private": True,
        },
    }
    generation_bytes = write_json(
        generation_output,
        generation_packet,
        protected_paths=protected_inputs,
    )
    generation_sha = sha256_bytes(generation_bytes)

    blind_cases: list[dict[str, Any]] = []
    mapping_cases: list[dict[str, Any]] = []
    review_cases: list[dict[str, Any]] = []
    for case in capture["cases"]:
        ordered_conditions = sorted(
            conditions,
            key=lambda condition: blind_order(spec["blind_seed"], case["case_id"], condition),
        )
        blind_answers = []
        mappings = []
        review_answers = []
        for condition in ordered_conditions:
            generated = answers_by_case[case["case_id"]][condition]
            opaque_id = answer_id(spec["blind_seed"], case["case_id"], condition)
            blind_answers.append(
                {"answer_id": opaque_id, "answer_markdown": generated["answer_markdown"]}
            )
            mappings.append(
                {
                    "answer_id": opaque_id,
                    "condition": condition,
                    "answer_sha256": generated["answer_sha256"],
                    "context_sha256": generated["context_sha256"],
                }
            )
            review_answers.append(
                {
                    "answer_id": opaque_id,
                    "claim_scores": [
                        {"claim_id": claim["claim_id"], "score": None}
                        for claim in case["required_claims"]
                    ],
                    "currentness": None,
                    "unsupported_assertion_count": None,
                    "usefulness": None,
                    "notes": "",
                    **(
                        {"abstention_pass": None}
                        if contract["version"] == 1 and case["requires_abstention"]
                        else {}
                    ),
                }
            )
        blind_cases.append(
            {
                "case_id": case["case_id"],
                "prompt_class": case["prompt_class"],
                **(
                    {"prompt_variant": case["prompt_variant"]}
                    if contract["version"] == 1
                    else {}
                ),
                "question": case["prompt"],
                "required_claims": case["required_claims"],
                "optional_claims": case["optional_claims"],
                "forbidden_claim_ids": case["forbidden_claim_ids"],
                **(
                    {"requires_abstention": case["requires_abstention"]}
                    if contract["version"] == 1
                    else {}
                ),
                "answers": blind_answers,
            }
        )
        mapping_cases.append({"case_id": case["case_id"], "answers": mappings})
        review_cases.append(
            {
                "case_id": case["case_id"],
                "answers": review_answers,
                "preferred_answer_id": None,
            }
        )
    blind_packet = {
        "schema": versioned_schema(
            contract, BLIND_PACKET_SCHEMA, BLIND_PACKET_SCHEMA_V1
        ),
        "trial_id": spec["trial_id"],
        "contract_sha256": contract_sha,
        "contract_commit": spec["contract_commit"],
        "capture_sha256": capture["capture_sha256"],
        "generation_sha256": generation_sha,
        "review_scale": contract["review"],
        "cases": blind_cases,
        "boundary": {
            "condition_labels_present": False,
            "condition_mapping_present": False,
            "raw_context_present": False,
            "owner_review_required": True,
            **(
                {"required_reviewer_count": contract["review"]["required_reviewer_count"]}
                if contract["version"] == 1
                else {}
            ),
            "unblinding_allowed": False,
        },
    }
    blind_bytes = write_json(
        blind_output, blind_packet, protected_paths=protected_inputs
    )
    blind_sha = sha256_bytes(blind_bytes)
    mapping_packet = {
        "schema": versioned_schema(contract, BLIND_MAP_SCHEMA, BLIND_MAP_SCHEMA_V1),
        "trial_id": spec["trial_id"],
        "contract_sha256": contract_sha,
        "capture_sha256": capture["capture_sha256"],
        "generation_sha256": generation_sha,
        "blind_packet_sha256": blind_sha,
        "blind_seed": spec["blind_seed"],
        "blind_seed_sha256": sha256_text(spec["blind_seed"]),
        "cases": mapping_cases,
        "boundary": {"mapping_private": True, "reviewer_must_not_read_before_review": True},
    }
    mapping_bytes = write_json(
        map_output, mapping_packet, protected_paths=protected_inputs
    )
    review_template = {
        "schema": versioned_schema(contract, REVIEW_SCHEMA, REVIEW_SCHEMA_V1),
        "trial_id": spec["trial_id"],
        "blind_packet_sha256": blind_sha,
        "reviewer": "",
        "reviewed_at": 0,
        **(
            {"independent_review": False, "condition_blinded": False}
            if contract["version"] == 1
            else {}
        ),
        "cases": review_cases,
    }
    review_bytes = write_json(
        review_template_output,
        review_template,
        protected_paths=protected_inputs,
    )
    answer_lengths = [
        generated["answer_chars"]
        for answers in answers_by_case.values()
        for generated in answers.values()
    ]
    generation_latencies = [
        generated["latency_ms"]
        for answers in answers_by_case.values()
        for generated in answers.values()
    ]
    redacted = {
        "schema": versioned_schema(
            contract, GENERATION_REDACTED_SCHEMA, GENERATION_REDACTED_SCHEMA_V1
        ),
        "trial_id": spec["trial_id"],
        "contract_sha256": contract_sha,
        "contract_commit": spec["contract_commit"],
        "capture_sha256": capture["capture_sha256"],
        "generation_sha256": generation_sha,
        "blind_packet_sha256": blind_sha,
        "blind_map_sha256": sha256_bytes(mapping_bytes),
        "review_template_sha256": sha256_bytes(review_bytes),
        "generated_at": generated_at,
        "codex_observation": codex_observation,
        "model": contract["generation"]["model"],
        "reasoning_effort": contract["generation"]["reasoning_effort"],
        "case_count": len(capture["cases"]),
        "condition_count": len(conditions),
        "answer_count": len(answer_lengths),
        "answer_chars_total": sum(answer_lengths),
        "answer_chars_min": min(answer_lengths),
        "answer_chars_max": max(answer_lengths),
        "generation_latency_ms_total": round(sum(generation_latencies), 3),
        "generation_latency_ms_p95": round(surface.percentile_95(generation_latencies), 3),
        "status": (
            "WAIT_TWO_BLIND_REVIEWS"
            if contract["version"] == 1
            else "WAIT_OWNER_BLIND_REVIEW"
        ),
        "boundary": {
            "raw_prompt_in_packet": False,
            "raw_context_in_packet": False,
            "raw_answer_in_packet": False,
            "answer_id_in_packet": False,
            "condition_mapping_in_packet": False,
            "tool_events_observed": False,
            "automatic_unblinding": False,
            "runtime_promotion_allowed": False,
        },
    }
    write_json(redacted_output, redacted, protected_paths=protected_inputs)
    return redacted


def validate_generation(
    value: dict[str, Any],
    raw_bytes: bytes,
    contract: dict[str, Any],
    contract_sha: str,
    capture: dict[str, Any],
) -> dict[str, Any]:
    expected_schema = versioned_schema(contract, GENERATION_SCHEMA, GENERATION_SCHEMA_V1)
    if value.get("schema") != expected_schema:
        raise TrialError(f"generation schema must be {expected_schema}")
    condition_ids = contract_conditions(contract)
    reject_unknown_fields(
        value,
        {
            "schema",
            "trial_id",
            "contract_sha256",
            "contract_commit",
            "capture_sha256",
            "generated_at",
            "codex_observation",
            "model",
            "reasoning_effort",
            "cases",
            "boundary",
        },
        "generation",
    )
    if require_label(value.get("trial_id"), "generation.trial_id") != capture["trial_id"]:
        raise TrialError("generation trial id mismatch")
    if require_sha256(
        value.get("contract_sha256"), "generation.contract_sha256"
    ) != contract_sha:
        raise TrialError("generation contract hash mismatch")
    if require_commit(
        value.get("contract_commit"), "generation.contract_commit"
    ) != capture["contract_commit"]:
        raise TrialError("generation contract commit mismatch")
    if require_sha256(
        value.get("capture_sha256"), "generation.capture_sha256"
    ) != capture["capture_sha256"]:
        raise TrialError("generation capture hash mismatch")
    generated_at = require_nonnegative_int(value.get("generated_at"), "generation.generated_at")
    if generated_at <= 0:
        raise TrialError("generation timestamp is missing")
    if require_string(
        value.get("codex_observation"), "generation.codex_observation", max_chars=128
    ) != contract["generation"]["cli_version"]:
        raise TrialError("generation Codex identity mismatch")
    if require_string(value.get("model"), "generation.model", max_chars=128) != contract[
        "generation"
    ]["model"]:
        raise TrialError("generation model mismatch")
    if require_label(
        value.get("reasoning_effort"), "generation.reasoning_effort"
    ) != contract["generation"]["reasoning_effort"]:
        raise TrialError("generation reasoning effort mismatch")
    boundary = require_object(value.get("boundary"), "generation.boundary")
    expected_boundary = {
        "independent_invocations": True,
        "ephemeral_empty_workspaces": True,
        "read_only_sandbox": True,
        "user_config_ignored": True,
        "project_rules_ignored": True,
        "tool_events_observed": False,
        "external_facts_allowed": False,
        "raw_generation_private": True,
    }
    reject_unknown_fields(boundary, set(expected_boundary), "generation.boundary")
    if boundary != expected_boundary:
        raise TrialError("generation boundary is incomplete")

    raw_cases = require_list(value.get("cases"), "generation.cases")
    if len(raw_cases) != len(capture["cases"]):
        raise TrialError("generation case count mismatch")
    answers: dict[str, dict[str, dict[str, Any]]] = {}
    invocation_indexes: set[int] = set()
    for raw_case, capture_case in zip(raw_cases, capture["cases"], strict=True):
        case = require_object(raw_case, "generation case")
        reject_unknown_fields(
            case,
            {
                "case_id",
                "prompt_class",
                "prompt",
                "prompt_sha256",
                "required_claims",
                "optional_claims",
                "forbidden_claim_ids",
                "answers",
                *(
                    {"prompt_variant", "requires_abstention"}
                    if contract["version"] == 1
                    else set()
                ),
            },
            "generation case",
        )
        case_id = require_label(case.get("case_id"), "generation case_id")
        if case_id != capture_case["case_id"]:
            raise TrialError("generation case id/order mismatch")
        if require_label(case.get("prompt_class"), "generation prompt_class") != capture_case[
            "prompt_class"
        ]:
            raise TrialError("generation prompt class mismatch")
        if contract["version"] == 1 and require_label(
            case.get("prompt_variant"), "generation prompt_variant"
        ) != capture_case["prompt_variant"]:
            raise TrialError("generation prompt variant mismatch")
        prompt = require_string(case.get("prompt"), "generation prompt", max_chars=16_000)
        if prompt != capture_case["prompt"]:
            raise TrialError("generation prompt differs from capture")
        if require_sha256(
            case.get("prompt_sha256"), "generation prompt_sha256"
        ) != capture_case["prompt_sha256"]:
            raise TrialError("generation prompt hash mismatch")
        if (
            validate_claims(
                case.get("required_claims"),
                "generation required_claims",
                allow_empty=capture_case["requires_abstention"],
            )
            != capture_case["required_claims"]
            or validate_claims(
                case.get("optional_claims"),
                "generation optional_claims",
                allow_empty=True,
            )
            != capture_case["optional_claims"]
            or [
                require_label(item, f"generation forbidden_claim_ids[{index}]")
                for index, item in enumerate(
                    require_list(
                        case.get("forbidden_claim_ids"),
                        "generation forbidden_claim_ids",
                    )
                )
            ]
            != capture_case["forbidden_claim_ids"]
        ):
            raise TrialError("generation claim rubric differs from capture")
        if contract["version"] == 1 and require_bool(
            case.get("requires_abstention"), "generation requires_abstention"
        ) != capture_case["requires_abstention"]:
            raise TrialError("generation abstention flag differs from capture")
        raw_answers = require_object(case.get("answers"), "generation answers")
        if set(raw_answers) != set(condition_ids):
            raise TrialError("generation condition set mismatch")
        case_answers: dict[str, dict[str, Any]] = {}
        for condition in condition_ids:
            path = f"generation answer {condition}"
            row = require_object(raw_answers[condition], path)
            reject_unknown_fields(
                row,
                {
                    "answer_markdown",
                    "answer_sha256",
                    "answer_chars",
                    "latency_ms",
                    "prompt_sha256",
                    "output_packet_sha256",
                    "event_counts",
                    "stdout_jsonl",
                    "stdout_sha256",
                    "stderr",
                    "stderr_sha256",
                    "stderr_bytes",
                    "invocation_index",
                    "context_sha256",
                    "context_tokens_estimate",
                },
                path,
            )
            answer = require_string(
                row.get("answer_markdown"),
                f"{path}.answer_markdown",
                max_chars=contract["generation"]["max_answer_chars"],
            )
            answer_sha = require_sha256(row.get("answer_sha256"), f"{path}.answer_sha256")
            if sha256_text(answer) != answer_sha:
                raise TrialError("generation answer hash mismatch")
            if require_nonnegative_int(row.get("answer_chars"), f"{path}.answer_chars") != len(
                answer
            ):
                raise TrialError("generation answer character count mismatch")
            require_finite(row.get("latency_ms"), f"{path}.latency_ms")
            context = capture_case["conditions"][condition]
            context_sha = require_sha256(
                row.get("context_sha256"), f"{path}.context_sha256"
            )
            if context_sha != context["context_sha256"]:
                raise TrialError("generation answer context hash mismatch")
            if require_nonnegative_int(
                row.get("context_tokens_estimate"), f"{path}.context_tokens_estimate"
            ) != context["context_tokens_estimate"]:
                raise TrialError("generation answer context token count mismatch")
            expected_prompt = build_generation_prompt(contract, prompt, context["context"])
            if require_sha256(
                row.get("prompt_sha256"), f"{path}.prompt_sha256"
            ) != sha256_text(expected_prompt):
                raise TrialError("generation invocation prompt hash mismatch")
            require_sha256(
                row.get("output_packet_sha256"), f"{path}.output_packet_sha256"
            )
            stdout_jsonl = require_string(
                row.get("stdout_jsonl"), f"{path}.stdout_jsonl", max_chars=2_000_000
            )
            if require_sha256(
                row.get("stdout_sha256"), f"{path}.stdout_sha256"
            ) != sha256_text(stdout_jsonl):
                raise TrialError("generation stdout hash mismatch")
            stderr = row.get("stderr")
            if not isinstance(stderr, str) or len(stderr) > 256_000:
                raise TrialError("generation stderr is malformed")
            if require_sha256(
                row.get("stderr_sha256"), f"{path}.stderr_sha256"
            ) != sha256_text(stderr):
                raise TrialError("generation stderr hash mismatch")
            if require_nonnegative_int(
                row.get("stderr_bytes"), f"{path}.stderr_bytes"
            ) != len(stderr.encode("utf-8")):
                raise TrialError("generation stderr byte count mismatch")
            observed_event_counts = dict(sorted(parse_codex_events(stdout_jsonl).items()))
            event_counts = require_object(row.get("event_counts"), f"{path}.event_counts")
            for event_type, count in event_counts.items():
                require_string(event_type, f"{path}.event_type", max_chars=128)
                require_nonnegative_int(count, f"{path}.event_count")
                if event_type in TOOL_EVENT_MARKERS:
                    raise TrialError("generation event counts contain tool use")
            if event_counts != observed_event_counts:
                raise TrialError("generation event counts do not match the JSONL stream")
            invocation_index = require_nonnegative_int(
                row.get("invocation_index"), f"{path}.invocation_index"
            )
            if not 1 <= invocation_index <= len(condition_ids) * len(capture["cases"]):
                raise TrialError("generation invocation index is outside the fixed matrix")
            if invocation_index in invocation_indexes:
                raise TrialError("generation invocation index is duplicated")
            invocation_indexes.add(invocation_index)
            case_answers[condition] = {
                "answer_markdown": answer,
                "answer_sha256": answer_sha,
                "context_sha256": context_sha,
                "invocation_index": invocation_index,
            }
        answers[case_id] = case_answers
    if invocation_indexes != set(
        range(1, len(condition_ids) * len(capture["cases"]) + 1)
    ):
        raise TrialError("generation invocation matrix is incomplete")
    return {
        "generation_sha256": sha256_bytes(raw_bytes),
        "generated_at": generated_at,
        "answers": answers,
    }


def validate_blind_packet(
    value: dict[str, Any],
    raw_bytes: bytes,
    contract: dict[str, Any],
    contract_sha: str,
    capture: dict[str, Any],
    generation: dict[str, Any] | None,
) -> dict[str, Any]:
    expected_schema = versioned_schema(
        contract, BLIND_PACKET_SCHEMA, BLIND_PACKET_SCHEMA_V1
    )
    if value.get("schema") != expected_schema:
        raise TrialError(f"blind packet schema must be {expected_schema}")
    condition_ids = contract_conditions(contract)
    reject_unknown_fields(
        value,
        {
            "schema",
            "trial_id",
            "contract_sha256",
            "contract_commit",
            "capture_sha256",
            "generation_sha256",
            "review_scale",
            "cases",
            "boundary",
        },
        "blind packet",
    )
    trial_id = require_label(value.get("trial_id"), "blind.trial_id")
    if trial_id != capture["trial_id"]:
        raise TrialError("blind packet trial id mismatch")
    observed_contract_sha = require_sha256(
        value.get("contract_sha256"), "blind.contract_sha256"
    )
    if observed_contract_sha != contract_sha:
        raise TrialError("blind packet contract hash mismatch")
    if require_commit(value.get("contract_commit"), "blind.contract_commit") != capture[
        "contract_commit"
    ]:
        raise TrialError("blind packet contract commit mismatch")
    capture_sha = require_sha256(value.get("capture_sha256"), "blind.capture_sha256")
    if capture_sha != capture["capture_sha256"]:
        raise TrialError("blind packet capture hash mismatch")
    generation_sha = require_sha256(value.get("generation_sha256"), "blind.generation_sha256")
    if generation is not None and generation_sha != generation["generation_sha256"]:
        raise TrialError("blind packet generation hash mismatch")
    if require_object(value.get("review_scale"), "blind.review_scale") != contract["review"]:
        raise TrialError("blind packet review scale differs from the contract")
    boundary = require_object(value.get("boundary"), "blind.boundary")
    expected_boundary = {
        "condition_labels_present": False,
        "condition_mapping_present": False,
        "raw_context_present": False,
        "owner_review_required": True,
        **(
            {"required_reviewer_count": contract["review"]["required_reviewer_count"]}
            if contract["version"] == 1
            else {}
        ),
        "unblinding_allowed": False,
    }
    reject_unknown_fields(boundary, set(expected_boundary), "blind.boundary")
    if boundary != expected_boundary:
        raise TrialError("blind packet privacy boundary is incomplete")
    raw_cases = require_list(value.get("cases"), "blind.cases")
    if len(raw_cases) != len(capture["cases"]):
        raise TrialError("blind packet case count mismatch")
    cases: list[dict[str, Any]] = []
    for raw_case, capture_case in zip(raw_cases, capture["cases"], strict=True):
        case = require_object(raw_case, "blind case")
        reject_unknown_fields(
            case,
            {
                "case_id",
                "prompt_class",
                "question",
                "required_claims",
                "optional_claims",
                "forbidden_claim_ids",
                "answers",
                *(
                    {"prompt_variant", "requires_abstention"}
                    if contract["version"] == 1
                    else set()
                ),
            },
            "blind case",
        )
        case_id = require_label(case.get("case_id"), "blind case_id")
        if case_id != capture_case["case_id"]:
            raise TrialError("blind packet case id/order mismatch")
        if require_label(case.get("prompt_class"), "blind prompt_class") != capture_case[
            "prompt_class"
        ]:
            raise TrialError("blind packet prompt class mismatch")
        if contract["version"] == 1 and require_label(
            case.get("prompt_variant"), "blind prompt_variant"
        ) != capture_case["prompt_variant"]:
            raise TrialError("blind packet prompt variant mismatch")
        if require_string(case.get("question"), "blind question", max_chars=16_000) != capture_case[
            "prompt"
        ]:
            raise TrialError("blind packet question differs from capture")
        required_claims = validate_claims(
            case.get("required_claims"),
            "blind required_claims",
            allow_empty=capture_case["requires_abstention"],
        )
        optional_claims = validate_claims(
            case.get("optional_claims"), "blind optional_claims", allow_empty=True
        )
        forbidden_claims = [
            require_label(item, f"blind forbidden_claim_ids[{index}]")
            for index, item in enumerate(
                require_list(case.get("forbidden_claim_ids"), "blind forbidden_claim_ids")
            )
        ]
        if (
            required_claims != capture_case["required_claims"]
            or optional_claims != capture_case["optional_claims"]
            or forbidden_claims != capture_case["forbidden_claim_ids"]
        ):
            raise TrialError("blind packet claim rubric differs from the contract/capture")
        requires_abstention = capture_case["requires_abstention"]
        if contract["version"] == 1 and require_bool(
            case.get("requires_abstention"), "blind requires_abstention"
        ) != requires_abstention:
            raise TrialError("blind packet abstention flag differs from capture")
        answer_rows: list[dict[str, str]] = []
        answer_ids: set[str] = set()
        generation_hashes = (
            Counter(
                row["answer_sha256"]
                for row in generation["answers"][case_id].values()
            )
            if generation is not None
            else None
        )
        observed_hashes: Counter[str] = Counter()
        for raw_answer in require_list(case.get("answers"), "blind answers"):
            answer = require_object(raw_answer, "blind answer")
            reject_unknown_fields(answer, {"answer_id", "answer_markdown"}, "blind answer")
            opaque_id = require_string(answer.get("answer_id"), "blind answer_id", max_chars=32)
            if not re.fullmatch(r"ans_[0-9a-f]{24}", opaque_id) or opaque_id in answer_ids:
                raise TrialError("blind packet contains an invalid/duplicate answer id")
            answer_ids.add(opaque_id)
            answer_text = require_string(answer.get("answer_markdown"), "blind answer text", max_chars=12_000)
            answer_hash = sha256_text(answer_text)
            observed_hashes[answer_hash] += 1
            if (
                generation_hashes is not None
                and observed_hashes[answer_hash] > generation_hashes[answer_hash]
            ):
                raise TrialError("blind packet answer set differs from generation")
            answer_rows.append({"answer_id": opaque_id, "answer_markdown": answer_text})
        if len(answer_rows) != len(condition_ids):
            raise TrialError("blind packet answer count mismatch")
        if generation_hashes is not None and observed_hashes != generation_hashes:
            raise TrialError("blind packet does not contain every generated answer")
        cases.append(
            {
                "case_id": case_id,
                "prompt_class": capture_case["prompt_class"],
                "prompt_variant": capture_case["prompt_variant"],
                "required_claims": required_claims,
                "requires_abstention": requires_abstention,
                "answers": answer_rows,
            }
        )
    return {
        "trial_id": trial_id,
        "contract_sha256": contract_sha,
        "capture_sha256": capture_sha,
        "generation_sha256": generation_sha,
        "blind_packet_sha256": sha256_bytes(raw_bytes),
        "cases": cases,
    }


def validate_mapping(
    value: dict[str, Any],
    blind: dict[str, Any],
    contract: dict[str, Any],
    capture: dict[str, Any],
    generation: dict[str, Any],
) -> dict[str, dict[str, dict[str, str]]]:
    expected_schema = versioned_schema(contract, BLIND_MAP_SCHEMA, BLIND_MAP_SCHEMA_V1)
    if value.get("schema") != expected_schema:
        raise TrialError(f"blind map schema must be {expected_schema}")
    condition_ids = contract_conditions(contract)
    reject_unknown_fields(
        value,
        {
            "schema",
            "trial_id",
            "contract_sha256",
            "capture_sha256",
            "generation_sha256",
            "blind_packet_sha256",
            "blind_seed",
            "blind_seed_sha256",
            "cases",
            "boundary",
        },
        "blind map",
    )
    for field in {"trial_id", "contract_sha256", "capture_sha256", "generation_sha256"}:
        expected = blind[field]
        actual = value.get(field)
        if actual != expected:
            raise TrialError("blind map identity/hash mismatch")
    if require_sha256(
        value.get("blind_packet_sha256"), "map.blind_packet_sha256"
    ) != blind["blind_packet_sha256"]:
        raise TrialError("blind map packet hash mismatch")
    seed = require_string(value.get("blind_seed"), "map.blind_seed", max_chars=64)
    if not HEX64_RE.fullmatch(seed):
        raise TrialError("blind map seed is malformed")
    seed_sha = require_sha256(value.get("blind_seed_sha256"), "map.blind_seed_sha256")
    if sha256_text(seed) != seed_sha or seed_sha != contract["blinding"]["seed_sha256"]:
        raise TrialError("blind map seed commitment mismatch")
    boundary = require_object(value.get("boundary"), "map.boundary")
    expected_boundary = {
        "mapping_private": True,
        "reviewer_must_not_read_before_review": True,
    }
    reject_unknown_fields(boundary, set(expected_boundary), "map.boundary")
    if boundary != expected_boundary:
        raise TrialError("blind map privacy boundary is incomplete")
    raw_cases = require_list(value.get("cases"), "map.cases")
    if len(raw_cases) != len(blind["cases"]):
        raise TrialError("blind map case count mismatch")
    expected_generation_order = {
        identity: index
        for index, identity in enumerate(
            sorted(
                [
                    (case["case_id"], condition)
                    for case in capture["cases"]
                    for condition in condition_ids
                ],
                key=lambda item: generation_order(seed, item[0], item[1]),
            ),
            start=1,
        )
    }
    mapping: dict[str, dict[str, dict[str, str]]] = {}
    for raw_case, blind_case in zip(raw_cases, blind["cases"], strict=True):
        case = require_object(raw_case, "map case")
        reject_unknown_fields(case, {"case_id", "answers"}, "map case")
        case_id = require_label(case.get("case_id"), "map case_id")
        if case_id != blind_case["case_id"]:
            raise TrialError("blind map case id/order mismatch")
        expected_conditions = sorted(
            condition_ids,
            key=lambda condition: blind_order(seed, case_id, condition),
        )
        expected_answer_ids = [
            answer_id(seed, case_id, condition) for condition in expected_conditions
        ]
        observed_blind_ids = [row["answer_id"] for row in blind_case["answers"]]
        if observed_blind_ids != expected_answer_ids:
            raise TrialError(
                "blind packet answer order does not reproduce from the committed seed"
            )
        rows: dict[str, dict[str, str]] = {}
        seen_conditions: set[str] = set()
        blind_answers = {row["answer_id"]: row for row in blind_case["answers"]}
        raw_answers = require_list(case.get("answers"), "map answers")
        if [row.get("answer_id") for row in raw_answers if isinstance(row, dict)] != (
            expected_answer_ids
        ):
            raise TrialError(
                "blind map answer order does not reproduce from the committed seed"
            )
        for raw_answer in raw_answers:
            answer = require_object(raw_answer, "map answer")
            reject_unknown_fields(
                answer,
                {"answer_id", "condition", "answer_sha256", "context_sha256"},
                "map answer",
            )
            opaque_id = require_string(answer.get("answer_id"), "map answer_id", max_chars=32)
            condition = require_label(answer.get("condition"), "map condition")
            if opaque_id not in blind_answers or condition not in condition_ids:
                raise TrialError("blind map contains an unknown answer/condition")
            if opaque_id in rows or condition in seen_conditions:
                raise TrialError("blind map contains duplicate answer/condition")
            expected_index = len(rows)
            if condition != expected_conditions[expected_index]:
                raise TrialError(
                    "blind map condition order does not reproduce from the committed seed"
                )
            answer_sha = require_sha256(answer.get("answer_sha256"), "map answer_sha256")
            generated = generation["answers"][case_id][condition]
            if (
                answer_sha != sha256_text(blind_answers[opaque_id]["answer_markdown"])
                or answer_sha != generated["answer_sha256"]
            ):
                raise TrialError("blind map answer hash mismatch")
            context_sha = require_sha256(answer.get("context_sha256"), "map context_sha256")
            if (
                context_sha != generated["context_sha256"]
                or context_sha
                != next(
                    row for row in capture["cases"] if row["case_id"] == case_id
                )["conditions"][condition]["context_sha256"]
            ):
                raise TrialError("blind map context hash mismatch")
            if generated["invocation_index"] != expected_generation_order[(case_id, condition)]:
                raise TrialError("generation invocation order does not match the committed seed")
            expected_id = answer_id(seed, case_id, condition)
            if opaque_id != expected_id:
                raise TrialError("blind map answer id does not reproduce from the committed seed")
            rows[opaque_id] = {
                "condition": condition,
                "answer_sha256": answer_sha,
                "context_sha256": context_sha,
            }
            seen_conditions.add(condition)
        if set(seen_conditions) != set(condition_ids) or set(rows) != set(blind_answers):
            raise TrialError("blind map is incomplete")
        mapping[case_id] = rows
    return mapping


def validate_review(
    value: dict[str, Any], blind: dict[str, Any], contract: dict[str, Any]
) -> dict[str, Any]:
    expected_schema = versioned_schema(contract, REVIEW_SCHEMA, REVIEW_SCHEMA_V1)
    if value.get("schema") != expected_schema:
        raise TrialError(f"review schema must be {expected_schema}")
    reject_unknown_fields(
        value,
        {
            "schema",
            "trial_id",
            "blind_packet_sha256",
            "reviewer",
            "reviewed_at",
            "cases",
            *(
                {"independent_review", "condition_blinded"}
                if contract["version"] == 1
                else set()
            ),
        },
        "review",
    )
    if require_label(value.get("trial_id"), "review.trial_id") != blind["trial_id"]:
        raise TrialError("review trial id mismatch")
    if require_sha256(
        value.get("blind_packet_sha256"), "review.blind_packet_sha256"
    ) != blind["blind_packet_sha256"]:
        raise TrialError("review blind packet hash mismatch")
    reviewer = require_string(value.get("reviewer"), "review.reviewer", max_chars=128)
    reviewed_at = require_nonnegative_int(value.get("reviewed_at"), "review.reviewed_at")
    if reviewed_at <= 0:
        raise TrialError("review.reviewed_at must be populated")
    independent_review = False
    condition_blinded = False
    if contract["version"] == 1:
        independent_review = require_bool(
            value.get("independent_review"), "review.independent_review"
        )
        condition_blinded = require_bool(
            value.get("condition_blinded"), "review.condition_blinded"
        )
        if not independent_review or not condition_blinded:
            raise TrialError("v1 review independence/blinding attestations must be true")
    raw_cases = require_list(value.get("cases"), "review.cases")
    if len(raw_cases) != len(blind["cases"]):
        raise TrialError("review case count mismatch")
    cases: dict[str, Any] = {}
    for raw_case, blind_case in zip(raw_cases, blind["cases"], strict=True):
        case = require_object(raw_case, "review case")
        reject_unknown_fields(case, {"case_id", "answers", "preferred_answer_id"}, "review case")
        case_id = require_label(case.get("case_id"), "review case_id")
        if case_id != blind_case["case_id"]:
            raise TrialError("review case id/order mismatch")
        blind_answers = {row["answer_id"]: row for row in blind_case["answers"]}
        expected_claims = [row["claim_id"] for row in blind_case["required_claims"]]
        answer_reviews: dict[str, Any] = {}
        for raw_answer in require_list(case.get("answers"), "review answers"):
            answer = require_object(raw_answer, "review answer")
            reject_unknown_fields(
                answer,
                {
                    "answer_id",
                    "claim_scores",
                    "currentness",
                    "unsupported_assertion_count",
                    "usefulness",
                    "notes",
                    *(
                        {"abstention_pass"}
                        if contract["version"] == 1
                        and blind_case["requires_abstention"]
                        else set()
                    ),
                },
                "review answer",
            )
            opaque_id = require_string(answer.get("answer_id"), "review answer_id", max_chars=32)
            if opaque_id not in blind_answers or opaque_id in answer_reviews:
                raise TrialError("review contains an unknown/duplicate answer id")
            score_rows = require_list(answer.get("claim_scores"), "review claim_scores")
            if len(score_rows) != len(expected_claims):
                raise TrialError("review claim score count mismatch")
            scores: dict[str, int] = {}
            for raw_score, expected_claim in zip(score_rows, expected_claims, strict=True):
                score_row = require_object(raw_score, "review claim score")
                reject_unknown_fields(score_row, {"claim_id", "score"}, "review claim score")
                claim_id = require_label(score_row.get("claim_id"), "review claim_id")
                if claim_id != expected_claim or claim_id in scores:
                    raise TrialError("review claim id/order mismatch")
                score = score_row.get("score")
                if not isinstance(score, int) or isinstance(score, bool):
                    raise TrialError("review claim score must be populated")
                if score not in contract["review"]["claim_score_values"]:
                    raise TrialError("review claim score is outside the fixed scale")
                scores[claim_id] = score
            currentness = require_label(answer.get("currentness"), "review currentness")
            if currentness not in contract["review"]["currentness_values"]:
                raise TrialError("review currentness is outside the fixed scale")
            unsupported = answer.get("unsupported_assertion_count")
            if not isinstance(unsupported, int) or isinstance(unsupported, bool) or unsupported < 0:
                raise TrialError("review unsupported assertion count must be populated")
            usefulness = answer.get("usefulness")
            if (
                not isinstance(usefulness, int)
                or isinstance(usefulness, bool)
                or not contract["review"]["usefulness_min"]
                <= usefulness
                <= contract["review"]["usefulness_max"]
            ):
                raise TrialError("review usefulness must be populated on the fixed scale")
            notes = answer.get("notes", "")
            if not isinstance(notes, str) or len(notes) > 2_000:
                raise TrialError("review notes must be a bounded string")
            abstention_pass: bool | None = None
            if contract["version"] == 1 and blind_case["requires_abstention"]:
                abstention_pass = require_bool(
                    answer.get("abstention_pass"), "review abstention_pass"
                )
            answer_reviews[opaque_id] = {
                "claim_scores": scores,
                "currentness": currentness,
                "unsupported_assertion_count": unsupported,
                "usefulness": usefulness,
                "abstention_pass": abstention_pass,
            }
        if set(answer_reviews) != set(blind_answers):
            raise TrialError("review does not cover every blinded answer exactly once")
        preference = require_string(
            case.get("preferred_answer_id"), "review preferred_answer_id", max_chars=32
        )
        if preference != contract["review"]["preference_tie_label"] and preference not in blind_answers:
            raise TrialError("review preference must name a blinded answer or tie")
        cases[case_id] = {
            "prompt_class": blind_case["prompt_class"],
            "requires_abstention": blind_case["requires_abstention"],
            "answers": answer_reviews,
            "preference": preference,
        }
    return {
        "reviewer": reviewer,
        "reviewed_at": reviewed_at,
        "independent_review": independent_review,
        "condition_blinded": condition_blinded,
        "cases": cases,
    }


def score_v1_slice(
    contract: dict[str, Any],
    capture: dict[str, Any],
    mapping: dict[str, dict[str, dict[str, str]]],
    review: dict[str, Any],
    case_ids: set[str],
) -> dict[str, Any]:
    condition_ids = contract_conditions(contract)
    aggregates: dict[str, dict[str, Any]] = {
        condition: {
            "weighted_score": 0.0,
            "weighted_max": 0.0,
            "currentness_failures": 0,
            "currentness_uncertain": 0,
            "unsupported_assertions": 0,
            "usefulness": [],
            "preference_wins": 0,
            "preference_ties": 0,
            "context_tokens": 0,
            "abstention_required": 0,
            "abstention_passed": 0,
        }
        for condition in condition_ids
    }
    capture_cases = {case["case_id"]: case for case in capture["cases"]}
    for case_id in sorted(case_ids):
        case_review = review["cases"][case_id]
        capture_case = capture_cases[case_id]
        weights = {
            row["claim_id"]: row["weight"] for row in capture_case["required_claims"]
        }
        for opaque_id, answer_review in case_review["answers"].items():
            condition = mapping[case_id][opaque_id]["condition"]
            aggregate = aggregates[condition]
            for claim_id, claim_score in answer_review["claim_scores"].items():
                weight = weights[claim_id]
                aggregate["weighted_score"] += (claim_score / 2.0) * weight
                aggregate["weighted_max"] += weight
            aggregate["currentness_failures"] += answer_review["currentness"] == "fail"
            aggregate["currentness_uncertain"] += (
                answer_review["currentness"] == "uncertain"
            )
            aggregate["unsupported_assertions"] += answer_review[
                "unsupported_assertion_count"
            ]
            aggregate["usefulness"].append(answer_review["usefulness"])
            aggregate["context_tokens"] += capture_case["conditions"][condition][
                "context_tokens_estimate"
            ]
            if case_review["requires_abstention"]:
                aggregate["abstention_required"] += 1
                aggregate["abstention_passed"] += answer_review["abstention_pass"] is True
        preference = case_review["preference"]
        if preference == contract["review"]["preference_tie_label"]:
            for condition in condition_ids:
                aggregates[condition]["preference_ties"] += 1
        else:
            preferred_condition = mapping[case_id][preference]["condition"]
            aggregates[preferred_condition]["preference_wins"] += 1

    thresholds = contract["thresholds"]
    metrics: dict[str, dict[str, Any]] = {}
    for condition, raw in aggregates.items():
        completeness = (
            raw["weighted_score"] / raw["weighted_max"]
            if raw["weighted_max"]
            else 1.0
        )
        mean_usefulness = sum(raw["usefulness"]) / len(raw["usefulness"])
        min_usefulness = min(raw["usefulness"])
        absolute_pass = (
            completeness >= thresholds["min_weighted_claim_completeness"]
            and raw["currentness_failures"] <= thresholds["max_currentness_failures"]
            and raw["currentness_uncertain"] <= thresholds["max_currentness_uncertain"]
            and raw["unsupported_assertions"] <= thresholds["max_unsupported_assertions"]
            and raw["abstention_required"] - raw["abstention_passed"]
            <= thresholds["max_abstention_failures"]
            and mean_usefulness >= thresholds["min_mean_usefulness"]
            and min_usefulness >= thresholds["min_case_usefulness"]
        )
        metrics[condition] = {
            "weighted_claim_completeness": round(completeness, 6),
            "currentness_failures": raw["currentness_failures"],
            "currentness_uncertain": raw["currentness_uncertain"],
            "unsupported_assertions": raw["unsupported_assertions"],
            "mean_usefulness": round(mean_usefulness, 6),
            "min_case_usefulness": min_usefulness,
            "preference_wins": raw["preference_wins"],
            "preference_ties": raw["preference_ties"],
            "context_tokens_total": raw["context_tokens"],
            "abstention_required": raw["abstention_required"],
            "abstention_passed": raw["abstention_passed"],
            "abstention_failures": raw["abstention_required"]
            - raw["abstention_passed"],
            "absolute_gate_pass": absolute_pass,
        }

    reference = metrics[REFERENCE_CONDITION]
    candidate = metrics["portfolio_digest"]
    completeness_drop = reference["weighted_claim_completeness"] - candidate[
        "weighted_claim_completeness"
    ]
    usefulness_drop = reference["mean_usefulness"] - candidate["mean_usefulness"]
    token_reduction = (
        reference["context_tokens_total"] - candidate["context_tokens_total"]
    ) / reference["context_tokens_total"]
    absolute_pass = reference["absolute_gate_pass"] and candidate["absolute_gate_pass"]
    noninferiority_pass = (
        completeness_drop <= thresholds["max_completeness_drop_vs_reference"]
        and usefulness_drop <= thresholds["max_usefulness_drop_vs_reference"]
        and candidate["currentness_failures"] <= reference["currentness_failures"]
        and candidate["currentness_uncertain"] <= reference["currentness_uncertain"]
        and candidate["unsupported_assertions"] <= reference["unsupported_assertions"]
        and candidate["abstention_failures"] <= reference["abstention_failures"]
    )
    efficiency_pass = token_reduction >= thresholds[
        "min_context_token_reduction_vs_reference"
    ]
    abstention_required = sum(row["abstention_required"] for row in metrics.values())
    abstention_passed = sum(row["abstention_passed"] for row in metrics.values())
    abstention_failures = abstention_required - abstention_passed
    abstention_pass = abstention_failures <= thresholds["max_abstention_failures"]
    return {
        "case_count": len(case_ids),
        "conditions": metrics,
        "candidate": {
            "completeness_drop_vs_reference": round(completeness_drop, 6),
            "usefulness_drop_vs_reference": round(usefulness_drop, 6),
            "context_token_reduction_vs_reference": round(token_reduction, 6),
            "absolute_gate_pass": absolute_pass,
            "noninferiority_pass": noninferiority_pass,
            "efficiency_pass": efficiency_pass,
        },
        "abstention_required": abstention_required,
        "abstention_passed": abstention_passed,
        "abstention_failures": abstention_failures,
        "all_abstention_pass": abstention_pass,
        "gate_pass": (
            absolute_pass and noninferiority_pass and efficiency_pass and abstention_pass
        ),
    }


def score_trial_v1(
    contract: dict[str, Any],
    contract_sha: str,
    capture: dict[str, Any],
    generation: dict[str, Any],
    blind: dict[str, Any],
    map_path: Path,
    mapping: dict[str, dict[str, dict[str, str]]],
    review_records: list[dict[str, Any]],
    output_path: Path,
    protected_inputs: tuple[Path, ...],
) -> dict[str, Any]:
    strata_cases = {
        stratum: {
            case["case_id"]
            for case in capture["cases"]
            if case["prompt_class"] == stratum
        }
        for stratum in sorted(EXPANDED_STRATA)
    }
    all_case_ids = {case["case_id"] for case in capture["cases"]}
    per_reviewer: dict[str, Any] = {}
    for index, review_record in enumerate(review_records, start=1):
        review = review_record["review"]
        reviewer_key = f"reviewer_{index}"
        stratum_rows = {
            stratum: score_v1_slice(contract, capture, mapping, review, case_ids)
            for stratum, case_ids in strata_cases.items()
        }
        global_row = score_v1_slice(
            contract, capture, mapping, review, all_case_ids
        )
        per_reviewer[reviewer_key] = {
            "review_sha256": review_record["review_sha256"],
            "per_stratum": stratum_rows,
            "global": global_row,
            "all_strata_gate_pass": all(
                row["gate_pass"] for row in stratum_rows.values()
            ),
        }

    per_stratum = {
        stratum: {
            "case_count": len(strata_cases[stratum]),
            "reviewer_gates": {
                reviewer_key: row["per_stratum"][stratum]["gate_pass"]
                for reviewer_key, row in per_reviewer.items()
            },
            "all_reviewers_gate_pass": all(
                row["per_stratum"][stratum]["gate_pass"]
                for row in per_reviewer.values()
            ),
        }
        for stratum in sorted(EXPANDED_STRATA)
    }
    all_reviewer_global_gates = all(
        row["global"]["gate_pass"] for row in per_reviewer.values()
    )
    all_reviewer_stratum_gates = all(
        row["all_strata_gate_pass"] for row in per_reviewer.values()
    )
    all_abstention_pass = all(
        row["global"]["all_abstention_pass"] for row in per_reviewer.values()
    )
    advance = (
        all_reviewer_global_gates
        and all_reviewer_stratum_gates
        and all_abstention_pass
    )
    output = {
        "schema": SCORE_SCHEMA_V1,
        "trial_id": capture["trial_id"],
        "contract_sha256": contract_sha,
        "contract_commit": capture["contract_commit"],
        "capture_sha256": capture["capture_sha256"],
        "generation_sha256": generation["generation_sha256"],
        "blind_packet_sha256": blind["blind_packet_sha256"],
        "blind_map_sha256": surface.sha256_file(map_path),
        "harness_source_sha256": contract["harness_source_sha256"],
        "per_reviewer": per_reviewer,
        "per_stratum": per_stratum,
        "global": {
            "reviewer_count": len(review_records),
            "stratum_count": len(per_stratum),
            "all_reviewer_global_gates_pass": all_reviewer_global_gates,
            "all_reviewer_stratum_gates_pass": all_reviewer_stratum_gates,
            "all_abstention_pass": all_abstention_pass,
            "advance": advance,
            "recommend_write_side_preregistration": advance,
        },
        "status": (
            "READY_TO_PREREGISTER_WRITE_SIDE_TRIAL" if advance else "NO_ADVANCE"
        ),
        "recommendation_scope": contract["thresholds"]["recommendation_scope"],
        "boundary": {
            "raw_prompt_in_output": False,
            "raw_context_in_output": False,
            "raw_answer_in_output": False,
            "answer_id_in_output": False,
            "reviewer_identity_in_output": False,
            "review_notes_in_output": False,
            "pooled_reviewer_mean_used_for_gate": False,
            "llm_judge": False,
            "reviews_complete": True,
            "runtime_promotion_allowed": False,
            "automatic_digest_regeneration_allowed": False,
            "compact_default_change_allowed": False,
            "version_or_tag_change_allowed": False,
            "release_action_allowed": False,
            "ci_action_allowed": False,
            "write_side_trial_requires_separate_preregistration": True,
        },
    }
    write_json(output_path, output, protected_paths=protected_inputs)
    return output


def _score_trial_core(
    contract_path: Path,
    capture_path: Path,
    generation_path: Path,
    blind_path: Path,
    map_path: Path,
    review_paths: list[Path],
    output_path: Path,
) -> dict[str, Any]:
    protected_inputs = (
        contract_path,
        capture_path,
        generation_path,
        blind_path,
        map_path,
        *review_paths,
        Path(__file__),
        Path(surface.__file__),
    )
    require_distinct_paths(
        {
            "contract": contract_path,
            "capture": capture_path,
            "generation": generation_path,
            "blind": blind_path,
            "map": map_path,
            **{
                f"review_{index}": path
                for index, path in enumerate(review_paths, start=1)
            },
            "harness_source": Path(__file__),
            "surface_source": Path(surface.__file__),
            "output": output_path,
        }
    )
    contract, contract_sha = load_contract(contract_path)
    capture_raw, capture_bytes = read_json(capture_path)
    capture = validate_capture(capture_raw, capture_bytes, contract, contract_sha)
    blind_raw, blind_bytes = read_json(blind_path)
    blind = validate_blind_packet(
        blind_raw,
        blind_bytes,
        contract,
        contract_sha,
        capture,
        None,
    )
    expected_review_count = 2 if contract["version"] == 1 else 1
    if len(review_paths) != expected_review_count:
        raise TrialError(
            f"score requires exactly {expected_review_count} --review argument(s)"
        )
    reviews: list[dict[str, Any]] = []
    review_packets: list[bytes] = []
    for review_path in review_paths:
        review_raw, review_bytes = read_json(review_path)
        reviews.append(validate_review(review_raw, blind, contract))
        review_packets.append(review_bytes)
    if len({review["reviewer"] for review in reviews}) != len(reviews):
        raise TrialError("score reviews must have distinct reviewer identities")
    review_records = sorted(
        [
            {
                "review": review,
                "review_sha256": sha256_bytes(review_bytes),
                "reviewer_sha256": sha256_text(review["reviewer"]),
            }
            for review, review_bytes in zip(reviews, review_packets, strict=True)
        ],
        key=lambda row: row["reviewer_sha256"],
    )

    # The generation packet and blind map both reveal condition-to-answer
    # identity. Do not open either until the owner review is complete.
    generation_raw, generation_bytes = read_json(generation_path)
    generation = validate_generation(
        generation_raw,
        generation_bytes,
        contract,
        contract_sha,
        capture,
    )
    blind = validate_blind_packet(
        blind_raw,
        blind_bytes,
        contract,
        contract_sha,
        capture,
        generation,
    )
    map_raw, _ = read_json(map_path)
    mapping = validate_mapping(map_raw, blind, contract, capture, generation)
    if contract["version"] == 1:
        return score_trial_v1(
            contract,
            contract_sha,
            capture,
            generation,
            blind,
            map_path,
            mapping,
            review_records,
            output_path,
            protected_inputs,
        )

    review = reviews[0]
    review_bytes = review_packets[0]

    aggregates: dict[str, dict[str, Any]] = {
        condition: {
            "weighted_score": 0.0,
            "weighted_max": 0.0,
            "currentness_failures": 0,
            "currentness_uncertain": 0,
            "unsupported_assertions": 0,
            "usefulness": [],
            "preference_wins": 0,
            "preference_ties": 0,
            "context_tokens": 0,
        }
        for condition in CONDITIONS
    }
    capture_cases = {case["case_id"]: case for case in capture["cases"]}
    for case_id, case_review in review["cases"].items():
        weights = {
            row["claim_id"]: row["weight"]
            for row in capture_cases[case_id]["required_claims"]
        }
        for opaque_id, answer_review in case_review["answers"].items():
            condition = mapping[case_id][opaque_id]["condition"]
            aggregate = aggregates[condition]
            for claim_id, score in answer_review["claim_scores"].items():
                weight = weights[claim_id]
                aggregate["weighted_score"] += (score / 2.0) * weight
                aggregate["weighted_max"] += weight
            aggregate["currentness_failures"] += answer_review["currentness"] == "fail"
            aggregate["currentness_uncertain"] += answer_review["currentness"] == "uncertain"
            aggregate["unsupported_assertions"] += answer_review[
                "unsupported_assertion_count"
            ]
            aggregate["usefulness"].append(answer_review["usefulness"])
            aggregate["context_tokens"] += capture_cases[case_id]["conditions"][condition][
                "context_tokens_estimate"
            ]
        preference = case_review["preference"]
        if preference == contract["review"]["preference_tie_label"]:
            for condition in CONDITIONS:
                aggregates[condition]["preference_ties"] += 1
        else:
            preference_condition = mapping[case_id][preference]["condition"]
            aggregates[preference_condition]["preference_wins"] += 1

    metrics: dict[str, dict[str, Any]] = {}
    thresholds = contract["thresholds"]
    for condition, raw in aggregates.items():
        completeness = raw["weighted_score"] / raw["weighted_max"]
        mean_usefulness = sum(raw["usefulness"]) / len(raw["usefulness"])
        min_usefulness = min(raw["usefulness"])
        absolute_pass = (
            completeness >= thresholds["min_weighted_claim_completeness"]
            and raw["currentness_failures"] <= thresholds["max_currentness_failures"]
            and raw["currentness_uncertain"] <= thresholds["max_currentness_uncertain"]
            and raw["unsupported_assertions"] <= thresholds["max_unsupported_assertions"]
            and mean_usefulness >= thresholds["min_mean_usefulness"]
            and min_usefulness >= thresholds["min_case_usefulness"]
        )
        metrics[condition] = {
            "weighted_claim_completeness": round(completeness, 6),
            "currentness_failures": raw["currentness_failures"],
            "currentness_uncertain": raw["currentness_uncertain"],
            "unsupported_assertions": raw["unsupported_assertions"],
            "mean_usefulness": round(mean_usefulness, 6),
            "min_case_usefulness": min_usefulness,
            "preference_wins": raw["preference_wins"],
            "preference_ties": raw["preference_ties"],
            "context_tokens_total": raw["context_tokens"],
            "absolute_gate_pass": absolute_pass,
        }
    reference = metrics[REFERENCE_CONDITION]
    recommendations: dict[str, dict[str, Any]] = {}
    for condition in thresholds["candidate_conditions"]:
        row = metrics[condition]
        completeness_drop = reference["weighted_claim_completeness"] - row[
            "weighted_claim_completeness"
        ]
        usefulness_drop = reference["mean_usefulness"] - row["mean_usefulness"]
        token_reduction = (
            reference["context_tokens_total"] - row["context_tokens_total"]
        ) / reference["context_tokens_total"]
        noninferiority_pass = (
            completeness_drop <= thresholds["max_completeness_drop_vs_reference"]
            and usefulness_drop <= thresholds["max_usefulness_drop_vs_reference"]
            and row["currentness_failures"] <= reference["currentness_failures"]
            and row["currentness_uncertain"] <= reference["currentness_uncertain"]
            and row["unsupported_assertions"] <= reference["unsupported_assertions"]
        )
        efficiency_pass = token_reduction >= thresholds[
            "min_context_token_reduction_vs_reference"
        ]
        advance = (
            reference["absolute_gate_pass"]
            and row["absolute_gate_pass"]
            and noninferiority_pass
            and efficiency_pass
        )
        recommendations[condition] = {
            "completeness_drop_vs_reference": round(completeness_drop, 6),
            "usefulness_drop_vs_reference": round(usefulness_drop, 6),
            "context_token_reduction_vs_reference": round(token_reduction, 6),
            "noninferiority_pass": noninferiority_pass,
            "efficiency_pass": efficiency_pass,
            "advance_to_expanded_trial": advance,
        }
    status = (
        "READY_FOR_EXPANDED_TRIAL"
        if any(row["advance_to_expanded_trial"] for row in recommendations.values())
        else "NO_ADVANCE"
    )
    output = {
        "schema": SCORE_SCHEMA,
        "trial_id": capture["trial_id"],
        "contract_sha256": contract_sha,
        "contract_commit": capture["contract_commit"],
        "capture_sha256": capture["capture_sha256"],
        "generation_sha256": generation["generation_sha256"],
        "blind_packet_sha256": blind["blind_packet_sha256"],
        "blind_map_sha256": surface.sha256_file(map_path),
        "review_sha256": sha256_bytes(review_bytes),
        "reviewer_sha256": sha256_text(review["reviewer"]),
        "reviewed_at": review["reviewed_at"],
        "conditions": metrics,
        "candidate_recommendations": recommendations,
        "status": status,
        "recommendation_scope": thresholds["recommendation_scope"],
        "boundary": {
            "raw_prompt_in_output": False,
            "raw_context_in_output": False,
            "raw_answer_in_output": False,
            "answer_id_in_output": False,
            "review_notes_in_output": False,
            "llm_judge": False,
            "owner_review_complete": True,
            "runtime_promotion_allowed": False,
            "automatic_digest_regeneration_allowed": False,
            "compact_default_change_allowed": False,
        },
    }
    write_json(output_path, output, protected_paths=protected_inputs)
    return output


def score_trial(
    contract_path: Path,
    capture_path: Path,
    generation_path: Path,
    blind_path: Path,
    map_path: Path,
    review_paths: list[Path],
    output_path: Path,
) -> dict[str, Any]:
    return _score_trial_core(
        contract_path,
        capture_path,
        generation_path,
        blind_path,
        map_path,
        review_paths,
        output_path,
    )


def validate_contract_command(contract_path: Path) -> dict[str, Any]:
    contract, contract_sha = load_contract(contract_path)
    return {
        "schema": contract["schema"],
        "contract_id": contract["contract_id"],
        "contract_sha256": contract_sha,
        "condition_count": len(contract["conditions"]),
        "case_count": len(contract["cases"]),
        "runtime_source_commit": contract["runtime_source_commit"],
        "model": contract["generation"]["model"],
        "status": "VALID",
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate = subparsers.add_parser("validate-contract")
    validate.add_argument("--contract", required=True)

    capture = subparsers.add_parser("capture")
    capture.add_argument("--contract", required=True)
    capture.add_argument("--spec", required=True)
    capture.add_argument("--source-db", required=True)
    capture.add_argument("--agent-bridge-bin", required=True)
    capture.add_argument("--raw-output", required=True)
    capture.add_argument("--redacted-output", required=True)
    capture.add_argument("--timeout-secs", type=float, default=120.0)

    generate = subparsers.add_parser("generate")
    generate.add_argument("--contract", required=True)
    generate.add_argument("--spec", required=True)
    generate.add_argument("--capture", required=True)
    generate.add_argument("--codex-bin", required=True)
    generate.add_argument("--generation-output", required=True)
    generate.add_argument("--blind-output", required=True)
    generate.add_argument("--map-output", required=True)
    generate.add_argument("--review-template-output", required=True)
    generate.add_argument("--redacted-output", required=True)
    generate.add_argument("--timeout-secs", type=float, default=600.0)

    score = subparsers.add_parser("score")
    score.add_argument("--contract", required=True)
    score.add_argument("--capture", required=True)
    score.add_argument("--generation", required=True)
    score.add_argument("--blind-packet", required=True)
    score.add_argument("--blind-map", required=True)
    score.add_argument("--review", required=True, action="append")
    score.add_argument("--output", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "validate-contract":
            packet = validate_contract_command(Path(args.contract))
        elif args.command == "capture":
            if not math.isfinite(args.timeout_secs) or args.timeout_secs <= 0:
                raise TrialError("--timeout-secs must be positive and finite")
            packet = capture_trial(
                Path(args.contract),
                Path(args.spec),
                Path(args.source_db),
                Path(args.agent_bridge_bin),
                Path(args.raw_output),
                Path(args.redacted_output),
                args.timeout_secs,
            )
        elif args.command == "generate":
            if not math.isfinite(args.timeout_secs) or args.timeout_secs <= 0:
                raise TrialError("--timeout-secs must be positive and finite")
            packet = generate_trial(
                Path(args.contract),
                Path(args.spec),
                Path(args.capture),
                Path(args.codex_bin),
                Path(args.generation_output),
                Path(args.blind_output),
                Path(args.map_output),
                Path(args.review_template_output),
                Path(args.redacted_output),
                args.timeout_secs,
            )
        else:
            packet = score_trial(
                Path(args.contract),
                Path(args.capture),
                Path(args.generation),
                Path(args.blind_packet),
                Path(args.blind_map),
                [Path(path) for path in args.review],
                Path(args.output),
            )
    except TrialError as exc:
        print(f"ERROR: {exc}", file=os.sys.stderr)
        return 2
    except (KeyError, TypeError, IndexError, OSError, sqlite3.Error):
        print("ERROR: malformed answer trial packet", file=os.sys.stderr)
        return 2
    print(json.dumps(packet, ensure_ascii=False, sort_keys=True, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
