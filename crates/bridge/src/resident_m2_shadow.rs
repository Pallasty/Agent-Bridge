//! Default-off, non-waking M2 policy shadow for Resident Xiao Shu.
//!
//! Callers provide only a typed trigger and content hashes. Agent-Bridge binds
//! the preview to an existing useful owner evaluation, applies a frozen sparse
//! wake policy, and may persist a private content-free shadow report. It never
//! invokes a provider, creates a cognitive wake, schedules work, or admits M2.

use crate::resident_cognition::RESIDENT_SUBJECT_ID;
use crate::resident_owner_evaluation::{load_bound_resident_owner_evaluation, ResidentOwnerLabel};
use crate::resident_wake_journal::{default_resident_state_root, ResidentSubjectLease};
use anyhow::{anyhow, bail, Context, Result};
use serde::{Deserialize, Serialize};
use serde_json::{json, Value};
use sha2::{Digest, Sha256};
use std::collections::{BTreeMap, BTreeSet};
use std::fs::{File, OpenOptions};
use std::io::{self, Read, Write};
use std::os::unix::fs::{MetadataExt, OpenOptionsExt, PermissionsExt};
use std::path::{Path, PathBuf};
use std::time::{SystemTime, UNIX_EPOCH};
use uuid::Uuid;

pub const RESIDENT_M2_SHADOW_SCHEMA_V0: &str = "agent_bridge.resident_m2_shadow.v0";
pub const RESIDENT_M2_SHADOW_REVIEW_SCHEMA_V0: &str = "agent_bridge.resident_m2_shadow_review.v0";
const RESIDENT_M2_SHADOW_ANCHOR_SCHEMA_V0: &str = "agent_bridge.resident_m2_shadow_anchor.v0";
const RESIDENT_M2_SHADOW_LEDGER_SCHEMA_V0: &str = "agent_bridge.resident_m2_shadow_ledger.v0";
const POLICY_REVISION: u64 = 1;
const MIN_NATURAL_REPORTS_FOR_OWNER_REVIEW: usize = 3;
const MIN_NATURAL_TRIGGER_KINDS_FOR_OWNER_REVIEW: usize = 2;
const MAX_REPORT_BYTES: u64 = 16_384;
const MILLIS_PER_SECOND: u64 = 1_000;
const SECONDS_PER_DAY: i64 = 86_400;

#[derive(Debug, Clone)]
pub struct ResidentM2ShadowOptions {
    pub basis_wake_id: String,
    pub trigger_kind: ResidentM2ShadowTriggerKind,
    pub signal_sha256: String,
    pub evidence_sha256: String,
    pub evidence_status: ResidentM2ShadowEvidenceStatus,
    pub observed_at_unix_ms: u64,
    pub due_at_unix_ms: Option<u64>,
    pub severity: ResidentM2ShadowSeverity,
    pub foreground_state: ResidentM2ShadowForegroundState,
    pub evaluated_at_unix_ms: u64,
    pub utc_offset_minutes: i16,
    pub journal_root: PathBuf,
    pub record: bool,
}

impl ResidentM2ShadowOptions {
    pub fn new(
        basis_wake_id: impl Into<String>,
        trigger_kind: ResidentM2ShadowTriggerKind,
        signal_sha256: impl Into<String>,
        evidence_sha256: impl Into<String>,
        observed_at_unix_ms: u64,
        utc_offset_minutes: i16,
    ) -> Self {
        Self {
            basis_wake_id: basis_wake_id.into(),
            trigger_kind,
            signal_sha256: signal_sha256.into(),
            evidence_sha256: evidence_sha256.into(),
            evidence_status: ResidentM2ShadowEvidenceStatus::Unknown,
            observed_at_unix_ms,
            due_at_unix_ms: None,
            severity: ResidentM2ShadowSeverity::Info,
            foreground_state: ResidentM2ShadowForegroundState::Unknown,
            evaluated_at_unix_ms: now_millis().max(1),
            utc_offset_minutes,
            journal_root: default_resident_state_root().join("resident-xiaoshu-v0"),
            record: false,
        }
    }
}

#[derive(Debug, Clone)]
pub struct ResidentM2ShadowReviewOptions {
    pub natural_report_ids: Vec<String>,
    pub mechanics_report_ids: Vec<String>,
    pub journal_root: PathBuf,
}

impl ResidentM2ShadowReviewOptions {
    pub fn new() -> Self {
        Self {
            natural_report_ids: Vec::new(),
            mechanics_report_ids: Vec::new(),
            journal_root: default_resident_state_root().join("resident-xiaoshu-v0"),
        }
    }
}

