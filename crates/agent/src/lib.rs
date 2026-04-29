//! AI coding agent runtime abstraction + git worktree manager.
//!
//! - [`AgentRuntime`]: trait wrapping a CLI agent (`claude`, `codex`, `aider`...).
//! - [`ClaudeCodeRuntime`]: spawns Claude Code in a working directory; one-shot
//!   `-p` mode for now (PTY/interactive mode is P2).
//! - [`OzAgentRuntime`]: spawns Warp Oz cloud agents via the `oz` CLI;
//!   the local subprocess is short-lived (it just POSTs to the Warp
//!   API and exits), but the cloud run continues asynchronously.
//! - [`AuggieRuntime`]: spawns Augment Code's `auggie --print` CLI in
//!   a working directory; same one-shot model as `ClaudeCodeRuntime`.
//! - [`GitWorktreeManager`]: thin wrapper around `git worktree {add,list,remove}`.

use ab_core::{Result, SessionId};
use async_trait::async_trait;
use serde::{Deserialize, Serialize};
use std::collections::HashMap;

pub mod auggie;
pub mod claude_code;
pub mod oz;
pub mod worktree;

pub use auggie::AuggieRuntime;
pub use claude_code::ClaudeCodeRuntime;
pub use oz::OzAgentRuntime;
pub use worktree::{GitWorktreeManager, Worktree};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SpawnConfig {
    pub cwd: String,
    #[serde(default)]
    pub env: HashMap<String, String>,
    #[serde(default)]
    pub initial_prompt: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AgentSession {
    pub id: SessionId,
    pub runtime_id: String,
    pub cwd: String,
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

    async fn capabilities(&self) -> AgentCapabilities;
}
