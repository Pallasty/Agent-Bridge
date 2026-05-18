//! MCP stdio server main loop.
//!
//! Reads newline-delimited JSON-RPC requests from stdin, dispatches them
//! against the [`ToolRegistry`], and writes responses to stdout.
//! Logs go to stderr (so they never collide with the protocol stream).

use crate::protocol::{
    InitializeResult, McpRequest, McpResponse, ResourcesCapability, ServerCapabilities, ServerInfo,
    ToolsCapability, INTERNAL_ERROR, INVALID_PARAMS, INVALID_REQUEST, METHOD_NOT_FOUND,
    PARSE_ERROR, PROTOCOL_VERSION,
};
use crate::{ContentBlock, ToolContext, ToolRegistry, ToolResult};
use ab_store::{prioritize_session_handoff, MemoryListSort, StateStore};
use serde_json::{json, Value};
use std::sync::Arc;
use tokio::io::{AsyncBufReadExt, AsyncWriteExt, BufReader};
use tracing::{debug, info, warn};

/// Run the stdio MCP server until stdin closes.
///
/// `store` is optional; when present, memory resources (`memory://…`) are
/// advertised and readable. Pass `None` when no state store is available.
pub async fn serve_stdio(
    registry: ToolRegistry,
    store: Option<Arc<dyn StateStore>>,
    server_name: &str,
    version: &str,
    tool_backend_id: Option<Value>,
) {
    info!(server = server_name, "MCP stdio server starting");
    let mut stdin = BufReader::new(tokio::io::stdin()).lines();
    let mut stdout = tokio::io::stdout();
    let mut telemetry = ConnectionTelemetry::from_env();

    while let Ok(Some(line)) = stdin.next_line().await {
        if line.trim().is_empty() {
            continue;
        }

        let req = match serde_json::from_str::<McpRequest>(&line) {
            Ok(r) => r,
            Err(e) => {
                let resp =
                    McpResponse::error(Value::Null, PARSE_ERROR, format!("invalid json-rpc: {e}"));
                write_response(&mut stdout, &resp).await;
                continue;
            }
        };

        if req.jsonrpc != "2.0" {
            if let Some(id) = req.id.clone() {
                let resp = McpResponse::error(id, INVALID_REQUEST, "jsonrpc must be '2.0'");
                write_response(&mut stdout, &resp).await;
            }
            continue;
        }

        // Notifications (no id) → handle silently, never respond.
        if req.id.is_none() {
            debug!(method = %req.method, "received notification");
            continue;
        }

        let resp = handle(
            &registry,
            store.as_deref(),
            req,
            server_name,
            version,
            tool_backend_id.as_ref(),
            &mut telemetry,
        )
        .await;
        write_response(&mut stdout, &resp).await;
    }

    info!("MCP stdio server stopped (stdin closed)");
}

fn tool_result_error_summary(result: &ToolResult) -> String {
    let mut parts: Vec<&str> = Vec::new();
    for block in &result.content {
        match block {
            ContentBlock::Text { text } => parts.push(text.as_str()),
            ContentBlock::Image { .. } => parts.push("(image)"),
        }
    }
    let joined = parts.join(" ").trim().to_string();
    if joined.is_empty() {
        "tool returned isError with no text content".to_string()
    } else {
        joined
    }
}

async fn record_mcp_tool_failure(store: Option<&dyn StateStore>, tool_name: &str, message: &str) {
    let Some(s) = store else {
        return;
    };
    if let Err(e) = s.record_mcp_tool_error(tool_name, message).await {
        warn!(tool = %tool_name, error = %e, "record_mcp_tool_error failed");
    }
}

#[derive(Debug, Clone)]
struct ConnectionTelemetry {
    client_name: Option<String>,
    profile: String,
    source: String,
    model: Option<String>,
    model_reasoning_effort: Option<String>,
}

