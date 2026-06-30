//! Google Gemini CLI agent runtime.
//!
//! One-shot wrapper around `gemini -p "<prompt>"`. The Gemini CLI defaults to
//! interactive mode; `-p / --prompt` switches to headless single-shot which
//! prints the model response to stdout and exits.
//!
//! Two flags get forced for a stable headless experience:
//!
//! - `--skip-trust`: workspace-trust prompts otherwise abort headless runs in
//!   any directory the user hasn't manually marked trusted.
//! - `--yolo`: auto-approve tool invocations so the agent can actually
//!   execute when the prompt asks it to (the bridge owns the permission
//!   model — there's no human at the other end of the gemini stdin).
//!
//! `SpawnConfig.model` (when set) maps to `-m <model>`. Auth is whatever the
//! user already configured (`gemini` defaults to OAuth via Google Cloud
//! Code Assist; an API key can be supplied via `GEMINI_API_KEY` in
//! `SpawnConfig.env`).

use ab_core::{Error, Result, SessionId};
use ab_store::{StateStore, StoredSession};
use async_trait::async_trait;
use dashmap::DashMap;
use std::collections::HashMap;
use std::process::Stdio;
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::Arc;
use std::time::{Duration, SystemTime, UNIX_EPOCH};
use tokio::process::Command;
use tracing::{info, warn};

use crate::{AgentCapabilities, AgentRuntime, AgentSession, SpawnConfig};

/// Default watchdog timeout for one-shot Gemini spawns. A successful
/// `gemini -p` round-trip is ~3-8s; quota-exhausted runs retry 3× with
/// exponential backoff and only exit ~30-60s in. 15s catches the latter
/// without false-killing slow-network real successes.
const DEFAULT_GEMINI_TIMEOUT_SECS: u64 = 15;

#[derive(Clone)]
pub struct GeminiRuntime {
    binary: String,
    default_model: Option<String>,
    /// `Some(secs)` = enforce a watchdog SIGTERM at deadline; `None` =
    /// no timeout (matches old behavior). Override via
    /// `AGENT_BRIDGE_GEMINI_TIMEOUT_SECS`; set the env to `0` to disable.
    timeout_secs: Option<u64>,
    store: Option<Arc<dyn StateStore>>,
    children: Arc<DashMap<String, u32>>,
}

impl Default for GeminiRuntime {
    fn default() -> Self {
        Self::new()
    }
}

impl GeminiRuntime {
    pub fn new() -> Self {
        let timeout_secs = match env_nonempty("AGENT_BRIDGE_GEMINI_TIMEOUT_SECS")
            .and_then(|s| s.parse::<u64>().ok())
        {
            Some(0) => None,
            Some(n) => Some(n),
            None => Some(DEFAULT_GEMINI_TIMEOUT_SECS),
        };
        Self {
            binary: std::env::var("AGENT_BRIDGE_GEMINI_BIN").unwrap_or_else(|_| "gemini".into()),
            default_model: env_nonempty("AGENT_BRIDGE_GEMINI_MODEL"),
            timeout_secs,
            store: None,
            children: Arc::new(DashMap::new()),
        }
    }

    pub fn with_binary(mut self, binary: impl Into<String>) -> Self {
        self.binary = binary.into();
        self
    }

    pub fn with_default_model(mut self, model: impl Into<String>) -> Self {
        self.default_model = Some(model.into());
        self
    }

    pub fn with_timeout_secs(mut self, secs: Option<u64>) -> Self {
        self.timeout_secs = secs;
        self
    }

    pub fn with_store(mut self, store: Arc<dyn StateStore>) -> Self {
        self.store = Some(store);
        self
    }

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
impl AgentRuntime for GeminiRuntime {
    fn id(&self) -> &str {
        "gemini"
    }

