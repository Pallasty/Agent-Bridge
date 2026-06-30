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
//! v0.3 addition: a per-runtime PID registry lets [`Self::kill`] send SIGTERM
//! to in-flight sessions. Shells out to `/bin/kill -TERM <pid>` to avoid
//! pulling in `libc` / `nix` for one syscall.
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
use std::collections::HashMap;
use std::process::Stdio;
use std::sync::Arc;
use std::time::{SystemTime, UNIX_EPOCH};
use tokio::process::Command;
use tracing::{info, warn};

use crate::pty_session::{PtyExit, PtySession};
use crate::{AgentCapabilities, AgentRuntime, AgentSession, SpawnConfig};

#[derive(Clone)]
pub struct ClaudeCodeRuntime {
    binary: String,
    interactive_args: Vec<String>,
    store: Option<Arc<dyn StateStore>>,
    /// SessionId → PID of the live one-shot child process.
    children: Arc<DashMap<String, u32>>,
    /// SessionId → live interactive PTY session (live `send_input`).
    interactive: Arc<DashMap<String, Arc<PtySession>>>,
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
        self.interactive
            .get(session.as_str())
            .map(|kv| kv.output_snapshot())
    }

    /// Launch the agent CLI inside a PTY the daemon owns and keep it alive for
    /// successive [`Self::send_input`] turns. Mirrors the one-shot path's
    /// StateStore bookkeeping (start row at spawn, finalise on exit).
    async fn spawn_interactive(&self, cfg: SpawnConfig) -> Result<AgentSession> {
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

        // Interactive Claude Code is the TUI (no `-p`). The host can provide
        // launch flags such as `--no-chrome` to avoid first-run prompts; tests
        // keep the default empty so `/bin/cat` remains a clean PTY stand-in.
        let args = self.interactive_args.clone();
        let (session, exit_rx) = PtySession::spawn(&self.binary, &args, &cwd, &cfg.env)?;
        let session = Arc::new(session);
        let pid = session.pid();
        self.interactive
            .insert(session_id.as_str().to_string(), session.clone());
        info!(session = %session_id, pid, cwd = %cwd, "claude-code interactive (PTY) session started");

        // Optional first turn: type the initial prompt and submit it.
        if let Some(p) = cfg.initial_prompt.as_deref() {
            if !p.is_empty() {
                if let Err(e) = session.write_input(&format!("{p}\r")) {
                    warn!(session = %session_id, error = %e, "claude-code: initial prompt write failed");
                }
            }
        }

        // Finalise on child exit (EOF on the PTY master). Mirrors the one-shot
        // wait task: stdout carries the merged PTY stream; stderr is None
        // because a PTY merges the two.
        let sid_bg = session_id.clone();
        let store_bg = self.store.clone();
        let interactive_bg = self.interactive.clone();
        tokio::spawn(async move {
            let exit = exit_rx.await;
            interactive_bg.remove(sid_bg.as_str());
            let ended_at = now_secs();
            match exit {
                Ok(PtyExit { exit_code, output }) => {
                    info!(
                        session = %sid_bg,
                        exit = ?exit_code,
                        output_preview = %truncate(&output, 200),
                        "claude-code interactive session finished"
                    );
                    if let Some(store) = store_bg {
                        let _ = store
                            .finalise_session(&sid_bg, ended_at, exit_code, Some(output), None)
                            .await;
                    }
                }
                Err(_) => {
                    warn!(session = %sid_bg, "claude-code: pty exit channel closed without a result");
                    if let Some(store) = store_bg {
                        let _ = store
                            .finalise_session(
                                &sid_bg,
                                ended_at,
                                None,
                                None,
                                Some("pty reader ended unexpectedly".into()),
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
        let pid = child.id().unwrap_or(0);
        if pid != 0 {
            self.children.insert(session_id.as_str().to_string(), pid);
        }
        info!(session = %session_id, pid, cwd = %cwd, "claude-code session started");

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

        Ok(AgentSession {
            id: session_id,
            runtime_id: self.id().into(),
            cwd,
        })
    }

    async fn send_input(&self, session: &SessionId, text: &str) -> Result<()> {
        let Some(sess) = self.interactive.get(session.as_str()).map(|kv| kv.clone()) else {
            return Err(Error::InvalidArgument(format!(
                "claude-code: no live interactive session {session}. One-shot (`-p`) sessions \
                 do not accept input — spawn with `interactive: true` to open a live PTY session."
            )));
        };
        // Each call submits one turn: type the text, then a carriage return.
        // The PTY line discipline maps CR→NL on input; this is the claude-code
        // injection profile (type-then-Enter). Run the blocking write off the
        // runtime so a full PTY input buffer can't stall it.
        let payload = format!("{text}\r");
        tokio::task::spawn_blocking(move || sess.write_input(&payload))
            .await
            .map_err(|e| Error::Backend(format!("send_input join: {e}")))?
    }

    async fn kill(&self, session: &SessionId) -> Result<()> {
        // Interactive PTY session: signal the child via its kill handle. The
        // background reader sees EOF, reaps, and finalises the session row.
        if let Some(sess) = self.interactive.get(session.as_str()).map(|kv| kv.clone()) {
            sess.kill()?;
            info!(session = %session, pid = sess.pid(), "interactive PTY session killed");
            return Ok(());
        }

        let pid = match self.children.get(session.as_str()) {
            Some(p) => *p,
            None => {
                return Err(Error::NotFound(format!(
                    "no live child for session {session} (already finished or unknown)"
                )));
            }
        };
        // Shell out to /bin/kill so we don't pull in libc/nix for one syscall.
        let status = tokio::process::Command::new("/bin/kill")
            .arg("-TERM")
            .arg(pid.to_string())
            .status()
            .await
            .map_err(|e| Error::Backend(format!("kill -TERM {pid}: {e}")))?;
        if !status.success() {
            return Err(Error::Backend(format!("/bin/kill exited with {status:?}")));
        }
        // Background wait task will see the child die, clean up `children` map,
        // and finalise the session row with the SIGTERM exit code.
        info!(session = %session, pid, "SIGTERM sent");
        Ok(())
    }

    fn pid_for(&self, session: &SessionId) -> Option<u32> {
        if let Some(sess) = self.interactive.get(session.as_str()) {
            let p = sess.pid();
            if p != 0 {
                return Some(p);
            }
        }
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
