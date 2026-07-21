//! Synthetic-only G1 retained-descriptor custody implementation prerequisite.
//!
//! This private module is disabled by default and compiled only on macOS. It
//! can be entered only with a test-only permit, traverses only disposable
//! synthetic trees, and never composes with the authenticated-envelope shadow.
//! A successful result proves a narrow descriptor-lifetime and path-identity
//! property; it is not secure custody for real corpus bytes and cannot confer
//! freeze, G1.4, capability, write, execution, or runtime authority.

#![cfg_attr(not(test), allow(dead_code))]

use sha2::{Digest, Sha256};
use std::ffi::CString;
use std::fs::File;
use std::io::Read;
use std::mem::MaybeUninit;
use std::os::fd::{AsRawFd, FromRawFd, OwnedFd, RawFd};
use std::os::unix::ffi::OsStrExt;
use std::path::Path;

const _: () = assert!(std::mem::size_of::<libc::fsid_t>() == 8);

const MAX_ABSOLUTE_COMPONENTS: usize = 64;
const MAX_RELATIVE_COMPONENTS: usize = 16;
const MAX_COMPONENT_BYTES: usize = 255;
const MAX_SYNTHETIC_FILE_BYTES: usize = 1_048_576;
const SYNTHETIC_ROOT_PREFIX: &[u8] = b"agent-bridge-engram-g1-custody-shadow-";
// Present in the current Darwin SDK but not yet exported by libc 0.2.186.
// Darwin open(2) assigns 0x00002000 to O_UNIQUE: opening fails unless the
// target has exactly one hard link. Unsupported kernels therefore fail closed.
const DARWIN_O_UNIQUE: libc::c_int = 0x00002000;
const IMPLEMENTATION_PROFILE: &str =
    "ab_store_engram_g1_secure_custody_retained_descriptor_shadow_macos_apfs_v0";
const CHAIN_COMMITMENT_DOMAIN: &[u8] =
    b"agent-bridge/engram/g1/secure-custody/synthetic-descriptor-chain/v0";

#[derive(Debug, thiserror::Error)]
#[error("{code}: {detail}")]
struct SyntheticCustodyError {
    code: &'static str,
    detail: &'static str,
}

impl SyntheticCustodyError {
    #[cfg(test)]
    fn code(&self) -> &'static str {
        self.code
    }
}

type CustodyResult<T> = Result<T, SyntheticCustodyError>;

fn custody_error(code: &'static str, detail: &'static str) -> SyntheticCustodyError {
    SyntheticCustodyError { code, detail }
}

/// There is deliberately no non-test constructor for this permit.
struct SyntheticCustodyPermitV1 {
    _private: (),
}

#[cfg(test)]
fn synthetic_test_permit_v1() -> SyntheticCustodyPermitV1 {
    SyntheticCustodyPermitV1 { _private: () }
}

#[derive(Debug, Clone, PartialEq, Eq)]
struct StatSnapshot {
    dev: u64,
    ino: u64,
    mode: u32,
    nlink: u64,
    uid: u32,
    gid: u32,
    rdev: u64,
    size: i64,
    blocks: i64,
    blksize: i32,
    mtime: i64,
    mtime_nsec: i64,
    ctime: i64,
    ctime_nsec: i64,
    birthtime: i64,
    birthtime_nsec: i64,
    flags: u32,
    generation: u32,
}

impl StatSnapshot {
    fn from_raw(value: &libc::stat) -> Self {
        Self {
            dev: value.st_dev as u64,
            ino: value.st_ino,
            mode: value.st_mode as u32,
            nlink: value.st_nlink as u64,
            uid: value.st_uid,
            gid: value.st_gid,
            rdev: value.st_rdev as u64,
            size: value.st_size,
            blocks: value.st_blocks,
            blksize: value.st_blksize,
            mtime: value.st_mtime,
            mtime_nsec: value.st_mtime_nsec,
            ctime: value.st_ctime,
            ctime_nsec: value.st_ctime_nsec,
            birthtime: value.st_birthtime,
            birthtime_nsec: value.st_birthtime_nsec,
            flags: value.st_flags,
            generation: value.st_gen,
        }
    }

    fn file_type(&self) -> u32 {
        self.mode & libc::S_IFMT as u32
    }

    fn permissions(&self) -> u32 {
        self.mode & 0o7777
    }

    fn same_object(&self, other: &Self) -> bool {
        self.dev == other.dev && self.ino == other.ino && self.file_type() == other.file_type()
    }

    fn stable_without_atime(&self, other: &Self) -> bool {
        self == other
    }
}

#[derive(Debug, Clone, PartialEq, Eq)]
struct MountFingerprint {
    device: u64,
    fsid_bytes: [u8; 8],
    fs_type: [u8; 16],
    mount_on: [u8; 1024],
    mount_from: [u8; 1024],
    fs_type_number: u32,
    flags: u32,
    local: bool,
}

impl MountFingerprint {
    fn fs_type_name(&self) -> &[u8] {
        let end = self
            .fs_type
            .iter()
            .position(|byte| *byte == 0)
            .unwrap_or(self.fs_type.len());
        &self.fs_type[..end]
    }
}

