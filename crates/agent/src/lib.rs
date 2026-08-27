//! AI coding agent runtime abstraction + git worktree manager.
//!
//! - [`AgentRuntime`]: trait wrapping a CLI agent (`claude`, `codex`, `aider`...).
//! - [`ClaudeCodeRuntime`]: spawns Claude Code in a working directory. One-shot
//!   `-p` mode by default; set [`SpawnConfig::interactive`] for a live
//!   PTY-backed session that accepts successive turns via
//!   [`AgentRuntime::send_input`] (see [`pty_session`]).
//! - [`OzAgentRuntime`]: spawns Warp Oz cloud agents via the `oz` CLI;
//!   the local subprocess is short-lived (it just POSTs to the Warp
//!   API and exits), but the cloud run continues asynchronously.
//! - [`AuggieRuntime`]: spawns Augment Code's `auggie --print` CLI in
//!   a working directory; same one-shot model as `ClaudeCodeRuntime`.
//! - [`GitWorktreeManager`]: thin wrapper around `git worktree {add,list,remove}`.

use ab_core::{Error, Result, SessionId};
use async_trait::async_trait;
use serde::{Deserialize, Serialize};
use std::collections::HashMap;

pub mod acp;
pub mod auggie;
pub mod claude_code;
pub mod codex;
pub mod gemini;
pub mod opencode_family;
pub mod oz;
pub mod pty_interactive;
pub mod pty_session;
pub mod resident_codex;
pub mod sandbox;
mod terminal_rusage;
pub mod worktree;

pub use acp::AcpRuntime;
pub use auggie::AuggieRuntime;
pub use claude_code::ClaudeCodeRuntime;
pub use codex::CodexRuntime;
pub use gemini::GeminiRuntime;
pub use opencode_family::OpenCodeFamilyRuntime;
pub use oz::OzAgentRuntime;
pub use resident_codex::{
    ResidentCodexBroker, ResidentCodexBrokerConfig, ResidentCodexError,
    ResidentCodexExecutionReceipt, ResidentCodexInvocationContract, ResidentCodexRequest,
    ResidentCodexRun,
};
pub use terminal_rusage::{TerminalResourceSnapshot, TerminalResourceStatus};
pub use worktree::{GitWorktreeManager, Worktree};

#[derive(Debug, Clone, Default, Serialize, Deserialize)]
pub struct SpawnConfig {
    pub cwd: String,
    #[serde(default)]
    pub env: HashMap<String, String>,
    #[serde(default)]
    pub initial_prompt: Option<String>,
    /// Optional model override, in the runtime's expected format
    /// (e.g. `opencode/gpt-5-nano`, `kilo/~anthropic/claude-haiku-latest`).
    /// Honored by [`OpenCodeFamilyRuntime`]; other runtimes ignore it for
    /// now (Claude Code's `-p` mode has no model flag).
    #[serde(default)]
    pub model: Option<String>,
    /// Optional remote node/IP to dispatch the one-shot run to via ssh. When
    /// set (and not `local`/`localhost`/this host), [`OpenCodeFamilyRuntime`]
    /// wraps the run in `ssh <user@node> <remote-cmd>` so the executor (e.g. a
    /// free remote `kilo`) runs remotely while lifecycle (start/finish/exit) is
    /// still recorded in `agent_sessions`. Other runtimes ignore it.
    #[serde(default)]
    pub node: Option<String>,
    /// ssh user for remote dispatch (paired with `node`). Ignored when `node`
    /// is unset/local.
    #[serde(default)]
    pub user: Option<String>,
    /// Open a live, PTY-backed interactive session instead of a one-shot run.
    /// When `true`, [`ClaudeCodeRuntime`] launches the agent CLI inside a
    /// pseudo-terminal it owns and keeps it alive so callers can drive
    /// successive turns via [`AgentRuntime::send_input`]; `initial_prompt`, if
    /// present, is typed and submitted as the first turn. Runtimes that have
    /// not implemented interactive mode must reject this flag before spawning.
    #[serde(default)]
    pub interactive: bool,
}

