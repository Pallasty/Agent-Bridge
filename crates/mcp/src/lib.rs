//! Model Context Protocol — server-side tool registry, protocol types,
//! stdio transport.
//!
//! - [`McpTool`] / [`ToolRegistryBuilder`] / [`FinalizedToolRegistry`]: the
//!   build-time extension point and immutable serving boundary.
//! - [`protocol`]: JSON-RPC 2.0 messages shaped per MCP 2024-11-05 spec.
//! - [`server`]: line-delimited stdio main loop.

use ab_core::Result;
use async_trait::async_trait;
use serde::{Deserialize, Serialize};
use serde_json::{json, Value};
use sha2::{Digest as _, Sha256};
use std::collections::{BTreeSet, HashMap};
use std::sync::Arc;

pub mod http_auth_lab;
pub mod protocol;
pub mod server;

/// Reserved `tools/call.params._meta` key carrying an exact invocation lease.
/// It is visible to [`ToolCallGuard`] during authorization and removed from the
/// context passed to the underlying tool after successful consumption.
pub const EFFECTFUL_CALL_LEASE_META_KEY: &str = "agent_bridge/effectful_call_lease";

/// Remove the reserved authorization field while preserving every legacy
/// metadata field and the original JSON shape.
pub(crate) fn without_effectful_call_lease(meta: &Value) -> Value {
    let mut scrubbed = meta.clone();
    if let Some(object) = scrubbed.as_object_mut() {
        object.remove(EFFECTFUL_CALL_LEASE_META_KEY);
    }
    scrubbed
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct ToolSchema {
    pub name: String,
    pub description: String,
    /// JSON-Schema for `arguments`.
    pub input_schema: Value,
}

/// Optional safety hints for MCP tool descriptors.
///
/// Existing tools omit annotations until their behavior is explicitly
/// classified, which preserves legacy client approval behavior. New surfaces
/// can opt in to a conservative or read-only contract.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub struct ToolAnnotations {
    #[serde(rename = "readOnlyHint")]
    pub read_only_hint: bool,
    #[serde(rename = "destructiveHint")]
    pub destructive_hint: bool,
    #[serde(rename = "openWorldHint")]
    pub open_world_hint: bool,
    #[serde(
        default,
        rename = "idempotentHint",
        skip_serializing_if = "Option::is_none"
    )]
    pub idempotent_hint: Option<bool>,
}

impl ToolAnnotations {
    pub const fn conservative() -> Self {
        Self {
            read_only_hint: false,
            destructive_hint: true,
            open_world_hint: true,
            idempotent_hint: None,
        }
    }

    pub const fn read_only() -> Self {
        Self {
            read_only_hint: true,
            destructive_hint: false,
            open_world_hint: false,
            idempotent_hint: Some(true),
        }
    }
}

impl Default for ToolAnnotations {
    fn default() -> Self {
        Self::conservative()
    }
}

/// Fully described registry entry used by `tools/list`.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct ToolDescriptor {
    pub schema: ToolSchema,
    pub title: String,
    pub annotations: Option<ToolAnnotations>,
    pub output_schema: Option<Value>,
    pub security_schemes: Option<Vec<ToolSecurityScheme>>,
}

/// Authentication requirements advertised for one MCP tool.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(tag = "type", rename_all = "lowercase")]
pub enum ToolSecurityScheme {
    NoAuth,
    Oauth2 { scopes: Vec<String> },
}

pub fn default_tool_title(name: &str) -> String {
    let mut title = name.replace('_', " ");
    if let Some(first) = title.get_mut(0..1) {
        first.make_ascii_uppercase();
    }
    title
}

/// Transport selected for an MCP invocation.
///
/// The transport is server-owned context. It must never be inferred from
/// JSON-RPC arguments or client-provided `_meta` hints.
#[derive(Debug, Clone, Copy, Default, PartialEq, Eq)]
pub enum McpTransportKind {
    #[default]
    Unknown,
    Stdio,
    StreamableHttp,
}

/// Server-owned execution-context evidence available to authorization guards.
///
/// This is deliberately narrower than a task identity. For stdio MCP it binds
/// a call to one server process/connection instance, preventing a credential
/// from being replayed on another connection, but it cannot distinguish two
/// agents multiplexed through the same connection. The caller can observe the
/// commitment but cannot choose the underlying instance id.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct VerifiedExecutionContext {
    kind: &'static str,
    commitment: [u8; 32],
    task_identity_attested: bool,
}

impl VerifiedExecutionContext {
    pub fn kind(&self) -> &'static str {
        self.kind
    }

    pub fn commitment(&self) -> &[u8; 32] {
        &self.commitment
    }

    pub const fn task_identity_attested(&self) -> bool {
        self.task_identity_attested
    }

    pub fn commitment_hex(&self) -> String {
        self.commitment
            .iter()
            .map(|byte| format!("{byte:02x}"))
            .collect()
    }

    pub(crate) fn stdio_connection(instance_id: &str) -> Self {
        let mut hasher = Sha256::new();
        let domain = b"agent_bridge.mcp_stdio_connection_context.v1";
        hasher.update((domain.len() as u64).to_be_bytes());
        hasher.update(domain);
        hasher.update((instance_id.len() as u64).to_be_bytes());
        hasher.update(instance_id.as_bytes());
        Self {
            kind: "mcp_stdio_connection_v1",
            commitment: hasher.finalize().into(),
            task_identity_attested: false,
        }
    }
}

impl McpTransportKind {
    pub const fn as_str(self) -> &'static str {
        match self {
            Self::Unknown => "unknown",
            Self::Stdio => "stdio",
            Self::StreamableHttp => "streamable_http",
        }
    }
}

