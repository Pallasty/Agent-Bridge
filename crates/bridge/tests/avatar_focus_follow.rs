use ab_bridge::avatar_focus_follow::{
    focus_follow_action_preflight, focus_follow_plan_from_sway_tree, focus_follow_runtime_bindings,
    FocusFollowOptions, FOCUS_FOLLOW_ACTION_SCHEMA, FOCUS_FOLLOW_SCHEMA,
};
use serde_json::json;

fn sway_tree() -> serde_json::Value {
    json!({
        "type": "root",
        "rect": {"x":0,"y":0,"width":1920,"height":1080},
        "nodes": [{
            "type":"output",
            "rect":{"x":0,"y":0,"width":1920,"height":1080},
            "nodes":[{
                "type":"workspace",
                "name":"2",
                "rect":{"x":0,"y":0,"width":1920,"height":1040},
                "nodes":[{
                    "id":41,
                    "type":"con",
                    "app_id":"com.example.Editor",
                    "name":"Editor",
                    "focused":true,
                    "rect":{"x":120,"y":80,"width":1200,"height":820}
                }],
                "floating_nodes":[{
                    "id":99,
                    "type":"floating_con",
                    "app_id":"agent-bridge-avatar",
                    "name":"Xiao Shu",
                    "focused":false,
                    "rect":{"x":1700,"y":850,"width":90,"height":130}
                }]
            }]
        }]
    })
}

#[test]
fn focus_follow_plan_is_bounded_read_only_and_pointer_safe() {
    let plan = focus_follow_plan_from_sway_tree(&sway_tree(), &FocusFollowOptions::default());

    assert_eq!(plan["schema"], FOCUS_FOLLOW_SCHEMA);
    assert_eq!(plan["status"], "planned");
    assert_eq!(plan["read_only"], true);
    assert_eq!(plan["default_enabled"], false);
    assert_eq!(plan["movement_authorized"], false);
    assert_eq!(plan["controls_desktop"], false);
    assert_eq!(plan["moves_pointer"], false);
    assert_eq!(plan["changes_focus"], false);
    assert!(plan["dispatch"].is_null());
    assert_eq!(plan["action_registry"]["concept_only"], false);
    assert_eq!(
        plan["action_registry"]["runtime_baseline_alpha_ready"],
        true
    );
    assert_eq!(
        plan["action_registry"]["dedicated_walk_atlases_ready"],
        true
    );
    assert_eq!(
        plan["action_registry"]["dedicated_turn_atlases_ready"],
        true
    );
    assert_eq!(plan["action_registry"]["runtime_bound"], true);
    assert_eq!(plan["action_registry"]["actions"][5], "wave");
    assert_eq!(plan["target"]["workspace"], "2");
    assert!(plan["path"]["point_count"].as_u64().unwrap() <= 32);
    assert_eq!(plan["choreography"][2], "arrive_settle");
}

#[test]
fn focus_follow_action_requires_execute_confirm_and_reason() {
    let plan = focus_follow_plan_from_sway_tree(&sway_tree(), &FocusFollowOptions::default());
    let dry_run = focus_follow_action_preflight(&plan, false, false, None, 900, None);
    assert_eq!(dry_run["schema"], FOCUS_FOLLOW_ACTION_SCHEMA);
    assert_eq!(dry_run["status"], "dry_run");
    assert_eq!(dry_run["ready"], false);

    let no_confirm =
        focus_follow_action_preflight(&plan, true, false, Some("owner requested"), 900, None);
    assert_eq!(
        no_confirm["blocked_reason"],
        "explicit_confirmation_required"
    );

    let no_reason = focus_follow_action_preflight(&plan, true, true, None, 900, None);
    assert_eq!(no_reason["blocked_reason"], "operator_reason_required");

    let ready = focus_follow_action_preflight(
        &plan,
        true,
        true,
        Some("owner requested focus move"),
        900,
        Some("/tmp/cancel"),
    );
    assert_eq!(ready["status"], "ready");
    assert_eq!(ready["ready"], true);
    assert_eq!(ready["moves_pointer"], false);
    assert_eq!(ready["changes_focus"], false);
    assert_eq!(ready["renderer_override_bound"], true);
    assert_eq!(ready["state_machine"][3]["state"], "acknowledging");
    assert_eq!(ready["state_machine"][3]["actions"], "wave");
}

