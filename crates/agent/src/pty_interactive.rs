//! Shared interactive-PTY session orchestration for agent runtimes.
//!
//! `claude-code` and `codex` both expose the same interactive contract: when
//! spawned with [`SpawnConfig::interactive`], launch
//! the CLI inside a daemon-owned pseudo-terminal (see [`crate::pty_session`]),
//! keep the child alive across `send_input` turns, and finalise to the
//! [`StateStore`] on exit, the same close-the-loop contract as the one-shot
//! path. This module centralises that orchestration so each runtime only owns
//! its live-session map (`InteractiveMap`) plus its launch argv; the
//! storage-agnostic PTY core stays in [`crate::pty_session`].
//!
//! Extracted from the original per-runtime copies once the second interactive
//! runtime joined `claude-code`. Future runtimes can share the same helper when
//! they implement live PTY mode.

use ab_core::{Error, Result, SessionId};
use ab_store::{StateStore, StoredSession};
use dashmap::DashMap;
use std::sync::Arc;
use std::time::{Duration, Instant, SystemTime, UNIX_EPOCH};
use tracing::{info, warn};

use crate::pty_session::{PtyExit, PtySession};
use crate::{AgentSession, SpawnConfig};

/// A runtime's live interactive sessions, keyed by `SessionId`. Cheap to share:
/// the runtime keeps one clone in its struct and hands the helpers a borrow.
pub type InteractiveMap = Arc<DashMap<String, Arc<PtySession>>>;

/// Grace between the graceful SIGHUP sent by [`kill_interactive`] and the
/// process-group SIGKILL escalation for children that catch and survive it.
/// gemini's Ink TUI catches SIGHUP *and* SIGTERM and keeps running (observed
/// live 2026-07-01); well-behaved CLIs exit on SIGHUP long before this fires.
const KILL_ESCALATION_GRACE: Duration = Duration::from_secs(3);

/// How a runtime's interactive TUI accepts a submitted turn. Simple line REPLs
/// (claude-code, `/bin/cat`) submit on a bare CR written together with the text;
/// full-screen TUIs that enable the Kitty keyboard protocol (codex) only submit
/// on a CSI-u Enter (`ESC [ 13 u`) and need the typed text rendered before the
/// submit key lands — hence a settle delay and a separate write.
#[derive(Clone, Copy)]
pub struct SubmitProfile {
    /// Byte sequence that submits the current input line.
    pub key: &'static str,
    /// Delay between writing the turn text and the submit key. Zero submits in a
    /// single combined write (legacy line REPLs); non-zero splits the two writes
    /// and waits in between so a TUI can render the input first.
    pub settle: Duration,
    /// Delay after spawning a live TUI before sending the optional first prompt.
    /// Full-screen TUIs often ignore input sent during alternate-screen startup;
    /// line-REPL stand-ins keep this at zero.
    pub initial_prompt_delay: Duration,
    /// Optional output markers that indicate the initial composer is ready to
    /// accept a first turn. When set, the helper waits for any marker before
    /// typing `initial_prompt`; this avoids fixed sleeps racing slow TUI boot.
    pub initial_prompt_ready_markers: &'static [&'static str],
    /// Maximum time to wait for [`Self::initial_prompt_ready_markers`] before
    /// falling back to the delay-only behavior.
    pub initial_prompt_ready_timeout: Duration,
}

