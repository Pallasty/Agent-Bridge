//! Synthetic Streamable HTTP/OAuth resource-server lab.
//!
//! This module is deliberately not a production authorization server. It only
//! accepts a loopback resource URL, reads public RSA keys from a static JWKS,
//! and exposes one read-only subject diagnostic after every request passes the
//! configured token and local-subject policy checks.

use crate::protocol::{
    InitializeResult, McpRequest, McpResponse, ServerCapabilities, ServerInfo, ToolDefinition,
    ToolsCapability, INTERNAL_ERROR, INVALID_PARAMS, INVALID_REQUEST, METHOD_NOT_FOUND,
};
use crate::{
    McpTool, McpTransportKind, ToolAnnotations, ToolContext, ToolRegistry, ToolResult, ToolSchema,
    ToolSecurityScheme, VerifiedOAuthSubject,
};
use ab_core::{Error, Result};
use async_trait::async_trait;
use axum::body::{to_bytes, Body};
use axum::extract::State;
use axum::http::header::{ACCEPT, ALLOW, AUTHORIZATION, CONTENT_TYPE, ORIGIN, WWW_AUTHENTICATE};
use axum::http::{HeaderMap, HeaderName, HeaderValue, Request, StatusCode};
use axum::response::{IntoResponse, Response};
use axum::routing::get;
use axum::{Json, Router};
use jsonwebtoken::{decode, decode_header, Algorithm, DecodingKey, Validation};
use serde::{Deserialize, Serialize};
use serde_json::{json, Value};
use sha2::{Digest, Sha256};
use std::collections::{BTreeSet, HashMap, HashSet};
use std::net::{IpAddr, SocketAddr};
use std::path::PathBuf;
use std::sync::Arc;
use std::time::{SystemTime, UNIX_EPOCH};
use url::Url;

pub const STREAMABLE_HTTP_PROTOCOL_VERSION: &str = "2025-11-25";
const COMPATIBLE_HTTP_PROTOCOL_VERSIONS: &[&str] = &["2025-11-25", "2025-06-18", "2025-03-26"];
const PROTOCOL_VERSION_HEADER: HeaderName = HeaderName::from_static("mcp-protocol-version");
const LAB_MODE: &str = "synthetic_lab";
const MCP_PATH: &str = "/mcp";
const RESOURCE_METADATA_PATH: &str = "/.well-known/oauth-protected-resource";
const MAX_MCP_BODY_BYTES: usize = 256 * 1024;

#[derive(Debug, Deserialize)]
#[serde(deny_unknown_fields)]
struct RawLabConfig {
    mode: String,
    listen: String,
    resource: String,
    issuer: String,
    authorization_servers: Vec<String>,
    required_scopes: Vec<String>,
    allowed_origins: Vec<String>,
    jwks: RawJwkSet,
    subjects: Vec<RawSubjectPolicy>,
    #[serde(default = "default_clock_skew_secs")]
    clock_skew_secs: u64,
    #[serde(default = "default_max_token_lifetime_secs")]
    max_token_lifetime_secs: u64,
}

#[derive(Debug, Deserialize)]
#[serde(deny_unknown_fields)]
struct RawJwkSet {
    keys: Vec<RawRsaJwk>,
}

#[derive(Debug, Deserialize)]
#[serde(deny_unknown_fields)]
struct RawRsaJwk {
    kty: String,
    kid: String,
    alg: String,
    #[serde(rename = "use")]
    key_use: Option<String>,
    n: String,
    e: String,
}

#[derive(Debug, Deserialize)]
#[serde(deny_unknown_fields)]
struct RawSubjectPolicy {
    subject: String,
    local_subject: String,
    #[serde(default)]
    allowed_client_ids: Vec<String>,
}

#[derive(Debug)]
struct SubjectPolicy {
    local_subject: String,
    allowed_client_ids: BTreeSet<String>,
}

struct LabConfig {
    listen: SocketAddr,
    resource: String,
    issuer: String,
    authorization_servers: Vec<String>,
    required_scopes: BTreeSet<String>,
    allowed_origins: BTreeSet<String>,
    metadata_url: String,
    keys: HashMap<String, DecodingKey>,
    subjects: HashMap<String, SubjectPolicy>,
    clock_skew_secs: u64,
    max_token_lifetime_secs: u64,
}

#[derive(Clone)]
struct LabState {
    config: Arc<LabConfig>,
    registry: ToolRegistry,
}

#[derive(Debug, Deserialize)]
struct JwtClaims {
    iss: String,
    sub: String,
    aud: AudienceClaim,
    exp: u64,
    nbf: Option<u64>,
    iat: u64,
    scope: Option<String>,
    scp: Option<Vec<String>>,
    client_id: Option<String>,
}

#[derive(Debug, Deserialize)]
#[serde(untagged)]
enum AudienceClaim {
    One(String),
    Many(Vec<String>),
}

