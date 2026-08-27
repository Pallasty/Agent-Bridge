//! Terminal resource accounting for child processes owned by built-in agents.
//!
//! Linux exposes the child's final `struct rusage` while it is waitable.  A
//! normal `Child::wait` reaps that state, so this module first observes it with
//! the raw five-argument `waitid(P_PID, ..., WEXITED | WNOWAIT | WNOHANG,
//! rusage)` syscall.  The owning Tokio/portable-pty child handle remains the
//! only code that reaps the process afterwards.

use std::collections::BTreeSet;
use std::io;
use std::sync::{Arc, Mutex};

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum TerminalResourceStatus {
    /// At least one spawned generation has not reached a final branch yet.
    Pending,
    /// Every spawned generation was observed before the accumulator was sealed.
    Complete,
    /// Some, but not all, spawned generations have trustworthy observations.
    Partial,
    /// The platform does not implement the Linux raw-waitid observation.
    Unsupported,
    /// The session was sealed without any trustworthy terminal observation.
    Unavailable,
}

/// Read-only, deliberately PID-free view of terminal child resource usage.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct TerminalResourceSnapshot {
    status: TerminalResourceStatus,
    known_user_cpu_micros: Option<u64>,
    known_system_cpu_micros: Option<u64>,
    known_max_rss_bytes: Option<u64>,
    spawned_attempts: u32,
    observed_attempts: u32,
    complete_for_spawned_attempts: bool,
}

impl TerminalResourceSnapshot {
    pub fn source(&self) -> &'static str {
        if cfg!(target_os = "linux") {
            "linux_raw_waitid_wnowait_rusage"
        } else {
            "unsupported_platform"
        }
    }

    pub fn scope(&self) -> &'static str {
        "waited_child_generations"
    }

    pub fn status(&self) -> TerminalResourceStatus {
        self.status
    }

    /// Known CPU consumed by successfully observed generations.  `Some` does
    /// not mean total unless [`Self::complete_for_spawned_attempts`] is true.
    pub fn known_user_cpu_micros(&self) -> Option<u64> {
        self.known_user_cpu_micros
    }

    /// Known CPU consumed by successfully observed generations.  `Some` does
    /// not mean total unless [`Self::complete_for_spawned_attempts`] is true.
    pub fn known_system_cpu_micros(&self) -> Option<u64> {
        self.known_system_cpu_micros
    }

    /// Largest `ru_maxrss` among observed generations, converted from Linux
    /// KiB to bytes.  It is not a sum and is not a workload-tree claim.
    pub fn known_max_rss_bytes(&self) -> Option<u64> {
        self.known_max_rss_bytes
    }

    pub fn spawned_attempts(&self) -> u32 {
        self.spawned_attempts
    }

    pub fn observed_attempts(&self) -> u32 {
        self.observed_attempts
    }

    pub fn complete_for_spawned_attempts(&self) -> bool {
        self.complete_for_spawned_attempts
    }

    /// Raw wait rusage is attributed to waited child generations.  It cannot
    /// prove that every descendant in the agent workload was included.
    pub fn complete_for_workload_tree(&self) -> bool {
        false
    }
}

#[derive(Debug, Default)]
struct AccumulatorState {
    sealed: bool,
    next_generation: u64,
    open_generations: BTreeSet<u64>,
    spawned_attempts: u32,
    observed_attempts: u32,
    failed_attempts: u32,
    known_user_cpu_micros: u64,
    known_system_cpu_micros: u64,
    known_max_rss_bytes: u64,
}

#[derive(Debug, Default)]
pub(crate) struct TerminalResourceAccumulator {
    state: Mutex<AccumulatorState>,
}

impl TerminalResourceAccumulator {
    pub(crate) fn new() -> Arc<Self> {
        Arc::new(Self::default())
    }

