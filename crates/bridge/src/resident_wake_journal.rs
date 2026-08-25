//! Privacy-minimal, file-backed exactly-once journal for Resident Xiao Shu wakes.
//!
//! The journal stores identifiers, lifecycle state, hashes, and bounded error
//! codes only. It never stores the wake prompt, model transcript, response, or
//! proposed memory contents. `create_new` is the durable idempotency gate: a
//! repeated `wake_id` is refused across process restarts rather than executed a
//! second time.

use serde::{Deserialize, Serialize};
use std::fs::{File, OpenOptions};
use std::io::{self, Write};
use std::os::fd::AsRawFd;
use std::os::unix::fs::{MetadataExt, OpenOptionsExt, PermissionsExt};
use std::path::{Path, PathBuf};
use uuid::Uuid;

pub const RESIDENT_WAKE_JOURNAL_SCHEMA_V0: &str = "agent_bridge.resident_wake_journal.v0";

/// Resolve the permission-capable durable root shared by Resident Xiao Shu
/// sidecars. The wrapper sets `AGENT_BRIDGE_STATE_DIR` on hosts whose data
/// directory cannot preserve private Unix modes; direct callers retain the
/// existing database-parent fallback.
pub fn default_resident_state_root() -> PathBuf {
    resolve_resident_state_root(
        std::env::var_os("AGENT_BRIDGE_STATE_DIR").map(PathBuf::from),
        std::env::var_os("XDG_STATE_HOME").map(PathBuf::from),
        &ab_store::default_db_path(),
    )
}

