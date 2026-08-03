#![cfg(target_os = "linux")]

#[path = "../src/story_render_durable_synthetic_composition.rs"]
mod story_render_durable_synthetic_composition;
#[path = "../src/story_render_fixed_synthetic_provider.rs"]
mod story_render_fixed_synthetic_provider;
#[allow(dead_code)]
#[path = "../src/story_render_guardian.rs"]
mod story_render_guardian;
#[allow(dead_code)]
#[path = "../src/story_render_guardian_protocol.rs"]
mod story_render_guardian_protocol;
#[allow(dead_code)]
#[path = "../src/story_render_guardian_supervision.rs"]
mod story_render_guardian_supervision;
#[path = "../src/story_render_replay_continuity_file_synthetic.rs"]
mod story_render_replay_continuity_file_synthetic;
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
use std::fs::{self, OpenOptions};
use std::io::Write;
use std::os::unix::fs::OpenOptionsExt;
use std::path::{Path, PathBuf};
use std::process::{Command, ExitStatus, Stdio};
use std::time::{Duration, Instant};

use story_render_durable_synthetic_composition::{
    run_s630_durable_synthetic_composition, StoryRenderDurableSyntheticCompositionError,
};
use story_render_replay_continuity_file_synthetic::{
    StoryRenderFileReplayFault, StoryRenderFileReplayStore, SYNTHETIC_FILE_REPLAY_DIRECTORY,
};
use story_render_replay_continuity_synthetic::{
    StoryRenderReplayContinuityError, StoryRenderReplayContinuityStore,
    StoryRenderSyntheticReplayMemory,
};
use story_render_supervisor::{
    begin_story_render_admission, start_story_render_supervisor, StoryRenderSupervisorConfig,
    StoryRenderSupervisorError,
};
use story_render_synthetic_admission::StoryRenderSyntheticAdmissionError;
use story_render_synthetic_composition::StoryRenderSyntheticResponse;

const HELPER_ACTION: &str = "AB_S630_HELPER_ACTION";
const HELPER_ROOT: &str = "AB_S630_HELPER_ROOT";
const HELPER_SEQUENCE: &str = "AB_S630_HELPER_SEQUENCE";

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

fn missing_worker_config(root: &Path) -> StoryRenderSupervisorConfig {
    let mut config = codec_config(root);
    config.executable = PathBuf::from("/s630/missing/python3");
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

fn helper_command(root: &Path, action: &str, sequence: u64) -> Command {
    let mut command = Command::new(std::env::current_exe().expect("current S630 test binary"));
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
        .expect("run S630 helper process")
}

fn record_path(root: &Path, sequence: u64) -> PathBuf {
    root.join(SYNTHETIC_FILE_REPLAY_DIRECTORY)
        .join(format!("sequence-{sequence:04x}.s629"))
}

fn record_state(root: &Path, sequence: u64) -> u8 {
    let record = fs::read(record_path(root, sequence)).expect("read S630 replay record");
    assert_eq!(record.len(), 17);
    record[16]
}

fn install_malformed_record(root: &Path, sequence: u64, record: &[u8]) {
    let store = StoryRenderFileReplayStore::open(root).expect("create S630 state directory");
    drop(store);
    let path = record_path(root, sequence);
    let mut file = OpenOptions::new()
        .write(true)
        .create_new(true)
        .mode(0o600)
        .open(path)
        .expect("create malformed S630 record");
    file.write_all(record).expect("write malformed S630 record");
    file.sync_all().expect("sync malformed S630 record");
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
        "success" => {
            let result =
                run_s630_durable_synthetic_composition(codec_config(&root), sequence, &store)
                    .await
                    .expect("run S630 helper composition");
            assert!(matches!(
                result.response,
                StoryRenderSyntheticResponse::Success(_)
            ));
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
        }
        _ => panic!("unknown S630 helper action"),
    }
}

