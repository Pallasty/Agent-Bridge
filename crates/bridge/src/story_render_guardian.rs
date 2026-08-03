//! Dormant S635 generic GuardianV2 process custody.
//!
//! The Host-side launcher is configuration-injected and the process entrypoint
//! is not called by any product binary. This module owns only inherited-fd
//! transport and one-process-group synthetic custody.

#![deny(clippy::all)]

use std::ffi::OsString;
use std::fs::File;
use std::io::{self, Read, Write};
use std::os::fd::{AsRawFd, FromRawFd, RawFd};
use std::os::unix::fs::MetadataExt;
use std::os::unix::net::UnixStream;
use std::os::unix::process::{CommandExt, ExitStatusExt};
use std::path::PathBuf;
use std::process::{Child, Command, ExitStatus, Stdio};
use std::thread;
use std::time::{Duration, Instant};

use crate::story_render_guardian_protocol::{
    read_frame_v2, read_sealed_exec_plan, write_frame_v2, ExecPlanError, GuardianFailureV2,
    GuardianFrameV2, GuardianStageV2, ProtocolV2Error, SealedExecPlan, WorkerExecPlanV1,
    WorkerExitV2,
};

const ROLE_ENV: &str = "AB_STORY_RENDER_GUARDIAN_V2_ROLE";
const ROLE_GUARDIAN: &str = "guardian";
const ROLE_BOOTSTRAP: &str = "bootstrap";
const ENTRYPOINT_ERROR_EXIT: i32 = 76;
const GUARDIAN_LOCK_FD: RawFd = 190;
const GUARDIAN_CONTROL_FD: RawFd = 191;
const GUARDIAN_PLAN_FD: RawFd = 192;
const WORKER_STDIN_FD: RawFd = 193;
const WORKER_STDOUT_FD: RawFd = 194;
const WORKER_STDERR_FD: RawFd = 195;
const WORKER_GATE_FD: RawFd = 196;
const WORKER_EXEC_STATUS_FD: RawFd = 197;
const CONTROL_TIMEOUT: Duration = Duration::from_secs(5);
const CLEANUP_TIMEOUT: Duration = Duration::from_secs(5);

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct GuardianLaunchSpec {
    pub executable: PathBuf,
    pub arguments: Vec<OsString>,
}

impl GuardianLaunchSpec {
    fn validate(&self) -> Result<(), GuardianRuntimeError> {
        if !self.executable.is_absolute()
            || self.arguments.len() > 32
            || self.arguments.iter().any(|argument| argument.len() > 4_096)
        {
            return Err(GuardianRuntimeError::InvalidConfiguration);
        }
        Ok(())
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, thiserror::Error)]
pub enum GuardianRuntimeError {
    #[error("invalid_configuration")]
    InvalidConfiguration,
    #[error("protocol")]
    Protocol,
    #[error("plan")]
    Plan,
    #[error("io")]
    Io,
    #[error("spawn")]
    Spawn,
    #[error("wait")]
    Wait,
    #[error("signal")]
    Signal,
}

impl From<ProtocolV2Error> for GuardianRuntimeError {
    fn from(_: ProtocolV2Error) -> Self {
        Self::Protocol
    }
}

impl From<ExecPlanError> for GuardianRuntimeError {
    fn from(_: ExecPlanError) -> Self {
        Self::Plan
    }
}

pub struct GuardianHostTransport {
    control: UnixStream,
    stdin: UnixStream,
    stdout: UnixStream,
    stderr: UnixStream,
    guardian: Child,
}

pub struct GuardianHostParts {
    pub control: UnixStream,
    pub stdin: UnixStream,
    pub stdout: UnixStream,
    pub stderr: UnixStream,
    pub guardian: Child,
}

impl GuardianHostTransport {
    pub fn guardian_pid(&self) -> u32 {
        self.guardian.id()
    }

    pub fn control_mut(&mut self) -> &mut UnixStream {
        &mut self.control
    }

