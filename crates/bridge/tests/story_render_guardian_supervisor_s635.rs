#![cfg(target_os = "linux")]
#![deny(clippy::all)]

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

use std::ffi::OsString;
use std::fs;
use std::path::{Path, PathBuf};
use std::time::{Duration, Instant};

use story_render_guardian::{run_guardian_entrypoint, GuardianLaunchSpec};
use story_render_supervisor::{
    start_story_render_supervisor, StoryRenderCustodyMode, StoryRenderSupervisorConfig,
    StoryRenderSupervisorError,
};

const REQUEST: &[u8] = br#"{"protocol":"synthetic-s635"}"#;

#[test]
fn subprocess_entrypoint() {
    let Some(exit_code) = run_guardian_entrypoint() else {
        return;
    };
    std::process::exit(exit_code);
}

fn fixture_script() -> PathBuf {
    Path::new(env!("CARGO_MANIFEST_DIR"))
        .join("tests/fixtures/story_render_worker_s623.py")
        .canonicalize()
        .expect("canonical S623 Worker fixture")
}

fn guardian_launch() -> GuardianLaunchSpec {
    GuardianLaunchSpec {
        executable: std::env::current_exe().expect("current S635 test executable"),
        arguments: vec![
            OsString::from("--exact"),
            OsString::from("subprocess_entrypoint"),
            OsString::from("--nocapture"),
        ],
    }
}

fn config(root: &Path, mode: &str, extra: &[&Path]) -> StoryRenderSupervisorConfig {
    let mut config = StoryRenderSupervisorConfig::s620_synthetic(
        PathBuf::from("/usr/bin/python3"),
        fixture_script(),
        root.join("render-worker.lock"),
    );
    config.arguments.push(OsString::from(mode));
    config
        .arguments
        .extend(extra.iter().map(|path| path.as_os_str().to_owned()));
    config.deadline = Duration::from_secs(2);
    config.termination_grace = Duration::from_millis(50);
    config.custody_mode = StoryRenderCustodyMode::GuardianV2(guardian_launch());
    config
}

fn process_is_live(pid: u32) -> bool {
    let Ok(stat) = fs::read_to_string(format!("/proc/{pid}/stat")) else {
        return false;
    };
    let Some(after_name) = stat.rsplit_once(") ").map(|(_, rest)| rest) else {
        return true;
    };
    !after_name.starts_with('Z')
}

async fn wait_for_pid_file(path: &Path, count: usize) -> Vec<u32> {
    let deadline = Instant::now() + Duration::from_secs(3);
    loop {
        if let Ok(text) = tokio::fs::read_to_string(path).await {
            let pids = text
                .split_whitespace()
                .filter_map(|value| value.parse::<u32>().ok())
                .collect::<Vec<_>>();
            if pids.len() == count {
                return pids;
            }
        }
        assert!(Instant::now() < deadline, "fixture PIDs were not published");
        tokio::time::sleep(Duration::from_millis(10)).await;
    }
}

#[test]
fn direct_v1_remains_the_default_rollback_mode() {
    let root = tempfile::tempdir().expect("S635 default temp root");
    let config = StoryRenderSupervisorConfig::s620_synthetic(
        PathBuf::from("/usr/bin/python3"),
        fixture_script(),
        root.path().join("render-worker.lock"),
    );

    assert!(matches!(
        config.custody_mode,
        StoryRenderCustodyMode::DirectV1
    ));
}

