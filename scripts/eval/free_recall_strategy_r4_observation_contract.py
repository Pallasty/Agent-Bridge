#!/usr/bin/env python3
"""Offline R4 design-contract gate for an observation-only episode sidecar."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
from typing import Any, Callable


SCHEMA = "agent_bridge.episode_observation_integration.v0"
FALSE_FLAGS = {
    "default_enabled",
    "producer_enabled",
    "retrieval_consumer_enabled",
    "mcp_surface_enabled",
    "real_capture_allowed",
    "storage_mutation_allowed",
    "deployment_allowed",
}
ALLOWED_COLUMNS = {
    "event_id",
    "episode_id",
    "event_type",
    "source_kind",
    "producer_run_id",
    "item_ref",
    "episode_position",
    "item_count",
    "payload_sha256",
    "observed_at",
}
FORBIDDEN_FIELD_TOKENS = {
    "content",
    "conversation_text",
    "query",
    "tags",
    "embedding",
    "memory_key",
    "raw_memory_key",
    "scope",
    "related_keys",
    "rank_score",
    "user_identity",
}
ZERO_EFFECTS = {
    "producer_calls",
    "sidecar_writes",
    "retrieval_projection_reads",
    "existing_memory_api_differences",
    "retrieval_output_differences",
}
ABSTAIN_ON = {"absence", "ambiguity", "conflict", "incompleteness"}


def canonical_manifest() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA,
        "mode": "disabled",
        "flags": {name: False for name in sorted(FALSE_FLAGS)},
        "storage": {
            "relation": "episode_observation_events",
            "separate_from_memories": True,
            "append_only": True,
            "modifies_memory_record": False,
            "columns": sorted(ALLOWED_COLUMNS),
            "triggers": [],
            "consumers": [],
        },
        "privacy": {
            "duplicates_memory_content": False,
            "item_ref_status": "unresolved_security_review",
            "item_ref_claims_custody_solved": False,
        },
        "projection": {
            "reducer_contract": "agent_bridge.episode_observation.v0",
            "ordering_authority": "episode_position",
            "requires_open": True,
            "requires_close": True,
            "requires_unique_items": True,
            "requires_unique_positions": True,
            "requires_contiguous_positions": True,
            "emits_finalized_only": True,
            "abstain_on": sorted(ABSTAIN_ON),
            "reads_retrieval_indexes": False,
            "mutates_retrieval": False,
        },
        "kill_switch": {
            "present": True,
            "disabled_zero_effects": sorted(ZERO_EFFECTS),
        },
        "evidence_scope": "public_synthetic_only",
        "next_authority": "r5_source_only_plan_requires_owner_authorization",
    }


def digest(value: Any) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def recursive_keys(value: Any) -> list[str]:
    out: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            out.append(str(key))
            out.extend(recursive_keys(child))
    elif isinstance(value, list):
        for child in value:
            out.extend(recursive_keys(child))
    return out


def validate(manifest: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if manifest.get("schema_version") != SCHEMA:
        errors.append("unsupported_schema")
    if manifest.get("mode") != "disabled":
        errors.append("mode_not_disabled")

    flags = manifest.get("flags")
    if not isinstance(flags, dict) or set(flags) != FALSE_FLAGS:
        errors.append("authority_flag_set_mismatch")
    elif any(flags.values()):
        errors.append("authority_enabled")

    storage = manifest.get("storage", {})
    if storage.get("relation") != "episode_observation_events":
        errors.append("relation_not_independent")
    if storage.get("separate_from_memories") is not True:
        errors.append("memory_table_coupling")
    if storage.get("append_only") is not True:
        errors.append("not_append_only")
    if storage.get("modifies_memory_record") is not False:
        errors.append("memory_record_mutation")
    if set(storage.get("columns", [])) != ALLOWED_COLUMNS:
        errors.append("column_contract_mismatch")
    if storage.get("triggers") != []:
        errors.append("trigger_coupling")
    if storage.get("consumers") != []:
        errors.append("consumer_coupling")

    keys = {key.lower() for key in recursive_keys(manifest)}
    if keys & FORBIDDEN_FIELD_TOKENS:
        errors.append("forbidden_field")

    privacy = manifest.get("privacy", {})
    if privacy.get("duplicates_memory_content") is not False:
        errors.append("content_duplication")
    if privacy.get("item_ref_status") != "unresolved_security_review":
        errors.append("item_ref_boundary_changed")
    if privacy.get("item_ref_claims_custody_solved") is not False:
        errors.append("item_ref_custody_overclaim")

    projection = manifest.get("projection", {})
    required_true = {
        "requires_open",
        "requires_close",
        "requires_unique_items",
        "requires_unique_positions",
        "requires_contiguous_positions",
        "emits_finalized_only",
    }
    if projection.get("reducer_contract") != "agent_bridge.episode_observation.v0":
        errors.append("reducer_contract_drift")
    if projection.get("ordering_authority") != "episode_position":
        errors.append("ordering_authority_drift")
    if any(projection.get(field) is not True for field in required_true):
        errors.append("partial_bundle_allowed")
    if set(projection.get("abstain_on", [])) != ABSTAIN_ON:
        errors.append("abstention_contract_drift")
    if projection.get("reads_retrieval_indexes") is not False:
        errors.append("retrieval_read_coupling")
    if projection.get("mutates_retrieval") is not False:
        errors.append("retrieval_mutation")

    kill = manifest.get("kill_switch", {})
    if kill.get("present") is not True:
        errors.append("kill_switch_missing")
    if set(kill.get("disabled_zero_effects", [])) != ZERO_EFFECTS:
        errors.append("zero_effect_invariant_drift")
    if manifest.get("evidence_scope") != "public_synthetic_only":
        errors.append("real_capture_claimed")
    if manifest.get("next_authority") != "r5_source_only_plan_requires_owner_authorization":
        errors.append("next_authority_widened")
    return sorted(set(errors))


def set_path(value: dict[str, Any], path: tuple[str, ...], replacement: Any) -> None:
    cursor = value
    for part in path[:-1]:
        cursor = cursor[part]
    cursor[path[-1]] = replacement


def mutation_cases() -> list[tuple[str, str, Callable[[dict[str, Any]], None]]]:
    cases: list[tuple[str, str, Callable[[dict[str, Any]], None]]] = []
    for flag in sorted(FALSE_FLAGS):
        cases.append(
            (
                f"enable_{flag}",
                "authority_enabled",
                lambda m, flag=flag: set_path(m, ("flags", flag), True),
            )
        )
    cases.extend(
        [
            ("enable_mode", "mode_not_disabled", lambda m: set_path(m, ("mode",), "shadow")),
            ("couple_memories", "memory_table_coupling", lambda m: set_path(m, ("storage", "separate_from_memories"), False)),
            ("mutate_memory_record", "memory_record_mutation", lambda m: set_path(m, ("storage", "modifies_memory_record"), True)),
            ("add_content_column", "column_contract_mismatch", lambda m: m["storage"]["columns"].append("content")),
            ("add_retrieval_trigger", "trigger_coupling", lambda m: m["storage"]["triggers"].append("memories_fts")),
            ("add_retrieval_consumer", "consumer_coupling", lambda m: m["storage"]["consumers"].append("memory_search")),
            ("duplicate_content", "content_duplication", lambda m: set_path(m, ("privacy", "duplicates_memory_content"), True)),
            ("claim_item_ref_derivation", "item_ref_boundary_changed", lambda m: set_path(m, ("privacy", "item_ref_status"), "hmac_sha256")),
            ("claim_item_ref_custody", "item_ref_custody_overclaim", lambda m: set_path(m, ("privacy", "item_ref_claims_custody_solved"), True)),
            ("order_by_time", "ordering_authority_drift", lambda m: set_path(m, ("projection", "ordering_authority"), "observed_at")),
            ("allow_partial", "partial_bundle_allowed", lambda m: set_path(m, ("projection", "emits_finalized_only"), False)),
            ("drop_ambiguity_abstain", "abstention_contract_drift", lambda m: m["projection"]["abstain_on"].remove("ambiguity")),
            ("read_retrieval_index", "retrieval_read_coupling", lambda m: set_path(m, ("projection", "reads_retrieval_indexes"), True)),
            ("mutate_retrieval", "retrieval_mutation", lambda m: set_path(m, ("projection", "mutates_retrieval"), True)),
            ("remove_kill_switch", "kill_switch_missing", lambda m: set_path(m, ("kill_switch", "present"), False)),
            ("drop_zero_effect", "zero_effect_invariant_drift", lambda m: m["kill_switch"]["disabled_zero_effects"].pop()),
            ("claim_real_capture", "real_capture_claimed", lambda m: set_path(m, ("evidence_scope",), "real_sessions")),
            ("widen_next_authority", "next_authority_widened", lambda m: set_path(m, ("next_authority",), "implement_and_deploy")),
        ]
    )
    for field in sorted(FORBIDDEN_FIELD_TOKENS):
        cases.append(
            (
                f"inject_forbidden_{field}",
                "forbidden_field",
                lambda m, field=field: m.setdefault("extension", {}).update({field: "x"}),
            )
        )
    return cases


def run() -> dict[str, Any]:
    manifest = canonical_manifest()
    canonical_errors = validate(manifest)
    results = []
    for name, expected, mutate in mutation_cases():
        candidate = copy.deepcopy(manifest)
        mutate(candidate)
        errors = validate(candidate)
        results.append(
            {
                "name": name,
                "expected_error": expected,
                "rejected_as_expected": expected in errors,
                "error_count": len(errors),
            }
        )

    reversed_manifest = {key: manifest[key] for key in reversed(list(manifest))}
    all_mutations_rejected = all(row["rejected_as_expected"] for row in results)
    gates = {
        "canonical_manifest": not canonical_errors,
        "isolation": not canonical_errors,
        "fail_closed": not canonical_errors,
        "directed_mutations": all_mutations_rejected,
        "key_order_invariant": digest(reversed_manifest) == digest(manifest),
        "zero_runtime_authority": not canonical_errors,
    }
    report = {
        "schema_version": "agent_bridge.free_recall_strategy_r4_report.v0",
        "fixture": "public_synthetic_design_manifest",
        "canonical_manifest_sha256": digest(manifest),
        "canonical_error_count": len(canonical_errors),
        "mutation_count": len(results),
        "mutation_rejection_count": sum(row["rejected_as_expected"] for row in results),
        "gates": gates,
        "verdict": "PASS" if all(gates.values()) else "FAIL",
        "mutations": results,
        "authority": {
            "schema_implementation": False,
            "runtime_execution": False,
            "real_capture": False,
            "retrieval_change": False,
            "deployment": False,
            "r5_source_plan_eligible": all(gates.values()),
        },
    }
    return report


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