impl ConnectionTelemetry {
    fn from_env() -> Self {
        let client_name = std::env::var("AGENT_BRIDGE_CLIENT_NAME")
            .ok()
            .and_then(nonempty_string);
        let profile = mcp_profile_label_from_env().to_string();
        let source = classify_mcp_source_from_client(client_name.as_deref())
            .or_else(mcp_source_from_env)
            .unwrap_or("other")
            .to_string();
        let model = std::env::var("AGENT_BRIDGE_MODEL")
            .ok()
            .and_then(nonempty_string);
        let model_reasoning_effort = std::env::var("AGENT_BRIDGE_MODEL_REASONING_EFFORT")
            .ok()
            .and_then(nonempty_string);
        Self {
            client_name,
            profile,
            source,
            model,
            model_reasoning_effort,
        }
    }

    fn observe_initialize_params(&mut self, params: Option<&Value>) {
        if let Some(name) = params
            .and_then(|p| p.get("clientInfo"))
            .and_then(|c| c.get("name"))
            .and_then(|v| v.as_str())
            .and_then(nonempty_str)
        {
            self.client_name = Some(name.to_string());
        }
        self.profile = mcp_profile_label_from_env().to_string();
        self.source = classify_mcp_source_from_client(self.client_name.as_deref())
            .or_else(mcp_source_from_env)
            .unwrap_or("other")
            .to_string();
        self.model = std::env::var("AGENT_BRIDGE_MODEL")
            .ok()
            .and_then(nonempty_string);
        self.model_reasoning_effort = std::env::var("AGENT_BRIDGE_MODEL_REASONING_EFFORT")
            .ok()
            .and_then(nonempty_string);
    }
}

fn nonempty_string(value: String) -> Option<String> {
    let trimmed = value.trim();
    if trimmed.is_empty() {
        None
    } else {
        Some(trimmed.to_string())
    }
}

fn nonempty_str(value: &str) -> Option<&str> {
    let trimmed = value.trim();
    if trimmed.is_empty() {
        None
    } else {
        Some(trimmed)
    }
}

fn mcp_profile_label_from_env() -> &'static str {
    let toolset = std::env::var("AGENT_BRIDGE_TOOLSET").ok();
    let profile = std::env::var("AGENT_BRIDGE_TOOL_PROFILE").ok();
    mcp_profile_label_from_values(toolset.as_deref(), profile.as_deref())
}

fn mcp_profile_label_from_values(toolset: Option<&str>, profile: Option<&str>) -> &'static str {
    match toolset.map(normalize_mcp_env_value).as_deref() {
        Some("codex-essential") | Some("codex") | Some("gemini-lean") | Some("gemini") => {
            "essential"
        }
        Some("all-dev") | Some("dev") | Some("full-dev") => "all",
        Some("claude-standard")
        | Some("claude-code")
        | Some("claude")
        | Some("hook-lifecycle")
        | Some("hooks")
        | Some("hook")
        | Some("lifecycle") => "standard",
        _ => mcp_profile_label_from_value(profile),
    }
}

fn mcp_profile_label_from_value(value: Option<&str>) -> &'static str {
    match value
        .unwrap_or("standard")
        .trim()
        .to_ascii_lowercase()
        .as_str()
    {
        "minimal" | "essential" => "essential",
        "all" | "full" => "all",
        _ => "standard",
    }
}

fn normalize_mcp_env_value(value: &str) -> String {
    value
        .trim()
        .to_ascii_lowercase()
        .replace('_', "-")
        .replace(' ', "-")
}

fn mcp_source_from_env() -> Option<&'static str> {
    if let Ok(value) = std::env::var("AGENT_BRIDGE_MCP_SOURCE") {
        if let Some(source) = normalize_mcp_source(&value) {
            return Some(source);
        }
    }
    if std::env::vars().any(|(k, _)| k.starts_with("CODEX_")) {
        return Some("codex");
    }
    None
}

fn classify_mcp_source_from_client(client_name: Option<&str>) -> Option<&'static str> {
    let name = client_name?.trim().to_ascii_lowercase();
    if name.is_empty() {
        return None;
    }
    if name.contains("hook")
        || name.contains("precompact")
        || name.contains("pre-compact")
        || name.contains("session-end")
        || name.contains("sessionend")
        || name.contains("stop")
    {
        return Some("hook");
    }
    if name.contains("codex") || name.contains("openai") {
        return Some("codex");
    }
    if name.contains("claude") {
        return Some("claude");
    }
    if name.contains("gemini") {
        return Some("gemini");
    }
    if name.contains("audit") || name.contains("smoke") || name.contains("test") {
        return Some("manual");
    }
    normalize_mcp_source(&name)
}

