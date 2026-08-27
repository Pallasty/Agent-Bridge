//! OpenAI Codex CLI agent runtime.
//!
//! One-shot wrapper around `codex exec [OPTIONS] "<prompt>"`. The `exec`
//! subcommand is Codex's non-interactive entry point: it runs the agent to
//! completion, streams progress to stdout, and exits.
//!
//! Two flags get forced for headless safety:
//!
//! - `--skip-git-repo-check`: Codex defaults to refusing to modify directories
//!   that aren't a git repo. The bridge spawns into worktrees / scratch dirs
//!   where this check is wrong context — the human approving the prompt owns
//!   that decision, not the spawn-time check.
//! - The user's `~/.codex/config.toml` already sets
//!   `approval_policy = "never"` and `sandbox_mode = "danger-full-access"`
//!   so we don't override those — match what the user explicitly chose.
//!
//! `SpawnConfig.model` (when set) maps to `-m <model>`. Note that on a
//! ChatGPT subscription only certain models are usable; see the codex docs.
//! Without an explicit model the CLI uses whatever `model = "..."` is set
//! in `~/.codex/config.toml`.
//!
//! Interactive PTY mode (live `send_input`): when spawned with
//! [`SpawnConfig::interactive`], the runtime launches the Codex CLI inside a
//! pseudo-terminal it owns (see [`crate::pty_session`]) and keeps the child
//! alive for successive `send_input` turns — the same close-the-loop contract
//! as the claude-code runtime. The interactive entry point is the bare `codex`
//! TUI (or `codex resume`), NOT `codex exec`, so the launch argv is
//! host-supplied via [`CodexRuntime::with_interactive_args`] (default empty =
//! bare `codex`); the one-shot path keeps forcing `exec --skip-git-repo-check`.
//! Output is captured to the [`StateStore`] on exit; one-shot sessions still
//! reject `send_input`.

use ab_core::{Error, Result, SessionId};
use ab_store::{StateStore, StoredSession};
use async_trait::async_trait;
use dashmap::DashMap;
use std::process::Stdio;
use std::sync::Arc;
use std::time::{Duration, SystemTime, UNIX_EPOCH};
use tokio::process::Command;
use tracing::{info, warn};

use crate::pty_interactive::{self, InteractiveMap};
use crate::{AgentCapabilities, AgentRuntime, AgentSession, SpawnConfig};

#[derive(Clone)]
pub struct CodexRuntime {
    binary: String,
    default_model: Option<String>,
    interactive_args: Vec<String>,
    store: Option<Arc<dyn StateStore>>,
    /// SessionId → PID of the live one-shot child process.
    children: Arc<DashMap<String, u32>>,
    /// SessionId → live interactive PTY session (live `send_input`).
    interactive: InteractiveMap,
}

impl Default for CodexRuntime {
    fn default() -> Self {
        Self::new()
    }
}

