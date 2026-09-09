//! Pure, read-only task-contract normalization and preview.
//!
//! This module has no store, runtime, or process-control dependency. It only
//! validates caller-provided state and compiles a deterministic instruction
//! preview for review before any agent action is authorized.

use std::collections::{BTreeMap, BTreeSet};

use serde::{Deserialize, Serialize};

pub const AGENT_TASK_CONTRACT_SCHEMA_V0: &str = "agent_bridge.agent_task_contract.v0";

/// Optional advisory text, separate from the compiled contract and its authority.
pub const AGENT_TASK_CONTRACT_NEXT_STEP_REVIEW: &str =
    include_str!("agent_task_contract_next_step_review.md");

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum AuthorityBoundary {
    ReadOnly,
    ProjectWrite,
    ExternalWrite,
    RuntimeEnablement,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum ParentEvidenceVerdict {
    Accepted,
    AcceptedWithDeviation,
    Rejected,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct ParentEvidenceRef {
    pub reference: String,
    pub verdict: ParentEvidenceVerdict,
    pub authority_boundary: AuthorityBoundary,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct AgentTaskContract {
    pub schema_version: String,
    pub contract_id: String,
    pub revision: u64,
    pub objective: String,
    #[serde(default)]
    pub parent_evidence_refs: Vec<ParentEvidenceRef>,
    #[serde(default)]
    pub this_attempt_only: Vec<String>,
    #[serde(default)]
    pub reserved_actions: Vec<String>,
    #[serde(default)]
    pub continuity_locks: BTreeMap<String, String>,
    #[serde(default)]
    pub allowed_changes: Vec<String>,
    #[serde(default)]
    pub acceptance_criteria: Vec<String>,
    pub authority_boundary: AuthorityBoundary,
    pub attempt_no: u32,
    pub attempt_budget: u32,
    pub changed_variable: Option<String>,
    #[serde(default)]
    pub planned_state: BTreeMap<String, String>,
    #[serde(default)]
    pub observed_state: BTreeMap<String, String>,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct AgentTaskContractSafety {
    pub read_only: bool,
    pub can_spawn_agent: bool,
    pub can_write_memory: bool,
    pub can_mutate_work_memory: bool,
    pub can_promote_canon: bool,
    pub can_enable_runtime: bool,
}

impl AgentTaskContractSafety {
    fn read_only_preview() -> Self {
        Self {
            read_only: true,
            can_spawn_agent: false,
            can_write_memory: false,
            can_mutate_work_memory: false,
            can_promote_canon: false,
            can_enable_runtime: false,
        }
    }
}

impl AuthorityBoundary {
    fn as_str(self) -> &'static str {
        match self {
            Self::ReadOnly => "read_only",
            Self::ProjectWrite => "project_write",
            Self::ExternalWrite => "external_write",
            Self::RuntimeEnablement => "runtime_enablement",
        }
    }
}

impl ParentEvidenceVerdict {
    fn as_str(self) -> &'static str {
        match self {
            Self::Accepted => "accepted",
            Self::AcceptedWithDeviation => "accepted_with_deviation",
            Self::Rejected => "rejected",
        }
    }
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct ContractViolation {
    pub code: String,
    pub message: String,
    #[serde(default)]
    pub fields: Vec<String>,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct AgentTaskContractPreview {
    pub status: String,
    pub safety: AgentTaskContractSafety,
    pub contract: AgentTaskContract,
    pub effective_state: BTreeMap<String, String>,
    pub compiled_instruction: String,
    pub violations: Vec<ContractViolation>,
}

/// Build a deterministic, side-effect-free preview of an agent task contract.
pub fn preview_agent_task_contract(contract: AgentTaskContract) -> AgentTaskContractPreview {
    let effective_state = effective_state(&contract);
    let violations = validate_contract(&contract, &effective_state);
    let blocked = !violations.is_empty();

    AgentTaskContractPreview {
        status: if blocked { "blocked" } else { "ready" }.to_string(),
        safety: AgentTaskContractSafety::read_only_preview(),
        compiled_instruction: if blocked {
            String::new()
        } else {
            compile_instruction(&contract, &effective_state)
        },
        contract,
        effective_state,
        violations,
    }
}

fn compile_instruction(
    contract: &AgentTaskContract,
    effective_state: &BTreeMap<String, String>,
) -> String {
    let mut lines = vec![
        "# Agent Task Contract Preview".to_string(),
        format!("Schema: {}", contract.schema_version),
        format!(
            "Contract: {} rev {}",
            inline_text(&contract.contract_id),
            contract.revision
        ),
        format!("Objective: {}", inline_text(&contract.objective)),
        format!(
            "Authority boundary: {}",
            contract.authority_boundary.as_str()
        ),
        format!(
            "Attempt: {}/{}",
            contract.attempt_no, contract.attempt_budget
        ),
    ];

    if let Some(changed_variable) = contract
        .changed_variable
        .as_deref()
        .map(str::trim)
        .filter(|value| !value.is_empty())
    {
        lines.push(format!(
            "Changed variable: {}",
            inline_text(changed_variable)
        ));
    }

    push_parent_evidence(&mut lines, &contract.parent_evidence_refs);
    push_string_items(
        &mut lines,
        "This attempt only:",
        &contract.this_attempt_only,
    );
    push_string_items(
        &mut lines,
        "Reserved actions — do not perform in this attempt:",
        &contract.reserved_actions,
    );
    push_map_items(&mut lines, "Continuity locks:", &contract.continuity_locks);
    push_string_items(&mut lines, "Allowed changes:", &contract.allowed_changes);
    push_string_items(
        &mut lines,
        "Acceptance criteria:",
        &contract.acceptance_criteria,
    );
    push_map_items(
        &mut lines,
        "Effective accepted state — observed overrides planned:",
        effective_state,
    );

    lines.join("\n")
}

fn push_parent_evidence(lines: &mut Vec<String>, evidence: &[ParentEvidenceRef]) {
    if evidence.is_empty() {
        return;
    }
    lines.push("Accepted parent evidence references:".to_string());
    lines.extend(evidence.iter().map(|item| {
        format!(
            "- {} [{}; authority={}]",
            inline_text(&item.reference),
            item.verdict.as_str(),
            item.authority_boundary.as_str()
        )
    }));
}

fn push_string_items(lines: &mut Vec<String>, heading: &str, items: &[String]) {
    let items = items
        .iter()
        .map(|item| item.trim())
        .filter(|item| !item.is_empty())
        .collect::<Vec<_>>();
    if items.is_empty() {
        return;
    }
    lines.push(heading.to_string());
    lines.extend(
        items
            .into_iter()
            .map(|item| format!("- {}", inline_text(item))),
    );
}

fn push_map_items(lines: &mut Vec<String>, heading: &str, items: &BTreeMap<String, String>) {
    if items.is_empty() {
        return;
    }
    lines.push(heading.to_string());
    lines.extend(
        items
            .iter()
            .map(|(key, value)| format!("- {}={}", inline_text(key), inline_text(value))),
    );
}

fn inline_text(value: &str) -> String {
    let mut rendered = String::with_capacity(value.len());
    for character in value.chars() {
        if character == '\\' {
            rendered.push_str("\\\\");
        } else if character.is_control() {
            rendered.extend(character.escape_default());
        } else {
            rendered.push(character);
        }
    }
    rendered
}

fn effective_state(contract: &AgentTaskContract) -> BTreeMap<String, String> {
    let mut effective = contract.continuity_locks.clone();
    effective.extend(contract.planned_state.clone());
    effective.extend(contract.observed_state.clone());
    effective
}

fn validate_contract(
    contract: &AgentTaskContract,
    effective_state: &BTreeMap<String, String>,
) -> Vec<ContractViolation> {
    let mut violations = Vec::new();

    let mut invalid_identity_fields = Vec::new();
    if contract.contract_id.trim().is_empty() {
        invalid_identity_fields.push("contract_id".to_string());
    }
    if contract.revision == 0 {
        invalid_identity_fields.push("revision".to_string());
    }
    if !invalid_identity_fields.is_empty() {
        violations.push(ContractViolation {
            code: "invalid_contract_identity".to_string(),
            message: "contract_id must be non-empty and revision must be at least 1".to_string(),
            fields: invalid_identity_fields,
        });
    }

    if contract.objective.trim().is_empty() {
        violations.push(ContractViolation {
            code: "missing_objective".to_string(),
            message: "objective must describe the bounded task outcome".to_string(),
            fields: vec!["objective".to_string()],
        });
    }

    if normalized_values(&contract.this_attempt_only).is_empty() {
        violations.push(ContractViolation {
            code: "missing_attempt_scope".to_string(),
            message: "this_attempt_only must contain at least one bounded action".to_string(),
            fields: vec!["this_attempt_only".to_string()],
        });
    }

    if normalized_values(&contract.acceptance_criteria).is_empty() {
        violations.push(ContractViolation {
            code: "missing_acceptance_criteria".to_string(),
            message: "acceptance_criteria must contain at least one observable condition"
                .to_string(),
            fields: vec!["acceptance_criteria".to_string()],
        });
    }

    if contract.schema_version != AGENT_TASK_CONTRACT_SCHEMA_V0 {
        violations.push(ContractViolation {
            code: "unsupported_schema_version".to_string(),
            message: format!(
                "schema_version must be {AGENT_TASK_CONTRACT_SCHEMA_V0}, got {}",
                contract.schema_version
            ),
            fields: vec!["schema_version".to_string()],
        });
    }

    if contract.attempt_no == 0
        || contract.attempt_budget == 0
        || contract.attempt_no > contract.attempt_budget
    {
        violations.push(ContractViolation {
            code: "attempt_budget_exceeded".to_string(),
            message: format!(
                "attempt_no {} is outside the bounded range 1..={}",
                contract.attempt_no, contract.attempt_budget
            ),
            fields: vec!["attempt_no".to_string(), "attempt_budget".to_string()],
        });
    }

    let attempt_actions = normalized_values(&contract.this_attempt_only);
    let reserved_actions = normalized_values(&contract.reserved_actions);
    let overlapping_actions = attempt_actions
        .intersection(&reserved_actions)
        .cloned()
        .collect::<Vec<_>>();
    if !overlapping_actions.is_empty() {
        violations.push(ContractViolation {
            code: "action_scope_overlap".to_string(),
            message: "this_attempt_only and reserved_actions must be disjoint".to_string(),
            fields: overlapping_actions,
        });
    }

    let rejected_refs = contract
        .parent_evidence_refs
        .iter()
        .filter(|evidence| evidence.verdict == ParentEvidenceVerdict::Rejected)
        .map(|evidence| evidence.reference.clone())
        .collect::<Vec<_>>();
    if !rejected_refs.is_empty() {
        violations.push(ContractViolation {
            code: "rejected_parent_evidence".to_string(),
            message: "a rejected parent cannot authorize a child contract".to_string(),
            fields: rejected_refs,
        });
    }

    let invalid_parent_refs = contract
        .parent_evidence_refs
        .iter()
        .enumerate()
        .filter(|(_, evidence)| evidence.reference.trim().is_empty())
        .map(|(index, _)| format!("parent_evidence_refs[{index}].reference"))
        .collect::<Vec<_>>();
    if !invalid_parent_refs.is_empty() {
        violations.push(ContractViolation {
            code: "invalid_parent_evidence_ref".to_string(),
            message: "parent evidence references must be non-empty exact identifiers".to_string(),
            fields: invalid_parent_refs,
        });
    }

    let has_accepted_parent = contract
        .parent_evidence_refs
        .iter()
        .any(|evidence| evidence.verdict != ParentEvidenceVerdict::Rejected);
    if contract.authority_boundary != AuthorityBoundary::ReadOnly && !has_accepted_parent {
        violations.push(ContractViolation {
            code: "authority_evidence_required".to_string(),
            message: "a non-read-only authority boundary requires accepted parent evidence"
                .to_string(),
            fields: vec![
                "authority_boundary".to_string(),
                "parent_evidence_refs".to_string(),
            ],
        });
    }

    let authority_change_allowed = contract
        .allowed_changes
        .iter()
        .any(|field| field.trim().eq_ignore_ascii_case("authority_boundary"));
    let authority_drift_refs = contract
        .parent_evidence_refs
        .iter()
        .filter(|evidence| evidence.verdict != ParentEvidenceVerdict::Rejected)
        .filter(|evidence| evidence.authority_boundary != contract.authority_boundary)
        .map(|evidence| evidence.reference.clone())
        .collect::<Vec<_>>();
    if !authority_change_allowed && !authority_drift_refs.is_empty() {
        violations.push(ContractViolation {
            code: "authority_boundary_drift".to_string(),
            message: "authority_boundary differs from accepted parent evidence without an explicit allowed change"
                .to_string(),
            fields: authority_drift_refs,
        });
    }

    let broken_locks = contract
        .continuity_locks
        .iter()
        .filter(|(key, locked_value)| {
            effective_state
                .get(*key)
                .is_some_and(|effective_value| effective_value != *locked_value)
                && !state_change_allowed(&contract.allowed_changes, key)
        })
        .map(|(key, _)| key.clone())
        .collect::<Vec<_>>();
    if !broken_locks.is_empty() {
        violations.push(ContractViolation {
            code: "continuity_lock_violation".to_string(),
            message: "effective state conflicts with a continuity lock without an explicit allowed change"
                .to_string(),
            fields: broken_locks,
        });
    }

    violations
}

fn normalized_values(values: &[String]) -> BTreeSet<String> {
    values
        .iter()
        .map(|value| value.trim().to_lowercase())
        .filter(|value| !value.is_empty())
        .collect()
}

fn state_change_allowed(allowed_changes: &[String], key: &str) -> bool {
    let key = key.trim();
    allowed_changes.iter().any(|field| {
        let field = field.trim();
        field.eq_ignore_ascii_case(key) || field.eq_ignore_ascii_case(&format!("state.{key}"))
    })
}
