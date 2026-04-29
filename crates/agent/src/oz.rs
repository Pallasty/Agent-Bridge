//! Oz cloud-agent runtime.
//!
//! Wraps the [`oz`](https://docs.warp.dev/reference/cli) CLI to spawn
//! Warp Oz cloud agents in the background. Architecturally identical
//! to [`ClaudeCodeRuntime`](crate::claude_code::ClaudeCodeRuntime) —
//! same store-finalise / PID-tracking / SIGTERM model — but the
//! subprocess command line is `oz agent run-cloud …` instead of
//! `claude -p …`.
//!
//! ## What `oz agent run-cloud` does
//!
//! According to Warp's `oz-platform` skill (and `oz help agent
//! run-cloud`), the CLI:
//! - posts to `https://app.warp.dev/api/v1/agent/run` with the prompt
//!   and optional environment id;
//! - prints a one-line status (`Spawned agent with run ID: <uuid>`)
//!   plus any diagnostic output;
//! - exits 0 quickly. The cloud agent itself keeps running on Warp's
//!   infrastructure, queryable via `oz run get <id>`.
//!
//! Hence the local child process is short-lived; we capture its full
//! stdout (which contains the run id) and write it into the bridge's
//! state store via `finalise_session`. Callers can later parse the
//! run id out of `agent_session_get(id).stdout` and follow up with
//! `oz run get <run-id>` themselves, or via a future
//! `oz_run_get` MCP tool.
//!
//! ## Why the CLI rather than HTTP?
//!
//! - **Auth stays in `oz`** — agent-bridge never sees the API key.
//! - **No new dependencies** — reuses the same tokio child-process
//!   plumbing as `ClaudeCodeRuntime`.
//! - **Symmetry** — `claude` and `oz` are both first-party CLIs; we
//!   already require users to install one, the assumption scales.
//!
//! Override the binary path with `AGENT_BRIDGE_OZ_BIN` (default:
//! `oz`). Pass per-spawn environment overrides via `SpawnConfig.env`;
//! `OZ_ENVIRONMENT_ID` (or the `environment_id` field once the
//! upstream `SpawnConfig` is extended) selects the cloud environment.

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

/// Default Oz CLI binary name on `$PATH`.
pub const DEFAULT_OZ_BIN: &str = "oz";

/// Default environment-id env var name read from `SpawnConfig.env`.
///
/// Lets MCP callers pin the cloud environment per-spawn without
/// changing the trait signature. Falls back to
/// `AGENT_BRIDGE_OZ_ENVIRONMENT_ID` from the daemon's process
/// environment if the per-spawn key is missing.
pub const ENV_KEY_ENVIRONMENT_ID: &str = "OZ_ENVIRONMENT_ID";

/// Bridge-wide default for the cloud environment id.
pub const DAEMON_ENV_KEY_ENVIRONMENT_ID: &str = "AGENT_BRIDGE_OZ_ENVIRONMENT_ID";

#[derive(Clone)]
pub struct OzAgentRuntime {
    binary: String,
    store: Option<Arc<dyn StateStore>>,
    /// SessionId → PID of the live `oz` child (short-lived).
    children: Arc<DashMap<String, u32>>,
}

impl Default for OzAgentRuntime {
    fn default() -> Self {
        Self {
            binary: DEFAULT_OZ_BIN.into(),
            store: None,
            children: Arc::new(DashMap::new()),
        }
    }
}

impl OzAgentRuntime {
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

    /// Number of in-flight `oz` child processes (testing / observability).
    pub fn live_count(&self) -> usize {
        self.children.len()
    }

    /// Build the argv slice for `oz agent run-cloud`.
    ///
    /// Pulled out so it can be unit-tested without spawning a process.
    fn build_argv(prompt: &str, environment_id: Option<&str>) -> Vec<String> {
        let mut args = vec![
            "agent".to_string(),
            "run-cloud".to_string(),
            "--prompt".to_string(),
            prompt.to_string(),
            "--output-format".to_string(),
            "json".to_string(),
        ];
        if let Some(env_id) = environment_id {
            if !env_id.is_empty() {
                args.push("--environment".to_string());
                args.push(env_id.to_string());
            }
        }
        args
    }

    /// Resolve the cloud environment id: per-spawn `env[OZ_ENVIRONMENT_ID]`
    /// first, then the daemon-wide `AGENT_BRIDGE_OZ_ENVIRONMENT_ID`,
    /// then `None`.
    fn resolve_environment_id(env: &HashMap<String, String>) -> Option<String> {
        env.get(ENV_KEY_ENVIRONMENT_ID)
            .cloned()
            .or_else(|| std::env::var(DAEMON_ENV_KEY_ENVIRONMENT_ID).ok())
            .filter(|s| !s.is_empty())
    }
}

