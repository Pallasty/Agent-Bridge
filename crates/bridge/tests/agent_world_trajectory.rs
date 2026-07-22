use std::collections::BTreeMap;

use ab_bridge::{
    agent_task_contract::{
        preview_agent_task_contract, AgentTaskContract, AuthorityBoundary,
        AGENT_TASK_CONTRACT_SCHEMA_V0,
    },
    agent_world_trajectory::{
        audit_agent_world_trajectory, validate_agent_world_turns, AgentWorldEvidenceRef,
        AgentWorldObservationOrigin, AgentWorldTurnV0, AGENT_WORLD_TRAJECTORY_AUDIT_SCHEMA_V0,
        AGENT_WORLD_TRAJECTORY_SCHEMA_V0,
    },
    event_spine::{
        EventSpineEvent, EventSpineIntegrity, EventSpineSnapshot, EventSpineSourceCount,
    },
};
use serde_json::json;

fn valid_contract() -> AgentTaskContract {
    AgentTaskContract {
        schema_version: AGENT_TASK_CONTRACT_SCHEMA_V0.to_string(),
        contract_id: "contract:qwen-agentworld:p0".to_string(),
        revision: 1,
        objective: "Audit a private terminal trajectory containing secret-objective-value"
            .to_string(),
        parent_evidence_refs: vec![],
        this_attempt_only: vec!["run secret-action-value in a sandbox".to_string()],
        reserved_actions: vec!["send traces to an external endpoint".to_string()],
        continuity_locks: BTreeMap::new(),
        allowed_changes: vec![],
        acceptance_criteria: vec!["raw values are absent from the audit".to_string()],
        authority_boundary: AuthorityBoundary::ReadOnly,
        attempt_no: 1,
        attempt_budget: 1,
        changed_variable: Some("trajectory manifest".to_string()),
        planned_state: BTreeMap::from([(
            "api_token".to_string(),
            "secret-state-value".to_string(),
        )]),
        observed_state: BTreeMap::new(),
    }
}

fn event(kind: &str, source: &str, event_id: &str, facts: serde_json::Value) -> EventSpineEvent {
    EventSpineEvent {
        event_id: event_id.to_string(),
        ts: 100,
        source: source.to_string(),
        kind: kind.to_string(),
        label: "private-label-is-not-exported".to_string(),
        ok: Some(true),
        payload_sha256: "payload-hash".to_string(),
        prev_hash: "prev-hash".to_string(),
        hash: format!("event-hash-{event_id}"),
        facts,
    }
}

fn snapshot(events: Vec<EventSpineEvent>) -> EventSpineSnapshot {
    EventSpineSnapshot {
        schema_version: 1,
        generated_at: 120,
        window_secs: 60,
        limit: 40,
        candidate_count: events.len(),
        event_count: events.len(),
        truncated_count: 0,
        sources: vec![EventSpineSourceCount {
            source: "mixed".to_string(),
            count: events.len(),
        }],
        integrity: EventSpineIntegrity {
            hash_algorithm: "sha256",
            chain_head: "verified-chain-head".to_string(),
            verified: true,
        },
        events,
    }
}

#[test]
fn p0_audit_fails_closed_when_telemetry_has_no_exact_pairs() {
    let contract = preview_agent_task_contract(valid_contract());
    let snapshot = snapshot(vec![
        event(
            "tool_call",
            "mcp_tool_calls",
            "call-1",
            json!({
                "tool_name": "terminal_send_keys",
                "args_size": 18,
                "result_size": 9,
                "private": "Bearer secret-event-value"
            }),
        ),
        event(
            "agent_session_finished",
            "agent_sessions",
            "session-1",
            json!({
                "stdout_preview": "secret-stdout-preview",
                "stderr_preview": null,
                "exit_code": 0
            }),
        ),
    ]);

    let audit = audit_agent_world_trajectory(&contract, &snapshot, b"test-only-commitment-key");

    assert_eq!(audit.schema_version, AGENT_WORLD_TRAJECTORY_AUDIT_SCHEMA_V0);
    assert_eq!(
        audit.trajectory.schema_version,
        AGENT_WORLD_TRAJECTORY_SCHEMA_V0
    );
    assert_eq!(audit.status, "blocked");
    assert_eq!(audit.trajectory.payload_mode, "digest_only");
    assert!(audit.trajectory.turns.is_empty());
    assert_eq!(audit.coverage.action_candidates, 1);
    assert_eq!(audit.coverage.exact_observation_candidates, 0);
    assert_eq!(audit.coverage.preview_only_observation_candidates, 1);
    assert_eq!(audit.coverage.reconstructed_turns, 0);
    assert_eq!(audit.coverage.reconstructability_ratio, 0.0);

    let blocker_codes = audit
        .blockers
        .iter()
        .map(|item| item.code.as_str())
        .collect::<Vec<_>>();
    assert!(blocker_codes.contains(&"missing_exact_observations"));
    assert!(blocker_codes.contains(&"preview_is_not_observation"));
    assert!(blocker_codes.contains(&"missing_action_observation_pairs"));
}

