//! Synthetic-only temporal evidence substrate (schema v43).
//!
//! This module deliberately has no `StateStore`, Bridge, MCP, or adapter
//! surface. Writes require a token that can only be constructed by this
//! module's unit tests. The additive schema and exact identity verifier are
//! active in normal builds so a later adapter review cannot infer capability
//! merely from table presence.

// S2 deliberately has no production writer, adapter, or snapshot caller. The
// dormant internal model becomes reachable only in this module's synthetic
// tests; a later adapter requires a separate review.
#![allow(dead_code)]

use super::{RusqliteResult, SqliteStore};
use ab_core::{Error, Result};
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use std::collections::{BTreeMap, BTreeSet, HashMap, HashSet};
use std::io::{self, Write};
use tokio_rusqlite::rusqlite::OptionalExtension;
use tokio_rusqlite::{params, rusqlite};

const TEMPORAL_EVIDENCE_SCHEMA_VERSION: &str = "43";
const TEMPORAL_EVIDENCE_LEDGER_FORMAT_VERSION: &str = "0";
const SCHEMA_DIGEST_META_KEY: &str = "truth_evidence.schema_sha256";
const MIGRATION_DIGEST_META_KEY: &str = "truth_evidence.migration_sha256";
const LEDGER_FORMAT_META_KEY: &str = "truth_evidence.ledger_format_version";
const ATTESTATION_VERSION: &str = "content_free_governance_v0";
const CANONICAL_ORDER: &str = "binary_utf8_v0";
const MAX_LABEL_BYTES: usize = 512;
const MAX_VALUE_BYTES: usize = 262_144;
const MAX_LINEAGES: usize = 10_000;
const MAX_POLICY_REVISIONS: usize = 10_000;
const MAX_EVIDENCE_REVISIONS: usize = 10_000;
const MAX_RELATIONSHIPS: usize = 50_000;
const MAX_TOMBSTONES: usize = 10_000;
const MAX_PAYLOAD_BYTES: usize = 16 * 1024 * 1024;
const MAX_SCHEMA_OBJECTS: i64 = 128;
const MAX_SCHEMA_MANIFEST_BYTES: i64 = 1024 * 1024;
const INPUT_JSON_EXPANSION_FACTOR: usize = 8;

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
enum TemporalEvidenceErrorKind {
    InvalidInput,
    Conflict,
    Integrity,
    Capacity,
    SchemaIdentity,
    Connection,
}

#[derive(Debug, thiserror::Error)]
#[error("{code}: {detail}")]
struct TemporalEvidenceRejection {
    code: &'static str,
    detail: String,
}

#[derive(Debug, thiserror::Error)]
#[error("{operation}: {code}: {detail}")]
struct TemporalEvidenceStoreError {
    kind: TemporalEvidenceErrorKind,
    code: String,
    operation: String,
    detail: String,
}

type TemporalEvidenceStoreResult<T> = std::result::Result<T, TemporalEvidenceStoreError>;

impl TemporalEvidenceStoreError {
    fn from_validation(operation: &str, error: Error) -> Self {
        let (message, fallback) = match error {
            Error::Backend(message) | Error::InvalidArgument(message) => {
                (message, "truth_evidence_invalid_input")
            }
            Error::Serde(error) => (error.to_string(), "truth_evidence_json"),
            other => (other.to_string(), "truth_evidence_invalid_input"),
        };
        let code = message
            .split(':')
            .next()
            .unwrap_or(fallback)
            .trim()
            .to_string();
        let code = if code.starts_with("truth_evidence_") {
            code
        } else {
            fallback.to_string()
        };
        Self {
            kind: classify_rejection(&code),
            code,
            operation: operation.to_string(),
            detail: message,
        }
    }

    fn from_rusqlite(operation: &str, error: rusqlite::Error) -> Self {
        if let rusqlite::Error::FromSqlConversionFailure(_, _, source) = &error {
            if let Some(rejection) = source.downcast_ref::<TemporalEvidenceRejection>() {
                return Self {
                    kind: classify_rejection(rejection.code),
                    code: rejection.code.to_string(),
                    operation: operation.to_string(),
                    detail: rejection.detail.clone(),
                };
            }
        }
        let (kind, code) = match &error {
            rusqlite::Error::SqliteFailure(inner, _)
                if inner.code == rusqlite::ErrorCode::ConstraintViolation =>
            {
                (
                    TemporalEvidenceErrorKind::Conflict,
                    "truth_evidence_sql_constraint",
                )
            }
            rusqlite::Error::SqliteFailure(_, _) => (
                TemporalEvidenceErrorKind::Integrity,
                "truth_evidence_sqlite",
            ),
            _ => (
                TemporalEvidenceErrorKind::Integrity,
                "truth_evidence_integrity",
            ),
        };
        Self {
            kind,
            code: code.to_string(),
            operation: operation.to_string(),
            detail: error.to_string(),
        }
    }

    fn from_call(operation: &str, error: tokio_rusqlite::Error) -> Self {
        match error {
            tokio_rusqlite::Error::ConnectionClosed => Self {
                kind: TemporalEvidenceErrorKind::Connection,
                code: "truth_evidence_connection_closed".into(),
                operation: operation.to_string(),
                detail: "SQLite worker connection closed".into(),
            },
            tokio_rusqlite::Error::Close((_, error)) | tokio_rusqlite::Error::Error(error) => {
                Self::from_rusqlite(operation, error)
            }
            _ => Self {
                kind: TemporalEvidenceErrorKind::Connection,
                code: "truth_evidence_connection".into(),
                operation: operation.to_string(),
                detail: "unrecognized SQLite worker failure".into(),
            },
        }
    }

    #[cfg(test)]
    fn code(&self) -> &str {
        &self.code
    }

    #[cfg(test)]
    fn kind(&self) -> TemporalEvidenceErrorKind {
        self.kind
    }
}

fn classify_rejection(code: &str) -> TemporalEvidenceErrorKind {
    match code {
        "truth_evidence_identity"
        | "truth_evidence_migration"
        | "truth_evidence_migration_backfill"
        | "truth_evidence_migration_collision" => TemporalEvidenceErrorKind::SchemaIdentity,
        "truth_evidence_input_capacity"
        | "truth_evidence_sequence_overflow"
        | "truth_evidence_snapshot_payload"
        | "truth_evidence_snapshot_truncated" => TemporalEvidenceErrorKind::Capacity,
        "truth_evidence_invalid_digest"
        | "truth_evidence_invalid_input"
        | "truth_evidence_invalid_label"
        | "truth_evidence_invalid_lifecycle"
        | "truth_evidence_invalid_policy"
        | "truth_evidence_invalid_time"
        | "truth_evidence_invalid_validity"
        | "truth_evidence_invalid_value"
        | "truth_evidence_json"
        | "truth_evidence_json_utf8"
        | "truth_evidence_missing_provenance"
        | "truth_evidence_dual_relationship"
        | "truth_evidence_noncanonical_aliases"
        | "truth_evidence_noncanonical_provenance"
        | "truth_evidence_noncanonical_relationships"
        | "truth_evidence_observation_after_recording"
        | "truth_evidence_snapshot_limit" => TemporalEvidenceErrorKind::InvalidInput,
        "truth_evidence_authority_policy_inactive"
        | "truth_evidence_authority_predicate_fallback"
        | "truth_evidence_authority_source_mismatch"
        | "truth_evidence_cross_claim_relationship"
        | "truth_evidence_dropped_relationship"
        | "truth_evidence_lineage_identity_drift"
        | "truth_evidence_lower_tier_suppression"
        | "truth_evidence_policy_identity_drift"
        | "truth_evidence_policy_not_latest_visible"
        | "truth_evidence_policy_tier_shopping"
        | "truth_evidence_policy_time_regression"
        | "truth_evidence_recorded_at_regression"
        | "truth_evidence_relationship_cycle"
        | "truth_evidence_relationship_outside_source_activity"
        | "truth_evidence_relationship_target_not_visible"
        | "truth_evidence_revision_predates_lineage"
        | "truth_evidence_same_second_target_ambiguity"
        | "truth_evidence_self_relationship"
        | "truth_evidence_sql_constraint"
        | "truth_evidence_tombstoned_lineage"
        | "truth_evidence_unknown_authority_policy" => TemporalEvidenceErrorKind::Conflict,
        _ => TemporalEvidenceErrorKind::Integrity,
    }
}

// Filled from the canonical sqlite_master manifest produced by the exact DDL
// below. `verify_v43` independently regenerates the live manifest; this is not
// a digest copied back out of schema_meta.
const EXPECTED_SCHEMA_SHA256: &str =
    "6d321d45aafe65ef06efb49c46ccf9f1931624aada9e8873d7e29765826e3aa0";

const MIGRATION_MANIFEST: &str = concat!(
    "agent_bridge.sqlite.temporal_evidence_migration.v0\n",
    "from=42\n",
    "to=43\n",
    "transaction=immediate\n",
    "legacy_backfill=forbidden\n",
    "ledger_format=0\n",
    "schema_manifest=sqlite_master_truth_scope_normalized_v1\n",
    "identifier_scope=sqlite_ascii_lower_v0\n",
    "runtime_table_namespace=main\n",
    "reserved_temp_objects=forbidden\n",
);

const SCHEMA_V43_TEMPORAL_EVIDENCE: &str = r#"
CREATE TABLE IF NOT EXISTS truth_lineages (
    lineage_id            TEXT    PRIMARY KEY,
    referent_id           TEXT    NOT NULL,
    predicate_id          TEXT    NOT NULL,
    created_at            INTEGER NOT NULL,
    claim_identity_sha256 TEXT    NOT NULL,
    CHECK (length(CAST(lineage_id AS BLOB)) BETWEEN 1 AND 512),
    CHECK (length(CAST(referent_id AS BLOB)) BETWEEN 1 AND 512),
    CHECK (length(CAST(predicate_id AS BLOB)) BETWEEN 1 AND 512),
    CHECK (typeof(created_at) = 'integer' AND created_at >= 0),
    CHECK (length(claim_identity_sha256) = 64
       AND claim_identity_sha256 NOT GLOB '*[^0-9a-f]*')
);
CREATE INDEX IF NOT EXISTS idx_truth_lineages_claim
    ON truth_lineages(referent_id COLLATE BINARY, predicate_id COLLATE BINARY,
                      lineage_id COLLATE BINARY);

CREATE TABLE IF NOT EXISTS truth_authority_policy_revisions (
    policy_revision_id  TEXT    PRIMARY KEY,
    policy_lineage_id   TEXT    NOT NULL,
    revision_seq        INTEGER NOT NULL,
    recorded_at         INTEGER NOT NULL,
    predicate_id        TEXT    NOT NULL,
    source_key          TEXT    NOT NULL,
    resolved_truth_tier TEXT    NOT NULL,
    valid_from          INTEGER,
    valid_until         INTEGER,
    status              TEXT    NOT NULL,
    UNIQUE (policy_lineage_id, revision_seq),
    UNIQUE (policy_lineage_id, recorded_at),
    CHECK (length(CAST(policy_revision_id AS BLOB)) BETWEEN 1 AND 512),
    CHECK (length(CAST(policy_lineage_id AS BLOB)) BETWEEN 1 AND 512),
    CHECK (typeof(revision_seq) = 'integer' AND revision_seq >= 1),
    CHECK (typeof(recorded_at) = 'integer' AND recorded_at >= 0),
    CHECK (length(CAST(predicate_id AS BLOB)) BETWEEN 1 AND 512),
    CHECK (length(CAST(source_key AS BLOB)) BETWEEN 1 AND 512),
    CHECK (resolved_truth_tier IN ('inferred','observed','verified','authoritative')),
    CHECK (valid_from IS NULL OR (typeof(valid_from) = 'integer' AND valid_from >= 0)),
    CHECK (valid_until IS NULL OR (typeof(valid_until) = 'integer' AND valid_until >= 0)),
    CHECK (valid_from IS NULL OR valid_until IS NULL OR valid_from <= valid_until),
    CHECK (status IN ('active','revoked'))
);
CREATE INDEX IF NOT EXISTS idx_truth_authority_policy_lineage_time
    ON truth_authority_policy_revisions(
        policy_lineage_id COLLATE BINARY, recorded_at DESC, revision_seq DESC);
CREATE INDEX IF NOT EXISTS idx_truth_authority_policy_pair
    ON truth_authority_policy_revisions(
        predicate_id COLLATE BINARY, source_key COLLATE BINARY,
        policy_lineage_id COLLATE BINARY);

CREATE TABLE IF NOT EXISTS truth_evidence_revisions (
    evidence_id                 TEXT    PRIMARY KEY,
    lineage_id                  TEXT    NOT NULL,
    revision_seq                INTEGER NOT NULL,
    value                       TEXT    NOT NULL,
    aliases                     TEXT    NOT NULL,
    observed_at                 INTEGER NOT NULL,
    recorded_at                 INTEGER NOT NULL,
    validity                    TEXT    NOT NULL,
    lifecycle                   TEXT    NOT NULL,
    source_bindings             TEXT    NOT NULL,
    authority_policy_revision_id TEXT   NOT NULL,
    resolved_truth_tier         TEXT    NOT NULL,
    UNIQUE (lineage_id, revision_seq),
    UNIQUE (lineage_id, recorded_at),
    FOREIGN KEY (lineage_id) REFERENCES truth_lineages(lineage_id),
    FOREIGN KEY (authority_policy_revision_id)
        REFERENCES truth_authority_policy_revisions(policy_revision_id),
    CHECK (length(CAST(evidence_id AS BLOB)) BETWEEN 1 AND 512),
    CHECK (length(CAST(lineage_id AS BLOB)) BETWEEN 1 AND 512),
    CHECK (typeof(revision_seq) = 'integer' AND revision_seq >= 1),
    CHECK (length(CAST(value AS BLOB)) BETWEEN 1 AND 262144),
    CHECK (json_valid(aliases) AND json_type(aliases) = 'array'),
    CHECK (typeof(observed_at) = 'integer' AND observed_at >= 0),
    CHECK (typeof(recorded_at) = 'integer' AND recorded_at >= 0
       AND observed_at <= recorded_at),
    CHECK (json_valid(validity) AND json_type(validity) = 'object'),
    CHECK (json_valid(lifecycle) AND json_type(lifecycle) = 'object'),
    CHECK (json_valid(source_bindings) AND json_type(source_bindings) = 'array'),
    CHECK (resolved_truth_tier IN ('inferred','observed','verified','authoritative'))
);
CREATE INDEX IF NOT EXISTS idx_truth_evidence_lineage_time
    ON truth_evidence_revisions(
        lineage_id COLLATE BINARY, recorded_at DESC, revision_seq DESC);
