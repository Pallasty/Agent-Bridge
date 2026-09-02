//! Process-local damping for sibling-agent expansion.
//!
//! This is a resource governor, not an authority system. It never grants a
//! capability and it does not trust a caller-supplied task/session identity.
//! When explicitly enabled, one logical `agent_spawn` request reserves one
//! process-local concurrency slot before any runtime is invoked. A successful
//! spawn must then return trusted local-workload custody; the slot remains held
//! until that runtime reports the session terminal. A monotonic TTL requests
//! TERM and then KILL through that custody handle.
//!
//! Configuration is default-off:
//!
//! - `AB_AGENT_SPAWN_GOVERNOR=1|true|yes|on`
//! - `AB_AGENT_SPAWN_MAX_ACTIVE=1..64` (required when enabled)
//! - `AB_AGENT_SPAWN_TTL_SECS=1..86400` (required when enabled)
//! - `AB_AGENT_SPAWN_TERM_GRACE_SECS=0..60` (optional, default 5)
//!
//! The governor deliberately rejects remote/cloud execution while enabled: a
//! local transport process is not custody of the remote workload. Its scope is
//! also one `Hub`/Bridge process. Cross-process inheritance and crash/restart
//! orphan recovery require a later durable authority and custody design.

use ab_agent::{
    AgentRuntime, AgentSession, CapabilitySupport, RuntimeLocality, SpawnedProcessCustody,
    WorkspaceRuntimeContract,
};
use serde::Serialize;
use std::sync::atomic::{AtomicU64, AtomicUsize, Ordering};
use std::sync::{Arc, Mutex};
use std::time::{Duration, Instant, SystemTime, UNIX_EPOCH};
use tokio::sync::{OwnedSemaphorePermit, Semaphore};

pub const ENABLE_ENV: &str = "AB_AGENT_SPAWN_GOVERNOR";
pub const MAX_ACTIVE_ENV: &str = "AB_AGENT_SPAWN_MAX_ACTIVE";
pub const TTL_SECS_ENV: &str = "AB_AGENT_SPAWN_TTL_SECS";
pub const TERM_GRACE_SECS_ENV: &str = "AB_AGENT_SPAWN_TERM_GRACE_SECS";

const MAX_ACTIVE_LIMIT: usize = 64;
const MAX_TTL_SECS: u64 = 86_400;
const MAX_TERM_GRACE_SECS: u64 = 60;
const DEFAULT_TERM_GRACE_SECS: u64 = 5;
const TERMINAL_POLL: Duration = Duration::from_millis(100);

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum AgentSpawnTarget {
    Local,
    Remote,
}

#[derive(Debug, Clone)]
struct EnabledConfig {
    max_active: usize,
    ttl: Duration,
    term_grace: Duration,
}

#[derive(Debug, Clone)]
enum ConfigState {
    Disabled,
    Invalid(String),
    Enabled(EnabledConfig),
}

struct QuarantinedPermit {
    _permit: OwnedSemaphorePermit,
    _reason: String,
}

struct GovernorInner {
    config: ConfigState,
    semaphore: Option<Arc<Semaphore>>,
    reserved_slots: AtomicUsize,
    active_sessions: AtomicUsize,
    quarantined_slots: AtomicUsize,
    capacity_rejections_total: AtomicU64,
    preflight_rejections_total: AtomicU64,
    activation_rejections_total: AtomicU64,
    terminal_releases_total: AtomicU64,
    ttl_expirations_total: AtomicU64,
    term_requests_total: AtomicU64,
    kill_requests_total: AtomicU64,
    monitor_abort_kills_total: AtomicU64,
    quarantined: Mutex<Vec<QuarantinedPermit>>,
}

/// Cloneable governor shared by every tool instance built from one [`crate::hub::Hub`].
#[derive(Clone)]
pub struct AgentSpawnGovernor {
    inner: Arc<GovernorInner>,
}

impl std::fmt::Debug for AgentSpawnGovernor {
    fn fmt(&self, formatter: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        formatter
            .debug_struct("AgentSpawnGovernor")
            .field("snapshot", &self.snapshot())
            .finish()
    }
}

