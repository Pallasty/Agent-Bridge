//! Dormant S629 file-backed replay continuity for isolated tests.
//!
//! Each sequence owns one create-new record. Record existence consumes the
//! sequence even if writing or finalization is interrupted. This module has no
//! runtime caller and is not an adversarial-filesystem or cross-host proof.

#![deny(clippy::all)]

use std::fs::{self, File, OpenOptions};
use std::io::{self, Write};
use std::os::unix::fs::{DirBuilderExt, FileExt, MetadataExt, OpenOptionsExt, PermissionsExt};
use std::path::{Path, PathBuf};

use crate::story_render_replay_continuity_synthetic::{
    SYNTHETIC_REPLAY_CONTINUITY_CAPACITY, StoryRenderReplayContinuityError,
    StoryRenderReplayContinuityStore,
};

pub const SYNTHETIC_FILE_REPLAY_DIRECTORY: &str = "story-render-replay-continuity-s629";
const STATE_RECORD_MAGIC: &[u8; 8] = b"ABSR629\0";
const STATE_RECORD_LEN: usize = 17;
const STATE_OFFSET: u64 = 16;
const STATE_RESERVED: u8 = 1;
const STATE_COMMITTED: u8 = 2;
const STATE_ABORTED: u8 = 3;

#[derive(Clone, Copy, Debug, Default, Eq, PartialEq)]
pub enum StoryRenderFileReplayFault {
    #[default]
    None,
    AfterCreateBeforeRecord,
    BeforeFinalize,
}

pub struct StoryRenderFileReplayStore {
    state_directory: PathBuf,
    fault: StoryRenderFileReplayFault,
}

pub struct StoryRenderFileReplayReservation {
    state_directory: PathBuf,
    record_path: PathBuf,
    sequence: u64,
}

impl StoryRenderFileReplayStore {
    pub fn open(root: &Path) -> Result<Self, StoryRenderReplayContinuityError> {
        Self::open_with_fault(root, StoryRenderFileReplayFault::None)
    }

    pub fn open_with_fault(
        root: &Path,
        fault: StoryRenderFileReplayFault,
    ) -> Result<Self, StoryRenderReplayContinuityError> {
        if !root.is_absolute() {
            return Err(StoryRenderReplayContinuityError::BackendUnavailable);
        }
        let root_metadata = fs::symlink_metadata(root).map_err(backend_error)?;
        if root_metadata.file_type().is_symlink() || !root_metadata.is_dir() {
            return Err(StoryRenderReplayContinuityError::BackendUnavailable);
        }
        let canonical_root = fs::canonicalize(root).map_err(backend_error)?;
        let state_directory = canonical_root.join(SYNTHETIC_FILE_REPLAY_DIRECTORY);
        let mut builder = fs::DirBuilder::new();
        builder.mode(0o700);
        match builder.create(&state_directory) {
            Ok(()) => {}
            Err(error) if error.kind() == io::ErrorKind::AlreadyExists => {}
            Err(error) => return Err(backend_error(error)),
        }
        let metadata = fs::symlink_metadata(&state_directory).map_err(backend_error)?;
        if metadata.file_type().is_symlink()
            || !metadata.is_dir()
            || metadata.permissions().mode() & 0o777 != 0o700
        {
            return Err(StoryRenderReplayContinuityError::BackendUnavailable);
        }

        Ok(Self {
            state_directory: fs::canonicalize(state_directory).map_err(backend_error)?,
            fault,
        })
    }

    fn record_path(&self, sequence: u64) -> PathBuf {
        self.state_directory
            .join(format!("sequence-{sequence:04x}.s629"))
    }

