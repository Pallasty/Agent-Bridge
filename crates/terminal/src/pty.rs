//! In-daemon PTY-backed [`TerminalBackend`].
//!
//! Unlike the other backends, `PtyBackend` does **not** delegate to an
//! external terminal multiplexer. The daemon spawns shells itself, owns
//! their PTY masters, and serves all of `list_panes` / `send_keys` /
//! `read_output` / `split` / `subscribe` from in-process state.
//!
//! Why: the previous backends require a host terminal (wezterm/kitty/zellij)
//! that exposes a CLI mux protocol, or — for Warp — an in-app IPC server we
//! have to compile ourselves. `PtyBackend` removes that whole class of
//! coupling: anywhere a Rust binary can run, the agent can read & write a
//! shell session, full stop.
//!
//! Output handling: bytes coming back from the PTY master fan out three ways.
//! 1. A copy is fed to [`crate::OscParser`] so OSC 9 / 99 / 777 notifications
//!    still surface as `TermEvent::OscNotification`s.
//! 2. A copy is fed to a per-pane [`vt100::Parser`], which maintains a real
//!    rows×cols screen grid (default 40×120). `read_output` prefers the
//!    rendered screen for short queries, so `vim`/`top`/progress bars come
//!    out the way a human would see them — not as ANSI-stripped fragments.
//! 3. The same chunk, post-`strip-ansi-escapes`, is appended to a per-pane
//!    [`RingBuffer`]. The ring acts as a long-N fallback: when the caller
//!    asks for more lines than fit on the visible screen, we serve from the
//!    ring (lower fidelity, but more history).
//!
//! The dual-state design lets us pay the high-quality rendering cost only
//! when it matters (short windows, interactive TUIs) while keeping the
//! cheap "last 200 lines of `cat` output" path working out of the box.

use ab_core::{Error, NotifyEvent, NotifySource, PaneId, Result};
use async_trait::async_trait;
use futures::stream::BoxStream;
use portable_pty::{native_pty_system, CommandBuilder, PtySize};
use std::collections::{HashMap, VecDeque};
use std::io::{Read, Write};
use std::path::PathBuf;
use std::sync::{Arc, Mutex, RwLock};
use tokio::sync::broadcast;

use crate::{OscEvent, OscParser, Pane, SplitDir, TermEvent, TerminalBackend, TerminalCapabilities};

/// Default rows/cols for spawned PTYs. Matches what most modern terminals
/// open with; agents that care about wrapping can resize via send_keys
/// (`\x1b[8;<rows>;<cols>t`) for now — explicit resize RPC is future work.
const DEFAULT_ROWS: u16 = 40;
const DEFAULT_COLS: u16 = 120;

/// Default per-pane scrollback capacity (bytes, post-ANSI-strip).
/// 64 KB ≈ a few hundred lines of ordinary shell output.
const DEFAULT_RING_CAP: usize = 64 * 1024;

/// Broadcast channel size for [`TerminalBackend::subscribe`]. If the agent
/// is slow to drain, older events are dropped — that's fine for OSC
/// notifications (best-effort by nature).
const EVENT_CHANNEL_CAP: usize = 64;

/// Minimum delay between ring-buffer polls in tests / docs. Not used at
/// runtime (the reader thread blocks on the PTY master directly).
#[allow(dead_code)]
const READER_POLL_HINT_MS: u64 = 5;

#[derive(Clone)]
pub struct PtyBackend {
    inner: Arc<Inner>,
}

struct Inner {
    panes: RwLock<HashMap<PaneId, Arc<PtyHandle>>>,
    events_tx: broadcast::Sender<TermEvent>,
    shell: String,
    ring_cap: usize,
}

