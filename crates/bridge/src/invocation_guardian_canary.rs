//! Default-off Invocation Guardian v2 source canary.
//!
//! The witness in this module is deliberately in-process and rollbackable. It
//! validates C1 protocol, fault, permit, marker, and stdio-dispatch mechanics;
//! it is never a protected monotonic witness and grants no production claim.

use std::collections::HashMap;
use std::fs::File;
use std::io::Write;
use std::os::fd::{AsRawFd, FromRawFd};
use std::os::unix::fs::{MetadataExt, PermissionsExt};
use std::path::{Path, PathBuf};
use std::sync::{Arc, Mutex};
use std::time::{Duration, SystemTime, UNIX_EPOCH};

use ab_core::{Error, Result};
use ab_mcp::{
    FinalizedToolRegistry, McpTool, RegistryFinalization, ToolAnnotations, ToolCallGuard,
    ToolContext, ToolRegistryBuilder, ToolResult, ToolSchema,
};
use async_trait::async_trait;
use base64::engine::general_purpose::STANDARD_NO_PAD;
use base64::Engine as _;
use ring::rand::{SecureRandom, SystemRandom};
use ring::signature::{Ed25519KeyPair, KeyPair as _, UnparsedPublicKey, ED25519};
use serde_json::{json, Value};
use sha2::{Digest, Sha256};

use crate::invocation_lease_scope::{
    domain_hash, CanaryTrustPins, Commitment, ObservedCanaryInvocation, SignedCanaryLease,
    SIGNATURE_BYTES,
};

pub const CANARY_TOOL_NAME: &str = "invocation_guardian_canary_write";
pub const CANARY_META_KEY: &str = "agent_bridge/invocation_guardian_canary_v2";
const HANDOFF_BYTES: usize = 96;
const RECEIPT_DOMAIN: &[u8] = b"agent_bridge.invocation_guardian.fake_receipt.v2\0";
const TARGET_DOMAIN: &[u8] = b"agent_bridge.invocation_guardian.canary_target.v2\0";
const TARGET_VALUE: &[u8] = b"fixed_operator_marker_directory";

