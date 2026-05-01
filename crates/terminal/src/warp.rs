//! Warp Terminal-backed [`TerminalBackend`].
//!
//! Warp (<https://www.warp.dev>) is a modern terminal that — unlike WezTerm,
//! kitty, or Zellij — does **not** ship a public CLI for arbitrary
//! mux control. Behaviour here is informed by Warp's own source
//! (see `app/src/terminal/local_tty/unix.rs` and `app/src/uri/mod.rs`
//! in <https://github.com/warpdotdev/warp>):
//!
//! - **Environment** — Warp's `build_host_shell_command` sets these on
//!   every spawned shell (Unix; the Windows path mirrors them):
//!   * `TERM_PROGRAM=WarpTerminal`
//!   * `WARP_IS_LOCAL_SHELL_SESSION=1`
//!   * `WARP_HONOR_PS1=0|1`         (note: literal `"0"` when PS1 is
//!     ignored — presence alone does not mean Warp)
//!   * `WARP_CLIENT_VERSION=<version>|local`
//!   * `WARP_USE_SSH_WRAPPER=0|1`
//!
//!   Warp's bash/zsh/fish bootstrap then sets a non-exported shell-local
//!   `WARP_SESSION_ID` (`bash_init_shell.sh:6`, `zsh_init_shell.sh:6`).
//!   Children inherit it only if the user manually exports it, so most
//!   of the time we won't see it from the bridge daemon.
//!
//! - **URL scheme** — the only public IPC, parsed in `app/src/uri/mod.rs`:
//!   * `warp://action/new_tab[?path=<dir>]`     opens a new tab
//!   * `warp://action/new_window[?path=<dir>]`  opens a new window
//!   * `warp://launch/<config>`                  opens a saved launch config
//!   * `warp://action/new_agent_conversation`    starts an agent tab
//!   Dispatched through the OS URL handler (`xdg-open` on Linux,
//!   `open` on macOS). There is **no** action for typing into another
//!   pane, splitting an existing pane, or enumerating panes.
//!
//! Given those constraints we adapt the trait as follows:
//!
//! - [`Self::list_panes`](TerminalBackend::list_panes) returns a single
//!   synthetic pane representing *this* shell session. The id prefers
//!   the (rarely-exported) `WARP_SESSION_ID`, falling back to
//!   `"warp:current"` so callers see a stable row instead of an empty
//!   list.
//! - [`Self::send_keys`](TerminalBackend::send_keys) returns
//!   [`Error::Backend`] — Warp exposes no public IPC for typing into
//!   panes. Failing loudly is preferable to silently dropping input.
//! - [`Self::split`](TerminalBackend::split) invokes the OS URL handler
//!   with `warp://action/new_tab` (`Vertical`) or
//!   `warp://action/new_window` (`Horizontal`), threading the current
//!   working directory through the `?path=` query parameter so the new
//!   pane opens in the same cwd. Warp does not return a pane id from a
//!   URL-scheme invocation, so we synthesise one (`warp:new-<uuid>`);
//!   it cannot be used with `send_keys` or further `split` calls.
//! - [`Self::subscribe`](TerminalBackend::subscribe) returns an empty
//!   stream (no event firehose). OSC notifications still flow in via
//!   the bridge's `osc.parse` RPC, exactly like the other backends.
//!
//! The URL-handler binary is configurable via
//! [`WarpBackend::with_opener`] or the `AGENT_BRIDGE_WARP_OPENER`
//! environment variable.

use ab_core::{Error, PaneId, Result};
use async_trait::async_trait;
use futures::stream::{self, BoxStream};
use serde::{Deserialize, Serialize};
use serde_json::json;
use std::path::Path;
use tokio::io::{AsyncBufReadExt, AsyncWriteExt, BufReader};
use tokio::net::UnixStream;
use tokio::process::Command;
use uuid::Uuid;

use crate::{Pane, SplitDir, TermEvent, TerminalBackend, TerminalCapabilities};

