//! Evaluation-only, exact-call authority for effectful Agent-Bridge invocations.
//!
//! This layer is deliberately separate from [`crate::agent_spawn_governor`].
//! The governor limits resources; a consumed invocation lease grants authority
//! for one exact effectful call.  A lease binds the registry-owned surface
//! name, RFC 8785/JCS arguments digest, normalized target digest, a short time
//! window, a bounded use count, and (where the transport can prove one) a
//! principal commitment.
//!
//! The verifier and issuer are separate types. [`InvocationLeaseAuthorizer`]
//! is stored in [`crate::hub::Hub`]; it cannot mint leases. A trusted host must
//! retain [`InvocationLeaseIssuer`] outside the Hub. No MCP/RPC self-issuance
//! surface is provided.
//!
//! Tokens contain a random nonce and an Ed25519 signature over that nonce and
//! the complete stored scope. The authorizer retains only the pinned public
//! verification key; the issuer retains the private signing capability. Thus,
//! writing an arbitrary lease row is not enough to create authority.
//!
//! Consumption is committed to an insert-only SQLite sidecar before the
//! underlying tool runs. This is useful for shadow evaluation and unit tests,
//! but it is **not** a production anti-replay boundary: another process under
//! the same UID can snapshot/restore the database, or drop/delete/recreate it.
//! Pathname device/inode checks, generation, public-key, and exact DDL pins
//! detect ordinary replacement and drift while the verifier is alive. They do
//! not fstat SQLite's opened file descriptor and cannot defeat a pathname-swap
//! race or that same-UID rollback class. Production `enforce` therefore maps
//! to Invalid/HOLD until an independently privileged guardian supplies
//! protected monotonic consumption state. Invalid/HOLD default-denies calls at
//! the wired MCP/Unix guards except explicit diagnostics and recovery controls;
//! unconnected effect surfaces mean this is not global fail-closed. Shadow
//! mode never consumes and never blocks. The default is off.

use ab_mcp::{McpTransportKind, ToolCallGuard, ToolContext};
use async_trait::async_trait;
use base64::{engine::general_purpose::URL_SAFE_NO_PAD, Engine as _};
use ring::rand::{SecureRandom, SystemRandom};
use ring::signature::{Ed25519KeyPair, KeyPair as _, UnparsedPublicKey, ED25519};
use serde::Serialize;
use serde_json::{json, Value};
use sha2::{Digest, Sha256};
use std::collections::BTreeSet;
use std::fmt;
use std::path::{Path, PathBuf};
use std::sync::atomic::{AtomicU64, Ordering};
use std::sync::Arc;
use std::time::{Duration, SystemTime, UNIX_EPOCH};
use tokio_rusqlite::rusqlite::{
    self, params, Connection, OpenFlags, OptionalExtension, TransactionBehavior,
};

use crate::security::{Cap, SecurityPolicy};

const APPLICATION_ID: i64 = 0x4142_494c; // "ABIL"
const USER_VERSION: i64 = 4;
const BUSY_TIMEOUT: Duration = Duration::from_millis(1_500);
const MAX_ARGUMENT_BYTES: usize = 1024 * 1024;
pub const MAX_INVOCATION_LEASE_TTL_SECS: u64 = 300;
pub const MAX_INVOCATION_LEASE_USES: u32 = 64;

pub const LEASE_REF_SCHEMA: &str = "agent_bridge.effectful_call_lease_ref.v3";
pub const LEASE_META_KEY: &str = ab_mcp::EFFECTFUL_CALL_LEASE_META_KEY;
const TOKEN_PREFIX: &str = "ecl3_";
const MCP_STDIO_CONNECTION_CONTEXT_KIND: &str = "mcp_stdio_connection_v1";
const TOKEN_NONCE_BYTES: usize = 32;
const TOKEN_SIGNATURE_BYTES: usize = 64;
const TOKEN_BYTES: usize = TOKEN_NONCE_BYTES + TOKEN_SIGNATURE_BYTES;

const META_TABLE: &str = "invocation_lease_meta_v0";
const LEASE_TABLE: &str = "invocation_leases_v0";
const CONSUMPTION_TABLE: &str = "invocation_lease_consumptions_v0";
const REVOCATION_TABLE: &str = "invocation_lease_revocations_v0";

const SCHEMA_SQL: &str = r#"
CREATE TABLE invocation_lease_meta_v0 (
    singleton INTEGER NOT NULL PRIMARY KEY CHECK (singleton = 1),
    generation_id BLOB NOT NULL
        CHECK (typeof(generation_id) = 'blob' AND length(generation_id) = 32),
    verify_public_key BLOB NOT NULL
        CHECK (typeof(verify_public_key) = 'blob' AND length(verify_public_key) = 32)
) STRICT, WITHOUT ROWID;

CREATE TABLE invocation_leases_v0 (
    token_commitment BLOB NOT NULL PRIMARY KEY
        CHECK (typeof(token_commitment) = 'blob' AND length(token_commitment) = 32),
    issuance_mode TEXT NOT NULL CHECK (issuance_mode IN ('shadow', 'enforce')),
    lease_id TEXT NOT NULL UNIQUE CHECK (length(lease_id) BETWEEN 1 AND 96),
    tool_name TEXT NOT NULL CHECK (length(tool_name) BETWEEN 1 AND 128),
    arguments_sha256 BLOB NOT NULL
        CHECK (typeof(arguments_sha256) = 'blob' AND length(arguments_sha256) = 32),
    target_sha256 BLOB NOT NULL
        CHECK (typeof(target_sha256) = 'blob' AND length(target_sha256) = 32),
    principal_kind TEXT NOT NULL
        CHECK (principal_kind IN ('bearer', 'oauth', 'unix_uid')),
    principal_commitment BLOB
        CHECK (principal_commitment IS NULL OR
               (typeof(principal_commitment) = 'blob' AND length(principal_commitment) = 32)),
    execution_context_kind TEXT
        CHECK (execution_context_kind IS NULL OR
               execution_context_kind = 'mcp_stdio_connection_v1'),
    execution_context_commitment BLOB
        CHECK (execution_context_commitment IS NULL OR
               (typeof(execution_context_commitment) = 'blob' AND
                length(execution_context_commitment) = 32)),
    issued_at_unix INTEGER NOT NULL CHECK (issued_at_unix >= 0),
    not_before_unix INTEGER NOT NULL CHECK (not_before_unix >= issued_at_unix),
    expires_at_unix INTEGER NOT NULL CHECK (expires_at_unix > not_before_unix),
    max_uses INTEGER NOT NULL CHECK (max_uses BETWEEN 1 AND 64),
    CHECK (expires_at_unix - not_before_unix BETWEEN 1 AND 300),
    CHECK ((principal_kind = 'bearer' AND principal_commitment IS NULL) OR
           (principal_kind != 'bearer' AND principal_commitment IS NOT NULL)),
    CHECK ((execution_context_kind IS NULL AND execution_context_commitment IS NULL) OR
           (execution_context_kind = 'mcp_stdio_connection_v1' AND
            execution_context_commitment IS NOT NULL))
) STRICT, WITHOUT ROWID;

CREATE TABLE invocation_lease_consumptions_v0 (
    token_commitment BLOB NOT NULL
        CHECK (typeof(token_commitment) = 'blob' AND length(token_commitment) = 32),
    use_index INTEGER NOT NULL CHECK (use_index BETWEEN 1 AND 64),
    scope_sha256 BLOB NOT NULL
        CHECK (typeof(scope_sha256) = 'blob' AND length(scope_sha256) = 32),
    call_id TEXT NOT NULL UNIQUE CHECK (length(call_id) BETWEEN 1 AND 96),
    consumed_at_unix INTEGER NOT NULL CHECK (consumed_at_unix >= 0),
    PRIMARY KEY (token_commitment, use_index),
    FOREIGN KEY (token_commitment) REFERENCES invocation_leases_v0(token_commitment)
) STRICT, WITHOUT ROWID;

CREATE TABLE invocation_lease_revocations_v0 (
    token_commitment BLOB NOT NULL PRIMARY KEY
        CHECK (typeof(token_commitment) = 'blob' AND length(token_commitment) = 32),
    reason_sha256 BLOB NOT NULL
        CHECK (typeof(reason_sha256) = 'blob' AND length(reason_sha256) = 32),
    revoked_at_unix INTEGER NOT NULL CHECK (revoked_at_unix >= 0),
    FOREIGN KEY (token_commitment) REFERENCES invocation_leases_v0(token_commitment)
) STRICT, WITHOUT ROWID;

CREATE TRIGGER invocation_lease_meta_v0_no_insert
BEFORE INSERT ON invocation_lease_meta_v0
WHEN EXISTS (SELECT 1 FROM invocation_lease_meta_v0)
BEGIN SELECT RAISE(ABORT, 'invocation lease generation is immutable'); END;
CREATE TRIGGER invocation_lease_meta_v0_no_update
BEFORE UPDATE ON invocation_lease_meta_v0
BEGIN SELECT RAISE(ABORT, 'invocation lease generation is immutable'); END;
CREATE TRIGGER invocation_lease_meta_v0_no_delete
BEFORE DELETE ON invocation_lease_meta_v0
BEGIN SELECT RAISE(ABORT, 'invocation lease generation is permanent'); END;

CREATE TRIGGER invocation_leases_v0_no_update
BEFORE UPDATE ON invocation_leases_v0
BEGIN SELECT RAISE(ABORT, 'invocation leases are immutable'); END;
CREATE TRIGGER invocation_leases_v0_no_delete
BEFORE DELETE ON invocation_leases_v0
BEGIN SELECT RAISE(ABORT, 'invocation leases are permanent'); END;

CREATE TRIGGER invocation_lease_consumptions_v0_no_update
BEFORE UPDATE ON invocation_lease_consumptions_v0
BEGIN SELECT RAISE(ABORT, 'invocation lease consumptions are immutable'); END;
CREATE TRIGGER invocation_lease_consumptions_v0_no_delete
BEFORE DELETE ON invocation_lease_consumptions_v0
BEGIN SELECT RAISE(ABORT, 'invocation lease consumptions are permanent'); END;

CREATE TRIGGER invocation_lease_revocations_v0_no_update
BEFORE UPDATE ON invocation_lease_revocations_v0
BEGIN SELECT RAISE(ABORT, 'invocation lease revocations are immutable'); END;
CREATE TRIGGER invocation_lease_revocations_v0_no_delete
BEFORE DELETE ON invocation_lease_revocations_v0
BEGIN SELECT RAISE(ABORT, 'invocation lease revocations are permanent'); END;
"#;

const EXPECTED_OBJECTS: &[(&str, &str)] = &[
    ("table", CONSUMPTION_TABLE),
    ("table", LEASE_TABLE),
    ("table", META_TABLE),
    ("table", REVOCATION_TABLE),
    ("trigger", "invocation_lease_consumptions_v0_no_delete"),
    ("trigger", "invocation_lease_consumptions_v0_no_update"),
    ("trigger", "invocation_lease_meta_v0_no_delete"),
    ("trigger", "invocation_lease_meta_v0_no_insert"),
    ("trigger", "invocation_lease_meta_v0_no_update"),
    ("trigger", "invocation_lease_revocations_v0_no_delete"),
    ("trigger", "invocation_lease_revocations_v0_no_update"),
    ("trigger", "invocation_leases_v0_no_delete"),
    ("trigger", "invocation_leases_v0_no_update"),
];

/// Initial high-risk surface. This provisional static set intentionally omits
/// `agent_kill` and `mobile_projection_stop` as a cross-task emergency
/// availability tradeoff; Bridge visibility of their targets is not
/// caller/task custody. The finalized inventory guard still requires exact
/// authority for them, while Invalid/HOLD has a separate explicit carveout.
/// Namespace-only remote targets and caller-selected external ids remain
/// protected until custody is provable.
pub const DEFAULT_PROTECTED_TOOLS: &[&str] = &[
    // Arbitrary/local command and terminal injection.
    "shell_exec",
    "system_control",
    "terminal_send_keys",
    "terminal_split",
    "terminal_resize",
    // Agent creation and command injection. agent_kill remains outside this
    // provisional static list as a cross-task emergency availability tradeoff;
    // resolving it through the Bridge store/live map does not prove caller
    // ownership. The finalized inventory guard does not inherit this omission.
    "agent_spawn",
    "agent_send_input",
    "agent_steer_launch",
    "agent_steer_drive",
    "agent_steer_kill",
    // Files, worktrees, and host application workflows.
    "worktree_create",
    "worktree_remove",
    "ide_command",
    "app_control",
    "macos_ax_focus_transaction",
    "warp_launch_workflow",
    "warp_open_settings",
    "warp_open_tab",
    "warp_open_window",
    // Desktop admission and confirmation form one authority chain. In
    // particular, desktop_confirm can consume a host-mutation grant returned
    // by desktop_invoke, so none of the three may sit outside the guard.
    "desktop_action",
    "desktop_invoke",
    "desktop_confirm",
    // Browser surfaces that can execute code, submit data, or change remote state.
    "browser_navigate",
    "browser_eval",
    "browser_click",
    "browser_fill_form",
    "browser_press_key",
    "browser_select_option",
    "browser_eval_in_frame",
    "browser_reload",
    "browser_back",
    "browser_forward",
    "browser_scroll",
    "browser_upload_file",
    "browser_set_emulation",
    "browser_hover",
    // Nominally observational browser calls can still write caller-selected
    // host paths and therefore remain effects at this boundary.
    "browser_screenshot",
    "browser_screenshot_element",
    // The CDP tracker may import pre-existing or popup tabs; a PageId proves
    // reachability, not that AB created the tab.
    "browser_close_page",
    "modelscope_abot_run_once",
    // Device control. Stop/cancel recovery tools remain open.
    "mobile_install_apk",
    "mobile_launch_app",
    "mobile_click",
    "mobile_input_text",
    "mobile_projection_start",
    "mobile_projection_update",
    "mobile_projection_sync_media",
    "mobile_projection_follow_media",
    "advance_track_then_project",
    // External/durable writes.
    "notify",
    "osc_parse",
    "forum_post",
    "forum_set_thread_status",
    "agent_message",
    "world_patch",
    "tailscale_acl_set",
    "github_issue_create",
    "gitlab_issue_create",
    "notion_page_create",
    // Raw Warp run ids are caller-selected external authority; this cancel
    // surface remains protected until it requires a Bridge-custodied session.
    "oz_run_cancel",
    // Durable local knowledge mutation can steer later tasks even when it has
    // no immediate external-world effect.
    "memory_save",
    "memory_delete",
    // Legacy Unix JSON-RPC aliases.
    "notify.send",
    "terminal.send_keys",
    "terminal.split",
    "browser.navigate",
    "browser.eval",
    "browser.click",
    "browser.screenshot",
    // Despite its name, this legacy method delivers OscEvent::Notify.
    "osc.parse",
];

/// Controls and diagnostics that remain reachable when production `enforce`
/// is requested while the rollout is on HOLD. Invalid/HOLD mode otherwise
/// default-denies every call that reaches a wired MCP or Unix guard, including
/// names missing from the provisional effect inventory.
pub const HOLD_OPEN_TOOLS: &[&str] = &[
    "capabilities",
    "system.ping",
    "system.capabilities",
    "agent_kill",
    "mobile_projection_stop",
];

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum InvocationLeaseMode {
    Off,
    Shadow,
    Enforce,
    Invalid,
}

impl InvocationLeaseMode {
    pub const fn as_str(self) -> &'static str {
        match self {
            Self::Off => "off",
            Self::Shadow => "shadow",
            Self::Enforce => "enforce",
            Self::Invalid => "invalid",
        }
    }
}

fn production_runtime_mode(
    requested: InvocationLeaseMode,
) -> (InvocationLeaseMode, Option<String>) {
    match requested {
        InvocationLeaseMode::Enforce => (
            InvocationLeaseMode::Invalid,
            Some(
                "HOLD: production enforce requires an independent-UID guardian with protected monotonic anti-replay state"
                    .into(),
            ),
        ),
        InvocationLeaseMode::Invalid => (
            InvocationLeaseMode::Invalid,
            Some("AB_INVOCATION_LEASE_MODE is invalid".into()),
        ),
        mode => (mode, None),
    }
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize)]
#[serde(tag = "kind", rename_all = "snake_case")]
pub enum LeasePrincipal {
    /// Stdio has no authenticated user identity. Possession of the opaque token
    /// is the authority; caller-provided session metadata is never consulted.
    Bearer,
    OAuth {
        issuer: String,
        local_subject: String,
    },
    UnixUid {
        uid: u32,
    },
}

/// Closed, transport-attested execution context that an exact invocation
/// lease may bind. This is intentionally not a task identity: the current MCP
/// variant proves only one server-created stdio connection/process instance.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum LeaseExecutionContext {
    McpStdioConnection([u8; 32]),
}

impl LeaseExecutionContext {
    /// Construct the current MCP connection context from the commitment
    /// advertised by the server. The accepted representation is exactly 32
    /// bytes encoded as 64 ASCII hexadecimal characters.
    pub fn mcp_stdio_connection_from_hex(
        commitment_hex: &str,
    ) -> Result<Self, InvocationLeaseError> {
        decode_hex_32_named(
            commitment_hex,
            "invalid_execution_context",
            "MCP stdio connection commitment",
        )
        .map(Self::McpStdioConnection)
    }

    pub const fn kind(&self) -> &'static str {
        match self {
            Self::McpStdioConnection(_) => MCP_STDIO_CONNECTION_CONTEXT_KIND,
        }
    }

    pub const fn commitment(&self) -> &[u8; 32] {
        match self {
            Self::McpStdioConnection(commitment) => commitment,
        }
    }

    pub fn commitment_hex(&self) -> String {
        hex(self.commitment())
    }
}

#[derive(Debug, thiserror::Error)]
#[error("AB_INVOCATION_LEASE_DENIED code={code}: {detail}")]
pub struct InvocationLeaseError {
    code: &'static str,
    detail: String,
}

impl InvocationLeaseError {
    fn new(code: &'static str, detail: impl Into<String>) -> Self {
        Self {
            code,
            detail: detail.into(),
        }
    }

    pub const fn code(&self) -> &'static str {
        self.code
    }
}

type LeaseResult<T> = std::result::Result<T, InvocationLeaseError>;

/// Secret bearer returned exactly once to the trusted issuer.
pub struct InvocationLeaseToken(String);

