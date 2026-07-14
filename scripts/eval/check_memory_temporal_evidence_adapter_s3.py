#!/usr/bin/env python3
"""Source-bound checker for the fail-closed temporal-evidence adapter S3 preregistration."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import sys
from pathlib import Path
from typing import Any, Callable


CONTRACT_SCHEMA = "agent_bridge.memory_temporal_evidence_adapter_preregistration.v0"
FIXTURE_SCHEMA = "agent_bridge.memory_temporal_evidence_adapter_s3_synthetic.v0"
RECEIPT_SCHEMA = "agent_bridge.memory_temporal_evidence_adapter_s3_receipt.v0"
BASELINE = "a989cf6e09d60cb4d3d9b6d5f6a60e55ecd65259"
STATUS = "PREREGISTERED_BLOCKED_PENDING_S4_INTERFACE"
DECISION = "BLOCKED_FAIL_CLOSED"
CONTRACT_SHA256 = "0efefdc38111bac5f344335be425dc6cf931fa509284833b959e326f7d2e8c2a"
FIXTURE_SHA256 = "ce2facc5989883eafb95b7e184868792dfdf511a6bc06c739d01f3556178afea"

GAPS = [
    "AUTHORITY_POLICY_CUSTODY_UNRESOLVED",
    "CANDIDATE_EVIDENCE_INTERFACE_UNIMPLEMENTED",
    "CAPTURE_PROVENANCE_UNATTESTED",
    "CONTENT_FREE_TOMBSTONE_CHANNEL_UNREPRESENTED",
    "PHYSICAL_PRIVACY_DELETION_UNRESOLVED",
    "PRODUCTION_PRODUCER_PROFILE_UNADMITTED",
    "PROVENANCE_DIGEST_CHANNEL_UNREPRESENTED",
    "READ_ONLY_OPEN_IDENTITY_UNBOUND",
    "RELATIONSHIP_SOURCE_TIME_AUTHORITY_BASIS_UNREPRESENTED",
    "SEALED_SNAPSHOT_PROJECTION_BINDING_UNREPRESENTED",
]

TOP_CONTRACT_KEYS = [
    "schema",
    "baseline_commit",
    "design_status",
    "decision",
    "upstream_bindings",
    "gap_contract",
    "s4_interface_contract",
    "governance_boundary",
    "track_b_boundary",
    "source_contract",
]
TOP_FIXTURE_KEYS = [
    "schema",
    "fixture_only",
    "producer_identity",
    "read_only_attestation",
    "governance_receipts",
    "cases",
    "expected_gap_codes",
    "boundary",
]
CASE_IDS = [
    "synthetic_exact_schema_identity_is_not_capture_authority",
    "synthetic_content_free_tombstoned_inbound_target",
    "synthetic_content_free_tombstoned_governance_source",
    "synthetic_source_time_authority_survives_later_target_upgrade",
    "synthetic_full_ledger_retains_post_cutoff_revision",
    "synthetic_projection_snapshot_mix_and_match",
]
TIER_RANK = {
    "inferred": 0,
    "observed": 1,
    "verified": 2,
    "authoritative": 3,
}


class ContractError(RuntimeError):
    pass


def reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ContractError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def load_json(path: Path) -> dict[str, Any]:
    if not path.is_file() or path.is_symlink():
        raise ContractError(f"JSON input is missing, non-regular, or symlinked: {path}")
    try:
        value = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=reject_duplicate_keys)
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ContractError(f"cannot read strict JSON {path}: {error}") from error
    if not isinstance(value, dict):
        raise ContractError(f"JSON root must be an object: {path}")
    return value


def load_json_text(text: str) -> dict[str, Any]:
    value = json.loads(text, object_pairs_hook=reject_duplicate_keys)
    if not isinstance(value, dict):
        raise ContractError("JSON root must be an object")
    return value


def canonical_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def digest_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def digest_file(path: Path) -> str:
    if not path.is_file() or path.is_symlink():
        raise ContractError(f"bound source is missing, non-regular, or symlinked: {path}")
    return digest_bytes(path.read_bytes())


def tombstone_attestation_digest(tombstone: dict[str, Any]) -> str:
    payload = {
        "attestation_version": tombstone["attestation_version"],
        "had_outgoing_governance": tombstone["had_outgoing_governance"],
        "lineage_id": tombstone["lineage_id"],
        "tombstone_id": tombstone["tombstone_id"],
        "tombstoned_at": tombstone["tombstoned_at"],
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return digest_bytes(encoded)


def exact_keys(value: dict[str, Any], expected: list[str], label: str) -> None:
    if list(value) != expected:
        raise ContractError(f"{label} keys/order drifted: {list(value)!r}")


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ContractError(message)


def read_source(root: Path, relative: str, expected_sha256: str) -> str:
    path = root / relative
    actual = digest_file(path)
    require(actual == expected_sha256, f"source hash drifted for {relative}: {actual}")
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as error:
        raise ContractError(f"cannot read source {relative}: {error}") from error


def struct_block(source: str, declaration: str) -> str:
    start = source.find(declaration)
    require(start >= 0, f"missing source declaration: {declaration}")
    end = source.find("\n}", start)
    require(end >= 0, f"unterminated source declaration: {declaration}")
    return source[start : end + 2]


def validate_contract(contract: dict[str, Any], *, check_digest: bool = True) -> None:
    exact_keys(contract, TOP_CONTRACT_KEYS, "contract")
    if check_digest:
        require(digest_bytes(canonical_bytes(contract)) == CONTRACT_SHA256, "contract canonical digest drifted")
    require(contract["schema"] == CONTRACT_SCHEMA, "contract schema drifted")
    require(contract["baseline_commit"] == BASELINE, "contract baseline drifted")
    require(contract["design_status"] == STATUS, "contract status drifted")
    require(contract["decision"] == DECISION, "contract decision drifted")

    upstream = contract["upstream_bindings"]
    exact_keys(upstream, ["s2", "projector_v0", "legacy_preflight", "track_b"], "upstream_bindings")
    s2 = upstream["s2"]
    require(s2["commit"] == BASELINE, "S2 commit drifted")
    require(s2["schema_version"] == 43 and s2["ledger_format_version"] == 0, "S2 identity drifted")
    require(s2["schema_sha256"] == "6d321d45aafe65ef06efb49c46ccf9f1931624aada9e8873d7e29765826e3aa0", "S2 schema digest drifted")
    require(s2["migration_sha256"] == "f0d9a3a2505d301a266bb41c09ce2fbaebd8572aa9340affd7e62b6d29faa8bb", "S2 migration digest drifted")
    require(len(s2["files"]) == 12, "S2 source binding must contain twelve files")

    projector = upstream["projector_v0"]
    require(projector["schema"] == "agent_bridge.truth_projection.v0", "projector schema drifted")
    require(projector["request_type"] == "TruthProjectionRequest", "projector request type drifted")
    for field in [
        "independent_tombstone_channel",
        "provenance_digest_channel",
        "source_time_authority_basis",
        "sealed_snapshot_projection_binding",
    ]:
        require(projector[field] is False, f"projector v0 capability was invented: {field}")

    legacy = upstream["legacy_preflight"]
    require(legacy["profile"] == "MutableSqliteV41", "legacy profile drifted")
    require(legacy["gap_count"] == 8, "legacy gap count drifted")
    require(legacy["mapping_present"] is False and legacy["projector_invoked"] is False, "legacy adapter capability was invented")
    require(upstream["track_b"]["unrepresented_marker"] == "CANDIDATE_EVIDENCE_SUBSTRATE_INTERFACE_UNREPRESENTED", "Track B marker drifted")
    require(len(upstream["track_b"]["files"]) == 5, "Track B source binding must contain five files")

    gap_contract = contract["gap_contract"]
    exact_keys(gap_contract, ["count", "codes"], "gap_contract")
    require(gap_contract["count"] == 10 and gap_contract["codes"] == GAPS, "S3 gap contract drifted")

    s4 = contract["s4_interface_contract"]
    exact_keys(
        s4,
        [
            "prepared_type",
            "read_only_snapshot",
            "content_free_tombstone_channel",
            "relationship_authority_basis",
            "provenance_channel",
            "sealed_projection_envelope",
            "cross_biocortex_boundary",
        ],
        "s4_interface_contract",
    )
    require(s4["prepared_type"] == {
        "name": "PreparedTemporalEvidenceV1",
        "crate_internal": True,
        "serde_serializable": False,
        "opaque_to_callers": True,
        "mapping_version_required": True,
    }, "prepared type contract drifted")
    tombstone = s4["content_free_tombstone_channel"]
    require(tombstone["independent_from_evidence"] is True, "tombstone channel must be independent")
    require(tombstone["placeholder_evidence_allowed"] is False, "placeholder tombstone evidence must be forbidden")
    require(tombstone["governed_source_terminal"] is True, "governed tombstone source must terminate")
    require(tombstone["inbound_target_prunable"] is True, "inbound tombstoned target rule drifted")
    relationship = s4["relationship_authority_basis"]
    require(relationship["basis"] == "complete_snapshot_latest_target_strictly_before_source_recorded_at", "relationship authority basis drifted")
    require(relationship["origin"] == "derived_from_complete_validated_snapshot", "relationship basis origin drifted")
    require(relationship["persisted_at_original_admission"] is False, "an unavailable original admission witness was claimed")
    require(relationship["same_second_target_allowed"] is False, "same-second target must remain ambiguous")
    require(relationship["cutoff_latest_tier_recheck_allowed"] is False, "cutoff-latest authority laundering was enabled")
    require(relationship["bound_by_snapshot_digest"] is True, "relationship witness must be snapshot-bound")
    require(relationship["original_physical_admission_witness_claimed"] is False, "physical admission witness was invented")
    require(s4["provenance_channel"]["fields"] == ["source_key", "provenance_sha256"], "provenance channel drifted")
    require(s4["sealed_projection_envelope"]["fields"] == [
        "producer_identity",
        "snapshot_payload_sha256",
        "snapshot_payload_bytes",
        "snapshot_counts",
        "snapshot_limits",
        "knowledge_cutoff",
        "as_of",
        "mapping_version",
        "prepared_input_sha256",
        "projection_sha256",
    ], "sealed projection fields drifted")
    require(s4["sealed_projection_envelope"]["atomic_map_and_project"] is True, "map+project must be atomic")
    require(s4["sealed_projection_envelope"]["mix_and_match_rejected"] is True, "snapshot/result substitution must reject")
    require(s4["cross_biocortex_boundary"]["raw_identifiers_values_and_sources_serializable"] is False, "raw truth material cannot cross BioCortex boundary")

    governance = contract["governance_boundary"]
    for field in [
        "real_capture_authorized",
        "private_material_allowed",
        "production_profile_active",
        "physical_privacy_deletion_resolved",
        "authority_policy_custody_resolved",
        "caller_profile_allowed",
        "caller_tier_allowed",
        "raw_values_serializable",
        "legacy_rows_qualified",
    ]:
        require(governance[field] is False, f"governance sentinel must remain false: {field}")
    for field in [
        "capture_authorization_receipt_sha256",
        "capture_provenance_receipt_sha256",
        "deletion_mechanism_receipt_sha256",
        "authority_custody_receipt_sha256",
    ]:
        require(governance[field] is None, f"governance receipt must remain null: {field}")
    require(governance["fixture_only"] is True, "S3 is fixture-only")

    track_b = contract["track_b_boundary"]
    require(track_b["candidate_interface_status"] == "PREREGISTERED_NOT_IMPLEMENTED_OR_BOUND", "Track B interface status drifted")
    for field in [
        "artifact_binding_satisfied",
        "dependency_graph_rewritten",
        "live_binding_ledger_rewritten",
        "real_run_admission_rewritten",
    ]:
        require(track_b[field] is False, f"Track B sentinel must remain false: {field}")
    require(track_b["side_effects_unlocked"] == "NONE", "Track B side effect was unlocked")

    source_contract = contract["source_contract"]
    for field in [
        "rust_delta_allowed",
        "producer_profile_reserved",
        "s3_adapter_present",
        "projector_invoked",
        "state_store_surface_present",
        "bridge_runtime_surface_present",
        "mcp_surface_present",
        "biocortex_runtime_influence",
    ]:
        require(source_contract[field] is False, f"source sentinel must remain false: {field}")


def validate_fixture(fixture: dict[str, Any], *, check_digest: bool = True) -> None:
    exact_keys(fixture, TOP_FIXTURE_KEYS, "fixture")
    if check_digest:
        require(digest_bytes(canonical_bytes(fixture)) == FIXTURE_SHA256, "fixture canonical digest drifted")
    require(fixture["schema"] == FIXTURE_SCHEMA and fixture["fixture_only"] is True, "fixture identity drifted")
    producer = fixture["producer_identity"]
    require(producer["schema_meta_version"] == "43", "fixture schema version drifted")
    require(producer["ledger_format_version"] == "0", "fixture ledger format drifted")
    require(producer["synthetic_identity_only"] is True, "fixture producer identity was promoted")
    read_only = fixture["read_only_attestation"]
    for field in ["actual_read_only_open_bound", "query_only_verified", "snapshot_counts_bound", "snapshot_limits_bound"]:
        require(read_only[field] is False, f"fixture read-only attestation was invented: {field}")
    require(read_only["prepared_input_sha256"] is None and read_only["projection_sha256"] is None, "fixture projection binding was invented")
    require(all(value is None for value in fixture["governance_receipts"].values()), "fixture governance receipt was invented")
    cases = fixture["cases"]
    require(isinstance(cases, list) and [case.get("case_id") for case in cases] == CASE_IDS, "synthetic cases drifted")
    require(cases[0]["schema_identity_verified"] is True and cases[0]["capture_authorized"] is False, "schema/capture separation drifted")
    require(cases[0]["expected_action"] == "BLOCK_BEFORE_PROFILE_ADMISSION", "schema identity case action drifted")
    target_tombstone = cases[1]["tombstone"]
    require(target_tombstone["content_fields_present"] is False, "content-free target tombstone drifted")
    require(target_tombstone["attestation_version"] == "content_free_governance_v0", "target tombstone attestation version drifted")
    require(target_tombstone["attestation_sha256"] == tombstone_attestation_digest(target_tombstone), "target tombstone attestation digest drifted")
    require(cases[1]["historical_inbound_relationship_retained"] is True, "inbound relationship evidence was erased")
    require(cases[1]["retained_revision_must_be_recarried_by_v0"] is True, "v0 retained-revision boundary drifted")
    require(cases[1]["expected_s4_action"] == "PRUNE_TARGET_WITHOUT_SYNTHESIZING_EVIDENCE", "target tombstone action drifted")
    source_tombstone = cases[2]["tombstone"]
    require(source_tombstone["had_outgoing_governance"] is True, "governed tombstone sentinel drifted")
    require(source_tombstone["attestation_version"] == "content_free_governance_v0", "source tombstone attestation version drifted")
    require(source_tombstone["attestation_sha256"] == tombstone_attestation_digest(source_tombstone), "source tombstone attestation digest drifted")
    require(cases[2]["expected_s4_action"] == "TERMINAL_REJECT_BEFORE_MAPPING", "governed tombstone must terminate")
    authority = cases[3]
    require(authority["source"]["recorded_at"] == 100, "relationship source time drifted")
    require([revision["recorded_at"] for revision in authority["target_revisions"]] == [90, 200], "relationship target times drifted")
    require(authority["source_time_target_evidence_id"] == "synthetic-target-v1", "source-time target basis drifted")
    require(authority["projector_v0_cutoff_latest_target_evidence_id"] == "synthetic-target-v2", "cutoff-latest counterexample drifted")
    source = authority["source"]
    strict_before = [revision for revision in authority["target_revisions"] if revision["recorded_at"] < source["recorded_at"]]
    cutoff_visible = [revision for revision in authority["target_revisions"] if revision["recorded_at"] <= authority["knowledge_cutoff"]]
    require(strict_before and cutoff_visible, "relationship counterexample lacks a visible target")
    source_time_target = max(strict_before, key=lambda revision: revision["revision_seq"])
    cutoff_target = max(cutoff_visible, key=lambda revision: revision["revision_seq"])
    admitted_by_s2 = TIER_RANK[source["truth_tier"]] >= TIER_RANK[source_time_target["truth_tier"]]
    rejected_by_v0 = TIER_RANK[source["truth_tier"]] < TIER_RANK[cutoff_target["truth_tier"]]
    require(source_time_target["evidence_id"] == authority["source_time_target_evidence_id"], "derived source-time basis drifted")
    require(cutoff_target["evidence_id"] == authority["projector_v0_cutoff_latest_target_evidence_id"], "derived cutoff target drifted")
    require(authority["relationship_admitted_by_s2"] is admitted_by_s2, "S2 relationship result was not derived")
    require(authority["projector_v0_would_reject"] is rejected_by_v0, "projector v0 result was not derived")
    require(admitted_by_s2 and rejected_by_v0, "relationship incompatibility disappeared")
    require(authority["expected_s4_action"] == "DERIVE_AND_BIND_SOURCE_TIME_BASIS_WITHOUT_CUTOFF_RECHECK", "source-time authority action drifted")
    require(cases[4]["present_in_snapshot"] is True and cases[4]["adapter_prefilter_allowed"] is False, "full-ledger rule drifted")
    mix = cases[5]
    require(mix["snapshot_a_sha256"] != mix["snapshot_b_sha256"], "mix-and-match snapshots must differ")
    require(mix["per_evidence_provenance_digest_present"] is True, "mix-and-match control must retain provenance")
    require(mix["expected_s4_action"] == "REJECT_SEALED_BINDING_MISMATCH", "mix-and-match must reject")
    require(fixture["expected_gap_codes"] == GAPS, "fixture gaps drifted")
    boundary = fixture["boundary"]
    false_fields = [key for key in boundary if key not in ["side_effects_unlocked", "decision"]]
    require(all(boundary[field] is False for field in false_fields), "fixture boundary was unlocked")
    require(boundary["side_effects_unlocked"] == "NONE" and boundary["decision"] == DECISION, "fixture boundary decision drifted")


def validate_sources(contract: dict[str, Any], source_root: Path) -> None:
    upstream = contract["upstream_bindings"]
    for relative, expected in upstream["s2"]["files"].items():
        read_source(source_root, relative, expected)
    for relative, expected in upstream["track_b"]["files"].items():
        read_source(source_root, relative, expected)

    projector_binding = upstream["projector_v0"]
    projector = read_source(source_root, projector_binding["path"], projector_binding["sha256"])
    request = struct_block(projector, "pub struct TruthProjectionRequest {")
    evidence = struct_block(projector, "pub struct TruthEvidence {")
    relationship = struct_block(projector, "pub struct TruthRelationship {")
    projection = struct_block(projector, "pub struct TruthProjection {")
    lifecycle = projector[projector.find("pub enum LifecycleState {") : projector.find("\n}", projector.find("pub enum LifecycleState {")) + 2]
    require("pub evidence: Vec<TruthEvidence>" in request, "projector request lost evidence channel")
    require("tombstone" not in request.lower(), "projector v0 unexpectedly gained an independent tombstone channel")
    require("Tombstoned" in lifecycle, "projector v0 tombstone evidence marker drifted")
    require("pub source_keys: Vec<String>" in evidence and "provenance_sha256" not in evidence, "projector provenance boundary drifted")
    require("target_evidence_id" not in relationship and "target_truth_tier" not in relationship, "projector relationship witness boundary drifted")
    require("snapshot_payload_sha256" not in projection and "projection_sha256" not in projection, "projector sealed binding boundary drifted")
    require("if source.truth_tier < target.truth_tier" in projector, "projector cutoff-latest tier comparison drifted")
    require("A later cross-repository\n//! transport must replace them with request-scoped opaque handles and bind the\n//! projection to a sealed snapshot." in projector, "projector sealed-snapshot warning drifted")

    legacy_binding = upstream["legacy_preflight"]
    legacy = read_source(source_root, legacy_binding["path"], legacy_binding["sha256"])
    require("MemoryEvidenceProfile::MutableSqliteV41" in legacy, "legacy adapter profile drifted")
    require("assert_eq!(report.gaps.len(), 8);" in legacy, "legacy adapter eight-gap assertion drifted")
    require("project(" not in legacy, "legacy adapter unexpectedly invokes projector")

    temporal_path = "crates/store/src/sqlite/temporal_evidence.rs"
    temporal = read_source(source_root, temporal_path, upstream["s2"]["files"][temporal_path])
    require("struct TemporalEvidenceSnapshot {" in temporal and "pub struct TemporalEvidenceSnapshot {" not in temporal, "S2 snapshot visibility drifted")
    require("async fn truth_evidence_snapshot_internal(" in temporal and "pub async fn truth_evidence_snapshot_internal(" not in temporal, "S2 reader visibility drifted")
    require("struct EvidenceSourceBinding {\n    provenance_sha256: String,\n    source_key: String," in temporal, "S2 provenance digest channel drifted")
    require("struct LineageTombstoneRow {" in temporal, "S2 tombstone row disappeared")
    for marker in ["had_outgoing_governance: bool", "attestation_sha256: String", "attestation_version: String"]:
        require(marker in temporal, f"S2 tombstone marker drifted: {marker}")
    require('const ATTESTATION_VERSION: &str = "content_free_governance_v0";' in temporal, "S2 tombstone attestation version drifted")
    require("CHECK (attestation_version = 'content_free_governance_v0')" in temporal, "S2 tombstone SQL attestation guard drifted")
    require("WHERE lineage_id=?1 AND recorded_at<?2" in temporal, "S2 strict-before relationship authority drifted")
    require(
        ".rev()\n            .find(|target| target.recorded_at < source.recorded_at)" in temporal,
        "S2 full-ledger strict-before authority derivation drifted",
    )
    require("truth_evidence_same_second_target_ambiguity" in temporal, "S2 same-second guard drifted")

    graph_path = "scripts/eval/fixtures/biocortex_ab_track_b_artifact_dependency_graph_v0.json"
    graph = read_source(source_root, graph_path, upstream["track_b"]["files"][graph_path])
    require("CANDIDATE_EVIDENCE_SUBSTRATE_INTERFACE_UNREPRESENTED" in graph, "Track B interface gap was rewritten")


def negative_controls(contract: dict[str, Any], fixture: dict[str, Any]) -> int:
    controls: list[tuple[str, str, Callable[[dict[str, Any]], None]]] = []

    def contract_control(name: str, mutate: Callable[[dict[str, Any]], None]) -> None:
        controls.append((name, "contract", mutate))

    def fixture_control(name: str, mutate: Callable[[dict[str, Any]], None]) -> None:
        controls.append((name, "fixture", mutate))

    contract_control("baseline", lambda value: value.__setitem__("baseline_commit", "0" * 40))
    contract_control("status", lambda value: value.__setitem__("design_status", "READY"))
    contract_control("decision", lambda value: value.__setitem__("decision", "ALLOW"))
    contract_control("gap_removed", lambda value: value["gap_contract"]["codes"].pop())
    contract_control("gap_order", lambda value: value["gap_contract"]["codes"].reverse())
    contract_control("s2_hash", lambda value: value["upstream_bindings"]["s2"].__setitem__("schema_sha256", "0" * 64))
    contract_control("invent_tombstone_channel", lambda value: value["upstream_bindings"]["projector_v0"].__setitem__("independent_tombstone_channel", True))
    contract_control("invent_legacy_mapping", lambda value: value["upstream_bindings"]["legacy_preflight"].__setitem__("mapping_present", True))
    contract_control("legacy_gap_count", lambda value: value["upstream_bindings"]["legacy_preflight"].__setitem__("gap_count", 7))
    contract_control("placeholder_tombstone", lambda value: value["s4_interface_contract"]["content_free_tombstone_channel"].__setitem__("placeholder_evidence_allowed", True))
    contract_control("cutoff_latest_recheck", lambda value: value["s4_interface_contract"]["relationship_authority_basis"].__setitem__("cutoff_latest_tier_recheck_allowed", True))
    contract_control("capture_authorized", lambda value: value["governance_boundary"].__setitem__("real_capture_authorized", True))
    contract_control("profile_reserved", lambda value: value["source_contract"].__setitem__("producer_profile_reserved", True))
    contract_control("projector_invoked", lambda value: value["source_contract"].__setitem__("projector_invoked", True))
    contract_control("track_b_bound", lambda value: value["track_b_boundary"].__setitem__("artifact_binding_satisfied", True))
    contract_control("state_store_surface", lambda value: value["source_contract"].__setitem__("state_store_surface_present", True))
    contract_control("biocortex_influence", lambda value: value["source_contract"].__setitem__("biocortex_runtime_influence", True))
    contract_control("raw_serializable", lambda value: value["governance_boundary"].__setitem__("raw_values_serializable", True))
    fixture_control("not_fixture", lambda value: value.__setitem__("fixture_only", False))
    fixture_control("schema_version", lambda value: value["producer_identity"].__setitem__("schema_meta_version", "42"))
    fixture_control("invent_read_only", lambda value: value["read_only_attestation"].__setitem__("actual_read_only_open_bound", True))
    fixture_control("invent_receipt", lambda value: value["governance_receipts"].__setitem__("capture_authorization_receipt_sha256", "0" * 64))
    fixture_control("schema_means_capture", lambda value: value["cases"][0].__setitem__("capture_authorized", True))
    fixture_control("contentful_tombstone", lambda value: value["cases"][1]["tombstone"].__setitem__("content_fields_present", True))
    fixture_control("governed_source_allowed", lambda value: value["cases"][2].__setitem__("expected_s4_action", "ALLOW"))
    fixture_control("adapter_prefilter", lambda value: value["cases"][4].__setitem__("adapter_prefilter_allowed", True))

    rejected = 0
    for name, kind, mutate in controls:
        candidate = copy.deepcopy(contract if kind == "contract" else fixture)
        mutate(candidate)
        try:
            (validate_contract if kind == "contract" else validate_fixture)(candidate, check_digest=False)
        except ContractError:
            rejected += 1
        else:
            raise ContractError(f"hostile mutation was accepted: {name}")

    try:
        load_json_text('{"schema":"x","schema":"y"}')
    except ContractError:
        rejected += 1
    else:
        raise ContractError("duplicate JSON key was accepted")

    unknown = copy.deepcopy(contract)
    unknown["unknown_field"] = False
    try:
        validate_contract(unknown, check_digest=False)
    except ContractError:
        rejected += 1
    else:
        raise ContractError("unknown contract field was accepted")

    require(rejected == 28, f"negative-control count drifted: {rejected}")
    return rejected


def receipt(contract: dict[str, Any], fixture: dict[str, Any], rejected: int) -> list[tuple[str, str]]:
    s2 = contract["upstream_bindings"]["s2"]
    source = contract["source_contract"]
    governance = contract["governance_boundary"]
    track_b = contract["track_b_boundary"]
    return [
        ("schema", RECEIPT_SCHEMA),
        ("design_status", STATUS),
        ("fixture_only", "true"),
        ("baseline_commit", BASELINE),
        ("s2_schema_version", str(s2["schema_version"])),
        ("s2_ledger_format_version", str(s2["ledger_format_version"])),
        ("s2_schema_sha256", s2["schema_sha256"]),
        ("s2_migration_sha256", s2["migration_sha256"]),
        ("s2_packet_unchanged", "true"),
        ("current_projector_schema", contract["upstream_bindings"]["projector_v0"]["schema"]),
        ("direct_projector_v0_mapping_allowed", "false"),
        ("current_mutable_profile", contract["upstream_bindings"]["legacy_preflight"]["profile"]),
        ("current_mutable_profile_gap_count", str(contract["upstream_bindings"]["legacy_preflight"]["gap_count"])),
        ("s3_gap_count", str(contract["gap_contract"]["count"])),
        ("synthetic_case_count", str(len(fixture["cases"]))),
        ("synthetic_negative_cases_rejected", str(rejected)),
        ("content_free_tombstone_channel_required", "true"),
        ("placeholder_tombstone_evidence_allowed", "false"),
        ("governed_tombstone_source_terminal", "true"),
        ("inbound_tombstoned_target_prunable", "true"),
        ("relationship_authority_basis", "complete_snapshot_latest_target_strictly_before_source_recorded_at"),
        ("cutoff_latest_tier_recheck_allowed", "false"),
        ("provenance_digest_preservation_required", "true"),
        ("read_only_identity_attestation_required", "true"),
        ("sealed_snapshot_projection_binding_required", "true"),
        ("schema_identity_proves_capture_authority", "false"),
        ("producer_profile_reserved", str(source["producer_profile_reserved"]).lower()),
        ("s3_adapter_present", str(source["s3_adapter_present"]).lower()),
        ("projector_invoked", str(source["projector_invoked"]).lower()),
        ("legacy_rows_qualified", str(governance["legacy_rows_qualified"]).lower()),
        ("real_capture_authorized", str(governance["real_capture_authorized"]).lower()),
        ("physical_privacy_deletion_resolved", str(governance["physical_privacy_deletion_resolved"]).lower()),
        ("authority_policy_custody_resolved", str(governance["authority_policy_custody_resolved"]).lower()),
        ("track_b_candidate_interface_status", track_b["candidate_interface_status"]),
        ("track_b_artifact_binding_satisfied", str(track_b["artifact_binding_satisfied"]).lower()),
        ("state_store_surface_present", str(source["state_store_surface_present"]).lower()),
        ("bridge_runtime_surface_present", str(source["bridge_runtime_surface_present"]).lower()),
        ("mcp_surface_present", str(source["mcp_surface_present"]).lower()),
        ("biocortex_runtime_influence", str(source["biocortex_runtime_influence"]).lower()),
        ("side_effects_unlocked", track_b["side_effects_unlocked"]),
        ("sentinels_cleared", "true"),
        ("decision", DECISION),
    ]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--contract", required=True, type=Path)
    parser.add_argument("--fixture", required=True, type=Path)
    parser.add_argument("--source-root", required=True, type=Path)
    args = parser.parse_args()
    try:
        source_root = args.source_root.resolve(strict=True)
        for sentinel in [
            "AB_EVIDENCE_ADAPTER_S3_SENTINEL",
            "AGENT_BRIDGE_EVIDENCE_ADAPTER_S3_SENTINEL",
            "PYTHONINSPECT",
        ]:
            require(sentinel not in os.environ, f"unsanitized environment sentinel reached checker: {sentinel}")
        contract = load_json(args.contract)
        fixture = load_json(args.fixture)
        require(args.contract.read_bytes() == canonical_bytes(contract), "contract is not canonical pretty JSON")
        require(args.fixture.read_bytes() == canonical_bytes(fixture), "fixture is not canonical pretty JSON")
        validate_contract(contract)
        validate_fixture(fixture)
        validate_sources(contract, source_root)
        rejected = negative_controls(contract, fixture)
        for key, value in receipt(contract, fixture, rejected):
            print(f"{key}\t{value}")
    except (ContractError, OSError, UnicodeError, json.JSONDecodeError) as error:
        print(f"S3 contract check failed: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