/// Default URL-handler binary on the current platform.
///
/// We don't probe the binary here (existence is checked lazily on each
/// `split` call) to keep `WarpBackend::default()` synchronous and
/// allocation-free in the cold path.
fn default_opener() -> &'static str {
    if cfg!(target_os = "macos") {
        "open"
    } else {
        "xdg-open"
    }
}

#[derive(Clone)]
pub struct WarpBackend {
    /// OS URL-handler binary used to dispatch `warp://...` URIs.
    opener: String,
    /// Optional local IPC socket path for Warp in-process bridge adapter.
    ///
    /// When configured (or when default path exists), this backend prefers
    /// socket RPC for session listing, input, and output reads.
    ipc_socket_path: std::path::PathBuf,
}

impl Default for WarpBackend {
    fn default() -> Self {
        let opener = std::env::var("AGENT_BRIDGE_WARP_OPENER")
            .ok()
            .filter(|s| !s.is_empty())
            .unwrap_or_else(|| default_opener().to_string());
        let ipc_socket_path = std::env::var("AGENT_BRIDGE_WARP_IPC_SOCKET")
            .ok()
            .filter(|s| !s.is_empty())
            .map(std::path::PathBuf::from)
            .unwrap_or_else(Self::default_ipc_socket_path);
        Self {
            opener,
            ipc_socket_path,
        }
    }
}

impl WarpBackend {
    pub fn new() -> Self {
        Self::default()
    }

    /// Override the URL-handler binary (default: `xdg-open` on Linux,
    /// `open` on macOS). Useful for tests and unusual desktop setups
    /// (e.g. a sandboxed handler shim).
    pub fn with_opener(opener: impl Into<String>) -> Self {
        Self {
            opener: opener.into(),
            ..Self::default()
        }
    }

    fn default_ipc_socket_path() -> std::path::PathBuf {
        if let Ok(runtime) = std::env::var("XDG_RUNTIME_DIR") {
            return std::path::PathBuf::from(runtime).join("warp-agent-bridge.sock");
        }
        std::env::temp_dir().join("warp-agent-bridge.sock")
    }

    fn rpc_timeout_ms() -> u64 {
        std::env::var("AGENT_BRIDGE_WARP_IPC_TIMEOUT_MS")
            .ok()
            .and_then(|s| s.parse::<u64>().ok())
            .filter(|v| *v > 0)
            .unwrap_or(1200)
    }

    fn ipc_socket_ready(&self) -> bool {
        path_is_unix_socket(&self.ipc_socket_path)
    }

    /// OS handler binary (`xdg-open` / `open` / `AGENT_BRIDGE_WARP_OPENER`).
    pub fn url_opener_binary(&self) -> &str {
        &self.opener
    }

    /// Path checked for the optional Warp ↔ agent-bridge Unix socket (scrollback / keys).
    pub fn ipc_bridge_socket_path(&self) -> &Path {
        &self.ipc_socket_path
    }

    /// True when [`Self::ipc_bridge_socket_path`] exists as a Unix socket.
    pub fn ipc_bridge_socket_ready(&self) -> bool {
        self.ipc_socket_ready()
    }

    /// Dispatch any `warp://` URI using this backend's opener (same as [`split`](TerminalBackend::split)).
    pub async fn dispatch_scheme_uri(&self, uri: &str) -> Result<()> {
        self.dispatch_url(uri).await
    }

    /// Read the current Warp session/pane identifier from the env, if any.
    ///
    /// `WARP_SESSION_ID` is set by the shell bootstrap script
    /// (`bash_init_shell.sh`, `zsh_init_shell.sh`, `fish.sh`) but **not**
    /// exported, so child processes only see it when the user explicitly
    /// re-exports it. The fallback `"warp:current"` keeps the contract
    /// total in the common case.
    fn current_pane_id() -> String {
        std::env::var("WARP_SESSION_ID")
            .ok()
            .filter(|s| !s.is_empty())
            .map(|s| format!("warp:{s}"))
            .unwrap_or_else(|| "warp:current".to_string())
    }

