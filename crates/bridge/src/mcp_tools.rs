//! Built-in MCP tools — wrap the bridge's backend bundle and expose it to
//! Claude Code (or any MCP client) over the `tools/call` channel.

use ab_agent::SpawnConfig;
use ab_core::{NotifyEvent, NotifySeverity, NotifySource, PageId, PaneId, Result};
use ab_mcp::{McpTool, ToolContext, ToolRegistry, ToolResult, ToolSchema};
use ab_terminal::{OscEvent, OscParser, SplitDir};
use async_trait::async_trait;
use base64::{engine::general_purpose, Engine as _};
use serde_json::{json, Value};
use std::collections::HashMap;
use std::path::PathBuf;
use std::sync::Arc;

use crate::hub::Hub;

// ===========================================================================
//                                   notify
// ===========================================================================

pub struct NotifyTool { hub: Hub }
impl NotifyTool { pub fn new(hub: Hub) -> Self { Self { hub } } }

#[async_trait]
impl McpTool for NotifyTool {
    fn name(&self) -> &'static str { "notify" }
    fn schema(&self) -> ToolSchema {
        ToolSchema {
            name: self.name().into(),
            description:
                "Send a desktop notification. Persists to the bridge's history \
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
            severity: args.get("severity").and_then(|v| v.as_str()).and_then(parse_severity).unwrap_or(NotifySeverity::Info),
            title: args.get("title").and_then(|v| v.as_str()).unwrap_or("agent-bridge").into(),
            body: args.get("body").and_then(|v| v.as_str()).unwrap_or("").into(),
            session_id: None,
            context: Value::Null,
        };
        let (delivered, persisted) = self.hub.deliver(&evt).await;
        Ok(ToolResult::text(format!("delivered to {delivered} notifier(s); persisted={persisted}")))
    }
}

// ===========================================================================
//                            notifications_recent
// ===========================================================================

pub struct NotificationsRecentTool { hub: Hub }
impl NotificationsRecentTool { pub fn new(hub: Hub) -> Self { Self { hub } } }