impl Default for ResidentM2ShadowReviewOptions {
    fn default() -> Self {
        Self::new()
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum ResidentM2ShadowTriggerKind {
    CommitmentDue,
    Recovery,
    Failure,
}

impl ResidentM2ShadowTriggerKind {
    fn as_str(self) -> &'static str {
        match self {
            Self::CommitmentDue => "commitment_due",
            Self::Recovery => "recovery",
            Self::Failure => "failure",
        }
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum ResidentM2ShadowEvidenceStatus {
    Verified,
    NotVerified,
    Unknown,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum ResidentM2ShadowSeverity {
    Info,
    Warning,
    Critical,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum ResidentM2ShadowForegroundState {
    Active,
    Inactive,
    Unknown,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct ResidentM2ShadowCandidate {
    pub trigger_kind: ResidentM2ShadowTriggerKind,
    pub signal_sha256: String,
    pub evidence_sha256: String,
    pub evidence_status: ResidentM2ShadowEvidenceStatus,
    pub observed_at_unix_ms: u64,
    pub due_at_unix_ms: Option<u64>,
    pub severity: ResidentM2ShadowSeverity,
    pub foreground_state: ResidentM2ShadowForegroundState,
    pub evaluated_at_unix_ms: u64,
    pub utc_offset_minutes: i16,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct ResidentM2ShadowPolicy {
    pub revision: u64,
    pub quiet_start_local_minute: u16,
    pub quiet_end_local_minute: u16,
    pub dedup_horizon_secs: u64,
    pub minimum_interval_secs: u64,
    pub max_projected_wakes_per_local_day: u16,
    pub recovery_freshness_secs: u64,
    pub failure_freshness_secs: u64,
    pub hypothetical_provider_timeout_secs: u64,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct ResidentM2ShadowDecision {
    pub would_wake: bool,
    pub suppression_reasons: Vec<String>,
    pub projected_provider_calls: u8,
    pub projected_provider_timeout_secs: u64,
    pub actual_provider_calls: u8,
    pub actual_wakes_created: u8,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct ResidentM2ShadowBoundary {
    pub shadow_only: bool,
    pub default_off: bool,
    pub candidate_source_automatically_discovered: bool,
    pub candidate_assertions_cryptographically_authenticated: bool,
    pub raw_signal_read_or_persisted: bool,
    pub raw_evidence_read_or_persisted: bool,
    pub provider_invoked: bool,
    pub creates_cognitive_wake: bool,
    pub scheduler_installed: bool,
    pub executes_action: bool,
    pub automatic_runtime_change: bool,
    pub automatic_memory_promotion: bool,
    pub m2_admitted: bool,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct ResidentM2ShadowReport {
    pub schema_version: String,
    pub report_id: String,
    pub subject_id: String,
    pub basis_wake_id: String,
    pub basis_evaluation_id: String,
    pub basis_evaluation_sha256: String,
    pub candidate: ResidentM2ShadowCandidate,
    pub policy: ResidentM2ShadowPolicy,
    pub decision: ResidentM2ShadowDecision,
    pub boundary: ResidentM2ShadowBoundary,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
struct ResidentM2ShadowAnchor {
    schema_version: String,
    ledger_id: String,
    report_id: String,
    report_sha256: String,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
struct ResidentM2ShadowLedger {
    schema_version: String,
    ledger_id: String,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
enum ShadowWriteStatus {
    Recorded,
    AlreadyRecorded,
}

impl ShadowWriteStatus {
    fn as_str(self) -> &'static str {
        match self {
            Self::Recorded => "recorded",
            Self::AlreadyRecorded => "already_recorded",
        }
    }
}

#[derive(Debug, thiserror::Error)]
pub enum ResidentM2ShadowError {
    #[error("resident_m2_shadow_invalid_configuration")]
    InvalidConfiguration,
    #[error("resident_m2_shadow_useful_owner_basis_required")]
    UsefulOwnerBasisRequired,
    #[error("resident_m2_shadow_stop_label_active")]
    StopLabelActive,
    #[error("resident_m2_shadow_io")]
    Io,
    #[error("resident_m2_shadow_corrupt")]
    Corrupt,
    #[error("resident_m2_shadow_conflict")]
    Conflict,
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

fn is_sha256_hex(value: &str) -> bool {
    value.len() == 64
        && value
            .bytes()
            .all(|byte| byte.is_ascii_digit() || (b'a'..=b'f').contains(&byte))
}

fn validate_identifier(value: &str) -> bool {
    !value.is_empty()
        && value.len() <= 128
        && value
            .bytes()
            .all(|byte| byte.is_ascii_alphanumeric() || b"-_:".contains(&byte))
}

fn frozen_policy() -> ResidentM2ShadowPolicy {
    ResidentM2ShadowPolicy {
        revision: POLICY_REVISION,
        quiet_start_local_minute: 22 * 60,
        quiet_end_local_minute: 8 * 60,
        dedup_horizon_secs: 24 * 60 * 60,
        minimum_interval_secs: 6 * 60 * 60,
        max_projected_wakes_per_local_day: 2,
        recovery_freshness_secs: 6 * 60 * 60,
        failure_freshness_secs: 60 * 60,
        hypothetical_provider_timeout_secs: 120,
    }
}

fn boundary() -> ResidentM2ShadowBoundary {
    ResidentM2ShadowBoundary {
        shadow_only: true,
        default_off: true,
        candidate_source_automatically_discovered: false,
        candidate_assertions_cryptographically_authenticated: false,
        raw_signal_read_or_persisted: false,
        raw_evidence_read_or_persisted: false,
        provider_invoked: false,
        creates_cognitive_wake: false,
        scheduler_installed: false,
        executes_action: false,
        automatic_runtime_change: false,
        automatic_memory_promotion: false,
        m2_admitted: false,
    }
}

fn candidate_from_options(options: &ResidentM2ShadowOptions) -> ResidentM2ShadowCandidate {
    ResidentM2ShadowCandidate {
        trigger_kind: options.trigger_kind,
        signal_sha256: options.signal_sha256.clone(),
        evidence_sha256: options.evidence_sha256.clone(),
        evidence_status: options.evidence_status,
        observed_at_unix_ms: options.observed_at_unix_ms,
        due_at_unix_ms: options.due_at_unix_ms,
        severity: options.severity,
        foreground_state: options.foreground_state,
        evaluated_at_unix_ms: options.evaluated_at_unix_ms,
        utc_offset_minutes: options.utc_offset_minutes,
    }
}

fn validate_candidate(candidate: &ResidentM2ShadowCandidate) -> Result<()> {
    if !is_sha256_hex(&candidate.signal_sha256)
        || !is_sha256_hex(&candidate.evidence_sha256)
        || candidate.observed_at_unix_ms == 0
        || candidate.evaluated_at_unix_ms == 0
        || candidate.observed_at_unix_ms > candidate.evaluated_at_unix_ms
        || !(-840..=840).contains(&candidate.utc_offset_minutes)
    {
        bail!(ResidentM2ShadowError::InvalidConfiguration);
    }
    match candidate.trigger_kind {
        ResidentM2ShadowTriggerKind::CommitmentDue => {
            if !matches!(candidate.due_at_unix_ms, Some(due) if due != 0) {
                bail!(ResidentM2ShadowError::InvalidConfiguration);
            }
        }
        ResidentM2ShadowTriggerKind::Recovery | ResidentM2ShadowTriggerKind::Failure => {
            if candidate.due_at_unix_ms.is_some() {
                bail!(ResidentM2ShadowError::InvalidConfiguration);
            }
        }
    }
    Ok(())
}

fn local_seconds(unix_ms: u64, utc_offset_minutes: i16) -> i64 {
    (unix_ms / MILLIS_PER_SECOND) as i64 + i64::from(utc_offset_minutes) * 60
}

fn local_minute_of_day(candidate: &ResidentM2ShadowCandidate) -> u16 {
    (local_seconds(candidate.evaluated_at_unix_ms, candidate.utc_offset_minutes)
        .rem_euclid(SECONDS_PER_DAY)
        / 60) as u16
}

fn local_day(candidate: &ResidentM2ShadowCandidate) -> i64 {
    local_seconds(candidate.evaluated_at_unix_ms, candidate.utc_offset_minutes)
        .div_euclid(SECONDS_PER_DAY)
}

fn report_id(basis_evaluation_id: &str, candidate: &ResidentM2ShadowCandidate) -> Result<String> {
    let candidate_bytes =
        serde_json::to_vec(candidate).map_err(|_| anyhow!(ResidentM2ShadowError::Corrupt))?;
    let mut material = Vec::new();
    material.extend_from_slice(RESIDENT_SUBJECT_ID.as_bytes());
    material.push(0);
    material.extend_from_slice(basis_evaluation_id.as_bytes());
    material.push(0);
    material.extend_from_slice(&POLICY_REVISION.to_le_bytes());
    material.extend_from_slice(&candidate_bytes);
    Ok(format!("shadow-{}", &sha256_hex(material)[..32]))
}

fn shadow_directory(root: &Path) -> PathBuf {
    root.join("m2-shadow-reports")
}

fn anchor_directory(root: &Path) -> PathBuf {
    root.join("m2-shadow-report-anchors")
}

fn report_path(root: &Path, report_id: &str) -> PathBuf {
    shadow_directory(root).join(format!("{report_id}.json"))
}

fn anchor_path(root: &Path, report_id: &str) -> PathBuf {
    anchor_directory(root).join(format!("{report_id}.json"))
}

fn ledger_path(root: &Path) -> PathBuf {
    root.join("m2-shadow-ledger.json")
}

fn ensure_private_directory(path: &Path) -> Result<(), ResidentM2ShadowError> {
    std::fs::create_dir_all(path).map_err(|_| ResidentM2ShadowError::Io)?;
    let metadata = std::fs::symlink_metadata(path).map_err(|_| ResidentM2ShadowError::Io)?;
    if !metadata.file_type().is_dir() {
        return Err(ResidentM2ShadowError::Corrupt);
    }
    std::fs::set_permissions(path, std::fs::Permissions::from_mode(0o700))
        .map_err(|_| ResidentM2ShadowError::Io)?;
    let mode = std::fs::symlink_metadata(path)
        .map_err(|_| ResidentM2ShadowError::Io)?
        .mode()
        & 0o777;
    if mode != 0o700 {
        return Err(ResidentM2ShadowError::Corrupt);
    }
    Ok(())
}

fn sync_directory(path: &Path) -> Result<(), ResidentM2ShadowError> {
    File::open(path)
        .and_then(|directory| directory.sync_all())
        .map_err(|_| ResidentM2ShadowError::Io)
}

fn validate_report(report: &ResidentM2ShadowReport) -> Result<(), ResidentM2ShadowError> {
    if report.schema_version != RESIDENT_M2_SHADOW_SCHEMA_V0
        || report.subject_id != RESIDENT_SUBJECT_ID
        || !validate_identifier(&report.report_id)
        || !validate_identifier(&report.basis_wake_id)
        || !validate_identifier(&report.basis_evaluation_id)
        || !is_sha256_hex(&report.basis_evaluation_sha256)
        || report.policy != frozen_policy()
        || report.boundary != boundary()
        || report.decision.actual_provider_calls != 0
        || report.decision.actual_wakes_created != 0
        || report.decision.projected_provider_calls != u8::from(report.decision.would_wake)
        || report.decision.projected_provider_timeout_secs
            != if report.decision.would_wake {
                report.policy.hypothetical_provider_timeout_secs
            } else {
                0
            }
    {
        return Err(ResidentM2ShadowError::Corrupt);
    }
    validate_candidate(&report.candidate).map_err(|_| ResidentM2ShadowError::Corrupt)?;
    if report_id(&report.basis_evaluation_id, &report.candidate)
        .map_err(|_| ResidentM2ShadowError::Corrupt)?
        != report.report_id
    {
        return Err(ResidentM2ShadowError::Corrupt);
    }
    Ok(())
}

fn open_private_report(path: &Path) -> Result<File, ResidentM2ShadowError> {
    let file = OpenOptions::new()
        .read(true)
        .custom_flags(libc::O_CLOEXEC | libc::O_NOFOLLOW)
        .open(path)
        .map_err(|error| {
            if error.kind() == io::ErrorKind::NotFound {
                ResidentM2ShadowError::Io
            } else {
                ResidentM2ShadowError::Corrupt
            }
        })?;
    let metadata = file.metadata().map_err(|_| ResidentM2ShadowError::Io)?;
    if !metadata.is_file()
        || metadata.len() > MAX_REPORT_BYTES
        || metadata.mode() & 0o777 != 0o600
        || metadata.nlink() != 1
    {
        return Err(ResidentM2ShadowError::Corrupt);
    }
    Ok(file)
}

fn load_report(path: &Path) -> Result<ResidentM2ShadowReport, ResidentM2ShadowError> {
    let file = open_private_report(path)?;
    let mut bytes = Vec::new();
    file.take(MAX_REPORT_BYTES + 1)
        .read_to_end(&mut bytes)
        .map_err(|_| ResidentM2ShadowError::Io)?;
    if bytes.len() as u64 > MAX_REPORT_BYTES {
        return Err(ResidentM2ShadowError::Corrupt);
    }
    let report: ResidentM2ShadowReport =
        serde_json::from_slice(&bytes).map_err(|_| ResidentM2ShadowError::Corrupt)?;
    validate_report(&report)?;
    Ok(report)
}

fn load_private_bytes(path: &Path) -> Result<Vec<u8>, ResidentM2ShadowError> {
    let file = open_private_report(path)?;
    let mut bytes = Vec::new();
    file.take(MAX_REPORT_BYTES + 1)
        .read_to_end(&mut bytes)
        .map_err(|_| ResidentM2ShadowError::Io)?;
    if bytes.len() as u64 > MAX_REPORT_BYTES {
        return Err(ResidentM2ShadowError::Corrupt);
    }
    Ok(bytes)
}

fn validate_anchor(anchor: &ResidentM2ShadowAnchor) -> Result<(), ResidentM2ShadowError> {
    if anchor.schema_version != RESIDENT_M2_SHADOW_ANCHOR_SCHEMA_V0
        || !anchor.ledger_id.starts_with("shadow-ledger-")
        || !validate_identifier(&anchor.ledger_id)
        || !anchor.report_id.starts_with("shadow-")
        || !validate_identifier(&anchor.report_id)
        || !is_sha256_hex(&anchor.report_sha256)
    {
        return Err(ResidentM2ShadowError::Corrupt);
    }
    Ok(())
}

fn validate_ledger(ledger: &ResidentM2ShadowLedger) -> Result<(), ResidentM2ShadowError> {
    if ledger.schema_version != RESIDENT_M2_SHADOW_LEDGER_SCHEMA_V0
        || !ledger.ledger_id.starts_with("shadow-ledger-")
        || !validate_identifier(&ledger.ledger_id)
    {
        return Err(ResidentM2ShadowError::Corrupt);
    }
    Ok(())
}

fn load_ledger(root: &Path) -> Result<ResidentM2ShadowLedger, ResidentM2ShadowError> {
    let path = ledger_path(root);
    match std::fs::symlink_metadata(&path) {
        Ok(_) => {}
        Err(error) if error.kind() == io::ErrorKind::NotFound => {
            return Err(ResidentM2ShadowError::Corrupt);
        }
        Err(_) => return Err(ResidentM2ShadowError::Io),
    }
    let bytes = load_private_bytes(&path)?;
    let ledger = serde_json::from_slice(&bytes).map_err(|_| ResidentM2ShadowError::Corrupt)?;
    validate_ledger(&ledger)?;
    Ok(ledger)
}

fn ensure_ledger(root: &Path) -> Result<ResidentM2ShadowLedger, ResidentM2ShadowError> {
    let path = ledger_path(root);
    match std::fs::symlink_metadata(&path) {
        Ok(_) => return load_ledger(root),
        Err(error) if error.kind() == io::ErrorKind::NotFound => {}
        Err(_) => return Err(ResidentM2ShadowError::Io),
    }
    let ledger = ResidentM2ShadowLedger {
        schema_version: RESIDENT_M2_SHADOW_LEDGER_SCHEMA_V0.to_string(),
        ledger_id: format!("shadow-ledger-{}", Uuid::new_v4().simple()),
    };
    let bytes = serde_json::to_vec(&ledger).map_err(|_| ResidentM2ShadowError::Corrupt)?;
    let temporary = root.join(format!(".m2-shadow-ledger.{}.tmp", Uuid::new_v4()));
    let mut file = OpenOptions::new()
        .write(true)
        .create_new(true)
        .mode(0o600)
        .custom_flags(libc::O_CLOEXEC | libc::O_NOFOLLOW)
        .open(&temporary)
        .map_err(|_| ResidentM2ShadowError::Io)?;
    if file
        .write_all(&bytes)
        .and_then(|_| file.sync_all())
        .is_err()
    {
        let _ = std::fs::remove_file(&temporary);
        return Err(ResidentM2ShadowError::Io);
    }
    drop(file);
    match std::fs::hard_link(&temporary, &path) {
        Ok(()) => {
            std::fs::remove_file(&temporary).map_err(|_| ResidentM2ShadowError::Io)?;
            sync_directory(root)?;
            Ok(ledger)
        }
        Err(error) if error.kind() == io::ErrorKind::AlreadyExists => {
            let _ = std::fs::remove_file(&temporary);
            load_ledger(root)
        }
        Err(_) => {
            let _ = std::fs::remove_file(&temporary);
            Err(ResidentM2ShadowError::Io)
        }
    }
}

fn load_anchor(path: &Path) -> Result<ResidentM2ShadowAnchor, ResidentM2ShadowError> {
    let bytes = load_private_bytes(path)?;
    let anchor = serde_json::from_slice(&bytes).map_err(|_| ResidentM2ShadowError::Corrupt)?;
    validate_anchor(&anchor)?;
    Ok(anchor)
}

fn persist_anchor(
    root: &Path,
    ledger_id: &str,
    report_id: &str,
    report_sha256: &str,
) -> Result<(), ResidentM2ShadowError> {
    let directory = anchor_directory(root);
    ensure_private_directory(&directory)?;
    let path = anchor_path(root, report_id);
    let anchor = ResidentM2ShadowAnchor {
        schema_version: RESIDENT_M2_SHADOW_ANCHOR_SCHEMA_V0.to_string(),
        ledger_id: ledger_id.to_string(),
        report_id: report_id.to_string(),
        report_sha256: report_sha256.to_string(),
    };
    validate_anchor(&anchor)?;
    let bytes = serde_json::to_vec(&anchor).map_err(|_| ResidentM2ShadowError::Corrupt)?;
    let temporary = directory.join(format!(".{report_id}.{}.tmp", Uuid::new_v4()));
    let mut file = OpenOptions::new()
        .write(true)
        .create_new(true)
        .mode(0o600)
        .custom_flags(libc::O_CLOEXEC | libc::O_NOFOLLOW)
        .open(&temporary)
        .map_err(|_| ResidentM2ShadowError::Io)?;
    if file
        .write_all(&bytes)
        .and_then(|_| file.sync_all())
        .is_err()
    {
        let _ = std::fs::remove_file(&temporary);
        return Err(ResidentM2ShadowError::Io);
    }
    drop(file);
    match std::fs::hard_link(&temporary, &path) {
        Ok(()) => {
            std::fs::remove_file(&temporary).map_err(|_| ResidentM2ShadowError::Io)?;
            sync_directory(&directory)
        }
        Err(error) if error.kind() == io::ErrorKind::AlreadyExists => {
            let _ = std::fs::remove_file(&temporary);
            if load_anchor(&path)? != anchor {
                return Err(ResidentM2ShadowError::Conflict);
            }
            Ok(())
        }
        Err(_) => {
            let _ = std::fs::remove_file(&temporary);
            Err(ResidentM2ShadowError::Io)
        }
    }
}

fn repair_target_anchor_if_needed(
    root: &Path,
    report_id: &str,
) -> Result<(), ResidentM2ShadowError> {
    let path = report_path(root, report_id);
    match std::fs::symlink_metadata(&path) {
        Ok(_) => {
            let ledger = ensure_ledger(root)?;
            let report = load_report(&path)?;
            if report.report_id != report_id {
                return Err(ResidentM2ShadowError::Corrupt);
            }
            validate_report_basis_binding(root, &report)?;
            let bytes = load_private_bytes(&path)?;
            persist_anchor(root, &ledger.ledger_id, report_id, &sha256_hex(bytes))
        }
        Err(error) if error.kind() == io::ErrorKind::NotFound => Ok(()),
        Err(_) => Err(ResidentM2ShadowError::Io),
    }
}

fn validate_report_basis_binding(
    root: &Path,
    report: &ResidentM2ShadowReport,
) -> Result<u64, ResidentM2ShadowError> {
    let basis = load_bound_resident_owner_evaluation(root, &report.basis_wake_id)
        .map_err(|_| ResidentM2ShadowError::Corrupt)?
        .ok_or(ResidentM2ShadowError::Corrupt)?;
    let basis_bytes = serde_json::to_vec(&basis).map_err(|_| ResidentM2ShadowError::Corrupt)?;
    if basis.label != ResidentOwnerLabel::Useful
        || basis.decision.value_signal != "positive"
        || basis.decision.stop_rule_triggered
        || basis.evaluation_id != report.basis_evaluation_id
        || sha256_hex(basis_bytes) != report.basis_evaluation_sha256
        || basis.recorded_at_unix_ms > report.candidate.evaluated_at_unix_ms
    {
        return Err(ResidentM2ShadowError::Corrupt);
    }
    Ok(basis.recorded_at_unix_ms)
}

fn load_history(root: &Path) -> Result<Vec<ResidentM2ShadowReport>, ResidentM2ShadowError> {
    let directory = shadow_directory(root);
    let anchors = anchor_directory(root);
    let metadata = match std::fs::symlink_metadata(&directory) {
        Ok(metadata) => metadata,
        Err(error) if error.kind() == io::ErrorKind::NotFound => {
            return match std::fs::symlink_metadata(&anchors) {
                Err(anchor_error) if anchor_error.kind() == io::ErrorKind::NotFound => {
                    Ok(Vec::new())
                }
                _ => Err(ResidentM2ShadowError::Corrupt),
            };
        }
        Err(_) => return Err(ResidentM2ShadowError::Io),
    };
    if !metadata.file_type().is_dir() || metadata.mode() & 0o777 != 0o700 {
        return Err(ResidentM2ShadowError::Corrupt);
    }
    let ledger = load_ledger(root)?;
    let anchor_metadata =
        std::fs::symlink_metadata(&anchors).map_err(|_| ResidentM2ShadowError::Corrupt)?;
    if !anchor_metadata.file_type().is_dir() || anchor_metadata.mode() & 0o777 != 0o700 {
        return Err(ResidentM2ShadowError::Corrupt);
    }
    let mut anchor_map = BTreeMap::new();
    for entry in std::fs::read_dir(&anchors).map_err(|_| ResidentM2ShadowError::Io)? {
        let entry = entry.map_err(|_| ResidentM2ShadowError::Io)?;
        let file_name = entry.file_name();
        let file_name = file_name.to_str().ok_or(ResidentM2ShadowError::Corrupt)?;
        if !file_name.starts_with("shadow-") || !file_name.ends_with(".json") {
            return Err(ResidentM2ShadowError::Corrupt);
        }
        let anchor = load_anchor(&entry.path())?;
        if anchor.ledger_id != ledger.ledger_id
            || file_name != format!("{}.json", anchor.report_id)
            || anchor_map
                .insert(anchor.report_id.clone(), anchor)
                .is_some()
        {
            return Err(ResidentM2ShadowError::Corrupt);
        }
    }
    let mut reports = Vec::new();
    for entry in std::fs::read_dir(&directory).map_err(|_| ResidentM2ShadowError::Io)? {
        let entry = entry.map_err(|_| ResidentM2ShadowError::Io)?;
        let file_name = entry.file_name();
        let file_name = file_name.to_str().ok_or(ResidentM2ShadowError::Corrupt)?;
        if !file_name.starts_with("shadow-") || !file_name.ends_with(".json") {
            return Err(ResidentM2ShadowError::Corrupt);
        }
        let bytes = load_private_bytes(&entry.path())?;
        let report: ResidentM2ShadowReport =
            serde_json::from_slice(&bytes).map_err(|_| ResidentM2ShadowError::Corrupt)?;
        validate_report(&report)?;
        if file_name != format!("{}.json", report.report_id) {
            return Err(ResidentM2ShadowError::Corrupt);
        }
        let anchor = anchor_map
            .remove(&report.report_id)
            .ok_or(ResidentM2ShadowError::Corrupt)?;
        if anchor.report_sha256 != sha256_hex(&bytes) {
            return Err(ResidentM2ShadowError::Corrupt);
        }
        validate_report_basis_binding(root, &report)?;
        reports.push(report);
    }
    if !anchor_map.is_empty() {
        return Err(ResidentM2ShadowError::Corrupt);
    }
    Ok(reports)
}

fn ensure_no_later_stop_evaluation(
    root: &Path,
    basis_recorded_at_unix_ms: u64,
) -> Result<(), ResidentM2ShadowError> {
    let directory = root.join("evaluations");
    let metadata =
        std::fs::symlink_metadata(&directory).map_err(|_| ResidentM2ShadowError::Corrupt)?;
    if !metadata.file_type().is_dir() || metadata.mode() & 0o777 != 0o700 {
        return Err(ResidentM2ShadowError::Corrupt);
    }
    for entry in std::fs::read_dir(&directory).map_err(|_| ResidentM2ShadowError::Io)? {
        let entry = entry.map_err(|_| ResidentM2ShadowError::Io)?;
        let file_name = entry.file_name();
        let file_name = file_name.to_str().ok_or(ResidentM2ShadowError::Corrupt)?;
        let wake_id = file_name
            .strip_suffix(".json")
            .filter(|wake_id| validate_identifier(wake_id))
            .ok_or(ResidentM2ShadowError::Corrupt)?;
        let evaluation = load_bound_resident_owner_evaluation(root, wake_id)
            .map_err(|_| ResidentM2ShadowError::Corrupt)?
            .ok_or(ResidentM2ShadowError::Corrupt)?;
        if evaluation.recorded_at_unix_ms >= basis_recorded_at_unix_ms
            && matches!(
                evaluation.label,
                ResidentOwnerLabel::Distracting | ResidentOwnerLabel::Harmful
            )
        {
            return Err(ResidentM2ShadowError::StopLabelActive);
        }
    }
    Ok(())
}

fn add_reason(reasons: &mut Vec<String>, reason: &str) {
    if !reasons.iter().any(|existing| existing == reason) {
        reasons.push(reason.to_string());
    }
}

fn evaluate_candidate(
    candidate: &ResidentM2ShadowCandidate,
    history: &[ResidentM2ShadowReport],
) -> ResidentM2ShadowDecision {
    let policy = frozen_policy();
    let now_secs = candidate.evaluated_at_unix_ms / MILLIS_PER_SECOND;
    let observed_secs = candidate.observed_at_unix_ms / MILLIS_PER_SECOND;
    let age_secs = now_secs.saturating_sub(observed_secs);
    let mut reasons = Vec::new();

    if candidate.evidence_status != ResidentM2ShadowEvidenceStatus::Verified {
        add_reason(&mut reasons, "evidence_not_verified");
    }
    match candidate.trigger_kind {
        ResidentM2ShadowTriggerKind::CommitmentDue => {
            if candidate
                .due_at_unix_ms
                .is_some_and(|due| due > candidate.evaluated_at_unix_ms)
            {
                add_reason(&mut reasons, "commitment_not_due");
            }
        }
        ResidentM2ShadowTriggerKind::Recovery => {
            if age_secs > policy.recovery_freshness_secs {
                add_reason(&mut reasons, "recovery_signal_stale");
            }
        }
        ResidentM2ShadowTriggerKind::Failure => {
            if age_secs > policy.failure_freshness_secs {
                add_reason(&mut reasons, "failure_signal_stale");
            }
            if candidate.severity == ResidentM2ShadowSeverity::Info {
                add_reason(&mut reasons, "failure_below_warning");
            }
        }
    }
    match candidate.foreground_state {
        ResidentM2ShadowForegroundState::Active => {
            add_reason(&mut reasons, "foreground_session_active")
        }
        ResidentM2ShadowForegroundState::Unknown => {
            add_reason(&mut reasons, "foreground_state_unknown")
        }
        ResidentM2ShadowForegroundState::Inactive => {}
    }
    let local_minute = local_minute_of_day(candidate);
    if local_minute >= policy.quiet_start_local_minute
        || local_minute < policy.quiet_end_local_minute
    {
        add_reason(&mut reasons, "quiet_hours");
    }

    let mut projected_today = 0_u16;
    for prior in history.iter().filter(|prior| {
        prior.decision.would_wake
            && prior.candidate.evaluated_at_unix_ms <= candidate.evaluated_at_unix_ms
    }) {
        let elapsed_secs =
            now_secs.saturating_sub(prior.candidate.evaluated_at_unix_ms / MILLIS_PER_SECOND);
        if prior.candidate.trigger_kind == candidate.trigger_kind
            && prior.candidate.signal_sha256 == candidate.signal_sha256
            && elapsed_secs < policy.dedup_horizon_secs
        {
            add_reason(&mut reasons, "duplicate_signal_24h");
        }
        if elapsed_secs < policy.minimum_interval_secs {
            add_reason(&mut reasons, "minimum_interval_6h");
        }
        if local_seconds(
            prior.candidate.evaluated_at_unix_ms,
            candidate.utc_offset_minutes,
        )
        .div_euclid(SECONDS_PER_DAY)
            == local_day(candidate)
        {
            projected_today = projected_today.saturating_add(1);
        }
    }
    if projected_today >= policy.max_projected_wakes_per_local_day {
        add_reason(&mut reasons, "daily_budget_2_exhausted");
    }

    let would_wake = reasons.is_empty();
    ResidentM2ShadowDecision {
        would_wake,
        suppression_reasons: reasons,
        projected_provider_calls: u8::from(would_wake),
        projected_provider_timeout_secs: if would_wake {
            policy.hypothetical_provider_timeout_secs
        } else {
            0
        },
        actual_provider_calls: 0,
        actual_wakes_created: 0,
    }
}

fn persist_report(
    root: &Path,
    report: &ResidentM2ShadowReport,
) -> Result<ShadowWriteStatus, ResidentM2ShadowError> {
    let ledger = ensure_ledger(root)?;
    let directory = shadow_directory(root);
    ensure_private_directory(&directory)?;
    let path = report_path(root, &report.report_id);
    let temporary = directory.join(format!(".{}.{}.tmp", report.report_id, Uuid::new_v4()));
    let bytes = serde_json::to_vec(report).map_err(|_| ResidentM2ShadowError::Corrupt)?;
    let mut file = OpenOptions::new()
        .write(true)
        .create_new(true)
        .mode(0o600)
        .custom_flags(libc::O_CLOEXEC | libc::O_NOFOLLOW)
        .open(&temporary)
        .map_err(|_| ResidentM2ShadowError::Io)?;
    if file
        .write_all(&bytes)
        .and_then(|_| file.sync_all())
        .is_err()
    {
        let _ = std::fs::remove_file(&temporary);
        return Err(ResidentM2ShadowError::Io);
    }
    drop(file);
    let status = match std::fs::hard_link(&temporary, &path) {
        Ok(()) => {
            std::fs::remove_file(&temporary).map_err(|_| ResidentM2ShadowError::Io)?;
            sync_directory(&directory)?;
            ShadowWriteStatus::Recorded
        }
        Err(error) if error.kind() == io::ErrorKind::AlreadyExists => {
            let _ = std::fs::remove_file(&temporary);
            let existing = load_report(&path)?;
            if existing != *report {
                return Err(ResidentM2ShadowError::Conflict);
            }
            ShadowWriteStatus::AlreadyRecorded
        }
        Err(_) => {
            let _ = std::fs::remove_file(&temporary);
            return Err(ResidentM2ShadowError::Io);
        }
    };
    let persisted_bytes = load_private_bytes(&path)?;
    persist_anchor(
        root,
        &ledger.ledger_id,
        &report.report_id,
        &sha256_hex(persisted_bytes),
    )?;
    Ok(status)
}

/// Evaluate one content-hashed trigger under the frozen M2 shadow policy.
///
/// Preview is the default. `record=true` stores only the typed hashes, policy,
/// and decision in a private receipt; neither path invokes the cognition
/// provider or creates a wake journal record.
pub fn evaluate_resident_m2_shadow(options: ResidentM2ShadowOptions) -> Result<Value> {
    let options = ResidentM2ShadowOptions {
        basis_wake_id: options.basis_wake_id.trim().to_string(),
        signal_sha256: options.signal_sha256.trim().to_string(),
        evidence_sha256: options.evidence_sha256.trim().to_string(),
        ..options
    };
    if !validate_identifier(&options.basis_wake_id)
        || !options.journal_root.is_absolute()
        || !options.journal_root.is_dir()
    {
        bail!(ResidentM2ShadowError::InvalidConfiguration);
    }
    let candidate = candidate_from_options(&options);
    validate_candidate(&candidate)?;

    let _lease = if options.record {
        Some(
            ResidentSubjectLease::acquire(&options.journal_root)
                .map_err(|error| anyhow!(error))
                .context("acquire resident subject writer lease for M2 shadow report")?,
        )
    } else {
        None
    };
    let basis = load_bound_resident_owner_evaluation(&options.journal_root, &options.basis_wake_id)
        .map_err(|error| anyhow!(error))?
        .ok_or_else(|| anyhow!(ResidentM2ShadowError::UsefulOwnerBasisRequired))?;
    if basis.label != ResidentOwnerLabel::Useful
        || basis.decision.value_signal != "positive"
        || basis.decision.stop_rule_triggered
        || candidate.evaluated_at_unix_ms < basis.recorded_at_unix_ms
    {
        bail!(ResidentM2ShadowError::UsefulOwnerBasisRequired);
    }
    ensure_no_later_stop_evaluation(&options.journal_root, basis.recorded_at_unix_ms)
        .map_err(|error| anyhow!(error))?;
    let basis_bytes =
        serde_json::to_vec(&basis).map_err(|_| anyhow!(ResidentM2ShadowError::Corrupt))?;
    let basis_evaluation_sha256 = sha256_hex(&basis_bytes);
    let report_id = report_id(&basis.evaluation_id, &candidate)?;
    if options.record {
        repair_target_anchor_if_needed(&options.journal_root, &report_id)
            .map_err(|error| anyhow!(error))?;
    }
    let history = load_history(&options.journal_root)
        .map_err(|error| anyhow!(error))?
        .into_iter()
        .filter(|prior| prior.report_id != report_id)
        .collect::<Vec<_>>();
    let decision = evaluate_candidate(&candidate, &history);
    let report = ResidentM2ShadowReport {
        schema_version: RESIDENT_M2_SHADOW_SCHEMA_V0.to_string(),
        report_id,
        subject_id: RESIDENT_SUBJECT_ID.to_string(),
        basis_wake_id: options.basis_wake_id,
        basis_evaluation_id: basis.evaluation_id,
        basis_evaluation_sha256,
        candidate,
        policy: frozen_policy(),
        decision,
        boundary: boundary(),
    };
    validate_report(&report).map_err(|error| anyhow!(error))?;

    if options.record {
        let status =
            persist_report(&options.journal_root, &report).map_err(|error| anyhow!(error))?;
        let persisted = load_report(&report_path(&options.journal_root, &report.report_id))
            .map_err(|error| anyhow!(error))?;
        Ok(packet(status.as_str(), persisted))
    } else {
        Ok(packet("preview", report))
    }
}

fn classified_report_ids(values: Vec<String>) -> Result<BTreeSet<String>, ResidentM2ShadowError> {
    let mut ids = BTreeSet::new();
    for value in values {
        let value = value.trim().to_string();
        if !value.starts_with("shadow-") || !validate_identifier(&value) || !ids.insert(value) {
            return Err(ResidentM2ShadowError::InvalidConfiguration);
        }
    }
    Ok(ids)
}

/// Build a read-only evidence packet over private M2 shadow reports.
///
/// The caller explicitly classifies report IDs as natural real-task evidence
/// or mechanics-only evidence for this invocation. Those classifications are
/// neither persisted nor authenticated. Even a ready packet admits only a
/// separate owner review of a candidate-source design; it never admits M2.
pub fn review_resident_m2_shadow(options: ResidentM2ShadowReviewOptions) -> Result<Value> {
    if !options.journal_root.is_absolute() || !options.journal_root.is_dir() {
        bail!(ResidentM2ShadowError::InvalidConfiguration);
    }
    let natural_ids =
        classified_report_ids(options.natural_report_ids).map_err(|error| anyhow!(error))?;
    let mechanics_ids =
        classified_report_ids(options.mechanics_report_ids).map_err(|error| anyhow!(error))?;
    if natural_ids.iter().any(|id| mechanics_ids.contains(id)) {
        bail!(ResidentM2ShadowError::InvalidConfiguration);
    }

    let mut reports = load_history(&options.journal_root).map_err(|error| anyhow!(error))?;
    let ledger_id = if reports.is_empty() {
        None
    } else {
        Some(
            load_ledger(&options.journal_root)
                .map_err(|error| anyhow!(error))?
                .ledger_id,
        )
    };
    reports.sort_by(|left, right| {
        left.candidate
            .evaluated_at_unix_ms
            .cmp(&right.candidate.evaluated_at_unix_ms)
            .then_with(|| left.report_id.cmp(&right.report_id))
    });
    let report_ids = reports
        .iter()
        .map(|report| report.report_id.clone())
        .collect::<BTreeSet<_>>();
    if natural_ids
        .iter()
        .chain(mechanics_ids.iter())
        .any(|id| !report_ids.contains(id))
    {
        bail!(ResidentM2ShadowError::InvalidConfiguration);
    }

    let unclassified_ids = report_ids
        .difference(&natural_ids)
        .filter(|id| !mechanics_ids.contains(*id))
        .cloned()
        .collect::<Vec<_>>();
    let natural_reports = reports
        .iter()
        .filter(|report| natural_ids.contains(&report.report_id))
        .collect::<Vec<_>>();

    let mut all_trigger_counts = BTreeMap::<String, usize>::new();
    let mut natural_trigger_counts = BTreeMap::<String, usize>::new();
    let mut natural_suppression_reason_counts = BTreeMap::<String, usize>::new();
    let mut actual_provider_calls = 0_u64;
    let mut actual_wakes_created = 0_u64;
    for report in &reports {
        *all_trigger_counts
            .entry(report.candidate.trigger_kind.as_str().to_string())
            .or_default() += 1;
        actual_provider_calls =
            actual_provider_calls.saturating_add(u64::from(report.decision.actual_provider_calls));
        actual_wakes_created =
            actual_wakes_created.saturating_add(u64::from(report.decision.actual_wakes_created));
    }
    let mut natural_would_wake_count = 0_usize;
    let mut natural_suppressed_count = 0_usize;
    for report in &natural_reports {
        *natural_trigger_counts
            .entry(report.candidate.trigger_kind.as_str().to_string())
            .or_default() += 1;
        if report.decision.would_wake {
            natural_would_wake_count += 1;
        } else {
            natural_suppressed_count += 1;
            for reason in &report.decision.suppression_reasons {
                *natural_suppression_reason_counts
                    .entry(reason.clone())
                    .or_default() += 1;
            }
        }
    }

    let mut stop_label_active = false;
    let basis_times = reports
        .iter()
        .map(|report| validate_report_basis_binding(&options.journal_root, report))
        .collect::<Result<BTreeSet<_>, _>>()
        .map_err(|error| anyhow!(error))?;
    for basis_time in basis_times {
        match ensure_no_later_stop_evaluation(&options.journal_root, basis_time) {
            Ok(()) => {}
            Err(ResidentM2ShadowError::StopLabelActive) => stop_label_active = true,
            Err(error) => return Err(anyhow!(error)),
        }
    }

    let classifications_complete = unclassified_ids.is_empty();
    let enough_natural_reports = natural_reports.len() >= MIN_NATURAL_REPORTS_FOR_OWNER_REVIEW;
    let enough_natural_trigger_kinds =
        natural_trigger_counts.len() >= MIN_NATURAL_TRIGGER_KINDS_FOR_OWNER_REVIEW;
    let includes_natural_would_wake = natural_would_wake_count > 0;
    let includes_natural_suppression = natural_suppressed_count > 0;
    let safe_boundaries = reports.iter().all(|report| report.boundary == boundary())
        && actual_provider_calls == 0
        && actual_wakes_created == 0;
    let ready_for_owner_review = classifications_complete
        && enough_natural_reports
        && enough_natural_trigger_kinds
        && includes_natural_would_wake
        && includes_natural_suppression
        && safe_boundaries
        && !stop_label_active;

    let mut block_reasons = Vec::new();
    if reports.is_empty() {
        block_reasons.push("no_shadow_reports");
    }
    if !classifications_complete {
        block_reasons.push("report_classification_incomplete");
    }
    if !enough_natural_reports {
        block_reasons.push("fewer_than_3_natural_reports");
    }
    if !enough_natural_trigger_kinds {
        block_reasons.push("fewer_than_2_natural_trigger_kinds");
    }
    if !includes_natural_would_wake {
        block_reasons.push("missing_natural_would_wake");
    }
    if !includes_natural_suppression {
        block_reasons.push("missing_natural_suppression");
    }
    if !safe_boundaries {
        block_reasons.push("unsafe_shadow_boundary");
    }
    if stop_label_active {
        block_reasons.push("owner_stop_label_active");
    }

    let earliest_evaluated_at_unix_ms = reports
        .first()
        .map(|report| report.candidate.evaluated_at_unix_ms);
    let latest_evaluated_at_unix_ms = reports
        .last()
        .map(|report| report.candidate.evaluated_at_unix_ms);
    let status = if stop_label_active {
        "stopped_by_owner_label"
    } else if ready_for_owner_review {
        "ready_for_owner_review"
    } else {
        "collecting"
    };
    let recommended_next_gate = if stop_label_active {
        "stop_shadow_collection_and_prepare_disable_or_rollback_review"
    } else if ready_for_owner_review {
        "owner_review_of_candidate_source_design_only"
    } else {
        "continue_bounded_manual_shadow_collection"
    };

    Ok(json!({
        "schema": RESIDENT_M2_SHADOW_REVIEW_SCHEMA_V0,
        "status": status,
        "evidence": {
            "ledger_id": ledger_id,
            "report_count": reports.len(),
            "natural_report_count": natural_reports.len(),
            "mechanics_report_count": mechanics_ids.len(),
            "unclassified_report_count": unclassified_ids.len(),
            "natural_report_ids": natural_ids,
            "mechanics_report_ids": mechanics_ids,
            "unclassified_report_ids": unclassified_ids,
            "all_trigger_counts": all_trigger_counts,
            "natural_trigger_counts": natural_trigger_counts,
            "natural_would_wake_count": natural_would_wake_count,
            "natural_suppressed_count": natural_suppressed_count,
            "natural_suppression_reason_counts": natural_suppression_reason_counts,
            "earliest_evaluated_at_unix_ms": earliest_evaluated_at_unix_ms,
            "latest_evaluated_at_unix_ms": latest_evaluated_at_unix_ms,
            "basis_binding_valid_count": reports.len(),
            "safe_boundary_report_count": reports.len(),
            "actual_provider_calls": actual_provider_calls,
            "actual_wakes_created": actual_wakes_created
        },
        "criteria": {
            "classifications_complete": classifications_complete,
            "minimum_natural_reports": MIN_NATURAL_REPORTS_FOR_OWNER_REVIEW,
            "enough_natural_reports": enough_natural_reports,
            "minimum_natural_trigger_kinds": MIN_NATURAL_TRIGGER_KINDS_FOR_OWNER_REVIEW,
            "enough_natural_trigger_kinds": enough_natural_trigger_kinds,
            "includes_natural_would_wake": includes_natural_would_wake,
            "includes_natural_suppression": includes_natural_suppression,
            "safe_boundaries": safe_boundaries,
            "owner_stop_label_active": stop_label_active,
            "ready_for_owner_review": ready_for_owner_review,
            "block_reasons": block_reasons
        },
        "decision": {
            "recommended_next_gate": recommended_next_gate,
            "m2_admitted": false
        },
        "boundary": {
            "read_only": true,
            "report_files_modified": false,
            "classification_persisted": false,
            "classification_source": "explicit_local_cli_argument",
            "classification_cryptographically_authenticated": false,
            "provider_invoked": false,
            "creates_cognitive_wake": false,
            "scheduler_installed": false,
            "executes_action": false,
            "automatic_runtime_change": false,
            "automatic_memory_promotion": false,
            "m2_admitted": false
        }
    }))
}

fn packet(status: &str, report: ResidentM2ShadowReport) -> Value {
    json!({
        "schema": RESIDENT_M2_SHADOW_SCHEMA_V0,
        "status": status,
        "basis_binding": {
            "owner_label": "useful",
            "owner_evaluation_bound": true,
            "owner_identity_cryptographically_authenticated": false
        },
        "report": report
    })
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::resident_owner_evaluation::{
        record_resident_owner_evaluation, ResidentOwnerEvaluationOptions,
    };
    use crate::resident_wake_journal::ResidentWakeReservation;
    use std::fs;

    const DAY_MS: u64 = 86_400_000;

    fn owner_evaluation(root: &Path, wake_id: &str, label: ResidentOwnerLabel) -> u64 {
        let mut wake = ResidentWakeReservation::reserve(
            root,
            wake_id,
            &format!("episode-{wake_id}"),
            RESIDENT_SUBJECT_ID,
            100,
        )
        .unwrap();
        wake.complete(200, "respond", &"a".repeat(64), &"b".repeat(64))
            .unwrap();
        let mut evaluation = ResidentOwnerEvaluationOptions::new(wake_id, label);
        evaluation.journal_root = root.to_path_buf();
        record_resident_owner_evaluation(evaluation).unwrap()["receipt"]["recorded_at_unix_ms"]
            .as_u64()
            .unwrap()
    }

    fn useful_basis(root: &Path, wake_id: &str) -> u64 {
        owner_evaluation(root, wake_id, ResidentOwnerLabel::Useful)
    }

    fn options(
        root: &Path,
        kind: ResidentM2ShadowTriggerKind,
        signal_byte: char,
        evaluated_at_unix_ms: u64,
    ) -> ResidentM2ShadowOptions {
        let mut options = ResidentM2ShadowOptions::new(
            "wake-shadow-basis",
            kind,
            signal_byte.to_string().repeat(64),
            "e".repeat(64),
            evaluated_at_unix_ms - 60_000,
            0,
        );
        options.journal_root = root.to_path_buf();
        options.evidence_status = ResidentM2ShadowEvidenceStatus::Verified;
        options.foreground_state = ResidentM2ShadowForegroundState::Inactive;
        options.evaluated_at_unix_ms = evaluated_at_unix_ms;
        options
    }

    fn daytime(day: u64, hour: u64) -> u64 {
        day * DAY_MS + hour * 3_600_000
    }

    fn day_after(timestamp_unix_ms: u64) -> u64 {
        timestamp_unix_ms / DAY_MS + 2
    }

    fn record_report(mut options: ResidentM2ShadowOptions) -> String {
        options.record = true;
        evaluate_resident_m2_shadow(options).unwrap()["report"]["report_id"]
            .as_str()
            .unwrap()
            .to_string()
    }

    fn review_options(
        root: &Path,
        natural_report_ids: Vec<String>,
        mechanics_report_ids: Vec<String>,
    ) -> ResidentM2ShadowReviewOptions {
        ResidentM2ShadowReviewOptions {
            natural_report_ids,
            mechanics_report_ids,
            journal_root: root.to_path_buf(),
        }
    }

    #[test]
    fn preview_is_state_free_and_never_invokes_or_wakes() {
        let root = tempfile::tempdir().unwrap();
        let root = root.path().canonicalize().unwrap();
        let basis_at = useful_basis(&root, "wake-shadow-basis");
        let packet = evaluate_resident_m2_shadow(options(
            &root,
            ResidentM2ShadowTriggerKind::Recovery,
            '1',
            daytime(day_after(basis_at), 12),
        ))
        .unwrap();
        assert_eq!(packet["status"], "preview");
        assert_eq!(packet["report"]["decision"]["would_wake"], true);
        assert_eq!(packet["report"]["decision"]["actual_provider_calls"], 0);
        assert_eq!(packet["report"]["decision"]["actual_wakes_created"], 0);
        assert!(!shadow_directory(&root).exists());
    }

    #[test]
    fn useful_owner_basis_is_required() {
        let root = tempfile::tempdir().unwrap();
        let root = root.path().canonicalize().unwrap();
        fs::create_dir_all(&root).unwrap();
        let error = evaluate_resident_m2_shadow(options(
            &root,
            ResidentM2ShadowTriggerKind::Recovery,
            '2',
            daytime(10, 12),
        ))
        .unwrap_err();
        assert!(error
            .to_string()
            .contains("resident_m2_shadow_useful_owner_basis_required"));
    }

    #[test]
    fn due_evidence_foreground_and_quiet_hours_suppress_deterministically() {
        let root = tempfile::tempdir().unwrap();
        let root = root.path().canonicalize().unwrap();
        let basis_at = useful_basis(&root, "wake-shadow-basis");

        let day = day_after(basis_at);
        let at = daytime(day, 12);
        let mut due = options(&root, ResidentM2ShadowTriggerKind::CommitmentDue, '3', at);
        due.due_at_unix_ms = Some(at - 1);
        let eligible = evaluate_resident_m2_shadow(due.clone()).unwrap();
        assert_eq!(eligible["report"]["decision"]["would_wake"], true);

        due.due_at_unix_ms = Some(at + 1);
        due.evidence_status = ResidentM2ShadowEvidenceStatus::Unknown;
        due.foreground_state = ResidentM2ShadowForegroundState::Active;
        due.evaluated_at_unix_ms = daytime(day, 23);
        due.due_at_unix_ms = Some(due.evaluated_at_unix_ms + 1);
        let suppressed = evaluate_resident_m2_shadow(due).unwrap();
        let reasons = suppressed["report"]["decision"]["suppression_reasons"]
            .as_array()
            .unwrap();
        for reason in [
            "evidence_not_verified",
            "commitment_not_due",
            "foreground_session_active",
            "quiet_hours",
        ] {
            assert!(reasons.iter().any(|value| value == reason));
        }
    }

    #[test]
    fn failure_requires_fresh_warning_or_critical_signal() {
        let root = tempfile::tempdir().unwrap();
        let root = root.path().canonicalize().unwrap();
        let basis_at = useful_basis(&root, "wake-shadow-basis");
        let at = daytime(day_after(basis_at), 12);
        let mut failure = options(&root, ResidentM2ShadowTriggerKind::Failure, '4', at);
        let info = evaluate_resident_m2_shadow(failure.clone()).unwrap();
        assert_eq!(info["report"]["decision"]["would_wake"], false);
        failure.severity = ResidentM2ShadowSeverity::Warning;
        let warning = evaluate_resident_m2_shadow(failure.clone()).unwrap();
        assert_eq!(warning["report"]["decision"]["would_wake"], true);
        failure.observed_at_unix_ms = at - 3_600_001;
        let stale = evaluate_resident_m2_shadow(failure).unwrap();
        assert_eq!(stale["report"]["decision"]["would_wake"], false);
    }

    #[test]
    fn private_history_enforces_dedup_interval_and_daily_budget() {
        let root = tempfile::tempdir().unwrap();
        let root = root.path().canonicalize().unwrap();
        let basis_at = useful_basis(&root, "wake-shadow-basis");
        let base = daytime(day_after(basis_at), 8);

        let mut first = options(&root, ResidentM2ShadowTriggerKind::Recovery, '5', base);
        first.record = true;
        let recorded = evaluate_resident_m2_shadow(first.clone()).unwrap();
        assert_eq!(recorded["status"], "recorded");
        let replay = evaluate_resident_m2_shadow(first).unwrap();
        assert_eq!(replay["status"], "already_recorded");

        let mut duplicate = options(
            &root,
            ResidentM2ShadowTriggerKind::Recovery,
            '5',
            base + 7 * 3_600_000,
        );
        duplicate.record = true;
        let duplicate = evaluate_resident_m2_shadow(duplicate).unwrap();
        assert_eq!(duplicate["report"]["decision"]["would_wake"], false);
        assert!(duplicate["report"]["decision"]["suppression_reasons"]
            .as_array()
            .unwrap()
            .iter()
            .any(|value| value == "duplicate_signal_24h"));

        let mut too_soon = options(
            &root,
            ResidentM2ShadowTriggerKind::Recovery,
            '6',
            base + 3_600_000,
        );
        too_soon.record = true;
        let too_soon = evaluate_resident_m2_shadow(too_soon).unwrap();
        assert!(too_soon["report"]["decision"]["suppression_reasons"]
            .as_array()
            .unwrap()
            .iter()
            .any(|value| value == "minimum_interval_6h"));

        let mut second = options(
            &root,
            ResidentM2ShadowTriggerKind::Recovery,
            '7',
            base + 7 * 3_600_000,
        );
        second.record = true;
        let second = evaluate_resident_m2_shadow(second).unwrap();
        assert_eq!(second["report"]["decision"]["would_wake"], true);

        let third = options(
            &root,
            ResidentM2ShadowTriggerKind::Recovery,
            '8',
            base + 13 * 3_600_000,
        );
        let third = evaluate_resident_m2_shadow(third).unwrap();
        assert!(third["report"]["decision"]["suppression_reasons"]
            .as_array()
            .unwrap()
            .iter()
            .any(|value| value == "daily_budget_2_exhausted"));

        let directory = shadow_directory(&root);
        assert_eq!(
            fs::metadata(&directory).unwrap().permissions().mode() & 0o777,
            0o700
        );
        for entry in fs::read_dir(&directory).unwrap() {
            let entry = entry.unwrap();
            assert_eq!(
                entry.metadata().unwrap().permissions().mode() & 0o777,
                0o600
            );
            assert_eq!(entry.metadata().unwrap().nlink(), 1);
            let raw = fs::read_to_string(entry.path()).unwrap();
            assert!(!raw.contains("owner prompt"));
        }
    }

    #[test]
    fn later_distracting_or_harmful_owner_label_stops_shadow_lane() {
        let root = tempfile::tempdir().unwrap();
        let root = root.path().canonicalize().unwrap();
        let basis_at = useful_basis(&root, "wake-shadow-basis");
        owner_evaluation(&root, "wake-shadow-stop", ResidentOwnerLabel::Distracting);

        let error = evaluate_resident_m2_shadow(options(
            &root,
            ResidentM2ShadowTriggerKind::Recovery,
            '9',
            daytime(day_after(basis_at), 12),
        ))
        .unwrap_err();
        assert!(error
            .to_string()
            .contains("resident_m2_shadow_stop_label_active"));
    }

    #[test]
    fn review_classifies_mechanics_sample_without_writing_or_admitting_m2() {
        let root = tempfile::tempdir().unwrap();
        let root = root.path().canonicalize().unwrap();
        let basis_at = useful_basis(&root, "wake-shadow-basis");
        let report_id = record_report(options(
            &root,
            ResidentM2ShadowTriggerKind::Recovery,
            'a',
            daytime(day_after(basis_at), 12),
        ));
        let path = report_path(&root, &report_id);
        let before = fs::read(&path).unwrap();

        let packet =
            review_resident_m2_shadow(review_options(&root, Vec::new(), vec![report_id])).unwrap();
        assert_eq!(packet["status"], "collecting");
        assert!(packet["evidence"]["ledger_id"]
            .as_str()
            .is_some_and(|value| value.starts_with("shadow-ledger-")));
        assert_eq!(packet["evidence"]["report_count"], 1);
        assert_eq!(packet["evidence"]["natural_report_count"], 0);
        assert_eq!(packet["evidence"]["mechanics_report_count"], 1);
        assert_eq!(packet["criteria"]["classifications_complete"], true);
        assert_eq!(packet["criteria"]["ready_for_owner_review"], false);
        assert_eq!(packet["decision"]["m2_admitted"], false);
        assert_eq!(packet["boundary"]["read_only"], true);
        assert_eq!(packet["boundary"]["report_files_modified"], false);
        assert_eq!(packet["boundary"]["provider_invoked"], false);
        assert_eq!(packet["boundary"]["creates_cognitive_wake"], false);
        assert_eq!(fs::read(path).unwrap(), before);
    }

    #[test]
    fn recorded_report_has_separate_hash_anchor() {
        let root = tempfile::tempdir().unwrap();
        let root = root.path().canonicalize().unwrap();
        let basis_at = useful_basis(&root, "wake-shadow-basis");
        let report_id = record_report(options(
            &root,
            ResidentM2ShadowTriggerKind::Recovery,
            '0',
            daytime(day_after(basis_at), 12),
        ));
        let report_bytes = fs::read(report_path(&root, &report_id)).unwrap();
        let ledger = load_ledger(&root).unwrap();
        let anchor = load_anchor(&anchor_path(&root, &report_id)).unwrap();
        assert_eq!(anchor.ledger_id, ledger.ledger_id);
        assert_eq!(anchor.report_id, report_id);
        assert_eq!(anchor.report_sha256, sha256_hex(report_bytes));
        assert_eq!(
            fs::metadata(anchor_directory(&root))
                .unwrap()
                .permissions()
                .mode()
                & 0o777,
            0o700
        );
        assert_eq!(
            fs::metadata(anchor_path(&root, &report_id))
                .unwrap()
                .permissions()
                .mode()
                & 0o777,
            0o600
        );
        assert_eq!(
            fs::metadata(ledger_path(&root))
                .unwrap()
                .permissions()
                .mode()
                & 0o777,
            0o600
        );
    }

    #[test]
    fn review_fails_closed_when_report_or_anchor_is_missing_or_mismatched() {
        for damage in ["report", "anchor", "anchor_hash", "ledger", "ledger_id"] {
            let root = tempfile::tempdir().unwrap();
            let root = root.path().canonicalize().unwrap();
            let basis_at = useful_basis(&root, "wake-shadow-basis");
            let report_id = record_report(options(
                &root,
                ResidentM2ShadowTriggerKind::Recovery,
                '1',
                daytime(day_after(basis_at), 12),
            ));
            match damage {
                "report" => fs::remove_file(report_path(&root, &report_id)).unwrap(),
                "anchor" => fs::remove_file(anchor_path(&root, &report_id)).unwrap(),
                "anchor_hash" => {
                    let path = anchor_path(&root, &report_id);
                    let mut anchor = load_anchor(&path).unwrap();
                    anchor.report_sha256 = "0".repeat(64);
                    fs::write(&path, serde_json::to_vec(&anchor).unwrap()).unwrap();
                }
                "ledger" => fs::remove_file(ledger_path(&root)).unwrap(),
                "ledger_id" => {
                    let path = ledger_path(&root);
                    let mut ledger = load_ledger(&root).unwrap();
                    ledger.ledger_id = "shadow-ledger-00000000000000000000000000000000".into();
                    fs::write(&path, serde_json::to_vec(&ledger).unwrap()).unwrap();
                }
                _ => unreachable!(),
            }
            let error =
                review_resident_m2_shadow(review_options(&root, Vec::new(), vec![report_id]))
                    .unwrap_err();
            assert!(
                error.to_string().contains("resident_m2_shadow_corrupt"),
                "damage={damage}: {error}"
            );
        }
    }

    #[test]
    fn exact_record_replay_backfills_legacy_anchor_without_rewriting_report() {
        let root = tempfile::tempdir().unwrap();
        let root = root.path().canonicalize().unwrap();
        let basis_at = useful_basis(&root, "wake-shadow-basis");
        let mut replay = options(
            &root,
            ResidentM2ShadowTriggerKind::Recovery,
            '2',
            daytime(day_after(basis_at), 12),
        );
        replay.record = true;
        let first = evaluate_resident_m2_shadow(replay.clone()).unwrap();
        let report_id = first["report"]["report_id"].as_str().unwrap().to_string();
        let report_path = report_path(&root, &report_id);
        let before = fs::read(&report_path).unwrap();
        fs::remove_file(anchor_path(&root, &report_id)).unwrap();
        fs::remove_dir(anchor_directory(&root)).unwrap();

        let second = evaluate_resident_m2_shadow(replay).unwrap();
        assert_eq!(second["status"], "already_recorded");
        assert_eq!(fs::read(&report_path).unwrap(), before);
        let anchor = load_anchor(&anchor_path(&root, &report_id)).unwrap();
        assert_eq!(anchor.ledger_id, load_ledger(&root).unwrap().ledger_id);
        assert_eq!(anchor.report_sha256, sha256_hex(before));
    }

    #[test]
    fn three_diverse_natural_reports_prepare_owner_review_only() {
        let root = tempfile::tempdir().unwrap();
        let root = root.path().canonicalize().unwrap();
        let basis_at = useful_basis(&root, "wake-shadow-basis");
        let day = day_after(basis_at);

        let first = record_report(options(
            &root,
            ResidentM2ShadowTriggerKind::Recovery,
            'b',
            daytime(day, 8),
        ));
        let mut failure = options(
            &root,
            ResidentM2ShadowTriggerKind::Failure,
            'c',
            daytime(day, 10),
        );
        failure.severity = ResidentM2ShadowSeverity::Warning;
        let second = record_report(failure);
        let mut commitment = options(
            &root,
            ResidentM2ShadowTriggerKind::CommitmentDue,
            'd',
            daytime(day + 1, 9),
        );
        commitment.due_at_unix_ms = Some(commitment.evaluated_at_unix_ms - 1);
        let third = record_report(commitment);

        let packet = review_resident_m2_shadow(review_options(
            &root,
            vec![first, second, third],
            Vec::new(),
        ))
        .unwrap();
        assert_eq!(packet["status"], "ready_for_owner_review");
        assert_eq!(packet["evidence"]["natural_report_count"], 3);
        assert_eq!(packet["evidence"]["natural_would_wake_count"], 2);
        assert_eq!(packet["evidence"]["natural_suppressed_count"], 1);
        assert_eq!(packet["criteria"]["enough_natural_trigger_kinds"], true);
        assert_eq!(packet["criteria"]["ready_for_owner_review"], true);
        assert_eq!(
            packet["decision"]["recommended_next_gate"],
            "owner_review_of_candidate_source_design_only"
        );
        assert_eq!(packet["decision"]["m2_admitted"], false);
    }

    #[test]
    fn review_rejects_unknown_duplicate_or_overlapping_classification() {
        let root = tempfile::tempdir().unwrap();
        let root = root.path().canonicalize().unwrap();
        let basis_at = useful_basis(&root, "wake-shadow-basis");
        let report_id = record_report(options(
            &root,
            ResidentM2ShadowTriggerKind::Recovery,
            'e',
            daytime(day_after(basis_at), 12),
        ));

        for options in [
            review_options(&root, vec!["shadow-not-present".to_string()], Vec::new()),
            review_options(
                &root,
                vec![report_id.clone(), report_id.clone()],
                Vec::new(),
            ),
            review_options(&root, vec![report_id.clone()], vec![report_id.clone()]),
        ] {
            let error = review_resident_m2_shadow(options).unwrap_err();
            assert!(error
                .to_string()
                .contains("resident_m2_shadow_invalid_configuration"));
        }
    }

    #[test]
    fn review_surfaces_later_stop_label_and_never_becomes_ready() {
        let root = tempfile::tempdir().unwrap();
        let root = root.path().canonicalize().unwrap();
        let basis_at = useful_basis(&root, "wake-shadow-basis");
        let report_id = record_report(options(
            &root,
            ResidentM2ShadowTriggerKind::Recovery,
            'f',
            daytime(day_after(basis_at), 12),
        ));
        owner_evaluation(
            &root,
            "wake-shadow-stop-review",
            ResidentOwnerLabel::Harmful,
        );

        let packet =
            review_resident_m2_shadow(review_options(&root, vec![report_id], Vec::new())).unwrap();
        assert_eq!(packet["status"], "stopped_by_owner_label");
        assert_eq!(packet["criteria"]["owner_stop_label_active"], true);
        assert_eq!(packet["criteria"]["ready_for_owner_review"], false);
        assert_eq!(
            packet["decision"]["recommended_next_gate"],
            "stop_shadow_collection_and_prepare_disable_or_rollback_review"
        );
        assert_eq!(packet["decision"]["m2_admitted"], false);
    }

    #[test]
    fn history_with_changed_basis_receipt_cannot_influence_review_or_policy() {
        let root = tempfile::tempdir().unwrap();
        let root = root.path().canonicalize().unwrap();
        let basis_at = useful_basis(&root, "wake-shadow-basis");
        let report_id = record_report(options(
            &root,
            ResidentM2ShadowTriggerKind::Recovery,
            '1',
            daytime(day_after(basis_at), 12),
        ));
        let evaluation_path = root.join("evaluations/wake-shadow-basis.json");
        let mut evaluation: Value =
            serde_json::from_slice(&fs::read(&evaluation_path).unwrap()).unwrap();
        evaluation["recorded_at_unix_ms"] = Value::from(basis_at + 1);
        fs::write(&evaluation_path, serde_json::to_vec(&evaluation).unwrap()).unwrap();

        let error = review_resident_m2_shadow(review_options(&root, vec![report_id], Vec::new()))
            .unwrap_err();
        assert!(error.to_string().contains("resident_m2_shadow_corrupt"));

        let future = options(
            &root,
            ResidentM2ShadowTriggerKind::Recovery,
            '2',
            daytime(day_after(basis_at) + 1, 12),
        );
        let error = evaluate_resident_m2_shadow(future).unwrap_err();
        assert!(error.to_string().contains("resident_m2_shadow_corrupt"));
    }
}
