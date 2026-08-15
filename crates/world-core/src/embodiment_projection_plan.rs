//! P3 owner-confirmed projection planning.
//!
//! This module creates a bounded plan only.  It never submits a command,
//! acquires a lease, calls an adapter, or claims that an effect occurred.

use serde::{Deserialize, Serialize};
use serde_json::Value;

use crate::{
    AttentionDecision, AuthorityDecision, AuthorityDecisionStatus, IntentId, ObservationEnvelope,
    ProjectionPlan, ATTENTION_DECISION_SCHEMA_V0, OBSERVATION_SCHEMA_V0,
};

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct ProjectionRequest {
    pub intent_id: IntentId,
    pub operation: String,
    pub arguments: Value,
    pub precondition: ObservationEnvelope,
    pub reversible: bool,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum ProjectionPlanViolation {
    AttentionNotShadow,
    AttentionHasAuthority,
    AttentionSchemaMismatch(String),
    OwnerConfirmationRequired,
    AuthorityNotApproved(AuthorityDecisionStatus),
    BodyMismatch,
    WorldRevisionMismatch { attention: u64, precondition: u64 },
    UnsupportedPreconditionSchema(String),
    EmptyOperation,
}

/// Compile a human-confirmed, re-observation-bound projection plan.
///
/// `authority.owner_confirmation` is deliberately required even when the
/// authority status is approved.  This keeps P3 distinct from shadow output:
/// no implicit promotion from attention to action is possible.
pub fn plan_owner_confirmed_projection(
    attention: &AttentionDecision,
    authority: &AuthorityDecision,
    request: ProjectionRequest,
) -> Result<ProjectionPlan, Vec<ProjectionPlanViolation>> {
    let mut violations = Vec::new();
    if attention.mode != "shadow" {
        violations.push(ProjectionPlanViolation::AttentionNotShadow);
    }
    if !attention.is_non_authoritative() {
        violations.push(ProjectionPlanViolation::AttentionHasAuthority);
    }
    if attention.schema != ATTENTION_DECISION_SCHEMA_V0 {
        violations.push(ProjectionPlanViolation::AttentionSchemaMismatch(
            attention.schema.clone(),
        ));
    }
    if !authority.owner_confirmation {
        violations.push(ProjectionPlanViolation::OwnerConfirmationRequired);
    }
    if authority.status != AuthorityDecisionStatus::Approved {
        violations.push(ProjectionPlanViolation::AuthorityNotApproved(
            authority.status,
        ));
    }
    if attention.body_id != request.precondition.body_id || authority.body_id != attention.body_id {
        violations.push(ProjectionPlanViolation::BodyMismatch);
    }
    if attention.input_world_revision != request.precondition.world_revision {
        violations.push(ProjectionPlanViolation::WorldRevisionMismatch {
            attention: attention.input_world_revision,
            precondition: request.precondition.world_revision,
        });
    }
    if request.precondition.schema != OBSERVATION_SCHEMA_V0 {
        violations.push(ProjectionPlanViolation::UnsupportedPreconditionSchema(
            request.precondition.schema.clone(),
        ));
    }
    let operation = request.operation.trim();
    if operation.is_empty() {
        violations.push(ProjectionPlanViolation::EmptyOperation);
    }
    if !violations.is_empty() {
        return Err(violations);
    }

    Ok(ProjectionPlan {
        schema: crate::PROJECTION_PLAN_SCHEMA_V0.into(),
        plan_id: format!(
            "projection-plan-{}-{}-{}",
            authority.decision_id, request.intent_id, attention.input_world_revision
        ),
        intent_id: request.intent_id,
        body_id: request.precondition.body_id.clone(),
        authority_decision_id: authority.decision_id.clone(),
        operation: operation.into(),
        arguments: request.arguments,
        precondition: request.precondition,
        reversible: request.reversible,
        re_observation_required: true,
    })
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::{
        aggregate_observed_world, shadow_attention, BodyDescriptor, BodyId, DecisionAuthority,
        ShadowAttentionPolicy, OBSERVATION_SCHEMA_V0,
    };
    use serde_json::json;

    fn body(id: &str) -> BodyDescriptor {
        BodyDescriptor {
            body_id: BodyId::from_raw(id),
            kind: "host".into(),
            label: id.into(),
            capabilities: vec!["terminal_write".into()],
            authority_scope: "local".into(),
            online: true,
            last_observed_unix_ms: Some(100),
        }
    }

    fn attention() -> AttentionDecision {
        let world = aggregate_observed_world(
            vec![body("body-a")],
            vec![ObservationEnvelope {
                schema: OBSERVATION_SCHEMA_V0.into(),
                body_id: BodyId::from_raw("body-a"),
                source: "cpu".into(),
                observed_at_unix_ms: 100,
                freshness_ms: 20,
                confidence: 1.0,
                world_revision: 4,
                payload: json!({"ready": true}),
            }],
            110,
            30,
        )
        .unwrap();
        shadow_attention(
            &world,
            &BodyId::from_raw("body-a"),
            &ShadowAttentionPolicy {
                max_observations: 1,
                required_sources: vec!["cpu".into()],
            },
        )
        .unwrap()
    }

    fn authority(owner_confirmation: bool) -> AuthorityDecision {
        AuthorityDecision {
            schema: crate::AUTHORITY_DECISION_SCHEMA_V0.into(),
            decision_id: "authority-1".into(),
            cognitive_decision_id: "cognitive-1".into(),
            body_id: BodyId::from_raw("body-a"),
            status: AuthorityDecisionStatus::Approved,
            boundary: "project_write".into(),
            owner_confirmation,
            lease_id: None,
        }
    }

    fn request() -> ProjectionRequest {
        ProjectionRequest {
            intent_id: IntentId::from_raw("intent-1"),
            operation: "terminal_write".into(),
            arguments: json!({"keys": "echo ready"}),
            precondition: ObservationEnvelope {
                schema: OBSERVATION_SCHEMA_V0.into(),
                body_id: BodyId::from_raw("body-a"),
                source: "cpu".into(),
                observed_at_unix_ms: 100,
                freshness_ms: 20,
                confidence: 1.0,
                world_revision: 4,
                payload: json!({"ready": true}),
            },
            reversible: true,
        }
    }

    #[test]
    fn owner_confirmed_projection_is_plan_only_and_re_observation_bound() {
        let plan =
            plan_owner_confirmed_projection(&attention(), &authority(true), request()).unwrap();
        assert_eq!(plan.operation, "terminal_write");
        assert_eq!(plan.authority_decision_id, "authority-1");
        assert!(plan.re_observation_required);
    }

    #[test]
    fn projection_requires_explicit_owner_confirmation() {
        let errors = plan_owner_confirmed_projection(&attention(), &authority(false), request())
            .unwrap_err();
        assert!(errors.contains(&ProjectionPlanViolation::OwnerConfirmationRequired));
    }

    #[test]
    fn projection_rejects_stale_lineage() {
        let mut request = request();
        request.precondition.world_revision = 3;
        let errors =
            plan_owner_confirmed_projection(&attention(), &authority(true), request).unwrap_err();
        assert!(
            errors.contains(&ProjectionPlanViolation::WorldRevisionMismatch {
                attention: 4,
                precondition: 3,
            })
        );
    }

    #[test]
    fn projection_rejects_non_approved_authority_and_empty_operation() {
        let mut authority = authority(true);
        authority.status = AuthorityDecisionStatus::PendingOwner;
        let mut request = request();
        request.operation = "  ".into();
        let errors =
            plan_owner_confirmed_projection(&attention(), &authority, request).unwrap_err();
        assert!(
            errors.contains(&ProjectionPlanViolation::AuthorityNotApproved(
                AuthorityDecisionStatus::PendingOwner,
            ))
        );
        assert!(errors.contains(&ProjectionPlanViolation::EmptyOperation));
    }

    #[test]
    fn projection_never_promotes_attention_authority() {
        let mut attention = attention();
        attention.authority = DecisionAuthority::OwnerConfirmed;
        let errors =
            plan_owner_confirmed_projection(&attention, &authority(true), request()).unwrap_err();
        assert!(errors.contains(&ProjectionPlanViolation::AttentionHasAuthority));
    }
}
