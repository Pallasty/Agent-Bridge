#![cfg(feature = "codebase-index-bounded-native-a1")]

use ab_store::{
    CodebaseIndexA1DispatchOutcome, CodebaseIndexA1DispatchStrategy, CodebaseIndexA1Failpoint,
    CodebaseIndexA1Options, SqliteStore, StateStore,
};
use std::path::Path;
use std::sync::Mutex;
use tokio_rusqlite::rusqlite::{self, params, Connection};

static CODEBASE_INDEX_A1_STRATEGY_ENV_LOCK: Mutex<()> = Mutex::new(());

#[tokio::test]
async fn codebase_index_env_dispatch_reports_selection_and_fallback_reason() {
    let temp_dir = tempfile::tempdir().expect("temporary dispatch receipt fixture");
    let db_path = temp_dir.path().join("index.sqlite3");
    let store = SqliteStore::open(&db_path)
        .await
        .expect("open sqlite store");
    let target_root = temp_dir.path().join("src");
    std::fs::create_dir_all(&target_root).expect("create target root");
    std::fs::write(target_root.join("lib.rs"), "fn receipt_probe() {}\n")
        .expect("write source fixture");

    let receipt = with_a1_a2_index_options_env(
        (Some("native_chunk_staged_v0"), Some("2"), None),
        (Some("mystery"), None, None),
        || async {
            store
                .codebase_index_with_env_dispatch(target_root.to_str().unwrap(), &[])
                .await
                .expect("fallback dispatch should succeed")
                .dispatch
        },
    )
    .await;

    assert_eq!(receipt.selected_namespace, "a1");
    assert_eq!(receipt.requested_strategy.as_deref(), Some("mystery"));
    assert_eq!(receipt.effective_strategy, "native_chunk_staged_v0");
    assert_eq!(
        receipt.fallback_reason.as_deref(),
        Some("a2_strategy_unknown")
    );
    assert_eq!(receipt.batch_rows, Some(2));
    assert!(!receipt.staging_parent_configured);
}

async fn with_a1_index_strategy_env<R, Fut, F>(value: Option<&str>, f: F) -> R
where
    F: FnOnce() -> Fut,
    Fut: std::future::Future<Output = R>,
{
    let _guard = CODEBASE_INDEX_A1_STRATEGY_ENV_LOCK.lock().unwrap();
    let key = "AB_CODEBASE_INDEX_A1_STRATEGY";
    let value_bytes = std::env::var_os(key);
    if let Some(value) = value {
        std::env::set_var(key, value);
    } else {
        std::env::remove_var(key);
    }
    let result = f().await;
    match value_bytes {
        Some(previous) => std::env::set_var(key, previous),
        None => std::env::remove_var(key),
    }
    result
}

async fn with_a1_index_options_env<R, Fut, F>(
    strategy: Option<&str>,
    batch_rows: Option<&str>,
    staging_parent: Option<&std::path::Path>,
    f: F,
) -> R
where
    F: FnOnce() -> Fut,
    Fut: std::future::Future<Output = R>,
{
    let _guard = CODEBASE_INDEX_A1_STRATEGY_ENV_LOCK.lock().unwrap();
    let key_strategy = "AB_CODEBASE_INDEX_A1_STRATEGY";
    let key_batch = "AB_CODEBASE_INDEX_A1_BATCH_ROWS";
    let key_staging_parent = "AB_CODEBASE_INDEX_A1_STAGING_PARENT";
    let old_strategy = std::env::var_os(key_strategy);
    let old_batch = std::env::var_os(key_batch);
    let old_parent = std::env::var_os(key_staging_parent);

    if let Some(strategy) = strategy {
        std::env::set_var(key_strategy, strategy);
    } else {
        std::env::remove_var(key_strategy);
    }
    if let Some(batch_rows) = batch_rows {
        std::env::set_var(key_batch, batch_rows);
    } else {
        std::env::remove_var(key_batch);
    }
    if let Some(staging_parent) = staging_parent {
        std::env::set_var(key_staging_parent, staging_parent);
    } else {
        std::env::remove_var(key_staging_parent);
    }

    let result = f().await;

    match old_strategy {
        Some(previous) => std::env::set_var(key_strategy, previous),
        None => std::env::remove_var(key_strategy),
    }
    match old_batch {
        Some(previous) => std::env::set_var(key_batch, previous),
        None => std::env::remove_var(key_batch),
    }
    match old_parent {
        Some(previous) => std::env::set_var(key_staging_parent, previous),
        None => std::env::remove_var(key_staging_parent),
    }
    result
}

async fn with_a2_index_options_env<R, Fut, F>(
    strategy: Option<&str>,
    batch_rows: Option<&str>,
    staging_parent: Option<&std::path::Path>,
    f: F,
) -> R
where
    F: FnOnce() -> Fut,
    Fut: std::future::Future<Output = R>,
{
    let _guard = CODEBASE_INDEX_A1_STRATEGY_ENV_LOCK.lock().unwrap();
    let key_strategy = "AB_CODEBASE_INDEX_A2_STRATEGY";
    let key_batch = "AB_CODEBASE_INDEX_A2_BATCH_ROWS";
    let key_staging_parent = "AB_CODEBASE_INDEX_A2_STAGING_PARENT";
    let old_strategy = std::env::var_os(key_strategy);
    let old_batch = std::env::var_os(key_batch);
    let old_parent = std::env::var_os(key_staging_parent);

    if let Some(strategy) = strategy {
        std::env::set_var(key_strategy, strategy);
    } else {
        std::env::remove_var(key_strategy);
    }
    if let Some(batch_rows) = batch_rows {
        std::env::set_var(key_batch, batch_rows);
    } else {
        std::env::remove_var(key_batch);
    }
    if let Some(staging_parent) = staging_parent {
        std::env::set_var(key_staging_parent, staging_parent);
    } else {
        std::env::remove_var(key_staging_parent);
    }

    let result = f().await;

    match old_strategy {
        Some(previous) => std::env::set_var(key_strategy, previous),
        None => std::env::remove_var(key_strategy),
    }
    match old_batch {
        Some(previous) => std::env::set_var(key_batch, previous),
        None => std::env::remove_var(key_batch),
    }
    match old_parent {
        Some(previous) => std::env::set_var(key_staging_parent, previous),
        None => std::env::remove_var(key_staging_parent),
    }
    result
}

