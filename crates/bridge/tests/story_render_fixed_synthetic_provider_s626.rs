#![cfg(target_os = "linux")]

#[path = "../src/story_render_fixed_synthetic_provider.rs"]
mod story_render_fixed_synthetic_provider;
#[allow(dead_code)]
#[path = "../src/story_render_supervisor.rs"]
mod story_render_supervisor;
#[path = "../src/story_render_synthetic_admission.rs"]
mod story_render_synthetic_admission;
#[path = "../src/story_render_synthetic_composition.rs"]
mod story_render_synthetic_composition;

use std::ffi::OsString;
use std::fs;
use std::path::{Path, PathBuf};
use std::time::{Duration, Instant};

use serde_json::Value;
use story_render_fixed_synthetic_provider::StoryRenderFixedSyntheticProvider;
use story_render_supervisor::{
    begin_story_render_admission, start_story_render_supervisor, StoryRenderSupervisorConfig,
    StoryRenderSupervisorError,
};
use story_render_synthetic_admission::{
    run_s625_synthetic_admission, StoryRenderSyntheticAdmissionError,
    StoryRenderSyntheticAdmissionProvider,
};
use story_render_synthetic_composition::StoryRenderSyntheticResponse;
use tempfile::TempDir;

fn repository_path(relative: &str) -> PathBuf {
    Path::new(env!("CARGO_MANIFEST_DIR"))
        .join("../..")
        .join(relative)
        .canonicalize()
        .expect("canonical repository fixture")
}

fn codec_worker_script() -> PathBuf {
    Path::new(env!("CARGO_MANIFEST_DIR"))
        .join("tests/fixtures/story_render_codec_worker_s624.py")
        .canonicalize()
        .expect("canonical S624 Worker fixture")
}

fn lifecycle_worker_script() -> PathBuf {
    Path::new(env!("CARGO_MANIFEST_DIR"))
        .join("tests/fixtures/story_render_worker_s623.py")
        .canonicalize()
        .expect("canonical S623 Worker fixture")
}

fn codec_config(root: &Path) -> StoryRenderSupervisorConfig {
    let mut config = StoryRenderSupervisorConfig::s620_synthetic(
        PathBuf::from("/usr/bin/python3"),
        codec_worker_script(),
        root.join("render-worker.lock"),
    );
    config.arguments.extend([
        OsString::from("success"),
        repository_path("scripts/story_render_worker_protocol.py").into_os_string(),
        repository_path(
            "docs/design/voice-scene/s620_story_render_one_shot_worker_protocol_contract.json",
        )
        .into_os_string(),
    ]);
    config.deadline = Duration::from_secs(2);
    config.termination_grace = Duration::from_millis(50);
    config
}

fn lifecycle_config(root: &Path, pid_file: &Path) -> StoryRenderSupervisorConfig {
    let mut config = StoryRenderSupervisorConfig::s620_synthetic(
        PathBuf::from("/usr/bin/python3"),
        lifecycle_worker_script(),
        root.join("render-worker.lock"),
    );
    config
        .arguments
        .extend([OsString::from("hang"), pid_file.as_os_str().to_owned()]);
    config.deadline = Duration::from_secs(2);
    config.termination_grace = Duration::from_millis(50);
    config
}

fn close_request(provider: &mut StoryRenderFixedSyntheticProvider) -> (String, Vec<u8>) {
    let request_id = provider
        .generate_request_id()
        .expect("fixed request identity");
    let grant = provider
        .issue_grant(&request_id)
        .expect("one fixed synthetic grant");
    let request = provider
        .build_request(&request_id, grant)
        .expect("fixed request construction");
    (request_id, request)
}

fn request_value(raw: &[u8]) -> Value {
    serde_json::from_slice(raw).expect("fixed request JSON")
}

fn is_lower_hex(value: &str, length: usize) -> bool {
    value.len() == length
        && value
            .bytes()
            .all(|byte| byte.is_ascii_digit() || (b'a'..=b'f').contains(&byte))
}