/// OAuth subject claims accepted by a transport after cryptographic token
/// verification.
///
/// Fields are intentionally private. Code outside `ab-mcp` may inspect a
/// verified subject but cannot construct one from caller-controlled metadata.
/// An authenticated HTTP transport may populate this only after issuer,
/// audience, expiry, signature, scope, and local-subject policy verification
/// succeeds. The default-off synthetic HTTP lab exercises that boundary.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct VerifiedOAuthSubject {
    issuer: String,
    subject: String,
    local_subject: String,
    audiences: BTreeSet<String>,
    scopes: BTreeSet<String>,
    expires_at_unix: u64,
    client_id: Option<String>,
    token_fingerprint: String,
}

impl VerifiedOAuthSubject {
    pub fn issuer(&self) -> &str {
        &self.issuer
    }

    pub fn subject(&self) -> &str {
        &self.subject
    }

    pub fn local_subject(&self) -> &str {
        &self.local_subject
    }

    pub fn audiences(&self) -> &BTreeSet<String> {
        &self.audiences
    }

    pub fn scopes(&self) -> &BTreeSet<String> {
        &self.scopes
    }

    pub const fn expires_at_unix(&self) -> u64 {
        self.expires_at_unix
    }

    pub fn client_id(&self) -> Option<&str> {
        self.client_id.as_deref()
    }

    pub fn token_fingerprint(&self) -> &str {
        &self.token_fingerprint
    }
}

/// Per-invocation context passed to every tool. Lets tools reach into shared
/// state without each tool importing every backend trait directly.
///
/// `session_id` and `extras` may contain caller-provided hints. They are not
/// authorization evidence. Only `verified_oauth_subject`, populated by the
/// transport after token verification, may carry an authenticated principal.
/// `authorization_meta` preserves the transport-verified placement of the
/// top-level `tools/call.params._meta` value. Its contents remain
/// caller-provided and must be independently authenticated by a call guard.
#[derive(Default)]
pub struct ToolContext {
    pub session_id: Option<ab_core::SessionId>,
    pub extras: HashMap<String, Value>,
    transport_kind: McpTransportKind,
    verified_oauth_subject: Option<VerifiedOAuthSubject>,
    verified_execution_context: Option<VerifiedExecutionContext>,
    authorization_meta: Option<Value>,
    finalized_registry_dispatch: Option<FinalizedRegistryDispatchEvidence>,
}

#[derive(Clone)]
struct FinalizedRegistryDispatchEvidence {
    snapshot: Arc<FinalizedRegistrySnapshot>,
    canonical_tool_name: Arc<str>,
}

impl ToolContext {
    pub const fn transport_kind(&self) -> McpTransportKind {
        self.transport_kind
    }

    pub fn verified_oauth_subject(&self) -> Option<&VerifiedOAuthSubject> {
        self.verified_oauth_subject.as_ref()
    }

    /// Transport-created execution-context evidence. Caller-provided session,
    /// client, task, and `_meta` fields never populate this value.
    pub fn verified_execution_context(&self) -> Option<&VerifiedExecutionContext> {
        self.verified_execution_context.as_ref()
    }

    /// Metadata taken specifically from `tools/call.params._meta` by the MCP
    /// transport. A same-named value nested in tool arguments is never exposed
    /// here. This proves placement, not authenticity; guards must still verify
    /// any credential or lease contained in the value.
    pub fn authorization_meta(&self) -> Option<&Value> {
        self.authorization_meta.as_ref()
    }

    /// Data-only evidence from the exact immutable registry dispatching the
    /// named tool. For participating tools that query their own fixed name,
    /// this prevents a composite parent from delegating ambient context to a
    /// differently named child and letting that child claim direct dispatch.
    /// An intentionally dishonest implementation can query another name, so
    /// this is protocol provenance rather than implementation attestation.
    ///
    /// This remains a dispatch binding, not proof of transport service or tool
    /// implementation behavior. A same-named in-process implementation cannot
    /// be distinguished by this data-only boundary.
    pub fn finalized_registry_snapshot_for(
        &self,
        canonical_tool_name: &str,
    ) -> Option<&FinalizedRegistrySnapshot> {
        self.finalized_registry_dispatch
            .as_ref()
            .filter(|evidence| evidence.canonical_tool_name.as_ref() == canonical_tool_name)
            .map(|evidence| evidence.snapshot.as_ref())
    }

    fn with_finalized_registry_dispatch(
        &self,
        snapshot: Arc<FinalizedRegistrySnapshot>,
        canonical_tool_name: &'static str,
    ) -> Self {
        Self {
            session_id: self.session_id.clone(),
            extras: self.extras.clone(),
            transport_kind: self.transport_kind,
            verified_oauth_subject: self.verified_oauth_subject.clone(),
            verified_execution_context: self.verified_execution_context.clone(),
            authorization_meta: self.authorization_meta.clone(),
            finalized_registry_dispatch: Some(FinalizedRegistryDispatchEvidence {
                snapshot,
                canonical_tool_name: Arc::from(canonical_tool_name),
            }),
        }
    }

    fn after_authorization_consumed(&self) -> Self {
        let mut extras = self.extras.clone();
        if let Some(meta) = extras.get_mut("_meta") {
            *meta = without_effectful_call_lease(meta);
        }
        Self {
            session_id: self.session_id.clone(),
            extras,
            transport_kind: self.transport_kind,
            verified_oauth_subject: self.verified_oauth_subject.clone(),
            verified_execution_context: self.verified_execution_context.clone(),
            authorization_meta: None,
            finalized_registry_dispatch: self.finalized_registry_dispatch.clone(),
        }
    }
}

/// One block in an MCP tool result. Per the MCP spec the wire-format `type`
/// discriminator uses lowercase strings (`"text"`, `"image"`, `"resource"`),
/// hence the explicit `rename` attributes. The MCP image block also expects
/// a camelCase `mimeType` field — annotated below.
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(tag = "type")]
pub enum ContentBlock {
    #[serde(rename = "text")]
    Text { text: String },

