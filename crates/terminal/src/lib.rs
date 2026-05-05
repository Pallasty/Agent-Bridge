//! Terminal multiplexer abstraction + OSC parsing.
//!
//! - [`TerminalBackend`] trait — generic mux operations plus sync [`TerminalCapabilities`].
//! - [`WezTermBackend`] — wraps `wezterm cli`.
//! - [`KittyBackend`]  — wraps `kitten @` (kitty remote control).
//! - [`ZellijBackend`] — wraps `zellij action` (session-granularity only).
//! - [`WarpBackend`]   — wraps Warp's `warp://` URL scheme (limited IPC).
//! - [`auto_backend`]  — pick a backend from `AGENT_BRIDGE_TERMINAL` or env detection.
//! - [`osc`] — pure-Rust streaming parser for OSC 9 / 99 / 777 notification
//!   sequences, used by both the bridge daemon and integration glue.

use ab_core::{PaneId, Result};
use async_trait::async_trait;
use futures::stream::BoxStream;
use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::sync::Arc;

pub mod kitty;
pub mod osc;
pub mod pty;
pub mod warp;
pub mod wezterm;
pub mod zellij;

pub use kitty::KittyBackend;
pub use osc::{OscEvent, OscParser};
pub use pty::PtyBackend;
pub use warp::{
    dispatch_warp_scheme_uri, warp_scheme_launch_configuration, warp_scheme_new_tab,
    warp_scheme_new_window, warp_scheme_open_settings_page, WarpBackend,
};
pub use wezterm::WezTermBackend;
pub use zellij::ZellijBackend;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Pane {
    pub id: PaneId,
    pub title: String,
    pub cwd: Option<String>,
    pub command: Option<String>,
}

#[derive(Debug, Clone, Copy, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum SplitDir {
    Horizontal,
    Vertical,
}

/// Optional spawn-time controls for new panes. Honored by backends that
/// own the underlying process lifecycle (PtyBackend); backends that
/// delegate to an external mux (wezterm/kitty/zellij/warp URL-scheme)
/// silently ignore the options because the mux owns the spawn.
#[derive(Debug, Clone, Default, Serialize, Deserialize)]
pub struct SpawnOptions {
    /// Working directory for the new shell. Defaults to the daemon's
    /// current directory when omitted.
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub cwd: Option<String>,
    /// Extra environment variables to inject. Merged on top of the
    /// daemon's env; the backend's own essentials (e.g. `TERM`) win
    /// over conflicts to avoid breaking the PTY contract.
    #[serde(default, skip_serializing_if = "HashMap::is_empty")]
    pub env: HashMap<String, String>,
}

/// Static capability flags for a [`TerminalBackend`] (sync; used by MCP `capabilities` and clients).
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct TerminalCapabilities {
    pub backend_id: String,
    pub can_read_output: bool,
    pub can_send_keys: bool,
    pub can_split: bool,
    /// Warp-only: whether the in-process bridge Unix socket path exists and is a socket.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub warp_ipc_socket_ready: Option<bool>,
}

/// A single structured Warp terminal block (command + output + metadata).
///
/// Available only when the Warp IPC bridge is connected; other backends
/// return `Error::Backend("not supported")` from `read_blocks`.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TerminalBlock {
    pub block_id: String,
    /// The command text (empty for background / static blocks).
    pub command: String,
    /// The rendered output of the block.
    pub output: String,
    /// Exit code; 0 if not yet finished.
    pub exit_code: i32,
    /// One of: BeforeExecution | Executing | DoneWithExecution | DoneWithNoExecution | Background | Static.
    pub state: String,
    pub is_running: bool,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum TermEvent {
    PaneOpened(PaneId),
    PaneClosed(PaneId),
    OscNotification { pane: PaneId, body: String },
}

#[async_trait]
pub trait TerminalBackend: Send + Sync {
    fn id(&self) -> &str;

    /// Sync introspection for tooling (filesystem probe only where needed, e.g. Warp IPC).
    fn capabilities(&self) -> TerminalCapabilities;

    async fn list_panes(&self) -> Result<Vec<Pane>>;

    async fn send_keys(&self, pane: &PaneId, keys: &str) -> Result<()>;

