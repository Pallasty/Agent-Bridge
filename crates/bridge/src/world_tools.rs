//! Live Semantic World Runtime Step C MCP tools.
//!
//! These are thin localhost TCP clients for the onsen PHASE0 Step B dev host.
//! They deliberately preserve host failures as structured `verified=false`
//! envelopes instead of turning live-world absence into opaque MCP errors.

use ab_core::Result;
use ab_mcp::{McpTool, ToolContext, ToolResult, ToolSchema};
use async_trait::async_trait;
use serde_json::{json, Value};
use std::net::IpAddr;
use std::path::PathBuf;
use std::time::{Duration, SystemTime, UNIX_EPOCH};
use tokio::io::{AsyncBufReadExt, AsyncWriteExt, BufReader};
use tokio::net::TcpStream;

const WORLD_PRESENT_SCHEMA: &str = "agent_bridge.world_present.v0";
const WORLD_TOOL_SCHEMA: &str = "agent_bridge.world_tool.v0";
const ACTION_RESULT_SCHEMA: &str = "agent_bridge.semantic_bus.action_result.v0";
const LSWR_ADAPTER: &str = "lswr.onsen";
const DEFAULT_HOST: &str = "127.0.0.1";
const DEFAULT_PORT: u16 = 37691;
const HOST_ADDR_ENV: &str = "ONSEN_LSWR_HOST_ADDR";
const HOST_PORT_ENV: &str = "ONSEN_LSWR_HOST_PORT";
const ONSEN_HOST_PORT_ENV: &str = "ONSEN_LSWR_PORT";
const DEFAULT_TIMEOUT_MS: u64 = 5_000;
const MIN_TIMEOUT_MS: u64 = 250;
const MAX_TIMEOUT_MS: u64 = 30_000;
const VERIFIED_TO: &str = "onsen_live_root_viewport";
const VERIFY_METHOD: &str = "live_viewport_pixel_coverage";

#[derive(Debug, Clone, PartialEq, Eq)]
struct WorldEndpoint {
    host: String,
    port: u16,
    timeout_ms: u64,
}

impl WorldEndpoint {
    fn from_args(args: &Value) -> std::result::Result<Self, String> {
        let env_addr = std::env::var(HOST_ADDR_ENV).ok();
        let (env_host, env_addr_port) = env_addr
            .as_deref()
            .and_then(split_host_port)
            .map(|(h, p)| (Some(h), p))
            .unwrap_or_else(|| {
                (
                    env_addr
                        .as_deref()
                        .map(str::trim)
                        .filter(|s| !s.is_empty())
                        .map(str::to_string),
                    None,
                )
            });

        let arg_host_raw = args
            .get("host")
            .and_then(Value::as_str)
            .map(str::trim)
            .filter(|s| !s.is_empty());
        let (arg_host, arg_host_port) = arg_host_raw
            .and_then(split_host_port)
            .map(|(h, p)| (Some(h), p))
            .unwrap_or_else(|| (arg_host_raw.map(str::to_string), None));

        let host = arg_host
            .or(env_host)
            .unwrap_or_else(|| DEFAULT_HOST.to_string());
        if !is_loopback_host(&host) {
            return Err("world_host_non_loopback_rejected".to_string());
        }

        let port = args
            .get("port")
            .and_then(Value::as_u64)
            .and_then(|p| u16::try_from(p).ok())
            .or(arg_host_port)
            .or(env_addr_port)
            .or_else(|| {
                std::env::var(HOST_PORT_ENV)
                    .ok()
                    .and_then(|p| p.parse::<u16>().ok())
            })
            .or_else(|| {
                std::env::var(ONSEN_HOST_PORT_ENV)
                    .ok()
                    .and_then(|p| p.parse::<u16>().ok())
            })
            .unwrap_or(DEFAULT_PORT);
        let timeout_ms = args
            .get("timeout_ms")
            .and_then(Value::as_u64)
            .unwrap_or(DEFAULT_TIMEOUT_MS)
            .clamp(MIN_TIMEOUT_MS, MAX_TIMEOUT_MS);
        Ok(Self {
            host,
            port,
            timeout_ms,
        })
    }
}

fn split_host_port(raw: &str) -> Option<(String, Option<u16>)> {
    let s = raw.trim();
    if s.is_empty() {
        return None;
    }
    if let Some(rest) = s.strip_prefix('[') {
        let (host, tail) = rest.split_once(']')?;
        let port = tail.strip_prefix(':').and_then(|p| p.parse::<u16>().ok());
        return Some((host.to_string(), port));
    }
    if let Some((host, port_s)) = s.rsplit_once(':') {
        if host.contains(':') {
            return Some((s.to_string(), None));
        }
        if let Ok(port) = port_s.parse::<u16>() {
            return Some((host.to_string(), Some(port)));
        }
    }
    Some((s.to_string(), None))
}

fn is_loopback_host(host: &str) -> bool {
    let h = host.trim().trim_matches(['[', ']']);
    if h.eq_ignore_ascii_case("localhost") {
        return true;
    }
    h.parse::<IpAddr>()
        .map(|ip| ip.is_loopback())
        .unwrap_or(false)
}

fn request_id(prefix: &str) -> String {
    let nanos = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap_or_default()
        .as_nanos();
    format!("{prefix}-{nanos}")
}

fn string_array(args: &Value, key: &str) -> Option<Vec<String>> {
    args.get(key).and_then(Value::as_array).map(|arr| {
        arr.iter()
            .filter_map(Value::as_str)
            .map(str::trim)
            .filter(|s| !s.is_empty())
            .map(str::to_string)
            .collect::<Vec<_>>()
    })
}

fn copy_debug_fields(args: &Value, request: &mut serde_json::Map<String, Value>) {
    if let Some(v) = args.get("debug_session") {
        request.insert("debug.session".to_string(), v.clone());
    }
    if let Some(v) = args.get("debug_viewport") {
        request.insert("debug.viewport".to_string(), v.clone());
    }
    if let Some(v) = args.get("debug_visibility") {
        request.insert("debug.visibility".to_string(), v.clone());
    }
}

fn build_query_request(args: &Value, default_entities: Option<Vec<String>>) -> Option<Value> {
    let entities = string_array(args, "entities").or(default_entities)?;
    let mut request = serde_json::Map::new();
    request.insert(
        "request_id".to_string(),
        json!(args
            .get("request_id")
            .and_then(Value::as_str)
            .map(str::to_string)
            .unwrap_or_else(|| request_id("ab-world-query"))),
    );
    request.insert(
        "world.visibility.query".to_string(),
        json!({ "entities": entities }),
    );
    copy_debug_fields(args, &mut request);
    Some(Value::Object(request))
}

fn build_patch_request(args: &Value) -> std::result::Result<Value, String> {
    let op = args
        .get("op")
        .and_then(Value::as_str)
        .map(str::trim)
        .filter(|s| !s.is_empty())
        .ok_or_else(|| "op is required".to_string())?;
    let entity = args
        .get("entity")
        .and_then(Value::as_str)
        .map(str::trim)
        .filter(|s| !s.is_empty())
        .ok_or_else(|| "entity is required".to_string())?;
    let visibility_entities =
        string_array(args, "visibility_entities").unwrap_or_else(|| vec![entity.to_string()]);
    let patch_args = args
        .get("args")
        .and_then(Value::as_object)
        .cloned()
        .map(Value::Object)
        .unwrap_or_else(|| json!({}));
    let expected_effect = args
        .get("expected_effect")
        .filter(|v| !v.is_null())
        .cloned();

    let mut request = serde_json::Map::new();
    request.insert(
        "request_id".to_string(),
        json!(args
            .get("request_id")
            .and_then(Value::as_str)
            .map(str::to_string)
            .unwrap_or_else(|| request_id("ab-world-patch"))),
    );
    let mut patch = serde_json::Map::new();
    patch.insert("op".to_string(), json!(op));
    patch.insert("entity".to_string(), json!(entity));
    patch.insert("args".to_string(), patch_args);
    if let Some(expected_effect) = expected_effect {
        patch.insert("expected_effect".to_string(), expected_effect);
    }
    request.insert("world.patch".to_string(), Value::Object(patch));
    request.insert(
        "world.visibility.query".to_string(),
        json!({ "entities": visibility_entities }),
    );
    copy_debug_fields(args, &mut request);
    Ok(Value::Object(request))
}

