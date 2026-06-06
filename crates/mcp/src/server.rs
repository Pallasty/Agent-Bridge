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
use ab_core::SessionId;
use ab_store::{prioritize_session_handoff, MemoryListSort, StateStore};
use serde_json::{json, Value};
use std::collections::HashMap;
use std::sync::{Arc, Mutex};
use std::time::Duration;
use tokio::io::{AsyncBufReadExt, AsyncWriteExt, BufReader};
use tokio::sync::mpsc;
use tokio::task::AbortHandle;
use tracing::{debug, info, warn};

/// Per-call backstop deadline for a spawned `tools/call` task. Layer 3 runs each
/// tools/call concurrently, so a hung tool no longer blocks other calls — but an
/// unbounded-lived hung task would still leak threads/handles, so every call is
/// also time-bounded. The default is generous (600s) so only a genuinely hung
/// backend is ever hit, never a legit long call; tune via
/// AGENT_BRIDGE_MCP_CALL_DEADLINE_SECS (0/invalid → default).
fn mcp_call_deadline() -> Duration {
    std::env::var("AGENT_BRIDGE_MCP_CALL_DEADLINE_SECS")
        .ok()
        .and_then(|s| s.trim().parse::<u64>().ok())
        .filter(|n| *n > 0)
        .map(Duration::from_secs)
        .unwrap_or(Duration::from_secs(600))
}

/// Tools that legitimately BLOCK on a human (solving a CAPTCHA, approving a card)
/// or on a long external wait advertise their own (generous, self-cleaning) inner
/// timeout — e.g. browser_pause_for_human clamps to 30 min. The ordinary 600s
/// backstop would truncate that window and report a false "backend hung", so these
/// get a much larger backstop (default 2400s > the 30-min inner max) instead.
fn is_human_blocking_tool(name: &str) -> bool {
    matches!(
        name,
        "browser_pause_for_human" | "present_await_decision" | "agent_session_wait"
    )
}

fn mcp_human_deadline() -> Duration {
    std::env::var("AGENT_BRIDGE_MCP_HUMAN_DEADLINE_SECS")
        .ok()
        .and_then(|s| s.trim().parse::<u64>().ok())
        .filter(|n| *n > 0)
        .map(Duration::from_secs)
        .unwrap_or(Duration::from_secs(2400))
}

/// Backstop deadline for a tools/call, picked by tool name: human-blocking tools
/// get the larger window so their legit long wait is not truncated.
fn call_deadline_for(tool_name: &str) -> Duration {
    if is_human_blocking_tool(tool_name) {
        mcp_human_deadline()
    } else {
        mcp_call_deadline()
    }
}

fn nonempty_json_str(value: Option<&Value>) -> Option<String> {
    value
        .and_then(|v| v.as_str())
        .map(str::trim)
        .filter(|s| !s.is_empty())
        .map(str::to_string)
}

fn session_id_from_object(value: Option<&Value>) -> Option<String> {
    let object = value?;
    nonempty_json_str(object.get("session_id"))
        .or_else(|| nonempty_json_str(object.get("sessionId")))
        .or_else(|| {
            object
                .get("x-codex-turn-metadata")
                .and_then(|v| session_id_from_object(Some(v)))
        })
        .or_else(|| nonempty_json_str(object.get("thread_id")))
        .or_else(|| nonempty_json_str(object.get("threadId")))
}

fn session_id_from_env() -> Option<String> {
    [
        "AGENT_BRIDGE_SESSION_ID",
        "CLAUDE_CODE_SESSION_ID",
        "CLAUDE_SESSION_ID",
        "CODEX_COMPANION_SESSION_ID",
        "CODEX_SESSION_ID",
        "MCP_SESSION_ID",
    ]
    .into_iter()
    .find_map(|key| {
        std::env::var(key)
            .ok()
            .map(|s| s.trim().to_string())
            .filter(|s| !s.is_empty())
    })
}