    /// Detect whether the current process is running inside Warp.
    ///
    /// Used by [`crate::auto_backend`] to pick this backend. Recognises:
    /// - `TERM_PROGRAM=WarpTerminal` — canonical sentinel set by
    ///   `build_host_shell_command` in Warp's `app/src/terminal/local_tty/unix.rs`
    ///   on every spawned shell (and the equivalent Windows path).
    /// - `WARP_IS_LOCAL_SHELL_SESSION=1` — same source, secondary marker.
    /// - `WARP_HONOR_PS1=1` — honoured-PS1 sessions only. Note that Warp
    ///   sets this to literal `"0"` for the default-PS1 case, so we
    ///   must check the value, not just presence.
    pub fn detect() -> bool {
        if std::env::var("TERM_PROGRAM")
            .map(|v| v == "WarpTerminal")
            .unwrap_or(false)
        {
            return true;
        }
        if std::env::var("WARP_IS_LOCAL_SHELL_SESSION")
            .map(|v| v == "1")
            .unwrap_or(false)
        {
            return true;
        }
        if std::env::var("WARP_HONOR_PS1")
            .map(|v| v == "1")
            .unwrap_or(false)
        {
            return true;
        }
        false
    }

    /// Read the Warp client version, if Warp injected one.
    /// Set by `build_host_shell_command` to either the running app's
    /// release tag, or the literal `"local"` for development builds.
    pub fn client_version() -> Option<String> {
        std::env::var("WARP_CLIENT_VERSION")
            .ok()
            .filter(|s| !s.is_empty())
    }

    /// Dispatch a `warp://...` URL through the OS URL handler.
    async fn dispatch_url(&self, url: &str) -> Result<()> {
        let status = Command::new(&self.opener)
            .arg(url)
            .stdin(std::process::Stdio::null())
            .stdout(std::process::Stdio::null())
            .stderr(std::process::Stdio::piped())
            .status()
            .await
            .map_err(|e| Error::Backend(format!("spawn `{} {url}`: {e}", self.opener)))?;
        if !status.success() {
            return Err(Error::Backend(format!(
                "{} {url}: exit={:?}",
                self.opener,
                status.code()
            )));
        }
        Ok(())
    }

    fn pane_id_from_session(session_id: &str) -> PaneId {
        if session_id.starts_with("warp:") {
            return PaneId::from_raw(session_id.to_string());
        }
        PaneId::from_raw(format!("warp:{session_id}"))
    }

    fn session_id_from_pane(pane: &PaneId) -> String {
        pane.as_str()
            .strip_prefix("warp:")
            .unwrap_or_else(|| pane.as_str())
            .to_string()
    }

