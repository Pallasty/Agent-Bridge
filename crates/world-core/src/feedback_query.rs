use crate::ids::{ActionId, EntityId, EventId, FeedbackId, FeedbackQueryId, RollbackGroupId};
use crate::model::Feedback;
use crate::schema::SCHEMA_FEEDBACK_QUERY;
use serde::{Deserialize, Serialize};
use std::collections::BTreeMap;

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct FeedbackQuery {
    pub schema: String,
    pub query_id: FeedbackQueryId,
    #[serde(default)]
    pub filters: FeedbackQueryFilters,
}

impl FeedbackQuery {
    pub fn new(filters: FeedbackQueryFilters) -> Self {
        Self {
            schema: SCHEMA_FEEDBACK_QUERY.to_string(),
            query_id: FeedbackQueryId::new(),
            filters,
        }
    }

    pub fn with_id(query_id: FeedbackQueryId, filters: FeedbackQueryFilters) -> Self {
        Self {
            schema: SCHEMA_FEEDBACK_QUERY.to_string(),
            query_id,
            filters,
        }
    }
}

#[derive(Debug, Clone, Default, PartialEq, Eq, Serialize, Deserialize)]
pub struct FeedbackQueryFilters {
    pub feedback_id: Option<FeedbackId>,
    pub source_event_id: Option<EventId>,
    pub target_event_id: Option<EventId>,
    pub action_id: Option<ActionId>,
    pub entity_id: Option<EntityId>,
    pub rollback_group: Option<RollbackGroupId>,
    pub adapter: Option<String>,
    pub changes_world_verdict: Option<bool>,
}

impl FeedbackQueryFilters {
    pub fn by_source_event(source_event_id: EventId) -> Self {
        Self {
            source_event_id: Some(source_event_id),
            ..Self::default()
        }
    }

    pub fn by_action(action_id: ActionId) -> Self {
        Self {
            action_id: Some(action_id),
            ..Self::default()
        }
    }

    pub fn matches_feedback(&self, feedback: &Feedback) -> bool {
        if let Some(feedback_id) = &self.feedback_id {
            if &feedback.feedback_id != feedback_id {
                return false;
            }
        }
        if let Some(event_id) = &self.source_event_id {
            if &feedback.source_event_id != event_id {
                return false;
            }
        }
        if let Some(event_id) = &self.target_event_id {
            if !feedback.target.events.iter().any(|id| id == event_id) {
                return false;
            }
        }
        if let Some(action_id) = &self.action_id {
            if !feedback.target.actions.iter().any(|id| id == action_id) {
                return false;
            }
        }
        if let Some(entity_id) = &self.entity_id {
            if !feedback.target.entities.iter().any(|id| id == entity_id) {
                return false;
            }
        }
        if let Some(group_id) = &self.rollback_group {
            if !feedback
                .target
                .rollback_groups
                .iter()
                .any(|id| id == group_id)
            {
                return false;
            }
        }
        if let Some(adapter) = &self.adapter {
            if feedback.target.adapter.as_ref() != Some(adapter) {
                return false;
            }
        }
        if let Some(changes_world_verdict) = self.changes_world_verdict {
            if feedback.changes_world_verdict != changes_world_verdict {
                return false;
            }
        }
        true
    }
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct FeedbackQueryResponse {
    pub schema: String,
    pub query_id: FeedbackQueryId,
    pub filters: FeedbackQueryFilters,
    #[serde(default)]
    pub feedback: Vec<Feedback>,
    pub summary: FeedbackQuerySummary,
}

impl FeedbackQueryResponse {
    pub fn new(query: &FeedbackQuery, feedback: Vec<Feedback>) -> Self {
        let summary = FeedbackQuerySummary::from_matches(&feedback);
        Self {
            schema: SCHEMA_FEEDBACK_QUERY.to_string(),
            query_id: query.query_id.clone(),
            filters: query.filters.clone(),
            feedback,
            summary,
        }
    }
}

#[derive(Debug, Clone, Default, PartialEq, Eq, Serialize, Deserialize)]
pub struct FeedbackQuerySummary {
    pub feedback_count: usize,
    pub world_verdict_mutation_attempt_count: usize,
    pub target_event_count: usize,
    pub target_action_count: usize,
    pub target_entity_count: usize,
    pub target_rollback_group_count: usize,
    #[serde(default)]
    pub adapter_counts: BTreeMap<String, usize>,
}

impl FeedbackQuerySummary {
    fn from_matches(feedback: &[Feedback]) -> Self {
        let mut summary = Self {
            feedback_count: feedback.len(),
            world_verdict_mutation_attempt_count: 0,
            target_event_count: 0,
            target_action_count: 0,
            target_entity_count: 0,
            target_rollback_group_count: 0,
            adapter_counts: BTreeMap::new(),
        };
        for record in feedback {
            if record.changes_world_verdict {
                summary.world_verdict_mutation_attempt_count += 1;
            }
            summary.target_event_count += record.target.events.len();
            summary.target_action_count += record.target.actions.len();
            summary.target_entity_count += record.target.entities.len();
            summary.target_rollback_group_count += record.target.rollback_groups.len();
            if let Some(adapter) = &record.target.adapter {
                *summary.adapter_counts.entry(adapter.clone()).or_insert(0) += 1;
            }
        }
        summary
    }
}