    pub fn stdin_mut(&mut self) -> &mut UnixStream {
        &mut self.stdin
    }

    pub fn stdout_mut(&mut self) -> &mut UnixStream {
        &mut self.stdout
    }

    pub fn stderr_mut(&mut self) -> &mut UnixStream {
        &mut self.stderr
    }

    pub fn finish_stdin(&self) -> Result<(), GuardianRuntimeError> {
        self.stdin
            .shutdown(std::net::Shutdown::Write)
            .map_err(|_| GuardianRuntimeError::Io)
    }

    pub fn wait_guardian(&mut self) -> Result<ExitStatus, GuardianRuntimeError> {
        self.guardian.wait().map_err(|_| GuardianRuntimeError::Wait)
    }

    pub fn into_parts(self) -> GuardianHostParts {
        GuardianHostParts {
            control: self.control,
            stdin: self.stdin,
            stdout: self.stdout,
            stderr: self.stderr,
            guardian: self.guardian,
        }
    }
}

pub fn spawn_guardian_v2(
    lock: &File,
    plan: &SealedExecPlan,
    launch: &GuardianLaunchSpec,
) -> Result<GuardianHostTransport, GuardianRuntimeError> {
    launch.validate()?;
    validate_lock_file(lock)?;
    let (host_control, guardian_control) = socket_pair()?;
    let (host_stdin, worker_stdin) = socket_pair()?;
    let (host_stdout, worker_stdout) = socket_pair()?;
    let (host_stderr, worker_stderr) = socket_pair()?;

    host_stdin
        .shutdown(std::net::Shutdown::Read)
        .map_err(|_| GuardianRuntimeError::Io)?;
    worker_stdin
        .shutdown(std::net::Shutdown::Write)
        .map_err(|_| GuardianRuntimeError::Io)?;
    host_stdout
        .shutdown(std::net::Shutdown::Write)
        .map_err(|_| GuardianRuntimeError::Io)?;
    worker_stdout
        .shutdown(std::net::Shutdown::Read)
        .map_err(|_| GuardianRuntimeError::Io)?;
    host_stderr
        .shutdown(std::net::Shutdown::Write)
        .map_err(|_| GuardianRuntimeError::Io)?;
    worker_stderr
        .shutdown(std::net::Shutdown::Read)
        .map_err(|_| GuardianRuntimeError::Io)?;

    host_control
        .set_read_timeout(Some(CONTROL_TIMEOUT))
        .map_err(|_| GuardianRuntimeError::Io)?;
    host_control
        .set_write_timeout(Some(CONTROL_TIMEOUT))
        .map_err(|_| GuardianRuntimeError::Io)?;

    let mut command = Command::new(&launch.executable);
    command
        .args(&launch.arguments)
        .stdin(Stdio::null())
        .stdout(Stdio::null())
        .stderr(Stdio::null())
        .env_clear()
        .env(ROLE_ENV, ROLE_GUARDIAN)
        .current_dir("/");
    let inherited = [
        (lock.as_raw_fd(), GUARDIAN_LOCK_FD),
        (guardian_control.as_raw_fd(), GUARDIAN_CONTROL_FD),
        (plan.as_raw_fd(), GUARDIAN_PLAN_FD),
        (worker_stdin.as_raw_fd(), WORKER_STDIN_FD),
        (worker_stdout.as_raw_fd(), WORKER_STDOUT_FD),
        (worker_stderr.as_raw_fd(), WORKER_STDERR_FD),
    ];
    unsafe {
        // SAFETY: the closure performs only descriptor duplication between
        // fork and exec. Every source descriptor remains open until spawn
        // returns, and fixed targets are unique to this dedicated child.
        command.pre_exec(move || {
            for (source, target) in inherited {
                dup_to_fixed(source, target)?;
            }
            Ok(())
        });
    }
    let guardian = command.spawn().map_err(|_| GuardianRuntimeError::Spawn)?;
    drop(guardian_control);
    drop(worker_stdin);
    drop(worker_stdout);
    drop(worker_stderr);
    Ok(GuardianHostTransport {
        control: host_control,
        stdin: host_stdin,
        stdout: host_stdout,
        stderr: host_stderr,
        guardian,
    })
}