    async fn rpc_call(&self, method: &str, params: serde_json::Value) -> Result<serde_json::Value> {
        let req = BridgeRequest {
            id: Uuid::new_v4().to_string(),
            method: method.to_string(),
            params,
        };
        let timeout = std::time::Duration::from_millis(Self::rpc_timeout_ms());

        let connect = tokio::time::timeout(timeout, UnixStream::connect(&self.ipc_socket_path))
            .await
            .map_err(|_| Error::Backend("warp ipc: connect timeout".into()))?;
        let stream = connect.map_err(|e| {
            Error::Backend(format!(
                "warp ipc: connect {} failed: {e}",
                self.ipc_socket_path.display()
            ))
        })?;

        let (reader, mut writer) = stream.into_split();
        let wire = serde_json::to_vec(&req)
            .map_err(|e| Error::Backend(format!("warp ipc: encode request failed: {e}")))?;
        tokio::time::timeout(timeout, writer.write_all(&wire))
            .await
            .map_err(|_| Error::Backend("warp ipc: write timeout".into()))?
            .map_err(|e| Error::Backend(format!("warp ipc: write failed: {e}")))?;
        tokio::time::timeout(timeout, writer.write_all(b"\n"))
            .await
            .map_err(|_| Error::Backend("warp ipc: write newline timeout".into()))?
            .map_err(|e| Error::Backend(format!("warp ipc: write newline failed: {e}")))?;
        tokio::time::timeout(timeout, writer.flush())
            .await
            .map_err(|_| Error::Backend("warp ipc: flush timeout".into()))?
            .map_err(|e| Error::Backend(format!("warp ipc: flush failed: {e}")))?;

        let mut line = String::new();
        let mut br = BufReader::new(reader);
        let bytes = tokio::time::timeout(timeout, br.read_line(&mut line))
            .await
            .map_err(|_| Error::Backend("warp ipc: read timeout".into()))?
            .map_err(|e| Error::Backend(format!("warp ipc: read failed: {e}")))?;
        if bytes == 0 {
            return Err(Error::Backend("warp ipc: empty response".into()));
        }

        let resp: BridgeResponse = serde_json::from_str(&line)
            .map_err(|e| Error::Backend(format!("warp ipc: decode response failed: {e}")))?;
        if resp.id != req.id {
            return Err(Error::Backend(format!(
                "warp ipc: response id mismatch (expected {}, got {})",
                req.id, resp.id
            )));
        }
        if let Some(err) = resp.error {
            return Err(Error::Backend(format!(
                "warp ipc error {}: {}",
                err.code, err.message
            )));
        }
        resp.result
            .ok_or_else(|| Error::Backend("warp ipc: missing result".into()))
    }

    async fn rpc_list_sessions(&self) -> Result<Vec<BridgeTerminalSession>> {
        let value = self.rpc_call("list_sessions", json!({})).await?;
        serde_json::from_value(value)
            .map_err(|e| Error::Backend(format!("warp ipc: parse list_sessions failed: {e}")))
    }

    async fn rpc_send_text(&self, session_id: &str, text: &str) -> Result<()> {
        let _ = self
            .rpc_call(
                "send_text",
                json!({
                    "session_id": session_id,
                    "text": text
                }),
            )
            .await?;
        Ok(())
    }

    async fn rpc_read_scrollback(
        &self,
        session_id: &str,
        last_n_lines: usize,
    ) -> Result<Vec<String>> {
        let value = self
            .rpc_call(
                "read_scrollback",
                json!({
                    "session_id": session_id,
                    "last_n_lines": last_n_lines.max(1)
                }),
            )
            .await?;
        serde_json::from_value(value)
            .map_err(|e| Error::Backend(format!("warp ipc: parse read_scrollback failed: {e}")))
    }
}

fn path_is_unix_socket(path: &std::path::Path) -> bool {
    #[cfg(unix)]
    {
        use std::os::unix::fs::FileTypeExt;
        std::fs::metadata(path)
            .map(|m| m.file_type().is_socket())
            .unwrap_or(false)
    }
    #[cfg(not(unix))]
    {
        let _ = path;
        false
    }
}

#[async_trait]
impl TerminalBackend for WarpBackend {
    fn id(&self) -> &str {
        "warp"
    }

    fn capabilities(&self) -> TerminalCapabilities {
        let ipc = self.ipc_socket_ready();
        TerminalCapabilities {
            backend_id: self.id().to_string(),
            can_read_output: ipc,
            can_send_keys: ipc,
            can_split: true,
            warp_ipc_socket_ready: Some(ipc),
        }
    }