impl InvocationLeaseToken {
    pub fn expose_to_trusted_host(&self) -> &str {
        &self.0
    }
}

impl fmt::Debug for InvocationLeaseToken {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        formatter.write_str("InvocationLeaseToken([REDACTED])")
    }
}

#[derive(Clone)]
struct ParsedLeaseToken {
    nonce: [u8; TOKEN_NONCE_BYTES],
    signature: [u8; TOKEN_SIGNATURE_BYTES],
}

#[derive(Debug, Clone, Serialize)]
pub struct InvocationLeaseReceipt {
    pub schema_version: &'static str,
    pub issuance_mode: &'static str,
    pub lease_id: String,
    pub tool_name: String,
    pub target: String,
    pub arguments_sha256: String,
    pub target_sha256: String,
    pub principal_kind: String,
    pub principal_commitment: Option<String>,
    pub execution_context_kind: Option<String>,
    pub execution_context_commitment: Option<String>,
    /// True only when this lease is signed for a server-attested execution
    /// context and verification requires that exact context.
    pub execution_context_binding_enforced: bool,
    pub issued_at_unix: i64,
    pub not_before_unix: i64,
    pub expires_at_unix: i64,
    pub max_uses: u32,
    pub grants_authority: bool,
    /// The current principal scopes do not include a transport-attested task
    /// identity. This is false until such an identity is part of the signature.
    pub task_binding_enforced: bool,
    /// A holder can currently transfer a token to another process acting as
    /// the same bearer/UID/OAuth principal. This remains false until custody is
    /// enforced by the independent guardian.
    pub same_principal_token_transfer_blocked: bool,
}

pub struct IssuedInvocationLease {
    pub receipt: InvocationLeaseReceipt,
    token: InvocationLeaseToken,
}

impl fmt::Debug for IssuedInvocationLease {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        formatter
            .debug_struct("IssuedInvocationLease")
            .field("receipt", &self.receipt)
            .field("token", &"[REDACTED]")
            .finish()
    }
}

impl IssuedInvocationLease {
    pub fn token(&self) -> &InvocationLeaseToken {
        &self.token
    }

    /// Value to place at `tools/call.params._meta` (or the legacy RPC
    /// `params._meta`). It is intentionally separate from tool arguments.
    pub fn authorization_meta(&self) -> Value {
        json!({
            LEASE_META_KEY: {
                "schema": LEASE_REF_SCHEMA,
                "token": self.token.0,
            }
        })
    }
}

#[derive(Clone)]
struct LedgerIdentity {
    path: PathBuf,
    canonical_path: PathBuf,
    generation_id: [u8; 32],
    verify_public_key: [u8; 32],
    #[cfg(unix)]
    device: u64,
    #[cfg(unix)]
    inode: u64,
}

impl fmt::Debug for LedgerIdentity {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        formatter
            .debug_struct("LedgerIdentity")
            .field("path", &"[PINNED]")
            .field("generation", &"[PINNED]")
            .field("verify_public_key", &"[PINNED]")
            .field("file_identity", &"[PINNED]")
            .finish()
    }
}

struct AuthorizerInner {
    mode: InvocationLeaseMode,
    ledger: Option<Arc<LedgerIdentity>>,
    protected_tools: Arc<BTreeSet<String>>,
    config_error: Option<String>,
    checked: AtomicU64,
    allowed: AtomicU64,
    denied: AtomicU64,
    shadow_would_allow: AtomicU64,
    shadow_would_deny: AtomicU64,
}

/// Verification/consumption capability stored in Hub. It has no issue method.
#[derive(Clone)]
pub struct InvocationLeaseAuthorizer {
    inner: Arc<AuthorizerInner>,
}

/// Trusted host capability. This type is deliberately not stored in Hub.
#[derive(Clone)]
pub struct InvocationLeaseIssuer {
    ledger: Arc<LedgerIdentity>,
    protected_tools: Arc<BTreeSet<String>>,
    signing_key: Arc<Ed25519KeyPair>,
    mode: InvocationLeaseMode,
}

pub struct ProvisionedInvocationLeaseAuthority {
    pub authorizer: InvocationLeaseAuthorizer,
    pub issuer: InvocationLeaseIssuer,
    pub generation_hex: String,
    pub verify_key_hex: String,
}

#[derive(Clone)]
pub struct InvocationLeaseMcpGuard {
    authorizer: InvocationLeaseAuthorizer,
    security: SecurityPolicy,
    /// When present, this is a closed, independently reviewed allowlist. It is
    /// never inferred from tool annotations or inventory classifications.
    /// Every MCP name outside it requires a lease, including names absent from
    /// the provisional static protected set.
    lease_exempt_tools: Option<Arc<BTreeSet<String>>>,
    inventory_digest: Option<Arc<str>>,
    require_execution_context_binding: bool,
}

#[derive(Clone)]
struct LeaseRow {
    token_commitment: [u8; 32],
    issuance_mode: String,
    lease_id: String,
    tool_name: String,
    arguments_sha256: [u8; 32],
    target_sha256: [u8; 32],
    principal_kind: String,
    principal_commitment: Option<[u8; 32]>,
    execution_context_kind: Option<String>,
    execution_context_commitment: Option<[u8; 32]>,
    issued_at_unix: i64,
    not_before_unix: i64,
    expires_at_unix: i64,
    max_uses: u32,
}

#[derive(Clone)]
struct EvaluationRequest {
    token_commitment: [u8; 32],
    token_nonce: [u8; TOKEN_NONCE_BYTES],
    token_signature: [u8; TOKEN_SIGNATURE_BYTES],
    tool_name: String,
    arguments_sha256: [u8; 32],
    target_sha256: [u8; 32],
    observed_principal: Option<(String, [u8; 32])>,
    observed_execution_context: Option<LeaseExecutionContext>,
    require_execution_context_binding: bool,
    required_principal_kind: &'static str,
    required_issuance_mode: &'static str,
    now_unix: i64,
    call_id: String,
    consume: bool,
    #[cfg(test)]
    linearized_now_override: Option<i64>,
}

impl InvocationLeaseAuthorizer {
    pub fn off() -> Self {
        Self::new(
            InvocationLeaseMode::Off,
            None,
            default_protected_tools(),
            None,
        )
    }

    fn new(
        mode: InvocationLeaseMode,
        ledger: Option<Arc<LedgerIdentity>>,
        protected_tools: BTreeSet<String>,
        config_error: Option<String>,
    ) -> Self {
        Self {
            inner: Arc::new(AuthorizerInner {
                mode,
                ledger,
                protected_tools: Arc::new(protected_tools),
                config_error,
                checked: AtomicU64::new(0),
                allowed: AtomicU64::new(0),
                denied: AtomicU64::new(0),
                shadow_would_allow: AtomicU64::new(0),
                shadow_would_deny: AtomicU64::new(0),
            }),
        }
    }

    /// Load only verification material. Environment configuration never
    /// exposes an issuer and cannot mint a grant.
    pub fn from_env() -> Self {
        let raw_mode = match std::env::var("AB_INVOCATION_LEASE_MODE") {
            Ok(value) => Some(value),
            Err(std::env::VarError::NotPresent) => None,
            Err(std::env::VarError::NotUnicode(_)) => {
                return Self::new(
                    InvocationLeaseMode::Invalid,
                    None,
                    default_protected_tools(),
                    Some("HOLD: AB_INVOCATION_LEASE_MODE must be valid UTF-8".into()),
                );
            }
        };
        let requested_mode = match raw_mode.as_deref().map(str::trim) {
            None | Some("") | Some("off" | "0" | "false" | "no") => InvocationLeaseMode::Off,
            Some("shadow") => InvocationLeaseMode::Shadow,
            Some("enforce" | "1" | "true" | "yes" | "on") => InvocationLeaseMode::Enforce,
            Some(_) => InvocationLeaseMode::Invalid,
        };
        if requested_mode == InvocationLeaseMode::Off {
            return Self::off();
        }

        let mut protected = default_protected_tools();
        match std::env::var("AB_INVOCATION_LEASE_EXTRA_TOOLS") {
            Ok(extra) => {
                if let Err(error) = extend_protected_tools(&mut protected, &extra) {
                    return Self::new(
                        InvocationLeaseMode::Invalid,
                        None,
                        protected,
                        Some(error.to_string()),
                    );
                }
            }
            Err(std::env::VarError::NotPresent) => {}
            Err(std::env::VarError::NotUnicode(_)) => {
                return Self::new(
                    InvocationLeaseMode::Invalid,
                    None,
                    protected,
                    Some("HOLD: AB_INVOCATION_LEASE_EXTRA_TOOLS must be valid UTF-8".into()),
                );
            }
        }
        let (mode, mode_error) = production_runtime_mode(requested_mode);
        if mode == InvocationLeaseMode::Invalid {
            return Self::new(
                mode,
                None,
                protected,
                Some(mode_error.unwrap_or_else(|| "AB_INVOCATION_LEASE_MODE is invalid".into())),
            );
        }

        let path = std::env::var_os("AB_INVOCATION_LEASE_DB").map(PathBuf::from);
        let generation = std::env::var("AB_INVOCATION_LEASE_DB_GENERATION")
            .ok()
            .and_then(|value| decode_hex_32(value.trim()).ok());
        let verify_public_key = std::env::var("AB_INVOCATION_LEASE_VERIFY_KEY")
            .ok()
            .and_then(|value| decode_hex_32(value.trim()).ok());
        let ledger = match (path, generation, verify_public_key) {
            (Some(path), Some(generation), Some(verify_public_key)) => {
                pin_existing_ledger(&path, generation, verify_public_key).map(Arc::new)
            }
            _ => Err(InvocationLeaseError::new(
                "config",
                "shadow mode requires AB_INVOCATION_LEASE_DB plus 64-hex generation and verify-key pins",
            )),
        };
        match ledger {
            Ok(ledger) => Self::new(mode, Some(ledger), protected, None),
            Err(error) if mode == InvocationLeaseMode::Shadow => {
                Self::new(mode, None, protected, Some(error.to_string()))
            }
            Err(error) => Self::new(
                InvocationLeaseMode::Invalid,
                None,
                protected,
                Some(error.to_string()),
            ),
        }
    }

    pub fn mode(&self) -> InvocationLeaseMode {
        self.inner.mode
    }

    pub fn gate_enabled(&self) -> bool {
        self.inner.mode != InvocationLeaseMode::Off
    }

    pub fn requires_lease(&self, tool_name: &str) -> bool {
        if self.inner.mode == InvocationLeaseMode::Invalid {
            // A requested production enforce is deliberately unusable while
            // HOLD is active. Default-deny at every wired ingress so an
            // incomplete effect inventory cannot turn Invalid into bypass.
            return !HOLD_OPEN_TOOLS.contains(&tool_name);
        }
        self.inner.protected_tools.contains(tool_name)
    }

    pub fn mcp_guard(&self, security: SecurityPolicy) -> InvocationLeaseMcpGuard {
        InvocationLeaseMcpGuard {
            authorizer: self.clone(),
            security,
            lease_exempt_tools: None,
            inventory_digest: None,
            require_execution_context_binding: false,
        }
    }

    /// Build a conservative finalized-registry guard. The exemption set must
    /// come from an independent security review; tool annotations or an
    /// inventory classification are not authority attestations and must never
    /// populate it automatically. The current finalizer passes an empty set,
    /// so every registered name requires a lease in shadow/local-test-enforce.
    /// Invalid/HOLD deliberately ignores even a reviewed set and retains its
    /// smaller hard-coded recovery/diagnostic allowlist.
    pub(crate) fn mcp_guard_for_inventory(
        &self,
        security: SecurityPolicy,
        lease_exempt_tools: BTreeSet<String>,
        inventory_digest: impl Into<String>,
    ) -> InvocationLeaseMcpGuard {
        InvocationLeaseMcpGuard {
            authorizer: self.clone(),
            security,
            lease_exempt_tools: Some(Arc::new(lease_exempt_tools)),
            inventory_digest: Some(Arc::from(inventory_digest.into())),
            require_execution_context_binding: true,
        }
    }

    pub fn snapshot(&self) -> Value {
        json!({
            "schema_version": "agent_bridge.invocation_lease_status.v3",
            "mode": self.inner.mode.as_str(),
            // Global fail-closed would require every effect ingress plus a
            // rollback-resistant guardian. Neither claim is true yet.
            "fail_closed": false,
            "authorizer_denies_configured_protected_calls_when_invoked": matches!(self.inner.mode, InvocationLeaseMode::Enforce | InvocationLeaseMode::Invalid),
            "invalid_hold_default_deny_at_guarded_ingress": self.inner.mode == InvocationLeaseMode::Invalid,
            "invalid_hold_open_tools": HOLD_OPEN_TOOLS,
            "rollout_state": "hold",
            "enforcement_ready": false,
            "same_uid_rollback_protected": false,
            "pathname_device_inode_pinned": cfg!(unix) && self.inner.ledger.is_some(),
            "open_fd_fstat_pinned": false,
            "parent_dir_pinned": false,
            "required_enforcement_dependency": "independent_uid_guardian_with_protected_monotonic_state",
            "local_sqlite_evaluation_ledger_configured": self.inner.ledger.is_some(),
            "durable_anti_replay": false,
            "configuration_valid": self.inner.mode != InvocationLeaseMode::Invalid && self.inner.config_error.is_none(),
            "configuration_error": self.inner.config_error,
            "protected_tools": self.inner.protected_tools.iter().collect::<Vec<_>>(),
            "max_ttl_secs": MAX_INVOCATION_LEASE_TTL_SECS,
            "max_uses": MAX_INVOCATION_LEASE_USES,
            "issuer_in_hub": false,
            "self_issue_surface": false,
            "issuer_separation": {
                "capability_type_separated": true,
                "private_signing_key_in_authorizer": false,
                "independent_process_uid_in_local_evaluator": false
            },
            "signed_scope_protocol_supported": true,
            "signed_scope_evaluated_for_protected_calls": matches!(self.inner.mode, InvocationLeaseMode::Shadow | InvocationLeaseMode::Enforce),
            "signed_scope_enforced_for_protected_calls": self.inner.mode == InvocationLeaseMode::Enforce,
            "production_grants_authority": false,
            "local_cfg_test_enforce_only": true,
            "execution_context_binding_supported": true,
            "execution_context_binding": {
                "mcp_stdio": "optional_exact_server_owned_connection_instance_not_task",
                "streamable_http": "not_available",
                "unix_rpc": "not_available"
            },
            "finalized_mcp_candidate_requires_execution_context_binding": true,
            "task_inheritance": "not_enforced_connection_binding_is_not_task_identity_v0",
            "task_binding_enforced": false,
            "same_principal_token_transfer_blocked": false,
            "target_binding": {
                "normalized_target": "arguments_derived_audit_hint",
                "resolved_runtime_target": false
            },
            "principal_binding": {
                "stdio": "opaque_bearer_with_optional_exact_server_connection_binding",
                "streamable_http": "verified_oauth_subject_when_required",
                "unix_rpc": "kernel_peer_uid_required"
            },
            "coverage": {
                "status": "guard_seams_present_but_runtime_ingress_attestation_and_production_enforcement_on_hold",
                "authorizer_gate_requested": self.gate_enabled(),
                "mcp_registry_guard_seam_present": true,
                "legacy_unix_rpc_guard_seam_present": true,
                "current_process_ingress_attested": false,
                "daemon_http_write_routes": false,
                "native_client_tools": false,
                "direct_in_process_handler_calls": false
            },
            "counters": {
                "checked": self.inner.checked.load(Ordering::Relaxed),
                "allowed": self.inner.allowed.load(Ordering::Relaxed),
                "denied": self.inner.denied.load(Ordering::Relaxed),
                "shadow_would_allow": self.inner.shadow_would_allow.load(Ordering::Relaxed),
                "shadow_would_deny": self.inner.shadow_would_deny.load(Ordering::Relaxed)
            }
        })
    }

    pub async fn authorize_mcp(
        &self,
        tool_name: &str,
        arguments: &Value,
        context: &ToolContext,
    ) -> LeaseResult<()> {
        self.authorize_mcp_inner(tool_name, arguments, context, false, false)
            .await
    }

    async fn authorize_mcp_required(
        &self,
        tool_name: &str,
        arguments: &Value,
        context: &ToolContext,
        require_execution_context_binding: bool,
    ) -> LeaseResult<()> {
        self.authorize_mcp_inner(
            tool_name,
            arguments,
            context,
            true,
            require_execution_context_binding,
        )
        .await
    }

    async fn authorize_mcp_inner(
        &self,
        tool_name: &str,
        arguments: &Value,
        context: &ToolContext,
        force_required: bool,
        require_execution_context_binding: bool,
    ) -> LeaseResult<()> {
        if self.inner.mode == InvocationLeaseMode::Off
            || (!force_required && !self.requires_lease(tool_name))
        {
            return Ok(());
        }
        if self.inner.mode == InvocationLeaseMode::Invalid {
            return self
                .authorize_with_execution_context_requirement(
                    tool_name,
                    arguments,
                    context.authorization_meta(),
                    None,
                    None,
                    "unverified_transport",
                    0,
                    force_required,
                    require_execution_context_binding,
                )
                .await;
        }
        let now = match unix_now() {
            Ok(now) => now,
            Err(error) => return self.handle_preparation_error(tool_name, error),
        };
        let observed = if let Some(subject) = context.verified_oauth_subject() {
            if subject.expires_at_unix() <= now as u64 {
                None
            } else {
                match principal_material(&LeasePrincipal::OAuth {
                    issuer: subject.issuer().to_string(),
                    local_subject: subject.local_subject().to_string(),
                }) {
                    Ok((kind, commitment)) => commitment.map(|value| (kind, value)),
                    Err(error) => return self.handle_preparation_error(tool_name, error),
                }
            }
        } else {
            None
        };
        let observed_execution_context = match context.verified_execution_context() {
            Some(attested)
                if attested.kind() == MCP_STDIO_CONNECTION_CONTEXT_KIND
                    && !attested.task_identity_attested() =>
            {
                Some(LeaseExecutionContext::McpStdioConnection(
                    *attested.commitment(),
                ))
            }
            Some(_) => {
                return self.handle_preparation_error(
                    tool_name,
                    InvocationLeaseError::new(
                        "unverified_execution_context",
                        "protected MCP calls accept only the closed server-owned stdio connection context profile",
                    ),
                );
            }
            None => None,
        };
        // A stdio session id, clientInfo, args._meta, and environment-derived
        // hint never become a principal. HTTP cannot downgrade from its
        // transport-verified OAuth identity to bearer possession.
        let required_principal_kind = match context.transport_kind() {
            McpTransportKind::Stdio => "bearer",
            McpTransportKind::StreamableHttp => "oauth",
            McpTransportKind::Unknown => {
                return self.handle_preparation_error(
                    tool_name,
                    InvocationLeaseError::new(
                        "unverified_transport",
                        "protected MCP calls require a server-owned transport identity",
                    ),
                );
            }
        };
        self.authorize_with_execution_context_requirement(
            tool_name,
            arguments,
            context.authorization_meta(),
            observed,
            observed_execution_context,
            required_principal_kind,
            now,
            force_required,
            require_execution_context_binding,
        )
        .await
    }

