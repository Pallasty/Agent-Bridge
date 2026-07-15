//! S7 synthetic local durable replay tombstones.
//!
//! This is a private executable storage contract, not a receiver.  It uses a
//! separately provisioned SQLite sidecar and deliberately has no default path,
//! public constructor, `StateStore` method, or Bridge caller.  Normal opening
//! never creates a missing database.  The database retains only fixed-length
//! commitments and has no update, delete, expiry, or garbage-collection path.

#![cfg_attr(not(test), allow(dead_code))]

use super::{
    replay_registry_seal, verifier_error, CandidateReplayRegistryV1, ReplayConsumeReceiptV1,
    ReplayConsumeRequestV1, VerifierResult,
};
use sha2::{Digest, Sha256};
use std::path::{Path, PathBuf};
#[cfg(test)]
use std::sync::atomic::{AtomicBool, Ordering};
use std::time::Duration;
use tokio_rusqlite::rusqlite::{
    self, params, Connection, OpenFlags, OptionalExtension, TransactionBehavior,
};

const APPLICATION_ID: i64 = 0x4142_5237; // ASCII "ABR7"
const USER_VERSION: i64 = 1;
const BUSY_TIMEOUT: Duration = Duration::from_millis(1_500);
const META_TABLE: &str = "track_b_replay_registry_meta_v1";
const TOMBSTONE_TABLE: &str = "track_b_replay_tombstones_v1";
const SCHEMA_MANIFEST_SHA256: &str =
    "686c22c3f4f3f696113a88a6d72bb292635a55020e00144ea2ef02f7eae35466";

const SCHEMA_SQL: &str = r#"
CREATE TABLE track_b_replay_registry_meta_v1 (
    singleton INTEGER NOT NULL PRIMARY KEY CHECK (singleton = 1),
    registry_generation_id BLOB NOT NULL
        CHECK (typeof(registry_generation_id) = 'blob' AND length(registry_generation_id) = 32)
) STRICT, WITHOUT ROWID;

CREATE TABLE track_b_replay_tombstones_v1 (
    replay_key_sha256 BLOB NOT NULL PRIMARY KEY
        CHECK (typeof(replay_key_sha256) = 'blob' AND length(replay_key_sha256) = 32),
    scope_sha256 BLOB NOT NULL
        CHECK (typeof(scope_sha256) = 'blob' AND length(scope_sha256) = 32),
    payload_sha256 BLOB NOT NULL
        CHECK (typeof(payload_sha256) = 'blob' AND length(payload_sha256) = 32)
) STRICT, WITHOUT ROWID;

CREATE TRIGGER track_b_replay_tombstones_v1_no_update
BEFORE UPDATE ON track_b_replay_tombstones_v1
BEGIN
    SELECT RAISE(ABORT, 'track_b replay tombstones are insert-only');
END;

CREATE TRIGGER track_b_replay_tombstones_v1_no_delete
BEFORE DELETE ON track_b_replay_tombstones_v1
BEGIN
    SELECT RAISE(ABORT, 'track_b replay tombstones are permanent');
END;

CREATE TRIGGER track_b_replay_registry_meta_v1_no_insert
BEFORE INSERT ON track_b_replay_registry_meta_v1
WHEN EXISTS (SELECT 1 FROM track_b_replay_registry_meta_v1)
BEGIN
    SELECT RAISE(ABORT, 'track_b replay registry identity is immutable');
END;

CREATE TRIGGER track_b_replay_registry_meta_v1_no_update
BEFORE UPDATE ON track_b_replay_registry_meta_v1
BEGIN
    SELECT RAISE(ABORT, 'track_b replay registry identity is immutable');
END;

CREATE TRIGGER track_b_replay_registry_meta_v1_no_delete
BEFORE DELETE ON track_b_replay_registry_meta_v1
BEGIN
    SELECT RAISE(ABORT, 'track_b replay registry identity is permanent');
END;
"#;

const EXPECTED_MAIN_OBJECTS: [(&str, &str); 7] = [
    ("table", META_TABLE),
    ("table", TOMBSTONE_TABLE),
    ("trigger", "track_b_replay_registry_meta_v1_no_delete"),
    ("trigger", "track_b_replay_registry_meta_v1_no_insert"),
    ("trigger", "track_b_replay_registry_meta_v1_no_update"),
    ("trigger", "track_b_replay_tombstones_v1_no_delete"),
    ("trigger", "track_b_replay_tombstones_v1_no_update"),
];

fn indeterminate(detail: &'static str) -> super::TrackBDetachedVerifierV1Error {
    verifier_error("track_b_detached_v1_registry_indeterminate", detail)
}

fn invalid_identity(detail: &'static str) -> super::TrackBDetachedVerifierV1Error {
    verifier_error("track_b_detached_v1_registry_identity", detail)
}

fn open_flags() -> OpenFlags {
    OpenFlags::SQLITE_OPEN_READ_WRITE
        | OpenFlags::SQLITE_OPEN_NO_MUTEX
        | OpenFlags::SQLITE_OPEN_NOFOLLOW
        | OpenFlags::SQLITE_OPEN_EXRESCODE
}

fn read_i64_pragma(connection: &Connection, pragma: &str) -> rusqlite::Result<i64> {
    connection.query_row(&format!("PRAGMA {pragma}"), [], |row| row.get(0))
}

