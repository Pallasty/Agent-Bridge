use ab_bridge::avatar_renderer::{
    renderer_payload_from_sources, renderer_plan_from_state, select_renderer_state, RendererScope,
    RendererSource,
};
use serde_json::json;

fn scope() -> RendererScope {
    RendererScope {
        project: "agent-bridge".to_string(),
        cwd: Some("/Data/CascadeProjects/agent-bridge".to_string()),
    }
}

#[test]
fn projected_avatar_state_wins_over_cross_project_raw_pet_state() {
    let projected = json!({
        "agent_avatar_protocol": 1,
        "project": "agent-bridge",
        "cwd": "/Data/CascadeProjects/agent-bridge",
        "mode": "reviewing",
        "activity_state": "documenting-and-validating"
    });
    let raw_pet = json!({
        "project": "s15-audit",
        "cwd": "/Data/CascadeProjects/biocortex-rs/.claude/worktrees/s15-audit",
        "mode": "handoff",
        "updated_at": "2026-06-01T05:51:29Z"
    });

    let selected = select_renderer_state(&scope(), Some(&projected), Some(&raw_pet));

    assert_eq!(selected.source, RendererSource::ProjectedAvatar);
    assert_eq!(selected.state["mode"], "reviewing");
    assert_eq!(selected.fallback_reason, None);
}

#[test]
fn matching_raw_pet_state_can_be_used_when_projected_state_is_absent() {
    let raw_pet = json!({
        "project": "agent-bridge",
        "cwd": "/Data/CascadeProjects/agent-bridge",
        "mode": "working",
        "activity_state": "implementing",
        "updated_at": "2026-06-01T05:53:20Z"
    });

    let selected = select_renderer_state(&scope(), None, Some(&raw_pet));

    assert_eq!(selected.source, RendererSource::ScopedRawPet);
    assert_eq!(selected.state["mode"], "working");
    assert_eq!(selected.fallback_reason, None);
}

#[test]
fn cross_project_raw_pet_state_falls_back_to_idle() {
    let raw_pet = json!({
        "project": "s15-audit",
        "cwd": "/Data/CascadeProjects/biocortex-rs/.claude/worktrees/s15-audit",
        "mode": "handoff"
    });

    let selected = select_renderer_state(&scope(), None, Some(&raw_pet));

    assert_eq!(selected.source, RendererSource::IdleFallback);
    assert_eq!(selected.state["mode"], "idle");
    assert_eq!(
        selected.fallback_reason.as_deref(),
        Some("raw_pet_scope_mismatch")
    );
}

#[test]
fn renderer_plan_maps_lifecycle_mode_to_calm_track() {
    let state = json!({
        "mode": "verified",
        "activity_state": "documenting",
        "avatar_id": "xiao-shu-v2"
    });

    let plan = renderer_plan_from_state(&state);

    assert_eq!(plan.track, "completion_nod");
    assert_eq!(plan.renderer_token, "xiao_shu::completion_nod::low");
    assert_eq!(plan.fallback_reason, None);
}

#[test]
fn renderer_plan_unknown_mode_uses_idle_fallback() {
    let state = json!({
        "mode": "teleporting",
        "avatar_id": "xiao-shu-v2"
    });

    let plan = renderer_plan_from_state(&state);

    assert_eq!(plan.track, "idle_breathe");
    assert_eq!(plan.renderer_token, "xiao_shu::idle_breathe::low");
    assert_eq!(plan.fallback_reason.as_deref(), Some("unknown_mode"));
}

#[test]
fn renderer_payload_combines_selected_state_and_plan() {
    let projected = json!({
        "agent_avatar_protocol": 1,
        "project": "agent-bridge",
        "cwd": "/Data/CascadeProjects/agent-bridge",
        "mode": "working",
        "avatar_id": "xiao-shu-v2"
    });
    let raw_pet = json!({
        "project": "s15-audit",
        "cwd": "/Data/CascadeProjects/biocortex-rs/.claude/worktrees/s15-audit",
        "mode": "handoff"
    });

    let payload = renderer_payload_from_sources(&scope(), Some(&projected), Some(&raw_pet));

    assert_eq!(payload["surface"], "linux_codex_avatar_renderer_state");
    assert_eq!(payload["read_only"], true);
    assert_eq!(payload["selection"]["source"], "projected_avatar");
    assert_eq!(payload["state"]["mode"], "working");
    assert_eq!(payload["plan"]["track"], "sorting_glow");
    assert_eq!(
        payload["plan"]["renderer_token"],
        "xiao_shu::sorting_glow::medium"
    );
    assert_eq!(payload["safety"]["codex_pet_package_mutation"], false);
    assert_eq!(payload["safety"]["emits_audio"], false);
}
