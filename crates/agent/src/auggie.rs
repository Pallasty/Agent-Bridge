//! Auggie agent runtime.
//!
//! Wraps the [`auggie`](https://docs.augmentcode.com/cli) CLI (npm
//! package `@augmentcode/auggie`) to drive Augment Code from
//! agent-bridge. Architecturally identical to
//! [`ClaudeCodeRuntime`](crate::claude_code::ClaudeCodeRuntime) — same
//! store-finalise / PID-tracking / SIGTERM model — but the subprocess
//! command line is `auggie --print --quiet "<prompt>"` instead of
//! `claude -p "<prompt>"`.
//!
//! ## What `auggie --print` does
//!
//! - runs a single non-interactive turn against the user's existing
//!   Auggie session (auth lives in `~/.augment` or the
//!   `AUGMENT_SESSION_AUTH` env var);
//! - streams agent output to stdout; `--quiet` suppresses the
//!   thinking / tool-call chrome so only the final assistant text
//!   reaches us;
//! - exits with the agent's terminal status.
//!
//! Hence the local child is the agent — long-lived for big prompts,
//! short-lived for trivial ones — and we capture stdout/stderr the
//! same way as Claude Code.
//!
//! ## Why the CLI rather than the HTTP API?
//!
//! - **Auth stays in `auggie`** — agent-bridge never sees the
//!   session token.
//! - **No new dependencies** — reuses the same tokio child-process
//!   plumbing as `ClaudeCodeRuntime` and `OzAgentRuntime`.
//! - **Symmetry** — `claude`, `oz`, and `auggie` are all first-party
//!   CLIs; we already require users to install one.
//!
//! Override the binary path with `AGENT_BRIDGE_AUGGIE_BIN` (default:
//! `auggie`). Pass per-spawn environment overrides via
//! `SpawnConfig.env` — notably `AUGMENT_SESSION_AUTH` for
//! headless/CI auth.

use ab_core::{Error, Result, SessionId};
use ab_store::{StateStore, StoredSession};
use async_trait::async_trait;
use dashmap::DashMap;
use std::collections::HashMap;
use std::process::Stdio;
use std::sync::Arc;
use std::time::{SystemTime, UNIX_EPOCH};
use tokio::process::Command;
use tracing::{info, warn};

use crate::{AgentCapabilities, AgentRuntime, AgentSession, SpawnConfig};

/// Default Auggie CLI binary name on `$PATH`.
pub const DEFAULT_AUGGIE_BIN: &str = "auggie";

#[derive(Clone)]
pub struct AuggieRuntime {
    binary: String,
    store: Option<Arc<dyn StateStore>>,
    /// SessionId → PID of the live `auggie` child.
    children: Arc<DashMap<String, u32>>,
}

impl Default for AuggieRuntime {
    fn default() -> Self {
        Self {
            binary: DEFAULT_AUGGIE_BIN.into(),
            store: None,
            children: Arc::new(DashMap::new()),
        }
    }
}

impl AuggieRuntime {
    pub fn new() -> Self {
        Self::default()
    }
    pub fn with_binary(binary: impl Into<String>) -> Self {
        Self {
            binary: binary.into(),
            store: None,
            children: Arc::new(DashMap::new()),
        }
    }
    pub fn with_store(mut self, store: Arc<dyn StateStore>) -> Self {
        self.store = Some(store);
        self
    }

    /// Number of in-flight sessions (testing / observability).
    pub fn live_count(&self) -> usize {
        self.children.len()
    }
}

fn now_secs() -> i64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|d| d.as_secs() as i64)
        .unwrap_or(0)
}

#[async_trait]
impl AgentRuntime for AuggieRuntime {
    fn id(&self) -> &str {
        "auggie"
    }

    async fn spawn(&self, cfg: SpawnConfig) -> Result<AgentSession> {
        let prompt = cfg.initial_prompt.clone().unwrap_or_default();
        if prompt.is_empty() {
            return Err(Error::InvalidArgument(
                "auggie: 'initial_prompt' is required for one-shot spawn".into(),
            ));
        }

        let session_id = SessionId::new();
        let cwd = cfg.cwd.clone();

        if let Some(store) = &self.store {
            let initial = StoredSession {
                id: session_id.clone(),
                runtime_id: self.id().into(),
                cwd: cwd.clone(),
                started_at: now_secs(),
                ended_at: None,
                exit_code: None,
                stdout: None,
                stderr: None,
                cloud_run_id: None,
                cloud_run_state: None,
                cloud_session_link: None,
            };
            if let Err(e) = store.save_session(&initial).await {
                warn!(session = %session_id, error = %e, "store: save_session failed");
            }
        }

        let mut cmd = Command::new(&self.binary);
        cmd.arg("--print")
            .arg("--quiet")
            .arg(&prompt)
            .current_dir(&cwd)
            .stdin(Stdio::null())
            .stdout(Stdio::piped())
            .stderr(Stdio::piped());
        apply_env(&mut cmd, &cfg.env);

        let child = cmd
            .spawn()
            .map_err(|e| Error::Backend(format!("spawn auggie: {e}")))?;
        let pid = child.id().unwrap_or(0);
        if pid != 0 {
            self.children.insert(session_id.as_str().to_string(), pid);
        }
        info!(session = %session_id, pid, cwd = %cwd, "auggie session started");

        let sid_bg = session_id.clone();
        let store_bg = self.store.clone();
        let children_bg = self.children.clone();
        tokio::spawn(async move {
            let out = child.wait_with_output().await;
            children_bg.remove(sid_bg.as_str());
            let ended_at = now_secs();
            match out {
                Ok(o) => {
                    let stdout = String::from_utf8_lossy(&o.stdout).into_owned();
                    let stderr = String::from_utf8_lossy(&o.stderr).into_owned();
                    info!(
                        session = %sid_bg,
                        exit = ?o.status.code(),
                        stdout_preview = %truncate(&stdout, 200),
                        stderr_preview = %truncate(&stderr, 200),
                        "auggie session finished"
                    );
                    let exit_code = o.status.code().or_else(|| {
                        #[cfg(unix)]
                        {
                            use std::os::unix::process::ExitStatusExt;
                            o.status.signal().map(|s| -(s as i32))
                        }
                        #[cfg(not(unix))]
                        {
                            None
                        }
                    });
                    if let Some(store) = store_bg {
                        let _ = store
                            .finalise_session(
                                &sid_bg,
                                ended_at,
                                exit_code,
                                Some(stdout),
                                Some(stderr),
                            )
                            .await;
                    }
                }
                Err(e) => {
                    warn!(session = %sid_bg, error = %e, "auggie wait failed");
                    if let Some(store) = store_bg {
                        let _ = store
                            .finalise_session(
                                &sid_bg,
                                ended_at,
                                None,
                                None,
                                Some(format!("wait failed: {e}")),
                            )
                            .await;
                    }
                }
            }
        });

        Ok(AgentSession {
            id: session_id,
            runtime_id: self.id().into(),
            cwd,
        })
    }

