//! MCP stdio server main loop.
//!
//! Reads newline-delimited JSON-RPC requests from stdin, dispatches them
//! against the [`ToolRegistry`], and writes responses to stdout.
//! Logs go to stderr (so they never collide with the protocol stream).

use crate::protocol::{
    InitializeResult, McpRequest, McpResponse, ServerCapabilities, ServerInfo, ToolsCapability,
    INTERNAL_ERROR, INVALID_PARAMS, INVALID_REQUEST, METHOD_NOT_FOUND, PARSE_ERROR,
    PROTOCOL_VERSION,
};
use crate::{ToolContext, ToolRegistry};
use serde_json::{json, Value};
use tokio::io::{AsyncBufReadExt, AsyncWriteExt, BufReader};
use tracing::{debug, info, warn};

/// Run the stdio MCP server until stdin closes.
pub async fn serve_stdio(registry: ToolRegistry, server_name: &str, version: &str) {
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

        let resp = handle(&registry, req, server_name, version).await;
        write_response(&mut stdout, &resp).await;
    }

    info!("MCP stdio server stopped (stdin closed)");
}

async fn handle(
    registry: &ToolRegistry,
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
            // MCP spec: each tool is {name, description, inputSchema}.
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
                    let err_result = crate::ToolResult::error(format!("tool '{name}' failed: {e}"));
                    match serde_json::to_value(err_result) {
                        Ok(v) => McpResponse::success(id, v),
                        Err(e2) => McpResponse::error(id, INTERNAL_ERROR, format!("serialize: {e2}")),
                    }
                }
            }
        }

        // Resources / prompts not implemented yet; respond predictably so
        // clients can advertise them in capabilities and gracefully degrade.
        "resources/list" => McpResponse::success(id, json!({ "resources": [] })),
        "prompts/list" => McpResponse::success(id, json!({ "prompts": [] })),

        other => McpResponse::error(id, METHOD_NOT_FOUND, format!("unknown method: {other}")),
    }
    .also_log(&req.method, server_name)
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
