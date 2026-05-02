//! Built-in MCP tools — wrap the bridge's backend bundle and expose it to
//! Claude Code (or any MCP client) over the `tools/call` channel.

use ab_agent::{oz::fetch_run_status, GitWorktreeManager, SpawnConfig};
use ab_core::{NotifyEvent, NotifySeverity, NotifySource, PageId, PaneId, Result, SessionId};
use ab_mcp::{ContentBlock, McpTool, ToolContext, ToolRegistry, ToolResult, ToolSchema};
use ab_store::{
    prioritize_session_handoff,
    // MemoryStats is used indirectly via store.memory_stats() — no direct struct access needed.
    CompactPolicy,
    ImportConflictPolicy,
    MemoryExportFilter,
    MemoryListSort,
    MemoryRecord,
    PlanRecord,
    PlanStep,
    SessionFilter,
    StateStore,
};
use ab_terminal::{
    dispatch_warp_scheme_uri, warp_scheme_launch_configuration, warp_scheme_new_tab,
    warp_scheme_new_window, warp_scheme_open_settings_page, OscEvent, OscParser, SplitDir,
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
            description: "Split a terminal pane horizontally or vertically and return the new \
                 pane's id."
                .into(),
            input_schema: json!({
                "type": "object",
                "properties": {
                    "pane": { "type": "string" },
                    "dir":  { "type": "string", "enum": ["horizontal", "vertical"], "default": "vertical" }
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
        let dir = match args
            .get("dir")
            .and_then(|v| v.as_str())
            .unwrap_or("vertical")
        {
            "horizontal" => SplitDir::Horizontal,
            _ => SplitDir::Vertical,
        };
        match term.split(&pane, dir).await {
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
//                              shell_exec tool
// ===========================================================================

const SHELL_EXEC_TRUNCATE_BYTES: usize = 131_072; // 128 KB

pub struct ShellExecTool;

impl ShellExecTool {
    pub fn new() -> Self {
        Self
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
            description: "Run a shell command synchronously and return its exit code, stdout, \
                 stderr, and wall-clock duration. Unlike terminal_send_keys this captures \
                 output directly — no PTY or scrollback parsing needed. \
                 stdout/stderr are truncated at 128 KB; check `truncated` flag. \
                 Default timeout: 30 s. Max timeout: 300 s."
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
        let cmd = match args.get("cmd").and_then(|v| v.as_str()) {
            Some(s) if !s.is_empty() => s.to_string(),
            _ => return Ok(ToolResult::error("missing or empty 'cmd'")),
        };
        let timeout_ms = args
            .get("timeout_ms")
            .and_then(|v| v.as_u64())
            .unwrap_or(30_000)
            .clamp(1_000, 300_000);

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
            format!("{s}\n[... truncated at {} KB]", SHELL_EXEC_TRUNCATE_BYTES / 1024),
            true,
        )
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
            description: "Spawn a sibling AI agent (today: Claude Code one-shot mode). \
                 Pass `prompt` and `cwd` (typically a git worktree path); the agent \
                 runs to completion in the background. Returns the new session id."
                .into(),
            input_schema: json!({
                "type": "object",
                "properties": {
                    "cwd":    { "type": "string", "description": "Working directory." },
                    "prompt": { "type": "string", "description": "Initial prompt." },
                    "env":    { "type": "object", "additionalProperties": { "type": "string" } }
                },
                "required": ["cwd", "prompt"]
            }),
        }
    }
    async fn execute(&self, args: Value, _ctx: &ToolContext) -> Result<ToolResult> {
        let agent = match &self.hub.agent {
            Some(a) => a.clone(),
            None => return Ok(ToolResult::error("no agent runtime configured")),
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

        let cfg = SpawnConfig {
            cwd,
            env,
            initial_prompt: prompt,
        };
        match agent.spawn(cfg).await {
            Ok(s) => Ok(ToolResult::json_text(
                &serde_json::to_value(s).unwrap_or(Value::Null),
            )),
            Err(e) => Ok(ToolResult::error(format!("agent: {e}"))),
        }
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
            description: "List git worktrees of a repository. Pass `repo` to point at any local \
                 git checkout for this call; if omitted, falls back to the bridge-wide \
                 default (AGENT_BRIDGE_REPO env var, else the daemon's launch cwd). \
                 Lets the agent see what parallel branches are already in flight."
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
            description: "Create a new git worktree on a fresh branch. Pass `repo` to target any \
                 local git checkout; otherwise uses the bridge-wide default. Use this \
                 when the agent wants to try multiple approaches in parallel without \
                 polluting the main checkout. Pair with `agent_spawn` to launch a \
                 sibling Claude in the new worktree."
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
            description: "Send SIGTERM to a running agent session. Use when a sub-agent has \
                 stalled, gone off-task, or you no longer need its result. The \
                 background wait task will subsequently finalise the session row \
                 with the SIGTERM exit code, so `agent_session_get(id)` afterwards \
                 still shows what (partial) output was captured."
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
            description: "List recent agent sessions (default 20, max 1000). Returns one row \
                 per spawn with id / runtime / cwd / started_at / ended_at / exit_code. \
                 All filters are optional and combine with AND: \
                 `runtime_id` exact match, `cwd_prefix` prefix match, \
                 `state` (\"running\"|\"finished\"), `exit_code` exact match \
                 (use negative for signal kills, e.g. -15 = SIGTERM). \
                 **v0.8**: each running row carries a `liveness` field — \
                 `alive` (PID still in /proc), `dead` (PID gone but \
                 finalise_session never ran → zombie row), or `unknown` \
                 (bridge restarted since spawn, no in-memory PID). \
                 Use `agent_session_get(id)` to fetch the full stdout/stderr."
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
            description: "Persist one note to agent self-memory (cross-session). Use this to \
                 record lessons, decisions, todos, or context the next-session-you \
                 (or other Claude instances) should know. Same `key` overwrites — \
                 `created_at` is preserved, `updated_at` bumps. `related_keys` is a \
                 free-form list of OTHER memory keys you think are causally linked \
                 (no graph algorithms — Claude declares relationships explicitly)."
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
            description: "Search memories by keyword (FTS5) with optional graph-neighbor expansion. \
                 Two modes: \
                 (1) mode='fts' (default): FTS5 full-text search ranked by bm25 + recency + importance. \
                 (2) mode='hybrid': FTS5 results expanded via graph neighbors, fused with \
                 Reciprocal Rank Fusion (RRF k=60). Surfaces memories connected to top hits \
                 even if they don't contain the query keyword. \
                 Results always exclude archived/superseded memories. \
                 Use 'hybrid' when you want broader discovery; 'fts' when you need precision."
                .into(),
            input_schema: json!({
                "type": "object",
                "properties": {
                    "query":      { "type": "string", "description": "Search query (FTS5 match syntax supported)." },
                    "tags_any":   { "type": "array", "items": { "type": "string" }, "default": [] },
                    "limit":      { "type": "integer", "minimum": 1, "maximum": 200, "default": 20 },
                    "mode":       {
                        "type": "string", "enum": ["fts", "hybrid"], "default": "fts",
                        "description": "'fts' = keyword only; 'hybrid' = FTS5 + graph RRF fusion."
                    },
                    "expand_top": {
                        "type": "integer", "minimum": 1, "maximum": 20, "default": 10,
                        "description": "[hybrid only] Number of top FTS5 hits to expand via graph neighbors."
                    },
                    "rrf_k":      {
                        "type": "number", "minimum": 1.0, "maximum": 200.0, "default": 60.0,
                        "description": "[hybrid only] RRF constant k. Higher k = less rank compression."
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
                .memory_search_hybrid(&q, &tags, limit, rrf_k, expand_top)
                .await?
        } else {
            store.memory_search(&q, &tags, limit).await?
        };

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
            description: "List memories, optionally filtered by `kind`, sorted by one of \
                 'recent' (default — last_accessed_at desc), 'frequent' \
                 (access_count desc), or 'newest' (created_at desc). Use this at \
                 session start with kind='lesson' to surface what previous-you \
                 learned."
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
            description: "Prune low-value memories. A row is removed only if BOTH thresholds \
                 match (AND): `min_uses` (access_count strictly less than) AND \
                 `older_than_days` (last_accessed_at older than now - that many \
                 days). A 1-hour grace period on `created_at` further protects \
                 freshly-saved rows. Set `dry_run=true` to preview the keys that \
                 would be deleted without actually removing them. **v0.8**: if \
                 BOTH thresholds are omitted, a balanced default is applied \
                 (`min_uses=2`, `older_than_days=90`) so callers don't get a \
                 silent no-op — the response field `applied_defaults` flags \
                 when this happens."
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
                 Optional filters narrow what's exported. The output file can \
                 then be moved across machines via any transport (scp, email \
                 attachment, cloud drive, git repo) and consumed by \
                 `memory_import` on the other side."
                .into(),
            input_schema: json!({
                "type": "object",
                "properties": {
                    "path":     { "type": "string", "description": "Absolute output path; parent dirs auto-created." },
                    "kind":     { "type": "string", "description": "Optional kind filter." },
                    "tags_any": { "type": "array", "items": {"type": "string"}, "description": "Match if memory has at least one tag." },
                    "since_ts": { "type": "integer", "description": "Only memories with updated_at >= this unix-epoch seconds value." }
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
        };
        match store.memory_export(&filter, &path).await {
            Ok(n) => Ok(ToolResult::json_text(&json!({
                "exported": n,
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
                 produces). `conflict_policy` decides what happens when a key \
                 already exists locally:\n\
                   - `skip` (default): keep local row\n\
                   - `overwrite`: always replace with the imported row\n\
                   - `newer_wins`: replace only if imported.updated_at is greater\n\
                 Returns a per-row summary {inserted, updated, skipped, malformed}."
                .into(),
            input_schema: json!({
                "type": "object",
                "properties": {
                    "path":            { "type": "string" },
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
        match store.memory_import(&path, policy).await {
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
            description: "Create or update a directed edge between two memory records. \
                 Edges are typed and weights are auto-assigned by type unless overridden. \
                 Standard types and base weights: \
                 updates(1.5) — newest replaces old; \
                 caused_by(1.3) — causal chain; \
                 supersedes(1.3) — explicit supersession; \
                 implements(1.1) — concrete realisation; \
                 relates(1.0) — generic relation; \
                 part_of(0.8) — structural containment; \
                 derived_from(0.8) — loose derivation; \
                 contradicts(0.5) — known conflict; \
                 invalidates(0.5) — explicit invalidation. \
                 Causal edge types get a ×1.2 temporal bonus in BFS traversal. \
                 Pairs with `memory_neighbors` (BFS) to walk the knowledge graph."
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
            description: "Return graph edges (and optionally BFS-traverse multi-hop) from a memory key. \
                 With depth=1 (default) returns direct neighbors ordered by weight DESC. \
                 With depth>1 performs BFS traversal, propagating energy as \
                 energy × edge_weight × temporal_bonus × decay_factor. \
                 Returns [{from_key, to_key, edge_type, weight, energy}] sorted by energy DESC. \
                 Causal edge types (updates, caused_by, supersedes, implements) get ×1.2 temporal bonus. \
                 Conflict edges (contradicts, invalidates) get ×0.85. \
                 Use this to discover chains of related decisions, bug-fix histories, and design evolutions."
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
            description: "Build a compact memory bootstrap block for the current session. \
                 Returns top scoped memories (global + project), with session_handoff \
                 rows first for continuity. \
                 Pass frontend='cursor' or 'warp' for the compact \
                 token-efficient format, or frontend='claude-code' \
                 (default) for the full format."
                .into(),
            input_schema: json!({
                "type": "object",
                "properties": {
                    "cwd": { "type": "string", "description": "Optional project path for scope filtering. Defaults to process cwd." },
                    "limit": { "type": "integer", "minimum": 1, "maximum": 200, "default": 60 },
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

        let rows = store
            .list_memories_in_scope(&cwd, None, MemoryListSort::ByImportance, limit)
            .await?;

        // Filter to active memories only — archived and superseded are hidden
        // from bootstrap to keep context clean.
        let rows: Vec<_> = rows.into_iter().filter(|r| r.status == "active").collect();
        let rows = prioritize_session_handoff(rows);

        if rows.is_empty() && error_section.is_empty() {
            let lifecycle_hint = session_lifecycle_hint();
            return Ok(ToolResult::text(format!(
                "(no scoped memories yet)\n\n{lifecycle_hint}"
            )));
        }

        let mut lines = if is_compact {
            // Compact format (Cursor / Warp): minimal headers, 80-char snippets
            vec![format!("=== Bootstrap (scope: {}) ===", cwd), String::new()]
        } else {
            vec![
                format!("=== Agent-Bridge Session Bootstrap (scope: {cwd}) ==="),
                "Use memory_get <key> for full content, memory_search for lookup.".to_string(),
                String::new(),
            ]
        };

        lines.extend(error_section);
        lines.extend(format_bootstrap_memory_rows(&rows, snippet_len));
        lines.push("=== End Bootstrap ===".to_string());
        lines.push(String::new());
        lines.push(session_lifecycle_hint());
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
            description: "Extract structured memories from conversation text using a two-pass \
                 pipeline: (1) explicit marker detection (lesson:, decision:, todo:, \
                 handoff:, etc.) and (2) implicit lexical signal scoring that catches \
                 unmarked insights via epistemic/normative/causal/decision signals \
                 in English and Chinese. Persists results to the memory store. \
                 Replaces the PreCompact hook's claude -p dependency — works in any \
                 frontend. Pass dry_run=true to preview without writing."
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
            description: "Return what the agent-bridge backend can do in this environment: \
                 terminal backend, browser availability, memory store status, \
                 configured hooks, detected frontend, and binary version. \
                 Call once at session start to avoid wasting tokens on unavailable features."
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
                "fts5": true
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
            "oz_run_tools": runtime_id == "warp-oz",
            "version": version
        })))
    }
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
            description: "Return aggregate statistics about the memory store: \
                 total counts by status (active/archived/superseded), \
                 counts per kind for active memories, number of graph edges, \
                 oldest/newest timestamps, average importance, top tags, \
                 and approximate DB size. \
                 Call before session_curate or session_finalize to understand \
                 store health without reading individual records."
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
            description: "Manual session-end maintenance for Cursor: run importance decay, \
                 compact stale memories, and optionally export JSONL. \
                 Equivalent to Claude Code's Stop hook pipeline. \
                 Response includes follow_up with active_total and an optional hint to run memory_consolidate \
                 when the active graph is large."
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
                    "export_path": { "type": "string", "description": "Optional JSONL export output path." }
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
            export_summary = json!({ "path": path, "exported": exported });
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
                "Scan a directory for common project manifests (Cargo.toml, package.json, \
                 pyproject.toml, go.mod, Makefile), infer languages and suggested test/lint/format \
                 commands, list Rust workspace members via cargo metadata, and snapshot git \
                 branch/clean/recent commit. Optional cwd defaults to process working directory."
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
            description: "Build a machine-readable session handoff brief for the next agent: \
                 aggregates active todos, recent session_handoff memories, git branch / \
                 last commit / working-tree files, plus optional narrative fields. \
                 No new tables — combines memory store + git only (DESIGN D9)."
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
            _ => return Ok(ToolResult::error(
                "WARP_API_KEY env var not set. \
                 Generate an API key at Warp Settings → Platform \
                 (warp://settings/platform), then export WARP_API_KEY=<key>."
            )),
        };

        // ── POST .../cancel via curl ──────────────────────────────────────
        // The oz CLI has no 'oz run cancel' subcommand; we call the REST API directly.
        // Endpoint: POST https://app.warp.dev/api/v1/agent/runs/{runId}/cancel
        let url = format!(
            "https://app.warp.dev/api/v1/agent/runs/{}/cancel",
            run_id
        );
        let out = tokio::process::Command::new("curl")
            .args([
                "-s",                           // silent
                "-X", "POST",
                "-H", &format!("Authorization: Bearer {api_key}"),
                "-H", "Content-Type: application/json",
                "-w", "\n__HTTP_STATUS__%{http_code}",
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

pub struct WarpOpenTabTool;

impl WarpOpenTabTool {
    pub fn new(_hub: Hub) -> Self {
        Self
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
            description: "Open a new Warp tab via URI scheme (warp://action/new_tab). \
                 Optional `path` sets initial cwd (defaults to bridge process cwd). \
                 Dispatches through AGENT_BRIDGE_WARP_OPENER (xdg-open / open)."
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
        dispatch_warp_scheme_uri(&uri)
            .await
            .map_err(|e| ab_core::Error::Backend(format!("warp_open_tab: {e}")))?;
        Ok(ToolResult::json_text(
            &json!({ "status": "ok", "uri": uri }),
        ))
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
//                                  registry
// ===========================================================================

pub fn build_registry(hub: Hub) -> ToolRegistry {
    let mut reg = ToolRegistry::new();
    // Notification surface
    reg.register(Arc::new(NotifyTool::new(hub.clone())));
    reg.register(Arc::new(NotificationsRecentTool::new(hub.clone())));
    reg.register(Arc::new(OscParseTool::new(hub.clone())));
    // Terminal surface
    reg.register(Arc::new(TerminalListTool::new(hub.clone())));
    reg.register(Arc::new(TerminalSendKeysTool::new(hub.clone())));
    reg.register(Arc::new(TerminalReadOutputTool::new(hub.clone())));
    reg.register(Arc::new(TerminalSplitTool::new(hub.clone())));
    reg.register(Arc::new(ShellExecTool::new()));
    // Browser surface
    reg.register(Arc::new(BrowserNavigateTool::new(hub.clone())));
    reg.register(Arc::new(BrowserEvalTool::new(hub.clone())));
    reg.register(Arc::new(BrowserSnapshotTool::new(hub.clone())));
    reg.register(Arc::new(BrowserClickTool::new(hub.clone())));
    reg.register(Arc::new(BrowserScreenshotTool::new(hub.clone())));
    reg.register(Arc::new(BrowserExtractTextTool::new(hub.clone())));
    reg.register(Arc::new(BrowserFillFormTool::new(hub.clone())));
    // Agent + worktree surface
    reg.register(Arc::new(AgentSpawnTool::new(hub.clone())));
    reg.register(Arc::new(AgentKillTool::new(hub.clone())));
    reg.register(Arc::new(AgentSessionListTool::new(hub.clone())));
    reg.register(Arc::new(AgentSessionGetTool::new(hub.clone())));
    reg.register(Arc::new(AgentSessionWaitTool::new(hub.clone())));
    reg.register(Arc::new(WorktreeListTool::new(hub.clone())));
    reg.register(Arc::new(WorktreeCreateTool::new(hub.clone())));
    reg.register(Arc::new(WorktreeRemoveTool::new(hub.clone())));
    // v0.4: agent self-memory
    reg.register(Arc::new(MemorySaveTool::new(hub.clone())));
    reg.register(Arc::new(MemoryGetTool::new(hub.clone())));
    reg.register(Arc::new(MemorySearchTool::new(hub.clone())));
    reg.register(Arc::new(MemoryListTool::new(hub.clone())));
    reg.register(Arc::new(MemoryDeleteTool::new(hub.clone())));
    reg.register(Arc::new(MemoryCompactTool::new(hub.clone())));
    reg.register(Arc::new(MemoryExportTool::new(hub.clone())));
    reg.register(Arc::new(MemoryImportTool::new(hub.clone())));
    reg.register(Arc::new(MemoryConsolidateTool::new(hub.clone())));
    // v0.6: graph edges
    reg.register(Arc::new(MemoryLinkTool::new(hub.clone())));
    reg.register(Arc::new(MemoryNeighborsTool::new(hub.clone())));
    // Cursor-friendly manual equivalents for Claude hook lifecycle.
    reg.register(Arc::new(SessionBootstrapTool::new(hub.clone())));
    reg.register(Arc::new(SessionFinalizeTool::new(hub.clone())));
    // v0.9: Cursor capability alignment
    reg.register(Arc::new(SessionCurateTool::new(hub.clone())));
    // W3: structured handoff + lifecycle dispatcher (DESIGN-warp-first-agent-shell)
    reg.register(Arc::new(SessionHandoffBriefTool::new(hub.clone())));
    reg.register(Arc::new(SessionLifecycleStepTool::new(hub.clone())));
    reg.register(Arc::new(HookStatusTool::new(hub.clone())));
    reg.register(Arc::new(ProjectDetectTool::new(hub.clone())));
    reg.register(Arc::new(ChangesDigestTool::new(hub.clone())));
    reg.register(Arc::new(CapabilitiesTool::new(hub.clone())));
    reg.register(Arc::new(MemoryStatsTool::new(hub.clone())));
    reg.register(Arc::new(MemorySuggestTool::new(hub.clone())));
    // v0.10: warp-oz cloud-run lifecycle tools
    reg.register(Arc::new(OzRunGetTool::new(hub.clone())));
    reg.register(Arc::new(OzRunListTool::new(hub.clone())));
    reg.register(Arc::new(OzRunCancelTool::new(hub.clone())));
    // W4: Warp URI scheme (DESIGN-warp-first-agent-shell)
    reg.register(Arc::new(WarpOpenTabTool::new(hub.clone())));
    reg.register(Arc::new(WarpOpenWindowTool::new(hub.clone())));
    reg.register(Arc::new(WarpOpenSettingsTool::new(hub.clone())));
    reg.register(Arc::new(WarpLaunchWorkflowTool::new(hub.clone())));
    reg.register(Arc::new(WarpStatusTool::new(hub.clone())));
    // v0.11: memory graph visualisation
    reg.register(Arc::new(MemoryGraphExportTool::new(hub.clone())));
    // v0.12: automated memory curation
    // W5: structured plans + context budget (DESIGN-warp-first-agent-shell)
    reg.register(Arc::new(PlanSaveTool::new(hub.clone())));
    reg.register(Arc::new(PlanLoadTool::new(hub.clone())));
    reg.register(Arc::new(PlanUpdateTool::new(hub.clone())));
    reg.register(Arc::new(ContextBudgetTool::new()));
    // W6: browser extract/fill + multi-session inbox (DESIGN-warp-first-agent-shell)
    reg.register(Arc::new(AgentMessageTool::new(hub.clone())));
    reg.register(Arc::new(AgentInboxTool::new(hub.clone())));
    reg.register(Arc::new(MemoryAutoCurateTool::new(hub)));
    reg
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
            Some('n')  => out.push('\n'),
            Some('r')  => out.push('\r'),
            Some('t')  => out.push('\t'),
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
                    out.push('\\'); out.push('x');
                    if let Some(a) = h1 { out.push(a); }
                    if let Some(b) = h2 { out.push(b); }
                }
            }
            Some(other) => { out.push('\\'); out.push(other); }
            None        => out.push('\\'),
        }
    }
    out
}
