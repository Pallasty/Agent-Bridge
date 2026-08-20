//! SEPL resource-version lineage and P1A0 baseline admission contracts.
//!
//! P0 remains read-only through [`crate::StateStore`]. P1A0 adds an explicit
//! AGENT.md path binding and genesis admission, while P1A1 adds a controlled
//! compare-and-swap commit, P1A2 adds a verified historical rollback, P1A3
//! adds proposal metadata, P1A4 adds an unauthenticated review preflight, and
//! P1A5 adds a persisted, content-addressed proposal artifact through
//! inherent [`crate::SqliteStore`] methods. P1A6 persists untrusted review
//! observations and P1A7 projects them into a bounded, conflict-preserving
//! read-only snapshot.
//! Neither slice exposes an MCP, CLI, scheduler, or automatic producer.

use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use std::collections::BTreeSet;
use std::path::PathBuf;
use tokio_rusqlite::rusqlite;

pub const RESOURCE_LINEAGE_SCHEMA: &str = "agent_bridge.resource_lineage.v0";
pub const RESOURCE_LINEAGE_HASH_DOMAIN: &str = "agent-bridge/sepl/resource-version/v0";
pub const RESOURCE_LINEAGE_MAX_ROWS: u32 = 256;
pub const RESOURCE_BASELINE_ADMISSION_SCHEMA: &str = "agent_bridge.resource_baseline_admission.v0";
pub const RESOURCE_BASELINE_OBSERVATION_SCOPE: &str =
    "opened_file_and_path_identity_before_sqlite_commit";
pub const RESOURCE_CAS_COMMIT_SCHEMA: &str = "agent_bridge.resource_cas_commit.v0";
pub const RESOURCE_CAS_COMMIT_SCOPE: &str =
    "opened_bound_path_replace_readback_and_lineage_append_before_sqlite_commit";
pub const RESOURCE_CAS_ROLLBACK_SCHEMA: &str = "agent_bridge.resource_cas_rollback.v0";
pub const RESOURCE_CAS_ROLLBACK_SCOPE: &str =
    "historical_content_hash_match_cas_replace_readback_and_lineage_append";
pub const RESOURCE_CHANGE_PROPOSAL_SCHEMA: &str = "agent_bridge.resource_change_proposal.v0";
pub const RESOURCE_CHANGE_PROPOSAL_SCOPE: &str =
    "read_only_agent_md_candidate_hash_lineage_binding_and_diff_summary";
pub const RESOURCE_CHANGE_PROPOSAL_REVIEW_SCHEMA: &str =
    "agent_bridge.resource_change_proposal_review.v0";
pub const RESOURCE_CHANGE_PROPOSAL_REVIEW_SCOPE: &str =
    "read_only_receipt_invariants_current_file_binding_and_complete_lineage";
pub const RESOURCE_PERSISTED_PROPOSAL_SCHEMA: &str = "agent_bridge.resource_persisted_proposal.v0";
pub const RESOURCE_PERSISTED_PROPOSAL_SCOPE: &str =
    "sqlite_persisted_candidate_receipt_and_domain_separated_record_hash";
pub const RESOURCE_PERSISTED_PROPOSAL_HASH_DOMAIN: &str =
    "agent-bridge/sepl/resource-persisted-proposal/v0";
pub const RESOURCE_PROPOSAL_REVIEW_OBSERVATION_SCHEMA: &str =
    "agent_bridge.resource_proposal_review_observation.v0";
pub const RESOURCE_PROPOSAL_REVIEW_OBSERVATION_SCOPE: &str =
    "persisted_untrusted_review_observation_only";
pub const RESOURCE_PROPOSAL_REVIEW_OBSERVATION_HASH_DOMAIN: &str =
    "agent-bridge/sepl/resource-proposal-review-observation/v0";
pub const RESOURCE_PROPOSAL_REVIEW_SNAPSHOT_SCHEMA: &str =
    "agent_bridge.resource_proposal_review_snapshot.v0";
pub const RESOURCE_PROPOSAL_REVIEW_SNAPSHOT_SCOPE: &str =
    "bounded_integrity_verified_untrusted_review_observation_set";
pub const RESOURCE_PROPOSAL_REVIEW_SNAPSHOT_HASH_DOMAIN: &str =
    "agent-bridge/sepl/resource-proposal-review-snapshot/v0";
pub const RESOURCE_PROPOSAL_REVIEW_SNAPSHOT_MAX_OBSERVATIONS: usize = 256;
pub const RESOURCE_BINDING_HASH_DOMAIN: &str = "agent-bridge/sepl/resource-binding/v0";
pub const RESOURCE_CONTENT_MAX_BYTES: u64 = 1_048_576;
const RESOURCE_LINEAGE_MIGRATION_META_KEY: &str = "resource_lineage.migration_sha256";
const RESOURCE_BINDINGS_MIGRATION_META_KEY: &str = "resource_bindings.migration_sha256";
const RESOURCE_PROPOSALS_MIGRATION_META_KEY: &str = "resource_proposals.migration_sha256";
const RESOURCE_PROPOSAL_REVIEWS_MIGRATION_META_KEY: &str =
    "resource_proposal_reviews.migration_sha256";

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