#[test]
fn successful_full_chain_commits_and_fresh_process_rejects_replay() {
    let root = tempfile::tempdir().expect("S630 temp root");

    assert!(run_helper(root.path(), "success", 900).success());
    assert_eq!(record_state(root.path(), 900), 2);
    assert!(run_helper(root.path(), "expect_replay", 900).success());
}

#[tokio::test]
async fn spawn_failure_aborts_and_fresh_process_rejects_replay() {
    let root = tempfile::tempdir().expect("S630 temp root");
    let store = StoryRenderFileReplayStore::open(root.path()).expect("open S630 store");

    let error =
        run_s630_durable_synthetic_composition(missing_worker_config(root.path()), 901, &store)
            .await
            .expect_err("spawn failure must abort durable reservation");
    assert_eq!(
        error,
        StoryRenderDurableSyntheticCompositionError::Admission(
            StoryRenderSyntheticAdmissionError::Supervisor(StoryRenderSupervisorError::SpawnFailed)
        )
    );
    assert_eq!(record_state(root.path(), 901), 3);
    assert!(run_helper(root.path(), "expect_replay", 901).success());
}

#[tokio::test]
async fn busy_host_does_not_consume_durable_sequence() {
    let root = tempfile::tempdir().expect("S630 temp root");
    let pid_file = root.path().join("busy.pid");
    let first = start_story_render_supervisor(
        lifecycle_config(root.path(), &pid_file),
        br#"{"synthetic":"s630-busy"}"#.to_vec(),
    )
    .await
    .expect("start busy S630 Worker");
    let pid = wait_for_pid_file(&pid_file).await;
    let store = StoryRenderFileReplayStore::open(root.path()).expect("open S630 store");

    let error = run_s630_durable_synthetic_composition(codec_config(root.path()), 902, &store)
        .await
        .expect_err("busy host rejects before durable reservation");
    assert_eq!(
        error,
        StoryRenderDurableSyntheticCompositionError::Admission(
            StoryRenderSyntheticAdmissionError::Supervisor(StoryRenderSupervisorError::Busy)
        )
    );
    assert!(!record_path(root.path(), 902).exists());

    drop(first);
    wait_until_not_live(pid).await;
    wait_until_lock_available(codec_config(root.path())).await;
    run_s630_durable_synthetic_composition(codec_config(root.path()), 902, &store)
        .await
        .expect("same unconsumed sequence succeeds after host release");
    assert_eq!(record_state(root.path(), 902), 2);
}

#[tokio::test]
async fn in_memory_continuity_store_is_injected_through_full_chain() {
    let root = tempfile::tempdir().expect("S630 temp root");
    let memory = StoryRenderSyntheticReplayMemory::new();
    let store = memory.open();

    run_s630_durable_synthetic_composition(codec_config(root.path()), 903, &store)
        .await
        .expect("S628 store crosses full S630 chain");
    drop(store);

    assert!(matches!(
        memory.open().reserve(903),
        Err(StoryRenderReplayContinuityError::Replay)
    ));
}

#[tokio::test]
async fn independent_replay_namespaces_allow_the_same_sequence_once_each() {
    let first_root = tempfile::tempdir().expect("first S630 temp root");
    let second_root = tempfile::tempdir().expect("second S630 temp root");
    let first_store =
        StoryRenderFileReplayStore::open(first_root.path()).expect("first S630 store");
    let second_store =
        StoryRenderFileReplayStore::open(second_root.path()).expect("second S630 store");

    run_s630_durable_synthetic_composition(codec_config(first_root.path()), 907, &first_store)
        .await
        .expect("first replay namespace accepts sequence");
    run_s630_durable_synthetic_composition(codec_config(second_root.path()), 907, &second_store)
        .await
        .expect("independent replay namespace accepts same sequence");

    assert_eq!(record_state(first_root.path(), 907), 2);
    assert_eq!(record_state(second_root.path(), 907), 2);
}

