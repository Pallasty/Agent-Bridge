use ab_bridge::avatar_focus_follow::{
    focus_follow_plan_from_sway_tree, FocusFollowOptions, FOCUS_FOLLOW_SCHEMA,
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
    assert_eq!(plan["action_registry"]["concept_only"], true);
    assert_eq!(plan["action_registry"]["production_alpha_ready"], false);
    assert_eq!(plan["action_registry"]["runtime_bound"], false);
    assert_eq!(plan["action_registry"]["actions"][5], "wave");
    assert_eq!(plan["target"]["workspace"], "2");
    assert!(plan["path"]["point_count"].as_u64().unwrap() <= 32);
    assert_eq!(plan["choreography"][2], "arrive_settle");
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
