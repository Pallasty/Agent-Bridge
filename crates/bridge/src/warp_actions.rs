//! Warp URI helpers for MCP tools (W4 — DESIGN-warp-first-agent-shell).
//!
//! The IPC backend that originally lived under `ab_terminal::WarpBackend`
//! moved to `museum/warp-ipc-terminal/` on 2026-05-08; this module now
//! exposes only the URL-scheme launchers, served by `crate::warp_scheme`.

use crate::warp_scheme;
use serde_json::{json, Value};
use tokio::process::Command;

/// Build the JSON payload for the `warp_status` MCP tool.
pub async fn warp_status_snapshot(terminal_backend_id: Option<String>) -> Value {
    let oz_on_path = oz_cli_available().await;
    json!({
        "inside_warp_terminal_shell": warp_scheme::detect(),
        "warp_client_version": warp_scheme::client_version(),
        "configured_terminal_backend_id": terminal_backend_id,
        "warp_url_opener": warp_scheme::opener_binary(),
        "oz_cli_on_path": oz_on_path,
        "uri_scheme_note": "Documented URIs: warp://action/new_tab, new_window, warp://launch/<name>. \
             open_settings_page is best-effort (not in public Warp docs). \
             IPC bridge retired (see museum/warp-ipc-terminal/) — use PtyBackend \
             + OSC 133 for terminal control.",
    })
}

async fn oz_cli_available() -> bool {
    Command::new("sh")
        .arg("-c")
        .arg("command -v oz >/dev/null 2>&1")
        .stdin(std::process::Stdio::null())
        .stdout(std::process::Stdio::null())
        .stderr(std::process::Stdio::null())
        .status()
        .await
        .map(|s| s.success())
        .unwrap_or(false)
}
