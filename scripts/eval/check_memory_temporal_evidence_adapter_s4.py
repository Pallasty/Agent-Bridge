#!/usr/bin/env python3
"""Source-bound structural checker for the S4 synthetic evidence adapter."""

from __future__ import annotations

import argparse
import hashlib
import re
import sys
import tomllib
from pathlib import Path


BASELINE = "630e82dd1c3d4875bd1da081b28e06fdfe90dedf"
STATUS = "SYNTHETIC_MECHANISM_IMPLEMENTED_BLOCKED_PRODUCTION"
DECISION = "BLOCKED_FAIL_CLOSED"
FEATURE = "temporal-evidence-s4-synthetic"

UNCHANGED_SHA256 = {
    "Cargo.lock": "4e2e14ff2806796690da12831c5f9a19a64497401b445b2e8501482ccb0ab4e1",
    "crates/bridge/src/memory_truth.rs": "2e46a521332820b07171b425c95004f35a98887c7c49a2d78baf7740f07195a4",
    "crates/bridge/src/memory_truth_adapter.rs": "c459e96919778c24b0bc699653d8c12b83332e6318b7298deee071a01e90e023",
    "docs/design/MEMORY_TEMPORAL_EVIDENCE_ADAPTER_S3_2026_07_14.md": "b2b236a32300a10ceb77a35ddb5b9217d390db5ddb1d26d73b3bf4fce8bd1fb0",
    "docs/reports/goal-c-u/2026-07-14-biocortex-ab-track-b-evidence-adapter-s3.md": "b0ebeb806fc5053842f3768341403e0441237b4a2860c3953463285c5dd64ba4",
    "scripts/check-memory-temporal-evidence-adapter-s3.sh": "6b141ebaf34452a572c5ebc179e8c707c4a840fac2866c898a59499a0c6dbcb0",
    "scripts/eval/check_memory_temporal_evidence_adapter_s3.py": "1cbc58593e636f57e9f6e35b63ba7cc85875c02b51cd90b5ffda09af5d55e4dd",
    "scripts/eval/fixtures/memory_temporal_evidence_adapter_s3.expected.v0.tsv": "1d8eaa508bf4b53550c2dc9bed573c989edbefbcc550e7604ecfafdb7df4ad03",
    "scripts/eval/fixtures/memory_temporal_evidence_adapter_s3_contract_v0.json": "0efefdc38111bac5f344335be425dc6cf931fa509284833b959e326f7d2e8c2a",
    "scripts/eval/fixtures/memory_temporal_evidence_adapter_s3_synthetic_v0.json": "ce2facc5989883eafb95b7e184868792dfdf511a6bc06c739d01f3556178afea",
}