    fn finalize(
        &self,
        reservation: StoryRenderFileReplayReservation,
        terminal_state: u8,
    ) -> Result<(), StoryRenderReplayContinuityError> {
        if reservation.state_directory != self.state_directory
            || reservation.record_path != self.record_path(reservation.sequence)
        {
            return Err(StoryRenderReplayContinuityError::WrongStore);
        }
        if self.fault == StoryRenderFileReplayFault::BeforeFinalize {
            return Err(StoryRenderReplayContinuityError::BackendUnavailable);
        }

        let file = OpenOptions::new()
            .read(true)
            .write(true)
            .custom_flags(libc::O_NOFOLLOW | libc::O_CLOEXEC)
            .open(&reservation.record_path)
            .map_err(backend_error)?;
        let metadata = file.metadata().map_err(backend_error)?;
        if !metadata.is_file()
            || metadata.len() != STATE_RECORD_LEN as u64
            || metadata.nlink() != 1
            || metadata.permissions().mode() & 0o777 != 0o600
        {
            return Err(StoryRenderReplayContinuityError::InvalidTransition);
        }

        let mut record = [0_u8; STATE_RECORD_LEN];
        file.read_exact_at(&mut record, 0).map_err(backend_error)?;
        if &record[..8] != STATE_RECORD_MAGIC
            || record[8..16] != reservation.sequence.to_be_bytes()
            || record[16] != STATE_RESERVED
        {
            return Err(StoryRenderReplayContinuityError::InvalidTransition);
        }
        if file
            .write_at(&[terminal_state], STATE_OFFSET)
            .map_err(backend_error)?
            != 1
        {
            return Err(StoryRenderReplayContinuityError::BackendUnavailable);
        }
        file.sync_all().map_err(backend_error)?;
        sync_directory(&self.state_directory)
    }
}

impl StoryRenderReplayContinuityStore for StoryRenderFileReplayStore {
    type Reservation = StoryRenderFileReplayReservation;

    fn reserve(
        &self,
        sequence: u64,
    ) -> Result<Self::Reservation, StoryRenderReplayContinuityError> {
        if sequence >= SYNTHETIC_REPLAY_CONTINUITY_CAPACITY as u64 {
            return Err(StoryRenderReplayContinuityError::OutOfRange);
        }
        let record_path = self.record_path(sequence);
        let mut file = match OpenOptions::new()
            .write(true)
            .create_new(true)
            .mode(0o600)
            .custom_flags(libc::O_NOFOLLOW | libc::O_CLOEXEC)
            .open(&record_path)
        {
            Ok(file) => file,
            Err(error) if error.kind() == io::ErrorKind::AlreadyExists => {
                return Err(StoryRenderReplayContinuityError::Replay);
            }
            Err(error) => return Err(backend_error(error)),
        };
        let metadata = file.metadata().map_err(backend_error)?;
        if !metadata.is_file()
            || metadata.nlink() != 1
            || metadata.permissions().mode() & 0o777 != 0o600
        {
            return Err(StoryRenderReplayContinuityError::BackendUnavailable);
        }
        if self.fault == StoryRenderFileReplayFault::AfterCreateBeforeRecord {
            return Err(StoryRenderReplayContinuityError::BackendUnavailable);
        }

        let mut record = [0_u8; STATE_RECORD_LEN];
        record[..8].copy_from_slice(STATE_RECORD_MAGIC);
        record[8..16].copy_from_slice(&sequence.to_be_bytes());
        record[16] = STATE_RESERVED;
        file.write_all(&record).map_err(backend_error)?;
        file.sync_all().map_err(backend_error)?;
        sync_directory(&self.state_directory)?;

        Ok(StoryRenderFileReplayReservation {
            state_directory: self.state_directory.clone(),
            record_path,
            sequence,
        })
    }

    fn commit(
        &self,
        reservation: Self::Reservation,
    ) -> Result<(), StoryRenderReplayContinuityError> {
        self.finalize(reservation, STATE_COMMITTED)
    }

    fn abort(
        &self,
        reservation: Self::Reservation,
    ) -> Result<(), StoryRenderReplayContinuityError> {
        self.finalize(reservation, STATE_ABORTED)
    }
}

fn sync_directory(directory: &Path) -> Result<(), StoryRenderReplayContinuityError> {
    File::open(directory)
        .and_then(|file| file.sync_all())
        .map_err(backend_error)
}

fn backend_error(_error: io::Error) -> StoryRenderReplayContinuityError {
    StoryRenderReplayContinuityError::BackendUnavailable
}
