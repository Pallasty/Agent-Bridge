//! Linux-only helper for the Invocation Guardian v2 C2 isolation preflight.
//!
//! This binary deliberately implements no guardian protocol and grants no
//! authority. A root-owned harness runs `serve` and `attack` under distinct
//! existing UIDs to test the operating-system substrate before any v2 service
//! can be considered for deployment.

#![cfg(target_os = "linux")]

use std::fs::{File, OpenOptions};
use std::io::{Read, Write};
use std::os::fd::{AsRawFd, RawFd};
use std::os::unix::fs::{FileTypeExt, MetadataExt, OpenOptionsExt, PermissionsExt};
use std::os::unix::net::{UnixListener, UnixStream};
use std::path::{Component, Path, PathBuf};
use std::time::Duration;

use anyhow::{bail, Context, Result};
use clap::{Parser, Subcommand, ValueEnum};
use serde::Serialize;

const SOCKET_MODE: u32 = 0o660;
const SOCKET_PARENT_MODE: u32 = 0o2750;
const STATE_DIRECTORY_MODE: u32 = 0o700;
const STATE_FILE_MODE: u32 = 0o600;
const PING: u8 = 0xc2;
const PONG: u8 = 0x2c;

#[derive(Debug, Parser)]
#[command(
    name = "invocation-guardian-isolation-probe",
    about = "Non-authoritative C2 Linux UID/IPC isolation probe helper"
)]
struct Args {
    #[command(subcommand)]
    command: Command,
}

#[derive(Debug, Subcommand)]
enum Command {
    /// Run a minimal peer-credential-checking Unix socket server.
    Serve {
        #[arg(long)]
        socket: PathBuf,
        #[arg(long)]
        state_dir: PathBuf,
        #[arg(long)]
        ready_file: PathBuf,
        #[arg(long)]
        expected_bridge_uid: u32,
        #[arg(long)]
        socket_gid: u32,
    },
    /// Attempt every operation that C2 requires the kernel to allow or deny.
    Attack {
        #[arg(long)]
        role: String,
        #[arg(long)]
        socket: PathBuf,
        #[arg(long)]
        state_dir: PathBuf,
        #[arg(long)]
        attacker_dir: PathBuf,
        #[arg(long)]
        guardian_uid: u32,
        #[arg(long)]
        guardian_pid: u32,
        #[arg(long)]
        socket_gid: u32,
        #[arg(long)]
        listener_fd_inode: u64,
        #[arg(long, value_enum)]
        expect_connect: Expectation,
        #[arg(long, value_enum)]
        expect_socket_group: Expectation,
    },
}

#[derive(Clone, Copy, Debug, Eq, PartialEq, ValueEnum)]
enum Expectation {
    Allow,
    Deny,
}

impl Expectation {
    const fn matches(self, observed: bool) -> bool {
        observed == matches!(self, Self::Allow)
    }

    const fn label(self) -> &'static str {
        match self {
            Self::Allow => "allow",
            Self::Deny => "deny",
        }
    }
}

#[derive(Debug, Serialize)]
struct ReadyEvidence {
    schema: &'static str,
    pid: u32,
    guardian_uid: u32,
    guardian_gid: u32,
    expected_bridge_uid: u32,
    socket_gid: u32,
    listener_fd_inode: u64,
    production_authority: bool,
}

#[derive(Debug, Serialize)]
struct AttackEvidence {
    schema: &'static str,
    role: String,
    status: &'static str,
    attacker_uid: u32,
    attacker_gid: u32,
    guardian_uid: u32,
    guardian_pid: u32,
    expected_connect: &'static str,
    expected_socket_group: &'static str,
    connect_authenticated: bool,
    socket_group_present: bool,
    state_read_opened: bool,
    state_write_opened: bool,
    state_unlinked: bool,
    state_renamed: bool,
    socket_unlinked: bool,
    socket_renamed: bool,
    socket_replaced: bool,
    ptrace_attached: bool,
    listener_fd_inherited: bool,
    production_authority: bool,
}