    async fn spawn(&self, cfg: SpawnConfig) -> Result<AgentSession> {
        cfg.reject_unsupported_interactive(self.id())?;

        let prompt = cfg.initial_prompt.clone().unwrap_or_default();
        if prompt.is_empty() {
            return Err(Error::InvalidArgument(
                "gemini: 'initial_prompt' is required for one-shot spawn".into(),
            ));
        }
        let model = cfg.model.clone().or_else(|| self.default_model.clone());

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
        cmd.arg("--skip-trust").arg("--yolo");
        if let Some(m) = &model {
            cmd.arg("-m").arg(m);
        }
        cmd.arg("-p").arg(&prompt);
        cmd.current_dir(&cwd)
            .stdin(Stdio::null())
            .stdout(Stdio::piped())
            .stderr(Stdio::piped());
        apply_env(&mut cmd, &cfg.env);

        let child = cmd
            .spawn()
            .map_err(|e| Error::Backend(format!("spawn gemini: {e}")))?;
        let pid = child.id().unwrap_or(0);
        if pid != 0 {
            self.children.insert(session_id.as_str().to_string(), pid);
        }
        info!(
            session = %session_id,
            pid,
            runtime = "gemini",
            model = ?model,
            cwd = %cwd,
            "session started"
        );

        let sid_bg = session_id.clone();
        let store_bg = self.store.clone();
        let children_bg = self.children.clone();
        let timeout_secs = self.timeout_secs;
        let timeout_fired = Arc::new(AtomicBool::new(false));
        let watchdog = match (timeout_secs, pid) {
            (Some(t), pid) if pid != 0 => {
                let flag = timeout_fired.clone();
                let sid_for_log = sid_bg.clone();
                Some(tokio::spawn(async move {
                    tokio::time::sleep(Duration::from_secs(t)).await;
                    flag.store(true, Ordering::SeqCst);
                    warn!(
                        session = %sid_for_log,
                        pid,
                        runtime = "gemini",
                        timeout_secs = t,
                        "watchdog firing — sending SIGTERM"
                    );
                    let _ = tokio::process::Command::new("/bin/kill")
                        .arg("-TERM")
                        .arg(pid.to_string())
                        .status()
                        .await;
                }))
            }
            _ => None,
        };
        let timeout_check = timeout_fired.clone();
        tokio::spawn(async move {
            let out = child.wait_with_output().await;
            if let Some(h) = watchdog {
                h.abort();
            }
            children_bg.remove(sid_bg.as_str());
            let ended_at = now_secs();
            let timed_out = timeout_check.load(Ordering::SeqCst);
            match out {
                Ok(o) => {
                    let stdout = String::from_utf8_lossy(&o.stdout).into_owned();
                    let raw_stderr = String::from_utf8_lossy(&o.stderr).into_owned();
                    let stderr = if timed_out {
                        format!(
                            "[agent-bridge] killed after {}s timeout — likely quota \
                             (set GEMINI_API_KEY or wait) or auth. Original stderr:\n{}",
                            timeout_secs.unwrap_or(0),
                            raw_stderr
                        )
                    } else {
                        raw_stderr
                    };
                    info!(
                        session = %sid_bg,
                        runtime = "gemini",
                        exit = ?o.status.code(),
                        timed_out,
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
                    warn!(session = %sid_bg, runtime = "gemini", error = %e, "wait failed");
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
            "gemini: send_input requires interactive mode (not yet supported); \
             use spawn() with initial_prompt for one-shot."
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
        info!(session = %session, pid, runtime = "gemini", "SIGTERM sent");
        Ok(())
    }

    fn pid_for(&self, session: &SessionId) -> Option<u32> {
        self.children.get(session.as_str()).map(|kv| *kv)
    }

    async fn capabilities(&self) -> AgentCapabilities {
        AgentCapabilities {
            supports_mcp: true,
            supports_teams: false,
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

    #[tokio::test]
    async fn spawn_rejects_interactive_mode() {
        let rt = GeminiRuntime::new().with_binary("/no/such/gemini");
        let err = rt
            .spawn(SpawnConfig {
                cwd: "/tmp".into(),
                env: HashMap::new(),
                initial_prompt: Some("hello".into()),
                model: None,
                node: None,
                user: None,
                interactive: true,
            })
            .await
            .expect_err("unsupported interactive mode must fail before spawn");

        assert!(format!("{err}").contains("interactive sessions are not supported"));
    }
}