fn process_is_live(pid: u32) -> bool {
    let Ok(stat) = fs::read_to_string(format!("/proc/{pid}/stat")) else {
        return false;
    };
    let Some(after_name) = stat.rsplit_once(") ").map(|(_, rest)| rest) else {
        return true;
    };
    after_name.chars().next() != Some('Z')
}

async fn wait_for_pid_file(path: &Path) -> u32 {
    let deadline = Instant::now() + Duration::from_secs(3);
    loop {
        if let Ok(text) = tokio::fs::read_to_string(path).await {
            if let Ok(pid) = text.trim().parse() {
                return pid;
            }
        }
        assert!(Instant::now() < deadline, "pid fixture was not published");
        tokio::time::sleep(Duration::from_millis(10)).await;
    }
}

async fn wait_until_not_live(pid: u32) {
    let deadline = Instant::now() + Duration::from_secs(3);
    while process_is_live(pid) && Instant::now() < deadline {
        tokio::time::sleep(Duration::from_millis(10)).await;
    }
    assert!(!process_is_live(pid), "process {pid} remained live");
}

async fn wait_until_lock_available(config: StoryRenderSupervisorConfig) {
    let deadline = Instant::now() + Duration::from_secs(3);
    loop {
        match begin_story_render_admission(config.clone()) {
            Ok(admission) => {
                drop(admission);
                return;
            }
            Err(StoryRenderSupervisorError::Busy) if Instant::now() < deadline => {
                tokio::time::sleep(Duration::from_millis(10)).await;
            }
            Err(error) => panic!("host lock did not recover: {error:?}"),
        }
    }
}

#[test]
fn equal_sequences_keep_identity_deterministic_but_replay_is_denied() {
    let mut first = StoryRenderFixedSyntheticProvider::new(7);
    let mut second = StoryRenderFixedSyntheticProvider::new(7);

    let (first_id, first_request) = close_request(&mut first);
    let second_id = second
        .generate_request_id()
        .expect("second deterministic identity");

    assert_eq!(first_id, second_id);
    assert!(second.issue_grant(&second_id).is_none());
    assert!(is_lower_hex(&first_id, 32));
    let value = request_value(&first_request);
    assert_eq!(value["request_id"], first_id);
    assert_eq!(
        value["authorization"]["output_directory"],
        format!("/home/pallasting/.agent-bridge-secure/story-render/outputs/{first_id}")
    );
    assert_eq!(
        value["authorization"]["key_id"],
        "story-render-synthetic-structure-only-no-key-v1"
    );
    assert_eq!(value["authorization"]["issued_at"], "2026-08-02T12:00:00Z");
    assert_eq!(value["authorization"]["expires_at"], "2026-08-02T12:05:00Z");
    assert!(value.get("key_material").is_none());
}

#[test]
fn distinct_sequences_domain_separate_identity_nonce_and_placeholder() {
    let mut first = StoryRenderFixedSyntheticProvider::new(10);
    let mut second = StoryRenderFixedSyntheticProvider::new(11);
    let (first_id, first_request) = close_request(&mut first);
    let (second_id, second_request) = close_request(&mut second);
    let first = request_value(&first_request);
    let second = request_value(&second_request);

    assert_ne!(first_id, second_id);
    assert_ne!(
        first["authorization"]["single_use_nonce"],
        second["authorization"]["single_use_nonce"]
    );
    assert_ne!(
        first["authorization"]["mac_sha256"],
        second["authorization"]["mac_sha256"]
    );
    for value in [
        first["authorization"]["single_use_nonce"]
            .as_str()
            .expect("nonce string"),
        first["authorization"]["mac_sha256"]
            .as_str()
            .expect("placeholder string"),
    ] {
        assert!(is_lower_hex(value, 64));
    }
}

#[test]
fn wrong_identity_does_not_consume_but_grant_is_single_use() {
    let mut provider = StoryRenderFixedSyntheticProvider::new(21);
    let request_id = provider
        .generate_request_id()
        .expect("fixed request identity");

    assert!(provider.issue_grant(&"0".repeat(32)).is_none());
    let grant = provider
        .issue_grant(&request_id)
        .expect("correct identity receives grant");
    assert!(provider.issue_grant(&request_id).is_none());
    assert!(provider.build_request(&request_id, grant).is_some());
    assert!(provider.issue_grant(&request_id).is_none());
}