fn normalize_mcp_source(value: &str) -> Option<&'static str> {
    match value.trim().to_ascii_lowercase().as_str() {
        "codex" => Some("codex"),
        "hook" | "hooks" | "lifecycle" => Some("hook"),
        "claude" | "claude-code" => Some("claude"),
        "gemini" => Some("gemini"),
        "manual" | "smoke" | "audit" | "test" => Some("manual"),
        "legacy" => Some("legacy"),
        "other" => Some("other"),
        _ => None,
    }
}

/// v17 telemetry — record every `tools/call` (success + failure) with timing
/// and size. Fire-and-forget; failures are logged but do not fail the call.
async fn record_mcp_tool_call_telemetry(
    store: Option<&dyn StateStore>,
    tool_name: &str,
    call_start: &std::time::Instant,
    ok: bool,
    args_size: Option<u32>,
    result_size: Option<u32>,
    telemetry: &ConnectionTelemetry,
) {
    let Some(s) = store else {
        return;
    };
    let duration_ms = call_start.elapsed().as_millis().min(u32::MAX as u128) as u32;
    if let Err(e) = s
        .record_mcp_tool_call(
            tool_name,
            duration_ms,
            ok,
            args_size,
            result_size,
            telemetry.client_name.clone(),
            Some(telemetry.profile.clone()),
            Some(telemetry.source.clone()),
            telemetry.model.clone(),
            telemetry.model_reasoning_effort.clone(),
        )
        .await
    {
        warn!(tool = %tool_name, error = %e, "record_mcp_tool_call failed");
    }
}

