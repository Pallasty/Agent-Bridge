use crate::ids::{
    ActionId, BranchId, EntityId, EventId, FeedbackId, ParticipantId, RollbackGroupId, WorldId,
};
use crate::schema::{SCHEMA_ACTION, SCHEMA_EVENT, SCHEMA_FEEDBACK, SCHEMA_ROLLBACK, SCHEMA_WORLD};
use crate::verification::Verification;
use serde::{Deserialize, Serialize};
use serde_json::Value;

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