#[tokio::test]
async fn guardian_v2_async_start_returns_truthful_worker_and_preserves_output_contract() {
    let root = tempfile::tempdir().expect("S635 success temp root");
    let config = config(root.path(), "success", &[]);

    let run = start_story_render_supervisor(config, REQUEST.to_vec())
        .await
        .expect("start GuardianV2 run");
    let worker_pid = run.worker_pid();
    assert!(process_is_live(worker_pid));

    let output = run.await.expect("GuardianV2 synthetic success");
    assert_eq!(output.status_code, Some(0));
    assert_eq!(output.stdout, br#"{"status":"synthetic-success"}"#);
    assert_eq!(output.stderr, b"synthetic diagnostic\n");
    assert!(!process_is_live(worker_pid));
}

#[tokio::test]
async fn guardian_v2_deadline_reaps_term_ignoring_group_before_same_lock_reopens() {
    let root = tempfile::tempdir().expect("S635 deadline temp root");
    let pid_file = root.path().join("descendants.pid");
    let mut guarded = config(root.path(), "term_ignoring_descendant", &[&pid_file]);
    guarded.deadline = Duration::from_millis(100);

    let run = start_story_render_supervisor(guarded, REQUEST.to_vec())
        .await
        .expect("start GuardianV2 deadline fixture");
    let pids = wait_for_pid_file(&pid_file, 2).await;
    assert_eq!(pids[0], run.worker_pid());
    assert_eq!(
        run.await.expect_err("deadline must fail closed"),
        StoryRenderSupervisorError::DeadlineExceeded
    );
    assert!(pids.iter().all(|pid| !process_is_live(*pid)));

    let retry =
        start_story_render_supervisor(config(root.path(), "success", &[]), REQUEST.to_vec())
            .await
            .expect("same lock reopens only after clean Guardian custody");
    retry.await.expect("post-cleanup retry succeeds");
}

async fn expect_guardian_failure(root: &Path, mode: &str, expected: StoryRenderSupervisorError) {
    let run = start_story_render_supervisor(config(root, mode, &[]), REQUEST.to_vec())
        .await
        .expect("start GuardianV2 failure fixture");
    assert_eq!(run.await.expect_err("fixture must fail closed"), expected);
}

#[tokio::test]
async fn guardian_v2_single_failure_matrix_preserves_stream_and_worker_errors() {
    for (mode, expected) in [
        (
            "no_response",
            StoryRenderSupervisorError::WorkerExitWithoutResponse,
        ),
        (
            "malformed_output",
            StoryRenderSupervisorError::ResponseRejected,
        ),
        (
            "stdout_overflow",
            StoryRenderSupervisorError::StdoutLimitExceeded,
        ),
        (
            "stderr_overflow",
            StoryRenderSupervisorError::StderrLimitExceeded,
        ),
        ("unknown_mode", StoryRenderSupervisorError::WorkerFailed),
    ] {
        let root = tempfile::tempdir().expect("S635 failure matrix root");
        expect_guardian_failure(root.path(), mode, expected).await;
    }
}

#[tokio::test]
async fn guardian_spawn_and_bound_failures_are_distinct_and_release_custody() {
    let spawn_root = tempfile::tempdir().expect("S635 spawn failure root");
    let mut spawn_config = config(spawn_root.path(), "success", &[]);
    spawn_config.custody_mode = StoryRenderCustodyMode::GuardianV2(GuardianLaunchSpec {
        executable: PathBuf::from("/s635/missing/guardian"),
        arguments: Vec::new(),
    });
    assert_eq!(
        start_story_render_supervisor(spawn_config, REQUEST.to_vec())
            .await
            .err(),
        Some(StoryRenderSupervisorError::GuardianSpawnFailed)
    );

    let protocol_root = tempfile::tempdir().expect("S635 protocol failure root");
    let mut protocol_config = config(protocol_root.path(), "success", &[]);
    protocol_config.custody_mode = StoryRenderCustodyMode::GuardianV2(GuardianLaunchSpec {
        executable: PathBuf::from("/usr/bin/true"),
        arguments: Vec::new(),
    });
    assert_eq!(
        start_story_render_supervisor(protocol_config, REQUEST.to_vec())
            .await
            .err(),
        Some(StoryRenderSupervisorError::GuardianProtocolRejected)
    );

    let retry = start_story_render_supervisor(
        config(protocol_root.path(), "success", &[]),
        REQUEST.to_vec(),
    )
    .await
    .expect("protocol failure releases custody after exact Guardian reap");
    retry.await.expect("post-protocol retry succeeds");
}

#[tokio::test]
async fn worker_exec_failure_is_spawn_failed_not_a_worker_exit() {
    let root = tempfile::tempdir().expect("S635 Worker exec failure root");
    let mut missing_worker = config(root.path(), "success", &[]);
    missing_worker.executable = PathBuf::from("/s635/missing/worker");

    let run = start_story_render_supervisor(missing_worker, REQUEST.to_vec())
        .await
        .expect("Guardian binds the gated bootstrap before Worker exec");
    assert_eq!(
        run.await.expect_err("Worker exec failure must fail closed"),
        StoryRenderSupervisorError::SpawnFailed
    );

    let retry =
        start_story_render_supervisor(config(root.path(), "success", &[]), REQUEST.to_vec())
            .await
            .expect("Worker exec failure releases proven custody");
    retry.await.expect("post-Worker-exec retry succeeds");
}

#[tokio::test]
async fn payload_inherits_no_guardian_custody_descriptors() {
    let root = tempfile::tempdir().expect("S635 payload fd audit root");
    let run = start_story_render_supervisor(config(root.path(), "fd_audit", &[]), REQUEST.to_vec())
        .await
        .expect("start payload fd audit");
    let output = run.await.expect("payload custody fd audit succeeds");

    assert_eq!(output.stdout, br#"{"status":"synthetic-success"}"#);
    assert!(output.stderr.is_empty());
}

#[tokio::test]
async fn guardian_loss_uses_host_fallback_before_reporting_and_reopening_lock() {
    let root = tempfile::tempdir().expect("S635 Guardian loss root");
    expect_guardian_failure(
        root.path(),
        "kill_guardian",
        StoryRenderSupervisorError::GuardianLost,
    )
    .await;

    let retry =
        start_story_render_supervisor(config(root.path(), "success", &[]), REQUEST.to_vec())
            .await
            .expect("Guardian loss fallback reopens lock");
    retry.await.expect("post-Guardian-loss retry succeeds");
}

#[tokio::test]
async fn worker_exit_with_live_descendant_is_failure_after_group_cleanup() {
    let root = tempfile::tempdir().expect("S635 residual integration root");
    let pid_file = root.path().join("residual.pid");
    let run = start_story_render_supervisor(
        config(root.path(), "exit_with_descendant", &[&pid_file]),
        REQUEST.to_vec(),
    )
    .await
    .expect("start residual integration fixture");
    let pids = wait_for_pid_file(&pid_file, 2).await;

    assert_eq!(
        run.await.expect_err("residual descendant must fail closed"),
        StoryRenderSupervisorError::WorkerFailed
    );
    assert!(pids.iter().all(|pid| !process_is_live(*pid)));
}
