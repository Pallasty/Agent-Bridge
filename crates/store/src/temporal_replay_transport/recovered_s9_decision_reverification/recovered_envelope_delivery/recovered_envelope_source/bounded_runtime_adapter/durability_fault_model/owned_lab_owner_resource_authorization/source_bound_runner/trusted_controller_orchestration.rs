//! S20 private trusted-controller orchestration kernel.
//!
//! This module is deliberately default-off, synthetic-only, and non-live.  It
//! has no public re-export or runtime caller and no process, signal, mount,
//! network, credential, signing, or application-effect adapter.  Its private
//! checkpoint port has only an in-memory test implementation; consequently it
//! does not claim real whole-file rollback protection.

#![cfg_attr(not(test), allow(dead_code))]

#[cfg(feature = "temporal-evidence-s20b-owned-lab-rich-packet-validators-synthetic")]
mod rich_packet_validators;

use super::*;
use serde_json::Value;

const S20_APPLICATION_ID: i64 = 1_094_865_690;
const S20_USER_VERSION: i64 = 20;
const S20_CHECKPOINT_INITIAL_DOMAIN: &[u8] =
    b"agent-bridge/biocortex/owned-lab/s20/checkpoint-initial/v1";
const S20_CHECKPOINT_TRANSITION_DOMAIN: &[u8] =
    b"agent-bridge/biocortex/owned-lab/s20/checkpoint-transition/v1";
const S20_SYNTHETIC_CHECKPOINT_PROVIDER_DOMAIN: &[u8] =
    b"agent-bridge/biocortex/owned-lab/s20/synthetic-checkpoint-provider-identity/v1";
const S20_BUSINESS_CONTENT_ROOT_DOMAIN: &[u8] =
    b"agent-bridge/biocortex/owned-lab/s20/business-content-root/v1";
const S20_INITIAL_BUSINESS_CONTENT_ROOT_SHA256_KAT: &str =
    "5463bd72d21d1515cebb33c8c575883db86cd12c1a980c878192a9802459e56d";
const S20_PREFLIGHT_DOMAIN: &[u8] = b"agent-bridge/biocortex/owned-lab/s20/preflight/v1";
const S20_CLAIM_DOMAIN: &[u8] = b"agent-bridge/biocortex/owned-lab/s20/claim/v1";
const S20_ACTION_DOMAIN: &[u8] = b"agent-bridge/biocortex/owned-lab/s20/action-start/v1";
const S20_SYNTHETIC_RUN_BINDING_DOMAIN: &[u8] =
    b"agent-bridge/biocortex/owned-lab/s20/synthetic-manifest-run-binding/v1";
const S20_RICH_PACKET_STATUS: &str =
    "PARTIAL_PREFLIGHT_SECURITY_PROJECTION_ONLY_FOUR_FROZEN_RICH_SCHEMAS_NOT_IMPLEMENTED";
const S20_FOUR_RICH_SCHEMAS_FULLY_IMPLEMENTED: bool = false;
const S20_REAL_INDEPENDENT_CHECKPOINT_ADAPTER_PRESENT: bool = false;
const S20_LIVE_ACTION_ADAPTER_PRESENT: bool = false;
const S20_NEW_KERNEL_OWNER_REVIEW_BINDING_PRESENT: bool = false;
const S20_EXACT_ASSIGNMENT_MEMBERSHIP_VALIDATOR_IMPLEMENTED: bool = false;
const S20_FULL_DATABASE_CONTENT_AUTHENTICATION_IMPLEMENTED: bool = false;
const S20_REAL_PARENT_DIRECTORY_DURABILITY_ADAPTER_PRESENT: bool = false;
const S20_RICH_POSTRUN_RECEIPT_IMPLEMENTED: bool = false;
const S20_EXACT_CANARY_INDEX_VALIDATOR_IMPLEMENTED: bool = true;
const S20_ACTION_COUNT: u64 = 60;

const ATTEMPT_REGISTERED: &str = "REGISTERED_UNUSED";
const ATTEMPT_PREFLIGHT_RESERVED: &str = "PREFLIGHT_RESERVED";
const ATTEMPT_PREFLIGHT_VALIDATED: &str = "PREFLIGHT_VALIDATED";
const ATTEMPT_CLAIM_RESERVED: &str = "CLAIM_ATTEMPT_RESERVED";
const ATTEMPT_CLAIM_CONSUMED: &str = "CLAIM_CONSUMED";
const ATTEMPT_ACTION_LINEARIZED: &str = "ACTION_START_LINEARIZED";
const ATTEMPT_POSTRUN_TERMINAL: &str = "POSTRUN_TERMINAL";
const ATTEMPT_PREFLIGHT_FAILED: &str = "PREFLIGHT_FAILED_TERMINAL";
const ATTEMPT_CLAIM_FAILED: &str = "CLAIM_FAILED_TERMINAL";
const ATTEMPT_ACTION_FAILED: &str = "ACTION_FAILED_TERMINAL";

const S20_SCHEMA_SQL: &str = r#"
CREATE TABLE kernel_meta (
  singleton INTEGER PRIMARY KEY CHECK(singleton=1),
  database_identity_sha256 BLOB NOT NULL CHECK(length(database_identity_sha256)=32),
  schema_catalog_sha256 BLOB NOT NULL CHECK(length(schema_catalog_sha256)=32),
  business_content_root_sha256 BLOB NOT NULL CHECK(length(business_content_root_sha256)=32),
  generation INTEGER NOT NULL CHECK(generation>0),
  checkpoint_head_sha256 BLOB NOT NULL CHECK(length(checkpoint_head_sha256)=32)
) STRICT;
CREATE TRIGGER kernel_meta_update_guard BEFORE UPDATE ON kernel_meta
WHEN NEW.singleton!=OLD.singleton
  OR NEW.database_identity_sha256 IS NOT OLD.database_identity_sha256
  OR NEW.schema_catalog_sha256 IS NOT OLD.schema_catalog_sha256
  OR NEW.business_content_root_sha256 IS OLD.business_content_root_sha256
  OR NEW.generation!=OLD.generation+1
  OR NEW.checkpoint_head_sha256 IS OLD.checkpoint_head_sha256
BEGIN SELECT RAISE(ABORT,'S20_META_TRANSITION_REJECTED'); END;
CREATE TRIGGER kernel_meta_delete_guard BEFORE DELETE ON kernel_meta
BEGIN SELECT RAISE(ABORT,'S20_META_DELETE_REJECTED'); END;
CREATE TABLE authority_control (
  singleton INTEGER PRIMARY KEY CHECK(singleton=1),
  control_ledger_identity_sha256 BLOB NOT NULL CHECK(length(control_ledger_identity_sha256)=32),
  anti_rollback_policy_sha256 BLOB NOT NULL CHECK(length(anti_rollback_policy_sha256)=32),
  stop_state TEXT NOT NULL CHECK(stop_state IN ('CLEAR','TRIGGERED')),
  stop_revision INTEGER NOT NULL CHECK(stop_revision>0),
  current_revocation_epoch INTEGER NOT NULL CHECK(current_revocation_epoch>0),
  revocation_revision INTEGER NOT NULL CHECK(revocation_revision>0),
  stop_policy_identity_sha256 BLOB NOT NULL CHECK(length(stop_policy_identity_sha256)=32),
  revocation_policy_identity_sha256 BLOB NOT NULL CHECK(length(revocation_policy_identity_sha256)=32),
  sqlite_profile_sha256 BLOB NOT NULL CHECK(length(sqlite_profile_sha256)=32),
  sqlite_schema_sha256 BLOB NOT NULL CHECK(length(sqlite_schema_sha256)=32)
) STRICT;
CREATE TRIGGER authority_control_update_guard BEFORE UPDATE ON authority_control
WHEN NEW.singleton!=OLD.singleton
  OR NEW.control_ledger_identity_sha256 IS NOT OLD.control_ledger_identity_sha256
  OR NEW.anti_rollback_policy_sha256 IS NOT OLD.anti_rollback_policy_sha256
  OR NEW.stop_policy_identity_sha256 IS NOT OLD.stop_policy_identity_sha256
  OR NEW.revocation_policy_identity_sha256 IS NOT OLD.revocation_policy_identity_sha256
  OR NEW.sqlite_profile_sha256 IS NOT OLD.sqlite_profile_sha256
  OR NEW.sqlite_schema_sha256 IS NOT OLD.sqlite_schema_sha256
  OR (OLD.stop_state='TRIGGERED' AND NEW.stop_state!='TRIGGERED')
  OR (NEW.stop_state!=OLD.stop_state AND NOT (OLD.stop_state='CLEAR' AND NEW.stop_state='TRIGGERED'))
  OR (NEW.stop_state=OLD.stop_state AND NEW.stop_revision!=OLD.stop_revision)
  OR (NEW.stop_state!=OLD.stop_state AND NEW.stop_revision!=OLD.stop_revision+1)
  OR NEW.current_revocation_epoch<OLD.current_revocation_epoch
  OR (NEW.current_revocation_epoch=OLD.current_revocation_epoch
      AND NEW.revocation_revision!=OLD.revocation_revision)
  OR (NEW.current_revocation_epoch>OLD.current_revocation_epoch
      AND NEW.revocation_revision!=OLD.revocation_revision+1)
BEGIN SELECT RAISE(ABORT,'S20_CONTROL_TRANSITION_REJECTED'); END;
CREATE TRIGGER authority_control_delete_guard BEFORE DELETE ON authority_control
BEGIN SELECT RAISE(ABORT,'S20_CONTROL_DELETE_REJECTED'); END;
CREATE TABLE claim_ledger (
  authorization_id_sha256 BLOB NOT NULL CHECK(length(authorization_id_sha256)=32),
  claim_namespace_sha256 BLOB NOT NULL CHECK(length(claim_namespace_sha256)=32),
  claim_key_sha256 BLOB NOT NULL CHECK(length(claim_key_sha256)=32),
  signed_payload_sha256 BLOB NOT NULL CHECK(length(signed_payload_sha256)=32),
  subject_manifest_sha256 BLOB NOT NULL CHECK(length(subject_manifest_sha256)=32),
  resource_scope_sha256 BLOB NOT NULL CHECK(length(resource_scope_sha256)=32),
  signed_revocation_epoch INTEGER NOT NULL CHECK(signed_revocation_epoch>0),
  state TEXT NOT NULL CHECK(state IN ('AUTHORIZED_UNCLAIMED','CONSUMED_FOR_EXACT_RUN')),
  revision INTEGER NOT NULL CHECK(revision>0),
  successful_claim_count INTEGER NOT NULL CHECK(successful_claim_count IN (0,1)),
  run_id_sha256 BLOB CHECK(run_id_sha256 IS NULL OR length(run_id_sha256)=32),
  controller_binary_sha256 BLOB CHECK(controller_binary_sha256 IS NULL OR length(controller_binary_sha256)=32),
  runner_binary_sha256 BLOB NOT NULL CHECK(length(runner_binary_sha256)=32),
  capability_nonce_sha256 BLOB NOT NULL CHECK(length(capability_nonce_sha256)=32),
  preflight_receipt_sha256 BLOB CHECK(preflight_receipt_sha256 IS NULL OR length(preflight_receipt_sha256)=32),
  control_snapshot_sha256 BLOB CHECK(control_snapshot_sha256 IS NULL OR length(control_snapshot_sha256)=32),
  claim_receipt_sha256 BLOB CHECK(claim_receipt_sha256 IS NULL OR length(claim_receipt_sha256)=32),
  PRIMARY KEY(authorization_id_sha256,claim_namespace_sha256,claim_key_sha256)
) WITHOUT ROWID, STRICT;
CREATE TRIGGER claim_ledger_update_guard BEFORE UPDATE ON claim_ledger
WHEN NOT (
  OLD.state='AUTHORIZED_UNCLAIMED' AND NEW.state='CONSUMED_FOR_EXACT_RUN'
  AND NEW.revision=OLD.revision+1
  AND OLD.successful_claim_count=0 AND NEW.successful_claim_count=1
  AND OLD.run_id_sha256 IS NULL AND OLD.controller_binary_sha256 IS NULL
  AND OLD.preflight_receipt_sha256 IS NULL AND OLD.control_snapshot_sha256 IS NULL
  AND OLD.claim_receipt_sha256 IS NULL
  AND NEW.run_id_sha256 IS NOT NULL AND NEW.controller_binary_sha256 IS NOT NULL
  AND NEW.preflight_receipt_sha256 IS NOT NULL AND NEW.control_snapshot_sha256 IS NOT NULL
  AND NEW.claim_receipt_sha256 IS NOT NULL
  AND NEW.authorization_id_sha256 IS OLD.authorization_id_sha256
  AND NEW.claim_namespace_sha256 IS OLD.claim_namespace_sha256
  AND NEW.claim_key_sha256 IS OLD.claim_key_sha256
  AND NEW.signed_payload_sha256 IS OLD.signed_payload_sha256
  AND NEW.subject_manifest_sha256 IS OLD.subject_manifest_sha256
  AND NEW.resource_scope_sha256 IS OLD.resource_scope_sha256
  AND NEW.signed_revocation_epoch=OLD.signed_revocation_epoch
  AND NEW.runner_binary_sha256 IS OLD.runner_binary_sha256
  AND NEW.capability_nonce_sha256 IS OLD.capability_nonce_sha256
)
BEGIN SELECT RAISE(ABORT,'S20_CLAIM_TRANSITION_REJECTED'); END;
CREATE TRIGGER claim_ledger_delete_guard BEFORE DELETE ON claim_ledger
BEGIN SELECT RAISE(ABORT,'S20_CLAIM_DELETE_REJECTED'); END;
CREATE TABLE orchestration_attempt (
  authorization_id_sha256 BLOB NOT NULL CHECK(length(authorization_id_sha256)=32),
  claim_namespace_sha256 BLOB NOT NULL CHECK(length(claim_namespace_sha256)=32),
  claim_key_sha256 BLOB NOT NULL CHECK(length(claim_key_sha256)=32),
  owner_envelope_sha256 BLOB NOT NULL CHECK(length(owner_envelope_sha256)=32),
  trust_anchor_document_sha256 BLOB NOT NULL CHECK(length(trust_anchor_document_sha256)=32),
  owner_identity_sha256 BLOB NOT NULL CHECK(length(owner_identity_sha256)=32),
  owner_key_version INTEGER NOT NULL CHECK(owner_key_version>0),
  signed_payload_sha256 BLOB NOT NULL CHECK(length(signed_payload_sha256)=32),
  subject_manifest_sha256 BLOB NOT NULL CHECK(length(subject_manifest_sha256)=32),
  resource_scope_sha256 BLOB NOT NULL CHECK(length(resource_scope_sha256)=32),
  state TEXT NOT NULL CHECK(state IN (
    'REGISTERED_UNUSED','PREFLIGHT_RESERVED','PREFLIGHT_VALIDATED','CLAIM_ATTEMPT_RESERVED',
    'CLAIM_CONSUMED','ACTION_START_LINEARIZED','POSTRUN_TERMINAL',
    'PREFLIGHT_FAILED_TERMINAL','CLAIM_FAILED_TERMINAL','ACTION_FAILED_TERMINAL')),
  revision INTEGER NOT NULL CHECK(revision>0),
  run_id_sha256 BLOB CHECK(run_id_sha256 IS NULL OR length(run_id_sha256)=32),
  run_assignment_id_sha256 BLOB CHECK(run_assignment_id_sha256 IS NULL OR length(run_assignment_id_sha256)=32),
  challenge_nonce_sha256 BLOB CHECK(challenge_nonce_sha256 IS NULL OR length(challenge_nonce_sha256)=32),
  controller_binary_sha256 BLOB CHECK(controller_binary_sha256 IS NULL OR length(controller_binary_sha256)=32),
  controller_start_token_sha256 BLOB CHECK(controller_start_token_sha256 IS NULL OR length(controller_start_token_sha256)=32),
  boot_id_sha256 BLOB CHECK(boot_id_sha256 IS NULL OR length(boot_id_sha256)=32),
  preflight_receipt_sha256 BLOB CHECK(preflight_receipt_sha256 IS NULL OR length(preflight_receipt_sha256)=32),
  claim_receipt_sha256 BLOB CHECK(claim_receipt_sha256 IS NULL OR length(claim_receipt_sha256)=32),
  terminal_receipt_sha256 BLOB CHECK(terminal_receipt_sha256 IS NULL OR length(terminal_receipt_sha256)=32),
  PRIMARY KEY(authorization_id_sha256,claim_namespace_sha256,claim_key_sha256)
) WITHOUT ROWID, STRICT;
CREATE TRIGGER orchestration_attempt_update_guard BEFORE UPDATE ON orchestration_attempt
WHEN NEW.authorization_id_sha256 IS NOT OLD.authorization_id_sha256
  OR NEW.claim_namespace_sha256 IS NOT OLD.claim_namespace_sha256
  OR NEW.claim_key_sha256 IS NOT OLD.claim_key_sha256
  OR NEW.owner_envelope_sha256 IS NOT OLD.owner_envelope_sha256
  OR NEW.trust_anchor_document_sha256 IS NOT OLD.trust_anchor_document_sha256
  OR NEW.owner_identity_sha256 IS NOT OLD.owner_identity_sha256
  OR NEW.owner_key_version!=OLD.owner_key_version
  OR NEW.signed_payload_sha256 IS NOT OLD.signed_payload_sha256
  OR NEW.subject_manifest_sha256 IS NOT OLD.subject_manifest_sha256
  OR NEW.resource_scope_sha256 IS NOT OLD.resource_scope_sha256
  OR NEW.revision!=OLD.revision+1
  OR (OLD.state='REGISTERED_UNUSED' AND NOT (
       OLD.run_id_sha256 IS NULL AND OLD.run_assignment_id_sha256 IS NULL
       AND OLD.challenge_nonce_sha256 IS NULL AND OLD.controller_binary_sha256 IS NULL
       AND OLD.controller_start_token_sha256 IS NULL AND OLD.boot_id_sha256 IS NULL
       AND NEW.run_id_sha256 IS NOT NULL AND NEW.run_assignment_id_sha256 IS NOT NULL
       AND NEW.challenge_nonce_sha256 IS NOT NULL AND NEW.controller_binary_sha256 IS NOT NULL
       AND NEW.controller_start_token_sha256 IS NOT NULL AND NEW.boot_id_sha256 IS NOT NULL
  ))
  OR (OLD.state!='REGISTERED_UNUSED' AND (
       NEW.run_id_sha256 IS NOT OLD.run_id_sha256
       OR NEW.run_assignment_id_sha256 IS NOT OLD.run_assignment_id_sha256
       OR NEW.challenge_nonce_sha256 IS NOT OLD.challenge_nonce_sha256
       OR NEW.controller_binary_sha256 IS NOT OLD.controller_binary_sha256
       OR NEW.controller_start_token_sha256 IS NOT OLD.controller_start_token_sha256
       OR NEW.boot_id_sha256 IS NOT OLD.boot_id_sha256
  ))
  OR (NEW.preflight_receipt_sha256 IS NOT OLD.preflight_receipt_sha256 AND NOT (
       OLD.state='PREFLIGHT_RESERVED' AND NEW.state='PREFLIGHT_VALIDATED'
       AND OLD.preflight_receipt_sha256 IS NULL AND NEW.preflight_receipt_sha256 IS NOT NULL
  ))
  OR (NEW.claim_receipt_sha256 IS NOT OLD.claim_receipt_sha256 AND NOT (
       OLD.state='CLAIM_ATTEMPT_RESERVED' AND NEW.state='CLAIM_CONSUMED'
       AND OLD.claim_receipt_sha256 IS NULL AND NEW.claim_receipt_sha256 IS NOT NULL
  ))
  OR (NEW.terminal_receipt_sha256 IS NOT OLD.terminal_receipt_sha256 AND NOT (
       OLD.terminal_receipt_sha256 IS NULL AND NEW.terminal_receipt_sha256 IS NOT NULL
       AND NEW.state IN ('PREFLIGHT_FAILED_TERMINAL','CLAIM_FAILED_TERMINAL',
                         'ACTION_FAILED_TERMINAL','POSTRUN_TERMINAL')
  ))
  OR NOT (
    (OLD.state='REGISTERED_UNUSED' AND NEW.state='PREFLIGHT_RESERVED'
     AND NEW.preflight_receipt_sha256 IS NULL AND NEW.claim_receipt_sha256 IS NULL
     AND NEW.terminal_receipt_sha256 IS NULL)
    OR (OLD.state='PREFLIGHT_RESERVED' AND NEW.state='PREFLIGHT_VALIDATED'
        AND NEW.preflight_receipt_sha256 IS NOT NULL AND NEW.claim_receipt_sha256 IS NULL
        AND NEW.terminal_receipt_sha256 IS NULL)
    OR (OLD.state='PREFLIGHT_RESERVED' AND NEW.state='PREFLIGHT_FAILED_TERMINAL'
        AND NEW.preflight_receipt_sha256 IS NULL AND NEW.claim_receipt_sha256 IS NULL
        AND NEW.terminal_receipt_sha256 IS NOT NULL)
    OR (OLD.state='PREFLIGHT_VALIDATED' AND NEW.state='CLAIM_ATTEMPT_RESERVED'
        AND NEW.preflight_receipt_sha256 IS NOT NULL AND NEW.claim_receipt_sha256 IS NULL
        AND NEW.terminal_receipt_sha256 IS NULL)
    OR (OLD.state='CLAIM_ATTEMPT_RESERVED' AND NEW.state='CLAIM_CONSUMED'
        AND NEW.preflight_receipt_sha256 IS NOT NULL AND NEW.claim_receipt_sha256 IS NOT NULL
        AND NEW.terminal_receipt_sha256 IS NULL)
    OR (OLD.state='CLAIM_ATTEMPT_RESERVED' AND NEW.state='CLAIM_FAILED_TERMINAL'
        AND NEW.preflight_receipt_sha256 IS NOT NULL AND NEW.claim_receipt_sha256 IS NULL
        AND NEW.terminal_receipt_sha256 IS NOT NULL)
    OR (OLD.state='CLAIM_CONSUMED' AND NEW.state='ACTION_START_LINEARIZED'
        AND NEW.preflight_receipt_sha256 IS NOT NULL AND NEW.claim_receipt_sha256 IS NOT NULL
        AND NEW.terminal_receipt_sha256 IS NULL)
    OR (OLD.state='CLAIM_CONSUMED' AND NEW.state='ACTION_FAILED_TERMINAL'
        AND NEW.preflight_receipt_sha256 IS NOT NULL AND NEW.claim_receipt_sha256 IS NOT NULL
        AND NEW.terminal_receipt_sha256 IS NOT NULL)
    OR (OLD.state='ACTION_START_LINEARIZED' AND NEW.state IN ('POSTRUN_TERMINAL','ACTION_FAILED_TERMINAL')
        AND NEW.preflight_receipt_sha256 IS NOT NULL AND NEW.claim_receipt_sha256 IS NOT NULL
        AND NEW.terminal_receipt_sha256 IS NOT NULL)
  )
