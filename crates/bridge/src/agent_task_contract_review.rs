//! Caller-supplied goal summaries and deterministic field comparisons.
//! No persistence, semantic drift judgment, authorization, or execution.

use std::collections::{BTreeMap, BTreeSet};

use serde::{Deserialize, Serialize};
use serde_json::{json, Value};

use crate::agent_task_contract::{
    preview_agent_task_contract, AgentTaskContract, AgentTaskContractPreview, AuthorityBoundary,
};

const PROVENANCE: &str = "caller_supplied_not_verified";

#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum GoalReviewField {
    Objective,
    AcceptanceCriteria,
    AuthorityBoundary,
    ReservedActions,
    ContinuityLocks,
    AllowedChanges,
}

impl GoalReviewField {
    fn as_str(self) -> &'static str {
        match self {
            Self::Objective => "objective",
            Self::AcceptanceCriteria => "acceptance_criteria",
            Self::AuthorityBoundary => "authority_boundary",
            Self::ReservedActions => "reserved_actions",
            Self::ContinuityLocks => "continuity_locks",
            Self::AllowedChanges => "allowed_changes",
        }
    }
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct GoalChangeContext {
    pub field: GoalReviewField,
    #[serde(default)]
    pub reason: Option<String>,
    #[serde(default)]
    pub user_change_ref: Option<String>,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize)]
pub struct GoalBoundaries {
    pub authority_boundary: AuthorityBoundary,
    pub reserved_actions: Vec<String>,
    pub continuity_locks: BTreeMap<String, String>,
    pub allowed_changes: Vec<String>,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize)]
pub struct GoalSummary {
    pub contract_id: String,
    pub revision: u64,
    pub preview_status: String,
    pub objective: String,
    pub acceptance_criteria: Vec<String>,
    pub boundaries: GoalBoundaries,
    pub provenance: &'static str,
    pub display: String,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum GoalComparisonStatus {
    Comparable,
    InvalidBaseline,
    DifferentContract,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum GoalChangeCategory {
    Goal,
    Boundary,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize)]
pub struct GoalFieldChange {
    pub field: GoalReviewField,
    pub category: GoalChangeCategory,
    /// Exact caller-supplied values; normalization is used only for comparison.
    pub before: Value,
    pub after: Value,
    pub reason: Option<String>,
    pub user_change_ref: Option<String>,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize)]