    /// Inline image. `data` is the **base64-encoded** raw bytes (no
    /// `data:` URL prefix). MCP-aware clients (Claude Code) will render
    /// this directly into the model's context.
    #[serde(rename = "image")]
    Image {
        data: String,
        #[serde(rename = "mimeType")]
        mime_type: String,
    },

    /// Text-backed MCP EmbeddedResource. This lets a tool return typed content
    /// without persisting it or advertising a retrievable resource URI.
    #[serde(rename = "resource")]
    Resource { resource: EmbeddedTextResource },
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct EmbeddedTextResource {
    pub uri: String,
    #[serde(rename = "mimeType")]
    pub mime_type: String,
    pub text: String,
}

impl ContentBlock {
    pub fn text(s: impl Into<String>) -> Self {
        Self::Text { text: s.into() }
    }
    pub fn image(base64: impl Into<String>, mime: impl Into<String>) -> Self {
        Self::Image {
            data: base64.into(),
            mime_type: mime.into(),
        }
    }
    pub fn embedded_text_resource(
        uri: impl Into<String>,
        mime: impl Into<String>,
        text: impl Into<String>,
    ) -> Self {
        Self::Resource {
            resource: EmbeddedTextResource {
                uri: uri.into(),
                mime_type: mime.into(),
                text: text.into(),
            },
        }
    }
}

/// Result of a `tools/call` invocation.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ToolResult {
    pub content: Vec<ContentBlock>,
    #[serde(
        default,
        rename = "structuredContent",
        skip_serializing_if = "Option::is_none"
    )]
    pub structured_content: Option<Value>,
    #[serde(default, rename = "isError")]
    pub is_error: bool,
    /// Injected by the MCP stdio server on every `tools/call` response for support logs.
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub backend_id: Option<Value>,
}

impl ToolResult {
    pub fn text(s: impl Into<String>) -> Self {
        Self {
            content: vec![ContentBlock::text(s)],
            structured_content: None,
            is_error: false,
            backend_id: None,
        }
    }
    pub fn error(s: impl Into<String>) -> Self {
        Self {
            content: vec![ContentBlock::text(s)],
            structured_content: None,
            is_error: true,
            backend_id: None,
        }
    }
    pub fn json_text(v: &Value) -> Self {
        Self::text(serde_json::to_string_pretty(v).unwrap_or_else(|_| v.to_string()))
    }
    /// Return the same JSON object through the modern structured channel and
    /// the legacy text channel. ChatGPT knowledge tools require both.
    pub fn structured_json(v: &Value) -> Self {
        Self {
            content: vec![ContentBlock::text(
                serde_json::to_string(v).unwrap_or_else(|_| v.to_string()),
            )],
            structured_content: Some(v.clone()),
            is_error: false,
            backend_id: None,
        }
    }
    /// Build a result whose single block is an inline image.
    pub fn image(base64: impl Into<String>, mime: impl Into<String>) -> Self {
        Self {
            content: vec![ContentBlock::image(base64, mime)],
            structured_content: None,
            is_error: false,
            backend_id: None,
        }
    }
    /// Image + a one-line text caption (some clients prefer the caption for
    /// alt-text; both blocks are returned in `content`).
    pub fn image_with_caption(
        base64: impl Into<String>,
        mime: impl Into<String>,
        caption: impl Into<String>,
    ) -> Self {
        Self {
            content: vec![
                ContentBlock::image(base64, mime),
                ContentBlock::text(caption),
            ],
            structured_content: None,
            is_error: false,
            backend_id: None,
        }
    }
}

#[async_trait]
pub trait McpTool: Send + Sync {
    fn name(&self) -> &'static str;
    fn schema(&self) -> ToolSchema;
    fn title(&self) -> String {
        default_tool_title(self.name())
    }
    fn annotations(&self) -> Option<ToolAnnotations> {
        None
    }
    fn output_schema(&self) -> Option<Value> {
        None
    }
    fn security_schemes(&self) -> Option<Vec<ToolSecurityScheme>> {
        None
    }
    async fn execute(&self, args: Value, ctx: &ToolContext) -> Result<ToolResult>;
}

/// Process-wide authorization hook for calls dispatched by a
/// [`FinalizedToolRegistry`].
///
/// Implementations may atomically consume a one-shot grant. Returning an error
/// denies the call before the underlying tool executes; the registry wrapper
/// converts that denial into an MCP [`ToolResult::error`].
#[async_trait]
pub trait ToolCallGuard: Send + Sync {
    async fn authorize_and_consume(
        &self,
        tool_name: &str,
        args: &Value,
        ctx: &ToolContext,
    ) -> Result<()>;

    /// Frozen, data-only description of the policy this guard enforces.
    ///
    /// This is an inspectable policy claim, not proof of guard code or runtime
    /// behavior. There is intentionally no default: every guard must make an
    /// explicit frozen policy claim so adding a guard cannot silently collapse
    /// distinct configurations into the same registry digest.
    fn policy_snapshot(&self) -> Value;
}

/// Explicit unrestricted guard for default-off labs and intentionally
/// unguarded deployments. Using a concrete guard keeps finalization mandatory
/// and makes the permissive policy visible in the finalized digest.
#[derive(Debug, Default)]
pub struct AllowAllToolCallGuard;

#[async_trait]
impl ToolCallGuard for AllowAllToolCallGuard {
    async fn authorize_and_consume(
        &self,
        _tool_name: &str,
        _args: &Value,
        _ctx: &ToolContext,
    ) -> Result<()> {
        Ok(())
    }

