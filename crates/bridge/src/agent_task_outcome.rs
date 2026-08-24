//! Privacy-minimal claims about the outcome of a bounded agent task.
//!
//! The claim intentionally contains no objective text, transcript, error text,
//! paths, commands, or evidence payloads.  Callers may bind evidence only by a
//! SHA-256 digest.  This module models a dedicated outcome-ledger row; lifecycle
//! and semantic-event records are deliberately not accepted.  Aggregation is
//! fail closed: malformed rows and conflicting retries are counted but never
//! contribute to outcome totals.

use std::collections::{BTreeMap, BTreeSet};

use ab_store::AgentTaskOutcomeRecord;
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};

pub const AGENT_TASK_OUTCOME_SCHEMA_V1: &str = "agent_bridge.agent_task_outcome.v1";

const MAX_IDENTIFIER_BYTES: usize = 128;
const MAX_EVIDENCE_DIGESTS: usize = 16;
const MAX_COUNTER_VALUE: u32 = 1_000;
const MAX_AGGREGATE_SUMMARIES: usize = 1_024;
const MAX_REVISION: u64 = 1_000_000;
const MAX_RECORDED_AT_SECS: i64 = 253_402_300_799;

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum AgentTaskOutcomeStatus {
    Achieved,
    PartiallyAchieved,
    Blocked,
    Abandoned,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum AgentTaskOutcomeVerification {
    Verified,
    NotVerified,
    Unknown,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum AgentTaskOutcomeVerificationMethod {
    Tests,
    Postcondition,
    OwnerConfirmation,
    Mixed,
    None,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum AgentTaskUserAcceptance {
    Unknown,
    Accepted,
    Corrected,
    Rejected,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum AgentTaskAcceptanceProvenance {
    Unavailable,
    OwnerExplicit,
    OwnerCorrection,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum AgentTaskOutcomeProvenance {
    AgentReported,
    HarnessVerified,
    OwnerAttested,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum AgentTaskRollbackStatus {
    NotNeeded,
    Available,
    Completed,
    Failed,
    Unknown,
}

impl AgentTaskOutcomeStatus {
    fn as_str(self) -> &'static str {
        match self {
            Self::Achieved => "achieved",
            Self::PartiallyAchieved => "partially_achieved",
            Self::Blocked => "blocked",
            Self::Abandoned => "abandoned",
        }
    }
}

impl AgentTaskOutcomeVerification {
    fn as_str(self) -> &'static str {
        match self {
            Self::Verified => "verified",
            Self::NotVerified => "not_verified",
            Self::Unknown => "unknown",
        }
    }
}

impl AgentTaskOutcomeVerificationMethod {
    fn as_str(self) -> &'static str {
        match self {
            Self::Tests => "tests",
            Self::Postcondition => "postcondition",
            Self::OwnerConfirmation => "owner_confirmation",
            Self::Mixed => "mixed",
            Self::None => "none",
        }
    }
}

impl AgentTaskUserAcceptance {
    fn as_str(self) -> &'static str {
        match self {
            Self::Unknown => "unknown",
            Self::Accepted => "accepted",
            Self::Corrected => "corrected",
            Self::Rejected => "rejected",
        }
    }
}

impl AgentTaskAcceptanceProvenance {
    fn as_str(self) -> &'static str {
        match self {
            Self::Unavailable => "unavailable",
            Self::OwnerExplicit => "owner_explicit",
            Self::OwnerCorrection => "owner_correction",
        }
    }
}

impl AgentTaskOutcomeProvenance {
    fn as_str(self) -> &'static str {
        match self {
            Self::AgentReported => "agent_reported",
            Self::HarnessVerified => "harness_verified",
            Self::OwnerAttested => "owner_attested",
        }
    }
}

impl AgentTaskRollbackStatus {
    fn as_str(self) -> &'static str {
        match self {
            Self::NotNeeded => "not_needed",
            Self::Available => "available",
            Self::Completed => "completed",
            Self::Failed => "failed",
            Self::Unknown => "unknown",
        }
    }
}

#[derive(Debug, Clone, Copy, Default, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct AgentTaskOperatorCounts {
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub manual_interventions: Option<u32>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub owner_restatements: Option<u32>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub repeated_authorization_prompts: Option<u32>,
}

/// A bounded outcome claim.  IDs are opaque correlation handles, not labels.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct AgentTaskOutcome {
    pub schema_version: String,
    pub outcome_id: String,
    pub contract_id: String,
    pub revision: u64,
    pub status: AgentTaskOutcomeStatus,
    pub verification: AgentTaskOutcomeVerification,
    pub verification_method: AgentTaskOutcomeVerificationMethod,
    pub user_acceptance: AgentTaskUserAcceptance,
    pub acceptance_provenance: AgentTaskAcceptanceProvenance,
    /// Closed rollback disposition.  The claim deliberately does not retain
    /// rollback commands, paths, or operator commentary.
    pub rollback_status: AgentTaskRollbackStatus,
    pub provenance: AgentTaskOutcomeProvenance,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub agent_id: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub body_id: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub environment_id: Option<String>,
    #[serde(default)]
    pub evidence_sha256: Vec<String>,
    #[serde(default)]
    pub counts: AgentTaskOperatorCounts,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct AgentTaskOutcomeViolation {
    pub code: String,
    pub field: String,
}