fn socket_pair() -> Result<(UnixStream, UnixStream), GuardianRuntimeError> {
    let pair = UnixStream::pair().map_err(|_| GuardianRuntimeError::Io)?;
    set_cloexec(pair.0.as_raw_fd(), true).map_err(|_| GuardianRuntimeError::Io)?;
    set_cloexec(pair.1.as_raw_fd(), true).map_err(|_| GuardianRuntimeError::Io)?;
    Ok(pair)
}

fn set_cloexec(fd: RawFd, enabled: bool) -> io::Result<()> {
    let current = unsafe {
        // SAFETY: F_GETFD reads flags from the supplied descriptor.
        libc::fcntl(fd, libc::F_GETFD)
    };
    if current == -1 {
        return Err(io::Error::last_os_error());
    }
    let updated = if enabled {
        current | libc::FD_CLOEXEC
    } else {
        current & !libc::FD_CLOEXEC
    };
    if unsafe {
        // SAFETY: F_SETFD writes descriptor flags and retains no pointers.
        libc::fcntl(fd, libc::F_SETFD, updated)
    } == -1
    {
        return Err(io::Error::last_os_error());
    }
    Ok(())
}

fn dup_to_fixed(source: RawFd, target: RawFd) -> io::Result<()> {
    if source == target {
        return set_cloexec(target, false);
    }
    if unsafe {
        // SAFETY: source is valid in the child; dup3 atomically replaces the
        // dedicated target and returns it without close-on-exec.
        libc::dup3(source, target, 0)
    } == -1
    {
        return Err(io::Error::last_os_error());
    }
    Ok(())
}

fn validate_lock_file(lock: &File) -> Result<(), GuardianRuntimeError> {
    let metadata = lock.metadata().map_err(|_| GuardianRuntimeError::Io)?;
    if !metadata.is_file() || metadata.mode() & 0o777 != 0o600 || metadata.nlink() != 1 {
        return Err(GuardianRuntimeError::InvalidConfiguration);
    }
    Ok(())
}

pub fn run_guardian_entrypoint() -> Option<i32> {
    let role = std::env::var(ROLE_ENV).ok()?;
    let result = match role.as_str() {
        ROLE_GUARDIAN => run_guardian_role(),
        ROLE_BOOTSTRAP => run_bootstrap_role(),
        _ => Err(GuardianRuntimeError::InvalidConfiguration),
    };
    Some(if result.is_ok() {
        0
    } else {
        ENTRYPOINT_ERROR_EXIT
    })
}

fn inherited_file(fd: RawFd) -> File {
    unsafe {
        // SAFETY: each fixed descriptor is installed exactly once by the
        // parent and ownership transfers to this entrypoint process.
        File::from_raw_fd(fd)
    }
}

fn inherited_stream(fd: RawFd) -> UnixStream {
    unsafe {
        // SAFETY: the fixed socket descriptor is installed exactly once by
        // the parent and ownership transfers to this entrypoint process.
        UnixStream::from_raw_fd(fd)
    }
}