struct PtyHandle {
    id: PaneId,
    /// Writer to the PTY master (typing into the shell).
    writer: Mutex<Box<dyn Write + Send>>,
    /// Async-friendly child kill handle (so we can kill from any thread).
    killer: Mutex<Box<dyn portable_pty::ChildKiller + Send + Sync>>,
    /// Virtual terminal grid for high-fidelity rendering of the visible
    /// screen (vim/top/progress-bar handling). Read by `read_output`
    /// when the caller's `lines` request fits within rows.
    parser: Arc<Mutex<vt100::Parser>>,
    /// Per-pane scrollback (post-ANSI-strip). Used as a long-N fallback
    /// when the caller asks for more rows than the screen has.
    ring: Arc<Mutex<RingBuffer>>,
    /// Initial cwd snapshot (set at spawn time; not tracked thereafter).
    cwd: Option<String>,
    /// Command line we asked the PTY to run (`$SHELL` for a default pane).
    command: String,
}

impl PtyBackend {
    /// Create a backend that spawns `$SHELL` (falling back to `/bin/zsh`,
    /// then `/bin/sh`) for new panes.
    pub fn new() -> Self {
        Self::with_shell(detect_shell())
    }

    /// Create a backend that spawns a specific shell binary.
    pub fn with_shell(shell: impl Into<String>) -> Self {
        let (tx, _) = broadcast::channel(EVENT_CHANNEL_CAP);
        Self {
            inner: Arc::new(Inner {
                panes: RwLock::new(HashMap::new()),
                events_tx: tx,
                shell: shell.into(),
                ring_cap: DEFAULT_RING_CAP,
            }),
        }
    }

    /// Override the per-pane scrollback ring capacity in bytes.
    /// Mostly useful for tests; production callers can leave it at default.
    pub fn with_ring_capacity(mut self, cap: usize) -> Self {
        Arc::get_mut(&mut self.inner)
            .expect("with_ring_capacity called on a shared PtyBackend")
            .ring_cap = cap.max(1024);
        self
    }

    /// Number of currently-tracked panes (for diagnostics / tests).
    pub fn pane_count(&self) -> usize {
        self.inner.panes.read().expect("panes lock poisoned").len()
    }

    /// Spawn a fresh PTY pane running the configured shell. Returns the
    /// new [`PaneId`]. Used by [`split`](TerminalBackend::split) and
    /// internally by `list_panes` when the map is empty.
    fn spawn_pane(&self, cwd: Option<PathBuf>) -> Result<PaneId> {
        let pty_system = native_pty_system();
        let pair = pty_system
            .openpty(PtySize {
                rows: DEFAULT_ROWS,
                cols: DEFAULT_COLS,
                pixel_width: 0,
                pixel_height: 0,
            })
            .map_err(|e| Error::Backend(format!("openpty: {e}")))?;

        let mut cmd = CommandBuilder::new(&self.inner.shell);
        if let Some(ref dir) = cwd {
            cmd.cwd(dir);
        }
        // Parity with the env that interactive terminals set so prompts /
        // pagers behave the same as in a "real" terminal.
        cmd.env("TERM", "xterm-256color");

        let child = pair
            .slave
            .spawn_command(cmd)
            .map_err(|e| Error::Backend(format!("spawn shell: {e}")))?;
        let killer = child.clone_killer();

        let writer = pair
            .master
            .take_writer()
            .map_err(|e| Error::Backend(format!("take_writer: {e}")))?;
        let reader = pair
            .master
            .try_clone_reader()
            .map_err(|e| Error::Backend(format!("clone_reader: {e}")))?;

        // Important: drop the slave fd in the parent so the read side sees
        // EOF when the child exits. Holding it open here would leak the
        // PTY and stall reader cleanup.
        drop(pair.slave);

        let id = PaneId::new();
        let ring = Arc::new(Mutex::new(RingBuffer::new(self.inner.ring_cap)));
        // vt100 scrollback set to 0: we already keep history in the ring,
        // so the parser only needs to cover the visible screen. Fewer
        // rows allocated = less memory per pane.
        let parser = Arc::new(Mutex::new(vt100::Parser::new(
            DEFAULT_ROWS, DEFAULT_COLS, 0,
        )));
        let handle = Arc::new(PtyHandle {
            id: id.clone(),
            writer: Mutex::new(writer),
            killer: Mutex::new(killer),
            parser: parser.clone(),
            ring: ring.clone(),
            cwd: cwd.as_ref().map(|p| p.display().to_string()),
            command: self.inner.shell.clone(),
        });

        // Start the background reader. PTY reads are blocking std::io, so
        // run on a dedicated OS thread (not a tokio task) — fan the bytes
        // out three ways: OSC parser (notifications), vt100 parser (live
        // screen render), and the ring (long-N fallback / history).
        let inner_for_thread: Arc<Inner> = self.inner.clone();
        let pane_for_thread = id.clone();
        let ring_for_thread = ring;
        let parser_for_thread = parser;
        std::thread::Builder::new()
            .name(format!("ab-pty-reader-{}", id.as_str()))
            .spawn(move || {
                reader_loop(
                    reader,
                    ring_for_thread,
                    parser_for_thread,
                    inner_for_thread.events_tx.clone(),
                    &pane_for_thread,
                );
                // PTY hit EOF → child has exited (or close to it). Drop
                // the handle so subsequent list_panes stops listing it,
                // and emit a PaneClosed event.
                let _ = inner_for_thread
                    .events_tx
                    .send(TermEvent::PaneClosed(pane_for_thread.clone()));
                let mut map = match inner_for_thread.panes.write() {
                    Ok(g) => g,
                    Err(poisoned) => poisoned.into_inner(),
                };
                map.remove(&pane_for_thread);
            })
            .map_err(|e| Error::Backend(format!("spawn reader thread: {e}")))?;

        self.inner
            .panes
            .write()
            .expect("panes lock poisoned")
            .insert(id.clone(), handle);

        let _ = self.inner.events_tx.send(TermEvent::PaneOpened(id.clone()));
        Ok(id)
    }

