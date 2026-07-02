//! PTY-backed interactive agent session (live `send_input`).
//!
//! The one-shot path in [`crate::claude_code`] spawns `claude -p "<prompt>"`
//! with piped stdio and captures output exactly once. Interactive mode instead
//! launches the agent CLI inside a pseudo-terminal **the daemon owns**, keeps
//! the child alive across turns, and lets callers type successive prompts via
//! `send_input`.
//!
//! This module is the focused, storage-agnostic core: it owns the PTY master
//! (writer + reader + killer), accumulates the merged output stream, and
//! resolves a one-shot channel with the exit code + full output when the child
//! exits (EOF on the master, including when killed). The runtime layer decides
//! how to persist that (`StateStore`), mirroring the one-shot wait task.
//!
//! Why a dedicated module rather than reusing `ab-terminal`'s `PtyBackend`:
//! that backend is shell-oriented (it only spawns `$SHELL`, has no argv
//! override, lazy-spawns panes, keys on `PaneId`, and never touches the
//! `StateStore`). The agent lifecycle wants none of that: it wants an
//! arbitrary `binary args...`, a `SessionId`, and StateStore finalisation. The
//! PTY plumbing itself is small enough that a purpose-built session is cleaner
//! than bending the shell backend (and avoids an `ab-agent -> ab-terminal` dep).

use ab_core::{Error, Result};
use portable_pty::{native_pty_system, CommandBuilder, PtySize};
use std::collections::HashMap;
use std::io::{Read, Write};
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::{Arc, Mutex};
use tokio::sync::oneshot;

/// Default PTY geometry for an interactive agent session. Matches the
/// `ab-terminal` `PtyBackend` so TUIs wrap their output the same way.
const DEFAULT_ROWS: u16 = 40;
const DEFAULT_COLS: u16 = 120;
const MAX_CAPTURE_CHARS: usize = 262_144;
const TRUNCATED_PREFIX: &str = "[agent-bridge: PTY output truncated; keeping latest output]\n";

/// Delivered through the session's exit channel once the child exits (the PTY
/// master hits EOF). `output` is the full merged stdout+stderr captured over
/// the session's life; `exit_code` is `None` when the status could not be
/// reaped (e.g. signal death the platform doesn't surface as a code).
pub struct PtyExit {
    pub exit_code: Option<i32>,
    pub output: String,
}

/// A live PTY-backed child process. Cheap to `Arc`-share: writes and kills are
/// internally synchronised, so the runtime can hand a clone to a `send_input`
/// blocking task while keeping one in its session map.
pub struct PtySession {
    /// Writer to the PTY master (typing into the agent CLI).
    writer: Mutex<Box<dyn Write + Send>>,
    /// Async-friendly child kill handle (usable from any thread).
    killer: Mutex<Box<dyn portable_pty::ChildKiller + Send + Sync>>,
    /// Live accumulation of the merged output stream (ANSI left intact; the
    /// terminal MCP layer is where rendering/stripping belongs, not here).
    output: Arc<Mutex<String>>,
    /// OS pid of the child, or 0 if the platform did not report one.
    pid: u32,
    /// Set by the reader thread once `child.wait()` has reaped the child.
    /// After the reap the OS may recycle the pid/pgid, so the SIGKILL paths
    /// ([`Self::kill_group`], `Drop`) must become no-ops rather than risk
    /// signalling an unrelated recycled process group.
    reaped: Arc<AtomicBool>,
}