async fn call_world_host_with_tool(
    endpoint: &WorldEndpoint,
    request: &Value,
    world_tool: &str,
) -> Value {
    let timeout_dur = Duration::from_millis(endpoint.timeout_ms);
    let mut stream = match tokio::time::timeout(
        timeout_dur,
        TcpStream::connect((endpoint.host.as_str(), endpoint.port)),
    )
    .await
    {
        Ok(Ok(s)) => s,
        Ok(Err(e)) => {
            return not_verified_envelope_with_tool(
                "world_host_unreachable",
                endpoint,
                request,
                Some(e.to_string()),
                world_tool,
            );
        }
        Err(_) => {
            return not_verified_envelope_with_tool(
                "world_host_timeout",
                endpoint,
                request,
                None,
                world_tool,
            );
        }
    };

    let line = match serde_json::to_string(request) {
        Ok(s) => format!("{s}\n"),
        Err(e) => {
            return not_verified_envelope_with_tool(
                "world_request_malformed",
                endpoint,
                request,
                Some(e.to_string()),
                world_tool,
            );
        }
    };
    match tokio::time::timeout(timeout_dur, stream.write_all(line.as_bytes())).await {
        Ok(Ok(())) => {}
        Ok(Err(e)) => {
            return not_verified_envelope_with_tool(
                "world_host_unreachable",
                endpoint,
                request,
                Some(e.to_string()),
                world_tool,
            );
        }
        Err(_) => {
            return not_verified_envelope_with_tool(
                "world_host_timeout",
                endpoint,
                request,
                None,
                world_tool,
            );
        }
    }

    let mut reader = BufReader::new(stream);
    let mut response_line = String::new();
    match tokio::time::timeout(timeout_dur, reader.read_line(&mut response_line)).await {
        Ok(Ok(0)) => {
            return not_verified_envelope_with_tool(
                "world_host_malformed_response",
                endpoint,
                request,
                Some("empty response".to_string()),
                world_tool,
            );
        }
        Ok(Ok(_)) => {}
        Ok(Err(e)) => {
            return not_verified_envelope_with_tool(
                "world_host_unreachable",
                endpoint,
                request,
                Some(e.to_string()),
                world_tool,
            );
        }
        Err(_) => {
            return not_verified_envelope_with_tool(
                "world_host_timeout",
                endpoint,
                request,
                None,
                world_tool,
            );
        }
    }
    match serde_json::from_str::<Value>(response_line.trim()) {
        Ok(host_response) => {
            wrap_host_response_with_tool(endpoint, request, host_response, world_tool)
        }
        Err(e) => not_verified_envelope_with_tool(
            "world_host_malformed_response",
            endpoint,
            request,
            Some(e.to_string()),
            world_tool,
        ),
    }
}

fn host_verified(host_response: &Value) -> bool {
    host_response
        .get("verified")
        .and_then(Value::as_bool)
        .unwrap_or(false)
}

fn host_reason(host_response: &Value) -> Value {
    for path in [
        &["reason"][..],
        &["error"][..],
        &["render", "reason"][..],
        &["render_integrity", "reason"][..],
        &["expected_effect", "reason"][..],
        &["world.visibility.query", "after", "reason"][..],
    ] {
        if let Some(v) = get_path(host_response, path) {
            if is_meaningful_reason(v) {
                return v.clone();
            }
        }
    }
    for entity_reason_key in ["reason", "pixel_coverage.reason"] {
        if let Some(v) = first_entity_reason(host_response, entity_reason_key) {
            return v.clone();
        }
    }
    Value::Null
}

fn host_patch_result(host_response: &Value) -> Option<Value> {
    for path in [
        &["world.patch"][..],
        &["world", "patch"][..],
        &["patch_result"][..],
    ] {
        if let Some(v) = get_path(host_response, path) {
            return Some(v.clone());
        }
    }
    None
}

fn host_expected_effect_result(host_response: &Value) -> Option<Value> {
    for path in [
        &["expected_effect"][..],
        &["world.patch", "expected_effect"][..],
        &["world", "patch", "expected_effect"][..],
    ] {
        if let Some(v) = get_path(host_response, path) {
            return Some(v.clone());
        }
    }
    None
}

fn is_meaningful_reason(value: &Value) -> bool {
    match value {
        Value::Null => false,
        Value::String(s) => !s.trim().is_empty(),
        _ => true,
    }
}

fn get_path<'a>(value: &'a Value, path: &[&str]) -> Option<&'a Value> {
    let mut cur = value;
    for key in path {
        cur = cur.get(*key)?;
    }
    Some(cur)
}

fn first_entity_reason<'a>(host_response: &'a Value, key: &str) -> Option<&'a Value> {
    let entities = get_path(
        host_response,
        &["world.visibility.query", "after", "entities"],
    )?
    .as_array()?;
    let key_path: Vec<&str> = key.split('.').collect();
    entities
        .iter()
        .filter_map(|entity| get_path(entity, &key_path))
        .find(|reason| is_meaningful_reason(reason))
}

fn first_key_recursive<'a>(value: &'a Value, key: &str) -> Option<&'a Value> {
    match value {
        Value::Object(map) => {
            if let Some(v) = map.get(key) {
                return Some(v);
            }
            map.values().find_map(|v| first_key_recursive(v, key))
        }
        Value::Array(arr) => arr.iter().find_map(|v| first_key_recursive(v, key)),
        _ => None,
    }
}

fn verify_block(verified: bool, host_response: Option<&Value>, reason: Value) -> Value {
    let evidence = host_response
        .map(|h| {
            json!({
                "screen_area": first_key_recursive(h, "screen_area").cloned().unwrap_or(Value::Null),
                "bounds_screen_area": first_key_recursive(h, "bounds_screen_area").cloned().unwrap_or(Value::Null),
                "flicker_frames": h.get("flicker").and_then(|f| f.get("frames")).cloned().unwrap_or(Value::Null),
                "render_source": h.get("render").and_then(|r| r.get("source")).cloned().unwrap_or(Value::Null),
                "render_path": h.get("transport").and_then(|t| t.get("render_path")).cloned().unwrap_or(Value::Null),
                "host_reason": reason,
            })
        })
        .unwrap_or_else(|| json!({ "host_reason": reason }));
    json!({
        "method": VERIFY_METHOD,
        "verified_to": if verified { json!(VERIFIED_TO) } else { Value::Null },
        "evidence": evidence,
    })
}

