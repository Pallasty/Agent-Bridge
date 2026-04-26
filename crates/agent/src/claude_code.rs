//! Claude Code agent runtime.
//!
//! P1 implementation: one-shot `claude -p "<prompt>"` spawned in a working
//! directory. Output is captured and printed to the bridge's logs; the
//! returned [`AgentSession`] tracks the launched session id.
//!
//! v0.2 addition: when constructed `with_store`, the runtime persists every
//! session to [`StateStore`] — start row at spawn, then a final UPDATE with
//! exit code + captured stdout/stderr when the child exits. This closes the
//! `agent_spawn` loop: callers can later query `agent_session_get(id)` to
//! retrieve the actual output.
//!
//! Interactive PTY mode (live `send_input`) is P2 — needs `portable-pty`.

use ab_core::{Error, Result, SessionId};
use ab_store::{StateStore, StoredSession};
use async_trait::async_trait;
use std::collections::HashMap;
use std::process::Stdio;
use std::sync::Arc;
use std::time::{SystemTime, UNIX_EPOCH};
use tokio::process::Command;
use tracing::{info, warn};

use crate::{AgentCapabilities, AgentRuntime, AgentSession, SpawnConfig};

#[derive(Clone)]
pub struct ClaudeCodeRuntime {
    binary: String,
    store: Option<Arc<dyn StateStore>>,
}

impl Default for ClaudeCodeRuntime {
    fn default() -> Self { Self { binary: "claude".into(), store: None } }
}

impl ClaudeCodeRuntime {
    pub fn new() -> Self { Self::default() }
    pub fn with_binary(binary: impl Into<String>) -> Self {
        Self { binary: binary.into(), store: None }
    }
    /// Attach a [`StateStore`] so spawn / finalise rows are persisted.
    pub fn with_store(mut self, store: Arc<dyn StateStore>) -> Self {
        self.store = Some(store);
        self
    }
}

fn now_secs() -> i64 {
    SystemTime::now().duration_since(UNIX_EPOCH).map(|d| d.as_secs() as i64).unwrap_or(0)
}

#[async_trait]
impl AgentRuntime for ClaudeCodeRuntime {
    fn id(&self) -> &str { "claude-code" }

    async fn spawn(&self, cfg: SpawnConfig) -> Result<AgentSession> {
        let prompt = cfg.initial_prompt.clone().unwrap_or_default();
        if prompt.is_empty() {
            return Err(Error::InvalidArgument(
                "claude-code: 'initial_prompt' is required for one-shot spawn".into(),
            ));
        }

        let session_id = SessionId::new();
        let cwd = cfg.cwd.clone();

        // Persist initial row (in-flight) so the session is queryable even
        // before the child exits.
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
            };
            if let Err(e) = store.save_session(&initial).await {
                warn!(session = %session_id, error = %e, "store: save_session failed");
            }
        }

        let mut cmd = Command::new(&self.binary);
        cmd.arg("-p")
            .arg(&prompt)
            .current_dir(&cwd)
            .stdin(Stdio::null())
            .stdout(Stdio::piped())
            .stderr(Stdio::piped());
        apply_env(&mut cmd, &cfg.env);

        let child = cmd
            .spawn()
            .map_err(|e| Error::Backend(format!("spawn claude: {e}")))?;
        info!(session = %session_id, cwd = %cwd, "claude-code session started");

        // Background drain + finalise. Logs a preview either way; persists the
        // full output (clamped) when a store is attached.
        let sid_bg = session_id.clone();
        let store_bg = self.store.clone();
        tokio::spawn(async move {
            let out = child.wait_with_output().await;
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
                        "claude-code session finished"
                    );
                    if let Some(store) = store_bg {
                        let _ = store
                            .finalise_session(
                                &sid_bg,
                                ended_at,
                                o.status.code(),
                                Some(stdout),
                                Some(stderr),
                            )
                            .await;
                    }
                }
                Err(e) => {
                    warn!(session = %sid_bg, error = %e, "claude-code wait failed");
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
            "claude-code: send_input requires PTY mode (P2). \
             Use spawn() with initial_prompt for one-shot invocations."
                .into(),
        ))
    }

    async fn capabilities(&self) -> AgentCapabilities {
        AgentCapabilities {
            supports_mcp: true,
            supports_teams: false, // future
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
    if chars.len() <= max { s.replace('\n', " ⏎ ") } else {
        let head: String = chars.iter().take(max - 1).collect::<String>().replace('\n', " ⏎ ");
        format!("{head}…")
    }
}
