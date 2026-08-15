#![cfg(target_os = "linux")]
#![deny(clippy::all)]

//! S633 dormant Guardian protocol and synthetic custody evidence.

#[path = "../src/story_render_guardian_synthetic.rs"]
mod story_render_guardian_synthetic;

use std::fs;
use std::io::Cursor;
use std::path::Path;
use std::time::{Duration, Instant};

use story_render_guardian_synthetic::{
    probe_lock_available, process_is_live, read_frame, run_synthetic_helper,
    spawn_host_crash_fixture, write_frame, GuardianFailure, GuardianFrame, GuardianOutcome,
    ProtocolError, SyntheticGuardianSpec, SyntheticHostCustody, SyntheticWorkerMode, WorkerBinding,
    HOST_CRASH_EXIT, MAX_FRAME_BYTES,
};

fn encoded(frame: GuardianFrame) -> Vec<u8> {
    let mut bytes = Vec::new();
    write_frame(&mut bytes, frame).expect("encode S633 frame");
    bytes
}

#[test]
fn guardian_frames_round_trip_without_ambiguous_pid_binding() {
    let frames = [
        GuardianFrame::Bound {
            guardian_pid: 101,
            worker_pid: 202,
            worker_pgid: 202,
        },
        GuardianFrame::Start {
            worker_pid: 202,
            worker_pgid: 202,
        },
        GuardianFrame::Cancel,
        GuardianFrame::Terminal {
            worker_pid: 202,
            worker_pgid: 202,
            outcome: GuardianOutcome::CleanSuccess,
        },
        GuardianFrame::Failure {
            failure: GuardianFailure::WorkerExitedWithLiveGroup,
        },
    ];

    for expected in frames {
        let actual = read_frame(&mut Cursor::new(encoded(expected))).expect("decode S633 frame");
        assert_eq!(actual, expected);
    }
}

#[test]
fn malformed_or_oversized_guardian_frames_fail_closed() {
    let oversized = u32::try_from(MAX_FRAME_BYTES + 1)
        .expect("bounded frame length")
        .to_be_bytes()
        .to_vec();
    assert_eq!(
        read_frame(&mut Cursor::new(oversized)),
        Err(ProtocolError::Oversized)
    );

    let mut wrong_magic = encoded(GuardianFrame::Cancel);
    wrong_magic[4] = b'X';
    assert_eq!(
        read_frame(&mut Cursor::new(wrong_magic)),
        Err(ProtocolError::InvalidFrame)
    );

    let mut trailing = encoded(GuardianFrame::Cancel);
    trailing[3] += 1;
    trailing.push(0);
    assert_eq!(
        read_frame(&mut Cursor::new(trailing)),
        Err(ProtocolError::InvalidFrame)
    );

    let invalid_pid = GuardianFrame::Bound {
        guardian_pid: 101,
        worker_pid: 0,
        worker_pgid: 0,
    };
    assert_eq!(
        write_frame(&mut Vec::new(), invalid_pid),
        Err(ProtocolError::InvalidFrame)
    );
}

#[test]
fn subprocess_entrypoint() {
    let Some(exit_code) = run_synthetic_helper() else {
        return;
    };
    std::process::exit(exit_code);
}

fn spec(root: &Path, mode: SyntheticWorkerMode) -> SyntheticGuardianSpec {
    SyntheticGuardianSpec {
        executable: std::env::current_exe().expect("current S633 test executable"),
        worker_mode: mode,
        pid_file: root.join("worker-pids"),
        payload_marker: root.join("payload-started"),
        termination_grace: Duration::from_millis(50),
    }
}

fn wait_for_file(path: &Path) {
    let deadline = Instant::now() + Duration::from_secs(5);
    while !path.exists() {
        assert!(Instant::now() < deadline, "fixture file was not published");
        std::thread::sleep(Duration::from_millis(10));
    }
}

fn read_pids(path: &Path, count: usize) -> Vec<u32> {
    let deadline = Instant::now() + Duration::from_secs(5);
    loop {
        if let Ok(text) = fs::read_to_string(path) {
            let pids: Vec<u32> = text
                .split_whitespace()
                .filter_map(|value| value.parse().ok())
                .collect();
            if pids.len() == count {
                return pids;
            }
        }
        assert!(Instant::now() < deadline, "fixture pids were not published");
        std::thread::sleep(Duration::from_millis(10));
    }
}

fn wait_until_not_live(pid: u32) {
    let deadline = Instant::now() + Duration::from_secs(5);
    while process_is_live(pid) && Instant::now() < deadline {
        std::thread::sleep(Duration::from_millis(10));
    }
    assert!(!process_is_live(pid), "process {pid} remained live");
}

fn expect_bound(frame: GuardianFrame) -> WorkerBinding {
    match frame {
        GuardianFrame::Bound {
            guardian_pid,
            worker_pid,
            worker_pgid,
        } => WorkerBinding {
            guardian_pid,
            worker_pid,
            worker_pgid,
        },
        other => panic!("expected bound frame, got {other:?}"),
    }
}

