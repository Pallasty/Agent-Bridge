//! Linux delegated-cgroup custody for one complete local agent workload tree.
//!
//! A prepared launch enters a private systemd user scope.  The hidden
//! supervisor stays in a sibling cgroup while the executor and every
//! descendant run below `workload/`, allowing it to observe recursive
//! `populated=0` and seal authoritative CPU/memory/pids counters before the
//! transient scope disappears.  Process identifiers and cgroup paths never
//! enter the public snapshot.
//!
//! Security boundary: cgroup custody and the v1 durable outbox provide
//! cooperative same-UID lifecycle/accounting integrity and crash recovery,
//! not hostile same-UID containment. An unsandboxed executor with
//! deliberate access to its delegated cgroup filesystem can interfere with
//! that subtree; hardening that boundary requires a separately validated LSM
//! or namespace policy and must not be inferred from a `Complete` receipt.

use ab_core::{Error, Result};
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use std::path::{Path, PathBuf};
use std::sync::{Arc, Mutex};
use std::time::{Duration, Instant};

#[cfg(target_os = "linux")]
static SUPERVISOR_SIGNAL_FD: std::sync::atomic::AtomicI32 = std::sync::atomic::AtomicI32::new(-1);

pub const POLICY_ENV: &str = "AGENT_BRIDGE_CGROUP_CUSTODY";
pub const RUNTIME_MAX_ENV: &str = "AGENT_BRIDGE_CGROUP_RUNTIME_MAX_SEC";
pub const RECEIPT_BINDING_ENV: &str = "AGENT_BRIDGE_WORKLOAD_RECEIPT_BINDING";
pub const RECEIPT_DIR_ENV: &str = "AGENT_BRIDGE_CGROUP_RECEIPT_DIR";
pub const INTERNAL_MARKER: &str = "__ab_agent_cgroup_supervise";

const SOURCE: &str = "linux_cgroup_v2_systemd_delegated_scope";
const SCOPE: &str = "delegated_session_workload_tree";
const MAX_PROTOCOL_FRAME_BYTES: usize = 64 * 1024;
const MAX_DURABLE_RECEIPT_ENTRIES: usize = 4096;
const MAX_DURABLE_ENTRY_FILES: usize = 16;
const MAX_RECEIPT_BINDING_BYTES: usize = 256;
// Schema 2 includes the mandatory producer.lock lease object. Schema 1 was
// never deployed; rejecting it explicitly avoids treating a pre-lease source
// candidate as a safely recoverable outbox entry.
const DURABLE_MANIFEST_SCHEMA: u32 = 2;
const DURABLE_RECEIPT_SCHEMA: u32 = 2;
const MANIFEST_FILE: &str = "manifest.json";
const RECEIPT_FILE: &str = "receipt.json";
const SPOOL_LOCK_FILE: &str = ".spool.lock";
const PRODUCER_LOCK_FILE: &str = "producer.lock";

/// PID-free content address for one durably spooled terminal cgroup receipt.
/// The path, unit nonce, cgroup path, and process identity remain private.
#[derive(Debug, Clone, PartialEq, Eq, PartialOrd, Ord, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct DurableWorkloadReceiptRef {
    pub receipt_id: String,
    pub sha256: String,
}

/// One independently manifest-bound terminal receipt found by restart scan.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct DurableWorkloadReceiptRecord {
    pub receipt_ref: DurableWorkloadReceiptRef,
    pub span_id: String,
    pub runtime: String,
    pub resources: WorkloadResourceSnapshot,
}

/// Bounded, content-free explanation for an entry that cannot be admitted.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct DurableWorkloadReceiptIssue {
    #[serde(skip_serializing_if = "Option::is_none")]
    pub receipt_id: Option<String>,
    pub state: String,
    pub reason: String,
}

#[derive(Debug, Clone, Default, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct DurableWorkloadReceiptScan {
    pub receipts: Vec<DurableWorkloadReceiptRecord>,
    pub unresolved: Vec<DurableWorkloadReceiptIssue>,
    pub issues: Vec<DurableWorkloadReceiptIssue>,
}

#[derive(Debug, Clone, Copy, Default, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum WorkloadResourceStatus {
    Pending,
    Complete,
    Partial,
    Unavailable,
    #[default]
    Unsupported,
}

/// Public, durable, PID-free accounting evidence for all generations of a
/// local runtime session. Counters are summed across generations; peaks are
/// the maximum observed generation peak.
#[derive(Debug, Clone, Default, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct WorkloadResourceSnapshot {
    pub status: WorkloadResourceStatus,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub source: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub scope: Option<String>,
    #[serde(default, skip_serializing_if = "Vec::is_empty")]
    pub controllers: Vec<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub cpu_usage_usec: Option<u64>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub cpu_user_usec: Option<u64>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub cpu_system_usec: Option<u64>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub memory_peak_bytes: Option<u64>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub pids_peak: Option<u64>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub oom_events: Option<u64>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub oom_kill_events: Option<u64>,
    pub populated_zero_observed: bool,
    pub start_before_exec: bool,
    pub complete_for_cpu_memory_workload_tree: bool,
    pub complete_for_pids_workload_tree: bool,
    pub generation_count: u32,
    pub captured_generation_count: u32,
    #[serde(default, skip_serializing_if = "Vec::is_empty")]
    pub incomplete_reasons: Vec<String>,
    #[serde(default, skip_serializing_if = "Vec::is_empty")]
    pub durable_receipts: Vec<DurableWorkloadReceiptRef>,
}

/// Opaque ownership handoff that keeps durable producer leases held while a
/// caller commits the corresponding terminal evidence and performs its
/// digest-bound ACK. The guard deliberately implements neither `Debug` nor
/// serde traits: it is an in-process capability, never durable evidence.
#[must_use = "dropping this guard releases durable receipt producer leases"]
#[derive(Clone, Default)]
pub struct DurableWorkloadReceiptLeaseGuard {
    _entries: Vec<HeldDurableReceiptLease>,
}

#[derive(Clone)]
struct HeldDurableReceiptLease {
    entry: Arc<DurableReceiptEntry>,
    receipt_ref: Option<DurableWorkloadReceiptRef>,
}

impl DurableWorkloadReceiptLeaseGuard {
    /// Whether this snapshot carried no durable producer lease.
    pub fn is_empty(&self) -> bool {
        self._entries.is_empty()
    }

    /// Whether this guard owns the producer lease for this exact
    /// content-addressed receipt reference.
    pub fn covers(&self, receipt_ref: &DurableWorkloadReceiptRef) -> bool {
        self._entries
            .iter()
            .any(|held| held.receipt_ref.as_ref() == Some(receipt_ref))
    }

    /// Fail-closed coverage check for a complete commit batch.
    pub fn covers_all(&self, receipt_refs: &[DurableWorkloadReceiptRef]) -> bool {
        receipt_refs
            .iter()
            .all(|receipt_ref| self.covers(receipt_ref))
    }

    /// PID-free opaque IDs whose producer leases are held by this guard.
    pub fn receipt_ids(&self) -> Vec<String> {
        let mut ids: Vec<_> = self
            ._entries
            .iter()
            .map(|held| held.entry.receipt_id.clone())
            .collect();
        ids.sort();
        ids.dedup();
        ids
    }

    /// Digest-bound ACK using the producer lease already owned by this
    /// guard. This is the live-path counterpart of the restart scanner's
    /// public ACK, which intentionally refuses entries with active owners.
    pub fn acknowledge(&self, receipt_ref: &DurableWorkloadReceiptRef) -> Result<bool> {
        let held = self
            ._entries
            .iter()
            .find(|held| held.receipt_ref.as_ref() == Some(receipt_ref))
            .ok_or_else(|| {
                Error::InvalidArgument(
                    "durable receipt lease guard does not cover the requested digest".into(),
                )
            })?;
        #[cfg(target_os = "linux")]
        {
            acknowledge_durable_workload_receipt_at_with_lease(
                &held.entry.root,
                receipt_ref,
                Some(&held.entry._producer_lease),
            )
        }
        #[cfg(not(target_os = "linux"))]
        {
            let _ = held;
            Err(Error::Backend(
                "durable workload receipt acknowledgement is Linux-only".into(),
            ))
        }
    }
}

#[derive(Clone)]
pub struct WorkloadGeneration {
    state: Arc<GenerationState>,
}

impl std::fmt::Debug for WorkloadGeneration {
    fn fmt(&self, formatter: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        formatter
            .debug_struct("WorkloadGeneration")
            .field("status", &self.state.snapshot().status)
            .finish_non_exhaustive()
    }
}

#[derive(Clone)]
pub struct WorkloadControl {
    state: Arc<GenerationState>,
}

impl std::fmt::Debug for WorkloadControl {
    fn fmt(&self, formatter: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        formatter
            .debug_struct("WorkloadControl")
            .finish_non_exhaustive()
    }
}

impl WorkloadControl {
    pub async fn request_terminate(&self) -> Result<()> {
        self.state.request_control(ControlAction::Terminate)
    }

    pub async fn request_kill(&self) -> Result<()> {
        self.state.request_control(ControlAction::Kill)
    }
}

#[derive(Clone)]
pub(crate) struct WorkloadCustody {
    inner: Arc<Mutex<CustodyState>>,
}

struct CustodyState {
    generations: Vec<Arc<GenerationState>>,
    /// The generation that currently owns lifecycle control. Historical
    /// generations stay in `generations` solely for terminal accounting.
    current_generation: Option<Arc<GenerationState>>,
    generation_count: u32,
    unaccounted_generation_count: u32,
    sealed: bool,
    fallback: Option<PidFd>,
    fallback_pid: u32,
    fallback_pgid: Option<u32>,
    fallback_start_ticks: Option<u64>,
}

impl WorkloadCustody {
    pub(crate) fn direct(pid: u32, pgid: Option<u32>, start_ticks: Option<u64>) -> Self {
        Self::new(pid, pgid, start_ticks, None)
    }

    pub(crate) fn new(
        pid: u32,
        pgid: Option<u32>,
        start_ticks: Option<u64>,
        generation: Option<WorkloadGeneration>,
    ) -> Self {
        let generation_unaccounted = generation.is_none();
        let current_generation = generation
            .as_ref()
            .map(|generation| generation.state.clone());
        let generations = generation
            .into_iter()
            .map(|generation| generation.state)
            .collect();
        Self {
            inner: Arc::new(Mutex::new(CustodyState {
                generations,
                current_generation,
                generation_count: 1,
                unaccounted_generation_count: u32::from(generation_unaccounted),
                sealed: false,
                fallback: generation_unaccounted
                    .then(|| PidFd::open_bound(pid, start_ticks))
                    .flatten(),
                fallback_pid: pid,
                fallback_pgid: pgid,
                fallback_start_ticks: start_ticks,
            })),
        }
    }

    pub(crate) fn begin_generation(&self, pid: u32, generation: Option<WorkloadGeneration>) {
        let generation = generation.map(|generation| generation.state);
        let mut state = lock_unpoison(&self.inner);
        state.generation_count = state.generation_count.saturating_add(1);
        if generation.is_none() {
            state.unaccounted_generation_count =
                state.unaccounted_generation_count.saturating_add(1);
        }
        let start_ticks = proc_process_identity(pid).map(|(_, ticks)| ticks);
        state.fallback = if state.sealed {
            None
        } else {
            generation
                .is_none()
                .then(|| PidFd::open_bound(pid, start_ticks))
                .flatten()
        };
        state.fallback_pid = pid;
        state.fallback_pgid = None;
        state.fallback_start_ticks = start_ticks;
        let seal_generation = state.sealed.then(|| generation.clone()).flatten();
        state.current_generation = (!state.sealed).then(|| generation.clone()).flatten();
        if let Some(generation) = generation {
            state.generations.push(generation);
        }
        drop(state);
        if let Some(generation) = seal_generation {
            generation.seal();
        }
    }

    pub(crate) fn attach_generation(&self, generation: WorkloadGeneration) {
        let generation = generation.state;
        let mut state = lock_unpoison(&self.inner);
        // PTY custody already captured a pidfd/start token before its sole
        // reaper thread started. Never reopen a numeric PID here: a fast
        // supervisor may already have exited and the PID may have been reused.
        state.unaccounted_generation_count = state.unaccounted_generation_count.saturating_sub(1);
        let seal_generation = state.sealed.then(|| generation.clone());
        if !state.sealed {
            state.current_generation = Some(generation.clone());
        }
        state.generations.push(generation);
        drop(state);
        if let Some(generation) = seal_generation {
            generation.seal();
        }
    }

    pub(crate) fn control(&self) -> Option<WorkloadControl> {
        lock_unpoison(&self.inner)
            .current_generation
            .clone()
            .map(|state| WorkloadControl { state })
    }

    pub(crate) fn snapshot(&self) -> WorkloadResourceSnapshot {
        self.snapshot_with_lease().0
    }

    pub(crate) fn snapshot_with_lease(
        &self,
    ) -> (WorkloadResourceSnapshot, DurableWorkloadReceiptLeaseGuard) {
        let state = lock_unpoison(&self.inner);
        let snapshot = merge_snapshots(
            &state.generations,
            state.generation_count,
            state.unaccounted_generation_count,
        );
        let mut entries: Vec<HeldDurableReceiptLease> = Vec::new();
        for generation in &state.generations {
            let StateDirectoryLease::Durable { _entry } = &generation._state_directory else {
                continue;
            };
            if !entries.iter().any(|held| Arc::ptr_eq(&held.entry, _entry)) {
                entries.push(HeldDurableReceiptLease {
                    entry: _entry.clone(),
                    receipt_ref: snapshot
                        .durable_receipts
                        .iter()
                        .find(|receipt_ref| receipt_ref.receipt_id == _entry.receipt_id)
                        .cloned(),
                });
            }
        }
        (
            snapshot,
            DurableWorkloadReceiptLeaseGuard { _entries: entries },
        )
    }

    pub(crate) fn seal(&self) {
        let generations = {
            let mut state = lock_unpoison(&self.inner);
            state.sealed = true;
            state.current_generation = None;
            state.fallback = None;
            state.generations.clone()
        };
        for generation in generations {
            generation.seal();
        }
    }

    pub(crate) fn request_terminate_now(&self) -> Result<()> {
        self.request(ControlAction::Terminate)
    }

    pub(crate) fn request_kill_now(&self) -> Result<()> {
        self.request(ControlAction::Kill)
    }

    fn request(&self, action: ControlAction) -> Result<()> {
        let state = lock_unpoison(&self.inner);
        if let Some(generation) = state.current_generation.as_ref() {
            match generation.request_control(action) {
                Ok(()) => return Ok(()),
                Err(control_error) => {
                    // In delegated mode the direct pidfd names the supervisor,
                    // not the payload leader.  SIGKILLing that endpoint would
                    // bypass its signal-pipe drain path and could orphan
                    // already-forked descendants.  READY proves the supervisor
                    // installed TERM/HUP handling, so a strict pidfd SIGTERM is
                    // the only safe last control attempt.
                    if let Some(supervisor) = &generation.supervisor_pidfd {
                        match supervisor.signal_checked(libc::SIGTERM) {
                            Ok(true) => return Ok(()),
                            Ok(false) => {}
                            Err(_) => {}
                        }
                    }
                    return Err(Error::Backend(format!(
                        "delegated workload control was lost: {control_error}"
                    )));
                }
            }
        }
        if let Some(pidfd) = &state.fallback {
            #[cfg(target_os = "linux")]
            if let Some(pgid) = state.fallback_pgid {
                return signal_process_group_pidfds(
                    pidfd,
                    state.fallback_pid,
                    pgid,
                    state.fallback_start_ticks,
                    action.signal(),
                );
            }
            return pidfd.signal(action.signal());
        }
        #[cfg(all(unix, not(target_os = "linux")))]
        {
            let result = unsafe { libc::kill(state.fallback_pid as libc::pid_t, action.signal()) };
            if result == 0 || std::io::Error::last_os_error().raw_os_error() == Some(libc::ESRCH) {
                return Ok(());
            }
            return Err(Error::Backend(format!(
                "signal workload process: {}",
                std::io::Error::last_os_error()
            )));
        }
        #[cfg(not(all(unix, not(target_os = "linux"))))]
        Err(Error::Backend(
            "race-free workload control is unavailable for this process".into(),
        ))
    }
}

fn lock_unpoison<T>(mutex: &Mutex<T>) -> std::sync::MutexGuard<'_, T> {
    mutex
        .lock()
        .unwrap_or_else(std::sync::PoisonError::into_inner)
}

#[derive(Debug, Clone, Copy)]
enum ControlAction {
    Terminate,
    Kill,
}

impl ControlAction {
    fn signal(self) -> i32 {
        match self {
            Self::Terminate => libc::SIGTERM,
            Self::Kill => libc::SIGKILL,
        }
    }
}

struct GenerationState {
    snapshot: Mutex<GenerationSnapshotState>,
    control: Mutex<Option<std::os::unix::net::UnixStream>>,
    receipt_path: std::path::PathBuf,
    expected_nonce: String,
    expected_unit: String,
    durable_manifest: Option<DurableReceiptManifest>,
    /// Spawn-time capability for the exact systemd-run/supervisor process.
    /// Used only to invoke its drain handler if the authenticated control
    /// stream is lost; it is never reconstructed from a later numeric PID.
    supervisor_pidfd: Option<PidFd>,
    _state_directory: StateDirectoryLease,
}

#[derive(Clone)]
enum StateDirectoryLease {
    Transient {
        _directory: Arc<tempfile::TempDir>,
    },
    /// Durable entries are deliberately not removed on Drop. Only an explicit,
    /// digest-bound ACK may rename and collect them after a durable consumer
    /// commit, so daemon loss cannot turn a valid terminal receipt into absence.
    Durable {
        _entry: Arc<DurableReceiptEntry>,
    },
}

struct DurableReceiptEntry {
    root: PathBuf,
    entry: PathBuf,
    receipt_id: String,
    /// The producer owns this exclusive lease from allocation until the last
    /// custody/prepared handle is dropped. A restart scanner may only import
    /// the entry after the kernel releases this open-file-description lock.
    _producer_lease: ProducerLease,
}

#[cfg(target_os = "linux")]
struct ProducerLease {
    _file: std::fs::File,
}

#[cfg(not(target_os = "linux"))]
struct ProducerLease;

#[cfg(target_os = "linux")]
impl DurableReceiptEntry {
    fn cleanup_proven_pre_start(&self) {
        let Ok(_root_lock) = lock_spool_root(&self.root) else {
            return;
        };
        // The producer lease held by `self` proves that no scanner or ACK owns
        // this entry. Removal is deliberately explicit and non-recursive.
        for name in [
            "supervisor.sock",
            RECEIPT_FILE,
            MANIFEST_FILE,
            PRODUCER_LOCK_FILE,
        ] {
            let _ = std::fs::remove_file(self.entry.join(name));
        }
        let _ = std::fs::remove_dir(&self.entry);
        let _ = sync_directory(&self.root);
    }
}

struct GenerationSnapshotState {
    cached: WorkloadResourceSnapshot,
    receipt_loaded: bool,
}

impl GenerationState {
    fn snapshot(&self) -> WorkloadResourceSnapshot {
        // Only the runtime's sole-reaper path may call `seal()` and admit a
        // terminal file.  Merely seeing the pathname while the supervisor is
        // live is not terminal authority and must remain Pending.
        lock_unpoison(&self.snapshot).cached.clone()
    }

