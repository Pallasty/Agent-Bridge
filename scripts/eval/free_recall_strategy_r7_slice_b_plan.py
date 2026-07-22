#!/usr/bin/env python3
"""Offline validator for the R7 Slice B migration/inert-adapter contract."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
from typing import Any, Callable


SCHEMA = "agent_bridge.free_recall_strategy_r7_plan.v0"
AUTHORITY_FIELDS = {
    "sql_source", "rust_source", "feature_change", "database_access", "build",
    "execution", "private_state_test", "producer_wiring", "runtime_enablement",
    "retrieval_change", "sync_export_change", "merge", "deployment",
}
EVENT_TYPES = ["episode.open", "episode.item", "episode.close"]
SOURCE_KINDS = ["session", "curation_batch", "owner_bundle"]


def canonical_plan() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA,
        "schema_cursor": {
            "reserved": False,
            "versionless_bypass": False,
            "owner_handoff_required": True,
            "owner_named": False,
            "predecessor_named": False,
            "target_named": False,
            "owner_reviewed_transaction": False,
        },
        "relation": {
            "name": "episode_observation_events",
            "columns": ["event_id", "episode_id", "event_type", "source_kind", "producer_run_id", "item_ref", "episode_position", "item_count", "payload_sha256", "observed_at"],
            "event_types": EVENT_TYPES,
            "source_kinds": SOURCE_KINDS,
            "payload_sha256": "lower_hex_64",
            "non_empty_text": ["event_id", "episode_id", "producer_run_id"],
            "integer_nonnegative": ["observed_at", "episode_position_when_present", "item_count_when_present"],
            "shape": {
                "episode.open": "item_ref_null_position_null_count_null",
                "episode.item": "item_ref_present_position_present_count_null",
                "episode.close": "item_ref_null_position_null_count_present",
            },
            "foreign_key_to_memories": False,
            "triggers": False,
            "fts_vector_graph": False,
            "sync_or_export": False,
            "retrieval_consumer": False,
            "indexes": ["episode_id"],
        },
        "gating": {
            "slice_b_compile_feature_new": True,
            "compile_feature_default_on": False,
            "default_binary_creates_relation": False,
            "default_binary_alters_schema_meta": False,
            "runtime_default_on": False,
            "runtime_disabled_producer_calls": 0,
            "runtime_disabled_event_writes": 0,
            "runtime_disabled_projection_reads": 0,
            "runtime_disabled_api_difference": False,
        },
        "migration": {
            "idempotent_concurrent_open": True,
            "failure_rolls_back_table_index_cursor": True,
            "test_database_scope": "disposable_only",
            "uses_user_state_db": False,
            "uses_private_capture": False,
        },
        "adapter": {
            "visibility": "private_sqlite_store_detail",
            "methods": ["append_validated_event", "read_finalized_projection"],
            "widens_state_store": False,
            "mcp_or_public_api": False,
            "derives_item_ref": False,
            "reads_raw_memory_keys": False,
            "producer_calls": False,
            "membership_inference": False,
            "finalization": "exact_open_contiguous_items_single_matching_close_else_abstain",
        },
        "rollback": {
            "disable_producer_and_reader": True,
            "leave_relation_inert": True,
            "rewrite_existing_events": False,
            "partial_delete": False,
            "drop_populated_relation": False,
            "erasure_claim": False,
        },
        "authority": {name: False for name in sorted(AUTHORITY_FIELDS)},
        "next_gate": "r8_slice_b_source_requires_owner_authorization",
    }


def canonical_digest(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def validate(plan: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if plan.get("schema_version") != SCHEMA:
        errors.append("unsupported_schema")
    cursor = plan.get("schema_cursor", {})
    if cursor.get("reserved") is not False:
        errors.append("schema_cursor_reserved")
    if cursor.get("versionless_bypass") is not False:
        errors.append("schema_owner_bypassed")
    if cursor.get("owner_handoff_required") is not True:
        errors.append("schema_owner_handoff_missing")
    if any(cursor.get(key) is not False for key in ("owner_named", "predecessor_named", "target_named", "owner_reviewed_transaction")):
        errors.append("premature_schema_claim")

    relation = plan.get("relation", {})
    if relation.get("name") != "episode_observation_events": errors.append("relation_drift")
    if relation.get("columns") != ["event_id", "episode_id", "event_type", "source_kind", "producer_run_id", "item_ref", "episode_position", "item_count", "payload_sha256", "observed_at"]: errors.append("column_contract_drift")
    if relation.get("event_types") != EVENT_TYPES or relation.get("source_kinds") != SOURCE_KINDS: errors.append("enum_contract_drift")
    if relation.get("payload_sha256") != "lower_hex_64": errors.append("payload_digest_contract_drift")
    if relation.get("non_empty_text") != ["event_id", "episode_id", "producer_run_id"]: errors.append("text_constraint_drift")
    if relation.get("integer_nonnegative") != ["observed_at", "episode_position_when_present", "item_count_when_present"]: errors.append("integer_constraint_drift")
    if relation.get("shape") != {"episode.open": "item_ref_null_position_null_count_null", "episode.item": "item_ref_present_position_present_count_null", "episode.close": "item_ref_null_position_null_count_present"}: errors.append("event_shape_drift")
    for key in ("foreign_key_to_memories", "triggers", "fts_vector_graph", "sync_or_export", "retrieval_consumer"):
        if relation.get(key) is not False: errors.append("relation_coupling")
    if relation.get("indexes") != ["episode_id"]: errors.append("index_scope_drift")

    gating = plan.get("gating", {})
    if gating.get("slice_b_compile_feature_new") is not True: errors.append("compile_gate_missing")
    for key in ("compile_feature_default_on", "default_binary_creates_relation", "default_binary_alters_schema_meta", "runtime_default_on", "runtime_disabled_api_difference"):
        if gating.get(key) is not False: errors.append("default_off_weakened")
    for key in ("runtime_disabled_producer_calls", "runtime_disabled_event_writes", "runtime_disabled_projection_reads"):
        if gating.get(key) != 0: errors.append("disabled_side_effect")

    migration = plan.get("migration", {})
    if migration.get("idempotent_concurrent_open") is not True or migration.get("failure_rolls_back_table_index_cursor") is not True: errors.append("migration_atomicity_weakened")
    if migration.get("test_database_scope") != "disposable_only" or migration.get("uses_user_state_db") is not False or migration.get("uses_private_capture") is not False: errors.append("database_scope_widened")

    adapter = plan.get("adapter", {})
    if adapter.get("visibility") != "private_sqlite_store_detail" or adapter.get("methods") != ["append_validated_event", "read_finalized_projection"]: errors.append("adapter_scope_widened")
    for key in ("widens_state_store", "mcp_or_public_api", "derives_item_ref", "reads_raw_memory_keys", "producer_calls", "membership_inference"):
        if adapter.get(key) is not False: errors.append("adapter_scope_widened")
    if adapter.get("finalization") != "exact_open_contiguous_items_single_matching_close_else_abstain": errors.append("finalization_not_fail_closed")

    rollback = plan.get("rollback", {})
    if rollback.get("disable_producer_and_reader") is not True or rollback.get("leave_relation_inert") is not True: errors.append("rollback_not_inert")
    for key in ("rewrite_existing_events", "partial_delete", "drop_populated_relation", "erasure_claim"):
        if rollback.get(key) is not False: errors.append("destructive_rollback")

    authority = plan.get("authority")
    if not isinstance(authority, dict) or set(authority) != AUTHORITY_FIELDS: errors.append("authority_set_mismatch")
    elif any(authority.values()): errors.append("authority_enabled")
    if plan.get("next_gate") != "r8_slice_b_source_requires_owner_authorization": errors.append("next_gate_widened")
    return sorted(set(errors))


def set_path(value: dict[str, Any], path: tuple[str, ...], replacement: Any) -> None:
    cursor = value
    for part in path[:-1]: cursor = cursor[part]
    cursor[path[-1]] = replacement


def mutations() -> list[tuple[str, str, Callable[[dict[str, Any]], None]]]:
    rows: list[tuple[str, str, Callable[[dict[str, Any]], None]]] = []
    for authority in sorted(AUTHORITY_FIELDS):
        rows.append((f"authorize_{authority}", "authority_enabled", lambda p, a=authority: set_path(p, ("authority", a), True)))
    rows.extend([
        ("reserve_v44", "schema_cursor_reserved", lambda p: set_path(p, ("schema_cursor", "reserved"), True)),
        ("skip_owner", "schema_owner_handoff_missing", lambda p: set_path(p, ("schema_cursor", "owner_handoff_required"), False)),
        ("copy_versionless_pattern", "schema_owner_bypassed", lambda p: set_path(p, ("schema_cursor", "versionless_bypass"), True)),
        ("claim_target_early", "premature_schema_claim", lambda p: set_path(p, ("schema_cursor", "target_named"), True)),
        ("add_fk", "relation_coupling", lambda p: set_path(p, ("relation", "foreign_key_to_memories"), True)),
        ("add_trigger", "relation_coupling", lambda p: set_path(p, ("relation", "triggers"), True)),
        ("add_fts", "relation_coupling", lambda p: set_path(p, ("relation", "fts_vector_graph"), True)),
        ("add_sync", "relation_coupling", lambda p: set_path(p, ("relation", "sync_or_export"), True)),
        ("add_retrieval", "relation_coupling", lambda p: set_path(p, ("relation", "retrieval_consumer"), True)),
        ("loosen_close_shape", "event_shape_drift", lambda p: set_path(p, ("relation", "shape", "episode.close"), "any_nullable")),
        ("add_time_index", "index_scope_drift", lambda p: p["relation"]["indexes"].append("observed_at")),
        ("default_feature_on", "default_off_weakened", lambda p: set_path(p, ("gating", "compile_feature_default_on"), True)),
        ("default_creates_table", "default_off_weakened", lambda p: set_path(p, ("gating", "default_binary_creates_relation"), True)),
        ("disabled_write", "disabled_side_effect", lambda p: set_path(p, ("gating", "runtime_disabled_event_writes"), 1)),
        ("user_state_test", "database_scope_widened", lambda p: set_path(p, ("migration", "uses_user_state_db"), True)),
        ("weak_atomicity", "migration_atomicity_weakened", lambda p: set_path(p, ("migration", "failure_rolls_back_table_index_cursor"), False)),
        ("widen_state_store", "adapter_scope_widened", lambda p: set_path(p, ("adapter", "widens_state_store"), True)),
        ("add_producer", "adapter_scope_widened", lambda p: set_path(p, ("adapter", "producer_calls"), True)),
        ("finalize_partial", "finalization_not_fail_closed", lambda p: set_path(p, ("adapter", "finalization"), "close_count_only")),
        ("drop_table_rollback", "destructive_rollback", lambda p: set_path(p, ("rollback", "drop_populated_relation"), True)),
        ("rewrite_rows", "destructive_rollback", lambda p: set_path(p, ("rollback", "rewrite_existing_events"), True)),
        ("widen_next_gate", "next_gate_widened", lambda p: set_path(p, ("next_gate",), "implement_build_run")),
    ])
    return rows


def run() -> dict[str, Any]:
    plan = canonical_plan()
    errors = validate(plan)
    rows = []
    for name, expected, mutate in mutations():
        candidate = copy.deepcopy(plan); mutate(candidate)
        rows.append({"name": name, "expected_error": expected, "rejected_as_expected": expected in validate(candidate)})
    reversed_plan = {key: plan[key] for key in reversed(list(plan))}
    gates = {
        "canonical_plan": not errors,
        "directed_mutations": all(row["rejected_as_expected"] for row in rows),
        "key_order_invariant": canonical_digest(plan) == canonical_digest(reversed_plan),
        "zero_authority": not errors,
    }
    return {"schema_version": "agent_bridge.free_recall_strategy_r7_report.v0", "fixture": "public_synthetic_slice_b_plan", "canonical_plan_sha256": canonical_digest(plan), "canonical_error_count": len(errors), "mutation_count": len(rows), "mutation_rejection_count": sum(row["rejected_as_expected"] for row in rows), "gates": gates, "verdict": "PASS" if all(gates.values()) else "FAIL", "mutations": rows, "authority": {"r8_slice_b_source_eligible": all(gates.values()), "source_implemented": False, "build_authorized": False, "execution_authorized": False, "private_database_used": False, "producer_authorized": False, "retrieval_authorized": False, "merge_authorized": False, "deployment_authorized": False}}


def main() -> int:
    parser = argparse.ArgumentParser(); parser.add_argument("--out", type=Path); parser.add_argument("--selftest", action="store_true")
    args = parser.parse_args(); report = run(); encoded = json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    if args.out: args.out.write_text(encoded, encoding="utf-8")
    else: print(encoded, end="")
    if args.selftest:
        assert report["verdict"] == "PASS", encoded
        assert report["mutation_count"] == report["mutation_rejection_count"]
        print("selftest: PASS")
    return 0 if report["verdict"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