fn run_guardian_role() -> Result<(), GuardianRuntimeError> {
    let lock = inherited_file(GUARDIAN_LOCK_FD);
    let mut control = inherited_stream(GUARDIAN_CONTROL_FD);
    let plan_file = inherited_file(GUARDIAN_PLAN_FD);
    let worker_stdin = inherited_file(WORKER_STDIN_FD);
    let worker_stdout = inherited_file(WORKER_STDOUT_FD);
    let worker_stderr = inherited_file(WORKER_STDERR_FD);
    for fd in [
        lock.as_raw_fd(),
        control.as_raw_fd(),
        plan_file.as_raw_fd(),
        worker_stdin.as_raw_fd(),
        worker_stdout.as_raw_fd(),
        worker_stderr.as_raw_fd(),
    ] {
        set_cloexec(fd, true).map_err(|_| GuardianRuntimeError::Io)?;
    }
    validate_lock_file(&lock)?;
    control
        .set_read_timeout(Some(CONTROL_TIMEOUT))
        .map_err(|_| GuardianRuntimeError::Io)?;
    control
        .set_write_timeout(Some(CONTROL_TIMEOUT))
        .map_err(|_| GuardianRuntimeError::Io)?;
    if unsafe {
        // SAFETY: this is a dedicated single-threaded Guardian process.
        libc::prctl(libc::PR_SET_CHILD_SUBREAPER, 1)
    } == -1
    {
        return Err(GuardianRuntimeError::Io);
    }
    let decoded = match read_sealed_exec_plan(&plan_file) {
        Ok(decoded) => decoded,
        Err(_) => {
            let _ = write_frame_v2(
                &mut control,
                GuardianFrameV2::Failure {
                    stage: GuardianStageV2::Plan,
                    failure: GuardianFailureV2::InvalidPlan,
                    worker_pid: 0,
                    worker_pgid: 0,
                },
            );
            return Err(GuardianRuntimeError::Plan);
        }
    };
    let (mut worker, mut gate, mut exec_status) =
        match spawn_bootstrap(&plan_file, worker_stdin, worker_stdout, worker_stderr) {
            Ok(value) => value,
            Err(error) => {
                let _ = write_frame_v2(
                    &mut control,
                    GuardianFrameV2::Failure {
                        stage: GuardianStageV2::WorkerSpawn,
                        failure: GuardianFailureV2::SpawnFailed,
                        worker_pid: 0,
                        worker_pgid: 0,
                    },
                );
                return Err(error);
            }
        };
    let guardian_pid = std::process::id();
    let worker_pid = worker.id();
    let binding = (worker_pid, worker_pid);
    write_frame_v2(
        &mut control,
        GuardianFrameV2::Bound {
            guardian_pid,
            worker_pid,
            worker_pgid: worker_pid,
            plan_sha256: decoded.sha256,
        },
    )?;
    match read_frame_v2(&mut control) {
        Ok(GuardianFrameV2::Start {
            worker_pid: acknowledged_pid,
            worker_pgid: acknowledged_pgid,
            plan_sha256,
        }) if (acknowledged_pid, acknowledged_pgid) == binding && plan_sha256 == decoded.sha256 => {
            gate.write_all(&[1]).map_err(|_| GuardianRuntimeError::Io)?;
            drop(gate);
        }
        _ => {
            let _ = write_frame_v2(
                &mut control,
                GuardianFrameV2::Failure {
                    stage: GuardianStageV2::Protocol,
                    failure: GuardianFailureV2::ProtocolRejected,
                    worker_pid,
                    worker_pgid: worker_pid,
                },
            );
            cleanup_or_hold(&mut worker, worker_pid, &lock, None);
        }
    }
    let mut exec_result = Vec::with_capacity(1);
    exec_status
        .read_to_end(&mut exec_result)
        .map_err(|_| GuardianRuntimeError::Io)?;
    match exec_result.as_slice() {
        [] => {}
        [1] => {
            worker.wait().map_err(|_| GuardianRuntimeError::Wait)?;
            cleanup_residual_group_or_hold(worker_pid, &lock);
            write_frame_v2(
                &mut control,
                GuardianFrameV2::Failure {
                    stage: GuardianStageV2::WorkerSpawn,
                    failure: GuardianFailureV2::SpawnFailed,
                    worker_pid,
                    worker_pgid: worker_pid,
                },
            )?;
            return Ok(());
        }
        _ => cleanup_or_hold(&mut worker, worker_pid, &lock, None),
    }
    monitor_worker(&mut control, &mut worker, worker_pid, &lock)
}