fn wrap_host_response_with_tool(
    endpoint: &WorldEndpoint,
    request: &Value,
    host_response: Value,
    world_tool: &str,
) -> Value {
    let verified = host_verified(&host_response);
    let reason = host_reason(&host_response);
    let verify = verify_block(verified, Some(&host_response), reason.clone());
    let action_result = action_result_block(world_tool, request, verified, &reason, true);
    let mut envelope = json!({
        "schema": WORLD_TOOL_SCHEMA,
        "ok": host_response.get("ok").and_then(Value::as_bool).unwrap_or(verified),
        "verified": verified,
        "reason": reason,
        "endpoint": {
            "host": endpoint.host,
            "port": endpoint.port,
            "timeout_ms": endpoint.timeout_ms,
        },
        "request": request,
        "verify": verify,
        "action_result": action_result,
        "host_response": host_response,
    });
    if let Some(patch_result) = envelope.get("host_response").and_then(host_patch_result) {
        if let Some(obj) = envelope.as_object_mut() {
            obj.insert("world.patch".to_string(), patch_result);
        }
    }
    if let Some(expected_effect) = envelope
        .get("host_response")
        .and_then(host_expected_effect_result)
    {
        if let Some(obj) = envelope.as_object_mut() {
            obj.insert("expected_effect".to_string(), expected_effect);
        }
    }
    envelope
}

fn not_verified_envelope_with_tool(
    reason: &str,
    endpoint: &WorldEndpoint,
    request: &Value,
    detail: Option<String>,
    world_tool: &str,
) -> Value {
    let reason_value = json!(reason);
    let action_result = action_result_block(world_tool, request, false, &reason_value, false);
    json!({
        "schema": WORLD_TOOL_SCHEMA,
        "ok": false,
        "verified": false,
        "reason": reason,
        "detail": detail,
        "endpoint": {
            "host": endpoint.host,
            "port": endpoint.port,
            "timeout_ms": endpoint.timeout_ms,
        },
        "request": request,
        "verify": verify_block(false, None, json!(reason)),
        "action_result": action_result,
        "host_response": Value::Null,
    })
}

fn request_id_from_request(request: &Value) -> String {
    request
        .get("request_id")
        .and_then(Value::as_str)
        .map(str::trim)
        .filter(|s| !s.is_empty())
        .unwrap_or("unknown")
        .to_string()
}

fn action_type_for_world_tool(world_tool: &str) -> &'static str {
    match world_tool {
        "world_patch" => "world.patch",
        "world_visibility_query" => "world.visibility.query",
        "world_query" => "world.query",
        _ => "world.unknown",
    }
}

fn action_verdict(verified: bool, reason: &Value) -> &'static str {
    if verified {
        return "verified";
    }
    match reason.as_str() {
        Some("world_host_non_loopback_rejected")
        | Some("world_patch_invalid")
        | Some("world_patch_blocked") => "blocked",
        _ => "not_verified",
    }
}

fn action_recover(verdict: &str) -> &'static str {
    match verdict {
        "verified" => "proceed",
        "blocked" => "replan",
        _ => "inspect_host_or_visibility_evidence",
    }
}

fn subject_id_for_request(request: &Value) -> String {
    get_path(request, &["world.patch", "entity"])
        .and_then(Value::as_str)
        .map(str::trim)
        .filter(|s| !s.is_empty())
        .map(|entity| format!("lswr:onsen:entity:{entity}"))
        .unwrap_or_else(|| "lswr:onsen:world".to_string())
}

fn action_result_block(
    world_tool: &str,
    request: &Value,
    verified: bool,
    reason: &Value,
    raw_available: bool,
) -> Value {
    let request_id = request_id_from_request(request);
    let verdict = action_verdict(verified, reason);
    json!({
        "schema": ACTION_RESULT_SCHEMA,
        "source_schema": WORLD_TOOL_SCHEMA,
        "adapter": LSWR_ADAPTER,
        "world_tool": world_tool,
        "action_type": action_type_for_world_tool(world_tool),
        "action_id": format!("lswr:{world_tool}:{request_id}:result"),
        "request_id": request_id,
        "subject_id": subject_id_for_request(request),
        "event_ids": [format!("evt-lswr-{world_tool}-{request_id}")],
        "verdict": verdict,
        "reason": reason,
        "verified_to": if verified { json!(VERIFIED_TO) } else { Value::Null },
        "verification_method": VERIFY_METHOD,
        "recover": action_recover(verdict),
        "raw_available": raw_available,
    })
}

enum WorldEndpointOrEnvelope {
    Endpoint(WorldEndpoint),
    Envelope(Value),
}

trait EndpointEnvelope {
    fn as_not_verified(
        self,
        reason: &str,
        request: &Value,
        world_tool: &str,
    ) -> WorldEndpointOrEnvelope;
}

impl EndpointEnvelope for WorldEndpoint {
    fn as_not_verified(
        self,
        reason: &str,
        request: &Value,
        world_tool: &str,
    ) -> WorldEndpointOrEnvelope {
        WorldEndpointOrEnvelope::Envelope(not_verified_envelope_with_tool(
            reason, &self, request, None, world_tool,
        ))
    }
}

impl From<WorldEndpoint> for WorldEndpointOrEnvelope {
    fn from(value: WorldEndpoint) -> Self {
        Self::Endpoint(value)
    }
}

fn endpoint_or_envelope(
    args: &Value,
    request: &Value,
    world_tool: &str,
) -> WorldEndpointOrEnvelope {
    match WorldEndpoint::from_args(args) {
        Ok(endpoint) => endpoint.into(),
        Err(reason) => {
            let endpoint = WorldEndpoint {
                host: args
                    .get("host")
                    .and_then(Value::as_str)
                    .unwrap_or(DEFAULT_HOST)
                    .to_string(),
                port: DEFAULT_PORT,
                timeout_ms: DEFAULT_TIMEOUT_MS,
            };
            endpoint.as_not_verified(&reason, request, world_tool)
        }
    }
}

async fn execute_with_endpoint(
    args: Value,
    request: Value,
    world_tool: &'static str,
) -> Result<ToolResult> {
    let include_raw = args
        .get("include_raw")
        .and_then(Value::as_bool)
        .unwrap_or(true);
    let mut result = match endpoint_or_envelope(&args, &request, world_tool) {
        WorldEndpointOrEnvelope::Endpoint(endpoint) => {
            call_world_host_with_tool(&endpoint, &request, world_tool).await
        }
        WorldEndpointOrEnvelope::Envelope(envelope) => envelope,
    };
    if !include_raw {
        if let Some(obj) = result.as_object_mut() {
            obj.remove("host_response");
        }
    }
    Ok(ToolResult::json_text(&result))
}

fn endpoint_schema_props() -> Value {
    json!({
        "host": { "type": "string", "description": "Loopback host for the onsen LSWR dev host. Non-loopback values are rejected in Step C." },
        "port": { "type": "integer", "minimum": 1, "maximum": 65535, "description": "Onsen LSWR dev host port. Param wins over ONSEN_LSWR_HOST_PORT, ONSEN_LSWR_PORT, and ONSEN_LSWR_HOST_ADDR port." },
        "timeout_ms": { "type": "integer", "minimum": 250, "maximum": 30000, "default": 5000 },
        "include_raw": { "type": "boolean", "default": true, "description": "Include exact host_response for parity checks." }
    })
}

fn infer_world_tool(args: &Value, envelope: &Value) -> String {
    if let Some(tool) = args
        .get("world_tool")
        .and_then(Value::as_str)
        .map(str::trim)
        .filter(|s| !s.is_empty())
    {
        return tool.to_string();
    }
    if let Some(tool) = get_path(envelope, &["action_result", "world_tool"])
        .and_then(Value::as_str)
        .map(str::trim)
        .filter(|s| !s.is_empty())
    {
        return tool.to_string();
    }
    let request = envelope.get("request").unwrap_or(&Value::Null);
    if request.get("world.patch").is_some()
        || get_path(envelope, &["host_response", "world.patch"]).is_some()
        || get_path(envelope, &["host_response", "world", "patch"]).is_some()
        || envelope.get("world.patch").is_some()
    {
        return "world_patch".to_string();
    }
    if request.get("world.visibility.query").is_some()
        || get_path(envelope, &["host_response", "world.visibility.query"]).is_some()
    {
        return "world_visibility_query".to_string();
    }
    "world_query".to_string()
}

