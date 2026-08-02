#![cfg(feature = "codebase-index-bounded-native-a1")]

use ab_store::{CodebaseIndexA1Failpoint, CodebaseIndexA1Options, SqliteStore, StateStore};
use std::path::Path;
use tokio_rusqlite::rusqlite::{self, params, Connection};

#[derive(Clone, Debug, PartialEq, Eq)]
struct SymbolRow {
    id: i64,
    file_path: String,
    line: i64,
    col: i64,
    kind: String,
    name: String,
    signature: String,
    language: String,
    root_path: String,
    indexed_at: i64,
    embedding: Option<Vec<u8>>,
}

#[derive(Clone, Debug, PartialEq, Eq)]
struct ImportRow {
    id: i64,
    file_path: String,
    line: i64,
    language: String,
    raw: String,
    target: String,
    alias: Option<String>,
    root_path: String,
    indexed_at: i64,
}

#[derive(Clone, Debug, PartialEq, Eq)]
struct CallRow {
    id: i64,
    file_path: String,
    line: i64,
    language: String,
    caller: String,
    callee: String,
    root_path: String,
    indexed_at: i64,
}

#[derive(Clone, Debug, PartialEq, Eq)]
struct AuthoritativeSnapshot {
    symbols: Vec<SymbolRow>,
    imports: Vec<ImportRow>,
    calls: Vec<CallRow>,
}

#[derive(Clone, Debug, PartialEq, Eq)]
struct SqliteInvariants {
    schema: Vec<(String, String, String, String)>,
    schema_meta_version: String,
    schema_version: i64,
    user_version: i64,
    journal_mode: String,
    database_names: Vec<String>,
    page_count: i64,
    freelist_count: i64,
    integrity_check: String,
    foreign_key_violations: usize,
}

impl AuthoritativeSnapshot {
    fn normalize_target_clock(mut self, target_root: &str) -> Self {
        for row in &mut self.symbols {
            if row.root_path == target_root {
                row.indexed_at = 0;
            }
        }
        for row in &mut self.imports {
            if row.root_path == target_root {
                row.indexed_at = 0;
            }
        }
        for row in &mut self.calls {
            if row.root_path == target_root {
                row.indexed_at = 0;
            }
        }
        self
    }
}

fn source_fixture(source_root: &Path) {
    std::fs::create_dir_all(source_root).expect("create source root");
    std::fs::write(
        source_root.join("seed.rs"),
        "use crate::engine::Engine;\npub fn run() {\n    Engine::new();\n    helper();\n}\nimpl Worker {\n    fn execute(&self) {\n        helper();\n    }\n}\nfn helper() {}\n",
    )
    .expect("write source fixture");
}

fn multitype_source_fixture(source_root: &Path) {
    source_fixture(source_root);
    std::fs::write(
        source_root.join("worker.py"),
        "import os as operating_system\n\ndef process(value):\n    print(value)\n    return helper(value)\n\ndef helper(value):\n    return value\n",
    )
    .expect("write Python fixture");
    std::fs::write(
        source_root.join("client.ts"),
        "import { Engine } from './engine';\nexport function start(): void {\n  Engine.create();\n  finish();\n}\nfunction finish(): void {}\n",
    )
    .expect("write TypeScript fixture");
    std::fs::write(
        source_root.join("main.go"),
        "package main\nimport \"fmt\"\nfunc main() {\n    fmt.Println(\"ready\")\n    helper()\n}\nfunc helper() {}\n",
    )
    .expect("write Go fixture");
}

fn seed_authoritative_rows(db_path: &Path, target_root: &str, other_root: &str) {
    let connection = Connection::open(db_path).expect("open seed connection");
    for root in [target_root, other_root] {
        connection
            .execute(
                "INSERT INTO codebase_symbols
                 (file_path, line, col, kind, name, signature, language, root_path,
                  indexed_at, embedding)
                 VALUES (?1, 7, 3, 'fn', 'old_symbol', 'old()', 'rust', ?2, 11, X'010203')",
                params![format!("{root}/old.rs"), root],
            )
            .expect("seed symbol");
        connection
            .execute(
                "INSERT INTO codebase_imports
                 (file_path, line, language, raw, target, alias, root_path, indexed_at)
                 VALUES (?1, 8, 'rust', 'use old::Item;', 'old::Item', 'Old', ?2, 11)",
                params![format!("{root}/old.rs"), root],
            )
            .expect("seed import");
        connection
            .execute(
                "INSERT INTO codebase_calls
                 (file_path, line, language, caller, callee, root_path, indexed_at)
                 VALUES (?1, 9, 'rust', 'old_symbol', 'old_call', ?2, 11)",
                params![format!("{root}/old.rs"), root],
            )
            .expect("seed call");
    }
}

