//! Read-only focus-follow planning for the Linux desktop Avatar.
//!
//! This module consumes an already captured Sway tree and proposes a bounded
//! path for the Avatar window. It never invokes Sway, moves a window, changes
//! focus, or controls the pointer.

use anyhow::{ensure, Result};
use serde::{Deserialize, Serialize};
use serde_json::{json, Value};

pub const FOCUS_FOLLOW_SCHEMA: &str = "agent_bridge.avatar_focus_follow_plan.v1";
pub const FOCUS_FOLLOW_ACTION_SCHEMA: &str = "agent_bridge.avatar_focus_follow_action.v2";
pub const FOCUS_FOLLOW_RECOMMEND_SCHEMA: &str =
    "agent_bridge.avatar_focus_follow_recommendation.v2";
pub const FOCUS_FOLLOW_PROMPT_SCHEMA: &str = "agent_bridge.avatar_focus_follow_prompt.v2";
pub const FOCUS_FOLLOW_ACK_SCHEMA_V1: &str = "agent_bridge.avatar_focus_follow_ack.v1";
pub const FOCUS_FOLLOW_ACK_SCHEMA: &str = "agent_bridge.avatar_focus_follow_ack.v2";
pub const FOCUS_FOLLOW_OUTCOME_SCHEMA_V1: &str = "agent_bridge.avatar_focus_follow_outcome.v1";
pub const FOCUS_FOLLOW_OUTCOME_SCHEMA: &str = "agent_bridge.avatar_focus_follow_outcome.v2";
pub const DEFAULT_AVATAR_APP_ID: &str = "agent-bridge-avatar";
pub const FOCUS_FOLLOW_ACTIONS: [&str; 6] = [
    "turn_left",
    "turn_right",
    "walk_left",
    "walk_right",
    "arrive_settle",
    "wave",
];

/// Return the target from a successfully completed focus-follow receipt.
/// Malformed, cancelled, failed, or older-schema receipts fail closed.
pub fn acknowledged_target_from_receipt(
    receipt: &Value,
    compositor_session_id: &str,
    avatar_node_id: i64,
) -> Option<i64> {
    let matches_session = receipt.get("schema")?.as_str()? == FOCUS_FOLLOW_ACK_SCHEMA
        && receipt.get("status")?.as_str()? == "completed"
        && receipt.get("compositor_session_id")?.as_str()? == compositor_session_id
        && receipt.get("avatar_node_id")?.as_i64()? == avatar_node_id;
    matches_session
        .then(|| receipt.get("target_node_id")?.as_i64())
        .flatten()
}

pub fn sway_command_succeeded(payload: &[u8]) -> bool {
    serde_json::from_slice::<Value>(payload)
        .ok()
        .and_then(|value| value.as_array().cloned())
        .is_some_and(|items| {
            !items.is_empty()
                && items
                    .iter()
                    .all(|item| item.get("success").and_then(Value::as_bool) == Some(true))
        })
}

/// Return the stable pairing key only for current v2 outcome records. Historical
/// v1 rows intentionally remain readable evidence but cannot prove pairing.
pub fn pairable_focus_follow_attempt_id(record: &Value) -> Option<&str> {
    (record.get("schema")?.as_str()? == FOCUS_FOLLOW_OUTCOME_SCHEMA)
        .then(|| record.get("attempt_id")?.as_str())
        .flatten()
        .filter(|attempt_id| !attempt_id.is_empty())
}