fn read_text_pragma(connection: &Connection, pragma: &str) -> rusqlite::Result<String> {
    connection.query_row(&format!("PRAGMA {pragma}"), [], |row| row.get(0))
}

fn validate_file(path: &Path) -> VerifierResult<PathBuf> {
    let metadata = std::fs::symlink_metadata(path)
        .map_err(|_| invalid_identity("the explicitly provisioned replay registry is missing"))?;
    if !metadata.file_type().is_file() || metadata.file_type().is_symlink() {
        return Err(invalid_identity(
            "the replay registry path is not a regular non-symlink file",
        ));
    }
    #[cfg(unix)]
    {
        use std::os::unix::fs::PermissionsExt as _;
        if metadata.permissions().mode() & 0o077 != 0 {
            return Err(invalid_identity(
                "the replay registry grants group or other file permissions",
            ));
        }
    }
    std::fs::canonicalize(path)
        .map_err(|_| invalid_identity("the replay registry canonical path is unavailable"))
}

fn validate_table_columns(connection: &Connection) -> rusqlite::Result<bool> {
    let meta_columns: Vec<(String, String, i64, i64)> = connection
        .prepare(&format!("PRAGMA main.table_info('{META_TABLE}')"))?
        .query_map([], |row| {
            Ok((row.get(1)?, row.get(2)?, row.get(3)?, row.get(5)?))
        })?
        .collect::<rusqlite::Result<_>>()?;
    let tombstone_columns: Vec<(String, String, i64, i64)> = connection
        .prepare(&format!("PRAGMA main.table_info('{TOMBSTONE_TABLE}')"))?
        .query_map([], |row| {
            Ok((row.get(1)?, row.get(2)?, row.get(3)?, row.get(5)?))
        })?
        .collect::<rusqlite::Result<_>>()?;
    Ok(meta_columns
        == vec![
            ("singleton".to_string(), "INTEGER".to_string(), 1, 1),
            (
                "registry_generation_id".to_string(),
                "BLOB".to_string(),
                1,
                0,
            ),
        ]
        && tombstone_columns
            == vec![
                ("replay_key_sha256".to_string(), "BLOB".to_string(), 1, 1),
                ("scope_sha256".to_string(), "BLOB".to_string(), 1, 0),
                ("payload_sha256".to_string(), "BLOB".to_string(), 1, 0),
            ])
}

fn validate_schema_and_identity(
    connection: &Connection,
    expected_generation_id: &[u8; 32],
) -> VerifierResult<()> {
    let application_id = read_i64_pragma(connection, "application_id")
        .map_err(|_| indeterminate("replay registry application identity could not be read"))?;
    let user_version = read_i64_pragma(connection, "user_version")
        .map_err(|_| indeterminate("replay registry schema version could not be read"))?;
    if application_id != APPLICATION_ID || user_version != USER_VERSION {
        return Err(invalid_identity(
            "replay registry application or schema version is not pinned S7 v1",
        ));
    }

    let schema_rows: Vec<(String, String, String)> = connection
        .prepare(
            "SELECT type, name, sql FROM main.sqlite_schema
             WHERE name NOT LIKE 'sqlite_%'
             ORDER BY type, name",
        )
        .and_then(|mut statement| {
            statement
                .query_map([], |row| Ok((row.get(0)?, row.get(1)?, row.get(2)?)))?
                .collect::<rusqlite::Result<Vec<_>>>()
        })
        .map_err(|_| indeterminate("replay registry schema objects could not be read"))?;
    let objects: Vec<(String, String)> = schema_rows
        .iter()
        .map(|(kind, name, _)| (kind.clone(), name.clone()))
        .collect();
    let mut expected: Vec<(String, String)> = EXPECTED_MAIN_OBJECTS
        .iter()
        .map(|(kind, name)| ((*kind).to_string(), (*name).to_string()))
        .collect();
    expected.sort();
    if objects != expected {
        return Err(invalid_identity(
            "replay registry contains missing, extra, or renamed persistent objects",
        ));
    }
    let mut schema_hasher = Sha256::new();
    for (kind, name, sql) in &schema_rows {
        for field in [kind.as_bytes(), name.as_bytes(), sql.as_bytes()] {
            schema_hasher.update((field.len() as u64).to_be_bytes());
            schema_hasher.update(field);
        }
    }
    let schema_digest = schema_hasher.finalize();
    if format!("{schema_digest:x}") != SCHEMA_MANIFEST_SHA256 {
        return Err(invalid_identity(
            "replay registry schema SQL does not match the pinned S7 manifest",
        ));
    }

    let temp_count: i64 = connection
        .query_row("SELECT COUNT(*) FROM temp.sqlite_schema", [], |row| {
            row.get(0)
        })
        .map_err(|_| indeterminate("temporary replay registry objects could not be checked"))?;
    if temp_count != 0 {
        return Err(invalid_identity(
            "temporary objects are forbidden in a replay registry connection",
        ));
    }

    if !validate_table_columns(connection)
        .map_err(|_| indeterminate("replay registry column layout could not be read"))?
    {
        return Err(invalid_identity(
            "replay registry column layout is not the closed S7 profile",
        ));
    }

    let generation: Option<Vec<u8>> = connection
        .query_row(
            &format!("SELECT registry_generation_id FROM main.{META_TABLE} WHERE singleton = 1"),
            [],
            |row| row.get(0),
        )
        .optional()
        .map_err(|_| indeterminate("replay registry generation could not be read"))?;
    if generation.as_deref() != Some(expected_generation_id.as_slice()) {
        return Err(invalid_identity(
            "replay registry generation does not match the externally pinned identity",
        ));
    }

    let quick_check = read_text_pragma(connection, "quick_check(1)")
        .map_err(|_| indeterminate("replay registry quick_check could not complete"))?;
    if quick_check != "ok" {
        return Err(invalid_identity("replay registry quick_check did not pass"));
    }
    Ok(())
}