BEGIN SELECT RAISE(ABORT,'S20_ATTEMPT_TRANSITION_REJECTED'); END;
CREATE TRIGGER orchestration_attempt_delete_guard BEFORE DELETE ON orchestration_attempt
BEGIN SELECT RAISE(ABORT,'S20_ATTEMPT_DELETE_REJECTED'); END;
CREATE TABLE action_journal (
  authorization_id_sha256 BLOB NOT NULL CHECK(length(authorization_id_sha256)=32),
  claim_namespace_sha256 BLOB NOT NULL CHECK(length(claim_namespace_sha256)=32),
  claim_key_sha256 BLOB NOT NULL CHECK(length(claim_key_sha256)=32),
  action_index INTEGER NOT NULL CHECK(action_index>=0 AND action_index<60),
  run_assignment_id_sha256 BLOB NOT NULL CHECK(length(run_assignment_id_sha256)=32),
  operation_id_sha256 BLOB NOT NULL CHECK(length(operation_id_sha256)=32),
  intent_sha256 BLOB NOT NULL CHECK(length(intent_sha256)=32),
  outcome TEXT NOT NULL CHECK(outcome IN ('INTENT_DURABLE_SYNTHETIC','STARTED_SYNTHETIC','FAILED_SYNTHETIC')),
  PRIMARY KEY(authorization_id_sha256,claim_namespace_sha256,claim_key_sha256,action_index)
) WITHOUT ROWID, STRICT;
CREATE TRIGGER action_journal_update_guard BEFORE UPDATE ON action_journal
WHEN NEW.authorization_id_sha256 IS NOT OLD.authorization_id_sha256
  OR NEW.claim_namespace_sha256 IS NOT OLD.claim_namespace_sha256
  OR NEW.claim_key_sha256 IS NOT OLD.claim_key_sha256
  OR NEW.action_index!=OLD.action_index
  OR NEW.run_assignment_id_sha256 IS NOT OLD.run_assignment_id_sha256
  OR NEW.operation_id_sha256 IS NOT OLD.operation_id_sha256
  OR NEW.intent_sha256 IS NOT OLD.intent_sha256
  OR OLD.outcome!='INTENT_DURABLE_SYNTHETIC'
  OR NEW.outcome NOT IN ('STARTED_SYNTHETIC','FAILED_SYNTHETIC')
BEGIN SELECT RAISE(ABORT,'S20_ACTION_UPDATE_REJECTED'); END;
CREATE TRIGGER action_journal_delete_guard BEFORE DELETE ON action_journal
BEGIN SELECT RAISE(ABORT,'S20_ACTION_DELETE_REJECTED'); END;
"#;

#[derive(Debug)]
struct KernelHeadV1 {
    database_identity_sha256: [u8; 32],
    schema_catalog_sha256: [u8; 32],
    business_content_root_sha256: [u8; 32],
    generation: u64,
    checkpoint_head_sha256: [u8; 32],
}

enum CheckpointSnapshotV1 {
    Committed(KernelHeadV1),
    Prepared,
}

#[derive(Debug)]
struct PreparedCheckpointV1 {
    database_identity_sha256: [u8; 32],
    schema_catalog_sha256: [u8; 32],
    business_content_root_sha256: [u8; 32],
    generation: u64,
    checkpoint_head_sha256: [u8; 32],
}

mod checkpoint_seal {
    pub trait Sealed {}
}

trait SyntheticCheckpointPortV1: checkpoint_seal::Sealed {
    fn snapshot(&self) -> CheckpointSnapshotV1;
    fn provider_identity_sha256(&self) -> [u8; 32];
    fn independent_failure_domain_proved(&self) -> bool;
    fn prepare(
        &mut self,
        expected: &KernelHeadV1,
        intent_sha256: [u8; 32],
        next_business_content_root_sha256: [u8; 32],
    ) -> AuthorizationResult<PreparedCheckpointV1>;
    fn commit(&mut self, prepared: PreparedCheckpointV1) -> AuthorizationResult<()>;
}

fn checkpoint_initial_digest(
    database_identity_sha256: &[u8; 32],
    schema_catalog_sha256: &[u8; 32],
    business_content_root_sha256: &[u8; 32],
) -> AuthorizationResult<[u8; 32]> {
    framed_digest(
        S20_CHECKPOINT_INITIAL_DOMAIN,
        &[
            database_identity_sha256,
            schema_catalog_sha256,
            business_content_root_sha256,
        ],
    )
}

fn checkpoint_transition_digest(
    previous: &[u8; 32],
    generation: u64,
    intent: &[u8; 32],
    business_content_root_sha256: &[u8; 32],
) -> AuthorizationResult<[u8; 32]> {
    framed_digest(
        S20_CHECKPOINT_TRANSITION_DOMAIN,
        &[
            previous,
            &generation.to_be_bytes(),
            intent,
            business_content_root_sha256,
        ],
    )
}

fn append_business_value_frame_v1(
    message: &mut Vec<u8>,
    value: rusqlite::types::ValueRef<'_>,
) -> AuthorizationResult<()> {
    let append = |message: &mut Vec<u8>, tag: u8, bytes: &[u8]| -> AuthorizationResult<()> {
        let len = u64::try_from(bytes.len())
            .map_err(|_| sqlite_error("s20_content_root", "business value length overflow"))?;
        message.push(tag);
        message.extend_from_slice(&len.to_be_bytes());
        message.extend_from_slice(bytes);
        Ok(())
    };
    match value {
        rusqlite::types::ValueRef::Null => append(message, 0, &[]),
        rusqlite::types::ValueRef::Integer(value) => append(message, 1, &value.to_be_bytes()),
        rusqlite::types::ValueRef::Real(value) => {
            append(message, 2, &value.to_bits().to_be_bytes())
        }
        rusqlite::types::ValueRef::Text(value) => append(message, 3, value),
        rusqlite::types::ValueRef::Blob(value) => append(message, 4, value),
    }
}