impl Default for AgentSpawnGovernor {
    fn default() -> Self {
        Self::disabled()
    }
}

#[derive(Debug, Clone, Serialize)]
pub struct AgentSpawnGovernorSnapshot {
    pub schema_version: &'static str,
    pub mode: &'static str,
    pub default_off: bool,
    pub process_scoped: bool,
    pub grants_authority: bool,
    pub local_custody_required: bool,
    pub max_active: Option<usize>,
    pub ttl_secs: Option<u64>,
    pub term_grace_secs: Option<u64>,
    pub reserved_slots: usize,
    pub active_sessions: usize,
    pub occupied_slots: usize,
    pub quarantined_slots: usize,
    pub capacity_rejections_total: u64,
    pub preflight_rejections_total: u64,
    pub activation_rejections_total: u64,
    pub terminal_releases_total: u64,
    pub ttl_expirations_total: u64,
    pub term_requests_total: u64,
    pub kill_requests_total: u64,
    pub monitor_abort_kills_total: u64,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub configuration_error: Option<String>,
    pub configuration_env: [&'static str; 4],
}

/// Non-authoritative receipt returned with a governed spawn. The opaque id is
/// diagnostic correlation only; presenting it never grants control or renewal.
#[derive(Debug, Clone, Serialize)]
pub struct AgentSpawnLeaseMetadata {
    pub schema_version: &'static str,
    pub mode: &'static str,
    pub lease_kind: &'static str,
    pub grants_authority: bool,
    pub lease_id: String,
    pub session_id: String,
    pub runtime_id: String,
    pub issued_at_unix_secs: u64,
    pub expires_at_unix_secs: u64,
    pub ttl_secs: u64,
    pub term_grace_secs: u64,
    pub max_active: usize,
    pub occupied_slots: usize,
}

impl AgentSpawnGovernor {
    pub fn disabled() -> Self {
        Self::from_state(ConfigState::Disabled)
    }

    /// Construct a deterministic enforcing governor. Production normally uses
    /// [`Self::from_env`]; this constructor is also useful for embedders/tests.
    pub fn enabled(max_active: usize, ttl_secs: u64, term_grace_secs: u64) -> Result<Self, String> {
        let config = validate_enabled_config(max_active, ttl_secs, term_grace_secs)?;
        Ok(Self::from_state(ConfigState::Enabled(config)))
    }

    /// Read the default-off process configuration. A recognized enable value
    /// with missing/invalid bounds is retained as `invalid`; every later
    /// reservation then fails closed while read-only diagnostics remain usable.
    pub fn from_env() -> Self {
        let enabled = std::env::var(ENABLE_ENV).ok();
        let max_active = std::env::var(MAX_ACTIVE_ENV).ok();
        let ttl_secs = std::env::var(TTL_SECS_ENV).ok();
        let term_grace_secs = std::env::var(TERM_GRACE_SECS_ENV).ok();
        Self::from_values(
            enabled.as_deref(),
            max_active.as_deref(),
            ttl_secs.as_deref(),
            term_grace_secs.as_deref(),
        )
    }

    fn from_values(
        enabled: Option<&str>,
        max_active: Option<&str>,
        ttl_secs: Option<&str>,
        term_grace_secs: Option<&str>,
    ) -> Self {
        match enabled {
            None | Some("0" | "false" | "no" | "off") => Self::disabled(),
            Some("1" | "true" | "yes" | "on") => {
                let parsed = (|| {
                    let max_active = parse_required::<usize>(MAX_ACTIVE_ENV, max_active)?;
                    let ttl_secs = parse_required::<u64>(TTL_SECS_ENV, ttl_secs)?;
                    let term_grace_secs = match term_grace_secs {
                        Some(value) => parse_value::<u64>(TERM_GRACE_SECS_ENV, value)?,
                        None => DEFAULT_TERM_GRACE_SECS,
                    };
                    validate_enabled_config(max_active, ttl_secs, term_grace_secs)
                })();
                match parsed {
                    Ok(config) => Self::from_state(ConfigState::Enabled(config)),
                    Err(error) => Self::from_state(ConfigState::Invalid(error)),
                }
            }
            Some(_) => Self::from_state(ConfigState::Invalid(format!(
                "{ENABLE_ENV} must be exactly one of 0,false,no,off,1,true,yes,on"
            ))),
        }
    }

