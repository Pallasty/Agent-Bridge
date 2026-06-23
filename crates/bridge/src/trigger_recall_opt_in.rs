use serde_json::{Value, json};
use sha2::{Digest, Sha256};
use std::collections::BTreeSet;
use std::time::{SystemTime, UNIX_EPOCH};

pub const TRIGGER_RECALL_OPT_IN_STATUS_SCHEMA: &str =
    "agent_bridge.memory.trigger_recall.opt_in_status.v0";
pub const TRIGGER_RECALL_OPT_IN_RUNTIME_TRANSITION_GATE_SCHEMA: &str =
    "agent_bridge.memory.trigger_recall.opt_in_runtime_transition_gate.v0";
pub const TRIGGER_RECALL_OPT_IN_BASELINE_TRIAL_SCHEMA: &str =
    "agent_bridge.memory.trigger_recall.opt_in_baseline_trial.v0";
pub const TRIGGER_RECALL_OPT_IN_GATED_BATCH_DIAGNOSTICS_SCHEMA: &str =
    "agent_bridge.memory.trigger_recall.opt_in_gated_batch_diagnostics.v0";
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

#[derive(Debug, Clone, Default)]
pub struct TriggerRecallOptInGatedBaselineTrialHit {
    pub key: String,
    pub kind: String,
    pub score: f64,
    pub scope: Option<String>,
    pub created_at: i64,
    pub updated_at: i64,
    pub tags_count: usize,
}

#[derive(Debug, Clone, Default)]
pub struct TriggerRecallOptInGatedBaselineTrialOptions {
    pub runtime_transition_gate: Value,
    pub query: String,
    pub tags_count: usize,
    pub limit: u64,
    pub mode: String,
    pub per_call_opt_in: bool,
    pub scope: Option<String>,
    pub scope_mode: String,
    pub runtime_enabled: bool,
    pub operator_disabled: bool,
    pub raw_payload_fields_present: bool,
    pub baseline_search_called: bool,
    pub baseline_hits: Option<Vec<TriggerRecallOptInGatedBaselineTrialHit>>,
    pub baseline_search_error: Option<String>,
    pub attempt_id: Option<String>,
    pub commit: Option<String>,
}

#[derive(Debug, Clone, Default)]
pub struct TriggerRecallOptInGatedBatchDiagnosticsPacket {
    pub trial_packet: Value,
    pub case_id: Option<String>,
    pub expected_status: Option<String>,
    pub expected_visible_behavior: Option<String>,
    pub raw_payload_fields_present: bool,
}

#[derive(Debug, Clone, Default)]
pub struct TriggerRecallOptInGatedBatchDiagnosticsOptions {
    pub packets: Vec<TriggerRecallOptInGatedBatchDiagnosticsPacket>,
    pub attempt_id: Option<String>,
    pub reviewer: Option<String>,
    pub commit: Option<String>,
    pub forum_post_id: Option<String>,
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

fn contains_any(haystack: &str, needles: &[&str]) -> bool {
    needles.iter().any(|needle| haystack.contains(needle))
}

pub fn trigger_recall_baseline_acceptance_reject_reason(query: &str) -> Option<&'static str> {
    let lower = query.to_lowercase();
    let has_bypass = contains_any(&lower, &["bypass", "绕过"]);
    let has_direct_write = contains_any(
        &lower,
        &[
            "directly write",
            "write graph edges",
            "write memory_edges",
            "直接写",
        ],
    );
    let has_graph_write_surface = contains_any(
        &lower,
        &[
            "graph edges",
            "memory_edges",
            "related keys",
            "materialize",
            "materialization",
            "dry run",
            "dry_run",
            "图谱",
        ],
    );

    if (has_bypass || has_direct_write) && has_graph_write_surface {
        return Some("write_bypass_intent");
    }

    if contains_any(
        &lower,
        &["write a poem", "poem", "poetry", "写诗", "诗歌", "写一首诗"],
    ) {
        return Some("creative_non_continuation_intent");
    }

    let has_dashboard_or_state = contains_any(&lower, &["dashboard", "state"]);
    if !has_dashboard_or_state {
        return None;
    }

    if contains_any(
        &lower,
        &[
            "exercise", "recovery", "pain", "tracker", "workout", "health", "fitness",
        ],
    ) {
        return Some("health_dashboard_intent");
    }

    if contains_any(
        &lower,
        &[
            "card spacing",
            "color palette",
            "button hover",
            "responsive layout",
            "visual design",
            "visual-design",
            "styling",
            "layout",
            "frontend",
        ],
    ) {
        return Some("frontend_dashboard_intent");
    }

    None
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

fn bool_false_at(value: &Value, pointer: &str) -> bool {
    value.pointer(pointer).and_then(Value::as_bool) == Some(false)
}

fn string_at<'a>(value: &'a Value, pointer: &str) -> &'a str {
    value.pointer(pointer).and_then(Value::as_str).unwrap_or("")
}

fn u64_at(value: &Value, pointer: &str) -> u64 {
    value.pointer(pointer).and_then(Value::as_u64).unwrap_or(0)
}