fn configure_connection(connection: &Connection) -> VerifierResult<()> {
    connection
        .busy_timeout(BUSY_TIMEOUT)
        .map_err(|_| indeterminate("replay registry busy timeout could not be configured"))?;

    let journal_mode = read_text_pragma(connection, "journal_mode")
        .map_err(|_| indeterminate("replay registry journal mode could not be read"))?;
    if journal_mode.to_ascii_lowercase() != "delete" {
        return Err(invalid_identity(
            "replay registry requires the closed DELETE journal profile",
        ));
    }
    connection
        .execute_batch(
            "PRAGMA synchronous=EXTRA;
             PRAGMA foreign_keys=ON;
             PRAGMA read_uncommitted=OFF;
             PRAGMA query_only=OFF;
             PRAGMA trusted_schema=OFF;
             PRAGMA locking_mode=NORMAL;",
        )
        .map_err(|_| indeterminate("replay registry connection profile could not be configured"))?;

    let synchronous = read_i64_pragma(connection, "synchronous")
        .map_err(|_| indeterminate("replay registry synchronous mode could not be read"))?;
    let foreign_keys = read_i64_pragma(connection, "foreign_keys")
        .map_err(|_| indeterminate("replay registry foreign-key mode could not be read"))?;
    let read_uncommitted = read_i64_pragma(connection, "read_uncommitted")
        .map_err(|_| indeterminate("replay registry isolation mode could not be read"))?;
    let query_only = read_i64_pragma(connection, "query_only")
        .map_err(|_| indeterminate("replay registry query mode could not be read"))?;
    let trusted_schema = read_i64_pragma(connection, "trusted_schema")
        .map_err(|_| indeterminate("replay registry trusted-schema mode could not be read"))?;
    let locking_mode = read_text_pragma(connection, "locking_mode")
        .map_err(|_| indeterminate("replay registry locking mode could not be read"))?;
    if synchronous != 3
        || foreign_keys != 1
        || read_uncommitted != 0
        || query_only != 0
        || trusted_schema != 0
        || locking_mode.to_ascii_lowercase() != "normal"
    {
        return Err(invalid_identity(
            "replay registry connection profile did not retain its closed values",
        ));
    }
    Ok(())
}

fn open_existing(
    path: &Path,
    canonical_path: &Path,
    expected_generation_id: &[u8; 32],
) -> VerifierResult<Connection> {
    if validate_file(path)?.as_path() != canonical_path {
        return Err(invalid_identity(
            "replay registry canonical path differs from the pinned path",
        ));
    }
    let connection = Connection::open_with_flags(path, open_flags())
        .map_err(|_| indeterminate("the existing replay registry could not be opened"))?;
    validate_schema_and_identity(&connection, expected_generation_id)?;
    configure_connection(&connection)?;
    validate_schema_and_identity(&connection, expected_generation_id)?;
    Ok(connection)
}

#[cfg(test)]
fn pause_before_commit_if_requested() {
    let Some(marker) = std::env::var_os("AB_S7_PAUSE_BEFORE_COMMIT_MARKER") else {
        return;
    };
    std::fs::write(PathBuf::from(marker), b"inserted-not-committed")
        .expect("write synthetic pre-commit marker");
    loop {
        std::thread::park_timeout(Duration::from_secs(1));
    }
}

/// A path- and generation-pinned local registry.  Construction is test-only;
/// the non-test feature compiles the storage contract but exposes no capability
/// that could provision or open a receiver ledger.
pub(super) struct SyntheticDurableReplayRegistryV1 {
    canonical_path: PathBuf,
    path: PathBuf,
    registry_generation_id: [u8; 32],
    #[cfg(test)]
    report_indeterminate_after_commit_once: AtomicBool,
}

impl std::fmt::Debug for SyntheticDurableReplayRegistryV1 {
    fn fmt(&self, formatter: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        formatter
            .debug_struct("SyntheticDurableReplayRegistryV1")
            .field("path", &"[PINNED]")
            .field("registry_generation", &"[PINNED]")
            .finish_non_exhaustive()
    }
}

impl SyntheticDurableReplayRegistryV1 {
    /// Private identity observation for the S8 admission wrapper. This does
    /// not expose a constructor or make the generation an anti-rollback
    /// anchor; S8 still requires an independently current authority record.
    pub(super) fn generation_id_for_restore_epoch(&self) -> [u8; 32] {
        self.registry_generation_id
    }
}

impl replay_registry_seal::Sealed for SyntheticDurableReplayRegistryV1 {}