    /// Warp does not expose pane enumeration; we synthesise a single row
    /// for the current shell session so callers see something stable.
    async fn list_panes(&self) -> Result<Vec<Pane>> {
        if let Ok(sessions) = self.rpc_list_sessions().await {
            if !sessions.is_empty() {
                let panes = sessions
                    .into_iter()
                    .map(|s| Pane {
                        id: Self::pane_id_from_session(&s.session_id),
                        title: s.title.unwrap_or_else(|| "warp session".to_string()),
                        cwd: s.cwd,
                        command: std::env::var("SHELL").ok(),
                    })
                    .collect();
                return Ok(panes);
            }
        }
        let id = Self::current_pane_id();
        let cwd = std::env::current_dir()
            .ok()
            .map(|p| p.display().to_string());
        let title = match Self::client_version() {
            Some(v) => format!("warp shell session ({v})"),
            None => "warp shell session".to_string(),
        };
        Ok(vec![Pane {
            id: PaneId::from_raw(id),
            title,
            cwd,
            command: std::env::var("SHELL").ok(),
        }])
    }

    /// Warp has no public IPC for typing into panes. Failing loudly is
    /// preferable to silently dropping input.
    async fn send_keys(&self, pane: &PaneId, keys: &str) -> Result<()> {
        let session_id = Self::session_id_from_pane(pane);
        if self.rpc_send_text(&session_id, keys).await.is_ok() {
            return Ok(());
        }
        Err(Error::Backend(
            "warp: send_keys is not supported via URL scheme, and Warp IPC is unavailable. \
             Use the prompt UI directly, or invoke a launch config via `warp://launch/<name>`."
                .into(),
        ))
    }

    async fn read_output(&self, pane: &PaneId, lines: usize) -> Result<Vec<String>> {
        let session_id = Self::session_id_from_pane(pane);
        if let Ok(lines) = self.rpc_read_scrollback(&session_id, lines).await {
            return Ok(lines);
        }
        Err(Error::Backend(
            "warp: read_output is not supported via URL scheme, and Warp IPC is unavailable."
                .into(),
        ))
    }

    /// Best-effort split via the URL scheme.
    ///
    /// Warp's URL handler doesn't expose a per-pane split action; the
    /// closest equivalents are full-tab/full-window opens, which both
    /// accept a `?path=<dir>` query parameter to set the new pane's
    /// initial working directory (see `Action::NewTab` /
    /// `parse_tab_path` in Warp's `app/src/uri/mod.rs`):
    ///
    /// - `Vertical`   → `warp://action/new_tab?path=<cwd>`
    /// - `Horizontal` → `warp://action/new_window?path=<cwd>`
    ///
    /// We thread the bridge's `current_dir()` through `?path=` so the
    /// new pane lands where the agent expects, instead of `$HOME`.
    ///
    /// The returned [`PaneId`] is synthetic (`warp:new-<uuid>`); it
    /// cannot be used with `send_keys` or further `split` calls.
    async fn split(&self, _pane: &PaneId, dir: SplitDir) -> Result<PaneId> {
        let action = match dir {
            SplitDir::Vertical => "new_tab",
            SplitDir::Horizontal => "new_window",
        };
        let url = match std::env::current_dir().ok() {
            Some(cwd) => {
                let path = cwd.display().to_string();
                let encoded = url_encode_query_value(&path);
                format!("warp://action/{action}?path={encoded}")
            }
            None => format!("warp://action/{action}"),
        };
        self.dispatch_url(&url).await?;
        Ok(PaneId::from_raw(format!("warp:new-{}", Uuid::new_v4())))
    }

    async fn subscribe(&self) -> Result<BoxStream<'static, TermEvent>> {
        Ok(Box::pin(stream::empty()))
    }
}

/// Percent-encode a filesystem path for use as a query-string value.
///
/// We cannot pull in `url`/`percent-encoding` for one call site, so this
/// hand-rolls the small subset we need: encode every byte that isn't an
/// unreserved query-string char per RFC 3986. Keeps the crate's
/// dependency surface unchanged.
fn url_encode_query_value(s: &str) -> String {
    let mut out = String::with_capacity(s.len());
    for &b in s.as_bytes() {
        let unreserved = b.is_ascii_alphanumeric()
            || b == b'-'
            || b == b'_'
            || b == b'.'
            || b == b'~'
            || b == b'/';
        if unreserved {
            out.push(b as char);
        } else {
            out.push_str(&format!("%{:02X}", b));
        }
    }
    out
}