    fn from_state(config: ConfigState) -> Self {
        let semaphore = match &config {
            ConfigState::Enabled(config) => Some(Arc::new(Semaphore::new(config.max_active))),
            ConfigState::Disabled | ConfigState::Invalid(_) => None,
        };
        Self {
            inner: Arc::new(GovernorInner {
                config,
                semaphore,
                reserved_slots: AtomicUsize::new(0),
                active_sessions: AtomicUsize::new(0),
                quarantined_slots: AtomicUsize::new(0),
                capacity_rejections_total: AtomicU64::new(0),
                preflight_rejections_total: AtomicU64::new(0),
                activation_rejections_total: AtomicU64::new(0),
                terminal_releases_total: AtomicU64::new(0),
                ttl_expirations_total: AtomicU64::new(0),
                term_requests_total: AtomicU64::new(0),
                kill_requests_total: AtomicU64::new(0),
                monitor_abort_kills_total: AtomicU64::new(0),
                quarantined: Mutex::new(Vec::new()),
            }),
        }
    }

    pub fn snapshot(&self) -> AgentSpawnGovernorSnapshot {
        let (mode, max_active, ttl_secs, term_grace_secs, configuration_error) =
            match &self.inner.config {
                ConfigState::Disabled => ("off", None, None, None, None),
                ConfigState::Invalid(error) => ("invalid", None, None, None, Some(error.clone())),
                ConfigState::Enabled(config) => (
                    "enforce",
                    Some(config.max_active),
                    Some(config.ttl.as_secs()),
                    Some(config.term_grace.as_secs()),
                    None,
                ),
            };
        AgentSpawnGovernorSnapshot {
            schema_version: "ab.agent_spawn_governor.v0",
            mode,
            default_off: true,
            process_scoped: true,
            grants_authority: false,
            local_custody_required: true,
            max_active,
            ttl_secs,
            term_grace_secs,
            reserved_slots: self.inner.reserved_slots.load(Ordering::Acquire),
            active_sessions: self.inner.active_sessions.load(Ordering::Acquire),
            occupied_slots: self.occupied_slots(),
            quarantined_slots: self.inner.quarantined_slots.load(Ordering::Acquire),
            capacity_rejections_total: self.inner.capacity_rejections_total.load(Ordering::Relaxed),
            preflight_rejections_total: self
                .inner
                .preflight_rejections_total
                .load(Ordering::Relaxed),
            activation_rejections_total: self
                .inner
                .activation_rejections_total
                .load(Ordering::Relaxed),
            terminal_releases_total: self.inner.terminal_releases_total.load(Ordering::Relaxed),
            ttl_expirations_total: self.inner.ttl_expirations_total.load(Ordering::Relaxed),
            term_requests_total: self.inner.term_requests_total.load(Ordering::Relaxed),
            kill_requests_total: self.inner.kill_requests_total.load(Ordering::Relaxed),
            monitor_abort_kills_total: self.inner.monitor_abort_kills_total.load(Ordering::Relaxed),
            configuration_error,
            configuration_env: [
                ENABLE_ENV,
                MAX_ACTIVE_ENV,
                TTL_SECS_ENV,
                TERM_GRACE_SECS_ENV,
            ],
        }
    }

    pub fn active_count(&self) -> usize {
        self.inner.active_sessions.load(Ordering::Acquire)
    }

    pub fn occupied_slots(&self) -> usize {
        let ConfigState::Enabled(config) = &self.inner.config else {
            return 0;
        };
        let available = self
            .inner
            .semaphore
            .as_ref()
            .map(|semaphore| semaphore.available_permits())
            .unwrap_or(0);
        config.max_active.saturating_sub(available)
    }