    fn request_control(&self, action: ControlAction) -> Result<()> {
        use std::io::Write;
        let mut stream = lock_unpoison(&self.control);
        let Some(stream) = stream.as_mut() else {
            return Err(Error::Backend(
                "workload supervisor control channel closed".into(),
            ));
        };
        let command = match action {
            ControlAction::Terminate => "terminate",
            ControlAction::Kill => "kill",
        };
        serde_json::to_writer(&mut *stream, &ControlMessage { command })
            .and_then(|()| stream.write_all(b"\n").map_err(serde_json::Error::io))
            .map_err(|error| Error::Backend(format!("send workload control: {error}")))
    }

    fn seal(&self) {
        let mut state = lock_unpoison(&self.snapshot);
        if !state.receipt_loaded {
            if self.receipt_path.is_file() {
                match read_receipt(
                    &self.receipt_path,
                    &self.expected_nonce,
                    &self.expected_unit,
                    self.durable_manifest.as_ref(),
                ) {
                    Ok(mut receipt) => {
                        if let Some(manifest) = &self.durable_manifest {
                            receipt.resources.durable_receipts = vec![DurableWorkloadReceiptRef {
                                receipt_id: manifest.receipt_id.clone(),
                                sha256: receipt.sha256,
                            }];
                        }
                        state.cached = receipt.resources;
                    }
                    Err(error) => {
                        state.cached.status = WorkloadResourceStatus::Partial;
                        state
                            .cached
                            .incomplete_reasons
                            .push(format!("terminal receipt invalid: {error}"));
                    }
                }
            } else {
                state.cached.status = WorkloadResourceStatus::Unavailable;
                state
                    .cached
                    .incomplete_reasons
                    .push("supervisor_exited_without_terminal_receipt".into());
            }
            state.receipt_loaded = true;
        }
        drop(state);
        if let Some(stream) = lock_unpoison(&self.control).take() {
            let _ = stream.shutdown(std::net::Shutdown::Both);
        }
    }
}

fn merge_snapshots(
    generations: &[Arc<GenerationState>],
    generation_count: u32,
    unaccounted_generation_count: u32,
) -> WorkloadResourceSnapshot {
    if generations.is_empty() {
        return WorkloadResourceSnapshot {
            status: WorkloadResourceStatus::Unsupported,
            generation_count,
            incomplete_reasons: (unaccounted_generation_count > 0)
                .then(|| {
                    vec![format!(
                        "{unaccounted_generation_count} executed generation(s) lacked delegated cgroup custody"
                    )]
                })
                .unwrap_or_default(),
            ..WorkloadResourceSnapshot::default()
        };
    }
    let snapshots: Vec<_> = generations.iter().map(|state| state.snapshot()).collect();
    let all_complete = snapshots
        .iter()
        .all(|snapshot| snapshot.status == WorkloadResourceStatus::Complete);
    let any_pending = snapshots
        .iter()
        .any(|snapshot| snapshot.status == WorkloadResourceStatus::Pending);
    let all_unavailable = snapshots
        .iter()
        .all(|snapshot| snapshot.status == WorkloadResourceStatus::Unavailable);
    let mut merged = WorkloadResourceSnapshot {
        status: if all_complete {
            WorkloadResourceStatus::Complete
        } else if any_pending {
            WorkloadResourceStatus::Pending
        } else if all_unavailable {
            WorkloadResourceStatus::Unavailable
        } else {
            WorkloadResourceStatus::Partial
        },
        source: Some(SOURCE.into()),
        scope: Some(SCOPE.into()),
        populated_zero_observed: snapshots
            .iter()
            .all(|snapshot| snapshot.populated_zero_observed),
        start_before_exec: snapshots.iter().all(|snapshot| snapshot.start_before_exec),
        complete_for_cpu_memory_workload_tree: snapshots
            .iter()
            .all(|snapshot| snapshot.complete_for_cpu_memory_workload_tree),
        complete_for_pids_workload_tree: snapshots
            .iter()
            .all(|snapshot| snapshot.complete_for_pids_workload_tree),
        generation_count,
        captured_generation_count: snapshots.iter().fold(0u32, |total, snapshot| {
            total.saturating_add(snapshot.captured_generation_count)
        }),
        ..WorkloadResourceSnapshot::default()
    };
    let mut cpu_total_overflow = false;
    let mut cpu_user_overflow = false;
    let mut cpu_system_overflow = false;
    let mut oom_overflow = false;
    let mut oom_kill_overflow = false;
    for snapshot in snapshots {
        for controller in snapshot.controllers {
            if !merged.controllers.contains(&controller) {
                merged.controllers.push(controller);
            }
        }
        cpu_total_overflow |= !sum_option(&mut merged.cpu_usage_usec, snapshot.cpu_usage_usec);
        cpu_user_overflow |= !sum_option(&mut merged.cpu_user_usec, snapshot.cpu_user_usec);
        cpu_system_overflow |= !sum_option(&mut merged.cpu_system_usec, snapshot.cpu_system_usec);
        oom_overflow |= !sum_option(&mut merged.oom_events, snapshot.oom_events);
        oom_kill_overflow |= !sum_option(&mut merged.oom_kill_events, snapshot.oom_kill_events);
        max_option(&mut merged.memory_peak_bytes, snapshot.memory_peak_bytes);
        max_option(&mut merged.pids_peak, snapshot.pids_peak);
        merged
            .incomplete_reasons
            .extend(snapshot.incomplete_reasons);
        merged.durable_receipts.extend(snapshot.durable_receipts);
    }
    if cpu_total_overflow || cpu_user_overflow || cpu_system_overflow {
        if cpu_total_overflow {
            merged.cpu_usage_usec = None;
        }
        if cpu_user_overflow {
            merged.cpu_user_usec = None;
        }
        if cpu_system_overflow {
            merged.cpu_system_usec = None;
        }
        merged.status = WorkloadResourceStatus::Partial;
        merged.complete_for_cpu_memory_workload_tree = false;
        merged
            .incomplete_reasons
            .push("cross-generation CPU counter overflow".into());
    }
    if oom_overflow || oom_kill_overflow {
        if oom_overflow {
            merged.oom_events = None;
        }
        if oom_kill_overflow {
            merged.oom_kill_events = None;
        }
        merged
            .incomplete_reasons
            .push("cross-generation OOM counter overflow".into());
    }
    if unaccounted_generation_count > 0 {
        merged.status = WorkloadResourceStatus::Partial;
        merged.populated_zero_observed = false;
        merged.start_before_exec = false;
        merged.complete_for_cpu_memory_workload_tree = false;
        merged.complete_for_pids_workload_tree = false;
        merged.incomplete_reasons.push(format!(
            "{unaccounted_generation_count} executed generation(s) lacked delegated cgroup custody"
        ));
    }
    merged.controllers.sort();
    merged.durable_receipts.sort();
    merged.durable_receipts.dedup();
    if merged
        .durable_receipts
        .windows(2)
        .any(|pair| pair[0].receipt_id == pair[1].receipt_id)
    {
        merged.status = WorkloadResourceStatus::Partial;
        merged.complete_for_cpu_memory_workload_tree = false;
        merged.complete_for_pids_workload_tree = false;
        merged
            .incomplete_reasons
            .push("durable receipt id was observed with conflicting digests".into());
    }
    merged.incomplete_reasons.sort();
    merged.incomplete_reasons.dedup();
    merged
}

fn sum_option(target: &mut Option<u64>, value: Option<u64>) -> bool {
    if let Some(value) = value {
        let Some(total) = target.unwrap_or(0).checked_add(value) else {
            return false;
        };
        *target = Some(total);
    }
    true
}

fn max_option(target: &mut Option<u64>, value: Option<u64>) {
    if let Some(value) = value {
        *target = Some(target.unwrap_or(0).max(value));
    }
}

#[cfg(target_os = "linux")]
struct PidFd(std::os::fd::OwnedFd);

#[cfg(not(target_os = "linux"))]
struct PidFd;

impl PidFd {
    #[cfg(target_os = "linux")]
    fn open(pid: u32) -> Option<Self> {
        use std::os::fd::FromRawFd;
        let fd = unsafe { libc::syscall(libc::SYS_pidfd_open, pid, 0) as i32 };
        (fd >= 0).then(|| Self(unsafe { std::os::fd::OwnedFd::from_raw_fd(fd) }))
    }

    #[cfg(not(target_os = "linux"))]
    fn open(_pid: u32) -> Option<Self> {
        None
    }

    /// Open a pidfd only while the numeric PID is still bound to the
    /// spawn-time `/proc` identity supplied by the caller. Checking on both
    /// sides of pidfd_open closes the exit/reuse window.
    #[cfg(target_os = "linux")]
    fn open_bound(pid: u32, expected_start_ticks: Option<u64>) -> Option<Self> {
        let expected_start_ticks = expected_start_ticks?;
        if pid == 0
            || proc_process_identity(pid).map(|(_, ticks)| ticks) != Some(expected_start_ticks)
        {
            return None;
        }
        let pidfd = Self::open(pid)?;
        if proc_process_identity(pid).map(|(_, ticks)| ticks) != Some(expected_start_ticks) {
            return None;
        }
        Some(pidfd)
    }

    #[cfg(not(target_os = "linux"))]
    fn open_bound(_pid: u32, _expected_start_ticks: Option<u64>) -> Option<Self> {
        None
    }

    #[cfg(target_os = "linux")]
    fn signal(&self, signal: i32) -> Result<()> {
        self.signal_checked(signal).map(|_| ())
    }

    #[cfg(target_os = "linux")]
    fn signal_checked(&self, signal: i32) -> Result<bool> {
        use std::os::fd::AsRawFd;
        let result = unsafe {
            libc::syscall(
                libc::SYS_pidfd_send_signal,
                self.0.as_raw_fd(),
                signal,
                std::ptr::null::<libc::siginfo_t>(),
                0,
            )
        };
        if result == 0 {
            Ok(true)
        } else {
            let error = std::io::Error::last_os_error();
            if error.raw_os_error() == Some(libc::ESRCH) {
                Ok(false)
            } else {
                Err(Error::Backend(format!("pidfd_send_signal: {error}")))
            }
        }
    }

    #[cfg(not(target_os = "linux"))]
    fn signal(&self, _signal: i32) -> Result<()> {
        Err(Error::Backend("pidfd control is Linux-only".into()))
    }

    #[cfg(not(target_os = "linux"))]
    fn signal_checked(&self, _signal: i32) -> Result<bool> {
        Err(Error::Backend("pidfd control is Linux-only".into()))
    }
}

#[cfg(target_os = "linux")]
fn signal_process_group_pidfds(
    leader: &PidFd,
    leader_pid: u32,
    pgid: u32,
    leader_start_ticks: Option<u64>,
    signal: i32,
) -> Result<()> {
    // A pidfd makes the leader endpoint non-reusable, but Linux exposes no
    // equivalent fd for a process-group epoch.  Require the original leader
    // to remain visible in the expected group before and after enumeration.
    // In AB's sole-reaper paths this includes a zombie leader while inherited
    // descendants still hold stdio open.  Once it has been reaped, declining
    // the fallback is safer than signalling a numerically reused PGID.
    let _leader_identity_guard = leader;
    let Some(leader_start_ticks) = leader_start_ticks else {
        return leader.signal(signal);
    };
    if proc_process_identity(leader_pid) != Some((pgid, leader_start_ticks)) {
        return Ok(());
    }
    let mut members = Vec::new();
    let entries = std::fs::read_dir("/proc")
        .map_err(|error| Error::Backend(format!("enumerate process group members: {error}")))?;
    for entry in entries.flatten() {
        let Some(pid) = entry
            .file_name()
            .to_str()
            .and_then(|value| value.parse::<u32>().ok())
        else {
            continue;
        };
        if proc_process_group(pid) == Some(pgid) {
            if let Some(pidfd) = PidFd::open(pid) {
                members.push((pid, pidfd));
            }
        }
    }
    if proc_process_identity(leader_pid) != Some((pgid, leader_start_ticks)) {
        return Ok(());
    }
    let mut first_error = None;
    for (pid, pidfd) in members {
        if proc_process_group(pid) != Some(pgid) {
            continue;
        }
        if let Err(error) = pidfd.signal(signal) {
            first_error.get_or_insert(error);
        }
    }
    if let Some(error) = first_error {
        Err(error)
    } else {
        Ok(())
    }
}

#[cfg(target_os = "linux")]
fn proc_process_group(pid: u32) -> Option<u32> {
    proc_process_identity(pid).map(|(pgid, _)| pgid)
}

#[cfg(target_os = "linux")]
fn proc_process_identity(pid: u32) -> Option<(u32, u64)> {
    let stat = std::fs::read_to_string(format!("/proc/{pid}/stat")).ok()?;
    let tail = stat.get(stat.rfind(')')? + 1..)?;
    let fields: Vec<_> = tail.split_whitespace().collect();
    Some((fields.get(2)?.parse().ok()?, fields.get(19)?.parse().ok()?))
}

#[cfg(not(target_os = "linux"))]
fn proc_process_identity(_pid: u32) -> Option<(u32, u64)> {
    None
}

#[derive(Serialize)]
struct ControlMessage<'a> {
    command: &'a str,
}

#[derive(Deserialize, Serialize)]
#[serde(deny_unknown_fields)]
struct Receipt {
    schema: u32,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    receipt_id: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    span_id: Option<String>,
    nonce: String,
    unit: String,
    resources: WorkloadResourceSnapshot,
}

#[derive(Debug, Clone, Deserialize, Serialize, PartialEq, Eq)]
#[serde(deny_unknown_fields)]
struct DurableReceiptManifest {
    schema: u32,
    receipt_id: String,
    span_id: String,
    runtime: String,
    unit: String,
    nonce: String,
}

struct ValidatedReceipt {
    resources: WorkloadResourceSnapshot,
    sha256: String,
}

fn read_bounded_protocol_line<R: std::io::BufRead>(reader: &mut R, frame: &str) -> Result<String> {
    use std::io::{BufRead, Read};

    let mut bytes = Vec::new();
    let mut bounded = reader.take((MAX_PROTOCOL_FRAME_BYTES + 1) as u64);
    bounded
        .read_until(b'\n', &mut bytes)
        .map_err(|error| Error::Backend(format!("read cgroup {frame} frame: {error}")))?;
    if bytes.is_empty() {
        return Err(Error::Backend(format!(
            "cgroup {frame} channel closed before a frame"
        )));
    }
    if bytes.len() > MAX_PROTOCOL_FRAME_BYTES {
        return Err(Error::Backend(format!(
            "cgroup {frame} frame exceeds {MAX_PROTOCOL_FRAME_BYTES} bytes"
        )));
    }
    if bytes.last() != Some(&b'\n') {
        return Err(Error::Backend(format!(
            "cgroup {frame} frame is not newline terminated"
        )));
    }
    String::from_utf8(bytes)
        .map_err(|_| Error::Backend(format!("cgroup {frame} frame is not valid UTF-8")))
}

fn valid_controller_list(controllers: &[String]) -> bool {
    controllers.windows(2).all(|pair| pair[0] < pair[1])
        && controllers
            .iter()
            .all(|controller| matches!(controller.as_str(), "cpu" | "memory" | "pids"))
}

fn validate_terminal_snapshot(snapshot: &WorkloadResourceSnapshot) -> Result<()> {
    let cpu_complete = snapshot.complete_for_cpu_memory_workload_tree;
    let pids_complete = snapshot.complete_for_pids_workload_tree;
    let status_consistent = matches!(
        (snapshot.status, cpu_complete),
        (WorkloadResourceStatus::Complete, true) | (WorkloadResourceStatus::Partial, false)
    );
    let cpu_fields_complete = snapshot.controllers.iter().any(|value| value == "cpu")
        && snapshot.controllers.iter().any(|value| value == "memory")
        && snapshot.cpu_usage_usec.is_some()
        && snapshot.cpu_user_usec.is_some()
        && snapshot.cpu_system_usec.is_some()
        && snapshot.memory_peak_bytes.is_some();
    let pids_fields_complete =
        snapshot.controllers.iter().any(|value| value == "pids") && snapshot.pids_peak.is_some();
    let reasons_bounded = snapshot.incomplete_reasons.len() <= 32
        && snapshot
            .incomplete_reasons
            .iter()
            .all(|reason| reason.len() <= 256 && !reason.contains('\0'));

    if snapshot.source.as_deref() != Some(SOURCE)
        || snapshot.scope.as_deref() != Some(SCOPE)
        || !valid_controller_list(&snapshot.controllers)
        || !snapshot.populated_zero_observed
        || !snapshot.start_before_exec
        || snapshot.generation_count != 1
        || snapshot.captured_generation_count != 1
        || !snapshot.durable_receipts.is_empty()
        || !status_consistent
        || (cpu_complete && !cpu_fields_complete)
        || (pids_complete && !pids_fields_complete)
        || !reasons_bounded
    {
        return Err(Error::Backend(
            "workload receipt resource invariants are inconsistent".into(),
        ));
    }
    Ok(())
}

fn read_receipt(
    path: &std::path::Path,
    expected_nonce: &str,
    expected_unit: &str,
    durable_manifest: Option<&DurableReceiptManifest>,
) -> Result<ValidatedReceipt> {
    use std::io::Read;
    use std::os::unix::fs::{MetadataExt, OpenOptionsExt};

    let mut file = std::fs::OpenOptions::new()
        .read(true)
        .custom_flags(libc::O_NOFOLLOW | libc::O_CLOEXEC)
        .open(path)
        .map_err(|error| Error::Backend(format!("open workload receipt: {error}")))?;
    let metadata = file
        .metadata()
        .map_err(|error| Error::Backend(format!("inspect workload receipt: {error}")))?;
    if !metadata.file_type().is_file()
        || metadata.uid() != unsafe { libc::geteuid() }
        || metadata.mode() & 0o077 != 0
        || (durable_manifest.is_some() && metadata.mode() & 0o777 != 0o600)
        || metadata.len() > MAX_PROTOCOL_FRAME_BYTES as u64
    {
        return Err(Error::Backend(
            "workload receipt is not a bounded private regular file".into(),
        ));
    }
    let mut bytes = Vec::new();
    file.by_ref()
        .take((MAX_PROTOCOL_FRAME_BYTES + 1) as u64)
        .read_to_end(&mut bytes)
        .map_err(|error| Error::Backend(format!("read workload receipt: {error}")))?;
    if bytes.len() > MAX_PROTOCOL_FRAME_BYTES {
        return Err(Error::Backend(
            "workload receipt exceeds its size bound".into(),
        ));
    }
    let receipt: Receipt = serde_json::from_slice(&bytes)
        .map_err(|error| Error::Backend(format!("decode workload receipt: {error}")))?;
    if receipt.nonce != expected_nonce || receipt.unit != expected_unit {
        return Err(Error::Backend(
            "workload receipt binding does not match prepared launch".into(),
        ));
    }
    match durable_manifest {
        None => {
            if receipt.schema != 1 || receipt.receipt_id.is_some() || receipt.span_id.is_some() {
                return Err(Error::Backend(format!(
                    "unsupported transient workload receipt schema {}",
                    receipt.schema
                )));
            }
        }
        Some(manifest) => {
            validate_manifest(manifest)?;
            if receipt.schema != DURABLE_RECEIPT_SCHEMA
                || receipt.receipt_id.as_deref() != Some(manifest.receipt_id.as_str())
                || receipt.span_id.as_deref() != Some(manifest.span_id.as_str())
                || receipt.nonce != manifest.nonce
                || receipt.unit != manifest.unit
            {
                return Err(Error::Backend(
                    "durable workload receipt does not match its independent manifest".into(),
                ));
            }
        }
    }
    validate_terminal_snapshot(&receipt.resources)?;
    Ok(ValidatedReceipt {
        resources: receipt.resources,
        sha256: sha256_hex(&bytes),
    })
}