/// Build `warp://action/new_tab` ([Warp URI docs](https://docs.warp.dev/terminal/more-features/uri-scheme)).
/// Non-empty `path` becomes `?path=<percent-encoded>`.
pub fn warp_scheme_new_tab(path: Option<&str>) -> String {
    match path.filter(|p| !p.is_empty()) {
        Some(p) => format!("warp://action/new_tab?path={}", url_encode_query_value(p)),
        None => "warp://action/new_tab".into(),
    }
}

/// Build `warp://action/new_window`.
pub fn warp_scheme_new_window(path: Option<&str>) -> String {
    match path.filter(|p| !p.is_empty()) {
        Some(p) => format!(
            "warp://action/new_window?path={}",
            url_encode_query_value(p)
        ),
        None => "warp://action/new_window".into(),
    }
}

/// Open Warp settings (bridge roadmap / DESIGN-warp-first-agent-shell).
///
/// This action id is **not** listed in the public Warp docs as of 2026; it may
/// require a recent client or become a no-op. Prefer trying from inside Warp.
pub fn warp_scheme_open_settings_page() -> &'static str {
    "warp://action/open_settings_page"
}

/// Open a saved **Launch Configuration** by name: `warp://launch/<name>` (Warp docs).
///
/// `configuration_name` is percent-encoded for spaces and special characters.
pub fn warp_scheme_launch_configuration(configuration_name: &str) -> String {
    let name = configuration_name.trim();
    format!("warp://launch/{}", url_encode_query_value(name))
}

/// Dispatch a `warp://…` URI using default opener + env (`WarpBackend::default()`).
pub async fn dispatch_warp_scheme_uri(uri: &str) -> Result<()> {
    WarpBackend::new().dispatch_scheme_uri(uri).await
}

#[derive(Debug, Clone, Serialize, Deserialize)]
struct BridgeRequest {
    id: String,
    method: String,
    #[serde(default)]
    params: serde_json::Value,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
struct BridgeResponse {
    id: String,
    #[serde(default)]
    result: Option<serde_json::Value>,
    #[serde(default)]
    error: Option<BridgeError>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
struct BridgeError {
    code: i32,
    message: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
struct BridgeTerminalSession {
    session_id: String,
    #[serde(default)]
    title: Option<String>,
    #[serde(default)]
    cwd: Option<String>,
}

// ─── tests ─────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;
    use tokio::io::{AsyncBufReadExt, AsyncWriteExt, BufReader};
    use tokio::net::UnixListener;

    #[test]
    fn id_is_stable() {
        assert_eq!(WarpBackend::new().id(), "warp");
    }

    #[test]
    fn default_opener_is_platform_appropriate() {
        // Clear the override so we test the platform default.
        // SAFETY: tests run single-threaded by default in this crate.
        std::env::remove_var("AGENT_BRIDGE_WARP_OPENER");
        let backend = WarpBackend::new();
        if cfg!(target_os = "macos") {
            assert_eq!(backend.opener, "open");
        } else {
            assert_eq!(backend.opener, "xdg-open");
        }
    }

    #[test]
    fn opener_env_override_takes_effect() {
        std::env::set_var("AGENT_BRIDGE_WARP_OPENER", "/usr/local/bin/my-opener");
        let backend = WarpBackend::new();
        assert_eq!(backend.opener, "/usr/local/bin/my-opener");
        std::env::remove_var("AGENT_BRIDGE_WARP_OPENER");
    }

    #[test]
    fn with_opener_overrides_default() {
        let backend = WarpBackend::with_opener("custom-handler");
        assert_eq!(backend.opener, "custom-handler");
    }

    #[test]
    fn detect_recognises_term_program() {
        std::env::remove_var("WARP_IS_LOCAL_SHELL_SESSION");
        std::env::remove_var("WARP_HONOR_PS1");
        std::env::set_var("TERM_PROGRAM", "WarpTerminal");
        assert!(WarpBackend::detect());
        std::env::set_var("TERM_PROGRAM", "iTerm.app");
        assert!(!WarpBackend::detect());
        std::env::remove_var("TERM_PROGRAM");
    }

