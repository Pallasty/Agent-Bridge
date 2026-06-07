use crate::model::{Action, Event, Feedback, RollbackRecord};
use crate::schema::SCHEMA_LEDGER_SNAPSHOT;
use crate::verification::Verification;
use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct WorldLedgerSnapshot {
    pub schema: String,
    #[serde(default)]
    pub actions: Vec<Action>,
    #[serde(default)]
    pub events: Vec<Event>,
    #[serde(default)]
    pub verifications: Vec<Verification>,
    #[serde(default)]
    pub feedback: Vec<Feedback>,
    #[serde(default)]
    pub rollback_records: Vec<RollbackRecord>,
}

impl WorldLedgerSnapshot {
    pub fn new(
        actions: Vec<Action>,
        events: Vec<Event>,
        verifications: Vec<Verification>,
        feedback: Vec<Feedback>,
        rollback_records: Vec<RollbackRecord>,
    ) -> Self {
        Self {
            schema: SCHEMA_LEDGER_SNAPSHOT.to_string(),
            actions,
            events,
            verifications,
            feedback,
            rollback_records,
        }
    }
}