    pub(crate) fn begin_generation(self: &Arc<Self>, pid: u32) -> Option<TerminalWaitObservation> {
        let mut state = self.state.lock().unwrap_or_else(|e| e.into_inner());
        if state.sealed {
            return None;
        }
        let Some(next_generation) = state.next_generation.checked_add(1) else {
            state.failed_attempts = state.failed_attempts.saturating_add(1);
            return None;
        };
        let Some(spawned_attempts) = state.spawned_attempts.checked_add(1) else {
            state.failed_attempts = state.failed_attempts.saturating_add(1);
            return None;
        };
        state.next_generation = next_generation;
        let generation = state.next_generation;
        state.open_generations.insert(generation);
        state.spawned_attempts = spawned_attempts;
        Some(TerminalWaitObservation {
            accumulator: self.clone(),
            generation,
            pid,
        })
    }

    pub(crate) fn seal(&self) {
        let mut state = self.state.lock().unwrap_or_else(|e| e.into_inner());
        state.sealed = true;
    }

    pub(crate) fn snapshot(&self) -> TerminalResourceSnapshot {
        let state = self.state.lock().unwrap_or_else(|e| e.into_inner());
        let complete = state.sealed
            && state.spawned_attempts != 0
            && state.observed_attempts == state.spawned_attempts
            && state.failed_attempts == 0
            && state.open_generations.is_empty();
        let status = if !cfg!(target_os = "linux") {
            TerminalResourceStatus::Unsupported
        } else if !state.sealed {
            TerminalResourceStatus::Pending
        } else if complete {
            TerminalResourceStatus::Complete
        } else if state.observed_attempts != 0 {
            TerminalResourceStatus::Partial
        } else {
            TerminalResourceStatus::Unavailable
        };
        let has_known = state.observed_attempts != 0;
        TerminalResourceSnapshot {
            status,
            known_user_cpu_micros: has_known.then_some(state.known_user_cpu_micros),
            known_system_cpu_micros: has_known.then_some(state.known_system_cpu_micros),
            known_max_rss_bytes: has_known.then_some(state.known_max_rss_bytes),
            spawned_attempts: state.spawned_attempts,
            observed_attempts: state.observed_attempts,
            complete_for_spawned_attempts: complete,
        }
    }

    fn record(&self, generation: u64, outcome: ObservationOutcome) {
        let mut state = self.state.lock().unwrap_or_else(|e| e.into_inner());
        if !state.open_generations.remove(&generation) {
            return;
        }
        match outcome {
            ObservationOutcome::Observed(usage) => {
                let Some(observed_attempts) = state.observed_attempts.checked_add(1) else {
                    state.failed_attempts = state.failed_attempts.saturating_add(1);
                    return;
                };
                state.observed_attempts = observed_attempts;
                let Some(user_cpu_micros) = state
                    .known_user_cpu_micros
                    .checked_add(usage.user_cpu_micros)
                else {
                    state.failed_attempts = state.failed_attempts.saturating_add(1);
                    return;
                };
                let Some(system_cpu_micros) = state
                    .known_system_cpu_micros
                    .checked_add(usage.system_cpu_micros)
                else {
                    state.failed_attempts = state.failed_attempts.saturating_add(1);
                    return;
                };
                state.known_user_cpu_micros = user_cpu_micros;
                state.known_system_cpu_micros = system_cpu_micros;
                state.known_max_rss_bytes = state.known_max_rss_bytes.max(usage.max_rss_bytes);
            }
            ObservationOutcome::Unavailable => {
                state.failed_attempts = state.failed_attempts.saturating_add(1);
            }
            #[cfg(not(target_os = "linux"))]
            ObservationOutcome::Unsupported => {
                state.failed_attempts = state.failed_attempts.saturating_add(1);
            }
        }
    }
}

#[derive(Clone)]
pub(crate) struct TerminalWaitObservation {
    accumulator: Arc<TerminalResourceAccumulator>,
    generation: u64,
    pid: u32,
}

impl TerminalWaitObservation {
    pub(crate) async fn observe(self) {
        #[cfg(target_os = "linux")]
        let outcome = loop {
            match observe_once(self.pid) {
                Ok(Some(usage)) => break ObservationOutcome::Observed(usage),
                Ok(None) => tokio::time::sleep(std::time::Duration::from_millis(20)).await,
                Err(error) if error.kind() == io::ErrorKind::Interrupted => continue,
                Err(_) => break ObservationOutcome::Unavailable,
            }
        };
        #[cfg(not(target_os = "linux"))]
        let outcome = ObservationOutcome::Unsupported;

        self.accumulator.record(self.generation, outcome);
    }

