#![cfg(target_os = "linux")]
#![deny(clippy::all)]

//! S631 full-chain cancellation and abrupt-host-exit evidence.
//!
//! Cancellation proves process-group cleanup. Abrupt host exit proves cleanup
//! only for the directly supervised Worker through `PR_SET_PDEATHSIG`; arbitrary
//! descendant-tree cleanup after an ungraceful host exit remains out of scope.

#[path = "../src/story_render_durable_synthetic_composition.rs"]
mod story_render_durable_synthetic_composition;
#[allow(dead_code)]
#[path = "../src/story_render_fixed_synthetic_provider.rs"]
mod story_render_fixed_synthetic_provider;
#[path = "../src/story_render_replay_continuity_file_synthetic.rs"]
mod story_render_replay_continuity_file_synthetic;
#[allow(dead_code)]
#[path = "../src/story_render_replay_continuity_synthetic.rs"]
mod story_render_replay_continuity_synthetic;
#[allow(dead_code)]
#[path = "../src/story_render_supervisor.rs"]
mod story_render_supervisor;
#[path = "../src/story_render_synthetic_admission.rs"]
mod story_render_synthetic_admission;
#[allow(dead_code)]
#[path = "../src/story_render_synthetic_composition.rs"]
mod story_render_synthetic_composition;

use std::ffi::OsString;
use std::fs;
use std::path::{Path, PathBuf};
use std::process::{Command, ExitStatus, Stdio};
use std::time::{Duration, Instant};

use story_render_durable_synthetic_composition::{
    run_s630_durable_synthetic_composition, StoryRenderDurableSyntheticCompositionError,
};
use story_render_replay_continuity_file_synthetic::{
    StoryRenderFileReplayStore, SYNTHETIC_FILE_REPLAY_DIRECTORY,
};
use story_render_replay_continuity_synthetic::StoryRenderReplayContinuityError;
use story_render_supervisor::{
    begin_story_render_admission, StoryRenderSupervisorConfig, StoryRenderSupervisorError,
};

const CRASH_EXIT: i32 = 73;
const HELPER_ACTION: &str = "AB_S631_HELPER_ACTION";
const HELPER_ROOT: &str = "AB_S631_HELPER_ROOT";
const HELPER_SEQUENCE: &str = "AB_S631_HELPER_SEQUENCE";
const HELPER_PID_FILE: &str = "AB_S631_HELPER_PID_FILE";

fn lifecycle_worker_script() -> PathBuf {
    Path::new(env!("CARGO_MANIFEST_DIR"))
        .join("tests/fixtures/story_render_worker_s623.py")
        .canonicalize()
        .expect("canonical S623 Worker fixture")
}

fn lifecycle_config(root: &Path, mode: &str, pid_file: &Path) -> StoryRenderSupervisorConfig {
    let mut config = StoryRenderSupervisorConfig::s620_synthetic(
        PathBuf::from("/usr/bin/python3"),
        lifecycle_worker_script(),
        root.join("render-worker.lock"),
    );
    config
        .arguments
        .extend([OsString::from(mode), pid_file.as_os_str().to_owned()]);
    config.deadline = Duration::from_secs(30);
    config.termination_grace = Duration::from_millis(50);
    config
}

fn missing_worker_config(root: &Path) -> StoryRenderSupervisorConfig {
    let mut config = lifecycle_config(root, "hang", &root.join("must-not-spawn.pid"));
    config.executable = PathBuf::from("/s631/missing/python3");
    config
}

fn helper_command(root: &Path, action: &str, sequence: u64) -> Command {
    let mut command = Command::new(std::env::current_exe().expect("current S631 test binary"));
    command
        .arg("--exact")
        .arg("subprocess_entrypoint")
        .arg("--nocapture")
        .env(HELPER_ACTION, action)
        .env(HELPER_ROOT, root)
        .env(HELPER_SEQUENCE, sequence.to_string())
        .stdin(Stdio::null())
        .stdout(Stdio::null())
        .stderr(Stdio::null());
    command
}

fn run_helper(root: &Path, action: &str, sequence: u64) -> ExitStatus {
    helper_command(root, action, sequence)
        .status()
        .expect("run S631 helper process")
}

fn record_path(root: &Path, sequence: u64) -> PathBuf {
    root.join(SYNTHETIC_FILE_REPLAY_DIRECTORY)
        .join(format!("sequence-{sequence:04x}.s629"))
}