impl AudienceClaim {
    fn into_set(self) -> BTreeSet<String> {
        match self {
            Self::One(value) => [value].into_iter().collect(),
            Self::Many(values) => values.into_iter().collect(),
        }
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
enum AuthFailureKind {
    Unauthorized,
    Forbidden,
}

#[derive(Debug)]
struct AuthFailure {
    kind: AuthFailureKind,
    code: &'static str,
}

#[derive(Debug)]
enum RequestAuthFailure {
    InvalidOrigin,
    OAuth(AuthFailure),
}

impl AuthFailure {
    const fn unauthorized(code: &'static str) -> Self {
        Self {
            kind: AuthFailureKind::Unauthorized,
            code,
        }
    }

    const fn forbidden(code: &'static str) -> Self {
        Self {
            kind: AuthFailureKind::Forbidden,
            code,
        }
    }
}

fn default_clock_skew_secs() -> u64 {
    30
}

fn default_max_token_lifetime_secs() -> u64 {
    900
}

/// Start the default-off synthetic HTTP/OAuth lab from an explicit JSON file.
pub async fn serve_from_path(path: PathBuf) -> Result<()> {
    let raw = tokio::fs::read_to_string(&path).await.map_err(|error| {
        Error::InvalidArgument(format!(
            "read synthetic lab config {}: {error}",
            path.display()
        ))
    })?;
    let state = state_from_json(&raw)?;
    let listen = state.config.listen;
    let resource = state.config.resource.clone();
    let app = router(state);
    let listener = tokio::net::TcpListener::bind(listen).await?;

    tracing::warn!(
        %listen,
        %resource,
        synthetic_lab = true,
        execution_allowed = false,
        "synthetic MCP HTTP/OAuth lab listening; not for production"
    );

    axum::serve(listener, app)
        .await
        .map_err(|error| Error::Backend(format!("synthetic HTTP/OAuth lab failed: {error}")))
}

fn state_from_json(raw: &str) -> Result<LabState> {
    let raw: RawLabConfig = serde_json::from_str(raw)?;
    let config = Arc::new(validate_config(raw)?);
    let mut registry = ToolRegistry::new();
    registry.register(Arc::new(OAuthSubjectDiagnostic {
        required_scopes: config.required_scopes.iter().cloned().collect(),
    }));
    Ok(LabState { config, registry })
}

fn validate_config(raw: RawLabConfig) -> Result<LabConfig> {
    if raw.mode != LAB_MODE {
        return invalid("config mode must be exactly 'synthetic_lab'");
    }

    let listen = raw
        .listen
        .parse::<SocketAddr>()
        .map_err(|error| Error::InvalidArgument(format!("invalid listen socket: {error}")))?;
    if !listen.ip().is_loopback() {
        return invalid("synthetic lab listener must use a loopback IP address");
    }

    let resource_url = parse_url(&raw.resource, "resource")?;
    if resource_url.scheme() != "http"
        || resource_url.username() != ""
        || resource_url.password().is_some()
        || resource_url.query().is_some()
        || resource_url.fragment().is_some()
        || resource_url.path() != MCP_PATH
    {
        return invalid("resource must be an uncredentialed http loopback URL ending in /mcp");
    }
    let resource_ip = resource_url
        .host_str()
        .and_then(|host| host.parse::<IpAddr>().ok())
        .ok_or_else(|| Error::InvalidArgument("resource host must be a loopback IP".into()))?;
    if resource_ip != listen.ip() || resource_url.port_or_known_default() != Some(listen.port()) {
        return invalid("resource URL and listener must identify the same loopback socket");
    }

    parse_authority_url(&raw.issuer, "issuer")?;
    let issuer = raw.issuer.trim().to_string();
    if raw.authorization_servers.is_empty() {
        return invalid("authorization_servers must contain the configured issuer");
    }
    let mut authorization_servers = Vec::with_capacity(raw.authorization_servers.len());
    for value in raw.authorization_servers {
        parse_authority_url(&value, "authorization server")?;
        let normalized = value.trim().to_string();
        if !authorization_servers.contains(&normalized) {
            authorization_servers.push(normalized);
        }
    }
    if !authorization_servers.contains(&issuer) {
        return invalid("authorization_servers must contain the exact configured issuer");
    }

    let required_scopes = validated_tokens(raw.required_scopes, "required scope")?;
    if required_scopes.is_empty() {
        return invalid("required_scopes must not be empty");
    }

    let mut allowed_origins = BTreeSet::new();
    for origin in raw.allowed_origins {
        let parsed = parse_url(&origin, "allowed origin")?;
        if parsed.username() != ""
            || parsed.password().is_some()
            || parsed.query().is_some()
            || parsed.fragment().is_some()
            || !matches!(parsed.path(), "" | "/")
        {
            return invalid(
                "allowed origins must not include credentials, paths, queries, or fragments",
            );
        }
        let normalized = parsed.origin().ascii_serialization();
        let loopback_http = parsed.scheme() == "http"
            && parsed
                .host_str()
                .and_then(|host| host.parse::<IpAddr>().ok())
                .is_some_and(|ip| ip.is_loopback());
        if parsed.scheme() != "https" && !loopback_http {
            return invalid("allowed origins must use https or loopback http");
        }
        allowed_origins.insert(normalized);
    }
    if allowed_origins.is_empty() {
        return invalid("allowed_origins must not be empty");
    }

    if raw.clock_skew_secs > 300 {
        return invalid("clock_skew_secs must be at most 300");
    }
    if raw.max_token_lifetime_secs == 0 || raw.max_token_lifetime_secs > 3600 {
        return invalid("max_token_lifetime_secs must be between 1 and 3600");
    }

    let mut keys = HashMap::new();
    for jwk in raw.jwks.keys {
        if jwk.kty != "RSA" || jwk.alg != "RS256" || jwk.key_use.as_deref() != Some("sig") {
            return invalid("every synthetic JWKS key must declare kty=RSA, alg=RS256, use=sig");
        }
        if !(300..=1024).contains(&jwk.n.len()) || !(1..=16).contains(&jwk.e.len()) {
            return invalid("synthetic RSA JWK components are outside the accepted size bounds");
        }
        validate_policy_token(&jwk.kid, "JWKS kid")?;
        if keys.contains_key(&jwk.kid) {
            return invalid("duplicate JWKS kid");
        }
        let key = DecodingKey::from_rsa_components(&jwk.n, &jwk.e).map_err(|error| {
            Error::InvalidArgument(format!(
                "invalid RSA components for kid {}: {error}",
                jwk.kid
            ))
        })?;
        keys.insert(jwk.kid, key);
    }
    if keys.is_empty() {
        return invalid("JWKS must contain at least one RSA signing key");
    }

    let mut subjects = HashMap::new();
    for subject in raw.subjects {
        validate_policy_token(&subject.subject, "external subject")?;
        validate_policy_token(&subject.local_subject, "local subject")?;
        if subjects.contains_key(&subject.subject) {
            return invalid("duplicate external subject policy");
        }
        let allowed_client_ids = validated_tokens(subject.allowed_client_ids, "client id")?;
        subjects.insert(
            subject.subject,
            SubjectPolicy {
                local_subject: subject.local_subject,
                allowed_client_ids,
            },
        );
    }
    if subjects.is_empty() {
        return invalid("subjects must contain at least one exact mapping");
    }

    let mut metadata_url = resource_url.clone();
    metadata_url.set_path(RESOURCE_METADATA_PATH);

    Ok(LabConfig {
        listen,
        resource: resource_url.to_string(),
        issuer,
        authorization_servers,
        required_scopes,
        allowed_origins,
        metadata_url: metadata_url.to_string(),
        keys,
        subjects,
        clock_skew_secs: raw.clock_skew_secs,
        max_token_lifetime_secs: raw.max_token_lifetime_secs,
    })
}

fn invalid<T>(message: impl Into<String>) -> Result<T> {
    Err(Error::InvalidArgument(message.into()))
}

fn parse_url(raw: &str, field: &str) -> Result<Url> {
    Url::parse(raw.trim())
        .map_err(|error| Error::InvalidArgument(format!("invalid {field} URL: {error}")))
}

fn parse_authority_url(raw: &str, field: &str) -> Result<Url> {
    let parsed = parse_url(raw, field)?;
    if parsed.username() != ""
        || parsed.password().is_some()
        || parsed.query().is_some()
        || parsed.fragment().is_some()
    {
        return invalid(format!(
            "{field} URL must not contain credentials, query, or fragment"
        ));
    }
    let loopback_http = parsed.scheme() == "http"
        && parsed
            .host_str()
            .and_then(|host| host.parse::<IpAddr>().ok())
            .is_some_and(|ip| ip.is_loopback());
    if parsed.scheme() != "https" && !loopback_http {
        return invalid(format!("{field} URL must use https or loopback http"));
    }
    Ok(parsed)
}

fn validated_tokens(values: Vec<String>, field: &str) -> Result<BTreeSet<String>> {
    let mut validated = BTreeSet::new();
    for value in values {
        validate_policy_token(&value, field)?;
        validated.insert(value);
    }
    Ok(validated)
}

fn validate_policy_token(value: &str, field: &str) -> Result<()> {
    if !is_policy_token(value) {
        return invalid(format!("{field} contains unsupported characters"));
    }
    Ok(())
}

fn is_policy_token(value: &str) -> bool {
    !value.is_empty()
        && value.len() <= 256
        && value
            .bytes()
            .all(|byte| byte.is_ascii_alphanumeric() || b"-._:/@".contains(&byte))
}

fn router(state: LabState) -> Router {
    Router::new()
        .route(RESOURCE_METADATA_PATH, get(resource_metadata))
        .route(MCP_PATH, get(mcp_get).post(mcp_post).delete(mcp_delete))
        .with_state(state)
}

async fn resource_metadata(State(state): State<LabState>) -> Json<Value> {
    Json(json!({
        "resource": state.config.resource,
        "authorization_servers": state.config.authorization_servers,
        "scopes_supported": state.config.required_scopes,
    }))
}

async fn mcp_get(State(state): State<LabState>, headers: HeaderMap) -> Response {
    if let Err(failure) = authorize_request(&state, &headers) {
        return request_auth_failure_response(&state.config, failure);
    }
    if !valid_protocol_header(&headers) {
        return json_error(StatusCode::BAD_REQUEST, "unsupported_protocol_version");
    }
    let mut response = StatusCode::METHOD_NOT_ALLOWED.into_response();
    response
        .headers_mut()
        .insert(ALLOW, HeaderValue::from_static("POST"));
    response
}

async fn mcp_delete(State(state): State<LabState>, headers: HeaderMap) -> Response {
    if let Err(failure) = authorize_request(&state, &headers) {
        return request_auth_failure_response(&state.config, failure);
    }
    if !valid_protocol_header(&headers) {
        return json_error(StatusCode::BAD_REQUEST, "unsupported_protocol_version");
    }
    StatusCode::METHOD_NOT_ALLOWED.into_response()
}

async fn mcp_post(State(state): State<LabState>, request: Request<Body>) -> Response {
    let (parts, body) = request.into_parts();
    let headers = parts.headers;
    let subject = match authorize_request(&state, &headers) {
        Ok(subject) => subject,
        Err(failure) => return request_auth_failure_response(&state.config, failure),
    };

    if !valid_protocol_header(&headers) {
        return json_error(StatusCode::BAD_REQUEST, "unsupported_protocol_version");
    }
    if !accepts_streamable_http(&headers) {
        return json_error(StatusCode::NOT_ACCEPTABLE, "invalid_accept");
    }
    if !has_json_content_type(&headers) {
        return json_error(StatusCode::UNSUPPORTED_MEDIA_TYPE, "invalid_content_type");
    }

    let body = match to_bytes(body, MAX_MCP_BODY_BYTES).await {
        Ok(body) => body,
        Err(_) => return json_error(StatusCode::PAYLOAD_TOO_LARGE, "request_body_too_large"),
    };

    let value: Value = match serde_json::from_slice(&body) {
        Ok(value) => value,
        Err(_) => {
            return json_rpc_http_error(
                StatusCode::BAD_REQUEST,
                None,
                INVALID_REQUEST,
                "invalid JSON",
            )
        }
    };
    if !value.is_object() {
        return json_rpc_http_error(
            StatusCode::BAD_REQUEST,
            None,
            INVALID_REQUEST,
            "MCP batching is not supported",
        );
    }

    if value.get("method").is_none() {
        let is_response = value.get("jsonrpc") == Some(&Value::String("2.0".into()))
            && value.get("id").is_some()
            && (value.get("result").is_some() ^ value.get("error").is_some());
        return if is_response {
            StatusCode::ACCEPTED.into_response()
        } else {
            json_rpc_http_error(
                StatusCode::BAD_REQUEST,
                value.get("id").cloned(),
                INVALID_REQUEST,
                "invalid JSON-RPC message",
            )
        };
    }

    let request: McpRequest = match serde_json::from_value(value) {
        Ok(request) => request,
        Err(_) => {
            return json_rpc_http_error(
                StatusCode::BAD_REQUEST,
                None,
                INVALID_REQUEST,
                "invalid MCP request",
            )
        }
    };
    if request.jsonrpc != "2.0" {
        return json_rpc_http_error(
            StatusCode::BAD_REQUEST,
            request.id,
            INVALID_REQUEST,
            "jsonrpc must be 2.0",
        );
    }
    if request.id.is_none() {
        return StatusCode::ACCEPTED.into_response();
    }

    let response = dispatch_request(&state, request, subject).await;
    (StatusCode::OK, Json(response)).into_response()
}

fn authorize_request(
    state: &LabState,
    headers: &HeaderMap,
) -> std::result::Result<VerifiedOAuthSubject, RequestAuthFailure> {
    if !valid_origin(&state.config, headers) {
        return Err(RequestAuthFailure::InvalidOrigin);
    }

    let token = match bearer_token(headers) {
        Some(token) => token,
        None => {
            return Err(RequestAuthFailure::OAuth(AuthFailure::unauthorized(
                "missing_bearer_token",
            )))
        }
    };

    verify_token(&state.config, token).map_err(RequestAuthFailure::OAuth)
}

fn valid_origin(config: &LabConfig, headers: &HeaderMap) -> bool {
    let mut values = headers.get_all(ORIGIN).iter();
    let Some(value) = values.next() else {
        return true;
    };
    if values.next().is_some() {
        return false;
    }
    value
        .to_str()
        .ok()
        .is_some_and(|origin| config.allowed_origins.contains(origin))
}

fn bearer_token(headers: &HeaderMap) -> Option<&str> {
    let mut values = headers.get_all(AUTHORIZATION).iter();
    let value = values.next()?.to_str().ok()?;
    if values.next().is_some() {
        return None;
    }
    let token = value.strip_prefix("Bearer ")?;
    (!token.is_empty() && !token.bytes().any(|byte| byte.is_ascii_whitespace())).then_some(token)
}

fn verify_token(
    config: &LabConfig,
    token: &str,
) -> std::result::Result<VerifiedOAuthSubject, AuthFailure> {
    let header = decode_header(token).map_err(|_| AuthFailure::unauthorized("invalid_token"))?;
    if header.alg != Algorithm::RS256 {
        return Err(AuthFailure::unauthorized("unsupported_token_algorithm"));
    }
    let kid = header
        .kid
        .as_deref()
        .ok_or_else(|| AuthFailure::unauthorized("missing_token_kid"))?;
    let key = config
        .keys
        .get(kid)
        .ok_or_else(|| AuthFailure::unauthorized("unknown_token_kid"))?;

    let mut validation = Validation::new(Algorithm::RS256);
    validation.leeway = config.clock_skew_secs;
    validation.validate_nbf = true;
    validation.set_issuer(&[config.issuer.as_str()]);
    validation.set_audience(&[config.resource.as_str()]);
    validation.required_spec_claims = HashSet::from_iter(
        ["exp", "iss", "sub", "aud", "iat"]
            .into_iter()
            .map(str::to_string),
    );

    let claims = decode::<JwtClaims>(token, key, &validation)
        .map_err(|_| AuthFailure::unauthorized("invalid_token"))?
        .claims;
    if claims.iss != config.issuer || claims.sub.trim().is_empty() {
        return Err(AuthFailure::unauthorized("invalid_token_claims"));
    }

    let now = unix_now();
    if claims.iat > now.saturating_add(config.clock_skew_secs)
        || claims.iat > claims.exp
        || claims.nbf.is_some_and(|nbf| nbf > claims.exp)
        || claims.exp.saturating_sub(claims.iat) > config.max_token_lifetime_secs
    {
        return Err(AuthFailure::unauthorized("invalid_token_time"));
    }

    let audiences = claims.aud.into_set();
    if !audiences.contains(&config.resource) {
        return Err(AuthFailure::unauthorized("invalid_token_audience"));
    }

    let mut scopes = BTreeSet::new();
    if let Some(scope) = claims.scope {
        scopes.extend(scope.split_ascii_whitespace().map(str::to_string));
    }
    if let Some(scp) = claims.scp {
        scopes.extend(scp.into_iter().filter(|scope| !scope.is_empty()));
    }
    if scopes.iter().any(|scope| !is_policy_token(scope)) {
        return Err(AuthFailure::unauthorized("invalid_token_scope"));
    }
    if !config.required_scopes.is_subset(&scopes) {
        return Err(AuthFailure::forbidden("insufficient_scope"));
    }

    let policy = config
        .subjects
        .get(&claims.sub)
        .ok_or_else(|| AuthFailure::forbidden("subject_not_allowed"))?;
    if !policy.allowed_client_ids.is_empty()
        && !claims
            .client_id
            .as_ref()
            .is_some_and(|client_id| policy.allowed_client_ids.contains(client_id))
    {
        return Err(AuthFailure::forbidden("client_not_allowed"));
    }

    let fingerprint = hex::encode(Sha256::digest(token.as_bytes()));
    Ok(VerifiedOAuthSubject {
        issuer: claims.iss,
        subject: claims.sub,
        local_subject: policy.local_subject.clone(),
        audiences,
        scopes,
        expires_at_unix: claims.exp,
        client_id: claims.client_id,
        token_fingerprint: fingerprint,
    })
}

fn unix_now() -> u64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|duration| duration.as_secs())
        .unwrap_or(0)
}