fn now_secs() -> i64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|d| d.as_secs() as i64)
        .unwrap_or(0)
}

#[async_trait]
impl AgentRuntime for OzAgentRuntime {
    fn id(&self) -> &str {
        "warp-oz"
    }

    async fn spawn(&self, cfg: SpawnConfig) -> Result<AgentSession> {
        let prompt = cfg.initial_prompt.clone().unwrap_or_default();
        if prompt.is_empty() {
            return Err(Error::InvalidArgument(
                "warp-oz: 'initial_prompt' is required for run-cloud spawn".into(),
            ));
        }

        let session_id = SessionId::new();
        let cwd = cfg.cwd.clone();
        let environment_id = Self::resolve_environment_id(&cfg.env);

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

        let argv = Self::build_argv(&prompt, environment_id.as_deref());

        let mut cmd = Command::new(&self.binary);
        cmd.args(&argv)
            .current_dir(&cwd)
            .stdin(Stdio::null())
            .stdout(Stdio::piped())
            .stderr(Stdio::piped());
        // Apply caller-provided env overrides (excluding our internal
        // OZ_ENVIRONMENT_ID sentinel — it's been consumed already and
        // would only confuse the oz CLI).
        for (k, v) in &cfg.env {
            if k == ENV_KEY_ENVIRONMENT_ID {
                continue;
            }
            cmd.env(k, v);
        }

        let child = cmd
            .spawn()
            .map_err(|e| Error::Backend(format!("spawn oz: {e}")))?;
        let pid = child.id().unwrap_or(0);
        if pid != 0 {
            self.children.insert(session_id.as_str().to_string(), pid);
        }
        info!(
            session = %session_id,
            pid,
            cwd = %cwd,
            environment_id = ?environment_id,
            "warp-oz session started"
        );

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
                        "warp-oz session finished"
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
                    warn!(session = %sid_bg, error = %e, "warp-oz wait failed");
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
        // `oz agent run-cloud` is fire-and-forget; the cloud agent
        // doesn't accept follow-up input over stdin. Equivalent of
        // ClaudeCodeRuntime's PTY-required error.
        Err(Error::InvalidArgument(
            "warp-oz: send_input is not supported. \
             Cloud agents are spawned with a single prompt; subsequent \
             interaction must go through Warp's UI or the `oz run` CLI."
                .into(),
        ))
    }

    async fn kill(&self, session: &SessionId) -> Result<()> {
        let pid = match self.children.get(session.as_str()) {
            Some(p) => *p,
            None => {
                return Err(Error::NotFound(format!(
                    "no live child for session {session} (already finished or unknown). \
                     The cloud run itself may still be active — \
                     use `oz run cancel <run-id>` to stop it."
                )));
            }
        };
        // SIGTERM the local `oz` CLI child. This is mostly cosmetic:
        // by the time `kill` is reachable the CLI has usually already
        // POSTed to /agent/run and exited. We still send the signal
        // so the local session row reflects the user's intent
        // (exit_code = -15) rather than 0. To actually cancel the
        // cloud run, callers must run `oz run cancel <run-id>` —
        // which we surface in the NotFound error above.
        let status = tokio::process::Command::new("/bin/kill")
            .arg("-TERM")
            .arg(pid.to_string())
            .status()
            .await
            .map_err(|e| Error::Backend(format!("kill -TERM {pid}: {e}")))?;
        if !status.success() {
            return Err(Error::Backend(format!("/bin/kill exited with {status:?}")));
        }
        info!(session = %session, pid, "SIGTERM sent to local oz CLI child");
        Ok(())
    }

    fn pid_for(&self, session: &SessionId) -> Option<u32> {
        self.children.get(session.as_str()).map(|kv| *kv)
    }

    async fn capabilities(&self) -> AgentCapabilities {
        AgentCapabilities {
            // Cloud agents in Oz environments can use MCP servers
            // configured in the Warp UI.
            supports_mcp: true,
            // Team-scoped runs are an Oz feature.
            supports_teams: true,
            // Cloud Claude/Codex/etc. all support extended thinking
            // when enabled in their respective profiles.
            supports_thinking: true,
        }
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

// ─── tests ───────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn id_is_stable() {
        assert_eq!(OzAgentRuntime::new().id(), "warp-oz");
    }

