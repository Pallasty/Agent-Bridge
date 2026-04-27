//! Built-in MCP tools — wrap the bridge's backend bundle and expose it to
//! Claude Code (or any MCP client) over the `tools/call` channel.

use ab_agent::{GitWorktreeManager, SpawnConfig};
use ab_core::{NotifyEvent, NotifySeverity, NotifySource, PageId, PaneId, Result, SessionId};
use ab_mcp::{McpTool, ToolContext, ToolRegistry, ToolResult, ToolSchema};
use ab_store::{
    CompactPolicy, ImportConflictPolicy, MemoryExportFilter, MemoryListSort, MemoryRecord,
    SessionFilter,
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
                "Capture a full-page PNG screenshot. Default mode writes the PNG \
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
        let inline = args.get("inline").and_then(|v| v.as_bool()).unwrap_or(false);
        if inline {
            let b64 = general_purpose::STANDARD.encode(&png);
            let caption = format!("inline screenshot — {} bytes, image/png", png.len());
            return Ok(ToolResult::image_with_caption(b64, "image/png", caption));
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

/// Resolve which `GitWorktreeManager` a tool call should use. If the caller
/// provided an explicit `repo` argument we bind a fresh manager to it for
/// this call only; otherwise fall back to the bridge-wide default (set by
/// AGENT_BRIDGE_REPO at startup). This lets Claude hop between repos within
/// a single session without restarting the MCP server.
fn resolve_worktree(hub: &Hub, args: &Value) -> std::result::Result<GitWorktreeManager, ToolResult> {
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

pub struct WorktreeListTool { hub: Hub }
impl WorktreeListTool { pub fn new(hub: Hub) -> Self { Self { hub } } }
#[async_trait]
impl McpTool for WorktreeListTool {
    fn name(&self) -> &'static str { "worktree_list" }
    fn schema(&self) -> ToolSchema {
        ToolSchema {
            name: self.name().into(),
            description:
                "List git worktrees of a repository. Pass `repo` to point at any local \
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
        let w = match resolve_worktree(&self.hub, &args) { Ok(w) => w, Err(e) => return Ok(e) };
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
                "Create a new git worktree on a fresh branch. Pass `repo` to target any \
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
        let w = match resolve_worktree(&self.hub, &args) { Ok(w) => w, Err(e) => return Ok(e) };
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
                "Remove a git worktree. Pass `repo` to target any local git checkout; \
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
        let w = match resolve_worktree(&self.hub, &args) { Ok(w) => w, Err(e) => return Ok(e) };
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

pub struct AgentKillTool { hub: Hub }
impl AgentKillTool { pub fn new(hub: Hub) -> Self { Self { hub } } }
#[async_trait]
impl McpTool for AgentKillTool {
    fn name(&self) -> &'static str { "agent_kill" }
    fn schema(&self) -> ToolSchema {
        ToolSchema {
            name: self.name().into(),
            description:
                "Send SIGTERM to a running agent session. Use when a sub-agent has \
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

pub struct AgentSessionListTool { hub: Hub }
impl AgentSessionListTool { pub fn new(hub: Hub) -> Self { Self { hub } } }
#[async_trait]
impl McpTool for AgentSessionListTool {
    fn name(&self) -> &'static str { "agent_session_list" }
    fn schema(&self) -> ToolSchema {
        ToolSchema {
            name: self.name().into(),
            description:
                "List recent agent sessions (default 20, max 1000). Returns one row \
                 per spawn with id / runtime / cwd / started_at / ended_at / exit_code. \
                 All filters are optional and combine with AND: \
                 `runtime_id` exact match, `cwd_prefix` prefix match, \
                 `state` (\"running\"|\"finished\"), `exit_code` exact match \
                 (use negative for signal kills, e.g. -15 = SIGTERM). \
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
        let limit = args.get("limit").and_then(|v| v.as_u64()).unwrap_or(20).min(1000) as u32;
        let filter = SessionFilter {
            runtime_id: args.get("runtime_id").and_then(|v| v.as_str()).map(|s| s.to_string()),
            cwd_prefix: args.get("cwd_prefix").and_then(|v| v.as_str()).map(|s| s.to_string()),
            exited_only: args.get("state").and_then(|v| v.as_str()).and_then(|s| match s {
                "finished" => Some(true),
                "running"  => Some(false),
                _ => None,
            }),
            exit_code: args.get("exit_code").and_then(|v| v.as_i64()).map(|n| n as i32),
        };
        let rows = store.list_sessions(&filter, limit).await?;
        // Strip stdout/stderr to keep the listing compact.
        let summary: Vec<Value> = rows.into_iter().map(|s| json!({
            "id":          s.id.as_str(),
            "runtime_id":  s.runtime_id,
            "cwd":         s.cwd,
            "started_at":  s.started_at,
            "ended_at":    s.ended_at,
            "exit_code":   s.exit_code,
            "running":     s.ended_at.is_none(),
            "stdout_len":  s.stdout.as_ref().map(|x| x.len()).unwrap_or(0),
            "stderr_len":  s.stderr.as_ref().map(|x| x.len()).unwrap_or(0),
        })).collect();
        Ok(ToolResult::json_text(&Value::Array(summary)))
    }
}

pub struct AgentSessionGetTool { hub: Hub }
impl AgentSessionGetTool { pub fn new(hub: Hub) -> Self { Self { hub } } }
#[async_trait]
impl McpTool for AgentSessionGetTool {
    fn name(&self) -> &'static str { "agent_session_get" }
    fn schema(&self) -> ToolSchema {
        ToolSchema {
            name: self.name().into(),
            description:
                "Fetch one agent session row by id, including the full captured \
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
        Ok(ToolResult::json_text(&serde_json::to_value(row).unwrap_or(Value::Null)))
    }
}

pub struct AgentSessionWaitTool { hub: Hub }
impl AgentSessionWaitTool { pub fn new(hub: Hub) -> Self { Self { hub } } }
#[async_trait]
impl McpTool for AgentSessionWaitTool {
    fn name(&self) -> &'static str { "agent_session_wait" }
    fn schema(&self) -> ToolSchema {
        ToolSchema {
            name: self.name().into(),
            description:
                "Block until the given session has finished (ended_at != null) or \
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
            args.get("timeout_secs").and_then(|v| v.as_u64()).unwrap_or(60).min(600),
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

pub struct MemorySaveTool { hub: Hub }
impl MemorySaveTool { pub fn new(hub: Hub) -> Self { Self { hub } } }
#[async_trait]
impl McpTool for MemorySaveTool {
    fn name(&self) -> &'static str { "memory_save" }
    fn schema(&self) -> ToolSchema {
        ToolSchema {
            name: self.name().into(),
            description:
                "Persist one note to agent self-memory (cross-session). Use this to \
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
                    "kind":         { "type": "string", "description": "lesson | decision | todo | context | …" },
                    "content":      { "type": "string", "description": "Markdown / free text. Capped at 256 KiB." },
                    "tags":         { "type": "array", "items": { "type": "string" }, "default": [] },
                    "related_keys": { "type": "array", "items": { "type": "string" }, "default": [] }
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
        let content = args.get("content").and_then(|v| v.as_str()).unwrap_or("").to_string();
        let tags = args.get("tags").and_then(|v| v.as_array())
            .map(|a| a.iter().filter_map(|x| x.as_str().map(|s| s.to_string())).collect())
            .unwrap_or_default();
        let related_keys = args.get("related_keys").and_then(|v| v.as_array())
            .map(|a| a.iter().filter_map(|x| x.as_str().map(|s| s.to_string())).collect())
            .unwrap_or_default();

        let mem = MemoryRecord {
            key: key.clone(), kind, content, tags, related_keys,
            // The store handles all timestamps + access_count itself.
            created_at: 0, updated_at: 0, last_accessed_at: 0, access_count: 0,
        };
        match store.memory_save(&mem).await {
            Ok(()) => Ok(ToolResult::text(format!("saved memory '{key}'"))),
            Err(e) => Ok(ToolResult::error(format!("memory: {e}"))),
        }
    }
}

pub struct MemoryGetTool { hub: Hub }
impl MemoryGetTool { pub fn new(hub: Hub) -> Self { Self { hub } } }
#[async_trait]
impl McpTool for MemoryGetTool {
    fn name(&self) -> &'static str { "memory_get" }
    fn schema(&self) -> ToolSchema {
        ToolSchema {
            name: self.name().into(),
            description:
                "Fetch one memory by exact key. Side effect: bumps the row's \
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
        Ok(ToolResult::json_text(&serde_json::to_value(row).unwrap_or(Value::Null)))
    }
}

pub struct MemorySearchTool { hub: Hub }
impl MemorySearchTool { pub fn new(hub: Hub) -> Self { Self { hub } } }
#[async_trait]
impl McpTool for MemorySearchTool {
    fn name(&self) -> &'static str { "memory_search" }
    fn schema(&self) -> ToolSchema {
        ToolSchema {
            name: self.name().into(),
            description:
                "Substring search over memory keys + content. Optional `tags_any` \
                 narrows to rows tagged with at least one of the listed tags. \
                 Results ranked by composite score: `recency_weight + 0.3 * \
                 ln(1 + access_count)` — most-recent + most-touched first."
                    .into(),
            input_schema: json!({
                "type": "object",
                "properties": {
                    "query":    { "type": "string", "description": "Substring (case-sensitive on most SQLite builds)." },
                    "tags_any": { "type": "array", "items": { "type": "string" }, "default": [] },
                    "limit":    { "type": "integer", "minimum": 1, "maximum": 200, "default": 20 }
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
        let q = args.get("query").and_then(|v| v.as_str()).unwrap_or("").to_string();
        let tags: Vec<String> = args.get("tags_any").and_then(|v| v.as_array())
            .map(|a| a.iter().filter_map(|x| x.as_str().map(|s| s.to_string())).collect())
            .unwrap_or_default();
        let limit = args.get("limit").and_then(|v| v.as_u64()).unwrap_or(20).min(200) as u32;
        let hits = store.memory_search(&q, &tags, limit).await?;
        Ok(ToolResult::json_text(&serde_json::to_value(hits).unwrap_or(Value::Null)))
    }
}

pub struct MemoryListTool { hub: Hub }
impl MemoryListTool { pub fn new(hub: Hub) -> Self { Self { hub } } }
#[async_trait]
impl McpTool for MemoryListTool {
    fn name(&self) -> &'static str { "memory_list" }
    fn schema(&self) -> ToolSchema {
        ToolSchema {
            name: self.name().into(),
            description:
                "List memories, optionally filtered by `kind`, sorted by one of \
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
        let kind = args.get("kind").and_then(|v| v.as_str()).map(|s| s.to_string());
        let sort = match args.get("sort").and_then(|v| v.as_str()).unwrap_or("recent") {
            "frequent" => MemoryListSort::Frequent,
            "newest"   => MemoryListSort::Newest,
            _          => MemoryListSort::Recent,
        };
        let limit = args.get("limit").and_then(|v| v.as_u64()).unwrap_or(20).min(200) as u32;
        let rows = store.list_memories(kind.as_deref(), sort, limit).await?;
        Ok(ToolResult::json_text(&serde_json::to_value(rows).unwrap_or(Value::Null)))
    }
}

pub struct MemoryDeleteTool { hub: Hub }
impl MemoryDeleteTool { pub fn new(hub: Hub) -> Self { Self { hub } } }
#[async_trait]
impl McpTool for MemoryDeleteTool {
    fn name(&self) -> &'static str { "memory_delete" }
    fn schema(&self) -> ToolSchema {
        ToolSchema {
            name: self.name().into(),
            description: "Delete a memory by key. Returns `{deleted: true}` if a row was removed.".into(),
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

pub struct MemoryCompactTool { hub: Hub }
impl MemoryCompactTool { pub fn new(hub: Hub) -> Self { Self { hub } } }
#[async_trait]
impl McpTool for MemoryCompactTool {
    fn name(&self) -> &'static str { "memory_compact" }
    fn schema(&self) -> ToolSchema {
        ToolSchema {
            name: self.name().into(),
            description:
                "Prune low-value memories. A row is removed if EITHER threshold \
                 matches: `min_uses` (access_count strictly less than) OR \
                 `older_than_days` (last_accessed_at older than now - that many \
                 days). Set `dry_run=true` to preview the keys that would be \
                 deleted without actually removing them. Both thresholds default \
                 to none — pass at least one to do anything."
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
        let older_than_secs = args.get("older_than_days").and_then(|v| v.as_i64()).map(|d| d * 86_400);
        let dry_run = args.get("dry_run").and_then(|v| v.as_bool()).unwrap_or(false);

        if min_uses.is_none() && older_than_secs.is_none() {
            return Ok(ToolResult::error(
                "at least one of `min_uses` or `older_than_days` must be set",
            ));
        }
        let policy = CompactPolicy { min_uses, older_than_secs, dry_run };
        let keys = store.memory_compact(policy).await?;
        Ok(ToolResult::json_text(&json!({
            "dry_run": dry_run,
            "removed_count": keys.len(),
            "removed_keys": keys,
        })))
    }
}

// ===========================================================================
//                       memory portability (v0.6)
// ===========================================================================

pub struct MemoryExportTool { hub: Hub }
impl MemoryExportTool { pub fn new(hub: Hub) -> Self { Self { hub } } }
#[async_trait]
impl McpTool for MemoryExportTool {
    fn name(&self) -> &'static str { "memory_export" }
    fn schema(&self) -> ToolSchema {
        ToolSchema {
            name: self.name().into(),
            description:
                "Export memories to a newline-delimited JSON file (one record \
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
            kind: args.get("kind").and_then(|v| v.as_str()).map(|s| s.to_string()),
            tags_any: args.get("tags_any").and_then(|v| v.as_array()).map(|a| {
                a.iter().filter_map(|x| x.as_str().map(|s| s.to_string())).collect()
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

pub struct MemoryImportTool { hub: Hub }
impl MemoryImportTool { pub fn new(hub: Hub) -> Self { Self { hub } } }
#[async_trait]
impl McpTool for MemoryImportTool {
    fn name(&self) -> &'static str { "memory_import" }
    fn schema(&self) -> ToolSchema {
        ToolSchema {
            name: self.name().into(),
            description:
                "Import memories from a JSONL file (the format `memory_export` \
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
        let policy = match args.get("conflict_policy").and_then(|v| v.as_str()).unwrap_or("skip") {
            "overwrite"  => ImportConflictPolicy::Overwrite,
            "newer_wins" => ImportConflictPolicy::NewerWins,
            _            => ImportConflictPolicy::Skip,
        };
        match store.memory_import(&path, policy).await {
            Ok(report) => Ok(ToolResult::json_text(&serde_json::to_value(report).unwrap_or(Value::Null))),
            Err(e) => Ok(ToolResult::error(format!("import: {e}"))),
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
    reg.register(Arc::new(MemoryImportTool::new(hub)));
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
