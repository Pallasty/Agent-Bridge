//! Provider-neutral contracts for visual and structured-world projection.
//!
//! These records describe a request and its evidence boundary only. They do
//! not select a provider, execute an engine, call MCP, or grant authority.

use serde::{Deserialize, Serialize};
use serde_json::Value;

pub const PROJECTION_REQUEST_ENVELOPE_SCHEMA_V0: &str =
    "agent_bridge.projection_request_envelope.v0";
pub const ENGINE_EXECUTION_RECEIPT_SCHEMA_V0: &str = "agent_bridge.engine_execution_receipt.v0";

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum ProjectionEvidenceClass {
    #[serde(rename = "simulated.generated")]
    SimulatedGenerated,
    #[serde(rename = "simulated.executed")]
    SimulatedExecuted,
    #[serde(rename = "observed.real")]
    ObservedReal,
}

impl ProjectionEvidenceClass {
    pub fn is_simulated(self) -> bool {
        matches!(self, Self::SimulatedGenerated | Self::SimulatedExecuted)
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum ProjectionVerdict {
    Verified,
    NotVerified,
    Blocked,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct ProjectionRequestEnvelope {
    pub schema: String,
    pub request_id: String,
    #[serde(default)]
    pub intent_id: Option<String>,
    #[serde(default)]
    pub source_world_id: Option<String>,
    pub source_world_revision: u64,
    pub provider_id: String,
    pub requested_outputs: Vec<String>,
    #[serde(default)]
    pub constraints: Value,
    #[serde(default)]
    pub authority_ref: Option<String>,
    pub created_at_unix_ms: u64,
}

impl ProjectionRequestEnvelope {
    pub fn validate(&self) -> Result<(), Vec<ProjectionContractViolation>> {
        let mut violations = Vec::new();
        if self.schema != PROJECTION_REQUEST_ENVELOPE_SCHEMA_V0 {
            violations.push(ProjectionContractViolation::SchemaMismatch {
                expected: PROJECTION_REQUEST_ENVELOPE_SCHEMA_V0.into(),
                actual: self.schema.clone(),
            });
        }
        if self.request_id.trim().is_empty() {
            violations.push(ProjectionContractViolation::EmptyField("request_id"));
        }
        if self.provider_id.trim().is_empty() {
            violations.push(ProjectionContractViolation::EmptyField("provider_id"));
        }
        if self.requested_outputs.is_empty()
            || self
                .requested_outputs
                .iter()
                .any(|output| output.trim().is_empty())
        {
            violations.push(ProjectionContractViolation::EmptyRequestedOutput);
        }
        if self.created_at_unix_ms == 0 {
            violations.push(ProjectionContractViolation::MissingTimestamp);
        }
        if violations.is_empty() {
            Ok(())
        } else {
            Err(violations)
        }
    }
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct ProjectionProvider {
    pub id: String,
    pub engine: String,
    pub engine_version: String,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct ProjectionActionEvidence {
    pub op: String,
    pub entity: String,
    pub applied: bool,
    #[serde(default, alias = "before_model_hash")]
    pub before_state_hash: Option<String>,
    #[serde(default, alias = "after_model_hash")]
    pub after_state_hash: Option<String>,
    #[serde(default)]
    pub before_world_revision: Option<Value>,
    #[serde(default)]
    pub after_world_revision: Option<Value>,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct ProjectionRollbackEvidence {
    pub requested: bool,
    pub applied: bool,
    pub verified: bool,
    #[serde(default)]
    pub reason: String,
    #[serde(default)]
    pub group_id: Option<String>,
    #[serde(default)]
    pub model_restored: bool,
    #[serde(default)]
    pub render_restored: bool,
    #[serde(default)]
    pub probe_checkpoint_restored: bool,
    #[serde(default, alias = "before_model_hash")]
    pub before_state_hash: Option<String>,
    #[serde(default, alias = "restored_model_hash")]
    pub restored_state_hash: Option<String>,
    #[serde(default, alias = "before_render_hash")]
    pub before_render_hash: Option<String>,
    #[serde(default, alias = "restored_render_hash")]
    pub restored_render_hash: Option<String>,
    #[serde(default)]
    pub visibility: Option<Value>,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct ProjectionTruthBoundary {
    pub external_world_effect_claimed: bool,
    pub generated_visual_claimed: bool,
    #[serde(default)]
    pub verified_to: Option<String>,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct EngineExecutionReceipt {
    pub schema: String,
    pub source: String,
    pub evidence_class: ProjectionEvidenceClass,
    pub provider: ProjectionProvider,
    pub request_id: String,
    pub receipt_id: String,
    pub verdict: ProjectionVerdict,
    pub verified: bool,
    #[serde(default)]
    pub reason: String,
    pub action: ProjectionActionEvidence,
    #[serde(default)]
    pub rollback: Option<ProjectionRollbackEvidence>,
    pub truth_boundary: ProjectionTruthBoundary,
}

impl EngineExecutionReceipt {
    pub fn validate(&self) -> Result<(), Vec<ProjectionContractViolation>> {
        let mut violations = Vec::new();
        if self.schema != ENGINE_EXECUTION_RECEIPT_SCHEMA_V0 {
            violations.push(ProjectionContractViolation::SchemaMismatch {
                expected: ENGINE_EXECUTION_RECEIPT_SCHEMA_V0.into(),
                actual: self.schema.clone(),
            });
        }
        if self.source.trim().is_empty() {
            violations.push(ProjectionContractViolation::EmptyField("source"));
        }
        if self.request_id.trim().is_empty() {
            violations.push(ProjectionContractViolation::EmptyField("request_id"));
        }
        if self.receipt_id.trim().is_empty() {
            violations.push(ProjectionContractViolation::EmptyField("receipt_id"));
        }
        if self.provider.id.trim().is_empty() || self.provider.engine.trim().is_empty() {
            violations.push(ProjectionContractViolation::EmptyProvider);
        }
        if self.verified != (self.verdict == ProjectionVerdict::Verified) {
            violations.push(ProjectionContractViolation::VerdictMismatch);
        }
        if self.verified && self.truth_boundary.verified_to.is_none() {
            violations.push(ProjectionContractViolation::VerifiedMissingBoundary);
        }
        if !self.verified && self.truth_boundary.verified_to.is_some() {
            violations.push(ProjectionContractViolation::UnverifiedHasBoundary);
        }
        if self.evidence_class == ProjectionEvidenceClass::SimulatedGenerated && self.verified {
            violations.push(ProjectionContractViolation::GeneratedCannotBeVerified);
        }
        if self.evidence_class == ProjectionEvidenceClass::SimulatedExecuted
            && self.truth_boundary.external_world_effect_claimed
        {
            violations.push(ProjectionContractViolation::SimulatedExternalEffect);
        }
        if let Some(rollback) = &self.rollback {
            if rollback.requested
                && rollback.applied
                && rollback.verified
                && !(rollback.model_restored
                    && rollback.render_restored
                    && rollback.probe_checkpoint_restored)
            {
                violations.push(ProjectionContractViolation::RollbackEvidenceIncomplete);
            }
        }
        if violations.is_empty() {
            Ok(())
        } else {
            Err(violations)
        }
    }

    pub fn is_provider_neutral_verified(&self) -> bool {
        self.validate().is_ok() && self.verified
    }
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum ProjectionContractViolation {
    SchemaMismatch { expected: String, actual: String },
    EmptyField(&'static str),
    EmptyRequestedOutput,
    MissingTimestamp,
    EmptyProvider,
    VerdictMismatch,
    VerifiedMissingBoundary,
    UnverifiedHasBoundary,
    GeneratedCannotBeVerified,
    SimulatedExternalEffect,
    RollbackEvidenceIncomplete,
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    fn request() -> ProjectionRequestEnvelope {
        ProjectionRequestEnvelope {
            schema: PROJECTION_REQUEST_ENVELOPE_SCHEMA_V0.into(),
            request_id: "request-1".into(),
            intent_id: Some("intent-1".into()),
            source_world_id: Some("world-1".into()),
            source_world_revision: 7,
            provider_id: "onsen.godot".into(),
            requested_outputs: vec!["structured_world".into(), "render_observation".into()],
            constraints: json!({"rollback": true}),
            authority_ref: None,
            created_at_unix_ms: 1,
        }
    }

    fn receipt() -> EngineExecutionReceipt {
        EngineExecutionReceipt {
            schema: ENGINE_EXECUTION_RECEIPT_SCHEMA_V0.into(),
            source: "onsen_godot_engine_execution_receipt_v0".into(),
            evidence_class: ProjectionEvidenceClass::SimulatedExecuted,
            provider: ProjectionProvider {
                id: "onsen.godot.live_semantic_world_host".into(),
                engine: "godot".into(),
                engine_version: "4.6.3-stable".into(),
            },
            request_id: "request-1".into(),
            receipt_id: "receipt-1".into(),
            verdict: ProjectionVerdict::Verified,
            verified: true,
            reason: String::new(),
            action: ProjectionActionEvidence {
                op: "move".into(),
                entity: "checkout_counter".into(),
                applied: true,
                before_state_hash: Some("before".into()),
                after_state_hash: Some("after".into()),
                before_world_revision: Some(json!(7)),
                after_world_revision: Some(json!(8)),
            },
            rollback: Some(ProjectionRollbackEvidence {
                requested: true,
                applied: true,
                verified: true,
                reason: String::new(),
                group_id: Some("rollback-1".into()),
                model_restored: true,
                render_restored: true,
                probe_checkpoint_restored: true,
                before_state_hash: Some("before".into()),
                restored_state_hash: Some("before".into()),
                before_render_hash: Some("render-before".into()),
                restored_render_hash: Some("render-before".into()),
                visibility: Some(json!({"verified": true})),
            }),
            truth_boundary: ProjectionTruthBoundary {
                external_world_effect_claimed: false,
                generated_visual_claimed: false,
                verified_to: Some("onsen_godot_live_root_viewport".into()),
            },
        }
    }

    #[test]
    fn request_is_valid_without_authorizing_execution() {
        assert!(request().validate().is_ok());
        assert!(request().authority_ref.is_none());
    }

    #[test]
    fn request_rejects_empty_identity_and_output() {
        let mut invalid = request();
        invalid.request_id = " ".into();
        invalid.requested_outputs = vec![String::new()];
        let errors = invalid.validate().unwrap_err();
        assert!(errors.contains(&ProjectionContractViolation::EmptyField("request_id")));
        assert!(errors.contains(&ProjectionContractViolation::EmptyRequestedOutput));
    }

    #[test]
    fn onsen_shaped_receipt_round_trips_and_validates() {
        let value = serde_json::to_value(receipt()).unwrap();
        let decoded: EngineExecutionReceipt = serde_json::from_value(value).unwrap();
        assert!(decoded.is_provider_neutral_verified());
        assert_eq!(decoded.action.before_state_hash.as_deref(), Some("before"));
    }

    #[test]
    fn generated_visual_cannot_be_promoted_to_execution_truth() {
        let mut invalid = receipt();
        invalid.evidence_class = ProjectionEvidenceClass::SimulatedGenerated;
        let errors = invalid.validate().unwrap_err();
        assert!(errors.contains(&ProjectionContractViolation::GeneratedCannotBeVerified));
    }

    #[test]
    fn simulated_receipt_cannot_claim_external_effects() {
        let mut invalid = receipt();
        invalid.truth_boundary.external_world_effect_claimed = true;
        let errors = invalid.validate().unwrap_err();
        assert!(errors.contains(&ProjectionContractViolation::SimulatedExternalEffect));
    }

    #[test]
    fn failed_receipt_cannot_keep_verified_to() {
        let mut invalid = receipt();
        invalid.verdict = ProjectionVerdict::NotVerified;
        invalid.verified = false;
        let errors = invalid.validate().unwrap_err();
        assert!(errors.contains(&ProjectionContractViolation::UnverifiedHasBoundary));
    }

    #[test]
    fn verified_rollback_requires_all_restore_evidence() {
        let mut invalid = receipt();
        invalid.rollback.as_mut().unwrap().render_restored = false;
        let errors = invalid.validate().unwrap_err();
        assert!(errors.contains(&ProjectionContractViolation::RollbackEvidenceIncomplete));
    }
}
