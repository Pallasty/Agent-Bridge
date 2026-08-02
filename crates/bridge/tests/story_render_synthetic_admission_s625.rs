#![cfg(target_os = "linux")]

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
use std::sync::Arc;
use std::time::{Duration, Instant};

use serde_json::{json, Value};
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

const REQUEST_ID: &str = "12121212121212121212121212121212";

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

fn codec_config(root: &Path, mode: &str, extra: &[&Path]) -> StoryRenderSupervisorConfig {
    let mut config = StoryRenderSupervisorConfig::s620_synthetic(
        PathBuf::from("/usr/bin/python3"),
        codec_worker_script(),
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

fn lifecycle_config(root: &Path, mode: &str, extra: &[&Path]) -> StoryRenderSupervisorConfig {
    let mut config = StoryRenderSupervisorConfig::s620_synthetic(
        PathBuf::from("/usr/bin/python3"),
        lifecycle_worker_script(),
        root.join("render-worker.lock"),
    );
    config.arguments.push(OsString::from(mode));
    config
        .arguments
        .extend(extra.iter().map(|path| path.as_os_str().to_owned()));
    config.deadline = Duration::from_secs(2);
    config.termination_grace = Duration::from_millis(50);
    config
}

fn authorization(request_id: &str) -> Value {
    json!({
        "authorization_id": "story-render-auth-abababababababababababababababab",
        "contract_sha256": "be4bfc12d9adeda14b8d20048b91baaaf903f155a3fca5bd3413b2b649f7334d",
        "preflight_sha256": "6553dcec1ad51e1b6352d0fc7fa2068b38713d1e37dedacbe45b00f3aca4a1bb",
        "output_directory": format!("/home/pallasting/.agent-bridge-secure/story-render/outputs/{request_id}"),
        "action": "render",
        "issued_at": "2026-08-02T12:00:00+00:00",
        "expires_at": "2026-08-02T12:05:00+00:00",
        "single_use_nonce": "cdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcd",
        "issuer": "agent-bridge-owner-console",
        "subject": "story-bounded-render-executor",
        "key_id": "story-render-owner-v1",
        "mac_sha256": "efefefefefefefefefefefefefefefefefefefefefefefefefefefefefefefef"
    })
}

fn request_bytes(request_id: &str, grant: Value) -> Vec<u8> {
    serde_json::to_vec(&json!({
        "protocol": "agent_bridge.story-render-worker.v1",
        "request_id": request_id,
        "fixture": {
            "preflight": "fixed_s602_fixture_only",
            "chapter": 2,
            "preflight_sha256": "6553dcec1ad51e1b6352d0fc7fa2068b38713d1e37dedacbe45b00f3aca4a1bb",
            "execution_contract_sha256": "24edc82e885c7f8e5a934019e78530f0d70a482e15ec04c52824395fef1e0fe8"
        },
        "authorization": grant
    }))
    .expect("encode fixed S622 request")
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
enum DeclineAt {
    Identity,
    Grant,
    Request,
}

struct RecordingProvider {
    probe_config: StoryRenderSupervisorConfig,
    worker_marker: PathBuf,
    events: Vec<&'static str>,
    decline_at: Option<DeclineAt>,
    invalid_identity: bool,
    oversized_request: bool,
}

impl RecordingProvider {
    fn new(probe_config: StoryRenderSupervisorConfig, worker_marker: PathBuf) -> Self {
        Self {
            probe_config,
            worker_marker,
            events: Vec::new(),
            decline_at: None,
            invalid_identity: false,
            oversized_request: false,
        }
    }

    fn observe_stage(&mut self, stage: &'static str) {
        self.events.push(stage);
        assert!(
            !self.worker_marker.exists(),
            "Worker spawned before {stage} completed"
        );
        let error = match begin_story_render_admission(self.probe_config.clone()) {
            Ok(admission) => {
                drop(admission);
                panic!("host lock was not held during {stage}")
            }
            Err(error) => error,
        };
        assert_eq!(error, StoryRenderSupervisorError::Busy, "stage={stage}");
    }
}

impl StoryRenderSyntheticAdmissionProvider for RecordingProvider {
    type Grant = Value;

    fn generate_request_id(&mut self) -> Option<String> {
        self.observe_stage("identity");
        if self.decline_at == Some(DeclineAt::Identity) {
            return None;
        }
        if self.invalid_identity {
            Some("NOT-LOWER-HEX".to_owned())
        } else {
            Some(REQUEST_ID.to_owned())
        }
    }

    fn issue_grant(&mut self, request_id: &str) -> Option<Self::Grant> {
        self.observe_stage("grant");
        (self.decline_at != Some(DeclineAt::Grant)).then(|| authorization(request_id))
    }

    fn build_request(&mut self, request_id: &str, grant: Self::Grant) -> Option<Vec<u8>> {
        self.observe_stage("request");
        if self.decline_at == Some(DeclineAt::Request) {
            return None;
        }
        if self.oversized_request {
            Some(vec![b'x'; 65_537])
        } else {
            Some(request_bytes(request_id, grant))
        }
    }
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

async fn wait_for_pid_file(path: &Path, count: usize) -> Vec<u32> {
    let deadline = Instant::now() + Duration::from_secs(3);
    loop {
        if let Ok(text) = tokio::fs::read_to_string(path).await {
            let pids: Vec<u32> = text
                .split_whitespace()
                .filter_map(|value| value.parse().ok())
                .collect();
            if pids.len() == count {
                return pids;
            }
        }
        assert!(Instant::now() < deadline, "pid fixture was not published");
        tokio::time::sleep(Duration::from_millis(10)).await;
    }
}

fn assert_lock_released(config: StoryRenderSupervisorConfig) {
    let admission = begin_story_render_admission(config).expect("host lock released");
    drop(admission);
}

async fn retry_lock_released(config: StoryRenderSupervisorConfig) {
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

#[tokio::test]
async fn lock_precedes_identity_grant_request_and_worker_spawn() {
    let root = TempDir::new().expect("temp root");
    let marker = root.path().join("worker-spawned");
    let config = codec_config(root.path(), "mark_success", &[&marker]);
    let mut provider = RecordingProvider::new(config.clone(), marker.clone());

    let result = run_s625_synthetic_admission(config, &mut provider)
        .await
        .expect("ordered synthetic admission succeeds");

    assert_eq!(provider.events, ["identity", "grant", "request"]);
    assert!(marker.exists());
    assert!(matches!(
        result.response,
        StoryRenderSyntheticResponse::Success(_)
    ));
}

#[tokio::test]
async fn busy_host_rejects_before_any_provider_stage_or_second_spawn() {
    let root = TempDir::new().expect("temp root");
    let first_pid_file = root.path().join("first.pid");
    let marker = root.path().join("second-spawned");
    let first = start_story_render_supervisor(
        lifecycle_config(root.path(), "hang", &[&first_pid_file]),
        br#"{"synthetic":"s625-busy"}"#.to_vec(),
    )
    .expect("start first Worker");
    wait_for_pid_file(&first_pid_file, 1).await;
    let config = codec_config(root.path(), "mark_success", &[&marker]);
    let mut provider = RecordingProvider::new(config.clone(), marker.clone());

    let error = run_s625_synthetic_admission(config.clone(), &mut provider)
        .await
        .expect_err("busy host rejects admission");

    assert_eq!(
        error,
        StoryRenderSyntheticAdmissionError::Supervisor(StoryRenderSupervisorError::Busy)
    );
    assert!(provider.events.is_empty());
    assert!(!marker.exists());
    let pid = first.worker_pid();
    drop(first);
    wait_until_not_live(pid).await;
    retry_lock_released(config).await;
}

#[tokio::test]
async fn provider_declines_fail_closed_release_lock_and_never_spawn() {
    for (stage, expected_events, expected_error) in [
        (
            DeclineAt::Identity,
            vec!["identity"],
            StoryRenderSyntheticAdmissionError::IdentityRejected,
        ),
        (
            DeclineAt::Grant,
            vec!["identity", "grant"],
            StoryRenderSyntheticAdmissionError::GrantDeclined,
        ),
        (
            DeclineAt::Request,
            vec!["identity", "grant", "request"],
            StoryRenderSyntheticAdmissionError::RequestBuildRejected,
        ),
    ] {
        let root = TempDir::new().expect("temp root");
        let marker = root.path().join("spawned");
        let config = codec_config(root.path(), "mark_success", &[&marker]);
        let mut provider = RecordingProvider::new(config.clone(), marker.clone());
        provider.decline_at = Some(stage);

        let error = run_s625_synthetic_admission(config.clone(), &mut provider)
            .await
            .expect_err("provider rejection fails closed");

        assert_eq!(error, expected_error, "stage={stage:?}");
        assert_eq!(provider.events, expected_events, "stage={stage:?}");
        assert!(!marker.exists());
        assert_lock_released(config);
    }
}

#[tokio::test]
async fn invalid_identity_stops_before_grant_and_releases_lock() {
    let root = TempDir::new().expect("temp root");
    let marker = root.path().join("spawned");
    let config = codec_config(root.path(), "mark_success", &[&marker]);
    let mut provider = RecordingProvider::new(config.clone(), marker.clone());
    provider.invalid_identity = true;

    let error = run_s625_synthetic_admission(config.clone(), &mut provider)
        .await
        .expect_err("invalid identity fails closed");

    assert_eq!(error, StoryRenderSyntheticAdmissionError::InvalidRequestId);
    assert_eq!(provider.events, ["identity"]);
    assert!(!marker.exists());
    assert_lock_released(config);
}

#[tokio::test]
async fn oversized_built_request_releases_lock_without_spawn() {
    let root = TempDir::new().expect("temp root");
    let marker = root.path().join("spawned");
    let config = codec_config(root.path(), "mark_success", &[&marker]);
    let mut provider = RecordingProvider::new(config.clone(), marker.clone());
    provider.oversized_request = true;

    let error = run_s625_synthetic_admission(config.clone(), &mut provider)
        .await
        .expect_err("oversized request fails closed");

    assert_eq!(
        error,
        StoryRenderSyntheticAdmissionError::Supervisor(StoryRenderSupervisorError::InputTooLarge)
    );
    assert_eq!(provider.events, ["identity", "grant", "request"]);
    assert!(!marker.exists());
    assert_lock_released(config);
}

#[tokio::test]
async fn spawn_failure_discards_admission_and_fresh_provider_can_retry() {
    let root = TempDir::new().expect("temp root");
    let marker = root.path().join("spawned");
    let mut invalid = codec_config(root.path(), "mark_success", &[&marker]);
    invalid.executable = PathBuf::from("/s625/missing/python3");
    let mut first_provider = RecordingProvider::new(invalid.clone(), marker.clone());

    let error = run_s625_synthetic_admission(invalid, &mut first_provider)
        .await
        .expect_err("spawn failure fails closed");

    assert_eq!(
        error,
        StoryRenderSyntheticAdmissionError::Supervisor(StoryRenderSupervisorError::SpawnFailed)
    );
    assert_eq!(first_provider.events, ["identity", "grant", "request"]);
    assert!(!marker.exists());

    let valid = codec_config(root.path(), "mark_success", &[&marker]);
    let mut fresh_provider = RecordingProvider::new(valid.clone(), marker.clone());
    run_s625_synthetic_admission(valid, &mut fresh_provider)
        .await
        .expect("fresh admission retries successfully");
    assert_eq!(fresh_provider.events, ["identity", "grant", "request"]);
    assert!(marker.exists());
}

#[tokio::test]
async fn cancellation_after_spawn_reaps_group_and_eventually_releases_admission() {
    let root = TempDir::new().expect("temp root");
    let pid_file = root.path().join("descendants.pid");
    let marker = root.path().join("not-a-worker-marker");
    let config = codec_config(root.path(), "hang_after_decode", &[&pid_file]);
    let retry_config = codec_config(root.path(), "success", &[]);
    let mut provider = RecordingProvider::new(config.clone(), marker);
    let task =
        tokio::spawn(async move { run_s625_synthetic_admission(config, &mut provider).await });
    let pids = wait_for_pid_file(&pid_file, 2).await;
    assert!(pids.iter().all(|pid| process_is_live(*pid)));

    task.abort();
    assert!(task.await.expect_err("task cancelled").is_cancelled());
    for pid in pids {
        wait_until_not_live(pid).await;
    }
    retry_lock_released(retry_config).await;
}

#[test]
fn source_keeps_s625_synthetic_private_and_runtime_free() {
    let source = include_str!("../src/story_render_synthetic_admission.rs");
    for required in [
        "begin_story_render_admission",
        "generate_request_id",
        "issue_grant",
        "build_request",
        "bind_response_validator",
    ] {
        assert!(source.contains(required), "missing S625 marker: {required}");
    }
    for forbidden in [
        "mcp_tools",
        "story_command_render",
        ".agent-bridge-secure",
        "authority-keys.v1.json",
        "hmac",
        "onnxruntime",
        "sounddevice",
        "tokio::process::Command",
    ] {
        assert!(
            !source.contains(forbidden),
            "forbidden S625 surface: {forbidden}"
        );
    }
}