struct RetainedDirectory {
    fd: OwnedFd,
    opened: StatSnapshot,
    mount: MountFingerprint,
    parent_index: Option<usize>,
    name_from_parent: Option<CString>,
    private_custody_directory: bool,
}

#[must_use = "synthetic custody conformance is not real custody or authority"]
#[derive(Debug, PartialEq, Eq)]
struct SyntheticCustodyConformanceV1 {
    implementation_profile: &'static str,
    content_sha256: [u8; 32],
    content_byte_length: u64,
    retained_descriptor_chain_sha256: [u8; 32],
    retained_directory_descriptor_count: usize,
    synthetic_disposable_tree_only: bool,
    synthetic_retained_descriptor_conformance_verified: bool,
    component_by_component_nofollow_verified: bool,
    effective_uid_and_exact_posix_modes_verified: bool,
    single_link_regular_file_verified: bool,
    same_local_apfs_mount_verified: bool,
    before_after_identity_stability_verified: bool,
    final_name_to_inode_revalidation_verified: bool,
    secure_custody_capture_verified: bool,
    authenticated_envelope_composed: bool,
    durable_trust_ledger_verified: bool,
    trusted_time_verified: bool,
    durable_replay_claim_verified: bool,
    capability_minted: bool,
    freeze_authority_verified: bool,
    ready_for_g1_4_candidate_protocol_preregistration: bool,
    runtime_authority: bool,
}

fn stat_fd(fd: RawFd) -> CustodyResult<StatSnapshot> {
    let mut raw = MaybeUninit::<libc::stat>::uninit();
    // SAFETY: `raw` points to writable storage for one `libc::stat`, and `fd`
    // is retained by the caller for the duration of this call.
    if unsafe { libc::fstat(fd, raw.as_mut_ptr()) } != 0 {
        return Err(custody_error(
            "DESCRIPTOR_STAT",
            "retained descriptor metadata could not be read",
        ));
    }
    // SAFETY: successful `fstat` initialized the complete structure.
    Ok(StatSnapshot::from_raw(unsafe { &raw.assume_init() }))
}

fn stat_at(parent_fd: RawFd, name: &CString) -> CustodyResult<StatSnapshot> {
    let mut raw = MaybeUninit::<libc::stat>::uninit();
    // SAFETY: `name` is NUL-terminated, `raw` is valid writable storage, and
    // `AT_SYMLINK_NOFOLLOW` prevents the final name from being dereferenced.
    if unsafe {
        libc::fstatat(
            parent_fd,
            name.as_ptr(),
            raw.as_mut_ptr(),
            libc::AT_SYMLINK_NOFOLLOW,
        )
    } != 0
    {
        return Err(custody_error(
            "NAME_STAT",
            "a retained parent could not revalidate its child name",
        ));
    }
    // SAFETY: successful `fstatat` initialized the complete structure.
    Ok(StatSnapshot::from_raw(unsafe { &raw.assume_init() }))
}

fn c_char_array<const N: usize>(source: &[libc::c_char; N]) -> [u8; N] {
    let mut output = [0_u8; N];
    for (target, value) in output.iter_mut().zip(source.iter()) {
        *target = *value as u8;
    }
    output
}

fn mount_fingerprint(fd: RawFd, device: u64) -> CustodyResult<MountFingerprint> {
    let mut raw = MaybeUninit::<libc::statfs>::uninit();
    // SAFETY: `raw` points to writable storage for one `libc::statfs`, and
    // `fd` is a retained descriptor.
    if unsafe { libc::fstatfs(fd, raw.as_mut_ptr()) } != 0 {
        return Err(custody_error(
            "MOUNT_STAT",
            "retained descriptor mount metadata could not be read",
        ));
    }
    // SAFETY: successful `fstatfs` initialized the complete structure.
    let raw = unsafe { raw.assume_init() };
    let mut fsid_bytes = [0_u8; 8];
    // SAFETY: Darwin `fsid_t` is exactly two initialized i32 values (8 bytes),
    // and the destination has the same fixed size. We copy bytes, not fields,
    // because libc intentionally keeps the fields private.
    unsafe {
        std::ptr::copy_nonoverlapping(
            (&raw.f_fsid as *const libc::fsid_t).cast::<u8>(),
            fsid_bytes.as_mut_ptr(),
            fsid_bytes.len(),
        );
    }
    Ok(MountFingerprint {
        device,
        fsid_bytes,
        fs_type: c_char_array(&raw.f_fstypename),
        mount_on: c_char_array(&raw.f_mntonname),
        mount_from: c_char_array(&raw.f_mntfromname),
        fs_type_number: raw.f_type,
        flags: raw.f_flags,
        local: raw.f_flags & libc::MNT_LOCAL as u32 != 0,
    })
}

fn require_allowed_mount(mount: &MountFingerprint) -> CustodyResult<()> {
    if !mount.local || mount.fs_type_name() != b"apfs" {
        return Err(custody_error(
            "MOUNT_POLICY",
            "the synthetic shadow accepts only a local APFS mount",
        ));
    }
    Ok(())
}