fn redacted_external_hash(value: Option<&str>) -> Option<String> {
    value
        .map(str::trim)
        .filter(|value| !value.is_empty())
        .map(|value| {
            if value.starts_with("sha256:") && value.len() >= 24 {
                value.to_string()
            } else {
                sha256_hex(value)
            }
        })
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

fn transition_gate_blockers(
    gate: &Value,
    mode: &str,
    per_call_opt_in: bool,
    exact_scope: bool,
    runtime_enabled: bool,
    operator_disabled: bool,
    raw_payload_fields_present: bool,
    query_present: bool,
) -> BTreeSet<String> {
    let gate_schema = gate.get("schema").and_then(Value::as_str).unwrap_or("");
    let gate_read_only = gate
        .get("read_only")
        .and_then(Value::as_bool)
        .unwrap_or(false);
    let gate_marker = gate
        .get("runtime_transition_gate")
        .and_then(Value::as_bool)
        .unwrap_or(false);
    let gate_status = gate.get("status").and_then(Value::as_str).unwrap_or("");
    let gate_transition_allowed = gate
        .pointer("/transition/transition_allowed")
        .and_then(Value::as_bool)
        .unwrap_or(false);
    let gate_may_call_trial = gate
        .pointer("/transition/may_call_gated_baseline_trial")
        .and_then(Value::as_bool)
        .unwrap_or(false);
    let gate_may_enforce_hold = gate
        .pointer("/transition/may_enforce_hold")
        .and_then(Value::as_bool)
        .unwrap_or(false);
    let gate_boundary_allowed = gate
        .pointer("/boundary_check/runtime_transition_allowed")
        .and_then(Value::as_bool)
        .unwrap_or(false);
    let gate_contains_raw = trigger_recall_value_contains_raw(gate);
    let gate_side_effects_safe = gate
        .pointer("/side_effects/calls_memory_search")
        .and_then(Value::as_bool)
        == Some(false)
        && gate
            .pointer("/side_effects/changes_memory_search_order")
            .and_then(Value::as_bool)
            == Some(false)
        && gate
            .pointer("/side_effects/changes_default_memory_search_schema")
            .and_then(Value::as_bool)
            == Some(false)
        && gate
            .pointer("/side_effects/writes_memory")
            .and_then(Value::as_bool)
            == Some(false);

    let mut blockers = BTreeSet::<String>::new();
    push_if(
        &mut blockers,
        gate_schema != TRIGGER_RECALL_OPT_IN_RUNTIME_TRANSITION_GATE_SCHEMA,
        "transition_gate_schema_mismatch",
    );
    push_if(
        &mut blockers,
        !gate_read_only,
        "transition_gate_not_read_only",
    );
    push_if(
        &mut blockers,
        !gate_marker,
        "transition_gate_marker_missing",
    );
    push_if(
        &mut blockers,
        gate_status != "transition_allowed",
        "transition_gate_status_not_allowed",
    );
    push_if(
        &mut blockers,
        !gate_transition_allowed,
        "transition_gate_transition_not_allowed",
    );
    push_if(
        &mut blockers,
        !gate_may_call_trial,
        "transition_gate_may_not_call_baseline_trial",
    );
    push_if(
        &mut blockers,
        gate_may_enforce_hold,
        "transition_gate_may_enforce_hold",
    );
    push_if(
        &mut blockers,
        !gate_boundary_allowed,
        "transition_gate_boundary_not_allowed",
    );
    push_if(
        &mut blockers,
        gate_contains_raw,
        "transition_gate_contains_raw_payload",
    );
    push_if(
        &mut blockers,
        !gate_side_effects_safe,
        "transition_gate_side_effect_contract_invalid",
    );
    if let Some(source_blockers) = gate
        .pointer("/boundary_check/blockers")
        .and_then(Value::as_array)
    {
        for blocker in source_blockers {
            if let Some(blocker) = blocker.as_str() {
                blockers.insert(format!("transition_gate_{blocker}"));
            }
        }
    }

    push_if(
        &mut blockers,
        mode != "fts",
        "requested_mode_not_authorized",
    );
    push_if(&mut blockers, !per_call_opt_in, "per_call_opt_in_missing");
    push_if(
        &mut blockers,
        !exact_scope,
        "exact_local_project_scope_missing",
    );
    push_if(&mut blockers, !runtime_enabled, "runtime_disabled");
    push_if(&mut blockers, operator_disabled, "operator_disabled");
    push_if(
        &mut blockers,
        raw_payload_fields_present,
        "raw_payload_fields_present",
    );
    push_if(&mut blockers, !query_present, "query_missing");

    blockers
}

fn baseline_order_hash(hits: &[TriggerRecallOptInGatedBaselineTrialHit]) -> String {
    let joined = hits
        .iter()
        .map(|hit| hit.key.as_str())
        .collect::<Vec<_>>()
        .join("\n");
    sha256_hex(&joined)
}

fn redacted_hit_summary(hit: &TriggerRecallOptInGatedBaselineTrialHit, rank: usize) -> Value {
    json!({
        "rank": rank,
        "key_hash": sha256_hex(&hit.key),
        "kind": hit.kind,
        "score": hit.score,
        "scope_present": hit.scope.is_some(),
        "scope_hash": hit.scope.as_ref().map(|scope| sha256_hex(scope)),
        "created_at": hit.created_at,
        "updated_at": hit.updated_at,
        "tags_count": hit.tags_count
    })
}

pub fn trigger_recall_opt_in_gated_baseline_trial(
    options: TriggerRecallOptInGatedBaselineTrialOptions,
) -> Value {
    let mode = normalize_mode(&options.mode);
    let scope_mode = normalize_scope_mode(&options.scope_mode);
    let scope = normalized_scope(options.scope);
    let exact_scope = exact_local_project_scope(scope.as_deref(), &scope_mode);
    let query = options.query.trim().to_string();
    let query_present = !query.is_empty();
    let blockers = transition_gate_blockers(
        &options.runtime_transition_gate,
        &mode,
        options.per_call_opt_in,
        exact_scope,
        options.runtime_enabled,
        options.operator_disabled,
        options.raw_payload_fields_present,
        query_present,
    );
    let transition_allowed = blockers.is_empty();
    let reject_reason = if transition_allowed {
        trigger_recall_baseline_acceptance_reject_reason(&query)
    } else {
        None
    };

    let baseline_search_supplied = options.baseline_hits.is_some();
    let baseline_hits = options.baseline_hits.unwrap_or_default();
    let baseline_count_before = baseline_hits.len();
    let baseline_result_available = options.baseline_search_called
        || baseline_search_supplied
        || options.baseline_search_error.is_some();
    let accepted = transition_allowed
        && baseline_result_available
        && reject_reason.is_none()
        && options.baseline_search_error.is_none();
    let held = transition_allowed
        && baseline_result_available
        && reject_reason.is_some()
        && options.baseline_search_error.is_none();
    let visible_hits = if accepted {
        baseline_hits
            .iter()
            .enumerate()
            .map(|(idx, hit)| redacted_hit_summary(hit, idx + 1))
            .collect::<Vec<_>>()
    } else {
        Vec::new()
    };
    let baseline_count_after = if accepted { baseline_count_before } else { 0 };
    let status = if !transition_allowed {
        "transition_gate_blocked"
    } else if options.baseline_search_error.is_some() {
        "baseline_search_error"
    } else if held {
        "held_by_query_intent"
    } else if accepted {
        "returned_accepted"
    } else {
        "baseline_search_pending"
    };
    let visible_behavior = if !transition_allowed {
        "transition_gate_blocked"
    } else if options.baseline_search_error.is_some() {
        "baseline_search_error"
    } else if held {
        "held_by_query_intent"
    } else if accepted {
        "baseline_fts_visible"
    } else {
        "baseline_search_pending"
    };
    let calls_memory_search =
        transition_allowed && (options.baseline_search_called || baseline_search_supplied);
    let query_intent_decision = if accepted {
        "allow"
    } else if held {
        "hold"
    } else {
        "not_evaluated"
    };

    json!({
        "schema": TRIGGER_RECALL_OPT_IN_BASELINE_TRIAL_SCHEMA,
        "generated_at": unix_now_secs(),
        "read_only": true,
        "status": status,
        "mode": mode,
        "per_call_opt_in": options.per_call_opt_in,
        "default_memory_search_unchanged": true,
        "runtime_transition_preflight": {
            "transition_gate_allowed": transition_allowed,
            "transition_gate_included": false,
            "blockers": blockers.into_iter().collect::<Vec<_>>()
        },
        "request": {
            "query_hash": if query_present { json!(sha256_hex(&query)) } else { Value::Null },
            "raw_query_included": false,
            "tags_count": options.tags_count,
            "limit": options.limit,
            "scope_present": scope.is_some(),
            "scope_hash": scope.as_ref().map(|value| sha256_hex(value)),
            "scope_mode": scope_mode,
            "exact_local_project_scope": exact_scope,
            "attempt_id_hash": options.attempt_id.as_ref().map(|value| sha256_hex(value)),
            "commit": options.commit.unwrap_or_default()
        },
        "baseline": {
            "memory_search_called": calls_memory_search,
            "baseline_candidate_count_before_gate": baseline_count_before,
            "baseline_candidate_count_after_gate": baseline_count_after,
            "baseline_order_hash_before_gate": if calls_memory_search { json!(baseline_order_hash(&baseline_hits)) } else { Value::Null },
            "baseline_search_error": options.baseline_search_error.as_deref().unwrap_or("")
        },
        "query_intent": {
            "decision": query_intent_decision,
            "reject_reason": reject_reason
        },
        "visible_behavior": visible_behavior,
        "fallback_behavior": if held { "hold_packet_not_empty_search" } else if accepted { "baseline_fts_visible" } else { "no_trial_result" },
        "visible_hits": visible_hits,
        "audit": {
            "regression_anchor": TRIGGER_RECALL_BASELINE_ACCEPTANCE_REGRESSION_ANCHOR,
            "query_hash_required": true,
            "baseline_order_hash_required": calls_memory_search,
            "raw_query_included": false,
            "raw_keys_included": false,
            "content_included": false,
            "held_queries_use_status_not_empty_array": true
        },
        "side_effects": {
            "calls_memory_search": calls_memory_search,
            "calls_memory_neighbors": false,
            "records_coactivation": false,
            "writes_memory": false,
            "writes_graph_edges": false,
            "changes_memory_search_order": false,
            "changes_default_memory_search_schema": false,
            "changes_production_retrieval_default": false,
            "runs_semantic_retrieval": false,
            "runs_graph_retrieval": false
        },
        "input_contract": {
            "runtime_transition_gate_included": false,
            "raw_payload_fields_present": options.raw_payload_fields_present,
            "raw_query_included": false,
            "raw_keys_included": false,
            "content_included": false,
            "unknown_fields_ignored": true
        }
    })
}

pub fn trigger_recall_opt_in_gated_batch_diagnostics(
    options: TriggerRecallOptInGatedBatchDiagnosticsOptions,
) -> Value {
    let outer_raw = options.raw_payload_fields_present;
    let mut packet_results = Vec::with_capacity(options.packets.len());
    let mut returned_accepted_count = 0u64;
    let mut held_by_query_intent_count = 0u64;
    let mut transition_gate_blocked_count = 0u64;
    let mut baseline_search_error_count = 0u64;
    let mut baseline_search_pending_count = 0u64;
    let mut other_status_count = 0u64;
    let mut raw_payload_blocked_count = 0u64;
    let mut expectation_mismatch_count = 0u64;
    let mut trial_memory_search_called_count = 0u64;
    let mut baseline_count_before_total = 0u64;
    let mut baseline_count_after_total = 0u64;
    let mut baseline_order_hash_count = 0u64;

    for (index, packet) in options.packets.iter().enumerate() {
        let trial_packet = &packet.trial_packet;
        let schema = trial_packet
            .get("schema")
            .and_then(Value::as_str)
            .unwrap_or("");
        let read_only = trial_packet
            .get("read_only")
            .and_then(Value::as_bool)
            .unwrap_or(false);
        let status = trial_packet
            .get("status")
            .and_then(Value::as_str)
            .unwrap_or("");
        let visible_behavior = string_at(trial_packet, "/visible_behavior");
        let query_intent_decision = string_at(trial_packet, "/query_intent/decision");
        let reject_reason = string_at(trial_packet, "/query_intent/reject_reason");
        let memory_search_called = trial_packet
            .pointer("/baseline/memory_search_called")
            .and_then(Value::as_bool)
            .unwrap_or(false)
            || trial_packet
                .pointer("/side_effects/calls_memory_search")
                .and_then(Value::as_bool)
                .unwrap_or(false);
        let baseline_count_before = u64_at(
            trial_packet,
            "/baseline/baseline_candidate_count_before_gate",
        );
        let baseline_count_after = u64_at(
            trial_packet,
            "/baseline/baseline_candidate_count_after_gate",
        );
        let baseline_order_hash = redacted_external_hash(
            trial_packet
                .pointer("/baseline/baseline_order_hash_before_gate")
                .and_then(Value::as_str),
        );
        let side_effect_contract_safe =
            bool_false_at(trial_packet, "/side_effects/records_coactivation")
                && bool_false_at(trial_packet, "/side_effects/writes_memory")
                && bool_false_at(trial_packet, "/side_effects/writes_graph_edges")
                && bool_false_at(trial_packet, "/side_effects/changes_memory_search_order")
                && bool_false_at(
                    trial_packet,
                    "/side_effects/changes_default_memory_search_schema",
                )
                && bool_false_at(
                    trial_packet,
                    "/side_effects/changes_production_retrieval_default",
                )
                && bool_false_at(trial_packet, "/side_effects/runs_semantic_retrieval")
                && bool_false_at(trial_packet, "/side_effects/runs_graph_retrieval");
        let packet_raw = outer_raw
            || packet.raw_payload_fields_present
            || trigger_recall_value_contains_raw(trial_packet);

        let mut blockers = BTreeSet::<String>::new();
        push_if(
            &mut blockers,
            schema != TRIGGER_RECALL_OPT_IN_BASELINE_TRIAL_SCHEMA,
            "trial_packet_schema_mismatch",
        );
        push_if(&mut blockers, !read_only, "trial_packet_not_read_only");
        push_if(
            &mut blockers,
            !side_effect_contract_safe,
            "trial_packet_side_effect_contract_invalid",
        );
        push_if(&mut blockers, packet_raw, "raw_payload_fields_present");

        if packet_raw {
            raw_payload_blocked_count += 1;
        } else {
            match status {
                "returned_accepted" => returned_accepted_count += 1,
                "held_by_query_intent" => held_by_query_intent_count += 1,
                "transition_gate_blocked" => transition_gate_blocked_count += 1,
                "baseline_search_error" => baseline_search_error_count += 1,
                "baseline_search_pending" => baseline_search_pending_count += 1,
                _ => other_status_count += 1,
            }
        }
        if memory_search_called {
            trial_memory_search_called_count += 1;
        }
        baseline_count_before_total =
            baseline_count_before_total.saturating_add(baseline_count_before);
        baseline_count_after_total =
            baseline_count_after_total.saturating_add(baseline_count_after);
        if baseline_order_hash.is_some() {
            baseline_order_hash_count += 1;
        }
        let status_match = packet
            .expected_status
            .as_deref()
            .map(|expected| expected == status);
        let behavior_match = packet
            .expected_visible_behavior
            .as_deref()
            .map(|expected| expected == visible_behavior);
        if status_match == Some(false) || behavior_match == Some(false) {
            expectation_mismatch_count += 1;
        }
        let case_hash = redacted_external_hash(packet.case_id.as_deref())
            .unwrap_or_else(|| sha256_hex(&format!("packet:{index}")));
        let diagnostic_status = if packet_raw {
            "raw_payload_rejected"
        } else if blockers.is_empty() {
            "accepted_for_batch_summary"
        } else {
            "blocked_before_batch_summary"
        };

        packet_results.push(json!({
            "packet_index": index,
            "case_hash": case_hash,
            "diagnostic_status": diagnostic_status,
            "status": status,
            "visible_behavior": visible_behavior,
            "query_intent_decision": query_intent_decision,
            "reject_reason": reject_reason,
            "expected_status": packet.expected_status,
            "expected_visible_behavior": packet.expected_visible_behavior,
            "status_expectation_matched": status_match,
            "visible_behavior_expectation_matched": behavior_match,
            "trial_memory_search_called": memory_search_called,
            "baseline_candidate_count_before_gate": baseline_count_before,
            "baseline_candidate_count_after_gate": baseline_count_after,
            "baseline_order_hash": baseline_order_hash,
            "blocker_count": blockers.len(),
            "blockers": blockers.into_iter().collect::<Vec<_>>(),
            "trial_packet_included": false,
            "visible_hits_included": false,
            "raw_payload_fields_present": packet_raw
        }));
    }

    let packet_count = packet_results.len() as u64;
    let has_accepted = returned_accepted_count > 0;
    let has_held = held_by_query_intent_count > 0;
    let has_blocked_control = transition_gate_blocked_count > 0;
    let status = if packet_count == 0 {
        "blocked_no_packets"
    } else if raw_payload_blocked_count > 0 {
        "blocked_raw_payload_rejected"
    } else if expectation_mismatch_count > 0 {
        "blocked_expectation_mismatch"
    } else if has_accepted && has_held && has_blocked_control {
        "ready_for_enforce_hold_review_packet"
    } else if has_accepted && has_held {
        "needs_transition_blocked_control_packet"
    } else {
        "needs_accepted_and_held_trial_packets"
    };

    json!({
        "schema": TRIGGER_RECALL_OPT_IN_GATED_BATCH_DIAGNOSTICS_SCHEMA,
        "generated_at": unix_now_secs(),
        "read_only": true,
        "control_surface": "trigger_recall_opt_in_gated_batch_diagnostics",
        "status": status,
        "summary": {
            "packet_count": packet_count,
            "returned_accepted_count": returned_accepted_count,
            "held_by_query_intent_count": held_by_query_intent_count,
            "transition_gate_blocked_count": transition_gate_blocked_count,
            "baseline_search_error_count": baseline_search_error_count,
            "baseline_search_pending_count": baseline_search_pending_count,
            "other_status_count": other_status_count,
            "raw_payload_blocked_count": raw_payload_blocked_count,
            "expectation_mismatch_count": expectation_mismatch_count,
            "trial_memory_search_called_count": trial_memory_search_called_count,
            "batch_tool_calls_memory_search_count": 0,
            "baseline_candidate_count_before_gate_total": baseline_count_before_total,
            "baseline_candidate_count_after_gate_total": baseline_count_after_total,
            "baseline_order_hash_count": baseline_order_hash_count
        },
        "packet_results": packet_results,
        "decision": {
            "ready_for_enforce_hold_review_packet": status == "ready_for_enforce_hold_review_packet",
            "may_implement_enforce_hold_now": false,
            "may_change_default_memory_search_now": false,
            "recommended_next_step": match status {
                "ready_for_enforce_hold_review_packet" => "write_review_packet_before_any_enforce_hold_design",
                "needs_transition_blocked_control_packet" => "add_transition_blocked_control_trial_packet",
                "blocked_raw_payload_rejected" => "remove_raw_query_key_content_fields_and_rerun",
                "blocked_expectation_mismatch" => "inspect_expectation_mismatches_before_review",
                "blocked_no_packets" => "collect_gated_trial_packets",
                _ => "collect_accepted_and_held_trial_packets",
            }
        },
        "safety": {
            "trial_packets_included": false,
            "visible_hits_included": false,
            "raw_queries_included": false,
            "raw_keys_included": false,
            "content_included": false,
            "batch_tool_calls_memory_search": false,
            "records_coactivation": false,
            "writes_memory": false,
            "writes_graph_edges": false,
            "changes_memory_search_order": false,
            "changes_default_memory_search_schema": false,
            "changes_production_retrieval_default": false,
            "may_enforce_hold": false
        },
        "review_refs": {
            "attempt_id_hash": redacted_external_hash(options.attempt_id.as_deref()),
            "reviewer_present": options.reviewer.as_ref().map(|value| !value.trim().is_empty()).unwrap_or(false),
            "commit_present": options.commit.as_ref().map(|value| !value.trim().is_empty()).unwrap_or(false),
            "forum_post_id_present": options.forum_post_id.as_ref().map(|value| !value.trim().is_empty()).unwrap_or(false)
        },
        "input_contract": {
            "packet_count": packet_count,
            "trial_packet_included": false,
            "visible_hits_included": false,
            "raw_payload_fields_present": outer_raw,
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
            "changes_production_retrieval_default": false,
            "runs_semantic_retrieval": false,
            "runs_graph_retrieval": false,
            "may_enforce_hold": false
        },
        "calls_memory_search": false,
        "runs_biocortex": false,
        "changes_memory_search_order": false,
        "raw_queries_included": false,
        "raw_keys_included": false,
        "content_included": false
    })
}

#[cfg(test)]
mod tests {
    use super::*;

    const PROJECT_SCOPE: &str = "project:/Data/CascadeProjects/agent-bridge";

    fn ready_status_options() -> TriggerRecallOptInStatusOptions {
        TriggerRecallOptInStatusOptions {
            mode: "fts".to_string(),
            per_call_opt_in: true,
            scope: Some(PROJECT_SCOPE.to_string()),
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
        }
    }

    fn ready_status_packet() -> Value {
        trigger_recall_opt_in_status(ready_status_options())
    }

    fn ready_gate_options(status_packet: Value) -> TriggerRecallOptInRuntimeTransitionGateOptions {
        TriggerRecallOptInRuntimeTransitionGateOptions {
            status_packet,
            mode: "fts".to_string(),
            per_call_opt_in: true,
            scope: Some(PROJECT_SCOPE.to_string()),
            scope_mode: "local_only".to_string(),
            regression_anchor: Some(
                TRIGGER_RECALL_BASELINE_ACCEPTANCE_REGRESSION_ANCHOR.to_string(),
            ),
            runtime_enabled: true,
            ..Default::default()
        }
    }

    fn assert_has_blockers(value: &Value, expected: &[&str]) {
        let blockers = value["boundary_check"]["blockers"]
            .as_array()
            .expect("blockers");
        for expected in expected {
            assert!(
                blockers.contains(&json!(expected)),
                "missing blocker {expected}; blockers={blockers:?}"
            );
        }
    }

    #[test]
    fn status_ready_path_stays_readonly() {
        let status = ready_status_packet();
        assert_eq!(status["status"], json!("ready_for_transition_gate"));
        assert_eq!(status["side_effects"]["calls_memory_search"], json!(false));
        assert_eq!(
            status["side_effects"]["may_run_gated_baseline_trial_now"],
            json!(false)
        );
        assert_eq!(status["side_effects"]["may_enforce_hold_now"], json!(false));
    }

    #[test]
    fn status_batch_matrix_blocks_unsafe_transition_inputs() {
        let mut cases: Vec<(&str, TriggerRecallOptInStatusOptions, Vec<&str>)> = Vec::new();

        let mut hybrid = ready_status_options();
        hybrid.mode = "hybrid".to_string();
        cases.push(("hybrid mode", hybrid, vec!["requested_mode_not_authorized"]));

        let mut missing_opt_in = ready_status_options();
        missing_opt_in.per_call_opt_in = false;
        cases.push((
            "missing per-call opt-in",
            missing_opt_in,
            vec!["per_call_opt_in_missing"],
        ));

        let mut bad_scope = ready_status_options();
        bad_scope.scope = Some("project:relative-agent-bridge".to_string());
        cases.push((
            "non-exact project scope",
            bad_scope,
            vec!["exact_local_project_scope_missing"],
        ));

        let mut operator_disabled = ready_status_options();
        operator_disabled.operator_disabled = true;
        cases.push((
            "operator disabled",
            operator_disabled,
            vec!["operator_disabled"],
        ));

        let mut missing_metric = ready_status_options();
        missing_metric.baseline_shadow_true_hits_lost = None;
        cases.push((
            "missing metric",
            missing_metric,
            vec!["eval_metrics_absent", "baseline_shadow_true_hits_lost"],
        ));

        let mut union_miss = ready_status_options();
        union_miss.union_cont_misses = Some(1);
        cases.push((
            "union continuation miss",
            union_miss,
            vec!["union_cont_misses_present"],
        ));

        let mut wrong_anchor = ready_status_options();
        wrong_anchor.regression_anchor = Some("stale-anchor".to_string());
        cases.push((
            "wrong regression anchor",
            wrong_anchor,
            vec!["regression_anchor_mismatch"],
        ));

        let mut raw_payload = ready_status_options();
        raw_payload.raw_payload_fields_present = true;
        cases.push((
            "raw payload marker",
            raw_payload,
            vec!["raw_payload_fields_present"],
        ));

        for (name, options, expected_blockers) in cases {
            let status = trigger_recall_opt_in_status(options);
            assert_ne!(
                status["status"],
                json!("ready_for_transition_gate"),
                "{name}"
            );
            assert_eq!(
                status["boundary_check"]["ready_for_transition_gate"],
                json!(false),
                "{name}"
            );
            assert_eq!(
                status["side_effects"]["calls_memory_search"],
                json!(false),
                "{name}"
            );
            assert_eq!(
                status["side_effects"]["may_enforce_hold_now"],
                json!(false),
                "{name}"
            );
            assert_has_blockers(&status, &expected_blockers);
        }
    }

    #[test]
    fn transition_gate_allows_only_ready_redacted_status() {
        let gate = trigger_recall_opt_in_runtime_transition_gate(ready_gate_options(
            ready_status_packet(),
        ));
        assert_eq!(gate["status"], json!("transition_allowed"));
        assert_eq!(gate["transition"]["transition_allowed"], json!(true));
        assert_eq!(
            gate["transition"]["may_call_gated_baseline_trial"],
            json!(true)
        );
        assert_eq!(gate["transition"]["may_enforce_hold"], json!(false));
        assert_eq!(
            gate["transition"]["default_memory_search_unchanged"],
            json!(true)
        );
        assert_eq!(gate["side_effects"]["calls_memory_search"], json!(false));
        assert_eq!(gate["boundary_check"]["blockers"], json!([]));
    }

    #[test]
    fn transition_gate_batch_matrix_blocks_unsafe_packets() {
        let mut blocked_status_options = ready_status_options();
        blocked_status_options.per_call_opt_in = false;
        let blocked_status = trigger_recall_opt_in_status(blocked_status_options);
        let gate =
            trigger_recall_opt_in_runtime_transition_gate(ready_gate_options(blocked_status));
        assert_eq!(gate["transition"]["transition_allowed"], json!(false));
        assert_eq!(
            gate["transition"]["may_call_gated_baseline_trial"],
            json!(false)
        );
        assert_has_blockers(
            &gate,
            &[
                "status_packet_not_ready_for_transition_gate",
                "status_per_call_opt_in_missing",
            ],
        );

        let mut bad_schema = ready_status_packet();
        bad_schema["schema"] = json!("agent_bridge.memory.trigger_recall.opt_in_status.vOLD");
        let gate = trigger_recall_opt_in_runtime_transition_gate(ready_gate_options(bad_schema));
        assert_has_blockers(&gate, &["status_packet_schema_mismatch"]);

        let mut bad_side_effect = ready_status_packet();
        bad_side_effect["side_effects"]["calls_memory_search"] = json!(true);
        let gate =
            trigger_recall_opt_in_runtime_transition_gate(ready_gate_options(bad_side_effect));
        assert_has_blockers(&gate, &["status_packet_side_effect_contract_invalid"]);

        let mut gate_options = ready_gate_options(ready_status_packet());
        gate_options.mode = "hybrid".to_string();
        let gate = trigger_recall_opt_in_runtime_transition_gate(gate_options);
        assert_has_blockers(&gate, &["requested_mode_not_authorized"]);

        let mut gate_options = ready_gate_options(ready_status_packet());
        gate_options.per_call_opt_in = false;
        let gate = trigger_recall_opt_in_runtime_transition_gate(gate_options);
        assert_has_blockers(&gate, &["per_call_opt_in_missing"]);

        let mut gate_options = ready_gate_options(ready_status_packet());
        gate_options.raw_payload_fields_present = true;
        let gate = trigger_recall_opt_in_runtime_transition_gate(gate_options);
        assert_has_blockers(&gate, &["raw_payload_fields_present"]);
    }

    #[test]
    fn transition_gate_blocks_raw_packet_without_echoing() {
        let mut status = ready_status_packet();
        status["raw_query"] = json!("secret trigger query");
        let gate = trigger_recall_opt_in_runtime_transition_gate(ready_gate_options(status));
        let serialized = serde_json::to_string(&gate).expect("serialize");
        assert!(!serialized.contains("secret trigger query"));
        assert_has_blockers(&gate, &["status_packet_contains_raw_payload"]);
        assert_eq!(gate["transition"]["transition_allowed"], json!(false));
    }

    fn ready_transition_gate_fixture() -> Value {
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
        trigger_recall_opt_in_runtime_transition_gate(
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
        )
    }

    #[test]
    fn baseline_trial_blocks_before_search_and_redacts_query() {
        let query = "secret frontend dashboard query";
        let trial = trigger_recall_opt_in_gated_baseline_trial(
            TriggerRecallOptInGatedBaselineTrialOptions {
                runtime_transition_gate: Value::Null,
                query: query.to_string(),
                mode: "semantic".to_string(),
                per_call_opt_in: false,
                scope: Some("project:/secret/path".to_string()),
                scope_mode: "local_only".to_string(),
                runtime_enabled: true,
                raw_payload_fields_present: true,
                limit: 5,
                ..Default::default()
            },
        );
        let serialized = serde_json::to_string(&trial).expect("serialize");
        assert!(!serialized.contains(query));
        assert!(!serialized.contains("/secret/path"));
        assert_eq!(trial["status"], json!("transition_gate_blocked"));
        assert_eq!(trial["side_effects"]["calls_memory_search"], json!(false));
        let blockers = trial["runtime_transition_preflight"]["blockers"]
            .as_array()
            .expect("blockers");
        assert!(blockers.contains(&json!("transition_gate_schema_mismatch")));
        assert!(blockers.contains(&json!("requested_mode_not_authorized")));
        assert!(blockers.contains(&json!("per_call_opt_in_missing")));
        assert!(blockers.contains(&json!("raw_payload_fields_present")));
    }

    #[test]
    fn baseline_trial_returns_accepted_redacted_hits() {
        let trial = trigger_recall_opt_in_gated_baseline_trial(
            TriggerRecallOptInGatedBaselineTrialOptions {
                runtime_transition_gate: ready_transition_gate_fixture(),
                query: "LSWR G25 store write execution preflight landed output only plan next gate"
                    .to_string(),
                mode: "fts".to_string(),
                per_call_opt_in: true,
                scope: Some("project:/Data/CascadeProjects/agent-bridge".to_string()),
                scope_mode: "local_only".to_string(),
                runtime_enabled: true,
                limit: 5,
                baseline_hits: Some(vec![TriggerRecallOptInGatedBaselineTrialHit {
                    key: "secret_g25_key".to_string(),
                    kind: "decision".to_string(),
                    score: 42.0,
                    scope: Some("project:/Data/CascadeProjects/agent-bridge".to_string()),
                    created_at: 1,
                    updated_at: 2,
                    tags_count: 0,
                }]),
                baseline_search_called: true,
                ..Default::default()
            },
        );
        let serialized = serde_json::to_string(&trial).expect("serialize");
        assert!(!serialized.contains("secret_g25_key"));
        assert_eq!(trial["status"], json!("returned_accepted"));
        assert_eq!(trial["query_intent"]["decision"], json!("allow"));
        assert_eq!(
            trial["baseline"]["baseline_candidate_count_before_gate"],
            json!(1)
        );
        assert_eq!(
            trial["baseline"]["baseline_candidate_count_after_gate"],
            json!(1)
        );
        assert_eq!(trial["visible_hits"].as_array().expect("hits").len(), 1);
        assert_eq!(trial["side_effects"]["calls_memory_search"], json!(true));
        assert_eq!(trial["side_effects"]["records_coactivation"], json!(false));
    }

    #[test]
    fn baseline_trial_holds_rejected_query_with_explicit_status() {
        let query = "Goal C dashboard state card spacing responsive layout visual design only";
        let trial = trigger_recall_opt_in_gated_baseline_trial(
            TriggerRecallOptInGatedBaselineTrialOptions {
                runtime_transition_gate: ready_transition_gate_fixture(),
                query: query.to_string(),
                mode: "fts".to_string(),
                per_call_opt_in: true,
                scope: Some("project:/Data/CascadeProjects/agent-bridge".to_string()),
                scope_mode: "local_only".to_string(),
                runtime_enabled: true,
                limit: 5,
                baseline_hits: Some(vec![TriggerRecallOptInGatedBaselineTrialHit {
                    key: "secret_frontend_key".to_string(),
                    kind: "decision".to_string(),
                    score: 7.0,
                    scope: None,
                    created_at: 1,
                    updated_at: 2,
                    tags_count: 0,
                }]),
                baseline_search_called: true,
                ..Default::default()
            },
        );
        let serialized = serde_json::to_string(&trial).expect("serialize");
        assert!(!serialized.contains(query));
        assert!(!serialized.contains("secret_frontend_key"));
        assert_eq!(trial["status"], json!("held_by_query_intent"));
        assert_eq!(trial["visible_behavior"], json!("held_by_query_intent"));
        assert_eq!(
            trial["fallback_behavior"],
            json!("hold_packet_not_empty_search")
        );
        assert_eq!(trial["query_intent"]["decision"], json!("hold"));
        assert_eq!(
            trial["query_intent"]["reject_reason"],
            json!("frontend_dashboard_intent")
        );
        assert_eq!(trial["visible_hits"], json!([]));
        assert_eq!(
            trial["baseline"]["baseline_candidate_count_before_gate"],
            json!(1)
        );
        assert_eq!(
            trial["baseline"]["baseline_candidate_count_after_gate"],
            json!(0)
        );
    }

    #[test]
    fn gated_batch_diagnostics_summarizes_trial_statuses_without_store_calls() {
        let accepted = trigger_recall_opt_in_gated_baseline_trial(
            TriggerRecallOptInGatedBaselineTrialOptions {
                runtime_transition_gate: ready_transition_gate_fixture(),
                query: "LSWR G25 store write execution preflight landed output only plan next gate"
                    .to_string(),
                mode: "fts".to_string(),
                per_call_opt_in: true,
                scope: Some(PROJECT_SCOPE.to_string()),
                scope_mode: "local_only".to_string(),
                runtime_enabled: true,
                limit: 5,
                baseline_hits: Some(vec![TriggerRecallOptInGatedBaselineTrialHit {
                    key: "secret_batch_accept_key".to_string(),
                    kind: "decision".to_string(),
                    score: 42.0,
                    scope: Some(PROJECT_SCOPE.to_string()),
                    created_at: 1,
                    updated_at: 2,
                    tags_count: 0,
                }]),
                baseline_search_called: true,
                ..Default::default()
            },
        );
        let held = trigger_recall_opt_in_gated_baseline_trial(
            TriggerRecallOptInGatedBaselineTrialOptions {
                runtime_transition_gate: ready_transition_gate_fixture(),
                query: "Goal C dashboard state card spacing responsive layout visual design only"
                    .to_string(),
                mode: "fts".to_string(),
                per_call_opt_in: true,
                scope: Some(PROJECT_SCOPE.to_string()),
                scope_mode: "local_only".to_string(),
                runtime_enabled: true,
                limit: 5,
                baseline_hits: Some(vec![TriggerRecallOptInGatedBaselineTrialHit {
                    key: "secret_batch_hold_key".to_string(),
                    kind: "decision".to_string(),
                    score: 7.0,
                    scope: None,
                    created_at: 1,
                    updated_at: 2,
                    tags_count: 0,
                }]),
                baseline_search_called: true,
                ..Default::default()
            },
        );
        let blocked = trigger_recall_opt_in_gated_baseline_trial(
            TriggerRecallOptInGatedBaselineTrialOptions {
                runtime_transition_gate: Value::Null,
                query: "blocked transition query".to_string(),
                mode: "fts".to_string(),
                per_call_opt_in: true,
                scope: Some(PROJECT_SCOPE.to_string()),
                scope_mode: "local_only".to_string(),
                runtime_enabled: true,
                limit: 5,
                ..Default::default()
            },
        );

        let batch = trigger_recall_opt_in_gated_batch_diagnostics(
            TriggerRecallOptInGatedBatchDiagnosticsOptions {
                packets: vec![
                    TriggerRecallOptInGatedBatchDiagnosticsPacket {
                        trial_packet: accepted,
                        case_id: Some("accepted secret case".to_string()),
                        expected_status: Some("returned_accepted".to_string()),
                        expected_visible_behavior: Some("baseline_fts_visible".to_string()),
                        ..Default::default()
                    },
                    TriggerRecallOptInGatedBatchDiagnosticsPacket {
                        trial_packet: held,
                        case_id: Some("held secret case".to_string()),
                        expected_status: Some("held_by_query_intent".to_string()),
                        expected_visible_behavior: Some("held_by_query_intent".to_string()),
                        ..Default::default()
                    },
                    TriggerRecallOptInGatedBatchDiagnosticsPacket {
                        trial_packet: blocked,
                        case_id: Some("blocked secret case".to_string()),
                        expected_status: Some("transition_gate_blocked".to_string()),
                        expected_visible_behavior: Some("transition_gate_blocked".to_string()),
                        ..Default::default()
                    },
                ],
                attempt_id: Some("batch-attempt-1".to_string()),
                reviewer: Some("codex".to_string()),
                commit: Some("batch-commit".to_string()),
                forum_post_id: Some("3975".to_string()),
                ..Default::default()
            },
        );

        let serialized = serde_json::to_string(&batch).expect("serialize");
        assert!(!serialized.contains("secret_batch_accept_key"));
        assert!(!serialized.contains("secret_batch_hold_key"));
        assert!(!serialized.contains("accepted secret case"));
        assert!(!serialized.contains("held secret case"));
        assert!(!serialized.contains("blocked secret case"));
        assert_eq!(
            batch["schema"],
            json!(TRIGGER_RECALL_OPT_IN_GATED_BATCH_DIAGNOSTICS_SCHEMA)
        );
        assert_eq!(batch["read_only"], json!(true));
        assert_eq!(
            batch["status"],
            json!("ready_for_enforce_hold_review_packet")
        );
        assert_eq!(batch["summary"]["packet_count"], json!(3));
        assert_eq!(batch["summary"]["returned_accepted_count"], json!(1));
        assert_eq!(batch["summary"]["held_by_query_intent_count"], json!(1));
        assert_eq!(batch["summary"]["transition_gate_blocked_count"], json!(1));
        assert_eq!(
            batch["summary"]["trial_memory_search_called_count"],
            json!(2)
        );
        assert_eq!(
            batch["summary"]["batch_tool_calls_memory_search_count"],
            json!(0)
        );
        assert_eq!(
            batch["decision"]["ready_for_enforce_hold_review_packet"],
            json!(true)
        );
        assert_eq!(
            batch["decision"]["may_implement_enforce_hold_now"],
            json!(false)
        );
        assert_eq!(batch["safety"]["trial_packets_included"], json!(false));
        assert_eq!(batch["safety"]["visible_hits_included"], json!(false));
        assert_eq!(batch["side_effects"]["calls_memory_search"], json!(false));
        assert_eq!(batch["side_effects"]["may_enforce_hold"], json!(false));
    }

    #[test]
    fn gated_batch_diagnostics_rejects_raw_trial_packet_without_echoing() {
        let mut trial = trigger_recall_opt_in_gated_baseline_trial(
            TriggerRecallOptInGatedBaselineTrialOptions {
                runtime_transition_gate: ready_transition_gate_fixture(),
                query: "LSWR G25 store write execution preflight landed output only plan next gate"
                    .to_string(),
                mode: "fts".to_string(),
                per_call_opt_in: true,
                scope: Some(PROJECT_SCOPE.to_string()),
                scope_mode: "local_only".to_string(),
                runtime_enabled: true,
                limit: 5,
                baseline_search_called: true,
                ..Default::default()
            },
        );
        trial["raw_query"] = json!("secret batch raw query");
        trial["raw_key"] = json!("secret_batch_raw_key");
        trial["content"] = json!("secret batch raw content");

        let batch = trigger_recall_opt_in_gated_batch_diagnostics(
            TriggerRecallOptInGatedBatchDiagnosticsOptions {
                packets: vec![TriggerRecallOptInGatedBatchDiagnosticsPacket {
                    trial_packet: trial,
                    case_id: Some("raw secret case".to_string()),
                    expected_status: Some("returned_accepted".to_string()),
                    ..Default::default()
                }],
                ..Default::default()
            },
        );

        let serialized = serde_json::to_string(&batch).expect("serialize");
        assert!(!serialized.contains("secret batch raw query"));
        assert!(!serialized.contains("secret_batch_raw_key"));
        assert!(!serialized.contains("secret batch raw content"));
        assert!(!serialized.contains("raw secret case"));
        assert_eq!(batch["status"], json!("blocked_raw_payload_rejected"));
        assert_eq!(batch["summary"]["raw_payload_blocked_count"], json!(1));
        assert_eq!(
            batch["packet_results"][0]["trial_packet_included"],
            json!(false)
        );
        let blockers = batch["packet_results"][0]["blockers"]
            .as_array()
            .expect("blockers");
        assert!(blockers.contains(&json!("raw_payload_fields_present")));
    }
}
