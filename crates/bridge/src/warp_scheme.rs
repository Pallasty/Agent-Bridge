//! Warp URL-scheme launchers — IPC-free helpers extracted from the
//! retired `WarpBackend` (see `museum/warp-ipc-terminal/`).
//!
//! The MCP tools `warp_open_tab`, `warp_open_window`,
//! `warp_launch_workflow`, `warp_open_settings`, and `warp_status` only
//! need three things from the host environment:
//!
//! 1. A way to detect whether the caller is running inside Warp
//!    (env-var sniff, no IPC).
//! 2. URL-string builders for the documented `warp://...` action and
//!    launch URIs.
//! 3. A `dispatch_url` that hands the URI to the OS's URL handler
//!    (`open` on macOS, `xdg-open` on Linux, configurable via
//!    `AGENT_BRIDGE_WARP_OPENER`).
//!
//! Keeping these as free functions in the bridge crate (rather than a
//! struct + trait impl in the terminal crate) avoids dragging the
//! retired Warp IPC backend back into the workspace.

use ab_core::{Error, Result};
use tokio::process::Command;

// ── env probes ─────────────────────────────────────────────────────────

/// Detect whether the current process is running inside Warp. Recognises
/// `TERM_PROGRAM=WarpTerminal`, `WARP_IS_LOCAL_SHELL_SESSION=1`, and
/// `WARP_HONOR_PS1=1`. Pure env read; no I/O.
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

/// Read `WARP_CLIENT_VERSION` from the env if Warp's shell hooks
/// injected one (release tag for shipped builds; literal `"local"` for
/// dev builds).
pub fn client_version() -> Option<String> {
    std::env::var("WARP_CLIENT_VERSION")
        .ok()
        .filter(|s| !s.is_empty())
}

// ── URL opener ─────────────────────────────────────────────────────────

fn default_opener_binary() -> &'static str {
    if cfg!(target_os = "macos") {
        "open"
    } else {
        "xdg-open"
    }
}

/// Resolve which OS URL-handler to use. Override via
/// `AGENT_BRIDGE_WARP_OPENER`.
pub fn opener_binary() -> String {
    std::env::var("AGENT_BRIDGE_WARP_OPENER")
        .ok()
        .filter(|s| !s.is_empty())
        .unwrap_or_else(|| default_opener_binary().to_string())
}

/// Hand a `warp://...` URI to the OS URL handler. Errors if the handler
/// fails to spawn or exits non-zero.
pub async fn dispatch_url(url: &str) -> Result<()> {
    let opener = opener_binary();
    let status = Command::new(&opener)
        .arg(url)
        .stdin(std::process::Stdio::null())
        .stdout(std::process::Stdio::null())
        .stderr(std::process::Stdio::piped())
        .status()
        .await
        .map_err(|e| Error::Backend(format!("spawn `{opener} {url}`: {e}")))?;
    if !status.success() {
        return Err(Error::Backend(format!(
            "{opener} {url}: exit={:?}",
            status.code()
        )));
    }
    Ok(())
}

// ── URL builders ───────────────────────────────────────────────────────

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

/// `warp://action/new_tab` — optional `?path=<percent-encoded>`.
pub fn scheme_new_tab(path: Option<&str>) -> String {
    match path.filter(|p| !p.is_empty()) {
        Some(p) => format!("warp://action/new_tab?path={}", url_encode_query_value(p)),
        None => "warp://action/new_tab".into(),
    }
}

/// `warp://action/new_window` — optional `?path=<percent-encoded>`.
pub fn scheme_new_window(path: Option<&str>) -> String {
    match path.filter(|p| !p.is_empty()) {
        Some(p) => format!(
            "warp://action/new_window?path={}",
            url_encode_query_value(p)
        ),
        None => "warp://action/new_window".into(),
    }
}

/// `warp://action/open_settings_page` — best-effort; not in the public
/// Warp docs as of 2026, may no-op on older clients.
pub fn scheme_open_settings_page() -> &'static str {
    "warp://action/open_settings_page"
}

/// `warp://launch/<percent-encoded-name>` — opens a saved Launch
/// Configuration by name.
pub fn scheme_launch_configuration(configuration_name: &str) -> String {
    let name = configuration_name.trim();
    format!("warp://launch/{}", url_encode_query_value(name))
}

// ── tests ──────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn url_encode_keeps_unreserved() {
        assert_eq!(url_encode_query_value("/path/to/dir"), "/path/to/dir");
        assert_eq!(url_encode_query_value("a-z_0~9"), "a-z_0~9");
    }

    #[test]
    fn url_encode_percent_encodes_specials() {
        assert_eq!(url_encode_query_value("hello world"), "hello%20world");
        assert_eq!(url_encode_query_value("a&b=c"), "a%26b%3Dc");
    }

    #[test]
    fn scheme_new_tab_with_and_without_path() {
        assert_eq!(scheme_new_tab(None), "warp://action/new_tab");
        assert_eq!(scheme_new_tab(Some("")), "warp://action/new_tab");
        assert_eq!(
            scheme_new_tab(Some("/Users/me/code")),
            "warp://action/new_tab?path=/Users/me/code"
        );
    }

    #[test]
    fn scheme_new_window_encodes_spaces() {
        assert_eq!(
            scheme_new_window(Some("/Users/me/code base")),
            "warp://action/new_window?path=/Users/me/code%20base"
        );
    }

    #[test]
    fn scheme_launch_configuration_trims_and_encodes() {
        assert_eq!(
            scheme_launch_configuration("  My Project  "),
            "warp://launch/My%20Project"
        );
    }

    #[test]
    fn detect_recognises_term_program() {
        let prev = std::env::var_os("TERM_PROGRAM");
        std::env::set_var("TERM_PROGRAM", "WarpTerminal");
        assert!(detect());
        // Restore so other tests aren't perturbed.
        match prev {
            Some(v) => std::env::set_var("TERM_PROGRAM", v),
            None => std::env::remove_var("TERM_PROGRAM"),
        }
    }

    #[test]
    fn opener_falls_back_to_platform_default() {
        let prev = std::env::var_os("AGENT_BRIDGE_WARP_OPENER");
        std::env::remove_var("AGENT_BRIDGE_WARP_OPENER");
        let got = opener_binary();
        assert!(got == "open" || got == "xdg-open", "got: {got}");
        if let Some(v) = prev {
            std::env::set_var("AGENT_BRIDGE_WARP_OPENER", v);
        }
    }
}