fn tool_context_from_call(params: &Value, args: &Value) -> ToolContext {
    let meta = params.get("_meta").or_else(|| args.get("_meta"));
    let raw_session_id = session_id_from_object(meta)
        .or_else(|| session_id_from_object(Some(args)))
        .or_else(|| session_id_from_object(Some(params)))
        .or_else(session_id_from_env);

    let mut extras = HashMap::new();
    if let Some(meta) = meta.cloned() {
        extras.insert("_meta".to_string(), meta);
    }

    ToolContext {
        session_id: raw_session_id.map(SessionId::from_raw),
        extras,
    }
}

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

    // Three tasks share the protocol stream so one hung tool can't wedge the whole
    // server (Layer 3): a reader pumps stdin lines into `line_rx`; a writer owns
    // stdout and drains `resp_rx` (serializing every response so concurrent tasks
    // never interleave); and the dispatch loop in between runs each tools/call
    // concurrently. stdin/stdout sit behind channels so the loop is unit-testable.
    let (line_tx, line_rx) = mpsc::unbounded_channel::<String>();
    let (resp_tx, mut resp_rx) = mpsc::unbounded_channel::<McpResponse>();

    tokio::spawn(async move {
        let mut stdin = BufReader::new(tokio::io::stdin()).lines();
        while let Ok(Some(line)) = stdin.next_line().await {
            if line_tx.send(line).is_err() {
                break;
            }
        }
    });

    let writer = tokio::spawn(async move {
        let mut stdout = tokio::io::stdout();
        while let Some(resp) = resp_rx.recv().await {
            write_response(&mut stdout, &resp).await;
        }
    });

    run_dispatch_loop(
        line_rx,
        resp_tx,
        registry,
        store,
        server_name.to_string(),
        version.to_string(),
        tool_backend_id,
    )
    .await;

    // Give the writer a brief grace to flush any just-completed responses, but do
    // NOT block on it indefinitely: a still-running (e.g. hung) tools/call task
    // holds a sender clone, so an unbounded `writer.await` would keep this process
    // alive until that task's deadline (up to 600s) after the client already left.
    let _ = tokio::time::timeout(Duration::from_secs(5), writer).await;
    info!("MCP stdio server stopped (stdin closed)");
}