pub(crate) const RESOURCE_BINDINGS_SCHEMA: &str = r#"
CREATE TABLE IF NOT EXISTS resource_bindings (
    resource_id       TEXT    NOT NULL PRIMARY KEY
                              CHECK (length(resource_id) BETWEEN 1 AND 512),
    resource_kind     TEXT    NOT NULL CHECK (resource_kind = 'agent_md'),
    canonical_path    TEXT    NOT NULL CHECK (length(canonical_path) BETWEEN 1 AND 4096),
    bound_at          INTEGER NOT NULL CHECK (typeof(bound_at) = 'integer'),
    binding_sha256    TEXT    NOT NULL CHECK (length(binding_sha256) = 64)
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_resource_bindings_path
    ON resource_bindings(canonical_path);
"#;

pub(crate) const RESOURCE_PROPOSALS_SCHEMA: &str = r#"
CREATE TABLE IF NOT EXISTS resource_change_proposals (
    proposal_id              TEXT    NOT NULL PRIMARY KEY CHECK (length(proposal_id) = 64),
    resource_id              TEXT    NOT NULL CHECK (length(resource_id) BETWEEN 1 AND 512),
    producer_id              TEXT    NOT NULL CHECK (length(producer_id) BETWEEN 1 AND 256),
    proposed_at               INTEGER NOT NULL CHECK (typeof(proposed_at) = 'integer' AND proposed_at >= 0),
    current_content          BLOB    NOT NULL CHECK (length(current_content) BETWEEN 1 AND 1048576),
    candidate_content        BLOB    NOT NULL CHECK (length(candidate_content) BETWEEN 1 AND 1048576),
    proposal_receipt_json    TEXT    NOT NULL CHECK (length(proposal_receipt_json) >= 2),
    record_sha256            TEXT    NOT NULL CHECK (length(record_sha256) = 64),
    UNIQUE (record_sha256)
);
CREATE INDEX IF NOT EXISTS idx_resource_change_proposals_resource_proposed
    ON resource_change_proposals(resource_id, proposed_at DESC);
"#;

pub(crate) const RESOURCE_PROPOSAL_REVIEWS_SCHEMA: &str = r#"
CREATE TABLE IF NOT EXISTS resource_proposal_review_observations (
    review_id              TEXT    NOT NULL PRIMARY KEY CHECK (length(review_id) = 64),
    proposal_id            TEXT    NOT NULL CHECK (length(proposal_id) = 64),
    reviewer_id            TEXT    NOT NULL CHECK (length(reviewer_id) BETWEEN 1 AND 256),
    reviewed_at            INTEGER NOT NULL CHECK (typeof(reviewed_at) = 'integer' AND reviewed_at >= 0),
    disposition            TEXT    NOT NULL CHECK (disposition IN ('accept_candidate', 'reject_candidate', 'defer')),
    reason                 TEXT    NOT NULL CHECK (length(reason) BETWEEN 1 AND 4096),
    proposal_record_sha256 TEXT    NOT NULL CHECK (length(proposal_record_sha256) = 64),
    record_sha256          TEXT    NOT NULL CHECK (length(record_sha256) = 64),
    UNIQUE (record_sha256),
    FOREIGN KEY (proposal_id) REFERENCES resource_change_proposals(proposal_id)
);
CREATE INDEX IF NOT EXISTS idx_resource_proposal_review_observations_proposal_reviewed
    ON resource_proposal_review_observations(proposal_id, reviewed_at DESC);
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
pub struct ResourceBindingRecord {
    pub resource_id: String,
    pub resource_kind: String,
    pub canonical_path: String,
    pub bound_at: i64,
    pub binding_sha256: String,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct AgentMdBaselineAdmission {
    pub resource_id: String,
    pub path: PathBuf,
    pub observed_at: i64,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct AgentMdBaselineReceipt {
    pub schema: String,
    pub binding: ResourceBindingRecord,
    pub version: ResourceVersionRecord,
    pub binding_created: bool,
    pub version_created: bool,
    pub content_readback_observed_before_commit: bool,
    pub path_identity_observed_before_commit: bool,
    pub observation_scope: String,
    pub external_writer_exclusion_verified: bool,
    pub resource_content_mutated: bool,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct AgentMdCasCommit {
    pub resource_id: String,
    pub path: PathBuf,
    pub expected_content_sha256: String,
    pub proposed_content: Vec<u8>,
    pub observed_at: i64,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct AgentMdCasCommitReceipt {
    pub schema: String,
    pub binding: ResourceBindingRecord,
    pub version: ResourceVersionRecord,
    pub expected_content_sha256: String,
    pub proposed_content_sha256: String,
    pub content_readback_verified: bool,
    pub resource_content_mutated: bool,
    pub rollback_performed: bool,
    pub rollback_verified: bool,
    pub external_writer_exclusion_verified: bool,
    pub commit_scope: String,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct AgentMdCasRollback {
    pub resource_id: String,
    pub path: PathBuf,
    pub expected_content_sha256: String,
    pub target_version: u64,
    pub target_content: Vec<u8>,
    pub observed_at: i64,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct AgentMdCasRollbackReceipt {
    pub schema: String,
    pub binding: ResourceBindingRecord,
    pub previous_version: ResourceVersionRecord,
    pub target_version: u64,
    pub version: ResourceVersionRecord,
    pub expected_content_sha256: String,
    pub restored_content_sha256: String,
    pub content_readback_verified: bool,
    pub resource_content_mutated: bool,
    pub rollback_performed: bool,
    pub rollback_verified: bool,
    pub external_writer_exclusion_verified: bool,
    pub rollback_scope: String,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct AgentMdChangeProposal {
    pub resource_id: String,
    pub path: PathBuf,
    pub expected_current_content_sha256: Option<String>,
    pub target_version: Option<u64>,
    pub proposed_content: Vec<u8>,
    pub observed_at: i64,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct AgentMdChangeProposalReceipt {
    pub schema: String,
    pub binding: ResourceBindingRecord,
    pub current_version: ResourceVersionRecord,
    pub current_content_sha256: String,
    pub proposed_content_sha256: String,
    pub target_version: Option<u64>,
    pub target_content_hash_match: Option<bool>,
    pub current_bytes: u64,
    pub proposed_bytes: u64,
    pub current_lines: u64,
    pub proposed_lines: u64,
    pub added_lines: u64,
    pub removed_lines: u64,
    pub changed_lines: u64,
    pub content_changed: bool,
    pub proposal_only: bool,
    pub resource_content_mutated: bool,
    pub lineage_mutated: bool,
    pub proposal_scope: String,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct AgentMdChangeProposalReview {
    pub resource_id: String,
    pub path: PathBuf,
    pub proposal: AgentMdChangeProposalReceipt,
    pub reviewed_at: i64,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct AgentMdChangeProposalReviewReceipt {
    pub schema: String,
    pub proposal: AgentMdChangeProposalReceipt,
    pub reviewed_at: i64,
    pub status: String,
    pub violations: Vec<String>,
    pub receipt_invariants_verified: bool,
    pub observed_state_current: bool,
    pub source_authenticity_verified: bool,
    pub candidate_content_available: bool,
    pub semantic_review_performed: bool,
    pub eligible_for_human_review: bool,
    pub automatic_apply_allowed: bool,
    pub proposal_only: bool,
    pub resource_content_mutated: bool,
    pub lineage_mutated: bool,
    pub review_scope: String,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct AgentMdPersistedProposalCreate {
    pub proposal: AgentMdChangeProposal,
    pub producer_id: String,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct AgentMdPersistedProposalArtifact {
    pub schema: String,
    pub proposal_id: String,
    pub resource_id: String,
    pub producer_id: String,
    pub proposed_at: i64,
    pub current_content: Vec<u8>,
    pub candidate_content: Vec<u8>,
    pub proposal: AgentMdChangeProposalReceipt,
    pub record_sha256: String,
    pub persistence_integrity_verified: bool,
    pub source_authenticity_verified: bool,
    pub candidate_content_available: bool,
    pub semantic_review_performed: bool,
    pub eligible_for_human_review: bool,
    pub automatic_apply_allowed: bool,
    pub resource_content_mutated: bool,
    pub lineage_mutated: bool,
    pub artifact_scope: String,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct AgentMdProposalReviewObservationCreate {
    pub proposal_id: String,
    pub reviewer_id: String,
    pub reviewed_at: i64,
    pub disposition: String,
    pub reason: String,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct AgentMdProposalReviewObservationArtifact {
    pub schema: String,
    pub review_id: String,
    pub proposal_id: String,
    pub reviewer_id: String,
    pub reviewed_at: i64,
    pub disposition: String,
    pub reason: String,
    pub proposal_record_sha256: String,
    pub record_sha256: String,
    pub persistence_integrity_verified: bool,
    pub proposal_integrity_verified: bool,
    pub reviewer_identity_authenticated: bool,
    pub human_review_claimed: bool,
    pub human_review_authenticated: bool,
    pub source_authenticity_verified: bool,
    pub semantic_review_authority_granted: bool,
    pub automatic_apply_allowed: bool,
    pub resource_content_mutated: bool,
    pub lineage_mutated: bool,
    pub artifact_scope: String,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct AgentMdProposalReviewSnapshot {
    pub schema: String,
    pub proposal_id: String,
    pub proposal_record_sha256: String,
    pub observations: Vec<AgentMdProposalReviewObservationArtifact>,
    pub observation_count: u64,
    pub accept_candidate_count: u64,
    pub reject_candidate_count: u64,
    pub defer_count: u64,
    pub distinct_disposition_count: u64,
    pub no_observations: bool,
    pub conflicting_dispositions_observed: bool,
    pub snapshot_sha256: String,
    pub bounded_snapshot_complete: bool,
    pub snapshot_integrity_verified: bool,
    pub proposal_integrity_verified: bool,
    pub all_observations_integrity_verified: bool,
    pub external_writer_exclusion_verified: bool,
    pub reviewer_identities_authenticated: bool,
    pub human_reviews_authenticated: bool,
    pub semantic_review_authority_granted: bool,
    pub quorum_established: bool,
    pub winner_selected: bool,
    pub eligible_for_apply: bool,
    pub automatic_apply_allowed: bool,
    pub resource_content_mutated: bool,
    pub lineage_mutated: bool,
    pub snapshot_scope: String,
}

pub fn persisted_proposal_record_sha256(
    resource_id: &str,
    producer_id: &str,
    proposed_at: i64,
    current_content: &[u8],
    candidate_content: &[u8],
    proposal: &AgentMdChangeProposalReceipt,
) -> String {
    let mut hasher = Sha256::new();
    update_framed(
        &mut hasher,
        RESOURCE_PERSISTED_PROPOSAL_HASH_DOMAIN.as_bytes(),
    );
    update_framed(&mut hasher, resource_id.as_bytes());
    update_framed(&mut hasher, producer_id.as_bytes());
    update_framed(&mut hasher, &proposed_at.to_be_bytes());
    update_framed(&mut hasher, current_content);
    update_framed(&mut hasher, candidate_content);
    let receipt =
        serde_json::to_vec(proposal).expect("proposal receipt serialization is infallible");
    update_framed(&mut hasher, &receipt);
    hex_digest(hasher.finalize())
}

pub fn proposal_review_observation_record_sha256(
    proposal_id: &str,
    reviewer_id: &str,
    reviewed_at: i64,
    disposition: &str,
    reason: &str,
    proposal_record_sha256: &str,
) -> String {
    let mut hasher = Sha256::new();
    update_framed(
        &mut hasher,
        RESOURCE_PROPOSAL_REVIEW_OBSERVATION_HASH_DOMAIN.as_bytes(),
    );
    update_framed(&mut hasher, proposal_id.as_bytes());
    update_framed(&mut hasher, reviewer_id.as_bytes());
    update_framed(&mut hasher, &reviewed_at.to_be_bytes());
    update_framed(&mut hasher, disposition.as_bytes());
    update_framed(&mut hasher, reason.as_bytes());
    update_framed(&mut hasher, proposal_record_sha256.as_bytes());
    hex_digest(hasher.finalize())
}

pub fn proposal_review_snapshot_sha256(
    proposal_id: &str,
    proposal_record_sha256: &str,
    ordered_review_record_sha256s: &[String],
) -> String {
    let mut hasher = Sha256::new();
    update_framed(
        &mut hasher,
        RESOURCE_PROPOSAL_REVIEW_SNAPSHOT_HASH_DOMAIN.as_bytes(),
    );
    update_framed(&mut hasher, proposal_id.as_bytes());
    update_framed(&mut hasher, proposal_record_sha256.as_bytes());
    update_framed(
        &mut hasher,
        &(ordered_review_record_sha256s.len() as u64).to_be_bytes(),
    );
    for record_sha256 in ordered_review_record_sha256s {
        update_framed(&mut hasher, record_sha256.as_bytes());
    }
    hex_digest(hasher.finalize())
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

fn bindings_migration_sha256() -> String {
    let mut hasher = Sha256::new();
    update_framed(
        &mut hasher,
        b"agent-bridge/sepl/resource-bindings-migration/v0",
    );
    update_framed(&mut hasher, RESOURCE_BINDINGS_SCHEMA.as_bytes());
    hex_digest(hasher.finalize())
}

fn proposals_migration_sha256() -> String {
    let mut hasher = Sha256::new();
    update_framed(
        &mut hasher,
        b"agent-bridge/sepl/resource-proposals-migration/v0",
    );
    update_framed(&mut hasher, RESOURCE_PROPOSALS_SCHEMA.as_bytes());
    hex_digest(hasher.finalize())
}

fn proposal_reviews_migration_sha256() -> String {
    let mut hasher = Sha256::new();
    update_framed(
        &mut hasher,
        b"agent-bridge/sepl/resource-proposal-reviews-migration/v0",
    );
    update_framed(&mut hasher, RESOURCE_PROPOSAL_REVIEWS_SCHEMA.as_bytes());
    hex_digest(hasher.finalize())
}

fn schema_mismatch(message: impl Into<String>) -> rusqlite::Error {
    rusqlite::Error::InvalidParameterName(format!(
        "resource_versions schema mismatch: {}",
        message.into()
    ))
}

fn bindings_schema_mismatch(message: impl Into<String>) -> rusqlite::Error {
    rusqlite::Error::InvalidParameterName(format!(
        "resource_bindings schema mismatch: {}",
        message.into()
    ))
}

fn proposals_schema_mismatch(message: impl Into<String>) -> rusqlite::Error {
    rusqlite::Error::InvalidParameterName(format!(
        "resource_change_proposals schema mismatch: {}",
        message.into()
    ))
}

fn proposal_reviews_schema_mismatch(message: impl Into<String>) -> rusqlite::Error {
    rusqlite::Error::InvalidParameterName(format!(
        "resource_proposal_review_observations schema mismatch: {}",
        message.into()
    ))
}

fn canonical_schema_sql(sql: &str) -> String {
    sql.split_whitespace()
        .collect::<Vec<_>>()
        .join(" ")
        .replace("CREATE TABLE IF NOT EXISTS", "CREATE TABLE")
        .replace("CREATE UNIQUE INDEX IF NOT EXISTS", "CREATE UNIQUE INDEX")
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
    migrate_or_verify_bindings(connection)?;
    migrate_or_verify_proposals(connection)?;
    migrate_or_verify_proposal_reviews(connection)?;
    Ok(())
}

fn migrate_or_verify_bindings(connection: &rusqlite::Connection) -> rusqlite::Result<()> {
    connection.execute_batch("SAVEPOINT sepl_resource_bindings_migration")?;
    match migrate_or_verify_bindings_inner(connection) {
        Ok(()) => connection.execute_batch("RELEASE sepl_resource_bindings_migration"),
        Err(error) => {
            if let Err(rollback_error) = connection.execute_batch(
                "ROLLBACK TO sepl_resource_bindings_migration;
                 RELEASE sepl_resource_bindings_migration;",
            ) {
                return Err(bindings_schema_mismatch(format!(
                    "{error}; migration rollback failed: {rollback_error}"
                )));
            }
            Err(error)
        }
    }
}

fn migrate_or_verify_bindings_inner(connection: &rusqlite::Connection) -> rusqlite::Result<()> {
    let table_exists: bool = connection.query_row(
        "SELECT EXISTS(SELECT 1 FROM sqlite_master \
         WHERE type='table' AND name='resource_bindings')",
        [],
        |row| row.get(0),
    )?;
    if !table_exists {
        connection.execute_batch(RESOURCE_BINDINGS_SCHEMA)?;
    }

    let mut statement = connection.prepare("PRAGMA table_info('resource_bindings')")?;
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
        ("canonical_path".to_string(), "TEXT".to_string(), 1, 0),
        ("bound_at".to_string(), "INTEGER".to_string(), 1, 0),
        ("binding_sha256".to_string(), "TEXT".to_string(), 1, 0),
    ];
    if columns != expected {
        return Err(bindings_schema_mismatch("column identity"));
    }

    let table_sql: String = connection.query_row(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='resource_bindings'",
        [],
        |row| row.get(0),
    )?;
    let expected_table_sql = RESOURCE_BINDINGS_SCHEMA
        .split_once(';')
        .map(|(table, _)| table)
        .ok_or_else(|| bindings_schema_mismatch("embedded table DDL"))?;
    if canonical_schema_sql(&table_sql) != canonical_schema_sql(expected_table_sql) {
        return Err(bindings_schema_mismatch("table DDL identity"));
    }

    connection.execute_batch(RESOURCE_BINDINGS_SCHEMA)?;
    let index_sql: String = connection.query_row(
        "SELECT sql FROM sqlite_master \
         WHERE type='index' AND name='idx_resource_bindings_path'",
        [],
        |row| row.get(0),
    )?;
    let expected_index_sql = RESOURCE_BINDINGS_SCHEMA
        .split_once(';')
        .map(|(_, index)| index.trim().trim_end_matches(';'))
        .ok_or_else(|| bindings_schema_mismatch("embedded index DDL"))?;
    if canonical_schema_sql(&index_sql) != canonical_schema_sql(expected_index_sql) {
        return Err(bindings_schema_mismatch("index DDL identity"));
    }

    let expected_digest = bindings_migration_sha256();
    connection.execute(
        "INSERT OR IGNORE INTO schema_meta(key, value) VALUES (?1, ?2)",
        rusqlite::params![RESOURCE_BINDINGS_MIGRATION_META_KEY, expected_digest],
    )?;
    let stored_digest: String = connection.query_row(
        "SELECT value FROM schema_meta WHERE key=?1",
        [RESOURCE_BINDINGS_MIGRATION_META_KEY],
        |row| row.get(0),
    )?;
    if stored_digest != bindings_migration_sha256() {
        return Err(bindings_schema_mismatch("migration digest"));
    }
    Ok(())
}

fn migrate_or_verify_proposals(connection: &rusqlite::Connection) -> rusqlite::Result<()> {
    connection.execute_batch("SAVEPOINT sepl_resource_proposals_migration")?;
    let result = (|| {
        let exists: bool = connection.query_row(
            "SELECT EXISTS(SELECT 1 FROM sqlite_master WHERE type='table' AND name='resource_change_proposals')",
            [],
            |row| row.get(0),
        )?;
        if !exists {
            connection.execute_batch(RESOURCE_PROPOSALS_SCHEMA)?;
        }
        let mut statement = connection.prepare("PRAGMA table_info('resource_change_proposals')")?;
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
            ("proposal_id".to_string(), "TEXT".to_string(), 1, 1),
            ("resource_id".to_string(), "TEXT".to_string(), 1, 0),
            ("producer_id".to_string(), "TEXT".to_string(), 1, 0),
            ("proposed_at".to_string(), "INTEGER".to_string(), 1, 0),
            ("current_content".to_string(), "BLOB".to_string(), 1, 0),
            ("candidate_content".to_string(), "BLOB".to_string(), 1, 0),
            (
                "proposal_receipt_json".to_string(),
                "TEXT".to_string(),
                1,
                0,
            ),
            ("record_sha256".to_string(), "TEXT".to_string(), 1, 0),
        ];
        if columns != expected {
            return Err(proposals_schema_mismatch("column identity"));
        }
        let table_sql: String = connection.query_row(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name='resource_change_proposals'",
            [],
            |row| row.get(0),
        )?;
        let expected_table_sql = RESOURCE_PROPOSALS_SCHEMA
            .split_once(';')
            .map(|(table, _)| table)
            .ok_or_else(|| proposals_schema_mismatch("embedded table DDL"))?;
        if canonical_schema_sql(&table_sql) != canonical_schema_sql(expected_table_sql) {
            return Err(proposals_schema_mismatch("table DDL identity"));
        }
        connection.execute_batch(RESOURCE_PROPOSALS_SCHEMA)?;
        let index_sql: String = connection.query_row(
            "SELECT sql FROM sqlite_master WHERE type='index' AND name='idx_resource_change_proposals_resource_proposed'",
            [],
            |row| row.get(0),
        )?;
        let expected_index_sql = RESOURCE_PROPOSALS_SCHEMA
            .split_once(';')
            .map(|(_, index)| index.trim().trim_end_matches(';'))
            .ok_or_else(|| proposals_schema_mismatch("embedded index DDL"))?;
        if canonical_schema_sql(&index_sql) != canonical_schema_sql(expected_index_sql) {
            return Err(proposals_schema_mismatch("index DDL identity"));
        }
        let expected_digest = proposals_migration_sha256();
        connection.execute(
            "INSERT OR IGNORE INTO schema_meta(key, value) VALUES (?1, ?2)",
            rusqlite::params![RESOURCE_PROPOSALS_MIGRATION_META_KEY, expected_digest],
        )?;
        let stored: String = connection.query_row(
            "SELECT value FROM schema_meta WHERE key=?1",
            [RESOURCE_PROPOSALS_MIGRATION_META_KEY],
            |row| row.get(0),
        )?;
        if stored != proposals_migration_sha256() {
            return Err(proposals_schema_mismatch("migration digest"));
        }
        Ok(())
    })();
    match result {
        Ok(()) => connection.execute_batch("RELEASE sepl_resource_proposals_migration"),
        Err(error) => {
            connection.execute_batch(
                "ROLLBACK TO sepl_resource_proposals_migration; RELEASE sepl_resource_proposals_migration;",
            )?;
            Err(error)
        }
    }
}

fn migrate_or_verify_proposal_reviews(connection: &rusqlite::Connection) -> rusqlite::Result<()> {
    connection.execute_batch("SAVEPOINT sepl_resource_proposal_reviews_migration")?;
    let result = (|| {
        let exists: bool = connection.query_row(
            "SELECT EXISTS(SELECT 1 FROM sqlite_master WHERE type='table' AND name='resource_proposal_review_observations')",
            [],
            |row| row.get(0),
        )?;
        if !exists {
            connection.execute_batch(RESOURCE_PROPOSAL_REVIEWS_SCHEMA)?;
        }
        let mut statement =
            connection.prepare("PRAGMA table_info('resource_proposal_review_observations')")?;
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
            ("review_id".to_string(), "TEXT".to_string(), 1, 1),
            ("proposal_id".to_string(), "TEXT".to_string(), 1, 0),
            ("reviewer_id".to_string(), "TEXT".to_string(), 1, 0),
            ("reviewed_at".to_string(), "INTEGER".to_string(), 1, 0),
            ("disposition".to_string(), "TEXT".to_string(), 1, 0),
            ("reason".to_string(), "TEXT".to_string(), 1, 0),
            (
                "proposal_record_sha256".to_string(),
                "TEXT".to_string(),
                1,
                0,
            ),
            ("record_sha256".to_string(), "TEXT".to_string(), 1, 0),
        ];
        if columns != expected {
            return Err(proposal_reviews_schema_mismatch("column identity"));
        }
        let table_sql: String = connection.query_row(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name='resource_proposal_review_observations'",
            [],
            |row| row.get(0),
        )?;
        let expected_table_sql = RESOURCE_PROPOSAL_REVIEWS_SCHEMA
            .split_once(';')
            .map(|(table, _)| table)
            .ok_or_else(|| proposal_reviews_schema_mismatch("embedded table DDL"))?;
        if canonical_schema_sql(&table_sql) != canonical_schema_sql(expected_table_sql) {
            return Err(proposal_reviews_schema_mismatch("table DDL identity"));
        }
        connection.execute_batch(RESOURCE_PROPOSAL_REVIEWS_SCHEMA)?;
        let index_sql: String = connection.query_row(
            "SELECT sql FROM sqlite_master WHERE type='index' AND name='idx_resource_proposal_review_observations_proposal_reviewed'",
            [],
            |row| row.get(0),
        )?;
        let expected_index_sql = RESOURCE_PROPOSAL_REVIEWS_SCHEMA
            .split_once(';')
            .map(|(_, index)| index.trim().trim_end_matches(';'))
            .ok_or_else(|| proposal_reviews_schema_mismatch("embedded index DDL"))?;
        if canonical_schema_sql(&index_sql) != canonical_schema_sql(expected_index_sql) {
            return Err(proposal_reviews_schema_mismatch("index DDL identity"));
        }
        let expected_digest = proposal_reviews_migration_sha256();
        connection.execute(
            "INSERT OR IGNORE INTO schema_meta(key, value) VALUES (?1, ?2)",
            rusqlite::params![
                RESOURCE_PROPOSAL_REVIEWS_MIGRATION_META_KEY,
                expected_digest
            ],
        )?;
        let stored: String = connection.query_row(
            "SELECT value FROM schema_meta WHERE key=?1",
            [RESOURCE_PROPOSAL_REVIEWS_MIGRATION_META_KEY],
            |row| row.get(0),
        )?;
        if stored != proposal_reviews_migration_sha256() {
            return Err(proposal_reviews_schema_mismatch("migration digest"));
        }
        Ok(())
    })();
    match result {
        Ok(()) => connection.execute_batch("RELEASE sepl_resource_proposal_reviews_migration"),
        Err(error) => {
            if let Err(rollback_error) = connection.execute_batch(
                "ROLLBACK TO sepl_resource_proposal_reviews_migration; RELEASE sepl_resource_proposal_reviews_migration;",
            ) {
                return Err(proposal_reviews_schema_mismatch(format!(
                    "{error}; migration rollback failed: {rollback_error}"
                )));
            }
            Err(error)
        }
    }
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

fn hex_digest(digest: impl AsRef<[u8]>) -> String {
    digest
        .as_ref()
        .iter()
        .map(|byte| format!("{byte:02x}"))
        .collect()
}

pub fn resource_content_sha256(content: &[u8]) -> String {
    hex_digest(Sha256::digest(content))
}

pub fn resource_binding_sha256(binding: &ResourceBindingRecord) -> String {
    let mut hasher = Sha256::new();
    for value in [
        RESOURCE_BINDING_HASH_DOMAIN.as_bytes(),
        binding.resource_id.as_bytes(),
        binding.resource_kind.as_bytes(),
        binding.canonical_path.as_bytes(),
        binding.bound_at.to_string().as_bytes(),
    ] {
        update_framed(&mut hasher, value);
    }
    hex_digest(hasher.finalize())
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
    hex_digest(hasher.finalize())
}

pub(crate) fn is_lower_hex_sha256(value: &str) -> bool {
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

    #[test]
    fn p0_migration_digest_remains_deployed_identity() {
        assert_eq!(
            migration_sha256(),
            "a7853b4266f76eb462ced318554de47818e6d81df0ad58ce546ebcdf4e63d8e7"
        );
    }

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
        let binding_objects: i64 = connection
            .query_row(
                "SELECT COUNT(*) FROM sqlite_master \
                 WHERE name IN ('resource_bindings', 'idx_resource_bindings_path')",
                [],
                |row| row.get(0),
            )
            .expect("query binding schema");
        assert_eq!(binding_objects, 2);
        let binding_digest: String = connection
            .query_row(
                "SELECT value FROM schema_meta WHERE key='resource_bindings.migration_sha256'",
                [],
                |row| row.get(0),
            )
            .expect("query binding migration digest");
        assert_eq!(binding_digest, bindings_migration_sha256());
        let proposal_objects: i64 = connection
            .query_row(
                "SELECT COUNT(*) FROM sqlite_master WHERE name IN (
                    'resource_change_proposals',
                    'idx_resource_change_proposals_resource_proposed'
                )",
                [],
                |row| row.get(0),
            )
            .expect("query proposal schema");
        assert_eq!(proposal_objects, 2);
        let proposal_digest: String = connection
            .query_row(
                "SELECT value FROM schema_meta WHERE key='resource_proposals.migration_sha256'",
                [],
                |row| row.get(0),
            )
            .expect("query proposal migration digest");
        assert_eq!(proposal_digest, proposals_migration_sha256());
        let review_objects: i64 = connection
            .query_row(
                "SELECT COUNT(*) FROM sqlite_master WHERE name IN (
                    'resource_proposal_review_observations',
                    'idx_resource_proposal_review_observations_proposal_reviewed'
                )",
                [],
                |row| row.get(0),
            )
            .expect("query review observation schema");
        assert_eq!(review_objects, 2);
        let review_digest: String = connection
            .query_row(
                "SELECT value FROM schema_meta WHERE key='resource_proposal_reviews.migration_sha256'",
                [],
                |row| row.get(0),
            )
            .expect("query review observation migration digest");
        assert_eq!(review_digest, proposal_reviews_migration_sha256());
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
                "DROP INDEX idx_resource_proposal_review_observations_proposal_reviewed;
                 DROP TABLE resource_proposal_review_observations;
                 DROP INDEX idx_resource_change_proposals_resource_proposed;
                 DROP TABLE resource_change_proposals;
                 DROP INDEX idx_resource_bindings_path;
                 DROP TABLE resource_bindings;
                 DROP TABLE resource_versions;
                 DELETE FROM schema_meta
                 WHERE key IN (
                     'resource_lineage.migration_sha256',
                     'resource_bindings.migration_sha256',
                     'resource_proposals.migration_sha256',
                     'resource_proposal_reviews.migration_sha256'
                 );",
            )
            .expect("rewind P0 and P1A0 rungs");
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
    async fn incompatible_existing_bindings_table_fails_closed() {
        let directory = tempfile::tempdir().expect("tempdir");
        let database = directory.path().join("state.db");
        let initial = SqliteStore::open(&database).await.expect("initial open");
        drop(initial);
        let connection = rusqlite::Connection::open(&database).expect("open raw database");
        connection
            .execute_batch(
                "DROP INDEX idx_resource_bindings_path;
                 DROP TABLE resource_bindings;
                 DELETE FROM schema_meta WHERE key='resource_bindings.migration_sha256';
                 CREATE TABLE resource_bindings (resource_id TEXT PRIMARY KEY);",
            )
            .expect("install incompatible bindings table");
        drop(connection);

        let error = SqliteStore::open(&database)
            .await
            .err()
            .expect("incompatible bindings table must fail");
        assert!(error
            .to_string()
            .contains("resource_bindings schema mismatch"));
    }

    #[tokio::test]
    async fn incompatible_existing_proposals_table_fails_closed() {
        let directory = tempfile::tempdir().expect("tempdir");
        let database = directory.path().join("state.db");
        let initial = SqliteStore::open(&database).await.expect("initial open");
        drop(initial);
        let connection = rusqlite::Connection::open(&database).expect("open raw database");
        connection
            .execute_batch(
                "DROP INDEX idx_resource_change_proposals_resource_proposed;
                 DROP TABLE resource_change_proposals;
                 DELETE FROM schema_meta WHERE key='resource_proposals.migration_sha256';
                 CREATE TABLE resource_change_proposals (proposal_id TEXT PRIMARY KEY);",
            )
            .expect("install incompatible proposals table");
        drop(connection);

        let error = SqliteStore::open(&database)
            .await
            .err()
            .expect("incompatible proposals table must fail");
        assert!(error
            .to_string()
            .contains("resource_change_proposals schema mismatch"));
    }

    #[tokio::test]
    async fn incompatible_existing_proposal_reviews_table_fails_closed() {
        let directory = tempfile::tempdir().expect("tempdir");
        let database = directory.path().join("state.db");
        let initial = SqliteStore::open(&database).await.expect("initial open");
        drop(initial);
        let connection = rusqlite::Connection::open(&database).expect("open raw database");
        connection
            .execute_batch(
                "DROP INDEX idx_resource_proposal_review_observations_proposal_reviewed;
                 DROP TABLE resource_proposal_review_observations;
                 DELETE FROM schema_meta WHERE key='resource_proposal_reviews.migration_sha256';
                 CREATE TABLE resource_proposal_review_observations (review_id TEXT PRIMARY KEY);",
            )
            .expect("install incompatible review observations table");
        drop(connection);

        let error = SqliteStore::open(&database)
            .await
            .err()
            .expect("incompatible review observations table must fail");
        assert!(error
            .to_string()
            .contains("resource_proposal_review_observations schema mismatch"));
    }

    #[tokio::test]
    async fn bindings_migration_failure_rolls_back_partial_ddl() {
        let directory = tempfile::tempdir().expect("tempdir");
        let database = directory.path().join("state.db");
        let initial = SqliteStore::open(&database).await.expect("initial open");
        drop(initial);
        let connection = rusqlite::Connection::open(&database).expect("open raw database");
        connection
            .execute_batch(
                "DROP INDEX idx_resource_bindings_path;
                 DROP TABLE resource_bindings;
                 DELETE FROM schema_meta WHERE key='resource_bindings.migration_sha256';
                 CREATE TABLE idx_resource_bindings_path (collision TEXT);",
            )
            .expect("install index-name collision");
        drop(connection);

        SqliteStore::open(&database)
            .await
            .err()
            .expect("colliding index identity must fail migration");

        let connection = rusqlite::Connection::open(&database).expect("reopen raw database");
        let binding_table_count: i64 = connection
            .query_row(
                "SELECT COUNT(*) FROM sqlite_master \
                 WHERE type='table' AND name='resource_bindings'",
                [],
                |row| row.get(0),
            )
            .expect("count binding table");
        let digest_count: i64 = connection
            .query_row(
                "SELECT COUNT(*) FROM schema_meta \
                 WHERE key='resource_bindings.migration_sha256'",
                [],
                |row| row.get(0),
            )
            .expect("count migration digest");
        assert_eq!(binding_table_count, 0);
        assert_eq!(digest_count, 0);
    }

    #[tokio::test]
    async fn proposals_migration_failure_rolls_back_partial_ddl() {
        let directory = tempfile::tempdir().expect("tempdir");
        let database = directory.path().join("state.db");
        let initial = SqliteStore::open(&database).await.expect("initial open");
        drop(initial);
        let connection = rusqlite::Connection::open(&database).expect("open raw database");
        connection
            .execute_batch(
                "DROP INDEX idx_resource_change_proposals_resource_proposed;
                 DROP TABLE resource_change_proposals;
                 DELETE FROM schema_meta WHERE key='resource_proposals.migration_sha256';
                 CREATE TABLE idx_resource_change_proposals_resource_proposed (collision TEXT);",
            )
            .expect("install proposal-index name collision");
        drop(connection);

        SqliteStore::open(&database)
            .await
            .err()
            .expect("colliding proposal index must fail migration");

        let connection = rusqlite::Connection::open(&database).expect("reopen raw database");
        let table_count: i64 = connection
            .query_row(
                "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='resource_change_proposals'",
                [],
                |row| row.get(0),
            )
            .expect("count proposal table");
        let digest_count: i64 = connection
            .query_row(
                "SELECT COUNT(*) FROM schema_meta WHERE key='resource_proposals.migration_sha256'",
                [],
                |row| row.get(0),
            )
            .expect("count proposal migration digest");
        assert_eq!(table_count, 0);
        assert_eq!(digest_count, 0);
    }

    #[tokio::test]
    async fn proposal_reviews_migration_failure_rolls_back_partial_ddl() {
        let directory = tempfile::tempdir().expect("tempdir");
        let database = directory.path().join("state.db");
        let initial = SqliteStore::open(&database).await.expect("initial open");
        drop(initial);
        let connection = rusqlite::Connection::open(&database).expect("open raw database");
        connection
            .execute_batch(
                "DROP INDEX idx_resource_proposal_review_observations_proposal_reviewed;
                 DROP TABLE resource_proposal_review_observations;
                 DELETE FROM schema_meta WHERE key='resource_proposal_reviews.migration_sha256';
                 CREATE TABLE idx_resource_proposal_review_observations_proposal_reviewed (collision TEXT);",
            )
            .expect("install review-index name collision");
        drop(connection);

        SqliteStore::open(&database)
            .await
            .err()
            .expect("colliding review index must fail migration");

        let connection = rusqlite::Connection::open(&database).expect("reopen raw database");
        let table_count: i64 = connection
            .query_row(
                "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='resource_proposal_review_observations'",
                [],
                |row| row.get(0),
            )
            .expect("count review table");
        let digest_count: i64 = connection
            .query_row(
                "SELECT COUNT(*) FROM schema_meta WHERE key='resource_proposal_reviews.migration_sha256'",
                [],
                |row| row.get(0),
            )
            .expect("count review migration digest");
        assert_eq!(table_count, 0);
        assert_eq!(digest_count, 0);
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

    #[tokio::test]
    async fn admits_agent_md_baseline_with_binding_and_verified_genesis() {
        let directory = tempfile::tempdir().expect("tempdir");
        let database = directory.path().join("state.db");
        let agent_md = directory.path().join("AGENT.md");
        std::fs::write(&agent_md, "# Stable profile\n\nPrefer explicit evidence.\n")
            .expect("write AGENT.md");
        let store = SqliteStore::open(&database).await.expect("open store");

        let receipt = store
            .admit_agent_md_baseline(AgentMdBaselineAdmission {
                resource_id: "agent-profile".to_string(),
                path: agent_md.clone(),
                observed_at: 1_700_000_000,
            })
            .await
            .expect("admit baseline");

        assert_eq!(receipt.schema, RESOURCE_BASELINE_ADMISSION_SCHEMA);
        assert!(receipt.binding_created);
        assert!(receipt.version_created);
        assert!(receipt.content_readback_observed_before_commit);
        assert!(receipt.path_identity_observed_before_commit);
        assert_eq!(
            receipt.observation_scope,
            RESOURCE_BASELINE_OBSERVATION_SCOPE
        );
        assert!(!receipt.external_writer_exclusion_verified);
        assert!(!receipt.resource_content_mutated);
        assert_eq!(receipt.version.version, 1);
        assert_eq!(receipt.version.predecessor_version, None);
        assert_eq!(receipt.binding.resource_kind, "agent_md");
        assert_eq!(
            receipt.binding.canonical_path,
            std::fs::canonicalize(&agent_md)
                .expect("canonical path")
                .to_str()
                .expect("utf-8 path")
        );
        assert_eq!(
            receipt.binding.binding_sha256,
            resource_binding_sha256(&receipt.binding)
        );

        let report = store
            .resource_lineage_read("agent-profile", 32)
            .await
            .expect("read lineage");
        assert_eq!(report.status, "verified");
        assert_eq!(report.records, vec![receipt.version]);
        assert_eq!(
            std::fs::read_to_string(&agent_md).expect("read unchanged AGENT.md"),
            "# Stable profile\n\nPrefer explicit evidence.\n"
        );
    }

    #[tokio::test]
    async fn repeated_baseline_admission_is_idempotent() {
        let directory = tempfile::tempdir().expect("tempdir");
        let database = directory.path().join("state.db");
        let agent_md = directory.path().join("AGENT.md");
        std::fs::write(&agent_md, "# Stable profile\n").expect("write AGENT.md");
        let store = SqliteStore::open(&database).await.expect("open store");
        let request = AgentMdBaselineAdmission {
            resource_id: "agent-profile".to_string(),
            path: agent_md,
            observed_at: 1_700_000_000,
        };

        let first = store
            .admit_agent_md_baseline(request.clone())
            .await
            .expect("first admission");
        let second = store
            .admit_agent_md_baseline(AgentMdBaselineAdmission {
                observed_at: 1_800_000_000,
                ..request
            })
            .await
            .expect("idempotent admission");

        assert!(first.binding_created);
        assert!(first.version_created);
        assert!(!second.binding_created);
        assert!(!second.version_created);
        assert_eq!(first.binding, second.binding);
        assert_eq!(first.version, second.version);
    }

    #[cfg(unix)]
    #[tokio::test]
    async fn commits_agent_md_cas_and_appends_predecessor_bound_version() {
        let directory = tempfile::tempdir().expect("tempdir");
        let database = directory.path().join("state.db");
        let agent_md = directory.path().join("AGENT.md");
        let original = b"# Stable profile\n".to_vec();
        let proposed = b"# Updated profile\n\nKeep evidence explicit.\n".to_vec();
        std::fs::write(&agent_md, &original).expect("write AGENT.md");
        let store = SqliteStore::open(&database).await.expect("open store");
        let baseline = store
            .admit_agent_md_baseline(AgentMdBaselineAdmission {
                resource_id: "agent-profile".to_string(),
                path: agent_md.clone(),
                observed_at: 1_700_000_000,
            })
            .await
            .expect("admit baseline");

        let receipt = store
            .commit_agent_md_cas(AgentMdCasCommit {
                resource_id: "agent-profile".to_string(),
                path: agent_md.clone(),
                expected_content_sha256: resource_content_sha256(&original),
                proposed_content: proposed.clone(),
                observed_at: 1_700_000_001,
            })
            .await
            .expect("commit CAS");

        assert_eq!(receipt.schema, RESOURCE_CAS_COMMIT_SCHEMA);
        assert_eq!(receipt.version.version, 2);
        assert_eq!(
            receipt.version.predecessor_record_sha256,
            Some(baseline.version.record_sha256)
        );
        assert_eq!(
            receipt.version.content_sha256,
            resource_content_sha256(&proposed)
        );
        assert!(receipt.content_readback_verified);
        assert!(receipt.resource_content_mutated);
        assert!(!receipt.rollback_performed);
        assert!(!receipt.rollback_verified);
        assert!(!receipt.external_writer_exclusion_verified);
        assert_eq!(receipt.commit_scope, RESOURCE_CAS_COMMIT_SCOPE);
        assert_eq!(
            std::fs::read(&agent_md).expect("read committed AGENT.md"),
            proposed
        );

        let report = store
            .resource_lineage_read("agent-profile", 32)
            .await
            .expect("read lineage");
        assert_eq!(report.status, "verified");
        assert_eq!(report.records.len(), 2);
        assert_eq!(report.records[1], receipt.version);
    }

    #[cfg(unix)]
    #[tokio::test]
    async fn rolls_back_agent_md_to_verified_historical_content() {
        let directory = tempfile::tempdir().expect("tempdir");
        let database = directory.path().join("state.db");
        let agent_md = directory.path().join("AGENT.md");
        let original = b"# Stable profile\n".to_vec();
        let proposed = b"# Updated profile\n".to_vec();
        std::fs::write(&agent_md, &original).expect("write AGENT.md");
        let store = SqliteStore::open(&database).await.expect("open store");
        let baseline = store
            .admit_agent_md_baseline(AgentMdBaselineAdmission {
                resource_id: "agent-profile".to_string(),
                path: agent_md.clone(),
                observed_at: 1_700_000_000,
            })
            .await
            .expect("admit baseline");
        let committed = store
            .commit_agent_md_cas(AgentMdCasCommit {
                resource_id: "agent-profile".to_string(),
                path: agent_md.clone(),
                expected_content_sha256: resource_content_sha256(&original),
                proposed_content: proposed.clone(),
                observed_at: 1_700_000_001,
            })
            .await
            .expect("commit second version");

        let receipt = store
            .rollback_agent_md_cas(AgentMdCasRollback {
                resource_id: "agent-profile".to_string(),
                path: agent_md.clone(),
                expected_content_sha256: resource_content_sha256(&proposed),
                target_version: baseline.version.version,
                target_content: original.clone(),
                observed_at: 1_700_000_002,
            })
            .await
            .expect("rollback to baseline");

        assert_eq!(receipt.schema, RESOURCE_CAS_ROLLBACK_SCHEMA);
        assert_eq!(receipt.target_version, baseline.version.version);
        assert_eq!(receipt.previous_version, committed.version);
        assert_eq!(receipt.version.version, 3);
        assert_eq!(
            receipt.version.predecessor_record_sha256,
            Some(committed.version.record_sha256)
        );
        assert_eq!(
            receipt.restored_content_sha256,
            resource_content_sha256(&original)
        );
        assert!(receipt.content_readback_verified);
        assert!(receipt.rollback_performed);
        assert!(receipt.rollback_verified);
        assert_eq!(
            std::fs::read(&agent_md).expect("read rolled back AGENT.md"),
            original
        );
        let report = store
            .resource_lineage_read("agent-profile", 32)
            .await
            .expect("read lineage");
        assert_eq!(report.status, "verified");
        assert_eq!(report.records.len(), 3);
        assert_eq!(report.records[2], receipt.version);
    }

    #[cfg(unix)]
    #[tokio::test]
    async fn rollback_rejects_content_that_does_not_match_historical_hash() {
        let directory = tempfile::tempdir().expect("tempdir");
        let database = directory.path().join("state.db");
        let agent_md = directory.path().join("AGENT.md");
        let original = b"# Stable profile\n".to_vec();
        let proposed = b"# Updated profile\n".to_vec();
        std::fs::write(&agent_md, &original).expect("write AGENT.md");
        let store = SqliteStore::open(&database).await.expect("open store");
        let baseline = store
            .admit_agent_md_baseline(AgentMdBaselineAdmission {
                resource_id: "agent-profile".to_string(),
                path: agent_md.clone(),
                observed_at: 1_700_000_000,
            })
            .await
            .expect("admit baseline");
        store
            .commit_agent_md_cas(AgentMdCasCommit {
                resource_id: "agent-profile".to_string(),
                path: agent_md.clone(),
                expected_content_sha256: resource_content_sha256(&original),
                proposed_content: proposed.clone(),
                observed_at: 1_700_000_001,
            })
            .await
            .expect("commit second version");

        let error = store
            .rollback_agent_md_cas(AgentMdCasRollback {
                resource_id: "agent-profile".to_string(),
                path: agent_md.clone(),
                expected_content_sha256: resource_content_sha256(&proposed),
                target_version: baseline.version.version,
                target_content: b"# Forged historical body\n".to_vec(),
                observed_at: 1_700_000_002,
            })
            .await
            .expect_err("forged historical content must fail");
        assert!(error
            .to_string()
            .contains("does not match target lineage version"));
        assert_eq!(
            std::fs::read(&agent_md).expect("read unchanged AGENT.md"),
            proposed
        );
        let report = store
            .resource_lineage_read("agent-profile", 32)
            .await
            .expect("read lineage");
        assert_eq!(report.records.len(), 2);
        assert_eq!(report.records[1].version, 2);
    }

    #[cfg(unix)]
    #[tokio::test]
    async fn rollback_rejects_current_or_future_target_version() {
        let directory = tempfile::tempdir().expect("tempdir");
        let database = directory.path().join("state.db");
        let agent_md = directory.path().join("AGENT.md");
        let original = b"# Stable profile\n".to_vec();
        let proposed = b"# Updated profile\n".to_vec();
        std::fs::write(&agent_md, &original).expect("write AGENT.md");
        let store = SqliteStore::open(&database).await.expect("open store");
        store
            .admit_agent_md_baseline(AgentMdBaselineAdmission {
                resource_id: "agent-profile".to_string(),
                path: agent_md.clone(),
                observed_at: 1_700_000_000,
            })
            .await
            .expect("admit baseline");
        store
            .commit_agent_md_cas(AgentMdCasCommit {
                resource_id: "agent-profile".to_string(),
                path: agent_md.clone(),
                expected_content_sha256: resource_content_sha256(&original),
                proposed_content: proposed.clone(),
                observed_at: 1_700_000_001,
            })
            .await
            .expect("commit second version");

        for target_version in [2, 3] {
            let error = store
                .rollback_agent_md_cas(AgentMdCasRollback {
                    resource_id: "agent-profile".to_string(),
                    path: agent_md.clone(),
                    expected_content_sha256: resource_content_sha256(&proposed),
                    target_version,
                    target_content: proposed.clone(),
                    observed_at: 1_700_000_002,
                })
                .await
                .expect_err("current or future target must fail");
            assert!(error.to_string().contains("earlier lineage version"));
        }
        assert_eq!(
            std::fs::read(&agent_md).expect("read unchanged AGENT.md"),
            proposed
        );
    }

    #[cfg(unix)]
    #[tokio::test]
    async fn proposes_agent_md_change_without_mutating_file_or_lineage() {
        let directory = tempfile::tempdir().expect("tempdir");
        let database = directory.path().join("state.db");
        let agent_md = directory.path().join("AGENT.md");
        let original = b"# Stable profile\nkeep this line\n".to_vec();
        let proposed = b"# Stable profile\nreplace this line\nnew line\n".to_vec();
        std::fs::write(&agent_md, &original).expect("write AGENT.md");
        let store = SqliteStore::open(&database).await.expect("open store");
        let baseline = store
            .admit_agent_md_baseline(AgentMdBaselineAdmission {
                resource_id: "agent-profile".to_string(),
                path: agent_md.clone(),
                observed_at: 1_700_000_000,
            })
            .await
            .expect("admit baseline");

        let receipt = store
            .propose_agent_md_change(AgentMdChangeProposal {
                resource_id: "agent-profile".to_string(),
                path: agent_md.clone(),
                expected_current_content_sha256: Some(resource_content_sha256(&original)),
                target_version: None,
                proposed_content: proposed.clone(),
                observed_at: 1_700_000_001,
            })
            .await
            .expect("proposal");

        assert_eq!(receipt.schema, RESOURCE_CHANGE_PROPOSAL_SCHEMA);
        assert_eq!(receipt.current_version, baseline.version);
        assert_eq!(
            receipt.current_content_sha256,
            resource_content_sha256(&original)
        );
        assert_eq!(
            receipt.proposed_content_sha256,
            resource_content_sha256(&proposed)
        );
        assert_eq!(receipt.current_lines, 2);
        assert_eq!(receipt.proposed_lines, 3);
        assert_eq!(receipt.added_lines, 2);
        assert_eq!(receipt.removed_lines, 1);
        assert_eq!(receipt.changed_lines, 2);
        assert!(receipt.content_changed);
        assert!(receipt.proposal_only);
        assert!(!receipt.resource_content_mutated);
        assert!(!receipt.lineage_mutated);
        assert_eq!(
            std::fs::read(&agent_md).expect("read unchanged AGENT.md"),
            original
        );
        let report = store
            .resource_lineage_read("agent-profile", 32)
            .await
            .expect("read lineage");
        assert_eq!(report.records.len(), 1);
        assert_eq!(report.records[0], baseline.version);
    }

    #[cfg(unix)]
    #[tokio::test]
    async fn proposal_accepts_only_historical_body_bound_to_target_hash() {
        let directory = tempfile::tempdir().expect("tempdir");
        let database = directory.path().join("state.db");
        let agent_md = directory.path().join("AGENT.md");
        let original = b"# Stable profile\n".to_vec();
        let current = b"# Current profile\n".to_vec();
        std::fs::write(&agent_md, &original).expect("write AGENT.md");
        let store = SqliteStore::open(&database).await.expect("open store");
        let baseline = store
            .admit_agent_md_baseline(AgentMdBaselineAdmission {
                resource_id: "agent-profile".to_string(),
                path: agent_md.clone(),
                observed_at: 1_700_000_000,
            })
            .await
            .expect("admit baseline");
        store
            .commit_agent_md_cas(AgentMdCasCommit {
                resource_id: "agent-profile".to_string(),
                path: agent_md.clone(),
                expected_content_sha256: resource_content_sha256(&original),
                proposed_content: current.clone(),
                observed_at: 1_700_000_001,
            })
            .await
            .expect("commit current version");

        let receipt = store
            .propose_agent_md_change(AgentMdChangeProposal {
                resource_id: "agent-profile".to_string(),
                path: agent_md.clone(),
                expected_current_content_sha256: Some(resource_content_sha256(&current)),
                target_version: Some(baseline.version.version),
                proposed_content: original.clone(),
                observed_at: 1_700_000_002,
            })
            .await
            .expect("historical proposal");
        assert_eq!(receipt.target_version, Some(baseline.version.version));
        assert_eq!(receipt.target_content_hash_match, Some(true));
        assert_eq!(receipt.current_version.version, 2);
        assert!(!receipt.resource_content_mutated);
        assert!(!receipt.lineage_mutated);

        let error = store
            .propose_agent_md_change(AgentMdChangeProposal {
                resource_id: "agent-profile".to_string(),
                path: agent_md.clone(),
                expected_current_content_sha256: Some(resource_content_sha256(&current)),
                target_version: Some(baseline.version.version),
                proposed_content: b"# Forged historical body\n".to_vec(),
                observed_at: 1_700_000_003,
            })
            .await
            .expect_err("forged target body must fail");
        assert!(error
            .to_string()
            .contains("does not match target lineage version"));
        assert_eq!(
            std::fs::read(&agent_md).expect("read unchanged AGENT.md"),
            current
        );
    }

    #[cfg(unix)]
    #[tokio::test]
    async fn reviews_current_proposal_without_mutating_file_or_lineage() {
        let directory = tempfile::tempdir().expect("tempdir");
        let database = directory.path().join("state.db");
        let agent_md = directory.path().join("AGENT.md");
        let original = b"# Stable profile\nkeep this line\n".to_vec();
        std::fs::write(&agent_md, &original).expect("write AGENT.md");
        let store = SqliteStore::open(&database).await.expect("open store");
        store
            .admit_agent_md_baseline(AgentMdBaselineAdmission {
                resource_id: "agent-profile".to_string(),
                path: agent_md.clone(),
                observed_at: 1_700_000_000,
            })
            .await
            .expect("admit baseline");
        let proposal = store
            .propose_agent_md_change(AgentMdChangeProposal {
                resource_id: "agent-profile".to_string(),
                path: agent_md.clone(),
                expected_current_content_sha256: Some(resource_content_sha256(&original)),
                target_version: None,
                proposed_content: b"# Stable profile\nreview this line\n".to_vec(),
                observed_at: 1_700_000_001,
            })
            .await
            .expect("proposal");

        let receipt = store
            .review_agent_md_change_proposal(AgentMdChangeProposalReview {
                resource_id: "agent-profile".to_string(),
                path: agent_md.clone(),
                proposal: proposal.clone(),
                reviewed_at: 1_700_000_002,
            })
            .await
            .expect("review proposal");

        assert_eq!(receipt.schema, RESOURCE_CHANGE_PROPOSAL_REVIEW_SCHEMA);
        assert_eq!(receipt.proposal, proposal);
        assert_eq!(receipt.reviewed_at, 1_700_000_002);
        assert_eq!(receipt.status, "current_unverified");
        assert!(receipt.violations.is_empty());
        assert!(receipt.receipt_invariants_verified);
        assert!(receipt.observed_state_current);
        assert!(!receipt.source_authenticity_verified);
        assert!(!receipt.candidate_content_available);
        assert!(!receipt.semantic_review_performed);
        assert!(!receipt.eligible_for_human_review);
        assert!(!receipt.automatic_apply_allowed);
        assert!(receipt.proposal_only);
        assert!(!receipt.resource_content_mutated);
        assert!(!receipt.lineage_mutated);
        assert_eq!(receipt.review_scope, RESOURCE_CHANGE_PROPOSAL_REVIEW_SCOPE);
        assert_eq!(
            std::fs::read(&agent_md).expect("read unchanged AGENT.md"),
            original
        );
        let report = store
            .resource_lineage_read("agent-profile", 32)
            .await
            .expect("read lineage");
        assert_eq!(report.records.len(), 1);
    }

    #[cfg(unix)]
    #[tokio::test]
    async fn review_marks_proposal_stale_after_lineage_advances() {
        let directory = tempfile::tempdir().expect("tempdir");
        let database = directory.path().join("state.db");
        let agent_md = directory.path().join("AGENT.md");
        let original = b"# Stable profile\n".to_vec();
        let current = b"# Current profile\n".to_vec();
        std::fs::write(&agent_md, &original).expect("write AGENT.md");
        let store = SqliteStore::open(&database).await.expect("open store");
        store
            .admit_agent_md_baseline(AgentMdBaselineAdmission {
                resource_id: "agent-profile".to_string(),
                path: agent_md.clone(),
                observed_at: 1_700_000_000,
            })
            .await
            .expect("admit baseline");
        let proposal = store
            .propose_agent_md_change(AgentMdChangeProposal {
                resource_id: "agent-profile".to_string(),
                path: agent_md.clone(),
                expected_current_content_sha256: Some(resource_content_sha256(&original)),
                target_version: None,
                proposed_content: b"# Candidate profile\n".to_vec(),
                observed_at: 1_700_000_001,
            })
            .await
            .expect("proposal");
        store
            .commit_agent_md_cas(AgentMdCasCommit {
                resource_id: "agent-profile".to_string(),
                path: agent_md.clone(),
                expected_content_sha256: resource_content_sha256(&original),
                proposed_content: current.clone(),
                observed_at: 1_700_000_002,
            })
            .await
            .expect("advance lineage");

        let receipt = store
            .review_agent_md_change_proposal(AgentMdChangeProposalReview {
                resource_id: "agent-profile".to_string(),
                path: agent_md.clone(),
                proposal,
                reviewed_at: 1_700_000_003,
            })
            .await
            .expect("review stale proposal");

        assert_eq!(receipt.status, "stale");
        assert!(receipt.receipt_invariants_verified);
        assert!(!receipt.observed_state_current);
        assert!(!receipt.source_authenticity_verified);
        assert!(!receipt.eligible_for_human_review);
        assert!(!receipt.automatic_apply_allowed);
        assert!(receipt
            .violations
            .contains(&"current_content_stale".to_string()));
        assert!(receipt
            .violations
            .contains(&"lineage_head_stale".to_string()));
        assert_eq!(
            std::fs::read(&agent_md).expect("read current AGENT.md"),
            current
        );
    }

    #[cfg(unix)]
    #[tokio::test]
    async fn review_rejects_forged_proposal_mutation_claims() {
        let directory = tempfile::tempdir().expect("tempdir");
        let database = directory.path().join("state.db");
        let agent_md = directory.path().join("AGENT.md");
        let original = b"# Stable profile\n".to_vec();
        std::fs::write(&agent_md, &original).expect("write AGENT.md");
        let store = SqliteStore::open(&database).await.expect("open store");
        store
            .admit_agent_md_baseline(AgentMdBaselineAdmission {
                resource_id: "agent-profile".to_string(),
                path: agent_md.clone(),
                observed_at: 1_700_000_000,
            })
            .await
            .expect("admit baseline");
        let mut proposal = store
            .propose_agent_md_change(AgentMdChangeProposal {
                resource_id: "agent-profile".to_string(),
                path: agent_md.clone(),
                expected_current_content_sha256: Some(resource_content_sha256(&original)),
                target_version: None,
                proposed_content: b"# Candidate profile\n".to_vec(),
                observed_at: 1_700_000_001,
            })
            .await
            .expect("proposal");
        proposal.resource_content_mutated = true;

        let receipt = store
            .review_agent_md_change_proposal(AgentMdChangeProposalReview {
                resource_id: "agent-profile".to_string(),
                path: agent_md.clone(),
                proposal,
                reviewed_at: 1_700_000_002,
            })
            .await
            .expect("review forged proposal");

        assert_eq!(receipt.status, "invalid");
        assert!(!receipt.receipt_invariants_verified);
        assert!(!receipt.observed_state_current);
        assert!(!receipt.source_authenticity_verified);
        assert!(!receipt.eligible_for_human_review);
        assert!(receipt
            .violations
            .contains(&"proposal_mutation_boundary_violated".to_string()));
        assert_eq!(
            std::fs::read(&agent_md).expect("read unchanged AGENT.md"),
            original
        );
    }

    #[cfg(unix)]
    #[tokio::test]
    async fn review_never_authenticates_self_consistent_candidate_metadata() {
        let directory = tempfile::tempdir().expect("tempdir");
        let database = directory.path().join("state.db");
        let agent_md = directory.path().join("AGENT.md");
        let original = b"# Stable profile\n".to_vec();
        std::fs::write(&agent_md, &original).expect("write AGENT.md");
        let store = SqliteStore::open(&database).await.expect("open store");
        store
            .admit_agent_md_baseline(AgentMdBaselineAdmission {
                resource_id: "agent-profile".to_string(),
                path: agent_md.clone(),
                observed_at: 1_700_000_000,
            })
            .await
            .expect("admit baseline");
        let mut proposal = store
            .propose_agent_md_change(AgentMdChangeProposal {
                resource_id: "agent-profile".to_string(),
                path: agent_md.clone(),
                expected_current_content_sha256: Some(resource_content_sha256(&original)),
                target_version: None,
                proposed_content: b"# Candidate profile\n".to_vec(),
                observed_at: 1_700_000_001,
            })
            .await
            .expect("proposal");
        let forged = b"# Forged but coherent\n";
        proposal.proposed_content_sha256 = resource_content_sha256(forged);
        proposal.proposed_bytes = forged.len() as u64;
        proposal.proposed_lines = 1;
        proposal.added_lines = 1;
        proposal.removed_lines = 1;
        proposal.changed_lines = 1;
        proposal.content_changed = true;

        let receipt = store
            .review_agent_md_change_proposal(AgentMdChangeProposalReview {
                resource_id: "agent-profile".to_string(),
                path: agent_md.clone(),
                proposal,
                reviewed_at: 1_700_000_002,
            })
            .await
            .expect("review self-consistent metadata");

        assert_eq!(receipt.status, "current_unverified");
        assert!(receipt.receipt_invariants_verified);
        assert!(receipt.observed_state_current);
        assert!(!receipt.source_authenticity_verified);
        assert!(!receipt.eligible_for_human_review);
        assert!(!receipt.automatic_apply_allowed);
        assert_eq!(
            std::fs::read(&agent_md).expect("read unchanged AGENT.md"),
            original
        );
    }

    #[cfg(unix)]
    #[tokio::test]
    async fn persisted_proposal_retains_candidate_without_claiming_source_authenticity() {
        let directory = tempfile::tempdir().expect("tempdir");
        let database = directory.path().join("state.db");
        let agent_md = directory.path().join("AGENT.md");
        let original = b"# Stable profile\n".to_vec();
        let candidate = b"# Candidate profile\nreview me\n".to_vec();
        std::fs::write(&agent_md, &original).expect("write AGENT.md");
        let store = SqliteStore::open(&database).await.expect("open store");
        store
            .admit_agent_md_baseline(AgentMdBaselineAdmission {
                resource_id: "agent-profile".to_string(),
                path: agent_md.clone(),
                observed_at: 1_700_000_000,
            })
            .await
            .expect("admit baseline");

        let artifact = store
            .create_persisted_agent_md_proposal(AgentMdPersistedProposalCreate {
                proposal: AgentMdChangeProposal {
                    resource_id: "agent-profile".to_string(),
                    path: agent_md.clone(),
                    expected_current_content_sha256: Some(resource_content_sha256(&original)),
                    target_version: None,
                    proposed_content: candidate.clone(),
                    observed_at: 1_700_000_001,
                },
                producer_id: "codex:test".to_string(),
            })
            .await
            .expect("create persisted proposal");

        assert_eq!(artifact.schema, RESOURCE_PERSISTED_PROPOSAL_SCHEMA);
        assert_eq!(artifact.proposal_id, artifact.record_sha256);
        assert_eq!(artifact.candidate_content, candidate);
        assert!(artifact.persistence_integrity_verified);
        assert!(!artifact.source_authenticity_verified);
        assert!(artifact.candidate_content_available);
        assert!(!artifact.eligible_for_human_review);
        assert!(!artifact.semantic_review_performed);
        assert!(!artifact.automatic_apply_allowed);
        assert!(!artifact.resource_content_mutated);
        assert!(!artifact.lineage_mutated);
        assert_eq!(
            std::fs::read(&agent_md).expect("read unchanged AGENT.md"),
            original
        );
        let reopened = SqliteStore::open(&database).await.expect("reopen store");
        let readback = reopened
            .read_persisted_agent_md_proposal(&artifact.proposal_id)
            .await
            .expect("read integrity-checked proposal");
        assert_eq!(readback, artifact);
    }

    #[cfg(unix)]
    #[tokio::test]
    async fn persisted_proposal_is_content_addressed_and_idempotent() {
        let directory = tempfile::tempdir().expect("tempdir");
        let database = directory.path().join("state.db");
        let agent_md = directory.path().join("AGENT.md");
        let original = b"# Stable profile\n".to_vec();
        std::fs::write(&agent_md, &original).expect("write AGENT.md");
        let store = SqliteStore::open(&database).await.expect("open store");
        store
            .admit_agent_md_baseline(AgentMdBaselineAdmission {
                resource_id: "agent-profile".to_string(),
                path: agent_md.clone(),
                observed_at: 1_700_000_000,
            })
            .await
            .expect("admit baseline");
        let make_request = || AgentMdPersistedProposalCreate {
            proposal: AgentMdChangeProposal {
                resource_id: "agent-profile".to_string(),
                path: agent_md.clone(),
                expected_current_content_sha256: Some(resource_content_sha256(&original)),
                target_version: None,
                proposed_content: b"# Candidate\n".to_vec(),
                observed_at: 1_700_000_001,
            },
            producer_id: "codex:test".to_string(),
        };
        let first = store
            .create_persisted_agent_md_proposal(make_request())
            .await
            .expect("first proposal");
        let second = store
            .create_persisted_agent_md_proposal(make_request())
            .await
            .expect("idempotent proposal");
        assert_eq!(first, second);
    }

    #[cfg(unix)]
    #[tokio::test]
    async fn persisted_proposal_read_rejects_persisted_candidate_tampering() {
        let directory = tempfile::tempdir().expect("tempdir");
        let database = directory.path().join("state.db");
        let agent_md = directory.path().join("AGENT.md");
        let original = b"# Stable profile\n".to_vec();
        std::fs::write(&agent_md, &original).expect("write AGENT.md");
        let store = SqliteStore::open(&database).await.expect("open store");
        store
            .admit_agent_md_baseline(AgentMdBaselineAdmission {
                resource_id: "agent-profile".to_string(),
                path: agent_md.clone(),
                observed_at: 1_700_000_000,
            })
            .await
            .expect("admit baseline");
        let artifact = store
            .create_persisted_agent_md_proposal(AgentMdPersistedProposalCreate {
                proposal: AgentMdChangeProposal {
                    resource_id: "agent-profile".to_string(),
                    path: agent_md,
                    expected_current_content_sha256: Some(resource_content_sha256(&original)),
                    target_version: None,
                    proposed_content: b"# Candidate\n".to_vec(),
                    observed_at: 1_700_000_001,
                },
                producer_id: "codex:test".to_string(),
            })
            .await
            .expect("create proposal");
        drop(store);
        let connection = rusqlite::Connection::open(&database).expect("open raw fixture db");
        connection
            .execute(
                "UPDATE resource_change_proposals SET candidate_content=?1",
                [b"# Tampered\n".as_slice()],
            )
            .expect("tamper fixture");
        drop(connection);
        let reopened = SqliteStore::open(&database).await.expect("reopen store");
        let error = reopened
            .read_persisted_agent_md_proposal(&artifact.proposal_id)
            .await
            .expect_err("tampering must fail closed");
        assert!(error.to_string().contains("record hash mismatch"));
    }

    #[cfg(unix)]
    #[tokio::test]
    async fn review_observation_is_content_addressed_untrusted_and_non_mutating() {
        let directory = tempfile::tempdir().expect("tempdir");
        let database = directory.path().join("state.db");
        let agent_md = directory.path().join("AGENT.md");
        let original = b"# Stable profile\n".to_vec();
        std::fs::write(&agent_md, &original).expect("write AGENT.md");
        let store = SqliteStore::open(&database).await.expect("open store");
        store
            .admit_agent_md_baseline(AgentMdBaselineAdmission {
                resource_id: "agent-profile".to_string(),
                path: agent_md.clone(),
                observed_at: 1_700_000_000,
            })
            .await
            .expect("admit baseline");
        let proposal = store
            .create_persisted_agent_md_proposal(AgentMdPersistedProposalCreate {
                proposal: AgentMdChangeProposal {
                    resource_id: "agent-profile".to_string(),
                    path: agent_md.clone(),
                    expected_current_content_sha256: Some(resource_content_sha256(&original)),
                    target_version: None,
                    proposed_content: b"# Candidate\n".to_vec(),
                    observed_at: 1_700_000_001,
                },
                producer_id: "codex:test".to_string(),
            })
            .await
            .expect("create proposal");
        let make_request = || AgentMdProposalReviewObservationCreate {
            proposal_id: proposal.proposal_id.clone(),
            reviewer_id: "owner-label:test".to_string(),
            reviewed_at: 1_700_000_002,
            disposition: "accept_candidate".to_string(),
            reason: "Candidate is coherent enough for later authenticated review.".to_string(),
        };

        let first = store
            .create_agent_md_proposal_review_observation(make_request())
            .await
            .expect("create review observation");
        let second = store
            .create_agent_md_proposal_review_observation(make_request())
            .await
            .expect("idempotent review observation");
        assert_eq!(first, second);
        assert_eq!(first.schema, RESOURCE_PROPOSAL_REVIEW_OBSERVATION_SCHEMA);
        assert_eq!(first.review_id, first.record_sha256);
        assert_eq!(first.proposal_record_sha256, proposal.record_sha256);
        assert!(first.persistence_integrity_verified);
        assert!(first.proposal_integrity_verified);
        assert!(first.human_review_claimed);
        assert!(!first.reviewer_identity_authenticated);
        assert!(!first.human_review_authenticated);
        assert!(!first.source_authenticity_verified);
        assert!(!first.semantic_review_authority_granted);
        assert!(!first.automatic_apply_allowed);
        assert!(!first.resource_content_mutated);
        assert!(!first.lineage_mutated);
        assert_eq!(
            std::fs::read(&agent_md).expect("read unchanged AGENT.md"),
            original
        );
        let lineage = store
            .resource_lineage_read("agent-profile", 32)
            .await
            .expect("read unchanged lineage");
        assert_eq!(lineage.records.len(), 1);
    }

    #[cfg(unix)]
    #[tokio::test]
    async fn review_observation_read_rejects_row_and_proposal_tampering() {
        let directory = tempfile::tempdir().expect("tempdir");
        let database = directory.path().join("state.db");
        let agent_md = directory.path().join("AGENT.md");
        let original = b"# Stable profile\n".to_vec();
        std::fs::write(&agent_md, &original).expect("write AGENT.md");
        let store = SqliteStore::open(&database).await.expect("open store");
        store
            .admit_agent_md_baseline(AgentMdBaselineAdmission {
                resource_id: "agent-profile".to_string(),
                path: agent_md.clone(),
                observed_at: 1_700_000_000,
            })
            .await
            .expect("admit baseline");
        let proposal = store
            .create_persisted_agent_md_proposal(AgentMdPersistedProposalCreate {
                proposal: AgentMdChangeProposal {
                    resource_id: "agent-profile".to_string(),
                    path: agent_md,
                    expected_current_content_sha256: Some(resource_content_sha256(&original)),
                    target_version: None,
                    proposed_content: b"# Candidate\n".to_vec(),
                    observed_at: 1_700_000_001,
                },
                producer_id: "codex:test".to_string(),
            })
            .await
            .expect("create proposal");
        let review = store
            .create_agent_md_proposal_review_observation(AgentMdProposalReviewObservationCreate {
                proposal_id: proposal.proposal_id.clone(),
                reviewer_id: "owner-label:test".to_string(),
                reviewed_at: 1_700_000_002,
                disposition: "defer".to_string(),
                reason: "Need another pass.".to_string(),
            })
            .await
            .expect("create review observation");
        drop(store);
        let connection = rusqlite::Connection::open(&database).expect("open raw fixture db");
        connection
            .execute(
                "UPDATE resource_proposal_review_observations SET reason='tampered' WHERE review_id=?1",
                [&review.review_id],
            )
            .expect("tamper review fixture");
        drop(connection);
        let reopened = SqliteStore::open(&database).await.expect("reopen store");
        let error = reopened
            .read_agent_md_proposal_review_observation(&review.review_id)
            .await
            .expect_err("review tampering must fail closed");
        assert!(error.to_string().contains("record hash mismatch"));

        drop(reopened);
        let connection = rusqlite::Connection::open(&database).expect("reopen raw fixture db");
        connection
            .execute(
                "UPDATE resource_proposal_review_observations SET reason=?1 WHERE review_id=?2",
                rusqlite::params![review.reason, review.review_id],
            )
            .expect("restore review fixture");
        connection
            .execute(
                "UPDATE resource_change_proposals SET candidate_content=?1 WHERE proposal_id=?2",
                rusqlite::params![b"# Tampered\n".as_slice(), proposal.proposal_id],
            )
            .expect("tamper proposal fixture");
        drop(connection);
        let reopened = SqliteStore::open(&database)
            .await
            .expect("reopen store again");
        let error = reopened
            .read_agent_md_proposal_review_observation(&review.review_id)
            .await
            .expect_err("referenced proposal tampering must fail closed");
        assert!(error.to_string().contains("record hash mismatch"));
    }

    #[cfg(unix)]
    #[tokio::test]
    async fn review_snapshot_is_bounded_deterministic_conflict_preserving_and_non_authoritative() {
        let directory = tempfile::tempdir().expect("tempdir");
        let database = directory.path().join("state.db");
        let agent_md = directory.path().join("AGENT.md");
        let original = b"# Stable profile\n".to_vec();
        std::fs::write(&agent_md, &original).expect("write AGENT.md");
        let store = SqliteStore::open(&database).await.expect("open store");
        store
            .admit_agent_md_baseline(AgentMdBaselineAdmission {
                resource_id: "agent-profile".to_string(),
                path: agent_md.clone(),
                observed_at: 1_700_000_000,
            })
            .await
            .expect("admit baseline");
        let proposal = store
            .create_persisted_agent_md_proposal(AgentMdPersistedProposalCreate {
                proposal: AgentMdChangeProposal {
                    resource_id: "agent-profile".to_string(),
                    path: agent_md.clone(),
                    expected_current_content_sha256: Some(resource_content_sha256(&original)),
                    target_version: None,
                    proposed_content: b"# Candidate\n".to_vec(),
                    observed_at: 1_700_000_001,
                },
                producer_id: "codex:test".to_string(),
            })
            .await
            .expect("create proposal");

        let empty = store
            .read_agent_md_proposal_review_snapshot(&proposal.proposal_id)
            .await
            .expect("read empty snapshot");
        assert!(empty.no_observations);
        assert_eq!(empty.observation_count, 0);
        assert_eq!(empty.distinct_disposition_count, 0);
        assert!(!empty.conflicting_dispositions_observed);
        assert_eq!(
            empty.snapshot_sha256,
            proposal_review_snapshot_sha256(&proposal.proposal_id, &proposal.record_sha256, &[])
        );

        for (reviewer_id, reviewed_at, disposition, reason) in [
            (
                "reviewer:later",
                1_700_000_003,
                "defer",
                "Need another bounded pass.",
            ),
            (
                "reviewer:accept",
                1_700_000_002,
                "accept_candidate",
                "Candidate can remain under observation.",
            ),
            (
                "reviewer:reject",
                1_700_000_002,
                "reject_candidate",
                "Candidate conflicts with one local constraint.",
            ),
        ] {
            store
                .create_agent_md_proposal_review_observation(
                    AgentMdProposalReviewObservationCreate {
                        proposal_id: proposal.proposal_id.clone(),
                        reviewer_id: reviewer_id.to_string(),
                        reviewed_at,
                        disposition: disposition.to_string(),
                        reason: reason.to_string(),
                    },
                )
                .await
                .expect("create review observation");
        }

        let first = store
            .read_agent_md_proposal_review_snapshot(&proposal.proposal_id)
            .await
            .expect("read review snapshot");
        let second = store
            .read_agent_md_proposal_review_snapshot(&proposal.proposal_id)
            .await
            .expect("read deterministic review snapshot");
        assert_eq!(first, second);
        assert_eq!(first.schema, RESOURCE_PROPOSAL_REVIEW_SNAPSHOT_SCHEMA);
        assert_eq!(first.observation_count, 3);
        assert_eq!(first.accept_candidate_count, 1);
        assert_eq!(first.reject_candidate_count, 1);
        assert_eq!(first.defer_count, 1);
        assert_eq!(first.distinct_disposition_count, 3);
        assert!(!first.no_observations);
        assert!(first.conflicting_dispositions_observed);
        assert!(first.bounded_snapshot_complete);
        assert!(first.snapshot_integrity_verified);
        assert!(first.proposal_integrity_verified);
        assert!(first.all_observations_integrity_verified);
        assert!(!first.external_writer_exclusion_verified);
        assert!(!first.reviewer_identities_authenticated);
        assert!(!first.human_reviews_authenticated);
        assert!(!first.semantic_review_authority_granted);
        assert!(!first.quorum_established);
        assert!(!first.winner_selected);
        assert!(!first.eligible_for_apply);
        assert!(!first.automatic_apply_allowed);
        assert!(!first.resource_content_mutated);
        assert!(!first.lineage_mutated);
        assert!(first.observations.windows(2).all(|pair| (
            pair[0].reviewed_at,
            &pair[0].review_id
        ) < (
            pair[1].reviewed_at,
            &pair[1].review_id
        )));
        let ordered_hashes = first
            .observations
            .iter()
            .map(|observation| observation.record_sha256.clone())
            .collect::<Vec<_>>();
        assert_eq!(
            first.snapshot_sha256,
            proposal_review_snapshot_sha256(
                &proposal.proposal_id,
                &proposal.record_sha256,
                &ordered_hashes
            )
        );
        let mut reordered_hashes = ordered_hashes.clone();
        reordered_hashes.swap(0, 1);
        assert_ne!(
            first.snapshot_sha256,
            proposal_review_snapshot_sha256(
                &proposal.proposal_id,
                &proposal.record_sha256,
                &reordered_hashes
            )
        );
        assert_eq!(
            std::fs::read(&agent_md).expect("read unchanged AGENT.md"),
            original
        );
        let lineage = store
            .resource_lineage_read("agent-profile", 32)
            .await
            .expect("read unchanged lineage");
        assert_eq!(lineage.records.len(), 1);
    }

    #[cfg(unix)]
    #[tokio::test]
    async fn review_snapshot_rejects_observation_and_proposal_tampering() {
        let directory = tempfile::tempdir().expect("tempdir");
        let database = directory.path().join("state.db");
        let agent_md = directory.path().join("AGENT.md");
        let original = b"# Stable profile\n".to_vec();
        std::fs::write(&agent_md, &original).expect("write AGENT.md");
        let store = SqliteStore::open(&database).await.expect("open store");
        store
            .admit_agent_md_baseline(AgentMdBaselineAdmission {
                resource_id: "agent-profile".to_string(),
                path: agent_md.clone(),
                observed_at: 1_700_000_000,
            })
            .await
            .expect("admit baseline");
        let proposal = store
            .create_persisted_agent_md_proposal(AgentMdPersistedProposalCreate {
                proposal: AgentMdChangeProposal {
                    resource_id: "agent-profile".to_string(),
                    path: agent_md,
                    expected_current_content_sha256: Some(resource_content_sha256(&original)),
                    target_version: None,
                    proposed_content: b"# Candidate\n".to_vec(),
                    observed_at: 1_700_000_001,
                },
                producer_id: "codex:test".to_string(),
            })
            .await
            .expect("create proposal");
        let review = store
            .create_agent_md_proposal_review_observation(AgentMdProposalReviewObservationCreate {
                proposal_id: proposal.proposal_id.clone(),
                reviewer_id: "reviewer:test".to_string(),
                reviewed_at: 1_700_000_002,
                disposition: "defer".to_string(),
                reason: "Need another pass.".to_string(),
            })
            .await
            .expect("create review observation");
        drop(store);

        let connection = rusqlite::Connection::open(&database).expect("open raw fixture db");
        connection
            .execute(
                "UPDATE resource_proposal_review_observations SET reason='tampered' WHERE review_id=?1",
                [&review.review_id],
            )
            .expect("tamper review fixture");
        drop(connection);
        let reopened = SqliteStore::open(&database).await.expect("reopen store");
        let error = reopened
            .read_agent_md_proposal_review_snapshot(&proposal.proposal_id)
            .await
            .expect_err("review tampering must fail closed");
        assert!(error
            .to_string()
            .contains("review observation integrity mismatch"));
        drop(reopened);

        let connection = rusqlite::Connection::open(&database).expect("reopen raw fixture db");
        connection
            .execute(
                "UPDATE resource_proposal_review_observations SET reason=?1 WHERE review_id=?2",
                rusqlite::params![review.reason, review.review_id],
            )
            .expect("restore review fixture");
        connection
            .execute(
                "UPDATE resource_change_proposals SET candidate_content=?1 WHERE proposal_id=?2",
                rusqlite::params![b"# Tampered\n".as_slice(), proposal.proposal_id],
            )
            .expect("tamper proposal fixture");
        drop(connection);
        let reopened = SqliteStore::open(&database)
            .await
            .expect("reopen store again");
        let error = reopened
            .read_agent_md_proposal_review_snapshot(&proposal.proposal_id)
            .await
            .expect_err("proposal tampering must fail closed");
        assert!(error.to_string().contains("record hash mismatch"));
    }

    #[cfg(unix)]
    #[tokio::test]
    async fn review_snapshot_fails_closed_above_the_observation_bound() {
        let directory = tempfile::tempdir().expect("tempdir");
        let database = directory.path().join("state.db");
        let agent_md = directory.path().join("AGENT.md");
        let original = b"# Stable profile\n".to_vec();
        std::fs::write(&agent_md, &original).expect("write AGENT.md");
        let store = SqliteStore::open(&database).await.expect("open store");
        store
            .admit_agent_md_baseline(AgentMdBaselineAdmission {
                resource_id: "agent-profile".to_string(),
                path: agent_md.clone(),
                observed_at: 1_700_000_000,
            })
            .await
            .expect("admit baseline");
        let proposal = store
            .create_persisted_agent_md_proposal(AgentMdPersistedProposalCreate {
                proposal: AgentMdChangeProposal {
                    resource_id: "agent-profile".to_string(),
                    path: agent_md,
                    expected_current_content_sha256: Some(resource_content_sha256(&original)),
                    target_version: None,
                    proposed_content: b"# Candidate\n".to_vec(),
                    observed_at: 1_700_000_001,
                },
                producer_id: "codex:test".to_string(),
            })
            .await
            .expect("create proposal");
        drop(store);

        let mut connection = rusqlite::Connection::open(&database).expect("open raw fixture db");
        let transaction = connection.transaction().expect("start fixture transaction");
        for index in 0..RESOURCE_PROPOSAL_REVIEW_SNAPSHOT_MAX_OBSERVATIONS {
            let reviewer_id = format!("reviewer:{index}");
            let reviewed_at = 1_700_000_002 + index as i64;
            let disposition = "defer";
            let reason = format!("bounded fixture {index}");
            let review_id = proposal_review_observation_record_sha256(
                &proposal.proposal_id,
                &reviewer_id,
                reviewed_at,
                disposition,
                &reason,
                &proposal.record_sha256,
            );
            transaction
                .execute(
                    "INSERT INTO resource_proposal_review_observations (
                        review_id, proposal_id, reviewer_id, reviewed_at, disposition,
                        reason, proposal_record_sha256, record_sha256
                     ) VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7, ?8)",
                    rusqlite::params![
                        review_id,
                        proposal.proposal_id,
                        reviewer_id,
                        reviewed_at,
                        disposition,
                        reason,
                        proposal.record_sha256,
                        review_id,
                    ],
                )
                .expect("insert bounded fixture");
        }
        transaction.commit().expect("commit fixtures");
        drop(connection);

        let reopened = SqliteStore::open(&database).await.expect("reopen store");
        let full = reopened
            .read_agent_md_proposal_review_snapshot(&proposal.proposal_id)
            .await
            .expect("exactly bounded observation set must succeed");
        assert_eq!(full.observation_count, 256);
        assert!(full.bounded_snapshot_complete);
        assert_eq!(full.defer_count, 256);
        assert!(full.snapshot_integrity_verified);
        drop(reopened);

        let connection = rusqlite::Connection::open(&database).expect("reopen raw fixture db");
        let index = RESOURCE_PROPOSAL_REVIEW_SNAPSHOT_MAX_OBSERVATIONS;
        let reviewer_id = format!("reviewer:{index}");
        let reviewed_at = 1_700_000_002 + index as i64;
        let disposition = "defer";
        let reason = format!("bounded fixture {index}");
        let review_id = proposal_review_observation_record_sha256(
            &proposal.proposal_id,
            &reviewer_id,
            reviewed_at,
            disposition,
            &reason,
            &proposal.record_sha256,
        );
        connection
            .execute(
                "INSERT INTO resource_proposal_review_observations (
                    review_id, proposal_id, reviewer_id, reviewed_at, disposition,
                    reason, proposal_record_sha256, record_sha256
                 ) VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7, ?8)",
                rusqlite::params![
                    review_id,
                    proposal.proposal_id,
                    reviewer_id,
                    reviewed_at,
                    disposition,
                    reason,
                    proposal.record_sha256,
                    review_id,
                ],
            )
            .expect("insert overflow fixture");
        drop(connection);

        let reopened = SqliteStore::open(&database).await.expect("reopen store again");
        let error = reopened
            .read_agent_md_proposal_review_snapshot(&proposal.proposal_id)
            .await
            .expect_err("oversized observation set must fail closed");
        assert!(error.to_string().contains("bounded maximum of 256"));
        assert_eq!(
            std::fs::read(directory.path().join("AGENT.md")).expect("read unchanged AGENT.md"),
            original
        );
    }

    #[tokio::test]
    async fn review_observation_rejects_invalid_caller_metadata() {
        let directory = tempfile::tempdir().expect("tempdir");
        let store = SqliteStore::open(&directory.path().join("state.db"))
            .await
            .expect("open store");
        for request in [
            AgentMdProposalReviewObservationCreate {
                proposal_id: "a".repeat(64),
                reviewer_id: " reviewer".to_string(),
                reviewed_at: 1,
                disposition: "defer".to_string(),
                reason: "reason".to_string(),
            },
            AgentMdProposalReviewObservationCreate {
                proposal_id: "a".repeat(64),
                reviewer_id: "reviewer".to_string(),
                reviewed_at: -1,
                disposition: "defer".to_string(),
                reason: "reason".to_string(),
            },
            AgentMdProposalReviewObservationCreate {
                proposal_id: "a".repeat(64),
                reviewer_id: "reviewer".to_string(),
                reviewed_at: 1,
                disposition: "approve_and_apply".to_string(),
                reason: "reason".to_string(),
            },
            AgentMdProposalReviewObservationCreate {
                proposal_id: "a".repeat(64),
                reviewer_id: "reviewer".to_string(),
                reviewed_at: 1,
                disposition: "defer".to_string(),
                reason: "".to_string(),
            },
        ] {
            store
                .create_agent_md_proposal_review_observation(request)
                .await
                .expect_err("invalid caller metadata must fail before proposal lookup");
        }
    }

    #[cfg(unix)]
    #[tokio::test]
    async fn proposal_rejects_stale_expected_current_hash() {
        let directory = tempfile::tempdir().expect("tempdir");
        let database = directory.path().join("state.db");
        let agent_md = directory.path().join("AGENT.md");
        let original = b"# Stable profile\n".to_vec();
        std::fs::write(&agent_md, &original).expect("write AGENT.md");
        let store = SqliteStore::open(&database).await.expect("open store");
        store
            .admit_agent_md_baseline(AgentMdBaselineAdmission {
                resource_id: "agent-profile".to_string(),
                path: agent_md.clone(),
                observed_at: 1_700_000_000,
            })
            .await
            .expect("admit baseline");

        let error = store
            .propose_agent_md_change(AgentMdChangeProposal {
                resource_id: "agent-profile".to_string(),
                path: agent_md.clone(),
                expected_current_content_sha256: Some(resource_content_sha256(b"# stale\n")),
                target_version: None,
                proposed_content: b"# candidate\n".to_vec(),
                observed_at: 1_700_000_001,
            })
            .await
            .expect_err("stale expected hash must fail");
        assert!(error.to_string().contains("does not match expected hash"));
        assert_eq!(
            std::fs::read(&agent_md).expect("read unchanged AGENT.md"),
            original
        );
    }

    #[cfg(unix)]
    #[tokio::test]
    async fn stale_cas_expected_hash_leaves_file_and_lineage_unchanged() {
        let directory = tempfile::tempdir().expect("tempdir");
        let database = directory.path().join("state.db");
        let agent_md = directory.path().join("AGENT.md");
        let original = b"# Stable profile\n".to_vec();
        let proposed = b"# Updated profile\n".to_vec();
        std::fs::write(&agent_md, &original).expect("write AGENT.md");
        let store = SqliteStore::open(&database).await.expect("open store");
        let baseline = store
            .admit_agent_md_baseline(AgentMdBaselineAdmission {
                resource_id: "agent-profile".to_string(),
                path: agent_md.clone(),
                observed_at: 1_700_000_000,
            })
            .await
            .expect("admit baseline");

        let error = store
            .commit_agent_md_cas(AgentMdCasCommit {
                resource_id: "agent-profile".to_string(),
                path: agent_md.clone(),
                expected_content_sha256: resource_content_sha256(b"# Wrong hash\n"),
                proposed_content: proposed,
                observed_at: 1_700_000_001,
            })
            .await
            .expect_err("stale expected hash must fail");
        assert!(error.to_string().contains("expected content hash"));
        assert_eq!(std::fs::read(&agent_md).expect("read AGENT.md"), original);
        let report = store
            .resource_lineage_read("agent-profile", 32)
            .await
            .expect("read lineage");
        assert_eq!(report.records, vec![baseline.version]);
    }

    #[cfg(unix)]
    #[tokio::test]
    async fn corrupted_prior_lineage_blocks_cas_extension() {
        let directory = tempfile::tempdir().expect("tempdir");
        let database = directory.path().join("state.db");
        let agent_md = directory.path().join("AGENT.md");
        let original = b"# Stable profile\n".to_vec();
        let second = b"# Updated profile\n".to_vec();
        let third = b"# Third profile\n".to_vec();
        std::fs::write(&agent_md, &original).expect("write AGENT.md");
        let store = SqliteStore::open(&database).await.expect("open store");
        store
            .admit_agent_md_baseline(AgentMdBaselineAdmission {
                resource_id: "agent-profile".to_string(),
                path: agent_md.clone(),
                observed_at: 1_700_000_000,
            })
            .await
            .expect("admit baseline");
        store
            .commit_agent_md_cas(AgentMdCasCommit {
                resource_id: "agent-profile".to_string(),
                path: agent_md.clone(),
                expected_content_sha256: resource_content_sha256(&original),
                proposed_content: second.clone(),
                observed_at: 1_700_000_001,
            })
            .await
            .expect("commit second version");

        let connection = rusqlite::Connection::open(&database).expect("open raw database");
        connection
            .execute(
                "UPDATE resource_versions SET record_sha256=?1 \
                 WHERE resource_id='agent-profile' AND version=1",
                ["0".repeat(64)],
            )
            .expect("corrupt prior record");
        drop(connection);

        let error = store
            .commit_agent_md_cas(AgentMdCasCommit {
                resource_id: "agent-profile".to_string(),
                path: agent_md.clone(),
                expected_content_sha256: resource_content_sha256(&second),
                proposed_content: third,
                observed_at: 1_700_000_002,
            })
            .await
            .expect_err("corrupted prior lineage must block extension");
        assert!(error
            .to_string()
            .contains("resource lineage is not verified"));
        assert_eq!(std::fs::read(&agent_md).expect("read AGENT.md"), second);
    }

    #[cfg(unix)]
    #[tokio::test]
    async fn post_replace_failure_restores_exact_file_and_rolls_back_lineage() {
        let directory = tempfile::tempdir().expect("tempdir");
        let database = directory.path().join("state.db");
        let agent_md = directory.path().join("AGENT.md");
        let original = b"# Stable profile\n".to_vec();
        let proposed = b"# Updated profile\n".to_vec();
        std::fs::write(&agent_md, &original).expect("write AGENT.md");
        let store = SqliteStore::open(&database).await.expect("open store");
        let baseline = store
            .admit_agent_md_baseline(AgentMdBaselineAdmission {
                resource_id: "agent-profile".to_string(),
                path: agent_md.clone(),
                observed_at: 1_700_000_000,
            })
            .await
            .expect("admit baseline");

        let error = store
            .commit_agent_md_cas_with_post_replace_failure(AgentMdCasCommit {
                resource_id: "agent-profile".to_string(),
                path: agent_md.clone(),
                expected_content_sha256: resource_content_sha256(&original),
                proposed_content: proposed,
                observed_at: 1_700_000_001,
            })
            .await
            .expect_err("injected post-replace failure must fail");
        assert!(error.to_string().contains("injected post-replace failure"));
        assert_eq!(
            std::fs::read(&agent_md).expect("read restored AGENT.md"),
            original
        );
        let report = store
            .resource_lineage_read("agent-profile", 32)
            .await
            .expect("read lineage");
        assert_eq!(report.records, vec![baseline.version]);
    }

    #[cfg(unix)]
    #[tokio::test]
    async fn concurrent_cas_commits_allow_one_and_reject_stale_peer() {
        let directory = tempfile::tempdir().expect("tempdir");
        let database = directory.path().join("state.db");
        let agent_md = directory.path().join("AGENT.md");
        let original = b"# Stable profile\n".to_vec();
        let proposed = b"# Updated profile\n".to_vec();
        std::fs::write(&agent_md, &original).expect("write AGENT.md");
        let left_store = SqliteStore::open(&database).await.expect("open left store");
        let right_store = SqliteStore::open(&database)
            .await
            .expect("open right store");
        left_store
            .admit_agent_md_baseline(AgentMdBaselineAdmission {
                resource_id: "agent-profile".to_string(),
                path: agent_md.clone(),
                observed_at: 1_700_000_000,
            })
            .await
            .expect("admit baseline");
        let request = || AgentMdCasCommit {
            resource_id: "agent-profile".to_string(),
            path: agent_md.clone(),
            expected_content_sha256: resource_content_sha256(&original),
            proposed_content: proposed.clone(),
            observed_at: 1_700_000_001,
        };

        let (left, right) = tokio::join!(
            left_store.commit_agent_md_cas(request()),
            right_store.commit_agent_md_cas(request())
        );
        assert!(left.is_ok() ^ right.is_ok());
        assert!(left.is_err() || right.is_err());
        assert_eq!(
            std::fs::read(&agent_md).expect("read committed AGENT.md"),
            proposed
        );
        let report = left_store
            .resource_lineage_read("agent-profile", 32)
            .await
            .expect("read lineage");
        assert_eq!(report.status, "verified");
        assert_eq!(report.records.len(), 2);
    }

    #[tokio::test]
    async fn baseline_admission_refuses_to_masquerade_as_post_commit_verification() {
        let directory = tempfile::tempdir().expect("tempdir");
        let database = directory.path().join("state.db");
        let agent_md = directory.path().join("AGENT.md");
        std::fs::write(&agent_md, "# Stable profile\n").expect("write AGENT.md");
        let store = SqliteStore::open(&database).await.expect("open store");
        let first = store
            .admit_agent_md_baseline(AgentMdBaselineAdmission {
                resource_id: "agent-profile".to_string(),
                path: agent_md.clone(),
                observed_at: 1_700_000_000,
            })
            .await
            .expect("baseline admission");

        let mut second = record(2, Some(&first.version));
        second.content_sha256 = first.version.content_sha256.clone();
        second.record_sha256 = resource_version_record_sha256(&second);
        let connection = rusqlite::Connection::open(&database).expect("open raw database");
        connection
            .execute(
                "INSERT INTO resource_versions(
                     resource_id, resource_kind, version, content_sha256,
                     predecessor_version, predecessor_record_sha256, observed_at, record_sha256
                 ) VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7, ?8)",
                rusqlite::params![
                    second.resource_id,
                    second.resource_kind,
                    second.version as i64,
                    second.content_sha256,
                    second.predecessor_version.map(|value| value as i64),
                    second.predecessor_record_sha256,
                    second.observed_at,
                    second.record_sha256,
                ],
            )
            .expect("insert simulated later version");
        drop(connection);

        let error = store
            .admit_agent_md_baseline(AgentMdBaselineAdmission {
                resource_id: "agent-profile".to_string(),
                path: agent_md,
                observed_at: 1_800_000_000,
            })
            .await
            .expect_err("baseline API must reject a post-genesis lineage");
        assert!(error
            .to_string()
            .contains("existing lineage head does not match"));
    }

    #[tokio::test]
    async fn readback_mismatch_rolls_back_binding_and_genesis() {
        let directory = tempfile::tempdir().expect("tempdir");
        let database = directory.path().join("state.db");
        let agent_md = directory.path().join("AGENT.md");
        std::fs::write(&agent_md, "# Stable profile\n").expect("write AGENT.md");
        let store = SqliteStore::open(&database).await.expect("open store");

        let error = store
            .admit_agent_md_baseline_with_readback_override(
                AgentMdBaselineAdmission {
                    resource_id: "agent-profile".to_string(),
                    path: agent_md,
                    observed_at: 1_700_000_000,
                },
                b"# Changed concurrently\n".to_vec(),
            )
            .await
            .expect_err("mismatched readback must fail");
        assert!(error
            .to_string()
            .contains("resource changed during baseline admission readback"));

        let connection = rusqlite::Connection::open(&database).expect("open raw database");
        let binding_count: i64 = connection
            .query_row("SELECT COUNT(*) FROM resource_bindings", [], |row| {
                row.get(0)
            })
            .expect("count bindings");
        let version_count: i64 = connection
            .query_row("SELECT COUNT(*) FROM resource_versions", [], |row| {
                row.get(0)
            })
            .expect("count versions");
        assert_eq!(binding_count, 0);
        assert_eq!(version_count, 0);
    }

    #[tokio::test]
    async fn rejects_rebinding_resource_id_to_another_agent_md() {
        let directory = tempfile::tempdir().expect("tempdir");
        let database = directory.path().join("state.db");
        let first_directory = directory.path().join("first");
        let second_directory = directory.path().join("second");
        std::fs::create_dir_all(&first_directory).expect("first dir");
        std::fs::create_dir_all(&second_directory).expect("second dir");
        let first = first_directory.join("AGENT.md");
        let second = second_directory.join("AGENT.md");
        std::fs::write(&first, "# First\n").expect("first AGENT.md");
        std::fs::write(&second, "# Second\n").expect("second AGENT.md");
        let store = SqliteStore::open(&database).await.expect("open store");
        store
            .admit_agent_md_baseline(AgentMdBaselineAdmission {
                resource_id: "agent-profile".to_string(),
                path: first,
                observed_at: 1_700_000_000,
            })
            .await
            .expect("first admission");

        let error = store
            .admit_agent_md_baseline(AgentMdBaselineAdmission {
                resource_id: "agent-profile".to_string(),
                path: second,
                observed_at: 1_800_000_000,
            })
            .await
            .expect_err("rebind must fail");
        assert!(error
            .to_string()
            .contains("existing resource binding does not match"));
    }

    #[cfg(unix)]
    #[tokio::test]
    async fn rejects_symlink_agent_md_target() {
        use std::os::unix::fs::symlink;

        let directory = tempfile::tempdir().expect("tempdir");
        let database = directory.path().join("state.db");
        let target = directory.path().join("profile.md");
        let agent_md = directory.path().join("AGENT.md");
        std::fs::write(&target, "# Stable profile\n").expect("write target");
        symlink(&target, &agent_md).expect("create symlink");
        let store = SqliteStore::open(&database).await.expect("open store");

        let error = store
            .admit_agent_md_baseline(AgentMdBaselineAdmission {
                resource_id: "agent-profile".to_string(),
                path: agent_md,
                observed_at: 1_700_000_000,
            })
            .await
            .expect_err("symlink must fail");
        assert!(error.to_string().contains("target must not be a symlink"));
    }

    #[cfg(unix)]
    #[tokio::test]
    async fn rejects_symlink_replacement_after_no_follow_open() {
        use std::os::unix::fs::symlink;

        let directory = tempfile::tempdir().expect("tempdir");
        let database = directory.path().join("state.db");
        let agent_md = directory.path().join("AGENT.md");
        let displaced = directory.path().join("AGENT.displaced.md");
        let decoy = directory.path().join("decoy.md");
        std::fs::write(&agent_md, "# Stable profile\n").expect("write AGENT.md");
        std::fs::write(&decoy, "# Decoy profile\n").expect("write decoy");
        let store = SqliteStore::open(&database).await.expect("open store");
        let hook_agent_md = agent_md.clone();

        let error = store
            .admit_agent_md_baseline_with_before_transaction_hook(
                AgentMdBaselineAdmission {
                    resource_id: "agent-profile".to_string(),
                    path: agent_md,
                    observed_at: 1_700_000_000,
                },
                move || {
                    std::fs::rename(&hook_agent_md, &displaced).expect("displace original");
                    symlink(&decoy, &hook_agent_md).expect("install symlink replacement");
                },
            )
            .await
            .expect_err("post-open symlink replacement must fail");
        assert!(error
            .to_string()
            .contains("path no longer identifies the opened regular file"));
    }

    #[cfg(unix)]
    #[tokio::test]
    async fn rejects_same_path_regular_file_replacement_after_open() {
        let directory = tempfile::tempdir().expect("tempdir");
        let database = directory.path().join("state.db");
        let agent_md = directory.path().join("AGENT.md");
        let displaced = directory.path().join("AGENT.displaced.md");
        std::fs::write(&agent_md, "# Stable profile\n").expect("write AGENT.md");
        let store = SqliteStore::open(&database).await.expect("open store");
        let hook_agent_md = agent_md.clone();

        let error = store
            .admit_agent_md_baseline_with_before_transaction_hook(
                AgentMdBaselineAdmission {
                    resource_id: "agent-profile".to_string(),
                    path: agent_md,
                    observed_at: 1_700_000_000,
                },
                move || {
                    std::fs::rename(&hook_agent_md, &displaced).expect("displace original");
                    std::fs::write(&hook_agent_md, "# Replacement profile\n")
                        .expect("install regular replacement");
                },
            )
            .await
            .expect_err("same-path inode replacement must fail");
        assert!(error
            .to_string()
            .contains("path no longer identifies the opened regular file"));
    }

    #[cfg(unix)]
    #[tokio::test]
    async fn rejects_in_place_content_change_after_open() {
        let directory = tempfile::tempdir().expect("tempdir");
        let database = directory.path().join("state.db");
        let agent_md = directory.path().join("AGENT.md");
        std::fs::write(&agent_md, "# Stable profile\n").expect("write AGENT.md");
        let store = SqliteStore::open(&database).await.expect("open store");
        let hook_agent_md = agent_md.clone();

        let error = store
            .admit_agent_md_baseline_with_before_transaction_hook(
                AgentMdBaselineAdmission {
                    resource_id: "agent-profile".to_string(),
                    path: agent_md,
                    observed_at: 1_700_000_000,
                },
                move || {
                    std::fs::write(&hook_agent_md, "# Changed in place\n")
                        .expect("change opened file content");
                },
            )
            .await
            .expect_err("in-place content change must fail readback");
        assert!(error
            .to_string()
            .contains("resource changed during baseline admission readback"));
    }

    #[cfg(unix)]
    #[tokio::test]
    async fn concurrent_baseline_admissions_converge_on_one_genesis() {
        let directory = tempfile::tempdir().expect("tempdir");
        let database = directory.path().join("state.db");
        let agent_md = directory.path().join("AGENT.md");
        std::fs::write(&agent_md, "# Stable profile\n").expect("write AGENT.md");
        let left_store = SqliteStore::open(&database).await.expect("open left store");
        let right_store = SqliteStore::open(&database)
            .await
            .expect("open right store");
        let request = AgentMdBaselineAdmission {
            resource_id: "agent-profile".to_string(),
            path: agent_md,
            observed_at: 1_700_000_000,
        };

        let (left, right) = tokio::join!(
            left_store.admit_agent_md_baseline(request.clone()),
            right_store.admit_agent_md_baseline(request)
        );
        let left = left.expect("left admission");
        let right = right.expect("right admission");
        assert_ne!(left.version_created, right.version_created);
        assert_eq!(left.binding, right.binding);
        assert_eq!(left.version, right.version);
    }
}