fn static_render_status(html: &str) -> &'static str {
    if crate::present::render_region(html)
        .map(str::trim)
        .unwrap_or_default()
        .is_empty()
    {
        "blank_static"
    } else {
        "rendered_static"
    }
}

fn inline_present_artifact(packet: &Value) -> Value {
    let html = crate::lswr_present::present_packet_review_html(packet);
    let id = crate::lswr_present::present_packet_review_id(packet);
    json!({
        "kind": "html",
        "id": id,
        "html": html,
        "bytes": html.len(),
        "static_render_status": static_render_status(&html),
    })
}

fn file_present_artifact(packet: &Value, dir: PathBuf) -> std::io::Result<Value> {
    let file = crate::lswr_present::write_present_packet_review_file(packet, &dir)?;
    Ok(json!({
        "kind": "file",
        "id": file.id,
        "path": file.artifact_path.display().to_string(),
        "bytes": file.bytes,
        "static_render_status": file.static_render_status,
    }))
}

fn world_present_payload(args: &Value) -> std::result::Result<Value, String> {
    let envelope = args
        .get("envelope")
        .filter(|v| v.is_object())
        .ok_or_else(|| "envelope object is required".to_string())?;
    if envelope.get("schema").and_then(Value::as_str)
        != Some(crate::lswr_present::WORLD_TOOL_SCHEMA)
    {
        return Err("envelope.schema must be agent_bridge.world_tool.v0".to_string());
    }
    let include_raw = args
        .get("include_raw")
        .and_then(Value::as_bool)
        .unwrap_or(false);
    let generated_at = args
        .get("generated_at")
        .and_then(Value::as_str)
        .map(str::to_string)
        .unwrap_or_else(|| format!("unix:{}", crate::present::now_unix()));
    let mut options = crate::lswr_present::PresentPacketOptions::new(&generated_at);
    if let Some(commit) = args.get("commit").and_then(Value::as_str) {
        options = options.with_commit(commit);
    }
    let world_tool = infer_world_tool(args, envelope);
    let packet =
        crate::lswr_present::world_envelope_to_present_packet(&world_tool, envelope, options);
    let artifact = match args
        .get("out_dir")
        .and_then(Value::as_str)
        .map(str::trim)
        .filter(|s| !s.is_empty())
    {
        Some(out_dir) => file_present_artifact(&packet, PathBuf::from(out_dir))
            .map_err(|e| format!("world_present: write failed: {e}"))?,
        None => inline_present_artifact(&packet),
    };
    let html_for_dual = match artifact.get("kind").and_then(Value::as_str) {
        Some("file") => artifact
            .get("path")
            .and_then(Value::as_str)
            .and_then(|path| std::fs::read_to_string(path).ok())
            .unwrap_or_default(),
        _ => artifact
            .get("html")
            .and_then(Value::as_str)
            .unwrap_or_default()
            .to_string(),
    };
    let dual_encoding = crate::present::extract_ab_payload(&html_for_dual).is_some();
    let verdict = packet.get("verdict").cloned().unwrap_or(Value::Null);
    let reason = packet.get("reason").cloned().unwrap_or(Value::Null);
    let mut result = json!({
        "schema": WORLD_PRESENT_SCHEMA,
        "world_tool": world_tool,
        "source_schema": envelope.get("schema").cloned().unwrap_or(Value::Null),
        "packet": packet,
        "artifact": artifact,
        "dual_encoding": dual_encoding,
        "verdict": verdict,
        "reason": reason,
    });
    if include_raw {
        if let Some(obj) = result.as_object_mut() {
            obj.insert("source_envelope".to_string(), envelope.clone());
        }
    }
    Ok(result)
}

fn debug_schema_props() -> Value {
    json!({
        "debug_session": {
            "type": "object",
            "description": "Forwarded as host key `debug.session`, e.g. {enter_operating_shift:true, freeze_shift:true}."
        },
        "debug_viewport": {
            "type": "object",
            "description": "Forwarded as host key `debug.viewport`, e.g. {reset:true, scale:1.25, offset:[0,0]}."
        },
        "debug_visibility": {
            "type": "object",
            "description": "Forwarded as host key `debug.visibility`, e.g. {alpha_zero_entities:[\"bath\"]}."
        }
    })
}

fn merge_props(
    mut base: serde_json::Map<String, Value>,
    extras: Value,
) -> serde_json::Map<String, Value> {
    if let Some(map) = extras.as_object() {
        for (k, v) in map {
            base.insert(k.clone(), v.clone());
        }
    }
    base
}

pub struct WorldPresentTool;

impl WorldPresentTool {
    pub fn new() -> Self {
        Self
    }
}

#[async_trait]
impl McpTool for WorldPresentTool {
    fn name(&self) -> &'static str {
        "world_present"
    }

    fn schema(&self) -> ToolSchema {
        ToolSchema {
            name: self.name().into(),
            description: "LSWR Step D expression wrapper. Converts a verified=false/true \
                 `agent_bridge.world_tool.v0` envelope from world_query/world_patch/\
                 world_visibility_query into an `agent_bridge.lswr.present_packet.v0` \
                 review packet and a self-describing HTML artifact. Preserves lower-layer \
                 verification semantics: not_verified/blocked are never laundered into \
                 success, `verified_to` is emitted only for verified packets, and ingestion \
                 is always blocked in this Step D gate."
                .into(),
            input_schema: json!({
                "type": "object",
                "properties": {
                    "envelope": {
                        "type": "object",
                        "description": "A `agent_bridge.world_tool.v0` envelope returned by a world_* tool."
                    },
                    "world_tool": {
                        "type": "string",
                        "enum": ["world_query", "world_patch", "world_visibility_query"],
                        "description": "Optional explicit source tool. If omitted, inferred from envelope.request."
                    },
                    "out_dir": {
                        "type": "string",
                        "description": "Optional directory for writing the HTML artifact. If omitted, returns inline HTML in artifact.html."
                    },
                    "include_raw": {
                        "type": "boolean",
                        "default": false,
                        "description": "When true, include the original source envelope in the result."
                    },
                    "generated_at": {
                        "type": "string",
                        "description": "Optional generated-at label for packet provenance."
                    },
                    "commit": {
                        "type": "string",
                        "description": "Optional source commit label for packet provenance."
                    }
                },
                "required": ["envelope"]
            }),
        }
    }

    async fn execute(&self, args: Value, _ctx: &ToolContext) -> Result<ToolResult> {
        match world_present_payload(&args) {
            Ok(payload) => Ok(ToolResult::json_text(&payload)),
            Err(e) => Ok(ToolResult::error(e)),
        }
    }
}

pub struct WorldQueryTool;

impl WorldQueryTool {
    pub fn new() -> Self {
        Self
    }
}

#[async_trait]
impl McpTool for WorldQueryTool {
    fn name(&self) -> &'static str {
        "world_query"
    }

    fn schema(&self) -> ToolSchema {
        let mut props = serde_json::Map::new();
        props.insert(
            "entities".to_string(),
            json!({ "type": "array", "items": { "type": "string" }, "default": ["bath"] }),
        );
        props.insert("request_id".to_string(), json!({ "type": "string" }));
        let props = merge_props(
            merge_props(props, debug_schema_props()),
            endpoint_schema_props(),
        );
        ToolSchema {
            name: self.name().into(),
            description: "Query the live onsen semantic world host through Agent-Bridge. \
                 Step C thin TCP client: returns render-grounded visibility/world state \
                 from the human-visible live viewport when a dev host is running; otherwise \
                 returns structured verified=false."
                .into(),
            input_schema: json!({
                "type": "object",
                "properties": props,
            }),
        }
    }

    async fn execute(&self, args: Value, _ctx: &ToolContext) -> Result<ToolResult> {
        let request = build_query_request(&args, Some(vec!["bath".to_string()]))
            .expect("world_query has a default entity");
        execute_with_endpoint(args, request, "world_query").await
    }
}