fn record_state(root: &Path, sequence: u64) -> Option<u8> {
    let record = fs::read(record_path(root, sequence)).ok()?;
    (record.len() == 17).then_some(record[16])
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

struct FixtureProcessGroupGuard {
    leader: Option<u32>,
}

impl FixtureProcessGroupGuard {
    fn armed(leader: u32) -> Self {
        Self {
            leader: Some(leader),
        }
    }

    fn disarm(&mut self) {
        self.leader = None;
    }
}

impl Drop for FixtureProcessGroupGuard {
    fn drop(&mut self) {
        let Some(leader) = self.leader else {
            return;
        };
        let expected = lifecycle_worker_script();
        let cmdline = fs::read(format!("/proc/{leader}/cmdline")).unwrap_or_default();
        let expected_bytes = expected.as_os_str().as_encoded_bytes();
        let belongs_to_fixture = cmdline
            .windows(expected_bytes.len())
            .any(|window| window == expected_bytes);
        let group_matches =
            unsafe { libc::getpgid(leader as libc::pid_t) } == leader as libc::pid_t;
        if belongs_to_fixture && group_matches {
            unsafe {
                libc::kill(-(leader as libc::pid_t), libc::SIGKILL);
            }
        }
    }
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

async fn wait_for_record_state(root: &Path, sequence: u64, expected: u8) {
    let deadline = Instant::now() + Duration::from_secs(3);
    loop {
        if record_state(root, sequence) == Some(expected) {
            return;
        }
        assert!(
            Instant::now() < deadline,
            "durable sequence did not reach state {expected}"
        );
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

#[tokio::test]
async fn subprocess_entrypoint() {
    let Ok(action) = std::env::var(HELPER_ACTION) else {
        return;
    };
    let root = PathBuf::from(std::env::var_os(HELPER_ROOT).expect("helper root"));
    let sequence = std::env::var(HELPER_SEQUENCE)
        .expect("helper sequence")
        .parse::<u64>()
        .expect("numeric helper sequence");
    let store = StoryRenderFileReplayStore::open(&root).expect("open helper replay store");

    match action.as_str() {
        "reserve_spawn_exit" => {
            let pid_file =
                PathBuf::from(std::env::var_os(HELPER_PID_FILE).expect("helper Worker pid file"));
            let task_root = root.clone();
            let task_pid_file = pid_file.clone();
            tokio::spawn(async move {
                let _ = run_s630_durable_synthetic_composition(
                    lifecycle_config(&task_root, "hang", &task_pid_file),
                    sequence,
                    &store,
                )
                .await;
            });
            wait_for_pid_file(&pid_file, 1).await;
            wait_for_record_state(&root, sequence, 1).await;
            std::process::exit(CRASH_EXIT);
        }
        "expect_replay" => {
            let error = run_s630_durable_synthetic_composition(
                missing_worker_config(&root),
                sequence,
                &store,
            )
            .await
            .expect_err("fresh helper must reject replay before spawn");
            assert_eq!(
                error,
                StoryRenderDurableSyntheticCompositionError::Continuity(
                    StoryRenderReplayContinuityError::Replay
                )
            );
            assert!(!root.join("must-not-spawn.pid").exists());
        }
        _ => panic!("unknown S631 helper action"),
    }
}

#[tokio::test]
async fn cancelling_full_chain_reaps_worker_group_recovers_lock_and_burns_sequence() {
    let root = tempfile::tempdir().expect("S631 cancellation temp root");
    let sequence = 1_000;
    let pid_file = root.path().join("cancel-descendants.pid");
    let store = StoryRenderFileReplayStore::open(root.path()).expect("open S631 replay store");
    let config = lifecycle_config(root.path(), "term_ignoring_descendant", &pid_file);
    let task = tokio::spawn(async move {
        run_s630_durable_synthetic_composition(config, sequence, &store).await
    });
    let pids = wait_for_pid_file(&pid_file, 2).await;
    let mut cleanup = FixtureProcessGroupGuard::armed(pids[0]);
    wait_for_record_state(root.path(), sequence, 1).await;
    assert!(pids.iter().all(|pid| process_is_live(*pid)));

    task.abort();
    assert!(task
        .await
        .expect_err("S630 task must be cancelled")
        .is_cancelled());

    for pid in &pids {
        wait_until_not_live(*pid).await;
    }
    cleanup.disarm();
    wait_until_lock_available(missing_worker_config(root.path())).await;
    assert_eq!(record_state(root.path(), sequence), Some(1));
    assert!(run_helper(root.path(), "expect_replay", sequence).success());
}

#[tokio::test]
async fn abrupt_host_exit_kills_direct_worker_recovers_lock_and_burns_sequence() {
    let root = tempfile::tempdir().expect("S631 crash temp root");
    let sequence = 1_001;
    let pid_file = root.path().join("crash-worker.pid");
    let status = helper_command(root.path(), "reserve_spawn_exit", sequence)
        .env(HELPER_PID_FILE, &pid_file)
        .status()
        .expect("run abrupt-exit S631 helper");
    assert_eq!(status.code(), Some(CRASH_EXIT));
    let pid = fs::read_to_string(&pid_file)
        .expect("read crashed helper Worker pid")
        .trim()
        .parse::<u32>()
        .expect("numeric crashed helper Worker pid");
    let mut cleanup = FixtureProcessGroupGuard::armed(pid);

    wait_until_not_live(pid).await;
    cleanup.disarm();
    wait_until_lock_available(missing_worker_config(root.path())).await;
    assert_eq!(record_state(root.path(), sequence), Some(1));
    assert!(run_helper(root.path(), "expect_replay", sequence).success());
}

#[test]
fn source_scope_remains_synthetic_and_dormant() {
    let source = include_str!("../src/story_render_supervisor.rs");
    for required in [
        "libc::PR_SET_PDEATHSIG",
        "libc::SIGKILL",
        "libc::getppid() != parent_pid",
        "libc::setsid",
        "libc::O_CLOEXEC",
    ] {
        assert!(
            source.contains(required),
            "missing S631 lifecycle marker: {required}"
        );
    }
    for forbidden in [
        "mcp_tools",
        "story_command_render",
        "authority-keys",
        "onnxruntime",
        "sounddevice",
    ] {
        assert!(
            !source.contains(forbidden),
            "forbidden S631 runtime surface: {forbidden}"
        );
    }
}
