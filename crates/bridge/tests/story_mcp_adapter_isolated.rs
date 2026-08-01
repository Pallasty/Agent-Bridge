#[path = "../src/mcp_tools/story.rs"]
mod story;
#[path = "../src/story_contract.rs"]
mod story_contract;

use ab_mcp::McpTool;
use serde_json::json;
use sha2::{Digest, Sha256};
use std::{collections::BTreeMap, path::Path, sync::Arc};
use story::{StoryCommandPreflightTool, StoryMcpConfig, StoryPreflightCancelOnDrop};
use story_contract::{
    run_story_preflight_hardened, StoryPreflightCancellation, StoryRequest, StorySourcePolicy,
    StoryStart,
};

fn file_sha256(path: &Path) -> String {
    let mut digest = Sha256::new();
    digest.update(std::fs::read(path).expect("fixture bytes"));
    format!("{:x}", digest.finalize())
}

fn voice_scene_root() -> std::path::PathBuf {
    Path::new("../../docs/design/voice-scene")
        .canonicalize()
        .expect("voice scene root")
}

fn complete_values() -> BTreeMap<String, String> {
    let root = voice_scene_root();
    let mut values = BTreeMap::new();
    values.insert("AB_STORY_COMMAND_PREFLIGHT_ENABLE".into(), "1".into());
    values.insert("AB_STORY_SOURCE_ROOT".into(), root.display().to_string());
    values.insert("AB_STORY_SOURCE_MAX_BYTES".into(), "1048576".into());
    values.insert("AB_STORY_EVIDENCE_ROOT".into(), root.display().to_string());
    for (prefix, name) in [
        (
            "VOICE_PLAN",
            "s5zc_source_grounded_utterance_plan_receipt.json",
        ),
        ("MAPPING", "s5x_story_voice_mapping_receipt.json"),
        (
            "ROLE_ACCEPTANCE",
            "s5y_character_voice_audition_receipt.json",
        ),
        ("CONTINUITY", "s5ze_cross_chapter_continuity_receipt.json"),
    ] {
        let path = root.join(name);
        values.insert(
            format!("AB_STORY_{prefix}_PATH"),
            path.display().to_string(),
        );
        values.insert(format!("AB_STORY_{prefix}_SHA256"), file_sha256(&path));
    }
    values
}

#[test]
fn disabled_adapter_needs_no_file_configuration() {
    assert!(StoryMcpConfig::from_values(&BTreeMap::new())
        .expect("disabled config")
        .is_none());
}

#[test]
fn enabled_adapter_requires_complete_configuration() {
    let values = BTreeMap::from([(
        "AB_STORY_COMMAND_PREFLIGHT_ENABLE".to_string(),
        "1".to_string(),
    )]);
    let error = StoryMcpConfig::from_values(&values)
        .unwrap_err()
        .to_string();

    assert!(error.contains("AB_STORY_SOURCE_ROOT"));
    assert!(error.contains("AB_STORY_CONTINUITY_SHA256"));
}

#[test]
fn complete_configuration_builds_hidden_adapter() {
    let config = StoryMcpConfig::from_values(&complete_values())
        .expect("valid config")
        .expect("enabled");
    let tool = StoryCommandPreflightTool::new(config);

    assert_eq!(tool.name(), "story_command_preflight");
    assert_eq!(tool.schema().input_schema["additionalProperties"], false);
    assert_eq!(
        tool.annotations().expect("annotations").read_only_hint,
        true
    );
}

#[tokio::test]
async fn adapter_preserves_s5zf_preflight_and_structured_result() {
    let root = voice_scene_root();
    let config = StoryMcpConfig::from_values(&complete_values())
        .unwrap()
        .unwrap();
    let result = StoryCommandPreflightTool::new(config)
        .execute_value(json!({
            "source_path": root.join("fixtures/story_s1.md"),
            "start": {"kind": "chapter", "chapter": 2},
            "dry_run": true
        }))
        .await;

    assert!(!result.is_error);
    let value = result.structured_content.expect("structured result");
    assert_eq!(
        value["preflight_sha256"],
        "6553dcec1ad51e1b6352d0fc7fa2068b38713d1e37dedacbe45b00f3aca4a1bb"
    );
    assert!(value["execution_authorized"] == false);
    assert!(value["runtime_effects"]
        .as_object()
        .unwrap()
        .values()
        .all(|item| item == false));
}

#[tokio::test]
async fn adapter_returns_tool_errors_for_unknown_fields_and_non_dry_run() {
    let config = StoryMcpConfig::from_values(&complete_values())
        .unwrap()
        .unwrap();
    let tool = StoryCommandPreflightTool::new(config);
    for args in [
        json!({"source_path": "book.md", "start": {"kind": "from_start"}, "dry_run": true, "play": true}),
        json!({"source_path": "book.md", "start": {"kind": "from_start"}, "dry_run": false}),
    ] {
        assert!(tool.execute_value(args).await.is_error);
    }
}

#[tokio::test]
async fn drop_guard_turns_future_drop_into_preflight_cancellation() {
    let root = voice_scene_root();
    let cancellation = Arc::new(StoryPreflightCancellation::new());
    drop(StoryPreflightCancelOnDrop::new(Arc::clone(&cancellation)));
    let config = StoryMcpConfig::from_values(&complete_values())
        .unwrap()
        .unwrap();
    let error = run_story_preflight_hardened(
        "/story cancelled",
        StoryRequest {
            source_path: root.join("fixtures/story_s1.md").display().to_string(),
            start: StoryStart::FromStart,
            dry_run: true,
        },
        StorySourcePolicy {
            allowed_root: config.source_policy.allowed_root.clone(),
            max_bytes: config.source_policy.max_bytes,
        },
        config.evidence,
        cancellation,
    )
    .await
    .unwrap_err();

    assert!(error.to_string().contains("cancelled"));
}

#[test]
fn invalid_hash_and_byte_limit_fail_before_exposure() {
    let mut bad_hash = complete_values();
    bad_hash.insert("AB_STORY_MAPPING_SHA256".into(), "not-a-hash".into());
    assert!(StoryMcpConfig::from_values(&bad_hash).is_err());

    let mut bad_limit = complete_values();
    bad_limit.insert("AB_STORY_SOURCE_MAX_BYTES".into(), "0".into());
    assert!(StoryMcpConfig::from_values(&bad_limit).is_err());
}