#[tokio::test]
async fn unknown_record_version_fails_closed_before_worker_spawn() {
    let root = tempfile::tempdir().expect("S630 temp root");
    let mut record = [0_u8; 17];
    record[..8].copy_from_slice(b"ABSR628\0");
    record[8..16].copy_from_slice(&904_u64.to_be_bytes());
    record[16] = 1;
    install_malformed_record(root.path(), 904, &record);
    let store = StoryRenderFileReplayStore::open(root.path()).expect("reopen S630 store");

    let error =
        run_s630_durable_synthetic_composition(missing_worker_config(root.path()), 904, &store)
            .await
            .expect_err("unknown record version must fail closed");
    assert_eq!(
        error,
        StoryRenderDurableSyntheticCompositionError::Continuity(
            StoryRenderReplayContinuityError::Replay
        )
    );
    assert_eq!(fs::read(record_path(root.path(), 904)).unwrap(), record);
}

#[tokio::test]
async fn truncated_record_fails_closed_before_worker_spawn() {
    let root = tempfile::tempdir().expect("S630 temp root");
    let record = b"bad";
    install_malformed_record(root.path(), 905, record);
    let store = StoryRenderFileReplayStore::open(root.path()).expect("reopen S630 store");

    let error =
        run_s630_durable_synthetic_composition(missing_worker_config(root.path()), 905, &store)
            .await
            .expect_err("truncated record must fail closed");
    assert_eq!(
        error,
        StoryRenderDurableSyntheticCompositionError::Continuity(
            StoryRenderReplayContinuityError::Replay
        )
    );
    assert_eq!(fs::read(record_path(root.path(), 905)).unwrap(), record);
}

#[tokio::test]
async fn finalize_failure_never_returns_success_and_remains_replay_blocked() {
    let root = tempfile::tempdir().expect("S630 temp root");
    let store = StoryRenderFileReplayStore::open_with_fault(
        root.path(),
        StoryRenderFileReplayFault::BeforeFinalize,
    )
    .expect("open faulting S630 store");

    let error = run_s630_durable_synthetic_composition(codec_config(root.path()), 906, &store)
        .await
        .expect_err("commit failure must hide successful Worker response");
    assert_eq!(
        error,
        StoryRenderDurableSyntheticCompositionError::Continuity(
            StoryRenderReplayContinuityError::BackendUnavailable
        )
    );
    assert_eq!(record_state(root.path(), 906), 1);
    assert!(run_helper(root.path(), "expect_replay", 906).success());
}

#[tokio::test]
async fn out_of_range_sequence_fails_before_worker_spawn() {
    let root = tempfile::tempdir().expect("S630 temp root");
    let store = StoryRenderFileReplayStore::open(root.path()).expect("open S630 store");

    let error =
        run_s630_durable_synthetic_composition(missing_worker_config(root.path()), 4_096, &store)
            .await
            .expect_err("out-of-range sequence must fail before spawn");
    assert_eq!(
        error,
        StoryRenderDurableSyntheticCompositionError::Continuity(
            StoryRenderReplayContinuityError::OutOfRange
        )
    );
    assert_eq!(
        fs::read_dir(root.path().join(SYNTHETIC_FILE_REPLAY_DIRECTORY))
            .expect("read empty S630 state directory")
            .count(),
        0
    );
}

#[test]
fn source_is_generic_dormant_and_has_no_runtime_or_storage_surface() {
    let source = include_str!("../src/story_render_durable_synthetic_composition.rs");
    for required in [
        "run_s630_durable_synthetic_composition",
        "StoryRenderReplayContinuityStore",
        "run_s625_synthetic_admission",
        ".commit(",
        ".abort(",
        "StoryRenderFixedSyntheticProvider",
        "new_with_external_replay_gate",
    ] {
        assert!(source.contains(required), "missing S630 marker: {required}");
    }
    for forbidden in [
        "StoryRenderFileReplayStore",
        "std::fs",
        "OpenOptions",
        "process::Command",
        "tokio::spawn",
        "mcp_tools",
        "story_command_render",
        "authority-keys",
        "Hmac",
        "onnxruntime",
        "sounddevice",
    ] {
        assert!(
            !source.contains(forbidden),
            "forbidden S630 surface: {forbidden}"
        );
    }
}