fn sha256_hex(bytes: &[u8]) -> String {
    format!("sha256:{:x}", Sha256::digest(bytes))
}

#[derive(Clone)]
pub(crate) struct PreparedWorkload {
    inner: Arc<PreparedInner>,
}

impl std::fmt::Debug for PreparedWorkload {
    fn fmt(&self, formatter: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        formatter
            .debug_struct("PreparedWorkload")
            .field("prepared", &true)
            .finish_non_exhaustive()
    }
}

struct PreparedInner {
    listener: Mutex<Option<std::os::unix::net::UnixListener>>,
    socket_path: PathBuf,
    receipt_path: PathBuf,
    nonce: String,
    unit: String,
    durable_manifest: Option<DurableReceiptManifest>,
    state_directory: StateDirectoryLease,
    /// Set only after the complete newline-framed START command has been
    /// written successfully. Before that point the target cannot execute, so
    /// dropping the final prepared launch may safely remove its durable stub.
    start_authorized: Arc<std::sync::atomic::AtomicBool>,
}

impl Drop for PreparedInner {
    fn drop(&mut self) {
        use std::sync::atomic::Ordering;
        if self.start_authorized.load(Ordering::Acquire) {
            return;
        }
        #[cfg(target_os = "linux")]
        if let StateDirectoryLease::Durable { _entry } = &self.state_directory {
            _entry.cleanup_proven_pre_start();
        }
    }
}

#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct ReadyMessage {
    schema: u32,
    nonce: String,
    unit: String,
    controllers: Vec<String>,
    start_before_exec: bool,
}

#[derive(Serialize)]
struct StartMessage<'a> {
    command: &'static str,
    nonce: &'a str,
}

/// Apply the outer delegated-scope launch plan after any workspace sandbox
/// launcher has been selected. The sandbox launcher remains the actual target
/// inside `workload/`, so its descendants inherit both controls.
pub(crate) fn wrap_launch_spec(
    mut launch: crate::sandbox::LaunchSpec,
    runtime: &str,
    env: &std::collections::HashMap<String, String>,
    receipt_binding: Option<&str>,
) -> Result<crate::sandbox::LaunchSpec> {
    #[cfg(not(target_os = "linux"))]
    {
        let _ = (runtime, env, receipt_binding);
        return Ok(launch);
    }

    #[cfg(target_os = "linux")]
    {
        if env.contains_key(RECEIPT_DIR_ENV) {
            return Err(Error::InvalidArgument(format!(
                "agent_spawn env cannot override ambient {RECEIPT_DIR_ENV} durable receipt policy"
            )));
        }
        if !custody_enabled(env)? {
            return Ok(launch);
        }
        if let Some(binding) = receipt_binding {
            validate_receipt_binding(binding)?;
        }
        let current_exe = std::env::current_exe().map_err(|error| {
            Error::Backend(format!(
                "{runtime}: resolve cgroup supervisor executable: {error}"
            ))
        })?;
        let current_exe = path_to_utf8(&current_exe, runtime)?;
        let systemd_run = find_in_trusted_path("systemd-run").ok_or_else(|| {
            Error::Backend(format!(
                "{runtime}: cgroup custody enabled but systemd-run is unavailable"
            ))
        })?;
        let systemd_run = path_to_utf8(&systemd_run, runtime)?;
        // Parse every ambient policy value before allocating a durable outbox
        // entry. Unavoidable state-local failures below are covered by the
        // PreparedInner pre-START drop guard.
        let runtime_max_seconds = runtime_max_seconds()?;
        let id = uuid::Uuid::new_v4().simple().to_string();
        let nonce = uuid::Uuid::new_v4().simple().to_string();
        let unit = format!("agent-bridge-agent-{id}.scope");
        let (state_path, state_directory, durable_manifest) = match receipt_binding {
            Some(span_id) => {
                let (path, entry, manifest) =
                    prepare_durable_receipt_entry(runtime, span_id, &unit, &nonce)?;
                (
                    path,
                    StateDirectoryLease::Durable {
                        _entry: Arc::new(entry),
                    },
                    Some(manifest),
                )
            }
            None => {
                let base = runtime_directory().ok_or_else(|| {
                    Error::Backend(format!(
                        "{runtime}: cgroup custody enabled but the user runtime directory is unavailable"
                    ))
                })?;
                let runtime_dir = tempfile::Builder::new()
                    .prefix("agent-bridge-cgroup-")
                    .tempdir_in(&base)
                    .map_err(|error| {
                        Error::Backend(format!(
                            "{runtime}: create private cgroup state directory: {error}"
                        ))
                    })?;
                set_mode(runtime_dir.path(), 0o700)?;
                let runtime_dir = Arc::new(runtime_dir);
                (
                    runtime_dir.path().to_path_buf(),
                    StateDirectoryLease::Transient {
                        _directory: runtime_dir,
                    },
                    None,
                )
            }
        };
        let socket_path = state_path.join("supervisor.sock");
        let receipt_path = state_path.join(RECEIPT_FILE);
        let start_authorized = Arc::new(std::sync::atomic::AtomicBool::new(false));
        let prepared_inner = Arc::new(PreparedInner {
            listener: Mutex::new(None),
            socket_path: socket_path.clone(),
            receipt_path: receipt_path.clone(),
            nonce: nonce.clone(),
            unit: unit.clone(),
            durable_manifest: durable_manifest.clone(),
            state_directory,
            start_authorized,
        });
        let listener = std::os::unix::net::UnixListener::bind(&socket_path).map_err(|error| {
            Error::Backend(format!(
                "{runtime}: bind private cgroup control socket: {error}"
            ))
        })?;
        set_mode(&socket_path, 0o600)?;
        *lock_unpoison(&prepared_inner.listener) = Some(listener);

        // These paths are validated only after PreparedInner exists, so any
        // unexpected encoding failure still removes a provably pre-START
        // durable entry through its drop guard.
        let socket_path_argument = path_to_utf8(&socket_path, runtime)?;
        let receipt_path_argument = path_to_utf8(&receipt_path, runtime)?;

        let original_program = std::mem::take(&mut launch.program);
        let original_args = std::mem::take(&mut launch.args);
        let mut supervisor_args = vec![
            "--user".into(),
            "--scope".into(),
            "--quiet".into(),
            "--collect".into(),
            "--expand-environment=no".into(),
            "--unit".into(),
            unit.clone(),
            "--property".into(),
            "Delegate=cpu memory pids".into(),
            "--property".into(),
            "OOMPolicy=continue".into(),
            "--property".into(),
            format!("RuntimeMaxSec={runtime_max_seconds}"),
            "--".into(),
            current_exe,
            INTERNAL_MARKER.into(),
            "--runtime".into(),
            runtime.into(),
            "--unit".into(),
            unit.clone(),
            "--socket".into(),
            socket_path_argument,
            "--receipt".into(),
            receipt_path_argument,
            "--nonce".into(),
            nonce.clone(),
        ];
        if let Some(manifest) = &durable_manifest {
            supervisor_args.extend([
                "--receipt-id".into(),
                manifest.receipt_id.clone(),
                "--span-id".into(),
                manifest.span_id.clone(),
            ]);
        }
        supervisor_args.extend(["--".into(), original_program]);
        supervisor_args.extend(original_args);
        launch.program = systemd_run;
        launch.args = supervisor_args;
        launch.workload = Some(PreparedWorkload {
            inner: prepared_inner,
        });
        Ok(launch)
    }
}

#[cfg(target_os = "linux")]
fn custody_enabled(env: &std::collections::HashMap<String, String>) -> Result<bool> {
    if env.contains_key(POLICY_ENV) || env.contains_key(RUNTIME_MAX_ENV) {
        return Err(Error::InvalidArgument(format!(
            "agent_spawn env cannot override ambient {POLICY_ENV}/{RUNTIME_MAX_ENV} custody policy"
        )));
    }
    let inherited = std::env::var(POLICY_ENV).ok();
    let requested = inherited
        .as_deref()
        .unwrap_or("auto")
        .trim()
        .to_ascii_lowercase();
    match requested.as_str() {
        "0" | "off" | "false" | "disabled" | "none" => Ok(false),
        "1" | "on" | "true" | "required" => {
            if platform_available() {
                Ok(true)
            } else {
                Err(Error::Backend(
                    "delegated cgroup custody was required but cgroup2/systemd user delegation is unavailable"
                        .into(),
                ))
            }
        }
        "auto" | "" => Ok(production_executable() && platform_available()),
        other => Err(Error::InvalidArgument(format!(
            "invalid {POLICY_ENV} value '{other}'; expected auto, on, or off"
        ))),
    }
}

#[cfg(target_os = "linux")]
fn runtime_max_seconds() -> Result<u64> {
    const DEFAULT: u64 = 24 * 60 * 60;
    const MINIMUM: u64 = 60;
    const MAXIMUM: u64 = 7 * 24 * 60 * 60;
    let Some(value) = std::env::var(RUNTIME_MAX_ENV)
        .ok()
        .filter(|value| !value.trim().is_empty())
    else {
        return Ok(DEFAULT);
    };
    let parsed = value.parse::<u64>().map_err(|_| {
        Error::InvalidArgument(format!(
            "invalid {RUNTIME_MAX_ENV} value; expected seconds in {MINIMUM}..={MAXIMUM}"
        ))
    })?;
    if !(MINIMUM..=MAXIMUM).contains(&parsed) {
        return Err(Error::InvalidArgument(format!(
            "invalid {RUNTIME_MAX_ENV} value; expected seconds in {MINIMUM}..={MAXIMUM}"
        )));
    }
    Ok(parsed)
}

#[cfg(target_os = "linux")]
fn production_executable() -> bool {
    std::env::current_exe()
        .ok()
        .and_then(|path| path.file_name().map(|name| name.to_owned()))
        .and_then(|name| name.to_str().map(str::to_owned))
        .is_some_and(|name| matches!(name.as_str(), "agent-bridge" | "agent-bridge.real"))
}

#[cfg(target_os = "linux")]
fn platform_available() -> bool {
    Path::new("/sys/fs/cgroup/cgroup.controllers").is_file()
        && runtime_directory()
            .map(|path| path.join("bus").exists())
            .unwrap_or(false)
        && find_in_trusted_path("systemd-run").is_some()
}

#[cfg(target_os = "linux")]
fn runtime_directory() -> Option<PathBuf> {
    use std::os::unix::fs::MetadataExt;
    let uid = unsafe { libc::geteuid() };
    let path = std::env::var_os("XDG_RUNTIME_DIR")
        .map(PathBuf::from)
        .unwrap_or_else(|| PathBuf::from(format!("/run/user/{uid}")));
    let metadata = std::fs::symlink_metadata(&path).ok()?;
    (metadata.is_dir() && metadata.uid() == uid && metadata.file_type().is_dir()).then_some(path)
}

#[cfg(target_os = "linux")]
fn find_in_trusted_path(program: &str) -> Option<PathBuf> {
    ["/usr/bin", "/bin"]
        .into_iter()
        .map(|directory| Path::new(directory).join(program))
        .find(|candidate| candidate.is_file())
}

fn path_to_utf8(path: &Path, runtime: &str) -> Result<String> {
    path.to_str()
        .map(str::to_owned)
        .ok_or_else(|| Error::Backend(format!("{runtime}: cgroup custody path is not valid UTF-8")))
}

#[cfg(unix)]
fn set_mode(path: &Path, mode: u32) -> Result<()> {
    use std::os::unix::fs::PermissionsExt;
    std::fs::set_permissions(path, std::fs::Permissions::from_mode(mode))
        .map_err(|error| Error::Backend(format!("secure private cgroup custody state: {error}")))
}

fn validate_receipt_id(receipt_id: &str) -> Result<()> {
    if receipt_id.len() != 32
        || !receipt_id
            .bytes()
            .all(|byte| byte.is_ascii_digit() || (b'a'..=b'f').contains(&byte))
    {
        return Err(Error::InvalidArgument(
            "durable workload receipt id must be 32 lowercase hexadecimal bytes".into(),
        ));
    }
    Ok(())
}

fn validate_receipt_binding(binding: &str) -> Result<()> {
    if binding.is_empty()
        || binding.len() > MAX_RECEIPT_BINDING_BYTES
        || binding.chars().any(char::is_control)
    {
        return Err(Error::InvalidArgument(format!(
            "durable workload receipt binding must be 1..={MAX_RECEIPT_BINDING_BYTES} non-control UTF-8 bytes"
        )));
    }
    Ok(())
}

fn validate_manifest(manifest: &DurableReceiptManifest) -> Result<()> {
    if manifest.schema != DURABLE_MANIFEST_SCHEMA {
        return Err(Error::Backend(format!(
            "unsupported durable workload manifest schema {}",
            manifest.schema
        )));
    }
    validate_receipt_id(&manifest.receipt_id)
        .map_err(|error| Error::Backend(format!("invalid durable receipt manifest: {error}")))?;
    validate_receipt_binding(&manifest.span_id)
        .map_err(|error| Error::Backend(format!("invalid durable receipt manifest: {error}")))?;
    if manifest.runtime.is_empty()
        || manifest.runtime.len() > 128
        || manifest.runtime.chars().any(char::is_control)
        || !manifest.unit.starts_with("agent-bridge-agent-")
        || !manifest.unit.ends_with(".scope")
        || manifest.unit.len() > 96
        || !manifest
            .unit
            .chars()
            .all(|character| character.is_ascii_alphanumeric() || matches!(character, '-' | '.'))
        || manifest.nonce.len() != 32
        || !manifest.nonce.bytes().all(|byte| byte.is_ascii_hexdigit())
    {
        return Err(Error::Backend(
            "durable workload receipt manifest fields are malformed or unbounded".into(),
        ));
    }
    Ok(())
}

#[cfg(target_os = "linux")]
fn durable_receipt_root() -> Result<PathBuf> {
    let root = if let Some(configured) = std::env::var_os(RECEIPT_DIR_ENV) {
        if configured.is_empty() {
            return Err(Error::InvalidArgument(format!(
                "ambient {RECEIPT_DIR_ENV} cannot be empty"
            )));
        }
        PathBuf::from(configured)
    } else if let Some(database) = std::env::var_os("AGENT_BRIDGE_DB") {
        let database = PathBuf::from(database);
        let parent = database.parent().ok_or_else(|| {
            Error::InvalidArgument(
                "ambient AGENT_BRIDGE_DB has no parent for durable workload receipts".into(),
            )
        })?;
        parent.join("workload-receipts")
    } else if let Some(data_home) = std::env::var_os("XDG_DATA_HOME") {
        PathBuf::from(data_home)
            .join("agent-bridge")
            .join("workload-receipts")
    } else {
        let home = std::env::var_os("HOME").ok_or_else(|| {
            Error::Backend(
                "durable workload receipts require AGENT_BRIDGE_CGROUP_RECEIPT_DIR, AGENT_BRIDGE_DB, XDG_DATA_HOME, or HOME"
                    .into(),
            )
        })?;
        PathBuf::from(home)
            .join(".local")
            .join("share")
            .join("agent-bridge")
            .join("workload-receipts")
    };
    validate_durable_root_path(&root)?;
    ensure_private_directory(&root, true)?;
    Ok(root)
}

#[cfg(target_os = "linux")]
fn validate_durable_root_path(path: &Path) -> Result<()> {
    if !path.is_absolute()
        || path == Path::new("/")
        || path.to_str().is_none()
        || path.components().any(|component| {
            matches!(
                component,
                std::path::Component::ParentDir | std::path::Component::CurDir
            )
        })
    {
        return Err(Error::InvalidArgument(
            "durable workload receipt root must be an absolute, normalized, non-root path".into(),
        ));
    }
    Ok(())
}

#[cfg(target_os = "linux")]
fn ensure_private_directory(path: &Path, create: bool) -> Result<()> {
    use std::os::unix::fs::MetadataExt;

    if create {
        match std::fs::symlink_metadata(path) {
            Ok(_) => {}
            Err(error) if error.kind() == std::io::ErrorKind::NotFound => {
                use std::os::unix::fs::DirBuilderExt;
                let mut builder = std::fs::DirBuilder::new();
                builder.recursive(true).mode(0o700);
                builder.create(path).map_err(|error| {
                    Error::Backend(format!(
                        "create private durable workload receipt directory: {error}"
                    ))
                })?;
                set_mode(path, 0o700)?;
                if let Some(parent) = path.parent() {
                    sync_directory(parent)?;
                }
            }
            Err(error) => {
                return Err(Error::Backend(format!(
                    "inspect durable workload receipt directory before creation: {error}"
                )))
            }
        }
    }
    let metadata = std::fs::symlink_metadata(path).map_err(|error| {
        Error::Backend(format!(
            "inspect private durable workload receipt directory: {error}"
        ))
    })?;
    if !metadata.file_type().is_dir()
        || metadata.uid() != unsafe { libc::geteuid() }
        || metadata.mode() & 0o777 != 0o700
    {
        return Err(Error::Backend(
            "durable workload receipt directory must be a non-symlink owner-bound 0700 directory"
                .into(),
        ));
    }
    Ok(())
}

#[cfg(target_os = "linux")]
struct SpoolRootLock {
    _file: std::fs::File,
}

#[cfg(target_os = "linux")]
enum ProducerLeaseAttempt {
    Acquired(ProducerLease),
    Active,
}

#[cfg(target_os = "linux")]
fn lock_spool_root(root: &Path) -> Result<SpoolRootLock> {
    let file = open_private_lock_file(&root.join(SPOOL_LOCK_FILE), true, false, false)?
        .ok_or_else(|| Error::Backend("durable spool root lock unexpectedly active".into()))?;
    Ok(SpoolRootLock { _file: file })
}

#[cfg(target_os = "linux")]
fn create_producer_lease(entry: &Path) -> Result<ProducerLease> {
    let path = entry.join(PRODUCER_LOCK_FILE);
    let file = open_private_lock_file(&path, true, true, true)?.ok_or_else(|| {
        Error::Backend("new durable producer lock was unexpectedly already leased".into())
    })?;
    Ok(ProducerLease { _file: file })
}

#[cfg(target_os = "linux")]
fn try_acquire_producer_lease(entry: &Path) -> Result<ProducerLeaseAttempt> {
    let path = entry.join(PRODUCER_LOCK_FILE);
    match open_private_lock_file(&path, false, false, true)? {
        Some(file) => Ok(ProducerLeaseAttempt::Acquired(ProducerLease {
            _file: file,
        })),
        None => Ok(ProducerLeaseAttempt::Active),
    }
}

/// Open and exclusively flock one owner-only lock file. `create_new` is used
/// for producer locks; the root lock is persistent and reopened. A nonblocking
/// conflict returns `None`, allowing scanners to report active ownership as a
/// distinct unresolved state rather than misclassifying it as corruption.
#[cfg(target_os = "linux")]
fn open_private_lock_file(
    path: &Path,
    create_if_missing: bool,
    create_exclusive: bool,
    nonblocking: bool,
) -> Result<Option<std::fs::File>> {
    use std::os::fd::AsRawFd;
    use std::os::unix::fs::{MetadataExt, OpenOptionsExt};

    let mut options = std::fs::OpenOptions::new();
    options
        .read(true)
        .write(true)
        .mode(0o600)
        .custom_flags(libc::O_NOFOLLOW | libc::O_CLOEXEC);
    if create_if_missing {
        if create_exclusive {
            options.create_new(true);
        } else {
            options.create(true);
        }
    }
    let file = options.open(path).map_err(|error| {
        Error::Backend(format!(
            "open durable workload lock '{}': {error}",
            path.display()
        ))
    })?;
    let metadata = file.metadata().map_err(|error| {
        Error::Backend(format!(
            "inspect durable workload lock '{}': {error}",
            path.display()
        ))
    })?;
    if !metadata.file_type().is_file()
        || metadata.uid() != unsafe { libc::geteuid() }
        || metadata.mode() & 0o777 != 0o600
        || metadata.len() != 0
    {
        return Err(Error::Backend(format!(
            "durable workload lock '{}' is not an empty owner-bound 0600 regular file",
            path.display()
        )));
    }
    let operation = libc::LOCK_EX | if nonblocking { libc::LOCK_NB } else { 0 };
    loop {
        if unsafe { libc::flock(file.as_raw_fd(), operation) } == 0 {
            return Ok(Some(file));
        }
        let error = std::io::Error::last_os_error();
        if error.kind() == std::io::ErrorKind::Interrupted {
            continue;
        }
        if nonblocking && error.kind() == std::io::ErrorKind::WouldBlock {
            return Ok(None);
        }
        return Err(Error::Backend(format!(
            "lock durable workload file '{}': {error}",
            path.display()
        )));
    }
}

