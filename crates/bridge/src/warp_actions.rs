//! Warp URI helpers for MCP tools (W4 — DESIGN-warp-first-agent-shell).

use ab_terminal::WarpBackend;
use serde_json::{json, Value};
use tokio::process::Command;

/// Build the JSON payload for the `warp_status` MCP tool.
pub async fn warp_status_snapshot(terminal_backend_id: Option<String>) -> Value {
    let backend = WarpBackend::new();
    let oz_on_path = oz_cli_available().await;
    json!({
        "inside_warp_terminal_shell": WarpBackend::detect(),
        "warp_client_version": WarpBackend::client_version(),
        "configured_terminal_backend_id": terminal_backend_id,
        "warp_url_opener": backend.url_opener_binary(),
        "warp_ipc_socket_path": backend.ipc_bridge_socket_path().display().to_string(),
        "warp_ipc_bridge_socket_ready": backend.ipc_bridge_socket_ready(),
        "oz_cli_on_path": oz_on_path,
        "uri_scheme_note": "Documented URIs: warp://action/new_tab, new_window, warp://launch/<name>. \
             open_settings_page is best-effort (not in public Warp docs).",
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
