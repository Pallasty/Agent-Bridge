#!/usr/bin/env python3
"""Check the source-bound, synthetic-only S2 evidence-substrate packet."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any


CONTRACT_SCHEMA = "agent_bridge.memory_temporal_evidence_substrate_implementation.v0"
FIXTURE_SCHEMA = "agent_bridge.memory_temporal_evidence_substrate_s2_synthetic.v0"
RECEIPT_SCHEMA = "agent_bridge.memory_temporal_evidence_substrate_s2_receipt.v0"
STATUS = "READY_FOR_SEPARATE_S3_ADAPTER_REVIEW"
DECISION = "BLOCKED_FAIL_CLOSED"
TABLES = [
    "truth_lineages",
    "truth_authority_policy_revisions",
    "truth_evidence_revisions",
    "truth_evidence_relationships",
    "truth_lineage_tombstones",
]
CAPS = {
    "max_lineages": 10_000,
    "max_policy_revisions": 10_000,
    "max_evidence_revisions": 10_000,
    "max_relationships": 50_000,
    "max_tombstones": 10_000,
    "max_payload_bytes": 16_777_216,
}
S1_SHA256 = {
    "docs/design/MEMORY_TEMPORAL_EVIDENCE_SUBSTRATE_S1_2026_07_14.md": "e4425eabc6eb801525cfc98fb70ce70f45d1a814d93e00e74006650052284a63",
    "docs/reports/goal-c-u/2026-07-14-biocortex-ab-track-b-evidence-substrate-s1.md": "5818f03fa7a233e89e6844775b752e741ef525b4b0fd832bfd1c761596cc2c30",
    "scripts/check-memory-temporal-evidence-substrate-s1.sh": "6094054796c6181d3048f4fef21b50072e512f1ebcf78e2ccca9bdc78ba06cae",
    "scripts/eval/check_memory_temporal_evidence_substrate_s1.py": "6137281fd2920cb09467d2c93d462a0bd515ad35d81625e86875c45dd15be13c",
    "scripts/eval/fixtures/memory_temporal_evidence_substrate_s1.expected.v0.tsv": "56fa48154222c55547af34734749a91a9c927c47280867a8b059bbc41f0fa233",
    "scripts/eval/fixtures/memory_temporal_evidence_substrate_s1_contract_v0.json": "67f05ef574960a0d46db9313b7c8a498c41531c22d6d546f7741617a0c250fe5",
    "scripts/eval/fixtures/memory_temporal_evidence_substrate_s1_synthetic_v0.json": "fea71602105364ca41df936d04981c6238fb9955ed69d8de9e0256a08c679a6a",
}
ADAPTER_SHA256 = "c459e96919778c24b0bc699653d8c12b83332e6318b7298deee071a01e90e023"
GAPS = [
    "CompleteLineageRevisionHistoryUnavailable",
    "UniqueLineageRevisionOrderUnavailable",
    "CompleteTombstoneGovernanceIndexUnavailable",
    "AllRelationshipChannelsAndHistoryUnavailable",
    "RelationshipEndpointClosureUnprovable",
    "DurableGovernanceAttestationUnavailable",
    "ExplicitTemporalClaimProvenanceBindingsUnavailable",
    "PredicateScopedAuthorityPolicyUnavailable",
]
REJECTION_CODES = [
    "truth_evidence_identity",
    "truth_evidence_migration_collision",
    "truth_evidence_policy_not_latest_visible",
    "truth_evidence_same_second_target_ambiguity",
    "truth_evidence_lower_tier_suppression",
    "truth_evidence_relationship_cycle",
    "truth_evidence_dropped_relationship",
    "truth_evidence_tombstoned_lineage",
    "truth_evidence_snapshot_truncated",
    "truth_evidence_snapshot_payload",
]
SENTINELS = (
    "AB_EVIDENCE_SUBSTRATE_SENTINEL",
    "AGENT_BRIDGE_EVIDENCE_SUBSTRATE_SENTINEL",
    "PYTHONINSPECT",
)


class Rejected(Exception):
    def __init__(self, code: str, detail: str):
        super().__init__(f"{code}: {detail}")
        self.code = code


def reject(code: str, detail: str) -> None:
    raise Rejected(code, detail)


def strict_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in pairs:
        if key in out:
            reject("duplicate_json_key", key)
        out[key] = value
    return out


def load(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=strict_object)
    except Rejected:
        raise
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        reject("invalid_json", f"{path}: {exc}")
    if not isinstance(value, dict):
        reject("invalid_type", f"{path} root")
    return value


def exact_keys(value: Any, keys: set[str], path: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != keys:
        reject("shape", f"{path} keys")
    return value


def sha(path: Path) -> str:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError as exc:
        reject("source_missing", f"{path}: {exc}")


def source_file(root: Path, relative: str) -> Path:
    if not relative or Path(relative).is_absolute() or ".." in Path(relative).parts:
        reject("source_path", relative)
    candidate = root / relative
    if candidate.is_symlink():
        reject("source_path", f"symlink: {relative}")
    path = candidate.resolve()
    try:
        path.relative_to(root)
    except ValueError:
        reject("source_path", relative)
    if not path.is_file() or path.is_symlink():
        reject("source_missing", relative)
    return path


def validate_contract(contract: dict[str, Any]) -> None:
    exact_keys(
        contract,
        {
            "schema", "baseline_commit", "implementation_status", "schema_contract",
            "snapshot_contract", "implementation_boundary", "source_contract",
            "unchanged_s1_sha256", "unchanged_adapter_guard", "decision",
        },
        "contract",
    )
    if contract["schema"] != CONTRACT_SCHEMA or contract["implementation_status"] != STATUS:
        reject("contract_identity", "schema/status")
    if not re.fullmatch(r"[0-9a-f]{40}", contract["baseline_commit"]):
        reject("contract_identity", "baseline")
    if contract["decision"] != DECISION:
        reject("boundary", "decision")

    schema = exact_keys(
        contract["schema_contract"],
        {
            "from_version", "to_version", "ledger_format_version", "transaction",
            "legacy_backfill", "tables", "explicit_indexes",
            "append_only_update_delete_triggers", "total_triggers", "identity_meta_keys",
            "reserved_identity_meta_namespace", "identity_meta_exact_row_count",
            "reserved_persistent_namespaces", "reserved_temp_namespaces",
            "schema_manifest_includes_all_object_types",
            "schema_manifest_includes_objects_attached_to_truth_tables",
            "temp_guard_includes_objects_attached_to_truth_tables",
            "sqlite_identifier_case_insensitive_guard",
            "runtime_truth_table_queries_main_qualified",
            "schema_digest_recomputed_from_live_manifest",
            "migration_digest_binds_manifest_schema_and_ddl",
        },
        "schema_contract",
    )
    required_schema = {
        "from_version": "42", "to_version": "43", "ledger_format_version": "0",
        "transaction": "immediate", "legacy_backfill": False, "tables": TABLES,
        "explicit_indexes": 6, "append_only_update_delete_triggers": 10,
        "total_triggers": 15,
        "identity_meta_keys": [
            "truth_evidence.schema_sha256", "truth_evidence.migration_sha256",
            "truth_evidence.ledger_format_version",
        ],
        "reserved_identity_meta_namespace": "truth_evidence.*",
        "identity_meta_exact_row_count": 3,
        "reserved_persistent_namespaces": ["truth_*", "idx_truth_*"],
        "reserved_temp_namespaces": ["truth_*", "idx_truth_*"],
        "schema_manifest_includes_all_object_types": True,
        "schema_manifest_includes_objects_attached_to_truth_tables": True,
        "temp_guard_includes_objects_attached_to_truth_tables": True,
        "sqlite_identifier_case_insensitive_guard": True,
        "runtime_truth_table_queries_main_qualified": True,
        "schema_digest_recomputed_from_live_manifest": True,
        "migration_digest_binds_manifest_schema_and_ddl": True,
    }
    if schema != required_schema:
        reject("schema_contract", "v43 identity contract drift")

    snapshot = exact_keys(
        contract["snapshot_contract"],
        {
            "full_ledger_not_cutoff_filtered", "knowledge_cutoff_is_bound_metadata",
            "one_read_transaction", "canonical_order", "canonical_payload_sha256",
            "bounded_streaming_canonical_digest", "cycle_validation_iterative",
            "fetch_plus_one_rejects_count_greater_than_or_equal_to_cap",
            "payload_bytes_greater_than_or_equal_to_cap_rejected", "hard_cap_maxima",
        },
        "snapshot_contract",
    )
    if snapshot["hard_cap_maxima"] != CAPS or snapshot["canonical_order"] != "binary_utf8_v0":
        reject("snapshot_contract", "caps/order")
    if any(snapshot[key] is not True for key in snapshot if key not in {"canonical_order", "hard_cap_maxima"}):
        reject("snapshot_contract", "required true invariant")

    boundary = exact_keys(
        contract["implementation_boundary"],
        {
            "crate_internal_writer", "synthetic_write_token_test_only",
            "crate_internal_snapshot_reader", "state_store_surface", "bridge_surface",
            "mcp_surface", "store_adapter", "producer_profile_changed",
            "legacy_rows_qualified", "real_capture_authorized",
            "biocortex_runtime_influence", "physical_privacy_deletion_resolved",
            "authority_policy_custody_resolved",
        },
        "implementation_boundary",
    )
    true_keys = {"crate_internal_writer", "synthetic_write_token_test_only", "crate_internal_snapshot_reader"}
    for key, value in boundary.items():
        if value is not (key in true_keys):
            reject("boundary", key)

    sources = exact_keys(
        contract["source_contract"],
        {
            "rust_module", "rust_tests", "sqlite_integration", "store_manifest", "lockfile",
            "rust_test_prefix", "minimum_prefixed_tests", "allowed_delta_paths",
        },
        "source_contract",
    )
    if sources["rust_module"] != "crates/store/src/sqlite/temporal_evidence.rs":
        reject("source_contract", "module")
    if sources["rust_test_prefix"] != "truth_evidence_s2_" or sources["minimum_prefixed_tests"] < 6:
        reject("source_contract", "tests")
    if sources["allowed_delta_paths"] != sorted(sources["allowed_delta_paths"]):
        reject("source_contract", "delta paths not canonical")
    if contract["unchanged_s1_sha256"] != S1_SHA256:
        reject("s1_drift", "hash contract")
    adapter = exact_keys(
        contract["unchanged_adapter_guard"],
        {"path", "sha256", "profile", "gap_count", "gaps"},
        "unchanged_adapter_guard",
    )
    if adapter.get("sha256") != ADAPTER_SHA256 or adapter.get("gap_count") != 8:
        reject("adapter_drift", "identity/count")
    if adapter.get("profile") != "MutableSqliteV41" or adapter.get("gaps") != GAPS:
        reject("adapter_drift", "profile/gaps")


def validate_fixture(fixture: dict[str, Any]) -> dict[str, int]:
    exact_keys(
        fixture,
        {
            "schema", "fixture_only", "real_capture_authorized", "legacy_rows_qualified",
            "adapter_allowed", "biocortex_runtime_influence", "migration",
            "authority_policies", "evidence", "tombstones", "snapshot",
            "expected_rejection_codes",
        },
        "fixture",
    )
    if fixture["schema"] != FIXTURE_SCHEMA or fixture["fixture_only"] is not True:
        reject("fixture_identity", "schema/fixture_only")
    for key in ("real_capture_authorized", "legacy_rows_qualified", "adapter_allowed", "biocortex_runtime_influence"):
        if fixture[key] is not False:
            reject("boundary", key)
    migration = fixture["migration"]
    if migration != {
        "from_version": "42", "to_version": "43", "legacy_memory_rows_before": 1,
        "truth_rows_after_migration": 0, "legacy_backfill": False,
    }:
        reject("migration", "not additive/no-backfill synthetic control")

    policies = fixture["authority_policies"]
    evidence = fixture["evidence"]
    tombstones = fixture["tombstones"]
    if not isinstance(policies, list) or not isinstance(evidence, list) or not isinstance(tombstones, list):
        reject("shape", "ledger arrays")
    if any(not row.get("policy_revision_id", "").startswith("synthetic-") for row in policies):
        reject("fixture_identity", "non-synthetic policy")
    if any(not row.get("evidence_id", "").startswith("synthetic-") for row in evidence):
        reject("fixture_identity", "non-synthetic evidence")

    by_lineage: dict[str, list[dict[str, Any]]] = defaultdict(list)
    claims: dict[str, tuple[str, str]] = {}
    evidence_ids: set[str] = set()
    for row in evidence:
        exact_keys(
            row,
            {"evidence_id", "lineage_id", "referent_id", "predicate_id", "revision_seq", "recorded_at", "relationships"},
            "evidence[]",
        )
        if row["evidence_id"] in evidence_ids:
            reject("evidence", "duplicate id")
        evidence_ids.add(row["evidence_id"])
        claim = (row["referent_id"], row["predicate_id"])
        if row["lineage_id"] in claims and claims[row["lineage_id"]] != claim:
            reject("evidence", "claim drift")
        claims[row["lineage_id"]] = claim
        by_lineage[row["lineage_id"]].append(row)
    for lineage, rows in by_lineage.items():
        rows.sort(key=lambda row: row["revision_seq"])
        if [row["revision_seq"] for row in rows] != list(range(1, len(rows) + 1)):
            reject("evidence", f"sequence {lineage}")
        if any(a["recorded_at"] >= b["recorded_at"] for a, b in zip(rows, rows[1:])):
            reject("evidence", f"time {lineage}")
        durable: set[tuple[str, str, int]] = set()
        for row in rows:
            current = {(r["kind"], r["target_lineage_id"], r["effective_from"]) for r in row["relationships"]}
            if not durable.issubset(current):
                reject("relationship_carry_forward", lineage)
            durable = current

    relationship_count = 0
    for row in evidence:
        for relation in row["relationships"]:
            relationship_count += 1
            target = relation["target_lineage_id"]
            if target not in claims or claims[target] != claims[row["lineage_id"]]:
                reject("relationship", target)
            if min(r["recorded_at"] for r in by_lineage[target]) >= row["recorded_at"]:
                reject("relationship", "target not strictly earlier")

    snapshot = fixture["snapshot"]
    counts = {
        "lineages": len(by_lineage), "policy_revisions": len(policies),
        "evidence_revisions": len(evidence), "relationships": relationship_count,
        "tombstones": len(tombstones),
    }
    if snapshot.get("expected_counts") != counts:
        reject("snapshot_counts", str(counts))
    cutoff = snapshot.get("knowledge_cutoff")
    later = sorted(row["evidence_id"] for row in evidence if row["recorded_at"] > cutoff)
    if snapshot.get("post_cutoff_evidence_ids_retained") != later:
        reject("full_ledger", "cutoff filtered or declaration drift")
    if snapshot.get("full_ledger_not_cutoff_filtered") is not True:
        reject("full_ledger", "required")
    cap_names = {
        "lineages": "max_lineages", "policy_revisions": "max_policy_revisions",
        "evidence_revisions": "max_evidence_revisions", "relationships": "max_relationships",
        "tombstones": "max_tombstones",
    }
    limits = snapshot.get("limits", {})
    if any(counts[name] >= limits.get(cap, 0) for name, cap in cap_names.items()):
        reject("snapshot_capacity", "count must be strictly below cap")
    if not 0 < limits.get("max_payload_bytes", 0) <= CAPS["max_payload_bytes"]:
        reject("snapshot_capacity", "payload")
    tombstoned = {row["lineage_id"] for row in tombstones}
    inbound = any(
        relation["target_lineage_id"] in tombstoned
        for row in evidence for relation in row["relationships"]
    )
    if not inbound or snapshot.get("inbound_relationship_to_tombstoned_target_retained") is not True:
        reject("tombstone", "inbound relationship must remain in substrate")
    if snapshot.get("canonical_order") != "binary_utf8_v0":
        reject("snapshot_order", "canonical order")
    if fixture["expected_rejection_codes"] != REJECTION_CODES:
        reject("negative_contract", "stable codes")
    return counts


def validate_sources(contract: dict[str, Any], root: Path) -> tuple[str, str, int]:
    root = root.resolve()
    for relative, expected in S1_SHA256.items():
        if sha(source_file(root, relative)) != expected:
            reject("s1_drift", relative)
    adapter_path = source_file(root, contract["unchanged_adapter_guard"]["path"])
    if sha(adapter_path) != ADAPTER_SHA256:
        reject("adapter_drift", str(adapter_path))
    adapter = adapter_path.read_text(encoding="utf-8")
    if "MemoryEvidenceProfile::MutableSqliteV41" not in adapter or "assert_eq!(report.gaps.len(), 8)" not in adapter:
        reject("adapter_drift", "profile/eight-gap assertion")
    if any(gap not in adapter for gap in GAPS):
        reject("adapter_drift", "gap names")

    sources = contract["source_contract"]
    module = source_file(root, sources["rust_module"]).read_text(encoding="utf-8")
    tests_source = source_file(root, sources["rust_tests"]).read_text(encoding="utf-8")
    sqlite = source_file(root, sources["sqlite_integration"]).read_text(encoding="utf-8")
    manifest = source_file(root, sources["store_manifest"]).read_text(encoding="utf-8")
    lockfile = source_file(root, sources["lockfile"]).read_text(encoding="utf-8")
    digest_match = re.search(r'EXPECTED_SCHEMA_SHA256:\s*&str\s*=\s*\n?\s*"([0-9a-f]{64})"', module)
    if not digest_match:
        reject("schema_identity", "reviewed schema digest constant")
    manifest_match = re.search(
        r"const MIGRATION_MANIFEST: &str = concat!\((.*?)\n\);", module, re.S
    )
    ddl_match = re.search(
        r'(?:pub\(super\) )?const SCHEMA_V43_TEMPORAL_EVIDENCE: &str = r#"(.*?)"#;',
        module,
        re.S,
    )
    if not manifest_match or not ddl_match:
        reject("migration_identity", "manifest/DDL source")
    try:
        manifest_bytes = "".join(
            json.loads(part)
            for part in re.findall(r'"(?:[^"\\]|\\.)*"', manifest_match.group(1))
        ).encode("utf-8")
    except json.JSONDecodeError as exc:
        reject("migration_identity", str(exc))
    migration_hasher = hashlib.sha256()
    migration_hasher.update(manifest_bytes)
    migration_hasher.update(
        f"schema_sha256={digest_match.group(1)}\n".encode("utf-8")
    )
    migration_hasher.update(b"ddl_utf8_v0\n")
    migration_hasher.update(ddl_match.group(1).encode("utf-8"))
    migration_digest = migration_hasher.hexdigest()
    created_tables = re.findall(r"^CREATE TABLE IF NOT EXISTS ([a-z0-9_]+) \(", module, re.M)
    if created_tables != TABLES:
        reject("schema_identity", f"tables {created_tables}")
    if len(re.findall(r"^CREATE INDEX IF NOT EXISTS idx_truth_", module, re.M)) != 6:
        reject("schema_identity", "index count")
    triggers = re.findall(r"^CREATE TRIGGER IF NOT EXISTS ([a-z0-9_]+)", module, re.M)
    append_only = [name for name in triggers if name.endswith("_append_only_update") or name.endswith("_append_only_delete")]
    if len(triggers) != 15 or len(append_only) != 10:
        reject("schema_identity", "trigger count")
    markers = [
        'TEMPORAL_EVIDENCE_SCHEMA_VERSION: &str = "43"',
        'TEMPORAL_EVIDENCE_LEDGER_FORMAT_VERSION: &str = "0"',
        "sqlite_temp_master", "live_schema_manifest", "migration_sha256()",
        "sqlite_master_truth_scope_normalized_v1", "lower(name) GLOB 'truth_*'",
        "lower(tbl_name) IN (", "reserved_temp_object_count",
        '"runtime_table_namespace=main\\n"', "validate_acyclic_adjacency",
        "BoundedCanonicalDigestWriter", "serde_json::to_writer(&mut writer, value)",
        "key GLOB 'truth_evidence.*'", "identity_row_count != 3",
        "SCHEMA_V43_TEMPORAL_EVIDENCE.as_bytes()", "TransactionBehavior::Immediate",
        "SyntheticTemporalEvidenceWriteToken", "#[cfg(test)]\nfn synthetic_write_token()",
        "truth_evidence_append_policy_synthetic", "truth_evidence_append_revision_synthetic",
        "truth_evidence_tombstone_lineage_synthetic", "truth_evidence_snapshot_internal",
    ]
    if any(marker not in module for marker in markers):
        reject("implementation_marker", "missing v43 writer/snapshot/identity marker")
    if "type IN ('table','index','trigger')" in module or "impl StateStore" in module:
        reject("implementation_boundary", "narrow schema manifest or StateStore exposure")
    runtime_module = module[ddl_match.end():]
    if re.search(r"\b(?:FROM|JOIN|INTO|UPDATE|DELETE FROM)\s+truth_", runtime_module):
        reject("implementation_boundary", "unqualified runtime truth table access")
    if "fn visit_cycle(" in module:
        reject("implementation_boundary", "recursive cycle validation")
    if "mod temporal_evidence;" not in sqlite or "pub mod temporal_evidence" in sqlite:
        reject("implementation_boundary", "module privacy")
    if "#[cfg(test)]\nmod tests;" not in module:
        reject("test_contract", "private test module")
    if "temporal_evidence::migrate_or_verify_v43(c)?;" not in sqlite:
        reject("implementation_marker", "migration integration")
    if re.search(r"^pub\s+(?:async\s+)?fn\s+truth_evidence_", module, re.M):
        reject("implementation_boundary", "public writer/reader")
    if not re.search(r'^sha2\s*=\s*"0\.10"$', manifest, re.M) or '"sha2"' not in lockfile:
        reject("source_contract", "sha2 lock binding")
    test_count = len(re.findall(r"(?:async\s+)?fn\s+truth_evidence_s2_[a-z0-9_]+", tests_source))
    if test_count < sources["minimum_prefixed_tests"]:
        reject("test_contract", f"only {test_count} prefixed tests")
    test_markers = [
        "CREATE TEMP VIEW TRUTH_LINEAGES",
        "MAX_LINEAGES - 1",
        "truth_evidence_s2_snapshot_streaming_cap_rejects_control_character_expansion",
    ]
    if any(marker not in tests_source for marker in test_markers):
        reject("test_contract", "identity, depth, or bounded-streaming regression missing")
    return digest_match.group(1), migration_digest, test_count


def run_negative_cases(fixture: dict[str, Any]) -> int:
    cases: list[tuple[str, Any]] = []
    for key in ("real_capture_authorized", "legacy_rows_qualified", "adapter_allowed", "biocortex_runtime_influence"):
        candidate = copy.deepcopy(fixture)
        candidate[key] = True
        cases.append(("boundary", candidate))
    candidate = copy.deepcopy(fixture)
    candidate["migration"]["truth_rows_after_migration"] = 1
    cases.append(("migration", candidate))
    candidate = copy.deepcopy(fixture)
    candidate["snapshot"]["post_cutoff_evidence_ids_retained"].pop()
    cases.append(("full_ledger", candidate))
    candidate = copy.deepcopy(fixture)
    candidate["snapshot"]["limits"]["max_lineages"] = 3
    cases.append(("snapshot_capacity", candidate))
    candidate = copy.deepcopy(fixture)
    candidate["evidence"][2]["relationships"] = []
    cases.append(("relationship_carry_forward", candidate))
    candidate = copy.deepcopy(fixture)
    candidate["runtime_enable"] = True
    cases.append(("shape", candidate))
    for expected, candidate in cases:
        try:
            validate_fixture(candidate)
        except Rejected as exc:
            if exc.code != expected:
                reject("negative_case", f"wanted {expected}, got {exc.code}")
        else:
            reject("negative_case", f"accepted {expected}")
    try:
        json.loads('{"schema":"a","schema":"b"}', object_pairs_hook=strict_object)
    except Rejected as exc:
        if exc.code != "duplicate_json_key":
            reject("negative_case", "duplicate key code")
    else:
        reject("negative_case", "duplicate key accepted")
    return len(cases) + 1


def emit(
    counts: dict[str, int],
    schema_digest: str,
    migration_digest: str,
    tests: int,
    negatives: int,
) -> None:
    if any(name in os.environ for name in SENTINELS):
        reject("environment", "hostile sentinel reached checker")
    rows = [
        ("schema", RECEIPT_SCHEMA), ("implementation_status", STATUS),
        ("fixture_only", "true"), ("schema_version", "43"),
        ("ledger_format_version", "0"), ("tables", "5"),
        ("append_only_update_delete_triggers", "10"),
        ("schema_sha256", schema_digest), ("migration_sha256", migration_digest),
        ("schema_migration_present", "true"),
        ("schema_and_migration_identity_verified", "true"),
        ("crate_internal_synthetic_writer_present", "true"),
        ("crate_internal_full_ledger_snapshot_present", "true"),
        ("prefixed_rust_tests_at_least_6", str(tests >= 6).lower()),
        ("synthetic_negative_cases_rejected", str(negatives)),
        ("fixture_lineages", str(counts["lineages"])),
        ("fixture_evidence_revisions", str(counts["evidence_revisions"])),
        ("s1_packet_unchanged", "true"), ("mutable_profile", "MutableSqliteV41"),
        ("mutable_profile_gap_count", "8"), ("state_store_surface_present", "false"),
        ("bridge_surface_present", "false"), ("mcp_surface_present", "false"),
        ("store_adapter_present", "false"), ("producer_profile_changed", "false"),
        ("legacy_backfill", "false"), ("legacy_rows_qualified", "false"),
        ("real_capture_authorized", "false"), ("biocortex_runtime_influence", "false"),
        ("physical_privacy_deletion_resolved", "false"),
        ("authority_policy_custody_resolved", "false"),
        ("sentinels_cleared", "true"), ("decision", DECISION),
    ]
    for key, value in rows:
        print(f"{key}\t{value}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--contract", type=Path, required=True)
    parser.add_argument("--fixture", type=Path, required=True)
    parser.add_argument("--source-root", type=Path, required=True)
    args = parser.parse_args()
    try:
        contract = load(args.contract)
        fixture = load(args.fixture)
        validate_contract(contract)
        counts = validate_fixture(fixture)
        schema_digest, migration_digest, tests = validate_sources(contract, args.source_root)
        negatives = run_negative_cases(fixture)
        emit(counts, schema_digest, migration_digest, tests, negatives)
    except (Rejected, AssertionError) as exc:
        print(f"S2 evidence-substrate check failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
