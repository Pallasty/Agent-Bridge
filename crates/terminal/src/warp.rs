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
use tokio::process::Command;
use uuid::Uuid;

use crate::{Pane, SplitDir, TermEvent, TerminalBackend};

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
}

impl Default for WarpBackend {
    fn default() -> Self {
        let opener = std::env::var("AGENT_BRIDGE_WARP_OPENER")
            .ok()
            .filter(|s| !s.is_empty())
            .unwrap_or_else(|| default_opener().to_string());
        Self { opener }
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
        }
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
}

#[async_trait]
impl TerminalBackend for WarpBackend {
    fn id(&self) -> &str {
        "warp"
    }

    /// Warp does not expose pane enumeration; we synthesise a single row
    /// for the current shell session so callers see something stable.
    async fn list_panes(&self) -> Result<Vec<Pane>> {
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
    async fn send_keys(&self, _pane: &PaneId, _keys: &str) -> Result<()> {
        Err(Error::Backend(
            "warp: send_keys is not supported — Warp does not expose a \
             public CLI/IPC for typing into panes. Use the prompt UI \
             directly, or invoke a launch config via `warp://launch/<name>`."
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

// ─── tests ─────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

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
        assert_eq!(url_encode_query_value("/data/中文"), "/data/%E4%B8%AD%E6%96%87");
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
}
