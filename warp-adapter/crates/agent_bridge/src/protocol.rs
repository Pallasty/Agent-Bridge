use serde::{Deserialize, Serialize};

/// JSON-RPC-like request envelope for local Agent-Bridge IPC.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct BridgeRequest {
    pub id: String,
    pub method: String,
    #[serde(default)]
    pub params: serde_json::Value,
}

/// JSON-RPC-like response envelope for local Agent-Bridge IPC.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct BridgeResponse {
    pub id: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub result: Option<serde_json::Value>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub error: Option<BridgeError>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct BridgeError {
    pub code: i32,
    pub message: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TerminalSession {
    pub session_id: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub title: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub cwd: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ReadScrollbackParams {
    pub session_id: String,
    #[serde(default = "default_line_count")]
    pub last_n_lines: usize,
}

fn default_line_count() -> usize {
    80
}

/// Minimal backend interface for Warp in-process integration.
///
/// Methods mirror the first migration targets from Agent-Bridge design:
/// - list_sessions
/// - send_text
/// - read_scrollback
pub trait AgentBridgeBackend: Send + Sync {
    fn list_sessions(&self) -> anyhow::Result<Vec<TerminalSession>>;
    fn send_text(&self, session_id: &str, text: &str) -> anyhow::Result<()>;
    fn read_scrollback(&self, session_id: &str, last_n_lines: usize) -> anyhow::Result<Vec<String>>;
}

