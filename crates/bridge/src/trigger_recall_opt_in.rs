use serde_json::{json, Value};
use sha2::{Digest, Sha256};
use std::collections::BTreeSet;
use std::time::{SystemTime, UNIX_EPOCH};

pub const TRIGGER_RECALL_OPT_IN_STATUS_SCHEMA: &str =
    "agent_bridge.memory.trigger_recall.opt_in_status.v0";
pub const TRIGGER_RECALL_OPT_IN_RUNTIME_TRANSITION_GATE_SCHEMA: &str =
    "agent_bridge.memory.trigger_recall.opt_in_runtime_transition_gate.v0";
pub const TRIGGER_RECALL_OPT_IN_ENABLE_ENV: &str = "AB_TRIGGER_RECALL_OPT_IN";
pub const TRIGGER_RECALL_DISABLE_ENV: &str = "AB_TRIGGER_RECALL_DISABLE";
pub const TRIGGER_RECALL_BASELINE_ACCEPTANCE_REGRESSION_ANCHOR: &str =
    "aio2_trigger_recall_baseline_acceptance_shadow_20260623";
pub const TRIGGER_RECALL_UNION_CONT_REGRESSION_ANCHOR: &str =
    "aio2_trigger_recall_union_cont_20260623";

#[derive(Debug, Clone, Default)]
pub struct TriggerRecallOptInStatusOptions {
    pub mode: String,
    pub per_call_opt_in: bool,
    pub scope: Option<String>,
    pub scope_mode: String,
    pub regression_anchor: Option<String>,
    pub aio2_corpus_ready: Option<bool>,
    pub union_cont_misses: Option<u64>,
    pub union_cont_false_hits: Option<u64>,
    pub baseline_shadow_true_hits_lost: Option<u64>,
    pub baseline_shadow_positive_cases_held: Option<u64>,
    pub baseline_shadow_false_hits_after_gate: Option<u64>,
    pub metric_captured_at: Option<String>,
    pub runtime_enabled: bool,
    pub operator_disabled: bool,
    pub raw_payload_fields_present: bool,
}

#[derive(Debug, Clone, Default)]
pub struct TriggerRecallOptInRuntimeTransitionGateOptions {
    pub status_packet: Value,
    pub mode: String,
    pub per_call_opt_in: bool,
    pub scope: Option<String>,
    pub scope_mode: String,
    pub regression_anchor: Option<String>,
    pub runtime_enabled: bool,
    pub operator_disabled: bool,
    pub reviewer: Option<String>,
    pub commit: Option<String>,
    pub forum_post_id: Option<String>,
    pub memory_key: Option<String>,
    pub raw_payload_fields_present: bool,
}

fn unix_now_secs() -> i64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap_or_default()
        .as_secs() as i64
}

fn sha256_hex(input: &str) -> String {
    let mut hasher = Sha256::new();
    hasher.update(input.as_bytes());
    format!("sha256:{:x}", hasher.finalize())
}

fn normalize_mode(mode: &str) -> String {
    let mode = mode.trim();
    if mode.is_empty() {
        "fts".to_string()
    } else {
        mode.to_ascii_lowercase()
    }
}

fn normalize_scope_mode(scope_mode: &str) -> String {
    let scope_mode = scope_mode.trim();
    if scope_mode.is_empty() {
        "local_only".to_string()
    } else {
        scope_mode.to_ascii_lowercase()
    }
}

fn normalized_scope(scope: Option<String>) -> Option<String> {
    scope
        .map(|value| value.trim().to_string())
        .filter(|value| !value.is_empty())
}

fn exact_local_project_scope(scope: Option<&str>, scope_mode: &str) -> bool {
    scope_mode == "local_only"
        && scope
            .and_then(|value| value.strip_prefix("project:"))
            .map(str::trim)
            .map(|value| value.starts_with('/') && value.len() > 1)
            .unwrap_or(false)
}

fn metric_value(value: Option<u64>) -> Value {
    value.map(Value::from).unwrap_or(Value::Null)
}

fn bool_metric_value(value: Option<bool>) -> Value {
    value.map(Value::from).unwrap_or(Value::Null)
}

fn push_if(reasons: &mut BTreeSet<String>, condition: bool, reason: &str) {
    if condition {
        reasons.insert(reason.to_string());
    }
}

