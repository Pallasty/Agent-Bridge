//! Synthetic-only Story render process supervisor.
//!
//! DirectV1 remains the default rollback path. GuardianV2 is configuration-
//! injected and default-off; neither mode has a product runtime caller here.

#![deny(clippy::all)]

use std::collections::BTreeMap;
use std::ffi::OsString;
use std::fs::{File, OpenOptions};
use std::future::Future;
use std::io;
use std::os::fd::AsRawFd;
use std::os::unix::fs::{MetadataExt, OpenOptionsExt};
use std::os::unix::process::CommandExt;
use std::path::{Path, PathBuf};
use std::pin::Pin;
use std::process::Stdio;
use std::sync::Arc;
use std::task::{Context, Poll};
use std::time::Duration;

use tokio::io::{AsyncRead, AsyncReadExt, AsyncWriteExt};
use tokio::process::{Child, ChildStderr, ChildStdin, ChildStdout, Command};
use tokio::sync::oneshot;

use crate::story_render_guardian::GuardianLaunchSpec;
use crate::story_render_guardian_supervision::start_guardian_supervision;

pub type ResponseValidator = Arc<dyn Fn(&[u8]) -> bool + Send + Sync + 'static>;

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum StoryRenderCustodyMode {
    DirectV1,
    GuardianV2(GuardianLaunchSpec),
}

#[derive(Clone)]
pub struct StoryRenderSupervisorConfig {
    pub executable: PathBuf,
    pub script: PathBuf,
    pub arguments: Vec<OsString>,
    pub lock_path: PathBuf,
    pub stdin_max_bytes: usize,
    pub stdout_max_bytes: usize,
    pub stderr_max_bytes: usize,
    pub deadline: Duration,
    pub termination_grace: Duration,
    pub environment: BTreeMap<String, String>,
    pub response_validator: ResponseValidator,
    pub custody_mode: StoryRenderCustodyMode,
}

impl StoryRenderSupervisorConfig {
    pub fn s620_synthetic(executable: PathBuf, script: PathBuf, lock_path: PathBuf) -> Self {
        Self {
            executable,
            script,
            arguments: Vec::new(),
            lock_path,
            stdin_max_bytes: 65_536,
            stdout_max_bytes: 65_536,
            stderr_max_bytes: 16_384,
            deadline: Duration::from_secs(300),
            termination_grace: Duration::from_secs(2),
            environment: s620_environment(),
            response_validator: Arc::new(|raw| {
                serde_json::from_slice::<serde_json::Value>(raw)
                    .is_ok_and(|value| value.is_object())
            }),
            custody_mode: StoryRenderCustodyMode::DirectV1,
        }
    }
}

fn s620_environment() -> BTreeMap<String, String> {
    BTreeMap::from([
        ("LANG".into(), "C.UTF-8".into()),
        ("LC_ALL".into(), "C.UTF-8".into()),
        ("TZ".into(), "UTC".into()),
        ("PYTHONNOUSERSITE".into(), "1".into()),
        ("PYTHONDONTWRITEBYTECODE".into(), "1".into()),
        ("HF_HUB_OFFLINE".into(), "1".into()),
        ("TRANSFORMERS_OFFLINE".into(), "1".into()),
        ("CUDA_VISIBLE_DEVICES".into(), "".into()),
        ("HIP_VISIBLE_DEVICES".into(), "".into()),
        ("ROCR_VISIBLE_DEVICES".into(), "".into()),
    ])
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, thiserror::Error)]
pub enum StoryRenderSupervisorError {
    #[error("invalid_configuration")]
    InvalidConfiguration,
    #[error("input_too_large")]
    InputTooLarge,
    #[error("lock_unavailable")]
    LockUnavailable,
    #[error("busy")]
    Busy,
    #[error("spawn_failed")]
    SpawnFailed,
    #[error("stdin_write_failed")]
    StdinWriteFailed,
    #[error("stdout_limit_exceeded")]
    StdoutLimitExceeded,
    #[error("stderr_limit_exceeded")]
    StderrLimitExceeded,
    #[error("worker_wait_failed")]
    WorkerWaitFailed,
    #[error("worker_failed")]
    WorkerFailed,
    #[error("worker_exit_without_response")]
    WorkerExitWithoutResponse,
    #[error("response_rejected")]
    ResponseRejected,
    #[error("deadline_exceeded")]
    DeadlineExceeded,
    #[error("cancelled")]
    Cancelled,
    #[error("signal_failed")]
    SignalFailed,
    #[error("cleanup_task_failed")]
    CleanupTaskFailed,
    #[error("guardian_spawn_failed")]
    GuardianSpawnFailed,
    #[error("guardian_protocol_rejected")]
    GuardianProtocolRejected,
    #[error("guardian_lost")]
    GuardianLost,
    #[error("cleanup_unproven")]
    CleanupUnproven,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct StoryRenderOutput {
    pub status_code: Option<i32>,
    pub stdout: Vec<u8>,
    pub stderr: Vec<u8>,
}

pub struct StoryRenderRun {
    pub(crate) worker_pid: u32,
    pub(crate) cancel: Option<oneshot::Sender<()>>,
    pub(crate) result: oneshot::Receiver<Result<StoryRenderOutput, StoryRenderSupervisorError>>,
}

pub struct StoryRenderAdmission {
    config: StoryRenderSupervisorConfig,
    lock: HostLock,
}

impl StoryRenderAdmission {
    pub fn bind_response_validator(&mut self, response_validator: ResponseValidator) {
        self.config.response_validator = response_validator;
    }

