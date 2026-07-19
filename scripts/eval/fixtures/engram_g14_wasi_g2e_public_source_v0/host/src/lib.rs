//! G2E source-level direct host model for the exact three-interface WIT world.
//! It is public synthetic source only: G2E does not compile, link, or run it.

#![forbid(unsafe_code)]

pub const WALL_EPOCH_SECONDS: u64 = 946_684_800;
pub const QUANTUM_NANOSECONDS: u64 = 1_000_000;
pub const MAX_LIVE_POLLABLES: usize = 16;

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct PollableId(pub u64);

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
struct TimerPollable {
    id: PollableId,
    deadline_nanoseconds: u64,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum ClockError {
    ArithmeticOverflow,
    EmptyPollInput,
    ForeignPollable,
    TooManyPollables,
}

/// One logical-clock authority owns all exact-world clock and poll semantics.
pub struct LogicalClockHost {
    logical_nanoseconds: u64,
    next_pollable_id: u64,
    timers: Vec<TimerPollable>,
}

impl LogicalClockHost {
    pub fn new() -> Self {
        Self {
            logical_nanoseconds: 0,
            next_pollable_id: 0,
            timers: Vec::new(),
        }
    }

    pub fn wall_clock_resolution(&self) -> u64 {
        QUANTUM_NANOSECONDS
    }

    pub fn wall_clock_now(&mut self) -> Result<(u64, u64), ClockError> {
        let current = self.logical_nanoseconds;
        self.advance_quantum()?;
        Ok((WALL_EPOCH_SECONDS, current))
    }

    pub fn monotonic_clock_resolution(&self) -> u64 {
        QUANTUM_NANOSECONDS
    }

    pub fn monotonic_clock_now(&mut self) -> Result<u64, ClockError> {
        let current = self.logical_nanoseconds;
        self.advance_quantum()?;
        Ok(current)
    }

    pub fn subscribe_duration(&mut self, duration_nanoseconds: u64) -> Result<PollableId, ClockError> {
        let deadline = self.logical_nanoseconds.checked_add(duration_nanoseconds).ok_or(ClockError::ArithmeticOverflow)?;
        self.register_deadline(deadline)
    }

    pub fn subscribe_instant(&mut self, deadline_nanoseconds: u64) -> Result<PollableId, ClockError> {
        self.register_deadline(deadline_nanoseconds)
    }

    /// Exact-world `wasi:io/poll` behavior: return ready caller indices or jump
    /// only this logical clock to the nearest registered deadline. No host wait.
    pub fn poll(&mut self, input: &[PollableId]) -> Result<Vec<u32>, ClockError> {
        if input.is_empty() {
            return Err(ClockError::EmptyPollInput);
        }
        let timers = input.iter().map(|id| self.timer_for(*id)).collect::<Result<Vec<_>, _>>()?;
        let mut ready = Self::ready_indices(&timers, self.logical_nanoseconds);
        if ready.is_empty() {
            let earliest = timers.iter().map(|timer| timer.deadline_nanoseconds).min().ok_or(ClockError::EmptyPollInput)?;
            self.logical_nanoseconds = earliest;
            ready = Self::ready_indices(&timers, self.logical_nanoseconds);
        }
        Ok(ready)
    }

    pub fn logical_nanoseconds(&self) -> u64 {
        self.logical_nanoseconds
    }

    fn advance_quantum(&mut self) -> Result<(), ClockError> {
        self.logical_nanoseconds = self.logical_nanoseconds.checked_add(QUANTUM_NANOSECONDS).ok_or(ClockError::ArithmeticOverflow)?;
        Ok(())
    }

    fn register_deadline(&mut self, deadline_nanoseconds: u64) -> Result<PollableId, ClockError> {
        if self.timers.len() >= MAX_LIVE_POLLABLES {
            return Err(ClockError::TooManyPollables);
        }
        let id = PollableId(self.next_pollable_id);
        self.next_pollable_id = self.next_pollable_id.checked_add(1).ok_or(ClockError::ArithmeticOverflow)?;
        self.timers.push(TimerPollable { id, deadline_nanoseconds });
        Ok(id)
    }

    fn timer_for(&self, id: PollableId) -> Result<TimerPollable, ClockError> {
        self.timers.iter().copied().find(|timer| timer.id == id).ok_or(ClockError::ForeignPollable)
    }

    fn ready_indices(timers: &[TimerPollable], logical_nanoseconds: u64) -> Vec<u32> {
        timers.iter().enumerate().filter_map(|(index, timer)| {
            (timer.deadline_nanoseconds <= logical_nanoseconds).then_some(index as u32)
        }).collect()
    }
}
