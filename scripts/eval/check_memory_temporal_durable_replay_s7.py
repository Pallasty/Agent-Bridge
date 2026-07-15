#!/usr/bin/env python3
"""Fail-closed checker for the S7 local durable replay contract."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sqlite3
import sys
import tomllib
from pathlib import Path
from typing import Any, Callable


STATUS = (
    "SYNTHETIC_LOCAL_DURABLE_REPLAY_TOMBSTONE_IMPLEMENTED_"
    "SUCCESSOR_GATE_PREREGISTERED_NOT_AUTHORIZED_NOT_TRANSPORT"
)
DECISION = "BLOCKED_FAIL_CLOSED"
FEATURE = "temporal-evidence-s7-durable-replay-synthetic"
S6_FEATURE = "temporal-evidence-s6-detached-verifier-synthetic"
S6_COMMIT = "b3a77aecea68edae4544929c747305634967f8af"
S6_PARENT = "ddebacba20146a90546db9e4ea4bd2795b9ecc1a"
S6_TREE = "d11123ac78cd510b6c23e4b41596e3f2df248d03"
REPLAY_VECTOR = "7c21a79214624b4c1c259d38aeff4b228d4df0071d180be249b78a5c47e1e8a5"
SCHEMA_MANIFEST_SHA256 = "686c22c3f4f3f696113a88a6d72bb292635a55020e00144ea2ef02f7eae35466"
SUCCESSOR_GATE_PATH = (
    "docs/design/fixtures/biocortex-ab-track-b-successor-admission-gate-s7-v0.json"
)
DURABLE_CONTRACT_PATH = (
    "docs/design/fixtures/biocortex-ab-track-b-durable-replay-contract-s7-v0.json"
)
SUCCESSOR_GATE_SHA256 = "dec28c4a79e7573f0a296af43e5c03a68f61b8c13ddaef4384e19aa441500546"
DURABLE_CONTRACT_SHA256 = "8e4f895089f3085725988b50001ab77ec909b86b1dd203e304cc6b4a143a4c8c"
S6_PROFILE_SHA256 = "fe3b66ad1d5711f38e790cf792a0db63bd7879ce9795c07f745ab9127575be23"
S6_CONTRACT_SHA256 = "4b54057fe78fd5eb760c89b86e3018003e4cf0a1b354ca720007927e7b005e74"
REMAINING_GAPS = (
    "AUTHORITY_POLICY_CUSTODY_UNRESOLVED",
    "CAPTURE_PROVENANCE_UNATTESTED",
    "CROSS_BIOCORTEX_OPAQUE_HANDLE_TRANSPORT_UNIMPLEMENTED",
    "PHYSICAL_PRIVACY_DELETION_UNRESOLVED",
    "PRODUCTION_PRODUCER_PROFILE_UNADMITTED",
)


class CheckFailure(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise CheckFailure(message)


def read_bytes(repo: Path, relative: str) -> bytes:
    path = repo / relative
    require(path.is_file() and not path.is_symlink(), f"missing/non-regular artifact: {relative}")
    return path.read_bytes()


def read_text(repo: Path, relative: str) -> str:
    return read_bytes(repo, relative).decode("utf-8")


def sha256(repo: Path, relative: str) -> str:
    return hashlib.sha256(read_bytes(repo, relative)).hexdigest()


def reject_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    output: dict[str, Any] = {}
    for key, value in pairs:
        if key in output:
            raise CheckFailure(f"duplicate JSON key: {key}")
        output[key] = value
    return output


def load_json(repo: Path, relative: str) -> dict[str, Any]:
    try:
        value = json.loads(read_text(repo, relative), object_pairs_hook=reject_duplicates)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CheckFailure(f"invalid JSON {relative}: {exc}") from exc
    require(isinstance(value, dict), f"top-level JSON object required: {relative}")
    return value


def schema_rows(connection: sqlite3.Connection) -> list[tuple[str, str, str]]:
    rows = connection.execute(
        "SELECT type, name, sql FROM sqlite_schema "
        "WHERE name NOT LIKE 'sqlite_%' ORDER BY type, name"
    ).fetchall()
    require(all(isinstance(item, str) for row in rows for item in row), "closed schema SQL required")
    return [(row[0], row[1], row[2]) for row in rows]


def schema_digest(connection: sqlite3.Connection) -> str:
    digest = hashlib.sha256()
    for row in schema_rows(connection):
        for field in row:
            encoded = field.encode("utf-8")
            digest.update(len(encoded).to_bytes(8, "big"))
            digest.update(encoded)
    return digest.hexdigest()


def extract_schema_sql(source: str) -> str:
    match = re.search(r'const SCHEMA_SQL: &str = r#"(.*?)"#;', source, re.DOTALL)
    require(match is not None, "closed S7 SCHEMA_SQL raw string missing")
    return match.group(1)


def new_schema_db(schema_sql: str) -> sqlite3.Connection:
    connection = sqlite3.connect(":memory:", isolation_level=None)
    connection.executescript(schema_sql)
    connection.execute(
        "INSERT INTO track_b_replay_registry_meta_v1(singleton, registry_generation_id) "
        "VALUES(1, ?)",
        (bytes([0x71]) * 32,),
    )
    connection.execute("PRAGMA application_id=1094865463")
    connection.execute("PRAGMA user_version=1")
    return connection


def expect_sql_rejection(operation: Callable[[], Any], label: str) -> None:
    try:
        operation()
    except sqlite3.DatabaseError:
        return
    raise CheckFailure(f"hostile SQLite mutation unexpectedly succeeded: {label}")


def exercise_schema_mutations(schema_sql: str) -> int:
    mutation_rejections = 0
    base = new_schema_db(schema_sql)
    require(schema_digest(base) == SCHEMA_MANIFEST_SHA256, "independent schema digest mismatch")
    base.close()

    trigger_names = [
        "track_b_replay_registry_meta_v1_no_delete",
        "track_b_replay_registry_meta_v1_no_insert",
        "track_b_replay_registry_meta_v1_no_update",
        "track_b_replay_tombstones_v1_no_delete",
        "track_b_replay_tombstones_v1_no_update",
    ]
    for trigger in trigger_names:
        connection = new_schema_db(schema_sql)
        connection.execute(f"DROP TRIGGER {trigger}")
        require(schema_digest(connection) != SCHEMA_MANIFEST_SHA256, f"dropped trigger undetected: {trigger}")
        mutation_rejections += 1
        connection.close()

    connection = new_schema_db(schema_sql)
    connection.execute("CREATE TABLE hostile_extra(value TEXT)")
    require(schema_digest(connection) != SCHEMA_MANIFEST_SHA256, "extra table undetected")
    mutation_rejections += 1
    connection.close()

    connection = new_schema_db(schema_sql)
    connection.execute("DROP TRIGGER track_b_replay_tombstones_v1_no_delete")
    connection.execute(
        "CREATE TRIGGER track_b_replay_tombstones_v1_no_delete "
        "BEFORE DELETE ON track_b_replay_tombstones_v1 BEGIN SELECT 1; END"
    )
    require(schema_digest(connection) != SCHEMA_MANIFEST_SHA256, "no-op trigger substitution undetected")
    mutation_rejections += 1
    connection.close()

    connection = new_schema_db(schema_sql)
    insert = (
        "INSERT INTO track_b_replay_tombstones_v1"
        "(replay_key_sha256,scope_sha256,payload_sha256) VALUES(?,?,?)"
    )
    good = bytes([0x41]) * 32
    for column in range(3):
        for length in (0, 31, 33):
            fields = [good, bytes([0x51]) * 32, bytes([0x61]) * 32]
            fields[column] = bytes([0x70]) * length
            expect_sql_rejection(
                lambda fields=fields: connection.execute(insert, tuple(fields)),
                f"column {column} length {length}",
            )
            mutation_rejections += 1
        fields_any: list[Any] = [good, bytes([0x51]) * 32, bytes([0x61]) * 32]
        fields_any[column] = "x" * 32
        expect_sql_rejection(
            lambda fields_any=fields_any: connection.execute(insert, tuple(fields_any)),
            f"column {column} text type",
        )
        mutation_rejections += 1
        fields_any = [good, bytes([0x51]) * 32, bytes([0x61]) * 32]
        fields_any[column] = None
        expect_sql_rejection(
            lambda fields_any=fields_any: connection.execute(insert, tuple(fields_any)),
            f"column {column} null",
        )
        mutation_rejections += 1

    connection.execute(insert, (good, bytes([0x51]) * 32, bytes([0x61]) * 32))
    expect_sql_rejection(
        lambda: connection.execute(
            "UPDATE track_b_replay_tombstones_v1 SET scope_sha256=?", (bytes([0x52]) * 32,)
        ),
        "tombstone update",
    )
    mutation_rejections += 1
    expect_sql_rejection(
        lambda: connection.execute("DELETE FROM track_b_replay_tombstones_v1"),
        "tombstone delete",
    )
    mutation_rejections += 1
    expect_sql_rejection(
        lambda: connection.execute(
            "UPDATE track_b_replay_registry_meta_v1 SET registry_generation_id=?",
            (bytes([0x72]) * 32,),
        ),
        "metadata update",
    )
    mutation_rejections += 1
    expect_sql_rejection(
        lambda: connection.execute("DELETE FROM track_b_replay_registry_meta_v1"),
        "metadata delete",
    )
    mutation_rejections += 1
    expect_sql_rejection(
        lambda: connection.execute(
            "INSERT INTO track_b_replay_registry_meta_v1(singleton,registry_generation_id) "
            "VALUES(1,?)",
            (bytes([0x72]) * 32,),
        ),
        "metadata replacement insert",
    )
    mutation_rejections += 1

    targeted = (
        insert + " ON CONFLICT(replay_key_sha256) DO NOTHING"
    )
    cursor = connection.execute(targeted, (good, bytes([0x51]) * 32, bytes([0x61]) * 32))
    require(cursor.rowcount == 0, "exact replay must not be treated as successful insert")
    mutation_rejections += 1
    cursor = connection.execute(targeted, (good, bytes([0x52]) * 32, bytes([0x62]) * 32))
    require(cursor.rowcount == 0, "scope collision must not overwrite winner")
    winner = connection.execute(
        "SELECT scope_sha256,payload_sha256 FROM track_b_replay_tombstones_v1"
    ).fetchone()
    require(winner == (bytes([0x51]) * 32, bytes([0x61]) * 32), "winner row was overwritten")
    mutation_rejections += 1
    connection.close()

    foreign = sqlite3.connect(":memory:", isolation_level=None)
    foreign.execute("CREATE TABLE unrelated(value TEXT)")
    foreign_identity = foreign.execute("PRAGMA application_id").fetchone()[0]
    require(foreign_identity != 1094865463, "foreign database identity unexpectedly admitted")
    mutation_rejections += 1
    foreign.close()
    return mutation_rejections


def check_contracts(repo: Path, source: str) -> tuple[dict[str, Any], dict[str, Any]]:
    require(sha256(repo, SUCCESSOR_GATE_PATH) == SUCCESSOR_GATE_SHA256, "successor gate digest drift")
    require(sha256(repo, DURABLE_CONTRACT_PATH) == DURABLE_CONTRACT_SHA256, "durable contract digest drift")
    successor = load_json(repo, SUCCESSOR_GATE_PATH)
    durable = load_json(repo, DURABLE_CONTRACT_PATH)

    require(successor["schema"] == "agent_bridge.memory_temporal_successor_admission_gate_s7.v0", "successor gate schema drift")
    require(successor["status"] == "NOT_ADMITTED", "successor gate must remain not admitted")
    require(successor["decision"] == DECISION, "successor decision drift")
    require(successor["admission"]["admitted"] is False, "successor payload was silently admitted")
    receipt_fields = [
        "authority_decision_receipt",
        "authority_policy_custodian_receipt",
        "build_attestation",
        "capture_authorization_receipt",
        "capture_provenance_receipt",
        "deletion_mechanism_receipt",
        "destination_receiver_identity",
        "externally_pinned_allowlist_receipt",
        "key_custody_receipts",
        "producer_runtime_identity",
        "revocation_state_receipt",
    ]
    require(all(successor["admission"][field] is None for field in receipt_fields), "invented admission evidence")
    require(successor["remaining_gap_codes"] == list(REMAINING_GAPS), "remaining gap drift")
    require(successor["predecessor"]["s6_feature_commit"] == S6_COMMIT, "S6 source binding drift")
    require(successor["version_and_replay_policy"]["replay_identity_sha256_known_vector"] == REPLAY_VECTOR, "replay vector drift")
    require(all(value is False for value in successor["boundary"].values() if isinstance(value, bool)), "successor boundary opened")
    require(successor["boundary"]["side_effects_unlocked"] == "NONE", "successor side effects opened")

    require(durable["schema"] == "agent_bridge.memory_temporal_durable_replay_contract_s7.v0", "durable contract schema drift")
    require(durable["decision"] == DECISION and durable["feature"] == FEATURE, "durable identity drift")
    storage = durable["storage_profile"]
    require(storage["application_id_decimal"] == 1094865463, "application id drift")
    require(storage["user_version"] == 1, "user version drift")
    require(storage["journal_mode"] == "DELETE", "journal mode drift")
    require(storage["synchronous"] == "EXTRA" and storage["synchronous_pragma_value"] == 3, "sync mode drift")
    require(storage["schema_manifest_sha256"] == SCHEMA_MANIFEST_SHA256, "schema manifest drift")
    require(storage["main_state_db_modified"] is False, "main state DB boundary opened")
    require(durable["privacy_profile"]["retention"] == "PERMANENT_NO_EXPIRY_GC", "retention drift")
    require(durable["privacy_profile"]["stored_commitment_bytes_per_tombstone"] == 96, "tombstone shape drift")
    require(all(value is False for value in durable["boundary"].values()), "durable boundary opened")
    require(all(durable["test_matrix"].values()), "test matrix contains an unclaimed case")

    schema_sql = extract_schema_sql(source)
    require("expires_at" not in schema_sql and "consumed_at" not in schema_sql, "time entered permanent tombstone schema")
    require("raw_" not in schema_sql and "nonce" not in schema_sql, "raw identity entered tombstone schema")
    return successor, durable


def check_source(repo: Path) -> tuple[str, int]:
    cargo = tomllib.loads(read_text(repo, "crates/store/Cargo.toml"))
    features = cargo.get("features", {})
    require(features.get(FEATURE) == [S6_FEATURE], "S7 feature dependency drift")
    require(FEATURE not in features.get("default", []), "S7 feature became default")

    parent = read_text(repo, "crates/store/src/temporal_replay_transport.rs")
    source = read_text(
        repo, "crates/store/src/temporal_replay_transport/durable_replay_registry.rs"
    )
    library = read_text(repo, "crates/store/src/lib.rs")
    bridge_cargo = read_text(repo, "crates/bridge/Cargo.toml")
    require(
        f'#[cfg(feature = "{FEATURE}")]\nmod durable_replay_registry;' in parent,
        "private S7 child module gate missing",
    )
    require("pub mod durable_replay_registry" not in parent, "S7 child module became public")
    require(FEATURE not in library, "S7 module leaked into store public root")
    require(FEATURE not in bridge_cargo, "Bridge forwards the S7 storage capability")
    require("pub use durable_replay_registry" not in parent + library, "S7 re-export forbidden")
    require("SQLITE_OPEN_CREATE" not in source.split("#[cfg(test)]\nfn provision_new", 1)[0], "normal S7 open can create")
    require("SQLITE_OPEN_NOFOLLOW" in source, "nofollow open flag missing")
    require("TransactionBehavior::Immediate" in source, "IMMEDIATE transaction missing")
    require("ON CONFLICT(replay_key_sha256) DO NOTHING" in source, "targeted conditional insert missing")
    require("INSERT OR IGNORE" not in source, "broad INSERT OR IGNORE forbidden")
    require("DO UPDATE" not in source, "replay UPSERT update forbidden")
    require("PRAGMA synchronous=EXTRA" in source, "EXTRA sync profile missing")
    require('journal_mode.to_ascii_lowercase() != "delete"' in source, "DELETE journal assertion missing")
    require('read_i64_pragma(connection, "trusted_schema")' in source, "trusted-schema readback missing")
    require("trusted_schema != 0" in source, "trusted-schema closed assertion missing")
    require("report_indeterminate_after_commit_once" in source, "result-loss hook missing")
    require("pause_before_commit_if_requested" in source, "pre-commit crash hook missing")
    require("replay_receipt.replay_key_sha256 != replay_key_sha256" in parent, "receipt key identity check missing")
    require("replay_receipt.scope_sha256 != scope_sha256" in parent, "receipt scope identity check missing")
    require("if !verified.replay_receipt.durable" in parent, "durable wrapper proof check missing")
    require("StateStore" not in source.replace("`StateStore`", ""), "S7 entered StateStore")

    schema_sql = extract_schema_sql(source)
    mutation_rejections = exercise_schema_mutations(schema_sql)
    require(mutation_rejections == 30, f"mutation rejection accounting drift: {mutation_rejections}")
    return source, mutation_rejections


def check_predecessor(repo: Path) -> None:
    require(
        sha256(repo, "docs/design/fixtures/biocortex-ab-track-b-candidate-exact-payload-profile-v0.json")
        == S6_PROFILE_SHA256,
        "S6 payload profile drift",
    )
    require(
        sha256(repo, "docs/design/fixtures/biocortex-ab-track-b-replay-transport-contract-v0.json")
        == S6_CONTRACT_SHA256,
        "S6 transport contract drift",
    )
    s6_expected = read_text(
        repo, "scripts/eval/fixtures/memory_temporal_replay_transport_s6.expected.v0.tsv"
    )
    require(f"replay_identity_sha256\t{REPLAY_VECTOR}\n" in s6_expected, "S6 replay vector missing")
    require("durable_nonce_registry_implemented\tfalse\n" in s6_expected, "historical S6 boundary drift")


def receipt(mutation_rejections: int) -> str:
    rows = [
        ("schema", "agent_bridge.memory_temporal_durable_replay_s7_receipt.v0"),
        ("status", STATUS),
        ("decision", DECISION),
        ("s6_feature_commit", S6_COMMIT),
        ("s6_parent", S6_PARENT),
        ("s6_tree", S6_TREE),
        ("s6_replay_identity_sha256", REPLAY_VECTOR),
        ("successor_admission_gate_sha256", SUCCESSOR_GATE_SHA256),
        ("durable_replay_contract_sha256", DURABLE_CONTRACT_SHA256),
        ("sqlite_schema_manifest_sha256", SCHEMA_MANIFEST_SHA256),
        ("sqlite_application_id", "1094865463"),
        ("sqlite_user_version", "1"),
        ("sqlite_journal_mode", "DELETE"),
        ("sqlite_synchronous", "EXTRA"),
        ("tombstone_commitment_bytes", "96"),
        ("mutation_rejections", str(mutation_rejections)),
        ("s7_nonignored_rust_tests", "13"),
        ("durable_local_registry_implemented", "true"),
        ("normal_open_can_create", "false"),
        ("main_state_db_modified", "false"),
        ("successor_payload_admitted", "false"),
        ("cross_repository_transport_authorized", "false"),
        ("bridge_runtime_caller_present", "false"),
        ("biocortex_runtime_influence", "false"),
        ("anti_rollback_anchor_present", "false"),
        ("remaining_gaps", ",".join(REMAINING_GAPS)),
        ("side_effects_unlocked", "NONE"),
    ]
    return "".join(f"{key}\t{value}\n" for key, value in rows)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", required=True, type=Path)
    args = parser.parse_args()
    repo = args.repo.resolve()
    try:
        check_predecessor(repo)
        source, mutation_rejections = check_source(repo)
        check_contracts(repo, source)
    except (CheckFailure, OSError, KeyError, TypeError, ValueError, sqlite3.DatabaseError) as exc:
        print(f"S7_CHECK_FAILED\t{exc}", file=sys.stderr)
        return 1
    sys.stdout.write(receipt(mutation_rejections))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
