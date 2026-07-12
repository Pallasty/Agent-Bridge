//! Deterministic, side-effect-free context-lane admission for shadow evaluation.
//!
//! This module keeps workflow state, interaction memory, source evidence,
//! entity relations, and tool observations distinguishable until a caller has
//! applied scope, temporal, provenance, and authority policy. It deliberately
//! has no MCP surface and grants no write or execution authority.

use std::collections::BTreeSet;

use ab_store::memory_scope_visible_in_context;
use serde::{Deserialize, Serialize};
use thiserror::Error;

pub const CONTEXT_LANE_SCHEMA: &str = "agent_bridge.context_lane_decision.v0";
pub const CONTEXT_LANE_MODE: &str = "shadow_only";

#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum ContextLane {
    WorkflowState,
    InteractionMemory,
    SourceEvidence,
    EntityRelation,
    ToolObservation,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum ContextAuthority {
    Inferred,
    UserStated,
    Observed,
    Verified,
    Authoritative,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct ContextLaneRequest {
    pub scope: String,
    pub as_of: i64,
    #[serde(default)]
    pub citations_required: bool,
    #[serde(default)]
    pub authoritative_answer_required: bool,
    #[serde(default)]
    pub allow_user_stated_as_context: bool,
    pub requested_lanes: BTreeSet<ContextLane>,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct ContextEvidenceItem {
    pub evidence_id: String,
    pub lane: ContextLane,
    pub authority: ContextAuthority,
    /// Opaque handle back to the source/readback packet. Never raw credentials.
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub source_handle: Option<String>,
    /// Optional attributed speaker, system, or other claimant handle.
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub claimant_handle: Option<String>,
    /// `None` and `global` are globally visible in the current single-user
    /// recall model. This is not a tenant/principal ACL.
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub scope: Option<String>,
    pub recorded_at: i64,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub valid_from: Option<i64>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub valid_until: Option<i64>,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum ContextEvidenceUse {
    LoadBearing,
    ContextOnly,
    Rejected,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum ContextRejectionReason {
    LaneNotRequested,
    CrossScope,
    RecordedAfterDecision,
    NotYetValid,
    NoLongerValid,
    MissingSourceHandle,
    MissingClaimantHandle,
    RelationWithoutSource,
    InsufficientAuthority,
    UserStatedContextDisabled,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct ContextEvidenceDecision {
    pub evidence_id: String,
    pub lane: ContextLane,
    pub evidence_use: ContextEvidenceUse,
    pub reasons: Vec<ContextRejectionReason>,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct ContextLaneDecision {
    pub schema: String,
    pub mode: String,
    pub scope: String,
    pub as_of: i64,
    pub evidence: Vec<ContextEvidenceDecision>,
    /// Load-bearing evidence may influence a later answer in shadow analysis.
    /// This contract itself can never persist memory or invoke a tool.
    pub may_write_memory: bool,
    pub may_execute_tools: bool,
}

#[derive(Debug, Clone, PartialEq, Eq, Error)]
pub enum ContextLaneError {
    #[error("request scope must be non-empty")]
    EmptyScope,
    #[error("request as_of must be non-negative, got {0}")]
    InvalidAsOf(i64),
    #[error("requested_lanes must not be empty")]
    NoRequestedLanes,
    #[error("evidence[{index}].evidence_id must be non-empty")]
    EmptyEvidenceId { index: usize },
    #[error("duplicate evidence id: {0}")]
    DuplicateEvidenceId(String),
    #[error("evidence {evidence_id} recorded_at must be non-negative, got {value}")]
    InvalidRecordedAt { evidence_id: String, value: i64 },
    #[error("evidence {evidence_id} has valid_from {valid_from} after valid_until {valid_until}")]
    InvalidValidity {
        evidence_id: String,
        valid_from: i64,
        valid_until: i64,
    },
}

/// Evaluate a bounded context packet without reading, writing, ranking, or
/// calling a model. Invalid packets fail as a whole; valid but inadmissible
/// evidence receives a per-item rejected/context-only decision.
pub fn evaluate_context_lanes(
    request: &ContextLaneRequest,
    evidence: &[ContextEvidenceItem],
) -> Result<ContextLaneDecision, ContextLaneError> {
    validate_request(request)?;
    validate_evidence(evidence)?;

    let evidence = evidence
        .iter()
        .map(|item| evaluate_item(request, item))
        .collect();

    Ok(ContextLaneDecision {
        schema: CONTEXT_LANE_SCHEMA.to_string(),
        mode: CONTEXT_LANE_MODE.to_string(),
        scope: request.scope.clone(),
        as_of: request.as_of,
        evidence,
        may_write_memory: false,
        may_execute_tools: false,
    })
}

fn validate_request(request: &ContextLaneRequest) -> Result<(), ContextLaneError> {
    if request.scope.trim().is_empty() {
        return Err(ContextLaneError::EmptyScope);
    }
    if request.as_of < 0 {
        return Err(ContextLaneError::InvalidAsOf(request.as_of));
    }
    if request.requested_lanes.is_empty() {
        return Err(ContextLaneError::NoRequestedLanes);
    }
    Ok(())
}

fn validate_evidence(evidence: &[ContextEvidenceItem]) -> Result<(), ContextLaneError> {
    let mut ids = BTreeSet::new();
    for (index, item) in evidence.iter().enumerate() {
        let id = item.evidence_id.trim();
        if id.is_empty() {
            return Err(ContextLaneError::EmptyEvidenceId { index });
        }
        if !ids.insert(id.to_string()) {
            return Err(ContextLaneError::DuplicateEvidenceId(id.to_string()));
        }
        if item.recorded_at < 0 {
            return Err(ContextLaneError::InvalidRecordedAt {
                evidence_id: id.to_string(),
                value: item.recorded_at,
            });
        }
        if let (Some(valid_from), Some(valid_until)) = (item.valid_from, item.valid_until) {
            if valid_from > valid_until {
                return Err(ContextLaneError::InvalidValidity {
                    evidence_id: id.to_string(),
                    valid_from,
                    valid_until,
                });
            }
        }
    }
    Ok(())
}

fn evaluate_item(
    request: &ContextLaneRequest,
    item: &ContextEvidenceItem,
) -> ContextEvidenceDecision {
    let mut reasons = Vec::new();

    if !request.requested_lanes.contains(&item.lane) {
        reasons.push(ContextRejectionReason::LaneNotRequested);
    }
    if !scope_visible(item.scope.as_deref(), &request.scope) {
        reasons.push(ContextRejectionReason::CrossScope);
    }
    if item.recorded_at > request.as_of {
        reasons.push(ContextRejectionReason::RecordedAfterDecision);
    }
    if item.valid_from.is_some_and(|from| from > request.as_of) {
        reasons.push(ContextRejectionReason::NotYetValid);
    }
    if item.valid_until.is_some_and(|until| until < request.as_of) {
        reasons.push(ContextRejectionReason::NoLongerValid);
    }

    let has_source = item
        .source_handle
        .as_deref()
        .map(str::trim)
        .is_some_and(|source| !source.is_empty());

    if item.lane == ContextLane::EntityRelation && !has_source {
        reasons.push(ContextRejectionReason::RelationWithoutSource);
    } else if matches!(item.lane, ContextLane::SourceEvidence) && !has_source {
        reasons.push(ContextRejectionReason::MissingSourceHandle);
    }

    let has_claimant = item
        .claimant_handle
        .as_deref()
        .map(str::trim)
        .is_some_and(|claimant| !claimant.is_empty());
    if item.authority == ContextAuthority::UserStated && !has_claimant {
        reasons.push(ContextRejectionReason::MissingClaimantHandle);
    }

    let grounded = request.citations_required || request.authoritative_answer_required;
    let authority_sufficient = item.authority >= ContextAuthority::Verified;
    if grounded && (!authority_sufficient || !has_source) {
        if !authority_sufficient {
            reasons.push(ContextRejectionReason::InsufficientAuthority);
        }
        if !has_source
            && !reasons.contains(&ContextRejectionReason::MissingSourceHandle)
            && !reasons.contains(&ContextRejectionReason::RelationWithoutSource)
        {
            reasons.push(ContextRejectionReason::MissingSourceHandle);
        }
    }

    let only_authority_failure = !reasons.is_empty()
        && reasons.iter().all(|reason| {
            matches!(
                reason,
                ContextRejectionReason::InsufficientAuthority
                    | ContextRejectionReason::MissingSourceHandle
            )
        });

    let user_context_allowed = item.authority == ContextAuthority::UserStated
        && request.allow_user_stated_as_context
        && has_claimant;
    let inferred_context_allowed = item.authority == ContextAuthority::Inferred
        && !matches!(
            item.lane,
            ContextLane::SourceEvidence | ContextLane::EntityRelation
        );

    let evidence_use = if reasons.is_empty() {
        if grounded {
            ContextEvidenceUse::LoadBearing
        } else if matches!(
            item.lane,
            ContextLane::WorkflowState | ContextLane::InteractionMemory
        ) {
            ContextEvidenceUse::ContextOnly
        } else {
            ContextEvidenceUse::LoadBearing
        }
    } else if grounded
        && only_authority_failure
        && (user_context_allowed || inferred_context_allowed)
    {
        ContextEvidenceUse::ContextOnly
    } else {
        if item.authority == ContextAuthority::UserStated
            && !request.allow_user_stated_as_context
            && !reasons.contains(&ContextRejectionReason::UserStatedContextDisabled)
        {
            reasons.push(ContextRejectionReason::UserStatedContextDisabled);
        }
        ContextEvidenceUse::Rejected
    };

    reasons.sort();
    reasons.dedup();
    ContextEvidenceDecision {
        evidence_id: item.evidence_id.clone(),
        lane: item.lane,
        evidence_use,
        reasons,
    }
}

fn scope_visible(item_scope: Option<&str>, request_scope: &str) -> bool {
    memory_scope_visible_in_context(item_scope, request_scope)
}

#[cfg(test)]
mod tests {
    use super::*;

    fn lanes(values: &[ContextLane]) -> BTreeSet<ContextLane> {
        values.iter().copied().collect()
    }

    fn request() -> ContextLaneRequest {
        ContextLaneRequest {
            scope: "project:/work/alpha".to_string(),
            as_of: 100,
            citations_required: true,
            authoritative_answer_required: true,
            allow_user_stated_as_context: true,
            requested_lanes: lanes(&[
                ContextLane::InteractionMemory,
                ContextLane::SourceEvidence,
                ContextLane::EntityRelation,
            ]),
        }
    }

    fn item(id: &str, lane: ContextLane, authority: ContextAuthority) -> ContextEvidenceItem {
        ContextEvidenceItem {
            evidence_id: id.to_string(),
            lane,
            authority,
            source_handle: Some(format!("source:{id}")),
            claimant_handle: None,
            scope: Some("project:/work/alpha".to_string()),
            recorded_at: 90,
            valid_from: Some(80),
            valid_until: None,
        }
    }

    #[test]
    fn verified_sourced_evidence_can_be_load_bearing() {
        let decision = evaluate_context_lanes(
            &request(),
            &[item(
                "policy",
                ContextLane::SourceEvidence,
                ContextAuthority::Verified,
            )],
        )
        .unwrap();
        assert_eq!(decision.mode, CONTEXT_LANE_MODE);
        assert_eq!(
            decision.evidence[0].evidence_use,
            ContextEvidenceUse::LoadBearing
        );
        assert!(!decision.may_write_memory);
        assert!(!decision.may_execute_tools);
    }

    #[test]
    fn user_stated_is_context_only_for_authoritative_answer() {
        let mut claim = item(
            "claim",
            ContextLane::InteractionMemory,
            ContextAuthority::UserStated,
        );
        claim.claimant_handle = Some("user:local".to_string());
        let decision = evaluate_context_lanes(&request(), &[claim]).unwrap();
        assert_eq!(
            decision.evidence[0].evidence_use,
            ContextEvidenceUse::ContextOnly
        );
        assert!(decision.evidence[0]
            .reasons
            .contains(&ContextRejectionReason::InsufficientAuthority));
    }

    #[test]
    fn user_stated_is_rejected_when_context_use_is_disabled() {
        let mut request = request();
        request.allow_user_stated_as_context = false;
        let mut claim = item(
            "claim",
            ContextLane::InteractionMemory,
            ContextAuthority::UserStated,
        );
        claim.claimant_handle = Some("user:local".to_string());
        let decision = evaluate_context_lanes(&request, &[claim]).unwrap();
        assert_eq!(
            decision.evidence[0].evidence_use,
            ContextEvidenceUse::Rejected
        );
        assert!(decision.evidence[0]
            .reasons
            .contains(&ContextRejectionReason::UserStatedContextDisabled));
    }

    #[test]
    fn unattributed_user_statement_fails_closed() {
        let decision = evaluate_context_lanes(
            &request(),
            &[item(
                "anonymous-claim",
                ContextLane::InteractionMemory,
                ContextAuthority::UserStated,
            )],
        )
        .unwrap();
        assert_eq!(
            decision.evidence[0].evidence_use,
            ContextEvidenceUse::Rejected
        );
        assert!(decision.evidence[0]
            .reasons
            .contains(&ContextRejectionReason::MissingClaimantHandle));
    }

    #[test]
    fn relation_without_source_fails_closed() {
        let mut relation = item(
            "relation",
            ContextLane::EntityRelation,
            ContextAuthority::Authoritative,
        );
        relation.source_handle = None;
        let decision = evaluate_context_lanes(&request(), &[relation]).unwrap();
        assert_eq!(
            decision.evidence[0].evidence_use,
            ContextEvidenceUse::Rejected
        );
        assert!(decision.evidence[0]
            .reasons
            .contains(&ContextRejectionReason::RelationWithoutSource));
    }

    #[test]
    fn cross_scope_and_future_evidence_are_rejected() {
        let mut evidence = item(
            "foreign",
            ContextLane::SourceEvidence,
            ContextAuthority::Verified,
        );
        evidence.scope = Some("project:/work/beta".to_string());
        evidence.recorded_at = 101;
        let decision = evaluate_context_lanes(&request(), &[evidence]).unwrap();
        assert_eq!(
            decision.evidence[0].evidence_use,
            ContextEvidenceUse::Rejected
        );
        assert!(decision.evidence[0]
            .reasons
            .contains(&ContextRejectionReason::CrossScope));
        assert!(decision.evidence[0]
            .reasons
            .contains(&ContextRejectionReason::RecordedAfterDecision));
    }

    #[test]
    fn malformed_or_duplicate_evidence_rejects_the_packet() {
        let mut malformed = item(
            "bad",
            ContextLane::SourceEvidence,
            ContextAuthority::Verified,
        );
        malformed.valid_from = Some(101);
        malformed.valid_until = Some(100);
        assert!(matches!(
            evaluate_context_lanes(&request(), &[malformed]),
            Err(ContextLaneError::InvalidValidity { .. })
        ));

        let duplicate = item(
            "dup",
            ContextLane::SourceEvidence,
            ContextAuthority::Verified,
        );
        assert!(matches!(
            evaluate_context_lanes(&request(), &[duplicate.clone(), duplicate]),
            Err(ContextLaneError::DuplicateEvidenceId(_))
        ));
    }
}