CREATE INDEX IF NOT EXISTS idx_truth_evidence_policy
    ON truth_evidence_revisions(authority_policy_revision_id COLLATE BINARY);

CREATE TABLE IF NOT EXISTS truth_evidence_relationships (
    declared_evidence_id TEXT    NOT NULL,
    relationship_kind    TEXT    NOT NULL,
    target_lineage_id    TEXT    NOT NULL,
    effective_from       INTEGER NOT NULL,
    PRIMARY KEY (
        declared_evidence_id, relationship_kind,
        target_lineage_id, effective_from
    ),
    UNIQUE (declared_evidence_id, target_lineage_id),
    FOREIGN KEY (declared_evidence_id)
        REFERENCES truth_evidence_revisions(evidence_id),
    FOREIGN KEY (target_lineage_id) REFERENCES truth_lineages(lineage_id),
    CHECK (relationship_kind IN ('supersedes','invalidates')),
    CHECK (typeof(effective_from) = 'integer' AND effective_from >= 0)
);
CREATE INDEX IF NOT EXISTS idx_truth_relationship_target
    ON truth_evidence_relationships(
        target_lineage_id COLLATE BINARY, declared_evidence_id COLLATE BINARY);

CREATE TABLE IF NOT EXISTS truth_lineage_tombstones (
    tombstone_id            TEXT    PRIMARY KEY,
    lineage_id              TEXT    NOT NULL UNIQUE,
    tombstoned_at           INTEGER NOT NULL,
    had_outgoing_governance INTEGER NOT NULL,
    attestation_version     TEXT    NOT NULL,
    attestation_sha256      TEXT    NOT NULL,
    FOREIGN KEY (lineage_id) REFERENCES truth_lineages(lineage_id),
    CHECK (length(CAST(tombstone_id AS BLOB)) BETWEEN 1 AND 512),
    CHECK (typeof(tombstoned_at) = 'integer' AND tombstoned_at >= 0),
    CHECK (had_outgoing_governance IN (0,1)),
    CHECK (attestation_version = 'content_free_governance_v0'),
    CHECK (length(attestation_sha256) = 64
       AND attestation_sha256 NOT GLOB '*[^0-9a-f]*')
);

CREATE TRIGGER IF NOT EXISTS truth_lineages_append_only_update
BEFORE UPDATE ON truth_lineages BEGIN
    SELECT RAISE(ABORT, 'truth_lineages is append-only');
END;
CREATE TRIGGER IF NOT EXISTS truth_lineages_append_only_delete
BEFORE DELETE ON truth_lineages BEGIN
    SELECT RAISE(ABORT, 'truth_lineages is append-only');
END;
CREATE TRIGGER IF NOT EXISTS truth_authority_policy_revisions_append_only_update
BEFORE UPDATE ON truth_authority_policy_revisions BEGIN
    SELECT RAISE(ABORT, 'truth_authority_policy_revisions is append-only');
END;
CREATE TRIGGER IF NOT EXISTS truth_authority_policy_revisions_append_only_delete
BEFORE DELETE ON truth_authority_policy_revisions BEGIN
    SELECT RAISE(ABORT, 'truth_authority_policy_revisions is append-only');
END;
CREATE TRIGGER IF NOT EXISTS truth_evidence_revisions_append_only_update
BEFORE UPDATE ON truth_evidence_revisions BEGIN
    SELECT RAISE(ABORT, 'truth_evidence_revisions is append-only');
END;
CREATE TRIGGER IF NOT EXISTS truth_evidence_revisions_append_only_delete
BEFORE DELETE ON truth_evidence_revisions BEGIN
    SELECT RAISE(ABORT, 'truth_evidence_revisions is append-only');
END;
CREATE TRIGGER IF NOT EXISTS truth_evidence_relationships_append_only_update
BEFORE UPDATE ON truth_evidence_relationships BEGIN
    SELECT RAISE(ABORT, 'truth_evidence_relationships is append-only');
END;
CREATE TRIGGER IF NOT EXISTS truth_evidence_relationships_append_only_delete
BEFORE DELETE ON truth_evidence_relationships BEGIN
    SELECT RAISE(ABORT, 'truth_evidence_relationships is append-only');
END;
CREATE TRIGGER IF NOT EXISTS truth_lineage_tombstones_append_only_update
BEFORE UPDATE ON truth_lineage_tombstones BEGIN
    SELECT RAISE(ABORT, 'truth_lineage_tombstones is append-only');
END;
CREATE TRIGGER IF NOT EXISTS truth_lineage_tombstones_append_only_delete
BEFORE DELETE ON truth_lineage_tombstones BEGIN
    SELECT RAISE(ABORT, 'truth_lineage_tombstones is append-only');
END;

CREATE TRIGGER IF NOT EXISTS truth_authority_policy_identity_guard_insert
BEFORE INSERT ON truth_authority_policy_revisions
WHEN EXISTS (
    SELECT 1 FROM truth_authority_policy_revisions p
     WHERE p.predicate_id = NEW.predicate_id
       AND p.source_key = NEW.source_key
       AND p.policy_lineage_id != NEW.policy_lineage_id
)
BEGIN
    SELECT RAISE(ABORT, 'truth authority predicate/source pair already has a lineage');
END;

CREATE TRIGGER IF NOT EXISTS truth_authority_policy_sequence_guard_insert
BEFORE INSERT ON truth_authority_policy_revisions
WHEN NEW.revision_seq != COALESCE((
         SELECT MAX(p.revision_seq) + 1
           FROM truth_authority_policy_revisions p
          WHERE p.policy_lineage_id = NEW.policy_lineage_id
     ), 1)
  OR EXISTS (
         SELECT 1 FROM truth_authority_policy_revisions p
          WHERE p.policy_lineage_id = NEW.policy_lineage_id
            AND (p.predicate_id != NEW.predicate_id
              OR p.source_key != NEW.source_key
              OR p.recorded_at >= NEW.recorded_at)
     )
BEGIN
    SELECT RAISE(ABORT, 'truth authority policy lineage sequence or identity drift');
END;

CREATE TRIGGER IF NOT EXISTS truth_evidence_revision_guard_insert
BEFORE INSERT ON truth_evidence_revisions
WHEN EXISTS (
         SELECT 1 FROM truth_lineage_tombstones t
          WHERE t.lineage_id = NEW.lineage_id
     )
  OR NEW.revision_seq != COALESCE((
         SELECT MAX(e.revision_seq) + 1
           FROM truth_evidence_revisions e
          WHERE e.lineage_id = NEW.lineage_id
     ), 1)
  OR EXISTS (
         SELECT 1 FROM truth_evidence_revisions e
          WHERE e.lineage_id = NEW.lineage_id
            AND e.recorded_at >= NEW.recorded_at
     )
  OR NOT EXISTS (
         SELECT 1
           FROM truth_lineages l
           JOIN truth_authority_policy_revisions p
             ON p.policy_revision_id = NEW.authority_policy_revision_id
          WHERE l.lineage_id = NEW.lineage_id
            AND l.created_at <= NEW.recorded_at
            AND p.predicate_id = l.predicate_id
            AND p.status = 'active'
            AND p.recorded_at <= NEW.recorded_at
            AND (p.valid_from IS NULL OR p.valid_from <= NEW.recorded_at)
            AND (p.valid_until IS NULL OR p.valid_until >= NEW.recorded_at)
            AND p.resolved_truth_tier = NEW.resolved_truth_tier
            AND EXISTS (
                  SELECT 1 FROM json_each(NEW.source_bindings) b
                   WHERE json_extract(b.value, '$.source_key') = p.source_key
                )
            AND p.policy_revision_id = (
                  SELECT p2.policy_revision_id
                    FROM truth_authority_policy_revisions p2
                   WHERE p2.policy_lineage_id = p.policy_lineage_id
                     AND p2.recorded_at <= NEW.recorded_at
                   ORDER BY p2.revision_seq DESC
                   LIMIT 1
                )
     )
BEGIN
    SELECT RAISE(ABORT, 'truth evidence revision admission guard rejected row');
END;

CREATE TRIGGER IF NOT EXISTS truth_evidence_relationship_guard_insert
BEFORE INSERT ON truth_evidence_relationships
WHEN EXISTS (
         SELECT 1
           FROM truth_evidence_revisions e
           JOIN truth_lineage_tombstones t ON t.lineage_id = e.lineage_id
          WHERE e.evidence_id = NEW.declared_evidence_id
     )
  OR EXISTS (
         SELECT 1
           FROM truth_evidence_revisions e
           JOIN truth_lineages s ON s.lineage_id = e.lineage_id
           JOIN truth_lineages t ON t.lineage_id = NEW.target_lineage_id
          WHERE e.evidence_id = NEW.declared_evidence_id
            AND (s.lineage_id = t.lineage_id
              OR s.referent_id != t.referent_id
              OR s.predicate_id != t.predicate_id)
     )
BEGIN
    SELECT RAISE(ABORT, 'truth evidence relationship endpoint guard rejected row');
END;

CREATE TRIGGER IF NOT EXISTS truth_lineage_tombstone_guard_insert
BEFORE INSERT ON truth_lineage_tombstones
WHEN NOT EXISTS (
         SELECT 1 FROM truth_evidence_revisions e
          WHERE e.lineage_id = NEW.lineage_id
     )
  OR NEW.tombstoned_at < COALESCE((
         SELECT MAX(e.recorded_at) FROM truth_evidence_revisions e
          WHERE e.lineage_id = NEW.lineage_id
     ), 0)
  OR NEW.had_outgoing_governance != EXISTS (
         SELECT 1
           FROM truth_evidence_relationships r
           JOIN truth_evidence_revisions e
             ON e.evidence_id = r.declared_evidence_id
          WHERE e.lineage_id = NEW.lineage_id
     )
BEGIN
    SELECT RAISE(ABORT, 'truth lineage tombstone governance guard rejected row');
END;
"#;

fn sql_reject(code: &'static str, detail: impl Into<String>) -> rusqlite::Error {
    rusqlite::Error::FromSqlConversionFailure(
        0,
        rusqlite::types::Type::Text,
        Box::new(TemporalEvidenceRejection {
            code,
            detail: detail.into(),
        }),
    )
}

fn sha256_hex(bytes: &[u8]) -> String {
    format!("{:x}", Sha256::digest(bytes))
}

fn migration_sha256() -> String {
    let mut hasher = Sha256::new();
    hasher.update(MIGRATION_MANIFEST.as_bytes());
    hasher.update(format!("schema_sha256={EXPECTED_SCHEMA_SHA256}\n").as_bytes());
    hasher.update(b"ddl_utf8_v0\n");
    hasher.update(SCHEMA_V43_TEMPORAL_EVIDENCE.as_bytes());
    format!("{:x}", hasher.finalize())
}

fn normalize_sql(sql: &str) -> String {
    sql.split_whitespace().collect::<Vec<_>>().join(" ")
}

fn live_schema_manifest(c: &rusqlite::Connection) -> RusqliteResult<String> {
    let (object_count, raw_bytes): (i64, i64) = c.query_row(
        "SELECT COUNT(*), COALESCE(SUM(
                    length(CAST(type AS BLOB))
                  + length(CAST(name AS BLOB))
                  + length(CAST(tbl_name AS BLOB))
                  + length(CAST(COALESCE(sql,'') AS BLOB)) + 4
                ),0)
           FROM main.sqlite_master
          WHERE lower(name) GLOB 'truth_*'
             OR lower(name) GLOB 'idx_truth_*'
             OR (
                    lower(tbl_name) IN (
                        'truth_lineages',
                        'truth_authority_policy_revisions',
                        'truth_evidence_revisions',
                        'truth_evidence_relationships',
                        'truth_lineage_tombstones'
                    )
                AND lower(name) NOT GLOB 'sqlite_autoindex_*'
             )",
        [],
        |row| Ok((row.get(0)?, row.get(1)?)),
    )?;
    if object_count < 0
        || object_count >= MAX_SCHEMA_OBJECTS
        || raw_bytes < 0
        || raw_bytes >= MAX_SCHEMA_MANIFEST_BYTES
    {
        return Err(sql_reject(
            "truth_evidence_identity",
            format!(
                "schema manifest preflight reached sentinel: objects={object_count}, bytes={raw_bytes}"
            ),
        ));
    }
    let mut stmt = c.prepare(
        "SELECT type, name, tbl_name, COALESCE(sql,'')
           FROM main.sqlite_master
          WHERE lower(name) GLOB 'truth_*'
             OR lower(name) GLOB 'idx_truth_*'
             OR (
                    lower(tbl_name) IN (
                        'truth_lineages',
                        'truth_authority_policy_revisions',
                        'truth_evidence_revisions',
                        'truth_evidence_relationships',
                        'truth_lineage_tombstones'
                    )
                AND lower(name) NOT GLOB 'sqlite_autoindex_*'
             )
          ORDER BY type COLLATE BINARY, name COLLATE BINARY",
    )?;
    let mut rows = stmt.query([])?;
    let mut manifest = String::from("sqlite_master_truth_scope_normalized_v1\n");
    while let Some(row) = rows.next()? {
        let object_type: String = row.get(0)?;
        let name: String = row.get(1)?;
        let table_name: String = row.get(2)?;
        let sql: String = row.get(3)?;
        manifest.push_str(&object_type);
        manifest.push('\t');
        manifest.push_str(&name);
        manifest.push('\t');
        manifest.push_str(&table_name);
        manifest.push('\t');
        manifest.push_str(&normalize_sql(&sql));
        manifest.push('\n');
    }
    Ok(manifest)
}

fn read_meta(c: &rusqlite::Connection, key: &str) -> RusqliteResult<Option<String>> {
    c.query_row(
        "SELECT value FROM main.schema_meta WHERE key=?1",
        params![key],
        |row| row.get(0),
    )
    .optional()
}

fn reserved_temp_object_count(c: &rusqlite::Connection) -> RusqliteResult<i64> {
    c.query_row(
        "SELECT COUNT(*) FROM sqlite_temp_master
          WHERE lower(name) GLOB 'truth_*'
             OR lower(name) GLOB 'idx_truth_*'
             OR lower(tbl_name) IN (
                    'truth_lineages',
                    'truth_authority_policy_revisions',
                    'truth_evidence_revisions',
                    'truth_evidence_relationships',
                    'truth_lineage_tombstones'
                )",
        [],
        |row| row.get(0),
    )
}