fn validated_component(value: &[u8]) -> CustodyResult<CString> {
    if value.is_empty()
        || value == b"."
        || value == b".."
        || value.len() > MAX_COMPONENT_BYTES
        || value.contains(&b'/')
    {
        return Err(custody_error(
            "PATH_COMPONENT",
            "path components must be bounded literal child names",
        ));
    }
    CString::new(value).map_err(|_| {
        custody_error(
            "PATH_COMPONENT",
            "path components may not contain a NUL byte",
        )
    })
}

fn absolute_root_components(root: &Path) -> CustodyResult<Vec<CString>> {
    let raw = root.as_os_str().as_bytes();
    if raw.first() != Some(&b'/') {
        return Err(custody_error(
            "ROOT_PATH",
            "the synthetic repository root must be absolute",
        ));
    }
    let mut output = Vec::new();
    for component in raw[1..].split(|byte| *byte == b'/') {
        if component.is_empty() || component == b"." || component == b".." {
            return Err(custody_error(
                "ROOT_PATH",
                "the synthetic repository root must use one separator and literal components",
            ));
        }
        output.push(validated_component(component)?);
        if output.len() > MAX_ABSOLUTE_COMPONENTS {
            return Err(custody_error(
                "ROOT_PATH",
                "the synthetic repository root depth is outside the frozen profile",
            ));
        }
    }
    if output.is_empty() {
        return Err(custody_error(
            "ROOT_PATH",
            "the synthetic repository root depth is outside the frozen profile",
        ));
    }
    if !output
        .last()
        .expect("non-empty root component list")
        .as_bytes()
        .starts_with(SYNTHETIC_ROOT_PREFIX)
    {
        return Err(custody_error(
            "SYNTHETIC_ROOT",
            "the disposable root name lacks the frozen synthetic prefix",
        ));
    }
    Ok(output)
}

fn relative_components(values: &[&str]) -> CustodyResult<Vec<CString>> {
    if values.is_empty() || values.len() > MAX_RELATIVE_COMPONENTS {
        return Err(custody_error(
            "RELATIVE_PATH",
            "the relative custody path depth is outside the frozen profile",
        ));
    }
    values
        .iter()
        .map(|value| validated_component(value.as_bytes()))
        .collect()
}

fn open_absolute_anchor() -> CustodyResult<OwnedFd> {
    let root = c"/";
    // SAFETY: the literal is NUL-terminated and flags request an existing
    // read-only directory without following a final symlink.
    let fd = unsafe {
        libc::open(
            root.as_ptr(),
            libc::O_RDONLY
                | libc::O_DIRECTORY
                | libc::O_NOFOLLOW
                | libc::O_CLOEXEC
                | libc::O_NONBLOCK,
        )
    };
    if fd < 0 {
        return Err(custody_error(
            "ROOT_OPEN",
            "the absolute filesystem anchor could not be retained",
        ));
    }
    // SAFETY: `fd` is newly returned and uniquely owned on this success path.
    Ok(unsafe { OwnedFd::from_raw_fd(fd) })
}

fn open_directory_at(parent_fd: RawFd, name: &CString) -> CustodyResult<OwnedFd> {
    // SAFETY: `name` is NUL-terminated and no creation mode argument is needed
    // because no creation flag is present.
    let fd = unsafe {
        libc::openat(
            parent_fd,
            name.as_ptr(),
            libc::O_RDONLY
                | libc::O_DIRECTORY
                | libc::O_NOFOLLOW
                | libc::O_CLOEXEC
                | libc::O_NONBLOCK,
        )
    };
    if fd < 0 {
        return Err(custody_error(
            "DIRECTORY_OPEN",
            "a directory component could not be retained without following links",
        ));
    }
    // SAFETY: `fd` is newly returned and uniquely owned on this success path.
    Ok(unsafe { OwnedFd::from_raw_fd(fd) })
}

fn open_file_at(parent_fd: RawFd, name: &CString) -> CustodyResult<OwnedFd> {
    // SAFETY: `name` is NUL-terminated and no creation mode argument is needed
    // because no creation flag is present. O_NONBLOCK prevents a raced FIFO or
    // device from blocking before the descriptor metadata is rejected.
    let fd = unsafe {
        libc::openat(
            parent_fd,
            name.as_ptr(),
            libc::O_RDONLY
                | libc::O_NOFOLLOW
                | libc::O_CLOEXEC
                | libc::O_NONBLOCK
                | DARWIN_O_UNIQUE,
        )
    };
    if fd < 0 {
        return Err(custody_error(
            "FILE_OPEN",
            "the synthetic file could not be retained without following links",
        ));
    }
    // SAFETY: `fd` is newly returned and uniquely owned on this success path.
    Ok(unsafe { OwnedFd::from_raw_fd(fd) })
}

fn require_directory_policy(
    snapshot: &StatSnapshot,
    effective_uid: u32,
    private_custody_directory: bool,
) -> CustodyResult<()> {
    if snapshot.file_type() != libc::S_IFDIR as u32 {
        return Err(custody_error(
            "DIRECTORY_POLICY",
            "a retained path component is not a directory",
        ));
    }
    if private_custody_directory
        && (snapshot.uid != effective_uid || snapshot.permissions() != 0o700)
    {
        return Err(custody_error(
            "DIRECTORY_POLICY",
            "synthetic custody directories must be euid-owned with exact mode 0700",
        ));
    }
    Ok(())
}