#[tokio::test]
async fn fixed_provider_crosses_s625_and_actual_s622_codec() {
    let root = TempDir::new().expect("temp root");
    let mut provider = StoryRenderFixedSyntheticProvider::new(31);
    let expected_request_id = provider
        .generate_request_id()
        .expect("fixed request identity");

    let result = run_s625_synthetic_admission(codec_config(root.path()), &mut provider)
        .await
        .expect("fixed synthetic provider crosses real codec");

    let StoryRenderSyntheticResponse::Success(success) = result.response else {
        panic!("expected synthetic success");
    };
    assert_eq!(success.request_id, expected_request_id);
    assert_eq!(success.render_id, expected_request_id);
    assert_eq!(success.segment_count, 3);
    assert!(!success.playback_authorized);
    assert!(!success.memory_authorized);
}

#[tokio::test]
async fn busy_host_rejects_without_consuming_fixed_grant() {
    let root = TempDir::new().expect("temp root");
    let pid_file = root.path().join("first.pid");
    let first = start_story_render_supervisor(
        lifecycle_config(root.path(), &pid_file),
        br#"{"synthetic":"s626-busy"}"#.to_vec(),
    )
    .expect("start first Worker");
    let pid = wait_for_pid_file(&pid_file).await;
    let mut provider = StoryRenderFixedSyntheticProvider::new(41);

    let error = run_s625_synthetic_admission(codec_config(root.path()), &mut provider)
        .await
        .expect_err("busy host rejects fixed provider");
    assert_eq!(
        error,
        StoryRenderSyntheticAdmissionError::Supervisor(StoryRenderSupervisorError::Busy)
    );

    drop(first);
    wait_until_not_live(pid).await;
    wait_until_lock_available(codec_config(root.path())).await;
    run_s625_synthetic_admission(codec_config(root.path()), &mut provider)
        .await
        .expect("same untouched provider succeeds after host release");
}

#[tokio::test]
async fn post_grant_spawn_failure_requires_a_fresh_provider_sequence() {
    let root = TempDir::new().expect("temp root");
    let mut invalid_config = codec_config(root.path());
    invalid_config.executable = PathBuf::from("/s626/missing/python3");
    let mut consumed = StoryRenderFixedSyntheticProvider::new(51);

    let error = run_s625_synthetic_admission(invalid_config, &mut consumed)
        .await
        .expect_err("spawn failure consumes the synthetic grant");
    assert_eq!(
        error,
        StoryRenderSyntheticAdmissionError::Supervisor(StoryRenderSupervisorError::SpawnFailed)
    );

    let error = run_s625_synthetic_admission(codec_config(root.path()), &mut consumed)
        .await
        .expect_err("consumed provider cannot issue a second grant");
    assert_eq!(error, StoryRenderSyntheticAdmissionError::GrantDeclined);

    let mut fresh = StoryRenderFixedSyntheticProvider::new(52);
    run_s625_synthetic_admission(codec_config(root.path()), &mut fresh)
        .await
        .expect("fresh deterministic sequence can retry");
}

#[test]
fn source_is_dormant_structural_and_contains_no_real_custody_surface() {
    let source = include_str!("../src/story_render_fixed_synthetic_provider.rs");
    for required in [
        "StoryRenderFixedSyntheticProvider",
        "StoryRenderSyntheticAdmissionProvider",
        "single_use_nonce",
        "synthetic-structure-only-no-key",
        "agent-bridge.story-render-synthetic-request.v1",
        "agent-bridge.story-render-synthetic-nonce.v1",
        "agent-bridge.story-render-synthetic-placeholder.v1",
    ] {
        assert!(source.contains(required), "missing S626 marker: {required}");
    }
    for forbidden in [
        "mcp_tools",
        "story_command_render",
        "authority-keys.v1.json",
        "std::fs",
        "OpenOptions",
        "tokio::",
        "process::Command",
        "rand::",
        "Uuid",
        "Hmac",
        "onnxruntime",
        "sounddevice",
    ] {
        assert!(
            !source.contains(forbidden),
            "forbidden S626 surface: {forbidden}"
        );
    }
}
