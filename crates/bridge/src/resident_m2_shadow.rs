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
use std::fs::{File, OpenOptions};
use std::io::{self, Read, Write};
use std::os::unix::fs::{MetadataExt, OpenOptionsExt, PermissionsExt};
use std::path::{Path, PathBuf};
use std::time::{SystemTime, UNIX_EPOCH};
use uuid::Uuid;

pub const RESIDENT_M2_SHADOW_SCHEMA_V0: &str = "agent_bridge.resident_m2_shadow.v0";
const POLICY_REVISION: u64 = 1;
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

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum ResidentM2ShadowTriggerKind {
    CommitmentDue,
    Recovery,
    Failure,
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

fn report_path(root: &Path, report_id: &str) -> PathBuf {
    shadow_directory(root).join(format!("{report_id}.json"))
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

fn load_history(root: &Path) -> Result<Vec<ResidentM2ShadowReport>, ResidentM2ShadowError> {
    let directory = shadow_directory(root);
    let metadata = match std::fs::symlink_metadata(&directory) {
        Ok(metadata) => metadata,
        Err(error) if error.kind() == io::ErrorKind::NotFound => return Ok(Vec::new()),
        Err(_) => return Err(ResidentM2ShadowError::Io),
    };
    if !metadata.file_type().is_dir() || metadata.mode() & 0o777 != 0o700 {
        return Err(ResidentM2ShadowError::Corrupt);
    }
    let mut reports = Vec::new();
    for entry in std::fs::read_dir(&directory).map_err(|_| ResidentM2ShadowError::Io)? {
        let entry = entry.map_err(|_| ResidentM2ShadowError::Io)?;
        let file_name = entry.file_name();
        let file_name = file_name.to_str().ok_or(ResidentM2ShadowError::Corrupt)?;
        if !file_name.starts_with("shadow-") || !file_name.ends_with(".json") {
            return Err(ResidentM2ShadowError::Corrupt);
        }
        let report = load_report(&entry.path())?;
        if file_name != format!("{}.json", report.report_id) {
            return Err(ResidentM2ShadowError::Corrupt);
        }
        reports.push(report);
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
    match std::fs::hard_link(&temporary, &path) {
        Ok(()) => {
            std::fs::remove_file(&temporary).map_err(|_| ResidentM2ShadowError::Io)?;
            sync_directory(&directory)?;
            Ok(ShadowWriteStatus::Recorded)
        }
        Err(error) if error.kind() == io::ErrorKind::AlreadyExists => {
            let _ = std::fs::remove_file(&temporary);
            let existing = load_report(&path)?;
            if existing != *report {
                return Err(ResidentM2ShadowError::Conflict);
            }
            Ok(ShadowWriteStatus::AlreadyRecorded)
        }
        Err(_) => {
            let _ = std::fs::remove_file(&temporary);
            Err(ResidentM2ShadowError::Io)
        }
    }
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
}