fn verify_v43_connection_at_versions(
    c: &rusqlite::Connection,
    allowed_versions: &[&str],
) -> RusqliteResult<()> {
    let reserved_temp_objects = reserved_temp_object_count(c)?;
    if reserved_temp_objects != 0 {
        return Err(sql_reject(
            "truth_evidence_identity",
            format!("reserved temporary objects={reserved_temp_objects}"),
        ));
    }
    let foreign_keys: i64 = c.query_row("PRAGMA foreign_keys", [], |row| row.get(0))?;
    if foreign_keys != 1 {
        return Err(sql_reject(
            "truth_evidence_identity",
            "PRAGMA foreign_keys must be enabled",
        ));
    }
    let version = read_meta(c, "version")?
        .ok_or_else(|| sql_reject("truth_evidence_identity", "schema_meta.version missing"))?;
    if !allowed_versions.iter().any(|allowed| version == *allowed) {
        return Err(sql_reject(
            "truth_evidence_identity",
            format!("expected schema version one of {allowed_versions:?}, got {version:?}"),
        ));
    }
    let manifest = live_schema_manifest(c)?;
    let live_digest = sha256_hex(manifest.as_bytes());
    if live_digest != EXPECTED_SCHEMA_SHA256 {
        return Err(sql_reject(
            "truth_evidence_identity",
            format!("live schema digest drifted to {live_digest}"),
        ));
    }
    let expected_meta = [
        (SCHEMA_DIGEST_META_KEY, EXPECTED_SCHEMA_SHA256.to_string()),
        (MIGRATION_DIGEST_META_KEY, migration_sha256()),
        (
            LEDGER_FORMAT_META_KEY,
            TEMPORAL_EVIDENCE_LEDGER_FORMAT_VERSION.to_string(),
        ),
    ];
    for (key, expected) in expected_meta {
        let actual = read_meta(c, key)?
            .ok_or_else(|| sql_reject("truth_evidence_identity", format!("{key} missing")))?;
        if actual != expected {
            return Err(sql_reject(
                "truth_evidence_identity",
                format!("{key} drifted"),
            ));
        }
    }
    let identity_row_count: i64 = c.query_row(
        "SELECT COUNT(*) FROM main.schema_meta WHERE key GLOB 'truth_evidence.*'",
        [],
        |row| row.get(0),
    )?;
    let unexpected_identity_rows: i64 = c.query_row(
        "SELECT COUNT(*) FROM main.schema_meta
          WHERE key GLOB 'truth_evidence.*'
            AND key NOT IN (?1,?2,?3)",
        params![
            SCHEMA_DIGEST_META_KEY,
            MIGRATION_DIGEST_META_KEY,
            LEDGER_FORMAT_META_KEY
        ],
        |row| row.get(0),
    )?;
    if identity_row_count != 3 || unexpected_identity_rows != 0 {
        return Err(sql_reject(
            "truth_evidence_identity",
            format!(
                "identity namespace rows={identity_row_count}, unexpected={unexpected_identity_rows}"
            ),
        ));
    }
    let foreign_key_violation: Option<String> = c
        .query_row(
            "SELECT \"table\" FROM pragma_foreign_key_check
              WHERE \"table\" IN (
                    'truth_lineages',
                    'truth_authority_policy_revisions',
                    'truth_evidence_revisions',
                    'truth_evidence_relationships',
                    'truth_lineage_tombstones'
              )
              LIMIT 1",
            [],
            |row| row.get(0),
        )
        .optional()?;
    if let Some(table) = foreign_key_violation {
        return Err(sql_reject(
            "truth_evidence_identity",
            format!("foreign key violation in {table}"),
        ));
    }
    Ok(())
}

fn verify_v43_connection(c: &rusqlite::Connection) -> RusqliteResult<()> {
    let mut accepted_versions = vec![TEMPORAL_EVIDENCE_SCHEMA_VERSION];
    #[cfg(feature = "episode-observation-slice-b")]
    accepted_versions.push("44");
    verify_v43_connection_at_versions(c, &accepted_versions)
}

fn accepted_schema_meta_version(version: &str) -> bool {
    version == TEMPORAL_EVIDENCE_SCHEMA_VERSION
        || (cfg!(feature = "episode-observation-slice-b") && version == "44")
}

/// Verify the v43 truth-evidence identity, optionally permitting one reviewed
/// downstream cursor. The truth manifest remains v43-scoped; this is a narrow
/// schema-owner handoff, not permission for arbitrary successor versions.
pub(super) fn migrate_or_verify_v43(
    c: &mut rusqlite::Connection,
    reviewed_successor_version: Option<&str>,
) -> RusqliteResult<()> {
    let tx = c.transaction_with_behavior(rusqlite::TransactionBehavior::Immediate)?;
    let version = read_meta(&tx, "version")?
        .ok_or_else(|| sql_reject("truth_evidence_migration", "schema_meta.version missing"))?;
    match version.as_str() {
        "42" => {
            let reserved_objects: i64 = tx.query_row(
                "SELECT COUNT(*) FROM main.sqlite_master
                  WHERE lower(name) GLOB 'truth_*'
                     OR lower(name) GLOB 'idx_truth_*'",
                [],
                |row| row.get(0),
            )?;
            let reserved_temp_objects = reserved_temp_object_count(&tx)?;
            let reserved_meta: i64 = tx.query_row(
                "SELECT COUNT(*) FROM main.schema_meta
                  WHERE key GLOB 'truth_evidence.*'",
                [],
                |row| row.get(0),
            )?;
            if reserved_objects != 0 || reserved_temp_objects != 0 || reserved_meta != 0 {
                return Err(sql_reject(
                    "truth_evidence_migration_collision",
                    format!(
                        "reserved objects={reserved_objects}, temporary objects={reserved_temp_objects}, identity rows={reserved_meta}"
                    ),
                ));
            }
            tx.execute_batch(SCHEMA_V43_TEMPORAL_EVIDENCE)?;
            let live_digest = sha256_hex(live_schema_manifest(&tx)?.as_bytes());
            if live_digest != EXPECTED_SCHEMA_SHA256 {
                return Err(sql_reject(
                    "truth_evidence_migration",
                    format!("compiled v43 schema digest is {live_digest}"),
                ));
            }
            tx.execute(
                "INSERT INTO main.schema_meta(key,value) VALUES(?1,?2)",
                params![SCHEMA_DIGEST_META_KEY, EXPECTED_SCHEMA_SHA256],
            )?;
            tx.execute(
                "INSERT INTO main.schema_meta(key,value) VALUES(?1,?2)",
                params![MIGRATION_DIGEST_META_KEY, migration_sha256()],
            )?;
            tx.execute(
                "INSERT INTO main.schema_meta(key,value) VALUES(?1,?2)",
                params![
                    LEDGER_FORMAT_META_KEY,
                    TEMPORAL_EVIDENCE_LEDGER_FORMAT_VERSION
                ],
            )?;
            let changed = tx.execute(
                "UPDATE main.schema_meta SET value='43' WHERE key='version' AND value='42'",
                [],
            )?;
            if changed != 1 {
                return Err(sql_reject(
                    "truth_evidence_migration",
                    "42->43 compare-and-set failed",
                ));
            }
            for table in [
                "truth_lineages",
                "truth_authority_policy_revisions",
                "truth_evidence_revisions",
                "truth_evidence_relationships",
                "truth_lineage_tombstones",
            ] {
                let count: i64 =
                    tx.query_row(&format!("SELECT COUNT(*) FROM main.{table}"), [], |row| {
                        row.get(0)
                    })?;
                if count != 0 {
                    return Err(sql_reject(
                        "truth_evidence_migration_backfill",
                        format!("{table} was not empty after migration"),
                    ));
                }
            }
            verify_v43_connection(&tx)?;
        }
        "43" => verify_v43_connection(&tx)?,
        other if reviewed_successor_version == Some(other) => {
            verify_v43_connection_at_versions(&tx, &[TEMPORAL_EVIDENCE_SCHEMA_VERSION, other])?
        }
        other => {
            return Err(sql_reject(
                "truth_evidence_migration",
                format!("unsupported schema version {other:?}"),
            ));
        }
    }
    tx.commit()?;
    Ok(())
}

fn verify_v43(c: &rusqlite::Connection) -> RusqliteResult<()> {
    verify_v43_connection(c)
}

/// Existing migration tests construct historical schemas by rewinding a
/// freshly-created database. They must first remove the additive v43 objects;
/// leaving a valid v43 ledger beside an older `schema_meta.version` is an
/// identity collision that production correctly rejects.
#[cfg(test)]
pub(super) fn expected_schema_meta_version_for_test() -> &'static str {
    if cfg!(feature = "episode-observation-slice-b") {
        "44"
    } else {
        "43"
    }
}

#[cfg(test)]
pub(super) fn remove_v43_for_legacy_migration_test(
    c: &mut rusqlite::Connection,
) -> RusqliteResult<()> {
    c.execute_batch("PRAGMA foreign_keys=ON;")?;
    verify_v43_connection(c)?;
    let tx = c.transaction_with_behavior(rusqlite::TransactionBehavior::Immediate)?;
    for table in [
        "truth_lineages",
        "truth_authority_policy_revisions",
        "truth_evidence_revisions",
        "truth_evidence_relationships",
        "truth_lineage_tombstones",
    ] {
        let count: i64 =
            tx.query_row(&format!("SELECT COUNT(*) FROM main.{table}"), [], |row| {
                row.get(0)
            })?;
        if count != 0 {
            return Err(sql_reject(
                "truth_evidence_test_rewind_nonempty",
                format!("refusing to remove {table} with {count} rows"),
            ));
        }
    }
    tx.execute_batch(
        "DROP TABLE main.truth_evidence_relationships;
         DROP TABLE main.truth_lineage_tombstones;
         DROP TABLE main.truth_evidence_revisions;
         DROP TABLE main.truth_authority_policy_revisions;
         DROP TABLE main.truth_lineages;
         DELETE FROM main.schema_meta WHERE key GLOB 'truth_evidence.*';
         DROP INDEX IF EXISTS main.idx_episode_observation_events_episode_id;
         DROP TABLE IF EXISTS main.episode_observation_events;",
    )?;
    tx.commit()?;
    Ok(())
}

#[derive(Debug)]
struct SyntheticTemporalEvidenceWriteToken {
    _private: (),
}