fn require_file_policy(
    snapshot: &StatSnapshot,
    effective_uid: u32,
    custody_mount: &MountFingerprint,
) -> CustodyResult<()> {
    if snapshot.file_type() != libc::S_IFREG as u32
        || snapshot.uid != effective_uid
        || snapshot.permissions() != 0o600
        || snapshot.nlink != 1
        || snapshot.size < 0
        || snapshot.size as usize > MAX_SYNTHETIC_FILE_BYTES
        || snapshot.dev != custody_mount.device
    {
        return Err(custody_error(
            "FILE_POLICY",
            "the synthetic object must be one bounded euid-owned 0600 regular file on the retained mount",
        ));
    }
    Ok(())
}

fn push_directory(
    directories: &mut Vec<RetainedDirectory>,
    fd: OwnedFd,
    parent_index: Option<usize>,
    name_from_parent: Option<CString>,
    private_custody_directory: bool,
    effective_uid: u32,
) -> CustodyResult<usize> {
    let opened = stat_fd(fd.as_raw_fd())?;
    require_directory_policy(&opened, effective_uid, private_custody_directory)?;
    let mount = mount_fingerprint(fd.as_raw_fd(), opened.dev)?;
    let index = directories.len();
    directories.push(RetainedDirectory {
        fd,
        opened,
        mount,
        parent_index,
        name_from_parent,
        private_custody_directory,
    });
    Ok(index)
}

fn validate_retained_directories(
    directories: &[RetainedDirectory],
    custody_mount: &MountFingerprint,
    effective_uid: u32,
) -> CustodyResult<()> {
    for directory in directories {
        if let (Some(parent_index), Some(name)) =
            (directory.parent_index, directory.name_from_parent.as_ref())
        {
            let named = stat_at(directories[parent_index].fd.as_raw_fd(), name)?;
            if !directory.opened.same_object(&named) {
                return Err(custody_error(
                    "DIRECTORY_NAME_REBIND",
                    "a directory name no longer identifies its retained inode",
                ));
            }
        }
    }
    for directory in directories {
        let current = stat_fd(directory.fd.as_raw_fd())?;
        require_directory_policy(&current, effective_uid, directory.private_custody_directory)?;
        let stable = if directory.private_custody_directory {
            directory.opened.stable_without_atime(&current)
        } else {
            directory.opened.same_object(&current)
        };
        if !stable {
            return Err(custody_error(
                "DIRECTORY_DRIFT",
                "a retained directory changed during synthetic capture",
            ));
        }
        let current_mount = mount_fingerprint(directory.fd.as_raw_fd(), current.dev)?;
        if current_mount != directory.mount {
            return Err(custody_error(
                "MOUNT_DRIFT",
                "a retained directory mount identity changed during capture",
            ));
        }
        if directory.private_custody_directory && &current_mount != custody_mount {
            return Err(custody_error(
                "MOUNT_POLICY",
                "a private custody directory crossed the retained root mount",
            ));
        }
    }
    Ok(())
}

fn descriptor_chain_commitment(
    directories: &[RetainedDirectory],
    file: &StatSnapshot,
    content_sha256: &[u8; 32],
) -> [u8; 32] {
    let mut digest = Sha256::new();
    digest.update((CHAIN_COMMITMENT_DOMAIN.len() as u64).to_be_bytes());
    digest.update(CHAIN_COMMITMENT_DOMAIN);
    digest.update((directories.len() as u64).to_be_bytes());
    for directory in directories {
        digest.update(directory.opened.dev.to_be_bytes());
        digest.update(directory.opened.ino.to_be_bytes());
        digest.update(directory.opened.mode.to_be_bytes());
        digest.update(directory.opened.uid.to_be_bytes());
    }
    digest.update(file.dev.to_be_bytes());
    digest.update(file.ino.to_be_bytes());
    digest.update(file.mode.to_be_bytes());
    digest.update(file.nlink.to_be_bytes());
    digest.update(file.uid.to_be_bytes());
    digest.update(file.size.to_be_bytes());
    digest.update(content_sha256);
    digest.finalize().into()
}