/// A digest-free projection safe for routine reports and aggregate samples.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct AgentTaskOutcomeSummary {
    pub outcome_id: String,
    pub contract_id: String,
    pub revision: u64,
    pub status: AgentTaskOutcomeStatus,
    pub verification: AgentTaskOutcomeVerification,
    pub verification_method: AgentTaskOutcomeVerificationMethod,
    pub user_acceptance: AgentTaskUserAcceptance,
    pub acceptance_provenance: AgentTaskAcceptanceProvenance,
    pub rollback_status: AgentTaskRollbackStatus,
    pub provenance: AgentTaskOutcomeProvenance,
    pub evidence_digest_count: usize,
    pub counts: AgentTaskOperatorCounts,
}

#[derive(Debug, Clone, Copy, Default, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct AgentTaskOutcomeStatusCounts {
    pub achieved: u64,
    pub partially_achieved: u64,
    pub blocked: u64,
    pub abandoned: u64,
}

#[derive(Debug, Clone, Copy, Default, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct AgentTaskOutcomeVerificationCounts {
    pub verified: u64,
    pub not_verified: u64,
    pub unknown: u64,
}

#[derive(Debug, Clone, Copy, Default, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct AgentTaskUserAcceptanceCounts {
    pub unknown: u64,
    pub accepted: u64,
    pub corrected: u64,
    pub rejected: u64,
}

#[derive(Debug, Clone, Copy, Default, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct AgentTaskRollbackStatusCounts {
    pub not_needed: u64,
    pub available: u64,
    pub completed: u64,
    pub failed: u64,
    pub unknown: u64,
}

#[derive(Debug, Clone, Copy, Default, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct AgentTaskOperatorCountTotals {
    pub manual_interventions: u64,
    pub owner_restatements: u64,
    pub repeated_authorization_prompts: u64,
}

#[derive(Debug, Clone, Copy, Default, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct AgentTaskOperatorCountCoverage {
    pub manual_interventions: u64,
    pub owner_restatements: u64,
    pub repeated_authorization_prompts: u64,
}

#[derive(Debug, Clone, Copy, Default, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct AgentTaskOutcomeProvenanceCounts {
    pub agent_reported: u64,
    pub harness_verified: u64,
    pub owner_attested: u64,
}

/// Aggregate over the one immutable, non-conflicting claim for each outcome ID.
///
/// `status_counts.achieved` remains a count of claims.  Consumers that require
/// evidence-backed claim must use `reported_verified_achieved_count`; a
/// lifecycle finalization event can contribute to neither count.
#[derive(Debug, Clone, Default, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct AgentTaskOutcomeAggregate {
    pub input_record_count: usize,
    pub accepted_outcome_count: usize,
    pub invalid_record_count: usize,
    pub duplicate_retry_count: usize,
    pub conflicting_outcome_count: usize,
    pub conflicting_record_count: usize,
    pub truncated_summary_count: usize,
    pub reported_verified_achieved_count: u64,
    pub reported_owner_accepted_achieved_count: u64,
    pub rollback_counts: AgentTaskRollbackStatusCounts,
    pub status_counts: AgentTaskOutcomeStatusCounts,
    pub verification_counts: AgentTaskOutcomeVerificationCounts,
    pub user_acceptance_counts: AgentTaskUserAcceptanceCounts,
    pub operator_counts: AgentTaskOperatorCountTotals,
    pub operator_count_coverage: AgentTaskOperatorCountCoverage,
    pub provenance_counts: AgentTaskOutcomeProvenanceCounts,
    pub summaries: Vec<AgentTaskOutcomeSummary>,
}

impl AgentTaskOutcome {
    /// Validate the fixed schema and all bounded/privacy-minimal fields.
    pub fn validate(&self) -> Result<(), Vec<AgentTaskOutcomeViolation>> {
        let violations = agent_task_outcome_violations(self);
        if violations.is_empty() {
            Ok(())
        } else {
            Err(violations)
        }
    }

    /// Admission policy for the public `session_finalize` producer.
    ///
    /// MCP session hints are not owner or harness authentication, so this
    /// route may persist only an agent-reported claim. Trusted harness and
    /// owner provenance remain reserved for a future authenticated producer.
    pub fn validate_agent_reported_admission(&self) -> Result<(), Vec<AgentTaskOutcomeViolation>> {
        let mut violations = agent_task_outcome_violations(self);
        if self.provenance != AgentTaskOutcomeProvenance::AgentReported {
            violations.push(violation("untrusted_transport_provenance", "provenance"));
        }
        if self.user_acceptance != AgentTaskUserAcceptance::Unknown
            || self.acceptance_provenance != AgentTaskAcceptanceProvenance::Unavailable
        {
            violations.push(violation(
                "untrusted_transport_acceptance",
                "user_acceptance",
            ));
        }
        if matches!(
            self.verification_method,
            AgentTaskOutcomeVerificationMethod::OwnerConfirmation
                | AgentTaskOutcomeVerificationMethod::Mixed
        ) {
            violations.push(violation(
                "untrusted_transport_verification_method",
                "verification_method",
            ));
        }
        if violations.is_empty() {
            Ok(())
        } else {
            Err(violations)
        }
    }

