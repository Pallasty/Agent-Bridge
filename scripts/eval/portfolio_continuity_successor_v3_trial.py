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
CONTRACT_SCHEMA_V2 = "agent_bridge.portfolio_continuity_answer_contract.v2"
CONTRACT_SCHEMA_V3 = "agent_bridge.portfolio_continuity_answer_contract.v3"
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
FAILURE_RECEIPT_SCHEMA_V2 = (
    "agent_bridge.portfolio_continuity_answer_generation_failure.v2"
)
REVIEW_RECEIPT_SCHEMA_V3 = (
    "agent_bridge.portfolio_continuity_answer_review_receipt.v3"
)
SCORE_CLAIM_SCHEMA_V3 = "agent_bridge.portfolio_continuity_answer_score_claim.v3"

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
SUCCESSOR_IDENTIFIER_ALIASES = {
    "compact_then_get_top2": "rank-only compact top-2 retrieval",
    "hybrid_retrieval": "full hybrid retrieval",
    "portfolio_digest": "direct portfolio digest",
    "portfolio_state_digest": "portfolio digest record",
    "session_bootstrap": "session bootstrap",
}
SUCCESSOR_DROPPED_RECORD_FIELDS = ["key"]
RETRYABLE_PRE_MODEL_ERROR_CODES = {
    "codex_identity_unavailable",
    "codex_spawn_failed",
    "generation_workspace_failed",
}
V3_REVIEW_ROSTER = (
    {
        "reviewer_slot": "reviewer_anthropic_opus",
        "provider": "anthropic",
        "model": "claude-opus-4-8",
        "reasoning_effort": "cli_default",
        "cli": "claude",
        "cli_version": "2.1.207 (Claude Code)",
        "command_profile": "claude_print_json_v1",
        "provider_overlap_with_generator": False,
        "model_overlap_with_generator": False,
    },
    {
        "reviewer_slot": "reviewer_openai_sol",
        "provider": "openai",
        "model": "gpt-5.6-sol",
        "reasoning_effort": "max",
        "cli": "codex",
        "cli_version": "codex-cli 0.144.1",
        "command_profile": "codex_exec_json_v1",
        "provider_overlap_with_generator": True,
        "model_overlap_with_generator": False,
    },
)
V3_CONFLICTS_OF_INTEREST = {
    "scheduler_authored_some_evaluated_material": True,
    "scheduler_discretion_after_freeze": False,
    "cross_reviewer_provider_independence": True,
    "generator_provider_overlap_slots": ["reviewer_openai_sol"],
    "pooled_reviewer_mean_allowed": False,
}
EMPTY_WORKSPACE_SHA256 = hashlib.sha256(b"").hexdigest()

TrialError = surface.TrialError


class GenerationFailure(TrialError):
    def __init__(
        self,
        error_code: str,
        phase: str,
        message: str,
        *,
        model_started: bool,
        answer_sha256: str | None = None,
        matched_marker_sha256: str | None = None,
    ) -> None:
        super().__init__(message)
        self.error_code = error_code
        self.phase = phase
        self.model_started = model_started
        self.answer_sha256 = answer_sha256
        self.matched_marker_sha256 = matched_marker_sha256


def contract_conditions(contract: dict[str, Any]) -> tuple[str, ...]:
    return tuple(row["condition_id"] for row in contract["conditions"])


def is_expanded(contract: dict[str, Any]) -> bool:
    return contract["version"] >= 1


def is_successor(contract: dict[str, Any]) -> bool:
    return contract["version"] >= 2


def has_review_provenance(contract: dict[str, Any]) -> bool:
    return contract["version"] >= 3


def versioned_schema(contract: dict[str, Any], v0: str, v1: str) -> str:
    if contract["version"] == 0:
        return v0
    if contract["version"] == 1:
        return v1
    if not v1.endswith(".v1"):
        raise TrialError("versioned schema derivation requires a v1 schema")
    return v1[:-1] + str(contract["version"])


def successor_schema(contract: dict[str, Any], v2: str) -> str:
    if not is_successor(contract) or not v2.endswith(".v2"):
        raise TrialError("successor schema derivation requires a successor contract")
    return v2[:-1] + str(contract["version"])


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


def render_json_value(value: Any) -> str:
    try:
        return (
            json.dumps(
                value,
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
                allow_nan=False,
            )
            + "\n"
        )
    except (TypeError, ValueError) as exc:
        raise TrialError("failed to render projected evidence") from exc


def project_successor_strings(value: Any, aliases: dict[str, str]) -> Any:
    if isinstance(value, str):
        projected = value
        for source in sorted(aliases, key=len, reverse=True):
            projected = projected.replace(source, aliases[source])
        return projected
    if isinstance(value, list):
        return [project_successor_strings(item, aliases) for item in value]
    if isinstance(value, dict):
        return {
            key: project_successor_strings(child, aliases)
            for key, child in value.items()
        }
    return value


def project_successor_record(
    record: dict[str, Any], projection: dict[str, Any]
) -> dict[str, Any]:
    dropped = set(projection["drop_record_fields"])
    aliases = projection["identifier_aliases"]
    return {
        key: project_successor_strings(value, aliases)
        for key, value in record.items()
        if key not in dropped
    }


def project_successor_context(
    condition: str, raw_result: Any, projection: dict[str, Any]
) -> str:
    if condition == REFERENCE_CONDITION:
        hits = require_list(raw_result, "successor hybrid raw_result")
        projected_hits: list[dict[str, Any]] = []
        for index, raw_hit in enumerate(hits):
            hit = require_object(raw_hit, f"successor hybrid hit {index}")
            reject_unknown_fields(
                hit, {"rank", "record", "score"}, f"successor hybrid hit {index}"
            )
            rank = require_nonnegative_int(
                hit.get("rank"), f"successor hybrid hit {index}.rank"
            )
            if rank != index + 1:
                raise TrialError("successor hybrid ranking is not contiguous")
            score = hit.get("score")
            if score is not None:
                score = surface.require_finite_number(
                    score, f"successor hybrid hit {index}.score"
                )
            projected_hits.append(
                {
                    "record": project_successor_record(
                        require_object(
                            hit.get("record"), f"successor hybrid hit {index}.record"
                        ),
                        projection,
                    ),
                    "score": score,
                }
            )
        projected: Any = projected_hits
    elif condition == "portfolio_digest":
        projected = project_successor_record(
            require_object(raw_result, "successor digest raw_result"), projection
        )
    else:
        raise TrialError("successor context projection received an unsupported condition")
    context = render_json_value(projected)
    if any(source in context for source in projection["identifier_aliases"]):
        raise TrialError("successor context projection retained an internal identifier")
    return context


def evaluate_successor_coverage(
    cases: list[dict[str, Any]], coverage_contract: dict[str, Any]
) -> dict[str, Any]:
    failed_case_ids: list[str] = []
    rows: list[dict[str, Any]] = []
    for case in cases:
        raw_hits = require_list(
            case["conditions"][REFERENCE_CONDITION]["raw_result"],
            "successor reference raw_result",
        )
        keys: list[str] = []
        for hit in raw_hits:
            normalized_hit = require_object(hit, "successor reference hit")
            record = require_object(
                normalized_hit.get("record"), "successor reference record"
            )
            keys.append(
                require_string(
                    record.get("key"), "successor reference key", max_chars=256
                )
            )
        if len(keys) != len(set(keys)):
            raise TrialError("successor reference coverage contains duplicate keys")
        minimum = (
            coverage_contract["min_reference_hits_abstention"]
            if case["requires_abstention"]
            else coverage_contract["min_reference_hits_non_abstention"]
        )
        passed = len(keys) >= minimum
        if not passed:
            failed_case_ids.append(case["case_id"])
        rows.append(
            {
                "case_id": case["case_id"],
                "requires_abstention": case["requires_abstention"],
                "reference_hit_count": len(keys),
                "minimum_reference_hits": minimum,
                "pass": passed,
            }
        )
    return {
        "status": "VALID" if not failed_case_ids else "INVALID_REFERENCE_COVERAGE",
        "failed_case_ids": failed_case_ids,
        "failed_case_count": len(failed_case_ids),
        "cases": rows,
    }


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


def validate_v3_review_execution(value: Any) -> dict[str, Any]:
    execution = require_object(value, "contract.review_execution")
    reject_unknown_fields(
        execution,
        {
            "required_receipt_count",
            "custodian_generated_receipts",
            "receipt_required_before_unblinding",
            "request_hash_required",
            "raw_response_hash_required",
            "review_retry_limit",
            "automatic_retry",
            "request_format",
            "review_instruction",
            "context_policy",
            "reviewers",
        },
        "contract.review_execution",
    )
    fixed_flags = {
        "required_receipt_count": 2,
        "custodian_generated_receipts": True,
        "receipt_required_before_unblinding": True,
        "request_hash_required": True,
        "raw_response_hash_required": True,
        "review_retry_limit": 0,
        "automatic_retry": False,
    }
    normalized: dict[str, Any] = {}
    for key, expected in fixed_flags.items():
        if isinstance(expected, bool):
            actual = require_bool(execution.get(key), f"contract.review_execution.{key}")
        else:
            actual = require_nonnegative_int(
                execution.get(key), f"contract.review_execution.{key}"
            )
        if actual != expected:
            raise TrialError(f"contract.review_execution.{key} is not fixed")
        normalized[key] = actual
    request_format = require_label(
        execution.get("request_format"), "contract.review_execution.request_format"
    )
    if request_format != "instruction_then_blind_packet_v1":
        raise TrialError("v3 review request format is not fixed")
    review_instruction = require_string(
        execution.get("review_instruction"),
        "contract.review_execution.review_instruction",
        max_chars=8_000,
    )
    context_policy = require_object(
        execution.get("context_policy"), "contract.review_execution.context_policy"
    )
    expected_context_policy = {
        "empty_workspace": True,
        "blind_packet_only": True,
        "project_context_allowed": False,
        "mcp_allowed": False,
        "tools_allowed": False,
    }
    reject_unknown_fields(
        context_policy,
        set(expected_context_policy),
        "contract.review_execution.context_policy",
    )
    if context_policy != expected_context_policy:
        raise TrialError("v3 review context policy is not fixed")
    raw_reviewers = require_list(
        execution.get("reviewers"), "contract.review_execution.reviewers"
    )
    if len(raw_reviewers) != len(V3_REVIEW_ROSTER):
        raise TrialError("v3 review roster must contain exactly two fixed slots")
    reviewers: list[dict[str, Any]] = []
    for index, (raw, expected) in enumerate(
        zip(raw_reviewers, V3_REVIEW_ROSTER, strict=True)
    ):
        path = f"contract.review_execution.reviewers[{index}]"
        reviewer = require_object(raw, path)
        reject_unknown_fields(reviewer, set(expected), path)
        normalized_reviewer: dict[str, Any] = {}
        for key, expected_value in expected.items():
            if isinstance(expected_value, bool):
                actual = require_bool(reviewer.get(key), f"{path}.{key}")
            else:
                actual = require_string(reviewer.get(key), f"{path}.{key}", max_chars=128)
            if actual != expected_value:
                raise TrialError(f"{path}.{key} does not match the owner-fixed roster")
            normalized_reviewer[key] = actual
        reviewers.append(normalized_reviewer)
    return {
        **normalized,
        "request_format": request_format,
        "review_instruction": review_instruction,
        "context_policy": expected_context_policy,
        "reviewers": reviewers,
    }