async fn handle(
    registry: &ToolRegistry,
    store: Option<&dyn StateStore>,
    req: McpRequest,
    server_name: &str,
    version: &str,
    tool_backend_id: Option<&Value>,
    telemetry: &mut ConnectionTelemetry,
) -> McpResponse {
    let id = req.id.clone().unwrap_or(Value::Null);
    debug!(method = %req.method, "dispatch");

    match req.method.as_str() {
        "initialize" => {
            telemetry.observe_initialize_params(req.params.as_ref());
            let result = InitializeResult {
                protocol_version: PROTOCOL_VERSION.into(),
                capabilities: ServerCapabilities {
                    tools: Some(ToolsCapability { list_changed: None }),
                    resources: store.map(|_| ResourcesCapability::default()),
                },
                server_info: ServerInfo {
                    name: server_name.into(),
                    version: version.into(),
                },
            };
            match serde_json::to_value(result) {
                Ok(v) => McpResponse::success(id, v),
                Err(e) => McpResponse::error(id, INTERNAL_ERROR, format!("serialize: {e}")),
            }
        }

        "ping" => McpResponse::success(id, json!({})),

        "tools/list" => {
            let tools = registry.list();
            let tools_json: Vec<Value> = tools
                .iter()
                .map(|t| {
                    json!({
                        "name": t.name,
                        "description": t.description,
                        "inputSchema": t.input_schema,
                    })
                })
                .collect();
            McpResponse::success(id, json!({ "tools": tools_json }))
        }

        "tools/call" => {
            let call_start = std::time::Instant::now();
            let params = req.params.unwrap_or(Value::Null);
            let name = match params.get("name").and_then(|v| v.as_str()) {
                Some(n) => n.to_string(),
                None => {
                    record_mcp_tool_failure(
                        store,
                        "<missing>",
                        "missing 'name' in tools/call params",
                    )
                    .await;
                    record_mcp_tool_call_telemetry(
                        store, "<missing>", &call_start, false, None, None, telemetry,
                    )
                    .await;
                    return McpResponse::error(id, INVALID_PARAMS, "missing 'name'");
                }
            };
            let args = params.get("arguments").cloned().unwrap_or(json!({}));
            let args_size = serde_json::to_string(&args).map(|s| s.len() as u32).ok();

            let tool = match registry.get(&name) {
                Some(t) => t,
                None => {
                    let msg = format!("unknown tool: {name}");
                    record_mcp_tool_failure(store, &name, &msg).await;
                    record_mcp_tool_call_telemetry(
                        store, &name, &call_start, false, args_size, None, telemetry,
                    )
                    .await;
                    return McpResponse::error(id, METHOD_NOT_FOUND, msg);
                }
            };

            let ctx = ToolContext::default();
            match tool.execute(args, &ctx).await {
                Ok(mut result) => {
                    let ok = !result.is_error;
                    if result.is_error {
                        let summary = tool_result_error_summary(&result);
                        record_mcp_tool_failure(store, &name, &summary).await;
                    }
                    if let Some(meta) = tool_backend_id {
                        result.backend_id = Some(meta.clone());
                    }
                    match serde_json::to_value(result) {
                        Ok(v) => {
                            let result_size =
                                serde_json::to_string(&v).map(|s| s.len() as u32).ok();
                            record_mcp_tool_call_telemetry(
                                store,
                                &name,
                                &call_start,
                                ok,
                                args_size,
                                result_size,
                                telemetry,
                            )
                            .await;
                            McpResponse::success(id, v)
                        }
                        Err(e) => {
                            record_mcp_tool_failure(
                                store,
                                &name,
                                &format!("serialize tool result: {e}"),
                            )
                            .await;
                            record_mcp_tool_call_telemetry(
                                store, &name, &call_start, false, args_size, None, telemetry,
                            )
                            .await;
                            McpResponse::error(id, INTERNAL_ERROR, format!("serialize: {e}"))
                        }
                    }
                }
                Err(e) => {
                    warn!(tool = %name, error = %e, "tool execution failed");
                    record_mcp_tool_failure(store, &name, &format!("tool '{name}' failed: {e}"))
                        .await;
                    record_mcp_tool_call_telemetry(
                        store, &name, &call_start, false, args_size, None, telemetry,
                    )
                    .await;
                    let mut err_result =
                        crate::ToolResult::error(format!("tool '{name}' failed: {e}"));
                    if let Some(meta) = tool_backend_id {
                        err_result.backend_id = Some(meta.clone());
                    }
                    match serde_json::to_value(err_result) {
                        Ok(v) => McpResponse::success(id, v),
                        Err(e2) => {
                            record_mcp_tool_failure(
                                store,
                                &name,
                                &format!("serialize error ToolResult: {e2}"),
                            )
                            .await;
                            McpResponse::error(id, INTERNAL_ERROR, format!("serialize: {e2}"))
                        }
                    }
                }
            }
        }

        "resources/list" => {
            if store.is_none() {
                return McpResponse::success(id, json!({ "resources": [] }));
            }
            McpResponse::success(id, json!({
                "resources": [
                    {
                        "uri": "memory://index",
                        "name": "Memory Index",
                        "description": "Compact index of all self-memory records (key, kind, tags, 120-char snippet). Load at session start to orient yourself.",
                        "mimeType": "text/plain"
                    },
                    {
                        "uri": "memory://lessons",
                        "name": "Lessons",
                        "description": "Full content of all 'lesson' memory records.",
                        "mimeType": "text/plain"
                    },
                    {
                        "uri": "memory://decisions",
                        "name": "Decisions",
                        "description": "Full content of all 'decision' memory records.",
                        "mimeType": "text/plain"
                    },
                    {
                        "uri": "memory://todos",
                        "name": "TODOs",
                        "description": "Full content of all 'todo' memory records.",
                        "mimeType": "text/plain"
                    },
                    {
                        "uri": "memory://all",
                        "name": "All Memories (JSONL)",
                        "description": "Complete memory export, one JSON object per line.",
                        "mimeType": "application/x-ndjson"
                    },
                    {
                        "uri": "agent-bridge://session/bootstrap",
                        "name": "Session Bootstrap",
                        "description": "Compact session bootstrap block: top scoped memories for the current working directory (importance-ranked; session_handoff first). Equivalent to calling session_bootstrap() tool. Pull this resource at session start when hooks are unavailable.",
                        "mimeType": "text/plain"
                    }
                ]
            }))
        }

        "resources/read" => {
            let uri = req.params
                .as_ref()
                .and_then(|p| p.get("uri"))
                .and_then(|v| v.as_str())
                .unwrap_or("");

            match store {
                None => McpResponse::error(id, INVALID_PARAMS, "no store available"),
                Some(s) => handle_resource_read(id, s, uri).await,
            }
        }

        "prompts/list" => McpResponse::success(id, json!({ "prompts": [] })),

        other => McpResponse::error(id, METHOD_NOT_FOUND, format!("unknown method: {other}")),
    }
    .also_log(&req.method, server_name)
}