fn capture_synthetic_retained_descriptor_with_hook<F>(
    _permit: &SyntheticCustodyPermitV1,
    synthetic_repository_root: &Path,
    relative_path_components: &[&str],
    expected_content_sha256: [u8; 32],
    expected_content_byte_length: u64,
    after_read_hook: F,
) -> CustodyResult<SyntheticCustodyConformanceV1>
where
    F: FnOnce(),
{
    if expected_content_sha256 == [0_u8; 32]
        || expected_content_byte_length as usize > MAX_SYNTHETIC_FILE_BYTES
    {
        return Err(custody_error(
            "EXPECTED_BINDING",
            "the expected synthetic content binding is outside the frozen profile",
        ));
    }

    let root_names = absolute_root_components(synthetic_repository_root)?;
    let relative_names = relative_components(relative_path_components)?;
    let (directory_names, file_name_slice) = relative_names.split_at(relative_names.len() - 1);
    let file_name = file_name_slice
        .first()
        .expect("relative component list is non-empty");
    // SAFETY: `geteuid` has no preconditions and does not mutate process state.
    let effective_uid = unsafe { libc::geteuid() };

    let mut directories = Vec::with_capacity(root_names.len() + directory_names.len() + 1);
    let absolute_anchor = open_absolute_anchor()?;
    let mut parent_index = push_directory(
        &mut directories,
        absolute_anchor,
        None,
        None,
        false,
        effective_uid,
    )?;

    let root_name_count = root_names.len();
    for (index, name) in root_names.into_iter().enumerate() {
        let private_root = index + 1 == root_name_count;
        let fd = open_directory_at(directories[parent_index].fd.as_raw_fd(), &name)?;
        parent_index = push_directory(
            &mut directories,
            fd,
            Some(parent_index),
            Some(name),
            private_root,
            effective_uid,
        )?;
    }
    let custody_root_index = parent_index;
    let custody_mount = directories[custody_root_index].mount.clone();
    require_allowed_mount(&custody_mount)?;

    for name in directory_names {
        let fd = open_directory_at(directories[parent_index].fd.as_raw_fd(), name)?;
        let child_index = push_directory(
            &mut directories,
            fd,
            Some(parent_index),
            Some(name.clone()),
            true,
            effective_uid,
        )?;
        if directories[child_index].mount != custody_mount {
            return Err(custody_error(
                "MOUNT_POLICY",
                "a relative directory crossed the retained synthetic root mount",
            ));
        }
        parent_index = child_index;
    }

    let path_before = stat_at(directories[parent_index].fd.as_raw_fd(), file_name)?;
    require_file_policy(&path_before, effective_uid, &custody_mount)?;
    let file_fd = open_file_at(directories[parent_index].fd.as_raw_fd(), file_name)?;
    let opened = stat_fd(file_fd.as_raw_fd())?;
    require_file_policy(&opened, effective_uid, &custody_mount)?;
    if !path_before.stable_without_atime(&opened) {
        return Err(custody_error(
            "FILE_OPEN_RACE",
            "the file name changed while its descriptor was opened",
        ));
    }
    let opened_mount = mount_fingerprint(file_fd.as_raw_fd(), opened.dev)?;
    if opened_mount != custody_mount {
        return Err(custody_error(
            "MOUNT_POLICY",
            "the retained file crossed the synthetic root mount",
        ));
    }

    let mut file = File::from(file_fd);
    let mut content = Vec::with_capacity(opened.size as usize);
    file.by_ref()
        .take(MAX_SYNTHETIC_FILE_BYTES as u64 + 1)
        .read_to_end(&mut content)
        .map_err(|_| {
            custody_error(
                "FILE_READ",
                "the retained synthetic file could not be read completely",
            )
        })?;
    let content_sha256: [u8; 32] = Sha256::digest(&content).into();

    after_read_hook();

    let after = stat_fd(file.as_raw_fd())?;
    let final_named = stat_at(directories[parent_index].fd.as_raw_fd(), file_name)?;
    if !after.same_object(&final_named) {
        return Err(custody_error(
            "FILE_NAME_REBIND",
            "the final file name no longer identifies the retained inode",
        ));
    }
    require_file_policy(&after, effective_uid, &custody_mount)?;
    if !opened.stable_without_atime(&after)
        || content.len() > MAX_SYNTHETIC_FILE_BYTES
        || after.size as usize != content.len()
    {
        return Err(custody_error(
            "FILE_DRIFT",
            "the retained file changed during synthetic capture",
        ));
    }
    let after_mount = mount_fingerprint(file.as_raw_fd(), after.dev)?;
    if after_mount != opened_mount {
        return Err(custody_error(
            "MOUNT_DRIFT",
            "the retained file mount identity changed during capture",
        ));
    }

    if !after.stable_without_atime(&final_named) {
        return Err(custody_error(
            "FILE_DRIFT",
            "the final named metadata differs from the retained file",
        ));
    }
    validate_retained_directories(&directories, &custody_mount, effective_uid)?;

    if content_sha256 != expected_content_sha256
        || content.len() as u64 != expected_content_byte_length
    {
        return Err(custody_error(
            "EXPECTED_BINDING",
            "the retained synthetic bytes do not match the independent expected binding",
        ));
    }

    let chain_sha256 = descriptor_chain_commitment(&directories, &after, &content_sha256);
    Ok(SyntheticCustodyConformanceV1 {
        implementation_profile: IMPLEMENTATION_PROFILE,
        content_sha256,
        content_byte_length: content.len() as u64,
        retained_descriptor_chain_sha256: chain_sha256,
        retained_directory_descriptor_count: directories.len(),
        synthetic_disposable_tree_only: true,
        synthetic_retained_descriptor_conformance_verified: true,
        component_by_component_nofollow_verified: true,
        effective_uid_and_exact_posix_modes_verified: true,
        single_link_regular_file_verified: true,
        same_local_apfs_mount_verified: true,
        before_after_identity_stability_verified: true,
        final_name_to_inode_revalidation_verified: true,
        secure_custody_capture_verified: false,
        authenticated_envelope_composed: false,
        durable_trust_ledger_verified: false,
        trusted_time_verified: false,
        durable_replay_claim_verified: false,
        capability_minted: false,
        freeze_authority_verified: false,
        ready_for_g1_4_candidate_protocol_preregistration: false,
        runtime_authority: false,
    })
}

