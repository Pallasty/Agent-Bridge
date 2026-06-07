use crate::ids::{ActionId, ActionQueryId, ParticipantId, RollbackGroupId};
use crate::model::{Action, AuthorityMode, ParticipantKind};
use crate::schema::SCHEMA_ACTION_QUERY;
use serde::{Deserialize, Serialize};
use std::collections::BTreeMap;

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct ActionQuery {
    pub schema: String,
    pub query_id: ActionQueryId,
    #[serde(default)]
    pub filters: ActionQueryFilters,
}

impl ActionQuery {
    pub fn new(filters: ActionQueryFilters) -> Self {
        Self {
            schema: SCHEMA_ACTION_QUERY.to_string(),
            query_id: ActionQueryId::new(),
            filters,
        }
    }

    pub fn with_id(query_id: ActionQueryId, filters: ActionQueryFilters) -> Self {
        Self {
            schema: SCHEMA_ACTION_QUERY.to_string(),
            query_id,
            filters,
        }
    }
}

#[derive(Debug, Clone, Default, PartialEq, Eq, Serialize, Deserialize)]
pub struct ActionQueryFilters {
    pub action_id: Option<ActionId>,
    pub action_type: Option<String>,
    pub source_participant_id: Option<ParticipantId>,
    pub participant_kind: Option<ParticipantKind>,
    pub authority_mode: Option<AuthorityMode>,
    pub target_ref_kind: Option<String>,
    pub target_ref_id: Option<String>,
    pub rollback_group: Option<RollbackGroupId>,
    pub has_expected_effect: Option<bool>,
}

impl ActionQueryFilters {
    pub fn by_action(action_id: ActionId) -> Self {
        Self {
            action_id: Some(action_id),
            ..Self::default()
        }
    }

    pub fn by_type(action_type: impl Into<String>) -> Self {
        Self {
            action_type: Some(action_type.into()),
            ..Self::default()
        }
    }

    pub fn matches_action(&self, action: &Action) -> bool {
        if let Some(action_id) = &self.action_id {
            if &action.action_id != action_id {
                return false;
            }
        }
        if let Some(action_type) = &self.action_type {
            if action.action_type.as_str() != action_type.as_str() {
                return false;
            }
        }
        if let Some(participant_id) = &self.source_participant_id {
            if &action.source.participant_id != participant_id {
                return false;
            }
        }
        if let Some(participant_kind) = self.participant_kind {
            if action.source.participant_kind != participant_kind {
                return false;
            }
        }
        if let Some(authority_mode) = self.authority_mode {
            if action.source.authority_mode != authority_mode {
                return false;
            }
        }
        if let Some(kind) = &self.target_ref_kind {
            if !action
                .target_refs
                .iter()
                .any(|target| target.kind.as_str() == kind.as_str())
            {
                return false;
            }
        }
        if let Some(id) = &self.target_ref_id {
            if !action
                .target_refs
                .iter()
                .any(|target| target.id.as_str() == id.as_str())
            {
                return false;
            }
        }
        if let Some(group_id) = &self.rollback_group {
            if action.rollback_group.as_ref() != Some(group_id) {
                return false;
            }
        }
        if let Some(has_expected_effect) = self.has_expected_effect {
            if action.expected_effect.is_null() == has_expected_effect {
                return false;
            }
        }
        true
    }
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct ActionQueryResponse {
    pub schema: String,
    pub query_id: ActionQueryId,
    pub filters: ActionQueryFilters,
    #[serde(default)]
    pub actions: Vec<Action>,
    pub summary: ActionQuerySummary,
}

impl ActionQueryResponse {
    pub fn new(query: &ActionQuery, actions: Vec<Action>) -> Self {
        let summary = ActionQuerySummary::from_matches(&actions);
        Self {
            schema: SCHEMA_ACTION_QUERY.to_string(),
            query_id: query.query_id.clone(),
            filters: query.filters.clone(),
            actions,
            summary,
        }
    }
}

#[derive(Debug, Clone, Default, PartialEq, Eq, Serialize, Deserialize)]
pub struct ActionQuerySummary {
    pub action_count: usize,
    pub target_ref_count: usize,
    pub rollback_linked_action_count: usize,
    pub expected_effect_payload_count: usize,
    #[serde(default)]
    pub action_type_counts: BTreeMap<String, usize>,
    #[serde(default)]
    pub participant_kind_counts: BTreeMap<String, usize>,
    #[serde(default)]
    pub authority_mode_counts: BTreeMap<String, usize>,
}

impl ActionQuerySummary {
    fn from_matches(actions: &[Action]) -> Self {
        let mut summary = Self {
            action_count: actions.len(),
            target_ref_count: 0,
            rollback_linked_action_count: 0,
            expected_effect_payload_count: 0,
            action_type_counts: BTreeMap::new(),
            participant_kind_counts: BTreeMap::new(),
            authority_mode_counts: BTreeMap::new(),
        };
        for action in actions {
            *summary
                .action_type_counts
                .entry(action.action_type.clone())
                .or_insert(0) += 1;
            *summary
                .participant_kind_counts
                .entry(participant_kind_key(action.source.participant_kind).to_string())
                .or_insert(0) += 1;
            *summary
                .authority_mode_counts
                .entry(authority_mode_key(action.source.authority_mode).to_string())
                .or_insert(0) += 1;
            summary.target_ref_count += action.target_refs.len();
            if action.rollback_group.is_some() {
                summary.rollback_linked_action_count += 1;
            }
            if !action.expected_effect.is_null() {
                summary.expected_effect_payload_count += 1;
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

fn authority_mode_key(mode: AuthorityMode) -> &'static str {
    match mode {
        AuthorityMode::Observe => "observe",
        AuthorityMode::Suggest => "suggest",
        AuthorityMode::Coedit => "coedit",
        AuthorityMode::Autonomous => "autonomous",
        AuthorityMode::Locked => "locked",
    }
}