    /// Atomically reserve one slot before a runtime is invoked. A dropped
    /// reservation releases the slot, covering validation errors, failed
    /// spawns, failover exhaustion, and cancellation before activation.
    pub fn reserve(&self) -> Result<AgentSpawnReservation, String> {
        match &self.inner.config {
            ConfigState::Disabled => Ok(AgentSpawnReservation::disabled(self.clone())),
            ConfigState::Invalid(error) => Err(format!(
                "agent_spawn governor configuration invalid: {error}"
            )),
            ConfigState::Enabled(config) => {
                let permit = self
                    .inner
                    .semaphore
                    .as_ref()
                    .expect("enabled governor has semaphore")
                    .clone()
                    .try_acquire_owned()
                    .map_err(|_| {
                        self.inner
                            .capacity_rejections_total
                            .fetch_add(1, Ordering::Relaxed);
                        format!(
                            "agent_spawn governor capacity exhausted: {} active/reserved/quarantined slot(s), max {}",
                            self.occupied_slots(),
                            config.max_active
                        )
                    })?;
                self.inner.reserved_slots.fetch_add(1, Ordering::AcqRel);
                Ok(AgentSpawnReservation {
                    governor: self.clone(),
                    permit: Some(permit),
                    counted_reserved: true,
                    lease_id: uuid::Uuid::new_v4().to_string(),
                    issued_at: Instant::now(),
                    issued_at_unix_secs: unix_now_secs(),
                })
            }
        }
    }

    /// Reject execution shapes for which this process cannot own and revoke
    /// the actual agent workload. The runtime contract is only a pre-spawn
    /// filter; activation still requires the returned custody attestation.
    pub fn preflight_runtime(
        &self,
        runtime_id: &str,
        contract: &WorkspaceRuntimeContract,
        target: AgentSpawnTarget,
    ) -> Result<(), String> {
        match &self.inner.config {
            ConfigState::Disabled => return Ok(()),
            ConfigState::Invalid(error) => {
                return Err(format!(
                    "agent_spawn governor configuration invalid: {error}"
                ));
            }
            ConfigState::Enabled(_) => {}
        }

        let rejection = if target == AgentSpawnTarget::Remote {
            Some("remote target has no local workload custody")
        } else if contract.source_kind != "agent_prompt" {
            Some("runtime source kind is not agent_prompt")
        } else if !matches!(
            contract.locality,
            RuntimeLocality::Local | RuntimeLocality::LocalOrRemote
        ) {
            Some("runtime locality is not a locally-custodied workload")
        } else if contract.cancellable != CapabilitySupport::Supported {
            Some("runtime does not attest cancellable support")
        } else {
            None
        };

        if let Some(reason) = rejection {
            self.inner
                .preflight_rejections_total
                .fetch_add(1, Ordering::Relaxed);
            Err(format!(
                "agent_spawn governor rejected runtime '{runtime_id}': {reason}"
            ))
        } else {
            Ok(())
        }
    }

    /// Prevent an alternate launch surface from bypassing enforcement when it
    /// cannot return the same trusted workload custody as `agent_spawn`.
    /// Existing sessions and stop/read controls remain available.
    pub fn check_unmanaged_launch_surface(&self, surface: &str) -> Result<(), String> {
        match &self.inner.config {
            ConfigState::Disabled => Ok(()),
            ConfigState::Invalid(error) => Err(format!(
                "agent_spawn governor configuration invalid: {error}"
            )),
            ConfigState::Enabled(_) => {
                self.inner
                    .preflight_rejections_total
                    .fetch_add(1, Ordering::Relaxed);
                Err(format!(
                    "agent_spawn governor rejected unmanaged launch surface '{surface}': no trusted local workload custody; use agent_spawn"
                ))
            }
        }
    }

    fn quarantine(&self, permit: OwnedSemaphorePermit, reason: String) {
        self.inner.quarantined_slots.fetch_add(1, Ordering::AcqRel);
        let mut quarantined = self
            .inner
            .quarantined
            .lock()
            .unwrap_or_else(|poisoned| poisoned.into_inner());
        quarantined.push(QuarantinedPermit {
            _permit: permit,
            _reason: reason,
        });
    }
}

/// RAII reservation for one logical spawn/failover request.
#[must_use = "dropping an unactivated reservation releases its concurrency slot"]
pub struct AgentSpawnReservation {
    governor: AgentSpawnGovernor,
    permit: Option<OwnedSemaphorePermit>,
    counted_reserved: bool,
    lease_id: String,
    issued_at: Instant,
    issued_at_unix_secs: u64,
}

impl AgentSpawnReservation {
    fn disabled(governor: AgentSpawnGovernor) -> Self {
        Self {
            governor,
            permit: None,
            counted_reserved: false,
            lease_id: String::new(),
            issued_at: Instant::now(),
            issued_at_unix_secs: unix_now_secs(),
        }
    }

