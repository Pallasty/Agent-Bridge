#![cfg(target_os = "linux")]

#[path = "../src/story_render_replay_continuity_file_synthetic.rs"]
mod story_render_replay_continuity_file_synthetic;
#[path = "../src/story_render_replay_continuity_synthetic.rs"]
mod story_render_replay_continuity_synthetic;

use std::fs;
use std::os::unix::fs::{MetadataExt, PermissionsExt, symlink};
use std::path::Path;
use std::process::{Command, ExitStatus, Stdio};

use story_render_replay_continuity_file_synthetic::{
    SYNTHETIC_FILE_REPLAY_DIRECTORY, StoryRenderFileReplayFault, StoryRenderFileReplayStore,
};
use story_render_replay_continuity_synthetic::{
    StoryRenderReplayContinuityError, StoryRenderReplayContinuityStore,
};

const HELPER_ACTION: &str = "AB_S629_HELPER_ACTION";
const HELPER_ROOT: &str = "AB_S629_HELPER_ROOT";
const HELPER_SEQUENCE: &str = "AB_S629_HELPER_SEQUENCE";
const CRASH_EXIT: i32 = 70;
const REPLAY_EXIT: i32 = 41;
const BACKEND_EXIT: i32 = 42;

fn helper_command(root: &Path, action: &str, sequence: u64) -> Command {
    let mut command = Command::new(std::env::current_exe().expect("current S629 test binary"));
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
        .expect("run S629 helper process")
}

#[test]
fn subprocess_entrypoint() {
    let Ok(action) = std::env::var(HELPER_ACTION) else {
        return;
    };
    let root = std::env::var_os(HELPER_ROOT).expect("helper root");
    let sequence = std::env::var(HELPER_SEQUENCE)
        .expect("helper sequence")
        .parse::<u64>()
        .expect("numeric helper sequence");
    let store = StoryRenderFileReplayStore::open(Path::new(&root)).expect("open helper store");

    match action.as_str() {
        "reserve_crash" => {
            let _reservation = store.reserve(sequence).expect("reserve before crash");
            std::process::exit(CRASH_EXIT);
        }
        "reserve" => {
            let _reservation = store.reserve(sequence).expect("reserve in helper");
        }
        "commit" => {
            let reservation = store.reserve(sequence).expect("reserve before commit");
            store.commit(reservation).expect("commit in helper");
        }
        "abort" => {
            let reservation = store.reserve(sequence).expect("reserve before abort");
            store.abort(reservation).expect("abort in helper");
        }
        "reserve_result" => match store.reserve(sequence) {
            Ok(_reservation) => {}
            Err(StoryRenderReplayContinuityError::Replay) => {
                std::process::exit(REPLAY_EXIT);
            }
            Err(_) => std::process::exit(BACKEND_EXIT),
        },
        _ => panic!("unknown S629 helper action"),
    }
}

#[test]
fn abrupt_process_exit_leaves_sequence_rejected_after_restart() {
    let root = tempfile::tempdir().expect("S629 temp root");

    let crashed = run_helper(root.path(), "reserve_crash", 700);
    assert_eq!(crashed.code(), Some(CRASH_EXIT));
    let restarted = run_helper(root.path(), "reserve_result", 700);
    assert_eq!(restarted.code(), Some(REPLAY_EXIT));
}

#[test]
fn committed_and_aborted_sequences_remain_rejected_in_fresh_processes() {
    let root = tempfile::tempdir().expect("S629 temp root");

    assert!(run_helper(root.path(), "commit", 701).success());
    assert!(run_helper(root.path(), "abort", 702).success());
    assert_eq!(
        run_helper(root.path(), "reserve_result", 701).code(),
        Some(REPLAY_EXIT)
    );
    assert_eq!(
        run_helper(root.path(), "reserve_result", 702).code(),
        Some(REPLAY_EXIT)
    );
}

#[test]
fn concurrent_processes_have_exactly_one_reservation_winner() {
    const CONTENDERS: usize = 12;
    let root = tempfile::tempdir().expect("S629 temp root");
    let children = (0..CONTENDERS)
        .map(|_| {
            helper_command(root.path(), "reserve_result", 703)
                .spawn()
                .expect("spawn S629 contender")
        })
        .collect::<Vec<_>>();

    let statuses = children
        .into_iter()
        .map(|mut child| child.wait().expect("wait for S629 contender"))
        .collect::<Vec<_>>();
    assert_eq!(statuses.iter().filter(|status| status.success()).count(), 1);
    assert_eq!(
        statuses
            .iter()
            .filter(|status| status.code() == Some(REPLAY_EXIT))
            .count(),
        CONTENDERS - 1
    );
}

#[test]
fn create_before_record_failure_consumes_sequence_fail_closed() {
    let root = tempfile::tempdir().expect("S629 temp root");
    let store = StoryRenderFileReplayStore::open_with_fault(
        root.path(),
        StoryRenderFileReplayFault::AfterCreateBeforeRecord,
    )
    .expect("open faulting store");

    assert!(matches!(
        store.reserve(704),
        Err(StoryRenderReplayContinuityError::BackendUnavailable)
    ));
    assert_eq!(
        run_helper(root.path(), "reserve_result", 704).code(),
        Some(REPLAY_EXIT)
    );
}

