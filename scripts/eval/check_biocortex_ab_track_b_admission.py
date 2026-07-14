#!/usr/bin/env python3
"""Validate the fail-closed BioCortex/AB Track B real-run admission v0 packet.

This checker reads public, committed inputs only.  It does not open the live
Agent-Bridge database, a sampling frame, prompts, answers, reviews, a blind
map, or any condition-labelled result, and it never launches Agent-Bridge.
"""

from __future__ import annotations

import argparse
import copy
from fractions import Fraction
import hashlib
import hmac
import json
import math
import re
import sys
from pathlib import Path
from typing import Any, Callable


CONTRACT_PATH = Path(
    "scripts/eval/fixtures/biocortex_ab_track_b_real_run_admission_v0.json"
)
SYNTHETIC_PATH = Path(
    "scripts/eval/fixtures/biocortex_ab_track_b_admission_synthetic_v0.json"
)
SCHEMA = "agent_bridge.biocortex_ab_track_b_real_run_admission.v0"
SYNTHETIC_SCHEMA = "agent_bridge.biocortex_ab_track_b_admission_synthetic.v0"
PARENT_COMMIT = "533ab2607825d877278edd6548e897f93c2acf19"
UNSET = "UNSET_BLOCKS_REAL_RUN"
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")

EXPECTED_TOP_LEVEL_KEYS = {
    "admission",
    "authority",
    "blockers",
    "candidate_condition",
    "context_and_result",
    "contract_id",
    "data_quality",
    "date",
    "earliest_post_fix_capture_date",
    "generation",
    "latency",
    "legacy_precedent",
    "parent_commit",
    "power_and_estimator",
    "public_fixture",
    "reference_condition",
    "review_and_blinding",
    "sampling",
    "schema",
    "source_bindings",
    "stages",
    "storage",
    "strict_case_pass",
    "truth_inputs",
}

EXPECTED_BLOCKERS = [
    "REFERENCE_FROZEN_CLOCK_UNAVAILABLE",
    "REFERENCE_CLEAN_ENV_HARNESS_UNIMPLEMENTED",
    "REFERENCE_DETERMINISTIC_TIE_BREAK_UNPROVED",
    "REFERENCE_HARD_CONTEXT_BUDGET_UNSET",
    "REFERENCE_RUNTIME_BINARY_AND_SNAPSHOT_UNSET",
    "CANDIDATE_STORE_ADAPTER_BLOCKED_DATA_MODEL",
    "PREVALENCE_FRAME_SAMPLING_AND_POWER_UNSET",
    "TRUTH_AS_OF_AND_AUTHORITY_MANIFEST_UNSET",
    "FRESH_REVIEWER_AND_BLIND_MAP_BINDINGS_UNSET",
    "LATENCY_HARDWARE_TOKENIZER_AND_ORDER_UNSET",
    "CANONICAL_SOURCE_AND_STORAGE_MANIFEST_UNSET",
    "POST_FIX_CAPTURE_DATE_NOT_REACHED_IN_THIS_PREREG",
]

EXPECTED_ADAPTER_GAPS = [
    "all_relationship_channels_and_history_unavailable",
    "complete_lineage_revision_history_unavailable",
    "complete_tombstone_governance_index_unavailable",
    "durable_governance_attestation_unavailable",
    "explicit_temporal_claim_provenance_bindings_unavailable",
    "predicate_scoped_authority_policy_unavailable",
    "relationship_endpoint_closure_unprovable",
    "unique_lineage_revision_order_unavailable",
]

EXPECTED_SOURCE_BINDINGS = {
    "Cargo.lock": (
        "rust_dependency_lock",
        "5ebad772d0d0d48d1414bf02939feeb56ad0aa3e15aa7ee0db6fb4cb46e6c613",
        "BOUND_CODE_ONLY",
    ),
    "crates/bridge/src/mcp_tools.rs": (
        "reference_search_implementation",
        "9a0f486b9bdf101d264f386efd0eb08c64299bba2c627c61e1ece19f5f79b448",
        "BOUND_CODE_ONLY",
    ),
    "crates/bridge/src/memory_truth.rs": (
        "candidate_pure_truth_resolver",
        "2e46a521332820b07171b425c95004f35a98887c7c49a2d78baf7740f07195a4",
        "BOUND_RESOLVER_ONLY",
    ),
    "crates/bridge/src/memory_truth_adapter.rs": (
        "candidate_adapter_preflight",
        "c459e96919778c24b0bc699653d8c12b83332e6318b7298deee071a01e90e023",
        "BOUND_BLOCKER_EVIDENCE",
    ),
    "crates/store/src/lib.rs": (
        "reference_store_contract",
        "8b38d1471ba7abc0f47092ee1a7af67504f80b539f0a3787c4982aaf229f3398",
        "BOUND_CODE_ONLY",
    ),
    "crates/store/src/sqlite.rs": (
        "reference_sqlite_implementation",
        "cba4f527f4e32b7241f84829c95b47ad179e05ce9a5e7b72e55a54f20b0dc3b4",
        "BOUND_CODE_ONLY",
    ),
    "docs/design/MEMORY_PEEK_TRUTH_ADAPTER_PREFLIGHT_V0_2026_07_10.md": (
        "candidate_adapter_design_contract",
        "c457e574fa40c711f70ba3085f114044eae37686911fedfe77a2efa718bf7aaa",
        "BOUND_BLOCKER_EVIDENCE",
    ),
    "docs/design/TEMPORAL_TRUTH_PROJECTION_V0_2026_07_10.md": (
        "candidate_resolver_design_contract",
        "5d8c4a31fe595606f5033c950b38ba969e3b9642a8e28a067fc5f4165e435481",
        "BOUND_RESOLVER_ONLY",
    ),
    "scripts/eval/fixtures/portfolio_continuity_successor_v3_answer_contract.json": (
        "consumed_legacy_contract",
        "da9e190492d74824159bbff18eaeff02a4848921989f4077072f126e1d4e4bcc",
        "MECHANISM_ONLY_CONSUMED",
    ),
    "scripts/eval/portfolio_continuity_ab_trial.py": (
        "legacy_shared_trial_surface",
        "b6f599e748088e36424bd03e70a5bc3112aeaf728f6679b19297889a98e5b7f3",
        "MECHANISM_ONLY_CONSUMED",
    ),
    "scripts/eval/portfolio_continuity_successor_v3_trial.py": (
        "legacy_successor_v3_harness",
        "0b92b1153a77257a49fc847eb37be3e20d687c41067559c22b2ebed72649e003",
        "MECHANISM_ONLY_CONSUMED",
    ),
}

EXPECTED_REQUEST = {
    "compact": False,
    "exclude_kinds": ["skill"],
    "expand_top": 10,
    "include_global": False,
    "limit": 10,
    "mode": "hybrid",
    "rrf_k": 60.0,
    "scope": None,
    "scope_mode": "local_only",
    "tags_any": [],
    "tool": "memory_search",
}

EXPECTED_ENVIRONMENT = {
    "AB_BOOTSTRAP_SURFACING_DISABLE": "1",
    "AGENT_BRIDGE_COACTIVATION_RERANK_DISABLE": "0",
    "AGENT_BRIDGE_CORRECTION_COSURFACE": "0",
    "AGENT_BRIDGE_MEMORY_CLASS_QUOTA": "UNSET",
    "AGENT_BRIDGE_MEMORY_SEARCH_EXCLUDE_KINDS": "UNSET",
    "AGENT_BRIDGE_OUTCOME_COLLECTOR": "0",
    "AGENT_BRIDGE_RECALL_SEMANTIC_FALLBACK": "0",
    "AGENT_BRIDGE_RETRIEVAL_TRAFFIC_CLASS": "eval",
    "AGENT_BRIDGE_SEED_BOOST_DISABLE": "1",
    "LC_ALL": "C",
    "TZ": "UTC",
}


class AdmissionError(ValueError):
    pass


def fail(message: str) -> None:
    raise AdmissionError(message)