#[cfg(test)]
fn synthetic_write_token() -> SyntheticTemporalEvidenceWriteToken {
    SyntheticTemporalEvidenceWriteToken { _private: () }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
enum TruthTier {
    Inferred,
    Observed,
    Verified,
    Authoritative,
}

impl TruthTier {
    fn as_str(self) -> &'static str {
        match self {
            Self::Inferred => "inferred",
            Self::Observed => "observed",
            Self::Verified => "verified",
            Self::Authoritative => "authoritative",
        }
    }

    fn parse(value: &str) -> RusqliteResult<Self> {
        match value {
            "inferred" => Ok(Self::Inferred),
            "observed" => Ok(Self::Observed),
            "verified" => Ok(Self::Verified),
            "authoritative" => Ok(Self::Authoritative),
            other => Err(sql_reject(
                "truth_evidence_decode",
                format!("unknown truth tier {other:?}"),
            )),
        }
    }

    fn rank(self) -> u8 {
        match self {
            Self::Inferred => 0,
            Self::Observed => 1,
            Self::Verified => 2,
            Self::Authoritative => 3,
        }
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
enum PolicyStatus {
    Active,
    Revoked,
}

impl PolicyStatus {
    fn as_str(self) -> &'static str {
        match self {
            Self::Active => "active",
            Self::Revoked => "revoked",
        }
    }

    fn parse(value: &str) -> RusqliteResult<Self> {
        match value {
            "active" => Ok(Self::Active),
            "revoked" => Ok(Self::Revoked),
            other => Err(sql_reject(
                "truth_evidence_decode",
                format!("unknown policy status {other:?}"),
            )),
        }
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
enum RelationshipKind {
    Supersedes,
    Invalidates,
}

impl RelationshipKind {
    fn as_str(self) -> &'static str {
        match self {
            Self::Supersedes => "supersedes",
            Self::Invalidates => "invalidates",
        }
    }

    fn parse(value: &str) -> RusqliteResult<Self> {
        match value {
            "supersedes" => Ok(Self::Supersedes),
            "invalidates" => Ok(Self::Invalidates),
            other => Err(sql_reject(
                "truth_evidence_decode",
                format!("unknown relationship kind {other:?}"),
            )),
        }
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
enum ValidityKind {
    Timeless,
    Bounded,
    Indeterminate,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
struct EvidenceValidity {
    kind: ValidityKind,
    valid_from: Option<i64>,
    valid_until: Option<i64>,
}

impl EvidenceValidity {
    fn validate(&self) -> std::result::Result<(), String> {
        if self.valid_from.is_some_and(|value| value < 0)
            || self.valid_until.is_some_and(|value| value < 0)
        {
            return Err("validity bounds must be non-negative".into());
        }
        match self.kind {
            ValidityKind::Timeless | ValidityKind::Indeterminate
                if self.valid_from.is_some() || self.valid_until.is_some() =>
            {
                return Err("timeless/indeterminate validity cannot carry bounds".into());
            }
            ValidityKind::Bounded if self.valid_from.is_none() && self.valid_until.is_none() => {
                return Err("bounded validity needs at least one bound".into());
            }
            _ => {}
        }
        if let (Some(lower), Some(upper)) = (self.valid_from, self.valid_until) {
            if lower > upper {
                return Err("validity bounds are inverted".into());
            }
        }
        Ok(())
    }

    fn active_at(&self, timestamp: i64) -> bool {
        if self.kind == ValidityKind::Indeterminate {
            return false;
        }
        self.valid_from.is_none_or(|lower| timestamp >= lower)
            && self.valid_until.is_none_or(|upper| timestamp <= upper)
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
enum LifecycleState {
    Active,
    Superseded,
    Archived,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
struct EvidenceLifecycle {
    effective_from: Option<i64>,
    state: LifecycleState,
}

impl EvidenceLifecycle {
    fn validate(&self) -> std::result::Result<(), String> {
        match self.state {
            LifecycleState::Active if self.effective_from.is_some() => {
                Err("active lifecycle cannot carry effective_from".into())
            }
            LifecycleState::Superseded | LifecycleState::Archived
                if self.effective_from.is_none_or(|value| value < 0) =>
            {
                Err("non-active lifecycle requires non-negative effective_from".into())
            }
            _ => Ok(()),
        }
    }

    fn active_at(&self, timestamp: i64) -> bool {
        match self.state {
            LifecycleState::Active => true,
            LifecycleState::Superseded | LifecycleState::Archived => {
                timestamp < self.effective_from.unwrap_or(0)
            }
        }
    }
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
struct EvidenceSourceBinding {
    provenance_sha256: String,
    source_key: String,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
struct NewRelationship {
    relationship_kind: RelationshipKind,
    target_lineage_id: String,
    effective_from: i64,
}

#[derive(Debug, Clone)]
struct NewTruthLineage {
    lineage_id: String,
    referent_id: String,
    predicate_id: String,
    created_at: i64,
}

#[derive(Debug, Clone)]
struct NewAuthorityPolicyRevision {
    policy_revision_id: String,
    policy_lineage_id: String,
    recorded_at: i64,
    predicate_id: String,
    source_key: String,
    resolved_truth_tier: TruthTier,
    valid_from: Option<i64>,
    valid_until: Option<i64>,
    status: PolicyStatus,
}

#[derive(Debug, Clone)]
struct NewEvidenceRevision {
    evidence_id: String,
    lineage: NewTruthLineage,
    value: String,
    aliases: Vec<String>,
    observed_at: i64,
    recorded_at: i64,
    validity: EvidenceValidity,
    lifecycle: EvidenceLifecycle,
    source_bindings: Vec<EvidenceSourceBinding>,
    authority_policy_revision_id: String,
    relationships: Vec<NewRelationship>,
}

#[derive(Debug, Clone)]
struct NewLineageTombstone {
    tombstone_id: String,
    lineage_id: String,
    tombstoned_at: i64,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
struct TruthLineageRow {
    claim_identity_sha256: String,
    created_at: i64,
    lineage_id: String,
    predicate_id: String,
    referent_id: String,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
struct AuthorityPolicyRevisionRow {
    policy_lineage_id: String,
    policy_revision_id: String,
    predicate_id: String,
    recorded_at: i64,
    resolved_truth_tier: TruthTier,
    revision_seq: i64,
    source_key: String,
    status: PolicyStatus,
    valid_from: Option<i64>,
    valid_until: Option<i64>,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
struct EvidenceRevisionRow {
    aliases: Vec<String>,
    authority_policy_revision_id: String,
    evidence_id: String,
    lifecycle: EvidenceLifecycle,
    lineage_id: String,
    observed_at: i64,
    recorded_at: i64,
    resolved_truth_tier: TruthTier,
    revision_seq: i64,
    source_bindings: Vec<EvidenceSourceBinding>,
    validity: EvidenceValidity,
    value: String,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
struct EvidenceRelationshipRow {
    declared_evidence_id: String,
    effective_from: i64,
    relationship_kind: RelationshipKind,
    target_lineage_id: String,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
struct LineageTombstoneRow {
    attestation_sha256: String,
    attestation_version: String,
    had_outgoing_governance: bool,
    lineage_id: String,
    tombstone_id: String,
    tombstoned_at: i64,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
struct TemporalEvidenceSnapshotLimits {
    max_lineages: usize,
    max_policy_revisions: usize,
    max_evidence_revisions: usize,
    max_relationships: usize,
    max_tombstones: usize,
    max_payload_bytes: usize,
}

impl Default for TemporalEvidenceSnapshotLimits {
    fn default() -> Self {
        Self {
            max_lineages: 1_000,
            max_policy_revisions: 1_000,
            max_evidence_revisions: 1_000,
            max_relationships: 5_000,
            max_tombstones: 1_000,
            max_payload_bytes: 4 * 1024 * 1024,
        }
    }
}

impl TemporalEvidenceSnapshotLimits {
    fn validate(self) -> Result<Self> {
        let checks = [
            ("max_lineages", self.max_lineages, MAX_LINEAGES),
            (
                "max_policy_revisions",
                self.max_policy_revisions,
                MAX_POLICY_REVISIONS,
            ),
            (
                "max_evidence_revisions",
                self.max_evidence_revisions,
                MAX_EVIDENCE_REVISIONS,
            ),
            (
                "max_relationships",
                self.max_relationships,
                MAX_RELATIONSHIPS,
            ),
            ("max_tombstones", self.max_tombstones, MAX_TOMBSTONES),
            (
                "max_payload_bytes",
                self.max_payload_bytes,
                MAX_PAYLOAD_BYTES,
            ),
        ];
        if let Some((field, value, maximum)) = checks
            .into_iter()
            .find(|(_, value, maximum)| *value == 0 || *value > *maximum)
        {
            return Err(Error::Backend(format!(
                "truth_evidence_snapshot_limit: {field} must be in 1..={maximum}, got {value}"
            )));
        }
        Ok(self)
    }
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
struct TemporalEvidenceProducerIdentity {
    schema_meta_version: String,
    schema_digest: String,
    migration_digest: String,
    ledger_format_version: String,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
struct TemporalEvidenceSnapshotCounts {
    lineages: usize,
    policy_revisions: usize,
    evidence_revisions: usize,
    relationships: usize,
    tombstones: usize,
}

#[derive(Debug, Clone, PartialEq, Eq)]
struct TemporalEvidenceSnapshot {
    producer_identity: TemporalEvidenceProducerIdentity,
    ledger_format_version: u32,
    knowledge_cutoff: i64,
    limits: TemporalEvidenceSnapshotLimits,
    counts: TemporalEvidenceSnapshotCounts,
    lineages: Vec<TruthLineageRow>,
    authority_policies: Vec<AuthorityPolicyRevisionRow>,
    revisions: Vec<EvidenceRevisionRow>,
    relationships: Vec<EvidenceRelationshipRow>,
    tombstones: Vec<LineageTombstoneRow>,
    payload_bytes: usize,
    payload_sha256: String,
    canonical_order: &'static str,
}

fn validate_label(value: &str, field: &str) -> Result<()> {
    let byte_len = value.len();
    if value.is_empty()
        || value.trim() != value
        || byte_len > MAX_LABEL_BYTES
        || !value.is_ascii()
        || value.bytes().any(|byte| byte < 32 || byte == 127)
    {
        return Err(Error::Backend(format!(
            "truth_evidence_invalid_label: {field} is empty, padded, non-printable, non-ASCII, or oversized"
        )));
    }
    Ok(())
}

fn validate_timestamp(value: i64, field: &str) -> Result<()> {
    if value < 0 {
        return Err(Error::Backend(format!(
            "truth_evidence_invalid_time: {field} must be non-negative"
        )));
    }
    Ok(())
}

fn validate_digest(value: &str, field: &str) -> Result<()> {
    if value.len() != 64
        || !value
            .bytes()
            .all(|byte| byte.is_ascii_digit() || (b'a'..=b'f').contains(&byte))
    {
        return Err(Error::Backend(format!(
            "truth_evidence_invalid_digest: {field} must be 64 lowercase hex characters"
        )));
    }
    Ok(())
}

fn write_canonical_json(value: &serde_json::Value, out: &mut Vec<u8>) -> Result<()> {
    match value {
        serde_json::Value::Null => out.extend_from_slice(b"null"),
        serde_json::Value::Bool(true) => out.extend_from_slice(b"true"),
        serde_json::Value::Bool(false) => out.extend_from_slice(b"false"),
        serde_json::Value::Number(number) => out.extend_from_slice(number.to_string().as_bytes()),
        serde_json::Value::String(text) => out.extend_from_slice(
            serde_json::to_string(text)
                .map_err(|error| Error::Backend(format!("truth_evidence_json: {error}")))?
                .as_bytes(),
        ),
        serde_json::Value::Array(values) => {
            out.push(b'[');
            for (index, child) in values.iter().enumerate() {
                if index > 0 {
                    out.push(b',');
                }
                write_canonical_json(child, out)?;
            }
            out.push(b']');
        }
        serde_json::Value::Object(values) => {
            out.push(b'{');
            let mut keys: Vec<&String> = values.keys().collect();
            keys.sort_unstable();
            for (index, key) in keys.into_iter().enumerate() {
                if index > 0 {
                    out.push(b',');
                }
                out.extend_from_slice(
                    serde_json::to_string(key)
                        .map_err(|error| Error::Backend(format!("truth_evidence_json: {error}")))?
                        .as_bytes(),
                );
                out.push(b':');
                write_canonical_json(&values[key], out)?;
            }
            out.push(b'}');
        }
    }
    Ok(())
}

fn canonical_json_bytes<T: Serialize>(value: &T) -> Result<Vec<u8>> {
    let value = serde_json::to_value(value)
        .map_err(|error| Error::Backend(format!("truth_evidence_json: {error}")))?;
    let mut out = Vec::new();
    write_canonical_json(&value, &mut out)?;
    Ok(out)
}

fn canonical_json_string<T: Serialize>(value: &T) -> Result<String> {
    String::from_utf8(canonical_json_bytes(value)?)
        .map_err(|error| Error::Backend(format!("truth_evidence_json_utf8: {error}")))
}

struct BoundedCanonicalDigestWriter {
    bytes_written: usize,
    hasher: Sha256,
    max_bytes: usize,
}

impl BoundedCanonicalDigestWriter {
    fn new(max_bytes: usize) -> Self {
        Self {
            bytes_written: 0,
            hasher: Sha256::new(),
            max_bytes,
        }
    }

    fn finish(self) -> (usize, String) {
        (self.bytes_written, format!("{:x}", self.hasher.finalize()))
    }
}

impl Write for BoundedCanonicalDigestWriter {
    fn write(&mut self, bytes: &[u8]) -> io::Result<usize> {
        let next = self
            .bytes_written
            .checked_add(bytes.len())
            .ok_or_else(|| io::Error::other("canonical payload length overflow"))?;
        if next >= self.max_bytes {
            return Err(io::Error::other(
                "canonical payload reached configured byte sentinel",
            ));
        }
        self.hasher.update(bytes);
        self.bytes_written = next;
        Ok(bytes.len())
    }

    fn flush(&mut self) -> io::Result<()> {
        Ok(())
    }
}

fn bounded_canonical_json_digest<T: Serialize>(
    value: &T,
    max_bytes: usize,
) -> RusqliteResult<(usize, String)> {
    let mut writer = BoundedCanonicalDigestWriter::new(max_bytes);
    serde_json::to_writer(&mut writer, value).map_err(|error| {
        sql_reject(
            "truth_evidence_snapshot_payload",
            format!("bounded canonical serialization failed: {error}"),
        )
    })?;
    Ok(writer.finish())
}

fn claim_identity_sha256(referent_id: &str, predicate_id: &str) -> Result<String> {
    let payload = BTreeMap::from([("predicate_id", predicate_id), ("referent_id", referent_id)]);
    Ok(sha256_hex(&canonical_json_bytes(&payload)?))
}

#[derive(Serialize)]
struct TombstoneAttestationPayload<'a> {
    attestation_version: &'a str,
    had_outgoing_governance: bool,
    lineage_id: &'a str,
    tombstone_id: &'a str,
    tombstoned_at: i64,
}

fn tombstone_attestation_sha256(
    tombstone_id: &str,
    lineage_id: &str,
    tombstoned_at: i64,
    had_outgoing_governance: bool,
) -> Result<String> {
    let payload = TombstoneAttestationPayload {
        attestation_version: ATTESTATION_VERSION,
        had_outgoing_governance,
        lineage_id,
        tombstone_id,
        tombstoned_at,
    };
    Ok(sha256_hex(&canonical_json_bytes(&payload)?))
}

fn map_call_error(operation: &str, error: tokio_rusqlite::Error) -> TemporalEvidenceStoreError {
    TemporalEvidenceStoreError::from_call(operation, error)
}

fn validate_new_lineage(input: &NewTruthLineage) -> Result<()> {
    validate_label(&input.lineage_id, "lineage_id")?;
    validate_label(&input.referent_id, "referent_id")?;
    validate_label(&input.predicate_id, "predicate_id")?;
    validate_timestamp(input.created_at, "created_at")
}

fn validate_new_policy(input: &NewAuthorityPolicyRevision) -> Result<()> {
    validate_label(&input.policy_revision_id, "policy_revision_id")?;
    validate_label(&input.policy_lineage_id, "policy_lineage_id")?;
    validate_label(&input.predicate_id, "predicate_id")?;
    validate_label(&input.source_key, "source_key")?;
    validate_timestamp(input.recorded_at, "recorded_at")?;
    if input.valid_from.is_some_and(|value| value < 0)
        || input.valid_until.is_some_and(|value| value < 0)
    {
        return Err(Error::Backend(
            "truth_evidence_invalid_policy: validity bounds must be non-negative".into(),
        ));
    }
    if let (Some(lower), Some(upper)) = (input.valid_from, input.valid_until) {
        if lower > upper {
            return Err(Error::Backend(
                "truth_evidence_invalid_policy: validity bounds are inverted".into(),
            ));
        }
    }
    Ok(())
}

fn validate_new_evidence_memory_budget(input: &NewEvidenceRevision) -> Result<()> {
    for (field, count) in [
        ("aliases", input.aliases.len()),
        ("source_bindings", input.source_bindings.len()),
        ("relationships", input.relationships.len()),
    ] {
        if count >= MAX_RELATIONSHIPS {
            return Err(Error::Backend(format!(
                "truth_evidence_input_capacity: {field} count {count} reached sentinel {MAX_RELATIONSHIPS}"
            )));
        }
    }

    // Bound user-controlled material before serde constructs any per-row
    // intermediate Value. Eight times raw UTF-8 exceeds JSON's six-byte
    // worst-case control-character escape and leaves delimiter headroom.
    // Aggregate snapshot serialization is separately streamed into a strict
    // bounded writer, so it never materializes a second full-ledger payload.
    let mut estimated = input
        .value
        .len()
        .checked_mul(INPUT_JSON_EXPANSION_FACTOR)
        .ok_or_else(|| {
            Error::Backend("truth_evidence_input_capacity: value size overflow".into())
        })?;
    let mut add_text = |field: &str, value: &str, fixed_overhead: usize| -> Result<()> {
        let addition = value
            .len()
            .checked_mul(INPUT_JSON_EXPANSION_FACTOR)
            .and_then(|size| size.checked_add(fixed_overhead))
            .ok_or_else(|| {
                Error::Backend(format!(
                    "truth_evidence_input_capacity: {field} size overflow"
                ))
            })?;
        estimated = estimated.checked_add(addition).ok_or_else(|| {
            Error::Backend(format!(
                "truth_evidence_input_capacity: {field} aggregate overflow"
            ))
        })?;
        if estimated >= MAX_PAYLOAD_BYTES {
            return Err(Error::Backend(format!(
                "truth_evidence_input_capacity: estimated canonical material reached sentinel {MAX_PAYLOAD_BYTES}"
            )));
        }
        Ok(())
    };
    for alias in &input.aliases {
        add_text("alias", alias, 8)?;
    }
    for binding in &input.source_bindings {
        add_text("source_binding", &binding.source_key, 320)?;
    }
    for relationship in &input.relationships {
        add_text("relationship", &relationship.target_lineage_id, 192)?;
    }
    Ok(())
}

fn validate_new_evidence(input: &NewEvidenceRevision) -> Result<()> {
    validate_new_evidence_memory_budget(input)?;
    validate_label(&input.evidence_id, "evidence_id")?;
    validate_new_lineage(&input.lineage)?;
    if input.value.is_empty() || input.value.len() > MAX_VALUE_BYTES {
        return Err(Error::Backend(format!(
            "truth_evidence_invalid_value: value must contain 1..={MAX_VALUE_BYTES} UTF-8 bytes"
        )));
    }
    validate_timestamp(input.observed_at, "observed_at")?;
    validate_timestamp(input.recorded_at, "recorded_at")?;
    if input.observed_at > input.recorded_at {
        return Err(Error::Backend(
            "truth_evidence_observation_after_recording: observed_at exceeds recorded_at".into(),
        ));
    }
    input
        .validity
        .validate()
        .map_err(|detail| Error::Backend(format!("truth_evidence_invalid_validity: {detail}")))?;
    input
        .lifecycle
        .validate()
        .map_err(|detail| Error::Backend(format!("truth_evidence_invalid_lifecycle: {detail}")))?;
    if input
        .aliases
        .iter()
        .any(|alias| validate_label(alias, "alias").is_err())
        || input.aliases.windows(2).any(|pair| pair[0] >= pair[1])
    {
        return Err(Error::Backend(
            "truth_evidence_noncanonical_aliases: aliases must be unique binary-sorted labels"
                .into(),
        ));
    }
    if input.source_bindings.is_empty() {
        return Err(Error::Backend(
            "truth_evidence_missing_provenance: source_bindings is empty".into(),
        ));
    }
    for binding in &input.source_bindings {
        validate_label(&binding.source_key, "source_key")?;
        validate_digest(&binding.provenance_sha256, "provenance_sha256")?;
    }
    if input.source_bindings.windows(2).any(|pair| {
        (&pair[0].source_key, &pair[0].provenance_sha256)
            >= (&pair[1].source_key, &pair[1].provenance_sha256)
            || pair[0].source_key == pair[1].source_key
    }) {
        return Err(Error::Backend(
            "truth_evidence_noncanonical_provenance: source bindings must be unique and binary-sorted"
                .into(),
        ));
    }
    validate_label(
        &input.authority_policy_revision_id,
        "authority_policy_revision_id",
    )?;
    for relationship in &input.relationships {
        validate_label(&relationship.target_lineage_id, "target_lineage_id")?;
        validate_timestamp(relationship.effective_from, "effective_from")?;
    }
    if input.relationships.windows(2).any(|pair| {
        (
            pair[0].relationship_kind.as_str(),
            &pair[0].target_lineage_id,
            pair[0].effective_from,
        ) >= (
            pair[1].relationship_kind.as_str(),
            &pair[1].target_lineage_id,
            pair[1].effective_from,
        )
    }) {
        return Err(Error::Backend(
            "truth_evidence_noncanonical_relationships: relationships must be binary-sorted".into(),
        ));
    }
    let mut targets = HashSet::new();
    if input
        .relationships
        .iter()
        .any(|relationship| !targets.insert(&relationship.target_lineage_id))
    {
        return Err(Error::Backend(
            "truth_evidence_dual_relationship: one evidence revision may declare one row per target"
                .into(),
        ));
    }
    Ok(())
}

fn validate_new_tombstone(input: &NewLineageTombstone) -> Result<()> {
    validate_label(&input.tombstone_id, "tombstone_id")?;
    validate_label(&input.lineage_id, "lineage_id")?;
    validate_timestamp(input.tombstoned_at, "tombstoned_at")
}

fn relationship_would_cycle(
    tx: &rusqlite::Transaction<'_>,
    source_lineage_id: &str,
    target_lineage_id: &str,
) -> RusqliteResult<bool> {
    tx.query_row(
        "WITH RECURSIVE
             latest(lineage_id, revision_seq) AS (
                 SELECT lineage_id, MAX(revision_seq)
                   FROM main.truth_evidence_revisions
                  GROUP BY lineage_id
             ),
             edges(source_lineage_id, target_lineage_id) AS (
                 SELECT e.lineage_id, r.target_lineage_id
                   FROM main.truth_evidence_relationships r
                   JOIN main.truth_evidence_revisions e
                     ON e.evidence_id = r.declared_evidence_id
                   JOIN latest l
                     ON l.lineage_id = e.lineage_id
                    AND l.revision_seq = e.revision_seq
             ),
             reach(node) AS (
                 SELECT ?1
                 UNION
                 SELECT e.target_lineage_id
                   FROM edges e
                   JOIN reach r ON r.node = e.source_lineage_id
             )
         SELECT EXISTS(SELECT 1 FROM reach WHERE node=?2)",
        params![target_lineage_id, source_lineage_id],
        |row| row.get(0),
    )
}

impl SqliteStore {
    async fn truth_evidence_append_policy_synthetic(
        &self,
        _token: &SyntheticTemporalEvidenceWriteToken,
        input: NewAuthorityPolicyRevision,
    ) -> TemporalEvidenceStoreResult<AuthorityPolicyRevisionRow> {
        let operation = "truth_evidence_append_policy_synthetic";
        validate_new_policy(&input)
            .map_err(|error| TemporalEvidenceStoreError::from_validation(operation, error))?;
        self.conn
            .call(move |c| -> RusqliteResult<AuthorityPolicyRevisionRow> {
                let tx = c.transaction_with_behavior(rusqlite::TransactionBehavior::Immediate)?;
                verify_v43_connection(&tx)?;
                let competing_lineage: Option<String> = tx
                    .query_row(
                        "SELECT policy_lineage_id
                           FROM main.truth_authority_policy_revisions
                          WHERE predicate_id=?1 AND source_key=?2
                            AND policy_lineage_id!=?3
                          LIMIT 1",
                        params![
                            input.predicate_id,
                            input.source_key,
                            input.policy_lineage_id
                        ],
                        |row| row.get(0),
                    )
                    .optional()?;
                if let Some(competing) = competing_lineage {
                    return Err(sql_reject(
                        "truth_evidence_policy_tier_shopping",
                        format!("predicate/source already belongs to {competing}"),
                    ));
                }
                let previous: Option<(i64, i64, String, String)> = tx
                    .query_row(
                        "SELECT revision_seq,recorded_at,predicate_id,source_key
                           FROM main.truth_authority_policy_revisions
                          WHERE policy_lineage_id=?1
                          ORDER BY revision_seq DESC
                          LIMIT 1",
                        params![input.policy_lineage_id],
                        |row| Ok((row.get(0)?, row.get(1)?, row.get(2)?, row.get(3)?)),
                    )
                    .optional()?;
                let revision_seq = match previous {
                    None => 1,
                    Some((sequence, recorded_at, predicate_id, source_key)) => {
                        if predicate_id != input.predicate_id || source_key != input.source_key {
                            return Err(sql_reject(
                                "truth_evidence_policy_identity_drift",
                                &input.policy_lineage_id,
                            ));
                        }
                        if input.recorded_at <= recorded_at {
                            return Err(sql_reject(
                                "truth_evidence_policy_time_regression",
                                &input.policy_lineage_id,
                            ));
                        }
                        sequence.checked_add(1).ok_or_else(|| {
                            sql_reject("truth_evidence_sequence_overflow", &input.policy_lineage_id)
                        })?
                    }
                };
                let row = AuthorityPolicyRevisionRow {
                    policy_revision_id: input.policy_revision_id,
                    policy_lineage_id: input.policy_lineage_id,
                    revision_seq,
                    recorded_at: input.recorded_at,
                    predicate_id: input.predicate_id,
                    source_key: input.source_key,
                    resolved_truth_tier: input.resolved_truth_tier,
                    valid_from: input.valid_from,
                    valid_until: input.valid_until,
                    status: input.status,
                };
                tx.execute(
                    "INSERT INTO main.truth_authority_policy_revisions(
                         policy_revision_id,policy_lineage_id,revision_seq,recorded_at,
                         predicate_id,source_key,resolved_truth_tier,valid_from,valid_until,status
                     ) VALUES(?1,?2,?3,?4,?5,?6,?7,?8,?9,?10)",
                    params![
                        row.policy_revision_id,
                        row.policy_lineage_id,
                        row.revision_seq,
                        row.recorded_at,
                        row.predicate_id,
                        row.source_key,
                        row.resolved_truth_tier.as_str(),
                        row.valid_from,
                        row.valid_until,
                        row.status.as_str(),
                    ],
                )?;
                validate_full_ledger(&tx)?;
                tx.commit()?;
                Ok(row)
            })
            .await
            .map_err(|error| map_call_error(operation, error))
    }

    async fn truth_evidence_append_revision_synthetic(
        &self,
        _token: &SyntheticTemporalEvidenceWriteToken,
        input: NewEvidenceRevision,
    ) -> TemporalEvidenceStoreResult<EvidenceRevisionRow> {
        let operation = "truth_evidence_append_revision_synthetic";
        validate_new_evidence(&input)
            .map_err(|error| TemporalEvidenceStoreError::from_validation(operation, error))?;
        let aliases_json = canonical_json_string(&input.aliases)
            .map_err(|error| TemporalEvidenceStoreError::from_validation(operation, error))?;
        let validity_json = canonical_json_string(&input.validity)
            .map_err(|error| TemporalEvidenceStoreError::from_validation(operation, error))?;
        let lifecycle_json = canonical_json_string(&input.lifecycle)
            .map_err(|error| TemporalEvidenceStoreError::from_validation(operation, error))?;
        let source_bindings_json = canonical_json_string(&input.source_bindings)
            .map_err(|error| TemporalEvidenceStoreError::from_validation(operation, error))?;
        let requested_claim_identity =
            claim_identity_sha256(&input.lineage.referent_id, &input.lineage.predicate_id)
                .map_err(|error| TemporalEvidenceStoreError::from_validation(operation, error))?;
        self.conn
            .call(move |c| -> RusqliteResult<EvidenceRevisionRow> {
                let tx = c.transaction_with_behavior(rusqlite::TransactionBehavior::Immediate)?;
                verify_v43_connection(&tx)?;
                let lineage: Option<(String, String, i64)> = tx
                    .query_row(
                        "SELECT referent_id,predicate_id,created_at
                           FROM main.truth_lineages WHERE lineage_id=?1",
                        params![input.lineage.lineage_id],
                        |row| Ok((row.get(0)?, row.get(1)?, row.get(2)?)),
                    )
                    .optional()?;
                let (referent_id, predicate_id, created_at) = match lineage {
                    Some(existing)
                        if existing.0 == input.lineage.referent_id
                            && existing.1 == input.lineage.predicate_id
                            && existing.2 == input.lineage.created_at =>
                    {
                        existing
                    }
                    Some(_) => {
                        return Err(sql_reject(
                            "truth_evidence_lineage_identity_drift",
                            &input.lineage.lineage_id,
                        ));
                    }
                    None => {
                        tx.execute(
                            "INSERT INTO main.truth_lineages(
                                 lineage_id,referent_id,predicate_id,created_at,
                                 claim_identity_sha256
                             ) VALUES(?1,?2,?3,?4,?5)",
                            params![
                                input.lineage.lineage_id,
                                input.lineage.referent_id,
                                input.lineage.predicate_id,
                                input.lineage.created_at,
                                requested_claim_identity,
                            ],
                        )?;
                        (
                            input.lineage.referent_id.clone(),
                            input.lineage.predicate_id.clone(),
                            input.lineage.created_at,
                        )
                    }
                };
                if created_at > input.recorded_at {
                    return Err(sql_reject(
                        "truth_evidence_revision_predates_lineage",
                        &input.evidence_id,
                    ));
                }
                let tombstoned: bool = tx.query_row(
                    "SELECT EXISTS(
                         SELECT 1 FROM main.truth_lineage_tombstones WHERE lineage_id=?1
                     )",
                    params![input.lineage.lineage_id],
                    |row| row.get(0),
                )?;
                if tombstoned {
                    return Err(sql_reject(
                        "truth_evidence_tombstoned_lineage",
                        &input.lineage.lineage_id,
                    ));
                }
                let previous: Option<(String, i64, i64)> = tx
                    .query_row(
                        "SELECT evidence_id,revision_seq,recorded_at
                           FROM main.truth_evidence_revisions
                          WHERE lineage_id=?1
                          ORDER BY revision_seq DESC LIMIT 1",
                        params![input.lineage.lineage_id],
                        |row| Ok((row.get(0)?, row.get(1)?, row.get(2)?)),
                    )
                    .optional()?;
                let revision_seq = match previous.as_ref() {
                    None => 1,
                    Some((_, sequence, recorded_at)) => {
                        if input.recorded_at <= *recorded_at {
                            return Err(sql_reject(
                                "truth_evidence_recorded_at_regression",
                                &input.lineage.lineage_id,
                            ));
                        }
                        sequence.checked_add(1).ok_or_else(|| {
                            sql_reject(
                                "truth_evidence_sequence_overflow",
                                &input.lineage.lineage_id,
                            )
                        })?
                    }
                };

                let policy: Option<(
                    String,
                    i64,
                    String,
                    String,
                    TruthTier,
                    Option<i64>,
                    Option<i64>,
                    PolicyStatus,
                )> = tx
                    .query_row(
                        "SELECT policy_lineage_id,recorded_at,predicate_id,source_key,
                                resolved_truth_tier,valid_from,valid_until,status
                           FROM main.truth_authority_policy_revisions
                          WHERE policy_revision_id=?1",
                        params![input.authority_policy_revision_id],
                        |row| {
                            let tier: String = row.get(4)?;
                            let status: String = row.get(7)?;
                            Ok((
                                row.get(0)?,
                                row.get(1)?,
                                row.get(2)?,
                                row.get(3)?,
                                TruthTier::parse(&tier)?,
                                row.get(5)?,
                                row.get(6)?,
                                PolicyStatus::parse(&status)?,
                            ))
                        },
                    )
                    .optional()?;
                let (
                    policy_lineage_id,
                    policy_recorded_at,
                    policy_predicate,
                    policy_source,
                    resolved_truth_tier,
                    policy_valid_from,
                    policy_valid_until,
                    policy_status,
                ) = policy.ok_or_else(|| {
                    sql_reject(
                        "truth_evidence_unknown_authority_policy",
                        &input.authority_policy_revision_id,
                    )
                })?;
                if policy_predicate != predicate_id {
                    return Err(sql_reject(
                        "truth_evidence_authority_predicate_fallback",
                        &input.evidence_id,
                    ));
                }
                if !input
                    .source_bindings
                    .iter()
                    .any(|binding| binding.source_key == policy_source)
                {
                    return Err(sql_reject(
                        "truth_evidence_authority_source_mismatch",
                        &input.evidence_id,
                    ));
                }
                let latest_policy_id: Option<String> = tx
                    .query_row(
                        "SELECT policy_revision_id
                           FROM main.truth_authority_policy_revisions
                          WHERE policy_lineage_id=?1 AND recorded_at<=?2
                          ORDER BY revision_seq DESC LIMIT 1",
                        params![policy_lineage_id, input.recorded_at],
                        |row| row.get(0),
                    )
                    .optional()?;
                if latest_policy_id.as_deref() != Some(input.authority_policy_revision_id.as_str())
                {
                    return Err(sql_reject(
                        "truth_evidence_policy_not_latest_visible",
                        &input.evidence_id,
                    ));
                }
                if policy_status != PolicyStatus::Active
                    || policy_recorded_at > input.recorded_at
                    || policy_valid_from.is_some_and(|lower| input.recorded_at < lower)
                    || policy_valid_until.is_some_and(|upper| input.recorded_at > upper)
                {
                    return Err(sql_reject(
                        "truth_evidence_authority_policy_inactive",
                        &input.evidence_id,
                    ));
                }

                let previous_relationships: BTreeSet<(String, String, i64)> =
                    if let Some((previous_id, _, _)) = previous.as_ref() {
                        let mut statement = tx.prepare(
                            "SELECT relationship_kind,target_lineage_id,effective_from
                               FROM main.truth_evidence_relationships
                              WHERE declared_evidence_id=?1
                              ORDER BY relationship_kind COLLATE BINARY,
                                       target_lineage_id COLLATE BINARY,effective_from",
                        )?;
                        let relationships = statement
                            .query_map(params![previous_id], |row| {
                                Ok((row.get(0)?, row.get(1)?, row.get(2)?))
                            })?
                            .collect::<std::result::Result<_, _>>()?;
                        relationships
                    } else {
                        BTreeSet::new()
                    };
                let requested_relationships: BTreeSet<(String, String, i64)> = input
                    .relationships
                    .iter()
                    .map(|relationship| {
                        (
                            relationship.relationship_kind.as_str().to_string(),
                            relationship.target_lineage_id.clone(),
                            relationship.effective_from,
                        )
                    })
                    .collect();
                if !previous_relationships.is_subset(&requested_relationships) {
                    return Err(sql_reject(
                        "truth_evidence_dropped_relationship",
                        &input.lineage.lineage_id,
                    ));
                }

                for relationship in &input.relationships {
                    if !input.validity.active_at(relationship.effective_from)
                        || !input.lifecycle.active_at(relationship.effective_from)
                    {
                        return Err(sql_reject(
                            "truth_evidence_relationship_outside_source_activity",
                            &relationship.target_lineage_id,
                        ));
                    }
                    let target: Option<(String, String)> = tx
                        .query_row(
                            "SELECT referent_id,predicate_id FROM main.truth_lineages
                              WHERE lineage_id=?1",
                            params![relationship.target_lineage_id],
                            |row| Ok((row.get(0)?, row.get(1)?)),
                        )
                        .optional()?;
                    let (target_referent, target_predicate) = target.ok_or_else(|| {
                        sql_reject(
                            "truth_evidence_dangling_relationship",
                            &relationship.target_lineage_id,
                        )
                    })?;
                    if relationship.target_lineage_id == input.lineage.lineage_id {
                        return Err(sql_reject(
                            "truth_evidence_self_relationship",
                            &input.lineage.lineage_id,
                        ));
                    }
                    if target_referent != referent_id || target_predicate != predicate_id {
                        return Err(sql_reject(
                            "truth_evidence_cross_claim_relationship",
                            &relationship.target_lineage_id,
                        ));
                    }
                    let same_second: bool = tx.query_row(
                        "SELECT EXISTS(
                             SELECT 1 FROM main.truth_evidence_revisions
                              WHERE lineage_id=?1 AND recorded_at=?2
                         )",
                        params![relationship.target_lineage_id, input.recorded_at],
                        |row| row.get(0),
                    )?;
                    if same_second {
                        return Err(sql_reject(
                            "truth_evidence_same_second_target_ambiguity",
                            &relationship.target_lineage_id,
                        ));
                    }
                    let target_tier: Option<String> = tx
                        .query_row(
                            "SELECT resolved_truth_tier
                               FROM main.truth_evidence_revisions
                              WHERE lineage_id=?1 AND recorded_at<?2
                              ORDER BY revision_seq DESC LIMIT 1",
                            params![relationship.target_lineage_id, input.recorded_at],
                            |row| row.get(0),
                        )
                        .optional()?;
                    let target_tier = TruthTier::parse(&target_tier.ok_or_else(|| {
                        sql_reject(
                            "truth_evidence_relationship_target_not_visible",
                            &relationship.target_lineage_id,
                        )
                    })?)?;
                    if resolved_truth_tier.rank() < target_tier.rank() {
                        return Err(sql_reject(
                            "truth_evidence_lower_tier_suppression",
                            &relationship.target_lineage_id,
                        ));
                    }
                    if relationship_would_cycle(
                        &tx,
                        &input.lineage.lineage_id,
                        &relationship.target_lineage_id,
                    )? {
                        return Err(sql_reject(
                            "truth_evidence_relationship_cycle",
                            &relationship.target_lineage_id,
                        ));
                    }
                }

                let row = EvidenceRevisionRow {
                    evidence_id: input.evidence_id,
                    lineage_id: input.lineage.lineage_id,
                    revision_seq,
                    value: input.value,
                    aliases: input.aliases,
                    observed_at: input.observed_at,
                    recorded_at: input.recorded_at,
                    validity: input.validity,
                    lifecycle: input.lifecycle,
                    source_bindings: input.source_bindings,
                    authority_policy_revision_id: input.authority_policy_revision_id,
                    resolved_truth_tier,
                };
                tx.execute(
                    "INSERT INTO main.truth_evidence_revisions(
                         evidence_id,lineage_id,revision_seq,value,aliases,observed_at,
                         recorded_at,validity,lifecycle,source_bindings,
                         authority_policy_revision_id,resolved_truth_tier
                     ) VALUES(?1,?2,?3,?4,?5,?6,?7,?8,?9,?10,?11,?12)",
                    params![
                        row.evidence_id,
                        row.lineage_id,
                        row.revision_seq,
                        row.value,
                        aliases_json,
                        row.observed_at,
                        row.recorded_at,
                        validity_json,
                        lifecycle_json,
                        source_bindings_json,
                        row.authority_policy_revision_id,
                        row.resolved_truth_tier.as_str(),
                    ],
                )?;
                for relationship in input.relationships {
                    tx.execute(
                        "INSERT INTO main.truth_evidence_relationships(
                             declared_evidence_id,relationship_kind,target_lineage_id,effective_from
                         ) VALUES(?1,?2,?3,?4)",
                        params![
                            row.evidence_id,
                            relationship.relationship_kind.as_str(),
                            relationship.target_lineage_id,
                            relationship.effective_from,
                        ],
                    )?;
                }
                validate_full_ledger(&tx)?;
                tx.commit()?;
                Ok(row)
            })
            .await
            .map_err(|error| map_call_error(operation, error))
    }

    async fn truth_evidence_tombstone_lineage_synthetic(
        &self,
        _token: &SyntheticTemporalEvidenceWriteToken,
        input: NewLineageTombstone,
    ) -> TemporalEvidenceStoreResult<LineageTombstoneRow> {
        let operation = "truth_evidence_tombstone_lineage_synthetic";
        validate_new_tombstone(&input)
            .map_err(|error| TemporalEvidenceStoreError::from_validation(operation, error))?;
        self.conn
            .call(move |c| -> RusqliteResult<LineageTombstoneRow> {
                let tx = c.transaction_with_behavior(rusqlite::TransactionBehavior::Immediate)?;
                verify_v43_connection(&tx)?;
                let latest_recorded_at: Option<i64> = tx.query_row(
                    "SELECT MAX(recorded_at) FROM main.truth_evidence_revisions
                          WHERE lineage_id=?1",
                    params![input.lineage_id],
                    |row| row.get(0),
                )?;
                let latest_recorded_at = latest_recorded_at.ok_or_else(|| {
                    sql_reject(
                        "truth_evidence_tombstone_without_revision",
                        &input.lineage_id,
                    )
                })?;
                if input.tombstoned_at < latest_recorded_at {
                    return Err(sql_reject(
                        "truth_evidence_tombstone_before_revision",
                        &input.lineage_id,
                    ));
                }
                let had_outgoing_governance: bool = tx.query_row(
                    "SELECT EXISTS(
                         SELECT 1
                           FROM main.truth_evidence_relationships r
                           JOIN main.truth_evidence_revisions e
                             ON e.evidence_id=r.declared_evidence_id
                          WHERE e.lineage_id=?1
                     )",
                    params![input.lineage_id],
                    |row| row.get(0),
                )?;
                let row = LineageTombstoneRow {
                    attestation_sha256: tombstone_attestation_sha256(
                        &input.tombstone_id,
                        &input.lineage_id,
                        input.tombstoned_at,
                        had_outgoing_governance,
                    )
                    .map_err(|error| {
                        sql_reject("truth_evidence_tombstone_digest", error.to_string())
                    })?,
                    tombstone_id: input.tombstone_id,
                    lineage_id: input.lineage_id,
                    tombstoned_at: input.tombstoned_at,
                    had_outgoing_governance,
                    attestation_version: ATTESTATION_VERSION.to_string(),
                };
                tx.execute(
                    "INSERT INTO main.truth_lineage_tombstones(
                         tombstone_id,lineage_id,tombstoned_at,had_outgoing_governance,
                         attestation_version,attestation_sha256
                     ) VALUES(?1,?2,?3,?4,?5,?6)",
                    params![
                        row.tombstone_id,
                        row.lineage_id,
                        row.tombstoned_at,
                        row.had_outgoing_governance,
                        row.attestation_version,
                        row.attestation_sha256,
                    ],
                )?;
                validate_full_ledger(&tx)?;
                tx.commit()?;
                Ok(row)
            })
            .await
            .map_err(|error| map_call_error(operation, error))
    }
}

#[derive(Serialize)]
struct SnapshotPayload<'a> {
    authority_policies: &'a [AuthorityPolicyRevisionRow],
    lineages: &'a [TruthLineageRow],
    relationships: &'a [EvidenceRelationshipRow],
    revisions: &'a [EvidenceRevisionRow],
    tombstones: &'a [LineageTombstoneRow],
}

fn decode_canonical_json<T>(encoded: &str, field: &str) -> RusqliteResult<T>
where
    T: for<'de> Deserialize<'de> + Serialize,
{
    let decoded: T = serde_json::from_str(encoded).map_err(|error| {
        sql_reject(
            "truth_evidence_decode",
            format!("{field} is invalid JSON: {error}"),
        )
    })?;
    let canonical = canonical_json_string(&decoded)
        .map_err(|error| sql_reject("truth_evidence_decode", error.to_string()))?;
    if canonical != encoded {
        return Err(sql_reject("truth_evidence_noncanonical_json", field));
    }
    Ok(decoded)
}

fn preflight_raw_payload(
    tx: &rusqlite::Transaction<'_>,
    max_payload_bytes: usize,
) -> RusqliteResult<()> {
    let queries = [
        "SELECT COALESCE(SUM(
             length(CAST(lineage_id AS BLOB))
           + length(CAST(referent_id AS BLOB))
           + length(CAST(predicate_id AS BLOB))
           + length(CAST(claim_identity_sha256 AS BLOB)) + 8
         ),0) FROM main.truth_lineages",
        "SELECT COALESCE(SUM(
             length(CAST(policy_revision_id AS BLOB))
           + length(CAST(policy_lineage_id AS BLOB))
           + length(CAST(predicate_id AS BLOB))
           + length(CAST(source_key AS BLOB))
           + length(CAST(resolved_truth_tier AS BLOB))
           + length(CAST(status AS BLOB)) + 40
         ),0) FROM main.truth_authority_policy_revisions",
        "SELECT COALESCE(SUM(
             length(CAST(evidence_id AS BLOB))
           + length(CAST(lineage_id AS BLOB))
           + length(CAST(value AS BLOB))
           + length(CAST(aliases AS BLOB))
           + length(CAST(validity AS BLOB))
           + length(CAST(lifecycle AS BLOB))
           + length(CAST(source_bindings AS BLOB))
           + length(CAST(authority_policy_revision_id AS BLOB))
           + length(CAST(resolved_truth_tier AS BLOB)) + 24
         ),0) FROM main.truth_evidence_revisions",
        "SELECT COALESCE(SUM(
             length(CAST(declared_evidence_id AS BLOB))
           + length(CAST(relationship_kind AS BLOB))
           + length(CAST(target_lineage_id AS BLOB)) + 8
         ),0) FROM main.truth_evidence_relationships",
        "SELECT COALESCE(SUM(
             length(CAST(tombstone_id AS BLOB))
           + length(CAST(lineage_id AS BLOB))
           + length(CAST(attestation_version AS BLOB))
           + length(CAST(attestation_sha256 AS BLOB)) + 16
         ),0) FROM main.truth_lineage_tombstones",
    ];
    let mut total = 0usize;
    for query in queries {
        let raw: i64 = tx.query_row(query, [], |row| row.get(0))?;
        let raw = usize::try_from(raw).map_err(|_| {
            sql_reject(
                "truth_evidence_snapshot_payload",
                "negative or oversized raw payload length",
            )
        })?;
        total = total.checked_add(raw).ok_or_else(|| {
            sql_reject(
                "truth_evidence_snapshot_payload",
                "raw payload length overflow",
            )
        })?;
        if total >= max_payload_bytes {
            return Err(sql_reject(
                "truth_evidence_snapshot_payload",
                "raw payload reached the configured byte sentinel",
            ));
        }
    }
    Ok(())
}