/// The concurrent dispatch loop, isolated from stdin/stdout (driven by channels)
/// so it can be unit-tested. Fast methods (initialize/ping/tools/list/resources)
/// run inline to keep telemetry mutation sequential; `tools/call` — the only
/// method that can hang — is spawned so the loop keeps reading (other calls
/// proceed, `notifications/cancelled` is honoured, a hung tool never wedges the
/// server). Each spawned call is also backstop-bounded by `mcp_call_deadline`.
async fn run_dispatch_loop(
    mut line_rx: mpsc::UnboundedReceiver<String>,
    resp_tx: mpsc::UnboundedSender<McpResponse>,
    registry: ToolRegistry,
    store: Option<Arc<dyn StateStore>>,
    server_name: String,
    version: String,
    tool_backend_id: Option<Value>,
) {
    let mut telemetry = ConnectionTelemetry::from_env();
    let registry = Arc::new(registry);
    // request-id (as JSON string) -> AbortHandle of the in-flight tools/call task,
    // so a notifications/cancelled can abort it. Pruned of finished entries on each
    // insert so a fast call that completes before we record it can't leak.
    let inflight: Arc<Mutex<HashMap<String, AbortHandle>>> = Arc::new(Mutex::new(HashMap::new()));

    while let Some(line) = line_rx.recv().await {
        if line.trim().is_empty() {
            continue;
        }

        let req = match serde_json::from_str::<McpRequest>(&line) {
            Ok(r) => r,
            Err(e) => {
                let _ = resp_tx.send(McpResponse::error(
                    Value::Null,
                    PARSE_ERROR,
                    format!("invalid json-rpc: {e}"),
                ));
                continue;
            }
        };

        if req.jsonrpc != "2.0" {
            if let Some(id) = req.id.clone() {
                let _ =
                    resp_tx.send(McpResponse::error(id, INVALID_REQUEST, "jsonrpc must be '2.0'"));
            }
            continue;
        }

        // Notifications (no id) → never respond. Honour cancellation: abort the
        // in-flight tools/call task whose requestId matches.
        if req.id.is_none() {
            if req.method == "notifications/cancelled" {
                if let Some(rid) = req.params.as_ref().and_then(|p| p.get("requestId")) {
                    let key = rid.to_string();
                    let handle = inflight.lock().unwrap().remove(&key);
                    if let Some(h) = handle {
                        warn!(request_id = %key, "client cancelled in-flight tool call — aborting");
                        h.abort();
                    }
                }
            } else {
                debug!(method = %req.method, "received notification");
            }
            continue;
        }

        // tools/call is the only method that can hang (it runs tool.execute). Run it
        // in its own task + backstop deadline so the loop keeps reading the next
        // request. Everything else is fast → handle inline.
        if req.method == "tools/call" {
            let req_id = req.id.clone().unwrap_or(Value::Null);
            let map_key = req_id.to_string();
            let sup_key = req_id.to_string();
            let req_id_deadline = req_id.clone();
            let req_id_panic = req_id;
            // Pick the backstop by tool name so a human-in-the-loop wait (CAPTCHA /
            // approval) is not truncated by the ordinary 600s deadline.
            let tool_name = req
                .params
                .as_ref()
                .and_then(|p| p.get("name"))
                .and_then(|v| v.as_str())
                .unwrap_or("")
                .to_string();
            let deadline = call_deadline_for(&tool_name);
            let reg = registry.clone();
            let st = store.clone();
            let mut tel = telemetry.clone();
            let sn = server_name.clone();
            let ver = version.clone();
            let tbid = tool_backend_id.clone();
            let out = resp_tx.clone();
            let inflight_sup = inflight.clone();

            // Hold the inflight lock across BOTH spawns and the insert so the supervisor
            // (which removes the entry) cannot run its removal before we record the
            // handle — closing the fast-call insert-vs-self-remove race, and ensuring a
            // notifications/cancelled arriving in this window still finds the entry. No
            // .await happens under the lock (tokio::spawn is synchronous).
            let mut map = inflight.lock().unwrap();
            map.retain(|_, h| !h.is_finished());

            // work task: run the tool under the (per-tool) backstop deadline.
            let work = tokio::spawn(async move {
                match tokio::time::timeout(
                    deadline,
                    handle(&reg, st.as_deref(), req, &sn, &ver, tbid.as_ref(), &mut tel),
                )
                .await
                {
                    Ok(r) => r,
                    Err(_) => {
                        warn!(
                            deadline_secs = deadline.as_secs(),
                            "tool call exceeded server deadline — cancelled; server stayed responsive"
                        );
                        McpResponse::error(
                            req_id_deadline,
                            INTERNAL_ERROR,
                            format!(
                                "tool call exceeded the server deadline ({}s) and was cancelled; \
                                 the backend likely hung (e.g. a wedged browser/CDP connection). \
                                 The MCP server stayed responsive — retry, or raise \
                                 AGENT_BRIDGE_MCP_CALL_DEADLINE_SECS for genuinely long calls.",
                                deadline.as_secs()
                            ),
                        )
                    }
                }
            });
            let abort = work.abort_handle();
            let st_sup = store.clone();
            let tool_name_sup = tool_name;

            // supervisor: await the work task so a PANIC inside tool.execute() still
            // yields an error response instead of a silent never-returns hang (which
            // would re-create the very wedge Layer 3 removes), and a cancellation
            // (abort) stays silent. Always removes the inflight entry.
            tokio::spawn(async move {
                let resp = match work.await {
                    Ok(r) => Some(r),
                    Err(e) if e.is_cancelled() => None, // client cancelled → no response
                    Err(_panicked) => {
                        warn!(
                            request_id = %sup_key,
                            "tools/call task panicked — returning an error response"
                        );
                        // Record the panic into the failure ring so a repeatedly-panicking
                        // tool surfaces via mcp_recent_errors, not only stderr warn! logs.
                        record_mcp_tool_failure(
                            st_sup.as_deref(),
                            &tool_name_sup,
                            "tool panicked during execution",
                        )
                        .await;
                        Some(McpResponse::error(
                            req_id_panic,
                            INTERNAL_ERROR,
                            "tool panicked during execution; the MCP server stayed responsive",
                        ))
                    }
                };
                inflight_sup.lock().unwrap().remove(&sup_key);
                if let Some(r) = resp {
                    let _ = out.send(r);
                }
            });

            map.insert(map_key, abort);
            drop(map);
        } else {
            let resp = handle(
                &registry,
                store.as_deref(),
                req,
                &server_name,
                &version,
                tool_backend_id.as_ref(),
                &mut telemetry,
            )
            .await;
            let _ = resp_tx.send(resp);
        }
    }
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
    codex_host: Option<String>,
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
        let codex_host = std::env::var("AGENT_BRIDGE_CODEX_HOST")
            .ok()
            .and_then(nonempty_string);
        Self {
            client_name,
            profile,
            source,
            model,
            model_reasoning_effort,
            codex_host,
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
        self.codex_host = std::env::var("AGENT_BRIDGE_CODEX_HOST")
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
        Some("codex-essential")
        | Some("codex-lean")
        | Some("codex-minimal")
        | Some("codex")
        | Some("gemini-lean")
        | Some("gemini") => "essential",
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
            telemetry.codex_host.clone(),
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

            let ctx = tool_context_from_call(&params, &args);
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
    use crate::{McpTool, ToolSchema};
    use async_trait::async_trait;

    // --- Layer 3 concurrency: a slow/hung tools/call must not block a later one,
    // and notifications/cancelled must abort an in-flight call. ---
    struct SleepTool {
        name: &'static str,
        delay_ms: u64,
    }

    #[async_trait]
    impl McpTool for SleepTool {
        fn name(&self) -> &'static str {
            self.name
        }
        fn schema(&self) -> ToolSchema {
            ToolSchema {
                name: self.name.into(),
                description: "test sleeper".into(),
                input_schema: json!({ "type": "object" }),
            }
        }
        async fn execute(&self, _args: Value, _ctx: &ToolContext) -> ab_core::Result<ToolResult> {
            tokio::time::sleep(Duration::from_millis(self.delay_ms)).await;
            Ok(ToolResult::text(self.name))
        }
    }

    struct PanicTool;

    #[async_trait]
    impl McpTool for PanicTool {
        fn name(&self) -> &'static str {
            "boom"
        }
        fn schema(&self) -> ToolSchema {
            ToolSchema {
                name: "boom".into(),
                description: "panics on execute".into(),
                input_schema: json!({ "type": "object" }),
            }
        }
        async fn execute(&self, _args: Value, _ctx: &ToolContext) -> ab_core::Result<ToolResult> {
            panic!("boom inside tool.execute");
        }
    }

    fn call_line(id: u64, tool: &str) -> String {
        json!({
            "jsonrpc": "2.0",
            "id": id,
            "method": "tools/call",
            "params": { "name": tool, "arguments": {} }
        })
        .to_string()
    }

    /// Drive the dispatch loop over fixed input lines and collect every response.
    /// The loop returns when input closes; the response channel then drains as the
    /// spawned tasks (which hold cloned senders) complete, so recv() yields all of
    /// them and ends when the last task drops its sender.
    async fn drive(reg: ToolRegistry, lines: Vec<String>) -> Vec<McpResponse> {
        let (ltx, lrx) = mpsc::unbounded_channel::<String>();
        let (rtx, mut rrx) = mpsc::unbounded_channel::<McpResponse>();
        for l in lines {
            ltx.send(l).unwrap();
        }
        drop(ltx); // close input → loop ends after draining
        run_dispatch_loop(lrx, rtx, reg, None, "test".into(), "0".into(), None).await;
        let mut out = Vec::new();
        while let Some(r) = rrx.recv().await {
            out.push(r);
        }
        out
    }

    #[tokio::test]
    async fn slow_tools_call_does_not_block_a_later_fast_one() {
        let mut reg = ToolRegistry::default();
        reg.register(Arc::new(SleepTool {
            name: "slow",
            delay_ms: 300,
        }));
        reg.register(Arc::new(SleepTool {
            name: "fast",
            delay_ms: 0,
        }));
        // slow is sent FIRST; the old sequential loop would block fast behind it.
        let resps = drive(reg, vec![call_line(1, "slow"), call_line(2, "fast")]).await;
        assert_eq!(resps.len(), 2, "both calls must respond");
        assert_eq!(
            resps[0].id,
            json!(2),
            "fast call must return before the slow one (concurrent, no head-of-line block)"
        );
        assert_eq!(resps[1].id, json!(1));
    }

    #[tokio::test]
    async fn notifications_cancelled_aborts_in_flight_call() {
        let mut reg = ToolRegistry::default();
        // would otherwise run 5s; the cancellation must abort it near-instantly.
        reg.register(Arc::new(SleepTool {
            name: "slow",
            delay_ms: 5_000,
        }));
        let cancel = json!({
            "jsonrpc": "2.0",
            "method": "notifications/cancelled",
            "params": { "requestId": 1 }
        })
        .to_string();
        let resps = tokio::time::timeout(
            Duration::from_millis(800),
            drive(reg, vec![call_line(1, "slow"), cancel]),
        )
        .await
        .expect("must finish well under the 5s tool sleep because the call was aborted");
        assert!(
            resps.is_empty(),
            "an aborted in-flight call must not emit a response"
        );
    }

    #[tokio::test]
    async fn panicking_tools_call_yields_error_response_not_a_hang() {
        let mut reg = ToolRegistry::default();
        reg.register(Arc::new(PanicTool));
        // A panic inside tool.execute() must NOT swallow the response (which would
        // re-create the "AB call never returns" wedge); the supervisor must turn it
        // into a JSON-RPC error response, promptly.
        let resps = tokio::time::timeout(
            Duration::from_millis(800),
            drive(reg, vec![call_line(1, "boom")]),
        )
        .await
        .expect("a panicking tool must return promptly, not hang the request");
        assert_eq!(resps.len(), 1, "exactly one response for the panicking call");
        assert_eq!(resps[0].id, json!(1));
        assert!(
            resps[0].error.is_some() && resps[0].result.is_none(),
            "a panicking tool must yield a JSON-RPC error, not a success or silence"
        );
    }

    #[test]
    fn tool_context_from_call_reads_session_id_from_meta() {
        let params = json!({
            "_meta": {
                "session_id": "session-from-meta",
                "client": "codex"
            },
            "name": "any_tool",
            "arguments": {}
        });
        let args = json!({});

        let ctx = tool_context_from_call(&params, &args);

        assert_eq!(
            ctx.session_id.as_ref().map(|s| s.as_str()),
            Some("session-from-meta")
        );
        assert_eq!(
            ctx.extras.get("_meta").and_then(|v| v.get("client")),
            Some(&json!("codex"))
        );
    }

    #[test]
    fn tool_context_from_call_reads_session_id_from_arguments() {
        let params = json!({
            "name": "any_tool",
            "arguments": {
                "sessionId": "session-from-args"
            }
        });
        let args = params.get("arguments").cloned().unwrap();

        let ctx = tool_context_from_call(&params, &args);

        assert_eq!(
            ctx.session_id.as_ref().map(|s| s.as_str()),
            Some("session-from-args")
        );
    }

    #[test]
    fn tool_context_from_call_reads_session_id_from_codex_turn_metadata() {
        let params = json!({
            "_meta": {
                "threadId": "thread-fallback",
                "x-codex-turn-metadata": {
                    "model": "gpt-5.5",
                    "reasoning_effort": "xhigh",
                    "session_id": "session-from-codex-turn-metadata",
                    "thread_id": "thread-from-codex-turn-metadata"
                }
            },
            "name": "any_tool",
            "arguments": {}
        });
        let args = json!({});

        let ctx = tool_context_from_call(&params, &args);

        assert_eq!(
            ctx.session_id.as_ref().map(|s| s.as_str()),
            Some("session-from-codex-turn-metadata")
        );
    }

    #[test]
    fn tool_context_from_call_falls_back_to_meta_thread_id() {
        let params = json!({
            "_meta": {
                "threadId": "thread-id-fallback"
            },
            "name": "any_tool",
            "arguments": {}
        });
        let args = json!({});

        let ctx = tool_context_from_call(&params, &args);

        assert_eq!(
            ctx.session_id.as_ref().map(|s| s.as_str()),
            Some("thread-id-fallback")
        );
    }

    struct EnvVarGuard {
        key: &'static str,
        prev: Option<String>,
    }

    impl EnvVarGuard {
        fn unset(key: &'static str) -> Self {
            let prev = std::env::var(key).ok();
            unsafe {
                std::env::remove_var(key);
            }
            Self { key, prev }
        }

        fn set(key: &'static str, value: &str) -> Self {
            let prev = std::env::var(key).ok();
            unsafe {
                std::env::set_var(key, value);
            }
            Self { key, prev }
        }
    }

    impl Drop for EnvVarGuard {
        fn drop(&mut self) {
            unsafe {
                match &self.prev {
                    Some(value) => std::env::set_var(self.key, value),
                    None => std::env::remove_var(self.key),
                }
            }
        }
    }

    static TOOL_CONTEXT_ENV_LOCK: std::sync::Mutex<()> = std::sync::Mutex::new(());

    fn clear_session_env_vars_except(key_to_set: &'static str, value: &str) -> Vec<EnvVarGuard> {
        let mut guards = vec![
            EnvVarGuard::unset("AGENT_BRIDGE_SESSION_ID"),
            EnvVarGuard::unset("CLAUDE_CODE_SESSION_ID"),
            EnvVarGuard::unset("CLAUDE_SESSION_ID"),
            EnvVarGuard::unset("CODEX_COMPANION_SESSION_ID"),
            EnvVarGuard::unset("CODEX_SESSION_ID"),
            EnvVarGuard::unset("MCP_SESSION_ID"),
        ];
        guards.push(EnvVarGuard::set(key_to_set, value));
        guards
    }

    #[test]
    fn tool_context_from_call_reads_session_id_from_claude_code_env() {
        let _lock = TOOL_CONTEXT_ENV_LOCK
            .lock()
            .unwrap_or_else(|e| e.into_inner());
        let _guards =
            clear_session_env_vars_except("CLAUDE_CODE_SESSION_ID", "session-from-claude-code");
        let params = json!({
            "name": "any_tool",
            "arguments": {}
        });
        let args = params.get("arguments").cloned().unwrap();

        let ctx = tool_context_from_call(&params, &args);

        assert_eq!(
            ctx.session_id.as_ref().map(|s| s.as_str()),
            Some("session-from-claude-code")
        );
    }

    #[test]
    fn tool_context_from_call_reads_session_id_from_codex_companion_env() {
        let _lock = TOOL_CONTEXT_ENV_LOCK
            .lock()
            .unwrap_or_else(|e| e.into_inner());
        let _guards = clear_session_env_vars_except(
            "CODEX_COMPANION_SESSION_ID",
            "session-from-codex-companion",
        );
        let params = json!({
            "name": "any_tool",
            "arguments": {}
        });
        let args = params.get("arguments").cloned().unwrap();

        let ctx = tool_context_from_call(&params, &args);

        assert_eq!(
            ctx.session_id.as_ref().map(|s| s.as_str()),
            Some("session-from-codex-companion")
        );
    }

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
            mcp_profile_label_from_values(Some("codex-lean"), Some("all")),
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
