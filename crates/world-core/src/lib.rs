//! Live Semantic World Runtime core schema and in-memory ledger.
//!
//! This crate intentionally has no dependency on `ab-bridge`, MCP, browser,
//! renderer, or engine crates. It holds portable semantic world types only.

use serde::{Deserialize, Serialize};
use serde_json::Value;
use std::collections::HashMap;
use thiserror::Error;
use uuid::Uuid;

pub const SCHEMA_WORLD: &str = "agent_bridge.lswr.world.v0";
pub const SCHEMA_ACTION: &str = "agent_bridge.lswr.action.v0";
pub const SCHEMA_EVENT: &str = "agent_bridge.lswr.event.v0";
pub const SCHEMA_VERIFICATION: &str = "agent_bridge.lswr.verification.v0";
pub const SCHEMA_FEEDBACK: &str = "agent_bridge.lswr.feedback.v0";
pub const SCHEMA_ROLLBACK: &str = "agent_bridge.lswr.rollback.v0";

pub type Result<T> = std::result::Result<T, WorldCoreError>;

#[derive(Debug, Error, PartialEq, Eq)]
pub enum WorldCoreError {
    #[error("{verdict} verification requires a stable reason")]
    MissingReason { verdict: Verdict },

    #[error("verified verification requires verified_to")]
    MissingVerifiedTo,

    #[error("{verdict} verification must not set verified_to")]
    VerifiedToNotAllowed { verdict: Verdict },

    #[error("human decision cannot set changes_world_verdict=true")]
    HumanDecisionChangesVerification,

    #[error("rollback group already exists: {0}")]
    DuplicateRollbackGroup(String),

    #[error("rollback group not found: {0}")]
    RollbackGroupNotFound(String),
}

macro_rules! id_newtype {
    ($name:ident, $prefix:expr) => {
        #[derive(Debug, Clone, PartialEq, Eq, Hash, Serialize, Deserialize)]
        #[serde(transparent)]
        pub struct $name(pub String);

        impl $name {
            pub fn new() -> Self {
                Self(format!("{}-{}", $prefix, Uuid::new_v4()))
            }

            pub fn from_raw(raw: impl Into<String>) -> Self {
                Self(raw.into())
            }

            pub fn as_str(&self) -> &str {
                &self.0
            }
        }

        impl Default for $name {
            fn default() -> Self {
                Self::new()
            }
        }

        impl std::fmt::Display for $name {
            fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
                f.write_str(&self.0)
            }
        }
    };
}

id_newtype!(WorldId, "world");
id_newtype!(BranchId, "branch");
id_newtype!(EntityId, "entity");
id_newtype!(ParticipantId, "participant");
id_newtype!(ActionId, "action");
id_newtype!(EventId, "event");
id_newtype!(FeedbackId, "feedback");
id_newtype!(RollbackGroupId, "rollback");

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum Verdict {
    Verified,
    NotVerified,
    Blocked,
}