fn capture_synthetic_retained_descriptor(
    permit: &SyntheticCustodyPermitV1,
    synthetic_repository_root: &Path,
    relative_path_components: &[&str],
    expected_content_sha256: [u8; 32],
    expected_content_byte_length: u64,
) -> CustodyResult<SyntheticCustodyConformanceV1> {
    capture_synthetic_retained_descriptor_with_hook(
        permit,
        synthetic_repository_root,
        relative_path_components,
        expected_content_sha256,
        expected_content_byte_length,
        || {},
    )
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::fs::{self, OpenOptions};
    use std::io::Write;
    use std::os::unix::fs::{symlink, PermissionsExt};
    use std::path::{Path, PathBuf};
    use tempfile::{Builder, TempDir};

    const CONTENT: &[u8] = b"synthetic engram custody shadow bytes v0\n";

    struct SyntheticTree {
        _temp: TempDir,
        root: PathBuf,
        directory: PathBuf,
        file: PathBuf,
    }

    fn set_mode(path: &Path, mode: u32) {
        fs::set_permissions(path, fs::Permissions::from_mode(mode)).unwrap();
    }

    fn synthetic_tree() -> SyntheticTree {
        let temp = Builder::new()
            .prefix(std::str::from_utf8(SYNTHETIC_ROOT_PREFIX).unwrap())
            .tempdir_in("/private/tmp")
            .unwrap();
        let root = temp.path().to_path_buf();
        set_mode(&root, 0o700);
        let directory = root.join("sealed");
        fs::create_dir(&directory).unwrap();
        set_mode(&directory, 0o700);
        let file = directory.join("manifest.bin");
        fs::write(&file, CONTENT).unwrap();
        set_mode(&file, 0o600);
        SyntheticTree {
            _temp: temp,
            root,
            directory,
            file,
        }
    }

    fn content_digest() -> [u8; 32] {
        Sha256::digest(CONTENT).into()
    }

    fn capture(tree: &SyntheticTree) -> CustodyResult<SyntheticCustodyConformanceV1> {
        capture_synthetic_retained_descriptor(
            &synthetic_test_permit_v1(),
            &tree.root,
            &["sealed", "manifest.bin"],
            content_digest(),
            CONTENT.len() as u64,
        )
    }

    #[test]
    fn engram_g1_secure_custody_shadow_happy_path_retains_and_revalidates() {
        let tree = synthetic_tree();
        let result = capture(&tree).unwrap();
        assert_eq!(result.implementation_profile, IMPLEMENTATION_PROFILE);
        assert_eq!(result.content_sha256, content_digest());
        assert_eq!(result.content_byte_length, CONTENT.len() as u64);
        assert!(result.retained_directory_descriptor_count >= 4);
        assert_ne!(result.retained_descriptor_chain_sha256, [0_u8; 32]);
        assert!(result.synthetic_disposable_tree_only);
        assert!(result.synthetic_retained_descriptor_conformance_verified);
        assert!(result.component_by_component_nofollow_verified);
        assert!(result.effective_uid_and_exact_posix_modes_verified);
        assert!(result.single_link_regular_file_verified);
        assert!(result.same_local_apfs_mount_verified);
        assert!(result.before_after_identity_stability_verified);
        assert!(result.final_name_to_inode_revalidation_verified);
        assert!(!result.secure_custody_capture_verified);
        assert!(!result.authenticated_envelope_composed);
        assert!(!result.durable_trust_ledger_verified);
        assert!(!result.trusted_time_verified);
        assert!(!result.durable_replay_claim_verified);
        assert!(!result.capability_minted);
        assert!(!result.freeze_authority_verified);
        assert!(!result.ready_for_g1_4_candidate_protocol_preregistration);
        assert!(!result.runtime_authority);
    }

    #[test]
    fn engram_g1_secure_custody_shadow_rejects_component_escape_forms() {
        let tree = synthetic_tree();
        for components in [
            vec!["", "manifest.bin"],
            vec![".", "manifest.bin"],
            vec!["..", "manifest.bin"],
            vec!["sealed/elsewhere", "manifest.bin"],
            vec!["sealed", "bad\0name"],
        ] {
            let error = capture_synthetic_retained_descriptor(
                &synthetic_test_permit_v1(),
                &tree.root,
                &components,
                content_digest(),
                CONTENT.len() as u64,
            )
            .unwrap_err();
            assert_eq!(error.code(), "PATH_COMPONENT");
        }
        let error = capture_synthetic_retained_descriptor(
            &synthetic_test_permit_v1(),
            Path::new("relative-root"),
            &["sealed", "manifest.bin"],
            content_digest(),
            CONTENT.len() as u64,
        )
        .unwrap_err();
        assert_eq!(error.code(), "ROOT_PATH");

        for raw_root in [
            format!("{}/.", tree.root.display()),
            format!("{}//sealed-root", tree.root.display()),
            format!("{}/", tree.root.display()),
        ] {
            let error = capture_synthetic_retained_descriptor(
                &synthetic_test_permit_v1(),
                Path::new(&raw_root),
                &["sealed", "manifest.bin"],
                content_digest(),
                CONTENT.len() as u64,
            )
            .unwrap_err();
            assert_eq!(error.code(), "ROOT_PATH");
        }
    }

    #[test]
    fn engram_g1_secure_custody_shadow_rejects_directory_symlink_and_mode() {
        let tree = synthetic_tree();
        let linked = tree.root.join("linked");
        symlink(&tree.directory, &linked).unwrap();
        let error = capture_synthetic_retained_descriptor(
            &synthetic_test_permit_v1(),
            &tree.root,
            &["linked", "manifest.bin"],
            content_digest(),
            CONTENT.len() as u64,
        )
        .unwrap_err();
        assert_eq!(error.code(), "DIRECTORY_OPEN");

        set_mode(&tree.directory, 0o750);
        let error = capture(&tree).unwrap_err();
        assert_eq!(error.code(), "DIRECTORY_POLICY");
    }

    #[test]
    fn engram_g1_secure_custody_shadow_rejects_root_symlink_mode_and_non_synthetic_name() {
        let tree = synthetic_tree();
        set_mode(&tree.root, 0o750);
        let error = capture(&tree).unwrap_err();
        assert_eq!(error.code(), "DIRECTORY_POLICY");
        set_mode(&tree.root, 0o700);

        let link_parent = tempfile::tempdir_in("/private/tmp").unwrap();
        let linked_root = link_parent
            .path()
            .join("agent-bridge-engram-g1-custody-shadow-linked-root");
        symlink(&tree.root, &linked_root).unwrap();
        let error = capture_synthetic_retained_descriptor(
            &synthetic_test_permit_v1(),
            &linked_root,
            &["sealed", "manifest.bin"],
            content_digest(),
            CONTENT.len() as u64,
        )
        .unwrap_err();
        assert_eq!(error.code(), "DIRECTORY_OPEN");

        let error = capture_synthetic_retained_descriptor(
            &synthetic_test_permit_v1(),
            Path::new("/private/tmp"),
            &["sealed", "manifest.bin"],
            content_digest(),
            CONTENT.len() as u64,
        )
        .unwrap_err();
        assert_eq!(error.code(), "SYNTHETIC_ROOT");
    }

    #[test]
    fn engram_g1_secure_custody_shadow_rejects_file_symlink_nonregular_and_mode() {
        let tree = synthetic_tree();
        let alternate = tree.directory.join("alternate.bin");
        fs::write(&alternate, CONTENT).unwrap();
        set_mode(&alternate, 0o600);
        let linked = tree.directory.join("linked.bin");
        symlink(&alternate, &linked).unwrap();
        let error = capture_synthetic_retained_descriptor(
            &synthetic_test_permit_v1(),
            &tree.root,
            &["sealed", "linked.bin"],
            content_digest(),
            CONTENT.len() as u64,
        )
        .unwrap_err();
        assert_eq!(error.code(), "FILE_POLICY");

        let directory_as_file = tree.directory.join("directory.bin");
        fs::create_dir(&directory_as_file).unwrap();
        set_mode(&directory_as_file, 0o700);
        let error = capture_synthetic_retained_descriptor(
            &synthetic_test_permit_v1(),
            &tree.root,
            &["sealed", "directory.bin"],
            content_digest(),
            CONTENT.len() as u64,
        )
        .unwrap_err();
        assert_eq!(error.code(), "FILE_POLICY");

        set_mode(&tree.file, 0o640);
        let error = capture(&tree).unwrap_err();
        assert_eq!(error.code(), "FILE_POLICY");
    }

    #[test]
    fn engram_g1_secure_custody_shadow_rejects_fifo_and_oversized_file() {
        let tree = synthetic_tree();
        let fifo = tree.directory.join("fifo.bin");
        let fifo_name = CString::new(fifo.as_os_str().as_bytes()).unwrap();
        // SAFETY: `fifo_name` is a valid NUL-terminated path in this disposable
        // test tree and the requested mode grants owner access only.
        assert_eq!(unsafe { libc::mkfifo(fifo_name.as_ptr(), 0o600) }, 0);
        let error = capture_synthetic_retained_descriptor(
            &synthetic_test_permit_v1(),
            &tree.root,
            &["sealed", "fifo.bin"],
            content_digest(),
            CONTENT.len() as u64,
        )
        .unwrap_err();
        assert_eq!(error.code(), "FILE_POLICY");

        let oversized = tree.directory.join("oversized.bin");
        fs::write(&oversized, vec![b'x'; MAX_SYNTHETIC_FILE_BYTES + 1]).unwrap();
        set_mode(&oversized, 0o600);
        let error = capture_synthetic_retained_descriptor(
            &synthetic_test_permit_v1(),
            &tree.root,
            &["sealed", "oversized.bin"],
            content_digest(),
            CONTENT.len() as u64,
        )
        .unwrap_err();
        assert_eq!(error.code(), "FILE_POLICY");
    }

    #[test]
    fn engram_g1_secure_custody_shadow_rejects_hardlink_before_open() {
        let tree = synthetic_tree();
        fs::hard_link(&tree.file, tree.directory.join("alias.bin")).unwrap();
        let parent = std::fs::File::open(&tree.directory).unwrap();
        let direct_error =
            open_file_at(parent.as_raw_fd(), &CString::new("manifest.bin").unwrap()).unwrap_err();
        assert_eq!(direct_error.code(), "FILE_OPEN");
        let error = capture(&tree).unwrap_err();
        assert_eq!(error.code(), "FILE_POLICY");
    }

    #[test]
    fn engram_g1_secure_custody_shadow_rejects_final_name_swap_after_read() {
        let tree = synthetic_tree();
        let original = tree.directory.join("original.bin");
        let decoy = tree.directory.join("decoy.bin");
        fs::write(&decoy, CONTENT).unwrap();
        set_mode(&decoy, 0o600);
        let error = capture_synthetic_retained_descriptor_with_hook(
            &synthetic_test_permit_v1(),
            &tree.root,
            &["sealed", "manifest.bin"],
            content_digest(),
            CONTENT.len() as u64,
            || {
                fs::rename(&tree.file, &original).unwrap();
                fs::rename(&decoy, &tree.file).unwrap();
            },
        )
        .unwrap_err();
        assert_eq!(error.code(), "FILE_NAME_REBIND");
    }

    #[test]
    fn engram_g1_secure_custody_shadow_rejects_in_place_mutation_after_read() {
        let tree = synthetic_tree();
        let error = capture_synthetic_retained_descriptor_with_hook(
            &synthetic_test_permit_v1(),
            &tree.root,
            &["sealed", "manifest.bin"],
            content_digest(),
            CONTENT.len() as u64,
            || {
                let mut file = OpenOptions::new().append(true).open(&tree.file).unwrap();
                file.write_all(b"drift").unwrap();
                file.sync_all().unwrap();
            },
        )
        .unwrap_err();
        assert_eq!(error.code(), "FILE_DRIFT");
    }

    #[test]
    fn engram_g1_secure_custody_shadow_rejects_hardlink_created_after_read() {
        let tree = synthetic_tree();
        let error = capture_synthetic_retained_descriptor_with_hook(
            &synthetic_test_permit_v1(),
            &tree.root,
            &["sealed", "manifest.bin"],
            content_digest(),
            CONTENT.len() as u64,
            || fs::hard_link(&tree.file, tree.directory.join("late-alias.bin")).unwrap(),
        )
        .unwrap_err();
        assert_eq!(error.code(), "FILE_POLICY");
    }

    #[test]
    fn engram_g1_secure_custody_shadow_rejects_parent_name_swap_after_read() {
        let tree = synthetic_tree();
        let displaced = tree.root.join("displaced");
        let error = capture_synthetic_retained_descriptor_with_hook(
            &synthetic_test_permit_v1(),
            &tree.root,
            &["sealed", "manifest.bin"],
            content_digest(),
            CONTENT.len() as u64,
            || {
                fs::rename(&tree.directory, &displaced).unwrap();
                fs::create_dir(&tree.directory).unwrap();
                set_mode(&tree.directory, 0o700);
                let replacement = tree.directory.join("manifest.bin");
                fs::write(&replacement, CONTENT).unwrap();
                set_mode(&replacement, 0o600);
            },
        )
        .unwrap_err();
        assert_eq!(error.code(), "DIRECTORY_NAME_REBIND");
    }

    #[test]
    fn engram_g1_secure_custody_shadow_rejects_wrong_expected_binding() {
        let tree = synthetic_tree();
        let error = capture_synthetic_retained_descriptor(
            &synthetic_test_permit_v1(),
            &tree.root,
            &["sealed", "manifest.bin"],
            Sha256::digest(b"different synthetic bytes").into(),
            CONTENT.len() as u64,
        )
        .unwrap_err();
        assert_eq!(error.code(), "EXPECTED_BINDING");
    }

    #[test]
    fn engram_g1_secure_custody_shadow_mount_policy_is_local_apfs_only() {
        let mut mount = MountFingerprint {
            device: 1,
            fsid_bytes: [0_u8; 8],
            fs_type: [0_u8; 16],
            mount_on: [0_u8; 1024],
            mount_from: [0_u8; 1024],
            fs_type_number: 0,
            flags: 0,
            local: false,
        };
        mount.fs_type[..3].copy_from_slice(b"nfs");
        assert_eq!(
            require_allowed_mount(&mount).unwrap_err().code(),
            "MOUNT_POLICY"
        );
        mount.local = true;
        mount.fs_type = [0_u8; 16];
        mount.fs_type[..4].copy_from_slice(b"fuse");
        assert_eq!(
            require_allowed_mount(&mount).unwrap_err().code(),
            "MOUNT_POLICY"
        );
        mount.fs_type = [0_u8; 16];
        mount.fs_type[..4].copy_from_slice(b"apfs");
        require_allowed_mount(&mount).unwrap();
    }
}