    async fn send_input(&self, _session: &SessionId, _text: &str) -> Result<()> {
        Err(Error::InvalidArgument(
            "auggie: send_input requires PTY mode (P2). \
             Use spawn() with initial_prompt for one-shot invocations."
                .into(),
        ))
    }

    async fn kill(&self, session: &SessionId) -> Result<()> {
        let pid = match self.children.get(session.as_str()) {
            Some(p) => *p,
            None => {
                return Err(Error::NotFound(format!(
                    "no live child for session {session} (already finished or unknown)"
                )));
            }
        };
        let status = tokio::process::Command::new("/bin/kill")
            .arg("-TERM")
            .arg(pid.to_string())
            .status()
            .await
            .map_err(|e| Error::Backend(format!("kill -TERM {pid}: {e}")))?;
        if !status.success() {
            return Err(Error::Backend(format!("/bin/kill exited with {status:?}")));
        }
        info!(session = %session, pid, "SIGTERM sent");
        Ok(())
    }

    fn pid_for(&self, session: &SessionId) -> Option<u32> {
        self.children.get(session.as_str()).map(|kv| *kv)
    }

    async fn capabilities(&self) -> AgentCapabilities {
        AgentCapabilities {
            // Auggie reads MCP servers from ~/.augment/settings.json.
            supports_mcp: true,
            // No multi-tenant/team scoping in the CLI today.
            supports_teams: false,
            // Augment exposes extended thinking via the underlying
            // model; the CLI passes through whatever the account allows.
            supports_thinking: true,
        }
    }
}

fn apply_env(cmd: &mut Command, env: &HashMap<String, String>) {
    for (k, v) in env {
        cmd.env(k, v);
    }
}

fn truncate(s: &str, max: usize) -> String {
    let chars: Vec<char> = s.chars().collect();
    if chars.len() <= max {
        s.replace('\n', " ⏎ ")
    } else {
        let head: String = chars
            .iter()
            .take(max - 1)
            .collect::<String>()
            .replace('\n', " ⏎ ");
        format!("{head}…")
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn id_is_auggie() {
        assert_eq!(AuggieRuntime::new().id(), "auggie");
    }

    #[test]
    fn with_binary_overrides_default() {
        let rt = AuggieRuntime::with_binary("/opt/auggie/bin/auggie");
        assert_eq!(rt.binary, "/opt/auggie/bin/auggie");
        assert_eq!(rt.live_count(), 0);
    }

    #[tokio::test]
    async fn spawn_rejects_empty_prompt() {
        let rt = AuggieRuntime::new();
        let err = rt
            .spawn(SpawnConfig {
                cwd: "/tmp".into(),
                env: HashMap::new(),
                initial_prompt: None,
            })
            .await
            .expect_err("empty prompt must fail");
        assert!(matches!(err, Error::InvalidArgument(_)));
    }

    #[tokio::test]
    async fn send_input_is_rejected() {
        let rt = AuggieRuntime::new();
        let sid = SessionId::new();
        let err = rt
            .send_input(&sid, "hello")
            .await
            .expect_err("send_input must fail in one-shot mode");
        assert!(matches!(err, Error::InvalidArgument(_)));
    }

    #[tokio::test]
    async fn kill_unknown_session_returns_not_found() {
        let rt = AuggieRuntime::new();
        let sid = SessionId::new();
        let err = rt.kill(&sid).await.expect_err("unknown session");
        assert!(matches!(err, Error::NotFound(_)));
    }

    #[tokio::test]
    async fn capabilities_advertise_mcp_and_thinking() {
        let caps = AuggieRuntime::new().capabilities().await;
        assert!(caps.supports_mcp);
        assert!(caps.supports_thinking);
        assert!(!caps.supports_teams);
    }
}