async fn with_a1_a2_index_options_env<R, Fut, F>(
    a1: (Option<&str>, Option<&str>, Option<&std::path::Path>),
    a2: (Option<&str>, Option<&str>, Option<&std::path::Path>),
    f: F,
) -> R
where
    F: FnOnce() -> Fut,
    Fut: std::future::Future<Output = R>,
{
    let _guard = CODEBASE_INDEX_A1_STRATEGY_ENV_LOCK.lock().unwrap();

    let key_a1_strategy = "AB_CODEBASE_INDEX_A1_STRATEGY";
    let key_a1_batch = "AB_CODEBASE_INDEX_A1_BATCH_ROWS";
    let key_a1_parent = "AB_CODEBASE_INDEX_A1_STAGING_PARENT";
    let key_a2_strategy = "AB_CODEBASE_INDEX_A2_STRATEGY";
    let key_a2_batch = "AB_CODEBASE_INDEX_A2_BATCH_ROWS";
    let key_a2_parent = "AB_CODEBASE_INDEX_A2_STAGING_PARENT";

    let old_a1_strategy = std::env::var_os(key_a1_strategy);
    let old_a1_batch = std::env::var_os(key_a1_batch);
    let old_a1_parent = std::env::var_os(key_a1_parent);
    let old_a2_strategy = std::env::var_os(key_a2_strategy);
    let old_a2_batch = std::env::var_os(key_a2_batch);
    let old_a2_parent = std::env::var_os(key_a2_parent);

    if let Some(value) = a1.0 {
        std::env::set_var(key_a1_strategy, value);
    } else {
        std::env::remove_var(key_a1_strategy);
    }
    if let Some(value) = a1.1 {
        std::env::set_var(key_a1_batch, value);
    } else {
        std::env::remove_var(key_a1_batch);
    }
    if let Some(value) = a1.2 {
        std::env::set_var(key_a1_parent, value);
    } else {
        std::env::remove_var(key_a1_parent);
    }

    if let Some(value) = a2.0 {
        std::env::set_var(key_a2_strategy, value);
    } else {
        std::env::remove_var(key_a2_strategy);
    }
    if let Some(value) = a2.1 {
        std::env::set_var(key_a2_batch, value);
    } else {
        std::env::remove_var(key_a2_batch);
    }
    if let Some(value) = a2.2 {
        std::env::set_var(key_a2_parent, value);
    } else {
        std::env::remove_var(key_a2_parent);
    }

    let result = f().await;

    match old_a1_strategy {
        Some(previous) => std::env::set_var(key_a1_strategy, previous),
        None => std::env::remove_var(key_a1_strategy),
    }
    match old_a1_batch {
        Some(previous) => std::env::set_var(key_a1_batch, previous),
        None => std::env::remove_var(key_a1_batch),
    }
    match old_a1_parent {
        Some(previous) => std::env::set_var(key_a1_parent, previous),
        None => std::env::remove_var(key_a1_parent),
    }

    match old_a2_strategy {
        Some(previous) => std::env::set_var(key_a2_strategy, previous),
        None => std::env::remove_var(key_a2_strategy),
    }
    match old_a2_batch {
        Some(previous) => std::env::set_var(key_a2_batch, previous),
        None => std::env::remove_var(key_a2_batch),
    }
    match old_a2_parent {
        Some(previous) => std::env::set_var(key_a2_parent, previous),
        None => std::env::remove_var(key_a2_parent),
    }

    result
}

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

    let db_path = temp_dir.path().join("state.db");
    let store = SqliteStore::open(&db_path)
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
    assert!(outcome.telemetry.staging_file_path.starts_with(
        staging_parent
            .canonicalize()
            .expect("canonical staging parent")
    ));
    assert!(
        !outcome.telemetry.staging_file_path.exists(),
        "telemetry must name the actual staging file removed after commit"
    );
    #[cfg(unix)]
    assert!(outcome.telemetry.staging_file_device > 0);
    #[cfg(target_os = "linux")]
    {
        assert!(outcome.telemetry.staging_file_mount_point.is_absolute());
        assert!(!outcome.telemetry.staging_file_filesystem_type.is_empty());
    }
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

