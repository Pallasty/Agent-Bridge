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
use std::time::{Duration, SystemTime, UNIX_EPOCH};
use tokio::io::{AsyncBufReadExt, AsyncWriteExt, BufReader};
use tokio::net::TcpStream;

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

    let mut request = serde_json::Map::new();
    request.insert(
        "request_id".to_string(),
        json!(args
            .get("request_id")
            .and_then(Value::as_str)
            .map(str::to_string)
            .unwrap_or_else(|| request_id("ab-world-patch"))),
    );
    request.insert(
        "world.patch".to_string(),
        json!({
            "op": op,
            "entity": entity,
            "args": patch_args,
        }),
    );
    request.insert(
        "world.visibility.query".to_string(),
        json!({ "entities": visibility_entities }),
    );
    copy_debug_fields(args, &mut request);
    Ok(Value::Object(request))
}

async fn call_world_host(endpoint: &WorldEndpoint, request: &Value) -> Value {
    let timeout_dur = Duration::from_millis(endpoint.timeout_ms);
    let mut stream = match tokio::time::timeout(
        timeout_dur,
        TcpStream::connect((endpoint.host.as_str(), endpoint.port)),
    )
    .await
    {
        Ok(Ok(s)) => s,
        Ok(Err(e)) => {
            return not_verified_envelope(
                "world_host_unreachable",
                endpoint,
                request,
                Some(e.to_string()),
            )
        }
        Err(_) => {
            return not_verified_envelope("world_host_timeout", endpoint, request, None);
        }
    };

    let line = match serde_json::to_string(request) {
        Ok(s) => format!("{s}\n"),
        Err(e) => {
            return not_verified_envelope(
                "world_request_malformed",
                endpoint,
                request,
                Some(e.to_string()),
            )
        }
    };
    match tokio::time::timeout(timeout_dur, stream.write_all(line.as_bytes())).await {
        Ok(Ok(())) => {}
        Ok(Err(e)) => {
            return not_verified_envelope(
                "world_host_unreachable",
                endpoint,
                request,
                Some(e.to_string()),
            )
        }
        Err(_) => return not_verified_envelope("world_host_timeout", endpoint, request, None),
    }

    let mut reader = BufReader::new(stream);
    let mut response_line = String::new();
    match tokio::time::timeout(timeout_dur, reader.read_line(&mut response_line)).await {
        Ok(Ok(0)) => {
            return not_verified_envelope(
                "world_host_malformed_response",
                endpoint,
                request,
                Some("empty response".to_string()),
            )
        }
        Ok(Ok(_)) => {}
        Ok(Err(e)) => {
            return not_verified_envelope(
                "world_host_unreachable",
                endpoint,
                request,
                Some(e.to_string()),
            )
        }
        Err(_) => return not_verified_envelope("world_host_timeout", endpoint, request, None),
    }
    match serde_json::from_str::<Value>(response_line.trim()) {
        Ok(host_response) => wrap_host_response(endpoint, request, host_response),
        Err(e) => not_verified_envelope(
            "world_host_malformed_response",
            endpoint,
            request,
            Some(e.to_string()),
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
        &["world.visibility.query", "after", "reason"][..],
    ] {
        if let Some(v) = get_path(host_response, path) {
            if !v.is_null() {
                return v.clone();
            }
        }
    }
    Value::Null
}

fn get_path<'a>(value: &'a Value, path: &[&str]) -> Option<&'a Value> {
    let mut cur = value;
    for key in path {
        cur = cur.get(*key)?;
    }
    Some(cur)
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

fn wrap_host_response(endpoint: &WorldEndpoint, request: &Value, host_response: Value) -> Value {
    let verified = host_verified(&host_response);
    let reason = host_reason(&host_response);
    json!({
        "schema": "agent_bridge.world_tool.v0",
        "ok": host_response.get("ok").and_then(Value::as_bool).unwrap_or(verified),
        "verified": verified,
        "reason": reason,
        "endpoint": {
            "host": endpoint.host,
            "port": endpoint.port,
            "timeout_ms": endpoint.timeout_ms,
        },
        "request": request,
        "verify": verify_block(verified, Some(&host_response), host_reason(&host_response)),
        "host_response": host_response,
    })
}