fn cap_limit(cap: usize) -> i64 {
    i64::try_from(cap).unwrap_or(i64::MAX)
}

fn reject_if_sentinel_reached(len: usize, cap: usize, field: &str) -> RusqliteResult<()> {
    if len >= cap {
        return Err(sql_reject(
            "truth_evidence_snapshot_truncated",
            format!("{field} reached configured fetch sentinel {cap}"),
        ));
    }
    Ok(())
}

fn load_snapshot(
    tx: &rusqlite::Transaction<'_>,
    limits: TemporalEvidenceSnapshotLimits,
    knowledge_cutoff: i64,
) -> RusqliteResult<TemporalEvidenceSnapshot> {
    verify_v43_connection(tx)?;
    preflight_raw_payload(tx, limits.max_payload_bytes)?;

    let lineages = {
        let mut stmt = tx.prepare(
            "SELECT lineage_id,referent_id,predicate_id,created_at,claim_identity_sha256
               FROM main.truth_lineages
              ORDER BY lineage_id COLLATE BINARY
              LIMIT ?1",
        )?;
        let rows = stmt
            .query_map(params![cap_limit(limits.max_lineages)], |row| {
                Ok(TruthLineageRow {
                    lineage_id: row.get(0)?,
                    referent_id: row.get(1)?,
                    predicate_id: row.get(2)?,
                    created_at: row.get(3)?,
                    claim_identity_sha256: row.get(4)?,
                })
            })?
            .collect::<std::result::Result<Vec<_>, _>>()?;
        reject_if_sentinel_reached(rows.len(), limits.max_lineages, "lineages")?;
        rows
    };

    let authority_policies = {
        let mut stmt = tx.prepare(
            "SELECT policy_revision_id,policy_lineage_id,revision_seq,recorded_at,
                    predicate_id,source_key,resolved_truth_tier,valid_from,valid_until,status
               FROM main.truth_authority_policy_revisions
              ORDER BY policy_lineage_id COLLATE BINARY,revision_seq,
                       policy_revision_id COLLATE BINARY
              LIMIT ?1",
        )?;
        let rows = stmt
            .query_map(params![cap_limit(limits.max_policy_revisions)], |row| {
                let tier: String = row.get(6)?;
                let status: String = row.get(9)?;
                Ok(AuthorityPolicyRevisionRow {
                    policy_revision_id: row.get(0)?,
                    policy_lineage_id: row.get(1)?,
                    revision_seq: row.get(2)?,
                    recorded_at: row.get(3)?,
                    predicate_id: row.get(4)?,
                    source_key: row.get(5)?,
                    resolved_truth_tier: TruthTier::parse(&tier)?,
                    valid_from: row.get(7)?,
                    valid_until: row.get(8)?,
                    status: PolicyStatus::parse(&status)?,
                })
            })?
            .collect::<std::result::Result<Vec<_>, _>>()?;
        reject_if_sentinel_reached(
            rows.len(),
            limits.max_policy_revisions,
            "authority_policies",
        )?;
        rows
    };

    let revisions = {
        let mut stmt = tx.prepare(
            "SELECT evidence_id,lineage_id,revision_seq,value,aliases,observed_at,
                    recorded_at,validity,lifecycle,source_bindings,
                    authority_policy_revision_id,resolved_truth_tier
               FROM main.truth_evidence_revisions
              ORDER BY lineage_id COLLATE BINARY,revision_seq,evidence_id COLLATE BINARY
              LIMIT ?1",
        )?;
        let rows = stmt
            .query_map(params![cap_limit(limits.max_evidence_revisions)], |row| {
                let aliases: String = row.get(4)?;
                let validity: String = row.get(7)?;
                let lifecycle: String = row.get(8)?;
                let source_bindings: String = row.get(9)?;
                let tier: String = row.get(11)?;
                Ok(EvidenceRevisionRow {
                    evidence_id: row.get(0)?,
                    lineage_id: row.get(1)?,
                    revision_seq: row.get(2)?,
                    value: row.get(3)?,
                    aliases: decode_canonical_json(&aliases, "aliases")?,
                    observed_at: row.get(5)?,
                    recorded_at: row.get(6)?,
                    validity: decode_canonical_json(&validity, "validity")?,
                    lifecycle: decode_canonical_json(&lifecycle, "lifecycle")?,
                    source_bindings: decode_canonical_json(&source_bindings, "source_bindings")?,
                    authority_policy_revision_id: row.get(10)?,
                    resolved_truth_tier: TruthTier::parse(&tier)?,
                })
            })?
            .collect::<std::result::Result<Vec<_>, _>>()?;
        reject_if_sentinel_reached(rows.len(), limits.max_evidence_revisions, "revisions")?;
        rows
    };

    let relationships = {
        let mut stmt = tx.prepare(
            "SELECT declared_evidence_id,relationship_kind,target_lineage_id,effective_from
               FROM main.truth_evidence_relationships
              ORDER BY declared_evidence_id COLLATE BINARY,relationship_kind COLLATE BINARY,
                       target_lineage_id COLLATE BINARY,effective_from
              LIMIT ?1",
        )?;
        let rows = stmt
            .query_map(params![cap_limit(limits.max_relationships)], |row| {
                let kind: String = row.get(1)?;
                Ok(EvidenceRelationshipRow {
                    declared_evidence_id: row.get(0)?,
                    relationship_kind: RelationshipKind::parse(&kind)?,
                    target_lineage_id: row.get(2)?,
                    effective_from: row.get(3)?,
                })
            })?
            .collect::<std::result::Result<Vec<_>, _>>()?;
        reject_if_sentinel_reached(rows.len(), limits.max_relationships, "relationships")?;
        rows
    };

    let tombstones = {
        let mut stmt = tx.prepare(
            "SELECT tombstone_id,lineage_id,tombstoned_at,had_outgoing_governance,
                    attestation_version,attestation_sha256
               FROM main.truth_lineage_tombstones
              ORDER BY lineage_id COLLATE BINARY,tombstone_id COLLATE BINARY
              LIMIT ?1",
        )?;
        let rows = stmt
            .query_map(params![cap_limit(limits.max_tombstones)], |row| {
                let governed: i64 = row.get(3)?;
                if !matches!(governed, 0 | 1) {
                    return Err(sql_reject(
                        "truth_evidence_decode",
                        "had_outgoing_governance is not boolean",
                    ));
                }
                Ok(LineageTombstoneRow {
                    tombstone_id: row.get(0)?,
                    lineage_id: row.get(1)?,
                    tombstoned_at: row.get(2)?,
                    had_outgoing_governance: governed == 1,
                    attestation_version: row.get(4)?,
                    attestation_sha256: row.get(5)?,
                })
            })?
            .collect::<std::result::Result<Vec<_>, _>>()?;
        reject_if_sentinel_reached(rows.len(), limits.max_tombstones, "tombstones")?;
        rows
    };

    let payload = SnapshotPayload {
        authority_policies: &authority_policies,
        lineages: &lineages,
        relationships: &relationships,
        revisions: &revisions,
        tombstones: &tombstones,
    };
    let (payload_bytes, payload_sha256) =
        bounded_canonical_json_digest(&payload, limits.max_payload_bytes)?;
    let schema_meta_version = read_meta(tx, "version")?
        .ok_or_else(|| sql_reject("truth_evidence_identity", "schema_meta.version missing"))?;
    let schema_digest = read_meta(tx, SCHEMA_DIGEST_META_KEY)?
        .ok_or_else(|| sql_reject("truth_evidence_identity", "schema digest missing"))?;
    let migration_digest = read_meta(tx, MIGRATION_DIGEST_META_KEY)?
        .ok_or_else(|| sql_reject("truth_evidence_identity", "migration digest missing"))?;
    let ledger_format_version = read_meta(tx, LEDGER_FORMAT_META_KEY)?
        .ok_or_else(|| sql_reject("truth_evidence_identity", "ledger format missing"))?;
    let snapshot = TemporalEvidenceSnapshot {
        producer_identity: TemporalEvidenceProducerIdentity {
            schema_meta_version,
            schema_digest,
            migration_digest,
            ledger_format_version,
        },
        ledger_format_version: 0,
        knowledge_cutoff,
        limits,
        counts: TemporalEvidenceSnapshotCounts {
            lineages: lineages.len(),
            policy_revisions: authority_policies.len(),
            evidence_revisions: revisions.len(),
            relationships: relationships.len(),
            tombstones: tombstones.len(),
        },
        lineages,
        authority_policies,
        revisions,
        relationships,
        tombstones,
        payload_bytes,
        payload_sha256,
        canonical_order: CANONICAL_ORDER,
    };
    validate_snapshot_model(&snapshot)?;
    Ok(snapshot)
}