    fn get_handle(&self, pane: &PaneId) -> Result<Arc<PtyHandle>> {
        self.inner
            .panes
            .read()
            .expect("panes lock poisoned")
            .get(pane)
            .cloned()
            .ok_or_else(|| Error::Backend(format!("unknown pane: {pane}")))
    }
}

impl Default for PtyBackend {
    fn default() -> Self {
        Self::new()
    }
}

impl Drop for Inner {
    fn drop(&mut self) {
        let map = match self.panes.write() {
            Ok(g) => g,
            Err(poisoned) => poisoned.into_inner(),
        };
        for (_, h) in map.iter() {
            if let Ok(mut k) = h.killer.lock() {
                let _ = k.kill();
            }
        }
    }
}

#[async_trait]
impl TerminalBackend for PtyBackend {
    fn id(&self) -> &str {
        "pty"
    }

    fn capabilities(&self) -> TerminalCapabilities {
        TerminalCapabilities {
            backend_id: self.id().to_string(),
            can_read_output: true,
            can_send_keys: true,
            can_split: true,
            warp_ipc_socket_ready: None,
        }
    }

    async fn list_panes(&self) -> Result<Vec<Pane>> {
        // Lazy spawn: if no panes exist yet, create one in the daemon's
        // current working directory. Keeps "first call returns something"
        // consistent with how WezTermBackend behaves when there's a window
        // open.
        if self.inner.panes.read().expect("panes lock poisoned").is_empty() {
            let cwd = std::env::current_dir().ok();
            self.spawn_pane(cwd)?;
        }
        let map = self.inner.panes.read().expect("panes lock poisoned");
        Ok(map
            .values()
            .map(|h| Pane {
                id: h.id.clone(),
                title: format!("pty {}", h.command),
                cwd: h.cwd.clone(),
                command: Some(h.command.clone()),
            })
            .collect())
    }