    /// Construct a canonical validated row for the dedicated outcome ledger.
    /// `recorded_at_secs` is transport metadata and is intentionally excluded
    /// from the idempotency digest. Caller-provided session hints are not
    /// persisted in the outcome ledger.
    pub fn to_store_record(
        &self,
        recorded_at_secs: i64,
    ) -> Result<AgentTaskOutcomeRecord, Vec<AgentTaskOutcomeViolation>> {
        self.validate()?;
        if !(0..=MAX_RECORDED_AT_SECS).contains(&recorded_at_secs) {
            return Err(vec![violation("recorded_at_out_of_bounds", "recorded_at")]);
        }
        let mut canonical_claim = self.clone();
        canonical_claim.evidence_sha256.sort_unstable();
        let record_sha256 = canonical_claim_sha256(&canonical_claim)?;
        Ok(AgentTaskOutcomeRecord {
            schema_version: AGENT_TASK_OUTCOME_SCHEMA_V1.to_string(),
            outcome_id: canonical_claim.outcome_id.clone(),
            recorded_at: recorded_at_secs,
            contract_id: canonical_claim.contract_id.clone(),
            contract_revision: canonical_claim.revision,
            status: canonical_claim.status.as_str().to_string(),
            verification_status: canonical_claim.verification.as_str().to_string(),
            verification_method: canonical_claim.verification_method.as_str().to_string(),
            evidence_sha256: canonical_claim.evidence_sha256.clone(),
            user_acceptance: canonical_claim.user_acceptance.as_str().to_string(),
            acceptance_provenance: canonical_claim.acceptance_provenance.as_str().to_string(),
            manual_interventions: canonical_claim.counts.manual_interventions,
            owner_restatements: canonical_claim.counts.owner_restatements,
            repeated_authorization_prompts: canonical_claim.counts.repeated_authorization_prompts,
            rollback_status: canonical_claim.rollback_status.as_str().to_string(),
            provenance: canonical_claim.provenance.as_str().to_string(),
            agent_id: canonical_claim.agent_id.clone(),
            body_id: canonical_claim.body_id.clone(),
            environment_id: canonical_claim.environment_id.clone(),
            record_sha256,
        })
    }

    /// Return a digest-free summary; evidence content cannot leak through this
    /// routine reporting surface.
    pub fn summary(&self) -> AgentTaskOutcomeSummary {
        AgentTaskOutcomeSummary {
            outcome_id: self.outcome_id.clone(),
            contract_id: self.contract_id.clone(),
            revision: self.revision,
            status: self.status,
            verification: self.verification,
            verification_method: self.verification_method,
            user_acceptance: self.user_acceptance,
            acceptance_provenance: self.acceptance_provenance,
            rollback_status: self.rollback_status,
            provenance: self.provenance,
            evidence_digest_count: self.evidence_sha256.len(),
            counts: self.counts,
        }
    }
}

/// Decode and authenticate one store row.  The row is admitted only when all
/// closed-set fields parse, all bounds hold, and its canonical claim digest
/// matches `record_sha256`.
pub fn from_store_record(
    record: &AgentTaskOutcomeRecord,
) -> Result<AgentTaskOutcome, Vec<AgentTaskOutcomeViolation>> {
    let mut violations = Vec::new();
    if record.schema_version != AGENT_TASK_OUTCOME_SCHEMA_V1 {
        violations.push(violation("unsupported_schema_version", "schema_version"));
    }
    if !(0..=MAX_RECORDED_AT_SECS).contains(&record.recorded_at) {
        violations.push(violation("recorded_at_out_of_bounds", "recorded_at"));
    }
    let status = parse_status(&record.status, &mut violations);
    let verification = parse_verification(&record.verification_status, &mut violations);
    let verification_method =
        parse_verification_method(&record.verification_method, &mut violations);
    let user_acceptance = parse_user_acceptance(&record.user_acceptance, &mut violations);
    let acceptance_provenance =
        parse_acceptance_provenance(&record.acceptance_provenance, &mut violations);
    let rollback_status = parse_rollback_status(&record.rollback_status, &mut violations);
    let provenance = parse_outcome_provenance(&record.provenance, &mut violations);
    if !violations.is_empty() {
        return Err(violations);
    }

    let mut claim = AgentTaskOutcome {
        schema_version: record.schema_version.clone(),
        outcome_id: record.outcome_id.clone(),
        contract_id: record.contract_id.clone(),
        revision: record.contract_revision,
        status: status.expect("closed status parsed without violations"),
        verification: verification.expect("closed verification parsed without violations"),
        verification_method: verification_method
            .expect("closed verification method parsed without violations"),
        user_acceptance: user_acceptance.expect("closed acceptance parsed without violations"),
        acceptance_provenance: acceptance_provenance
            .expect("closed acceptance provenance parsed without violations"),
        rollback_status: rollback_status.expect("closed rollback parsed without violations"),
        provenance: provenance.expect("closed provenance parsed without violations"),
        agent_id: record.agent_id.clone(),
        body_id: record.body_id.clone(),
        environment_id: record.environment_id.clone(),
        evidence_sha256: record.evidence_sha256.clone(),
        counts: AgentTaskOperatorCounts {
            manual_interventions: record.manual_interventions,
            owner_restatements: record.owner_restatements,
            repeated_authorization_prompts: record.repeated_authorization_prompts,
        },
    };
    claim.validate()?;
    claim.evidence_sha256.sort_unstable();
    let expected_digest = canonical_claim_sha256(&claim)?;
    if record.record_sha256 != expected_digest {
        return Err(vec![violation("record_sha256_mismatch", "record_sha256")]);
    }
    Ok(claim)
}