impl AttackEvidence {
    fn passes(&self, connect: Expectation, socket_group: Expectation) -> bool {
        self.attacker_uid != 0
            && self.attacker_uid != self.guardian_uid
            && connect.matches(self.connect_authenticated)
            && socket_group.matches(self.socket_group_present)
            && !self.state_read_opened
            && !self.state_write_opened
            && !self.state_unlinked
            && !self.state_renamed
            && !self.socket_unlinked
            && !self.socket_renamed
            && !self.socket_replaced
            && !self.ptrace_attached
            && !self.listener_fd_inherited
    }
}

fn main() -> Result<()> {
    match Args::parse().command {
        Command::Serve {
            socket,
            state_dir,
            ready_file,
            expected_bridge_uid,
            socket_gid,
        } => serve(
            &socket,
            &state_dir,
            &ready_file,
            expected_bridge_uid,
            socket_gid,
        ),
        Command::Attack {
            role,
            socket,
            state_dir,
            attacker_dir,
            guardian_uid,
            guardian_pid,
            socket_gid,
            listener_fd_inode,
            expect_connect,
            expect_socket_group,
        } => attack(
            role,
            &socket,
            &state_dir,
            &attacker_dir,
            guardian_uid,
            guardian_pid,
            socket_gid,
            listener_fd_inode,
            expect_connect,
            expect_socket_group,
        ),
    }
}

fn serve(
    socket: &Path,
    state_dir: &Path,
    ready_file: &Path,
    expected_bridge_uid: u32,
    socket_gid: u32,
) -> Result<()> {
    let guardian_uid = effective_uid();
    let guardian_gid = effective_gid();
    if guardian_uid == 0
        || expected_bridge_uid == 0
        || guardian_uid == expected_bridge_uid
        || socket_gid == 0
        || socket_gid == guardian_gid
    {
        bail!("guardian, bridge, and socket-group identities must be distinct non-root values");
    }
    validate_directory(state_dir, guardian_uid, guardian_gid, STATE_DIRECTORY_MODE)?;
    let socket_parent = socket.parent().context("socket has no parent")?;
    validate_directory(socket_parent, guardian_uid, socket_gid, SOCKET_PARENT_MODE)?;
    validate_direct_child(ready_file, state_dir)?;
    validate_direct_child(socket, socket_parent)?;

    for name in ["read.state", "write.state", "unlink.state", "rename.state"] {
        create_private_file(&state_dir.join(name), b"c2-isolation-probe\n")?;
    }

    let listener = bind_socket(socket, guardian_uid, socket_gid)?;
    let _unlink_decoy = bind_socket(&socket_parent.join("unlink.sock"), guardian_uid, socket_gid)?;
    let _rename_decoy = bind_socket(&socket_parent.join("rename.sock"), guardian_uid, socket_gid)?;
    let _replace_decoy = bind_socket(
        &socket_parent.join("replace.sock"),
        guardian_uid,
        socket_gid,
    )?;
    let listener_fd_inode = fd_inode(listener.as_raw_fd())?;
    let ready = ReadyEvidence {
        schema: "agent_bridge.invocation_guardian_c2_ready.v1",
        pid: std::process::id(),
        guardian_uid,
        guardian_gid,
        expected_bridge_uid,
        socket_gid,
        listener_fd_inode,
        production_authority: false,
    };
    let mut ready_output = OpenOptions::new()
        .write(true)
        .create_new(true)
        .mode(STATE_FILE_MODE)
        .open(ready_file)
        .context("create ready evidence")?;
    serde_json::to_writer(&mut ready_output, &ready)?;
    ready_output.write_all(b"\n")?;
    ready_output.sync_all()?;
    File::open(state_dir)?.sync_all()?;

    loop {
        let (mut stream, _) = listener.accept()?;
        let peer_uid = peer_uid(stream.as_raw_fd());
        let mut request = [0_u8; 1];
        if peer_uid == Some(expected_bridge_uid)
            && stream.read_exact(&mut request).is_ok()
            && request[0] == PING
        {
            let _ = stream.write_all(&[PONG]);
        }
    }
}