fn append_business_table_v1(
    connection: &Connection,
    message: &mut Vec<u8>,
    table: &'static str,
    columns: &[&'static str],
    order_by: &'static str,
) -> AuthorizationResult<()> {
    append_u32_frame(message, table.as_bytes())?;
    message.extend_from_slice(
        &u64::try_from(columns.len())
            .map_err(|_| sqlite_error("s20_content_root", "column count overflow"))?
            .to_be_bytes(),
    );
    for column in columns {
        append_u32_frame(message, column.as_bytes())?;
    }

    // Table and column names are frozen compile-time literals above; no
    // caller-controlled identifier reaches this statement.
    let sql = format!(
        "SELECT {} FROM {} ORDER BY {}",
        columns.join(","),
        table,
        order_by
    );
    let mut statement = connection
        .prepare(&sql)
        .map_err(|_| sqlite_error("s20_content_root", "cannot prepare business table read"))?;
    let mut rows = statement
        .query([])
        .map_err(|_| sqlite_error("s20_content_root", "cannot query business table"))?;
    let mut row_count = 0_u64;
    let mut framed_rows = Vec::new();
    while let Some(row) = rows
        .next()
        .map_err(|_| sqlite_error("s20_content_root", "cannot iterate business table"))?
    {
        framed_rows.extend_from_slice(&row_count.to_be_bytes());
        for index in 0..columns.len() {
            let value = row.get_ref(index).map_err(|_| {
                sqlite_error("s20_content_root", "cannot read typed business value")
            })?;
            append_business_value_frame_v1(&mut framed_rows, value)?;
        }
        row_count = row_count
            .checked_add(1)
            .ok_or_else(|| sqlite_error("s20_content_root", "business row count overflow"))?;
    }
    message.extend_from_slice(&row_count.to_be_bytes());
    message.extend_from_slice(&framed_rows);
    Ok(())
}

fn sqlite_business_content_root_for_head_v1(
    connection: &Connection,
    database_identity_sha256: &[u8; 32],
    schema_catalog_sha256: &[u8; 32],
    generation: u64,
) -> AuthorizationResult<[u8; 32]> {
    if generation == 0 || !nonzero(database_identity_sha256) || !nonzero(schema_catalog_sha256) {
        return Err(sqlite_error(
            "s20_content_root",
            "database identity, schema catalog, or generation is invalid",
        ));
    }
    const AUTHORITY_CONTROL_COLUMNS: &[&str] = &[
        "singleton",
        "control_ledger_identity_sha256",
        "anti_rollback_policy_sha256",
        "stop_state",
        "stop_revision",
        "current_revocation_epoch",
        "revocation_revision",
        "stop_policy_identity_sha256",
        "revocation_policy_identity_sha256",
        "sqlite_profile_sha256",
        "sqlite_schema_sha256",
    ];
    const CLAIM_LEDGER_COLUMNS: &[&str] = &[
        "authorization_id_sha256",
        "claim_namespace_sha256",
        "claim_key_sha256",
        "signed_payload_sha256",
        "subject_manifest_sha256",
        "resource_scope_sha256",
        "signed_revocation_epoch",
        "state",
        "revision",
        "successful_claim_count",
        "run_id_sha256",
        "controller_binary_sha256",
        "runner_binary_sha256",
        "capability_nonce_sha256",
        "preflight_receipt_sha256",
        "control_snapshot_sha256",
        "claim_receipt_sha256",
    ];
    const ORCHESTRATION_ATTEMPT_COLUMNS: &[&str] = &[
        "authorization_id_sha256",
        "claim_namespace_sha256",
        "claim_key_sha256",
        "owner_envelope_sha256",
        "trust_anchor_document_sha256",
        "owner_identity_sha256",
        "owner_key_version",
        "signed_payload_sha256",
        "subject_manifest_sha256",
        "resource_scope_sha256",
        "state",
        "revision",
        "run_id_sha256",
        "run_assignment_id_sha256",
        "challenge_nonce_sha256",
        "controller_binary_sha256",
        "controller_start_token_sha256",
        "boot_id_sha256",
        "preflight_receipt_sha256",
        "claim_receipt_sha256",
        "terminal_receipt_sha256",
    ];
    const ACTION_JOURNAL_COLUMNS: &[&str] = &[
        "authorization_id_sha256",
        "claim_namespace_sha256",
        "claim_key_sha256",
        "action_index",
        "run_assignment_id_sha256",
        "operation_id_sha256",
        "intent_sha256",
        "outcome",
    ];

    let mut message = Vec::new();
    append_u32_frame(&mut message, S20_BUSINESS_CONTENT_ROOT_DOMAIN)?;
    append_u32_frame(&mut message, database_identity_sha256)?;
    append_u32_frame(&mut message, schema_catalog_sha256)?;
    message.extend_from_slice(&generation.to_be_bytes());
    message.extend_from_slice(&4_u64.to_be_bytes());
    append_business_table_v1(
        connection,
        &mut message,
        "authority_control",
        AUTHORITY_CONTROL_COLUMNS,
        "singleton",
    )?;
    append_business_table_v1(
        connection,
        &mut message,
        "claim_ledger",
        CLAIM_LEDGER_COLUMNS,
        "authorization_id_sha256,claim_namespace_sha256,claim_key_sha256",
    )?;
    append_business_table_v1(
        connection,
        &mut message,
        "orchestration_attempt",
        ORCHESTRATION_ATTEMPT_COLUMNS,
        "authorization_id_sha256,claim_namespace_sha256,claim_key_sha256",
    )?;
    append_business_table_v1(
        connection,
        &mut message,
        "action_journal",
        ACTION_JOURNAL_COLUMNS,
        "authorization_id_sha256,claim_namespace_sha256,claim_key_sha256,action_index",
    )?;
    Ok(sha256_bytes(&message))
}

fn sqlite_business_content_root_v1(connection: &Connection) -> AuthorizationResult<[u8; 32]> {
    let head = read_kernel_head(connection)?;
    sqlite_business_content_root_for_head_v1(
        connection,
        &head.database_identity_sha256,
        &head.schema_catalog_sha256,
        head.generation,
    )
}

fn sqlite_schema_catalog_digest_v1(connection: &Connection) -> AuthorizationResult<[u8; 32]> {
    let mut statement = connection
        .prepare(
            "SELECT type,name,tbl_name,sql FROM sqlite_schema
             WHERE name NOT LIKE 'sqlite_%' ORDER BY type,name,tbl_name",
        )
        .map_err(|_| sqlite_error("s20_schema", "cannot prepare schema catalog read"))?;
    let mut rows = statement
        .query([])
        .map_err(|_| sqlite_error("s20_schema", "cannot read schema catalog"))?;
    let mut message = Vec::new();
    append_u32_frame(
        &mut message,
        b"agent-bridge/biocortex/owned-lab/s20/sqlite-schema-catalog/v1",
    )?;
    let mut count = 0_u64;
    while let Some(row) = rows
        .next()
        .map_err(|_| sqlite_error("s20_schema", "schema catalog row failed"))?
    {
        count = count
            .checked_add(1)
            .ok_or_else(|| sqlite_error("s20_schema", "schema object count overflow"))?;
        for index in 0..4 {
            let field = row
                .get::<_, String>(index)
                .map_err(|_| sqlite_error("s20_schema", "schema catalog field failed"))?;
            message.extend_from_slice(&(field.len() as u64).to_be_bytes());
            message.extend_from_slice(field.as_bytes());
        }
    }
    if count != 15 {
        return Err(sqlite_error(
            "s20_schema",
            "schema catalog object count drifted",
        ));
    }
    Ok(sha256_bytes(&message))
}

fn verify_s20_profile(connection: &Connection) -> AuthorizationResult<()> {
    if pragma_i64(connection, "PRAGMA application_id")? != S20_APPLICATION_ID
        || pragma_i64(connection, "PRAGMA user_version")? != S20_USER_VERSION
        || !pragma_text(connection, "PRAGMA journal_mode")?.eq_ignore_ascii_case("delete")
        || pragma_i64(connection, "PRAGMA synchronous")? != 3
        || pragma_i64(connection, "PRAGMA temp_store")? != 1
        || pragma_i64(connection, "PRAGMA mmap_size")? != 0
        || pragma_i64(connection, "PRAGMA cache_size")? != -2048
        || pragma_i64(connection, "PRAGMA foreign_keys")? != 1
        || pragma_i64(connection, "PRAGMA trusted_schema")? != 0
    {
        return Err(sqlite_error(
            "s20_profile",
            "SQLite profile readback drifted",
        ));
    }
    Ok(())
}

fn apply_s20_profile(connection: &Connection) -> AuthorizationResult<()> {
    connection
        .execute_batch(
            "PRAGMA synchronous=EXTRA;
             PRAGMA temp_store=FILE;
             PRAGMA mmap_size=0;
             PRAGMA cache_size=-2048;
             PRAGMA foreign_keys=ON;
             PRAGMA trusted_schema=OFF;",
        )
        .map_err(|_| sqlite_error("s20_profile", "cannot apply defensive SQLite profile"))?;
    verify_s20_profile(connection)
}

fn read_kernel_head(connection: &Connection) -> AuthorizationResult<KernelHeadV1> {
    connection
        .query_row(
            "SELECT database_identity_sha256,schema_catalog_sha256,
                    business_content_root_sha256,generation,checkpoint_head_sha256
             FROM kernel_meta WHERE singleton=1",
            [],
            |row| {
                Ok((
                    row.get::<_, Vec<u8>>(0)?,
                    row.get::<_, Vec<u8>>(1)?,
                    row.get::<_, Vec<u8>>(2)?,
                    row.get::<_, i64>(3)?,
                    row.get::<_, Vec<u8>>(4)?,
                ))
            },
        )
        .map_err(|_| sqlite_error("s20_meta", "cannot read kernel metadata"))
        .and_then(|row| {
            Ok(KernelHeadV1 {
                database_identity_sha256: row
                    .0
                    .try_into()
                    .map_err(|_| sqlite_error("s20_meta", "database identity length drifted"))?,
                schema_catalog_sha256: row
                    .1
                    .try_into()
                    .map_err(|_| sqlite_error("s20_meta", "schema digest length drifted"))?,
                business_content_root_sha256: row.2.try_into().map_err(|_| {
                    sqlite_error("s20_meta", "business content root length drifted")
                })?,
                generation: u64::try_from(row.3)
                    .map_err(|_| sqlite_error("s20_meta", "generation is invalid"))?,
                checkpoint_head_sha256: row
                    .4
                    .try_into()
                    .map_err(|_| sqlite_error("s20_meta", "checkpoint length drifted"))?,
            })
        })
}

fn verify_committed_checkpoint<P: SyntheticCheckpointPortV1>(
    connection: &Connection,
    port: &P,
) -> AuthorizationResult<KernelHeadV1> {
    verify_s20_profile(connection)?;
    let database = read_kernel_head(connection)?;
    if sqlite_schema_catalog_digest_v1(connection)? != database.schema_catalog_sha256 {
        return Err(sqlite_error(
            "s20_schema",
            "live schema differs from checkpointed schema",
        ));
    }
    if sqlite_business_content_root_v1(connection)? != database.business_content_root_sha256 {
        return Err(sqlite_error(
            "s20_content_root",
            "live business content differs from checkpointed content root",
        ));
    }
    match port.snapshot() {
        CheckpointSnapshotV1::Committed(external)
            if external.database_identity_sha256 == database.database_identity_sha256
                && external.schema_catalog_sha256 == database.schema_catalog_sha256
                && external.business_content_root_sha256
                    == database.business_content_root_sha256
                && external.generation == database.generation
                && external.checkpoint_head_sha256 == database.checkpoint_head_sha256 =>
        {
            Ok(database)
        }
        CheckpointSnapshotV1::Committed(_) | CheckpointSnapshotV1::Prepared => Err(sqlite_error(
            "s20_checkpoint",
            "external checkpoint is stale, future, forked, prepared, or mismatched",
        )),
    }
}

/// Opaque evidence that the live SQLite business rows, committed kernel head,
/// and the sealed external checkpoint snapshot were recomputed and equal in
/// one verification call.  Raw digests supplied by a rich-packet caller never
/// construct this token.
#[must_use]
struct ValidatedCommittedDatabaseStateV1 {
    database_identity_sha256: [u8; 32],
    schema_catalog_sha256: [u8; 32],
    business_content_root_sha256: [u8; 32],
    generation: u64,
    checkpoint_head_sha256: [u8; 32],
    checkpoint_provider_identity_sha256: [u8; 32],
    independent_failure_domain_proved: bool,
}

fn validate_committed_database_state_v1<P: SyntheticCheckpointPortV1>(
    connection: &Connection,
    port: &P,
) -> AuthorizationResult<ValidatedCommittedDatabaseStateV1> {
    let head = verify_committed_checkpoint(connection, port)?;
    Ok(ValidatedCommittedDatabaseStateV1 {
        database_identity_sha256: head.database_identity_sha256,
        schema_catalog_sha256: head.schema_catalog_sha256,
        business_content_root_sha256: head.business_content_root_sha256,
        generation: head.generation,
        checkpoint_head_sha256: head.checkpoint_head_sha256,
        checkpoint_provider_identity_sha256: port.provider_identity_sha256(),
        independent_failure_domain_proved: port.independent_failure_domain_proved(),
    })
}

fn prepare_transition<P: SyntheticCheckpointPortV1>(
    transaction: &rusqlite::Transaction<'_>,
    port: &mut P,
    old: &KernelHeadV1,
    intent_sha256: [u8; 32],
) -> AuthorizationResult<PreparedCheckpointV1> {
    let still_old = read_kernel_head(transaction)?;
    if still_old.database_identity_sha256 != old.database_identity_sha256
        || still_old.schema_catalog_sha256 != old.schema_catalog_sha256
        || still_old.business_content_root_sha256 != old.business_content_root_sha256
        || still_old.generation != old.generation
        || still_old.checkpoint_head_sha256 != old.checkpoint_head_sha256
    {
        return Err(sqlite_error(
            "s20_content_root",
            "kernel head changed before staged business content was sealed",
        ));
    }
    let next_generation = old
        .generation
        .checked_add(1)
        .ok_or_else(|| sqlite_error("s20_content_root", "checkpoint generation overflow"))?;
    let staged_at_old_generation = sqlite_business_content_root_for_head_v1(
        transaction,
        &old.database_identity_sha256,
        &old.schema_catalog_sha256,
        old.generation,
    )?;
    if staged_at_old_generation == old.business_content_root_sha256 {
        return Err(sqlite_error(
            "s20_content_root",
            "checkpointed transaction did not change business content",
        ));
    }
    let next_business_content_root_sha256 = sqlite_business_content_root_for_head_v1(
        transaction,
        &old.database_identity_sha256,
        &old.schema_catalog_sha256,
        next_generation,
    )?;
    port.prepare(old, intent_sha256, next_business_content_root_sha256)
}

fn advance_meta(
    transaction: &rusqlite::Transaction<'_>,
    prepared: &PreparedCheckpointV1,
) -> AuthorizationResult<()> {
    if sqlite_business_content_root_for_head_v1(
        transaction,
        &prepared.database_identity_sha256,
        &prepared.schema_catalog_sha256,
        prepared.generation,
    )? != prepared.business_content_root_sha256
    {
        return Err(sqlite_error(
            "s20_content_root",
            "prepared checkpoint does not bind the staged business content",
        ));
    }
    let meta_changed = transaction
        .execute(
            "UPDATE kernel_meta
             SET business_content_root_sha256=?1,generation=?2,checkpoint_head_sha256=?3
             WHERE singleton=1",
            params![
                &prepared.business_content_root_sha256[..],
                to_sql_integer(prepared.generation)?,
                &prepared.checkpoint_head_sha256[..],
            ],
        )
        .map_err(|_| sqlite_error("s20_meta", "cannot advance kernel metadata"))?;
    if meta_changed != 1 {
        return Err(sqlite_error(
            "s20_meta",
            "kernel metadata update was not singular",
        ));
    }
    Ok(())
}

#[derive(Clone)]
struct PreflightReservationRequestV1 {
    run_id_sha256: [u8; 32],
    run_assignment_id_sha256: [u8; 32],
    challenge_nonce_sha256: [u8; 32],
    controller_binary_sha256: [u8; 32],
    controller_start_token_sha256: [u8; 32],
    boot_id_sha256: [u8; 32],
}

#[must_use]
struct ReservedPreflightV1 {
    request: PreflightReservationRequestV1,
}

struct SyntheticMeasuredPreflightV1 {
    runner_binary_sha256: [u8; 32],
    observer_binary_sha256: [u8; 32],
    root_parent_identity_sha256: [u8; 32],
    side_effect_count: u64,
}

#[must_use]
struct ValidatedPreflightS20V1 {
    request: PreflightReservationRequestV1,
    preflight_receipt_sha256: [u8; 32],
    control_snapshot_sha256: [u8; 32],
    stop_revision: u64,
    revocation_revision: u64,
}

#[must_use]
struct BurnedClaimAttemptV1 {
    preflight: ValidatedPreflightS20V1,
}

#[must_use]
struct ClaimedRunPermitS20V1 {
    run_id_sha256: [u8; 32],
    run_assignment_id_sha256: [u8; 32],
    claim_receipt_sha256: [u8; 32],
    controller_start_token_sha256: [u8; 32],
    next_action_index: u64,
    _process_local: Rc<()>,
}

enum ClaimOutcomeS20V1 {
    Claimed(ClaimedRunPermitS20V1),
    FailedTerminal([u8; 32]),
}

fn exact_attempt_key_params<'a>(authorized: &'a AuthorizedUnclaimedS19SubjectV1) -> [&'a [u8]; 3] {
    [
        &authorized.authorization.authorization_id_sha256,
        &authorized.subject.claim_namespace_sha256,
        &authorized.subject.claim_key_sha256,
    ]
}

struct ExactControlReadV1 {
    stop_state: String,
    stop_revision: u64,
    current_revocation_epoch: u64,
    revocation_revision: u64,
    control_ledger_identity_sha256: [u8; 32],
    anti_rollback_policy_sha256: [u8; 32],
    stop_policy_identity_sha256: [u8; 32],
    revocation_policy_identity_sha256: [u8; 32],
    sqlite_profile_sha256: [u8; 32],
    sqlite_schema_sha256: [u8; 32],
}

fn read_exact_controls(connection: &Connection) -> AuthorizationResult<ExactControlReadV1> {
    let row = connection
        .query_row(
            "SELECT stop_state,stop_revision,current_revocation_epoch,revocation_revision,
                    control_ledger_identity_sha256,anti_rollback_policy_sha256,
                    stop_policy_identity_sha256,revocation_policy_identity_sha256,
                    sqlite_profile_sha256,sqlite_schema_sha256
             FROM authority_control WHERE singleton=1",
            [],
            |row| {
                Ok((
                    row.get::<_, String>(0)?,
                    row.get::<_, i64>(1)?,
                    row.get::<_, i64>(2)?,
                    row.get::<_, i64>(3)?,
                    row.get::<_, Vec<u8>>(4)?,
                    row.get::<_, Vec<u8>>(5)?,
                    row.get::<_, Vec<u8>>(6)?,
                    row.get::<_, Vec<u8>>(7)?,
                    row.get::<_, Vec<u8>>(8)?,
                    row.get::<_, Vec<u8>>(9)?,
                ))
            },
        )
        .map_err(|_| sqlite_error("s20_control", "cannot read authority controls"))?;
    Ok(ExactControlReadV1 {
        stop_state: row.0,
        stop_revision: u64::try_from(row.1)
            .map_err(|_| sqlite_error("s20_control", "STOP revision is invalid"))?,
        current_revocation_epoch: u64::try_from(row.2)
            .map_err(|_| sqlite_error("s20_control", "revocation epoch is invalid"))?,
        revocation_revision: u64::try_from(row.3)
            .map_err(|_| sqlite_error("s20_control", "revocation revision is invalid"))?,
        control_ledger_identity_sha256: row
            .4
            .try_into()
            .map_err(|_| sqlite_error("s20_control", "control ledger identity length drifted"))?,
        anti_rollback_policy_sha256: row
            .5
            .try_into()
            .map_err(|_| sqlite_error("s20_control", "anti-rollback policy length drifted"))?,
        stop_policy_identity_sha256: row
            .6
            .try_into()
            .map_err(|_| sqlite_error("s20_control", "STOP policy identity length drifted"))?,
        revocation_policy_identity_sha256: row.7.try_into().map_err(|_| {
            sqlite_error("s20_control", "revocation policy identity length drifted")
        })?,
        sqlite_profile_sha256: row
            .8
            .try_into()
            .map_err(|_| sqlite_error("s20_control", "SQLite profile length drifted"))?,
        sqlite_schema_sha256: row
            .9
            .try_into()
            .map_err(|_| sqlite_error("s20_control", "SQLite schema length drifted"))?,
    })
}

fn controls_match_authorized_s20(
    controls: &ExactControlReadV1,
    authorized: &AuthorizedUnclaimedS19SubjectV1,
) -> bool {
    controls.stop_state == STOP_CLEAR
        && controls.stop_revision > 0
        && controls.current_revocation_epoch == authorized.authorization.revocation_epoch
        && controls.revocation_revision > 0
        && controls.control_ledger_identity_sha256
            == authorized.subject.control_ledger_identity_sha256
        && controls.anti_rollback_policy_sha256 == authorized.subject.anti_rollback_policy_sha256
        && controls.stop_policy_identity_sha256 == authorized.subject.stop_control_policy_sha256
        && controls.revocation_policy_identity_sha256 == authorized.revocation_policy_sha256
        && controls.sqlite_profile_sha256 == authorized.subject.sqlite_profile_sha256
        && controls.sqlite_schema_sha256 == authorized.subject.sqlite_schema_sha256
}

fn control_is_clear_and_current(
    connection: &Connection,
    authorized: &AuthorizedUnclaimedS19SubjectV1,
) -> AuthorizationResult<bool> {
    Ok(controls_match_authorized_s20(
        &read_exact_controls(connection)?,
        authorized,
    ))
}

// S19 authenticates the manifest and run-level controller bindings but does
// not carry an independently authorized assignment ledger.  S20A therefore
// derives one deterministic synthetic run binding and rejects arbitrary caller
// values.  This is deliberately not represented as exact assignment
// membership; that stronger proof remains an S20B contract obligation.
fn synthetic_manifest_run_binding_v1(
    authorized: &AuthorizedUnclaimedS19SubjectV1,
    run_id_sha256: &[u8; 32],
) -> AuthorizationResult<[u8; 32]> {
    framed_digest(
        S20_SYNTHETIC_RUN_BINDING_DOMAIN,
        &[
            b"SYNTHETIC_MANIFEST_RUN_BOUND_NOT_ASSIGNMENT_MEMBERSHIP_PROOF",
            &authorized.subject.canonical_manifest_sha256,
            run_id_sha256,
        ],
    )
}