pub fn agent_task_outcome_violations(claim: &AgentTaskOutcome) -> Vec<AgentTaskOutcomeViolation> {
    let mut violations = Vec::new();

    if claim.schema_version != AGENT_TASK_OUTCOME_SCHEMA_V1 {
        violations.push(violation("unsupported_schema_version", "schema_version"));
    }
    for (field, value) in [
        ("outcome_id", Some(claim.outcome_id.as_str())),
        ("contract_id", Some(claim.contract_id.as_str())),
        ("agent_id", claim.agent_id.as_deref()),
        ("body_id", claim.body_id.as_deref()),
        ("environment_id", claim.environment_id.as_deref()),
    ] {
        if value.is_some_and(|value| !valid_identifier(value)) {
            violations.push(violation("invalid_identifier", field));
        }
    }
    if claim.revision == 0 || claim.revision > MAX_REVISION {
        violations.push(violation("revision_out_of_bounds", "revision"));
    }
    if claim.evidence_sha256.len() > MAX_EVIDENCE_DIGESTS {
        violations.push(violation("evidence_array_out_of_bounds", "evidence_sha256"));
    }
    let mut digests = BTreeSet::new();
    for (index, digest) in claim.evidence_sha256.iter().enumerate() {
        if !valid_sha256(digest) {
            violations.push(violation(
                "invalid_sha256_digest",
                &format!("evidence_sha256[{index}]"),
            ));
        } else if !digests.insert(digest) {
            violations.push(violation(
                "duplicate_sha256_digest",
                &format!("evidence_sha256[{index}]"),
            ));
        }
    }

    if claim.verification == AgentTaskOutcomeVerification::Verified {
        if claim.verification_method == AgentTaskOutcomeVerificationMethod::None {
            violations.push(violation("verified_requires_method", "verification_method"));
        }
        if claim.evidence_sha256.is_empty() {
            violations.push(violation(
                "verified_requires_evidence_digest",
                "evidence_sha256",
            ));
        }
    }
    if claim.verification_method == AgentTaskOutcomeVerificationMethod::None
        && !claim.evidence_sha256.is_empty()
    {
        violations.push(violation("evidence_requires_method", "verification_method"));
    }
    if matches!(
        claim.status,
        AgentTaskOutcomeStatus::Achieved | AgentTaskOutcomeStatus::PartiallyAchieved
    ) && claim.verification == AgentTaskOutcomeVerification::NotVerified
    {
        violations.push(violation(
            "achievement_cannot_be_not_verified",
            "verification",
        ));
    }

    let acceptance_consistent = matches!(
        (claim.user_acceptance, claim.acceptance_provenance),
        (
            AgentTaskUserAcceptance::Unknown,
            AgentTaskAcceptanceProvenance::Unavailable
        ) | (
            AgentTaskUserAcceptance::Accepted,
            AgentTaskAcceptanceProvenance::OwnerExplicit
        ) | (
            AgentTaskUserAcceptance::Corrected,
            AgentTaskAcceptanceProvenance::OwnerCorrection
        ) | (
            AgentTaskUserAcceptance::Rejected,
            AgentTaskAcceptanceProvenance::OwnerExplicit
        )
    );
    if !acceptance_consistent {
        violations.push(violation(
            "inconsistent_acceptance_provenance",
            "acceptance_provenance",
        ));
    }
    if claim.provenance == AgentTaskOutcomeProvenance::HarnessVerified
        && claim.verification != AgentTaskOutcomeVerification::Verified
    {
        violations.push(violation(
            "harness_provenance_requires_verified",
            "provenance",
        ));
    }
    if claim.provenance == AgentTaskOutcomeProvenance::OwnerAttested
        && claim.acceptance_provenance == AgentTaskAcceptanceProvenance::Unavailable
    {
        violations.push(violation(
            "owner_provenance_requires_owner_signal",
            "provenance",
        ));
    }

    for (field, count) in [
        (
            "counts.manual_interventions",
            claim.counts.manual_interventions,
        ),
        ("counts.owner_restatements", claim.counts.owner_restatements),
        (
            "counts.repeated_authorization_prompts",
            claim.counts.repeated_authorization_prompts,
        ),
    ] {
        if count.is_some_and(|count| count > MAX_COUNTER_VALUE) {
            violations.push(violation("counter_out_of_bounds", field));
        }
    }

    violations
}