impl std::fmt::Display for Verdict {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            Self::Verified => f.write_str("verified"),
            Self::NotVerified => f.write_str("not_verified"),
            Self::Blocked => f.write_str("blocked"),
        }
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum ParticipantKind {
    Human,
    Ai,
    Runtime,
    Adapter,
    System,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum AuthorityMode {
    Observe,
    Suggest,
    Coedit,
    Autonomous,
    Locked,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct WorldRef {
    pub schema: String,
    pub world_id: WorldId,
    pub branch_id: BranchId,
    pub adapter: Option<String>,
}

impl WorldRef {
    pub fn new(world_id: WorldId, branch_id: BranchId) -> Self {
        Self {
            schema: SCHEMA_WORLD.to_string(),
            world_id,
            branch_id,
            adapter: None,
        }
    }
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct EntityRef {
    pub entity_id: EntityId,
    pub kind: String,
    #[serde(default)]
    pub state: Value,
    #[serde(default)]
    pub tags: Vec<String>,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct TargetRef {
    pub kind: String,
    pub id: String,
}

impl TargetRef {
    pub fn entity(entity_id: &EntityId) -> Self {
        Self {
            kind: "entity".to_string(),
            id: entity_id.to_string(),
        }
    }

    pub fn event(event_id: &EventId) -> Self {
        Self {
            kind: "event".to_string(),
            id: event_id.to_string(),
        }
    }

    pub fn rollback(group_id: &RollbackGroupId) -> Self {
        Self {
            kind: "rollback".to_string(),
            id: group_id.to_string(),
        }
    }
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct Participant {
    pub participant_id: ParticipantId,
    pub participant_kind: ParticipantKind,
    pub authority_mode: AuthorityMode,
    pub surface: Option<String>,
}

impl Participant {
    pub fn ai(participant_id: ParticipantId, authority_mode: AuthorityMode) -> Self {
        Self {
            participant_id,
            participant_kind: ParticipantKind::Ai,
            authority_mode,
            surface: None,
        }
    }

    pub fn human(participant_id: ParticipantId, surface: impl Into<String>) -> Self {
        Self {
            participant_id,
            participant_kind: ParticipantKind::Human,
            authority_mode: AuthorityMode::Coedit,
            surface: Some(surface.into()),
        }
    }

    pub fn runtime(participant_id: ParticipantId, surface: impl Into<String>) -> Self {
        Self {
            participant_id,
            participant_kind: ParticipantKind::Runtime,
            authority_mode: AuthorityMode::Coedit,
            surface: Some(surface.into()),
        }
    }
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct Action {
    pub schema: String,
    pub action_id: ActionId,
    pub action_type: String,
    pub source: Participant,
    #[serde(default)]
    pub target_refs: Vec<TargetRef>,
    #[serde(default)]
    pub expected_effect: Value,
    pub rollback_group: Option<RollbackGroupId>,
}

impl Action {
    pub fn new(action_type: impl Into<String>, source: Participant) -> Self {
        Self {
            schema: SCHEMA_ACTION.to_string(),
            action_id: ActionId::new(),
            action_type: action_type.into(),
            source,
            target_refs: Vec::new(),
            expected_effect: Value::Null,
            rollback_group: None,
        }
    }
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct AdapterEvidence {
    pub adapter_kind: String,
    pub method: String,
    pub summary: String,
    pub raw_available: bool,
    #[serde(default)]
    pub payload: Value,
}

impl AdapterEvidence {
    pub fn new(
        adapter_kind: impl Into<String>,
        method: impl Into<String>,
        summary: impl Into<String>,
        raw_available: bool,
        payload: Value,
    ) -> Self {
        Self {
            adapter_kind: adapter_kind.into(),
            method: method.into(),
            summary: summary.into(),
            raw_available,
            payload,
        }
    }
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct Verification {
    pub schema: String,
    pub action_id: Option<ActionId>,
    pub verdict: Verdict,
    pub reason: Option<String>,
    pub method: String,
    pub verified_to: Option<TargetRef>,
    pub evidence: AdapterEvidence,
}

impl Verification {
    pub fn new(
        action_id: Option<ActionId>,
        verdict: Verdict,
        reason: Option<String>,
        method: impl Into<String>,
        verified_to: Option<TargetRef>,
        evidence: AdapterEvidence,
    ) -> Result<Self> {
        validate_verification(verdict, reason.as_deref(), verified_to.as_ref())?;
        Ok(Self {
            schema: SCHEMA_VERIFICATION.to_string(),
            action_id,
            verdict,
            reason,
            method: method.into(),
            verified_to,
            evidence,
        })
    }
}

pub fn validate_verification(
    verdict: Verdict,
    reason: Option<&str>,
    verified_to: Option<&TargetRef>,
) -> Result<()> {
    match verdict {
        Verdict::Verified => {
            if verified_to.is_none() {
                return Err(WorldCoreError::MissingVerifiedTo);
            }
        }
        Verdict::NotVerified | Verdict::Blocked => {
            if reason.map(str::trim).unwrap_or_default().is_empty() {
                return Err(WorldCoreError::MissingReason { verdict });
            }
            if verified_to.is_some() {
                return Err(WorldCoreError::VerifiedToNotAllowed { verdict });
            }
        }
    }
    Ok(())
}

#[derive(Debug, Clone, Default, PartialEq, Serialize, Deserialize)]
pub struct EventRefs {
    #[serde(default)]
    pub entities: Vec<EntityId>,
    #[serde(default)]
    pub actions: Vec<ActionId>,
    #[serde(default)]
    pub events: Vec<EventId>,
    #[serde(default)]
    pub feedback: Vec<FeedbackId>,
    #[serde(default)]
    pub rollback_groups: Vec<RollbackGroupId>,
    #[serde(default)]
    pub adapter: Option<String>,
}

impl EventRefs {
    pub fn empty() -> Self {
        Self {
            entities: Vec::new(),
            actions: Vec::new(),
            events: Vec::new(),
            feedback: Vec::new(),
            rollback_groups: Vec::new(),
            adapter: None,
        }
    }
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct EventProvenance {
    pub adapter: Option<String>,
    pub source_schema: Option<String>,
    pub raw_available: bool,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct Event {
    pub schema: String,
    pub event_id: EventId,
    pub event_type: String,
    pub world_id: WorldId,
    pub branch_id: Option<BranchId>,
    pub tick: Option<u64>,
    pub source: Participant,
    pub refs: EventRefs,
    #[serde(default)]
    pub payload: Value,
    pub verification: Option<Verification>,
    pub provenance: EventProvenance,
}

impl Event {
    pub fn new(
        event_type: impl Into<String>,
        world_id: WorldId,
        source: Participant,
        provenance: EventProvenance,
    ) -> Self {
        Self {
            schema: SCHEMA_EVENT.to_string(),
            event_id: EventId::new(),
            event_type: event_type.into(),
            world_id,
            branch_id: None,
            tick: None,
            source,
            refs: EventRefs::empty(),
            payload: Value::Null,
            verification: None,
            provenance,
        }
    }

    pub fn is_human_decision(&self) -> bool {
        self.event_type == "human.accept" || self.event_type == "human.reject"
    }
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct Feedback {
    pub schema: String,
    pub feedback_id: FeedbackId,
    pub source_event_id: EventId,
    #[serde(default)]
    pub target: EventRefs,
    #[serde(default)]
    pub raw: Value,
    #[serde(default)]
    pub normalized: Value,
    pub changes_world_verdict: bool,
}

impl Feedback {
    pub fn new(source_event_id: EventId) -> Self {
        Self {
            schema: SCHEMA_FEEDBACK.to_string(),
            feedback_id: FeedbackId::new(),
            source_event_id,
            target: EventRefs::empty(),
            raw: Value::Null,
            normalized: Value::Null,
            changes_world_verdict: false,
        }
    }
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct RollbackRecord {
    pub schema: String,
    pub rollback_group: RollbackGroupId,
    pub before: Value,
    pub after: Value,
    #[serde(default)]
    pub actions: Vec<ActionId>,
    pub verification_event_id: Option<EventId>,
}

impl RollbackRecord {
    pub fn new(rollback_group: RollbackGroupId, before: Value, after: Value) -> Self {
        Self {
            schema: SCHEMA_ROLLBACK.to_string(),
            rollback_group,
            before,
            after,
            actions: Vec::new(),
            verification_event_id: None,
        }
    }
}

#[derive(Debug, Default, Clone, Serialize, Deserialize)]
pub struct WorldLedger {
    events: Vec<Event>,
    verifications: Vec<Verification>,
    feedback: Vec<Feedback>,
    rollback_groups: HashMap<RollbackGroupId, RollbackRecord>,
}

impl WorldLedger {
    pub fn new() -> Self {
        Self::default()
    }

    pub fn append_event(&mut self, event: Event) -> Result<()> {
        if event.is_human_decision() && payload_changes_world_verdict(&event.payload) {
            return Err(WorldCoreError::HumanDecisionChangesVerification);
        }
        if let Some(verification) = event.verification.clone() {
            self.append_verification(verification)?;
        }
        self.events.push(event);
        Ok(())
    }

    pub fn append_verification(&mut self, verification: Verification) -> Result<()> {
        validate_verification(
            verification.verdict,
            verification.reason.as_deref(),
            verification.verified_to.as_ref(),
        )?;
        self.verifications.push(verification);
        Ok(())
    }

    pub fn append_feedback(&mut self, feedback: Feedback) -> Result<()> {
        if feedback.changes_world_verdict {
            return Err(WorldCoreError::HumanDecisionChangesVerification);
        }
        self.feedback.push(feedback);
        Ok(())
    }

    pub fn register_rollback(&mut self, record: RollbackRecord) -> Result<()> {
        if self.rollback_groups.contains_key(&record.rollback_group) {
            return Err(WorldCoreError::DuplicateRollbackGroup(
                record.rollback_group.to_string(),
            ));
        }
        self.rollback_groups
            .insert(record.rollback_group.clone(), record);
        Ok(())
    }

    pub fn events(&self) -> &[Event] {
        &self.events
    }

    pub fn verifications(&self) -> &[Verification] {
        &self.verifications
    }

    pub fn feedback(&self) -> &[Feedback] {
        &self.feedback
    }

    pub fn rollback_groups(&self) -> impl Iterator<Item = &RollbackRecord> {
        self.rollback_groups.values()
    }

    pub fn rollback_group(&self, group_id: &RollbackGroupId) -> Result<&RollbackRecord> {
        self.rollback_groups
            .get(group_id)
            .ok_or_else(|| WorldCoreError::RollbackGroupNotFound(group_id.to_string()))
    }

    pub fn query_events_by_type(&self, event_type: &str) -> Vec<&Event> {
        self.events
            .iter()
            .filter(|event| event.event_type == event_type)
            .collect()
    }

    pub fn query_evidence_by_action(&self, action_id: &ActionId) -> Vec<&Verification> {
        self.verifications
            .iter()
            .filter(|verification| verification.action_id.as_ref() == Some(action_id))
            .collect()
    }
}

fn payload_changes_world_verdict(payload: &Value) -> bool {
    payload
        .get("changes_world_verdict")
        .and_then(Value::as_bool)
        .unwrap_or(false)
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    fn world_id() -> WorldId {
        WorldId::from_raw("lswr_web_proto_01")
    }

    fn ai() -> Participant {
        Participant::ai(ParticipantId::from_raw("ai:codex"), AuthorityMode::Coedit)
    }

    fn human() -> Participant {
        Participant::human(ParticipantId::from_raw("human:owner"), "web_scene")
    }

    fn provenance() -> EventProvenance {
        EventProvenance {
            adapter: Some("threejs_web".to_string()),
            source_schema: Some(SCHEMA_EVENT.to_string()),
            raw_available: true,
        }
    }

    fn evidence(method: &str, payload: Value) -> AdapterEvidence {
        AdapterEvidence::new("threejs_web", method, "fixture evidence", true, payload)
    }

    #[test]
    fn serde_round_trip_for_core_records() {
        let action = Action {
            schema: SCHEMA_ACTION.to_string(),
            action_id: ActionId::from_raw("act_add_cube_02"),
            action_type: "add_entity".to_string(),
            source: ai(),
            target_refs: vec![TargetRef::entity(&EntityId::from_raw("cube_02"))],
            expected_effect: json!({"entity_present": "cube_02", "human_visible": true}),
            rollback_group: Some(RollbackGroupId::from_raw("rb_001")),
        };
        let verification = Verification::new(
            Some(action.action_id.clone()),
            Verdict::Verified,
            None,
            "web_scene_projection_check",
            Some(TargetRef::entity(&EntityId::from_raw("cube_02"))),
            evidence(
                "web_scene_projection_check",
                json!({"projected": true, "bounds_nonzero": true}),
            ),
        )
        .unwrap();
        let mut event = Event::new("runtime.action_result", world_id(), ai(), provenance());
        event.refs.actions.push(action.action_id.clone());
        event.verification = Some(verification.clone());
        let rollback = RollbackRecord::new(
            RollbackGroupId::from_raw("rb_001"),
            json!({"entities": []}),
            json!({"entities": [{"entity_id": "cube_02"}]}),
        );

        let encoded = serde_json::to_string(&(action, event, verification, rollback)).unwrap();
        let decoded: (Action, Event, Verification, RollbackRecord) =
            serde_json::from_str(&encoded).unwrap();

        assert_eq!(decoded.0.action_type, "add_entity");
        assert_eq!(decoded.1.event_type, "runtime.action_result");
        assert_eq!(decoded.2.verdict, Verdict::Verified);
        assert_eq!(decoded.3.rollback_group.as_str(), "rb_001");
    }

    #[test]
    fn not_verified_and_blocked_require_reasons() {
        let not_verified = Verification::new(
            None,
            Verdict::NotVerified,
            None,
            "web_scene_projection_check",
            None,
            evidence("web_scene_projection_check", json!({})),
        );
        assert_eq!(
            not_verified.unwrap_err(),
            WorldCoreError::MissingReason {
                verdict: Verdict::NotVerified
            }
        );

        let blocked = Verification::new(
            None,
            Verdict::Blocked,
            Some("".to_string()),
            "world_policy_check",
            None,
            evidence("world_policy_check", json!({})),
        );
        assert_eq!(
            blocked.unwrap_err(),
            WorldCoreError::MissingReason {
                verdict: Verdict::Blocked
            }
        );
    }

    #[test]
    fn verified_to_is_only_allowed_for_verified() {
        let target = TargetRef::entity(&EntityId::from_raw("cube_01"));
        let missing_target = Verification::new(
            None,
            Verdict::Verified,
            None,
            "web_scene_projection_check",
            None,
            evidence("web_scene_projection_check", json!({})),
        );
        assert_eq!(
            missing_target.unwrap_err(),
            WorldCoreError::MissingVerifiedTo
        );

        let not_verified_with_target = Verification::new(
            None,
            Verdict::NotVerified,
            Some("projection_object_absent".to_string()),
            "web_scene_projection_check",
            Some(target),
            evidence("web_scene_projection_check", json!({})),
        );
        assert_eq!(
            not_verified_with_target.unwrap_err(),
            WorldCoreError::VerifiedToNotAllowed {
                verdict: Verdict::NotVerified
            }
        );
    }

    #[test]
    fn human_decision_does_not_mutate_prior_verification() {
        let action_id = ActionId::from_raw("act_material_cube_01");
        let verification = Verification::new(
            Some(action_id.clone()),
            Verdict::NotVerified,
            Some("projection_object_absent".to_string()),
            "web_scene_projection_check",
            None,
            evidence(
                "web_scene_projection_check",
                json!({"projected": false, "unprojected_entities": ["cube_01"]}),
            ),
        )
        .unwrap();

        let mut ledger = WorldLedger::new();
        ledger.append_verification(verification.clone()).unwrap();

        let mut reject = Event::new("human.reject", world_id(), human(), provenance());
        reject.refs.actions.push(action_id.clone());
        reject.payload = json!({
            "decision": "reject",
            "does_not_change_verification": true
        });
        ledger.append_event(reject).unwrap();

        let evidence = ledger.query_evidence_by_action(&action_id);
        assert_eq!(evidence.len(), 1);
        assert_eq!(evidence[0].verdict, Verdict::NotVerified);
        assert_eq!(
            evidence[0].reason.as_deref(),
            Some("projection_object_absent")
        );

        let mut invalid_accept = Event::new("human.accept", world_id(), human(), provenance());
        invalid_accept.payload = json!({
            "decision": "accept",
            "changes_world_verdict": true
        });
        assert_eq!(
            ledger.append_event(invalid_accept).unwrap_err(),
            WorldCoreError::HumanDecisionChangesVerification
        );
    }

    #[test]
    fn adapter_evidence_can_hold_web_and_nexus_payloads_without_core_fields() {
        let web = evidence(
            "web_scene_projection_check",
            json!({
                "projected": false,
                "reason": "projection_object_absent",
                "unprojected_entities": ["cube_02"]
            }),
        );
        let nexus = AdapterEvidence::new(
            "nexus",
            "nexus_event_causal_verification",
            "expected causal edge present",
            true,
            json!({
                "event_id": "evt_food_warning",
                "hash_chain_valid": true,
                "expected_causal_edge": {
                    "cause_id": "evt_tax_change",
                    "consequence_id": "evt_food_warning",
                    "edge_type": "direct",
                    "present": true
                }
            }),
        );

        assert_eq!(web.payload["unprojected_entities"][0], "cube_02");
        assert_eq!(nexus.payload["expected_causal_edge"]["edge_type"], "direct");
        assert_eq!(web.adapter_kind, "threejs_web");
        assert_eq!(nexus.adapter_kind, "nexus");
    }

    #[test]
    fn rollback_group_registration_and_query_are_ledger_visible() {
        let action_id = ActionId::from_raw("act_move_cube_01");
        let group_id = RollbackGroupId::from_raw("rb_002");
        let mut record = RollbackRecord::new(
            group_id.clone(),
            json!({"entities": [{"entity_id": "cube_01", "position": [0, 1, 0]}]}),
            json!({"entities": [{"entity_id": "cube_01", "position": [-2, 1, 0]}]}),
        );
        record.actions.push(action_id);

        let mut ledger = WorldLedger::new();
        ledger.register_rollback(record).unwrap();
        let fetched = ledger.rollback_group(&group_id).unwrap();
        assert_eq!(fetched.rollback_group, group_id);
        assert_eq!(fetched.actions.len(), 1);

        let duplicate = RollbackRecord::new(group_id.clone(), json!({}), json!({}));
        assert_eq!(
            ledger.register_rollback(duplicate).unwrap_err(),
            WorldCoreError::DuplicateRollbackGroup(group_id.to_string())
        );
    }
}