fn authoritative_snapshot(db_path: &Path) -> AuthoritativeSnapshot {
    let connection = Connection::open(db_path).expect("open snapshot connection");
    let symbols = connection
        .prepare(
            "SELECT id, file_path, line, col, kind, name, signature, language,
                    root_path, indexed_at, embedding
             FROM codebase_symbols ORDER BY id",
        )
        .expect("prepare symbols snapshot")
        .query_map([], |row| {
            Ok(SymbolRow {
                id: row.get(0)?,
                file_path: row.get(1)?,
                line: row.get(2)?,
                col: row.get(3)?,
                kind: row.get(4)?,
                name: row.get(5)?,
                signature: row.get(6)?,
                language: row.get(7)?,
                root_path: row.get(8)?,
                indexed_at: row.get(9)?,
                embedding: row.get(10)?,
            })
        })
        .expect("query symbols snapshot")
        .collect::<rusqlite::Result<Vec<_>>>()
        .expect("collect symbols snapshot");
    let imports = connection
        .prepare(
            "SELECT id, file_path, line, language, raw, target, alias, root_path, indexed_at
             FROM codebase_imports ORDER BY id",
        )
        .expect("prepare imports snapshot")
        .query_map([], |row| {
            Ok(ImportRow {
                id: row.get(0)?,
                file_path: row.get(1)?,
                line: row.get(2)?,
                language: row.get(3)?,
                raw: row.get(4)?,
                target: row.get(5)?,
                alias: row.get(6)?,
                root_path: row.get(7)?,
                indexed_at: row.get(8)?,
            })
        })
        .expect("query imports snapshot")
        .collect::<rusqlite::Result<Vec<_>>>()
        .expect("collect imports snapshot");
    let calls = connection
        .prepare(
            "SELECT id, file_path, line, language, caller, callee, root_path, indexed_at
             FROM codebase_calls ORDER BY id",
        )
        .expect("prepare calls snapshot")
        .query_map([], |row| {
            Ok(CallRow {
                id: row.get(0)?,
                file_path: row.get(1)?,
                line: row.get(2)?,
                language: row.get(3)?,
                caller: row.get(4)?,
                callee: row.get(5)?,
                root_path: row.get(6)?,
                indexed_at: row.get(7)?,
            })
        })
        .expect("query calls snapshot")
        .collect::<rusqlite::Result<Vec<_>>>()
        .expect("collect calls snapshot");
    AuthoritativeSnapshot {
        symbols,
        imports,
        calls,
    }
}

fn sqlite_invariants(db_path: &Path) -> SqliteInvariants {
    let connection = Connection::open(db_path).expect("open invariant connection");
    let schema = connection
        .prepare(
            "SELECT type, name, tbl_name, COALESCE(sql, '')
             FROM sqlite_schema ORDER BY type, name, tbl_name",
        )
        .expect("prepare schema snapshot")
        .query_map([], |row| {
            Ok((row.get(0)?, row.get(1)?, row.get(2)?, row.get(3)?))
        })
        .expect("query schema snapshot")
        .collect::<rusqlite::Result<Vec<_>>>()
        .expect("collect schema snapshot");
    let database_names = connection
        .prepare("PRAGMA database_list")
        .expect("prepare database list")
        .query_map([], |row| row.get(1))
        .expect("query database list")
        .collect::<rusqlite::Result<Vec<String>>>()
        .expect("collect database list");
    let foreign_key_violations = connection
        .prepare("PRAGMA foreign_key_check")
        .expect("prepare foreign key check")
        .query_map([], |_| Ok(()))
        .expect("query foreign key check")
        .count();
    SqliteInvariants {
        schema,
        schema_meta_version: connection
            .query_row(
                "SELECT value FROM schema_meta WHERE key = 'version'",
                [],
                |row| row.get(0),
            )
            .expect("read schema meta version"),
        schema_version: connection
            .query_row("PRAGMA schema_version", [], |row| row.get(0))
            .expect("read schema version"),
        user_version: connection
            .query_row("PRAGMA user_version", [], |row| row.get(0))
            .expect("read user version"),
        journal_mode: connection
            .query_row("PRAGMA journal_mode", [], |row| row.get(0))
            .expect("read journal mode"),
        database_names,
        page_count: connection
            .query_row("PRAGMA page_count", [], |row| row.get(0))
            .expect("read page count"),
        freelist_count: connection
            .query_row("PRAGMA freelist_count", [], |row| row.get(0))
            .expect("read freelist count"),
        integrity_check: connection
            .query_row("PRAGMA integrity_check", [], |row| row.get(0))
            .expect("run integrity check"),
        foreign_key_violations,
    }
}

