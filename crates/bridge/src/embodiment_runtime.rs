//! Default-off P4 runtime boundary for embodied projection trials.
//!
//! This gate validates plans and records post-effect evidence.  It deliberately
//! has no adapter, MCP registration, process control, or persistence dependency.

use std::collections::BTreeSet;

use ab_world_core::{
    complete_verified_effect_receipt, AttentionDecision, AuthorityDecision, ContractViolation,
    EffectReceipt, ProjectionPlan, ProjectionPlanViolation, ProjectionRequest,
};
use serde_json::Value;

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum EmbodimentRuntimeError {
    Disabled,
    OperationNotAllowlisted(String),
    PlanRejected(Vec<ProjectionPlanViolation>),
    ReceiptRejected(Vec<ContractViolation>),
}

/// A process-local, default-off gate for bounded projection trials.
///
/// The gate is intentionally stateless across restarts.  It cannot execute a
/// plan and it cannot make a plan executable without explicit owner-confirmed
/// authority supplied by the caller.
#[derive(Debug, Clone, Default)]
pub struct EmbodimentRuntimeGate {
    enabled: bool,
    allowed_operations: BTreeSet<String>,
}

impl EmbodimentRuntimeGate {
    pub fn disabled() -> Self {
        Self::default()
    }

    pub fn enabled(allowed_operations: impl IntoIterator<Item = String>) -> Self {
        Self {
            enabled: true,
            allowed_operations: allowed_operations.into_iter().collect(),
        }
    }

    pub fn is_enabled(&self) -> bool {
        self.enabled
    }

    pub fn prepare_plan(
        &self,
        attention: &AttentionDecision,
        authority: &AuthorityDecision,
        request: ProjectionRequest,
    ) -> Result<ProjectionPlan, EmbodimentRuntimeError> {
        if !self.enabled {
            return Err(EmbodimentRuntimeError::Disabled);
        }
        let operation = request.operation.trim().to_string();
        if !self.allowed_operations.contains(&operation) {
            return Err(EmbodimentRuntimeError::OperationNotAllowlisted(operation));
        }
        ab_world_core::plan_owner_confirmed_projection(attention, authority, request)
            .map_err(EmbodimentRuntimeError::PlanRejected)
    }

    pub fn record_verified_effect(
        &self,
        plan: &ProjectionPlan,
        execution: Value,
        outcome: Value,
        observed_after: ab_world_core::ObservationEnvelope,
        rollback: Option<Value>,
    ) -> Result<EffectReceipt, EmbodimentRuntimeError> {
        if !self.enabled {
            return Err(EmbodimentRuntimeError::Disabled);
        }
        if !self.allowed_operations.contains(&plan.operation) {
            return Err(EmbodimentRuntimeError::OperationNotAllowlisted(
                plan.operation.clone(),
            ));
        }
        complete_verified_effect_receipt(plan, execution, outcome, observed_after, rollback)
            .map_err(EmbodimentRuntimeError::ReceiptRejected)
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use ab_world_core::{
        aggregate_observed_world, shadow_attention, AuthorityDecisionStatus, BodyDescriptor,
        BodyId, DecisionAuthority, IntentId, ObservationEnvelope, ShadowAttentionPolicy,
        OBSERVATION_SCHEMA_V0,
    };
    use serde_json::json;

    fn body() -> BodyDescriptor {
        BodyDescriptor {
            body_id: BodyId::from_raw("body-runtime"),
            kind: "host".into(),
            label: "runtime-test".into(),
            capabilities: vec!["terminal_write".into()],
            authority_scope: "local".into(),
            online: true,
            last_observed_unix_ms: Some(100),
        }
    }

    fn observation() -> ObservationEnvelope {
        ObservationEnvelope {
            schema: OBSERVATION_SCHEMA_V0.into(),
            body_id: BodyId::from_raw("body-runtime"),
            source: "body_status".into(),
            observed_at_unix_ms: 100,
            freshness_ms: 20,
            confidence: 1.0,
            world_revision: 9,
            payload: json!({"ready": true}),
        }
    }

    fn attention() -> AttentionDecision {
        let world = aggregate_observed_world(vec![body()], vec![observation()], 110, 30).unwrap();
        shadow_attention(
            &world,
            &BodyId::from_raw("body-runtime"),
            &ShadowAttentionPolicy {
                max_observations: 1,
                required_sources: vec!["body_status".into()],
            },
        )
        .unwrap()
    }

    fn authority() -> AuthorityDecision {
        AuthorityDecision {
            schema: ab_world_core::AUTHORITY_DECISION_SCHEMA_V0.into(),
            decision_id: "runtime-authority".into(),
            cognitive_decision_id: "runtime-cognitive".into(),
            body_id: BodyId::from_raw("body-runtime"),
            status: AuthorityDecisionStatus::Approved,
            boundary: "project_write".into(),
            owner_confirmation: true,
            lease_id: None,
        }
    }

    fn request() -> ProjectionRequest {
        ProjectionRequest {
            intent_id: IntentId::from_raw("runtime-intent"),
            operation: "terminal_write".into(),
            arguments: json!({"keys": "temporary"}),
            precondition: observation(),
            reversible: true,
        }
    }

    #[test]
    fn gate_is_default_off() {
        let gate = EmbodimentRuntimeGate::disabled();
        assert!(!gate.is_enabled());
        assert_eq!(
            gate.prepare_plan(&attention(), &authority(), request()),
            Err(EmbodimentRuntimeError::Disabled)
        );
    }

    #[test]
    fn enabled_gate_allowlists_and_records_only() {
        let gate = EmbodimentRuntimeGate::enabled(vec!["terminal_write".into()]);
        let plan = gate
            .prepare_plan(&attention(), &authority(), request())
            .unwrap();
        let receipt = gate
            .record_verified_effect(
                &plan,
                json!({"submitted": true}),
                json!({"read_back": true}),
                observation(),
                Some(json!({"rollback": "remove temporary marker"})),
            )
            .unwrap();
        assert!(receipt.is_verified_closed_loop());
    }

    #[test]
    fn gate_rejects_unlisted_operation_before_planning() {
        let gate = EmbodimentRuntimeGate::enabled(vec!["body_status".into()]);
        assert_eq!(
            gate.prepare_plan(&attention(), &authority(), request()),
            Err(EmbodimentRuntimeError::OperationNotAllowlisted(
                "terminal_write".into()
            ))
        );
    }

    #[test]
    fn authority_remains_explicit_at_runtime_boundary() {
        let mut authority = authority();
        authority.owner_confirmation = false;
        let gate = EmbodimentRuntimeGate::enabled(vec!["terminal_write".into()]);
        assert!(matches!(
            gate.prepare_plan(&attention(), &authority, request()),
            Err(EmbodimentRuntimeError::PlanRejected(_))
        ));
        assert_eq!(DecisionAuthority::NonAuthoritative, attention().authority);
    }
}
