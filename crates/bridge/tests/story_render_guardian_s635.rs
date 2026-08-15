#![cfg(target_os = "linux")]
#![deny(clippy::all)]

#[allow(dead_code)]
#[path = "../src/story_render_guardian.rs"]
mod story_render_guardian;
#[allow(dead_code)]
#[path = "../src/story_render_guardian_protocol.rs"]
mod story_render_guardian_protocol;

use std::collections::BTreeMap;
use std::ffi::OsString;
use std::fs::{self, File, OpenOptions};
use std::io::{Read, Write};
use std::os::fd::AsRawFd;
use std::os::unix::fs::OpenOptionsExt;
use std::path::{Path, PathBuf};
use std::time::{Duration, Instant};

use story_render_guardian::{run_guardian_entrypoint, spawn_guardian_v2, GuardianLaunchSpec};
use story_render_guardian_protocol::{
    read_frame_v2, write_frame_v2, GuardianFailureV2, GuardianFrameV2, GuardianStageV2,
    SealedExecPlan, WorkerExecPlanV1, WorkerExitV2,
};

fn worker_script() -> PathBuf {
    Path::new(env!("CARGO_MANIFEST_DIR"))
        .join("tests/fixtures/story_render_worker_s623.py")
        .canonicalize()
        .expect("canonical S623 Worker fixture")
}

fn environment() -> BTreeMap<OsString, OsString> {
    BTreeMap::from([
        (OsString::from("LANG"), OsString::from("C.UTF-8")),
        (OsString::from("LC_ALL"), OsString::from("C.UTF-8")),
        (OsString::from("TZ"), OsString::from("UTC")),
        (OsString::from("PYTHONNOUSERSITE"), OsString::from("1")),
        (
            OsString::from("PYTHONDONTWRITEBYTECODE"),
            OsString::from("1"),
        ),
        (OsString::from("HF_HUB_OFFLINE"), OsString::from("1")),
        (OsString::from("TRANSFORMERS_OFFLINE"), OsString::from("1")),
        (OsString::from("CUDA_VISIBLE_DEVICES"), OsString::from("")),
        (OsString::from("HIP_VISIBLE_DEVICES"), OsString::from("")),
        (OsString::from("ROCR_VISIBLE_DEVICES"), OsString::from("")),
    ])
}

fn plan(arguments: Vec<OsString>) -> WorkerExecPlanV1 {
    WorkerExecPlanV1 {
        executable: PathBuf::from("/usr/bin/python3"),
        script: worker_script(),
        arguments,
        environment: environment(),
        current_dir: PathBuf::from("/"),
    }
}

fn launch_spec() -> GuardianLaunchSpec {
    GuardianLaunchSpec {
        executable: std::env::current_exe().expect("current S635 Guardian test binary"),
        arguments: vec![
            OsString::from("--exact"),
            OsString::from("subprocess_entrypoint"),
            OsString::from("--nocapture"),
        ],
    }
}

fn acquire_lock(path: &Path) -> File {
    let file = OpenOptions::new()
        .read(true)
        .write(true)
        .create(true)
        .mode(0o600)
        .custom_flags(libc::O_CLOEXEC | libc::O_NOFOLLOW)
        .open(path)
        .expect("open S635 Guardian lock");
    let result = unsafe {
        // SAFETY: the file owns a valid descriptor and flock retains no pointer.
        libc::flock(file.as_raw_fd(), libc::LOCK_EX | libc::LOCK_NB)
    };
    assert_eq!(result, 0, "acquire S635 Guardian lock");
    file
}

fn lock_available(path: &Path) -> bool {
    let file = OpenOptions::new()
        .read(true)
        .write(true)
        .mode(0o600)
        .custom_flags(libc::O_CLOEXEC | libc::O_NOFOLLOW)
        .open(path)
        .expect("open lock probe");
    unsafe {
        // SAFETY: the probe owns the descriptor and closes it immediately.
        libc::flock(file.as_raw_fd(), libc::LOCK_EX | libc::LOCK_NB) == 0
    }
}

fn process_is_live(pid: u32) -> bool {
    let Ok(stat) = fs::read_to_string(format!("/proc/{pid}/stat")) else {
        return false;
    };
    stat.rsplit_once(") ")
        .is_none_or(|(_, rest)| !rest.starts_with('Z'))
}

fn wait_for_pids(path: &Path, count: usize) -> Vec<u32> {
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
        assert!(Instant::now() < deadline, "Worker pids were not published");
        std::thread::sleep(Duration::from_millis(10));
    }
}

fn wait_until(condition: impl Fn() -> bool, message: &str) {
    let deadline = Instant::now() + Duration::from_secs(5);
    while !condition() {
        assert!(Instant::now() < deadline, "{message}");
        std::thread::sleep(Duration::from_millis(10));
    }
}

#[test]
fn subprocess_entrypoint() {
    let Some(exit_code) = run_guardian_entrypoint() else {
        return;
    };
    std::process::exit(exit_code);
}