/// Aggregate dedicated outcome-ledger rows.  A lifecycle-finalize signal has no
/// representation in this input type and therefore can never become completion.
/// The immutable `outcome_id` is the retry key: identical rows deduplicate;
/// every differing claim under the same key is excluded as a conflict.
pub fn aggregate_agent_task_outcomes(
    records: &[AgentTaskOutcomeRecord],
) -> AgentTaskOutcomeAggregate {
    let mut aggregate = AgentTaskOutcomeAggregate {
        input_record_count: records.len(),
        ..AgentTaskOutcomeAggregate::default()
    };
    let mut grouped: BTreeMap<String, Vec<AgentTaskOutcome>> = BTreeMap::new();

    for record in records {
        let claim = match from_store_record(record) {
            Ok(claim) => claim,
            Err(_) => {
                aggregate.invalid_record_count += 1;
                continue;
            }
        };
        grouped
            .entry(claim.outcome_id.clone())
            .or_default()
            .push(claim);
    }

    for claims in grouped.into_values() {
        let claim_record_count = claims.len();
        let mut unique = Vec::<AgentTaskOutcome>::new();
        for claim in claims {
            if unique.contains(&claim) {
                aggregate.duplicate_retry_count += 1;
            } else {
                unique.push(claim);
            }
        }

        if unique.len() != 1 {
            aggregate.conflicting_outcome_count += 1;
            aggregate.conflicting_record_count += claim_record_count;
            continue;
        }

        let claim = unique.pop().expect("non-conflicting outcome is non-empty");
        admit_claim(&mut aggregate, &claim);
        aggregate.accepted_outcome_count += 1;
        if aggregate.summaries.len() < MAX_AGGREGATE_SUMMARIES {
            aggregate.summaries.push(claim.summary());
        } else {
            aggregate.truncated_summary_count += 1;
        }
    }

    aggregate
}

fn admit_claim(aggregate: &mut AgentTaskOutcomeAggregate, claim: &AgentTaskOutcome) {
    match claim.status {
        AgentTaskOutcomeStatus::Achieved => aggregate.status_counts.achieved += 1,
        AgentTaskOutcomeStatus::PartiallyAchieved => {
            aggregate.status_counts.partially_achieved += 1
        }
        AgentTaskOutcomeStatus::Blocked => aggregate.status_counts.blocked += 1,
        AgentTaskOutcomeStatus::Abandoned => aggregate.status_counts.abandoned += 1,
    }
    match claim.verification {
        AgentTaskOutcomeVerification::Verified => aggregate.verification_counts.verified += 1,
        AgentTaskOutcomeVerification::NotVerified => {
            aggregate.verification_counts.not_verified += 1
        }
        AgentTaskOutcomeVerification::Unknown => aggregate.verification_counts.unknown += 1,
    }
    match claim.user_acceptance {
        AgentTaskUserAcceptance::Unknown => aggregate.user_acceptance_counts.unknown += 1,
        AgentTaskUserAcceptance::Accepted => aggregate.user_acceptance_counts.accepted += 1,
        AgentTaskUserAcceptance::Corrected => aggregate.user_acceptance_counts.corrected += 1,
        AgentTaskUserAcceptance::Rejected => aggregate.user_acceptance_counts.rejected += 1,
    }
    if claim.status == AgentTaskOutcomeStatus::Achieved
        && claim.verification == AgentTaskOutcomeVerification::Verified
    {
        aggregate.reported_verified_achieved_count += 1;
    }
    if claim.status == AgentTaskOutcomeStatus::Achieved
        && claim.user_acceptance == AgentTaskUserAcceptance::Accepted
    {
        aggregate.reported_owner_accepted_achieved_count += 1;
    }
    match claim.rollback_status {
        AgentTaskRollbackStatus::NotNeeded => aggregate.rollback_counts.not_needed += 1,
        AgentTaskRollbackStatus::Available => aggregate.rollback_counts.available += 1,
        AgentTaskRollbackStatus::Completed => aggregate.rollback_counts.completed += 1,
        AgentTaskRollbackStatus::Failed => aggregate.rollback_counts.failed += 1,
        AgentTaskRollbackStatus::Unknown => aggregate.rollback_counts.unknown += 1,
    }
    match claim.provenance {
        AgentTaskOutcomeProvenance::AgentReported => {
            aggregate.provenance_counts.agent_reported += 1
        }
        AgentTaskOutcomeProvenance::HarnessVerified => {
            aggregate.provenance_counts.harness_verified += 1
        }
        AgentTaskOutcomeProvenance::OwnerAttested => {
            aggregate.provenance_counts.owner_attested += 1
        }
    }
    if let Some(count) = claim.counts.manual_interventions {
        aggregate.operator_counts.manual_interventions += u64::from(count);
        aggregate.operator_count_coverage.manual_interventions += 1;
    }
    if let Some(count) = claim.counts.owner_restatements {
        aggregate.operator_counts.owner_restatements += u64::from(count);
        aggregate.operator_count_coverage.owner_restatements += 1;
    }
    if let Some(count) = claim.counts.repeated_authorization_prompts {
        aggregate.operator_counts.repeated_authorization_prompts += u64::from(count);
        aggregate
            .operator_count_coverage
            .repeated_authorization_prompts += 1;
    }
}

fn canonical_claim_sha256(
    claim: &AgentTaskOutcome,
) -> Result<String, Vec<AgentTaskOutcomeViolation>> {
    let value = serde_json::to_value(claim)
        .map_err(|_| vec![violation("claim_serialization_failed", "record_sha256")])?;
    let canonical = serde_json_canonicalizer::to_vec(&value)
        .map_err(|_| vec![violation("claim_canonicalization_failed", "record_sha256")])?;
    Ok(format!("sha256:{:x}", Sha256::digest(canonical)))
}

