//! Portable factual primitives for the Embodiment Loop.
//!
//! This module deliberately models observations, intent, receipts, and write
//! ownership without executing an action or deciding policy. Runtime adapters
//! remain responsible for authorization and for persisting a later snapshot.

use std::collections::HashMap;

use serde::{Deserialize, Serialize};
use serde_json::Value;

use crate::{BodyId, IntentId, LeaseId, ReceiptId};

pub const EMBODIMENT_SNAPSHOT_SCHEMA_V0: &str = "agent_bridge.embodiment_snapshot.v0";
pub const OBSERVATION_SCHEMA_V0: &str = "agent_bridge.observation.v0";
pub const ACTION_RECEIPT_SCHEMA_V0: &str = "agent_bridge.action_receipt.v0";

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct BodyDescriptor {
    pub body_id: BodyId,
    pub kind: String,
    pub label: String,
    #[serde(default)]
    pub capabilities: Vec<String>,
    pub authority_scope: String,
    pub online: bool,
    pub last_observed_unix_ms: Option<u64>,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct ObservationEnvelope {
    pub schema: String,
    pub body_id: BodyId,
    pub source: String,
    pub observed_at_unix_ms: u64,
    pub freshness_ms: u64,
    pub confidence: f32,
    pub world_revision: u64,
    #[serde(default)]
    pub payload: Value,
}

impl ObservationEnvelope {
    pub fn is_fresh_at(&self, now_unix_ms: u64, max_age_ms: u64) -> bool {
        now_unix_ms
            .saturating_sub(self.observed_at_unix_ms)
            .saturating_add(self.freshness_ms)
            <= max_age_ms
    }
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct Intent {
    pub intent_id: IntentId,
    pub body_id: BodyId,
    pub actor: String,
    pub action_kind: String,
    pub created_at_unix_ms: u64,
    pub resumable: bool,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct ActionReceipt {
    pub schema: String,
    pub receipt_id: ReceiptId,
    pub intent_id: IntentId,
    pub body_id: BodyId,
    pub lease_id: Option<LeaseId>,
    pub precondition: ObservationEnvelope,
    pub execution: Value,
    pub outcome: Value,
    pub verified: bool,
    pub reversible: bool,
    pub rollback: Option<Value>,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct WriteLease {
    pub lease_id: LeaseId,
    pub body_id: BodyId,
    pub holder: String,
    pub acquired_at_unix_ms: u64,
}

#[derive(Debug, Default)]
pub struct WriteLeaseRegistry {
    leases: HashMap<BodyId, WriteLease>,
}

impl WriteLeaseRegistry {
    pub fn acquire(
        &mut self,
        body_id: BodyId,
        holder: impl Into<String>,
        now_unix_ms: u64,
    ) -> Result<WriteLease, WriteLease> {
        if let Some(existing) = self.leases.get(&body_id) {
            return Err(existing.clone());
        }
        let lease = WriteLease {
            lease_id: LeaseId::new(),
            body_id: body_id.clone(),
            holder: holder.into(),
            acquired_at_unix_ms: now_unix_ms,
        };
        self.leases.insert(body_id, lease.clone());
        Ok(lease)
    }

    pub fn release(&mut self, lease_id: &LeaseId) -> bool {
        let Some((body_id, _)) = self
            .leases
            .iter()
            .find(|(_, lease)| &lease.lease_id == lease_id)
            .map(|(id, lease)| (id.clone(), lease.clone()))
        else {
            return false;
        };
        self.leases.remove(&body_id).is_some()
    }

    pub fn current(&self, body_id: &BodyId) -> Option<&WriteLease> {
        self.leases.get(body_id)
    }
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct EmbodimentSnapshot {
    pub schema: String,
    pub bodies: Vec<BodyDescriptor>,
    pub observations: Vec<ObservationEnvelope>,
    pub open_intents: Vec<Intent>,
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    #[test]
    fn stale_observation_fails_closed() {
        let observation = ObservationEnvelope {
            schema: OBSERVATION_SCHEMA_V0.into(),
            body_id: BodyId::from_raw("body-mac"),
            source: "body_status".into(),
            observed_at_unix_ms: 100,
            freshness_ms: 5,
            confidence: 1.0,
            world_revision: 1,
            payload: json!({}),
        };
        assert!(observation.is_fresh_at(104, 10));
        assert!(!observation.is_fresh_at(111, 10));
    }

    #[test]
    fn only_one_holder_can_acquire_a_body() {
        let body = BodyId::from_raw("body-mac");
        let mut registry = WriteLeaseRegistry::default();
        let first = registry.acquire(body.clone(), "agent-a", 10).unwrap();
        let held = registry.acquire(body.clone(), "agent-b", 11).unwrap_err();
        assert_eq!(held.holder, "agent-a");
        assert!(registry.release(&first.lease_id));
        assert_eq!(
            registry.acquire(body, "agent-b", 12).unwrap().holder,
            "agent-b"
        );
    }
}
