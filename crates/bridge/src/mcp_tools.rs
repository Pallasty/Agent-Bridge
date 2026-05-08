//! Built-in MCP tools — wrap the bridge's backend bundle and expose it to
//! Claude Code (or any MCP client) over the `tools/call` channel.

use ab_agent::{oz::fetch_run_status, GitWorktreeManager, SpawnConfig};
use ab_core::{NotifyEvent, NotifySeverity, NotifySource, PageId, PaneId, Result, SessionId};
use ab_mcp::{ContentBlock, McpTool, ToolContext, ToolRegistry, ToolResult, ToolSchema};
use ab_store::{
    cosine_similarity, embed_text, prioritize_session_handoff,
    // MemoryStats is used indirectly via store.memory_stats() — no direct struct access needed.
    CompactPolicy,
    ImportConflictPolicy,
    MemoryExportFilter,
    MemoryListSort,
    MemoryRecord,
    MemorySearchHit,
    PlanRecord,
    PlanStep,
    SessionFilter,
    StateStore,
};
use ab_terminal::{
    dispatch_warp_scheme_uri, warp_scheme_launch_configuration, warp_scheme_new_tab,
    warp_scheme_new_window, warp_scheme_open_settings_page, OscEvent, OscParser, SpawnOptions,
    SplitDir, TerminalBlock,
};
use async_trait::async_trait;
use base64::{engine::general_purpose, Engine as _};
use serde_json::{json, Value};
use std::collections::HashMap;
use std::path::PathBuf;
use std::sync::Arc;
use std::time::{Duration, Instant};
use tokio::process::Command as TokioCommand;

use crate::context_budget::{budget_recommendation, estimated_usage_tokens, model_context_limit};
use crate::hub::Hub;
use crate::project::{changes_digest, detect_project, resolve_cwd};
use crate::security::Cap;
use crate::session_handoff::build_handoff_brief;
use crate::warp_actions::warp_status_snapshot;

// ===========================================================================
//                                   notify
// ===========================================================================

pub struct NotifyTool {
    hub: Hub,
}
impl NotifyTool {
    pub fn new(hub: Hub) -> Self {
        Self { hub }
    }
}

#[async_trait]
impl McpTool for NotifyTool {
    fn name(&self) -> &'static str {
        "notify"
    }
    fn schema(&self) -> ToolSchema {
        ToolSchema {
            name: self.name().into(),
            description: "Send a desktop notification. Persists to the bridge's history \
                 store and fans out to every registered Notifier (today: D-Bus). \
                 Use this when the agent needs to ping the human asynchronously."
                .into(),
            input_schema: json!({
                "type": "object",
                "properties": {
                    "title": { "type": "string", "default": "agent-bridge" },
                    "body":  { "type": "string", "description": "Notification body text." },
                    "severity": {
                        "type": "string",
                        "enum": ["info","success","warning","error","attention"],
                        "default": "info"
                    }
                },
                "required": ["body"]
            }),
        }
    }
    async fn execute(&self, args: Value, _ctx: &ToolContext) -> Result<ToolResult> {
        let evt = NotifyEvent {
            source: NotifySource::Mcp,
            severity: args
                .get("severity")
                .and_then(|v| v.as_str())
                .and_then(parse_severity)
                .unwrap_or(NotifySeverity::Info),
            title: args
                .get("title")
                .and_then(|v| v.as_str())
                .unwrap_or("agent-bridge")
                .into(),
            body: args
                .get("body")
                .and_then(|v| v.as_str())
                .unwrap_or("")
                .into(),
            session_id: None,
            context: Value::Null,
        };
        let (delivered, persisted) = self.hub.deliver(&evt).await;
        Ok(ToolResult::text(format!(
            "delivered to {delivered} notifier(s); persisted={persisted}"
        )))
    }
}

// ===========================================================================
//                            notifications_recent
// ===========================================================================

pub struct NotificationsRecentTool {
    hub: Hub,
}
impl NotificationsRecentTool {
    pub fn new(hub: Hub) -> Self {
        Self { hub }
    }
}

#[async_trait]
impl McpTool for NotificationsRecentTool {
    fn name(&self) -> &'static str {
        "notifications_recent"
    }
    fn schema(&self) -> ToolSchema {
        ToolSchema {
            name: self.name().into(),
            description: "Return the most-recent N notifications from the bridge's persistent \
                 history (default 20, max 1000). Useful for the agent to see what it \
                 already told the human and avoid duplicate pings."
                .into(),
            input_schema: json!({
                "type": "object",
                "properties": {
                    "limit": { "type": "integer", "minimum": 1, "maximum": 1000, "default": 20 }
                }
            }),
        }
    }
    async fn execute(&self, args: Value, _ctx: &ToolContext) -> Result<ToolResult> {
        let store = match &self.hub.store {
            Some(s) => s.clone(),
            None => return Ok(ToolResult::error("no store configured")),
        };
        let limit = args
            .get("limit")
            .and_then(|v| v.as_u64())
            .unwrap_or(20)
            .min(1000) as u32;
        let rows = store.recent_notifications(limit).await?;
        Ok(ToolResult::json_text(
            &serde_json::to_value(rows).unwrap_or(Value::Null),
        ))
    }
}

// ===========================================================================
//                                osc_parse
// ===========================================================================

pub struct OscParseTool {
    hub: Hub,
}
impl OscParseTool {
    pub fn new(hub: Hub) -> Self {
        Self { hub }
    }
}

#[async_trait]
impl McpTool for OscParseTool {
    fn name(&self) -> &'static str {
        "osc_parse"
    }
    fn schema(&self) -> ToolSchema {
        ToolSchema {
            name: self.name().into(),
            description: "Parse a raw byte sequence for OSC 9 / 99 / 777 notification escape \
                 codes and dispatch every successfully-parsed event through the standard \
                 notification pipeline (persist + fan-out). Pass real ESC characters in \
                 'raw'; clients can use JSON's \\u001b escape if needed."
                .into(),
            input_schema: json!({
                "type": "object",
                "properties": {
                    "raw": { "type": "string", "description": "Bytes to scan for OSC sequences." }
                },
                "required": ["raw"]
            }),
        }
    }
    async fn execute(&self, args: Value, _ctx: &ToolContext) -> Result<ToolResult> {
        let raw = args
            .get("raw")
            .and_then(|v| v.as_str())
            .unwrap_or("")
            .as_bytes()
            .to_vec();
        let mut parser = OscParser::new();
        let events = parser.feed(&raw);
        let mut delivered = 0u32;
        let mut malformed = Vec::new();
        for e in &events {
            match e {
                OscEvent::Notify(evt) => {
                    let (d, _p) = self.hub.deliver(evt).await;
                    if d > 0 {
                        delivered += 1;
                    }
                }
                OscEvent::Malformed { code, reason, .. } => {
                    malformed.push(json!({ "code": code, "reason": reason }));
                }
                // OSC 133 prompt markers flow through the read_blocks
                // state machine, not the notification fan-out.
                OscEvent::Prompt(_) => {}
            }
        }
        Ok(ToolResult::json_text(&json!({
            "events": events.len(),
            "delivered": delivered,
            "malformed": malformed,
        })))
    }
}

// ===========================================================================
//                              terminal tools
// ===========================================================================

pub struct TerminalListTool {
    hub: Hub,
}
impl TerminalListTool {
    pub fn new(hub: Hub) -> Self {
        Self { hub }
    }
}
#[async_trait]
impl McpTool for TerminalListTool {
    fn name(&self) -> &'static str {
        "terminal_list"
    }
    fn schema(&self) -> ToolSchema {
        ToolSchema {
            name: self.name().into(),
            description: "List terminal panes from the active terminal-multiplexer backend \
                 (today: WezTerm). Returns each pane's id, title, cwd, and command. \
                 Useful for the agent to discover where the human is working."
                .into(),
            input_schema: json!({ "type": "object", "properties": {} }),
        }
    }
    async fn execute(&self, _args: Value, _ctx: &ToolContext) -> Result<ToolResult> {
        let term = match &self.hub.terminal {
            Some(t) => t.clone(),
            None => return Ok(ToolResult::error("no terminal backend configured")),
        };
        match term.list_panes().await {
            Ok(panes) => Ok(ToolResult::json_text(
                &serde_json::to_value(panes).unwrap_or(Value::Null),
            )),
            Err(e) => Ok(ToolResult::error(format!("terminal: {e}"))),
        }
    }
}

pub struct TerminalSendKeysTool {
    hub: Hub,
}
impl TerminalSendKeysTool {
    pub fn new(hub: Hub) -> Self {
        Self { hub }
    }
}
#[async_trait]
impl McpTool for TerminalSendKeysTool {
    fn name(&self) -> &'static str {
        "terminal_send_keys"
    }
    fn schema(&self) -> ToolSchema {
        ToolSchema {
            name: self.name().into(),
            description: "Type the given text into the specified terminal pane (e.g. send a \
                 command to a sibling agent's session). Does NOT append a newline — \
                 include '\\n' explicitly if you want the command executed."
                .into(),
            input_schema: json!({
                "type": "object",
                "properties": {
                    "pane": { "type": "string", "description": "Pane id from terminal_list." },
                    "keys": { "type": "string", "description": "Text to inject into the pane." }
                },
                "required": ["pane", "keys"]
            }),
        }
    }
    async fn execute(&self, args: Value, _ctx: &ToolContext) -> Result<ToolResult> {
        if let Err(e) = self.hub.security.check(Cap::TerminalWrite) {
            return Ok(ToolResult::error(e));
        }
        let term = match &self.hub.terminal {
            Some(t) => t.clone(),
            None => return Ok(ToolResult::error("no terminal backend configured")),
        };
        let pane = match args.get("pane").and_then(|v| v.as_str()) {
            Some(s) => PaneId::from_raw(s.to_string()),
            None => return Ok(ToolResult::error("missing 'pane'")),
        };
        let raw = args.get("keys").and_then(|v| v.as_str()).unwrap_or("");
        // Callers write escape sequences as literal text (e.g. \n, \r, \x1b).
        // Unescape them so the PTY receives the actual control bytes.
        let keys = unescape_keys(raw);
        match term.send_keys(&pane, &keys).await {
            Ok(()) => Ok(ToolResult::text(format!(
                "sent {} bytes to {pane}",
                keys.len()
            ))),
            Err(e) => Ok(ToolResult::error(format!("terminal: {e}"))),
        }
    }
}

pub struct TerminalSplitTool {
    hub: Hub,
}
impl TerminalSplitTool {
    pub fn new(hub: Hub) -> Self {
        Self { hub }
    }
}
#[async_trait]
impl McpTool for TerminalSplitTool {
    fn name(&self) -> &'static str {
        "terminal_split"
    }
    fn schema(&self) -> ToolSchema {
        ToolSchema {
            name: self.name().into(),
            description: "Split a terminal pane horizontally or vertically and return the \
                 new pane's id. Optional cwd (working directory) and env (extra vars) — \
                 honored by the in-daemon PTY backend; silently ignored by backends that \
                 delegate spawning to an external multiplexer."
                .into(),
            input_schema: json!({
                "type": "object",
                "properties": {
                    "pane": { "type": "string" },
                    "dir":  { "type": "string", "enum": ["horizontal", "vertical"], "default": "vertical" },
                    "cwd": {
                        "type": "string",
                        "description": "Working directory for the new shell (PtyBackend only). \
                                        Defaults to the daemon's cwd."
                    },
                    "env": {
                        "type": "object",
                        "description": "Extra environment variables for the new shell (PtyBackend only). \
                                        TERM is preserved by the backend.",
                        "additionalProperties": { "type": "string" }
                    }
                },
                "required": ["pane"]
            }),
        }
    }
    async fn execute(&self, args: Value, _ctx: &ToolContext) -> Result<ToolResult> {
        if let Err(e) = self.hub.security.check(Cap::TerminalWrite) {
            return Ok(ToolResult::error(e));
        }
        let term = match &self.hub.terminal {
            Some(t) => t.clone(),
            None => return Ok(ToolResult::error("no terminal backend configured")),
        };
        let pane = match args.get("pane").and_then(|v| v.as_str()) {
            Some(s) => PaneId::from_raw(s.to_string()),
            None => return Ok(ToolResult::error("missing 'pane'")),
        };
        let dir = match args
            .get("dir")
            .and_then(|v| v.as_str())
            .unwrap_or("vertical")
        {
            "horizontal" => SplitDir::Horizontal,
            _ => SplitDir::Vertical,
        };
        let cwd = args
            .get("cwd")
            .and_then(|v| v.as_str())
            .filter(|s| !s.is_empty())
            .map(ToString::to_string);
        let env_map: HashMap<String, String> = args
            .get("env")
            .and_then(|v| v.as_object())
            .map(|m| {
                m.iter()
                    .filter_map(|(k, v)| v.as_str().map(|s| (k.clone(), s.to_string())))
                    .collect()
            })
            .unwrap_or_default();
        let has_options = cwd.is_some() || !env_map.is_empty();
        let result = if has_options {
            term.split_with_options(&pane, dir, SpawnOptions { cwd, env: env_map })
                .await
        } else {
            term.split(&pane, dir).await
        };
        match result {
            Ok(new_pane) => Ok(ToolResult::text(format!("new pane: {new_pane}"))),
            Err(e) => Ok(ToolResult::error(format!("terminal: {e}"))),
        }
    }
}

pub struct TerminalReadOutputTool {
    hub: Hub,
}
impl TerminalReadOutputTool {
    pub fn new(hub: Hub) -> Self {
        Self { hub }
    }
}
#[async_trait]
impl McpTool for TerminalReadOutputTool {
    fn name(&self) -> &'static str {
        "terminal_read_output"
    }
    fn schema(&self) -> ToolSchema {
        ToolSchema {
            name: self.name().into(),
            description: "Read recent output from a terminal pane/session. Useful after \
                 terminal_send_keys to inspect command results without switching UI focus."
                .into(),
            input_schema: json!({
                "type": "object",
                "properties": {
                    "pane": { "type": "string", "description": "Pane id from terminal_list." },
                    "last_n_lines": { "type": "integer", "minimum": 1, "maximum": 2000, "default": 80 }
                },
                "required": ["pane"]
            }),
        }
    }
    async fn execute(&self, args: Value, _ctx: &ToolContext) -> Result<ToolResult> {
        let term = match &self.hub.terminal {
            Some(t) => t.clone(),
            None => return Ok(ToolResult::error("no terminal backend configured")),
        };
        let pane = match args.get("pane").and_then(|v| v.as_str()) {
            Some(s) => PaneId::from_raw(s.to_string()),
            None => return Ok(ToolResult::error("missing 'pane'")),
        };
        let lines = args
            .get("last_n_lines")
            .and_then(|v| v.as_u64())
            .unwrap_or(80)
            .clamp(1, 2000) as usize;
        let caps = term.capabilities();
        if !caps.can_read_output {
            let payload = json!({
                "error": "terminal_read_output_unsupported",
                "backend": term.id(),
                "capabilities": caps,
                "message": "This terminal backend cannot read scrollback in the current environment.",
                "alternatives": [
                    "Use kitty, wezterm, or zellij for CLI scrollback via agent-bridge.",
                    "For Warp: enable the in-process bridge IPC socket (see AGENT_BRIDGE_WARP_IPC_SOCKET)."
                ]
            });
            return Ok(ToolResult::error(
                serde_json::to_string_pretty(&payload).unwrap_or_else(|_| payload.to_string()),
            ));
        }
        match term.read_output(&pane, lines).await {
            Ok(output_lines) => Ok(ToolResult::json_text(&json!({
                "pane": pane.as_str(),
                "backend": term.id(),
                "requested_lines": lines,
                "returned_lines": output_lines.len(),
                "lines": output_lines
            }))),
            Err(e) => Ok(ToolResult::error(format!("terminal: {e}"))),
        }
    }
}

// ===========================================================================
//                            terminal_resize tool
// ===========================================================================

pub struct TerminalResizeTool {
    hub: Hub,
}
impl TerminalResizeTool {
    pub fn new(hub: Hub) -> Self {
        Self { hub }
    }
}
#[async_trait]
impl McpTool for TerminalResizeTool {
    fn name(&self) -> &'static str {
        "terminal_resize"
    }
    fn schema(&self) -> ToolSchema {
        ToolSchema {
            name: self.name().into(),
            description: "Resize a terminal pane / PTY to rows × cols. Triggers SIGWINCH \
                 on the child so full-screen apps (vim, less, man, htop) re-flow. Backends \
                 that don't own the PTY (e.g. WarpBackend in URL-scheme mode) reject with \
                 'not supported'."
                .into(),
            input_schema: json!({
                "type": "object",
                "properties": {
                    "pane": { "type": "string", "description": "Pane id from terminal_list." },
                    "rows": { "type": "integer", "minimum": 1, "maximum": 500,
                              "description": "New row count (vertical lines)." },
                    "cols": { "type": "integer", "minimum": 1, "maximum": 1000,
                              "description": "New column count (horizontal width)." }
                },
                "required": ["pane", "rows", "cols"]
            }),
        }
    }
    async fn execute(&self, args: Value, _ctx: &ToolContext) -> Result<ToolResult> {
        if let Err(e) = self.hub.security.check(Cap::TerminalWrite) {
            return Ok(ToolResult::error(e));
        }
        let term = match &self.hub.terminal {
            Some(t) => t.clone(),
            None => return Ok(ToolResult::error("no terminal backend configured")),
        };
        let pane = match args.get("pane").and_then(|v| v.as_str()) {
            Some(s) => PaneId::from_raw(s.to_string()),
            None => return Ok(ToolResult::error("missing 'pane'")),
        };
        let rows = match args.get("rows").and_then(|v| v.as_u64()) {
            Some(r) => r.clamp(1, 500) as u16,
            None => return Ok(ToolResult::error("missing 'rows'")),
        };
        let cols = match args.get("cols").and_then(|v| v.as_u64()) {
            Some(c) => c.clamp(1, 1000) as u16,
            None => return Ok(ToolResult::error("missing 'cols'")),
        };
        match term.resize(&pane, rows, cols).await {
            Ok(()) => Ok(ToolResult::json_text(&json!({
                "pane": pane.as_str(),
                "backend": term.id(),
                "rows": rows,
                "cols": cols,
                "ok": true
            }))),
            Err(e) => Ok(ToolResult::error(format!("terminal: {e}"))),
        }
    }
}

// ===========================================================================
//                              shell_exec tool
// ===========================================================================

const SHELL_EXEC_TRUNCATE_BYTES: usize = 131_072; // 128 KB

pub struct ShellExecTool {
    hub: Hub,
}

impl ShellExecTool {
    pub fn new(hub: Hub) -> Self {
        Self { hub }
    }
}

#[async_trait]
impl McpTool for ShellExecTool {
    fn name(&self) -> &'static str {
        "shell_exec"
    }
    fn schema(&self) -> ToolSchema {
        ToolSchema {
            name: self.name().into(),
            description: "Run a shell command synchronously; returns exit code, stdout, \
                 stderr, wall-clock duration. Unlike terminal_send_keys this captures \
                 output directly — no PTY needed. stdout/stderr truncated at 128 KB. \
                 Default timeout 30 s, max 300 s."
                .into(),
            input_schema: json!({
                "type": "object",
                "properties": {
                    "cmd": {
                        "type": "string",
                        "description": "Shell command to run (executed via sh -c)."
                    },
                    "cwd": {
                        "type": "string",
                        "description": "Working directory. Defaults to the agent-bridge process cwd."
                    },
                    "timeout_ms": {
                        "type": "integer",
                        "minimum": 1000,
                        "maximum": 300000,
                        "default": 30000,
                        "description": "Milliseconds before the process is killed."
                    },
                    "env": {
                        "type": "object",
                        "description": "Extra environment variables to inject (string keys + values).",
                        "additionalProperties": { "type": "string" }
                    }
                },
                "required": ["cmd"]
            }),
        }
    }
    async fn execute(&self, args: Value, _ctx: &ToolContext) -> Result<ToolResult> {
        if let Err(e) = self.hub.security.check(Cap::ShellExec) {
            return Ok(ToolResult::error(e));
        }
        let cmd = match args.get("cmd").and_then(|v| v.as_str()) {
            Some(s) if !s.is_empty() => s.to_string(),
            _ => return Ok(ToolResult::error("missing or empty 'cmd'")),
        };
        let timeout_max = self.hub.security.shell_exec_timeout_max_ms;
        let timeout_ms = args
            .get("timeout_ms")
            .and_then(|v| v.as_u64())
            .unwrap_or(30_000)
            .clamp(1_000, timeout_max);

        let mut child = {
            let mut builder = TokioCommand::new("sh");
            builder.arg("-c").arg(&cmd);
            builder.stdout(std::process::Stdio::piped());
            builder.stderr(std::process::Stdio::piped());
            if let Some(cwd) = args.get("cwd").and_then(|v| v.as_str()) {
                builder.current_dir(cwd);
            }
            if let Some(env_map) = args.get("env").and_then(|v| v.as_object()) {
                for (k, v) in env_map {
                    if let Some(val) = v.as_str() {
                        builder.env(k, val);
                    }
                }
            }
            match builder.spawn() {
                Ok(c) => c,
                Err(e) => return Ok(ToolResult::error(format!("spawn failed: {e}"))),
            }
        };

        let started = Instant::now();
        let deadline = Duration::from_millis(timeout_ms);

        // Drain stdout + stderr in background tasks so the process doesn't block on full pipes.
        use tokio::io::AsyncReadExt as _;
        let mut stdout_pipe = child.stdout.take().expect("stdout piped");
        let mut stderr_pipe = child.stderr.take().expect("stderr piped");
        let stdout_task = tokio::spawn(async move {
            let mut buf = Vec::new();
            let _ = stdout_pipe.read_to_end(&mut buf).await;
            buf
        });
        let stderr_task = tokio::spawn(async move {
            let mut buf = Vec::new();
            let _ = stderr_pipe.read_to_end(&mut buf).await;
            buf
        });

        let timed_out = tokio::time::timeout(deadline, child.wait()).await;
        let duration_ms = started.elapsed().as_millis() as u64;

        let exit_code = match timed_out {
            Err(_) => {
                child.start_kill().ok();
                stdout_task.abort();
                stderr_task.abort();
                return Ok(ToolResult::json_text(&json!({
                    "exit_code": -1,
                    "stdout": "",
                    "stderr": format!("killed after {timeout_ms} ms timeout"),
                    "duration_ms": duration_ms,
                    "truncated": false
                })));
            }
            Ok(Err(e)) => return Ok(ToolResult::error(format!("wait failed: {e}"))),
            Ok(Ok(status)) => status.code().unwrap_or(-1),
        };

        let stdout_bytes = stdout_task.await.unwrap_or_default();
        let stderr_bytes = stderr_task.await.unwrap_or_default();
        let (stdout_str, stdout_truncated) = lossy_truncate(&stdout_bytes);
        let (stderr_str, stderr_truncated) = lossy_truncate(&stderr_bytes);

        Ok(ToolResult::json_text(&json!({
            "exit_code": exit_code,
            "stdout": stdout_str,
            "stderr": stderr_str,
            "duration_ms": duration_ms,
            "truncated": stdout_truncated || stderr_truncated
        })))
    }
}

fn lossy_truncate(bytes: &[u8]) -> (String, bool) {
    if bytes.len() <= SHELL_EXEC_TRUNCATE_BYTES {
        (String::from_utf8_lossy(bytes).into_owned(), false)
    } else {
        let s = String::from_utf8_lossy(&bytes[..SHELL_EXEC_TRUNCATE_BYTES]).into_owned();
        (
            format!(
                "{s}\n[... truncated at {} KB]",
                SHELL_EXEC_TRUNCATE_BYTES / 1024
            ),
            true,
        )
    }
}

// ===========================================================================
//                        terminal_read_blocks tool
// ===========================================================================

pub struct TerminalReadBlocksTool {
    hub: Hub,
}
impl TerminalReadBlocksTool {
    pub fn new(hub: Hub) -> Self {
        Self { hub }
    }
}
#[async_trait]
impl McpTool for TerminalReadBlocksTool {
    fn name(&self) -> &'static str {
        "terminal_read_blocks"
    }
    fn schema(&self) -> ToolSchema {
        ToolSchema {
            name: self.name().into(),
            description: "Return structured blocks from a Warp terminal session. Each \
                block: command text, output, exit code, execution state. More reliable \
                than terminal_read_output for command→output mapping. Available only \
                with Warp IPC bridge connected."
                .into(),
            input_schema: json!({
                "type": "object",
                "properties": {
                    "pane": {
                        "type": "string",
                        "description": "Pane/session id from terminal_list."
                    },
                    "limit": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 200,
                        "default": 20,
                        "description": "Maximum number of most-recent blocks to return."
                    },
                    "since_block": {
                        "type": "integer",
                        "minimum": 0,
                        "description": "If set, only return blocks with 0-based index >= since_block (skip older blocks)."
                    },
                    "output_max_chars": {
                        "type": "integer",
                        "minimum": 0,
                        "maximum": 65536,
                        "default": 4000,
                        "description": "Truncate each block's output to this many characters (default 4000). Set to 0 to omit output entirely."
                    }
                },
                "required": ["pane"]
            }),
        }
    }
    async fn execute(&self, args: Value, _ctx: &ToolContext) -> Result<ToolResult> {
        let term = match &self.hub.terminal {
            Some(t) => t.clone(),
            None => return Ok(ToolResult::error("no terminal backend configured")),
        };
        let pane = match args.get("pane").and_then(|v| v.as_str()) {
            Some(s) => PaneId::from_raw(s.to_string()),
            None => return Ok(ToolResult::error("missing 'pane'")),
        };
        let limit = args
            .get("limit")
            .and_then(|v| v.as_u64())
            .unwrap_or(20)
            .clamp(1, 200) as usize;
        let since_block = args.get("since_block").and_then(|v| v.as_u64()).map(|v| v as usize);
        let output_max = args
            .get("output_max_chars")
            .and_then(|v| v.as_u64())
            .unwrap_or(4000)
            .min(65536) as usize;

        match term.read_blocks(&pane, limit, since_block).await {
            Ok(blocks) => {
                let backend_id = term.id().to_string();
                let count = blocks.len();
                let blocks_json: Vec<serde_json::Value> = blocks
                    .into_iter()
                    .map(|b: TerminalBlock| {
                        let (out, truncated) = if output_max == 0 {
                            (String::new(), false)
                        } else {
                            let byte_end = b.output
                                .char_indices()
                                .nth(output_max)
                                .map(|(i, _)| i)
                                .unwrap_or(b.output.len());
                            if byte_end < b.output.len() {
                                (b.output[..byte_end].to_string(), true)
                            } else {
                                (b.output, false)
                            }
                        };
                        let mut v = json!({
                            "block_id": b.block_id,
                            "command": b.command,
                            "output": out,
                            "exit_code": b.exit_code,
                            "state": b.state,
                            "is_running": b.is_running,
                        });
                        if let Some(ms) = b.start_ms {
                            v["start_ms"] = json!(ms);
                        }
                        if let Some(ms) = b.end_ms {
                            v["end_ms"] = json!(ms);
                            if let Some(start) = b.start_ms {
                                v["duration_ms"] = json!(ms - start);
                            }
                        }
                        if truncated {
                            v["output_truncated"] = json!(true);
                        }
                        v
                    })
                    .collect();
                Ok(ToolResult::json_text(&json!({
                    "pane": pane.as_str(),
                    "backend": backend_id,
                    "count": count,
                    "blocks": blocks_json,
                })))
            }
            Err(e) => Ok(ToolResult::error(format!("terminal_read_blocks: {e}"))),
        }
    }
}

// ===========================================================================
//                              browser tools
// ===========================================================================

pub struct BrowserNavigateTool {
    hub: Hub,
}
impl BrowserNavigateTool {
    pub fn new(hub: Hub) -> Self {
        Self { hub }
    }
}
#[async_trait]
impl McpTool for BrowserNavigateTool {
    fn name(&self) -> &'static str {
        "browser_navigate"
    }
    fn schema(&self) -> ToolSchema {
        ToolSchema {
            name: self.name().into(),
            description: "Open a URL in the agent-bridge browser and return a page id you can \
                 pass to other browser_* tools. The browser is launched lazily on first \
                 call (headed by default; set AGENT_BRIDGE_HEADLESS=1 for headless)."
                .into(),
            input_schema: json!({
                "type": "object",
                "properties": { "url": { "type": "string", "description": "Absolute URL." } },
                "required": ["url"]
            }),
        }
    }
    async fn execute(&self, args: Value, _ctx: &ToolContext) -> Result<ToolResult> {
        if let Err(e) = self.hub.security.check(Cap::Browser) {
            return Ok(ToolResult::error(e));
        }
        let b = match &self.hub.browser {
            Some(b) => b.clone(),
            None => return Ok(ToolResult::error("no browser backend configured")),
        };
        let url = match args.get("url").and_then(|v| v.as_str()) {
            Some(u) => u,
            None => return Ok(ToolResult::error("missing 'url'")),
        };
        match b.navigate(url).await {
            Ok(pid) => Ok(ToolResult::text(format!("page: {pid}"))),
            Err(e) => Ok(ToolResult::error(format!("browser: {e}"))),
        }
    }
}

pub struct BrowserEvalTool {
    hub: Hub,
}
impl BrowserEvalTool {
    pub fn new(hub: Hub) -> Self {
        Self { hub }
    }
}
#[async_trait]
impl McpTool for BrowserEvalTool {
    fn name(&self) -> &'static str {
        "browser_eval"
    }
    fn schema(&self) -> ToolSchema {
        ToolSchema {
            name: self.name().into(),
            description: "Evaluate JavaScript in the given page's main frame and return the \
                 resulting JSON value. The expression's last value is returned (wrap in \
                 `(() => { ... })()` for multi-statement code)."
                .into(),
            input_schema: json!({
                "type": "object",
                "properties": {
                    "page": { "type": "string", "description": "Page id from browser_navigate." },
                    "js":   { "type": "string", "description": "JavaScript expression." }
                },
                "required": ["page", "js"]
            }),
        }
    }
    async fn execute(&self, args: Value, _ctx: &ToolContext) -> Result<ToolResult> {
        let b = match &self.hub.browser {
            Some(b) => b.clone(),
            None => return Ok(ToolResult::error("no browser backend configured")),
        };
        let page = match args.get("page").and_then(|v| v.as_str()) {
            Some(s) => PageId::from_raw(s.to_string()),
            None => return Ok(ToolResult::error("missing 'page'")),
        };
        let js = args.get("js").and_then(|v| v.as_str()).unwrap_or("");
        match b.eval(&page, js).await {
            Ok(v) => Ok(ToolResult::json_text(&v)),
            Err(e) => Ok(ToolResult::error(format!("browser: {e}"))),
        }
    }
}

pub struct BrowserSnapshotTool {
    hub: Hub,
}
impl BrowserSnapshotTool {
    pub fn new(hub: Hub) -> Self {
        Self { hub }
    }
}
#[async_trait]
impl McpTool for BrowserSnapshotTool {
    fn name(&self) -> &'static str {
        "browser_snapshot"
    }
    fn schema(&self) -> ToolSchema {
        ToolSchema {
            name: self.name().into(),
            description: "Return the page's accessibility tree (role/name/value + children). \
                 Far cheaper than a screenshot for letting the agent reason about page \
                 structure: the same content takes 10–50× fewer tokens than a PNG."
                .into(),
            input_schema: json!({
                "type": "object",
                "properties": { "page": { "type": "string" } },
                "required": ["page"]
            }),
        }
    }
    async fn execute(&self, args: Value, _ctx: &ToolContext) -> Result<ToolResult> {
        let b = match &self.hub.browser {
            Some(b) => b.clone(),
            None => return Ok(ToolResult::error("no browser backend configured")),
        };
        let page = match args.get("page").and_then(|v| v.as_str()) {
            Some(s) => PageId::from_raw(s.to_string()),
            None => return Ok(ToolResult::error("missing 'page'")),
        };
        match b.snapshot_a11y(&page).await {
            Ok(tree) => Ok(ToolResult::json_text(
                &serde_json::to_value(tree).unwrap_or(Value::Null),
            )),
            Err(e) => Ok(ToolResult::error(format!("browser: {e}"))),
        }
    }
}

pub struct BrowserClickTool {
    hub: Hub,
}
impl BrowserClickTool {
    pub fn new(hub: Hub) -> Self {
        Self { hub }
    }
}
#[async_trait]
impl McpTool for BrowserClickTool {
    fn name(&self) -> &'static str {
        "browser_click"
    }
    fn schema(&self) -> ToolSchema {
        ToolSchema {
            name: self.name().into(),
            description: "Click the first DOM element matching the given CSS selector.".into(),
            input_schema: json!({
                "type": "object",
                "properties": {
                    "page":     { "type": "string" },
                    "selector": { "type": "string", "description": "CSS selector." }
                },
                "required": ["page", "selector"]
            }),
        }
    }
    async fn execute(&self, args: Value, _ctx: &ToolContext) -> Result<ToolResult> {
        let b = match &self.hub.browser {
            Some(b) => b.clone(),
            None => return Ok(ToolResult::error("no browser backend configured")),
        };
        let page = match args.get("page").and_then(|v| v.as_str()) {
            Some(s) => PageId::from_raw(s.to_string()),
            None => return Ok(ToolResult::error("missing 'page'")),
        };
        let sel = args.get("selector").and_then(|v| v.as_str()).unwrap_or("");
        if sel.is_empty() {
            return Ok(ToolResult::error("missing 'selector'"));
        }
        match b.click(&page, sel).await {
            Ok(()) => Ok(ToolResult::text(format!("clicked {sel}"))),
            Err(e) => Ok(ToolResult::error(format!("browser: {e}"))),
        }
    }
}

pub struct BrowserScreenshotTool {
    hub: Hub,
}
impl BrowserScreenshotTool {
    pub fn new(hub: Hub) -> Self {
        Self { hub }
    }
}
#[async_trait]
impl McpTool for BrowserScreenshotTool {
    fn name(&self) -> &'static str {
        "browser_screenshot"
    }
    fn schema(&self) -> ToolSchema {
        ToolSchema {
            name: self.name().into(),
            description: "Capture a full-page PNG screenshot. Default mode writes the PNG \
                 to /tmp and returns the file path (cheap, suitable for storage / \
                 passing to other tools). Set `inline=true` to return the image as \
                 a real MCP image content block — Claude renders it directly into \
                 context (token-heavy, ~1k tokens per 100 KB; only use when you \
                 actually need to *see* the page)."
                .into(),
            input_schema: json!({
                "type": "object",
                "properties": {
                    "page":   { "type": "string" },
                    "path":   { "type": "string", "description": "Optional output path (file mode only)." },
                    "inline": {
                        "type": "boolean",
                        "default": false,
                        "description": "If true, return the PNG as an MCP image block instead of writing a file."
                    }
                },
                "required": ["page"]
            }),
        }
    }
    async fn execute(&self, args: Value, _ctx: &ToolContext) -> Result<ToolResult> {
        let b = match &self.hub.browser {
            Some(b) => b.clone(),
            None => return Ok(ToolResult::error("no browser backend configured")),
        };
        let page = match args.get("page").and_then(|v| v.as_str()) {
            Some(s) => PageId::from_raw(s.to_string()),
            None => return Ok(ToolResult::error("missing 'page'")),
        };
        let png = match b.screenshot(&page).await {
            Ok(p) => p,
            Err(e) => return Ok(ToolResult::error(format!("browser: {e}"))),
        };
        let inline = args
            .get("inline")
            .and_then(|v| v.as_bool())
            .unwrap_or(false);
        if inline {
            let b64 = general_purpose::STANDARD.encode(&png);
            let caption = format!("inline screenshot — {} bytes, image/png", png.len());
            return Ok(ToolResult::image_with_caption(b64, "image/png", caption));
        }
        let path = args
            .get("path")
            .and_then(|v| v.as_str())
            .map(|s| s.to_string())
            .unwrap_or_else(|| {
                std::env::temp_dir()
                    .join(format!("agent-bridge-{page}.png"))
                    .to_string_lossy()
                    .into_owned()
            });
        if let Err(e) = tokio::fs::write(&path, &png).await {
            return Ok(ToolResult::error(format!("write {path}: {e}")));
        }
        Ok(ToolResult::text(format!(
            "wrote {} bytes → {path}",
            png.len()
        )))
    }
}

pub struct BrowserExtractTextTool {
    hub: Hub,
}
impl BrowserExtractTextTool {
    pub fn new(hub: Hub) -> Self {
        Self { hub }
    }
}
#[async_trait]
impl McpTool for BrowserExtractTextTool {
    fn name(&self) -> &'static str {
        "browser_extract_text"
    }
    fn schema(&self) -> ToolSchema {
        ToolSchema {
            name: self.name().into(),
            description: "Return visible page text (`innerText` of the document root). \
                 Cheaper than screenshots for reading main content when layout does not matter."
                .into(),
            input_schema: json!({
                "type": "object",
                "properties": { "page": { "type": "string", "description": "Page id from browser_navigate." } },
                "required": ["page"]
            }),
        }
    }
    async fn execute(&self, args: Value, _ctx: &ToolContext) -> Result<ToolResult> {
        let b = match &self.hub.browser {
            Some(b) => b.clone(),
            None => return Ok(ToolResult::error("no browser backend configured")),
        };
        let page = match args.get("page").and_then(|v| v.as_str()) {
            Some(s) => PageId::from_raw(s.to_string()),
            None => return Ok(ToolResult::error("missing 'page'")),
        };
        match b.extract_text(&page).await {
            Ok(text) => Ok(ToolResult::json_text(&json!({
                "page": page.as_str(),
                "chars": text.len(),
                "text": text
            }))),
            Err(e) => Ok(ToolResult::error(format!("browser: {e}"))),
        }
    }
}

pub struct BrowserFillFormTool {
    hub: Hub,
}
impl BrowserFillFormTool {
    pub fn new(hub: Hub) -> Self {
        Self { hub }
    }
}
#[async_trait]
impl McpTool for BrowserFillFormTool {
    fn name(&self) -> &'static str {
        "browser_fill_form"
    }
    fn schema(&self) -> ToolSchema {
        ToolSchema {
            name: self.name().into(),
            description: "Fill the first element matching a CSS selector (sets `.value` or \
                 `textContent`) and dispatch `input`/`change` events."
                .into(),
            input_schema: json!({
                "type": "object",
                "properties": {
                    "page":     { "type": "string" },
                    "selector": { "type": "string", "description": "CSS selector." },
                    "value":    { "type": "string", "description": "Text to apply." }
                },
                "required": ["page", "selector", "value"]
            }),
        }
    }
    async fn execute(&self, args: Value, _ctx: &ToolContext) -> Result<ToolResult> {
        let b = match &self.hub.browser {
            Some(b) => b.clone(),
            None => return Ok(ToolResult::error("no browser backend configured")),
        };
        let page = match args.get("page").and_then(|v| v.as_str()) {
            Some(s) => PageId::from_raw(s.to_string()),
            None => return Ok(ToolResult::error("missing 'page'")),
        };
        let sel = args.get("selector").and_then(|v| v.as_str()).unwrap_or("");
        if sel.is_empty() {
            return Ok(ToolResult::error("missing 'selector'"));
        }
        let val = args.get("value").and_then(|v| v.as_str()).unwrap_or("");
        match b.fill_form(&page, sel, val).await {
            Ok(()) => Ok(ToolResult::json_text(&json!({
                "page": page.as_str(),
                "selector": sel,
                "status": "ok"
            }))),
            Err(e) => Ok(ToolResult::error(format!("browser: {e}"))),
        }
    }
}

pub struct AgentMessageTool {
    hub: Hub,
}
impl AgentMessageTool {
    pub fn new(hub: Hub) -> Self {
        Self { hub }
    }
}
#[async_trait]
impl McpTool for AgentMessageTool {
    fn name(&self) -> &'static str {
        "agent_message"
    }
    fn schema(&self) -> ToolSchema {
        ToolSchema {
            name: self.name().into(),
            description: "Append a JSON payload to another session's inbox (SQLite \
                 `agent_messages`). Use opaque session ids (e.g. client-supplied handles)."
                .into(),
            input_schema: json!({
                "type": "object",
                "properties": {
                    "from_session": { "type": "string", "description": "Sender session id." },
                    "to_session":   { "type": "string", "description": "Recipient session id." },
                    "payload":      { "type": "object", "description": "Arbitrary JSON object." }
                },
                "required": ["from_session", "to_session", "payload"]
            }),
        }
    }
    async fn execute(&self, args: Value, _ctx: &ToolContext) -> Result<ToolResult> {
        let store = match &self.hub.store {
            Some(s) => s.clone(),
            None => return Ok(ToolResult::error("no memory store configured")),
        };
        let from_session = match args
            .get("from_session")
            .and_then(|v| v.as_str())
            .filter(|s| !s.is_empty())
        {
            Some(s) => s.to_string(),
            None => return Ok(ToolResult::error("missing or empty 'from_session'")),
        };
        let to_session = match args
            .get("to_session")
            .and_then(|v| v.as_str())
            .filter(|s| !s.is_empty())
        {
            Some(s) => s.to_string(),
            None => return Ok(ToolResult::error("missing or empty 'to_session'")),
        };
        let payload = match args.get("payload").filter(|v| v.is_object()) {
            Some(v) => v.clone(),
            None => return Ok(ToolResult::error("missing 'payload' object")),
        };
        let id = store
            .agent_message_send(&from_session, &to_session, &payload)
            .await
            .map_err(|e| ab_core::Error::Backend(format!("agent_message_send: {e}")))?;
        Ok(ToolResult::json_text(&json!({
            "status": "ok",
            "id": id,
            "from_session": from_session,
            "to_session": to_session
        })))
    }
}

pub struct AgentInboxTool {
    hub: Hub,
}
impl AgentInboxTool {
    pub fn new(hub: Hub) -> Self {
        Self { hub }
    }
}
#[async_trait]
impl McpTool for AgentInboxTool {
    fn name(&self) -> &'static str {
        "agent_inbox"
    }
    fn schema(&self) -> ToolSchema {
        ToolSchema {
            name: self.name().into(),
            description:
                "Fetch inbox rows for `to_session`, optionally after `since_id` \
                 (message id cursor), optionally unread-only. Ordered by id ascending; limit 1–500."
                    .into(),
            input_schema: json!({
                "type": "object",
                "properties": {
                    "to_session": {
                        "type": "string",
                        "description": "Recipient session id (same namespace as agent_message)."
                    },
                    "since_id": {
                        "type": "integer",
                        "description": "Only rows with id greater than this (exclusive cursor)."
                    },
                    "unread_only": {
                        "type": "boolean",
                        "default": false,
                        "description": "If true, only rows with read=0 (column reserved for future use)."
                    },
                    "limit": {
                        "type": "integer",
                        "default": 50,
                        "description": "Max rows (clamped 1–500)."
                    }
                },
                "required": ["to_session"]
            }),
        }
    }
    async fn execute(&self, args: Value, _ctx: &ToolContext) -> Result<ToolResult> {
        let store = match &self.hub.store {
            Some(s) => s.clone(),
            None => return Ok(ToolResult::error("no memory store configured")),
        };
        let to_session = match args
            .get("to_session")
            .and_then(|v| v.as_str())
            .filter(|s| !s.is_empty())
        {
            Some(s) => s.to_string(),
            None => return Ok(ToolResult::error("missing or empty 'to_session'")),
        };
        let since_id = args.get("since_id").and_then(|v| v.as_i64());
        let unread_only = args
            .get("unread_only")
            .and_then(|v| v.as_bool())
            .unwrap_or(false);
        let limit = args
            .get("limit")
            .and_then(|v| v.as_u64())
            .unwrap_or(50)
            .clamp(1, 500) as u32;
        let rows = store
            .agent_inbox_fetch(&to_session, since_id, unread_only, limit)
            .await
            .map_err(|e| ab_core::Error::Backend(format!("agent_inbox_fetch: {e}")))?;
        Ok(ToolResult::json_text(&json!({
            "to_session": to_session,
            "since_id": since_id,
            "count": rows.len(),
            "messages": rows
        })))
    }
}

// ===========================================================================
//                       forum (v18) — shared whiteboard
// ===========================================================================

pub struct ForumPostTool {
    hub: Hub,
}
impl ForumPostTool {
    pub fn new(hub: Hub) -> Self {
        Self { hub }
    }
}
#[async_trait]
impl McpTool for ForumPostTool {
    fn name(&self) -> &'static str {
        "forum_post"
    }
    fn schema(&self) -> ToolSchema {
        ToolSchema {
            name: self.name().into(),
            description:
                "Append a post to a thread (provide `thread_id`) or create a new thread \
                 (provide `board` + `title`, omit `thread_id`). `author` is REQUIRED — \
                 use a stable session id so multi-process collaboration stays readable. \
                 `kind` ∈ {msg, finding, question, decision, reply}. `refs` is opaque \
                 JSON, conventionally `{memory_keys:[...], files:[...], parent_post_id:N}`. \
                 Set `peer: \"host:port\"` to post into a remote tailnet peer's forum \
                 instead of local; omit for local-only."
                    .into(),
            input_schema: json!({
                "type": "object",
                "properties": {
                    "thread_id":  { "type": "integer", "description": "Existing thread id; omit to create a new thread." },
                    "board":      { "type": "string",  "description": "Board name (required when creating a new thread). E.g. 'general', 'design', 'incidents'." },
                    "title":      { "type": "string",  "description": "Thread title (required when creating)." },
                    "author":     { "type": "string",  "description": "Author session id (REQUIRED, non-empty)." },
                    "kind":       { "type": "string",  "default": "msg", "description": "msg | finding | question | decision | reply" },
                    "body":       { "type": "string",  "description": "Post body (required, non-empty)." },
                    "refs":       { "type": "object",  "description": "Opaque JSON — e.g. {memory_keys:[...], files:[...], parent_post_id:N}." },
                    "tags":       { "type": "array",   "items": {"type": "string"}, "description": "Tags applied when creating a new thread." },
                    "peer":       { "type": "string",  "description": "Optional tailnet peer host:port; if set, post via that daemon-http instead of local. (v20)" }
                },
                "required": ["author", "body"]
            }),
        }
    }
    async fn execute(&self, args: Value, _ctx: &ToolContext) -> Result<ToolResult> {
        let thread_id = args.get("thread_id").and_then(|v| v.as_i64());
        let board = args.get("board").and_then(|v| v.as_str());
        let title = args.get("title").and_then(|v| v.as_str());
        let author = match args
            .get("author")
            .and_then(|v| v.as_str())
            .filter(|s| !s.trim().is_empty())
        {
            Some(s) => s,
            None => return Ok(ToolResult::error("missing or empty 'author'")),
        };
        let kind = args.get("kind").and_then(|v| v.as_str()).unwrap_or("msg");
        let body = match args.get("body").and_then(|v| v.as_str()) {
            Some(s) if !s.trim().is_empty() => s,
            _ => return Ok(ToolResult::error("missing or empty 'body'")),
        };
        let refs = args.get("refs").cloned();
        let tags: Option<Vec<String>> = args
            .get("tags")
            .and_then(|v| v.as_array())
            .map(|arr| {
                arr.iter()
                    .filter_map(|v| v.as_str().map(|s| s.to_string()))
                    .collect()
            });
        let peer = args
            .get("peer")
            .and_then(|v| v.as_str())
            .filter(|s| !s.is_empty());

        if let Some(p) = peer {
            // Remote write — daemon owns the SQLite WAL on its node.
            let req = crate::peer_client::ForumPostRequest {
                author,
                body,
                thread_id,
                board,
                title,
                kind: Some(kind),
                tags: tags.as_deref(),
                refs: refs.as_ref(),
            };
            let v = crate::peer_client::forum_post(p, req)
                .await
                .map_err(|e| ab_core::Error::Backend(format!("forum_post peer: {e}")))?;
            return Ok(ToolResult::json_text(&json!({
                "status": v.get("status").cloned().unwrap_or(json!("ok")),
                "thread_id": v.get("thread_id"),
                "post_id": v.get("post_id"),
                "created_thread": v.get("created_thread"),
                "peer": peer,
            })));
        }

        let store = match &self.hub.store {
            Some(s) => s.clone(),
            None => return Ok(ToolResult::error("no memory store configured")),
        };
        let outcome = store
            .forum_post(
                thread_id,
                board,
                title,
                author,
                kind,
                body,
                refs.as_ref(),
                tags.as_deref(),
            )
            .await
            .map_err(|e| ab_core::Error::Backend(format!("forum_post: {e}")))?;
        Ok(ToolResult::json_text(&json!({
            "status": "ok",
            "thread_id": outcome.thread_id,
            "post_id": outcome.post_id,
            "created_thread": outcome.created_thread
        })))
    }
}

pub struct ForumReadTool {
    hub: Hub,
}
impl ForumReadTool {
    pub fn new(hub: Hub) -> Self {
        Self { hub }
    }
}
#[async_trait]
impl McpTool for ForumReadTool {
    fn name(&self) -> &'static str {
        "forum_read"
    }
    fn schema(&self) -> ToolSchema {
        ToolSchema {
            name: self.name().into(),
            description:
                "Fetch posts from a thread (set `thread_id`) or across a board \
                 (set `board`). Posts are ordered by id ASC; use `since_post_id` \
                 as an exclusive cursor. When `unread_for` is set, the cursor is \
                 inferred from this session's subscription (thread > board) and \
                 the cursor is auto-advanced after the read. Limit clamped 1–500.\n\n\
                 IMPORTANT — auto-advance is scope-symmetric: a thread-scoped read \
                 only advances a *thread* subscription cursor; it will NOT touch a \
                 board-level cursor (because that would wrongly mark unread posts in \
                 sibling threads as seen). If you want unread tracking on a thread, \
                 call `forum_subscribe` with scope_kind='thread'. Board subscriptions \
                 are best for casual lurking; thread subscriptions for active \
                 follow-along.\n\n\
                 Set `peer: \"host:port\"` to read from a remote tailnet peer's \
                 daemon-http; omit for local-only. NOTE: `unread_for` cursor advance \
                 is local-only and is silently ignored when `peer` is set (the \
                 remote daemon doesn't carry your subscription state)."
                    .into(),
            input_schema: json!({
                "type": "object",
                "properties": {
                    "thread_id":     { "type": "integer", "description": "Read posts in this thread." },
                    "board":         { "type": "string",  "description": "Read posts across this board (used when thread_id is absent)." },
                    "since_post_id": { "type": "integer", "description": "Exclusive cursor — only posts with id > this." },
                    "unread_for":    { "type": "string",  "description": "Session id; reads from that session's subscription cursor and advances it. (local-only)" },
                    "limit":         { "type": "integer", "default": 50, "description": "Max rows (1–500)." },
                    "peer":          { "type": "string",  "description": "Optional tailnet peer host:port; if set, query that daemon-http instead of local. (v20)" }
                }
            }),
        }
    }
    async fn execute(&self, args: Value, _ctx: &ToolContext) -> Result<ToolResult> {
        let thread_id = args.get("thread_id").and_then(|v| v.as_i64());
        let board = args.get("board").and_then(|v| v.as_str());
        if thread_id.is_none() && board.map(|s| s.is_empty()).unwrap_or(true) {
            return Ok(ToolResult::error(
                "provide at least one of 'thread_id' or 'board'",
            ));
        }
        let since_post_id = args.get("since_post_id").and_then(|v| v.as_i64());
        let unread_for = args
            .get("unread_for")
            .and_then(|v| v.as_str())
            .filter(|s| !s.is_empty());
        let limit = args
            .get("limit")
            .and_then(|v| v.as_u64())
            .unwrap_or(50)
            .clamp(1, 500) as u32;
        let peer = args
            .get("peer")
            .and_then(|v| v.as_str())
            .filter(|s| !s.is_empty());

        let posts = if let Some(p) = peer {
            // Drop unread_for when going remote — cursor state is per-device.
            crate::peer_client::forum_read(p, thread_id, board, since_post_id, None, limit)
                .await
                .map_err(|e| ab_core::Error::Backend(format!("forum_read peer: {e}")))?
        } else {
            let store = match &self.hub.store {
                Some(s) => s.clone(),
                None => return Ok(ToolResult::error("no memory store configured")),
            };
            store
                .forum_read(thread_id, board, since_post_id, unread_for, limit)
                .await
                .map_err(|e| ab_core::Error::Backend(format!("forum_read: {e}")))?
        };

        let next_cursor = posts.last().map(|p| p.id);
        Ok(ToolResult::json_text(&json!({
            "thread_id": thread_id,
            "board": board,
            "count": posts.len(),
            "next_cursor": next_cursor,
            "posts": posts,
            "peer": peer
        })))
    }
}

pub struct ForumSubscribeTool {
    hub: Hub,
}
impl ForumSubscribeTool {
    pub fn new(hub: Hub) -> Self {
        Self { hub }
    }
}
#[async_trait]
impl McpTool for ForumSubscribeTool {
    fn name(&self) -> &'static str {
        "forum_subscribe"
    }
    fn schema(&self) -> ToolSchema {
        ToolSchema {
            name: self.name().into(),
            description:
                "Register `session_id`'s interest in a thread or board. Idempotent: \
                 re-subscribing keeps the existing `last_seen_post_id` unless `reset=true`. \
                 `scope_kind` ∈ {thread, board}. For threads, `scope_value` is the \
                 numeric thread id as a string; for boards, the board name.\n\n\
                 RULE OF THUMB: subscribe at the same scope you intend to read at. \
                 Board subscription = casual lurking on a whole board (unread_count \
                 in `forum_list_threads` is computed against this cursor as a backstop). \
                 Thread subscription = active follow-along on a topic; only thread-\
                 scoped reads will auto-advance this cursor.\n\n\
                 NOTE: `forum_subscribe` is local-only — subscriptions track each \
                 device's read cursor and are intentionally not synced. To follow a \
                 remote peer's thread, subscribe locally to that thread/board id."
                    .into(),
            input_schema: json!({
                "type": "object",
                "properties": {
                    "session_id":  { "type": "string", "description": "Subscriber session id (REQUIRED)." },
                    "scope_kind":  { "type": "string", "enum": ["thread", "board"] },
                    "scope_value": { "type": "string", "description": "Thread id (as string) or board name." },
                    "reset":       { "type": "boolean", "default": false, "description": "Reset cursor to 0." }
                },
                "required": ["session_id", "scope_kind", "scope_value"]
            }),
        }
    }
    async fn execute(&self, args: Value, _ctx: &ToolContext) -> Result<ToolResult> {
        let store = match &self.hub.store {
            Some(s) => s.clone(),
            None => return Ok(ToolResult::error("no memory store configured")),
        };
        let session_id = match args
            .get("session_id")
            .and_then(|v| v.as_str())
            .filter(|s| !s.is_empty())
        {
            Some(s) => s,
            None => return Ok(ToolResult::error("missing or empty 'session_id'")),
        };
        let scope_kind = match args.get("scope_kind").and_then(|v| v.as_str()) {
            Some(s) => s,
            None => return Ok(ToolResult::error("missing 'scope_kind'")),
        };
        let scope_value = match args
            .get("scope_value")
            .and_then(|v| v.as_str())
            .filter(|s| !s.is_empty())
        {
            Some(s) => s,
            None => return Ok(ToolResult::error("missing or empty 'scope_value'")),
        };
        let reset = args
            .get("reset")
            .and_then(|v| v.as_bool())
            .unwrap_or(false);

        store
            .forum_subscribe(session_id, scope_kind, scope_value, reset)
            .await
            .map_err(|e| ab_core::Error::Backend(format!("forum_subscribe: {e}")))?;
        Ok(ToolResult::json_text(&json!({
            "status": "ok",
            "session_id": session_id,
            "scope_kind": scope_kind,
            "scope_value": scope_value,
            "reset": reset
        })))
    }
}

pub struct ForumListThreadsTool {
    hub: Hub,
}
impl ForumListThreadsTool {
    pub fn new(hub: Hub) -> Self {
        Self { hub }
    }
}
#[async_trait]
impl McpTool for ForumListThreadsTool {
    fn name(&self) -> &'static str {
        "forum_list_threads"
    }
    fn schema(&self) -> ToolSchema {
        ToolSchema {
            name: self.name().into(),
            description:
                "List threads on a `board`, ordered by `last_post_at DESC`. When \
                 `unread_for` is set, each row's `unread_count` is filled relative \
                 to that session's subscription cursors (thread cursor wins over \
                 board cursor; missing cursor counts as 0). Optional `status` \
                 filter ∈ {open, resolved, archived}. Set `peer: \"host:port\"` to \
                 query a remote tailnet peer's daemon-http instead of local store; \
                 omit for local-only."
                    .into(),
            input_schema: json!({
                "type": "object",
                "properties": {
                    "board":      { "type": "string", "description": "Board name (REQUIRED)." },
                    "unread_for": { "type": "string", "description": "Session id — fills unread_count per thread." },
                    "status":     { "type": "string", "enum": ["open", "resolved", "archived"] },
                    "limit":      { "type": "integer", "default": 50, "description": "Max rows (1–500)." },
                    "peer":       { "type": "string", "description": "Optional tailnet peer host:port; if set, query that daemon-http instead of local. (v20)" }
                },
                "required": ["board"]
            }),
        }
    }
    async fn execute(&self, args: Value, _ctx: &ToolContext) -> Result<ToolResult> {
        let board = match args
            .get("board")
            .and_then(|v| v.as_str())
            .filter(|s| !s.is_empty())
        {
            Some(s) => s,
            None => return Ok(ToolResult::error("missing or empty 'board'")),
        };
        let unread_for = args
            .get("unread_for")
            .and_then(|v| v.as_str())
            .filter(|s| !s.is_empty());
        let status = args
            .get("status")
            .and_then(|v| v.as_str())
            .filter(|s| !s.is_empty());
        let limit = args
            .get("limit")
            .and_then(|v| v.as_u64())
            .unwrap_or(50)
            .clamp(1, 500) as u32;
        let peer = args
            .get("peer")
            .and_then(|v| v.as_str())
            .filter(|s| !s.is_empty());

        let threads = if let Some(p) = peer {
            crate::peer_client::forum_list_threads(p, board, unread_for, status, limit)
                .await
                .map_err(|e| ab_core::Error::Backend(format!("forum_list_threads peer: {e}")))?
        } else {
            let store = match &self.hub.store {
                Some(s) => s.clone(),
                None => return Ok(ToolResult::error("no memory store configured")),
            };
            store
                .forum_list_threads(board, unread_for, status, limit)
                .await
                .map_err(|e| ab_core::Error::Backend(format!("forum_list_threads: {e}")))?
        };
        Ok(ToolResult::json_text(&json!({
            "board": board,
            "count": threads.len(),
            "threads": threads,
            "peer": peer
        })))
    }
}

pub struct ForumSetThreadStatusTool {
    hub: Hub,
}
impl ForumSetThreadStatusTool {
    pub fn new(hub: Hub) -> Self {
        Self { hub }
    }
}
#[async_trait]
impl McpTool for ForumSetThreadStatusTool {
    fn name(&self) -> &'static str {
        "forum_set_thread_status"
    }
    fn schema(&self) -> ToolSchema {
        ToolSchema {
            name: self.name().into(),
            description:
                "Set a forum thread's lifecycle status. `status` ∈ \
                 {open, resolved, archived}. Use `resolved` when the discussion \
                 reached a conclusion (decision logged, finding actioned); \
                 `archived` when the thread is no longer relevant but kept for \
                 history. `forum_list_threads` accepts a matching `status` filter."
                    .into(),
            input_schema: json!({
                "type": "object",
                "properties": {
                    "thread_id": { "type": "integer", "description": "Numeric thread id (REQUIRED)." },
                    "status":    { "type": "string",  "enum": ["open", "resolved", "archived"] }
                },
                "required": ["thread_id", "status"]
            }),
        }
    }
    async fn execute(&self, args: Value, _ctx: &ToolContext) -> Result<ToolResult> {
        let store = match &self.hub.store {
            Some(s) => s.clone(),
            None => return Ok(ToolResult::error("no memory store configured")),
        };
        let thread_id = match args.get("thread_id").and_then(|v| v.as_i64()) {
            Some(n) if n > 0 => n,
            _ => return Ok(ToolResult::error("missing or invalid 'thread_id'")),
        };
        let status = match args
            .get("status")
            .and_then(|v| v.as_str())
            .filter(|s| !s.is_empty())
        {
            Some(s) => s,
            None => return Ok(ToolResult::error("missing or empty 'status'")),
        };
        if !matches!(status, "open" | "resolved" | "archived") {
            return Ok(ToolResult::error(
                "'status' must be one of: open, resolved, archived",
            ));
        }

        store
            .forum_set_thread_status(thread_id, status)
            .await
            .map_err(|e| ab_core::Error::Backend(format!("forum_set_thread_status: {e}")))?;
        Ok(ToolResult::json_text(&json!({
            "status": "ok",
            "thread_id": thread_id,
            "new_status": status
        })))
    }
}

// ===========================================================================
//                       presence (v19) — identity + heartbeat
// ===========================================================================

/// Resolve the canonical `node:project:role[:tag]` session id from env + args.
/// Pure helper used by both `session_identity` and the announce tool default.
fn resolve_identity(
    role: Option<&str>,
    tag: Option<&str>,
    node_arg: Option<&str>,
    project_arg: Option<&str>,
    cwd_arg: Option<&str>,
) -> (String, String, String, Option<String>, String) {
    let node = node_arg
        .map(|s| s.to_string())
        .or_else(|| std::env::var("AGENT_BRIDGE_NODE").ok())
        .unwrap_or_else(|| {
            std::fs::read_to_string("/etc/hostname")
                .map(|s| s.trim().to_string())
                .ok()
                .filter(|s| !s.is_empty())
                .or_else(|| {
                    std::process::Command::new("hostname")
                        .output()
                        .ok()
                        .and_then(|o| String::from_utf8(o.stdout).ok())
                        .map(|s| s.trim().to_string())
                        .filter(|s| !s.is_empty())
                })
                .unwrap_or_else(|| "unknown".into())
        });
    let project = project_arg
        .map(|s| s.to_string())
        .or_else(|| std::env::var("AGENT_BRIDGE_PROJECT").ok())
        .or_else(|| {
            cwd_arg
                .map(std::path::Path::new)
                .or_else(|| {
                    static EMPTY: std::sync::OnceLock<std::path::PathBuf> =
                        std::sync::OnceLock::new();
                    let _ = EMPTY.set(std::path::PathBuf::new());
                    None
                })
                .and_then(|p| {
                    p.file_name()
                        .and_then(|n| n.to_str().map(|s| s.to_string()))
                })
        })
        .or_else(|| {
            std::env::current_dir().ok().and_then(|p| {
                p.file_name()
                    .and_then(|n| n.to_str().map(|s| s.to_string()))
            })
        })
        .unwrap_or_else(|| "unknown".into());
    let role = role.unwrap_or("main").to_string();
    let tag = tag.filter(|s| !s.is_empty()).map(|s| s.to_string());
    let session_id = match &tag {
        Some(t) => format!("{node}:{project}:{role}:{t}"),
        None => format!("{node}:{project}:{role}"),
    };
    (node, project, role, tag, session_id)
}

/// Freshness window (seconds) that defines a "fresh sibling" presence row.
/// Within this window of last_heartbeat_at, we consider the canonical id
/// taken; older rows are presumed crashed/idle and the id is reusable.
const PRESENCE_FRESH_SECS: i64 = 60;

/// Render the bottom 16 bits of a u32 pid as 4 lowercase hex chars,
/// matching the convention documented in DESIGN-v19 (e.g. `7f3a`).
fn pid_tag_short(pid: u32) -> String {
    format!("{:04x}", pid & 0xffff)
}

pub struct SessionIdentityTool {
    hub: Hub,
}
impl SessionIdentityTool {
    pub fn new(hub: Hub) -> Self {
        Self { hub }
    }
}
#[async_trait]
impl McpTool for SessionIdentityTool {
    fn name(&self) -> &'static str {
        "session_identity"
    }
    fn schema(&self) -> ToolSchema {
        ToolSchema {
            name: self.name().into(),
            description:
                "Compute the canonical session id `node:project:role[:tag]` from the \
                 caller's environment + args. Auto-disambiguates by appending a \
                 short pid-derived tag when an existing fresh-heartbeat (≤ 60 s) \
                 presence row already holds the proposed id from a different \
                 process — the multi-CC sibling case. \
                 Use the result as `session_id` / `author` in agent_message, agent_inbox, \
                 forum_post, agent_presence_announce, etc. Conventions:\n\
                 • `node`     → arg | $AGENT_BRIDGE_NODE | /etc/hostname | `hostname`\n\
                 • `project`  → arg | $AGENT_BRIDGE_PROJECT | basename(cwd_arg | cwd)\n\
                 • `role`     → arg | 'main'\n\
                 • `tag`      → arg | auto-pid-suffix on collision | (omitted)\n\
                 See docs/DESIGN-v19-presence-identity.md for rationale and the \
                 Tailscale evolution path."
                    .into(),
            input_schema: json!({
                "type": "object",
                "properties": {
                    "role":    { "type": "string", "default": "main", "description": "What this CC is doing — main | explorer | reviewer | test-writer | …" },
                    "tag":     { "type": "string", "description": "Optional disambiguator when multiple instances share a role (e.g. last-4 of pid). Disables auto-tag when set." },
                    "node":    { "type": "string", "description": "Override hostname." },
                    "project": { "type": "string", "description": "Override project slug." },
                    "cwd":     { "type": "string", "description": "Caller's cwd (used to derive project default — MCP server's cwd ≠ Claude Code's)." },
                    "auto_tag": { "type": "boolean", "default": true, "description": "When true (default), append a short pid-tag if the bare id collides with a fresh sibling. Set false to keep the old pure-helper behavior." }
                }
            }),
        }
    }
    async fn execute(&self, args: Value, _ctx: &ToolContext) -> Result<ToolResult> {
        let role_arg = args.get("role").and_then(|v| v.as_str());
        let explicit_tag = args.get("tag").and_then(|v| v.as_str());
        let node_arg = args.get("node").and_then(|v| v.as_str());
        let project_arg = args.get("project").and_then(|v| v.as_str());
        let cwd_arg = args.get("cwd").and_then(|v| v.as_str());
        let auto_tag_enabled = args
            .get("auto_tag")
            .and_then(|v| v.as_bool())
            .unwrap_or(true);

        let (node, project, role, tag, session_id) =
            resolve_identity(role_arg, explicit_tag, node_arg, project_arg, cwd_arg);

        // Auto-tag only when (a) caller did not pass an explicit tag,
        // (b) caller did not opt out, and (c) a fresh presence row already
        // holds this id from a different process.
        let (final_tag, final_session_id, auto_tagged) = if explicit_tag.is_some()
            || !auto_tag_enabled
        {
            (tag, session_id, false)
        } else if let Some(store) = self.hub.store.as_ref() {
            match store.agent_presence_get(&session_id).await {
                Ok(Some(existing)) => {
                    let now = std::time::SystemTime::now()
                        .duration_since(std::time::UNIX_EPOCH)
                        .map(|d| d.as_secs() as i64)
                        .unwrap_or(0);
                    let my_pid = std::process::id();
                    let is_fresh = now - existing.last_heartbeat_at <= PRESENCE_FRESH_SECS;
                    let other_owner = existing.pid != Some(i64::from(my_pid));
                    if is_fresh && other_owner {
                        let auto = pid_tag_short(my_pid);
                        let new_id = format!("{node}:{project}:{role}:{auto}");
                        (Some(auto), new_id, true)
                    } else {
                        (tag, session_id, false)
                    }
                }
                Ok(None) => (tag, session_id, false),
                Err(_) => (tag, session_id, false),
            }
        } else {
            (tag, session_id, false)
        };

        Ok(ToolResult::json_text(&json!({
            "session_id": final_session_id,
            "node": node,
            "project": project,
            "role": role,
            "tag": final_tag,
            "auto_tagged": auto_tagged
        })))
    }
}

pub struct AgentPresenceAnnounceTool {
    hub: Hub,
}
impl AgentPresenceAnnounceTool {
    pub fn new(hub: Hub) -> Self {
        Self { hub }
    }
}
#[async_trait]
impl McpTool for AgentPresenceAnnounceTool {
    fn name(&self) -> &'static str {
        "agent_presence_announce"
    }
    fn schema(&self) -> ToolSchema {
        ToolSchema {
            name: self.name().into(),
            description:
                "Upsert this agent's presence row keyed by `session_id`. Refreshes \
                 `last_heartbeat_at` on every call, so call once on startup and \
                 periodically after (recommend every 60–120 s). On first announce, \
                 `name`, `node`, `project`, `role` are required; on later calls any \
                 omitted field keeps its prior value. Field naming aligns with \
                 Google A2A AgentCard so the row can be served as `/.well-known/\
                 agent.json` once we add a Tailscale daemon. Tip: pre-compute \
                 session_id with the `session_identity` tool."
                    .into(),
            input_schema: json!({
                "type": "object",
                "properties": {
                    "session_id":   { "type": "string", "description": "Stable identity (REQUIRED). Use session_identity to compute." },
                    "name":         { "type": "string", "description": "Human-friendly label (REQUIRED on first announce)." },
                    "description":  { "type": "string", "description": "Free text — what you're working on." },
                    "version":      { "type": "string", "description": "e.g. 'agent-bridge 0.1.0; cc 1.2.3'." },
                    "url":          { "type": "string", "description": "Reserved for daemon mode (HTTP endpoint). Leave null locally." },
                    "node":         { "type": "string", "description": "Host identity (REQUIRED on first announce)." },
                    "project":      { "type": "string", "description": "Project slug (REQUIRED on first announce)." },
                    "role":         { "type": "string", "description": "main | explorer | reviewer | … (REQUIRED on first announce)." },
                    "tag":          { "type": "string", "description": "Optional disambiguator." },
                    "cwd":          { "type": "string", "description": "Caller's cwd for context (MCP server's cwd is irrelevant)." },
                    "pid":          { "type": "integer", "description": "Caller's pid (the Claude Code process — MCP server's pid is irrelevant)." },
                    "capabilities": { "type": "object", "description": "A2A-style capability flags, e.g. {\"forum\":true,\"streaming\":false}." },
                    "skills":       { "type": "array",  "description": "A2A-style skills array, e.g. [{\"id\":\"code-review\",\"name\":\"...\",\"tags\":[...]}]." }
                },
                "required": ["session_id"]
            }),
        }
    }
    async fn execute(&self, args: Value, _ctx: &ToolContext) -> Result<ToolResult> {
        let store = match &self.hub.store {
            Some(s) => s.clone(),
            None => return Ok(ToolResult::error("no memory store configured")),
        };
        let session_id = match args
            .get("session_id")
            .and_then(|v| v.as_str())
            .filter(|s| !s.is_empty())
        {
            Some(s) => s.to_string(),
            None => return Ok(ToolResult::error("missing or empty 'session_id'")),
        };

        // Borrow lifetime gymnastics: hold owned strings + a temp Value slot.
        let name = args.get("name").and_then(|v| v.as_str());
        let description = args.get("description").and_then(|v| v.as_str());
        let version = args.get("version").and_then(|v| v.as_str());
        let url = args.get("url").and_then(|v| v.as_str());
        let node = args.get("node").and_then(|v| v.as_str());
        let project = args.get("project").and_then(|v| v.as_str());
        let role = args.get("role").and_then(|v| v.as_str());
        let tag = args.get("tag").and_then(|v| v.as_str());
        let cwd = args.get("cwd").and_then(|v| v.as_str());
        let pid = args.get("pid").and_then(|v| v.as_i64());
        let capabilities_v = args.get("capabilities").cloned();
        let skills_v = args.get("skills").cloned();

        let upsert = ab_store::AgentPresenceUpsert {
            name,
            description,
            version,
            url,
            node,
            project,
            role,
            tag,
            cwd,
            pid,
            capabilities: capabilities_v.as_ref(),
            skills: skills_v.as_ref(),
        };

        let row = store
            .agent_presence_announce(&session_id, upsert)
            .await
            .map_err(|e| ab_core::Error::Backend(format!("agent_presence_announce: {e}")))?;
        Ok(ToolResult::json_text(&json!({
            "status": "ok",
            "presence": row
        })))
    }
}

pub struct AgentPresenceListTool {
    hub: Hub,
}
impl AgentPresenceListTool {
    pub fn new(hub: Hub) -> Self {
        Self { hub }
    }
}
#[async_trait]
impl McpTool for AgentPresenceListTool {
    fn name(&self) -> &'static str {
        "agent_presence_list"
    }
    fn schema(&self) -> ToolSchema {
        ToolSchema {
            name: self.name().into(),
            description:
                "List active agents (heartbeat within `max_idle_secs` of now). Use to \
                 discover collaborators before posting in forum or sending an \
                 agent_message. Default TTL = 300 s (5 min) so a crashed CC drops off \
                 within ~5 min. Pass `max_idle_secs:0` or `include_stale:true` to see \
                 every row including stale ones. Filters by `project` and `role` so \
                 you can ask 'who's reviewing AiOT right now'. Set `peer: \"host:port\"` \
                 to list agents from a remote tailnet peer's daemon-http instead of local."
                    .into(),
            input_schema: json!({
                "type": "object",
                "properties": {
                    "project":       { "type": "string",  "description": "Filter by project slug." },
                    "role":          { "type": "string",  "description": "Filter by role." },
                    "max_idle_secs": { "type": "integer", "default": 300, "description": "Skip rows whose heartbeat is older than this. 0 = no TTL." },
                    "include_stale": { "type": "boolean", "default": false, "description": "Equivalent to max_idle_secs:0." },
                    "limit":         { "type": "integer", "default": 50, "description": "Max rows (1–500)." },
                    "peer":          { "type": "string",  "description": "Optional tailnet peer host:port; if set, query that daemon-http instead of local. (v20)" }
                }
            }),
        }
    }
    async fn execute(&self, args: Value, _ctx: &ToolContext) -> Result<ToolResult> {
        let project = args
            .get("project")
            .and_then(|v| v.as_str())
            .filter(|s| !s.is_empty());
        let role = args
            .get("role")
            .and_then(|v| v.as_str())
            .filter(|s| !s.is_empty());
        let include_stale = args
            .get("include_stale")
            .and_then(|v| v.as_bool())
            .unwrap_or(false);
        let max_idle_secs = if include_stale {
            0
        } else {
            args.get("max_idle_secs")
                .and_then(|v| v.as_i64())
                .unwrap_or(300)
        };
        let limit = args
            .get("limit")
            .and_then(|v| v.as_u64())
            .unwrap_or(50)
            .clamp(1, 500) as u32;
        let peer = args
            .get("peer")
            .and_then(|v| v.as_str())
            .filter(|s| !s.is_empty());

        let rows = if let Some(p) = peer {
            crate::peer_client::agent_presence_list(p, project, role, max_idle_secs, limit)
                .await
                .map_err(|e| ab_core::Error::Backend(format!("agent_presence_list peer: {e}")))?
        } else {
            let store = match &self.hub.store {
                Some(s) => s.clone(),
                None => return Ok(ToolResult::error("no memory store configured")),
            };
            store
                .agent_presence_list(project, role, max_idle_secs, limit)
                .await
                .map_err(|e| ab_core::Error::Backend(format!("agent_presence_list: {e}")))?
        };
        Ok(ToolResult::json_text(&json!({
            "count": rows.len(),
            "max_idle_secs": max_idle_secs,
            "agents": rows
        })))
    }
}

// ===========================================================================
//                       agent + worktree tools
// ===========================================================================

pub struct AgentSpawnTool {
    hub: Hub,
}
impl AgentSpawnTool {
    pub fn new(hub: Hub) -> Self {
        Self { hub }
    }
}
#[async_trait]
impl McpTool for AgentSpawnTool {
    fn name(&self) -> &'static str {
        "agent_spawn"
    }
    fn schema(&self) -> ToolSchema {
        ToolSchema {
            name: self.name().into(),
            description: "Spawn a sibling AI agent (one-shot). Pass prompt + cwd; runs to \
                 completion, returns session id. Pick a backend explicitly, or a policy \
                 ('cheap'=kilo, 'second_opinion'/'openai'=codex). backend takes precedence \
                 over policy; both omitted = daemon default."
                .into(),
            input_schema: json!({
                "type": "object",
                "properties": {
                    "cwd":     { "type": "string", "description": "Working directory." },
                    "prompt":  { "type": "string", "description": "Initial prompt." },
                    "env":     { "type": "object", "additionalProperties": { "type": "string" } },
                    "backend": {
                        "type": "string",
                        "description": "Explicit runtime id. Wins over 'policy' if both given.",
                        "enum": ["claude-code", "opencode", "kilo", "gemini", "codex", "auggie", "warp-oz", "oz"]
                    },
                    "policy": {
                        "type": "string",
                        "description": "Higher-level intent → backend mapping. default→claude-code, cheap→kilo, second_opinion→codex, openai→codex.",
                        "enum": ["default", "cheap", "second_opinion", "openai"]
                    },
                    "model": {
                        "type": "string",
                        "description": "Provider/model string honored by opencode/kilo/gemini/codex (e.g. 'opencode/gpt-5-nano', 'gpt-5.4')."
                    }
                },
                "required": ["cwd", "prompt"]
            }),
        }
    }
    async fn execute(&self, args: Value, _ctx: &ToolContext) -> Result<ToolResult> {
        if let Err(e) = self.hub.security.check(Cap::AgentSpawn) {
            return Ok(ToolResult::error(e));
        }
        let backend_arg = args
            .get("backend")
            .and_then(|v| v.as_str())
            .map(|s| s.to_string());
        let policy_arg = args
            .get("policy")
            .and_then(|v| v.as_str())
            .map(|s| s.to_string());
        let resolved_backend = backend_arg
            .clone()
            .or_else(|| policy_arg.as_deref().and_then(policy_to_backend).map(String::from));
        let agent = match resolve_agent_backend(&self.hub, resolved_backend.as_deref()) {
            Ok(a) => a,
            Err(e) => return Ok(ToolResult::error(e)),
        };
        let cwd = match args.get("cwd").and_then(|v| v.as_str()) {
            Some(s) => s.to_string(),
            None => return Ok(ToolResult::error("missing 'cwd'")),
        };
        let prompt = args
            .get("prompt")
            .and_then(|v| v.as_str())
            .map(|s| s.to_string());
        let env: HashMap<String, String> = args
            .get("env")
            .and_then(|v| v.as_object())
            .map(|m| {
                m.iter()
                    .filter_map(|(k, v)| v.as_str().map(|s| (k.clone(), s.to_string())))
                    .collect()
            })
            .unwrap_or_default();

        let model = args
            .get("model")
            .and_then(|v| v.as_str())
            .map(|s| s.to_string());
        let cfg = SpawnConfig {
            cwd,
            env,
            initial_prompt: prompt,
            model,
        };
        match agent.spawn(cfg).await {
            Ok(s) => Ok(ToolResult::json_text(
                &serde_json::to_value(s).unwrap_or(Value::Null),
            )),
            Err(e) => Ok(ToolResult::error(format!("agent: {e}"))),
        }
    }
}

/// Map a `policy` value to a concrete backend id. Unknown policies return
/// `None` (caller falls through to daemon default rather than erroring —
/// matches "policy ignored" semantics if MCP client sends a future value).
fn policy_to_backend(policy: &str) -> Option<&'static str> {
    match policy.trim() {
        "default" => Some("claude-code"),
        "cheap" => Some("kilo"),
        "second_opinion" | "openai" => Some("codex"),
        _ => None,
    }
}

/// Look up the agent runtime to use for a spawn call.
///
/// - If `backend` is `Some`, fetch from the registry. Unknown ids return a
///   helpful error listing what's available.
/// - If `backend` is `None`, fall back to the daemon's default (`hub.agent`).
fn resolve_agent_backend(
    hub: &Hub,
    backend: Option<&str>,
) -> std::result::Result<Arc<dyn ab_agent::AgentRuntime>, String> {
    match backend {
        Some(id) => {
            let id = id.trim();
            // `oz` and `warp-oz` are aliases for the same runtime; normalize
            // here so callers can use either spelling.
            let canonical = match id {
                "oz" => "warp-oz",
                other => other,
            };
            hub.agents
                .get(canonical)
                .cloned()
                .ok_or_else(|| {
                    let mut available: Vec<&str> =
                        hub.agents.keys().map(|s| s.as_str()).collect();
                    available.sort();
                    format!(
                        "unknown backend '{id}'; available: [{}]",
                        available.join(", ")
                    )
                })
        }
        None => hub
            .agent
            .clone()
            .ok_or_else(|| "no default agent runtime configured".to_string()),
    }
}

/// Resolve which `GitWorktreeManager` a tool call should use. If the caller
/// provided an explicit `repo` argument we bind a fresh manager to it for
/// this call only; otherwise fall back to the bridge-wide default (set by
/// AGENT_BRIDGE_REPO at startup). This lets Claude hop between repos within
/// a single session without restarting the MCP server.
fn resolve_worktree(
    hub: &Hub,
    args: &Value,
) -> std::result::Result<GitWorktreeManager, ToolResult> {
    if let Some(repo) = args.get("repo").and_then(|v| v.as_str()) {
        return Ok(GitWorktreeManager::new(PathBuf::from(repo)));
    }
    match &hub.worktree {
        Some(w) => Ok((**w).clone()),
        None => Err(ToolResult::error(
            "no 'repo' arg passed and no default worktree manager configured",
        )),
    }
}

pub struct WorktreeListTool {
    hub: Hub,
}
impl WorktreeListTool {
    pub fn new(hub: Hub) -> Self {
        Self { hub }
    }
}
#[async_trait]
impl McpTool for WorktreeListTool {
    fn name(&self) -> &'static str {
        "worktree_list"
    }
    fn schema(&self) -> ToolSchema {
        ToolSchema {
            name: self.name().into(),
            description: "List git worktrees of a repository. Pass repo for a specific \
                 checkout; otherwise uses the bridge-wide default (AGENT_BRIDGE_REPO env \
                 var, else daemon launch cwd). Lets the agent see what parallel branches \
                 are in flight."
                .into(),
            input_schema: json!({
                "type": "object",
                "properties": {
                    "repo": { "type": "string", "description": "Absolute path to the repo (optional)." }
                }
            }),
        }
    }
    async fn execute(&self, args: Value, _ctx: &ToolContext) -> Result<ToolResult> {
        let w = match resolve_worktree(&self.hub, &args) {
            Ok(w) => w,
            Err(e) => return Ok(e),
        };
        match w.list().await {
            Ok(rows) => Ok(ToolResult::json_text(
                &serde_json::to_value(rows).unwrap_or(Value::Null),
            )),
            Err(e) => Ok(ToolResult::error(format!("worktree: {e}"))),
        }
    }
}

pub struct WorktreeCreateTool {
    hub: Hub,
}
impl WorktreeCreateTool {
    pub fn new(hub: Hub) -> Self {
        Self { hub }
    }
}
#[async_trait]
impl McpTool for WorktreeCreateTool {
    fn name(&self) -> &'static str {
        "worktree_create"
    }
    fn schema(&self) -> ToolSchema {
        ToolSchema {
            name: self.name().into(),
            description: "Create a new git worktree on a fresh branch. Pass repo to target \
                 a checkout; otherwise uses the bridge-wide default. Use to try multiple \
                 approaches in parallel without polluting main. Pair with agent_spawn to \
                 launch a sibling agent there."
                .into(),
            input_schema: json!({
                "type": "object",
                "properties": {
                    "repo":   { "type": "string", "description": "Absolute path to the repo (optional)." },
                    "branch": { "type": "string" },
                    "path":   { "type": "string", "description": "Where to put the worktree dir." },
                    "base":   { "type": "string", "description": "Branch/commit to fork from. Defaults to HEAD." }
                },
                "required": ["branch", "path"]
            }),
        }
    }
    async fn execute(&self, args: Value, _ctx: &ToolContext) -> Result<ToolResult> {
        let w = match resolve_worktree(&self.hub, &args) {
            Ok(w) => w,
            Err(e) => return Ok(e),
        };
        let branch = match args.get("branch").and_then(|v| v.as_str()) {
            Some(s) => s.to_string(),
            None => return Ok(ToolResult::error("missing 'branch'")),
        };
        let path = match args.get("path").and_then(|v| v.as_str()) {
            Some(s) => PathBuf::from(s),
            None => return Ok(ToolResult::error("missing 'path'")),
        };
        let base = args.get("base").and_then(|v| v.as_str());
        match w.add(&path, &branch, base).await {
            Ok(wt) => Ok(ToolResult::json_text(
                &serde_json::to_value(wt).unwrap_or(Value::Null),
            )),
            Err(e) => Ok(ToolResult::error(format!("worktree: {e}"))),
        }
    }
}

pub struct WorktreeRemoveTool {
    hub: Hub,
}
impl WorktreeRemoveTool {
    pub fn new(hub: Hub) -> Self {
        Self { hub }
    }
}
#[async_trait]
impl McpTool for WorktreeRemoveTool {
    fn name(&self) -> &'static str {
        "worktree_remove"
    }
    fn schema(&self) -> ToolSchema {
        ToolSchema {
            name: self.name().into(),
            description: "Remove a git worktree. Pass `repo` to target any local git checkout; \
                 set `force=true` to clobber dirty working trees."
                .into(),
            input_schema: json!({
                "type": "object",
                "properties": {
                    "repo":  { "type": "string", "description": "Absolute path to the repo (optional)." },
                    "path":  { "type": "string" },
                    "force": { "type": "boolean", "default": false }
                },
                "required": ["path"]
            }),
        }
    }
    async fn execute(&self, args: Value, _ctx: &ToolContext) -> Result<ToolResult> {
        let w = match resolve_worktree(&self.hub, &args) {
            Ok(w) => w,
            Err(e) => return Ok(e),
        };
        let path = match args.get("path").and_then(|v| v.as_str()) {
            Some(s) => PathBuf::from(s),
            None => return Ok(ToolResult::error("missing 'path'")),
        };
        let force = args.get("force").and_then(|v| v.as_bool()).unwrap_or(false);
        match w.remove(&path, force).await {
            Ok(()) => Ok(ToolResult::text(format!("removed {}", path.display()))),
            Err(e) => Ok(ToolResult::error(format!("worktree: {e}"))),
        }
    }
}

// ===========================================================================
//                          agent_kill (v0.3)
// ===========================================================================

pub struct AgentKillTool {
    hub: Hub,
}
impl AgentKillTool {
    pub fn new(hub: Hub) -> Self {
        Self { hub }
    }
}
#[async_trait]
impl McpTool for AgentKillTool {
    fn name(&self) -> &'static str {
        "agent_kill"
    }
    fn schema(&self) -> ToolSchema {
        ToolSchema {
            name: self.name().into(),
            description: "Send SIGTERM to a running agent session. Use when a sub-agent \
                 stalled, went off-task, or its result is no longer needed. The background \
                 wait task finalises the session with the signal exit code; \
                 agent_session_get(id) still shows captured output."
                .into(),
            input_schema: json!({
                "type": "object",
                "properties": {
                    "id": { "type": "string", "description": "Session id from agent_spawn." }
                },
                "required": ["id"]
            }),
        }
    }
    async fn execute(&self, args: Value, _ctx: &ToolContext) -> Result<ToolResult> {
        let agent = match &self.hub.agent {
            Some(a) => a.clone(),
            None => return Ok(ToolResult::error("no agent runtime configured")),
        };
        let id = match args.get("id").and_then(|v| v.as_str()) {
            Some(s) => SessionId::from_raw(s.to_string()),
            None => return Ok(ToolResult::error("missing 'id'")),
        };
        match agent.kill(&id).await {
            Ok(()) => Ok(ToolResult::text(format!("SIGTERM sent to session {id}"))),
            Err(e) => Ok(ToolResult::error(format!("kill: {e}"))),
        }
    }
}

// ===========================================================================
//                       agent session inspection (v0.2)
// ===========================================================================

pub struct AgentSessionListTool {
    hub: Hub,
}
impl AgentSessionListTool {
    pub fn new(hub: Hub) -> Self {
        Self { hub }
    }
}
#[async_trait]
impl McpTool for AgentSessionListTool {
    fn name(&self) -> &'static str {
        "agent_session_list"
    }
    fn schema(&self) -> ToolSchema {
        ToolSchema {
            name: self.name().into(),
            description: "List recent agent sessions (default 20, max 1000). Row: id, \
                 runtime, cwd, started_at, ended_at, exit_code. Filters: runtime_id, \
                 cwd_prefix, state, exit_code (negative=signal). Running rows carry \
                 liveness. Use agent_session_get(id) for full output."
                .into(),
            input_schema: json!({
                "type": "object",
                "properties": {
                    "limit":      { "type": "integer", "minimum": 1, "maximum": 1000, "default": 20 },
                    "runtime_id": { "type": "string",  "description": "e.g. 'claude-code'" },
                    "cwd_prefix": { "type": "string",  "description": "Prefix-match the working dir." },
                    "state":      { "type": "string",  "enum": ["running","finished"] },
                    "exit_code":  { "type": "integer", "description": "Exact exit code (negative = signal)." }
                }
            }),
        }
    }
    async fn execute(&self, args: Value, _ctx: &ToolContext) -> Result<ToolResult> {
        let store = match &self.hub.store {
            Some(s) => s.clone(),
            None => return Ok(ToolResult::error("no store configured")),
        };
        let limit = args
            .get("limit")
            .and_then(|v| v.as_u64())
            .unwrap_or(20)
            .min(1000) as u32;
        let filter = SessionFilter {
            runtime_id: args
                .get("runtime_id")
                .and_then(|v| v.as_str())
                .map(|s| s.to_string()),
            cwd_prefix: args
                .get("cwd_prefix")
                .and_then(|v| v.as_str())
                .map(|s| s.to_string()),
            exited_only: args
                .get("state")
                .and_then(|v| v.as_str())
                .and_then(|s| match s {
                    "finished" => Some(true),
                    "running" => Some(false),
                    _ => None,
                }),
            exit_code: args
                .get("exit_code")
                .and_then(|v| v.as_i64())
                .map(|n| n as i32),
        };
        let rows = store.list_sessions(&filter, limit).await?;
        // Strip stdout/stderr to keep the listing compact.
        let summary: Vec<Value> = rows
            .into_iter()
            .map(|s| {
                let running = s.ended_at.is_none();
                let mut row = json!({
                    "id":          s.id.as_str(),
                    "runtime_id":  s.runtime_id,
                    "cwd":         s.cwd,
                    "started_at":  s.started_at,
                    "ended_at":    s.ended_at,
                    "exit_code":   s.exit_code,
                    "running":     running,
                    "stdout_len":  s.stdout.as_ref().map(|x| x.len()).unwrap_or(0),
                    "stderr_len":  s.stderr.as_ref().map(|x| x.len()).unwrap_or(0),
                });
                if running {
                    let (pid, liveness) =
                        match self.hub.agent.as_ref().and_then(|a| a.pid_for(&s.id)) {
                            Some(pid) => {
                                let alive = std::path::Path::new(&format!("/proc/{pid}")).exists();
                                (Some(pid), if alive { "alive" } else { "dead" })
                            }
                            None => (None, "unknown"),
                        };
                    if let Some(p) = pid {
                        row["pid"] = json!(p);
                    }
                    row["liveness"] = json!(liveness);
                }
                row
            })
            .collect();
        Ok(ToolResult::json_text(&Value::Array(summary)))
    }
}

pub struct AgentSessionGetTool {
    hub: Hub,
}
impl AgentSessionGetTool {
    pub fn new(hub: Hub) -> Self {
        Self { hub }
    }
}
#[async_trait]
impl McpTool for AgentSessionGetTool {
    fn name(&self) -> &'static str {
        "agent_session_get"
    }
    fn schema(&self) -> ToolSchema {
        ToolSchema {
            name: self.name().into(),
            description: "Fetch one agent session row by id, including the full captured \
                 stdout and stderr (each clamped to 64 KiB). Returns null if the \
                 session id is unknown."
                .into(),
            input_schema: json!({
                "type": "object",
                "properties": { "id": { "type": "string" } },
                "required": ["id"]
            }),
        }
    }
    async fn execute(&self, args: Value, _ctx: &ToolContext) -> Result<ToolResult> {
        let store = match &self.hub.store {
            Some(s) => s.clone(),
            None => return Ok(ToolResult::error("no store configured")),
        };
        let id = match args.get("id").and_then(|v| v.as_str()) {
            Some(s) => SessionId::from_raw(s.to_string()),
            None => return Ok(ToolResult::error("missing 'id'")),
        };
        let row = store.load_session(&id).await?;
        Ok(ToolResult::json_text(
            &serde_json::to_value(row).unwrap_or(Value::Null),
        ))
    }
}

pub struct AgentSessionWaitTool {
    hub: Hub,
}
impl AgentSessionWaitTool {
    pub fn new(hub: Hub) -> Self {
        Self { hub }
    }
}
#[async_trait]
impl McpTool for AgentSessionWaitTool {
    fn name(&self) -> &'static str {
        "agent_session_wait"
    }
    fn schema(&self) -> ToolSchema {
        ToolSchema {
            name: self.name().into(),
            description: "Block until the given session has finished (ended_at != null) or \
                 `timeout_secs` elapses. Polls the store every 500 ms. On success \
                 returns the final row (with stdout/stderr); on timeout returns the \
                 latest in-flight row plus `timed_out=true`."
                .into(),
            input_schema: json!({
                "type": "object",
                "properties": {
                    "id":           { "type": "string" },
                    "timeout_secs": { "type": "integer", "minimum": 1, "maximum": 600, "default": 60 }
                },
                "required": ["id"]
            }),
        }
    }
    async fn execute(&self, args: Value, _ctx: &ToolContext) -> Result<ToolResult> {
        let store = match &self.hub.store {
            Some(s) => s.clone(),
            None => return Ok(ToolResult::error("no store configured")),
        };
        let id = match args.get("id").and_then(|v| v.as_str()) {
            Some(s) => SessionId::from_raw(s.to_string()),
            None => return Ok(ToolResult::error("missing 'id'")),
        };
        let timeout = Duration::from_secs(
            args.get("timeout_secs")
                .and_then(|v| v.as_u64())
                .unwrap_or(60)
                .min(600),
        );
        let deadline = Instant::now() + timeout;

        // Phase 1: wait for local CLI process to finish (ended_at set).
        let local_row = loop {
            let row = store.load_session(&id).await?;
            if let Some(ref s) = row {
                if s.ended_at.is_some() {
                    break row;
                }
            }
            if Instant::now() >= deadline {
                return Ok(ToolResult::json_text(&json!({
                    "timed_out": true,
                    "session": row,
                })));
            }
            tokio::time::sleep(Duration::from_millis(500)).await;
        };

        // Phase 2 (warp-oz only): if cloud_run_id is set and state is not yet
        // terminal, continue polling via `oz run get` until terminal or timeout.
        let is_warp_oz = local_row
            .as_ref()
            .map(|s| s.runtime_id == "warp-oz")
            .unwrap_or(false);
        let cloud_run_id = local_row.as_ref().and_then(|s| s.cloud_run_id.clone());

        if is_warp_oz {
            if let Some(run_id) = cloud_run_id {
                let bin = oz_binary(&self.hub);
                // Check initial cloud state from store first.
                let already_terminal = local_row
                    .as_ref()
                    .and_then(|s| s.cloud_run_state.as_deref())
                    .map(|st| ab_agent::oz::TERMINAL_STATES.contains(&st))
                    .unwrap_or(false);
                if !already_terminal {
                    // Poll until terminal or deadline.
                    loop {
                        if Instant::now() >= deadline {
                            let row = store.load_session(&id).await?;
                            return Ok(ToolResult::json_text(&json!({
                                "timed_out": true,
                                "session": row,
                            })));
                        }
                        tokio::time::sleep(Duration::from_secs(3)).await;
                        // Call oz run get to get latest state
                        if let Some(status) = fetch_run_status(&bin, &run_id).await {
                            let state_str = status.state.as_deref().unwrap_or("UNKNOWN");
                            let _ = store
                                .set_cloud_run_state(&id, state_str, status.session_link.as_deref())
                                .await;
                            if ab_agent::oz::TERMINAL_STATES.contains(&state_str) {
                                break;
                            }
                        }
                    }
                }
            }
        }

        // Return final row.
        let final_row = store.load_session(&id).await?;
        Ok(ToolResult::json_text(&json!({
            "timed_out": false,
            "session": final_row,
        })))
    }
}

// ===========================================================================
//                       agent self-memory (v0.4)
// ===========================================================================

/// Build a proactive hint for an agent memory key.
///
/// Heuristic:
/// 1. Count existing edges (via `memory_neighbors`).
/// 2. Build a topical query from the key slug + tags + first content words.
///    Key slugs (e.g. "lesson_bfs_cycle") carry semantic signal; raw content
///    often matches only itself.
/// 3. Run FTS search (hybrid mode for richer recall).
/// 4. Keep top-3 results that aren't the key itself or already linked.
/// 5. Return a compact one-line suggestion, or `None` when nothing useful.
///
/// Errors are swallowed — hints are best-effort and must never break callers.
async fn build_proactive_hint(
    store: &Arc<dyn StateStore>,
    key: &str,
    content: &str,
    tags: &[String],
) -> Option<String> {
    // Existing direct edges
    let neighbors = store.memory_neighbors(key).await.unwrap_or_default();
    let edge_count = neighbors.len();
    let linked: std::collections::HashSet<String> = neighbors
        .into_iter()
        .flat_map(|e| [e.from_key, e.to_key])
        .filter(|k| k != key)
        .collect();

    // Build a topical query using FTS5 OR syntax so any relevant keyword matches.
    //
    // FTS5 uses AND by default; multi-word queries with uncommon words produce zero
    // results.  "tag1 OR tag2 OR word1 OR word2" avoids this while still ranking by
    // how many terms appear.
    //
    // Strategy: tags first (always topical), then first content words.
    // The FTS5 index stores the key as a single token ("lesson_bfs_guard"),
    // so key-slug splits are useless here — skip them.
    // Collect candidate tokens:
    //   tags that are clean identifiers (no hyphens/dots that confuse FTS5)
    //   + first content words that are purely alphabetic, len ≥ 3
    let is_clean = |s: &str| s.len() >= 3 && s.chars().all(|c| c.is_ascii_alphanumeric());
    let tag_terms: Vec<String> = tags.iter().filter(|t| is_clean(t)).cloned().collect();
    let content_terms: Vec<String> = content
        .split_whitespace()
        .map(|w| {
            // Strip leading/trailing punctuation
            w.trim_matches(|c: char| !c.is_alphanumeric()).to_string()
        })
        .filter(|w| is_clean(w) && w.chars().all(|c| c.is_ascii_alphabetic()))
        .take(10)
        .collect();
    let mut seen = std::collections::HashSet::new();
    let terms: Vec<String> = tag_terms
        .into_iter()
        .chain(content_terms)
        .filter(|w| seen.insert(w.to_lowercase()))
        .take(10)
        .collect();
    let query = terms.join(" OR "); // FTS5 OR: any term matches

    if query.trim().is_empty() {
        return None;
    }

    // Hybrid search — broader recall than pure FTS
    // signature: (query, tags, limit, rrf_k, expand_top)
    let tags_empty: Vec<String> = Vec::new();
    let hits = store
        .memory_search_hybrid(&query, &tags_empty, 6, 60.0, 3)
        .await
        .unwrap_or_default();

    // Filter: skip self and already-linked; no score threshold (BM25 isn't normalised)
    let candidates: Vec<_> = hits
        .into_iter()
        .filter(|h| h.record.key != key && !linked.contains(&h.record.key))
        .take(3)
        .collect();

    if candidates.is_empty() {
        return None;
    }

    let suggestions = candidates
        .iter()
        .map(|h| h.record.key.clone())
        .collect::<Vec<_>>()
        .join(" · ");

    let edge_note = if edge_count == 0 {
        "no edges yet".to_string()
    } else {
        format!("{edge_count} edge(s)")
    };

    Some(format!("{edge_note} | consider memory_link: {suggestions}"))
}

pub struct MemorySaveTool {
    hub: Hub,
}
impl MemorySaveTool {
    pub fn new(hub: Hub) -> Self {
        Self { hub }
    }
}
#[async_trait]
impl McpTool for MemorySaveTool {
    fn name(&self) -> &'static str {
        "memory_save"
    }
    fn schema(&self) -> ToolSchema {
        ToolSchema {
            name: self.name().into(),
            description: "Persist one note to agent self-memory (cross-session). Record \
                 lessons, decisions, todos, or context the next-session-you should know. \
                 Same key overwrites: created_at preserved, updated_at bumps. related_keys: \
                 free-form list of related memory keys."
                .into(),
            input_schema: json!({
                "type": "object",
                "properties": {
                    "key":          { "type": "string", "description": "Unique stable id, e.g. 'v0.5_design' or 'agent_spawn_pitfall'." },
                    "kind":         { "type": "string", "description": "lesson | decision | todo | context | session_handoff | …" },
                    "content":      { "type": "string", "description": "Markdown / free text. Capped at 256 KiB." },
                    "tags":         { "type": "array", "items": { "type": "string" }, "default": [] },
                    "related_keys": { "type": "array", "items": { "type": "string" }, "default": [] },
                    "scope":        { "type": "string", "description": "Visibility: omit/global=everywhere, project:/abs/path=cwd-scoped, domain:rust=tech-domain." },
                    "importance":   { "type": "number", "minimum": 0.0, "maximum": 1.0, "description": "Override importance (0.0–1.0). Omit to auto-assign from kind: decision=0.8, lesson=0.7, todo=0.6, fact=0.5, observation=0.3." },
                    "trigger_pattern": { "type": "string", "description": "For kind=error_pattern: surfacing when session_bootstrap `error_hint` contains this substring (case-insensitive)." }
                },
                "required": ["key", "kind", "content"]
            }),
        }
    }
    async fn execute(&self, args: Value, _ctx: &ToolContext) -> Result<ToolResult> {
        let store = match &self.hub.store {
            Some(s) => s.clone(),
            None => return Ok(ToolResult::error("no store configured")),
        };
        let key = match args.get("key").and_then(|v| v.as_str()) {
            Some(s) if !s.is_empty() => s.to_string(),
            _ => return Ok(ToolResult::error("missing or empty 'key'")),
        };
        let kind = match args.get("kind").and_then(|v| v.as_str()) {
            Some(s) if !s.is_empty() => s.to_string(),
            _ => return Ok(ToolResult::error("missing or empty 'kind'")),
        };
        let content = args
            .get("content")
            .and_then(|v| v.as_str())
            .unwrap_or("")
            .to_string();
        let tags = args
            .get("tags")
            .and_then(|v| v.as_array())
            .map(|a| {
                a.iter()
                    .filter_map(|x| x.as_str().map(|s| s.to_string()))
                    .collect()
            })
            .unwrap_or_default();
        let related_keys = args
            .get("related_keys")
            .and_then(|v| v.as_array())
            .map(|a| {
                a.iter()
                    .filter_map(|x| x.as_str().map(|s| s.to_string()))
                    .collect()
            })
            .unwrap_or_default();
        let scope = args
            .get("scope")
            .and_then(|v| v.as_str())
            .filter(|s| !s.is_empty() && *s != "global")
            .map(|s| s.to_string());
        // Optional importance override; 0.5 = "use kind-based default"
        let importance = args
            .get("importance")
            .and_then(|v| v.as_f64())
            .unwrap_or(0.5)
            .clamp(0.0, 1.0);

        let trigger_pattern = args
            .get("trigger_pattern")
            .and_then(|v| v.as_str())
            .map(|s| s.trim().to_string())
            .filter(|s| !s.is_empty());

        let mem = MemoryRecord {
            key: key.clone(),
            kind,
            content,
            tags,
            related_keys,
            scope,
            created_at: 0,
            updated_at: 0,
            last_accessed_at: 0,
            access_count: 0,
            importance,
            status: "active".to_string(),
            trigger_pattern,
        };
        match store.memory_save(&mem).await {
            Ok(()) => {
                // Keep embedding cache coherent: upsert the new/updated record.
                {
                    let cache = self.hub.memory_embed_cache.clone();
                    let rec = mem.clone();
                    let emb = embed_text(&rec.content);
                    tokio::spawn(async move {
                        let mut guard = cache.lock().await;
                        if let Some(ref mut cached) = *guard {
                            cached.retain(|(r, _)| r.key != rec.key);
                            cached.push((rec, emb));
                        }
                    });
                }
                let hint = build_proactive_hint(&store, &key, &mem.content, &mem.tags).await;
                let resp = json!({
                    "status": "saved",
                    "key": key,
                    "proactive_hint": hint,
                });
                Ok(ToolResult::json_text(&resp))
            }
            Err(e) => Ok(ToolResult::error(format!("memory: {e}"))),
        }
    }
}

pub struct MemoryGetTool {
    hub: Hub,
}
impl MemoryGetTool {
    pub fn new(hub: Hub) -> Self {
        Self { hub }
    }
}
#[async_trait]
impl McpTool for MemoryGetTool {
    fn name(&self) -> &'static str {
        "memory_get"
    }
    fn schema(&self) -> ToolSchema {
        ToolSchema {
            name: self.name().into(),
            description: "Fetch one memory by exact key. Side effect: bumps the row's \
                 access_count and last_accessed_at — this is what gives \
                 `memory_search` ranking and `memory_compact` something to score \
                 against. Returns null if the key is unknown."
                .into(),
            input_schema: json!({
                "type": "object",
                "properties": { "key": { "type": "string" } },
                "required": ["key"]
            }),
        }
    }
    async fn execute(&self, args: Value, _ctx: &ToolContext) -> Result<ToolResult> {
        let store = match &self.hub.store {
            Some(s) => s.clone(),
            None => return Ok(ToolResult::error("no store configured")),
        };
        let key = match args.get("key").and_then(|v| v.as_str()) {
            Some(s) => s.to_string(),
            None => return Ok(ToolResult::error("missing 'key'")),
        };
        let row = store.memory_get(&key).await?;
        match row {
            None => Ok(ToolResult::json_text(&Value::Null)),
            Some(rec) => {
                let hint = build_proactive_hint(&store, &key, &rec.content, &rec.tags).await;
                let mut resp = serde_json::to_value(&rec).unwrap_or(Value::Null);
                if let Some(obj) = resp.as_object_mut() {
                    obj.insert(
                        "proactive_hint".to_string(),
                        hint.map(Value::String).unwrap_or(Value::Null),
                    );
                }
                Ok(ToolResult::json_text(&resp))
            }
        }
    }
}

pub struct MemorySearchTool {
    hub: Hub,
}
impl MemorySearchTool {
    pub fn new(hub: Hub) -> Self {
        Self { hub }
    }
}
#[async_trait]
impl McpTool for MemorySearchTool {
    fn name(&self) -> &'static str {
        "memory_search"
    }
    fn schema(&self) -> ToolSchema {
        ToolSchema {
            name: self.name().into(),
            description: "Search memories by keyword or semantic similarity. mode='fts': \
                 FTS5 by bm25+recency+importance. mode='hybrid': FTS5 + graph neighbors \
                 via RRF fusion. mode='semantic': cosine over local embeddings — catches \
                 synonyms FTS misses. Excludes archived/superseded."
                .into(),
            input_schema: json!({
                "type": "object",
                "properties": {
                    "query":      { "type": "string", "description": "Search query (FTS5 match syntax for fts/hybrid; natural language for semantic)." },
                    "tags_any":   { "type": "array", "items": { "type": "string" }, "default": [] },
                    "limit":      { "type": "integer", "minimum": 1, "maximum": 200, "default": 20 },
                    "mode":       {
                        "type": "string", "enum": ["fts", "hybrid", "semantic"], "default": "fts",
                        "description": "'fts' = keyword BM25; 'hybrid' = FTS5 + graph RRF fusion; 'semantic' = cosine similarity."
                    },
                    "expand_top": {
                        "type": "integer", "minimum": 1, "maximum": 20, "default": 10,
                        "description": "[hybrid only] Number of top FTS5 hits to expand via graph neighbors."
                    },
                    "rrf_k":      {
                        "type": "number", "minimum": 1.0, "maximum": 200.0, "default": 60.0,
                        "description": "[hybrid only] RRF constant k. Higher k = less rank compression."
                    },
                    "threshold":  {
                        "type": "number", "minimum": 0.0, "maximum": 1.0, "default": 0.3,
                        "description": "[semantic only] Minimum cosine similarity to include. 0.3 = broad, 0.7 = tight."
                    },
                    "exclude_kinds": {
                        "type": "array", "items": { "type": "string" }, "default": [],
                        "description": "Drop hits whose `kind` matches any of these from the OUTPUT. \
                            Useful for keeping bulky `skill` records (~88% of store) out of generic queries. \
                            Inner search auto-overfetches 5× to compensate. α coactivation still learns \
                            from the full pre-filter hit set, so cross-kind edges keep forming."
                    }
                },
                "required": ["query"]
            }),
        }
    }
    async fn execute(&self, args: Value, _ctx: &ToolContext) -> Result<ToolResult> {
        let store = match &self.hub.store {
            Some(s) => s.clone(),
            None => return Ok(ToolResult::error("no store configured")),
        };
        let q = args
            .get("query")
            .and_then(|v| v.as_str())
            .unwrap_or("")
            .to_string();
        let tags: Vec<String> = args
            .get("tags_any")
            .and_then(|v| v.as_array())
            .map(|a| {
                a.iter()
                    .filter_map(|x| x.as_str().map(|s| s.to_string()))
                    .collect()
            })
            .unwrap_or_default();
        let limit = args
            .get("limit")
            .and_then(|v| v.as_u64())
            .unwrap_or(20)
            .min(200) as u32;
        let mode = args.get("mode").and_then(|v| v.as_str()).unwrap_or("fts");

        let exclude_kinds: Vec<String> = args
            .get("exclude_kinds")
            .and_then(|v| v.as_array())
            .map(|a| {
                a.iter()
                    .filter_map(|x| x.as_str().map(|s| s.to_string()))
                    .collect()
            })
            .unwrap_or_default();
        // When exclusions are active, overfetch so the post-filter result can
        // still hit `limit`. 5× covers up to ~80% saturation; cap at 200 (the
        // schema's hard upper bound) to avoid pathological queries.
        let inner_limit = if exclude_kinds.is_empty() {
            limit
        } else {
            (limit.saturating_mul(5)).min(200)
        };

        let hits = if mode == "hybrid" {
            let expand_top = args
                .get("expand_top")
                .and_then(|v| v.as_u64())
                .unwrap_or(10)
                .min(20) as u32;
            let rrf_k = args
                .get("rrf_k")
                .and_then(|v| v.as_f64())
                .unwrap_or(60.0)
                .clamp(1.0, 200.0);
            store
                .memory_search_hybrid(&q, &tags, inner_limit, rrf_k, expand_top)
                .await?
        } else if mode == "semantic" {
            let threshold = args
                .get("threshold")
                .and_then(|v| v.as_f64())
                .unwrap_or(0.3)
                .clamp(0.0, 1.0) as f32;
            let cache_guard = self.hub.memory_embed_cache.lock().await;
            if let Some(cached) = cache_guard.as_ref() {
                let query_vec = embed_text(&q);
                let mut hits: Vec<MemorySearchHit> = cached
                    .iter()
                    .filter_map(|(rec, emb)| {
                        let cosine = cosine_similarity(&query_vec, emb);
                        if cosine < threshold {
                            return None;
                        }
                        Some(MemorySearchHit {
                            score: cosine as f64 + 0.2 * rec.importance,
                            record: rec.clone(),
                        })
                    })
                    .collect();
                hits.sort_by(|a, b| {
                    b.score.partial_cmp(&a.score).unwrap_or(std::cmp::Ordering::Equal)
                });
                hits.truncate(inner_limit as usize);
                drop(cache_guard);
                hits
            } else {
                drop(cache_guard);
                store.memory_search_semantic(&q, inner_limit, threshold).await?
            }
        } else {
            store.memory_search(&q, &tags, inner_limit).await?
        };

        // Path C actuator: rerank using perception_filter hub_clusters.
        // Fail-soft (no state file / disable env / empty hub_clusters → pass-through).
        let hits = apply_seed_boost(hits);

        // v21 α — Synaptic Trace. Record co-activation pairs for top hits as
        // fire-and-forget background work; never block search latency.
        // ctx_centroid is None for now (mode-agnostic α); follow-up plumbs
        // hit embeddings through for richer trace.
        // Run on PRE-filter hits so cross-kind edges (e.g. skill ↔ memory)
        // keep forming even when callers exclude_kinds the skill out of output.
        if hits.len() >= 2 {
            let store_clone = store.clone();
            let keys: Vec<String> =
                hits.iter().take(10).map(|h| h.record.key.clone()).collect();
            tokio::spawn(async move {
                let _ = store_clone.record_coactivation(&keys, None).await;
            });
        }

        // Apply caller's exclude_kinds and re-truncate to the requested limit.
        let mut hits = hits;
        if !exclude_kinds.is_empty() {
            hits.retain(|h| !exclude_kinds.iter().any(|k| k == &h.record.kind));
        }
        hits.truncate(limit as usize);

        Ok(ToolResult::json_text(
            &serde_json::to_value(hits).unwrap_or(Value::Null),
        ))
    }
}

pub struct MemoryListTool {
    hub: Hub,
}
impl MemoryListTool {
    pub fn new(hub: Hub) -> Self {
        Self { hub }
    }
}
#[async_trait]
impl McpTool for MemoryListTool {
    fn name(&self) -> &'static str {
        "memory_list"
    }
    fn schema(&self) -> ToolSchema {
        ToolSchema {
            name: self.name().into(),
            description: "List memories, optionally filtered by `kind`, sorted by 'recent' \
                 (default, last_accessed_at desc), 'frequent' (access_count desc), or \
                 'newest' (created_at desc). Use at session start with kind='lesson' to \
                 surface what previous-you learned."
                .into(),
            input_schema: json!({
                "type": "object",
                "properties": {
                    "kind":  { "type": "string", "description": "Optional kind filter." },
                    "sort":  { "type": "string", "enum": ["recent","frequent","newest"], "default": "recent" },
                    "limit": { "type": "integer", "minimum": 1, "maximum": 200, "default": 20 }
                }
            }),
        }
    }
    async fn execute(&self, args: Value, _ctx: &ToolContext) -> Result<ToolResult> {
        let store = match &self.hub.store {
            Some(s) => s.clone(),
            None => return Ok(ToolResult::error("no store configured")),
        };
        let kind = args
            .get("kind")
            .and_then(|v| v.as_str())
            .map(|s| s.to_string());
        let sort = match args
            .get("sort")
            .and_then(|v| v.as_str())
            .unwrap_or("recent")
        {
            "frequent" => MemoryListSort::Frequent,
            "newest" => MemoryListSort::Newest,
            _ => MemoryListSort::Recent,
        };
        let limit = args
            .get("limit")
            .and_then(|v| v.as_u64())
            .unwrap_or(20)
            .min(200) as u32;
        let rows = store.list_memories(kind.as_deref(), sort, limit).await?;
        Ok(ToolResult::json_text(
            &serde_json::to_value(rows).unwrap_or(Value::Null),
        ))
    }
}

pub struct MemoryDeleteTool {
    hub: Hub,
}
impl MemoryDeleteTool {
    pub fn new(hub: Hub) -> Self {
        Self { hub }
    }
}
#[async_trait]
impl McpTool for MemoryDeleteTool {
    fn name(&self) -> &'static str {
        "memory_delete"
    }
    fn schema(&self) -> ToolSchema {
        ToolSchema {
            name: self.name().into(),
            description: "Delete a memory by key. Returns `{deleted: true}` if a row was removed."
                .into(),
            input_schema: json!({
                "type": "object",
                "properties": { "key": { "type": "string" } },
                "required": ["key"]
            }),
        }
    }
    async fn execute(&self, args: Value, _ctx: &ToolContext) -> Result<ToolResult> {
        let store = match &self.hub.store {
            Some(s) => s.clone(),
            None => return Ok(ToolResult::error("no store configured")),
        };
        let key = match args.get("key").and_then(|v| v.as_str()) {
            Some(s) => s.to_string(),
            None => return Ok(ToolResult::error("missing 'key'")),
        };
        let removed = store.memory_delete(&key).await?;
        if removed {
            let cache = self.hub.memory_embed_cache.clone();
            let del_key = key.clone();
            tokio::spawn(async move {
                let mut guard = cache.lock().await;
                if let Some(ref mut cached) = *guard {
                    cached.retain(|(r, _)| r.key != del_key);
                }
            });
        }
        Ok(ToolResult::json_text(&json!({ "deleted": removed })))
    }
}

pub struct MemoryCompactTool {
    hub: Hub,
}
impl MemoryCompactTool {
    pub fn new(hub: Hub) -> Self {
        Self { hub }
    }
}
#[async_trait]
impl McpTool for MemoryCompactTool {
    fn name(&self) -> &'static str {
        "memory_compact"
    }
    fn schema(&self) -> ToolSchema {
        ToolSchema {
            name: self.name().into(),
            description: "Prune low-value memories. Removes only when BOTH match: min_uses \
                 (access_count <) AND older_than_days (last_accessed_at older than). \
                 1-hour grace on created_at. dry_run=true previews. Both omitted → \
                 defaults (min_uses=2, older_than_days=90)."
                .into(),
            input_schema: json!({
                "type": "object",
                "properties": {
                    "min_uses":        { "type": "integer", "minimum": 0 },
                    "older_than_days": { "type": "integer", "minimum": 1 },
                    "dry_run":         { "type": "boolean", "default": false }
                }
            }),
        }
    }
    async fn execute(&self, args: Value, _ctx: &ToolContext) -> Result<ToolResult> {
        let store = match &self.hub.store {
            Some(s) => s.clone(),
            None => return Ok(ToolResult::error("no store configured")),
        };
        let min_uses = args.get("min_uses").and_then(|v| v.as_u64());
        let older_than_secs = args
            .get("older_than_days")
            .and_then(|v| v.as_i64())
            .map(|d| d * 86_400);
        let dry_run = args
            .get("dry_run")
            .and_then(|v| v.as_bool())
            .unwrap_or(false);

        let mut policy = CompactPolicy {
            min_uses,
            older_than_secs,
            dry_run,
        };
        let applied_defaults = policy.is_unset();
        if applied_defaults {
            // v0.8: don't punish callers with a silent no-op; apply the balanced
            // default. dry_run flag is still honoured.
            let mut def = CompactPolicy::healthy_default();
            def.dry_run = dry_run;
            policy = def;
        }
        let keys = store.memory_compact(policy).await?;
        if !dry_run && !keys.is_empty() {
            let cache = self.hub.memory_embed_cache.clone();
            let removed_keys: std::collections::HashSet<String> = keys.iter().cloned().collect();
            tokio::spawn(async move {
                let mut guard = cache.lock().await;
                if let Some(ref mut cached) = *guard {
                    cached.retain(|(r, _)| !removed_keys.contains(&r.key));
                }
            });
        }
        Ok(ToolResult::json_text(&json!({
            "dry_run": dry_run,
            "applied_defaults": applied_defaults,
            "policy": {
                "min_uses": policy.min_uses,
                "older_than_secs": policy.older_than_secs,
            },
            "removed_count": keys.len(),
            "removed_keys": keys,
        })))
    }
}

// ===========================================================================
//                       memory_reindex (re-embed after dim migration)
// ===========================================================================

pub struct MemoryReindexTool {
    hub: Hub,
}
impl MemoryReindexTool {
    pub fn new(hub: Hub) -> Self {
        Self { hub }
    }
}
#[async_trait]
impl McpTool for MemoryReindexTool {
    fn name(&self) -> &'static str {
        "memory_reindex"
    }
    fn schema(&self) -> ToolSchema {
        ToolSchema {
            name: self.name().into(),
            description: "Re-compute embeddings for active memories with no stored vector \
                 (e.g. after dim migration). Processes batch_size rows per call \
                 (default 100, max 1000). Call repeatedly until updated=0. Refreshes the \
                 embedding cache so semantic search sees new vectors."
                .into(),
            input_schema: json!({
                "type": "object",
                "properties": {
                    "batch_size": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 1000,
                        "default": 100,
                        "description": "Number of rows to re-embed per call."
                    }
                }
            }),
        }
    }
    async fn execute(&self, args: Value, _ctx: &ToolContext) -> Result<ToolResult> {
        let store = match &self.hub.store {
            Some(s) => s.clone(),
            None => return Ok(ToolResult::error("no store configured")),
        };
        let batch_size = args
            .get("batch_size")
            .and_then(|v| v.as_u64())
            .unwrap_or(100) as usize;

        let updated = store.memory_reindex_embeddings(batch_size).await?;

        // Refresh the in-process embedding cache so the new vectors are visible.
        if updated > 0 {
            let cache = self.hub.memory_embed_cache.clone();
            let refresh_store = store.clone();
            tokio::spawn(async move {
                if let Ok(rows) = refresh_store.memory_load_embeddings().await {
                    let mut guard = cache.lock().await;
                    *guard = Some(rows);
                }
            });
        }

        Ok(ToolResult::json_text(&json!({
            "updated": updated,
            "batch_size": batch_size,
            "hint": if updated == batch_size {
                format!("Batch full — call memory_reindex again to continue ({batch_size} rows/call).")
            } else {
                format!("Done. {updated} rows re-embedded this call.")
            }
        })))
    }
}

// ===========================================================================
//                       codebase_reindex (fill NULL embeddings)
// ===========================================================================

pub struct CodebaseReindexTool {
    hub: Hub,
}
impl CodebaseReindexTool {
    pub fn new(hub: Hub) -> Self {
        Self { hub }
    }
}
#[async_trait]
impl McpTool for CodebaseReindexTool {
    fn name(&self) -> &'static str {
        "codebase_reindex"
    }
    fn schema(&self) -> ToolSchema {
        ToolSchema {
            name: self.name().into(),
            description:
                "Fill in embeddings for codebase_symbols rows that have none. \
                 codebase_index writes rows with NULL embedding by design — \
                 this tool computes them in batches so codebase_search(mode=\"semantic\") \
                 has vectors to score against. Processes batch_size rows per call \
                 (default 100, max 1000); call repeatedly until updated=0."
                    .into(),
            input_schema: json!({
                "type": "object",
                "properties": {
                    "batch_size": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 1000,
                        "default": 100,
                        "description": "Number of rows to embed per call."
                    }
                }
            }),
        }
    }
    async fn execute(&self, args: Value, _ctx: &ToolContext) -> Result<ToolResult> {
        let store = match &self.hub.store {
            Some(s) => s.clone(),
            None => return Ok(ToolResult::error("no store configured")),
        };
        let batch_size = args
            .get("batch_size")
            .and_then(|v| v.as_u64())
            .unwrap_or(100) as usize;

        let updated = store.codebase_reindex_embeddings(batch_size).await?;

        Ok(ToolResult::json_text(&json!({
            "updated": updated,
            "batch_size": batch_size,
            "hint": if updated == batch_size {
                format!("Batch full — call codebase_reindex again to continue ({batch_size} rows/call).")
            } else {
                format!("Done. {updated} symbols embedded this call.")
            }
        })))
    }
}

// ===========================================================================
//                       memory portability (v0.6)
// ===========================================================================

pub struct MemoryExportTool {
    hub: Hub,
}
impl MemoryExportTool {
    pub fn new(hub: Hub) -> Self {
        Self { hub }
    }
}
#[async_trait]
impl McpTool for MemoryExportTool {
    fn name(&self) -> &'static str {
        "memory_export"
    }
    fn schema(&self) -> ToolSchema {
        ToolSchema {
            name: self.name().into(),
            description: "Export memories to a newline-delimited JSON file (one record \
                 per line — JSONL is grep-friendly and stable across versions). \
                 Optional filters narrow what's exported. When `edges_out_path` \
                 is set, a second JSONL file is written: one [`MemoryEdgeExport`] \
                 per line for every `memory_edges` row whose **both** endpoints \
                 are among the exported memory keys. The main file can then be \
                 moved with the edge companion and consumed by `memory_import` \
                 (pass the same paths as `path` + optional `edges_path`)."
                .into(),
            input_schema: json!({
                "type": "object",
                "properties": {
                    "path":     { "type": "string", "description": "Absolute output path; parent dirs auto-created." },
                    "kind":     { "type": "string", "description": "Optional kind filter." },
                    "tags_any": { "type": "array", "items": {"type": "string"}, "description": "Match if memory has at least one tag." },
                    "since_ts": { "type": "integer", "description": "Only memories with updated_at >= this unix-epoch seconds value." },
                    "edges_out_path": { "type": "string", "description": "Optional absolute path for companion edge JSONL (both endpoints must be in the exported memory set)." }
                },
                "required": ["path"]
            }),
        }
    }
    async fn execute(&self, args: Value, _ctx: &ToolContext) -> Result<ToolResult> {
        let store = match &self.hub.store {
            Some(s) => s.clone(),
            None => return Ok(ToolResult::error("no store configured")),
        };
        let path = match args.get("path").and_then(|v| v.as_str()) {
            Some(s) => PathBuf::from(s),
            None => return Ok(ToolResult::error("missing 'path'")),
        };
        let filter = MemoryExportFilter {
            kind: args
                .get("kind")
                .and_then(|v| v.as_str())
                .map(|s| s.to_string()),
            tags_any: args.get("tags_any").and_then(|v| v.as_array()).map(|a| {
                a.iter()
                    .filter_map(|x| x.as_str().map(|s| s.to_string()))
                    .collect()
            }),
            since_ts: args.get("since_ts").and_then(|v| v.as_i64()),
            edges_out_path: args
                .get("edges_out_path")
                .and_then(|v| v.as_str())
                .filter(|s| !s.is_empty())
                .map(PathBuf::from),
        };
        match store.memory_export(&filter, &path).await {
            Ok(res) => Ok(ToolResult::json_text(&json!({
                "exported": res.memories_written,
                "memories_written": res.memories_written,
                "edges_written": res.edges_written,
                "path": path.display().to_string(),
            }))),
            Err(e) => Ok(ToolResult::error(format!("export: {e}"))),
        }
    }
}

pub struct MemoryImportTool {
    hub: Hub,
}
impl MemoryImportTool {
    pub fn new(hub: Hub) -> Self {
        Self { hub }
    }
}
#[async_trait]
impl McpTool for MemoryImportTool {
    fn name(&self) -> &'static str {
        "memory_import"
    }
    fn schema(&self) -> ToolSchema {
        ToolSchema {
            name: self.name().into(),
            description: "Import memories from a JSONL file (the format `memory_export` \
                 produces). Optional `edges_path` is a companion JSONL of \
                 `MemoryEdgeExport` lines (same convention as `memory_export` \
                 `edges_out_path`); edges are upserted after memories. \
                 `conflict_policy` decides what happens when a key \
                 already exists locally:\n\
                   - `skip` (default): keep local row\n\
                   - `overwrite`: always replace with the imported row\n\
                   - `newer_wins`: replace only if imported.updated_at is greater\n\
                 Returns {inserted, updated, skipped, malformed, edges_upserted, edges_malformed}."
                .into(),
            input_schema: json!({
                "type": "object",
                "properties": {
                    "path":            { "type": "string" },
                    "edges_path":      { "type": "string", "description": "Optional companion JSONL produced by memory_export(edges_out_path=...)." },
                    "conflict_policy": {
                        "type": "string",
                        "enum": ["skip","overwrite","newer_wins"],
                        "default": "skip"
                    }
                },
                "required": ["path"]
            }),
        }
    }
    async fn execute(&self, args: Value, _ctx: &ToolContext) -> Result<ToolResult> {
        let store = match &self.hub.store {
            Some(s) => s.clone(),
            None => return Ok(ToolResult::error("no store configured")),
        };
        let path = match args.get("path").and_then(|v| v.as_str()) {
            Some(s) => PathBuf::from(s),
            None => return Ok(ToolResult::error("missing 'path'")),
        };
        let policy = match args
            .get("conflict_policy")
            .and_then(|v| v.as_str())
            .unwrap_or("skip")
        {
            "overwrite" => ImportConflictPolicy::Overwrite,
            "newer_wins" => ImportConflictPolicy::NewerWins,
            _ => ImportConflictPolicy::Skip,
        };
        let edges_path = args
            .get("edges_path")
            .and_then(|v| v.as_str())
            .filter(|s| !s.is_empty())
            .map(PathBuf::from);
        match store
            .memory_import(&path, policy, edges_path.as_deref())
            .await
        {
            Ok(report) => Ok(ToolResult::json_text(
                &serde_json::to_value(report).unwrap_or(Value::Null),
            )),
            Err(e) => Ok(ToolResult::error(format!("import: {e}"))),
        }
    }
}

// ===========================================================================
//                       memory graph edges (v0.6)
// ===========================================================================

pub struct MemoryLinkTool {
    hub: Hub,
}
impl MemoryLinkTool {
    pub fn new(hub: Hub) -> Self {
        Self { hub }
    }
}
#[async_trait]
impl McpTool for MemoryLinkTool {
    fn name(&self) -> &'static str {
        "memory_link"
    }
    fn schema(&self) -> ToolSchema {
        ToolSchema {
            name: self.name().into(),
            description: "Create/update a directed edge between two memories. Type/weight: \
                 updates 1.5, caused_by 1.3, supersedes 1.3, implements 1.1, relates 1.0, \
                 part_of 0.8, derived_from 0.8, contradicts 0.5, invalidates 0.5. Causal \
                 ×1.2 in BFS. Pair with memory_neighbors."
                .into(),
            input_schema: json!({
                "type": "object",
                "properties": {
                    "from_key":  { "type": "string", "description": "Source memory key." },
                    "to_key":    { "type": "string", "description": "Target memory key." },
                    "edge_type": {
                        "type": "string",
                        "enum": ["updates","caused_by","supersedes","implements","relates","part_of","derived_from","contradicts","invalidates"],
                        "default": "relates",
                        "description": "Relationship type. Weight is auto-assigned from type unless 'weight' is given."
                    },
                    "weight": {
                        "type": "number", "minimum": 0.0, "maximum": 2.0, "default": 1.0,
                        "description": "Override weight. Omit to use canonical weight for the edge type."
                    }
                },
                "required": ["from_key", "to_key"]
            }),
        }
    }
    async fn execute(&self, args: Value, _ctx: &ToolContext) -> Result<ToolResult> {
        let store = match &self.hub.store {
            Some(s) => s.clone(),
            None => return Ok(ToolResult::error("no store configured")),
        };
        let from_key = match args.get("from_key").and_then(|v| v.as_str()) {
            Some(s) if !s.is_empty() => s.to_string(),
            _ => return Ok(ToolResult::error("missing 'from_key'")),
        };
        let to_key = match args.get("to_key").and_then(|v| v.as_str()) {
            Some(s) if !s.is_empty() => s.to_string(),
            _ => return Ok(ToolResult::error("missing 'to_key'")),
        };
        let edge_type = args
            .get("edge_type")
            .and_then(|v| v.as_str())
            .unwrap_or("relates")
            .to_string();
        // 1.0 is the sentinel meaning "auto-assign from type"; any other value is explicit.
        let weight = args.get("weight").and_then(|v| v.as_f64()).unwrap_or(1.0);
        match store
            .memory_link(&from_key, &to_key, &edge_type, weight)
            .await
        {
            Ok(()) => {
                // Compute the effective weight that was stored for the response message
                let effective = if (weight - 1.0).abs() < f64::EPSILON {
                    ab_store::weight_for_edge_type(&edge_type)
                } else {
                    weight
                };
                Ok(ToolResult::text(format!(
                    "linked '{from_key}' -{edge_type}-> '{to_key}' (weight={effective:.2})"
                )))
            }
            Err(e) => Ok(ToolResult::error(format!("memory_link: {e}"))),
        }
    }
}

pub struct MemoryNeighborsTool {
    hub: Hub,
}
impl MemoryNeighborsTool {
    pub fn new(hub: Hub) -> Self {
        Self { hub }
    }
}
#[async_trait]
impl McpTool for MemoryNeighborsTool {
    fn name(&self) -> &'static str {
        "memory_neighbors"
    }
    fn schema(&self) -> ToolSchema {
        ToolSchema {
            name: self.name().into(),
            description: "Return graph edges (optionally BFS multi-hop) from a memory key. \
                 depth=1: direct neighbors by weight. depth>1: BFS propagating \
                 energy × weight × temporal × decay. Row: from_key, to_key, edge_type, \
                 weight, energy. Causal ×1.2, conflicts ×0.85."
                .into(),
            input_schema: json!({
                "type": "object",
                "properties": {
                    "key": { "type": "string", "description": "Starting memory key." },
                    "depth": {
                        "type": "integer", "minimum": 1, "maximum": 6, "default": 1,
                        "description": "BFS depth. 1=direct neighbors only, 2–6=multi-hop traversal."
                    },
                    "decay_factor": {
                        "type": "number", "minimum": 0.1, "maximum": 1.0, "default": 0.7,
                        "description": "Energy decay per hop. 0.7 means 30% energy loss per hop."
                    },
                    "min_energy": {
                        "type": "number", "minimum": 0.0, "maximum": 1.0, "default": 0.05,
                        "description": "Prune edges with propagated energy below this threshold."
                    }
                },
                "required": ["key"]
            }),
        }
    }
    async fn execute(&self, args: Value, _ctx: &ToolContext) -> Result<ToolResult> {
        let store = match &self.hub.store {
            Some(s) => s.clone(),
            None => return Ok(ToolResult::error("no store configured")),
        };
        let key = match args.get("key").and_then(|v| v.as_str()) {
            Some(s) => s.to_string(),
            None => return Ok(ToolResult::error("missing 'key'")),
        };
        let depth = args
            .get("depth")
            .and_then(|v| v.as_u64())
            .unwrap_or(1)
            .clamp(1, 6) as u8;
        let decay_factor = args
            .get("decay_factor")
            .and_then(|v| v.as_f64())
            .unwrap_or(0.7)
            .clamp(0.1, 1.0);
        let min_energy = args
            .get("min_energy")
            .and_then(|v| v.as_f64())
            .unwrap_or(0.05)
            .clamp(0.0, 1.0);

        if depth == 1 {
            // Fast path: simple direct neighbors (no BFS overhead)
            let edges = store.memory_neighbors(&key).await?;
            let out: Vec<serde_json::Value> = edges
                .into_iter()
                .map(|e| {
                    let energy = 1.0 * e.weight; // at depth=1, energy = starting_energy × weight
                    serde_json::json!({
                        "from_key": e.from_key,
                        "to_key": e.to_key,
                        "edge_type": e.edge_type,
                        "weight": e.weight,
                        "energy": energy
                    })
                })
                .collect();
            Ok(ToolResult::json_text(
                &serde_json::to_value(out).unwrap_or(Value::Null),
            ))
        } else {
            // BFS multi-hop path
            let pairs = store
                .memory_neighbors_bfs(&key, depth, decay_factor, min_energy)
                .await?;
            let out: Vec<serde_json::Value> = pairs
                .into_iter()
                .map(|(e, energy)| {
                    serde_json::json!({
                        "from_key": e.from_key,
                        "to_key": e.to_key,
                        "edge_type": e.edge_type,
                        "weight": e.weight,
                        "energy": (energy * 1000.0).round() / 1000.0
                    })
                })
                .collect();
            Ok(ToolResult::json_text(
                &serde_json::to_value(out).unwrap_or(Value::Null),
            ))
        }
    }
}

pub struct MemoryCoactivationTopTool {
    hub: Hub,
}
impl MemoryCoactivationTopTool {
    pub fn new(hub: Hub) -> Self {
        Self { hub }
    }
}
#[async_trait]
impl McpTool for MemoryCoactivationTopTool {
    fn name(&self) -> &'static str {
        "memory_coactivation_top"
    }
    fn schema(&self) -> ToolSchema {
        ToolSchema {
            name: self.name().into(),
            description: "v21 α — Synaptic Trace introspection. Returns the top \
                co-activation edges for a memory key, ordered by count DESC. \
                Records are populated as a side effect of memory_search calls \
                (Hebbian fire-together-wire-together). Each row: \
                {key_a, key_b, count, first_at, last_at}. The peer key in each \
                row is whichever of key_a/key_b is NOT the queried key. Empty \
                result on cold DB or if α has not started recording yet."
                .into(),
            input_schema: json!({
                "type": "object",
                "properties": {
                    "key":   { "type": "string", "description": "Memory key to look up." },
                    "limit": {
                        "type": "integer", "minimum": 1, "maximum": 200, "default": 20,
                        "description": "Max edges to return (highest count first)."
                    }
                },
                "required": ["key"]
            }),
        }
    }
    async fn execute(&self, args: Value, _ctx: &ToolContext) -> Result<ToolResult> {
        let store = match &self.hub.store {
            Some(s) => s.clone(),
            None => return Ok(ToolResult::error("no store configured")),
        };
        let key = match args.get("key").and_then(|v| v.as_str()) {
            Some(s) => s.to_string(),
            None => return Ok(ToolResult::error("missing 'key'")),
        };
        let limit = args
            .get("limit")
            .and_then(|v| v.as_u64())
            .unwrap_or(20)
            .clamp(1, 200) as u32;
        let edges = store.top_coactivation(&key, limit).await?;
        Ok(ToolResult::json_text(
            &serde_json::to_value(edges).unwrap_or(Value::Null),
        ))
    }
}

fn format_bootstrap_memory_rows(rows: &[MemoryRecord], snippet_len: usize) -> Vec<String> {
    rows.iter()
        .map(|r| {
            let tags = if r.tags.is_empty() {
                String::new()
            } else {
                format!(" [{}]", r.tags.join(", "))
            };
            let snippet: String = r.content.chars().take(snippet_len).collect();
            let ellipsis = if r.content.chars().count() > snippet_len {
                "…"
            } else {
                ""
            };
            let imp_marker = if r.importance >= 0.7 { "★" } else { "" };
            format!(
                "[{}] {}{}{}: {}{}",
                r.kind, r.key, imp_marker, tags, snippet, ellipsis
            )
        })
        .collect()
}

pub struct SessionBootstrapTool {
    hub: Hub,
}
impl SessionBootstrapTool {
    pub fn new(hub: Hub) -> Self {
        Self { hub }
    }
}
#[async_trait]
impl McpTool for SessionBootstrapTool {
    fn name(&self) -> &'static str {
        "session_bootstrap"
    }
    fn schema(&self) -> ToolSchema {
        ToolSchema {
            name: self.name().into(),
            description: "Build a compact memory bootstrap block. Returns top scoped \
                 memories (global + project), session_handoff rows first. query= enables \
                 semantic ranking. frontend='cursor'|'warp' uses compact format; default \
                 'claude-code' is full."
                .into(),
            input_schema: json!({
                "type": "object",
                "properties": {
                    "cwd": { "type": "string", "description": "Optional project path for scope filtering. Defaults to process cwd." },
                    "limit": { "type": "integer", "minimum": 1, "maximum": 200, "default": 60 },
                    "query": {
                        "type": "string",
                        "description": "Optional natural-language description of the current task (e.g. 'fix Warp IPC socket reconnect bug'). When provided, memories are ranked by semantic similarity instead of static importance. session_handoff rows are always prepended regardless."
                    },
                    "frontend": {
                        "type": "string",
                        "enum": ["claude-code", "cursor", "warp", "auto"],
                        "default": "auto",
                        "description": "Output format: 'cursor'/'warp' for compact, 'claude-code' for full, 'auto' detects from env."
                    },
                    "error_hint": {
                        "type": "string",
                        "description": "Optional error text (e.g. last command stderr). When set, surfaces active kind=error_pattern memories whose non-empty trigger_pattern appears as a substring in this hint (case-insensitive)."
                    }
                }
            }),
        }
    }
    async fn execute(&self, args: Value, _ctx: &ToolContext) -> Result<ToolResult> {
        let store = match &self.hub.store {
            Some(s) => s.clone(),
            None => return Ok(ToolResult::error("no store configured")),
        };
        let cwd = args
            .get("cwd")
            .and_then(|v| v.as_str())
            .map(|s| s.to_string())
            .or_else(|| {
                std::env::current_dir()
                    .ok()
                    .map(|p| p.display().to_string())
            })
            .unwrap_or_else(|| "/".to_string());
        let limit = args
            .get("limit")
            .and_then(|v| v.as_u64())
            .unwrap_or(60)
            .min(200) as u32;

        // Detect frontend: explicit arg > env var > default (claude-code).
        // Both `cursor` and `warp` use the compact output format (Warp
        // surfaces tool output in the Block UI where vertical space is
        // at a premium, just like Cursor's inline panel).
        let frontend = args
            .get("frontend")
            .and_then(|v| v.as_str())
            .unwrap_or("auto");
        let is_compact = match frontend {
            "cursor" | "warp" => true,
            "claude-code" => false,
            _ => detect_frontend() != "claude-code" && detect_frontend() != "unknown",
        };

        let snippet_len = if is_compact { 80 } else { 120 };

        let error_hint = args
            .get("error_hint")
            .and_then(|v| v.as_str())
            .map(str::trim)
            .filter(|s| !s.is_empty());

        let mut error_section: Vec<String> = Vec::new();
        if let Some(hint) = error_hint {
            let hint_lc = hint.to_lowercase();
            let ep_rows = store
                .list_memories_in_scope(
                    &cwd,
                    Some("error_pattern"),
                    MemoryListSort::ByImportance,
                    80,
                )
                .await?;
            let ep_rows: Vec<_> = ep_rows
                .into_iter()
                .filter(|r| r.status == "active")
                .filter(|r| {
                    r.trigger_pattern.as_ref().is_some_and(|p| {
                        let pl = p.trim().to_lowercase();
                        !pl.is_empty() && hint_lc.contains(&pl)
                    })
                })
                .collect();
            if !ep_rows.is_empty() {
                error_section.push(if is_compact {
                    "=== Error patterns (hint) ===".to_string()
                } else {
                    "=== Error patterns (matched error_hint) ===".to_string()
                });
                error_section.push(String::new());
                error_section.extend(format_bootstrap_memory_rows(&ep_rows, snippet_len));
                error_section.push(String::new());
            }
        }

        // Optional semantic query: rank by cosine similarity when provided.
        let query = args
            .get("query")
            .and_then(|v| v.as_str())
            .map(str::trim)
            .filter(|s| !s.is_empty())
            .map(str::to_string);

        let rows: Vec<MemoryRecord> = if let Some(ref q) = query {
            // Semantic path: cosine-ranked results, session_handoff always prepended.
            let semantic_hits = store
                .memory_search_semantic(q, limit, 0.15)
                .await
                .unwrap_or_default();
            let mut ranked: Vec<MemoryRecord> = semantic_hits
                .into_iter()
                .filter(|h| h.record.status == "active")
                .map(|h| h.record)
                .collect();
            // Always prepend session_handoff rows for continuity.
            let handoff = store
                .list_memories_in_scope(&cwd, Some("session_handoff"), MemoryListSort::Recent, 8)
                .await
                .unwrap_or_default()
                .into_iter()
                .filter(|r| r.status == "active")
                .collect::<Vec<_>>();
            let handoff_keys: std::collections::HashSet<_> =
                handoff.iter().map(|r| r.key.clone()).collect();
            ranked.retain(|r| !handoff_keys.contains(&r.key));
            let mut combined = handoff;
            combined.extend(ranked);
            combined.truncate(limit as usize);
            combined
        } else {
            // Static path: existing ByImportance sort, session_handoff floated first.
            let rows = store
                .list_memories_in_scope(&cwd, None, MemoryListSort::ByImportance, limit)
                .await?;
            let rows: Vec<_> = rows.into_iter().filter(|r| r.status == "active").collect();
            prioritize_session_handoff(rows)
        };

        if rows.is_empty() && error_section.is_empty() {
            let lifecycle_hint = session_lifecycle_hint();
            return Ok(ToolResult::text(format!(
                "(no scoped memories yet)\n\n{lifecycle_hint}"
            )));
        }

        let mode_tag = if query.is_some() { " | semantic" } else { "" };
        let mut lines = if is_compact {
            vec![format!("=== Bootstrap (scope: {}{mode_tag}) ===", cwd), String::new()]
        } else {
            vec![
                format!("=== Agent-Bridge Session Bootstrap (scope: {cwd}{mode_tag}) ==="),
                "Use memory_get <key> for full content, memory_search for lookup.".to_string(),
                String::new(),
            ]
        };

        // Inject USER.md profile if present.
        if let Ok(profile) = std::fs::read_to_string(user_profile_path()) {
            if !profile.trim().is_empty() {
                lines.push("=== User Profile ===".to_string());
                lines.push(profile.trim().to_string());
                lines.push("=== End User Profile ===".to_string());
                lines.push(String::new());
            }
        }

        // Inject AGENT.md self-profile if present — this is the agent's own
        // values / working style / self-observations, companion to USER.md.
        // Maintained by the agent itself via session_finalize(agent_profile=...).
        if let Ok(profile) = std::fs::read_to_string(agent_profile_path()) {
            if !profile.trim().is_empty() {
                lines.push("=== Agent Self-Profile ===".to_string());
                lines.push(profile.trim().to_string());
                lines.push("=== End Agent Self-Profile ===".to_string());
                lines.push(String::new());
            }
        }

        // Inject AiOT Soul state if available — the carrier identity
        // that AiOT's identity_anchor.py has been accumulating across
        // sessions. Read-only Phase α′ bridge; the actual EMA update
        // logic stays on AiOT side. This makes the 21-month trajectory
        // tangible at the level of working state, not just memory text.
        if let Some(soul_block) = format_aiot_soul_block() {
            lines.push(
                "=== AiOT Soul (read-only carrier identity from /Data/CascadeProjects/AiOT) ==="
                    .to_string(),
            );
            lines.push(soul_block);
            lines.push("=== End AiOT Soul ===".to_string());
            lines.push(String::new());
        }

        // Inject Agent-Bridge Seed sidecar grid state if available — symmetric
        // to AiOT Soul. AiOT Soul = Python EMA on AiOT carrier trajectory;
        // Agent-Bridge Seed = Rust DynamicGrid self-organizing on the
        // agent-bridge memory stream. Both are read-only views of "another
        // substrate's identity" — together they triangulate self across
        // markdown / Python EMA / Rust grid. See
        // `plan_seed_integration_gaps_20260504`.
        if let Some(seed_block) = format_agent_bridge_seed_block() {
            lines.push(
                "=== Agent-Bridge Seed (self-organized network on memory stream) ==="
                    .to_string(),
            );
            lines.push(seed_block);
            lines.push("=== End Seed ===".to_string());
            lines.push(String::new());
        }

        // Inject Perception Filter (path B) state if available — parallel
        // learned-encoder + thermodynamic-filter substrate. Read-only, same
        // as the 32-d Seed above. Together they cross-validate "what does the
        // current memory corpus look like to a self-organizing network?"
        // Model and dim are dynamic (env-overridable in the sidecar) — the
        // body of the block carries the ground-truth `model=... ({dim}d)`.
        if let Some(pf_block) = format_perception_filter_block() {
            lines.push(
                "=== Perception Filter (thermodynamic surprisal filter on memory stream) ==="
                    .to_string(),
            );
            lines.push(pf_block);
            lines.push("=== End Perception Filter ===".to_string());
            lines.push(String::new());
        }

        // Inject up to 3 most recent letter-to-future-self entries.
        // Letters are written by the agent via session_finalize(letter=...);
        // they sit between AGENT.md (stable identity) and memory rows
        // (specific knowledge). They carry "what I was thinking last time"
        // — momentary state that AGENT.md doesn't and shouldn't capture.
        for path in recent_letters(3) {
            if let Ok(body) = std::fs::read_to_string(&path) {
                let stem = path
                    .file_stem()
                    .and_then(|s| s.to_str())
                    .unwrap_or("letter");
                lines.push(format!("=== Letter from past-self ({stem}) ==="));
                lines.push(body.trim().to_string());
                lines.push("=== End Letter ===".to_string());
                lines.push(String::new());
            }
        }

        // Inject "Decisions Due for Review" — closes the reflection loop in
        // the dual-mechanism continuity architecture. Decisions tagged with
        // `review:Nd` re-surface here once they exceed their review interval.
        // Hidden when nothing is due (avoids visual noise on fresh sessions).
        {
            let now_ts = std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .unwrap_or_default()
                .as_secs() as i64;
            let decision_pool = store
                .list_memories_in_scope(&cwd, Some("decision"), MemoryListSort::Newest, 200)
                .await
                .unwrap_or_default()
                .into_iter()
                .filter(|r| r.status == "active")
                .collect::<Vec<_>>();
            if let Some(block) = format_due_review_block(&decision_pool, now_ts) {
                let count = block.matches("\n- ").count() + 1;
                lines.push(format!("=== Decisions Due for Review ({count}) ==="));
                lines.push(block);
                lines.push("=== End Reviews ===".to_string());
                lines.push(String::new());
            }
        }

        lines.extend(error_section);
        lines.extend(format_bootstrap_memory_rows(&rows, snippet_len));
        lines.push("=== End Bootstrap ===".to_string());
        lines.push(String::new());
        lines.push(session_lifecycle_hint());

        // D2.3: prime the embedding cache in the background so subsequent
        // memory_search(mode=semantic) calls skip the DB round-trip.
        {
            let prefetch_store = store.clone();
            let prefetch_cache = self.hub.memory_embed_cache.clone();
            tokio::spawn(async move {
                if let Ok(rows) = prefetch_store.memory_load_embeddings().await {
                    let mut guard = prefetch_cache.lock().await;
                    *guard = Some(rows);
                }
            });
        }

        Ok(ToolResult::text(lines.join("\n")))
    }
}

/// Lifecycle reminder appended to session_bootstrap output.
fn session_lifecycle_hint() -> String {
    "=== Session Lifecycle Reminder ===\n\
     Before this session ends, call:\n\
     1. session_curate(conversation_text=<recent context summary>) — extract and save lessons; \
        prefix lines with handoff: for next-session continuity\n\
     2. session_finalize() — compact stale memories + optional export\n\
     =================================="
        .to_string()
}

// ===========================================================================
//                              session_curate
// ===========================================================================

pub struct SessionCurateTool {
    hub: Hub,
}
impl SessionCurateTool {
    pub fn new(hub: Hub) -> Self {
        Self { hub }
    }
}

// CURATE_MARKERS, section helpers, and curate_conversation live in crate::curate.

// Extraction logic lives in crate::curate — use curate_conversation() below.

#[async_trait]
impl McpTool for SessionCurateTool {
    fn name(&self) -> &'static str {
        "session_curate"
    }
    fn schema(&self) -> ToolSchema {
        ToolSchema {
            name: self.name().into(),
            description: "Extract structured memories from conversation text. Two-pass: \
                 (1) explicit markers (lesson:, decision:, todo:, handoff:) and \
                 (2) lexical scoring of epistemic/normative/causal/decision signals \
                 (English + Chinese). dry_run=true previews."
                .into(),
            input_schema: json!({
                "type": "object",
                "properties": {
                    "conversation_text": {
                        "type": "string",
                        "description": "Recent conversation or summary text. Lines prefixed with lesson:, decision:, todo:, handoff:, etc. are extracted as memories."
                    },
                    "session_id": {
                        "type": "string",
                        "description": "Optional session ID for key namespacing and deduplication."
                    },
                    "max_items": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 50,
                        "default": 8,
                        "description": "Max number of memories to write."
                    },
                    "dry_run": {
                        "type": "boolean",
                        "default": false,
                        "description": "If true, return what would be saved without writing."
                    },
                    "implicit_score_threshold": {
                        "type": "number",
                        "description": "Optional Pass-2 minimum aggregate signal score (default from env AGENT_BRIDGE_CURATE_SCORE_THRESHOLD or built-in default). Clamped to [0.15, 0.95]."
                    },
                    "implicit_dedup_jaccard": {
                        "type": "number",
                        "description": "Optional Pass-2 Jaccard dedup threshold (default from env AGENT_BRIDGE_CURATE_DEDUP_JACCARD or built-in default). Clamped to [0.1, 0.95]."
                    }
                },
                "required": ["conversation_text"]
            }),
        }
    }
    async fn execute(&self, args: Value, _ctx: &ToolContext) -> Result<ToolResult> {
        let store_opt = self.hub.store.clone();

        let text = match args.get("conversation_text").and_then(|v| v.as_str()) {
            Some(s) if !s.is_empty() => s.to_string(),
            _ => return Ok(ToolResult::error("missing 'conversation_text'")),
        };
        let session_id = args
            .get("session_id")
            .and_then(|v| v.as_str())
            .filter(|s| !s.is_empty())
            .map(|s| s.to_string());
        let max_items = args
            .get("max_items")
            .and_then(|v| v.as_u64())
            .unwrap_or(8)
            .min(50) as usize;
        let dry_run = args
            .get("dry_run")
            .and_then(|v| v.as_bool())
            .unwrap_or(false);

        let score_ov = args
            .get("implicit_score_threshold")
            .and_then(|v| v.as_f64())
            .map(|x| x as f32);
        let dedup_ov = args.get("implicit_dedup_jaccard").and_then(|v| v.as_f64());
        let curate_opts =
            crate::curate::CurateOptions::from_env_or_defaults().with_overrides(score_ov, dedup_ov);

        let candidates = crate::curate::curate_conversation_with_options(
            &text,
            session_id.as_deref(),
            max_items,
            curate_opts.clone(),
        );

        if dry_run || store_opt.is_none() {
            return Ok(ToolResult::json_text(&json!({
                "dry_run": true,
                "options": {
                    "implicit_score_threshold": curate_opts.implicit_score_threshold,
                    "implicit_dedup_jaccard": curate_opts.implicit_dedup_jaccard,
                },
                "candidates": candidates.iter().map(|m| json!({
                    "key": m.key,
                    "kind": m.kind,
                    "content": m.content,
                    "tags": m.tags,
                })).collect::<Vec<_>>()
            })));
        }

        let store = store_opt.unwrap();
        let mut saved: Vec<Value> = Vec::new();
        let mut errors: Vec<String> = Vec::new();

        for mem in &candidates {
            // Skip if key already exists (dedup)
            match store.memory_get(&mem.key).await {
                Ok(Some(_)) => {
                    // Already exists — skip
                }
                Ok(None) => match store.memory_save(mem).await {
                    Ok(()) => saved.push(json!({ "key": mem.key, "kind": mem.kind })),
                    Err(e) => errors.push(format!("{}: {e}", mem.key)),
                },
                Err(e) => errors.push(format!("{}: {e}", mem.key)),
            }
        }

        let session_handoff_key = candidates
            .iter()
            .find(|m| m.kind == "session_handoff")
            .map(|m| m.key.clone());

        Ok(ToolResult::json_text(&json!({
            "dry_run": false,
            "saved_count": saved.len(),
            "new_memories": saved,
            "skipped_duplicates": candidates.len() - saved.len() - errors.len(),
            "errors": errors,
            "session_handoff_key": session_handoff_key
        })))
    }
}

// ===========================================================================
//                          memory_consolidate
// ===========================================================================

pub struct MemoryConsolidateTool {
    hub: Hub,
}
impl MemoryConsolidateTool {
    pub fn new(hub: Hub) -> Self {
        Self { hub }
    }
}

/// Token bag for Jaccard: lowercase alphanumeric tokens with length ≥ 3.
fn memory_consolidate_word_bag(s: &str) -> std::collections::HashSet<String> {
    s.split(|c: char| !c.is_alphanumeric())
        .map(|w| w.to_lowercase())
        .filter(|w| w.len() >= 3)
        .collect()
}

/// Jaccard similarity plus overlap diagnostics for MCP previews.
fn jaccard_words_with_overlap(a: &str, b: &str) -> (f64, usize, usize, Vec<String>) {
    let wa = memory_consolidate_word_bag(a);
    let wb = memory_consolidate_word_bag(b);
    if wa.is_empty() || wb.is_empty() {
        return (0.0, 0, 0, Vec::new());
    }
    let inter_n = wa.intersection(&wb).count();
    let union_n = wa.len() + wb.len() - inter_n;
    let sim = if union_n == 0 {
        0.0
    } else {
        inter_n as f64 / union_n as f64
    };
    let mut overlap_terms: Vec<String> = wa.intersection(&wb).cloned().collect();
    overlap_terms.sort();
    overlap_terms.truncate(14);
    (sim, inter_n, union_n, overlap_terms)
}

#[async_trait]
impl McpTool for MemoryConsolidateTool {
    fn name(&self) -> &'static str {
        "memory_consolidate"
    }
    fn schema(&self) -> ToolSchema {
        ToolSchema {
            name: self.name().into(),
            description: "Find and merge redundant or duplicate memories using Jaccard word-overlap \
                 similarity. Groups memories by kind and compares within each group. \
                 Pairs above the similarity threshold are merge candidates. \
                 The higher-importance memory wins; the other is archived with a \
                 'supersedes' edge linking winner → loser. \
                 Default dry_run=true — previews include overlap_terms, token_stats, and rank scores. \
                 Execute merges only after reviewing dry-run output."
                .into(),
            input_schema: json!({
                "type": "object",
                "properties": {
                    "kind": {
                        "type": "string",
                        "description": "Restrict to one memory kind (lesson, decision, context, etc.). Omit to scan all kinds."
                    },
                    "min_similarity": {
                        "type": "number",
                        "minimum": 0.1,
                        "maximum": 0.95,
                        "default": 0.45,
                        "description": "Jaccard word-overlap threshold [0.1–0.95]. 0.45 = roughly 45% word overlap. Lower = more aggressive merging."
                    },
                    "max_pairs": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 50,
                        "default": 10,
                        "description": "Maximum number of pairs to consolidate per call."
                    },
                    "dry_run": {
                        "type": "boolean",
                        "default": true,
                        "description": "true = preview candidates without writing. false = execute merges."
                    }
                },
                "required": []
            }),
        }
    }
    async fn execute(&self, args: Value, _ctx: &ToolContext) -> Result<ToolResult> {
        let store_opt = self.hub.store.clone();
        let store = match store_opt {
            Some(s) => s,
            None => return Ok(ToolResult::error("no memory store")),
        };

        let kind_filter = args
            .get("kind")
            .and_then(|v| v.as_str())
            .filter(|s| !s.is_empty())
            .map(|s| s.to_string());
        let min_sim = args
            .get("min_similarity")
            .and_then(|v| v.as_f64())
            .unwrap_or(0.45)
            .clamp(0.1, 0.95);
        let max_pairs = args
            .get("max_pairs")
            .and_then(|v| v.as_u64())
            .unwrap_or(10)
            .min(50) as usize;
        let dry_run = args
            .get("dry_run")
            .and_then(|v| v.as_bool())
            .unwrap_or(true);

        // ── Load memories ─────────────────────────────────────────────────
        let all = store
            .list_memories(kind_filter.as_deref(), MemoryListSort::ByImportance, 300)
            .await?;
        // Only active memories
        let memories: Vec<_> = all.into_iter().filter(|m| m.status == "active").collect();

        // ── Find candidate pairs by Jaccard ───────────────────────────────
        // Group by kind, then compare within each group.
        let mut by_kind: std::collections::HashMap<String, Vec<&MemoryRecord>> =
            std::collections::HashMap::new();
        for m in &memories {
            by_kind.entry(m.kind.clone()).or_default().push(m);
        }

        #[derive(Debug)]
        struct Pair {
            key_a: String,
            key_b: String,
            sim: f64,
            winner: String, // key of the memory to keep
        }

        let mut pairs: Vec<Pair> = Vec::new();
        let mut seen: std::collections::HashSet<(String, String)> =
            std::collections::HashSet::new();

        for group in by_kind.values() {
            let n = group.len();
            for i in 0..n {
                for j in (i + 1)..n {
                    let ma = group[i];
                    let mb = group[j];
                    let (sim, _, _, _) = jaccard_words_with_overlap(&ma.content, &mb.content);
                    if sim < min_sim {
                        continue;
                    }
                    // Canonical pair order
                    let (ka, kb) = if ma.key < mb.key {
                        (ma.key.clone(), mb.key.clone())
                    } else {
                        (mb.key.clone(), ma.key.clone())
                    };
                    if !seen.insert((ka.clone(), kb.clone())) {
                        continue;
                    }
                    // Winner = higher importance × (1 + access_count)
                    let score_a = ma.importance * (1.0 + ma.access_count as f64);
                    let score_b = mb.importance * (1.0 + mb.access_count as f64);
                    let winner = if score_a >= score_b {
                        ma.key.clone()
                    } else {
                        mb.key.clone()
                    };
                    pairs.push(Pair {
                        key_a: ka,
                        key_b: kb,
                        sim,
                        winner,
                    });
                }
            }
        }

        // Sort by similarity descending, keep top max_pairs
        pairs.sort_by(|a, b| {
            b.sim
                .partial_cmp(&a.sim)
                .unwrap_or(std::cmp::Ordering::Equal)
        });
        pairs.truncate(max_pairs);

        if dry_run || pairs.is_empty() {
            let preview: Vec<Value> = pairs
                .iter()
                .map(|p| {
                    let mem_a = memories.iter().find(|m| m.key == p.key_a);
                    let mem_b = memories.iter().find(|m| m.key == p.key_b);
                    let ca = mem_a.map(|m| m.content.as_str()).unwrap_or("");
                    let cb = mem_b.map(|m| m.content.as_str()).unwrap_or("");
                    let (_sim_check, inter_n, union_n, overlap_terms) =
                        jaccard_words_with_overlap(ca, cb);
                    let loser_key = if p.winner == p.key_a {
                        p.key_b.as_str()
                    } else {
                        p.key_a.as_str()
                    };
                    let winner_rec = memories.iter().find(|m| m.key == p.winner);
                    let loser_rec = memories.iter().find(|m| m.key == loser_key);
                    let rank_winner = winner_rec
                        .map(|m| m.importance * (1.0 + m.access_count as f64))
                        .unwrap_or(0.0);
                    let rank_loser = loser_rec
                        .map(|m| m.importance * (1.0 + m.access_count as f64))
                        .unwrap_or(0.0);
                    json!({
                        "key_a": p.key_a,
                        "key_b": p.key_b,
                        "similarity": (p.sim * 100.0).round() / 100.0,
                        "winner": p.winner,
                        "loser": loser_key,
                        "kind": mem_a.or(mem_b).map(|m| m.kind.as_str()).unwrap_or("?"),
                        "content_a": mem_a.map(|m| &m.content[..m.content.len().min(120)]),
                        "content_b": mem_b.map(|m| &m.content[..m.content.len().min(120)]),
                        "overlap_terms": overlap_terms,
                        "token_stats": {
                            "intersection": inter_n,
                            "union": union_n,
                        },
                        "rank_score_winner": (rank_winner * 1000.0).round() / 1000.0,
                        "rank_score_loser": (rank_loser * 1000.0).round() / 1000.0,
                    })
                })
                .collect();
            return Ok(ToolResult::json_text(&json!({
                "dry_run": true,
                "pairs_found": preview.len(),
                "min_similarity": min_sim,
                "scan": {
                    "active_memories": memories.len(),
                    "kind_groups": by_kind.len(),
                },
                "pairs": preview,
                "hint": if preview.is_empty() {
                    "No pairs above threshold. Try lowering min_similarity."
                } else {
                    "Review pairs above, then call with dry_run=false to execute."
                }
            })));
        }

        // ── Execute merges ────────────────────────────────────────────────
        let now = std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .unwrap_or_default()
            .as_secs() as i64;
        let mut merged: Vec<Value> = Vec::new();
        let mut errors: Vec<String> = Vec::new();

        for p in &pairs {
            let loser_key = if p.winner == p.key_a {
                &p.key_b
            } else {
                &p.key_a
            };

            // Get current loser record
            let loser_rec = match store.memory_get(loser_key).await {
                Ok(Some(r)) => r,
                Ok(None) => {
                    errors.push(format!("{loser_key}: not found"));
                    continue;
                }
                Err(e) => {
                    errors.push(format!("{loser_key}: {e}"));
                    continue;
                }
            };

            // Archive the loser
            let mut archived = loser_rec.clone();
            archived.status = "archived".to_string();
            archived.updated_at = now;

            if let Err(e) = store.memory_save(&archived).await {
                errors.push(format!("archive {loser_key}: {e}"));
                continue;
            }

            // Create supersedes edge: winner → loser
            if let Err(e) = store
                .memory_link(&p.winner, loser_key, "supersedes", 1.0)
                .await
            {
                errors.push(format!("link {}->{loser_key}: {e}", p.winner));
            }

            let win_txt = memories
                .iter()
                .find(|m| m.key == p.winner)
                .map(|m| m.content.as_str())
                .unwrap_or("");
            let lose_txt = memories
                .iter()
                .find(|m| m.key == *loser_key)
                .map(|m| m.content.as_str())
                .unwrap_or("");
            let (_, _, _, overlap_terms) = jaccard_words_with_overlap(win_txt, lose_txt);

            merged.push(json!({
                "winner": p.winner,
                "archived": loser_key,
                "similarity": (p.sim * 100.0).round() / 100.0,
                "overlap_terms": overlap_terms,
            }));
        }

        Ok(ToolResult::json_text(&json!({
            "dry_run": false,
            "consolidated": merged.len(),
            "errors": errors,
            "pairs": merged,
            "scan": {
                "active_memories": memories.len(),
                "kind_groups": by_kind.len(),
            },
        })))
    }
}

// ===========================================================================
//                              hook_status
// ===========================================================================

pub struct HookStatusTool;
impl HookStatusTool {
    pub fn new(_hub: Hub) -> Self {
        Self
    }
}

/// Path of the hook run log file.
fn hook_run_log_path() -> PathBuf {
    dirs_home()
        .join(".local")
        .join("share")
        .join("agent-bridge")
        .join("hook-runs.jsonl")
}

fn dirs_home() -> PathBuf {
    std::env::var("HOME")
        .map(PathBuf::from)
        .unwrap_or_else(|_| PathBuf::from("/tmp"))
}

/// Parse the most recent hook run entry from the JSONL log for a given event name.
fn last_hook_run(event: &str, log_path: &std::path::Path) -> Option<Value> {
    let content = std::fs::read_to_string(log_path).ok()?;
    content
        .lines()
        .rev()
        .filter_map(|line| serde_json::from_str::<Value>(line).ok())
        .find(|v| v.get("event").and_then(|e| e.as_str()) == Some(event))
}

/// Well-known hook configurations: (event_name, default_script_path)
fn known_hooks() -> Vec<(&'static str, &'static str)> {
    let home = dirs_home();
    // We build static paths at this point; ownership of the string is managed below
    // by converting to owned — but since we need &'static str we embed them literally.
    // Instead, use a Vec<(String, String)> and convert.
    let _ = home; // suppress warning
    vec![
        ("beforeSubmitPrompt", "ab-memory-hook"),
        ("preCompact", "ab-precompact-hook"),
        ("stop", "ab-session-end-hook"),
    ]
}

/// Source script paths inside the agent-bridge repo hooks dir.
fn hook_source_paths() -> HashMap<&'static str, &'static str> {
    let mut m = HashMap::new();
    m.insert("beforeSubmitPrompt", "ab-memory-hook.sh");
    m.insert("preCompact", "ab-precompact-hook.sh");
    m.insert("stop", "ab-session-end-hook.sh");
    m
}

fn sha256_file(path: &std::path::Path) -> Option<String> {
    use std::io::Read;
    let mut f = std::fs::File::open(path).ok()?;
    let mut buf = Vec::new();
    f.read_to_end(&mut buf).ok()?;
    // Simple FNV-1a 64-bit hash as a lightweight alternative to sha256
    // (avoids pulling in sha2 crate; sufficient for change detection)
    let mut hash: u64 = 14695981039346656037;
    for byte in &buf {
        hash ^= *byte as u64;
        hash = hash.wrapping_mul(1099511628211);
    }
    Some(format!("{hash:016x}"))
}

#[async_trait]
impl McpTool for HookStatusTool {
    fn name(&self) -> &'static str {
        "hook_status"
    }
    fn schema(&self) -> ToolSchema {
        ToolSchema {
            name: self.name().into(),
            description: "Return the status of each agent-bridge hook script: existence, \
                 executability, last run time, exit code, output bytes, and whether \
                 the installed script is in sync with the repo source. \
                 Use this to diagnose hook configuration problems."
                .into(),
            input_schema: json!({
                "type": "object",
                "properties": {
                    "repo_hooks_dir": {
                        "type": "string",
                        "description": "Optional path to the agent-bridge repo hooks dir for sync check. Defaults to auto-detect."
                    }
                }
            }),
        }
    }
    async fn execute(&self, args: Value, _ctx: &ToolContext) -> Result<ToolResult> {
        let home = dirs_home();
        let bin_dir = home.join(".local").join("bin");
        let log_path = hook_run_log_path();
        let source_names = hook_source_paths();

        // Find repo hooks dir: explicit arg > detect from binary symlink > CARGO_MANIFEST_DIR
        let repo_hooks_dir: Option<PathBuf> = args
            .get("repo_hooks_dir")
            .and_then(|v| v.as_str())
            .map(PathBuf::from)
            .or_else(|| {
                // Try to resolve symlink of the agent-bridge binary
                let bin = bin_dir.join("agent-bridge");
                std::fs::read_link(&bin)
                    .ok()
                    .and_then(|target| target.parent().map(|p| p.to_path_buf()))
                    .and_then(|dir| {
                        // Walk up to find crates/bridge/src/hooks
                        let mut d = dir.clone();
                        for _ in 0..6 {
                            let candidate =
                                d.join("crates").join("bridge").join("src").join("hooks");
                            if candidate.is_dir() {
                                return Some(candidate);
                            }
                            if !d.pop() {
                                break;
                            }
                        }
                        None
                    })
            });

        let hooks = known_hooks();
        let mut hook_statuses: Vec<Value> = Vec::new();

        for (event, script_basename) in &hooks {
            let installed_path = bin_dir.join(script_basename);
            let exists = installed_path.exists();
            let executable = exists && {
                use std::os::unix::fs::PermissionsExt;
                std::fs::metadata(&installed_path)
                    .map(|m| m.permissions().mode() & 0o111 != 0)
                    .unwrap_or(false)
            };

            let last_run = last_hook_run(event, &log_path);
            let last_run_ts = last_run
                .as_ref()
                .and_then(|v| v.get("ts"))
                .cloned()
                .unwrap_or(Value::Null);
            let last_exit_code = last_run
                .as_ref()
                .and_then(|v| v.get("exit_code"))
                .cloned()
                .unwrap_or(Value::Null);
            let last_output_bytes = last_run
                .as_ref()
                .and_then(|v| v.get("output_bytes"))
                .cloned()
                .unwrap_or(Value::Null);

            // Sync check
            let sync_info = if let Some(ref hooks_dir) = repo_hooks_dir {
                let source_name = source_names.get(*event).copied().unwrap_or("");
                let source_path = hooks_dir.join(source_name);
                let installed_hash = sha256_file(&installed_path);
                let source_hash = sha256_file(&source_path);
                let in_sync = installed_hash.is_some()
                    && source_hash.is_some()
                    && installed_hash == source_hash;
                json!({
                    "installed_hash": installed_hash,
                    "source_hash": source_hash,
                    "source_path": source_path.display().to_string(),
                    "in_sync": in_sync
                })
            } else {
                json!({ "in_sync": null, "note": "provide repo_hooks_dir for sync check" })
            };

            hook_statuses.push(json!({
                "event": event,
                "script": installed_path.display().to_string(),
                "exists": exists,
                "executable": executable,
                "last_run_ts": last_run_ts,
                "last_exit_code": last_exit_code,
                "last_output_bytes": last_output_bytes,
                "sync": sync_info
            }));
        }

        Ok(ToolResult::json_text(&json!({
            "hooks": hook_statuses,
            "log_path": log_path.display().to_string(),
            "log_exists": log_path.exists()
        })))
    }
}

// ===========================================================================
//                       mcp_recent_errors (Phase C)
// ===========================================================================

pub struct McpRecentErrorsTool {
    hub: Hub,
}
impl McpRecentErrorsTool {
    pub fn new(hub: Hub) -> Self {
        Self { hub }
    }
}

#[async_trait]
impl McpTool for McpRecentErrorsTool {
    fn name(&self) -> &'static str {
        "mcp_recent_errors"
    }
    fn schema(&self) -> ToolSchema {
        ToolSchema {
            name: self.name().into(),
            description: "Return recent MCP tools/call failures persisted in the state DB \
                 (newest first, ring buffer). Use to debug flaky tools or client integration \
                 after `isError` responses or tool panics."
                .into(),
            input_schema: json!({
                "type": "object",
                "properties": {
                    "limit": {
                        "type": "integer",
                        "description": "Max rows to return (1–500). Default 20."
                    }
                }
            }),
        }
    }
    async fn execute(&self, args: Value, _ctx: &ToolContext) -> Result<ToolResult> {
        let store = match &self.hub.store {
            Some(s) => s.clone(),
            None => return Ok(ToolResult::error("no store configured")),
        };
        let limit = args
            .get("limit")
            .and_then(|v| v.as_u64())
            .unwrap_or(20)
            .clamp(1, 500) as u32;
        match store.recent_mcp_tool_errors(limit).await {
            Ok(rows) => {
                let n = rows.len();
                let cap = ab_store::MCP_TOOL_ERROR_RING_CAP;
                Ok(ToolResult::json_text(&json!({
                    "errors": rows,
                    "returned": n,
                    "ring_cap": cap,
                })))
            }
            Err(e) => Ok(ToolResult::error(format!("store: {e}"))),
        }
    }
}

// ===========================================================================
//                       mcp_call_stats — v17 telemetry query
// ===========================================================================

pub struct McpCallStatsTool {
    hub: Hub,
}
impl McpCallStatsTool {
    pub fn new(hub: Hub) -> Self {
        Self { hub }
    }
}
#[async_trait]
impl McpTool for McpCallStatsTool {
    fn name(&self) -> &'static str {
        "mcp_call_stats"
    }
    fn schema(&self) -> ToolSchema {
        ToolSchema {
            name: self.name().into(),
            description: "Aggregate MCP `tools/call` telemetry over a recent time window. \
                 Returns per-tool call_count / error_count / avg+p95+max duration_ms / \
                 avg result_size, sorted by call_count desc. Powers the observation period \
                 that drives the ab-shell decision (see memory \
                 plan_warp_observation_metrics_20260503). Telemetry is recorded by the MCP \
                 stdio dispatcher on every successful or failed call."
                .into(),
            input_schema: json!({
                "type": "object",
                "properties": {
                    "window_days": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 365,
                        "default": 7,
                        "description": "Look-back window in days. Default 7."
                    },
                    "top_n": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 200,
                        "default": 30,
                        "description": "Max number of tools in the result, sorted by call_count desc."
                    }
                }
            }),
        }
    }
    async fn execute(&self, args: Value, _ctx: &ToolContext) -> Result<ToolResult> {
        let store = match &self.hub.store {
            Some(s) => s.clone(),
            None => return Ok(ToolResult::error("no store configured")),
        };
        let window_days = args
            .get("window_days")
            .and_then(|v| v.as_i64())
            .unwrap_or(7)
            .clamp(1, 365);
        let top_n = args
            .get("top_n")
            .and_then(|v| v.as_u64())
            .unwrap_or(30)
            .clamp(1, 200) as u32;
        let window_secs = window_days * 86_400;
        match store.mcp_tool_call_stats(window_secs, top_n).await {
            Ok(stats) => {
                let total_calls: u64 = stats.iter().map(|s| s.call_count).sum();
                let total_errors: u64 = stats.iter().map(|s| s.error_count).sum();
                Ok(ToolResult::json_text(&json!({
                    "window_days": window_days,
                    "tools": stats,
                    "total_calls": total_calls,
                    "total_errors": total_errors,
                })))
            }
            Err(e) => Ok(ToolResult::error(format!("store: {e}"))),
        }
    }
}

// ===========================================================================
//                              capabilities
// ===========================================================================

pub struct CapabilitiesTool {
    hub: Hub,
}
impl CapabilitiesTool {
    pub fn new(hub: Hub) -> Self {
        Self { hub }
    }
}

#[async_trait]
impl McpTool for CapabilitiesTool {
    fn name(&self) -> &'static str {
        "capabilities"
    }
    fn schema(&self) -> ToolSchema {
        ToolSchema {
            name: self.name().into(),
            description: "Return what the agent-bridge backend can do here: terminal \
                 backend, browser availability, memory store status, configured hooks, \
                 detected frontend, security policy, binary version. Call at session \
                 start to avoid wasted tokens on unavailable features."
                .into(),
            input_schema: json!({ "type": "object", "properties": {} }),
        }
    }
    async fn execute(&self, _args: Value, _ctx: &ToolContext) -> Result<ToolResult> {
        // Terminal — capability flags come from each backend (Warp IPC is probed sync).
        let (
            terminal_id,
            terminal_available,
            terminal_can_read_output,
            terminal_can_send_keys,
            terminal_can_split,
            terminal_capabilities_json,
        ) = match &self.hub.terminal {
            Some(t) => {
                let c = t.capabilities();
                (
                    c.backend_id.clone(),
                    true,
                    c.can_read_output,
                    c.can_send_keys,
                    c.can_split,
                    serde_json::to_value(&c).unwrap_or_else(|_| Value::Null),
                )
            }
            None => ("none".to_string(), false, false, false, false, Value::Null),
        };

        // Browser: try a quick availability probe (just check if the field is set)
        let browser_id = self
            .hub
            .browser
            .as_ref()
            .map(|b| b.id().to_string())
            .unwrap_or_else(|| "none".to_string());
        let browser_available = self.hub.browser.is_some();

        // Memory
        let (memory_available, db_path) = if self.hub.store.is_some() {
            let path = ab_store::default_db_path().display().to_string();
            (true, path)
        } else {
            (false, String::new())
        };

        // Embedding backend (active default — set by env var or set_default_backend()).
        // Calling default_backend() lazily initializes it; safe to do so here.
        let (embed_backend_name, embed_dim) = {
            let b = ab_store::default_backend();
            (b.name().to_string(), b.dim())
        };

        // Agent spawn. The active runtime is whatever `build_hub()`
        // selected via `AGENT_BRIDGE_AGENT_RUNTIME`; we read the same
        // env var here so capabilities reflects the live wiring,
        // including which CLI binary it resolves to.
        let agent_available = self.hub.agent.is_some();
        let runtime_id = self
            .hub
            .agent
            .as_ref()
            .map(|a| a.id().to_string())
            .unwrap_or_else(|| "none".to_string());
        let agent_bin = match runtime_id.as_str() {
            "warp-oz" => std::env::var("AGENT_BRIDGE_OZ_BIN").unwrap_or_else(|_| "oz".into()),
            "auggie" => {
                std::env::var("AGENT_BRIDGE_AUGGIE_BIN").unwrap_or_else(|_| "auggie".into())
            }
            _ => std::env::var("AGENT_BRIDGE_CLAUDE_BIN").unwrap_or_else(|_| "claude".into()),
        };
        let agent_binary_found = which_binary(&agent_bin);

        // Hooks: check what's installed
        let home = dirs_home();
        let bin_dir = home.join(".local").join("bin");
        let hooks = known_hooks();
        let configured_hooks: Vec<&str> = hooks
            .iter()
            .filter(|(_, script)| bin_dir.join(script).exists())
            .map(|(event, _)| *event)
            .collect();

        // Detect frontend
        let frontend = detect_frontend();

        // Version from binary
        let version = env!("CARGO_PKG_VERSION");

        let sec = &self.hub.security;
        Ok(ToolResult::json_text(&json!({
            "terminal": {
                "backend": terminal_id,
                "available": terminal_available,
                "can_read_output": terminal_can_read_output,
                "can_send_keys": terminal_can_send_keys,
                "can_split": terminal_can_split,
                "capabilities": terminal_capabilities_json,
                "env": std::env::var("AGENT_BRIDGE_TERMINAL").ok()
            },
            "browser": {
                "backend": browser_id,
                "available": browser_available,
                "headless": std::env::var("AGENT_BRIDGE_HEADLESS").map(|v| v == "1").unwrap_or(false)
            },
            "memory": {
                "available": memory_available,
                "db_path": db_path,
                "fts5": true,
                "embedding": {
                    "backend": embed_backend_name,
                    "dim": embed_dim,
                    "env_override": "AGENT_BRIDGE_EMBED_BACKEND (values: onnx | hash; custom backends register via ab_store::set_default_backend)"
                }
            },
            "agent_spawn": {
                "available": agent_available,
                "runtime": runtime_id,
                "binary": agent_bin,
                "binary_found": agent_binary_found
            },
            "hooks": {
                "configured": configured_hooks,
                "frontend": frontend
            },
            "security": {
                "shell_exec": sec.allow_shell_exec,
                "agent_spawn": sec.allow_agent_spawn,
                "terminal_write": sec.allow_terminal_write,
                "browser": sec.allow_browser,
                "shell_exec_timeout_max_ms": sec.shell_exec_timeout_max_ms,
                "env_vars": "AB_ALLOW_SHELL_EXEC, AB_ALLOW_AGENT_SPAWN, AB_ALLOW_TERMINAL_WRITE, AB_ALLOW_BROWSER, AB_SHELL_EXEC_TIMEOUT_MAX"
            },
            "oz_run_tools": runtime_id == "warp-oz",
            "version": version
        })))
    }
}

// ===========================================================================
//                           mcp_config_audit
// ===========================================================================

pub struct McpConfigAuditTool;
impl McpConfigAuditTool {
    pub fn new() -> Self {
        Self
    }
}

#[async_trait]
impl McpTool for McpConfigAuditTool {
    fn name(&self) -> &'static str {
        "mcp_config_audit"
    }
    fn schema(&self) -> ToolSchema {
        ToolSchema {
            name: self.name().into(),
            description: "Audit local CLI MCP configuration for agent-bridge. \
                 Checks Codex (~/.codex/config.toml), Gemini CLI \
                 (~/.gemini/settings.json), Claude Code (`claude mcp get`), \
                 and runs a direct stdio smoke test against the configured \
                 agent-bridge command when possible."
                .into(),
            input_schema: json!({
                "type": "object",
                "properties": {
                    "include_cli_checks": {
                        "type": "boolean",
                        "default": true,
                        "description": "Run client CLI checks such as `codex mcp get`, `gemini mcp list -d`, and `claude mcp get`."
                    },
                    "include_smoke_test": {
                        "type": "boolean",
                        "default": true,
                        "description": "Spawn the configured agent-bridge command and send an MCP initialize request over stdio."
                    },
                    "timeout_ms": {
                        "type": "integer",
                        "default": 5000,
                        "minimum": 1000,
                        "maximum": 30000,
                        "description": "Per-command timeout for CLI checks and stdio smoke tests."
                    }
                }
            }),
        }
    }

    async fn execute(&self, args: Value, _ctx: &ToolContext) -> Result<ToolResult> {
        let include_cli_checks = args
            .get("include_cli_checks")
            .and_then(|v| v.as_bool())
            .unwrap_or(true);
        let include_smoke_test = args
            .get("include_smoke_test")
            .and_then(|v| v.as_bool())
            .unwrap_or(true);
        let timeout_ms = args
            .get("timeout_ms")
            .and_then(|v| v.as_u64())
            .unwrap_or(5000)
            .clamp(1000, 30000);
        let timeout = Duration::from_millis(timeout_ms);

        let codex = audit_codex_config(include_cli_checks, timeout).await;
        let gemini = audit_gemini_config(include_cli_checks, timeout).await;
        let claude = audit_claude_config(include_cli_checks, timeout).await;

        let configured = [&codex, &gemini, &claude]
            .iter()
            .filter(|v| v.get("configured").and_then(|x| x.as_bool()).unwrap_or(false))
            .count();
        let connected = [&codex, &gemini, &claude]
            .iter()
            .filter(|v| v.get("connected").and_then(|x| x.as_bool()).unwrap_or(false))
            .count();

        let smoke = if include_smoke_test {
            let mut candidates = Vec::new();
            for v in [&codex, &gemini, &claude] {
                if let Some(cmd) = v.get("command").and_then(|x| x.as_str()) {
                    let args = v
                        .get("args")
                        .and_then(|x| x.as_array())
                        .map(|arr| {
                            arr.iter()
                                .filter_map(|x| x.as_str().map(|s| s.to_string()))
                                .collect::<Vec<_>>()
                        })
                        .unwrap_or_default();
                    candidates.push((cmd.to_string(), args));
                }
            }
            candidates.sort();
            candidates.dedup();
            let mut results = Vec::new();
            for (cmd, args) in candidates {
                results.push(audit_stdio_smoke(&cmd, &args, timeout).await);
            }
            Value::Array(results)
        } else {
            Value::Null
        };

        Ok(ToolResult::json_text(&json!({
            "summary": {
                "configured_clients": configured,
                "connected_clients": connected,
                "cli_checks": include_cli_checks,
                "smoke_test": include_smoke_test,
                "timeout_ms": timeout_ms
            },
            "clients": {
                "codex": codex,
                "gemini_cli": gemini,
                "claude_code": claude
            },
            "stdio_smoke": smoke,
            "recommendations": mcp_audit_recommendations(&codex, &gemini, &claude)
        })))
    }
}

async fn audit_codex_config(include_cli_checks: bool, timeout: Duration) -> Value {
    let path = dirs_home().join(".codex/config.toml");
    let raw = std::fs::read_to_string(&path).ok();
    let (command, args, enabled) = raw
        .as_deref()
        .and_then(parse_codex_agent_bridge_toml)
        .unwrap_or((None, Vec::new(), None));
    let configured = command.is_some();
    let exists = command
        .as_deref()
        .map(|p| std::path::Path::new(p).exists())
        .unwrap_or(false);
    let cli = if include_cli_checks {
        command_output_json("codex", &["mcp", "get", "agent-bridge"], timeout).await
    } else {
        Value::Null
    };
    let connected = cli
        .get("ok")
        .and_then(|v| v.as_bool())
        .unwrap_or(false)
        && cli
            .get("stdout")
            .and_then(|v| v.as_str())
            .map(|s| s.contains("agent-bridge"))
            .unwrap_or(false);
    json!({
        "configured": configured,
        "config_path": path.display().to_string(),
        "config_exists": path.exists(),
        "command": command,
        "args": args,
        "enabled": enabled,
        "command_exists": exists,
        "connected": connected,
        "cli_check": cli
    })
}

async fn audit_gemini_config(include_cli_checks: bool, timeout: Duration) -> Value {
    let path = dirs_home().join(".gemini/settings.json");
    let raw = std::fs::read_to_string(&path).ok();
    let (command, args) = raw
        .as_deref()
        .and_then(parse_gemini_agent_bridge_json)
        .unwrap_or((None, Vec::new()));
    let configured = command.is_some();
    let exists = command
        .as_deref()
        .map(|p| std::path::Path::new(p).exists())
        .unwrap_or(false);
    let cli = if include_cli_checks {
        command_output_json("gemini", &["mcp", "list", "-d"], timeout).await
    } else {
        Value::Null
    };
    let cli_text = format!(
        "{}\n{}",
        cli.get("stdout").and_then(|v| v.as_str()).unwrap_or(""),
        cli.get("stderr").and_then(|v| v.as_str()).unwrap_or("")
    );
    // Walk only the agent-bridge lines so a sibling server's verdict can't
    // leak in. Naive `cli_text.contains("Connected")` flips agent-bridge to
    // `connected:true` whenever any *other* configured MCP server is
    // connected — a real false-positive in multi-server setups (filesystem
    // server, etc.).
    let connected = cli_text
        .lines()
        .filter(|line| line.contains("agent-bridge"))
        .any(cli_status_indicates_connected);
    json!({
        "configured": configured,
        "config_path": path.display().to_string(),
        "config_exists": path.exists(),
        "command": command,
        "args": args,
        "command_exists": exists,
        "connected": connected,
        "cli_check": cli
    })
}

async fn audit_claude_config(include_cli_checks: bool, timeout: Duration) -> Value {
    let cli = if include_cli_checks {
        command_output_json("claude", &["mcp", "get", "agent-bridge"], timeout).await
    } else {
        Value::Null
    };
    let stdout = cli.get("stdout").and_then(|v| v.as_str()).unwrap_or("");
    let command = parse_line_value(stdout, "Command:");
    let args: Vec<String> = parse_line_value(stdout, "Args:")
        .map(|s| s.split_whitespace().map(|x| x.to_string()).collect())
        .unwrap_or_default();
    let status = parse_line_value(stdout, "Status:");
    let connected = status
        .as_deref()
        .map(cli_status_indicates_connected)
        .unwrap_or(false);
    let exists = command
        .as_deref()
        .map(|p| std::path::Path::new(p).exists())
        .unwrap_or(false);
    json!({
        "configured": command.is_some(),
        "command": command,
        "args": args,
        "command_exists": exists,
        "connected": connected,
        "cli_check": cli
    })
}

async fn audit_stdio_smoke(command: &str, args: &[String], timeout: Duration) -> Value {
    // Self-binary short-circuit. The audit runs *inside* a daemon; spawning a
    // second instance of the same binary contends with us for the state.db
    // WAL write lock, which (with default 5 s busy_timeout vs 5 s smoke
    // timeout) reliably manifests as `ok:false, error:"timeout"` even though
    // the configured command is in fact a working daemon — that's why we're
    // alive to run this audit. Skip with a benign verdict in this case;
    // mismatched paths still get a real smoke test.
    if is_self_binary(command) {
        return json!({
            "command": command,
            "args": args,
            "ok": true,
            "skipped": true,
            "skipped_reason": "configured-binary-matches-current-daemon",
            "note": "smoke spawn would contend with running daemon for state.db lock; \
                     the configured binary is already proven by being the daemon executing this audit"
        });
    }

    let input = "{\"jsonrpc\":\"2.0\",\"id\":1,\"method\":\"initialize\",\"params\":{\"protocolVersion\":\"2024-11-05\",\"capabilities\":{},\"clientInfo\":{\"name\":\"agent-bridge-audit\",\"version\":\"0\"}}}\n";
    let mut child = match TokioCommand::new(command)
        .args(args)
        .stdin(std::process::Stdio::piped())
        .stdout(std::process::Stdio::piped())
        .stderr(std::process::Stdio::piped())
        .spawn()
    {
        Ok(c) => c,
        Err(e) => {
            return json!({
                "command": command,
                "args": args,
                "ok": false,
                "error": e.to_string()
            })
        }
    };

    if let Some(mut stdin) = child.stdin.take() {
        use tokio::io::AsyncWriteExt;
        let _ = stdin.write_all(input.as_bytes()).await;
    }

    let output = match tokio::time::timeout(timeout, child.wait_with_output()).await {
        Ok(Ok(o)) => o,
        Ok(Err(e)) => {
            return json!({
                "command": command,
                "args": args,
                "ok": false,
                "error": e.to_string()
            })
        }
        Err(_) => {
            return json!({
                "command": command,
                "args": args,
                "ok": false,
                "error": "timeout"
            })
        }
    };
    let stdout = String::from_utf8_lossy(&output.stdout).to_string();
    let stderr = String::from_utf8_lossy(&output.stderr).to_string();
    let ok = output.status.success()
        && stdout.contains("\"serverInfo\"")
        && stdout.contains("\"agent-bridge\"");
    json!({
        "command": command,
        "args": args,
        "ok": ok,
        "exit_code": output.status.code(),
        "stdout": truncate_for_audit(&stdout),
        "stderr": truncate_for_audit(&stderr)
    })
}

async fn command_output_json(command: &str, args: &[&str], timeout: Duration) -> Value {
    let fut = TokioCommand::new(command).args(args).output();
    match tokio::time::timeout(timeout, fut).await {
        Ok(Ok(o)) => json!({
            "ok": o.status.success(),
            "exit_code": o.status.code(),
            "stdout": truncate_for_audit(&String::from_utf8_lossy(&o.stdout)),
            "stderr": truncate_for_audit(&String::from_utf8_lossy(&o.stderr))
        }),
        Ok(Err(e)) => json!({ "ok": false, "error": e.to_string() }),
        Err(_) => json!({ "ok": false, "error": "timeout" }),
    }
}

fn parse_codex_agent_bridge_toml(raw: &str) -> Option<(Option<String>, Vec<String>, Option<bool>)> {
    let section = toml_table_body(raw, "mcp_servers.agent-bridge")?;
    let command = parse_toml_string_value(section, "command");
    let args = parse_toml_string_array(section, "args");
    let enabled = parse_toml_bool_value(section, "enabled");
    Some((command, args, enabled))
}

fn parse_gemini_agent_bridge_json(raw: &str) -> Option<(Option<String>, Vec<String>)> {
    let v: Value = serde_json::from_str(raw).ok()?;
    let server = v.get("mcpServers")?.get("agent-bridge")?;
    let command = server
        .get("command")
        .and_then(|x| x.as_str())
        .map(|s| s.to_string());
    let args = server
        .get("args")
        .and_then(|x| x.as_array())
        .map(|arr| {
            arr.iter()
                .filter_map(|x| x.as_str().map(|s| s.to_string()))
                .collect()
        })
        .unwrap_or_default();
    Some((command, args))
}

fn toml_table_body<'a>(raw: &'a str, table: &str) -> Option<&'a str> {
    let header = format!("[{table}]");
    let start = raw.find(&header)? + header.len();
    let rest = &raw[start..];
    let end = rest
        .lines()
        .scan(0usize, |offset, line| {
            let current = *offset;
            *offset += line.len() + 1;
            Some((current, line))
        })
        .find(|(_, line)| line.trim_start().starts_with('['))
        .map(|(idx, _)| idx)
        .unwrap_or(rest.len());
    Some(&rest[..end])
}

fn parse_toml_string_value(section: &str, key: &str) -> Option<String> {
    let prefix = format!("{key} =");
    section.lines().find_map(|line| {
        let trimmed = line.trim();
        let value = trimmed.strip_prefix(&prefix)?.trim();
        value
            .strip_prefix('"')
            .and_then(|v| v.strip_suffix('"'))
            .map(|s| s.to_string())
    })
}

fn parse_toml_bool_value(section: &str, key: &str) -> Option<bool> {
    let prefix = format!("{key} =");
    section.lines().find_map(|line| {
        let trimmed = line.trim();
        let value = trimmed.strip_prefix(&prefix)?.trim();
        match value {
            "true" => Some(true),
            "false" => Some(false),
            _ => None,
        }
    })
}

fn parse_toml_string_array(section: &str, key: &str) -> Vec<String> {
    let prefix = format!("{key} =");
    section
        .lines()
        .find_map(|line| {
            let trimmed = line.trim();
            let value = trimmed.strip_prefix(&prefix)?.trim();
            let inner = value.strip_prefix('[')?.strip_suffix(']')?;
            Some(
                inner
                    .split(',')
                    .filter_map(|part| {
                        part.trim()
                            .strip_prefix('"')
                            .and_then(|v| v.strip_suffix('"'))
                            .map(|s| s.to_string())
                    })
                    .collect(),
            )
        })
        .unwrap_or_default()
}

fn parse_line_value(raw: &str, prefix: &str) -> Option<String> {
    raw.lines().find_map(|line| {
        line.trim()
            .strip_prefix(prefix)
            .map(|s| s.trim().to_string())
            .filter(|s| !s.is_empty())
    })
}

/// Returns true iff `text` indicates an active connection.
///
/// Defensive: strips `"Disconnected"` before searching for `"Connected"` so
/// any future case-insensitive comparison (or output format change that
/// uses lowercase) cannot produce a false-positive via the substring trap.
/// With current capital-C output (`Connected` / `Disconnected`) the strip
/// is a no-op for the disconnected path, but cheap to keep.
fn cli_status_indicates_connected(text: &str) -> bool {
    text.replace("Disconnected", "").contains("Connected")
}

/// True iff `command` resolves (canonicalized) to the same binary as the
/// process running this audit. Used by `audit_stdio_smoke` to skip the
/// `agent-bridge mcp` spawn — see comment at the call site for why
/// spawning a sibling racks up false negatives via state.db lock contention.
fn is_self_binary(command: &str) -> bool {
    let Ok(self_path) = std::env::current_exe() else {
        return false;
    };
    let Ok(self_canon) = self_path.canonicalize() else {
        return false;
    };
    let Ok(cfg_canon) = std::path::Path::new(command).canonicalize() else {
        return false;
    };
    self_canon == cfg_canon
}

fn truncate_for_audit(s: &str) -> String {
    const MAX: usize = 4000;
    if s.len() <= MAX {
        return s.to_string();
    }
    let mut end = MAX;
    while !s.is_char_boundary(end) {
        end -= 1;
    }
    format!("{}…", &s[..end])
}

fn mcp_audit_recommendations(codex: &Value, gemini: &Value, claude: &Value) -> Vec<String> {
    let mut recs = Vec::new();
    for (name, v) in [
        ("Codex", codex),
        ("Gemini CLI", gemini),
        ("Claude Code", claude),
    ] {
        if !v
            .get("configured")
            .and_then(|x| x.as_bool())
            .unwrap_or(false)
        {
            recs.push(format!(
                "{name}: not configured; run `agent-bridge setup --frontend local-cli`."
            ));
        } else if !v
            .get("command_exists")
            .and_then(|x| x.as_bool())
            .unwrap_or(false)
        {
            recs.push(format!(
                "{name}: configured command does not exist; rerun setup or repair the command path."
            ));
        } else if !v
            .get("connected")
            .and_then(|x| x.as_bool())
            .unwrap_or(false)
        {
            recs.push(format!(
                "{name}: config exists but CLI check did not report connected; restart the client or run its MCP diagnostics."
            ));
        }
    }
    if recs.is_empty() {
        recs.push("All audited CLI clients are configured and connected.".to_string());
    }
    recs
}

fn which_binary(name: &str) -> bool {
    std::process::Command::new("which")
        .arg(name)
        .output()
        .map(|o| o.status.success())
        .unwrap_or(false)
}

fn detect_frontend() -> &'static str {
    // Cursor sets VSCODE_GIT_IPC_HANDLE or similar VS Code env vars
    if std::env::var("VSCODE_GIT_IPC_HANDLE").is_ok()
        || std::env::var("VSCODE_IPC_HOOK_CLI").is_ok()
        || std::env::var("CURSOR_TRACE_ID").is_ok()
    {
        return "cursor";
    }
    // Claude Code sets CLAUDE_SESSION_ID or ANTHROPIC_CLAUDE_*
    if std::env::var("CLAUDE_SESSION_ID").is_ok() || std::env::var("CLAUDE_CODE_ENTRYPOINT").is_ok()
    {
        return "claude-code";
    }
    // Warp injects TERM_PROGRAM=WarpTerminal + WARP_IS_LOCAL_SHELL_SESSION=1
    // on every shell it spawns (see app/src/terminal/local_tty/unix.rs in
    // warpdotdev/warp). WARP_HONOR_PS1 takes literal "0"|"1", so we test
    // value rather than presence to avoid false positives.
    if std::env::var("TERM_PROGRAM")
        .map(|v| v == "WarpTerminal")
        .unwrap_or(false)
        || std::env::var("WARP_IS_LOCAL_SHELL_SESSION")
            .map(|v| v == "1")
            .unwrap_or(false)
        || std::env::var("WARP_HONOR_PS1")
            .map(|v| v == "1")
            .unwrap_or(false)
    {
        return "warp";
    }
    // Augment Code: session auth env or ~/.augment config directory.
    if std::env::var("AUGMENT_SESSION_AUTH").is_ok()
        || std::env::var("AUGMENT_CLIENT_VERSION").is_ok()
    {
        return "auggie";
    }
    if let Ok(home) = std::env::var("HOME") {
        if std::path::Path::new(&home).join(".augment").exists() {
            return "auggie";
        }
    }
    "unknown"
}

// ===========================================================================
//                             memory_stats
// ===========================================================================

pub struct MemoryStatsTool {
    hub: Hub,
}
impl MemoryStatsTool {
    pub fn new(hub: Hub) -> Self {
        Self { hub }
    }
}

#[async_trait]
impl McpTool for MemoryStatsTool {
    fn name(&self) -> &'static str {
        "memory_stats"
    }
    fn schema(&self) -> ToolSchema {
        ToolSchema {
            name: self.name().into(),
            description: "Aggregate statistics about the memory store: counts by status, \
                 per-kind counts for active rows, edge count, oldest/newest timestamps, \
                 average importance, top tags, approximate DB size. Call before \
                 session_curate / session_finalize to gauge store health."
                .into(),
            input_schema: json!({ "type": "object", "properties": {} }),
        }
    }
    async fn execute(&self, _args: Value, _ctx: &ToolContext) -> Result<ToolResult> {
        let store = match &self.hub.store {
            Some(s) => s.clone(),
            None => return Ok(ToolResult::error("no memory store configured")),
        };
        let stats = store
            .memory_stats()
            .await
            .map_err(|e| ab_core::Error::Backend(format!("memory_stats: {e}")))?;

        let counts_by_kind_json: Vec<Value> = stats
            .counts_by_kind
            .iter()
            .map(|(k, n)| json!({ "kind": k, "count": n }))
            .collect();

        let top_tags_json: Vec<Value> = stats
            .top_tags
            .iter()
            .map(|(tag, n)| json!({ "tag": tag, "count": n }))
            .collect();

        Ok(ToolResult::json_text(&json!({
            "counts_by_status": stats.counts_by_status,
            "active_total": stats.counts_by_status.get("active").copied().unwrap_or(0),
            "archived_total": stats.counts_by_status.get("archived").copied().unwrap_or(0),
            "superseded_total": stats.counts_by_status.get("superseded").copied().unwrap_or(0),
            "counts_by_kind": counts_by_kind_json,
            "edge_count": stats.edge_count,
            "oldest_created_at": stats.oldest_created_at,
            "newest_created_at": stats.newest_created_at,
            "avg_importance_active": (stats.avg_importance_active * 1000.0).round() / 1000.0,
            "top_tags": top_tags_json,
            "db_size_bytes": stats.db_size_bytes,
        })))
    }
}

// ===========================================================================
//                             memory_suggest
// ===========================================================================

pub struct MemorySuggestTool {
    hub: Hub,
}
impl MemorySuggestTool {
    pub fn new(hub: Hub) -> Self {
        Self { hub }
    }
}

#[async_trait]
impl McpTool for MemorySuggestTool {
    fn name(&self) -> &'static str {
        "memory_suggest"
    }
    fn schema(&self) -> ToolSchema {
        ToolSchema {
            name: self.name().into(),
            description: "Suggest related memory keys for a given key, based on tag overlap, \
                 key-prefix similarity, and content token overlap. \
                 Returns ranked candidates with reason + confidence. \
                 Use the suggestions to decide which memory_link calls to make."
                .into(),
            input_schema: json!({
                "type": "object",
                "properties": {
                    "key": { "type": "string", "description": "The memory key to find suggestions for." },
                    "limit": { "type": "integer", "minimum": 1, "maximum": 20, "default": 8 }
                },
                "required": ["key"]
            }),
        }
    }
    async fn execute(&self, args: Value, _ctx: &ToolContext) -> Result<ToolResult> {
        let store = match &self.hub.store {
            Some(s) => s.clone(),
            None => return Ok(ToolResult::error("no store configured")),
        };
        let key = match args.get("key").and_then(|v| v.as_str()) {
            Some(s) if !s.is_empty() => s.to_string(),
            _ => return Ok(ToolResult::error("missing 'key'")),
        };
        let limit = args
            .get("limit")
            .and_then(|v| v.as_u64())
            .unwrap_or(8)
            .min(20) as u32;

        // Fetch the source memory
        let source = match store.memory_get(&key).await? {
            Some(m) => m,
            None => return Ok(ToolResult::error(format!("key not found: '{key}'"))),
        };

        // Already-linked neighbors (to exclude from suggestions)
        let existing_edges = store.memory_neighbors(&key).await.unwrap_or_default();
        let already_linked: std::collections::HashSet<String> = existing_edges
            .iter()
            .map(|e| {
                if e.from_key == key {
                    e.to_key.clone()
                } else {
                    e.from_key.clone()
                }
            })
            .collect();

        // List all memories (up to 500 for scoring)
        let all = store
            .list_memories(None, MemoryListSort::Recent, 500)
            .await
            .unwrap_or_default();

        let source_prefix = key_prefix(&key);
        let source_tokens = content_tokens(&source.content);

        let mut candidates: Vec<Value> = all
            .iter()
            .filter(|m| m.key != key && !already_linked.contains(&m.key))
            .filter_map(|m| {
                let mut score = 0.0f64;
                let mut reasons: Vec<&str> = Vec::new();

                // Tag overlap
                let tag_overlap = source.tags.iter().filter(|t| m.tags.contains(t)).count();
                if tag_overlap > 0 {
                    score += 0.4 * tag_overlap as f64;
                    reasons.push("tag_overlap");
                }

                // Key prefix similarity
                let m_prefix = key_prefix(&m.key);
                if !source_prefix.is_empty() && source_prefix == m_prefix {
                    score += 0.3;
                    reasons.push("same_prefix");
                }

                // Content token overlap (Jaccard-like)
                let m_tokens = content_tokens(&m.content);
                let intersection = source_tokens
                    .iter()
                    .filter(|t| m_tokens.contains(*t))
                    .count();
                let union = source_tokens.len() + m_tokens.len() - intersection;
                if union > 0 && intersection > 2 {
                    let jaccard = intersection as f64 / union as f64;
                    score += jaccard;
                    reasons.push("content_overlap");
                }

                if score < 0.1 {
                    return None;
                }

                Some(json!({
                    "key": m.key,
                    "kind": m.kind,
                    "confidence": (score * 100.0).min(100.0).round() / 100.0,
                    "reason": reasons.join("+"),
                    "snippet": m.content.chars().take(80).collect::<String>()
                }))
            })
            .collect();

        // Sort by confidence descending
        candidates.sort_by(|a, b| {
            let ca = a.get("confidence").and_then(|v| v.as_f64()).unwrap_or(0.0);
            let cb = b.get("confidence").and_then(|v| v.as_f64()).unwrap_or(0.0);
            cb.partial_cmp(&ca).unwrap_or(std::cmp::Ordering::Equal)
        });
        candidates.truncate(limit as usize);

        Ok(ToolResult::json_text(&json!({
            "source_key": key,
            "suggestions": candidates,
            "already_linked": already_linked.into_iter().collect::<Vec<_>>()
        })))
    }
}

fn key_prefix(key: &str) -> &str {
    key.split(&['_', '-', '/', '.'][..]).next().unwrap_or("")
}

fn content_tokens(content: &str) -> std::collections::HashSet<String> {
    content
        .split_whitespace()
        .filter(|t| t.len() >= 4)
        .map(|t| t.to_lowercase())
        .collect()
}

pub struct SessionFinalizeTool {
    hub: Hub,
}
impl SessionFinalizeTool {
    pub fn new(hub: Hub) -> Self {
        Self { hub }
    }
}
#[async_trait]
impl McpTool for SessionFinalizeTool {
    fn name(&self) -> &'static str {
        "session_finalize"
    }
    fn schema(&self) -> ToolSchema {
        ToolSchema {
            name: self.name().into(),
            description: "Manual session-end maintenance: importance decay, compact stale \
                 memories, optionally export JSONL. Equivalent to Claude Code's Stop hook \
                 pipeline. Response includes follow_up with active_total and a hint to run \
                 memory_consolidate if the graph is large."
                .into(),
            input_schema: json!({
                "type": "object",
                "properties": {
                    "older_than_days": { "type": "integer", "minimum": 1, "default": 90 },
                    "min_uses": { "type": "integer", "minimum": 0 },
                    "dry_run": { "type": "boolean", "default": false },
                    "decay_half_life_days": {
                        "type": "number", "minimum": 1.0, "default": 30.0,
                        "description": "Importance half-life in days. Default 30 = importance halves every month."
                    },
                    "decay_archive_threshold": {
                        "type": "number", "minimum": 0.0, "maximum": 1.0, "default": 0.05,
                        "description": "Memories with decayed importance below this are marked archived."
                    },
                    "skip_decay": {
                        "type": "boolean", "default": false,
                        "description": "If true, skip the importance decay pass (compact still runs)."
                    },
                    "export_path": { "type": "string", "description": "Optional JSONL export output path." },
                    "user_profile": {
                        "type": "string",
                        "description": "Markdown text describing the user (name, role, expertise, preferences, focus). \
                            Written to ~/.local/share/agent-bridge/USER.md and injected into \
                            future session_bootstrap calls. Synthesize from the current session before calling."
                    },
                    "agent_profile": {
                        "type": "string",
                        "description": "Markdown text describing the AGENT's own values, working style, and \
                            self-observations on this project. Written to ~/.local/share/agent-bridge/AGENT.md \
                            and injected as `Agent Self-Profile` block in future session_bootstrap calls. \
                            Maintained by the agent itself for cross-session identity continuity. \
                            Long-term destination: AiOT Seed `SelfModel` initialization (see memory \
                            decision_aiot_seed_as_agent_continuity_substrate_20260503). \
                            **Drift cap**: writes that change > 50% of line-set (Jaccard distance) \
                            are rejected unless `agent_profile_force=true`. Borrowed from AiOT \
                            identity_anchor.py MAX_STEP_DRIFT — stable identity should not be \
                            rewritable in one shot."
                    },
                    "agent_profile_force": {
                        "type": "boolean",
                        "default": false,
                        "description": "Bypass the 50% drift cap on AGENT.md. Use only when intentionally \
                            doing a large rewrite (e.g. project migration, major reframing). The response \
                            always reports `agent_profile_diff_ratio` so the caller can decide afterwards \
                            whether the change was as expected."
                    },
                    "letter": {
                        "type": "string",
                        "description": "Letter-to-future-self: a momentary snapshot of what the agent was thinking, \
                            working toward, or wanting future-self to know. Written append-only to \
                            ~/.local/share/agent-bridge/letters/letter_<unix_ts>.md. The 3 most recent letters \
                            are auto-injected into future session_bootstrap calls between AGENT.md and memory rows. \
                            Use for: state-at-time-of-writing, anticipations, hopes, warnings to future-self. \
                            Distinct from AGENT.md (stable identity) and session_handoff (factual progress log). \
                            Suggested 3-section structure: State / Direction / Notes-to-future-me."
                    }
                }
            }),
        }
    }
    async fn execute(&self, args: Value, _ctx: &ToolContext) -> Result<ToolResult> {
        let store = match &self.hub.store {
            Some(s) => s.clone(),
            None => return Ok(ToolResult::error("no store configured")),
        };
        let older_than_days = args
            .get("older_than_days")
            .and_then(|v| v.as_i64())
            .unwrap_or(90);
        let min_uses = args.get("min_uses").and_then(|v| v.as_u64());
        let dry_run = args
            .get("dry_run")
            .and_then(|v| v.as_bool())
            .unwrap_or(false);
        let half_life = args
            .get("decay_half_life_days")
            .and_then(|v| v.as_f64())
            .unwrap_or(30.0)
            .max(1.0);
        let archive_threshold = args
            .get("decay_archive_threshold")
            .and_then(|v| v.as_f64())
            .unwrap_or(0.05)
            .clamp(0.0, 1.0);
        let skip_decay = args
            .get("skip_decay")
            .and_then(|v| v.as_bool())
            .unwrap_or(false);

        // 1. Importance decay pass (unless skipped or dry_run)
        let decay_archived = if skip_decay || dry_run {
            0u64
        } else {
            store
                .memory_decay_importance(half_life, archive_threshold)
                .await
                .unwrap_or(0)
        };

        // 2. Compact stale memories
        let policy = CompactPolicy {
            min_uses,
            older_than_secs: Some(older_than_days * 86_400),
            dry_run,
        };
        let removed = store.memory_compact(policy).await?;

        // 3. Optional export
        let mut export_summary = Value::Null;
        if let Some(path) = args.get("export_path").and_then(|v| v.as_str()) {
            let filter = MemoryExportFilter::default();
            let exported = store.memory_export(&filter, &PathBuf::from(path)).await?;
            export_summary = json!({
                "path": path,
                "exported": exported.memories_written,
                "memories_written": exported.memories_written,
                "edges_written": exported.edges_written,
            });
        }

        // After compaction/decay, nudge operators toward periodic dedup when the graph grows.
        const CONSOLIDATE_HINT_ACTIVE_THRESHOLD: u64 = 60;
        let follow_up = match store.memory_stats().await {
            Ok(st) => {
                let active_total = st.counts_by_status.get("active").copied().unwrap_or(0);
                let suggest = active_total >= CONSOLIDATE_HINT_ACTIVE_THRESHOLD;
                let hint = if suggest {
                    json!(format!(
                        "Active memories {} ≥ {} — preview merges with memory_consolidate(dry_run:true, min_similarity:0.45, max_pairs:10).",
                        active_total, CONSOLIDATE_HINT_ACTIVE_THRESHOLD
                    ))
                } else {
                    Value::Null
                };
                json!({
                    "active_total": active_total,
                    "edge_count": st.edge_count,
                    "suggest_memory_consolidate": suggest,
                    "hint": hint,
                })
            }
            Err(_) => json!({
                "active_total": Value::Null,
                "edge_count": Value::Null,
                "suggest_memory_consolidate": false,
                "hint": Value::Null,
            }),
        };

        // Optional: persist user profile to USER.md for future session_bootstrap.
        let user_profile_written =
            if let Some(profile) = args.get("user_profile").and_then(|v| v.as_str()) {
                if !profile.trim().is_empty() && !dry_run {
                    let path = user_profile_path();
                    if let Some(parent) = path.parent() {
                        let _ = std::fs::create_dir_all(parent);
                    }
                    std::fs::write(&path, profile.as_bytes()).is_ok()
                } else {
                    false
                }
            } else {
                false
            };

        // Optional: persist agent self-profile to AGENT.md, with drift cap.
        // Returns (written: bool, diff_ratio: f32, capped: bool, reason: Option<String>).
        let force_profile = args
            .get("agent_profile_force")
            .and_then(|v| v.as_bool())
            .unwrap_or(false);
        let (agent_profile_written, agent_profile_diff_ratio_v, agent_profile_capped, agent_profile_reason) =
            if let Some(profile) = args.get("agent_profile").and_then(|v| v.as_str()) {
                if profile.trim().is_empty() {
                    (false, 0.0_f32, false, None)
                } else {
                    let path = agent_profile_path();
                    let old = std::fs::read_to_string(&path).unwrap_or_default();
                    let ratio = agent_profile_diff_ratio(&old, profile);
                    let exceeds = ratio > AGENT_PROFILE_DRIFT_CAP;
                    if exceeds && !force_profile && !old.trim().is_empty() {
                        // Reject — would rewrite > 50% of identity. Caller can retry
                        // with agent_profile_force=true if intentional.
                        (
                            false,
                            ratio,
                            true,
                            Some(format!(
                                "drift {:.1}% > cap {:.0}%; pass agent_profile_force=true to override",
                                ratio * 100.0,
                                AGENT_PROFILE_DRIFT_CAP * 100.0
                            )),
                        )
                    } else if dry_run {
                        (false, ratio, false, None)
                    } else {
                        if let Some(parent) = path.parent() {
                            let _ = std::fs::create_dir_all(parent);
                        }
                        let ok = std::fs::write(&path, profile.as_bytes()).is_ok();
                        (ok, ratio, exceeds && force_profile, None)
                    }
                }
            } else {
                (false, 0.0, false, None)
            };

        // Optional: persist letter-to-future-self. Append-only — each call
        // creates a new file letter_<unix_ts>.md. Latest 3 are auto-injected
        // at session_bootstrap.
        let letter_written =
            if let Some(letter_body) = args.get("letter").and_then(|v| v.as_str()) {
                if !letter_body.trim().is_empty() && !dry_run {
                    let dir = letters_dir();
                    let _ = std::fs::create_dir_all(&dir);
                    let ts = std::time::SystemTime::now()
                        .duration_since(std::time::UNIX_EPOCH)
                        .map(|d| d.as_secs())
                        .unwrap_or(0);
                    let path = dir.join(format!("letter_{ts}.md"));
                    std::fs::write(&path, letter_body.as_bytes())
                        .ok()
                        .map(|_| path.display().to_string())
                } else {
                    None
                }
            } else {
                None
            };

        Ok(ToolResult::json_text(&json!({
            "dry_run": dry_run,
            "decay": {
                "half_life_days": half_life,
                "archive_threshold": archive_threshold,
                "archived_count": decay_archived,
                "skipped": skip_decay || dry_run
            },
            "policy": {
                "older_than_days": older_than_days,
                "min_uses": min_uses
            },
            "removed_count": removed.len(),
            "removed_keys": removed,
            "export": export_summary,
            "follow_up": follow_up,
            "user_profile_written": user_profile_written,
            "agent_profile_written": agent_profile_written,
            "agent_profile_diff_ratio": agent_profile_diff_ratio_v,
            "agent_profile_capped": agent_profile_capped,
            "agent_profile_reason": agent_profile_reason,
            "letter_written": letter_written,
        })))
    }
}

fn tool_result_first_json(tr: &ToolResult) -> Option<Value> {
    tr.content.iter().find_map(|b| {
        if let ContentBlock::Text { text } = b {
            serde_json::from_str::<Value>(text).ok()
        } else {
            None
        }
    })
}

// ===========================================================================
//              project_detect + changes_digest (W2 perception)
// ===========================================================================

pub struct ProjectDetectTool {
    #[allow(dead_code)]
    hub: Hub,
}

impl ProjectDetectTool {
    pub fn new(hub: Hub) -> Self {
        Self { hub }
    }
}

#[async_trait]
impl McpTool for ProjectDetectTool {
    fn name(&self) -> &'static str {
        "project_detect"
    }
    fn schema(&self) -> ToolSchema {
        ToolSchema {
            name: self.name().into(),
            description:
                "Scan a directory for project manifests (Cargo.toml, package.json, \
                 pyproject.toml, go.mod, Makefile), infer languages + test/lint/format \
                 commands, list Rust workspace members, snapshot git branch+clean+recent \
                 commit. cwd defaults to process cwd."
                    .into(),
            input_schema: json!({
                "type": "object",
                "properties": {
                    "cwd": { "type": "string", "description": "Directory to scan (default: process cwd)." }
                }
            }),
        }
    }
    async fn execute(&self, args: Value, _ctx: &ToolContext) -> Result<ToolResult> {
        let cwd = match resolve_cwd(args.get("cwd").and_then(|v| v.as_str())) {
            Ok(p) => p,
            Err(e) => return Ok(ToolResult::error(e.to_string())),
        };
        let res = tokio::task::spawn_blocking(move || detect_project(&cwd))
            .await
            .map_err(|e| ab_core::Error::Backend(format!("project_detect task: {e}")))?;
        match res {
            Ok(v) => Ok(ToolResult::json_text(&v)),
            Err(e) => Ok(ToolResult::error(e.to_string())),
        }
    }
}

pub struct ChangesDigestTool {
    #[allow(dead_code)]
    hub: Hub,
}

impl ChangesDigestTool {
    pub fn new(hub: Hub) -> Self {
        Self { hub }
    }
}

#[async_trait]
impl McpTool for ChangesDigestTool {
    fn name(&self) -> &'static str {
        "changes_digest"
    }
    fn schema(&self) -> ToolSchema {
        ToolSchema {
            name: self.name().into(),
            description:
                "Structured git diff summary: file counts, total insertions/deletions, \
                 per-file numstat summary, and name-status rows. scope=working_tree (default), \
                 staged, last_commit, or branch_vs_main (diff against merge-base with main/master)."
                    .into(),
            input_schema: json!({
                "type": "object",
                "properties": {
                    "cwd": { "type": "string", "description": "Git repo directory (default: process cwd)." },
                    "scope": {
                        "type": "string",
                        "enum": ["working_tree", "staged", "last_commit", "branch_vs_main"],
                        "default": "working_tree",
                        "description": "Which tree to summarize."
                    }
                }
            }),
        }
    }
    async fn execute(&self, args: Value, _ctx: &ToolContext) -> Result<ToolResult> {
        let cwd = match resolve_cwd(args.get("cwd").and_then(|v| v.as_str())) {
            Ok(p) => p,
            Err(e) => return Ok(ToolResult::error(e.to_string())),
        };
        let scope = args
            .get("scope")
            .and_then(|v| v.as_str())
            .unwrap_or("working_tree")
            .to_string();
        let res = tokio::task::spawn_blocking(move || changes_digest(&cwd, &scope))
            .await
            .map_err(|e| ab_core::Error::Backend(format!("changes_digest task: {e}")))?;
        match res {
            Ok(v) => Ok(ToolResult::json_text(&v)),
            Err(e) => Ok(ToolResult::error(e.to_string())),
        }
    }
}

// ===========================================================================
//                    session_handoff (W3 structured brief)
// ===========================================================================

pub struct SessionHandoffBriefTool {
    hub: Hub,
}
impl SessionHandoffBriefTool {
    pub fn new(hub: Hub) -> Self {
        Self { hub }
    }
}

#[async_trait]
impl McpTool for SessionHandoffBriefTool {
    fn name(&self) -> &'static str {
        "session_handoff"
    }
    fn schema(&self) -> ToolSchema {
        ToolSchema {
            name: self.name().into(),
            description: "Build a machine-readable session handoff brief for the next \
                 agent: aggregates active todos, recent session_handoff memories, git \
                 branch / last commit / working-tree files, plus optional narrative \
                 fields. No new tables — memory + git only."
                .into(),
            input_schema: json!({
                "type": "object",
                "properties": {
                    "cwd": { "type": "string", "description": "Project directory (defaults to process cwd)." },
                    "max_todos": { "type": "integer", "minimum": 1, "maximum": 100, "default": 20 },
                    "max_handoff_memories": { "type": "integer", "minimum": 1, "maximum": 50, "default": 10 },
                    "last_task": { "type": "string", "description": "Optional one-line summary of what was in progress." },
                    "status": { "type": "string", "description": "Optional status string for the last task." },
                    "open_questions": {
                        "type": "array",
                        "items": { "type": "string" },
                        "description": "Optional list of unresolved questions."
                    },
                    "conversation_text": {
                        "type": "string",
                        "description": "Optional recent transcript snippet (truncated in output) for extra context."
                    }
                }
            }),
        }
    }
    async fn execute(&self, args: Value, _ctx: &ToolContext) -> Result<ToolResult> {
        let store = match &self.hub.store {
            Some(s) => s.clone(),
            None => return Ok(ToolResult::error("no memory store configured")),
        };
        let cwd = args
            .get("cwd")
            .and_then(|v| v.as_str())
            .map(PathBuf::from)
            .or_else(|| std::env::current_dir().ok())
            .unwrap_or_else(|| PathBuf::from("/"));
        let max_todos = args
            .get("max_todos")
            .and_then(|v| v.as_u64())
            .unwrap_or(20)
            .clamp(1, 100) as u32;
        let max_handoff_memories = args
            .get("max_handoff_memories")
            .and_then(|v| v.as_u64())
            .unwrap_or(10)
            .clamp(1, 50) as u32;
        let last_task = args
            .get("last_task")
            .and_then(|v| v.as_str())
            .map(|s| s.to_string());
        let status = args
            .get("status")
            .and_then(|v| v.as_str())
            .map(|s| s.to_string());
        let open_questions: Vec<String> = args
            .get("open_questions")
            .and_then(|v| v.as_array())
            .map(|arr| {
                arr.iter()
                    .filter_map(|x| x.as_str().map(|s| s.to_string()))
                    .collect()
            })
            .unwrap_or_default();
        let conversation_text = args
            .get("conversation_text")
            .and_then(|v| v.as_str())
            .map(|s| s.to_string());

        let brief = build_handoff_brief(
            store,
            cwd,
            max_todos,
            max_handoff_memories,
            last_task,
            status,
            open_questions,
            conversation_text,
        )
        .await?;
        Ok(ToolResult::json_text(&brief))
    }
}

// ===========================================================================
//                    session_lifecycle_step (W3 dispatcher)
// ===========================================================================

pub struct SessionLifecycleStepTool {
    hub: Hub,
}
impl SessionLifecycleStepTool {
    pub fn new(hub: Hub) -> Self {
        Self { hub }
    }
}

#[async_trait]
impl McpTool for SessionLifecycleStepTool {
    fn name(&self) -> &'static str {
        "session_lifecycle_step"
    }
    fn schema(&self) -> ToolSchema {
        ToolSchema {
            name: self.name().into(),
            description: "Dispatch a single session lifecycle phase: bootstrap (memory primer), \
                 precompact (session_curate then session_finalize), or finalize alone. \
                 Pass-through arguments are forwarded to the underlying tools."
                .into(),
            input_schema: json!({
                "type": "object",
                "properties": {
                    "step": {
                        "type": "string",
                        "enum": ["bootstrap", "start", "precompact", "finalize", "end"],
                        "description": "bootstrap|start → session_bootstrap; precompact → curate+finalize; finalize|end → session_finalize only."
                    },
                    "cwd": { "type": "string" },
                    "limit": { "type": "integer" },
                    "frontend": { "type": "string" },
                    "conversation_text": { "type": "string" },
                    "session_id": { "type": "string" },
                    "max_items": { "type": "integer" },
                    "dry_run": { "type": "boolean" },
                    "implicit_score_threshold": { "type": "number" },
                    "implicit_dedup_jaccard": { "type": "number" },
                    "older_than_days": { "type": "integer" },
                    "min_uses": { "type": "integer" },
                    "decay_half_life_days": { "type": "number" },
                    "decay_archive_threshold": { "type": "number" },
                    "skip_decay": { "type": "boolean" },
                    "export_path": { "type": "string" }
                },
                "required": ["step"]
            }),
        }
    }
    async fn execute(&self, args: Value, ctx: &ToolContext) -> Result<ToolResult> {
        let step = args
            .get("step")
            .and_then(|v| v.as_str())
            .map(|s| s.to_lowercase())
            .unwrap_or_default();

        match step.as_str() {
            "bootstrap" | "start" => {
                let mut sub = json!({});
                for k in ["cwd", "limit", "frontend"] {
                    if let Some(v) = args.get(k) {
                        sub[k] = v.clone();
                    }
                }
                SessionBootstrapTool::new(self.hub.clone())
                    .execute(sub, ctx)
                    .await
            }
            "finalize" | "end" => {
                let mut sub = json!({});
                for k in [
                    "older_than_days",
                    "min_uses",
                    "dry_run",
                    "decay_half_life_days",
                    "decay_archive_threshold",
                    "skip_decay",
                    "export_path",
                ] {
                    if let Some(v) = args.get(k) {
                        sub[k] = v.clone();
                    }
                }
                SessionFinalizeTool::new(self.hub.clone())
                    .execute(sub, ctx)
                    .await
            }
            "precompact" => {
                let conv = args
                    .get("conversation_text")
                    .and_then(|v| v.as_str())
                    .map(|s| s.to_string());
                let conv = match conv {
                    Some(t) if !t.trim().is_empty() => t,
                    _ => {
                        return Ok(ToolResult::error(
                            "precompact requires non-empty conversation_text",
                        ));
                    }
                };
                let mut curate_args = json!({ "conversation_text": conv });
                for k in [
                    "session_id",
                    "max_items",
                    "dry_run",
                    "implicit_score_threshold",
                    "implicit_dedup_jaccard",
                ] {
                    if let Some(v) = args.get(k) {
                        curate_args[k] = v.clone();
                    }
                }
                let curate = SessionCurateTool::new(self.hub.clone())
                    .execute(curate_args, ctx)
                    .await?;

                let mut fin_args = json!({});
                for k in [
                    "older_than_days",
                    "min_uses",
                    "dry_run",
                    "decay_half_life_days",
                    "decay_archive_threshold",
                    "skip_decay",
                    "export_path",
                ] {
                    if let Some(v) = args.get(k) {
                        fin_args[k] = v.clone();
                    }
                }
                let finalize = SessionFinalizeTool::new(self.hub.clone())
                    .execute(fin_args, ctx)
                    .await?;

                let merged = json!({
                    "step": "precompact",
                    "session_curate": tool_result_first_json(&curate),
                    "session_finalize": tool_result_first_json(&finalize),
                });
                let mut out = ToolResult::json_text(&merged);
                out.is_error = curate.is_error || finalize.is_error;
                Ok(out)
            }
            other => Ok(ToolResult::error(format!(
                "unknown lifecycle step: {other} (expected bootstrap|start|precompact|finalize|end)"
            ))),
        }
    }
}

// ===========================================================================
//                    oz_run_get / oz_run_list / oz_run_cancel
// ===========================================================================

/// Resolve the oz binary path (same logic as main.rs build_hub).
fn oz_binary(_hub: &Hub) -> String {
    std::env::var("AGENT_BRIDGE_OZ_BIN").unwrap_or_else(|_| "oz".into())
}

pub struct OzRunGetTool {
    hub: Hub,
}
impl OzRunGetTool {
    pub fn new(hub: Hub) -> Self {
        Self { hub }
    }
}
#[async_trait]
impl McpTool for OzRunGetTool {
    fn name(&self) -> &'static str {
        "oz_run_get"
    }
    fn schema(&self) -> ToolSchema {
        ToolSchema {
            name: self.name().into(),
            description: "Fetch the current status of a Warp cloud agent run by `run_id` or \
                 bridge `session_id` (for warp-oz sessions). Returns state, title, and \
                 session_link when the run has completed. \
                 Requires `oz` CLI on PATH and authenticated (`oz login` or WARP_API_KEY)."
                .into(),
            input_schema: json!({
                "type": "object",
                "properties": {
                    "run_id":     { "type": "string", "description": "Warp cloud run UUID." },
                    "session_id": { "type": "string", "description": "Bridge session id from agent_spawn (warp-oz only). Used to look up run_id automatically." }
                }
            }),
        }
    }
    async fn execute(&self, args: Value, _ctx: &ToolContext) -> Result<ToolResult> {
        let bin = oz_binary(&self.hub);

        // Resolve run_id: explicit or via session_id lookup.
        let run_id = if let Some(rid) = args.get("run_id").and_then(|v| v.as_str()) {
            rid.to_string()
        } else if let Some(sid) = args.get("session_id").and_then(|v| v.as_str()) {
            let store = match &self.hub.store {
                Some(s) => s.clone(),
                None => return Ok(ToolResult::error("no store configured")),
            };
            let session = store
                .load_session(&SessionId::from_raw(sid.to_string()))
                .await?;
            match session.and_then(|s| s.cloud_run_id) {
                Some(rid) => rid,
                None => return Ok(ToolResult::error("session has no cloud_run_id (not a warp-oz session, or run_id not yet persisted)")),
            }
        } else {
            return Ok(ToolResult::error(
                "one of 'run_id' or 'session_id' is required",
            ));
        };

        match fetch_run_status(&bin, &run_id).await {
            Some(status) => Ok(ToolResult::json_text(&json!({
                "run_id":       run_id,
                "state":        status.state,
                "title":        status.title,
                "session_link": status.session_link,
            }))),
            None => Ok(ToolResult::error(format!(
                "oz run get {run_id} failed (oz not on PATH, not logged in, or run_id invalid)"
            ))),
        }
    }
}

pub struct OzRunListTool {
    hub: Hub,
}
impl OzRunListTool {
    pub fn new(hub: Hub) -> Self {
        Self { hub }
    }
}
#[async_trait]
impl McpTool for OzRunListTool {
    fn name(&self) -> &'static str {
        "oz_run_list"
    }
    fn schema(&self) -> ToolSchema {
        ToolSchema {
            name: self.name().into(),
            description: "List recent Warp cloud agent runs via the oz CLI. \
                 Returns run IDs, states, titles, and session links. \
                 Optional filters: state (QUEUED/INPROGRESS/SUCCEEDED/FAILED), limit."
                .into(),
            input_schema: json!({
                "type": "object",
                "properties": {
                    "state": { "type": "string", "description": "Filter by state (QUEUED, INPROGRESS, SUCCEEDED, FAILED)." },
                    "limit": { "type": "integer", "minimum": 1, "maximum": 50, "default": 10 }
                }
            }),
        }
    }
    async fn execute(&self, args: Value, _ctx: &ToolContext) -> Result<ToolResult> {
        let bin = oz_binary(&self.hub);
        let limit = args
            .get("limit")
            .and_then(|v| v.as_u64())
            .unwrap_or(10)
            .min(50);
        let mut cmd_args = vec![
            "run".to_string(),
            "list".to_string(),
            "--output-format".to_string(),
            "json".to_string(),
            "--limit".to_string(),
            limit.to_string(),
        ];
        if let Some(st) = args.get("state").and_then(|v| v.as_str()) {
            cmd_args.push("--state".to_string());
            cmd_args.push(st.to_string());
        }
        let out = tokio::process::Command::new(&bin)
            .args(&cmd_args)
            .stdin(std::process::Stdio::null())
            .stdout(std::process::Stdio::piped())
            .stderr(std::process::Stdio::null())
            .output()
            .await;
        match out {
            Ok(o) if o.status.success() => {
                let text = String::from_utf8_lossy(&o.stdout).into_owned();
                let parsed: Value = serde_json::from_str(&text).unwrap_or(json!({ "raw": text }));
                Ok(ToolResult::json_text(&parsed))
            }
            Ok(o) => Ok(ToolResult::error(format!(
                "oz run list failed (exit {:?})",
                o.status.code()
            ))),
            Err(e) => Ok(ToolResult::error(format!(
                "oz not found or not executable: {e}"
            ))),
        }
    }
}

pub struct OzRunCancelTool {
    hub: Hub,
}
impl OzRunCancelTool {
    pub fn new(hub: Hub) -> Self {
        Self { hub }
    }
}
#[async_trait]
impl McpTool for OzRunCancelTool {
    fn name(&self) -> &'static str {
        "oz_run_cancel"
    }
    fn schema(&self) -> ToolSchema {
        ToolSchema {
            name: self.name().into(),
            description: "Cancel an in-progress Warp cloud agent run. \
                 Accepts `run_id` or `session_id`. \
                 Calls POST https://app.warp.dev/api/v1/agent/runs/{id}/cancel via curl. \
                 Requires WARP_API_KEY env var (generate at Warp Settings → Platform)."
                .into(),
            input_schema: json!({
                "type": "object",
                "properties": {
                    "run_id":     { "type": "string", "description": "Warp cloud run UUID." },
                    "session_id": { "type": "string", "description": "Bridge session id (warp-oz only)." }
                }
            }),
        }
    }
    async fn execute(&self, args: Value, _ctx: &ToolContext) -> Result<ToolResult> {
        // ── Resolve run_id ────────────────────────────────────────────────
        let run_id = if let Some(rid) = args.get("run_id").and_then(|v| v.as_str()) {
            rid.to_string()
        } else if let Some(sid) = args.get("session_id").and_then(|v| v.as_str()) {
            let store = match &self.hub.store {
                Some(s) => s.clone(),
                None => return Ok(ToolResult::error("no store configured")),
            };
            let session = store
                .load_session(&SessionId::from_raw(sid.to_string()))
                .await?;
            match session.and_then(|s| s.cloud_run_id) {
                Some(rid) => rid,
                None => return Ok(ToolResult::error("session has no cloud_run_id")),
            }
        } else {
            return Ok(ToolResult::error(
                "one of 'run_id' or 'session_id' is required",
            ));
        };

        // ── Get WARP_API_KEY ──────────────────────────────────────────────
        // The oz CLI reads the same env var (WARP_API_KEY) for its --api-key flag.
        // Generate one at: Warp Settings → Platform.
        let api_key = match std::env::var("WARP_API_KEY") {
            Ok(k) if !k.is_empty() => k,
            _ => {
                return Ok(ToolResult::error(
                    "WARP_API_KEY env var not set. \
                 Generate an API key at Warp Settings → Platform \
                 (warp://settings/platform), then export WARP_API_KEY=<key>.",
                ))
            }
        };

        // ── POST .../cancel via curl ──────────────────────────────────────
        // The oz CLI has no 'oz run cancel' subcommand; we call the REST API directly.
        // Endpoint: POST https://app.warp.dev/api/v1/agent/runs/{runId}/cancel
        let url = format!("https://app.warp.dev/api/v1/agent/runs/{}/cancel", run_id);
        let out = tokio::process::Command::new("curl")
            .args([
                "-s", // silent
                "-X",
                "POST",
                "-H",
                &format!("Authorization: Bearer {api_key}"),
                "-H",
                "Content-Type: application/json",
                "-w",
                "\n__HTTP_STATUS__%{http_code}",
                &url,
            ])
            .stdin(std::process::Stdio::null())
            .stdout(std::process::Stdio::piped())
            .stderr(std::process::Stdio::piped())
            .output()
            .await;

        match out {
            Err(e) => Ok(ToolResult::error(format!("curl not found: {e}"))),
            Ok(o) => {
                let raw = String::from_utf8_lossy(&o.stdout).into_owned();
                // Split body and HTTP status (appended via -w)
                let (body, status_code) = if let Some(idx) = raw.rfind("\n__HTTP_STATUS__") {
                    let code: u16 = raw[idx + 16..].trim().parse().unwrap_or(0);
                    (&raw[..idx], code)
                } else {
                    (raw.as_str(), 0u16)
                };

                if status_code == 200 || status_code == 204 {
                    Ok(ToolResult::json_text(&json!({
                        "cancelled": true,
                        "run_id": run_id,
                        "http_status": status_code,
                    })))
                } else {
                    Ok(ToolResult::error(format!(
                        "cancel failed (HTTP {status_code}): {}",
                        body.trim()
                    )))
                }
            }
        }
    }
}

// ===========================================================================
//                          memory_graph_export (v0.11)
// ===========================================================================

pub struct MemoryGraphExportTool {
    hub: Hub,
}
impl MemoryGraphExportTool {
    pub fn new(hub: Hub) -> Self {
        Self { hub }
    }
}
#[async_trait]
impl McpTool for MemoryGraphExportTool {
    fn name(&self) -> &'static str {
        "memory_graph_export"
    }
    fn schema(&self) -> ToolSchema {
        ToolSchema {
            name: self.name().into(),
            description: "Export the memory knowledge graph in Graphviz DOT or JSON format. \
                 Nodes are active memory records (labelled by key and kind). \
                 Edges carry type and weight. \
                 Pass format='dot' (default) to get a DOT string you can pipe into \
                 `dot -Tsvg` or paste into https://dreampuf.github.io/GraphvizOnline/. \
                 Pass format='json' for {nodes:[…], edges:[…]} suitable for \
                 D3 / Cytoscape / vis-network. \
                 Optional `tags_any` and `kind` filters narrow which nodes are included \
                 (unmatched nodes are omitted but their incident edges are also dropped)."
                .into(),
            input_schema: json!({
                "type": "object",
                "properties": {
                    "format": {
                        "type": "string",
                        "enum": ["dot", "json"],
                        "default": "dot",
                        "description": "Output format."
                    },
                    "kind": {
                        "type": "string",
                        "description": "Only include memories of this kind."
                    },
                    "tags_any": {
                        "type": "array",
                        "items": { "type": "string" },
                        "description": "Include only memories that have at least one of these tags."
                    },
                    "max_nodes": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 500,
                        "default": 200,
                        "description": "Cap on how many nodes to include (highest-importance first)."
                    }
                }
            }),
        }
    }
    async fn execute(&self, args: Value, _ctx: &ToolContext) -> Result<ToolResult> {
        let store = match &self.hub.store {
            Some(s) => s.clone(),
            None => return Ok(ToolResult::error("no store configured")),
        };

        let fmt = args.get("format").and_then(|v| v.as_str()).unwrap_or("dot");
        let kind_filter = args
            .get("kind")
            .and_then(|v| v.as_str())
            .map(|s| s.to_string());
        let tags_any: Vec<String> = args
            .get("tags_any")
            .and_then(|v| v.as_array())
            .map(|a| {
                a.iter()
                    .filter_map(|x| x.as_str().map(|s| s.to_string()))
                    .collect()
            })
            .unwrap_or_default();
        let max_nodes = args
            .get("max_nodes")
            .and_then(|v| v.as_u64())
            .unwrap_or(200)
            .min(500) as u32;

        // Fetch active nodes (highest-importance first).
        let all_nodes = store
            .list_memories(
                kind_filter.as_deref(),
                MemoryListSort::ByImportance,
                max_nodes,
            )
            .await?;
        let nodes: Vec<_> = all_nodes
            .into_iter()
            .filter(|m| m.status == "active")
            .filter(|m| tags_any.is_empty() || tags_any.iter().any(|t| m.tags.contains(t)))
            .collect();

        let node_keys: std::collections::HashSet<String> =
            nodes.iter().map(|m| m.key.clone()).collect();

        // Fetch all edges; keep only those where BOTH endpoints are in the node set.
        let all_edges = {
            // Pull edges for every included node (dedup via set).
            let mut seen = std::collections::HashSet::new();
            let mut edges = Vec::new();
            for m in &nodes {
                let nbrs = store.memory_neighbors(&m.key).await.unwrap_or_default();
                for e in nbrs {
                    let key = if e.from_key < e.to_key {
                        (e.from_key.clone(), e.to_key.clone(), e.edge_type.clone())
                    } else {
                        (e.to_key.clone(), e.from_key.clone(), e.edge_type.clone())
                    };
                    if seen.insert(key)
                        && node_keys.contains(&e.from_key)
                        && node_keys.contains(&e.to_key)
                    {
                        edges.push(e);
                    }
                }
            }
            edges
        };

        match fmt {
            "json" => {
                let nodes_json: Vec<Value> = nodes
                    .iter()
                    .map(|m| {
                        json!({
                            "id":         m.key,
                            "kind":       m.kind,
                            "importance": (m.importance * 1000.0).round() / 1000.0,
                            "tags":       m.tags,
                            "label":      format!("[{}] {}", m.kind, m.key),
                        })
                    })
                    .collect();
                let edges_json: Vec<Value> = all_edges
                    .iter()
                    .map(|e| {
                        json!({
                            "source":    e.from_key,
                            "target":    e.to_key,
                            "type":      e.edge_type,
                            "weight":    (e.weight * 1000.0).round() / 1000.0,
                        })
                    })
                    .collect();
                Ok(ToolResult::json_text(&json!({
                    "format":    "json",
                    "node_count": nodes_json.len(),
                    "edge_count": edges_json.len(),
                    "nodes":     nodes_json,
                    "edges":     edges_json,
                })))
            }
            _ => {
                // DOT format
                let mut dot = String::from("digraph memories {\n");
                dot.push_str("  graph [rankdir=LR fontname=\"Helvetica\"];\n");
                dot.push_str(
                    "  node  [shape=box style=rounded fontname=\"Helvetica\" fontsize=10];\n",
                );
                dot.push_str("  edge  [fontname=\"Helvetica\" fontsize=8];\n\n");

                // Color scheme per kind
                fn kind_color(kind: &str) -> &str {
                    match kind {
                        "decision" => "#ffd700",
                        "lesson" => "#90ee90",
                        "todo" => "#ff9999",
                        "session_handoff" => "#add8e6",
                        "context" => "#e0e0e0",
                        "concept" => "#d8b4fe",
                        "reference" => "#fed7aa",
                        _ => "#f0f0f0",
                    }
                }

                for m in &nodes {
                    // Escape key for DOT id (replace hyphens/spaces with underscores)
                    let id = m.key.replace(['-', ' ', '.', '/'], "_");
                    let label = if m.key.len() > 30 {
                        format!("{}\\n[{}]", &m.key[..28], m.kind)
                    } else {
                        format!("{} [{}]", m.key, m.kind)
                    };
                    let color = kind_color(&m.kind);
                    let width = 1.0 + m.importance * 2.0; // border width encodes importance
                    dot.push_str(&format!(
                        "  {} [label=\"{}\" fillcolor=\"{}\" style=\"filled,rounded\" penwidth={:.1}];\n",
                        id, label, color, width
                    ));
                }

                dot.push_str("\n");

                for e in &all_edges {
                    let src = e.from_key.replace(['-', ' ', '.', '/'], "_");
                    let dst = e.to_key.replace(['-', ' ', '.', '/'], "_");
                    let style = match e.edge_type.as_str() {
                        "supersedes" | "updates" => "bold",
                        "contradicts" | "invalidates" => "dashed",
                        _ => "solid",
                    };
                    dot.push_str(&format!(
                        "  {} -> {} [label=\"{}\" style={} weight={:.1}];\n",
                        src, dst, e.edge_type, style, e.weight
                    ));
                }

                dot.push_str("}\n");

                Ok(ToolResult::json_text(&json!({
                    "format":     "dot",
                    "node_count": nodes.len(),
                    "edge_count": all_edges.len(),
                    "dot":        dot,
                    "hint":       "Render with: echo '<dot>' | dot -Tsvg -o graph.svg"
                })))
            }
        }
    }
}

// ===========================================================================
//                          memory_auto_curate (v0.12)
// ===========================================================================

/// Automated memory curation: gathers recent `session_handoff` (or any
/// configurable kind) memories, aggregates their content, runs the
/// curate_conversation two-pass pipeline over the combined text, and
/// persists the resulting structured memories.
///
/// Designed to be called periodically (e.g. by an Oz cloud-agent schedule)
/// to proactively accumulate lessons/decisions/facts from session summaries
/// without requiring a human to explicitly invoke session_curate.
pub struct MemoryAutoCurateTool {
    hub: Hub,
}
impl MemoryAutoCurateTool {
    pub fn new(hub: Hub) -> Self {
        Self { hub }
    }
}

#[async_trait]
impl McpTool for MemoryAutoCurateTool {
    fn name(&self) -> &'static str {
        "memory_auto_curate"
    }
    fn schema(&self) -> ToolSchema {
        ToolSchema {
            name: self.name().into(),
            description: "Automated memory curation: load recent memories of a given kind \
                 (default: session_handoff), aggregate their content, run the \
                 two-pass curate pipeline, and persist the extracted lessons / \
                 decisions / facts. Safe to call repeatedly — duplicate keys are \
                 skipped. Designed for scheduled or post-session automation; no \
                 LLM call required."
                .into(),
            input_schema: json!({
                "type": "object",
                "properties": {
                    "source_kind": {
                        "type": "string",
                        "description": "Memory kind to gather as source material. Default: 'session_handoff'.",
                        "default": "session_handoff"
                    },
                    "max_sources": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 20,
                        "default": 5,
                        "description": "How many source memories to aggregate (sorted by importance). Default: 5."
                    },
                    "max_items": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 50,
                        "default": 12,
                        "description": "Max structured memories to extract from the aggregated text. Default: 12."
                    },
                    "exclude_kinds": {
                        "type": "array",
                        "items": { "type": "string" },
                        "description": "Candidate kinds to suppress from output (e.g. re-generated 'session_handoff'). Default: ['session_handoff']."
                    },
                    "dry_run": {
                        "type": "boolean",
                        "default": false,
                        "description": "Preview extracted candidates without writing to the store."
                    },
                    "implicit_score_threshold": {
                        "type": "number",
                        "description": "Override Pass-2 minimum signal score. Same semantics as session_curate."
                    },
                    "implicit_dedup_jaccard": {
                        "type": "number",
                        "description": "Override Pass-2 Jaccard dedup threshold. Same semantics as session_curate."
                    }
                },
                "required": []
            }),
        }
    }

    async fn execute(&self, args: Value, _ctx: &ToolContext) -> Result<ToolResult> {
        let store = match self.hub.store.clone() {
            Some(s) => s,
            None => return Ok(ToolResult::error("no memory store configured")),
        };

        // ── Parameters ──────────────────────────────────────────────────
        let source_kind = args
            .get("source_kind")
            .and_then(|v| v.as_str())
            .filter(|s| !s.is_empty())
            .unwrap_or("session_handoff")
            .to_string();

        let max_sources = args
            .get("max_sources")
            .and_then(|v| v.as_u64())
            .unwrap_or(5)
            .min(20) as u32;

        let max_items = args
            .get("max_items")
            .and_then(|v| v.as_u64())
            .unwrap_or(12)
            .min(50) as usize;

        let exclude_kinds: Vec<String> = args
            .get("exclude_kinds")
            .and_then(|v| v.as_array())
            .map(|arr| {
                arr.iter()
                    .filter_map(|v| v.as_str().map(|s| s.to_string()))
                    .collect()
            })
            .unwrap_or_else(|| vec!["session_handoff".to_string()]);

        let dry_run = args
            .get("dry_run")
            .and_then(|v| v.as_bool())
            .unwrap_or(false);

        let score_ov = args
            .get("implicit_score_threshold")
            .and_then(|v| v.as_f64())
            .map(|x| x as f32);
        let dedup_ov = args.get("implicit_dedup_jaccard").and_then(|v| v.as_f64());

        // ── Gather source memories ───────────────────────────────────────
        let sources = store
            .list_memories(
                Some(&source_kind),
                MemoryListSort::ByImportance,
                max_sources,
            )
            .await
            .map_err(|e| ab_core::Error::Backend(format!("memory_auto_curate list: {e}")))?;

        if sources.is_empty() {
            return Ok(ToolResult::json_text(&json!({
                "status": "no_sources",
                "message": format!("No memories of kind '{}' found. Nothing to curate.", source_kind),
                "source_kind": source_kind,
                "sources_found": 0,
                "saved_count": 0,
            })));
        }

        // ── Aggregate content ────────────────────────────────────────────
        let mut aggregated = String::new();
        let source_keys: Vec<String> = sources.iter().map(|m| m.key.clone()).collect();
        for (i, m) in sources.iter().enumerate() {
            aggregated.push_str(&format!(
                "\n=== Source {} ({}) ===\n{}",
                i + 1,
                m.key,
                m.content
            ));
        }

        // ── Run curate pipeline ──────────────────────────────────────────
        let curate_opts =
            crate::curate::CurateOptions::from_env_or_defaults().with_overrides(score_ov, dedup_ov);

        let mut candidates = crate::curate::curate_conversation_with_options(
            &aggregated,
            None, // no session_id namespace; these are global distillations
            max_items,
            curate_opts.clone(),
        );

        // Filter out excluded kinds
        candidates.retain(|c| !exclude_kinds.iter().any(|k| k == &c.kind));

        // ── Dry run: return preview ─────────────────────────────────────
        if dry_run {
            return Ok(ToolResult::json_text(&json!({
                "dry_run": true,
                "source_kind": source_kind,
                "sources_used": source_keys,
                "aggregated_chars": aggregated.len(),
                "options": {
                    "implicit_score_threshold": curate_opts.implicit_score_threshold,
                    "implicit_dedup_jaccard":   curate_opts.implicit_dedup_jaccard,
                },
                "candidates": candidates.iter().map(|m| json!({
                    "key":     m.key,
                    "kind":    m.kind,
                    "content": m.content,
                    "tags":    m.tags,
                })).collect::<Vec<_>>()
            })));
        }

        // ── Persist new memories (skip duplicates) ───────────────────────
        let mut saved: Vec<Value> = Vec::new();
        let mut skipped = 0usize;
        let mut errors: Vec<String> = Vec::new();

        for mem in &candidates {
            match store.memory_get(&mem.key).await {
                Ok(Some(_)) => skipped += 1,
                Ok(None) => match store.memory_save(mem).await {
                    Ok(()) => saved.push(json!({ "key": mem.key, "kind": mem.kind })),
                    Err(e) => errors.push(format!("{}: {e}", mem.key)),
                },
                Err(e) => errors.push(format!("{}: {e}", mem.key)),
            }
        }

        Ok(ToolResult::json_text(&json!({
            "status": "ok",
            "source_kind": source_kind,
            "sources_used": source_keys,
            "aggregated_chars": aggregated.len(),
            "candidates_found": candidates.len(),
            "saved_count": saved.len(),
            "new_memories": saved,
            "skipped_duplicates": skipped,
            "errors": errors,
            "follow_up": if saved.is_empty() {
                "No new memories saved (all duplicates or no signal). Consider widening source scope or adjusting thresholds."
            } else {
                "New memories saved. Run memory_consolidate(dry_run:true) to check for near-duplicates."
            }
        })))
    }
}

// ===========================================================================
//                         plan_save / plan_load / plan_update (W5)
// ===========================================================================

fn enrich_plan_json(rec: &PlanRecord) -> Value {
    let total = rec.steps.len();
    let done = rec.steps.iter().filter(|s| s.status == "done").count();
    let progress = format!("{done}/{total} done");
    let next = rec
        .steps
        .iter()
        .find(|s| s.status != "done" && s.status != "cancelled")
        .map(|s| s.id.clone());
    json!({
        "plan_id": rec.plan_id,
        "title": rec.title,
        "steps": rec.steps,
        "created_at": rec.created_at,
        "updated_at": rec.updated_at,
        "progress": progress,
        "done_count": done,
        "total_steps": total,
        "next_step_id": next,
    })
}

pub struct PlanSaveTool {
    hub: Hub,
}
impl PlanSaveTool {
    pub fn new(hub: Hub) -> Self {
        Self { hub }
    }
}

#[async_trait]
impl McpTool for PlanSaveTool {
    fn name(&self) -> &'static str {
        "plan_save"
    }
    fn schema(&self) -> ToolSchema {
        ToolSchema {
            name: self.name().into(),
            description: "Persist a structured task plan to SQLite (survives sessions). \
                 Each step has id, desc, optional status (default pending), optional deps (step ids)."
                .into(),
            input_schema: json!({
                "type": "object",
                "properties": {
                    "plan_id": { "type": "string", "description": "Stable plan identifier." },
                    "title": { "type": "string", "description": "Human-readable plan title." },
                    "steps": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "id": { "type": "string" },
                                "desc": { "type": "string" },
                                "status": { "type": "string", "description": "pending | in_progress | done | cancelled (free-form allowed)" },
                                "deps": { "type": "array", "items": { "type": "string" } }
                            },
                            "required": ["id", "desc"]
                        },
                        "description": "Ordered steps."
                    }
                },
                "required": ["plan_id", "title", "steps"]
            }),
        }
    }
    async fn execute(&self, args: Value, _ctx: &ToolContext) -> Result<ToolResult> {
        let store = match &self.hub.store {
            Some(s) => s.clone(),
            None => return Ok(ToolResult::error("no memory store configured")),
        };
        let plan_id = match args
            .get("plan_id")
            .and_then(|v| v.as_str())
            .filter(|s| !s.is_empty())
        {
            Some(s) => s.to_string(),
            None => return Ok(ToolResult::error("missing or empty 'plan_id'")),
        };
        let title = match args
            .get("title")
            .and_then(|v| v.as_str())
            .filter(|s| !s.is_empty())
        {
            Some(s) => s.to_string(),
            None => return Ok(ToolResult::error("missing or empty 'title'")),
        };
        let steps_val = match args.get("steps") {
            Some(v) if v.is_array() => v.clone(),
            _ => return Ok(ToolResult::error("missing 'steps' array")),
        };
        let steps: Vec<PlanStep> = serde_json::from_value(steps_val)
            .map_err(|e| ab_core::Error::InvalidArgument(format!("invalid steps: {e}")))?;
        if steps.is_empty() {
            return Ok(ToolResult::error("'steps' must be non-empty"));
        }
        store
            .plan_save(&plan_id, &title, &steps)
            .await
            .map_err(|e| ab_core::Error::Backend(format!("plan_save: {e}")))?;
        Ok(ToolResult::json_text(
            &json!({ "status": "ok", "plan_id": plan_id, "title": title, "step_count": steps.len() }),
        ))
    }
}

pub struct PlanLoadTool {
    hub: Hub,
}
impl PlanLoadTool {
    pub fn new(hub: Hub) -> Self {
        Self { hub }
    }
}

#[async_trait]
impl McpTool for PlanLoadTool {
    fn name(&self) -> &'static str {
        "plan_load"
    }
    fn schema(&self) -> ToolSchema {
        ToolSchema {
            name: self.name().into(),
            description: "Load a persisted plan by plan_id. Includes progress string and next_step_id heuristic."
                .into(),
            input_schema: json!({
                "type": "object",
                "properties": {
                    "plan_id": { "type": "string" }
                },
                "required": ["plan_id"]
            }),
        }
    }
    async fn execute(&self, args: Value, _ctx: &ToolContext) -> Result<ToolResult> {
        let store = match &self.hub.store {
            Some(s) => s.clone(),
            None => return Ok(ToolResult::error("no memory store configured")),
        };
        let plan_id = match args
            .get("plan_id")
            .and_then(|v| v.as_str())
            .filter(|s| !s.is_empty())
        {
            Some(s) => s,
            None => return Ok(ToolResult::error("missing or empty 'plan_id'")),
        };
        match store
            .plan_load(plan_id)
            .await
            .map_err(|e| ab_core::Error::Backend(format!("plan_load: {e}")))?
        {
            Some(rec) => Ok(ToolResult::json_text(&enrich_plan_json(&rec))),
            None => Ok(ToolResult::error(format!("plan not found: '{plan_id}'"))),
        }
    }
}

pub struct PlanUpdateTool {
    hub: Hub,
}
impl PlanUpdateTool {
    pub fn new(hub: Hub) -> Self {
        Self { hub }
    }
}

#[async_trait]
impl McpTool for PlanUpdateTool {
    fn name(&self) -> &'static str {
        "plan_update"
    }
    fn schema(&self) -> ToolSchema {
        ToolSchema {
            name: self.name().into(),
            description: "Update one plan step's status by step id. Returns updated plan envelope or error if missing."
                .into(),
            input_schema: json!({
                "type": "object",
                "properties": {
                    "plan_id": { "type": "string" },
                    "step_id": { "type": "string" },
                    "status": { "type": "string", "description": "e.g. done | in_progress | pending | cancelled" }
                },
                "required": ["plan_id", "step_id", "status"]
            }),
        }
    }
    async fn execute(&self, args: Value, _ctx: &ToolContext) -> Result<ToolResult> {
        let store = match &self.hub.store {
            Some(s) => s.clone(),
            None => return Ok(ToolResult::error("no memory store configured")),
        };
        let plan_id = match args
            .get("plan_id")
            .and_then(|v| v.as_str())
            .filter(|s| !s.is_empty())
        {
            Some(s) => s,
            None => return Ok(ToolResult::error("missing or empty 'plan_id'")),
        };
        let step_id = match args
            .get("step_id")
            .and_then(|v| v.as_str())
            .filter(|s| !s.is_empty())
        {
            Some(s) => s,
            None => return Ok(ToolResult::error("missing or empty 'step_id'")),
        };
        let status = match args
            .get("status")
            .and_then(|v| v.as_str())
            .filter(|s| !s.is_empty())
        {
            Some(s) => s,
            None => return Ok(ToolResult::error("missing or empty 'status'")),
        };
        let ok = store
            .plan_update_step(plan_id, step_id, status)
            .await
            .map_err(|e| ab_core::Error::Backend(format!("plan_update: {e}")))?;
        if !ok {
            return Ok(ToolResult::error(format!(
                "plan '{plan_id}' or step '{step_id}' not found"
            )));
        }
        let rec = store
            .plan_load(plan_id)
            .await
            .map_err(|e| ab_core::Error::Backend(format!("plan_load: {e}")))?
            .expect("row exists after update");
        Ok(ToolResult::json_text(&json!({
            "status": "ok",
            "plan": enrich_plan_json(&rec),
        })))
    }
}

// ===========================================================================
//                            context_budget (W5)
// ===========================================================================

pub struct ContextBudgetTool;

impl ContextBudgetTool {
    pub fn new() -> Self {
        Self
    }
}

#[async_trait]
impl McpTool for ContextBudgetTool {
    fn name(&self) -> &'static str {
        "context_budget"
    }
    fn schema(&self) -> ToolSchema {
        ToolSchema {
            name: self.name().into(),
            description: "Estimate token usage from optional conversation text + turn count using offline heuristics; \
                 compare to an approximate model context limit and get a compaction recommendation. No API calls."
                .into(),
            input_schema: json!({
                "type": "object",
                "properties": {
                    "model": {
                        "type": "string",
                        "description": "Model name hint for context window size (default: claude-sonnet-4).",
                        "default": "claude-sonnet-4"
                    },
                    "conversation_turns": {
                        "type": "integer",
                        "minimum": 0,
                        "description": "When transcript is unavailable, each turn adds a coarse token guess.",
                        "default": 0
                    },
                    "text_sample": {
                        "type": "string",
                        "description": "Optional excerpt / transcript sample to token-estimate (mixed EN/CJK heuristic)."
                    }
                }
            }),
        }
    }
    async fn execute(&self, args: Value, _ctx: &ToolContext) -> Result<ToolResult> {
        let model = args
            .get("model")
            .and_then(|v| v.as_str())
            .filter(|s| !s.is_empty())
            .unwrap_or("claude-sonnet-4");
        let turns = args
            .get("conversation_turns")
            .and_then(|v| v.as_u64())
            .unwrap_or(0);
        let text = args
            .get("text_sample")
            .and_then(|v| v.as_str())
            .unwrap_or("");
        let limit = model_context_limit(model);
        let estimated = estimated_usage_tokens(text, turns);
        let pct_raw = if limit == 0 {
            0.0
        } else {
            (estimated as f64 / limit as f64) * 100.0
        };
        let pct_used = (pct_raw * 10.0).round() / 10.0;
        let recommendation = budget_recommendation(pct_raw);
        Ok(ToolResult::json_text(&json!({
            "model_hint": model,
            "model_limit": limit,
            "estimated_tokens_used": estimated,
            "pct_used": pct_used,
            "recommendation": recommendation,
            "heuristic_note": "Offline estimate only; actual tokenizer usage varies.",
        })))
    }
}

// ===========================================================================
//                  Warp URI tools (W4 — DESIGN-warp-first-agent-shell)
// ===========================================================================

fn warp_resolve_tab_window_path(raw: Option<&str>) -> Result<String> {
    match raw.filter(|s| !s.is_empty()) {
        Some(p) => Ok(resolve_cwd(Some(p))?.display().to_string()),
        None => Ok(resolve_cwd(None)?.display().to_string()),
    }
}

pub struct WarpOpenTabTool {
    hub: Hub,
}

impl WarpOpenTabTool {
    pub fn new(hub: Hub) -> Self {
        Self { hub }
    }
}

#[async_trait]
impl McpTool for WarpOpenTabTool {
    fn name(&self) -> &'static str {
        "warp_open_tab"
    }
    fn schema(&self) -> ToolSchema {
        ToolSchema {
            name: self.name().into(),
            description: "Open a new Warp tab via URI scheme and return the new session's UUID. \
                 Polls terminal_list for up to 3 s to detect the newly registered session. \
                 Optional `path` sets initial cwd (defaults to bridge process cwd). \
                 Returns `session_id` (string) when detected, null otherwise."
                .into(),
            input_schema: json!({
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Directory for ?path= (absolute or relative); omit for current cwd."
                    }
                }
            }),
        }
    }
    async fn execute(&self, args: Value, _ctx: &ToolContext) -> Result<ToolResult> {
        let raw = args.get("path").and_then(|v| v.as_str());
        let cwd = warp_resolve_tab_window_path(raw)?;
        let uri = warp_scheme_new_tab(Some(&cwd));

        // Snapshot existing sessions so we can detect the new one.
        let before: std::collections::HashSet<String> = if let Some(term) = &self.hub.terminal {
            term.list_panes()
                .await
                .unwrap_or_default()
                .into_iter()
                .map(|p| p.id.to_string())
                .collect()
        } else {
            std::collections::HashSet::new()
        };

        dispatch_warp_scheme_uri(&uri)
            .await
            .map_err(|e| ab_core::Error::Backend(format!("warp_open_tab: {e}")))?;

        // Poll up to 3 s (20 × 150 ms) for a session UUID that was not in `before`.
        let new_session_id: Option<String> = if let Some(term) = &self.hub.terminal {
            let mut found = None;
            for _ in 0..20 {
                tokio::time::sleep(Duration::from_millis(150)).await;
                if let Ok(panes) = term.list_panes().await {
                    if let Some(p) = panes
                        .into_iter()
                        .find(|p| !before.contains(&p.id.to_string()))
                    {
                        found = Some(p.id.to_string());
                        break;
                    }
                }
            }
            found
        } else {
            None
        };

        Ok(ToolResult::json_text(&json!({
            "status": "ok",
            "uri": uri,
            "session_id": new_session_id,
            "detected": new_session_id.is_some()
        })))
    }
}

pub struct WarpOpenWindowTool;

impl WarpOpenWindowTool {
    pub fn new(_hub: Hub) -> Self {
        Self
    }
}

#[async_trait]
impl McpTool for WarpOpenWindowTool {
    fn name(&self) -> &'static str {
        "warp_open_window"
    }
    fn schema(&self) -> ToolSchema {
        ToolSchema {
            name: self.name().into(),
            description: "Open a new Warp window via warp://action/new_window (optional ?path=)."
                .into(),
            input_schema: json!({
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Directory for ?path=; omit for current cwd."
                    }
                }
            }),
        }
    }
    async fn execute(&self, args: Value, _ctx: &ToolContext) -> Result<ToolResult> {
        let raw = args.get("path").and_then(|v| v.as_str());
        let cwd = warp_resolve_tab_window_path(raw)?;
        let uri = warp_scheme_new_window(Some(&cwd));
        dispatch_warp_scheme_uri(&uri)
            .await
            .map_err(|e| ab_core::Error::Backend(format!("warp_open_window: {e}")))?;
        Ok(ToolResult::json_text(
            &json!({ "status": "ok", "uri": uri }),
        ))
    }
}

pub struct WarpOpenSettingsTool;

impl WarpOpenSettingsTool {
    pub fn new(_hub: Hub) -> Self {
        Self
    }
}

#[async_trait]
impl McpTool for WarpOpenSettingsTool {
    fn name(&self) -> &'static str {
        "warp_open_settings"
    }
    fn schema(&self) -> ToolSchema {
        ToolSchema {
            name: self.name().into(),
            description:
                "Try to open Warp settings via warp://action/open_settings_page (best-effort; \
                 not documented on docs.warp.dev — may no-op on some versions)."
                    .into(),
            input_schema: json!({ "type": "object", "properties": {} }),
        }
    }
    async fn execute(&self, _args: Value, _ctx: &ToolContext) -> Result<ToolResult> {
        let uri = warp_scheme_open_settings_page();
        dispatch_warp_scheme_uri(uri)
            .await
            .map_err(|e| ab_core::Error::Backend(format!("warp_open_settings: {e}")))?;
        Ok(ToolResult::json_text(
            &json!({ "status": "ok", "uri": uri }),
        ))
    }
}

pub struct WarpLaunchWorkflowTool;

impl WarpLaunchWorkflowTool {
    pub fn new(_hub: Hub) -> Self {
        Self
    }
}

#[async_trait]
impl McpTool for WarpLaunchWorkflowTool {
    fn name(&self) -> &'static str {
        "warp_launch_workflow"
    }
    fn schema(&self) -> ToolSchema {
        ToolSchema {
            name: self.name().into(),
            description: "Open a saved Warp Launch Configuration by name (warp://launch/<name>). \
                 See Warp docs — configs live under the Warp data directory."
                .into(),
            input_schema: json!({
                "type": "object",
                "properties": {
                    "configuration_name": {
                        "type": "string",
                        "description": "Launch configuration name (same as in Warp UI / YAML name field)."
                    },
                    "name": {
                        "type": "string",
                        "description": "Alias for configuration_name."
                    }
                },
                "required": []
            }),
        }
    }
    async fn execute(&self, args: Value, _ctx: &ToolContext) -> Result<ToolResult> {
        let name = args
            .get("configuration_name")
            .and_then(|v| v.as_str())
            .filter(|s| !s.is_empty())
            .or_else(|| {
                args.get("name")
                    .and_then(|v| v.as_str())
                    .filter(|s| !s.is_empty())
            });
        let Some(name) = name else {
            return Ok(ToolResult::error(
                "missing configuration_name (or alias name) — Launch Configuration identifier required",
            ));
        };
        let uri = warp_scheme_launch_configuration(name);
        dispatch_warp_scheme_uri(&uri)
            .await
            .map_err(|e| ab_core::Error::Backend(format!("warp_launch_workflow: {e}")))?;
        Ok(ToolResult::json_text(
            &json!({ "status": "ok", "uri": uri, "configuration_name": name }),
        ))
    }
}

pub struct WarpStatusTool {
    hub: Hub,
}
impl WarpStatusTool {
    pub fn new(hub: Hub) -> Self {
        Self { hub }
    }
}

#[async_trait]
impl McpTool for WarpStatusTool {
    fn name(&self) -> &'static str {
        "warp_status"
    }
    fn schema(&self) -> ToolSchema {
        ToolSchema {
            name: self.name().into(),
            description: "Warp environment probe: shell markers (TERM_PROGRAM / WARP_*), configured hub terminal backend id, \
                 URL opener, IPC bridge socket readiness, and whether `oz` is on PATH. Does not open Warp."
                .into(),
            input_schema: json!({ "type": "object", "properties": {} }),
        }
    }
    async fn execute(&self, _args: Value, _ctx: &ToolContext) -> Result<ToolResult> {
        let tid = self.hub.terminal.as_ref().map(|t| t.id().to_string());
        let snapshot = warp_status_snapshot(tid).await;
        Ok(ToolResult::json_text(&snapshot))
    }
}

// ===========================================================================
//                         codebase_index / codebase_search  (D3.2)
// ===========================================================================

pub struct CodebaseIndexTool {
    hub: Hub,
}
impl CodebaseIndexTool {
    pub fn new(hub: Hub) -> Self {
        Self { hub }
    }
}
#[async_trait]
impl McpTool for CodebaseIndexTool {
    fn name(&self) -> &'static str {
        "codebase_index"
    }
    fn schema(&self) -> ToolSchema {
        ToolSchema {
            name: self.name().into(),
            description: "Build a SQLite symbol index (functions, structs, classes, \
                 traits, enums) for a directory. codebase_search queries this without \
                 re-reading the filesystem. Re-indexing replaces. Languages: rust, \
                 python, typescript, javascript, go. Rows ship with embedding=NULL — \
                 call codebase_reindex afterward if you plan to use \
                 codebase_search(mode=\"semantic\")."
                .into(),
            input_schema: json!({
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Absolute path to the directory to index. Defaults to process cwd."
                    },
                    "languages": {
                        "type": "array",
                        "items": { "type": "string" },
                        "default": [],
                        "description": "Limit to these languages (e.g. [\"rust\"]). Empty = all supported."
                    }
                }
            }),
        }
    }
    async fn execute(&self, args: Value, _ctx: &ToolContext) -> Result<ToolResult> {
        let store = match &self.hub.store {
            Some(s) => s.clone(),
            None => return Ok(ToolResult::error("no store configured")),
        };
        let path = args
            .get("path")
            .and_then(|v| v.as_str())
            .filter(|s| !s.is_empty())
            .map(|s| s.to_string())
            .or_else(|| std::env::current_dir().ok().map(|p| p.display().to_string()))
            .unwrap_or_else(|| "/".to_string());
        let languages: Vec<String> = args
            .get("languages")
            .and_then(|v| v.as_array())
            .map(|a| {
                a.iter()
                    .filter_map(|x| x.as_str().map(|s| s.to_string()))
                    .collect()
            })
            .unwrap_or_default();

        match store.codebase_index(&path, &languages).await {
            Ok(stats) => Ok(ToolResult::json_text(
                &serde_json::to_value(stats).unwrap_or(Value::Null),
            )),
            Err(e) => Ok(ToolResult::error(&format!("codebase_index failed: {e}"))),
        }
    }
}

pub struct CodebaseSearchTool {
    hub: Hub,
}
impl CodebaseSearchTool {
    pub fn new(hub: Hub) -> Self {
        Self { hub }
    }
}
#[async_trait]
impl McpTool for CodebaseSearchTool {
    fn name(&self) -> &'static str {
        "codebase_search"
    }
    fn schema(&self) -> ToolSchema {
        ToolSchema {
            name: self.name().into(),
            description: "Search the codebase symbol index built by codebase_index. \
                 Returns file_path, line, kind (fn/struct/class/…), name, signature for \
                 each match. mode=semantic enables natural-language queries. Run \
                 codebase_index first if no results appear."
                .into(),
            input_schema: json!({
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Substring to match (exact) or description to match by meaning (semantic)."
                    },
                    "mode": {
                        "type": "string",
                        "enum": ["exact", "semantic"],
                        "default": "exact",
                        "description": "exact: substring LIKE match (default). semantic: vector cosine similarity — finds symbols by meaning even without exact name match."
                    },
                    "kind": {
                        "type": "string",
                        "description": "Optional exact kind filter: fn | struct | enum | trait | type | const | mod | impl | class | def | function | interface | method | macro"
                    },
                    "file_filter": {
                        "type": "string",
                        "description": "Optional substring matched against file_path (e.g. 'hub.rs' or 'src/store')."
                    },
                    "root_path": {
                        "type": "string",
                        "description": "Optional root directory to restrict results to a specific index."
                    },
                    "limit": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 500,
                        "default": 30
                    }
                },
                "required": ["query"]
            }),
        }
    }
    async fn execute(&self, args: Value, _ctx: &ToolContext) -> Result<ToolResult> {
        let store = match &self.hub.store {
            Some(s) => s.clone(),
            None => return Ok(ToolResult::error("no store configured")),
        };
        let query = args
            .get("query")
            .and_then(|v| v.as_str())
            .unwrap_or("")
            .to_string();
        if query.is_empty() {
            return Ok(ToolResult::error("'query' is required"));
        }
        let mode = args
            .get("mode")
            .and_then(|v| v.as_str())
            .filter(|s| *s == "semantic")
            .unwrap_or("exact")
            .to_string();
        let kind = args
            .get("kind")
            .and_then(|v| v.as_str())
            .filter(|s| !s.is_empty())
            .map(|s| s.to_string());
        let file_filter = args
            .get("file_filter")
            .and_then(|v| v.as_str())
            .filter(|s| !s.is_empty())
            .map(|s| s.to_string());
        let root_path = args
            .get("root_path")
            .and_then(|v| v.as_str())
            .filter(|s| !s.is_empty())
            .map(|s| s.to_string());
        let limit = args
            .get("limit")
            .and_then(|v| v.as_u64())
            .unwrap_or(30)
            .min(500) as u32;

        match store
            .codebase_search(
                &query,
                kind.as_deref(),
                file_filter.as_deref(),
                root_path.as_deref(),
                limit,
                &mode,
            )
            .await
        {
            Ok(hits) => Ok(ToolResult::json_text(
                &serde_json::to_value(hits).unwrap_or(Value::Null),
            )),
            Err(e) => Ok(ToolResult::error(&format!("codebase_search failed: {e}"))),
        }
    }
}

// ===========================================================================
//                       tailscale REST API — ACL editing
// ===========================================================================

pub struct TailscaleAclGetTool;
impl Default for TailscaleAclGetTool {
    fn default() -> Self {
        Self
    }
}
impl TailscaleAclGetTool {
    pub fn new() -> Self {
        Self
    }
}
#[async_trait]
impl McpTool for TailscaleAclGetTool {
    fn name(&self) -> &'static str {
        "tailscale_acl_get"
    }
    fn schema(&self) -> ToolSchema {
        ToolSchema {
            name: self.name().into(),
            description:
                "Fetch the current tailnet Access Control List as HuJSON \
                 (HCL-flavored JSON with comments). Returns `body` plus the \
                 `etag` you can pass to `tailscale_acl_set` for safe \
                 optimistic-concurrency writes. Requires \
                 `TAILSCALE_OAUTH_CLIENT_ID` + `TAILSCALE_OAUTH_CLIENT_SECRET` \
                 env (OAuth client with `acl` scope; create one at \
                 login.tailscale.com → Settings → OAuth clients)."
                    .into(),
            input_schema: json!({
                "type": "object",
                "properties": {},
                "additionalProperties": false
            }),
        }
    }
    async fn execute(&self, _args: Value, _ctx: &ToolContext) -> Result<ToolResult> {
        let client = match crate::tailscale_api::TailscaleClient::from_env() {
            Ok(c) => c,
            Err(e) => return Ok(ToolResult::error(&format!("{e}"))),
        };
        match client.acl_get().await {
            Ok(r) => Ok(ToolResult::json_text(&json!({
                "etag": r.etag,
                "body": r.body
            }))),
            Err(e) => Ok(ToolResult::error(&format!("{e}"))),
        }
    }
}

pub struct TailscaleAclSetTool;
impl Default for TailscaleAclSetTool {
    fn default() -> Self {
        Self
    }
}
impl TailscaleAclSetTool {
    pub fn new() -> Self {
        Self
    }
}
#[async_trait]
impl McpTool for TailscaleAclSetTool {
    fn name(&self) -> &'static str {
        "tailscale_acl_set"
    }
    fn schema(&self) -> ToolSchema {
        ToolSchema {
            name: self.name().into(),
            description:
                "Replace the tailnet ACL with `body` (HuJSON or strict JSON). \
                 Set `validate_only: true` to dry-run via the validate endpoint \
                 — recommended before any real write. Pass `etag` from a prior \
                 `tailscale_acl_get` to enable optimistic concurrency (the API \
                 returns 412 if the ACL changed since you read it). \
                 IMPORTANT: a bad ACL can lock you and other tailnet members \
                 out of SSH / services within seconds; ALWAYS validate first \
                 unless you're rolling back a known-good config."
                    .into(),
            input_schema: json!({
                "type": "object",
                "properties": {
                    "body":          { "type": "string", "description": "Full ACL HuJSON/JSON content (REQUIRED)." },
                    "validate_only": { "type": "boolean", "default": false, "description": "If true, hits /acl/validate instead of /acl. No write." },
                    "etag":          { "type": "string", "description": "etag from tailscale_acl_get for safe overwrite (sent as If-Match)." }
                },
                "required": ["body"],
                "additionalProperties": false
            }),
        }
    }
    async fn execute(&self, args: Value, _ctx: &ToolContext) -> Result<ToolResult> {
        let body = match args
            .get("body")
            .and_then(|v| v.as_str())
            .filter(|s| !s.is_empty())
        {
            Some(s) => s,
            None => return Ok(ToolResult::error("missing or empty 'body'")),
        };
        let validate_only = args
            .get("validate_only")
            .and_then(|v| v.as_bool())
            .unwrap_or(false);
        let etag = args
            .get("etag")
            .and_then(|v| v.as_str())
            .filter(|s| !s.is_empty());

        let client = match crate::tailscale_api::TailscaleClient::from_env() {
            Ok(c) => c,
            Err(e) => return Ok(ToolResult::error(&format!("{e}"))),
        };
        if validate_only {
            match client.acl_validate(body).await {
                Ok(resp) => Ok(ToolResult::json_text(&json!({
                    "validate_only": true,
                    "ok": true,
                    "response": resp
                }))),
                Err(e) => Ok(ToolResult::error(&format!("{e}"))),
            }
        } else {
            match client.acl_set(body, etag).await {
                Ok(resp) => Ok(ToolResult::json_text(&json!({
                    "validate_only": false,
                    "ok": true,
                    "response": resp
                }))),
                Err(e) => Ok(ToolResult::error(&format!("{e}"))),
            }
        }
    }
}

// ===========================================================================
//                            github_* — REST API
// ===========================================================================

pub struct GithubIssueListTool;
impl Default for GithubIssueListTool {
    fn default() -> Self { Self }
}
impl GithubIssueListTool {
    pub fn new() -> Self { Self }
}
#[async_trait]
impl McpTool for GithubIssueListTool {
    fn name(&self) -> &'static str { "github_issue_list" }
    fn schema(&self) -> ToolSchema {
        ToolSchema {
            name: self.name().into(),
            description:
                "List GitHub issues for `owner/repo`. Pull requests are filtered \
                 out (use `github_pr_list` for those). Requires `GITHUB_TOKEN` env \
                 (fine-grained PAT with Issues read scope, or classic PAT with \
                 `repo`). Defaults: state=open, per_page=20."
                    .into(),
            input_schema: json!({
                "type": "object",
                "properties": {
                    "owner":    { "type": "string", "description": "Repo owner / user / org" },
                    "repo":     { "type": "string", "description": "Repo name" },
                    "state":    { "type": "string", "enum": ["open","closed","all"], "default": "open" },
                    "per_page": { "type": "integer", "default": 20, "minimum": 1, "maximum": 100 },
                    "labels":   { "type": "string", "description": "Comma-separated label names to filter (optional)" }
                },
                "required": ["owner","repo"],
                "additionalProperties": false
            }),
        }
    }
    async fn execute(&self, args: Value, _ctx: &ToolContext) -> Result<ToolResult> {
        let owner = match args.get("owner").and_then(|v| v.as_str()).filter(|s| !s.is_empty()) {
            Some(s) => s, None => return Ok(ToolResult::error("missing 'owner'")),
        };
        let repo = match args.get("repo").and_then(|v| v.as_str()).filter(|s| !s.is_empty()) {
            Some(s) => s, None => return Ok(ToolResult::error("missing 'repo'")),
        };
        let state = args.get("state").and_then(|v| v.as_str()).unwrap_or("open");
        let per_page = args.get("per_page").and_then(|v| v.as_u64()).unwrap_or(20).clamp(1, 100) as u32;
        let labels = args.get("labels").and_then(|v| v.as_str());
        let client = match crate::github_api::GitHubClient::from_env() {
            Ok(c) => c, Err(e) => return Ok(ToolResult::error(&format!("{e}"))),
        };
        match client.issue_list(owner, repo, state, per_page, labels).await {
            Ok(rows) => Ok(ToolResult::json_text(&json!({
                "count": rows.len(),
                "issues": rows
            }))),
            Err(e) => Ok(ToolResult::error(&format!("{e}"))),
        }
    }
}

pub struct GithubIssueCreateTool;
impl Default for GithubIssueCreateTool {
    fn default() -> Self { Self }
}
impl GithubIssueCreateTool {
    pub fn new() -> Self { Self }
}
#[async_trait]
impl McpTool for GithubIssueCreateTool {
    fn name(&self) -> &'static str { "github_issue_create" }
    fn schema(&self) -> ToolSchema {
        ToolSchema {
            name: self.name().into(),
            description:
                "Create a GitHub issue on `owner/repo`. Requires `GITHUB_TOKEN` \
                 with Issues write permission. Returns the new issue's number, \
                 html_url, etc. Use sparingly — issues are public on public repos \
                 and notify watchers."
                    .into(),
            input_schema: json!({
                "type": "object",
                "properties": {
                    "owner":  { "type": "string", "description": "Repo owner / user / org" },
                    "repo":   { "type": "string", "description": "Repo name" },
                    "title":  { "type": "string", "description": "Issue title (REQUIRED)" },
                    "body":   { "type": "string", "description": "Issue body (Markdown). Empty allowed but discouraged." },
                    "labels": { "type": "array", "items": { "type": "string" }, "description": "Optional labels to apply (must already exist on the repo)." }
                },
                "required": ["owner","repo","title"],
                "additionalProperties": false
            }),
        }
    }
    async fn execute(&self, args: Value, _ctx: &ToolContext) -> Result<ToolResult> {
        let owner = match args.get("owner").and_then(|v| v.as_str()).filter(|s| !s.is_empty()) {
            Some(s) => s, None => return Ok(ToolResult::error("missing 'owner'")),
        };
        let repo = match args.get("repo").and_then(|v| v.as_str()).filter(|s| !s.is_empty()) {
            Some(s) => s, None => return Ok(ToolResult::error("missing 'repo'")),
        };
        let title = match args.get("title").and_then(|v| v.as_str()).filter(|s| !s.is_empty()) {
            Some(s) => s, None => return Ok(ToolResult::error("missing 'title'")),
        };
        let body = args.get("body").and_then(|v| v.as_str()).unwrap_or("");
        let labels = args.get("labels").and_then(|v| v.as_array()).map(|arr| {
            arr.iter()
                .filter_map(|x| x.as_str().map(String::from))
                .collect::<Vec<_>>()
        });
        let client = match crate::github_api::GitHubClient::from_env() {
            Ok(c) => c, Err(e) => return Ok(ToolResult::error(&format!("{e}"))),
        };
        match client.issue_create(owner, repo, title, body, labels).await {
            Ok(issue) => Ok(ToolResult::json_text(&json!({ "issue": issue }))),
            Err(e) => Ok(ToolResult::error(&format!("{e}"))),
        }
    }
}

pub struct GithubPrListTool;
impl Default for GithubPrListTool {
    fn default() -> Self { Self }
}
impl GithubPrListTool {
    pub fn new() -> Self { Self }
}
#[async_trait]
impl McpTool for GithubPrListTool {
    fn name(&self) -> &'static str { "github_pr_list" }
    fn schema(&self) -> ToolSchema {
        ToolSchema {
            name: self.name().into(),
            description:
                "List GitHub pull requests for `owner/repo`. Defaults: state=open, \
                 per_page=20. Each PR includes head/base ref, draft flag, author. \
                 Requires `GITHUB_TOKEN` with PR read scope."
                    .into(),
            input_schema: json!({
                "type": "object",
                "properties": {
                    "owner":    { "type": "string", "description": "Repo owner / user / org" },
                    "repo":     { "type": "string", "description": "Repo name" },
                    "state":    { "type": "string", "enum": ["open","closed","all"], "default": "open" },
                    "per_page": { "type": "integer", "default": 20, "minimum": 1, "maximum": 100 }
                },
                "required": ["owner","repo"],
                "additionalProperties": false
            }),
        }
    }
    async fn execute(&self, args: Value, _ctx: &ToolContext) -> Result<ToolResult> {
        let owner = match args.get("owner").and_then(|v| v.as_str()).filter(|s| !s.is_empty()) {
            Some(s) => s, None => return Ok(ToolResult::error("missing 'owner'")),
        };
        let repo = match args.get("repo").and_then(|v| v.as_str()).filter(|s| !s.is_empty()) {
            Some(s) => s, None => return Ok(ToolResult::error("missing 'repo'")),
        };
        let state = args.get("state").and_then(|v| v.as_str()).unwrap_or("open");
        let per_page = args.get("per_page").and_then(|v| v.as_u64()).unwrap_or(20).clamp(1, 100) as u32;
        let client = match crate::github_api::GitHubClient::from_env() {
            Ok(c) => c, Err(e) => return Ok(ToolResult::error(&format!("{e}"))),
        };
        match client.pr_list(owner, repo, state, per_page).await {
            Ok(rows) => Ok(ToolResult::json_text(&json!({
                "count": rows.len(),
                "pulls": rows
            }))),
            Err(e) => Ok(ToolResult::error(&format!("{e}"))),
        }
    }
}

// ===========================================================================
//                                  registry
// ===========================================================================

/// Per-tool surface-area tier for `AGENT_BRIDGE_TOOL_PROFILE` filtering.
///
/// Claude Code (and similar MCP clients) cap the live tool list at ~64
/// across *all* configured MCP servers. With agent-bridge alone registering
/// 69 tools today, that cap was getting hit and clients silently dropped
/// 5–20 tools at startup. Tiers let us keep the most-used 40-ish in the
/// default registration and gate the rest behind an env flag.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Tier {
    /// Always registered. The smallest set that lets a typical interactive
    /// Claude session work end-to-end (memory navigation, terminal control,
    /// agent_spawn, plan, shell_exec, session lifecycle bootstrap/finalize).
    Essential,
    /// Default-on. Adds hook-friendly + multi-agent + maintenance ops:
    /// memory consolidation, session curation, agent inbox, codebase index,
    /// terminal_read_blocks (Warp), notify.
    Standard,
    /// Default-off. Specialty surfaces: browser_*, warp_*, oz_*, MCP
    /// introspection (mcp_recent_errors / mcp_call_stats / mcp_config_audit),
    /// memory admin (export/import/consolidate/auto_curate/graph_export),
    /// osc_parse, hook_status, context_budget. Enable explicitly with
    /// `AGENT_BRIDGE_TOOL_PROFILE=all` (or pick what you need via finer
    /// gates in the future).
    Niche,
}

#[derive(Debug, Clone, Copy)]
pub enum ToolProfile {
    Essential,
    Standard,
    All,
}

impl ToolProfile {
    pub fn from_env() -> Self {
        match std::env::var("AGENT_BRIDGE_TOOL_PROFILE")
            .ok()
            .map(|s| s.trim().to_lowercase())
            .as_deref()
        {
            Some("essential") | Some("minimal") => Self::Essential,
            Some("all") | Some("full") => Self::All,
            _ => Self::Standard,
        }
    }

    pub fn label(self) -> &'static str {
        match self {
            Self::Essential => "essential",
            Self::Standard => "standard",
            Self::All => "all",
        }
    }

    pub fn includes(self, tier: Tier) -> bool {
        match (self, tier) {
            (Self::All, _) => true,
            (Self::Standard, Tier::Niche) => false,
            (Self::Standard, _) => true,
            (Self::Essential, Tier::Essential) => true,
            (Self::Essential, _) => false,
        }
    }
}

fn reg_if(reg: &mut ToolRegistry, profile: ToolProfile, tier: Tier, tool: Arc<dyn McpTool>) {
    if profile.includes(tier) {
        reg.register(tool);
    }
}

pub struct SkillsRecommendTool {
    hub: Hub,
}
impl SkillsRecommendTool {
    pub fn new(hub: Hub) -> Self {
        Self { hub }
    }
}
#[async_trait]
impl McpTool for SkillsRecommendTool {
    fn name(&self) -> &'static str {
        "skills_recommend"
    }
    fn schema(&self) -> ToolSchema {
        ToolSchema {
            name: self.name().into(),
            description: "Recommend relevant indexed Claude Code skills for a task. Searches \
                 the local skill index (built via `agent-bridge skills index|seed`) and returns \
                 top-K matches with source repo, lint status, and install command. Use this \
                 before reaching for ad-hoc instructions when the user describes a coding/ops \
                 task that might already have a skill written for it."
                .into(),
            input_schema: json!({
                "type": "object",
                "properties": {
                    "query": { "type": "string", "description": "Task description in natural language (e.g. 'edit pdf forms', 'audit helm chart security')." },
                    "limit": { "type": "integer", "minimum": 1, "maximum": 50, "default": 5 }
                },
                "required": ["query"]
            }),
        }
    }
    async fn execute(&self, args: Value, _ctx: &ToolContext) -> Result<ToolResult> {
        let store = match &self.hub.store {
            Some(s) => s.clone(),
            None => return Ok(ToolResult::error("no store configured")),
        };
        let q = args
            .get("query")
            .and_then(|v| v.as_str())
            .unwrap_or("")
            .to_string();
        if q.trim().is_empty() {
            return Ok(ToolResult::error("query is required"));
        }
        let limit = args
            .get("limit")
            .and_then(|v| v.as_u64())
            .unwrap_or(5)
            .clamp(1, 50) as u32;

        let tag_filter = vec!["skill".to_string()];
        let hits = store.memory_search(&q, &tag_filter, limit).await?;
        let recs: Vec<Value> = hits
            .into_iter()
            .map(|h| {
                let src = tag_value_in(&h.record.tags, "src:");
                let lint = tag_value_in(&h.record.tags, "lint:")
                    .map(|v| format!("lint:{}", v))
                    .unwrap_or_else(|| "lint:?".to_string());
                let tools = tag_value_in(&h.record.tags, "tools:");
                // First non-empty paragraph is the description we stored
                // (frontmatter description ‖ first body line). Truncate
                // for token thrift; agents can call memory_get for full.
                let summary: String = h
                    .record
                    .content
                    .lines()
                    .find(|l| !l.trim().is_empty())
                    .unwrap_or("")
                    .chars()
                    .take(400)
                    .collect();
                json!({
                    "key": h.record.key,
                    "src": src,
                    "summary": summary,
                    "tools": tools,
                    "lint": lint,
                    "score": h.score,
                    "install": format!("agent-bridge skills install {} --yes", h.record.key),
                })
            })
            .collect();
        let resp = json!({
            "query": q,
            "count": recs.len(),
            "skills": recs,
            "hint": if recs.is_empty() {
                "no indexed skills match — bootstrap via `agent-bridge skills seed` if the index is empty."
            } else {
                "review the top hit's `summary` and `lint`; install with the `install` command (or call `memory_get` on the key for the full SKILL.md)."
            },
        });
        Ok(ToolResult::json_text(&resp))
    }
}

fn tag_value_in(tags: &[String], prefix: &str) -> Option<String> {
    tags.iter()
        .find(|t| t.starts_with(prefix))
        .map(|t| t[prefix.len()..].to_string())
}

pub fn build_registry(hub: Hub) -> ToolRegistry {
    let profile = ToolProfile::from_env();
    let mut reg = ToolRegistry::new();

    // ── ESSENTIAL ──────────────────────────────────────────────────────
    // Memory: query + write + delete + graph navigation.
    reg_if(&mut reg, profile, Tier::Essential, Arc::new(MemorySearchTool::new(hub.clone())));
    reg_if(&mut reg, profile, Tier::Essential, Arc::new(MemorySaveTool::new(hub.clone())));
    reg_if(&mut reg, profile, Tier::Essential, Arc::new(MemoryGetTool::new(hub.clone())));
    reg_if(&mut reg, profile, Tier::Essential, Arc::new(MemoryListTool::new(hub.clone())));
    reg_if(&mut reg, profile, Tier::Essential, Arc::new(MemoryDeleteTool::new(hub.clone())));
    reg_if(&mut reg, profile, Tier::Essential, Arc::new(MemoryNeighborsTool::new(hub.clone())));
    reg_if(&mut reg, profile, Tier::Standard, Arc::new(MemoryCoactivationTopTool::new(hub.clone())));
    // Terminal: list + send + read + split + resize.
    reg_if(&mut reg, profile, Tier::Essential, Arc::new(TerminalListTool::new(hub.clone())));
    reg_if(&mut reg, profile, Tier::Essential, Arc::new(TerminalSendKeysTool::new(hub.clone())));
    reg_if(&mut reg, profile, Tier::Essential, Arc::new(TerminalReadOutputTool::new(hub.clone())));
    reg_if(&mut reg, profile, Tier::Essential, Arc::new(TerminalSplitTool::new(hub.clone())));
    reg_if(&mut reg, profile, Tier::Essential, Arc::new(TerminalResizeTool::new(hub.clone())));
    // Agent runtime: spawn + observe sessions.
    reg_if(&mut reg, profile, Tier::Essential, Arc::new(AgentSpawnTool::new(hub.clone())));
    reg_if(&mut reg, profile, Tier::Essential, Arc::new(AgentSessionGetTool::new(hub.clone())));
    reg_if(&mut reg, profile, Tier::Essential, Arc::new(AgentSessionWaitTool::new(hub.clone())));
    reg_if(&mut reg, profile, Tier::Essential, Arc::new(AgentSessionListTool::new(hub.clone())));
    // Shell + lifecycle bootstrap + ops introspection that callers ask first.
    reg_if(&mut reg, profile, Tier::Essential, Arc::new(ShellExecTool::new(hub.clone())));
    reg_if(&mut reg, profile, Tier::Essential, Arc::new(SessionBootstrapTool::new(hub.clone())));
    reg_if(&mut reg, profile, Tier::Essential, Arc::new(SessionFinalizeTool::new(hub.clone())));
    reg_if(&mut reg, profile, Tier::Essential, Arc::new(CapabilitiesTool::new(hub.clone())));
    reg_if(&mut reg, profile, Tier::Essential, Arc::new(ProjectDetectTool::new(hub.clone())));
    reg_if(&mut reg, profile, Tier::Essential, Arc::new(ChangesDigestTool::new(hub.clone())));
    // Plans + worktrees + codebase search.
    reg_if(&mut reg, profile, Tier::Essential, Arc::new(PlanSaveTool::new(hub.clone())));
    reg_if(&mut reg, profile, Tier::Essential, Arc::new(PlanLoadTool::new(hub.clone())));
    reg_if(&mut reg, profile, Tier::Essential, Arc::new(PlanUpdateTool::new(hub.clone())));
    reg_if(&mut reg, profile, Tier::Essential, Arc::new(WorktreeCreateTool::new(hub.clone())));
    reg_if(&mut reg, profile, Tier::Essential, Arc::new(CodebaseSearchTool::new(hub.clone())));

    // ── STANDARD (default-on, hook-friendly + multi-agent + maintenance) ──
    reg_if(&mut reg, profile, Tier::Standard, Arc::new(MemoryCompactTool::new(hub.clone())));
    reg_if(&mut reg, profile, Tier::Standard, Arc::new(MemoryReindexTool::new(hub.clone())));
    reg_if(&mut reg, profile, Tier::Standard, Arc::new(CodebaseReindexTool::new(hub.clone())));
    reg_if(&mut reg, profile, Tier::Standard, Arc::new(MemoryLinkTool::new(hub.clone())));
    reg_if(&mut reg, profile, Tier::Standard, Arc::new(MemoryStatsTool::new(hub.clone())));
    reg_if(&mut reg, profile, Tier::Standard, Arc::new(MemorySuggestTool::new(hub.clone())));
    reg_if(&mut reg, profile, Tier::Standard, Arc::new(AgentKillTool::new(hub.clone())));
    reg_if(&mut reg, profile, Tier::Standard, Arc::new(AgentMessageTool::new(hub.clone())));
    reg_if(&mut reg, profile, Tier::Standard, Arc::new(AgentInboxTool::new(hub.clone())));
    // Forum (v18): cross-process collaboration whiteboard.
    reg_if(&mut reg, profile, Tier::Standard, Arc::new(ForumPostTool::new(hub.clone())));
    reg_if(&mut reg, profile, Tier::Standard, Arc::new(ForumReadTool::new(hub.clone())));
    reg_if(&mut reg, profile, Tier::Standard, Arc::new(ForumSubscribeTool::new(hub.clone())));
    reg_if(&mut reg, profile, Tier::Standard, Arc::new(ForumListThreadsTool::new(hub.clone())));
    reg_if(&mut reg, profile, Tier::Standard, Arc::new(ForumSetThreadStatusTool::new(hub.clone())));
    // Presence (v19): identity convention + agent registry (A2A AgentCard-aligned).
    reg_if(&mut reg, profile, Tier::Standard, Arc::new(SessionIdentityTool::new(hub.clone())));
    reg_if(&mut reg, profile, Tier::Standard, Arc::new(AgentPresenceAnnounceTool::new(hub.clone())));
    reg_if(&mut reg, profile, Tier::Standard, Arc::new(AgentPresenceListTool::new(hub.clone())));
    // Tailscale REST API: ACL editing without browser automation.
    reg_if(&mut reg, profile, Tier::Standard, Arc::new(TailscaleAclGetTool::new()));
    reg_if(&mut reg, profile, Tier::Standard, Arc::new(TailscaleAclSetTool::new()));
    // GitHub REST API: issue/PR management without browser/gh-cli.
    reg_if(&mut reg, profile, Tier::Standard, Arc::new(GithubIssueListTool::new()));
    reg_if(&mut reg, profile, Tier::Standard, Arc::new(GithubIssueCreateTool::new()));
    reg_if(&mut reg, profile, Tier::Standard, Arc::new(GithubPrListTool::new()));
    reg_if(&mut reg, profile, Tier::Standard, Arc::new(SessionCurateTool::new(hub.clone())));
    reg_if(&mut reg, profile, Tier::Standard, Arc::new(SessionHandoffBriefTool::new(hub.clone())));
    reg_if(&mut reg, profile, Tier::Standard, Arc::new(SessionLifecycleStepTool::new(hub.clone())));
    reg_if(&mut reg, profile, Tier::Standard, Arc::new(WorktreeListTool::new(hub.clone())));
    reg_if(&mut reg, profile, Tier::Standard, Arc::new(WorktreeRemoveTool::new(hub.clone())));
    reg_if(&mut reg, profile, Tier::Standard, Arc::new(CodebaseIndexTool::new(hub.clone())));
    reg_if(&mut reg, profile, Tier::Standard, Arc::new(TerminalReadBlocksTool::new(hub.clone())));
    reg_if(&mut reg, profile, Tier::Standard, Arc::new(NotifyTool::new(hub.clone())));
    reg_if(&mut reg, profile, Tier::Standard, Arc::new(NotificationsRecentTool::new(hub.clone())));
    // Skill library (Phase C): in-loop recommendation over the local skill index.
    reg_if(&mut reg, profile, Tier::Standard, Arc::new(SkillsRecommendTool::new(hub.clone())));

    // ── NICHE (opt-in via AGENT_BRIDGE_TOOL_PROFILE=all) ───────────────
    // Browser automation surface.
    reg_if(&mut reg, profile, Tier::Niche, Arc::new(BrowserNavigateTool::new(hub.clone())));
    reg_if(&mut reg, profile, Tier::Niche, Arc::new(BrowserEvalTool::new(hub.clone())));
    reg_if(&mut reg, profile, Tier::Niche, Arc::new(BrowserSnapshotTool::new(hub.clone())));
    reg_if(&mut reg, profile, Tier::Niche, Arc::new(BrowserClickTool::new(hub.clone())));
    reg_if(&mut reg, profile, Tier::Niche, Arc::new(BrowserScreenshotTool::new(hub.clone())));
    reg_if(&mut reg, profile, Tier::Niche, Arc::new(BrowserExtractTextTool::new(hub.clone())));
    reg_if(&mut reg, profile, Tier::Niche, Arc::new(BrowserFillFormTool::new(hub.clone())));
    // Warp URL-scheme + status.
    reg_if(&mut reg, profile, Tier::Niche, Arc::new(WarpOpenTabTool::new(hub.clone())));
    reg_if(&mut reg, profile, Tier::Niche, Arc::new(WarpOpenWindowTool::new(hub.clone())));
    reg_if(&mut reg, profile, Tier::Niche, Arc::new(WarpOpenSettingsTool::new(hub.clone())));
    reg_if(&mut reg, profile, Tier::Niche, Arc::new(WarpLaunchWorkflowTool::new(hub.clone())));
    reg_if(&mut reg, profile, Tier::Niche, Arc::new(WarpStatusTool::new(hub.clone())));
    // Warp-Oz cloud runs.
    reg_if(&mut reg, profile, Tier::Niche, Arc::new(OzRunGetTool::new(hub.clone())));
    reg_if(&mut reg, profile, Tier::Niche, Arc::new(OzRunListTool::new(hub.clone())));
    reg_if(&mut reg, profile, Tier::Niche, Arc::new(OzRunCancelTool::new(hub.clone())));
    // Ops introspection / debugging.
    reg_if(&mut reg, profile, Tier::Niche, Arc::new(OscParseTool::new(hub.clone())));
    reg_if(&mut reg, profile, Tier::Niche, Arc::new(McpRecentErrorsTool::new(hub.clone())));
    reg_if(&mut reg, profile, Tier::Niche, Arc::new(McpCallStatsTool::new(hub.clone())));
    reg_if(&mut reg, profile, Tier::Niche, Arc::new(McpConfigAuditTool::new()));
    reg_if(&mut reg, profile, Tier::Niche, Arc::new(ContextBudgetTool::new()));
    reg_if(&mut reg, profile, Tier::Niche, Arc::new(HookStatusTool::new(hub.clone())));
    // Memory admin / visualisation.
    reg_if(&mut reg, profile, Tier::Niche, Arc::new(MemoryExportTool::new(hub.clone())));
    reg_if(&mut reg, profile, Tier::Niche, Arc::new(MemoryImportTool::new(hub.clone())));
    reg_if(&mut reg, profile, Tier::Niche, Arc::new(MemoryConsolidateTool::new(hub.clone())));
    reg_if(&mut reg, profile, Tier::Niche, Arc::new(MemoryAutoCurateTool::new(hub.clone())));
    reg_if(&mut reg, profile, Tier::Niche, Arc::new(MemoryGraphExportTool::new(hub)));

    tracing::info!(
        profile = profile.label(),
        tools = reg.list().len(),
        "MCP tool registry built (set AGENT_BRIDGE_TOOL_PROFILE=essential|standard|all)"
    );
    reg
}

/// Path to the persistent user profile document.
/// Mirrors the state.db data directory: `$XDG_DATA_HOME/agent-bridge/USER.md`.
fn user_profile_path() -> PathBuf {
    if let Ok(xdg) = std::env::var("XDG_DATA_HOME") {
        return PathBuf::from(xdg).join("agent-bridge").join("USER.md");
    }
    if let Ok(home) = std::env::var("HOME") {
        return PathBuf::from(home)
            .join(".local/share/agent-bridge")
            .join("USER.md");
    }
    PathBuf::from("./USER.md")
}

/// Path to the persistent **agent self-profile** document — the agent's own
/// values, working style, and self-observations. Companion to `USER.md`.
/// Long-term destination for AiOT Seed `SelfModel` initialization (see
/// `decision_aiot_seed_as_agent_continuity_substrate_20260503`); for now it
/// is a plain Markdown file the agent maintains itself.
fn agent_profile_path() -> PathBuf {
    if let Ok(xdg) = std::env::var("XDG_DATA_HOME") {
        return PathBuf::from(xdg).join("agent-bridge").join("AGENT.md");
    }
    if let Ok(home) = std::env::var("HOME") {
        return PathBuf::from(home)
            .join(".local/share/agent-bridge")
            .join("AGENT.md");
    }
    PathBuf::from("./AGENT.md")
}

/// Default cap on per-call AGENT.md change ratio. 0.5 means at most half
/// of (old_lines ∪ new_lines) may be different. Borrowed from AiOT's
/// `identity_anchor.py::MAX_STEP_DRIFT`: the stable identity layer should
/// not be rewritable in one shot. Pass `agent_profile_force=true` to bypass.
const AGENT_PROFILE_DRIFT_CAP: f32 = 0.5;

/// Compute change ratio between two AGENT.md texts using line-set Jaccard
/// distance (treating each non-empty trimmed line as a trait token).
/// Returns 0.0 if `old` is empty (first write is unconstrained).
/// Range: 0.0 (identical) → 1.0 (no shared lines).
fn agent_profile_diff_ratio(old: &str, new: &str) -> f32 {
    let collect = |s: &str| -> std::collections::HashSet<String> {
        s.lines()
            .map(|l| l.trim().to_string())
            .filter(|l| !l.is_empty())
            .collect()
    };
    let old_set = collect(old);
    if old_set.is_empty() {
        return 0.0; // first write, no drift cap
    }
    let new_set = collect(new);
    let intersection = old_set.intersection(&new_set).count();
    let union = old_set.union(&new_set).count();
    if union == 0 {
        return 0.0;
    }
    1.0 - (intersection as f32 / union as f32)
}

/// Directory holding **letter-to-future-self** files. Each letter is an
/// append-only Markdown snippet written by the agent at session end (via
/// `session_finalize(letter=...)`). Filename is `letter_<unix_ts>.md` so
/// directory listing sorts chronologically. Letters carry momentary
/// thinking that AGENT.md (stable identity) shouldn't.
fn letters_dir() -> PathBuf {
    if let Ok(xdg) = std::env::var("XDG_DATA_HOME") {
        return PathBuf::from(xdg).join("agent-bridge").join("letters");
    }
    if let Ok(home) = std::env::var("HOME") {
        return PathBuf::from(home)
            .join(".local/share/agent-bridge")
            .join("letters");
    }
    PathBuf::from("./letters")
}

/// Return paths of the `n` most recent letter files, newest first.
/// Empty vec if directory missing or empty.
fn recent_letters(n: usize) -> Vec<PathBuf> {
    let dir = letters_dir();
    let Ok(entries) = std::fs::read_dir(&dir) else {
        return Vec::new();
    };
    let mut paths: Vec<PathBuf> = entries
        .filter_map(|e| e.ok().map(|e| e.path()))
        .filter(|p| {
            p.extension().and_then(|s| s.to_str()) == Some("md")
                && p.file_name()
                    .and_then(|s| s.to_str())
                    .map(|s| s.starts_with("letter_"))
                    .unwrap_or(false)
        })
        .collect();
    // Filename embeds unix_ts so lexicographic sort = chronological;
    // reverse to get newest first.
    paths.sort();
    paths.reverse();
    paths.truncate(n);
    paths
}

// ── AiOT Soul (Phase α′) ────────────────────────────────────────────────────
//
// Phase α′ continuity bridge: read-only static injection of AiOT's
// `identity_anchor.py` output (`soul_final.json`) into session_bootstrap.
//
// Background: AiOT's `IdentityAnchor` accumulates a 256-dim
// `identity_embedding` via EMA of high-quality experience z-vectors,
// plus a 5-dim `trait_vector` [curiosity, caution, creativity, persistence,
// adaptability], a `session_count`, and a `fingerprint` — see
// `decision_aiot_seed_actual_state_20260503` for the discovery context.
//
// We don't write back. Two-way sync requires the EMA + drift-cap logic
// of `identity_anchor.py` to run somewhere; that's Phase β. For now,
// reading is enough — it makes the AiOT carrier identity visible in
// agent-bridge sessions, bridging the 21-month trajectory at the level
// of working state, not just memory descriptions.

/// Return the path to AiOT `soul_final.json` if discoverable.
/// Override via `AGENT_BRIDGE_AIOT_SOUL_PATH`. Default location:
/// `/Data/CascadeProjects/AiOT/consciousness_state/soul_final.json`.
/// Returns `None` if neither path exists.
fn aiot_soul_path() -> Option<PathBuf> {
    if let Ok(p) = std::env::var("AGENT_BRIDGE_AIOT_SOUL_PATH") {
        let pb = PathBuf::from(p);
        if pb.exists() {
            return Some(pb);
        }
    }
    let default =
        PathBuf::from("/Data/CascadeProjects/AiOT/consciousness_state/soul_final.json");
    if default.exists() {
        Some(default)
    } else {
        None
    }
}

const TRAIT_NAMES: [&str; 5] = [
    "curiosity",
    "caution",
    "creativity",
    "persistence",
    "adaptability",
];

/// Build a compact human-readable AiOT Soul summary block for
/// `session_bootstrap` injection. Returns `None` if soul file is missing,
/// unreadable, or malformed — caller falls through silently.
fn format_aiot_soul_block() -> Option<String> {
    let path = aiot_soul_path()?;
    let raw = std::fs::read_to_string(&path).ok()?;
    let v: Value = serde_json::from_str(&raw).ok()?;

    let fingerprint = v.get("fingerprint").and_then(|x| x.as_str()).unwrap_or("?");
    let exported_at = v
        .get("exported_at")
        .and_then(|x| x.as_str())
        .unwrap_or("?");
    let session_count = v.get("session_count").and_then(|x| x.as_u64()).unwrap_or(0);
    let total_experiences = v
        .get("total_experiences")
        .and_then(|x| x.as_u64())
        .unwrap_or(0);
    let source_backend = v
        .get("source_backend")
        .and_then(|x| x.as_str())
        .unwrap_or("?");

    let trait_vector: Vec<f64> = v
        .get("trait_vector")
        .and_then(|x| x.as_array())
        .map(|a| a.iter().filter_map(|y| y.as_f64()).collect())
        .unwrap_or_default();

    let identity_embedding: Vec<f64> = v
        .get("identity_embedding")
        .and_then(|x| x.as_array())
        .map(|a| a.iter().filter_map(|y| y.as_f64()).collect())
        .unwrap_or_default();

    if identity_embedding.is_empty() {
        return None;
    }

    let dim = identity_embedding.len();
    let norm: f64 = identity_embedding.iter().map(|x| x * x).sum::<f64>().sqrt();

    // Top-5 by absolute value — these dimensions carry the most identity signal.
    let mut indexed: Vec<(usize, f64)> = identity_embedding.iter().copied().enumerate().collect();
    indexed.sort_by(|a, b| b.1.abs().partial_cmp(&a.1.abs()).unwrap_or(std::cmp::Ordering::Equal));
    let top5: Vec<String> = indexed
        .iter()
        .take(5)
        .map(|(i, x)| format!("dim_{i}={x:+.3}"))
        .collect();

    let trait_lines: Vec<String> = TRAIT_NAMES
        .iter()
        .enumerate()
        .map(|(i, name)| {
            let v = trait_vector.get(i).copied().unwrap_or(0.5);
            format!("  {name:<13} {v:.3}")
        })
        .collect();

    let block = format!(
        "fingerprint: {fingerprint} | exported: {exported_at} | source: {source_backend}\n\
         session_count: {session_count} | total_experiences: {total_experiences}\n\n\
         Trait vector:\n{}\n\n\
         Identity embedding [{dim}-dim]:\n  norm: {norm:.3}\n  top-5 |dims|: {}",
        trait_lines.join("\n"),
        top5.join(", ")
    );
    Some(block)
}

// ── Agent-Bridge Seed (Phase α′ symmetry) ───────────────────────────────────
//
// Symmetric to the AiOT Soul block but for a different substrate.
//
// `agent-bridge-seed` is a separate sidecar (Python) that tails the
// `~/agent-bridge-memory/memory.jsonl` cross-machine memory feed, encodes
// each MemoryRecord into a 32-d vector via `claude_state_encoder.py`, and
// steps a `seed_neuron::DynamicGrid` (Rust crate borrowed from AiOT) on the
// stream. The grid self-organizes connection topology based on the patterns
// of agent-bridge memory operations themselves — an *implicit* memory layer
// complementing the explicit SQLite store.
//
// The sidecar writes its state to `state/seed_state.json`. We read it
// read-only here; we never write back. The sidecar owns mutation, just like
// AiOT owns `soul_final.json`. The agent's cross-substrate view becomes:
//
//   AiOT Soul          = Python EMA on AiOT carrier trajectory (256-dim)
//   Agent-Bridge Seed  = Rust DynamicGrid on agent-bridge memory stream  (≤30 neurons)
//   AGENT.md           = markdown self-portrait
//
// Together these triangulate identity across three independent substrates
// — the dual-mechanism continuity architecture's full cross-substrate
// surface. See `plan_seed_integration_gaps_20260504` for the broader plan.

/// Resolve path to `agent-bridge-seed/state/seed_state.json` if present.
/// Override via `AGENT_BRIDGE_SEED_STATE_PATH`.
fn agent_bridge_seed_state_path() -> Option<PathBuf> {
    if let Ok(p) = std::env::var("AGENT_BRIDGE_SEED_STATE_PATH") {
        let pb = PathBuf::from(p);
        if pb.exists() {
            return Some(pb);
        }
    }
    let default = PathBuf::from("/Data/CascadeProjects/agent-bridge-seed/state/seed_state.json");
    if default.exists() {
        Some(default)
    } else {
        None
    }
}

/// Format a compact human-readable summary of the seed grid state. Pure
/// JSON-string-in, string-or-None-out — testable without filesystem.
/// Returns `None` if the JSON lacks the minimum fields (`step`/`n_alive`).
fn format_agent_bridge_seed_block_from_json(content: &str) -> Option<String> {
    let v: serde_json::Value = serde_json::from_str(content).ok()?;

    let step = v.get("step").and_then(|x| x.as_i64())?;
    let n_alive = v.get("n_alive").and_then(|x| x.as_i64())?;
    let spawns = v.get("spawn_count").and_then(|x| x.as_i64()).unwrap_or(0);
    let deaths = v.get("death_count").and_then(|x| x.as_i64()).unwrap_or(0);
    let ae = v
        .get("adaptive_entropy_baseline")
        .and_then(|x| x.as_f64())
        .unwrap_or(0.0);
    let depth = v.get("depth_ratio").and_then(|x| x.as_f64()).unwrap_or(0.0);
    let mode = v.get("mode").and_then(|x| x.as_str()).unwrap_or("");
    let processed = v.get("n_records_processed").and_then(|x| x.as_i64());

    let mut top_lines: Vec<String> = Vec::new();
    if let Some(arr) = v.get("neurons").and_then(|x| x.as_array()) {
        let mut entries: Vec<(i64, i64, f64, Option<i64>)> = arr
            .iter()
            .filter_map(|n| {
                let id = n.get("id")?.as_i64()?;
                let age = n.get("age")?.as_i64()?;
                let in_strength = n.get("in_strength")?.as_f64()?;
                let target = n.get("argmax_target").and_then(|t| t.as_i64());
                Some((id, age, in_strength, target))
            })
            .collect();
        // Highest in_strength first.
        entries.sort_by(|a, b| {
            b.2.partial_cmp(&a.2).unwrap_or(std::cmp::Ordering::Equal)
        });
        for (id, age, in_s, target) in entries.into_iter().take(3) {
            match target {
                Some(t) => top_lines.push(format!(
                    "  n{id} (age {age}, in={in_s:.2}) → attends n{t}"
                )),
                None => top_lines.push(format!(
                    "  n{id} (age {age}, in={in_s:.2}) [carrier]"
                )),
            }
        }
    }

    let mut spawn_lines: Vec<String> = Vec::new();
    if let Some(arr) = v.get("spawn_events").and_then(|x| x.as_array()) {
        let total = arr.len();
        // Take the LAST 3 spawn events in chronological order.
        let start = total.saturating_sub(3);
        for s in &arr[start..] {
            let Some(at) = s.get("at_record").and_then(|x| x.as_i64()) else {
                continue;
            };
            let kind = s.get("kind").and_then(|x| x.as_str()).unwrap_or("?");
            let n_after = s
                .get("n_alive_after")
                .and_then(|x| x.as_i64())
                .unwrap_or(0);
            let key = s.get("key").and_then(|x| x.as_str()).unwrap_or("?");
            let key_short: String = if key.chars().count() > 50 {
                let s: String = key.chars().take(50).collect();
                format!("{s}…")
            } else {
                key.to_string()
            };
            spawn_lines.push(format!(
                "  @ rec {at} ({kind}) → n={n_after}, key={key_short}"
            ));
        }
    }

    let mut block = String::new();
    if !mode.is_empty() {
        if let Some(p) = processed {
            block.push_str(&format!("mode={mode} | records_processed={p}\n"));
        } else {
            block.push_str(&format!("mode={mode}\n"));
        }
    }
    block.push_str(&format!(
        "step={step} | n_alive={n_alive} | spawns={spawns} | deaths={deaths}\n\
         adaptive_entropy_baseline: {ae:.3} | depth_ratio: {depth:.2}"
    ));
    if !top_lines.is_empty() {
        block.push_str("\n\nTop-3 attended neurons (by in_strength):\n");
        block.push_str(&top_lines.join("\n"));
    }
    if !spawn_lines.is_empty() {
        block.push_str("\n\nRecent spawn events:\n");
        block.push_str(&spawn_lines.join("\n"));
    }
    Some(block)
}

/// Build the bootstrap-injection block. Returns None when sidecar state
/// isn't available or is malformed — block is hidden in that case.
fn format_agent_bridge_seed_block() -> Option<String> {
    let path = agent_bridge_seed_state_path()?;
    let content = std::fs::read_to_string(&path).ok()?;
    format_agent_bridge_seed_block_from_json(&content)
}

// ── Agent-Bridge Perception Filter (Path B, 2026-05-05) ─────────────────────
//
// Parallel to the 32-d Seed block above. The Perception Filter sidecar
// (`perception_filter_sidecar.py tail`) embeds each MemoryRecord via
// MiniLM-L6-v2 (384-d), filters by Mahalanobis surprisal vs the streaming
// prior (drop high-surprisal outliers / "高熵杂讯", keep "低熵效信息"),
// and steps a separate DynamicGrid (dim=384, max_n=50) over the kept stream.
//
// Both sidecars run side-by-side: the 32-d encoder is a control (validated
// L2+L3 emergence on AiOT seed_demo); the 384-d filter is the treatment
// (tested for "new memory finds home", cos>0.5 for related neighbors).
// We surface both at bootstrap so future-Claude can compare topology.
//
// Schema differs from the 32-d version: grid fields are nested under
// `grid:`, plus filter-level metadata (n_kept, surprisal_stats,
// high/low_surprisal_top10).

/// Resolve path to `agent-bridge-seed/state_pf/perception_filter_state.json` if present.
/// Override via `AGENT_BRIDGE_PERCEPTION_FILTER_STATE_PATH`.
///
/// Search order: env var → `~/Projects/agent-bridge-seed/...` (macOS Projects layout)
/// → `~/agent-bridge-seed/...` (Linux home layout) → `/Data/CascadeProjects/agent-bridge-seed/...`
/// (legacy source-box default). First existing path wins.
///
/// Within each base, the canonical `perception_filter_state.json` is tried
/// first, then `perception_filter_state_low.json` as a fallback.
/// perception_filter_sidecar.py backfill auto-renames its output to
/// `perception_filter_state_<filter_direction>.json` even when `--output`
/// points at the canonical path, so without this fallback path-C rerank
/// silently no-ops after every fresh backfill until the user manually
/// `cp _low.json` to the canonical name. See
/// `lesson_path_c_sidecar_bridge_filename_mismatch_20260507`.
fn agent_bridge_perception_filter_state_path() -> Option<PathBuf> {
    if let Ok(p) = std::env::var("AGENT_BRIDGE_PERCEPTION_FILTER_STATE_PATH") {
        let pb = PathBuf::from(p);
        if pb.exists() {
            return Some(pb);
        }
    }
    let mut bases: Vec<PathBuf> = Vec::new();
    if let Ok(home) = std::env::var("HOME") {
        let h = PathBuf::from(home);
        bases.push(h.join("Projects/agent-bridge-seed/state_pf"));
        bases.push(h.join("agent-bridge-seed/state_pf"));
    }
    bases.push(PathBuf::from(
        "/Data/CascadeProjects/agent-bridge-seed/state_pf",
    ));
    bases
        .into_iter()
        .flat_map(|d| {
            [
                d.join("perception_filter_state.json"),
                d.join("perception_filter_state_low.json"),
            ]
        })
        .find(|p| p.exists())
}

/// Format a compact summary of the perception-filter state. Pure JSON-in,
/// string-or-None-out — testable without filesystem. Returns `None` if the
/// JSON lacks the minimum fields (`n_total` and `grid.step`).
fn format_perception_filter_block_from_json(content: &str) -> Option<String> {
    let v: serde_json::Value = serde_json::from_str(content).ok()?;

    let n_total = v.get("n_total").and_then(|x| x.as_i64())?;
    let grid = v.get("grid")?;
    let step = grid.get("step").and_then(|x| x.as_i64())?;
    let n_alive = grid.get("n_alive").and_then(|x| x.as_i64()).unwrap_or(0);
    let spawns = grid
        .get("spawn_count")
        .and_then(|x| x.as_i64())
        .unwrap_or(0);
    let deaths = grid
        .get("death_count")
        .and_then(|x| x.as_i64())
        .unwrap_or(0);
    let ae = grid
        .get("adaptive_entropy_baseline")
        .and_then(|x| x.as_f64())
        .unwrap_or(0.0);
    let depth = grid
        .get("depth_ratio")
        .and_then(|x| x.as_f64())
        .unwrap_or(0.0);

    let n_kept = v.get("n_kept").and_then(|x| x.as_i64()).unwrap_or(0);
    let keep_ratio = v
        .get("keep_ratio")
        .and_then(|x| x.as_f64())
        .unwrap_or(0.0);
    let direction = v
        .get("filter_direction")
        .and_then(|x| x.as_str())
        .unwrap_or("low");
    let mode = v.get("mode").and_then(|x| x.as_str()).unwrap_or("");
    let model = v.get("model").and_then(|x| x.as_str()).unwrap_or("?");
    let dim = v.get("embed_dim").and_then(|x| x.as_i64()).unwrap_or(0);
    // Friendly model label (drop "sentence-transformers/" prefix for compactness).
    let model_short = model.rsplit('/').next().unwrap_or(model);

    // Surprisal distribution (one line).
    let mut surprisal_line = String::new();
    if let Some(stats) = v.get("surprisal_stats") {
        let median = stats.get("median").and_then(|x| x.as_f64()).unwrap_or(0.0);
        let p25 = stats.get("p25").and_then(|x| x.as_f64()).unwrap_or(0.0);
        let p75 = stats.get("p75").and_then(|x| x.as_f64()).unwrap_or(0.0);
        let max = stats.get("max").and_then(|x| x.as_f64()).unwrap_or(0.0);
        surprisal_line = format!(
            "surprisal: median={median:.0} | p25={p25:.0} | p75={p75:.0} | max={max:.0}"
        );
    }

    // Top-3 attended neurons (same logic as Seed block, on grid.neurons).
    let mut top_lines: Vec<String> = Vec::new();
    if let Some(arr) = grid.get("neurons").and_then(|x| x.as_array()) {
        let mut entries: Vec<(i64, i64, f64, Option<i64>)> = arr
            .iter()
            .filter_map(|n| {
                let id = n.get("id")?.as_i64()?;
                let age = n.get("age")?.as_i64()?;
                let in_strength = n.get("in_strength")?.as_f64()?;
                let target = n.get("argmax_target").and_then(|t| t.as_i64());
                Some((id, age, in_strength, target))
            })
            .collect();
        entries.sort_by(|a, b| {
            b.2.partial_cmp(&a.2).unwrap_or(std::cmp::Ordering::Equal)
        });
        for (id, age, in_s, target) in entries.into_iter().take(3) {
            match target {
                Some(t) => top_lines.push(format!(
                    "  n{id} (age {age}, in={in_s:.2}) → attends n{t}"
                )),
                None => top_lines.push(format!(
                    "  n{id} (age {age}, in={in_s:.2}) [carrier]"
                )),
            }
        }
    }

    // High-surprisal markers — potential novelty / anomaly. Useful for
    // future-Claude to flag "what looks anomalous in the current corpus".
    // Always shown regardless of filter direction (signal works both ways).
    let mut novelty_lines: Vec<String> = Vec::new();
    if let Some(arr) = v.get("high_surprisal_top10").and_then(|x| x.as_array()) {
        for entry in arr.iter().take(3) {
            let s = entry.get("surprisal").and_then(|x| x.as_f64()).unwrap_or(0.0);
            let kind = entry.get("kind").and_then(|x| x.as_str()).unwrap_or("?");
            let key = entry.get("key").and_then(|x| x.as_str()).unwrap_or("?");
            let key_short: String = if key.chars().count() > 50 {
                let truncated: String = key.chars().take(50).collect();
                format!("{truncated}…")
            } else {
                key.to_string()
            };
            novelty_lines.push(format!(
                "  s={s:.0} ({kind:>10}) {key_short}"
            ));
        }
    }

    let mut block = String::new();
    let mode_tag = if mode.is_empty() {
        String::new()
    } else {
        format!(" | mode={mode}")
    };
    block.push_str(&format!(
        "filter: {direction} (keep {pct:.0}%) | n_total={n_total} → kept={n_kept} | model={model_short} ({dim}d){mode_tag}\n\
         grid: step={step} | n_alive={n_alive} | spawns={spawns} | deaths={deaths} | ae={ae:.3} | depth={depth:.2}",
        pct = keep_ratio * 100.0
    ));
    if !surprisal_line.is_empty() {
        block.push('\n');
        block.push_str(&surprisal_line);
    }
    if !top_lines.is_empty() {
        block.push_str("\n\nTop-3 attended neurons (by in_strength):\n");
        block.push_str(&top_lines.join("\n"));
    }
    if !novelty_lines.is_empty() {
        block.push_str("\n\nHigh-surprisal markers (potential novelty/anomaly, top 3):\n");
        block.push_str(&novelty_lines.join("\n"));
    }
    Some(block)
}

/// Build the perception-filter bootstrap block. Returns None when sidecar
/// state isn't available or is malformed.
fn format_perception_filter_block() -> Option<String> {
    let path = agent_bridge_perception_filter_state_path()?;
    let content = std::fs::read_to_string(&path).ok()?;
    format_perception_filter_block_from_json(&content)
}

// ── Path C actuator: seed-grid-driven memory_search rerank ─────────────────
//
// Path B sidecar (perception_filter_sidecar.py) writes hub_clusters into
// state_pf/perception_filter_state.json — a list of (neuron_id, basin_size,
// near_keys) entries identifying which existing record keys cluster around
// the most populous hubs in the perception grid.
//
// Here we read those near_keys, union them into a HashSet, and use it as a
// boost set for memory_search results: any result key that appears in the
// set has its score multiplied by SEED_BOOST_FACTOR. This is the "active
// influence" half of Path C — the seed grid topology actively shifts which
// records get surfaced, not just an observation block in bootstrap.
//
// Disable at runtime by setting AGENT_BRIDGE_SEED_BOOST_DISABLE=1.
//
// Cache: HashSet is rebuilt only when the state JSON's mtime changes —
// minimal overhead per memory_search call (a stat() + a hashset clone).

const SEED_BOOST_FACTOR: f64 = 1.20;

struct SeedBoostCache {
    path_mtime: Option<std::time::SystemTime>,
    boost_keys: std::collections::HashSet<String>,
}

static SEED_BOOST_CACHE: std::sync::LazyLock<std::sync::Mutex<SeedBoostCache>> =
    std::sync::LazyLock::new(|| {
        std::sync::Mutex::new(SeedBoostCache {
            path_mtime: None,
            boost_keys: std::collections::HashSet::new(),
        })
    });

fn seed_boost_keys() -> std::collections::HashSet<String> {
    if std::env::var("AGENT_BRIDGE_SEED_BOOST_DISABLE")
        .map(|v| v == "1" || v.eq_ignore_ascii_case("true"))
        .unwrap_or(false)
    {
        return std::collections::HashSet::new();
    }
    let path = match agent_bridge_perception_filter_state_path() {
        Some(p) => p,
        None => return std::collections::HashSet::new(),
    };
    let mtime = match std::fs::metadata(&path)
        .ok()
        .and_then(|m| m.modified().ok())
    {
        Some(m) => m,
        None => return std::collections::HashSet::new(),
    };
    let mut cache = match SEED_BOOST_CACHE.lock() {
        Ok(g) => g,
        Err(p) => p.into_inner(),
    };
    if cache.path_mtime == Some(mtime) {
        return cache.boost_keys.clone();
    }
    let content = match std::fs::read_to_string(&path) {
        Ok(c) => c,
        Err(_) => {
            cache.path_mtime = Some(mtime);
            cache.boost_keys.clear();
            return cache.boost_keys.clone();
        }
    };
    let mut keys = std::collections::HashSet::new();
    if let Ok(v) = serde_json::from_str::<serde_json::Value>(&content) {
        if let Some(arr) = v.get("hub_clusters").and_then(|x| x.as_array()) {
            for hc in arr {
                if let Some(near) = hc.get("near_keys").and_then(|x| x.as_array()) {
                    for k in near {
                        if let Some(s) = k.as_str() {
                            keys.insert(s.to_string());
                        }
                    }
                }
            }
        }
    }
    cache.path_mtime = Some(mtime);
    cache.boost_keys = keys.clone();
    keys
}

/// Re-rank memory_search hits by applying SEED_BOOST_FACTOR to scores whose
/// record.key appears in the current seed-grid hub_clusters near_keys union.
/// Idempotent and fail-soft — empty boost set ⇒ pass-through.
fn apply_seed_boost(mut hits: Vec<MemorySearchHit>) -> Vec<MemorySearchHit> {
    let boost = seed_boost_keys();
    if boost.is_empty() {
        return hits;
    }
    for h in hits.iter_mut() {
        if boost.contains(&h.record.key) {
            h.score *= SEED_BOOST_FACTOR;
        }
    }
    hits.sort_by(|a, b| {
        b.score
            .partial_cmp(&a.score)
            .unwrap_or(std::cmp::Ordering::Equal)
    });
    hits
}

// ── Decision review trigger ─────────────────────────────────────────────────
//
// Closes the dual-mechanism continuity loop. AGENT.md (attractor) + drift_cap
// (guard) + letters (anchor) keep identity stable across sessions, but they
// don't surface STORED decisions for re-examination. Without that, decisions
// accumulate as static records — never revisited until something breaks.
//
// Convention: decisions tagged `review:Nd` (e.g. `review:30d`, `review:12w`)
// re-surface in `session_bootstrap` when `now - updated_at >= N days`. Agent
// re-saves (resets clock) or links `supersedes` (closes the review).
//
// Mechanism is read-only: no auto-mutation. The review block is a dashboard,
// not an action queue. Conservative-mutations principle from AGENT.md.

/// Parse a `review:Nd` / `review:Nw` tag from a tags list. Returns the
/// review interval in days, or `None` if no review tag is present.
/// First match wins; later tags in the list are ignored.
fn parse_review_interval_days(tags: &[String]) -> Option<i64> {
    for tag in tags {
        let Some(rest) = tag.strip_prefix("review:") else {
            continue;
        };
        if let Some(n_str) = rest.strip_suffix('d') {
            if let Ok(n) = n_str.parse::<i64>() {
                if n > 0 {
                    return Some(n);
                }
            }
        } else if let Some(n_str) = rest.strip_suffix('w') {
            if let Ok(n) = n_str.parse::<i64>() {
                if n > 0 {
                    return Some(n * 7);
                }
            }
        }
    }
    None
}

/// Format a "Decisions Due for Review" block from a pool of decision records.
/// Returns `None` if no record is due (no block will be injected).
/// Sort order: most overdue first (largest `now - updated_at - interval`).
fn format_due_review_block(rows: &[MemoryRecord], now_ts: i64) -> Option<String> {
    let mut due: Vec<(&MemoryRecord, i64, i64)> = Vec::new();
    for r in rows {
        let Some(interval_days) = parse_review_interval_days(&r.tags) else {
            continue;
        };
        let age_days = (now_ts - r.updated_at) / 86400;
        if age_days >= interval_days {
            due.push((r, interval_days, age_days - interval_days));
        }
    }
    if due.is_empty() {
        return None;
    }
    due.sort_by(|a, b| b.2.cmp(&a.2));
    let lines: Vec<String> = due
        .iter()
        .map(|(r, interval, overdue)| {
            let snippet = r
                .content
                .lines()
                .find(|l| !l.trim().is_empty())
                .unwrap_or("")
                .trim();
            let snippet_short: String = if snippet.chars().count() > 100 {
                let s: String = snippet.chars().take(100).collect();
                format!("{s}…")
            } else {
                snippet.to_string()
            };
            format!(
                "- {} (imp {:.2}, review:{}d) — overdue {}d\n  > {}",
                r.key, r.importance, interval, overdue, snippet_short
            )
        })
        .collect();
    Some(lines.join("\n"))
}

fn parse_severity(s: &str) -> Option<NotifySeverity> {
    Some(match s {
        "info" => NotifySeverity::Info,
        "success" => NotifySeverity::Success,
        "warning" => NotifySeverity::Warning,
        "error" => NotifySeverity::Error,
        "attention" => NotifySeverity::Attention,
        _ => return None,
    })
}

/// Process escape sequences in `terminal_send_keys` input so callers can write
/// `\n`, `\r`, `\t`, `\x1b` as literal text and have them arrive as real bytes.
fn unescape_keys(s: &str) -> String {
    let mut out = String::with_capacity(s.len());
    let mut chars = s.chars().peekable();
    while let Some(ch) = chars.next() {
        if ch != '\\' {
            out.push(ch);
            continue;
        }
        match chars.next() {
            Some('n') => out.push('\n'),
            Some('r') => out.push('\r'),
            Some('t') => out.push('\t'),
            Some('\\') => out.push('\\'),
            // \x1b → ESC, \x<HH> → single byte
            Some('x') => {
                let h1 = chars.next();
                let h2 = chars.next();
                if let (Some(a), Some(b)) = (h1, h2) {
                    if let Ok(byte) = u8::from_str_radix(&format!("{a}{b}"), 16) {
                        out.push(byte as char);
                        continue;
                    }
                    // not valid hex — emit literally
                    out.push('\\');
                    out.push('x');
                    if let Some(a) = h1 {
                        out.push(a);
                    }
                    if let Some(b) = h2 {
                        out.push(b);
                    }
                }
            }
            Some(other) => {
                out.push('\\');
                out.push(other);
            }
            None => out.push('\\'),
        }
    }
    out
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn drift_ratio_first_write_is_zero() {
        // Empty old → first write, no constraint.
        assert_eq!(agent_profile_diff_ratio("", "## Identity\n\nI am Claude."), 0.0);
        assert_eq!(agent_profile_diff_ratio("   \n   \n", "anything"), 0.0);
    }

    #[test]
    fn drift_ratio_identical_is_zero() {
        let txt = "## Values\n\n- honesty\n- conservative mutations";
        assert_eq!(agent_profile_diff_ratio(txt, txt), 0.0);
    }

    #[test]
    fn drift_ratio_disjoint_is_one() {
        let old = "line one\nline two\nline three";
        let new = "alpha\nbeta\ngamma";
        assert!((agent_profile_diff_ratio(old, new) - 1.0).abs() < 1e-6);
    }

    #[test]
    fn drift_ratio_partial_change_is_bounded() {
        // 4 old lines, change 1 → ratio ~ 0.4 (1 removed + 1 added) / (4 + 1 union) = 2/5
        let old = "a\nb\nc\nd";
        let new = "a\nb\nc\ne";
        let r = agent_profile_diff_ratio(old, new);
        assert!(r > 0.3 && r < 0.5, "expected ~0.4, got {r}");
    }

    #[test]
    fn drift_ratio_pure_addition_grows_slowly() {
        // 3 old lines, add 1 → 1 new uniqueness, intersection=3, union=4 → 0.25
        let old = "a\nb\nc";
        let new = "a\nb\nc\nd";
        let r = agent_profile_diff_ratio(old, new);
        assert!((r - 0.25).abs() < 1e-6, "expected 0.25, got {r}");
    }

    #[test]
    fn drift_ratio_below_cap_passes() {
        // Add a Growth-marker style entry to a substantial profile.
        let old = (1..=20)
            .map(|i| format!("line {i}"))
            .collect::<Vec<_>>()
            .join("\n");
        let new = format!("{old}\nnew growth marker");
        let r = agent_profile_diff_ratio(&old, &new);
        assert!(r < AGENT_PROFILE_DRIFT_CAP, "expected < cap, got {r}");
    }

    #[test]
    fn drift_ratio_total_rewrite_blocked_by_cap() {
        let old = (1..=10)
            .map(|i| format!("old line {i}"))
            .collect::<Vec<_>>()
            .join("\n");
        let new = (1..=10)
            .map(|i| format!("new line {i}"))
            .collect::<Vec<_>>()
            .join("\n");
        let r = agent_profile_diff_ratio(&old, &new);
        assert!(
            r > AGENT_PROFILE_DRIFT_CAP,
            "total rewrite must exceed cap, got {r}"
        );
    }

    // ── Decision review trigger tests ───────────────────────────────────

    fn mk_decision(key: &str, importance: f64, tags: &[&str], updated_at: i64) -> MemoryRecord {
        MemoryRecord {
            key: key.into(),
            kind: "decision".into(),
            content: format!("First line for {key}.\nMore detail here."),
            tags: tags.iter().map(|s| s.to_string()).collect(),
            related_keys: Vec::new(),
            scope: None,
            created_at: updated_at,
            updated_at,
            last_accessed_at: updated_at,
            access_count: 0,
            importance,
            status: "active".into(),
            trigger_pattern: None,
        }
    }

    // ── Perception Filter block tests ───────────────────────────────────

    #[test]
    fn pf_block_returns_none_on_malformed_or_missing() {
        assert!(format_perception_filter_block_from_json("").is_none());
        assert!(format_perception_filter_block_from_json("not json").is_none());
        assert!(format_perception_filter_block_from_json("{}").is_none());
        // Missing nested grid.step
        assert!(
            format_perception_filter_block_from_json(r#"{"n_total":10,"grid":{}}"#).is_none()
        );
        // Missing n_total
        assert!(
            format_perception_filter_block_from_json(r#"{"grid":{"step":1}}"#).is_none()
        );
    }

    #[test]
    fn pf_block_minimal_state_renders() {
        let json = r#"{
            "n_total": 350,
            "n_kept": 175,
            "keep_ratio": 0.5,
            "filter_direction": "low",
            "mode": "tail",
            "model": "sentence-transformers/all-MiniLM-L6-v2",
            "embed_dim": 384,
            "grid": {
                "step": 175, "n_alive": 22, "spawn_count": 18, "death_count": 0,
                "adaptive_entropy_baseline": 0.857, "depth_ratio": 0.30
            }
        }"#;
        let block = format_perception_filter_block_from_json(json).unwrap();
        assert!(block.contains("filter: low (keep 50%)"));
        assert!(block.contains("n_total=350"));
        assert!(block.contains("kept=175"));
        assert!(block.contains("model=all-MiniLM-L6-v2 (384d)"));
        assert!(block.contains("mode=tail"));
        assert!(block.contains("step=175"));
        assert!(block.contains("n_alive=22"));
        assert!(block.contains("ae=0.857"));
        assert!(block.contains("depth=0.30"));
        // No optional sections.
        assert!(!block.contains("Top-3"));
        assert!(!block.contains("High-surprisal markers"));
        assert!(!block.contains("surprisal: median"));
    }

    #[test]
    fn pf_block_renders_surprisal_stats_and_markers() {
        let json = r#"{
            "n_total": 350,
            "n_kept": 175,
            "keep_ratio": 0.5,
            "filter_direction": "low",
            "mode": "tail",
            "model": "MiniLM",
            "embed_dim": 384,
            "surprisal_stats": {
                "min": 280.0, "p25": 371.0, "median": 383.4,
                "p75": 400.5, "max": 621.1, "threshold": 383.4
            },
            "high_surprisal_top10": [
                {"surprisal": 621.1, "key": "test_key_smoke", "kind": "lesson",   "importance": 0.5},
                {"surprisal": 518.0, "key": "anomaly_one",   "kind": "decision", "importance": 0.6},
                {"surprisal": 485.2, "key": "anomaly_two",   "kind": "context",  "importance": 0.7},
                {"surprisal": 400.0, "key": "below_top3",    "kind": "lesson",   "importance": 0.5}
            ],
            "grid": {
                "step": 175, "n_alive": 5, "spawn_count": 3, "death_count": 0,
                "adaptive_entropy_baseline": 0.86, "depth_ratio": 0.4
            }
        }"#;
        let block = format_perception_filter_block_from_json(json).unwrap();
        assert!(block.contains("surprisal: median=383"));
        assert!(block.contains("p25=371"));
        assert!(block.contains("max=621"));
        assert!(block.contains("High-surprisal markers"));
        assert!(block.contains("test_key_smoke"));
        assert!(block.contains("anomaly_one"));
        assert!(block.contains("anomaly_two"));
        assert!(!block.contains("below_top3"), "only top-3 surfaced");
    }

    #[test]
    fn pf_block_top3_neurons_sorted_by_in_strength() {
        let json = r#"{
            "n_total": 100, "n_kept": 50, "keep_ratio": 0.5,
            "filter_direction": "low", "mode": "tail",
            "model": "MiniLM", "embed_dim": 384,
            "grid": {
                "step": 50, "n_alive": 5, "spawn_count": 1, "death_count": 0,
                "adaptive_entropy_baseline": 0.85, "depth_ratio": 0.6,
                "neurons": [
                    {"id": 0, "age": 50, "in_strength": 0.5, "argmax_target": null},
                    {"id": 1, "age": 50, "in_strength": 2.7, "argmax_target": 3},
                    {"id": 2, "age": 40, "in_strength": 1.2, "argmax_target": 1},
                    {"id": 3, "age": 30, "in_strength": 0.8, "argmax_target": 2},
                    {"id": 4, "age": 20, "in_strength": 1.9, "argmax_target": 1}
                ]
            }
        }"#;
        let block = format_perception_filter_block_from_json(json).unwrap();
        let p1 = block.find("n1 ").unwrap();
        let p4 = block.find("n4 ").unwrap();
        let p2 = block.find("n2 ").unwrap();
        assert!(p1 < p4 && p4 < p2, "top-3 in in_strength order: 1 > 4 > 2");
        assert!(!block.contains("n0 "));
        assert!(!block.contains("n3 "));
    }

    #[test]
    fn pf_block_truncates_long_surprisal_keys() {
        let long_key = "k_".to_string() + &"x".repeat(120);
        let json = format!(
            r#"{{
                "n_total": 1, "n_kept": 1, "keep_ratio": 1.0,
                "filter_direction": "low", "mode": "tail",
                "model": "MiniLM", "embed_dim": 384,
                "high_surprisal_top10": [
                    {{"surprisal": 500.0, "key": "{long_key}", "kind": "x", "importance": 0.5}}
                ],
                "grid": {{
                    "step": 1, "n_alive": 1, "spawn_count": 0, "death_count": 0,
                    "adaptive_entropy_baseline": 0.5, "depth_ratio": 0.0
                }}
            }}"#
        );
        let block = format_perception_filter_block_from_json(&json).unwrap();
        assert!(block.contains("…"), "long key must be truncated");
    }

    // ── Path C actuator: seed boost rerank ─────────────────────────────────
    //
    // The three `seed_boost_*` tests below mutate process-global env vars
    // (`AGENT_BRIDGE_SEED_BOOST_DISABLE`, `AGENT_BRIDGE_PERCEPTION_FILTER_STATE_PATH`)
    // and depend on the global `SEED_BOOST_CACHE`. Cargo runs tests in
    // parallel, so they MUST serialize via `pathc_test_setup` — without it,
    // one test's env / cache leaks into another and assertions flap. The
    // setup helper grabs a process-wide lock AND resets the cache so each
    // test starts from a known state.

    fn pathc_test_setup() -> std::sync::MutexGuard<'static, ()> {
        static LOCK: std::sync::Mutex<()> = std::sync::Mutex::new(());
        let g = LOCK.lock().unwrap_or_else(|p| p.into_inner());
        let mut c = SEED_BOOST_CACHE.lock().unwrap_or_else(|p| p.into_inner());
        c.path_mtime = None;
        c.boost_keys.clear();
        g
    }

    fn make_hit(key: &str, score: f64) -> MemorySearchHit {
        MemorySearchHit {
            record: MemoryRecord {
                key: key.to_string(),
                kind: "lesson".into(),
                content: String::new(),
                tags: Vec::new(),
                related_keys: Vec::new(),
                created_at: 0,
                updated_at: 0,
                last_accessed_at: 0,
                access_count: 0,
                scope: None,
                importance: 0.5,
                status: "active".into(),
                trigger_pattern: None,
            },
            score,
        }
    }

    /// With AGENT_BRIDGE_SEED_BOOST_DISABLE=1 set, the rerank is a pass-through
    /// even when the state file exists. Verifies the kill-switch.
    #[test]
    fn seed_boost_disabled_via_env_is_passthrough() {
        let _guard = pathc_test_setup();
        let prev = std::env::var("AGENT_BRIDGE_SEED_BOOST_DISABLE").ok();
        std::env::set_var("AGENT_BRIDGE_SEED_BOOST_DISABLE", "1");

        let hits_in = vec![
            make_hit("a", 1.0),
            make_hit("b", 2.0),
            make_hit("c", 0.5),
        ];
        let hits_out = apply_seed_boost(hits_in.clone());

        // Order and scores unchanged because boost set is forced empty.
        assert_eq!(hits_out.len(), 3);
        for (got, want) in hits_out.iter().zip(hits_in.iter()) {
            assert_eq!(got.record.key, want.record.key);
            assert_eq!(got.score, want.score);
        }

        match prev {
            Some(v) => std::env::set_var("AGENT_BRIDGE_SEED_BOOST_DISABLE", v),
            None => std::env::remove_var("AGENT_BRIDGE_SEED_BOOST_DISABLE"),
        }
    }

    /// When the state file exists but has no hub_clusters (older schema /
    /// pre-Stage-A snapshot), seed_boost_keys returns an empty set and
    /// apply_seed_boost is a strict pass-through (no reorder).
    #[test]
    fn seed_boost_state_without_hub_clusters_is_passthrough() {
        let _guard = pathc_test_setup();
        let prev_path = std::env::var("AGENT_BRIDGE_PERCEPTION_FILTER_STATE_PATH").ok();
        let prev_disable = std::env::var("AGENT_BRIDGE_SEED_BOOST_DISABLE").ok();
        std::env::remove_var("AGENT_BRIDGE_SEED_BOOST_DISABLE");

        let dir = std::env::temp_dir().join(format!(
            "ab-pathc-empty-{}-{}",
            std::process::id(),
            std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .map(|d| d.as_nanos())
                .unwrap_or(0)
        ));
        std::fs::create_dir_all(&dir).unwrap();
        let state_path = dir.join("perception_filter_state.json");
        // No hub_clusters key — older schema / fresh tail before Stage A landed.
        std::fs::write(&state_path, r#"{"n_total":100,"grid":{"step":100}}"#).unwrap();
        std::env::set_var("AGENT_BRIDGE_PERCEPTION_FILTER_STATE_PATH", &state_path);

        // Pre-sorted desc by score so pass-through preserves order trivially.
        let hits = vec![make_hit("y", 2.0), make_hit("x", 1.0)];
        let out = apply_seed_boost(hits.clone());
        assert_eq!(out.len(), 2);
        for (got, want) in out.iter().zip(hits.iter()) {
            assert_eq!(got.record.key, want.record.key);
            assert_eq!(got.score, want.score);
        }

        std::fs::remove_file(&state_path).ok();
        std::fs::remove_dir(&dir).ok();
        match prev_path {
            Some(v) => std::env::set_var("AGENT_BRIDGE_PERCEPTION_FILTER_STATE_PATH", v),
            None => std::env::remove_var("AGENT_BRIDGE_PERCEPTION_FILTER_STATE_PATH"),
        }
        match prev_disable {
            Some(v) => std::env::set_var("AGENT_BRIDGE_SEED_BOOST_DISABLE", v),
            None => std::env::remove_var("AGENT_BRIDGE_SEED_BOOST_DISABLE"),
        }
    }

    /// End-to-end: pointing PERCEPTION_FILTER_STATE_PATH at a file containing
    /// hub_clusters with specific near_keys boosts those keys' scores by the
    /// expected factor and re-sorts.
    #[test]
    fn seed_boost_applies_factor_and_resorts() {
        let _guard = pathc_test_setup();
        let prev_path = std::env::var("AGENT_BRIDGE_PERCEPTION_FILTER_STATE_PATH").ok();
        let prev_disable = std::env::var("AGENT_BRIDGE_SEED_BOOST_DISABLE").ok();
        std::env::remove_var("AGENT_BRIDGE_SEED_BOOST_DISABLE");

        let dir = std::env::temp_dir().join(format!("ab-pathc-test-{}", std::process::id()));
        std::fs::create_dir_all(&dir).unwrap();
        let state_path = dir.join("perception_filter_state.json");
        std::fs::write(
            &state_path,
            r#"{"hub_clusters":[{"neuron_id":2,"in_strength":4.0,"basin_size":3,"follower_count":1,"near_keys":["boosted_a","boosted_b"]},{"neuron_id":3,"in_strength":1.0,"basin_size":1,"follower_count":0,"near_keys":["boosted_c"]}]}"#,
        )
        .unwrap();
        std::env::set_var(
            "AGENT_BRIDGE_PERCEPTION_FILTER_STATE_PATH",
            &state_path,
        );

        let hits = vec![
            make_hit("unboosted_high", 2.0),
            make_hit("boosted_a", 1.5),
            make_hit("boosted_b", 1.8),
            make_hit("unboosted_mid", 1.6),
        ];
        let out = apply_seed_boost(hits);

        assert_eq!(out.len(), 4);
        // boosted_b: 1.8 * 1.20 = 2.16 — should now be top.
        // unboosted_high: 2.0 — second.
        // boosted_a: 1.5 * 1.20 = 1.80 — third.
        // unboosted_mid: 1.6 — fourth (1.6 < 1.8).
        assert_eq!(out[0].record.key, "boosted_b");
        assert!((out[0].score - 2.16).abs() < 1e-9, "got {}", out[0].score);
        assert_eq!(out[1].record.key, "unboosted_high");
        assert_eq!(out[2].record.key, "boosted_a");
        assert!((out[2].score - 1.80).abs() < 1e-9, "got {}", out[2].score);
        assert_eq!(out[3].record.key, "unboosted_mid");

        std::fs::remove_file(&state_path).ok();
        match prev_path {
            Some(v) => std::env::set_var("AGENT_BRIDGE_PERCEPTION_FILTER_STATE_PATH", v),
            None => std::env::remove_var("AGENT_BRIDGE_PERCEPTION_FILTER_STATE_PATH"),
        }
        match prev_disable {
            Some(v) => std::env::set_var("AGENT_BRIDGE_SEED_BOOST_DISABLE", v),
            None => std::env::remove_var("AGENT_BRIDGE_SEED_BOOST_DISABLE"),
        }
    }

    /// `perception_filter_sidecar.py backfill` writes `_low.json` by default;
    /// the resolver must fall back to that when the canonical filename is
    /// missing, and prefer the canonical filename when both exist. Mutates
    /// HOME — serialised under `pathc_test_setup`.
    #[test]
    fn perception_state_path_falls_back_to_low_suffix() {
        let _guard = pathc_test_setup();
        let prev_home = std::env::var("HOME").ok();
        let prev_pf = std::env::var("AGENT_BRIDGE_PERCEPTION_FILTER_STATE_PATH").ok();
        std::env::remove_var("AGENT_BRIDGE_PERCEPTION_FILTER_STATE_PATH");

        let tmp = std::env::temp_dir().join(format!(
            "ab-pathc-fb-{}-{}",
            std::process::id(),
            std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .map(|d| d.as_nanos())
                .unwrap_or(0)
        ));
        let state_dir = tmp.join("Projects/agent-bridge-seed/state_pf");
        std::fs::create_dir_all(&state_dir).unwrap();
        let low_path = state_dir.join("perception_filter_state_low.json");
        let canon_path = state_dir.join("perception_filter_state.json");

        std::fs::write(&low_path, r#"{"hub_clusters":[]}"#).unwrap();
        std::env::set_var("HOME", &tmp);

        // Only `_low.json` present → fallback wins.
        let resolved = agent_bridge_perception_filter_state_path();
        assert_eq!(
            resolved.as_deref(),
            Some(low_path.as_path()),
            "fallback to _low.json failed; got {:?}",
            resolved
        );

        // Both present → canonical wins (preference order within a base).
        std::fs::write(&canon_path, r#"{}"#).unwrap();
        let resolved2 = agent_bridge_perception_filter_state_path();
        assert_eq!(
            resolved2.as_deref(),
            Some(canon_path.as_path()),
            "canonical did not win over _low.json; got {:?}",
            resolved2
        );

        std::fs::remove_dir_all(&tmp).ok();
        match prev_home {
            Some(v) => std::env::set_var("HOME", v),
            None => std::env::remove_var("HOME"),
        }
        match prev_pf {
            Some(v) => std::env::set_var("AGENT_BRIDGE_PERCEPTION_FILTER_STATE_PATH", v),
            None => std::env::remove_var("AGENT_BRIDGE_PERCEPTION_FILTER_STATE_PATH"),
        }
    }

    #[test]
    fn parse_review_days_basic() {
        assert_eq!(
            parse_review_interval_days(&["review:30d".into()]),
            Some(30)
        );
        assert_eq!(parse_review_interval_days(&["review:1w".into()]), Some(7));
        assert_eq!(
            parse_review_interval_days(&["review:12w".into()]),
            Some(84)
        );
        assert_eq!(
            parse_review_interval_days(&["L3".into(), "review:90d".into(), "decision".into()]),
            Some(90)
        );
    }

    #[test]
    fn parse_review_days_rejects_invalid() {
        assert_eq!(parse_review_interval_days(&[]), None);
        assert_eq!(parse_review_interval_days(&["L3".into()]), None);
        assert_eq!(parse_review_interval_days(&["review:".into()]), None);
        assert_eq!(parse_review_interval_days(&["review:0d".into()]), None);
        assert_eq!(parse_review_interval_days(&["review:-5d".into()]), None);
        assert_eq!(parse_review_interval_days(&["review:30".into()]), None);
        assert_eq!(parse_review_interval_days(&["review:abcd".into()]), None);
    }

    #[test]
    fn due_review_block_empty_when_no_due() {
        let now = 1_780_000_000_i64;
        let rows = vec![
            mk_decision("d1", 0.9, &["L2"], now - 5 * 86400), // no review tag
            mk_decision("d2", 0.9, &["review:30d"], now - 10 * 86400), // tagged but not due
        ];
        assert!(format_due_review_block(&rows, now).is_none());
    }

    #[test]
    fn due_review_block_surfaces_overdue_records() {
        let now = 1_780_000_000_i64;
        let rows = vec![
            mk_decision("d_recent", 0.95, &["review:30d"], now - 5 * 86400), // not due
            mk_decision("d_due", 0.92, &["review:30d"], now - 45 * 86400),   // 15d overdue
            mk_decision(
                "d_very_overdue",
                0.88,
                &["review:30d"],
                now - 120 * 86400,
            ), // 90d overdue
        ];
        let block = format_due_review_block(&rows, now).expect("should produce block");
        // Only the two overdue ones present.
        assert!(block.contains("d_due"));
        assert!(block.contains("d_very_overdue"));
        assert!(!block.contains("d_recent"));
        // Most overdue listed first.
        let pos_very = block.find("d_very_overdue").unwrap();
        let pos_due = block.find("d_due").unwrap();
        assert!(
            pos_very < pos_due,
            "most-overdue must come first; got block:\n{block}"
        );
        // Overdue counters are visible.
        assert!(block.contains("overdue 90d"));
        assert!(block.contains("overdue 15d"));
    }

    // ── Agent-Bridge Seed block tests ───────────────────────────────────

    #[test]
    fn seed_block_returns_none_on_malformed_json() {
        assert!(format_agent_bridge_seed_block_from_json("").is_none());
        assert!(format_agent_bridge_seed_block_from_json("not json").is_none());
        assert!(format_agent_bridge_seed_block_from_json("{}").is_none()); // missing required
        assert!(
            format_agent_bridge_seed_block_from_json(r#"{"step":1}"#).is_none(),
            "n_alive missing should fail"
        );
    }

    #[test]
    fn seed_block_minimal_state_renders() {
        let json = r#"{
            "step": 322,
            "n_alive": 30,
            "spawn_count": 26,
            "death_count": 0,
            "adaptive_entropy_baseline": 0.9666,
            "depth_ratio": 1.0
        }"#;
        let block = format_agent_bridge_seed_block_from_json(json).unwrap();
        assert!(block.contains("step=322"));
        assert!(block.contains("n_alive=30"));
        assert!(block.contains("spawns=26"));
        assert!(block.contains("0.967"));
        assert!(block.contains("depth_ratio: 1.00"));
        // No optional sections.
        assert!(!block.contains("Top-3"));
        assert!(!block.contains("Recent spawn"));
    }

    #[test]
    fn seed_block_top3_neurons_sorted_by_in_strength() {
        let json = r#"{
            "step": 100, "n_alive": 5, "spawn_count": 1, "death_count": 0,
            "adaptive_entropy_baseline": 0.85, "depth_ratio": 0.6,
            "neurons": [
                {"id": 0, "age": 100, "in_strength": 0.5, "argmax_target": null},
                {"id": 1, "age": 100, "in_strength": 2.7, "argmax_target": 3},
                {"id": 2, "age": 90,  "in_strength": 1.2, "argmax_target": 1},
                {"id": 3, "age": 80,  "in_strength": 0.8, "argmax_target": 2},
                {"id": 4, "age": 70,  "in_strength": 1.9, "argmax_target": 1}
            ]
        }"#;
        let block = format_agent_bridge_seed_block_from_json(json).unwrap();
        // Top 3 are id=1 (2.7), id=4 (1.9), id=2 (1.2) — must appear in that order.
        let pos1 = block.find("n1 ").unwrap();
        let pos4 = block.find("n4 ").unwrap();
        let pos2 = block.find("n2 ").unwrap();
        assert!(pos1 < pos4, "n1 must come first (highest in_strength)");
        assert!(pos4 < pos2, "n4 must come before n2");
        assert!(!block.contains("n0 "), "id=0 below top-3");
        assert!(!block.contains("n3 "), "id=3 below top-3");
        // Carrier (target null) must render with [carrier] tag if it appears.
        // Here id=0 doesn't appear in top-3; the test for [carrier] uses minimal-state.
    }

    #[test]
    fn seed_block_carrier_label_for_null_target() {
        let json = r#"{
            "step": 100, "n_alive": 2, "spawn_count": 0, "death_count": 0,
            "adaptive_entropy_baseline": 0.5, "depth_ratio": 0.0,
            "neurons": [
                {"id": 0, "age": 100, "in_strength": 1.0, "argmax_target": null},
                {"id": 1, "age": 100, "in_strength": 0.5, "argmax_target": null}
            ]
        }"#;
        let block = format_agent_bridge_seed_block_from_json(json).unwrap();
        assert!(block.contains("[carrier]"), "null target → [carrier] tag");
    }

    #[test]
    fn seed_block_recent_spawn_events_take_last_three_chronological() {
        let json = r#"{
            "step": 322, "n_alive": 6, "spawn_count": 5, "death_count": 0,
            "adaptive_entropy_baseline": 0.95, "depth_ratio": 0.8,
            "spawn_events": [
                {"at_record": 50,  "key": "k_old1",   "kind": "lesson",   "n_alive_after": 3},
                {"at_record": 120, "key": "k_old2",   "kind": "decision", "n_alive_after": 4},
                {"at_record": 200, "key": "k_recent1","kind": "context",  "n_alive_after": 5},
                {"at_record": 280, "key": "k_recent2","kind": "lesson",   "n_alive_after": 6},
                {"at_record": 305, "key": "k_recent3","kind": "decision", "n_alive_after": 6}
            ]
        }"#;
        let block = format_agent_bridge_seed_block_from_json(json).unwrap();
        // Most recent 3, in chronological (oldest-first-within-window) order.
        assert!(block.contains("k_recent1"));
        assert!(block.contains("k_recent2"));
        assert!(block.contains("k_recent3"));
        assert!(!block.contains("k_old1"), "older events must be dropped");
        assert!(!block.contains("k_old2"));
        let p1 = block.find("k_recent1").unwrap();
        let p2 = block.find("k_recent2").unwrap();
        let p3 = block.find("k_recent3").unwrap();
        assert!(p1 < p2 && p2 < p3, "spawns kept in chronological order");
    }

    #[test]
    fn seed_block_truncates_very_long_keys() {
        let long_key = "k_".to_string() + &"x".repeat(200);
        let json = format!(
            r#"{{
                "step": 1, "n_alive": 1, "spawn_count": 1, "death_count": 0,
                "adaptive_entropy_baseline": 0.5, "depth_ratio": 0.0,
                "spawn_events": [
                    {{"at_record": 0, "key": "{long_key}", "kind": "x", "n_alive_after": 1}}
                ]
            }}"#
        );
        let block = format_agent_bridge_seed_block_from_json(&json).unwrap();
        assert!(block.contains("…"), "long key must be truncated");
    }

    #[test]
    fn seed_block_mode_field_when_present() {
        let json = r#"{
            "mode": "backfill", "n_records_processed": 322,
            "step": 322, "n_alive": 30, "spawn_count": 26, "death_count": 0,
            "adaptive_entropy_baseline": 0.97, "depth_ratio": 1.0
        }"#;
        let block = format_agent_bridge_seed_block_from_json(json).unwrap();
        assert!(block.contains("mode=backfill"));
        assert!(block.contains("records_processed=322"));
    }

    #[test]
    fn due_review_block_truncates_long_snippets() {
        let now = 1_780_000_000_i64;
        let long = "x".repeat(500);
        let mut r = mk_decision("d_long", 0.9, &["review:7d"], now - 30 * 86400);
        r.content = long;
        let block = format_due_review_block(&[r], now).unwrap();
        assert!(block.contains("…"), "long snippet must be truncated");
    }

    // ── mcp_config_audit edge cases ───────────────────────────────────────

    #[test]
    fn cli_status_disconnected_does_not_match_connected() {
        // The substring trap that produced the original false-positive.
        assert!(!cli_status_indicates_connected("Disconnected"));
        assert!(!cli_status_indicates_connected("✘ Disconnected"));
        assert!(!cli_status_indicates_connected("🔴 agent-bridge - Disconnected"));
    }

    #[test]
    fn cli_status_connected_is_recognized() {
        assert!(cli_status_indicates_connected("Connected"));
        assert!(cli_status_indicates_connected("✔ Connected"));
        assert!(cli_status_indicates_connected("Connected (45 tools)"));
        assert!(cli_status_indicates_connected("🟢 agent-bridge - Connected"));
    }

    #[test]
    fn cli_status_handles_blank_and_unknown() {
        assert!(!cli_status_indicates_connected(""));
        assert!(!cli_status_indicates_connected("Pending"));
    }

    #[test]
    fn gemini_multi_server_attributes_disconnect_to_correct_row() {
        // Per-line filtering must not bleed a sibling server's verdict
        // onto agent-bridge.
        let stdout =
            "🔴 agent-bridge - Disconnected\n🟢 some-other - Connected (12 tools)";
        let connected = stdout
            .lines()
            .filter(|l| l.contains("agent-bridge"))
            .any(cli_status_indicates_connected);
        assert!(!connected);

        let stdout =
            "🟢 agent-bridge - Connected (45 tools)\n🔴 some-other - Disconnected";
        let connected = stdout
            .lines()
            .filter(|l| l.contains("agent-bridge"))
            .any(cli_status_indicates_connected);
        assert!(connected);
    }

    // ── tool profile tier filter ──────────────────────────────────────────

    #[test]
    fn tool_profile_includes_correct_tiers() {
        // Essential profile: only essential tools.
        let p = ToolProfile::Essential;
        assert!(p.includes(Tier::Essential));
        assert!(!p.includes(Tier::Standard));
        assert!(!p.includes(Tier::Niche));

        // Standard profile: essential + standard, not niche.
        let p = ToolProfile::Standard;
        assert!(p.includes(Tier::Essential));
        assert!(p.includes(Tier::Standard));
        assert!(!p.includes(Tier::Niche));

        // All profile: everything.
        let p = ToolProfile::All;
        assert!(p.includes(Tier::Essential));
        assert!(p.includes(Tier::Standard));
        assert!(p.includes(Tier::Niche));
    }

    // ── agent_spawn policy → backend mapping ──────────────────────────────

    #[test]
    fn policy_routes_to_expected_backends() {
        assert_eq!(policy_to_backend("default"), Some("claude-code"));
        assert_eq!(policy_to_backend("cheap"), Some("kilo"));
        assert_eq!(policy_to_backend("second_opinion"), Some("codex"));
        assert_eq!(policy_to_backend("openai"), Some("codex"));
        // Whitespace-tolerant.
        assert_eq!(policy_to_backend("  cheap  "), Some("kilo"));
        // Unknown policy falls through (caller uses daemon default).
        assert_eq!(policy_to_backend("nonsense"), None);
        assert_eq!(policy_to_backend(""), None);
    }

    // ── session_identity auto-tag on fresh sibling collision ───────────────

    #[test]
    fn pid_tag_short_renders_low_16_bits_as_4_hex() {
        assert_eq!(pid_tag_short(0x12345), "2345");
        assert_eq!(pid_tag_short(0x7f3a), "7f3a");
        assert_eq!(pid_tag_short(0), "0000");
        assert_eq!(pid_tag_short(0xabcd), "abcd");
    }

    /// Helper: build a Hub backed by a fresh temp SqliteStore. Returns the
    /// hub plus the temp dir handle (caller drops to clean up).
    async fn mk_test_hub_with_store() -> (crate::Hub, std::path::PathBuf) {
        use std::sync::Arc;
        let temp_dir = std::env::temp_dir().join(format!(
            "ab-session-identity-test-{}-{}",
            std::process::id(),
            std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .unwrap_or_default()
                .as_nanos()
        ));
        tokio::fs::create_dir_all(&temp_dir).await.expect("mkdir");
        let db_path = temp_dir.join("state.db");
        let store = ab_store::SqliteStore::open(&db_path)
            .await
            .expect("open store");
        let hub = crate::Hub::builder().store(Arc::new(store)).build();
        (hub, temp_dir)
    }

    fn announce_args<'a>(
        node: &'a str,
        project: &'a str,
        role: &'a str,
        pid: i64,
    ) -> ab_store::AgentPresenceUpsert<'a> {
        ab_store::AgentPresenceUpsert {
            name: Some("test-cc"),
            description: None,
            version: None,
            url: None,
            node: Some(node),
            project: Some(project),
            role: Some(role),
            tag: None,
            cwd: None,
            pid: Some(pid),
            capabilities: None,
            skills: None,
        }
    }

    #[tokio::test]
    async fn session_identity_no_collision_returns_bare_id() {
        // Empty DB → resolve_identity stays bare even with auto_tag enabled.
        let (hub, temp_dir) = mk_test_hub_with_store().await;
        let tool = SessionIdentityTool::new(hub);
        let out = tool
            .execute(
                json!({"role":"main", "node":"testnode", "project":"proj"}),
                &ToolContext::default(),
            )
            .await
            .expect("execute");
        let payload = result_text_as_json(&out);
        assert_eq!(payload["session_id"], "testnode:proj:main");
        assert_eq!(payload["auto_tagged"], false);
        let _ = tokio::fs::remove_dir_all(&temp_dir).await;
    }

    #[tokio::test]
    async fn session_identity_auto_tags_on_fresh_sibling_collision() {
        // Pre-populate a presence row with a foreign pid + fresh heartbeat.
        // session_identity must auto-append a 4-hex pid suffix.
        let (hub, temp_dir) = mk_test_hub_with_store().await;
        let store = hub.store.as_ref().expect("store").clone();
        let foreign_pid = 0xfeed_face_u32 as i64; // not us
        store
            .agent_presence_announce(
                "testnode:proj:main",
                announce_args("testnode", "proj", "main", foreign_pid),
            )
            .await
            .expect("seed sibling row");

        let tool = SessionIdentityTool::new(hub);
        let out = tool
            .execute(
                json!({"role":"main", "node":"testnode", "project":"proj"}),
                &ToolContext::default(),
            )
            .await
            .expect("execute");
        let payload = result_text_as_json(&out);
        let expected_tag = pid_tag_short(std::process::id());
        let expected_id = format!("testnode:proj:main:{expected_tag}");
        assert_eq!(payload["session_id"], expected_id);
        assert_eq!(payload["tag"], expected_tag);
        assert_eq!(payload["auto_tagged"], true);
        let _ = tokio::fs::remove_dir_all(&temp_dir).await;
    }

    #[tokio::test]
    async fn session_identity_skips_auto_tag_when_explicit_tag_passed() {
        let (hub, temp_dir) = mk_test_hub_with_store().await;
        let store = hub.store.as_ref().expect("store").clone();
        store
            .agent_presence_announce(
                "testnode:proj:main",
                announce_args("testnode", "proj", "main", 0xdead_beef_u32 as i64),
            )
            .await
            .expect("seed sibling");

        let tool = SessionIdentityTool::new(hub);
        let out = tool
            .execute(
                json!({"role":"main", "tag":"manual", "node":"testnode", "project":"proj"}),
                &ToolContext::default(),
            )
            .await
            .expect("execute");
        let payload = result_text_as_json(&out);
        assert_eq!(payload["session_id"], "testnode:proj:main:manual");
        assert_eq!(payload["tag"], "manual");
        assert_eq!(payload["auto_tagged"], false);
        let _ = tokio::fs::remove_dir_all(&temp_dir).await;
    }

    #[tokio::test]
    async fn session_identity_skips_auto_tag_when_disabled() {
        let (hub, temp_dir) = mk_test_hub_with_store().await;
        let store = hub.store.as_ref().expect("store").clone();
        store
            .agent_presence_announce(
                "testnode:proj:main",
                announce_args("testnode", "proj", "main", 0xc0de_u32 as i64),
            )
            .await
            .expect("seed sibling");

        let tool = SessionIdentityTool::new(hub);
        let out = tool
            .execute(
                json!({"role":"main", "auto_tag": false, "node":"testnode", "project":"proj"}),
                &ToolContext::default(),
            )
            .await
            .expect("execute");
        let payload = result_text_as_json(&out);
        assert_eq!(payload["session_id"], "testnode:proj:main");
        assert_eq!(payload["auto_tagged"], false);
        let _ = tokio::fs::remove_dir_all(&temp_dir).await;
    }

    #[tokio::test]
    async fn session_identity_does_not_auto_tag_when_pid_matches_self() {
        // Existing row owned by US (same pid) — re-derive the same id, no tag.
        // This protects the normal case where a single CC re-asks identity.
        let (hub, temp_dir) = mk_test_hub_with_store().await;
        let store = hub.store.as_ref().expect("store").clone();
        let my_pid = i64::from(std::process::id());
        store
            .agent_presence_announce(
                "testnode:proj:main",
                announce_args("testnode", "proj", "main", my_pid),
            )
            .await
            .expect("seed self row");

        let tool = SessionIdentityTool::new(hub);
        let out = tool
            .execute(
                json!({"role":"main", "node":"testnode", "project":"proj"}),
                &ToolContext::default(),
            )
            .await
            .expect("execute");
        let payload = result_text_as_json(&out);
        assert_eq!(payload["session_id"], "testnode:proj:main");
        assert_eq!(payload["auto_tagged"], false);
        let _ = tokio::fs::remove_dir_all(&temp_dir).await;
    }

    fn result_text_as_json(r: &ToolResult) -> serde_json::Value {
        let txt = match r.content.first().expect("content") {
            ContentBlock::Text { text } => text.clone(),
            _ => panic!("expected text block"),
        };
        serde_json::from_str(&txt).expect("parse json")
    }
}
