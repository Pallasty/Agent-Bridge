//! Default-off S635 Host-side GuardianV2 supervision.

#![deny(clippy::all)]

use std::ffi::OsString;
use std::io;
use std::process::ExitStatus;
use std::time::Duration;

use tokio::io::{AsyncRead, AsyncReadExt, AsyncWriteExt};
use tokio::net::UnixStream as TokioUnixStream;
use tokio::sync::{oneshot, watch};
use tokio::time::Instant;

use crate::story_render_guardian::{spawn_guardian_v2, GuardianHostParts, GuardianLaunchSpec};
use crate::story_render_guardian_protocol::{
    decode_frame_body_v2, encode_frame_v2, GuardianFailureV2, GuardianFrameV2, GuardianStageV2,
    SealedExecPlan, WorkerExecPlanV1, WorkerExitV2, MAX_CONTROL_BODY_BYTES,
};
use crate::story_render_supervisor::{
    signal_group, HostLock, StoryRenderOutput, StoryRenderRun, StoryRenderSupervisorConfig,
    StoryRenderSupervisorError,
};

const FALLBACK_TIMEOUT: Duration = Duration::from_secs(5);

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
struct GuardianBinding {
    guardian_pid: u32,
    worker_pid: u32,
    worker_pgid: u32,
    plan_sha256: [u8; 32],
}

type GuardianExit = Result<ExitStatus, ()>;

pub(crate) async fn start_guardian_supervision(
    config: StoryRenderSupervisorConfig,
    request: Vec<u8>,
    lock: HostLock,
    launch: GuardianLaunchSpec,
) -> Result<StoryRenderRun, StoryRenderSupervisorError> {
    let deadline = Instant::now() + config.deadline;
    let plan = WorkerExecPlanV1 {
        executable: config.executable.clone(),
        script: config.script.clone(),
        arguments: config.arguments.clone(),
        environment: config
            .environment
            .iter()
            .map(|(key, value)| (OsString::from(key), OsString::from(value)))
            .collect(),
        current_dir: "/".into(),
    };
    let spawned = tokio::task::spawn_blocking(move || {
        let sealed = SealedExecPlan::create(&plan)
            .map_err(|_| StoryRenderSupervisorError::InvalidConfiguration)?;
        let transport = spawn_guardian_v2(&lock.0, &sealed, &launch).map_err(|error| {
            if matches!(
                error,
                crate::story_render_guardian::GuardianRuntimeError::InvalidConfiguration
            ) {
                StoryRenderSupervisorError::InvalidConfiguration
            } else {
                StoryRenderSupervisorError::GuardianSpawnFailed
            }
        })?;
        Ok((lock, sealed.sha256(), transport))
    })
    .await
    .map_err(|_| StoryRenderSupervisorError::CleanupTaskFailed)??;
    let (lock, plan_sha256, transport) = spawned;
    let GuardianHostParts {
        control,
        stdin,
        stdout,
        stderr,
        guardian,
    } = transport.into_parts();
    let guardian_pid = guardian.id();
    let mut guardian_exit = spawn_guardian_wait(guardian);
    let mut control = into_tokio_stream(control)?;
    let stdin = into_tokio_stream(stdin)?;
    let stdout = into_tokio_stream(stdout)?;
    let stderr = into_tokio_stream(stderr)?;

    let bound = match tokio::time::timeout_at(deadline, read_control_frame(&mut control)).await {
        Ok(Ok(frame)) => match frame {
            GuardianFrameV2::Bound {
                guardian_pid: reported_guardian,
                worker_pid,
                worker_pgid,
                plan_sha256: reported_sha,
            } if reported_guardian == guardian_pid && reported_sha == plan_sha256 => {
                Ok(GuardianBinding {
                    guardian_pid,
                    worker_pid,
                    worker_pgid,
                    plan_sha256,
                })
            }
            _ => Err(StoryRenderSupervisorError::GuardianProtocolRejected),
        },
        Ok(Err(_)) | Err(_) => Err(StoryRenderSupervisorError::GuardianProtocolRejected),
    };
    let binding = match bound {
        Ok(binding) => binding,
        Err(error) => {
            drop(control);
            drop(stdin);
            drop(stdout);
            drop(stderr);
            let clean = reap_guardian_then_fallback(
                guardian_pid,
                None,
                &mut guardian_exit,
                config.termination_grace,
            )
            .await;
            if !clean {
                std::mem::forget(lock);
                return Err(StoryRenderSupervisorError::CleanupUnproven);
            }
            return Err(error);
        }
    };
    if write_control_frame(
        &mut control,
        GuardianFrameV2::Start {
            worker_pid: binding.worker_pid,
            worker_pgid: binding.worker_pgid,
            plan_sha256: binding.plan_sha256,
        },
    )
    .await
    .is_err()
    {
        drop(control);
        drop(stdin);
        drop(stdout);
        drop(stderr);
        let clean = reap_guardian_then_fallback(
            guardian_pid,
            Some(binding),
            &mut guardian_exit,
            config.termination_grace,
        )
        .await;
        if !clean {
            std::mem::forget(lock);
            return Err(StoryRenderSupervisorError::CleanupUnproven);
        }
        return Err(StoryRenderSupervisorError::GuardianProtocolRejected);
    }

    let (cancel_tx, cancel_rx) = oneshot::channel();
    let (result_tx, result_rx) = oneshot::channel();
    tokio::spawn(async move {
        let result = supervise_guardian(
            GuardianChannels {
                control,
                stdin,
                stdout,
                stderr,
                exit: guardian_exit,
            },
            binding,
            request,
            &config,
            deadline,
            cancel_rx,
            lock,
        )
        .await;
        let _ = result_tx.send(result);
    });
    Ok(StoryRenderRun {
        worker_pid: binding.worker_pid,
        cancel: Some(cancel_tx),
        result: result_rx,
    })
}