#[test]
fn runtime_bindings_are_alpha_ready_including_dedicated_wave() {
    let bindings = focus_follow_runtime_bindings();
    for action in [
        "turn_left",
        "turn_right",
        "walk_left",
        "walk_right",
        "arrive_settle",
        "wave",
    ] {
        let asset = bindings[action]["asset"].as_str().unwrap();
        let sprite = ab_bridge::avatar_native::decode_sidecar_sprite_asset(asset).unwrap();
        assert!(sprite.rgba.chunks_exact(4).any(|pixel| pixel[3] == 0));
        assert!(sprite.rgba.chunks_exact(4).any(|pixel| pixel[3] > 0));
        assert_eq!(bindings[action]["alpha_ready"], true);
    }
    assert_eq!(bindings["wave"]["asset"], "xiao-shu-v3-focus-wave-v1");
    assert_eq!(bindings["wave"]["dedicated_motion"], true);
    assert_eq!(
        bindings["turn_left"]["asset"],
        "xiao-shu-v3-focus-turn-left-v1"
    );
    assert_eq!(
        bindings["turn_right"]["asset"],
        "xiao-shu-v3-focus-turn-right-v1"
    );
    assert_eq!(bindings["turn_left"]["dedicated_motion"], true);
    assert_eq!(bindings["turn_right"]["dedicated_motion"], true);
    assert_eq!(
        bindings["walk_left"]["asset"],
        "xiao-shu-v3-focus-walk-left-v1"
    );
    assert_eq!(
        bindings["walk_right"]["asset"],
        "xiao-shu-v3-focus-walk-right-v1"
    );
    assert_eq!(bindings["walk_left"]["dedicated_motion"], true);
    assert_eq!(bindings["walk_right"]["dedicated_motion"], true);
}

#[test]
fn native_motion_override_decodes_bound_asset() {
    let path = std::env::temp_dir().join(format!(
        "ab-avatar-motion-override-test-{}.json",
        std::process::id()
    ));
    std::fs::write(
        &path,
        serde_json::to_vec(&json!({
            "schema": ab_bridge::avatar_native::NATIVE_MOTION_OVERRIDE_SCHEMA,
            "expires_at_unix_ms": u64::MAX,
            "state": {"mode": "working"},
            "plan": {
                "asset_route": "/avatar-surface/sidecar-spritesheet?asset=xiao-shu-v3-ai-soft-bounce-v1"
            }
        }))
        .unwrap(),
    )
    .unwrap();
    let plan = ab_bridge::avatar_native::native_motion_override_plan(&path)
        .unwrap()
        .unwrap();
    std::fs::remove_file(&path).unwrap();
    assert_eq!(plan.mode, "working");
    assert_eq!(plan.asset.as_deref(), Some("xiao-shu-v3-ai-soft-bounce-v1"));
    assert_eq!(plan.frame_count, 6);
}

#[test]
fn expired_native_motion_override_fails_closed() {
    let path = std::env::temp_dir().join(format!(
        "ab-avatar-motion-override-expired-test-{}.json",
        std::process::id()
    ));
    std::fs::write(
        &path,
        serde_json::to_vec(&json!({
            "schema": ab_bridge::avatar_native::NATIVE_MOTION_OVERRIDE_SCHEMA,
            "expires_at_unix_ms": 1,
            "state": {"mode": "working"},
            "plan": {
                "asset_route": "/avatar-surface/sidecar-spritesheet?asset=xiao-shu-v3-ai-soft-bounce-v1"
            }
        }))
        .unwrap(),
    )
    .unwrap();
    let plan = ab_bridge::avatar_native::native_motion_override_plan(&path).unwrap();
    std::fs::remove_file(&path).unwrap();
    assert!(plan.is_none());
}

#[test]
fn focus_follow_plan_fails_closed_without_avatar() {
    let mut tree = sway_tree();
    tree["nodes"][0]["nodes"][0]["floating_nodes"] = json!([]);

    let plan = focus_follow_plan_from_sway_tree(&tree, &FocusFollowOptions::default());

    assert_eq!(plan["status"], "avatar_not_found");
    assert_eq!(plan["movement_authorized"], false);
    assert!(plan["dispatch"].is_null());
}

#[test]
fn focus_follow_plan_does_not_follow_itself() {
    let mut tree = sway_tree();
    tree["nodes"][0]["nodes"][0]["nodes"][0]["focused"] = json!(false);
    tree["nodes"][0]["nodes"][0]["floating_nodes"][0]["focused"] = json!(true);

    let plan = focus_follow_plan_from_sway_tree(&tree, &FocusFollowOptions::default());

    assert_eq!(plan["status"], "focus_target_not_found");
    assert_eq!(plan["moves_pointer"], false);
}