async fn handle_resource_read(id: Value, store: &dyn StateStore, uri: &str) -> McpResponse {
    match uri {
        "memory://index" => {
            let rows = match store.list_memories(None, MemoryListSort::Recent, 500).await {
                Ok(r) => r,
                Err(e) => return McpResponse::error(id, INTERNAL_ERROR, format!("store: {e}")),
            };
            let mut lines = vec![
                "Agent-Bridge Self-Memory Index".to_string(),
                "Use memory_get <key> for full content, memory_search for keyword lookup."
                    .to_string(),
                String::new(),
            ];
            // Sort: session handoff → lessons → decisions → todos → other
            let mut sorted = rows;
            sorted.sort_by_key(|r| match r.kind.as_str() {
                "session_handoff" => 0u8,
                "lesson" => 1,
                "decision" => 2,
                "todo" => 3,
                _ => 4,
            });
            for r in &sorted {
                let tags = if r.tags.is_empty() {
                    String::new()
                } else {
                    format!(" [{}]", r.tags.join(", "))
                };
                let snippet: String = r.content.chars().take(120).collect();
                let ellipsis = if r.content.chars().count() > 120 {
                    "…"
                } else {
                    ""
                };
                lines.push(format!(
                    "[{}] {}{}: {}{}",
                    r.kind, r.key, tags, snippet, ellipsis
                ));
            }
            resource_text_response(id, uri, lines.join("\n"))
        }

        "memory://all" => {
            let rows = match store
                .list_memories(None, MemoryListSort::Recent, 10_000)
                .await
            {
                Ok(r) => r,
                Err(e) => return McpResponse::error(id, INTERNAL_ERROR, format!("store: {e}")),
            };
            let jsonl: Vec<String> = rows
                .iter()
                .filter_map(|r| serde_json::to_string(r).ok())
                .collect();
            resource_text_response(id, uri, jsonl.join("\n"))
        }

        kind_uri if kind_uri.starts_with("memory://") => {
            let kind = &kind_uri["memory://".len()..];
            let rows = match store
                .list_memories(Some(kind), MemoryListSort::Recent, 500)
                .await
            {
                Ok(r) => r,
                Err(e) => return McpResponse::error(id, INTERNAL_ERROR, format!("store: {e}")),
            };
            if rows.is_empty() {
                return resource_text_response(id, uri, format!("(no '{}' memories yet)", kind));
            }
            let mut parts = Vec::new();
            for r in &rows {
                parts.push(format!(
                    "# {} [{}]\n{}",
                    r.key,
                    r.tags.join(", "),
                    r.content
                ));
            }
            resource_text_response(id, uri, parts.join("\n\n---\n\n"))
        }

        "agent-bridge://session/bootstrap" => {
            let cwd = std::env::current_dir()
                .map(|p| p.display().to_string())
                .unwrap_or_else(|_| "/".to_string());
            let rows = match store
                .list_memories_in_scope(&cwd, None, MemoryListSort::ByImportance, 60)
                .await
            {
                Ok(r) => r,
                Err(e) => return McpResponse::error(id, INTERNAL_ERROR, format!("store: {e}")),
            };
            let rows: Vec<_> = rows.into_iter().filter(|r| r.status == "active").collect();
            let rows = prioritize_session_handoff(rows);
            let mut lines = vec![
                format!("=== Agent-Bridge Session Bootstrap (scope: {cwd}) ==="),
                "Use memory_get <key> for full content, memory_search for lookup.".to_string(),
                String::new(),
            ];
            for r in &rows {
                let tags = if r.tags.is_empty() {
                    String::new()
                } else {
                    format!(" [{}]", r.tags.join(", "))
                };
                let snippet: String = r.content.chars().take(120).collect();
                let ellipsis = if r.content.chars().count() > 120 {
                    "…"
                } else {
                    ""
                };
                lines.push(format!(
                    "[{}] {}{}: {}{}",
                    r.kind, r.key, tags, snippet, ellipsis
                ));
            }
            lines.push("=== End Bootstrap ===".to_string());
            lines.push(String::new());
            lines.push(
                "=== Session Lifecycle Reminder ===\n\
                 Before this session ends, call:\n\
                 1. session_curate(conversation_text=<summary>) — save lessons; \
                    use handoff: lines for next-session continuity\n\
                 2. session_finalize() — compact + optional export\n\
                 =================================="
                    .to_string(),
            );
            resource_text_response(id, uri, lines.join("\n"))
        }

        _ => McpResponse::error(id, INVALID_PARAMS, format!("unknown resource uri: {uri}")),
    }
}

