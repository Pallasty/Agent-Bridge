use serde::{Deserialize, Serialize};

use crate::ids::SessionId;

/// A notification event flowing into the bridge — eventually fanned out to
/// all registered Notifier backends (dbus, webhook, push, ...).
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct NotifyEvent {
    pub source: NotifySource,
    pub severity: NotifySeverity,
    pub title: String,
    pub body: String,
    /// Originating agent session, if any.
    pub session_id: Option<SessionId>,
    /// Free-form structured data (git branch, PR url, etc.).
    #[serde(default)]
    pub context: serde_json::Value,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum NotifySource {
    /// User-triggered via agent-cli.
    Manual,
    /// OSC 9 escape sequence ("growl-style" iTerm notification).
    Osc9,
    /// OSC 99 ConEmu/extension notification.
    Osc99,
    /// OSC 777 (rxvt-unicode) notification.
    Osc777,
    /// MCP tool invocation.
    Mcp,
    /// Internal agent-bridge subsystem.
    System,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Default, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum NotifySeverity {
    #[default]
    Info,
    Success,
    Warning,
    Error,
    Attention,
}