impl SubmitProfile {
    /// Legacy line REPL: CR submits immediately, written with the text in one go.
    pub const ENTER: SubmitProfile = SubmitProfile {
        key: "\r",
        settle: Duration::ZERO,
        initial_prompt_delay: Duration::ZERO,
        initial_prompt_ready_markers: &[],
        initial_prompt_ready_timeout: Duration::ZERO,
    };
    /// Kitty-keyboard-protocol TUI (codex): submit on CSI-u Enter after a render
    /// settle, written separately from the text.
    pub const KITTY_ENTER: SubmitProfile = SubmitProfile {
        key: "\x1b[13u",
        settle: Duration::from_millis(500),
        initial_prompt_delay: Duration::ZERO,
        initial_prompt_ready_markers: &[],
        initial_prompt_ready_timeout: Duration::ZERO,
    };
    /// Ink/React TUI (gemini): submits on a **bare CR** like a line REPL, but the
    /// CR must be written *separately* from the text after a render settle — Ink
    /// re-renders on each input and a zero-settle combined `text\r` write drops
    /// the CR (empirically: combined never submits; split @600ms round-trips).
    /// gemini also enables the Kitty keyboard protocol yet still submits on CR,
    /// so Kitty-enable does NOT imply `KITTY_ENTER` — the key was probed.
    pub const ENTER_SETTLED: SubmitProfile = SubmitProfile {
        key: "\r",
        settle: Duration::from_millis(600),
        initial_prompt_delay: Duration::ZERO,
        initial_prompt_ready_markers: &[],
        initial_prompt_ready_timeout: Duration::ZERO,
    };

    pub fn with_initial_prompt_delay(mut self, delay: Duration) -> Self {
        self.initial_prompt_delay = delay;
        self
    }

    pub fn with_initial_prompt_ready_markers(
        mut self,
        markers: &'static [&'static str],
        timeout: Duration,
    ) -> Self {
        self.initial_prompt_ready_markers = markers;
        self.initial_prompt_ready_timeout = timeout;
        self
    }
}

/// Write one turn — the text then the submit key — honouring a runtime's
/// [`SubmitProfile`]. A zero settle writes both in one go (legacy CR REPLs); a
/// non-zero settle types the text, waits for the TUI to render it, then sends the
/// submit key as a separate write (Kitty-protocol TUIs like codex otherwise drop
/// a submit that arrives glued to the text). Blocking PTY writes run off the
/// runtime so a full input buffer can't stall it.
async fn submit_turn(sess: &Arc<PtySession>, text: &str, submit: SubmitProfile) -> Result<()> {
    if submit.settle.is_zero() {
        let payload = format!("{text}{}", submit.key);
        let s = sess.clone();
        tokio::task::spawn_blocking(move || s.write_input(&payload))
            .await
            .map_err(|e| Error::Backend(format!("submit_turn join: {e}")))?
    } else {
        let s1 = sess.clone();
        let t = text.to_string();
        tokio::task::spawn_blocking(move || s1.write_input(&t))
            .await
            .map_err(|e| Error::Backend(format!("submit_turn join: {e}")))??;
        tokio::time::sleep(submit.settle).await;
        let s2 = sess.clone();
        let key = submit.key;
        tokio::task::spawn_blocking(move || s2.write_input(key))
            .await
            .map_err(|e| Error::Backend(format!("submit_turn join: {e}")))?
    }
}

async fn wait_for_initial_prompt_ready(
    sess: &Arc<PtySession>,
    session: &SessionId,
    runtime_id: &str,
    submit: SubmitProfile,
) {
    if submit.initial_prompt_ready_markers.is_empty()
        || submit.initial_prompt_ready_timeout.is_zero()
    {
        return;
    }
    let deadline = Instant::now() + submit.initial_prompt_ready_timeout;
    loop {
        let output = sess.output_snapshot();
        if submit
            .initial_prompt_ready_markers
            .iter()
            .any(|marker| output.contains(marker))
        {
            return;
        }
        if Instant::now() >= deadline {
            warn!(
                session = %session,
                runtime = %runtime_id,
                "interactive: initial prompt readiness marker timed out; falling back to delayed submit"
            );
            return;
        }
        tokio::time::sleep(Duration::from_millis(100)).await;
    }
}

fn now_secs() -> i64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|d| d.as_secs() as i64)
        .unwrap_or(0)
}