fn not_verified_envelope(
    reason: &str,
    endpoint: &WorldEndpoint,
    request: &Value,
    detail: Option<String>,
) -> Value {
    json!({
        "schema": "agent_bridge.world_tool.v0",
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
        "host_response": Value::Null,
    })
}

enum WorldEndpointOrEnvelope {
    Endpoint(WorldEndpoint),
    Envelope(Value),
}

trait EndpointEnvelope {
    fn as_not_verified(self, reason: &str, request: &Value) -> WorldEndpointOrEnvelope;
}

impl EndpointEnvelope for WorldEndpoint {
    fn as_not_verified(self, reason: &str, request: &Value) -> WorldEndpointOrEnvelope {
        WorldEndpointOrEnvelope::Envelope(not_verified_envelope(reason, &self, request, None))
    }
}

impl From<WorldEndpoint> for WorldEndpointOrEnvelope {
    fn from(value: WorldEndpoint) -> Self {
        Self::Endpoint(value)
    }
}

fn endpoint_or_envelope(args: &Value, request: &Value) -> WorldEndpointOrEnvelope {
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
            endpoint.as_not_verified(&reason, request)
        }
    }
}

async fn execute_with_endpoint(args: Value, request: Value) -> Result<ToolResult> {
    let include_raw = args
        .get("include_raw")
        .and_then(Value::as_bool)
        .unwrap_or(true);
    let mut result = match endpoint_or_envelope(&args, &request) {
        WorldEndpointOrEnvelope::Endpoint(endpoint) => call_world_host(&endpoint, &request).await,
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
        execute_with_endpoint(args, request).await
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
        execute_with_endpoint(args, request).await
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
        execute_with_endpoint(args, request).await
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use tokio::net::TcpListener;

    static ENV_LOCK: std::sync::Mutex<()> = std::sync::Mutex::new(());

    fn clear_endpoint_env() {
        std::env::remove_var(HOST_ADDR_ENV);
        std::env::remove_var(HOST_PORT_ENV);
        std::env::remove_var(ONSEN_HOST_PORT_ENV);
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
            "debug_session": { "enter_operating_shift": true }
        }))
        .expect("request");
        assert_eq!(req["world.patch"]["op"], "move");
        assert_eq!(req["world.patch"]["entity"], "bath");
        assert_eq!(req["world.visibility.query"]["entities"], json!(["bath"]));
        assert_eq!(req["debug.session"]["enter_operating_shift"], true);
    }

    #[test]
    fn visibility_request_requires_explicit_entities() {
        assert!(build_query_request(&json!({}), None).is_none());
        let req = build_query_request(&json!({"entities": ["bath"]}), None).expect("request");
        assert_eq!(req["world.visibility.query"]["entities"], json!(["bath"]));
    }

    #[test]
    fn verified_to_is_only_set_when_host_verified() {
        let ep = WorldEndpoint {
            host: DEFAULT_HOST.to_string(),
            port: DEFAULT_PORT,
            timeout_ms: DEFAULT_TIMEOUT_MS,
        };
        let req = json!({"request_id":"r1"});
        let good = wrap_host_response(
            &ep,
            &req,
            json!({
                "ok": true,
                "verified": true,
                "render": {"source": "live_root_viewport_texture"},
                "flicker": {"frames": 2},
                "world.visibility.query": {"after": {"entities": [{"screen_area": 0.1}]}}
            }),
        );
        assert_eq!(good["verify"]["verified_to"], VERIFIED_TO);
        let bad = wrap_host_response(&ep, &req, json!({"ok": true, "verified": false}));
        assert!(bad["verify"]["verified_to"].is_null());
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
        let result = call_world_host(&ep, &json!({"request_id":"bad"})).await;
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
        let result = call_world_host(&ep, &json!({"request_id":"down"})).await;
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
        let result = call_world_host(&ep, &json!({"request_id":"timeout"})).await;
        assert_eq!(result["verified"], false);
        assert_eq!(result["reason"], "world_host_timeout");
    }
}
