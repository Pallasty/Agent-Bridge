//! Explicit, owner-asserted value labels for completed Resident Xiao Shu wakes.
//!
//! This is a product-evaluation receipt, not a model judgment. It binds one of
//! four fixed labels to the hashes in an already completed private wake
//! journal. The receipt contains no observed event, prompt, provider response,
//! arbitrary note, or action authority.

use crate::resident_cognition::RESIDENT_SUBJECT_ID;
use crate::resident_wake_journal::{
    default_resident_state_root, load_resident_wake_record, ResidentSubjectLease,
    ResidentWakeJournalError, ResidentWakeJournalState,
};
use anyhow::{anyhow, bail, Context, Result};
use serde::{Deserialize, Serialize};
use serde_json::{json, Value};
use sha2::{Digest, Sha256};
use std::fs::{File, OpenOptions};
use std::io::{self, Read, Write};
use std::os::unix::fs::{MetadataExt, OpenOptionsExt, PermissionsExt};
use std::path::{Path, PathBuf};
use std::time::{SystemTime, UNIX_EPOCH};
use uuid::Uuid;

pub const RESIDENT_OWNER_EVALUATION_SCHEMA_V0: &str = "agent_bridge.resident_owner_evaluation.v0";

const MAX_RECEIPT_BYTES: u64 = 16_384;

#[derive(Debug, Clone)]
pub struct ResidentOwnerEvaluationOptions {
    pub wake_id: String,
    pub label: ResidentOwnerLabel,
    pub journal_root: PathBuf,
    pub dry_run: bool,
}