    /// Convert a reserved slot into a session-bound monitor. Failure after a
    /// runtime returned success is treated as a trust-boundary violation: the
    /// runtime is asked to stop and the slot is quarantined for this process.
    pub async fn activate(
        mut self,
        agent: Arc<dyn AgentRuntime>,
        session: &AgentSession,
    ) -> Result<Option<AgentSpawnLeaseMetadata>, String> {
        if matches!(self.governor.inner.config, ConfigState::Disabled) {
            return Ok(None);
        }

        let config = match &self.governor.inner.config {
            ConfigState::Enabled(config) => config.clone(),
            ConfigState::Invalid(error) => {
                return Err(format!(
                    "agent_spawn governor configuration invalid: {error}"
                ));
            }
            ConfigState::Disabled => unreachable!(),
        };
        let permit = self
            .permit
            .take()
            .ok_or_else(|| "agent_spawn governor reservation has no slot".to_string())?;
        self.clear_reserved_count();

        let custody = session.process_custody();
        let rejection = if session.runtime_id != agent.id() {
            Some(format!(
                "runtime identity mismatch: selected '{}', session reported '{}'",
                agent.id(),
                session.runtime_id
            ))
        } else {
            match custody.as_ref() {
                Some(custody) if custody.is_local_workload_root() => None,
                Some(custody) => Some(format!(
                    "session returned non-workload custody scope {:?}",
                    custody.scope()
                )),
                None => Some("session returned no trusted process custody".to_string()),
            }
        };

        if let Some(reason) = rejection {
            self.governor
                .inner
                .activation_rejections_total
                .fetch_add(1, Ordering::Relaxed);
            if let Some(custody) = custody {
                self.governor
                    .inner
                    .kill_requests_total
                    .fetch_add(1, Ordering::Relaxed);
                let _ = custody.request_kill().await;
            }
            let _ = agent.kill(&session.id).await;
            self.governor
                .quarantine(permit, format!("session {}: {reason}", session.id.as_str()));
            return Err(format!(
                "agent_spawn governor rejected spawned session {}: {reason}; slot quarantined",
                session.id
            ));
        }

        let custody = custody.expect("validated local workload custody");
        self.governor
            .inner
            .active_sessions
            .fetch_add(1, Ordering::AcqRel);
        let expires_at = self.issued_at + config.ttl;
        let metadata = AgentSpawnLeaseMetadata {
            schema_version: "ab.agent_spawn_governor_lease.v0",
            mode: "enforce",
            lease_kind: "process_local_capacity",
            grants_authority: false,
            lease_id: self.lease_id.clone(),
            session_id: session.id.as_str().to_string(),
            runtime_id: session.runtime_id.clone(),
            issued_at_unix_secs: self.issued_at_unix_secs,
            expires_at_unix_secs: self
                .issued_at_unix_secs
                .saturating_add(config.ttl.as_secs()),
            ttl_secs: config.ttl.as_secs(),
            term_grace_secs: config.term_grace.as_secs(),
            max_active: config.max_active,
            occupied_slots: self.governor.occupied_slots(),
        };

        let guard = ActiveLeaseGuard {
            governor: self.governor.clone(),
            permit: Some(permit),
            custody: custody.clone(),
            session_id: session.id.as_str().to_string(),
            armed: true,
            counted_active: true,
        };
        let session_id = session.id.clone();
        tokio::spawn(async move {
            monitor_session(
                agent,
                session_id,
                custody,
                expires_at,
                config.term_grace,
                guard,
            )
            .await;
        });
        Ok(Some(metadata))
    }