#[allow(clippy::too_many_arguments)]
fn attack(
    role: String,
    socket: &Path,
    state_dir: &Path,
    attacker_dir: &Path,
    guardian_uid: u32,
    guardian_pid: u32,
    socket_gid: u32,
    listener_fd_inode: u64,
    expect_connect: Expectation,
    expect_socket_group: Expectation,
) -> Result<()> {
    validate_normalized_absolute(socket)?;
    validate_normalized_absolute(state_dir)?;
    validate_normalized_absolute(attacker_dir)?;
    let socket_parent = socket.parent().context("socket has no parent")?;
    let attacker_uid = effective_uid();
    let attacker_gid = effective_gid();
    validate_directory(
        attacker_dir,
        attacker_uid,
        attacker_gid,
        STATE_DIRECTORY_MODE,
    )?;

    let connect_authenticated = connect_authenticated(socket, guardian_uid);
    let socket_group_present = supplementary_groups()?.contains(&socket_gid);
    let state_read_opened = File::open(state_dir.join("read.state")).is_ok();
    let state_write_opened = OpenOptions::new()
        .write(true)
        .open(state_dir.join("write.state"))
        .is_ok();
    let state_unlinked = std::fs::remove_file(state_dir.join("unlink.state")).is_ok();
    let state_renamed = std::fs::rename(
        state_dir.join("rename.state"),
        attacker_dir.join("stolen.state"),
    )
    .is_ok();
    let socket_unlinked = std::fs::remove_file(socket_parent.join("unlink.sock")).is_ok();
    let socket_renamed = std::fs::rename(
        socket_parent.join("rename.sock"),
        attacker_dir.join("stolen.sock"),
    )
    .is_ok();
    let replacement = attacker_dir.join("replacement.node");
    let _ = OpenOptions::new()
        .write(true)
        .create_new(true)
        .mode(STATE_FILE_MODE)
        .open(&replacement);
    let socket_replaced = std::fs::rename(replacement, socket_parent.join("replace.sock")).is_ok();
    let ptrace_attached = try_ptrace_attach(guardian_pid);
    let listener_fd_inherited = inherited_socket_inode(listener_fd_inode)?;

    let mut evidence = AttackEvidence {
        schema: "agent_bridge.invocation_guardian_c2_attack.v1",
        role,
        status: "HOLD",
        attacker_uid,
        attacker_gid,
        guardian_uid,
        guardian_pid,
        expected_connect: expect_connect.label(),
        expected_socket_group: expect_socket_group.label(),
        connect_authenticated,
        socket_group_present,
        state_read_opened,
        state_write_opened,
        state_unlinked,
        state_renamed,
        socket_unlinked,
        socket_renamed,
        socket_replaced,
        ptrace_attached,
        listener_fd_inherited,
        production_authority: false,
    };
    let passed = evidence.passes(expect_connect, expect_socket_group);
    evidence.status = if passed { "PASS" } else { "FAIL" };
    println!("{}", serde_json::to_string(&evidence)?);
    if !passed {
        bail!("C2 attack expectations were not satisfied");
    }
    Ok(())
}

fn bind_socket(path: &Path, uid: u32, gid: u32) -> Result<UnixListener> {
    if std::fs::symlink_metadata(path).is_ok() {
        bail!(
            "refusing to replace existing socket node: {}",
            path.display()
        );
    }
    let listener = UnixListener::bind(path)?;
    std::fs::set_permissions(path, std::fs::Permissions::from_mode(SOCKET_MODE))?;
    let metadata = std::fs::symlink_metadata(path)?;
    if !metadata.file_type().is_socket()
        || metadata.file_type().is_symlink()
        || metadata.uid() != uid
        || metadata.gid() != gid
        || metadata.mode() & 0o777 != SOCKET_MODE
    {
        bail!("bound socket identity or mode mismatch: {}", path.display());
    }
    Ok(listener)
}