pub fn focus_follow_arrival_failure_reason(
    observed_plan: &Value,
    expected_target_node_id: i64,
    expected_avatar_node_id: i64,
    destination_x: i64,
    destination_y: i64,
) -> Option<&'static str> {
    if observed_plan
        .pointer("/target/node_id")
        .and_then(Value::as_i64)
        != Some(expected_target_node_id)
    {
        return Some("focus_target_changed_at_arrival");
    }
    if observed_plan
        .pointer("/avatar/node_id")
        .and_then(Value::as_i64)
        != Some(expected_avatar_node_id)
    {
        return Some("avatar_identity_changed_at_arrival");
    }
    let x = observed_plan
        .pointer("/avatar/current_rect/x")
        .and_then(Value::as_i64);
    let y = observed_plan
        .pointer("/avatar/current_rect/y")
        .and_then(Value::as_i64);
    if x.is_none_or(|value| (value - destination_x).abs() > 8)
        || y.is_none_or(|value| (value - destination_y).abs() > 32)
    {
        return Some("arrival_postcondition_mismatch");
    }
    None
}

pub fn focus_follow_outcome_record(
    action: &Value,
    phase: &str,
    observed_at_unix_ms: u64,
) -> Result<Value> {
    ensure!(
        matches!(phase, "started" | "final"),
        "invalid outcome phase"
    );
    let attempt_id = action
        .get("attempt_id")
        .and_then(Value::as_str)
        .filter(|value| {
            value.starts_with("af-")
                && value.len() <= 64
                && value
                    .bytes()
                    .all(|byte| byte.is_ascii_alphanumeric() || byte == b'-')
        })
        .ok_or_else(|| anyhow::anyhow!("invalid or missing outcome attempt_id"))?;
    let status = action
        .get("status")
        .and_then(Value::as_str)
        .unwrap_or("unknown");
    let final_phase = phase == "final";
    let negative_learning_candidate = final_phase && matches!(status, "failed" | "cancelled");
    Ok(json!({
        "schema": FOCUS_FOLLOW_OUTCOME_SCHEMA,
        "attempt_id": attempt_id,
        "phase": phase,
        "observed_at_unix_ms": observed_at_unix_ms,
        "status": status,
        "outcome_class": if !final_phase {
            "attempt_started"
        } else if status == "completed" {
            "positive"
        } else {
            "negative"
        },
        "rollback_available": true,
        "automatic_rollback": false,
        "expression_scope": "avatar_window_only",
        "authorization_mode": action.get("authorization_mode"),
        "target_node_id": action.pointer("/plan/target/node_id"),
        "avatar_node_id": action.pointer("/plan/avatar/node_id"),
        "travel_px": action.get("travel_px"),
        "executed_steps": action.get("executed_steps"),
        "execution_stage": action.get("execution_stage"),
        "stopped_reason": action.get("stopped_reason"),
        "postcondition_verified": action.get("postcondition_verified"),
        "negative_learning_candidate": negative_learning_candidate,
        "requires_lesson_on_rollback": negative_learning_candidate,
        "moves_pointer": false,
        "changes_focus": false,
        "emits_keyboard_input": false,
    }))
}