impl SpawnConfig {
    /// Fail closed when a runtime has not implemented live interactive mode.
    pub fn reject_unsupported_interactive(&self, runtime_id: &str) -> Result<()> {
        if self.interactive {
            Err(Error::InvalidArgument(format!(
                "{runtime_id}: interactive sessions are not supported by this runtime yet; \
                 use backend 'claude-code' for live PTY sessions or omit interactive for one-shot."
            )))
        } else {
            Ok(())
        }
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AgentSession {
    pub id: SessionId,
    pub runtime_id: String,
    pub cwd: String,
    /// Requested child sandbox profile. This is launch intent rather than a
    /// synchronous enforcement attestation; a fail-closed launcher can still
    /// exit before the underlying executor starts.
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub sandbox_profile_requested: Option<String>,
    /// Runtime-internal identity captured at the actual spawn point. It is
    /// deliberately omitted from public session serialization; bridge layers
    /// may use it to bind read-only process accounting without guessing a PID.
    #[serde(skip)]
    process_custody: Option<SpawnedProcessCustody>,
}

impl AgentSession {
    /// Construct a session descriptor without process custody.
    ///
    /// Runtime implementations outside this crate can implement
    /// [`AgentRuntime`] without gaining a way to mint a trusted local-process
    /// identity. Built-in runtimes attach custody only at their actual spawn
    /// point.
    pub fn new(
        id: SessionId,
        runtime_id: impl Into<String>,
        cwd: impl Into<String>,
        sandbox_profile_requested: Option<String>,
    ) -> Self {
        Self {
            id,
            runtime_id: runtime_id.into(),
            cwd: cwd.into(),
            sandbox_profile_requested,
            process_custody: None,
        }
    }

    /// Return the non-serializable process identity captured by a built-in
    /// runtime at the successful spawn point, when one exists.
    pub fn process_custody(&self) -> Option<SpawnedProcessCustody> {
        self.process_custody.clone()
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum SpawnedProcessScope {
    /// The local child (possibly a sandbox launcher) is the root of the agent
    /// workload whose descendants belong to this node's task body.
    LocalWorkloadRoot,
    /// The child is only a local transport for work executing on another node.
    LocalTransport,
    /// The child only submits or observes a cloud run.
    CloudLauncher,
}

#[derive(Clone)]
pub struct SpawnedProcessCustody {
    pid: u32,
    pgid: Option<u32>,
    start_ticks: Option<u64>,
    scope: SpawnedProcessScope,
    terminal_resources: std::sync::Arc<terminal_rusage::TerminalResourceAccumulator>,
    initial_wait_observation: terminal_rusage::TerminalWaitObservation,
}

impl SpawnedProcessCustody {
    /// Construct from the PID returned by the successful spawn itself. On
    /// Linux, absence of a start token remains explicit and later binding must
    /// fail closed rather than trusting PID alone.
    pub(crate) fn from_spawn(
        pid: u32,
        pgid: Option<u32>,
        scope: SpawnedProcessScope,
    ) -> Option<Self> {
        if pid == 0 {
            return None;
        }
        let terminal_resources = terminal_rusage::TerminalResourceAccumulator::new();
        let initial_wait_observation = terminal_resources.begin_generation(pid)?;
        Some(Self {
            pid,
            pgid,
            start_ticks: crate::pty_session::proc_start_ticks(pid)
                .and_then(|ticks| u64::try_from(ticks).ok()),
            scope,
            terminal_resources,
            initial_wait_observation,
        })
    }

    pub fn pid(&self) -> u32 {
        self.pid
    }

    pub fn pgid(&self) -> Option<u32> {
        self.pgid
    }

    pub fn start_ticks(&self) -> Option<u64> {
        self.start_ticks
    }

    pub fn scope(&self) -> SpawnedProcessScope {
        self.scope
    }

    pub fn is_local_workload_root(&self) -> bool {
        self.scope == SpawnedProcessScope::LocalWorkloadRoot
    }

    /// Snapshot terminal resources known for all child generations spawned by
    /// this runtime session.  The snapshot never contains process identity.
    pub fn terminal_resources(&self) -> TerminalResourceSnapshot {
        self.terminal_resources.snapshot()
    }

    pub(crate) fn initial_wait_observation(&self) -> terminal_rusage::TerminalWaitObservation {
        self.initial_wait_observation.clone()
    }

    pub(crate) fn begin_process_generation(
        &self,
        pid: u32,
    ) -> Option<terminal_rusage::TerminalWaitObservation> {
        self.terminal_resources.begin_generation(pid)
    }

    pub(crate) fn seal_terminal_resources(&self) {
        self.terminal_resources.seal();
    }
}

impl std::fmt::Debug for SpawnedProcessCustody {
    fn fmt(&self, formatter: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        formatter
            .debug_struct("SpawnedProcessCustody")
            .field("scope", &self.scope)
            .field("terminal_resources", &self.terminal_resources())
            .finish_non_exhaustive()
    }
}

#[derive(Debug, Clone, Default, Serialize, Deserialize)]
pub struct AgentCapabilities {
    pub supports_mcp: bool,
    pub supports_teams: bool,
    pub supports_thinking: bool,
}

/// Conservative capability state used by routing decisions. `Unknown` is
/// deliberately distinct from `Supported`: callers must not infer authority
/// from a runtime failing to describe itself.
#[derive(Debug, Clone, Copy, Default, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum CapabilitySupport {
    Supported,
    Unsupported,
    #[default]
    Unknown,
}

#[derive(Debug, Clone, Copy, Default, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum RuntimeLocality {
    Local,
    LocalOrRemote,
    Cloud,
    #[default]
    Unknown,
}

/// Read-only construction-time description of an agent runtime's execution
/// shape. This is routing metadata, not a runtime enforcement attestation.
#[derive(Debug, Clone, PartialEq, Eq, Serialize)]
pub struct WorkspaceRuntimeContract {
    pub schema_version: &'static str,
    pub source_kind: &'static str,
    pub locality: RuntimeLocality,
    pub one_shot: CapabilitySupport,
    pub interactive: CapabilitySupport,
    pub cancellable: CapabilitySupport,
    pub live_output: CapabilitySupport,
    pub workspace_sandbox: CapabilitySupport,
    pub remote_sandbox: CapabilitySupport,
    pub network_isolation: CapabilitySupport,
}

impl Default for WorkspaceRuntimeContract {
    fn default() -> Self {
        Self {
            schema_version: "ab.workspace_runtime.v0",
            source_kind: "agent_prompt",
            locality: RuntimeLocality::Unknown,
            one_shot: CapabilitySupport::Unknown,
            interactive: CapabilitySupport::Unknown,
            cancellable: CapabilitySupport::Unknown,
            live_output: CapabilitySupport::Unknown,
            workspace_sandbox: CapabilitySupport::Unknown,
            remote_sandbox: CapabilitySupport::Unknown,
            network_isolation: CapabilitySupport::Unknown,
        }
    }
}

impl WorkspaceRuntimeContract {
    pub fn agent_prompt(locality: RuntimeLocality) -> Self {
        Self {
            locality,
            ..Self::default()
        }
    }

    pub fn local_agent(interactive: bool) -> Self {
        Self {
            one_shot: CapabilitySupport::Supported,
            interactive: if interactive {
                CapabilitySupport::Supported
            } else {
                CapabilitySupport::Unsupported
            },
            cancellable: CapabilitySupport::Supported,
            live_output: if interactive {
                CapabilitySupport::Supported
            } else {
                CapabilitySupport::Unsupported
            },
            workspace_sandbox: CapabilitySupport::Supported,
            remote_sandbox: CapabilitySupport::Unsupported,
            ..Self::agent_prompt(RuntimeLocality::Local)
        }
    }

    pub fn local_or_remote_agent(interactive: bool) -> Self {
        Self {
            locality: RuntimeLocality::LocalOrRemote,
            ..Self::local_agent(interactive)
        }
    }

    pub fn cloud_agent() -> Self {
        Self {
            one_shot: CapabilitySupport::Supported,
            interactive: CapabilitySupport::Unsupported,
            cancellable: CapabilitySupport::Unsupported,
            live_output: CapabilitySupport::Unsupported,
            workspace_sandbox: CapabilitySupport::Unsupported,
            remote_sandbox: CapabilitySupport::Unsupported,
            ..Self::agent_prompt(RuntimeLocality::Cloud)
        }
    }
}

#[async_trait]
pub trait AgentRuntime: Send + Sync {
    fn id(&self) -> &str;

    /// Construction-time execution descriptor. The default is intentionally
    /// unknown so newly added runtimes cannot silently gain routing authority.
    fn workspace_contract(&self) -> WorkspaceRuntimeContract {
        WorkspaceRuntimeContract::default()
    }

    async fn spawn(&self, cfg: SpawnConfig) -> Result<AgentSession>;

    /// Type one turn of input into a live session and submit it.
    ///
    /// Only meaningful for sessions opened with [`SpawnConfig::interactive`].
    /// One-shot (`-p`) sessions cannot accept input, so runtimes reject the
    /// call with `InvalidArgument`; runtimes without interactive support reject
    /// it unconditionally.
    async fn send_input(&self, session: &SessionId, text: &str) -> Result<()>;

    /// Send SIGTERM to the underlying process. Idempotent — calling on an
    /// already-finished session is a no-op (NotFound error). Default impl
    /// rejects; runtimes that track child PIDs override.
    async fn kill(&self, session: &SessionId) -> Result<()> {
        Err(ab_core::Error::InvalidArgument(format!(
            "kill not supported by this runtime (session {session})"
        )))
    }

    /// Return the OS PID of the live child for `session`, if this runtime is
    /// still tracking it. Used by `agent_session_list` to surface a
    /// process-liveness probe (v0.8). Default impl returns `None` so runtimes
    /// without process tracking are still trait-compatible.
    fn pid_for(&self, _session: &SessionId) -> Option<u32> {
        None
    }

    /// Whether this runtime still owns an active lifecycle for `session`.
    /// Unlike [`Self::pid_for`], this remains true during a retry backoff where
    /// the prior child has been reaped and no new PID is safely addressable.
    fn session_is_active(&self, session: &SessionId) -> bool {
        self.pid_for(session).is_some()
    }

    /// Snapshot the merged live PTY output of an interactive `session`, if this
    /// runtime is tracking one. Returns `None` for non-interactive runtimes,
    /// unknown sessions, or sessions that have already exited and been finalised
    /// to the [`StateStore`] (read the persisted `stdout` for those). Surfaced
    /// via `agent_session_output` so programmatic multi-turn callers can read a
    /// reply before the next [`AgentRuntime::send_input`]. Default impl returns
    /// `None` so runtimes without interactive support stay trait-compatible.
    fn read_interactive_output(&self, _session: &SessionId) -> Option<String> {
        None
    }

    async fn capabilities(&self) -> AgentCapabilities;
}

#[cfg(test)]
mod workspace_contract_tests {
    use super::*;

    #[test]
    fn default_contract_grants_no_execution_authority() {
        let contract = WorkspaceRuntimeContract::default();
        assert_eq!(contract.locality, RuntimeLocality::Unknown);
        assert_eq!(contract.interactive, CapabilitySupport::Unknown);
        assert_eq!(contract.workspace_sandbox, CapabilitySupport::Unknown);
        assert_eq!(contract.network_isolation, CapabilitySupport::Unknown);
    }

    #[test]
    fn local_interactive_contract_is_explicit_about_non_claims() {
        let contract = WorkspaceRuntimeContract::local_agent(true);
        assert_eq!(contract.locality, RuntimeLocality::Local);
        assert_eq!(contract.interactive, CapabilitySupport::Supported);
        assert_eq!(contract.workspace_sandbox, CapabilitySupport::Supported);
        assert_eq!(contract.remote_sandbox, CapabilitySupport::Unsupported);
        assert_eq!(contract.network_isolation, CapabilitySupport::Unknown);
    }
}

#[cfg(test)]
mod process_custody_tests {
    use super::*;
    use serde_json::json;

    fn session_with_custody() -> AgentSession {
        let mut session = AgentSession::new(
            SessionId::from_raw("ses-custody-test"),
            "test-runtime",
            "/tmp",
            None,
        );
        session.process_custody = SpawnedProcessCustody::from_spawn(
            std::process::id(),
            Some(std::process::id()),
            SpawnedProcessScope::LocalWorkloadRoot,
        );
        session
    }

    #[test]
    fn custody_is_not_serialized_or_deserializable() {
        let session = session_with_custody();
        let debug = format!("{session:?}");
        assert!(!debug.contains("pid:"));
        assert!(!debug.contains("pgid:"));
        assert!(!debug.contains("start_ticks:"));

        let serialized = serde_json::to_value(session).expect("serialize session");
        assert!(serialized.get("process_custody").is_none());

        let mut forged = serialized;
        forged.as_object_mut().expect("session object").insert(
            "process_custody".into(),
            json!({
                "pid": std::process::id(),
                "pgid": std::process::id(),
                "start_ticks": 1,
                "scope": "LocalWorkloadRoot"
            }),
        );
        let decoded: AgentSession = serde_json::from_value(forged).expect("deserialize session");
        assert!(decoded.process_custody().is_none());
    }

    #[test]
    fn public_constructor_cannot_claim_process_custody() {
        let session = AgentSession::new(
            SessionId::from_raw("ses-no-custody"),
            "external-runtime",
            "/tmp",
            Some("workspace".into()),
        );
        assert!(session.process_custody().is_none());
    }

    #[test]
    fn zero_pid_never_produces_custody() {
        assert!(
            SpawnedProcessCustody::from_spawn(0, None, SpawnedProcessScope::LocalWorkloadRoot)
                .is_none()
        );
    }

    #[cfg(unix)]
    #[test]
    fn spawned_child_custody_captures_pid_and_birth_token() {
        let mut child = std::process::Command::new("/bin/sh")
            .args(["-c", "sleep 5"])
            .spawn()
            .expect("spawn child");
        let pid = child.id();
        let custody = SpawnedProcessCustody::from_spawn(
            pid,
            Some(pid),
            SpawnedProcessScope::LocalWorkloadRoot,
        )
        .expect("non-zero child pid");

        assert_eq!(custody.pid(), pid);
        assert_eq!(custody.pgid(), Some(pid));
        assert_eq!(custody.scope(), SpawnedProcessScope::LocalWorkloadRoot);
        assert!(custody.is_local_workload_root());
        #[cfg(target_os = "linux")]
        assert_eq!(
            custody.start_ticks(),
            crate::pty_session::proc_start_ticks(pid).map(|ticks| ticks as u64)
        );

        let _ = child.kill();
        let _ = child.wait();
    }
}