    pub async fn authorize_unix(
        &self,
        method: &str,
        arguments: &Value,
        peer_uid: Option<u32>,
        authorization_meta: Option<&Value>,
    ) -> LeaseResult<()> {
        if !self.requires_lease(method) || self.inner.mode == InvocationLeaseMode::Off {
            return Ok(());
        }
        if self.inner.mode == InvocationLeaseMode::Invalid {
            return self
                .authorize(method, arguments, authorization_meta, None, "unix_uid", 0)
                .await;
        }
        let now = match unix_now() {
            Ok(now) => now,
            Err(error) => return self.handle_preparation_error(method, error),
        };
        let observed = peer_uid
            .and_then(|uid| principal_material(&LeasePrincipal::UnixUid { uid }).ok())
            .and_then(|(kind, commitment)| commitment.map(|value| (kind, value)));
        self.authorize(
            method,
            arguments,
            authorization_meta,
            observed,
            "unix_uid",
            now,
        )
        .await
    }

    fn handle_preparation_error(
        &self,
        tool_name: &str,
        error: InvocationLeaseError,
    ) -> LeaseResult<()> {
        self.inner.checked.fetch_add(1, Ordering::Relaxed);
        if self.inner.mode == InvocationLeaseMode::Shadow {
            self.inner.shadow_would_deny.fetch_add(1, Ordering::Relaxed);
            tracing::warn!(
                tool = tool_name,
                reason = error.code(),
                "invocation lease shadow preflight verdict: would deny"
            );
            Ok(())
        } else {
            self.inner.denied.fetch_add(1, Ordering::Relaxed);
            Err(error)
        }
    }

    async fn authorize(
        &self,
        tool_name: &str,
        arguments: &Value,
        authorization_meta: Option<&Value>,
        observed_principal: Option<(String, [u8; 32])>,
        required_principal_kind: &'static str,
        now_unix: i64,
    ) -> LeaseResult<()> {
        self.authorize_with_execution_context(
            tool_name,
            arguments,
            authorization_meta,
            observed_principal,
            None,
            required_principal_kind,
            now_unix,
        )
        .await
    }

    async fn authorize_with_execution_context(
        &self,
        tool_name: &str,
        arguments: &Value,
        authorization_meta: Option<&Value>,
        observed_principal: Option<(String, [u8; 32])>,
        observed_execution_context: Option<LeaseExecutionContext>,
        required_principal_kind: &'static str,
        now_unix: i64,
    ) -> LeaseResult<()> {
        self.authorize_with_execution_context_requirement(
            tool_name,
            arguments,
            authorization_meta,
            observed_principal,
            observed_execution_context,
            required_principal_kind,
            now_unix,
            false,
            false,
        )
        .await
    }

    async fn authorize_with_execution_context_requirement(
        &self,
        tool_name: &str,
        arguments: &Value,
        authorization_meta: Option<&Value>,
        observed_principal: Option<(String, [u8; 32])>,
        observed_execution_context: Option<LeaseExecutionContext>,
        required_principal_kind: &'static str,
        now_unix: i64,
        force_required: bool,
        require_execution_context_binding: bool,
    ) -> LeaseResult<()> {
        if self.inner.mode == InvocationLeaseMode::Off
            || (!force_required && !self.requires_lease(tool_name))
        {
            return Ok(());
        }
        self.inner.checked.fetch_add(1, Ordering::Relaxed);
        if self.inner.mode == InvocationLeaseMode::Invalid {
            self.inner.denied.fetch_add(1, Ordering::Relaxed);
            return Err(InvocationLeaseError::new(
                "invalid_configuration",
                self.inner
                    .config_error
                    .clone()
                    .unwrap_or_else(|| "invocation lease configuration is invalid".into()),
            ));
        }

        let result = self
            .evaluate(
                tool_name,
                arguments,
                authorization_meta,
                observed_principal,
                observed_execution_context,
                require_execution_context_binding,
                required_principal_kind,
                now_unix,
                self.inner.mode == InvocationLeaseMode::Enforce,
            )
            .await;
        match self.inner.mode {
            InvocationLeaseMode::Shadow => {
                match result {
                    Ok(()) => {
                        self.inner
                            .shadow_would_allow
                            .fetch_add(1, Ordering::Relaxed);
                    }
                    Err(error) => {
                        self.inner.shadow_would_deny.fetch_add(1, Ordering::Relaxed);
                        tracing::warn!(
                            tool = tool_name,
                            reason = error.code(),
                            "invocation lease shadow verdict: would deny"
                        );
                    }
                }
                Ok(())
            }
            InvocationLeaseMode::Enforce => match result {
                Ok(()) => {
                    self.inner.allowed.fetch_add(1, Ordering::Relaxed);
                    Ok(())
                }
                Err(error) => {
                    self.inner.denied.fetch_add(1, Ordering::Relaxed);
                    tracing::warn!(
                        tool = tool_name,
                        reason = error.code(),
                        "effectful invocation denied before dispatch"
                    );
                    Err(error)
                }
            },
            InvocationLeaseMode::Off => Ok(()),
            InvocationLeaseMode::Invalid => unreachable!("handled above"),
        }
    }

    async fn evaluate(
        &self,
        tool_name: &str,
        arguments: &Value,
        authorization_meta: Option<&Value>,
        observed_principal: Option<(String, [u8; 32])>,
        observed_execution_context: Option<LeaseExecutionContext>,
        require_execution_context_binding: bool,
        required_principal_kind: &'static str,
        now_unix: i64,
        consume: bool,
    ) -> LeaseResult<()> {
        let ledger = self.inner.ledger.clone().ok_or_else(|| {
            InvocationLeaseError::new(
                "ledger_unavailable",
                "local lease evaluation ledger is unavailable",
            )
        })?;
        let token = parse_lease_ref(authorization_meta)?;
        let token_commitment = token_commitment(&token.nonce);
        let arguments_sha256 = canonical_arguments_sha256(arguments)?;
        let target = normalized_target(tool_name, arguments);
        let target_sha256 = domain_hash(
            b"agent_bridge.invocation_lease.target.v1",
            target.as_bytes(),
        );
        let request = EvaluationRequest {
            token_commitment,
            token_nonce: token.nonce,
            token_signature: token.signature,
            tool_name: tool_name.to_string(),
            arguments_sha256,
            target_sha256,
            observed_principal,
            observed_execution_context,
            require_execution_context_binding,
            required_principal_kind,
            required_issuance_mode: self.inner.mode.as_str(),
            now_unix,
            call_id: format!("call-{}", uuid::Uuid::new_v4().simple()),
            consume,
            #[cfg(test)]
            linearized_now_override: Some(now_unix),
        };
        tokio::task::spawn_blocking(move || evaluate_ledger(&ledger, &request))
            .await
            .map_err(|_| {
                InvocationLeaseError::new(
                    "ledger_indeterminate",
                    "lease verification worker did not complete",
                )
            })?
    }
}

impl InvocationLeaseIssuer {
    pub async fn issue_exact(
        &self,
        principal: LeasePrincipal,
        tool_name: &str,
        arguments: &Value,
        ttl_secs: u64,
        max_uses: u32,
    ) -> LeaseResult<IssuedInvocationLease> {
        let now = unix_now()?;
        self.issue_exact_at(
            principal, tool_name, arguments, now, now, ttl_secs, max_uses,
        )
        .await
    }

    /// Issue an exact invocation lease additionally bound to a closed,
    /// server-attested execution context. The current variant is a stdio MCP
    /// connection instance; it does not attest a task or agent identity.
    pub async fn issue_exact_for_execution_context(
        &self,
        principal: LeasePrincipal,
        execution_context: LeaseExecutionContext,
        tool_name: &str,
        arguments: &Value,
        ttl_secs: u64,
        max_uses: u32,
    ) -> LeaseResult<IssuedInvocationLease> {
        let now = unix_now()?;
        self.issue_exact_at_with_execution_context(
            principal,
            Some(execution_context),
            tool_name,
            arguments,
            now,
            now,
            ttl_secs,
            max_uses,
        )
        .await
    }

    async fn issue_exact_at(
        &self,
        principal: LeasePrincipal,
        tool_name: &str,
        arguments: &Value,
        issued_at_unix: i64,
        not_before_unix: i64,
        ttl_secs: u64,
        max_uses: u32,
    ) -> LeaseResult<IssuedInvocationLease> {
        self.issue_exact_at_with_execution_context(
            principal,
            None,
            tool_name,
            arguments,
            issued_at_unix,
            not_before_unix,
            ttl_secs,
            max_uses,
        )
        .await
    }

    async fn issue_exact_at_with_execution_context(
        &self,
        principal: LeasePrincipal,
        execution_context: Option<LeaseExecutionContext>,
        tool_name: &str,
        arguments: &Value,
        issued_at_unix: i64,
        not_before_unix: i64,
        ttl_secs: u64,
        max_uses: u32,
    ) -> LeaseResult<IssuedInvocationLease> {
        validate_tool_name(tool_name)?;
        if !self.protected_tools.contains(tool_name) {
            return Err(InvocationLeaseError::new(
                "unprotected_tool",
                "issuer refuses a lease for a surface outside the protected set",
            ));
        }
        if !(1..=MAX_INVOCATION_LEASE_TTL_SECS).contains(&ttl_secs) {
            return Err(InvocationLeaseError::new(
                "invalid_ttl",
                format!("ttl_secs must be 1..={MAX_INVOCATION_LEASE_TTL_SECS}"),
            ));
        }
        if !(1..=MAX_INVOCATION_LEASE_USES).contains(&max_uses) {
            return Err(InvocationLeaseError::new(
                "invalid_uses",
                format!("max_uses must be 1..={MAX_INVOCATION_LEASE_USES}"),
            ));
        }
        if issued_at_unix < 0 || not_before_unix < issued_at_unix {
            return Err(InvocationLeaseError::new(
                "invalid_time",
                "issued/not-before timestamps are invalid",
            ));
        }
        let expires_at_unix = not_before_unix
            .checked_add(ttl_secs as i64)
            .ok_or_else(|| InvocationLeaseError::new("invalid_time", "expiry overflow"))?;
        let arguments_sha256 = canonical_arguments_sha256(arguments)?;
        let target = normalized_target(tool_name, arguments);
        let target_sha256 = domain_hash(
            b"agent_bridge.invocation_lease.target.v1",
            target.as_bytes(),
        );
        let (principal_kind, principal_commitment) = principal_material(&principal)?;
        let (execution_context_kind, execution_context_commitment) = execution_context
            .as_ref()
            .map(|context| {
                (
                    Some(context.kind().to_string()),
                    Some(*context.commitment()),
                )
            })
            .unwrap_or((None, None));
        let mut nonce = [0_u8; TOKEN_NONCE_BYTES];
        SystemRandom::new()
            .fill(&mut nonce)
            .map_err(|_| InvocationLeaseError::new("rng", "secure token generation failed"))?;
        let row = LeaseRow {
            token_commitment: token_commitment(&nonce),
            issuance_mode: self.mode.as_str().to_string(),
            lease_id: format!("lease-{}", uuid::Uuid::new_v4().simple()),
            tool_name: tool_name.to_string(),
            arguments_sha256,
            target_sha256,
            principal_kind: principal_kind.clone(),
            principal_commitment,
            execution_context_kind,
            execution_context_commitment,
            issued_at_unix,
            not_before_unix,
            expires_at_unix,
            max_uses,
        };
        let signature = self.signing_key.sign(&signature_message(
            &nonce,
            &row,
            &self.ledger.generation_id,
            &self.ledger.verify_public_key,
        ));
        let mut raw_token = [0_u8; TOKEN_BYTES];
        raw_token[..TOKEN_NONCE_BYTES].copy_from_slice(&nonce);
        raw_token[TOKEN_NONCE_BYTES..].copy_from_slice(signature.as_ref());
        let token = InvocationLeaseToken(format!(
            "{TOKEN_PREFIX}{}",
            URL_SAFE_NO_PAD.encode(raw_token)
        ));
        let ledger = self.ledger.clone();
        let insert_row = row.clone();
        tokio::task::spawn_blocking(move || insert_lease(&ledger, &insert_row))
            .await
            .map_err(|_| {
                InvocationLeaseError::new("ledger_indeterminate", "issuer worker did not complete")
            })??;
        tracing::info!(
            lease_id = row.lease_id,
            tool = row.tool_name,
            expires_at_unix = row.expires_at_unix,
            max_uses = row.max_uses,
            "trusted host issued exact invocation lease"
        );
        Ok(IssuedInvocationLease {
            receipt: InvocationLeaseReceipt {
                schema_version: "agent_bridge.effectful_call_lease.v3",
                issuance_mode: self.mode.as_str(),
                lease_id: row.lease_id,
                tool_name: row.tool_name,
                target,
                arguments_sha256: hex(&row.arguments_sha256),
                target_sha256: hex(&row.target_sha256),
                principal_kind,
                principal_commitment: row.principal_commitment.as_ref().map(hex),
                execution_context_kind: row.execution_context_kind.clone(),
                execution_context_commitment: row.execution_context_commitment.as_ref().map(hex),
                execution_context_binding_enforced: row.execution_context_kind.is_some(),
                issued_at_unix,
                not_before_unix,
                expires_at_unix,
                max_uses,
                grants_authority: self.mode == InvocationLeaseMode::Enforce,
                task_binding_enforced: false,
                same_principal_token_transfer_blocked: false,
            },
            token,
        })
    }

    pub async fn revoke(&self, issued: &IssuedInvocationLease, reason: &str) -> LeaseResult<()> {
        let parsed = decode_token(issued.token.expose_to_trusted_host())?;
        let commitment = token_commitment(&parsed.nonce);
        let reason_sha = domain_hash(
            b"agent_bridge.invocation_lease.revocation_reason.v1",
            reason.as_bytes(),
        );
        let now = unix_now()?;
        let ledger = self.ledger.clone();
        tokio::task::spawn_blocking(move || insert_revocation(&ledger, commitment, reason_sha, now))
            .await
            .map_err(|_| {
                InvocationLeaseError::new(
                    "ledger_indeterminate",
                    "revocation worker did not complete",
                )
            })?
    }
}

impl ProvisionedInvocationLeaseAuthority {
    /// Create a local evaluation ledger and ephemeral signing key. Production
    /// enforce is intentionally unavailable; tests may exercise its atomicity.
    pub fn provision(
        path: &Path,
        mode: InvocationLeaseMode,
        extra_tools: &[&str],
    ) -> LeaseResult<Self> {
        if !matches!(
            mode,
            InvocationLeaseMode::Shadow | InvocationLeaseMode::Enforce
        ) {
            return Err(InvocationLeaseError::new(
                "invalid_mode",
                "provision requires shadow or enforce mode",
            ));
        }
        if mode == InvocationLeaseMode::Enforce && !cfg!(test) {
            return Err(InvocationLeaseError::new(
                "enforcement_hold",
                "local same-UID SQLite enforce is unavailable outside cfg(test)",
            ));
        }
        let mut generation = [0_u8; 32];
        SystemRandom::new()
            .fill(&mut generation)
            .map_err(|_| InvocationLeaseError::new("rng", "generation RNG failed"))?;
        let signing_key = generate_signing_key()?;
        let verify_public_key = public_key_bytes(&signing_key)?;
        provision_ledger(path, generation, verify_public_key)?;
        let ledger = Arc::new(pin_existing_ledger(path, generation, verify_public_key)?);
        let protected = protected_tools_with_extras(extra_tools)?;
        let authorizer =
            InvocationLeaseAuthorizer::new(mode, Some(ledger.clone()), protected.clone(), None);
        let issuer = InvocationLeaseIssuer {
            ledger,
            protected_tools: Arc::new(protected),
            signing_key,
            mode,
        };
        Ok(Self {
            authorizer,
            issuer,
            generation_hex: hex(&generation),
            verify_key_hex: hex(&verify_public_key),
        })
    }

    /// Reopen only the verification capability using externally pinned public
    /// material. A private issuer cannot be reconstructed from the ledger.
    pub fn open_authorizer(
        path: &Path,
        generation_hex: &str,
        verify_key_hex: &str,
        mode: InvocationLeaseMode,
        extra_tools: &[&str],
    ) -> LeaseResult<InvocationLeaseAuthorizer> {
        if !matches!(
            mode,
            InvocationLeaseMode::Shadow | InvocationLeaseMode::Enforce
        ) {
            return Err(InvocationLeaseError::new(
                "invalid_mode",
                "open_authorizer requires shadow or enforce mode",
            ));
        }
        if mode == InvocationLeaseMode::Enforce && !cfg!(test) {
            return Err(InvocationLeaseError::new(
                "enforcement_hold",
                "local same-UID SQLite enforce is unavailable outside cfg(test)",
            ));
        }
        let generation = decode_hex_32(generation_hex)?;
        let verify_public_key = decode_hex_32(verify_key_hex)?;
        let ledger = Arc::new(pin_existing_ledger(path, generation, verify_public_key)?);
        let protected = protected_tools_with_extras(extra_tools)?;
        Ok(InvocationLeaseAuthorizer::new(
            mode,
            Some(ledger),
            protected,
            None,
        ))
    }
}

impl InvocationLeaseMcpGuard {
    fn requires_lease(&self, tool_name: &str) -> bool {
        match self.authorizer.mode() {
            InvocationLeaseMode::Off => false,
            InvocationLeaseMode::Invalid => self.authorizer.requires_lease(tool_name),
            InvocationLeaseMode::Shadow | InvocationLeaseMode::Enforce => self
                .lease_exempt_tools
                .as_ref()
                .map(|exempt| !exempt.contains(tool_name))
                .unwrap_or_else(|| self.authorizer.requires_lease(tool_name)),
        }
    }