    /// PTY children are already drained and reaped on their dedicated reader
    /// thread.  Observe in that same thread immediately before its sole wait.
    pub(crate) fn observe_blocking(self) {
        #[cfg(target_os = "linux")]
        let outcome = loop {
            match observe_once(self.pid) {
                Ok(Some(usage)) => break ObservationOutcome::Observed(usage),
                Ok(None) => std::thread::sleep(std::time::Duration::from_millis(2)),
                Err(error) if error.kind() == io::ErrorKind::Interrupted => continue,
                Err(_) => break ObservationOutcome::Unavailable,
            }
        };
        #[cfg(not(target_os = "linux"))]
        let outcome = ObservationOutcome::Unsupported;

        self.accumulator.record(self.generation, outcome);
    }
}

#[derive(Debug, Clone, Copy)]
struct ObservedUsage {
    user_cpu_micros: u64,
    system_cpu_micros: u64,
    max_rss_bytes: u64,
}

enum ObservationOutcome {
    Observed(ObservedUsage),
    Unavailable,
    #[cfg(not(target_os = "linux"))]
    Unsupported,
}

#[cfg(target_os = "linux")]
fn observe_once(pid: u32) -> io::Result<Option<ObservedUsage>> {
    if pid == 0 || pid > libc::pid_t::MAX as u32 {
        return Err(io::Error::new(
            io::ErrorKind::InvalidInput,
            "invalid child pid for waitid",
        ));
    }
    let mut info: libc::siginfo_t = unsafe { std::mem::zeroed() };
    let mut usage: libc::rusage = unsafe { std::mem::zeroed() };
    let options = libc::WEXITED | libc::WNOWAIT | libc::WNOHANG;
    let rc = unsafe {
        libc::syscall(
            libc::SYS_waitid,
            libc::P_PID,
            pid as libc::id_t,
            &mut info as *mut libc::siginfo_t,
            options,
            &mut usage as *mut libc::rusage,
        )
    };
    if rc == -1 {
        return Err(io::Error::last_os_error());
    }
    if unsafe { info.si_pid() } == 0 {
        return Ok(None);
    }
    if unsafe { info.si_pid() } != pid as libc::pid_t {
        return Err(io::Error::other("waitid returned an unexpected child pid"));
    }
    let max_rss_kib = u64::try_from(usage.ru_maxrss)
        .map_err(|_| io::Error::other("waitid returned negative ru_maxrss"))?;
    let max_rss_bytes = max_rss_kib
        .checked_mul(1024)
        .ok_or_else(|| io::Error::other("waitid ru_maxrss byte conversion overflow"))?;
    Ok(Some(ObservedUsage {
        user_cpu_micros: timeval_micros(usage.ru_utime)?,
        system_cpu_micros: timeval_micros(usage.ru_stime)?,
        max_rss_bytes,
    }))
}

#[cfg(target_os = "linux")]
fn timeval_micros(value: libc::timeval) -> io::Result<u64> {
    let seconds = u64::try_from(value.tv_sec)
        .map_err(|_| io::Error::other("waitid returned negative timeval seconds"))?;
    let micros = u64::try_from(value.tv_usec)
        .map_err(|_| io::Error::other("waitid returned negative timeval microseconds"))?;
    if micros >= 1_000_000 {
        return Err(io::Error::other(
            "waitid returned out-of-range timeval microseconds",
        ));
    }
    seconds
        .checked_mul(1_000_000)
        .and_then(|whole| whole.checked_add(micros))
        .ok_or_else(|| io::Error::other("waitid timeval conversion overflow"))
}

/// Equivalent output semantics to `tokio::process::Child::wait_with_output`,
/// with concurrent pipe draining, but observes terminal rusage before the
/// child handle performs the sole reap.
#[cfg(test)]
pub(crate) async fn wait_with_output(
    child: tokio::process::Child,
    observation: TerminalWaitObservation,
) -> io::Result<std::process::Output> {
    wait_with_output_notify_reaped(child, observation, || {}).await
}