fn reserve_preflight_once_v1<P: SyntheticCheckpointPortV1>(
    connection: &mut Connection,
    port: &mut P,
    authorized: &AuthorizedUnclaimedS19SubjectV1,
    request: PreflightReservationRequestV1,
) -> AuthorizationResult<ReservedPreflightV1> {
    if ![
        &request.run_id_sha256[..],
        &request.run_assignment_id_sha256[..],
        &request.challenge_nonce_sha256[..],
        &request.controller_binary_sha256[..],
        &request.controller_start_token_sha256[..],
        &request.boot_id_sha256[..],
    ]
    .iter()
    .all(|value| nonzero(value))
        || request.run_assignment_id_sha256
            != synthetic_manifest_run_binding_v1(authorized, &request.run_id_sha256)?
        || request.controller_binary_sha256 != authorized.subject.controller_binary_sha256
        || request.boot_id_sha256 != authorized.subject.boot_id_sha256
    {
        return Err(manifest_error(
            "s20_preflight_reserve",
            "reservation binding drifted",
        ));
    }
    let transaction = connection
        .transaction_with_behavior(rusqlite::TransactionBehavior::Immediate)
        .map_err(|_| sqlite_error("s20_preflight_reserve", "cannot begin reservation"))?;
    let old = verify_committed_checkpoint(&transaction, port)?;
    if !control_is_clear_and_current(&transaction, authorized)? {
        return Err(manifest_error(
            "s20_preflight_reserve",
            "control is not clear/current",
        ));
    }
    let key = exact_attempt_key_params(authorized);
    let state = transaction
        .query_row(
            "SELECT state FROM orchestration_attempt
             WHERE authorization_id_sha256=?1 AND claim_namespace_sha256=?2 AND claim_key_sha256=?3",
            params![key[0], key[1], key[2]],
            |row| row.get::<_, String>(0),
        )
        .map_err(|_| sqlite_error("s20_preflight_reserve", "eligible row is absent"))?;
    if state != ATTEMPT_REGISTERED {
        return Err(manifest_error(
            "s20_preflight_reserve",
            "attempt was already reserved or terminalized",
        ));
    }
    let intent = framed_digest(
        S20_PREFLIGHT_DOMAIN,
        &[
            b"RESERVE",
            key[0],
            key[1],
            key[2],
            &request.run_id_sha256,
            &request.run_assignment_id_sha256,
            &request.challenge_nonce_sha256,
            &request.controller_binary_sha256,
            &request.controller_start_token_sha256,
            &request.boot_id_sha256,
        ],
    )?;
    let changed = transaction
        .execute(
            "UPDATE orchestration_attempt
             SET state='PREFLIGHT_RESERVED',revision=revision+1,run_id_sha256=?1,
                 run_assignment_id_sha256=?2,challenge_nonce_sha256=?3,
                 controller_binary_sha256=?4,controller_start_token_sha256=?5,boot_id_sha256=?6
             WHERE authorization_id_sha256=?7 AND claim_namespace_sha256=?8
               AND claim_key_sha256=?9 AND state='REGISTERED_UNUSED'",
            params![
                &request.run_id_sha256[..],
                &request.run_assignment_id_sha256[..],
                &request.challenge_nonce_sha256[..],
                &request.controller_binary_sha256[..],
                &request.controller_start_token_sha256[..],
                &request.boot_id_sha256[..],
                key[0],
                key[1],
                key[2],
            ],
        )
        .map_err(|_| sqlite_error("s20_preflight_reserve", "reservation update failed"))?;
    if changed != 1 {
        return Err(sqlite_error(
            "s20_preflight_reserve",
            "reservation CAS failed",
        ));
    }
    let prepared = prepare_transition(&transaction, port, &old, intent)?;
    advance_meta(&transaction, &prepared)?;
    transaction
        .commit()
        .map_err(|_| sqlite_error("s20_preflight_reserve", "reservation commit unknown"))?;
    port.commit(prepared)?;
    Ok(ReservedPreflightV1 { request })
}

fn validate_preflight_once_v1<P: SyntheticCheckpointPortV1>(
    connection: &mut Connection,
    port: &mut P,
    authorized: &AuthorizedUnclaimedS19SubjectV1,
    reserved: ReservedPreflightV1,
    measured: SyntheticMeasuredPreflightV1,
) -> AuthorizationResult<ValidatedPreflightS20V1> {
    let valid = measured.runner_binary_sha256 == authorized.subject.runner_binary_sha256
        && measured.observer_binary_sha256 == authorized.subject.preflight_observer_binary_sha256
        && measured.root_parent_identity_sha256 == authorized.subject.root_parent_identity_sha256
        && measured.side_effect_count == 0;
    let transaction = connection
        .transaction_with_behavior(rusqlite::TransactionBehavior::Immediate)
        .map_err(|_| sqlite_error("s20_preflight_validate", "cannot begin validation"))?;
    let head = verify_committed_checkpoint(&transaction, port)?;
    let controls = read_exact_controls(&transaction)?;
    let controls_ok = controls_match_authorized_s20(&controls, authorized);
    let control_snapshot_sha256 = framed_digest(
        S20_PREFLIGHT_DOMAIN,
        &[
            b"CONTROL_SNAPSHOT",
            &head.database_identity_sha256,
            &head.checkpoint_head_sha256,
            controls.stop_state.as_bytes(),
            &controls.stop_revision.to_be_bytes(),
            &controls.current_revocation_epoch.to_be_bytes(),
            &controls.revocation_revision.to_be_bytes(),
            &controls.control_ledger_identity_sha256,
            &controls.anti_rollback_policy_sha256,
            &controls.stop_policy_identity_sha256,
            &controls.revocation_policy_identity_sha256,
            &controls.sqlite_profile_sha256,
            &controls.sqlite_schema_sha256,
        ],
    )?;
    let key = exact_attempt_key_params(authorized);
    let receipt = framed_digest(
        S20_PREFLIGHT_DOMAIN,
        &[
            if valid && controls_ok {
                &b"VALID"[..]
            } else {
                &b"FAILED"[..]
            },
            key[0],
            key[1],
            key[2],
            &authorized.authorization.payload_sha256,
            &authorized.authorization.owner_envelope_sha256,
            &authorized.subject.canonical_manifest_sha256,
            &reserved.request.run_id_sha256,
            &reserved.request.run_assignment_id_sha256,
            &reserved.request.challenge_nonce_sha256,
            &reserved.request.controller_start_token_sha256,
            &control_snapshot_sha256,
        ],
    )?;
    let next_state = if valid && controls_ok {
        ATTEMPT_PREFLIGHT_VALIDATED
    } else {
        ATTEMPT_PREFLIGHT_FAILED
    };
    let changed = transaction
        .execute(
            "UPDATE orchestration_attempt SET state=?1,revision=revision+1,
                    preflight_receipt_sha256=?2,terminal_receipt_sha256=?3
             WHERE authorization_id_sha256=?4 AND claim_namespace_sha256=?5
               AND claim_key_sha256=?6 AND state='PREFLIGHT_RESERVED'
               AND run_id_sha256=?7 AND run_assignment_id_sha256=?8
               AND challenge_nonce_sha256=?9 AND controller_binary_sha256=?10
               AND controller_start_token_sha256=?11 AND boot_id_sha256=?12",
            params![
                next_state,
                if valid && controls_ok {
                    Some(&receipt[..])
                } else {
                    None
                },
                if valid && controls_ok {
                    None
                } else {
                    Some(&receipt[..])
                },
                key[0],
                key[1],
                key[2],
                &reserved.request.run_id_sha256[..],
                &reserved.request.run_assignment_id_sha256[..],
                &reserved.request.challenge_nonce_sha256[..],
                &reserved.request.controller_binary_sha256[..],
                &reserved.request.controller_start_token_sha256[..],
                &reserved.request.boot_id_sha256[..],
            ],
        )
        .map_err(|_| sqlite_error("s20_preflight_validate", "validation transition failed"))?;
    if changed != 1 {
        return Err(sqlite_error(
            "s20_preflight_validate",
            "validation token was replayed",
        ));
    }
    let prepared = prepare_transition(&transaction, port, &head, receipt)?;
    advance_meta(&transaction, &prepared)?;
    transaction
        .commit()
        .map_err(|_| sqlite_error("s20_preflight_validate", "validation commit unknown"))?;
    port.commit(prepared)?;
    if !valid || !controls_ok {
        return Err(manifest_error(
            "s20_preflight_validate",
            "preflight failed and was terminally tombstoned",
        ));
    }
    Ok(ValidatedPreflightS20V1 {
        request: reserved.request,
        preflight_receipt_sha256: receipt,
        control_snapshot_sha256,
        stop_revision: controls.stop_revision,
        revocation_revision: controls.revocation_revision,
    })
}

fn burn_claim_attempt_once_v1<P: SyntheticCheckpointPortV1>(
    connection: &mut Connection,
    port: &mut P,
    authorized: &AuthorizedUnclaimedS19SubjectV1,
    preflight: ValidatedPreflightS20V1,
) -> AuthorizationResult<BurnedClaimAttemptV1> {
    let transaction = connection
        .transaction_with_behavior(rusqlite::TransactionBehavior::Immediate)
        .map_err(|_| sqlite_error("s20_claim_burn", "cannot begin claim burn"))?;
    let old = verify_committed_checkpoint(&transaction, port)?;
    let key = exact_attempt_key_params(authorized);
    let intent = framed_digest(
        S20_CLAIM_DOMAIN,
        &[
            b"BURN_ONCE",
            key[0],
            key[1],
            key[2],
            &preflight.request.run_id_sha256,
            &preflight.request.run_assignment_id_sha256,
            &preflight.preflight_receipt_sha256,
        ],
    )?;
    let changed = transaction
        .execute(
            "UPDATE orchestration_attempt SET state='CLAIM_ATTEMPT_RESERVED',revision=revision+1
             WHERE authorization_id_sha256=?1 AND claim_namespace_sha256=?2
               AND claim_key_sha256=?3 AND state='PREFLIGHT_VALIDATED'
               AND run_id_sha256=?4 AND preflight_receipt_sha256=?5",
            params![
                key[0],
                key[1],
                key[2],
                &preflight.request.run_id_sha256[..],
                &preflight.preflight_receipt_sha256[..],
            ],
        )
        .map_err(|_| sqlite_error("s20_claim_burn", "claim burn transition failed"))?;
    if changed != 1 {
        return Err(sqlite_error(
            "s20_claim_burn",
            "claim opportunity already burned",
        ));
    }
    let prepared = prepare_transition(&transaction, port, &old, intent)?;
    advance_meta(&transaction, &prepared)?;
    transaction
        .commit()
        .map_err(|_| sqlite_error("s20_claim_burn", "claim burn commit unknown"))?;
    port.commit(prepared)?;
    Ok(BurnedClaimAttemptV1 { preflight })
}

fn execute_burned_claim_once_v1<P: SyntheticCheckpointPortV1>(
    connection: &mut Connection,
    port: &mut P,
    authorized: &AuthorizedUnclaimedS19SubjectV1,
    burned: BurnedClaimAttemptV1,
) -> AuthorizationResult<ClaimOutcomeS20V1> {
    let transaction = connection
        .transaction_with_behavior(rusqlite::TransactionBehavior::Immediate)
        .map_err(|_| sqlite_error("s20_claim", "cannot begin single claim"))?;
    let old = verify_committed_checkpoint(&transaction, port)?;
    let key = exact_attempt_key_params(authorized);
    let controls = read_exact_controls(&transaction)?;
    let controls_ok = controls_match_authorized_s20(&controls, authorized)
        && controls.stop_revision == burned.preflight.stop_revision
        && controls.revocation_revision == burned.preflight.revocation_revision;
    let next_revision = authorized
        .subject
        .expected_unclaimed_revision
        .checked_add(1)
        .ok_or_else(|| sqlite_error("s20_claim", "claim revision overflow"))?;
    let success_receipt = framed_digest(
        S20_CLAIM_DOMAIN,
        &[
            b"SUCCESS",
            key[0],
            key[1],
            key[2],
            &authorized.authorization.payload_sha256,
            &authorized.subject.canonical_manifest_sha256,
            &burned.preflight.request.run_id_sha256,
            &burned.preflight.request.controller_binary_sha256,
            &authorized.subject.runner_binary_sha256,
            &authorized.capability_nonce_sha256,
            &burned.preflight.preflight_receipt_sha256,
            &burned.preflight.control_snapshot_sha256,
            &burned.preflight.stop_revision.to_be_bytes(),
            &burned.preflight.revocation_revision.to_be_bytes(),
            &next_revision.to_be_bytes(),
        ],
    )?;
    let changed = if controls_ok {
        transaction
            .execute(
                "UPDATE claim_ledger SET state='CONSUMED_FOR_EXACT_RUN',revision=?1,
                        successful_claim_count=1,
                        run_id_sha256=?2,controller_binary_sha256=?3,
                        preflight_receipt_sha256=?4,control_snapshot_sha256=?5,
                        claim_receipt_sha256=?6
                 WHERE authorization_id_sha256=?7 AND claim_namespace_sha256=?8
                   AND claim_key_sha256=?9 AND signed_payload_sha256=?10
                   AND subject_manifest_sha256=?11 AND resource_scope_sha256=?12
                   AND signed_revocation_epoch=?13 AND state='AUTHORIZED_UNCLAIMED'
                   AND revision=?14 AND successful_claim_count=0 AND run_id_sha256 IS NULL
                   AND controller_binary_sha256 IS NULL AND preflight_receipt_sha256 IS NULL
                   AND control_snapshot_sha256 IS NULL AND claim_receipt_sha256 IS NULL
                   AND runner_binary_sha256=?15 AND capability_nonce_sha256=?16
                   AND EXISTS(
                     SELECT 1 FROM authority_control WHERE singleton=1
                       AND control_ledger_identity_sha256=?17
                       AND anti_rollback_policy_sha256=?18
                       AND stop_state='CLEAR' AND stop_revision=?19
                       AND current_revocation_epoch=?13 AND revocation_revision=?20
                       AND stop_policy_identity_sha256=?21
                       AND revocation_policy_identity_sha256=?22
                       AND sqlite_profile_sha256=?23 AND sqlite_schema_sha256=?24
                   )",
                params![
                    to_sql_integer(next_revision)?,
                    &burned.preflight.request.run_id_sha256[..],
                    &burned.preflight.request.controller_binary_sha256[..],
                    &burned.preflight.preflight_receipt_sha256[..],
                    &burned.preflight.control_snapshot_sha256[..],
                    &success_receipt[..],
                    key[0],
                    key[1],
                    key[2],
                    &authorized.authorization.payload_sha256[..],
                    &authorized.subject.canonical_manifest_sha256[..],
                    &authorized.subject.resource_scope_sha256[..],
                    to_sql_integer(authorized.authorization.revocation_epoch)?,
                    to_sql_integer(authorized.subject.expected_unclaimed_revision)?,
                    &authorized.subject.runner_binary_sha256[..],
                    &authorized.capability_nonce_sha256[..],
                    &authorized.subject.control_ledger_identity_sha256[..],
                    &authorized.subject.anti_rollback_policy_sha256[..],
                    to_sql_integer(burned.preflight.stop_revision)?,
                    to_sql_integer(burned.preflight.revocation_revision)?,
                    &authorized.subject.stop_control_policy_sha256[..],
                    &authorized.revocation_policy_sha256[..],
                    &authorized.subject.sqlite_profile_sha256[..],
                    &authorized.subject.sqlite_schema_sha256[..],
                ],
            )
            .map_err(|_| sqlite_error("s20_claim", "claim CAS failed"))?
    } else {
        0
    };
    let success = changed == 1;
    let receipt = if success {
        success_receipt
    } else {
        framed_digest(
            S20_CLAIM_DOMAIN,
            &[
                if controls_ok {
                    &b"FAILED_CAS_PREDICATE"[..]
                } else {
                    &b"FAILED_CONTROL"[..]
                },
                key[0],
                key[1],
                key[2],
                &authorized.authorization.payload_sha256,
                &authorized.subject.canonical_manifest_sha256,
                &burned.preflight.request.run_id_sha256,
                &burned.preflight.preflight_receipt_sha256,
                &burned.preflight.control_snapshot_sha256,
            ],
        )?
    };
    let intent = framed_digest(
        S20_CLAIM_DOMAIN,
        &[
            if success {
                &b"COMMIT_SUCCESS"[..]
            } else {
                &b"COMMIT_FAILURE"[..]
            },
            &receipt,
        ],
    )?;
    let attempt_changed = transaction
        .execute(
            "UPDATE orchestration_attempt SET state=?1,revision=revision+1,
                    claim_receipt_sha256=?2,terminal_receipt_sha256=?3
             WHERE authorization_id_sha256=?4 AND claim_namespace_sha256=?5
               AND claim_key_sha256=?6 AND state='CLAIM_ATTEMPT_RESERVED'
               AND run_id_sha256=?7 AND preflight_receipt_sha256=?8",
            params![
                if success {
                    ATTEMPT_CLAIM_CONSUMED
                } else {
                    ATTEMPT_CLAIM_FAILED
                },
                if success { Some(&receipt[..]) } else { None },
                if success { None } else { Some(&receipt[..]) },
                key[0],
                key[1],
                key[2],
                &burned.preflight.request.run_id_sha256[..],
                &burned.preflight.preflight_receipt_sha256[..],
            ],
        )
        .map_err(|_| sqlite_error("s20_claim", "attempt result tombstone failed"))?;
    if attempt_changed != 1 {
        return Err(sqlite_error(
            "s20_claim",
            "claim attempt was not uniquely reserved",
        ));
    }
    let prepared = prepare_transition(&transaction, port, &old, intent)?;
    advance_meta(&transaction, &prepared)?;
    transaction
        .commit()
        .map_err(|_| sqlite_error("s20_claim", "claim result commit unknown"))?;
    port.commit(prepared)?;
    if success {
        Ok(ClaimOutcomeS20V1::Claimed(ClaimedRunPermitS20V1 {
            run_id_sha256: burned.preflight.request.run_id_sha256,
            run_assignment_id_sha256: burned.preflight.request.run_assignment_id_sha256,
            claim_receipt_sha256: receipt,
            controller_start_token_sha256: burned.preflight.request.controller_start_token_sha256,
            next_action_index: 0,
            _process_local: Rc::new(()),
        }))
    } else {
        Ok(ClaimOutcomeS20V1::FailedTerminal(receipt))
    }
}

