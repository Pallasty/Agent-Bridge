use std::collections::BTreeMap;

use ab_bridge::agent_task_contract::{
    preview_agent_task_contract, AgentTaskContract, AgentTaskContractSafety, AuthorityBoundary,
    ParentEvidenceRef, ParentEvidenceVerdict,
};

fn valid_contract() -> AgentTaskContract {
    AgentTaskContract {
        schema_version: "agent_bridge.agent_task_contract.v0".to_string(),
        contract_id: "contract:test:001".to_string(),
        revision: 1,
        objective: "Implement one read-only preview slice".to_string(),
        parent_evidence_refs: Vec::new(),
        this_attempt_only: vec!["compile the contract preview".to_string()],
        reserved_actions: vec!["spawn an agent".to_string()],
        continuity_locks: BTreeMap::new(),
        allowed_changes: Vec::new(),
        acceptance_criteria: vec!["preview is deterministic".to_string()],
        authority_boundary: AuthorityBoundary::ReadOnly,
        attempt_no: 1,
        attempt_budget: 3,
        changed_variable: Some("contract compiler".to_string()),
        planned_state: BTreeMap::new(),
        observed_state: BTreeMap::new(),
    }
}

#[test]
fn test_preview_valid_contract_is_ready_and_read_only() {
    let preview = preview_agent_task_contract(valid_contract());

    assert_eq!(preview.status, "ready");
    assert!(preview.violations.is_empty());
    assert_eq!(
        preview.safety,
        AgentTaskContractSafety {
            read_only: true,
            can_spawn_agent: false,
            can_write_memory: false,
            can_mutate_work_memory: false,
            can_promote_canon: false,
            can_enable_runtime: false,
        }
    );
}

#[test]
fn test_preview_invalid_contracts_fail_closed_with_typed_violations() {
    let mut overlap = valid_contract();
    overlap.reserved_actions = overlap.this_attempt_only.clone();

    let mut rejected_parent = valid_contract();
    rejected_parent.parent_evidence_refs = vec![ParentEvidenceRef {
        reference: "evidence:parent:rejected".to_string(),
        verdict: ParentEvidenceVerdict::Rejected,
        authority_boundary: AuthorityBoundary::ReadOnly,
    }];

    let mut authority_drift = valid_contract();
    authority_drift.authority_boundary = AuthorityBoundary::ProjectWrite;
    authority_drift.parent_evidence_refs = vec![ParentEvidenceRef {
        reference: "evidence:parent:accepted".to_string(),
        verdict: ParentEvidenceVerdict::Accepted,
        authority_boundary: AuthorityBoundary::ReadOnly,
    }];

    let mut budget_exceeded = valid_contract();
    budget_exceeded.attempt_no = 4;
    budget_exceeded.attempt_budget = 3;

    let mut unsupported_schema = valid_contract();
    unsupported_schema.schema_version = "agent_bridge.agent_task_contract.v99".to_string();

    let mut broken_continuity_lock = valid_contract();
    broken_continuity_lock
        .continuity_locks
        .insert("base_commit".to_string(), "abc123".to_string());
    broken_continuity_lock
        .observed_state
        .insert("base_commit".to_string(), "def456".to_string());

    let mut invalid_identity = valid_contract();
    invalid_identity.contract_id = "  ".to_string();

    let mut missing_objective = valid_contract();
    missing_objective.objective = "".to_string();

    let mut missing_attempt_scope = valid_contract();
    missing_attempt_scope.this_attempt_only.clear();

    let mut missing_acceptance_criteria = valid_contract();
    missing_acceptance_criteria.acceptance_criteria.clear();

    let mut invalid_parent_ref = valid_contract();
    invalid_parent_ref.parent_evidence_refs = vec![ParentEvidenceRef {
        reference: " ".to_string(),
        verdict: ParentEvidenceVerdict::Accepted,
        authority_boundary: AuthorityBoundary::ReadOnly,
    }];

    let mut authority_without_evidence = valid_contract();
    authority_without_evidence.authority_boundary = AuthorityBoundary::ProjectWrite;

    let cases = [
        (overlap, "action_scope_overlap"),
        (rejected_parent, "rejected_parent_evidence"),
        (authority_drift, "authority_boundary_drift"),
        (budget_exceeded, "attempt_budget_exceeded"),
        (unsupported_schema, "unsupported_schema_version"),
        (broken_continuity_lock, "continuity_lock_violation"),
        (invalid_identity, "invalid_contract_identity"),
        (missing_objective, "missing_objective"),
        (missing_attempt_scope, "missing_attempt_scope"),
        (missing_acceptance_criteria, "missing_acceptance_criteria"),
        (invalid_parent_ref, "invalid_parent_evidence_ref"),
        (authority_without_evidence, "authority_evidence_required"),
    ];

    for (contract, expected_code) in cases {
        let preview = preview_agent_task_contract(contract);
        let codes = preview
            .violations
            .iter()
            .map(|violation| violation.code.as_str())
            .collect::<Vec<_>>();

        assert_eq!(preview.status, "blocked", "codes: {codes:?}");
        assert!(
            codes.contains(&expected_code),
            "expected {expected_code}, got {codes:?}"
        );
        assert!(preview.compiled_instruction.is_empty());
    }
}