    pub fn inventory_digest(&self) -> Option<&str> {
        self.inventory_digest.as_deref()
    }
}

#[async_trait]
impl ToolCallGuard for InvocationLeaseMcpGuard {
    async fn authorize_and_consume(
        &self,
        tool_name: &str,
        args: &Value,
        context: &ToolContext,
    ) -> ab_core::Result<()> {
        if !self.requires_lease(tool_name) {
            return Ok(());
        }
        if let Some(capability) = mcp_capability(tool_name) {
            self.security
                .check(capability)
                .map_err(ab_core::Error::Backend)?;
        }
        self.authorizer
            .authorize_mcp_required(
                tool_name,
                args,
                context,
                self.require_execution_context_binding,
            )
            .await
            .map_err(|error| ab_core::Error::Backend(error.to_string()))
    }

    fn policy_snapshot(&self) -> Value {
        let lease_exempt_tools = self
            .lease_exempt_tools
            .as_ref()
            .map(|tools| tools.iter().cloned().collect::<Vec<_>>());
        let ledger_trust_root_commitment_sha256 =
            self.authorizer.inner.ledger.as_deref().map(|ledger| {
                ledger_trust_root_commitment(&ledger.generation_id, &ledger.verify_public_key)
            });
        json!({
            "schema": "agent_bridge.invocation_lease_mcp_guard_policy.v1",
            "mode": self.authorizer.mode().as_str(),
            "configuration_valid": self.authorizer.inner.mode != InvocationLeaseMode::Invalid
                && self.authorizer.inner.config_error.is_none(),
            "configuration_error": self.authorizer.inner.config_error,
            "ledger_configured": self.authorizer.inner.ledger.is_some(),
            "ledger_trust_root_commitment_sha256": ledger_trust_root_commitment_sha256,
            "static_protected_tools": self.authorizer.inner.protected_tools.iter().collect::<Vec<_>>(),
            "lease_exempt_tools": lease_exempt_tools,
            "inventory_digest_sha256": self.inventory_digest.as_deref(),
            "require_execution_context_binding": self.require_execution_context_binding,
            "invalid_hold_open_tools": HOLD_OPEN_TOOLS,
            "security_ceiling": {
                "shell_exec": self.security.allow_shell_exec,
                "agent_spawn": self.security.allow_agent_spawn,
                "terminal_write": self.security.allow_terminal_write,
                "browser": self.security.allow_browser,
                "shell_exec_timeout_max_ms": self.security.shell_exec_timeout_max_ms
            },
            "behavior_cryptographically_attested": false,
            "production_fail_closed": false,
            "rollout_state": "hold"
        })
    }
}

fn ledger_trust_root_commitment(generation_id: &[u8; 32], verify_public_key: &[u8; 32]) -> String {
    let mut material = Vec::with_capacity(64);
    material.extend_from_slice(generation_id);
    material.extend_from_slice(verify_public_key);
    hex(&domain_hash(
        b"agent_bridge.invocation_lease.guard_trust_root_commitment.v1",
        &material,
    ))
}

pub fn rpc_capability(method: &str) -> Option<Cap> {
    match method {
        "terminal.send_keys" | "terminal.split" => Some(Cap::TerminalWrite),
        "browser.navigate" | "browser.eval" | "browser.click" | "browser.screenshot" => {
            Some(Cap::Browser)
        }
        _ => None,
    }
}

fn mcp_capability(tool_name: &str) -> Option<Cap> {
    match tool_name {
        "shell_exec" | "system_control" => Some(Cap::ShellExec),
        "agent_spawn" | "agent_send_input" | "agent_steer_launch" | "agent_steer_kill" => {
            Some(Cap::AgentSpawn)
        }
        "terminal_send_keys" | "terminal_split" | "terminal_resize" | "agent_steer_drive" => {
            Some(Cap::TerminalWrite)
        }
        name if name.starts_with("browser_") || name == "modelscope_abot_run_once" => {
            Some(Cap::Browser)
        }
        name if name.starts_with("mobile_") || name == "advance_track_then_project" => {
            Some(Cap::ShellExec)
        }
        _ => None,
    }
}

pub fn normalized_target(tool_name: &str, arguments: &Value) -> String {
    fn field(arguments: &Value, key: &str) -> Option<String> {
        arguments.get(key).and_then(|value| match value {
            Value::String(value) if !value.trim().is_empty() => Some(value.trim().to_string()),
            Value::Number(value) => Some(value.to_string()),
            _ => None,
        })
    }
    fn compact(value: String) -> String {
        if value.len() <= 256 {
            value
        } else {
            format!(
                "sha256:{}",
                hex(&domain_hash(
                    b"agent_bridge.invocation_lease.long_target.v1",
                    value.as_bytes(),
                ))
            )
        }
    }

    let detail = match tool_name {
        "shell_exec" => field(arguments, "cwd").unwrap_or_else(|| "process-cwd".into()),
        "system_control" => format!(
            "{}/{}@{}",
            field(arguments, "domain").unwrap_or_else(|| "?".into()),
            field(arguments, "action").unwrap_or_else(|| "?".into()),
            field(arguments, "bin").unwrap_or_else(|| "configured-bin".into())
        ),
        "terminal_send_keys" | "terminal_split" | "terminal_resize" | "terminal.send_keys"
        | "terminal.split" => field(arguments, "pane").unwrap_or_else(|| "?".into()),
        "agent_spawn" => format!(
            "{}@{}",
            field(arguments, "backend").unwrap_or_else(|| "default-runtime".into()),
            field(arguments, "node").unwrap_or_else(|| "local".into())
        ),
        "agent_send_input" => field(arguments, "id").unwrap_or_else(|| "?".into()),
        "agent_steer_launch" | "agent_steer_drive" => field(arguments, "session")
            .or_else(|| {
                Some(format!(
                    "{}:{}",
                    field(arguments, "project")?,
                    field(arguments, "role")?
                ))
            })
            .unwrap_or_else(|| "?".into()),
        name if name.starts_with("browser_") || name.starts_with("browser.") => {
            field(arguments, "url")
                .or_else(|| field(arguments, "page"))
                .unwrap_or_else(|| "browser-session".into())
        }
        "forum_post" | "forum_set_thread_status" => field(arguments, "peer")
            .or_else(|| field(arguments, "thread_id"))
            .or_else(|| field(arguments, "board"))
            .unwrap_or_else(|| "local-forum".into()),
        "world_patch" => field(arguments, "endpoint")
            .or_else(|| field(arguments, "world_id"))
            .unwrap_or_else(|| "configured-world".into()),
        "github_issue_create" => {
            field(arguments, "repo").unwrap_or_else(|| "configured-repo".into())
        }
        "gitlab_issue_create" => {
            field(arguments, "project").unwrap_or_else(|| "configured-project".into())
        }
        "notion_page_create" => {
            field(arguments, "parent_id").unwrap_or_else(|| "configured-parent".into())
        }
        "tailscale_acl_set" => "configured-tailnet".into(),
        "worktree_create" | "worktree_remove" | "ide_command" => field(arguments, "path")
            .or_else(|| field(arguments, "repo"))
            .or_else(|| field(arguments, "cwd"))
            .unwrap_or_else(|| "configured-workspace".into()),
        name if name.starts_with("mobile_") => field(arguments, "device")
            .or_else(|| field(arguments, "serial"))
            .unwrap_or_else(|| "selected-device".into()),
        _ => ["target", "path", "url", "peer", "node", "session", "id"]
            .into_iter()
            .find_map(|key| field(arguments, key))
            .unwrap_or_else(|| "default-target".into()),
    };
    format!("{tool_name}:{}", compact(detail))
}

fn default_protected_tools() -> BTreeSet<String> {
    DEFAULT_PROTECTED_TOOLS
        .iter()
        .map(|tool| (*tool).to_string())
        .collect()
}

fn protected_tools_with_extras(extra_tools: &[&str]) -> LeaseResult<BTreeSet<String>> {
    let mut protected = default_protected_tools();
    for tool in extra_tools {
        validate_tool_name(tool)?;
        protected.insert((*tool).to_string());
    }
    Ok(protected)
}

fn generate_signing_key() -> LeaseResult<Arc<Ed25519KeyPair>> {
    let rng = SystemRandom::new();
    let document = Ed25519KeyPair::generate_pkcs8(&rng)
        .map_err(|_| InvocationLeaseError::new("rng", "Ed25519 key generation failed"))?;
    let key = Ed25519KeyPair::from_pkcs8(document.as_ref()).map_err(|_| {
        InvocationLeaseError::new("signing_key", "generated Ed25519 key was rejected")
    })?;
    Ok(Arc::new(key))
}

fn public_key_bytes(key: &Ed25519KeyPair) -> LeaseResult<[u8; 32]> {
    key.public_key().as_ref().try_into().map_err(|_| {
        InvocationLeaseError::new("signing_key", "Ed25519 public key has wrong length")
    })
}

fn extend_protected_tools(tools: &mut BTreeSet<String>, input: &str) -> LeaseResult<()> {
    if input.len() > 4096 {
        return Err(InvocationLeaseError::new(
            "config",
            "AB_INVOCATION_LEASE_EXTRA_TOOLS exceeds 4096 bytes",
        ));
    }
    for value in input
        .split(',')
        .map(str::trim)
        .filter(|value| !value.is_empty())
    {
        validate_tool_name(value)?;
        tools.insert(value.to_string());
    }
    Ok(())
}

fn validate_tool_name(value: &str) -> LeaseResult<()> {
    if value.is_empty()
        || value.len() > 128
        || !value
            .bytes()
            .all(|byte| byte.is_ascii_alphanumeric() || matches!(byte, b'_' | b'-' | b'.'))
    {
        return Err(InvocationLeaseError::new(
            "invalid_tool",
            "tool name must be 1..=128 ASCII letters, digits, '_', '-', or '.'",
        ));
    }
    Ok(())
}

fn principal_material(principal: &LeasePrincipal) -> LeaseResult<(String, Option<[u8; 32]>)> {
    match principal {
        LeasePrincipal::Bearer => Ok(("bearer".into(), None)),
        LeasePrincipal::OAuth {
            issuer,
            local_subject,
        } => {
            if issuer.is_empty()
                || issuer.len() > 1024
                || local_subject.is_empty()
                || local_subject.len() > 512
            {
                return Err(InvocationLeaseError::new(
                    "invalid_principal",
                    "OAuth issuer/local subject is empty or too long",
                ));
            }
            let canonical = serde_json_canonicalizer::to_vec(&json!({
                "issuer": issuer,
                "local_subject": local_subject
            }))
            .map_err(|_| {
                InvocationLeaseError::new(
                    "invalid_principal",
                    "OAuth principal is not canonicalizable",
                )
            })?;
            Ok((
                "oauth".into(),
                Some(domain_hash(
                    b"agent_bridge.invocation_lease.oauth_principal.v1",
                    &canonical,
                )),
            ))
        }
        LeasePrincipal::UnixUid { uid } => Ok((
            "unix_uid".into(),
            Some(domain_hash(
                b"agent_bridge.invocation_lease.unix_uid.v1",
                &uid.to_be_bytes(),
            )),
        )),
    }
}

fn parse_lease_ref(meta: Option<&Value>) -> LeaseResult<ParsedLeaseToken> {
    let lease = meta
        .and_then(|value| value.as_object())
        .and_then(|object| object.get(LEASE_META_KEY))
        .and_then(Value::as_object)
        .ok_or_else(|| {
            InvocationLeaseError::new(
                "missing_lease",
                "effectful call requires a params._meta invocation lease reference",
            )
        })?;
    if lease.len() != 2 || lease.get("schema").and_then(Value::as_str) != Some(LEASE_REF_SCHEMA) {
        return Err(InvocationLeaseError::new(
            "malformed_lease",
            "invocation lease reference has the wrong closed schema",
        ));
    }
    let token = lease.get("token").and_then(Value::as_str).ok_or_else(|| {
        InvocationLeaseError::new("malformed_lease", "invocation lease token is missing")
    })?;
    decode_token(token)
}

fn decode_token(token: &str) -> LeaseResult<ParsedLeaseToken> {
    let encoded = token.strip_prefix(TOKEN_PREFIX).ok_or_else(|| {
        InvocationLeaseError::new(
            "malformed_lease",
            "invocation lease token prefix is invalid",
        )
    })?;
    if encoded.len() != 128 {
        return Err(InvocationLeaseError::new(
            "malformed_lease",
            "invocation lease token length is invalid",
        ));
    }
    let decoded = URL_SAFE_NO_PAD.decode(encoded).map_err(|_| {
        InvocationLeaseError::new(
            "malformed_lease",
            "invocation lease token encoding is invalid",
        )
    })?;
    let raw: [u8; TOKEN_BYTES] = decoded.try_into().map_err(|_| {
        InvocationLeaseError::new("malformed_lease", "invocation lease token size is invalid")
    })?;
    let mut nonce = [0_u8; TOKEN_NONCE_BYTES];
    nonce.copy_from_slice(&raw[..TOKEN_NONCE_BYTES]);
    let mut signature = [0_u8; TOKEN_SIGNATURE_BYTES];
    signature.copy_from_slice(&raw[TOKEN_NONCE_BYTES..]);
    Ok(ParsedLeaseToken { nonce, signature })
}

fn canonical_arguments_sha256(arguments: &Value) -> LeaseResult<[u8; 32]> {
    let rough_size = serde_json::to_vec(arguments)
        .map_err(|_| InvocationLeaseError::new("arguments", "arguments are not serializable"))?
        .len();
    if rough_size > MAX_ARGUMENT_BYTES {
        return Err(InvocationLeaseError::new(
            "arguments_too_large",
            format!("arguments exceed {MAX_ARGUMENT_BYTES} bytes"),
        ));
    }
    let canonical = serde_json_canonicalizer::to_vec(arguments).map_err(|_| {
        InvocationLeaseError::new("arguments", "arguments cannot be canonicalized as JCS")
    })?;
    Ok(domain_hash(
        b"agent_bridge.invocation_lease.arguments_jcs.v1",
        &canonical,
    ))
}

fn token_commitment(nonce: &[u8; TOKEN_NONCE_BYTES]) -> [u8; 32] {
    domain_hash(
        b"agent_bridge.invocation_lease.token_nonce_commitment.v2",
        nonce,
    )
}

fn scope_commitment(row: &LeaseRow) -> [u8; 32] {
    let material = json!({
        "schema": "agent_bridge.invocation_lease_scope.v3",
        "token_commitment": hex(&row.token_commitment),
        "issuance_mode": &row.issuance_mode,
        "lease_id": &row.lease_id,
        "tool_name": &row.tool_name,
        "arguments_sha256": hex(&row.arguments_sha256),
        "target_sha256": hex(&row.target_sha256),
        "principal_kind": &row.principal_kind,
        "principal_commitment": row.principal_commitment.as_ref().map(hex),
        "execution_context_kind": &row.execution_context_kind,
        "execution_context_commitment": row.execution_context_commitment.as_ref().map(hex),
        "issued_at_unix": row.issued_at_unix,
        "not_before_unix": row.not_before_unix,
        "expires_at_unix": row.expires_at_unix,
        "max_uses": row.max_uses,
    });
    let canonical = serde_json_canonicalizer::to_vec(&material)
        .expect("fixed invocation lease scope is canonicalizable");
    domain_hash(
        b"agent_bridge.invocation_lease.scope_commitment.v3",
        &canonical,
    )
}

fn signature_message(
    nonce: &[u8; TOKEN_NONCE_BYTES],
    row: &LeaseRow,
    generation_id: &[u8; 32],
    verify_public_key: &[u8; 32],
) -> [u8; 32] {
    let scope = scope_commitment(row);
    let mut material = Vec::with_capacity(
        TOKEN_NONCE_BYTES + scope.len() + generation_id.len() + verify_public_key.len(),
    );
    material.extend_from_slice(nonce);
    material.extend_from_slice(&scope);
    material.extend_from_slice(generation_id);
    material.extend_from_slice(verify_public_key);
    domain_hash(
        b"agent_bridge.invocation_lease.ed25519_message.v3",
        &material,
    )
}

fn domain_hash(domain: &[u8], payload: &[u8]) -> [u8; 32] {
    let mut hasher = Sha256::new();
    hasher.update((domain.len() as u64).to_be_bytes());
    hasher.update(domain);
    hasher.update((payload.len() as u64).to_be_bytes());
    hasher.update(payload);
    hasher.finalize().into()
}

fn hex(bytes: &[u8; 32]) -> String {
    bytes.iter().map(|byte| format!("{byte:02x}")).collect()
}

fn decode_hex_32(value: &str) -> LeaseResult<[u8; 32]> {
    decode_hex_32_named(value, "config", "ledger generation")
}

fn decode_hex_32_named(value: &str, code: &'static str, label: &str) -> LeaseResult<[u8; 32]> {
    if value.len() != 64 || !value.bytes().all(|byte| byte.is_ascii_hexdigit()) {
        return Err(InvocationLeaseError::new(
            code,
            format!("{label} must be exactly 64 hexadecimal characters"),
        ));
    }
    let mut out = [0_u8; 32];
    for (index, chunk) in value.as_bytes().chunks_exact(2).enumerate() {
        let pair = std::str::from_utf8(chunk).expect("hex is ASCII");
        out[index] = u8::from_str_radix(pair, 16).map_err(|_| {
            InvocationLeaseError::new(code, format!("{label} contains invalid hex"))
        })?;
    }
    Ok(out)
}

fn unix_now() -> LeaseResult<i64> {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|duration| duration.as_secs() as i64)
        .map_err(|_| InvocationLeaseError::new("clock", "system clock precedes Unix epoch"))
}

fn open_flags() -> OpenFlags {
    OpenFlags::SQLITE_OPEN_READ_WRITE
        | OpenFlags::SQLITE_OPEN_NO_MUTEX
        | OpenFlags::SQLITE_OPEN_NOFOLLOW
        | OpenFlags::SQLITE_OPEN_EXRESCODE
}

struct ValidatedLedgerFile {
    canonical_path: PathBuf,
    #[cfg(unix)]
    device: u64,
    #[cfg(unix)]
    inode: u64,
}