#[async_trait]
impl McpTool for NotificationsRecentTool {
    fn name(&self) -> &'static str { "notifications_recent" }
    fn schema(&self) -> ToolSchema {
        ToolSchema {
            name: self.name().into(),
            description:
                "Return the most-recent N notifications from the bridge's persistent \
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
        let limit = args.get("limit").and_then(|v| v.as_u64()).unwrap_or(20).min(1000) as u32;
        let rows = store.recent_notifications(limit).await?;
        Ok(ToolResult::json_text(&serde_json::to_value(rows).unwrap_or(Value::Null)))
    }
}

// ===========================================================================
//                                osc_parse
// ===========================================================================

pub struct OscParseTool { hub: Hub }
impl OscParseTool { pub fn new(hub: Hub) -> Self { Self { hub } } }

#[async_trait]
impl McpTool for OscParseTool {
    fn name(&self) -> &'static str { "osc_parse" }
    fn schema(&self) -> ToolSchema {
        ToolSchema {
            name: self.name().into(),
            description:
                "Parse a raw byte sequence for OSC 9 / 99 / 777 notification escape \
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
        let raw = args.get("raw").and_then(|v| v.as_str()).unwrap_or("").as_bytes().to_vec();
        let mut parser = OscParser::new();
        let events = parser.feed(&raw);
        let mut delivered = 0u32;
        let mut malformed = Vec::new();
        for e in &events {
            match e {
                OscEvent::Notify(evt) => {
                    let (d, _p) = self.hub.deliver(evt).await;
                    if d > 0 { delivered += 1; }
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

pub struct TerminalListTool { hub: Hub }
impl TerminalListTool { pub fn new(hub: Hub) -> Self { Self { hub } } }
#[async_trait]
impl McpTool for TerminalListTool {
    fn name(&self) -> &'static str { "terminal_list" }
    fn schema(&self) -> ToolSchema {
        ToolSchema {
            name: self.name().into(),
            description:
                "List terminal panes from the active terminal-multiplexer backend \
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
            Ok(panes) => Ok(ToolResult::json_text(&serde_json::to_value(panes).unwrap_or(Value::Null))),
            Err(e) => Ok(ToolResult::error(format!("terminal: {e}"))),
        }
    }
}

pub struct TerminalSendKeysTool { hub: Hub }
impl TerminalSendKeysTool { pub fn new(hub: Hub) -> Self { Self { hub } } }
#[async_trait]
impl McpTool for TerminalSendKeysTool {
    fn name(&self) -> &'static str { "terminal_send_keys" }
    fn schema(&self) -> ToolSchema {
        ToolSchema {
            name: self.name().into(),
            description:
                "Type the given text into the specified terminal pane (e.g. send a \
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
        let keys = args.get("keys").and_then(|v| v.as_str()).unwrap_or("");
        match term.send_keys(&pane, keys).await {
            Ok(()) => Ok(ToolResult::text(format!("sent {} bytes to {pane}", keys.len()))),
            Err(e) => Ok(ToolResult::error(format!("terminal: {e}"))),
        }
    }
}

pub struct TerminalSplitTool { hub: Hub }
impl TerminalSplitTool { pub fn new(hub: Hub) -> Self { Self { hub } } }
#[async_trait]
impl McpTool for TerminalSplitTool {
    fn name(&self) -> &'static str { "terminal_split" }
    fn schema(&self) -> ToolSchema {
        ToolSchema {
            name: self.name().into(),
            description:
                "Split a terminal pane horizontally or vertically and return the new \
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
        let dir = match args.get("dir").and_then(|v| v.as_str()).unwrap_or("vertical") {
            "horizontal" => SplitDir::Horizontal,
            _ => SplitDir::Vertical,
        };
        match term.split(&pane, dir).await {
            Ok(new_pane) => Ok(ToolResult::text(format!("new pane: {new_pane}"))),
            Err(e) => Ok(ToolResult::error(format!("terminal: {e}"))),
        }
    }
}

// ===========================================================================
//                              browser tools
// ===========================================================================

pub struct BrowserNavigateTool { hub: Hub }
impl BrowserNavigateTool { pub fn new(hub: Hub) -> Self { Self { hub } } }
#[async_trait]
impl McpTool for BrowserNavigateTool {
    fn name(&self) -> &'static str { "browser_navigate" }
    fn schema(&self) -> ToolSchema {
        ToolSchema {
            name: self.name().into(),
            description:
                "Open a URL in the agent-bridge browser and return a page id you can \
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

pub struct BrowserEvalTool { hub: Hub }
impl BrowserEvalTool { pub fn new(hub: Hub) -> Self { Self { hub } } }
#[async_trait]
impl McpTool for BrowserEvalTool {
    fn name(&self) -> &'static str { "browser_eval" }
    fn schema(&self) -> ToolSchema {
        ToolSchema {
            name: self.name().into(),
            description:
                "Evaluate JavaScript in the given page's main frame and return the \
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

pub struct BrowserSnapshotTool { hub: Hub }
impl BrowserSnapshotTool { pub fn new(hub: Hub) -> Self { Self { hub } } }
#[async_trait]
impl McpTool for BrowserSnapshotTool {
    fn name(&self) -> &'static str { "browser_snapshot" }
    fn schema(&self) -> ToolSchema {
        ToolSchema {
            name: self.name().into(),
            description:
                "Return the page's accessibility tree (role/name/value + children). \
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
            Ok(tree) => Ok(ToolResult::json_text(&serde_json::to_value(tree).unwrap_or(Value::Null))),
            Err(e) => Ok(ToolResult::error(format!("browser: {e}"))),
        }
    }
}

pub struct BrowserClickTool { hub: Hub }
impl BrowserClickTool { pub fn new(hub: Hub) -> Self { Self { hub } } }
#[async_trait]
impl McpTool for BrowserClickTool {
    fn name(&self) -> &'static str { "browser_click" }
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

pub struct BrowserScreenshotTool { hub: Hub }
impl BrowserScreenshotTool { pub fn new(hub: Hub) -> Self { Self { hub } } }
#[async_trait]
impl McpTool for BrowserScreenshotTool {
    fn name(&self) -> &'static str { "browser_screenshot" }
    fn schema(&self) -> ToolSchema {
        ToolSchema {
            name: self.name().into(),
            description:
                "Capture a full-page PNG screenshot. By default writes to /tmp and \
                 returns the path; if `inline=true` returns base64 in-line (token-heavy, \
                 only use for small viewports)."
                    .into(),
            input_schema: json!({
                "type": "object",
                "properties": {
                    "page":   { "type": "string" },
                    "path":   { "type": "string", "description": "Optional output path." },
                    "inline": { "type": "boolean", "default": false }
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
        let inline = args.get("inline").and_then(|v| v.as_bool()).unwrap_or(false);
        if inline {
            let b64 = general_purpose::STANDARD.encode(&png);
            return Ok(ToolResult::text(format!("data:image/png;base64,{b64}")));
        }
        let path = args
            .get("path")
            .and_then(|v| v.as_str())
            .map(|s| s.to_string())
            .unwrap_or_else(|| format!("/tmp/agent-bridge-{}.png", page));
        if let Err(e) = tokio::fs::write(&path, &png).await {
            return Ok(ToolResult::error(format!("write {path}: {e}")));
        }
        Ok(ToolResult::text(format!("wrote {} bytes → {path}", png.len())))
    }
}

// ===========================================================================
//                       agent + worktree tools
// ===========================================================================

pub struct AgentSpawnTool { hub: Hub }
impl AgentSpawnTool { pub fn new(hub: Hub) -> Self { Self { hub } } }
#[async_trait]
impl McpTool for AgentSpawnTool {
    fn name(&self) -> &'static str { "agent_spawn" }
    fn schema(&self) -> ToolSchema {
        ToolSchema {
            name: self.name().into(),
            description:
                "Spawn a sibling AI agent (today: Claude Code one-shot mode). \
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
        let prompt = args.get("prompt").and_then(|v| v.as_str()).map(|s| s.to_string());
        let env: HashMap<String, String> = args
            .get("env")
            .and_then(|v| v.as_object())
            .map(|m| {
                m.iter()
                    .filter_map(|(k, v)| v.as_str().map(|s| (k.clone(), s.to_string())))
                    .collect()
            })
            .unwrap_or_default();

        let cfg = SpawnConfig { cwd, env, initial_prompt: prompt };
        match agent.spawn(cfg).await {
            Ok(s) => Ok(ToolResult::json_text(&serde_json::to_value(s).unwrap_or(Value::Null))),
            Err(e) => Ok(ToolResult::error(format!("agent: {e}"))),
        }
    }
}

pub struct WorktreeListTool { hub: Hub }
impl WorktreeListTool { pub fn new(hub: Hub) -> Self { Self { hub } } }
#[async_trait]
impl McpTool for WorktreeListTool {
    fn name(&self) -> &'static str { "worktree_list" }
    fn schema(&self) -> ToolSchema {
        ToolSchema {
            name: self.name().into(),
            description:
                "List git worktrees rooted at the bridge's repo (set with the \
                 AGENT_BRIDGE_REPO env var; defaults to the daemon's launch cwd). \
                 Lets the agent see what parallel branches are already in flight."
                    .into(),
            input_schema: json!({ "type": "object", "properties": {} }),
        }
    }
    async fn execute(&self, _args: Value, _ctx: &ToolContext) -> Result<ToolResult> {
        let w = match &self.hub.worktree {
            Some(w) => w.clone(),
            None => return Ok(ToolResult::error("no worktree manager configured")),
        };
        match w.list().await {
            Ok(rows) => Ok(ToolResult::json_text(&serde_json::to_value(rows).unwrap_or(Value::Null))),
            Err(e) => Ok(ToolResult::error(format!("worktree: {e}"))),
        }
    }
}

pub struct WorktreeCreateTool { hub: Hub }
impl WorktreeCreateTool { pub fn new(hub: Hub) -> Self { Self { hub } } }
#[async_trait]
impl McpTool for WorktreeCreateTool {
    fn name(&self) -> &'static str { "worktree_create" }
    fn schema(&self) -> ToolSchema {
        ToolSchema {
            name: self.name().into(),
            description:
                "Create a new git worktree on a fresh branch. Use this when the agent \
                 wants to try multiple approaches in parallel without polluting the \
                 main checkout. Pair with `agent_spawn` to launch a sibling Claude in \
                 the new worktree."
                    .into(),
            input_schema: json!({
                "type": "object",
                "properties": {
                    "branch": { "type": "string" },
                    "path":   { "type": "string", "description": "Where to put the worktree dir." },
                    "base":   { "type": "string", "description": "Branch/commit to fork from. Defaults to HEAD." }
                },
                "required": ["branch", "path"]
            }),
        }
    }
    async fn execute(&self, args: Value, _ctx: &ToolContext) -> Result<ToolResult> {
        let w = match &self.hub.worktree {
            Some(w) => w.clone(),
            None => return Ok(ToolResult::error("no worktree manager configured")),
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
            Ok(wt) => Ok(ToolResult::json_text(&serde_json::to_value(wt).unwrap_or(Value::Null))),
            Err(e) => Ok(ToolResult::error(format!("worktree: {e}"))),
        }
    }
}

pub struct WorktreeRemoveTool { hub: Hub }
impl WorktreeRemoveTool { pub fn new(hub: Hub) -> Self { Self { hub } } }
#[async_trait]
impl McpTool for WorktreeRemoveTool {
    fn name(&self) -> &'static str { "worktree_remove" }
    fn schema(&self) -> ToolSchema {
        ToolSchema {
            name: self.name().into(),
            description:
                "Remove a git worktree. Set `force=true` to clobber dirty working trees."
                    .into(),
            input_schema: json!({
                "type": "object",
                "properties": {
                    "path":  { "type": "string" },
                    "force": { "type": "boolean", "default": false }
                },
                "required": ["path"]
            }),
        }
    }
    async fn execute(&self, args: Value, _ctx: &ToolContext) -> Result<ToolResult> {
        let w = match &self.hub.worktree {
            Some(w) => w.clone(),
            None => return Ok(ToolResult::error("no worktree manager configured")),
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
    reg.register(Arc::new(TerminalSplitTool::new(hub.clone())));
    // Browser surface
    reg.register(Arc::new(BrowserNavigateTool::new(hub.clone())));
    reg.register(Arc::new(BrowserEvalTool::new(hub.clone())));
    reg.register(Arc::new(BrowserSnapshotTool::new(hub.clone())));
    reg.register(Arc::new(BrowserClickTool::new(hub.clone())));
    reg.register(Arc::new(BrowserScreenshotTool::new(hub.clone())));
    // Agent + worktree surface
    reg.register(Arc::new(AgentSpawnTool::new(hub.clone())));
    reg.register(Arc::new(WorktreeListTool::new(hub.clone())));
    reg.register(Arc::new(WorktreeCreateTool::new(hub.clone())));
    reg.register(Arc::new(WorktreeRemoveTool::new(hub)));
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