pub struct WorldVisibilityQueryTool;

impl WorldVisibilityQueryTool {
    pub fn new() -> Self {
        Self
    }
}

#[async_trait]
impl McpTool for WorldVisibilityQueryTool {
    fn name(&self) -> &'static str {
        "world_visibility_query"
    }

    fn schema(&self) -> ToolSchema {
        let mut props = serde_json::Map::new();
        props.insert(
            "entities".to_string(),
            json!({
                "type": "array",
                "items": { "type": "string" },
                "minItems": 1,
                "description": "Required explicit entity list. No silent [bath] default for explicit perception queries."
            }),
        );
        props.insert("request_id".to_string(), json!({ "type": "string" }));
        let props = merge_props(
            merge_props(props, debug_schema_props()),
            endpoint_schema_props(),
        );
        ToolSchema {
            name: self.name().into(),
            description: "Explicit pixel-grounded visibility query for the live onsen root \
                 viewport. `entities` is required by C0 sign-off; missing host or failed \
                 perception returns structured verified=false, not fake success."
                .into(),
            input_schema: json!({
                "type": "object",
                "properties": props,
                "required": ["entities"]
            }),
        }
    }

    async fn execute(&self, args: Value, _ctx: &ToolContext) -> Result<ToolResult> {
        let Some(request) = build_query_request(&args, None) else {
            return Ok(ToolResult::error(
                "entities is required for world_visibility_query",
            ));
        };
        execute_with_endpoint(args, request, "world_visibility_query").await
    }
}

pub struct WorldPatchTool;

impl WorldPatchTool {
    pub fn new() -> Self {
        Self
    }
}