impl PtySession {
    /// Spawn `binary args...` inside a fresh PTY in `cwd` with `env` applied.
    ///
    /// Returns the session handle plus a [`oneshot::Receiver`] that resolves
    /// with the [`PtyExit`] once the child exits (covering normal exit and
    /// kill). A dedicated OS thread drains the master; PTY reads are blocking
    /// `std::io`, so they must not run on the tokio runtime.
    pub fn spawn(
        binary: &str,
        args: &[String],
        cwd: &str,
        env: &HashMap<String, String>,
    ) -> Result<(Self, oneshot::Receiver<PtyExit>)> {
        let pty_system = native_pty_system();
        let pair = pty_system
            .openpty(PtySize {
                rows: DEFAULT_ROWS,
                cols: DEFAULT_COLS,
                pixel_width: 0,
                pixel_height: 0,
            })
            .map_err(|e| Error::Backend(format!("openpty: {e}")))?;

        let mut cmd = CommandBuilder::new(binary);
        for a in args {
            cmd.arg(a);
        }
        if !cwd.is_empty() {
            cmd.cwd(cwd);
        }
        for (k, v) in env {
            cmd.env(k, v);
        }
        // Parity with the env interactive terminals set, so the agent CLI's
        // prompt / pager behaviour matches a "real" terminal.
        cmd.env("TERM", "xterm-256color");

        let child = pair
            .slave
            .spawn_command(cmd)
            .map_err(|e| Error::Backend(format!("spawn {binary}: {e}")))?;
        let pid = child.process_id().unwrap_or(0);
        let killer = child.clone_killer();

        let writer = pair
            .master
            .take_writer()
            .map_err(|e| Error::Backend(format!("take_writer: {e}")))?;
        let reader = pair
            .master
            .try_clone_reader()
            .map_err(|e| Error::Backend(format!("clone_reader: {e}")))?;

        // Drop the slave fd in the parent so the reader sees EOF when the child
        // exits; holding it open would stall the reader and leak the PTY.
        drop(pair.slave);
        // The master is only needed for the writer/reader we already took; we
        // don't resize interactive agent sessions (yet), so let it drop.
        drop(pair.master);

        let output = Arc::new(Mutex::new(String::new()));
        let output_for_thread = output.clone();
        let reaped = Arc::new(AtomicBool::new(false));
        let reaped_for_thread = reaped.clone();
        let (tx, rx) = oneshot::channel();

        std::thread::Builder::new()
            .name(format!("ab-agent-pty-{pid}"))
            .spawn(move || {
                let mut child = child;
                let mut reader = reader;
                let mut buf = [0u8; 4096];
                loop {
                    match reader.read(&mut buf) {
                        Ok(0) => break, // EOF: child exited (or is exiting).
                        Ok(n) => {
                            let chunk = String::from_utf8_lossy(&buf[..n]);
                            if let Ok(mut o) = output_for_thread.lock() {
                                append_capped_output(&mut o, &chunk);
                            }
                        }
                        Err(e) if e.kind() == std::io::ErrorKind::Interrupted => continue,
                        Err(_) => break, // PTY closed / bad fd / etc.
                    }
                }
                // Reap for the exit code now that the master is at EOF.
                let exit_code = child.wait().ok().map(|s| s.exit_code() as i32);
                reaped_for_thread.store(true, Ordering::SeqCst);
                let final_output = output_for_thread
                    .lock()
                    .map(|o| o.clone())
                    .unwrap_or_default();
                let _ = tx.send(PtyExit {
                    exit_code,
                    output: final_output,
                });
            })
            .map_err(|e| Error::Backend(format!("spawn pty reader thread: {e}")))?;

        Ok((
            Self {
                writer: Mutex::new(writer),
                killer: Mutex::new(killer),
                output,
                pid,
                reaped,
            },
            rx,
        ))
    }

    /// OS pid of the child (0 if the platform did not report one).
    pub fn pid(&self) -> u32 {
        self.pid
    }

    /// Snapshot the merged output captured so far. Used for observability and
    /// tests; the trait has no streaming-read method yet.
    pub fn output_snapshot(&self) -> String {
        self.output.lock().map(|o| o.clone()).unwrap_or_default()
    }

    /// Write `text` verbatim to the PTY (no submit key appended). Synchronous:
    /// callers in async context should wrap this in `spawn_blocking` so a full
    /// PTY input buffer can't stall the runtime.
    pub fn write_input(&self, text: &str) -> Result<()> {
        let mut w = self
            .writer
            .lock()
            .map_err(|_| Error::Backend("pty writer lock poisoned".into()))?;
        w.write_all(text.as_bytes())
            .map_err(|e| Error::Backend(format!("pty write: {e}")))?;
        w.flush()
            .map_err(|e| Error::Backend(format!("pty flush: {e}")))?;
        Ok(())
    }

    /// Signal the child to terminate. Idempotent in practice: killing an
    /// already-dead child surfaces a harmless error the caller may ignore.
    ///
    /// On unix this is portable_pty's graceful kill — `SIGHUP` to the child
    /// pid only — which a TUI can catch and survive (gemini's Ink TUI catches
    /// SIGHUP and SIGTERM). Callers that must guarantee teardown follow up
    /// with [`Self::kill_group`] after a grace period.
    pub fn kill(&self) -> Result<()> {
        let mut k = self
            .killer
            .lock()
            .map_err(|_| Error::Backend("pty killer lock poisoned".into()))?;
        k.kill()
            .map_err(|e| Error::Backend(format!("pty kill: {e}")))
    }