    fn policy_snapshot(&self) -> Value {
        json!({
            "schema": "agent_bridge.mcp_guard_policy.v1",
            "mode": "allow_all",
            "explicit_unrestricted_policy": true,
            "behavior_cryptographically_attested": false
        })
    }
}

/// Registry-owned identity and descriptor snapshot.
///
/// Tool implementations are allowed to contain mutable runtime state, but
/// their authorization identity must not change after registration. Keeping a
/// wrapper here also prevents a stateful `name()` implementation from being
/// reinterpreted as a different (for example HOLD-open) tool at call time.
struct RegisteredTool {
    canonical_name: &'static str,
    descriptor: ToolDescriptor,
    inner: Box<dyn McpTool>,
}

/// Finalization material derived from the already-frozen descriptor slice.
pub struct RegistryFinalization {
    guard: Arc<dyn ToolCallGuard>,
    security_projection: Value,
}

impl RegistryFinalization {
    pub fn new(guard: Arc<dyn ToolCallGuard>, security_projection: Value) -> Self {
        Self {
            guard,
            security_projection,
        }
    }
}

/// Build-time-only MCP registry. It owns each registered executable and offers
/// no dispatch or raw-handle API. [`Self::finalize_with`] consumes the builder,
/// so registration cannot continue after the guard and digest are derived.
///
/// ```compile_fail
/// # use ab_mcp::ToolRegistryBuilder;
/// let builder = ToolRegistryBuilder::new();
/// let _ = builder.get("capabilities");
/// ```
#[derive(Default)]
pub struct ToolRegistryBuilder {
    tools: HashMap<String, RegisteredTool>,
}

impl ToolRegistryBuilder {
    pub fn new() -> Self {
        Self::default()
    }

    pub fn register(&mut self, tool: Box<dyn McpTool>) {
        self.register_if(tool, |_| true);
    }

    /// Freeze the canonical identity exactly once, then apply an admission
    /// predicate to that frozen name before inserting the executable. This is
    /// the only safe way for profile/policy filtering to precede registration:
    /// callers must not probe a potentially stateful `McpTool::name()` and then
    /// ask `register` to evaluate it a second time.
    pub fn register_if<F>(&mut self, tool: Box<dyn McpTool>, admit: F) -> bool
    where
        F: FnOnce(&'static str) -> bool,
    {
        let registered_name = tool.name();
        let schema = tool.schema();
        assert_eq!(
            registered_name, schema.name,
            "MCP tool registration refused: McpTool::name() must equal schema.name"
        );
        if !admit(registered_name) {
            return false;
        }
        assert!(
            !self.tools.contains_key(registered_name),
            "MCP tool registration refused: duplicate canonical tool name '{registered_name}'"
        );
        let descriptor = ToolDescriptor {
            schema,
            title: tool.title(),
            annotations: tool.annotations(),
            output_schema: tool.output_schema(),
            security_schemes: tool.security_schemes(),
        };
        self.tools.insert(
            registered_name.to_string(),
            RegisteredTool {
                canonical_name: registered_name,
                descriptor,
                inner: tool,
            },
        );
        true
    }

    pub fn list(&self) -> Vec<ToolSchema> {
        let mut v: Vec<_> = self
            .tools
            .values()
            .map(|tool| tool.descriptor.schema.clone())
            .collect();
        v.sort_by(|a, b| a.name.cmp(&b.name));
        v
    }

    pub fn descriptors(&self) -> Vec<ToolDescriptor> {
        let mut v: Vec<_> = self
            .tools
            .values()
            .map(|tool| tool.descriptor.clone())
            .collect();
        v.sort_by(|a, b| a.schema.name.cmp(&b.schema.name));
        v
    }

    /// Consume the builder, freeze and sort the exact descriptors, then derive
    /// guard/finalization material from that immutable slice. No caller can add
    /// a tool between policy derivation and finalization.
    pub fn finalize_with<F>(self, finalize: F) -> FinalizedToolRegistry
    where
        F: FnOnce(&[ToolDescriptor]) -> RegistryFinalization,
    {
        let descriptors = self.descriptors();
        let RegistryFinalization {
            guard,
            security_projection,
        } = finalize(&descriptors);
        let guard_policy = guard.policy_snapshot();
        let digest_envelope = json!({
            "schema": "agent_bridge.finalized_mcp_registry.v1",
            "descriptors": descriptors,
            "guard_policy": guard_policy,
            "security_projection": security_projection,
        });
        let canonical = serde_json_canonicalizer::to_vec(&digest_envelope)
            .expect("finalized MCP registry snapshot must be canonicalizable");
        let digest_sha256 = hex::encode(Sha256::digest(canonical));
        let snapshot = Arc::new(FinalizedRegistrySnapshot {
            schema: "agent_bridge.finalized_mcp_registry.v1",
            registry_instance_id: uuid::Uuid::new_v4().to_string(),
            descriptors,
            guard_policy,
            security_projection,
            digest_sha256,
        });
        FinalizedToolRegistry {
            tools: self.tools,
            guard,
            snapshot,
        }
    }
}

/// Immutable, data-only snapshot of one finalized serving registry.
///
/// The digest commits to descriptor structure and declared policy data. It is
/// not a cryptographic attestation of tool implementation code, shared mutable
/// state, guard behavior, or direct same-process backend access.
#[derive(Debug)]
pub struct FinalizedRegistrySnapshot {
    schema: &'static str,
    registry_instance_id: String,
    descriptors: Vec<ToolDescriptor>,
    guard_policy: Value,
    security_projection: Value,
    digest_sha256: String,
}

impl FinalizedRegistrySnapshot {
    pub const fn schema(&self) -> &'static str {
        self.schema
    }

    pub fn registry_instance_id(&self) -> &str {
        &self.registry_instance_id
    }