fn accepts_streamable_http(headers: &HeaderMap) -> bool {
    let values: Vec<_> = headers
        .get_all(ACCEPT)
        .iter()
        .filter_map(|value| value.to_str().ok())
        .flat_map(|value| value.split(','))
        .map(|value| value.trim().to_ascii_lowercase())
        .collect();
    let accepts_json = values
        .iter()
        .any(|value| value.starts_with("application/json"));
    let accepts_sse = values
        .iter()
        .any(|value| value.starts_with("text/event-stream"));
    accepts_json && accepts_sse
}

fn has_json_content_type(headers: &HeaderMap) -> bool {
    headers
        .get(CONTENT_TYPE)
        .and_then(|value| value.to_str().ok())
        .is_some_and(|value| value.to_ascii_lowercase().starts_with("application/json"))
}

fn valid_protocol_header(headers: &HeaderMap) -> bool {
    let mut values = headers.get_all(&PROTOCOL_VERSION_HEADER).iter();
    let Some(value) = values.next() else {
        // The MCP transport spec assigns 2025-03-26 when no session or header
        // can identify a version. This lab supports that compatibility level.
        return true;
    };
    values.next().is_none()
        && value
            .to_str()
            .ok()
            .is_some_and(|version| COMPATIBLE_HTTP_PROTOCOL_VERSIONS.contains(&version.trim()))
}

