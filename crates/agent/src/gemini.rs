//! Google Gemini CLI agent runtime.
//!
//! Wraps the Google Gemini CLI in two modes:
//!
//! - **One-shot**: `gemini -p "<prompt>"` — headless single-shot that prints the
//!   model response to stdout and exits.
//! - **Interactive**: a daemon-owned PTY running the bare `gemini` TUI, kept
//!   alive across `send_input` turns (shared [`crate::pty_interactive`] helper).
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
use std::process::Stdio;
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::Arc;
use std::time::{Duration, SystemTime, UNIX_EPOCH};
use tokio::process::Command;
use tracing::{info, warn};

use crate::pty_interactive::{self, InteractiveMap};
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
    /// Launch flags for the interactive PTY entry point (the bare `gemini` TUI).
    /// Host-supplied; default empty = bare `gemini`, which starts the interactive
    /// TUI (the one-shot path adds `-p`, so it never launches the TUI).
    interactive_args: Vec<String>,
    /// SessionId → live interactive PTY session (live `send_input`).
    interactive: InteractiveMap,
    /// How the gemini TUI accepts a submitted turn. Real-binary verified: gemini
    /// enables the Kitty keyboard protocol (like codex) yet still submits on a
    /// **bare CR** — so the key is CR, NOT CSI-u Enter. But its Ink/React input
    /// re-renders on each keystroke and drops a zero-settle combined `text\r`
    /// write, so the CR must be split off after a render settle. Hence
    /// `SubmitProfile::ENTER_SETTLED`, not `ENTER` (combined) or `KITTY_ENTER`.
    submit: pty_interactive::SubmitProfile,
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
            interactive_args: Vec::new(),
            interactive: Arc::new(DashMap::new()),
            // gemini: bare CR submit, but split off after a render settle — the
            // Ink TUI drops a combined text+CR write (real-binary verified
            // 2026-06-30: combined never submits, split @600ms round-trips).
            submit: pty_interactive::SubmitProfile::ENTER_SETTLED
                .with_initial_prompt_delay(Duration::from_secs(3)),
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

    /// Launch flags for the interactive `gemini` TUI (default empty = bare
    /// binary). The one-shot `run` path is unaffected — it builds its own argv.
    pub fn with_interactive_args(
        mut self,
        args: impl IntoIterator<Item = impl Into<String>>,
    ) -> Self {
        self.interactive_args = args.into_iter().map(Into::into).collect();
        self
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

    /// Launch the bare `gemini` TUI inside a daemon-owned PTY and keep it alive
    /// for successive [`AgentRuntime::send_input`] turns. Mirrors the one-shot
    /// path's StateStore bookkeeping (start row at spawn, finalise on exit).
    /// Auth/trust for the TUI come from the spawn env (`GEMINI_API_KEY`,
    /// `GEMINI_CLI_TRUST_WORKSPACE=true`) plus the operator's `~/.gemini`
    /// (`selectedType: "gemini-api-key"` to skip the first-run auth dialog).
    async fn spawn_interactive(&self, cfg: SpawnConfig) -> Result<AgentSession> {
        pty_interactive::spawn_interactive(
            self.id(),
            &self.binary,
            &self.interactive_args,
            &self.store,
            &self.interactive,
            cfg,
            self.submit,
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
impl AgentRuntime for GeminiRuntime {
    fn id(&self) -> &str {
        "gemini"
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
                "gemini: 'initial_prompt' is required for one-shot spawn".into(),
            ));
        }
        let model = cfg.model.clone().or_else(|| self.default_model.clone());
        let mut launch_args = vec!["--skip-trust".to_string(), "--yolo".to_string()];
        if let Some(model) = &model {
            launch_args.push("-m".to_string());
            launch_args.push(model.clone());
        }
        launch_args.push("-p".to_string());
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
            sandboxed = launch.sandboxed,
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
            sandbox_profile_requested: launch.sandboxed.then(|| "workspace".into()),
        })
    }

    async fn send_input(&self, session: &SessionId, text: &str) -> Result<()> {
        pty_interactive::send_input(self.id(), &self.interactive, session, text, self.submit).await
    }

    async fn kill(&self, session: &SessionId) -> Result<()> {
        // Interactive PTY session: signal via its kill handle; the background
        // reader sees EOF, reaps, and finalises the session row.
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
        info!(session = %session, pid, runtime = "gemini", "SIGTERM sent");
        Ok(())
    }

    fn pid_for(&self, session: &SessionId) -> Option<u32> {
        if let Some(pid) = pty_interactive::interactive_pid(&self.interactive, session) {
            return Some(pid);
        }
        self.children.get(session.as_str()).map(|kv| *kv)
    }

    /// Trait-level exposure of the live interactive PTY buffer so
    /// `agent_session_output` can read a reply through `dyn AgentRuntime`;
    /// mirrors inherent [`GeminiRuntime::read_interactive_output`].
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
    use std::collections::HashMap;

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

    fn interactive_cfg(cwd: &str) -> SpawnConfig {
        SpawnConfig {
            cwd: cwd.into(),
            env: HashMap::new(),
            initial_prompt: None,
            model: None,
            node: None,
            user: None,
            interactive: true,
        }
    }

    #[tokio::test]
    async fn interactive_session_multi_turn_round_trips() {
        // `/bin/cat` is a deterministic stand-in for the gemini TUI: it stays
        // alive and echoes each submitted line back through the PTY. This proves
        // the PTY plumbing; the real submit key (bare CR, despite gemini enabling
        // the Kitty keyboard protocol) is covered by the ignored
        // `gemini_real_interactive` integration test.
        let rt = GeminiRuntime::new().with_binary("/bin/cat");
        let sess = rt
            .spawn(interactive_cfg("/tmp"))
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
        let rt = GeminiRuntime::new().with_binary("/bin/cat");
        let mut cfg = interactive_cfg("/tmp");
        cfg.initial_prompt = Some("first-turn-marker".into());
        let sess = rt.spawn(cfg).await.expect("spawn interactive");
        let ok = wait_for(2000, 25, || {
            rt.read_interactive_output(&sess.id)
                .map(|o| o.contains("first-turn-marker"))
                .unwrap_or(false)
        })
        .await;
        assert!(
            ok,
            "the initial prompt should be submitted as the first turn"
        );
        rt.kill(&sess.id).await.expect("kill");
    }

    #[cfg(unix)]
    #[tokio::test]
    async fn interactive_initial_prompt_waits_for_tui_boot_settle() {
        let rt = GeminiRuntime::new()
            .with_binary("/bin/bash")
            .with_interactive_args([
                "-lc",
                "while IFS= read -r -t 0.2 _line; do :; done; printf 'READY\\n'; exec cat",
            ]);
        let mut cfg = interactive_cfg("/tmp");
        cfg.initial_prompt = Some("boot-settle-marker".into());
        let sess = rt.spawn(cfg).await.expect("spawn delayed-ready stand-in");

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

    #[tokio::test]
    async fn interactive_args_are_passed_to_pty_child() {
        let rt = GeminiRuntime::new()
            .with_binary("/bin/sh")
            .with_interactive_args(["-c", "printf 'ARGV:%s\\n' \"$1\"; cat", "sh", "flag-one"]);
        let sess = rt
            .spawn(interactive_cfg("/tmp"))
            .await
            .expect("spawn interactive");
        let ok = wait_for(2000, 25, || {
            rt.read_interactive_output(&sess.id)
                .map(|o| o.contains("ARGV:flag-one"))
                .unwrap_or(false)
        })
        .await;
        assert!(ok, "interactive_args should reach the PTY child");
        rt.kill(&sess.id).await.expect("kill");
    }

    #[tokio::test]
    async fn trait_read_interactive_output_surfaces_live_buffer() {
        // agent_session_output reads through `dyn AgentRuntime`, so the trait
        // method (not just the inherent one) must surface the live PTY buffer.
        let rt = GeminiRuntime::new().with_binary("/bin/cat");
        let dynrt: &dyn AgentRuntime = &rt;
        let sess = dynrt
            .spawn(interactive_cfg("/tmp"))
            .await
            .expect("spawn interactive");
        dynrt
            .send_input(&sess.id, "gamma-three")
            .await
            .expect("turn");
        let ok = wait_for(2000, 25, || {
            dynrt
                .read_interactive_output(&sess.id)
                .map(|o| o.contains("gamma-three"))
                .unwrap_or(false)
        })
        .await;
        assert!(
            ok,
            "trait-dispatched read_interactive_output should surface the live PTY buffer"
        );
        assert!(
            dynrt.read_interactive_output(&SessionId::new()).is_none(),
            "unknown session should read as None"
        );
        dynrt.kill(&sess.id).await.expect("kill");
    }

    #[tokio::test]
    async fn send_input_rejected_without_interactive_session() {
        // One-shot sessions (and unknown ids) must reject input — only live PTY
        // sessions accept it.
        let rt = GeminiRuntime::new().with_binary("/bin/cat");
        let err = rt
            .send_input(&SessionId::new(), "nope")
            .await
            .expect_err("send_input must fail without a live interactive session");
        assert!(matches!(err, Error::InvalidArgument(_)));
    }

    #[tokio::test]
    async fn kill_unknown_session_errors() {
        let rt = GeminiRuntime::new().with_binary("/bin/cat");
        let err = rt
            .kill(&SessionId::new())
            .await
            .expect_err("kill of an unknown session must error");
        assert!(matches!(err, Error::NotFound(_)));
    }
}
