//! SEPL P0 read-only resource-version lineage.
//!
//! P0 deliberately exposes no mutation API. The SQLite substrate can be
//! populated only by a future, separately admitted producer. This module only
//! validates and projects bounded lineage already present in the store.

use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use std::collections::BTreeSet;
use tokio_rusqlite::rusqlite;

pub const RESOURCE_LINEAGE_SCHEMA: &str = "agent_bridge.resource_lineage.v0";
pub const RESOURCE_LINEAGE_HASH_DOMAIN: &str = "agent-bridge/sepl/resource-version/v0";
pub const RESOURCE_LINEAGE_MAX_ROWS: u32 = 256;
const RESOURCE_LINEAGE_MIGRATION_META_KEY: &str = "resource_lineage.migration_sha256";

pub(crate) const RESOURCE_VERSIONS_SCHEMA: &str = r#"
CREATE TABLE IF NOT EXISTS resource_versions (
    resource_id               TEXT    NOT NULL CHECK (length(resource_id) BETWEEN 1 AND 512),
    resource_kind             TEXT    NOT NULL CHECK (resource_kind = 'agent_md'),
    version                    INTEGER NOT NULL CHECK (version >= 1),
    content_sha256             TEXT    NOT NULL CHECK (length(content_sha256) = 64),
    predecessor_version        INTEGER,
    predecessor_record_sha256  TEXT,
    observed_at                INTEGER NOT NULL CHECK (typeof(observed_at) = 'integer'),
    record_sha256              TEXT    NOT NULL CHECK (length(record_sha256) = 64),
    PRIMARY KEY (resource_id, version),
    CHECK (
        (predecessor_version IS NULL AND predecessor_record_sha256 IS NULL)
        OR
        (predecessor_version IS NOT NULL
         AND predecessor_version >= 1
         AND predecessor_version < version
         AND predecessor_record_sha256 IS NOT NULL
         AND length(predecessor_record_sha256) = 64)
    ),
    FOREIGN KEY (resource_id, predecessor_version)
        REFERENCES resource_versions(resource_id, version)
);
CREATE INDEX IF NOT EXISTS idx_resource_versions_latest
    ON resource_versions(resource_id, version DESC);