fn into_tokio_stream(
    stream: std::os::unix::net::UnixStream,
) -> Result<TokioUnixStream, StoryRenderSupervisorError> {
    stream
        .set_nonblocking(true)
        .map_err(|_| StoryRenderSupervisorError::GuardianProtocolRejected)?;
    TokioUnixStream::from_std(stream)
        .map_err(|_| StoryRenderSupervisorError::GuardianProtocolRejected)
}

fn spawn_guardian_wait(mut guardian: std::process::Child) -> watch::Receiver<Option<GuardianExit>> {
    let (sender, receiver) = watch::channel(None);
    tokio::task::spawn_blocking(move || {
        let status = guardian.wait().map_err(|_| ());
        let _ = sender.send(Some(status));
    });
    receiver
}

async fn wait_guardian(
    exit: &mut watch::Receiver<Option<GuardianExit>>,
) -> Result<ExitStatus, StoryRenderSupervisorError> {
    loop {
        if let Some(result) = *exit.borrow_and_update() {
            return result.map_err(|()| StoryRenderSupervisorError::GuardianLost);
        }
        exit.changed()
            .await
            .map_err(|_| StoryRenderSupervisorError::GuardianLost)?;
    }
}

async fn read_control_frame(
    control: &mut TokioUnixStream,
) -> Result<GuardianFrameV2, StoryRenderSupervisorError> {
    let mut length = [0_u8; 4];
    control.read_exact(&mut length).await.map_err(|error| {
        if error.kind() == io::ErrorKind::UnexpectedEof {
            StoryRenderSupervisorError::GuardianLost
        } else {
            StoryRenderSupervisorError::GuardianProtocolRejected
        }
    })?;
    let length = usize::try_from(u32::from_be_bytes(length))
        .map_err(|_| StoryRenderSupervisorError::GuardianProtocolRejected)?;
    if length > MAX_CONTROL_BODY_BYTES {
        return Err(StoryRenderSupervisorError::GuardianProtocolRejected);
    }
    let mut body = vec![0_u8; length];
    control
        .read_exact(&mut body)
        .await
        .map_err(|_| StoryRenderSupervisorError::GuardianProtocolRejected)?;
    decode_frame_body_v2(&body).map_err(|_| StoryRenderSupervisorError::GuardianProtocolRejected)
}

async fn write_control_frame(
    control: &mut TokioUnixStream,
    frame: GuardianFrameV2,
) -> Result<(), StoryRenderSupervisorError> {
    let encoded =
        encode_frame_v2(frame).map_err(|_| StoryRenderSupervisorError::GuardianProtocolRejected)?;
    control
        .write_all(&encoded)
        .await
        .map_err(|_| StoryRenderSupervisorError::GuardianProtocolRejected)
}

struct GuardianChannels {
    control: TokioUnixStream,
    stdin: TokioUnixStream,
    stdout: TokioUnixStream,
    stderr: TokioUnixStream,
    exit: watch::Receiver<Option<GuardianExit>>,
}

struct Captured {
    stdout: Vec<u8>,
    stderr: Vec<u8>,
    exit: WorkerExitV2,
}

enum Completion {
    Finished(Result<Captured, StoryRenderSupervisorError>),
    Cancelled,
    Deadline,
}