#[test]
fn p0_audit_serialization_never_exports_raw_contract_or_event_content() {
    let contract = preview_agent_task_contract(valid_contract());
    let snapshot = snapshot(vec![event(
        "tool_call",
        "mcp_tool_calls",
        "call-1",
        json!({"private": "Bearer secret-event-value"}),
    )]);

    let serialized = serde_json::to_string(&audit_agent_world_trajectory(
        &contract,
        &snapshot,
        b"test-only-commitment-key",
    ))
    .expect("serialize audit");

    for secret in [
        "secret-objective-value",
        "secret-action-value",
        "secret-state-value",
        "secret-event-value",
        "private-label-is-not-exported",
        "contract:qwen-agentworld:p0",
        "api_token",
    ] {
        assert!(!serialized.contains(secret), "leaked {secret}");
    }
    assert!(serialized.contains("objective_sha256"));
    assert!(serialized.contains("value_sha256"));
    assert!(serialized.contains("payload-hash"));
}

#[test]
fn p0_audit_is_deterministic_for_same_contract_and_chain() {
    let contract = preview_agent_task_contract(valid_contract());
    let snapshot = snapshot(vec![event(
        "semantic_event",
        "semantic_events",
        "semantic-1",
        json!({"action": "click", "target": "private-target"}),
    )]);

    let left = audit_agent_world_trajectory(&contract, &snapshot, b"test-only-commitment-key");
    let right = audit_agent_world_trajectory(&contract, &snapshot, b"test-only-commitment-key");

    assert_eq!(left, right);
    assert_eq!(left.trajectory.trajectory_id.len(), 64);
}

#[test]
fn simulated_turn_cannot_claim_evidence_or_attestation() {
    let blockers = validate_agent_world_turns(&[AgentWorldTurnV0 {
        turn_index: 1,
        action_sha256: "a".repeat(64),
        observation_sha256: "b".repeat(64),
        observation_origin: AgentWorldObservationOrigin::Simulated,
        evidence_refs: vec![AgentWorldEvidenceRef {
            event_id_sha256: "a".repeat(64),
            payload_sha256: "b".repeat(64),
            event_hash: "c".repeat(64),
        }],
        attestation_ref: Some("sandbox:attestation:1".to_string()),
    }]);

    assert_eq!(blockers.len(), 1);
    assert_eq!(blockers[0].code, "simulated_turn_claims_evidence");
}

#[test]
fn observed_turn_requires_evidence_but_simulated_turn_without_it_is_valid() {
    let observed = AgentWorldTurnV0 {
        turn_index: 1,
        action_sha256: "a".repeat(64),
        observation_sha256: "b".repeat(64),
        observation_origin: AgentWorldObservationOrigin::Observed,
        evidence_refs: vec![],
        attestation_ref: None,
    };
    let simulated = AgentWorldTurnV0 {
        turn_index: 2,
        observation_origin: AgentWorldObservationOrigin::Simulated,
        ..observed.clone()
    };

    let observed_blockers = validate_agent_world_turns(&[observed]);
    assert_eq!(observed_blockers.len(), 1);
    assert_eq!(observed_blockers[0].code, "observed_turn_without_evidence");
    assert!(validate_agent_world_turns(&[simulated]).is_empty());
}

#[test]
fn exact_observation_field_is_not_auto_paired_with_an_action() {
    let contract = preview_agent_task_contract(valid_contract());
    let snapshot = snapshot(vec![event(
        "tool_call",
        "future_capture",
        "future-1",
        json!({"action": "hashed elsewhere", "observation": "private output"}),
    )]);

    let audit = audit_agent_world_trajectory(&contract, &snapshot, b"test-only-commitment-key");

    assert_eq!(audit.coverage.exact_observation_candidates, 1);
    assert_eq!(audit.coverage.reconstructed_turns, 0);
    assert!(audit
        .blockers
        .iter()
        .any(|item| item.code == "missing_action_observation_pairs"));
}

#[test]
fn claimed_verified_bit_does_not_override_local_chain_failure() {
    let contract = preview_agent_task_contract(valid_contract());
    let snapshot = snapshot(vec![event(
        "tool_call",
        "mcp_tool_calls",
        "forged",
        json!({}),
    )]);
    assert!(snapshot.integrity.verified);

    let audit = audit_agent_world_trajectory(&contract, &snapshot, b"test-only-commitment-key");
    assert!(
        !audit
            .trajectory
            .provenance
            .event_spine_local_chain_consistent
    );
    assert!(audit
        .blockers
        .iter()
        .any(|item| item.code == "inconsistent_event_spine_chain"));
}

#[test]
fn observed_turn_rejects_malformed_evidence_and_duplicate_index() {
    let turn = AgentWorldTurnV0 {
        turn_index: 1,
        action_sha256: "a".repeat(64),
        observation_sha256: "b".repeat(64),
        observation_origin: AgentWorldObservationOrigin::Observed,
        evidence_refs: vec![AgentWorldEvidenceRef {
            event_id_sha256: "not-a-digest".to_string(),
            payload_sha256: "c".repeat(64),
            event_hash: "d".repeat(64),
        }],
        attestation_ref: None,
    };
    let blockers = validate_agent_world_turns(&[turn.clone(), turn]);
    assert!(blockers
        .iter()
        .any(|item| item.code == "invalid_observed_evidence_ref"));
    assert!(blockers
        .iter()
        .any(|item| item.code == "duplicate_turn_index"));
}