fn target_timestamps(snapshot: &AuthoritativeSnapshot, target_root: &str) -> Vec<i64> {
    let mut values = snapshot
        .symbols
        .iter()
        .filter(|row| row.root_path == target_root)
        .map(|row| row.indexed_at)
        .chain(
            snapshot
                .imports
                .iter()
                .filter(|row| row.root_path == target_root)
                .map(|row| row.indexed_at),
        )
        .chain(
            snapshot
                .calls
                .iter()
                .filter(|row| row.root_path == target_root)
                .map(|row| row.indexed_at),
        )
        .collect::<Vec<_>>();
    values.sort_unstable();
    values.dedup();
    values
}

#[tokio::test]
async fn bounded_native_a1_persists_multiple_batches_in_one_index() {
    let temp_dir = tempfile::tempdir().expect("temporary A1 fixture");
    let source_root = temp_dir.path().join("source");
    source_fixture(&source_root);

    let store = SqliteStore::open(&temp_dir.path().join("state.db"))
        .await
        .expect("open temporary store");
    let outcome = store
        .codebase_index_bounded_native_a1(
            source_root.to_str().expect("UTF-8 fixture path"),
            &["rust".to_string()],
            CodebaseIndexA1Options {
                batch_rows: 1,
                failpoint: None,
                staging_parent: None,
            },
        )
        .await
        .expect("bounded A1 index");

    assert_eq!(outcome.stats.indexed_files, 1);
    assert!(outcome.stats.symbols >= 2, "{outcome:#?}");
    assert!(outcome.stats.imports >= 1, "{outcome:#?}");
    assert!(outcome.stats.calls >= 2, "{outcome:#?}");
    assert!(outcome.telemetry.emitted_batches > 1, "{outcome:#?}");
    assert_eq!(outcome.telemetry.max_accumulator_rows, 1);
    assert!(outcome.telemetry.staging_transaction_committed);
    assert!(outcome.telemetry.authoritative_transaction_committed);
    assert!(outcome.telemetry.autocommit_before);
    assert!(!outcome.telemetry.autocommit_during);
    assert!(outcome.telemetry.autocommit_after);
}