impl CodexRuntime {
    pub fn new() -> Self {
        Self {
            binary: std::env::var("AGENT_BRIDGE_CODEX_BIN").unwrap_or_else(|_| "codex".into()),
            default_model: env_nonempty("AGENT_BRIDGE_CODEX_MODEL"),
            interactive_args: Vec::new(),
            store: None,
            children: Arc::new(DashMap::new()),
            interactive: Arc::new(DashMap::new()),
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

    pub fn with_store(mut self, store: Arc<dyn StateStore>) -> Self {
        self.store = Some(store);
        self
    }

    /// Launch flags for the interactive PTY entry point (bare `codex` TUI /
    /// `codex resume`). Host-supplied; default empty = bare `codex`. The
    /// one-shot path is unaffected (it always uses `exec`).
    pub fn with_interactive_args(
        mut self,
        args: impl IntoIterator<Item = impl Into<String>>,
    ) -> Self {
        self.interactive_args = args.into_iter().map(Into::into).collect();
        self
    }

    pub fn live_count(&self) -> usize {
        self.children.len()
    }

    /// Number of live interactive PTY sessions (testing / observability).
    pub fn interactive_count(&self) -> usize {
        self.interactive.len()
    }

    /// Snapshot the merged PTY output of a live interactive session, if one
    /// exists for `session`. Returns `None` once the session has exited (and
    /// been finalised to the [`StateStore`]).
    pub fn read_interactive_output(&self, session: &SessionId) -> Option<String> {
        pty_interactive::interactive_output(&self.interactive, session)
    }

    /// Launch the Codex CLI inside a PTY the daemon owns and keep it alive for
    /// successive [`AgentRuntime::send_input`] turns. Mirrors the one-shot
    /// path's StateStore bookkeeping (start row at spawn, finalise on exit).
    async fn spawn_interactive(&self, cfg: SpawnConfig) -> Result<AgentSession> {
        // Interactive Codex is the bare TUI (no `exec`). The host supplies any
        // launch flags via `with_interactive_args`; tests keep the default
        // empty so `/bin/cat` is a clean PTY stand-in.
        pty_interactive::spawn_interactive(
            self.id(),
            &self.binary,
            &self.interactive_args,
            &self.store,
            &self.interactive,
            cfg,
            pty_interactive::SubmitProfile::KITTY_ENTER
                .with_initial_prompt_delay(Duration::from_secs(3)),
        )
        .await
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
impl AgentRuntime for CodexRuntime {
    fn id(&self) -> &str {
        "codex"
    }

    fn workspace_contract(&self) -> crate::WorkspaceRuntimeContract {
        crate::WorkspaceRuntimeContract::local_agent(true)
    }

    async fn spawn(&self, cfg: SpawnConfig) -> Result<AgentSession> {
        if cfg.interactive {
            return self.spawn_interactive(cfg).await;
        }

        let prompt = cfg.initial_prompt.clone().unwrap_or_default();
        if prompt.is_empty() {
            return Err(Error::InvalidArgument(
                "codex: 'initial_prompt' is required for one-shot spawn".into(),
            ));
        }
        let model = cfg.model.clone().or_else(|| self.default_model.clone());
        let mut launch_args = vec!["exec".to_string(), "--skip-git-repo-check".to_string()];
        if let Some(model) = &model {
            launch_args.push("-m".to_string());
            launch_args.push(model.clone());
        }
        launch_args.push(prompt.clone());
        let launch = crate::sandbox::wrap_local_command(
            self.id(),
            &cfg.cwd,
            &cfg.env,
            &self.binary,
            &launch_args,
        )?;

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
                proc_pid: None,
                proc_pgid: None,
                proc_start_ticks: None,
                owner_pid: None,
                owner_start_ticks: None,
            };
            if let Err(e) = store.save_session(&initial).await {
                warn!(session = %session_id, error = %e, "store: save_session failed");
            }
        }

        let mut cmd = Command::new(&launch.program);
        cmd.args(&launch.args);
        cmd.current_dir(&cwd)
            .stdin(Stdio::null())
            .stdout(Stdio::piped())
            .stderr(Stdio::piped());
        crate::sandbox::configure_command_env(&mut cmd, &cfg.env, launch.sandboxed)?;

        let child = cmd
            .spawn()
            .map_err(|e| Error::Backend(format!("spawn codex: {e}")))?;
        let pid = child.id().unwrap_or(0);
        let process_custody = crate::SpawnedProcessCustody::from_spawn(
            pid,
            None,
            crate::SpawnedProcessScope::LocalWorkloadRoot,
        );
        if pid != 0 {
            self.children.insert(session_id.as_str().to_string(), pid);
        }
        info!(
            session = %session_id,
            pid,
            runtime = "codex",
            model = ?model,
            cwd = %cwd,
            sandboxed = launch.sandboxed,
            "session started"
        );

        let sid_bg = session_id.clone();
        let store_bg = self.store.clone();
        let children_bg = self.children.clone();
        let terminal_custody = process_custody.clone();
        tokio::spawn(async move {
            let out = match terminal_custody.as_ref() {
                Some(custody) => {
                    let custody_on_wait = custody.clone();
                    let children_on_wait = children_bg.clone();
                    let sid_on_wait = sid_bg.clone();
                    crate::terminal_rusage::wait_with_output_notify_reaped(
                        child,
                        custody.initial_wait_observation(),
                        move || {
                            custody_on_wait.seal_terminal_resources();
                            children_on_wait.remove(sid_on_wait.as_str());
                        },
                    )
                    .await
                }
                None => child.wait_with_output().await,
            };
            if let Some(custody) = &terminal_custody {
                custody.seal_terminal_resources();
            }
            children_bg.remove(sid_bg.as_str());
            let ended_at = now_secs();
            match out {
                Ok(o) => {
                    let stdout = String::from_utf8_lossy(&o.stdout).into_owned();
                    let stderr = String::from_utf8_lossy(&o.stderr).into_owned();
                    info!(
                        session = %sid_bg,
                        runtime = "codex",
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
                    warn!(session = %sid_bg, runtime = "codex", error = %e, "wait failed");
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
            sandbox_profile_requested: launch.sandboxed.then(|| "workspace".into()),
            process_custody,
        })
    }

    async fn send_input(&self, session: &SessionId, text: &str) -> Result<()> {
        pty_interactive::send_input(
            self.id(),
            &self.interactive,
            session,
            text,
            pty_interactive::SubmitProfile::KITTY_ENTER,
        )
        .await
    }

    async fn kill(&self, session: &SessionId) -> Result<()> {
        // Interactive PTY session: signal the child via its kill handle. The
        // background reader sees EOF, reaps, and finalises the session row.
        if let Some(result) =
            pty_interactive::kill_interactive(self.id(), &self.interactive, session)
        {
            return result;
        }

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
        info!(session = %session, pid, runtime = "codex", "SIGTERM sent");
        Ok(())
    }

    fn pid_for(&self, session: &SessionId) -> Option<u32> {
        if let Some(pid) = pty_interactive::interactive_pid(&self.interactive, session) {
            return Some(pid);
        }
        self.children.get(session.as_str()).map(|kv| *kv)
    }

    /// Trait-level exposure of the live interactive PTY buffer (Kitty-Enter
    /// TUI) so `agent_session_output` can read a reply through `dyn
    /// AgentRuntime`; mirrors inherent [`CodexRuntime::read_interactive_output`].
    fn read_interactive_output(&self, session: &SessionId) -> Option<String> {
        pty_interactive::interactive_output(&self.interactive, session)
    }

    async fn capabilities(&self) -> AgentCapabilities {
        AgentCapabilities {
            supports_mcp: true,
            supports_teams: false,
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

#[cfg(test)]
mod tests {
    use super::*;
    use std::time::Duration;

    async fn wait_for<F: FnMut() -> bool>(total_ms: u64, step_ms: u64, mut predicate: F) -> bool {
        let mut waited = 0u64;
        while waited <= total_ms {
            if predicate() {
                return true;
            }
            tokio::time::sleep(Duration::from_millis(step_ms)).await;
            waited += step_ms;
        }
        predicate()
    }

    #[tokio::test]
    async fn interactive_session_multi_turn_round_trips() {
        // `/bin/cat` is a deterministic stand-in for the interactive Codex CLI:
        // it stays alive and echoes each submitted line back through the PTY.
        let rt = CodexRuntime::new().with_binary("/bin/cat");
        let sess = rt
            .spawn(SpawnConfig {
                cwd: "/tmp".into(),
                interactive: true,
                ..Default::default()
            })
            .await
            .expect("spawn interactive");
        assert_eq!(rt.interactive_count(), 1);
        assert!(
            rt.pid_for(&sess.id).is_some(),
            "interactive session should expose a pid"
        );

        rt.send_input(&sess.id, "alpha-one").await.expect("turn 1");
        let ok1 = wait_for(2000, 25, || {
            rt.read_interactive_output(&sess.id)
                .map(|o| o.contains("alpha-one"))
                .unwrap_or(false)
        })
        .await;
        assert!(ok1, "turn 1 should echo through the PTY");

        // A second turn proves the session stayed alive (not fire-and-forget).
        rt.send_input(&sess.id, "beta-two").await.expect("turn 2");
        let ok2 = wait_for(2000, 25, || {
            rt.read_interactive_output(&sess.id)
                .map(|o| o.contains("beta-two"))
                .unwrap_or(false)
        })
        .await;
        assert!(ok2, "turn 2 should echo — proves multi-turn interactive");

        rt.kill(&sess.id).await.expect("kill");
    }

    #[tokio::test]
    async fn interactive_initial_prompt_is_submitted_as_first_turn() {
        let rt = CodexRuntime::new().with_binary("/bin/cat");
        let sess = rt
            .spawn(SpawnConfig {
                cwd: "/tmp".into(),
                interactive: true,
                initial_prompt: Some("seed-prompt".into()),
                ..Default::default()
            })
            .await
            .expect("spawn interactive");
        let ok = wait_for(2000, 25, || {
            rt.read_interactive_output(&sess.id)
                .map(|o| o.contains("seed-prompt"))
                .unwrap_or(false)
        })
        .await;
        assert!(
            ok,
            "initial_prompt should be typed + submitted as the first turn"
        );
        rt.kill(&sess.id).await.expect("kill");
    }

    #[cfg(unix)]
    #[tokio::test]
    async fn interactive_initial_prompt_waits_for_tui_boot_settle() {
        let rt = CodexRuntime::new()
            .with_binary("/bin/bash")
            .with_interactive_args([
                "-lc",
                "while IFS= read -r -t 0.2 _line; do :; done; printf 'READY\\n'; exec cat",
            ]);
        let sess = rt
            .spawn(SpawnConfig {
                cwd: "/tmp".into(),
                interactive: true,
                initial_prompt: Some("boot-settle-marker".into()),
                ..Default::default()
            })
            .await
            .expect("spawn delayed-ready stand-in");

        let ready = wait_for(3000, 25, || {
            rt.read_interactive_output(&sess.id)
                .map(|o| o.contains("READY"))
                .unwrap_or(false)
        })
        .await;
        assert!(ready, "stand-in should reach its post-drain READY state");

        let submitted_after_ready = wait_for(5000, 25, || {
            rt.read_interactive_output(&sess.id)
                .map(|o| o.contains("boot-settle-marker"))
                .unwrap_or(false)
        })
        .await;
        assert!(
            submitted_after_ready,
            "initial_prompt should be submitted after the TUI boot settle; \
             an immediate write would be drained before READY and never echoed"
        );
        rt.kill(&sess.id).await.expect("kill");
    }

    #[cfg(unix)]
    #[tokio::test]
    async fn interactive_args_are_passed_to_pty_child() {
        let rt = CodexRuntime::new()
            .with_binary("/bin/sh")
            .with_interactive_args(["-c", "printf 'ARGV:%s\\n' \"$1\"; cat", "sh", "flag-one"]);
        let sess = rt
            .spawn(SpawnConfig {
                cwd: "/tmp".into(),
                interactive: true,
                ..Default::default()
            })
            .await
            .expect("spawn interactive shell");

        let saw_arg = wait_for(2000, 25, || {
            rt.read_interactive_output(&sess.id)
                .map(|o| o.contains("ARGV:flag-one"))
                .unwrap_or(false)
        })
        .await;
        assert!(saw_arg, "interactive args should reach the PTY child");

        rt.send_input(&sess.id, "still-live")
            .await
            .expect("turn after argv print");
        let still_live = wait_for(2000, 25, || {
            rt.read_interactive_output(&sess.id)
                .map(|o| o.contains("still-live"))
                .unwrap_or(false)
        })
        .await;
        assert!(
            still_live,
            "child should remain interactive after startup args"
        );

        rt.kill(&sess.id).await.expect("kill");
    }

    #[tokio::test]
    async fn send_input_rejected_without_interactive_session() {
        // One-shot sessions (and unknown ids) must reject input — only live
        // PTY sessions accept it.
        let rt = CodexRuntime::new().with_binary("/bin/cat");
        let err = rt
            .send_input(&SessionId::new(), "nope")
            .await
            .expect_err("send_input must fail without a live interactive session");
        assert!(matches!(err, Error::InvalidArgument(_)));
    }

    #[tokio::test]
    async fn kill_unknown_session_errors() {
        let rt = CodexRuntime::new().with_binary("/bin/cat");
        let err = rt
            .kill(&SessionId::new())
            .await
            .expect_err("killing an unknown session must error");
        assert!(matches!(err, Error::NotFound(_)));
    }
}
