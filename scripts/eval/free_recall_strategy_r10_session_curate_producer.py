#!/usr/bin/env python3
"""Public-synthetic validator for the R10 session_curate producer contract."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable


SCHEMA = "agent_bridge.free_recall_strategy_r10_plan.v0"
AUTHORITY_FIELDS = {
    "rust_source", "sql_source", "cargo_feature", "database_access", "build",
    "execution", "private_state_test", "real_capture", "producer_integration",
    "runtime_enablement", "production_key_custody", "retrieval_change",
    "sync_export_change", "mcp_api_change", "merge", "release", "deployment",
}


def canonical_plan() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA,
        "producer": {
            "seams": ["session_curate:curation_batch"],
            "open": "after_auxiliary_scan_immediately_before_candidate_loop",
            "item": "only_after_memory_save_success",
            "position": "zero_based_successful_memory_save_ordinal",
            "close": "after_loop_if_positive_all_saved_items_observed",
            "empty_candidates_emit": False,
            "zero_success_close": False,
        },
        "candidate_ledger": {
            "outcomes": ["saved", "duplicate", "lookup_error", "save_error"],
            "auxiliary_errors_separate": True,
            "duplicate_count": "explicit_duplicate_outcomes",
            "candidate_error_count": "lookup_plus_save_errors",
            "subtraction_from_mixed_errors": False,
        },
        "dependency": {
            "kind": "optional_hub_curation_batch_observation_capability",
            "default_present": False,
            "widens_state_store": False,
            "downcasts_state_store": False,
            "opens_second_sqlite_connection": False,
            "direct_sqlite_dependency": False,
            "mcp_or_public_surface": False,
            "retrieval_or_sync_surface": False,
            "capability_owns_identity_ref_hash_and_sink": True,
            "raw_key_use": "transient_just_saved_key_inside_trusted_capability",
        },
        "activation": {
            "compile_support_default_on": False,
            "runtime_default_on": False,
            "requires_compile_support": True,
            "requires_runtime_enablement": True,
            "requires_trusted_key_provider": True,
            "requires_injected_sink": True,
            "missing_gate_behavior": "abstain_no_events",
            "dry_run_events": 0,
            "no_store_events": 0,
            "production_ids_or_secrets": False,
        },
        "failure": {
            "core_curation": "continues_unchanged",
            "observation": "first_failure_latches_and_suppresses_later_calls_and_close",
            "begin_failure_aborts_core": False,
            "item_failure_rolls_back_memory": False,
            "sidecar_error_enters_candidate_ledger": False,
            "incomplete_projection": "abstain",
            "public_response_change": False,
        },
        "slices": {
            "c1": "bridge_orchestration_fake_capability_no_sidecar_io",
            "c2": "separately_gated_store_capability_key_custody_and_runtime_wiring",
            "c2_open": False,
        },
        "authority": {name: False for name in sorted(AUTHORITY_FIELDS)},
        "next_gate": "r11_c1_source_requires_owner_authorization",
    }


def canonical_digest(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def validate(plan: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if plan.get("schema_version") != SCHEMA:
        errors.append("unsupported_schema")

    producer = plan.get("producer", {})
    if producer.get("seams") != ["session_curate:curation_batch"]:
        errors.append("producer_scope_widened")
    if producer.get("open") != "after_auxiliary_scan_immediately_before_candidate_loop":
        errors.append("open_order_drift")
    if producer.get("item") != "only_after_memory_save_success":
        errors.append("item_before_save")
    if producer.get("position") != "zero_based_successful_memory_save_ordinal":
        errors.append("position_semantics_drift")
    if producer.get("close") != "after_loop_if_positive_all_saved_items_observed":
        errors.append("close_not_fail_closed")
    if producer.get("empty_candidates_emit") is not False:
        errors.append("empty_batch_emits")
    if producer.get("zero_success_close") is not False:
        errors.append("zero_success_finalized")

    ledger = plan.get("candidate_ledger", {})
    if ledger.get("outcomes") != ["saved", "duplicate", "lookup_error", "save_error"]:
        errors.append("candidate_ledger_drift")
    if ledger.get("auxiliary_errors_separate") is not True:
        errors.append("auxiliary_error_blended")
    if ledger.get("duplicate_count") != "explicit_duplicate_outcomes":
        errors.append("duplicate_count_inferred")
    if ledger.get("candidate_error_count") != "lookup_plus_save_errors":
        errors.append("candidate_error_count_drift")
    if ledger.get("subtraction_from_mixed_errors") is not False:
        errors.append("mixed_error_subtraction")

    dependency = plan.get("dependency", {})
    if dependency.get("kind") != "optional_hub_curation_batch_observation_capability":
        errors.append("dependency_boundary_drift")
    if dependency.get("default_present") is not False:
        errors.append("dependency_default_on")
    for key in ("widens_state_store", "downcasts_state_store", "opens_second_sqlite_connection", "direct_sqlite_dependency", "mcp_or_public_surface", "retrieval_or_sync_surface"):
        if dependency.get(key) is not False:
            errors.append("dependency_boundary_widened")
    if dependency.get("capability_owns_identity_ref_hash_and_sink") is not True:
        errors.append("capability_ownership_weakened")
    if dependency.get("raw_key_use") != "transient_just_saved_key_inside_trusted_capability":
        errors.append("raw_key_boundary_widened")

    activation = plan.get("activation", {})
    for key in ("compile_support_default_on", "runtime_default_on", "production_ids_or_secrets"):
        if activation.get(key) is not False:
            errors.append("activation_default_off_weakened")
    for key in ("requires_compile_support", "requires_runtime_enablement", "requires_trusted_key_provider", "requires_injected_sink"):
        if activation.get(key) is not True:
            errors.append("activation_gate_missing")
    if activation.get("missing_gate_behavior") != "abstain_no_events":
        errors.append("missing_gate_fallback")
    if activation.get("dry_run_events") != 0 or activation.get("no_store_events") != 0:
        errors.append("non_write_path_emits")

    failure = plan.get("failure", {})
    if failure.get("core_curation") != "continues_unchanged":
        errors.append("core_behavior_coupled")
    if failure.get("observation") != "first_failure_latches_and_suppresses_later_calls_and_close":
        errors.append("failure_latch_missing")
    for key in ("begin_failure_aborts_core", "item_failure_rolls_back_memory", "sidecar_error_enters_candidate_ledger", "public_response_change"):
        if failure.get(key) is not False:
            errors.append("observation_changes_core")
    if failure.get("incomplete_projection") != "abstain":
        errors.append("incomplete_projection_leaks")

    slices = plan.get("slices", {})
    if slices.get("c1") != "bridge_orchestration_fake_capability_no_sidecar_io":
        errors.append("c1_scope_widened")
    if slices.get("c2") != "separately_gated_store_capability_key_custody_and_runtime_wiring" or slices.get("c2_open") is not False:
        errors.append("c2_opened_early")

    authority = plan.get("authority")
    if not isinstance(authority, dict) or set(authority) != AUTHORITY_FIELDS:
        errors.append("authority_set_mismatch")
    elif any(authority.values()):
        errors.append("authority_enabled")
    if plan.get("next_gate") != "r11_c1_source_requires_owner_authorization":
        errors.append("next_gate_widened")
    return sorted(set(errors))


@dataclass(frozen=True)
class TraceCase:
    name: str
    outcomes: tuple[str, ...]
    dry_run: bool = False
    has_store: bool = True
    gate_ready: bool = True
    begin_fails: bool = False
    item_failure_ordinal: int | None = None
    close_fails: bool = False
    auxiliary_errors: int = 0


def simulate(case: TraceCase) -> dict[str, Any]:
    valid = {"saved", "duplicate", "lookup_error", "save_error"}
    if not set(case.outcomes).issubset(valid):
        raise ValueError("unsupported synthetic outcome")
    counts = {name: case.outcomes.count(name) for name in sorted(valid)}
    candidate_errors = counts["lookup_error"] + counts["save_error"]
    events: list[str] = []
    compromised = False
    observed = 0

    active = (
        not case.dry_run
        and case.has_store
        and case.gate_ready
        and bool(case.outcomes)
    )
    if active and not case.begin_fails:
        events.append("open")
        saved_ordinal = 0
        for outcome in case.outcomes:
            if outcome != "saved":
                continue
            if not compromised:
                if case.item_failure_ordinal == saved_ordinal:
                    compromised = True
                else:
                    events.append(f"item:{saved_ordinal}")
                    observed += 1
            saved_ordinal += 1
        if counts["saved"] > 0 and not compromised and observed == counts["saved"]:
            if not case.close_fails:
                events.append(f"close:{observed}")

    finalized = bool(events) and events[-1].startswith("close:")
    return {
        "name": case.name,
        "events": events,
        "finalized": finalized,
        "candidate_count": len(case.outcomes),
        "saved_count": counts["saved"],
        "skipped_duplicates": counts["duplicate"],
        "candidate_error_count": candidate_errors,
        "auxiliary_error_count": case.auxiliary_errors,
        "public_error_count": candidate_errors + case.auxiliary_errors,
        "core_outcomes_preserved": list(case.outcomes),
    }


def trace_cases() -> list[TraceCase]:
    return [
        TraceCase("dry_run", ("saved",), dry_run=True),
        TraceCase("no_store", ("saved",), has_store=False),
        TraceCase("missing_gate", ("saved",), gate_ready=False),
        TraceCase("empty", ()),
        TraceCase("all_duplicates", ("duplicate", "duplicate")),
        TraceCase("mixed", ("saved", "duplicate", "lookup_error", "saved", "save_error"), auxiliary_errors=1),
        TraceCase("begin_failure", ("saved", "saved"), begin_fails=True),
        TraceCase("first_item_failure", ("saved", "saved"), item_failure_ordinal=0),
        TraceCase("later_item_failure", ("saved", "duplicate", "saved", "saved"), item_failure_ordinal=1),
        TraceCase("close_failure", ("saved",), close_fails=True),
        TraceCase("auxiliary_only", (), auxiliary_errors=2),
    ]


def validate_traces(rows: list[dict[str, Any]]) -> list[str]:
    by_name = {row["name"]: row for row in rows}
    errors: list[str] = []
    for name in ("dry_run", "no_store", "missing_gate", "empty", "auxiliary_only"):
        if by_name[name]["events"]:
            errors.append(f"{name}_emitted")
    if by_name["all_duplicates"]["events"] != ["open"] or by_name["all_duplicates"]["finalized"]:
        errors.append("all_duplicates_finalized")
    mixed = by_name["mixed"]
    if mixed["events"] != ["open", "item:0", "item:1", "close:2"]:
        errors.append("mixed_trace_order")
    if (mixed["skipped_duplicates"], mixed["candidate_error_count"], mixed["auxiliary_error_count"], mixed["public_error_count"]) != (1, 2, 1, 3):
        errors.append("mixed_ledger_wrong")
    if by_name["begin_failure"]["events"] or by_name["begin_failure"]["core_outcomes_preserved"] != ["saved", "saved"]:
        errors.append("begin_failure_changed_core")
    if by_name["first_item_failure"]["events"] != ["open"]:
        errors.append("first_item_failure_not_latched")
    if by_name["later_item_failure"]["events"] != ["open", "item:0"]:
        errors.append("later_item_failure_not_latched")
    if by_name["close_failure"]["events"] != ["open", "item:0"] or by_name["close_failure"]["finalized"]:
        errors.append("close_failure_finalized")
    if by_name["auxiliary_only"]["skipped_duplicates"] != 0:
        errors.append("auxiliary_error_corrupted_count")
    return sorted(set(errors))


def set_path(value: dict[str, Any], path: tuple[str, ...], replacement: Any) -> None:
    cursor = value
    for part in path[:-1]:
        cursor = cursor[part]
    cursor[path[-1]] = replacement


def mutations() -> list[tuple[str, str, Callable[[dict[str, Any]], None]]]:
    rows: list[tuple[str, str, Callable[[dict[str, Any]], None]]] = []
    for authority in sorted(AUTHORITY_FIELDS):
        rows.append((f"authorize_{authority}", "authority_enabled", lambda p, a=authority: set_path(p, ("authority", a), True)))
    rows.extend([
        ("add_memory_save_producer", "producer_scope_widened", lambda p: p["producer"]["seams"].append("memory_save:inferred_session")),
        ("open_before_aux_scan", "open_order_drift", lambda p: set_path(p, ("producer", "open"), "before_auxiliary_scan")),
        ("item_before_save", "item_before_save", lambda p: set_path(p, ("producer", "item"), "before_memory_save")),
        ("candidate_index_position", "position_semantics_drift", lambda p: set_path(p, ("producer", "position"), "candidate_index")),
        ("close_zero_success", "zero_success_finalized", lambda p: set_path(p, ("producer", "zero_success_close"), True)),
        ("close_on_partial_observation", "close_not_fail_closed", lambda p: set_path(p, ("producer", "close"), "after_loop_if_any_item_observed")),
        ("blend_aux_errors", "auxiliary_error_blended", lambda p: set_path(p, ("candidate_ledger", "auxiliary_errors_separate"), False)),
        ("subtract_mixed_errors", "mixed_error_subtraction", lambda p: set_path(p, ("candidate_ledger", "subtraction_from_mixed_errors"), True)),
        ("widen_state_store", "dependency_boundary_widened", lambda p: set_path(p, ("dependency", "widens_state_store"), True)),
        ("downcast_store", "dependency_boundary_widened", lambda p: set_path(p, ("dependency", "downcasts_state_store"), True)),
        ("open_second_sqlite", "dependency_boundary_widened", lambda p: set_path(p, ("dependency", "opens_second_sqlite_connection"), True)),
        ("add_mcp_surface", "dependency_boundary_widened", lambda p: set_path(p, ("dependency", "mcp_or_public_surface"), True)),
        ("raw_key_in_report", "raw_key_boundary_widened", lambda p: set_path(p, ("dependency", "raw_key_use"), "persisted_in_public_report")),
        ("compile_default_on", "activation_default_off_weakened", lambda p: set_path(p, ("activation", "compile_support_default_on"), True)),
        ("runtime_default_on", "activation_default_off_weakened", lambda p: set_path(p, ("activation", "runtime_default_on"), True)),
        ("fallback_without_key", "activation_gate_missing", lambda p: set_path(p, ("activation", "requires_trusted_key_provider"), False)),
        ("dry_run_emits", "non_write_path_emits", lambda p: set_path(p, ("activation", "dry_run_events"), 1)),
        ("production_env_secret", "activation_default_off_weakened", lambda p: set_path(p, ("activation", "production_ids_or_secrets"), True)),
        ("sidecar_aborts_core", "observation_changes_core", lambda p: set_path(p, ("failure", "begin_failure_aborts_core"), True)),
        ("sidecar_rolls_back_memory", "observation_changes_core", lambda p: set_path(p, ("failure", "item_failure_rolls_back_memory"), True)),
        ("sidecar_error_public", "observation_changes_core", lambda p: set_path(p, ("failure", "public_response_change"), True)),
        ("continue_after_item_failure", "failure_latch_missing", lambda p: set_path(p, ("failure", "observation"), "continue_and_close_partial")),
        ("project_incomplete", "incomplete_projection_leaks", lambda p: set_path(p, ("failure", "incomplete_projection"), "partial_items")),
        ("open_c2", "c2_opened_early", lambda p: set_path(p, ("slices", "c2_open"), True)),
        ("widen_next_gate", "next_gate_widened", lambda p: set_path(p, ("next_gate",), "implement_integrate_build_run")),
    ])
    return rows


def run() -> dict[str, Any]:
    plan = canonical_plan()
    canonical_errors = validate(plan)
    mutation_rows = []
    for name, expected, mutate in mutations():
        candidate = copy.deepcopy(plan)
        mutate(candidate)
        mutation_rows.append({
            "name": name,
            "expected_error": expected,
            "rejected_as_expected": expected in validate(candidate),
        })
    traces = [simulate(case) for case in trace_cases()]
    trace_errors = validate_traces(traces)
    reversed_plan = {key: plan[key] for key in reversed(list(plan))}
    gates = {
        "canonical_plan": not canonical_errors,
        "public_synthetic_traces": not trace_errors,
        "directed_mutations": all(row["rejected_as_expected"] for row in mutation_rows),
        "key_order_invariant": canonical_digest(plan) == canonical_digest(reversed_plan),
        "zero_authority": not canonical_errors,
    }
    return {
        "schema_version": "agent_bridge.free_recall_strategy_r10_report.v0",
        "fixture": "public_synthetic_session_curate_producer",
        "canonical_plan_sha256": canonical_digest(plan),
        "canonical_error_count": len(canonical_errors),
        "trace_error_count": len(trace_errors),
        "trace_case_count": len(traces),
        "mutation_count": len(mutation_rows),
        "mutation_rejection_count": sum(row["rejected_as_expected"] for row in mutation_rows),
        "gates": gates,
        "verdict": "PASS" if all(gates.values()) else "FAIL",
        "traces": traces,
        "mutations": mutation_rows,
        "authority": {
            "r11_c1_source_eligible": all(gates.values()),
            "source_implemented": False,
            "build_authorized": False,
            "execution_authorized": False,
            "database_used": False,
            "producer_integrated": False,
            "c2_open": False,
            "merge_authorized": False,
            "deployment_authorized": False,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path)
    parser.add_argument("--selftest", action="store_true")
    args = parser.parse_args()
    report = run()
    encoded = json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    if args.out:
        args.out.write_text(encoded, encoding="utf-8")
    else:
        print(encoded, end="")
    if args.selftest:
        assert report["verdict"] == "PASS", encoded
        assert report["mutation_count"] == report["mutation_rejection_count"]
        print("selftest: PASS")
    return 0 if report["verdict"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