#[cfg(target_os = "linux")]
fn ensure_spool_capacity_locked(root: &Path, maximum: usize) -> Result<()> {
    let entries = std::fs::read_dir(root)
        .map_err(|error| Error::Backend(format!("enumerate durable receipt capacity: {error}")))?;
    let mut count = 0usize;
    for entry in entries {
        let entry = entry.map_err(|error| {
            Error::Backend(format!("inspect durable receipt capacity entry: {error}"))
        })?;
        if entry.file_name() == std::ffi::OsStr::new(SPOOL_LOCK_FILE) {
            continue;
        }
        count = count.saturating_add(1);
        if count >= maximum {
            return Err(Error::Backend(format!(
                "durable workload receipt spool capacity {maximum} is exhausted"
            )));
        }
    }
    Ok(())
}

#[cfg(target_os = "linux")]
fn prepare_durable_receipt_entry(
    runtime: &str,
    span_id: &str,
    unit: &str,
    nonce: &str,
) -> Result<(PathBuf, DurableReceiptEntry, DurableReceiptManifest)> {
    let root = durable_receipt_root()?;
    prepare_durable_receipt_entry_at(&root, runtime, span_id, unit, nonce)
}

#[cfg(target_os = "linux")]
fn prepare_durable_receipt_entry_at(
    root: &Path,
    runtime: &str,
    span_id: &str,
    unit: &str,
    nonce: &str,
) -> Result<(PathBuf, DurableReceiptEntry, DurableReceiptManifest)> {
    prepare_durable_receipt_entry_at_with_limit(
        root,
        runtime,
        span_id,
        unit,
        nonce,
        MAX_DURABLE_RECEIPT_ENTRIES,
    )
}

#[cfg(target_os = "linux")]
fn prepare_durable_receipt_entry_at_with_limit(
    root: &Path,
    runtime: &str,
    span_id: &str,
    unit: &str,
    nonce: &str,
    maximum_entries: usize,
) -> Result<(PathBuf, DurableReceiptEntry, DurableReceiptManifest)> {
    use std::io::Write;
    use std::os::unix::fs::{OpenOptionsExt, PermissionsExt};

    ensure_private_directory(root, false)?;
    let receipt_id = uuid::Uuid::new_v4().simple().to_string();
    let manifest = DurableReceiptManifest {
        schema: DURABLE_MANIFEST_SCHEMA,
        receipt_id: receipt_id.clone(),
        span_id: span_id.to_owned(),
        runtime: runtime.to_owned(),
        unit: unit.to_owned(),
        nonce: nonce.to_owned(),
    };
    validate_manifest(&manifest)?;
    let _root_lock = lock_spool_root(root)?;
    ensure_spool_capacity_locked(root, maximum_entries)?;
    let entry = root.join(format!("receipt-{receipt_id}"));
    {
        use std::os::unix::fs::DirBuilderExt;
        let mut builder = std::fs::DirBuilder::new();
        builder.mode(0o700);
        builder
            .create(&entry)
            .map_err(|error| Error::Backend(format!("create durable receipt entry: {error}")))?;
    }
    if let Err(error) =
        set_mode(&entry, 0o700).and_then(|()| ensure_private_directory(&entry, false))
    {
        let _ = std::fs::remove_dir(&entry);
        return Err(error);
    }
    let producer_lease = match create_producer_lease(&entry) {
        Ok(lease) => lease,
        Err(error) => {
            let _ = std::fs::remove_dir(&entry);
            let _ = sync_directory(root);
            return Err(error);
        }
    };
    let manifest_path = entry.join(MANIFEST_FILE);
    let write_result = (|| -> Result<()> {
        let mut file = std::fs::OpenOptions::new()
            .write(true)
            .create_new(true)
            .mode(0o600)
            .open(&manifest_path)
            .map_err(|error| Error::Backend(format!("create durable receipt manifest: {error}")))?;
        file.set_permissions(std::fs::Permissions::from_mode(0o600))
            .map_err(|error| Error::Backend(format!("secure durable receipt manifest: {error}")))?;
        serde_json::to_writer(&mut file, &manifest)
            .map_err(|error| Error::Backend(format!("encode durable receipt manifest: {error}")))?;
        file.write_all(b"\n")
            .map_err(|error| Error::Backend(format!("finish durable receipt manifest: {error}")))?;
        file.sync_all()
            .map_err(|error| Error::Backend(format!("sync durable receipt manifest: {error}")))?;
        sync_directory(&entry)?;
        sync_directory(root)?;
        Ok(())
    })();
    if let Err(error) = write_result {
        let _ = std::fs::remove_file(&manifest_path);
        let _ = std::fs::remove_file(entry.join(PRODUCER_LOCK_FILE));
        let _ = std::fs::remove_dir(&entry);
        let _ = sync_directory(root);
        return Err(error);
    }
    Ok((
        entry.clone(),
        DurableReceiptEntry {
            root: root.to_path_buf(),
            entry,
            receipt_id,
            _producer_lease: producer_lease,
        },
        manifest,
    ))
}

#[cfg(target_os = "linux")]
fn sync_directory(path: &Path) -> Result<()> {
    use std::os::unix::fs::OpenOptionsExt;
    let directory = std::fs::OpenOptions::new()
        .read(true)
        .custom_flags(libc::O_DIRECTORY | libc::O_NOFOLLOW | libc::O_CLOEXEC)
        .open(path)
        .map_err(|error| Error::Backend(format!("open directory for durable sync: {error}")))?;
    directory
        .sync_all()
        .map_err(|error| Error::Backend(format!("sync durable directory: {error}")))
}

impl crate::sandbox::LaunchSpec {
    /// Complete the authenticated READY/START barrier after the direct child
    /// has been spawned. A prepared launch fails closed: the actual executor
    /// has not started when this method returns an error.
    pub async fn activate_workload_cgroup(
        &self,
        direct_pid: u32,
    ) -> Result<Option<WorkloadGeneration>> {
        self.activate_workload_cgroup_with_identity(direct_pid, None)
            .await
    }

    /// PTY helpers can start a sole-reaper thread before activation. Bind the
    /// numeric PID to the spawn-time `/proc` token before opening a new pidfd,
    /// so a failed fast-exit supervisor cannot redirect cleanup to PID reuse.
    pub(crate) async fn activate_workload_cgroup_with_identity(
        &self,
        direct_pid: u32,
        expected_start_ticks: Option<u64>,
    ) -> Result<Option<WorkloadGeneration>> {
        #[cfg(not(target_os = "linux"))]
        {
            let _ = (direct_pid, expected_start_ticks);
            return Ok(None);
        }
        #[cfg(target_os = "linux")]
        {
            let Some(prepared) = self.workload.clone() else {
                return Ok(None);
            };
            let activated = tokio::task::spawn_blocking(move || {
                prepared.activate(direct_pid, expected_start_ticks)
            })
            .await
            .map_err(|error| Error::Backend(format!("join cgroup activation: {error}")))?;
            activated.map(Some)
        }
    }
}

#[cfg(target_os = "linux")]
impl PreparedWorkload {
    fn activate(
        &self,
        direct_pid: u32,
        expected_start_ticks: Option<u64>,
    ) -> Result<WorkloadGeneration> {
        use std::io::{BufReader, Write};
        if direct_pid == 0 {
            return Err(Error::Backend(
                "delegated cgroup activation requires a nonzero spawned child identity".into(),
            ));
        }
        #[cfg(target_os = "linux")]
        if let Some(expected) = expected_start_ticks {
            if proc_process_identity(direct_pid).map(|(_, ticks)| ticks) != Some(expected) {
                return Err(Error::Backend(
                    "delegated cgroup spawned child identity changed before activation".into(),
                ));
            }
        }
        let direct_pidfd = PidFd::open(direct_pid);
        #[cfg(target_os = "linux")]
        if direct_pidfd.is_none() {
            return Err(Error::Backend(
                "pidfd_open failed for delegated cgroup supervisor".into(),
            ));
        }
        #[cfg(target_os = "linux")]
        if let Some(expected) = expected_start_ticks {
            if proc_process_identity(direct_pid).map(|(_, ticks)| ticks) != Some(expected) {
                return Err(Error::Backend(
                    "delegated cgroup spawned child identity changed during pidfd binding".into(),
                ));
            }
        }
        let mut failure_guard = ActivationFailureGuard::new(
            direct_pidfd
                .as_ref()
                .ok_or_else(|| Error::Backend("cgroup supervisor identity unavailable".into()))?,
        );
        let listener = lock_unpoison(&self.inner.listener).take().ok_or_else(|| {
            Error::Backend("cgroup launch activation was attempted more than once".into())
        })?;
        listener.set_nonblocking(true).map_err(|error| {
            Error::Backend(format!("configure cgroup control listener: {error}"))
        })?;
        let deadline = Instant::now() + Duration::from_secs(15);
        let (mut stream, _) = loop {
            match listener.accept() {
                Ok(connection) => break connection,
                Err(error) if error.kind() == std::io::ErrorKind::WouldBlock => {
                    if Instant::now() >= deadline {
                        return Err(Error::Backend(
                            "timed out waiting for delegated cgroup supervisor READY".into(),
                        ));
                    }
                    std::thread::sleep(Duration::from_millis(10));
                }
                Err(error) => {
                    return Err(Error::Backend(format!(
                        "accept cgroup supervisor control connection: {error}"
                    )));
                }
            }
        };
        stream
            .set_read_timeout(Some(Duration::from_secs(5)))
            .map_err(|error| Error::Backend(format!("configure READY timeout: {error}")))?;
        if let Err(error) = validate_peer(&stream, direct_pid) {
            return Err(error);
        }
        let mut reader = BufReader::new(
            stream
                .try_clone()
                .map_err(|error| Error::Backend(format!("clone cgroup READY socket: {error}")))?,
        );
        let line = read_bounded_protocol_line(&mut reader, "supervisor READY")?;
        let ready: ReadyMessage = serde_json::from_str(&line)
            .map_err(|error| Error::Backend(format!("decode cgroup supervisor READY: {error}")))?;
        if ready.schema != 1
            || ready.nonce != self.inner.nonce
            || ready.unit != self.inner.unit
            || !ready.start_before_exec
            || !valid_controller_list(&ready.controllers)
        {
            return Err(Error::Backend(
                "cgroup supervisor READY failed launch binding validation".into(),
            ));
        }
        stream.set_read_timeout(None).ok();
        stream
            .set_write_timeout(Some(Duration::from_secs(1)))
            .map_err(|error| Error::Backend(format!("configure control write timeout: {error}")))?;
        // START is newline-framed. An error before the final newline cannot be
        // parsed by the bounded supervisor reader; after a successful newline
        // there are no remaining fallible activation steps. TERM is still the
        // safe cleanup choice for any partial transmission.
        failure_guard.start_may_have_been_sent();
        serde_json::to_writer(
            &mut stream,
            &StartMessage {
                command: "start",
                nonce: &self.inner.nonce,
            },
        )
        .and_then(|()| stream.write_all(b"\n").map_err(serde_json::Error::io))
        .map_err(|error| Error::Backend(format!("send cgroup supervisor START: {error}")))?;
        self.inner
            .start_authorized
            .store(true, std::sync::atomic::Ordering::Release);
        let cached = WorkloadResourceSnapshot {
            status: WorkloadResourceStatus::Pending,
            source: Some(SOURCE.into()),
            scope: Some(SCOPE.into()),
            controllers: ready.controllers,
            start_before_exec: true,
            generation_count: 1,
            ..WorkloadResourceSnapshot::default()
        };
        failure_guard.disarm();
        drop(failure_guard);
        let state = Arc::new(GenerationState {
            snapshot: Mutex::new(GenerationSnapshotState {
                cached,
                receipt_loaded: false,
            }),
            control: Mutex::new(Some(stream)),
            receipt_path: self.inner.receipt_path.clone(),
            expected_nonce: self.inner.nonce.clone(),
            expected_unit: self.inner.unit.clone(),
            durable_manifest: self.inner.durable_manifest.clone(),
            supervisor_pidfd: direct_pidfd,
            _state_directory: self.inner.state_directory.clone(),
        });
        let _ = std::fs::remove_file(&self.inner.socket_path);
        Ok(WorkloadGeneration { state })
    }
}

#[cfg(target_os = "linux")]
struct ActivationFailureGuard<'a> {
    supervisor: &'a PidFd,
    start_may_have_been_sent: bool,
    armed: bool,
}

#[cfg(target_os = "linux")]
impl<'a> ActivationFailureGuard<'a> {
    fn new(supervisor: &'a PidFd) -> Self {
        Self {
            supervisor,
            start_may_have_been_sent: false,
            armed: true,
        }
    }

    fn start_may_have_been_sent(&mut self) {
        self.start_may_have_been_sent = true;
    }

    fn disarm(&mut self) {
        self.armed = false;
    }
}

#[cfg(target_os = "linux")]
impl Drop for ActivationFailureGuard<'_> {
    fn drop(&mut self) {
        if self.armed {
            let signal = if self.start_may_have_been_sent {
                libc::SIGTERM
            } else {
                libc::SIGKILL
            };
            let _ = self.supervisor.signal(signal);
        }
    }
}

#[cfg(not(target_os = "linux"))]
struct ActivationFailureGuard<'a> {
    _supervisor: &'a PidFd,
}

#[cfg(not(target_os = "linux"))]
impl<'a> ActivationFailureGuard<'a> {
    fn new(supervisor: &'a PidFd) -> Self {
        Self {
            _supervisor: supervisor,
        }
    }

    fn start_may_have_been_sent(&mut self) {}

    fn disarm(&mut self) {}
}

#[cfg(target_os = "linux")]
fn validate_peer(stream: &std::os::unix::net::UnixStream, expected_pid: u32) -> Result<()> {
    use std::os::fd::AsRawFd;
    let mut credentials: libc::ucred = unsafe { std::mem::zeroed() };
    let mut length = std::mem::size_of::<libc::ucred>() as libc::socklen_t;
    let result = unsafe {
        libc::getsockopt(
            stream.as_raw_fd(),
            libc::SOL_SOCKET,
            libc::SO_PEERCRED,
            (&mut credentials as *mut libc::ucred).cast(),
            &mut length,
        )
    };
    if result != 0 {
        return Err(Error::Backend(format!(
            "read cgroup supervisor peer credentials: {}",
            std::io::Error::last_os_error()
        )));
    }
    if credentials.uid != unsafe { libc::geteuid() }
        || credentials.pid < 0
        || credentials.pid as u32 != expected_pid
    {
        return Err(Error::Backend(
            "cgroup supervisor peer identity does not match spawned child".into(),
        ));
    }
    Ok(())
}

// The hidden supervisor lives below. Keeping the public custody contract above
// platform-neutral lets non-Linux builds degrade explicitly without
// introducing numeric-PID control.

struct SupervisorRequest {
    runtime: String,
    unit: String,
    socket: PathBuf,
    receipt: PathBuf,
    nonce: String,
    receipt_id: Option<String>,
    span_id: Option<String>,
    program: std::ffi::OsString,
    args: Vec<std::ffi::OsString>,
}

/// Called by the `agent-bridge` executable before ordinary CLI parsing. `None`
/// means the invocation is not the private supervisor protocol; `Some` owns
/// the process and must be returned from `main`.
pub fn run_internal_supervisor_if_requested() -> Option<Result<()>> {
    let args: Vec<std::ffi::OsString> = std::env::args_os().skip(1).collect();
    let request = match parse_supervisor_request(&args) {
        Ok(Some(request)) => request,
        Ok(None) => return None,
        Err(error) => return Some(Err(error)),
    };
    Some(run_supervisor(request))
}

fn parse_supervisor_request(args: &[std::ffi::OsString]) -> Result<Option<SupervisorRequest>> {
    if args.first().and_then(|arg| arg.to_str()) != Some(INTERNAL_MARKER) {
        return Ok(None);
    }
    let mut runtime = None;
    let mut unit = None;
    let mut socket = None;
    let mut receipt = None;
    let mut nonce = None;
    let mut receipt_id = None;
    let mut span_id = None;
    let mut index = 1;
    while index < args.len() {
        match args[index].to_str() {
            Some("--runtime") => parse_supervisor_string(args, &mut index, &mut runtime)?,
            Some("--unit") => parse_supervisor_string(args, &mut index, &mut unit)?,
            Some("--socket") => parse_supervisor_path(args, &mut index, &mut socket)?,
            Some("--receipt") => parse_supervisor_path(args, &mut index, &mut receipt)?,
            Some("--nonce") => parse_supervisor_string(args, &mut index, &mut nonce)?,
            Some("--receipt-id") => parse_supervisor_string(args, &mut index, &mut receipt_id)?,
            Some("--span-id") => parse_supervisor_string(args, &mut index, &mut span_id)?,
            Some("--") => {
                index += 1;
                break;
            }
            Some(other) => {
                return Err(Error::InvalidArgument(format!(
                    "cgroup supervisor: unknown option '{other}'"
                )));
            }
            None => {
                return Err(Error::InvalidArgument(
                    "cgroup supervisor option is not valid UTF-8".into(),
                ));
            }
        }
    }
    let runtime = required_supervisor_value(runtime, "runtime")?;
    let unit = required_supervisor_value(unit, "unit")?;
    let nonce = required_supervisor_value(nonce, "nonce")?;
    if !unit.starts_with("agent-bridge-agent-")
        || !unit.ends_with(".scope")
        || unit.len() > 96
        || !unit
            .chars()
            .all(|character| character.is_ascii_alphanumeric() || matches!(character, '-' | '.'))
    {
        return Err(Error::InvalidArgument(
            "cgroup supervisor: invalid private unit name".into(),
        ));
    }
    if nonce.len() != 32 || !nonce.bytes().all(|byte| byte.is_ascii_hexdigit()) {
        return Err(Error::InvalidArgument(
            "cgroup supervisor: invalid launch nonce".into(),
        ));
    }
    match (&receipt_id, &span_id) {
        (None, None) => {}
        (Some(receipt_id), Some(span_id)) => {
            validate_receipt_id(receipt_id)?;
            validate_receipt_binding(span_id)?;
        }
        _ => {
            return Err(Error::InvalidArgument(
                "cgroup supervisor: durable receipt id and span binding must appear together"
                    .into(),
            ));
        }
    }
    let socket = socket
        .ok_or_else(|| Error::InvalidArgument("cgroup supervisor: missing --socket".into()))?;
    let receipt = receipt
        .ok_or_else(|| Error::InvalidArgument("cgroup supervisor: missing --receipt".into()))?;
    if socket.parent().is_none() || socket.parent() != receipt.parent() {
        return Err(Error::InvalidArgument(
            "cgroup supervisor: state paths must share a private directory".into(),
        ));
    }
    let program = args.get(index).cloned().ok_or_else(|| {
        Error::InvalidArgument("cgroup supervisor: missing target after --".into())
    })?;
    if program.is_empty() {
        return Err(Error::InvalidArgument(
            "cgroup supervisor: target program is empty".into(),
        ));
    }
    Ok(Some(SupervisorRequest {
        runtime,
        unit,
        socket,
        receipt,
        nonce,
        receipt_id,
        span_id,
        program,
        args: args[index + 1..].to_vec(),
    }))
}

