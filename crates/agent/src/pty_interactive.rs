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
use std::time::{SystemTime, UNIX_EPOCH};
use tracing::{info, warn};

use crate::pty_session::{PtyExit, PtySession};
use crate::{AgentSession, SpawnConfig};

/// A runtime's live interactive sessions, keyed by `SessionId`. Cheap to share:
/// the runtime keeps one clone in its struct and hands the helpers a borrow.
pub type InteractiveMap = Arc<DashMap<String, Arc<PtySession>>>;

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
) -> Result<AgentSession> {
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
        };
        if let Err(e) = store.save_session(&initial).await {
            warn!(session = %session_id, error = %e, "store: save_session failed");
        }
    }

    let (session, exit_rx) = PtySession::spawn(binary, interactive_args, &cwd, &cfg.env)?;
    let session = Arc::new(session);
    let pid = session.pid();
    interactive.insert(session_id.as_str().to_string(), session.clone());
    info!(session = %session_id, runtime = %runtime_id, pid, cwd = %cwd, "interactive (PTY) session started");

    // Optional first turn: type the initial prompt and submit it.
    if let Some(p) = cfg.initial_prompt.as_deref() {
        if !p.is_empty() {
            if let Err(e) = session.write_input(&format!("{p}\r")) {
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
) -> Result<()> {
    let Some(sess) = interactive.get(session.as_str()).map(|kv| kv.clone()) else {
        return Err(Error::InvalidArgument(format!(
            "{runtime_id}: no live interactive session {session}. One-shot sessions do not \
             accept input; spawn with `interactive: true` to open a live PTY session."
        )));
    };
    let payload = format!("{text}\r");
    tokio::task::spawn_blocking(move || sess.write_input(&payload))
        .await
        .map_err(|e| Error::Backend(format!("send_input join: {e}")))?
}

/// Kill a live interactive session if one exists. Returns `Some(result)` when
/// `session` was an interactive PTY session (handled here); `None` to let the
/// caller fall through to its one-shot kill path.
pub fn kill_interactive(
    runtime_id: &str,
    interactive: &InteractiveMap,
    session: &SessionId,
) -> Option<Result<()>> {
    let sess = interactive.get(session.as_str()).map(|kv| kv.clone())?;
    match sess.kill() {
        Ok(()) => {
            info!(session = %session, runtime = %runtime_id, pid = sess.pid(), "interactive PTY session killed");
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
