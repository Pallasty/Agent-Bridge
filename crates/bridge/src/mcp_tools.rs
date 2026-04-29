//! Built-in MCP tools — wrap the bridge's backend bundle and expose it to
//! Claude Code (or any MCP client) over the `tools/call` channel.

use ab_agent::{GitWorktreeManager, SpawnConfig};
use ab_core::{NotifyEvent, NotifySeverity, NotifySource, PageId, PaneId, Result, SessionId};
use ab_mcp::{McpTool, ToolContext, ToolRegistry, ToolResult, ToolSchema};
use ab_store::{
    CompactPolicy, ImportConflictPolicy, MemoryExportFilter, MemoryListSort, MemoryRecord,
    SessionFilter, StateStore,
};
use ab_terminal::{OscEvent, OscParser, SplitDir};
use async_trait::async_trait;
use base64::{engine::general_purpose, Engine as _};
use serde_json::{json, Value};
use std::collections::HashMap;
use std::path::PathBuf;
use std::sync::Arc;
use std::time::{Duration, Instant};

use crate::hub::Hub;

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
        let keys = args.get("keys").and_then(|v| v.as_str()).unwrap_or("");
        match term.send_keys(&pane, keys).await {
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

        loop {
            let row = store.load_session(&id).await?;
            match row.as_ref() {
                Some(s) if s.ended_at.is_some() => {
                    return Ok(ToolResult::json_text(&json!({
                        "timed_out": false,
                        "session": s,
                    })));
                }
                _ => {}
            }
            if Instant::now() >= deadline {
                return Ok(ToolResult::json_text(&json!({
                    "timed_out": true,
                    "session": row,
                })));
            }
            tokio::time::sleep(Duration::from_millis(500)).await;
        }
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
    let is_clean = |s: &str| {
        s.len() >= 3 && s.chars().all(|c| c.is_ascii_alphanumeric())
    };
    let tag_terms: Vec<String> = tags
        .iter()
        .filter(|t| is_clean(t))
        .cloned()
        .collect();
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
    let query = terms.join(" OR ");  // FTS5 OR: any term matches

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
                    "importance":   { "type": "number", "minimum": 0.0, "maximum": 1.0, "description": "Override importance (0.0–1.0). Omit to auto-assign from kind: decision=0.8, lesson=0.7, todo=0.6, fact=0.5, observation=0.3." }
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
        };
        match store.memory_save(&mem).await {
            Ok(()) => {
                let hint =
                    build_proactive_hint(&store, &key, &mem.content, &mem.tags).await;
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
                let hint =
                    build_proactive_hint(&store, &key, &rec.content, &rec.tags).await;
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
        let mode = args
            .get("mode")
            .and_then(|v| v.as_str())
            .unwrap_or("fts");

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
        let weight = args
            .get("weight")
            .and_then(|v| v.as_f64())
            .unwrap_or(1.0);
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
                 Returns top scoped memories (global + project). \
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

        let rows = store
            .list_memories_in_scope(&cwd, None, MemoryListSort::ByImportance, limit)
            .await?;

        // Filter to active memories only — archived and superseded are hidden
        // from bootstrap to keep context clean.
        let rows: Vec<_> = rows
            .into_iter()
            .filter(|r| r.status == "active")
            .collect();

        if rows.is_empty() {
            let lifecycle_hint = session_lifecycle_hint();
            return Ok(ToolResult::text(format!(
                "(no scoped memories yet)\n\n{lifecycle_hint}"
            )));
        }

        let mut lines = if is_compact {
            // Compact format (Cursor / Warp): minimal headers, 80-char snippets
            vec![
                format!("=== Bootstrap (scope: {}) ===", cwd),
                String::new(),
            ]
        } else {
            vec![
                format!("=== Agent-Bridge Session Bootstrap (scope: {cwd}) ==="),
                "Use memory_get <key> for full content, memory_search for lookup.".to_string(),
                String::new(),
            ]
        };

        let snippet_len = if is_compact { 80 } else { 120 };
        for r in &rows {
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
            lines.push(format!(
                "[{}] {}{}{}: {}{}",
                r.kind, r.key, imp_marker, tags, snippet, ellipsis
            ));
        }
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
     1. session_curate(conversation_text=<recent context summary>) — extract and save lessons\n\
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

/// Explicit line-prefix markers → memory kind.
static CURATE_MARKERS: &[(&str, &str)] = &[
    ("lesson:", "lesson"),
    ("learned:", "lesson"),
    ("learning:", "lesson"),
    ("gotcha:", "lesson"),
    ("pitfall:", "lesson"),
    ("bug:", "lesson"),
    ("fix:", "lesson"),
    ("warning:", "lesson"),
    ("pattern:", "lesson"),
    ("decision:", "decision"),
    ("decided:", "decision"),
    ("design:", "decision"),
    ("architecture:", "decision"),
    ("we decided:", "decision"),
    ("we chose:", "decision"),
    ("todo:", "todo"),
    ("TODO:", "todo"),
    ("action item:", "todo"),
    ("next step:", "todo"),
    ("note:", "context"),
    ("context:", "context"),
    ("status:", "context"),
    ("state:", "context"),
    ("remember:", "context"),
    ("important:", "context"),
    ("key insight:", "lesson"),
    ("root cause:", "lesson"),
    ("handoff:", "session_handoff"),
    ("session_handoff:", "session_handoff"),
];

/// Section-header keywords that make subsequent bullet-list lines inherit a kind.
/// Format: (keyword substring in lowercase, inherited kind)
static SECTION_HEADERS: &[(&str, &str)] = &[
    ("lesson", "lesson"),
    ("learned", "lesson"),
    ("learning", "lesson"),
    ("gotcha", "lesson"),
    ("pitfall", "lesson"),
    ("insight", "lesson"),
    ("decision", "decision"),
    ("decided", "decision"),
    ("todo", "todo"),
    ("action item", "todo"),
    ("next step", "todo"),
    ("context", "context"),
    ("status", "context"),
    ("handoff", "session_handoff"),
    ("summary", "context"),
];

/// Return true if the line looks like a section header (ends with `:` and has no
/// indentation, or is written in bold markdown like `**Lessons:**`).
fn is_section_header(line: &str) -> Option<&'static str> {
    let trimmed = line.trim();
    // Must end with ':' or ':*'  (markdown bold close)
    let bare = trimmed
        .trim_start_matches('*')
        .trim_end_matches('*')
        .trim_end_matches(':')
        .trim();
    let lower = bare.to_lowercase();
    for (kw, kind) in SECTION_HEADERS {
        if lower.contains(kw) && trimmed.ends_with(':') || trimmed.ends_with(":**") {
            return Some(kind);
        }
    }
    None
}

/// Strip leading bullet/dash/number from a list item and return the payload.
fn strip_bullet(line: &str) -> Option<&str> {
    let t = line.trim();
    // Markdown list: `- `, `* `, `+ `, `1. `, `•`
    for prefix in &["- ", "* ", "+ ", "• "] {
        if let Some(rest) = t.strip_prefix(prefix) {
            return Some(rest.trim());
        }
    }
    // Numbered list: `1. ` etc.
    if let Some(pos) = t.find(". ") {
        let num_part = &t[..pos];
        if num_part.chars().all(|c| c.is_ascii_digit()) && pos <= 2 {
            return Some(t[pos + 2..].trim());
        }
    }
    None
}

fn curate_conversation(text: &str, session_id: Option<&str>, max_items: usize) -> Vec<MemoryRecord> {
    let mut results: Vec<MemoryRecord> = Vec::new();
    let now = std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .unwrap_or_default()
        .as_secs() as i64;

    let sid_suffix = session_id
        .map(|s| format!("_{}", &s[..s.len().min(8)]))
        .unwrap_or_default();

    // Track the current section context so bullet items inherit the section kind.
    let mut section_kind: Option<&'static str> = None;

    for (idx, line) in text.lines().enumerate() {
        if results.len() >= max_items {
            break;
        }
        let trimmed = line.trim();
        if trimmed.is_empty() {
            // Blank line resets section context after a gap
            // (keep for one blank, reset on two — approximate by counting)
            continue;
        }

        // ── 1. Check for section header ──────────────────────────────────────
        if let Some(kind) = is_section_header(trimmed) {
            section_kind = Some(kind);
            continue;
        }

        // ── 2. Explicit line-prefix markers ─────────────────────────────────
        let mut matched = false;
        if trimmed.len() >= 10 {
            let lower = trimmed.to_lowercase();
            for (marker, kind) in CURATE_MARKERS {
                let marker_lower = marker.to_lowercase();
                if lower.starts_with(&marker_lower) {
                    let content = trimmed[marker.len()..].trim().to_string();
                    if content.len() >= 5 {
                        push_curated(
                            &mut results,
                            kind,
                            &content,
                            &sid_suffix,
                            idx,
                            now,
                        );
                        matched = true;
                        break;
                    }
                }
            }
        }

        // ── 3. Bullet items under a recognised section ──────────────────────
        if !matched {
            if let Some(kind) = section_kind {
                if let Some(payload) = strip_bullet(trimmed) {
                    if payload.len() >= 8 {
                        push_curated(&mut results, kind, payload, &sid_suffix, idx, now);
                    }
                } else if !trimmed.starts_with('[') {
                    // Non-bullet, non-empty line resets the section context
                    section_kind = None;
                }
            }
        }
    }
    results
}

fn push_curated(
    results: &mut Vec<MemoryRecord>,
    kind: &str,
    content: &str,
    sid_suffix: &str,
    idx: usize,
    now: i64,
) {
    let content_slug: String = content
        .chars()
        .take(40)
        .map(|c| if c.is_alphanumeric() { c } else { '_' })
        .collect();
    let key = format!(
        "curated_{}{}_{}{}",
        kind,
        sid_suffix,
        idx,
        &content_slug[..content_slug.len().min(20)]
    );
    results.push(MemoryRecord {
        key,
        kind: kind.to_string(),
        content: content.to_string(),
        tags: vec!["auto_curated".to_string()],
        related_keys: vec![],
        scope: None,
        created_at: now,
        updated_at: now,
        last_accessed_at: now,
        access_count: 0,
        importance: 0.5,
        status: "active".to_string(),
    });
}

#[async_trait]
impl McpTool for SessionCurateTool {
    fn name(&self) -> &'static str {
        "session_curate"
    }
    fn schema(&self) -> ToolSchema {
        ToolSchema {
            name: self.name().into(),
            description: "Extract structured memories from conversation text using rule-based \
                 marker detection (lesson:, decision:, todo:, handoff:, etc.) and \
                 persist them to the memory store. This replaces the PreCompact \
                 shell hook's dependency on claude -p — it works in any frontend \
                 (Cursor, Claude Code, or standalone). \
                 Pass dry_run=true to preview without writing."
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

        let candidates = curate_conversation(&text, session_id.as_deref(), max_items);

        if dry_run || store_opt.is_none() {
            return Ok(ToolResult::json_text(&json!({
                "dry_run": true,
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

/// Jaccard similarity over word-bags (lowercase, ≥3 chars).
fn jaccard_words(a: &str, b: &str) -> f64 {
    let bag = |s: &str| -> std::collections::HashSet<String> {
        s.split(|c: char| !c.is_alphanumeric())
            .map(|w| w.to_lowercase())
            .filter(|w| w.len() >= 3)
            .collect()
    };
    let wa = bag(a);
    let wb = bag(b);
    if wa.is_empty() || wb.is_empty() {
        return 0.0;
    }
    let inter = wa.intersection(&wb).count();
    let union = wa.len() + wb.len() - inter;
    if union == 0 {
        0.0
    } else {
        inter as f64 / union as f64
    }
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
                 Default dry_run=true — always preview before committing."
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
        let mut seen: std::collections::HashSet<(String, String)> = std::collections::HashSet::new();

        for group in by_kind.values() {
            let n = group.len();
            for i in 0..n {
                for j in (i + 1)..n {
                    let ma = group[i];
                    let mb = group[j];
                    let sim = jaccard_words(&ma.content, &mb.content);
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
                    pairs.push(Pair { key_a: ka, key_b: kb, sim, winner });
                }
            }
        }

        // Sort by similarity descending, keep top max_pairs
        pairs.sort_by(|a, b| b.sim.partial_cmp(&a.sim).unwrap_or(std::cmp::Ordering::Equal));
        pairs.truncate(max_pairs);

        if dry_run || pairs.is_empty() {
            let preview: Vec<Value> = pairs
                .iter()
                .map(|p| {
                    let mem_a = memories.iter().find(|m| m.key == p.key_a);
                    let mem_b = memories.iter().find(|m| m.key == p.key_b);
                    json!({
                        "key_a": p.key_a,
                        "key_b": p.key_b,
                        "similarity": (p.sim * 100.0).round() / 100.0,
                        "winner": p.winner,
                        "loser": if p.winner == p.key_a { &p.key_b } else { &p.key_a },
                        "kind": mem_a.or(mem_b).map(|m| m.kind.as_str()).unwrap_or("?"),
                        "content_a": mem_a.map(|m| &m.content[..m.content.len().min(120)]),
                        "content_b": mem_b.map(|m| &m.content[..m.content.len().min(120)]),
                    })
                })
                .collect();
            return Ok(ToolResult::json_text(&json!({
                "dry_run": true,
                "pairs_found": preview.len(),
                "min_similarity": min_sim,
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

            merged.push(json!({
                "winner": p.winner,
                "archived": loser_key,
                "similarity": (p.sim * 100.0).round() / 100.0,
            }));
        }

        Ok(ToolResult::json_text(&json!({
            "dry_run": false,
            "consolidated": merged.len(),
            "errors": errors,
            "pairs": merged,
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
                            let candidate = d.join("crates").join("bridge").join("src").join("hooks");
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
        // Terminal
        let terminal_id = self
            .hub
            .terminal
            .as_ref()
            .map(|t| t.id().to_string())
            .unwrap_or_else(|| "none".to_string());
        let terminal_available = self.hub.terminal.is_some();

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
    if std::env::var("CLAUDE_SESSION_ID").is_ok()
        || std::env::var("CLAUDE_CODE_ENTRYPOINT").is_ok()
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
    "unknown"
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
                let tag_overlap = source
                    .tags
                    .iter()
                    .filter(|t| m.tags.contains(t))
                    .count();
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
    key.split(&['_', '-', '/', '.'][..])
        .next()
        .unwrap_or("")
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
                 Equivalent to Claude Code's Stop hook pipeline."
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
            "export": export_summary
        })))
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
    reg.register(Arc::new(HookStatusTool::new(hub.clone())));
    reg.register(Arc::new(CapabilitiesTool::new(hub.clone())));
    reg.register(Arc::new(MemorySuggestTool::new(hub)));
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
