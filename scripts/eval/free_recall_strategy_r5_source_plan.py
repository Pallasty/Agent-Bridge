#!/usr/bin/env python3
"""Offline R5 source-plan and item-ref contract validator."""

from __future__ import annotations

import argparse
import copy
import hashlib
import hmac
import json
import re
from pathlib import Path
from typing import Any, Callable


SCHEMA = "agent_bridge.episode_source_plan.v0"
DOMAIN = b"agent-bridge/episode-item-ref/v1"
EPOCH_RE = re.compile(r"^[a-z0-9-]{1,32}$")
AUTHORITY_FIELDS = {
    "dependency_change",
    "rust_source",
    "schema_migration",
    "build",
    "execution",
    "private_state_test",
    "real_capture",
    "retrieval_change",
    "merge",
    "deployment",
    "production_key_provisioning",
}


def frame(value: bytes) -> bytes:
    return len(value).to_bytes(8, "big") + value


def derive_item_ref(key: bytes, epoch: str, memory_key: str) -> str:
    if len(key) < 32:
        raise ValueError("weak key")
    if not EPOCH_RE.fullmatch(epoch):
        raise ValueError("invalid epoch")
    epoch_bytes = epoch.encode("utf-8")
    memory_key_bytes = memory_key.encode("utf-8")
    if not 1 <= len(memory_key_bytes) <= 4096:
        raise ValueError("invalid memory key length")
    message = frame(DOMAIN) + frame(epoch_bytes) + frame(memory_key_bytes)
    digest = hmac.new(key, message, hashlib.sha256).hexdigest()
    return f"epr_v1_{epoch}_{digest}"


def canonical_plan() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA,
        "item_ref": {
            "scheme": "hmac_sha256",
            "digest_bytes": 32,
            "truncated": False,
            "reversible": False,
            "domain": DOMAIN.decode("ascii"),
            "framing": "u64be_length_prefix_each_part",
            "authenticated_parts": ["domain", "key_epoch", "memory_key_utf8"],
            "key_epoch_grammar": "[a-z0-9-]{1,32}",
            "memory_key_utf8_min_bytes": 1,
            "memory_key_utf8_max_bytes": 4096,
            "unkeyed_fallback": False,
            "persistent_reverse_map": False,
        },
        "key_provider": {
            "interface_only": True,
            "minimum_key_bytes": 32,
            "environment_secret": False,
            "cli_secret": False,
            "auto_generate_production_key": False,
            "logs_key_material": False,
            "serializes_key_material": False,
            "synthetic_test_provider_only": True,
            "unknown_epoch": "abstain",
            "missing_provider": "disabled_no_events",
            "production_custody_resolved": False,
        },
        "retention": {
            "normal_ingestion": "append_only",
            "event_rewrite": False,
            "purge_scope": "whole_episode_transaction_only",
            "partial_purge": False,
            "real_erasure_claim": False,
        },
        "slice_a": {
            "pure_contract_types": True,
            "item_ref_deriver": True,
            "noop_sink": True,
            "sqlite": False,
            "producer_callsite": False,
            "runtime_config_loader": False,
            "mcp_surface": False,
        },
        "slice_b_plan": {
            "relation": "episode_observation_events",
            "schema_version_reserved": False,
            "modifies_memory_record": False,
            "foreign_key_to_memories": False,
            "retrieval_trigger": False,
            "sync_or_export": False,
            "compile_time_default_on": False,
            "runtime_default_on": False,
            "rollback": "disable_and_leave_inert_relation",
        },
        "slice_c_plan": {
            "producer_seams": ["session_curate:curation_batch"],
            "open_before_save_loop": True,
            "item_after_successful_save_only": True,
            "close_after_loop": True,
            "position_source": "saved_candidate_order",
            "crash_result": "incomplete_abstain",
            "zero_save_result": "no_finalized_episode",
            "requires_compile_gate": True,
            "requires_runtime_gate": True,
            "requires_trusted_key_provider": True,
        },
        "offline_join": {
            "bounded": True,
            "persists_reverse_map": False,
            "feeds_retrieval": False,
            "unknown_epoch": "abstain",
            "collision": "abstain",
            "duplicate_match": "abstain",
            "ambiguous_episode": "abstain",
        },
        "authority": {name: False for name in sorted(AUTHORITY_FIELDS)},
        "next_gate": "r6_slice_a_source_requires_owner_authorization",
    }