fn auth_failure_response(config: &LabConfig, failure: AuthFailure) -> Response {
    let (status, challenge_error) = match failure.kind {
        AuthFailureKind::Unauthorized => (StatusCode::UNAUTHORIZED, Some("invalid_token")),
        AuthFailureKind::Forbidden if failure.code == "insufficient_scope" => {
            (StatusCode::FORBIDDEN, Some("insufficient_scope"))
        }
        AuthFailureKind::Forbidden => (StatusCode::FORBIDDEN, None),
    };
    let scopes = config
        .required_scopes
        .iter()
        .cloned()
        .collect::<Vec<_>>()
        .join(" ");
    let mut response = (status, Json(json!({ "error": failure.code }))).into_response();
    if let Some(error) = challenge_error {
        let challenge = format!(
            "Bearer resource_metadata=\"{}\", scope=\"{}\", error=\"{}\"",
            config.metadata_url, scopes, error
        );
        if let Ok(value) = HeaderValue::from_str(&challenge) {
            response.headers_mut().insert(WWW_AUTHENTICATE, value);
        }
    }
    response
}

fn request_auth_failure_response(config: &LabConfig, failure: RequestAuthFailure) -> Response {
    match failure {
        RequestAuthFailure::InvalidOrigin => json_error(StatusCode::FORBIDDEN, "invalid_origin"),
        RequestAuthFailure::OAuth(failure) => auth_failure_response(config, failure),
    }
}

