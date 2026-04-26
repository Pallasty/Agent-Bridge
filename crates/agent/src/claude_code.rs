//! Claude Code agent runtime.
//!
//! P1 implementation: one-shot `claude -p "<prompt>"` spawned in a working
//! directory. Output is captured and printed to the bridge's logs; the
//! returned [`AgentSession`] tracks the launched session id.
//!
//! Interactive PTY mode (live `send_input`) is P2 — needs `portable-pty`.

use ab_core::{Error, Result, SessionId};
use async_trait::async_trait;
use std::collections::HashMap;
use std::process::Stdio;
use tokio::process::Command;
use tracing::{info, warn};

use crate::{AgentCapabilities, AgentRuntime, AgentSession, SpawnConfig};

#[derive(Clone)]
pub struct ClaudeCodeRuntime {
    binary: String,
}

impl Default for ClaudeCodeRuntime {
    fn default() -> Self { Self { binary: "claude".into() } }
}

impl ClaudeCodeRuntime {
    pub fn new() -> Self { Self::default() }
    pub fn with_binary(binary: impl Into<String>) -> Self { Self { binary: binary.into() } }
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

        // Drain output asynchronously so the child doesn't block on a full pipe;
        // log first 200 chars per stream for diagnostics.
        let sid_log = session_id.clone();
        tokio::spawn(async move {
            let out = child.wait_with_output().await;
            match out {
                Ok(o) => {
                    let stdout = String::from_utf8_lossy(&o.stdout);
                    let stderr = String::from_utf8_lossy(&o.stderr);
                    info!(
                        session = %sid_log,
                        exit = ?o.status.code(),
                        stdout_preview = %truncate(&stdout, 200),
                        stderr_preview = %truncate(&stderr, 200),
                        "claude-code session finished"
                    );
                }
                Err(e) => warn!(session = %sid_log, error = %e, "claude-code wait failed"),
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