#[tokio::test]
async fn codebase_index_with_a1_strategy_explicitly_dispatches_full_vec() {
    let temp_dir = tempfile::tempdir().expect("temporary A1 dispatch fixture");
    let source_root = temp_dir.path().join("source");
    source_fixture(&source_root);
    let target_root = source_root.to_str().expect("UTF-8 fixture path");
    let other_root = "/fixture/full-vec-dispatch-sentinel";
    let default_db = temp_dir.path().join("default.db");
    let dispatch_db = temp_dir.path().join("dispatch.db");
    let default_store = SqliteStore::open(&default_db)
        .await
        .expect("open default dispatch store");
    let dispatch_store = SqliteStore::open(&dispatch_db)
        .await
        .expect("open strategy dispatch store");
    seed_authoritative_rows(&default_db, target_root, other_root);
    seed_authoritative_rows(&dispatch_db, target_root, other_root);

    let default_stats = default_store
        .codebase_index(target_root, &[])
        .await
        .expect("run default FullVec path");
    let dispatch_stats = dispatch_store
        .codebase_index_with_a1_strategy(target_root, &[], CodebaseIndexA1DispatchStrategy::FullVec)
        .await
        .expect("run explicit FullVec dispatch");

    match dispatch_stats {
        CodebaseIndexA1DispatchOutcome::FullVec(outcome) => {
            assert_eq!(outcome.stats.indexed_files, default_stats.indexed_files);
            assert_eq!(outcome.stats.symbols, default_stats.symbols);
            assert_eq!(outcome.stats.imports, default_stats.imports);
            assert_eq!(outcome.stats.calls, default_stats.calls);
            assert_eq!(outcome.stats.root_path, default_stats.root_path);
        }
        _ => panic!("explicit FullVec strategy must return FullVec dispatch outcome"),
    }

    assert_eq!(
        authoritative_snapshot(&default_db).normalize_target_clock(target_root),
        authoritative_snapshot(&dispatch_db).normalize_target_clock(target_root)
    );
}

#[tokio::test]
async fn codebase_index_default_env_is_full_vec_and_matches_explicit_full_vec() {
    let temp_dir = tempfile::tempdir().expect("temporary env default fixture");
    let source_root = temp_dir.path().join("source");
    source_fixture(&source_root);
    let target_root = source_root.to_str().expect("UTF-8 fixture path");
    let other_root = "/fixture/default-env-full-vec-sentinel";
    let default_db = temp_dir.path().join("default.db");
    let env_db = temp_dir.path().join("env.db");
    let default_store = SqliteStore::open(&default_db)
        .await
        .expect("open default env fixture store");
    let env_store = SqliteStore::open(&env_db)
        .await
        .expect("open environment-gated fixture store");
    seed_authoritative_rows(&default_db, target_root, other_root);
    seed_authoritative_rows(&env_db, target_root, other_root);

    let default_stats = default_store
        .codebase_index(target_root, &[])
        .await
        .expect("run default FullVec baseline");

    let env_stats = with_a1_index_strategy_env::<_, _, _>(None, || async {
        env_store
            .codebase_index(target_root, &[])
            .await
            .expect("run codebase_index with default-off env gate")
    })
    .await;

    assert_eq!(env_stats.indexed_files, default_stats.indexed_files);
    assert_eq!(env_stats.symbols, default_stats.symbols);
    assert_eq!(env_stats.imports, default_stats.imports);
    assert_eq!(env_stats.calls, default_stats.calls);
    assert_eq!(env_stats.root_path, default_stats.root_path);
    assert_eq!(
        authoritative_snapshot(&default_db).normalize_target_clock(target_root),
        authoritative_snapshot(&env_db).normalize_target_clock(target_root)
    );
}

#[tokio::test]
async fn codebase_index_with_a1_env_switches_to_native_chunk_staged_v0() {
    let temp_dir = tempfile::tempdir().expect("temporary env switched fixture");
    let source_root = temp_dir.path().join("source");
    source_fixture(&source_root);
    let target_root = source_root.to_str().expect("UTF-8 fixture path");
    let other_root = "/fixture/env-native-chunk-staged-root";
    let staging_parent = temp_dir.path().join("env-staging");
    std::fs::create_dir_all(&staging_parent).expect("create env staging parent");
    let env_db = temp_dir.path().join("env.db");
    let store = SqliteStore::open(&env_db)
        .await
        .expect("open env switched store");
    seed_authoritative_rows(&env_db, target_root, other_root);

    let _ = with_a1_index_options_env(
        Some("native_chunk_staged_v0"),
        Some("4"),
        Some(&staging_parent),
        || async {
            store
                .codebase_index(target_root, &["rust".to_string()])
                .await
                .expect("run env-switched codebase_index")
        },
    )
    .await;

    assert!(
        std::fs::read_dir(&staging_parent)
            .expect("read env staging parent")
            .count()
            == 0,
        "env switched staged-native path must cleanup temporary staging"
    );
}

#[tokio::test]
async fn codebase_index_with_a1_env_invalid_staging_parent_returns_error() {
    let temp_dir = tempfile::tempdir().expect("temporary env invalid staging parent fixture");
    let source_root = temp_dir.path().join("source");
    source_fixture(&source_root);
    let target_root = source_root.to_str().expect("UTF-8 fixture path");
    let other_root = "/fixture/env-invalid-staging-parent-fallback";
    let staging_parent = temp_dir.path().join("invalid-staging-parent");
    std::fs::write(&staging_parent, b"not-a-directory")
        .expect("write invalid staging-parent sentinel");

    let env_db = temp_dir.path().join("env.db");
    let store = SqliteStore::open(&env_db)
        .await
        .expect("open env invalid parent store");
    seed_authoritative_rows(&env_db, target_root, other_root);
    let before = authoritative_snapshot(&env_db);

    let err = with_a1_index_options_env(
        Some("native_chunk_staged_v0"),
        Some("4"),
        Some(&staging_parent),
        || async {
            store
                .codebase_index(target_root, &["rust".to_string()])
                .await
                .expect_err("invalid staging parent should error")
        },
    )
    .await;

    assert!(
        err.to_string().contains("codebase_index A1 staging dir"),
        "invalid staging parent error should mention staging dir creation: {err}"
    );
    assert_eq!(
        authoritative_snapshot(&env_db).normalize_target_clock(target_root),
        before.normalize_target_clock(target_root)
    );
}

