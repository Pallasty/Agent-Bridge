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
//! v0.3 addition: a per-runtime live-child registry lets [`Self::kill`] send a
//! graceful stop to in-flight sessions. The registry now retains private
//! process custody rather than a reusable numeric PID.
//!
//! Interactive PTY mode (live `send_input`): when spawned with
//! [`SpawnConfig::interactive`], the runtime launches the agent CLI inside a
//! pseudo-terminal it owns (see [`crate::pty_session`]), keeps the child alive,
//! and lets callers drive successive turns via [`Self::send_input`]. Output is
//! captured to the [`StateStore`] on exit, the same close-the-loop contract as
//! the one-shot path. One-shot sessions still reject `send_input`.

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
pub struct ClaudeCodeRuntime {
    binary: String,
    interactive_args: Vec<String>,
    store: Option<Arc<dyn StateStore>>,
    /// SessionId → private custody for the live one-shot child process.
    children: Arc<DashMap<String, crate::SpawnedProcessCustody>>,
    /// SessionId → live interactive PTY session (live `send_input`).
    interactive: InteractiveMap,
}

impl Default for ClaudeCodeRuntime {
    fn default() -> Self {
        Self {
            binary: "claude".into(),
            interactive_args: Vec::new(),
            store: None,
            children: Arc::new(DashMap::new()),
            interactive: Arc::new(DashMap::new()),
        }
    }
}

impl ClaudeCodeRuntime {
    pub fn new() -> Self {
        Self::default()
    }
    pub fn with_binary(binary: impl Into<String>) -> Self {
        Self {
            binary: binary.into(),
            interactive_args: Vec::new(),
            store: None,
            children: Arc::new(DashMap::new()),
            interactive: Arc::new(DashMap::new()),
        }
    }
    pub fn with_interactive_args(
        mut self,
        args: impl IntoIterator<Item = impl Into<String>>,
    ) -> Self {
        self.interactive_args = args.into_iter().map(Into::into).collect();
        self
    }
    pub fn with_store(mut self, store: Arc<dyn StateStore>) -> Self {
        self.store = Some(store);
        self
    }

    /// Number of in-flight one-shot sessions (testing / observability).
    pub fn live_count(&self) -> usize {
        self.children.len()
    }

    /// Number of live interactive PTY sessions (testing / observability).
    pub fn interactive_count(&self) -> usize {
        self.interactive.len()
    }

    /// Snapshot the merged PTY output of a live interactive session, if one
    /// exists for `session`. Returns `None` once the session has exited (and
    /// been finalised to the [`StateStore`]). Used for observability and tests
    /// — the trait has no streaming-read method yet.
    pub fn read_interactive_output(&self, session: &SessionId) -> Option<String> {
        pty_interactive::interactive_output(&self.interactive, session)
    }

    /// Launch the agent CLI inside a PTY the daemon owns and keep it alive for
    /// successive [`Self::send_input`] turns. Mirrors the one-shot path's
    /// StateStore bookkeeping (start row at spawn, finalise on exit).
    async fn spawn_interactive(&self, cfg: SpawnConfig) -> Result<AgentSession> {
        // Interactive Claude Code is the TUI (no `-p`). The host can provide
        // launch flags such as `--no-chrome` to avoid first-run prompts; tests
        // keep the default empty so `/bin/cat` remains a clean PTY stand-in.
        pty_interactive::spawn_interactive(
            self.id(),
            &self.binary,
            &self.interactive_args,
            &self.store,
            &self.interactive,
            cfg,
            pty_interactive::SubmitProfile::ENTER.with_initial_prompt_delay(Duration::from_secs(3)),
        )
        .await
    }
}

fn now_secs() -> i64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|d| d.as_secs() as i64)
        .unwrap_or(0)
}