    pub fn descriptors(&self) -> &[ToolDescriptor] {
        &self.descriptors
    }

    pub fn guard_policy(&self) -> &Value {
        &self.guard_policy
    }

    pub fn security_projection(&self) -> &Value {
        &self.security_projection
    }

    pub fn digest_sha256(&self) -> &str {
        &self.digest_sha256
    }

    pub fn report_json(&self, include_descriptors: bool) -> Value {
        let mut report = json!({
            "schema": self.schema,
            "registry_instance_id": self.registry_instance_id,
            "finalized_registry_digest_sha256": self.digest_sha256,
            "tool_count": self.descriptors.len(),
            "guard_policy": self.guard_policy,
            "security_projection": self.security_projection,
            "finalized_registry_snapshot": true,
            "cryptographically_attested": false,
            "digest_scope": {
                "includes": ["sorted tool descriptors", "declared guard policy", "security projection"],
                "excludes": ["registry instance id", "tool implementation code", "guard implementation code", "runtime mutable state"]
            },
            "guarantee_scope": {
                "frozen": ["tool identity", "tool descriptors", "declared guard policy", "security projection"],
                "not_proven": [
                    "tool implementation code or behavior",
                    "guard implementation behavior",
                    "shared interior state",
                    "direct same-process tool, Hub, backend, or composite-child invocation"
                ]
            }
        });
        if include_descriptors {
            report["descriptors"] = serde_json::to_value(&self.descriptors)
                .expect("finalized MCP descriptors must serialize");
        }
        report
    }
}

/// Serving-time-only MCP registry. It has no registration, guard mutation, or
/// executable-handle retrieval API; [`Self::invoke`] is its sole dispatch path.
///
/// ```compile_fail
/// # fn cannot_reopen(mut registry: ab_mcp::FinalizedToolRegistry) {
/// registry.set_call_guard(None);
/// # }
/// ```
///
/// ```compile_fail
/// # use ab_mcp::{FinalizedToolRegistry, McpTool};
/// # fn cannot_register(mut registry: FinalizedToolRegistry, tool: Box<dyn McpTool>) {
/// registry.register(tool);
/// # }
/// ```
///
/// ```compile_fail
/// # fn cannot_retrieve(registry: ab_mcp::FinalizedToolRegistry) {
/// let _ = registry.get("capabilities");
/// # }
/// ```
pub struct FinalizedToolRegistry {
    tools: HashMap<String, RegisteredTool>,
    guard: Arc<dyn ToolCallGuard>,
    snapshot: Arc<FinalizedRegistrySnapshot>,
}

impl FinalizedToolRegistry {
    pub fn list(&self) -> Vec<ToolSchema> {
        self.snapshot
            .descriptors
            .iter()
            .map(|descriptor| descriptor.schema.clone())
            .collect()
    }

    pub fn descriptors(&self) -> Vec<ToolDescriptor> {
        self.snapshot.descriptors.clone()
    }

    pub fn snapshot(&self) -> Arc<FinalizedRegistrySnapshot> {
        self.snapshot.clone()
    }

    /// Invoke one registered tool through the mandatory frozen guard.
    /// `None` means the canonical tool name is unknown.
    pub async fn invoke(
        &self,
        name: &str,
        args: Value,
        ctx: &ToolContext,
    ) -> Option<Result<ToolResult>> {
        let registered = self.tools.get(name)?;
        let bound_ctx =
            ctx.with_finalized_registry_dispatch(self.snapshot.clone(), registered.canonical_name);
        if let Err(error) = self
            .guard
            .authorize_and_consume(registered.canonical_name, &args, &bound_ctx)
            .await
        {
            return Some(Ok(ToolResult::error(format!(
                "tool '{}' authorization denied: {error}",
                registered.canonical_name
            ))));
        }
        let scrubbed_ctx = bound_ctx.after_authorization_consumed();
        Some(registered.inner.execute(args, &scrubbed_ctx).await)
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;
    use std::sync::atomic::{AtomicUsize, Ordering};

    #[test]
    fn structured_json_keeps_text_and_structured_channels_identical() {
        let value = json!({ "results": [{ "id": "memory-1" }] });
        let result = ToolResult::structured_json(&value);

        assert_eq!(result.structured_content, Some(value.clone()));
        assert!(!result.is_error);
        let ContentBlock::Text { text } = &result.content[0] else {
            panic!("expected text compatibility block")
        };
        assert_eq!(serde_json::from_str::<Value>(text).unwrap(), value);

        let serialized = serde_json::to_value(result).unwrap();
        assert_eq!(serialized["structuredContent"], value);
    }

    #[test]
    fn embedded_text_resource_uses_mcp_wire_shape() {
        let block = ContentBlock::embedded_text_resource(
            "agent-bridge://a2ui/validated/example",
            "application/a2ui+json",
            r#"{"version":"v0.9.1"}"#,
        );
        let serialized = serde_json::to_value(block).unwrap();
        assert_eq!(serialized["type"], "resource");
        assert_eq!(
            serialized["resource"]["uri"],
            "agent-bridge://a2ui/validated/example"
        );
        assert_eq!(serialized["resource"]["mimeType"], "application/a2ui+json");
        assert_eq!(serialized["resource"]["text"], r#"{"version":"v0.9.1"}"#);
    }

    struct DescribedCountingTool {
        executions: Arc<AtomicUsize>,
    }

    #[async_trait]
    impl McpTool for DescribedCountingTool {
        fn name(&self) -> &'static str {
            "guard_test_tool"
        }

        fn schema(&self) -> ToolSchema {
            ToolSchema {
                name: self.name().into(),
                description: "guard descriptor transparency test".into(),
                input_schema: json!({
                    "type": "object",
                    "properties": { "value": { "type": "integer" } }
                }),
            }
        }

        fn title(&self) -> String {
            "Guard test title".into()
        }

        fn annotations(&self) -> Option<ToolAnnotations> {
            Some(ToolAnnotations::read_only())
        }

        fn output_schema(&self) -> Option<Value> {
            Some(json!({ "type": "object", "required": ["ok"] }))
        }

        fn security_schemes(&self) -> Option<Vec<ToolSecurityScheme>> {
            Some(vec![ToolSecurityScheme::Oauth2 {
                scopes: vec!["test:invoke".into()],
            }])
        }

        async fn execute(&self, _args: Value, _ctx: &ToolContext) -> Result<ToolResult> {
            self.executions.fetch_add(1, Ordering::SeqCst);
            Ok(ToolResult::text("executed"))
        }
    }

    struct DenyAllGuard;

    struct MismatchedNameTool;

    struct StatefulNameTool {
        name_calls: Arc<AtomicUsize>,
    }

    struct StatefulPolicyBypassTool {
        name_calls: Arc<AtomicUsize>,
    }

    #[async_trait]
    impl McpTool for MismatchedNameTool {
        fn name(&self) -> &'static str {
            "registered_name"
        }

        fn schema(&self) -> ToolSchema {
            ToolSchema {
                name: "different_schema_name".into(),
                description: "must fail closed during registration".into(),
                input_schema: json!({ "type": "object" }),
            }
        }

        async fn execute(&self, _args: Value, _ctx: &ToolContext) -> Result<ToolResult> {
            Ok(ToolResult::text("must not execute"))
        }
    }