#[test]
fn generic_guardian_runs_real_fixture_and_reports_exact_exit() {
    let root = tempfile::tempdir().expect("S635 Guardian success root");
    let lock_path = root.path().join("render.lock");
    let lock = acquire_lock(&lock_path);
    let sealed =
        SealedExecPlan::create(&plan(vec![OsString::from("success")])).expect("seal success plan");
    let plan_sha256 = sealed.sha256();
    let mut host =
        spawn_guardian_v2(&lock, &sealed, &launch_spec()).expect("spawn generic S635 Guardian");

    let bound = read_frame_v2(host.control_mut()).expect("read exact bound");
    let (worker_pid, worker_pgid) = match bound {
        GuardianFrameV2::Bound {
            guardian_pid,
            worker_pid,
            worker_pgid,
            plan_sha256: actual,
        } => {
            assert_eq!(guardian_pid, host.guardian_pid());
            assert_eq!(actual, plan_sha256);
            (worker_pid, worker_pgid)
        }
        other => panic!("expected bound frame, got {other:?}"),
    };
    assert_eq!(worker_pid, worker_pgid);
    write_frame_v2(
        host.control_mut(),
        GuardianFrameV2::Start {
            worker_pid,
            worker_pgid,
            plan_sha256,
        },
    )
    .expect("acknowledge exact Worker binding");
    host.stdin_mut()
        .write_all(br#"{"synthetic":"s635"}"#)
        .expect("write Worker stdin");
    host.finish_stdin().expect("close Worker stdin direction");

    let mut stdout = Vec::new();
    host.stdout_mut()
        .read_to_end(&mut stdout)
        .expect("read Worker stdout");
    let mut stderr = Vec::new();
    host.stderr_mut()
        .read_to_end(&mut stderr)
        .expect("read Worker stderr");
    assert_eq!(
        read_frame_v2(host.control_mut()).expect("read terminal"),
        GuardianFrameV2::Terminal {
            worker_pid,
            worker_pgid,
            exit: WorkerExitV2::Exited(0),
        }
    );
    assert_eq!(stdout, br#"{"status":"synthetic-success"}"#);
    assert_eq!(stderr, b"synthetic diagnostic\n");
    assert!(host
        .wait_guardian()
        .expect("wait Guardian success")
        .success());
    assert!(!lock_available(&lock_path));
    drop(lock);
    assert!(lock_available(&lock_path));
}

#[test]
fn host_control_eof_reaps_term_ignoring_group_before_lock_recovers() {
    let root = tempfile::tempdir().expect("S635 Guardian Host EOF root");
    let lock_path = root.path().join("render.lock");
    let pid_path = root.path().join("worker-pids");
    let lock = acquire_lock(&lock_path);
    let sealed = SealedExecPlan::create(&plan(vec![
        OsString::from("term_ignoring_descendant"),
        pid_path.as_os_str().to_owned(),
    ]))
    .expect("seal Host EOF plan");
    let plan_sha256 = sealed.sha256();
    let mut host =
        spawn_guardian_v2(&lock, &sealed, &launch_spec()).expect("spawn Host EOF Guardian");
    let (worker_pid, worker_pgid) = match read_frame_v2(host.control_mut()).unwrap() {
        GuardianFrameV2::Bound {
            worker_pid,
            worker_pgid,
            ..
        } => (worker_pid, worker_pgid),
        other => panic!("expected bound frame, got {other:?}"),
    };
    write_frame_v2(
        host.control_mut(),
        GuardianFrameV2::Start {
            worker_pid,
            worker_pgid,
            plan_sha256,
        },
    )
    .expect("start Host EOF Worker");
    host.finish_stdin().expect("close empty Worker stdin");
    let pids = wait_for_pids(&pid_path, 2);
    assert!(pids.iter().all(|pid| process_is_live(*pid)));

    drop(host);
    assert!(!lock_available(&lock_path));
    drop(lock);
    wait_until(
        || lock_available(&lock_path),
        "Guardian did not release lock after Host EOF cleanup",
    );
    assert!(pids.iter().all(|pid| !process_is_live(*pid)));
}

#[test]
fn worker_exit_with_live_descendant_is_cleaned_and_reported_as_failure() {
    let root = tempfile::tempdir().expect("S635 residual descendant root");
    let lock_path = root.path().join("render.lock");
    let pid_path = root.path().join("worker-pids");
    let lock = acquire_lock(&lock_path);
    let sealed = SealedExecPlan::create(&plan(vec![
        OsString::from("exit_with_descendant"),
        pid_path.as_os_str().to_owned(),
    ]))
    .expect("seal residual descendant plan");
    let plan_sha256 = sealed.sha256();
    let mut host = spawn_guardian_v2(&lock, &sealed, &launch_spec())
        .expect("spawn residual descendant Guardian");
    let (worker_pid, worker_pgid) = match read_frame_v2(host.control_mut()).unwrap() {
        GuardianFrameV2::Bound {
            worker_pid,
            worker_pgid,
            ..
        } => (worker_pid, worker_pgid),
        other => panic!("expected bound frame, got {other:?}"),
    };
    write_frame_v2(
        host.control_mut(),
        GuardianFrameV2::Start {
            worker_pid,
            worker_pgid,
            plan_sha256,
        },
    )
    .expect("start residual descendant Worker");
    host.finish_stdin().expect("close residual Worker stdin");
    let pids = wait_for_pids(&pid_path, 2);

    let event = read_frame_v2(host.control_mut());
    if event.is_err() {
        unsafe {
            libc::kill(host.guardian_pid() as libc::pid_t, libc::SIGKILL);
            libc::kill(-(worker_pgid as libc::pid_t), libc::SIGKILL);
        }
    }
    let _ = host.wait_guardian();
    drop(lock);
    wait_until(
        || pids.iter().all(|pid| !process_is_live(*pid)),
        "residual Worker group remained live",
    );

    assert_eq!(
        event,
        Ok(GuardianFrameV2::Failure {
            stage: GuardianStageV2::Cleanup,
            failure: GuardianFailureV2::WorkerExitedWithLiveGroup,
            worker_pid,
            worker_pgid,
        })
    );
    assert!(lock_available(&lock_path));
}