#[async_trait]
impl AgentRuntime for ClaudeCodeRuntime {
    fn id(&self) -> &str {
        "claude-code"
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
                "claude-code: 'initial_prompt' is required for one-shot spawn".into(),
            ));
        }

        let launch_args = vec!["-p".to_string(), prompt.clone()];
        let launch = crate::sandbox::wrap_local_command(
            self.id(),
            &cfg.cwd,
            &cfg.env,
            &self.binary,
            &launch_args,
        )?;

        let session_id = SessionId::new();
        let cwd = cfg.cwd.clone();

        let mut cmd = Command::new(&launch.program);
        cmd.args(&launch.args)
            .current_dir(&cwd)
            .stdin(Stdio::null())
            .stdout(Stdio::piped())
            .stderr(Stdio::piped());
        crate::sandbox::configure_command_env(&mut cmd, &cfg.env, launch.sandboxed)?;

        let child = cmd
            .spawn()
            .map_err(|e| Error::Backend(format!("spawn claude: {e}")))?;
        let pid = child.id().unwrap_or(0);
        let mut activation_guard = crate::SpawnActivationGuard::capture(
            pid,
            None,
            crate::SpawnedProcessScope::LocalWorkloadRoot,
            launch.workload.is_some(),
        );
        let workload_generation = launch.activate_workload_cgroup(pid).await?;
        activation_guard.disarm();
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
        let process_custody = crate::SpawnedProcessCustody::from_spawn_with_workload(
            pid,
            None,
            crate::SpawnedProcessScope::LocalWorkloadRoot,
            workload_generation,
        );
        if let Some(custody) = process_custody.clone() {
            self.children
                .insert(session_id.as_str().to_string(), custody);
        }
        info!(session = %session_id, pid, cwd = %cwd, sandboxed = launch.sandboxed, "claude-code session started");

        let sid_bg = session_id.clone();
        let store_bg = self.store.clone();
        let children_bg = self.children.clone();
        let terminal_custody = process_custody.clone();
        let mut return_guard = crate::SpawnReturnGuard::new(process_custody.clone());
        let (initial_saved, initial_save_task) =
            crate::spawn_initial_session_save(store_bg.clone(), initial);
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
            let _ = initial_save_task.await;
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
                    // On Unix, status.code() is None when the child was killed
                    // by a signal. Encode signals as negative exit codes
                    // (e.g. SIGTERM = 15 → -15) so callers can distinguish
                    // "exited normally with 0" from "killed by SIGTERM".
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

        let _ = initial_saved.await;

        let session = AgentSession {
            id: session_id,
            runtime_id: self.id().into(),
            cwd,
            sandbox_profile_requested: launch.sandboxed.then(|| "workspace".into()),
            process_custody,
        };
        return_guard.disarm();
        Ok(session)
    }

    async fn send_input(&self, session: &SessionId, text: &str) -> Result<()> {
        pty_interactive::send_input(
            self.id(),
            &self.interactive,
            session,
            text,
            pty_interactive::SubmitProfile::ENTER,
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

        let custody = match self.children.get(session.as_str()) {
            Some(custody) => custody.clone(),
            None => {
                return Err(Error::NotFound(format!(
                    "no live child for session {session} (already finished or unknown)"
                )));
            }
        };
        let pid = custody.pid();
        custody.request_terminate().await?;
        // Background wait task will see the child die, clean up `children` map,
        // and finalise the session row with the SIGTERM exit code.
        info!(session = %session, pid, "SIGTERM sent");
        Ok(())
    }

    fn pid_for(&self, session: &SessionId) -> Option<u32> {
        if let Some(pid) = pty_interactive::interactive_pid(&self.interactive, session) {
            return Some(pid);
        }
        self.children
            .get(session.as_str())
            .map(|custody| custody.pid())
    }

    /// Trait-level exposure of the live interactive PTY buffer so
    /// `agent_session_output` can read a reply through `dyn AgentRuntime`;
    /// mirrors inherent [`ClaudeCodeRuntime::read_interactive_output`].
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
        // `/bin/cat` is a deterministic stand-in for the interactive agent CLI:
        // it stays alive and echoes each submitted line back through the PTY.
        let rt = ClaudeCodeRuntime::with_binary("/bin/cat");
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
        let rt = ClaudeCodeRuntime::with_binary("/bin/cat");
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
        let rt = ClaudeCodeRuntime::with_binary("/bin/bash").with_interactive_args([
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
        let rt = ClaudeCodeRuntime::with_binary("/bin/sh").with_interactive_args([
            "-c",
            "printf 'ARGV:%s\\n' \"$1\"; cat",
            "sh",
            "flag-one",
        ]);
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

    #[cfg(target_os = "linux")]
    #[tokio::test]
    async fn one_shot_reap_clears_pid_before_inherited_pipe_eof() {
        use ab_store::{SessionFilter, SqliteStore, StateStore as _};
        use std::os::unix::fs::PermissionsExt;

        let root = tempfile::tempdir().expect("tempdir");
        let binary = root.path().join("fake-claude");
        std::fs::write(
            &binary,
            "#!/bin/sh\nsleep 3 &\nprintf '%s\\n' 'leader-finished'\n",
        )
        .expect("write fake claude");
        let mut permissions = std::fs::metadata(&binary).expect("metadata").permissions();
        permissions.set_mode(0o755);
        std::fs::set_permissions(&binary, permissions).expect("chmod");
        let store = Arc::new(
            SqliteStore::open(&root.path().join("state.db"))
                .await
                .expect("open store"),
        );
        let runtime =
            ClaudeCodeRuntime::with_binary(binary.display().to_string()).with_store(store.clone());
        let session = runtime
            .spawn(SpawnConfig {
                cwd: root.path().display().to_string(),
                initial_prompt: Some("pipe inheritance probe".into()),
                ..Default::default()
            })
            .await
            .expect("spawn fake claude");
        let custody = session.process_custody().expect("custody");

        // The deliberately fast leader may already have been reaped before
        // `spawn` returns from its initial Store acknowledgement. Either
        // ordering is valid; the invariant is that its live PID clears while
        // the inherited descendant pipe still keeps finalisation open.
        let pid_cleared = wait_for(2_000, 10, || runtime.live_count() == 0).await;
        assert!(
            pid_cleared,
            "leader PID must clear at reap, before descendant pipe EOF"
        );
        let terminal = custody.terminal_resources();
        assert_eq!(terminal.status(), crate::TerminalResourceStatus::Complete);
        assert_eq!(terminal.observed_attempts(), 1);

        let filter = SessionFilter {
            runtime_id: Some("claude-code".into()),
            cwd_prefix: Some(root.path().display().to_string()),
            ..SessionFilter::default()
        };
        let draining = store.list_sessions(&filter, 10).await.expect("list");
        assert_eq!(draining.len(), 1);
        assert!(
            draining[0].ended_at.is_none(),
            "Store finalisation should still await inherited pipe EOF"
        );

        let mut finalised = None;
        for _ in 0..250 {
            let rows = store.list_sessions(&filter, 10).await.expect("list");
            if rows.first().is_some_and(|row| row.ended_at.is_some()) {
                finalised = rows.into_iter().next();
                break;
            }
            tokio::time::sleep(Duration::from_millis(20)).await;
        }
        let finalised = finalised.expect("output drain should eventually finalise");
        assert_eq!(finalised.exit_code, Some(0));
        assert!(finalised
            .stdout
            .as_deref()
            .is_some_and(|output| output.contains("leader-finished")));
        assert_eq!(runtime.live_count(), 0);
    }

    #[tokio::test]
    async fn send_input_rejected_without_interactive_session() {
        // One-shot sessions (and unknown ids) must reject input — only live
        // PTY sessions accept it.
        let rt = ClaudeCodeRuntime::with_binary("/bin/cat");
        let err = rt
            .send_input(&SessionId::new(), "nope")
            .await
            .expect_err("send_input must fail without a live interactive session");
        assert!(matches!(err, Error::InvalidArgument(_)));
    }

    #[tokio::test]
    async fn kill_unknown_session_errors() {
        let rt = ClaudeCodeRuntime::with_binary("/bin/cat");
        let err = rt
            .kill(&SessionId::new())
            .await
            .expect_err("killing an unknown session must error");
        assert!(matches!(err, Error::NotFound(_)));
    }
}