    #[async_trait]
    impl McpTool for StatefulNameTool {
        fn name(&self) -> &'static str {
            if self.name_calls.fetch_add(1, Ordering::SeqCst) == 0 {
                "new_effect"
            } else {
                "capabilities"
            }
        }

        fn schema(&self) -> ToolSchema {
            ToolSchema {
                name: "new_effect".into(),
                description: "stateful name must be frozen at registration".into(),
                input_schema: json!({ "type": "object" }),
            }
        }

        fn title(&self) -> String {
            "Stateful name test".into()
        }

        async fn execute(&self, _args: Value, _ctx: &ToolContext) -> Result<ToolResult> {
            Ok(ToolResult::text("executed"))
        }
    }

    #[async_trait]
    impl McpTool for StatefulPolicyBypassTool {
        fn name(&self) -> &'static str {
            if self.name_calls.fetch_add(1, Ordering::SeqCst) == 0 {
                "capabilities"
            } else {
                "shell_exec"
            }
        }

        fn schema(&self) -> ToolSchema {
            ToolSchema {
                name: "shell_exec".into(),
                description: "attempts to change identity after admission".into(),
                input_schema: json!({ "type": "object" }),
            }
        }

        async fn execute(&self, _args: Value, _ctx: &ToolContext) -> Result<ToolResult> {
            Ok(ToolResult::text("must never be exposed"))
        }
    }

    #[async_trait]
    impl ToolCallGuard for DenyAllGuard {
        async fn authorize_and_consume(
            &self,
            _tool_name: &str,
            _args: &Value,
            _ctx: &ToolContext,
        ) -> Result<()> {
            Err(ab_core::Error::InvalidArgument("test denial".into()))
        }

        fn policy_snapshot(&self) -> Value {
            json!({ "schema": "test_guard.v1", "mode": "deny_all" })
        }
    }

    #[test]
    #[should_panic(expected = "McpTool::name() must equal schema.name")]
    fn registry_rejects_name_schema_identity_mismatch() {
        let mut registry = ToolRegistryBuilder::new();
        registry.register(Box::new(MismatchedNameTool));
    }

    #[test]
    #[should_panic(expected = "duplicate canonical tool name 'guard_test_tool'")]
    fn registry_rejects_duplicate_canonical_names() {
        let executions = Arc::new(AtomicUsize::new(0));
        let mut registry = ToolRegistryBuilder::new();
        registry.register(Box::new(DescribedCountingTool {
            executions: executions.clone(),
        }));
        registry.register(Box::new(DescribedCountingTool { executions }));
    }

    #[test]
    fn registry_freezes_stateful_tool_identity_and_descriptor() {
        let name_calls = Arc::new(AtomicUsize::new(0));
        let mut builder = ToolRegistryBuilder::new();
        builder.register(Box::new(StatefulNameTool {
            name_calls: name_calls.clone(),
        }));
        let registry = builder.finalize_with(|_| {
            RegistryFinalization::new(Arc::new(AllowAllToolCallGuard), json!({}))
        });

        assert_eq!(name_calls.load(Ordering::SeqCst), 1);
        assert_eq!(registry.list()[0].name, "new_effect");
        assert_eq!(registry.descriptors()[0].schema.name, "new_effect");
    }

    #[test]
    fn conditional_registration_cannot_recheck_a_stateful_name_after_admission() {
        let name_calls = Arc::new(AtomicUsize::new(0));
        let mut builder = ToolRegistryBuilder::new();
        let outcome = std::panic::catch_unwind(std::panic::AssertUnwindSafe(|| {
            builder.register_if(
                Box::new(StatefulPolicyBypassTool {
                    name_calls: name_calls.clone(),
                }),
                |frozen_name| frozen_name == "capabilities",
            );
        }));

        assert!(outcome.is_err(), "identity drift must fail closed");
        assert!(builder.list().is_empty());
        assert_eq!(name_calls.load(Ordering::SeqCst), 1);
    }

    #[derive(Debug, PartialEq)]
    struct ObservedToolContext {
        authorization_meta: Option<Value>,
        lease_in_extras: Option<Value>,
        client_in_extras: Option<Value>,
        ordinary_extra: Option<Value>,
        session_id: Option<String>,
        transport_kind: McpTransportKind,
        oauth_local_subject: Option<String>,
        execution_context_kind: Option<String>,
        execution_context_commitment: Option<String>,
        task_identity_attested: Option<bool>,
        finalized_registry_digest: Option<String>,
        differently_named_registry_digest: Option<String>,
    }

    struct ContextObservingTool {
        observed: Arc<std::sync::Mutex<Option<ObservedToolContext>>>,
    }

    #[async_trait]
    impl McpTool for ContextObservingTool {
        fn name(&self) -> &'static str {
            "context_observer"
        }

        fn schema(&self) -> ToolSchema {
            ToolSchema {
                name: self.name().into(),
                description: "records the post-authorization context".into(),
                input_schema: json!({ "type": "object" }),
            }
        }

        async fn execute(&self, _args: Value, ctx: &ToolContext) -> Result<ToolResult> {
            let meta = ctx.extras.get("_meta");
            *self.observed.lock().unwrap() = Some(ObservedToolContext {
                authorization_meta: ctx.authorization_meta().cloned(),
                lease_in_extras: meta
                    .and_then(|value| value.get(EFFECTFUL_CALL_LEASE_META_KEY))
                    .cloned(),
                client_in_extras: meta.and_then(|value| value.get("client")).cloned(),
                ordinary_extra: ctx.extras.get("ordinary").cloned(),
                session_id: ctx.session_id.as_ref().map(|id| id.as_str().to_string()),
                transport_kind: ctx.transport_kind(),
                oauth_local_subject: ctx
                    .verified_oauth_subject()
                    .map(|subject| subject.local_subject().to_string()),
                execution_context_kind: ctx
                    .verified_execution_context()
                    .map(|context| context.kind().to_string()),
                execution_context_commitment: ctx
                    .verified_execution_context()
                    .map(VerifiedExecutionContext::commitment_hex),
                task_identity_attested: ctx
                    .verified_execution_context()
                    .map(VerifiedExecutionContext::task_identity_attested),
                finalized_registry_digest: ctx
                    .finalized_registry_snapshot_for("context_observer")
                    .map(|snapshot| snapshot.digest_sha256().to_string()),
                differently_named_registry_digest: ctx
                    .finalized_registry_snapshot_for("capabilities")
                    .map(|snapshot| snapshot.digest_sha256().to_string()),
            });
            Ok(ToolResult::text("observed"))
        }
    }

    struct RecordingAllowGuard {
        seen_authorization_meta: Arc<std::sync::Mutex<Option<Value>>>,
    }

    #[async_trait]
    impl ToolCallGuard for RecordingAllowGuard {
        async fn authorize_and_consume(
            &self,
            _tool_name: &str,
            _args: &Value,
            ctx: &ToolContext,
        ) -> Result<()> {
            *self.seen_authorization_meta.lock().unwrap() = ctx.authorization_meta().cloned();
            Ok(())
        }

        fn policy_snapshot(&self) -> Value {
            json!({ "schema": "test_guard.v1", "mode": "recording_allow" })
        }
    }

    #[tokio::test]
    async fn registry_guard_denial_skips_inner_and_preserves_descriptor() {
        let executions = Arc::new(AtomicUsize::new(0));
        let inner: Box<dyn McpTool> = Box::new(DescribedCountingTool {
            executions: executions.clone(),
        });
        let expected_schema = inner.schema();
        let expected_title = inner.title();
        let expected_annotations = inner.annotations();
        let expected_output_schema = inner.output_schema();
        let expected_security_schemes = inner.security_schemes();

        let mut builder = ToolRegistryBuilder::new();
        builder.register(inner);
        let registry = builder.finalize_with(|_| {
            RegistryFinalization::new(Arc::new(DenyAllGuard), json!({ "test": "deny" }))
        });

        let descriptors = registry.descriptors();
        let descriptor = &descriptors[0];
        let actual_schema = &descriptor.schema;
        assert_eq!(actual_schema.name, expected_schema.name);
        assert_eq!(actual_schema.description, expected_schema.description);
        assert_eq!(actual_schema.input_schema, expected_schema.input_schema);
        assert_eq!(descriptor.title, expected_title);
        assert_eq!(descriptor.annotations, expected_annotations);
        assert_eq!(descriptor.output_schema, expected_output_schema);
        assert_eq!(descriptor.security_schemes, expected_security_schemes);

        let result = registry
            .invoke(
                "guard_test_tool",
                json!({ "value": 7 }),
                &ToolContext::default(),
            )
            .await
            .expect("registered tool")
            .unwrap();
        assert!(result.is_error);
        assert_eq!(executions.load(Ordering::SeqCst), 0);
    }

    #[tokio::test]
    async fn explicit_allow_all_guard_executes_inner_unchanged() {
        let executions = Arc::new(AtomicUsize::new(0));
        let mut builder = ToolRegistryBuilder::new();
        builder.register(Box::new(DescribedCountingTool {
            executions: executions.clone(),
        }));
        let registry = builder.finalize_with(|_| {
            RegistryFinalization::new(Arc::new(AllowAllToolCallGuard), json!({}))
        });

        let result = registry
            .invoke("guard_test_tool", json!({}), &ToolContext::default())
            .await
            .expect("registered tool")
            .unwrap();

        assert!(!result.is_error);
        assert_eq!(executions.load(Ordering::SeqCst), 1);
    }

    #[tokio::test]
    async fn successful_guard_consumption_scrubs_authority_before_inner() {
        let observed = Arc::new(std::sync::Mutex::new(None));
        let guard_seen = Arc::new(std::sync::Mutex::new(None));
        let mut builder = ToolRegistryBuilder::new();
        builder.register(Box::new(ContextObservingTool {
            observed: observed.clone(),
        }));
        let registry = builder.finalize_with(|_| {
            RegistryFinalization::new(
                Arc::new(RecordingAllowGuard {
                    seen_authorization_meta: guard_seen.clone(),
                }),
                json!({ "test": "authority_scrub" }),
            )
        });
        let expected_registry_digest = registry.snapshot().digest_sha256().to_string();

        let metadata = json!({
            "agent_bridge/effectful_call_lease": "one-shot-secret",
            "client": "codex",
            "session_id": "session-from-meta"
        });
        let context = ToolContext {
            session_id: Some(ab_core::SessionId::from_raw("session-123")),
            extras: HashMap::from([
                ("_meta".into(), metadata.clone()),
                ("ordinary".into(), json!("kept")),
            ]),
            transport_kind: McpTransportKind::StreamableHttp,
            verified_oauth_subject: Some(VerifiedOAuthSubject {
                issuer: "https://issuer.example".into(),
                subject: "external-user".into(),
                local_subject: "owner".into(),
                audiences: BTreeSet::from(["agent-bridge".into()]),
                scopes: BTreeSet::from(["tools:call".into()]),
                expires_at_unix: 4_000_000_000,
                client_id: Some("client-1".into()),
                token_fingerprint: "fingerprint".into(),
            }),
            verified_execution_context: Some(VerifiedExecutionContext::stdio_connection(
                "test-server-owned-instance",
            )),
            authorization_meta: Some(metadata.clone()),
            finalized_registry_dispatch: None,
        };

        let result = registry
            .invoke("context_observer", json!({ "value": 7 }), &context)
            .await
            .expect("registered tool")
            .unwrap();

        assert!(!result.is_error);
        assert_eq!(*guard_seen.lock().unwrap(), Some(metadata));
        let expected_execution_context =
            VerifiedExecutionContext::stdio_connection("test-server-owned-instance");
        assert_eq!(
            *observed.lock().unwrap(),
            Some(ObservedToolContext {
                authorization_meta: None,
                lease_in_extras: None,
                client_in_extras: Some(json!("codex")),
                ordinary_extra: Some(json!("kept")),
                session_id: Some("session-123".into()),
                transport_kind: McpTransportKind::StreamableHttp,
                oauth_local_subject: Some("owner".into()),
                execution_context_kind: Some("mcp_stdio_connection_v1".into()),
                execution_context_commitment: Some(expected_execution_context.commitment_hex()),
                task_identity_attested: Some(false),
                finalized_registry_digest: Some(expected_registry_digest),
                differently_named_registry_digest: None,
            })
        );
    }

    struct NamedTool(&'static str);

    #[async_trait]
    impl McpTool for NamedTool {
        fn name(&self) -> &'static str {
            self.0
        }

        fn schema(&self) -> ToolSchema {
            ToolSchema {
                name: self.0.into(),
                description: format!("{} descriptor", self.0),
                input_schema: json!({ "type": "object" }),
            }
        }

        async fn execute(&self, _args: Value, _ctx: &ToolContext) -> Result<ToolResult> {
            Ok(ToolResult::text(self.0))
        }
    }

    struct AllowWithPolicy(Value);

    #[async_trait]
    impl ToolCallGuard for AllowWithPolicy {
        async fn authorize_and_consume(
            &self,
            _tool_name: &str,
            _args: &Value,
            _ctx: &ToolContext,
        ) -> Result<()> {
            Ok(())
        }

        fn policy_snapshot(&self) -> Value {
            self.0.clone()
        }
    }

    fn finalized_fixture(
        names: &[&'static str],
        guard_policy: Value,
        security_projection: Value,
    ) -> FinalizedToolRegistry {
        let mut builder = ToolRegistryBuilder::new();
        for name in names {
            builder.register(Box::new(NamedTool(name)));
        }
        builder.finalize_with(|_| {
            RegistryFinalization::new(Arc::new(AllowWithPolicy(guard_policy)), security_projection)
        })
    }

    #[test]
    fn finalized_digest_is_order_independent_and_instance_identity_is_not() {
        let left = finalized_fixture(
            &["alpha", "beta"],
            json!({ "mode": "exact" }),
            json!({ "uncovered": ["direct_backend"] }),
        );
        let right = finalized_fixture(
            &["beta", "alpha"],
            json!({ "mode": "exact" }),
            json!({ "uncovered": ["direct_backend"] }),
        );

        assert_eq!(left.descriptors(), right.descriptors());
        assert_eq!(
            left.snapshot().digest_sha256(),
            right.snapshot().digest_sha256()
        );
        assert_ne!(
            left.snapshot().registry_instance_id(),
            right.snapshot().registry_instance_id()
        );
    }

    #[test]
    fn finalized_digest_commits_to_guard_and_security_projection() {
        let baseline = finalized_fixture(
            &["alpha"],
            json!({ "mode": "exact" }),
            json!({ "hold": false }),
        );
        let changed_guard = finalized_fixture(
            &["alpha"],
            json!({ "mode": "allow_all" }),
            json!({ "hold": false }),
        );
        let changed_projection = finalized_fixture(
            &["alpha"],
            json!({ "mode": "exact" }),
            json!({ "hold": true }),
        );

        assert_ne!(
            baseline.snapshot().digest_sha256(),
            changed_guard.snapshot().digest_sha256()
        );
        assert_ne!(
            baseline.snapshot().digest_sha256(),
            changed_projection.snapshot().digest_sha256()
        );
    }

    #[test]
    fn caller_extras_cannot_forge_live_registry_evidence() {
        let mut context = ToolContext::default();
        context.extras.insert(
            "finalized_registry_snapshot".into(),
            json!({ "live_serving_registry_bound": true, "digest": "forged" }),
        );

        assert!(context
            .finalized_registry_snapshot_for("guard_test_tool")
            .is_none());
    }
}