    #[test]
    fn build_argv_without_environment() {
        let argv = OzAgentRuntime::build_argv("hello world", None);
        assert_eq!(
            argv,
            vec![
                "agent",
                "run-cloud",
                "--prompt",
                "hello world",
                "--output-format",
                "json",
            ]
        );
    }

    #[test]
    fn build_argv_with_environment() {
        let argv = OzAgentRuntime::build_argv("do a thing", Some("UA17BXYZ"));
        assert_eq!(
            argv,
            vec![
                "agent",
                "run-cloud",
                "--prompt",
                "do a thing",
                "--output-format",
                "json",
                "--environment",
                "UA17BXYZ",
            ]
        );
    }

    #[test]
    fn build_argv_treats_empty_env_id_as_none() {
        // Empty string from a misconfigured env var must not produce
        // `--environment ""` (the CLI would error).
        let argv = OzAgentRuntime::build_argv("p", Some(""));
        assert!(!argv.contains(&"--environment".to_string()));
    }

    #[test]
    fn resolve_environment_id_prefers_per_spawn_env() {
        std::env::remove_var(DAEMON_ENV_KEY_ENVIRONMENT_ID);
        let mut env = HashMap::new();
        env.insert(ENV_KEY_ENVIRONMENT_ID.into(), "PER_SPAWN".into());
        assert_eq!(
            OzAgentRuntime::resolve_environment_id(&env),
            Some("PER_SPAWN".into())
        );
    }

    #[test]
    fn resolve_environment_id_falls_back_to_daemon_env() {
        std::env::set_var(DAEMON_ENV_KEY_ENVIRONMENT_ID, "DAEMON_DEFAULT");
        let env = HashMap::new();
        assert_eq!(
            OzAgentRuntime::resolve_environment_id(&env),
            Some("DAEMON_DEFAULT".into())
        );
        std::env::remove_var(DAEMON_ENV_KEY_ENVIRONMENT_ID);
    }

    #[test]
    fn resolve_environment_id_returns_none_when_unset() {
        std::env::remove_var(DAEMON_ENV_KEY_ENVIRONMENT_ID);
        let env = HashMap::new();
        assert!(OzAgentRuntime::resolve_environment_id(&env).is_none());
    }

    #[test]
    fn resolve_environment_id_treats_empty_as_unset() {
        std::env::remove_var(DAEMON_ENV_KEY_ENVIRONMENT_ID);
        let mut env = HashMap::new();
        env.insert(ENV_KEY_ENVIRONMENT_ID.into(), String::new());
        assert!(OzAgentRuntime::resolve_environment_id(&env).is_none());
    }

    #[test]
    fn with_binary_overrides_default() {
        let r = OzAgentRuntime::with_binary("/usr/local/bin/oz");
        assert_eq!(r.binary, "/usr/local/bin/oz");
    }

    #[tokio::test]
    async fn spawn_rejects_empty_prompt() {
        let runtime = OzAgentRuntime::new();
        let cfg = SpawnConfig {
            cwd: "/tmp".into(),
            env: HashMap::new(),
            initial_prompt: None,
        };
        let err = runtime.spawn(cfg).await.expect_err("must reject empty prompt");
        match err {
            Error::InvalidArgument(msg) => {
                assert!(msg.contains("initial_prompt"), "got: {msg}");
            }
            other => panic!("expected InvalidArgument, got {other:?}"),
        }
    }

    #[tokio::test]
    async fn send_input_returns_unsupported_error() {
        let runtime = OzAgentRuntime::new();
        let err = runtime
            .send_input(&SessionId::from_raw("nope"), "hi")
            .await
            .expect_err("send_input should fail");
        match err {
            Error::InvalidArgument(_) => {}
            other => panic!("expected InvalidArgument, got {other:?}"),
        }
    }

    #[tokio::test]
    async fn kill_unknown_session_returns_not_found() {
        let runtime = OzAgentRuntime::new();
        let err = runtime
            .kill(&SessionId::from_raw("never-spawned"))
            .await
            .expect_err("kill on unknown session should fail");
        match err {
            Error::NotFound(msg) => {
                assert!(msg.contains("oz run cancel"), "expected hint, got: {msg}");
            }
            other => panic!("expected NotFound, got {other:?}"),
        }
    }

    #[tokio::test]
    async fn capabilities_advertise_cloud_features() {
        let caps = OzAgentRuntime::new().capabilities().await;
        assert!(caps.supports_mcp);
        assert!(caps.supports_teams);
        assert!(caps.supports_thinking);
    }
}