    /// Forcibly terminate the child's entire process group with an
    /// uncatchable `SIGKILL`. Escalation path for children that catch and
    /// survive the graceful [`Self::kill`]. The child is spawned as a session
    /// leader (portable_pty calls `setsid` pre-exec), so its pgid equals its
    /// pid and the group kill also reaps grandchildren the leader would
    /// otherwise orphan. A group that already exited (`ESRCH`) is success,
    /// and a child the reader thread already reaped is a no-op — after the
    /// reap the pid/pgid may be recycled and the SIGKILL could hit an
    /// unrelated process group.
    #[cfg(unix)]
    pub fn kill_group(&self) -> Result<()> {
        if self.reaped.load(Ordering::SeqCst) {
            return Ok(());
        }
        if self.pid == 0 {
            // No pid reported: the group is unaddressable, fall back to the
            // killer handle.
            return self.kill();
        }
        let rc = unsafe { libc::kill(-(self.pid as i32), libc::SIGKILL) };
        if rc == 0 {
            return Ok(());
        }
        let err = std::io::Error::last_os_error();
        if err.raw_os_error() == Some(libc::ESRCH) {
            Ok(())
        } else {
            Err(Error::Backend(format!("pty kill_group: {err}")))
        }
    }

    /// Non-unix fallback: the platform killer is already a hard terminate
    /// (`TerminateProcess` on Windows).
    #[cfg(not(unix))]
    pub fn kill_group(&self) -> Result<()> {
        self.kill()
    }
}

fn append_capped_output(out: &mut String, chunk: &str) {
    out.push_str(chunk);
    let char_count = out.chars().count();
    if char_count <= MAX_CAPTURE_CHARS {
        return;
    }

    let prefix_chars = TRUNCATED_PREFIX.chars().count();
    let keep_chars = MAX_CAPTURE_CHARS.saturating_sub(prefix_chars);
    let tail_start_char = char_count.saturating_sub(keep_chars);
    let tail_start_byte = out
        .char_indices()
        .nth(tail_start_char)
        .map(|(idx, _)| idx)
        .unwrap_or(0);
    let tail = out[tail_start_byte..].to_string();
    out.clear();
    out.push_str(TRUNCATED_PREFIX);
    out.push_str(&tail);
}

impl Drop for PtySession {
    /// Group-SIGKILL so a dropped session never leaks a live child + its
    /// blocked reader thread — including TUIs that catch SIGHUP/SIGTERM
    /// (gemini) and even survive the PTY master closing. This is the backstop
    /// for the `kill_interactive` escalation task, which is cancelled if the
    /// tokio runtime shuts down inside the grace window (e.g. a test that
    /// kills and returns, or daemon stop right after `agent_kill`). No-op
    /// once the reader thread has reaped the child (pid may be recycled).
    fn drop(&mut self) {
        let _ = self.kill_group();
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
    async fn pty_session_multi_turn_round_trips_through_cat() {
        // `cat` stays alive reading stdin and echoes each line back through the
        // PTY: a deterministic stand-in for an interactive agent CLI.
        let (sess, _rx) =
            PtySession::spawn("/bin/cat", &[], "/tmp", &HashMap::new()).expect("spawn cat");

        sess.write_input("alpha-one\r").expect("write turn 1");
        let ok1 = wait_for(2000, 25, || sess.output_snapshot().contains("alpha-one")).await;
        assert!(ok1, "turn 1 should echo through the PTY");

        // Second turn proves the session is still alive (not fire-and-forget).
        sess.write_input("beta-two\r").expect("write turn 2");
        let ok2 = wait_for(2000, 25, || sess.output_snapshot().contains("beta-two")).await;
        assert!(ok2, "turn 2 should echo - multi-turn interactive");

        sess.kill().expect("kill");
    }

    #[tokio::test]
    async fn pty_session_exit_channel_resolves_on_child_exit() {
        // `true` exits immediately; the exit channel must resolve with a code.
        let (sess, rx) = PtySession::spawn(
            "/bin/sh",
            &["-c".into(), "exit 7".into()],
            "/tmp",
            &HashMap::new(),
        )
        .expect("spawn sh");
        let exit = tokio::time::timeout(Duration::from_secs(5), rx)
            .await
            .expect("exit within timeout")
            .expect("exit channel delivered");
        assert_eq!(
            exit.exit_code,
            Some(7),
            "shell `exit 7` should surface code 7"
        );
        // Keep the handle alive until after we read the exit, then drop it.
        drop(sess);
    }

    #[tokio::test]
    async fn spawn_unknown_binary_errors() {
        let err = PtySession::spawn("/no/such/binary-xyzzy", &[], "/tmp", &HashMap::new())
            .err()
            .expect("spawning a missing binary must fail");
        assert!(matches!(err, Error::Backend(_)));
    }

    #[test]
    fn append_capped_output_keeps_tail_with_truncation_marker() {
        let mut out = "a".repeat(MAX_CAPTURE_CHARS - 4);
        append_capped_output(&mut out, "bbbbcccc");

        assert!(out.starts_with(TRUNCATED_PREFIX));
        assert!(out.ends_with("bbbbcccc"));
        assert!(out.chars().count() <= MAX_CAPTURE_CHARS);
    }
}