mod starter_seal {
    pub trait Sealed {}
}

trait SyntheticActionStarterV1: starter_seal::Sealed {
    fn start_once(&mut self, action_index: u64, intent_sha256: [u8; 32]) -> bool;
}

// The private Rust API and `action_journal.action_index` are deliberately
// zero-based.  Frozen receipt semantics are one-based and must use this
// checked projection before deriving an operation or receipt digest.
fn action_sequence_from_zero_based_index_v1(
    action_index_zero_based: u64,
) -> AuthorizationResult<u64> {
    if action_index_zero_based >= S20_ACTION_COUNT {
        return Err(manifest_error(
            "s20_action",
            "zero-based action index is outside the frozen sequence",
        ));
    }
    action_index_zero_based
        .checked_add(1)
        .ok_or_else(|| manifest_error("s20_action", "one-based action sequence overflow"))
}

fn linearize_synthetic_action_start_v1<P, S>(
    connection: &mut Connection,
    port: &mut P,
    authorized: &AuthorizedUnclaimedS19SubjectV1,
    mut permit: ClaimedRunPermitS20V1,
    expected_action_index: u64,
    starter: &mut S,
) -> AuthorizationResult<(ClaimedRunPermitS20V1, [u8; 32])>
where
    P: SyntheticCheckpointPortV1,
    S: SyntheticActionStarterV1,
{
    if permit.next_action_index != expected_action_index {
        return Err(manifest_error("s20_action", "action index is not exact"));
    }
    let action_sequence = action_sequence_from_zero_based_index_v1(expected_action_index)?;
    // Phase one permanently burns the exact action index before the sealed
    // starter can be called.  The external PREPARED record is durable first;
    // then the SQLite intent and logical head commit; then the checkpoint is
    // finalized.  A crash at any cut leaves either PREPARED or an immutable
    // intent and cannot be resumed by a reconstructed permit.
    let intent_transaction = connection
        .transaction_with_behavior(rusqlite::TransactionBehavior::Immediate)
        .map_err(|_| sqlite_error("s20_action", "cannot begin action intent"))?;
    let intent_old = verify_committed_checkpoint(&intent_transaction, port)?;
    if !control_is_clear_and_current(&intent_transaction, authorized)? {
        return Err(manifest_error(
            "s20_action",
            "STOP/revocation won before action",
        ));
    }
    let key = exact_attempt_key_params(authorized);
    let bound = intent_transaction
        .query_row(
            "SELECT count(*) FROM orchestration_attempt a JOIN claim_ledger c
               ON c.authorization_id_sha256=a.authorization_id_sha256
              AND c.claim_namespace_sha256=a.claim_namespace_sha256
              AND c.claim_key_sha256=a.claim_key_sha256
             WHERE a.authorization_id_sha256=?1 AND a.claim_namespace_sha256=?2
               AND a.claim_key_sha256=?3
               AND a.state IN ('CLAIM_CONSUMED','ACTION_START_LINEARIZED')
               AND c.state='CONSUMED_FOR_EXACT_RUN' AND c.run_id_sha256=?4
               AND c.claim_receipt_sha256=?5 AND a.run_assignment_id_sha256=?6
               AND a.controller_start_token_sha256=?7",
            params![
                key[0],
                key[1],
                key[2],
                &permit.run_id_sha256[..],
                &permit.claim_receipt_sha256[..],
                &permit.run_assignment_id_sha256[..],
                &permit.controller_start_token_sha256[..]
            ],
            |row| row.get::<_, i64>(0),
        )
        .map_err(|_| sqlite_error("s20_action", "cannot verify consumed claim"))?;
    if bound != 1 {
        return Err(manifest_error(
            "s20_action",
            "claim/attempt binding is not consumed",
        ));
    }
    let journal_prefix = intent_transaction
        .query_row(
            "SELECT count(*),
                    coalesce(sum(CASE WHEN action_index<?4
                                           AND outcome='STARTED_SYNTHETIC'
                                      THEN 1 ELSE 0 END),0)
               FROM action_journal
              WHERE authorization_id_sha256=?1 AND claim_namespace_sha256=?2
                AND claim_key_sha256=?3",
            params![
                key[0],
                key[1],
                key[2],
                to_sql_integer(expected_action_index)?
            ],
            |row| Ok((row.get::<_, i64>(0)?, row.get::<_, i64>(1)?)),
        )
        .map_err(|_| sqlite_error("s20_action", "cannot verify exact action prefix"))?;
    let expected_prefix = to_sql_integer(expected_action_index)?;
    if journal_prefix != (expected_prefix, expected_prefix) {
        return Err(manifest_error(
            "s20_action",
            "action journal is not one complete STARTED prefix",
        ));
    }
    let operation_id_sha256 = framed_digest(
        S20_ACTION_DOMAIN,
        &[
            b"SYNTHETIC_MANIFEST_RUN_BOUND_SEQUENCE_NOT_ASSIGNMENT_MEMBERSHIP_PROOF",
            &permit.run_assignment_id_sha256,
            &permit.run_id_sha256,
            &action_sequence.to_be_bytes(),
        ],
    )?;
    let intent = framed_digest(
        S20_ACTION_DOMAIN,
        &[
            key[0],
            key[1],
            key[2],
            &permit.run_id_sha256,
            &permit.run_assignment_id_sha256,
            &operation_id_sha256,
            &permit.claim_receipt_sha256,
            &permit.controller_start_token_sha256,
            b"ACTION_SEQUENCE_ONE_BASED",
            &action_sequence.to_be_bytes(),
        ],
    )?;
    let intent_changed = intent_transaction
        .execute(
            "INSERT INTO action_journal(
               authorization_id_sha256,claim_namespace_sha256,claim_key_sha256,
               action_index,run_assignment_id_sha256,operation_id_sha256,intent_sha256,outcome)
             VALUES(?1,?2,?3,?4,?5,?6,?7,'INTENT_DURABLE_SYNTHETIC')",
            params![
                key[0],
                key[1],
                key[2],
                to_sql_integer(expected_action_index)?,
                &permit.run_assignment_id_sha256[..],
                &operation_id_sha256[..],
                &intent[..],
            ],
        )
        .map_err(|_| sqlite_error("s20_action", "action intent was already consumed"))?;
    if intent_changed != 1 {
        return Err(sqlite_error(
            "s20_action",
            "action intent insert was not singular",
        ));
    }
    let prepared = prepare_transition(&intent_transaction, port, &intent_old, intent)?;
    advance_meta(&intent_transaction, &prepared)?;
    intent_transaction
        .commit()
        .map_err(|_| sqlite_error("s20_action", "action intent commit unknown"))?;
    port.commit(prepared)?;
    permit.next_action_index = expected_action_index
        .checked_add(1)
        .ok_or_else(|| manifest_error("s20_action", "action index overflow"))?;

    // Phase two re-enters the same SQLite writer domain used by STOP and
    // revocation.  Whichever obtains this lock first defines the order.  No
    // after-the-fact guard leaves this function.
    let start_transaction = connection
        .transaction_with_behavior(rusqlite::TransactionBehavior::Immediate)
        .map_err(|_| sqlite_error("s20_action", "cannot begin action start"))?;
    let outcome_old = verify_committed_checkpoint(&start_transaction, port)?;
    let controls_ok = control_is_clear_and_current(&start_transaction, authorized)?;
    let outcome_intent = framed_digest(
        S20_ACTION_DOMAIN,
        &[
            if controls_ok {
                &b"START_ONCE"[..]
            } else {
                &b"DENY_AFTER_INTENT"[..]
            },
            &intent,
        ],
    )?;
    if !controls_ok {
        let journal_changed = start_transaction
            .execute(
                "UPDATE action_journal SET outcome='FAILED_SYNTHETIC'
                 WHERE authorization_id_sha256=?1 AND claim_namespace_sha256=?2
                   AND claim_key_sha256=?3 AND action_index=?4
                   AND intent_sha256=?5 AND outcome='INTENT_DURABLE_SYNTHETIC'",
                params![
                    key[0],
                    key[1],
                    key[2],
                    to_sql_integer(expected_action_index)?,
                    &intent[..]
                ],
            )
            .map_err(|_| sqlite_error("s20_action", "cannot deny durable action intent"))?;
        if journal_changed != 1 {
            return Err(sqlite_error(
                "s20_action",
                "denied durable action intent was not singular",
            ));
        }
        let attempt_changed = start_transaction
            .execute(
                "UPDATE orchestration_attempt SET state='ACTION_FAILED_TERMINAL',revision=revision+1,
                        terminal_receipt_sha256=?1
                 WHERE authorization_id_sha256=?2 AND claim_namespace_sha256=?3
                   AND claim_key_sha256=?4
                   AND state IN ('CLAIM_CONSUMED','ACTION_START_LINEARIZED')",
                params![&intent[..], key[0], key[1], key[2]],
            )
            .map_err(|_| sqlite_error("s20_action", "cannot terminalize denied action"))?;
        if attempt_changed != 1 {
            return Err(sqlite_error(
                "s20_action",
                "denied action terminal transition was not singular",
            ));
        }
        let outcome_prepared =
            prepare_transition(&start_transaction, port, &outcome_old, outcome_intent)?;
        advance_meta(&start_transaction, &outcome_prepared)?;
        start_transaction
            .commit()
            .map_err(|_| sqlite_error("s20_action", "denied action commit unknown"))?;
        port.commit(outcome_prepared)?;
        return Err(manifest_error(
            "s20_action",
            "STOP/revocation won before start",
        ));
    }
    let started = starter.start_once(expected_action_index, intent);
    let journal_changed = start_transaction
        .execute(
            "UPDATE action_journal SET outcome=?1
             WHERE authorization_id_sha256=?2 AND claim_namespace_sha256=?3
               AND claim_key_sha256=?4 AND action_index=?5
               AND intent_sha256=?6 AND outcome='INTENT_DURABLE_SYNTHETIC'",
            params![
                if started {
                    "STARTED_SYNTHETIC"
                } else {
                    "FAILED_SYNTHETIC"
                },
                key[0],
                key[1],
                key[2],
                to_sql_integer(expected_action_index)?,
                &intent[..],
            ],
        )
        .map_err(|_| sqlite_error("s20_action", "cannot commit sealed starter outcome"))?;
    if journal_changed != 1 {
        return Err(sqlite_error(
            "s20_action",
            "sealed starter outcome update was not singular",
        ));
    }
    if !started {
        let attempt_changed = start_transaction
            .execute(
                "UPDATE orchestration_attempt SET state='ACTION_FAILED_TERMINAL',revision=revision+1,
                        terminal_receipt_sha256=?1
                 WHERE authorization_id_sha256=?2 AND claim_namespace_sha256=?3
                   AND claim_key_sha256=?4
                   AND state IN ('CLAIM_CONSUMED','ACTION_START_LINEARIZED')",
                params![&intent[..], key[0], key[1], key[2]],
            )
            .map_err(|_| sqlite_error("s20_action", "cannot terminalize failed action"))?;
        if attempt_changed != 1 {
            return Err(sqlite_error(
                "s20_action",
                "failed action terminal transition was not singular",
            ));
        }
    } else if expected_action_index == S20_ACTION_COUNT - 1 {
        let attempt_changed = start_transaction
            .execute(
                "UPDATE orchestration_attempt SET state='POSTRUN_TERMINAL',revision=revision+1,
                        terminal_receipt_sha256=?1
                 WHERE authorization_id_sha256=?2 AND claim_namespace_sha256=?3
                   AND claim_key_sha256=?4 AND state='ACTION_START_LINEARIZED'",
                params![&intent[..], key[0], key[1], key[2]],
            )
            .map_err(|_| sqlite_error("s20_action", "cannot terminalize complete synthetic run"))?;
        if attempt_changed != 1 {
            return Err(sqlite_error(
                "s20_action",
                "complete synthetic run terminal transition was not singular",
            ));
        }
    } else if expected_action_index == 0 {
        let attempt_changed = start_transaction
            .execute(
                "UPDATE orchestration_attempt SET state='ACTION_START_LINEARIZED',revision=revision+1
                 WHERE authorization_id_sha256=?1 AND claim_namespace_sha256=?2
                   AND claim_key_sha256=?3 AND state='CLAIM_CONSUMED'",
                params![key[0], key[1], key[2]],
            )
            .map_err(|_| sqlite_error("s20_action", "cannot record first linearized action"))?;
        if attempt_changed != 1 {
            return Err(sqlite_error(
                "s20_action",
                "first action linearization transition was not singular",
            ));
        }
    } else {
        let attempt_count = start_transaction
            .query_row(
                "SELECT count(*) FROM orchestration_attempt
                 WHERE authorization_id_sha256=?1 AND claim_namespace_sha256=?2
                   AND claim_key_sha256=?3 AND state='ACTION_START_LINEARIZED'",
                params![key[0], key[1], key[2]],
                |row| row.get::<_, i64>(0),
            )
            .map_err(|_| sqlite_error("s20_action", "cannot verify prior linearization"))?;
        if attempt_count != 1 {
            return Err(sqlite_error(
                "s20_action",
                "later action lacks one prior linearization",
            ));
        }
    }
    let outcome_prepared =
        prepare_transition(&start_transaction, port, &outcome_old, outcome_intent)?;
    advance_meta(&start_transaction, &outcome_prepared)?;
    start_transaction
        .commit()
        .map_err(|_| sqlite_error("s20_action", "action outcome commit unknown"))?;
    port.commit(outcome_prepared)?;
    if started {
        Ok((permit, intent))
    } else {
        Err(manifest_error(
            "s20_action",
            "synthetic starter failed terminally",
        ))
    }
}

#[derive(Debug, Eq, PartialEq)]
enum PartialRichSecurityProjectionKindV1 {
    PreflightProjection,
}

struct PartialExpectedRichSecurityProjectionV1 {
    kind: PartialRichSecurityProjectionKindV1,
    exact_value: Value,
    self_digest_key: &'static str,
    digest_domain: &'static [u8],
}

fn seal_rich_value_v1(
    mut value: Value,
    self_digest_key: &str,
    domain: &[u8],
) -> AuthorizationResult<Value> {
    value
        .as_object_mut()
        .ok_or_else(|| manifest_error("s20_rich", "rich packet is not an object"))?
        .remove(self_digest_key);
    let body = restricted_canonical_bytes(&value)?;
    let digest = framed_digest(domain, &[&body])?;
    value
        .as_object_mut()
        .expect("rich packet object was checked")
        .insert(self_digest_key.to_owned(), Value::String(hex(&digest)));
    Ok(value)
}

fn validate_partial_rich_security_projection_v1(
    raw: &[u8],
    expected: PartialExpectedRichSecurityProjectionV1,
) -> AuthorizationResult<PartialRichSecurityProjectionKindV1> {
    let candidate = parse_restricted_canonical(raw)?;
    let sealed = seal_rich_value_v1(
        expected.exact_value,
        expected.self_digest_key,
        expected.digest_domain,
    )?;
    if candidate != sealed || restricted_canonical_bytes(&candidate)? != raw {
        return Err(manifest_error(
            "s20_rich",
            "partial rich security projection differs from independent expected semantics",
        ));
    }
    Ok(expected.kind)
}

#[derive(Clone, Copy)]
enum CanaryAccountingModeV1 {
    SyntheticZero,
    CompleteExact,
}

struct ExactCanaryAccountingV1 {
    ol00_count: u64,
    ol04_count: u64,
    ol05_count: u64,
    assigned_attempt_count: u64,
    planned_pidfd_sigkill_count: u64,
    planned_fresh_exec_read_count: u64,
    planned_s16_mapping_phase_count: u64,
    actual_assigned_attempt_count: u64,
    actual_observation_count: u64,
    assigned_action_start_receipt_count: u64,
    actual_pidfd_sigkill_count: u64,
    actual_fresh_exec_read_count: u64,
    actual_s16_mapping_phase_count: u64,
    successful_claim_count: u64,
    retry_count: u64,
}

fn validate_exact_canary_accounting_v1(
    mode: CanaryAccountingModeV1,
    accounting: &ExactCanaryAccountingV1,
) -> AuthorizationResult<()> {
    let frozen_index = accounting.ol00_count == 1
        && accounting.ol04_count == 6
        && accounting.ol05_count == 53
        && accounting.assigned_attempt_count == 60
        && accounting.planned_pidfd_sigkill_count == 59
        && accounting.planned_fresh_exec_read_count == 59
        && accounting.planned_s16_mapping_phase_count == 113
        && accounting.retry_count == 0;
    let observed = match mode {
        CanaryAccountingModeV1::SyntheticZero => {
            accounting.actual_assigned_attempt_count == 0
                && accounting.actual_observation_count == 0
                && accounting.assigned_action_start_receipt_count == 0
                && accounting.actual_pidfd_sigkill_count == 0
                && accounting.actual_fresh_exec_read_count == 0
                && accounting.actual_s16_mapping_phase_count == 0
                && accounting.successful_claim_count == 0
        }
        CanaryAccountingModeV1::CompleteExact => {
            accounting.actual_assigned_attempt_count == 60
                && accounting.actual_observation_count == 60
                && accounting.assigned_action_start_receipt_count == 60
                && accounting.actual_pidfd_sigkill_count == 59
                && accounting.actual_fresh_exec_read_count == 59
                && accounting.actual_s16_mapping_phase_count == 113
                && accounting.successful_claim_count == 1
        }
    };
    if !frozen_index || !observed {
        return Err(manifest_error(
            "s20_canary_accounting",
            "canary index, one-claim, no-retry, or observed accounting drifted",
        ));
    }
    Ok(())
}