fn validate_file(path: &Path) -> LeaseResult<ValidatedLedgerFile> {
    let metadata = std::fs::symlink_metadata(path).map_err(|_| {
        InvocationLeaseError::new("ledger_identity", "provisioned lease ledger is missing")
    })?;
    if !metadata.file_type().is_file() || metadata.file_type().is_symlink() {
        return Err(InvocationLeaseError::new(
            "ledger_identity",
            "lease ledger is not a regular non-symlink file",
        ));
    }
    #[cfg(unix)]
    {
        use std::os::unix::fs::{MetadataExt as _, PermissionsExt as _};
        if metadata.permissions().mode() & 0o7777 != 0o600 {
            return Err(InvocationLeaseError::new(
                "ledger_identity",
                "lease ledger mode must be exactly 0600",
            ));
        }
        if metadata.uid() != unsafe { libc::geteuid() } {
            return Err(InvocationLeaseError::new(
                "ledger_identity",
                "lease ledger is not owned by the current effective uid",
            ));
        }
        let canonical_path = std::fs::canonicalize(path).map_err(|_| {
            InvocationLeaseError::new("ledger_identity", "lease ledger cannot be canonicalized")
        })?;
        return Ok(ValidatedLedgerFile {
            canonical_path,
            device: metadata.dev(),
            inode: metadata.ino(),
        });
    }
    #[cfg(not(unix))]
    {
        let canonical_path = std::fs::canonicalize(path).map_err(|_| {
            InvocationLeaseError::new("ledger_identity", "lease ledger cannot be canonicalized")
        })?;
        Ok(ValidatedLedgerFile { canonical_path })
    }
}

fn read_i64_pragma(connection: &Connection, pragma: &str) -> rusqlite::Result<i64> {
    connection.query_row(&format!("PRAGMA {pragma}"), [], |row| row.get(0))
}

fn read_text_pragma(connection: &Connection, pragma: &str) -> rusqlite::Result<String> {
    connection.query_row(&format!("PRAGMA {pragma}"), [], |row| row.get(0))
}

fn configure_connection(connection: &Connection) -> LeaseResult<()> {
    connection.busy_timeout(BUSY_TIMEOUT).map_err(|_| {
        InvocationLeaseError::new("ledger_indeterminate", "cannot configure busy timeout")
    })?;
    let journal = read_text_pragma(connection, "journal_mode").map_err(|_| {
        InvocationLeaseError::new("ledger_indeterminate", "cannot read journal mode")
    })?;
    if !journal.eq_ignore_ascii_case("delete") {
        return Err(InvocationLeaseError::new(
            "ledger_identity",
            "lease ledger requires DELETE journal mode",
        ));
    }
    connection
        .execute_batch(
            "PRAGMA synchronous=EXTRA;
             PRAGMA foreign_keys=ON;
             PRAGMA read_uncommitted=OFF;
             PRAGMA query_only=OFF;
             PRAGMA trusted_schema=OFF;
             PRAGMA locking_mode=NORMAL;",
        )
        .map_err(|_| {
            InvocationLeaseError::new(
                "ledger_indeterminate",
                "cannot configure closed ledger connection profile",
            )
        })?;
    let profile_ok = read_i64_pragma(connection, "synchronous").ok() == Some(3)
        && read_i64_pragma(connection, "foreign_keys").ok() == Some(1)
        && read_i64_pragma(connection, "read_uncommitted").ok() == Some(0)
        && read_i64_pragma(connection, "query_only").ok() == Some(0)
        && read_i64_pragma(connection, "trusted_schema").ok() == Some(0)
        && read_text_pragma(connection, "locking_mode")
            .map(|value| value.eq_ignore_ascii_case("normal"))
            .unwrap_or(false);
    if !profile_ok {
        return Err(InvocationLeaseError::new(
            "ledger_identity",
            "lease ledger did not retain its closed connection profile",
        ));
    }
    Ok(())
}

fn table_columns(
    connection: &Connection,
    table: &str,
) -> rusqlite::Result<Vec<(String, String, i64, i64)>> {
    connection
        .prepare(&format!("PRAGMA main.table_info('{table}')"))?
        .query_map([], |row| {
            Ok((row.get(1)?, row.get(2)?, row.get(3)?, row.get(5)?))
        })?
        .collect()
}

fn schema_ddl_digest(connection: &Connection) -> LeaseResult<[u8; 32]> {
    let objects: Vec<(String, String, String)> = connection
        .prepare(
            "SELECT type, name, COALESCE(sql, '') FROM main.sqlite_schema
             WHERE name NOT LIKE 'sqlite_%' ORDER BY type, name",
        )
        .and_then(|mut statement| {
            statement
                .query_map([], |row| Ok((row.get(0)?, row.get(1)?, row.get(2)?)))?
                .collect()
        })
        .map_err(|_| {
            InvocationLeaseError::new("ledger_indeterminate", "cannot inspect ledger DDL")
        })?;
    let canonical = serde_json_canonicalizer::to_vec(&objects).map_err(|_| {
        InvocationLeaseError::new("ledger_indeterminate", "cannot canonicalize ledger DDL")
    })?;
    Ok(domain_hash(
        b"agent_bridge.invocation_lease.sqlite_ddl.v2",
        &canonical,
    ))
}

fn expected_schema_ddl_digest() -> LeaseResult<[u8; 32]> {
    let connection = Connection::open_in_memory().map_err(|_| {
        InvocationLeaseError::new("ledger_indeterminate", "cannot build expected schema")
    })?;
    connection.execute_batch(SCHEMA_SQL).map_err(|_| {
        InvocationLeaseError::new("ledger_indeterminate", "expected schema is invalid")
    })?;
    schema_ddl_digest(&connection)
}

fn validate_schema(
    connection: &Connection,
    generation: &[u8; 32],
    verify_public_key: &[u8; 32],
) -> LeaseResult<()> {
    if read_i64_pragma(connection, "application_id").ok() != Some(APPLICATION_ID)
        || read_i64_pragma(connection, "user_version").ok() != Some(USER_VERSION)
    {
        return Err(InvocationLeaseError::new(
            "ledger_identity",
            "lease ledger application/schema identity is invalid",
        ));
    }
    let objects: Vec<(String, String)> = connection
        .prepare(
            "SELECT type, name FROM main.sqlite_schema
             WHERE name NOT LIKE 'sqlite_%' ORDER BY type, name",
        )
        .and_then(|mut statement| {
            statement
                .query_map([], |row| Ok((row.get(0)?, row.get(1)?)))?
                .collect()
        })
        .map_err(|_| {
            InvocationLeaseError::new("ledger_indeterminate", "cannot inspect ledger schema")
        })?;
    let mut expected: Vec<(String, String)> = EXPECTED_OBJECTS
        .iter()
        .map(|(kind, name)| ((*kind).into(), (*name).into()))
        .collect();
    expected.sort();
    if objects != expected {
        return Err(InvocationLeaseError::new(
            "ledger_identity",
            "lease ledger contains missing, renamed, or extra persistent objects",
        ));
    }
    if schema_ddl_digest(connection)? != expected_schema_ddl_digest()? {
        return Err(InvocationLeaseError::new(
            "ledger_identity",
            "lease ledger table/trigger DDL differs from the compiled closed schema",
        ));
    }
    let expected_columns = [
        (
            META_TABLE,
            vec![
                ("singleton".into(), "INTEGER".into(), 1, 1),
                ("generation_id".into(), "BLOB".into(), 1, 0),
                ("verify_public_key".into(), "BLOB".into(), 1, 0),
            ],
        ),
        (
            LEASE_TABLE,
            vec![
                ("token_commitment".into(), "BLOB".into(), 1, 1),
                ("issuance_mode".into(), "TEXT".into(), 1, 0),
                ("lease_id".into(), "TEXT".into(), 1, 0),
                ("tool_name".into(), "TEXT".into(), 1, 0),
                ("arguments_sha256".into(), "BLOB".into(), 1, 0),
                ("target_sha256".into(), "BLOB".into(), 1, 0),
                ("principal_kind".into(), "TEXT".into(), 1, 0),
                ("principal_commitment".into(), "BLOB".into(), 0, 0),
                ("execution_context_kind".into(), "TEXT".into(), 0, 0),
                ("execution_context_commitment".into(), "BLOB".into(), 0, 0),
                ("issued_at_unix".into(), "INTEGER".into(), 1, 0),
                ("not_before_unix".into(), "INTEGER".into(), 1, 0),
                ("expires_at_unix".into(), "INTEGER".into(), 1, 0),
                ("max_uses".into(), "INTEGER".into(), 1, 0),
            ],
        ),
        (
            CONSUMPTION_TABLE,
            vec![
                ("token_commitment".into(), "BLOB".into(), 1, 1),
                ("use_index".into(), "INTEGER".into(), 1, 2),
                ("scope_sha256".into(), "BLOB".into(), 1, 0),
                ("call_id".into(), "TEXT".into(), 1, 0),
                ("consumed_at_unix".into(), "INTEGER".into(), 1, 0),
            ],
        ),
        (
            REVOCATION_TABLE,
            vec![
                ("token_commitment".into(), "BLOB".into(), 1, 1),
                ("reason_sha256".into(), "BLOB".into(), 1, 0),
                ("revoked_at_unix".into(), "INTEGER".into(), 1, 0),
            ],
        ),
    ];
    for (table, expected) in expected_columns {
        if table_columns(connection, table).ok().as_ref() != Some(&expected) {
            return Err(InvocationLeaseError::new(
                "ledger_identity",
                format!("lease ledger column profile drifted for {table}"),
            ));
        }
    }
    let stored_generation: Option<Vec<u8>> = connection
        .query_row(
            &format!("SELECT generation_id FROM {META_TABLE} WHERE singleton=1"),
            [],
            |row| row.get(0),
        )
        .optional()
        .map_err(|_| {
            InvocationLeaseError::new("ledger_indeterminate", "cannot read ledger generation")
        })?;
    if stored_generation.as_deref() != Some(generation.as_slice()) {
        return Err(InvocationLeaseError::new(
            "ledger_identity",
            "lease ledger generation differs from the external pin",
        ));
    }
    let stored_verify_key: Option<Vec<u8>> = connection
        .query_row(
            &format!("SELECT verify_public_key FROM {META_TABLE} WHERE singleton=1"),
            [],
            |row| row.get(0),
        )
        .optional()
        .map_err(|_| {
            InvocationLeaseError::new("ledger_indeterminate", "cannot read ledger verify key")
        })?;
    if stored_verify_key.as_deref() != Some(verify_public_key.as_slice()) {
        return Err(InvocationLeaseError::new(
            "ledger_identity",
            "lease ledger verify key differs from the external pin",
        ));
    }
    if read_text_pragma(connection, "quick_check(1)")
        .ok()
        .as_deref()
        != Some("ok")
    {
        return Err(InvocationLeaseError::new(
            "ledger_identity",
            "lease ledger quick_check failed",
        ));
    }
    Ok(())
}

fn open_existing(ledger: &LedgerIdentity) -> LeaseResult<Connection> {
    let before = validate_file(&ledger.path)?;
    if before.canonical_path != ledger.canonical_path || {
        #[cfg(unix)]
        {
            before.device != ledger.device || before.inode != ledger.inode
        }
        #[cfg(not(unix))]
        {
            false
        }
    } {
        return Err(InvocationLeaseError::new(
            "ledger_identity",
            "lease ledger canonical path or pinned device/inode changed",
        ));
    }
    let connection = Connection::open_with_flags(&ledger.path, open_flags()).map_err(|_| {
        InvocationLeaseError::new("ledger_indeterminate", "cannot open existing lease ledger")
    })?;
    let after = validate_file(&ledger.path)?;
    if after.canonical_path != ledger.canonical_path || {
        #[cfg(unix)]
        {
            after.device != ledger.device || after.inode != ledger.inode
        }
        #[cfg(not(unix))]
        {
            false
        }
    } {
        return Err(InvocationLeaseError::new(
            "ledger_identity",
            "lease ledger changed while it was being opened",
        ));
    }
    configure_connection(&connection)?;
    validate_schema(
        &connection,
        &ledger.generation_id,
        &ledger.verify_public_key,
    )?;
    Ok(connection)
}

fn pin_existing_ledger(
    path: &Path,
    generation_id: [u8; 32],
    verify_public_key: [u8; 32],
) -> LeaseResult<LedgerIdentity> {
    let validated = validate_file(path)?;
    let ledger = LedgerIdentity {
        path: path.to_path_buf(),
        canonical_path: validated.canonical_path,
        generation_id,
        verify_public_key,
        #[cfg(unix)]
        device: validated.device,
        #[cfg(unix)]
        inode: validated.inode,
    };
    drop(open_existing(&ledger)?);
    Ok(ledger)
}

fn provision_ledger(
    path: &Path,
    generation_id: [u8; 32],
    verify_public_key: [u8; 32],
) -> LeaseResult<()> {
    if generation_id.iter().all(|byte| *byte == 0) {
        return Err(InvocationLeaseError::new(
            "ledger_identity",
            "all-zero ledger generation is forbidden",
        ));
    }
    let parent = path.parent().ok_or_else(|| {
        InvocationLeaseError::new("ledger_identity", "ledger requires an explicit parent")
    })?;
    if !parent.is_dir() {
        return Err(InvocationLeaseError::new(
            "ledger_identity",
            "ledger parent must already exist",
        ));
    }
    let mut options = std::fs::OpenOptions::new();
    options.read(true).write(true).create_new(true);
    #[cfg(unix)]
    {
        use std::os::unix::fs::OpenOptionsExt as _;
        options.mode(0o600);
    }
    let file = options.open(path).map_err(|_| {
        InvocationLeaseError::new("ledger_identity", "refusing to replace an existing ledger")
    })?;
    file.sync_all().map_err(|_| {
        InvocationLeaseError::new("ledger_indeterminate", "cannot sync new ledger file")
    })?;
    drop(file);
    let provision = (|| -> LeaseResult<()> {
        let mut connection = Connection::open_with_flags(path, open_flags()).map_err(|_| {
            InvocationLeaseError::new("ledger_indeterminate", "cannot open new ledger")
        })?;
        connection.busy_timeout(BUSY_TIMEOUT).map_err(|_| {
            InvocationLeaseError::new("ledger_indeterminate", "cannot set new-ledger timeout")
        })?;
        connection
            .execute_batch("PRAGMA journal_mode=DELETE; PRAGMA synchronous=EXTRA;")
            .map_err(|_| {
                InvocationLeaseError::new("ledger_indeterminate", "cannot set durability profile")
            })?;
        let transaction = connection
            .transaction_with_behavior(TransactionBehavior::Immediate)
            .map_err(|_| {
                InvocationLeaseError::new("ledger_indeterminate", "cannot provision transaction")
            })?;
        transaction.execute_batch(SCHEMA_SQL).map_err(|_| {
            InvocationLeaseError::new("ledger_indeterminate", "cannot create closed schema")
        })?;
        transaction
            .execute(
                &format!(
                    "INSERT INTO {META_TABLE}(singleton,generation_id,verify_public_key)
                     VALUES(1,?1,?2)"
                ),
                params![generation_id.as_slice(), verify_public_key.as_slice()],
            )
            .map_err(|_| {
                InvocationLeaseError::new("ledger_indeterminate", "cannot pin ledger generation")
            })?;
        transaction
            .execute_batch(&format!(
                "PRAGMA application_id={APPLICATION_ID}; PRAGMA user_version={USER_VERSION};"
            ))
            .map_err(|_| {
                InvocationLeaseError::new("ledger_indeterminate", "cannot pin schema header")
            })?;
        transaction.commit().map_err(|_| {
            InvocationLeaseError::new(
                "ledger_indeterminate",
                "ledger provisioning commit is indeterminate",
            )
        })?;
        configure_connection(&connection)?;
        validate_schema(&connection, &generation_id, &verify_public_key)?;
        Ok(())
    })();
    if provision.is_err() {
        let _ = std::fs::remove_file(path);
        let mut journal = path.as_os_str().to_os_string();
        journal.push("-journal");
        let _ = std::fs::remove_file(PathBuf::from(journal));
        return provision;
    }
    std::fs::File::open(path)
        .and_then(|file| file.sync_all())
        .map_err(|_| {
            InvocationLeaseError::new("ledger_indeterminate", "cannot sync provisioned ledger")
        })?;
    std::fs::File::open(parent)
        .and_then(|directory| directory.sync_all())
        .map_err(|_| {
            InvocationLeaseError::new(
                "ledger_indeterminate",
                "cannot sync provisioned ledger directory",
            )
        })?;
    Ok(())
}

fn insert_lease(ledger: &LedgerIdentity, row: &LeaseRow) -> LeaseResult<()> {
    let mut connection = open_existing(ledger)?;
    let transaction = connection
        .transaction_with_behavior(TransactionBehavior::Immediate)
        .map_err(|_| {
            InvocationLeaseError::new(
                "ledger_indeterminate",
                "issuer cannot acquire ledger writer",
            )
        })?;
    validate_schema(
        &transaction,
        &ledger.generation_id,
        &ledger.verify_public_key,
    )?;
    let inserted = transaction
        .execute(
            &format!(
                "INSERT INTO {LEASE_TABLE}
                 (token_commitment,issuance_mode,lease_id,tool_name,arguments_sha256,target_sha256,
                  principal_kind,principal_commitment,execution_context_kind,
                  execution_context_commitment,issued_at_unix,not_before_unix,
                  expires_at_unix,max_uses)
                 VALUES(?1,?2,?3,?4,?5,?6,?7,?8,?9,?10,?11,?12,?13,?14)"
            ),
            params![
                row.token_commitment.as_slice(),
                row.issuance_mode,
                row.lease_id,
                row.tool_name,
                row.arguments_sha256.as_slice(),
                row.target_sha256.as_slice(),
                row.principal_kind,
                row.principal_commitment
                    .as_ref()
                    .map(|value| value.as_slice()),
                row.execution_context_kind,
                row.execution_context_commitment
                    .as_ref()
                    .map(|value| value.as_slice()),
                row.issued_at_unix,
                row.not_before_unix,
                row.expires_at_unix,
                row.max_uses,
            ],
        )
        .map_err(|_| {
            InvocationLeaseError::new("ledger_indeterminate", "lease insert failed closed")
        })?;
    if inserted != 1 {
        return Err(InvocationLeaseError::new(
            "ledger_indeterminate",
            "lease insert returned an impossible row count",
        ));
    }
    transaction.commit().map_err(|_| {
        InvocationLeaseError::new(
            "ledger_indeterminate",
            "lease issue commit is indeterminate",
        )
    })
}