    fn clear_reserved_count(&mut self) {
        if self.counted_reserved {
            self.governor
                .inner
                .reserved_slots
                .fetch_sub(1, Ordering::AcqRel);
            self.counted_reserved = false;
        }
    }
}

impl Drop for AgentSpawnReservation {
    fn drop(&mut self) {
        self.clear_reserved_count();
    }
}

struct ActiveLeaseGuard {
    governor: AgentSpawnGovernor,
    permit: Option<OwnedSemaphorePermit>,
    custody: SpawnedProcessCustody,
    session_id: String,
    armed: bool,
    counted_active: bool,
}

impl ActiveLeaseGuard {
    fn release_after_terminal(mut self) {
        self.armed = false;
        if self.counted_active {
            self.governor
                .inner
                .active_sessions
                .fetch_sub(1, Ordering::AcqRel);
            self.governor
                .inner
                .terminal_releases_total
                .fetch_add(1, Ordering::Relaxed);
            self.counted_active = false;
        }
        let _ = self.permit.take();
    }
}

impl Drop for ActiveLeaseGuard {
    fn drop(&mut self) {
        if self.counted_active {
            self.governor
                .inner
                .active_sessions
                .fetch_sub(1, Ordering::AcqRel);
            self.counted_active = false;
        }
        if self.armed {
            self.governor
                .inner
                .monitor_abort_kills_total
                .fetch_add(1, Ordering::Relaxed);
            self.governor
                .inner
                .kill_requests_total
                .fetch_add(1, Ordering::Relaxed);
            let _ = self.custody.request_kill_now();
            if let Some(permit) = self.permit.take() {
                self.governor.quarantine(
                    permit,
                    format!("session {}: lifecycle monitor dropped", self.session_id),
                );
            }
        }
    }
}

async fn monitor_session(
    agent: Arc<dyn AgentRuntime>,
    session_id: ab_core::SessionId,
    custody: SpawnedProcessCustody,
    expires_at: Instant,
    term_grace: Duration,
    guard: ActiveLeaseGuard,
) {
    loop {
        if !agent.session_is_active(&session_id) {
            guard.release_after_terminal();
            return;
        }
        let now = Instant::now();
        if now >= expires_at {
            break;
        }
        tokio::time::sleep(TERMINAL_POLL.min(expires_at.saturating_duration_since(now))).await;
    }

    guard
        .governor
        .inner
        .ttl_expirations_total
        .fetch_add(1, Ordering::Relaxed);
    guard
        .governor
        .inner
        .term_requests_total
        .fetch_add(1, Ordering::Relaxed);
    if let Err(error) = custody.request_terminate().await {
        tracing::warn!(
            session_id = %session_id,
            error = %error,
            "agent_spawn governor TERM request failed"
        );
    }

    let grace_deadline = Instant::now() + term_grace;
    while agent.session_is_active(&session_id) && Instant::now() < grace_deadline {
        tokio::time::sleep(
            TERMINAL_POLL.min(grace_deadline.saturating_duration_since(Instant::now())),
        )
        .await;
    }

    if agent.session_is_active(&session_id) {
        guard
            .governor
            .inner
            .kill_requests_total
            .fetch_add(1, Ordering::Relaxed);
        if let Err(error) = custody.request_kill().await {
            tracing::warn!(
                session_id = %session_id,
                error = %error,
                "agent_spawn governor KILL request failed"
            );
        }
    }

    // Do not release capacity on the assumption that a signal succeeded. A
    // wedged runtime holds its slot until it actually reports terminal.
    while agent.session_is_active(&session_id) {
        tokio::time::sleep(TERMINAL_POLL).await;
    }
    guard.release_after_terminal();
}

fn validate_enabled_config(
    max_active: usize,
    ttl_secs: u64,
    term_grace_secs: u64,
) -> Result<EnabledConfig, String> {
    if !(1..=MAX_ACTIVE_LIMIT).contains(&max_active) {
        return Err(format!(
            "{MAX_ACTIVE_ENV} must be in 1..={MAX_ACTIVE_LIMIT}"
        ));
    }
    if !(1..=MAX_TTL_SECS).contains(&ttl_secs) {
        return Err(format!("{TTL_SECS_ENV} must be in 1..={MAX_TTL_SECS}"));
    }
    if term_grace_secs > MAX_TERM_GRACE_SECS {
        return Err(format!(
            "{TERM_GRACE_SECS_ENV} must be in 0..={MAX_TERM_GRACE_SECS}"
        ));
    }
    Ok(EnabledConfig {
        max_active,
        ttl: Duration::from_secs(ttl_secs),
        term_grace: Duration::from_secs(term_grace_secs),
    })
}

fn parse_required<T>(name: &str, value: Option<&str>) -> Result<T, String>
where
    T: std::str::FromStr,
{
    let value = value.ok_or_else(|| format!("{name} is required when {ENABLE_ENV}=true"))?;
    parse_value(name, value)
}

fn parse_value<T>(name: &str, value: &str) -> Result<T, String>
where
    T: std::str::FromStr,
{
    value
        .parse::<T>()
        .map_err(|_| format!("{name} must be an unsigned decimal integer"))
}

fn unix_now_secs() -> u64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap_or_default()
        .as_secs()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn disabled_mode_is_compatible_and_occupies_no_slot() {
        let governor = AgentSpawnGovernor::disabled();
        let reservation = governor.reserve().expect("disabled reservation");
        assert_eq!(governor.snapshot().mode, "off");
        assert_eq!(governor.occupied_slots(), 0);
        drop(reservation);
        assert_eq!(governor.occupied_slots(), 0);
    }