impl CandidateReplayRegistryV1 for SyntheticDurableReplayRegistryV1 {
    fn consume_once(
        &self,
        request: ReplayConsumeRequestV1,
    ) -> VerifierResult<ReplayConsumeReceiptV1> {
        if request.consumed_at_utc < 0 || request.consumed_at_utc >= request.expires_at_utc {
            return Err(verifier_error(
                "track_b_detached_v1_registry_time",
                "registry request is outside its admission-validity window",
            ));
        }

        let mut connection = open_existing(
            &self.path,
            &self.canonical_path,
            &self.registry_generation_id,
        )?;
        let transaction = connection
            .transaction_with_behavior(TransactionBehavior::Immediate)
            .map_err(|_| indeterminate("replay registry write ownership is indeterminate"))?;
        validate_schema_and_identity(&transaction, &self.registry_generation_id)?;

        let inserted = transaction
            .execute(
                "INSERT INTO main.track_b_replay_tombstones_v1
                    (replay_key_sha256, scope_sha256, payload_sha256)
                 VALUES (?1, ?2, ?3)
                 ON CONFLICT(replay_key_sha256) DO NOTHING",
                params![
                    request.replay_key_sha256.as_slice(),
                    request.scope_sha256.as_slice(),
                    request.payload_sha256.as_slice(),
                ],
            )
            .map_err(|_| indeterminate("replay registry conditional insert failed closed"))?;

        if inserted == 1 {
            #[cfg(test)]
            pause_before_commit_if_requested();
            transaction
                .commit()
                .map_err(|_| indeterminate("replay registry commit result is indeterminate"))?;
            #[cfg(test)]
            if self
                .report_indeterminate_after_commit_once
                .swap(false, Ordering::SeqCst)
            {
                return Err(indeterminate(
                    "synthetic result loss after a confirmed durable commit",
                ));
            }
            return Ok(ReplayConsumeReceiptV1 {
                durable: true,
                replay_key_sha256: request.replay_key_sha256,
                scope_sha256: request.scope_sha256,
            });
        }
        if inserted != 0 {
            return Err(indeterminate(
                "replay registry insert returned an impossible row count",
            ));
        }

        let previous: Option<(Vec<u8>, Vec<u8>)> = transaction
            .query_row(
                "SELECT scope_sha256, payload_sha256
                 FROM main.track_b_replay_tombstones_v1
                 WHERE replay_key_sha256 = ?1",
                [request.replay_key_sha256.as_slice()],
                |row| Ok((row.get(0)?, row.get(1)?)),
            )
            .optional()
            .map_err(|_| indeterminate("replay registry conflict row could not be read"))?;
        transaction
            .rollback()
            .map_err(|_| indeterminate("replay registry conflict transaction is indeterminate"))?;
        let Some((scope_sha256, payload_sha256)) = previous else {
            return Err(indeterminate(
                "replay registry conflict had no immutable winner row",
            ));
        };
        if scope_sha256.len() != 32 || payload_sha256.len() != 32 {
            return Err(indeterminate(
                "replay registry conflict row violated its fixed-length profile",
            ));
        }
        if scope_sha256.as_slice() == request.scope_sha256
            && payload_sha256.as_slice() == request.payload_sha256
        {
            return Err(verifier_error(
                "track_b_detached_v1_replay",
                "candidate request nonce was already durably consumed",
            ));
        }
        Err(verifier_error(
            "track_b_detached_v1_scope_collision",
            "transport key and nonce were durably burned for a different scope",
        ))
    }
}

#[cfg(test)]
fn provision_new(path: &Path, registry_generation_id: [u8; 32]) -> VerifierResult<()> {
    if registry_generation_id.iter().all(|byte| *byte == 0) {
        return Err(invalid_identity(
            "replay registry generation must not be the all-zero sentinel",
        ));
    }
    let parent = path.parent().ok_or_else(|| {
        invalid_identity("replay registry provisioning requires an explicit parent")
    })?;
    if !parent.is_dir() {
        return Err(invalid_identity(
            "replay registry parent must be provisioned separately",
        ));
    }

    let mut options = std::fs::OpenOptions::new();
    options.read(true).write(true).create_new(true);
    #[cfg(unix)]
    {
        use std::os::unix::fs::OpenOptionsExt as _;
        options.mode(0o600);
    }
    let file = options
        .open(path)
        .map_err(|_| invalid_identity("replay registry provisioning refuses an existing path"))?;
    file.sync_all()
        .map_err(|_| indeterminate("new replay registry file could not be synchronized"))?;
    drop(file);

    let result = (|| -> VerifierResult<()> {
        let mut connection = Connection::open_with_flags(path, open_flags())
            .map_err(|_| indeterminate("new replay registry could not be opened"))?;
        connection
            .busy_timeout(BUSY_TIMEOUT)
            .map_err(|_| indeterminate("new replay registry busy timeout failed"))?;
        connection
            .execute_batch("PRAGMA journal_mode=DELETE; PRAGMA synchronous=EXTRA;")
            .map_err(|_| indeterminate("new replay registry durability profile failed"))?;
        let transaction = connection
            .transaction_with_behavior(TransactionBehavior::Immediate)
            .map_err(|_| indeterminate("new replay registry transaction failed"))?;
        transaction
            .execute_batch(SCHEMA_SQL)
            .map_err(|_| indeterminate("new replay registry schema failed"))?;
        transaction
            .execute(
                &format!(
                    "INSERT INTO main.{META_TABLE}(singleton, registry_generation_id) VALUES(1, ?1)"
                ),
                [registry_generation_id.as_slice()],
            )
            .map_err(|_| indeterminate("new replay registry identity insert failed"))?;
        transaction
            .execute_batch(&format!(
                "PRAGMA application_id={APPLICATION_ID}; PRAGMA user_version={USER_VERSION};"
            ))
            .map_err(|_| indeterminate("new replay registry header identity failed"))?;
        transaction
            .commit()
            .map_err(|_| indeterminate("new replay registry commit is indeterminate"))?;
        configure_connection(&connection)?;
        validate_schema_and_identity(&connection, &registry_generation_id)?;
        drop(connection);
        std::fs::File::open(path)
            .and_then(|database| database.sync_all())
            .map_err(|_| indeterminate("provisioned replay registry could not be synchronized"))?;
        std::fs::File::open(parent)
            .and_then(|directory| directory.sync_all())
            .map_err(|_| {
                indeterminate("provisioned replay registry directory could not be synchronized")
            })?;
        Ok(())
    })();
    if result.is_err() {
        let _ = std::fs::remove_file(path);
        let mut journal = path.as_os_str().to_os_string();
        journal.push("-journal");
        let _ = std::fs::remove_file(PathBuf::from(journal));
    }
    result
}