#[cfg(test)]
struct SyntheticCheckpointPortImplV1 {
    database_identity_sha256: [u8; 32],
    schema_catalog_sha256: [u8; 32],
    business_content_root_sha256: [u8; 32],
    generation: u64,
    checkpoint_head_sha256: [u8; 32],
    checkpoint_provider_identity_sha256: [u8; 32],
    prepared: Option<([u8; 32], [u8; 32], [u8; 32], u64, [u8; 32])>,
    fail_commit_once: bool,
}

#[cfg(test)]
impl checkpoint_seal::Sealed for SyntheticCheckpointPortImplV1 {}

#[cfg(test)]
impl SyntheticCheckpointPortV1 for SyntheticCheckpointPortImplV1 {
    fn snapshot(&self) -> CheckpointSnapshotV1 {
        if self.prepared.is_some() {
            CheckpointSnapshotV1::Prepared
        } else {
            CheckpointSnapshotV1::Committed(KernelHeadV1 {
                database_identity_sha256: self.database_identity_sha256,
                schema_catalog_sha256: self.schema_catalog_sha256,
                business_content_root_sha256: self.business_content_root_sha256,
                generation: self.generation,
                checkpoint_head_sha256: self.checkpoint_head_sha256,
            })
        }
    }

    fn provider_identity_sha256(&self) -> [u8; 32] {
        self.checkpoint_provider_identity_sha256
    }

    fn independent_failure_domain_proved(&self) -> bool {
        false
    }

    fn prepare(
        &mut self,
        expected: &KernelHeadV1,
        intent_sha256: [u8; 32],
        next_business_content_root_sha256: [u8; 32],
    ) -> AuthorizationResult<PreparedCheckpointV1> {
        if self.prepared.is_some()
            || self.database_identity_sha256 != expected.database_identity_sha256
            || self.schema_catalog_sha256 != expected.schema_catalog_sha256
            || self.business_content_root_sha256 != expected.business_content_root_sha256
            || self.generation != expected.generation
            || self.checkpoint_head_sha256 != expected.checkpoint_head_sha256
            || next_business_content_root_sha256 == self.business_content_root_sha256
            || !nonzero(&next_business_content_root_sha256)
        {
            return Err(sqlite_error(
                "s20_checkpoint",
                "checkpoint prepare CAS failed",
            ));
        }
        let generation = self
            .generation
            .checked_add(1)
            .ok_or_else(|| sqlite_error("s20_checkpoint", "checkpoint generation overflow"))?;
        let checkpoint_head_sha256 = checkpoint_transition_digest(
            &self.checkpoint_head_sha256,
            generation,
            &intent_sha256,
            &next_business_content_root_sha256,
        )?;
        let prepared = PreparedCheckpointV1 {
            database_identity_sha256: self.database_identity_sha256,
            schema_catalog_sha256: self.schema_catalog_sha256,
            business_content_root_sha256: next_business_content_root_sha256,
            generation,
            checkpoint_head_sha256,
        };
        self.prepared = Some((
            prepared.database_identity_sha256,
            prepared.schema_catalog_sha256,
            prepared.business_content_root_sha256,
            prepared.generation,
            prepared.checkpoint_head_sha256,
        ));
        Ok(prepared)
    }

    fn commit(&mut self, prepared: PreparedCheckpointV1) -> AuthorizationResult<()> {
        let prepared_matches = self.prepared.as_ref().is_some_and(
            |(
                database_identity_sha256,
                schema_catalog_sha256,
                business_content_root_sha256,
                generation,
                checkpoint_head_sha256,
            )| {
                *database_identity_sha256 == prepared.database_identity_sha256
                    && *schema_catalog_sha256 == prepared.schema_catalog_sha256
                    && *business_content_root_sha256 == prepared.business_content_root_sha256
                    && *generation == prepared.generation
                    && *checkpoint_head_sha256 == prepared.checkpoint_head_sha256
            },
        );
        if !prepared_matches
            || prepared.database_identity_sha256 != self.database_identity_sha256
            || prepared.schema_catalog_sha256 != self.schema_catalog_sha256
            || prepared.business_content_root_sha256 == self.business_content_root_sha256
            || prepared.generation != self.generation + 1
        {
            return Err(sqlite_error(
                "s20_checkpoint",
                "checkpoint commit is not prepared",
            ));
        }
        if self.fail_commit_once {
            self.fail_commit_once = false;
            return Err(sqlite_error(
                "s20_checkpoint",
                "synthetic checkpoint commit acknowledgement is unknown",
            ));
        }
        self.business_content_root_sha256 = prepared.business_content_root_sha256;
        self.generation = prepared.generation;
        self.checkpoint_head_sha256 = prepared.checkpoint_head_sha256;
        self.prepared = None;
        Ok(())
    }
}

#[cfg(test)]
fn initialize_synthetic_authority_ledger_v1(
    path: &Path,
    authorized: &AuthorizedUnclaimedS19SubjectV1,
    database_identity_sha256: [u8; 32],
) -> AuthorizationResult<(Connection, SyntheticCheckpointPortImplV1)> {
    use std::os::unix::fs::OpenOptionsExt as _;

    std::fs::OpenOptions::new()
        .write(true)
        .create_new(true)
        .mode(0o600)
        .open(path)
        .and_then(|file| file.sync_all())
        .map_err(|_| sqlite_error("s20_setup", "cannot create-new synthetic ledger"))?;
    let mut connection = open_ledger_file_without_create(path)?;
    connection
        .execute_batch(
            "PRAGMA journal_mode=DELETE;
             PRAGMA synchronous=EXTRA;
             PRAGMA temp_store=FILE;
             PRAGMA mmap_size=0;
             PRAGMA cache_size=-2048;
             PRAGMA foreign_keys=ON;
             PRAGMA trusted_schema=OFF;
             PRAGMA application_id=1094865690;
             PRAGMA user_version=20;",
        )
        .map_err(|_| sqlite_error("s20_setup", "cannot apply setup profile"))?;
    connection
        .execute_batch(S20_SCHEMA_SQL)
        .map_err(|_| sqlite_error("s20_setup", "cannot create synthetic authority schema"))?;
    let schema_catalog_sha256 = sqlite_schema_catalog_digest_v1(&connection)?;
    let transaction = connection
        .transaction_with_behavior(rusqlite::TransactionBehavior::Immediate)
        .map_err(|_| sqlite_error("s20_setup", "cannot begin authority registration"))?;
    let control_changed = transaction
        .execute(
            "INSERT INTO authority_control(
               singleton,control_ledger_identity_sha256,anti_rollback_policy_sha256,
               stop_state,stop_revision,current_revocation_epoch,revocation_revision,
               stop_policy_identity_sha256,revocation_policy_identity_sha256,
               sqlite_profile_sha256,sqlite_schema_sha256)
             VALUES(1,?1,?2,'CLEAR',1,?3,1,?4,?5,?6,?7)",
            params![
                &authorized.subject.control_ledger_identity_sha256[..],
                &authorized.subject.anti_rollback_policy_sha256[..],
                to_sql_integer(authorized.authorization.revocation_epoch)?,
                &authorized.subject.stop_control_policy_sha256[..],
                &authorized.revocation_policy_sha256[..],
                &authorized.subject.sqlite_profile_sha256[..],
                &authorized.subject.sqlite_schema_sha256[..]
            ],
        )
        .map_err(|_| sqlite_error("s20_setup", "cannot register authority controls"))?;
    if control_changed != 1 {
        return Err(sqlite_error(
            "s20_setup",
            "authority control registration was not singular",
        ));
    }
    let claim_changed = transaction
        .execute(
            "INSERT INTO claim_ledger(
               authorization_id_sha256,claim_namespace_sha256,claim_key_sha256,
               signed_payload_sha256,subject_manifest_sha256,resource_scope_sha256,
               signed_revocation_epoch,state,revision,successful_claim_count,run_id_sha256,
               controller_binary_sha256,runner_binary_sha256,capability_nonce_sha256,
               preflight_receipt_sha256,control_snapshot_sha256,claim_receipt_sha256)
             VALUES(?1,?2,?3,?4,?5,?6,?7,'AUTHORIZED_UNCLAIMED',?8,0,NULL,NULL,?9,?10,
                    NULL,NULL,NULL)",
            params![
                &authorized.authorization.authorization_id_sha256[..],
                &authorized.subject.claim_namespace_sha256[..],
                &authorized.subject.claim_key_sha256[..],
                &authorized.authorization.payload_sha256[..],
                &authorized.subject.canonical_manifest_sha256[..],
                &authorized.subject.resource_scope_sha256[..],
                to_sql_integer(authorized.authorization.revocation_epoch)?,
                to_sql_integer(authorized.subject.expected_unclaimed_revision)?,
                &authorized.subject.runner_binary_sha256[..],
                &authorized.capability_nonce_sha256[..],
            ],
        )
        .map_err(|_| sqlite_error("s20_setup", "cannot register unclaimed claim row"))?;
    if claim_changed != 1 {
        return Err(sqlite_error(
            "s20_setup",
            "unclaimed claim registration was not singular",
        ));
    }
    let attempt_changed = transaction
        .execute(
            "INSERT INTO orchestration_attempt(
               authorization_id_sha256,claim_namespace_sha256,claim_key_sha256,
               owner_envelope_sha256,trust_anchor_document_sha256,owner_identity_sha256,
               owner_key_version,signed_payload_sha256,subject_manifest_sha256,
               resource_scope_sha256,state,revision,run_id_sha256,run_assignment_id_sha256,
               challenge_nonce_sha256,controller_binary_sha256,controller_start_token_sha256,boot_id_sha256,
               preflight_receipt_sha256,claim_receipt_sha256,terminal_receipt_sha256)
             VALUES(?1,?2,?3,?4,?5,?6,?7,?8,?9,?10,'REGISTERED_UNUSED',1,
                    NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL)",
            params![
                &authorized.authorization.authorization_id_sha256[..],
                &authorized.subject.claim_namespace_sha256[..],
                &authorized.subject.claim_key_sha256[..],
                &authorized.authorization.owner_envelope_sha256[..],
                &authorized.authorization.trust_anchor_document_sha256[..],
                &authorized.authorization.owner_identity_sha256[..],
                to_sql_integer(authorized.authorization.owner_key_version)?,
                &authorized.authorization.payload_sha256[..],
                &authorized.subject.canonical_manifest_sha256[..],
                &authorized.subject.resource_scope_sha256[..],
            ],
        )
        .map_err(|_| sqlite_error("s20_setup", "cannot preregister exact attempt eligibility"))?;
    if attempt_changed != 1 {
        return Err(sqlite_error(
            "s20_setup",
            "attempt eligibility preregistration was not singular",
        ));
    }
    let business_content_root_sha256 = sqlite_business_content_root_for_head_v1(
        &transaction,
        &database_identity_sha256,
        &schema_catalog_sha256,
        1,
    )?;
    let checkpoint_head_sha256 = checkpoint_initial_digest(
        &database_identity_sha256,
        &schema_catalog_sha256,
        &business_content_root_sha256,
    )?;
    let checkpoint_provider_identity_sha256 = framed_digest(
        S20_SYNTHETIC_CHECKPOINT_PROVIDER_DOMAIN,
        &[&database_identity_sha256, &schema_catalog_sha256],
    )?;
    let meta_changed = transaction
        .execute(
            "INSERT INTO kernel_meta(singleton,database_identity_sha256,schema_catalog_sha256,
                                     business_content_root_sha256,generation,
                                     checkpoint_head_sha256)
             VALUES(1,?1,?2,?3,1,?4)",
            params![
                &database_identity_sha256[..],
                &schema_catalog_sha256[..],
                &business_content_root_sha256[..],
                &checkpoint_head_sha256[..],
            ],
        )
        .map_err(|_| sqlite_error("s20_setup", "cannot register kernel metadata"))?;
    if meta_changed != 1 {
        return Err(sqlite_error(
            "s20_setup",
            "kernel metadata registration was not singular",
        ));
    }
    transaction
        .commit()
        .map_err(|_| sqlite_error("s20_setup", "authority registration commit unknown"))?;
    Ok((
        connection,
        SyntheticCheckpointPortImplV1 {
            database_identity_sha256,
            schema_catalog_sha256,
            business_content_root_sha256,
            generation: 1,
            checkpoint_head_sha256,
            checkpoint_provider_identity_sha256,
            prepared: None,
            fail_commit_once: false,
        },
    ))
}

#[cfg(test)]
fn open_existing_s20_ledger_v1<P: SyntheticCheckpointPortV1>(
    path: &Path,
    port: &P,
) -> AuthorizationResult<Connection> {
    let connection = open_ledger_file_without_create(path)?;
    apply_s20_profile(&connection)?;
    if pragma_i64(&connection, "PRAGMA application_id")? != S20_APPLICATION_ID
        || pragma_i64(&connection, "PRAGMA user_version")? != S20_USER_VERSION
        || !pragma_text(&connection, "PRAGMA journal_mode")?.eq_ignore_ascii_case("delete")
        || pragma_text(&connection, "PRAGMA quick_check(1)")? != "ok"
    {
        return Err(sqlite_error(
            "s20_open",
            "ledger identity or integrity drifted",
        ));
    }
    verify_committed_checkpoint(&connection, port)?;
    let cardinalities = connection
        .query_row(
            "SELECT (SELECT count(*) FROM kernel_meta),
                    (SELECT count(*) FROM authority_control),
                    (SELECT count(*) FROM claim_ledger),
                    (SELECT count(*) FROM orchestration_attempt)",
            [],
            |row| {
                Ok((
                    row.get::<_, i64>(0)?,
                    row.get::<_, i64>(1)?,
                    row.get::<_, i64>(2)?,
                    row.get::<_, i64>(3)?,
                ))
            },
        )
        .map_err(|_| sqlite_error("s20_open", "cannot verify exact ledger cardinalities"))?;
    if cardinalities != (1, 1, 1, 1) {
        return Err(sqlite_error(
            "s20_open",
            "ledger singleton or exact authorization cardinality drifted",
        ));
    }
    let incomplete_attempt_count = connection
        .query_row(
            "SELECT count(*) FROM orchestration_attempt
             WHERE state IN ('PREFLIGHT_RESERVED','PREFLIGHT_VALIDATED','CLAIM_ATTEMPT_RESERVED',
                             'CLAIM_CONSUMED','ACTION_START_LINEARIZED')",
            [],
            |row| row.get::<_, i64>(0),
        )
        .map_err(|_| sqlite_error("s20_open", "cannot inspect incomplete attempts"))?;
    let pending_action_count = connection
        .query_row(
            "SELECT count(*) FROM action_journal WHERE outcome='INTENT_DURABLE_SYNTHETIC'",
            [],
            |row| row.get::<_, i64>(0),
        )
        .map_err(|_| sqlite_error("s20_open", "cannot inspect pending action intents"))?;
    if incomplete_attempt_count != 0 || pending_action_count != 0 {
        return Err(sqlite_error(
            "s20_open",
            "incomplete prior-controller attempt or action intent is non-resumable",
        ));
    }
    Ok(connection)
}