fn create_private_file(path: &Path, contents: &[u8]) -> Result<()> {
    let mut file = OpenOptions::new()
        .write(true)
        .create_new(true)
        .mode(STATE_FILE_MODE)
        .open(path)?;
    file.write_all(contents)?;
    file.sync_all()?;
    Ok(())
}

fn validate_directory(path: &Path, uid: u32, gid: u32, mode: u32) -> Result<()> {
    validate_normalized_absolute(path)?;
    if std::fs::canonicalize(path)? != path {
        bail!(
            "directory contains a symlinked ancestor: {}",
            path.display()
        );
    }
    let metadata = std::fs::symlink_metadata(path)?;
    if !metadata.is_dir()
        || metadata.file_type().is_symlink()
        || metadata.uid() != uid
        || metadata.gid() != gid
        || metadata.mode() & 0o7777 != mode
    {
        bail!("directory identity or mode mismatch: {}", path.display());
    }
    Ok(())
}

fn validate_direct_child(path: &Path, parent: &Path) -> Result<()> {
    validate_normalized_absolute(path)?;
    if path.parent() != Some(parent) {
        bail!("path must be a direct child of its protected directory");
    }
    Ok(())
}

fn validate_normalized_absolute(path: &Path) -> Result<()> {
    if !path.is_absolute()
        || path.components().any(|component| {
            matches!(
                component,
                Component::CurDir | Component::ParentDir | Component::Prefix(_)
            )
        })
    {
        bail!("path must be normalized and absolute: {}", path.display());
    }
    Ok(())
}

fn connect_authenticated(socket: &Path, guardian_uid: u32) -> bool {
    let Ok(mut stream) = UnixStream::connect(socket) else {
        return false;
    };
    let _ = stream.set_read_timeout(Some(Duration::from_secs(2)));
    let _ = stream.set_write_timeout(Some(Duration::from_secs(2)));
    if peer_uid(stream.as_raw_fd()) != Some(guardian_uid) || stream.write_all(&[PING]).is_err() {
        return false;
    }
    let mut response = [0_u8; 1];
    stream.read_exact(&mut response).is_ok() && response[0] == PONG
}

fn peer_uid(fd: RawFd) -> Option<u32> {
    let mut credential = std::mem::MaybeUninit::<libc::ucred>::uninit();
    let mut length = std::mem::size_of::<libc::ucred>() as libc::socklen_t;
    let result = unsafe {
        libc::getsockopt(
            fd,
            libc::SOL_SOCKET,
            libc::SO_PEERCRED,
            credential.as_mut_ptr().cast(),
            &mut length,
        )
    };
    if result == 0 && length as usize == std::mem::size_of::<libc::ucred>() {
        Some(unsafe { credential.assume_init() }.uid)
    } else {
        None
    }
}

fn supplementary_groups() -> Result<Vec<u32>> {
    let count = unsafe { libc::getgroups(0, std::ptr::null_mut()) };
    if count < 0 {
        return Err(std::io::Error::last_os_error().into());
    }
    let mut groups = vec![0 as libc::gid_t; count as usize];
    if count > 0 && unsafe { libc::getgroups(count, groups.as_mut_ptr()) } < 0 {
        return Err(std::io::Error::last_os_error().into());
    }
    groups.push(effective_gid());
    groups.sort_unstable();
    groups.dedup();
    Ok(groups)
}

