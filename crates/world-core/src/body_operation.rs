//! Portable contract for one bounded body operation.
//!
//! This records the invariants an actuator adapter must satisfy. It neither
//! dispatches an action nor grants authority; runtime layers must validate the
//! supplied lease and produce the independent post-action observation.

use std::collections::BTreeSet;

use serde::{Deserialize, Serialize};
use serde_json::{json, Value};
use sha2::{Digest, Sha256};

use crate::{BodyId, IntentId, LeaseId, ObservationEnvelope, OBSERVATION_SCHEMA_V0};

pub const BODY_OPERATION_ENVELOPE_SCHEMA_V1: &str = "agent_bridge.body_operation_envelope.v1";

const MAX_IDENTIFIER_LEN: usize = 128;
const MAX_ACTION_KIND_LEN: usize = 96;
const MAX_EVIDENCE_DIGESTS: usize = 8;
const MAX_MEMORY_LINK_DIGESTS: usize = 16;
const MAX_OBSERVATION_AGE_MS: u64 = 60_000;
const MAX_OPERATION_DURATION_MS: u64 = 3_600_000;

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum BodyOperationStatus {
    Planned,
    Submitted,
    Succeeded,
    Failed,
    Abandoned,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum BodyVerificationStatus {
    Verified,
    NotVerified,
    Unknown,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum BodyRecoveryDecision {
    None,
    Reobserve,
    RetryAfterReobserve,
    Rollback,
    Escalate,
    Abandon,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct BodyObservationProvenance {
    pub adapter_id: String,
    pub adapter_build_sha256: String,
    pub observation_sha256: String,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct BodyPostconditionVerification {
    pub status: BodyVerificationStatus,
    pub verifier_adapter_id: Option<String>,
    pub verifier_build_sha256: Option<String>,
    #[serde(default)]
    pub evidence_sha256: Vec<String>,
    pub independent_from_action: bool,
}

/// Content-addressed operation envelope shared by body adapters.
///
/// Observation payloads are accepted for in-memory validation.
/// [`Self::redacted_facts`] deliberately omits them before Event Spine storage.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct BodyOperationEnvelope {
    pub schema_version: String,
    pub agent_id: String,
    pub body_id: BodyId,
    pub environment_id: String,
    pub operation_id: String,
    pub intent_id: IntentId,
    pub mutation: bool,
    pub lease_id: Option<LeaseId>,
    pub action_kind: String,
    pub action_adapter_id: String,
    pub action_adapter_build_sha256: String,
    pub action_request_sha256: String,
    pub expected_postcondition_sha256: String,
    pub action_started_at_unix_ms: u64,
    pub action_completed_at_unix_ms: Option<u64>,
    pub pre_observation: ObservationEnvelope,
    pub pre_observation_max_age_ms: u64,
    pub pre_observation_provenance: BodyObservationProvenance,
    pub status: BodyOperationStatus,
    pub observed_after: Option<ObservationEnvelope>,
    pub post_observation_provenance: Option<BodyObservationProvenance>,
    pub postcondition_verification: BodyPostconditionVerification,
    pub recovery_decision: BodyRecoveryDecision,
    pub rollback_sha256: Option<String>,
    #[serde(default)]
    pub memory_links_sha256: Vec<String>,
}

impl BodyOperationEnvelope {
    pub fn is_terminal(&self) -> bool {
        matches!(
            self.status,
            BodyOperationStatus::Succeeded
                | BodyOperationStatus::Failed
                | BodyOperationStatus::Abandoned
        )
    }

    /// Privacy-minimal persistence view. Raw observations, action arguments,
    /// postcondition text, and memory identifiers are represented by digests.
    pub fn redacted_facts(&self) -> Value {
        json!({
            "schema_version": self.schema_version,
            "agent_id": self.agent_id,
            "body_id": self.body_id,
            "environment_id": self.environment_id,
            "operation_id": self.operation_id,
            "intent_id": self.intent_id,
            "mutation": self.mutation,
            "lease_present": self.lease_id.is_some(),
            "action_kind": self.action_kind,
            "action_adapter_id": self.action_adapter_id,
            "action_adapter_build_sha256": self.action_adapter_build_sha256,
            "action_request_sha256": self.action_request_sha256,
            "expected_postcondition_sha256": self.expected_postcondition_sha256,
            "action_started_at_unix_ms": self.action_started_at_unix_ms,
            "action_completed_at_unix_ms": self.action_completed_at_unix_ms,
            "pre_observation": observation_metadata(&self.pre_observation),
            "pre_observation_max_age_ms": self.pre_observation_max_age_ms,
            "pre_observation_provenance": self.pre_observation_provenance,
            "status": self.status,
            "observed_after": self.observed_after.as_ref().map(observation_metadata),
            "post_observation_provenance": self.post_observation_provenance,
            "postcondition_verification_claim": self.postcondition_verification,
            "recovery_decision": self.recovery_decision,
            "rollback_sha256": self.rollback_sha256,
            "memory_links_sha256": self.memory_links_sha256,
            "raw_observation_payloads_stored": false,
            "executes_action": false,
            "grants_authority": false,
            "authenticates_adapter": false,
        })
    }
}

fn observation_metadata(observation: &ObservationEnvelope) -> Value {
    json!({
        "schema": observation.schema,
        "body_id": observation.body_id,
        "source": observation.source,
        "observed_at_unix_ms": observation.observed_at_unix_ms,
        "freshness_ms": observation.freshness_ms,
        "confidence": observation.confidence,
        "world_revision": observation.world_revision,
        "payload_stored": false,
    })
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct BodyOperationViolation {
    pub code: String,
    pub field: String,
}

impl BodyOperationViolation {
    fn new(code: &str, field: &str) -> Self {
        Self {
            code: code.to_string(),
            field: field.to_string(),
        }
    }
}

/// Validate the five operation invariants at an explicit observation time.
pub fn validate_body_operation_at(
    envelope: &BodyOperationEnvelope,
    now_unix_ms: u64,
) -> Result<(), Vec<BodyOperationViolation>> {
    let mut violations = Vec::new();

    if envelope.schema_version != BODY_OPERATION_ENVELOPE_SCHEMA_V1 {
        violations.push(BodyOperationViolation::new(
            "unsupported_schema_version",
            "schema_version",
        ));
    }
    for (field, value) in [
        ("agent_id", envelope.agent_id.as_str()),
        ("body_id", envelope.body_id.as_str()),
        ("environment_id", envelope.environment_id.as_str()),
        ("operation_id", envelope.operation_id.as_str()),
        ("intent_id", envelope.intent_id.as_str()),
    ] {
        if !valid_identifier(value) {
            violations.push(BodyOperationViolation::new("invalid_identifier", field));
        }
    }
    if !valid_identifier(&envelope.action_kind) || envelope.action_kind.len() > MAX_ACTION_KIND_LEN
    {
        violations.push(BodyOperationViolation::new(
            "invalid_action_kind",
            "action_kind",
        ));
    }
    if !valid_identifier(&envelope.action_adapter_id) {
        violations.push(BodyOperationViolation::new(
            "invalid_identifier",
            "action_adapter_id",
        ));
    }
    validate_digest(
        &envelope.action_adapter_build_sha256,
        "action_adapter_build_sha256",
        &mut violations,
    );
    validate_digest(
        &envelope.action_request_sha256,
        "action_request_sha256",
        &mut violations,
    );
    validate_digest(
        &envelope.expected_postcondition_sha256,
        "expected_postcondition_sha256",
        &mut violations,
    );
    validate_digest_list(
        &envelope.memory_links_sha256,
        MAX_MEMORY_LINK_DIGESTS,
        "memory_links_sha256",
        &mut violations,
    );
    if let Some(rollback) = &envelope.rollback_sha256 {
        validate_digest(rollback, "rollback_sha256", &mut violations);
    }

    if envelope.pre_observation_max_age_ms == 0
        || envelope.pre_observation_max_age_ms > MAX_OBSERVATION_AGE_MS
    {
        violations.push(BodyOperationViolation::new(
            "invalid_observation_max_age",
            "pre_observation_max_age_ms",
        ));
    }

    if envelope.action_started_at_unix_ms == 0 || envelope.action_started_at_unix_ms > now_unix_ms {
        violations.push(BodyOperationViolation::new(
            "invalid_action_start_time",
            "action_started_at_unix_ms",
        ));
    }
    let completed_at = envelope.action_completed_at_unix_ms;
    if envelope.is_terminal() && completed_at.is_none() {
        violations.push(BodyOperationViolation::new(
            "terminal_operation_requires_completion_time",
            "action_completed_at_unix_ms",
        ));
    }
    if let Some(completed_at) = completed_at {
        if completed_at < envelope.action_started_at_unix_ms || completed_at > now_unix_ms {
            violations.push(BodyOperationViolation::new(
                "invalid_action_completion_time",
                "action_completed_at_unix_ms",
            ));
        }
        if completed_at.saturating_sub(envelope.action_started_at_unix_ms)
            > MAX_OPERATION_DURATION_MS
        {
            violations.push(BodyOperationViolation::new(
                "operation_duration_out_of_bounds",
                "action_completed_at_unix_ms",
            ));
        }
    }

    validate_observation(
        &envelope.pre_observation,
        &envelope.body_id,
        envelope.action_started_at_unix_ms,
        envelope.pre_observation_max_age_ms,
        "pre_observation",
        &mut violations,
    );
    validate_observation_provenance(
        &envelope.pre_observation,
        &envelope.pre_observation_provenance,
        "pre_observation_provenance",
        &mut violations,
    );
    if envelope.mutation && envelope.lease_id.is_none() {
        violations.push(BodyOperationViolation::new(
            "mutation_requires_lease",
            "lease_id",
        ));
    }

    if let Some(after) = &envelope.observed_after {
        // Validate the observation's own shape/freshness budget without making
        // receipt-arrival time part of the contract. A delayed idempotent
        // receipt retry must not turn an already-valid post observation stale.
        validate_observation(
            after,
            &envelope.body_id,
            after.observed_at_unix_ms,
            envelope.pre_observation_max_age_ms,
            "observed_after",
            &mut violations,
        );
        if after.observed_at_unix_ms > now_unix_ms {
            violations.push(BodyOperationViolation::new(
                "observation_from_future",
                "observed_after.observed_at_unix_ms",
            ));
        }
        match completed_at {
            Some(completed_at) if after.observed_at_unix_ms < completed_at => {
                violations.push(BodyOperationViolation::new(
                    "post_observation_before_completion",
                    "observed_after.observed_at_unix_ms",
                ));
            }
            Some(completed_at)
                if after
                    .observed_at_unix_ms
                    .saturating_sub(completed_at)
                    .saturating_add(after.freshness_ms)
                    > envelope.pre_observation_max_age_ms =>
            {
                violations.push(BodyOperationViolation::new(
                    "stale_observation",
                    "observed_after.observed_at_unix_ms",
                ));
            }
            None => violations.push(BodyOperationViolation::new(
                "post_observation_requires_completion_time",
                "action_completed_at_unix_ms",
            )),
            _ => {}
        }
        if after.observed_at_unix_ms <= envelope.pre_observation.observed_at_unix_ms
            || after.observed_at_unix_ms < envelope.action_started_at_unix_ms
        {
            violations.push(BodyOperationViolation::new(
                "post_observation_not_after_action",
                "observed_after.observed_at_unix_ms",
            ));
        }
        if after.world_revision < envelope.pre_observation.world_revision {
            violations.push(BodyOperationViolation::new(
                "post_observation_revision_regressed",
                "observed_after.world_revision",
            ));
        }
    }
    match (
        envelope.observed_after.as_ref(),
        envelope.post_observation_provenance.as_ref(),
    ) {
        (Some(after), Some(provenance)) => validate_observation_provenance(
            after,
            provenance,
            "post_observation_provenance",
            &mut violations,
        ),
        (None, Some(_)) => violations.push(BodyOperationViolation::new(
            "post_provenance_without_observation",
            "post_observation_provenance",
        )),
        _ => {}
    }

    validate_digest_list(
        &envelope.postcondition_verification.evidence_sha256,
        MAX_EVIDENCE_DIGESTS,
        "postcondition_verification.evidence_sha256",
        &mut violations,
    );
    if let Some(adapter) = &envelope.postcondition_verification.verifier_adapter_id {
        if !valid_identifier(adapter) {
            violations.push(BodyOperationViolation::new(
                "invalid_identifier",
                "postcondition_verification.verifier_adapter_id",
            ));
        }
    }
    if let Some(build) = &envelope.postcondition_verification.verifier_build_sha256 {
        validate_digest(
            build,
            "postcondition_verification.verifier_build_sha256",
            &mut violations,
        );
    }
    if envelope.postcondition_verification.status == BodyVerificationStatus::Verified {
        if envelope.status != BodyOperationStatus::Succeeded {
            violations.push(BodyOperationViolation::new(
                "verified_requires_succeeded_status",
                "status",
            ));
        }
        if envelope.observed_after.is_none() {
            violations.push(BodyOperationViolation::new(
                "verified_without_post_observation",
                "observed_after",
            ));
        }
        if !envelope.postcondition_verification.independent_from_action {
            violations.push(BodyOperationViolation::new(
                "verification_not_independent",
                "postcondition_verification.independent_from_action",
            ));
        }
        if envelope
            .postcondition_verification
            .verifier_adapter_id
            .is_none()
        {
            violations.push(BodyOperationViolation::new(
                "missing_verifier_provenance",
                "postcondition_verification.verifier_adapter_id",
            ));
        }
        if let Some(verifier_adapter_id) = envelope
            .postcondition_verification
            .verifier_adapter_id
            .as_ref()
        {
            if verifier_adapter_id == &envelope.action_adapter_id {
                violations.push(BodyOperationViolation::new(
                    "verification_adapter_not_independent",
                    "postcondition_verification.verifier_adapter_id",
                ));
            }
            if envelope.observed_after.as_ref().is_some_and(|observation| {
                observation.source.as_str() != verifier_adapter_id.as_str()
            }) {
                violations.push(BodyOperationViolation::new(
                    "verification_observation_source_mismatch",
                    "observed_after.source",
                ));
            }
        }
        if envelope
            .postcondition_verification
            .verifier_build_sha256
            .is_none()
        {
            violations.push(BodyOperationViolation::new(
                "missing_verifier_provenance",
                "postcondition_verification.verifier_build_sha256",
            ));
        }
        if envelope.post_observation_provenance.is_none() {
            violations.push(BodyOperationViolation::new(
                "missing_verifier_provenance",
                "post_observation_provenance",
            ));
        }
        if let (Some(post_provenance), Some(verifier_id), Some(verifier_build)) = (
            envelope.post_observation_provenance.as_ref(),
            envelope
                .postcondition_verification
                .verifier_adapter_id
                .as_ref(),
            envelope
                .postcondition_verification
                .verifier_build_sha256
                .as_ref(),
        ) {
            if &post_provenance.adapter_id != verifier_id {
                violations.push(BodyOperationViolation::new(
                    "verification_provenance_adapter_mismatch",
                    "post_observation_provenance.adapter_id",
                ));
            }
            if &post_provenance.adapter_build_sha256 != verifier_build {
                violations.push(BodyOperationViolation::new(
                    "verification_provenance_build_mismatch",
                    "post_observation_provenance.adapter_build_sha256",
                ));
            }
        }
        if envelope
            .postcondition_verification
            .evidence_sha256
            .is_empty()
        {
            violations.push(BodyOperationViolation::new(
                "missing_verification_evidence",
                "postcondition_verification.evidence_sha256",
            ));
        }
    }

    if envelope.status == BodyOperationStatus::Succeeded {
        if envelope.observed_after.is_none() {
            violations.push(BodyOperationViolation::new(
                "success_without_post_observation",
                "observed_after",
            ));
        }
        if envelope.postcondition_verification.status != BodyVerificationStatus::Verified {
            violations.push(BodyOperationViolation::new(
                "success_without_verified_postcondition",
                "postcondition_verification.status",
            ));
        }
        if envelope
            .observed_after
            .as_ref()
            .map(|after| after.world_revision <= envelope.pre_observation.world_revision)
            .unwrap_or(false)
        {
            violations.push(BodyOperationViolation::new(
                "success_without_newer_observation",
                "observed_after.world_revision",
            ));
        }
        if envelope.recovery_decision != BodyRecoveryDecision::None {
            violations.push(BodyOperationViolation::new(
                "success_cannot_require_recovery",
                "recovery_decision",
            ));
        }
    }
    if envelope.status == BodyOperationStatus::Failed
        && envelope.recovery_decision == BodyRecoveryDecision::None
    {
        violations.push(BodyOperationViolation::new(
            "failed_operation_requires_recovery_decision",
            "recovery_decision",
        ));
    }
    if envelope.recovery_decision == BodyRecoveryDecision::Rollback
        && envelope.rollback_sha256.is_none()
    {
        violations.push(BodyOperationViolation::new(
            "rollback_decision_requires_digest",
            "rollback_sha256",
        ));
    }

    if violations.is_empty() {
        Ok(())
    } else {
        Err(violations)
    }
}

fn validate_observation(
    observation: &ObservationEnvelope,
    body_id: &BodyId,
    now_unix_ms: u64,
    max_age_ms: u64,
    field: &str,
    violations: &mut Vec<BodyOperationViolation>,
) {
    if observation.schema != OBSERVATION_SCHEMA_V0 {
        violations.push(BodyOperationViolation::new(
            "unsupported_observation_schema",
            &format!("{field}.schema"),
        ));
    }
    if &observation.body_id != body_id {
        violations.push(BodyOperationViolation::new(
            "observation_body_mismatch",
            &format!("{field}.body_id"),
        ));
    }
    if !valid_identifier(&observation.source) {
        violations.push(BodyOperationViolation::new(
            "invalid_observation_source",
            &format!("{field}.source"),
        ));
    }
    if !observation.confidence.is_finite() || !(0.0..=1.0).contains(&observation.confidence) {
        violations.push(BodyOperationViolation::new(
            "invalid_observation_confidence",
            &format!("{field}.confidence"),
        ));
    }
    if observation.observed_at_unix_ms > now_unix_ms {
        violations.push(BodyOperationViolation::new(
            "observation_from_future",
            &format!("{field}.observed_at_unix_ms"),
        ));
    } else if max_age_ms == 0
        || max_age_ms > MAX_OBSERVATION_AGE_MS
        || !observation.is_fresh_at(now_unix_ms, max_age_ms)
    {
        violations.push(BodyOperationViolation::new(
            "stale_observation",
            &format!("{field}.observed_at_unix_ms"),
        ));
    }
}

fn validate_observation_provenance(
    observation: &ObservationEnvelope,
    provenance: &BodyObservationProvenance,
    field: &str,
    violations: &mut Vec<BodyOperationViolation>,
) {
    if provenance.adapter_id != observation.source {
        violations.push(BodyOperationViolation::new(
            "observation_provenance_source_mismatch",
            &format!("{field}.adapter_id"),
        ));
    }
    if !valid_identifier(&provenance.adapter_id) {
        violations.push(BodyOperationViolation::new(
            "invalid_identifier",
            &format!("{field}.adapter_id"),
        ));
    }
    validate_digest(
        &provenance.adapter_build_sha256,
        &format!("{field}.adapter_build_sha256"),
        violations,
    );
    validate_digest(
        &provenance.observation_sha256,
        &format!("{field}.observation_sha256"),
        violations,
    );
    match body_observation_sha256(observation) {
        Ok(computed) if computed != provenance.observation_sha256 => {
            violations.push(BodyOperationViolation::new(
                "observation_digest_mismatch",
                &format!("{field}.observation_sha256"),
            ));
        }
        Err(violation) => violations.push(violation),
        _ => {}
    }
}

/// Canonical digest binding every observation field, including its payload.
///
/// This detects content changes inside an envelope. It does not authenticate
/// the adapter that supplied the observation; trusted runtime admission still
/// needs a server-side adapter registry or signed attestation.
pub fn body_observation_sha256(
    observation: &ObservationEnvelope,
) -> Result<String, BodyOperationViolation> {
    let value = serde_json::to_value(observation).map_err(|_| {
        BodyOperationViolation::new("observation_serialization_failed", "observation")
    })?;
    let canonical = serde_json_canonicalizer::to_vec(&value).map_err(|_| {
        BodyOperationViolation::new("observation_canonicalization_failed", "observation")
    })?;
    Ok(format!("sha256:{:x}", Sha256::digest(canonical)))
}

fn validate_digest(value: &str, field: &str, violations: &mut Vec<BodyOperationViolation>) {
    if !is_sha256(value) {
        violations.push(BodyOperationViolation::new("invalid_sha256", field));
    }
}

fn validate_digest_list(
    values: &[String],
    maximum: usize,
    field: &str,
    violations: &mut Vec<BodyOperationViolation>,
) {
    if values.len() > maximum {
        violations.push(BodyOperationViolation::new("too_many_digests", field));
    }
    let mut unique = BTreeSet::new();
    for value in values {
        if !is_sha256(value) {
            violations.push(BodyOperationViolation::new("invalid_sha256", field));
        }
        if !unique.insert(value) {
            violations.push(BodyOperationViolation::new("duplicate_digest", field));
        }
    }
}

fn valid_identifier(value: &str) -> bool {
    !value.is_empty()
        && value.len() <= MAX_IDENTIFIER_LEN
        && value
            .bytes()
            .all(|byte| byte.is_ascii_alphanumeric() || matches!(byte, b'.' | b'_' | b':' | b'-'))
}

fn is_sha256(value: &str) -> bool {
    value.len() == 71
        && value.starts_with("sha256:")
        && value.as_bytes()[7..]
            .iter()
            .all(|byte| byte.is_ascii_hexdigit() && !byte.is_ascii_uppercase())
}

#[cfg(test)]
mod tests {
    use super::*;

    fn digest(character: char) -> String {
        format!("sha256:{}", character.to_string().repeat(64))
    }

    fn observation(revision: u64, payload: Value) -> ObservationEnvelope {
        ObservationEnvelope {
            schema: OBSERVATION_SCHEMA_V0.into(),
            body_id: BodyId::from_raw("body-local"),
            source: "desktop_snapshot".into(),
            observed_at_unix_ms: 990,
            freshness_ms: 0,
            confidence: 1.0,
            world_revision: revision,
            payload,
        }
    }

    fn valid_envelope() -> BodyOperationEnvelope {
        let pre_observation = observation(7, json!({"secret": "before"}));
        let observed_after = ObservationEnvelope {
            source: "desktop_verify".into(),
            observed_at_unix_ms: 999,
            ..observation(8, json!({"secret": "after"}))
        };
        let pre_observation_sha256 = body_observation_sha256(&pre_observation).unwrap();
        let post_observation_sha256 = body_observation_sha256(&observed_after).unwrap();
        BodyOperationEnvelope {
            schema_version: BODY_OPERATION_ENVELOPE_SCHEMA_V1.into(),
            agent_id: "agent-codex".into(),
            body_id: BodyId::from_raw("body-local"),
            environment_id: "env-desktop".into(),
            operation_id: "operation-1".into(),
            intent_id: IntentId::from_raw("intent-1"),
            mutation: true,
            lease_id: Some(LeaseId::from_raw("lease-1")),
            action_kind: "focus_window".into(),
            action_adapter_id: "desktop_action".into(),
            action_adapter_build_sha256: digest('9'),
            action_request_sha256: digest('a'),
            expected_postcondition_sha256: digest('b'),
            action_started_at_unix_ms: 995,
            action_completed_at_unix_ms: Some(998),
            pre_observation,
            pre_observation_max_age_ms: 100,
            pre_observation_provenance: BodyObservationProvenance {
                adapter_id: "desktop_snapshot".into(),
                adapter_build_sha256: digest('c'),
                observation_sha256: pre_observation_sha256,
            },
            status: BodyOperationStatus::Succeeded,
            observed_after: Some(observed_after),
            post_observation_provenance: Some(BodyObservationProvenance {
                adapter_id: "desktop_verify".into(),
                adapter_build_sha256: digest('e'),
                observation_sha256: post_observation_sha256,
            }),
            postcondition_verification: BodyPostconditionVerification {
                status: BodyVerificationStatus::Verified,
                verifier_adapter_id: Some("desktop_verify".into()),
                verifier_build_sha256: Some(digest('e')),
                evidence_sha256: vec![digest('f')],
                independent_from_action: true,
            },
            recovery_decision: BodyRecoveryDecision::None,
            rollback_sha256: Some(digest('1')),
            memory_links_sha256: vec![digest('2')],
        }
    }

    fn codes(result: Result<(), Vec<BodyOperationViolation>>) -> Vec<String> {
        result
            .unwrap_err()
            .into_iter()
            .map(|violation| violation.code)
            .collect()
    }

    #[test]
    fn verified_mutation_satisfies_all_five_invariants() {
        assert_eq!(validate_body_operation_at(&valid_envelope(), 1_000), Ok(()));
    }

    #[test]
    fn mutation_requires_lease_and_operation_identity() {
        let mut envelope = valid_envelope();
        envelope.lease_id = None;
        envelope.operation_id.clear();
        let codes = codes(validate_body_operation_at(&envelope, 1_000));
        assert!(codes.contains(&"mutation_requires_lease".into()));
        assert!(codes.contains(&"invalid_identifier".into()));
    }

    #[test]
    fn stale_pre_observation_fails_closed() {
        let mut envelope = valid_envelope();
        envelope.pre_observation.observed_at_unix_ms = 100;
        assert!(codes(validate_body_operation_at(&envelope, 1_000))
            .contains(&"stale_observation".into()));
    }

    #[test]
    fn post_observation_must_follow_action_completion() {
        let mut envelope = valid_envelope();
        envelope.action_completed_at_unix_ms = Some(1_000);
        let codes = codes(validate_body_operation_at(&envelope, 1_000));
        assert!(codes.contains(&"post_observation_before_completion".into()));
    }

    #[test]
    fn success_requires_new_independently_verified_observation() {
        let mut envelope = valid_envelope();
        envelope.observed_after.as_mut().unwrap().world_revision = 7;
        envelope.postcondition_verification.independent_from_action = false;
        let codes = codes(validate_body_operation_at(&envelope, 1_000));
        assert!(codes.contains(&"verification_not_independent".into()));
        assert!(codes.contains(&"success_without_newer_observation".into()));
    }

    #[test]
    fn verifier_must_be_distinct_and_source_bound() {
        let mut envelope = valid_envelope();
        envelope.postcondition_verification.verifier_adapter_id =
            Some(envelope.action_adapter_id.clone());
        envelope.observed_after.as_mut().unwrap().source = "other_verifier".into();
        let codes = codes(validate_body_operation_at(&envelope, 1_000));
        assert!(codes.contains(&"verification_adapter_not_independent".into()));
        assert!(codes.contains(&"verification_observation_source_mismatch".into()));
    }

    #[test]
    fn observation_provenance_is_source_bound() {
        let mut envelope = valid_envelope();
        envelope.pre_observation_provenance.adapter_id = "other_adapter".into();
        assert!(codes(validate_body_operation_at(&envelope, 1_000))
            .contains(&"observation_provenance_source_mismatch".into()));
    }

    #[test]
    fn failed_operation_requires_a_recovery_decision() {
        let mut envelope = valid_envelope();
        envelope.status = BodyOperationStatus::Failed;
        envelope.recovery_decision = BodyRecoveryDecision::None;
        assert!(codes(validate_body_operation_at(&envelope, 1_000))
            .contains(&"failed_operation_requires_recovery_decision".into()));
    }

    #[test]
    fn failed_or_abandoned_operation_cannot_claim_verified() {
        let mut envelope = valid_envelope();
        envelope.status = BodyOperationStatus::Failed;
        envelope.recovery_decision = BodyRecoveryDecision::Escalate;
        assert!(codes(validate_body_operation_at(&envelope, 1_000))
            .contains(&"verified_requires_succeeded_status".into()));
    }

    #[test]
    fn observation_digest_and_action_time_are_bound() {
        let mut envelope = valid_envelope();
        envelope.pre_observation.payload = json!({"secret": "tampered"});
        envelope
            .observed_after
            .as_mut()
            .unwrap()
            .observed_at_unix_ms = 994;
        let codes = codes(validate_body_operation_at(&envelope, 1_000));
        assert!(codes.contains(&"observation_digest_mismatch".into()));
        assert!(codes.contains(&"post_observation_not_after_action".into()));
    }

    #[test]
    fn delayed_receipt_keeps_action_time_freshness_semantics() {
        assert_eq!(
            validate_body_operation_at(&valid_envelope(), 1_000_000),
            Ok(())
        );
    }

    #[test]
    fn persisted_projection_omits_raw_observation_payloads() {
        let facts = valid_envelope().redacted_facts();
        let serialized = serde_json::to_string(&facts).unwrap();
        assert!(!serialized.contains("\"secret\""));
        assert!(!serialized.contains("lease-1"));
        assert_eq!(facts["lease_present"], true);
        assert_eq!(facts["raw_observation_payloads_stored"], false);
    }
}