fn resolve_resident_state_root(
    agent_bridge_state_dir: Option<PathBuf>,
    xdg_state_home: Option<PathBuf>,
    database: &Path,
) -> PathBuf {
    agent_bridge_state_dir
        .or_else(|| xdg_state_home.map(|root| root.join("agent-bridge")))
        .or_else(|| database.parent().map(Path::to_path_buf))
        .unwrap_or_else(|| PathBuf::from("/tmp"))
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum ResidentWakeJournalState {
    Running,
    Completed,
    Failed,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct ResidentWakeJournalRecord {
    pub schema_version: String,
    pub wake_id: String,
    pub cognitive_episode_id: String,
    pub subject_id: String,
    pub state: ResidentWakeJournalState,
    pub started_at_unix_ms: u64,
    pub finished_at_unix_ms: u64,
    pub provider: String,
    pub disposition: String,
    pub final_sha256: String,
    pub execution_receipt_sha256: String,
    pub error_code: String,
    pub child_exit_observed: bool,
    pub advances_continuity: bool,
}

impl ResidentWakeJournalRecord {
    pub fn validate(&self) -> Result<(), ResidentWakeJournalError> {
        if self.schema_version != RESIDENT_WAKE_JOURNAL_SCHEMA_V0 {
            return Err(ResidentWakeJournalError::Corrupt);
        }
        for identifier in [&self.wake_id, &self.cognitive_episode_id, &self.subject_id] {
            validate_identifier(identifier)?;
        }
        if self.started_at_unix_ms == 0
            || self.provider != "codex_cli"
            || self.disposition.chars().count() > 64
            || self.error_code.chars().count() > 128
        {
            return Err(ResidentWakeJournalError::Corrupt);
        }
        match self.state {
            ResidentWakeJournalState::Running => {
                if self.finished_at_unix_ms != 0
                    || !self.disposition.is_empty()
                    || !self.final_sha256.is_empty()
                    || !self.execution_receipt_sha256.is_empty()
                    || !self.error_code.is_empty()
                    || self.child_exit_observed
                    || self.advances_continuity
                {
                    return Err(ResidentWakeJournalError::Corrupt);
                }
            }
            ResidentWakeJournalState::Completed => {
                if self.finished_at_unix_ms < self.started_at_unix_ms
                    || self.disposition.is_empty()
                    || !is_sha256_hex(&self.final_sha256)
                    || !is_sha256_hex(&self.execution_receipt_sha256)
                    || !self.error_code.is_empty()
                    || !self.child_exit_observed
                    || !self.advances_continuity
                {
                    return Err(ResidentWakeJournalError::Corrupt);
                }
            }
            ResidentWakeJournalState::Failed => {
                if self.finished_at_unix_ms < self.started_at_unix_ms
                    || !self.disposition.is_empty()
                    || !self.final_sha256.is_empty()
                    || !self.execution_receipt_sha256.is_empty()
                    || self.error_code.is_empty()
                    || self.advances_continuity
                {
                    return Err(ResidentWakeJournalError::Corrupt);
                }
            }
        }
        Ok(())
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, thiserror::Error)]
pub enum ResidentWakeJournalError {
    #[error("resident_wake_journal_invalid_root")]
    InvalidRoot,
    #[error("resident_wake_journal_invalid_identifier")]
    InvalidIdentifier,
    #[error("resident_wake_duplicate")]
    Duplicate,
    #[error("resident_wake_concurrent")]
    Concurrent,
    #[error("resident_wake_journal_io")]
    Io,
    #[error("resident_wake_journal_corrupt")]
    Corrupt,
    #[error("resident_wake_journal_already_finalized")]
    AlreadyFinalized,
    #[error("resident_wake_journal_invalid_transition")]
    InvalidTransition,
}

#[derive(Debug)]
pub struct ResidentWakeReservation {
    path: PathBuf,
    journal_dir: PathBuf,
    record: ResidentWakeJournalRecord,
    finalized: bool,
}

/// Process-scoped, non-blocking single-writer fence for the resident subject.
///
/// The lease is held across continuity recovery, provider execution, result
/// validation, and receipt commit. This is deliberately wider than the
/// provider's own process lock so two different wake IDs cannot race a stale
/// sleep digest into the ledger.
#[derive(Debug)]
pub struct ResidentSubjectLease(File);

impl ResidentSubjectLease {
    pub fn acquire(root: &Path) -> Result<Self, ResidentWakeJournalError> {
        if !root.is_absolute() {
            return Err(ResidentWakeJournalError::InvalidRoot);
        }
        create_private_directory(root)?;
        let path = root.join("writer.lock");
        let file = OpenOptions::new()
            .read(true)
            .write(true)
            .create(true)
            .mode(0o600)
            .custom_flags(libc::O_CLOEXEC | libc::O_NOFOLLOW)
            .open(path)
            .map_err(|_| ResidentWakeJournalError::Io)?;
        let metadata = file.metadata().map_err(|_| ResidentWakeJournalError::Io)?;
        if !metadata.is_file() || metadata.mode() & 0o777 != 0o600 || metadata.nlink() != 1 {
            return Err(ResidentWakeJournalError::Corrupt);
        }
        let result = unsafe { libc::flock(file.as_raw_fd(), libc::LOCK_EX | libc::LOCK_NB) };
        if result == 0 {
            return Ok(Self(file));
        }
        let error = io::Error::last_os_error();
        if matches!(error.raw_os_error(), Some(code) if code == libc::EAGAIN || code == libc::EWOULDBLOCK)
        {
            Err(ResidentWakeJournalError::Concurrent)
        } else {
            Err(ResidentWakeJournalError::Io)
        }
    }
}

impl Drop for ResidentSubjectLease {
    fn drop(&mut self) {
        let _ = unsafe { libc::flock(self.0.as_raw_fd(), libc::LOCK_UN) };
    }
}

impl ResidentWakeReservation {
    pub fn reserve(
        root: &Path,
        wake_id: &str,
        cognitive_episode_id: &str,
        subject_id: &str,
        started_at_unix_ms: u64,
    ) -> Result<Self, ResidentWakeJournalError> {
        if !root.is_absolute() || started_at_unix_ms == 0 {
            return Err(ResidentWakeJournalError::InvalidRoot);
        }
        validate_identifier(wake_id)?;
        validate_identifier(cognitive_episode_id)?;
        validate_identifier(subject_id)?;
        create_private_directory(root)?;
        let journal_dir = root.join("wakes");
        create_private_directory(&journal_dir)?;
        let path = journal_dir.join(format!("{wake_id}.json"));
        let record = ResidentWakeJournalRecord {
            schema_version: RESIDENT_WAKE_JOURNAL_SCHEMA_V0.to_string(),
            wake_id: wake_id.to_string(),
            cognitive_episode_id: cognitive_episode_id.to_string(),
            subject_id: subject_id.to_string(),
            state: ResidentWakeJournalState::Running,
            started_at_unix_ms,
            finished_at_unix_ms: 0,
            provider: "codex_cli".to_string(),
            disposition: String::new(),
            final_sha256: String::new(),
            execution_receipt_sha256: String::new(),
            error_code: String::new(),
            child_exit_observed: false,
            advances_continuity: false,
        };
        record.validate()?;
        let bytes = serde_json::to_vec(&record).map_err(|_| ResidentWakeJournalError::Corrupt)?;
        let mut file = OpenOptions::new()
            .write(true)
            .create_new(true)
            .mode(0o600)
            .custom_flags(libc::O_CLOEXEC | libc::O_NOFOLLOW)
            .open(&path)
            .map_err(|error| {
                if error.kind() == io::ErrorKind::AlreadyExists {
                    ResidentWakeJournalError::Duplicate
                } else {
                    ResidentWakeJournalError::Io
                }
            })?;
        file.write_all(&bytes)
            .map_err(|_| ResidentWakeJournalError::Io)?;
        file.sync_all().map_err(|_| ResidentWakeJournalError::Io)?;
        sync_directory(&journal_dir)?;
        Ok(Self {
            path,
            journal_dir,
            record,
            finalized: false,
        })
    }

    pub fn path(&self) -> &Path {
        &self.path
    }

    pub fn running_record(&self) -> &ResidentWakeJournalRecord {
        &self.record
    }

    pub fn complete(
        &mut self,
        finished_at_unix_ms: u64,
        disposition: &str,
        final_sha256: &str,
        execution_receipt_sha256: &str,
    ) -> Result<ResidentWakeJournalRecord, ResidentWakeJournalError> {
        if self.finalized {
            return Err(ResidentWakeJournalError::AlreadyFinalized);
        }
        let mut next = self.record.clone();
        next.state = ResidentWakeJournalState::Completed;
        next.finished_at_unix_ms = finished_at_unix_ms;
        next.disposition = disposition.to_string();
        next.final_sha256 = final_sha256.to_string();
        next.execution_receipt_sha256 = execution_receipt_sha256.to_string();
        next.child_exit_observed = true;
        next.advances_continuity = true;
        next.validate()?;
        replace_private_record(&self.path, &self.journal_dir, &next)?;
        self.record = next;
        self.finalized = true;
        Ok(self.record.clone())
    }

    pub fn fail(
        &mut self,
        finished_at_unix_ms: u64,
        error_code: &str,
        child_exit_observed: bool,
    ) -> Result<ResidentWakeJournalRecord, ResidentWakeJournalError> {
        if self.finalized {
            return Err(ResidentWakeJournalError::AlreadyFinalized);
        }
        if error_code.trim().is_empty() || error_code.chars().count() > 128 {
            return Err(ResidentWakeJournalError::InvalidTransition);
        }
        let mut next = self.record.clone();
        next.state = ResidentWakeJournalState::Failed;
        next.finished_at_unix_ms = finished_at_unix_ms;
        next.error_code = error_code.to_string();
        next.child_exit_observed = child_exit_observed;
        next.validate()?;
        replace_private_record(&self.path, &self.journal_dir, &next)?;
        self.record = next;
        self.finalized = true;
        Ok(self.record.clone())
    }
}

pub fn load_resident_wake_record(
    root: &Path,
    wake_id: &str,
) -> Result<ResidentWakeJournalRecord, ResidentWakeJournalError> {
    if !root.is_absolute() {
        return Err(ResidentWakeJournalError::InvalidRoot);
    }
    validate_identifier(wake_id)?;
    let path = root.join("wakes").join(format!("{wake_id}.json"));
    let metadata = std::fs::symlink_metadata(&path).map_err(|_| ResidentWakeJournalError::Io)?;
    if !metadata.file_type().is_file()
        || metadata.len() > 16_384
        || metadata.mode() & 0o777 != 0o600
        || metadata.nlink() != 1
    {
        return Err(ResidentWakeJournalError::Corrupt);
    }
    let bytes = std::fs::read(path).map_err(|_| ResidentWakeJournalError::Io)?;
    let record: ResidentWakeJournalRecord =
        serde_json::from_slice(&bytes).map_err(|_| ResidentWakeJournalError::Corrupt)?;
    record.validate()?;
    Ok(record)
}

fn replace_private_record(
    path: &Path,
    journal_dir: &Path,
    record: &ResidentWakeJournalRecord,
) -> Result<(), ResidentWakeJournalError> {
    let temporary = journal_dir.join(format!(".{}.{}.tmp", record.wake_id, Uuid::new_v4()));
    let bytes = serde_json::to_vec(record).map_err(|_| ResidentWakeJournalError::Corrupt)?;
    let mut file = OpenOptions::new()
        .write(true)
        .create_new(true)
        .mode(0o600)
        .custom_flags(libc::O_CLOEXEC | libc::O_NOFOLLOW)
        .open(&temporary)
        .map_err(|_| ResidentWakeJournalError::Io)?;
    let write_result = file
        .write_all(&bytes)
        .and_then(|_| file.sync_all())
        .map_err(|_| ResidentWakeJournalError::Io);
    if let Err(error) = write_result {
        let _ = std::fs::remove_file(&temporary);
        return Err(error);
    }
    std::fs::rename(&temporary, path).map_err(|_| {
        let _ = std::fs::remove_file(&temporary);
        ResidentWakeJournalError::Io
    })?;
    sync_directory(journal_dir)
}

fn create_private_directory(path: &Path) -> Result<(), ResidentWakeJournalError> {
    std::fs::create_dir_all(path).map_err(|_| ResidentWakeJournalError::Io)?;
    let metadata = std::fs::symlink_metadata(path).map_err(|_| ResidentWakeJournalError::Io)?;
    if !metadata.file_type().is_dir() {
        return Err(ResidentWakeJournalError::InvalidRoot);
    }
    std::fs::set_permissions(path, std::fs::Permissions::from_mode(0o700))
        .map_err(|_| ResidentWakeJournalError::Io)
}

fn sync_directory(path: &Path) -> Result<(), ResidentWakeJournalError> {
    File::open(path)
        .and_then(|directory| directory.sync_all())
        .map_err(|_| ResidentWakeJournalError::Io)
}

fn validate_identifier(value: &str) -> Result<(), ResidentWakeJournalError> {
    if value.is_empty()
        || value.len() > 128
        || !value.chars().all(|character| {
            character.is_ascii_alphanumeric() || matches!(character, '-' | '_' | ':')
        })
    {
        return Err(ResidentWakeJournalError::InvalidIdentifier);
    }
    Ok(())
}

fn is_sha256_hex(value: &str) -> bool {
    value.len() == 64
        && value
            .bytes()
            .all(|byte| byte.is_ascii_digit() || (b'a'..=b'f').contains(&byte))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn resident_state_root_prefers_explicit_private_root() {
        let resolved = resolve_resident_state_root(
            Some(PathBuf::from("/private/agent-bridge")),
            Some(PathBuf::from("/xdg-state")),
            Path::new("/data/agent-bridge/state.db"),
        );
        assert_eq!(resolved, Path::new("/private/agent-bridge"));
    }

    #[test]
    fn resident_state_root_uses_xdg_state_before_database_parent() {
        let resolved = resolve_resident_state_root(
            None,
            Some(PathBuf::from("/xdg-state")),
            Path::new("/data/agent-bridge/state.db"),
        );
        assert_eq!(resolved, Path::new("/xdg-state/agent-bridge"));
    }

    #[test]
    fn resident_state_root_retains_database_parent_fallback() {
        let resolved =
            resolve_resident_state_root(None, None, Path::new("/data/agent-bridge/state.db"));
        assert_eq!(resolved, Path::new("/data/agent-bridge"));
    }

    fn reserve(root: &Path) -> ResidentWakeReservation {
        ResidentWakeReservation::reserve(
            root,
            "wake-test-0001",
            "episode-test-0001",
            "agent-bridge:resident:xiaoshu",
            100,
        )
        .unwrap()
    }

    #[test]
    fn duplicate_wake_is_refused_across_reservations() {
        let root = tempfile::tempdir().unwrap();
        let root = root.path().canonicalize().unwrap();
        let first = reserve(&root);
        let error = ResidentWakeReservation::reserve(
            &root,
            "wake-test-0001",
            "episode-test-0001",
            "agent-bridge:resident:xiaoshu",
            101,
        )
        .unwrap_err();
        assert_eq!(error, ResidentWakeJournalError::Duplicate);
        assert_eq!(
            first.running_record().state,
            ResidentWakeJournalState::Running
        );
    }

    #[test]
    fn concurrent_subject_writer_is_refused_without_waiting() {
        let root = tempfile::tempdir().unwrap();
        let root = root.path().canonicalize().unwrap();
        let _first = ResidentSubjectLease::acquire(&root).unwrap();
        let error = ResidentSubjectLease::acquire(&root).unwrap_err();
        assert_eq!(error, ResidentWakeJournalError::Concurrent);
    }

    #[test]
    fn completed_record_survives_reopen_without_private_content() {
        let root = tempfile::tempdir().unwrap();
        let root = root.path().canonicalize().unwrap();
        let mut reservation = reserve(&root);
        let record = reservation
            .complete(200, "respond", &"a".repeat(64), &"b".repeat(64))
            .unwrap();
        assert_eq!(record.state, ResidentWakeJournalState::Completed);
        assert!(record.advances_continuity);
        let reopened = load_resident_wake_record(&root, "wake-test-0001").unwrap();
        assert_eq!(reopened, record);
        let raw = std::fs::read_to_string(reservation.path()).unwrap();
        assert!(!raw.contains("prompt"));
        assert!(!raw.contains("response"));
        assert!(!raw.contains("memory_candidates"));
    }

    #[test]
    fn failed_record_never_advances_continuity() {
        let root = tempfile::tempdir().unwrap();
        let root = root.path().canonicalize().unwrap();
        let mut reservation = reserve(&root);
        let record = reservation.fail(150, "provider_deadline", true).unwrap();
        assert_eq!(record.state, ResidentWakeJournalState::Failed);
        assert!(!record.advances_continuity);
        assert_eq!(record.error_code, "provider_deadline");
    }
}