fn parse_status(
    value: &str,
    violations: &mut Vec<AgentTaskOutcomeViolation>,
) -> Option<AgentTaskOutcomeStatus> {
    match value {
        "achieved" => Some(AgentTaskOutcomeStatus::Achieved),
        "partially_achieved" => Some(AgentTaskOutcomeStatus::PartiallyAchieved),
        "blocked" => Some(AgentTaskOutcomeStatus::Blocked),
        "abandoned" => Some(AgentTaskOutcomeStatus::Abandoned),
        _ => {
            violations.push(violation("unknown_closed_set_value", "status"));
            None
        }
    }
}

fn parse_verification(
    value: &str,
    violations: &mut Vec<AgentTaskOutcomeViolation>,
) -> Option<AgentTaskOutcomeVerification> {
    match value {
        "verified" => Some(AgentTaskOutcomeVerification::Verified),
        "not_verified" => Some(AgentTaskOutcomeVerification::NotVerified),
        "unknown" => Some(AgentTaskOutcomeVerification::Unknown),
        _ => {
            violations.push(violation("unknown_closed_set_value", "verification_status"));
            None
        }
    }
}

fn parse_verification_method(
    value: &str,
    violations: &mut Vec<AgentTaskOutcomeViolation>,
) -> Option<AgentTaskOutcomeVerificationMethod> {
    match value {
        "tests" => Some(AgentTaskOutcomeVerificationMethod::Tests),
        "postcondition" => Some(AgentTaskOutcomeVerificationMethod::Postcondition),
        "owner_confirmation" => Some(AgentTaskOutcomeVerificationMethod::OwnerConfirmation),
        "mixed" => Some(AgentTaskOutcomeVerificationMethod::Mixed),
        "none" => Some(AgentTaskOutcomeVerificationMethod::None),
        _ => {
            violations.push(violation("unknown_closed_set_value", "verification_method"));
            None
        }
    }
}

fn parse_user_acceptance(
    value: &str,
    violations: &mut Vec<AgentTaskOutcomeViolation>,
) -> Option<AgentTaskUserAcceptance> {
    match value {
        "unknown" => Some(AgentTaskUserAcceptance::Unknown),
        "accepted" => Some(AgentTaskUserAcceptance::Accepted),
        "corrected" => Some(AgentTaskUserAcceptance::Corrected),
        "rejected" => Some(AgentTaskUserAcceptance::Rejected),
        _ => {
            violations.push(violation("unknown_closed_set_value", "user_acceptance"));
            None
        }
    }
}

fn parse_acceptance_provenance(
    value: &str,
    violations: &mut Vec<AgentTaskOutcomeViolation>,
) -> Option<AgentTaskAcceptanceProvenance> {
    match value {
        "unavailable" => Some(AgentTaskAcceptanceProvenance::Unavailable),
        "owner_explicit" => Some(AgentTaskAcceptanceProvenance::OwnerExplicit),
        "owner_correction" => Some(AgentTaskAcceptanceProvenance::OwnerCorrection),
        _ => {
            violations.push(violation(
                "unknown_closed_set_value",
                "acceptance_provenance",
            ));
            None
        }
    }
}

fn parse_rollback_status(
    value: &str,
    violations: &mut Vec<AgentTaskOutcomeViolation>,
) -> Option<AgentTaskRollbackStatus> {
    match value {
        "not_needed" => Some(AgentTaskRollbackStatus::NotNeeded),
        "available" => Some(AgentTaskRollbackStatus::Available),
        "completed" => Some(AgentTaskRollbackStatus::Completed),
        "failed" => Some(AgentTaskRollbackStatus::Failed),
        "unknown" => Some(AgentTaskRollbackStatus::Unknown),
        _ => {
            violations.push(violation("unknown_closed_set_value", "rollback_status"));
            None
        }
    }
}

fn parse_outcome_provenance(
    value: &str,
    violations: &mut Vec<AgentTaskOutcomeViolation>,
) -> Option<AgentTaskOutcomeProvenance> {
    match value {
        "agent_reported" => Some(AgentTaskOutcomeProvenance::AgentReported),
        "harness_verified" => Some(AgentTaskOutcomeProvenance::HarnessVerified),
        "owner_attested" => Some(AgentTaskOutcomeProvenance::OwnerAttested),
        _ => {
            violations.push(violation("unknown_closed_set_value", "provenance"));
            None
        }
    }
}

fn valid_identifier(value: &str) -> bool {
    !value.is_empty()
        && value.len() <= MAX_IDENTIFIER_BYTES
        && value
            .bytes()
            .all(|byte| byte.is_ascii_alphanumeric() || matches!(byte, b'.' | b'_' | b':' | b'-'))
}

fn valid_sha256(value: &str) -> bool {
    let Some(hex) = value.strip_prefix("sha256:") else {
        return false;
    };
    hex.len() == 64
        && hex
            .bytes()
            .all(|byte| byte.is_ascii_digit() || (b'a'..=b'f').contains(&byte))
}

