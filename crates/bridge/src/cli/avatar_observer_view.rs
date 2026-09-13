//! Pure conversion of an already acquired focus plan to observer context.

pub(crate) fn focus_observer_travel_px(plan: &serde_json::Value) -> Option<i64> {
    let from = plan.pointer("/avatar/current_rect")?;
    let to = plan.pointer("/avatar/destination_rect")?;
    Some(
        (to.get("x")?.as_i64()? - from.get("x")?.as_i64()?)
            .abs()
            .max((to.get("y")?.as_i64()? - from.get("y")?.as_i64()?).abs()),
    )
}

pub(crate) fn focus_observer_identity_from_plan(
    plan: &serde_json::Value,
) -> ab_bridge::avatar_focus_observer::FocusTargetIdentity {
    use ab_bridge::avatar_focus_observer::FocusTargetIdentity;

    let value = plan
        .pointer("/target/app_id")
        .and_then(serde_json::Value::as_str)
        .map(str::to_string);
    match (
        plan.pointer("/target/identity_kind")
            .and_then(serde_json::Value::as_str),
        value,
    ) {
        (Some("wayland_app_id"), Some(value)) => FocusTargetIdentity::WaylandAppId(value),
        (Some("xwayland_class"), Some(value)) => FocusTargetIdentity::XwaylandClass(value),
        _ => FocusTargetIdentity::Missing,
    }
}

pub(crate) fn focus_observer_context_from_plan(
    plan: &serde_json::Value,
    observed_at_ms: u64,
    acknowledged_target_node_id: Option<i64>,
    paused: bool,
    action_busy: bool,
) -> ab_bridge::avatar_focus_observer::FocusObserverContext {
    use ab_bridge::avatar_focus_observer::FocusObserverContext;

    let target_node_id = plan
        .pointer("/target/node_id")
        .and_then(serde_json::Value::as_i64);
    let identity = focus_observer_identity_from_plan(plan);
    let status = plan
        .get("status")
        .and_then(serde_json::Value::as_str)
        .unwrap_or("unknown");
    FocusObserverContext {
        observed_at_ms,
        plan_actionable: matches!(status, "planned" | "already_near_focus"),
        target_node_id,
        travel_px: focus_observer_travel_px(plan),
        fullscreen: status == "fullscreen_target"
            || plan
                .pointer("/target/fullscreen")
                .and_then(serde_json::Value::as_bool)
                .unwrap_or(false),
        sensitive_mark: plan
            .pointer("/target/sensitive_mark")
            .and_then(serde_json::Value::as_bool)
            .unwrap_or(false),
        identity,
        acknowledged_target_node_id,
        paused,
        action_busy,
    }
}

pub(crate) fn focus_observer_terminal_context(
    observed_at_ms: u64,
) -> ab_bridge::avatar_focus_observer::FocusObserverContext {
    ab_bridge::avatar_focus_observer::FocusObserverContext {
        observed_at_ms,
        plan_actionable: false,
        target_node_id: None,
        travel_px: None,
        fullscreen: false,
        sensitive_mark: false,
        identity: ab_bridge::avatar_focus_observer::FocusTargetIdentity::Missing,
        acknowledged_target_node_id: None,
        paused: false,
        action_busy: false,
    }
}