fn parse_supervisor_string(
    args: &[std::ffi::OsString],
    index: &mut usize,
    slot: &mut Option<String>,
) -> Result<()> {
    let option = args[*index].to_string_lossy().into_owned();
    if slot.is_some() {
        return Err(Error::InvalidArgument(format!(
            "cgroup supervisor: duplicate {option}"
        )));
    }
    let value = args.get(*index + 1).ok_or_else(|| {
        Error::InvalidArgument(format!("cgroup supervisor: {option} requires a value"))
    })?;
    *slot = Some(
        value
            .to_str()
            .ok_or_else(|| {
                Error::InvalidArgument(format!(
                    "cgroup supervisor: {option} value is not valid UTF-8"
                ))
            })?
            .to_owned(),
    );
    *index += 2;
    Ok(())
}

fn parse_supervisor_path(
    args: &[std::ffi::OsString],
    index: &mut usize,
    slot: &mut Option<PathBuf>,
) -> Result<()> {
    let option = args[*index].to_string_lossy().into_owned();
    if slot.is_some() {
        return Err(Error::InvalidArgument(format!(
            "cgroup supervisor: duplicate {option}"
        )));
    }
    let value = args.get(*index + 1).ok_or_else(|| {
        Error::InvalidArgument(format!("cgroup supervisor: {option} requires a value"))
    })?;
    *slot = Some(PathBuf::from(value));
    *index += 2;
    Ok(())
}

fn required_supervisor_value(value: Option<String>, name: &str) -> Result<String> {
    value
        .filter(|value| !value.is_empty())
        .ok_or_else(|| Error::InvalidArgument(format!("cgroup supervisor: missing --{name}")))
}

#[cfg(not(target_os = "linux"))]
fn run_supervisor(_request: SupervisorRequest) -> Result<()> {
    Err(Error::Backend(
        "delegated cgroup supervisor is supported only on Linux".into(),
    ))
}

#[cfg(target_os = "linux")]
fn run_supervisor(request: SupervisorRequest) -> Result<()> {
    use std::io::{BufReader, Write};
    use std::os::unix::process::CommandExt;
    use std::sync::atomic::{AtomicBool, Ordering};

    validate_state_paths(&request)?;
    let root = delegated_scope_root(&request.unit)?;
    let supervisor = root.join("supervisor");
    let workload = root.join("workload");
    std::fs::create_dir(&supervisor).map_err(|error| {
        Error::Backend(format!(
            "{}: create delegated supervisor cgroup: {error}",
            request.runtime
        ))
    })?;
    std::fs::create_dir(&workload).map_err(|error| {
        Error::Backend(format!(
            "{}: create delegated workload cgroup: {error}",
            request.runtime
        ))
    })?;
    write_cgroup_file(&supervisor.join("cgroup.procs"), b"0\n")?;
    let root_processes = std::fs::read_to_string(root.join("cgroup.procs"))
        .map_err(|error| Error::Backend(format!("verify delegated scope root: {error}")))?;
    if !root_processes.trim().is_empty() {
        return Err(Error::Backend(
            "delegated scope root still contains processes before controller enablement".into(),
        ));
    }
    let controllers = enable_controllers(&root)?;
    let cgroup_procs = std::fs::OpenOptions::new()
        .write(true)
        .open(workload.join("cgroup.procs"))
        .map_err(|error| Error::Backend(format!("open workload start barrier: {error}")))?;
    validate_workload_endpoints(&workload, &controllers)?;
    let signal_pipe = SupervisorSignalPipe::install()?;

    let mut stream = std::os::unix::net::UnixStream::connect(&request.socket).map_err(|error| {
        Error::Backend(format!(
            "{}: connect private cgroup control socket: {error}",
            request.runtime
        ))
    })?;
    let ready = SupervisorReady {
        schema: 1,
        nonce: &request.nonce,
        unit: &request.unit,
        controllers: &controllers,
        start_before_exec: true,
    };
    serde_json::to_writer(&mut stream, &ready)
        .and_then(|()| stream.write_all(b"\n").map_err(serde_json::Error::io))
        .map_err(|error| Error::Backend(format!("send cgroup supervisor READY: {error}")))?;
    stream
        .set_read_timeout(Some(Duration::from_secs(20)))
        .map_err(|error| Error::Backend(format!("configure START timeout: {error}")))?;
    let mut start_reader = BufReader::new(
        stream
            .try_clone()
            .map_err(|error| Error::Backend(format!("clone START socket: {error}")))?,
    );
    let start_line = read_bounded_protocol_line(&mut start_reader, "supervisor START")?;
    let start: SupervisorStart = serde_json::from_str(&start_line)
        .map_err(|error| Error::Backend(format!("decode cgroup supervisor START: {error}")))?;
    if start.command != "start" || start.nonce != request.nonce {
        return Err(Error::Backend(
            "cgroup supervisor START failed launch binding validation".into(),
        ));
    }
    stream.set_read_timeout(None).ok();

    use std::os::fd::AsRawFd;
    let cgroup_procs_fd = cgroup_procs.as_raw_fd();
    let supervisor_pid = unsafe { libc::getpid() };
    let mut command = std::process::Command::new(&request.program);
    command.args(&request.args);
    unsafe {
        command.pre_exec(move || {
            for signal in [libc::SIGTERM, libc::SIGHUP, libc::SIGINT, libc::SIGPIPE] {
                libc::signal(signal, libc::SIG_DFL);
            }
            // Arm parent death before admission, then close the classic race
            // where the supervisor dies between fork and PR_SET_PDEATHSIG.
            if libc::prctl(libc::PR_SET_PDEATHSIG, libc::SIGKILL) != 0 {
                return Err(std::io::Error::last_os_error());
            }
            if libc::getppid() != supervisor_pid {
                return Err(std::io::Error::other(
                    "delegated workload supervisor changed before exec",
                ));
            }
            let bytes = b"0\n";
            let written = libc::write(cgroup_procs_fd, bytes.as_ptr().cast(), bytes.len());
            if written != bytes.len() as isize {
                return Err(std::io::Error::last_os_error());
            }
            Ok(())
        });
    }
    let mut child = command.spawn().map_err(|error| {
        Error::Backend(format!(
            "{}: spawn delegated workload target: {error}",
            request.runtime
        ))
    })?;
    drop(cgroup_procs);
    let mut drain_guard = WorkloadDrainGuard::new(workload.clone());

    let completed = Arc::new(AtomicBool::new(false));
    let control_completed = completed.clone();
    let control_workload = workload.clone();
    let control_stream = stream
        .try_clone()
        .map_err(|error| Error::Backend(format!("clone workload control socket: {error}")))?;
    let control_thread = std::thread::Builder::new()
        .name("ab-cgroup-control".into())
        .spawn(move || {
            supervise_control_channel(control_stream, &control_workload, &control_completed)
        })
        .map_err(|error| Error::Backend(format!("spawn workload control monitor: {error}")))?;
    let signal_completed = completed.clone();
    let signal_workload = workload.clone();
    let signal_thread = std::thread::Builder::new()
        .name("ab-cgroup-signals".into())
        .spawn(move || {
            signal_pipe.monitor(&signal_workload, &signal_completed);
        })
        .map_err(|error| Error::Backend(format!("spawn workload signal monitor: {error}")))?;

    let status = child
        .wait()
        .map_err(|error| Error::Backend(format!("wait delegated workload leader: {error}")))?;
    wait_populated_zero(&workload)?;
    let resources = collect_resources(&workload, &controllers);
    write_receipt_atomic(
        &request.receipt,
        &Receipt {
            schema: if request.receipt_id.is_some() {
                DURABLE_RECEIPT_SCHEMA
            } else {
                1
            },
            receipt_id: request.receipt_id.clone(),
            span_id: request.span_id.clone(),
            nonce: request.nonce.clone(),
            unit: request.unit.clone(),
            resources,
        },
    )?;
    completed.store(true, Ordering::Release);
    let _ = stream.shutdown(std::net::Shutdown::Both);
    let _ = control_thread.join();
    let _ = signal_thread.join();
    drain_guard.disarm();
    mirror_exit(status)
}

#[cfg(target_os = "linux")]
extern "C" fn supervisor_signal_handler(signal: libc::c_int) {
    use std::sync::atomic::Ordering;
    let fd = SUPERVISOR_SIGNAL_FD.load(Ordering::Relaxed);
    if fd >= 0 {
        let byte = signal as u8;
        unsafe {
            libc::write(fd, (&byte as *const u8).cast(), 1);
        }
    }
}

#[cfg(target_os = "linux")]
struct SupervisorSignalPipe {
    read: std::os::fd::OwnedFd,
    _write: std::os::fd::OwnedFd,
}

#[cfg(target_os = "linux")]
impl SupervisorSignalPipe {
    fn install() -> Result<Self> {
        use std::os::fd::{FromRawFd, IntoRawFd};
        let mut fds = [-1; 2];
        if unsafe { libc::pipe2(fds.as_mut_ptr(), libc::O_CLOEXEC | libc::O_NONBLOCK) } != 0 {
            return Err(Error::Backend(format!(
                "create supervisor signal pipe: {}",
                std::io::Error::last_os_error()
            )));
        }
        let read = unsafe { std::os::fd::OwnedFd::from_raw_fd(fds[0]) };
        let write = unsafe { std::os::fd::OwnedFd::from_raw_fd(fds[1]) };
        SUPERVISOR_SIGNAL_FD.store(fds[1], std::sync::atomic::Ordering::Release);
        let mut action: libc::sigaction = unsafe { std::mem::zeroed() };
        action.sa_sigaction = supervisor_signal_handler as *const () as usize;
        unsafe {
            libc::sigemptyset(&mut action.sa_mask);
        }
        action.sa_flags = libc::SA_RESTART;
        for signal in [libc::SIGTERM, libc::SIGHUP] {
            if unsafe { libc::sigaction(signal, &action, std::ptr::null_mut()) } != 0 {
                SUPERVISOR_SIGNAL_FD.store(-1, std::sync::atomic::Ordering::Release);
                return Err(Error::Backend(format!(
                    "install supervisor signal handler: {}",
                    std::io::Error::last_os_error()
                )));
            }
        }
        unsafe {
            libc::signal(libc::SIGINT, libc::SIG_IGN);
            libc::signal(libc::SIGPIPE, libc::SIG_IGN);
        }
        // Make the ownership transfer explicit; both descriptors remain open
        // until the monitor exits and the supervisor seals its receipt.
        let read_fd = read.into_raw_fd();
        let write_fd = write.into_raw_fd();
        Ok(Self {
            read: unsafe { std::os::fd::OwnedFd::from_raw_fd(read_fd) },
            _write: unsafe { std::os::fd::OwnedFd::from_raw_fd(write_fd) },
        })
    }

    fn monitor(self, workload: &Path, completed: &std::sync::atomic::AtomicBool) {
        use std::os::fd::AsRawFd;
        use std::sync::atomic::Ordering;
        let mut kill_requested = false;
        while !completed.load(Ordering::Acquire) {
            let mut byte = 0u8;
            let read =
                unsafe { libc::read(self.read.as_raw_fd(), (&mut byte as *mut u8).cast(), 1) };
            if read == 1 {
                if !kill_requested && matches!(byte as i32, libc::SIGTERM | libc::SIGHUP) {
                    kill_workload_tree(workload);
                    kill_requested = true;
                }
            } else {
                std::thread::sleep(Duration::from_millis(20));
            }
        }
        SUPERVISOR_SIGNAL_FD.store(-1, Ordering::Release);
    }
}

#[cfg(target_os = "linux")]
#[derive(Serialize)]
struct SupervisorReady<'a> {
    schema: u32,
    nonce: &'a str,
    unit: &'a str,
    controllers: &'a [String],
    start_before_exec: bool,
}

#[cfg(target_os = "linux")]
#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct SupervisorStart {
    command: String,
    nonce: String,
}

#[cfg(target_os = "linux")]
fn validate_state_paths(request: &SupervisorRequest) -> Result<()> {
    use std::os::unix::fs::{FileTypeExt, MetadataExt};
    let directory = request.socket.parent().ok_or_else(|| {
        Error::InvalidArgument("cgroup supervisor: socket has no parent directory".into())
    })?;
    let metadata = std::fs::symlink_metadata(directory).map_err(|error| {
        Error::Backend(format!("inspect private cgroup state directory: {error}"))
    })?;
    let uid = unsafe { libc::geteuid() };
    if !metadata.file_type().is_dir()
        || metadata.uid() != uid
        || metadata.mode() & 0o077 != 0
        || !directory.is_absolute()
    {
        return Err(Error::Backend(
            "cgroup supervisor state directory is not private and owner-bound".into(),
        ));
    }
    let socket = std::fs::symlink_metadata(&request.socket)
        .map_err(|error| Error::Backend(format!("inspect cgroup control socket: {error}")))?;
    if !socket.file_type().is_socket() || socket.uid() != uid || socket.mode() & 0o077 != 0 {
        return Err(Error::Backend(
            "cgroup supervisor socket is not private and owner-bound".into(),
        ));
    }
    if request.receipt.exists() {
        return Err(Error::Backend(
            "cgroup supervisor refuses a pre-existing terminal receipt".into(),
        ));
    }
    Ok(())
}

#[cfg(target_os = "linux")]
fn delegated_scope_root(unit: &str) -> Result<PathBuf> {
    let membership = std::fs::read_to_string("/proc/self/cgroup")
        .map_err(|error| Error::Backend(format!("read supervisor cgroup membership: {error}")))?;
    let relative = membership
        .lines()
        .find_map(|line| line.strip_prefix("0::"))
        .ok_or_else(|| {
            Error::Backend("supervisor is not in a native cgroup v2 hierarchy".into())
        })?;
    let relative_path = Path::new(relative);
    if relative_path.file_name().and_then(|value| value.to_str()) != Some(unit)
        || relative_path.components().any(|component| {
            !matches!(
                component,
                std::path::Component::RootDir | std::path::Component::Normal(_)
            )
        })
    {
        return Err(Error::Backend(
            "supervisor is not inside its expected private systemd scope".into(),
        ));
    }
    let root = Path::new("/sys/fs/cgroup").join(relative.trim_start_matches('/'));
    if !root.join("cgroup.controllers").is_file() || !root.join("cgroup.procs").is_file() {
        return Err(Error::Backend(
            "expected delegated cgroup v2 control files are unavailable".into(),
        ));
    }
    let cgroup_type = std::fs::read_to_string(root.join("cgroup.type"))
        .map_err(|error| Error::Backend(format!("read delegated cgroup type: {error}")))?;
    if cgroup_type.trim() != "domain" {
        return Err(Error::Backend(
            "delegated workload requires a domain cgroup".into(),
        ));
    }
    Ok(root)
}

#[cfg(target_os = "linux")]
fn write_cgroup_file(path: &Path, value: &[u8]) -> Result<()> {
    use std::io::Write;
    let endpoint = path
        .file_name()
        .and_then(|name| name.to_str())
        .unwrap_or("control");
    let mut file = std::fs::OpenOptions::new()
        .write(true)
        .open(path)
        .map_err(|error| Error::Backend(format!("open cgroup endpoint {endpoint}: {error}")))?;
    file.write_all(value)
        .map_err(|error| Error::Backend(format!("write cgroup endpoint {endpoint}: {error}")))
}

#[cfg(target_os = "linux")]
fn enable_controllers(root: &Path) -> Result<Vec<String>> {
    let available = std::fs::read_to_string(root.join("cgroup.controllers"))
        .map_err(|error| Error::Backend(format!("read delegated controllers: {error}")))?;
    let requested: Vec<_> = ["cpu", "memory", "pids"]
        .into_iter()
        .filter(|controller| {
            available
                .split_whitespace()
                .any(|value| value == *controller)
        })
        .collect();
    if !requested.is_empty() {
        let value = requested
            .iter()
            .map(|controller| format!("+{controller}"))
            .collect::<Vec<_>>()
            .join(" ");
        write_cgroup_file(&root.join("cgroup.subtree_control"), value.as_bytes())?;
    }
    let enabled = std::fs::read_to_string(root.join("cgroup.subtree_control"))
        .map_err(|error| Error::Backend(format!("read enabled delegated controllers: {error}")))?;
    let mut controllers: Vec<_> = enabled
        .split_whitespace()
        .filter(|controller| matches!(*controller, "cpu" | "memory" | "pids"))
        .map(str::to_owned)
        .collect();
    controllers.sort();
    Ok(controllers)
}

#[cfg(target_os = "linux")]
fn validate_workload_endpoints(root: &Path, controllers: &[String]) -> Result<()> {
    let mut readable = vec!["cgroup.events"];
    if controllers.iter().any(|controller| controller == "cpu") {
        readable.push("cpu.stat");
    }
    if controllers.iter().any(|controller| controller == "memory") {
        readable.extend(["memory.peak", "memory.events"]);
    }
    if controllers.iter().any(|controller| controller == "pids") {
        readable.push("pids.peak");
    }
    for endpoint in readable {
        std::fs::File::open(root.join(endpoint)).map_err(|error| {
            Error::Backend(format!(
                "preflight delegated workload endpoint {endpoint}: {error}"
            ))
        })?;
    }
    std::fs::OpenOptions::new()
        .write(true)
        .open(root.join("cgroup.kill"))
        .map_err(|error| Error::Backend(format!("preflight workload cgroup.kill: {error}")))?;
    Ok(())
}

#[cfg(target_os = "linux")]
#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct SupervisorControl {
    command: String,
}

#[cfg(target_os = "linux")]
fn supervise_control_channel(
    stream: std::os::unix::net::UnixStream,
    workload: &Path,
    completed: &std::sync::atomic::AtomicBool,
) {
    use std::sync::atomic::Ordering;
    let mut reader = std::io::BufReader::new(stream);
    loop {
        let line = match read_bounded_protocol_line(&mut reader, "supervisor control") {
            Ok(line) => line,
            Err(_) => {
                if !completed.load(Ordering::Acquire) {
                    kill_workload_tree(workload);
                }
                return;
            }
        };
        let Ok(control) = serde_json::from_str::<SupervisorControl>(&line) else {
            if !completed.load(Ordering::Acquire) {
                kill_workload_tree(workload);
            }
            return;
        };
        match control.command.as_str() {
            "terminate" => {
                signal_workload_members(workload, libc::SIGTERM);
                // A bounded grace period keeps TERM useful for cleanup while
                // guaranteeing that the recursive subtree eventually empties.
                for _ in 0..20 {
                    if completed.load(Ordering::Acquire) || cgroup_is_empty(workload) {
                        return;
                    }
                    std::thread::sleep(Duration::from_millis(100));
                }
                kill_workload_tree(workload);
            }
            "kill" => kill_workload_tree(workload),
            _ => {
                if !completed.load(Ordering::Acquire) {
                    kill_workload_tree(workload);
                }
                return;
            }
        }
    }
}