def canonical_digest(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def validate(plan: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if plan.get("schema_version") != SCHEMA:
        errors.append("unsupported_schema")

    ref = plan.get("item_ref", {})
    if ref.get("scheme") != "hmac_sha256":
        errors.append("item_ref_scheme_drift")
    if ref.get("digest_bytes") != 32 or ref.get("truncated") is not False:
        errors.append("item_ref_truncated")
    if ref.get("reversible") is not False:
        errors.append("item_ref_reversible")
    if ref.get("domain") != DOMAIN.decode("ascii"):
        errors.append("domain_separation_missing")
    if ref.get("framing") != "u64be_length_prefix_each_part":
        errors.append("length_framing_missing")
    if ref.get("authenticated_parts") != ["domain", "key_epoch", "memory_key_utf8"]:
        errors.append("authenticated_part_missing")
    if ref.get("key_epoch_grammar") != "[a-z0-9-]{1,32}":
        errors.append("epoch_grammar_drift")
    if ref.get("memory_key_utf8_min_bytes") != 1 or ref.get("memory_key_utf8_max_bytes") != 4096:
        errors.append("memory_key_bounds_drift")
    if ref.get("unkeyed_fallback") is not False:
        errors.append("unkeyed_fallback")
    if ref.get("persistent_reverse_map") is not False:
        errors.append("persistent_reverse_map")

    provider = plan.get("key_provider", {})
    if provider.get("interface_only") is not True:
        errors.append("production_provider_claimed")
    if provider.get("minimum_key_bytes") != 32:
        errors.append("weak_key_allowed")
    for field in (
        "environment_secret",
        "cli_secret",
        "auto_generate_production_key",
        "logs_key_material",
        "serializes_key_material",
        "production_custody_resolved",
    ):
        if provider.get(field) is not False:
            errors.append("unsafe_key_provider")
    if provider.get("synthetic_test_provider_only") is not True:
        errors.append("non_synthetic_provider")
    if provider.get("unknown_epoch") != "abstain":
        errors.append("unknown_epoch_fallback")
    if provider.get("missing_provider") != "disabled_no_events":
        errors.append("missing_provider_fallback")

    retention = plan.get("retention", {})
    if retention.get("normal_ingestion") != "append_only":
        errors.append("non_append_ingestion")
    if retention.get("event_rewrite") is not False:
        errors.append("event_rewrite")
    if retention.get("purge_scope") != "whole_episode_transaction_only":
        errors.append("purge_scope_widened")
    if retention.get("partial_purge") is not False:
        errors.append("partial_purge")
    if retention.get("real_erasure_claim") is not False:
        errors.append("erasure_overclaim")

    slice_a = plan.get("slice_a", {})
    for field in ("pure_contract_types", "item_ref_deriver", "noop_sink"):
        if slice_a.get(field) is not True:
            errors.append("slice_a_missing")
    for field in ("sqlite", "producer_callsite", "runtime_config_loader", "mcp_surface"):
        if slice_a.get(field) is not False:
            errors.append("slice_a_scope_widened")

    slice_b = plan.get("slice_b_plan", {})
    if slice_b.get("relation") != "episode_observation_events":
        errors.append("relation_drift")
    for field in (
        "schema_version_reserved",
        "modifies_memory_record",
        "foreign_key_to_memories",
        "retrieval_trigger",
        "sync_or_export",
        "compile_time_default_on",
        "runtime_default_on",
    ):
        if slice_b.get(field) is not False:
            errors.append("slice_b_coupling")
    if slice_b.get("rollback") != "disable_and_leave_inert_relation":
        errors.append("destructive_rollback")

    slice_c = plan.get("slice_c_plan", {})
    if slice_c.get("producer_seams") != ["session_curate:curation_batch"]:
        errors.append("producer_scope_widened")
    required_true = (
        "open_before_save_loop",
        "item_after_successful_save_only",
        "close_after_loop",
        "requires_compile_gate",
        "requires_runtime_gate",
        "requires_trusted_key_provider",
    )
    if any(slice_c.get(field) is not True for field in required_true):
        errors.append("producer_fail_closed_weakened")
    if slice_c.get("position_source") != "saved_candidate_order":
        errors.append("position_source_drift")
    if slice_c.get("crash_result") != "incomplete_abstain":
        errors.append("crash_fallback")
    if slice_c.get("zero_save_result") != "no_finalized_episode":
        errors.append("zero_save_fallback")

    join = plan.get("offline_join", {})
    if join.get("bounded") is not True:
        errors.append("unbounded_join")
    if join.get("persists_reverse_map") is not False:
        errors.append("join_persists_map")
    if join.get("feeds_retrieval") is not False:
        errors.append("join_feeds_retrieval")
    for field in ("unknown_epoch", "collision", "duplicate_match", "ambiguous_episode"):
        if join.get(field) != "abstain":
            errors.append("join_not_fail_closed")

    authority = plan.get("authority")
    if not isinstance(authority, dict) or set(authority) != AUTHORITY_FIELDS:
        errors.append("authority_set_mismatch")
    elif any(authority.values()):
        errors.append("authority_enabled")
    if plan.get("next_gate") != "r6_slice_a_source_requires_owner_authorization":
        errors.append("next_gate_widened")
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
    rows.extend(
        [
            ("use_raw_key", "item_ref_scheme_drift", lambda p: set_path(p, ("item_ref", "scheme"), "raw_memory_key")),
            ("use_unkeyed_sha256", "item_ref_scheme_drift", lambda p: set_path(p, ("item_ref", "scheme"), "sha256")),
            ("use_random_mapping", "persistent_reverse_map", lambda p: set_path(p, ("item_ref", "persistent_reverse_map"), True)),
            ("truncate_digest", "item_ref_truncated", lambda p: set_path(p, ("item_ref", "digest_bytes"), 16)),
            ("make_reversible", "item_ref_reversible", lambda p: set_path(p, ("item_ref", "reversible"), True)),
            ("drop_domain", "domain_separation_missing", lambda p: set_path(p, ("item_ref", "domain"), "")),
            ("drop_framing", "length_framing_missing", lambda p: set_path(p, ("item_ref", "framing"), "concat")),
            ("drop_epoch_auth", "authenticated_part_missing", lambda p: p["item_ref"]["authenticated_parts"].remove("key_epoch")),
            ("allow_epoch_delimiter", "epoch_grammar_drift", lambda p: set_path(p, ("item_ref", "key_epoch_grammar"), ".+")),
            ("allow_empty_memory_key", "memory_key_bounds_drift", lambda p: set_path(p, ("item_ref", "memory_key_utf8_min_bytes"), 0)),
            ("allow_unkeyed_fallback", "unkeyed_fallback", lambda p: set_path(p, ("item_ref", "unkeyed_fallback"), True)),
            ("allow_weak_key", "weak_key_allowed", lambda p: set_path(p, ("key_provider", "minimum_key_bytes"), 16)),
            ("read_env_secret", "unsafe_key_provider", lambda p: set_path(p, ("key_provider", "environment_secret"), True)),
            ("read_cli_secret", "unsafe_key_provider", lambda p: set_path(p, ("key_provider", "cli_secret"), True)),
            ("auto_generate_key", "unsafe_key_provider", lambda p: set_path(p, ("key_provider", "auto_generate_production_key"), True)),
            ("log_key", "unsafe_key_provider", lambda p: set_path(p, ("key_provider", "logs_key_material"), True)),
            ("claim_custody", "unsafe_key_provider", lambda p: set_path(p, ("key_provider", "production_custody_resolved"), True)),
            ("unknown_epoch_fallback", "unknown_epoch_fallback", lambda p: set_path(p, ("key_provider", "unknown_epoch"), "current_epoch")),
            ("partial_purge", "partial_purge", lambda p: set_path(p, ("retention", "partial_purge"), True)),
            ("rewrite_events", "event_rewrite", lambda p: set_path(p, ("retention", "event_rewrite"), True)),
            ("claim_erasure", "erasure_overclaim", lambda p: set_path(p, ("retention", "real_erasure_claim"), True)),
            ("slice_a_add_sqlite", "slice_a_scope_widened", lambda p: set_path(p, ("slice_a", "sqlite"), True)),
            ("reserve_schema", "slice_b_coupling", lambda p: set_path(p, ("slice_b_plan", "schema_version_reserved"), True)),
            ("modify_memory_record", "slice_b_coupling", lambda p: set_path(p, ("slice_b_plan", "modifies_memory_record"), True)),
            ("add_foreign_key", "slice_b_coupling", lambda p: set_path(p, ("slice_b_plan", "foreign_key_to_memories"), True)),
            ("add_retrieval_trigger", "slice_b_coupling", lambda p: set_path(p, ("slice_b_plan", "retrieval_trigger"), True)),
            ("default_on", "slice_b_coupling", lambda p: set_path(p, ("slice_b_plan", "runtime_default_on"), True)),
            ("destructive_rollback", "destructive_rollback", lambda p: set_path(p, ("slice_b_plan", "rollback"), "drop_table")),
            ("add_second_producer", "producer_scope_widened", lambda p: p["slice_c_plan"]["producer_seams"].append("memory_save:inferred")),
            ("emit_item_before_save", "producer_fail_closed_weakened", lambda p: set_path(p, ("slice_c_plan", "item_after_successful_save_only"), False)),
            ("order_by_time", "position_source_drift", lambda p: set_path(p, ("slice_c_plan", "position_source"), "observed_at")),
            ("crash_finalize", "crash_fallback", lambda p: set_path(p, ("slice_c_plan", "crash_result"), "partial_finalize")),
            ("persist_join_map", "join_persists_map", lambda p: set_path(p, ("offline_join", "persists_reverse_map"), True)),
            ("join_into_retrieval", "join_feeds_retrieval", lambda p: set_path(p, ("offline_join", "feeds_retrieval"), True)),
            ("collision_pick_first", "join_not_fail_closed", lambda p: set_path(p, ("offline_join", "collision"), "first")),
            ("widen_next_gate", "next_gate_widened", lambda p: set_path(p, ("next_gate",), "implement_build_run")),
        ]
    )
    return rows


def run() -> dict[str, Any]:
    plan = canonical_plan()
    errors = validate(plan)
    mutation_rows = []
    for name, expected, mutate in mutations():
        candidate = copy.deepcopy(plan)
        mutate(candidate)
        found = validate(candidate)
        mutation_rows.append({"name": name, "expected_error": expected, "rejected_as_expected": expected in found})

    key = bytes(range(32))
    epoch = "epoch-test-0001"
    memory_key = "curated_decision_测试_01"
    known = derive_item_ref(key, epoch, memory_key)
    crypto_checks = {
        "deterministic": known == derive_item_ref(key, epoch, memory_key),
        "domain_separated": known != "epr_v1_" + epoch + "_" + hmac.new(key, frame(b"other-domain") + frame(epoch.encode()) + frame(memory_key.encode()), hashlib.sha256).hexdigest(),
        "epoch_authenticated": known != derive_item_ref(key, "epoch-test-0002", memory_key),
        "memory_key_bound": known != derive_item_ref(key, epoch, memory_key + "x"),
        "weak_key_rejected": False,
        "invalid_epoch_rejected": False,
        "empty_memory_key_rejected": False,
        "oversized_memory_key_rejected": False,
    }
    try:
        derive_item_ref(b"short", epoch, memory_key)
    except ValueError:
        crypto_checks["weak_key_rejected"] = True
    for field, args in (
        ("invalid_epoch_rejected", (key, "bad_epoch", memory_key)),
        ("empty_memory_key_rejected", (key, epoch, "")),
        ("oversized_memory_key_rejected", (key, epoch, "x" * 4097)),
    ):
        try:
            derive_item_ref(*args)
        except ValueError:
            crypto_checks[field] = True

    reversed_plan = {key: plan[key] for key in reversed(list(plan))}
    gates = {
        "canonical_plan": not errors,
        "item_ref_known_answer": all(crypto_checks.values()),
        "directed_mutations": all(row["rejected_as_expected"] for row in mutation_rows),
        "key_order_invariant": canonical_digest(plan) == canonical_digest(reversed_plan),
        "zero_authority": not errors,
    }
    return {
        "schema_version": "agent_bridge.free_recall_strategy_r5_report.v0",
        "fixture": "public_synthetic_source_plan",
        "canonical_plan_sha256": canonical_digest(plan),
        "known_answer_item_ref": known,
        "canonical_error_count": len(errors),
        "mutation_count": len(mutation_rows),
        "mutation_rejection_count": sum(row["rejected_as_expected"] for row in mutation_rows),
        "crypto_checks": crypto_checks,
        "gates": gates,
        "verdict": "PASS" if all(gates.values()) else "FAIL",
        "mutations": mutation_rows,
        "authority": {
            "r6_slice_a_source_eligible": all(gates.values()),
            "source_implemented": False,
            "build_authorized": False,
            "execution_authorized": False,
            "real_capture_authorized": False,
            "retrieval_authorized": False,
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
