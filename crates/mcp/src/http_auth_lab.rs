//! Default-off Streamable HTTP/OAuth resource-server verification surfaces.
//!
//! The synthetic lab uses a static public JWKS. The provider candidate fetches
//! discovery metadata and rotating public keys from an established OAuth/OIDC
//! provider. Both surfaces bind only to loopback, expose one read-only subject
//! diagnostic, and deliberately initialize none of the Agent-Bridge backends.

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
use reqwest::redirect::Policy as RedirectPolicy;
use serde::{Deserialize, Serialize};
use serde_json::{json, Value};
use sha2::{Digest, Sha256};
use std::collections::{BTreeSet, HashMap, HashSet};
use std::net::{IpAddr, SocketAddr};
use std::path::PathBuf;
use std::sync::atomic::{AtomicU64, Ordering as AtomicOrdering};
use std::sync::Arc;
use std::time::{SystemTime, UNIX_EPOCH};
use tokio::sync::{Mutex, RwLock};
use url::Url;

pub const STREAMABLE_HTTP_PROTOCOL_VERSION: &str = "2025-11-25";
const COMPATIBLE_HTTP_PROTOCOL_VERSIONS: &[&str] = &["2025-11-25", "2025-06-18", "2025-03-26"];
const PROTOCOL_VERSION_HEADER: HeaderName = HeaderName::from_static("mcp-protocol-version");
const LAB_MODE: &str = "synthetic_lab";
const PROVIDER_MODE: &str = "provider_candidate";
const MCP_PATH: &str = "/mcp";
const RESOURCE_METADATA_PATH: &str = "/.well-known/oauth-protected-resource";
const RESOURCE_METADATA_MCP_PATH: &str = "/.well-known/oauth-protected-resource/mcp";
const MAX_MCP_BODY_BYTES: usize = 256 * 1024;
const MAX_DISCOVERY_BODY_BYTES: usize = 64 * 1024;
const MAX_JWKS_BODY_BYTES: usize = 128 * 1024;
const MAX_REMOTE_JWKS_KEYS: usize = 64;
const MIN_REMOTE_REFRESH_INTERVAL_SECS: u64 = 5;

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
struct RawProviderConfig {
    mode: String,
    listen: String,
    resource: String,
    issuer: String,
    authorization_servers: Vec<String>,
    required_scopes: Vec<String>,
    allowed_origins: Vec<String>,
    expected_audiences: Vec<String>,
    provider: RawProviderSettings,
    subjects: Vec<RawSubjectPolicy>,
    #[serde(default = "default_clock_skew_secs")]
    clock_skew_secs: u64,
    #[serde(default = "default_max_token_lifetime_secs")]
    max_token_lifetime_secs: u64,
}

#[derive(Debug, Deserialize)]
#[serde(deny_unknown_fields)]
struct RawProviderSettings {
    discovery_url: String,
    client_registration: ClientRegistrationMode,
    #[serde(default = "default_jwks_cache_ttl_secs")]
    jwks_cache_ttl_secs: u64,
    #[serde(default = "default_provider_http_timeout_secs")]
    http_timeout_secs: u64,
}

#[derive(Debug, Clone, Copy, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
enum ClientRegistrationMode {
    Cimd,
    Dcr,
    Predefined,
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
struct RemoteJwkSet {
    keys: Vec<RemoteRsaJwk>,
}

#[derive(Debug, Deserialize)]
struct RemoteRsaJwk {
    kty: String,
    kid: Option<String>,
    alg: Option<String>,
    #[serde(rename = "use")]
    key_use: Option<String>,
    n: Option<String>,
    e: Option<String>,
}

#[derive(Debug, Deserialize)]
struct ProviderMetadata {
    issuer: String,
    jwks_uri: String,
    authorization_endpoint: String,
    token_endpoint: String,
    #[serde(default)]
    code_challenge_methods_supported: Vec<String>,
    client_id_metadata_document_supported: Option<bool>,
    registration_endpoint: Option<String>,
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

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
enum AuthRuntimeKind {
    SyntheticLab,
    ProviderCandidate,
}

impl AuthRuntimeKind {
    const fn as_str(self) -> &'static str {
        match self {
            Self::SyntheticLab => LAB_MODE,
            Self::ProviderCandidate => PROVIDER_MODE,
        }
    }

    const fn is_synthetic(self) -> bool {
        matches!(self, Self::SyntheticLab)
    }
}

enum KeySource {
    Static(HashMap<String, DecodingKey>),
    Remote(Arc<RemoteJwksProvider>),
}

struct RemoteJwksProvider {
    issuer: String,
    discovery_url: Url,
    registration_mode: ClientRegistrationMode,
    cache_ttl_secs: u64,
    client: reqwest::Client,
    cache: RwLock<JwksCache>,
    refresh_lock: Mutex<()>,
    last_refresh_attempt_at_unix: AtomicU64,
}

#[derive(Default)]
struct JwksCache {
    fetched_at_unix: u64,
    keys: HashMap<String, DecodingKey>,
}

struct LabConfig {
    runtime_kind: AuthRuntimeKind,
    listen: SocketAddr,
    resource: String,
    expected_audiences: BTreeSet<String>,
    issuer: String,
    authorization_servers: Vec<String>,
    required_scopes: BTreeSet<String>,
    allowed_origins: BTreeSet<String>,
    metadata_url: String,
    key_source: KeySource,
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
    azp: Option<String>,
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
    Unavailable,
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