#[tokio::test]
async fn bounded_native_a1_rolls_back_every_authoritative_phase() {
    let temp_dir = tempfile::tempdir().expect("temporary A1 rollback fixture");
    let source_root = temp_dir.path().join("source");
    let staging_parent = temp_dir.path().join("rollback-staging");
    source_fixture(&source_root);
    std::fs::create_dir_all(&staging_parent).expect("create rollback staging parent");
    let db_path = temp_dir.path().join("state.db");
    let store = SqliteStore::open(&db_path)
        .await
        .expect("open temporary store");
    let target_root = source_root.to_str().expect("UTF-8 fixture path");
    let other_root = "/fixture/other-root";
    seed_authoritative_rows(&db_path, target_root, other_root);
    let before = authoritative_snapshot(&db_path);

    let cases = [
        (
            CodebaseIndexA1Failpoint::AfterStagingBatch(1),
            "after_staging_batch",
        ),
        (
            CodebaseIndexA1Failpoint::AfterDeleteSymbols,
            "after_delete_symbols",
        ),
        (
            CodebaseIndexA1Failpoint::AfterDeleteImports,
            "after_delete_imports",
        ),
        (
            CodebaseIndexA1Failpoint::AfterDeleteCalls,
            "after_delete_calls",
        ),
        (
            CodebaseIndexA1Failpoint::AfterSymbolRows(1),
            "after_symbol_rows",
        ),
        (
            CodebaseIndexA1Failpoint::AfterImportRows(1),
            "after_import_rows",
        ),
        (
            CodebaseIndexA1Failpoint::AfterCallRows(1),
            "after_call_rows",
        ),
        (CodebaseIndexA1Failpoint::BeforeCommit, "before_commit"),
    ];

    for (failpoint, expected_marker) in cases {
        let error = store
            .codebase_index_bounded_native_a1(
                target_root,
                &["rust".to_string()],
                CodebaseIndexA1Options {
                    batch_rows: 1,
                    failpoint: Some(failpoint),
                    staging_parent: Some(staging_parent.clone()),
                },
            )
            .await
            .expect_err("injected A1 failure");
        assert!(
            error.to_string().contains(expected_marker),
            "failpoint {failpoint:?} returned {error}"
        );
        assert_eq!(
            authoritative_snapshot(&db_path),
            before,
            "failpoint {failpoint:?} changed authoritative rows"
        );
        let status = store
            .codebase_index_status(target_root)
            .await
            .expect("connection remains usable after rollback");
        assert_eq!(status.symbols, 1);
        assert_eq!(status.imports, 1);
        assert_eq!(status.calls, 1);
        assert_eq!(
            std::fs::read_dir(&staging_parent)
                .expect("read rollback staging parent")
                .count(),
            0,
            "failpoint {failpoint:?} leaked a staging directory"
        );
    }
}

#[tokio::test]
async fn bounded_native_a1_matches_full_vec_authoritative_contract() {
    let temp_dir = tempfile::tempdir().expect("temporary A1 equivalence fixture");
    let source_root = temp_dir.path().join("source");
    multitype_source_fixture(&source_root);
    let target_root = source_root.to_str().expect("UTF-8 fixture path");
    let other_root = "/fixture/equivalence-sentinel";
    let full_db = temp_dir.path().join("full.db");
    let native_db = temp_dir.path().join("native.db");
    let full_store = SqliteStore::open(&full_db)
        .await
        .expect("open FullVec store");
    let native_store = SqliteStore::open(&native_db)
        .await
        .expect("open staged-native store");
    seed_authoritative_rows(&full_db, target_root, other_root);
    seed_authoritative_rows(&native_db, target_root, other_root);
    let native_before = sqlite_invariants(&native_db);

    let full_stats = full_store
        .codebase_index(target_root, &[])
        .await
        .expect("run FullVec baseline");
    let native = native_store
        .codebase_index_bounded_native_a1(
            target_root,
            &[],
            CodebaseIndexA1Options {
                batch_rows: 2,
                failpoint: None,
                staging_parent: None,
            },
        )
        .await
        .expect("run staged-native candidate");

    assert_eq!(native.stats.indexed_files, full_stats.indexed_files);
    assert_eq!(native.stats.symbols, full_stats.symbols);
    assert_eq!(native.stats.imports, full_stats.imports);
    assert_eq!(native.stats.calls, full_stats.calls);
    assert_eq!(native.stats.root_path, full_stats.root_path);

    let full_snapshot = authoritative_snapshot(&full_db);
    let native_snapshot = authoritative_snapshot(&native_db);
    assert_eq!(target_timestamps(&full_snapshot, target_root).len(), 1);
    assert_eq!(target_timestamps(&native_snapshot, target_root).len(), 1);
    assert_eq!(
        full_snapshot.clone().normalize_target_clock(target_root),
        native_snapshot.clone().normalize_target_clock(target_root)
    );
    assert!(
        native_snapshot
            .symbols
            .iter()
            .filter(|row| row.root_path == target_root)
            .all(|row| row.embedding.is_none()),
        "new target symbols must retain legacy NULL embedding semantics"
    );

    assert_eq!(native.telemetry.strategy, "native_chunk_staged_v0");
    assert_eq!(native.telemetry.batch_rows, 2);
    assert!(native.telemetry.emitted_batches > 1);
    assert!(native.telemetry.max_accumulator_rows <= 2);
    assert_eq!(
        native.telemetry.staging_rows,
        u64::from(native.stats.symbols)
            + u64::from(native.stats.imports)
            + u64::from(native.stats.calls)
    );
    assert_eq!(
        native.telemetry.declared_live_row_bound,
        native
            .telemetry
            .batch_rows
            .saturating_add(native.telemetry.max_extractor_output_rows.saturating_sub(1))
    );
    assert!(native.telemetry.staging_file_bytes > 0);
    assert!(native.telemetry.staging_cleanup_succeeded);

    let full_invariants = sqlite_invariants(&full_db);
    let native_invariants = sqlite_invariants(&native_db);
    assert_eq!(native_invariants.schema, native_before.schema);
    assert_eq!(
        native_invariants.schema_meta_version,
        native_before.schema_meta_version
    );
    assert_eq!(
        native_invariants.schema_version,
        native_before.schema_version
    );
    assert_eq!(native_invariants.user_version, native_before.user_version);
    assert_eq!(native_invariants.journal_mode, "wal");
    assert_eq!(native_invariants.database_names, ["main"]);
    assert_eq!(native_invariants.integrity_check, "ok");
    assert_eq!(native_invariants.foreign_key_violations, 0);
    assert_eq!(native_invariants.page_count, full_invariants.page_count);
    assert_eq!(
        native_invariants.freelist_count,
        full_invariants.freelist_count
    );
}