#[async_trait]
impl McpTool for WorldPatchTool {
    fn name(&self) -> &'static str {
        "world_patch"
    }

    fn schema(&self) -> ToolSchema {
        let mut props = serde_json::Map::new();
        props.insert(
            "op".to_string(),
            json!({
                "type": "string",
                "enum": ["move", "move_facility", "rotate", "rotate_facility", "flip", "flip_facility", "remove", "remove_facility", "place", "place_facility"]
            }),
        );
        props.insert("entity".to_string(), json!({ "type": "string" }));
        props.insert(
            "args".to_string(),
            json!({ "type": "object", "description": "Forwarded to host world.patch.args, e.g. {cell:[8,0]}." }),
        );
        props.insert(
            "expected_effect".to_string(),
            json!({
                "description": "Optional falsifiable render-derived clause or clauses forwarded as world.patch.expected_effect. Minimal supported shape: {target, metric, to_op, to_value, from?} or an array of those clauses.",
                "oneOf": [
                    {"type": "object"},
                    {"type": "array", "items": {"type": "object"}}
                ]
            }),
        );
        props.insert(
            "visibility_entities".to_string(),
            json!({
                "type": "array",
                "items": { "type": "string" },
                "description": "Entities queried after patch. Defaults to [entity] so patch never returns an empty ACK."
            }),
        );
        props.insert("request_id".to_string(), json!({ "type": "string" }));
        let props = merge_props(
            merge_props(props, debug_schema_props()),
            endpoint_schema_props(),
        );
        ToolSchema {
            name: self.name().into(),
            description: "Apply a live onsen world patch through the dev host and always request \
                 visibility in the same round trip. AB is only a TCP client; host false/unreachable \
                 is faithfully surfaced as verified=false."
                .into(),
            input_schema: json!({
                "type": "object",
                "properties": props,
                "required": ["op", "entity"]
            }),
        }
    }

    async fn execute(&self, args: Value, _ctx: &ToolContext) -> Result<ToolResult> {
        let request = match build_patch_request(&args) {
            Ok(r) => r,
            Err(e) => return Ok(ToolResult::error(e)),
        };
        execute_with_endpoint(args, request, "world_patch").await
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use ab_mcp::ContentBlock;
    use tokio::net::TcpListener;

    static ENV_LOCK: std::sync::Mutex<()> = std::sync::Mutex::new(());

    fn result_text_as_json(r: &ToolResult) -> Value {
        let text = match r.content.first().expect("content") {
            ContentBlock::Text { text } => text,
            _ => panic!("expected text block"),
        };
        serde_json::from_str(text).expect("json payload")
    }

    fn verified_visibility_envelope() -> Value {
        json!({
            "schema": crate::lswr_present::WORLD_TOOL_SCHEMA,
            "ok": true,
            "verified": true,
            "reason": null,
            "request": {
                "request_id": "fixture-verified-visibility",
                "world.visibility.query": {"entities": ["bath"]}
            },
            "verify": {
                "method": "live_viewport_pixel_coverage",
                "verified_to": "onsen_live_root_viewport",
                "evidence": {"host_reason": null, "screen_area": 0.1, "bounds_screen_area": 0.2}
            },
            "host_response": {
                "verified": true,
                "world.visibility.query": {
                    "after": {
                        "entities": [{"id": "bath", "screen_area": 0.1, "bounds_screen_area": 0.2, "occluded": false}]
                    }
                }
            }
        })
    }

    fn alpha_zero_envelope() -> Value {
        json!({
            "schema": crate::lswr_present::WORLD_TOOL_SCHEMA,
            "ok": true,
            "verified": false,
            "reason": "pixel_coverage_zero",
            "request": {
                "request_id": "fixture-alpha-zero",
                "world.visibility.query": {"entities": ["bath"]}
            },
            "verify": {
                "method": "live_viewport_pixel_coverage",
                "verified_to": null,
                "evidence": {"host_reason": "pixel_coverage_zero", "screen_area": 0.0, "bounds_screen_area": 0.2}
            }
        })
    }

    fn host_unreachable_envelope() -> Value {
        json!({
            "schema": crate::lswr_present::WORLD_TOOL_SCHEMA,
            "ok": false,
            "verified": false,
            "reason": "world_host_unreachable",
            "detail": "Connection refused",
            "request": {"request_id": "fixture-host-unreachable"},
            "verify": {
                "method": "live_viewport_pixel_coverage",
                "verified_to": null,
                "evidence": {"host_reason": "world_host_unreachable"}
            },
            "host_response": null
        })
    }

    fn blocked_envelope() -> Value {
        json!({
            "schema": crate::lswr_present::WORLD_TOOL_SCHEMA,
            "ok": false,
            "verified": false,
            "reason": "world_host_non_loopback_rejected",
            "request": {
                "request_id": "fixture-blocked",
                "world.visibility.query": {"entities": ["bath"]}
            },
            "verify": {
                "method": "live_viewport_pixel_coverage",
                "verified_to": null,
                "evidence": {"host_reason": "world_host_non_loopback_rejected"}
            },
            "host_response": null
        })
    }

    fn clear_endpoint_env() {
        std::env::remove_var(HOST_ADDR_ENV);
        std::env::remove_var(HOST_PORT_ENV);
        std::env::remove_var(ONSEN_HOST_PORT_ENV);
    }

    async fn spawn_one_response_host(response: Value) -> u16 {
        let listener = TcpListener::bind((DEFAULT_HOST, 0)).await.expect("bind");
        let port = listener.local_addr().expect("addr").port();
        let response_line = serde_json::to_string(&response).expect("response json");
        tokio::spawn(async move {
            let (socket, _) = listener.accept().await.expect("accept");
            let mut reader = BufReader::new(socket);
            let mut request_line = String::new();
            let _ = reader.read_line(&mut request_line).await;
            let mut socket = reader.into_inner();
            let _ = socket.write_all(response_line.as_bytes()).await;
            let _ = socket.write_all(b"\n").await;
        });
        port
    }

    #[tokio::test]
    async fn world_present_canonical_envelopes_preserve_verdicts() {
        let cases = [
            (
                verified_visibility_envelope(),
                "world_visibility_query",
                "verified",
                Value::Null,
                "Verified",
            ),
            (
                alpha_zero_envelope(),
                "world_visibility_query",
                "not_verified",
                json!("pixel_coverage_zero"),
                "Unconfirmed",
            ),
            (
                host_unreachable_envelope(),
                "world_query",
                "not_verified",
                json!("world_host_unreachable"),
                "Unconfirmed",
            ),
            (
                blocked_envelope(),
                "world_visibility_query",
                "blocked",
                json!("world_host_non_loopback_rejected"),
                "Blocked",
            ),
        ];
        let tool = WorldPresentTool::new();
        for (envelope, expected_tool, expected_verdict, expected_reason, card_label) in cases {
            let out = tool
                .execute(
                    json!({
                        "envelope": envelope,
                        "generated_at": "2026-06-06T00:00:00Z",
                        "commit": "test-commit"
                    }),
                    &ToolContext::default(),
                )
                .await
                .expect("execute");
            assert!(!out.is_error);
            let payload = result_text_as_json(&out);
            assert_eq!(payload["schema"], WORLD_PRESENT_SCHEMA);
            assert_eq!(payload["world_tool"], expected_tool);
            assert_eq!(payload["verdict"], expected_verdict);
            assert_eq!(payload["reason"], expected_reason);
            assert_eq!(
                payload["packet"]["schema"],
                crate::lswr_present::LSWR_PRESENT_PACKET_SCHEMA
            );
            assert_eq!(payload["packet"]["ingestion"]["allowed"], false);
            assert_eq!(payload["artifact"]["kind"], "html");
            assert_eq!(
                payload["artifact"]["static_render_status"],
                "rendered_static"
            );
            assert_eq!(payload["dual_encoding"], true);
            assert!(payload.get("source_envelope").is_none());

            let html = payload["artifact"]["html"].as_str().expect("html");
            assert!(html.contains(card_label), "missing label {card_label}");
            assert!(html.contains("Ingestion blocked"));
            if expected_verdict == "verified" {
                assert_eq!(
                    payload["packet"]["provenance"]["verified_to"],
                    "onsen_live_root_viewport"
                );
                assert_eq!(
                    payload["packet"]["human_readable"]["visible"],
                    json!(["bath"])
                );
            } else {
                assert!(payload["packet"]["provenance"]["verified_to"].is_null());
                assert_eq!(payload["packet"]["human_readable"]["visible"], json!([]));
                assert!(!html.contains("verified successfully"));
                assert!(!html.contains("World visibility verified"));
            }
        }
    }

    #[tokio::test]
    async fn world_present_writes_file_when_out_dir_is_provided() {
        let out_dir = std::env::temp_dir().join(format!(
            "ab-world-present-test-{}-{}",
            std::process::id(),
            crate::present::now_unix()
        ));
        let tool = WorldPresentTool::new();
        let out = tool
            .execute(
                json!({
                    "envelope": verified_visibility_envelope(),
                    "out_dir": out_dir.display().to_string(),
                    "include_raw": true,
                    "generated_at": "2026-06-06T00:00:00Z"
                }),
                &ToolContext::default(),
            )
            .await
            .expect("execute");
        assert!(!out.is_error);
        let payload = result_text_as_json(&out);
        assert_eq!(payload["artifact"]["kind"], "file");
        assert_eq!(
            payload["artifact"]["static_render_status"],
            "rendered_static"
        );
        assert_eq!(payload["dual_encoding"], true);
        assert_eq!(
            payload["source_envelope"]["schema"],
            crate::lswr_present::WORLD_TOOL_SCHEMA
        );
        let path = payload["artifact"]["path"].as_str().expect("path");
        let html = std::fs::read_to_string(path).expect("artifact file");
        let recovered = crate::present::extract_ab_payload(&html).expect("payload");
        assert_eq!(
            recovered["schema"],
            crate::lswr_present::LSWR_PRESENT_PACKET_SCHEMA
        );
        let _ = std::fs::remove_dir_all(&out_dir);
    }

    #[test]
    fn endpoint_resolution_prefers_params_and_rejects_non_loopback() {
        let _guard = ENV_LOCK.lock().unwrap_or_else(|e| e.into_inner());
        clear_endpoint_env();
        std::env::set_var(HOST_ADDR_ENV, "127.0.0.1:4000");
        std::env::set_var(HOST_PORT_ENV, "4001");
        std::env::set_var(ONSEN_HOST_PORT_ENV, "4004");
        let ep = WorldEndpoint::from_args(&json!({
            "host": "localhost:4002",
            "port": 4003,
            "timeout_ms": 10
        }))
        .expect("endpoint");
        assert_eq!(ep.host, "localhost");
        assert_eq!(ep.port, 4003);
        assert_eq!(ep.timeout_ms, MIN_TIMEOUT_MS);
        assert_eq!(
            WorldEndpoint::from_args(&json!({"host": "192.168.1.5"})).unwrap_err(),
            "world_host_non_loopback_rejected"
        );
        clear_endpoint_env();
    }

    #[test]
    fn endpoint_resolution_accepts_onsen_host_port_alias() {
        let _guard = ENV_LOCK.lock().unwrap_or_else(|e| e.into_inner());
        clear_endpoint_env();
        std::env::set_var(ONSEN_HOST_PORT_ENV, "4100");
        let alias = WorldEndpoint::from_args(&json!({})).expect("endpoint");
        assert_eq!(alias.host, DEFAULT_HOST);
        assert_eq!(alias.port, 4100);

        std::env::set_var(HOST_PORT_ENV, "4101");
        let explicit = WorldEndpoint::from_args(&json!({})).expect("endpoint");
        assert_eq!(explicit.port, 4101);
        clear_endpoint_env();
    }

    #[test]
    fn world_patch_request_defaults_visibility_to_entity() {
        let req = build_patch_request(&json!({
            "op": "move",
            "entity": "bath",
            "args": { "cell": [8, 0] },
            "expected_effect": {
                "target": "entity",
                "metric": "screen_area",
                "to_op": ">=",
                "to_value": 0.01
            },
            "debug_session": { "enter_operating_shift": true }
        }))
        .expect("request");
        assert_eq!(req["world.patch"]["op"], "move");
        assert_eq!(req["world.patch"]["entity"], "bath");
        assert_eq!(
            req["world.patch"]["expected_effect"]["metric"],
            "screen_area"
        );
        assert_eq!(req["world.visibility.query"]["entities"], json!(["bath"]));
        assert_eq!(req["debug.session"]["enter_operating_shift"], true);
    }

    #[test]
    fn visibility_request_requires_explicit_entities() {
        assert!(build_query_request(&json!({}), None).is_none());
        let req = build_query_request(&json!({"entities": ["bath"]}), None).expect("request");
        assert_eq!(req["world.visibility.query"]["entities"], json!(["bath"]));
    }

    #[tokio::test]
    async fn world_tool_envelope_includes_action_result_without_raw_host_response() {
        let port = spawn_one_response_host(json!({
            "ok": true,
            "verified": true,
            "render": {"source": "live_root_viewport_texture"},
            "flicker": {"frames": 1},
            "world.patch": {"accepted": true, "entity": "bath", "op": "move"},
            "world.visibility.query": {
                "after": {
                    "entities": [{
                        "id": "bath",
                        "screen_area": 0.12,
                        "bounds_screen_area": 0.2,
                        "occluded": false
                    }]
                }
            }
        }))
        .await;

        let out = WorldPatchTool::new()
            .execute(
                json!({
                    "request_id": "ssb3-patch",
                    "op": "move",
                    "entity": "bath",
                    "args": {"cell": [8, 0]},
                    "host": DEFAULT_HOST,
                    "port": port,
                    "include_raw": false
                }),
                &ToolContext::default(),
            )
            .await
            .expect("execute");
        assert!(!out.is_error);
        let payload = result_text_as_json(&out);
        assert_eq!(payload["schema"], WORLD_TOOL_SCHEMA);
        assert!(payload.get("host_response").is_none());
        assert_eq!(payload["verified"], true);
        assert_eq!(payload["action_result"]["schema"], ACTION_RESULT_SCHEMA);
        assert_eq!(payload["action_result"]["source_schema"], WORLD_TOOL_SCHEMA);
        assert_eq!(payload["action_result"]["adapter"], LSWR_ADAPTER);
        assert_eq!(payload["action_result"]["world_tool"], "world_patch");
        assert_eq!(payload["action_result"]["action_type"], "world.patch");
        assert_eq!(
            payload["action_result"]["action_id"],
            "lswr:world_patch:ssb3-patch:result"
        );
        assert_eq!(
            payload["action_result"]["subject_id"],
            "lswr:onsen:entity:bath"
        );
        assert_eq!(
            payload["action_result"]["event_ids"],
            json!(["evt-lswr-world_patch-ssb3-patch"])
        );
        assert_eq!(payload["action_result"]["verdict"], "verified");
        assert_eq!(payload["action_result"]["verified_to"], VERIFIED_TO);
        assert_eq!(
            payload["action_result"]["verification_method"],
            VERIFY_METHOD
        );
        assert_eq!(payload["action_result"]["recover"], "proceed");
        assert_eq!(payload["action_result"]["raw_available"], true);

        let present = WorldPresentTool::new()
            .execute(
                json!({
                    "envelope": payload,
                    "generated_at": "2026-06-07T00:00:00Z"
                }),
                &ToolContext::default(),
            )
            .await
            .expect("present");
        let present_payload = result_text_as_json(&present);
        assert_eq!(present_payload["world_tool"], "world_patch");
        assert_eq!(
            present_payload["packet"]["machine_payload"]["action_result"]["schema"],
            ACTION_RESULT_SCHEMA
        );
        assert_eq!(
            present_payload["packet"]["machine_payload"]["action_result"]["verdict"],
            "verified"
        );
    }

    #[tokio::test]
    async fn world_patch_applied_but_render_not_verified_stays_unconfirmed_without_raw() {
        let port = spawn_one_response_host(json!({
            "ok": true,
            "verified": false,
            "render": {"source": "live_root_viewport_texture"},
            "render_integrity": {
                "verified": false,
                "reason": "render_frozen_after_patch",
                "status": "checked",
                "model_changed": true,
                "signature_changed": false
            },
            "world.patch": {
                "requested": true,
                "applied": true,
                "op": "move",
                "entity": "bath",
                "source": "game_loop_director_live_patch_v0",
                "model": {"changed": true},
                "render_refresh": {
                    "requested": false,
                    "reason": "debug_freeze_render_after_patch"
                }
            },
            "world.visibility.query": {
                "after": {
                    "entities": [{
                        "id": "bath",
                        "verified": true,
                        "screen_area": 0.12,
                        "bounds_screen_area": 0.2,
                        "occluded": false
                    }]
                }
            }
        }))
        .await;

        let out = WorldPatchTool::new()
            .execute(
                json!({
                    "request_id": "f3-render-frozen",
                    "op": "move",
                    "entity": "bath",
                    "args": {"cell": [8, 0]},
                    "host": DEFAULT_HOST,
                    "port": port,
                    "include_raw": false
                }),
                &ToolContext::default(),
            )
            .await
            .expect("execute");
        assert!(!out.is_error);
        let payload = result_text_as_json(&out);
        assert_eq!(payload["schema"], WORLD_TOOL_SCHEMA);
        assert!(payload.get("host_response").is_none());
        assert_eq!(payload["verified"], false);
        assert_eq!(payload["reason"], "render_frozen_after_patch");
        assert_eq!(payload["world.patch"]["applied"], true);
        assert_eq!(payload["world.patch"]["model"]["changed"], true);
        assert_eq!(payload["action_result"]["world_tool"], "world_patch");
        assert_eq!(payload["action_result"]["verdict"], "not_verified");
        assert_eq!(
            payload["action_result"]["reason"],
            "render_frozen_after_patch"
        );
        assert!(payload["action_result"]["verified_to"].is_null());
        assert_eq!(
            payload["action_result"]["recover"],
            "inspect_host_or_visibility_evidence"
        );
        assert_eq!(
            payload["verify"]["evidence"]["host_reason"],
            "render_frozen_after_patch"
        );

        let present = WorldPresentTool::new()
            .execute(
                json!({
                    "envelope": payload,
                    "generated_at": "2026-06-08T00:00:00Z"
                }),
                &ToolContext::default(),
            )
            .await
            .expect("present");
        assert!(!present.is_error);
        let present_payload = result_text_as_json(&present);
        assert_eq!(present_payload["world_tool"], "world_patch");
        assert_eq!(present_payload["verdict"], "not_verified");
        assert_eq!(present_payload["reason"], "render_frozen_after_patch");
        assert_eq!(
            present_payload["packet"]["human_readable"]["changed"],
            json!(["bath"])
        );
        assert_eq!(
            present_payload["packet"]["human_readable"]["visible"],
            json!([])
        );
        assert!(present_payload["packet"]["provenance"]["verified_to"].is_null());
        assert_eq!(
            present_payload["packet"]["machine_payload"]["patch_result"]["applied"],
            true
        );
        assert_eq!(
            present_payload["packet"]["machine_payload"]["action_result"]["verdict"],
            "not_verified"
        );
    }

    #[tokio::test]
    async fn world_patch_expected_effect_failure_survives_without_raw() {
        let port = spawn_one_response_host(json!({
            "ok": true,
            "verified": false,
            "render": {"source": "live_root_viewport_texture"},
            "expected_effect": {
                "verified": false,
                "reason": "expected_effect_clause_failed",
                "clauses": [{
                    "target": "bath",
                    "metric": "screen_area",
                    "to_op": ">=",
                    "to_value": 0.25,
                    "actual": 0.12,
                    "verified": false,
                    "reason": "expected_effect_clause_failed"
                }]
            },
            "world.patch": {
                "requested": true,
                "applied": true,
                "op": "move",
                "entity": "bath",
                "source": "game_loop_director_live_patch_v0",
                "model": {"changed": true},
                "render_refresh": {"requested": true, "reason": ""}
            },
            "world.visibility.query": {
                "after": {
                    "entities": [{
                        "id": "bath",
                        "verified": true,
                        "screen_area": 0.12,
                        "bounds_screen_area": 0.2,
                        "pixel_coverage": {"estimated_changed_pixels": 1200},
                        "occluded": false
                    }]
                }
            }
        }))
        .await;

        let out = WorldPatchTool::new()
            .execute(
                json!({
                    "request_id": "f4-expected-effect",
                    "op": "move",
                    "entity": "bath",
                    "args": {"cell": [8, 0]},
                    "expected_effect": {
                        "target": "bath",
                        "metric": "screen_area",
                        "to_op": ">=",
                        "to_value": 0.25
                    },
                    "host": DEFAULT_HOST,
                    "port": port,
                    "include_raw": false
                }),
                &ToolContext::default(),
            )
            .await
            .expect("execute");
        assert!(!out.is_error);
        let payload = result_text_as_json(&out);
        assert!(payload.get("host_response").is_none());
        assert_eq!(payload["verified"], false);
        assert_eq!(payload["reason"], "expected_effect_clause_failed");
        assert_eq!(payload["world.patch"]["applied"], true);
        assert_eq!(payload["expected_effect"]["verified"], false);
        assert_eq!(
            payload["expected_effect"]["clauses"][0]["actual"],
            json!(0.12)
        );
        assert_eq!(payload["action_result"]["verdict"], "not_verified");
        assert_eq!(
            payload["verify"]["evidence"]["host_reason"],
            "expected_effect_clause_failed"
        );

        let present = WorldPresentTool::new()
            .execute(
                json!({
                    "envelope": payload,
                    "generated_at": "2026-06-08T00:00:00Z"
                }),
                &ToolContext::default(),
            )
            .await
            .expect("present");
        assert!(!present.is_error);
        let present_payload = result_text_as_json(&present);
        assert_eq!(present_payload["verdict"], "not_verified");
        assert_eq!(present_payload["reason"], "expected_effect_clause_failed");
        assert_eq!(
            present_payload["packet"]["machine_payload"]["expected_effect"]["verified"],
            false
        );
        assert_eq!(
            present_payload["packet"]["machine_payload"]["patch_result"]["applied"],
            true
        );
        assert!(present_payload["packet"]["provenance"]["verified_to"].is_null());
    }

    #[tokio::test]
    async fn blocked_world_action_result_is_not_laundered() {
        let out = WorldVisibilityQueryTool::new()
            .execute(
                json!({
                    "request_id": "ssb3-blocked",
                    "entities": ["bath"],
                    "host": "192.168.1.5"
                }),
                &ToolContext::default(),
            )
            .await
            .expect("execute");
        assert!(!out.is_error);
        let payload = result_text_as_json(&out);
        assert_eq!(payload["schema"], WORLD_TOOL_SCHEMA);
        assert_eq!(payload["verified"], false);
        assert_eq!(payload["reason"], "world_host_non_loopback_rejected");
        assert_eq!(
            payload["action_result"]["world_tool"],
            "world_visibility_query"
        );
        assert_eq!(
            payload["action_result"]["action_type"],
            "world.visibility.query"
        );
        assert_eq!(payload["action_result"]["verdict"], "blocked");
        assert!(payload["action_result"]["verified_to"].is_null());
        assert_eq!(payload["action_result"]["recover"], "replan");
        assert_eq!(payload["action_result"]["raw_available"], false);
        assert_eq!(
            payload["action_result"]["event_ids"],
            json!(["evt-lswr-world_visibility_query-ssb3-blocked"])
        );
    }

    #[test]
    fn verified_to_is_only_set_when_host_verified() {
        let ep = WorldEndpoint {
            host: DEFAULT_HOST.to_string(),
            port: DEFAULT_PORT,
            timeout_ms: DEFAULT_TIMEOUT_MS,
        };
        let req = json!({"request_id":"r1"});
        let good = wrap_host_response_with_tool(
            &ep,
            &req,
            json!({
                "ok": true,
                "verified": true,
                "render": {"source": "live_root_viewport_texture"},
                "flicker": {"frames": 2},
                "world.visibility.query": {"after": {"entities": [{"screen_area": 0.1}]}}
            }),
            "world_query",
        );
        assert_eq!(good["verify"]["verified_to"], VERIFIED_TO);
        let bad = wrap_host_response_with_tool(
            &ep,
            &req,
            json!({"ok": true, "verified": false}),
            "world_query",
        );
        assert!(bad["verify"]["verified_to"].is_null());
    }

    #[test]
    fn nested_entity_reason_lifts_into_envelope_without_raw_host_response() {
        let ep = WorldEndpoint {
            host: DEFAULT_HOST.to_string(),
            port: DEFAULT_PORT,
            timeout_ms: DEFAULT_TIMEOUT_MS,
        };
        let req = json!({"request_id":"nested-reason"});
        let mut result = wrap_host_response_with_tool(
            &ep,
            &req,
            json!({
                "ok": true,
                "verified": false,
                "render": {"source": "live_root_viewport_texture"},
                "world.visibility.query": {
                    "after": {
                        "entities": [{
                            "entity": "bath",
                            "reason": "pixel_coverage_zero",
                            "screen_area": 0.0,
                            "bounds_screen_area": 0.0186
                        }]
                    }
                }
            }),
            "world_query",
        );
        assert_eq!(result["reason"], "pixel_coverage_zero");
        assert_eq!(
            result["verify"]["evidence"]["host_reason"],
            "pixel_coverage_zero"
        );
        result.as_object_mut().unwrap().remove("host_response");
        assert_eq!(result["reason"], "pixel_coverage_zero");
        assert_eq!(
            result["verify"]["evidence"]["host_reason"],
            "pixel_coverage_zero"
        );

        let nested_pixel_reason = wrap_host_response_with_tool(
            &ep,
            &req,
            json!({
                "ok": true,
                "verified": false,
                "world.visibility.query": {
                    "after": {
                        "entities": [{
                            "entity": "bath",
                            "reason": "",
                            "pixel_coverage": {"reason": "pixel_coverage_zero"}
                        }]
                    }
                }
            }),
            "world_query",
        );
        assert_eq!(nested_pixel_reason["reason"], "pixel_coverage_zero");
    }

    #[tokio::test]
    async fn malformed_host_response_returns_structured_not_verified() {
        let listener = TcpListener::bind((DEFAULT_HOST, 0)).await.expect("bind");
        let port = listener.local_addr().expect("addr").port();
        tokio::spawn(async move {
            let (mut socket, _) = listener.accept().await.expect("accept");
            let _ = socket.write_all(b"not-json\n").await;
        });
        let ep = WorldEndpoint {
            host: DEFAULT_HOST.to_string(),
            port,
            timeout_ms: 1_000,
        };
        let result =
            call_world_host_with_tool(&ep, &json!({"request_id":"bad"}), "world_query").await;
        assert_eq!(result["verified"], false);
        assert_eq!(result["reason"], "world_host_malformed_response");
    }

    #[tokio::test]
    async fn unreachable_host_returns_structured_not_verified() {
        let listener = TcpListener::bind((DEFAULT_HOST, 0)).await.expect("bind");
        let port = listener.local_addr().expect("addr").port();
        drop(listener);
        let ep = WorldEndpoint {
            host: DEFAULT_HOST.to_string(),
            port,
            timeout_ms: 1_000,
        };
        let result =
            call_world_host_with_tool(&ep, &json!({"request_id":"down"}), "world_query").await;
        assert_eq!(result["verified"], false);
        assert_eq!(result["reason"], "world_host_unreachable");
    }

    #[tokio::test]
    async fn read_timeout_returns_structured_not_verified() {
        let listener = TcpListener::bind((DEFAULT_HOST, 0)).await.expect("bind");
        let port = listener.local_addr().expect("addr").port();
        tokio::spawn(async move {
            let (_socket, _) = listener.accept().await.expect("accept");
            tokio::time::sleep(Duration::from_millis(MIN_TIMEOUT_MS * 2)).await;
        });
        let ep = WorldEndpoint {
            host: DEFAULT_HOST.to_string(),
            port,
            timeout_ms: MIN_TIMEOUT_MS,
        };
        let result =
            call_world_host_with_tool(&ep, &json!({"request_id":"timeout"}), "world_query").await;
        assert_eq!(result["verified"], false);
        assert_eq!(result["reason"], "world_host_timeout");
    }
}