    const fn unavailable(code: &'static str) -> Self {
        Self {
            kind: AuthFailureKind::Unavailable,
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

fn default_jwks_cache_ttl_secs() -> u64 {
    300
}

fn default_provider_http_timeout_secs() -> u64 {
    5
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
    serve_state(state).await
}

/// Start the default-off provider-backed candidate from an explicit JSON file.
pub async fn serve_provider_from_path(path: PathBuf) -> Result<()> {
    let raw = tokio::fs::read_to_string(&path).await.map_err(|error| {
        Error::InvalidArgument(format!(
            "read provider candidate config {}: {error}",
            path.display()
        ))
    })?;
    let state = provider_state_from_json(&raw).await?;
    serve_state(state).await
}

async fn serve_state(state: LabState) -> Result<()> {
    let listen = state.config.listen;
    let resource = state.config.resource.clone();
    let runtime_kind = state.config.runtime_kind.as_str();
    let app = router(state);
    let listener = tokio::net::TcpListener::bind(listen).await?;

    tracing::warn!(
        %listen,
        %resource,
        %runtime_kind,
        execution_allowed = false,
        "default-off MCP HTTP/OAuth verification surface listening"
    );

    axum::serve(listener, app)
        .await
        .map_err(|error| Error::Backend(format!("HTTP/OAuth verification surface failed: {error}")))
}

fn state_from_json(raw: &str) -> Result<LabState> {
    let raw: RawLabConfig = serde_json::from_str(raw)?;
    let config = Arc::new(validate_config(raw)?);
    Ok(state_from_config(config))
}

async fn provider_state_from_json(raw: &str) -> Result<LabState> {
    let raw: RawProviderConfig = serde_json::from_str(raw)?;
    let config = Arc::new(validate_provider_config(raw).await?);
    Ok(state_from_config(config))
}

fn state_from_config(config: Arc<LabConfig>) -> LabState {
    let mut registry = ToolRegistry::new();
    registry.register(Arc::new(OAuthSubjectDiagnostic {
        required_scopes: config.required_scopes.iter().cloned().collect(),
        runtime_kind: config.runtime_kind,
    }));
    LabState { config, registry }
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
        validate_external_subject(&subject.subject)?;
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
        runtime_kind: AuthRuntimeKind::SyntheticLab,
        listen,
        resource: resource_url.to_string(),
        expected_audiences: [resource_url.to_string()].into_iter().collect(),
        issuer,
        authorization_servers,
        required_scopes,
        allowed_origins,
        metadata_url: metadata_url.to_string(),
        key_source: KeySource::Static(keys),
        subjects,
        clock_skew_secs: raw.clock_skew_secs,
        max_token_lifetime_secs: raw.max_token_lifetime_secs,
    })
}

async fn validate_provider_config(raw: RawProviderConfig) -> Result<LabConfig> {
    if raw.mode != PROVIDER_MODE {
        return invalid("config mode must be exactly 'provider_candidate'");
    }

    let listen = raw
        .listen
        .parse::<SocketAddr>()
        .map_err(|error| Error::InvalidArgument(format!("invalid listen socket: {error}")))?;
    if !listen.ip().is_loopback() {
        return invalid("provider candidate listener must use a loopback IP address");
    }

    let resource_url = parse_url(&raw.resource, "resource")?;
    if resource_url.username() != ""
        || resource_url.password().is_some()
        || resource_url.query().is_some()
        || resource_url.fragment().is_some()
        || resource_url.path() == "/"
    {
        return invalid(
            "provider resource must be an uncredentialed URL with a non-root path and no query or fragment",
        );
    }
    validate_https_or_loopback(&resource_url, "provider resource")?;

    let issuer_url = parse_authority_url(&raw.issuer, "issuer")?;
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
    if authorization_servers.first() != Some(&issuer) {
        return invalid("authorization_servers[0] must exactly match the configured issuer");
    }

    let required_scopes = validated_tokens(raw.required_scopes, "required scope")?;
    if required_scopes.is_empty() {
        return invalid("required_scopes must not be empty");
    }

    let allowed_origins = validate_allowed_origins(raw.allowed_origins)?;
    let expected_audiences = validate_expected_audiences(raw.expected_audiences)?;
    if !expected_audiences.contains(resource_url.as_str()) {
        return invalid("expected_audiences must contain the exact provider resource URL");
    }

    if raw.clock_skew_secs > 300 {
        return invalid("clock_skew_secs must be at most 300");
    }
    if raw.max_token_lifetime_secs == 0 || raw.max_token_lifetime_secs > 3600 {
        return invalid("max_token_lifetime_secs must be between 1 and 3600");
    }
    if !(30..=3600).contains(&raw.provider.jwks_cache_ttl_secs) {
        return invalid("provider jwks_cache_ttl_secs must be between 30 and 3600");
    }
    if !(1..=30).contains(&raw.provider.http_timeout_secs) {
        return invalid("provider http_timeout_secs must be between 1 and 30");
    }

    let subjects = validate_subject_policies(raw.subjects)?;
    let discovery_url = parse_url(&raw.provider.discovery_url, "provider discovery")?;
    if discovery_url.username() != ""
        || discovery_url.password().is_some()
        || discovery_url.query().is_some()
        || discovery_url.fragment().is_some()
        || discovery_url.path() == "/"
    {
        return invalid(
            "provider discovery URL must have a path and no credentials, query, or fragment",
        );
    }
    validate_https_or_loopback(&discovery_url, "provider discovery")?;
    if discovery_url.origin() != issuer_url.origin() {
        return invalid("provider discovery URL must use the configured issuer origin");
    }

    let remote = RemoteJwksProvider::initialize(
        issuer.clone(),
        discovery_url,
        raw.provider.client_registration,
        raw.provider.jwks_cache_ttl_secs,
        raw.provider.http_timeout_secs,
    )
    .await?;

    let metadata_url = metadata_url_for_resource(&resource_url)?;
    Ok(LabConfig {
        runtime_kind: AuthRuntimeKind::ProviderCandidate,
        listen,
        resource: resource_url.to_string(),
        expected_audiences,
        issuer,
        authorization_servers,
        required_scopes,
        allowed_origins,
        metadata_url,
        key_source: KeySource::Remote(Arc::new(remote)),
        subjects,
        clock_skew_secs: raw.clock_skew_secs,
        max_token_lifetime_secs: raw.max_token_lifetime_secs,
    })
}

fn validate_allowed_origins(values: Vec<String>) -> Result<BTreeSet<String>> {
    let mut allowed_origins = BTreeSet::new();
    for origin in values {
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
        validate_https_or_loopback(&parsed, "allowed origin")?;
        allowed_origins.insert(parsed.origin().ascii_serialization());
    }
    if allowed_origins.is_empty() {
        return invalid("allowed_origins must not be empty");
    }
    Ok(allowed_origins)
}

fn validate_expected_audiences(values: Vec<String>) -> Result<BTreeSet<String>> {
    let mut audiences = BTreeSet::new();
    for audience in values {
        let parsed = parse_url(&audience, "expected audience")?;
        if parsed.username() != ""
            || parsed.password().is_some()
            || parsed.query().is_some()
            || parsed.fragment().is_some()
            || parsed.path() == "/"
        {
            return invalid(
                "expected audiences must be uncredentialed URLs with a non-root path and no query or fragment",
            );
        }
        validate_https_or_loopback(&parsed, "expected audience")?;
        audiences.insert(parsed.to_string());
    }
    if audiences.is_empty() {
        return invalid("expected_audiences must not be empty");
    }
    Ok(audiences)
}

fn validate_subject_policies(
    values: Vec<RawSubjectPolicy>,
) -> Result<HashMap<String, SubjectPolicy>> {
    let mut subjects = HashMap::new();
    for subject in values {
        validate_external_subject(&subject.subject)?;
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
    Ok(subjects)
}

fn validate_https_or_loopback(url: &Url, field: &str) -> Result<()> {
    let loopback_http = url.scheme() == "http"
        && url
            .host_str()
            .and_then(|host| host.parse::<IpAddr>().ok())
            .is_some_and(|ip| ip.is_loopback());
    if url.scheme() != "https" && !loopback_http {
        return invalid(format!("{field} URL must use https or loopback http"));
    }
    Ok(())
}

fn metadata_url_for_resource(resource: &Url) -> Result<String> {
    let mut metadata = resource.clone();
    let resource_path = resource.path().trim_start_matches('/');
    metadata.set_path(&format!("{RESOURCE_METADATA_PATH}/{resource_path}"));
    metadata.set_query(None);
    metadata.set_fragment(None);
    Ok(metadata.to_string())
}

impl RemoteJwksProvider {
    async fn initialize(
        issuer: String,
        discovery_url: Url,
        registration_mode: ClientRegistrationMode,
        cache_ttl_secs: u64,
        http_timeout_secs: u64,
    ) -> Result<Self> {
        let client = reqwest::Client::builder()
            .redirect(RedirectPolicy::none())
            .timeout(std::time::Duration::from_secs(http_timeout_secs))
            .build()
            .map_err(|error| Error::Backend(format!("build provider HTTP client: {error}")))?;
        let provider = Self {
            issuer,
            discovery_url,
            registration_mode,
            cache_ttl_secs,
            client,
            cache: RwLock::new(JwksCache::default()),
            refresh_lock: Mutex::new(()),
            last_refresh_attempt_at_unix: AtomicU64::new(0),
        };
        provider.refresh_cache().await?;
        Ok(provider)
    }

    async fn key_for(&self, kid: &str) -> std::result::Result<DecodingKey, RemoteKeyFailure> {
        let observed_fetch = {
            let cache = self.cache.read().await;
            if cache.fetched_at_unix > 0
                && unix_now().saturating_sub(cache.fetched_at_unix) <= self.cache_ttl_secs
            {
                if let Some(key) = cache.keys.get(kid) {
                    return Ok(key.clone());
                }
            }
            cache.fetched_at_unix
        };

        let _guard = self.refresh_lock.lock().await;
        {
            let cache = self.cache.read().await;
            if cache.fetched_at_unix > 0
                && unix_now().saturating_sub(cache.fetched_at_unix) <= self.cache_ttl_secs
            {
                if let Some(key) = cache.keys.get(kid) {
                    return Ok(key.clone());
                }
                if cache.fetched_at_unix > observed_fetch {
                    return Err(RemoteKeyFailure::UnknownKid);
                }
            }
        }

        let now = unix_now();
        let cache_is_fresh = {
            let cache = self.cache.read().await;
            cache.fetched_at_unix > 0
                && now.saturating_sub(cache.fetched_at_unix) <= self.cache_ttl_secs
        };
        let last_attempt = self
            .last_refresh_attempt_at_unix
            .load(AtomicOrdering::Relaxed);
        if last_attempt > 0 && now.saturating_sub(last_attempt) < MIN_REMOTE_REFRESH_INTERVAL_SECS {
            return Err(if cache_is_fresh {
                RemoteKeyFailure::UnknownKid
            } else {
                RemoteKeyFailure::Unavailable
            });
        }
        self.last_refresh_attempt_at_unix
            .store(now, AtomicOrdering::Relaxed);

        if let Err(error) = self.refresh_cache().await {
            tracing::warn!(
                discovery_url = %self.discovery_url,
                error = %error,
                "provider JWKS refresh failed closed"
            );
            return Err(RemoteKeyFailure::Unavailable);
        }
        self.cache
            .read()
            .await
            .keys
            .get(kid)
            .cloned()
            .ok_or(RemoteKeyFailure::UnknownKid)
    }

    async fn refresh_cache(&self) -> Result<()> {
        let metadata: ProviderMetadata = fetch_bounded_json(
            &self.client,
            &self.discovery_url,
            MAX_DISCOVERY_BODY_BYTES,
            "provider discovery",
        )
        .await?;
        if metadata.issuer != self.issuer {
            return invalid("provider discovery issuer does not exactly match configured issuer");
        }
        if !metadata
            .code_challenge_methods_supported
            .iter()
            .any(|method| method == "S256")
        {
            return invalid("provider discovery does not advertise PKCE S256");
        }
        validate_remote_endpoint(&metadata.authorization_endpoint, "authorization endpoint")?;
        validate_remote_endpoint(&metadata.token_endpoint, "token endpoint")?;
        match self.registration_mode {
            ClientRegistrationMode::Cimd
                if metadata.client_id_metadata_document_supported != Some(true) =>
            {
                return invalid("provider discovery does not advertise CIMD support")
            }
            ClientRegistrationMode::Dcr => {
                let endpoint = metadata.registration_endpoint.as_deref().ok_or_else(|| {
                    Error::InvalidArgument(
                        "provider discovery does not advertise a DCR registration endpoint".into(),
                    )
                })?;
                validate_remote_endpoint(endpoint, "registration endpoint")?;
            }
            ClientRegistrationMode::Cimd | ClientRegistrationMode::Predefined => {}
        }

        let jwks_url = parse_url(&metadata.jwks_uri, "provider JWKS")?;
        if jwks_url.username() != ""
            || jwks_url.password().is_some()
            || jwks_url.query().is_some()
            || jwks_url.fragment().is_some()
        {
            return invalid("provider JWKS URL must not contain credentials, query, or fragment");
        }
        validate_https_or_loopback(&jwks_url, "provider JWKS")?;
        let jwks: RemoteJwkSet = fetch_bounded_json(
            &self.client,
            &jwks_url,
            MAX_JWKS_BODY_BYTES,
            "provider JWKS",
        )
        .await?;
        let keys = decode_remote_jwks(jwks)?;
        let mut cache = self.cache.write().await;
        *cache = JwksCache {
            fetched_at_unix: unix_now(),
            keys,
        };
        Ok(())
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
enum RemoteKeyFailure {
    UnknownKid,
    Unavailable,
}

async fn fetch_bounded_json<T: for<'de> Deserialize<'de>>(
    client: &reqwest::Client,
    url: &Url,
    max_bytes: usize,
    label: &str,
) -> Result<T> {
    let mut response = client
        .get(url.clone())
        .header("accept", "application/json")
        .send()
        .await
        .map_err(|error| Error::Backend(format!("fetch {label}: {error}")))?;
    if response.status() != reqwest::StatusCode::OK {
        return Err(Error::Backend(format!(
            "fetch {label}: unexpected HTTP status {}",
            response.status()
        )));
    }
    let content_type = response
        .headers()
        .get(CONTENT_TYPE)
        .and_then(|value| value.to_str().ok())
        .and_then(|value| value.split(';').next())
        .map(str::trim)
        .map(str::to_ascii_lowercase);
    if !content_type
        .as_deref()
        .is_some_and(|value| value == "application/json" || value.ends_with("+json"))
    {
        return Err(Error::Backend(format!(
            "fetch {label}: response is not JSON"
        )));
    }
    if response
        .content_length()
        .is_some_and(|length| length > max_bytes as u64)
    {
        return Err(Error::Backend(format!("fetch {label}: response too large")));
    }
    let mut body = Vec::new();
    while let Some(chunk) = response
        .chunk()
        .await
        .map_err(|error| Error::Backend(format!("read {label}: {error}")))?
    {
        if body.len().saturating_add(chunk.len()) > max_bytes {
            return Err(Error::Backend(format!("fetch {label}: response too large")));
        }
        body.extend_from_slice(&chunk);
    }
    serde_json::from_slice(&body)
        .map_err(|error| Error::InvalidArgument(format!("decode {label}: {error}")))
}

fn validate_remote_endpoint(raw: &str, field: &str) -> Result<()> {
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
    validate_https_or_loopback(&parsed, field)
}

fn decode_remote_jwks(jwks: RemoteJwkSet) -> Result<HashMap<String, DecodingKey>> {
    if jwks.keys.len() > MAX_REMOTE_JWKS_KEYS {
        return invalid("provider JWKS contains too many keys");
    }
    let mut keys = HashMap::new();
    for jwk in jwks.keys {
        if jwk.kty != "RSA"
            || jwk.alg.as_deref().is_some_and(|alg| alg != "RS256")
            || jwk
                .key_use
                .as_deref()
                .is_some_and(|key_use| key_use != "sig")
        {
            continue;
        }
        let Some(kid) = jwk.kid else {
            continue;
        };
        validate_policy_token(&kid, "provider JWKS kid")?;
        if keys.contains_key(&kid) {
            return invalid("provider JWKS contains duplicate usable kid values");
        }
        let n = jwk
            .n
            .ok_or_else(|| Error::InvalidArgument("provider RSA JWK is missing n".into()))?;
        let e = jwk
            .e
            .ok_or_else(|| Error::InvalidArgument("provider RSA JWK is missing e".into()))?;
        if !(300..=1024).contains(&n.len()) || !(1..=16).contains(&e.len()) {
            return invalid("provider RSA JWK components are outside accepted size bounds");
        }
        let key = DecodingKey::from_rsa_components(&n, &e).map_err(|error| {
            Error::InvalidArgument(format!(
                "invalid provider RSA components for kid {kid}: {error}"
            ))
        })?;
        keys.insert(kid, key);
    }
    if keys.is_empty() {
        return invalid("provider JWKS contains no usable RSA/RS256 signing keys");
    }
    Ok(keys)
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

fn validate_external_subject(value: &str) -> Result<()> {
    if !is_external_subject(value) {
        return invalid("external subject contains unsupported characters");
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

fn is_external_subject(value: &str) -> bool {
    !value.is_empty()
        && value.len() <= 256
        && value
            .bytes()
            .all(|byte| byte.is_ascii_alphanumeric() || b"-._:/@|".contains(&byte))
}

fn router(state: LabState) -> Router {
    Router::new()
        .route(RESOURCE_METADATA_PATH, get(resource_metadata))
        .route(RESOURCE_METADATA_MCP_PATH, get(resource_metadata))
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
    if let Err(failure) = authorize_request(&state, &headers).await {
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
    if let Err(failure) = authorize_request(&state, &headers).await {
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
    let subject = match authorize_request(&state, &headers).await {
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

async fn authorize_request(
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

    verify_token(&state.config, token)
        .await
        .map_err(RequestAuthFailure::OAuth)
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

async fn verify_token(
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
    let key = match &config.key_source {
        KeySource::Static(keys) => keys
            .get(kid)
            .cloned()
            .ok_or_else(|| AuthFailure::unauthorized("unknown_token_kid"))?,
        KeySource::Remote(provider) => match provider.key_for(kid).await {
            Ok(key) => key,
            Err(RemoteKeyFailure::UnknownKid) => {
                return Err(AuthFailure::unauthorized("unknown_token_kid"))
            }
            Err(RemoteKeyFailure::Unavailable) => {
                return Err(AuthFailure::unavailable("jwks_unavailable"))
            }
        },
    };

    let mut validation = Validation::new(Algorithm::RS256);
    validation.leeway = config.clock_skew_secs;
    validation.validate_nbf = true;
    validation.set_issuer(&[config.issuer.as_str()]);
    validation.set_audience(
        &config
            .expected_audiences
            .iter()
            .map(String::as_str)
            .collect::<Vec<_>>(),
    );
    validation.required_spec_claims = HashSet::from_iter(
        ["exp", "iss", "sub", "aud", "iat"]
            .into_iter()
            .map(str::to_string),
    );

    let claims = decode::<JwtClaims>(token, &key, &validation)
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
    if audiences.is_disjoint(&config.expected_audiences) {
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
    let client_id = claims.client_id.or(claims.azp);
    if !policy.allowed_client_ids.is_empty()
        && !client_id
            .as_ref()
            .is_some_and(|value| policy.allowed_client_ids.contains(value))
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
        client_id,
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
        AuthFailureKind::Unavailable => (StatusCode::SERVICE_UNAVAILABLE, None),
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
                    name: format!(
                        "agent-bridge-http-auth-{}",
                        state.config.runtime_kind.as_str()
                    ),
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
    runtime_kind: AuthRuntimeKind,
}

#[async_trait]
impl McpTool for OAuthSubjectDiagnostic {
    fn name(&self) -> &'static str {
        "oauth_subject_diagnostic"
    }

    fn schema(&self) -> ToolSchema {
        ToolSchema {
            name: self.name().into(),
            description: format!(
                "Read the cryptographically verified OAuth subject bound by the default-off {} HTTP surface. Never executes or mutates anything.",
                self.runtime_kind.as_str()
            ),
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
                "authenticated", "environment", "synthetic_lab", "provider_candidate",
                "execution_allowed", "transport",
                "issuer", "external_subject", "local_subject", "audiences", "scopes",
                "expires_at_unix", "token_fingerprint_prefix"
            ],
            "properties": {
                "authenticated": { "type": "boolean" },
                "environment": { "type": "string" },
                "synthetic_lab": { "type": "boolean" },
                "provider_candidate": { "type": "boolean" },
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
            "environment": self.runtime_kind.as_str(),
            "synthetic_lab": self.runtime_kind.is_synthetic(),
            "provider_candidate": self.runtime_kind == AuthRuntimeKind::ProviderCandidate,
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
    use std::sync::atomic::{AtomicBool, AtomicUsize, Ordering};
    use std::sync::OnceLock;
    use tower::ServiceExt;

    const TEST_KID: &str = "lab-key-1";
    const ROTATED_TEST_KID: &str = "provider-key-2";
    const PROVIDER_TEST_RESOURCE: &str =
        "https://api.openai.com/v1/mcp/tunnel_0123456789abcdef0123456789abcdef";

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

    fn rotated_test_key() -> &'static TestKeyMaterial {
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

    #[derive(Clone)]
    struct TestProviderState {
        issuer: String,
        jwks: Arc<RwLock<Value>>,
        fail_jwks: Arc<AtomicBool>,
        jwks_calls: Arc<AtomicUsize>,
    }

    async fn provider_discovery(State(state): State<TestProviderState>) -> Json<Value> {
        Json(json!({
            "issuer": state.issuer,
            "jwks_uri": format!("{}/jwks", state.issuer),
            "authorization_endpoint": format!("{}/authorize", state.issuer),
            "token_endpoint": format!("{}/oauth/token", state.issuer),
            "code_challenge_methods_supported": ["S256"],
            "client_id_metadata_document_supported": true,
            "registration_endpoint": format!("{}/register", state.issuer)
        }))
    }

    async fn provider_jwks(State(state): State<TestProviderState>) -> Response {
        state.jwks_calls.fetch_add(1, Ordering::SeqCst);
        if state.fail_jwks.load(Ordering::SeqCst) {
            return StatusCode::SERVICE_UNAVAILABLE.into_response();
        }
        Json(state.jwks.read().await.clone()).into_response()
    }

    async fn start_test_provider() -> (TestProviderState, tokio::task::JoinHandle<()>) {
        let listener = tokio::net::TcpListener::bind("127.0.0.1:0").await.unwrap();
        let issuer = format!("http://{}", listener.local_addr().unwrap());
        let state = TestProviderState {
            issuer,
            jwks: Arc::new(RwLock::new(jwks_value(TEST_KID, test_key()))),
            fail_jwks: Arc::new(AtomicBool::new(false)),
            jwks_calls: Arc::new(AtomicUsize::new(0)),
        };
        let app = Router::new()
            .route("/.well-known/openid-configuration", get(provider_discovery))
            .route("/jwks", get(provider_jwks))
            .with_state(state.clone());
        let handle = tokio::spawn(async move {
            axum::serve(listener, app).await.unwrap();
        });
        (state, handle)
    }

    fn jwks_value(kid: &str, key: &TestKeyMaterial) -> Value {
        json!({
            "keys": [{
                "kty": "RSA",
                "kid": kid,
                "alg": "RS256",
                "use": "sig",
                "n": key.modulus,
                "e": key.exponent,
                "x5c": ["ignored-public-certificate-chain"]
            }]
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
        client_id: Option<String>,
        #[serde(skip_serializing_if = "Option::is_none")]
        azp: Option<String>,
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

    fn provider_config_json(provider: &TestProviderState) -> String {
        json!({
            "mode": "provider_candidate",
            "listen": "127.0.0.1:18792",
            "resource": PROVIDER_TEST_RESOURCE,
            "issuer": provider.issuer,
            "authorization_servers": [provider.issuer],
            "required_scopes": ["agent-bridge:subject.read"],
            "allowed_origins": ["https://chatgpt.com"],
            "expected_audiences": [PROVIDER_TEST_RESOURCE],
            "provider": {
                "discovery_url": format!(
                    "{}/.well-known/openid-configuration",
                    provider.issuer
                ),
                "client_registration": "cimd",
                "jwks_cache_ttl_secs": 30,
                "http_timeout_secs": 2
            },
            "subjects": [{
                "subject": "chatgpt-user-1",
                "local_subject": "owner",
                "allowed_client_ids": ["chatgpt-test-client"]
            }],
            "clock_skew_secs": 0,
            "max_token_lifetime_secs": 900
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
            client_id: Some("chatgpt-test-client".into()),
            azp: None,
        }
    }

    fn provider_valid_claims(provider: &TestProviderState) -> TestClaims {
        let mut claims = valid_claims();
        claims.iss = provider.issuer.clone();
        claims.aud = PROVIDER_TEST_RESOURCE.into();
        claims
    }

    fn token(claims: &TestClaims) -> String {
        token_with_key(claims, TEST_KID, test_key())
    }

    fn token_with_key(claims: &TestClaims, kid: &str, key: &TestKeyMaterial) -> String {
        let mut header = Header::new(Algorithm::RS256);
        header.kid = Some(kid.into());
        encode(
            &header,
            claims,
            &EncodingKey::from_rsa_pem(key.private_pem.as_bytes()).unwrap(),
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
        wrong_client.client_id = Some("other-client".into());
        cases.push(("wrong client", token(&wrong_client), StatusCode::FORBIDDEN));

        let mut authorized_party = valid_claims();
        authorized_party.client_id = None;
        authorized_party.azp = Some("chatgpt-test-client".into());
        cases.push((
            "authorized party client",
            token(&authorized_party),
            StatusCode::OK,
        ));

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

    #[tokio::test]
    async fn provider_candidate_discovers_keys_and_binds_subject() {
        let (provider, provider_task) = start_test_provider().await;
        let state = provider_state_from_json(&provider_config_json(&provider))
            .await
            .unwrap();
        assert_eq!(provider.jwks_calls.load(Ordering::SeqCst), 1);
        assert_eq!(
            state.config.runtime_kind,
            AuthRuntimeKind::ProviderCandidate
        );

        let app = router(state);
        let metadata = app
            .clone()
            .oneshot(
                Request::builder()
                    .uri(RESOURCE_METADATA_MCP_PATH)
                    .body(Body::empty())
                    .unwrap(),
            )
            .await
            .unwrap();
        assert_eq!(metadata.status(), StatusCode::OK);
        assert_eq!(
            response_json(metadata).await["resource"],
            PROVIDER_TEST_RESOURCE
        );

        let unauthenticated = post(
            app.clone(),
            None,
            json!({ "jsonrpc": "2.0", "id": 1, "method": "ping" }),
        )
        .await;
        assert_eq!(unauthenticated.status(), StatusCode::UNAUTHORIZED);
        let challenge = unauthenticated.headers()[WWW_AUTHENTICATE]
            .to_str()
            .unwrap();
        assert!(challenge.contains(
            "resource_metadata=\"https://api.openai.com/.well-known/oauth-protected-resource/v1/mcp/tunnel_0123456789abcdef0123456789abcdef\""
        ));

        let response = post(
            app,
            Some(&token(&provider_valid_claims(&provider))),
            json!({
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {
                    "name": "oauth_subject_diagnostic",
                    "arguments": {},
                    "_meta": { "sub": "attacker", "local_subject": "admin" }
                }
            }),
        )
        .await;
        assert_eq!(response.status(), StatusCode::OK);
        let body = response_json(response).await;
        let diagnostic = &body["result"]["structuredContent"];
        assert_eq!(diagnostic["environment"], PROVIDER_MODE);
        assert_eq!(diagnostic["synthetic_lab"], false);
        assert_eq!(diagnostic["provider_candidate"], true);
        assert_eq!(diagnostic["execution_allowed"], false);
        assert_eq!(diagnostic["issuer"], provider.issuer);
        assert_eq!(diagnostic["external_subject"], "chatgpt-user-1");
        assert_eq!(diagnostic["local_subject"], "owner");

        provider_task.abort();
    }

    #[tokio::test]
    async fn provider_candidate_refreshes_rotated_keys_and_fails_closed_on_outage() {
        let (provider, provider_task) = start_test_provider().await;
        let state = provider_state_from_json(&provider_config_json(&provider))
            .await
            .unwrap();
        assert_eq!(provider.jwks_calls.load(Ordering::SeqCst), 1);

        *provider.jwks.write().await = jwks_value(ROTATED_TEST_KID, rotated_test_key());
        let rotated_token = token_with_key(
            &provider_valid_claims(&provider),
            ROTATED_TEST_KID,
            rotated_test_key(),
        );
        let app = router(state.clone());
        let (first, second) = tokio::join!(
            post(
                app.clone(),
                Some(&rotated_token),
                json!({ "jsonrpc": "2.0", "id": 3, "method": "ping" }),
            ),
            post(
                app,
                Some(&rotated_token),
                json!({ "jsonrpc": "2.0", "id": 4, "method": "ping" }),
            )
        );
        assert_eq!(first.status(), StatusCode::OK);
        assert_eq!(second.status(), StatusCode::OK);
        assert_eq!(provider.jwks_calls.load(Ordering::SeqCst), 2);

        let KeySource::Remote(remote) = &state.config.key_source else {
            panic!("provider candidate must use remote JWKS");
        };
        let unknown_token = token_with_key(
            &provider_valid_claims(&provider),
            "provider-key-unknown",
            rotated_test_key(),
        );
        let response = post(
            router(state.clone()),
            Some(&unknown_token),
            json!({ "jsonrpc": "2.0", "id": 5, "method": "ping" }),
        )
        .await;
        assert_eq!(response.status(), StatusCode::UNAUTHORIZED);
        assert_eq!(provider.jwks_calls.load(Ordering::SeqCst), 2);

        remote
            .last_refresh_attempt_at_unix
            .store(0, Ordering::SeqCst);
        provider.fail_jwks.store(true, Ordering::SeqCst);
        let response = post(
            router(state.clone()),
            Some(&unknown_token),
            json!({ "jsonrpc": "2.0", "id": 6, "method": "ping" }),
        )
        .await;
        assert_eq!(response.status(), StatusCode::SERVICE_UNAVAILABLE);
        assert_eq!(response_json(response).await["error"], "jwks_unavailable");
        assert_eq!(provider.jwks_calls.load(Ordering::SeqCst), 3);

        remote.cache.write().await.fetched_at_unix = unix_now().saturating_sub(31);
        let response = post(
            router(state),
            Some(&rotated_token),
            json!({ "jsonrpc": "2.0", "id": 7, "method": "ping" }),
        )
        .await;
        assert_eq!(response.status(), StatusCode::SERVICE_UNAVAILABLE);
        assert_eq!(response_json(response).await["error"], "jwks_unavailable");
        assert_eq!(provider.jwks_calls.load(Ordering::SeqCst), 3);

        provider_task.abort();
    }

    #[tokio::test]
    async fn provider_candidate_rejects_unsafe_or_inconsistent_config() {
        let (provider, provider_task) = start_test_provider().await;

        let mut config: Value = serde_json::from_str(&provider_config_json(&provider)).unwrap();
        config["listen"] = json!("0.0.0.0:18792");
        assert!(provider_state_from_json(&config.to_string()).await.is_err());
        assert_eq!(provider.jwks_calls.load(Ordering::SeqCst), 0);

        let mut config: Value = serde_json::from_str(&provider_config_json(&provider)).unwrap();
        config["expected_audiences"] = json!(["https://api.openai.com/v1/mcp/other"]);
        assert!(provider_state_from_json(&config.to_string()).await.is_err());
        assert_eq!(provider.jwks_calls.load(Ordering::SeqCst), 0);

        let mut config: Value = serde_json::from_str(&provider_config_json(&provider)).unwrap();
        config["unexpected_policy_switch"] = json!(true);
        assert!(provider_state_from_json(&config.to_string()).await.is_err());
        assert_eq!(provider.jwks_calls.load(Ordering::SeqCst), 0);

        let mut config: Value = serde_json::from_str(&provider_config_json(&provider)).unwrap();
        config["provider"]["discovery_url"] =
            json!("http://127.0.0.1:9/.well-known/openid-configuration");
        assert!(provider_state_from_json(&config.to_string()).await.is_err());
        assert_eq!(provider.jwks_calls.load(Ordering::SeqCst), 0);

        let mut config: Value = serde_json::from_str(&provider_config_json(&provider)).unwrap();
        config["issuer"] = json!("https://other.example.invalid/");
        config["authorization_servers"] = json!(["https://other.example.invalid/"]);
        assert!(provider_state_from_json(&config.to_string()).await.is_err());
        assert_eq!(provider.jwks_calls.load(Ordering::SeqCst), 0);

        provider_task.abort();
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

    #[test]
    fn external_subject_accepts_auth0_separator_without_relaxing_policy_tokens() {
        assert!(validate_external_subject("auth0|user_123").is_ok());
        assert!(!is_policy_token("auth0|user_123"));
        assert!(validate_external_subject("auth0|user\n123").is_err());
    }
}