def validate_contract(value: dict[str, Any]) -> dict[str, Any]:
    schema = value.get("schema")
    if schema not in {
        CONTRACT_SCHEMA,
        CONTRACT_SCHEMA_V1,
        CONTRACT_SCHEMA_V2,
        CONTRACT_SCHEMA_V3,
    }:
        raise TrialError(
            "contract schema must be one of the supported v0/v1/v2/v3 schemas"
        )
    version = {
        CONTRACT_SCHEMA: 0,
        CONTRACT_SCHEMA_V1: 1,
        CONTRACT_SCHEMA_V2: 2,
        CONTRACT_SCHEMA_V3: 3,
    }[schema]
    expanded = version >= 1
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
    if version >= 2:
        contract_fields.update(
            {
                "context_projection",
                "coverage",
                "retry_policy",
                "failure_receipt",
                "execution_repo_path_sha256",
            }
        )
    if version >= 3:
        contract_fields.update({"review_execution", "conflicts_of_interest"})
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
    if expanded:
        harness_source_sha256 = require_sha256(
            value.get("harness_source_sha256"), "contract.harness_source_sha256"
        )
        if surface.sha256_file(Path(__file__)) != harness_source_sha256:
            raise TrialError("expanded harness source hash does not match the contract")
        surface_source_sha256 = require_sha256(
            value.get("surface_source_sha256"), "contract.surface_source_sha256"
        )
        if surface.sha256_file(Path(surface.__file__)) != surface_source_sha256:
            raise TrialError(
                "expanded surface helper source hash does not match the contract"
            )
        digest_key_sha256 = require_sha256(
            value.get("digest_key_sha256"), "contract.digest_key_sha256"
        )

    context_projection: dict[str, Any] | None = None
    coverage_contract: dict[str, Any] | None = None
    retry_policy: dict[str, Any] | None = None
    failure_receipt_contract: dict[str, Any] | None = None
    execution_repo_path_sha256: str | None = None
    review_execution: dict[str, Any] | None = None
    conflicts_of_interest: dict[str, Any] | None = None
    if version >= 2:
        execution_repo_path_sha256 = require_sha256(
            value.get("execution_repo_path_sha256"),
            "contract.execution_repo_path_sha256",
        )
        projection_raw = require_object(
            value.get("context_projection"), "contract.context_projection"
        )
        reject_unknown_fields(
            projection_raw,
            {
                "drop_record_fields",
                "identifier_aliases",
                "answer_postprocessing_allowed",
            },
            "contract.context_projection",
        )
        dropped_fields = [
            require_label(item, f"contract.context_projection.drop_record_fields[{index}]")
            for index, item in enumerate(
                require_list(
                    projection_raw.get("drop_record_fields"),
                    "contract.context_projection.drop_record_fields",
                )
            )
        ]
        if dropped_fields != SUCCESSOR_DROPPED_RECORD_FIELDS:
            raise TrialError("v2 dropped record fields are not fixed")
        aliases_raw = require_object(
            projection_raw.get("identifier_aliases"),
            "contract.context_projection.identifier_aliases",
        )
        reject_unknown_fields(
            aliases_raw,
            set(SUCCESSOR_IDENTIFIER_ALIASES),
            "contract.context_projection.identifier_aliases",
        )
        aliases = {
            key: require_string(
                aliases_raw.get(key),
                f"contract.context_projection.identifier_aliases.{key}",
                max_chars=128,
            )
            for key in SUCCESSOR_IDENTIFIER_ALIASES
        }
        if aliases != SUCCESSOR_IDENTIFIER_ALIASES:
            raise TrialError("v2 identifier aliases are not fixed")
        if require_bool(
            projection_raw.get("answer_postprocessing_allowed"),
            "contract.context_projection.answer_postprocessing_allowed",
        ):
            raise TrialError("v2 answer postprocessing must remain disabled")
        context_projection = {
            "drop_record_fields": dropped_fields,
            "identifier_aliases": aliases,
            "answer_postprocessing_allowed": False,
        }

        coverage_raw = require_object(value.get("coverage"), "contract.coverage")
        reject_unknown_fields(
            coverage_raw,
            {
                "min_reference_hits_non_abstention",
                "min_reference_hits_abstention",
                "require_unique_reference_keys",
                "generation_requires_status",
            },
            "contract.coverage",
        )
        coverage_contract = {
            "min_reference_hits_non_abstention": require_nonnegative_int(
                coverage_raw.get("min_reference_hits_non_abstention"),
                "contract.coverage.min_reference_hits_non_abstention",
            ),
            "min_reference_hits_abstention": require_nonnegative_int(
                coverage_raw.get("min_reference_hits_abstention"),
                "contract.coverage.min_reference_hits_abstention",
            ),
            "require_unique_reference_keys": require_bool(
                coverage_raw.get("require_unique_reference_keys"),
                "contract.coverage.require_unique_reference_keys",
            ),
            "generation_requires_status": require_string(
                coverage_raw.get("generation_requires_status"),
                "contract.coverage.generation_requires_status",
                max_chars=32,
            ),
        }
        if coverage_contract != {
            "min_reference_hits_non_abstention": 2,
            "min_reference_hits_abstention": 0,
            "require_unique_reference_keys": True,
            "generation_requires_status": "VALID",
        }:
            raise TrialError("v2 reference coverage policy is not fixed")

        retry_raw = require_object(value.get("retry_policy"), "contract.retry_policy")
        reject_unknown_fields(
            retry_raw,
            {
                "pre_model_full_restart_limit",
                "post_model_retry_limit",
                "semantic_retry_limit",
                "automatic_retry",
            },
            "contract.retry_policy",
        )
        retry_policy = {
            "pre_model_full_restart_limit": require_nonnegative_int(
                retry_raw.get("pre_model_full_restart_limit"),
                "contract.retry_policy.pre_model_full_restart_limit",
            ),
            "post_model_retry_limit": require_nonnegative_int(
                retry_raw.get("post_model_retry_limit"),
                "contract.retry_policy.post_model_retry_limit",
            ),
            "semantic_retry_limit": require_nonnegative_int(
                retry_raw.get("semantic_retry_limit"),
                "contract.retry_policy.semantic_retry_limit",
            ),
            "automatic_retry": require_bool(
                retry_raw.get("automatic_retry"),
                "contract.retry_policy.automatic_retry",
            ),
        }
        if retry_policy != {
            "pre_model_full_restart_limit": 1,
            "post_model_retry_limit": 0,
            "semantic_retry_limit": 0,
            "automatic_retry": False,
        }:
            raise TrialError("v2 retry policy is not fixed")

        failure_raw = require_object(
            value.get("failure_receipt"), "contract.failure_receipt"
        )
        reject_unknown_fields(
            failure_raw,
            {"private", "atomic_write", "raw_material_allowed"},
            "contract.failure_receipt",
        )
        failure_receipt_contract = {
            "private": require_bool(
                failure_raw.get("private"), "contract.failure_receipt.private"
            ),
            "atomic_write": require_bool(
                failure_raw.get("atomic_write"),
                "contract.failure_receipt.atomic_write",
            ),
            "raw_material_allowed": require_bool(
                failure_raw.get("raw_material_allowed"),
                "contract.failure_receipt.raw_material_allowed",
            ),
        }
        if failure_receipt_contract != {
            "private": True,
            "atomic_write": True,
            "raw_material_allowed": False,
        }:
            raise TrialError("v2 failure receipt policy is not fixed")

    if version >= 3:
        review_execution = validate_v3_review_execution(value.get("review_execution"))
        coi = require_object(
            value.get("conflicts_of_interest"), "contract.conflicts_of_interest"
        )
        reject_unknown_fields(
            coi,
            set(V3_CONFLICTS_OF_INTEREST),
            "contract.conflicts_of_interest",
        )
        if coi != V3_CONFLICTS_OF_INTEREST:
            raise TrialError("v3 conflicts-of-interest disclosure is not fixed")
        conflicts_of_interest = V3_CONFLICTS_OF_INTEREST

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
    fixed_conditions = EXPANDED_CONDITIONS if expanded else CONDITIONS
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
    if version >= 3 and (
        model,
        reasoning_effort,
        cli_version,
    ) != ("gpt-5.4", "medium", "codex-cli 0.144.1"):
        raise TrialError("v3 generator identity must preserve the fixed v2 comparison")

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
                    *(
                        {
                            "reviewer_type",
                            "cross_reviewer_provider_independence",
                            "self_attestation_sufficient",
                        }
                        if version >= 3
                        else set()
                    ),
                }
                if expanded
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
    if expanded:
        if require_nonnegative_int(
            review.get("required_reviewer_count"),
            "contract.review.required_reviewer_count",
        ) != 2:
            raise TrialError("expanded trials require exactly two independent reviewers")
        if not require_bool(
            review.get("independent_reviewers"),
            "contract.review.independent_reviewers",
        ):
            raise TrialError("expanded trial reviewers must be independent")
        abstention_values = require_list(
            review.get("abstention_values"),
            "contract.review.abstention_values",
        )
        if abstention_values != [False, True]:
            raise TrialError("expanded abstention values are not fixed")
        if version >= 3:
            if require_label(
                review.get("reviewer_type"), "contract.review.reviewer_type"
            ) != "headless_llm":
                raise TrialError("v3 reviews must use the fixed headless-LLM class")
            if not require_bool(
                review.get("cross_reviewer_provider_independence"),
                "contract.review.cross_reviewer_provider_independence",
            ):
                raise TrialError("v3 reviewers must be cross-provider")
            if require_bool(
                review.get("self_attestation_sufficient"),
                "contract.review.self_attestation_sufficient",
            ):
                raise TrialError("v3 reviewer self-attestation must not satisfy provenance")

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
    if expanded:
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
        *({"max_abstention_failures"} if expanded else set()),
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
        if expanded
        else [COMPACT_CONDITION, "portfolio_digest"]
    )
    if candidate_conditions != expected_candidates:
        raise TrialError("contract candidate conditions are not fixed")
    recommendation_scope = require_label(
        thresholds.get("recommendation_scope"),
        "contract.thresholds.recommendation_scope",
    )
    expected_scope = "write_side_trial_only" if expanded else "expanded_trial_only"
    if recommendation_scope != expected_scope:
        raise TrialError(
            f"contract recommendation scope must remain {expected_scope}"
        )
    normalized_thresholds["candidate_conditions"] = candidate_conditions
    normalized_thresholds["recommendation_scope"] = recommendation_scope
    if expanded:
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
            raise TrialError("expanded aggregation gates must both be all")
        normalized_thresholds["aggregation"] = normalized_aggregation
        if normalized_thresholds["max_abstention_failures"] != 0:
            raise TrialError("expanded max_abstention_failures must be zero")

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
                    {
                        "prompt_variant",
                        "requires_abstention",
                        *({"retrieval_query_sha256"} if version >= 2 else set()),
                    }
                    if expanded
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
            if expanded
            else "legacy"
        )
        if expanded and prompt_variant not in {"direct", "heldout"}:
            raise TrialError("expanded prompt_variant must be direct or heldout")
        prompt_sha256 = require_sha256(case.get("prompt_sha256"), f"{path}.prompt_sha256")
        retrieval_query_sha256 = (
            require_sha256(
                case.get("retrieval_query_sha256"),
                f"{path}.retrieval_query_sha256",
            )
            if version >= 2
            else prompt_sha256
        )
        requires_abstention = (
            require_bool(case.get("requires_abstention"), f"{path}.requires_abstention")
            if expanded
            else False
        )
        required_claims = validate_claims(
            case.get("required_claims"),
            f"{path}.required_claims",
            allow_empty=requires_abstention,
        )
        if expanded and requires_abstention and required_claims:
            raise TrialError("expanded abstention cases must have required_claims=[]")
        if expanded and not requires_abstention and not required_claims:
            raise TrialError("expanded non-abstention cases require claims")
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
                "retrieval_query_sha256": retrieval_query_sha256,
                "required_claims": required_claims,
                "optional_claims": optional_claims,
                "forbidden_claim_ids": forbidden,
                "requires_abstention": requires_abstention,
            }
        )
    if version == 0 and len(cases) != 2:
        raise TrialError("contract must contain exactly two preregistered cases")
    if expanded:
        if len(cases) != 12:
            raise TrialError(
                "expanded contract must contain exactly 12 preregistered cases"
            )
        strata = Counter(case["prompt_class"] for case in cases)
        if set(strata) != EXPANDED_STRATA or set(strata.values()) != {2}:
            raise TrialError(
                "expanded contract must contain six fixed prompt strata with two cases each"
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
            raise TrialError(
                "expanded strata must each contain direct and heldout variants"
            )
        if any(
            all(
                case["requires_abstention"]
                for case in cases
                if case["prompt_class"] == stratum
            )
            for stratum in strata
        ):
            raise TrialError(
                "expanded strata must retain a non-abstention completeness case"
            )
        if sum(case["requires_abstention"] for case in cases) != 2:
            raise TrialError("expanded contract requires exactly two abstention cases")

    boundaries = require_object(value.get("boundaries"), "contract.boundaries")
    expected_boundaries = {
        "raw_artifacts_in_git": False,
        "writes_live_ab_store": False,
        "llm_judge": version >= 3,
        "automatic_unblinding": False,
        "runtime_promotion_allowed": False,
        "automatic_digest_regeneration_allowed": False,
        "compact_default_change_allowed": False,
        "benchmark_claim_allowed": False,
        "version_or_tag_change_allowed": False,
        **(
            {"release_action_allowed": False, "ci_action_allowed": False}
            if expanded
            else {}
        ),
        **(
            {
                "answer_postprocessing_allowed": False,
                "ad_hoc_retry_allowed": False,
            }
            if version >= 2
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
            if expanded
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
                if expanded
                else {}
            ),
            **({"abstention_values": abstention_values} if expanded else {}),
            **(
                {
                    "reviewer_type": "headless_llm",
                    "cross_reviewer_provider_independence": True,
                    "self_attestation_sufficient": False,
                }
                if version >= 3
                else {}
            ),
        },
        "thresholds": normalized_thresholds,
        "cases": cases,
        "boundaries": expected_boundaries,
        **(
            {
                "context_projection": context_projection,
                "coverage": coverage_contract,
                "retry_policy": retry_policy,
                "failure_receipt": failure_receipt_contract,
                "execution_repo_path_sha256": execution_repo_path_sha256,
            }
            if version >= 2
            else {}
        ),
        **(
            {
                "review_execution": review_execution,
                "conflicts_of_interest": conflicts_of_interest,
            }
            if version >= 3
            else {}
        ),
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
    try:
        repo = repo.resolve(strict=True)
    except OSError as exc:
        raise TrialError("failed to resolve spec.repo") from exc
    if is_successor(contract) and sha256_text(str(repo)) != contract[
        "execution_repo_path_sha256"
    ]:
        raise TrialError("spec.repo does not match successor execution worktree commitment")
    digest_key = require_string(value.get("digest_key"), "spec.digest_key", max_chars=256)
    if is_expanded(contract) and sha256_text(digest_key) != contract[
        "digest_key_sha256"
    ]:
        raise TrialError("spec.digest_key does not match the expanded contract commitment")
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
        allowed_case_fields = {"case_id", "prompt"}
        if is_successor(contract):
            allowed_case_fields.add("retrieval_query")
        reject_unknown_fields(case, allowed_case_fields, path)
        case_id = require_label(case.get("case_id"), f"{path}.case_id")
        if case_id != contract_case["case_id"]:
            raise TrialError("spec case order/id does not match the contract")
        prompt = require_string(case.get("prompt"), f"{path}.prompt", max_chars=16_000)
        if sha256_text(prompt) != contract_case["prompt_sha256"]:
            raise TrialError("spec prompt does not match its preregistered hash")
        retrieval_query = prompt
        if is_successor(contract):
            retrieval_query = require_string(
                case.get("retrieval_query"),
                f"{path}.retrieval_query",
                max_chars=16_000,
            )
            if sha256_text(retrieval_query) != contract_case["retrieval_query_sha256"]:
                raise TrialError(
                    "spec retrieval query does not match its preregistered hash"
                )
        cases.append(
            {**contract_case, "prompt": prompt, "retrieval_query": retrieval_query}
        )
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


def git_root(path: Path) -> Path:
    try:
        completed = subprocess.run(
            ["git", "-C", str(path), "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise TrialError("failed to resolve the execution git root") from exc
    root = Path(completed.stdout.strip()).resolve()
    if completed.returncode != 0 or not root.is_dir():
        raise TrialError("failed to resolve the execution git root")
    return root


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
    spec_raw, spec_bytes = read_json(spec_path)
    spec_sha = sha256_bytes(spec_bytes)
    spec = validate_spec(spec_raw, contract, contract_sha)
    repo: Path = spec["repo"]
    if git_head(repo) != spec["contract_commit"]:
        raise TrialError("repository HEAD does not match spec.contract_commit")
    if is_expanded(contract):
        require_committed_file(
            repo, spec["contract_commit"], contract_path, "expanded contract"
        )
        require_committed_file(
            repo,
            spec["contract_commit"],
            Path(__file__),
            "expanded harness source",
        )
        require_committed_file(
            repo,
            spec["contract_commit"],
            Path(surface.__file__),
            "expanded surface helper source",
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
            retrieval_query = case["retrieval_query"]

            def full_search(client: surface.McpClient) -> dict[str, Any]:
                result, latency = client.request(
                    "tools/call",
                    {
                        "name": "memory_search",
                        "arguments": {
                            "query": retrieval_query,
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
                context = (
                    project_successor_context(
                        REFERENCE_CONDITION,
                        hits,
                        contract["context_projection"],
                    )
                    if is_successor(contract)
                    else text
                )
                return {
                    "condition": make_context(context, latency, hits),
                    "ranked_keys": keys,
                }

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
                context = (
                    project_successor_context(
                        "portfolio_digest",
                        record,
                        contract["context_projection"],
                    )
                    if is_successor(contract)
                    else text
                )
                return {"condition": make_context(context, latency, record)}

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
                        if is_expanded(contract)
                        else {}
                    ),
                    "prompt": prompt,
                    "prompt_sha256": case["prompt_sha256"],
                    **(
                        {
                            "retrieval_query": retrieval_query,
                            "retrieval_query_sha256": case[
                                "retrieval_query_sha256"
                            ],
                        }
                        if is_successor(contract)
                        else {}
                    ),
                    "required_claims": case["required_claims"],
                    "optional_claims": case["optional_claims"],
                    "forbidden_claim_ids": case["forbidden_claim_ids"],
                    **(
                        {"requires_abstention": case["requires_abstention"]}
                        if is_expanded(contract)
                        else {}
                    ),
                    "ranking_projection_invariant": COMPACT_CONDITION in conditions,
                    "conditions": {
                        condition: condition_rows[condition] for condition in conditions
                    },
                }
            )

    coverage = (
        evaluate_successor_coverage(cases, contract["coverage"])
        if is_successor(contract)
        else None
    )
    if any(run["snapshot_sha256_before"] != base_snapshot_sha for run in runs):
        raise TrialError("an isolated condition did not start from the shared base snapshot")
    capture = {
        "schema": versioned_schema(contract, CAPTURE_SCHEMA, CAPTURE_SCHEMA_V1),
        "trial_id": spec["trial_id"],
        "contract_sha256": contract_sha,
        "contract_commit": spec["contract_commit"],
        **({"spec_sha256": spec_sha} if is_successor(contract) else {}),
        "captured_at": captured_at,
        "runtime_source_commit": contract["runtime_source_commit"],
        "binary_observation": binary_observation,
        "base_snapshot_sha256": base_snapshot_sha,
        "runs": runs,
        "cases": cases,
        **({"coverage": coverage} if is_successor(contract) else {}),
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
            **(
                {
                    "pre_generation_context_projection": True,
                    "raw_retrieval_query_private": True,
                }
                if is_successor(contract)
                else {}
            ),
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
                    if is_expanded(contract)
                    else {}
                ),
                "prompt_sha256": case["prompt_sha256"],
                **(
                    {"retrieval_query_sha256": case["retrieval_query_sha256"]}
                    if is_successor(contract)
                    else {}
                ),
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
        **({"spec_sha256": spec_sha} if is_successor(contract) else {}),
        "capture_sha256": sha256_bytes(raw_bytes),
        "captured_at": captured_at,
        "runtime_source_commit": contract["runtime_source_commit"],
        "binary_observation": binary_observation,
        "base_snapshot_sha256": base_snapshot_sha,
        "case_count": len(cases),
        "condition_run_count": len(runs),
        "cases": redacted_cases,
        **({"coverage": coverage} if is_successor(contract) else {}),
        "boundary": {
            "raw_prompt_in_packet": False,
            "raw_context_in_packet": False,
            "raw_memory_key_in_packet": False,
            **(
                {"raw_retrieval_query_in_packet": False}
                if is_successor(contract)
                else {}
            ),
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
            *({"spec_sha256"} if is_successor(contract) else set()),
            "captured_at",
            "runtime_source_commit",
            "binary_observation",
            "base_snapshot_sha256",
            "runs",
            "cases",
            *({"coverage"} if is_successor(contract) else set()),
            "boundary",
        },
        "capture",
    )
    if require_sha256(value.get("contract_sha256"), "capture.contract_sha256") != contract_sha:
        raise TrialError("capture contract hash mismatch")
    trial_id = require_label(value.get("trial_id"), "capture.trial_id")
    contract_commit = require_commit(value.get("contract_commit"), "capture.contract_commit")
    spec_sha = (
        require_sha256(value.get("spec_sha256"), "capture.spec_sha256")
        if is_successor(contract)
        else None
    )
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
        **(
            {
                "pre_generation_context_projection": True,
                "raw_retrieval_query_private": True,
            }
            if is_successor(contract)
            else {}
        ),
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
                    {
                        "prompt_variant",
                        "requires_abstention",
                        *(
                            {"retrieval_query", "retrieval_query_sha256"}
                            if is_successor(contract)
                            else set()
                        ),
                    }
                    if is_expanded(contract)
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
        if is_expanded(contract) and require_label(
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
        retrieval_query = prompt
        if is_successor(contract):
            retrieval_query = require_string(
                case.get("retrieval_query"),
                "capture retrieval_query",
                max_chars=16_000,
            )
            if sha256_text(retrieval_query) != contract_case[
                "retrieval_query_sha256"
            ]:
                raise TrialError("capture retrieval query hash mismatch")
            if require_sha256(
                case.get("retrieval_query_sha256"),
                "capture retrieval_query_sha256",
            ) != contract_case["retrieval_query_sha256"]:
                raise TrialError("capture stored retrieval query hash mismatch")
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
        if is_expanded(contract) and require_bool(
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
        if is_successor(contract):
            full_hits = require_list(
                conditions[REFERENCE_CONDITION]["raw_result"],
                "capture successor full-search raw_result",
            )
            expected_context = project_successor_context(
                REFERENCE_CONDITION,
                full_hits,
                contract["context_projection"],
            )
            if full_context != expected_context:
                raise TrialError(
                    "capture successor full-search context is not the fixed projection"
                )
        else:
            full_hits, _ = surface.normalize_search(full_context)
            if conditions[REFERENCE_CONDITION]["raw_result"] != full_hits:
                raise TrialError(
                    "capture full-search raw result does not match its context"
                )
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
        if is_successor(contract):
            expected_digest_context = project_successor_context(
                "portfolio_digest",
                digest_raw,
                contract["context_projection"],
            )
            if conditions["portfolio_digest"]["context"] != expected_digest_context:
                raise TrialError(
                    "capture successor digest context is not the fixed projection"
                )
        elif digest_raw != digest_context:
            raise TrialError("capture digest raw result does not match its context")
        digest_key = require_string(
            digest_raw.get("key"), "capture digest key", max_chars=256
        )
        if is_expanded(contract) and sha256_text(digest_key) != contract[
            "digest_key_sha256"
        ]:
            raise TrialError("capture digest key does not match the expanded commitment")
        require_string(digest_raw.get("content"), "capture digest content")

        cases.append(
            {
                **contract_case,
                "prompt": prompt,
                "retrieval_query": retrieval_query,
                "conditions": conditions,
            }
        )
    coverage = None
    if is_successor(contract):
        coverage = evaluate_successor_coverage(cases, contract["coverage"])
        if require_object(value.get("coverage"), "capture.coverage") != coverage:
            raise TrialError("capture successor coverage summary drifted")
    return {
        "trial_id": trial_id,
        "contract_commit": contract_commit,
        **({"spec_sha256": spec_sha} if is_successor(contract) else {}),
        "captured_at": captured_at,
        "capture_sha256": sha256_bytes(capture_bytes),
        "cases": cases,
        **({"coverage": coverage} if is_successor(contract) else {}),
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


def validate_generation_failure_receipt(
    value: dict[str, Any],
    raw_bytes: bytes,
    contract: dict[str, Any],
    contract_sha: str,
    spec_sha: str,
    capture: dict[str, Any],
) -> dict[str, Any]:
    if not is_successor(contract):
        raise TrialError("generation failure receipts require a successor contract")
    reject_unknown_fields(
        value,
        {
            "schema",
            "trial_id",
            "contract_sha256",
            "contract_commit",
            "spec_sha256",
            "capture_sha256",
            "failed_at",
            "attempt",
            "prior_failure_receipt_sha256",
            "phase",
            "error_code",
            "case_id",
            "condition",
            "invocation_index",
            "model_started",
            "any_model_started",
            "answer_sha256",
            "matched_marker_sha256",
            "retry_authorized",
            "retry_scope",
            "boundary",
        },
        "generation failure receipt",
    )
    expected_schema = successor_schema(contract, FAILURE_RECEIPT_SCHEMA_V2)
    if value.get("schema") != expected_schema:
        raise TrialError(
            f"generation failure receipt schema must be {expected_schema}"
        )
    if require_label(
        value.get("trial_id"), "generation failure receipt.trial_id"
    ) != capture["trial_id"]:
        raise TrialError("generation failure receipt trial id mismatch")
    if require_sha256(
        value.get("contract_sha256"),
        "generation failure receipt.contract_sha256",
    ) != contract_sha:
        raise TrialError("generation failure receipt contract hash mismatch")
    if require_commit(
        value.get("contract_commit"),
        "generation failure receipt.contract_commit",
    ) != capture["contract_commit"]:
        raise TrialError("generation failure receipt contract commit mismatch")
    if require_sha256(
        value.get("spec_sha256"), "generation failure receipt.spec_sha256"
    ) != spec_sha:
        raise TrialError("generation failure receipt spec hash mismatch")
    if require_sha256(
        value.get("capture_sha256"),
        "generation failure receipt.capture_sha256",
    ) != capture["capture_sha256"]:
        raise TrialError("generation failure receipt capture hash mismatch")
    failed_at = require_nonnegative_int(
        value.get("failed_at"), "generation failure receipt.failed_at"
    )
    if failed_at <= 0:
        raise TrialError("generation failure receipt timestamp is missing")
    attempt = require_nonnegative_int(
        value.get("attempt"), "generation failure receipt.attempt"
    )
    if attempt not in {1, 2}:
        raise TrialError("generation failure receipt attempt must be one or two")
    prior_sha = value.get("prior_failure_receipt_sha256")
    if prior_sha is not None:
        prior_sha = require_sha256(
            prior_sha,
            "generation failure receipt.prior_failure_receipt_sha256",
        )
    if (attempt == 1) is not (prior_sha is None):
        raise TrialError("generation failure receipt prior-attempt binding is invalid")
    phase = require_label(value.get("phase"), "generation failure receipt.phase")
    error_code = require_label(
        value.get("error_code"), "generation failure receipt.error_code"
    )
    case_id = value.get("case_id")
    if case_id is not None:
        case_id = require_label(case_id, "generation failure receipt.case_id")
        if case_id not in {case["case_id"] for case in capture["cases"]}:
            raise TrialError("generation failure receipt case id is unknown")
    condition = value.get("condition")
    if condition is not None:
        condition = require_label(
            condition, "generation failure receipt.condition"
        )
        if condition not in contract_conditions(contract):
            raise TrialError("generation failure receipt condition is unknown")
    invocation_index = require_nonnegative_int(
        value.get("invocation_index"),
        "generation failure receipt.invocation_index",
    )
    if (case_id is None) is not (condition is None):
        raise TrialError("generation failure receipt coordinates are inconsistent")
    if invocation_index > 0 and case_id is None:
        raise TrialError("generation failure invocation is missing case coordinates")
    model_started = require_bool(
        value.get("model_started"),
        "generation failure receipt.model_started",
    )
    any_model_started = require_bool(
        value.get("any_model_started"),
        "generation failure receipt.any_model_started",
    )
    if model_started and not any_model_started:
        raise TrialError("generation failure receipt model state is inconsistent")
    answer_sha = value.get("answer_sha256")
    if answer_sha is not None:
        answer_sha = require_sha256(
            answer_sha, "generation failure receipt.answer_sha256"
        )
    marker_sha = value.get("matched_marker_sha256")
    if marker_sha is not None:
        marker_sha = require_sha256(
            marker_sha,
            "generation failure receipt.matched_marker_sha256",
        )
        if answer_sha is None:
            raise TrialError("generation failure marker hash requires an answer hash")
    retry_authorized = require_bool(
        value.get("retry_authorized"),
        "generation failure receipt.retry_authorized",
    )
    retry_scope = require_label(
        value.get("retry_scope"), "generation failure receipt.retry_scope"
    )
    expected_retry = (
        attempt == 1
        and phase == "pre_model_infrastructure"
        and error_code in RETRYABLE_PRE_MODEL_ERROR_CODES
        and not model_started
        and not any_model_started
    )
    if retry_authorized is not expected_retry:
        raise TrialError("generation failure receipt retry authorization drifted")
    expected_scope = "explicit_full_restart" if expected_retry else "none"
    if retry_scope != expected_scope:
        raise TrialError("generation failure receipt retry scope drifted")
    boundary = require_object(
        value.get("boundary"), "generation failure receipt.boundary"
    )
    expected_boundary = {
        "private": True,
        "atomic_write": True,
        "raw_prompt_present": False,
        "raw_retrieval_query_present": False,
        "raw_context_present": False,
        "raw_answer_present": False,
        "raw_marker_present": False,
        "automatic_retry": False,
    }
    reject_unknown_fields(
        boundary,
        set(expected_boundary),
        "generation failure receipt.boundary",
    )
    if boundary != expected_boundary:
        raise TrialError("generation failure receipt privacy boundary is incomplete")
    return {
        "attempt": attempt,
        "retry_authorized": retry_authorized,
        "receipt_sha256": sha256_bytes(raw_bytes),
    }


def write_generation_failure_receipt(
    *,
    output_path: Path,
    contract: dict[str, Any],
    contract_sha: str,
    spec_sha: str,
    capture: dict[str, Any],
    attempt: int,
    prior_receipt_sha: str | None,
    failure: GenerationFailure,
    any_model_started: bool,
    case_id: str | None,
    condition: str | None,
    invocation_index: int,
    protected_inputs: tuple[Path, ...],
) -> dict[str, Any]:
    retry_authorized = (
        attempt == 1
        and failure.phase == "pre_model_infrastructure"
        and failure.error_code in RETRYABLE_PRE_MODEL_ERROR_CODES
        and not failure.model_started
        and not any_model_started
    )
    packet = {
        "schema": successor_schema(contract, FAILURE_RECEIPT_SCHEMA_V2),
        "trial_id": capture["trial_id"],
        "contract_sha256": contract_sha,
        "contract_commit": capture["contract_commit"],
        "spec_sha256": spec_sha,
        "capture_sha256": capture["capture_sha256"],
        "failed_at": int(time.time()),
        "attempt": attempt,
        "prior_failure_receipt_sha256": prior_receipt_sha,
        "phase": failure.phase,
        "error_code": failure.error_code,
        "case_id": case_id,
        "condition": condition,
        "invocation_index": invocation_index,
        "model_started": failure.model_started,
        "any_model_started": any_model_started,
        "answer_sha256": failure.answer_sha256,
        "matched_marker_sha256": failure.matched_marker_sha256,
        "retry_authorized": retry_authorized,
        "retry_scope": "explicit_full_restart" if retry_authorized else "none",
        "boundary": {
            "private": True,
            "atomic_write": True,
            "raw_prompt_present": False,
            "raw_retrieval_query_present": False,
            "raw_context_present": False,
            "raw_answer_present": False,
            "raw_marker_present": False,
            "automatic_retry": False,
        },
    }
    rendered = surface.render_json(packet)
    validate_generation_failure_receipt(
        packet,
        rendered,
        contract,
        contract_sha,
        spec_sha,
        capture,
    )
    written = write_json(output_path, packet, protected_paths=protected_inputs)
    if written != rendered:
        raise TrialError("generation failure receipt serialization drifted")
    return packet


def claim_generation_attempt(
    *,
    repo: Path,
    contract: dict[str, Any],
    contract_sha: str,
    spec_sha: str,
    capture_sha: str,
    attempt: int,
    prior_receipt_sha: str | None,
    reserved_paths: tuple[Path, ...],
) -> tuple[Path, ...]:
    if attempt not in {1, 2}:
        raise TrialError("generation attempt claim must be one or two")
    if (attempt == 1) is not (prior_receipt_sha is None):
        raise TrialError("generation attempt claim prior binding is invalid")
    claim_dir = repo / "data" / "portfolio-continuity-generation-claims"
    try:
        claim_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
        if claim_dir.stat().st_mode & 0o077:
            raise TrialError("private attempt claim directory permissions are too broad")
    except OSError as exc:
        raise TrialError("failed to prepare the private attempt claim directory") from exc
    # A successor contract represents one preregistered execution, not a family of
    # executions selected by mutable private-spec bytes or capture contents.
    # Keep those hashes in the claim packet for provenance, but key the
    # exclusive claim only by the frozen public contract. This closes retries
    # through cosmetic/private-spec changes, changed trial IDs, or recapture.
    claim_schema = successor_schema(
        contract, "agent_bridge.portfolio_continuity_answer_attempt_claim.v2"
    )
    identity_sha = sha256_text(f"{claim_schema}\0{contract_sha}")
    first_claim_path = claim_dir / f"{identity_sha}.attempt-1.json"
    resolved_claim_dir = claim_dir.resolve(strict=False)
    if any(
        path.resolve(strict=False).is_relative_to(resolved_claim_dir)
        for path in reserved_paths
    ):
        raise TrialError("generation outputs must not use the attempt claim directory")
    if attempt == 2 and not first_claim_path.is_file():
        raise TrialError("attempt two is missing the claimed first attempt")
    claim_path = claim_dir / f"{identity_sha}.attempt-{attempt}.json"
    require_ignored_data_path(repo, claim_path, "generation attempt claim")
    packet = {
        "schema": claim_schema,
        "execution_identity_sha256": identity_sha,
        "contract_sha256": contract_sha,
        "spec_sha256": spec_sha,
        "capture_sha256": capture_sha,
        "attempt": attempt,
        "prior_failure_receipt_sha256": prior_receipt_sha,
        "claimed_at": int(time.time()),
        "boundary": {
            "private": True,
            "single_use": True,
            "raw_material_present": False,
        },
    }
    rendered = surface.render_json(packet)
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_CLOEXEC", 0)
    flags |= getattr(os, "O_NOFOLLOW", 0)
    try:
        file_descriptor = os.open(claim_path, flags, 0o600)
        try:
            handle = os.fdopen(file_descriptor, "wb")
        except (OSError, ValueError):
            os.close(file_descriptor)
            raise
        with handle:
            handle.write(rendered)
            handle.flush()
            os.fsync(handle.fileno())
        directory_descriptor = os.open(
            claim_dir,
            os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_CLOEXEC", 0),
        )
        try:
            os.fsync(directory_descriptor)
        finally:
            os.close(directory_descriptor)
    except FileExistsError as exc:
        raise TrialError("generation attempt was already claimed") from exc
    except OSError as exc:
        raise TrialError("failed to atomically claim generation attempt") from exc
    claim_paths = [claim_path]
    if first_claim_path != claim_path:
        claim_paths.insert(0, first_claim_path)
    return tuple(claim_paths)


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
        try:
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
        except TrialError as exc:
            if not is_successor(contract):
                raise
            raise GenerationFailure(
                "generation_workspace_failed",
                "pre_model_infrastructure",
                "failed to prepare the isolated generation workspace",
                model_started=False,
            ) from exc
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
        except OSError as exc:
            if not is_successor(contract):
                raise TrialError(f"Codex generation failed to complete: {exc}") from exc
            raise GenerationFailure(
                "codex_spawn_failed",
                "pre_model_infrastructure",
                "failed to start the Codex generation process",
                model_started=False,
            ) from exc
        except subprocess.TimeoutExpired as exc:
            if not is_successor(contract):
                raise TrialError(f"Codex generation failed to complete: {exc}") from exc
            raise GenerationFailure(
                "codex_timeout",
                "model_execution",
                "Codex generation timed out",
                model_started=True,
            ) from exc
        latency_ms = (time.perf_counter() - started) * 1000.0
        if completed.returncode != 0:
            raise GenerationFailure(
                "codex_exit_unsuccessful",
                "model_execution",
                "Codex generation exited unsuccessfully",
                model_started=True,
            )
        if len(completed.stdout.encode("utf-8")) > 2_000_000:
            raise GenerationFailure(
                "event_stream_too_large",
                "post_model_validation",
                "Codex JSONL event stream is unexpectedly large",
                model_started=True,
            )
        if len(completed.stderr.encode("utf-8")) > 256_000:
            raise GenerationFailure(
                "stderr_too_large",
                "post_model_validation",
                "Codex stderr is unexpectedly large",
                model_started=True,
            )
        try:
            event_counts = parse_codex_events(completed.stdout)
        except TrialError as exc:
            if not is_successor(contract):
                raise
            error_code = (
                "tool_use_detected"
                if "attempted tool use" in str(exc)
                else "event_stream_invalid"
            )
            raise GenerationFailure(
                error_code,
                "semantic_validation",
                "Codex event stream violated the generation contract",
                model_started=True,
            ) from exc
        try:
            answer_packet, answer_bytes = read_json(output_path)
            reject_unknown_fields(answer_packet, {"answer_markdown"}, "Codex answer")
            raw_answer = require_string(
                answer_packet.get("answer_markdown"),
                "Codex answer.answer_markdown",
                max_chars=generation["max_answer_chars"],
            )
        except (OSError, TrialError) as exc:
            if not is_successor(contract):
                raise
            raise GenerationFailure(
                "output_schema_invalid",
                "semantic_validation",
                "Codex answer packet violated the output schema",
                model_started=True,
            ) from exc
        answer = raw_answer if is_successor(contract) else raw_answer.strip()
        forbidden_markers = set(CONDITIONS) | {
            "portfolio_state_digest",
            "=== EVIDENCE CONTEXT ===",
        }
        if extra_forbidden_markers is not None:
            forbidden_markers.update(extra_forbidden_markers)
        matched_marker = next(
            (marker for marker in sorted(forbidden_markers) if marker in answer),
            None,
        )
        if matched_marker is not None:
            raise GenerationFailure(
                "answer_marker_leak",
                "semantic_validation",
                "Codex answer leaked a condition/evidence marker",
                model_started=True,
                answer_sha256=sha256_text(answer),
                matched_marker_sha256=sha256_text(matched_marker),
            )
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


def forbidden_claim_id(seed: str, case_id: str, claim_id: str) -> str:
    return "forbid_" + sha256_text(
        f"{seed}\0forbidden-claim-id\0{case_id}\0{claim_id}"
    )[:24]


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
    failure_output: Path | None = None,
    prior_failure_receipt: Path | None = None,
) -> dict[str, Any]:
    protected_inputs = (
        contract_path,
        spec_path,
        capture_path,
        codex_binary,
        Path(__file__),
        Path(surface.__file__),
        *((prior_failure_receipt,) if prior_failure_receipt is not None else ()),
    )
    output_paths = {
        "generation_output": generation_output,
        "blind_output": blind_output,
        "map_output": map_output,
        "review_template_output": review_template_output,
        "redacted_output": redacted_output,
    }
    all_paths = {
        "contract": contract_path,
        "spec": spec_path,
        "capture": capture_path,
        "codex_binary": codex_binary,
        "harness_source": Path(__file__),
        "surface_source": Path(surface.__file__),
        **output_paths,
        **({"failure_output": failure_output} if failure_output is not None else {}),
        **(
            {"prior_failure_receipt": prior_failure_receipt}
            if prior_failure_receipt is not None
            else {}
        ),
    }
    require_distinct_paths(all_paths)
    contract, contract_sha = load_contract(contract_path)
    conditions = contract_conditions(contract)
    if is_successor(contract):
        if failure_output is None:
            raise TrialError("v2 generation requires --failure-output")
    elif failure_output is not None or prior_failure_receipt is not None:
        raise TrialError("failure receipts are supported only by v2 generation")
    spec_raw, spec_bytes = read_json(spec_path)
    spec_sha = sha256_bytes(spec_bytes)
    spec = validate_spec(spec_raw, contract, contract_sha)
    capture_raw, capture_bytes = read_json(capture_path)
    capture = validate_capture(capture_raw, capture_bytes, contract, contract_sha)
    if capture["trial_id"] != spec["trial_id"] or capture["contract_commit"] != spec["contract_commit"]:
        raise TrialError("capture/spec trial identity mismatch")
    if is_successor(contract) and capture["spec_sha256"] != spec_sha:
        raise TrialError("capture/spec private byte identity mismatch")
    attempt = 1
    prior_receipt_sha: str | None = None
    if prior_failure_receipt is not None:
        prior_raw, prior_bytes = read_json(prior_failure_receipt)
        prior = validate_generation_failure_receipt(
            prior_raw,
            prior_bytes,
            contract,
            contract_sha,
            spec_sha,
            capture,
        )
        if prior["attempt"] != 1 or not prior["retry_authorized"]:
            raise TrialError(
                "prior failure receipt does not authorize an explicit full restart"
            )
        attempt = 2
        prior_receipt_sha = prior["receipt_sha256"]
    repo: Path = spec["repo"]
    if git_head(repo) != spec["contract_commit"]:
        raise TrialError("repository HEAD does not match the preregistered capture commit")
    if is_expanded(contract):
        require_committed_file(
            repo, spec["contract_commit"], contract_path, "expanded contract"
        )
        require_committed_file(
            repo,
            spec["contract_commit"],
            Path(__file__),
            "expanded harness source",
        )
        require_committed_file(
            repo,
            spec["contract_commit"],
            Path(surface.__file__),
            "expanded surface helper source",
        )
    private_outputs = {
        **output_paths,
        **({"failure_output": failure_output} if failure_output is not None else {}),
    }
    for label, path in private_outputs.items():
        require_ignored_data_path(repo, path, label)
        if is_successor(contract) and (path.exists() or path.is_symlink()):
            raise TrialError("v2 generation requires fresh output paths")
    if attempt == 2:
        if prior_receipt_sha is None:
            raise TrialError("attempt two is missing its prior failure receipt hash")
    if is_successor(contract):
        attempt_claim_paths = claim_generation_attempt(
            repo=repo,
            contract=contract,
            contract_sha=contract_sha,
            spec_sha=spec_sha,
            capture_sha=capture["capture_sha256"],
            attempt=attempt,
            prior_receipt_sha=prior_receipt_sha,
            reserved_paths=tuple(private_outputs.values()),
        )
        protected_inputs += attempt_claim_paths
    if is_successor(contract) and capture["coverage"]["status"] != contract[
        "coverage"
    ]["generation_requires_status"]:
        failure = GenerationFailure(
            "reference_coverage_invalid",
            "pre_model_gate",
            "successor reference coverage does not permit generation",
            model_started=False,
        )
        write_generation_failure_receipt(
            output_path=failure_output,
            contract=contract,
            contract_sha=contract_sha,
            spec_sha=spec_sha,
            capture=capture,
            attempt=attempt,
            prior_receipt_sha=prior_receipt_sha,
            failure=failure,
            any_model_started=False,
            case_id=capture["coverage"]["failed_case_ids"][0],
            condition=REFERENCE_CONDITION,
            invocation_index=0,
            protected_inputs=protected_inputs,
        )
        raise TrialError("successor generation stopped at the reference coverage gate")
    try:
        codex_observation = observe_codex_identity(
            codex_binary, contract["generation"]["cli_version"], timeout
        )
    except TrialError as exc:
        if is_successor(contract):
            failure = GenerationFailure(
                "codex_identity_unavailable",
                "pre_model_infrastructure",
                "Codex identity preflight failed",
                model_started=False,
            )
            write_generation_failure_receipt(
                output_path=failure_output,
                contract=contract,
                contract_sha=contract_sha,
                spec_sha=spec_sha,
                capture=capture,
                attempt=attempt,
                prior_receipt_sha=prior_receipt_sha,
                failure=failure,
                any_model_started=False,
                case_id=None,
                condition=None,
                invocation_index=0,
                protected_inputs=protected_inputs,
            )
            raise TrialError("successor generation failed Codex identity preflight") from exc
        raise

    jobs = [
        (case, condition)
        for case in capture["cases"]
        for condition in conditions
    ]
    jobs.sort(key=lambda item: generation_order(spec["blind_seed"], item[0]["case_id"], item[1]))
    answers_by_case: dict[str, dict[str, dict[str, Any]]] = {
        case["case_id"]: {} for case in capture["cases"]
    }
    any_model_started = False
    for invocation_index, (case, condition) in enumerate(jobs, start=1):
        try:
            generated = generate_one_answer(
                codex_binary=codex_binary,
                contract=contract,
                question=case["prompt"],
                context=case["conditions"][condition]["context"],
                extra_forbidden_markers=(
                    {spec["digest_key"]} if is_expanded(contract) else None
                ),
                timeout=timeout,
            )
        except GenerationFailure as failure:
            any_model_started = any_model_started or failure.model_started
            if is_successor(contract):
                write_generation_failure_receipt(
                    output_path=failure_output,
                    contract=contract,
                    contract_sha=contract_sha,
                    spec_sha=spec_sha,
                    capture=capture,
                    attempt=attempt,
                    prior_receipt_sha=prior_receipt_sha,
                    failure=failure,
                    any_model_started=any_model_started,
                    case_id=case["case_id"],
                    condition=condition,
                    invocation_index=invocation_index,
                    protected_inputs=protected_inputs,
                )
                raise TrialError(
                    f"successor generation stopped with {failure.error_code}"
                ) from failure
            raise
        any_model_started = True
        generated["invocation_index"] = invocation_index
        generated["context_sha256"] = case["conditions"][condition]["context_sha256"]
        generated["context_tokens_estimate"] = case["conditions"][condition][
            "context_tokens_estimate"
        ]
        answers_by_case[case["case_id"]][condition] = generated

    def write_generation_artifact(path: Path, packet: dict[str, Any]) -> bytes:
        try:
            return write_json(path, packet, protected_paths=protected_inputs)
        except TrialError as exc:
            if is_successor(contract):
                failure = GenerationFailure(
                    "artifact_write_failed",
                    "post_model_artifact",
                    "failed to write a generation artifact",
                    model_started=True,
                )
                write_generation_failure_receipt(
                    output_path=failure_output,
                    contract=contract,
                    contract_sha=contract_sha,
                    spec_sha=spec_sha,
                    capture=capture,
                    attempt=attempt,
                    prior_receipt_sha=prior_receipt_sha,
                    failure=failure,
                    any_model_started=True,
                    case_id=None,
                    condition=None,
                    invocation_index=0,
                    protected_inputs=protected_inputs,
                )
                raise TrialError(
                    "successor generation stopped with artifact_write_failed"
                ) from exc
            raise

    generated_at = int(time.time())
    generation_cases = []
    for case in capture["cases"]:
        generation_cases.append(
            {
                "case_id": case["case_id"],
                "prompt_class": case["prompt_class"],
                **(
                    {"prompt_variant": case["prompt_variant"]}
                    if is_expanded(contract)
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
                    if is_expanded(contract)
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
        **(
            {
                "attempt": attempt,
                "prior_failure_receipt_sha256": prior_receipt_sha,
            }
            if is_successor(contract)
            else {}
        ),
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
            **(
                {
                    "answer_postprocessing_applied": False,
                    "automatic_retry": False,
                }
                if is_successor(contract)
                else {}
            ),
        },
    }
    generation_bytes = write_generation_artifact(
        generation_output, generation_packet
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
        forbidden_mappings = [
            {
                "forbidden_claim_id": forbidden_claim_id(
                    spec["blind_seed"], case["case_id"], claim_id
                ),
                "claim_id": claim_id,
            }
            for claim_id in case["forbidden_claim_ids"]
        ]
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
                        if is_expanded(contract) and case["requires_abstention"]
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
                    if is_expanded(contract)
                    else {}
                ),
                "question": case["prompt"],
                "required_claims": case["required_claims"],
                "optional_claims": case["optional_claims"],
                "forbidden_claim_ids": (
                    [row["forbidden_claim_id"] for row in forbidden_mappings]
                    if has_review_provenance(contract)
                    else case["forbidden_claim_ids"]
                ),
                **(
                    {"requires_abstention": case["requires_abstention"]}
                    if is_expanded(contract)
                    else {}
                ),
                "answers": blind_answers,
            }
        )
        mapping_cases.append(
            {
                "case_id": case["case_id"],
                "answers": mappings,
                **(
                    {"forbidden_claims": forbidden_mappings}
                    if has_review_provenance(contract)
                    else {}
                ),
            }
        )
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
            **(
                {
                    "owner_review_required": False,
                    "fixed_model_reviews_required": True,
                    "review_receipts_required": True,
                }
                if has_review_provenance(contract)
                else {"owner_review_required": True}
            ),
            **(
                {"required_reviewer_count": contract["review"]["required_reviewer_count"]}
                if is_expanded(contract)
                else {}
            ),
            "unblinding_allowed": False,
        },
    }
    blind_bytes = write_generation_artifact(blind_output, blind_packet)
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
    mapping_bytes = write_generation_artifact(map_output, mapping_packet)
    review_template = {
        "schema": versioned_schema(contract, REVIEW_SCHEMA, REVIEW_SCHEMA_V1),
        "trial_id": spec["trial_id"],
        "blind_packet_sha256": blind_sha,
        **(
            {"reviewer_slot": ""}
            if has_review_provenance(contract)
            else {"reviewer": ""}
        ),
        **({"reviewed_at": 0} if not has_review_provenance(contract) else {}),
        **(
            {"independent_review": False, "condition_blinded": False}
            if is_expanded(contract) and not has_review_provenance(contract)
            else {}
        ),
        "cases": review_cases,
    }
    review_bytes = write_generation_artifact(
        review_template_output, review_template
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
        **(
            {
                "attempt": attempt,
                "prior_failure_receipt_sha256": prior_receipt_sha,
            }
            if is_successor(contract)
            else {}
        ),
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
            "WAIT_TWO_PROVENANCE_BOUND_MODEL_REVIEWS"
            if has_review_provenance(contract)
            else "WAIT_TWO_BLIND_REVIEWS"
            if is_expanded(contract)
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
            **(
                {
                    "answer_postprocessing_applied": False,
                    "automatic_retry": False,
                }
                if is_successor(contract)
                else {}
            ),
        },
    }
    write_generation_artifact(redacted_output, redacted)
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
            *(
                {"attempt", "prior_failure_receipt_sha256"}
                if is_successor(contract)
                else set()
            ),
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
    attempt = 1
    prior_receipt_sha: str | None = None
    if is_successor(contract):
        attempt = require_nonnegative_int(value.get("attempt"), "generation.attempt")
        if attempt not in {1, 2}:
            raise TrialError("generation attempt must be one or two")
        prior_receipt_sha = value.get("prior_failure_receipt_sha256")
        if prior_receipt_sha is not None:
            prior_receipt_sha = require_sha256(
                prior_receipt_sha, "generation.prior_failure_receipt_sha256"
            )
        if (attempt == 1) is not (prior_receipt_sha is None):
            raise TrialError("generation prior-attempt binding is invalid")
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
        **(
            {
                "answer_postprocessing_applied": False,
                "automatic_retry": False,
            }
            if is_successor(contract)
            else {}
        ),
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
                    if is_expanded(contract)
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
        if is_expanded(contract) and require_label(
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
        if is_expanded(contract) and require_bool(
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
        **(
            {
                "attempt": attempt,
                "prior_failure_receipt_sha256": prior_receipt_sha,
            }
            if is_successor(contract)
            else {}
        ),
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
        **(
            {
                "owner_review_required": False,
                "fixed_model_reviews_required": True,
                "review_receipts_required": True,
            }
            if has_review_provenance(contract)
            else {"owner_review_required": True}
        ),
        **(
            {"required_reviewer_count": contract["review"]["required_reviewer_count"]}
            if is_expanded(contract)
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
                    if is_expanded(contract)
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
        if is_expanded(contract) and require_label(
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
        forbidden_claims_valid = (
            len(forbidden_claims) == len(capture_case["forbidden_claim_ids"])
            and len(forbidden_claims) == len(set(forbidden_claims))
            and all(
                re.fullmatch(r"forbid_[0-9a-f]{24}", claim_id)
                for claim_id in forbidden_claims
            )
            if has_review_provenance(contract)
            else forbidden_claims == capture_case["forbidden_claim_ids"]
        )
        if (
            required_claims != capture_case["required_claims"]
            or optional_claims != capture_case["optional_claims"]
            or not forbidden_claims_valid
        ):
            raise TrialError("blind packet claim rubric differs from the contract/capture")
        requires_abstention = capture_case["requires_abstention"]
        if is_expanded(contract) and require_bool(
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
                "forbidden_claim_ids": forbidden_claims,
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
        reject_unknown_fields(
            case,
            {
                "case_id",
                "answers",
                *({"forbidden_claims"} if has_review_provenance(contract) else set()),
            },
            "map case",
        )
        case_id = require_label(case.get("case_id"), "map case_id")
        if case_id != blind_case["case_id"]:
            raise TrialError("blind map case id/order mismatch")
        if has_review_provenance(contract):
            capture_case = next(
                row for row in capture["cases"] if row["case_id"] == case_id
            )
            expected_forbidden = [
                {
                    "forbidden_claim_id": forbidden_claim_id(seed, case_id, claim_id),
                    "claim_id": claim_id,
                }
                for claim_id in capture_case["forbidden_claim_ids"]
            ]
            raw_forbidden = require_list(
                case.get("forbidden_claims"), "map forbidden_claims"
            )
            observed_forbidden: list[dict[str, str]] = []
            for raw_mapping in raw_forbidden:
                claim_mapping = require_object(raw_mapping, "map forbidden claim")
                reject_unknown_fields(
                    claim_mapping,
                    {"forbidden_claim_id", "claim_id"},
                    "map forbidden claim",
                )
                observed_forbidden.append(
                    {
                        "forbidden_claim_id": require_label(
                            claim_mapping.get("forbidden_claim_id"),
                            "map forbidden_claim_id",
                        ),
                        "claim_id": require_label(
                            claim_mapping.get("claim_id"), "map forbidden claim_id"
                        ),
                    }
                )
            if observed_forbidden != expected_forbidden or [
                row["forbidden_claim_id"] for row in observed_forbidden
            ] != blind_case["forbidden_claim_ids"]:
                raise TrialError("blind map forbidden-claim mapping is invalid")
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
            *({"reviewer_slot"} if has_review_provenance(contract) else {"reviewer"}),
            *({"reviewed_at"} if not has_review_provenance(contract) else set()),
            "cases",
            *(
                {"independent_review", "condition_blinded"}
                if is_expanded(contract) and not has_review_provenance(contract)
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
    if has_review_provenance(contract):
        reviewer_slot = require_label(
            value.get("reviewer_slot"), "review.reviewer_slot"
        )
        if reviewer_slot not in {
            row["reviewer_slot"] for row in contract["review_execution"]["reviewers"]
        }:
            raise TrialError("review reviewer_slot is not in the fixed roster")
        reviewer = reviewer_slot
    else:
        reviewer_slot = None
        reviewer = require_string(value.get("reviewer"), "review.reviewer", max_chars=128)
    reviewed_at = 0
    if not has_review_provenance(contract):
        reviewed_at = require_nonnegative_int(
            value.get("reviewed_at"), "review.reviewed_at"
        )
        if reviewed_at <= 0:
            raise TrialError("review.reviewed_at must be populated")
    independent_review = False
    condition_blinded = False
    if is_expanded(contract) and not has_review_provenance(contract):
        independent_review = require_bool(
            value.get("independent_review"), "review.independent_review"
        )
        condition_blinded = require_bool(
            value.get("condition_blinded"), "review.condition_blinded"
        )
        if not independent_review or not condition_blinded:
            raise TrialError(
                "expanded review independence/blinding attestations must be true"
            )
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
                        if is_expanded(contract)
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
            if is_expanded(contract) and blind_case["requires_abstention"]:
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
        **({"reviewer_slot": reviewer_slot} if reviewer_slot is not None else {}),
        **({"reviewed_at": reviewed_at} if not has_review_provenance(contract) else {}),
        "independent_review": independent_review,
        "condition_blinded": condition_blinded,
        "cases": cases,
    }


def build_v3_review_request(
    contract: dict[str, Any], blind_bytes: bytes, reviewer_slot: str
) -> bytes:
    if not has_review_provenance(contract):
        raise TrialError("review requests require a v3 provenance contract")
    try:
        blind_text = blind_bytes.decode("utf-8")
        blind_packet = json.loads(
            blind_text,
            parse_constant=surface.reject_json_constant,
            object_pairs_hook=surface.reject_duplicate_json_keys,
        )
    except UnicodeDecodeError as exc:
        raise TrialError("blind packet is not UTF-8") from exc
    except json.JSONDecodeError as exc:
        raise TrialError("blind packet JSON is malformed") from exc
    blind_packet = require_object(blind_packet, "review request blind packet")
    review_cases: list[dict[str, Any]] = []
    for raw_case in require_list(
        blind_packet.get("cases"), "review request blind cases"
    ):
        case = require_object(raw_case, "review request blind case")
        required_claims = validate_claims(
            case.get("required_claims"),
            "review request required claims",
            allow_empty=require_bool(
                case.get("requires_abstention"),
                "review request requires_abstention",
            ),
        )
        answers = [
            {
                "answer_id": require_string(
                    require_object(raw_answer, "review request answer").get("answer_id"),
                    "review request answer_id",
                    max_chars=32,
                ),
                "claim_scores": [
                    {"claim_id": claim["claim_id"], "score": None}
                    for claim in required_claims
                ],
                "currentness": None,
                "unsupported_assertion_count": None,
                "usefulness": None,
                "notes": "",
                **(
                    {"abstention_pass": None}
                    if case["requires_abstention"]
                    else {}
                ),
            }
            for raw_answer in require_list(
                case.get("answers"), "review request answers"
            )
        ]
        review_cases.append(
            {
                "case_id": require_label(
                    case.get("case_id"), "review request case_id"
                ),
                "answers": answers,
                "preferred_answer_id": None,
            }
        )
    review_template = {
        "schema": versioned_schema(contract, REVIEW_SCHEMA, REVIEW_SCHEMA_V1),
        "trial_id": require_label(
            blind_packet.get("trial_id"), "review request trial_id"
        ),
        "blind_packet_sha256": sha256_bytes(blind_bytes),
        "reviewer_slot": reviewer_slot,
        "cases": review_cases,
    }
    review_template_text = surface.render_json(review_template).decode("utf-8")
    request = (
        contract["review_execution"]["review_instruction"].rstrip()
        + "\n\n=== REVIEWER SLOT ===\n"
        + reviewer_slot
        + "\n\n=== BLIND PACKET JSON ===\n"
        + blind_text.rstrip("\n")
        + "\n=== END BLIND PACKET JSON ===\n"
        + "\n=== REVIEW OUTPUT TEMPLATE JSON ===\n"
        + review_template_text.rstrip("\n")
        + "\n=== END REVIEW OUTPUT TEMPLATE JSON ===\n"
    )
    return request.encode("utf-8")


def validate_v3_review_receipt(
    value: dict[str, Any],
    raw_bytes: bytes,
    command_bytes: bytes,
    raw_response_bytes: bytes,
    review_bytes: bytes,
    review: dict[str, Any],
    blind: dict[str, Any],
    blind_bytes: bytes,
    contract: dict[str, Any],
    contract_sha: str,
) -> dict[str, Any]:
    if not has_review_provenance(contract):
        raise TrialError("review provenance receipts require a v3 contract")
    if value.get("schema") != REVIEW_RECEIPT_SCHEMA_V3:
        raise TrialError(f"review receipt schema must be {REVIEW_RECEIPT_SCHEMA_V3}")
    reject_unknown_fields(
        value,
        {
            "schema",
            "trial_id",
            "contract_sha256",
            "blind_packet_sha256",
            "reviewer_slot",
            "provider",
            "model",
            "reasoning_effort",
            "cli",
            "cli_version",
            "command_profile",
            "command_sha256",
            "request_sha256",
            "raw_response_sha256",
            "review_sha256",
            "session_id_sha256",
            "usage_sha256",
            "invocation_index",
            "retry_count",
            "started_at",
            "completed_at",
            "exit_code",
            "workspace_file_count",
            "workspace_tree_sha256",
            "model_pinned_in_command",
            "reasoning_effort_pinned_in_command",
            "custodian_generated",
            "project_context_loaded",
            "mcp_server_count",
            "tool_events_observed",
            "conflicts_of_interest",
            "boundary",
        },
        "review receipt",
    )
    if require_label(value.get("trial_id"), "review receipt.trial_id") != blind[
        "trial_id"
    ]:
        raise TrialError("review receipt trial id mismatch")
    if require_sha256(
        value.get("contract_sha256"), "review receipt.contract_sha256"
    ) != contract_sha:
        raise TrialError("review receipt contract hash mismatch")
    if require_sha256(
        value.get("blind_packet_sha256"), "review receipt.blind_packet_sha256"
    ) != blind["blind_packet_sha256"]:
        raise TrialError("review receipt blind packet hash mismatch")
    reviewer_slot = require_label(
        value.get("reviewer_slot"), "review receipt.reviewer_slot"
    )
    roster = {
        row["reviewer_slot"]: row for row in contract["review_execution"]["reviewers"]
    }
    if reviewer_slot not in roster or reviewer_slot != review["reviewer_slot"]:
        raise TrialError("review receipt slot does not bind the review packet")
    expected_reviewer = roster[reviewer_slot]
    for key in {
        "provider",
        "model",
        "reasoning_effort",
        "cli",
        "cli_version",
        "command_profile",
    }:
        actual = require_string(value.get(key), f"review receipt.{key}", max_chars=128)
        if actual != expected_reviewer[key]:
            raise TrialError(f"review receipt {key} does not match the frozen roster")
    if require_sha256(
        value.get("command_sha256"), "review receipt.command_sha256"
    ) != sha256_bytes(command_bytes):
        raise TrialError("review receipt command hash mismatch")
    for key in {"session_id_sha256", "usage_sha256"}:
        require_sha256(value.get(key), f"review receipt.{key}")
    expected_request_sha = sha256_bytes(
        build_v3_review_request(contract, blind_bytes, reviewer_slot)
    )
    if require_sha256(
        value.get("request_sha256"), "review receipt.request_sha256"
    ) != expected_request_sha:
        raise TrialError("review receipt request hash mismatch")
    if require_sha256(
        value.get("raw_response_sha256"), "review receipt.raw_response_sha256"
    ) != sha256_bytes(raw_response_bytes):
        raise TrialError("review receipt raw response hash mismatch")
    if require_sha256(
        value.get("review_sha256"), "review receipt.review_sha256"
    ) != sha256_bytes(review_bytes):
        raise TrialError("review receipt review hash mismatch")
    if raw_response_bytes != review_bytes:
        raise TrialError("review packet is not byte-identical to the model response")
    if require_nonnegative_int(
        value.get("invocation_index"), "review receipt.invocation_index"
    ) != 1:
        raise TrialError("review receipt must describe the single invocation")
    if require_nonnegative_int(
        value.get("retry_count"), "review receipt.retry_count"
    ) != 0:
        raise TrialError("v3 review retries are forbidden")
    started_at = require_nonnegative_int(
        value.get("started_at"), "review receipt.started_at"
    )
    completed_at = require_nonnegative_int(
        value.get("completed_at"), "review receipt.completed_at"
    )
    if started_at <= 0 or completed_at < started_at:
        raise TrialError("review receipt timestamps are invalid")
    if require_nonnegative_int(value.get("exit_code"), "review receipt.exit_code") != 0:
        raise TrialError("review model invocation did not exit successfully")
    if require_nonnegative_int(
        value.get("workspace_file_count"), "review receipt.workspace_file_count"
    ) != 0 or require_sha256(
        value.get("workspace_tree_sha256"), "review receipt.workspace_tree_sha256"
    ) != EMPTY_WORKSPACE_SHA256:
        raise TrialError("review receipt does not prove the fixed empty-workspace state")
    expected_effort_pinned = expected_reviewer["reasoning_effort"] != "cli_default"
    fixed_booleans = {
        "model_pinned_in_command": True,
        "reasoning_effort_pinned_in_command": expected_effort_pinned,
        "custodian_generated": True,
        "project_context_loaded": False,
        "tool_events_observed": False,
    }
    for key, expected in fixed_booleans.items():
        if require_bool(value.get(key), f"review receipt.{key}") is not expected:
            raise TrialError(f"review receipt {key} violates the frozen execution policy")
    if require_nonnegative_int(
        value.get("mcp_server_count"), "review receipt.mcp_server_count"
    ) != 0:
        raise TrialError("review receipt reports an MCP server")
    expected_coi = {
        "scheduler_authored_some_evaluated_material": True,
        "provider_overlap_with_generator": expected_reviewer[
            "provider_overlap_with_generator"
        ],
        "model_overlap_with_generator": expected_reviewer[
            "model_overlap_with_generator"
        ],
    }
    coi = require_object(value.get("conflicts_of_interest"), "review receipt COI")
    reject_unknown_fields(coi, set(expected_coi), "review receipt COI")
    if coi != expected_coi:
        raise TrialError("review receipt COI disclosure drifted")
    expected_boundary = {
        "private": True,
        "raw_response_private": True,
        "blind_packet_only": True,
        "condition_labels_present": False,
        "self_attestation_used_for_provenance": False,
    }
    boundary = require_object(value.get("boundary"), "review receipt.boundary")
    reject_unknown_fields(boundary, set(expected_boundary), "review receipt.boundary")
    if boundary != expected_boundary:
        raise TrialError("review receipt boundary is incomplete")
    return {
        "reviewer_slot": reviewer_slot,
        "provider": expected_reviewer["provider"],
        "model": expected_reviewer["model"],
        "provider_overlap_with_generator": expected_reviewer[
            "provider_overlap_with_generator"
        ],
        "review_receipt_sha256": sha256_bytes(raw_bytes),
        "raw_response_sha256": sha256_bytes(raw_response_bytes),
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


def summarize_v3_review_agreement(
    review_records: list[dict[str, Any]],
) -> dict[str, Any]:
    if len(review_records) != 2:
        raise TrialError("v3 agreement requires exactly two review records")
    left = review_records[0]["review"]
    right = review_records[1]["review"]
    counts = {
        "claim_score": [0, 0],
        "currentness": [0, 0],
        "unsupported_assertion_count": [0, 0],
        "usefulness": [0, 0],
        "abstention": [0, 0],
        "preference": [0, 0],
    }
    for case_id, left_case in left["cases"].items():
        right_case = right["cases"][case_id]
        counts["preference"][1] += 1
        counts["preference"][0] += left_case["preference"] == right_case["preference"]
        for answer_id, left_answer in left_case["answers"].items():
            right_answer = right_case["answers"][answer_id]
            for claim_id, left_score in left_answer["claim_scores"].items():
                counts["claim_score"][1] += 1
                counts["claim_score"][0] += (
                    left_score == right_answer["claim_scores"][claim_id]
                )
            for key in {
                "currentness",
                "unsupported_assertion_count",
                "usefulness",
            }:
                counts[key][1] += 1
                counts[key][0] += left_answer[key] == right_answer[key]
            if left_answer["abstention_pass"] is not None:
                counts["abstention"][1] += 1
                counts["abstention"][0] += (
                    left_answer["abstention_pass"]
                    == right_answer["abstention_pass"]
                )
    return {
        "reviewer_slots": [row["reviewer_slot"] for row in review_records],
        "provider_families": [row["provider"] for row in review_records],
        "metrics": {
            key: {
                "agreement_count": values[0],
                "comparison_count": values[1],
                "agreement_rate": (
                    round(values[0] / values[1], 6) if values[1] else None
                ),
            }
            for key, values in counts.items()
        },
        "used_for_gate": False,
        "pooled_mean_used": False,
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
    score_claim_sha256: str | None = None,
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
            **(
                {
                    "reviewer_slot": review_record["reviewer_slot"],
                    "provider": review_record["provider"],
                    "model": review_record["model"],
                    "provider_overlap_with_generator": review_record[
                        "provider_overlap_with_generator"
                    ],
                    "review_receipt_sha256": review_record[
                        "review_receipt_sha256"
                    ],
                    "raw_response_sha256": review_record["raw_response_sha256"],
                }
                if has_review_provenance(contract)
                else {}
            ),
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
        "schema": versioned_schema(contract, SCORE_SCHEMA, SCORE_SCHEMA_V1),
        "trial_id": capture["trial_id"],
        "contract_sha256": contract_sha,
        "contract_commit": capture["contract_commit"],
        "capture_sha256": capture["capture_sha256"],
        "generation_sha256": generation["generation_sha256"],
        "blind_packet_sha256": blind["blind_packet_sha256"],
        "blind_map_sha256": surface.sha256_file(map_path),
        "harness_source_sha256": contract["harness_source_sha256"],
        **(
            {"score_claim_sha256": score_claim_sha256}
            if has_review_provenance(contract)
            else {}
        ),
        "per_reviewer": per_reviewer,
        "per_stratum": per_stratum,
        **(
            {"cross_reviewer_agreement": summarize_v3_review_agreement(review_records)}
            if has_review_provenance(contract)
            else {}
        ),
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
            "reviewer_identity_in_output": has_review_provenance(contract),
            **(
                {"private_reviewer_identifier_in_output": False}
                if has_review_provenance(contract)
                else {}
            ),
            "review_notes_in_output": False,
            "pooled_reviewer_mean_used_for_gate": False,
            "llm_judge": has_review_provenance(contract),
            **(
                {
                    "review_provenance_required": True,
                    "review_self_attestation_used": False,
                    "cross_reviewer_provider_independence": True,
                    "generator_provider_overlap_disclosed": True,
                    "score_single_use_claimed": True,
                }
                if has_review_provenance(contract)
                else {}
            ),
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


def claim_v3_score_attempt(
    claim_path: Path,
    repo: Path,
    contract: dict[str, Any],
    contract_sha: str,
    blind: dict[str, Any],
    review_records: list[dict[str, Any]],
) -> str:
    if not has_review_provenance(contract):
        raise TrialError("score claims require a v3 contract")
    if sha256_text(str(repo)) != contract["execution_repo_path_sha256"]:
        raise TrialError("score execution worktree does not match the commitment")
    require_ignored_data_path(repo, claim_path, "score attempt claim")
    claim_dir = claim_path.parent
    try:
        claim_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
        if claim_dir.stat().st_mode & 0o077:
            raise TrialError("private score claim directory permissions are too broad")
    except OSError as exc:
        raise TrialError("failed to prepare the private score claim directory") from exc
    packet = {
        "schema": SCORE_CLAIM_SCHEMA_V3,
        "contract_sha256": contract_sha,
        "blind_packet_sha256": blind["blind_packet_sha256"],
        "reviews": [
            {
                "reviewer_slot": row["review"]["reviewer_slot"],
                "review_sha256": row["review_sha256"],
                "review_receipt_sha256": row["review_receipt_sha256"],
                "raw_response_sha256": row["raw_response_sha256"],
            }
            for row in review_records
        ],
        "claimed_at": int(time.time()),
        "boundary": {
            "private": True,
            "single_use": True,
            "unblinding_not_yet_started": True,
            "retry_allowed": False,
        },
    }
    rendered = surface.render_json(packet)
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_CLOEXEC", 0)
    flags |= getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(claim_path, flags, 0o600)
        try:
            with os.fdopen(descriptor, "wb") as handle:
                handle.write(rendered)
                handle.flush()
                os.fsync(handle.fileno())
        except BaseException:
            raise
        directory_descriptor = os.open(
            claim_dir,
            os.O_RDONLY
            | getattr(os, "O_DIRECTORY", 0)
            | getattr(os, "O_CLOEXEC", 0),
        )
        try:
            os.fsync(directory_descriptor)
        finally:
            os.close(directory_descriptor)
    except FileExistsError as exc:
        raise TrialError("score attempt was already claimed") from exc
    except OSError as exc:
        raise TrialError("failed to atomically claim the score attempt") from exc
    return sha256_bytes(rendered)


def _score_trial_core(
    contract_path: Path,
    capture_path: Path,
    generation_path: Path,
    blind_path: Path,
    map_path: Path,
    review_paths: list[Path],
    output_path: Path,
    review_receipt_paths: list[Path] | None = None,
    review_command_paths: list[Path] | None = None,
    review_response_paths: list[Path] | None = None,
    score_claim_path: Path | None = None,
) -> dict[str, Any]:
    review_receipt_paths = review_receipt_paths or []
    review_command_paths = review_command_paths or []
    review_response_paths = review_response_paths or []
    protected_inputs = (
        contract_path,
        capture_path,
        generation_path,
        blind_path,
        map_path,
        *review_paths,
        *review_receipt_paths,
        *review_command_paths,
        *review_response_paths,
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
            **{
                f"review_receipt_{index}": path
                for index, path in enumerate(review_receipt_paths, start=1)
            },
            **{
                f"review_command_{index}": path
                for index, path in enumerate(review_command_paths, start=1)
            },
            **{
                f"review_response_{index}": path
                for index, path in enumerate(review_response_paths, start=1)
            },
            **({"score_claim": score_claim_path} if score_claim_path else {}),
            "harness_source": Path(__file__),
            "surface_source": Path(surface.__file__),
            "output": output_path,
        }
    )
    contract, contract_sha = load_contract(contract_path)
    if has_review_provenance(contract):
        if (
            len(review_receipt_paths) != 2
            or len(review_command_paths) != 2
            or len(review_response_paths) != 2
            or score_claim_path is None
        ):
            raise TrialError(
                "v3 score requires two receipts, commands, raw responses, and a score claim"
            )
        if output_path.exists() or output_path.is_symlink():
            raise TrialError("v3 score requires a fresh output path")
    elif (
        review_receipt_paths
        or review_command_paths
        or review_response_paths
        or score_claim_path is not None
    ):
        raise TrialError("review provenance inputs are supported only by v3 score")
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
    expected_review_count = 2 if is_expanded(contract) else 1
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
    review_records = [
            {
                "review": review,
                "review_sha256": sha256_bytes(review_bytes),
                "reviewer_sha256": sha256_text(review["reviewer"]),
            }
            for review, review_bytes in zip(reviews, review_packets, strict=True)
    ]
    score_claim_sha: str | None = None
    if has_review_provenance(contract):
        expected_slots = [
            row["reviewer_slot"] for row in contract["review_execution"]["reviewers"]
        ]
        if [review["reviewer_slot"] for review in reviews] != expected_slots:
            raise TrialError("v3 reviews must follow the fixed reviewer-slot order")
        for record, receipt_path, command_path, response_path, review_bytes in zip(
            review_records,
            review_receipt_paths,
            review_command_paths,
            review_response_paths,
            review_packets,
            strict=True,
        ):
            receipt_raw, receipt_bytes = read_json(receipt_path)
            try:
                command_bytes = command_path.read_bytes()
                response_bytes = response_path.read_bytes()
            except OSError as exc:
                raise TrialError("failed to read a private review response") from exc
            if (
                receipt_path.stat().st_mode & 0o077
                or command_path.stat().st_mode & 0o077
                or response_path.stat().st_mode & 0o077
            ):
                raise TrialError("review provenance files have overly broad permissions")
            provenance = validate_v3_review_receipt(
                receipt_raw,
                receipt_bytes,
                command_bytes,
                response_bytes,
                review_bytes,
                record["review"],
                blind,
                blind_bytes,
                contract,
                contract_sha,
            )
            record.update(provenance)
        repo = git_root(contract_path.parent)
        score_claim_sha = claim_v3_score_attempt(
            score_claim_path,
            repo,
            contract,
            contract_sha,
            blind,
            review_records,
        )
        protected_inputs += (score_claim_path,)
    else:
        review_records.sort(key=lambda row: row["reviewer_sha256"])

    # The generation packet and blind map both reveal condition-to-answer
    # identity. Do not open either until every review provenance gate is complete.
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
    if is_expanded(contract):
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
            score_claim_sha,
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
    review_receipt_paths: list[Path] | None = None,
    review_command_paths: list[Path] | None = None,
    review_response_paths: list[Path] | None = None,
    score_claim_path: Path | None = None,
) -> dict[str, Any]:
    return _score_trial_core(
        contract_path,
        capture_path,
        generation_path,
        blind_path,
        map_path,
        review_paths,
        output_path,
        review_receipt_paths,
        review_command_paths,
        review_response_paths,
        score_claim_path,
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
    generate.add_argument("--failure-output")
    generate.add_argument("--prior-failure-receipt")
    generate.add_argument("--timeout-secs", type=float, default=600.0)

    score = subparsers.add_parser("score")
    score.add_argument("--contract", required=True)
    score.add_argument("--capture", required=True)
    score.add_argument("--generation", required=True)
    score.add_argument("--blind-packet", required=True)
    score.add_argument("--blind-map", required=True)
    score.add_argument("--review", required=True, action="append")
    score.add_argument("--review-receipt", action="append")
    score.add_argument("--review-command", action="append")
    score.add_argument("--review-response", action="append")
    score.add_argument("--score-claim")
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
                Path(args.failure_output) if args.failure_output else None,
                (
                    Path(args.prior_failure_receipt)
                    if args.prior_failure_receipt
                    else None
                ),
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
                (
                    [Path(path) for path in args.review_receipt]
                    if args.review_receipt
                    else None
                ),
                (
                    [Path(path) for path in args.review_command]
                    if args.review_command
                    else None
                ),
                (
                    [Path(path) for path in args.review_response]
                    if args.review_response
                    else None
                ),
                Path(args.score_claim) if args.score_claim else None,
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