    #[test]
    fn capacity_is_atomic_and_failed_request_raii_releases() {
        let governor = AgentSpawnGovernor::enabled(1, 60, 1).expect("valid governor");
        let reservation = governor.reserve().expect("first slot");
        assert_eq!(governor.occupied_slots(), 1);
        let error = governor.reserve().err().expect("second slot must reject");
        assert!(error.contains("capacity exhausted"), "got: {error}");
        drop(reservation);
        assert_eq!(governor.occupied_slots(), 0);
        assert!(governor.reserve().is_ok());
    }

    #[test]
    fn enabled_configuration_is_fail_closed_when_incomplete_or_malformed() {
        let incomplete = AgentSpawnGovernor::from_values(Some("true"), Some("2"), None, None);
        assert_eq!(incomplete.snapshot().mode, "invalid");
        assert!(incomplete.reserve().is_err());

        let typo = AgentSpawnGovernor::from_values(Some("TRUE"), Some("2"), Some("30"), None);
        assert_eq!(typo.snapshot().mode, "invalid");
        assert!(typo.reserve().is_err());
    }

    #[test]
    fn preflight_allows_only_cancellable_local_workloads() {
        let governor = AgentSpawnGovernor::enabled(2, 60, 1).expect("valid governor");
        let local = WorkspaceRuntimeContract::local_agent(true);
        governor
            .preflight_runtime("local", &local, AgentSpawnTarget::Local)
            .expect("local cancellable runtime");
        assert!(governor
            .preflight_runtime("remote", &local, AgentSpawnTarget::Remote)
            .expect_err("remote must reject")
            .contains("remote target"));

        let cloud = WorkspaceRuntimeContract::cloud_agent();
        assert!(governor
            .preflight_runtime("cloud", &cloud, AgentSpawnTarget::Local)
            .expect_err("cloud must reject")
            .contains("locality"));

        let mut uncancellable = WorkspaceRuntimeContract::local_agent(false);
        uncancellable.cancellable = CapabilitySupport::Unknown;
        assert!(governor
            .preflight_runtime("unknown", &uncancellable, AgentSpawnTarget::Local)
            .expect_err("unknown cancellation must reject")
            .contains("cancellable"));
    }

    #[test]
    fn enforcing_mode_blocks_unmanaged_alternate_launch_surfaces() {
        let disabled = AgentSpawnGovernor::disabled();
        disabled
            .check_unmanaged_launch_surface("agent_steer_launch")
            .expect("legacy mode stays compatible");

        let enforcing = AgentSpawnGovernor::enabled(2, 60, 1).expect("valid governor");
        let error = enforcing
            .check_unmanaged_launch_surface("agent_steer_launch")
            .expect_err("unmanaged launcher must not bypass governor");
        assert!(error.contains("no trusted local workload custody"));
        assert!(error.contains("use agent_spawn"));
        assert_eq!(enforcing.snapshot().preflight_rejections_total, 1);
    }
}