fn spawn_bootstrap(
    plan: &File,
    worker_stdin: File,
    worker_stdout: File,
    worker_stderr: File,
) -> Result<(Child, File, File), GuardianRuntimeError> {
    let mut gate_fds = [-1; 2];
    if unsafe {
        // SAFETY: gate_fds points to two writable integers populated by pipe2.
        libc::pipe2(gate_fds.as_mut_ptr(), libc::O_CLOEXEC)
    } == -1
    {
        return Err(GuardianRuntimeError::Io);
    }
    let gate_read = inherited_file(gate_fds[0]);
    let gate_write = inherited_file(gate_fds[1]);
    let mut exec_status_fds = [-1; 2];
    if unsafe {
        // SAFETY: exec_status_fds points to two writable integers populated by pipe2.
        libc::pipe2(exec_status_fds.as_mut_ptr(), libc::O_CLOEXEC)
    } == -1
    {
        return Err(GuardianRuntimeError::Io);
    }
    let exec_status_read = inherited_file(exec_status_fds[0]);
    let exec_status_write = inherited_file(exec_status_fds[1]);
    let executable = std::env::current_exe().map_err(|_| GuardianRuntimeError::Io)?;
    let arguments = std::env::args_os().skip(1).collect::<Vec<_>>();
    let mut command = Command::new(executable);
    command
        .args(arguments)
        .stdin(Stdio::null())
        .stdout(Stdio::null())
        .stderr(Stdio::null())
        .env_clear()
        .env(ROLE_ENV, ROLE_BOOTSTRAP)
        .current_dir("/");
    let inherited = [
        (plan.as_raw_fd(), GUARDIAN_PLAN_FD),
        (worker_stdin.as_raw_fd(), WORKER_STDIN_FD),
        (worker_stdout.as_raw_fd(), WORKER_STDOUT_FD),
        (worker_stderr.as_raw_fd(), WORKER_STDERR_FD),
        (gate_read.as_raw_fd(), WORKER_GATE_FD),
        (exec_status_write.as_raw_fd(), WORKER_EXEC_STATUS_FD),
    ];
    let parent_pid = std::process::id();
    unsafe {
        // SAFETY: this dedicated Guardian is single-threaded. The closure uses
        // only async-signal-safe prctl/getppid/setsid/dup3/fcntl operations,
        // and all source descriptors remain alive until spawn returns.
        command.pre_exec(move || {
            if libc::prctl(libc::PR_SET_PDEATHSIG, libc::SIGKILL) == -1 {
                return Err(io::Error::last_os_error());
            }
            if libc::getppid() != parent_pid as libc::pid_t {
                return Err(io::Error::other("guardian changed"));
            }
            if libc::setsid() == -1 {
                return Err(io::Error::last_os_error());
            }
            for (source, target) in inherited {
                dup_to_fixed(source, target)?;
            }
            Ok(())
        });
    }
    let child = command.spawn().map_err(|_| GuardianRuntimeError::Spawn)?;
    drop(gate_read);
    drop(worker_stdin);
    drop(worker_stdout);
    drop(worker_stderr);
    drop(exec_status_write);
    Ok((child, gate_write, exec_status_read))
}

fn run_bootstrap_role() -> Result<(), GuardianRuntimeError> {
    let plan_file = inherited_file(GUARDIAN_PLAN_FD);
    let worker_stdin = inherited_file(WORKER_STDIN_FD);
    let worker_stdout = inherited_file(WORKER_STDOUT_FD);
    let worker_stderr = inherited_file(WORKER_STDERR_FD);
    let mut gate = inherited_file(WORKER_GATE_FD);
    let mut exec_status = inherited_file(WORKER_EXEC_STATUS_FD);
    for fd in [
        plan_file.as_raw_fd(),
        worker_stdin.as_raw_fd(),
        worker_stdout.as_raw_fd(),
        worker_stderr.as_raw_fd(),
        gate.as_raw_fd(),
        exec_status.as_raw_fd(),
    ] {
        set_cloexec(fd, true).map_err(|_| GuardianRuntimeError::Io)?;
    }
    let decoded = read_sealed_exec_plan(&plan_file)?;
    let mut byte = [0_u8; 1];
    std::io::Read::read_exact(&mut gate, &mut byte).map_err(|_| GuardianRuntimeError::Io)?;
    if byte != [1] {
        return Err(GuardianRuntimeError::Protocol);
    }
    drop(gate);
    let error = worker_command(decoded.plan, worker_stdin, worker_stdout, worker_stderr).exec();
    let _ = exec_status.write_all(&[1]);
    Err(if error.kind() == io::ErrorKind::InvalidInput {
        GuardianRuntimeError::InvalidConfiguration
    } else {
        GuardianRuntimeError::Spawn
    })
}