    async fn send_keys(&self, pane: &PaneId, keys: &str) -> Result<()> {
        let handle = self.get_handle(pane)?;
        // Writer is sync; do the write on a blocking thread so we don't
        // block the tokio runtime if the PTY's input buffer is full.
        let bytes = keys.as_bytes().to_vec();
        let handle_for_blocking = handle.clone();
        tokio::task::spawn_blocking(move || -> std::io::Result<()> {
            let mut w = handle_for_blocking
                .writer
                .lock()
                .expect("pty writer lock poisoned");
            w.write_all(&bytes)?;
            w.flush()
        })
        .await
        .map_err(|e| Error::Backend(format!("send_keys join: {e}")))?
        .map_err(|e| Error::Backend(format!("send_keys write: {e}")))?;
        Ok(())
    }

    async fn read_output(&self, pane: &PaneId, lines: usize) -> Result<Vec<String>> {
        let handle = self.get_handle(pane)?;
        let parser = handle.parser.clone();
        let ring = handle.ring.clone();
        // Snapshot both states under their own short locks. Splitting them
        // (rather than holding both) avoids a potential deadlock with the
        // reader thread, which acquires parser then ring in that order.
        let (visible, ring_bytes) = tokio::task::spawn_blocking(move || {
            let visible = {
                let p = parser.lock().expect("parser lock poisoned");
                p.screen().contents()
            };
            let bytes = {
                let g = ring.lock().expect("ring lock poisoned");
                g.snapshot()
            };
            (visible, bytes)
        })
        .await
        .map_err(|e| Error::Backend(format!("read_output join: {e}")))?;

        let n = lines.max(1);
        let grid_rows = DEFAULT_ROWS as usize;
        let visible_lines: Vec<String> = visible.lines().map(str::to_owned).collect();

        // Fast path: as long as the request fits inside the grid, the
        // rendered visible screen is the truth — vim / top / clear /
        // progress bars look right. Note `visible_lines.len()` may be
        // smaller than `grid_rows` because vt100::Screen::contents()
        // trims trailing blank rows; that's still the correct answer
        // (those rows are empty), so we serve fewer lines rather than
        // falling back to the ring (which keeps OLD content vt100 has
        // already cleared with \e[2J).
        if n <= grid_rows {
            let start = visible_lines.len().saturating_sub(n);
            return Ok(visible_lines[start..].to_vec());
        }

        // Long-N fallback: caller wants more than the grid can hold.
        // Serve from the ring (post-ANSI-strip; older history at the
        // cost of fidelity).
        let ring_text = String::from_utf8_lossy(&ring_bytes);
        let ring_lines: Vec<String> = ring_text.lines().map(str::to_owned).collect();
        let start = ring_lines.len().saturating_sub(n);
        Ok(ring_lines[start..].to_vec())
    }

    async fn split(&self, _pane: &PaneId, _dir: SplitDir) -> Result<PaneId> {
        // SplitDir doesn't have meaning in a headless PTY backend (no UI
        // layout to bisect). We honour the call by spawning a sibling
        // pane in the parent's cwd, which matches what most users expect
        // when they ask for a split.
        let cwd = std::env::current_dir().ok();
        self.spawn_pane(cwd)
    }

    async fn subscribe(&self) -> Result<BoxStream<'static, TermEvent>> {
        let mut rx = self.inner.events_tx.subscribe();
        let s = async_stream::stream! {
            loop {
                match rx.recv().await {
                    Ok(ev) => yield ev,
                    // Lagged means we dropped events; keep going.
                    Err(broadcast::error::RecvError::Lagged(_)) => continue,
                    // Closed means the backend was dropped → stream end.
                    Err(broadcast::error::RecvError::Closed) => break,
                }
            }
        };
        Ok(Box::pin(s))
    }
}

// ─── ring buffer ───────────────────────────────────────────────────────

/// Byte-oriented ring buffer. Append-only from the reader side; readers
/// snapshot the whole contents under a single mutex hold.
struct RingBuffer {
    buf: VecDeque<u8>,
    cap: usize,
}