fn resource_text_response(id: Value, uri: &str, text: String) -> McpResponse {
    McpResponse::success(
        id,
        json!({
            "contents": [{ "uri": uri, "text": text }]
        }),
    )
}

trait LogResponse {
    fn also_log(self, method: &str, server: &str) -> Self;
}
impl LogResponse for McpResponse {
    fn also_log(self, method: &str, server: &str) -> Self {
        if let Some(err) = &self.error {
            warn!(server, method, code = err.code, msg = %err.message, "mcp error");
        } else {
            debug!(server, method, "mcp ok");
        }
        self
    }
}

async fn write_response(stdout: &mut tokio::io::Stdout, resp: &McpResponse) {
    let mut bytes = match serde_json::to_vec(resp) {
        Ok(b) => b,
        Err(e) => {
            warn!(error = %e, "failed to serialise response");
            return;
        }
    };
    bytes.push(b'\n');
    if let Err(e) = stdout.write_all(&bytes).await {
        warn!(error = %e, "stdout write failed");
        return;
    }
    let _ = stdout.flush().await;
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn mcp_source_classifier_identifies_common_clients() {
        assert_eq!(
            classify_mcp_source_from_client(Some("ab-session-end-hook")),
            Some("hook")
        );
        assert_eq!(
            classify_mcp_source_from_client(Some("OpenAI Codex")),
            Some("codex")
        );
        assert_eq!(
            classify_mcp_source_from_client(Some("Claude Code")),
            Some("claude")
        );
        assert_eq!(
            classify_mcp_source_from_client(Some("agent-bridge-audit")),
            Some("manual")
        );
        assert_eq!(
            classify_mcp_source_from_client(Some("unknown-client")),
            None
        );
    }

    #[test]
    fn mcp_profile_label_normalizes_env_values() {
        assert_eq!(mcp_profile_label_from_value(None), "standard");
        assert_eq!(mcp_profile_label_from_value(Some("minimal")), "essential");
        assert_eq!(mcp_profile_label_from_value(Some("essential")), "essential");
        assert_eq!(mcp_profile_label_from_value(Some("all")), "all");
        assert_eq!(mcp_profile_label_from_value(Some("full")), "all");
        assert_eq!(mcp_profile_label_from_value(Some("weird")), "standard");
    }

    #[test]
    fn mcp_profile_label_honors_toolset_before_profile() {
        assert_eq!(
            mcp_profile_label_from_values(Some("codex-essential"), Some("all")),
            "essential"
        );
        assert_eq!(
            mcp_profile_label_from_values(Some("all_dev"), Some("essential")),
            "all"
        );
        assert_eq!(
            mcp_profile_label_from_values(Some("hook-lifecycle"), None),
            "standard"
        );
        assert_eq!(
            mcp_profile_label_from_values(Some("unknown"), Some("all")),
            "all"
        );
    }
}
