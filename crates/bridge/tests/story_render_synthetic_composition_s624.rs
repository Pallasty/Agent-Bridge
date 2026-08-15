#![cfg(target_os = "linux")]

#[allow(dead_code)]
#[path = "../src/story_render_guardian.rs"]
mod story_render_guardian;
#[allow(dead_code)]
#[path = "../src/story_render_guardian_protocol.rs"]
mod story_render_guardian_protocol;
#[allow(dead_code)]
#[path = "../src/story_render_guardian_supervision.rs"]
mod story_render_guardian_supervision;
#[allow(dead_code)]
#[path = "../src/story_render_supervisor.rs"]
mod story_render_supervisor;
#[path = "../src/story_render_synthetic_composition.rs"]
mod story_render_synthetic_composition;

use std::ffi::OsString;
use std::fs;
use std::path::{Path, PathBuf};
use std::sync::Arc;
use std::time::{Duration, Instant};

use serde_json::{json, Value};
use story_render_supervisor::{StoryRenderSupervisorConfig, StoryRenderSupervisorError};
use story_render_synthetic_composition::{
    run_s622_synthetic_composition, StoryRenderSyntheticCompositionError,
    StoryRenderSyntheticResponse,
};
use tempfile::TempDir;

const REQUEST_ID: &str = "12121212121212121212121212121212";

fn repository_path(relative: &str) -> PathBuf {
    Path::new(env!("CARGO_MANIFEST_DIR"))
        .join("../..")
        .join(relative)
        .canonicalize()
        .expect("canonical repository fixture")
}

fn worker_script() -> PathBuf {
    Path::new(env!("CARGO_MANIFEST_DIR"))
        .join("tests/fixtures/story_render_codec_worker_s624.py")
        .canonicalize()
        .expect("canonical S624 Worker fixture")
}

fn request_value() -> Value {
    json!({
        "protocol": "agent_bridge.story-render-worker.v1",
        "request_id": REQUEST_ID,
        "fixture": {
            "preflight": "fixed_s602_fixture_only",
            "chapter": 2,
            "preflight_sha256": "6553dcec1ad51e1b6352d0fc7fa2068b38713d1e37dedacbe45b00f3aca4a1bb",
            "execution_contract_sha256": "24edc82e885c7f8e5a934019e78530f0d70a482e15ec04c52824395fef1e0fe8"
        },
        "authorization": {
            "authorization_id": "story-render-auth-abababababababababababababababab",
            "contract_sha256": "be4bfc12d9adeda14b8d20048b91baaaf903f155a3fca5bd3413b2b649f7334d",
            "preflight_sha256": "6553dcec1ad51e1b6352d0fc7fa2068b38713d1e37dedacbe45b00f3aca4a1bb",
            "output_directory": format!("/home/pallasting/.agent-bridge-secure/story-render/outputs/{REQUEST_ID}"),
            "action": "render",
            "issued_at": "2026-08-02T12:00:00+00:00",
            "expires_at": "2026-08-02T12:05:00+00:00",
            "single_use_nonce": "cdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcd",
            "issuer": "agent-bridge-owner-console",
            "subject": "story-bounded-render-executor",
            "key_id": "story-render-owner-v1",
            "mac_sha256": "efefefefefefefefefefefefefefefefefefefefefefefefefefefefefefefef"
        }
    })
}

fn request_bytes() -> Vec<u8> {
    serde_json::to_vec(&request_value()).expect("encode S622 request")
}

