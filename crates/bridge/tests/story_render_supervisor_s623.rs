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

use std::collections::BTreeMap;
use std::ffi::OsString;
use std::fs;
use std::os::unix::fs::PermissionsExt;
use std::path::{Path, PathBuf};
use std::time::{Duration, Instant};

use story_render_supervisor::{
    start_story_render_supervisor, StoryRenderSupervisorConfig, StoryRenderSupervisorError,
};
use tempfile::TempDir;

const REQUEST: &[u8] = br#"{"protocol":"synthetic-s623"}"#;

fn python_executable() -> PathBuf {
    let path = PathBuf::from("/usr/bin/python3");
    assert!(
        path.is_file(),
        "S623 synthetic tests require /usr/bin/python3"
    );
    path
}

fn fixture_script() -> PathBuf {
    Path::new(env!("CARGO_MANIFEST_DIR"))
        .join("tests/fixtures/story_render_worker_s623.py")
        .canonicalize()
        .expect("canonical synthetic worker fixture")
}

fn synthetic_config(root: &Path, mode: &str, extra: &[&Path]) -> StoryRenderSupervisorConfig {
    let mut config = StoryRenderSupervisorConfig::s620_synthetic(
        python_executable(),
        fixture_script(),
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

fn error_from_start(
    result: Result<story_render_supervisor::StoryRenderRun, StoryRenderSupervisorError>,
) -> StoryRenderSupervisorError {
    match result {
        Err(error) => error,
        Ok(run) => {
            drop(run);
            panic!("supervisor unexpectedly started")
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
            let values: Vec<u32> = text
                .split_whitespace()
                .filter_map(|value| value.parse().ok())
                .collect();
            if values.len() == count {
                return values;
            }
        }
        assert!(Instant::now() < deadline, "pid fixture was not published");
        tokio::time::sleep(Duration::from_millis(10)).await;
    }
}

async fn retry_after_cleanup(config: StoryRenderSupervisorConfig) {
    let deadline = Instant::now() + Duration::from_secs(3);
    loop {
        match start_story_render_supervisor(config.clone(), REQUEST.to_vec()).await {
            Ok(run) => {
                run.await.expect("retry after cleanup succeeds");
                return;
            }
            Err(StoryRenderSupervisorError::Busy) if Instant::now() < deadline => {
                tokio::time::sleep(Duration::from_millis(10)).await;
            }
            Err(error) => panic!("lock did not recover: {error:?}"),
        }
    }
}

#[test]
fn s620_defaults_are_fixed_and_environment_is_allowlisted() {
    let root = TempDir::new().expect("temp root");
    let config = StoryRenderSupervisorConfig::s620_synthetic(
        python_executable(),
        fixture_script(),
        root.path().join("render-worker.lock"),
    );

    assert_eq!(config.stdin_max_bytes, 65_536);
    assert_eq!(config.stdout_max_bytes, 65_536);
    assert_eq!(config.stderr_max_bytes, 16_384);
    assert_eq!(config.deadline, Duration::from_secs(300));
    assert_eq!(config.termination_grace, Duration::from_secs(2));
    assert_eq!(
        config.environment,
        BTreeMap::from([
            ("CUDA_VISIBLE_DEVICES".into(), "".into()),
            ("HF_HUB_OFFLINE".into(), "1".into()),
            ("HIP_VISIBLE_DEVICES".into(), "".into()),
            ("LANG".into(), "C.UTF-8".into()),
            ("LC_ALL".into(), "C.UTF-8".into()),
            ("PYTHONDONTWRITEBYTECODE".into(), "1".into()),
            ("PYTHONNOUSERSITE".into(), "1".into()),
            ("ROCR_VISIBLE_DEVICES".into(), "".into()),
            ("TRANSFORMERS_OFFLINE".into(), "1".into()),
            ("TZ".into(), "UTC".into()),
        ])
    );
}

#[test]
fn start_outside_tokio_runtime_rejects_before_lock_or_spawn() {
    let root = TempDir::new().expect("temp root");
    let marker = root.path().join("spawned");
    let config = synthetic_config(root.path(), "mark_success", &[&marker]);

    let error = error_from_start(futures::executor::block_on(start_story_render_supervisor(
        config.clone(),
        REQUEST.to_vec(),
    )));

    assert_eq!(error, StoryRenderSupervisorError::InvalidConfiguration);
    assert!(!config.lock_path.exists());
    assert!(!marker.exists());
}

#[tokio::test]
async fn success_drains_both_pipes_reaps_worker_and_releases_lock() {
    let root = TempDir::new().expect("temp root");
    let config = synthetic_config(root.path(), "success", &[]);
    let run = start_story_render_supervisor(config.clone(), REQUEST.to_vec())
        .await
        .expect("start synthetic worker");
    let pid = run.worker_pid();

    let output = run.await.expect("synthetic success");

    assert_eq!(output.status_code, Some(0));
    assert_eq!(output.stdout, br#"{"status":"synthetic-success"}"#);
    assert_eq!(output.stderr, b"synthetic diagnostic\n");
    wait_until_not_live(pid).await;
    let mode = fs::metadata(&config.lock_path)
        .expect("lock metadata")
        .permissions()
        .mode()
        & 0o777;
    assert_eq!(mode, 0o600);
    retry_after_cleanup(config).await;
}

#[tokio::test]
async fn busy_lock_rejects_without_queue_or_second_spawn() {
    let root = TempDir::new().expect("temp root");
    let first_pid_file = root.path().join("first.pid");
    let marker = root.path().join("second-spawned");
    let first = start_story_render_supervisor(
        synthetic_config(root.path(), "hang", &[&first_pid_file]),
        REQUEST.to_vec(),
    )
    .await
    .expect("start first worker");
    wait_for_pid_file(&first_pid_file, 1).await;

    let error = error_from_start(
        start_story_render_supervisor(
            synthetic_config(root.path(), "mark_success", &[&marker]),
            REQUEST.to_vec(),
        )
        .await,
    );

    assert_eq!(error, StoryRenderSupervisorError::Busy);
    tokio::time::sleep(Duration::from_millis(50)).await;
    assert!(!marker.exists(), "busy request must not spawn a worker");
    let pid = first.worker_pid();
    drop(first);
    wait_until_not_live(pid).await;
}

#[tokio::test]
async fn oversized_input_rejects_before_lock_creation_or_spawn() {
    let root = TempDir::new().expect("temp root");
    let marker = root.path().join("spawned");
    let config = synthetic_config(root.path(), "mark_success", &[&marker]);

    let error = error_from_start(
        start_story_render_supervisor(config.clone(), vec![b'x'; config.stdin_max_bytes + 1]).await,
    );

    assert_eq!(error, StoryRenderSupervisorError::InputTooLarge);
    assert!(!config.lock_path.exists());
    assert!(!marker.exists());
}

#[tokio::test]
async fn spawn_failure_releases_lock_for_a_fresh_attempt() {
    let root = TempDir::new().expect("temp root");
    let mut invalid = synthetic_config(root.path(), "success", &[]);
    invalid.executable = PathBuf::from("/s623/missing/python3");

    let error = error_from_start(start_story_render_supervisor(invalid, REQUEST.to_vec()).await);

    assert_eq!(error, StoryRenderSupervisorError::SpawnFailed);
    retry_after_cleanup(synthetic_config(root.path(), "success", &[])).await;
}

async fn assert_worker_failure(mode: &str, expected: StoryRenderSupervisorError) {
    let root = TempDir::new().expect("temp root");
    let config = synthetic_config(root.path(), mode, &[]);
    let run = start_story_render_supervisor(config.clone(), REQUEST.to_vec())
        .await
        .expect("start failure fixture");
    let pid = run.worker_pid();

    let error = run.await.expect_err("fixture must fail closed");

    assert_eq!(error, expected);
    wait_until_not_live(pid).await;
    retry_after_cleanup(synthetic_config(root.path(), "success", &[])).await;
}

#[tokio::test]
async fn empty_and_malformed_worker_responses_fail_closed() {
    assert_worker_failure(
        "no_response",
        StoryRenderSupervisorError::WorkerExitWithoutResponse,
    )
    .await;
    assert_worker_failure(
        "malformed_output",
        StoryRenderSupervisorError::ResponseRejected,
    )
    .await;
}

#[tokio::test]
async fn stdout_overflow_terminates_and_reaps_worker() {
    assert_worker_failure(
        "stdout_overflow",
        StoryRenderSupervisorError::StdoutLimitExceeded,
    )
    .await;
}

#[tokio::test]
async fn stderr_overflow_terminates_and_reaps_worker() {
    assert_worker_failure(
        "stderr_overflow",
        StoryRenderSupervisorError::StderrLimitExceeded,
    )
    .await;
}

#[tokio::test]
async fn deadline_terminates_reaps_and_releases_lock() {
    let root = TempDir::new().expect("temp root");
    let pid_file = root.path().join("deadline.pid");
    let mut config = synthetic_config(root.path(), "hang", &[&pid_file]);
    config.deadline = Duration::from_millis(100);
    let run = start_story_render_supervisor(config.clone(), REQUEST.to_vec())
        .await
        .expect("start hanging fixture");
    let pid = run.worker_pid();
    wait_for_pid_file(&pid_file, 1).await;

    let error = run.await.expect_err("deadline must fail closed");

    assert_eq!(error, StoryRenderSupervisorError::DeadlineExceeded);
    wait_until_not_live(pid).await;
    retry_after_cleanup(synthetic_config(root.path(), "success", &[])).await;
}

#[tokio::test]
async fn dropping_future_kills_term_ignoring_process_group_and_recovers_lock() {
    let root = TempDir::new().expect("temp root");
    let pid_file = root.path().join("descendants.pid");
    let config = synthetic_config(root.path(), "term_ignoring_descendant", &[&pid_file]);
    let run = start_story_render_supervisor(config.clone(), REQUEST.to_vec())
        .await
        .expect("start descendant fixture");
    let reported = wait_for_pid_file(&pid_file, 2).await;
    assert_eq!(reported[0], run.worker_pid());
    assert!(reported.iter().all(|pid| process_is_live(*pid)));

    drop(run);

    for pid in reported {
        wait_until_not_live(pid).await;
    }
    retry_after_cleanup(synthetic_config(root.path(), "success", &[])).await;
}

#[test]
fn source_owns_cleanup_and_has_no_runtime_registration_or_real_custody_path() {
    let source = include_str!("../src/story_render_supervisor.rs");
    for required in [
        "tokio::select!",
        "libc::flock",
        "libc::setsid",
        "libc::PR_SET_PDEATHSIG",
        "libc::SIGTERM",
        "libc::SIGKILL",
        "kill_on_drop(true)",
        ".wait()",
        "env_clear()",
    ] {
        assert!(
            source.contains(required),
            "missing ownership marker: {required}"
        );
    }
    for forbidden in [
        "mcp_tools",
        "story_command_render",
        "/home/pallasting/.agent-bridge-secure",
        "authority-keys.v1.json",
        "onnxruntime",
        "sounddevice",
    ] {
        assert!(
            !source.contains(forbidden),
            "forbidden S623 surface: {forbidden}"
        );
    }
}