    #[test]
    fn detect_recognises_local_shell_session() {
        std::env::remove_var("TERM_PROGRAM");
        std::env::remove_var("WARP_HONOR_PS1");
        std::env::set_var("WARP_IS_LOCAL_SHELL_SESSION", "1");
        assert!(WarpBackend::detect());
        std::env::remove_var("WARP_IS_LOCAL_SHELL_SESSION");
    }

    #[test]
    fn detect_only_when_honor_ps1_is_one() {
        // Warp sets WARP_HONOR_PS1 to literal "0" or "1" — the "0" case
        // must NOT be misread as "running inside Warp".
        std::env::remove_var("TERM_PROGRAM");
        std::env::remove_var("WARP_IS_LOCAL_SHELL_SESSION");
        std::env::set_var("WARP_HONOR_PS1", "0");
        assert!(
            !WarpBackend::detect(),
            "WARP_HONOR_PS1=0 must not be mistaken for Warp"
        );
        std::env::set_var("WARP_HONOR_PS1", "1");
        assert!(WarpBackend::detect());
        std::env::remove_var("WARP_HONOR_PS1");
    }

    #[test]
    fn detect_returns_false_when_no_warp_env() {
        std::env::remove_var("TERM_PROGRAM");
        std::env::remove_var("WARP_IS_LOCAL_SHELL_SESSION");
        std::env::remove_var("WARP_HONOR_PS1");
        assert!(!WarpBackend::detect());
    }

    #[test]
    fn current_pane_id_uses_session_env_when_present() {
        std::env::set_var("WARP_SESSION_ID", "abc-123");
        assert_eq!(WarpBackend::current_pane_id(), "warp:abc-123");
        std::env::remove_var("WARP_SESSION_ID");
    }

    #[test]
    fn current_pane_id_falls_back_when_env_missing() {
        std::env::remove_var("WARP_SESSION_ID");
        assert_eq!(WarpBackend::current_pane_id(), "warp:current");
    }

    #[test]
    fn client_version_reads_warp_env() {
        std::env::set_var("WARP_CLIENT_VERSION", "v1.2.3");
        assert_eq!(WarpBackend::client_version(), Some("v1.2.3".into()));
        std::env::remove_var("WARP_CLIENT_VERSION");
        assert_eq!(WarpBackend::client_version(), None);
    }

    #[test]
    fn url_encode_handles_spaces_and_unicode() {
        assert_eq!(url_encode_query_value("/tmp/foo"), "/tmp/foo");
        assert_eq!(
            url_encode_query_value("/Users/me/My Code"),
            "/Users/me/My%20Code"
        );
        assert_eq!(
            url_encode_query_value("/data/中文"),
            "/data/%E4%B8%AD%E6%96%87"
        );
    }

    #[test]
    fn capabilities_reflect_missing_ipc_socket() {
        std::env::set_var(
            "AGENT_BRIDGE_WARP_IPC_SOCKET",
            "/nonexistent/agent-bridge-no-socket.sock",
        );
        let backend = WarpBackend::new();
        let c = crate::TerminalBackend::capabilities(&backend);
        assert_eq!(c.backend_id, "warp");
        assert!(!c.can_read_output);
        assert!(!c.can_send_keys);
        assert!(c.can_split);
        assert_eq!(c.warp_ipc_socket_ready, Some(false));
        std::env::remove_var("AGENT_BRIDGE_WARP_IPC_SOCKET");
    }

    #[tokio::test]
    async fn list_panes_returns_single_synthetic_row() {
        std::env::remove_var("WARP_SESSION_ID");
        let backend = WarpBackend::new();
        let panes = backend.list_panes().await.expect("list_panes");
        assert_eq!(panes.len(), 1);
        assert_eq!(panes[0].id.as_str(), "warp:current");
    }