    /// Read recent output lines from a pane/session.
    ///
    /// Backends that cannot expose scrollback should return an
    /// `Error::Backend` explaining the limitation.
    async fn read_output(&self, pane: &PaneId, lines: usize) -> Result<Vec<String>>;

    /// Return structured blocks for a session (Warp IPC only).
    ///
    /// `limit` caps the number of most-recent blocks returned.
    /// `since_block` is an optional 0-based index floor (skip older blocks).
    /// Default impl returns `Error::Backend("not supported")`.
    async fn read_blocks(
        &self,
        _pane: &PaneId,
        _limit: usize,
        _since_block: Option<usize>,
    ) -> Result<Vec<TerminalBlock>> {
        Err(ab_core::Error::Backend(
            "read_blocks is only available via the Warp IPC bridge".into(),
        ))
    }

    async fn split(&self, pane: &PaneId, dir: SplitDir) -> Result<PaneId>;

    /// Split with caller-provided spawn options (cwd, extra env vars).
    ///
    /// Default impl ignores `_options` and falls through to [`split`] —
    /// backends that don't own the spawn (wezterm/kitty/zellij CLI,
    /// Warp URL-scheme) can't honor cwd/env and would silently drop
    /// them anyway. PtyBackend overrides this to actually use the
    /// options when launching the child shell.
    async fn split_with_options(
        &self,
        pane: &PaneId,
        dir: SplitDir,
        _options: SpawnOptions,
    ) -> Result<PaneId> {
        self.split(pane, dir).await
    }

    /// Resize a pane / PTY to `rows` × `cols`. Updates both the kernel-side
    /// `TIOCSWINSZ` (so the child receives `SIGWINCH` and full-screen apps
    /// like vim/less re-flow) and the backend's render state where it has
    /// one. Default impl returns `Error::Backend("not supported")` —
    /// backends that don't own the PTY (e.g. WarpBackend in URL-scheme
    /// mode) fall through to this.
    async fn resize(&self, _pane: &PaneId, _rows: u16, _cols: u16) -> Result<()> {
        Err(ab_core::Error::Backend(
            "resize is not supported by this backend".into(),
        ))
    }

    /// Stream lifecycle + OSC events. Backends without push semantics may
    /// return an empty/never-emitting stream.
    async fn subscribe(&self) -> Result<BoxStream<'static, TermEvent>>;
}

/// Pick a [`TerminalBackend`] from the environment.
///
/// Resolution order:
/// 1. Explicit override: `AGENT_BRIDGE_TERMINAL` ∈ {`pty`, `kitty`, `zellij`, `wezterm`, `warp`}.
/// 2. Auto-detect:
///    - `ZELLIJ` set → zellij
///    - `KITTY_WINDOW_ID` set → kitty
///    - [`WarpBackend::detect`] (i.e. `TERM_PROGRAM=WarpTerminal` or any
///      `WARP_*` shell-session marker) → warp
/// 3. Fallback: `pty` — the in-daemon backend, which always works because
///    it owns the shell itself and needs nothing on the host but a Rust
///    runtime. (Previously wezterm; that needed `wezterm` on PATH and
///    failed loudly on bare hosts.)
///
/// Unknown override values silently fall through to the auto-detect step
/// rather than panicking — prefer logging a warning at the call site.
pub fn auto_backend() -> Arc<dyn TerminalBackend> {
    let explicit = std::env::var("AGENT_BRIDGE_TERMINAL")
        .ok()
        .map(|s| s.trim().to_lowercase());

    let chosen = match explicit.as_deref() {
        Some("pty") => "pty",
        Some("kitty") => "kitty",
        Some("zellij") => "zellij",
        Some("wezterm") => "wezterm",
        Some("warp") => "warp",
        _ => {
            if std::env::var_os("ZELLIJ").is_some() {
                "zellij"
            } else if std::env::var_os("KITTY_WINDOW_ID").is_some() {
                "kitty"
            } else if WarpBackend::detect() {
                "warp"
            } else {
                "pty"
            }
        }
    };

    match chosen {
        "kitty" => Arc::new(KittyBackend::new()),
        "zellij" => Arc::new(ZellijBackend::new()),
        "warp" => Arc::new(WarpBackend::new()),
        "wezterm" => Arc::new(WezTermBackend::new()),
        _ => Arc::new(PtyBackend::new()),
    }
}