fn model_validation(result: Result<()>) -> RusqliteResult<()> {
    result.map_err(|error| sql_reject("truth_evidence_model", error.to_string()))
}

fn validate_acyclic_adjacency(adjacency: &HashMap<String, Vec<String>>) -> RusqliteResult<()> {
    const VISITING: u8 = 1;
    const VISITED: u8 = 2;

    let mut states = HashMap::with_capacity(adjacency.len());
    for start in adjacency.keys() {
        if states.get(start).copied() == Some(VISITED) {
            continue;
        }
        states.insert(start.clone(), VISITING);
        let mut stack = vec![(start.clone(), 0_usize)];
        while let Some((node, next_target)) = stack.last_mut() {
            let targets = adjacency.get(node).map(Vec::as_slice).unwrap_or_default();
            if *next_target == targets.len() {
                let completed = node.clone();
                stack.pop();
                states.insert(completed, VISITED);
                continue;
            }

            let target = targets[*next_target].clone();
            *next_target += 1;
            match states.get(&target).copied() {
                Some(VISITING) => {
                    return Err(sql_reject("truth_evidence_relationship_cycle", target));
                }
                Some(VISITED) => {}
                None => {
                    states.insert(target.clone(), VISITING);
                    stack.push((target, 0));
                }
                Some(_) => unreachable!("cycle validator emitted an unknown visit state"),
            }
        }
    }
    Ok(())
}

