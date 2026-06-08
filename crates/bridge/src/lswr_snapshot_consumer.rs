use crate::lswr_snapshot_bridge::{ReadOnlyBridgeSnapshot, ReadOnlyBridgeSnapshotOptions};
use ab_world_core::{Feedback, RollbackRecord, TargetRef, Verdict, Verification};
use serde::{Deserialize, Serialize};
use serde_json::Value;

pub const LSWR_READONLY_BRIDGE_CONSUMER_SUMMARY_SCHEMA: &str =
    "agent_bridge.lswr.readonly_bridge_consumer_summary.v0";

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct ReadOnlyBridgeConsumerSummary {
    pub schema: String,
    pub projection_schema: String,
    pub snapshot_sha256: String,
    pub readback_mode: String,
    pub read_only_confirmed: bool,
    pub safety: ConsumerSafety,
    pub counts: ConsumerCounts,
    pub outcome_counts: ConsumerOutcomeCounts,
    pub query_surfaces: Vec<String>,
    pub verified: Vec<ConsumerVerification>,
    pub not_verified: Vec<ConsumerVerification>,
    pub blocked: Vec<ConsumerVerification>,
    pub feedback: Vec<ConsumerFeedback>,
    pub rollbacks: Vec<ConsumerRollback>,
    pub guidance: Vec<String>,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct ConsumerSafety {
    pub read_only: bool,
    pub mutation_surface: String,
    pub mcp_tool_registration: bool,
    pub snapshot: bool,
    pub query: bool,
    pub patch: bool,
    pub action: bool,
    pub invoke: bool,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct ConsumerCounts {
    pub actions: usize,
    pub events: usize,
    pub verifications: usize,
    pub feedback: usize,
    pub rollback_records: usize,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct ConsumerOutcomeCounts {
    pub verified: Option<usize>,
    pub not_verified: Option<usize>,
    pub blocked: Option<usize>,
    pub feedback_changes_world_verdict: Option<usize>,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct ConsumerVerification {
    pub action_id: Option<String>,
    pub verdict: String,
    pub method: String,
    pub reason: Option<String>,
    pub target_kind: Option<String>,
    pub target_id: Option<String>,
    pub evidence_adapter: String,
    pub evidence_method: String,
    pub evidence_summary: String,
    pub raw_available: bool,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct ConsumerFeedback {
    pub feedback_id: String,
    pub source_event_id: String,
    pub decision: Option<String>,
    pub changes_world_verdict: bool,
    pub target_entities: Vec<String>,
    pub target_actions: Vec<String>,
    pub target_events: Vec<String>,
    pub target_rollback_groups: Vec<String>,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct ConsumerRollback {
    pub rollback_group: String,
    pub actions: Vec<String>,
    pub verification_event_id: Option<String>,
}

pub fn build_readonly_bridge_consumer_summary(
    projection: &ReadOnlyBridgeSnapshot,
) -> ReadOnlyBridgeConsumerSummary {
    let read_only_confirmed = projection.read_only
        && projection.mutation_surface == "none"
        && !projection.mcp_tool_registration
        && !projection.affordances.patch
        && !projection.affordances.action
        && !projection.affordances.invoke;
    let safety = ConsumerSafety {
        read_only: projection.read_only,
        mutation_surface: projection.mutation_surface.clone(),
        mcp_tool_registration: projection.mcp_tool_registration,
        snapshot: projection.affordances.snapshot,
        query: projection.affordances.query,
        patch: projection.affordances.patch,
        action: projection.affordances.action,
        invoke: projection.affordances.invoke,
    };
    let counts = ConsumerCounts {
        actions: projection.counts.actions,
        events: projection.counts.events,
        verifications: projection.counts.verifications,
        feedback: projection.counts.feedback,
        rollback_records: projection.counts.rollback_records,
    };
    let query_surfaces = projection
        .query_surfaces
        .iter()
        .map(|surface| surface.name.clone())
        .collect::<Vec<_>>();

    let Some(snapshot) = projection.snapshot.as_ref() else {
        return ReadOnlyBridgeConsumerSummary {
            schema: LSWR_READONLY_BRIDGE_CONSUMER_SUMMARY_SCHEMA.to_string(),
            projection_schema: projection.schema.clone(),
            snapshot_sha256: projection.snapshot_sha256.clone(),
            readback_mode: "counts_only".to_string(),
            read_only_confirmed,
            safety,
            counts,
            outcome_counts: ConsumerOutcomeCounts {
                verified: None,
                not_verified: None,
                blocked: None,
                feedback_changes_world_verdict: None,
            },
            query_surfaces,
            verified: Vec::new(),
            not_verified: Vec::new(),
            blocked: Vec::new(),
            feedback: Vec::new(),
            rollbacks: Vec::new(),
            guidance: vec![
                "Counts and query surfaces are safe to display.".to_string(),
                "Detailed verification, feedback, and rollback readback requires include_snapshot=true.".to_string(),
            ],
        };
    };

    let mut verified = Vec::new();
    let mut not_verified = Vec::new();
    let mut blocked = Vec::new();
    for verification in &snapshot.verifications {
        match verification.verdict {
            Verdict::Verified => verified.push(consumer_verification(verification)),
            Verdict::NotVerified => not_verified.push(consumer_verification(verification)),
            Verdict::Blocked => blocked.push(consumer_verification(verification)),
        }
    }

    let feedback = snapshot
        .feedback
        .iter()
        .map(consumer_feedback)
        .collect::<Vec<_>>();
    let rollbacks = snapshot
        .rollback_records
        .iter()
        .map(consumer_rollback)
        .collect::<Vec<_>>();
    let feedback_changes_world_verdict = feedback
        .iter()
        .filter(|entry| entry.changes_world_verdict)
        .count();

    ReadOnlyBridgeConsumerSummary {
        schema: LSWR_READONLY_BRIDGE_CONSUMER_SUMMARY_SCHEMA.to_string(),
        projection_schema: projection.schema.clone(),
        snapshot_sha256: projection.snapshot_sha256.clone(),
        readback_mode: "detailed_snapshot".to_string(),
        read_only_confirmed,
        safety,
        counts,
        outcome_counts: ConsumerOutcomeCounts {
            verified: Some(verified.len()),
            not_verified: Some(not_verified.len()),
            blocked: Some(blocked.len()),
            feedback_changes_world_verdict: Some(feedback_changes_world_verdict),
        },
        query_surfaces,
        verified,
        not_verified,
        blocked,
        feedback,
        rollbacks,
        guidance: vec![
            "Verified items come from adapter or runtime evidence only.".to_string(),
            "Human feedback remains feedback and must not alter verification verdicts.".to_string(),
            "Rollback records describe reversible before and after state; this summary does not execute rollback.".to_string(),
        ],
    }
}

pub fn default_consumer_projection_options() -> ReadOnlyBridgeSnapshotOptions {
    ReadOnlyBridgeSnapshotOptions {
        include_snapshot: true,
    }
}

fn consumer_verification(verification: &Verification) -> ConsumerVerification {
    let (target_kind, target_id) = target_pair(verification.verified_to.as_ref());
    ConsumerVerification {
        action_id: verification.action_id.as_ref().map(ToString::to_string),
        verdict: verification.verdict.to_string(),
        method: verification.method.clone(),
        reason: verification.reason.clone(),
        target_kind,
        target_id,
        evidence_adapter: verification.evidence.adapter_kind.clone(),
        evidence_method: verification.evidence.method.clone(),
        evidence_summary: verification.evidence.summary.clone(),
        raw_available: verification.evidence.raw_available,
    }
}

fn consumer_feedback(feedback: &Feedback) -> ConsumerFeedback {
    ConsumerFeedback {
        feedback_id: feedback.feedback_id.to_string(),
        source_event_id: feedback.source_event_id.to_string(),
        decision: extract_decision(&feedback.normalized)
            .or_else(|| extract_decision(&feedback.raw)),
        changes_world_verdict: feedback.changes_world_verdict,
        target_entities: feedback
            .target
            .entities
            .iter()
            .map(ToString::to_string)
            .collect(),
        target_actions: feedback
            .target
            .actions
            .iter()
            .map(ToString::to_string)
            .collect(),
        target_events: feedback
            .target
            .events
            .iter()
            .map(ToString::to_string)
            .collect(),
        target_rollback_groups: feedback
            .target
            .rollback_groups
            .iter()
            .map(ToString::to_string)
            .collect(),
    }
}

fn consumer_rollback(rollback: &RollbackRecord) -> ConsumerRollback {
    ConsumerRollback {
        rollback_group: rollback.rollback_group.to_string(),
        actions: rollback.actions.iter().map(ToString::to_string).collect(),
        verification_event_id: rollback
            .verification_event_id
            .as_ref()
            .map(ToString::to_string),
    }
}

fn target_pair(target: Option<&TargetRef>) -> (Option<String>, Option<String>) {
    target
        .map(|target| (Some(target.kind.clone()), Some(target.id.clone())))
        .unwrap_or((None, None))
}

fn extract_decision(value: &Value) -> Option<String> {
    value
        .get("decision")
        .and_then(Value::as_str)
        .map(ToString::to_string)
}
