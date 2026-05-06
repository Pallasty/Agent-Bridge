//! `opencode` / `kilo` CLI family runtime.
//!
//! `kilo` is a fork of `opencode`, so the two share an identical
//! non-interactive `run` shape:
//!
//! ```text
//! <bin> run [--model PROVIDER/MODEL] [--dangerously-skip-permissions] "<prompt>"
//! ```
//!
//! We model both as a single struct parameterised by binary + runtime id +
//! optional default model. Two convenience constructors,
//! [`OpenCodeFamilyRuntime::opencode`] and [`OpenCodeFamilyRuntime::kilo`],
//! pick up sensible defaults from env (`AGENT_BRIDGE_OPENCODE_BIN`,
//! `AGENT_BRIDGE_OPENCODE_MODEL`, `AGENT_BRIDGE_KILO_BIN`,
//! `AGENT_BRIDGE_KILO_MODEL`).
//!
//! Per-call model selection comes from [`SpawnConfig::model`]. If neither
//! the call nor the default is set, the binary picks its own default
//! (which today is `anthropic/claude-sonnet` for kilo and a free-tier model
//! for opencode — both fine for smoke testing).
//!
//! Like [`crate::ClaudeCodeRuntime`] this is a one-shot wrapper: spawn,
//! capture stdout+stderr to the store, surface PID for kill.

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

#[derive(Clone)]
pub struct OpenCodeFamilyRuntime {
    binary: String,
    runtime_id: &'static str,
    default_model: Option<String>,
    store: Option<Arc<dyn StateStore>>,
    children: Arc<DashMap<String, u32>>,
}

impl OpenCodeFamilyRuntime {
    /// Build the `opencode` runtime, picking up
    /// `AGENT_BRIDGE_OPENCODE_BIN` / `AGENT_BRIDGE_OPENCODE_MODEL` if set.
    pub fn opencode() -> Self {
        Self {
            binary: std::env::var("AGENT_BRIDGE_OPENCODE_BIN")
                .unwrap_or_else(|_| "opencode".into()),
            runtime_id: "opencode",
            default_model: env_nonempty("AGENT_BRIDGE_OPENCODE_MODEL"),
            store: None,
            children: Arc::new(DashMap::new()),
        }
    }

    /// Build the `kilo` runtime, picking up
    /// `AGENT_BRIDGE_KILO_BIN` / `AGENT_BRIDGE_KILO_MODEL` if set.
    pub fn kilo() -> Self {
        Self {
            binary: std::env::var("AGENT_BRIDGE_KILO_BIN").unwrap_or_else(|_| "kilo".into()),
            runtime_id: "kilo",
            default_model: env_nonempty("AGENT_BRIDGE_KILO_MODEL"),
            store: None,
            children: Arc::new(DashMap::new()),
        }
    }

    pub fn with_store(mut self, store: Arc<dyn StateStore>) -> Self {
        self.store = Some(store);
        self
    }

    pub fn with_binary(mut self, binary: impl Into<String>) -> Self {
        self.binary = binary.into();
        self
    }

    pub fn with_default_model(mut self, model: impl Into<String>) -> Self {
        self.default_model = Some(model.into());
        self
    }

    /// Number of in-flight sessions (testing / observability).
    pub fn live_count(&self) -> usize {
        self.children.len()
    }
}

fn env_nonempty(key: &str) -> Option<String> {
    std::env::var(key)
        .ok()
        .map(|s| s.trim().to_string())
        .filter(|s| !s.is_empty())
}

fn now_secs() -> i64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|d| d.as_secs() as i64)
        .unwrap_or(0)
}

#[async_trait]
impl AgentRuntime for OpenCodeFamilyRuntime {
    fn id(&self) -> &str {
        self.runtime_id
    }

    async fn spawn(&self, cfg: SpawnConfig) -> Result<AgentSession> {
        let prompt = cfg.initial_prompt.clone().unwrap_or_default();
        if prompt.is_empty() {
            return Err(Error::InvalidArgument(format!(
                "{}: 'initial_prompt' is required for one-shot spawn",
                self.runtime_id
            )));
        }
        let model = cfg.model.clone().or_else(|| self.default_model.clone());

        let session_id = SessionId::new();
        let cwd = cfg.cwd.clone();

        if let Some(store) = &self.store {
            let initial = StoredSession {
                id: session_id.clone(),
                runtime_id: self.runtime_id.into(),
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
        cmd.arg("run").arg("--dangerously-skip-permissions");
        if let Some(m) = &model {
            cmd.arg("--model").arg(m);
        }
        // The prompt comes last as a positional argument so any preceding
        // flag values (model strings, etc.) can't shadow it.
        cmd.arg(&prompt);
        cmd.current_dir(&cwd)
            .stdin(Stdio::null())
            .stdout(Stdio::piped())
            .stderr(Stdio::piped());
        apply_env(&mut cmd, &cfg.env);

        let child = cmd
            .spawn()
            .map_err(|e| Error::Backend(format!("spawn {}: {e}", self.runtime_id)))?;
        let pid = child.id().unwrap_or(0);
        if pid != 0 {
            self.children.insert(session_id.as_str().to_string(), pid);
        }
        info!(
            session = %session_id,
            pid,
            runtime = %self.runtime_id,
            model = ?model,
            cwd = %cwd,
            "session started"
        );

        let runtime_id = self.runtime_id;
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
                        runtime = %runtime_id,
                        exit = ?o.status.code(),
                        stdout_preview = %truncate(&stdout, 200),
                        stderr_preview = %truncate(&stderr, 200),
                        "session finished"
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
                    warn!(
                        session = %sid_bg,
                        runtime = %runtime_id,
                        error = %e,
                        "wait failed"
                    );
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
            runtime_id: self.runtime_id.into(),
            cwd,
        })
    }

    async fn send_input(&self, _session: &SessionId, _text: &str) -> Result<()> {
        Err(Error::InvalidArgument(format!(
            "{}: send_input requires interactive (PTY) mode, not yet supported. \
             Use spawn() with initial_prompt for one-shot invocations.",
            self.runtime_id
        )))
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
        info!(
            session = %session,
            pid,
            runtime = %self.runtime_id,
            "SIGTERM sent"
        );
        Ok(())
    }

    fn pid_for(&self, session: &SessionId) -> Option<u32> {
        self.children.get(session.as_str()).map(|kv| *kv)
    }

    async fn capabilities(&self) -> AgentCapabilities {
        AgentCapabilities {
            supports_mcp: true,
            supports_teams: false,
            supports_thinking: false,
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
