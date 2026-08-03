#![cfg(target_os = "linux")]
#![deny(clippy::all)]

#[allow(dead_code)]
#[path = "../src/story_render_guardian_protocol.rs"]
mod story_render_guardian_protocol;

use std::collections::BTreeMap;
use std::ffi::OsString;
use std::io::Cursor;
use std::os::fd::AsRawFd;
use std::path::PathBuf;

use story_render_guardian_protocol::{
    decode_exec_plan, encode_exec_plan, read_frame_v2, read_sealed_exec_plan, write_frame_v2,
    ExecPlanError, GuardianFailureV2, GuardianFrameV2, GuardianStageV2, ProtocolV2Error,
    SealedExecPlan, WorkerExecPlanV1, WorkerExitV2, MAX_CONTROL_BODY_BYTES, MAX_EXEC_PLAN_BYTES,
};

fn digest(seed: u8) -> [u8; 32] {
    [seed; 32]
}

fn plan() -> WorkerExecPlanV1 {
    WorkerExecPlanV1 {
        executable: PathBuf::from("/usr/bin/python3"),
        script: PathBuf::from("/opt/agent-bridge/story_worker.py"),
        arguments: vec![
            OsString::from("success"),
            OsString::from("/opt/agent-bridge/protocol.json"),
        ],
        environment: BTreeMap::from([
            (OsString::from("LANG"), OsString::from("C.UTF-8")),
            (OsString::from("TZ"), OsString::from("UTC")),
        ]),
        current_dir: PathBuf::from("/"),
    }
}

fn encoded(frame: GuardianFrameV2) -> Vec<u8> {
    let mut bytes = Vec::new();
    write_frame_v2(&mut bytes, frame).expect("encode ABG2 frame");
    bytes
}

#[test]
fn abg2_frames_round_trip_with_plan_and_exit_identity() {
    let frames = [
        GuardianFrameV2::Bound {
            guardian_pid: 101,
            worker_pid: 202,
            worker_pgid: 202,
            plan_sha256: digest(1),
        },
        GuardianFrameV2::Start {
            worker_pid: 202,
            worker_pgid: 202,
            plan_sha256: digest(1),
        },
        GuardianFrameV2::Cancel {
            worker_pid: 202,
            worker_pgid: 202,
        },
        GuardianFrameV2::Terminal {
            worker_pid: 202,
            worker_pgid: 202,
            exit: WorkerExitV2::Exited(7),
        },
        GuardianFrameV2::Terminal {
            worker_pid: 202,
            worker_pgid: 202,
            exit: WorkerExitV2::Signaled(libc::SIGKILL),
        },
        GuardianFrameV2::Failure {
            stage: GuardianStageV2::WorkerSpawn,
            failure: GuardianFailureV2::SpawnFailed,
            worker_pid: 0,
            worker_pgid: 0,
        },
    ];

    for expected in frames {
        let actual =
            read_frame_v2(&mut Cursor::new(encoded(expected))).expect("decode strict ABG2 frame");
        assert_eq!(actual, expected);
    }
}

#[test]
fn abg2_rejects_oversize_trailing_and_ambiguous_bindings() {
    let oversized = u32::try_from(MAX_CONTROL_BODY_BYTES + 1)
        .expect("bounded control length")
        .to_be_bytes()
        .to_vec();
    assert_eq!(
        read_frame_v2(&mut Cursor::new(oversized)),
        Err(ProtocolV2Error::Oversized)
    );

    let mut trailing = encoded(GuardianFrameV2::Cancel {
        worker_pid: 202,
        worker_pgid: 202,
    });
    let body_len = u32::from_be_bytes(trailing[..4].try_into().unwrap());
    trailing[..4].copy_from_slice(&(body_len + 1).to_be_bytes());
    trailing.push(0);
    assert_eq!(
        read_frame_v2(&mut Cursor::new(trailing)),
        Err(ProtocolV2Error::InvalidFrame)
    );

    assert_eq!(
        write_frame_v2(
            &mut Vec::new(),
            GuardianFrameV2::Bound {
                guardian_pid: 101,
                worker_pid: 202,
                worker_pgid: 203,
                plan_sha256: digest(1),
            },
        ),
        Err(ProtocolV2Error::InvalidFrame)
    );
}

#[test]
fn worker_exec_plan_is_canonical_bounded_and_strict() {
    let expected = plan();
    let encoded_once = encode_exec_plan(&expected).expect("encode WorkerExecPlanV1");
    let encoded_twice = encode_exec_plan(&expected).expect("encode deterministically");
    assert_eq!(encoded_once, encoded_twice);
    assert!(encoded_once.len() <= MAX_EXEC_PLAN_BYTES);
    assert_eq!(
        decode_exec_plan(&encoded_once).expect("decode WorkerExecPlanV1"),
        expected
    );

    let mut trailing = encoded_once.clone();
    trailing.push(0);
    assert_eq!(
        decode_exec_plan(&trailing),
        Err(ExecPlanError::InvalidEncoding)
    );

    let mut relative = plan();
    relative.executable = PathBuf::from("python3");
    assert_eq!(encode_exec_plan(&relative), Err(ExecPlanError::InvalidPlan));
}

#[test]
fn sealed_exec_plan_is_digest_bound_and_immutable() {
    let expected = plan();
    let sealed = SealedExecPlan::create(&expected).expect("create sealed execution plan");
    let first = read_sealed_exec_plan(sealed.file()).expect("read sealed plan");
    assert_eq!(first.plan, expected);
    assert_eq!(first.sha256, sealed.sha256());

    let byte = [0_u8; 1];
    let written = unsafe {
        // SAFETY: the descriptor is valid for the call and the byte buffer is
        // readable for exactly one byte. The seal must reject the write.
        libc::pwrite(sealed.as_raw_fd(), byte.as_ptr().cast(), byte.len(), 0)
    };
    assert_eq!(written, -1);
    assert_eq!(
        std::io::Error::last_os_error().raw_os_error(),
        Some(libc::EPERM)
    );
}