fn insert_revocation(
    ledger: &LedgerIdentity,
    token: [u8; 32],
    reason: [u8; 32],
    now: i64,
) -> LeaseResult<()> {
    let mut connection = open_existing(ledger)?;
    let transaction = connection
        .transaction_with_behavior(TransactionBehavior::Immediate)
        .map_err(|_| {
            InvocationLeaseError::new("ledger_indeterminate", "cannot acquire revocation writer")
        })?;
    let inserted = transaction
        .execute(
            &format!(
                "INSERT INTO {REVOCATION_TABLE}(token_commitment,reason_sha256,revoked_at_unix)
                 VALUES(?1,?2,?3) ON CONFLICT(token_commitment) DO NOTHING"
            ),
            params![token.as_slice(), reason.as_slice(), now],
        )
        .map_err(|_| {
            InvocationLeaseError::new("ledger_indeterminate", "revocation insert failed closed")
        })?;
    if inserted != 0 && inserted != 1 {
        return Err(InvocationLeaseError::new(
            "ledger_indeterminate",
            "revocation insert returned an impossible row count",
        ));
    }
    transaction.commit().map_err(|_| {
        InvocationLeaseError::new("ledger_indeterminate", "revocation commit is indeterminate")
    })
}

fn read_lease_row(
    transaction: &rusqlite::Transaction<'_>,
    token_commitment: &[u8; 32],
) -> LeaseResult<Option<LeaseRow>> {
    let raw: Option<(
        String,
        String,
        String,
        Vec<u8>,
        Vec<u8>,
        String,
        Option<Vec<u8>>,
        Option<String>,
        Option<Vec<u8>>,
        i64,
        i64,
        i64,
        i64,
    )> = transaction
        .query_row(
            &format!(
                "SELECT issuance_mode,lease_id,tool_name,arguments_sha256,target_sha256,principal_kind,
                        principal_commitment,execution_context_kind,execution_context_commitment,
                        issued_at_unix,not_before_unix,expires_at_unix,max_uses
                 FROM {LEASE_TABLE} WHERE token_commitment=?1"
            ),
            [token_commitment.as_slice()],
            |row| {
                Ok((
                    row.get(0)?,
                    row.get(1)?,
                    row.get(2)?,
                    row.get(3)?,
                    row.get(4)?,
                    row.get(5)?,
                    row.get(6)?,
                    row.get(7)?,
                    row.get(8)?,
                    row.get(9)?,
                    row.get(10)?,
                    row.get(11)?,
                    row.get(12)?,
                ))
            },
        )
        .optional()
        .map_err(|_| {
            InvocationLeaseError::new("ledger_indeterminate", "cannot read lease record")
        })?;
    let Some((
        issuance_mode,
        lease_id,
        tool_name,
        arguments,
        target,
        principal_kind,
        principal,
        execution_context_kind,
        execution_context,
        issued,
        not_before,
        expires,
        max_uses,
    )) = raw
    else {
        return Ok(None);
    };
    let arguments_sha256: [u8; 32] = arguments.try_into().map_err(|_| {
        InvocationLeaseError::new(
            "ledger_identity",
            "stored arguments digest has wrong length",
        )
    })?;
    let target_sha256: [u8; 32] = target.try_into().map_err(|_| {
        InvocationLeaseError::new("ledger_identity", "stored target digest has wrong length")
    })?;
    let principal_commitment = principal
        .map(|value| {
            value.try_into().map_err(|_| {
                InvocationLeaseError::new(
                    "ledger_identity",
                    "stored principal digest has wrong length",
                )
            })
        })
        .transpose()?;
    let execution_context_commitment = execution_context
        .map(|value| {
            value.try_into().map_err(|_| {
                InvocationLeaseError::new(
                    "ledger_identity",
                    "stored execution context commitment has wrong length",
                )
            })
        })
        .transpose()?;
    match (
        execution_context_kind.as_deref(),
        execution_context_commitment.as_ref(),
    ) {
        (None, None) | (Some(MCP_STDIO_CONNECTION_CONTEXT_KIND), Some(_)) => {}
        _ => {
            return Err(InvocationLeaseError::new(
                "ledger_identity",
                "stored execution context profile is outside the closed schema",
            ));
        }
    }
    let max_uses = u32::try_from(max_uses)
        .map_err(|_| InvocationLeaseError::new("ledger_identity", "stored max_uses is invalid"))?;
    Ok(Some(LeaseRow {
        token_commitment: *token_commitment,
        issuance_mode,
        lease_id,
        tool_name,
        arguments_sha256,
        target_sha256,
        principal_kind,
        principal_commitment,
        execution_context_kind,
        execution_context_commitment,
        issued_at_unix: issued,
        not_before_unix: not_before,
        expires_at_unix: expires,
        max_uses,
    }))
}

fn evaluate_ledger(ledger: &LedgerIdentity, request: &EvaluationRequest) -> LeaseResult<()> {
    let mut connection = open_existing(ledger)?;
    let transaction = connection
        .transaction_with_behavior(TransactionBehavior::Immediate)
        .map_err(|_| {
            InvocationLeaseError::new(
                "ledger_indeterminate",
                "lease consumption write ownership is indeterminate",
            )
        })?;
    // BEGIN IMMEDIATE is the consumption serialization point. Production
    // re-reads the clock here instead of trusting the earlier request-entry
    // sample; tests may inject the boundary instant deterministically.
    let effective_now = if request.consume {
        #[cfg(test)]
        if let Some(now) = request.linearized_now_override {
            now
        } else {
            unix_now()?
        }
        #[cfg(not(test))]
        {
            unix_now()?
        }
    } else {
        request.now_unix
    };
    validate_schema(
        &transaction,
        &ledger.generation_id,
        &ledger.verify_public_key,
    )?;
    let row = read_lease_row(&transaction, &request.token_commitment)?.ok_or_else(|| {
        InvocationLeaseError::new("unknown_lease", "lease token is not recognized")
    })?;
    UnparsedPublicKey::new(&ED25519, ledger.verify_public_key)
        .verify(
            &signature_message(
                &request.token_nonce,
                &row,
                &ledger.generation_id,
                &ledger.verify_public_key,
            ),
            &request.token_signature,
        )
        .map_err(|_| {
            InvocationLeaseError::new(
                "invalid_signature",
                "lease token was not signed by the externally pinned issuer key",
            )
        })?;
    if row.issuance_mode != request.required_issuance_mode {
        return Err(InvocationLeaseError::new(
            "issuance_mode_mismatch",
            "lease was not issued for the authorizer's current evaluation mode",
        ));
    }
    if row.issued_at_unix < 0
        || row.not_before_unix < row.issued_at_unix
        || row.expires_at_unix <= row.not_before_unix
        || row.expires_at_unix - row.not_before_unix > MAX_INVOCATION_LEASE_TTL_SECS as i64
        || !(1..=MAX_INVOCATION_LEASE_USES).contains(&row.max_uses)
    {
        return Err(InvocationLeaseError::new(
            "ledger_identity",
            "stored lease violates the closed time/use profile",
        ));
    }
    if effective_now < row.not_before_unix {
        return Err(InvocationLeaseError::new(
            "not_yet_valid",
            "lease validity window has not started",
        ));
    }
    if effective_now >= row.expires_at_unix {
        return Err(InvocationLeaseError::new(
            "expired",
            "lease validity window has ended",
        ));
    }
    let revoked: bool = transaction
        .query_row(
            &format!("SELECT EXISTS(SELECT 1 FROM {REVOCATION_TABLE} WHERE token_commitment=?1)"),
            [request.token_commitment.as_slice()],
            |result| result.get(0),
        )
        .map_err(|_| {
            InvocationLeaseError::new("ledger_indeterminate", "cannot inspect revocation state")
        })?;
    if revoked {
        return Err(InvocationLeaseError::new("revoked", "lease was revoked"));
    }
    if row.tool_name != request.tool_name
        || row.arguments_sha256 != request.arguments_sha256
        || row.target_sha256 != request.target_sha256
    {
        return Err(InvocationLeaseError::new(
            "scope_mismatch",
            "tool, normalized target, or canonical arguments differ from the issued scope",
        ));
    }
    if row.principal_kind != request.required_principal_kind {
        return Err(InvocationLeaseError::new(
            "principal_mismatch",
            format!(
                "transport requires a {}-bound lease; bearer downgrade is not permitted",
                request.required_principal_kind
            ),
        ));
    }
    match row.principal_kind.as_str() {
        "bearer" if row.principal_commitment.is_none() => {}
        "oauth" | "unix_uid" => {
            let Some((observed_kind, observed_commitment)) = &request.observed_principal else {
                return Err(InvocationLeaseError::new(
                    "missing_principal",
                    "lease requires a transport-verified principal",
                ));
            };
            if observed_kind != &row.principal_kind
                || row.principal_commitment.as_ref() != Some(observed_commitment)
            {
                return Err(InvocationLeaseError::new(
                    "principal_mismatch",
                    "transport-verified principal differs from the issued scope",
                ));
            }
        }
        _ => {
            return Err(InvocationLeaseError::new(
                "ledger_identity",
                "stored principal profile is invalid",
            ));
        }
    }
    match (
        row.execution_context_kind.as_deref(),
        row.execution_context_commitment.as_ref(),
    ) {
        (None, None) if request.require_execution_context_binding => {
            return Err(InvocationLeaseError::new(
                "execution_context_required",
                "the finalized MCP guard requires a connection-bound lease",
            ));
        }
        (None, None) => {}
        (Some(MCP_STDIO_CONNECTION_CONTEXT_KIND), Some(expected_commitment)) => {
            let Some(LeaseExecutionContext::McpStdioConnection(observed_commitment)) =
                &request.observed_execution_context
            else {
                return Err(InvocationLeaseError::new(
                    "missing_execution_context",
                    "lease requires the exact server-attested MCP stdio connection context",
                ));
            };
            if observed_commitment != expected_commitment {
                return Err(InvocationLeaseError::new(
                    "execution_context_mismatch",
                    "server-attested execution context differs from the issued scope",
                ));
            }
        }
        _ => {
            return Err(InvocationLeaseError::new(
                "ledger_identity",
                "stored execution context profile is outside the closed schema",
            ));
        }
    }
    let uses: i64 = transaction
        .query_row(
            &format!("SELECT COUNT(*) FROM {CONSUMPTION_TABLE} WHERE token_commitment=?1"),
            [request.token_commitment.as_slice()],
            |result| result.get(0),
        )
        .map_err(|_| {
            InvocationLeaseError::new("ledger_indeterminate", "cannot count lease consumptions")
        })?;
    if uses < 0 || uses >= i64::from(row.max_uses) {
        return Err(InvocationLeaseError::new(
            "exhausted",
            "lease use budget is exhausted",
        ));
    }
    if !request.consume {
        transaction.rollback().map_err(|_| {
            InvocationLeaseError::new(
                "ledger_indeterminate",
                "shadow verification rollback is indeterminate",
            )
        })?;
        return Ok(());
    }
    let inserted = transaction
        .execute(
            &format!(
                "INSERT INTO {CONSUMPTION_TABLE}
                 (token_commitment,use_index,scope_sha256,call_id,consumed_at_unix)
                 VALUES(?1,?2,?3,?4,?5)"
            ),
            params![
                request.token_commitment.as_slice(),
                uses + 1,
                scope_commitment(&row).as_slice(),
                request.call_id,
                effective_now,
            ],
        )
        .map_err(|_| {
            InvocationLeaseError::new(
                "replay_or_indeterminate",
                "lease consumption insert failed closed",
            )
        })?;
    if inserted != 1 {
        return Err(InvocationLeaseError::new(
            "ledger_indeterminate",
            "lease consumption returned an impossible row count",
        ));
    }
    transaction.commit().map_err(|_| {
        InvocationLeaseError::new(
            "ledger_indeterminate",
            "lease consumption commit result is indeterminate",
        )
    })
}

#[cfg(test)]
mod tests {
    use super::*;
    use ab_mcp::{
        McpTool, RegistryFinalization, ToolCallGuard, ToolRegistryBuilder, ToolResult, ToolSchema,
    };
    use std::sync::Arc;

    struct HoldSentinelTool {
        executions: Arc<AtomicU64>,
    }

    #[async_trait]
    impl McpTool for HoldSentinelTool {
        fn name(&self) -> &'static str {
            "new_effect_after_inventory"
        }

        fn schema(&self) -> ToolSchema {
            ToolSchema {
                name: self.name().into(),
                description: "test-only uninventoried effect sentinel".into(),
                input_schema: json!({"type": "object"}),
            }
        }