pub fn focus_follow_runtime_bindings() -> Value {
    json!({
        "turn_left": {
            "asset": "xiao-shu-v3-focus-turn-left-v1",
            "alpha_ready": true,
            "dedicated_motion": true,
        },
        "turn_right": {
            "asset": "xiao-shu-v3-focus-turn-right-v1",
            "alpha_ready": true,
            "dedicated_motion": true,
        },
        "walk_left": {
            "asset": "xiao-shu-v3-focus-walk-left-v1",
            "alpha_ready": true,
            "dedicated_motion": true,
        },
        "walk_right": {
            "asset": "xiao-shu-v3-focus-walk-right-v1",
            "alpha_ready": true,
            "dedicated_motion": true,
        },
        "arrive_settle": {
            "asset": "xiao-shu-v3-ai-completion-nod-v2",
            "alpha_ready": true,
            "dedicated_motion": true,
        },
        "wave": {
            "asset": "xiao-shu-v3-focus-wave-v1",
            "alpha_ready": true,
            "dedicated_motion": true,
        },
    })
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub struct FocusRect {
    pub x: i64,
    pub y: i64,
    pub width: i64,
    pub height: i64,
}

impl FocusRect {
    fn center(self) -> (i64, i64) {
        (self.x + self.width / 2, self.y + self.height / 2)
    }

    fn overlaps(self, other: Self) -> bool {
        self.x < other.x + other.width
            && self.x + self.width > other.x
            && self.y < other.y + other.height
            && self.y + self.height > other.y
    }
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct FocusFollowOptions {
    pub avatar_app_id: String,
    pub margin_px: i64,
    pub max_step_px: i64,
}

impl Default for FocusFollowOptions {
    fn default() -> Self {
        Self {
            avatar_app_id: DEFAULT_AVATAR_APP_ID.to_string(),
            margin_px: 24,
            max_step_px: 48,
        }
    }
}

#[derive(Debug, Clone)]
struct WindowRef {
    rect: FocusRect,
    app_id: Option<String>,
    identity_kind: Option<&'static str>,
    title: Option<String>,
    node_id: Option<i64>,
    workspace: Option<String>,
    workspace_rect: FocusRect,
    fullscreen: bool,
    sensitive_mark: bool,
}

fn structured_window_identity(value: &Value) -> Option<String> {
    value
        .get("app_id")
        .and_then(Value::as_str)
        .or_else(|| {
            value
                .pointer("/window_properties/class")
                .and_then(Value::as_str)
        })
        .or_else(|| {
            value
                .pointer("/window_properties/instance")
                .and_then(Value::as_str)
        })
        .map(str::to_string)
}

fn structured_window_identity_kind(value: &Value) -> Option<&'static str> {
    if value.get("app_id").and_then(Value::as_str).is_some() {
        Some("wayland_app_id")
    } else if value
        .pointer("/window_properties/class")
        .and_then(Value::as_str)
        .is_some()
        || value
            .pointer("/window_properties/instance")
            .and_then(Value::as_str)
            .is_some()
    {
        Some("xwayland_class")
    } else {
        None
    }
}

fn has_sensitive_mark(value: &Value) -> bool {
    value
        .get("marks")
        .and_then(Value::as_array)
        .is_some_and(|marks| {
            marks
                .iter()
                .any(|mark| mark.as_str() == Some("ab-sensitive"))
        })
}

fn rect_at(value: &Value) -> Option<FocusRect> {
    let rect = value.get("rect")?;
    let parsed = FocusRect {
        x: rect.get("x")?.as_i64()?,
        y: rect.get("y")?.as_i64()?,
        width: rect.get("width")?.as_i64()?,
        height: rect.get("height")?.as_i64()?,
    };
    (parsed.width > 0 && parsed.height > 0).then_some(parsed)
}

fn child_values(value: &Value) -> impl Iterator<Item = &Value> {
    ["nodes", "floating_nodes"]
        .into_iter()
        .filter_map(|key| value.get(key).and_then(Value::as_array))
        .flatten()
}

fn find_avatar(value: &Value, app_id: &str) -> Option<WindowRef> {
    if value.get("app_id").and_then(Value::as_str) == Some(app_id) {
        let rect = rect_at(value)?;
        return Some(WindowRef {
            rect,
            app_id: Some(app_id.to_string()),
            identity_kind: Some("wayland_app_id"),
            title: value
                .get("name")
                .and_then(Value::as_str)
                .map(str::to_string),
            node_id: value.get("id").and_then(Value::as_i64),
            workspace: None,
            workspace_rect: rect,
            fullscreen: false,
            sensitive_mark: false,
        });
    }
    child_values(value).find_map(|child| find_avatar(child, app_id))
}

fn find_focused_target(
    value: &Value,
    avatar_app_id: &str,
    workspace: Option<(&str, FocusRect)>,
    ancestor_fullscreen: bool,
    ancestor_sensitive_mark: bool,
) -> Option<WindowRef> {
    let node_type = value.get("type").and_then(Value::as_str);
    let fullscreen = ancestor_fullscreen
        || (node_type != Some("workspace")
            && value
                .get("fullscreen_mode")
                .and_then(Value::as_i64)
                .is_some_and(|mode| mode != 0));
    let sensitive_mark = ancestor_sensitive_mark || has_sensitive_mark(value);
    let next_workspace = if node_type == Some("workspace") {
        rect_at(value).map(|rect| {
            (
                value
                    .get("name")
                    .and_then(Value::as_str)
                    .unwrap_or("unknown"),
                rect,
            )
        })
    } else {
        workspace
    };

    for child in child_values(value) {
        if let Some(found) = find_focused_target(
            child,
            avatar_app_id,
            next_workspace,
            fullscreen,
            sensitive_mark,
        ) {
            return Some(found);
        }
    }

    if value.get("focused").and_then(Value::as_bool) != Some(true)
        || value.get("app_id").and_then(Value::as_str) == Some(avatar_app_id)
    {
        return None;
    }
    let rect = rect_at(value)?;
    let (workspace_name, workspace_rect) = next_workspace?;
    Some(WindowRef {
        rect,
        app_id: structured_window_identity(value),
        identity_kind: structured_window_identity_kind(value),
        title: value
            .get("name")
            .and_then(Value::as_str)
            .map(str::to_string),
        node_id: value.get("id").and_then(Value::as_i64),
        workspace: Some(workspace_name.to_string()),
        workspace_rect,
        fullscreen,
        sensitive_mark,
    })
}

fn clamp(value: i64, min: i64, max: i64) -> i64 {
    value.max(min).min(max.max(min))
}

fn docking_candidates(
    target: FocusRect,
    workspace: FocusRect,
    avatar: FocusRect,
    margin: i64,
) -> Vec<(&'static str, FocusRect)> {
    let x_min = workspace.x;
    let y_min = workspace.y;
    let x_max = workspace.x + workspace.width - avatar.width;
    let y_max = workspace.y + workspace.height - avatar.height;
    let raw = [
        (
            "right",
            target.x + target.width + margin,
            target.y + target.height - avatar.height - margin,
        ),
        (
            "left",
            target.x - avatar.width - margin,
            target.y + target.height - avatar.height - margin,
        ),
        (
            "bottom",
            target.x + target.width - avatar.width - margin,
            target.y + target.height + margin,
        ),
        (
            "top",
            target.x + target.width - avatar.width - margin,
            target.y - avatar.height - margin,
        ),
    ];
    raw.into_iter()
        .map(|(edge, x, y)| {
            (
                edge,
                FocusRect {
                    x: clamp(x, x_min, x_max),
                    y: clamp(y, y_min, y_max),
                    width: avatar.width,
                    height: avatar.height,
                },
            )
        })
        .filter(|(_, candidate)| !candidate.overlaps(target))
        .collect()
}

fn path_points(from: FocusRect, to: FocusRect, max_step_px: i64) -> Vec<Value> {
    let dx = to.x - from.x;
    let dy = to.y - from.y;
    let distance_axis = dx.abs().max(dy.abs());
    let steps = ((distance_axis + max_step_px - 1) / max_step_px).clamp(1, 32);
    (1..=steps)
        .map(|step| {
            json!({
                "step": step,
                "x": from.x + dx * step / steps,
                "y": from.y + dy * step / steps,
            })
        })
        .collect()
}

fn base_plan(status: &str) -> Value {
    json!({
        "schema": FOCUS_FOLLOW_SCHEMA,
        "status": status,
        "read_only": true,
        "default_enabled": false,
        "movement_authorized": false,
        "dispatch": null,
        "controls_desktop": false,
        "moves_pointer": false,
        "changes_focus": false,
        "emits_input": false,
        "action_registry": {
            "actions": FOCUS_FOLLOW_ACTIONS,
            "concept_asset": "xiao-shu-v3-ai-focus-follow-actions-v1-contact",
            "concept_only": false,
            "runtime_bindings": focus_follow_runtime_bindings(),
            "runtime_baseline_alpha_ready": true,
            "dedicated_turn_atlases_ready": true,
            "dedicated_walk_atlases_ready": true,
            "dedicated_wave_atlas_ready": true,
            "runtime_bound": true,
        },
    })
}

pub fn focus_follow_plan_from_sway_tree(tree: &Value, opts: &FocusFollowOptions) -> Value {
    let Some(avatar) = find_avatar(tree, &opts.avatar_app_id) else {
        let mut plan = base_plan("avatar_not_found");
        plan["recommended_action"] = json!("start_or_restore_avatar_then_replan");
        return plan;
    };
    let Some(target) = find_focused_target(tree, &opts.avatar_app_id, None, false, false) else {
        let mut plan = base_plan("focus_target_not_found");
        plan["avatar"] =
            json!({"node_id": avatar.node_id, "app_id": avatar.app_id, "rect": avatar.rect});
        plan["recommended_action"] = json!("focus_a_non_avatar_window_then_replan");
        return plan;
    };

    if target.fullscreen {
        let mut plan = base_plan("fullscreen_target");
        plan["avatar"] = json!({
            "node_id": avatar.node_id,
            "app_id": opts.avatar_app_id,
            "rect": avatar.rect,
        });
        plan["target"] = json!({
            "node_id": target.node_id,
            "app_id": target.app_id,
            "identity_kind": target.identity_kind,
            "identity_present": target.app_id.is_some(),
            "title": target.title,
            "rect": target.rect,
            "workspace": target.workspace,
            "workspace_rect": target.workspace_rect,
            "fullscreen": true,
            "sensitive_mark": target.sensitive_mark,
        });
        plan["recommended_action"] = json!("keep_current_position");
        return plan;
    }

    let margin = opts.margin_px.clamp(8, 256);
    let max_step = opts.max_step_px.clamp(8, 256);
    let current_center = avatar.rect.center();
    let candidates = docking_candidates(target.rect, target.workspace_rect, avatar.rect, margin);
    let selected = candidates.into_iter().min_by_key(|(_, rect)| {
        let center = rect.center();
        (center.0 - current_center.0).pow(2) + (center.1 - current_center.1).pow(2)
    });
    let Some((edge, destination)) = selected else {
        let mut plan = base_plan("no_safe_docking_point");
        plan["avatar"] =
            json!({"node_id": avatar.node_id, "app_id": avatar.app_id, "rect": avatar.rect});
        plan["target"] = json!({
            "rect": target.rect,
            "workspace": target.workspace,
            "workspace_rect": target.workspace_rect,
        });
        plan["recommended_action"] = json!("keep_current_position");
        return plan;
    };

    let dx = destination.x - avatar.rect.x;
    let direction = if dx < 0 { "left" } else { "right" };
    let path = path_points(avatar.rect, destination, max_step);
    let mut plan = base_plan(
        if avatar.rect.x == destination.x && avatar.rect.y == destination.y {
            "already_near_focus"
        } else {
            "planned"
        },
    );
    plan["avatar"] = json!({
        "node_id": avatar.node_id,
        "app_id": opts.avatar_app_id,
        "current_rect": avatar.rect,
        "destination_rect": destination,
    });
    plan["target"] = json!({
        "node_id": target.node_id,
        "app_id": target.app_id,
        "identity_kind": target.identity_kind,
        "identity_present": target.app_id.is_some(),
        "title": target.title,
        "rect": target.rect,
        "workspace": target.workspace,
        "workspace_rect": target.workspace_rect,
        "fullscreen": target.fullscreen,
        "sensitive_mark": target.sensitive_mark,
    });
    plan["docking"] = json!({"edge": edge, "margin_px": margin});
    plan["path"] = json!({
        "max_step_px": max_step,
        "point_count": path.len(),
        "points": path,
    });
    plan["choreography"] = json!([
        format!("turn_{direction}"),
        format!("walk_{direction}"),
        "arrive_settle",
    ]);
    plan["recommended_action"] = json!("review_plan_only_no_dispatch");
    plan
}

pub fn focus_follow_recommendation(
    plan: &Value,
    last_target_node_id: Option<i64>,
    min_travel_px: i64,
) -> Value {
    let plan_status = plan
        .get("status")
        .and_then(Value::as_str)
        .unwrap_or("unknown");
    let target_node_id = plan.pointer("/target/node_id").and_then(Value::as_i64);
    let current = plan.pointer("/avatar/current_rect");
    let destination = plan.pointer("/avatar/destination_rect");
    let travel_px = current.zip(destination).and_then(|(from, to)| {
        Some(
            (to.get("x")?.as_i64()? - from.get("x")?.as_i64()?)
                .abs()
                .max((to.get("y")?.as_i64()? - from.get("y")?.as_i64()?).abs()),
        )
    });
    let min_travel_px = min_travel_px.clamp(24, 512);
    let same_target = last_target_node_id.is_some() && last_target_node_id == target_node_id;
    let (decision, reason) = if !matches!(plan_status, "planned" | "already_near_focus") {
        ("suppress", "plan_not_actionable")
    } else if target_node_id.is_none() || travel_px.is_none() {
        ("suppress", "plan_missing_target_or_rects")
    } else if same_target {
        ("stay", "target_unchanged")
    } else if plan_status == "already_near_focus"
        || travel_px.is_some_and(|distance| distance < min_travel_px)
    {
        ("stay", "movement_below_threshold")
    } else {
        ("recommend_move", "new_focus_target_outside_threshold")
    };

    json!({
        "schema": FOCUS_FOLLOW_RECOMMEND_SCHEMA,
        "status": "ready",
        "read_only": true,
        "default_enabled": false,
        "dispatch": null,
        "writes_state": false,
        "moves_avatar": false,
        "moves_pointer": false,
        "changes_focus": false,
        "emits_input": false,
        "decision": decision,
        "reason": reason,
        "last_target_node_id": last_target_node_id,
        "target_node_id": target_node_id,
        "target_changed": last_target_node_id.is_some() && !same_target,
        "min_travel_px": min_travel_px,
        "travel_px": travel_px,
        "requires_explicit_action_confirmation": false,
        "requires_agent_expression_decision": decision == "recommend_move",
        "recommended_command": if decision == "recommend_move" {
            Some("agent-bridge avatar focus-follow-action --execute --reason <reason>")
        } else {
            None
        },
        "plan": plan,
    })
}

pub fn focus_follow_prompt_preflight(
    recommendation: &Value,
    show: bool,
    confirm: bool,
    cooldown_active: bool,
    timeout_ms: u64,
) -> Value {
    let decision = recommendation
        .get("decision")
        .and_then(Value::as_str)
        .unwrap_or("suppress");
    let (status, blocked_reason) = if decision != "recommend_move" {
        ("suppressed", Some("movement_not_recommended"))
    } else if cooldown_active {
        ("suppressed", Some("cooldown_active"))
    } else if show {
        ("ready", None)
    } else {
        ("dry_run", None)
    };

    json!({
        "schema": FOCUS_FOLLOW_PROMPT_SCHEMA,
        "status": status,
        "ready": status == "ready",
        "default_enabled": false,
        "show_requested": show,
        "explicitly_confirmed": confirm,
        "authorization_mode": if confirm { "owner_confirmed_legacy" } else { "agent_reversible_expression" },
        "agent_autonomy_allowed": true,
        "blocked_reason": blocked_reason,
        "presentation": {
            "kind": "avatar_anchored_bubble",
            "app_name": "Xiao Shu",
            "title": "小舒",
            "text": "我过去看看。",
            "timeout_ms": timeout_ms.clamp(2_000, 30_000),
            "anchor": "above_avatar",
            "edge_avoidance": "inside_avatar_surface",
            "fallback": "desktop_notification_bubble",
            "dismissible": false,
            "transient": true,
        },
        "rate_limited": true,
        "cooldown_active": cooldown_active,
        "emits_audio": false,
        "moves_avatar": false,
        "moves_pointer": false,
        "changes_focus": false,
        "executes_recommendation": false,
        "requires_separate_movement_confirmation": false,
        "movement_remains_a_separate_agent_decision": true,
        "recommendation": recommendation,
    })
}

pub fn focus_follow_action_preflight(
    plan: &Value,
    execute: bool,
    confirm: bool,
    reason: Option<&str>,
    max_travel_px: i64,
    cancel_file: Option<&str>,
) -> Value {
    let plan_status = plan
        .get("status")
        .and_then(Value::as_str)
        .unwrap_or("unknown");
    let current = plan.pointer("/avatar/current_rect");
    let destination = plan.pointer("/avatar/destination_rect");
    let travel_px = current.zip(destination).and_then(|(from, to)| {
        Some(
            (to.get("x")?.as_i64()? - from.get("x")?.as_i64()?)
                .abs()
                .max((to.get("y")?.as_i64()? - from.get("y")?.as_i64()?).abs()),
        )
    });
    let bounded_max = max_travel_px.clamp(48, 2_048);
    let reason = reason.map(str::trim).filter(|value| !value.is_empty());
    let blocked_reason = if !matches!(plan_status, "planned" | "already_near_focus") {
        Some("focus_follow_plan_not_actionable")
    } else if plan
        .pointer("/avatar/node_id")
        .and_then(Value::as_i64)
        .is_none()
        || plan
            .pointer("/target/node_id")
            .and_then(Value::as_i64)
            .is_none()
    {
        Some("focus_follow_plan_missing_identity")
    } else if travel_px.is_none() {
        Some("focus_follow_plan_missing_rects")
    } else if travel_px.is_some_and(|distance| distance > bounded_max) {
        Some("travel_exceeds_bound")
    } else if execute && reason.is_none() {
        Some("expression_reason_required")
    } else {
        None
    };
    let ready = execute && blocked_reason.is_none();
    let status = match (execute, blocked_reason) {
        (_, Some(_)) => "blocked",
        (false, None) => "dry_run",
        (true, None) => "ready",
    };

    json!({
        "schema": FOCUS_FOLLOW_ACTION_SCHEMA,
        "status": status,
        "ready": ready,
        "default_enabled": false,
        "execute_requested": execute,
        "explicitly_confirmed": confirm,
        "authorization_mode": if confirm { "owner_confirmed_legacy" } else { "agent_reversible_expression" },
        "agent_autonomy_allowed": true,
        "rollback_available": true,
        "automatic_rollback": false,
        "optional_user_permission_layer": "future_product_policy",
        "failure_learning_required": true,
        "reason_present": reason.is_some(),
        "blocked_reason": blocked_reason,
        "movement_scope": "avatar_window_only",
        "moves_pointer": false,
        "changes_focus": false,
        "emits_keyboard_input": false,
        "max_travel_px": bounded_max,
        "travel_px": travel_px,
        "cancel": {
            "sigint": true,
            "cancel_file": cancel_file,
        },
        "state_machine": [
            {"state":"turning", "actions": plan.get("choreography").and_then(Value::as_array).and_then(|items| items.first()).cloned()},
            {"state":"walking", "actions": plan.get("choreography").and_then(Value::as_array).and_then(|items| items.get(1)).cloned()},
            {"state":"arriving", "actions": "arrive_settle"},
            {"state":"acknowledging", "actions": "wave"},
            {"state":"completed", "actions": "idle_breathe"},
        ],
        "runtime_bindings": focus_follow_runtime_bindings(),
        "renderer_override_bound": true,
        "plan": plan,
    })
}