async fn supervise_guardian(
    channels: GuardianChannels,
    binding: GuardianBinding,
    request: Vec<u8>,
    config: &StoryRenderSupervisorConfig,
    deadline: Instant,
    mut cancel: oneshot::Receiver<()>,
    lock: HostLock,
) -> Result<StoryRenderOutput, StoryRenderSupervisorError> {
    let GuardianChannels {
        mut control,
        mut stdin,
        mut stdout,
        mut stderr,
        mut exit,
    } = channels;
    let completion = {
        let run = async {
            let write = async {
                stdin
                    .write_all(&request)
                    .await
                    .map_err(|_| StoryRenderSupervisorError::StdinWriteFailed)?;
                stdin
                    .shutdown()
                    .await
                    .map_err(|_| StoryRenderSupervisorError::StdinWriteFailed)
            };
            let read_stdout = read_bounded(
                &mut stdout,
                config.stdout_max_bytes,
                StoryRenderSupervisorError::StdoutLimitExceeded,
            );
            let read_stderr = read_bounded(
                &mut stderr,
                config.stderr_max_bytes,
                StoryRenderSupervisorError::StderrLimitExceeded,
            );
            let terminal = read_terminal(&mut control, binding);
            let guardian = wait_guardian(&mut exit);
            let ((), stdout, stderr, worker_exit, guardian_status) =
                tokio::try_join!(write, read_stdout, read_stderr, terminal, guardian)?;
            if !guardian_status.success() {
                return Err(StoryRenderSupervisorError::GuardianLost);
            }
            Ok(Captured {
                stdout,
                stderr,
                exit: worker_exit,
            })
        };
        tokio::pin!(run);
        tokio::select! {
            biased;
            _ = &mut cancel => Completion::Cancelled,
            _ = tokio::time::sleep_until(deadline) => Completion::Deadline,
            result = &mut run => Completion::Finished(result),
        }
    };
    let (outcome, terminal_clean) = match completion {
        Completion::Finished(Ok(captured)) => (validate_captured(captured, config), true),
        Completion::Finished(Err(error)) => (Err(error), false),
        Completion::Cancelled => (Err(StoryRenderSupervisorError::Cancelled), false),
        Completion::Deadline => (Err(StoryRenderSupervisorError::DeadlineExceeded), false),
    };
    if terminal_clean {
        drop(lock);
        return outcome;
    }

    drop(stdin);
    drop(stdout);
    drop(stderr);
    let clean = cleanup_guardian(&mut control, binding, &mut exit, config.termination_grace).await;
    if clean {
        drop(lock);
        outcome
    } else {
        std::mem::forget(lock);
        Err(StoryRenderSupervisorError::CleanupUnproven)
    }
}

fn validate_captured(
    captured: Captured,
    config: &StoryRenderSupervisorConfig,
) -> Result<StoryRenderOutput, StoryRenderSupervisorError> {
    let status_code = match captured.exit {
        WorkerExitV2::Exited(0) => Some(0),
        WorkerExitV2::Exited(_) | WorkerExitV2::Signaled(_) => {
            return Err(StoryRenderSupervisorError::WorkerFailed);
        }
    };
    if captured.stdout.is_empty() {
        return Err(StoryRenderSupervisorError::WorkerExitWithoutResponse);
    }
    if !(config.response_validator)(&captured.stdout) {
        return Err(StoryRenderSupervisorError::ResponseRejected);
    }
    Ok(StoryRenderOutput {
        status_code,
        stdout: captured.stdout,
        stderr: captured.stderr,
    })
}

async fn read_terminal(
    control: &mut TokioUnixStream,
    binding: GuardianBinding,
) -> Result<WorkerExitV2, StoryRenderSupervisorError> {
    match read_control_frame(control).await? {
        GuardianFrameV2::Terminal {
            worker_pid,
            worker_pgid,
            exit,
        } if worker_pid == binding.worker_pid && worker_pgid == binding.worker_pgid => Ok(exit),
        GuardianFrameV2::Failure {
            stage,
            failure,
            worker_pid,
            worker_pgid,
        } if (worker_pid == 0 && worker_pgid == 0)
            || (worker_pid == binding.worker_pid && worker_pgid == binding.worker_pgid) =>
        {
            Err(map_guardian_failure(stage, failure))
        }
        _ => Err(StoryRenderSupervisorError::GuardianProtocolRejected),
    }
}