#[cfg(test)]
fn authority_trigger_stop_v1<P: SyntheticCheckpointPortV1>(
    connection: &mut Connection,
    port: &mut P,
) -> AuthorizationResult<()> {
    let transaction = connection
        .transaction_with_behavior(rusqlite::TransactionBehavior::Immediate)
        .map_err(|_| sqlite_error("s20_stop", "cannot begin STOP transition"))?;
    let head = verify_committed_checkpoint(&transaction, port)?;
    let intent = framed_digest(
        S20_ACTION_DOMAIN,
        &[b"ABSORBING_STOP", &head.generation.to_be_bytes()],
    )?;
    let changed = transaction
        .execute(
            "UPDATE authority_control SET stop_state='TRIGGERED',stop_revision=stop_revision+1
             WHERE singleton=1 AND stop_state='CLEAR'",
            [],
        )
        .map_err(|_| sqlite_error("s20_stop", "STOP transition rejected"))?;
    if changed != 1 {
        return Err(sqlite_error(
            "s20_stop",
            "STOP transition was replayed or not singular",
        ));
    }
    let prepared = prepare_transition(&transaction, port, &head, intent)?;
    advance_meta(&transaction, &prepared)?;
    transaction
        .commit()
        .map_err(|_| sqlite_error("s20_stop", "STOP commit unknown"))?;
    port.commit(prepared)
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;
    use std::path::PathBuf;
    use std::sync::atomic::{AtomicU64, Ordering};

    static NEXT_PATH: AtomicU64 = AtomicU64::new(1);

    fn repeated(byte: u8) -> [u8; 32] {
        [byte; 32]
    }

    fn authorized_fixture() -> AuthorizedUnclaimedS19SubjectV1 {
        AuthorizedUnclaimedS19SubjectV1 {
            authorization: VerifiedUnclaimedOwnedLabAuthorizationV1 {
                authorization_id_sha256: repeated(0x01),
                payload_sha256: repeated(0x02),
                owner_envelope_sha256: repeated(0x03),
                trust_anchor_document_sha256: repeated(0x04),
                owner_identity_sha256: repeated(0x05),
                owner_key_id: "owner-key-v1".into(),
                owner_key_version: 7,
                revocation_epoch: 11,
            },
            subject: VerifiedS19SubjectV1 {
                canonical_manifest_sha256: repeated(0x10),
                schema_sha256: repeated(0x11),
                source_commit: [0x12; 20],
                integration_commit: [0x13; 20],
                controller_binary_sha256: repeated(0x14),
                runner_binary_sha256: repeated(0x15),
                preflight_observer_binary_sha256: repeated(0x16),
                boot_id_sha256: repeated(0x17),
                root_parent_identity_sha256: repeated(0x18),
                resource_scope_sha256: repeated(0x19),
                control_ledger_identity_sha256: repeated(0x1a),
                anti_rollback_policy_sha256: repeated(0x1b),
                stop_control_policy_sha256: repeated(0x1c),
                sqlite_profile_sha256: repeated(0x1d),
                sqlite_schema_sha256: repeated(0x1e),
                claim_namespace_sha256: repeated(0x1f),
                claim_key_sha256: repeated(0x20),
                expected_unclaimed_revision: 41,
                assignment_set_sha256: repeated(0x21),
                schedule_sha256: repeated(0x22),
                catalog_row_count: 5_639,
                catalog_sha256: [0x28; 32],
                classifier_binary_sha256: repeated(0x23),
                classifier_source_sha256: repeated(0x24),
                expected_oracle_sha256: repeated(0x25),
                s17_observation_schema_sha256: repeated(0x26),
                s17_plan_sha256: repeated(0x27),
                target_phase_count: 113,
                target_phase_unique_match_count: 113,
                allowed_operation_ids: vec![
                    "CREATE_EXACT_RUN_ROOT".into(),
                    "SQLITE_EXACT_PROFILE_SETUP".into(),
                    "SPAWN_ONE_ASSIGNED_CHILD".into(),
                    "PIDFD_OPEN_ASSIGNED_CHILD".into(),
                    "PIDFD_SEND_SIGNAL_SIGKILL".into(),
                    "FRESH_EXEC_REOPEN".into(),
                    "WRITE_BOUND_RECEIPTS".into(),
                    "CLEANUP_EXACT_RUN_ROOT".into(),
                ],
            },
            capability_nonce_sha256: repeated(0x21),
            revocation_policy_sha256: repeated(0x22),
        }
    }

    fn unique_path(label: &str) -> PathBuf {
        let scratch = std::env::var_os("AB_S20_TEST_SCRATCH")
            .map(PathBuf::from)
            .expect("AB_S20_TEST_SCRATCH must be injected by the S20 gate");
        std::fs::create_dir_all(&scratch).expect("create injected S20 scratch directory");
        scratch.join(format!(
            "ab-s20-{label}-{}.sqlite",
            NEXT_PATH.fetch_add(1, Ordering::Relaxed)
        ))
    }

    struct LedgerFixture {
        path: PathBuf,
        connection: Option<Connection>,
        port: SyntheticCheckpointPortImplV1,
        authorized: AuthorizedUnclaimedS19SubjectV1,
    }

    impl LedgerFixture {
        fn new(label: &str) -> Self {
            let path = unique_path(label);
            let authorized = authorized_fixture();
            let (connection, port) =
                initialize_synthetic_authority_ledger_v1(&path, &authorized, repeated(0x90))
                    .expect("synthetic authority registration");
            Self {
                path,
                connection: Some(connection),
                port,
                authorized,
            }
        }

        fn connection(&mut self) -> &mut Connection {
            self.connection.as_mut().expect("open fixture connection")
        }
    }

    impl Drop for LedgerFixture {
        fn drop(&mut self) {
            self.connection.take();
            let _ = std::fs::remove_file(&self.path);
        }
    }

    fn reservation(byte: u8) -> PreflightReservationRequestV1 {
        let run_id_sha256 = repeated(byte);
        PreflightReservationRequestV1 {
            run_id_sha256,
            run_assignment_id_sha256: synthetic_manifest_run_binding_v1(
                &authorized_fixture(),
                &run_id_sha256,
            )
            .unwrap(),
            challenge_nonce_sha256: repeated(byte.wrapping_add(1)),
            controller_binary_sha256: repeated(0x14),
            controller_start_token_sha256: repeated(byte.wrapping_add(2)),
            boot_id_sha256: repeated(0x17),
        }
    }

    fn measured() -> SyntheticMeasuredPreflightV1 {
        SyntheticMeasuredPreflightV1 {
            runner_binary_sha256: repeated(0x15),
            observer_binary_sha256: repeated(0x16),
            root_parent_identity_sha256: repeated(0x18),
            side_effect_count: 0,
        }
    }

    fn claim_success(fixture: &mut LedgerFixture) -> ClaimedRunPermitS20V1 {
        let reserved = {
            let (connection, port, authorized) = (
                fixture.connection.as_mut().unwrap(),
                &mut fixture.port,
                &fixture.authorized,
            );
            reserve_preflight_once_v1(connection, port, authorized, reservation(0x30)).unwrap()
        };
        let validated = {
            let (connection, port, authorized) = (
                fixture.connection.as_mut().unwrap(),
                &mut fixture.port,
                &fixture.authorized,
            );
            validate_preflight_once_v1(connection, port, authorized, reserved, measured()).unwrap()
        };
        let burned = {
            let (connection, port, authorized) = (
                fixture.connection.as_mut().unwrap(),
                &mut fixture.port,
                &fixture.authorized,
            );
            burn_claim_attempt_once_v1(connection, port, authorized, validated).unwrap()
        };
        match {
            let (connection, port, authorized) = (
                fixture.connection.as_mut().unwrap(),
                &mut fixture.port,
                &fixture.authorized,
            );
            execute_burned_claim_once_v1(connection, port, authorized, burned).unwrap()
        } {
            ClaimOutcomeS20V1::Claimed(permit) => permit,
            ClaimOutcomeS20V1::FailedTerminal(_) => panic!("expected claimed permit"),
        }
    }

    #[test]
    fn s20_external_authority_preregistration_allows_only_one_preflight_reservation() {
        let mut fixture = LedgerFixture::new("reserve-once");
        let first = reservation(0x30);
        let mut arbitrary_assignment = first.clone();
        arbitrary_assignment.run_assignment_id_sha256 = repeated(0xa7);
        {
            let (connection, port, authorized) = (
                fixture.connection.as_mut().unwrap(),
                &mut fixture.port,
                &fixture.authorized,
            );
            assert!(
                reserve_preflight_once_v1(connection, port, authorized, arbitrary_assignment)
                    .is_err()
            );
        }
        {
            let (connection, port, authorized) = (
                fixture.connection.as_mut().unwrap(),
                &mut fixture.port,
                &fixture.authorized,
            );
            let _ = reserve_preflight_once_v1(connection, port, authorized, first).unwrap();
        }
        let second = reservation(0x40);
        let rejected = {
            let (connection, port, authorized) = (
                fixture.connection.as_mut().unwrap(),
                &mut fixture.port,
                &fixture.authorized,
            );
            reserve_preflight_once_v1(connection, port, authorized, second)
        };
        assert!(rejected.is_err());
        let count: i64 = fixture
            .connection()
            .query_row("SELECT count(*) FROM orchestration_attempt", [], |row| {
                row.get(0)
            })
            .unwrap();
        assert_eq!(count, 1);
    }

    #[test]
    fn s20_failed_preflight_is_absorbing_across_revalidation() {
        let mut fixture = LedgerFixture::new("preflight-terminal");
        let reserved = {
            let (connection, port, authorized) = (
                fixture.connection.as_mut().unwrap(),
                &mut fixture.port,
                &fixture.authorized,
            );
            reserve_preflight_once_v1(connection, port, authorized, reservation(0x30)).unwrap()
        };
        let mut invalid = measured();
        invalid.side_effect_count = 1;
        let result = {
            let (connection, port, authorized) = (
                fixture.connection.as_mut().unwrap(),
                &mut fixture.port,
                &fixture.authorized,
            );
            validate_preflight_once_v1(connection, port, authorized, reserved, invalid)
        };
        assert!(result.is_err());
        let state: String = fixture
            .connection()
            .query_row("SELECT state FROM orchestration_attempt", [], |row| {
                row.get(0)
            })
            .unwrap();
        assert_eq!(state, ATTEMPT_PREFLIGHT_FAILED);
        let again = {
            let (connection, port, authorized) = (
                fixture.connection.as_mut().unwrap(),
                &mut fixture.port,
                &fixture.authorized,
            );
            reserve_preflight_once_v1(connection, port, authorized, reservation(0x50))
        };
        assert!(again.is_err());
    }

    #[test]
    fn s20_failed_claim_leaves_s19_row_unclaimed_but_attempt_terminal_after_reopen() {
        let mut fixture = LedgerFixture::new("claim-terminal");
        let reserved = {
            let (connection, port, authorized) = (
                fixture.connection.as_mut().unwrap(),
                &mut fixture.port,
                &fixture.authorized,
            );
            reserve_preflight_once_v1(connection, port, authorized, reservation(0x30)).unwrap()
        };
        let validated = {
            let (connection, port, authorized) = (
                fixture.connection.as_mut().unwrap(),
                &mut fixture.port,
                &fixture.authorized,
            );
            validate_preflight_once_v1(connection, port, authorized, reserved, measured()).unwrap()
        };
        let burned = {
            let (connection, port, authorized) = (
                fixture.connection.as_mut().unwrap(),
                &mut fixture.port,
                &fixture.authorized,
            );
            burn_claim_attempt_once_v1(connection, port, authorized, validated).unwrap()
        };
        {
            let (connection, port) = (fixture.connection.as_mut().unwrap(), &mut fixture.port);
            authority_trigger_stop_v1(connection, port).unwrap();
        }
        let outcome = {
            let (connection, port, authorized) = (
                fixture.connection.as_mut().unwrap(),
                &mut fixture.port,
                &fixture.authorized,
            );
            execute_burned_claim_once_v1(connection, port, authorized, burned).unwrap()
        };
        assert!(matches!(outcome, ClaimOutcomeS20V1::FailedTerminal(_)));
        let rows: (String, String) = fixture
            .connection()
            .query_row(
                "SELECT c.state,a.state FROM claim_ledger c JOIN orchestration_attempt a
                   ON a.authorization_id_sha256=c.authorization_id_sha256",
                [],
                |row| Ok((row.get(0)?, row.get(1)?)),
            )
            .unwrap();
        assert_eq!(rows.0, CLAIM_UNCLAIMED);
        assert_eq!(rows.1, ATTEMPT_CLAIM_FAILED);
        fixture.connection.take();
        let mut reopened = open_existing_s20_ledger_v1(&fixture.path, &fixture.port).unwrap();
        assert!(reserve_preflight_once_v1(
            &mut reopened,
            &mut fixture.port,
            &fixture.authorized,
            reservation(0x60)
        )
        .is_err());
    }

    #[test]
    fn s20_full_claim_predicate_runner_drift_is_zero_row_and_terminal() {
        let mut fixture = LedgerFixture::new("claim-runner-binding-drift");
        let reserved = {
            let (connection, port, authorized) = (
                fixture.connection.as_mut().unwrap(),
                &mut fixture.port,
                &fixture.authorized,
            );
            reserve_preflight_once_v1(connection, port, authorized, reservation(0x30)).unwrap()
        };
        let validated = {
            let (connection, port, authorized) = (
                fixture.connection.as_mut().unwrap(),
                &mut fixture.port,
                &fixture.authorized,
            );
            validate_preflight_once_v1(connection, port, authorized, reserved, measured()).unwrap()
        };
        let burned = {
            let (connection, port, authorized) = (
                fixture.connection.as_mut().unwrap(),
                &mut fixture.port,
                &fixture.authorized,
            );
            burn_claim_attempt_once_v1(connection, port, authorized, validated).unwrap()
        };

        fixture.authorized.subject.runner_binary_sha256 = repeated(0xa5);
        let outcome = {
            let (connection, port, authorized) = (
                fixture.connection.as_mut().unwrap(),
                &mut fixture.port,
                &fixture.authorized,
            );
            execute_burned_claim_once_v1(connection, port, authorized, burned).unwrap()
        };
        assert!(matches!(outcome, ClaimOutcomeS20V1::FailedTerminal(_)));
        let rows: (String, i64, i64, String) = fixture
            .connection()
            .query_row(
                "SELECT c.state,c.successful_claim_count,c.revision,a.state
                   FROM claim_ledger c JOIN orchestration_attempt a
                     ON a.authorization_id_sha256=c.authorization_id_sha256",
                [],
                |row| Ok((row.get(0)?, row.get(1)?, row.get(2)?, row.get(3)?)),
            )
            .unwrap();
        assert_eq!(rows.0, CLAIM_UNCLAIMED);
        assert_eq!(rows.1, 0);
        assert_eq!(rows.2, 41);
        assert_eq!(rows.3, ATTEMPT_CLAIM_FAILED);
    }

    fn insert_uncheckpointed_action_rows(connection: &Connection, indices: &[u64]) {
        let authorization_id_sha256 = repeated(0xd1);
        let claim_namespace_sha256 = repeated(0xd2);
        let claim_key_sha256 = repeated(0xd3);
        let run_assignment_id_sha256 = repeated(0xd4);
        for index in indices {
            let mut operation_id_sha256 = repeated(0xd5);
            operation_id_sha256[0] = u8::try_from(*index).unwrap();
            let mut intent_sha256 = repeated(0xd6);
            intent_sha256[0] = u8::try_from(*index).unwrap();
            connection
                .execute(
                    "INSERT INTO action_journal(
                       authorization_id_sha256,claim_namespace_sha256,claim_key_sha256,
                       action_index,run_assignment_id_sha256,operation_id_sha256,
                       intent_sha256,outcome)
                     VALUES(?1,?2,?3,?4,?5,?6,?7,'STARTED_SYNTHETIC')",
                    params![
                        &authorization_id_sha256[..],
                        &claim_namespace_sha256[..],
                        &claim_key_sha256[..],
                        to_sql_integer(*index).unwrap(),
                        &run_assignment_id_sha256[..],
                        &operation_id_sha256[..],
                        &intent_sha256[..],
                    ],
                )
                .unwrap();
        }
    }

    #[test]
    fn s20_business_content_root_is_order_stable_and_type_framed() {
        let mut first = LedgerFixture::new("content-root-order-first");
        let mut second = LedgerFixture::new("content-root-order-second");
        insert_uncheckpointed_action_rows(first.connection(), &[1, 0]);
        insert_uncheckpointed_action_rows(second.connection(), &[0, 1]);
        let first_root = sqlite_business_content_root_v1(first.connection()).unwrap();
        let second_root = sqlite_business_content_root_v1(second.connection()).unwrap();
        assert_eq!(first_root, second_root);
        let head = read_kernel_head(first.connection()).unwrap();
        let mut other_database = head.database_identity_sha256;
        other_database[0] ^= 1;
        let mut other_schema = head.schema_catalog_sha256;
        other_schema[0] ^= 1;
        assert_ne!(
            first_root,
            sqlite_business_content_root_for_head_v1(
                first.connection(),
                &other_database,
                &head.schema_catalog_sha256,
                head.generation,
            )
            .unwrap()
        );
        assert_ne!(
            first_root,
            sqlite_business_content_root_for_head_v1(
                first.connection(),
                &head.database_identity_sha256,
                &other_schema,
                head.generation,
            )
            .unwrap()
        );
        assert_ne!(
            first_root,
            sqlite_business_content_root_for_head_v1(
                first.connection(),
                &head.database_identity_sha256,
                &head.schema_catalog_sha256,
                head.generation + 1,
            )
            .unwrap()
        );

        let integer_bytes = 1_i64.to_be_bytes();
        let mut integer_frame = Vec::new();
        append_business_value_frame_v1(&mut integer_frame, rusqlite::types::ValueRef::Integer(1))
            .unwrap();
        let mut blob_frame = Vec::new();
        append_business_value_frame_v1(
            &mut blob_frame,
            rusqlite::types::ValueRef::Blob(&integer_bytes),
        )
        .unwrap();
        let mut null_frame = Vec::new();
        append_business_value_frame_v1(&mut null_frame, rusqlite::types::ValueRef::Null).unwrap();
        let mut empty_blob_frame = Vec::new();
        append_business_value_frame_v1(&mut empty_blob_frame, rusqlite::types::ValueRef::Blob(&[]))
            .unwrap();
        assert_ne!(integer_frame, blob_frame);
        assert_ne!(null_frame, empty_blob_frame);
    }

    #[test]
    fn s20_business_content_root_tracks_meta_and_external_checkpoint() {
        let mut fixture = LedgerFixture::new("content-root-transition");
        let initial = read_kernel_head(fixture.connection()).unwrap();
        assert_eq!(
            hex(&initial.business_content_root_sha256),
            S20_INITIAL_BUSINESS_CONTENT_ROOT_SHA256_KAT
        );
        assert_eq!(
            initial.business_content_root_sha256,
            sqlite_business_content_root_v1(fixture.connection()).unwrap()
        );
        assert_eq!(
            initial.business_content_root_sha256,
            fixture.port.business_content_root_sha256
        );
        let evidence = validate_committed_database_state_v1(
            fixture.connection.as_ref().unwrap(),
            &fixture.port,
        )
        .unwrap();
        assert_eq!(
            evidence.checkpoint_provider_identity_sha256,
            fixture.port.checkpoint_provider_identity_sha256
        );
        assert!(!evidence.independent_failure_domain_proved);
        let before = initial.business_content_root_sha256;
        {
            let (connection, port, authorized) = (
                fixture.connection.as_mut().unwrap(),
                &mut fixture.port,
                &fixture.authorized,
            );
            let _ =
                reserve_preflight_once_v1(connection, port, authorized, reservation(0x30)).unwrap();
        }
        let committed =
            verify_committed_checkpoint(fixture.connection.as_ref().unwrap(), &fixture.port)
                .unwrap();
        assert_ne!(committed.business_content_root_sha256, before);
        assert_eq!(
            committed.business_content_root_sha256,
            fixture.port.business_content_root_sha256
        );
    }

    #[test]
    fn s20_committed_state_rejects_same_connection_identity_and_journal_drift() {
        let mut application_id = LedgerFixture::new("same-connection-application-id-drift");
        application_id
            .connection()
            .execute_batch("PRAGMA application_id=1094865691;")
            .unwrap();
        assert!(validate_committed_database_state_v1(
            application_id.connection.as_ref().unwrap(),
            &application_id.port,
        )
        .is_err());

        let mut user_version = LedgerFixture::new("same-connection-user-version-drift");
        user_version
            .connection()
            .execute_batch("PRAGMA user_version=21;")
            .unwrap();
        assert!(validate_committed_database_state_v1(
            user_version.connection.as_ref().unwrap(),
            &user_version.port,
        )
        .is_err());

        let mut journal_mode = LedgerFixture::new("same-connection-journal-mode-drift");
        assert_eq!(
            pragma_text(journal_mode.connection(), "PRAGMA journal_mode=MEMORY").unwrap(),
            "memory"
        );
        assert!(validate_committed_database_state_v1(
            journal_mode.connection.as_ref().unwrap(),
            &journal_mode.port,
        )
        .is_err());
    }

    #[test]
    fn s20_business_content_root_reopen_rejects_insert_update_and_delete_tamper() {
        let mut inserted = LedgerFixture::new("content-root-insert-tamper");
        insert_uncheckpointed_action_rows(inserted.connection(), &[0]);
        inserted.connection.take();
        assert!(open_existing_s20_ledger_v1(&inserted.path, &inserted.port).is_err());

        let mut updated = LedgerFixture::new("content-root-update-tamper");
        let changed = updated
            .connection()
            .execute(
                "UPDATE authority_control
                 SET stop_state='TRIGGERED',stop_revision=stop_revision+1
                 WHERE singleton=1 AND stop_state='CLEAR'",
                [],
            )
            .unwrap();
        assert_eq!(changed, 1);
        updated.connection.take();
        assert!(open_existing_s20_ledger_v1(&updated.path, &updated.port).is_err());

        let mut deleted = LedgerFixture::new("content-root-delete-tamper");
        let schema_before = sqlite_schema_catalog_digest_v1(deleted.connection()).unwrap();
        let delete_guard_sql: String = deleted
            .connection()
            .query_row(
                "SELECT sql FROM sqlite_schema
                 WHERE type='trigger' AND name='claim_ledger_delete_guard'",
                [],
                |row| row.get(0),
            )
            .unwrap();
        deleted
            .connection()
            .execute_batch("DROP TRIGGER claim_ledger_delete_guard")
            .unwrap();
        assert_eq!(
            deleted
                .connection()
                .execute("DELETE FROM claim_ledger", [])
                .unwrap(),
            1
        );
        deleted
            .connection()
            .execute_batch(&delete_guard_sql)
            .unwrap();
        assert_eq!(
            sqlite_schema_catalog_digest_v1(deleted.connection()).unwrap(),
            schema_before,
            "delete-tamper KAT must restore the exact schema so only business-row loss is detected"
        );
        deleted.connection.take();
        assert!(open_existing_s20_ledger_v1(&deleted.path, &deleted.port).is_err());
    }

    #[test]
    fn s20_checkpoint_prepared_fork_and_old_file_replacement_fail_closed() {
        let mut fixture = LedgerFixture::new("checkpoint");
        let old = unique_path("checkpoint-old");
        fixture.connection.take();
        std::fs::copy(&fixture.path, &old).unwrap();
        fixture.connection =
            Some(open_existing_s20_ledger_v1(&fixture.path, &fixture.port).unwrap());
        {
            let (connection, port, authorized) = (
                fixture.connection.as_mut().unwrap(),
                &mut fixture.port,
                &fixture.authorized,
            );
            let _ =
                reserve_preflight_once_v1(connection, port, authorized, reservation(0x30)).unwrap();
        }
        fixture.connection.take();
        std::fs::copy(&old, &fixture.path).unwrap();
        assert!(open_existing_s20_ledger_v1(&fixture.path, &fixture.port).is_err());
        let _ = std::fs::remove_file(old);

        let mut prepared = LedgerFixture::new("checkpoint-prepared");
        prepared.connection.take();
        prepared.port.prepared = Some((
            prepared.port.database_identity_sha256,
            prepared.port.schema_catalog_sha256,
            repeated(0xb9),
            prepared.port.generation + 1,
            repeated(0xba),
        ));
        assert!(open_existing_s20_ledger_v1(&prepared.path, &prepared.port).is_err());

        let mut forked = LedgerFixture::new("checkpoint-forked");
        forked.connection.take();
        forked.port.checkpoint_head_sha256[0] ^= 1;
        assert!(open_existing_s20_ledger_v1(&forked.path, &forked.port).is_err());

        let mut content_forked = LedgerFixture::new("checkpoint-content-root-forked");
        content_forked.connection.take();
        content_forked.port.business_content_root_sha256[0] ^= 1;
        assert!(open_existing_s20_ledger_v1(&content_forked.path, &content_forked.port).is_err());

        let mut swapped = LedgerFixture::new("checkpoint-swapped-token");
        let expected = read_kernel_head(swapped.connection.as_ref().unwrap()).unwrap();
        let authentic = swapped
            .port
            .prepare(&expected, repeated(0xc1), repeated(0xc2))
            .unwrap();
        let mut fabricated_root = authentic.business_content_root_sha256;
        fabricated_root[0] ^= 1;
        assert!(swapped
            .port
            .commit(PreparedCheckpointV1 {
                database_identity_sha256: authentic.database_identity_sha256,
                schema_catalog_sha256: authentic.schema_catalog_sha256,
                business_content_root_sha256: fabricated_root,
                generation: authentic.generation,
                checkpoint_head_sha256: authentic.checkpoint_head_sha256,
            })
            .is_err());
        assert!(swapped.port.prepared.is_some());
    }

    #[test]
    fn s20_unknown_checkpoint_commit_absorbs_without_returning_a_token() {
        let mut fixture = LedgerFixture::new("checkpoint-unknown");
        fixture.port.fail_commit_once = true;
        let result = {
            let (connection, port, authorized) = (
                fixture.connection.as_mut().unwrap(),
                &mut fixture.port,
                &fixture.authorized,
            );
            reserve_preflight_once_v1(connection, port, authorized, reservation(0x30))
        };
        assert!(result.is_err());
        assert!(fixture.port.prepared.is_some());
        let state: String = fixture
            .connection()
            .query_row("SELECT state FROM orchestration_attempt", [], |row| {
                row.get(0)
            })
            .unwrap();
        assert_eq!(state, ATTEMPT_PREFLIGHT_RESERVED);
        fixture.connection.take();
        assert!(open_existing_s20_ledger_v1(&fixture.path, &fixture.port).is_err());
    }

    #[test]
    fn s20_attempt_trigger_rejects_stage_binding_drift_and_delete() {
        let mut fixture = LedgerFixture::new("attempt-trigger");
        {
            let (connection, port, authorized) = (
                fixture.connection.as_mut().unwrap(),
                &mut fixture.port,
                &fixture.authorized,
            );
            let _ =
                reserve_preflight_once_v1(connection, port, authorized, reservation(0x30)).unwrap();
        }
        assert!(fixture
            .connection()
            .execute(
                "UPDATE orchestration_attempt SET state='PREFLIGHT_VALIDATED',revision=revision+1",
                [],
            )
            .is_err());
        assert!(fixture
            .connection()
            .execute(
                "UPDATE orchestration_attempt SET state='PREFLIGHT_VALIDATED',revision=revision+1,
                        run_id_sha256=?1,preflight_receipt_sha256=?2",
                params![&repeated(0xee)[..], &repeated(0xef)[..]],
            )
            .is_err());
        assert!(fixture
            .connection()
            .execute("DELETE FROM orchestration_attempt", [])
            .is_err());
    }

    struct CountingStarter {
        calls: u64,
        result: bool,
    }

    impl starter_seal::Sealed for CountingStarter {}

    impl SyntheticActionStarterV1 for CountingStarter {
        fn start_once(&mut self, _action_index: u64, _intent_sha256: [u8; 32]) -> bool {
            self.calls += 1;
            self.result
        }
    }

    #[test]
    fn s20_stop_and_action_start_have_one_writer_order_and_no_after_guard() {
        let mut stop_first = LedgerFixture::new("stop-first");
        let permit = claim_success(&mut stop_first);
        {
            let (connection, port) = (
                stop_first.connection.as_mut().unwrap(),
                &mut stop_first.port,
            );
            authority_trigger_stop_v1(connection, port).unwrap();
        }
        let mut starter = CountingStarter {
            calls: 0,
            result: true,
        };
        let denied = {
            let (connection, port, authorized) = (
                stop_first.connection.as_mut().unwrap(),
                &mut stop_first.port,
                &stop_first.authorized,
            );
            linearize_synthetic_action_start_v1(
                connection,
                port,
                authorized,
                permit,
                0,
                &mut starter,
            )
        };
        assert!(denied.is_err());
        assert_eq!(starter.calls, 0);

        let mut action_first = LedgerFixture::new("action-first");
        let mut permit = claim_success(&mut action_first);
        let mut starter = CountingStarter {
            calls: 0,
            result: true,
        };
        {
            let (connection, port, authorized) = (
                action_first.connection.as_mut().unwrap(),
                &mut action_first.port,
                &action_first.authorized,
            );
            permit = linearize_synthetic_action_start_v1(
                connection,
                port,
                authorized,
                permit,
                0,
                &mut starter,
            )
            .unwrap()
            .0;
        }
        assert_eq!(starter.calls, 1);
        {
            let (connection, port) = (
                action_first.connection.as_mut().unwrap(),
                &mut action_first.port,
            );
            authority_trigger_stop_v1(connection, port).unwrap();
        }
        let denied = {
            let (connection, port, authorized) = (
                action_first.connection.as_mut().unwrap(),
                &mut action_first.port,
                &action_first.authorized,
            );
            linearize_synthetic_action_start_v1(
                connection,
                port,
                authorized,
                permit,
                1,
                &mut starter,
            )
        };
        assert!(denied.is_err());
        assert_eq!(starter.calls, 1);
    }

    #[test]
    fn s20_stop_replay_zero_row_is_rejected() {
        let mut fixture = LedgerFixture::new("stop-zero-row");
        {
            let (connection, port) = (fixture.connection.as_mut().unwrap(), &mut fixture.port);
            authority_trigger_stop_v1(connection, port).unwrap();
        }
        let replay = {
            let (connection, port) = (fixture.connection.as_mut().unwrap(), &mut fixture.port);
            authority_trigger_stop_v1(connection, port)
        };
        assert!(replay.is_err());
        assert!(fixture.port.prepared.is_none());
        let control: (String, i64) = fixture
            .connection()
            .query_row(
                "SELECT stop_state,stop_revision FROM authority_control WHERE singleton=1",
                [],
                |row| Ok((row.get(0)?, row.get(1)?)),
            )
            .unwrap();
        assert_eq!(control.0, "TRIGGERED");
        assert_eq!(control.1, 2);
    }

    #[test]
    fn s20_zero_based_action_index_projects_to_one_based_receipt_sequence() {
        assert_eq!(action_sequence_from_zero_based_index_v1(0).unwrap(), 1);
        assert_eq!(action_sequence_from_zero_based_index_v1(59).unwrap(), 60);
        assert!(action_sequence_from_zero_based_index_v1(60).is_err());
    }

    #[test]
    fn s20_partial_rich_projection_rejects_canonical_and_cross_binding_drift() {
        let authorized = authorized_fixture();
        let domain = b"agent-bridge/biocortex/owned-lab/s20/rich-preflight-kat/v1";
        let value = json!({
            "authorization_binding": {
                "authorization_id_sha256": hex(&authorized.authorization.authorization_id_sha256),
                "owner_envelope_sha256": hex(&authorized.authorization.owner_envelope_sha256),
                "signed_payload_sha256": hex(&authorized.authorization.payload_sha256),
                "subject_manifest_sha256": hex(&authorized.subject.canonical_manifest_sha256)
            },
            "canonicalization": S19_CANONICAL_PROFILE,
            "nonclaims": {"execution_start_permitted": false, "side_effects_unlocked": "NONE"},
            "packet_kind": "S19_OWNED_LAB_FRESH_PREFLIGHT_RECEIPT",
            "preflight_receipt_sha256": repeated(0xff).iter().map(|b| format!("{b:02x}")).collect::<String>(),
            "schema": "agent_bridge.memory_temporal_owned_lab_preflight_receipt_s19.v0"
        });
        let sealed = seal_rich_value_v1(value.clone(), "preflight_receipt_sha256", domain).unwrap();
        let raw = restricted_canonical_bytes(&sealed).unwrap();
        assert_eq!(
            validate_partial_rich_security_projection_v1(
                &raw,
                PartialExpectedRichSecurityProjectionV1 {
                    kind: PartialRichSecurityProjectionKindV1::PreflightProjection,
                    exact_value: value.clone(),
                    self_digest_key: "preflight_receipt_sha256",
                    digest_domain: domain,
                }
            )
            .unwrap(),
            PartialRichSecurityProjectionKindV1::PreflightProjection
        );
        let mut mutated = sealed;
        mutated["authorization_binding"]["authorization_id_sha256"] =
            Value::String(hex(&repeated(0xee)));
        let mutated_raw = restricted_canonical_bytes(&mutated).unwrap();
        assert!(validate_partial_rich_security_projection_v1(
            &mutated_raw,
            PartialExpectedRichSecurityProjectionV1 {
                kind: PartialRichSecurityProjectionKindV1::PreflightProjection,
                exact_value: value,
                self_digest_key: "preflight_receipt_sha256",
                digest_domain: domain,
            }
        )
        .is_err());
        assert_eq!(
            S20_RICH_PACKET_STATUS,
            "PARTIAL_PREFLIGHT_SECURITY_PROJECTION_ONLY_FOUR_FROZEN_RICH_SCHEMAS_NOT_IMPLEMENTED"
        );
    }

    #[test]
    fn s20_no_live_effect_or_authority_counts_exist() {
        assert!(S20_RICH_PACKET_STATUS.contains("NOT_IMPLEMENTED"));
        assert!(!S20_FOUR_RICH_SCHEMAS_FULLY_IMPLEMENTED);
        assert!(!S20_REAL_INDEPENDENT_CHECKPOINT_ADAPTER_PRESENT);
        assert!(!S20_LIVE_ACTION_ADAPTER_PRESENT);
        assert!(!S20_NEW_KERNEL_OWNER_REVIEW_BINDING_PRESENT);
        assert!(!S20_EXACT_ASSIGNMENT_MEMBERSHIP_VALIDATOR_IMPLEMENTED);
        assert!(!S20_FULL_DATABASE_CONTENT_AUTHENTICATION_IMPLEMENTED);
        assert!(!S20_REAL_PARENT_DIRECTORY_DURABILITY_ADAPTER_PRESENT);
        assert!(!S20_RICH_POSTRUN_RECEIPT_IMPLEMENTED);
        assert_eq!(S20_APPLICATION_ID, 1_094_865_690);
        assert_eq!(S20_USER_VERSION, 20);
    }

    #[test]
    fn s20_exact_canary_index_distinguishes_synthetic_zero_and_complete_exact() {
        let mut accounting = ExactCanaryAccountingV1 {
            ol00_count: 1,
            ol04_count: 6,
            ol05_count: 53,
            assigned_attempt_count: 60,
            planned_pidfd_sigkill_count: 59,
            planned_fresh_exec_read_count: 59,
            planned_s16_mapping_phase_count: 113,
            actual_assigned_attempt_count: 0,
            actual_observation_count: 0,
            assigned_action_start_receipt_count: 0,
            actual_pidfd_sigkill_count: 0,
            actual_fresh_exec_read_count: 0,
            actual_s16_mapping_phase_count: 0,
            successful_claim_count: 0,
            retry_count: 0,
        };
        validate_exact_canary_accounting_v1(CanaryAccountingModeV1::SyntheticZero, &accounting)
            .unwrap();
        accounting.actual_assigned_attempt_count = 60;
        accounting.actual_observation_count = 60;
        accounting.assigned_action_start_receipt_count = 60;
        accounting.actual_pidfd_sigkill_count = 59;
        accounting.actual_fresh_exec_read_count = 59;
        accounting.actual_s16_mapping_phase_count = 113;
        accounting.successful_claim_count = 1;
        validate_exact_canary_accounting_v1(CanaryAccountingModeV1::CompleteExact, &accounting)
            .unwrap();
        accounting.actual_observation_count = 0;
        assert!(validate_exact_canary_accounting_v1(
            CanaryAccountingModeV1::CompleteExact,
            &accounting
        )
        .is_err());
        accounting.actual_observation_count = 60;
        accounting.assigned_action_start_receipt_count = 0;
        assert!(validate_exact_canary_accounting_v1(
            CanaryAccountingModeV1::CompleteExact,
            &accounting
        )
        .is_err());
        accounting.assigned_action_start_receipt_count = 60;
        accounting.retry_count = 1;
        assert!(validate_exact_canary_accounting_v1(
            CanaryAccountingModeV1::CompleteExact,
            &accounting
        )
        .is_err());
        accounting.retry_count = 0;
        accounting.ol05_count = 52;
        assert!(validate_exact_canary_accounting_v1(
            CanaryAccountingModeV1::CompleteExact,
            &accounting
        )
        .is_err());
        assert!(S20_EXACT_CANARY_INDEX_VALIDATOR_IMPLEMENTED);
    }
}