#[cfg(target_os = "linux")]
fn signal_workload_members(root: &Path, signal: i32) {
    // Repeat a stable, pidfd-bound scan so fork/exit races cannot redirect a
    // signal to a subsequently reused numeric PID.
    for _ in 0..3 {
        let pids = cgroup_member_pids(root);
        if pids.is_empty() {
            return;
        }
        for pid in pids {
            if let Some(pidfd) = PidFd::open(pid) {
                // pidfd_open itself is stable, but a numeric PID may have been
                // reused between the cgroup scan and pidfd_open. Revalidate
                // current membership before signaling the acquired handle.
                if cgroup_member_pids(root).binary_search(&pid).is_ok() {
                    let _ = pidfd.signal(signal);
                }
            }
        }
        std::thread::sleep(Duration::from_millis(10));
    }
}

#[cfg(target_os = "linux")]
struct WorkloadDrainGuard {
    root: PathBuf,
    armed: bool,
}

#[cfg(target_os = "linux")]
impl WorkloadDrainGuard {
    fn new(root: PathBuf) -> Self {
        Self { root, armed: true }
    }

    fn disarm(&mut self) {
        self.armed = false;
    }
}

#[cfg(target_os = "linux")]
impl Drop for WorkloadDrainGuard {
    fn drop(&mut self) {
        if self.armed {
            kill_workload_tree(&self.root);
        }
    }
}

#[cfg(target_os = "linux")]
fn kill_workload_tree(root: &Path) {
    if write_cgroup_file(&root.join("cgroup.kill"), b"1\n").is_err() {
        signal_workload_members(root, libc::SIGKILL);
    }
}

#[cfg(target_os = "linux")]
fn cgroup_member_pids(root: &Path) -> Vec<u32> {
    let mut directories = vec![root.to_path_buf()];
    let mut pids = std::collections::BTreeSet::new();
    while let Some(directory) = directories.pop() {
        if let Ok(contents) = std::fs::read_to_string(directory.join("cgroup.procs")) {
            pids.extend(
                contents
                    .lines()
                    .filter_map(|line| line.trim().parse::<u32>().ok())
                    .filter(|pid| *pid != 0),
            );
        }
        let Ok(entries) = std::fs::read_dir(&directory) else {
            continue;
        };
        for entry in entries.flatten() {
            if entry.file_type().is_ok_and(|kind| kind.is_dir()) {
                directories.push(entry.path());
            }
        }
    }
    pids.into_iter().collect()
}

#[cfg(target_os = "linux")]
fn cgroup_is_empty(root: &Path) -> bool {
    read_flat_counter(root.join("cgroup.events"), "populated") == Some(0)
}

#[cfg(target_os = "linux")]
fn wait_populated_zero(root: &Path) -> Result<()> {
    let deadline =
        Instant::now() + Duration::from_secs(runtime_max_seconds().unwrap_or(24 * 60 * 60));
    loop {
        match read_flat_counter(root.join("cgroup.events"), "populated") {
            Some(0) => return Ok(()),
            Some(_) => {
                if Instant::now() >= deadline {
                    kill_workload_tree(root);
                    return Err(Error::Backend(
                        "delegated workload exceeded its bounded terminal-empty deadline".into(),
                    ));
                }
                std::thread::sleep(Duration::from_millis(25));
            }
            None => {
                return Err(Error::Backend(
                    "delegated workload cgroup.events lost populated state".into(),
                ));
            }
        }
    }
}

#[cfg(target_os = "linux")]
fn collect_resources(root: &Path, controllers: &[String]) -> WorkloadResourceSnapshot {
    let cpu_stat = read_flat_map(root.join("cpu.stat"));
    let memory_events = read_flat_map(root.join("memory.events"));
    let cpu_enabled = controllers.iter().any(|controller| controller == "cpu");
    let memory_enabled = controllers.iter().any(|controller| controller == "memory");
    let pids_enabled = controllers.iter().any(|controller| controller == "pids");
    let cpu_usage = cpu_stat.get("usage_usec").copied();
    let cpu_user = cpu_stat.get("user_usec").copied();
    let cpu_system = cpu_stat.get("system_usec").copied();
    let memory_peak = read_single_counter(root.join("memory.peak"));
    let pids_peak = read_single_counter(root.join("pids.peak"));
    let mut incomplete_reasons = Vec::new();
    if !cpu_enabled {
        incomplete_reasons.push("cpu controller was not delegated".into());
    } else if cpu_usage.is_none() || cpu_user.is_none() || cpu_system.is_none() {
        incomplete_reasons.push("cpu.stat terminal counters are incomplete".into());
    }
    if !memory_enabled {
        incomplete_reasons.push("memory controller was not delegated".into());
    } else if memory_peak.is_none() {
        incomplete_reasons.push("memory.peak terminal counter is unavailable".into());
    }
    if !pids_enabled {
        incomplete_reasons.push("pids controller was not delegated".into());
    } else if pids_peak.is_none() {
        incomplete_reasons.push("pids.peak terminal counter is unavailable".into());
    }
    let complete = cpu_enabled
        && memory_enabled
        && cpu_usage.is_some()
        && cpu_user.is_some()
        && cpu_system.is_some()
        && memory_peak.is_some();
    WorkloadResourceSnapshot {
        status: if complete {
            WorkloadResourceStatus::Complete
        } else {
            WorkloadResourceStatus::Partial
        },
        source: Some(SOURCE.into()),
        scope: Some(SCOPE.into()),
        controllers: controllers.to_vec(),
        cpu_usage_usec: cpu_usage,
        cpu_user_usec: cpu_user,
        cpu_system_usec: cpu_system,
        memory_peak_bytes: memory_peak,
        pids_peak,
        oom_events: memory_events.get("oom").copied(),
        oom_kill_events: memory_events.get("oom_kill").copied(),
        populated_zero_observed: true,
        start_before_exec: true,
        complete_for_cpu_memory_workload_tree: complete,
        complete_for_pids_workload_tree: pids_enabled && pids_peak.is_some(),
        generation_count: 1,
        captured_generation_count: 1,
        incomplete_reasons,
        durable_receipts: Vec::new(),
    }
}

#[cfg(target_os = "linux")]
fn read_flat_map(path: PathBuf) -> std::collections::HashMap<String, u64> {
    let Ok(contents) = std::fs::read_to_string(path) else {
        return std::collections::HashMap::new();
    };
    if contents.len() > MAX_PROTOCOL_FRAME_BYTES {
        return std::collections::HashMap::new();
    }
    let mut counters = std::collections::HashMap::new();
    for line in contents.lines() {
        if line.len() > 256 {
            return std::collections::HashMap::new();
        }
        let mut fields = line.split_whitespace();
        let (Some(key), Some(value), None) = (fields.next(), fields.next(), fields.next()) else {
            return std::collections::HashMap::new();
        };
        let Ok(value) = value.parse::<u64>() else {
            return std::collections::HashMap::new();
        };
        if counters.insert(key.to_owned(), value).is_some() {
            return std::collections::HashMap::new();
        }
    }
    counters
}

#[cfg(target_os = "linux")]
fn read_flat_counter(path: PathBuf, key: &str) -> Option<u64> {
    read_flat_map(path).get(key).copied()
}

#[cfg(target_os = "linux")]
fn read_single_counter(path: PathBuf) -> Option<u64> {
    std::fs::read_to_string(path).ok()?.trim().parse().ok()
}

#[cfg(target_os = "linux")]
fn write_receipt_atomic(path: &Path, receipt: &Receipt) -> Result<()> {
    use std::io::Write;
    use std::os::unix::fs::{OpenOptionsExt, PermissionsExt};
    let parent = path
        .parent()
        .ok_or_else(|| Error::Backend("workload receipt path has no parent".into()))?;
    let temporary = parent.join(format!(".receipt-{}.tmp", uuid::Uuid::new_v4().simple()));
    let write_result = (|| -> Result<()> {
        let mut file = std::fs::OpenOptions::new()
            .write(true)
            .create_new(true)
            .mode(0o600)
            .open(&temporary)
            .map_err(|error| Error::Backend(format!("create workload receipt: {error}")))?;
        file.set_permissions(std::fs::Permissions::from_mode(0o600))
            .map_err(|error| Error::Backend(format!("secure workload receipt: {error}")))?;
        serde_json::to_writer(&mut file, receipt)
            .map_err(|error| Error::Backend(format!("encode workload receipt: {error}")))?;
        file.write_all(b"\n")
            .map_err(|error| Error::Backend(format!("finish workload receipt: {error}")))?;
        file.sync_all()
            .map_err(|error| Error::Backend(format!("sync workload receipt: {error}")))?;
        std::fs::rename(&temporary, path)
            .map_err(|error| Error::Backend(format!("publish workload receipt: {error}")))?;
        sync_directory(parent)?;
        Ok(())
    })();
    if write_result.is_err() {
        let _ = std::fs::remove_file(&temporary);
    }
    write_result
}

/// Scan the bounded durable outbox without inferring terminal success from an
/// absent scope or missing receipt. The manifest is the independently durable
/// launch binding; a receipt that merely repeats its own identifiers is never
/// admitted without matching that manifest.
#[cfg(target_os = "linux")]
pub fn scan_durable_workload_receipts() -> Result<DurableWorkloadReceiptScan> {
    let root = durable_receipt_root()?;
    scan_durable_workload_receipts_at(&root)
}

#[cfg(target_os = "linux")]
fn scan_durable_workload_receipts_at(root: &Path) -> Result<DurableWorkloadReceiptScan> {
    ensure_private_directory(root, false)?;
    let _root_lock = lock_spool_root(root)?;
    let mut entries = std::fs::read_dir(&root)
        .map_err(|error| Error::Backend(format!("scan durable receipt root: {error}")))?
        .take(MAX_DURABLE_RECEIPT_ENTRIES + 2)
        .collect::<std::result::Result<Vec<_>, _>>()
        .map_err(|error| Error::Backend(format!("enumerate durable receipt root: {error}")))?;
    entries.retain(|entry| entry.file_name() != std::ffi::OsStr::new(SPOOL_LOCK_FILE));
    if entries.len() > MAX_DURABLE_RECEIPT_ENTRIES {
        return Err(Error::Backend(format!(
            "durable workload receipt root exceeds bounded entry limit {MAX_DURABLE_RECEIPT_ENTRIES}"
        )));
    }
    entries.sort_by_key(std::fs::DirEntry::file_name);
    let mut scan = DurableWorkloadReceiptScan::default();
    for entry in entries {
        let name = entry.file_name();
        let Some(name) = name.to_str() else {
            scan.issues.push(durable_issue(
                None,
                "invalid",
                "durable receipt entry name is not valid UTF-8",
            ));
            continue;
        };
        if let Some(receipt_id) = parse_entry_name(name, ".acked-") {
            // The no-replace rename to `.acked-*` is the ACK linearization
            // point. Once it exists, Store has already authorized deletion;
            // the producer lease is no longer an admission boundary. This
            // also makes cleanup restartable if a prior process died after
            // deleting producer.lock but before removing the directory.
            match cleanup_acked_entry(&entry.path()) {
                Ok(()) => {
                    let _ = sync_directory(&root);
                }
                Err(error) => scan.issues.push(durable_issue(
                    Some(receipt_id),
                    "acked_cleanup_pending",
                    &error.to_string(),
                )),
            }
            continue;
        }
        let Some(receipt_id) = parse_entry_name(name, "receipt-") else {
            scan.issues.push(durable_issue(
                None,
                "invalid",
                "unexpected entry in durable workload receipt root",
            ));
            continue;
        };
        let producer_lease = match try_acquire_producer_lease(&entry.path()) {
            Ok(ProducerLeaseAttempt::Acquired(lease)) => lease,
            Ok(ProducerLeaseAttempt::Active) => {
                scan.unresolved.push(durable_issue(
                    Some(receipt_id),
                    "producer_active",
                    "durable receipt producer lease is still held; terminal commit remains unresolved",
                ));
                continue;
            }
            Err(error) => {
                scan.issues.push(durable_issue(
                    Some(receipt_id),
                    "invalid",
                    &error.to_string(),
                ));
                continue;
            }
        };
        match inspect_durable_entry(&entry.path(), &receipt_id) {
            Ok((manifest, Some(mut receipt))) => {
                let receipt_ref = DurableWorkloadReceiptRef {
                    receipt_id: receipt_id.clone(),
                    sha256: receipt.sha256,
                };
                receipt.resources.durable_receipts = vec![receipt_ref.clone()];
                scan.receipts.push(DurableWorkloadReceiptRecord {
                    receipt_ref,
                    span_id: manifest.span_id,
                    runtime: manifest.runtime,
                    resources: receipt.resources,
                });
            }
            Ok((_manifest, None)) => scan.unresolved.push(durable_issue(
                Some(receipt_id),
                "receipt_commit_unknown",
                "durable launch manifest has no valid terminal receipt; terminal completeness is unknown",
            )),
            Err(error) => scan.issues.push(durable_issue(
                Some(receipt_id),
                "invalid",
                &error.to_string(),
            )),
        }
        drop(producer_lease);
    }
    scan.receipts
        .sort_by(|left, right| left.receipt_ref.cmp(&right.receipt_ref));
    scan.unresolved.sort_by(|left, right| {
        left.receipt_id
            .cmp(&right.receipt_id)
            .then(left.reason.cmp(&right.reason))
    });
    scan.issues.sort_by(|left, right| {
        left.receipt_id
            .cmp(&right.receipt_id)
            .then(left.reason.cmp(&right.reason))
    });
    Ok(scan)
}

#[cfg(not(target_os = "linux"))]
pub fn scan_durable_workload_receipts() -> Result<DurableWorkloadReceiptScan> {
    Ok(DurableWorkloadReceiptScan::default())
}

/// Acknowledge one receipt only after its caller has durably and idempotently
/// committed the projection. Rename is the ACK linearization point; cleanup is
/// deliberately best-effort and restart-scannable through the `.acked-*`
/// tombstone. No recursive deletion or caller-supplied path is used.
#[cfg(target_os = "linux")]
pub fn acknowledge_durable_workload_receipt(
    receipt_ref: &DurableWorkloadReceiptRef,
) -> Result<bool> {
    validate_receipt_id(&receipt_ref.receipt_id)?;
    let Some(digest_hex) = receipt_ref.sha256.strip_prefix("sha256:") else {
        return Err(Error::InvalidArgument(
            "durable workload receipt digest must use sha256:<64 lowercase hex>".into(),
        ));
    };
    if digest_hex.len() != 64
        || !digest_hex
            .bytes()
            .all(|byte| byte.is_ascii_digit() || (b'a'..=b'f').contains(&byte))
    {
        return Err(Error::InvalidArgument(
            "durable workload receipt digest must use sha256:<64 lowercase hex>".into(),
        ));
    }
    let root = durable_receipt_root()?;
    acknowledge_durable_workload_receipt_at(&root, receipt_ref)
}

#[cfg(target_os = "linux")]
fn acknowledge_durable_workload_receipt_at(
    root: &Path,
    receipt_ref: &DurableWorkloadReceiptRef,
) -> Result<bool> {
    acknowledge_durable_workload_receipt_at_with_lease(root, receipt_ref, None)
}

#[cfg(target_os = "linux")]
fn acknowledge_durable_workload_receipt_at_with_lease(
    root: &Path,
    receipt_ref: &DurableWorkloadReceiptRef,
    owned_producer_lease: Option<&ProducerLease>,
) -> Result<bool> {
    ensure_private_directory(root, false)?;
    let _root_lock = lock_spool_root(root)?;
    validate_receipt_id(&receipt_ref.receipt_id)?;
    let Some(digest_hex) = receipt_ref.sha256.strip_prefix("sha256:") else {
        return Err(Error::InvalidArgument(
            "durable workload receipt digest must use sha256:<64 lowercase hex>".into(),
        ));
    };
    if digest_hex.len() != 64
        || !digest_hex
            .bytes()
            .all(|byte| byte.is_ascii_digit() || (b'a'..=b'f').contains(&byte))
    {
        return Err(Error::InvalidArgument(
            "durable workload receipt digest must use sha256:<64 lowercase hex>".into(),
        ));
    }
    let pending = root.join(format!("receipt-{}", receipt_ref.receipt_id));
    let acknowledged = root.join(format!(".acked-{}", receipt_ref.receipt_id));

    match std::fs::symlink_metadata(&pending) {
        Ok(_) => {}
        Err(error) if error.kind() == std::io::ErrorKind::NotFound => {
            match std::fs::symlink_metadata(&acknowledged) {
                Ok(_) => {
                    cleanup_acked_entry(&acknowledged)?;
                    sync_directory(root)?;
                }
                Err(error) if error.kind() == std::io::ErrorKind::NotFound => {}
                Err(error) => {
                    return Err(Error::Backend(format!(
                        "inspect acknowledged workload receipt tombstone: {error}"
                    )))
                }
            }
            return Ok(false);
        }
        Err(error) => {
            return Err(Error::Backend(format!(
                "inspect pending durable workload receipt: {error}"
            )))
        }
    }
    let acquired_lease = if owned_producer_lease.is_none() {
        Some(match try_acquire_producer_lease(&pending)? {
            ProducerLeaseAttempt::Acquired(lease) => lease,
            ProducerLeaseAttempt::Active => {
                return Err(Error::Backend(
                    "cannot acknowledge durable receipt while producer lease is active".into(),
                ));
            }
        })
    } else {
        None
    };
    let _producer_lease = owned_producer_lease
        .or(acquired_lease.as_ref())
        .expect("owned or newly acquired producer lease");
    let (_manifest, receipt) = inspect_durable_entry(&pending, &receipt_ref.receipt_id)?;
    let receipt = receipt.ok_or_else(|| {
        Error::Backend(
            "cannot acknowledge a durable workload launch without a terminal receipt".into(),
        )
    })?;
    if receipt.sha256 != receipt_ref.sha256 {
        return Err(Error::Backend(
            "durable workload receipt digest changed before acknowledgement".into(),
        ));
    }
    if let Err(error) = rename_directory_noreplace(&pending, &acknowledged) {
        if std::fs::symlink_metadata(&pending).is_err() {
            if std::fs::symlink_metadata(&acknowledged).is_ok() {
                cleanup_acked_entry(&acknowledged)?;
                sync_directory(root)?;
            }
            return Ok(false);
        }
        return Err(error);
    }
    sync_directory(&root)?;
    if let Err(error) = cleanup_acked_entry(&acknowledged) {
        tracing::warn!(
            receipt_id = %receipt_ref.receipt_id,
            error = %error,
            "durable workload receipt acknowledged; tombstone cleanup deferred"
        );
    } else {
        let _ = sync_directory(&root);
    }
    Ok(true)
}

#[cfg(not(target_os = "linux"))]
pub fn acknowledge_durable_workload_receipt(
    _receipt_ref: &DurableWorkloadReceiptRef,
) -> Result<bool> {
    Err(Error::Backend(
        "durable workload receipt acknowledgement is Linux-only".into(),
    ))
}

#[cfg(target_os = "linux")]
fn durable_issue(
    receipt_id: Option<String>,
    state: &str,
    reason: &str,
) -> DurableWorkloadReceiptIssue {
    DurableWorkloadReceiptIssue {
        receipt_id,
        state: state.chars().take(64).collect(),
        reason: reason.chars().take(512).collect(),
    }
}

#[cfg(target_os = "linux")]
fn parse_entry_name(name: &str, prefix: &str) -> Option<String> {
    let receipt_id = name.strip_prefix(prefix)?;
    validate_receipt_id(receipt_id).ok()?;
    Some(receipt_id.to_owned())
}