#[tokio::test]
async fn codebase_index_with_a2_env_switches_to_native_chunk_staged_v0() {
    let temp_dir = tempfile::tempdir().expect("temporary a2 env switched fixture");
    let source_root = temp_dir.path().join("source");
    source_fixture(&source_root);
    let target_root = source_root.to_str().expect("UTF-8 fixture path");
    let other_root = "/fixture/env-native-chunk-staged-root-a2";
    let staging_parent = temp_dir.path().join("env-a2-staging");
    std::fs::create_dir_all(&staging_parent).expect("create a2 env staging parent");

    let env_db = temp_dir.path().join("env-a2.db");
    let store = SqliteStore::open(&env_db)
        .await
        .expect("open a2 env switched store");
    seed_authoritative_rows(&env_db, target_root, other_root);

    let _ = with_a2_index_options_env(
        Some("native_chunk_staged_v0"),
        Some("4"),
        Some(&staging_parent),
        || async {
            store
                .codebase_index(target_root, &["rust".to_string()])
                .await
                .expect("run a2 env-switched codebase_index")
        },
    )
    .await;

    assert!(
        std::fs::read_dir(&staging_parent)
            .expect("read a2 env staging parent")
            .count()
            == 0,
        "a2 env switched staged-native path must cleanup temporary staging"
    );
}

#[tokio::test]
async fn codebase_index_with_a2_env_preempts_a1_native_env() {
    let temp_dir = tempfile::tempdir().expect("temporary a2 precedence fixture");
    let source_root = temp_dir.path().join("source");
    source_fixture(&source_root);
    let target_root = source_root.to_str().expect("UTF-8 fixture path");
    let other_root = "/fixture/env-preempt-a1-root";
    let a1_staging_parent = temp_dir.path().join("a1-invalid-staging");
    std::fs::write(&a1_staging_parent, b"invalid-a1-parent")
        .expect("write invalid a1 staging parent sentinel");
    let a2_staging_parent = temp_dir.path().join("a2-staging");
    std::fs::create_dir_all(&a2_staging_parent).expect("create a2 precedence staging parent");

    let env_db = temp_dir.path().join("env-a2-preempt.db");
    let store = SqliteStore::open(&env_db)
        .await
        .expect("open a2 precedence store");
    seed_authoritative_rows(&env_db, target_root, other_root);

    let _ = with_a1_a2_index_options_env(
        (
            Some("native_chunk_staged_v0"),
            Some("4"),
            Some(&a1_staging_parent),
        ),
        (
            Some("native_chunk_staged_v0"),
            Some("4"),
            Some(&a2_staging_parent),
        ),
        || async {
            store
                .codebase_index(target_root, &["rust".to_string()])
                .await
                .expect("run a2-preempting codebase_index")
        },
    )
    .await;

    assert!(
        std::fs::metadata(&a1_staging_parent)
            .expect("a1 invalid parent should remain a file")
            .is_file(),
        "a1 invalid parent should not be touched when a2 wins"
    );
    assert!(
        std::fs::read_dir(&a2_staging_parent)
            .expect("read a2 staging parent")
            .count()
            == 0,
        "a2 env switched staged-native path must cleanup temporary staging"
    );
}

#[tokio::test]
async fn codebase_index_with_a2_unknown_strategy_falls_back_to_a1_strategy() {
    let temp_dir = tempfile::tempdir().expect("temporary a2 fallback fixture");
    let source_root = temp_dir.path().join("source");
    source_fixture(&source_root);
    let target_root = source_root.to_str().expect("UTF-8 fixture path");
    let other_root = "/fixture/fallback-a2-unknown-a1-root";
    let a2_staging_parent = temp_dir.path().join("a2-invalid-staging");
    std::fs::write(&a2_staging_parent, b"invalid-a2-parent")
        .expect("write invalid a2 staging parent sentinel");
    let a1_staging_parent = temp_dir.path().join("a1-staging");
    std::fs::create_dir_all(&a1_staging_parent).expect("create fallback a1 staging parent");

    let env_db = temp_dir.path().join("env-a2-unknown.db");
    let store = SqliteStore::open(&env_db)
        .await
        .expect("open a2-unknown fallback store");
    seed_authoritative_rows(&env_db, target_root, other_root);

    let _ = with_a1_a2_index_options_env(
        (
            Some("native_chunk_staged_v0"),
            Some("4"),
            Some(&a1_staging_parent),
        ),
        (Some("not-a2-strategy"), Some("4"), Some(&a2_staging_parent)),
        || async {
            store
                .codebase_index(target_root, &["rust".to_string()])
                .await
                .expect("run a2-unknown fallback to a1 codebase_index")
        },
    )
    .await;

    assert!(
        std::fs::metadata(&a1_staging_parent)
            .expect("a1 fallback staging parent should remain a directory")
            .is_dir(),
        "a1 fallback path should be used when a2 strategy is unknown"
    );
    assert!(
        std::fs::read_dir(&a1_staging_parent)
            .expect("read a1 fallback staging parent")
            .count()
            == 0,
        "a1 fallback staged-native path must cleanup temporary staging"
    );
    assert!(
        std::fs::metadata(&a2_staging_parent)
            .expect("a2 invalid parent should remain file")
            .is_file(),
        "invalid a2 fallback parent should stay untouched"
    );
}