#[cfg(test)]
pub(super) fn provision_and_open_for_test(
    path: &Path,
    registry_generation_id: [u8; 32],
) -> VerifierResult<SyntheticDurableReplayRegistryV1> {
    provision_new(path, registry_generation_id)?;
    open_for_test(path, registry_generation_id)
}

#[cfg(test)]
pub(super) fn open_for_test(
    path: &Path,
    registry_generation_id: [u8; 32],
) -> VerifierResult<SyntheticDurableReplayRegistryV1> {
    let canonical_path = validate_file(path)?;
    let _ = open_existing(path, &canonical_path, &registry_generation_id)?;
    Ok(SyntheticDurableReplayRegistryV1 {
        canonical_path,
        path: path.to_path_buf(),
        registry_generation_id,
        report_indeterminate_after_commit_once: AtomicBool::new(false),
    })
}

#[cfg(test)]
pub(super) fn open_with_result_loss_for_test(
    path: &Path,
    registry_generation_id: [u8; 32],
) -> VerifierResult<SyntheticDurableReplayRegistryV1> {
    let registry = open_for_test(path, registry_generation_id)?;
    registry
        .report_indeterminate_after_commit_once
        .store(true, Ordering::SeqCst);
    Ok(registry)
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::process::{Command, Stdio};
    use std::sync::{Arc, Barrier};

    const GENERATION: [u8; 32] = [0x71; 32];
    const MULTIPROCESS_HELPER_ENV: &str = "AB_S7_MULTIPROCESS_HELPER";
    const CRASH_HELPER_ENV: &str = "AB_S7_CRASH_HELPER";
    const PRECOMMIT_HELPER_ENV: &str = "AB_S7_PRECOMMIT_HELPER";

    struct TestDirectory {
        path: PathBuf,
    }

    impl TestDirectory {
        fn new(label: &str) -> Self {
            let path = std::env::temp_dir().join(format!(
                "ab-s7-{label}-{}-{}",
                std::process::id(),
                std::time::SystemTime::now()
                    .duration_since(std::time::UNIX_EPOCH)
                    .expect("system clock")
                    .as_nanos()
            ));
            std::fs::create_dir(&path).expect("create isolated S7 directory");
            Self { path }
        }

        fn database(&self) -> PathBuf {
            self.path.join("replay.db")
        }
    }

    impl Drop for TestDirectory {
        fn drop(&mut self) {
            let _ = std::fs::remove_dir_all(&self.path);
        }
    }

    fn request(scope: u8, payload: u8) -> ReplayConsumeRequestV1 {
        ReplayConsumeRequestV1 {
            consumed_at_utc: 150,
            expires_at_utc: 200,
            payload_sha256: [payload; 32],
            replay_key_sha256: [0x41; 32],
            scope_sha256: [scope; 32],
        }
    }

    fn error_code(result: VerifierResult<ReplayConsumeReceiptV1>) -> Option<&'static str> {
        result.err().map(|error| error.code)
    }

    #[test]
    fn s7_full_verifier_requires_durable_commit() {
        let directory = TestDirectory::new("full-verifier");
        let database = directory.database();
        let generation = [0x73; 32];
        let registry = provision_and_open_for_test(&database, generation)
            .expect("explicit S7 registry provision");
        let payload = super::super::tests::sample_payload("trial-s7-durable-verifier");
        let exact = super::super::tests::canonical(&payload);
        let verified = super::super::verify_synthetic_detached_candidate_durable_v1(
            super::super::tests::permit(&payload),
            super::super::tests::authentication(&exact),
            exact.clone(),
            &registry,
            150,
        )
        .expect("durably committed candidate verifies under the private S7 wrapper");
        assert!(verified.replay_receipt.durable);
        drop(verified);
        drop(registry);

        let reopened = open_for_test(&database, generation).expect("reopen pinned registry");
        let replay = super::super::verify_synthetic_detached_candidate_durable_v1(
            super::super::tests::permit(&payload),
            super::super::tests::authentication(&exact),
            exact,
            &reopened,
            150,
        )
        .expect_err("restart must preserve the consumed nonce");
        assert_eq!(replay.code(), "track_b_detached_v1_replay");
    }

    #[test]
    fn s7_restart_expiry_and_insert_only_tombstone_are_durable() {
        let directory = TestDirectory::new("restart");
        let path = directory.database();
        let first = provision_and_open_for_test(&path, GENERATION).expect("explicit provision");
        let receipt = first
            .consume_once(request(0x51, 0x61))
            .expect("first consume");
        assert!(receipt.durable);
        drop(first);

        let reopened = open_for_test(&path, GENERATION).expect("restart open");
        assert_eq!(
            error_code(reopened.consume_once(request(0x51, 0x61))),
            Some("track_b_detached_v1_replay")
        );
        let mut after_expiry = request(0x51, 0x61);
        after_expiry.consumed_at_utc = 500;
        after_expiry.expires_at_utc = 501;
        assert_eq!(
            error_code(reopened.consume_once(after_expiry)),
            Some("track_b_detached_v1_replay"),
            "expiry is admission metadata and never a tombstone retention deadline"
        );

        let raw = Connection::open_with_flags(&path, open_flags()).expect("raw audit connection");
        assert!(raw
            .execute(
                "UPDATE track_b_replay_tombstones_v1 SET scope_sha256=?1",
                [[0x99_u8; 32].as_slice()],
            )
            .is_err());
        assert!(raw
            .execute("DELETE FROM track_b_replay_tombstones_v1", [])
            .is_err());
        let count: i64 = raw
            .query_row(
                "SELECT COUNT(*) FROM track_b_replay_tombstones_v1",
                [],
                |row| row.get(0),
            )
            .expect("count permanent tombstone");
        assert_eq!(count, 1);
    }

    #[test]
    fn s7_scope_collision_never_overwrites_the_first_commitment() {
        let directory = TestDirectory::new("collision");
        let path = directory.database();
        let registry = provision_and_open_for_test(&path, GENERATION).expect("explicit provision");
        registry.consume_once(request(0x51, 0x61)).expect("winner");
        assert_eq!(
            error_code(registry.consume_once(request(0x52, 0x62))),
            Some("track_b_detached_v1_scope_collision")
        );
        assert_eq!(
            error_code(registry.consume_once(request(0x51, 0x61))),
            Some("track_b_detached_v1_replay")
        );
    }

    #[test]
    fn s7_missing_replaced_or_foreign_registry_fails_closed_without_creation() {
        let directory = TestDirectory::new("identity");
        let path = directory.database();
        let missing = open_for_test(&path, GENERATION).expect_err("missing DB must reject");
        assert_eq!(missing.code, "track_b_detached_v1_registry_identity");
        assert!(
            !path.exists(),
            "normal open must not create a replacement DB"
        );

        provision_new(&path, GENERATION).expect("explicit provision");
        assert!(open_for_test(&path, [0x72; 32]).is_err());
        std::fs::remove_file(&path).expect("simulate registry deletion");
        assert!(open_for_test(&path, GENERATION).is_err());
        assert!(!path.exists());

        let foreign = directory.path.join("foreign.db");
        let connection = Connection::open(&foreign).expect("foreign SQLite");
        connection
            .execute("CREATE TABLE unrelated(value TEXT)", [])
            .expect("foreign schema");
        drop(connection);
        #[cfg(unix)]
        {
            use std::os::unix::fs::PermissionsExt as _;
            std::fs::set_permissions(&foreign, std::fs::Permissions::from_mode(0o600))
                .expect("restrict foreign DB");
        }
        assert!(open_for_test(&foreign, GENERATION).is_err());
    }

    #[test]
    fn s7_schema_trigger_or_permission_drift_fails_closed() {
        let directory = TestDirectory::new("schema-drift");
        let path = directory.database();
        drop(provision_and_open_for_test(&path, GENERATION).expect("explicit provision"));
        let raw = Connection::open_with_flags(&path, open_flags()).expect("raw drift connection");
        raw.execute_batch("DROP TRIGGER track_b_replay_tombstones_v1_no_delete;")
            .expect("simulate trigger drift");
        drop(raw);
        let drift = open_for_test(&path, GENERATION).expect_err("trigger drift must reject");
        assert_eq!(drift.code, "track_b_detached_v1_registry_identity");

        #[cfg(unix)]
        {
            use std::os::unix::fs::PermissionsExt as _;
            std::fs::set_permissions(&path, std::fs::Permissions::from_mode(0o644))
                .expect("simulate permissive mode");
            let permissions =
                open_for_test(&path, GENERATION).expect_err("group-readable registry must reject");
            assert_eq!(permissions.code, "track_b_detached_v1_registry_identity");
        }
    }

    #[test]
    fn s7_busy_writer_fails_closed_without_memory_fallback() {
        let directory = TestDirectory::new("busy");
        let path = directory.database();
        let registry = provision_and_open_for_test(&path, GENERATION).expect("explicit provision");
        let mut locker = Connection::open_with_flags(&path, open_flags()).expect("locker open");
        locker
            .busy_timeout(BUSY_TIMEOUT)
            .expect("locker busy timeout");
        let transaction = locker
            .transaction_with_behavior(TransactionBehavior::Immediate)
            .expect("hold writer lock");
        assert_eq!(
            error_code(registry.consume_once(request(0x51, 0x61))),
            Some("track_b_detached_v1_registry_indeterminate")
        );
        transaction.rollback().expect("release writer lock");
        let receipt = registry
            .consume_once(request(0x51, 0x61))
            .expect("known pre-commit lock failure must not burn the nonce");
        assert!(receipt.durable);
    }

    #[test]
    fn s7_independent_connections_linearize_one_winner() {
        let directory = TestDirectory::new("threads");
        let path = directory.database();
        drop(provision_and_open_for_test(&path, GENERATION).expect("explicit provision"));
        let barrier = Arc::new(Barrier::new(6));
        let mut workers = Vec::new();
        for _ in 0..6 {
            let worker_path = path.clone();
            let worker_barrier = Arc::clone(&barrier);
            workers.push(std::thread::spawn(move || {
                let registry = open_for_test(&worker_path, GENERATION).expect("worker open");
                worker_barrier.wait();
                error_code(registry.consume_once(request(0x51, 0x61)))
            }));
        }
        let results: Vec<Option<&'static str>> = workers
            .into_iter()
            .map(|worker| worker.join().expect("worker join"))
            .collect();
        assert_eq!(results.iter().filter(|result| result.is_none()).count(), 1);
        assert_eq!(
            results
                .iter()
                .filter(|result| **result == Some("track_b_detached_v1_replay"))
                .count(),
            5
        );
    }

    #[test]
    fn s7_mixed_scope_connection_race_preserves_one_immutable_winner() {
        let directory = TestDirectory::new("mixed-scope");
        let path = directory.database();
        drop(provision_and_open_for_test(&path, GENERATION).expect("explicit provision"));
        let barrier = Arc::new(Barrier::new(8));
        let mut workers = Vec::new();
        for index in 0..8 {
            let worker_path = path.clone();
            let worker_barrier = Arc::clone(&barrier);
            workers.push(std::thread::spawn(move || {
                let registry = open_for_test(&worker_path, GENERATION).expect("worker open");
                worker_barrier.wait();
                let variant = if index % 2 == 0 { 0x51 } else { 0x52 };
                (
                    variant,
                    error_code(registry.consume_once(request(variant, variant + 0x10))),
                )
            }));
        }
        let results: Vec<(u8, Option<&'static str>)> = workers
            .into_iter()
            .map(|worker| worker.join().expect("worker join"))
            .collect();
        let winner = results
            .iter()
            .find_map(|(variant, code)| code.is_none().then_some(*variant))
            .expect("one mixed-scope winner");
        assert_eq!(results.iter().filter(|(_, code)| code.is_none()).count(), 1);
        for (variant, code) in results {
            if code.is_none() {
                continue;
            }
            let expected = if variant == winner {
                "track_b_detached_v1_replay"
            } else {
                "track_b_detached_v1_scope_collision"
            };
            assert_eq!(code, Some(expected));
        }
        let reopened = open_for_test(&path, GENERATION).expect("mixed-scope audit open");
        assert_eq!(
            error_code(reopened.consume_once(request(winner, winner + 0x10))),
            Some("track_b_detached_v1_replay")
        );
        let loser = if winner == 0x51 { 0x52 } else { 0x51 };
        assert_eq!(
            error_code(reopened.consume_once(request(loser, loser + 0x10))),
            Some("track_b_detached_v1_scope_collision")
        );
    }

    #[test]
    fn s7_result_loss_after_commit_is_indeterminate_then_replay() {
        let directory = TestDirectory::new("result-loss");
        let path = directory.database();
        drop(provision_and_open_for_test(&path, GENERATION).expect("explicit provision"));
        let registry =
            open_with_result_loss_for_test(&path, GENERATION).expect("fault-injected open");
        assert_eq!(
            error_code(registry.consume_once(request(0x51, 0x61))),
            Some("track_b_detached_v1_registry_indeterminate")
        );
        drop(registry);
        let reopened = open_for_test(&path, GENERATION).expect("restart after result loss");
        assert_eq!(
            error_code(reopened.consume_once(request(0x51, 0x61))),
            Some("track_b_detached_v1_replay")
        );
    }

    fn helper_command(test_name: &str, database: &Path) -> Command {
        let mut command = Command::new(std::env::current_exe().expect("current test executable"));
        command
            .arg("--ignored")
            .arg("--exact")
            .arg(test_name)
            .arg("--nocapture")
            .env("AB_S7_HELPER_DB", database)
            .stdout(Stdio::null())
            .stderr(Stdio::null());
        command
    }

    #[test]
    #[ignore]
    fn s7_real_process_competition_helper() {
        if std::env::var_os(MULTIPROCESS_HELPER_ENV).is_none() {
            return;
        }
        let database = PathBuf::from(std::env::var_os("AB_S7_HELPER_DB").expect("helper DB"));
        let barrier = PathBuf::from(std::env::var_os("AB_S7_HELPER_BARRIER").expect("barrier"));
        let deadline = std::time::Instant::now() + Duration::from_secs(10);
        while !barrier.exists() {
            if std::time::Instant::now() >= deadline {
                std::process::exit(31);
            }
            std::thread::sleep(Duration::from_millis(5));
        }
        let registry = open_for_test(&database, GENERATION).expect("child open");
        match error_code(registry.consume_once(request(0x51, 0x61))) {
            None => std::process::exit(0),
            Some("track_b_detached_v1_replay") => std::process::exit(20),
            Some("track_b_detached_v1_scope_collision") => std::process::exit(21),
            Some(_) => std::process::exit(22),
        }
    }

    #[test]
    fn s7_real_processes_linearize_one_winner() {
        let directory = TestDirectory::new("processes");
        let path = directory.database();
        let barrier = directory.path.join("start");
        drop(provision_and_open_for_test(&path, GENERATION).expect("explicit provision"));
        const HELPER: &str = "temporal_replay_transport::durable_replay_registry::tests::s7_real_process_competition_helper";
        let mut children = Vec::new();
        for _ in 0..4 {
            let mut command = helper_command(HELPER, &path);
            command
                .env(MULTIPROCESS_HELPER_ENV, "1")
                .env("AB_S7_HELPER_BARRIER", &barrier);
            children.push(command.spawn().expect("spawn competition helper"));
        }
        std::fs::write(&barrier, b"go").expect("release child processes");
        let codes: Vec<Option<i32>> = children
            .into_iter()
            .map(|mut child| child.wait().expect("wait child").code())
            .collect();
        assert_eq!(codes.iter().filter(|code| **code == Some(0)).count(), 1);
        assert_eq!(codes.iter().filter(|code| **code == Some(20)).count(), 3);
    }

    #[test]
    #[ignore]
    fn s7_post_commit_sigkill_helper() {
        if std::env::var_os(CRASH_HELPER_ENV).is_none() {
            return;
        }
        let database = PathBuf::from(std::env::var_os("AB_S7_HELPER_DB").expect("helper DB"));
        let committed =
            PathBuf::from(std::env::var_os("AB_S7_HELPER_COMMITTED").expect("commit marker path"));
        let registry = open_for_test(&database, GENERATION).expect("crash helper open");
        registry
            .consume_once(request(0x51, 0x61))
            .expect("crash helper durable commit");
        std::fs::write(&committed, b"committed").expect("commit marker");
        loop {
            std::thread::park_timeout(Duration::from_secs(1));
        }
    }

    #[test]
    fn s7_sigkill_after_commit_preserves_the_tombstone() {
        let directory = TestDirectory::new("sigkill");
        let path = directory.database();
        let committed = directory.path.join("committed");
        drop(provision_and_open_for_test(&path, GENERATION).expect("explicit provision"));
        const HELPER: &str = "temporal_replay_transport::durable_replay_registry::tests::s7_post_commit_sigkill_helper";
        let mut command = helper_command(HELPER, &path);
        command
            .env(CRASH_HELPER_ENV, "1")
            .env("AB_S7_HELPER_COMMITTED", &committed);
        let mut child = command.spawn().expect("spawn crash helper");
        let deadline = std::time::Instant::now() + Duration::from_secs(10);
        while !committed.exists() {
            assert!(
                std::time::Instant::now() < deadline,
                "commit marker timeout"
            );
            std::thread::sleep(Duration::from_millis(5));
        }
        child.kill().expect("SIGKILL committed helper");
        let status = child.wait().expect("reap killed helper");
        assert!(!status.success());
        let reopened = open_for_test(&path, GENERATION).expect("open after SIGKILL");
        assert_eq!(
            error_code(reopened.consume_once(request(0x51, 0x61))),
            Some("track_b_detached_v1_replay")
        );
    }

    #[test]
    #[ignore]
    fn s7_precommit_sigkill_helper() {
        if std::env::var_os(PRECOMMIT_HELPER_ENV).is_none() {
            return;
        }
        let database = PathBuf::from(std::env::var_os("AB_S7_HELPER_DB").expect("helper DB"));
        let registry = open_for_test(&database, GENERATION).expect("pre-commit helper open");
        let _ = registry.consume_once(request(0x51, 0x61));
        std::process::exit(32);
    }

    #[test]
    fn s7_sigkill_before_commit_rolls_back_without_releasing_a_receipt() {
        let directory = TestDirectory::new("precommit-sigkill");
        let path = directory.database();
        let inserted = directory.path.join("inserted");
        drop(provision_and_open_for_test(&path, GENERATION).expect("explicit provision"));
        const HELPER: &str = "temporal_replay_transport::durable_replay_registry::tests::s7_precommit_sigkill_helper";
        let mut command = helper_command(HELPER, &path);
        command
            .env(PRECOMMIT_HELPER_ENV, "1")
            .env("AB_S7_PAUSE_BEFORE_COMMIT_MARKER", &inserted);
        let mut child = command.spawn().expect("spawn pre-commit helper");
        let deadline = std::time::Instant::now() + Duration::from_secs(10);
        while !inserted.exists() {
            assert!(
                std::time::Instant::now() < deadline,
                "pre-commit marker timeout"
            );
            std::thread::sleep(Duration::from_millis(5));
        }
        child.kill().expect("SIGKILL pre-commit helper");
        let status = child.wait().expect("reap killed helper");
        assert!(!status.success());

        let reopened = open_for_test(&path, GENERATION).expect("open after pre-commit SIGKILL");
        let receipt = reopened
            .consume_once(request(0x51, 0x61))
            .expect("uncommitted insert must roll back");
        assert!(receipt.durable);
    }
}
