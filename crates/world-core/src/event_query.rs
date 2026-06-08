use crate::ids::{
    ActionId, BranchId, EntityId, EventId, EventQueryId, ParticipantId, RollbackGroupId, WorldId,
};
use crate::model::{Event, ParticipantKind};
use crate::schema::SCHEMA_EVENT_QUERY;
use crate::verification::Verdict;
use serde::{Deserialize, Serialize};
use std::collections::BTreeMap;

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct EventQuery {
    pub schema: String,
    pub query_id: EventQueryId,
    #[serde(default)]
    pub filters: EventQueryFilters,
}

impl EventQuery {
    pub fn new(filters: EventQueryFilters) -> Self {
        Self {
            schema: SCHEMA_EVENT_QUERY.to_string(),
            query_id: EventQueryId::new(),
            filters,
        }
    }

    pub fn with_id(query_id: EventQueryId, filters: EventQueryFilters) -> Self {
        Self {
            schema: SCHEMA_EVENT_QUERY.to_string(),
            query_id,
            filters,
        }
    }
}

#[derive(Debug, Clone, Default, PartialEq, Eq, Serialize, Deserialize)]
pub struct EventQueryFilters {
    pub event_id: Option<EventId>,
    pub related_event_id: Option<EventId>,
    pub event_type: Option<String>,
    pub world_id: Option<WorldId>,
    pub branch_id: Option<BranchId>,
    pub entity_id: Option<EntityId>,
    pub action_id: Option<ActionId>,
    pub participant_id: Option<ParticipantId>,
    pub rollback_group: Option<RollbackGroupId>,
    pub adapter: Option<String>,
    pub verdict: Option<Verdict>,
}

impl EventQueryFilters {
    pub fn by_event(event_id: EventId) -> Self {
        Self {
            event_id: Some(event_id),
            ..Self::default()
        }
    }

    pub fn by_related_event(related_event_id: EventId) -> Self {
        Self {
            related_event_id: Some(related_event_id),
            ..Self::default()
        }
    }

    pub fn by_type(event_type: impl Into<String>) -> Self {
        Self {
            event_type: Some(event_type.into()),
            ..Self::default()
        }
    }

    pub fn matches_event(&self, event: &Event) -> bool {
        if let Some(event_id) = &self.event_id {
            if &event.event_id != event_id {
                return false;
            }
        }
        if let Some(event_id) = &self.related_event_id {
            let matches_id = &event.event_id == event_id;
            let references_id = event.refs.events.iter().any(|id| id == event_id);
            if !matches_id && !references_id {
                return false;
            }
        }
        if let Some(event_type) = &self.event_type {
            if event.event_type.as_str() != event_type.as_str() {
                return false;
            }
        }
        if let Some(world_id) = &self.world_id {
            if &event.world_id != world_id {
                return false;
            }
        }
        if let Some(branch_id) = &self.branch_id {
            if event.branch_id.as_ref() != Some(branch_id) {
                return false;
            }
        }
        if let Some(entity_id) = &self.entity_id {
            if !event.refs.entities.iter().any(|id| id == entity_id) {
                return false;
            }
        }
        if let Some(action_id) = &self.action_id {
            let references_action = event.refs.actions.iter().any(|id| id == action_id);
            let verification_action = event
                .verification
                .as_ref()
                .and_then(|verification| verification.action_id.as_ref())
                == Some(action_id);
            if !references_action && !verification_action {
                return false;
            }
        }
        if let Some(participant_id) = &self.participant_id {
            if &event.source.participant_id != participant_id {
                return false;
            }
        }
        if let Some(group_id) = &self.rollback_group {
            if !event.refs.rollback_groups.iter().any(|id| id == group_id) {
                return false;
            }
        }
        if let Some(adapter) = &self.adapter {
            let provenance_match = event.provenance.adapter.as_ref() == Some(adapter);
            let refs_match = event.refs.adapter.as_ref() == Some(adapter);
            let verification_match = event
                .verification
                .as_ref()
                .map(|verification| verification.evidence.adapter_kind.as_str())
                == Some(adapter.as_str());
            if !provenance_match && !refs_match && !verification_match {
                return false;
            }
        }
        if let Some(verdict) = self.verdict {
            if event
                .verification
                .as_ref()
                .map(|verification| verification.verdict)
                != Some(verdict)
            {
                return false;
            }
        }
        true
    }
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct EventQueryResponse {
    pub schema: String,
    pub query_id: EventQueryId,
    pub filters: EventQueryFilters,
    #[serde(default)]
    pub events: Vec<Event>,
    pub summary: EventQuerySummary,
}

impl EventQueryResponse {
    pub fn new(query: &EventQuery, events: Vec<Event>) -> Self {
        let summary = EventQuerySummary::from_matches(&events);
        Self {
            schema: SCHEMA_EVENT_QUERY.to_string(),
            query_id: query.query_id.clone(),
            filters: query.filters.clone(),
            events,
            summary,
        }
    }
}

#[derive(Debug, Clone, Default, PartialEq, Eq, Serialize, Deserialize)]
pub struct EventQuerySummary {
    pub event_count: usize,
    #[serde(default)]
    pub event_type_counts: BTreeMap<String, usize>,
    #[serde(default)]
    pub participant_kind_counts: BTreeMap<String, usize>,
    #[serde(default)]
    pub adapter_counts: BTreeMap<String, usize>,
    #[serde(default)]
    pub embedded_verdict_counts: BTreeMap<String, usize>,
}

impl EventQuerySummary {
    fn from_matches(events: &[Event]) -> Self {
        let mut summary = Self {
            event_count: events.len(),
            event_type_counts: BTreeMap::new(),
            participant_kind_counts: BTreeMap::new(),
            adapter_counts: BTreeMap::new(),
            embedded_verdict_counts: BTreeMap::new(),
        };
        for event in events {
            *summary
                .event_type_counts
                .entry(event.event_type.clone())
                .or_insert(0) += 1;
            *summary
                .participant_kind_counts
                .entry(participant_kind_key(event.source.participant_kind).to_string())
                .or_insert(0) += 1;
            if let Some(adapter) = event_adapter(event) {
                *summary
                    .adapter_counts
                    .entry(adapter.to_string())
                    .or_insert(0) += 1;
            }
            if let Some(verification) = &event.verification {
                *summary
                    .embedded_verdict_counts
                    .entry(verification.verdict.to_string())
                    .or_insert(0) += 1;
            }
        }
        summary
    }
}

fn participant_kind_key(kind: ParticipantKind) -> &'static str {
    match kind {
        ParticipantKind::Human => "human",
        ParticipantKind::Ai => "ai",
        ParticipantKind::Runtime => "runtime",
        ParticipantKind::Adapter => "adapter",
        ParticipantKind::System => "system",
    }
}

fn event_adapter(event: &Event) -> Option<&str> {
    event
        .provenance
        .adapter
        .as_deref()
        .or(event.refs.adapter.as_deref())
        .or_else(|| {
            event
                .verification
                .as_ref()
                .map(|verification| verification.evidence.adapter_kind.as_str())
        })
}
