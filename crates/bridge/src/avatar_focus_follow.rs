//! Read-only focus-follow planning for the Linux desktop Avatar.
//!
//! This module consumes an already captured Sway tree and proposes a bounded
//! path for the Avatar window. It never invokes Sway, moves a window, changes
//! focus, or controls the pointer.

use serde::{Deserialize, Serialize};
use serde_json::{json, Value};

pub const FOCUS_FOLLOW_SCHEMA: &str = "agent_bridge.avatar_focus_follow_plan.v1";
pub const DEFAULT_AVATAR_APP_ID: &str = "agent-bridge-avatar";
pub const FOCUS_FOLLOW_ACTIONS: [&str; 6] = [
    "turn_left",
    "turn_right",
    "walk_left",
    "walk_right",
    "arrive_settle",
    "wave",
];

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
    title: Option<String>,
    node_id: Option<i64>,
    workspace: Option<String>,
    workspace_rect: FocusRect,
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
            title: value
                .get("name")
                .and_then(Value::as_str)
                .map(str::to_string),
            node_id: value.get("id").and_then(Value::as_i64),
            workspace: None,
            workspace_rect: rect,
        });
    }
    child_values(value).find_map(|child| find_avatar(child, app_id))
}

fn find_focused_target(
    value: &Value,
    avatar_app_id: &str,
    workspace: Option<(&str, FocusRect)>,
) -> Option<WindowRef> {
    let next_workspace = if value.get("type").and_then(Value::as_str) == Some("workspace") {
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
        if let Some(found) = find_focused_target(child, avatar_app_id, next_workspace) {
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
        app_id: value
            .get("app_id")
            .and_then(Value::as_str)
            .map(str::to_string),
        title: value
            .get("name")
            .and_then(Value::as_str)
            .map(str::to_string),
        node_id: value.get("id").and_then(Value::as_i64),
        workspace: Some(workspace_name.to_string()),
        workspace_rect,
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
            "concept_only": true,
            "production_alpha_ready": false,
            "runtime_bound": false,
        },
    })
}

pub fn focus_follow_plan_from_sway_tree(tree: &Value, opts: &FocusFollowOptions) -> Value {
    let Some(avatar) = find_avatar(tree, &opts.avatar_app_id) else {
        let mut plan = base_plan("avatar_not_found");
        plan["recommended_action"] = json!("start_or_restore_avatar_then_replan");
        return plan;
    };
    let Some(target) = find_focused_target(tree, &opts.avatar_app_id, None) else {
        let mut plan = base_plan("focus_target_not_found");
        plan["avatar"] = json!({"app_id": avatar.app_id, "rect": avatar.rect});
        plan["recommended_action"] = json!("focus_a_non_avatar_window_then_replan");
        return plan;
    };

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
        plan["avatar"] = json!({"app_id": avatar.app_id, "rect": avatar.rect});
        plan["target"] = json!({"rect": target.rect, "workspace": target.workspace});
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
        "app_id": opts.avatar_app_id,
        "current_rect": avatar.rect,
        "destination_rect": destination,
    });
    plan["target"] = json!({
        "node_id": target.node_id,
        "app_id": target.app_id,
        "title": target.title,
        "rect": target.rect,
        "workspace": target.workspace,
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