fn validate_snapshot_model(snapshot: &TemporalEvidenceSnapshot) -> RusqliteResult<()> {
    if !accepted_schema_meta_version(&snapshot.producer_identity.schema_meta_version)
        || snapshot.producer_identity.schema_digest != EXPECTED_SCHEMA_SHA256
        || snapshot.producer_identity.migration_digest != migration_sha256()
        || snapshot.producer_identity.ledger_format_version
            != TEMPORAL_EVIDENCE_LEDGER_FORMAT_VERSION
        || snapshot.ledger_format_version != 0
        || snapshot.canonical_order != CANONICAL_ORDER
    {
        return Err(sql_reject(
            "truth_evidence_identity",
            "snapshot producer identity drifted",
        ));
    }
    if snapshot.counts
        != (TemporalEvidenceSnapshotCounts {
            lineages: snapshot.lineages.len(),
            policy_revisions: snapshot.authority_policies.len(),
            evidence_revisions: snapshot.revisions.len(),
            relationships: snapshot.relationships.len(),
            tombstones: snapshot.tombstones.len(),
        })
    {
        return Err(sql_reject(
            "truth_evidence_snapshot_counts",
            "snapshot counts drifted",
        ));
    }

    let mut lineage_by_id: HashMap<&str, &TruthLineageRow> = HashMap::new();
    for lineage in &snapshot.lineages {
        model_validation(validate_label(&lineage.lineage_id, "lineage_id"))?;
        model_validation(validate_label(&lineage.referent_id, "referent_id"))?;
        model_validation(validate_label(&lineage.predicate_id, "predicate_id"))?;
        model_validation(validate_timestamp(lineage.created_at, "created_at"))?;
        model_validation(validate_digest(
            &lineage.claim_identity_sha256,
            "claim_identity_sha256",
        ))?;
        let expected = claim_identity_sha256(&lineage.referent_id, &lineage.predicate_id)
            .map_err(|error| sql_reject("truth_evidence_claim_identity", error.to_string()))?;
        if lineage.claim_identity_sha256 != expected {
            return Err(sql_reject(
                "truth_evidence_claim_identity",
                &lineage.lineage_id,
            ));
        }
        if lineage_by_id.insert(&lineage.lineage_id, lineage).is_some() {
            return Err(sql_reject(
                "truth_evidence_duplicate_lineage",
                &lineage.lineage_id,
            ));
        }
    }

    let mut policy_by_id: HashMap<&str, &AuthorityPolicyRevisionRow> = HashMap::new();
    let mut policies_by_lineage: BTreeMap<&str, Vec<&AuthorityPolicyRevisionRow>> = BTreeMap::new();
    let mut policy_pair_lineage: HashMap<(&str, &str), &str> = HashMap::new();
    for policy in &snapshot.authority_policies {
        for (field, value) in [
            ("policy_revision_id", policy.policy_revision_id.as_str()),
            ("policy_lineage_id", policy.policy_lineage_id.as_str()),
            ("predicate_id", policy.predicate_id.as_str()),
            ("source_key", policy.source_key.as_str()),
        ] {
            model_validation(validate_label(value, field))?;
        }
        model_validation(validate_timestamp(policy.recorded_at, "policy.recorded_at"))?;
        if policy.revision_seq < 1
            || policy.valid_from.is_some_and(|value| value < 0)
            || policy.valid_until.is_some_and(|value| value < 0)
            || matches!((policy.valid_from, policy.valid_until), (Some(a), Some(b)) if a > b)
        {
            return Err(sql_reject(
                "truth_evidence_policy_contract",
                &policy.policy_revision_id,
            ));
        }
        if policy_by_id
            .insert(&policy.policy_revision_id, policy)
            .is_some()
        {
            return Err(sql_reject(
                "truth_evidence_duplicate_policy",
                &policy.policy_revision_id,
            ));
        }
        policies_by_lineage
            .entry(&policy.policy_lineage_id)
            .or_default()
            .push(policy);
        let pair = (&*policy.predicate_id, &*policy.source_key);
        if let Some(existing) = policy_pair_lineage.insert(pair, &policy.policy_lineage_id) {
            if existing != policy.policy_lineage_id {
                return Err(sql_reject(
                    "truth_evidence_policy_tier_shopping",
                    format!("{}/{}", policy.predicate_id, policy.source_key),
                ));
            }
        }
    }
    for (policy_lineage_id, policies) in &policies_by_lineage {
        let mut previous_time = None;
        for (index, policy) in policies.iter().enumerate() {
            if policy.revision_seq != i64::try_from(index + 1).unwrap_or(i64::MAX) {
                return Err(sql_reject(
                    "truth_evidence_policy_sequence",
                    *policy_lineage_id,
                ));
            }
            if previous_time.is_some_and(|time| policy.recorded_at <= time) {
                return Err(sql_reject(
                    "truth_evidence_policy_time_regression",
                    *policy_lineage_id,
                ));
            }
            if policy.predicate_id != policies[0].predicate_id
                || policy.source_key != policies[0].source_key
            {
                return Err(sql_reject(
                    "truth_evidence_policy_identity_drift",
                    *policy_lineage_id,
                ));
            }
            previous_time = Some(policy.recorded_at);
        }
    }

    let mut revision_by_id: HashMap<&str, &EvidenceRevisionRow> = HashMap::new();
    let mut revisions_by_lineage: BTreeMap<&str, Vec<&EvidenceRevisionRow>> = BTreeMap::new();
    for revision in &snapshot.revisions {
        model_validation(validate_label(&revision.evidence_id, "evidence_id"))?;
        model_validation(validate_label(&revision.lineage_id, "lineage_id"))?;
        model_validation(validate_timestamp(revision.observed_at, "observed_at"))?;
        model_validation(validate_timestamp(revision.recorded_at, "recorded_at"))?;
        if revision.revision_seq < 1
            || revision.value.is_empty()
            || revision.value.len() > MAX_VALUE_BYTES
            || revision.observed_at > revision.recorded_at
        {
            return Err(sql_reject(
                "truth_evidence_revision_contract",
                &revision.evidence_id,
            ));
        }
        revision
            .validity
            .validate()
            .map_err(|detail| sql_reject("truth_evidence_invalid_validity", detail))?;
        revision
            .lifecycle
            .validate()
            .map_err(|detail| sql_reject("truth_evidence_invalid_lifecycle", detail))?;
        if revision.aliases.windows(2).any(|pair| pair[0] >= pair[1]) {
            return Err(sql_reject(
                "truth_evidence_noncanonical_aliases",
                &revision.evidence_id,
            ));
        }
        for alias in &revision.aliases {
            model_validation(validate_label(alias, "alias"))?;
        }
        if revision.source_bindings.is_empty()
            || revision.source_bindings.windows(2).any(|pair| {
                (&pair[0].source_key, &pair[0].provenance_sha256)
                    >= (&pair[1].source_key, &pair[1].provenance_sha256)
                    || pair[0].source_key == pair[1].source_key
            })
        {
            return Err(sql_reject(
                "truth_evidence_noncanonical_provenance",
                &revision.evidence_id,
            ));
        }
        for binding in &revision.source_bindings {
            model_validation(validate_label(&binding.source_key, "source_key"))?;
            model_validation(validate_digest(
                &binding.provenance_sha256,
                "provenance_sha256",
            ))?;
        }
        let lineage = lineage_by_id
            .get(revision.lineage_id.as_str())
            .ok_or_else(|| sql_reject("truth_evidence_missing_lineage", &revision.lineage_id))?;
        if lineage.created_at > revision.recorded_at {
            return Err(sql_reject(
                "truth_evidence_revision_predates_lineage",
                &revision.evidence_id,
            ));
        }
        let policy = policy_by_id
            .get(revision.authority_policy_revision_id.as_str())
            .ok_or_else(|| {
                sql_reject(
                    "truth_evidence_unknown_authority_policy",
                    &revision.authority_policy_revision_id,
                )
            })?;
        let visible_policies: Vec<_> = policies_by_lineage
            .get(policy.policy_lineage_id.as_str())
            .into_iter()
            .flatten()
            .copied()
            .filter(|candidate| candidate.recorded_at <= revision.recorded_at)
            .collect();
        let latest_policy = visible_policies.last().ok_or_else(|| {
            sql_reject(
                "truth_evidence_authority_policy_inactive",
                &revision.evidence_id,
            )
        })?;
        if latest_policy.policy_revision_id != revision.authority_policy_revision_id {
            return Err(sql_reject(
                "truth_evidence_policy_not_latest_visible",
                &revision.evidence_id,
            ));
        }
        if policy.predicate_id != lineage.predicate_id
            || policy.status != PolicyStatus::Active
            || policy
                .valid_from
                .is_some_and(|lower| revision.recorded_at < lower)
            || policy
                .valid_until
                .is_some_and(|upper| revision.recorded_at > upper)
            || policy.resolved_truth_tier != revision.resolved_truth_tier
            || !revision
                .source_bindings
                .iter()
                .any(|binding| binding.source_key == policy.source_key)
        {
            return Err(sql_reject(
                "truth_evidence_authority_policy_inactive",
                &revision.evidence_id,
            ));
        }
        if revision_by_id
            .insert(&revision.evidence_id, revision)
            .is_some()
        {
            return Err(sql_reject(
                "truth_evidence_duplicate_revision",
                &revision.evidence_id,
            ));
        }
        revisions_by_lineage
            .entry(&revision.lineage_id)
            .or_default()
            .push(revision);
    }
    for (lineage_id, revisions) in &revisions_by_lineage {
        let mut previous_time = None;
        for (index, revision) in revisions.iter().enumerate() {
            if revision.revision_seq != i64::try_from(index + 1).unwrap_or(i64::MAX) {
                return Err(sql_reject("truth_evidence_revision_sequence", *lineage_id));
            }
            if previous_time.is_some_and(|time| revision.recorded_at <= time) {
                return Err(sql_reject(
                    "truth_evidence_recorded_at_regression",
                    *lineage_id,
                ));
            }
            previous_time = Some(revision.recorded_at);
        }
    }
    for lineage_id in lineage_by_id.keys() {
        if !revisions_by_lineage.contains_key(lineage_id) {
            return Err(sql_reject("truth_evidence_orphan_lineage", *lineage_id));
        }
    }

    let mut relationships_by_evidence: HashMap<&str, BTreeSet<(String, String, i64)>> =
        HashMap::new();
    let mut targets_by_evidence: HashMap<&str, HashSet<&str>> = HashMap::new();
    for relationship in &snapshot.relationships {
        let source = revision_by_id
            .get(relationship.declared_evidence_id.as_str())
            .ok_or_else(|| {
                sql_reject(
                    "truth_evidence_missing_relationship_source",
                    &relationship.declared_evidence_id,
                )
            })?;
        let source_lineage = lineage_by_id
            .get(source.lineage_id.as_str())
            .ok_or_else(|| sql_reject("truth_evidence_missing_lineage", &source.lineage_id))?;
        let target_lineage = lineage_by_id
            .get(relationship.target_lineage_id.as_str())
            .ok_or_else(|| {
                sql_reject(
                    "truth_evidence_dangling_relationship",
                    &relationship.target_lineage_id,
                )
            })?;
        if source.lineage_id == relationship.target_lineage_id {
            return Err(sql_reject(
                "truth_evidence_self_relationship",
                &source.lineage_id,
            ));
        }
        if source_lineage.referent_id != target_lineage.referent_id
            || source_lineage.predicate_id != target_lineage.predicate_id
        {
            return Err(sql_reject(
                "truth_evidence_cross_claim_relationship",
                &relationship.target_lineage_id,
            ));
        }
        if !source.validity.active_at(relationship.effective_from)
            || !source.lifecycle.active_at(relationship.effective_from)
        {
            return Err(sql_reject(
                "truth_evidence_relationship_outside_source_activity",
                &relationship.declared_evidence_id,
            ));
        }
        if !targets_by_evidence
            .entry(&relationship.declared_evidence_id)
            .or_default()
            .insert(&relationship.target_lineage_id)
        {
            return Err(sql_reject(
                "truth_evidence_dual_relationship",
                &relationship.declared_evidence_id,
            ));
        }
        let target_revisions = revisions_by_lineage
            .get(relationship.target_lineage_id.as_str())
            .ok_or_else(|| {
                sql_reject(
                    "truth_evidence_relationship_target_not_visible",
                    &relationship.target_lineage_id,
                )
            })?;
        if target_revisions
            .iter()
            .any(|target| target.recorded_at == source.recorded_at)
        {
            return Err(sql_reject(
                "truth_evidence_same_second_target_ambiguity",
                &relationship.target_lineage_id,
            ));
        }
        let target = target_revisions
            .iter()
            .rev()
            .find(|target| target.recorded_at < source.recorded_at)
            .ok_or_else(|| {
                sql_reject(
                    "truth_evidence_relationship_target_not_visible",
                    &relationship.target_lineage_id,
                )
            })?;
        if source.resolved_truth_tier.rank() < target.resolved_truth_tier.rank() {
            return Err(sql_reject(
                "truth_evidence_lower_tier_suppression",
                &relationship.target_lineage_id,
            ));
        }
        relationships_by_evidence
            .entry(&relationship.declared_evidence_id)
            .or_default()
            .insert((
                relationship.relationship_kind.as_str().to_string(),
                relationship.target_lineage_id.clone(),
                relationship.effective_from,
            ));
    }
    for (lineage_id, revisions) in &revisions_by_lineage {
        let mut durable = BTreeSet::new();
        for revision in revisions {
            let current = relationships_by_evidence
                .get(revision.evidence_id.as_str())
                .cloned()
                .unwrap_or_default();
            if !durable.is_subset(&current) {
                return Err(sql_reject(
                    "truth_evidence_dropped_relationship",
                    *lineage_id,
                ));
            }
            durable = current;
        }
    }

    let mut adjacency: HashMap<String, Vec<String>> = snapshot
        .lineages
        .iter()
        .map(|lineage| (lineage.lineage_id.clone(), Vec::new()))
        .collect();
    for (lineage_id, revisions) in &revisions_by_lineage {
        if let Some(latest) = revisions.last() {
            if let Some(relationships) = relationships_by_evidence.get(latest.evidence_id.as_str())
            {
                adjacency
                    .entry((*lineage_id).to_string())
                    .or_default()
                    .extend(relationships.iter().map(|(_, target, _)| target.clone()));
            }
        }
    }
    validate_acyclic_adjacency(&adjacency)?;

    let mut tombstoned_lineages = HashSet::new();
    for tombstone in &snapshot.tombstones {
        model_validation(validate_label(&tombstone.tombstone_id, "tombstone_id"))?;
        model_validation(validate_label(&tombstone.lineage_id, "lineage_id"))?;
        model_validation(validate_timestamp(tombstone.tombstoned_at, "tombstoned_at"))?;
        model_validation(validate_digest(
            &tombstone.attestation_sha256,
            "attestation_sha256",
        ))?;
        if tombstone.attestation_version != ATTESTATION_VERSION
            || !tombstoned_lineages.insert(&tombstone.lineage_id)
        {
            return Err(sql_reject(
                "truth_evidence_tombstone_contract",
                &tombstone.lineage_id,
            ));
        }
        if !lineage_by_id.contains_key(tombstone.lineage_id.as_str()) {
            return Err(sql_reject(
                "truth_evidence_dangling_tombstone",
                &tombstone.lineage_id,
            ));
        }
        let revisions = revisions_by_lineage
            .get(tombstone.lineage_id.as_str())
            .ok_or_else(|| {
                sql_reject(
                    "truth_evidence_tombstone_without_revision",
                    &tombstone.lineage_id,
                )
            })?;
        if revisions
            .last()
            .is_some_and(|revision| tombstone.tombstoned_at < revision.recorded_at)
        {
            return Err(sql_reject(
                "truth_evidence_tombstone_before_revision",
                &tombstone.lineage_id,
            ));
        }
        let actual_governed = revisions.iter().any(|revision| {
            relationships_by_evidence
                .get(revision.evidence_id.as_str())
                .is_some_and(|relationships| !relationships.is_empty())
        });
        if actual_governed != tombstone.had_outgoing_governance {
            return Err(sql_reject(
                "truth_evidence_governance_attestation_mismatch",
                &tombstone.lineage_id,
            ));
        }
        let expected = tombstone_attestation_sha256(
            &tombstone.tombstone_id,
            &tombstone.lineage_id,
            tombstone.tombstoned_at,
            tombstone.had_outgoing_governance,
        )
        .map_err(|error| sql_reject("truth_evidence_tombstone_digest", error.to_string()))?;
        if tombstone.attestation_sha256 != expected {
            return Err(sql_reject(
                "truth_evidence_tombstone_digest",
                &tombstone.lineage_id,
            ));
        }
    }
    Ok(())
}