#[derive(Clone)]
pub struct CanarySourceConfig {
    pub enabled: bool,
    pub trust_pins: CanaryTrustPins,
    pub principal_kind: String,
    pub principal_commitment: Commitment,
    pub provider_key_generation: u64,
    pub provider_signing_key: Arc<Ed25519KeyPair>,
    pub witness: Arc<FakeProtectedWitness>,
    pub marker_root: PathBuf,
    pub witness_timeout: Duration,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum FakeWitnessFault {
    None,
    BeforeCommitIndeterminate,
    AfterCommitResponseLost,
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct FakeProviderReceipt {
    pub namespace: String,
    pub revision: u64,
    pub previous_head: Commitment,
    pub new_head: Commitment,
    pub token_commitment: Commitment,
    pub exact_scope_commitment: Commitment,
    pub request_challenge: Commitment,
    pub provider_key_generation: u64,
    pub signature: [u8; SIGNATURE_BYTES],
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub enum FakeWitnessDecision {
    FreshCommitted(FakeProviderReceipt),
    AlreadyCommitted(FakeProviderReceipt),
    Conflict,
    Indeterminate,
    Hold,
}

#[derive(Clone)]
pub struct FakeWitnessRequest {
    pub namespace: String,
    pub token_commitment: Commitment,
    pub exact_scope_commitment: Commitment,
    pub request_challenge: Commitment,
}

#[async_trait]
pub trait AsyncProtectedWitness: Send + Sync {
    async fn consume_once(&self, request: FakeWitnessRequest) -> FakeWitnessDecision;
}

pub struct FakeProtectedWitness {
    namespace: String,
    key_generation: u64,
    signing_key: Arc<Ed25519KeyPair>,
    state: Mutex<FakeWitnessState>,
}

struct FakeWitnessState {
    head: Commitment,
    revision: u64,
    by_token: HashMap<Commitment, FakeProviderReceipt>,
    next_fault: FakeWitnessFault,
}

impl FakeProtectedWitness {
    pub fn new(namespace: String, key_generation: u64, signing_key: Arc<Ed25519KeyPair>) -> Self {
        Self {
            namespace,
            key_generation,
            signing_key,
            state: Mutex::new(FakeWitnessState {
                head: [0; 32],
                revision: 0,
                by_token: HashMap::new(),
                next_fault: FakeWitnessFault::None,
            }),
        }
    }

    pub fn inject_once(&self, fault: FakeWitnessFault) {
        self.state.lock().expect("fake witness mutex").next_fault = fault;
    }

    pub fn committed_count(&self) -> usize {
        self.state
            .lock()
            .map(|state| state.by_token.len())
            .unwrap_or_default()
    }
}

#[async_trait]
impl AsyncProtectedWitness for FakeProtectedWitness {
    async fn consume_once(&self, request: FakeWitnessRequest) -> FakeWitnessDecision {
        if request.namespace != self.namespace
            || request.token_commitment.iter().all(|byte| *byte == 0)
            || request.exact_scope_commitment.iter().all(|byte| *byte == 0)
            || request.request_challenge.iter().all(|byte| *byte == 0)
        {
            return FakeWitnessDecision::Hold;
        }
        let Ok(mut state) = self.state.lock() else {
            return FakeWitnessDecision::Hold;
        };
        if let Some(receipt) = state.by_token.get(&request.token_commitment) {
            return if receipt.exact_scope_commitment == request.exact_scope_commitment {
                FakeWitnessDecision::AlreadyCommitted(receipt.clone())
            } else {
                FakeWitnessDecision::Conflict
            };
        }
        let fault = std::mem::replace(&mut state.next_fault, FakeWitnessFault::None);
        if fault == FakeWitnessFault::BeforeCommitIndeterminate {
            return FakeWitnessDecision::Indeterminate;
        }
        let Some(revision) = state.revision.checked_add(1) else {
            return FakeWitnessDecision::Hold;
        };
        let previous_head = state.head;
        let new_head = next_head(
            &self.namespace,
            revision,
            &previous_head,
            &request.token_commitment,
            &request.exact_scope_commitment,
        );
        let mut receipt = FakeProviderReceipt {
            namespace: self.namespace.clone(),
            revision,
            previous_head,
            new_head,
            token_commitment: request.token_commitment,
            exact_scope_commitment: request.exact_scope_commitment,
            request_challenge: request.request_challenge,
            provider_key_generation: self.key_generation,
            signature: [0; SIGNATURE_BYTES],
        };
        let signature = self.signing_key.sign(&receipt_message(&receipt));
        receipt.signature.copy_from_slice(signature.as_ref());
        state.head = new_head;
        state.revision = revision;
        state
            .by_token
            .insert(request.token_commitment, receipt.clone());
        if fault == FakeWitnessFault::AfterCommitResponseLost {
            FakeWitnessDecision::Indeterminate
        } else {
            FakeWitnessDecision::FreshCommitted(receipt)
        }
    }
}

struct FreshCanaryPermit {
    handoff: [u8; HANDOFF_BYTES],
}

impl FreshCanaryPermit {
    fn from_verified_fresh(receipt: &FakeProviderReceipt, receipt_commitment: Commitment) -> Self {
        let mut handoff = [0; HANDOFF_BYTES];
        handoff[..32].copy_from_slice(&receipt.token_commitment);
        handoff[32..64].copy_from_slice(&receipt.exact_scope_commitment);
        handoff[64..].copy_from_slice(&receipt_commitment);
        Self { handoff }
    }

    fn install(self, context: &ToolContext) -> Result<()> {
        context.install_guard_handoff(CANARY_TOOL_NAME, self.handoff.to_vec())
    }
}

struct CanaryGuard {
    config: CanarySourceConfig,
}

#[async_trait]
impl ToolCallGuard for CanaryGuard {
    async fn authorize_and_consume(
        &self,
        tool_name: &str,
        arguments: &Value,
        context: &ToolContext,
    ) -> Result<()> {
        if !self.config.enabled || tool_name != CANARY_TOOL_NAME || arguments != &json!({}) {
            return deny("canary disabled or invocation shape is not exact");
        }
        let snapshot = context
            .finalized_registry_snapshot_for(CANARY_TOOL_NAME)
            .ok_or_else(|| invalid("missing canonical finalized registry dispatch"))?;
        let registry_sha256 = decode_hex_32(snapshot.digest_sha256())?;
        let execution = context
            .verified_execution_context()
            .filter(|execution| execution.kind() == "mcp_stdio_connection_v1")
            .ok_or_else(|| invalid("missing server-owned stdio execution context"))?;
        let lease = parse_authorization_meta(context.authorization_meta())?;
        if lease.scope.tool_name != CANARY_TOOL_NAME {
            return deny("signed scope names a different tool");
        }
        let observed = ObservedCanaryInvocation {
            tool_name: tool_name.to_string(),
            arguments_jcs_sha256: arguments_jcs_sha256(arguments)?,
            target_sha256: canary_target_sha256(),
            registry_sha256,
            namespace: self.config.trust_pins.namespace.clone(),
            principal_kind: self.config.principal_kind.clone(),
            principal_commitment: self.config.principal_commitment,
            transport_kind: "stdio".into(),
            connection_commitment: *execution.commitment(),
        };
        let exact_scope_commitment = lease
            .verify(&self.config.trust_pins, &observed, unix_now()?)
            .map_err(|error| invalid(&format!("signed scope rejected: {error}")))?;
        let request_challenge = random_nonzero()?;
        let request = FakeWitnessRequest {
            namespace: self.config.trust_pins.namespace.clone(),
            token_commitment: lease.scope.token_commitment,
            exact_scope_commitment,
            request_challenge,
        };
        let decision = tokio::time::timeout(
            self.config.witness_timeout,
            self.config.witness.consume_once(request),
        )
        .await
        .unwrap_or(FakeWitnessDecision::Indeterminate);
        let receipt = match decision {
            FakeWitnessDecision::FreshCommitted(receipt) => receipt,
            FakeWitnessDecision::AlreadyCommitted(_) => return deny("already committed"),
            FakeWitnessDecision::Conflict => return deny("witness conflict"),
            FakeWitnessDecision::Indeterminate => return deny("witness indeterminate"),
            FakeWitnessDecision::Hold => return deny("witness hold"),
        };
        verify_receipt(
            &receipt,
            &self.config,
            &lease.scope.token_commitment,
            &exact_scope_commitment,
            &request_challenge,
        )?;
        let receipt_commitment = domain_hash(
            b"agent_bridge.invocation_guardian.provider_receipt.v2\0",
            &receipt_message(&receipt),
        );
        FreshCanaryPermit::from_verified_fresh(&receipt, receipt_commitment).install(context)
    }

    fn policy_snapshot(&self) -> Value {
        json!({
            "schema": "agent_bridge.invocation_guardian_canary_guard.v2",
            "enabled": self.config.enabled,
            "tool": CANARY_TOOL_NAME,
            "namespace": self.config.trust_pins.namespace,
            "issuer_key_commitment": hex_lower(&self.config.trust_pins.issuer_key_commitment),
            "ledger_generation": hex_lower(&self.config.trust_pins.ledger_generation),
            "provider_key_generation": self.config.provider_key_generation,
            "provider_verify_key_commitment": hex_lower(&domain_hash(
                b"agent_bridge.invocation_guardian.provider_key.v2\0",
                self.config.provider_signing_key.public_key().as_ref(),
            )),
            "witness_class": "in_process_fake_source_canary",
            "protected_witness": false,
            "production_authority": false,
            "fresh_only_dispatch": true,
            "already_committed_grants_dispatch": false,
        })
    }
}

struct CanaryMarkerTool {
    root: PathBuf,
}

#[async_trait]
impl McpTool for CanaryMarkerTool {
    fn name(&self) -> &'static str {
        CANARY_TOOL_NAME
    }

    fn schema(&self) -> ToolSchema {
        ToolSchema {
            name: CANARY_TOOL_NAME.into(),
            description: "Default-off source canary: write one fixed marker after a fresh fake-witness commitment. No caller-selected path or payload.".into(),
            input_schema: json!({
                "type": "object",
                "properties": {},
                "additionalProperties": false
            }),
        }
    }

    fn annotations(&self) -> Option<ToolAnnotations> {
        Some(ToolAnnotations {
            read_only_hint: false,
            destructive_hint: false,
            idempotent_hint: Some(true),
            open_world_hint: false,
        })
    }

    async fn execute(&self, arguments: Value, context: &ToolContext) -> Result<ToolResult> {
        if arguments != json!({}) {
            return deny("canary marker accepts no arguments");
        }
        let handoff = context
            .take_guard_handoff(CANARY_TOOL_NAME)
            .filter(|handoff| handoff.len() == HANDOFF_BYTES)
            .ok_or_else(|| invalid("fresh-only guard handoff is absent"))?;
        let token: Commitment = handoff[..32]
            .try_into()
            .map_err(|_| invalid("invalid token handoff"))?;
        let scope: Commitment = handoff[32..64]
            .try_into()
            .map_err(|_| invalid("invalid scope handoff"))?;
        let receipt: Commitment = handoff[64..]
            .try_into()
            .map_err(|_| invalid("invalid receipt handoff"))?;
        let marker_name = format!("{}.json", hex_lower(&token));
        let payload = serde_json::to_vec(&json!({
            "schema": "agent_bridge.invocation_guardian_canary_marker.v1",
            "token_commitment": hex_lower(&token),
            "exact_scope_commitment": hex_lower(&scope),
            "provider_receipt_commitment": hex_lower(&receipt),
            "witness_class": "in_process_fake_source_canary",
            "production_authority": false
        }))?;
        write_marker(&self.root, &marker_name, &payload)?;
        Ok(ToolResult::structured_json(&json!({
            "created": true,
            "marker_name": marker_name,
            "production_authority": false
        })))
    }
}

pub fn build_canary_registry(config: CanarySourceConfig) -> Result<FinalizedToolRegistry> {
    validate_marker_root(&config.marker_root)?;
    let root = config.marker_root.clone();
    let guard = Arc::new(CanaryGuard {
        config: config.clone(),
    });
    let mut builder = ToolRegistryBuilder::new();
    if config.enabled {
        builder.register(Box::new(CanaryMarkerTool { root }));
    }
    Ok(builder.finalize_with(|descriptors| {
        RegistryFinalization::new(
            guard,
            json!({
                "schema": "agent_bridge.invocation_guardian_canary_security_projection.v1",
                "default_off": true,
                "registered_tools": descriptors.iter().map(|descriptor| descriptor.schema.name.as_str()).collect::<Vec<_>>(),
                "global_effect_coverage": false,
                "task_identity_attested": false,
                "deployment_isolation_attested": false,
                "protected_witness_attested": false,
                "production_global_enforce": false
            }),
        )
    }))
}

pub fn canary_authorization_meta(lease: &SignedCanaryLease) -> Result<Value> {
    Ok(json!({
        CANARY_META_KEY: {
            "scope": STANDARD_NO_PAD.encode(lease.scope.canonical_bytes().map_err(|error| invalid(&error.to_string()))?),
            "signature": STANDARD_NO_PAD.encode(lease.signature)
        }
    }))
}

pub fn arguments_jcs_sha256(arguments: &Value) -> Result<Commitment> {
    let canonical = serde_json_canonicalizer::to_vec(arguments)
        .map_err(|_| invalid("arguments cannot be canonicalized"))?;
    Ok(Sha256::digest(canonical).into())
}

pub fn canary_target_sha256() -> Commitment {
    domain_hash(TARGET_DOMAIN, TARGET_VALUE)
}

fn parse_authorization_meta(meta: Option<&Value>) -> Result<SignedCanaryLease> {
    let envelope = meta
        .and_then(|meta| meta.get(CANARY_META_KEY))
        .and_then(Value::as_object)
        .ok_or_else(|| invalid("missing canary authorization envelope"))?;
    if envelope.len() != 2 {
        return deny("unknown canary authorization fields");
    }
    let scope_bytes = envelope
        .get("scope")
        .and_then(Value::as_str)
        .ok_or_else(|| invalid("missing scope"))
        .and_then(|value| {
            STANDARD_NO_PAD
                .decode(value)
                .map_err(|_| invalid("invalid scope encoding"))
        })?;
    let signature_bytes = envelope
        .get("signature")
        .and_then(Value::as_str)
        .ok_or_else(|| invalid("missing signature"))
        .and_then(|value| {
            STANDARD_NO_PAD
                .decode(value)
                .map_err(|_| invalid("invalid signature encoding"))
        })?;
    Ok(SignedCanaryLease {
        scope: crate::invocation_lease_scope::CanaryLeaseScope::decode_canonical(&scope_bytes)
            .map_err(|error| invalid(&error.to_string()))?,
        signature: signature_bytes
            .try_into()
            .map_err(|_| invalid("signature has the wrong length"))?,
    })
}

fn verify_receipt(
    receipt: &FakeProviderReceipt,
    config: &CanarySourceConfig,
    token: &Commitment,
    scope: &Commitment,
    challenge: &Commitment,
) -> Result<()> {
    if receipt.namespace != config.trust_pins.namespace
        || receipt.provider_key_generation != config.provider_key_generation
        || &receipt.token_commitment != token
        || &receipt.exact_scope_commitment != scope
        || &receipt.request_challenge != challenge
        || receipt.revision == 0
        || receipt.new_head.iter().all(|byte| *byte == 0)
    {
        return deny("provider receipt binding mismatch");
    }
    UnparsedPublicKey::new(&ED25519, config.provider_signing_key.public_key().as_ref())
        .verify(&receipt_message(receipt), &receipt.signature)
        .map_err(|_| invalid("provider receipt signature is invalid"))
}

fn receipt_message(receipt: &FakeProviderReceipt) -> Vec<u8> {
    let mut message = Vec::with_capacity(256);
    message.extend_from_slice(RECEIPT_DOMAIN);
    push_field(&mut message, receipt.namespace.as_bytes());
    message.extend_from_slice(&receipt.revision.to_be_bytes());
    message.extend_from_slice(&receipt.previous_head);
    message.extend_from_slice(&receipt.new_head);
    message.extend_from_slice(&receipt.token_commitment);
    message.extend_from_slice(&receipt.exact_scope_commitment);
    message.extend_from_slice(&receipt.request_challenge);
    message.extend_from_slice(&receipt.provider_key_generation.to_be_bytes());
    message
}

fn next_head(
    namespace: &str,
    revision: u64,
    previous: &Commitment,
    token: &Commitment,
    scope: &Commitment,
) -> Commitment {
    let mut digest = Sha256::new();
    digest.update(b"agent_bridge.invocation_guardian.fake_head.v2\0");
    digest.update(namespace.as_bytes());
    digest.update(revision.to_be_bytes());
    digest.update(previous);
    digest.update(token);
    digest.update(scope);
    digest.finalize().into()
}

fn push_field(output: &mut Vec<u8>, value: &[u8]) {
    output.extend_from_slice(&(value.len() as u32).to_be_bytes());
    output.extend_from_slice(value);
}

fn validate_marker_root(root: &Path) -> Result<()> {
    if !root.is_absolute() {
        return deny("marker root must be absolute");
    }
    let metadata = std::fs::symlink_metadata(root)?;
    if !metadata.is_dir()
        || metadata.file_type().is_symlink()
        || metadata.uid() != unsafe { libc::geteuid() }
        || metadata.permissions().mode() & 0o777 != 0o700
        || std::fs::canonicalize(root)? != root
    {
        return deny("marker root identity or mode is unsafe");
    }
    Ok(())
}

fn write_marker(root: &Path, name: &str, payload: &[u8]) -> Result<()> {
    validate_marker_root(root)?;
    if name.contains('/') || !name.ends_with(".json") {
        return deny("marker name is invalid");
    }
    let directory_fd = unsafe {
        libc::open(
            std::ffi::CString::new(root.as_os_str().as_encoded_bytes())
                .map_err(|_| invalid("marker root contains NUL"))?
                .as_ptr(),
            libc::O_RDONLY | libc::O_DIRECTORY | libc::O_NOFOLLOW | libc::O_CLOEXEC,
        )
    };
    if directory_fd < 0 {
        return Err(std::io::Error::last_os_error().into());
    }
    let directory = unsafe { File::from_raw_fd(directory_fd) };
    let name = std::ffi::CString::new(name).map_err(|_| invalid("marker name contains NUL"))?;
    let marker_fd = unsafe {
        libc::openat(
            directory.as_raw_fd(),
            name.as_ptr(),
            libc::O_WRONLY | libc::O_CREAT | libc::O_EXCL | libc::O_NOFOLLOW | libc::O_CLOEXEC,
            0o600,
        )
    };
    if marker_fd < 0 {
        return Err(std::io::Error::last_os_error().into());
    }
    let mut marker = unsafe { File::from_raw_fd(marker_fd) };
    marker.write_all(payload)?;
    marker.write_all(b"\n")?;
    marker.sync_all()?;
    directory.sync_all()?;
    Ok(())
}

fn unix_now() -> Result<i64> {
    Ok(SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map_err(|_| invalid("clock precedes Unix epoch"))?
        .as_secs()
        .try_into()
        .map_err(|_| invalid("clock is out of range"))?)
}

fn random_nonzero() -> Result<Commitment> {
    let mut value = [0; 32];
    SystemRandom::new()
        .fill(&mut value)
        .map_err(|_| invalid("secure challenge generation failed"))?;
    if value.iter().all(|byte| *byte == 0) {
        return deny("secure challenge generation returned zero");
    }
    Ok(value)
}

fn decode_hex_32(value: &str) -> Result<Commitment> {
    if value.len() != 64 {
        return deny("digest is not 32-byte lowercase hex");
    }
    let mut output = [0; 32];
    for (index, pair) in value.as_bytes().chunks_exact(2).enumerate() {
        output[index] = (hex_nibble(pair[0])? << 4) | hex_nibble(pair[1])?;
    }
    Ok(output)
}

fn hex_nibble(value: u8) -> Result<u8> {
    match value {
        b'0'..=b'9' => Ok(value - b'0'),
        b'a'..=b'f' => Ok(value - b'a' + 10),
        _ => deny("digest is not lowercase hex"),
    }
}

fn hex_lower(value: &[u8]) -> String {
    const HEX: &[u8; 16] = b"0123456789abcdef";
    let mut output = String::with_capacity(value.len() * 2);
    for byte in value {
        output.push(HEX[(byte >> 4) as usize] as char);
        output.push(HEX[(byte & 0xf) as usize] as char);
    }
    output
}

fn invalid(message: &str) -> Error {
    Error::InvalidArgument(message.to_string())
}

fn deny<T>(message: &str) -> Result<T> {
    Err(invalid(message))
}

#[cfg(test)]
mod tests {
    use super::*;
    use ring::signature::Ed25519KeyPair;

    fn key() -> Arc<Ed25519KeyPair> {
        let document = Ed25519KeyPair::generate_pkcs8(&SystemRandom::new()).unwrap();
        Arc::new(Ed25519KeyPair::from_pkcs8(document.as_ref()).unwrap())
    }

    fn request(token: u8) -> FakeWitnessRequest {
        FakeWitnessRequest {
            namespace: "canary/test".into(),
            token_commitment: [token; 32],
            exact_scope_commitment: [4; 32],
            request_challenge: [5; 32],
        }
    }

    #[tokio::test]
    async fn fake_witness_returns_fresh_once_and_audit_only_afterward() {
        let witness = FakeProtectedWitness::new("canary/test".into(), 1, key());
        assert!(matches!(
            witness.consume_once(request(3)).await,
            FakeWitnessDecision::FreshCommitted(_)
        ));
        assert!(matches!(
            witness.consume_once(request(3)).await,
            FakeWitnessDecision::AlreadyCommitted(_)
        ));
        assert_eq!(witness.committed_count(), 1);
    }

    #[tokio::test]
    async fn response_loss_burns_grant_and_replay_never_becomes_fresh() {
        let witness = FakeProtectedWitness::new("canary/test".into(), 1, key());
        witness.inject_once(FakeWitnessFault::AfterCommitResponseLost);
        assert_eq!(
            witness.consume_once(request(3)).await,
            FakeWitnessDecision::Indeterminate
        );
        assert!(matches!(
            witness.consume_once(request(3)).await,
            FakeWitnessDecision::AlreadyCommitted(_)
        ));
        assert_eq!(witness.committed_count(), 1);
    }

    #[tokio::test]
    async fn precommit_indeterminate_does_not_fabricate_consumption() {
        let witness = FakeProtectedWitness::new("canary/test".into(), 1, key());
        witness.inject_once(FakeWitnessFault::BeforeCommitIndeterminate);
        assert_eq!(
            witness.consume_once(request(3)).await,
            FakeWitnessDecision::Indeterminate
        );
        assert_eq!(witness.committed_count(), 0);
        assert!(matches!(
            witness.consume_once(request(3)).await,
            FakeWitnessDecision::FreshCommitted(_)
        ));
    }

    #[tokio::test(flavor = "multi_thread", worker_threads = 4)]
    async fn concurrent_consumption_has_exactly_one_fresh_decision() {
        let witness = Arc::new(FakeProtectedWitness::new("canary/test".into(), 1, key()));
        let mut tasks = Vec::new();
        for _ in 0..32 {
            let witness = witness.clone();
            tasks.push(tokio::spawn(async move {
                witness.consume_once(request(3)).await
            }));
        }
        let mut fresh = 0;
        let mut already = 0;
        for task in tasks {
            match task.await.unwrap() {
                FakeWitnessDecision::FreshCommitted(_) => fresh += 1,
                FakeWitnessDecision::AlreadyCommitted(_) => already += 1,
                other => panic!("unexpected decision: {other:?}"),
            }
        }
        assert_eq!(fresh, 1);
        assert_eq!(already, 31);
        assert_eq!(witness.committed_count(), 1);
    }
}