fn map_guardian_failure(
    stage: GuardianStageV2,
    failure: GuardianFailureV2,
) -> StoryRenderSupervisorError {
    match (stage, failure) {
        (GuardianStageV2::Plan, GuardianFailureV2::InvalidPlan) => {
            StoryRenderSupervisorError::InvalidConfiguration
        }
        (GuardianStageV2::WorkerSpawn, GuardianFailureV2::SpawnFailed) => {
            StoryRenderSupervisorError::SpawnFailed
        }
        (_, GuardianFailureV2::CleanupUnproven) => StoryRenderSupervisorError::CleanupUnproven,
        (GuardianStageV2::Cleanup, GuardianFailureV2::WorkerExitedWithLiveGroup) => {
            StoryRenderSupervisorError::WorkerFailed
        }
        (GuardianStageV2::Protocol, _) => StoryRenderSupervisorError::GuardianProtocolRejected,
        _ => StoryRenderSupervisorError::GuardianLost,
    }
}

async fn cleanup_guardian(
    control: &mut TokioUnixStream,
    binding: GuardianBinding,
    exit: &mut watch::Receiver<Option<GuardianExit>>,
    grace: Duration,
) -> bool {
    let _ = write_control_frame(
        control,
        GuardianFrameV2::Cancel {
            worker_pid: binding.worker_pid,
            worker_pgid: binding.worker_pgid,
        },
    )
    .await;
    let terminal = tokio::time::timeout(grace + FALLBACK_TIMEOUT, read_terminal(control, binding))
        .await
        .is_ok_and(|result| result.is_ok());
    let guardian = wait_exact_guardian(binding.guardian_pid, exit).await;
    if terminal && guardian.is_some_and(|status| status.success()) {
        return true;
    }
    guardian.is_some() && fallback_group_cleanup(binding.worker_pgid, grace).await
}

async fn reap_guardian_then_fallback(
    guardian_pid: u32,
    binding: Option<GuardianBinding>,
    exit: &mut watch::Receiver<Option<GuardianExit>>,
    grace: Duration,
) -> bool {
    let guardian = wait_exact_guardian(guardian_pid, exit).await;
    match binding {
        Some(binding) => {
            guardian.is_some() && fallback_group_cleanup(binding.worker_pgid, grace).await
        }
        None => guardian.is_some(),
    }
}

async fn wait_exact_guardian(
    guardian_pid: u32,
    exit: &mut watch::Receiver<Option<GuardianExit>>,
) -> Option<ExitStatus> {
    if let Ok(result) = tokio::time::timeout(FALLBACK_TIMEOUT, wait_guardian(exit)).await {
        return result.ok();
    }
    let _ = signal_process(guardian_pid, libc::SIGKILL);
    tokio::time::timeout(FALLBACK_TIMEOUT, wait_guardian(exit))
        .await
        .ok()
        .and_then(Result::ok)
}

async fn fallback_group_cleanup(pgid: u32, grace: Duration) -> bool {
    if signal_group(pgid, libc::SIGTERM).is_err() {
        return false;
    }
    tokio::time::sleep(grace).await;
    if signal_group(pgid, libc::SIGKILL).is_err() {
        return false;
    }
    let deadline = Instant::now() + FALLBACK_TIMEOUT;
    loop {
        if !process_group_exists(pgid) {
            return true;
        }
        if Instant::now() >= deadline {
            return false;
        }
        tokio::time::sleep(Duration::from_millis(10)).await;
    }
}

fn signal_process(pid: u32, signal: libc::c_int) -> Result<(), ()> {
    if pid <= 1 || pid > i32::MAX as u32 {
        return Err(());
    }
    let result = unsafe { libc::kill(pid as libc::pid_t, signal) };
    if result == 0 || io::Error::last_os_error().raw_os_error() == Some(libc::ESRCH) {
        Ok(())
    } else {
        Err(())
    }
}

fn process_group_exists(pgid: u32) -> bool {
    if pgid <= 1 || pgid > i32::MAX as u32 {
        return true;
    }
    let result = unsafe { libc::kill(-(pgid as libc::pid_t), 0) };
    result == 0 || io::Error::last_os_error().raw_os_error() == Some(libc::EPERM)
}

async fn read_bounded<R: AsyncRead + Unpin>(
    reader: &mut R,
    maximum: usize,
    overflow: StoryRenderSupervisorError,
) -> Result<Vec<u8>, StoryRenderSupervisorError> {
    let mut output = Vec::new();
    let mut chunk = [0_u8; 8_192];
    loop {
        let count = reader
            .read(&mut chunk)
            .await
            .map_err(|_| StoryRenderSupervisorError::WorkerWaitFailed)?;
        if count == 0 {
            return Ok(output);
        }
        if output.len().saturating_add(count) > maximum {
            return Err(overflow);
        }
        output.extend_from_slice(&chunk[..count]);
    }
}