pub fn trigger_recall_value_contains_raw(value: &Value) -> bool {
    fn key_is_raw(key: &str) -> bool {
        matches!(
            key,
            "query"
                | "raw_query"
                | "raw_queries"
                | "raw_key"
                | "raw_keys"
                | "baseline_keys"
                | "candidate_keys"
                | "memory_keys"
                | "content"
                | "raw_content"
                | "memory_content"
                | "candidate_content"
                | "case_rows"
        )
    }

    match value {
        Value::Object(map) => map
            .iter()
            .any(|(key, value)| key_is_raw(key) || trigger_recall_value_contains_raw(value)),
        Value::Array(values) => values.iter().any(trigger_recall_value_contains_raw),
        _ => false,
    }
}

pub fn trigger_recall_opt_in_status(options: TriggerRecallOptInStatusOptions) -> Value {
    let mode = normalize_mode(&options.mode);
    let scope_mode = normalize_scope_mode(&options.scope_mode);
    let scope = normalized_scope(options.scope);
    let exact_scope = exact_local_project_scope(scope.as_deref(), &scope_mode);
    let regression_anchor = options.regression_anchor.unwrap_or_default();
    let anchor_ok = regression_anchor == TRIGGER_RECALL_BASELINE_ACCEPTANCE_REGRESSION_ANCHOR;
    let metrics_complete = options.aio2_corpus_ready.is_some()
        && [
            options.union_cont_misses,
            options.union_cont_false_hits,
            options.baseline_shadow_true_hits_lost,
            options.baseline_shadow_positive_cases_held,
            options.baseline_shadow_false_hits_after_gate,
        ]
        .iter()
        .all(Option::is_some);

    let mut eval_blockers = BTreeSet::<String>::new();
    push_if(&mut eval_blockers, !anchor_ok, "regression_anchor_mismatch");
    push_if(&mut eval_blockers, !metrics_complete, "eval_metrics_absent");
    push_if(
        &mut eval_blockers,
        options.aio2_corpus_ready != Some(true),
        "aio2_corpus_not_ready",
    );
    push_if(
        &mut eval_blockers,
        options.union_cont_misses.unwrap_or(1) > 0,
        "union_cont_misses_present",
    );
    push_if(
        &mut eval_blockers,
        options.union_cont_false_hits.unwrap_or(1) > 0,
        "union_cont_false_hits_present",
    );
    push_if(
        &mut eval_blockers,
        options.baseline_shadow_true_hits_lost.unwrap_or(1) > 0,
        "baseline_shadow_true_hits_lost",
    );
    push_if(
        &mut eval_blockers,
        options.baseline_shadow_positive_cases_held.unwrap_or(1) > 0,
        "baseline_shadow_positive_cases_held",
    );
    push_if(
        &mut eval_blockers,
        options.baseline_shadow_false_hits_after_gate.unwrap_or(1) > 0,
        "baseline_shadow_false_hits_after_gate_present",
    );
    let eval_passed = eval_blockers.is_empty();

    let mut blockers = BTreeSet::<String>::new();
    push_if(
        &mut blockers,
        mode != "fts",
        "requested_mode_not_authorized",
    );
    push_if(
        &mut blockers,
        !options.per_call_opt_in,
        "per_call_opt_in_missing",
    );
    push_if(
        &mut blockers,
        !exact_scope,
        "exact_local_project_scope_missing",
    );
    push_if(&mut blockers, !options.runtime_enabled, "runtime_disabled");
    push_if(
        &mut blockers,
        options.operator_disabled,
        "operator_disabled",
    );
    push_if(
        &mut blockers,
        options.raw_payload_fields_present,
        "raw_payload_fields_present",
    );
    blockers.extend(eval_blockers.iter().cloned());

    let ready = blockers.is_empty();
    let status = if ready {
        "ready_for_transition_gate"
    } else if options.operator_disabled {
        "operator_disabled"
    } else if !options.runtime_enabled {
        "runtime_disabled"
    } else {
        "blocked"
    };

    json!({
        "schema": TRIGGER_RECALL_OPT_IN_STATUS_SCHEMA,
        "generated_at": unix_now_secs(),
        "read_only": true,
        "control_surface": "trigger_recall_opt_in_status",
        "status": status,
        "runtime_gate": {
            "runtime_enable_env": TRIGGER_RECALL_OPT_IN_ENABLE_ENV,
            "runtime_enabled": options.runtime_enabled,
            "operator_disable_env": TRIGGER_RECALL_DISABLE_ENV,
            "operator_disabled": options.operator_disabled,
            "feature_flag_default_off": true
        },
        "requested_transition": {
            "mode": mode,
            "mode_authorized": mode == "fts",
            "per_call_opt_in": options.per_call_opt_in,
            "scope_present": scope.is_some(),
            "scope_hash": scope.as_ref().map(|value| sha256_hex(value)),
            "scope_mode": scope_mode,
            "exact_local_project_scope": exact_scope,
            "default_memory_search_unchanged": true
        },
        "eval_metrics": {
            "regression_anchor": if regression_anchor.is_empty() { Value::Null } else { json!(regression_anchor) },
            "required_regression_anchor": TRIGGER_RECALL_BASELINE_ACCEPTANCE_REGRESSION_ANCHOR,
            "union_cont_regression_anchor": TRIGGER_RECALL_UNION_CONT_REGRESSION_ANCHOR,
            "regression_anchor_matches": anchor_ok,
            "metric_captured_at": options.metric_captured_at.unwrap_or_default(),
            "complete": metrics_complete,
            "passed": eval_passed,
            "aio2_corpus_ready": bool_metric_value(options.aio2_corpus_ready),
            "union_cont_misses": metric_value(options.union_cont_misses),
            "union_cont_false_hits": metric_value(options.union_cont_false_hits),
            "baseline_shadow_true_hits_lost": metric_value(options.baseline_shadow_true_hits_lost),
            "baseline_shadow_positive_cases_held": metric_value(options.baseline_shadow_positive_cases_held),
            "baseline_shadow_false_hits_after_gate": metric_value(options.baseline_shadow_false_hits_after_gate),
            "blockers": eval_blockers.into_iter().collect::<Vec<_>>()
        },
        "audit_shape": {
            "schema_if_trial_later": "agent_bridge.memory.trigger_recall.opt_in_baseline_trial.v0",
            "query_hash_required": true,
            "baseline_order_hash_required": true,
            "raw_query_included": false,
            "raw_keys_included": false,
            "content_included": false,
            "held_queries_use_status_not_empty_array": true,
            "default_memory_search_unchanged": true
        },
        "boundary_check": {
            "ready_for_transition_gate": ready,
            "blockers": blockers.into_iter().collect::<Vec<_>>()
        },
        "side_effects": {
            "calls_memory_search": false,
            "calls_memory_neighbors": false,
            "records_coactivation": false,
            "writes_memory": false,
            "writes_graph_edges": false,
            "changes_memory_search_order": false,
            "changes_default_memory_search_schema": false,
            "may_run_gated_baseline_trial_now": false,
            "may_enforce_hold_now": false
        },
        "input_contract": {
            "raw_payload_fields_present": options.raw_payload_fields_present,
            "raw_query_included": false,
            "raw_keys_included": false,
            "content_included": false,
            "unknown_fields_ignored": true
        }
    })
}