/// Wait-with-output variant that invokes `on_reaped` immediately after
/// the child handle's wait completes. `Ok` is the successful, sole reap; on
/// `Err`, callers must likewise stop treating the old PID as signalable. The
/// callback never waits for stdout/stderr EOF: descendants may keep inherited
/// pipes open after the waited leader is already gone.
pub(crate) async fn wait_with_output_notify_reaped<F>(
    mut child: tokio::process::Child,
    observation: TerminalWaitObservation,
    on_reaped: F,
) -> io::Result<std::process::Output>
where
    F: FnOnce() + Send,
{
    use tokio::io::AsyncReadExt;

    let stdout = child.stdout.take();
    let stderr = child.stderr.take();
    let wait = async {
        observation.observe().await;
        let status = child.wait().await;
        on_reaped();
        status
    };
    let drain = async {
        let read_stdout = async {
            let mut bytes = Vec::new();
            if let Some(mut pipe) = stdout {
                pipe.read_to_end(&mut bytes).await?;
            }
            Ok::<_, io::Error>(bytes)
        };
        let read_stderr = async {
            let mut bytes = Vec::new();
            if let Some(mut pipe) = stderr {
                pipe.read_to_end(&mut bytes).await?;
            }
            Ok::<_, io::Error>(bytes)
        };
        tokio::join!(read_stdout, read_stderr)
    };
    let (status, (stdout, stderr)) = tokio::join!(wait, drain);
    Ok(std::process::Output {
        status: status?,
        stdout: stdout?,
        stderr: stderr?,
    })
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::process::Stdio;
    use tokio::process::Command;

    #[cfg(target_os = "linux")]
    #[tokio::test]
    async fn observes_fast_exit_before_the_only_reap() {
        let mut child = Command::new("/bin/true").spawn().expect("spawn");
        let pid = child.id().expect("pid");
        let accumulator = TerminalResourceAccumulator::new();
        let observation = accumulator.begin_generation(pid).expect("generation");
        observation.observe().await;
        let status = child.wait().await.expect("sole reap");
        assert!(status.success());
        accumulator.seal();
        let snapshot = accumulator.snapshot();
        assert_eq!(snapshot.status(), TerminalResourceStatus::Complete);
        assert_eq!(snapshot.spawned_attempts(), 1);
        assert_eq!(snapshot.observed_attempts(), 1);
        assert!(snapshot.known_user_cpu_micros().is_some());
        assert!(snapshot.complete_for_spawned_attempts());
        assert!(!snapshot.complete_for_workload_tree());
    }

    #[cfg(target_os = "linux")]
    #[tokio::test]
    async fn concurrent_pipe_drain_does_not_deadlock_large_output() {
        let mut command = Command::new("/bin/sh");
        command
            .args(["-c", "dd if=/dev/zero bs=65536 count=8 2>/dev/null; dd if=/dev/zero bs=65536 count=8 1>&2 2>/dev/null"])
            .stdout(Stdio::piped())
            .stderr(Stdio::piped());
        let child = command.spawn().expect("spawn");
        let pid = child.id().expect("pid");
        let accumulator = TerminalResourceAccumulator::new();
        let observation = accumulator.begin_generation(pid).expect("generation");
        let output = tokio::time::timeout(
            std::time::Duration::from_secs(10),
            wait_with_output(child, observation),
        )
        .await
        .expect("wait must not deadlock")
        .expect("output");
        accumulator.seal();
        assert!(output.status.success());
        assert_eq!(output.stdout.len(), 512 * 1024);
        assert_eq!(output.stderr.len(), 512 * 1024);
        assert_eq!(
            accumulator.snapshot().status(),
            TerminalResourceStatus::Complete
        );
    }

    #[cfg(target_os = "linux")]
    #[tokio::test]
    async fn reap_notification_precedes_inherited_pipe_eof() {
        let mut command = Command::new("/bin/sh");
        command
            .args(["-c", "sleep 1 & exit 0"])
            .stdout(Stdio::piped())
            .stderr(Stdio::piped());
        let child = command.spawn().expect("spawn");
        let pid = child.id().expect("pid");
        let accumulator = TerminalResourceAccumulator::new();
        let observation = accumulator.begin_generation(pid).expect("generation");
        let reaped = Arc::new(tokio::sync::Notify::new());
        let reaped_callback = reaped.clone();
        let waiter = tokio::spawn(async move {
            wait_with_output_notify_reaped(child, observation, move || {
                reaped_callback.notify_one();
            })
            .await
        });

        tokio::time::timeout(std::time::Duration::from_millis(500), reaped.notified())
            .await
            .expect("leader should be reaped promptly");
        assert!(
            !waiter.is_finished(),
            "inherited pipe should still delay complete output collection"
        );
        let output = tokio::time::timeout(std::time::Duration::from_secs(2), waiter)
            .await
            .expect("descendant closes pipe")
            .expect("wait task")
            .expect("output");
        accumulator.seal();
        assert!(output.status.success());
        assert_eq!(
            accumulator.snapshot().status(),
            TerminalResourceStatus::Complete
        );
    }

    #[cfg(target_os = "linux")]
    #[tokio::test]
    async fn signal_exit_still_has_a_complete_observation() {
        use std::os::unix::process::ExitStatusExt;

        let mut command = Command::new("/bin/sh");
        command
            .args(["-c", "kill -TERM $$"])
            .stdout(Stdio::piped())
            .stderr(Stdio::piped());
        let child = command.spawn().expect("spawn");
        let pid = child.id().expect("pid");
        let accumulator = TerminalResourceAccumulator::new();
        let observation = accumulator.begin_generation(pid).expect("generation");
        let output = wait_with_output(child, observation).await.expect("output");
        accumulator.seal();

        assert_eq!(output.status.signal(), Some(libc::SIGTERM));
        assert_eq!(
            accumulator.snapshot().status(),
            TerminalResourceStatus::Complete
        );
    }

    #[test]
    fn partial_values_are_labelled_known_not_total() {
        let accumulator = TerminalResourceAccumulator::new();
        let first = accumulator.begin_generation(10).unwrap();
        let _second = accumulator.begin_generation(11).unwrap();
        accumulator.record(
            first.generation,
            ObservationOutcome::Observed(ObservedUsage {
                user_cpu_micros: 7,
                system_cpu_micros: 3,
                max_rss_bytes: 4096,
            }),
        );
        accumulator.seal();
        let snapshot = accumulator.snapshot();
        if cfg!(target_os = "linux") {
            assert_eq!(snapshot.status(), TerminalResourceStatus::Partial);
        } else {
            assert_eq!(snapshot.status(), TerminalResourceStatus::Unsupported);
        }
        assert_eq!(snapshot.known_user_cpu_micros(), Some(7));
        assert_eq!(snapshot.known_system_cpu_micros(), Some(3));
        assert_eq!(snapshot.known_max_rss_bytes(), Some(4096));
        assert!(!snapshot.complete_for_spawned_attempts());
    }

    #[cfg(target_os = "linux")]
    #[test]
    fn invalid_timevals_and_cross_generation_overflow_fail_closed() {
        assert!(timeval_micros(libc::timeval {
            tv_sec: -1,
            tv_usec: 0,
        })
        .is_err());
        assert!(timeval_micros(libc::timeval {
            tv_sec: 0,
            tv_usec: 1_000_000,
        })
        .is_err());

        let accumulator = TerminalResourceAccumulator::new();
        let first = accumulator.begin_generation(10).unwrap();
        let second = accumulator.begin_generation(11).unwrap();
        accumulator.record(
            first.generation,
            ObservationOutcome::Observed(ObservedUsage {
                user_cpu_micros: u64::MAX,
                system_cpu_micros: 1,
                max_rss_bytes: 1,
            }),
        );
        accumulator.record(
            second.generation,
            ObservationOutcome::Observed(ObservedUsage {
                user_cpu_micros: 1,
                system_cpu_micros: 1,
                max_rss_bytes: 2,
            }),
        );
        accumulator.seal();
        let snapshot = accumulator.snapshot();
        assert_eq!(snapshot.status(), TerminalResourceStatus::Partial);
        assert_eq!(snapshot.observed_attempts(), 2);
        assert_eq!(snapshot.known_user_cpu_micros(), Some(u64::MAX));
        assert!(!snapshot.complete_for_spawned_attempts());
    }
}
