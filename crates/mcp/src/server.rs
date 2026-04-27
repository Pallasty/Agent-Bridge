//! MCP stdio server main loop.
//!
//! Reads newline-delimited JSON-RPC requests from stdin, dispatches them
//! against the [`ToolRegistry`], and writes responses to stdout.
//! Logs go to stderr (so they never collide with the protocol stream).

use crate::protocol::{
    InitializeResult, McpRequest, McpResponse, ResourcesCapability, ServerCapabilities,
    ServerInfo, ToolsCapability, INTERNAL_ERROR, INVALID_PARAMS, INVALID_REQUEST,
    METHOD_NOT_FOUND, PARSE_ERROR, PROTOCOL_VERSION,
};
use crate::{ToolContext, ToolRegistry};
use ab_store::{MemoryListSort, StateStore};
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
                let resp = McpResponse::error(
                    Value::Null,
                    PARSE_ERROR,
                    format!("invalid json-rpc: {e}"),
                );
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

        let resp = handle(&registry, store.as_deref(), req, server_name, version).await;
        write_response(&mut stdout, &resp).await;
    }

    info!("MCP stdio server stopped (stdin closed)");
}

async fn handle(
    registry: &ToolRegistry,
    store: Option<&dyn StateStore>,
    req: McpRequest,
    server_name: &str,
    version: &str,
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
                    return McpResponse::error(id, INVALID_PARAMS, "missing 'name'");
                }
            };
            let args = params.get("arguments").cloned().unwrap_or(json!({}));

            let tool = match registry.get(&name) {
                Some(t) => t,
                None => {
                    return McpResponse::error(
                        id,
                        METHOD_NOT_FOUND,
                        format!("unknown tool: {name}"),
                    );
                }
            };

            let ctx = ToolContext::default();
            match tool.execute(args, &ctx).await {
                Ok(result) => match serde_json::to_value(result) {
                    Ok(v) => McpResponse::success(id, v),
                    Err(e) => McpResponse::error(id, INTERNAL_ERROR, format!("serialize: {e}")),
                },
                Err(e) => {
                    warn!(tool = %name, error = %e, "tool execution failed");
                    let err_result =
                        crate::ToolResult::error(format!("tool '{name}' failed: {e}"));
                    match serde_json::to_value(err_result) {
                        Ok(v) => McpResponse::success(id, v),
                        Err(e2) => {
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
                "Use memory_get <key> for full content, memory_search for keyword lookup.".to_string(),
                String::new(),
            ];
            // Sort: lessons → decisions → todos → context
            let mut sorted = rows;
            sorted.sort_by_key(|r| match r.kind.as_str() {
                "lesson"   => 0u8,
                "decision" => 1,
                "todo"     => 2,
                _          => 3,
            });
            for r in &sorted {
                let tags = if r.tags.is_empty() {
                    String::new()
                } else {
                    format!(" [{}]", r.tags.join(", "))
                };
                let snippet: String = r.content.chars().take(120).collect();
                let ellipsis = if r.content.chars().count() > 120 { "…" } else { "" };
                lines.push(format!("[{}] {}{}: {}{}", r.kind, r.key, tags, snippet, ellipsis));
            }
            resource_text_response(id, uri, lines.join("\n"))
        }

        "memory://all" => {
            let rows = match store.list_memories(None, MemoryListSort::Recent, 10_000).await {
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
            let rows = match store.list_memories(Some(kind), MemoryListSort::Recent, 500).await {
                Ok(r) => r,
                Err(e) => return McpResponse::error(id, INTERNAL_ERROR, format!("store: {e}")),
            };
            if rows.is_empty() {
                return resource_text_response(id, uri, format!("(no '{}' memories yet)", kind));
            }
            let mut parts = Vec::new();
            for r in &rows {
                parts.push(format!("# {} [{}]\n{}", r.key, r.tags.join(", "), r.content));
            }
            resource_text_response(id, uri, parts.join("\n\n---\n\n"))
        }

        _ => McpResponse::error(id, INVALID_PARAMS, format!("unknown resource uri: {uri}")),
    }
}

fn resource_text_response(id: Value, uri: &str, text: String) -> McpResponse {
    McpResponse::success(id, json!({
        "contents": [{ "uri": uri, "text": text }]
    }))
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