#[test]
fn payload_waits_for_host_identity_and_inherits_no_custody_descriptors() {
    let root = tempfile::tempdir().expect("S633 gate temp root");
    let lock_path = root.path().join("guardian.lock");
    let spec = spec(root.path(), SyntheticWorkerMode::FdAuditExit);
    let mut host = SyntheticHostCustody::spawn(&lock_path, &spec).expect("spawn Guardian");
    let binding = expect_bound(host.read_event().expect("read bound event"));

    assert_eq!(binding.worker_pid, binding.worker_pgid);
    assert!(!spec.payload_marker.exists());
    assert!(!probe_lock_available(&lock_path).expect("probe held lock"));

    host.acknowledge_start(binding)
        .expect("open Worker start gate");
    assert_eq!(
        host.read_event().expect("read terminal event"),
        GuardianFrame::Terminal {
            worker_pid: binding.worker_pid,
            worker_pgid: binding.worker_pgid,
            outcome: GuardianOutcome::CleanSuccess,
        }
    );
    host.wait_guardian().expect("wait clean Guardian");
    assert_eq!(
        fs::read_to_string(&spec.payload_marker).expect("payload marker"),
        "custody_fds_closed\n"
    );
    drop(host);
    assert!(probe_lock_available(&lock_path).expect("probe released lock"));
}

#[test]
fn host_exit_eof_reaps_term_ignoring_group_before_lock_recovers() {
    let root = tempfile::tempdir().expect("S633 Host-exit temp root");
    let lock_path = root.path().join("guardian.lock");
    let ready_path = root.path().join("host-started");
    let spec = spec(root.path(), SyntheticWorkerMode::TermIgnoringDescendant);
    let mut host = spawn_host_crash_fixture(&lock_path, &spec, &ready_path)
        .expect("spawn abrupt Host fixture");

    wait_for_file(&ready_path);
    let pids = read_pids(&spec.pid_file, 2);
    let status = host.wait().expect("wait abrupt Host fixture");
    assert_eq!(status.code(), Some(HOST_CRASH_EXIT));

    let deadline = Instant::now() + Duration::from_secs(5);
    loop {
        if probe_lock_available(&lock_path).expect("probe Host-exit lock") {
            assert!(
                pids.iter().all(|pid| !process_is_live(*pid)),
                "lock recovered before old process group was absent"
            );
            break;
        }
        assert!(
            Instant::now() < deadline,
            "Guardian did not release clean lock"
        );
        std::thread::sleep(Duration::from_millis(10));
    }
}

#[test]
fn guardian_exit_uses_host_fallback_before_lock_recovers() {
    let root = tempfile::tempdir().expect("S633 Guardian-exit temp root");
    let lock_path = root.path().join("guardian.lock");
    let spec = spec(root.path(), SyntheticWorkerMode::TermIgnoringDescendant);
    let mut host = SyntheticHostCustody::spawn(&lock_path, &spec).expect("spawn Guardian");
    let binding = expect_bound(host.read_event().expect("read bound event"));
    host.acknowledge_start(binding)
        .expect("start Worker payload");
    let pids = read_pids(&spec.pid_file, 2);

    host.kill_guardian_for_test()
        .expect("kill Guardian fixture");
    assert!(!probe_lock_available(&lock_path).expect("probe fallback lock"));
    host.fallback_cleanup(binding)
        .expect("Host fallback group cleanup");
    for pid in pids {
        wait_until_not_live(pid);
    }
    assert!(!probe_lock_available(&lock_path).expect("Host still owns lock"));
    drop(host);
    assert!(probe_lock_available(&lock_path).expect("probe fallback release"));
}

#[test]
fn worker_exit_with_live_descendant_is_failure_not_terminal_success() {
    let root = tempfile::tempdir().expect("S633 residual temp root");
    let lock_path = root.path().join("guardian.lock");
    let spec = spec(root.path(), SyntheticWorkerMode::ExitWithDescendant);
    let mut host = SyntheticHostCustody::spawn(&lock_path, &spec).expect("spawn Guardian");
    let binding = expect_bound(host.read_event().expect("read bound event"));
    host.acknowledge_start(binding)
        .expect("start residual fixture");
    let pids = read_pids(&spec.pid_file, 2);

    assert_eq!(
        host.read_event().expect("read residual failure"),
        GuardianFrame::Failure {
            failure: GuardianFailure::WorkerExitedWithLiveGroup,
        }
    );
    host.wait_guardian()
        .expect("wait residual cleanup Guardian");
    for pid in pids {
        wait_until_not_live(pid);
    }
    assert!(!probe_lock_available(&lock_path).expect("Host retains lock"));
    drop(host);
    assert!(probe_lock_available(&lock_path).expect("probe residual release"));
}

#[test]
fn guardian_prototype_remains_synthetic_only_after_s635_product_wiring() {
    let supervisor = include_str!("../src/story_render_supervisor.rs");
    let bridge_lib = include_str!("../src/lib.rs");
    let guardian = include_str!("../src/story_render_guardian_synthetic.rs");

    assert!(supervisor.contains("story_render_guardian::GuardianLaunchSpec"));
    assert!(supervisor.contains("story_render_guardian_supervision::start_guardian_supervision"));
    assert!(!supervisor.contains("story_render_guardian_synthetic"));
    assert!(!bridge_lib.contains("story_render_guardian_synthetic"));
    for required in [
        "PR_SET_CHILD_SUBREAPER",
        "PR_SET_PDEATHSIG",
        "shared open-file-description",
        "MAX_FRAME_BYTES",
    ] {
        assert!(
            guardian.contains(required),
            "missing S633 marker: {required}"
        );
    }
    for forbidden in [
        "mcp_tools",
        "story_command_render",
        "authority-keys",
        "onnxruntime",
        "sounddevice",
        "cgroup.kill",
        "systemd-run",
    ] {
        assert!(
            !guardian.contains(forbidden),
            "forbidden S633 runtime surface: {forbidden}"
        );
    }
}