#[tokio::test]
async fn bounded_native_a1_uses_and_cleans_explicit_staging_parent() {
    let temp_dir = tempfile::tempdir().expect("temporary A1 staging-parent fixture");
    let source_root = temp_dir.path().join("source");
    let staging_parent = temp_dir.path().join("explicit-staging");
    source_fixture(&source_root);
    std::fs::create_dir_all(&staging_parent).expect("create explicit staging parent");
    let store = SqliteStore::open(&temp_dir.path().join("state.db"))
        .await
        .expect("open temporary store");

    let outcome = store
        .codebase_index_bounded_native_a1(
            source_root.to_str().expect("UTF-8 fixture path"),
            &["rust".to_string()],
            CodebaseIndexA1Options {
                batch_rows: 2,
                failpoint: None,
                staging_parent: Some(staging_parent.clone()),
            },
        )
        .await
        .expect("run staged-native with explicit parent");

    assert!(outcome.telemetry.staging_parent_was_explicit);
    assert!(outcome.telemetry.staging_cleanup_succeeded);
    assert_eq!(
        std::fs::read_dir(&staging_parent)
            .expect("read explicit staging parent")
            .count(),
        0,
        "successful staging must not leak a temporary directory"
    );
}

#[tokio::test]
async fn full_vec_a1_timing_seam_matches_default_path() {
    let temp_dir = tempfile::tempdir().expect("temporary FullVec seam fixture");
    let source_root = temp_dir.path().join("source");
    multitype_source_fixture(&source_root);
    let target_root = source_root.to_str().expect("UTF-8 fixture path");
    let other_root = "/fixture/full-vec-seam-sentinel";
    let default_db = temp_dir.path().join("default.db");
    let measured_db = temp_dir.path().join("measured.db");
    let default_store = SqliteStore::open(&default_db)
        .await
        .expect("open default FullVec store");
    let measured_store = SqliteStore::open(&measured_db)
        .await
        .expect("open measured FullVec store");
    seed_authoritative_rows(&default_db, target_root, other_root);
    seed_authoritative_rows(&measured_db, target_root, other_root);

    let default_stats = default_store
        .codebase_index(target_root, &[])
        .await
        .expect("run default FullVec path");
    let measured = measured_store
        .codebase_index_full_vec_a1(target_root, &[])
        .await
        .expect("run measured FullVec seam");

    assert_eq!(measured.stats.indexed_files, default_stats.indexed_files);
    assert_eq!(measured.stats.symbols, default_stats.symbols);
    assert_eq!(measured.stats.imports, default_stats.imports);
    assert_eq!(measured.stats.calls, default_stats.calls);
    assert_eq!(measured.stats.root_path, default_stats.root_path);
    assert_eq!(
        authoritative_snapshot(&default_db).normalize_target_clock(target_root),
        authoritative_snapshot(&measured_db).normalize_target_clock(target_root)
    );
    assert!(measured.telemetry.extraction_and_accumulation_ns > 0);
    assert!(measured.telemetry.authoritative_transaction_ns > 0);
    assert!(measured.telemetry.autocommit_before);
    assert!(!measured.telemetry.autocommit_during);
    assert!(measured.telemetry.autocommit_after);
}