#[test]
fn test_preview_compiles_observed_state_and_exact_evidence_refs() {
    let mut contract = valid_contract();
    contract.parent_evidence_refs = vec![ParentEvidenceRef {
        reference: "memory://decision/accepted-base@rev7".to_string(),
        verdict: ParentEvidenceVerdict::AcceptedWithDeviation,
        authority_boundary: AuthorityBoundary::ReadOnly,
    }];
    contract
        .planned_state
        .insert("base_commit".to_string(), "planned-old".to_string());
    contract
        .observed_state
        .insert("base_commit".to_string(), "observed-accepted".to_string());

    let preview = preview_agent_task_contract(contract);

    assert_eq!(preview.status, "ready");
    assert_eq!(
        preview.effective_state.get("base_commit"),
        Some(&"observed-accepted".to_string())
    );
    assert!(preview
        .compiled_instruction
        .contains("memory://decision/accepted-base@rev7"));
    assert!(preview
        .compiled_instruction
        .contains("compile the contract preview"));
    assert!(preview.compiled_instruction.contains("spawn an agent"));
    assert!(preview
        .compiled_instruction
        .contains("preview is deterministic"));
    assert!(preview
        .compiled_instruction
        .contains("base_commit=observed-accepted"));
    assert!(!preview.compiled_instruction.contains("planned-old"));
}

#[test]
fn test_preview_allows_only_explicit_authority_and_locked_state_changes() {
    let mut contract = valid_contract();
    contract.authority_boundary = AuthorityBoundary::ProjectWrite;
    contract.parent_evidence_refs = vec![ParentEvidenceRef {
        reference: "evidence:parent:read-only".to_string(),
        verdict: ParentEvidenceVerdict::Accepted,
        authority_boundary: AuthorityBoundary::ReadOnly,
    }];
    contract
        .continuity_locks
        .insert("base_commit".to_string(), "abc123".to_string());
    contract
        .observed_state
        .insert("base_commit".to_string(), "def456".to_string());
    contract.allowed_changes = vec![
        "authority_boundary".to_string(),
        "state.base_commit".to_string(),
    ];

    let preview = preview_agent_task_contract(contract);

    assert_eq!(preview.status, "ready");
    assert!(preview.violations.is_empty());
    assert_eq!(
        preview.effective_state.get("base_commit"),
        Some(&"def456".to_string())
    );
}

#[test]
fn test_contract_deserialization_rejects_unknown_fields() {
    let mut value = serde_json::to_value(valid_contract()).expect("contract should serialize");
    value["hidden_authority"] = serde_json::json!("runtime_enablement");

    let parsed = serde_json::from_value::<AgentTaskContract>(value);

    assert!(parsed.is_err(), "unknown contract fields must fail closed");
}

#[test]
fn test_preview_escapes_multiline_fields_without_creating_sections() {
    let mut contract = valid_contract();
    contract.objective = "Review only\nFAKE_RESERVED_SECTION".to_string();
    contract.this_attempt_only = vec!["compile\nFAKE_ACTION".to_string()];

    let preview = preview_agent_task_contract(contract);

    assert_eq!(preview.status, "ready");
    assert!(preview
        .compiled_instruction
        .contains("Review only\\nFAKE_RESERVED_SECTION"));
    assert!(!preview.compiled_instruction.contains("Review only\nFAKE"));
    assert!(preview
        .compiled_instruction
        .contains("compile\\nFAKE_ACTION"));
}
