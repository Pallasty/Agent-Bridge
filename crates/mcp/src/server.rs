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

async fn handle(
    registry: &ToolRegistry,
    store: Option<&dyn StateStore>,
    req: McpRequest,
    server_name: &str,
    version: &str,
    tool_backend_id: Option<&Value>,
) -> McpResponse {
    let id = req.id.clone().unwrap_or(Value::Null);
    debug!(method = %req.method, "dispatch");

    match req.method.as_str() {
        "initialize" => {
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
                    return McpResponse::error(id, INVALID_PARAMS, "missing 'name'");
                }
            };
            let args = params.get("arguments").cloned().unwrap_or(json!({}));

            let tool = match registry.get(&name) {
                Some(t) => t,
                None => {
                    let msg = format!("unknown tool: {name}");
                    record_mcp_tool_failure(store, &name, &msg).await;
                    return McpResponse::error(id, METHOD_NOT_FOUND, msg);
                }
            };

            let ctx = ToolContext::default();
            match tool.execute(args, &ctx).await {
                Ok(mut result) => {
                    if result.is_error {
                        let summary = tool_result_error_summary(&result);
                        record_mcp_tool_failure(store, &name, &summary).await;
                    }
                    if let Some(meta) = tool_backend_id {
                        result.backend_id = Some(meta.clone());
                    }
                    match serde_json::to_value(result) {
                        Ok(v) => McpResponse::success(id, v),
                        Err(e) => {
                            record_mcp_tool_failure(
                                store,
                                &name,
                                &format!("serialize tool result: {e}"),
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
