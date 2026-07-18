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
pub mod sandbox;
pub mod worktree;

pub use acp::AcpRuntime;
pub use auggie::AuggieRuntime;
pub use claude_code::ClaudeCodeRuntime;
pub use codex::CodexRuntime;
pub use gemini::GeminiRuntime;
pub use opencode_family::OpenCodeFamilyRuntime;
pub use oz::OzAgentRuntime;
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
}

#[derive(Debug, Clone, Default, Serialize, Deserialize)]
pub struct AgentCapabilities {
    pub supports_mcp: bool,
    pub supports_teams: bool,
    pub supports_thinking: bool,
}

#[async_trait]
pub trait AgentRuntime: Send + Sync {
    fn id(&self) -> &str;

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