        async fn execute(
            &self,
            _args: Value,
            _context: &ToolContext,
        ) -> ab_core::Result<ToolResult> {
            self.executions.fetch_add(1, Ordering::SeqCst);
            Ok(ToolResult::text("effect executed"))
        }
    }

    struct TestAuthority {
        _directory: tempfile::TempDir,
        database: PathBuf,
        generation: String,
        verify_key: String,
        authorizer: InvocationLeaseAuthorizer,
        issuer: InvocationLeaseIssuer,
    }

    fn authority(mode: InvocationLeaseMode) -> TestAuthority {
        let directory = tempfile::tempdir().expect("temp authority directory");
        let database = directory.path().join("invocation-leases.db");
        let provisioned = ProvisionedInvocationLeaseAuthority::provision(&database, mode, &[])
            .expect("provision exact-call ledger");
        TestAuthority {
            _directory: directory,
            database,
            generation: provisioned.generation_hex,
            verify_key: provisioned.verify_key_hex,
            authorizer: provisioned.authorizer,
            issuer: provisioned.issuer,
        }
    }

    #[test]
    fn guard_policy_commits_the_non_secret_ledger_trust_root() {
        let first = authority(InvocationLeaseMode::Enforce);
        let second = authority(InvocationLeaseMode::Enforce);
        let first_policy = first
            .authorizer
            .mcp_guard(SecurityPolicy::default())
            .policy_snapshot();
        let first_again = first
            .authorizer
            .mcp_guard(SecurityPolicy::default())
            .policy_snapshot();
        let second_policy = second
            .authorizer
            .mcp_guard(SecurityPolicy::default())
            .policy_snapshot();

        let first_commitment = &first_policy["ledger_trust_root_commitment_sha256"];
        assert!(first_commitment.is_string());
        assert_eq!(
            first_commitment,
            &first_again["ledger_trust_root_commitment_sha256"]
        );
        assert_ne!(
            first_commitment,
            &second_policy["ledger_trust_root_commitment_sha256"]
        );
        assert_ne!(
            ledger_trust_root_commitment(&[1; 32], &[3; 32]),
            ledger_trust_root_commitment(&[2; 32], &[3; 32]),
            "generation changes must alter the commitment"
        );
        assert_ne!(
            ledger_trust_root_commitment(&[1; 32], &[3; 32]),
            ledger_trust_root_commitment(&[1; 32], &[4; 32]),
            "verify-key changes must alter the commitment"
        );
        assert!(InvocationLeaseAuthorizer::off()
            .mcp_guard(SecurityPolicy::default())
            .policy_snapshot()["ledger_trust_root_commitment_sha256"]
            .is_null());
    }

    async fn authorize_bearer_at(
        authority: &InvocationLeaseAuthorizer,
        tool: &str,
        arguments: &Value,
        metadata: &Value,
        now: i64,
    ) -> LeaseResult<()> {
        authority
            .authorize(tool, arguments, Some(metadata), None, "bearer", now)
            .await
    }

    async fn authorize_bearer_with_execution_context_at(
        authority: &InvocationLeaseAuthorizer,
        tool: &str,
        arguments: &Value,
        metadata: &Value,
        execution_context: Option<LeaseExecutionContext>,
        now: i64,
    ) -> LeaseResult<()> {
        authority
            .authorize_with_execution_context(
                tool,
                arguments,
                Some(metadata),
                None,
                execution_context,
                "bearer",
                now,
            )
            .await
    }

    async fn authorize_bearer_with_strict_execution_context_at(
        authority: &InvocationLeaseAuthorizer,
        tool: &str,
        arguments: &Value,
        metadata: &Value,
        execution_context: LeaseExecutionContext,
        now: i64,
    ) -> LeaseResult<()> {
        authority
            .authorize_with_execution_context_requirement(
                tool,
                arguments,
                Some(metadata),
                None,
                Some(execution_context),
                "bearer",
                now,
                true,
                true,
            )
            .await
    }

    #[tokio::test]
    async fn off_is_backward_compatible_and_recovery_controls_are_open() {
        let authority = InvocationLeaseAuthorizer::off();
        authority
            .authorize(
                "shell_exec",
                &json!({"cmd":"true"}),
                None,
                None,
                "bearer",
                10,
            )
            .await
            .expect("off mode permits legacy call");
        for recovery in ["agent_kill", "mobile_projection_stop"] {
            assert!(!authority.requires_lease(recovery));
        }
        assert!(authority.requires_lease("browser_close_page"));
        assert!(authority.requires_lease("agent_steer_kill"));
        assert!(authority.requires_lease("oz_run_cancel"));
        assert!(authority.requires_lease("osc_parse"));
        assert!(authority.requires_lease("osc.parse"));
    }

    #[tokio::test]
    async fn canonical_key_order_matches_and_one_shot_replay_is_rejected() {
        let authority = authority(InvocationLeaseMode::Enforce);
        let issued = authority
            .issuer
            .issue_exact(
                LeasePrincipal::Bearer,
                "shell_exec",
                &json!({"cmd":"printf ok", "env":{"B":"2", "A":"1"}}),
                60,
                1,
            )
            .await
            .unwrap();
        let metadata = issued.authorization_meta();
        let reordered = json!({"env":{"A":"1", "B":"2"}, "cmd":"printf ok"});
        let now = unix_now().unwrap();
        authorize_bearer_at(
            &authority.authorizer,
            "shell_exec",
            &reordered,
            &metadata,
            now,
        )
        .await
        .expect("JCS ordering is stable");
        let replay = authorize_bearer_at(
            &authority.authorizer,
            "shell_exec",
            &reordered,
            &metadata,
            now,
        )
        .await
        .expect_err("second use rejected");
        assert_eq!(replay.code(), "exhausted");
    }

    #[tokio::test]
    async fn wrong_scope_does_not_consume_the_exact_grant() {
        let authority = authority(InvocationLeaseMode::Enforce);
        let exact = json!({"cmd":"printf exact", "cwd":"/tmp"});
        let issued = authority
            .issuer
            .issue_exact(LeasePrincipal::Bearer, "shell_exec", &exact, 60, 1)
            .await
            .unwrap();
        let metadata = issued.authorization_meta();
        let now = unix_now().unwrap();
        let wrong_tool = authorize_bearer_at(
            &authority.authorizer,
            "system_control",
            &exact,
            &metadata,
            now,
        )
        .await
        .unwrap_err();
        assert_eq!(wrong_tool.code(), "scope_mismatch");
        let wrong_target = authorize_bearer_at(
            &authority.authorizer,
            "shell_exec",
            &json!({"cmd":"printf exact", "cwd":"/var"}),
            &metadata,
            now,
        )
        .await
        .unwrap_err();
        assert_eq!(wrong_target.code(), "scope_mismatch");
        let mismatch = authorize_bearer_at(
            &authority.authorizer,
            "shell_exec",
            &json!({"cmd":"printf changed", "cwd":"/tmp"}),
            &metadata,
            now,
        )
        .await
        .unwrap_err();
        assert_eq!(mismatch.code(), "scope_mismatch");
        authorize_bearer_at(&authority.authorizer, "shell_exec", &exact, &metadata, now)
            .await
            .expect("mismatch did not consume");
    }

    #[tokio::test]
    async fn exact_connection_binding_rejects_missing_and_wrong_without_consuming() {
        let authority = authority(InvocationLeaseMode::Enforce);
        let args = json!({"cmd":"printf connection-bound", "cwd":"/tmp"});
        let expected = LeaseExecutionContext::mcp_stdio_connection_from_hex(&"11".repeat(32))
            .expect("strict connection commitment");
        let wrong = LeaseExecutionContext::mcp_stdio_connection_from_hex(&"22".repeat(32))
            .expect("strict connection commitment");
        let issued = authority
            .issuer
            .issue_exact_for_execution_context(
                LeasePrincipal::Bearer,
                expected.clone(),
                "shell_exec",
                &args,
                60,
                1,
            )
            .await
            .unwrap();
        let metadata = issued.authorization_meta();
        let now = unix_now().unwrap();

        assert_eq!(
            issued.receipt.schema_version,
            "agent_bridge.effectful_call_lease.v3"
        );
        assert_eq!(
            issued.receipt.execution_context_kind.as_deref(),
            Some(MCP_STDIO_CONNECTION_CONTEXT_KIND)
        );
        assert_eq!(
            issued.receipt.execution_context_commitment.as_deref(),
            Some(expected.commitment_hex().as_str())
        );
        assert!(issued.receipt.execution_context_binding_enforced);
        assert!(!issued.receipt.task_binding_enforced);

        let missing = authorize_bearer_with_execution_context_at(
            &authority.authorizer,
            "shell_exec",
            &args,
            &metadata,
            None,
            now,
        )
        .await
        .expect_err("bound lease requires a server-owned connection context");
        assert_eq!(missing.code(), "missing_execution_context");

        let mismatch = authorize_bearer_with_execution_context_at(
            &authority.authorizer,
            "shell_exec",
            &args,
            &metadata,
            Some(wrong),
            now,
        )
        .await
        .expect_err("a different connection must be rejected");
        assert_eq!(mismatch.code(), "execution_context_mismatch");

        authorize_bearer_with_execution_context_at(
            &authority.authorizer,
            "shell_exec",
            &args,
            &metadata,
            Some(expected),
            now,
        )
        .await
        .expect("connection mismatches did not consume the one-shot lease");
    }

    #[tokio::test]
    async fn finalized_mcp_candidate_requires_a_bound_lease_without_breaking_legacy_helper() {
        let authority = authority(InvocationLeaseMode::Enforce);
        let args = json!({"cmd":"printf strict-connection"});
        let connection = LeaseExecutionContext::McpStdioConnection([0x55; 32]);
        let unbound = authority
            .issuer
            .issue_exact(LeasePrincipal::Bearer, "shell_exec", &args, 60, 1)
            .await
            .unwrap();
        let unbound_meta = unbound.authorization_meta();
        let now = unix_now().unwrap();

        let strict_denial = authorize_bearer_with_strict_execution_context_at(
            &authority.authorizer,
            "shell_exec",
            &args,
            &unbound_meta,
            connection.clone(),
            now,
        )
        .await
        .expect_err("finalized MCP candidate rejects legacy unbound bearer leases");
        assert_eq!(strict_denial.code(), "execution_context_required");

        authorize_bearer_with_execution_context_at(
            &authority.authorizer,
            "shell_exec",
            &args,
            &unbound_meta,
            Some(connection.clone()),
            now,
        )
        .await
        .expect("strict denial did not consume; legacy helper remains migration-compatible");

        let bound = authority
            .issuer
            .issue_exact_for_execution_context(
                LeasePrincipal::Bearer,
                connection.clone(),
                "shell_exec",
                &args,
                60,
                1,
            )
            .await
            .unwrap();
        authorize_bearer_with_strict_execution_context_at(
            &authority.authorizer,
            "shell_exec",
            &args,
            &bound.authorization_meta(),
            connection,
            unix_now().unwrap(),
        )
        .await
        .expect("matching connection-bound lease satisfies finalized MCP strict mode");
    }

    #[tokio::test]
    async fn execution_context_constructor_is_closed_and_scope_signature_covers_binding() {
        let malformed = [String::new(), "11".into(), "1".repeat(63), "gg".repeat(32)];
        for value in &malformed {
            let error = LeaseExecutionContext::mcp_stdio_connection_from_hex(value)
                .expect_err("only exact 64-character hexadecimal commitments are accepted");
            assert_eq!(error.code(), "invalid_execution_context");
        }

        let authority = authority(InvocationLeaseMode::Enforce);
        let args = json!({"cmd":"printf signed-binding"});
        let context = LeaseExecutionContext::McpStdioConnection([0x33; 32]);
        let issued = authority
            .issuer
            .issue_exact_for_execution_context(
                LeasePrincipal::Bearer,
                context,
                "shell_exec",
                &args,
                60,
                1,
            )
            .await
            .unwrap();
        let parsed = decode_token(issued.token.expose_to_trusted_host()).unwrap();
        let mut connection = open_existing(&authority.issuer.ledger).unwrap();
        let transaction = connection
            .transaction_with_behavior(TransactionBehavior::Immediate)
            .unwrap();
        let mut row = read_lease_row(&transaction, &token_commitment(&parsed.nonce))
            .unwrap()
            .unwrap();
        transaction.rollback().unwrap();

        UnparsedPublicKey::new(&ED25519, authority.issuer.ledger.verify_public_key)
            .verify(
                &signature_message(
                    &parsed.nonce,
                    &row,
                    &authority.issuer.ledger.generation_id,
                    &authority.issuer.ledger.verify_public_key,
                ),
                &parsed.signature,
            )
            .expect("stored execution context is covered by the signature");
        row.execution_context_commitment = Some([0x44; 32]);
        assert!(
            UnparsedPublicKey::new(&ED25519, authority.issuer.ledger.verify_public_key)
                .verify(
                    &signature_message(
                        &parsed.nonce,
                        &row,
                        &authority.issuer.ledger.generation_id,
                        &authority.issuer.ledger.verify_public_key,
                    ),
                    &parsed.signature,
                )
                .is_err()
        );
    }

    #[tokio::test]
    async fn unix_rpc_requires_kernel_uid_bound_scope() {
        let authority = authority(InvocationLeaseMode::Enforce);
        let args = json!({"pane":"p1", "keys":"echo safe"});
        let bearer = authority
            .issuer
            .issue_exact(LeasePrincipal::Bearer, "terminal.send_keys", &args, 60, 1)
            .await
            .unwrap();
        let denied = authority
            .authorizer
            .authorize_unix(
                "terminal.send_keys",
                &args,
                Some(1000),
                Some(&bearer.authorization_meta()),
            )
            .await
            .unwrap_err();
        assert_eq!(denied.code(), "principal_mismatch");

        let bound = authority
            .issuer
            .issue_exact(
                LeasePrincipal::UnixUid { uid: 1000 },
                "terminal.send_keys",
                &args,
                60,
                1,
            )
            .await
            .unwrap();
        authority
            .authorizer
            .authorize_unix(
                "terminal.send_keys",
                &args,
                Some(1000),
                Some(&bound.authorization_meta()),
            )
            .await
            .expect("matching kernel uid");
    }

    #[tokio::test]
    async fn oauth_scope_matches_exact_issuer_and_local_subject_without_consuming_mismatch() {
        let authority = authority(InvocationLeaseMode::Enforce);
        let args = json!({"cmd":"printf oauth"});
        let issued = authority
            .issuer
            .issue_exact(
                LeasePrincipal::OAuth {
                    issuer: "https://issuer.example".into(),
                    local_subject: "owner".into(),
                },
                "shell_exec",
                &args,
                60,
                1,
            )
            .await
            .unwrap();
        let metadata = issued.authorization_meta();
        let now = unix_now().unwrap();
        let observed = |issuer: &str, local_subject: &str| {
            let (kind, commitment) = principal_material(&LeasePrincipal::OAuth {
                issuer: issuer.into(),
                local_subject: local_subject.into(),
            })
            .unwrap();
            (kind, commitment.expect("OAuth commitment"))
        };

        let wrong = authority
            .authorizer
            .authorize(
                "shell_exec",
                &args,
                Some(&metadata),
                Some(observed("https://issuer.example", "other-owner")),
                "oauth",
                now,
            )
            .await
            .expect_err("wrong OAuth subject must be rejected");
        assert_eq!(wrong.code(), "principal_mismatch");
        let wrong_issuer = authority
            .authorizer
            .authorize(
                "shell_exec",
                &args,
                Some(&metadata),
                Some(observed("https://other-issuer.example", "owner")),
                "oauth",
                now,
            )
            .await
            .expect_err("wrong OAuth issuer must be rejected");
        assert_eq!(wrong_issuer.code(), "principal_mismatch");

        authority
            .authorizer
            .authorize(
                "shell_exec",
                &args,
                Some(&metadata),
                Some(observed("https://issuer.example", "owner")),
                "oauth",
                now,
            )
            .await
            .expect("exact issuer and local subject match; mismatch did not consume");
    }

    #[tokio::test]
    async fn validity_boundaries_accept_nbf_and_reject_expiry() {
        let authority = authority(InvocationLeaseMode::Enforce);
        let args = json!({"cmd":"true"});
        let issued = authority
            .issuer
            .issue_exact_at(LeasePrincipal::Bearer, "shell_exec", &args, 100, 110, 5, 2)
            .await
            .unwrap();
        let metadata = issued.authorization_meta();
        let early = authorize_bearer_at(&authority.authorizer, "shell_exec", &args, &metadata, 109)
            .await
            .unwrap_err();
        assert_eq!(early.code(), "not_yet_valid");
        authorize_bearer_at(&authority.authorizer, "shell_exec", &args, &metadata, 110)
            .await
            .expect("nbf inclusive");
        let expired =
            authorize_bearer_at(&authority.authorizer, "shell_exec", &args, &metadata, 115)
                .await
                .unwrap_err();
        assert_eq!(expired.code(), "expired");
    }

    #[tokio::test]
    async fn issuance_bounds_multi_use_order_revocation_and_receipt_mode_are_explicit() {
        let enforced = authority(InvocationLeaseMode::Enforce);
        let args = json!({"cmd":"printf bounded"});
        let now = unix_now().unwrap();

        for ttl in [0, MAX_INVOCATION_LEASE_TTL_SECS + 1] {
            let error = enforced
                .issuer
                .issue_exact_at(
                    LeasePrincipal::Bearer,
                    "shell_exec",
                    &args,
                    now,
                    now,
                    ttl,
                    1,
                )
                .await
                .expect_err("TTL outside the closed range must be rejected");
            assert_eq!(error.code(), "invalid_ttl");
        }
        for uses in [0, MAX_INVOCATION_LEASE_USES + 1] {
            let error = enforced
                .issuer
                .issue_exact_at(
                    LeasePrincipal::Bearer,
                    "shell_exec",
                    &args,
                    now,
                    now,
                    60,
                    uses,
                )
                .await
                .expect_err("use count outside the closed range must be rejected");
            assert_eq!(error.code(), "invalid_uses");
        }

        let issued = enforced
            .issuer
            .issue_exact_at(LeasePrincipal::Bearer, "shell_exec", &args, now, now, 60, 2)
            .await
            .unwrap();
        assert!(issued.receipt.grants_authority);
        assert!(issued.receipt.execution_context_kind.is_none());
        assert!(issued.receipt.execution_context_commitment.is_none());
        assert!(!issued.receipt.execution_context_binding_enforced);
        assert!(!issued.receipt.task_binding_enforced);
        assert!(!issued.receipt.same_principal_token_transfer_blocked);
        let metadata = issued.authorization_meta();
        authorize_bearer_at(&enforced.authorizer, "shell_exec", &args, &metadata, now)
            .await
            .expect("first ordered use");
        authorize_bearer_at(&enforced.authorizer, "shell_exec", &args, &metadata, now)
            .await
            .expect("second ordered use");
        let exhausted =
            authorize_bearer_at(&enforced.authorizer, "shell_exec", &args, &metadata, now)
                .await
                .expect_err("third use exceeds max_uses=2");
        assert_eq!(exhausted.code(), "exhausted");

        let revoked = enforced
            .issuer
            .issue_exact(LeasePrincipal::Bearer, "shell_exec", &args, 60, 1)
            .await
            .unwrap();
        enforced
            .issuer
            .revoke(&revoked, "test revocation")
            .await
            .unwrap();
        let revocation_error = authorize_bearer_at(
            &enforced.authorizer,
            "shell_exec",
            &args,
            &revoked.authorization_meta(),
            unix_now().unwrap(),
        )
        .await
        .expect_err("revoked grant must not authorize");
        assert_eq!(revocation_error.code(), "revoked");

        let shadow = authority(InvocationLeaseMode::Shadow);
        let shadow_receipt = shadow
            .issuer
            .issue_exact(LeasePrincipal::Bearer, "shell_exec", &args, 60, 1)
            .await
            .unwrap();
        assert!(
            !shadow_receipt.receipt.grants_authority,
            "Shadow receipts are evaluation material, not execution authority"
        );
    }

    #[tokio::test]
    async fn shadow_issued_token_cannot_be_promoted_to_enforce_authority() {
        let shadow = authority(InvocationLeaseMode::Shadow);
        let args = json!({"cmd":"printf shadow-only"});
        let issued = shadow
            .issuer
            .issue_exact(LeasePrincipal::Bearer, "shell_exec", &args, 60, 1)
            .await
            .unwrap();
        assert_eq!(issued.receipt.issuance_mode, "shadow");
        assert!(!issued.receipt.grants_authority);

        let enforcing = ProvisionedInvocationLeaseAuthority::open_authorizer(
            &shadow.database,
            &shadow.generation,
            &shadow.verify_key,
            InvocationLeaseMode::Enforce,
            &[],
        )
        .unwrap();
        let denied = authorize_bearer_at(
            &enforcing,
            "shell_exec",
            &args,
            &issued.authorization_meta(),
            unix_now().unwrap(),
        )
        .await
        .expect_err("Shadow issuance must never become Enforce authority");
        assert_eq!(denied.code(), "issuance_mode_mismatch");
    }

    #[tokio::test]
    async fn static_agent_ceiling_denies_steer_kill_before_lease_consumption() {
        let authority = authority(InvocationLeaseMode::Enforce);
        let args = json!({"session_id":"ab-agent-owned-test"});
        let issued = authority
            .issuer
            .issue_exact(LeasePrincipal::Bearer, "agent_steer_kill", &args, 60, 1)
            .await
            .unwrap();
        let policy = SecurityPolicy {
            allow_agent_spawn: false,
            ..SecurityPolicy::default()
        };
        let guard = authority.authorizer.mcp_guard(policy);
        let denied = guard
            .authorize_and_consume("agent_steer_kill", &args, &ToolContext::default())
            .await
            .expect_err("static AgentSpawn ceiling must run before lease verification");
        assert!(denied.to_string().contains("AB_ALLOW_AGENT_SPAWN=false"));

        authorize_bearer_at(
            &authority.authorizer,
            "agent_steer_kill",
            &args,
            &issued.authorization_meta(),
            unix_now().unwrap(),
        )
        .await
        .expect("policy denial must not consume the exact lease");
    }

    #[tokio::test(flavor = "multi_thread", worker_threads = 4)]
    async fn concurrent_one_shot_has_exactly_one_winner() {
        let authority = authority(InvocationLeaseMode::Enforce);
        let args = json!({"cmd":"printf winner"});
        let issued = authority
            .issuer
            .issue_exact(LeasePrincipal::Bearer, "shell_exec", &args, 60, 1)
            .await
            .unwrap();
        let metadata = Arc::new(issued.authorization_meta());
        let args = Arc::new(args);
        let now = unix_now().unwrap();
        let mut tasks = Vec::new();
        for _ in 0..8 {
            let authorizer = authority.authorizer.clone();
            let metadata = metadata.clone();
            let args = args.clone();
            tasks.push(tokio::spawn(async move {
                authorize_bearer_at(&authorizer, "shell_exec", &args, &metadata, now)
                    .await
                    .is_ok()
            }));
        }
        let mut winners = 0;
        for task in tasks {
            winners += usize::from(task.await.unwrap());
        }
        assert_eq!(winners, 1);
    }

    #[tokio::test]
    async fn restart_preserves_consumption_tombstone() {
        let authority = authority(InvocationLeaseMode::Enforce);
        let args = json!({"cmd":"true"});
        let issued = authority
            .issuer
            .issue_exact(LeasePrincipal::Bearer, "shell_exec", &args, 60, 1)
            .await
            .unwrap();
        let metadata = issued.authorization_meta();
        let now = unix_now().unwrap();
        authorize_bearer_at(&authority.authorizer, "shell_exec", &args, &metadata, now)
            .await
            .unwrap();
        let reopened = ProvisionedInvocationLeaseAuthority::open_authorizer(
            &authority.database,
            &authority.generation,
            &authority.verify_key,
            InvocationLeaseMode::Enforce,
            &[],
        )
        .unwrap();
        let replay = authorize_bearer_at(&reopened, "shell_exec", &args, &metadata, now)
            .await
            .unwrap_err();
        assert_eq!(replay.code(), "exhausted");
    }

    #[tokio::test]
    async fn shadow_never_consumes_or_blocks() {
        let authority = authority(InvocationLeaseMode::Shadow);
        let args = json!({"cmd":"true"});
        let issued = authority
            .issuer
            .issue_exact(LeasePrincipal::Bearer, "shell_exec", &args, 60, 1)
            .await
            .unwrap();
        let metadata = issued.authorization_meta();
        let now = unix_now().unwrap();
        for _ in 0..2 {
            authorize_bearer_at(&authority.authorizer, "shell_exec", &args, &metadata, now)
                .await
                .expect("shadow permits and does not consume");
        }
        authority
            .authorizer
            .authorize("shell_exec", &args, None, None, "bearer", now)
            .await
            .expect("shadow missing token still permits");
    }

    #[tokio::test]
    async fn token_is_redacted_and_not_stored_raw() {
        let authority = authority(InvocationLeaseMode::Enforce);
        let issued = authority
            .issuer
            .issue_exact(
                LeasePrincipal::Bearer,
                "shell_exec",
                &json!({"cmd":"true"}),
                60,
                1,
            )
            .await
            .unwrap();
        let token = issued.token.expose_to_trusted_host().to_string();
        assert!(!format!("{issued:?}").contains(&token));
        let database = std::fs::read(&authority.database).unwrap();
        assert!(!database
            .windows(token.len())
            .any(|window| window == token.as_bytes()));
    }

    #[tokio::test]
    async fn permission_drift_fails_closed_without_memory_fallback() {
        let authority = authority(InvocationLeaseMode::Enforce);
        let args = json!({"cmd":"true"});
        let issued = authority
            .issuer
            .issue_exact(LeasePrincipal::Bearer, "shell_exec", &args, 60, 1)
            .await
            .unwrap();
        #[cfg(unix)]
        {
            use std::os::unix::fs::PermissionsExt as _;
            std::fs::set_permissions(&authority.database, std::fs::Permissions::from_mode(0o644))
                .unwrap();
            let denied = authorize_bearer_at(
                &authority.authorizer,
                "shell_exec",
                &args,
                &issued.authorization_meta(),
                unix_now().unwrap(),
            )
            .await
            .unwrap_err();
            assert_eq!(denied.code(), "ledger_identity");
        }
    }

    #[tokio::test]
    async fn production_enforce_configuration_is_an_explicit_hold() {
        let (mode, error) = production_runtime_mode(InvocationLeaseMode::Enforce);
        assert_eq!(mode, InvocationLeaseMode::Invalid);
        assert!(error.expect("HOLD reason").contains("independent-UID"));

        let hold = InvocationLeaseAuthorizer::new(
            InvocationLeaseMode::Invalid,
            None,
            default_protected_tools(),
            Some("test HOLD".into()),
        );
        assert!(
            hold.requires_lease("previously_uninventoried_effect"),
            "Invalid/HOLD must default-deny unknown calls at a wired ingress"
        );
        assert!(hold.requires_lease("desktop_confirm"));
        assert!(hold.requires_lease("memory_save"));
        assert!(hold.requires_lease("agent_steer_kill"));
        assert!(hold.requires_lease("oz_run_cancel"));
        assert!(hold.requires_lease("browser_close_page"));
        assert!(!hold.requires_lease("agent_kill"));
        assert!(!hold.requires_lease("mobile_projection_stop"));
        assert!(!hold.requires_lease("capabilities"));
        let denied = hold
            .authorize_mcp(
                "previously_uninventoried_effect",
                &json!({"path": "/tmp/must-not-run"}),
                &ToolContext::default(),
            )
            .await
            .expect_err("Invalid/HOLD rejects unknown calls before dispatch");
        assert_eq!(denied.code(), "invalid_configuration");
        let unix_denied = hold
            .authorize_unix(
                "previously_uninventoried_rpc",
                &json!({"path": "/tmp/must-not-run"}),
                Some(unsafe { libc::geteuid() }),
                None,
            )
            .await
            .expect_err("Invalid/HOLD rejects unknown Unix calls before dispatch");
        assert_eq!(unix_denied.code(), "invalid_configuration");

        let snapshot = hold.snapshot();
        assert_eq!(snapshot["rollout_state"], "hold");
        assert_eq!(snapshot["enforcement_ready"], false);
        assert_eq!(snapshot["fail_closed"], false);
        assert_eq!(
            snapshot["invalid_hold_default_deny_at_guarded_ingress"],
            true
        );
        assert_eq!(snapshot["same_uid_rollback_protected"], false);
        assert_eq!(snapshot["open_fd_fstat_pinned"], false);
        assert_eq!(snapshot["target_binding"]["resolved_runtime_target"], false);
        assert_eq!(snapshot["task_binding_enforced"], false);
        assert_eq!(
            snapshot["finalized_mcp_candidate_requires_execution_context_binding"],
            true
        );
        assert_eq!(snapshot["same_principal_token_transfer_blocked"], false);
        assert_eq!(snapshot["coverage"]["authorizer_gate_requested"], true);
        assert_eq!(
            snapshot["coverage"]["current_process_ingress_attested"],
            false
        );
        assert_eq!(
            InvocationLeaseAuthorizer::off().snapshot()["coverage"]["authorizer_gate_requested"],
            false
        );
    }

    #[tokio::test]
    async fn invalid_hold_denies_uninventoried_registry_effect_before_inner() {
        let hold = InvocationLeaseAuthorizer::new(
            InvocationLeaseMode::Invalid,
            None,
            default_protected_tools(),
            Some("test HOLD".into()),
        );
        let executions = Arc::new(AtomicU64::new(0));
        let mut registry = ToolRegistryBuilder::new();
        registry.register(Box::new(HoldSentinelTool {
            executions: executions.clone(),
        }));
        let registry = registry.finalize_with(|_| {
            RegistryFinalization::new(
                Arc::new(hold.mcp_guard(SecurityPolicy::default())),
                json!({ "test": "invalid_hold_unknown_effect" }),
            )
        });

        let result = registry
            .invoke(
                "new_effect_after_inventory",
                json!({"path": "/tmp/must-not-run"}),
                &ToolContext::default(),
            )
            .await
            .expect("sentinel registered")
            .expect("guard returns MCP error result");

        assert!(result.is_error);
        assert!(result.content.iter().any(|block| match block {
            ab_mcp::ContentBlock::Text { text } => text.contains("invalid_configuration"),
            _ => false,
        }));
        assert_eq!(
            executions.load(Ordering::SeqCst),
            0,
            "Invalid/HOLD must deny an unknown effect before the inner tool runs"
        );
    }

    #[tokio::test]
    async fn finalized_inventory_guard_defaults_unknown_names_to_required() {
        let authority = authority(InvocationLeaseMode::Enforce);
        let guard = authority.authorizer.mcp_guard_for_inventory(
            SecurityPolicy::default(),
            BTreeSet::new(),
            "sha256:test-finalized-inventory",
        );
        assert_eq!(
            guard.inventory_digest(),
            Some("sha256:test-finalized-inventory")
        );
        let denied = guard
            .authorize_and_consume(
                "new_effect_after_inventory",
                &json!({"path":"/tmp/must-not-run"}),
                &ToolContext::default(),
            )
            .await
            .expect_err("empty independently reviewed exemption set denies unknown tools");
        assert!(denied.to_string().contains("unverified_transport"));
        assert_eq!(
            authority.authorizer.inner.checked.load(Ordering::Relaxed),
            1
        );

        // This proves only the explicit review mechanism. Production callers
        // must not derive this set from MCP annotations or effect labels.
        let reviewed_exempt = BTreeSet::from(["new_effect_after_inventory".to_string()]);
        let reviewed_guard = authority.authorizer.mcp_guard_for_inventory(
            SecurityPolicy::default(),
            reviewed_exempt,
            "sha256:test-independent-review",
        );
        reviewed_guard
            .authorize_and_consume(
                "new_effect_after_inventory",
                &json!({"path":"/tmp/reviewed-only"}),
                &ToolContext::default(),
            )
            .await
            .expect("an explicit independent-review exemption bypasses lease evaluation");
        assert_eq!(
            authority.authorizer.inner.checked.load(Ordering::Relaxed),
            1
        );
    }

    #[tokio::test]
    async fn invalid_hold_ignores_even_an_explicit_inventory_exemption() {
        let hold = InvocationLeaseAuthorizer::new(
            InvocationLeaseMode::Invalid,
            None,
            default_protected_tools(),
            Some("test HOLD".into()),
        );
        let broad_exemption = BTreeSet::from(["new_effect_after_inventory".to_string()]);
        let guard = hold.mcp_guard_for_inventory(
            SecurityPolicy::default(),
            broad_exemption,
            "sha256:test-not-trusted-by-hold",
        );
        let denied = guard
            .authorize_and_consume(
                "new_effect_after_inventory",
                &json!({"path":"/tmp/must-not-run"}),
                &ToolContext::default(),
            )
            .await
            .expect_err("Invalid/HOLD accepts only its hard-coded diagnostic/recovery set");
        assert!(denied.to_string().contains("invalid_configuration"));
    }

    #[tokio::test]
    async fn attacker_inserted_row_with_wrong_signature_is_rejected() {
        let authority = authority(InvocationLeaseMode::Enforce);
        let args = json!({"cmd":"printf forged", "cwd":"/tmp"});
        let now = unix_now().unwrap();
        let nonce = [0x41_u8; TOKEN_NONCE_BYTES];
        let (principal_kind, principal_commitment) =
            principal_material(&LeasePrincipal::Bearer).unwrap();
        let row = LeaseRow {
            token_commitment: token_commitment(&nonce),
            issuance_mode: "enforce".into(),
            lease_id: "lease-attacker-selected".into(),
            tool_name: "shell_exec".into(),
            arguments_sha256: canonical_arguments_sha256(&args).unwrap(),
            target_sha256: domain_hash(
                b"agent_bridge.invocation_lease.target.v1",
                normalized_target("shell_exec", &args).as_bytes(),
            ),
            principal_kind,
            principal_commitment,
            execution_context_kind: None,
            execution_context_commitment: None,
            issued_at_unix: now,
            not_before_unix: now,
            expires_at_unix: now + 60,
            max_uses: 1,
        };
        let wrong_key = generate_signing_key().unwrap();
        let wrong_verify_key = public_key_bytes(&wrong_key).unwrap();
        let wrong_signature = wrong_key.sign(&signature_message(
            &nonce,
            &row,
            &authority.issuer.ledger.generation_id,
            &wrong_verify_key,
        ));
        insert_lease(&authority.issuer.ledger, &row).unwrap();

        let mut raw_token = [0_u8; TOKEN_BYTES];
        raw_token[..TOKEN_NONCE_BYTES].copy_from_slice(&nonce);
        raw_token[TOKEN_NONCE_BYTES..].copy_from_slice(wrong_signature.as_ref());
        let metadata = json!({
            LEASE_META_KEY: {
                "schema": LEASE_REF_SCHEMA,
                "token": format!("{TOKEN_PREFIX}{}", URL_SAFE_NO_PAD.encode(raw_token))
            }
        });
        let denied =
            authorize_bearer_at(&authority.authorizer, "shell_exec", &args, &metadata, now)
                .await
                .unwrap_err();
        assert_eq!(denied.code(), "invalid_signature");
    }

    #[cfg(unix)]
    #[tokio::test]
    async fn replacing_ledger_with_same_bytes_but_new_inode_is_rejected() {
        use std::os::unix::fs::PermissionsExt as _;

        let authority = authority(InvocationLeaseMode::Enforce);
        let args = json!({"cmd":"true"});
        let issued = authority
            .issuer
            .issue_exact(LeasePrincipal::Bearer, "shell_exec", &args, 60, 1)
            .await
            .unwrap();
        let old_path = authority.database.with_extension("old-inode");
        std::fs::rename(&authority.database, &old_path).unwrap();
        std::fs::copy(&old_path, &authority.database).unwrap();
        std::fs::set_permissions(&authority.database, std::fs::Permissions::from_mode(0o600))
            .unwrap();

        let denied = authorize_bearer_at(
            &authority.authorizer,
            "shell_exec",
            &args,
            &issued.authorization_meta(),
            unix_now().unwrap(),
        )
        .await
        .unwrap_err();
        assert_eq!(denied.code(), "ledger_identity");
    }

    #[tokio::test]
    async fn no_op_trigger_body_drift_is_rejected_by_exact_ddl_pin() {
        let authority = authority(InvocationLeaseMode::Enforce);
        let args = json!({"cmd":"true"});
        let issued = authority
            .issuer
            .issue_exact(LeasePrincipal::Bearer, "shell_exec", &args, 60, 1)
            .await
            .unwrap();
        let connection = Connection::open(&authority.database).unwrap();
        connection
            .execute_batch(
                "DROP TRIGGER invocation_leases_v0_no_delete;
                 CREATE TRIGGER invocation_leases_v0_no_delete
                 BEFORE DELETE ON invocation_leases_v0 BEGIN SELECT 1; END;",
            )
            .unwrap();
        drop(connection);

        let denied = authorize_bearer_at(
            &authority.authorizer,
            "shell_exec",
            &args,
            &issued.authorization_meta(),
            unix_now().unwrap(),
        )
        .await
        .unwrap_err();
        assert_eq!(denied.code(), "ledger_identity");
    }

    #[tokio::test]
    async fn bearer_cannot_downgrade_an_oauth_required_transport() {
        let authority = authority(InvocationLeaseMode::Enforce);
        let args = json!({"cmd":"true"});
        let issued = authority
            .issuer
            .issue_exact(LeasePrincipal::Bearer, "shell_exec", &args, 60, 1)
            .await
            .unwrap();
        let denied = authority
            .authorizer
            .authorize(
                "shell_exec",
                &args,
                Some(&issued.authorization_meta()),
                Some(("oauth".into(), [7_u8; 32])),
                "oauth",
                unix_now().unwrap(),
            )
            .await
            .unwrap_err();
        assert_eq!(denied.code(), "principal_mismatch");
    }

    #[tokio::test]
    async fn expiry_is_rechecked_at_consumption_linearization() {
        let authority = authority(InvocationLeaseMode::Enforce);
        let args = json!({"cmd":"true"});
        let issued = authority
            .issuer
            .issue_exact_at(LeasePrincipal::Bearer, "shell_exec", &args, 100, 100, 5, 1)
            .await
            .unwrap();
        let parsed = decode_token(issued.token.expose_to_trusted_host()).unwrap();
        let ledger = authority.authorizer.inner.ledger.clone().unwrap();
        let mut request = EvaluationRequest {
            token_commitment: token_commitment(&parsed.nonce),
            token_nonce: parsed.nonce,
            token_signature: parsed.signature,
            tool_name: "shell_exec".into(),
            arguments_sha256: canonical_arguments_sha256(&args).unwrap(),
            target_sha256: domain_hash(
                b"agent_bridge.invocation_lease.target.v1",
                normalized_target("shell_exec", &args).as_bytes(),
            ),
            observed_principal: None,
            observed_execution_context: None,
            require_execution_context_binding: false,
            required_principal_kind: "bearer",
            required_issuance_mode: "enforce",
            now_unix: 104,
            call_id: "call-expiry-linearization".into(),
            consume: true,
            linearized_now_override: Some(105),
        };
        let denied = evaluate_ledger(&ledger, &request).unwrap_err();
        assert_eq!(denied.code(), "expired");

        request.call_id = "call-before-expiry".into();
        request.linearized_now_override = Some(104);
        evaluate_ledger(&ledger, &request).expect("expiry denial did not consume");
    }

    #[tokio::test]
    async fn signed_token_cannot_be_copied_to_a_different_ledger_generation() {
        let authority = authority(InvocationLeaseMode::Enforce);
        let args = json!({"cmd":"printf generation-bound"});
        let issued = authority
            .issuer
            .issue_exact(LeasePrincipal::Bearer, "shell_exec", &args, 60, 1)
            .await
            .unwrap();
        let parsed = decode_token(issued.token.expose_to_trusted_host()).unwrap();
        let receipt = &issued.receipt;
        let copied_row = LeaseRow {
            token_commitment: token_commitment(&parsed.nonce),
            issuance_mode: receipt.issuance_mode.into(),
            lease_id: receipt.lease_id.clone(),
            tool_name: receipt.tool_name.clone(),
            arguments_sha256: canonical_arguments_sha256(&args).unwrap(),
            target_sha256: domain_hash(
                b"agent_bridge.invocation_lease.target.v1",
                normalized_target("shell_exec", &args).as_bytes(),
            ),
            principal_kind: "bearer".into(),
            principal_commitment: None,
            execution_context_kind: None,
            execution_context_commitment: None,
            issued_at_unix: receipt.issued_at_unix,
            not_before_unix: receipt.not_before_unix,
            expires_at_unix: receipt.expires_at_unix,
            max_uses: receipt.max_uses,
        };

        let second_directory = tempfile::tempdir().unwrap();
        let second_database = second_directory.path().join("second-generation.db");
        let mut second_generation = decode_hex_32(&authority.generation).unwrap();
        second_generation[0] ^= 0xff;
        let verify_key = decode_hex_32(&authority.verify_key).unwrap();
        provision_ledger(&second_database, second_generation, verify_key).unwrap();
        let second_ledger =
            Arc::new(pin_existing_ledger(&second_database, second_generation, verify_key).unwrap());
        insert_lease(&second_ledger, &copied_row).unwrap();
        let second_authorizer = InvocationLeaseAuthorizer::new(
            InvocationLeaseMode::Enforce,
            Some(second_ledger),
            default_protected_tools(),
            None,
        );
        let denied = authorize_bearer_at(
            &second_authorizer,
            "shell_exec",
            &args,
            &issued.authorization_meta(),
            unix_now().unwrap(),
        )
        .await
        .unwrap_err();
        assert_eq!(denied.code(), "invalid_signature");
    }

    #[tokio::test]
    async fn shadow_unknown_transport_preflight_never_blocks() {
        let authority = authority(InvocationLeaseMode::Shadow);
        authority
            .authorizer
            .authorize_mcp(
                "shell_exec",
                &json!({"cmd":"true"}),
                &ToolContext::default(),
            )
            .await
            .expect("shadow converts unverified transport into a would-deny verdict");
        assert_eq!(
            authority.authorizer.snapshot()["counters"]["shadow_would_deny"],
            1
        );
    }
}