    #[tokio::test]
    async fn send_keys_returns_unsupported_error() {
        let backend = WarpBackend::new();
        let err = backend
            .send_keys(&PaneId::from_raw("warp:current"), "echo hi\n")
            .await
            .expect_err("send_keys must fail on warp");
        match err {
            Error::Backend(msg) => assert!(msg.contains("warp")),
            other => panic!("expected Error::Backend, got {other:?}"),
        }
    }

    #[tokio::test]
    async fn subscribe_yields_empty_stream() {
        use futures::StreamExt;
        let backend = WarpBackend::new();
        let mut stream = backend.subscribe().await.expect("subscribe");
        // poll once — empty stream resolves to None immediately.
        assert!(stream.next().await.is_none());
    }

    #[tokio::test]
    async fn warp_ipc_e2e_list_send_read() {
        let socket = std::env::temp_dir().join(format!("ab-warp-ipc-{}.sock", Uuid::new_v4()));
        let _ = std::fs::remove_file(&socket);
        let listener = UnixListener::bind(&socket).expect("bind unix socket");

        let server = tokio::spawn(async move {
            for _ in 0..3 {
                let (stream, _) = listener.accept().await.expect("accept");
                let (reader, mut writer) = stream.into_split();
                let mut br = BufReader::new(reader);
                let mut line = String::new();
                br.read_line(&mut line).await.expect("read request");
                let req: BridgeRequest = serde_json::from_str(&line).expect("decode request");
                let result = match req.method.as_str() {
                    "list_sessions" => json!([{
                        "session_id": "test-session",
                        "title": "Warp Test Session",
                        "cwd": "/tmp"
                    }]),
                    "send_text" => json!({"ok": true}),
                    "read_scrollback" => json!(["line one", "line two"]),
                    _ => json!(null),
                };
                let resp = BridgeResponse {
                    id: req.id,
                    result: Some(result),
                    error: None,
                };
                let mut wire = serde_json::to_vec(&resp).expect("encode response");
                wire.push(b'\n');
                writer.write_all(&wire).await.expect("write response");
                writer.flush().await.expect("flush response");
            }
        });

        std::env::set_var("AGENT_BRIDGE_WARP_IPC_SOCKET", socket.display().to_string());
        let backend = WarpBackend::new();
        let caps = backend.capabilities();
        assert!(caps.can_read_output);
        assert!(caps.can_send_keys);

        let panes = backend.list_panes().await.expect("list_panes via ipc");
        assert_eq!(panes.len(), 1);
        assert_eq!(panes[0].id.as_str(), "warp:test-session");

        let lines = backend
            .read_output(&PaneId::from_raw("warp:test-session"), 20)
            .await
            .expect("read_output via ipc");
        assert_eq!(lines, vec!["line one".to_string(), "line two".to_string()]);

        backend
            .send_keys(&PaneId::from_raw("warp:test-session"), "echo hi\n")
            .await
            .expect("send_keys via ipc");

        server.await.expect("server task");
        std::env::remove_var("AGENT_BRIDGE_WARP_IPC_SOCKET");
        let _ = std::fs::remove_file(&socket);
    }

    #[test]
    fn warp_scheme_tabs_windows_without_path() {
        assert_eq!(warp_scheme_new_tab(None), "warp://action/new_tab");
        assert_eq!(warp_scheme_new_window(None), "warp://action/new_window");
    }

    #[test]
    fn warp_scheme_tabs_encode_spaces_in_path() {
        let u = warp_scheme_new_tab(Some("/tmp/foo bar"));
        assert!(u.starts_with("warp://action/new_tab?path="));
        assert!(u.contains("%20"));
    }

    #[test]
    fn warp_scheme_launch_configuration_trims_and_encodes() {
        assert_eq!(
            warp_scheme_launch_configuration(" My LC "),
            "warp://launch/My%20LC"
        );
    }
}
