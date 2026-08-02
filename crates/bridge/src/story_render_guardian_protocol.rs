//! Dormant S635 GuardianV2 control and execution-plan protocol.
//!
//! This module is transport-only. It does not spawn a Guardian or Worker,
//! select a custody mode, expose a runtime surface, or authorize execution.

#![deny(clippy::all)]

use std::collections::BTreeMap;
use std::ffi::{CString, OsString};
use std::fs::File;
use std::io::{self, Read, Write};
use std::os::fd::{AsRawFd, FromRawFd, RawFd};
use std::os::unix::ffi::{OsStrExt, OsStringExt};
use std::os::unix::fs::FileExt;
use std::path::PathBuf;

use sha2::{Digest, Sha256};

pub const MAX_CONTROL_BODY_BYTES: usize = 64;
pub const MAX_EXEC_PLAN_BYTES: usize = 65_536;
const MAX_PLAN_COMPONENT_BYTES: usize = 4_096;
const MAX_ARGUMENTS: usize = 128;
const MAX_ENVIRONMENT_ENTRIES: usize = 64;
const CONTROL_MAGIC: &[u8; 4] = b"ABG2";
const CONTROL_VERSION: u8 = 2;
const EXEC_PLAN_MAGIC: &[u8; 8] = b"ABEP1\0\0\0";
const EXEC_PLAN_VERSION: u16 = 1;

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum WorkerExitV2 {
    Exited(i32),
    Signaled(i32),
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
#[repr(u8)]
pub enum GuardianStageV2 {
    Plan = 1,
    WorkerSpawn = 2,
    Protocol = 3,
    Cleanup = 4,
    Io = 5,
}

impl GuardianStageV2 {
    fn from_u8(value: u8) -> Option<Self> {
        match value {
            1 => Some(Self::Plan),
            2 => Some(Self::WorkerSpawn),
            3 => Some(Self::Protocol),
            4 => Some(Self::Cleanup),
            5 => Some(Self::Io),
            _ => None,
        }
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
#[repr(u8)]
pub enum GuardianFailureV2 {
    InvalidPlan = 1,
    SpawnFailed = 2,
    ProtocolRejected = 3,
    WorkerExitedWithLiveGroup = 4,
    CleanupUnproven = 5,
    Io = 6,
}

impl GuardianFailureV2 {
    fn from_u8(value: u8) -> Option<Self> {
        match value {
            1 => Some(Self::InvalidPlan),
            2 => Some(Self::SpawnFailed),
            3 => Some(Self::ProtocolRejected),
            4 => Some(Self::WorkerExitedWithLiveGroup),
            5 => Some(Self::CleanupUnproven),
            6 => Some(Self::Io),
            _ => None,
        }
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum GuardianFrameV2 {
    Bound {
        guardian_pid: u32,
        worker_pid: u32,
        worker_pgid: u32,
        plan_sha256: [u8; 32],
    },
    Start {
        worker_pid: u32,
        worker_pgid: u32,
        plan_sha256: [u8; 32],
    },
    Cancel {
        worker_pid: u32,
        worker_pgid: u32,
    },
    Terminal {
        worker_pid: u32,
        worker_pgid: u32,
        exit: WorkerExitV2,
    },
    Failure {
        stage: GuardianStageV2,
        failure: GuardianFailureV2,
        worker_pid: u32,
        worker_pgid: u32,
    },
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, thiserror::Error)]
pub enum ProtocolV2Error {
    #[error("unexpected_eof")]
    UnexpectedEof,
    #[error("oversized")]
    Oversized,
    #[error("invalid_frame")]
    InvalidFrame,
    #[error("io")]
    Io,
}

fn valid_pid(pid: u32) -> bool {
    pid > 1 && pid <= i32::MAX as u32
}

fn valid_binding(worker_pid: u32, worker_pgid: u32) -> bool {
    valid_pid(worker_pid) && worker_pid == worker_pgid
}

fn push_header(body: &mut Vec<u8>, tag: u8) {
    body.extend_from_slice(CONTROL_MAGIC);
    body.extend_from_slice(&[CONTROL_VERSION, tag, 0, 0]);
}

fn push_u32(body: &mut Vec<u8>, value: u32) {
    body.extend_from_slice(&value.to_be_bytes());
}

fn push_i32(body: &mut Vec<u8>, value: i32) {
    body.extend_from_slice(&value.to_be_bytes());
}

fn encode_control_body(frame: GuardianFrameV2) -> Result<Vec<u8>, ProtocolV2Error> {
    let mut body = Vec::with_capacity(MAX_CONTROL_BODY_BYTES);
    match frame {
        GuardianFrameV2::Bound {
            guardian_pid,
            worker_pid,
            worker_pgid,
            plan_sha256,
        } if valid_pid(guardian_pid) && valid_binding(worker_pid, worker_pgid) => {
            push_header(&mut body, 1);
            push_u32(&mut body, guardian_pid);
            push_u32(&mut body, worker_pid);
            push_u32(&mut body, worker_pgid);
            body.extend_from_slice(&plan_sha256);
        }
        GuardianFrameV2::Start {
            worker_pid,
            worker_pgid,
            plan_sha256,
        } if valid_binding(worker_pid, worker_pgid) => {
            push_header(&mut body, 2);
            push_u32(&mut body, worker_pid);
            push_u32(&mut body, worker_pgid);
            body.extend_from_slice(&plan_sha256);
        }
        GuardianFrameV2::Cancel {
            worker_pid,
            worker_pgid,
        } if valid_binding(worker_pid, worker_pgid) => {
            push_header(&mut body, 3);
            push_u32(&mut body, worker_pid);
            push_u32(&mut body, worker_pgid);
        }
        GuardianFrameV2::Terminal {
            worker_pid,
            worker_pgid,
            exit,
        } if valid_binding(worker_pid, worker_pgid) && valid_exit(exit) => {
            push_header(&mut body, 4);
            push_u32(&mut body, worker_pid);
            push_u32(&mut body, worker_pgid);
            match exit {
                WorkerExitV2::Exited(code) => {
                    body.extend_from_slice(&[1, 0, 0, 0]);
                    push_i32(&mut body, code);
                }
                WorkerExitV2::Signaled(signal) => {
                    body.extend_from_slice(&[2, 0, 0, 0]);
                    push_i32(&mut body, signal);
                }
            }
        }
        GuardianFrameV2::Failure {
            stage,
            failure,
            worker_pid,
            worker_pgid,
        } if (worker_pid == 0 && worker_pgid == 0) || valid_binding(worker_pid, worker_pgid) => {
            push_header(&mut body, 5);
            body.extend_from_slice(&[stage as u8, failure as u8, 0, 0]);
            push_u32(&mut body, worker_pid);
            push_u32(&mut body, worker_pgid);
        }
        _ => return Err(ProtocolV2Error::InvalidFrame),
    }
    if body.len() > MAX_CONTROL_BODY_BYTES {
        return Err(ProtocolV2Error::Oversized);
    }
    Ok(body)
}

fn valid_exit(exit: WorkerExitV2) -> bool {
    match exit {
        WorkerExitV2::Exited(code) => (0..=255).contains(&code),
        WorkerExitV2::Signaled(signal) => (1..=255).contains(&signal),
    }
}

pub fn write_frame_v2(
    writer: &mut impl Write,
    frame: GuardianFrameV2,
) -> Result<(), ProtocolV2Error> {
    writer
        .write_all(&encode_frame_v2(frame)?)
        .map_err(|_| ProtocolV2Error::Io)
}

pub fn encode_frame_v2(frame: GuardianFrameV2) -> Result<Vec<u8>, ProtocolV2Error> {
    let body = encode_control_body(frame)?;
    let length = u32::try_from(body.len()).map_err(|_| ProtocolV2Error::Oversized)?;
    let mut encoded = Vec::with_capacity(4 + body.len());
    encoded.extend_from_slice(&length.to_be_bytes());
    encoded.extend_from_slice(&body);
    Ok(encoded)
}

pub fn read_frame_v2(reader: &mut impl Read) -> Result<GuardianFrameV2, ProtocolV2Error> {
    let mut length_bytes = [0_u8; 4];
    read_exact_v2(reader, &mut length_bytes)?;
    let length = usize::try_from(u32::from_be_bytes(length_bytes))
        .map_err(|_| ProtocolV2Error::Oversized)?;
    if length > MAX_CONTROL_BODY_BYTES {
        return Err(ProtocolV2Error::Oversized);
    }
    let mut body = vec![0_u8; length];
    read_exact_v2(reader, &mut body)?;
    decode_control_body(&body)
}

pub fn decode_frame_body_v2(body: &[u8]) -> Result<GuardianFrameV2, ProtocolV2Error> {
    if body.len() > MAX_CONTROL_BODY_BYTES {
        return Err(ProtocolV2Error::Oversized);
    }
    decode_control_body(body)
}

fn read_exact_v2(reader: &mut impl Read, output: &mut [u8]) -> Result<(), ProtocolV2Error> {
    match reader.read_exact(output) {
        Ok(()) => Ok(()),
        Err(error) if error.kind() == io::ErrorKind::UnexpectedEof => {
            Err(ProtocolV2Error::UnexpectedEof)
        }
        Err(_) => Err(ProtocolV2Error::Io),
    }
}

fn u32_at(body: &[u8], offset: usize) -> Result<u32, ProtocolV2Error> {
    body.get(offset..offset + 4)
        .and_then(|bytes| bytes.try_into().ok())
        .map(u32::from_be_bytes)
        .ok_or(ProtocolV2Error::InvalidFrame)
}

fn i32_at(body: &[u8], offset: usize) -> Result<i32, ProtocolV2Error> {
    body.get(offset..offset + 4)
        .and_then(|bytes| bytes.try_into().ok())
        .map(i32::from_be_bytes)
        .ok_or(ProtocolV2Error::InvalidFrame)
}

fn decode_control_body(body: &[u8]) -> Result<GuardianFrameV2, ProtocolV2Error> {
    if body.len() < 8
        || body.get(..4) != Some(CONTROL_MAGIC)
        || body[4] != CONTROL_VERSION
        || body[6..8] != [0, 0]
    {
        return Err(ProtocolV2Error::InvalidFrame);
    }
    let frame = match (body[5], body.len()) {
        (1, 52) => {
            let mut plan_sha256 = [0_u8; 32];
            plan_sha256.copy_from_slice(&body[20..52]);
            GuardianFrameV2::Bound {
                guardian_pid: u32_at(body, 8)?,
                worker_pid: u32_at(body, 12)?,
                worker_pgid: u32_at(body, 16)?,
                plan_sha256,
            }
        }
        (2, 48) => {
            let mut plan_sha256 = [0_u8; 32];
            plan_sha256.copy_from_slice(&body[16..48]);
            GuardianFrameV2::Start {
                worker_pid: u32_at(body, 8)?,
                worker_pgid: u32_at(body, 12)?,
                plan_sha256,
            }
        }
        (3, 16) => GuardianFrameV2::Cancel {
            worker_pid: u32_at(body, 8)?,
            worker_pgid: u32_at(body, 12)?,
        },
        (4, 24) if body[17..20] == [0, 0, 0] => {
            let value = i32_at(body, 20)?;
            let exit = match body[16] {
                1 => WorkerExitV2::Exited(value),
                2 => WorkerExitV2::Signaled(value),
                _ => return Err(ProtocolV2Error::InvalidFrame),
            };
            GuardianFrameV2::Terminal {
                worker_pid: u32_at(body, 8)?,
                worker_pgid: u32_at(body, 12)?,
                exit,
            }
        }
        (5, 20) if body[10..12] == [0, 0] => GuardianFrameV2::Failure {
            stage: GuardianStageV2::from_u8(body[8]).ok_or(ProtocolV2Error::InvalidFrame)?,
            failure: GuardianFailureV2::from_u8(body[9]).ok_or(ProtocolV2Error::InvalidFrame)?,
            worker_pid: u32_at(body, 12)?,
            worker_pgid: u32_at(body, 16)?,
        },
        _ => return Err(ProtocolV2Error::InvalidFrame),
    };
    encode_control_body(frame)?;
    Ok(frame)
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct WorkerExecPlanV1 {
    pub executable: PathBuf,
    pub script: PathBuf,
    pub arguments: Vec<OsString>,
    pub environment: BTreeMap<OsString, OsString>,
    pub current_dir: PathBuf,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, thiserror::Error)]
pub enum ExecPlanError {
    #[error("invalid_plan")]
    InvalidPlan,
    #[error("invalid_encoding")]
    InvalidEncoding,
    #[error("oversized")]
    Oversized,
    #[error("unsealed")]
    Unsealed,
    #[error("io")]
    Io,
}

fn valid_component(bytes: &[u8], allow_empty: bool) -> bool {
    bytes.len() <= MAX_PLAN_COMPONENT_BYTES
        && (allow_empty || !bytes.is_empty())
        && !bytes.contains(&0)
}

fn validate_exec_plan(plan: &WorkerExecPlanV1) -> Result<(), ExecPlanError> {
    if !plan.executable.is_absolute()
        || !plan.script.is_absolute()
        || plan.current_dir.as_path() != std::path::Path::new("/")
        || plan.arguments.len() > MAX_ARGUMENTS
        || plan.environment.len() > MAX_ENVIRONMENT_ENTRIES
        || !valid_component(plan.executable.as_os_str().as_bytes(), false)
        || !valid_component(plan.script.as_os_str().as_bytes(), false)
    {
        return Err(ExecPlanError::InvalidPlan);
    }
    if plan
        .arguments
        .iter()
        .any(|argument| !valid_component(argument.as_bytes(), true))
    {
        return Err(ExecPlanError::InvalidPlan);
    }
    if plan.environment.iter().any(|(key, value)| {
        !valid_component(key.as_bytes(), false)
            || key.as_bytes().contains(&b'=')
            || !valid_component(value.as_bytes(), true)
    }) {
        return Err(ExecPlanError::InvalidPlan);
    }
    Ok(())
}

fn push_bytes(output: &mut Vec<u8>, bytes: &[u8]) -> Result<(), ExecPlanError> {
    let length = u32::try_from(bytes.len()).map_err(|_| ExecPlanError::Oversized)?;
    output.extend_from_slice(&length.to_be_bytes());
    output.extend_from_slice(bytes);
    Ok(())
}

pub fn encode_exec_plan(plan: &WorkerExecPlanV1) -> Result<Vec<u8>, ExecPlanError> {
    validate_exec_plan(plan)?;
    let mut output = Vec::new();
    output.extend_from_slice(EXEC_PLAN_MAGIC);
    output.extend_from_slice(&EXEC_PLAN_VERSION.to_be_bytes());
    output.extend_from_slice(&0_u16.to_be_bytes());
    push_bytes(&mut output, plan.executable.as_os_str().as_bytes())?;
    push_bytes(&mut output, plan.script.as_os_str().as_bytes())?;
    push_bytes(&mut output, plan.current_dir.as_os_str().as_bytes())?;
    output.extend_from_slice(
        &u16::try_from(plan.arguments.len())
            .map_err(|_| ExecPlanError::Oversized)?
            .to_be_bytes(),
    );
    for argument in &plan.arguments {
        push_bytes(&mut output, argument.as_bytes())?;
    }
    output.extend_from_slice(
        &u16::try_from(plan.environment.len())
            .map_err(|_| ExecPlanError::Oversized)?
            .to_be_bytes(),
    );
    for (key, value) in &plan.environment {
        push_bytes(&mut output, key.as_bytes())?;
        push_bytes(&mut output, value.as_bytes())?;
    }
    if output.len() > MAX_EXEC_PLAN_BYTES {
        return Err(ExecPlanError::Oversized);
    }
    Ok(output)
}

struct PlanReader<'a> {
    bytes: &'a [u8],
    offset: usize,
}

impl<'a> PlanReader<'a> {
    fn new(bytes: &'a [u8]) -> Self {
        Self { bytes, offset: 0 }
    }

    fn take(&mut self, count: usize) -> Result<&'a [u8], ExecPlanError> {
        let end = self
            .offset
            .checked_add(count)
            .ok_or(ExecPlanError::InvalidEncoding)?;
        let value = self
            .bytes
            .get(self.offset..end)
            .ok_or(ExecPlanError::InvalidEncoding)?;
        self.offset = end;
        Ok(value)
    }

    fn u16(&mut self) -> Result<u16, ExecPlanError> {
        self.take(2)?
            .try_into()
            .map(u16::from_be_bytes)
            .map_err(|_| ExecPlanError::InvalidEncoding)
    }

    fn bytes(&mut self) -> Result<Vec<u8>, ExecPlanError> {
        let length = self
            .take(4)?
            .try_into()
            .map(u32::from_be_bytes)
            .map_err(|_| ExecPlanError::InvalidEncoding)?;
        let length = usize::try_from(length).map_err(|_| ExecPlanError::Oversized)?;
        if length > MAX_PLAN_COMPONENT_BYTES {
            return Err(ExecPlanError::Oversized);
        }
        Ok(self.take(length)?.to_vec())
    }

    fn is_finished(&self) -> bool {
        self.offset == self.bytes.len()
    }
}

pub fn decode_exec_plan(bytes: &[u8]) -> Result<WorkerExecPlanV1, ExecPlanError> {
    if bytes.len() > MAX_EXEC_PLAN_BYTES {
        return Err(ExecPlanError::Oversized);
    }
    let mut reader = PlanReader::new(bytes);
    if reader.take(8)? != EXEC_PLAN_MAGIC
        || reader.u16()? != EXEC_PLAN_VERSION
        || reader.u16()? != 0
    {
        return Err(ExecPlanError::InvalidEncoding);
    }
    let executable = PathBuf::from(OsString::from_vec(reader.bytes()?));
    let script = PathBuf::from(OsString::from_vec(reader.bytes()?));
    let current_dir = PathBuf::from(OsString::from_vec(reader.bytes()?));
    let argument_count = usize::from(reader.u16()?);
    if argument_count > MAX_ARGUMENTS {
        return Err(ExecPlanError::Oversized);
    }
    let mut arguments = Vec::with_capacity(argument_count);
    for _ in 0..argument_count {
        arguments.push(OsString::from_vec(reader.bytes()?));
    }
    let environment_count = usize::from(reader.u16()?);
    if environment_count > MAX_ENVIRONMENT_ENTRIES {
        return Err(ExecPlanError::Oversized);
    }
    let mut environment = BTreeMap::new();
    for _ in 0..environment_count {
        let key = OsString::from_vec(reader.bytes()?);
        let value = OsString::from_vec(reader.bytes()?);
        if environment.insert(key, value).is_some() {
            return Err(ExecPlanError::InvalidEncoding);
        }
    }
    if !reader.is_finished() {
        return Err(ExecPlanError::InvalidEncoding);
    }
    let plan = WorkerExecPlanV1 {
        executable,
        script,
        arguments,
        environment,
        current_dir,
    };
    validate_exec_plan(&plan)?;
    if encode_exec_plan(&plan)? != bytes {
        return Err(ExecPlanError::InvalidEncoding);
    }
    Ok(plan)
}

pub struct SealedExecPlan {
    file: File,
    sha256: [u8; 32],
}

impl SealedExecPlan {
    pub fn create(plan: &WorkerExecPlanV1) -> Result<Self, ExecPlanError> {
        let encoded = encode_exec_plan(plan)?;
        let name = CString::new("ab-story-render-plan").map_err(|_| ExecPlanError::Io)?;
        let raw_fd = unsafe {
            // SAFETY: the name is a valid NUL-terminated C string and the
            // flags are defined by memfd_create. Ownership transfers to File.
            libc::syscall(
                libc::SYS_memfd_create,
                name.as_ptr(),
                libc::MFD_CLOEXEC | libc::MFD_ALLOW_SEALING,
            )
        };
        if raw_fd == -1 {
            return Err(ExecPlanError::Io);
        }
        let raw_fd = RawFd::try_from(raw_fd).map_err(|_| ExecPlanError::Io)?;
        let mut file = unsafe {
            // SAFETY: memfd_create returned a new descriptor owned by us.
            File::from_raw_fd(raw_fd)
        };
        file.write_all(&encoded).map_err(|_| ExecPlanError::Io)?;
        file.sync_all().map_err(|_| ExecPlanError::Io)?;
        let seals =
            libc::F_SEAL_WRITE | libc::F_SEAL_GROW | libc::F_SEAL_SHRINK | libc::F_SEAL_SEAL;
        let seal_result = unsafe {
            // SAFETY: fcntl acts on the valid memfd and consumes no pointers.
            libc::fcntl(file.as_raw_fd(), libc::F_ADD_SEALS, seals)
        };
        if seal_result == -1 {
            return Err(ExecPlanError::Io);
        }
        let sha256: [u8; 32] = Sha256::digest(&encoded).into();
        Ok(Self { file, sha256 })
    }

    pub fn file(&self) -> &File {
        &self.file
    }

    pub fn sha256(&self) -> [u8; 32] {
        self.sha256
    }
}

impl AsRawFd for SealedExecPlan {
    fn as_raw_fd(&self) -> RawFd {
        self.file.as_raw_fd()
    }
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct DecodedSealedExecPlan {
    pub plan: WorkerExecPlanV1,
    pub sha256: [u8; 32],
}

pub fn read_sealed_exec_plan(file: &File) -> Result<DecodedSealedExecPlan, ExecPlanError> {
    let required = libc::F_SEAL_WRITE | libc::F_SEAL_GROW | libc::F_SEAL_SHRINK | libc::F_SEAL_SEAL;
    let seals = unsafe {
        // SAFETY: fcntl queries seal bits from the valid descriptor.
        libc::fcntl(file.as_raw_fd(), libc::F_GET_SEALS)
    };
    if seals == -1 {
        return Err(ExecPlanError::Io);
    }
    if seals & required != required {
        return Err(ExecPlanError::Unsealed);
    }
    let length = usize::try_from(file.metadata().map_err(|_| ExecPlanError::Io)?.len())
        .map_err(|_| ExecPlanError::Oversized)?;
    if length > MAX_EXEC_PLAN_BYTES {
        return Err(ExecPlanError::Oversized);
    }
    let mut encoded = vec![0_u8; length];
    let mut offset = 0;
    while offset < encoded.len() {
        let count = file
            .read_at(&mut encoded[offset..], offset as u64)
            .map_err(|_| ExecPlanError::Io)?;
        if count == 0 {
            return Err(ExecPlanError::InvalidEncoding);
        }
        offset += count;
    }
    let sha256: [u8; 32] = Sha256::digest(&encoded).into();
    let plan = decode_exec_plan(&encoded)?;
    Ok(DecodedSealedExecPlan { plan, sha256 })
}