impl RingBuffer {
    fn new(cap: usize) -> Self {
        Self {
            buf: VecDeque::with_capacity(cap.min(4096)),
            cap,
        }
    }
    fn append(&mut self, bytes: &[u8]) {
        // Fast path: bytes shorter than remaining capacity → push tail.
        if self.buf.len() + bytes.len() <= self.cap {
            self.buf.extend(bytes.iter().copied());
            return;
        }
        // Slow path: drop from the front to make room. If a single chunk
        // is larger than the whole capacity, only keep the tail.
        if bytes.len() >= self.cap {
            self.buf.clear();
            self.buf.extend(&bytes[bytes.len() - self.cap..]);
            return;
        }
        let need = self.buf.len() + bytes.len() - self.cap;
        for _ in 0..need {
            self.buf.pop_front();
        }
        self.buf.extend(bytes.iter().copied());
    }
    fn snapshot(&self) -> Vec<u8> {
        let (a, b) = self.buf.as_slices();
        let mut out = Vec::with_capacity(a.len() + b.len());
        out.extend_from_slice(a);
        out.extend_from_slice(b);
        out
    }
}

// ─── reader loop ───────────────────────────────────────────────────────

fn reader_loop(
    mut reader: Box<dyn Read + Send>,
    ring: Arc<Mutex<RingBuffer>>,
    parser: Arc<Mutex<vt100::Parser>>,
    events_tx: broadcast::Sender<TermEvent>,
    pane: &PaneId,
) {
    let mut buf = [0u8; 4096];
    let mut osc = OscParser::new();
    loop {
        match reader.read(&mut buf) {
            Ok(0) => break, // EOF
            Ok(n) => {
                let chunk = &buf[..n];
                // 1) OSC parse on the raw stream — escape sequences must
                //    survive intact for this to work.
                for ev in osc.feed(chunk) {
                    if let OscEvent::Notify(NotifyEvent {
                        title, body, severity, source, ..
                    }) = ev
                    {
                        let labelled = match source {
                            NotifySource::Mcp | NotifySource::Manual => body,
                            _ => format!("[{:?}/{:?}] {}", severity, source, body)
                                .replace("[Info/Osc] ", ""),
                        };
                        let final_body = if title.is_empty() {
                            labelled
                        } else {
                            format!("{title}: {labelled}")
                        };
                        let _ = events_tx.send(TermEvent::OscNotification {
                            pane: pane.clone(),
                            body: final_body,
                        });
                    }
                }
                // 2) Feed the vt100 parser so read_output's fast path
                //    can serve high-fidelity rendered screens. Cheap —
                //    process() is a state machine over the bytes.
                if let Ok(mut p) = parser.lock() {
                    p.process(chunk);
                }
                // 3) ANSI-strip into the ring as the long-N fallback.
                //    strip-ansi-escapes 0.2 returns Vec<u8> directly
                //    (no Result), preserving CR/LF/etc.
                let stripped = strip_ansi_escapes::strip(chunk);
                if let Ok(mut g) = ring.lock() {
                    g.append(&stripped);
                }
            }
            Err(e) if e.kind() == std::io::ErrorKind::Interrupted => continue,
            Err(_) => break, // PTY closed / bad fd / etc.
        }
    }
}

// ─── shell detection ───────────────────────────────────────────────────

fn detect_shell() -> String {
    if let Ok(s) = std::env::var("SHELL") {
        if !s.is_empty() {
            return s;
        }
    }
    // macOS default since 10.15; on Linux distros zsh is rarely missing
    // these days but fall back to sh as the universal floor.
    if std::path::Path::new("/bin/zsh").exists() {
        return "/bin/zsh".to_string();
    }
    "/bin/sh".to_string()
}