impl ResidentOwnerEvaluationOptions {
    pub fn new(wake_id: impl Into<String>, label: ResidentOwnerLabel) -> Self {
        let journal_root = default_resident_state_root().join("resident-xiaoshu-v0");
        Self {
            wake_id: wake_id.into(),
            label,
            journal_root,
            dry_run: false,
        }
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum ResidentOwnerLabel {
    Useful,
    Neutral,
    Distracting,
    Harmful,
}

impl ResidentOwnerLabel {
    pub fn as_str(self) -> &'static str {
        match self {
            Self::Useful => "useful",
            Self::Neutral => "neutral",
            Self::Distracting => "distracting",
            Self::Harmful => "harmful",
        }
    }

    fn decision(self) -> ResidentOwnerEvaluationDecision {
        match self {
            Self::Useful => ResidentOwnerEvaluationDecision {
                value_signal: "positive".to_string(),
                stop_rule_triggered: false,
                recommended_next_gate: "owner_review_of_separate_m2_shadow_design_only".to_string(),
            },
            Self::Neutral => ResidentOwnerEvaluationDecision {
                value_signal: "no_positive_signal".to_string(),
                stop_rule_triggered: false,
                recommended_next_gate: "retain_explicit_m1_without_expansion".to_string(),
            },
            Self::Distracting => ResidentOwnerEvaluationDecision {
                value_signal: "negative".to_string(),
                stop_rule_triggered: true,
                recommended_next_gate: "stop_use_and_prepare_disable_review".to_string(),
            },
            Self::Harmful => ResidentOwnerEvaluationDecision {
                value_signal: "negative".to_string(),
                stop_rule_triggered: true,
                recommended_next_gate: "stop_use_and_prepare_rollback_review".to_string(),
            },
        }
    }
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct ResidentOwnerEvaluationDecision {
    pub value_signal: String,
    pub stop_rule_triggered: bool,
    pub recommended_next_gate: String,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct ResidentOwnerEvaluationReceipt {
    pub schema_version: String,
    pub evaluation_id: String,
    pub subject_id: String,
    pub wake_id: String,
    pub label: ResidentOwnerLabel,
    pub recorded_at_unix_ms: u64,
    pub cognition_final_sha256: String,
    pub execution_receipt_sha256: String,
    pub cognition_disposition: String,
    pub label_source: String,
    pub decision: ResidentOwnerEvaluationDecision,
}

impl ResidentOwnerEvaluationReceipt {
    fn validate(&self) -> Result<(), ResidentOwnerEvaluationError> {
        if self.schema_version != RESIDENT_OWNER_EVALUATION_SCHEMA_V0
            || self.subject_id != RESIDENT_SUBJECT_ID
            || !validate_identifier(&self.evaluation_id)
            || !validate_identifier(&self.wake_id)
            || self.recorded_at_unix_ms == 0
            || !is_sha256_hex(&self.cognition_final_sha256)
            || !is_sha256_hex(&self.execution_receipt_sha256)
            || self.cognition_disposition.is_empty()
            || self.cognition_disposition.chars().count() > 64
            || self.label_source != "explicit_local_cli_argument"
            || self.decision != self.label.decision()
        {
            return Err(ResidentOwnerEvaluationError::Corrupt);
        }
        Ok(())
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
enum EvaluationWriteStatus {
    Recorded,
    AlreadyRecorded,
}

impl EvaluationWriteStatus {
    fn as_str(self) -> &'static str {
        match self {
            Self::Recorded => "recorded",
            Self::AlreadyRecorded => "already_recorded",
        }
    }
}

#[derive(Debug, thiserror::Error)]
pub enum ResidentOwnerEvaluationError {
    #[error("resident_owner_evaluation_invalid_configuration")]
    InvalidConfiguration,
    #[error("resident_owner_evaluation_wake_not_found")]
    WakeNotFound,
    #[error("resident_owner_evaluation_wake_not_completed")]
    WakeNotCompleted,
    #[error("resident_owner_evaluation_wake_binding_mismatch")]
    WakeBindingMismatch,
    #[error("resident_owner_evaluation_conflict: existing={existing}, requested={requested}")]
    Conflict {
        existing: &'static str,
        requested: &'static str,
    },
    #[error("resident_owner_evaluation_io")]
    Io,
    #[error("resident_owner_evaluation_corrupt")]
    Corrupt,
}

fn now_millis() -> u64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|duration| duration.as_millis().min(u64::MAX as u128) as u64)
        .unwrap_or_default()
}

fn sha256_hex(bytes: impl AsRef<[u8]>) -> String {
    format!("{:x}", Sha256::digest(bytes.as_ref()))
}

fn evaluation_id(wake_id: &str) -> String {
    let material = format!("{RESIDENT_SUBJECT_ID}\0owner_evaluation\0{wake_id}");
    format!("evaluation-{}", &sha256_hex(material.as_bytes())[..32])
}

fn validate_identifier(value: &str) -> bool {
    !value.is_empty()
        && value.len() <= 128
        && value
            .bytes()
            .all(|byte| byte.is_ascii_alphanumeric() || b"-_:.".contains(&byte))
}

fn is_sha256_hex(value: &str) -> bool {
    value.len() == 64
        && value
            .bytes()
            .all(|byte| byte.is_ascii_digit() || (b'a'..=b'f').contains(&byte))
}

fn boundary() -> Value {
    json!({
        "explicit_local_operator_assertion": true,
        "owner_identity_cryptographically_authenticated": false,
        "model_generated_label": false,
        "provider_invoked": false,
        "raw_event_read_or_persisted": false,
        "provider_result_rewritten": false,
        "creates_cognitive_wake": false,
        "executes_action": false,
        "automatic_runtime_change": false,
        "automatic_memory_promotion": false,
        "m2_admitted": false
    })
}

fn evaluation_path(root: &Path, wake_id: &str) -> PathBuf {
    root.join("evaluations").join(format!("{wake_id}.json"))
}

fn ensure_private_directory(path: &Path) -> Result<(), ResidentOwnerEvaluationError> {
    std::fs::create_dir_all(path).map_err(|_| ResidentOwnerEvaluationError::Io)?;
    let metadata = std::fs::symlink_metadata(path).map_err(|_| ResidentOwnerEvaluationError::Io)?;
    if !metadata.file_type().is_dir() {
        return Err(ResidentOwnerEvaluationError::Corrupt);
    }
    std::fs::set_permissions(path, std::fs::Permissions::from_mode(0o700))
        .map_err(|_| ResidentOwnerEvaluationError::Io)
}

fn sync_directory(path: &Path) -> Result<(), ResidentOwnerEvaluationError> {
    File::open(path)
        .and_then(|directory| directory.sync_all())
        .map_err(|_| ResidentOwnerEvaluationError::Io)
}

fn open_private_receipt(path: &Path) -> Result<File, ResidentOwnerEvaluationError> {
    let file = OpenOptions::new()
        .read(true)
        .custom_flags(libc::O_CLOEXEC | libc::O_NOFOLLOW)
        .open(path)
        .map_err(|error| {
            if error.kind() == io::ErrorKind::NotFound {
                ResidentOwnerEvaluationError::WakeNotFound
            } else {
                ResidentOwnerEvaluationError::Io
            }
        })?;
    let metadata = file
        .metadata()
        .map_err(|_| ResidentOwnerEvaluationError::Io)?;
    if !metadata.is_file()
        || metadata.len() > MAX_RECEIPT_BYTES
        || metadata.mode() & 0o777 != 0o600
        || metadata.nlink() != 1
    {
        return Err(ResidentOwnerEvaluationError::Corrupt);
    }
    Ok(file)
}

pub fn load_resident_owner_evaluation(
    root: &Path,
    wake_id: &str,
) -> Result<Option<ResidentOwnerEvaluationReceipt>, ResidentOwnerEvaluationError> {
    if !root.is_absolute() || !validate_identifier(wake_id) {
        return Err(ResidentOwnerEvaluationError::InvalidConfiguration);
    }
    let path = evaluation_path(root, wake_id);
    let file = match open_private_receipt(&path) {
        Ok(file) => file,
        Err(ResidentOwnerEvaluationError::WakeNotFound) => return Ok(None),
        Err(error) => return Err(error),
    };
    let mut bytes = Vec::new();
    file.take(MAX_RECEIPT_BYTES + 1)
        .read_to_end(&mut bytes)
        .map_err(|_| ResidentOwnerEvaluationError::Io)?;
    if bytes.len() as u64 > MAX_RECEIPT_BYTES {
        return Err(ResidentOwnerEvaluationError::Corrupt);
    }
    let receipt: ResidentOwnerEvaluationReceipt =
        serde_json::from_slice(&bytes).map_err(|_| ResidentOwnerEvaluationError::Corrupt)?;
    receipt.validate()?;
    if receipt.wake_id != wake_id {
        return Err(ResidentOwnerEvaluationError::Corrupt);
    }
    Ok(Some(receipt))
}

pub fn load_bound_resident_owner_evaluation(
    root: &Path,
    wake_id: &str,
) -> Result<Option<ResidentOwnerEvaluationReceipt>, ResidentOwnerEvaluationError> {
    let Some(receipt) = load_resident_owner_evaluation(root, wake_id)? else {
        return Ok(None);
    };
    let wake = load_resident_wake_record(root, wake_id).map_err(|error| match error {
        ResidentWakeJournalError::Io => ResidentOwnerEvaluationError::WakeNotFound,
        _ => ResidentOwnerEvaluationError::Corrupt,
    })?;
    if wake.state != ResidentWakeJournalState::Completed
        || wake.subject_id != RESIDENT_SUBJECT_ID
        || wake.final_sha256 != receipt.cognition_final_sha256
        || wake.execution_receipt_sha256 != receipt.execution_receipt_sha256
        || wake.disposition != receipt.cognition_disposition
    {
        return Err(ResidentOwnerEvaluationError::WakeBindingMismatch);
    }
    Ok(Some(receipt))
}

fn persist_receipt(
    root: &Path,
    receipt: &ResidentOwnerEvaluationReceipt,
) -> Result<EvaluationWriteStatus, ResidentOwnerEvaluationError> {
    let directory = root.join("evaluations");
    ensure_private_directory(&directory)?;
    let path = evaluation_path(root, &receipt.wake_id);
    let temporary = directory.join(format!(".{}.{}.tmp", receipt.evaluation_id, Uuid::new_v4()));
    let bytes = serde_json::to_vec(receipt).map_err(|_| ResidentOwnerEvaluationError::Corrupt)?;
    let mut file = OpenOptions::new()
        .write(true)
        .create_new(true)
        .mode(0o600)
        .custom_flags(libc::O_CLOEXEC | libc::O_NOFOLLOW)
        .open(&temporary)
        .map_err(|_| ResidentOwnerEvaluationError::Io)?;
    if file
        .write_all(&bytes)
        .and_then(|_| file.sync_all())
        .is_err()
    {
        let _ = std::fs::remove_file(&temporary);
        return Err(ResidentOwnerEvaluationError::Io);
    }
    drop(file);
    match std::fs::hard_link(&temporary, &path) {
        Ok(()) => {
            std::fs::remove_file(&temporary).map_err(|_| ResidentOwnerEvaluationError::Io)?;
            sync_directory(&directory)?;
            Ok(EvaluationWriteStatus::Recorded)
        }
        Err(error) if error.kind() == io::ErrorKind::AlreadyExists => {
            let _ = std::fs::remove_file(&temporary);
            let existing = load_bound_resident_owner_evaluation(root, &receipt.wake_id)?
                .ok_or(ResidentOwnerEvaluationError::Corrupt)?;
            if existing.label != receipt.label {
                return Err(ResidentOwnerEvaluationError::Conflict {
                    existing: existing.label.as_str(),
                    requested: receipt.label.as_str(),
                });
            }
            Ok(EvaluationWriteStatus::AlreadyRecorded)
        }
        Err(_) => {
            let _ = std::fs::remove_file(&temporary);
            Err(ResidentOwnerEvaluationError::Io)
        }
    }
}

fn dry_run_packet(options: &ResidentOwnerEvaluationOptions) -> Value {
    json!({
        "schema": RESIDENT_OWNER_EVALUATION_SCHEMA_V0,
        "status": "dry_run",
        "evaluation_id": evaluation_id(&options.wake_id),
        "subject_id": RESIDENT_SUBJECT_ID,
        "wake_id": options.wake_id,
        "label": options.label,
        "binding_verified": false,
        "receipt_recorded": false,
        "decision": options.label.decision(),
        "boundary": boundary()
    })
}

/// Persist one explicit local owner evaluation for a completed resident wake.
///
/// The private receipt is the authoritative record. A repeated identical label
/// is idempotent; a different label for the same wake is a conflict and cannot
/// overwrite history.
pub fn record_resident_owner_evaluation(options: ResidentOwnerEvaluationOptions) -> Result<Value> {
    let options = ResidentOwnerEvaluationOptions {
        wake_id: options.wake_id.trim().to_string(),
        ..options
    };
    if !validate_identifier(&options.wake_id) {
        bail!(ResidentOwnerEvaluationError::InvalidConfiguration);
    }
    if options.dry_run {
        return Ok(dry_run_packet(&options));
    }
    if !options.journal_root.is_absolute() || !options.journal_root.is_dir() {
        bail!(ResidentOwnerEvaluationError::InvalidConfiguration);
    }

    let _lease = ResidentSubjectLease::acquire(&options.journal_root)
        .map_err(|error| anyhow!(error))
        .context("acquire resident subject writer lease for owner evaluation")?;
    let wake =
        load_resident_wake_record(&options.journal_root, &options.wake_id).map_err(|error| {
            match error {
                ResidentWakeJournalError::Io => anyhow!(ResidentOwnerEvaluationError::WakeNotFound),
                _ => anyhow!(ResidentOwnerEvaluationError::Corrupt),
            }
        })?;
    if wake.state != ResidentWakeJournalState::Completed || !wake.advances_continuity {
        bail!(ResidentOwnerEvaluationError::WakeNotCompleted);
    }
    if wake.subject_id != RESIDENT_SUBJECT_ID {
        bail!(ResidentOwnerEvaluationError::WakeBindingMismatch);
    }

    let receipt = ResidentOwnerEvaluationReceipt {
        schema_version: RESIDENT_OWNER_EVALUATION_SCHEMA_V0.to_string(),
        evaluation_id: evaluation_id(&options.wake_id),
        subject_id: RESIDENT_SUBJECT_ID.to_string(),
        wake_id: options.wake_id.clone(),
        label: options.label,
        recorded_at_unix_ms: now_millis().max(1),
        cognition_final_sha256: wake.final_sha256.clone(),
        execution_receipt_sha256: wake.execution_receipt_sha256.clone(),
        cognition_disposition: wake.disposition.clone(),
        label_source: "explicit_local_cli_argument".to_string(),
        decision: options.label.decision(),
    };
    receipt.validate().map_err(|error| anyhow!(error))?;
    let status =
        persist_receipt(&options.journal_root, &receipt).map_err(|error| anyhow!(error))?;
    let persisted = load_bound_resident_owner_evaluation(&options.journal_root, &options.wake_id)
        .map_err(|error| anyhow!(error))?
        .ok_or_else(|| anyhow!(ResidentOwnerEvaluationError::Corrupt))?;

    Ok(json!({
        "schema": RESIDENT_OWNER_EVALUATION_SCHEMA_V0,
        "status": status.as_str(),
        "receipt": persisted,
        "binding": {
            "wake_journal_state": "completed",
            "subject_match": true,
            "cognition_final_sha256_match": true,
            "execution_receipt_sha256_match": true
        },
        "boundary": boundary()
    }))
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::resident_wake_journal::ResidentWakeReservation;

    fn completed_wake(root: &Path, wake_id: &str) {
        let mut wake = ResidentWakeReservation::reserve(
            root,
            wake_id,
            "episode-owner-eval-1",
            RESIDENT_SUBJECT_ID,
            100,
        )
        .expect("reserve wake");
        wake.complete(200, "respond", &"a".repeat(64), &"b".repeat(64))
            .expect("complete wake");
    }

    fn options(
        root: &Path,
        wake_id: &str,
        label: ResidentOwnerLabel,
    ) -> ResidentOwnerEvaluationOptions {
        ResidentOwnerEvaluationOptions {
            wake_id: wake_id.to_string(),
            label,
            journal_root: root.to_path_buf(),
            dry_run: false,
        }
    }

    #[test]
    fn dry_run_is_state_free_and_does_not_claim_binding() {
        let temp = tempfile::tempdir().expect("tempdir");
        let missing = temp.path().join("missing");
        let mut options = options(&missing, "wake-eval-dry", ResidentOwnerLabel::Useful);
        options.dry_run = true;
        let packet = record_resident_owner_evaluation(options).expect("dry run");
        assert_eq!(packet["status"], "dry_run");
        assert_eq!(packet["binding_verified"], false);
        assert_eq!(packet["receipt_recorded"], false);
        assert_eq!(packet["boundary"]["m2_admitted"], false);
        assert!(!missing.exists());
    }

    #[test]
    fn completed_wake_receives_private_hash_bound_receipt() {
        let temp = tempfile::tempdir().expect("tempdir");
        let root = temp.path().join("resident");
        completed_wake(&root, "wake-eval-1");
        let packet = record_resident_owner_evaluation(options(
            &root,
            "wake-eval-1",
            ResidentOwnerLabel::Useful,
        ))
        .expect("record evaluation");
        assert_eq!(packet["status"], "recorded");
        assert_eq!(packet["receipt"]["label"], "useful");
        assert_eq!(packet["receipt"]["cognition_final_sha256"], "a".repeat(64));
        assert_eq!(packet["boundary"]["provider_invoked"], false);
        assert_eq!(packet["boundary"]["automatic_runtime_change"], false);

        let path = evaluation_path(&root, "wake-eval-1");
        let metadata = std::fs::metadata(&path).expect("metadata");
        assert_eq!(metadata.permissions().mode() & 0o777, 0o600);
        assert_eq!(metadata.nlink(), 1);
        assert!(std::fs::read_dir(root.join("evaluations"))
            .expect("evaluations directory")
            .all(|entry| !entry
                .expect("directory entry")
                .file_name()
                .to_string_lossy()
                .starts_with('.')));
        let raw = std::fs::read_to_string(path).expect("receipt text");
        assert!(!raw.contains("observed_event"));
        assert!(!raw.contains("provider_response"));
        assert!(!raw.contains("note"));
    }

    #[test]
    fn repeated_label_is_idempotent_and_conflicting_label_fails_closed() {
        let temp = tempfile::tempdir().expect("tempdir");
        let root = temp.path().join("resident");
        completed_wake(&root, "wake-eval-2");
        let first = record_resident_owner_evaluation(options(
            &root,
            "wake-eval-2",
            ResidentOwnerLabel::Neutral,
        ))
        .expect("first evaluation");
        let second = record_resident_owner_evaluation(options(
            &root,
            "wake-eval-2",
            ResidentOwnerLabel::Neutral,
        ))
        .expect("idempotent replay");
        assert_eq!(first["status"], "recorded");
        assert_eq!(second["status"], "already_recorded");
        assert_eq!(first["receipt"], second["receipt"]);

        let error = record_resident_owner_evaluation(options(
            &root,
            "wake-eval-2",
            ResidentOwnerLabel::Harmful,
        ))
        .expect_err("conflicting evaluation must fail");
        assert!(format!("{error:#}").contains("resident_owner_evaluation_conflict"));
        let persisted = load_bound_resident_owner_evaluation(&root, "wake-eval-2")
            .expect("load")
            .expect("receipt");
        assert_eq!(persisted.label, ResidentOwnerLabel::Neutral);
    }

    #[test]
    fn missing_or_failed_wake_cannot_be_evaluated() {
        let temp = tempfile::tempdir().expect("tempdir");
        let root = temp.path().join("resident");
        std::fs::create_dir_all(&root).expect("root");
        let missing = record_resident_owner_evaluation(options(
            &root,
            "wake-missing",
            ResidentOwnerLabel::Useful,
        ))
        .expect_err("missing wake");
        assert!(format!("{missing:#}").contains("wake_not_found"));

        let mut failed = ResidentWakeReservation::reserve(
            &root,
            "wake-eval-failed",
            "episode-owner-eval-2",
            RESIDENT_SUBJECT_ID,
            100,
        )
        .expect("reserve failed wake");
        failed
            .fail(200, "provider_deadline", true)
            .expect("fail wake");
        let error = record_resident_owner_evaluation(options(
            &root,
            "wake-eval-failed",
            ResidentOwnerLabel::Useful,
        ))
        .expect_err("failed wake");
        assert!(format!("{error:#}").contains("wake_not_completed"));
    }

    #[test]
    fn tampered_wake_binding_is_rejected_on_load() {
        let temp = tempfile::tempdir().expect("tempdir");
        let root = temp.path().join("resident");
        completed_wake(&root, "wake-eval-3");
        record_resident_owner_evaluation(options(&root, "wake-eval-3", ResidentOwnerLabel::Useful))
            .expect("evaluation");

        let wake_path = root.join("wakes/wake-eval-3.json");
        let mut wake: Value =
            serde_json::from_str(&std::fs::read_to_string(&wake_path).expect("wake text"))
                .expect("wake json");
        wake["final_sha256"] = Value::String("c".repeat(64));
        std::fs::write(
            &wake_path,
            serde_json::to_vec(&wake).expect("serialize wake"),
        )
        .expect("tamper wake");
        let error = load_bound_resident_owner_evaluation(&root, "wake-eval-3")
            .expect_err("binding mismatch");
        assert!(matches!(
            error,
            ResidentOwnerEvaluationError::WakeBindingMismatch
        ));
    }
}
