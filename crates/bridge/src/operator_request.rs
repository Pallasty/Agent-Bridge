//! Private, non-executing operator-request queue for external MCP clients.
//!
//! A staged request is immutable. A local-only CLI may append exactly one
//! approve/reject decision, but approval is evidence for a future executor
//! review, never authority to execute by itself.

use crate::agent_task_contract::{
    preview_agent_task_contract, AgentTaskContract, AgentTaskContractPreview, AuthorityBoundary,
};
use ab_store::default_db_path;
use anyhow::{anyhow, bail, Context, Result};
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use std::collections::BTreeSet;
use std::fs::{self, OpenOptions};
use std::io::Write;
use std::path::{Path, PathBuf};
use std::str::FromStr;
use std::time::{SystemTime, UNIX_EPOCH};
use uuid::Uuid;

pub const OPERATOR_REQUEST_SCHEMA_V0: &str = "agent_bridge.operator_request.v0";
pub const OPERATOR_DECISION_SCHEMA_V0: &str = "agent_bridge.operator_decision.v0";
pub const OPERATOR_REQUEST_DIR_ENV: &str = "AGENT_BRIDGE_OPERATOR_REQUEST_DIR";
pub const CHATGPT_COLLAB_CHANNEL_ENV: &str = "AGENT_BRIDGE_CHATGPT_COLLAB_CHANNEL";
pub const CHATGPT_COLLAB_CAPABILITIES_ENV: &str = "AGENT_BRIDGE_CHATGPT_COLLAB_CAPABILITIES";
pub const DEFAULT_REQUEST_TTL_SECS: u64 = 600;
pub const MIN_REQUEST_TTL_SECS: u64 = 60;
pub const MAX_REQUEST_TTL_SECS: u64 = 3_600;
const MAX_SUMMARY_CHARS: usize = 2_000;
const MAX_TARGET_CHARS: usize = 1_024;
const MAX_SOURCE_CHARS: usize = 128;
const MAX_TOOLSET_CHARS: usize = 128;
const MAX_SESSION_CHARS: usize = 256;
const MAX_CONTRACT_BYTES: usize = 64 * 1024;
const MAX_REQUESTS_PER_HOUR: usize = 30;
const MAX_REQUEST_RECORDS: usize = 5_000;

#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum OperatorCapability {
    WorkMemoryWrite,
    ForumPost,
    ProjectWrite,
    ExternalWrite,
    RuntimeEnablement,
}

impl OperatorCapability {
    pub fn as_str(self) -> &'static str {
        match self {
            Self::WorkMemoryWrite => "work_memory_write",
            Self::ForumPost => "forum_post",
            Self::ProjectWrite => "project_write",
            Self::ExternalWrite => "external_write",
            Self::RuntimeEnablement => "runtime_enablement",
        }
    }

    fn authority_boundary(self) -> AuthorityBoundary {
        match self {
            Self::WorkMemoryWrite | Self::ForumPost | Self::ProjectWrite => {
                AuthorityBoundary::ProjectWrite
            }
            Self::ExternalWrite => AuthorityBoundary::ExternalWrite,
            Self::RuntimeEnablement => AuthorityBoundary::RuntimeEnablement,
        }
    }
}

impl FromStr for OperatorCapability {
    type Err = anyhow::Error;

    fn from_str(value: &str) -> Result<Self> {
        match normalize_name(value).as_str() {
            "work-memory-write" => Ok(Self::WorkMemoryWrite),
            "forum-post" => Ok(Self::ForumPost),
            "project-write" => Ok(Self::ProjectWrite),
            "external-write" => Ok(Self::ExternalWrite),
            "runtime-enablement" => Ok(Self::RuntimeEnablement),
            _ => bail!("unsupported operator capability: {value}"),
        }
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum OperatorDecision {
    Approve,
    Reject,
}

impl OperatorDecision {
    pub fn as_str(self) -> &'static str {
        match self {
            Self::Approve => "approve",
            Self::Reject => "reject",
        }
    }
}

impl FromStr for OperatorDecision {
    type Err = anyhow::Error;