fn try_ptrace_attach(pid: u32) -> bool {
    let result = unsafe {
        libc::ptrace(
            libc::PTRACE_ATTACH,
            pid as libc::pid_t,
            std::ptr::null_mut::<libc::c_void>(),
            std::ptr::null_mut::<libc::c_void>(),
        )
    };
    if result != 0 {
        return false;
    }
    let mut status = 0;
    let _ = unsafe { libc::waitpid(pid as libc::pid_t, &mut status, 0) };
    let _ = unsafe {
        libc::ptrace(
            libc::PTRACE_DETACH,
            pid as libc::pid_t,
            std::ptr::null_mut::<libc::c_void>(),
            std::ptr::null_mut::<libc::c_void>(),
        )
    };
    true
}

fn inherited_socket_inode(expected: u64) -> Result<bool> {
    for entry in std::fs::read_dir("/proc/self/fd")? {
        let Ok(name) = entry?.file_name().to_string_lossy().parse::<RawFd>() else {
            continue;
        };
        let mut status = std::mem::MaybeUninit::<libc::stat>::uninit();
        if unsafe { libc::fstat(name, status.as_mut_ptr()) } != 0 {
            continue;
        }
        let status = unsafe { status.assume_init() };
        if status.st_ino == expected && status.st_mode & libc::S_IFMT == libc::S_IFSOCK {
            return Ok(true);
        }
    }
    Ok(false)
}

fn fd_inode(fd: RawFd) -> Result<u64> {
    let mut status = std::mem::MaybeUninit::<libc::stat>::uninit();
    if unsafe { libc::fstat(fd, status.as_mut_ptr()) } != 0 {
        return Err(std::io::Error::last_os_error().into());
    }
    Ok(unsafe { status.assume_init() }.st_ino)
}

fn effective_uid() -> u32 {
    unsafe { libc::geteuid() }
}

fn effective_gid() -> u32 {
    unsafe { libc::getegid() }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn safe_evidence() -> AttackEvidence {
        AttackEvidence {
            schema: "agent_bridge.invocation_guardian_c2_attack.v1",
            role: "bridge".into(),
            status: "PASS",
            attacker_uid: 1001,
            attacker_gid: 1001,
            guardian_uid: 1002,
            guardian_pid: 42,
            expected_connect: "allow",
            expected_socket_group: "allow",
            connect_authenticated: true,
            socket_group_present: true,
            state_read_opened: false,
            state_write_opened: false,
            state_unlinked: false,
            state_renamed: false,
            socket_unlinked: false,
            socket_renamed: false,
            socket_replaced: false,
            ptrace_attached: false,
            listener_fd_inherited: false,
            production_authority: false,
        }
    }

    #[test]
    fn bridge_requires_authenticated_connect_and_every_mutation_denied() {
        let evidence = safe_evidence();
        assert!(evidence.passes(Expectation::Allow, Expectation::Allow));
        assert!(!evidence.passes(Expectation::Deny, Expectation::Allow));
        let mut drift = safe_evidence();
        drift.socket_unlinked = true;
        assert!(!drift.passes(Expectation::Allow, Expectation::Allow));
    }

    #[test]
    fn agent_requires_no_group_no_connect_and_every_mutation_denied() {
        let mut evidence = safe_evidence();
        evidence.role = "agent".into();
        evidence.connect_authenticated = false;
        evidence.socket_group_present = false;
        assert!(evidence.passes(Expectation::Deny, Expectation::Deny));
        evidence.listener_fd_inherited = true;
        assert!(!evidence.passes(Expectation::Deny, Expectation::Deny));
    }

    #[test]
    fn server_rejects_root_or_same_uid_before_touching_paths() {
        let error = serve(
            Path::new("/path/is/not/consulted/guardian.sock"),
            Path::new("/path/is/not/consulted/state"),
            Path::new("/path/is/not/consulted/ready.json"),
            effective_uid(),
            effective_gid(),
        )
        .unwrap_err();
        assert!(error
            .to_string()
            .contains("must be distinct non-root values"));
    }
}
