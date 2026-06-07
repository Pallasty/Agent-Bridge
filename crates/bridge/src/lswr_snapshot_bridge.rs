use ab_world_core::{
    WorldCoreError, WorldLedger, WorldLedgerSnapshot, SCHEMA_ACTION_QUERY, SCHEMA_EVENT_QUERY,
    SCHEMA_EVIDENCE_QUERY, SCHEMA_FEEDBACK_QUERY, SCHEMA_LEDGER_SNAPSHOT, SCHEMA_ROLLBACK_QUERY,
};
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use thiserror::Error;

pub const LSWR_READONLY_BRIDGE_SNAPSHOT_SCHEMA: &str =
    "agent_bridge.lswr.readonly_bridge_snapshot.v0";

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub struct ReadOnlyBridgeSnapshotOptions {
    pub include_snapshot: bool,
}

impl Default for ReadOnlyBridgeSnapshotOptions {
    fn default() -> Self {
        Self {
            include_snapshot: false,
        }
    }
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct ReadOnlyBridgeSnapshot {
    pub schema: String,
    pub snapshot_schema: String,
    pub snapshot_sha256: String,
    pub read_only: bool,
    pub mutation_surface: String,
    pub mcp_tool_registration: bool,
    pub affordances: ReadOnlyBridgeAffordances,
    pub counts: ReadOnlyBridgeCounts,
    pub query_surfaces: Vec<ReadOnlyQuerySurface>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub snapshot: Option<WorldLedgerSnapshot>,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct ReadOnlyBridgeAffordances {
    pub snapshot: bool,
    pub query: bool,
    pub patch: bool,
    pub action: bool,
    pub invoke: bool,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct ReadOnlyBridgeCounts {
    pub actions: usize,
    pub events: usize,
    pub verifications: usize,
    pub feedback: usize,
    pub rollback_records: usize,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct ReadOnlyQuerySurface {
    pub name: String,
    pub schema: String,
}

#[derive(Debug, Error)]
pub enum LswrBridgeSnapshotError {
    #[error("failed to encode ledger snapshot: {0}")]
    SnapshotEncode(#[from] serde_json::Error),

    #[error("invalid ledger snapshot: {0}")]
    SnapshotImport(#[from] WorldCoreError),
}

pub fn build_readonly_bridge_snapshot(
    snapshot: WorldLedgerSnapshot,
    options: ReadOnlyBridgeSnapshotOptions,
) -> Result<ReadOnlyBridgeSnapshot, LswrBridgeSnapshotError> {
    let snapshot_sha256 = hash_snapshot(&snapshot)?;
    let ledger = WorldLedger::from_snapshot(snapshot.clone())?;

    Ok(ReadOnlyBridgeSnapshot {
        schema: LSWR_READONLY_BRIDGE_SNAPSHOT_SCHEMA.to_string(),
        snapshot_schema: SCHEMA_LEDGER_SNAPSHOT.to_string(),
        snapshot_sha256,
        read_only: true,
        mutation_surface: "none".to_string(),
        mcp_tool_registration: false,
        affordances: ReadOnlyBridgeAffordances {
            snapshot: true,
            query: true,
            patch: false,
            action: false,
            invoke: false,
        },
        counts: ReadOnlyBridgeCounts {
            actions: ledger.actions().len(),
            events: ledger.events().len(),
            verifications: ledger.verifications().len(),
            feedback: ledger.feedback().len(),
            rollback_records: ledger.rollback_groups().count(),
        },
        query_surfaces: readonly_query_surfaces(),
        snapshot: options.include_snapshot.then_some(snapshot),
    })
}

pub fn readonly_query_surfaces() -> Vec<ReadOnlyQuerySurface> {
    vec![
        ReadOnlyQuerySurface {
            name: "world.actions.query".to_string(),
            schema: SCHEMA_ACTION_QUERY.to_string(),
        },
        ReadOnlyQuerySurface {
            name: "world.events.query".to_string(),
            schema: SCHEMA_EVENT_QUERY.to_string(),
        },
        ReadOnlyQuerySurface {
            name: "world.evidence.query".to_string(),
            schema: SCHEMA_EVIDENCE_QUERY.to_string(),
        },
        ReadOnlyQuerySurface {
            name: "world.feedback.query".to_string(),
            schema: SCHEMA_FEEDBACK_QUERY.to_string(),
        },
        ReadOnlyQuerySurface {
            name: "world.rollbacks.query".to_string(),
            schema: SCHEMA_ROLLBACK_QUERY.to_string(),
        },
    ]
}

fn hash_snapshot(snapshot: &WorldLedgerSnapshot) -> Result<String, serde_json::Error> {
    let encoded = serde_json::to_vec(snapshot)?;
    let digest = Sha256::digest(encoded);
    Ok(format!("sha256:{digest:x}"))
}

#[cfg(test)]
mod tests {
    use super::*;
    use ab_world_core::{
        Action, ActionId, AdapterEvidence, AuthorityMode, BranchId, EntityId, Event, EventId,
        EventProvenance, Feedback, Participant, ParticipantId, RollbackGroupId, RollbackRecord,
        TargetRef, Verdict, Verification, WorldId, SCHEMA_EVENT,
    };
    use serde_json::json;

    #[test]
    fn readonly_bridge_snapshot_reports_counts_and_blocks_mutation_affordances() {
        let snapshot = fixture_snapshot();

        let projection =
            build_readonly_bridge_snapshot(snapshot, ReadOnlyBridgeSnapshotOptions::default())
                .expect("readonly bridge snapshot");

        assert_eq!(projection.schema, LSWR_READONLY_BRIDGE_SNAPSHOT_SCHEMA);
        assert_eq!(projection.snapshot_schema, SCHEMA_LEDGER_SNAPSHOT);
        assert!(projection.snapshot_sha256.starts_with("sha256:"));
        assert_eq!(projection.snapshot_sha256.len(), "sha256:".len() + 64);
        assert!(projection.read_only);
        assert_eq!(projection.mutation_surface, "none");
        assert!(!projection.mcp_tool_registration);
        assert!(projection.affordances.snapshot);
        assert!(projection.affordances.query);
        assert!(!projection.affordances.patch);
        assert!(!projection.affordances.action);
        assert!(!projection.affordances.invoke);
        assert_eq!(projection.counts.actions, 1);
        assert_eq!(projection.counts.events, 2);
        assert_eq!(projection.counts.verifications, 1);
        assert_eq!(projection.counts.feedback, 1);
        assert_eq!(projection.counts.rollback_records, 1);
        assert!(projection.snapshot.is_none());
        assert_eq!(
            projection
                .query_surfaces
                .iter()
                .map(|surface| surface.name.as_str())
                .collect::<Vec<_>>(),
            vec![
                "world.actions.query",
                "world.events.query",
                "world.evidence.query",
                "world.feedback.query",
                "world.rollbacks.query"
            ]
        );
    }

    #[test]
    fn readonly_bridge_snapshot_can_include_the_raw_snapshot_when_requested() {
        let snapshot = fixture_snapshot();

        let projection = build_readonly_bridge_snapshot(
            snapshot.clone(),
            ReadOnlyBridgeSnapshotOptions {
                include_snapshot: true,
            },
        )
        .expect("readonly bridge snapshot");

        assert_eq!(projection.snapshot, Some(snapshot));
    }

    #[test]
    fn readonly_bridge_snapshot_rejects_invalid_snapshot_imports() {
        let mut snapshot = fixture_snapshot();
        snapshot.schema = "agent_bridge.lswr.ledger_snapshot.v999".to_string();

        let err =
            build_readonly_bridge_snapshot(snapshot, ReadOnlyBridgeSnapshotOptions::default())
                .expect_err("invalid schema");

        assert!(matches!(
            err,
            LswrBridgeSnapshotError::SnapshotImport(WorldCoreError::InvalidLedgerSnapshotSchema(_))
        ));
    }

    fn fixture_snapshot() -> WorldLedgerSnapshot {
        let world_id = WorldId::from_raw("world:readonly_bridge");
        let branch_id = BranchId::from_raw("branch:readonly_bridge");
        let entity_id = EntityId::from_raw("entity:cube_readonly_bridge");
        let action_id = ActionId::from_raw("action:move_cube_readonly_bridge");
        let result_event_id = EventId::from_raw("event:move_cube_readonly_bridge_result");
        let human_event_id = EventId::from_raw("event:move_cube_readonly_bridge_accept");
        let rollback_group = RollbackGroupId::from_raw("rollback:move_cube_readonly_bridge");

        let mut action = Action::new(
            "entity.move",
            Participant::ai(
                ParticipantId::from_raw("ai:codex"),
                AuthorityMode::Autonomous,
            ),
        );
        action.action_id = action_id.clone();
        action.target_refs.push(TargetRef::entity(&entity_id));
        action.expected_effect = json!({
            "entity_present": entity_id.as_str(),
            "semantic_position": [2.0, 0.0, -1.0],
            "human_visible": true
        });
        action.rollback_group = Some(rollback_group.clone());

        let verification = Verification::new(
            Some(action_id.clone()),
            Verdict::Verified,
            None,
            "semantic_state_query",
            Some(TargetRef::entity(&entity_id)),
            AdapterEvidence::new(
                "semantic_scene",
                "semantic_state_query",
                "semantic state reports the expected transform",
                true,
                json!({
                    "entity_present": true,
                    "position": [2.0, 0.0, -1.0]
                }),
            ),
        )
        .expect("verification");

        let mut result_event = Event::new(
            "runtime.action_result",
            world_id.clone(),
            Participant::runtime(ParticipantId::from_raw("runtime:semantic_scene"), "core"),
            EventProvenance {
                adapter: Some("semantic_scene".to_string()),
                source_schema: Some(SCHEMA_EVENT.to_string()),
                raw_available: true,
            },
        );
        result_event.event_id = result_event_id.clone();
        result_event.branch_id = Some(branch_id);
        result_event.refs.entities.push(entity_id.clone());
        result_event.refs.actions.push(action_id.clone());
        result_event
            .refs
            .rollback_groups
            .push(rollback_group.clone());
        result_event.payload = json!({
            "action_type": "entity.move",
            "applied": true,
            "semantic_position": [2.0, 0.0, -1.0]
        });
        result_event.verification = Some(verification);

        let mut human_event = Event::new(
            "human.accept",
            world_id,
            Participant::human(ParticipantId::from_raw("human:owner"), "core_review"),
            EventProvenance {
                adapter: Some("core_review".to_string()),
                source_schema: Some(SCHEMA_EVENT.to_string()),
                raw_available: true,
            },
        );
        human_event.event_id = human_event_id.clone();
        human_event.refs.events.push(result_event_id.clone());
        human_event.refs.actions.push(action_id.clone());
        human_event.refs.entities.push(entity_id.clone());
        human_event.payload = json!({
            "decision": "accept",
            "does_not_change_verification": true
        });

        let mut feedback = Feedback::new(human_event_id);
        feedback.target.events.push(result_event_id.clone());
        feedback.target.actions.push(action_id.clone());
        feedback.target.entities.push(entity_id);
        feedback.target.rollback_groups.push(rollback_group.clone());
        feedback.raw = json!({"decision": "accept", "surface": "core_review"});
        feedback.normalized = json!({"decision": "accept", "does_not_change_verification": true});

        let mut rollback = RollbackRecord::new(
            rollback_group,
            json!({"entities": [{"entity_id": "entity:cube_readonly_bridge", "position": [0.0, 0.0, 0.0]}]}),
            json!({"entities": [{"entity_id": "entity:cube_readonly_bridge", "position": [2.0, 0.0, -1.0]}]}),
        );
        rollback.actions.push(action_id);
        rollback.verification_event_id = Some(result_event_id);

        let mut ledger = WorldLedger::new();
        ledger.append_action(action).expect("append action");
        ledger.register_rollback(rollback).expect("rollback");
        ledger.append_event(result_event).expect("result event");
        ledger.append_event(human_event).expect("human event");
        ledger.append_feedback(feedback).expect("feedback");
        ledger.to_snapshot()
    }
}