#[tokio::test]
async fn codebase_index_with_a2_unknown_strategy_falls_back_to_a1_staged_native_equivalence() {
    let temp_dir = tempfile::tempdir().expect("temporary a2 fallback equivalence fixture");
    let source_root = temp_dir.path().join("source");
    source_fixture(&source_root);
    let target_root = source_root.to_str().expect("UTF-8 fixture path");
    let other_root = "/fixture/fallback-a2-unknown-a1-exact";
    let a2_staging_parent = temp_dir.path().join("a2-invalid-staging");
    std::fs::write(&a2_staging_parent, b"invalid-a2-parent")
        .expect("write invalid a2 fallback parent sentinel");
    let a1_staging_parent = temp_dir.path().join("a1-staging");
    std::fs::create_dir_all(&a1_staging_parent)
        .expect("create fallback a1 equivalence staging parent");

    let a1_db = temp_dir.path().join("a1-exact.db");
    let fallback_db = temp_dir.path().join("a2-unknown-exact.db");
    let a1_store = SqliteStore::open(&a1_db)
        .await
        .expect("open a1 exact reference store");
    let fallback_store = SqliteStore::open(&fallback_db)
        .await
        .expect("open a2-unknown fallback store");
    seed_authoritative_rows(&a1_db, target_root, other_root);
    seed_authoritative_rows(&fallback_db, target_root, other_root);

    let a1_outcome = a1_store
        .codebase_index_with_a1_strategy(
            target_root,
            &["rust".to_string()],
            CodebaseIndexA1DispatchStrategy::NativeChunkStagedV0(CodebaseIndexA1Options {
                batch_rows: 4,
                failpoint: None,
                staging_parent: Some(a1_staging_parent.clone()),
            }),
        )
        .await
        .expect("run explicit A1 staged-native reference");
    let a1_stats = match a1_outcome {
        CodebaseIndexA1DispatchOutcome::NativeChunkStagedV0(outcome) => outcome.stats,
        _ => panic!("explicit staged-native A1 strategy must return native outcome"),
    };
    let a1_snapshot = authoritative_snapshot(&a1_db).normalize_target_clock(target_root);

    let fallback_stats = with_a1_a2_index_options_env(
        (
            Some("native_chunk_staged_v0"),
            Some("4"),
            Some(&a1_staging_parent),
        ),
        (Some("not-a2-strategy"), Some("4"), Some(&a2_staging_parent)),
        || async {
            fallback_store
                .codebase_index(target_root, &["rust".to_string()])
                .await
                .expect("run codebase_index with unknown A2 strategy")
        },
    )
    .await;

    assert_eq!(fallback_stats.indexed_files, a1_stats.indexed_files);
    assert_eq!(fallback_stats.symbols, a1_stats.symbols);
    assert_eq!(fallback_stats.imports, a1_stats.imports);
    assert_eq!(fallback_stats.calls, a1_stats.calls);
    assert_eq!(fallback_stats.root_path, a1_stats.root_path);
    assert_eq!(
        authoritative_snapshot(&fallback_db).normalize_target_clock(target_root),
        a1_snapshot,
        "A2 unknown-strategy fallback should produce the same authoritative snapshot as explicit A1 staged-native"
    );
    assert!(
        std::fs::read_dir(&a1_staging_parent)
            .expect("read a1 fallback equivalence staging parent")
            .count()
            == 0,
        "a1 fallback staged-native path should cleanup temporary staging"
    );
    assert!(
        std::fs::metadata(&a2_staging_parent)
            .expect("a2 invalid fallback parent should remain file")
            .is_file(),
        "invalid a2 parent should stay untouched"
    );
}

#[tokio::test]
async fn codebase_index_with_a2_unknown_strategy_and_a1_staging_failure_reverts_without_partial_effect(
) {
    let temp_dir =
        tempfile::tempdir().expect("temporary a2 fallback invalid-a1 staging failure fixture");
    let source_root = temp_dir.path().join("source");
    source_fixture(&source_root);
    let target_root = source_root.to_str().expect("UTF-8 fixture path");
    let other_root = "/fixture/fallback-a2-unknown-a1-fail";

    let a1_staging_parent = temp_dir.path().join("a1-invalid-staging");
    std::fs::write(&a1_staging_parent, b"invalid-a1-staging-parent")
        .expect("write invalid a1 staging parent sentinel");
    let a2_staging_parent = temp_dir.path().join("a2-invalid-staging");
    std::fs::write(&a2_staging_parent, b"invalid-a2-staging-parent")
        .expect("write invalid a2 staging parent sentinel");

    let fallback_db = temp_dir.path().join("a2-unknown-failure.db");
    let store = SqliteStore::open(&fallback_db)
        .await
        .expect("open a2 unknown with a1 failure store");
    seed_authoritative_rows(&fallback_db, target_root, other_root);
    let before = authoritative_snapshot(&fallback_db);
    let before_status = store
        .codebase_index_status(target_root)
        .await
        .expect("status before fallback failure");

    let err = with_a1_a2_index_options_env(
        (
            Some("native_chunk_staged_v0"),
            Some("4"),
            Some(&a1_staging_parent),
        ),
        (Some("not-a2-strategy"), Some("4"), Some(&a2_staging_parent)),
        || async {
            store
                .codebase_index(target_root, &["rust".to_string()])
                .await
                .expect_err("unknown A2 strategy should still hit A1 staging failure")
        },
    )
    .await;

    assert!(
        err.to_string().contains("codebase_index A1 staging dir"),
        "invalid A1 fallback staging parent should surface a clear staging-dir error, got {err}"
    );
    assert_eq!(
        authoritative_snapshot(&fallback_db).normalize_target_clock(target_root),
        before.normalize_target_clock(target_root),
        "A2-unknown + A1 staging failure should rollback authoritative state"
    );

    let after_status = store
        .codebase_index_status(target_root)
        .await
        .expect("status after failure should remain readable");
    assert_eq!(after_status.symbols, before_status.symbols);
    assert_eq!(after_status.imports, before_status.imports);
    assert_eq!(after_status.calls, before_status.calls);

    assert!(
        std::fs::metadata(&a1_staging_parent)
            .expect("a1 invalid parent should remain file")
            .is_file(),
        "invalid A1 fallback parent should remain untouched by attempted staging open failure"
    );
    assert!(
        std::fs::metadata(&a2_staging_parent)
            .expect("a2 invalid parent should remain file")
            .is_file(),
        "invalid A2 sentinel should remain untouched when A2 is unknown"
    );
}