class CheckFailure(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise CheckFailure(message)


def read(repo: Path, relative: str) -> str:
    path = repo / relative
    require(path.is_file(), f"missing required file: {relative}")
    require(not path.is_symlink(), f"symlink forbidden: {relative}")
    return path.read_text(encoding="utf-8")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def compact(source: str) -> str:
    return re.sub(r"\s+", " ", source)


def struct_body(source: str, name: str) -> tuple[str, str]:
    match = re.search(
        rf"(?P<prefix>(?:#\[[^\n]+\]\s*)*)pub struct {re.escape(name)}\s*\{{(?P<body>.*?)\n\}}",
        source,
        re.DOTALL,
    )
    require(match is not None, f"missing public struct {name}")
    return match.group("prefix"), match.group("body")


def check(repo: Path) -> list[tuple[str, str]]:
    for relative, expected in UNCHANGED_SHA256.items():
        actual = sha256(repo / relative)
        require(actual == expected, f"S3/v0 drift: {relative}: {actual}")

    store_cargo = tomllib.loads(read(repo, "crates/store/Cargo.toml"))
    bridge_cargo = tomllib.loads(read(repo, "crates/bridge/Cargo.toml"))
    require(store_cargo["features"]["default"] == ["onnx-embed"], "store default feature drift")
    require(store_cargo["features"].get(FEATURE) == [], "store S4 feature must be empty/default-off")
    require(bridge_cargo["features"]["default"] == ["onnx-embed"], "bridge default feature drift")
    require(
        bridge_cargo["features"].get(FEATURE) == [f"ab-store/{FEATURE}"],
        "bridge S4 feature must only forward the store feature",
    )

    projection = read(repo, "crates/store/src/sqlite/temporal_evidence/projection_v1.rs")
    projection_flat = compact(projection)
    tests = read(repo, "crates/store/src/sqlite/temporal_evidence/tests.rs")
    bridge_adapter = read(repo, "crates/bridge/src/memory_temporal_evidence_adapter_v1.rs")
    bridge_lib = read(repo, "crates/bridge/src/lib.rs")
    store_lib = read(repo, "crates/store/src/lib.rs")
    sqlite = read(repo, "crates/store/src/sqlite.rs")
    temporal = read(repo, "crates/store/src/sqlite/temporal_evidence.rs")
    design = read(repo, "docs/design/MEMORY_TEMPORAL_EVIDENCE_ADAPTER_S4_2026_07_14.md")
    report = read(repo, "docs/reports/goal-c-u/2026-07-14-biocortex-ab-track-b-evidence-adapter-s4.md")

    require(f'feature = "{FEATURE}"' in temporal, "projection module is not feature/test gated")
    require(f'feature = "{FEATURE}"' in sqlite, "SQLite reexport is not feature gated")
    require("pub use temporal_evidence::*" not in sqlite, "wildcard temporal-evidence reexport forbidden")
    require(f'feature = "{FEATURE}"' in store_lib, "store facade is not feature gated")
    require(f'feature = "{FEATURE}"' in bridge_lib, "bridge module is not feature gated")
    require("pub(crate) mod memory_temporal_evidence_adapter_v1;" in bridge_lib, "bridge module must be crate-private")
    require("pub(crate) async fn project_synthetic_temporal_evidence_v1" in bridge_adapter, "bridge wrapper must be crate-private")
    require("pub async fn project_synthetic_temporal_evidence_v1" not in bridge_adapter, "public bridge wrapper forbidden")
    require("StateStore" not in projection and "impl SqliteStore" not in projection, "S4 API entered a write-shaped store surface")
    state_store_suffix = store_lib[store_lib.index("pub trait StateStore") :]
    require("temporal_truth_" not in state_store_suffix, "S4 method entered StateStore trait")
    require("SyntheticTemporalTruthProjection" not in state_store_suffix, "S4 permit entered StateStore trait")

    permit_prefix, permit_body = struct_body(projection, "SyntheticTemporalTruthProjectionPermitV1")
    require("pub " not in permit_body, "permit fields must remain private")
    require("Debug" in permit_prefix, "permit Debug marker missing")
    for forbidden in ("Clone", "Copy", "Default", "Serialize", "Deserialize"):
        require(forbidden not in permit_prefix, f"permit must not derive {forbidden}")
    literals = list(re.finditer(r"SyntheticTemporalTruthProjectionPermitV1\s*\{\s*_private:\s*\(\)\s*\}", projection))
    require(len(literals) == 1, f"expected one permit struct literal, got {len(literals)}")
    permit_context = projection[max(0, literals[0].start() - 240) : literals[0].start()]
    require("#[cfg(test)]" in permit_context and "pub(super) fn synthetic_projection_permit_v1" in permit_context,
            "sole permit constructor must be cfg(test) pub(super)")
    require(
        not re.search(r"pub\s+fn\s+\w+\s*\([^)]*\)\s*->\s*SyntheticTemporalTruthProjectionPermitV1", projection),
        "non-test/public permit factory forbidden",
    )
    require(
        "_permit: SyntheticTemporalTruthProjectionPermitV1" in projection_flat,
        "one-shot API must consume permit by value",
    )

    bound_prefix, bound_body = struct_body(projection, "BoundTemporalTruthProjectionV1")
    require("pub " not in bound_body, "bound result fields must remain private")
    for forbidden in ("Clone", "Default", "Serialize", "Deserialize"):
        require(forbidden not in bound_prefix, f"bound result must not derive {forbidden}")
    for type_name in ("SyntheticTemporalTruthProjectionPermitV1", "BoundTemporalTruthProjectionV1"):
        require(
            not re.search(
                rf"impl\s+(?:serde::)?(?:Serialize|Deserialize|Default|Clone)\s+for\s+{type_name}",
                projection,
            ),
            f"manual serialization/default/clone impl forbidden for {type_name}",
        )

    api = projection[projection.index("pub async fn temporal_truth_project_read_only_synthetic_v1") :]
    ordered = [
        "SQLITE_OPEN_READ_ONLY",
        "PRAGMA query_only=ON; PRAGMA foreign_keys=ON;",
        "is_readonly(rusqlite::MAIN_DB)",
        "TransactionBehavior::Deferred",
        "load_snapshot(",
        "prepare_snapshot_v1(",
        "seal_projection_v1(",
        "transaction.commit()",
        "connection.total_changes()",
    ]
    cursor = -1
    for token in ordered:
        position = api.find(token, cursor + 1)
        require(position >= 0, f"atomic/read-only token missing or out of order: {token}")
        cursor = position

    prepare = projection[
        projection.index("fn prepare_snapshot_v1") : projection.index("fn prepared_input_digest_v1")
    ]
    prepare_flat = compact(prepare)
    require(
        "find(|target| target.recorded_at < revision.recorded_at)" in prepare_flat,
        "source-time authority must use latest target strictly before source",
    )
    require(
        prepare.index("had_outgoing_governance") < prepare.index("let tombstoned"),
        "governed tombstone must terminate before mapping",
    )
    require("provenance_sha256" in projection and "source_key" in projection, "lossless provenance fields missing")
    suppression = projection[
        projection.index("fn derive_suppression_v1") : projection.index("fn intrinsic_temporal_state_v1")
    ]
    require("resolved_truth_tier" not in suppression, "visible graph must not recheck cutoff-latest target tier")
    visible = projection[
        projection.index("fn select_visible_revisions_v1") : projection.index("fn validate_visible_aliases_v1")
    ]
    require("recorded_at > knowledge_cutoff" in visible, "cutoff selection missing from projection stage")
    require("snapshot.revisions" in prepare, "prepare stage must receive complete snapshot revisions")

    require(len(re.findall(r"(?:async\s+)?fn temporal_truth_projection_s4_", tests)) == 7, "S4 test count must be seven")
    require(len(re.findall(r"(?:async\s+)?fn truth_evidence_s2_", tests)) == 14, "S2 regression count must be fourteen")
    for test_name in (
        "source_time_authority_survives_later_target_upgrade",
        "post_cutoff_is_bound_but_not_projected",
        "tombstoned_target_prunes_but_governed_source_rejects",
        "identity_drift_rejects_without_migration",
    ):
        require(test_name in tests, f"missing S4 adversarial test: {test_name}")

    allowed_bridge = {
        repo / "crates/bridge/src/lib.rs",
        repo / "crates/bridge/src/memory_temporal_evidence_adapter_v1.rs",
    }
    for path in (repo / "crates/bridge/src").rglob("*.rs"):
        if path in allowed_bridge:
            continue
        source = path.read_text(encoding="utf-8")
        require("temporal_truth_project_read_only_synthetic_v1" not in source,
                f"unexpected Bridge runtime caller: {path.relative_to(repo)}")
        require("project_synthetic_temporal_evidence_v1" not in source,
                f"unexpected Bridge wrapper caller: {path.relative_to(repo)}")

    allowed_store = {
        repo / "crates/store/src/lib.rs",
        repo / "crates/store/src/sqlite.rs",
        repo / "crates/store/src/sqlite/temporal_evidence.rs",
        repo / "crates/store/src/sqlite/temporal_evidence/projection_v1.rs",
        repo / "crates/store/src/sqlite/temporal_evidence/tests.rs",
    }
    for path in (repo / "crates/store/src").rglob("*.rs"):
        if path in allowed_store:
            continue
        source = path.read_text(encoding="utf-8")
        require("temporal_truth_project_read_only_synthetic_v1" not in source,
                f"unexpected store caller: {path.relative_to(repo)}")
        require("SyntheticTemporalTruthProjectionPermitV1" not in source,
                f"unexpected store permit reference: {path.relative_to(repo)}")

    require("SYNTHETIC_MECHANISM_IMPLEMENTED_BLOCKED_PRODUCTION" in design, "design status drift")
    require("BLOCKED_FAIL_CLOSED" in design and "BLOCKED_FAIL_CLOSED" in report, "decision drift")
    require("no safe non-test constructor" in report, "report must state permit boundary")
    require("reports no latency" in design, "design must reject unsupported performance claims")
    remaining_codes = (
        "AUTHORITY_POLICY_CUSTODY_UNRESOLVED",
        "CANDIDATE_EVIDENCE_INTERFACE_UNIMPLEMENTED",
        "CAPTURE_PROVENANCE_UNATTESTED",
        "CROSS_BIOCORTEX_OPAQUE_HANDLE_TRANSPORT_UNIMPLEMENTED",
        "PHYSICAL_PRIVACY_DELETION_UNRESOLVED",
        "PRODUCTION_PRODUCER_PROFILE_UNADMITTED",
    )
    for code in remaining_codes:
        require(code in report, f"remaining gap missing from report: {code}")

    return [
        ("schema", "agent_bridge.memory_temporal_evidence_adapter_s4_receipt.v1"),
        ("status", STATUS),
        ("baseline_commit", BASELINE),
        ("s2_schema_version", "43"),
        ("s2_ledger_format_version", "0"),
        ("projection_schema", "agent_bridge.temporal_truth_projection.v1"),
        ("mapping_version", "sqlite_v43_full_ledger_source_time_v1"),
        ("feature_default", "false"),
        ("safe_non_test_permit_constructor", "false"),
        ("physical_read_only_attested", "true"),
        ("query_only_attested", "true"),
        ("zero_total_changes_attested", "true"),
        ("single_transaction_load_map_project_seal", "true"),
        ("governed_tombstone_source_terminal", "true"),
        ("inbound_tombstoned_target_prunable", "true"),
        ("relationship_authority_basis", "complete_snapshot_latest_target_strictly_before_source_recorded_at"),
        ("physical_admission_witness_claimed", "false"),
        ("cutoff_latest_tier_recheck_allowed", "false"),
        ("provenance_digest_preserved", "true"),
        ("sealed_snapshot_projection_binding", "true"),
        ("s4_test_count", "7"),
        ("s2_regression_test_count", "14"),
        ("synthetic_interface_gaps_resolved", "5"),
        ("remaining_gap_count", "6"),
        ("remaining_gap_codes", ",".join(remaining_codes)),
        ("bridge_wrapper_present", "true"),
        ("bridge_runtime_caller_present", "false"),
        ("candidate_evidence_interface_implemented", "false"),
        ("capture_provenance_attested", "false"),
        ("cross_biocortex_opaque_transport_implemented", "false"),
        ("legacy_rows_qualified", "false"),
        ("production_profile_active", "false"),
        ("real_capture_authorized", "false"),
        ("physical_privacy_deletion_resolved", "false"),
        ("authority_policy_custody_resolved", "false"),
        ("track_b_artifact_binding_satisfied", "false"),
        ("state_store_surface_present", "false"),
        ("mcp_surface_present", "false"),
        ("biocortex_runtime_influence", "false"),
        ("performance_claimed", "false"),
        ("side_effects_unlocked", "NONE"),
        ("decision", DECISION),
    ]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    args = parser.parse_args()
    try:
        rows = check(args.repo.resolve())
    except (CheckFailure, KeyError, OSError, ValueError) as error:
        print(f"S4_CHECK_FAILED\t{error}", file=sys.stderr)
        return 1
    for key, value in rows:
        print(f"{key}\t{value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
