//! Dormant S628 replay-continuity seam and synthetic backing.
//!
//! A reopened handle shares one in-memory backing. This proves reservation
//! state-machine behavior only; it does not prove persistence across an OS
//! process restart and has no runtime caller.

#![deny(clippy::all)]

use std::sync::Arc;
use std::sync::atomic::{AtomicU8, Ordering};

pub const SYNTHETIC_REPLAY_CONTINUITY_CAPACITY: usize = 4_096;
const STATE_AVAILABLE: u8 = 0;
const STATE_RESERVED: u8 = 1;
const STATE_COMMITTED: u8 = 2;
const STATE_ABORTED: u8 = 3;

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum StoryRenderReplayContinuityError {
    Replay,
    OutOfRange,
    BackendUnavailable,
    WrongStore,
    InvalidTransition,
}

/// Synchronous reservation persistence boundary for one replay namespace.
pub trait StoryRenderReplayContinuityStore: Send + Sync {
    type Reservation: Send;

    fn reserve(&self, sequence: u64)
    -> Result<Self::Reservation, StoryRenderReplayContinuityError>;

    fn commit(
        &self,
        reservation: Self::Reservation,
    ) -> Result<(), StoryRenderReplayContinuityError>;

    fn abort(&self, reservation: Self::Reservation)
    -> Result<(), StoryRenderReplayContinuityError>;
}

#[derive(Clone, Copy, Debug, Default, Eq, PartialEq)]
pub enum StoryRenderSyntheticReplayFault {
    #[default]
    None,
    ReserveUnavailable,
    FinalizeUnavailable,
}

pub struct StoryRenderSyntheticReplayMemory {
    backing: Arc<StoryRenderSyntheticReplayBacking>,
}

impl StoryRenderSyntheticReplayMemory {
    pub fn new() -> Self {
        Self::default()
    }

    pub fn open(&self) -> StoryRenderSyntheticReplayStore {
        self.open_with_fault(StoryRenderSyntheticReplayFault::None)
    }

    pub fn open_with_fault(
        &self,
        fault: StoryRenderSyntheticReplayFault,
    ) -> StoryRenderSyntheticReplayStore {
        StoryRenderSyntheticReplayStore {
            backing: Arc::clone(&self.backing),
            fault,
        }
    }
}

impl Default for StoryRenderSyntheticReplayMemory {
    fn default() -> Self {
        Self {
            backing: Arc::new(StoryRenderSyntheticReplayBacking {
                states: std::array::from_fn(|_| AtomicU8::new(STATE_AVAILABLE)),
            }),
        }
    }
}

struct StoryRenderSyntheticReplayBacking {
    states: [AtomicU8; SYNTHETIC_REPLAY_CONTINUITY_CAPACITY],
}

pub struct StoryRenderSyntheticReplayStore {
    backing: Arc<StoryRenderSyntheticReplayBacking>,
    fault: StoryRenderSyntheticReplayFault,
}

pub struct StoryRenderSyntheticReplayReservation {
    backing: Arc<StoryRenderSyntheticReplayBacking>,
    index: usize,
}

impl StoryRenderReplayContinuityStore for StoryRenderSyntheticReplayStore {
    type Reservation = StoryRenderSyntheticReplayReservation;

    fn reserve(
        &self,
        sequence: u64,
    ) -> Result<Self::Reservation, StoryRenderReplayContinuityError> {
        let index =
            usize::try_from(sequence).map_err(|_| StoryRenderReplayContinuityError::OutOfRange)?;
        if index >= SYNTHETIC_REPLAY_CONTINUITY_CAPACITY {
            return Err(StoryRenderReplayContinuityError::OutOfRange);
        }
        if self.fault == StoryRenderSyntheticReplayFault::ReserveUnavailable {
            return Err(StoryRenderReplayContinuityError::BackendUnavailable);
        }

        match self.backing.states[index].compare_exchange(
            STATE_AVAILABLE,
            STATE_RESERVED,
            Ordering::AcqRel,
            Ordering::Acquire,
        ) {
            Ok(STATE_AVAILABLE) => Ok(StoryRenderSyntheticReplayReservation {
                backing: Arc::clone(&self.backing),
                index,
            }),
            Err(STATE_RESERVED | STATE_COMMITTED | STATE_ABORTED) => {
                Err(StoryRenderReplayContinuityError::Replay)
            }
            Ok(_) | Err(_) => Err(StoryRenderReplayContinuityError::InvalidTransition),
        }
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

impl StoryRenderSyntheticReplayStore {
    fn finalize(
        &self,
        reservation: StoryRenderSyntheticReplayReservation,
        terminal_state: u8,
    ) -> Result<(), StoryRenderReplayContinuityError> {
        if !Arc::ptr_eq(&self.backing, &reservation.backing) {
            return Err(StoryRenderReplayContinuityError::WrongStore);
        }
        if self.fault == StoryRenderSyntheticReplayFault::FinalizeUnavailable {
            return Err(StoryRenderReplayContinuityError::BackendUnavailable);
        }

        self.backing.states[reservation.index]
            .compare_exchange(
                STATE_RESERVED,
                terminal_state,
                Ordering::AcqRel,
                Ordering::Acquire,
            )
            .map(|_| ())
            .map_err(|_| StoryRenderReplayContinuityError::InvalidTransition)
    }
}
