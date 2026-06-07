use crate::ids::{ActionId, EventId, RollbackGroupId, RollbackQueryId};
use crate::model::RollbackRecord;
use crate::schema::SCHEMA_ROLLBACK_QUERY;
use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct RollbackQuery {
    pub schema: String,
    pub query_id: RollbackQueryId,
    #[serde(default)]
    pub filters: RollbackQueryFilters,
}

impl RollbackQuery {
    pub fn new(filters: RollbackQueryFilters) -> Self {
        Self {
            schema: SCHEMA_ROLLBACK_QUERY.to_string(),
            query_id: RollbackQueryId::new(),
            filters,
        }
    }

    pub fn with_id(query_id: RollbackQueryId, filters: RollbackQueryFilters) -> Self {
        Self {
            schema: SCHEMA_ROLLBACK_QUERY.to_string(),
            query_id,
            filters,
        }
    }
}

#[derive(Debug, Clone, Default, PartialEq, Eq, Serialize, Deserialize)]
pub struct RollbackQueryFilters {
    pub rollback_group: Option<RollbackGroupId>,
    pub action_id: Option<ActionId>,
    pub verification_event_id: Option<EventId>,
    pub has_verification_event: Option<bool>,
}

impl RollbackQueryFilters {
    pub fn by_group(rollback_group: RollbackGroupId) -> Self {
        Self {
            rollback_group: Some(rollback_group),
            ..Self::default()
        }
    }

    pub fn by_action(action_id: ActionId) -> Self {
        Self {
            action_id: Some(action_id),
            ..Self::default()
        }
    }

    pub fn matches_rollback(&self, record: &RollbackRecord) -> bool {
        if let Some(group_id) = &self.rollback_group {
            if &record.rollback_group != group_id {
                return false;
            }
        }
        if let Some(action_id) = &self.action_id {
            if !record.actions.iter().any(|id| id == action_id) {
                return false;
            }
        }
        if let Some(event_id) = &self.verification_event_id {
            if record.verification_event_id.as_ref() != Some(event_id) {
                return false;
            }
        }
        if let Some(has_verification_event) = self.has_verification_event {
            if record.verification_event_id.is_some() != has_verification_event {
                return false;
            }
        }
        true
    }
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct RollbackQueryResponse {
    pub schema: String,
    pub query_id: RollbackQueryId,
    pub filters: RollbackQueryFilters,
    #[serde(default)]
    pub rollback_records: Vec<RollbackRecord>,
    pub summary: RollbackQuerySummary,
}

impl RollbackQueryResponse {
    pub fn new(query: &RollbackQuery, rollback_records: Vec<RollbackRecord>) -> Self {
        let summary = RollbackQuerySummary::from_matches(&rollback_records);
        Self {
            schema: SCHEMA_ROLLBACK_QUERY.to_string(),
            query_id: query.query_id.clone(),
            filters: query.filters.clone(),
            rollback_records,
            summary,
        }
    }
}

#[derive(Debug, Clone, Default, PartialEq, Eq, Serialize, Deserialize)]
pub struct RollbackQuerySummary {
    pub rollback_count: usize,
    pub action_ref_count: usize,
    pub before_payload_count: usize,
    pub after_payload_count: usize,
    pub verification_event_count: usize,
}

impl RollbackQuerySummary {
    fn from_matches(rollback_records: &[RollbackRecord]) -> Self {
        let mut summary = Self {
            rollback_count: rollback_records.len(),
            action_ref_count: 0,
            before_payload_count: 0,
            after_payload_count: 0,
            verification_event_count: 0,
        };
        for record in rollback_records {
            summary.action_ref_count += record.actions.len();
            if !record.before.is_null() {
                summary.before_payload_count += 1;
            }
            if !record.after.is_null() {
                summary.after_payload_count += 1;
            }
            if record.verification_event_id.is_some() {
                summary.verification_event_count += 1;
            }
        }
        summary
    }
}