fn validate_full_ledger(tx: &rusqlite::Transaction<'_>) -> RusqliteResult<()> {
    let limits = TemporalEvidenceSnapshotLimits {
        max_lineages: MAX_LINEAGES,
        max_policy_revisions: MAX_POLICY_REVISIONS,
        max_evidence_revisions: MAX_EVIDENCE_REVISIONS,
        max_relationships: MAX_RELATIONSHIPS,
        max_tombstones: MAX_TOMBSTONES,
        max_payload_bytes: MAX_PAYLOAD_BYTES,
    };
    load_snapshot(tx, limits, i64::MAX).map(|_| ())
}

impl SqliteStore {
    async fn truth_evidence_snapshot_internal(
        &self,
        limits: TemporalEvidenceSnapshotLimits,
        knowledge_cutoff: i64,
    ) -> TemporalEvidenceStoreResult<TemporalEvidenceSnapshot> {
        let operation = "truth_evidence_snapshot_internal";
        let limits = limits
            .validate()
            .map_err(|error| TemporalEvidenceStoreError::from_validation(operation, error))?;
        validate_timestamp(knowledge_cutoff, "knowledge_cutoff")
            .map_err(|error| TemporalEvidenceStoreError::from_validation(operation, error))?;
        self.conn
            .call(move |c| -> RusqliteResult<TemporalEvidenceSnapshot> {
                let tx = c.transaction_with_behavior(rusqlite::TransactionBehavior::Deferred)?;
                let snapshot = load_snapshot(&tx, limits, knowledge_cutoff)?;
                tx.commit()?;
                Ok(snapshot)
            })
            .await
            .map_err(|error| map_call_error(operation, error))
    }
}

#[cfg(any(test, feature = "temporal-evidence-s4-synthetic"))]
mod projection_v1;
#[cfg(any(test, feature = "temporal-evidence-s4-synthetic"))]
pub use projection_v1::*;

#[cfg(test)]
mod tests;