    fn from_str(value: &str) -> Result<Self> {
        match normalize_name(value).as_str() {
            "approve" | "approved" => Ok(Self::Approve),
            "reject" | "rejected" => Ok(Self::Reject),
            _ => bail!("decision must be approve or reject"),
        }
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct OperatorRequestInput {
    pub requested_capability: OperatorCapability,
    pub target: String,
    pub summary: String,
    #[serde(default = "default_request_ttl_secs")]
    pub ttl_secs: u64,
    pub contract: AgentTaskContract,
}

fn default_request_ttl_secs() -> u64 {
    DEFAULT_REQUEST_TTL_SECS
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct OperatorRequestRecord {
    pub schema: String,
    pub request_id: String,
    pub request_digest: String,
    pub source: String,
    pub toolset: String,
    pub channel_id: String,
    pub session_id: Option<String>,
    pub identity_strength: String,
    pub requested_capability: OperatorCapability,
    pub target: String,
    pub summary: String,
    pub created_at: u64,
    pub expires_at: u64,
    pub contract_preview: AgentTaskContractPreview,
    pub execution_performed: bool,
    pub canonical_write_performed: bool,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct OperatorDecisionRecord {
    pub schema: String,
    pub request_id: String,
    pub request_digest: String,
    pub decision_digest: String,
    pub decision: OperatorDecision,
    pub operator_id: String,
    pub reason: String,
    pub decided_at: u64,
    pub approval_scope: String,
    pub execution_allowed: bool,
    pub requires_separate_executor_gate: bool,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct OperatorRequestView {
    pub status: String,
    pub request: OperatorRequestRecord,
    pub decision: Option<OperatorDecisionRecord>,
    pub execution_allowed: bool,
    pub next_step: String,
}

#[derive(Debug, Clone)]
pub struct OperatorRequestStore {
    root: PathBuf,
}

impl Default for OperatorRequestStore {
    fn default() -> Self {
        Self::new(default_operator_request_dir())
    }
}

impl OperatorRequestStore {
    pub fn new(root: PathBuf) -> Self {
        Self { root }
    }

    pub fn root(&self) -> &Path {
        &self.root
    }

    pub fn stage(
        &self,
        input: OperatorRequestInput,
        channel_id: &str,
        session_id: Option<&str>,
        source: &str,
        toolset: &str,
        allowed_capabilities: &BTreeSet<OperatorCapability>,
    ) -> Result<OperatorRequestView> {
        validate_channel_id(channel_id)?;
        validate_text("target", &input.target, MAX_TARGET_CHARS)?;
        validate_text("summary", &input.summary, MAX_SUMMARY_CHARS)?;
        let source = normalized_nonempty(source, "unknown");
        let toolset = normalized_nonempty(toolset, "unknown");
        validate_text("source", &source, MAX_SOURCE_CHARS)?;
        validate_text("toolset", &toolset, MAX_TOOLSET_CHARS)?;
        let session_id = session_id
            .map(str::trim)
            .filter(|value| !value.is_empty())
            .map(ToOwned::to_owned);
        if let Some(session_id) = session_id.as_deref() {
            validate_text("session_id", session_id, MAX_SESSION_CHARS)?;
        }
        if !(MIN_REQUEST_TTL_SECS..=MAX_REQUEST_TTL_SECS).contains(&input.ttl_secs) {
            bail!("ttl_secs must be in {MIN_REQUEST_TTL_SECS}..={MAX_REQUEST_TTL_SECS}");
        }
        if !allowed_capabilities.contains(&input.requested_capability) {
            bail!(
                "requested capability {} is not allowlisted by {}",
                input.requested_capability.as_str(),
                CHATGPT_COLLAB_CAPABILITIES_ENV
            );
        }

        let contract_bytes = serde_json::to_vec(&input.contract)?;
        if contract_bytes.len() > MAX_CONTRACT_BYTES {
            bail!("contract exceeds {MAX_CONTRACT_BYTES} bytes");
        }
        let preview = preview_agent_task_contract(input.contract.clone());
        if preview.status != "ready" {
            bail!(
                "agent task contract is blocked: {} violation(s)",
                preview.violations.len()
            );
        }
        let required_boundary = input.requested_capability.authority_boundary();
        if input.contract.authority_boundary != required_boundary {
            bail!(
                "authority boundary mismatch: {} requires {:?}, contract requested {:?}",
                input.requested_capability.as_str(),
                required_boundary,
                input.contract.authority_boundary
            );
        }

        self.ensure_layout()?;
        let now = now_secs();
        let existing = self.request_records()?;
        if existing.len() >= MAX_REQUEST_RECORDS {
            bail!("operator request store reached the {MAX_REQUEST_RECORDS}-record safety cap");
        }
        let recent = existing
            .iter()
            .filter(|record| record.created_at >= now.saturating_sub(3_600))
            .count();
        if recent >= MAX_REQUESTS_PER_HOUR {
            bail!("operator request rate limit reached ({MAX_REQUESTS_PER_HOUR}/hour)");
        }

        let request_id = Uuid::new_v4().to_string();
        let identity_strength = if session_id.is_some() {
            "channel_and_client_session"
        } else {
            "channel_only"
        };
        let expires_at = now.saturating_add(input.ttl_secs);
        let request_digest = request_digest(
            &request_id,
            &source,
            &toolset,
            channel_id,
            session_id.as_deref(),
            now,
            expires_at,
            input.requested_capability,
            &input.target,
            &input.summary,
            &input.contract,
        )?;
        let record = OperatorRequestRecord {
            schema: OPERATOR_REQUEST_SCHEMA_V0.to_string(),
            request_id: request_id.clone(),
            request_digest,
            source,
            toolset,
            channel_id: channel_id.trim().to_string(),
            session_id,
            identity_strength: identity_strength.to_string(),
            requested_capability: input.requested_capability,
            target: input.target.trim().to_string(),
            summary: input.summary.trim().to_string(),
            created_at: now,
            expires_at,
            contract_preview: preview,
            execution_performed: false,
            canonical_write_performed: false,
        };
        write_json_create_new(&self.request_path(&request_id)?, &record)?;
        self.view_for(record)
    }

    pub fn get(&self, request_id: &str) -> Result<OperatorRequestView> {
        let expected_id = canonical_request_id(request_id)?;
        let path = self.request_path(&expected_id)?;
        let body =
            fs::read(&path).with_context(|| format!("read operator request {}", path.display()))?;
        let record: OperatorRequestRecord = serde_json::from_slice(&body)
            .with_context(|| format!("parse operator request {}", path.display()))?;
        validate_request_record(&record, &expected_id)?;
        self.view_for(record)
    }

    pub fn list(&self, limit: usize) -> Result<Vec<OperatorRequestView>> {
        self.ensure_layout()?;
        let mut records = self.request_records()?;
        records.sort_by(|left, right| {
            right
                .created_at
                .cmp(&left.created_at)
                .then_with(|| right.request_id.cmp(&left.request_id))
        });
        records
            .into_iter()
            .take(limit.clamp(1, 500))
            .map(|record| self.view_for(record))
            .collect()
    }

    pub fn decide(
        &self,
        request_id: &str,
        decision: OperatorDecision,
        operator_id: &str,
        reason: &str,
    ) -> Result<OperatorRequestView> {
        validate_text("operator_id", operator_id, 256)?;
        validate_text("reason", reason, 2_000)?;
        let current = self.get(request_id)?;
        if current.status != "pending" {
            bail!(
                "request {} is {}, not pending",
                current.request.request_id,
                current.status
            );
        }
        let decided_at = now_secs();
        if decided_at >= current.request.expires_at {
            bail!(
                "request {} expired before decision",
                current.request.request_id
            );
        }
        let operator_id = operator_id.trim().to_string();
        let reason = reason.trim().to_string();
        let decision_digest = decision_digest(
            &current.request.request_id,
            &current.request.request_digest,
            decision,
            &operator_id,
            &reason,
            decided_at,
        )?;
        let decision_record = OperatorDecisionRecord {
            schema: OPERATOR_DECISION_SCHEMA_V0.to_string(),
            request_id: current.request.request_id.clone(),
            request_digest: current.request.request_digest.clone(),
            decision_digest,
            decision,
            operator_id,
            reason,
            decided_at,
            approval_scope: "request_evidence_only".to_string(),
            execution_allowed: false,
            requires_separate_executor_gate: true,
        };
        write_json_create_new(
            &self.decision_path(&current.request.request_id)?,
            &decision_record,
        )?;
        self.get(&current.request.request_id)
    }

    fn ensure_layout(&self) -> Result<()> {
        ensure_private_dir(&self.root)?;
        ensure_private_dir(&self.requests_dir())?;
        ensure_private_dir(&self.decisions_dir())?;
        Ok(())
    }

    fn requests_dir(&self) -> PathBuf {
        self.root.join("requests")
    }

    fn decisions_dir(&self) -> PathBuf {
        self.root.join("decisions")
    }

    fn request_path(&self, request_id: &str) -> Result<PathBuf> {
        Ok(self
            .requests_dir()
            .join(format!("{}.json", canonical_request_id(request_id)?)))
    }

    fn decision_path(&self, request_id: &str) -> Result<PathBuf> {
        Ok(self
            .decisions_dir()
            .join(format!("{}.json", canonical_request_id(request_id)?)))
    }

    fn request_records(&self) -> Result<Vec<OperatorRequestRecord>> {
        let mut records = Vec::new();
        for entry in fs::read_dir(self.requests_dir())? {
            let entry = entry?;
            if entry.path().extension().and_then(|value| value.to_str()) != Some("json") {
                continue;
            }
            let path = entry.path();
            let body = fs::read(&path)?;
            let record: OperatorRequestRecord = serde_json::from_slice(&body)?;
            let expected_id = path
                .file_stem()
                .and_then(|value| value.to_str())
                .ok_or_else(|| anyhow!("operator request filename is not UTF-8"))?;
            validate_request_record(&record, expected_id)?;
            records.push(record);
        }
        Ok(records)
    }

    fn view_for(&self, request: OperatorRequestRecord) -> Result<OperatorRequestView> {
        let decision = match fs::read(self.decision_path(&request.request_id)?) {
            Ok(body) => {
                let decision = serde_json::from_slice::<OperatorDecisionRecord>(&body)?;
                validate_decision_record(&decision, &request)?;
                Some(decision)
            }
            Err(error) if error.kind() == std::io::ErrorKind::NotFound => None,
            Err(error) => return Err(error.into()),
        };
        let status = match decision.as_ref().map(|record| record.decision) {
            Some(OperatorDecision::Approve) => "approved_for_executor_review",
            Some(OperatorDecision::Reject) => "rejected",
            None if now_secs() >= request.expires_at => "expired",
            None => "pending",
        };
        let next_step = match status {
            "pending" => "A local operator may approve or reject this exact digest.",
            "approved_for_executor_review" => {
                "A separate, not-yet-implemented executor gate must revalidate the exact digest."
            }
            "rejected" => "No execution or canonical write is allowed.",
            _ => "Stage a new bounded request; expired requests cannot be revived.",
        };
        Ok(OperatorRequestView {
            status: status.to_string(),
            request,
            decision,
            execution_allowed: false,
            next_step: next_step.to_string(),
        })
    }
}

pub fn default_operator_request_dir() -> PathBuf {
    if let Some(path) = std::env::var(OPERATOR_REQUEST_DIR_ENV)
        .ok()
        .map(|value| value.trim().to_string())
        .filter(|value| !value.is_empty())
    {
        return PathBuf::from(path);
    }
    default_db_path()
        .parent()
        .unwrap_or_else(|| Path::new("."))
        .join("operator-requests")
}

pub fn configured_chatgpt_collab_channel() -> Option<String> {
    std::env::var(CHATGPT_COLLAB_CHANNEL_ENV)
        .ok()
        .map(|value| value.trim().to_string())
        .filter(|value| validate_channel_id(value).is_ok())
}

pub fn configured_chatgpt_collab_capabilities() -> BTreeSet<OperatorCapability> {
    std::env::var(CHATGPT_COLLAB_CAPABILITIES_ENV)
        .ok()
        .into_iter()
        .flat_map(|value| {
            value
                .split(',')
                .map(str::trim)
                .filter(|item| !item.is_empty())
                .filter_map(|item| OperatorCapability::from_str(item).ok())
                .collect::<Vec<_>>()
        })
        .collect()
}

fn request_digest(
    request_id: &str,
    source: &str,
    toolset: &str,
    channel_id: &str,
    session_id: Option<&str>,
    created_at: u64,
    expires_at: u64,
    capability: OperatorCapability,
    target: &str,
    summary: &str,
    contract: &AgentTaskContract,
) -> Result<String> {
    #[derive(Serialize)]
    struct DigestMaterial<'a> {
        schema: &'static str,
        request_id: &'a str,
        source: &'a str,
        toolset: &'a str,
        channel_id: &'a str,
        session_id: Option<&'a str>,
        created_at: u64,
        expires_at: u64,
        requested_capability: OperatorCapability,
        target: &'a str,
        summary: &'a str,
        contract: &'a AgentTaskContract,
    }
    let bytes = serde_json::to_vec(&DigestMaterial {
        schema: OPERATOR_REQUEST_SCHEMA_V0,
        request_id,
        source,
        toolset,
        channel_id: channel_id.trim(),
        session_id,
        created_at,
        expires_at,
        requested_capability: capability,
        target: target.trim(),
        summary: summary.trim(),
        contract,
    })?;
    Ok(format!("{:x}", Sha256::digest(bytes)))
}

fn decision_digest(
    request_id: &str,
    request_digest: &str,
    decision: OperatorDecision,
    operator_id: &str,
    reason: &str,
    decided_at: u64,
) -> Result<String> {
    #[derive(Serialize)]
    struct DigestMaterial<'a> {
        schema: &'static str,
        request_id: &'a str,
        request_digest: &'a str,
        decision: OperatorDecision,
        operator_id: &'a str,
        reason: &'a str,
        decided_at: u64,
        approval_scope: &'static str,
        execution_allowed: bool,
        requires_separate_executor_gate: bool,
    }
    let bytes = serde_json::to_vec(&DigestMaterial {
        schema: OPERATOR_DECISION_SCHEMA_V0,
        request_id,
        request_digest,
        decision,
        operator_id,
        reason,
        decided_at,
        approval_scope: "request_evidence_only",
        execution_allowed: false,
        requires_separate_executor_gate: true,
    })?;
    Ok(format!("{:x}", Sha256::digest(bytes)))
}

fn validate_request_record(record: &OperatorRequestRecord, expected_id: &str) -> Result<()> {
    if record.schema != OPERATOR_REQUEST_SCHEMA_V0 {
        bail!("unsupported operator request schema");
    }
    let canonical_id = canonical_request_id(&record.request_id)?;
    if canonical_id != canonical_request_id(expected_id)? {
        bail!("operator request id does not match its record path");
    }
    validate_channel_id(&record.channel_id)?;
    validate_text("source", &record.source, MAX_SOURCE_CHARS)?;
    validate_text("toolset", &record.toolset, MAX_TOOLSET_CHARS)?;
    validate_text("target", &record.target, MAX_TARGET_CHARS)?;
    validate_text("summary", &record.summary, MAX_SUMMARY_CHARS)?;
    if let Some(session_id) = record.session_id.as_deref() {
        validate_text("session_id", session_id, MAX_SESSION_CHARS)?;
    }
    if record.expires_at <= record.created_at {
        bail!("operator request expiry is invalid");
    }
    if record.execution_performed || record.canonical_write_performed {
        bail!("operator request record claims a forbidden side effect");
    }
    let expected_identity = if record.session_id.is_some() {
        "channel_and_client_session"
    } else {
        "channel_only"
    };
    if record.identity_strength != expected_identity {
        bail!("operator request identity strength is inconsistent");
    }
    let preview = preview_agent_task_contract(record.contract_preview.contract.clone());
    if preview.status != "ready" || preview != record.contract_preview {
        bail!("operator request contract preview failed integrity validation");
    }
    if record.contract_preview.contract.authority_boundary
        != record.requested_capability.authority_boundary()
    {
        bail!("operator request authority boundary is inconsistent");
    }
    let expected_digest = request_digest(
        &record.request_id,
        &record.source,
        &record.toolset,
        &record.channel_id,
        record.session_id.as_deref(),
        record.created_at,
        record.expires_at,
        record.requested_capability,
        &record.target,
        &record.summary,
        &record.contract_preview.contract,
    )?;
    if record.request_digest != expected_digest {
        bail!("operator request digest mismatch");
    }
    Ok(())
}

fn validate_decision_record(
    decision: &OperatorDecisionRecord,
    request: &OperatorRequestRecord,
) -> Result<()> {
    if decision.schema != OPERATOR_DECISION_SCHEMA_V0
        || decision.request_id != request.request_id
        || decision.request_digest != request.request_digest
    {
        bail!("operator decision does not match the request");
    }
    validate_text("operator_id", &decision.operator_id, 256)?;
    validate_text("reason", &decision.reason, 2_000)?;
    if decision.decided_at >= request.expires_at {
        bail!("operator decision was recorded after request expiry");
    }
    if decision.approval_scope != "request_evidence_only"
        || decision.execution_allowed
        || !decision.requires_separate_executor_gate
    {
        bail!("operator decision exceeds the P1 evidence-only boundary");
    }
    let expected_digest = decision_digest(
        &decision.request_id,
        &decision.request_digest,
        decision.decision,
        &decision.operator_id,
        &decision.reason,
        decision.decided_at,
    )?;
    if decision.decision_digest != expected_digest {
        bail!("operator decision digest mismatch");
    }
    Ok(())
}

fn validate_channel_id(value: &str) -> Result<()> {
    let trimmed = value.trim();
    if trimmed.is_empty() || trimmed.len() > 128 {
        bail!("collaboration channel id must contain 1..=128 ASCII characters");
    }
    if !trimmed
        .chars()
        .all(|character| character.is_ascii_alphanumeric() || "._:-".contains(character))
    {
        bail!("collaboration channel id contains unsupported characters");
    }
    Ok(())
}

fn validate_text(field: &str, value: &str, max_chars: usize) -> Result<()> {
    let trimmed = value.trim();
    if trimmed.is_empty() {
        bail!("{field} must be non-empty");
    }
    if trimmed.chars().count() > max_chars {
        bail!("{field} exceeds {max_chars} characters");
    }
    if trimmed.chars().any(char::is_control) {
        bail!("{field} contains control characters");
    }
    Ok(())
}

fn canonical_request_id(value: &str) -> Result<String> {
    Uuid::parse_str(value.trim())
        .map(|id| id.to_string())
        .map_err(|_| anyhow!("invalid operator request id"))
}

fn normalize_name(value: &str) -> String {
    value
        .trim()
        .to_ascii_lowercase()
        .replace('_', "-")
        .replace(' ', "-")
}

fn normalized_nonempty(value: &str, fallback: &str) -> String {
    let value = value.trim();
    if value.is_empty() {
        fallback.to_string()
    } else {
        value.to_string()
    }
}

fn now_secs() -> u64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap_or_default()
        .as_secs()
}

fn ensure_private_dir(path: &Path) -> Result<()> {
    fs::create_dir_all(path).with_context(|| format!("create {}", path.display()))?;
    #[cfg(unix)]
    {
        use std::os::unix::fs::PermissionsExt;
        fs::set_permissions(path, fs::Permissions::from_mode(0o700))?;
    }
    Ok(())
}

fn write_json_create_new<T: Serialize>(path: &Path, value: &T) -> Result<()> {
    let parent = path
        .parent()
        .ok_or_else(|| anyhow!("operator request path has no parent"))?;
    ensure_private_dir(parent)?;
    let body = serde_json::to_vec_pretty(value)?;
    let mut options = OpenOptions::new();
    options.create_new(true).write(true);
    #[cfg(unix)]
    {
        use std::os::unix::fs::OpenOptionsExt;
        options.mode(0o600);
    }
    let mut file = options
        .open(path)
        .with_context(|| format!("create immutable record {}", path.display()))?;
    file.write_all(&body)?;
    file.write_all(b"\n")?;
    file.sync_all()?;
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::agent_task_contract::{ParentEvidenceRef, ParentEvidenceVerdict};
    use std::collections::BTreeMap;

    fn contract(boundary: AuthorityBoundary) -> AgentTaskContract {
        AgentTaskContract {
            schema_version: crate::agent_task_contract::AGENT_TASK_CONTRACT_SCHEMA_V0.to_string(),
            contract_id: "chatgpt-collab-test".to_string(),
            revision: 1,
            objective: "Stage a bounded collaboration request".to_string(),
            parent_evidence_refs: vec![ParentEvidenceRef {
                reference: "owner-reviewed-boundary".to_string(),
                verdict: ParentEvidenceVerdict::Accepted,
                authority_boundary: boundary,
            }],
            this_attempt_only: vec!["stage request evidence".to_string()],
            reserved_actions: vec!["execute request".to_string()],
            continuity_locks: BTreeMap::new(),
            allowed_changes: vec!["private operator queue".to_string()],
            acceptance_criteria: vec!["no execution occurs".to_string()],
            authority_boundary: boundary,
            attempt_no: 1,
            attempt_budget: 1,
            changed_variable: Some("request queue".to_string()),
            planned_state: BTreeMap::new(),
            observed_state: BTreeMap::new(),
        }
    }

    fn allowed(capability: OperatorCapability) -> BTreeSet<OperatorCapability> {
        BTreeSet::from([capability])
    }

    #[test]
    fn stages_private_non_executing_request_and_decides_once() {
        let temp = tempfile::tempdir().unwrap();
        let store = OperatorRequestStore::new(temp.path().join("queue"));
        let staged = store
            .stage(
                OperatorRequestInput {
                    requested_capability: OperatorCapability::ProjectWrite,
                    target: "/tmp/project".to_string(),
                    summary: "Prepare a reversible patch".to_string(),
                    ttl_secs: 600,
                    contract: contract(AuthorityBoundary::ProjectWrite),
                },
                "chatgpt-desktop",
                Some("conversation-1"),
                "chatgpt",
                "chatgpt-collab",
                &allowed(OperatorCapability::ProjectWrite),
            )
            .unwrap();
        assert_eq!(staged.status, "pending");
        assert_eq!(
            staged.request.identity_strength,
            "channel_and_client_session"
        );
        assert!(!staged.execution_allowed);
        assert!(!staged.request.execution_performed);
        assert!(!staged.request.canonical_write_performed);

        #[cfg(unix)]
        {
            use std::os::unix::fs::PermissionsExt;
            let request_path = store.request_path(&staged.request.request_id).unwrap();
            assert_eq!(
                fs::metadata(store.root()).unwrap().permissions().mode() & 0o777,
                0o700
            );
            assert_eq!(
                fs::metadata(request_path).unwrap().permissions().mode() & 0o777,
                0o600
            );
        }

        let approved = store
            .decide(
                &staged.request.request_id,
                OperatorDecision::Approve,
                "local-owner",
                "Evidence is bounded",
            )
            .unwrap();
        assert_eq!(approved.status, "approved_for_executor_review");
        assert!(!approved.execution_allowed);
        assert!(!approved.decision.as_ref().unwrap().execution_allowed);
        assert!(
            approved
                .decision
                .as_ref()
                .unwrap()
                .requires_separate_executor_gate
        );
        assert!(store
            .decide(
                &staged.request.request_id,
                OperatorDecision::Reject,
                "local-owner",
                "Replay should fail",
            )
            .is_err());
    }

    #[test]
    fn authority_and_capability_allowlists_fail_closed() {
        let temp = tempfile::tempdir().unwrap();
        let store = OperatorRequestStore::new(temp.path().join("queue"));
        let mismatched = store.stage(
            OperatorRequestInput {
                requested_capability: OperatorCapability::ExternalWrite,
                target: "remote service".to_string(),
                summary: "Request external mutation".to_string(),
                ttl_secs: 600,
                contract: contract(AuthorityBoundary::ProjectWrite),
            },
            "chatgpt-desktop",
            None,
            "chatgpt",
            "chatgpt-collab",
            &allowed(OperatorCapability::ExternalWrite),
        );
        assert!(mismatched
            .unwrap_err()
            .to_string()
            .contains("authority boundary mismatch"));

        let denied = store.stage(
            OperatorRequestInput {
                requested_capability: OperatorCapability::ProjectWrite,
                target: "/tmp/project".to_string(),
                summary: "Request project mutation".to_string(),
                ttl_secs: 600,
                contract: contract(AuthorityBoundary::ProjectWrite),
            },
            "chatgpt-desktop",
            None,
            "chatgpt",
            "chatgpt-collab",
            &BTreeSet::new(),
        );
        assert!(denied.unwrap_err().to_string().contains("not allowlisted"));
        assert!(!store.root().exists());
    }

    #[test]
    fn request_ids_are_path_safe_and_channel_identity_is_honest() {
        let temp = tempfile::tempdir().unwrap();
        let store = OperatorRequestStore::new(temp.path().join("queue"));
        assert!(store.get("../../secret").is_err());
        let staged = store
            .stage(
                OperatorRequestInput {
                    requested_capability: OperatorCapability::ForumPost,
                    target: "forum-thread:146".to_string(),
                    summary: "Propose a reply".to_string(),
                    ttl_secs: 600,
                    contract: contract(AuthorityBoundary::ProjectWrite),
                },
                "chatgpt-desktop",
                None,
                "chatgpt",
                "chatgpt-collab",
                &allowed(OperatorCapability::ForumPost),
            )
            .unwrap();
        assert_eq!(staged.request.identity_strength, "channel_only");
        assert_eq!(store.list(10).unwrap().len(), 1);
    }

    #[test]
    fn request_and_decision_tampering_fail_closed() {
        let temp = tempfile::tempdir().unwrap();
        let store = OperatorRequestStore::new(temp.path().join("request-queue"));
        let staged = store
            .stage(
                OperatorRequestInput {
                    requested_capability: OperatorCapability::ProjectWrite,
                    target: "/tmp/project".to_string(),
                    summary: "Prepare a reversible patch".to_string(),
                    ttl_secs: 600,
                    contract: contract(AuthorityBoundary::ProjectWrite),
                },
                "chatgpt-desktop",
                None,
                "chatgpt",
                "chatgpt-collab",
                &allowed(OperatorCapability::ProjectWrite),
            )
            .unwrap();
        let request_path = store.request_path(&staged.request.request_id).unwrap();
        let mut request_json: serde_json::Value =
            serde_json::from_slice(&fs::read(&request_path).unwrap()).unwrap();
        request_json["target"] = serde_json::Value::String("/tmp/other".to_string());
        fs::write(
            &request_path,
            serde_json::to_vec_pretty(&request_json).unwrap(),
        )
        .unwrap();
        assert!(store
            .get(&staged.request.request_id)
            .unwrap_err()
            .to_string()
            .contains("digest mismatch"));

        let decision_store = OperatorRequestStore::new(temp.path().join("decision-queue"));
        let staged = decision_store
            .stage(
                OperatorRequestInput {
                    requested_capability: OperatorCapability::ForumPost,
                    target: "forum-thread:146".to_string(),
                    summary: "Propose a bounded reply".to_string(),
                    ttl_secs: 600,
                    contract: contract(AuthorityBoundary::ProjectWrite),
                },
                "chatgpt-desktop",
                None,
                "chatgpt",
                "chatgpt-collab",
                &allowed(OperatorCapability::ForumPost),
            )
            .unwrap();
        decision_store
            .decide(
                &staged.request.request_id,
                OperatorDecision::Approve,
                "local-owner",
                "Reviewed exact request",
            )
            .unwrap();
        let decision_path = decision_store
            .decision_path(&staged.request.request_id)
            .unwrap();
        let mut decision_json: serde_json::Value =
            serde_json::from_slice(&fs::read(&decision_path).unwrap()).unwrap();
        decision_json["reason"] = serde_json::Value::String("Changed later".to_string());
        fs::write(
            &decision_path,
            serde_json::to_vec_pretty(&decision_json).unwrap(),
        )
        .unwrap();
        assert!(decision_store
            .get(&staged.request.request_id)
            .unwrap_err()
            .to_string()
            .contains("decision digest mismatch"));
    }
}