#[tokio::test]
async fn codebase_index_with_a2_unknown_strategy_recovers_after_a1_staging_parent_is_fixed() {
    let temp_dir = tempfile::tempdir().expect("temporary a2 fallback staging recovery fixture");
    let source_root = temp_dir.path().join("source");
    source_fixture(&source_root);
    let target_root = source_root.to_str().expect("UTF-8 fixture path");
    let other_root = "/fixture/fallback-a2-unknown-a1-recovery";

    let invalid_a1_staging_parent = temp_dir.path().join("a1-invalid-staging");
    std::fs::write(&invalid_a1_staging_parent, b"invalid-a1-staging-parent")
        .expect("write invalid a1 staging parent sentinel");
    let valid_a1_staging_parent = temp_dir.path().join("a1-valid-staging");
    std::fs::create_dir_all(&valid_a1_staging_parent).expect("create valid a1 staging parent");
    let a2_staging_parent = temp_dir.path().join("a2-invalid-staging");
    std::fs::write(&a2_staging_parent, b"invalid-a2-staging-parent")
        .expect("write invalid a2 staging parent sentinel");

    let fallback_db = temp_dir.path().join("a2-unknown-recovery.db");
    let fallback_store = SqliteStore::open(&fallback_db)
        .await
        .expect("open a2 unknown recovery fallback store");
    seed_authoritative_rows(&fallback_db, target_root, other_root);
    let before_retry = authoritative_snapshot(&fallback_db).normalize_target_clock(target_root);

    let baseline_db = temp_dir.path().join("a2-unknown-recovery-baseline.db");
    let baseline_store = SqliteStore::open(&baseline_db)
        .await
        .expect("open a2 unknown recovery baseline store");
    seed_authoritative_rows(&baseline_db, target_root, other_root);

    let first = with_a1_a2_index_options_env(
        (
            Some("native_chunk_staged_v0"),
            Some("4"),
            Some(&invalid_a1_staging_parent),
        ),
        (Some("not-a2-strategy"), Some("4"), Some(&a2_staging_parent)),
        || async {
            fallback_store
                .codebase_index(target_root, &["rust".to_string()])
                .await
                .expect_err("invalid A1 staging parent should fail before retrying")
        },
    )
    .await;
    assert!(
        first.to_string().contains("codebase_index A1 staging dir"),
        "invalid A1 staging parent should surface staging-dir error on first attempt, got {first}"
    );
    assert_eq!(
        authoritative_snapshot(&fallback_db).normalize_target_clock(target_root),
        before_retry,
        "failed fallback should not mutate authoritative rows"
    );

    let baseline_explicit = baseline_store
        .codebase_index_with_a1_strategy(
            target_root,
            &["rust".to_string()],
            CodebaseIndexA1DispatchStrategy::NativeChunkStagedV0(CodebaseIndexA1Options {
                batch_rows: 4,
                failpoint: None,
                staging_parent: Some(valid_a1_staging_parent.clone()),
            }),
        )
        .await
        .expect("run baseline explicit A1 staged-native");
    let baseline_stats = match baseline_explicit {
        CodebaseIndexA1DispatchOutcome::NativeChunkStagedV0(outcome) => outcome.stats,
        _ => panic!("explicit staged-native A1 strategy should return native outcome"),
    };
    let baseline_snapshot =
        authoritative_snapshot(&baseline_db).normalize_target_clock(target_root);

    let retry = with_a1_a2_index_options_env(
        (
            Some("native_chunk_staged_v0"),
            Some("4"),
            Some(&valid_a1_staging_parent),
        ),
        (Some("not-a2-strategy"), Some("4"), Some(&a2_staging_parent)),
        || async {
            fallback_store
                .codebase_index(target_root, &["rust".to_string()])
                .await
                .expect("A2 unknown should recover once A1 staging parent is valid")
        },
    )
    .await;

    assert_eq!(retry.indexed_files, baseline_stats.indexed_files);
    assert_eq!(retry.symbols, baseline_stats.symbols);
    assert_eq!(retry.imports, baseline_stats.imports);
    assert_eq!(retry.calls, baseline_stats.calls);
    assert_eq!(retry.root_path, baseline_stats.root_path);
    assert_eq!(
        authoritative_snapshot(&fallback_db).normalize_target_clock(target_root),
        baseline_snapshot,
        "recovered A2-unknown fallback should match explicit A1 baseline"
    );
    assert!(
        std::fs::read_dir(&valid_a1_staging_parent)
            .expect("read valid a1 staging parent")
            .count()
            == 0,
        "successful retry should cleanup staging artifacts"
    );
    assert!(
        std::fs::metadata(&invalid_a1_staging_parent)
            .expect("invalid a1 parent should remain file")
            .is_file(),
        "invalid a1 parent from failed attempt should remain untouched"
    );
    assert!(
        std::fs::metadata(&a2_staging_parent)
            .expect("a2 parent should remain file")
            .is_file(),
        "invalid a2 parent should remain untouched"
    );
}

