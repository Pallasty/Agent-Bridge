use crate::ids::{ActionId, EntityId, EventId, EvidenceQueryId, ParticipantId, RollbackGroupId};
use crate::model::{Event, TargetRef};
use crate::schema::SCHEMA_EVIDENCE_QUERY;
use crate::verification::{Verdict, Verification};
use serde::{Deserialize, Serialize};
use std::collections::BTreeMap;

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct EvidenceQuery {
    pub schema: String,
    pub query_id: EvidenceQueryId,
    #[serde(default)]
    pub filters: EvidenceQueryFilters,
}

impl EvidenceQuery {
    pub fn new(filters: EvidenceQueryFilters) -> Self {
        Self {
            schema: SCHEMA_EVIDENCE_QUERY.to_string(),
            query_id: EvidenceQueryId::new(),
            filters,
        }
    }

    pub fn with_id(query_id: EvidenceQueryId, filters: EvidenceQueryFilters) -> Self {
        Self {
            schema: SCHEMA_EVIDENCE_QUERY.to_string(),
            query_id,
            filters,
        }
    }
}

#[derive(Debug, Clone, Default, PartialEq, Eq, Serialize, Deserialize)]
pub struct EvidenceQueryFilters {
    pub event_id: Option<EventId>,
    pub action_id: Option<ActionId>,
    pub entity_id: Option<EntityId>,
    pub participant_id: Option<ParticipantId>,
    pub rollback_group: Option<RollbackGroupId>,
    pub verdict: Option<Verdict>,
    pub method: Option<String>,
    pub adapter_kind: Option<String>,
}

impl EvidenceQueryFilters {
    pub fn by_action(action_id: ActionId) -> Self {
        Self {
            action_id: Some(action_id),
            ..Self::default()
        }
    }

    pub fn by_event(event_id: EventId) -> Self {
        Self {
            event_id: Some(event_id),
            ..Self::default()
        }
    }

    pub fn by_verdict(verdict: Verdict) -> Self {
        Self {
            verdict: Some(verdict),
            ..Self::default()
        }
    }

    pub fn matches_event(&self, event: &Event) -> bool {
        if let Some(event_id) = &self.event_id {
            let matches_id = &event.event_id == event_id;
            let references_id = event.refs.events.iter().any(|id| id == event_id);
            if !matches_id && !references_id {
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
        if let Some(entity_id) = &self.entity_id {
            if !event.refs.entities.iter().any(|id| id == entity_id) {
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
        if let Some(method) = &self.method {
            if event
                .verification
                .as_ref()
                .map(|verification| verification.method.as_str())
                != Some(method.as_str())
            {
                return false;
            }
        }
        if let Some(adapter_kind) = &self.adapter_kind {
            let provenance_match = event.provenance.adapter.as_ref() == Some(adapter_kind);
            let verification_match = event
                .verification
                .as_ref()
                .map(|verification| verification.evidence.adapter_kind.as_str())
                == Some(adapter_kind.as_str());
            if !provenance_match && !verification_match {
                return false;
            }
        }
        true
    }

    pub fn matches_verification(&self, verification: &Verification) -> bool {
        if let Some(event_id) = &self.event_id {
            if verification.verified_to.as_ref() != Some(&TargetRef::event(event_id)) {
                return false;
            }
        }
        if let Some(action_id) = &self.action_id {
            if verification.action_id.as_ref() != Some(action_id) {
                return false;
            }
        }
        if let Some(entity_id) = &self.entity_id {
            if verification.verified_to.as_ref() != Some(&TargetRef::entity(entity_id)) {
                return false;
            }
        }
        if self.participant_id.is_some() {
            return false;
        }
        if let Some(group_id) = &self.rollback_group {
            if verification.verified_to.as_ref() != Some(&TargetRef::rollback(group_id)) {
                return false;
            }
        }
        if let Some(verdict) = self.verdict {
            if verification.verdict != verdict {
                return false;
            }
        }
        if let Some(method) = &self.method {
            if verification.method.as_str() != method.as_str() {
                return false;
            }
        }
        if let Some(adapter_kind) = &self.adapter_kind {
            if verification.evidence.adapter_kind.as_str() != adapter_kind.as_str() {
                return false;
            }
        }
        true
    }
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct EvidenceQueryResponse {
    pub schema: String,
    pub query_id: EvidenceQueryId,
    pub filters: EvidenceQueryFilters,
    #[serde(default)]
    pub events: Vec<Event>,
    #[serde(default)]
    pub verifications: Vec<Verification>,
    pub summary: EvidenceQuerySummary,
}

impl EvidenceQueryResponse {
    pub fn new(
        query: &EvidenceQuery,
        events: Vec<Event>,
        verifications: Vec<Verification>,
    ) -> Self {
        let summary = EvidenceQuerySummary::from_matches(&events, &verifications);
        Self {
            schema: SCHEMA_EVIDENCE_QUERY.to_string(),
            query_id: query.query_id.clone(),
            filters: query.filters.clone(),
            events,
            verifications,
            summary,
        }
    }
}

#[derive(Debug, Clone, Default, PartialEq, Eq, Serialize, Deserialize)]
pub struct EvidenceQuerySummary {
    pub event_count: usize,
    pub verification_count: usize,
    #[serde(default)]
    pub verdict_counts: BTreeMap<String, usize>,
    #[serde(default)]
    pub adapter_counts: BTreeMap<String, usize>,
}

impl EvidenceQuerySummary {
    fn from_matches(events: &[Event], verifications: &[Verification]) -> Self {
        let mut summary = Self {
            event_count: events.len(),
            verification_count: verifications.len(),
            verdict_counts: BTreeMap::new(),
            adapter_counts: BTreeMap::new(),
        };
        for verification in verifications {
            *summary
                .verdict_counts
                .entry(verification.verdict.to_string())
                .or_insert(0) += 1;
            *summary
                .adapter_counts
                .entry(verification.evidence.adapter_kind.clone())
                .or_insert(0) += 1;
        }
        for event in events {
            if let Some(adapter) = &event.provenance.adapter {
                summary.adapter_counts.entry(adapter.clone()).or_insert(0);
            }
        }
        summary
    }
}