pub fn trigger_recall_opt_in_runtime_transition_gate(
    options: TriggerRecallOptInRuntimeTransitionGateOptions,
) -> Value {
    let mode = normalize_mode(&options.mode);
    let scope_mode = normalize_scope_mode(&options.scope_mode);
    let scope = normalized_scope(options.scope);
    let exact_scope = exact_local_project_scope(scope.as_deref(), &scope_mode);
    let regression_anchor = options.regression_anchor.unwrap_or_default();
    let anchor_ok = regression_anchor == TRIGGER_RECALL_BASELINE_ACCEPTANCE_REGRESSION_ANCHOR;
    let status_schema = options
        .status_packet
        .get("schema")
        .and_then(Value::as_str)
        .unwrap_or("");
    let status_read_only = options
        .status_packet
        .get("read_only")
        .and_then(Value::as_bool)
        .unwrap_or(false);
    let source_ready = options
        .status_packet
        .pointer("/boundary_check/ready_for_transition_gate")
        .and_then(Value::as_bool)
        .unwrap_or(false);
    let source_status = options
        .status_packet
        .get("status")
        .and_then(Value::as_str)
        .unwrap_or("missing");
    let source_eval_complete = options
        .status_packet
        .pointer("/eval_metrics/complete")
        .and_then(Value::as_bool)
        .unwrap_or(false);
    let source_eval_passed = options
        .status_packet
        .pointer("/eval_metrics/passed")
        .and_then(Value::as_bool)
        .unwrap_or(false);
    let source_contains_raw = trigger_recall_value_contains_raw(&options.status_packet);
    let source_side_effects_safe = options
        .status_packet
        .pointer("/side_effects/calls_memory_search")
        .and_then(Value::as_bool)
        == Some(false)
        && options
            .status_packet
            .pointer("/side_effects/changes_memory_search_order")
            .and_then(Value::as_bool)
            == Some(false)
        && options
            .status_packet
            .pointer("/side_effects/changes_default_memory_search_schema")
            .and_then(Value::as_bool)
            == Some(false)
        && options
            .status_packet
            .pointer("/side_effects/may_enforce_hold_now")
            .and_then(Value::as_bool)
            == Some(false);

    let mut blockers = BTreeSet::<String>::new();
    push_if(
        &mut blockers,
        status_schema != TRIGGER_RECALL_OPT_IN_STATUS_SCHEMA,
        "status_packet_schema_mismatch",
    );
    push_if(
        &mut blockers,
        !status_read_only,
        "status_packet_not_read_only",
    );
    push_if(
        &mut blockers,
        source_contains_raw,
        "status_packet_contains_raw_payload",
    );
    push_if(
        &mut blockers,
        !source_ready,
        "status_packet_not_ready_for_transition_gate",
    );
    push_if(
        &mut blockers,
        !source_side_effects_safe,
        "status_packet_side_effect_contract_invalid",
    );
    push_if(&mut blockers, !source_eval_complete, "eval_metrics_absent");
    push_if(&mut blockers, !source_eval_passed, "eval_metrics_failed");
    push_if(
        &mut blockers,
        mode != "fts",
        "requested_mode_not_authorized",
    );
    push_if(
        &mut blockers,
        !options.per_call_opt_in,
        "per_call_opt_in_missing",
    );
    push_if(
        &mut blockers,
        !exact_scope,
        "exact_local_project_scope_missing",
    );
    push_if(&mut blockers, !options.runtime_enabled, "runtime_disabled");
    push_if(
        &mut blockers,
        options.operator_disabled,
        "operator_disabled",
    );
    push_if(&mut blockers, !anchor_ok, "regression_anchor_mismatch");
    push_if(
        &mut blockers,
        options.raw_payload_fields_present,
        "raw_payload_fields_present",
    );
    if let Some(source_blockers) = options
        .status_packet
        .pointer("/boundary_check/blockers")
        .and_then(Value::as_array)
    {
        for blocker in source_blockers {
            if let Some(blocker) = blocker.as_str() {
                blockers.insert(format!("status_{blocker}"));
            }
        }
    }

    let allowed = blockers.is_empty();
    json!({
        "schema": TRIGGER_RECALL_OPT_IN_RUNTIME_TRANSITION_GATE_SCHEMA,
        "generated_at": unix_now_secs(),
        "read_only": true,
        "runtime_transition_gate": true,
        "implementation_stage": "trigger_recall_opt_in_readonly_transition_gate",
        "status": if allowed { "transition_allowed" } else { "blocked" },
        "source_status": {
            "schema": status_schema,
            "status": source_status,
            "read_only": status_read_only,
            "ready_for_transition_gate": source_ready,
            "eval_metrics_complete": source_eval_complete,
            "eval_metrics_passed": source_eval_passed,
            "side_effect_contract_safe": source_side_effects_safe,
            "status_packet_included": false,
            "raw_payload_fields_present": source_contains_raw
        },
        "requested_transition": {
            "mode": mode,
            "mode_authorized": mode == "fts",
            "per_call_opt_in": options.per_call_opt_in,
            "scope_present": scope.is_some(),
            "scope_hash": scope.as_ref().map(|value| sha256_hex(value)),
            "scope_mode": scope_mode,
            "exact_local_project_scope": exact_scope,
            "regression_anchor_matches": anchor_ok,
            "operator_disabled": options.operator_disabled,
            "runtime_enabled": options.runtime_enabled
        },
        "transition": {
            "transition_allowed": allowed,
            "may_call_gated_baseline_trial": allowed,
            "may_enforce_hold": false,
            "next_allowed_surface": if allowed { "trigger_recall_opt_in_gated_baseline_trial" } else { "none" },
            "default_memory_search_unchanged": true
        },
        "boundary_check": {
            "runtime_transition_allowed": allowed,
            "blockers": blockers.into_iter().collect::<Vec<_>>()
        },
        "review_refs": {
            "reviewer_present": options.reviewer.as_ref().map(|value| !value.trim().is_empty()).unwrap_or(false),
            "commit_present": options.commit.as_ref().map(|value| !value.trim().is_empty()).unwrap_or(false),
            "forum_post_id_present": options.forum_post_id.as_ref().map(|value| !value.trim().is_empty()).unwrap_or(false),
            "memory_key_present": options.memory_key.as_ref().map(|value| !value.trim().is_empty()).unwrap_or(false)
        },
        "input_contract": {
            "status_packet_included": false,
            "raw_payload_fields_present": options.raw_payload_fields_present,
            "raw_query_included": false,
            "raw_keys_included": false,
            "content_included": false,
            "unknown_fields_ignored": true
        },
        "side_effects": {
            "calls_memory_search": false,
            "calls_memory_neighbors": false,
            "records_coactivation": false,
            "writes_memory": false,
            "writes_graph_edges": false,
            "writes_approval": false,
            "changes_memory_search_order": false,
            "changes_default_memory_search_schema": false,
            "runs_semantic_retrieval": false,
            "runs_graph_retrieval": false
        }
    })
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn status_ready_path_stays_readonly() {
        let status = trigger_recall_opt_in_status(TriggerRecallOptInStatusOptions {
            mode: "fts".to_string(),
            per_call_opt_in: true,
            scope: Some("project:/Data/CascadeProjects/agent-bridge".to_string()),
            scope_mode: "local_only".to_string(),
            regression_anchor: Some(
                TRIGGER_RECALL_BASELINE_ACCEPTANCE_REGRESSION_ANCHOR.to_string(),
            ),
            aio2_corpus_ready: Some(true),
            union_cont_misses: Some(0),
            union_cont_false_hits: Some(0),
            baseline_shadow_true_hits_lost: Some(0),
            baseline_shadow_positive_cases_held: Some(0),
            baseline_shadow_false_hits_after_gate: Some(0),
            runtime_enabled: true,
            ..Default::default()
        });
        assert_eq!(status["status"], json!("ready_for_transition_gate"));
        assert_eq!(status["side_effects"]["calls_memory_search"], json!(false));
        assert_eq!(status["side_effects"]["may_enforce_hold_now"], json!(false));
    }

    #[test]
    fn transition_gate_blocks_raw_packet_without_echoing() {
        let mut status = trigger_recall_opt_in_status(TriggerRecallOptInStatusOptions {
            mode: "fts".to_string(),
            per_call_opt_in: true,
            scope: Some("project:/Data/CascadeProjects/agent-bridge".to_string()),
            scope_mode: "local_only".to_string(),
            regression_anchor: Some(
                TRIGGER_RECALL_BASELINE_ACCEPTANCE_REGRESSION_ANCHOR.to_string(),
            ),
            aio2_corpus_ready: Some(true),
            union_cont_misses: Some(0),
            union_cont_false_hits: Some(0),
            baseline_shadow_true_hits_lost: Some(0),
            baseline_shadow_positive_cases_held: Some(0),
            baseline_shadow_false_hits_after_gate: Some(0),
            runtime_enabled: true,
            ..Default::default()
        });
        status["raw_query"] = json!("secret trigger query");
        let gate = trigger_recall_opt_in_runtime_transition_gate(
            TriggerRecallOptInRuntimeTransitionGateOptions {
                status_packet: status,
                mode: "fts".to_string(),
                per_call_opt_in: true,
                scope: Some("project:/Data/CascadeProjects/agent-bridge".to_string()),
                scope_mode: "local_only".to_string(),
                regression_anchor: Some(
                    TRIGGER_RECALL_BASELINE_ACCEPTANCE_REGRESSION_ANCHOR.to_string(),
                ),
                runtime_enabled: true,
                ..Default::default()
            },
        );
        let serialized = serde_json::to_string(&gate).expect("serialize");
        assert!(!serialized.contains("secret trigger query"));
        let blockers = gate["boundary_check"]["blockers"]
            .as_array()
            .expect("blockers");
        assert!(blockers.contains(&json!("status_packet_contains_raw_payload")));
        assert_eq!(gate["transition"]["transition_allowed"], json!(false));
    }
}
