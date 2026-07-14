#!/usr/bin/env python3
"""Validate the public, synthetic S1 evidence-substrate design packet.

This checker is intentionally standard-library-only. It validates a logical
schema and a synthetic snapshot, then proves that preregistered adversarial
mutations fail closed. It never opens SQLite, Agent-Bridge, BioCortex, or a
projector and cannot authorize a real adapter or capture.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Callable


CONTRACT_SCHEMA = "agent_bridge.memory_temporal_evidence_substrate_design.v0"
FIXTURE_SCHEMA = "agent_bridge.memory_temporal_evidence_substrate_synthetic.v0"
RECEIPT_SCHEMA = "agent_bridge.memory_temporal_evidence_substrate_design_receipt.v0"
DESIGN_STATUS = "READY_FOR_SEPARATE_MIGRATION_REVIEW"
ATTESTATION_VERSION = "content_free_governance_v0"
CANONICAL_ORDER = "binary_utf8_v0"
TIER_ORDER = {"inferred": 0, "observed": 1, "verified": 2, "authoritative": 3}
HARD_CAP_MAXIMA = {
    "max_lineages": 10_000,
    "max_policy_revisions": 10_000,
    "max_evidence_revisions": 10_000,
    "max_relationships": 50_000,
    "max_tombstones": 10_000,
    "max_payload_bytes": 16_777_216,
}
SENTINELS = (
    "AB_EVIDENCE_SUBSTRATE_SENTINEL",
    "AGENT_BRIDGE_EVIDENCE_SUBSTRATE_SENTINEL",
    "PYTHONINSPECT",
)

NEGATIVE_CASES = [
    "primary_key_contract_drift",
    "foreign_key_contract_drift",
    "store_derived_contract_drift",
    "duplicate_revision_seq",
    "missing_revision_seq",
    "ambiguous_recorded_at",
    "lineage_claim_drift",
    "dropped_relationship",
    "dangling_relationship",
    "self_relationship",
    "relationship_cycle",
    "cross_claim_relationship",
    "dual_relationship_kind",
    "conflicting_relationship_time",
    "lower_tier_suppression",
    "missing_provenance",
    "caller_declared_tier",
    "unknown_authority_policy",
    "authority_predicate_fallback",
    "policy_revocation_bypass",
    "policy_recorded_at_regression",
    "policy_tier_shopping",
    "observation_after_recording",
    "inverted_validity",
    "missing_governance_attestation",
    "tombstone_content_leak",
    "later_target_downgrade",
    "same_second_target_downgrade",
    "snapshot_truncated",
    "endpoint_nonclosure",
    "unbounded_snapshot_caps",
    "canonical_payload_hash_drift",
    "noncanonical_order",
    "duplicate_evidence_id",
    "unknown_field",
    "duplicate_json_key",
]


class ValidationError(Exception):
    def __init__(self, code: str, detail: str):
        super().__init__(f"{code}: {detail}")
        self.code = code
        self.detail = detail


def reject(code: str, detail: str) -> None:
    raise ValidationError(code, detail)


def strict_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in pairs:
        if key in out:
            reject("duplicate_json_key", f"duplicate JSON key {key!r}")
        out[key] = value
    return out


def load_strict(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=strict_object)
    except ValidationError:
        raise
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        reject("invalid_json", f"{path}: {exc}")
    if not isinstance(value, dict):
        reject("invalid_type", f"{path} root must be an object")
    return value


def require_keys(
    value: Any,
    required: set[str],
    path: str,
    *,
    missing_code: str = "missing_field",
    unknown_code: str = "unknown_field",
) -> dict[str, Any]:
    if not isinstance(value, dict):
        reject("invalid_type", f"{path} must be an object")
    missing = sorted(required - value.keys())
    unknown = sorted(value.keys() - required)
    if missing:
        reject(missing_code, f"{path} missing {missing}")
    if unknown:
        reject(unknown_code, f"{path} has unknown fields {unknown}")
    return value


def require_bool(value: Any, path: str) -> bool:
    if not isinstance(value, bool):
        reject("invalid_type", f"{path} must be boolean")
    return value


def require_int(value: Any, path: str, *, minimum: int = 0) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        reject("invalid_integer", f"{path} must be an integer >= {minimum}")
    return value


def require_label(value: Any, path: str) -> str:
    if not isinstance(value, str):
        reject("invalid_label", f"{path} must be a string")
    if not value or value != value.strip() or len(value.encode("utf-8")) > 512:
        reject("invalid_label", f"{path} is empty, padded, or oversized")
    if not value.isascii() or any(ord(ch) < 32 or ord(ch) == 127 for ch in value):
        reject("invalid_label", f"{path} must be printable ASCII")
    return value


def require_hex64(value: Any, path: str) -> str:
    if not isinstance(value, str) or len(value) != 64:
        reject("invalid_digest", f"{path} must be 64 lowercase hex characters")
    if any(ch not in "0123456789abcdef" for ch in value):
        reject("invalid_digest", f"{path} must be lowercase hexadecimal")
    return value


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def sha256_json(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def claim_digest(lineage: dict[str, Any]) -> str:
    return sha256_json(
        {
            "predicate_id": lineage["predicate_id"],
            "referent_id": lineage["referent_id"],
        }
    )


def tombstone_digest(tombstone: dict[str, Any]) -> str:
    return sha256_json(
        {
            "attestation_version": tombstone["attestation_version"],
            "had_outgoing_governance": tombstone["had_outgoing_governance"],
            "lineage_id": tombstone["lineage_id"],
            "tombstone_id": tombstone["tombstone_id"],
            "tombstoned_at": tombstone["tombstoned_at"],
        }
    )


def snapshot_payload(fixture: dict[str, Any]) -> dict[str, Any]:
    return {
        "authority_policies": fixture["authority_policies"],
        "lineages": fixture["lineages"],
        "relationships": fixture["relationships"],
        "revisions": fixture["revisions"],
        "tombstones": fixture["tombstones"],
    }


def validate_contract(contract: dict[str, Any]) -> None:
    require_keys(
        contract,
        {
            "schema",
            "design_status",
            "scope",
            "logical_ledgers",
            "writer_contract",
            "resolver_v0_compatibility",
            "snapshot_contract",
            "adapter_boundary",
            "required_negative_cases",
        },
        "contract",
    )
    if contract["schema"] != CONTRACT_SCHEMA or contract["design_status"] != DESIGN_STATUS:
        reject("contract_identity", "contract schema or design status drifted")

    expected_scope = {
        "design_only": True,
        "schema_migration_present": False,
        "runtime_writer_present": False,
        "store_adapter_present": False,
        "projector_invoked": False,
        "legacy_rows_qualified": False,
        "real_capture_authorized": False,
        "biocortex_runtime_influence": False,
    }
    if contract["scope"] != expected_scope:
        reject("scope_drift", "design-only scope changed")

    expected_fields = {
        "truth_lineages": [
            "lineage_id",
            "referent_id",
            "predicate_id",
            "created_at",
            "claim_identity_sha256",
        ],
        "truth_authority_policy_revisions": [
            "policy_revision_id",
            "policy_lineage_id",
            "revision_seq",
            "recorded_at",
            "predicate_id",
            "source_key",
            "resolved_truth_tier",
            "valid_from",
            "valid_until",
            "status",
        ],
        "truth_evidence_revisions": [
            "evidence_id",
            "lineage_id",
            "revision_seq",
            "value",
            "aliases",
            "observed_at",
            "recorded_at",
            "validity",
            "lifecycle",
            "source_bindings",
            "authority_policy_revision_id",
            "resolved_truth_tier",
        ],
        "truth_evidence_relationships": [
            "declared_evidence_id",
            "relationship_kind",
            "target_lineage_id",
            "effective_from",
        ],
        "truth_lineage_tombstones": [
            "tombstone_id",
            "lineage_id",
            "tombstoned_at",
            "had_outgoing_governance",
            "attestation_version",
            "attestation_sha256",
        ],
    }
    expected_primary_keys = {
        "truth_lineages": ["lineage_id"],
        "truth_authority_policy_revisions": ["policy_revision_id"],
        "truth_evidence_revisions": ["evidence_id"],
        "truth_evidence_relationships": [
            "declared_evidence_id",
            "relationship_kind",
            "target_lineage_id",
            "effective_from",
        ],
        "truth_lineage_tombstones": ["tombstone_id"],
    }
    expected_store_derived = {
        "truth_lineages": ["claim_identity_sha256"],
        "truth_authority_policy_revisions": ["revision_seq"],
        "truth_evidence_revisions": ["revision_seq", "resolved_truth_tier"],
        "truth_evidence_relationships": [],
        "truth_lineage_tombstones": ["had_outgoing_governance", "attestation_sha256"],
    }
    expected_foreign_keys = {
        "truth_lineages": [],
        "truth_authority_policy_revisions": [],
        "truth_evidence_revisions": [
            "lineage_id->truth_lineages.lineage_id",
            "authority_policy_revision_id->truth_authority_policy_revisions.policy_revision_id",
        ],
        "truth_evidence_relationships": [
            "declared_evidence_id->truth_evidence_revisions.evidence_id",
            "target_lineage_id->truth_lineages.lineage_id",
        ],
        "truth_lineage_tombstones": ["lineage_id->truth_lineages.lineage_id"],
    }
    ledgers = contract["logical_ledgers"]
    if not isinstance(ledgers, list) or len(ledgers) != len(expected_fields):
        reject("ledger_contract", "logical ledger count drifted")
    names = []
    for index, ledger in enumerate(ledgers):
        ledger = require_keys(
            ledger,
            {
                "name",
                "append_only",
                "primary_key",
                "fields",
                "store_derived_fields",
                "foreign_keys",
            },
            f"contract.logical_ledgers[{index}]",
        )
        name = require_label(ledger["name"], f"ledger[{index}].name")
        names.append(name)
        if name not in expected_fields or ledger["fields"] != expected_fields[name]:
            reject("ledger_contract", f"field contract drifted for {name}")
        if ledger["append_only"] is not True:
            reject("ledger_not_append_only", f"{name} must be append-only")
        if ledger["primary_key"] != expected_primary_keys[name]:
            reject("primary_key_contract_drift", f"primary key drifted for {name}")
        if ledger["store_derived_fields"] != expected_store_derived[name]:
            reject("store_derived_contract_drift", f"store-derived fields drifted for {name}")
        if ledger["foreign_keys"] != expected_foreign_keys[name]:
            reject("foreign_key_contract_drift", f"foreign keys drifted for {name}")
    if names != list(expected_fields):
        reject("ledger_contract", "logical ledger order or names drifted")

    expected_writer = {
        "single_immediate_transaction": True,
        "update_allowed": False,
        "delete_allowed": False,
        "revision_seq_store_allocated": True,
        "truth_tier_store_derived": True,
        "governance_attestation_store_derived": True,
        "unknown_authority_default": "reject",
        "authority_policy_identity_stable": True,
        "authority_policy_recorded_at": "strictly_increasing_by_revision_seq",
        "authority_policy_binding": "latest_visible_exact_revision",
        "authority_policy_pair_lineage": "unique_by_predicate_and_source",
        "relationship_tier_view": "strictly_before_source_recorded_at_latest_target_revision",
        "tombstone_after_revision_blocks_future_revision": True,
        "legacy_memory_backfill": "forbidden_without_separate_admission",
    }
    if contract["writer_contract"] != expected_writer:
        reject("writer_contract", "writer fail-closed contract drifted")

    expected_resolver = {
        "revision_seq_required": True,
        "recorded_at_unique_per_lineage": True,
        "revision_seq_substitutes_recorded_at": False,
        "same_recorded_at_allowed": False,
        "same_second_support_requires_resolver_v1": True,
        "cross_lineage_same_second_relationship_allowed": False,
        "world_clock_field": "observed_at",
        "knowledge_clock_field": "recorded_at",
        "validity_boundary": "inclusive",
        "relationship_target_grain": "lineage_id",
        "relationship_snapshot": "complete_per_revision_carry_forward",
    }
    if contract["resolver_v0_compatibility"] != expected_resolver:
        reject("resolver_contract", "resolver-v0 compatibility drifted")

    snapshot = require_keys(
        contract["snapshot_contract"],
        {
            "transaction",
            "required_sets",
            "hard_caps",
            "hard_cap_maxima",
            "fetch_plus_one",
            "truncation_terminal",
            "endpoint_nonclosure_terminal",
            "tombstone_index_incomplete_terminal",
            "relationship_channel_incomplete_terminal",
            "canonical_order",
            "canonical_digest",
            "producer_identity_fields",
        },
        "contract.snapshot_contract",
    )
    if (
        snapshot["transaction"] != "one_sqlite_read_transaction"
        or snapshot["fetch_plus_one"] is not True
        or snapshot["truncation_terminal"] is not True
        or snapshot["endpoint_nonclosure_terminal"] is not True
        or snapshot["tombstone_index_incomplete_terminal"] is not True
        or snapshot["relationship_channel_incomplete_terminal"] is not True
        or snapshot["canonical_order"] != CANONICAL_ORDER
        or snapshot["canonical_digest"] != "sha256_canonical_json_v0"
    ):
        reject("snapshot_contract", "snapshot fail-closed contract drifted")
    if snapshot["required_sets"] != names:
        reject("snapshot_contract", "snapshot required-set closure drifted")
    if snapshot["hard_caps"] != [
        "max_lineages",
        "max_policy_revisions",
        "max_evidence_revisions",
        "max_relationships",
        "max_tombstones",
        "max_payload_bytes",
    ]:
        reject("snapshot_contract", "snapshot cap contract drifted")
    if snapshot["hard_cap_maxima"] != HARD_CAP_MAXIMA:
        reject("unbounded_snapshot_caps", "snapshot cap maxima drifted")
    if snapshot["producer_identity_fields"] != [
        "schema_meta_version",
        "schema_digest",
        "migration_digest",
        "ledger_format_version",
    ]:
        reject("snapshot_contract", "producer identity contract drifted")

    expected_adapter = {
        "adapter_allowed": False,
        "current_mutable_profile_gaps_remain": 8,
        "caller_declared_tier_allowed": False,
        "memory_key_is_referent": False,
        "governed_tombstone_source_allowed": False,
        "raw_values_may_leave_agent_bridge": False,
        "new_producer_profile_reserved": False,
    }
    if contract["adapter_boundary"] != expected_adapter:
        reject("adapter_boundary", "adapter boundary drifted")
    if contract["required_negative_cases"] != NEGATIVE_CASES:
        reject("negative_case_contract", "negative-case preregistration drifted")


def validate_validity(validity: Any, path: str) -> tuple[str, int | None, int | None]:
    validity = require_keys(validity, {"kind", "valid_from", "valid_until"}, path)
    kind = validity["kind"]
    if kind not in ("timeless", "bounded", "indeterminate"):
        reject("invalid_validity", f"{path}.kind is unknown")
    lower = validity["valid_from"]
    upper = validity["valid_until"]
    for name, value in (("valid_from", lower), ("valid_until", upper)):
        if value is not None:
            require_int(value, f"{path}.{name}")
    if kind in ("timeless", "indeterminate") and (lower is not None or upper is not None):
        reject("invalid_validity", f"{path} {kind} cannot carry bounds")
    if kind == "bounded" and lower is None and upper is None:
        reject("invalid_validity", f"{path} bounded validity needs a bound")
    if lower is not None and upper is not None and lower > upper:
        reject("inverted_validity", f"{path} has inverted bounds")
    return kind, lower, upper


def validate_lifecycle(lifecycle: Any, path: str) -> tuple[str, int | None]:
    lifecycle = require_keys(lifecycle, {"state", "effective_from"}, path)
    state = lifecycle["state"]
    if state not in ("active", "superseded", "archived"):
        reject("invalid_lifecycle", f"{path}.state is unknown")
    effective = lifecycle["effective_from"]
    if state == "active":
        if effective is not None:
            reject("invalid_lifecycle", f"{path} active lifecycle cannot have effective_from")
    else:
        require_int(effective, f"{path}.effective_from")
    return state, effective


def active_at(revision: dict[str, Any], timestamp: int) -> bool:
    validity = revision["validity"]
    if validity["kind"] == "indeterminate":
        return False
    if validity["kind"] == "bounded":
        if validity["valid_from"] is not None and timestamp < validity["valid_from"]:
            return False
        if validity["valid_until"] is not None and timestamp > validity["valid_until"]:
            return False
    lifecycle = revision["lifecycle"]
    if lifecycle["state"] != "active" and timestamp >= lifecycle["effective_from"]:
        return False
    return True


def validate_fixture(fixture: dict[str, Any], *, check_expected: bool = True) -> dict[str, int]:
    require_keys(
        fixture,
        {
            "schema",
            "fixture_only",
            "real_capture_authorized",
            "legacy_rows_qualified",
            "adapter_allowed",
            "projector_invoked",
            "biocortex_runtime_influence",
            "lineages",
            "authority_policies",
            "revisions",
            "relationships",
            "tombstones",
            "snapshot",
            "expected",
        },
        "fixture",
    )
    if fixture["schema"] != FIXTURE_SCHEMA:
        reject("fixture_identity", "fixture schema drifted")
    expected_flags = {
        "fixture_only": True,
        "real_capture_authorized": False,
        "legacy_rows_qualified": False,
        "adapter_allowed": False,
        "projector_invoked": False,
        "biocortex_runtime_influence": False,
    }
    for name, expected in expected_flags.items():
        if fixture[name] is not expected:
            reject("fixture_authority", f"fixture.{name} must be {expected}")

    lineages_raw = fixture["lineages"]
    if not isinstance(lineages_raw, list) or not lineages_raw:
        reject("lineage_contract", "fixture.lineages must be non-empty")
    if lineages_raw != sorted(lineages_raw, key=lambda row: row.get("lineage_id", "")):
        reject("noncanonical_order", "lineages are not in binary id order")
    lineages: dict[str, dict[str, Any]] = {}
    for index, raw in enumerate(lineages_raw):
        row = require_keys(
            raw,
            {
                "lineage_id",
                "referent_id",
                "predicate_id",
                "created_at",
                "claim_identity_sha256",
            },
            f"fixture.lineages[{index}]",
        )
        lineage_id = require_label(row["lineage_id"], f"lineage[{index}].lineage_id")
        require_label(row["referent_id"], f"lineage[{index}].referent_id")
        require_label(row["predicate_id"], f"lineage[{index}].predicate_id")
        require_int(row["created_at"], f"lineage[{index}].created_at")
        require_hex64(row["claim_identity_sha256"], f"lineage[{index}].claim_identity_sha256")
        if row["claim_identity_sha256"] != claim_digest(row):
            reject("lineage_claim_drift", f"claim identity digest drifted for {lineage_id}")
        if lineage_id in lineages:
            reject("duplicate_lineage_id", lineage_id)
        lineages[lineage_id] = row

    policies_raw = fixture["authority_policies"]
    if not isinstance(policies_raw, list) or not policies_raw:
        reject("authority_policy", "authority_policies must be non-empty")
    policy_sort = lambda row: (
        row.get("policy_lineage_id", ""),
        row.get("revision_seq", -1),
        row.get("policy_revision_id", ""),
    )
    if policies_raw != sorted(policies_raw, key=policy_sort):
        reject("noncanonical_order", "authority policies are not canonical")
    policies: dict[str, dict[str, Any]] = {}
    policies_by_lineage: dict[str, list[dict[str, Any]]] = defaultdict(list)
    policy_pair_lineages: dict[tuple[str, str], set[str]] = defaultdict(set)
    for index, raw in enumerate(policies_raw):
        row = require_keys(
            raw,
            {
                "policy_revision_id",
                "policy_lineage_id",
                "revision_seq",
                "recorded_at",
                "predicate_id",
                "source_key",
                "resolved_truth_tier",
                "valid_from",
                "valid_until",
                "status",
            },
            f"fixture.authority_policies[{index}]",
        )
        policy_id = require_label(row["policy_revision_id"], f"policy[{index}].policy_revision_id")
        lineage_id = require_label(row["policy_lineage_id"], f"policy[{index}].policy_lineage_id")
        require_int(row["revision_seq"], f"policy[{index}].revision_seq", minimum=1)
        require_int(row["recorded_at"], f"policy[{index}].recorded_at")
        require_label(row["predicate_id"], f"policy[{index}].predicate_id")
        require_label(row["source_key"], f"policy[{index}].source_key")
        if row["resolved_truth_tier"] not in TIER_ORDER:
            reject("authority_policy", f"unknown tier for {policy_id}")
        if row["status"] not in ("active", "revoked"):
            reject("authority_policy", f"unknown status for {policy_id}")
        for bound in ("valid_from", "valid_until"):
            if row[bound] is not None:
                require_int(row[bound], f"policy[{index}].{bound}")
        if (
            row["valid_from"] is not None
            and row["valid_until"] is not None
            and row["valid_from"] > row["valid_until"]
        ):
            reject("authority_policy", f"inverted policy validity for {policy_id}")
        if policy_id in policies:
            reject("duplicate_policy_id", policy_id)
        policies[policy_id] = row
        policies_by_lineage[lineage_id].append(row)
        policy_pair_lineages[(row["predicate_id"], row["source_key"])].add(lineage_id)
    for lineage_id, rows in policies_by_lineage.items():
        seqs = [row["revision_seq"] for row in rows]
        if len(set(seqs)) != len(seqs) or seqs != list(range(1, len(rows) + 1)):
            reject("authority_policy", f"policy sequence is not contiguous for {lineage_id}")
        recorded = [row["recorded_at"] for row in rows]
        if any(current <= previous for previous, current in zip(recorded, recorded[1:])):
            reject("policy_recorded_at_regression", f"policy time regressed for {lineage_id}")
        if len({row["predicate_id"] for row in rows}) != 1:
            reject("authority_policy", f"policy predicate drifted for {lineage_id}")
        if len({row["source_key"] for row in rows}) != 1:
            reject("authority_policy", f"policy source drifted for {lineage_id}")
    for (predicate_id, source_key), lineage_ids in policy_pair_lineages.items():
        if len(lineage_ids) != 1:
            reject(
                "policy_tier_shopping",
                f"multiple policy lineages for {predicate_id}/{source_key}",
            )

    revisions_raw = fixture["revisions"]
    if not isinstance(revisions_raw, list) or not revisions_raw:
        reject("revision_contract", "revisions must be non-empty")
    revision_sort = lambda row: (
        row.get("lineage_id", ""),
        row.get("revision_seq", -1),
        row.get("evidence_id", ""),
    )
    if revisions_raw != sorted(revisions_raw, key=revision_sort):
        reject("noncanonical_order", "evidence revisions are not canonical")
    revisions: dict[str, dict[str, Any]] = {}
    revisions_by_lineage: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for index, raw in enumerate(revisions_raw):
        if isinstance(raw, dict) and ("truth_tier" in raw or "caller_truth_tier" in raw):
            reject("caller_declared_tier", f"revision[{index}] declares a caller tier")
        row = require_keys(
            raw,
            {
                "evidence_id",
                "lineage_id",
                "revision_seq",
                "value",
                "aliases",
                "observed_at",
                "recorded_at",
                "validity",
                "lifecycle",
                "source_bindings",
                "authority_policy_revision_id",
                "resolved_truth_tier",
            },
            f"fixture.revisions[{index}]",
        )
        evidence_id = require_label(row["evidence_id"], f"revision[{index}].evidence_id")
        lineage_id = require_label(row["lineage_id"], f"revision[{index}].lineage_id")
        if evidence_id in revisions:
            reject("duplicate_evidence_id", evidence_id)
        if lineage_id not in lineages:
            reject("missing_lineage", lineage_id)
        require_int(row["revision_seq"], f"revision[{index}].revision_seq", minimum=1)
        if not isinstance(row["value"], str) or not row["value"] or len(row["value"].encode()) > 262144:
            reject("invalid_value", evidence_id)
        if not isinstance(row["aliases"], list) or any(not isinstance(v, str) for v in row["aliases"]):
            reject("invalid_aliases", evidence_id)
        if row["aliases"] != sorted(set(row["aliases"])):
            reject("noncanonical_aliases", evidence_id)
        for alias_index, alias in enumerate(row["aliases"]):
            require_label(alias, f"revision[{index}].aliases[{alias_index}]")
        observed_at = require_int(row["observed_at"], f"revision[{index}].observed_at")
        recorded_at = require_int(row["recorded_at"], f"revision[{index}].recorded_at")
        if observed_at > recorded_at:
            reject("observation_after_recording", evidence_id)
        if lineages[lineage_id]["created_at"] > recorded_at:
            reject("revision_contract", f"{evidence_id} predates its lineage")
        validate_validity(row["validity"], f"revision[{index}].validity")
        validate_lifecycle(row["lifecycle"], f"revision[{index}].lifecycle")
        bindings = row["source_bindings"]
        if not isinstance(bindings, list) or not bindings:
            reject("missing_provenance", evidence_id)
        binding_sort = lambda binding: (
            binding.get("source_key", ""),
            binding.get("provenance_sha256", ""),
        )
        if bindings != sorted(bindings, key=binding_sort):
            reject("noncanonical_provenance", evidence_id)
        source_keys = set()
        for binding_index, binding in enumerate(bindings):
            binding = require_keys(
                binding,
                {"source_key", "provenance_sha256"},
                f"revision[{index}].source_bindings[{binding_index}]",
            )
            source_key = require_label(binding["source_key"], "source_binding.source_key")
            require_hex64(binding["provenance_sha256"], "source_binding.provenance_sha256")
            if source_key in source_keys:
                reject("duplicate_provenance", evidence_id)
            source_keys.add(source_key)
        policy_id = require_label(
            row["authority_policy_revision_id"],
            f"revision[{index}].authority_policy_revision_id",
        )
        if policy_id not in policies:
            reject("unknown_authority_policy", f"{evidence_id}->{policy_id}")
        policy = policies[policy_id]
        lineage = lineages[lineage_id]
        if policy["predicate_id"] != lineage["predicate_id"]:
            reject("authority_predicate_fallback", evidence_id)
        if policy["source_key"] not in source_keys:
            reject("authority_source_mismatch", evidence_id)
        if row["resolved_truth_tier"] != policy["resolved_truth_tier"]:
            reject("caller_declared_tier", f"resolved tier mismatch for {evidence_id}")
        visible_policies = [
            candidate
            for candidate in policies_by_lineage[policy["policy_lineage_id"]]
            if candidate["recorded_at"] <= recorded_at
        ]
        if not visible_policies:
            reject("authority_policy_inactive", evidence_id)
        latest_policy = visible_policies[-1]
        if latest_policy["policy_revision_id"] != policy_id:
            if latest_policy["status"] == "revoked":
                reject("policy_revocation_bypass", evidence_id)
            reject("authority_policy_stale", evidence_id)
        if policy["status"] != "active":
            reject("authority_policy_inactive", evidence_id)
        if policy["valid_from"] is not None and recorded_at < policy["valid_from"]:
            reject("authority_policy_inactive", evidence_id)
        if policy["valid_until"] is not None and recorded_at > policy["valid_until"]:
            reject("authority_policy_inactive", evidence_id)
        revisions[evidence_id] = row
        revisions_by_lineage[lineage_id].append(row)
    for lineage_id, rows in revisions_by_lineage.items():
        seqs = [row["revision_seq"] for row in rows]
        if len(set(seqs)) != len(seqs):
            reject("duplicate_revision_seq", lineage_id)
        if seqs != list(range(1, len(rows) + 1)):
            reject("missing_revision_seq", lineage_id)
        recorded = [row["recorded_at"] for row in rows]
        if len(set(recorded)) != len(recorded) or recorded != sorted(recorded):
            reject("ambiguous_recorded_at", lineage_id)

    relationships_raw = fixture["relationships"]
    if not isinstance(relationships_raw, list):
        reject("relationship_contract", "relationships must be an array")
    relationship_sort = lambda row: (
        row.get("declared_evidence_id", ""),
        row.get("relationship_kind", ""),
        row.get("target_lineage_id", ""),
        row.get("effective_from", -1),
    )
    if relationships_raw != sorted(relationships_raw, key=relationship_sort):
        reject("noncanonical_order", "relationships are not canonical")
    relationship_rows: list[dict[str, Any]] = []
    relation_tuples = set()
    by_evidence_target: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    by_evidence: dict[str, set[tuple[str, str, int]]] = defaultdict(set)
    for index, raw in enumerate(relationships_raw):
        row = require_keys(
            raw,
            {"declared_evidence_id", "relationship_kind", "target_lineage_id", "effective_from"},
            f"fixture.relationships[{index}]",
        )
        evidence_id = require_label(row["declared_evidence_id"], "relationship.declared_evidence_id")
        target_id = require_label(row["target_lineage_id"], "relationship.target_lineage_id")
        kind = row["relationship_kind"]
        if kind not in ("supersedes", "invalidates"):
            reject("relationship_contract", f"unknown relationship kind {kind!r}")
        effective = require_int(row["effective_from"], "relationship.effective_from")
        if evidence_id not in revisions:
            reject("missing_relationship_source", evidence_id)
        source_revision = revisions[evidence_id]
        source_lineage_id = source_revision["lineage_id"]
        if target_id not in lineages:
            reject("dangling_relationship", f"{evidence_id}->{target_id}")
        if source_lineage_id == target_id:
            reject("self_relationship", evidence_id)
        source_claim = (
            lineages[source_lineage_id]["referent_id"],
            lineages[source_lineage_id]["predicate_id"],
        )
        target_claim = (lineages[target_id]["referent_id"], lineages[target_id]["predicate_id"])
        if source_claim != target_claim:
            reject("cross_claim_relationship", f"{evidence_id}->{target_id}")
        if not active_at(source_revision, effective):
            reject("relationship_outside_source_activity", f"{evidence_id}->{target_id}")
        relation_tuple = (evidence_id, kind, target_id, effective)
        if relation_tuple in relation_tuples:
            reject("duplicate_relationship", f"{evidence_id}->{target_id}")
        relation_tuples.add(relation_tuple)
        by_evidence_target[(evidence_id, target_id)].append(row)
        by_evidence[evidence_id].add((kind, target_id, effective))
        relationship_rows.append(row)
    for (evidence_id, target_id), rows in by_evidence_target.items():
        if len({row["relationship_kind"] for row in rows}) > 1:
            reject("dual_relationship_kind", f"{evidence_id}->{target_id}")
        if len({row["effective_from"] for row in rows}) > 1:
            reject("conflicting_relationship_time", f"{evidence_id}->{target_id}")

    latest_by_lineage = {lineage_id: rows[-1] for lineage_id, rows in revisions_by_lineage.items()}
    for row in relationship_rows:
        source = revisions[row["declared_evidence_id"]]
        same_second_targets = [
            revision
            for revision in revisions_by_lineage[row["target_lineage_id"]]
            if revision["recorded_at"] == source["recorded_at"]
        ]
        if same_second_targets:
            reject(
                "same_second_target_ambiguity",
                f"{source['evidence_id']}->{row['target_lineage_id']}",
            )
        visible_targets = [
            revision
            for revision in revisions_by_lineage[row["target_lineage_id"]]
            if revision["recorded_at"] < source["recorded_at"]
        ]
        if not visible_targets:
            reject(
                "relationship_target_not_visible",
                f"{source['evidence_id']}->{row['target_lineage_id']}",
            )
        target = visible_targets[-1]
        if TIER_ORDER[source["resolved_truth_tier"]] < TIER_ORDER[target["resolved_truth_tier"]]:
            reject(
                "lower_tier_suppression",
                f"{source['evidence_id']}->{row['target_lineage_id']}",
            )

    for lineage_id, rows in revisions_by_lineage.items():
        durable: set[tuple[str, str, int]] = set()
        for revision in rows:
            current = by_evidence.get(revision["evidence_id"], set())
            if not durable.issubset(current):
                reject("dropped_relationship", f"{lineage_id}:{revision['evidence_id']}")
            durable = set(current)

    adjacency: dict[str, set[str]] = {lineage_id: set() for lineage_id in lineages}
    for lineage_id, revision in latest_by_lineage.items():
        for _, target_id, _ in by_evidence.get(revision["evidence_id"], set()):
            adjacency[lineage_id].add(target_id)
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(node: str) -> None:
        if node in visiting:
            reject("relationship_cycle", node)
        if node in visited:
            return
        visiting.add(node)
        for target in sorted(adjacency[node]):
            visit(target)
        visiting.remove(node)
        visited.add(node)

    for lineage_id in sorted(lineages):
        visit(lineage_id)

    tombstones_raw = fixture["tombstones"]
    if not isinstance(tombstones_raw, list):
        reject("tombstone_contract", "tombstones must be an array")
    if tombstones_raw != sorted(
        tombstones_raw,
        key=lambda row: (row.get("lineage_id", ""), row.get("tombstone_id", "")),
    ):
        reject("noncanonical_order", "tombstones are not canonical")
    tombstone_ids = set()
    tombstoned_lineages: dict[str, dict[str, Any]] = {}
    for index, raw in enumerate(tombstones_raw):
        if isinstance(raw, dict) and any(
            key in raw for key in ("value", "content", "aliases", "source_bindings")
        ):
            reject("tombstone_content_leak", f"tombstone[{index}] contains content")
        if isinstance(raw, dict) and "had_outgoing_governance" not in raw:
            reject("missing_governance_attestation", f"tombstone[{index}]")
        row = require_keys(
            raw,
            {
                "tombstone_id",
                "lineage_id",
                "tombstoned_at",
                "had_outgoing_governance",
                "attestation_version",
                "attestation_sha256",
            },
            f"fixture.tombstones[{index}]",
        )
        tombstone_id = require_label(row["tombstone_id"], f"tombstone[{index}].tombstone_id")
        lineage_id = require_label(row["lineage_id"], f"tombstone[{index}].lineage_id")
        if tombstone_id in tombstone_ids or lineage_id in tombstoned_lineages:
            reject("duplicate_tombstone", lineage_id)
        if lineage_id not in lineages or lineage_id not in revisions_by_lineage:
            reject("dangling_tombstone", lineage_id)
        tombstoned_at = require_int(row["tombstoned_at"], f"tombstone[{index}].tombstoned_at")
        if tombstoned_at < revisions_by_lineage[lineage_id][-1]["recorded_at"]:
            reject("tombstone_before_revision", lineage_id)
        require_bool(row["had_outgoing_governance"], "tombstone.had_outgoing_governance")
        actual_governed = any(
            revisions[rel["declared_evidence_id"]]["lineage_id"] == lineage_id
            for rel in relationship_rows
        )
        if row["had_outgoing_governance"] != actual_governed:
            reject("governance_attestation_mismatch", lineage_id)
        if row["attestation_version"] != ATTESTATION_VERSION:
            reject("tombstone_contract", f"attestation version drifted for {lineage_id}")
        require_hex64(row["attestation_sha256"], "tombstone.attestation_sha256")
        if row["attestation_sha256"] != tombstone_digest(row):
            reject("governance_attestation_hash", lineage_id)
        tombstone_ids.add(tombstone_id)
        tombstoned_lineages[lineage_id] = row

    snapshot = require_keys(
        fixture["snapshot"],
        {
            "ledger_format_version",
            "producer_profile",
            "producer_profile_bound",
            "schema_meta_version",
            "schema_digest",
            "migration_digest",
            "transaction",
            "knowledge_cutoff",
            "caps",
            "counts",
            "truncated",
            "endpoint_closure",
            "tombstone_index_complete",
            "relationship_channels_complete",
            "canonical_order",
            "payload_sha256",
        },
        "fixture.snapshot",
    )
    if snapshot["ledger_format_version"] != 0:
        reject("snapshot_identity", "ledger format must be synthetic v0")
    if snapshot["producer_profile"] != "synthetic_design_fixture_only":
        reject("snapshot_identity", "synthetic producer profile drifted")
    if snapshot["producer_profile_bound"] is not False:
        reject("snapshot_identity", "synthetic fixture cannot bind a producer profile")
    if snapshot["schema_meta_version"] != "synthetic-unbound":
        reject("snapshot_identity", "synthetic fixture cannot attest schema_meta")
    require_hex64(snapshot["schema_digest"], "snapshot.schema_digest")
    require_hex64(snapshot["migration_digest"], "snapshot.migration_digest")
    if snapshot["transaction"] != "one_read_transaction":
        reject("snapshot_contract", "fixture transaction mode drifted")
    cutoff = require_int(snapshot["knowledge_cutoff"], "snapshot.knowledge_cutoff")
    caps = require_keys(
        snapshot["caps"],
        {
            "max_lineages",
            "max_policy_revisions",
            "max_evidence_revisions",
            "max_relationships",
            "max_tombstones",
            "max_payload_bytes",
        },
        "fixture.snapshot.caps",
    )
    for key, value in caps.items():
        require_int(value, f"snapshot.caps.{key}", minimum=1)
        if value > HARD_CAP_MAXIMA[key]:
            reject("unbounded_snapshot_caps", f"snapshot.caps.{key} exceeds design maximum")
    actual_counts = {
        "lineages": len(lineages_raw),
        "policy_revisions": len(policies_raw),
        "evidence_revisions": len(revisions_raw),
        "relationships": len(relationships_raw),
        "tombstones": len(tombstones_raw),
    }
    counts = require_keys(snapshot["counts"], set(actual_counts), "fixture.snapshot.counts")
    if counts != actual_counts:
        reject("snapshot_count_drift", "snapshot counts do not match payload")
    cap_map = {
        "lineages": "max_lineages",
        "policy_revisions": "max_policy_revisions",
        "evidence_revisions": "max_evidence_revisions",
        "relationships": "max_relationships",
        "tombstones": "max_tombstones",
    }
    for count_name, cap_name in cap_map.items():
        if counts[count_name] >= caps[cap_name]:
            reject("snapshot_cap_exhausted", f"{count_name} does not leave fetch+1 room")
    payload = snapshot_payload(fixture)
    if len(canonical_bytes(payload)) >= caps["max_payload_bytes"]:
        reject("snapshot_cap_exhausted", "payload does not leave byte headroom")
    if snapshot["truncated"] is not False:
        reject("snapshot_truncated", "synthetic snapshot is truncated")
    if snapshot["endpoint_closure"] is not True:
        reject("endpoint_nonclosure", "snapshot endpoint closure is false")
    if snapshot["tombstone_index_complete"] is not True:
        reject("tombstone_index_incomplete", "tombstone index is incomplete")
    if snapshot["relationship_channels_complete"] is not True:
        reject("relationship_channels_incomplete", "relationship channels are incomplete")
    if snapshot["canonical_order"] != CANONICAL_ORDER:
        reject("snapshot_contract", "canonical order drifted")
    require_hex64(snapshot["payload_sha256"], "snapshot.payload_sha256")
    if snapshot["payload_sha256"] != sha256_json(payload):
        reject("canonical_payload_hash_drift", "snapshot payload hash drifted")

    if check_expected:
        expected = require_keys(
            fixture["expected"],
            {
                "two_revision_lineage",
                "relationship_carry_forward",
                "late_backfill_evidence_id",
                "late_backfill_visible_at_cutoff",
                "same_referent_predicates",
                "supersession_source_evidence_id",
                "supersession_target_lineage_id",
                "supersession_effective_from",
                "pre_boundary_target_suppressed",
                "at_boundary_target_suppressed",
                "same_tier_conflict_evidence_ids",
                "lower_tier_evidence_id",
                "tombstoned_target_pruned",
                "governed_tombstone_lineage",
                "governed_tombstone_adapter_allowed",
            },
            "fixture.expected",
        )
        two_lineage = expected["two_revision_lineage"]
        if [row["revision_seq"] for row in revisions_by_lineage.get(two_lineage, [])] != [1, 2]:
            reject("expected_control", "two-revision control is not live")
        carry_ids = expected["relationship_carry_forward"]
        if carry_ids != ["employment-new-v1", "employment-new-v2"]:
            reject("expected_control", "carry-forward ids drifted")
        carry_sets = [by_evidence.get(evidence_id, set()) for evidence_id in carry_ids]
        if not carry_sets[0] or carry_sets[0] != carry_sets[1]:
            reject("expected_control", "carry-forward control is not exact")
        late_id = expected["late_backfill_evidence_id"]
        late_visible = revisions.get(late_id, {}).get("recorded_at", 0) <= cutoff
        if late_visible != expected["late_backfill_visible_at_cutoff"] or late_visible:
            reject("expected_control", "late-backfill cutoff control drifted")
        predicates = sorted(
            {
                row["predicate_id"]
                for row in lineages.values()
                if row["referent_id"] == "employee:alice"
            }
        )
        if predicates != expected["same_referent_predicates"]:
            reject("expected_control", "same-referent predicate control drifted")
        source_id = expected["supersession_source_evidence_id"]
        target_id = expected["supersession_target_lineage_id"]
        effective = expected["supersession_effective_from"]
        relation = ("supersedes", target_id, effective)
        if relation not in by_evidence.get(source_id, set()):
            reject("expected_control", "supersession boundary control is missing")
        if expected["pre_boundary_target_suppressed"] is not (effective <= effective - 1):
            reject("expected_control", "pre-boundary suppression expectation drifted")
        if expected["at_boundary_target_suppressed"] is not (effective <= effective):
            reject("expected_control", "at-boundary suppression expectation drifted")
        conflict_ids = expected["same_tier_conflict_evidence_ids"]
        if conflict_ids != sorted(conflict_ids) or len(conflict_ids) != 2:
            reject("expected_control", "same-tier conflict ids are not canonical")
        conflict_rows = [revisions.get(evidence_id) for evidence_id in conflict_ids]
        if any(row is None for row in conflict_rows):
            reject("expected_control", "same-tier conflict evidence is missing")
        if (
            len({row["resolved_truth_tier"] for row in conflict_rows}) != 1
            or len({row["value"] for row in conflict_rows}) != 2
            or len({lineages[row["lineage_id"]]["predicate_id"] for row in conflict_rows}) != 1
        ):
            reject("expected_control", "same-tier conflict control is not live")
        lower = revisions.get(expected["lower_tier_evidence_id"])
        if lower is None or TIER_ORDER[lower["resolved_truth_tier"]] >= TIER_ORDER[conflict_rows[0]["resolved_truth_tier"]]:
            reject("expected_control", "policy hierarchy control is not live")
        pruned = expected["tombstoned_target_pruned"]
        if pruned not in tombstoned_lineages or not any(
            row["target_lineage_id"] == pruned for row in relationship_rows
        ):
            reject("expected_control", "tombstoned inbound-target control is not live")
        governed = expected["governed_tombstone_lineage"]
        if (
            governed not in tombstoned_lineages
            or tombstoned_lineages[governed]["had_outgoing_governance"] is not True
            or expected["governed_tombstone_adapter_allowed"] is not False
        ):
            reject("expected_control", "governed tombstone fail-closed control drifted")

    return {
        "lineages": len(lineages),
        "policy_revisions": len(policies),
        "evidence_revisions": len(revisions),
        "relationships": len(relationship_rows),
        "tombstones": len(tombstoned_lineages),
    }


def reseal(fixture: dict[str, Any], *, refresh_claims: bool = False, refresh_tombstones: bool = False) -> None:
    if refresh_claims:
        for lineage in fixture["lineages"]:
            lineage["claim_identity_sha256"] = claim_digest(lineage)
    if refresh_tombstones:
        for tombstone in fixture["tombstones"]:
            tombstone["attestation_sha256"] = tombstone_digest(tombstone)
    snapshot = fixture["snapshot"]
    snapshot["counts"] = {
        "lineages": len(fixture["lineages"]),
        "policy_revisions": len(fixture["authority_policies"]),
        "evidence_revisions": len(fixture["revisions"]),
        "relationships": len(fixture["relationships"]),
        "tombstones": len(fixture["tombstones"]),
    }
    snapshot["payload_sha256"] = sha256_json(snapshot_payload(fixture))


def find_row(rows: list[dict[str, Any]], field: str, value: str) -> dict[str, Any]:
    for row in rows:
        if row.get(field) == value:
            return row
    raise AssertionError(f"fixture row {field}={value!r} not found")


def run_negative_cases(pristine_contract: dict[str, Any], pristine: dict[str, Any]) -> None:
    cases: list[tuple[str, str, str, Callable[[dict[str, Any]], None]]] = []

    def add(name: str, code: str, mutate: Callable[[dict[str, Any]], None]) -> None:
        cases.append((name, code, "fixture", mutate))

    def add_contract(name: str, code: str, mutate: Callable[[dict[str, Any]], None]) -> None:
        cases.append((name, code, "contract", mutate))

    add_contract(
        "primary_key_contract_drift",
        "primary_key_contract_drift",
        lambda c: c["logical_ledgers"][0].__setitem__("primary_key", []),
    )
    add_contract(
        "foreign_key_contract_drift",
        "foreign_key_contract_drift",
        lambda c: c["logical_ledgers"][2].__setitem__("foreign_keys", []),
    )
    add_contract(
        "store_derived_contract_drift",
        "store_derived_contract_drift",
        lambda c: c["logical_ledgers"][2].__setitem__("store_derived_fields", []),
    )

    add(
        "duplicate_revision_seq",
        "duplicate_revision_seq",
        lambda f: find_row(f["revisions"], "evidence_id", "employment-new-v2").__setitem__("revision_seq", 1),
    )
    add(
        "missing_revision_seq",
        "missing_revision_seq",
        lambda f: find_row(f["revisions"], "evidence_id", "employment-new-v2").__setitem__("revision_seq", 3),
    )

    def ambiguous_recorded(f: dict[str, Any]) -> None:
        row = find_row(f["revisions"], "evidence_id", "employment-new-v2")
        row["observed_at"] = 140
        row["recorded_at"] = 150

    add("ambiguous_recorded_at", "ambiguous_recorded_at", ambiguous_recorded)
    add(
        "lineage_claim_drift",
        "lineage_claim_drift",
        lambda f: find_row(f["lineages"], "lineage_id", "employment-current").__setitem__(
            "predicate_id", "employment.status"
        ),
    )

    def drop_relationship(f: dict[str, Any]) -> None:
        f["relationships"] = [
            row for row in f["relationships"] if row["declared_evidence_id"] != "employment-new-v2"
        ]

    add("dropped_relationship", "dropped_relationship", drop_relationship)
    add(
        "dangling_relationship",
        "dangling_relationship",
        lambda f: f["relationships"][0].__setitem__("target_lineage_id", "missing-lineage"),
    )
    add(
        "self_relationship",
        "self_relationship",
        lambda f: f["relationships"][0].__setitem__("target_lineage_id", "employment-current"),
    )

    def add_cycle(f: dict[str, Any]) -> None:
        revision = copy.deepcopy(
            find_row(f["revisions"], "evidence_id", "employment-old-v1")
        )
        revision["evidence_id"] = "employment-old-v2"
        revision["revision_seq"] = 2
        revision["observed_at"] = 185
        revision["recorded_at"] = 190
        f["revisions"].append(revision)
        f["revisions"].sort(
            key=lambda item: (
                item["lineage_id"],
                item["revision_seq"],
                item["evidence_id"],
            )
        )
        f["relationships"].append(
            {
                "declared_evidence_id": "employment-old-v2",
                "relationship_kind": "supersedes",
                "target_lineage_id": "employment-current",
                "effective_from": 190,
            }
        )
        f["relationships"].sort(
            key=lambda row: (
                row["declared_evidence_id"],
                row["relationship_kind"],
                row["target_lineage_id"],
                row["effective_from"],
            )
        )

    add("relationship_cycle", "relationship_cycle", add_cycle)
    add(
        "cross_claim_relationship",
        "cross_claim_relationship",
        lambda f: f["relationships"][0].__setitem__("target_lineage_id", "status-primary"),
    )

    def add_dual_kind(f: dict[str, Any]) -> None:
        row = copy.deepcopy(f["relationships"][1])
        row["relationship_kind"] = "invalidates"
        f["relationships"].append(row)
        f["relationships"].sort(
            key=lambda item: (
                item["declared_evidence_id"],
                item["relationship_kind"],
                item["target_lineage_id"],
                item["effective_from"],
            )
        )

    add("dual_relationship_kind", "dual_relationship_kind", add_dual_kind)

    def add_conflicting_time(f: dict[str, Any]) -> None:
        row = copy.deepcopy(f["relationships"][1])
        row["effective_from"] = 201
        f["relationships"].append(row)
        f["relationships"].sort(
            key=lambda item: (
                item["declared_evidence_id"],
                item["relationship_kind"],
                item["target_lineage_id"],
                item["effective_from"],
            )
        )

    add("conflicting_relationship_time", "conflicting_relationship_time", add_conflicting_time)

    def lower_tier(f: dict[str, Any]) -> None:
        row = find_row(f["revisions"], "evidence_id", "status-correction-v1")
        row["authority_policy_revision_id"] = "policy-status-user-v1"
        row["resolved_truth_tier"] = "observed"
        row["source_bindings"] = [
            {
                "source_key": "source:user-statement",
                "provenance_sha256": "dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd",
            }
        ]

    add("lower_tier_suppression", "lower_tier_suppression", lower_tier)
    add(
        "missing_provenance",
        "missing_provenance",
        lambda f: find_row(f["revisions"], "evidence_id", "status-primary-v1").__setitem__(
            "source_bindings", []
        ),
    )
    add(
        "caller_declared_tier",
        "caller_declared_tier",
        lambda f: find_row(f["revisions"], "evidence_id", "status-primary-v1").__setitem__(
            "truth_tier", "authoritative"
        ),
    )
    add(
        "unknown_authority_policy",
        "unknown_authority_policy",
        lambda f: find_row(f["revisions"], "evidence_id", "status-primary-v1").__setitem__(
            "authority_policy_revision_id", "policy-missing-v1"
        ),
    )

    def predicate_fallback(f: dict[str, Any]) -> None:
        row = find_row(f["revisions"], "evidence_id", "status-primary-v1")
        row["authority_policy_revision_id"] = "policy-employment-v1"
        row["resolved_truth_tier"] = "authoritative"
        row["source_bindings"] = [
            {
                "source_key": "source:hr-registry",
                "provenance_sha256": "eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee",
            }
        ]

    add("authority_predicate_fallback", "authority_predicate_fallback", predicate_fallback)

    def revoke_policy(f: dict[str, Any]) -> None:
        row = copy.deepcopy(
            find_row(f["authority_policies"], "policy_revision_id", "policy-employment-v1")
        )
        row["policy_revision_id"] = "policy-employment-v2"
        row["revision_seq"] = 2
        row["recorded_at"] = 140
        row["status"] = "revoked"
        f["authority_policies"].append(row)
        f["authority_policies"].sort(
            key=lambda item: (
                item["policy_lineage_id"],
                item["revision_seq"],
                item["policy_revision_id"],
            )
        )

    add("policy_revocation_bypass", "policy_revocation_bypass", revoke_policy)

    def regress_policy_time(f: dict[str, Any]) -> None:
        row = copy.deepcopy(
            find_row(f["authority_policies"], "policy_revision_id", "policy-employment-v1")
        )
        row["policy_revision_id"] = "policy-employment-v2"
        row["revision_seq"] = 2
        row["recorded_at"] = 5
        f["authority_policies"].append(row)
        f["authority_policies"].sort(
            key=lambda item: (
                item["policy_lineage_id"],
                item["revision_seq"],
                item["policy_revision_id"],
            )
        )

    add("policy_recorded_at_regression", "policy_recorded_at_regression", regress_policy_time)

    def add_policy_tier_shop(f: dict[str, Any]) -> None:
        row = copy.deepcopy(
            find_row(f["authority_policies"], "policy_revision_id", "policy-status-ops-v1")
        )
        row["policy_revision_id"] = "policy-status-ops-shadow-v1"
        row["policy_lineage_id"] = "policy-status-ops-shadow"
        row["resolved_truth_tier"] = "authoritative"
        f["authority_policies"].append(row)
        f["authority_policies"].sort(
            key=lambda item: (
                item["policy_lineage_id"],
                item["revision_seq"],
                item["policy_revision_id"],
            )
        )

    add("policy_tier_shopping", "policy_tier_shopping", add_policy_tier_shop)
    add(
        "observation_after_recording",
        "observation_after_recording",
        lambda f: find_row(f["revisions"], "evidence_id", "status-primary-v1").__setitem__(
            "observed_at", 121
        ),
    )

    def invert_validity(f: dict[str, Any]) -> None:
        row = find_row(f["revisions"], "evidence_id", "employment-old-v1")
        row["validity"]["valid_from"] = 200
        row["validity"]["valid_until"] = 199

    add("inverted_validity", "inverted_validity", invert_validity)
    add(
        "missing_governance_attestation",
        "missing_governance_attestation",
        lambda f: f["tombstones"][1].pop("had_outgoing_governance"),
    )
    add(
        "tombstone_content_leak",
        "tombstone_content_leak",
        lambda f: f["tombstones"][0].__setitem__("value", "must-not-survive"),
    )

    def later_target_downgrade(f: dict[str, Any]) -> None:
        source = find_row(f["revisions"], "evidence_id", "status-correction-v1")
        source["authority_policy_revision_id"] = "policy-status-user-v1"
        source["resolved_truth_tier"] = "observed"
        source["source_bindings"] = [
            {
                "source_key": "source:user-statement",
                "provenance_sha256": "ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff",
            }
        ]
        target = copy.deepcopy(find_row(f["revisions"], "evidence_id", "status-peer-v1"))
        target["evidence_id"] = "status-peer-v2"
        target["revision_seq"] = 2
        target["value"] = "inactive-later-observation"
        target["observed_at"] = 225
        target["recorded_at"] = 230
        target["authority_policy_revision_id"] = "policy-status-user-v1"
        target["resolved_truth_tier"] = "observed"
        target["source_bindings"] = [
            {
                "source_key": "source:user-statement",
                "provenance_sha256": "abababababababababababababababababababababababababababababababab",
            }
        ]
        f["revisions"].append(target)
        f["revisions"].sort(
            key=lambda item: (
                item["lineage_id"],
                item["revision_seq"],
                item["evidence_id"],
            )
        )

    add("later_target_downgrade", "lower_tier_suppression", later_target_downgrade)

    def same_second_target_downgrade(f: dict[str, Any]) -> None:
        source = find_row(f["revisions"], "evidence_id", "status-correction-v1")
        source["authority_policy_revision_id"] = "policy-status-user-v1"
        source["resolved_truth_tier"] = "observed"
        source["source_bindings"] = [
            {
                "source_key": "source:user-statement",
                "provenance_sha256": "cdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcd",
            }
        ]
        target = copy.deepcopy(find_row(f["revisions"], "evidence_id", "status-peer-v1"))
        target["evidence_id"] = "status-peer-v2"
        target["revision_seq"] = 2
        target["value"] = "same-second-ambiguous-observation"
        target["observed_at"] = 199
        target["recorded_at"] = 200
        target["authority_policy_revision_id"] = "policy-status-user-v1"
        target["resolved_truth_tier"] = "observed"
        target["source_bindings"] = [
            {
                "source_key": "source:user-statement",
                "provenance_sha256": "dededededededededededededededededededededededededededededededede",
            }
        ]
        f["revisions"].append(target)
        f["revisions"].sort(
            key=lambda item: (
                item["lineage_id"],
                item["revision_seq"],
                item["evidence_id"],
            )
        )

    add(
        "same_second_target_downgrade",
        "same_second_target_ambiguity",
        same_second_target_downgrade,
    )
    add(
        "snapshot_truncated",
        "snapshot_truncated",
        lambda f: f["snapshot"].__setitem__("truncated", True),
    )
    add(
        "endpoint_nonclosure",
        "endpoint_nonclosure",
        lambda f: f["snapshot"].__setitem__("endpoint_closure", False),
    )
    add_contract(
        "unbounded_snapshot_caps",
        "unbounded_snapshot_caps",
        lambda c: c["snapshot_contract"].__setitem__(
            "hard_cap_maxima", {key: 10**15 for key in HARD_CAP_MAXIMA}
        ),
    )

    def payload_hash_drift(f: dict[str, Any]) -> None:
        f["snapshot"]["payload_sha256"] = "0" * 64

    add("canonical_payload_hash_drift", "canonical_payload_hash_drift", payload_hash_drift)

    def reverse_lineages(f: dict[str, Any]) -> None:
        f["lineages"].reverse()

    add("noncanonical_order", "noncanonical_order", reverse_lineages)

    def duplicate_evidence(f: dict[str, Any]) -> None:
        row = find_row(f["revisions"], "evidence_id", "status-late-v1")
        row["evidence_id"] = "status-primary-v1"

    add("duplicate_evidence_id", "duplicate_evidence_id", duplicate_evidence)
    add("unknown_field", "unknown_field", lambda f: f.__setitem__("runtime_enable", True))

    if [name for name, _, _, _ in cases] != NEGATIVE_CASES[:-1]:
        raise AssertionError("negative mutation implementation drifted")

    for name, expected_code, target, mutate in cases:
        candidate = copy.deepcopy(pristine_contract if target == "contract" else pristine)
        mutate(candidate)
        if target == "fixture" and name not in {
            "canonical_payload_hash_drift",
            "snapshot_truncated",
            "endpoint_nonclosure",
            "unknown_field",
        }:
            reseal(candidate)
        try:
            if target == "contract":
                validate_contract(candidate)
            else:
                validate_fixture(candidate, check_expected=False)
        except ValidationError as exc:
            if exc.code != expected_code:
                raise AssertionError(
                    f"negative case {name} rejected as {exc.code}, expected {expected_code}: {exc.detail}"
                ) from exc
        else:
            raise AssertionError(f"negative case {name} was accepted")

    duplicate_key_json = '{"schema":"x","schema":"y"}'
    try:
        json.loads(duplicate_key_json, object_pairs_hook=strict_object)
    except ValidationError as exc:
        if exc.code != "duplicate_json_key":
            raise AssertionError("duplicate JSON key rejected with wrong code") from exc
    else:
        raise AssertionError("duplicate JSON key was accepted")


def emit_receipt(metrics: dict[str, int]) -> None:
    sentinels_cleared = all(name not in os.environ for name in SENTINELS)
    if not sentinels_cleared:
        reject("environment_not_clean", "hostile sentinel reached checker")
    rows = [
        ("schema", RECEIPT_SCHEMA),
        ("design_status", DESIGN_STATUS),
        ("fixture_only", "true"),
        ("contract_valid", "true"),
        ("synthetic_fixture_valid", "true"),
        ("negative_cases_rejected", str(len(NEGATIVE_CASES))),
        ("lineages", str(metrics["lineages"])),
        ("policy_revisions", str(metrics["policy_revisions"])),
        ("evidence_revisions", str(metrics["evidence_revisions"])),
        ("relationships", str(metrics["relationships"])),
        ("tombstones", str(metrics["tombstones"])),
        ("append_only_revision_model", "true"),
        ("revision_sequence_and_v0_time_unique", "true"),
        ("dual_clock_bound", "true"),
        ("relationship_history_complete", "true"),
        ("governance_attestation_permanent", "true"),
        ("predicate_authority_default_deny", "true"),
        ("snapshot_complete_and_bounded", "true"),
        ("schema_migration_present", "false"),
        ("runtime_writer_present", "false"),
        ("store_adapter_present", "false"),
        ("projector_invoked", "false"),
        ("legacy_rows_qualified", "false"),
        ("adapter_allowed", "false"),
        ("real_capture_authorized", "false"),
        ("biocortex_runtime_influence", "false"),
        ("sentinels_cleared", "true"),
        ("decision", "BLOCKED_FAIL_CLOSED"),
    ]
    for key, value in rows:
        print(f"{key}\t{value}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--contract", type=Path, required=True)
    parser.add_argument("--fixture", type=Path, required=True)
    args = parser.parse_args()
    try:
        contract = load_strict(args.contract)
        fixture = load_strict(args.fixture)
        validate_contract(contract)
        metrics = validate_fixture(fixture)
        run_negative_cases(contract, fixture)
        emit_receipt(metrics)
    except (ValidationError, AssertionError) as exc:
        print(f"S1 evidence-substrate design check failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