fn worker_command(
    plan: WorkerExecPlanV1,
    worker_stdin: File,
    worker_stdout: File,
    worker_stderr: File,
) -> Command {
    let mut command = Command::new(plan.executable);
    command
        .arg(plan.script)
        .args(plan.arguments)
        .stdin(Stdio::from(worker_stdin))
        .stdout(Stdio::from(worker_stdout))
        .stderr(Stdio::from(worker_stderr))
        .env_clear()
        .envs(plan.environment)
        .current_dir(plan.current_dir);
    command
}

fn monitor_worker(
    control: &mut UnixStream,
    worker: &mut Child,
    worker_pgid: u32,
    lock: &File,
) -> Result<(), GuardianRuntimeError> {
    loop {
        let revents = poll_control(control.as_raw_fd(), 20)?;
        if revents & (libc::POLLIN | libc::POLLHUP | libc::POLLERR) != 0 {
            match read_frame_v2(control) {
                Ok(GuardianFrameV2::Cancel {
                    worker_pid,
                    worker_pgid: acknowledged_pgid,
                }) if worker_pid == worker_pgid && acknowledged_pgid == worker_pgid => {
                    cleanup_or_hold(worker, worker_pgid, lock, Some(control));
                }
                Err(ProtocolV2Error::UnexpectedEof | ProtocolV2Error::Io) => {
                    cleanup_or_hold(worker, worker_pgid, lock, None);
                }
                _ => {
                    let _ = write_frame_v2(
                        control,
                        GuardianFrameV2::Failure {
                            stage: GuardianStageV2::Protocol,
                            failure: GuardianFailureV2::ProtocolRejected,
                            worker_pid: worker_pgid,
                            worker_pgid,
                        },
                    );
                    cleanup_or_hold(worker, worker_pgid, lock, None);
                }
            }
        }
        if let Some(status) = worker.try_wait().map_err(|_| GuardianRuntimeError::Wait)? {
            if process_group_exists(worker_pgid) {
                cleanup_residual_group_or_hold(worker_pgid, lock);
                write_frame_v2(
                    control,
                    GuardianFrameV2::Failure {
                        stage: GuardianStageV2::Cleanup,
                        failure: GuardianFailureV2::WorkerExitedWithLiveGroup,
                        worker_pid: worker_pgid,
                        worker_pgid,
                    },
                )?;
                return Ok(());
            }
            reap_adopted_children();
            write_frame_v2(
                control,
                GuardianFrameV2::Terminal {
                    worker_pid: worker_pgid,
                    worker_pgid,
                    exit: worker_exit(status)?,
                },
            )?;
            return Ok(());
        }
    }
}

fn cleanup_residual_group_or_hold(worker_pgid: u32, lock: &File) {
    if !process_group_exists(worker_pgid) {
        reap_adopted_children();
        return;
    }
    if signal_group(worker_pgid, libc::SIGTERM).is_err() {
        hold_lock_for_manual_recovery(lock);
    }
    thread::sleep(Duration::from_millis(50));
    if signal_group(worker_pgid, libc::SIGKILL).is_err()
        || !reap_group_until_absent(worker_pgid, CLEANUP_TIMEOUT)
    {
        hold_lock_for_manual_recovery(lock);
    }
}