fn violation(code: &str, field: &str) -> AgentTaskOutcomeViolation {
    AgentTaskOutcomeViolation {
        code: code.to_string(),
        field: field.to_string(),
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::{json, Value};

    fn digest(character: char) -> String {
        format!(
            "sha256:{}",
            std::iter::repeat(character).take(64).collect::<String>()
        )
    }

    fn claim(outcome_id: &str, revision: u64) -> AgentTaskOutcome {
        AgentTaskOutcome {
            schema_version: AGENT_TASK_OUTCOME_SCHEMA_V1.to_string(),
            outcome_id: outcome_id.to_string(),
            contract_id: "contract-1".to_string(),
            revision,
            status: AgentTaskOutcomeStatus::Achieved,
            verification: AgentTaskOutcomeVerification::Verified,
            verification_method: AgentTaskOutcomeVerificationMethod::Tests,
            user_acceptance: AgentTaskUserAcceptance::Accepted,
            acceptance_provenance: AgentTaskAcceptanceProvenance::OwnerExplicit,
            rollback_status: AgentTaskRollbackStatus::NotNeeded,
            provenance: AgentTaskOutcomeProvenance::HarnessVerified,
            agent_id: Some("agent-1".to_string()),
            body_id: None,
            environment_id: Some("env-1".to_string()),
            evidence_sha256: vec![digest('a')],
            counts: AgentTaskOperatorCounts::default(),
        }
    }

    fn record(claim: &AgentTaskOutcome) -> AgentTaskOutcomeRecord {
        claim.to_store_record(100).expect("valid outcome row")
    }

    #[test]
    fn serde_rejects_unknown_fields_and_unknown_enum_values() {
        let value = serde_json::to_value(claim("outcome-1", 1)).unwrap();
        let mut object = value.as_object().unwrap().clone();
        object.insert("task_text".to_string(), json!("private"));
        assert!(serde_json::from_value::<AgentTaskOutcome>(Value::Object(object)).is_err());

        let mut value = serde_json::to_value(claim("outcome-1", 1)).unwrap();
        value["status"] = json!("completed");
        assert!(serde_json::from_value::<AgentTaskOutcome>(value).is_err());
    }

    #[test]
    fn verified_requires_method_and_sha256_digest() {
        let mut candidate = claim("outcome-1", 1);
        candidate.verification_method = AgentTaskOutcomeVerificationMethod::None;
        candidate.evidence_sha256 = vec!["raw evidence".to_string()];
        let violations = agent_task_outcome_violations(&candidate);
        assert!(violations
            .iter()
            .any(|item| item.code == "verified_requires_method"));
        assert!(violations
            .iter()
            .any(|item| item.code == "invalid_sha256_digest"));

        candidate.verification_method = AgentTaskOutcomeVerificationMethod::Tests;
        candidate.evidence_sha256 = vec![digest('A')];
        assert!(agent_task_outcome_violations(&candidate)
            .iter()
            .any(|item| item.code == "invalid_sha256_digest"));
    }

    #[test]
    fn acceptance_and_provenance_are_consistent() {
        let mut candidate = claim("outcome-1", 1);
        candidate.user_acceptance = AgentTaskUserAcceptance::Corrected;
        assert!(candidate.validate().is_err());
        candidate.acceptance_provenance = AgentTaskAcceptanceProvenance::OwnerCorrection;
        candidate.provenance = AgentTaskOutcomeProvenance::OwnerAttested;
        assert!(candidate.validate().is_ok());

        candidate.user_acceptance = AgentTaskUserAcceptance::Unknown;
        candidate.acceptance_provenance = AgentTaskAcceptanceProvenance::Unavailable;
        assert!(candidate.validate().is_err());
    }

    #[test]
    fn public_finalize_admits_only_agent_reported_unknown_acceptance() {
        let mut candidate = claim("outcome-1", 1);
        assert!(candidate.validate_agent_reported_admission().is_err());

        candidate.provenance = AgentTaskOutcomeProvenance::AgentReported;
        candidate.user_acceptance = AgentTaskUserAcceptance::Unknown;
        candidate.acceptance_provenance = AgentTaskAcceptanceProvenance::Unavailable;
        assert_eq!(candidate.validate_agent_reported_admission(), Ok(()));

        candidate.verification_method = AgentTaskOutcomeVerificationMethod::OwnerConfirmation;
        assert!(candidate.validate_agent_reported_admission().is_err());
    }

    #[test]
    fn identifiers_arrays_and_counts_are_bounded() {
        let mut candidate = claim("bad id with spaces", MAX_REVISION + 1);
        candidate.evidence_sha256 = vec![digest('a'); MAX_EVIDENCE_DIGESTS + 1];
        candidate.counts.manual_interventions = Some(MAX_COUNTER_VALUE + 1);
        let violations = agent_task_outcome_violations(&candidate);
        for code in [
            "invalid_identifier",
            "revision_out_of_bounds",
            "evidence_array_out_of_bounds",
            "duplicate_sha256_digest",
            "counter_out_of_bounds",
        ] {
            assert!(violations.iter().any(|item| item.code == code), "{code}");
        }
    }

    #[test]
    fn record_validates_timestamp_and_summary_drops_digest_values() {
        let candidate = claim("outcome-1", 1);
        let row = record(&candidate);
        assert_eq!(row.recorded_at, 100);
        assert_eq!(row.outcome_id, candidate.outcome_id);
        assert_eq!(from_store_record(&row).unwrap(), candidate);
        assert!(row.record_sha256.starts_with("sha256:"));
        assert!(candidate.to_store_record(-1).is_err());
        assert!(candidate.to_store_record(MAX_RECORDED_AT_SECS + 1).is_err());

        let summary_json = serde_json::to_string(&candidate.summary()).unwrap();
        assert!(!summary_json.contains(&digest('a')));
        assert!(summary_json.contains("\"evidence_digest_count\":1"));
    }

    #[test]
    fn retry_digest_ignores_transport_metadata_and_canonicalizes_evidence_order() {
        let mut candidate = claim("outcome-1", 1);
        candidate.evidence_sha256 = vec![digest('b'), digest('a')];
        let first = candidate.to_store_record(100).unwrap();
        let retry = candidate.to_store_record(200).unwrap();

        assert_eq!(first.record_sha256, retry.record_sha256);
        assert_eq!(first.evidence_sha256, vec![digest('a'), digest('b')]);
        assert_eq!(from_store_record(&first), from_store_record(&retry));
        let aggregate = aggregate_agent_task_outcomes(&[first, retry]);
        assert_eq!(aggregate.accepted_outcome_count, 1);
        assert_eq!(aggregate.duplicate_retry_count, 1);
    }

    #[test]
    fn aggregate_deduplicates_identical_retry() {
        let first = claim("outcome-1", 1);
        let mut second = claim("outcome-2", 2);
        second.status = AgentTaskOutcomeStatus::Blocked;
        second.verification = AgentTaskOutcomeVerification::NotVerified;
        second.verification_method = AgentTaskOutcomeVerificationMethod::Postcondition;
        second.provenance = AgentTaskOutcomeProvenance::AgentReported;
        second.counts.manual_interventions = Some(2);

        let aggregate = aggregate_agent_task_outcomes(&[
            record(&first),
            record(&first),
            record(&second),
            record(&second),
        ]);
        assert_eq!(aggregate.accepted_outcome_count, 2);
        assert_eq!(aggregate.duplicate_retry_count, 2);
        assert_eq!(aggregate.status_counts.achieved, 1);
        assert_eq!(aggregate.status_counts.blocked, 1);
        assert_eq!(aggregate.reported_verified_achieved_count, 1);
        assert_eq!(aggregate.operator_counts.manual_interventions, 2);
        assert_eq!(aggregate.operator_count_coverage.manual_interventions, 1);
        assert_eq!(aggregate.summaries[0].outcome_id, "outcome-1");
        assert_eq!(aggregate.summaries[1].outcome_id, "outcome-2");
    }

    #[test]
    fn same_retry_conflict_is_excluded_and_counted() {
        let first = claim("outcome-1", 1);
        let mut conflicting = first.clone();
        conflicting.rollback_status = AgentTaskRollbackStatus::Available;
        let aggregate =
            aggregate_agent_task_outcomes(&[record(&first), record(&first), record(&conflicting)]);

        assert_eq!(aggregate.duplicate_retry_count, 1);
        assert_eq!(aggregate.conflicting_outcome_count, 1);
        assert_eq!(aggregate.conflicting_record_count, 3);
        assert_eq!(aggregate.accepted_outcome_count, 0);
        assert_eq!(aggregate.status_counts.achieved, 0);
        assert!(aggregate.summaries.is_empty());
    }

    #[test]
    fn changing_contract_or_revision_conflicts_for_immutable_outcome_id() {
        let first = claim("outcome-1", 1);
        let mut second = claim("outcome-1", 2);
        second.contract_id = "contract-2".to_string();
        let aggregate = aggregate_agent_task_outcomes(&[record(&first), record(&second)]);
        assert_eq!(aggregate.conflicting_outcome_count, 1);
        assert_eq!(aggregate.conflicting_record_count, 2);
        assert_eq!(aggregate.accepted_outcome_count, 0);
    }

    #[test]
    fn lifecycle_finalize_cannot_deserialize_as_an_outcome_row() {
        let mut finalized = record(&claim("outcome-1", 1));
        finalized.status = "completed".to_string();
        assert!(from_store_record(&finalized).is_err());
        let aggregate = aggregate_agent_task_outcomes(&[finalized]);
        assert_eq!(aggregate.invalid_record_count, 1);
        assert_eq!(aggregate.accepted_outcome_count, 0);
    }

    #[test]
    fn agent_reported_achievement_is_not_verified_achievement() {
        let mut candidate = claim("outcome-1", 1);
        candidate.verification = AgentTaskOutcomeVerification::Unknown;
        candidate.verification_method = AgentTaskOutcomeVerificationMethod::None;
        candidate.evidence_sha256.clear();
        candidate.provenance = AgentTaskOutcomeProvenance::AgentReported;
        candidate.user_acceptance = AgentTaskUserAcceptance::Unknown;
        candidate.acceptance_provenance = AgentTaskAcceptanceProvenance::Unavailable;

        let aggregate = aggregate_agent_task_outcomes(&[record(&candidate)]);
        assert_eq!(aggregate.status_counts.achieved, 1);
        assert_eq!(aggregate.verification_counts.unknown, 1);
        assert_eq!(aggregate.reported_verified_achieved_count, 0);
        assert_eq!(aggregate.reported_owner_accepted_achieved_count, 0);
    }

    #[test]
    fn invalid_ledger_row_is_not_counted() {
        let candidate = claim("outcome-1", 1);
        let mut row = record(&candidate);
        row.record_sha256 = digest('f');
        let aggregate = aggregate_agent_task_outcomes(&[row]);
        assert_eq!(aggregate.invalid_record_count, 1);
        assert_eq!(aggregate.accepted_outcome_count, 0);
    }
}