#[test]
fn finalize_failure_keeps_reserved_sequence_rejected() {
    let root = tempfile::tempdir().expect("S629 temp root");
    let store = StoryRenderFileReplayStore::open_with_fault(
        root.path(),
        StoryRenderFileReplayFault::BeforeFinalize,
    )
    .expect("open faulting store");
    let reservation = store.reserve(705).expect("reserve before fault");

    assert_eq!(
        store.commit(reservation),
        Err(StoryRenderReplayContinuityError::BackendUnavailable)
    );
    assert_eq!(
        run_helper(root.path(), "reserve_result", 705).code(),
        Some(REPLAY_EXIT)
    );
}

#[test]
fn another_store_root_cannot_finalize_reservation() {
    let first_root = tempfile::tempdir().expect("first S629 root");
    let second_root = tempfile::tempdir().expect("second S629 root");
    let first = StoryRenderFileReplayStore::open(first_root.path()).expect("first store");
    let second = StoryRenderFileReplayStore::open(second_root.path()).expect("second store");
    let reservation = first.reserve(706).expect("first reservation");

    assert_eq!(
        second.commit(reservation),
        Err(StoryRenderReplayContinuityError::WrongStore)
    );
    assert_eq!(
        run_helper(first_root.path(), "reserve_result", 706).code(),
        Some(REPLAY_EXIT)
    );
}

#[test]
fn durable_layout_is_private_fixed_and_single_linked() {
    let root = tempfile::tempdir().expect("S629 temp root");
    let store = StoryRenderFileReplayStore::open(root.path()).expect("open store");
    let _reservation = store.reserve(707).expect("reserve sequence");
    let state_directory = root.path().join(SYNTHETIC_FILE_REPLAY_DIRECTORY);
    let directory_metadata = fs::symlink_metadata(&state_directory).expect("state directory");

    assert!(directory_metadata.is_dir());
    assert_eq!(directory_metadata.permissions().mode() & 0o777, 0o700);
    let entries = fs::read_dir(&state_directory)
        .expect("read state directory")
        .collect::<Result<Vec<_>, _>>()
        .expect("collect state entries");
    assert_eq!(entries.len(), 1);
    let metadata = entries[0].metadata().expect("state record metadata");
    assert!(metadata.is_file());
    assert_eq!(metadata.permissions().mode() & 0o777, 0o600);
    assert_eq!(metadata.nlink(), 1);
    assert_eq!(metadata.len(), 17);
}

#[test]
fn out_of_range_sequences_create_no_state_records() {
    let root = tempfile::tempdir().expect("S629 temp root");
    let store = StoryRenderFileReplayStore::open(root.path()).expect("open store");

    for sequence in [4_096, u64::MAX] {
        assert!(matches!(
            store.reserve(sequence),
            Err(StoryRenderReplayContinuityError::OutOfRange)
        ));
    }
    assert_eq!(
        fs::read_dir(root.path().join(SYNTHETIC_FILE_REPLAY_DIRECTORY))
            .expect("read empty state directory")
            .count(),
        0
    );
}

#[test]
fn relative_and_symlink_roots_are_rejected_before_state_creation() {
    assert!(matches!(
        StoryRenderFileReplayStore::open(Path::new("relative-s629-root")),
        Err(StoryRenderReplayContinuityError::BackendUnavailable)
    ));

    let root = tempfile::tempdir().expect("S629 temp root");
    let actual = root.path().join("actual");
    fs::create_dir(&actual).expect("create actual root");
    let linked = root.path().join("linked");
    symlink(&actual, &linked).expect("create root symlink");
    assert!(matches!(
        StoryRenderFileReplayStore::open(&linked),
        Err(StoryRenderReplayContinuityError::BackendUnavailable)
    ));
    assert!(!actual.join(SYNTHETIC_FILE_REPLAY_DIRECTORY).exists());
}

#[test]
fn source_is_a_dormant_bounded_file_backend_without_runtime_surfaces() {
    let source = include_str!("../src/story_render_replay_continuity_file_synthetic.rs");
    for required in [
        "create_new(true)",
        "sync_all",
        "O_NOFOLLOW",
        "MetadataExt",
        "FileExt",
        "STATE_RECORD_LEN",
        "SYNTHETIC_FILE_REPLAY_DIRECTORY",
    ] {
        assert!(source.contains(required), "missing S629 marker: {required}");
    }
    for forbidden in [
        "remove_file",
        "remove_dir",
        "set_len(0)",
        "tokio::",
        "mcp_tools",
        "authority-keys",
        "Hmac",
        "onnxruntime",
        "sounddevice",
        "process::Command",
        "story_command_render",
    ] {
        assert!(
            !source.contains(forbidden),
            "forbidden S629 surface: {forbidden}"
        );
    }
}