fn poll_control(fd: RawFd, timeout_ms: i32) -> Result<i16, GuardianRuntimeError> {
    let mut poll_fd = libc::pollfd {
        fd,
        events: libc::POLLIN | libc::POLLHUP | libc::POLLERR,
        revents: 0,
    };
    if unsafe {
        // SAFETY: poll receives one valid pollfd for the duration of the call.
        libc::poll(&mut poll_fd, 1, timeout_ms)
    } == -1
    {
        return Err(GuardianRuntimeError::Io);
    }
    Ok(poll_fd.revents)
}

fn worker_exit(status: ExitStatus) -> Result<WorkerExitV2, GuardianRuntimeError> {
    if let Some(code) = status.code() {
        return Ok(WorkerExitV2::Exited(code));
    }
    status
        .signal()
        .map(WorkerExitV2::Signaled)
        .ok_or(GuardianRuntimeError::Wait)
}

fn cleanup_or_hold(
    worker: &mut Child,
    worker_pgid: u32,
    lock: &File,
    notify: Option<&mut UnixStream>,
) -> ! {
    match cleanup_worker_group(worker, worker_pgid, Duration::from_millis(50)) {
        Ok((status, true)) => {
            if let (Some(control), Ok(exit)) = (notify, worker_exit(status)) {
                let _ = write_frame_v2(
                    control,
                    GuardianFrameV2::Terminal {
                        worker_pid: worker_pgid,
                        worker_pgid,
                        exit,
                    },
                );
            }
            std::process::exit(0);
        }
        Ok((_, false)) | Err(_) => hold_lock_for_manual_recovery(lock),
    }
}

fn hold_lock_for_manual_recovery(lock: &File) -> ! {
    let _retained_lock = lock;
    loop {
        thread::park();
    }
}

fn cleanup_worker_group(
    worker: &mut Child,
    pgid: u32,
    grace: Duration,
) -> Result<(ExitStatus, bool), GuardianRuntimeError> {
    signal_group(pgid, libc::SIGTERM)?;
    thread::sleep(grace);
    signal_group(pgid, libc::SIGKILL)?;
    let status = worker.wait().map_err(|_| GuardianRuntimeError::Wait)?;
    Ok((status, reap_group_until_absent(pgid, CLEANUP_TIMEOUT)))
}

fn signal_group(pgid: u32, signal: libc::c_int) -> Result<(), GuardianRuntimeError> {
    if pgid <= 1 || pgid > i32::MAX as u32 {
        return Err(GuardianRuntimeError::Signal);
    }
    let result = unsafe {
        // SAFETY: the validated negative PID selects the exact Worker group.
        libc::kill(-(pgid as libc::pid_t), signal)
    };
    if result == 0 || io::Error::last_os_error().raw_os_error() == Some(libc::ESRCH) {
        Ok(())
    } else {
        Err(GuardianRuntimeError::Signal)
    }
}

fn process_group_exists(pgid: u32) -> bool {
    if pgid <= 1 || pgid > i32::MAX as u32 {
        return true;
    }
    let result = unsafe {
        // SAFETY: signal zero queries the validated process group.
        libc::kill(-(pgid as libc::pid_t), 0)
    };
    result == 0 || io::Error::last_os_error().raw_os_error() == Some(libc::EPERM)
}

fn reap_group_until_absent(pgid: u32, timeout: Duration) -> bool {
    let deadline = Instant::now() + timeout;
    loop {
        reap_adopted_children();
        if !process_group_exists(pgid) {
            return true;
        }
        if Instant::now() >= deadline {
            return false;
        }
        thread::sleep(Duration::from_millis(10));
    }
}

fn reap_adopted_children() {
    loop {
        let mut status = 0;
        let result = unsafe {
            // SAFETY: status is valid writable storage and WNOHANG bounds wait.
            libc::waitpid(-1, &mut status, libc::WNOHANG)
        };
        if result <= 0 {
            return;
        }
    }
}