fn synthetic_config(root: &Path, mode: &str, extra: &[&Path]) -> StoryRenderSupervisorConfig {
    let mut config = StoryRenderSupervisorConfig::s620_synthetic(
        PathBuf::from("/usr/bin/python3"),
        worker_script(),
        root.join("render-worker.lock"),
    );
    config.arguments.extend([
        OsString::from(mode),
        repository_path("scripts/story_render_worker_protocol.py").into_os_string(),
        repository_path(
            "docs/design/voice-scene/s620_story_render_one_shot_worker_protocol_contract.json",
        )
        .into_os_string(),
    ]);
    config
        .arguments
        .extend(extra.iter().map(|path| path.as_os_str().to_owned()));
    config.deadline = Duration::from_secs(2);
    config.termination_grace = Duration::from_millis(50);
    config.response_validator = Arc::new(|_| true);
    config
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

async fn wait_until_not_live(pid: u32) {
    let deadline = Instant::now() + Duration::from_secs(3);
    while process_is_live(pid) && Instant::now() < deadline {
        tokio::time::sleep(Duration::from_millis(10)).await;
    }
    assert!(!process_is_live(pid), "process {pid} remained live");
}

async fn wait_for_pid_file(path: &Path) -> Vec<u32> {
    let deadline = Instant::now() + Duration::from_secs(3);
    loop {
        if let Ok(text) = tokio::fs::read_to_string(path).await {
            let pids: Vec<u32> = text
                .split_whitespace()
                .filter_map(|value| value.parse().ok())
                .collect();
            if pids.len() == 2 {
                return pids;
            }
        }
        assert!(Instant::now() < deadline, "pid fixture was not published");
        tokio::time::sleep(Duration::from_millis(10)).await;
    }
}

async fn retry_after_cleanup(
    root: &Path,
) -> story_render_synthetic_composition::StoryRenderSyntheticResult {
    let deadline = Instant::now() + Duration::from_secs(3);
    loop {
        match run_s622_synthetic_composition(
            synthetic_config(root, "success", &[]),
            REQUEST_ID.to_owned(),
            request_bytes(),
        )
        .await
        {
            Ok(result) => return result,
            Err(StoryRenderSyntheticCompositionError::Supervisor(
                StoryRenderSupervisorError::Busy,
            )) if Instant::now() < deadline => {
                tokio::time::sleep(Duration::from_millis(10)).await;
            }
            Err(error) => panic!("lock did not recover: {error:?}"),
        }
    }
}

#[tokio::test]
async fn real_s622_codec_success_crosses_supervisor_and_returns_typed_result() {
    let root = TempDir::new().expect("temp root");

    let result = run_s622_synthetic_composition(
        synthetic_config(root.path(), "success", &[]),
        REQUEST_ID.to_owned(),
        request_bytes(),
    )
    .await
    .expect("synthetic composition succeeds");

    assert_eq!(result.status_code, Some(0));
    assert_eq!(result.stderr, b"synthetic S622 codec worker\n");
    let StoryRenderSyntheticResponse::Success(success) = result.response else {
        panic!("expected success response")
    };
    assert_eq!(success.request_id, REQUEST_ID);
    assert_eq!(success.render_id, REQUEST_ID);
    assert_eq!(success.segment_count, 3);
    assert_eq!(success.assembly.sha256, "34".repeat(32));
    assert_eq!(success.assembly.sample_rate_hz, 24_000);
    assert_eq!(success.assembly.channels, 1);
    assert_eq!(success.assembly.frames, 72_000);
    assert_eq!(success.assembly.duration_seconds, 3.0);
    assert!(!success.playback_authorized);
    assert!(!success.memory_authorized);
}

#[tokio::test]
async fn contract_defined_worker_error_remains_a_typed_protocol_result() {
    let root = TempDir::new().expect("temp root");

    let result = run_s622_synthetic_composition(
        synthetic_config(root.path(), "worker_error", &[]),
        REQUEST_ID.to_owned(),
        request_bytes(),
    )
    .await
    .expect("valid Worker error is a protocol response");

    let StoryRenderSyntheticResponse::Error(error) = result.response else {
        panic!("expected Worker error response")
    };
    assert_eq!(error.request_id, REQUEST_ID);
    assert_eq!(error.code, "render_failed");
    assert!(!error.retryable);
}

#[tokio::test]
async fn actual_s622_request_rejection_is_returned_without_authority_execution() {
    let root = TempDir::new().expect("temp root");
    let mut request = request_value();
    request["fixture"]["chapter"] = json!(3);

    let result = run_s622_synthetic_composition(
        synthetic_config(root.path(), "success", &[]),
        REQUEST_ID.to_owned(),
        serde_json::to_vec(&request).expect("encode drifted request"),
    )
    .await
    .expect("codec rejection is a valid Worker response");

    assert_eq!(
        result.stderr,
        b"synthetic codec rejection: fixture_binding_mismatch\n"
    );
    let StoryRenderSyntheticResponse::Error(error) = result.response else {
        panic!("expected invalid_request response")
    };
    assert_eq!(error.code, "invalid_request");
    assert!(!error.retryable);
}

#[tokio::test]
async fn rust_boundary_rejects_forged_or_noncanonical_worker_responses() {
    for mode in [
        "mismatched_response",
        "forbidden_response",
        "unknown_error_code",
        "duplicate_response_key",
    ] {
        let root = TempDir::new().expect("temp root");
        let error = run_s622_synthetic_composition(
            synthetic_config(root.path(), mode, &[]),
            REQUEST_ID.to_owned(),
            request_bytes(),
        )
        .await
        .expect_err("forged response must fail closed");

        assert_eq!(
            error,
            StoryRenderSyntheticCompositionError::Supervisor(
                StoryRenderSupervisorError::ResponseRejected
            ),
            "mode={mode}"
        );
    }
}

#[tokio::test]
async fn invalid_binding_identity_rejects_before_lock_or_worker_spawn() {
    let root = TempDir::new().expect("temp root");
    let marker = root.path().join("spawned");
    let config = synthetic_config(root.path(), "mark_success", &[&marker]);

    let error =
        run_s622_synthetic_composition(config.clone(), "NOT-LOWER-HEX".to_owned(), request_bytes())
            .await
            .expect_err("invalid binding must reject");

    assert_eq!(
        error,
        StoryRenderSyntheticCompositionError::InvalidRequestId
    );
    assert!(!config.lock_path.exists());
    assert!(!marker.exists());
}

#[tokio::test]
async fn aborting_composition_propagates_drop_cleanup_to_the_process_group() {
    let root = TempDir::new().expect("temp root");
    let pid_file = root.path().join("descendants.pid");
    let config = synthetic_config(root.path(), "hang_after_decode", &[&pid_file]);
    let task = tokio::spawn(run_s622_synthetic_composition(
        config,
        REQUEST_ID.to_owned(),
        request_bytes(),
    ));
    let pids = wait_for_pid_file(&pid_file).await;
    assert!(pids.iter().all(|pid| process_is_live(*pid)));

    task.abort();
    let join_error = task.await.expect_err("composition task is cancelled");
    assert!(join_error.is_cancelled());
    for pid in pids {
        wait_until_not_live(pid).await;
    }

    let retry = retry_after_cleanup(root.path()).await;
    assert!(matches!(
        retry.response,
        StoryRenderSyntheticResponse::Success(_)
    ));
}

#[test]
fn composition_source_is_private_and_has_no_runtime_authority_or_execution_surface() {
    let source = include_str!("../src/story_render_synthetic_composition.rs");
    for required in [
        "run_s622_synthetic_composition",
        "start_story_render_supervisor",
        "response_validator",
        "deny_unknown_fields",
    ] {
        assert!(
            source.contains(required),
            "missing composition marker: {required}"
        );
    }
    for forbidden in [
        "mcp_tools",
        "story_command_render",
        ".agent-bridge-secure",
        "authority-keys.v1.json",
        "onnxruntime",
        "sounddevice",
        "tokio::process::Command",
    ] {
        assert!(
            !source.contains(forbidden),
            "forbidden S624 surface: {forbidden}"
        );
    }
}

#[test]
fn synthetic_worker_invokes_s622_codec_but_has_no_model_or_key_custody() {
    let source = include_str!("fixtures/story_render_codec_worker_s624.py");
    for required in [
        "codec.decode_request",
        "codec.validate_worker_response",
        "codec.encode_error_response",
    ] {
        assert!(source.contains(required), "missing codec call: {required}");
    }
    for forbidden in [
        "onnxruntime",
        "torch",
        "sounddevice",
        "authority-keys.v1.json",
        "import hmac",
    ] {
        assert!(
            !source.contains(forbidden),
            "forbidden Worker surface: {forbidden}"
        );
    }
}
