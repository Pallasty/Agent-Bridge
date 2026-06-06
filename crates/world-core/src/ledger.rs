use crate::ids::{ActionId, RollbackGroupId};
use crate::model::{Event, Feedback, RollbackRecord};
use crate::verification::{validate_verification, Result, Verification, WorldCoreError};
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