// ─── tests ─────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;
    use futures::StreamExt;
    use std::time::Duration;

    /// Wait up to `total_ms` for `predicate` to become true, polling every
    /// `step_ms`. Used because PTY I/O is concurrent — we can't simply
    /// `read_output` immediately after `send_keys`.
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

    #[test]
    fn id_is_stable() {
        assert_eq!(PtyBackend::new().id(), "pty");
    }

    #[test]
    fn capabilities_advertise_full_io() {
        let caps = PtyBackend::new().capabilities();
        assert_eq!(caps.backend_id, "pty");
        assert!(caps.can_read_output);
        assert!(caps.can_send_keys);
        assert!(caps.can_split);
    }

    #[test]
    fn ring_buffer_truncates_to_cap() {
        let mut r = RingBuffer::new(8);
        r.append(b"abcdef");
        assert_eq!(r.snapshot(), b"abcdef");
        r.append(b"ghij");
        // After: should hold the last 8 bytes "cdefghij"
        assert_eq!(r.snapshot(), b"cdefghij");
    }

    #[test]
    fn ring_buffer_handles_oversize_chunk() {
        let mut r = RingBuffer::new(4);
        r.append(b"abcdefghij");
        // Only the tail of cap bytes should survive.
        assert_eq!(r.snapshot(), b"ghij");
    }

    #[tokio::test]
    async fn list_panes_lazy_spawns_default() {
        let backend = PtyBackend::with_shell("/bin/sh");
        assert_eq!(backend.pane_count(), 0);
        let panes = backend.list_panes().await.expect("list_panes");
        assert_eq!(panes.len(), 1);
        assert_eq!(backend.pane_count(), 1);
    }

    #[tokio::test]
    async fn send_keys_round_trips_through_cat() {
        let backend = PtyBackend::with_shell("/bin/cat");
        let panes = backend.list_panes().await.expect("list_panes");
        let pane = panes[0].id.clone();
        backend
            .send_keys(&pane, "hello-pty\n")
            .await
            .expect("send_keys");
        let ok = wait_for(2000, 25, || {
            // tokio::block_in_place would be ideal, but we're already in
            // a multi-threaded runtime; this synchronous read is fine
            // because read_output's blocking work is tiny.
            let lines = futures::executor::block_on(backend.read_output(&pane, 20))
                .unwrap_or_default();
            lines.iter().any(|l| l.contains("hello-pty"))
        })
        .await;
        assert!(ok, "expected 'hello-pty' to round-trip through cat");
    }

    #[tokio::test]
    async fn pty_progress_bar_via_perl_round_trip() {
        // Real end-to-end: spawn a shell, send a perl one-liner that
        // emits raw CR-separated tokens, verify the rendered visible
        // screen shows only the final token (CR overwrote the others).
        // This is the "vim/top/progress bar" headline win for the
        // vt100 upgrade.
        let backend = PtyBackend::with_shell("/bin/sh");
        let _ = backend.list_panes().await.expect("seed");
        let pane = backend.list_panes().await.expect("list")[0].id.clone();
        backend
            .send_keys(
                &pane,
                "perl -e 'print \"BAR_A\\x0dBAR_B\\x0dBAR_DONE\\n\"'\n",
            )
            .await
            .expect("send_keys");
        let ok = wait_for(3000, 50, || {
            let lines = futures::executor::block_on(backend.read_output(&pane, 20))
                .unwrap_or_default();
            // Must contain the final token AND must not contain the
            // earlier ones as standalone lines.
            let has_done = lines.iter().any(|l| l.contains("BAR_DONE"));
            let leaked = lines.iter().any(|l| l == "BAR_A" || l == "BAR_B");
            has_done && !leaked
        })
        .await;
        assert!(
            ok,
            "expected only BAR_DONE on rendered screen; got leaked tokens"
        );
    }

    #[tokio::test]
    async fn split_creates_sibling_pane() {
        let backend = PtyBackend::with_shell("/bin/sh");
        let _ = backend.list_panes().await.expect("seed");
        let new_id = backend
            .split(&PaneId::from_raw("ignored"), SplitDir::Vertical)
            .await
            .expect("split");
        assert_eq!(backend.pane_count(), 2);
        let panes = backend.list_panes().await.expect("list");
        assert!(panes.iter().any(|p| p.id == new_id));
    }

    #[tokio::test]
    async fn subscribe_receives_pane_opened() {
        let backend = PtyBackend::with_shell("/bin/sh");
        let mut events = backend.subscribe().await.expect("subscribe");
        let _ = backend.list_panes().await.expect("seed");
        // First event after subscribe should be PaneOpened. Use a small
        // timeout so the test fails loudly rather than hanging.
        let ev = tokio::time::timeout(Duration::from_secs(2), events.next())
            .await
            .expect("timeout waiting for event")
            .expect("stream ended");
        match ev {
            TermEvent::PaneOpened(_) => {}
            other => panic!("expected PaneOpened, got {other:?}"),
        }
    }

    #[test]
    fn vt100_clear_screen_drops_old_content() {
        // Real clear-screen sequence: ESC[2J = erase whole display,
        // ESC[H = move cursor to home. After this, the visible grid
        // should be entirely blank.
        let mut p = vt100::Parser::new(DEFAULT_ROWS, DEFAULT_COLS, 0);
        p.process(b"hello before clear\nsome more text\n");
        p.process(b"\x1b[2J\x1b[H");
        let contents = p.screen().contents();
        let non_blank: Vec<&str> = contents.lines().filter(|l| !l.is_empty()).collect();
        assert!(
            non_blank.is_empty(),
            "expected blank screen after \\e[2J\\e[H, got {:?}",
            non_blank
        );
    }

    #[test]
    fn vt100_clear_with_intermediate_prompt_drops_old_lines() {
        // Mimic the real integration byte stream: prompt → cmd echo →
        // output → clear → new echo → new prompt. If vt100 handles
        // \e[2J\e[H correctly under this exact pattern, the OLD line
        // must not appear in screen contents after the clear.
        let mut p = vt100::Parser::new(DEFAULT_ROWS, DEFAULT_COLS, 0);
        p.process(b"$ echo OLD; printf '\\e[2J\\e[H'; echo NEW\r\n");
        p.process(b"OLD\r\n");
        p.process(b"\x1b[2J\x1b[H");
        p.process(b"NEW\r\n");
        p.process(b"$ ");
        let contents = p.screen().contents();
        assert!(
            contents.contains("NEW"),
            "expected NEW after clear, got {contents:?}"
        );
        assert!(
            !contents.contains("OLD"),
            "expected OLD to be erased by \\e[2J, but it survived: {contents:?}"
        );
    }

    #[test]
    fn vt100_progress_bar_overwrite_via_carriage_return() {
        // Carriage return without newline → cursor returns to column 0
        // without scrolling. Each successive write overwrites the previous
        // value, so only the *last* version is visible. This is exactly
        // what a `printf 'X%%\r'` style progress bar relies on, and the
        // case strip-ansi-escapes gets wrong (it would dump every step).
        let mut p = vt100::Parser::new(DEFAULT_ROWS, DEFAULT_COLS, 0);
        p.process(b"10%\r20%\r30%\rfinal\n");
        let contents = p.screen().contents();
        assert!(
            contents.contains("final"),
            "expected 'final' on rendered screen, got {contents:?}"
        );
        for stale in &["10%", "20%", "30%"] {
            assert!(
                !contents.contains(stale),
                "expected '{stale}' to be overwritten, but it survived in {contents:?}"
            );
        }
    }

    #[tokio::test]
    async fn read_output_unknown_pane_errors() {
        let backend = PtyBackend::with_shell("/bin/sh");
        let err = backend
            .read_output(&PaneId::from_raw("does-not-exist"), 10)
            .await
            .expect_err("must error");
        match err {
            Error::Backend(msg) => assert!(msg.contains("unknown pane")),
            other => panic!("expected Error::Backend, got {other:?}"),
        }
    }
}