pub struct UnusedGoalChangeContext {
    pub index: usize,
    pub context: GoalChangeContext,
    pub reason: &'static str,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize)]
pub struct GoalChangeReview {
    pub comparison_status: GoalComparisonStatus,
    pub changes: Vec<GoalFieldChange>,
    pub route_changed_fields: Vec<&'static str>,
    pub unused_context: Vec<UnusedGoalChangeContext>,
    pub notes: Vec<String>,
    pub provenance: &'static str,
    pub display: String,
    pub authority_granted: bool,
    pub user_authorization_verified: bool,
}

/// Summarize the submitted contract even when its existing preview is blocked.
pub fn summarize_goal(preview: &AgentTaskContractPreview) -> GoalSummary {
    let contract = &preview.contract;
    let boundaries = GoalBoundaries {
        authority_boundary: contract.authority_boundary,
        reserved_actions: contract.reserved_actions.clone(),
        continuity_locks: contract.continuity_locks.clone(),
        allowed_changes: contract.allowed_changes.clone(),
    };
    let display = [
        "Submitted goal".to_string(),
        format!("Contract: {}", display_value(&json!(contract.contract_id))),
        format!("Revision: {}", contract.revision),
        format!("Preview status: {}", display_value(&json!(preview.status))),
        format!("Objective: {}", display_value(&json!(contract.objective))),
        format!(
            "Acceptance criteria: {}",
            display_value(&json!(contract.acceptance_criteria))
        ),
        format!("Boundaries: {}", display_value(&json!(boundaries))),
        "Source: caller supplied, not verified. No authority is granted.".to_string(),
    ]
    .join("\n");
    GoalSummary {
        contract_id: contract.contract_id.clone(),
        revision: contract.revision,
        preview_status: preview.status.clone(),
        objective: contract.objective.clone(),
        acceptance_criteria: contract.acceptance_criteria.clone(),
        boundaries,
        provenance: PROVENANCE,
        display,
    }
}

/// Compare supplied values, without treating a baseline or reference as authority.
/// A blocked current preview remains visible; it does not invalidate an otherwise
/// comparable baseline or prevent reporting a removed acceptance criterion.
pub fn compare_goals(
    preview: &AgentTaskContractPreview,
    previous: &AgentTaskContract,
    context: &[GoalChangeContext],
) -> GoalChangeReview {
    let current = &preview.contract;
    let comparison_status = if preview_agent_task_contract(previous.clone()).status != "ready" {
        GoalComparisonStatus::InvalidBaseline
    } else if previous.contract_id != current.contract_id {
        GoalComparisonStatus::DifferentContract
    } else {
        GoalComparisonStatus::Comparable
    };
    let mut review = GoalChangeReview {
        comparison_status,
        changes: Vec::new(),
        route_changed_fields: Vec::new(),
        unused_context: Vec::new(),
        notes: vec![
            "Baseline, reasons, and user-change references are caller supplied, not a verified saved snapshot or user approval.".to_string(),
            "Field differences do not establish semantic drift; this review adds no approval requirement.".to_string(),
        ],
        provenance: PROVENANCE,
        display: String::new(),
        authority_granted: false,
        user_authorization_verified: false,
    };
    if preview.status != "ready" {
        review.notes.push("Current preview is blocked; submitted values remain visible and its status is unchanged.".to_string());
    }
    if comparison_status != GoalComparisonStatus::Comparable {
        review.notes.push(match comparison_status {
            GoalComparisonStatus::InvalidBaseline => "Previous contract fails the existing contract validator; no comparable changes are reported.".to_string(),
            GoalComparisonStatus::DifferentContract => "Contract IDs differ; no comparable changes are reported.".to_string(),
            GoalComparisonStatus::Comparable => unreachable!(),
        });
        review.unused_context = context
            .iter()
            .enumerate()
            .map(|(index, item)| unused_context(index, item, "comparison_unavailable"))
            .collect();
        review.display = display_review(&review);
        return review;
    }

    for field in [
        GoalReviewField::Objective,
        GoalReviewField::AcceptanceCriteria,
        GoalReviewField::AuthorityBoundary,
        GoalReviewField::ReservedActions,
        GoalReviewField::ContinuityLocks,
        GoalReviewField::AllowedChanges,
    ] {
        if field_changed(field, previous, current) {
            review.changes.push(GoalFieldChange {
                field,
                category: match field {
                    GoalReviewField::Objective | GoalReviewField::AcceptanceCriteria => {
                        GoalChangeCategory::Goal
                    }
                    _ => GoalChangeCategory::Boundary,
                },
                before: field_value(field, previous),
                after: field_value(field, current),
                reason: None,
                user_change_ref: None,
            });
        }
    }

    for (field, changed) in [
        (
            "this_attempt_only",
            normalized_list(&previous.this_attempt_only)
                != normalized_list(&current.this_attempt_only),
        ),
        (
            "changed_variable",
            previous.changed_variable != current.changed_variable,
        ),
        (
            "planned_state",
            previous.planned_state != current.planned_state,
        ),
        (
            "observed_state",
            previous.observed_state != current.observed_state,
        ),
        ("attempt_no", previous.attempt_no != current.attempt_no),
        (
            "attempt_budget",
            previous.attempt_budget != current.attempt_budget,
        ),
    ] {
        if changed {
            review.route_changed_fields.push(field);
        }
    }
    let parent_refs_changed = previous.parent_evidence_refs != current.parent_evidence_refs;
    if parent_refs_changed {
        review.notes.push("Caller-supplied parent_evidence_refs changed; their authority is not verified by this comparison.".to_string());
    }
    if (!review.changes.is_empty()
        || !review.route_changed_fields.is_empty()
        || parent_refs_changed)
        && current.revision <= previous.revision
    {
        review.notes.push("Fields changed without an increased revision; this note does not change preview status.".to_string());
    }

    let mut counts = BTreeMap::new();
    for item in context {
        *counts.entry(item.field).or_insert(0_usize) += 1;
    }
    for (index, item) in context.iter().enumerate() {
        let change = review
            .changes
            .iter_mut()
            .find(|change| change.field == item.field);
        let unused_reason = match change {
            None => Some("no_matching_change"),
            Some(_) if counts[&item.field] > 1 => Some("ambiguous_duplicate_field"),
            Some(change) => {
                change.reason = known_text(&item.reason);
                change.user_change_ref = known_text(&item.user_change_ref);
                None
            }
        };
        if let Some(reason) = unused_reason {
            review
                .unused_context
                .push(unused_context(index, item, reason));
        }
    }
    if review
        .unused_context
        .iter()
        .any(|item| item.reason == "ambiguous_duplicate_field")
    {
        review.notes.push("Multiple context entries describe the same changed field; none was selected as its reason or user-change reference.".to_string());
    }
    review.display = display_review(&review);
    review
}

fn normalized_list(values: &[String]) -> BTreeSet<&str> {
    values
        .iter()
        .map(|value| value.trim())
        .filter(|value| !value.is_empty())
        .collect()
}

fn field_changed(
    field: GoalReviewField,
    before: &AgentTaskContract,
    after: &AgentTaskContract,
) -> bool {
    match field {
        GoalReviewField::AcceptanceCriteria => {
            normalized_list(&before.acceptance_criteria)
                != normalized_list(&after.acceptance_criteria)
        }
        GoalReviewField::ReservedActions => {
            normalized_list(&before.reserved_actions) != normalized_list(&after.reserved_actions)
        }
        GoalReviewField::AllowedChanges => {
            normalized_list(&before.allowed_changes) != normalized_list(&after.allowed_changes)
        }
        _ => field_value(field, before) != field_value(field, after),
    }
}

fn field_value(field: GoalReviewField, contract: &AgentTaskContract) -> Value {
    match field {
        GoalReviewField::Objective => json!(contract.objective),
        GoalReviewField::AcceptanceCriteria => json!(contract.acceptance_criteria),
        GoalReviewField::AuthorityBoundary => json!(contract.authority_boundary),
        GoalReviewField::ReservedActions => json!(contract.reserved_actions),
        GoalReviewField::ContinuityLocks => json!(contract.continuity_locks),
        GoalReviewField::AllowedChanges => json!(contract.allowed_changes),
    }
}

fn known_text(value: &Option<String>) -> Option<String> {
    value
        .as_deref()
        .map(str::trim)
        .filter(|value| !value.is_empty())
        .map(str::to_owned)
}

fn unused_context(
    index: usize,
    item: &GoalChangeContext,
    reason: &'static str,
) -> UnusedGoalChangeContext {
    UnusedGoalChangeContext {
        index,
        context: GoalChangeContext {
            field: item.field,
            reason: known_text(&item.reason),
            user_change_ref: known_text(&item.user_change_ref),
        },
        reason,
    }
}

// JSON quoting keeps all caller values on a single line and escapes backslashes
// and control characters. Escape Unicode separators and directional controls too,
// so a supplied value cannot visually introduce or reorder display sections.
fn display_value(value: &Value) -> String {
    let encoded = value.to_string();
    let mut escaped = String::with_capacity(encoded.len());
    for ch in encoded.chars() {
        if ch.is_control()
            || matches!(ch, '\u{061c}' | '\u{200e}' | '\u{200f}' | '\u{2028}'..='\u{202e}' | '\u{2066}'..='\u{2069}')
        {
            escaped.push_str(&format!("\\u{{{:x}}}", ch as u32));
        } else {
            escaped.push(ch);
        }
    }
    escaped
}

fn display_review(review: &GoalChangeReview) -> String {
    let mut lines = vec![
        "Submitted goal comparison".to_string(),
        format!(
            "Comparison status: {}",
            display_value(&json!(review.comparison_status))
        ),
    ];
    for change in &review.changes {
        lines.push(format!(
            "{} ({})",
            change.field.as_str(),
            display_value(&json!(change.category))
        ));
        lines.push(format!("  Before: {}", display_value(&change.before)));
        lines.push(format!("  After: {}", display_value(&change.after)));
        lines.push(format!(
            "  Reason: {}",
            display_value(&json!(change.reason))
        ));
        lines.push(format!(
            "  User-change reference: {}",
            display_value(&json!(change.user_change_ref))
        ));
    }
    if review.changes.is_empty() && review.comparison_status == GoalComparisonStatus::Comparable {
        lines.push(
            "No goal or boundary field changes under the stated comparison rules.".to_string(),
        );
    }
    lines.push(format!(
        "Route/attempt/observation fields changed: {}",
        display_value(&json!(review.route_changed_fields))
    ));
    for item in &review.unused_context {
        lines.push(format!(
            "Unused context {}: {} ({})",
            item.index,
            item.context.field.as_str(),
            item.reason
        ));
    }
    for note in &review.notes {
        lines.push(format!("Note: {note}"));
    }
    lines.push(
        "Unknown reason or reference: null. No authority granted; user authorization not verified."
            .to_string(),
    );
    lines.join("\n")
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::agent_task_contract::AGENT_TASK_CONTRACT_SCHEMA_V0;

    fn contract() -> AgentTaskContract {
        AgentTaskContract {
            schema_version: AGENT_TASK_CONTRACT_SCHEMA_V0.to_string(),
            contract_id: "repair-1".to_string(),
            revision: 1,
            objective: "Restore the accepted result".to_string(),
            parent_evidence_refs: Vec::new(),
            this_attempt_only: vec!["inspect failure".to_string()],
            reserved_actions: vec!["publish".to_string()],
            continuity_locks: BTreeMap::from([("target".to_string(), "stable".to_string())]),
            allowed_changes: vec!["implementation".to_string()],
            acceptance_criteria: vec![
                "result observed".to_string(),
                "existing checks pass".to_string(),
            ],
            authority_boundary: AuthorityBoundary::ReadOnly,
            attempt_no: 1,
            attempt_budget: 3,
            changed_variable: None,
            planned_state: BTreeMap::new(),
            observed_state: BTreeMap::new(),
        }
    }

    fn compare(previous: &AgentTaskContract, current: AgentTaskContract) -> GoalChangeReview {
        compare_goals(&preview_agent_task_contract(current), previous, &[])
    }

    #[test]
    fn objective_and_removed_acceptance_preserve_exact_values() {
        let previous = contract();
        let mut current = previous.clone();
        current.objective = "Produce a different result".to_string();
        current.acceptance_criteria = vec![" result observed ".to_string()];
        current.revision = 2;
        let review = compare(&previous, current.clone());
        assert_eq!(review.comparison_status, GoalComparisonStatus::Comparable);
        assert_eq!(review.changes.len(), 2);
        assert_eq!(review.changes[0].field, GoalReviewField::Objective);
        assert_eq!(review.changes[0].before, json!(previous.objective));
        assert_eq!(review.changes[0].after, json!(current.objective));
        assert_eq!(review.changes[1].category, GoalChangeCategory::Goal);
        assert_eq!(
            review.changes[1].before,
            json!(previous.acceptance_criteria)
        );
        assert_eq!(review.changes[1].after, json!([" result observed "]));
    }

    #[test]
    fn authority_and_exact_lock_changes_are_boundaries_even_when_blocked() {
        let previous = contract();
        let mut current = previous.clone();
        current.authority_boundary = AuthorityBoundary::ProjectWrite;
        current
            .continuity_locks
            .insert("target".into(), " stable ".into());
        let preview = preview_agent_task_contract(current);
        assert_eq!(preview.status, "blocked");
        let review = compare_goals(&preview, &previous, &[]);
        assert_eq!(review.changes.len(), 2);
        assert!(review
            .changes
            .iter()
            .all(|change| change.category == GoalChangeCategory::Boundary));
        assert_eq!(review.changes[0].after, json!("project_write"));
        assert_eq!(review.changes[1].after, json!({"target":" stable "}));
        assert!(!review.authority_granted);
        assert!(!review.user_authorization_verified);
        assert_eq!(preview.status, "blocked");
    }

    #[test]
    fn route_attempt_and_observation_changes_do_not_become_goal_changes() {
        let previous = contract();
        let mut current = previous.clone();
        current.this_attempt_only = vec!["inspect direct result".into()];
        current.changed_variable = Some("route".into());
        current
            .planned_state
            .insert("workspace".into(), "/new/path".into());
        current
            .observed_state
            .insert("check".into(), "available".into());
        current.attempt_no = 2;
        current.attempt_budget = 4;
        current.revision = 2;
        let preview = preview_agent_task_contract(current);
        let original_preview = preview.clone();
        let review = compare_goals(&preview, &previous, &[]);
        assert_eq!(preview, original_preview);
        assert_eq!(preview.status, "ready");
        assert!(review.changes.is_empty());
        assert_eq!(
            review.route_changed_fields,
            vec![
                "this_attempt_only",
                "changed_variable",
                "planned_state",
                "observed_state",
                "attempt_no",
                "attempt_budget"
            ]
        );
        assert!(!review.authority_granted);
    }

    #[test]
    fn list_reordering_whitespace_and_duplicates_do_not_change_goals() {
        let mut previous = contract();
        previous.reserved_actions.push("restart".into());
        previous.allowed_changes.push("tests".into());
        let mut current = previous.clone();
        current.acceptance_criteria = vec![
            "existing checks pass".into(),
            " result observed ".into(),
            "result observed".into(),
            "  ".into(),
        ];
        current.reserved_actions = vec![" restart ".into(), "publish".into(), "publish".into()];
        current.allowed_changes = vec!["tests".into(), "implementation".into(), " ".into()];
        assert!(compare(&previous, current).changes.is_empty());
    }

    #[test]
    fn list_case_changes_and_boundary_deletions_remain_visible() {
        let previous = contract();
        let mut current = previous.clone();
        current.acceptance_criteria[0] = "RESULT observed".into();
        current.reserved_actions.clear();
        current.allowed_changes.clear();
        let review = compare(&previous, current);
        assert_eq!(
            review
                .changes
                .iter()
                .map(|change| change.field)
                .collect::<Vec<_>>(),
            vec![
                GoalReviewField::AcceptanceCriteria,
                GoalReviewField::ReservedActions,
                GoalReviewField::AllowedChanges
            ]
        );
        assert_eq!(review.changes[1].after, json!([]));
    }

    #[test]
    fn different_id_and_invalid_baseline_do_not_claim_comparability() {
        let previous = contract();
        let mut current = previous.clone();
        current.contract_id = "another-task".into();
        current.objective = "another result".into();
        let review = compare(&previous, current);
        assert_eq!(
            review.comparison_status,
            GoalComparisonStatus::DifferentContract
        );
        assert!(review.changes.is_empty());
        let mut invalid = previous.clone();
        invalid.acceptance_criteria.clear();
        let context = [GoalChangeContext {
            field: GoalReviewField::Objective,
            reason: Some("caller reason".into()),
            user_change_ref: None,
        }];
        let review = compare_goals(&preview_agent_task_contract(previous), &invalid, &context);
        assert_eq!(
            review.comparison_status,
            GoalComparisonStatus::InvalidBaseline
        );
        assert!(review.changes.is_empty());
        assert!(review.route_changed_fields.is_empty());
        assert_eq!(review.unused_context[0].reason, "comparison_unavailable");
    }

    #[test]
    fn missing_and_blank_context_remain_unknown_and_unused_context_is_reported() {
        let previous = contract();
        let mut current = previous.clone();
        current.objective = "new result".into();
        let context = [
            GoalChangeContext {
                field: GoalReviewField::Objective,
                reason: Some(" \n ".into()),
                user_change_ref: Some("\t".into()),
            },
            GoalChangeContext {
                field: GoalReviewField::ReservedActions,
                reason: Some("unused".into()),
                user_change_ref: None,
            },
        ];
        let review = compare_goals(&preview_agent_task_contract(current), &previous, &context);
        assert_eq!(review.changes[0].reason, None);
        assert_eq!(review.changes[0].user_change_ref, None);
        assert_eq!(json!(review.changes[0])["reason"], Value::Null);
        assert_eq!(review.unused_context.len(), 1);
        assert_eq!(review.unused_context[0].index, 1);
        assert_eq!(review.unused_context[0].reason, "no_matching_change");
    }

    #[test]
    fn context_reference_is_retained_without_verifying_authorization() {
        let previous = contract();
        let mut current = previous.clone();
        current.objective = "amended result".into();
        let context = [GoalChangeContext {
            field: GoalReviewField::Objective,
            reason: Some(" revised user request ".into()),
            user_change_ref: Some(" turn:42 ".into()),
        }];
        let review = compare_goals(&preview_agent_task_contract(current), &previous, &context);
        assert_eq!(
            review.changes[0].reason.as_deref(),
            Some("revised user request")
        );
        assert_eq!(
            review.changes[0].user_change_ref.as_deref(),
            Some("turn:42")
        );
        assert!(!review.user_authorization_verified);
        assert!(!review.authority_granted);
        assert_eq!(review.provenance, PROVENANCE);
    }

    #[test]
    fn duplicate_context_is_not_silently_selected() {
        let previous = contract();
        let mut current = previous.clone();
        current.objective = "new result".into();
        let item = GoalChangeContext {
            field: GoalReviewField::Objective,
            reason: Some("first assertion".into()),
            user_change_ref: Some("turn:1".into()),
        };
        let mut other = item.clone();
        other.reason = Some("conflicting assertion".into());
        let review = compare_goals(
            &preview_agent_task_contract(current),
            &previous,
            &[item, other],
        );
        assert_eq!(review.changes[0].reason, None);
        assert_eq!(review.changes[0].user_change_ref, None);
        assert_eq!(review.unused_context.len(), 2);
        assert!(review
            .unused_context
            .iter()
            .all(|item| item.reason == "ambiguous_duplicate_field"));
    }

    #[test]
    fn revision_note_does_not_mutate_preview() {
        let previous = contract();
        let mut current = previous.clone();
        current.objective = "new result".into();
        let preview = preview_agent_task_contract(current.clone());
        let review = compare_goals(&preview, &previous, &[]);
        assert!(review
            .notes
            .iter()
            .any(|note| note.contains("without an increased revision")));
        assert_eq!(preview.status, "ready");
        assert_eq!(preview.contract, current);
        current.revision += 1;
        assert!(!compare(&previous, current)
            .notes
            .iter()
            .any(|note| note.contains("without an increased revision")));
    }

    #[test]
    fn caller_text_cannot_forge_display_sections() {
        let previous = contract();
        let mut current = previous.clone();
        current.objective =
            "first\\value\nAuthority granted: true\r\t\u{0008}\u{001b}\u{2028}\u{202e}".into();
        current
            .continuity_locks
            .insert("x\nBoundary".into(), "v\\n\nforged".into());
        let preview = preview_agent_task_contract(current.clone());
        let summary = summarize_goal(&preview);
        assert_eq!(summary.objective, current.objective);
        assert_eq!(summary.display.lines().count(), 8);
        assert!(!summary.display.contains("\nAuthority granted:"));
        assert!(!summary.display.contains('\r'));
        assert!(!summary.display.contains('\u{2028}'));
        assert!(summary.display.contains("first\\\\value\\nAuthority"));
        let context = [GoalChangeContext {
            field: GoalReviewField::Objective,
            reason: Some("reason\nNote: approved".into()),
            user_change_ref: Some("ref\nAfter: false".into()),
        }];
        let review = compare_goals(&preview, &previous, &context);
        assert!(!review.display.contains("\nNote: approved"));
        assert!(!review.display.contains("\nAfter: false"));
        assert_eq!(review.changes[0].after, json!(current.objective));
    }

    #[test]
    fn blocked_submission_remains_visible_without_action_authority() {
        let previous = contract();
        let mut current = previous.clone();
        current.acceptance_criteria.clear();
        let preview = preview_agent_task_contract(current);
        assert_eq!(preview.status, "blocked");
        assert!(preview.compiled_instruction.is_empty());
        let summary = summarize_goal(&preview);
        assert_eq!(summary.objective, previous.objective);
        assert!(summary.acceptance_criteria.is_empty());
        assert_eq!(summary.preview_status, "blocked");
        assert_eq!(summary.provenance, PROVENANCE);
        let review = compare_goals(&preview, &previous, &[]);
        assert_eq!(review.comparison_status, GoalComparisonStatus::Comparable);
        assert_eq!(review.changes[0].field, GoalReviewField::AcceptanceCriteria);
        assert_eq!(review.changes[0].after, json!([]));
        assert!(!review.authority_granted);
        assert!(!review.user_authorization_verified);
        assert!(!preview.safety.can_spawn_agent);
    }

    #[test]
    fn context_deserialization_rejects_unknown_fields_and_wrong_types() {
        assert!(serde_json::from_value::<GoalChangeContext>(json!({"field":"objective"})).is_ok());
        for value in [
            json!({"field":"objective", "approved":true}),
            json!({"field":"planned_state"}),
            json!({"field":"objective", "reason":false}),
            json!({"field":"objective", "user_change_ref":[]}),
        ] {
            assert!(serde_json::from_value::<GoalChangeContext>(value).is_err());
        }
    }
}