    pub async fn start(
        self,
        request: Vec<u8>,
    ) -> Result<StoryRenderRun, StoryRenderSupervisorError> {
        if request.len() > self.config.stdin_max_bytes {
            return Err(StoryRenderSupervisorError::InputTooLarge);
        }
        start_with_lock(self.config, request, self.lock).await
    }
}

impl StoryRenderRun {
    pub fn worker_pid(&self) -> u32 {
        self.worker_pid
    }
}

impl Future for StoryRenderRun {
    type Output = Result<StoryRenderOutput, StoryRenderSupervisorError>;

    fn poll(mut self: Pin<&mut Self>, context: &mut Context<'_>) -> Poll<Self::Output> {
        match Pin::new(&mut self.result).poll(context) {
            Poll::Ready(Ok(result)) => {
                self.cancel.take();
                Poll::Ready(result)
            }
            Poll::Ready(Err(_)) => {
                self.cancel.take();
                Poll::Ready(Err(StoryRenderSupervisorError::CleanupTaskFailed))
            }
            Poll::Pending => Poll::Pending,
        }
    }
}

impl Drop for StoryRenderRun {
    fn drop(&mut self) {
        if let Some(cancel) = self.cancel.take() {
            let _ = cancel.send(());
        }
    }
}

pub async fn start_story_render_supervisor(
    config: StoryRenderSupervisorConfig,
    request: Vec<u8>,
) -> Result<StoryRenderRun, StoryRenderSupervisorError> {
    require_runtime()?;
    validate_config(&config)?;
    if request.len() > config.stdin_max_bytes {
        return Err(StoryRenderSupervisorError::InputTooLarge);
    }
    let lock = acquire_lock(&config.lock_path)?;
    start_with_lock(config, request, lock).await
}

pub fn begin_story_render_admission(
    config: StoryRenderSupervisorConfig,
) -> Result<StoryRenderAdmission, StoryRenderSupervisorError> {
    require_runtime()?;
    validate_config(&config)?;
    let lock = acquire_lock(&config.lock_path)?;
    Ok(StoryRenderAdmission { config, lock })
}

fn require_runtime() -> Result<(), StoryRenderSupervisorError> {
    tokio::runtime::Handle::try_current()
        .map(|_| ())
        .map_err(|_| StoryRenderSupervisorError::InvalidConfiguration)
}

async fn start_with_lock(
    config: StoryRenderSupervisorConfig,
    request: Vec<u8>,
    lock: HostLock,
) -> Result<StoryRenderRun, StoryRenderSupervisorError> {
    match config.custody_mode.clone() {
        StoryRenderCustodyMode::DirectV1 => start_direct_with_lock(config, request, lock),
        StoryRenderCustodyMode::GuardianV2(launch) => {
            start_guardian_supervision(config, request, lock, launch).await
        }
    }
}

fn start_direct_with_lock(
    config: StoryRenderSupervisorConfig,
    request: Vec<u8>,
    lock: HostLock,
) -> Result<StoryRenderRun, StoryRenderSupervisorError> {
    let mut child = spawn_worker(&config).map_err(|_| StoryRenderSupervisorError::SpawnFailed)?;
    let worker_pid = child.id().ok_or(StoryRenderSupervisorError::SpawnFailed)?;
    let stdin = child
        .stdin
        .take()
        .ok_or(StoryRenderSupervisorError::SpawnFailed)?;
    let stdout = child
        .stdout
        .take()
        .ok_or(StoryRenderSupervisorError::SpawnFailed)?;
    let stderr = child
        .stderr
        .take()
        .ok_or(StoryRenderSupervisorError::SpawnFailed)?;
    let (cancel_tx, cancel_rx) = oneshot::channel();
    let (result_tx, result_rx) = oneshot::channel();
    let worker = SupervisedWorker {
        child,
        stdin,
        stdout,
        stderr,
        worker_pid,
    };
    tokio::spawn(async move {
        let result = supervise_worker(worker, request, &config, cancel_rx).await;
        drop(lock);
        let _ = result_tx.send(result);
    });
    Ok(StoryRenderRun {
        worker_pid,
        cancel: Some(cancel_tx),
        result: result_rx,
    })
}

fn validate_config(config: &StoryRenderSupervisorConfig) -> Result<(), StoryRenderSupervisorError> {
    if !config.executable.is_absolute()
        || !config.script.is_absolute()
        || !config.lock_path.is_absolute()
        || !config.script.is_file()
        || config.stdin_max_bytes != 65_536
        || config.stdout_max_bytes != 65_536
        || config.stderr_max_bytes != 16_384
        || config.deadline.is_zero()
        || config.termination_grace.is_zero()
        || config.environment != s620_environment()
    {
        return Err(StoryRenderSupervisorError::InvalidConfiguration);
    }
    Ok(())
}

pub(crate) struct HostLock(pub(crate) File);

impl Drop for HostLock {
    fn drop(&mut self) {
        // A failed fork/exec can briefly leave this file descriptor inherited by
        // the child. Explicitly unlock the shared file description before close
        // so a later request is not reported busy until that child exits.
        loop {
            let result = unsafe { libc::flock(self.0.as_raw_fd(), libc::LOCK_UN) };
            if result == 0 || io::Error::last_os_error().kind() != io::ErrorKind::Interrupted {
                break;
            }
        }
    }
}

pub(crate) fn acquire_lock(path: &Path) -> Result<HostLock, StoryRenderSupervisorError> {
    let file = OpenOptions::new()
        .read(true)
        .write(true)
        .create(true)
        .mode(0o600)
        .custom_flags(libc::O_CLOEXEC | libc::O_NOFOLLOW)
        .open(path)
        .map_err(|_| StoryRenderSupervisorError::LockUnavailable)?;
    let metadata = file
        .metadata()
        .map_err(|_| StoryRenderSupervisorError::LockUnavailable)?;
    if !metadata.is_file() || metadata.mode() & 0o777 != 0o600 || metadata.nlink() != 1 {
        return Err(StoryRenderSupervisorError::LockUnavailable);
    }
    let result = unsafe { libc::flock(file.as_raw_fd(), libc::LOCK_EX | libc::LOCK_NB) };
    if result == 0 {
        return Ok(HostLock(file));
    }
    let error = io::Error::last_os_error();
    if matches!(error.raw_os_error(), Some(code) if code == libc::EAGAIN || code == libc::EWOULDBLOCK)
    {
        Err(StoryRenderSupervisorError::Busy)
    } else {
        Err(StoryRenderSupervisorError::LockUnavailable)
    }
}

fn spawn_worker(config: &StoryRenderSupervisorConfig) -> io::Result<Child> {
    let mut command = Command::new(&config.executable);
    command
        .arg(&config.script)
        .args(&config.arguments)
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .env_clear()
        .envs(&config.environment)
        .current_dir("/")
        .kill_on_drop(true);
    let parent_pid = unsafe { libc::getpid() };
    unsafe {
        command.as_std_mut().pre_exec(move || {
            if libc::prctl(libc::PR_SET_PDEATHSIG, libc::SIGKILL) == -1 {
                return Err(io::Error::last_os_error());
            }
            if libc::getppid() != parent_pid {
                return Err(io::Error::other("parent changed"));
            }
            if libc::setsid() == -1 {
                return Err(io::Error::last_os_error());
            }
            Ok(())
        });
    }
    command.spawn()
}

enum Completion {
    Finished(Result<StoryRenderOutput, StoryRenderSupervisorError>),
    Cancelled,
    Deadline,
}

struct SupervisedWorker {
    child: Child,
    stdin: ChildStdin,
    stdout: ChildStdout,
    stderr: ChildStderr,
    worker_pid: u32,
}

async fn supervise_worker(
    worker: SupervisedWorker,
    request: Vec<u8>,
    config: &StoryRenderSupervisorConfig,
    mut cancel: oneshot::Receiver<()>,
) -> Result<StoryRenderOutput, StoryRenderSupervisorError> {
    let SupervisedWorker {
        mut child,
        mut stdin,
        mut stdout,
        mut stderr,
        worker_pid,
    } = worker;
    let completion = {
        let run = async {
            let write = async move {
                stdin
                    .write_all(&request)
                    .await
                    .map_err(|_| StoryRenderSupervisorError::StdinWriteFailed)?;
                stdin
                    .shutdown()
                    .await
                    .map_err(|_| StoryRenderSupervisorError::StdinWriteFailed)?;
                drop(stdin);
                Ok(())
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
            let wait = async {
                child
                    .wait()
                    .await
                    .map_err(|_| StoryRenderSupervisorError::WorkerWaitFailed)
            };
            let ((), stdout, stderr, status) =
                tokio::try_join!(write, read_stdout, read_stderr, wait)?;
            if !status.success() {
                return Err(StoryRenderSupervisorError::WorkerFailed);
            }
            if stdout.is_empty() {
                return Err(StoryRenderSupervisorError::WorkerExitWithoutResponse);
            }
            if !(config.response_validator)(&stdout) {
                return Err(StoryRenderSupervisorError::ResponseRejected);
            }
            Ok(StoryRenderOutput {
                status_code: status.code(),
                stdout,
                stderr,
            })
        };
        tokio::pin!(run);
        tokio::select! {
            biased;
            _ = &mut cancel => Completion::Cancelled,
            _ = tokio::time::sleep(config.deadline) => Completion::Deadline,
            result = &mut run => Completion::Finished(result),
        }
    };

    match completion {
        Completion::Finished(Ok(output)) => Ok(output),
        Completion::Finished(Err(error)) => {
            if matches!(
                error,
                StoryRenderSupervisorError::StdinWriteFailed
                    | StoryRenderSupervisorError::StdoutLimitExceeded
                    | StoryRenderSupervisorError::StderrLimitExceeded
                    | StoryRenderSupervisorError::WorkerWaitFailed
            ) {
                terminate_and_wait(&mut child, worker_pid, config.termination_grace).await?;
            }
            Err(error)
        }
        Completion::Cancelled => {
            terminate_and_wait(&mut child, worker_pid, config.termination_grace).await?;
            Err(StoryRenderSupervisorError::Cancelled)
        }
        Completion::Deadline => {
            terminate_and_wait(&mut child, worker_pid, config.termination_grace).await?;
            Err(StoryRenderSupervisorError::DeadlineExceeded)
        }
    }
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

async fn terminate_and_wait(
    child: &mut Child,
    worker_pid: u32,
    grace: Duration,
) -> Result<(), StoryRenderSupervisorError> {
    let term_result = signal_group(worker_pid, libc::SIGTERM);
    tokio::time::sleep(grace).await;
    let kill_result = signal_group(worker_pid, libc::SIGKILL);
    child
        .wait()
        .await
        .map_err(|_| StoryRenderSupervisorError::WorkerWaitFailed)?;
    term_result?;
    kill_result?;
    Ok(())
}

pub(crate) fn signal_group(
    pid: u32,
    signal: libc::c_int,
) -> Result<(), StoryRenderSupervisorError> {
    if pid <= 1 || pid > i32::MAX as u32 {
        return Err(StoryRenderSupervisorError::SignalFailed);
    }
    let result = unsafe { libc::kill(-(pid as libc::pid_t), signal) };
    if result == 0 {
        return Ok(());
    }
    let error = io::Error::last_os_error();
    if error.raw_os_error() == Some(libc::ESRCH) {
        Ok(())
    } else {
        Err(StoryRenderSupervisorError::SignalFailed)
    }
}
