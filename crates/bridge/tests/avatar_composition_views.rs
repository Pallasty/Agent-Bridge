#[allow(dead_code)]
#[path = "../src/cli/avatar_live_view.rs"]
mod live;
#[allow(dead_code)]
#[path = "../src/cli/avatar_observer_view.rs"]
mod observer;

use serde_json::json;

#[test]
fn completed_linux_live_receipt_preserves_failures_and_observation_limits() {
    let receipt = live::linux_live_receipt(
        1250,
        &json!({"session_id": "fixture-session"}),
        3,
        1,
        &Some("fixture heartbeat failure".to_string()),
        &json!({"project": "fixture-project"}),
        &json!({"fixture_renderer": true}),
        &json!({"utterance_count": 1}),
        &json!({"sidecar_read_failures": 2}),
        &json!({"safety": {"controls_desktop": false}}),
    );
    assert_eq!(
        receipt,
        json!({
            "surface": "linux_avatar_live_receipt", "schema": 1,
            "dry_run": false, "completed": true, "elapsed_ms": 1250,
            "presence": {"session_id": "fixture-session", "heartbeat_count": 3,
                "heartbeat_failures": 1, "last_error": "fixture heartbeat failure",
                "last_projection": {"project": "fixture-project"}},
            "renderer": {"completed": true, "launch_plan": {"fixture_renderer": true},
                "dynamic_state_source": "pet_state_sidecar", "dynamic_state_polling_ran": true,
                "final_visual_state_observed": false,
                "reason": "the native surface completed and polled the sidecar, but this foreground receipt does not capture compositor pixels or infer the final visible sprite"},
            "voice_feedback": {"utterance_count": 1}, "observation": {"sidecar_read_failures": 2},
            "safety": {"controls_desktop": false}
        })
    );
}

#[test]
fn completed_voice_receipt_preserves_actual_audio_and_ownership_evidence() {
    assert_eq!(
        live::voice_observer_receipt(
            "fixture-pet",
            2500,
            &json!({"utterance_count": 0, "adapter_error": "fixture failure"}),
            &json!({"ownership": {"presence": false}, "safety": {"initial_state_silent": true}})
        ),
        json!({"surface": "linux_avatar_voice_observer_receipt", "schema": 1,
            "dry_run": false, "completed": true, "pet_id": "fixture-pet", "elapsed_ms": 2500,
            "voice_feedback": {"utterance_count": 0, "adapter_error": "fixture failure"},
            "ownership": {"presence": false}, "safety": {"initial_state_silent": true}})
    );
    let empty = live::voice_observer_receipt("fixture", 0, &json!({}), &json!({}));
    assert!(empty["ownership"].is_null());
    assert!(empty["safety"].is_null());
}

#[test]
fn observer_projection_keeps_missing_identity_and_terminal_context_fail_closed() {
    let missing = observer::focus_observer_context_from_plan(&json!({}), 123, None, true, true);
    assert!(!missing.plan_actionable);
    assert!(missing.identity.is_missing());
    assert_eq!(missing.travel_px, None);
    assert!(missing.paused && missing.action_busy);
    let terminal = observer::focus_observer_terminal_context(456);
    assert_eq!(terminal.observed_at_ms, 456);
    assert!(!terminal.plan_actionable);
    assert!(terminal.identity.is_missing());
    assert_eq!(terminal.target_node_id, None);
}

#[test]
fn observer_projection_preserves_identity_geometry_and_fullscreen_signals() {
    let context = observer::focus_observer_context_from_plan(
        &json!({
            "status": "fullscreen_target",
            "target": {"node_id": 41, "identity_kind": "xwayland_class", "app_id": "Editor",
                "sensitive_mark": true},
            "avatar": {"current_rect": {"x": 100, "y": 150},
                "destination_rect": {"x": 10, "y": 30}}
        }),
        123,
        Some(41),
        false,
        false,
    );
    assert!(context.fullscreen && context.sensitive_mark);
    assert!(!context.plan_actionable);
    assert_eq!(context.target_node_id, Some(41));
    assert_eq!(context.acknowledged_target_node_id, Some(41));
    assert_eq!(context.travel_px, Some(120));
    assert_eq!(
        context.identity,
        ab_bridge::avatar_focus_observer::FocusTargetIdentity::XwaylandClass("Editor".to_string())
    );
}

#[test]
fn live_plan_requires_compiled_native_backend_and_ready_voice_plan() {
    use ab_bridge::avatar_floater::{AvatarBackend, BackendRecommendation};
    for compiled in [false, true] {
        for native in [false, true] {
            for voice_ready in [false, true] {
                let backend = BackendRecommendation {
                    backend: if native {
                        AvatarBackend::NativeTransparent
                    } else {
                        AvatarBackend::BrowserDegraded
                    },
                    transparency_available: native,
                    reason: "fixture recommendation".to_string(),
                };
                let plan = live::linux_live_plan(
                    compiled,
                    &backend,
                    &json!({"session_id": "fixture"}),
                    5,
                    &json!({}),
                    &json!({"ready": voice_ready}),
                    100,
                    true,
                );
                assert_eq!(plan["ready"], compiled && native && voice_ready);
                assert_eq!(plan["safety"]["emits_audio"], true);
                assert_eq!(plan["safety"]["writes_presence_only"], false);
                assert_eq!(plan["safety"]["persistent_writes_presence_only"], true);
                assert_eq!(plan["safety"]["controls_desktop"], false);
                assert_eq!(plan["presence"]["heartbeat_interval_secs"], 5);
                assert!(plan["presence"]["project"].is_null());
            }
        }
    }
}
