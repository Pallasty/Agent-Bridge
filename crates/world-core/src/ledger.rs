use crate::evidence_query::{EvidenceQuery, EvidenceQueryResponse};
use crate::ids::{ActionId, EntityId, EventId, ParticipantId, RollbackGroupId};
use crate::model::{Event, Feedback, RollbackRecord};
use crate::verification::{validate_verification, Result, Verdict, Verification, WorldCoreError};
use serde::{Deserialize, Serialize};
use serde_json::Value;
use std::collections::HashMap;

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

    pub fn event_by_id(&self, event_id: &EventId) -> Option<&Event> {
        self.events.iter().find(|event| &event.event_id == event_id)
    }

    pub fn query_events_by_type(&self, event_type: &str) -> Vec<&Event> {
        self.events
            .iter()
            .filter(|event| event.event_type == event_type)
            .collect()
    }

    pub fn query_events_by_entity(&self, entity_id: &EntityId) -> Vec<&Event> {
        self.events
            .iter()
            .filter(|event| event.refs.entities.iter().any(|id| id == entity_id))
            .collect()
    }

    pub fn query_events_by_action(&self, action_id: &ActionId) -> Vec<&Event> {
        self.events
            .iter()
            .filter(|event| event.refs.actions.iter().any(|id| id == action_id))
            .collect()
    }

    pub fn query_events_by_rollback_group(&self, group_id: &RollbackGroupId) -> Vec<&Event> {
        self.events
            .iter()
            .filter(|event| event.refs.rollback_groups.iter().any(|id| id == group_id))
            .collect()
    }

    pub fn query_events_by_participant(&self, participant_id: &ParticipantId) -> Vec<&Event> {
        self.events
            .iter()
            .filter(|event| &event.source.participant_id == participant_id)
            .collect()
    }

    pub fn query_verifications_by_verdict(&self, verdict: Verdict) -> Vec<&Verification> {
        self.verifications
            .iter()
            .filter(|verification| verification.verdict == verdict)
            .collect()
    }

    pub fn query_evidence_by_action(&self, action_id: &ActionId) -> Vec<&Verification> {
        self.verifications
            .iter()
            .filter(|verification| verification.action_id.as_ref() == Some(action_id))
            .collect()
    }

    pub fn query_feedback_by_source_event(&self, event_id: &EventId) -> Vec<&Feedback> {
        self.feedback
            .iter()
            .filter(|feedback| &feedback.source_event_id == event_id)
            .collect()
    }

    pub fn query_feedback_by_action(&self, action_id: &ActionId) -> Vec<&Feedback> {
        self.feedback
            .iter()
            .filter(|feedback| feedback.target.actions.iter().any(|id| id == action_id))
            .collect()
    }

    pub fn query_rollbacks_by_action(&self, action_id: &ActionId) -> Vec<&RollbackRecord> {
        self.rollback_groups
            .values()
            .filter(|record| record.actions.iter().any(|id| id == action_id))
            .collect()
    }

    pub fn query_evidence(&self, query: &EvidenceQuery) -> EvidenceQueryResponse {
        let events = self
            .events
            .iter()
            .filter(|event| query.filters.matches_event(event))
            .cloned()
            .collect();
        let verifications = self
            .verifications
            .iter()
            .filter(|verification| query.filters.matches_verification(verification))
            .cloned()
            .collect();
        EvidenceQueryResponse::new(query, events, verifications)
    }
}

fn payload_changes_world_verdict(payload: &Value) -> bool {
    payload
        .get("changes_world_verdict")
        .and_then(Value::as_bool)
        .unwrap_or(false)
}