fn json_error(status: StatusCode, code: &'static str) -> Response {
    (status, Json(json!({ "error": code }))).into_response()
}

fn json_rpc_http_error(
    status: StatusCode,
    id: Option<Value>,
    code: i32,
    message: &'static str,
) -> Response {
    (
        status,
        Json(McpResponse::error(id.unwrap_or(Value::Null), code, message)),
    )
        .into_response()
}

async fn dispatch_request(
    state: &LabState,
    request: McpRequest,
    subject: VerifiedOAuthSubject,
) -> McpResponse {
    let id = request.id.clone().unwrap_or(Value::Null);
    match request.method.as_str() {
        "initialize" => {
            let requested = request
                .params
                .as_ref()
                .and_then(|params| params.get("protocolVersion"))
                .and_then(Value::as_str);
            let protocol_version = requested
                .filter(|version| COMPATIBLE_HTTP_PROTOCOL_VERSIONS.contains(version))
                .unwrap_or(STREAMABLE_HTTP_PROTOCOL_VERSION);
            let result = InitializeResult {
                protocol_version: protocol_version.to_string(),
                capabilities: ServerCapabilities {
                    tools: Some(ToolsCapability {
                        list_changed: Some(false),
                    }),
                    resources: None,
                },
                server_info: ServerInfo {
                    name: "agent-bridge-http-auth-lab".into(),
                    version: env!("CARGO_PKG_VERSION").into(),
                },
            };
            serialize_result(id, result)
        }
        "ping" => McpResponse::success(id, json!({})),
        "tools/list" => {
            if request
                .params
                .as_ref()
                .and_then(|params| params.get("cursor"))
                .is_some()
            {
                return McpResponse::error(id, INVALID_PARAMS, "this lab has no tools cursor");
            }
            let tools = state
                .registry
                .descriptors()
                .into_iter()
                .map(|tool| ToolDefinition {
                    name: tool.schema.name,
                    title: tool.title,
                    description: tool.schema.description,
                    input_schema: tool.schema.input_schema,
                    annotations: tool.annotations,
                    output_schema: tool.output_schema,
                    security_schemes: tool.security_schemes,
                })
                .collect::<Vec<_>>();
            McpResponse::success(id, json!({ "tools": tools }))
        }
        "tools/call" => {
            let params = request.params.unwrap_or(Value::Null);
            let Some(name) = params.get("name").and_then(Value::as_str) else {
                return McpResponse::error(id, INVALID_PARAMS, "missing 'name'");
            };
            let Some(tool) = state.registry.get(name) else {
                return McpResponse::error(id, METHOD_NOT_FOUND, format!("unknown tool: {name}"));
            };
            let args = params
                .get("arguments")
                .cloned()
                .unwrap_or_else(|| json!({}));
            let mut extras = HashMap::new();
            if let Some(meta) = params.get("_meta") {
                extras.insert("_meta".to_string(), meta.clone());
            }
            let context = ToolContext {
                session_id: None,
                extras,
                transport_kind: McpTransportKind::StreamableHttp,
                verified_oauth_subject: Some(subject),
            };
            match tool.execute(args, &context).await {
                Ok(result) => serialize_result(id, result),
                Err(error) => serialize_result(
                    id,
                    ToolResult::error(format!("tool '{name}' failed: {error}")),
                ),
            }
        }
        other => McpResponse::error(id, METHOD_NOT_FOUND, format!("unknown method: {other}")),
    }
}

