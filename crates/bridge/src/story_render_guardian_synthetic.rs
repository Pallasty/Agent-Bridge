//! Dormant S633 Guardian protocol and synthetic custody prototype.
//!
//! This module is intentionally not wired into `lib.rs` or the Story render
//! Supervisor. Integration tests include it by path. It must not read real
//! authority, load a model, render audio, or register an MCP surface.

#![deny(clippy::all)]

use std::fs::{self, File, OpenOptions};
use std::io::{self, Read, Write};
use std::os::fd::{AsRawFd, FromRawFd, IntoRawFd, RawFd};
use std::os::unix::fs::{MetadataExt, OpenOptionsExt};
use std::os::unix::net::UnixStream;
use std::os::unix::process::CommandExt;
use std::path::{Path, PathBuf};
use std::process::{Child, Command, Stdio};
use std::thread;
use std::time::{Duration, Instant};

const MAGIC: [u8; 4] = *b"ABG1";
const VERSION: u8 = 1;
const HEADER_BYTES: usize = 8;

pub const MAX_FRAME_BYTES: usize = 64;
pub const HOST_CRASH_EXIT: i32 = 73;

const HELPER_ERROR_EXIT: i32 = 74;
const GUARDIAN_LOCK_FD: RawFd = 190;
const GUARDIAN_SOCKET_FD: RawFd = 191;
const WORKER_START_FD: RawFd = 193;
const HELPER_ROLE_ENV: &str = "AB_S633_HELPER_ROLE";
const WORKER_MODE_ENV: &str = "AB_S633_WORKER_MODE";
const LOCK_PATH_ENV: &str = "AB_S633_LOCK_PATH";
const PID_FILE_ENV: &str = "AB_S633_PID_FILE";
const PAYLOAD_MARKER_ENV: &str = "AB_S633_PAYLOAD_MARKER";
const TERMINATION_GRACE_MS_ENV: &str = "AB_S633_TERMINATION_GRACE_MS";
const READY_PATH_ENV: &str = "AB_S633_READY_PATH";

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum GuardianOutcome {
    CleanSuccess,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum GuardianFailure {
    WorkerExitedWithLiveGroup,
    ProtocolRejected,
    CleanupUnproven,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum GuardianFrame {
    Bound {
        guardian_pid: u32,
        worker_pid: u32,
        worker_pgid: u32,
    },
    Start {
        worker_pid: u32,
        worker_pgid: u32,
    },
    Cancel,
    Terminal {
        worker_pid: u32,
        worker_pgid: u32,
        outcome: GuardianOutcome,
    },
    Failure {
        failure: GuardianFailure,
    },
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum ProtocolError {
    Io,
    UnexpectedEof,
    Oversized,
    InvalidFrame,
}

impl std::fmt::Display for ProtocolError {
    fn fmt(&self, formatter: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        let code = match self {
            Self::Io => "guardian_frame_io",
            Self::UnexpectedEof => "guardian_frame_unexpected_eof",
            Self::Oversized => "guardian_frame_oversized",
            Self::InvalidFrame => "guardian_frame_invalid",
        };
        formatter.write_str(code)
    }
}

impl std::error::Error for ProtocolError {}

fn push_u32(body: &mut Vec<u8>, value: u32) {
    body.extend_from_slice(&value.to_be_bytes());
}

fn valid_pid(pid: u32) -> bool {
    pid > 1 && pid <= i32::MAX as u32
}

fn encode_body(frame: GuardianFrame) -> Result<Vec<u8>, ProtocolError> {
    let (kind, values): (u8, Vec<u32>) = match frame {
        GuardianFrame::Bound {
            guardian_pid,
            worker_pid,
            worker_pgid,
        } if valid_pid(guardian_pid)
            && valid_pid(worker_pid)
            && worker_pid == worker_pgid
            && guardian_pid != worker_pid =>
        {
            (1, vec![guardian_pid, worker_pid, worker_pgid])
        }
        GuardianFrame::Start {
            worker_pid,
            worker_pgid,
        } if valid_pid(worker_pid) && worker_pid == worker_pgid => {
            (2, vec![worker_pid, worker_pgid])
        }
        GuardianFrame::Cancel => (3, Vec::new()),
        GuardianFrame::Terminal {
            worker_pid,
            worker_pgid,
            outcome: GuardianOutcome::CleanSuccess,
        } if valid_pid(worker_pid) && worker_pid == worker_pgid => {
            (4, vec![worker_pid, worker_pgid, 0])
        }
        GuardianFrame::Failure { failure } => {
            let code = match failure {
                GuardianFailure::WorkerExitedWithLiveGroup => 1,
                GuardianFailure::ProtocolRejected => 2,
                GuardianFailure::CleanupUnproven => 3,
            };
            (5, vec![code])
        }
        _ => return Err(ProtocolError::InvalidFrame),
    };

    let mut body = Vec::with_capacity(HEADER_BYTES + values.len() * 4);
    body.extend_from_slice(&MAGIC);
    body.push(VERSION);
    body.push(kind);
    body.extend_from_slice(&[0, 0]);
    for value in values {
        push_u32(&mut body, value);
    }
    Ok(body)
}

fn u32_at(body: &[u8], offset: usize) -> Result<u32, ProtocolError> {
    let raw: [u8; 4] = body
        .get(offset..offset + 4)
        .ok_or(ProtocolError::InvalidFrame)?
        .try_into()
        .map_err(|_| ProtocolError::InvalidFrame)?;
    Ok(u32::from_be_bytes(raw))
}

fn decode_body(body: &[u8]) -> Result<GuardianFrame, ProtocolError> {
    if body.len() < HEADER_BYTES || body[..4] != MAGIC || body[4] != VERSION || body[6..8] != [0, 0]
    {
        return Err(ProtocolError::InvalidFrame);
    }
    let frame = match (body[5], body.len()) {
        (1, 20) => GuardianFrame::Bound {
            guardian_pid: u32_at(body, 8)?,
            worker_pid: u32_at(body, 12)?,
            worker_pgid: u32_at(body, 16)?,
        },
        (2, 16) => GuardianFrame::Start {
            worker_pid: u32_at(body, 8)?,
            worker_pgid: u32_at(body, 12)?,
        },
        (3, 8) => GuardianFrame::Cancel,
        (4, 20) if u32_at(body, 16)? == 0 => GuardianFrame::Terminal {
            worker_pid: u32_at(body, 8)?,
            worker_pgid: u32_at(body, 12)?,
            outcome: GuardianOutcome::CleanSuccess,
        },
        (5, 12) => {
            let failure = match u32_at(body, 8)? {
                1 => GuardianFailure::WorkerExitedWithLiveGroup,
                2 => GuardianFailure::ProtocolRejected,
                3 => GuardianFailure::CleanupUnproven,
                _ => return Err(ProtocolError::InvalidFrame),
            };
            GuardianFrame::Failure { failure }
        }
        _ => return Err(ProtocolError::InvalidFrame),
    };
    encode_body(frame)?;
    Ok(frame)
}

pub fn write_frame(writer: &mut impl Write, frame: GuardianFrame) -> Result<(), ProtocolError> {
    let body = encode_body(frame)?;
    if body.len() > MAX_FRAME_BYTES {
        return Err(ProtocolError::Oversized);
    }
    let length = u32::try_from(body.len()).map_err(|_| ProtocolError::Oversized)?;
    let mut packet = Vec::with_capacity(4 + body.len());
    packet.extend_from_slice(&length.to_be_bytes());
    packet.extend_from_slice(&body);
    writer.write_all(&packet).map_err(|_| ProtocolError::Io)
}

pub fn read_frame(reader: &mut impl Read) -> Result<GuardianFrame, ProtocolError> {
    let mut length = [0_u8; 4];
    read_exact(reader, &mut length)?;
    let length =
        usize::try_from(u32::from_be_bytes(length)).map_err(|_| ProtocolError::Oversized)?;
    if length > MAX_FRAME_BYTES {
        return Err(ProtocolError::Oversized);
    }
    if length < HEADER_BYTES {
        return Err(ProtocolError::InvalidFrame);
    }
    let mut body = vec![0_u8; length];
    read_exact(reader, &mut body)?;
    decode_body(&body)
}

fn read_exact(reader: &mut impl Read, output: &mut [u8]) -> Result<(), ProtocolError> {
    match reader.read_exact(output) {
        Ok(()) => Ok(()),
        Err(error) if error.kind() == io::ErrorKind::UnexpectedEof => {
            Err(ProtocolError::UnexpectedEof)
        }
        Err(_) => Err(ProtocolError::Io),
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum SyntheticWorkerMode {
    FdAuditExit,
    TermIgnoringDescendant,
    ExitWithDescendant,
}

impl SyntheticWorkerMode {
    fn as_str(self) -> &'static str {
        match self {
            Self::FdAuditExit => "fd_audit_exit",
            Self::TermIgnoringDescendant => "term_ignoring_descendant",
            Self::ExitWithDescendant => "exit_with_descendant",
        }
    }

    fn parse(value: &str) -> Result<Self, CustodyError> {
        match value {
            "fd_audit_exit" => Ok(Self::FdAuditExit),
            "term_ignoring_descendant" => Ok(Self::TermIgnoringDescendant),
            "exit_with_descendant" => Ok(Self::ExitWithDescendant),
            _ => Err(CustodyError::InvalidConfiguration),
        }
    }

    fn expected_pid_count(self) -> usize {
        match self {
            Self::FdAuditExit => 1,
            Self::TermIgnoringDescendant | Self::ExitWithDescendant => 2,
        }
    }
}

#[derive(Debug, Clone)]
pub struct SyntheticGuardianSpec {
    pub executable: PathBuf,
    pub worker_mode: SyntheticWorkerMode,
    pub pid_file: PathBuf,
    pub payload_marker: PathBuf,
    pub termination_grace: Duration,
}

impl SyntheticGuardianSpec {
    fn validate(&self) -> Result<(), CustodyError> {
        if !self.executable.is_absolute()
            || !self.executable.is_file()
            || !self.pid_file.is_absolute()
            || !self.payload_marker.is_absolute()
            || self.termination_grace.is_zero()
            || self.termination_grace > Duration::from_secs(2)
        {
            return Err(CustodyError::InvalidConfiguration);
        }
        Ok(())
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct WorkerBinding {
    pub guardian_pid: u32,
    pub worker_pid: u32,
    pub worker_pgid: u32,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum CustodyError {
    InvalidConfiguration,
    LockUnavailable,
    Busy,
    SpawnFailed,
    Protocol(ProtocolError),
    UnexpectedFrame,
    SignalFailed,
    WaitFailed,
    CleanupUnproven,
    Io,
}

impl std::fmt::Display for CustodyError {
    fn fmt(&self, formatter: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        let code = match self {
            Self::InvalidConfiguration => "guardian_invalid_configuration",
            Self::LockUnavailable => "guardian_lock_unavailable",
            Self::Busy => "guardian_busy",
            Self::SpawnFailed => "guardian_spawn_failed",
            Self::Protocol(_) => "guardian_protocol_rejected",
            Self::UnexpectedFrame => "guardian_unexpected_frame",
            Self::SignalFailed => "guardian_signal_failed",
            Self::WaitFailed => "guardian_wait_failed",
            Self::CleanupUnproven => "guardian_cleanup_unproven",
            Self::Io => "guardian_io",
        };
        formatter.write_str(code)
    }
}

impl std::error::Error for CustodyError {}

impl From<ProtocolError> for CustodyError {
    fn from(error: ProtocolError) -> Self {
        Self::Protocol(error)
    }
}

/// Lock custody shared with the Guardian through one shared open-file-description.
///
/// This type deliberately has no `Drop` implementation and never calls
/// `LOCK_UN`. The lock is released only when the last duplicated descriptor
/// closes. If fallback cleanup is unproven, the Host leaks its descriptor so
/// the process retains the admission lock for manual recovery.
struct SharedCustodyLock(File);

impl SharedCustodyLock {
    fn acquire(path: &Path) -> Result<Self, CustodyError> {
        let file = open_lock_file(path)?;
        let result = unsafe {
            // SAFETY: `file` owns a valid descriptor and flock does not retain
            // the pointer or borrow Rust memory.
            libc::flock(file.as_raw_fd(), libc::LOCK_EX | libc::LOCK_NB)
        };
        if result == 0 {
            return Ok(Self(file));
        }
        match io::Error::last_os_error().raw_os_error() {
            Some(code) if code == libc::EAGAIN || code == libc::EWOULDBLOCK => {
                Err(CustodyError::Busy)
            }
            _ => Err(CustodyError::LockUnavailable),
        }
    }

    fn as_raw_fd(&self) -> RawFd {
        self.0.as_raw_fd()
    }

    fn leak(self) {
        let _ = self.0.into_raw_fd();
    }
}

fn open_lock_file(path: &Path) -> Result<File, CustodyError> {
    if !path.is_absolute() {
        return Err(CustodyError::InvalidConfiguration);
    }
    let file = OpenOptions::new()
        .read(true)
        .write(true)
        .create(true)
        .mode(0o600)
        .custom_flags(libc::O_CLOEXEC | libc::O_NOFOLLOW)
        .open(path)
        .map_err(|_| CustodyError::LockUnavailable)?;
    let metadata = file.metadata().map_err(|_| CustodyError::LockUnavailable)?;
    if !metadata.is_file() || metadata.mode() & 0o777 != 0o600 || metadata.nlink() != 1 {
        return Err(CustodyError::LockUnavailable);
    }
    Ok(file)
}

pub fn probe_lock_available(path: &Path) -> Result<bool, CustodyError> {
    let file = open_lock_file(path)?;
    let result = unsafe {
        // SAFETY: `file` owns a valid descriptor; the probe lock is released
        // by last-close when this function returns.
        libc::flock(file.as_raw_fd(), libc::LOCK_EX | libc::LOCK_NB)
    };
    if result == 0 {
        return Ok(true);
    }
    match io::Error::last_os_error().raw_os_error() {
        Some(code) if code == libc::EAGAIN || code == libc::EWOULDBLOCK => Ok(false),
        _ => Err(CustodyError::LockUnavailable),
    }
}

pub fn process_is_live(pid: u32) -> bool {
    let Ok(stat) = fs::read_to_string(format!("/proc/{pid}/stat")) else {
        return false;
    };
    let Some(after_name) = stat.rsplit_once(") ").map(|(_, rest)| rest) else {
        return true;
    };
    !after_name.starts_with('Z')
}

fn process_group_exists(pgid: u32) -> bool {
    if !valid_pid(pgid) {
        return false;
    }
    let result = unsafe {
        // SAFETY: negative PID selects a process group; signal 0 performs a
        // permission/existence check and mutates no process state.
        libc::kill(-(pgid as libc::pid_t), 0)
    };
    result == 0 || io::Error::last_os_error().raw_os_error() == Some(libc::EPERM)
}

fn set_cloexec(fd: RawFd, enabled: bool) -> io::Result<()> {
    let flags = unsafe {
        // SAFETY: fcntl reads descriptor flags and does not retain pointers.
        libc::fcntl(fd, libc::F_GETFD)
    };
    if flags == -1 {
        return Err(io::Error::last_os_error());
    }
    let updated = if enabled {
        flags | libc::FD_CLOEXEC
    } else {
        flags & !libc::FD_CLOEXEC
    };
    let result = unsafe {
        // SAFETY: fcntl writes flags for the validated descriptor only.
        libc::fcntl(fd, libc::F_SETFD, updated)
    };
    if result == -1 {
        Err(io::Error::last_os_error())
    } else {
        Ok(())
    }
}

fn dup_to_fixed(source: RawFd, target: RawFd) -> io::Result<()> {
    if source == target {
        return set_cloexec(target, false);
    }
    let result = unsafe {
        // SAFETY: dup2 atomically replaces `target` with a duplicate of the
        // valid inherited `source` descriptor.
        libc::dup2(source, target)
    };
    if result == -1 {
        Err(io::Error::last_os_error())
    } else {
        Ok(())
    }
}

fn configure_helper_command(command: &mut Command, role: &str) {
    command
        .arg("--exact")
        .arg("subprocess_entrypoint")
        .arg("--nocapture")
        .env_clear()
        .env(HELPER_ROLE_ENV, role)
        .stdin(Stdio::null())
        .stdout(Stdio::null())
        .stderr(Stdio::null());
}

fn configure_spec_environment(command: &mut Command, spec: &SyntheticGuardianSpec) {
    command
        .env(WORKER_MODE_ENV, spec.worker_mode.as_str())
        .env(PID_FILE_ENV, &spec.pid_file)
        .env(PAYLOAD_MARKER_ENV, &spec.payload_marker)
        .env(
            TERMINATION_GRACE_MS_ENV,
            spec.termination_grace.as_millis().to_string(),
        );
}

pub struct SyntheticHostCustody {
    lock: Option<SharedCustodyLock>,
    socket: UnixStream,
    guardian: Child,
    guardian_lost: bool,
    cleanup_confirmed: bool,
}

impl SyntheticHostCustody {
    pub fn spawn(lock_path: &Path, spec: &SyntheticGuardianSpec) -> Result<Self, CustodyError> {
        spec.validate()?;
        let lock = SharedCustodyLock::acquire(lock_path)?;
        let (host_socket, guardian_socket) = UnixStream::pair().map_err(|_| CustodyError::Io)?;
        set_cloexec(host_socket.as_raw_fd(), true).map_err(|_| CustodyError::Io)?;
        set_cloexec(guardian_socket.as_raw_fd(), true).map_err(|_| CustodyError::Io)?;
        host_socket
            .set_read_timeout(Some(Duration::from_secs(5)))
            .map_err(|_| CustodyError::Io)?;
        host_socket
            .set_write_timeout(Some(Duration::from_secs(5)))
            .map_err(|_| CustodyError::Io)?;

        let mut command = Command::new(&spec.executable);
        configure_helper_command(&mut command, "guardian");
        configure_spec_environment(&mut command, spec);
        command.env(LOCK_PATH_ENV, lock_path);
        let lock_fd = lock.as_raw_fd();
        let socket_fd = guardian_socket.as_raw_fd();
        unsafe {
            // SAFETY: the closure uses only async-signal-safe descriptor
            // operations between fork and exec. Captured raw descriptors stay
            // open in the parent until `spawn` returns.
            command.pre_exec(move || {
                dup_to_fixed(lock_fd, GUARDIAN_LOCK_FD)?;
                dup_to_fixed(socket_fd, GUARDIAN_SOCKET_FD)?;
                Ok(())
            });
        }
        let guardian = command.spawn().map_err(|_| CustodyError::SpawnFailed)?;
        drop(guardian_socket);
        Ok(Self {
            lock: Some(lock),
            socket: host_socket,
            guardian,
            guardian_lost: false,
            cleanup_confirmed: false,
        })
    }

    pub fn read_event(&mut self) -> Result<GuardianFrame, CustodyError> {
        read_frame(&mut self.socket).map_err(Into::into)
    }

    pub fn acknowledge_start(&mut self, binding: WorkerBinding) -> Result<(), CustodyError> {
        write_frame(
            &mut self.socket,
            GuardianFrame::Start {
                worker_pid: binding.worker_pid,
                worker_pgid: binding.worker_pgid,
            },
        )
        .map_err(Into::into)
    }

    pub fn wait_guardian(&mut self) -> Result<(), CustodyError> {
        let status = self.guardian.wait().map_err(|_| CustodyError::WaitFailed)?;
        if !status.success() {
            return Err(CustodyError::WaitFailed);
        }
        self.cleanup_confirmed = true;
        Ok(())
    }

    pub fn kill_guardian_for_test(&mut self) -> Result<(), CustodyError> {
        let pid = self.guardian.id();
        if !valid_pid(pid) {
            return Err(CustodyError::SignalFailed);
        }
        let result = unsafe {
            // SAFETY: PID is the exact child returned by `Command::spawn`.
            libc::kill(pid as libc::pid_t, libc::SIGKILL)
        };
        if result == -1 && io::Error::last_os_error().raw_os_error() != Some(libc::ESRCH) {
            return Err(CustodyError::SignalFailed);
        }
        self.guardian.wait().map_err(|_| CustodyError::WaitFailed)?;
        self.guardian_lost = true;
        Ok(())
    }

    pub fn fallback_cleanup(&mut self, binding: WorkerBinding) -> Result<(), CustodyError> {
        if !self.guardian_lost
            || binding.guardian_pid != self.guardian.id()
            || binding.worker_pid != binding.worker_pgid
        {
            return Err(CustodyError::InvalidConfiguration);
        }
        if !terminate_group_without_child(binding.worker_pgid, Duration::from_millis(50))? {
            return Err(CustodyError::CleanupUnproven);
        }
        self.cleanup_confirmed = true;
        Ok(())
    }
}

impl Drop for SyntheticHostCustody {
    fn drop(&mut self) {
        if self.guardian_lost && !self.cleanup_confirmed {
            if let Some(lock) = self.lock.take() {
                lock.leak();
            }
        }
    }
}

pub fn spawn_host_crash_fixture(
    lock_path: &Path,
    spec: &SyntheticGuardianSpec,
    ready_path: &Path,
) -> Result<Child, CustodyError> {
    spec.validate()?;
    if !lock_path.is_absolute() || !ready_path.is_absolute() {
        return Err(CustodyError::InvalidConfiguration);
    }
    let mut command = Command::new(&spec.executable);
    configure_helper_command(&mut command, "host_crash");
    configure_spec_environment(&mut command, spec);
    command
        .env(LOCK_PATH_ENV, lock_path)
        .env(READY_PATH_ENV, ready_path);
    command.spawn().map_err(|_| CustodyError::SpawnFailed)
}

pub fn run_synthetic_helper() -> Option<i32> {
    let role = std::env::var(HELPER_ROLE_ENV).ok()?;
    let result = match role.as_str() {
        "guardian" => run_guardian_helper(),
        "worker" => run_worker_helper(),
        "descendant" => run_descendant_helper(),
        "host_crash" => run_host_crash_helper(),
        _ => Err(CustodyError::InvalidConfiguration),
    };
    Some(if result.is_ok() { 0 } else { HELPER_ERROR_EXIT })
}

fn spec_from_environment() -> Result<SyntheticGuardianSpec, CustodyError> {
    let executable = std::env::current_exe().map_err(|_| CustodyError::Io)?;
    let worker_mode = SyntheticWorkerMode::parse(
        &std::env::var(WORKER_MODE_ENV).map_err(|_| CustodyError::InvalidConfiguration)?,
    )?;
    let pid_file =
        PathBuf::from(std::env::var_os(PID_FILE_ENV).ok_or(CustodyError::InvalidConfiguration)?);
    let payload_marker = PathBuf::from(
        std::env::var_os(PAYLOAD_MARKER_ENV).ok_or(CustodyError::InvalidConfiguration)?,
    );
    let grace_ms = std::env::var(TERMINATION_GRACE_MS_ENV)
        .map_err(|_| CustodyError::InvalidConfiguration)?
        .parse::<u64>()
        .map_err(|_| CustodyError::InvalidConfiguration)?;
    let spec = SyntheticGuardianSpec {
        executable,
        worker_mode,
        pid_file,
        payload_marker,
        termination_grace: Duration::from_millis(grace_ms),
    };
    spec.validate()?;
    Ok(spec)
}

fn run_host_crash_helper() -> Result<(), CustodyError> {
    let spec = spec_from_environment()?;
    let lock_path =
        PathBuf::from(std::env::var_os(LOCK_PATH_ENV).ok_or(CustodyError::InvalidConfiguration)?);
    let ready_path =
        PathBuf::from(std::env::var_os(READY_PATH_ENV).ok_or(CustodyError::InvalidConfiguration)?);
    let mut host = SyntheticHostCustody::spawn(&lock_path, &spec)?;
    let binding = binding_from_frame(host.read_event()?)?;
    host.acknowledge_start(binding)?;
    wait_for_pid_file(&spec.pid_file, spec.worker_mode.expected_pid_count())?;
    fs::write(ready_path, b"host_started\n").map_err(|_| CustodyError::Io)?;
    std::process::exit(HOST_CRASH_EXIT);
}

fn binding_from_frame(frame: GuardianFrame) -> Result<WorkerBinding, CustodyError> {
    match frame {
        GuardianFrame::Bound {
            guardian_pid,
            worker_pid,
            worker_pgid,
        } => Ok(WorkerBinding {
            guardian_pid,
            worker_pid,
            worker_pgid,
        }),
        _ => Err(CustodyError::UnexpectedFrame),
    }
}

fn wait_for_pid_file(path: &Path, count: usize) -> Result<(), CustodyError> {
    let deadline = Instant::now() + Duration::from_secs(5);
    loop {
        if let Ok(text) = fs::read_to_string(path) {
            if text.split_whitespace().count() == count {
                return Ok(());
            }
        }
        if Instant::now() >= deadline {
            return Err(CustodyError::WaitFailed);
        }
        thread::sleep(Duration::from_millis(10));
    }
}

fn run_guardian_helper() -> Result<(), CustodyError> {
    let spec = spec_from_environment()?;
    let lock_path =
        PathBuf::from(std::env::var_os(LOCK_PATH_ENV).ok_or(CustodyError::InvalidConfiguration)?);
    let lock = unsafe {
        // SAFETY: the Host installs this unique fixed descriptor immediately
        // before exec and transfers ownership to this Guardian process.
        File::from_raw_fd(GUARDIAN_LOCK_FD)
    };
    let mut socket = unsafe {
        // SAFETY: the Host installs this unique Unix socket descriptor before
        // exec and transfers ownership to this Guardian process.
        UnixStream::from_raw_fd(GUARDIAN_SOCKET_FD)
    };
    validate_inherited_lock(&lock, &lock_path)?;
    set_cloexec(lock.as_raw_fd(), true).map_err(|_| CustodyError::Io)?;
    set_cloexec(socket.as_raw_fd(), true).map_err(|_| CustodyError::Io)?;
    socket
        .set_read_timeout(Some(Duration::from_secs(1)))
        .map_err(|_| CustodyError::Io)?;
    socket
        .set_write_timeout(Some(Duration::from_secs(1)))
        .map_err(|_| CustodyError::Io)?;
    let subreaper = unsafe {
        // SAFETY: prctl modifies only this dedicated single-threaded Guardian.
        libc::prctl(libc::PR_SET_CHILD_SUBREAPER, 1)
    };
    if subreaper == -1 {
        return Err(CustodyError::InvalidConfiguration);
    }

    let (mut worker, mut start_gate) = spawn_bootstrap(&spec)?;
    let worker_pid = worker.id();
    let binding = WorkerBinding {
        guardian_pid: std::process::id(),
        worker_pid,
        worker_pgid: worker_pid,
    };
    write_frame(
        &mut socket,
        GuardianFrame::Bound {
            guardian_pid: binding.guardian_pid,
            worker_pid,
            worker_pgid: worker_pid,
        },
    )?;

    let start = read_frame(&mut socket);
    match start {
        Ok(GuardianFrame::Start {
            worker_pid: acknowledged_pid,
            worker_pgid: acknowledged_pgid,
        }) if acknowledged_pid == worker_pid && acknowledged_pgid == worker_pid => {
            start_gate.write_all(&[1]).map_err(|_| CustodyError::Io)?;
            drop(start_gate);
        }
        Err(ProtocolError::UnexpectedEof | ProtocolError::Io) => {
            cleanup_or_hold(&mut worker, worker_pid, spec.termination_grace, lock);
        }
        _ => {
            let _ = write_frame(
                &mut socket,
                GuardianFrame::Failure {
                    failure: GuardianFailure::ProtocolRejected,
                },
            );
            cleanup_or_hold(&mut worker, worker_pid, spec.termination_grace, lock);
        }
    }

    monitor_worker(
        &mut socket,
        &mut worker,
        binding,
        spec.termination_grace,
        lock,
    )
}

fn validate_inherited_lock(lock: &File, path: &Path) -> Result<(), CustodyError> {
    let inherited = lock.metadata().map_err(|_| CustodyError::LockUnavailable)?;
    let expected = fs::metadata(path).map_err(|_| CustodyError::LockUnavailable)?;
    if !inherited.is_file()
        || inherited.mode() & 0o777 != 0o600
        || inherited.nlink() != 1
        || inherited.dev() != expected.dev()
        || inherited.ino() != expected.ino()
    {
        return Err(CustodyError::LockUnavailable);
    }
    Ok(())
}

fn spawn_bootstrap(spec: &SyntheticGuardianSpec) -> Result<(Child, File), CustodyError> {
    let mut gate = [0_i32; 2];
    let pipe_result = unsafe {
        // SAFETY: `gate` points to two writable integers and pipe2 initializes
        // both descriptors atomically with close-on-exec.
        libc::pipe2(gate.as_mut_ptr(), libc::O_CLOEXEC)
    };
    if pipe_result == -1 {
        return Err(CustodyError::Io);
    }
    let gate_read = unsafe {
        // SAFETY: pipe2 returned a new owned read descriptor.
        File::from_raw_fd(gate[0])
    };
    let gate_write = unsafe {
        // SAFETY: pipe2 returned a new owned write descriptor.
        File::from_raw_fd(gate[1])
    };
    let mut command = Command::new(&spec.executable);
    configure_helper_command(&mut command, "worker");
    configure_spec_environment(&mut command, spec);
    let gate_fd = gate_read.as_raw_fd();
    let parent_pid = unsafe {
        // SAFETY: getpid has no preconditions.
        libc::getpid()
    };
    unsafe {
        // SAFETY: the closure uses async-signal-safe Linux calls only. The
        // inherited gate descriptor remains open until spawn returns.
        command.pre_exec(move || {
            if libc::prctl(libc::PR_SET_PDEATHSIG, libc::SIGKILL) == -1 {
                return Err(io::Error::last_os_error());
            }
            if libc::getppid() != parent_pid {
                return Err(io::Error::other("guardian changed"));
            }
            if libc::setsid() == -1 {
                return Err(io::Error::last_os_error());
            }
            dup_to_fixed(gate_fd, WORKER_START_FD)?;
            Ok(())
        });
    }
    let child = command.spawn().map_err(|_| CustodyError::SpawnFailed)?;
    drop(gate_read);
    Ok((child, gate_write))
}

fn monitor_worker(
    socket: &mut UnixStream,
    worker: &mut Child,
    binding: WorkerBinding,
    grace: Duration,
    lock: File,
) -> Result<(), CustodyError> {
    loop {
        let revents = poll_socket(socket.as_raw_fd(), 20)?;
        if revents & (libc::POLLIN | libc::POLLHUP | libc::POLLERR) != 0 {
            match read_frame(socket) {
                Ok(GuardianFrame::Cancel) => {
                    cleanup_or_hold(worker, binding.worker_pgid, grace, lock);
                }
                Err(ProtocolError::UnexpectedEof | ProtocolError::Io) => {
                    cleanup_or_hold(worker, binding.worker_pgid, grace, lock);
                }
                _ => {
                    let _ = write_frame(
                        socket,
                        GuardianFrame::Failure {
                            failure: GuardianFailure::ProtocolRejected,
                        },
                    );
                    cleanup_or_hold(worker, binding.worker_pgid, grace, lock);
                }
            }
        }

        if worker
            .try_wait()
            .map_err(|_| CustodyError::WaitFailed)?
            .is_some()
        {
            if process_group_exists(binding.worker_pgid) {
                if !cleanup_worker_group(worker, binding.worker_pgid, grace)? {
                    hold_lock_for_manual_recovery(lock);
                }
                write_frame(
                    socket,
                    GuardianFrame::Failure {
                        failure: GuardianFailure::WorkerExitedWithLiveGroup,
                    },
                )?;
                return Ok(());
            }
            reap_adopted_children();
            write_frame(
                socket,
                GuardianFrame::Terminal {
                    worker_pid: binding.worker_pid,
                    worker_pgid: binding.worker_pgid,
                    outcome: GuardianOutcome::CleanSuccess,
                },
            )?;
            return Ok(());
        }
    }
}

fn poll_socket(fd: RawFd, timeout_ms: i32) -> Result<i16, CustodyError> {
    let mut poll_fd = libc::pollfd {
        fd,
        events: libc::POLLIN | libc::POLLHUP | libc::POLLERR,
        revents: 0,
    };
    let result = unsafe {
        // SAFETY: poll receives one valid pollfd for the duration of the call.
        libc::poll(&mut poll_fd, 1, timeout_ms)
    };
    if result == -1 {
        Err(CustodyError::Io)
    } else {
        Ok(poll_fd.revents)
    }
}

fn cleanup_or_hold(worker: &mut Child, pgid: u32, grace: Duration, lock: File) -> ! {
    match cleanup_worker_group(worker, pgid, grace) {
        Ok(true) => {
            drop(lock);
            std::process::exit(0);
        }
        Ok(false) | Err(_) => hold_lock_for_manual_recovery(lock),
    }
}

fn hold_lock_for_manual_recovery(lock: File) -> ! {
    let _retained_lock = lock;
    loop {
        thread::park();
    }
}

fn signal_group(pgid: u32, signal: libc::c_int) -> Result<(), CustodyError> {
    if !valid_pid(pgid) {
        return Err(CustodyError::SignalFailed);
    }
    let result = unsafe {
        // SAFETY: the validated negative PID addresses the exact Worker group.
        libc::kill(-(pgid as libc::pid_t), signal)
    };
    if result == 0 || io::Error::last_os_error().raw_os_error() == Some(libc::ESRCH) {
        Ok(())
    } else {
        Err(CustodyError::SignalFailed)
    }
}

fn cleanup_worker_group(
    worker: &mut Child,
    pgid: u32,
    grace: Duration,
) -> Result<bool, CustodyError> {
    signal_group(pgid, libc::SIGTERM)?;
    thread::sleep(grace);
    signal_group(pgid, libc::SIGKILL)?;
    worker.wait().map_err(|_| CustodyError::WaitFailed)?;
    Ok(reap_group_until_absent(pgid, Duration::from_secs(5)))
}

fn terminate_group_without_child(pgid: u32, grace: Duration) -> Result<bool, CustodyError> {
    signal_group(pgid, libc::SIGTERM)?;
    thread::sleep(grace);
    signal_group(pgid, libc::SIGKILL)?;
    let deadline = Instant::now() + Duration::from_secs(5);
    while process_group_exists(pgid) && Instant::now() < deadline {
        thread::sleep(Duration::from_millis(10));
    }
    Ok(!process_group_exists(pgid))
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
            // SAFETY: status points to valid writable storage and WNOHANG
            // prevents an unbounded wait.
            libc::waitpid(-1, &mut status, libc::WNOHANG)
        };
        if result <= 0 {
            return;
        }
    }
}

fn run_worker_helper() -> Result<(), CustodyError> {
    let spec = spec_from_environment()?;
    let mut gate = unsafe {
        // SAFETY: the Guardian installs this unique fixed descriptor before
        // exec and transfers ownership to the bootstrap process.
        File::from_raw_fd(WORKER_START_FD)
    };
    let mut byte = [0_u8; 1];
    gate.read_exact(&mut byte).map_err(|_| CustodyError::Io)?;
    if byte != [1] {
        return Err(CustodyError::Protocol(ProtocolError::InvalidFrame));
    }
    drop(gate);
    verify_payload_descriptor_isolation()?;

    match spec.worker_mode {
        SyntheticWorkerMode::FdAuditExit => {
            fs::write(&spec.pid_file, format!("{}\n", std::process::id()))
                .map_err(|_| CustodyError::Io)?;
            fs::write(&spec.payload_marker, b"custody_fds_closed\n").map_err(|_| CustodyError::Io)
        }
        SyntheticWorkerMode::TermIgnoringDescendant => {
            let descendant = spawn_descendant(&spec.executable)?;
            publish_worker_and_descendant(&spec.pid_file, descendant.id())?;
            loop {
                thread::park();
            }
        }
        SyntheticWorkerMode::ExitWithDescendant => {
            let descendant = spawn_descendant(&spec.executable)?;
            publish_worker_and_descendant(&spec.pid_file, descendant.id())
        }
    }
}

fn verify_payload_descriptor_isolation() -> Result<(), CustodyError> {
    for fd in [GUARDIAN_LOCK_FD, GUARDIAN_SOCKET_FD, WORKER_START_FD] {
        let result = unsafe {
            // SAFETY: F_GETFD only queries the integer descriptor.
            libc::fcntl(fd, libc::F_GETFD)
        };
        if result != -1 || io::Error::last_os_error().raw_os_error() != Some(libc::EBADF) {
            return Err(CustodyError::InvalidConfiguration);
        }
    }
    Ok(())
}

fn spawn_descendant(executable: &Path) -> Result<Child, CustodyError> {
    let mut command = Command::new(executable);
    configure_helper_command(&mut command, "descendant");
    command.spawn().map_err(|_| CustodyError::SpawnFailed)
}

fn publish_worker_and_descendant(path: &Path, descendant_pid: u32) -> Result<(), CustodyError> {
    fs::write(path, format!("{} {descendant_pid}\n", std::process::id()))
        .map_err(|_| CustodyError::Io)
}

fn run_descendant_helper() -> Result<(), CustodyError> {
    let previous = unsafe {
        // SAFETY: this single-threaded synthetic descendant installs SIG_IGN
        // for SIGTERM before entering its wait loop.
        libc::signal(libc::SIGTERM, libc::SIG_IGN)
    };
    if previous == libc::SIG_ERR {
        return Err(CustodyError::SignalFailed);
    }
    loop {
        thread::park();
    }
}
