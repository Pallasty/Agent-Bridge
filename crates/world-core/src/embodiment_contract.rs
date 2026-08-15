//! P0 contracts for the decision-coupled embodiment loop.
//!
//! These types are portable data contracts only.  They do not call adapters,
//! mutate a body, persist memory, or grant authority.  Runtime layers may
//! consume them after applying their own policy and owner gates.

use std::collections::BTreeSet;

use serde::{Deserialize, Serialize};
use serde_json::Value;

use crate::{
    ActionReceipt, BodyDescriptor, BodyId, IntentId, LeaseId, ObservationEnvelope,
    OBSERVATION_SCHEMA_V0,
};

pub const OBSERVED_WORLD_SCHEMA_V0: &str = "agent_bridge.observed_world.v0";
pub const COMPONENT_PROPOSAL_SCHEMA_V0: &str = "agent_bridge.component_proposal.v0";
pub const COGNITIVE_DECISION_SCHEMA_V0: &str = "agent_bridge.cognitive_decision.v0";
pub const AUTHORITY_DECISION_SCHEMA_V0: &str = "agent_bridge.authority_decision.v0";
pub const PROJECTION_PLAN_SCHEMA_V0: &str = "agent_bridge.projection_plan.v0";
pub const EFFECT_RECEIPT_SCHEMA_V0: &str = "agent_bridge.effect_receipt.v0";
pub const MEMORY_USE_DECISION_SCHEMA_V0: &str = "agent_bridge.memory_use_decision.v0";

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum DecisionAuthority {
    NonAuthoritative,
    OwnerConfirmed,
    DeterministicKernel,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum AuthorityDecisionStatus {
    PendingOwner,
    Approved,
    Denied,
    Expired,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum EffectStatus {
    Planned,
    Submitted,
    Succeeded,
    Failed,
    Abandoned,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum MemoryUseMode {
    RecallOnly,
    Candidate,
    Canonical,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct ObservedWorld {
    pub schema: String,
    pub world_revision: u64,
    pub observed_at_unix_ms: u64,
    pub bodies: Vec<BodyDescriptor>,
    pub observations: Vec<ObservationEnvelope>,
}

impl ObservedWorld {
    pub fn from_observations(
        world_revision: u64,
        observed_at_unix_ms: u64,
        bodies: Vec<BodyDescriptor>,
        observations: Vec<ObservationEnvelope>,
    ) -> Self {
        Self {
            schema: OBSERVED_WORLD_SCHEMA_V0.into(),
            world_revision,
            observed_at_unix_ms,
            bodies,
            observations,
        }
    }

    pub fn is_read_only(&self) -> bool {
        true
    }
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum ObservedWorldViolation {
    DuplicateBody(String),
    UnknownBody(String),
    UnsupportedObservationSchema(String),
    StaleObservation(String),
    WorldRevisionMismatch { expected: u64, actual: u64 },
    InvalidConfidence(String),
}

/// Aggregate a deterministic, read-only world view from explicit observations.
///
/// This is intentionally a pure P1 boundary: it does not sample hardware,
/// persist state, infer intent, or execute an action. Callers must provide the
/// sampling timestamp and freshness bound explicitly.
pub fn aggregate_observed_world(
    mut bodies: Vec<BodyDescriptor>,
    mut observations: Vec<ObservationEnvelope>,
    now_unix_ms: u64,
    max_age_ms: u64,
) -> Result<ObservedWorld, Vec<ObservedWorldViolation>> {
    let mut violations = Vec::new();
    let mut body_ids = BTreeSet::new();
    for body in &bodies {
        if !body_ids.insert(body.body_id.to_string()) {
            violations.push(ObservedWorldViolation::DuplicateBody(
                body.body_id.to_string(),
            ));
        }
    }

    let expected_revision = observations
        .first()
        .map(|observation| observation.world_revision);
    for observation in &observations {
        let body_id = observation.body_id.to_string();
        if !body_ids.contains(&body_id) {
            violations.push(ObservedWorldViolation::UnknownBody(body_id.clone()));
        }
        if observation.schema != OBSERVATION_SCHEMA_V0 {
            violations.push(ObservedWorldViolation::UnsupportedObservationSchema(
                observation.schema.clone(),
            ));
        }
        if !observation.is_fresh_at(now_unix_ms, max_age_ms) {
            violations.push(ObservedWorldViolation::StaleObservation(body_id));
        }
        if !observation.confidence.is_finite() || !(0.0..=1.0).contains(&observation.confidence) {
            violations.push(ObservedWorldViolation::InvalidConfidence(
                observation.body_id.to_string(),
            ));
        }
        if let Some(expected) = expected_revision {
            if observation.world_revision != expected {
                violations.push(ObservedWorldViolation::WorldRevisionMismatch {
                    expected,
                    actual: observation.world_revision,
                });
            }
        }
    }

    if !violations.is_empty() {
        return Err(violations);
    }

    bodies.sort_by(|left, right| left.body_id.as_str().cmp(right.body_id.as_str()));
    observations.sort_by(|left, right| {
        left.body_id
            .as_str()
            .cmp(right.body_id.as_str())
            .then_with(|| left.source.cmp(&right.source))
            .then_with(|| left.observed_at_unix_ms.cmp(&right.observed_at_unix_ms))
    });
    Ok(ObservedWorld::from_observations(
        expected_revision.unwrap_or_default(),
        observations
            .iter()
            .map(|observation| observation.observed_at_unix_ms)
            .max()
            .unwrap_or_default(),
        bodies,
        observations,
    ))
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct ComponentProposal {
    pub schema: String,
    pub proposal_id: String,
    pub component: String,
    pub body_id: BodyId,
    pub based_on_world_revision: u64,
    pub confidence: f32,
    pub proposal: Value,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct CognitiveDecision {
    pub schema: String,
    pub decision_id: String,
    pub body_id: BodyId,
    pub intent_id: IntentId,
    pub proposal_ids: Vec<String>,
    pub decision: Value,
    pub authority: DecisionAuthority,
}

impl CognitiveDecision {
    pub fn is_non_authoritative(&self) -> bool {
        self.authority == DecisionAuthority::NonAuthoritative
    }
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct AuthorityDecision {
    pub schema: String,
    pub decision_id: String,
    pub cognitive_decision_id: String,
    pub body_id: BodyId,
    pub status: AuthorityDecisionStatus,
    pub boundary: String,
    pub owner_confirmation: bool,
    pub lease_id: Option<LeaseId>,
}

impl AuthorityDecision {
    pub fn permits_projection(&self) -> bool {
        matches!(self.status, AuthorityDecisionStatus::Approved)
    }
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct ProjectionPlan {
    pub schema: String,
    pub plan_id: String,
    pub intent_id: IntentId,
    pub body_id: BodyId,
    pub authority_decision_id: String,
    pub operation: String,
    pub arguments: Value,
    pub precondition: ObservationEnvelope,
    pub reversible: bool,
    pub re_observation_required: bool,
}

impl ProjectionPlan {
    pub fn is_closed_loop(&self) -> bool {
        self.re_observation_required
    }
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct EffectReceipt {
    pub schema: String,
    pub receipt_id: String,
    pub plan_id: String,
    pub intent_id: IntentId,
    pub body_id: BodyId,
    pub status: EffectStatus,
    pub precondition: ObservationEnvelope,
    pub execution: Value,
    pub outcome: Value,
    pub observed_after: Option<ObservationEnvelope>,
    pub verified: bool,
    pub reversible: bool,
    pub rollback: Option<Value>,
}

impl EffectReceipt {
    pub fn is_verified_closed_loop(&self) -> bool {
        self.verified && self.observed_after.is_some()
    }

    pub fn from_action_receipt(receipt: ActionReceipt) -> Self {
        Self {
            schema: EFFECT_RECEIPT_SCHEMA_V0.into(),
            receipt_id: receipt.receipt_id.to_string(),
            plan_id: receipt.intent_id.to_string(),
            intent_id: receipt.intent_id,
            body_id: receipt.body_id,
            status: if receipt.verified {
                EffectStatus::Succeeded
            } else {
                EffectStatus::Failed
            },
            precondition: receipt.precondition,
            execution: receipt.execution,
            outcome: receipt.outcome,
            observed_after: None,
            // The legacy receipt has no post-effect observation.  Its local
            // flag cannot establish the new closed-loop verification claim.
            verified: false,
            reversible: receipt.reversible,
            rollback: receipt.rollback,
        }
    }
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct MemoryUseDecision {
    pub schema: String,
    pub decision_id: String,
    pub mode: MemoryUseMode,
    pub memory_refs: Vec<String>,
    pub reason: String,
    pub canon_promotion_allowed: bool,
}

impl MemoryUseDecision {
    pub fn is_read_only(&self) -> bool {
        !self.canon_promotion_allowed && self.mode != MemoryUseMode::Canonical
    }
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum ContractViolation {
    CognitiveDecisionHasAuthority,
    AuthorityDecisionNotApproved,
    ProjectionMissingReObservation,
    VerifiedReceiptMissingObservation,
    ReceiptBodyMismatch,
    ReceiptObservationSchemaMismatch,
    ReceiptWorldRevisionRegression,
    CanonicalMemoryWithoutPromotion,
}

pub fn validate_projection(
    cognitive: &CognitiveDecision,
    authority: &AuthorityDecision,
    plan: &ProjectionPlan,
) -> Result<(), ContractViolation> {
    if !cognitive.is_non_authoritative() {
        return Err(ContractViolation::CognitiveDecisionHasAuthority);
    }
    if !authority.permits_projection() {
        return Err(ContractViolation::AuthorityDecisionNotApproved);
    }
    if !plan.is_closed_loop() {
        return Err(ContractViolation::ProjectionMissingReObservation);
    }
    Ok(())
}

pub fn validate_effect_receipt(receipt: &EffectReceipt) -> Result<(), ContractViolation> {
    if receipt.verified && receipt.observed_after.is_none() {
        return Err(ContractViolation::VerifiedReceiptMissingObservation);
    }
    Ok(())
}

/// Build a verified receipt only after a caller supplies a post-effect
/// observation.  This function records evidence; it does not execute the plan.
pub fn complete_verified_effect_receipt(
    plan: &ProjectionPlan,
    execution: Value,
    outcome: Value,
    observed_after: ObservationEnvelope,
    rollback: Option<Value>,
) -> Result<EffectReceipt, Vec<ContractViolation>> {
    let mut violations = Vec::new();
    if !plan.is_closed_loop() {
        violations.push(ContractViolation::ProjectionMissingReObservation);
    }
    if observed_after.body_id != plan.body_id {
        violations.push(ContractViolation::ReceiptBodyMismatch);
    }
    if observed_after.schema != OBSERVATION_SCHEMA_V0 {
        violations.push(ContractViolation::ReceiptObservationSchemaMismatch);
    }
    if observed_after.world_revision < plan.precondition.world_revision {
        violations.push(ContractViolation::ReceiptWorldRevisionRegression);
    }
    if !violations.is_empty() {
        return Err(violations);
    }

    Ok(EffectReceipt {
        schema: EFFECT_RECEIPT_SCHEMA_V0.into(),
        receipt_id: format!(
            "effect-receipt-{}-{}",
            plan.plan_id, observed_after.world_revision
        ),
        plan_id: plan.plan_id.clone(),
        intent_id: plan.intent_id.clone(),
        body_id: plan.body_id.clone(),
        status: EffectStatus::Succeeded,
        precondition: plan.precondition.clone(),
        execution,
        outcome,
        observed_after: Some(observed_after),
        verified: true,
        reversible: plan.reversible,
        rollback,
    })
}

pub fn validate_memory_use(decision: &MemoryUseDecision) -> Result<(), ContractViolation> {
    if decision.mode == MemoryUseMode::Canonical && !decision.canon_promotion_allowed {
        return Err(ContractViolation::CanonicalMemoryWithoutPromotion);
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::{ActionReceipt, ReceiptId};
    use serde_json::json;

    fn observation() -> ObservationEnvelope {
        ObservationEnvelope {
            schema: crate::OBSERVATION_SCHEMA_V0.into(),
            body_id: BodyId::from_raw("body-mac"),
            source: "body_status".into(),
            observed_at_unix_ms: 100,
            freshness_ms: 100,
            confidence: 1.0,
            world_revision: 7,
            payload: json!({"cpu_percent": 12}),
        }
    }

    fn cognitive() -> CognitiveDecision {
        CognitiveDecision {
            schema: COGNITIVE_DECISION_SCHEMA_V0.into(),
            decision_id: "decision-1".into(),
            body_id: BodyId::from_raw("body-mac"),
            intent_id: IntentId::from_raw("intent-1"),
            proposal_ids: vec!["proposal-1".into()],
            decision: json!({"operation": "terminal_read"}),
            authority: DecisionAuthority::NonAuthoritative,
        }
    }

    fn authority() -> AuthorityDecision {
        AuthorityDecision {
            schema: AUTHORITY_DECISION_SCHEMA_V0.into(),
            decision_id: "authority-1".into(),
            cognitive_decision_id: "decision-1".into(),
            body_id: BodyId::from_raw("body-mac"),
            status: AuthorityDecisionStatus::Approved,
            boundary: "read_only".into(),
            owner_confirmation: false,
            lease_id: None,
        }
    }

    fn plan() -> ProjectionPlan {
        ProjectionPlan {
            schema: PROJECTION_PLAN_SCHEMA_V0.into(),
            plan_id: "plan-1".into(),
            intent_id: IntentId::from_raw("intent-1"),
            body_id: BodyId::from_raw("body-mac"),
            authority_decision_id: "authority-1".into(),
            operation: "terminal_read".into(),
            arguments: json!({}),
            precondition: observation(),
            reversible: true,
            re_observation_required: true,
        }
    }

    #[test]
    fn projection_requires_non_authoritative_cognition_and_approved_authority() {
        assert!(validate_projection(&cognitive(), &authority(), &plan()).is_ok());

        let mut cognitive = cognitive();
        cognitive.authority = DecisionAuthority::OwnerConfirmed;
        assert_eq!(
            validate_projection(&cognitive, &authority(), &plan()),
            Err(ContractViolation::CognitiveDecisionHasAuthority)
        );
    }

    fn body(id: &str) -> BodyDescriptor {
        BodyDescriptor {
            body_id: BodyId::from_raw(id),
            kind: "host".into(),
            label: id.into(),
            capabilities: vec!["body_status".into()],
            authority_scope: "local".into(),
            online: true,
            last_observed_unix_ms: Some(100),
        }
    }

    fn observation_for(body_id: &str, source: &str, revision: u64) -> ObservationEnvelope {
        ObservationEnvelope {
            schema: OBSERVATION_SCHEMA_V0.into(),
            body_id: BodyId::from_raw(body_id),
            source: source.into(),
            observed_at_unix_ms: 100,
            freshness_ms: 20,
            confidence: 0.9,
            world_revision: revision,
            payload: json!({"ready": true}),
        }
    }

    #[test]
    fn observed_world_aggregation_is_sorted_and_read_only() {
        let world = aggregate_observed_world(
            vec![body("body-b"), body("body-a")],
            vec![
                observation_for("body-b", "memory", 3),
                observation_for("body-a", "cpu", 3),
            ],
            110,
            30,
        )
        .unwrap();
        assert!(world.is_read_only());
        assert_eq!(world.world_revision, 3);
        assert_eq!(world.bodies[0].body_id.as_str(), "body-a");
        assert_eq!(world.observations[0].body_id.as_str(), "body-a");
    }

    #[test]
    fn observed_world_aggregation_rejects_mixed_revision_and_unknown_body() {
        let errors = aggregate_observed_world(
            vec![body("body-a")],
            vec![
                observation_for("body-a", "cpu", 3),
                observation_for("body-b", "ram", 4),
            ],
            110,
            30,
        )
        .unwrap_err();
        assert!(errors.contains(&ObservedWorldViolation::UnknownBody("body-b".into())));
        assert!(
            errors.contains(&ObservedWorldViolation::WorldRevisionMismatch {
                expected: 3,
                actual: 4,
            })
        );
    }

    #[test]
    fn observed_world_aggregation_rejects_stale_and_invalid_observations() {
        let mut observation = observation_for("body-a", "cpu", 3);
        observation.observed_at_unix_ms = 1;
        observation.confidence = 1.5;
        let errors =
            aggregate_observed_world(vec![body("body-a")], vec![observation], 110, 30).unwrap_err();
        assert!(errors.contains(&ObservedWorldViolation::StaleObservation("body-a".into())));
        assert!(errors.contains(&ObservedWorldViolation::InvalidConfidence("body-a".into())));
    }

    #[test]
    fn projection_requires_re_observation() {
        let mut plan = plan();
        plan.re_observation_required = false;
        assert_eq!(
            validate_projection(&cognitive(), &authority(), &plan),
            Err(ContractViolation::ProjectionMissingReObservation)
        );
    }

    #[test]
    fn verified_effect_requires_after_observation() {
        let receipt = EffectReceipt {
            schema: EFFECT_RECEIPT_SCHEMA_V0.into(),
            receipt_id: "receipt-1".into(),
            plan_id: "plan-1".into(),
            intent_id: IntentId::from_raw("intent-1"),
            body_id: BodyId::from_raw("body-mac"),
            status: EffectStatus::Succeeded,
            precondition: observation(),
            execution: json!({"submitted": true}),
            outcome: json!({"status": "ok"}),
            observed_after: None,
            verified: true,
            reversible: true,
            rollback: None,
        };
        assert_eq!(
            validate_effect_receipt(&receipt),
            Err(ContractViolation::VerifiedReceiptMissingObservation)
        );
    }

    #[test]
    fn legacy_action_receipt_adapts_without_claiming_verification() {
        let receipt = ActionReceipt {
            schema: crate::ACTION_RECEIPT_SCHEMA_V0.into(),
            receipt_id: ReceiptId::from_raw("receipt-1"),
            intent_id: IntentId::from_raw("intent-1"),
            body_id: BodyId::from_raw("body-mac"),
            lease_id: None,
            precondition: observation(),
            execution: json!({}),
            outcome: json!({}),
            verified: true,
            reversible: true,
            rollback: None,
        };
        let adapted = EffectReceipt::from_action_receipt(receipt);
        assert!(!adapted.is_verified_closed_loop());
        assert!(validate_effect_receipt(&adapted).is_ok());
    }

    #[test]
    fn canonical_memory_requires_explicit_promotion() {
        let decision = MemoryUseDecision {
            schema: MEMORY_USE_DECISION_SCHEMA_V0.into(),
            decision_id: "memory-decision-1".into(),
            mode: MemoryUseMode::Canonical,
            memory_refs: vec!["memory-key".into()],
            reason: "reviewed evidence".into(),
            canon_promotion_allowed: false,
        };
        assert_eq!(
            validate_memory_use(&decision),
            Err(ContractViolation::CanonicalMemoryWithoutPromotion)
        );
    }

    #[test]
    fn real_reversible_temp_file_trial_requires_after_observation() {
        use std::fs;

        let path = std::env::temp_dir().join(format!("agent-bridge-p4-{}", uuid::Uuid::new_v4()));
        fs::write(&path, b"p4-before").unwrap();
        let observed_contents = fs::read(&path).unwrap();
        assert_eq!(observed_contents, b"p4-before");

        let mut after = observation();
        after.world_revision = 8;
        after.payload = json!({"path": "temporary", "bytes": observed_contents.len()});
        let receipt = complete_verified_effect_receipt(
            &plan(),
            json!({"write": true}),
            json!({"read_back_bytes": observed_contents.len()}),
            after,
            Some(json!({"delete": true})),
        )
        .unwrap();
        assert!(receipt.is_verified_closed_loop());
        assert!(validate_effect_receipt(&receipt).is_ok());

        fs::remove_file(path).unwrap();
    }

    #[test]
    fn verified_receipt_rejects_body_or_revision_mismatch() {
        let mut after = observation();
        after.body_id = BodyId::from_raw("body-other");
        after.world_revision = 0;
        let errors = complete_verified_effect_receipt(&plan(), json!({}), json!({}), after, None)
            .unwrap_err();
        assert!(errors.contains(&ContractViolation::ReceiptBodyMismatch));
        assert!(errors.contains(&ContractViolation::ReceiptWorldRevisionRegression));
    }
}