#[cfg(target_os = "linux")]
fn inspect_durable_entry(
    entry: &Path,
    expected_receipt_id: &str,
) -> Result<(DurableReceiptManifest, Option<ValidatedReceipt>)> {
    ensure_private_directory(entry, false)?;
    validate_durable_entry_contents(entry)?;
    let manifest_bytes = read_private_durable_file(&entry.join(MANIFEST_FILE), "manifest")?;
    let manifest: DurableReceiptManifest = serde_json::from_slice(&manifest_bytes)
        .map_err(|error| Error::Backend(format!("decode durable receipt manifest: {error}")))?;
    validate_manifest(&manifest)?;
    if manifest.receipt_id != expected_receipt_id {
        return Err(Error::Backend(
            "durable receipt manifest id does not match its entry name".into(),
        ));
    }
    let receipt_path = entry.join(RECEIPT_FILE);
    let receipt = match std::fs::symlink_metadata(&receipt_path) {
        Ok(_) => Some(read_receipt(
            &receipt_path,
            &manifest.nonce,
            &manifest.unit,
            Some(&manifest),
        )?),
        Err(error) if error.kind() == std::io::ErrorKind::NotFound => None,
        Err(error) => {
            return Err(Error::Backend(format!(
                "inspect durable terminal receipt: {error}"
            )))
        }
    };
    Ok((manifest, receipt))
}

#[cfg(target_os = "linux")]
fn validate_durable_entry_contents(entry: &Path) -> Result<()> {
    use std::os::unix::fs::MetadataExt;

    let mut files = std::fs::read_dir(entry)
        .map_err(|error| Error::Backend(format!("enumerate durable receipt entry: {error}")))?
        .take(MAX_DURABLE_ENTRY_FILES + 1)
        .collect::<std::result::Result<Vec<_>, _>>()
        .map_err(|error| Error::Backend(format!("read durable receipt entry: {error}")))?;
    if files.len() > MAX_DURABLE_ENTRY_FILES {
        return Err(Error::Backend(format!(
            "durable receipt entry exceeds bounded file limit {MAX_DURABLE_ENTRY_FILES}"
        )));
    }
    files.sort_by_key(std::fs::DirEntry::file_name);
    for file in files {
        let name = file.file_name();
        let Some(name) = name.to_str() else {
            return Err(Error::Backend(
                "durable receipt file name is not valid UTF-8".into(),
            ));
        };
        let metadata = std::fs::symlink_metadata(file.path())
            .map_err(|error| Error::Backend(format!("inspect durable receipt file: {error}")))?;
        if metadata.file_type().is_symlink() || metadata.uid() != unsafe { libc::geteuid() } {
            return Err(Error::Backend(
                "durable receipt entry contains a symlink or foreign-owned object".into(),
            ));
        }
        match name {
            PRODUCER_LOCK_FILE => {
                if !metadata.file_type().is_file()
                    || metadata.mode() & 0o777 != 0o600
                    || metadata.len() != 0
                {
                    return Err(Error::Backend(
                        "durable producer lease has invalid type, mode, or content".into(),
                    ));
                }
            }
            MANIFEST_FILE | RECEIPT_FILE => {
                if !metadata.file_type().is_file()
                    || metadata.mode() & 0o777 != 0o600
                    || metadata.len() > MAX_PROTOCOL_FRAME_BYTES as u64
                {
                    return Err(Error::Backend(
                        "durable receipt JSON file is not a bounded owner-only regular file".into(),
                    ));
                }
            }
            "supervisor.sock" => {
                use std::os::unix::fs::FileTypeExt;
                if !metadata.file_type().is_socket() || metadata.mode() & 0o777 != 0o600 {
                    return Err(Error::Backend(
                        "durable receipt control socket has invalid type or mode".into(),
                    ));
                }
            }
            _ if valid_receipt_temporary_name(name) => {
                if !metadata.file_type().is_file()
                    || metadata.mode() & 0o777 != 0o600
                    || metadata.len() > MAX_PROTOCOL_FRAME_BYTES as u64
                {
                    return Err(Error::Backend(
                        "durable temporary receipt is not a bounded owner-only regular file".into(),
                    ));
                }
            }
            _ => {
                return Err(Error::Backend(
                    "durable receipt entry contains an unexpected object".into(),
                ))
            }
        }
    }
    Ok(())
}

#[cfg(target_os = "linux")]
fn valid_receipt_temporary_name(name: &str) -> bool {
    name.strip_prefix(".receipt-")
        .and_then(|name| name.strip_suffix(".tmp"))
        .is_some_and(|id| validate_receipt_id(id).is_ok())
}

#[cfg(target_os = "linux")]
fn read_private_durable_file(path: &Path, label: &str) -> Result<Vec<u8>> {
    use std::io::Read;
    use std::os::unix::fs::{MetadataExt, OpenOptionsExt};

    let mut file = std::fs::OpenOptions::new()
        .read(true)
        .custom_flags(libc::O_NOFOLLOW | libc::O_CLOEXEC)
        .open(path)
        .map_err(|error| Error::Backend(format!("open durable receipt {label}: {error}")))?;
    let metadata = file
        .metadata()
        .map_err(|error| Error::Backend(format!("inspect durable receipt {label}: {error}")))?;
    if !metadata.file_type().is_file()
        || metadata.uid() != unsafe { libc::geteuid() }
        || metadata.mode() & 0o777 != 0o600
        || metadata.len() > MAX_PROTOCOL_FRAME_BYTES as u64
    {
        return Err(Error::Backend(format!(
            "durable receipt {label} is not a bounded owner-only regular file"
        )));
    }
    let mut bytes = Vec::new();
    file.by_ref()
        .take((MAX_PROTOCOL_FRAME_BYTES + 1) as u64)
        .read_to_end(&mut bytes)
        .map_err(|error| Error::Backend(format!("read durable receipt {label}: {error}")))?;
    if bytes.len() > MAX_PROTOCOL_FRAME_BYTES {
        return Err(Error::Backend(format!(
            "durable receipt {label} exceeds its size bound"
        )));
    }
    Ok(bytes)
}

#[cfg(target_os = "linux")]
fn rename_directory_noreplace(source: &Path, destination: &Path) -> Result<()> {
    use std::os::unix::ffi::OsStrExt;
    let source = std::ffi::CString::new(source.as_os_str().as_bytes())
        .map_err(|_| Error::Backend("durable receipt source path contains NUL".into()))?;
    let destination = std::ffi::CString::new(destination.as_os_str().as_bytes())
        .map_err(|_| Error::Backend("durable receipt destination path contains NUL".into()))?;
    let result = unsafe {
        libc::renameat2(
            libc::AT_FDCWD,
            source.as_ptr(),
            libc::AT_FDCWD,
            destination.as_ptr(),
            libc::RENAME_NOREPLACE,
        )
    };
    if result == 0 {
        Ok(())
    } else {
        Err(Error::Backend(format!(
            "atomically acknowledge durable receipt: {}",
            std::io::Error::last_os_error()
        )))
    }
}

#[cfg(target_os = "linux")]
fn cleanup_acked_entry(entry: &Path) -> Result<()> {
    ensure_private_directory(entry, false)?;
    validate_durable_entry_contents(entry)?;
    let files = std::fs::read_dir(entry)
        .map_err(|error| Error::Backend(format!("enumerate acknowledged receipt: {error}")))?
        .take(MAX_DURABLE_ENTRY_FILES + 1)
        .collect::<std::result::Result<Vec<_>, _>>()
        .map_err(|error| Error::Backend(format!("read acknowledged receipt: {error}")))?;
    if files.len() > MAX_DURABLE_ENTRY_FILES {
        return Err(Error::Backend(
            "acknowledged receipt exceeds bounded cleanup file limit".into(),
        ));
    }
    for file in files {
        std::fs::remove_file(file.path()).map_err(|error| {
            Error::Backend(format!("remove acknowledged receipt file: {error}"))
        })?;
    }
    std::fs::remove_dir(entry)
        .map_err(|error| Error::Backend(format!("remove acknowledged receipt entry: {error}")))
}