fn serialize_result<T: Serialize>(id: Value, result: T) -> McpResponse {
    match serde_json::to_value(result) {
        Ok(value) => McpResponse::success(id, value),
        Err(error) => McpResponse::error(id, INTERNAL_ERROR, format!("serialize: {error}")),
    }
}

struct OAuthSubjectDiagnostic {
    required_scopes: Vec<String>,
}

#[async_trait]
impl McpTool for OAuthSubjectDiagnostic {
    fn name(&self) -> &'static str {
        "oauth_subject_diagnostic"
    }

    fn schema(&self) -> ToolSchema {
        ToolSchema {
            name: self.name().into(),
            description: "Read the cryptographically verified OAuth subject bound by the synthetic loopback HTTP lab. Never executes or mutates anything.".into(),
            input_schema: json!({
                "type": "object",
                "properties": {},
                "additionalProperties": false
            }),
        }
    }

    fn annotations(&self) -> Option<ToolAnnotations> {
        Some(ToolAnnotations::read_only())
    }

    fn output_schema(&self) -> Option<Value> {
        Some(json!({
            "type": "object",
            "required": [
                "authenticated", "synthetic_lab", "execution_allowed", "transport",
                "issuer", "external_subject", "local_subject", "audiences", "scopes",
                "expires_at_unix", "token_fingerprint_prefix"
            ],
            "properties": {
                "authenticated": { "type": "boolean" },
                "synthetic_lab": { "type": "boolean" },
                "execution_allowed": { "type": "boolean" },
                "transport": { "type": "string" },
                "issuer": { "type": "string" },
                "external_subject": { "type": "string" },
                "local_subject": { "type": "string" },
                "audiences": { "type": "array", "items": { "type": "string" } },
                "scopes": { "type": "array", "items": { "type": "string" } },
                "expires_at_unix": { "type": "integer" },
                "client_id": { "type": ["string", "null"] },
                "token_fingerprint_prefix": { "type": "string" }
            },
            "additionalProperties": false
        }))
    }

    fn security_schemes(&self) -> Option<Vec<ToolSecurityScheme>> {
        Some(vec![ToolSecurityScheme::Oauth2 {
            scopes: self.required_scopes.clone(),
        }])
    }

    async fn execute(&self, args: Value, context: &ToolContext) -> Result<ToolResult> {
        if !args.as_object().is_some_and(serde_json::Map::is_empty) {
            return invalid("OAuth subject diagnostic takes no arguments");
        }
        if context.transport_kind() != McpTransportKind::StreamableHttp {
            return invalid("OAuth subject diagnostic requires Streamable HTTP");
        }
        let subject = context
            .verified_oauth_subject()
            .ok_or_else(|| Error::InvalidArgument("verified OAuth subject is absent".into()))?;
        let fingerprint_prefix = subject
            .token_fingerprint()
            .chars()
            .take(16)
            .collect::<String>();
        Ok(ToolResult::structured_json(&json!({
            "authenticated": true,
            "synthetic_lab": true,
            "execution_allowed": false,
            "transport": context.transport_kind().as_str(),
            "issuer": subject.issuer(),
            "external_subject": subject.subject(),
            "local_subject": subject.local_subject(),
            "audiences": subject.audiences(),
            "scopes": subject.scopes(),
            "expires_at_unix": subject.expires_at_unix(),
            "client_id": subject.client_id(),
            "token_fingerprint_prefix": fingerprint_prefix,
        })))
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use axum::body::{to_bytes, Body};
    use axum::http::Request;
    use base64::{engine::general_purpose::URL_SAFE_NO_PAD, Engine as _};
    use jsonwebtoken::{encode, EncodingKey, Header};
    use rsa::pkcs8::{EncodePrivateKey, LineEnding};
    use rsa::traits::PublicKeyParts;
    use rsa::RsaPrivateKey;
    use std::sync::OnceLock;
    use tower::ServiceExt;

    const TEST_KID: &str = "lab-key-1";

    struct TestKeyMaterial {
        private_pem: String,
        modulus: String,
        exponent: String,
    }

    fn test_key() -> &'static TestKeyMaterial {
        static KEY: OnceLock<TestKeyMaterial> = OnceLock::new();
        KEY.get_or_init(|| {
            let private = RsaPrivateKey::new(&mut rand::thread_rng(), 2048).unwrap();
            TestKeyMaterial {
                private_pem: private.to_pkcs8_pem(LineEnding::LF).unwrap().to_string(),
                modulus: URL_SAFE_NO_PAD.encode(private.n().to_bytes_be()),
                exponent: URL_SAFE_NO_PAD.encode(private.e().to_bytes_be()),
            }
        })
    }

    #[derive(Clone, Serialize)]
    struct TestClaims {
        iss: String,
        sub: String,
        aud: String,
        exp: u64,
        nbf: u64,
        iat: u64,
        scope: String,
        client_id: String,
    }

    fn config_json() -> String {
        json!({
            "mode": "synthetic_lab",
            "listen": "127.0.0.1:18789",
            "resource": "http://127.0.0.1:18789/mcp",
            "issuer": "https://issuer.example.invalid",
            "authorization_servers": ["https://issuer.example.invalid"],
            "required_scopes": ["agent-bridge:subject.read"],
            "allowed_origins": ["https://chatgpt.com"],
            "clock_skew_secs": 0,
            "max_token_lifetime_secs": 900,
            "jwks": { "keys": [{
                "kty": "RSA",
                "kid": TEST_KID,
                "alg": "RS256",
                "use": "sig",
                "n": test_key().modulus,
                "e": test_key().exponent
            }]},
            "subjects": [{
                "subject": "chatgpt-user-1",
                "local_subject": "owner",
                "allowed_client_ids": ["chatgpt-test-client"]
            }]
        })
        .to_string()
    }

    fn valid_claims() -> TestClaims {
        let now = unix_now();
        TestClaims {
            iss: "https://issuer.example.invalid".into(),
            sub: "chatgpt-user-1".into(),
            aud: "http://127.0.0.1:18789/mcp".into(),
            exp: now + 300,
            nbf: now.saturating_sub(1),
            iat: now.saturating_sub(1),
            scope: "agent-bridge:subject.read".into(),
            client_id: "chatgpt-test-client".into(),
        }
    }

    fn token(claims: &TestClaims) -> String {
        let mut header = Header::new(Algorithm::RS256);
        header.kid = Some(TEST_KID.into());
        encode(
            &header,
            claims,
            &EncodingKey::from_rsa_pem(test_key().private_pem.as_bytes()).unwrap(),
        )
        .unwrap()
    }

    async fn post(app: Router, token: Option<&str>, body: Value) -> Response {
        let mut request = Request::builder()
            .method("POST")
            .uri(MCP_PATH)
            .header(ACCEPT, "application/json, text/event-stream")
            .header(CONTENT_TYPE, "application/json")
            .header(&PROTOCOL_VERSION_HEADER, STREAMABLE_HTTP_PROTOCOL_VERSION)
            .header(ORIGIN, "https://chatgpt.com");
        if let Some(token) = token {
            request = request.header(AUTHORIZATION, format!("Bearer {token}"));
        }
        app.oneshot(request.body(Body::from(body.to_string())).unwrap())
            .await
            .unwrap()
    }

    async fn response_json(response: Response) -> Value {
        serde_json::from_slice(&to_bytes(response.into_body(), 1024 * 1024).await.unwrap()).unwrap()
    }

    #[tokio::test]
    async fn metadata_and_challenge_are_rfc9728_shaped() {
        let app = router(state_from_json(&config_json()).unwrap());
        let metadata = app
            .clone()
            .oneshot(
                Request::builder()
                    .uri(RESOURCE_METADATA_PATH)
                    .body(Body::empty())
                    .unwrap(),
            )
            .await
            .unwrap();
        assert_eq!(metadata.status(), StatusCode::OK);
        let metadata = response_json(metadata).await;
        assert_eq!(metadata["resource"], "http://127.0.0.1:18789/mcp");
        assert_eq!(
            metadata["authorization_servers"][0],
            "https://issuer.example.invalid"
        );

        let response = post(
            app,
            None,
            json!({ "jsonrpc": "2.0", "id": 1, "method": "ping" }),
        )
        .await;
        assert_eq!(response.status(), StatusCode::UNAUTHORIZED);
        let challenge = response.headers()[WWW_AUTHENTICATE].to_str().unwrap();
        assert!(challenge.contains(
            "resource_metadata=\"http://127.0.0.1:18789/.well-known/oauth-protected-resource\""
        ));
        assert!(challenge.contains("scope=\"agent-bridge:subject.read\""));
    }

    #[tokio::test]
    async fn invalid_origin_is_forbidden_before_token_use() {
        let app = router(state_from_json(&config_json()).unwrap());
        let response = app
            .oneshot(
                Request::builder()
                    .method("POST")
                    .uri(MCP_PATH)
                    .header(ORIGIN, "https://evil.example")
                    .header(AUTHORIZATION, format!("Bearer {}", token(&valid_claims())))
                    .body(Body::empty())
                    .unwrap(),
            )
            .await
            .unwrap();
        assert_eq!(response.status(), StatusCode::FORBIDDEN);
        assert_eq!(response_json(response).await["error"], "invalid_origin");
    }

    #[tokio::test]
    async fn authentication_precedes_bounded_body_buffering() {
        let app = router(state_from_json(&config_json()).unwrap());
        let oversized = json!({ "padding": "x".repeat(MAX_MCP_BODY_BYTES + 1) });
        let unauthenticated = post(app.clone(), None, oversized.clone()).await;
        assert_eq!(unauthenticated.status(), StatusCode::UNAUTHORIZED);

        let authenticated = post(app, Some(&token(&valid_claims())), oversized).await;
        assert_eq!(authenticated.status(), StatusCode::PAYLOAD_TOO_LARGE);
    }

    #[tokio::test]
    async fn invalid_tokens_and_policy_misses_fail_closed() {
        let state = state_from_json(&config_json()).unwrap();
        let app = router(state);
        let now = unix_now();
        let mut cases = Vec::new();

        let mut wrong_issuer = valid_claims();
        wrong_issuer.iss = "https://other.example.invalid".into();
        cases.push((
            "wrong issuer",
            token(&wrong_issuer),
            StatusCode::UNAUTHORIZED,
        ));

        let mut wrong_audience = valid_claims();
        wrong_audience.aud = "http://127.0.0.1:18789/other".into();
        cases.push((
            "wrong audience",
            token(&wrong_audience),
            StatusCode::UNAUTHORIZED,
        ));

        let mut expired = valid_claims();
        expired.exp = now.saturating_sub(10);
        expired.iat = now.saturating_sub(20);
        cases.push(("expired", token(&expired), StatusCode::UNAUTHORIZED));

        let mut future = valid_claims();
        future.nbf = now + 60;
        future.iat = now + 60;
        cases.push(("not yet valid", token(&future), StatusCode::UNAUTHORIZED));

        let mut excessive_lifetime = valid_claims();
        excessive_lifetime.iat = now;
        excessive_lifetime.exp = now + 901;
        cases.push((
            "excessive lifetime",
            token(&excessive_lifetime),
            StatusCode::UNAUTHORIZED,
        ));

        let mut missing_scope = valid_claims();
        missing_scope.scope = "other:read".into();
        cases.push((
            "missing scope",
            token(&missing_scope),
            StatusCode::FORBIDDEN,
        ));

        let mut unknown_subject = valid_claims();
        unknown_subject.sub = "unknown-user".into();
        cases.push((
            "unknown subject",
            token(&unknown_subject),
            StatusCode::FORBIDDEN,
        ));

        let mut wrong_client = valid_claims();
        wrong_client.client_id = "other-client".into();
        cases.push(("wrong client", token(&wrong_client), StatusCode::FORBIDDEN));

        let mut bad_signature = token(&valid_claims());
        let signature_start = bad_signature.rfind('.').unwrap() + 1;
        let replacement = if &bad_signature[signature_start..=signature_start] == "A" {
            "B"
        } else {
            "A"
        };
        bad_signature.replace_range(signature_start..=signature_start, replacement);
        cases.push(("bad signature", bad_signature, StatusCode::UNAUTHORIZED));

        for (label, token, expected) in cases {
            let response = post(
                app.clone(),
                Some(&token),
                json!({ "jsonrpc": "2.0", "id": label, "method": "ping" }),
            )
            .await;
            assert_eq!(response.status(), expected, "{label}");
        }
    }

    #[tokio::test]
    async fn valid_token_binds_subject_and_spoofed_meta_cannot_replace_it() {
        let app = router(state_from_json(&config_json()).unwrap());
        let response = post(
            app,
            Some(&token(&valid_claims())),
            json!({
                "jsonrpc": "2.0",
                "id": 7,
                "method": "tools/call",
                "params": {
                    "name": "oauth_subject_diagnostic",
                    "arguments": {},
                    "_meta": {
                        "iss": "https://attacker.example",
                        "sub": "attacker",
                        "local_subject": "admin",
                        "authorization": "Bearer forged"
                    }
                }
            }),
        )
        .await;
        assert_eq!(response.status(), StatusCode::OK);
        let body = response_json(response).await;
        let diagnostic = &body["result"]["structuredContent"];
        assert_eq!(diagnostic["authenticated"], true);
        assert_eq!(diagnostic["synthetic_lab"], true);
        assert_eq!(diagnostic["execution_allowed"], false);
        assert_eq!(diagnostic["transport"], "streamable_http");
        assert_eq!(diagnostic["issuer"], "https://issuer.example.invalid");
        assert_eq!(diagnostic["external_subject"], "chatgpt-user-1");
        assert_eq!(diagnostic["local_subject"], "owner");
        assert_ne!(diagnostic["external_subject"], "attacker");
    }

    #[tokio::test]
    async fn tools_list_advertises_read_only_oauth_scope() {
        let app = router(state_from_json(&config_json()).unwrap());
        let response = post(
            app,
            Some(&token(&valid_claims())),
            json!({ "jsonrpc": "2.0", "id": 8, "method": "tools/list" }),
        )
        .await;
        let body = response_json(response).await;
        assert_eq!(body["result"]["tools"].as_array().unwrap().len(), 1);
        assert_eq!(
            body["result"]["tools"][0]["annotations"]["readOnlyHint"],
            true
        );
        assert_eq!(
            body["result"]["tools"][0]["securitySchemes"][0]["type"],
            "oauth2"
        );
        assert_eq!(
            body["result"]["tools"][0]["securitySchemes"][0]["scopes"][0],
            "agent-bridge:subject.read"
        );
    }

    #[test]
    fn config_rejects_non_loopback_and_non_lab_mode() {
        let mut config: Value = serde_json::from_str(&config_json()).unwrap();
        config["listen"] = json!("0.0.0.0:18789");
        assert!(state_from_json(&config.to_string()).is_err());

        let mut config: Value = serde_json::from_str(&config_json()).unwrap();
        config["mode"] = json!("production");
        assert!(state_from_json(&config.to_string()).is_err());

        let mut config: Value = serde_json::from_str(&config_json()).unwrap();
        config["unexpected_policy_switch"] = json!(true);
        assert!(state_from_json(&config.to_string()).is_err());
    }
}