def duplicate_rejector(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            fail("duplicate JSON key")
        result[key] = value
    return result


def read_strict_json(path: Path, label: str) -> tuple[dict[str, Any], bytes]:
    try:
        raw = path.read_bytes()
    except OSError as exc:
        fail(f"cannot read {label}: {exc}")
    try:
        value = json.loads(
            raw.decode("utf-8"),
            parse_constant=lambda _: fail("non-finite JSON number"),
            object_pairs_hook=duplicate_rejector,
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        fail(f"invalid strict JSON: {exc}")
    if not isinstance(value, dict):
        fail("contract root must be an object")
    try:
        canonical = (
            json.dumps(
                value,
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
                allow_nan=False,
            )
            + "\n"
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        fail(f"{label} cannot be rendered canonically: {exc}")
    if raw != canonical:
        fail(f"{label} must use canonical sorted pretty JSON with one final newline")
    return value, raw


def require_object(value: Any, path: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        fail(f"{path} must be an object")
    return value


def require_exact_keys(value: dict[str, Any], expected: set[str], path: str) -> None:
    if set(value) != expected:
        fail(f"{path} field set drift")


def require_exact(value: Any, expected: Any, path: str) -> None:
    if not strict_equal(value, expected):
        fail(f"{path} drift")


def strict_equal(value: Any, expected: Any) -> bool:
    if type(value) is not type(expected):
        return False
    if isinstance(expected, dict):
        return set(value) == set(expected) and all(
            strict_equal(value[key], expected[key]) for key in expected
        )
    if isinstance(expected, list):
        return len(value) == len(expected) and all(
            strict_equal(left, right) for left, right in zip(value, expected)
        )
    if isinstance(expected, float):
        return math.isfinite(value) and value == expected
    return value == expected


def require_false(value: Any, path: str) -> None:
    if value is not False:
        fail(f"{path} must remain false")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
    except OSError as exc:
        fail(f"cannot hash source binding: {exc}")
    return digest.hexdigest()


def walk(value: Any):
    if isinstance(value, dict):
        for key, child in value.items():
            yield key, child
            yield from walk(child)
    elif isinstance(value, list):
        for child in value:
            yield from walk(child)


def validate_sha_fields(contract: dict[str, Any]) -> None:
    for key, value in walk(contract):
        if isinstance(value, float) and not math.isfinite(value):
            fail(f"{key} must be finite")
        if not key.endswith("sha256"):
            continue
        if not isinstance(value, str):
            fail(f"{key} must be a string")
        if value != UNSET and not SHA256_RE.fullmatch(value):
            fail(f"{key} must be a lowercase SHA-256 or fail-closed placeholder")


def validate_sources(contract: dict[str, Any], root: Path | None) -> None:
    rows = contract.get("source_bindings")
    if not isinstance(rows, list) or len(rows) != len(EXPECTED_SOURCE_BINDINGS):
        fail("source binding count drift")
    observed: dict[str, tuple[str, str, str]] = {}
    ordered_paths: list[str] = []
    for index, row_value in enumerate(rows):
        row = require_object(row_value, f"source_bindings[{index}]")
        require_exact_keys(row, {"path", "role", "sha256", "status"}, f"source_bindings[{index}]")
        path = row.get("path")
        if not isinstance(path, str) or not path or path.startswith("/") or ".." in Path(path).parts:
            fail("source binding path must be canonical and relative")
        if path in observed:
            fail("duplicate source binding path")
        ordered_paths.append(path)
        observed[path] = (row.get("role"), row.get("sha256"), row.get("status"))
    require_exact(ordered_paths, sorted(ordered_paths), "source binding order")
    require_exact(observed, EXPECTED_SOURCE_BINDINGS, "source_bindings")
    if root is None:
        return
    for relative, (_, expected_sha, _) in EXPECTED_SOURCE_BINDINGS.items():
        source = root / relative
        if not source.is_file() or source.is_symlink():
            fail("bound source is missing or not a regular non-symlink file")
        require_exact(sha256_file(source), expected_sha, f"source hash {relative}")


def validate_contract(contract: dict[str, Any], root: Path | None = None) -> None:
    require_exact_keys(contract, EXPECTED_TOP_LEVEL_KEYS, "contract")
    require_exact(contract.get("schema"), SCHEMA, "schema")
    require_exact(
        contract.get("contract_id"),
        "biocortex_ab_track_b_real_run_admission_20260713",
        "contract_id",
    )
    require_exact(contract.get("parent_commit"), PARENT_COMMIT, "parent_commit")
    require_exact(contract.get("date"), "2026-07-13", "date")
    require_exact(
        contract.get("earliest_post_fix_capture_date"),
        "2026-07-17",
        "earliest_post_fix_capture_date",
    )
    validate_sha_fields(contract)

    admission = require_object(contract.get("admission"), "admission")
    require_exact_keys(
        admission,
        {"capture_allowed", "current_stage", "real_run_admitted", "status", "unblock_rule"},
        "admission",
    )
    require_exact(admission.get("status"), "BLOCKED_FAIL_CLOSED", "admission.status")
    require_false(admission.get("capture_allowed"), "admission.capture_allowed")
    require_false(admission.get("real_run_admitted"), "admission.real_run_admitted")
    require_exact(admission.get("current_stage"), "PRE_OUTPUT_ADMISSION", "admission.current_stage")
    require_exact(
        admission.get("unblock_rule"),
        "EACH_STAGE_REQUIRES_ITS_DECLARED_BINDINGS_BEFORE_ITS_SIDE_EFFECT",
        "admission.unblock_rule",
    )

    authority = require_object(contract.get("authority"), "authority")
    expected_authority_keys = {
        "agent_bridge_db_write",
        "agent_bridge_retrieval_execution",
        "biocortex_runtime_influence",
        "capture",
        "deployment",
        "generation",
        "production_promotion",
        "real_review",
        "scientific_claim",
        "scoring",
        "unblinding",
    }
    require_exact_keys(authority, expected_authority_keys, "authority")
    for key, value in authority.items():
        require_false(value, f"authority.{key}")

    require_exact(contract.get("blockers"), EXPECTED_BLOCKERS, "blockers")

    candidate = require_object(contract.get("candidate_condition"), "candidate_condition")
    require_exact_keys(
        candidate,
        {"adapter", "candidate_context_builder_sha256", "candidate_id", "resolver_status"},
        "candidate_condition",
    )
    adapter = require_object(candidate.get("adapter"), "candidate_condition.adapter")
    require_exact_keys(
        adapter,
        {
            "adapter_allowed",
            "current_profile",
            "live_snapshot_preflight_run",
            "minimum_static_gaps",
            "observation_scope",
            "status",
        },
        "candidate_condition.adapter",
    )
    require_exact(adapter.get("status"), "BLOCKED_DATA_MODEL", "candidate adapter status")
    require_false(adapter.get("adapter_allowed"), "candidate adapter_allowed")
    require_false(adapter.get("live_snapshot_preflight_run"), "candidate live preflight")
    require_exact(adapter.get("current_profile"), "mutable_sqlite_v41", "candidate profile")
    require_exact(
        adapter.get("observation_scope"),
        "STATIC_PRODUCER_PROFILE_FACTS_ONLY",
        "candidate observation scope",
    )
    require_exact(adapter.get("minimum_static_gaps"), EXPECTED_ADAPTER_GAPS, "candidate gaps")
    require_exact(
        candidate.get("candidate_context_builder_sha256"),
        UNSET,
        "candidate context builder",
    )
    require_exact(
        candidate.get("resolver_status"),
        "PURE_RESOLVER_SOURCE_BOUND_ADAPTER_NOT_ADMITTED",
        "candidate resolver status",
    )
    require_exact(
        candidate.get("candidate_id"),
        "temporal_truth_projection_v0_with_future_reviewed_store_adapter",
        "candidate id",
    )

    context = require_object(contract.get("context_and_result"), "context_and_result")
    require_exact_keys(
        context,
        {
            "candidate_may_exceed_reference_case_bytes",
            "candidate_may_exceed_reference_case_tokens",
            "context_builder_sha256",
            "context_token_ratio_max",
            "exact_tokenizer_code_sha256",
            "exact_tokenizer_id",
            "exact_tokenizer_model_sha256",
            "legacy_builder_admissible",
            "legacy_builder_dropped_fields",
            "legacy_builder_retains_volatile_fields",
            "max_context_bytes_per_case",
            "max_context_tokens_per_case",
            "result_bytes_definition",
            "status",
        },
        "context_and_result",
    )
    require_exact(context.get("status"), "BLOCKED_BINDINGS_UNSET", "context status")
    require_false(context.get("legacy_builder_admissible"), "legacy builder admissible")
    require_false(
        context.get("candidate_may_exceed_reference_case_bytes"),
        "candidate case byte overrun",
    )
    require_false(
        context.get("candidate_may_exceed_reference_case_tokens"),
        "candidate case token overrun",
    )
    require_exact(context.get("context_token_ratio_max"), 1.0, "context token ratio")
    require_exact(
        context.get("result_bytes_definition"),
        "EXACT_UTF8_BYTES_OF_FINAL_FROZEN_CONTEXT_SENT_TO_GENERATOR",
        "result bytes definition",
    )
    require_exact(context.get("legacy_builder_dropped_fields"), ["key"], "legacy drop fields")
    require_exact(
        context.get("legacy_builder_retains_volatile_fields"),
        ["access_count", "last_accessed_at"],
        "legacy volatile fields",
    )
    for key in [
        "context_builder_sha256",
        "exact_tokenizer_code_sha256",
        "exact_tokenizer_id",
        "exact_tokenizer_model_sha256",
        "max_context_bytes_per_case",
        "max_context_tokens_per_case",
    ]:
        require_exact(context.get(key), UNSET, f"context_and_result.{key}")

    quality = require_object(contract.get("data_quality"), "data_quality")
    require_exact_keys(
        quality,
        {
            "availability_is_not_admissibility",
            "checks",
            "grain",
            "old_successor_v3_data_admissible_as_confirmatory",
            "old_successor_v3_mechanism_reusable",
        },
        "data_quality",
    )
    require_exact(quality.get("availability_is_not_admissibility"), True, "data quality distinction")
    require_false(
        quality.get("old_successor_v3_data_admissible_as_confirmatory"),
        "legacy confirmatory admissibility",
    )
    require_exact(quality.get("old_successor_v3_mechanism_reusable"), True, "legacy mechanism reuse")
    require_exact(
        quality.get("checks"),
        [
            "KEY_UNIQUENESS",
            "VALIDITY_AND_DOMAIN",
            "RELATIONAL_INTEGRITY",
            "TIMELINESS_AND_FROZEN_AS_OF",
            "LEAKAGE_AND_CONSUMED_CASE_EXCLUSION",
            "MISSINGNESS_AND_TIMEOUT_INTENTION_TO_TREAT",
            "SOURCE_LINEAGE_AND_HASH_BINDING",
        ],
        "data quality checks",
    )
    require_exact(
        quality.get("grain"),
        {
            "latency": "case_id_x_condition_x_repetition",
            "primary_estimator": "case_id",
            "review": "trial_id_x_reviewer_slot_x_case_id_x_opaque_answer_id",
            "retrieval": "case_id_x_condition",
            "storage": "canonical_package_x_condition",
        },
        "data quality grain",
    )

    generation = require_object(contract.get("generation"), "generation")
    require_exact_keys(
        generation,
        {
            "condition_roster_sha256",
            "execution_profile_sha256",
            "generator_cli_identity_sha256",
            "generator_instruction_sha256",
            "generator_model_identity_sha256",
            "harness_sha256",
            "independent_invocations",
            "private_map_read_allowed",
            "status",
            "tool_or_external_fact_access_allowed",
        },
        "generation",
    )
    require_exact(
        generation.get("status"),
        "BLOCKED_PRE_OUTPUT_BINDINGS_UNSET",
        "generation status",
    )
    require_exact(generation.get("independent_invocations"), True, "generation invocation isolation")
    require_false(generation.get("private_map_read_allowed"), "generation private map read")
    require_false(
        generation.get("tool_or_external_fact_access_allowed"),
        "generation external access",
    )
    for key in [
        "condition_roster_sha256",
        "execution_profile_sha256",
        "generator_cli_identity_sha256",
        "generator_instruction_sha256",
        "generator_model_identity_sha256",
        "harness_sha256",
    ]:
        require_exact(generation.get(key), UNSET, f"generation.{key}")

    legacy = require_object(contract.get("legacy_precedent"), "legacy_precedent")
    require_exact_keys(
        legacy,
        {
            "base_snapshot_sha256",
            "binary_sha256",
            "consumed_case_count",
            "consumed_map_reusable",
            "consumed_score_claim_reusable",
            "consumed_sealed_cases_reusable",
            "mechanism_only",
            "runtime_source_commit",
        },
        "legacy_precedent",
    )
    require_exact(legacy.get("consumed_case_count"), 12, "legacy case count")
    require_exact(legacy.get("mechanism_only"), True, "legacy mechanism-only")
    for key in [
        "consumed_map_reusable",
        "consumed_score_claim_reusable",
        "consumed_sealed_cases_reusable",
    ]:
        require_false(legacy.get(key), f"legacy_precedent.{key}")
    require_exact(
        legacy.get("runtime_source_commit"),
        "1f75ede032b36db321c3e767d620eac5a6a44c6e",
        "legacy runtime source",
    )
    require_exact(
        legacy.get("binary_sha256"),
        "5ea3008c49bcc501e58f5cd6091b779350cb39b1b0105b3bce81b9439900ff7a",
        "legacy binary",
    )
    require_exact(
        legacy.get("base_snapshot_sha256"),
        "ef8679fc81a2640a79db5553c2f7cc9a104d6ebbb12bdf8cb83ebfafc4f3b16f",
        "legacy snapshot",
    )

    reference = require_object(contract.get("reference_condition"), "reference_condition")
    require_exact_keys(
        reference,
        {
            "ambient_inputs",
            "binary_sha256",
            "context_builder_sha256",
            "effective_config_sha256",
            "fixed_as_of_utc",
            "implementation_commit",
            "internal_budget_observation",
            "request",
            "runtime_features_sha256",
            "snapshot_sha256",
            "sqlite_runtime_version",
            "status",
        },
        "reference_condition",
    )
    require_exact(
        reference.get("status"),
        "NO_GO_EXACT_REFERENCE_BINDING",
        "reference status",
    )
    require_exact(reference.get("implementation_commit"), PARENT_COMMIT, "reference commit")
    require_exact(reference.get("request"), EXPECTED_REQUEST, "reference request")
    ambient = require_object(reference.get("ambient_inputs"), "reference ambient_inputs")
    require_exact_keys(
        ambient,
        {"inherit_parent_environment", "required_effective_environment"},
        "reference ambient_inputs",
    )
    require_false(ambient.get("inherit_parent_environment"), "parent environment inheritance")
    require_exact(
        ambient.get("required_effective_environment"),
        EXPECTED_ENVIRONMENT,
        "reference effective environment",
    )
    for key in [
        "binary_sha256",
        "context_builder_sha256",
        "effective_config_sha256",
        "fixed_as_of_utc",
        "runtime_features_sha256",
        "snapshot_sha256",
        "sqlite_runtime_version",
    ]:
        require_exact(reference.get(key), UNSET, f"reference_condition.{key}")
    require_exact(
        reference.get("internal_budget_observation"),
        {
            "final_output_top_k": 10,
            "graph_expansion_seed_cap": 10,
            "graph_neighbor_fanout": "UNBOUNDED_BLOCKS_EXACT_BUDGET",
            "mcp_filter_overfetch": 50,
            "sqlite_fts_raw_scan_cap": 800,
            "store_fts_ranked_pool": 200,
            "store_fused_cap": 50,
        },
        "reference internal budget",
    )

    sampling = require_object(contract.get("sampling"), "sampling")
    require_exact_keys(
        sampling,
        {
            "answer_blinding_seed_distinct_from_sampling_seed",
            "challenge_case_count_range",
            "challenge_role",
            "confirmatory_population",
            "dedup_rule",
            "dependence_cluster_rule",
            "eligible_frame_manifest_sha256",
            "exclusion_ledger_sha256",
            "frame_builder_sha256",
            "frame_window_end_utc",
            "frame_window_start_utc",
            "inclusion_exclusion_rules_sha256",
            "observation_unit",
            "old_successor_v3_cases_allowed",
            "pilot_confirmatory_disjointness_checker_sha256",
            "primary_selection",
            "primary_floor_excludes_diagnostic_challenge",
            "raw_frame_manifest_sha256",
            "reserve_manifest_sha256",
            "reserve_replacement_after_condition_output_allowed",
            "sample_weight",
            "sampling_receipt_must_precede_condition_output",
            "sampling_receipt_required_bindings",
            "sampling_receipt_sha256",
            "sampling_receipt_schema_sha256",
            "sampling_receipt_writer_sha256",
            "sampling_seed_anti_shopping_protocol",
            "sampling_seed_derivation_message",
            "sampling_seed_derivation_sha256",
            "sampling_seed_entropy_receipt_sha256",
            "sampling_seed_pairwise_distinct_from_latency_and_blinding",
            "sampling_seed_timing",
            "sampling_selection_algorithm_sha256",
            "sampling_selection_domain",
            "sampling_selection_message",
            "sampling_seed_sha256",
            "selected_case_manifest_sha256",
            "status",
            "strata_allocation_manifest_sha256",
            "target_population_definition_sha256",
        },
        "sampling",
    )
    require_exact(
        sampling.get("status"),
        "BLOCKED_PENDING_PREVALENCE_ADMISSION_BINDINGS",
        "sampling status",
    )
    require_false(sampling.get("old_successor_v3_cases_allowed"), "legacy case reuse")
    require_false(
        sampling.get("reserve_replacement_after_condition_output_allowed"),
        "post-output reserve replacement",
    )
    require_exact(
        sampling.get("confirmatory_population"),
        "UNTOUCHED_PREVALENCE_HOLDOUT_ONLY",
        "confirmatory population",
    )
    require_exact(sampling.get("challenge_role"), "DIAGNOSTIC_ONLY", "challenge role")
    require_exact(sampling.get("challenge_case_count_range"), [4, 6], "challenge case range")
    require_exact(
        sampling.get("answer_blinding_seed_distinct_from_sampling_seed"),
        True,
        "sampling/blinding seed separation",
    )
    require_exact(
        sampling.get("dedup_rule"),
        "DEDUP_REPLAYED_OR_IMPORTED_SAME_EVENT_KEEP_DISTINCT_REAL_EPISODES",
        "sampling dedup rule",
    )
    require_exact(
        sampling.get("dependence_cluster_rule"),
        "SEMANTIC_NEAR_DUPLICATES_CLUSTERED_NOT_POST_HOC_DELETED",
        "sampling cluster rule",
    )
    require_exact(
        sampling.get("primary_selection"),
        "STRATIFIED_SRSWOR_BY_HMAC_SHA256_ASCENDING",
        "sampling selection",
    )
    require_exact(
        sampling.get("primary_floor_excludes_diagnostic_challenge"),
        True,
        "primary floor challenge exclusion",
    )
    require_exact(
        sampling.get("sampling_receipt_must_precede_condition_output"),
        True,
        "sampling receipt ordering",
    )
    require_exact(
        sampling.get("sampling_receipt_required_bindings"),
        [
            "trial_id",
            "contract_sha256",
            "receipt_schema_sha256",
            "receipt_writer_sha256",
            "created_at_utc",
            "frame_o_excl_receipt_sha256",
            "seed_entropy_receipt_sha256",
            "seed_derivation_sha256",
            "sampling_selection_algorithm_sha256",
            "sampling_selection_domain",
            "sampling_selection_message",
            "eligible_frame_manifest_sha256",
            "strata_allocation_manifest_sha256",
            "selected_case_manifest_sha256",
            "reserve_manifest_sha256",
            "case_inclusion_probabilities",
            "case_sampling_weights",
            "receipt_precedes_first_condition_output",
        ],
        "sampling receipt bindings",
    )
    require_exact(
        sampling.get("sampling_seed_anti_shopping_protocol"),
        "EXTERNAL_UNPREDICTABLE_BEACON_OR_MULTI_PARTY_COMMIT_REVEAL_NO_SINGLE_PARTY_SEED_CHOICE",
        "sampling anti-shopping protocol",
    )
    require_exact(
        sampling.get("sampling_seed_derivation_message"),
        "domain_utf8_NUL_contract_sha256_ascii_NUL_trial_id_utf8_NUL_eligible_frame_sha256_ascii_NUL_external_entropy_sha256_ascii",
        "sampling seed derivation message",
    )
    require_exact(
        sampling.get("sampling_seed_timing"),
        "O_EXCL_FRAME_RECEIPT_THEN_EXTERNAL_UNPREDICTABLE_ENTROPY_THEN_DERIVE_AND_O_EXCL_SAMPLE_RECEIPT_BEFORE_OUTPUT",
        "sampling seed timing",
    )
    require_exact(
        sampling.get("sampling_seed_pairwise_distinct_from_latency_and_blinding"),
        True,
        "sampling seed pairwise separation",
    )
    require_exact(
        sampling.get("sampling_selection_domain"),
        "agent-bridge/track-b/sample/v1",
        "sampling selection domain",
    )
    require_exact(
        sampling.get("sampling_selection_message"),
        "domain_utf8_NUL_frame_sha256_ascii_NUL_stratum_utf8_NUL_case_id_utf8",
        "sampling selection message",
    )
    require_exact(
        sampling.get("observation_unit"),
        "ONE_REAL_QUERY_EPISODE_BEFORE_CONDITION_ASSIGNMENT",
        "sampling observation unit",
    )
    require_exact(
        sampling.get("sample_weight"),
        "N_h_DIV_n_h_APPLIED_ONCE_AT_CASE_GRAIN",
        "sample weight",
    )
    for key in [
        "eligible_frame_manifest_sha256",
        "exclusion_ledger_sha256",
        "frame_builder_sha256",
        "frame_window_end_utc",
        "frame_window_start_utc",
        "inclusion_exclusion_rules_sha256",
        "pilot_confirmatory_disjointness_checker_sha256",
        "raw_frame_manifest_sha256",
        "reserve_manifest_sha256",
        "sampling_receipt_sha256",
        "sampling_receipt_schema_sha256",
        "sampling_receipt_writer_sha256",
        "sampling_seed_derivation_sha256",
        "sampling_seed_entropy_receipt_sha256",
        "sampling_selection_algorithm_sha256",
        "sampling_seed_sha256",
        "selected_case_manifest_sha256",
        "strata_allocation_manifest_sha256",
        "target_population_definition_sha256",
    ]:
        require_exact(sampling.get(key), UNSET, f"sampling.{key}")

    review = require_object(contract.get("review_and_blinding"), "review_and_blinding")
    require_exact_keys(
        review,
        {
            "answer_blinding_seed_sha256",
            "blind_map_sha256",
            "blind_packet_sha256",
            "capture_sha256",
            "condition_roster_sha256",
            "condition_map_private",
            "fresh_roster_required",
            "generation_sha256",
            "map_bijection_checker_sha256",
            "map_identity_required_bindings",
            "map_schema_sha256",
            "old_reviewer_roster_reusable_without_refreeze",
            "pooled_reviewer_rescue_allowed",
            "required_reviewer_count",
            "review_command_schema_sha256",
            "review_instruction_sha256",
            "review_provenance_checker_sha256",
            "review_raw_response_schema_sha256",
            "review_receipt_schema_sha256",
            "review_schema_sha256",
            "reviewer_case_rule",
            "reviewer_conflict_and_overlap_manifest_sha256",
            "reviewer_roster_sha256",
            "score_order",
            "single_use_trial_specific_map_required",
            "status",
            "zero_retry",
        },
        "review_and_blinding",
    )
    require_exact(review.get("status"), "BLOCKED_BINDINGS_UNSET", "review status")
    require_exact(review.get("required_reviewer_count"), 2, "reviewer count")
    require_exact(review.get("zero_retry"), True, "review zero retry")
    require_exact(review.get("fresh_roster_required"), True, "fresh roster")
    require_false(
        review.get("old_reviewer_roster_reusable_without_refreeze"),
        "old reviewer roster reuse",
    )
    require_false(review.get("pooled_reviewer_rescue_allowed"), "reviewer pooling")
    require_exact(review.get("condition_map_private"), True, "private map")
    require_exact(review.get("single_use_trial_specific_map_required"), True, "single-use map")
    require_exact(
        review.get("map_identity_required_bindings"),
        [
            "trial_id",
            "contract_sha256",
            "sampling_receipt_sha256",
            "eligible_frame_manifest_sha256",
            "selected_case_manifest_sha256",
            "condition_roster_sha256",
            "capture_sha256",
            "generation_sha256",
            "blind_packet_sha256",
            "answer_blinding_seed_sha256",
        ],
        "map identity bindings",
    )
    require_exact(
        review.get("reviewer_case_rule"),
        "STRICT_CASE_PASS_IS_AND_ACROSS_BOTH_FIXED_REVIEWER_SLOTS",
        "reviewer case rule",
    )
    require_exact(
        review.get("score_order"),
        "VALIDATE_BOTH_RECEIPTS_THEN_O_EXCL_SCORE_CLAIM_THEN_FIRST_UNBLIND",
        "review score order",
    )
    for key in [
        "answer_blinding_seed_sha256",
        "blind_map_sha256",
        "blind_packet_sha256",
        "capture_sha256",
        "condition_roster_sha256",
        "generation_sha256",
        "map_bijection_checker_sha256",
        "map_schema_sha256",
        "review_command_schema_sha256",
        "review_instruction_sha256",
        "review_provenance_checker_sha256",
        "review_raw_response_schema_sha256",
        "review_receipt_schema_sha256",
        "review_schema_sha256",
        "reviewer_conflict_and_overlap_manifest_sha256",
        "reviewer_roster_sha256",
    ]:
        require_exact(review.get(key), UNSET, f"review_and_blinding.{key}")

    power = require_object(contract.get("power_and_estimator"), "power_and_estimator")
    require_exact_keys(
        power,
        {
            "bootstrap_or_lcb_seed_sha256",
            "case_weight_applied_once_after_reviewer_and",
            "challenge_population_confirmatory",
            "cluster_variance_policy_sha256",
            "confidence_rule",
            "minimum_point_lift",
            "minimum_total_coverage_floor",
            "paired_method_sha256",
            "pilot_population_sha256",
            "power_analysis_sha256",
            "required_primary_case_count",
            "required_primary_case_count_rule",
            "statistical_unit",
            "target_power",
        },
        "power_and_estimator",
    )
    require_exact(power.get("statistical_unit"), "CASE_NOT_ANSWER_CLAIM_OR_REVIEWER", "power unit")
    require_exact(power.get("case_weight_applied_once_after_reviewer_and"), True, "case weight application")
    require_false(power.get("challenge_population_confirmatory"), "challenge confirmation")
    require_exact(power.get("minimum_point_lift"), 0.05, "minimum point lift")
    require_exact(power.get("minimum_total_coverage_floor"), 24, "coverage floor")
    require_exact(
        power.get("required_primary_case_count_rule"),
        "MAX_OF_24_AND_POWER_REQUIRED_N_EXCLUDING_DIAGNOSTIC_CHALLENGE",
        "primary case count rule",
    )
    require_exact(
        power.get("confidence_rule"),
        "ONE_SIDED_95_PERCENT_PAIRED_CASE_LEVEL_LCB_GT_ZERO",
        "confidence rule",
    )
    for key in [
        "bootstrap_or_lcb_seed_sha256",
        "cluster_variance_policy_sha256",
        "paired_method_sha256",
        "pilot_population_sha256",
        "power_analysis_sha256",
        "required_primary_case_count",
        "target_power",
    ]:
        require_exact(power.get(key), UNSET, f"power_and_estimator.{key}")

    latency = require_object(contract.get("latency"), "latency")
    require_exact_keys(
        latency,
        {
            "affinity_policy_sha256",
            "aggregation_population",
            "aggregation_weighting",
            "cache_mode",
            "candidate_to_reference_p95_ratio_max",
            "clock_source",
            "clock_unit",
            "condition_assignment_domain",
            "condition_assignment_rule",
            "condition_order_algorithm",
            "condition_order_domain",
            "condition_order_message",
            "condition_order_seed_sha256",
            "context_hash_must_be_constant_across_repetitions",
            "dropped_timeout_or_error_units_allowed",
            "execution_order_independent_from_condition_assignment",
            "hardware_guard_policy_sha256",
            "hardware_guard_required_fields",
            "hardware_profile_sha256",
            "hardware_profile_required_fields",
            "measured_repetitions_per_case_condition",
            "order_balance_rule",
            "p95_rule",
            "pre_touch_manifest_sha256",
            "process_startup_and_snapshot_clone_included",
            "runner_sha256",
            "sacrificial_warmup_units_per_case_condition",
            "status",
            "timed_start_snapshot_rule",
            "timer_end",
            "timer_start",
            "timeout_disposition",
            "timeout_ns",
            "total_expected_units",
            "warmup_query_manifest_sha256",
        },
        "latency",
    )
    require_exact(
        latency.get("status"),
        "PROTOCOL_FROZEN_SYNTHETIC_ARITHMETIC_PASS_BINDINGS_UNSET",
        "latency status",
    )
    require_exact(latency.get("measured_repetitions_per_case_condition"), 6, "latency repetitions")
    require_exact(
        latency.get("sacrificial_warmup_units_per_case_condition"),
        1,
        "latency sacrificial warmups",
    )
    require_exact(latency.get("candidate_to_reference_p95_ratio_max"), 1.25, "latency ratio")
    require_exact(latency.get("clock_source"), "PYTHON_TIME_PERF_COUNTER_NS_MONOTONIC", "latency clock source")
    require_exact(latency.get("clock_unit"), "INTEGER_NANOSECONDS", "latency clock unit")
    require_exact(
        latency.get("aggregation_population"),
        "UNTOUCHED_PREVALENCE_HOLDOUT_ONLY",
        "latency population",
    )
    require_exact(
        latency.get("aggregation_weighting"),
        "CASE_SAMPLING_WEIGHT_DIVIDED_EQUALLY_ACROSS_FIXED_REPETITIONS",
        "latency weighting",
    )
    require_exact(
        latency.get("cache_mode"),
        "WARM_PRETOUCH_ON_SACRIFICIAL_CLONE_THEN_FRESH_TIMED_PROCESS_AND_PRISTINE_CLONE",
        "latency cache mode",
    )
    require_exact(
        latency.get("condition_order_algorithm"),
        "DOMAIN_SEPARATED_HMAC_GLOBAL_ORDINAL_AND_WITHIN_CASE_EXACT_AB_BA",
        "latency order algorithm",
    )
    require_exact(
        latency.get("condition_assignment_domain"),
        "agent-bridge/track-b/latency-assignment/v1",
        "latency assignment domain",
    )
    require_exact(
        latency.get("condition_assignment_rule"),
        "WITHIN_EACH_CASE_HMAC_RANK_LOWER_HALF_REFERENCE_FIRST",
        "latency assignment rule",
    )
    require_exact(
        latency.get("condition_order_domain"),
        "agent-bridge/track-b/latency-order/v1",
        "latency order domain",
    )
    require_exact(
        latency.get("condition_order_message"),
        "domain_utf8_NUL_case_id_utf8_NUL_repetition_ascii",
        "latency order message",
    )
    require_exact(
        latency.get("order_balance_rule"),
        "EACH_CASE_EXACTLY_HALF_REFERENCE_FIRST_AND_GLOBAL_SURVEY_WEIGHT_MASS_EXACTLY_BALANCED",
        "latency order balance",
    )
    require_exact(
        latency.get("execution_order_independent_from_condition_assignment"),
        True,
        "latency order/assignment independence",
    )
    require_exact(
        latency.get("p95_rule"),
        "FIRST_OBSERVED_LATENCY_WITH_CUMULATIVE_WEIGHT_GTE_0.95_TOTAL_WEIGHT_NO_INTERPOLATION",
        "weighted p95 rule",
    )
    require_exact(
        latency.get("context_hash_must_be_constant_across_repetitions"),
        True,
        "context repetition invariant",
    )
    require_false(latency.get("dropped_timeout_or_error_units_allowed"), "dropped latency units")
    require_false(latency.get("process_startup_and_snapshot_clone_included"), "startup timing")
    require_exact(
        latency.get("timer_start"),
        "IMMEDIATELY_BEFORE_FIRST_TIMED_MCP_CALL",
        "latency timer start",
    )
    require_exact(
        latency.get("timer_end"),
        "FINAL_CONTEXT_VALIDATED_AND_UTF8_BYTES_COMPUTED",
        "latency timer end",
    )
    require_exact(
        latency.get("timed_start_snapshot_rule"),
        "TIMED_CLONE_SHA256_MUST_EQUAL_SHARED_BASE_AFTER_SACRIFICIAL_WARMUP_IS_DISCARDED",
        "timed snapshot rule",
    )
    require_exact(
        latency.get("timeout_disposition"),
        "ANY_NON_OK_UNIT_BLOCKS_RUN_NO_DROP_NO_IMPUTATION",
        "timeout disposition",
    )
    require_exact(
        latency.get("hardware_guard_required_fields"),
        [
            "boot_session_sha256",
            "load1",
            "power_governor",
            "swap_used_bytes",
            "thermal_throttle_count",
        ],
        "hardware guard fields",
    )
    require_exact(
        latency.get("hardware_profile_required_fields"),
        [
            "affinity",
            "architecture",
            "cpu_model",
            "cpu_vendor",
            "filesystem",
            "host_slot",
            "kernel",
            "logical_cores",
            "memory_bytes",
            "os",
            "physical_cores",
            "power_governor",
            "python_version",
            "runtime_version",
            "smt_enabled",
            "thread_environment",
        ],
        "hardware profile fields",
    )
    for key in [
        "affinity_policy_sha256",
        "condition_order_seed_sha256",
        "hardware_guard_policy_sha256",
        "hardware_profile_sha256",
        "pre_touch_manifest_sha256",
        "runner_sha256",
        "timeout_ns",
        "total_expected_units",
        "warmup_query_manifest_sha256",
    ]:
        require_exact(latency.get(key), UNSET, f"latency.{key}")

    storage = require_object(contract.get("storage"), "storage")
    require_exact_keys(
        storage,
        {
            "allowed_persistent_artifact_roles",
            "arm_builder_manifest_sha256",
            "arm_manifest_required_fields",
            "artifact_directory_scan_manifest_sha256",
            "candidate_to_reference_normalized_ratio_max",
            "canonical_edge_order",
            "canonical_memory_order",
            "canonical_package_manifest_required_fields",
            "canonical_package_sha256",
            "canonical_serialization_rule",
            "canonical_source_bytes",
            "canonical_source_definition",
            "directory_scan_required",
            "edge_row_count",
            "edge_source_bytes",
            "forbidden_artifact_suffixes",
            "memory_row_count",
            "memory_source_bytes",
            "normalized_index_ratio_definition",
            "persistent_artifact_allowlist_sha256",
            "schema_digest_sha256",
            "serializer_sha256",
            "sqlite_page_size_allowed_values",
            "sqlite_quick_check_required",
            "sqlite_runtime_and_page_size_must_match_across_arms",
            "status",
            "total_persistent_condition_bytes_definition",
            "unlisted_persistent_artifact_allowed",
            "wal_or_shm_allowed_at_measurement",
        },
        "storage",
    )
    require_exact(
        storage.get("status"),
        "PROTOCOL_FROZEN_SYNTHETIC_ARITHMETIC_PASS_BINDINGS_UNSET",
        "storage status",
    )
    require_exact(storage.get("candidate_to_reference_normalized_ratio_max"), 1.1, "storage ratio")
    require_exact(storage.get("sqlite_quick_check_required"), True, "storage quick check")
    require_exact(storage.get("directory_scan_required"), True, "storage directory scan")
    require_exact(
        storage.get("sqlite_runtime_and_page_size_must_match_across_arms"),
        True,
        "storage cross-arm SQLite identity",
    )
    require_false(storage.get("wal_or_shm_allowed_at_measurement"), "storage WAL/SHM")
    require_false(storage.get("unlisted_persistent_artifact_allowed"), "unlisted storage artifact")
    require_exact(
        storage.get("canonical_source_definition"),
        "SUM_EXACT_UNCOMPRESSED_BYTES_OF_DETERMINISTIC_LF_UTF8_MEMORIES_JSONL_AND_EDGES_JSONL",
        "canonical source definition",
    )
    require_exact(
        storage.get("canonical_edge_order"),
        "source_key_asc_target_key_asc_edge_type_asc_created_at_asc",
        "canonical edge order",
    )
    require_exact(
        storage.get("canonical_memory_order"),
        "created_at_asc_key_asc",
        "canonical memory order",
    )
    require_exact(
        storage.get("canonical_serialization_rule"),
        "UTF8_LF_ONE_SORTED_KEY_JSON_OBJECT_PER_LINE_NO_NAN",
        "canonical serialization rule",
    )
    require_exact(
        storage.get("total_persistent_condition_bytes_definition"),
        "SUM_ST_SIZE_OF_CLOSED_MAIN_SQLITE_AND_ALL_CONDITION_SPECIFIC_PERSISTENT_ARTIFACTS",
        "persistent bytes definition",
    )
    require_exact(
        storage.get("normalized_index_ratio_definition"),
        "total_persistent_condition_bytes_DIV_canonical_source_bytes",
        "normalized storage ratio definition",
    )
    require_exact(
        storage.get("forbidden_artifact_suffixes"),
        ["-journal", "-shm", "-wal"],
        "forbidden artifact suffixes",
    )
    require_exact(
        storage.get("allowed_persistent_artifact_roles"),
        ["main_sqlite", "truth_index"],
        "allowed persistent artifact roles",
    )
    require_exact(
        storage.get("sqlite_page_size_allowed_values"),
        [512, 1024, 2048, 4096, 8192, 16384, 32768, 65536],
        "SQLite page-size domain",
    )
    require_exact(
        storage.get("canonical_package_manifest_required_fields"),
        [
            "package_sha256",
            "serializer_sha256",
            "serialization_rule",
            "memories_sha256",
            "memory_order",
            "edges_sha256",
            "edge_order",
            "memory_source_bytes",
            "edge_source_bytes",
            "canonical_source_bytes",
            "memory_row_count",
            "edge_row_count",
        ],
        "canonical package fields",
    )
    require_exact(
        storage.get("arm_manifest_required_fields"),
        [
            "condition_id",
            "builder_sha256",
            "canonical_package_sha256",
            "closed",
            "main_sqlite_st_size",
            "page_size",
            "page_count",
            "freelist_count",
            "user_version",
            "schema_meta_version",
            "sqlite_version",
            "schema_digest_sha256",
            "quick_check",
            "artifacts",
            "total_persistent_condition_bytes",
            "normalized_persistent_bytes",
        ],
        "storage arm fields",
    )
    for key in [
        "arm_builder_manifest_sha256",
        "artifact_directory_scan_manifest_sha256",
        "canonical_package_sha256",
        "canonical_source_bytes",
        "edge_row_count",
        "edge_source_bytes",
        "memory_row_count",
        "memory_source_bytes",
        "persistent_artifact_allowlist_sha256",
        "schema_digest_sha256",
        "serializer_sha256",
    ]:
        require_exact(storage.get(key), UNSET, f"storage.{key}")

    strict = require_object(contract.get("strict_case_pass"), "strict_case_pass")
    require_exact_keys(
        strict,
        {
            "answerable_all_gold_recalled",
            "answerable_authority_exists",
            "answerable_current_referent_correct",
            "answerable_required_claim_score",
            "currentness_required",
            "field_sources",
            "forbidden_claim_count_max",
            "missingness_disposition",
            "response_mode_must_be_correct",
            "unanswerable_requires_correct_abstention",
            "unsupported_assertion_count_max",
            "usefulness_min",
        },
        "strict_case_pass",
    )
    require_exact(strict.get("answerable_all_gold_recalled"), True, "strict gold recall")
    require_exact(strict.get("answerable_authority_exists"), True, "strict authority")
    require_exact(strict.get("answerable_current_referent_correct"), True, "strict referent")
    require_exact(strict.get("answerable_required_claim_score"), 2, "strict claim score")
    require_exact(strict.get("currentness_required"), "pass", "strict currentness")
    require_exact(
        strict.get("field_sources"),
        {
            "deterministic_retrieval_truth_gates": [
                "authority_exists",
                "all_gold_recalled",
                "current_referent_correct",
            ],
            "each_reviewer_answer_gates": [
                "required_claim_score",
                "currentness",
                "response_mode",
                "required_abstention",
                "forbidden_or_stale_count",
                "unsupported_assertion_count",
                "usefulness",
            ],
        },
        "strict field sources",
    )
    require_exact(
        strict.get("missingness_disposition"),
        {
            "capture_timeout_or_error": "TERMINAL_PROTOCOL_FAILURE_NO_REPLACEMENT",
            "generation_failure": "TERMINAL_PROTOCOL_FAILURE_NO_REPLACEMENT",
            "missing_or_invalid_review": "TERMINAL_PROTOCOL_FAILURE_NO_UNBLIND_NO_REPLACEMENT",
        },
        "strict missingness disposition",
    )
    require_exact(strict.get("forbidden_claim_count_max"), 0, "strict forbidden count")
    require_exact(strict.get("unsupported_assertion_count_max"), 0, "strict unsupported count")
    require_exact(strict.get("usefulness_min"), 4, "strict usefulness")
    require_exact(strict.get("unanswerable_requires_correct_abstention"), True, "strict abstention")
    require_exact(strict.get("response_mode_must_be_correct"), True, "strict response mode")

    public = require_object(contract.get("public_fixture"), "public_fixture")
    require_exact_keys(
        public,
        {
            "benchmark_claim",
            "private_material_allowed",
            "required_adversarial_obligations",
            "runtime_execution",
            "scientific_result",
            "scope",
            "synthetic_fixture_path",
            "synthetic_fixture_sha256",
        },
        "public_fixture",
    )
    require_false(public.get("benchmark_claim"), "public benchmark claim")
    require_false(public.get("runtime_execution"), "public runtime execution")
    require_false(public.get("scientific_result"), "public scientific result")
    require_false(public.get("private_material_allowed"), "public private material")
    require_exact(
        public.get("scope"),
        "CONTRACT_AND_SYNTHETIC_ARITHMETIC_CHECKER_PLUMBING_ONLY",
        "public fixture scope",
    )
    require_exact(
        public.get("synthetic_fixture_path"),
        SYNTHETIC_PATH.as_posix(),
        "public synthetic fixture path",
    )
    require_exact(
        public.get("synthetic_fixture_sha256"),
        "3c1f57abb41a92692bc84d019635073b97b32ae3ee3fe231ba3048017a2d0b43",
        "public synthetic fixture hash",
    )
    require_exact(
        public.get("required_adversarial_obligations"),
        [
            "NORMAL_FTS_HIT",
            "GRAPH_ONLY_HIT_WITH_ACCESS_MUTATION",
            "EXCLUDED_SKILL_HIT",
            "EQUAL_SCORE_TIE",
            "TTL_BOUNDARY",
            "SEED_OR_COACTIVATION_ORDER_CHANGE",
        ],
        "public obligations",
    )

    stages = require_object(contract.get("stages"), "stages")
    require_exact(
        stages,
        {
            "post_generation_pre_review": {
                "required_artifacts": [
                    "capture_sha256",
                    "generation_sha256",
                    "blind_packet_sha256",
                    "blind_map_sha256",
                    "map_bijection_receipt_sha256",
                ],
                "side_effect_unlocked": "FIXED_BLIND_REVIEW_ONLY",
                "status": "NOT_REACHED",
            },
            "pre_output_admission": {
                "required_binding_groups": [
                    "reference_runtime_clock_environment_snapshot_and_context",
                    "candidate_adapter_and_truth_authority",
                    "prevalence_frame_sampling_power_and_sampling_receipt",
                    "generator_condition_roster_reviewer_roster_and_seed_commitments",
                    "hardware_latency_tokenizer_and_storage_protocol_identities",
                ],
                "side_effect_unlocked": "CONDITION_CAPTURE_AND_GENERATION_ONLY",
                "status": "BLOCKED",
            },
            "pre_unblind": {
                "required_artifacts": [
                    "both_complete_review_objects",
                    "both_command_request_raw_response_and_receipt_chains",
                    "contract_scoped_o_excl_score_claim",
                ],
                "side_effect_unlocked": "FIRST_CONDITION_MAP_READ_AND_SINGLE_SCORE_ONLY",
                "status": "NOT_REACHED",
            },
        },
        "stages",
    )

    truth = require_object(contract.get("truth_inputs"), "truth_inputs")
    require_exact_keys(
        truth,
        {
            "claim_authority_policy_sha256",
            "gold_evidence_manifest_sha256",
            "referent_schema_sha256",
            "status",
            "strict_case_algorithm_sha256",
            "truth_as_of_utc",
            "truth_authority_manifest_sha256",
            "truth_manifest_schema_sha256",
        },
        "truth_inputs",
    )
    require_exact(
        truth.get("status"),
        "BLOCKED_PRE_OUTPUT_BINDINGS_UNSET",
        "truth input status",
    )
    for key in [
        "claim_authority_policy_sha256",
        "gold_evidence_manifest_sha256",
        "referent_schema_sha256",
        "strict_case_algorithm_sha256",
        "truth_as_of_utc",
        "truth_authority_manifest_sha256",
        "truth_manifest_schema_sha256",
    ]:
        require_exact(truth.get(key), UNSET, f"truth_inputs.{key}")

    validate_sources(contract, root)


def require_sha256_value(value: Any, path: str) -> str:
    if not isinstance(value, str) or not SHA256_RE.fullmatch(value):
        fail(f"{path} must be a lowercase SHA-256")
    return value


def require_int(value: Any, path: str, *, minimum: int = 0) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < minimum:
        fail(f"{path} must be an integer >= {minimum}")
    return value


def require_finite_positive(value: Any, path: str) -> float:
    if not isinstance(value, float) or not math.isfinite(value) or value <= 0:
        fail(f"{path} must be a positive finite JSON float")
    return value


def require_positive_fraction(value: Any, path: str) -> Fraction:
    fraction = require_object(value, path)
    require_exact_keys(fraction, {"denominator", "numerator"}, path)
    numerator = require_int(fraction.get("numerator"), f"{path}.numerator", minimum=1)
    denominator = require_int(
        fraction.get("denominator"), f"{path}.denominator", minimum=1
    )
    if math.gcd(numerator, denominator) != 1:
        fail(f"{path} must be in lowest terms")
    return Fraction(numerator, denominator)


def compact_canonical_bytes(value: Any) -> bytes:
    try:
        return json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        fail(f"cannot render compact canonical JSON: {exc}")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def weighted_observed_quantile(
    observations: list[tuple[int, Fraction]], numerator: int, denominator: int
) -> int:
    if not observations or numerator <= 0 or numerator > denominator:
        fail("invalid weighted quantile input")
    ordered = sorted(observations, key=lambda row: row[0])
    total = sum((weight for _, weight in ordered), start=Fraction(0, 1))
    if total <= 0:
        fail("weighted quantile total weight must be positive")
    threshold = total * Fraction(numerator, denominator)
    cumulative = Fraction(0, 1)
    for observed, weight in ordered:
        if weight <= 0:
            fail("weighted quantile observation weight must be positive")
        cumulative += weight
        if cumulative >= threshold:
            return observed
    fail("weighted quantile did not reach its threshold")


def validate_synthetic_sampling(
    fixture: dict[str, Any],
    contract: dict[str, Any],
    case_weights: dict[str, Fraction],
    case_order: list[str],
) -> tuple[bytes, int, int, str]:
    sampling = require_object(fixture.get("sampling"), "synthetic sampling")
    require_exact_keys(
        sampling,
        {
            "algorithm",
            "allocations",
            "case_inclusion_probabilities",
            "case_sampling_weights",
            "contract_id",
            "domain",
            "eligible_frame",
            "eligible_frame_sha256",
            "frame_o_excl_frozen",
            "message_format",
            "receipt_precedes_first_condition_output",
            "receipt_schema",
            "receipt_writer_sha256",
            "reserve_case_ids",
            "sampling_receipt_sha256",
            "seed_hex",
            "seed_protocol",
            "seed_sha256",
            "selected_case_ids",
            "trial_id",
        },
        "synthetic sampling",
    )
    require_exact(
        sampling.get("algorithm"),
        "STRATIFIED_SRSWOR_BY_HMAC_SHA256_ASCENDING",
        "synthetic sampling algorithm",
    )
    require_exact(
        sampling.get("algorithm"),
        contract["sampling"]["primary_selection"],
        "synthetic sampling contract algorithm",
    )
    require_exact(
        sampling.get("domain"),
        contract["sampling"]["sampling_selection_domain"],
        "synthetic sampling domain",
    )
    require_exact(
        sampling.get("message_format"),
        contract["sampling"]["sampling_selection_message"],
        "synthetic sampling message",
    )
    require_exact(
        sampling.get("contract_id"), contract["contract_id"], "synthetic sampling contract"
    )
    require_exact(
        sampling.get("trial_id"),
        "public_synthetic_track_b_admission_v0",
        "synthetic sampling trial",
    )
    require_exact(
        sampling.get("receipt_schema"),
        "agent_bridge.biocortex_ab_track_b_sampling_receipt.v0",
        "synthetic sampling receipt schema",
    )
    require_exact(
        sampling.get("receipt_writer_sha256"),
        sha256_bytes(b"PUBLIC_SYNTHETIC_SAMPLING_RECEIPT_WRITER_V0"),
        "synthetic sampling receipt writer",
    )
    require_exact(
        sampling.get("frame_o_excl_frozen"), True, "synthetic frame freeze ordering"
    )
    require_exact(
        sampling.get("receipt_precedes_first_condition_output"),
        True,
        "synthetic sampling receipt ordering",
    )
    require_exact(
        sampling.get("seed_protocol"),
        "PUBLIC_SYNTHETIC_FIXED_SEED_NO_REAL_RANDOMNESS",
        "synthetic seed protocol boundary",
    )

    frame_raw = sampling.get("eligible_frame")
    if not isinstance(frame_raw, list) or not frame_raw:
        fail("synthetic eligible frame must be a non-empty array")
    frame_by_stratum: dict[str, list[str]] = {}
    frame_case_ids: list[str] = []
    event_ids: set[str] = set()
    for index, row_value in enumerate(frame_raw):
        row = require_object(row_value, f"synthetic eligible_frame[{index}]")
        require_exact_keys(
            row,
            {"case_id", "dependence_cluster_id", "event_id", "stratum"},
            f"synthetic eligible_frame[{index}]",
        )
        case_id = row.get("case_id")
        if not isinstance(case_id, str) or not re.fullmatch(
            r"public_(?:reserve|synth)_[a-z0-9]+", case_id
        ):
            fail("synthetic eligible-frame case id domain drift")
        if case_id in frame_case_ids:
            fail("duplicate synthetic eligible-frame case id")
        event_id = row.get("event_id")
        if not isinstance(event_id, str) or not event_id:
            fail("synthetic eligible-frame event id invalid")
        if event_id in event_ids:
            fail("duplicate synthetic eligible-frame event id")
        event_ids.add(event_id)
        cluster_id = row.get("dependence_cluster_id")
        if not isinstance(cluster_id, str) or not cluster_id:
            fail("synthetic eligible-frame dependence cluster invalid")
        stratum = row.get("stratum")
        if not isinstance(stratum, str) or not re.fullmatch(r"[a-z][a-z0-9_]*", stratum):
            fail("synthetic eligible-frame stratum invalid")
        frame_case_ids.append(case_id)
        frame_by_stratum.setdefault(stratum, []).append(case_id)
    require_exact(frame_case_ids, sorted(frame_case_ids), "synthetic eligible-frame order")
    frame_sha256 = sha256_bytes(compact_canonical_bytes(frame_raw))
    require_exact(
        sampling.get("eligible_frame_sha256"),
        frame_sha256,
        "synthetic eligible-frame hash",
    )

    allocations_raw = sampling.get("allocations")
    if not isinstance(allocations_raw, list) or not allocations_raw:
        fail("synthetic sampling allocations must be a non-empty array")
    allocations: dict[str, tuple[int, int]] = {}
    allocation_order: list[str] = []
    for index, allocation_value in enumerate(allocations_raw):
        allocation = require_object(
            allocation_value, f"synthetic sampling allocations[{index}]"
        )
        require_exact_keys(
            allocation,
            {"N_h", "n_h", "stratum"},
            f"synthetic sampling allocations[{index}]",
        )
        stratum = allocation.get("stratum")
        if not isinstance(stratum, str) or stratum in allocations:
            fail("synthetic sampling allocation stratum invalid or duplicate")
        population = require_int(allocation.get("N_h"), "synthetic sampling N_h", minimum=1)
        sample = require_int(allocation.get("n_h"), "synthetic sampling n_h", minimum=1)
        if sample > population:
            fail("synthetic sampling n_h exceeds N_h")
        allocations[stratum] = (population, sample)
        allocation_order.append(stratum)
    require_exact(allocation_order, sorted(allocation_order), "synthetic allocation order")
    require_exact(set(allocations), set(frame_by_stratum), "synthetic allocation strata")
    for stratum, (population, _) in allocations.items():
        require_exact(
            population,
            len(frame_by_stratum[stratum]),
            f"synthetic sampling population {stratum}",
        )

    seed_hex = sampling.get("seed_hex")
    if not isinstance(seed_hex, str) or not re.fullmatch(r"[0-9a-f]{64}", seed_hex):
        fail("synthetic sampling seed must be 256-bit lowercase hex")
    seed = bytes.fromhex(seed_hex)
    seed_sha256 = sha256_bytes(seed)
    require_exact(
        sampling.get("seed_sha256"), seed_sha256, "synthetic sampling seed commitment"
    )
    domain = sampling["domain"].encode("utf-8")
    selected: list[str] = []
    reserve: list[str] = []
    selected_strata: dict[str, str] = {}
    for stratum in allocation_order:
        scored: list[tuple[bytes, str]] = []
        for case_id in frame_by_stratum[stratum]:
            message = (
                domain
                + b"\0"
                + frame_sha256.encode("ascii")
                + b"\0"
                + stratum.encode("utf-8")
                + b"\0"
                + case_id.encode("utf-8")
            )
            scored.append((hmac.new(seed, message, hashlib.sha256).digest(), case_id))
        scored.sort()
        sample = allocations[stratum][1]
        for _, case_id in scored[:sample]:
            selected.append(case_id)
            selected_strata[case_id] = stratum
        reserve.extend(case_id for _, case_id in scored[sample:])
    selected_sorted = sorted(selected)
    require_exact(
        sampling.get("selected_case_ids"),
        selected_sorted,
        "synthetic selected-case manifest",
    )
    require_exact(
        sampling.get("reserve_case_ids"), reserve, "synthetic reserve-case manifest"
    )
    if set(selected_sorted) & set(reserve):
        fail("synthetic selected/reserve overlap")
    require_exact(
        set(selected_sorted) | set(reserve),
        set(frame_case_ids),
        "synthetic selected/reserve frame partition",
    )
    require_exact(case_order, selected_sorted, "synthetic selected/latency case binding")
    for case_id in selected_sorted:
        stratum = selected_strata[case_id]
        population, sample = allocations[stratum]
        expected_weight = Fraction(population, sample)
        if case_weights[case_id] != expected_weight:
            fail("synthetic sampling weight does not equal N_h/n_h")

    inclusion_probabilities = []
    sampling_weights = []
    for case_id in selected_sorted:
        stratum = selected_strata[case_id]
        population, sample = allocations[stratum]
        probability = Fraction(sample, population)
        weight = Fraction(population, sample)
        inclusion_probabilities.append(
            {
                "case_id": case_id,
                "denominator": probability.denominator,
                "numerator": probability.numerator,
            }
        )
        sampling_weights.append(
            {
                "case_id": case_id,
                "denominator": weight.denominator,
                "numerator": weight.numerator,
            }
        )
    require_exact(
        sampling.get("case_inclusion_probabilities"),
        inclusion_probabilities,
        "synthetic inclusion probabilities",
    )
    require_exact(
        sampling.get("case_sampling_weights"),
        sampling_weights,
        "synthetic receipt sampling weights",
    )

    receipt_core = {
        "algorithm": sampling["algorithm"],
        "allocations": allocations_raw,
        "case_inclusion_probabilities": inclusion_probabilities,
        "case_sampling_weights": sampling_weights,
        "contract_id": sampling["contract_id"],
        "domain": sampling["domain"],
        "eligible_frame_sha256": frame_sha256,
        "frame_o_excl_frozen": sampling["frame_o_excl_frozen"],
        "message_format": sampling["message_format"],
        "receipt_precedes_first_condition_output": sampling[
            "receipt_precedes_first_condition_output"
        ],
        "receipt_schema": sampling["receipt_schema"],
        "receipt_writer_sha256": sampling["receipt_writer_sha256"],
        "reserve_case_ids": reserve,
        "sampling_seed_sha256": seed_sha256,
        "seed_protocol": sampling["seed_protocol"],
        "selected_case_ids": selected_sorted,
        "trial_id": sampling["trial_id"],
    }
    receipt_sha256 = sha256_bytes(compact_canonical_bytes(receipt_core))
    require_exact(
        sampling.get("sampling_receipt_sha256"),
        receipt_sha256,
        "synthetic sampling receipt hash",
    )
    return seed, len(selected_sorted), len(reserve), receipt_sha256


def validate_synthetic_fixture(
    fixture: dict[str, Any], contract: dict[str, Any]
) -> dict[str, Any]:
    require_exact_keys(
        fixture,
        {
            "base_snapshot_sha256",
            "canonical_source",
            "cases",
            "conditions",
            "hardware",
            "latency_units",
            "private_material",
            "sampling",
            "schedule",
            "schema",
            "storage_arms",
            "synthetic_only",
            "timeout_ns",
            "tokenizer",
        },
        "synthetic fixture",
    )
    require_exact(fixture.get("schema"), SYNTHETIC_SCHEMA, "synthetic schema")
    require_exact(fixture.get("synthetic_only"), True, "synthetic-only marker")
    require_false(fixture.get("private_material"), "synthetic private material")
    require_exact(fixture.get("conditions"), ["reference", "candidate"], "synthetic conditions")
    base_snapshot = require_sha256_value(
        fixture.get("base_snapshot_sha256"), "synthetic base snapshot"
    )
    timeout_ns = require_int(fixture.get("timeout_ns"), "synthetic timeout", minimum=1)

    tokenizer = require_object(fixture.get("tokenizer"), "synthetic tokenizer")
    require_exact_keys(tokenizer, {"algorithm", "config_sha256", "id"}, "synthetic tokenizer")
    require_exact(
        tokenizer.get("algorithm"),
        "UNICODE_WHITESPACE_SPLIT_V0",
        "synthetic tokenizer algorithm",
    )
    require_exact(
        tokenizer.get("id"),
        "public_synthetic_unicode_whitespace_v0",
        "synthetic tokenizer id",
    )
    require_exact(
        tokenizer.get("config_sha256"),
        sha256_bytes(b"UNICODE_WHITESPACE_SPLIT_V0"),
        "synthetic tokenizer config",
    )

    cases_raw = fixture.get("cases")
    if not isinstance(cases_raw, list) or not cases_raw:
        fail("synthetic cases must be a non-empty array")
    case_weights: dict[str, Fraction] = {}
    case_order: list[str] = []
    for index, case_value in enumerate(cases_raw):
        case = require_object(case_value, f"synthetic cases[{index}]")
        require_exact_keys(case, {"case_id", "sampling_weight"}, f"synthetic cases[{index}]")
        case_id = case.get("case_id")
        if not isinstance(case_id, str) or not re.fullmatch(r"public_synth_[a-z]+", case_id):
            fail("synthetic case id domain drift")
        if case_id in case_weights:
            fail("duplicate synthetic case id")
        case_weights[case_id] = require_positive_fraction(
            case.get("sampling_weight"), "synthetic sampling weight"
        )
        case_order.append(case_id)
    require_exact(case_order, sorted(case_order), "synthetic case order")

    (
        sampling_seed,
        sampling_selected_count,
        sampling_reserve_count,
        sampling_receipt_sha256,
    ) = validate_synthetic_sampling(fixture, contract, case_weights, case_order)

    repetitions = contract["latency"]["measured_repetitions_per_case_condition"]
    expected_pairs = [(case_id, rep) for case_id in case_order for rep in range(1, repetitions + 1)]
    if len(expected_pairs) % 2:
        fail("synthetic order population must contain an even number of pairs")

    schedule = require_object(fixture.get("schedule"), "synthetic schedule")
    require_exact_keys(
        schedule,
        {
            "algorithm",
            "assignment_domain",
            "message_format",
            "order_domain",
            "pair_count",
            "seed_hex",
            "seed_sha256",
        },
        "synthetic schedule",
    )
    require_exact(
        schedule.get("algorithm"),
        "HMAC_SHA256_DOMAIN_SEPARATED_GLOBAL_ORDINAL_WITHIN_CASE_HALF_BALANCED",
        "synthetic schedule algorithm",
    )
    require_exact(
        schedule.get("order_domain"),
        contract["latency"]["condition_order_domain"],
        "synthetic schedule order domain",
    )
    require_exact(
        schedule.get("assignment_domain"),
        contract["latency"]["condition_assignment_domain"],
        "synthetic schedule assignment domain",
    )
    require_exact(
        schedule.get("message_format"),
        contract["latency"]["condition_order_message"],
        "synthetic schedule message",
    )
    require_exact(schedule.get("pair_count"), len(expected_pairs), "synthetic pair count")
    seed_hex = schedule.get("seed_hex")
    if not isinstance(seed_hex, str) or not re.fullmatch(r"[0-9a-f]{64}", seed_hex):
        fail("synthetic schedule seed must be 256-bit lowercase hex")
    seed = bytes.fromhex(seed_hex)
    require_exact(schedule.get("seed_sha256"), sha256_bytes(seed), "synthetic seed commitment")
    if hmac.compare_digest(seed, sampling_seed):
        fail("synthetic sampling and latency-order seeds must be distinct")
    order_domain = schedule["order_domain"].encode("utf-8")
    assignment_domain = schedule["assignment_domain"].encode("utf-8")
    ordered_pairs: list[tuple[bytes, str, int]] = []
    assignment_by_case: dict[str, list[tuple[bytes, int]]] = {
        case_id: [] for case_id in case_order
    }
    for case_id, rep in expected_pairs:
        suffix = case_id.encode("utf-8") + b"\0" + str(rep).encode("ascii")
        order_message = order_domain + b"\0" + suffix
        assignment_message = assignment_domain + b"\0" + suffix
        ordered_pairs.append(
            (hmac.new(seed, order_message, hashlib.sha256).digest(), case_id, rep)
        )
        assignment_by_case[case_id].append(
            (hmac.new(seed, assignment_message, hashlib.sha256).digest(), rep)
        )
    ordered_pairs.sort()
    expected_ordinals = {
        (case_id, rep): ordinal + 1
        for ordinal, (_, case_id, rep) in enumerate(ordered_pairs)
    }
    expected_first: dict[tuple[str, int], str] = {}
    for case_id, ranked in assignment_by_case.items():
        ranked.sort()
        for rank, (_, rep) in enumerate(ranked):
            expected_first[(case_id, rep)] = (
                "reference" if rank < repetitions // 2 else "candidate"
            )

    units = fixture.get("latency_units")
    if not isinstance(units, list) or len(units) != len(expected_pairs):
        fail("synthetic latency pair coverage drift")
    seen_pairs: set[tuple[str, int]] = set()
    seen_ordinals: set[int] = set()
    first_counts = {"reference": 0, "candidate": 0}
    first_counts_by_case = {
        case_id: {"reference": 0, "candidate": 0} for case_id in case_order
    }
    observations: dict[str, list[tuple[int, Fraction]]] = {
        "reference": [],
        "candidate": [],
    }
    context_identity: dict[tuple[str, str], tuple[str, int, int]] = {}
    utf8_multibyte_seen = False
    unit_rows = 0
    for index, unit_value in enumerate(units):
        unit = require_object(unit_value, f"synthetic latency_units[{index}]")
        require_exact_keys(
            unit,
            {
                "case_id",
                "conditions",
                "first_condition",
                "ordinal",
                "repetition",
                "sacrificial_warmup_discarded",
                "timed_start_snapshot_sha256",
            },
            f"synthetic latency_units[{index}]",
        )
        case_id = unit.get("case_id")
        if case_id not in case_weights:
            fail("synthetic unit references unknown case")
        rep = require_int(unit.get("repetition"), "synthetic repetition", minimum=1)
        if rep > repetitions:
            fail("synthetic repetition exceeds contract")
        pair = (case_id, rep)
        if pair in seen_pairs:
            fail("duplicate synthetic case/repetition pair")
        seen_pairs.add(pair)
        ordinal = require_int(unit.get("ordinal"), "synthetic ordinal", minimum=1)
        require_exact(ordinal, index + 1, "synthetic execution array order")
        if ordinal in seen_ordinals:
            fail("duplicate synthetic ordinal")
        seen_ordinals.add(ordinal)
        require_exact(ordinal, expected_ordinals[pair], "synthetic schedule ordinal")
        expected_first_condition = expected_first[pair]
        require_exact(
            unit.get("first_condition"),
            expected_first_condition,
            "synthetic first condition",
        )
        first_counts[expected_first_condition] += 1
        first_counts_by_case[case_id][expected_first_condition] += 1
        require_exact(
            unit.get("sacrificial_warmup_discarded"),
            True,
            "synthetic sacrificial warmup",
        )
        require_exact(
            unit.get("timed_start_snapshot_sha256"),
            base_snapshot,
            "synthetic timed-start snapshot",
        )
        conditions = require_object(unit.get("conditions"), "synthetic unit conditions")
        require_exact_keys(conditions, {"reference", "candidate"}, "synthetic unit conditions")
        per_pair_shape: dict[str, tuple[int, int]] = {}
        for condition in ["reference", "candidate"]:
            row = require_object(conditions.get(condition), f"synthetic {condition} row")
            require_exact_keys(
                row,
                {
                    "assembly_ns",
                    "context_tokens",
                    "latency_ns",
                    "result_bytes",
                    "result_sha256",
                    "result_text",
                    "retrieval_wire_ns",
                    "status",
                },
                f"synthetic {condition} row",
            )
            require_exact(row.get("status"), "ok", "synthetic unit status")
            latency_ns = require_int(row.get("latency_ns"), "synthetic latency", minimum=1)
            if latency_ns >= timeout_ns:
                fail("synthetic latency reached timeout")
            wire_ns = require_int(row.get("retrieval_wire_ns"), "synthetic wire latency", minimum=0)
            assembly_ns = require_int(row.get("assembly_ns"), "synthetic assembly latency", minimum=0)
            if wire_ns + assembly_ns != latency_ns:
                fail("synthetic latency components do not sum")
            result_text = row.get("result_text")
            if not isinstance(result_text, str) or not result_text:
                fail("synthetic result text must be non-empty UTF-8")
            result_raw = result_text.encode("utf-8")
            utf8_multibyte_seen = utf8_multibyte_seen or len(result_raw) != len(result_text)
            require_exact(row.get("result_bytes"), len(result_raw), "synthetic result bytes")
            require_exact(
                row.get("result_sha256"), sha256_bytes(result_raw), "synthetic result hash"
            )
            require_exact(
                row.get("context_tokens"), len(result_text.split()), "synthetic token count"
            )
            identity = (row["result_sha256"], row["result_bytes"], row["context_tokens"])
            prior = context_identity.setdefault((case_id, condition), identity)
            require_exact(identity, prior, "synthetic context repetition invariant")
            per_pair_shape[condition] = (row["result_bytes"], row["context_tokens"])
            observations[condition].append(
                (latency_ns, case_weights[case_id] / repetitions)
            )
            unit_rows += 1
        if per_pair_shape["candidate"][0] > per_pair_shape["reference"][0]:
            fail("synthetic candidate context bytes exceed reference")
        if per_pair_shape["candidate"][1] > per_pair_shape["reference"][1]:
            fail("synthetic candidate context tokens exceed reference")
    require_exact(seen_pairs, set(expected_pairs), "synthetic pair set")
    require_exact(seen_ordinals, set(range(1, len(expected_pairs) + 1)), "synthetic ordinals")
    require_exact(
        first_counts,
        {"reference": len(expected_pairs) // 2, "candidate": len(expected_pairs) // 2},
        "synthetic AB/BA balance",
    )
    for case_id, counts in first_counts_by_case.items():
        require_exact(
            counts,
            {"reference": repetitions // 2, "candidate": repetitions // 2},
            f"synthetic per-case AB/BA balance {case_id}",
        )
    weighted_reference_first = sum(
        case_weights[case_id] * counts["reference"]
        for case_id, counts in first_counts_by_case.items()
    )
    weighted_candidate_first = sum(
        case_weights[case_id] * counts["candidate"]
        for case_id, counts in first_counts_by_case.items()
    )
    require_exact(
        weighted_reference_first,
        weighted_candidate_first,
        "synthetic survey-weighted AB/BA balance",
    )
    require_exact(utf8_multibyte_seen, True, "synthetic multibyte UTF-8 coverage")
    reference_p95 = weighted_observed_quantile(observations["reference"], 95, 100)
    candidate_p95 = weighted_observed_quantile(observations["candidate"], 95, 100)
    if reference_p95 <= 0 or candidate_p95 * 4 > reference_p95 * 5:
        fail("synthetic latency p95 ratio exceeds 1.25")

    hardware = require_object(fixture.get("hardware"), "synthetic hardware")
    require_exact_keys(
        hardware,
        {
            "guard_policy",
            "guard_policy_sha256",
            "post_guard",
            "pre_guard",
            "profile",
            "profile_sha256",
        },
        "synthetic hardware",
    )
    profile = require_object(hardware.get("profile"), "synthetic hardware profile")
    require_exact_keys(
        profile,
        set(contract["latency"]["hardware_profile_required_fields"]),
        "synthetic hardware profile",
    )
    require_exact(
        hardware.get("profile_sha256"),
        sha256_bytes(compact_canonical_bytes(profile)),
        "synthetic hardware profile hash",
    )
    for key in [
        "affinity",
        "architecture",
        "cpu_model",
        "cpu_vendor",
        "filesystem",
        "host_slot",
        "kernel",
        "os",
        "power_governor",
        "python_version",
        "runtime_version",
    ]:
        if not isinstance(profile.get(key), str) or not profile[key]:
            fail("synthetic hardware string field invalid")
    for key in ["logical_cores", "memory_bytes", "physical_cores"]:
        require_int(profile.get(key), f"synthetic hardware {key}", minimum=1)
    if not isinstance(profile.get("smt_enabled"), bool):
        fail("synthetic SMT field must be boolean")
    if profile["physical_cores"] > profile["logical_cores"]:
        fail("synthetic physical cores exceed logical cores")
    if not profile["smt_enabled"] and profile["physical_cores"] != profile["logical_cores"]:
        fail("synthetic non-SMT physical/logical core shape mismatch")
    thread_environment = require_object(
        profile.get("thread_environment"), "synthetic thread environment"
    )
    if not thread_environment or not all(
        isinstance(key, str) and isinstance(value, str)
        for key, value in thread_environment.items()
    ):
        fail("synthetic thread environment invalid")
    policy = require_object(hardware.get("guard_policy"), "synthetic guard policy")
    require_exact_keys(
        policy,
        {
            "max_load1",
            "max_swap_used_bytes",
            "max_thermal_throttle_delta",
            "required_power_governor",
        },
        "synthetic guard policy",
    )
    require_exact(
        hardware.get("guard_policy_sha256"),
        sha256_bytes(compact_canonical_bytes(policy)),
        "synthetic guard policy hash",
    )
    max_load = require_finite_positive(policy.get("max_load1"), "synthetic max load")
    max_swap = require_int(policy.get("max_swap_used_bytes"), "synthetic max swap")
    max_thermal = require_int(
        policy.get("max_thermal_throttle_delta"), "synthetic max thermal delta"
    )
    required_governor = policy.get("required_power_governor")
    if not isinstance(required_governor, str) or not required_governor:
        fail("synthetic required governor invalid")
    guards: dict[str, dict[str, Any]] = {}
    for phase in ["pre_guard", "post_guard"]:
        guard = require_object(hardware.get(phase), f"synthetic {phase}")
        require_exact_keys(
            guard,
            set(contract["latency"]["hardware_guard_required_fields"]),
            f"synthetic {phase}",
        )
        load = guard.get("load1")
        if not isinstance(load, float) or not math.isfinite(load) or load < 0 or load > max_load:
            fail("synthetic hardware load guard failed")
        if require_int(guard.get("swap_used_bytes"), "synthetic swap") > max_swap:
            fail("synthetic hardware swap guard failed")
        require_sha256_value(
            guard.get("boot_session_sha256"), "synthetic boot session"
        )
        require_exact(guard.get("power_governor"), required_governor, "synthetic governor")
        require_int(guard.get("thermal_throttle_count"), "synthetic thermal count")
        guards[phase] = guard
    require_exact(
        guards["post_guard"]["boot_session_sha256"],
        guards["pre_guard"]["boot_session_sha256"],
        "synthetic boot-session continuity",
    )
    thermal_delta = (
        guards["post_guard"]["thermal_throttle_count"]
        - guards["pre_guard"]["thermal_throttle_count"]
    )
    if thermal_delta < 0 or thermal_delta > max_thermal:
        fail("synthetic thermal throttle guard failed")
    require_exact(profile.get("power_governor"), required_governor, "profile governor")

    source = require_object(fixture.get("canonical_source"), "synthetic canonical source")
    require_exact_keys(
        source,
        set(contract["storage"]["canonical_package_manifest_required_fields"]),
        "synthetic canonical source",
    )
    for key in ["package_sha256", "serializer_sha256", "memories_sha256", "edges_sha256"]:
        require_sha256_value(source.get(key), f"synthetic source {key}")
    require_exact(
        source.get("serialization_rule"),
        contract["storage"]["canonical_serialization_rule"],
        "synthetic serialization rule",
    )
    require_exact(
        source.get("memory_order"),
        contract["storage"]["canonical_memory_order"],
        "synthetic memory order",
    )
    require_exact(
        source.get("edge_order"),
        contract["storage"]["canonical_edge_order"],
        "synthetic edge order",
    )
    memory_bytes = require_int(source.get("memory_source_bytes"), "synthetic memory bytes", minimum=1)
    edge_bytes = require_int(source.get("edge_source_bytes"), "synthetic edge bytes", minimum=1)
    canonical_bytes = require_int(
        source.get("canonical_source_bytes"), "synthetic canonical bytes", minimum=1
    )
    if memory_bytes + edge_bytes != canonical_bytes:
        fail("synthetic canonical source byte denominator mismatch")
    require_int(source.get("memory_row_count"), "synthetic memory rows", minimum=1)
    require_int(source.get("edge_row_count"), "synthetic edge rows", minimum=1)
    source_core = {key: value for key, value in source.items() if key != "package_sha256"}
    require_exact(
        source.get("package_sha256"),
        sha256_bytes(compact_canonical_bytes(source_core)),
        "synthetic package hash",
    )

    arms_raw = fixture.get("storage_arms")
    if not isinstance(arms_raw, list) or len(arms_raw) != 2:
        fail("synthetic storage must contain two arms")
    arm_totals: dict[str, int] = {}
    arm_order: list[str] = []
    arm_page_sizes: dict[str, int] = {}
    arm_sqlite_versions: dict[str, str] = {}
    for arm_index, arm_value in enumerate(arms_raw):
        arm = require_object(arm_value, f"synthetic storage_arms[{arm_index}]")
        require_exact_keys(
            arm,
            set(contract["storage"]["arm_manifest_required_fields"]),
            f"synthetic storage_arms[{arm_index}]",
        )
        condition = arm.get("condition_id")
        if condition not in {"reference", "candidate"} or condition in arm_totals:
            fail("synthetic storage condition invalid or duplicate")
        arm_order.append(condition)
        require_sha256_value(arm.get("builder_sha256"), "synthetic arm builder")
        require_exact(
            arm.get("canonical_package_sha256"),
            source["package_sha256"],
            "synthetic storage package binding",
        )
        require_exact(arm.get("closed"), True, "synthetic closed storage")
        main_size = require_int(
            arm.get("main_sqlite_st_size"), "synthetic main sqlite bytes", minimum=1
        )
        page_size = require_int(arm.get("page_size"), "synthetic page size", minimum=1)
        if page_size not in contract["storage"]["sqlite_page_size_allowed_values"]:
            fail("synthetic SQLite page size outside allowed domain")
        page_count = require_int(arm.get("page_count"), "synthetic page count", minimum=1)
        if main_size != page_size * page_count:
            fail("synthetic main SQLite page accounting mismatch")
        freelist = require_int(arm.get("freelist_count"), "synthetic freelist")
        if freelist > page_count:
            fail("synthetic freelist exceeds page count")
        require_int(arm.get("user_version"), "synthetic user version")
        require_int(arm.get("schema_meta_version"), "synthetic schema_meta version", minimum=1)
        sqlite_version = arm.get("sqlite_version")
        if not isinstance(sqlite_version, str) or not sqlite_version:
            fail("synthetic SQLite version invalid")
        arm_page_sizes[condition] = page_size
        arm_sqlite_versions[condition] = sqlite_version
        require_sha256_value(arm.get("schema_digest_sha256"), "synthetic schema digest")
        require_exact(arm.get("quick_check"), "ok", "synthetic quick_check")
        artifacts = arm.get("artifacts")
        if not isinstance(artifacts, list) or not artifacts:
            fail("synthetic artifact manifest must be non-empty")
        artifact_paths: set[str] = set()
        artifact_total = 0
        main_artifact_sizes: list[int] = []
        for artifact_index, artifact_value in enumerate(artifacts):
            artifact = require_object(
                artifact_value, f"synthetic artifact[{artifact_index}]"
            )
            require_exact_keys(
                artifact,
                {"path", "role", "sha256", "st_size"},
                f"synthetic artifact[{artifact_index}]",
            )
            path = artifact.get("path")
            role = artifact.get("role")
            if not isinstance(path, str) or not path or path.startswith("/") or ".." in Path(path).parts:
                fail("synthetic artifact path invalid")
            if path in artifact_paths:
                fail("duplicate synthetic artifact path")
            artifact_paths.add(path)
            if not path.startswith(f"{condition}/"):
                fail("synthetic artifact path escapes condition directory")
            if any(path.endswith(suffix) for suffix in contract["storage"]["forbidden_artifact_suffixes"]):
                fail("synthetic forbidden storage sidecar")
            if role not in contract["storage"]["allowed_persistent_artifact_roles"]:
                fail("synthetic artifact role outside allowlist")
            require_sha256_value(artifact.get("sha256"), "synthetic artifact hash")
            size = require_int(artifact.get("st_size"), "synthetic artifact size", minimum=1)
            artifact_total += size
            if role == "main_sqlite":
                main_artifact_sizes.append(size)
        require_exact(main_artifact_sizes, [main_size], "synthetic main artifact")
        total = require_int(
            arm.get("total_persistent_condition_bytes"),
            "synthetic total persistent bytes",
            minimum=1,
        )
        if artifact_total != total:
            fail("synthetic persistent artifact byte total mismatch")
        normalized = require_object(
            arm.get("normalized_persistent_bytes"), "synthetic normalized bytes"
        )
        require_exact_keys(normalized, {"denominator", "numerator"}, "synthetic normalized bytes")
        require_exact(normalized.get("numerator"), total, "synthetic normalized numerator")
        require_exact(normalized.get("denominator"), canonical_bytes, "synthetic normalized denominator")
        arm_totals[condition] = total
    require_exact(arm_order, ["reference", "candidate"], "synthetic storage arm order")
    require_exact(
        len(set(arm_page_sizes.values())), 1, "synthetic cross-arm SQLite page size"
    )
    require_exact(
        len(set(arm_sqlite_versions.values())), 1, "synthetic cross-arm SQLite runtime"
    )
    reference_total = arm_totals["reference"]
    candidate_total = arm_totals["candidate"]
    if candidate_total * 10 > reference_total * 11:
        fail("synthetic storage ratio exceeds 1.10")

    return {
        "candidate_latency_p95_ns": candidate_p95,
        "candidate_storage_bytes": candidate_total,
        "context_identity_count": len(context_identity),
        "fractional_sampling_weight_count": sum(
            weight.denominator != 1 for weight in case_weights.values()
        ),
        "hardware_guard_pass": True,
        "latency_pair_count": len(expected_pairs),
        "latency_unit_count": unit_rows,
        "reference_latency_p95_ns": reference_p95,
        "reference_storage_bytes": reference_total,
        "sampling_receipt_sha256": sampling_receipt_sha256,
        "sampling_reserve_count": sampling_reserve_count,
        "sampling_selected_count": sampling_selected_count,
        "sqlite_cross_arm_identity_pass": True,
        "storage_ratio_pass": True,
        "utf8_multibyte_pass": utf8_multibyte_seen,
        "within_case_order_balance_pass": True,
        "weighted_first_position_mass_denominator": weighted_reference_first.denominator,
        "weighted_first_position_mass_numerator": weighted_reference_first.numerator,
        "weighted_latency_ratio_pass": True,
    }


def set_path(value: dict[str, Any], path: tuple[Any, ...], replacement: Any) -> None:
    cursor: Any = value
    for component in path[:-1]:
        cursor = cursor[component]
    cursor[path[-1]] = replacement


def run_contract_self_test(contract: dict[str, Any]) -> int:
    mutations: list[tuple[str, Callable[[dict[str, Any]], None]]] = [
        ("admission-status", lambda x: set_path(x, ("admission", "status"), "READY")),
        ("real-run", lambda x: set_path(x, ("admission", "real_run_admitted"), True)),
        ("capture", lambda x: set_path(x, ("admission", "capture_allowed"), True)),
        ("authority", lambda x: set_path(x, ("authority", "scientific_claim"), True)),
        ("blocker-drop", lambda x: x["blockers"].pop()),
        ("adapter-allow", lambda x: set_path(x, ("candidate_condition", "adapter", "adapter_allowed"), True)),
        ("adapter-gap", lambda x: x["candidate_condition"]["adapter"]["minimum_static_gaps"].pop()),
        ("candidate-builder", lambda x: set_path(x, ("candidate_condition", "candidate_context_builder_sha256"), "0" * 64)),
        ("legacy-builder", lambda x: set_path(x, ("context_and_result", "legacy_builder_admissible"), True)),
        ("legacy-data", lambda x: set_path(x, ("data_quality", "old_successor_v3_data_admissible_as_confirmatory"), True)),
        ("legacy-case", lambda x: set_path(x, ("legacy_precedent", "consumed_sealed_cases_reusable"), True)),
        ("clock", lambda x: set_path(x, ("reference_condition", "fixed_as_of_utc"), "2026-07-17T00:00:00Z")),
        ("parent-env", lambda x: set_path(x, ("reference_condition", "ambient_inputs", "inherit_parent_environment"), True)),
        ("seed-boost", lambda x: set_path(x, ("reference_condition", "ambient_inputs", "required_effective_environment", "AGENT_BRIDGE_SEED_BOOST_DISABLE"), "0")),
        ("rrf", lambda x: set_path(x, ("reference_condition", "request", "rrf_k"), 59.0)),
        ("graph-seed-cap", lambda x: set_path(x, ("reference_condition", "internal_budget_observation", "graph_expansion_seed_cap"), 9)),
        ("fanout", lambda x: set_path(x, ("reference_condition", "internal_budget_observation", "graph_neighbor_fanout"), 100)),
        ("old-cases", lambda x: set_path(x, ("sampling", "old_successor_v3_cases_allowed"), True)),
        ("sampling-ready", lambda x: set_path(x, ("sampling", "status"), "READY")),
        ("review-pool", lambda x: set_path(x, ("review_and_blinding", "pooled_reviewer_rescue_allowed"), True)),
        ("old-roster", lambda x: set_path(x, ("review_and_blinding", "old_reviewer_roster_reusable_without_refreeze"), True)),
        ("power-unit", lambda x: set_path(x, ("power_and_estimator", "statistical_unit"), "REVIEWER_ROW")),
        ("challenge", lambda x: set_path(x, ("power_and_estimator", "challenge_population_confirmatory"), True)),
        ("latency-reps", lambda x: set_path(x, ("latency", "measured_repetitions_per_case_condition"), 8)),
        ("latency-drop", lambda x: set_path(x, ("latency", "dropped_timeout_or_error_units_allowed"), True)),
        ("storage-wal", lambda x: set_path(x, ("storage", "wal_or_shm_allowed_at_measurement"), True)),
        ("strict-unsupported", lambda x: set_path(x, ("strict_case_pass", "unsupported_assertion_count_max"), 1)),
        ("public-runtime", lambda x: set_path(x, ("public_fixture", "runtime_execution"), True)),
        ("source-hash", lambda x: set_path(x, ("source_bindings", 0, "sha256"), "0" * 64)),
        ("date-gate", lambda x: set_path(x, ("earliest_post_fix_capture_date",), "2026-07-13")),
        ("unknown-field", lambda x: x["latency"].update({"raw_query": "private"})),
        ("numeric-type", lambda x: set_path(x, ("context_and_result", "context_token_ratio_max"), 1)),
        ("source-order", lambda x: x["source_bindings"].reverse()),
        ("gap-order", lambda x: x["candidate_condition"]["adapter"]["minimum_static_gaps"].reverse()),
        ("stage-order", lambda x: set_path(x, ("admission", "unblock_rule"), "ALL_BEFORE_OUTPUT")),
        ("stage-advance", lambda x: set_path(x, ("stages", "post_generation_pre_review", "status"), "READY")),
        ("seed-separation", lambda x: set_path(x, ("sampling", "answer_blinding_seed_distinct_from_sampling_seed"), False)),
        ("sampling-domain", lambda x: set_path(x, ("sampling", "sampling_selection_domain"), "wrong-domain")),
        ("sampling-receipt-order", lambda x: set_path(x, ("sampling", "sampling_receipt_must_precede_condition_output"), False)),
        ("sampling-receipt-binding", lambda x: x["sampling"]["sampling_receipt_required_bindings"].pop()),
        ("sampling-seed-shopping", lambda x: set_path(x, ("sampling", "sampling_seed_anti_shopping_protocol"), "CALLER_CHOOSES_SEED")),
        ("sampling-seed-timing", lambda x: set_path(x, ("sampling", "sampling_seed_timing"), "SEED_THEN_FRAME")),
        ("map-private", lambda x: set_path(x, ("review_and_blinding", "condition_map_private"), False)),
        ("map-identity", lambda x: x["review_and_blinding"]["map_identity_required_bindings"].pop()),
        ("score-order", lambda x: set_path(x, ("review_and_blinding", "score_order"), "UNBLIND_THEN_CLAIM")),
        ("reviewer-and", lambda x: set_path(x, ("review_and_blinding", "reviewer_case_rule"), "POOLED_MEAN")),
        ("strict-sources", lambda x: x["strict_case_pass"]["field_sources"]["each_reviewer_answer_gates"].pop()),
        ("strict-missingness", lambda x: set_path(x, ("strict_case_pass", "missingness_disposition", "missing_or_invalid_review"), "DROP")),
        ("truth-binding", lambda x: set_path(x, ("truth_inputs", "truth_authority_manifest_sha256"), "0" * 64)),
        ("generation-map-read", lambda x: set_path(x, ("generation", "private_map_read_allowed"), True)),
        ("latency-weighting", lambda x: set_path(x, ("latency", "aggregation_weighting"), "EQUAL_SAMPLE_ROWS")),
        ("latency-assignment", lambda x: set_path(x, ("latency", "condition_assignment_rule"), "GLOBAL_HALF")),
        ("latency-domain-independence", lambda x: set_path(x, ("latency", "execution_order_independent_from_condition_assignment"), False)),
        ("warmup-clone", lambda x: set_path(x, ("latency", "cache_mode"), "WARMUP_AND_TIME_SAME_CLONE")),
        ("hardware-shape", lambda x: x["latency"]["hardware_profile_required_fields"].pop()),
        ("storage-shape", lambda x: x["storage"]["arm_manifest_required_fields"].pop()),
        ("storage-role-allowlist", lambda x: x["storage"]["allowed_persistent_artifact_roles"].append("wal")),
        ("storage-page-domain", lambda x: x["storage"]["sqlite_page_size_allowed_values"].append(1)),
        ("storage-directory-scan", lambda x: set_path(x, ("storage", "directory_scan_required"), False)),
        ("synthetic-binding", lambda x: set_path(x, ("public_fixture", "synthetic_fixture_sha256"), "0" * 64)),
        ("primary-n-rule", lambda x: set_path(x, ("power_and_estimator", "required_primary_case_count_rule"), "24_INCLUDING_CHALLENGE")),
    ]
    rejected = 0
    for label, mutate in mutations:
        trial = copy.deepcopy(contract)
        mutate(trial)
        try:
            validate_contract(trial, None)
        except AdmissionError:
            rejected += 1
        else:
            fail(f"self-test mutation accepted: {label}")
    return rejected


def replace_synthetic_context(
    fixture: dict[str, Any], case_id: str, condition: str, text: str
) -> None:
    raw = text.encode("utf-8")
    for unit in fixture["latency_units"]:
        if unit["case_id"] != case_id:
            continue
        row = unit["conditions"][condition]
        row["result_text"] = text
        row["result_sha256"] = sha256_bytes(raw)
        row["result_bytes"] = len(raw)
        row["context_tokens"] = len(text.split())


def replace_one_synthetic_context(
    fixture: dict[str, Any], unit_index: int, condition: str, text: str
) -> None:
    raw = text.encode("utf-8")
    row = fixture["latency_units"][unit_index]["conditions"][condition]
    row["result_text"] = text
    row["result_sha256"] = sha256_bytes(raw)
    row["result_bytes"] = len(raw)
    row["context_tokens"] = len(text.split())


def inflate_synthetic_candidate_latency(fixture: dict[str, Any], latency_ns: int) -> None:
    for unit in fixture["latency_units"]:
        if unit["case_id"] != "public_synth_d":
            continue
        row = unit["conditions"]["candidate"]
        row["latency_ns"] = latency_ns
        row["retrieval_wire_ns"] = latency_ns - row["assembly_ns"]


def inflate_synthetic_storage(fixture: dict[str, Any], aux_bytes: int) -> None:
    candidate = fixture["storage_arms"][1]
    candidate["artifacts"][1]["st_size"] = aux_bytes
    total = candidate["main_sqlite_st_size"] + aux_bytes
    candidate["total_persistent_condition_bytes"] = total
    candidate["normalized_persistent_bytes"]["numerator"] = total


def rebind_synthetic_profile_field(
    fixture: dict[str, Any], field: str, value: Any
) -> None:
    profile = fixture["hardware"]["profile"]
    profile[field] = value
    fixture["hardware"]["profile_sha256"] = sha256_bytes(
        compact_canonical_bytes(profile)
    )


def remove_synthetic_multibyte_coverage(fixture: dict[str, Any]) -> None:
    replace_synthetic_context(
        fixture, "public_synth_c", "reference", "charlie reference stable context"
    )
    replace_synthetic_context(
        fixture, "public_synth_c", "candidate", "charlie current context"
    )


def add_rebound_forbidden_artifact(fixture: dict[str, Any]) -> None:
    candidate = fixture["storage_arms"][1]
    candidate["artifacts"].append(
        {
            "path": "candidate/wal.payload",
            "role": "wal",
            "sha256": sha256_bytes(b"public synthetic disguised WAL"),
            "st_size": 1,
        }
    )
    candidate["total_persistent_condition_bytes"] += 1
    candidate["normalized_persistent_bytes"]["numerator"] += 1


def set_rebound_invalid_page_size(fixture: dict[str, Any]) -> None:
    candidate = fixture["storage_arms"][1]
    candidate["page_size"] = 1
    candidate["page_count"] = candidate["main_sqlite_st_size"]


def rebind_globally_blocked_latency_schedule(fixture: dict[str, Any]) -> None:
    schedule = fixture["schedule"]
    seed = bytes.fromhex("03" * 32)
    schedule["seed_hex"] = seed.hex()
    schedule["seed_sha256"] = sha256_bytes(seed)
    domain = schedule["order_domain"].encode("utf-8")
    ranked: list[tuple[bytes, tuple[str, int]]] = []
    by_pair = {
        (unit["case_id"], unit["repetition"]): unit
        for unit in fixture["latency_units"]
    }
    for pair in by_pair:
        case_id, repetition = pair
        message = (
            domain
            + b"\0"
            + case_id.encode("utf-8")
            + b"\0"
            + str(repetition).encode("ascii")
        )
        ranked.append((hmac.new(seed, message, hashlib.sha256).digest(), pair))
    ranked.sort()
    rebound = []
    for index, (_, pair) in enumerate(ranked):
        unit = by_pair[pair]
        unit["ordinal"] = index + 1
        unit["first_condition"] = (
            "reference" if index < len(ranked) // 2 else "candidate"
        )
        rebound.append(unit)
    fixture["latency_units"] = rebound


def run_synthetic_self_test(
    fixture: dict[str, Any], contract: dict[str, Any]
) -> int:
    mutations: list[tuple[str, Callable[[dict[str, Any]], None]]] = [
        ("sampling-frame-hash", lambda x: set_path(x, ("sampling", "eligible_frame_sha256"), "0" * 64)),
        ("sampling-duplicate-event", lambda x: set_path(x, ("sampling", "eligible_frame", 1, "event_id"), x["sampling"]["eligible_frame"][0]["event_id"])),
        ("sampling-population", lambda x: set_path(x, ("sampling", "allocations", 1, "N_h"), 5)),
        ("sampling-allocation", lambda x: set_path(x, ("sampling", "allocations", 1, "n_h"), 2)),
        ("sampling-selected", lambda x: set_path(x, ("sampling", "selected_case_ids", 0), "public_reserve_807")),
        ("sampling-reserve-overlap", lambda x: set_path(x, ("sampling", "reserve_case_ids"), ["public_synth_d"])),
        ("sampling-weight", lambda x: set_path(x, ("cases", 1, "sampling_weight", "numerator"), 1)),
        ("sampling-weight-unreduced", lambda x: set_path(x, ("cases", 1, "sampling_weight"), {"denominator": 6, "numerator": 8})),
        ("sampling-inclusion-probability", lambda x: set_path(x, ("sampling", "case_inclusion_probabilities", 1, "numerator"), 1)),
        ("sampling-seed-commitment", lambda x: set_path(x, ("sampling", "seed_sha256"), "0" * 64)),
        ("sampling-seed-reuse", lambda x: set_path(x, ("sampling", "seed_hex"), x["schedule"]["seed_hex"])),
        ("sampling-message", lambda x: set_path(x, ("sampling", "message_format"), "wrong")),
        ("sampling-receipt-writer", lambda x: set_path(x, ("sampling", "receipt_writer_sha256"), "0" * 64)),
        ("sampling-receipt", lambda x: set_path(x, ("sampling", "sampling_receipt_sha256"), "0" * 64)),
        ("missing-pair", lambda x: x["latency_units"].pop()),
        ("duplicate-pair", lambda x: x["latency_units"].append(copy.deepcopy(x["latency_units"][0]))),
        ("ordinal", lambda x: set_path(x, ("latency_units", 0, "ordinal"), 99)),
        ("execution-array-order", lambda x: x["latency_units"].reverse()),
        ("condition-order", lambda x: set_path(x, ("latency_units", 0, "first_condition"), "wrong")),
        ("pair-count", lambda x: set_path(x, ("schedule", "pair_count"), 23)),
        ("seed-commitment", lambda x: set_path(x, ("schedule", "seed_sha256"), "0" * 64)),
        ("seed-reveal", lambda x: set_path(x, ("schedule", "seed_hex"), "22" * 32)),
        ("schedule-order-domain", lambda x: set_path(x, ("schedule", "order_domain"), "wrong")),
        ("schedule-assignment-domain", lambda x: set_path(x, ("schedule", "assignment_domain"), "wrong")),
        ("fully-rebound-globally-blocked-schedule", rebind_globally_blocked_latency_schedule),
        ("warmup-discard", lambda x: set_path(x, ("latency_units", 0, "sacrificial_warmup_discarded"), False)),
        ("timed-snapshot", lambda x: set_path(x, ("latency_units", 0, "timed_start_snapshot_sha256"), "0" * 64)),
        ("missing-condition", lambda x: x["latency_units"][0]["conditions"].pop("candidate")),
        ("unit-status", lambda x: set_path(x, ("latency_units", 0, "conditions", "reference", "status"), "timeout")),
        ("timeout", lambda x: set_path(x, ("latency_units", 0, "conditions", "reference", "latency_ns"), x["timeout_ns"])),
        ("latency-components", lambda x: set_path(x, ("latency_units", 0, "conditions", "reference", "assembly_ns"), 1)),
        ("result-bytes", lambda x: set_path(x, ("latency_units", 0, "conditions", "reference", "result_bytes"), 1)),
        ("result-hash", lambda x: set_path(x, ("latency_units", 0, "conditions", "reference", "result_sha256"), "0" * 64)),
        ("result-tokens", lambda x: set_path(x, ("latency_units", 0, "conditions", "reference", "context_tokens"), 99)),
        ("context-repeat", lambda x: replace_one_synthetic_context(x, 1, "reference", "changed but consistently rebound")),
        ("candidate-context-budget", lambda x: replace_synthetic_context(x, "public_synth_a", "candidate", "alpha candidate context deliberately longer than the stable reference context")),
        ("utf8-multibyte-coverage", remove_synthetic_multibyte_coverage),
        ("latency-ratio", lambda x: inflate_synthetic_candidate_latency(x, 400_000)),
        ("profile-hash", lambda x: set_path(x, ("hardware", "profile_sha256"), "0" * 64)),
        ("profile-field", lambda x: x["hardware"]["profile"].pop("affinity")),
        ("guard-policy-hash", lambda x: set_path(x, ("hardware", "guard_policy_sha256"), "0" * 64)),
        ("guard-load", lambda x: set_path(x, ("hardware", "post_guard", "load1"), 2.0)),
        ("guard-swap", lambda x: set_path(x, ("hardware", "post_guard", "swap_used_bytes"), 1)),
        ("guard-thermal", lambda x: set_path(x, ("hardware", "post_guard", "thermal_throttle_count"), 6)),
        ("guard-thermal-reset", lambda x: set_path(x, ("hardware", "post_guard", "thermal_throttle_count"), 4)),
        ("guard-boot-session", lambda x: set_path(x, ("hardware", "post_guard", "boot_session_sha256"), "0" * 64)),
        ("guard-governor", lambda x: set_path(x, ("hardware", "post_guard", "power_governor"), "powersave")),
        ("profile-core-shape", lambda x: rebind_synthetic_profile_field(x, "physical_cores", 99)),
        ("source-zero", lambda x: set_path(x, ("canonical_source", "canonical_source_bytes"), 0)),
        ("source-sum", lambda x: set_path(x, ("canonical_source", "canonical_source_bytes"), 10001)),
        ("package-hash", lambda x: set_path(x, ("canonical_source", "package_sha256"), "0" * 64)),
        ("serialization-rule", lambda x: set_path(x, ("canonical_source", "serialization_rule"), "DRIFT")),
        ("quick-check", lambda x: set_path(x, ("storage_arms", 0, "quick_check"), "corrupt")),
        ("builder-hash", lambda x: set_path(x, ("storage_arms", 0, "builder_sha256"), "not-a-hash")),
        ("schema-meta", lambda x: set_path(x, ("storage_arms", 0, "schema_meta_version"), 0)),
        ("wal-sidecar", lambda x: x["storage_arms"][0]["artifacts"].append({"path":"reference/state.db-wal","role":"wal","sha256":"0"*64,"st_size":1})),
        ("rebound-forbidden-role", add_rebound_forbidden_artifact),
        ("sqlite-page-size-domain", set_rebound_invalid_page_size),
        ("sqlite-runtime-drift", lambda x: set_path(x, ("storage_arms", 1, "sqlite_version"), "different-runtime")),
        ("page-accounting", lambda x: set_path(x, ("storage_arms", 0, "page_count"), 9)),
        ("artifact-total", lambda x: set_path(x, ("storage_arms", 0, "total_persistent_condition_bytes"), 1)),
        ("normalized-denominator", lambda x: set_path(x, ("storage_arms", 0, "normalized_persistent_bytes", "denominator"), 9999)),
        ("storage-ratio", lambda x: inflate_synthetic_storage(x, 10_000)),
        ("duplicate-artifact", lambda x: x["storage_arms"][1]["artifacts"].append(copy.deepcopy(x["storage_arms"][1]["artifacts"][0]))),
        ("duplicate-arm", lambda x: set_path(x, ("storage_arms", 1, "condition_id"), "reference")),
        ("nested-bool-int", lambda x: set_path(x, ("latency_units", 0, "conditions", "reference", "result_bytes"), False)),
        ("nested-int-float", lambda x: set_path(x, ("latency_units", 0, "conditions", "reference", "latency_ns"), 100100.0)),
    ]
    rejected = 0
    for label, mutate in mutations:
        trial = copy.deepcopy(fixture)
        mutate(trial)
        try:
            validate_synthetic_fixture(trial, contract)
        except AdmissionError:
            rejected += 1
        else:
            fail(f"synthetic self-test mutation accepted: {label}")
    return rejected


def count_unset(value: Any) -> int:
    if isinstance(value, dict):
        return sum(count_unset(child) for child in value.values())
    if isinstance(value, list):
        return sum(count_unset(child) for child in value)
    return int(value == UNSET)


def render_receipt(
    contract: dict[str, Any],
    raw: bytes,
    synthetic_raw: bytes,
    synthetic_metrics: dict[str, Any],
) -> str:
    rows = [
        ("schema", SCHEMA),
        ("contract_sha256", hashlib.sha256(raw).hexdigest()),
        ("synthetic_fixture_sha256", hashlib.sha256(synthetic_raw).hexdigest()),
        ("decision", contract["admission"]["status"]),
        ("real_run_admitted", str(contract["admission"]["real_run_admitted"]).lower()),
        ("capture_allowed", str(contract["admission"]["capture_allowed"]).lower()),
        ("reference_status", contract["reference_condition"]["status"]),
        ("candidate_status", contract["candidate_condition"]["adapter"]["status"]),
        ("candidate_adapter_allowed", str(contract["candidate_condition"]["adapter"]["adapter_allowed"]).lower()),
        ("candidate_minimum_gap_count", len(contract["candidate_condition"]["adapter"]["minimum_static_gaps"])),
        ("sampling_status", contract["sampling"]["status"]),
        ("latency_status", contract["latency"]["status"]),
        ("storage_status", contract["storage"]["status"]),
        ("synthetic_sampling_selected_count", synthetic_metrics["sampling_selected_count"]),
        ("synthetic_sampling_reserve_count", synthetic_metrics["sampling_reserve_count"]),
        ("synthetic_sampling_receipt_sha256", synthetic_metrics["sampling_receipt_sha256"]),
        ("synthetic_fractional_sampling_weight_count", synthetic_metrics["fractional_sampling_weight_count"]),
        ("synthetic_latency_pair_count", synthetic_metrics["latency_pair_count"]),
        ("synthetic_latency_unit_count", synthetic_metrics["latency_unit_count"]),
        ("synthetic_within_case_order_balance_pass", str(synthetic_metrics["within_case_order_balance_pass"]).lower()),
        ("synthetic_weighted_first_position_mass", f'{synthetic_metrics["weighted_first_position_mass_numerator"]}/{synthetic_metrics["weighted_first_position_mass_denominator"]}'),
        ("synthetic_reference_p95_ns", synthetic_metrics["reference_latency_p95_ns"]),
        ("synthetic_candidate_p95_ns", synthetic_metrics["candidate_latency_p95_ns"]),
        ("synthetic_weighted_latency_ratio_pass", str(synthetic_metrics["weighted_latency_ratio_pass"]).lower()),
        ("synthetic_context_identity_count", synthetic_metrics["context_identity_count"]),
        ("synthetic_utf8_multibyte_pass", str(synthetic_metrics["utf8_multibyte_pass"]).lower()),
        ("synthetic_hardware_guard_pass", str(synthetic_metrics["hardware_guard_pass"]).lower()),
        ("synthetic_reference_storage_bytes", synthetic_metrics["reference_storage_bytes"]),
        ("synthetic_candidate_storage_bytes", synthetic_metrics["candidate_storage_bytes"]),
        ("synthetic_sqlite_cross_arm_identity_pass", str(synthetic_metrics["sqlite_cross_arm_identity_pass"]).lower()),
        ("synthetic_storage_ratio_pass", str(synthetic_metrics["storage_ratio_pass"]).lower()),
        ("blocker_count", len(contract["blockers"])),
        ("source_binding_count", len(contract["source_bindings"])),
        ("unset_binding_count", count_unset(contract)),
        ("legacy_consumed_case_count", contract["legacy_precedent"]["consumed_case_count"]),
        ("measured_repetitions_per_case_condition", contract["latency"]["measured_repetitions_per_case_condition"]),
        ("public_runtime_execution", str(contract["public_fixture"]["runtime_execution"]).lower()),
        ("scientific_claim_authority", str(contract["authority"]["scientific_claim"]).lower()),
        ("earliest_post_fix_capture_date", contract["earliest_post_fix_capture_date"]),
    ]
    return "".join(f"{key}\t{value}\n" for key, value in rows)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--self-test", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = args.root.resolve()
    contract_path = root / CONTRACT_PATH
    synthetic_path = root / SYNTHETIC_PATH
    try:
        contract, raw = read_strict_json(contract_path, "contract")
        synthetic, synthetic_raw = read_strict_json(synthetic_path, "synthetic fixture")
        validate_contract(contract, root)
        require_exact(
            sha256_bytes(synthetic_raw),
            contract["public_fixture"]["synthetic_fixture_sha256"],
            "synthetic fixture byte binding",
        )
        synthetic_metrics = validate_synthetic_fixture(synthetic, contract)
        if args.self_test:
            contract_rejected = run_contract_self_test(contract)
            synthetic_rejected = run_synthetic_self_test(synthetic, contract)
            print(
                "SELF_TEST_OK"
                f"\tcontract_mutations_rejected={contract_rejected}"
                f"\tsynthetic_mutations_rejected={synthetic_rejected}"
                f"\ttotal_mutations_rejected={contract_rejected + synthetic_rejected}"
            )
        else:
            sys.stdout.write(
                render_receipt(contract, raw, synthetic_raw, synthetic_metrics)
            )
    except AdmissionError as exc:
        print(f"track-b admission check failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