"#;

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct ResourceVersionRecord {
    pub resource_id: String,
    pub resource_kind: String,
    pub version: u64,
    pub content_sha256: String,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub predecessor_version: Option<u64>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub predecessor_record_sha256: Option<String>,
    pub observed_at: i64,
    pub record_sha256: String,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct ResourceLineageReport {
    pub schema: String,
    pub resource_id: String,
    pub status: String,
    pub records: Vec<ResourceVersionRecord>,
    pub violations: Vec<String>,
    pub truncated: bool,
    pub prefix_omitted: bool,
    pub substrate_available: bool,
    pub mutation_supported: bool,
    pub content_readback_verified: bool,
}

fn migration_sha256() -> String {
    let mut hasher = Sha256::new();
    update_framed(
        &mut hasher,
        b"agent-bridge/sepl/resource-lineage-migration/v0",
    );
    update_framed(&mut hasher, RESOURCE_VERSIONS_SCHEMA.as_bytes());
    hasher
        .finalize()
        .iter()
        .map(|byte| format!("{byte:02x}"))
        .collect()
}

fn schema_mismatch(message: impl Into<String>) -> rusqlite::Error {
    rusqlite::Error::InvalidParameterName(format!(
        "resource_versions schema mismatch: {}",
        message.into()
    ))
}

fn canonical_schema_sql(sql: &str) -> String {
    sql.split_whitespace()
        .collect::<Vec<_>>()
        .join(" ")
        .replace("CREATE TABLE IF NOT EXISTS", "CREATE TABLE")
        .replace("CREATE INDEX IF NOT EXISTS", "CREATE INDEX")
}

pub(crate) fn migrate_or_verify(connection: &rusqlite::Connection) -> rusqlite::Result<()> {
    let table_exists: bool = connection.query_row(
        "SELECT EXISTS(SELECT 1 FROM sqlite_master \
         WHERE type='table' AND name='resource_versions')",
        [],
        |row| row.get(0),
    )?;
    if !table_exists {
        connection.execute_batch(RESOURCE_VERSIONS_SCHEMA)?;
    }

    let mut statement = connection.prepare("PRAGMA table_info('resource_versions')")?;
    let columns = statement
        .query_map([], |row| {
            Ok((
                row.get::<_, String>(1)?,
                row.get::<_, String>(2)?,
                row.get::<_, i64>(3)?,
                row.get::<_, i64>(5)?,
            ))
        })?
        .collect::<rusqlite::Result<Vec<_>>>()?;
    let expected = vec![
        ("resource_id".to_string(), "TEXT".to_string(), 1, 1),
        ("resource_kind".to_string(), "TEXT".to_string(), 1, 0),
        ("version".to_string(), "INTEGER".to_string(), 1, 2),
        ("content_sha256".to_string(), "TEXT".to_string(), 1, 0),
        (
            "predecessor_version".to_string(),
            "INTEGER".to_string(),
            0,
            0,
        ),
        (
            "predecessor_record_sha256".to_string(),
            "TEXT".to_string(),
            0,
            0,
        ),
        ("observed_at".to_string(), "INTEGER".to_string(), 1, 0),
        ("record_sha256".to_string(), "TEXT".to_string(), 1, 0),
    ];
    if columns != expected {
        return Err(schema_mismatch("column identity"));
    }

    let table_sql: String = connection.query_row(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='resource_versions'",
        [],
        |row| row.get(0),
    )?;
    let expected_table_sql = RESOURCE_VERSIONS_SCHEMA
        .split_once(';')
        .map(|(table, _)| table)
        .ok_or_else(|| schema_mismatch("embedded table DDL"))?;
    if canonical_schema_sql(&table_sql) != canonical_schema_sql(expected_table_sql) {
        return Err(schema_mismatch("table DDL identity"));
    }
    // The table identity is now proven, so it is safe to idempotently restore
    // the expected index if a partial first migration omitted only that index.
    connection.execute_batch(RESOURCE_VERSIONS_SCHEMA)?;
    let index_sql: String = connection.query_row(
        "SELECT sql FROM sqlite_master WHERE type='index' AND name='idx_resource_versions_latest'",
        [],
        |row| row.get(0),
    )?;
    let expected_index_sql = RESOURCE_VERSIONS_SCHEMA
        .split_once(';')
        .map(|(_, index)| index.trim().trim_end_matches(';'))
        .ok_or_else(|| schema_mismatch("embedded index DDL"))?;
    if canonical_schema_sql(&index_sql) != canonical_schema_sql(expected_index_sql) {
        return Err(schema_mismatch("index DDL identity"));
    }

    let expected_digest = migration_sha256();
    connection.execute(
        "INSERT OR IGNORE INTO schema_meta(key, value) VALUES (?1, ?2)",
        rusqlite::params![RESOURCE_LINEAGE_MIGRATION_META_KEY, expected_digest],
    )?;
    let stored_digest: String = connection.query_row(
        "SELECT value FROM schema_meta WHERE key=?1",
        [RESOURCE_LINEAGE_MIGRATION_META_KEY],
        |row| row.get(0),
    )?;
    if stored_digest != migration_sha256() {
        return Err(schema_mismatch("migration digest"));
    }
    Ok(())
}

pub fn unavailable_resource_lineage(resource_id: &str) -> ResourceLineageReport {
    ResourceLineageReport {
        schema: RESOURCE_LINEAGE_SCHEMA.to_string(),
        resource_id: resource_id.to_string(),
        status: "unavailable".to_string(),
        records: Vec::new(),
        violations: Vec::new(),
        truncated: false,
        prefix_omitted: false,
        substrate_available: false,
        mutation_supported: false,
        content_readback_verified: false,
    }
}

fn update_framed(hasher: &mut Sha256, value: &[u8]) {
    hasher.update((value.len() as u64).to_be_bytes());
    hasher.update(value);
}

pub fn resource_version_record_sha256(record: &ResourceVersionRecord) -> String {
    let mut hasher = Sha256::new();
    for value in [
        RESOURCE_LINEAGE_HASH_DOMAIN.as_bytes(),
        record.resource_id.as_bytes(),
        record.resource_kind.as_bytes(),
        record.version.to_string().as_bytes(),
        record.content_sha256.as_bytes(),
        record
            .predecessor_version
            .map(|value| value.to_string())
            .unwrap_or_default()
            .as_bytes(),
        record
            .predecessor_record_sha256
            .as_deref()
            .unwrap_or_default()
            .as_bytes(),
        record.observed_at.to_string().as_bytes(),
    ] {
        update_framed(&mut hasher, value);
    }
    hasher
        .finalize()
        .iter()
        .map(|byte| format!("{byte:02x}"))
        .collect()
}

fn is_lower_hex_sha256(value: &str) -> bool {
    value.len() == 64
        && value
            .bytes()
            .all(|byte| byte.is_ascii_digit() || (b'a'..=b'f').contains(&byte))
}

pub fn validate_resource_lineage(
    resource_id: &str,
    mut records: Vec<ResourceVersionRecord>,
    truncated: bool,
) -> ResourceLineageReport {
    records.sort_by(|left, right| left.version.cmp(&right.version));
    let mut violations = BTreeSet::new();
    let mut seen_versions = BTreeSet::new();

    for record in &records {
        if record.resource_id != resource_id {
            violations.insert(format!("resource_id_mismatch:version={}", record.version));
        }
        if record.resource_kind != "agent_md" {
            violations.insert(format!(
                "resource_kind_unsupported:version={}",
                record.version
            ));
        }
        if record.version == 0 || !seen_versions.insert(record.version) {
            violations.insert(format!(
                "version_invalid_or_duplicate:version={}",
                record.version
            ));
        }
        if !is_lower_hex_sha256(&record.content_sha256) {
            violations.insert(format!(
                "content_sha256_malformed:version={}",
                record.version
            ));
        }
        if !is_lower_hex_sha256(&record.record_sha256)
            || resource_version_record_sha256(record) != record.record_sha256
        {
            violations.insert(format!("record_sha256_mismatch:version={}", record.version));
        }
        if record.predecessor_version.is_some() != record.predecessor_record_sha256.is_some() {
            violations.insert(format!(
                "predecessor_binding_incomplete:version={}",
                record.version
            ));
        }
        if let Some(predecessor_version) = record.predecessor_version {
            if predecessor_version == 0 || predecessor_version >= record.version {
                violations.insert(format!(
                    "predecessor_version_invalid:version={}",
                    record.version
                ));
            }
        }
        if record
            .predecessor_record_sha256
            .as_deref()
            .is_some_and(|value| !is_lower_hex_sha256(value))
        {
            violations.insert(format!(
                "predecessor_sha256_malformed:version={}",
                record.version
            ));
        }
    }

    for pair in records.windows(2) {
        let predecessor = &pair[0];
        let successor = &pair[1];
        if successor.version != predecessor.version.saturating_add(1) {
            violations.insert(format!("version_gap:version={}", successor.version));
        }
        if successor.predecessor_version != Some(predecessor.version) {
            violations.insert(format!(
                "predecessor_version_mismatch:version={}",
                successor.version
            ));
        }
        if successor.predecessor_record_sha256.as_deref()
            != Some(predecessor.record_sha256.as_str())
        {
            violations.insert(format!(
                "predecessor_sha256_mismatch:version={}",
                successor.version
            ));
        }
    }

    let prefix_omitted = records
        .first()
        .is_some_and(|record| record.predecessor_version.is_some());
    if !truncated && prefix_omitted {
        violations.insert("predecessor_reference_missing_from_complete_lineage".to_string());
    }
    if !truncated && records.first().is_some_and(|record| record.version != 1) {
        violations.insert("genesis_version_missing".to_string());
    }

    let violations: Vec<_> = violations.into_iter().collect();
    let status = if !violations.is_empty() {
        "mismatch"
    } else if records.is_empty() {
        "empty"
    } else if truncated || prefix_omitted {
        "verified_bounded_suffix"
    } else {
        "verified"
    };

    ResourceLineageReport {
        schema: RESOURCE_LINEAGE_SCHEMA.to_string(),
        resource_id: resource_id.to_string(),
        status: status.to_string(),
        records,
        violations,
        truncated,
        prefix_omitted,
        substrate_available: true,
        mutation_supported: false,
        content_readback_verified: false,
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::{SqliteStore, StateStore};

    fn record(version: u64, predecessor: Option<&ResourceVersionRecord>) -> ResourceVersionRecord {
        let mut record = ResourceVersionRecord {
            resource_id: "agent-profile".to_string(),
            resource_kind: "agent_md".to_string(),
            version,
            content_sha256: format!("{:064x}", version + 10),
            predecessor_version: predecessor.map(|row| row.version),
            predecessor_record_sha256: predecessor.map(|row| row.record_sha256.clone()),
            observed_at: 1_700_000_000 + version as i64,
            record_sha256: String::new(),
        };
        record.record_sha256 = resource_version_record_sha256(&record);
        record
    }

    #[test]
    fn validates_complete_lineage_and_sorts_deterministically() {
        let first = record(1, None);
        let second = record(2, Some(&first));
        let report = validate_resource_lineage("agent-profile", vec![second, first], false);
        assert_eq!(report.status, "verified");
        assert!(report.violations.is_empty());
        assert_eq!(report.records[0].version, 1);
        assert!(!report.mutation_supported);
        assert!(!report.content_readback_verified);
    }

    #[test]
    fn rejects_hash_drift_and_broken_predecessor() {
        let first = record(1, None);
        let mut second = record(2, Some(&first));
        second.content_sha256 = "f".repeat(64);
        second.predecessor_record_sha256 = Some("a".repeat(64));
        let report = validate_resource_lineage("agent-profile", vec![first, second], false);
        assert_eq!(report.status, "mismatch");
        assert!(report
            .violations
            .iter()
            .any(|value| value == "record_sha256_mismatch:version=2"));
        assert!(report
            .violations
            .iter()
            .any(|value| value == "predecessor_sha256_mismatch:version=2"));
    }

    #[test]
    fn bounded_suffix_is_not_misreported_as_complete() {
        let first = record(1, None);
        let second = record(2, Some(&first));
        let report = validate_resource_lineage("agent-profile", vec![second], true);
        assert_eq!(report.status, "verified_bounded_suffix");
        assert!(report.prefix_omitted);
        assert!(report.violations.is_empty());
    }

    #[test]
    fn bounded_suffix_rejects_future_and_malformed_predecessor() {
        let mut row = record(2, None);
        row.predecessor_version = Some(3);
        row.predecessor_record_sha256 = Some("A".repeat(64));
        row.record_sha256 = resource_version_record_sha256(&row);
        let report = validate_resource_lineage("agent-profile", vec![row], true);
        assert_eq!(report.status, "mismatch");
        assert!(report
            .violations
            .iter()
            .any(|value| value == "predecessor_version_invalid:version=2"));
        assert!(report
            .violations
            .iter()
            .any(|value| value == "predecessor_sha256_malformed:version=2"));
    }

    #[tokio::test]
    async fn sqlite_migration_is_additive_and_read_path_is_honestly_empty() {
        let directory = tempfile::tempdir().expect("tempdir");
        let database = directory.path().join("state.db");
        let store = SqliteStore::open(&database).await.expect("open store");

        let report = store
            .resource_lineage_read("agent-profile", 32)
            .await
            .expect("read empty lineage");
        assert_eq!(report.status, "empty");
        assert!(report.records.is_empty());
        assert!(!report.mutation_supported);
        assert!(!report.content_readback_verified);

        drop(store);
        let connection = tokio_rusqlite::rusqlite::Connection::open(&database)
            .expect("inspect migrated database");
        let table_count: i64 = connection
            .query_row(
                "SELECT COUNT(*) FROM sqlite_master \
                 WHERE type='table' AND name='resource_versions'",
                [],
                |row| row.get(0),
            )
            .expect("query schema");
        assert_eq!(table_count, 1);
    }

    #[tokio::test]
    async fn concurrent_first_open_is_idempotent() {
        let directory = tempfile::tempdir().expect("tempdir");
        let database = directory.path().join("state.db");
        // The repository-wide bootstrap ladder is not guaranteed to support
        // two brand-new database opens at the same instant. Establish its base
        // schema first, remove only this additive rung, then race the P0 rung.
        let initial = SqliteStore::open(&database).await.expect("initial open");
        drop(initial);
        let connection = rusqlite::Connection::open(&database).expect("open raw database");
        connection
            .execute_batch(
                "DROP TABLE resource_versions;
                 DELETE FROM schema_meta WHERE key='resource_lineage.migration_sha256';",
            )
            .expect("rewind P0 rung");
        drop(connection);
        let (left, right) =
            tokio::join!(SqliteStore::open(&database), SqliteStore::open(&database));
        left.expect("left open");
        right.expect("right open");
    }

    #[tokio::test]
    async fn incompatible_existing_table_fails_closed() {
        let directory = tempfile::tempdir().expect("tempdir");
        let database = directory.path().join("state.db");
        let initial = SqliteStore::open(&database).await.expect("initial open");
        drop(initial);
        let connection = rusqlite::Connection::open(&database).expect("open raw database");
        connection
            .execute_batch(
                "DROP TABLE resource_versions;
                 DELETE FROM schema_meta WHERE key='resource_lineage.migration_sha256';
                 CREATE TABLE resource_versions (resource_id TEXT PRIMARY KEY);",
            )
            .expect("install incompatible table");
        drop(connection);

        let error = SqliteStore::open(&database)
            .await
            .err()
            .expect("incompatible table must fail");
        assert!(error
            .to_string()
            .contains("resource_versions schema mismatch"));
    }

    #[tokio::test]
    async fn same_columns_without_constraints_fail_closed() {
        let directory = tempfile::tempdir().expect("tempdir");
        let database = directory.path().join("state.db");
        let initial = SqliteStore::open(&database).await.expect("initial open");
        drop(initial);
        let connection = rusqlite::Connection::open(&database).expect("open raw database");
        connection
            .execute_batch(
                "DROP TABLE resource_versions;
                 DELETE FROM schema_meta WHERE key='resource_lineage.migration_sha256';
                 CREATE TABLE resource_versions (
                     resource_id TEXT NOT NULL,
                     resource_kind TEXT NOT NULL,
                     version INTEGER NOT NULL,
                     content_sha256 TEXT NOT NULL,
                     predecessor_version INTEGER,
                     predecessor_record_sha256 TEXT,
                     observed_at INTEGER NOT NULL,
                     record_sha256 TEXT NOT NULL,
                     PRIMARY KEY (resource_id, version)
                 );",
            )
            .expect("install same-column unconstrained table");
        drop(connection);

        let error = SqliteStore::open(&database)
            .await
            .err()
            .expect("constraint drift must fail");
        assert!(error.to_string().contains("table DDL identity"));
    }

    #[tokio::test]
    async fn read_only_legacy_database_reports_substrate_unavailable() {
        let directory = tempfile::tempdir().expect("tempdir");
        let database = directory.path().join("state.db");
        let initial = SqliteStore::open(&database).await.expect("initial open");
        drop(initial);
        let connection = rusqlite::Connection::open(&database).expect("open raw database");
        connection
            .execute_batch(
                "DROP TABLE resource_versions;
                 DELETE FROM schema_meta WHERE key='resource_lineage.migration_sha256';",
            )
            .expect("rewind P0 rung");
        drop(connection);

        let store = SqliteStore::open_read_only(&database)
            .await
            .expect("open legacy database read-only");
        let report = store
            .resource_lineage_read("agent-profile", 32)
            .await
            .expect("read unavailable lineage");
        assert_eq!(report.status, "unavailable");
        assert!(!report.substrate_available);
        assert!(report.records.is_empty());
    }

    #[tokio::test]
    async fn read_limit_is_clamped_and_returns_latest_bounded_suffix() {
        let directory = tempfile::tempdir().expect("tempdir");
        let database = directory.path().join("state.db");
        let initial = SqliteStore::open(&database).await.expect("initial open");
        drop(initial);

        let first = record(1, None);
        let second = record(2, Some(&first));
        let third = record(3, Some(&second));
        let mut connection = rusqlite::Connection::open(&database).expect("open raw database");
        let transaction = connection.transaction().expect("transaction");
        for row in [&first, &second, &third] {
            transaction
                .execute(
                    "INSERT INTO resource_versions(
                         resource_id, resource_kind, version, content_sha256,
                         predecessor_version, predecessor_record_sha256,
                         observed_at, record_sha256
                     ) VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7, ?8)",
                    rusqlite::params![
                        row.resource_id,
                        row.resource_kind,
                        row.version as i64,
                        row.content_sha256,
                        row.predecessor_version.map(|value| value as i64),
                        row.predecessor_record_sha256,
                        row.observed_at,
                        row.record_sha256,
                    ],
                )
                .expect("insert lineage row");
        }
        transaction.commit().expect("commit fixture");
        drop(connection);

        let store = SqliteStore::open_read_only(&database)
            .await
            .expect("open read-only");
        let one = store
            .resource_lineage_read("agent-profile", 0)
            .await
            .expect("clamp zero to one");
        assert_eq!(one.status, "verified_bounded_suffix");
        assert_eq!(one.records.len(), 1);
        assert_eq!(one.records[0].version, 3);

        let all = store
            .resource_lineage_read("agent-profile", RESOURCE_LINEAGE_MAX_ROWS + 1)
            .await
            .expect("clamp above maximum");
        assert_eq!(all.status, "verified");
        assert_eq!(all.records.len(), 3);
    }
}
