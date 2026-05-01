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
use std::sync::Arc;

pub mod kitty;
pub mod osc;
pub mod warp;
pub mod wezterm;
pub mod zellij;

pub use kitty::KittyBackend;
pub use osc::{OscEvent, OscParser};
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

    async fn split(&self, pane: &PaneId, dir: SplitDir) -> Result<PaneId>;

    /// Stream lifecycle + OSC events. Backends without push semantics may
    /// return an empty/never-emitting stream.
    async fn subscribe(&self) -> Result<BoxStream<'static, TermEvent>>;
}

/// Pick a [`TerminalBackend`] from the environment.
///
/// Resolution order:
/// 1. Explicit override: `AGENT_BRIDGE_TERMINAL` ∈ {`kitty`, `zellij`, `wezterm`, `warp`}.
/// 2. Auto-detect:
///    - `ZELLIJ` set → zellij
///    - `KITTY_WINDOW_ID` set → kitty
///    - [`WarpBackend::detect`] (i.e. `TERM_PROGRAM=WarpTerminal` or any
///      `WARP_*` shell-session marker) → warp
/// 3. Fallback: wezterm (preserves pre-multi-backend behaviour).
///
/// Unknown override values silently fall through to the auto-detect step
/// rather than panicking — prefer logging a warning at the call site.
pub fn auto_backend() -> Arc<dyn TerminalBackend> {
    let explicit = std::env::var("AGENT_BRIDGE_TERMINAL")
        .ok()
        .map(|s| s.trim().to_lowercase());

    let chosen = match explicit.as_deref() {
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
                "wezterm"
            }
        }
    };

    match chosen {
        "kitty" => Arc::new(KittyBackend::new()),
        "zellij" => Arc::new(ZellijBackend::new()),
        "warp" => Arc::new(WarpBackend::new()),
        _ => Arc::new(WezTermBackend::new()),
    }
}