#[tokio::test]
async fn codebase_index_with_a1_env_unknown_strategy_defaults_to_full_vec() {
    let temp_dir = tempfile::tempdir().expect("temporary env fallback fixture");
    let source_root = temp_dir.path().join("source");
    source_fixture(&source_root);
    let target_root = source_root.to_str().expect("UTF-8 fixture path");
    let other_root = "/fixture/env-unknown-strategy-fallback";
    let default_db = temp_dir.path().join("default.db");
    let env_db = temp_dir.path().join("env.db");
    let default_store = SqliteStore::open(&default_db)
        .await
        .expect("open env fallback baseline store");
    let env_store = SqliteStore::open(&env_db)
        .await
        .expect("open env fallback gated store");
    seed_authoritative_rows(&default_db, target_root, other_root);
    seed_authoritative_rows(&env_db, target_root, other_root);

    let default_stats = default_store
        .codebase_index(target_root, &[])
        .await
        .expect("run baseline FullVec fallback path");

    let env_stats = with_a1_index_strategy_env(Some("definitely_not_a1_strategy"), || async {
        env_store
            .codebase_index(target_root, &[])
            .await
            .expect("run codebase_index with unknown strategy env")
    })
    .await;

    assert_eq!(env_stats.indexed_files, default_stats.indexed_files);
    assert_eq!(env_stats.symbols, default_stats.symbols);
    assert_eq!(env_stats.imports, default_stats.imports);
    assert_eq!(env_stats.calls, default_stats.calls);
    assert_eq!(env_stats.root_path, default_stats.root_path);
    assert_eq!(
        authoritative_snapshot(&default_db).normalize_target_clock(target_root),
        authoritative_snapshot(&env_db).normalize_target_clock(target_root)
    );
}

#[tokio::test]
async fn codebase_index_with_a1_env_fullvec_alias_switches_to_full_vec() {
    let temp_dir = tempfile::tempdir().expect("temporary env fullvec alias fixture");
    let source_root = temp_dir.path().join("source");
    source_fixture(&source_root);
    let target_root = source_root.to_str().expect("UTF-8 fixture path");
    let other_root = "/fixture/env-fullvec-alias-fallback";
    let default_db = temp_dir.path().join("default.db");
    let env_db = temp_dir.path().join("env.db");
    let default_store = SqliteStore::open(&default_db)
        .await
        .expect("open env alias baseline store");
    let env_store = SqliteStore::open(&env_db)
        .await
        .expect("open env alias switched store");
    seed_authoritative_rows(&default_db, target_root, other_root);
    seed_authoritative_rows(&env_db, target_root, other_root);

    let default_stats = default_store
        .codebase_index(target_root, &[])
        .await
        .expect("run baseline FullVec path");

    let env_stats = with_a1_index_options_env(Some("FULLVEC_A1"), None, None, || async {
        env_store
            .codebase_index(target_root, &[])
            .await
            .expect("run codebase_index with FULLVEC_A1 strategy")
    })
    .await;

    assert_eq!(env_stats.indexed_files, default_stats.indexed_files);
    assert_eq!(env_stats.symbols, default_stats.symbols);
    assert_eq!(env_stats.imports, default_stats.imports);
    assert_eq!(env_stats.calls, default_stats.calls);
    assert_eq!(env_stats.root_path, default_stats.root_path);
    assert_eq!(
        authoritative_snapshot(&default_db).normalize_target_clock(target_root),
        authoritative_snapshot(&env_db).normalize_target_clock(target_root)
    );
}