/// Launch `binary args...` inside a daemon-owned PTY, register it under a fresh
/// `SessionId`, optionally submit `cfg.initial_prompt` as the first turn, and
/// finalise to `store` on exit. The interactive entry point (the CLI's live
/// TUI/REPL, not its one-shot subcommand) and any launch flags are the caller's
/// to supply via `interactive_args`.
pub async fn spawn_interactive(
    runtime_id: &str,
    binary: &str,
    interactive_args: &[String],
    store: &Option<Arc<dyn StateStore>>,
    interactive: &InteractiveMap,
    cfg: SpawnConfig,
    submit: SubmitProfile,
) -> Result<AgentSession> {
    let launch = crate::sandbox::wrap_local_command(
        runtime_id,
        &cfg.cwd,
        &cfg.env,
        binary,
        interactive_args,
    )?;
    let session_id = SessionId::new();
    let cwd = cfg.cwd.clone();

    if let Some(store) = store {
        let initial = StoredSession {
            id: session_id.clone(),
            runtime_id: runtime_id.into(),
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

    let (session, exit_rx) = PtySession::spawn(
        &launch.program,
        &launch.args,
        &cwd,
        &cfg.env,
        launch.sandboxed,
    )?;
    let session = Arc::new(session);
    let pid = session.pid();
    let process_custody = session.process_custody();
    interactive.insert(session_id.as_str().to_string(), session.clone());
    info!(session = %session_id, runtime = %runtime_id, pid, cwd = %cwd, sandboxed = launch.sandboxed, "interactive (PTY) session started");

    // v41: stamp the child's process identity onto the session row so the
    // orphan reaper can later kill a proven-abandoned process group even
    // after this owning process is SIGKILLed (no Drop ever fires then).
    // pgid == pid: portable_pty setsids the child (see PtySession::kill_group).
    // Fail-soft: an unstamped row just stays reaper-invisible (legacy rule).
    if let Some(store) = store {
        if pid != 0 {
            let owner_pid = std::process::id();
            if let Err(e) = store
                .update_session_process(
                    &session_id,
                    pid as i64,
                    pid as i64,
                    process_custody
                        .as_ref()
                        .and_then(|custody| custody.start_ticks())
                        .and_then(|ticks| i64::try_from(ticks).ok()),
                    owner_pid as i64,
                    crate::pty_session::proc_start_ticks(owner_pid),
                )
                .await
            {
                warn!(session = %session_id, error = %e, "store: update_session_process failed");
            }
        }
    }

    // Optional first turn: type the initial prompt and submit it.
    if let Some(p) = cfg.initial_prompt.as_deref() {
        if !p.is_empty() {
            if !submit.initial_prompt_delay.is_zero() {
                tokio::time::sleep(submit.initial_prompt_delay).await;
            }
            wait_for_initial_prompt_ready(&session, &session_id, runtime_id, submit).await;
            if let Err(e) = submit_turn(&session, p, submit).await {
                warn!(session = %session_id, runtime = %runtime_id, error = %e, "interactive: initial prompt write failed");
            }
        }
    }

    // Finalise on child exit (EOF on the PTY master). Mirrors the one-shot wait
    // task: stdout carries the merged PTY stream; stderr is None (a PTY merges
    // the two).
    let sid_bg = session_id.clone();
    let store_bg = store.clone();
    let interactive_bg = interactive.clone();
    let rid = runtime_id.to_string();
    tokio::spawn(async move {
        let exit = exit_rx.await;
        interactive_bg.remove(sid_bg.as_str());
        let ended_at = now_secs();
        match exit {
            Ok(PtyExit { exit_code, output }) => {
                info!(session = %sid_bg, runtime = %rid, exit = ?exit_code, "interactive session finished");
                if let Some(store) = store_bg {
                    let _ = store
                        .finalise_session(&sid_bg, ended_at, exit_code, Some(output), None)
                        .await;
                }
            }
            Err(_) => {
                warn!(session = %sid_bg, runtime = %rid, "pty exit channel closed without a result");
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
        runtime_id: runtime_id.into(),
        cwd,
        sandbox_profile_requested: launch.sandboxed.then(|| "workspace".into()),
        process_custody,
    })
}

/// Type one turn into a live interactive session and submit it (CR). Rejects
/// with `InvalidArgument` when the session isn't a live PTY session (one-shot
/// or unknown id). Runs the blocking write off the runtime so a full PTY input
/// buffer can't stall it.
pub async fn send_input(
    runtime_id: &str,
    interactive: &InteractiveMap,
    session: &SessionId,
    text: &str,
    submit: SubmitProfile,
) -> Result<()> {
    let Some(sess) = interactive.get(session.as_str()).map(|kv| kv.clone()) else {
        return Err(Error::InvalidArgument(format!(
            "{runtime_id}: no live interactive session {session}. One-shot sessions do not \
             accept input; spawn with `interactive: true` to open a live PTY session."
        )));
    };
    submit_turn(&sess, text, submit).await
}

/// Kill a live interactive session if one exists. Returns `Some(result)` when
/// `session` was an interactive PTY session (handled here); `None` to let the
/// caller fall through to its one-shot kill path.
///
/// The graceful kill (SIGHUP to the leader) is followed by a background
/// escalation: if the child has not exited within [`KILL_ESCALATION_GRACE`]
/// (its finalise task removes the map entry on PTY EOF, so a lingering entry
/// means a live child), the whole process group gets an uncatchable SIGKILL.
/// Must be called from within a tokio runtime (all runtime `kill` paths are).
pub fn kill_interactive(
    runtime_id: &str,
    interactive: &InteractiveMap,
    session: &SessionId,
) -> Option<Result<()>> {
    let sess = interactive.get(session.as_str()).map(|kv| kv.clone())?;
    match sess.kill() {
        Ok(()) => {
            info!(session = %session, runtime = %runtime_id, pid = sess.pid(), "interactive PTY session killed");
            let map = interactive.clone();
            let key = session.as_str().to_string();
            let rid = runtime_id.to_string();
            tokio::spawn(async move {
                tokio::time::sleep(KILL_ESCALATION_GRACE).await;
                if !map.contains_key(&key) {
                    return; // exited gracefully; finalise task cleaned up
                }
                warn!(
                    session = %key,
                    runtime = %rid,
                    pid = sess.pid(),
                    "interactive child survived SIGHUP grace; escalating to process-group SIGKILL"
                );
                if let Err(e) = sess.kill_group() {
                    warn!(session = %key, runtime = %rid, error = %e, "SIGKILL escalation failed");
                }
            });
            Some(Ok(()))
        }
        Err(e) => Some(Err(e)),
    }
}

/// OS pid of a live interactive session, if one is tracked and the platform
/// reported a non-zero pid.
pub fn interactive_pid(interactive: &InteractiveMap, session: &SessionId) -> Option<u32> {
    interactive
        .get(session.as_str())
        .map(|kv| kv.pid())
        .filter(|p| *p != 0)
}

/// Snapshot the merged PTY output of a live interactive session, if one exists.
/// Returns `None` once the session has exited (and been finalised).
pub fn interactive_output(interactive: &InteractiveMap, session: &SessionId) -> Option<String> {
    interactive
        .get(session.as_str())
        .map(|kv| kv.output_snapshot())
}

#[cfg(test)]
mod tests {
    use super::*;

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

    #[cfg(unix)]
    #[tokio::test]
    async fn initial_prompt_waits_for_ready_marker_before_submit() {
        let interactive: InteractiveMap = Arc::new(DashMap::new());
        let store: Option<Arc<dyn StateStore>> = None;
        let args = vec![
            "-lc".to_string(),
            "while IFS= read -r -t 0.2 _line; do :; done; \
             printf 'READY-FOR-FIRST-TURN\\n'; exec cat"
                .to_string(),
        ];
        let submit = SubmitProfile::ENTER
            .with_initial_prompt_ready_markers(&["READY-FOR-FIRST-TURN"], Duration::from_secs(3));
        let sess = spawn_interactive(
            "test-runtime",
            "/bin/bash",
            &args,
            &store,
            &interactive,
            SpawnConfig {
                cwd: "/tmp".into(),
                initial_prompt: Some("first-turn-after-ready".into()),
                interactive: true,
                ..Default::default()
            },
            submit,
        )
        .await
        .expect("spawn delayed-ready stand-in");

        let submitted = wait_for(5000, 25, || {
            interactive_output(&interactive, &sess.id)
                .map(|o| o.contains("first-turn-after-ready"))
                .unwrap_or(false)
        })
        .await;
        assert!(
            submitted,
            "initial prompt should be held until the readiness marker appears"
        );

        kill_interactive("test-runtime", &interactive, &sess.id)
            .expect("interactive session should be live")
            .expect("kill delayed-ready stand-in");
    }

    #[cfg(unix)]
    #[tokio::test]
    async fn kill_escalates_to_sigkill_when_child_ignores_hup_and_term() {
        let interactive: InteractiveMap = Arc::new(DashMap::new());
        let store: Option<Arc<dyn StateStore>> = None;
        // Stand-in for signal-tolerant TUIs: gemini's Ink TUI catches SIGHUP
        // AND SIGTERM and keeps running (observed live 2026-07-01), so the
        // graceful SIGHUP from PtySession::kill never reaps it. The marker
        // echo lets the test wait until the traps are armed — a SIGHUP that
        // races trap setup kills the child outright and the test would pass
        // without exercising escalation at all.
        let args = vec![
            "-c".to_string(),
            "trap '' HUP TERM; echo TRAP-ARMED; while :; do sleep 0.1; done".to_string(),
        ];
        let sess = spawn_interactive(
            "test-runtime",
            "/bin/bash",
            &args,
            &store,
            &interactive,
            SpawnConfig {
                cwd: "/tmp".into(),
                interactive: true,
                ..Default::default()
            },
            SubmitProfile::ENTER,
        )
        .await
        .expect("spawn signal-immune stand-in");

        let armed = wait_for(5000, 25, || {
            interactive_output(&interactive, &sess.id)
                .map(|o| o.contains("TRAP-ARMED"))
                .unwrap_or(false)
        })
        .await;
        assert!(armed, "stand-in must arm its traps before the kill");

        kill_interactive("test-runtime", &interactive, &sess.id)
            .expect("interactive session should be live")
            .expect("kill signal-immune stand-in");

        // Well inside the grace window the child must still be alive — it
        // caught the graceful SIGHUP. This pins the reap below on the
        // escalation, not on the SIGHUP itself.
        tokio::time::sleep(Duration::from_millis(1000)).await;
        assert!(
            interactive.contains_key(sess.id.as_str()),
            "stand-in died to the plain SIGHUP; escalation path not exercised"
        );

        // The finalise task removes the map entry on child exit (PTY EOF), so
        // entry removal == the child really died. Must happen within the
        // escalation grace plus slack.
        let reaped = wait_for(KILL_ESCALATION_GRACE.as_millis() as u64 + 5000, 100, || {
            !interactive.contains_key(sess.id.as_str())
        })
        .await;
        assert!(
            reaped,
            "a child that ignores SIGHUP/SIGTERM must be SIGKILLed after the grace period"
        );
    }

    #[cfg(unix)]
    #[tokio::test]
    async fn dropping_session_group_kills_signal_immune_child() {
        let interactive: InteractiveMap = Arc::new(DashMap::new());
        let store: Option<Arc<dyn StateStore>> = None;
        let args = vec![
            "-c".to_string(),
            "trap '' HUP TERM; echo TRAP-ARMED; while :; do sleep 0.1; done".to_string(),
        ];
        let sess = spawn_interactive(
            "test-runtime",
            "/bin/bash",
            &args,
            &store,
            &interactive,
            SpawnConfig {
                cwd: "/tmp".into(),
                interactive: true,
                ..Default::default()
            },
            SubmitProfile::ENTER,
        )
        .await
        .expect("spawn signal-immune stand-in");

        let armed = wait_for(5000, 25, || {
            interactive_output(&interactive, &sess.id)
                .map(|o| o.contains("TRAP-ARMED"))
                .unwrap_or(false)
        })
        .await;
        assert!(armed, "stand-in must arm its traps before the drop");
        let pid = interactive_pid(&interactive, &sess.id).expect("child pid") as i32;

        // Dropping the last session handle (the map entry) must reap even a
        // child that catches SIGHUP/SIGTERM: the kill_interactive escalation
        // task is cancelled when the tokio runtime shuts down inside the
        // grace window, leaving Drop as the only backstop.
        interactive.remove(sess.id.as_str());
        let dead = wait_for(5000, 50, || unsafe { libc::kill(pid, 0) } == -1).await;
        assert!(
            dead,
            "dropping the session must SIGKILL a signal-immune child's process group"
        );
    }
}
