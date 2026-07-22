//! Digest-only Qwen-AgentWorld trajectory compatibility audit.
//!
//! P0 does not export prompts, tool arguments/results, session transcripts, or
//! state values. It derives a manifest from an [`AgentTaskContractPreview`] and
//! an [`EventSpineSnapshot`] so callers can measure whether current telemetry
//! is sufficient for honest action/observation reconstruction before any world
//! model receives data.

use crate::{
    agent_task_contract::AgentTaskContractPreview,
    event_spine::{EventSpineEvent, EventSpineSnapshot},
};
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};

pub const AGENT_WORLD_TRAJECTORY_SCHEMA_V0: &str = "agent_bridge.agent_world_trajectory.v0";
pub const AGENT_WORLD_TRAJECTORY_AUDIT_SCHEMA_V0: &str =
    "agent_bridge.agent_world_trajectory_audit.v0";

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct AgentWorldTrajectorySafety {
    pub read_only: bool,
    pub derived_only: bool,
    pub raw_content_exported: bool,
    pub can_write_memory: bool,
    pub can_promote_canon: bool,
    pub can_emit_attestation: bool,
    pub can_enable_runtime: bool,
    pub simulated_observations_evidence_admissible: bool,
}

impl AgentWorldTrajectorySafety {
    fn p0() -> Self {
        Self {
            read_only: true,
            derived_only: true,
            raw_content_exported: false,
            can_write_memory: false,
            can_promote_canon: false,
            can_emit_attestation: false,
            can_enable_runtime: false,
            simulated_observations_evidence_admissible: false,
        }
    }
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct AgentWorldDigestRef {
    pub ordinal: usize,
    pub sha256: String,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct AgentWorldStateDigestRef {
    pub key_sha256: String,
    pub value_sha256: String,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct AgentWorldTaskManifestV0 {
    pub contract_ref: String,
    pub contract_revision: u64,
    pub objective_sha256: String,
    pub action_space: Vec<AgentWorldDigestRef>,
    pub initial_state: Vec<AgentWorldStateDigestRef>,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum AgentWorldObservationOrigin {
    Observed,
    Simulated,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct AgentWorldTurnV0 {
    pub turn_index: usize,
    pub action_sha256: String,
    pub observation_sha256: String,
    pub observation_origin: AgentWorldObservationOrigin,
    #[serde(default)]
    pub evidence_refs: Vec<AgentWorldEvidenceRef>,
    pub attestation_ref: Option<String>,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct AgentWorldEvidenceRef {
    pub event_id_sha256: String,
    pub payload_sha256: String,
    pub event_hash: String,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct AgentWorldTrajectoryV0 {
    pub schema_version: String,
    pub trajectory_id: String,
    pub payload_mode: String,
    pub task: AgentWorldTaskManifestV0,
    pub turns: Vec<AgentWorldTurnV0>,
    pub provenance: AgentWorldProvenanceV0,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct AgentWorldProvenanceV0 {
    pub source: String,
    pub event_spine_chain_head: String,
    pub event_spine_local_chain_consistent: bool,
    pub candidate_count: usize,
    pub event_count: usize,
    pub truncated_count: usize,
    pub event_refs: Vec<AgentWorldEventRef>,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct AgentWorldEventRef {
    pub event_id: String,
    pub ts: i64,
    pub source: String,
    pub kind: String,
    pub ok: Option<bool>,
    pub payload_sha256: String,
    pub event_hash: String,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct AgentWorldTrajectoryCoverage {
    pub contract_ready: bool,
    pub initial_state_fields: usize,
    pub source_events: usize,
    pub action_candidates: usize,
    pub exact_observation_candidates: usize,
    pub preview_only_observation_candidates: usize,
    pub reconstructed_turns: usize,
    pub reconstructability_ratio: f64,
    pub source_snapshot_truncated: bool,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct AgentWorldTrajectoryBlocker {
    pub code: String,
    pub message: String,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct AgentWorldTrajectoryAuditV0 {
    pub schema_version: String,
    pub status: String,
    pub safety: AgentWorldTrajectorySafety,
    pub trajectory: AgentWorldTrajectoryV0,
    pub coverage: AgentWorldTrajectoryCoverage,
    pub blockers: Vec<AgentWorldTrajectoryBlocker>,
}

/// Build a deterministic, digest-only compatibility audit.
///
/// Current event-spine telemetry intentionally lacks raw tool arguments and
/// results. P0 therefore emits no turns. A later capture producer may provide
/// explicit pairs, but must pass [`validate_agent_world_turns`] before a
/// trajectory can become shadow-ready.
pub fn audit_agent_world_trajectory(
    contract: &AgentTaskContractPreview,
    snapshot: &EventSpineSnapshot,
    commitment_key: &[u8],
) -> AgentWorldTrajectoryAuditV0 {
    let task = task_manifest(contract, commitment_key);
    let event_refs = snapshot
        .events
        .iter()
        .map(|event| event_ref(event, commitment_key))
        .collect::<Vec<_>>();
    let turns = Vec::new();
    let local_chain_consistent =
        crate::event_spine::verify_event_chain(&snapshot.events, &snapshot.integrity.chain_head);

    let action_candidates = snapshot
        .events
        .iter()
        .filter(|event| matches!(event.kind.as_str(), "tool_call" | "semantic_event"))
        .count();
    let exact_observation_candidates = snapshot
        .events
        .iter()
        .filter(|event| has_exact_observation(event))
        .count();
    let preview_only_observation_candidates = snapshot
        .events
        .iter()
        .filter(|event| {
            event.kind == "agent_session_finished"
                && (event.facts.get("stdout_preview").is_some()
                    || event.facts.get("stderr_preview").is_some())
        })
        .count();

    let mut blockers = Vec::new();
    if contract.status != "ready" {
        blockers.push(blocker(
            "invalid_task_contract",
            "the source AgentTaskContract preview is blocked",
        ));
    }
    if !local_chain_consistent {
        blockers.push(blocker(
            "inconsistent_event_spine_chain",
            "the source event-spine hash chain failed local recomputation",
        ));
    }
    if snapshot.truncated_count > 0 {
        blockers.push(blocker(
            "truncated_event_spine",
            "the source snapshot omitted older candidate events",
        ));
    }
    if task.initial_state.is_empty() {
        blockers.push(blocker(
            "missing_initial_state",
            "the task contract contains no effective initial-state fields",
        ));
    }
    if snapshot.event_count == 0 {
        blockers.push(blocker(
            "no_source_events",
            "the source event spine contains no events",
        ));
    }
    if action_candidates > 0 && exact_observation_candidates == 0 {
        blockers.push(blocker(
            "missing_exact_observations",
            "current telemetry records tool metadata or actions but not exact environment observations",
        ));
    }
    if preview_only_observation_candidates > 0 {
        blockers.push(blocker(
            "preview_is_not_observation",
            "session stdout/stderr previews are truncated diagnostics and cannot serve as ground-truth observations",
        ));
    }
    if turns.is_empty() {
        blockers.push(blocker(
            "missing_action_observation_pairs",
            "no source event carries an unambiguous action and exact observation pair",
        ));
    }
    blockers.extend(validate_agent_world_turns(&turns));

    let reconstructability_ratio = if action_candidates == 0 {
        0.0
    } else {
        turns.len() as f64 / action_candidates as f64
    };
    let trajectory_id = sha256_text(&format!(
        "{}\n{}\n{}\n{}",
        AGENT_WORLD_TRAJECTORY_SCHEMA_V0,
        commitment(commitment_key, "contract", &contract.contract.contract_id),
        contract.contract.revision,
        snapshot.integrity.chain_head
    ));
    let status = if blockers.is_empty() {
        "ready_for_shadow"
    } else {
        "blocked"
    };

    AgentWorldTrajectoryAuditV0 {
        schema_version: AGENT_WORLD_TRAJECTORY_AUDIT_SCHEMA_V0.to_string(),
        status: status.to_string(),
        safety: AgentWorldTrajectorySafety::p0(),
        trajectory: AgentWorldTrajectoryV0 {
            schema_version: AGENT_WORLD_TRAJECTORY_SCHEMA_V0.to_string(),
            trajectory_id,
            payload_mode: "digest_only".to_string(),
            task,
            turns,
            provenance: AgentWorldProvenanceV0 {
                source: "event_spine_snapshot".to_string(),
                event_spine_chain_head: snapshot.integrity.chain_head.clone(),
                event_spine_local_chain_consistent: local_chain_consistent,
                candidate_count: snapshot.candidate_count,
                event_count: snapshot.event_count,
                truncated_count: snapshot.truncated_count,
                event_refs,
            },
        },
        coverage: AgentWorldTrajectoryCoverage {
            contract_ready: contract.status == "ready",
            initial_state_fields: contract.effective_state.len(),
            source_events: snapshot.event_count,
            action_candidates,
            exact_observation_candidates,
            preview_only_observation_candidates,
            reconstructed_turns: 0,
            reconstructability_ratio,
            source_snapshot_truncated: snapshot.truncated_count > 0,
        },
        blockers,
    }
}

/// Enforce observed/simulated evidence separation for any future turn producer.
pub fn validate_agent_world_turns(turns: &[AgentWorldTurnV0]) -> Vec<AgentWorldTrajectoryBlocker> {
    let mut blockers = Vec::new();
    let mut seen_turn_indexes = std::collections::BTreeSet::new();
    for turn in turns {
        if !seen_turn_indexes.insert(turn.turn_index) {
            blockers.push(blocker(
                "duplicate_turn_index",
                "turn indexes must be unique",
            ));
        }
        if !is_sha256(&turn.action_sha256) || !is_sha256(&turn.observation_sha256) {
            blockers.push(blocker(
                "invalid_turn_digest",
                &format!(
                    "turn {} has a malformed action or observation digest",
                    turn.turn_index
                ),
            ));
        }
        match turn.observation_origin {
            AgentWorldObservationOrigin::Observed => {
                if turn.evidence_refs.is_empty() {
                    blockers.push(blocker(
                        "observed_turn_without_evidence",
                        &format!(
                            "observed turn {} has no evidence reference",
                            turn.turn_index
                        ),
                    ));
                }
                if turn.evidence_refs.iter().any(|reference| {
                    !is_sha256(&reference.event_id_sha256)
                        || !is_sha256(&reference.payload_sha256)
                        || !is_sha256(&reference.event_hash)
                }) {
                    blockers.push(blocker(
                        "invalid_observed_evidence_ref",
                        &format!(
                            "observed turn {} has a malformed evidence reference",
                            turn.turn_index
                        ),
                    ));
                }
                if turn.attestation_ref.is_some() {
                    blockers.push(blocker(
                        "unresolved_attestation_ref",
                        &format!(
                            "observed turn {} carries an attestation that P0 cannot authenticate",
                            turn.turn_index
                        ),
                    ));
                }
            }
            AgentWorldObservationOrigin::Simulated => {
                if !turn.evidence_refs.is_empty() || turn.attestation_ref.is_some() {
                    blockers.push(blocker(
                        "simulated_turn_claims_evidence",
                        &format!(
                            "simulated turn {} cannot carry evidence or attestation references",
                            turn.turn_index
                        ),
                    ));
                }
            }
        }
    }
    blockers
}

fn task_manifest(
    contract: &AgentTaskContractPreview,
    commitment_key: &[u8],
) -> AgentWorldTaskManifestV0 {
    AgentWorldTaskManifestV0 {
        contract_ref: commitment(commitment_key, "contract", &contract.contract.contract_id),
        contract_revision: contract.contract.revision,
        objective_sha256: commitment(commitment_key, "objective", &contract.contract.objective),
        action_space: contract
            .contract
            .this_attempt_only
            .iter()
            .enumerate()
            .map(|(ordinal, action)| AgentWorldDigestRef {
                ordinal,
                sha256: commitment(commitment_key, "action", action),
            })
            .collect(),
        initial_state: contract
            .effective_state
            .iter()
            .map(|(key, value)| AgentWorldStateDigestRef {
                key_sha256: commitment(commitment_key, "state-key", key),
                value_sha256: commitment(commitment_key, "state-value", value),
            })
            .collect(),
    }
}

fn event_ref(event: &EventSpineEvent, commitment_key: &[u8]) -> AgentWorldEventRef {
    AgentWorldEventRef {
        event_id: commitment(commitment_key, "event-id", &event.event_id),
        ts: event.ts,
        source: event.source.clone(),
        kind: event.kind.clone(),
        ok: event.ok,
        payload_sha256: event.payload_sha256.clone(),
        event_hash: event.hash.clone(),
    }
}

fn has_exact_observation(event: &EventSpineEvent) -> bool {
    event
        .facts
        .as_object()
        .map(|facts| {
            facts.contains_key("observation")
                || facts.contains_key("exact_observation")
                || facts.contains_key("tool_result")
        })
        .unwrap_or(false)
}

fn blocker(code: &str, message: &str) -> AgentWorldTrajectoryBlocker {
    AgentWorldTrajectoryBlocker {
        code: code.to_string(),
        message: message.to_string(),
    }
}

fn sha256_text(value: &str) -> String {
    let mut hasher = Sha256::new();
    hasher.update(value.as_bytes());
    hasher
        .finalize()
        .iter()
        .map(|byte| format!("{byte:02x}"))
        .collect()
}

fn commitment(key: &[u8], domain: &str, value: &str) -> String {
    let mut hasher = Sha256::new();
    hasher.update(domain.as_bytes());
    hasher.update([0]);
    hasher.update(value.as_bytes());
    hasher.update([0]);
    hasher.update(key);
    hasher
        .finalize()
        .iter()
        .map(|byte| format!("{byte:02x}"))
        .collect()
}

fn is_sha256(value: &str) -> bool {
    value.len() == 64 && value.bytes().all(|byte| byte.is_ascii_hexdigit())
}