#[tokio::test]
async fn codebase_index_with_a1_env_dash_alias_switches_to_native() {
    let temp_dir = tempfile::tempdir().expect("temporary env alias fixture");
    let source_root = temp_dir.path().join("source");
    source_fixture(&source_root);
    let target_root = source_root.to_str().expect("UTF-8 fixture path");
    let staging_parent = temp_dir.path().join("alias-staging");
    std::fs::create_dir_all(&staging_parent).expect("create alias staging parent");

    let env_db = temp_dir.path().join("alias.env.db");
    let default_db = temp_dir.path().join("alias.default.db");
    let env_store = SqliteStore::open(&env_db)
        .await
        .expect("open alias env switched store");
    let default_store = SqliteStore::open(&default_db)
        .await
        .expect("open alias dispatch default store");
    seed_authoritative_rows(&env_db, target_root, "/fixture/native-alias-target");
    seed_authoritative_rows(&default_db, target_root, "/fixture/native-alias-target");

    let _ = with_a1_index_options_env(
        Some("native-chunk-staged-v0"),
        Some("4"),
        Some(&staging_parent),
        || async {
            env_store
                .codebase_index(target_root, &["rust".to_string()])
                .await
                .expect("run env alias native strategy")
        },
    )
    .await;

    let explicit = default_store
        .codebase_index_with_a1_strategy(
            target_root,
            &["rust".to_string()],
            CodebaseIndexA1DispatchStrategy::NativeChunkStagedV0(CodebaseIndexA1Options {
                batch_rows: 4,
                failpoint: None,
                staging_parent: Some(staging_parent.clone()),
            }),
        )
        .await
        .expect("run explicit native strategy");

    match explicit {
        CodebaseIndexA1DispatchOutcome::NativeChunkStagedV0(outcome) => {
            assert!(outcome.telemetry.batch_rows == 4);
            assert!(outcome.telemetry.staging_cleanup_succeeded);
        }
        _ => panic!("explicit native strategy must return native outcome"),
    }

    let env_snapshot = authoritative_snapshot(&env_db).normalize_target_clock(target_root);
    let explicit_db_snapshot =
        authoritative_snapshot(&default_db).normalize_target_clock(target_root);
    assert_eq!(env_snapshot, explicit_db_snapshot);
    assert!(
        std::fs::read_dir(&staging_parent)
            .expect("read alias staging parent")
            .count()
            == 0,
        "alias native strategy must cleanup staging parent"
    );
}

#[tokio::test]
async fn codebase_index_with_a1_strategy_explicitly_dispatches_staged_native() {
    let temp_dir = tempfile::tempdir().expect("temporary A1 dispatch staging fixture");
    let source_root = temp_dir.path().join("source");
    source_fixture(&source_root);
    let staging_parent = temp_dir.path().join("dispatch-staging");
    std::fs::create_dir_all(&staging_parent).expect("create dispatch staging parent");
    let store = SqliteStore::open(&temp_dir.path().join("state.db"))
        .await
        .expect("open dispatch store");

    let dispatch = store
        .codebase_index_with_a1_strategy(
            source_root.to_str().expect("UTF-8 fixture path"),
            &["rust".to_string()],
            CodebaseIndexA1DispatchStrategy::NativeChunkStagedV0(CodebaseIndexA1Options {
                batch_rows: 4,
                failpoint: None,
                staging_parent: Some(staging_parent.clone()),
            }),
        )
        .await
        .expect("run staged-native via dispatch API");

    match dispatch {
        CodebaseIndexA1DispatchOutcome::NativeChunkStagedV0(outcome) => {
            assert_eq!(outcome.telemetry.strategy, "native_chunk_staged_v0");
            assert!(outcome.telemetry.batch_rows > 0);
            assert!(outcome.telemetry.staging_cleanup_succeeded);
            assert!(outcome.telemetry.staging_file_path.starts_with(
                staging_parent
                    .canonicalize()
                    .expect("canonical dispatch staging parent")
            ));
            assert!(
                !outcome.telemetry.staging_file_path.exists(),
                "dispatch telemetry must point at cleaned staging file"
            );
            assert!(
                std::fs::read_dir(&staging_parent)
                    .expect("read dispatch staging parent")
                    .count()
                    == 0,
                "dispatch staged-native path must cleanup temporary staging"
            );
        }
        _ => panic!("explicit staged-native strategy must return staged-native outcome"),
    }
}

#[tokio::test]
async fn a1_pragma_evidence_is_authoritative_read_only_and_stable() {
    let temp_dir = tempfile::tempdir().expect("temporary A1 PRAGMA fixture");
    let source_root = temp_dir.path().join("source");
    source_fixture(&source_root);
    let target_root = source_root.to_str().expect("UTF-8 fixture path");
    let staging_parent = temp_dir.path().join("staging");
    std::fs::create_dir_all(&staging_parent).expect("create staging parent");
    let db_path = temp_dir.path().join("state.db");
    let store = SqliteStore::open(&db_path)
        .await
        .expect("open temporary store");

    let before = store
        .codebase_index_pragmas_a1()
        .await
        .expect("read authoritative PRAGMAs before indexing");
    assert_eq!(before.journal_mode, "wal");
    assert_eq!(before.foreign_keys, 1);
    assert_eq!(before.busy_timeout_ms, 5_000);
    assert!(before.autocommit);
    assert_eq!(before.database_names, ["main", "temp"]);
    assert_eq!(before.database_files.len(), 2);
    assert_eq!(
        before.database_files[0]
            .canonicalize()
            .expect("canonical authoritative database path"),
        db_path
            .canonicalize()
            .expect("canonical fixture database path")
    );
    assert!(before.database_files[1].as_os_str().is_empty());

    store
        .codebase_index_full_vec_a1(target_root, &["rust".to_string()])
        .await
        .expect("run measured FullVec path");
    let after_full_vec = store
        .codebase_index_pragmas_a1()
        .await
        .expect("read authoritative PRAGMAs after FullVec");
    assert_eq!(after_full_vec, before);

    store
        .codebase_index_bounded_native_a1(
            target_root,
            &["rust".to_string()],
            CodebaseIndexA1Options {
                batch_rows: 2,
                failpoint: None,
                staging_parent: Some(staging_parent),
            },
        )
        .await
        .expect("run bounded native path");
    let after_bounded_native = store
        .codebase_index_pragmas_a1()
        .await
        .expect("read authoritative PRAGMAs after bounded native");
    assert_eq!(after_bounded_native, before);
}