#[cfg(target_os = "linux")]
fn mirror_exit(status: std::process::ExitStatus) -> Result<()> {
    use std::os::unix::process::ExitStatusExt;
    if let Some(code) = status.code() {
        std::process::exit(code);
    }
    if let Some(signal) = status.signal() {
        unsafe {
            libc::signal(signal, libc::SIG_DFL);
            libc::raise(signal);
            libc::_exit(128 + signal);
        }
    }
    Err(Error::Backend(
        "delegated workload exited without a code or signal".into(),
    ))
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::io::Write;
    use std::os::unix::fs::OpenOptionsExt;

    #[cfg(not(target_os = "linux"))]
    #[test]
    fn proc_identity_is_unavailable_without_linux_procfs() {
        assert_eq!(proc_process_identity(std::process::id()), None);
    }

    fn complete_snapshot(cpu: u64, memory: u64, pids: u64) -> WorkloadResourceSnapshot {
        WorkloadResourceSnapshot {
            status: WorkloadResourceStatus::Complete,
            source: Some(SOURCE.into()),
            scope: Some(SCOPE.into()),
            controllers: vec!["cpu".into(), "memory".into(), "pids".into()],
            cpu_usage_usec: Some(cpu),
            cpu_user_usec: Some(cpu / 2),
            cpu_system_usec: Some(cpu - cpu / 2),
            memory_peak_bytes: Some(memory),
            pids_peak: Some(pids),
            oom_events: Some(0),
            oom_kill_events: Some(0),
            populated_zero_observed: true,
            start_before_exec: true,
            complete_for_cpu_memory_workload_tree: true,
            complete_for_pids_workload_tree: true,
            generation_count: 1,
            captured_generation_count: 1,
            incomplete_reasons: Vec::new(),
            durable_receipts: Vec::new(),
        }
    }

    fn generation_with_cached(snapshot: WorkloadResourceSnapshot) -> Arc<GenerationState> {
        let runtime_dir = Arc::new(tempfile::tempdir().expect("runtime dir"));
        Arc::new(GenerationState {
            snapshot: Mutex::new(GenerationSnapshotState {
                cached: snapshot,
                receipt_loaded: true,
            }),
            control: Mutex::new(None),
            receipt_path: runtime_dir.path().join("receipt.json"),
            expected_nonce: "a".repeat(32),
            expected_unit: "agent-bridge-agent-test.scope".into(),
            durable_manifest: None,
            supervisor_pidfd: None,
            _state_directory: StateDirectoryLease::Transient {
                _directory: runtime_dir,
            },
        })
    }

    fn write_private(path: &Path, bytes: &[u8]) {
        let mut file = std::fs::OpenOptions::new()
            .write(true)
            .create_new(true)
            .mode(0o600)
            .open(path)
            .expect("create private fixture");
        file.write_all(bytes).expect("write fixture");
    }

    #[cfg(target_os = "linux")]
    fn durable_fixture(root: &Path, span_id: &str) -> (PathBuf, DurableReceiptManifest) {
        set_mode(root, 0o700).expect("private durable root");
        let (entry, _lease, manifest) = prepare_durable_receipt_entry_at(
            root,
            "test-runtime",
            span_id,
            "agent-bridge-agent-durabletest.scope",
            &"d".repeat(32),
        )
        .expect("prepare durable fixture");
        (entry, manifest)
    }

    #[cfg(target_os = "linux")]
    fn durable_nonlock_entry_count(root: &Path) -> usize {
        std::fs::read_dir(root)
            .expect("read durable root")
            .map(|entry| entry.expect("durable root entry"))
            .filter(|entry| entry.file_name() != std::ffi::OsStr::new(SPOOL_LOCK_FILE))
            .count()
    }

    #[cfg(target_os = "linux")]
    fn write_durable_fixture_receipt(
        entry: &Path,
        manifest: &DurableReceiptManifest,
        snapshot: WorkloadResourceSnapshot,
    ) -> DurableWorkloadReceiptRef {
        write_receipt_atomic(
            &entry.join(RECEIPT_FILE),
            &Receipt {
                schema: DURABLE_RECEIPT_SCHEMA,
                receipt_id: Some(manifest.receipt_id.clone()),
                span_id: Some(manifest.span_id.clone()),
                nonce: manifest.nonce.clone(),
                unit: manifest.unit.clone(),
                resources: snapshot,
            },
        )
        .expect("write durable terminal receipt");
        let (_, receipt) = inspect_durable_entry(entry, &manifest.receipt_id)
            .expect("inspect durable terminal receipt");
        DurableWorkloadReceiptRef {
            receipt_id: manifest.receipt_id.clone(),
            sha256: receipt.expect("terminal receipt").sha256,
        }
    }

    #[test]
    fn merge_sums_counters_takes_peaks_and_tracks_pids_completeness() {
        let first = generation_with_cached(complete_snapshot(11, 100, 2));
        let second = generation_with_cached(complete_snapshot(13, 80, 4));
        let merged = merge_snapshots(&[first, second], 2, 0);
        assert_eq!(merged.status, WorkloadResourceStatus::Complete);
        assert_eq!(merged.cpu_usage_usec, Some(24));
        assert_eq!(merged.memory_peak_bytes, Some(100));
        assert_eq!(merged.pids_peak, Some(4));
        assert_eq!(merged.generation_count, 2);
        assert_eq!(merged.captured_generation_count, 2);
        assert!(merged.complete_for_cpu_memory_workload_tree);
        assert!(merged.complete_for_pids_workload_tree);

        let mut pids_unknown = complete_snapshot(7, 70, 1);
        pids_unknown.controllers.retain(|value| value != "pids");
        pids_unknown.pids_peak = None;
        pids_unknown.complete_for_pids_workload_tree = false;
        let merged = merge_snapshots(
            &[
                generation_with_cached(complete_snapshot(5, 50, 3)),
                generation_with_cached(pids_unknown),
            ],
            2,
            0,
        );
        assert!(merged.complete_for_cpu_memory_workload_tree);
        assert!(!merged.complete_for_pids_workload_tree);
        assert_eq!(merged.pids_peak, Some(3));
    }

    #[test]
    fn merge_deduplicates_and_sorts_durable_receipt_refs() {
        let first_ref = DurableWorkloadReceiptRef {
            receipt_id: "a".repeat(32),
            sha256: format!("sha256:{}", "1".repeat(64)),
        };
        let second_ref = DurableWorkloadReceiptRef {
            receipt_id: "b".repeat(32),
            sha256: format!("sha256:{}", "2".repeat(64)),
        };
        let mut first = complete_snapshot(3, 4, 1);
        first.durable_receipts = vec![second_ref.clone(), first_ref.clone()];
        let mut second = complete_snapshot(5, 6, 2);
        second.durable_receipts = vec![first_ref.clone()];
        let merged = merge_snapshots(
            &[
                generation_with_cached(first),
                generation_with_cached(second),
            ],
            2,
            0,
        );
        assert_eq!(merged.durable_receipts, vec![first_ref, second_ref]);

        let mut conflicting = complete_snapshot(1, 1, 1);
        conflicting.durable_receipts = vec![DurableWorkloadReceiptRef {
            receipt_id: "a".repeat(32),
            sha256: format!("sha256:{}", "9".repeat(64)),
        }];
        let mut original = complete_snapshot(1, 1, 1);
        original.durable_receipts = vec![DurableWorkloadReceiptRef {
            receipt_id: "a".repeat(32),
            sha256: format!("sha256:{}", "1".repeat(64)),
        }];
        let merged = merge_snapshots(
            &[
                generation_with_cached(original),
                generation_with_cached(conflicting),
            ],
            2,
            0,
        );
        assert_eq!(merged.status, WorkloadResourceStatus::Partial);
        assert!(!merged.complete_for_cpu_memory_workload_tree);
    }

    #[cfg(target_os = "linux")]
    #[test]
    fn durable_restart_scan_and_digest_bound_ack_are_idempotent() {
        use std::os::unix::fs::MetadataExt;

        let root = tempfile::tempdir().expect("durable root");
        let (entry, manifest) = durable_fixture(root.path(), "agent-spawn-durable");
        let entry_metadata = std::fs::symlink_metadata(&entry).unwrap();
        assert_eq!(entry_metadata.mode() & 0o777, 0o700);
        let manifest_metadata = std::fs::symlink_metadata(entry.join(MANIFEST_FILE)).unwrap();
        assert_eq!(manifest_metadata.mode() & 0o777, 0o600);
        let expected_ref =
            write_durable_fixture_receipt(&entry, &manifest, complete_snapshot(17, 23, 2));

        let scan = scan_durable_workload_receipts_at(root.path()).expect("restart scan");
        assert!(scan.unresolved.is_empty(), "{:?}", scan.unresolved);
        assert!(scan.issues.is_empty(), "{:?}", scan.issues);
        assert_eq!(scan.receipts.len(), 1);
        assert_eq!(scan.receipts[0].receipt_ref, expected_ref);
        assert_eq!(scan.receipts[0].span_id, "agent-spawn-durable");
        assert_eq!(
            scan.receipts[0].resources.durable_receipts,
            vec![expected_ref.clone()]
        );
        assert!(expected_ref.sha256.starts_with("sha256:"));
        assert_eq!(expected_ref.sha256.len(), 71);

        assert!(
            acknowledge_durable_workload_receipt_at(root.path(), &expected_ref).expect("first ACK")
        );
        assert!(
            !acknowledge_durable_workload_receipt_at(root.path(), &expected_ref)
                .expect("ACK replay")
        );
        assert_eq!(durable_nonlock_entry_count(root.path()), 0);
    }

    #[cfg(target_os = "linux")]
    #[test]
    fn durable_missing_terminal_is_commit_unknown_and_cannot_be_acked() {
        let root = tempfile::tempdir().expect("durable root");
        let (_entry, manifest) = durable_fixture(root.path(), "agent-spawn-pending");
        let scan = scan_durable_workload_receipts_at(root.path()).expect("restart scan");
        assert!(scan.receipts.is_empty());
        assert!(scan.issues.is_empty());
        assert_eq!(scan.unresolved.len(), 1);
        assert_eq!(scan.unresolved[0].state, "receipt_commit_unknown");
        assert!(acknowledge_durable_workload_receipt_at(
            root.path(),
            &DurableWorkloadReceiptRef {
                receipt_id: manifest.receipt_id,
                sha256: format!("sha256:{}", "0".repeat(64)),
            },
        )
        .is_err());
    }

    #[cfg(target_os = "linux")]
    #[test]
    fn durable_manifest_tamper_mode_and_symlink_fail_closed() {
        use std::os::unix::fs::{symlink, PermissionsExt};

        let root = tempfile::tempdir().expect("durable root");
        let (entry, manifest) = durable_fixture(root.path(), "agent-spawn-original");
        write_durable_fixture_receipt(&entry, &manifest, complete_snapshot(7, 8, 1));

        let mut tampered = manifest.clone();
        tampered.span_id = "agent-spawn-tampered".into();
        std::fs::remove_file(entry.join(MANIFEST_FILE)).unwrap();
        write_private(
            &entry.join(MANIFEST_FILE),
            &serde_json::to_vec(&tampered).unwrap(),
        );
        let scan = scan_durable_workload_receipts_at(root.path()).unwrap();
        assert!(scan.receipts.is_empty());
        assert_eq!(scan.issues.len(), 1);

        std::fs::set_permissions(
            entry.join(MANIFEST_FILE),
            std::fs::Permissions::from_mode(0o644),
        )
        .unwrap();
        let scan = scan_durable_workload_receipts_at(root.path()).unwrap();
        assert_eq!(scan.issues.len(), 1);

        std::fs::remove_file(entry.join(MANIFEST_FILE)).unwrap();
        let external = tempfile::tempdir().expect("external symlink target");
        let target = external.path().join("manifest");
        write_private(&target, b"{}");
        symlink(&target, entry.join(MANIFEST_FILE)).unwrap();
        let scan = scan_durable_workload_receipts_at(root.path()).unwrap();
        assert!(scan.receipts.is_empty());
        assert_eq!(scan.issues.len(), 1);
    }

    #[cfg(target_os = "linux")]
    #[test]
    fn durable_ack_rejects_changed_digest_and_scanner_collects_acked_tombstone() {
        let root = tempfile::tempdir().expect("durable root");
        let (entry, manifest) = durable_fixture(root.path(), "agent-spawn-digest");
        let original_ref =
            write_durable_fixture_receipt(&entry, &manifest, complete_snapshot(9, 10, 1));
        std::fs::remove_file(entry.join(RECEIPT_FILE)).unwrap();
        let replacement_ref =
            write_durable_fixture_receipt(&entry, &manifest, complete_snapshot(11, 12, 2));
        assert_ne!(original_ref.sha256, replacement_ref.sha256);
        assert!(
            acknowledge_durable_workload_receipt_at(root.path(), &original_ref).is_err(),
            "stale digest must not ACK replacement content"
        );

        let tombstone = root
            .path()
            .join(format!(".acked-{}", replacement_ref.receipt_id));
        rename_directory_noreplace(&entry, &tombstone).expect("simulate committed ACK rename");
        sync_directory(root.path()).unwrap();
        let scan = scan_durable_workload_receipts_at(root.path()).expect("tombstone cleanup scan");
        assert!(scan.receipts.is_empty());
        assert!(scan.unresolved.is_empty());
        assert!(scan.issues.is_empty(), "{:?}", scan.issues);
        assert_eq!(durable_nonlock_entry_count(root.path()), 0);
    }

    #[cfg(target_os = "linux")]
    #[test]
    fn durable_pre_start_drop_cleans_only_unstarted_entry() {
        use std::sync::atomic::Ordering;

        let root = tempfile::tempdir().expect("durable root");
        set_mode(root.path(), 0o700).unwrap();
        let (entry_path, entry, manifest) = prepare_durable_receipt_entry_at(
            root.path(),
            "test-runtime",
            "agent-spawn-pre-start",
            "agent-bridge-agent-prestart.scope",
            &"e".repeat(32),
        )
        .expect("prepare pre-START entry");
        let socket_path = entry_path.join("supervisor.sock");
        let listener = std::os::unix::net::UnixListener::bind(&socket_path).unwrap();
        set_mode(&socket_path, 0o600).unwrap();
        let start_authorized = Arc::new(std::sync::atomic::AtomicBool::new(false));
        let prepared = Arc::new(PreparedInner {
            listener: Mutex::new(Some(listener)),
            socket_path,
            receipt_path: entry_path.join(RECEIPT_FILE),
            nonce: manifest.nonce.clone(),
            unit: manifest.unit.clone(),
            durable_manifest: Some(manifest),
            state_directory: StateDirectoryLease::Durable {
                _entry: Arc::new(entry),
            },
            start_authorized: start_authorized.clone(),
        });
        drop(prepared);
        assert!(!entry_path.exists());
        assert_eq!(durable_nonlock_entry_count(root.path()), 0);

        let (started_path, started_entry, started_manifest) = prepare_durable_receipt_entry_at(
            root.path(),
            "test-runtime",
            "agent-spawn-started",
            "agent-bridge-agent-started.scope",
            &"f".repeat(32),
        )
        .expect("prepare START-authorized entry");
        let started_socket = started_path.join("supervisor.sock");
        let started_listener = std::os::unix::net::UnixListener::bind(&started_socket).unwrap();
        set_mode(&started_socket, 0o600).unwrap();
        let started = Arc::new(std::sync::atomic::AtomicBool::new(false));
        let prepared = Arc::new(PreparedInner {
            listener: Mutex::new(Some(started_listener)),
            socket_path: started_socket,
            receipt_path: started_path.join(RECEIPT_FILE),
            nonce: started_manifest.nonce.clone(),
            unit: started_manifest.unit.clone(),
            durable_manifest: Some(started_manifest),
            state_directory: StateDirectoryLease::Durable {
                _entry: Arc::new(started_entry),
            },
            start_authorized: started.clone(),
        });
        started.store(true, Ordering::Release);
        drop(prepared);
        assert!(
            started_path.is_dir(),
            "START-authorized entry must survive Drop"
        );
    }

    #[cfg(target_os = "linux")]
    #[test]
    fn durable_scanner_skips_active_producer_then_imports_after_release() {
        use std::os::fd::AsRawFd;
        use std::os::unix::fs::MetadataExt;

        let root = tempfile::tempdir().expect("durable root");
        set_mode(root.path(), 0o700).unwrap();
        let (entry, producer, manifest) = prepare_durable_receipt_entry_at(
            root.path(),
            "test-runtime",
            "agent-spawn-active",
            "agent-bridge-agent-active.scope",
            &"a".repeat(32),
        )
        .expect("prepare active producer");
        let lock_metadata = std::fs::symlink_metadata(entry.join(PRODUCER_LOCK_FILE)).unwrap();
        assert_eq!(lock_metadata.mode() & 0o777, 0o600);
        assert_ne!(
            unsafe { libc::fcntl(producer._producer_lease._file.as_raw_fd(), libc::F_GETFD) }
                & libc::FD_CLOEXEC,
            0
        );
        let expected_ref =
            write_durable_fixture_receipt(&entry, &manifest, complete_snapshot(21, 34, 3));

        let active_scan = scan_durable_workload_receipts_at(root.path()).unwrap();
        assert!(active_scan.receipts.is_empty());
        assert!(active_scan.issues.is_empty(), "{:?}", active_scan.issues);
        assert_eq!(active_scan.unresolved.len(), 1);
        assert_eq!(active_scan.unresolved[0].state, "producer_active");
        assert!(acknowledge_durable_workload_receipt_at(root.path(), &expected_ref).is_err());

        drop(producer);
        let released_scan = scan_durable_workload_receipts_at(root.path()).unwrap();
        assert!(released_scan.unresolved.is_empty());
        assert!(
            released_scan.issues.is_empty(),
            "{:?}",
            released_scan.issues
        );
        assert_eq!(released_scan.receipts.len(), 1);
        assert_eq!(released_scan.receipts[0].receipt_ref, expected_ref);
        assert!(acknowledge_durable_workload_receipt_at(root.path(), &expected_ref).unwrap());
        assert_eq!(durable_nonlock_entry_count(root.path()), 0);
    }

    #[cfg(target_os = "linux")]
    #[test]
    fn durable_scanner_finishes_partially_cleaned_acked_tombstone() {
        let root = tempfile::tempdir().expect("durable root");
        set_mode(root.path(), 0o700).unwrap();
        let (entry, producer, manifest) = prepare_durable_receipt_entry_at(
            root.path(),
            "test-runtime",
            "agent-spawn-acked-cleanup",
            "agent-bridge-agent-acked-cleanup.scope",
            &"c".repeat(32),
        )
        .expect("prepare durable entry");
        let receipt_ref =
            write_durable_fixture_receipt(&entry, &manifest, complete_snapshot(13, 21, 2));
        drop(producer);

        let acknowledged = root
            .path()
            .join(format!(".acked-{}", receipt_ref.receipt_id));
        rename_directory_noreplace(&entry, &acknowledged).expect("linearize ACK tombstone");
        std::fs::remove_file(acknowledged.join(PRODUCER_LOCK_FILE))
            .expect("simulate interrupted tombstone cleanup");

        let scan = scan_durable_workload_receipts_at(root.path()).expect("resume cleanup");
        assert!(scan.receipts.is_empty());
        assert!(scan.unresolved.is_empty());
        assert!(scan.issues.is_empty(), "{:?}", scan.issues);
        assert!(!acknowledged.exists());
        assert_eq!(durable_nonlock_entry_count(root.path()), 0);
    }

    #[cfg(target_os = "linux")]
    #[test]
    fn durable_snapshot_guard_holds_and_owner_acknowledges_exact_digest() {
        let root = tempfile::tempdir().expect("durable root");
        set_mode(root.path(), 0o700).unwrap();
        let (entry, producer, manifest) = prepare_durable_receipt_entry_at(
            root.path(),
            "test-runtime",
            "agent-spawn-handoff",
            "agent-bridge-agent-handoff.scope",
            &"b".repeat(32),
        )
        .expect("prepare guarded producer");
        let receipt_ref =
            write_durable_fixture_receipt(&entry, &manifest, complete_snapshot(55, 89, 5));
        let mut cached = complete_snapshot(55, 89, 5);
        cached.durable_receipts = vec![receipt_ref.clone()];
        let generation = WorkloadGeneration {
            state: Arc::new(GenerationState {
                snapshot: Mutex::new(GenerationSnapshotState {
                    cached,
                    receipt_loaded: true,
                }),
                control: Mutex::new(None),
                receipt_path: entry.join(RECEIPT_FILE),
                expected_nonce: manifest.nonce.clone(),
                expected_unit: manifest.unit.clone(),
                durable_manifest: Some(manifest),
                supervisor_pidfd: None,
                _state_directory: StateDirectoryLease::Durable {
                    _entry: Arc::new(producer),
                },
            }),
        };
        let custody = WorkloadCustody::new(1, None, None, Some(generation));
        let (snapshot, guard) = custody.snapshot_with_lease();
        assert_eq!(snapshot.durable_receipts, vec![receipt_ref.clone()]);
        assert!(!guard.is_empty());
        assert!(guard.covers(&receipt_ref));
        assert!(guard.covers_all(std::slice::from_ref(&receipt_ref)));
        assert_eq!(guard.receipt_ids(), vec![receipt_ref.receipt_id.clone()]);
        let mut wrong_digest = receipt_ref.clone();
        wrong_digest.sha256 = format!("sha256:{}", "0".repeat(64));
        assert!(!guard.covers(&wrong_digest));
        assert!(!guard.covers_all(std::slice::from_ref(&wrong_digest)));
        assert!(guard.acknowledge(&wrong_digest).is_err());

        drop(custody);
        let active_scan = scan_durable_workload_receipts_at(root.path()).unwrap();
        assert_eq!(active_scan.unresolved.len(), 1);
        assert_eq!(active_scan.unresolved[0].state, "producer_active");
        assert!(guard.acknowledge(&receipt_ref).unwrap());
        assert!(!guard.acknowledge(&receipt_ref).unwrap());
        assert_eq!(durable_nonlock_entry_count(root.path()), 0);
    }

    #[cfg(target_os = "linux")]
    #[test]
    fn durable_allocation_is_capacity_admitted_under_root_lock() {
        let root = tempfile::tempdir().expect("durable root");
        set_mode(root.path(), 0o700).unwrap();
        let first = prepare_durable_receipt_entry_at_with_limit(
            root.path(),
            "test-runtime",
            "agent-spawn-capacity-one",
            "agent-bridge-agent-capacity1.scope",
            &"1".repeat(32),
            1,
        )
        .expect("first entry fits capacity");
        assert!(prepare_durable_receipt_entry_at_with_limit(
            root.path(),
            "test-runtime",
            "agent-spawn-capacity-two",
            "agent-bridge-agent-capacity2.scope",
            &"2".repeat(32),
            1,
        )
        .is_err());
        assert_eq!(durable_nonlock_entry_count(root.path()), 1);
        drop(first);
    }

    #[cfg(target_os = "linux")]
    #[test]
    fn durable_directory_sync_and_root_security_fail_closed() {
        use std::os::unix::fs::{symlink, PermissionsExt};

        let root = tempfile::tempdir().expect("durable root");
        set_mode(root.path(), 0o700).unwrap();
        sync_directory(root.path()).expect("directory fsync");

        std::fs::set_permissions(root.path(), std::fs::Permissions::from_mode(0o755)).unwrap();
        assert!(ensure_private_directory(root.path(), false).is_err());
        set_mode(root.path(), 0o700).unwrap();

        let parent = tempfile::tempdir().expect("symlink parent");
        let link = parent.path().join("spool-link");
        symlink(root.path(), &link).unwrap();
        assert!(ensure_private_directory(&link, false).is_err());
        assert!(sync_directory(&link).is_err());
    }

    #[test]
    fn cross_generation_cpu_overflow_fails_closed() {
        let first = generation_with_cached(complete_snapshot(u64::MAX, 10, 1));
        let second = generation_with_cached(complete_snapshot(1, 20, 2));
        let merged = merge_snapshots(&[first, second], 2, 0);
        assert_eq!(merged.status, WorkloadResourceStatus::Partial);
        assert_eq!(merged.cpu_usage_usec, None);
        assert!(!merged.complete_for_cpu_memory_workload_tree);
        assert!(merged
            .incomplete_reasons
            .iter()
            .any(|reason| reason.contains("CPU counter overflow")));
    }

    #[test]
    fn mixed_delegated_and_direct_generations_cannot_be_complete() {
        let delegated = generation_with_cached(complete_snapshot(9, 12, 2));
        let merged = merge_snapshots(&[delegated], 2, 1);
        assert_eq!(merged.status, WorkloadResourceStatus::Partial);
        assert_eq!(merged.generation_count, 2);
        assert_eq!(merged.captured_generation_count, 1);
        assert!(!merged.complete_for_cpu_memory_workload_tree);
        assert!(!merged.complete_for_pids_workload_tree);
    }

    #[test]
    fn historical_delegated_generation_never_controls_current_direct_generation() {
        let delegated = WorkloadGeneration {
            state: generation_with_cached(complete_snapshot(9, 12, 2)),
        };
        let custody = WorkloadCustody::new(0, None, None, Some(delegated));
        assert!(custody.control().is_some());

        custody.begin_generation(0, None);
        assert!(custody.control().is_none());
        assert_eq!(custody.snapshot().generation_count, 2);
        assert_eq!(custody.snapshot().captured_generation_count, 1);
    }

    #[test]
    fn sealed_custody_exposes_no_current_control_after_late_attach() {
        let custody = WorkloadCustody::direct(0, None, None);
        custody.seal();
        custody.attach_generation(WorkloadGeneration {
            state: generation_with_cached(complete_snapshot(3, 4, 1)),
        });
        assert!(custody.control().is_none());
    }

    #[test]
    fn sealed_custody_cannot_reacquire_direct_fallback_on_late_begin() {
        let custody = WorkloadCustody::direct(0, None, None);
        custody.seal();
        custody.begin_generation(std::process::id(), None);
        let state = lock_unpoison(&custody.inner);
        assert!(state.current_generation.is_none());
        assert!(state.fallback.is_none());
    }

    #[test]
    fn protocol_frames_are_bounded_and_newline_terminated() {
        let mut valid = std::io::Cursor::new(b"{\"command\":\"start\"}\n".to_vec());
        assert!(read_bounded_protocol_line(&mut valid, "test").is_ok());

        let mut oversized = vec![b'x'; MAX_PROTOCOL_FRAME_BYTES + 1];
        oversized.push(b'\n');
        let mut oversized = std::io::Cursor::new(oversized);
        assert!(read_bounded_protocol_line(&mut oversized, "test").is_err());

        let mut unterminated = std::io::Cursor::new(b"{}".to_vec());
        assert!(read_bounded_protocol_line(&mut unterminated, "test").is_err());
    }

    #[cfg(target_os = "linux")]
    #[test]
    fn receipt_requires_private_bounded_binding_and_consistent_resources() {
        let dir = tempfile::tempdir().expect("receipt dir");
        let nonce = "b".repeat(32);
        let unit = "agent-bridge-agent-receipt.scope";
        let path = dir.path().join("receipt.json");
        write_receipt_atomic(
            &path,
            &Receipt {
                schema: 1,
                receipt_id: None,
                span_id: None,
                nonce: nonce.clone(),
                unit: unit.into(),
                resources: complete_snapshot(10, 20, 2),
            },
        )
        .expect("write receipt");
        assert!(read_receipt(&path, &nonce, unit, None).is_ok());
        assert!(read_receipt(&path, &"c".repeat(32), unit, None).is_err());

        let oversized = dir.path().join("oversized.json");
        let file = std::fs::OpenOptions::new()
            .write(true)
            .create_new(true)
            .mode(0o600)
            .open(&oversized)
            .expect("oversized fixture");
        file.set_len((MAX_PROTOCOL_FRAME_BYTES + 1) as u64)
            .expect("size oversized fixture");
        assert!(read_receipt(&oversized, &nonce, unit, None).is_err());

        let inconsistent = dir.path().join("inconsistent.json");
        let mut snapshot = complete_snapshot(1, 2, 1);
        snapshot.populated_zero_observed = false;
        write_private(
            &inconsistent,
            &serde_json::to_vec(&Receipt {
                schema: 1,
                receipt_id: None,
                span_id: None,
                nonce,
                unit: unit.into(),
                resources: snapshot,
            })
            .expect("encode inconsistent receipt"),
        );
        assert!(read_receipt(&inconsistent, &"b".repeat(32), unit, None).is_err());
    }

    #[cfg(target_os = "linux")]
    #[test]
    fn late_generation_attachment_observes_prior_seal_latch() {
        let runtime_dir = Arc::new(tempfile::tempdir().expect("runtime dir"));
        let nonce = "d".repeat(32);
        let unit = "agent-bridge-agent-late.scope";
        let receipt_path = runtime_dir.path().join("receipt.json");
        write_receipt_atomic(
            &receipt_path,
            &Receipt {
                schema: 1,
                receipt_id: None,
                span_id: None,
                nonce: nonce.clone(),
                unit: unit.into(),
                resources: complete_snapshot(3, 4, 1),
            },
        )
        .expect("write terminal receipt");
        let generation = WorkloadGeneration {
            state: Arc::new(GenerationState {
                snapshot: Mutex::new(GenerationSnapshotState {
                    cached: WorkloadResourceSnapshot {
                        status: WorkloadResourceStatus::Pending,
                        source: Some(SOURCE.into()),
                        scope: Some(SCOPE.into()),
                        generation_count: 1,
                        ..WorkloadResourceSnapshot::default()
                    },
                    receipt_loaded: false,
                }),
                control: Mutex::new(None),
                receipt_path,
                expected_nonce: nonce,
                expected_unit: unit.into(),
                durable_manifest: None,
                supervisor_pidfd: None,
                _state_directory: StateDirectoryLease::Transient {
                    _directory: runtime_dir,
                },
            }),
        };
        let custody = WorkloadCustody::direct(0, None, None);
        custody.seal();
        custody.attach_generation(generation);
        let snapshot = custody.snapshot();
        assert_eq!(snapshot.status, WorkloadResourceStatus::Complete);
        assert!(snapshot.complete_for_cpu_memory_workload_tree);
    }

    #[cfg(target_os = "linux")]
    #[test]
    fn flat_counter_parser_rejects_duplicates_and_extra_fields() {
        let dir = tempfile::tempdir().expect("counter dir");
        let valid = dir.path().join("valid");
        std::fs::write(&valid, "usage_usec 3\nuser_usec 2\n").expect("valid counters");
        assert_eq!(read_flat_map(valid).get("usage_usec"), Some(&3));

        let duplicate = dir.path().join("duplicate");
        std::fs::write(&duplicate, "usage_usec 3\nusage_usec 4\n").expect("duplicate counters");
        assert!(read_flat_map(duplicate).is_empty());

        let extra = dir.path().join("extra");
        std::fs::write(&extra, "usage_usec 3 trailing\n").expect("extra field counters");
        assert!(read_flat_map(extra).is_empty());
    }

    #[test]
    fn supervisor_parser_rejects_duplicate_private_fields() {
        let args: Vec<std::ffi::OsString> = [
            INTERNAL_MARKER,
            "--runtime",
            "test",
            "--runtime",
            "again",
            "--",
            "/bin/true",
        ]
        .into_iter()
        .map(Into::into)
        .collect();
        assert!(parse_supervisor_request(&args).is_err());
    }
}
