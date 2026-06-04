use ab_bridge::avatar_renderer::{
    renderer_payload_from_sources, renderer_plan_from_state, select_renderer_state,
    validate_aura_io_manifest, validate_aura_io_sidecar_path, RendererScope, RendererSource,
};
use serde_json::json;
use sha2::{Digest, Sha256};
use std::error::Error;
use std::fs;
use std::path::{Path, PathBuf};
use std::time::{SystemTime, UNIX_EPOCH};

fn scope() -> RendererScope {
    RendererScope {
        project: "agent-bridge".to_string(),
        cwd: Some("/Data/CascadeProjects/agent-bridge".to_string()),
    }
}

fn unique_temp_dir(name: &str) -> Result<PathBuf, Box<dyn Error>> {
    let nanos = SystemTime::now().duration_since(UNIX_EPOCH)?.as_nanos();
    let path = std::env::temp_dir().join(format!(
        "agent-bridge-avatar-renderer-{name}-{}-{nanos}",
        std::process::id()
    ));
    fs::create_dir_all(&path)?;
    Ok(path)
}

fn sha256_hex(bytes: &[u8]) -> String {
    let mut hasher = Sha256::new();
    hasher.update(bytes);
    format!("{:x}", hasher.finalize())
}

fn write_valid_aura_io_fixture(dir: &Path) -> Result<PathBuf, Box<dyn Error>> {
    let uniform_path = dir.join("a2_working_uniform.bin");
    let digest_path = dir.join("a2_working_digest.json");
    let aura_io_path = dir.join("a2_working_aura_io.json");
    let uniform_bytes = vec![7_u8; 1024];
    let digest_bytes = br#"{"items":[{"title":"working"}]}"#;
    fs::write(&uniform_path, &uniform_bytes)?;
    fs::write(&digest_path, digest_bytes)?;
    let aura_io = json!({
        "schema_version": "lcc.aura_io.v1",
        "renderer_input": {
            "kind": "tfe_uniform_f32x256",
            "contract_version": 1,
            "path": uniform_path,
            "sha256": format!("sha256:{}", sha256_hex(&uniform_bytes)),
            "uniform_len": 256,
            "bin_bytes": 1024,
            "encoding": "little_endian_f32"
        },
        "source_digest": {
            "schema_version": "1.0",
            "item_count": 1,
            "json_path": digest_path,
            "json_sha256": format!("sha256:{}", sha256_hex(digest_bytes))
        },
        "visible_signal_source": "curated_digest_only",
        "shadow_signal_policy": "shadow_only_until_falsified",
        "source_state": {
            "mode": "working",
            "activity_state": "a2-preflight",
            "focus": "face-aura",
            "risk_level": "low"
        }
    });
    fs::write(&aura_io_path, serde_json::to_vec_pretty(&aura_io)?)?;
    Ok(aura_io_path)
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

#[test]
fn aura_io_sidecar_validates_renderer_input_hashes() -> Result<(), Box<dyn Error>> {
    let dir = unique_temp_dir("valid-aura-io")?;
    let aura_io_path = write_valid_aura_io_fixture(&dir)?;

    let report = validate_aura_io_sidecar_path(&aura_io_path, true)?;

    assert_eq!(report["ok"], true);
    assert_eq!(report["schema_version"], "lcc.aura_io.v1");
    assert_eq!(report["renderer_input_kind"], "tfe_uniform_f32x256");
    assert_eq!(report["uniform_len"], 256);
    assert_eq!(report["bin_bytes"], 1024);
    assert_eq!(report["uniform_file_sha256_matches"], true);
    assert_eq!(report["digest_file_sha256_matches"], true);
    assert_eq!(report["visible_signal_source"], "curated_digest_only");
    assert_eq!(
        report["shadow_signal_policy"],
        "shadow_only_until_falsified"
    );

    fs::remove_dir_all(dir)?;
    Ok(())
}

#[test]
fn aura_io_manifest_rejects_shadow_driven_visible_source() -> Result<(), Box<dyn Error>> {
    let dir = unique_temp_dir("shadow-aura-io")?;
    let aura_io_path = write_valid_aura_io_fixture(&dir)?;
    let mut aura_io: serde_json::Value = serde_json::from_slice(&fs::read(&aura_io_path)?)?;
    aura_io["visible_signal_source"] = json!("biocortex_state");

    let err = validate_aura_io_manifest(&aura_io, false).unwrap_err();

    assert!(err.to_string().contains("visible_signal_source"));
    fs::remove_dir_all(dir)?;
    Ok(())
}
