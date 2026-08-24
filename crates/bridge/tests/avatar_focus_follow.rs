use ab_bridge::avatar_focus_follow::{
    acknowledged_target_from_receipt, focus_follow_action_preflight,
    focus_follow_arrival_failure_reason, focus_follow_outcome_record,
    focus_follow_plan_from_sway_tree, focus_follow_prompt_preflight, focus_follow_recommendation,
    focus_follow_runtime_bindings, sway_command_succeeded, FocusFollowOptions,
    FOCUS_FOLLOW_ACK_SCHEMA, FOCUS_FOLLOW_ACTION_SCHEMA, FOCUS_FOLLOW_OUTCOME_SCHEMA,
    FOCUS_FOLLOW_PROMPT_SCHEMA, FOCUS_FOLLOW_RECOMMEND_SCHEMA, FOCUS_FOLLOW_SCHEMA,
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
fn acknowledgement_receipt_only_accepts_completed_current_schema() {
    let completed = json!({
        "schema": FOCUS_FOLLOW_ACK_SCHEMA,
        "status": "completed",
        "target_node_id": 41
    });
    assert_eq!(acknowledged_target_from_receipt(&completed), Some(41));
    assert_eq!(
        acknowledged_target_from_receipt(&json!({
            "schema": FOCUS_FOLLOW_ACK_SCHEMA,
            "status": "cancelled",
            "target_node_id": 41
        })),
        None
    );
    assert_eq!(
        acknowledged_target_from_receipt(&json!({
            "schema": "agent_bridge.avatar_focus_follow_ack.v0",
            "status": "completed",
            "target_node_id": 41
        })),
        None
    );
}

#[test]
fn sway_command_receipt_requires_nonempty_all_success_array() {
    assert!(sway_command_succeeded(br#"[{"success":true}]"#));
    assert!(!sway_command_succeeded(
        br#"[{"success":true},{"success":false,"error":"no match"}]"#
    ));
    assert!(!sway_command_succeeded(br#"[]"#));
    assert!(!sway_command_succeeded(b"not-json"));
}

#[test]
fn arrival_verification_binds_target_avatar_and_position() {
    let mut observed =
        focus_follow_plan_from_sway_tree(&sway_tree(), &FocusFollowOptions::default());
    let destination = observed["avatar"]["destination_rect"].clone();
    observed["avatar"]["current_rect"] = destination.clone();
    let x = destination["x"].as_i64().unwrap();
    let y = destination["y"].as_i64().unwrap();
    assert_eq!(
        focus_follow_arrival_failure_reason(&observed, 41, 99, x, y),
        None
    );

    let mut wrong_target = observed.clone();
    wrong_target["target"]["node_id"] = json!(42);
    assert_eq!(
        focus_follow_arrival_failure_reason(&wrong_target, 41, 99, x, y),
        Some("focus_target_changed_at_arrival")
    );
    let mut wrong_avatar = observed.clone();
    wrong_avatar["avatar"]["node_id"] = json!(100);
    assert_eq!(
        focus_follow_arrival_failure_reason(&wrong_avatar, 41, 99, x, y),
        Some("avatar_identity_changed_at_arrival")
    );
    observed["avatar"]["current_rect"]["x"] = json!(x + 9);
    assert_eq!(
        focus_follow_arrival_failure_reason(&observed, 41, 99, x, y),
        Some("arrival_postcondition_mismatch")
    );
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
    assert_eq!(plan["avatar"]["node_id"], 99);
    assert_eq!(plan["target"]["workspace"], "2");
    assert!(plan["path"]["point_count"].as_u64().unwrap() <= 32);
    assert_eq!(plan["choreography"][2], "arrive_settle");
}

#[test]
fn focus_follow_action_treats_confirmation_as_optional_legacy_metadata() {
    let plan = focus_follow_plan_from_sway_tree(&sway_tree(), &FocusFollowOptions::default());
    let dry_run = focus_follow_action_preflight(&plan, false, false, None, 900, None);
    assert_eq!(dry_run["schema"], FOCUS_FOLLOW_ACTION_SCHEMA);
    assert_eq!(dry_run["status"], "dry_run");
    assert_eq!(dry_run["ready"], false);

    let autonomous = focus_follow_action_preflight(
        &plan,
        true,
        false,
        Some("agent attention expression"),
        900,
        None,
    );
    assert_eq!(autonomous["status"], "ready");
    assert_eq!(autonomous["ready"], true);
    assert_eq!(
        autonomous["authorization_mode"],
        "agent_reversible_expression"
    );
    assert_eq!(autonomous["agent_autonomy_allowed"], true);
    assert_eq!(autonomous["rollback_available"], true);
    assert_eq!(autonomous["automatic_rollback"], false);

    let no_reason = focus_follow_action_preflight(&plan, true, true, None, 900, None);
    assert_eq!(no_reason["blocked_reason"], "expression_reason_required");

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
fn focus_follow_outcomes_make_cancelled_attempts_negative_learning_signals() {
    let plan = focus_follow_plan_from_sway_tree(&sway_tree(), &FocusFollowOptions::default());
    let mut action =
        focus_follow_action_preflight(&plan, true, false, Some("agent expression"), 900, None);
    action["status"] = json!("cancelled");
    action["executed_steps"] = json!(3);
    action["stopped_reason"] = json!("focus_target_changed");
    let outcome = focus_follow_outcome_record(&action, "final", 1234);
    assert_eq!(outcome["schema"], FOCUS_FOLLOW_OUTCOME_SCHEMA);
    assert_eq!(outcome["outcome_class"], "negative");
    assert_eq!(outcome["negative_learning_candidate"], true);
    assert_eq!(outcome["requires_lesson_on_rollback"], true);
    assert_eq!(outcome["authorization_mode"], "agent_reversible_expression");
    assert_eq!(outcome["target_node_id"], 41);
    assert_eq!(outcome["moves_pointer"], false);
    assert!(!outcome.to_string().contains("Editor"));
}

#[test]
fn focus_follow_recommendation_is_read_only_and_change_sensitive() {
    let plan = focus_follow_plan_from_sway_tree(&sway_tree(), &FocusFollowOptions::default());
    let recommendation = focus_follow_recommendation(&plan, Some(7), 96);

    assert_eq!(recommendation["schema"], FOCUS_FOLLOW_RECOMMEND_SCHEMA);
    assert_eq!(recommendation["decision"], "recommend_move");
    assert_eq!(
        recommendation["reason"],
        "new_focus_target_outside_threshold"
    );
    assert_eq!(recommendation["read_only"], true);
    assert_eq!(recommendation["writes_state"], false);
    assert_eq!(recommendation["moves_avatar"], false);
    assert!(recommendation["dispatch"].is_null());
    assert_eq!(
        recommendation["requires_explicit_action_confirmation"],
        false
    );
    assert_eq!(recommendation["requires_agent_expression_decision"], true);
    assert_eq!(
        recommendation["recommended_command"],
        "agent-bridge avatar focus-follow-action --execute --reason <reason>"
    );

    let unchanged = focus_follow_recommendation(&plan, Some(41), 96);
    assert_eq!(unchanged["decision"], "stay");
    assert_eq!(unchanged["reason"], "target_unchanged");
    assert_eq!(unchanged["requires_explicit_action_confirmation"], false);
}

#[test]
fn focus_follow_recommendation_suppresses_non_actionable_plan() {
    let mut tree = sway_tree();
    tree["nodes"][0]["nodes"][0]["floating_nodes"] = json!([]);
    let plan = focus_follow_plan_from_sway_tree(&tree, &FocusFollowOptions::default());
    let recommendation = focus_follow_recommendation(&plan, None, 96);

    assert_eq!(recommendation["decision"], "suppress");
    assert_eq!(recommendation["reason"], "plan_not_actionable");
    assert_eq!(recommendation["moves_pointer"], false);
    assert_eq!(recommendation["changes_focus"], false);
}

#[test]
fn focus_follow_prompt_requires_recommendation_but_not_owner_confirmation() {
    let plan = focus_follow_plan_from_sway_tree(&sway_tree(), &FocusFollowOptions::default());
    let recommendation = focus_follow_recommendation(&plan, Some(7), 96);

    let preview = focus_follow_prompt_preflight(&recommendation, false, false, false, 8_000);
    assert_eq!(preview["schema"], FOCUS_FOLLOW_PROMPT_SCHEMA);
    assert_eq!(preview["status"], "dry_run");
    assert_eq!(preview["emits_audio"], false);
    assert_eq!(preview["moves_avatar"], false);
    assert_eq!(preview["executes_recommendation"], false);

    let autonomous = focus_follow_prompt_preflight(&recommendation, true, false, false, 8_000);
    assert_eq!(autonomous["status"], "ready");
    assert_eq!(
        autonomous["authorization_mode"],
        "agent_reversible_expression"
    );
    assert_eq!(autonomous["agent_autonomy_allowed"], true);
    assert_eq!(autonomous["requires_separate_movement_confirmation"], false);

    let ready = focus_follow_prompt_preflight(&recommendation, true, true, false, 8_000);
    assert_eq!(ready["status"], "ready");
    assert_eq!(ready["ready"], true);
    assert_eq!(ready["presentation"]["kind"], "avatar_anchored_bubble");
    assert_eq!(ready["presentation"]["text"], "我过去看看。");
    assert_eq!(ready["presentation"]["anchor"], "above_avatar");
    assert_eq!(
        ready["presentation"]["fallback"],
        "desktop_notification_bubble"
    );

    let cooling = focus_follow_prompt_preflight(&recommendation, true, true, true, 8_000);
    assert_eq!(cooling["status"], "suppressed");
    assert_eq!(cooling["blocked_reason"], "cooldown_active");
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
