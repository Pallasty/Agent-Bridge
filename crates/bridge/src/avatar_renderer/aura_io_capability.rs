use std::fmt;
use std::fs;
use std::io::Read;
use std::path::Path;

use serde_json::{json, Value};

use super::{
    sha256_hex, shadow_visible_key, strip_sha256_prefix, LCC_AURA_IO_SCHEMA_VERSION,
    LCC_AURA_RENDERER_INPUT_KIND, LCC_AURA_SHADOW_SIGNAL_POLICY, LCC_AURA_UNIFORM_BYTES,
    LCC_AURA_UNIFORM_CONTRACT_VERSION, LCC_AURA_UNIFORM_ENCODING, LCC_AURA_UNIFORM_LEN,
    LCC_AURA_VISIBLE_SIGNAL_SOURCE,
};

const AURA_IO_LOGICAL_PATH_MAX_BYTES: usize = 4_096;
const AURA_IO_SIDECAR_MAX_BYTES: usize = 65_536;
const AURA_IO_UNIFORM_EXACT_BYTES: usize = 1_024;
const AURA_IO_DIGEST_MAX_BYTES: usize = 1_048_576;

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum AuraIoRole {
    Root,
    Directory,
    Sidecar,
    Uniform,
    Digest,
}

impl AuraIoRole {
    fn as_str(self) -> &'static str {
        match self {
            Self::Root => "root",
            Self::Directory => "directory",
            Self::Sidecar => "sidecar",
            Self::Uniform => "uniform",
            Self::Digest => "digest",
        }
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum AuraIoFailureReason {
    NotAbsolute,
    NotRelative,
    Empty,
    DotComponent,
    ParentComponent,
    InvalidComponent,
    PathTooLong,
    NotDirectory,
    NotRegular,
    MultipleLinks,
    CrossDevice,
    Symlink,
    WrongOwner,
    WritableByUntrustedPrincipal,
    UnsupportedFilesystem,
    UnsupportedPlatform,
    Permission,
    StaleHandle,
    SafeOpen,
    Oversize,
    WrongSize,
    Parse,
    Schema,
    HashMismatch,
    Io,
}

impl AuraIoFailureReason {
    fn as_str(self) -> &'static str {
        match self {
            Self::NotAbsolute => "not_absolute",
            Self::NotRelative => "not_relative",
            Self::Empty => "empty",
            Self::DotComponent => "dot_component",
            Self::ParentComponent => "parent_component",
            Self::InvalidComponent => "invalid_component",
            Self::PathTooLong => "path_too_long",
            Self::NotDirectory => "not_directory",
            Self::NotRegular => "not_regular",
            Self::MultipleLinks => "multiple_links",
            Self::CrossDevice => "cross_device",
            Self::Symlink => "symlink",
            Self::WrongOwner => "wrong_owner",
            Self::WritableByUntrustedPrincipal => "untrusted_writable",
            Self::UnsupportedFilesystem => "unsupported_filesystem",
            Self::UnsupportedPlatform => "unsupported_platform",
            Self::Permission => "permission",
            Self::StaleHandle => "stale_handle",
            Self::SafeOpen => "safe_open",
            Self::Oversize => "oversize",
            Self::WrongSize => "wrong_size",
            Self::Parse => "parse",
            Self::Schema => "schema",
            Self::HashMismatch => "hash_mismatch",
            Self::Io => "io",
        }
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct AuraIoReadError {
    role: AuraIoRole,
    reason: AuraIoFailureReason,
}

impl AuraIoReadError {
    fn new(role: AuraIoRole, reason: AuraIoFailureReason) -> Self {
        Self { role, reason }
    }

    pub fn role(&self) -> AuraIoRole {
        self.role
    }

    pub fn reason(&self) -> AuraIoFailureReason {
        self.reason
    }

    pub fn code(&self) -> String {
        format!("aura_io_{}_{}", self.role.as_str(), self.reason.as_str())
    }
}

impl fmt::Display for AuraIoReadError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        f.write_str(&self.code())
    }
}

impl std::error::Error for AuraIoReadError {}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct RelativeAuraPath {
    components: Vec<String>,
}

#[derive(Debug, Clone, Copy)]
struct AuraIoLimits {
    logical_path_bytes: usize,
    sidecar_bytes: usize,
    uniform_bytes: usize,
    digest_bytes: usize,
}

impl Default for AuraIoLimits {
    fn default() -> Self {
        Self {
            logical_path_bytes: AURA_IO_LOGICAL_PATH_MAX_BYTES,
            sidecar_bytes: AURA_IO_SIDECAR_MAX_BYTES,
            uniform_bytes: AURA_IO_UNIFORM_EXACT_BYTES,
            digest_bytes: AURA_IO_DIGEST_MAX_BYTES,
        }
    }
}

#[derive(Debug)]
struct OpaqueDirectoryHandle {
    #[cfg(target_os = "linux")]
    fd: rustix::fd::OwnedFd,
    #[cfg(target_os = "linux")]
    device: u64,
    #[cfg(target_os = "linux")]
    filesystem_magic: u64,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct SanitizedAuraIoReport {
    uniform_sha256: String,
    digest_sha256: String,
    digest_item_count: u64,
}

impl SanitizedAuraIoReport {
    pub fn to_json_value(&self) -> Value {
        json!({
            "surface": "lcc_aura_io_intake",
            "schema": 1,
            "ok": true,
            "schema_version": LCC_AURA_IO_SCHEMA_VERSION,
            "renderer_input_kind": LCC_AURA_RENDERER_INPUT_KIND,
            "uniform_contract_version": LCC_AURA_UNIFORM_CONTRACT_VERSION,
            "uniform_len": LCC_AURA_UNIFORM_LEN,
            "bin_bytes": LCC_AURA_UNIFORM_BYTES,
            "uniform_sha256": self.uniform_sha256,
            "digest_sha256": self.digest_sha256,
            "digest_item_count": self.digest_item_count,
            "visible_signal_source": LCC_AURA_VISIBLE_SIGNAL_SOURCE,
            "shadow_signal_policy": LCC_AURA_SHADOW_SIGNAL_POLICY,
            "uniform_file_sha256_matches": true,
            "digest_file_sha256_matches": true,
            "safety": {
                "read_only": true,
                "writes_files": false,
                "mutates_renderer": false,
                "emits_audio": false,
                "controls_desktop": false,
                "shadow_visible_state": false,
                "retained_directory_capability": true,
                "request_time_file_io": false,
            }
        })
    }
}

#[derive(Debug)]
pub struct AuraIoReadCapability {
    root: OpaqueDirectoryHandle,
    limits: AuraIoLimits,
}

impl AuraIoReadCapability {
    pub fn open(root: &Path) -> std::result::Result<Self, AuraIoReadError> {
        if !root.is_absolute() {
            return Err(AuraIoReadError::new(
                AuraIoRole::Root,
                AuraIoFailureReason::NotAbsolute,
            ));
        }
        open_aura_io_root(root).map(|root| Self {
            root,
            limits: AuraIoLimits::default(),
        })
    }

    pub fn parse_entry(
        &self,
        raw: &Path,
    ) -> std::result::Result<RelativeAuraPath, AuraIoReadError> {
        let _ = &self.root;
        parse_aura_io_logical_path(raw, AuraIoRole::Sidecar, self.limits.logical_path_bytes)
    }

    pub fn load_snapshot(
        &self,
        logical_sidecar: &RelativeAuraPath,
    ) -> std::result::Result<SanitizedAuraIoReport, AuraIoReadError> {
        load_aura_io_snapshot(&self.root, &self.limits, logical_sidecar)
    }
}

fn parse_aura_io_logical_path(
    raw: &Path,
    role: AuraIoRole,
    max_bytes: usize,
) -> std::result::Result<RelativeAuraPath, AuraIoReadError> {
    if raw.is_absolute() {
        return Err(AuraIoReadError::new(role, AuraIoFailureReason::NotRelative));
    }
    let text = raw
        .to_str()
        .ok_or_else(|| AuraIoReadError::new(role, AuraIoFailureReason::InvalidComponent))?;
    if text.is_empty() {
        return Err(AuraIoReadError::new(role, AuraIoFailureReason::Empty));
    }
    if text.len() > max_bytes {
        return Err(AuraIoReadError::new(role, AuraIoFailureReason::PathTooLong));
    }

    let mut components = Vec::new();
    for component in text.split('/') {
        let reason = match component {
            "" => Some(AuraIoFailureReason::InvalidComponent),
            "." => Some(AuraIoFailureReason::DotComponent),
            ".." => Some(AuraIoFailureReason::ParentComponent),
            _ if component.as_bytes().contains(&0) => Some(AuraIoFailureReason::InvalidComponent),
            _ => None,
        };
        if let Some(reason) = reason {
            return Err(AuraIoReadError::new(role, reason));
        }
        components.push(component.to_owned());
    }
    Ok(RelativeAuraPath { components })
}

#[cfg(target_os = "linux")]
fn open_aura_io_root(root: &Path) -> std::result::Result<OpaqueDirectoryHandle, AuraIoReadError> {
    use rustix::fs::{fstat, fstatfs, openat2, Mode, OFlags, ResolveFlags, CWD};
    use rustix::io::{fcntl_getfd, FdFlags};

    let role = AuraIoRole::Root;
    let fd = openat2(
        CWD,
        root,
        OFlags::RDONLY | OFlags::DIRECTORY | OFlags::NOFOLLOW | OFlags::CLOEXEC,
        Mode::empty(),
        ResolveFlags::NO_MAGICLINKS | ResolveFlags::NO_SYMLINKS,
    )
    .map_err(|error| map_aura_io_os_error(role, error))?;
    let stat = fstat(&fd).map_err(|error| map_aura_io_os_error(role, error))?;
    if stat.st_mode & libc::S_IFMT != libc::S_IFDIR {
        return Err(AuraIoReadError::new(
            role,
            AuraIoFailureReason::NotDirectory,
        ));
    }
    if stat.st_uid != rustix::process::geteuid().as_raw() {
        return Err(AuraIoReadError::new(role, AuraIoFailureReason::WrongOwner));
    }
    if stat.st_mode & 0o022 != 0 {
        return Err(AuraIoReadError::new(
            role,
            AuraIoFailureReason::WritableByUntrustedPrincipal,
        ));
    }
    let filesystem = fstatfs(&fd).map_err(|error| map_aura_io_os_error(role, error))?;
    if !aura_io_filesystem_allowed(filesystem.f_type as u64) {
        return Err(AuraIoReadError::new(
            role,
            AuraIoFailureReason::UnsupportedFilesystem,
        ));
    }
    let fd_flags = fcntl_getfd(&fd).map_err(|error| map_aura_io_os_error(role, error))?;
    if !fd_flags.contains(FdFlags::CLOEXEC) {
        return Err(AuraIoReadError::new(role, AuraIoFailureReason::SafeOpen));
    }
    Ok(OpaqueDirectoryHandle {
        fd,
        device: stat.st_dev,
        filesystem_magic: filesystem.f_type as u64,
    })
}

#[cfg(not(target_os = "linux"))]
fn open_aura_io_root(_root: &Path) -> std::result::Result<OpaqueDirectoryHandle, AuraIoReadError> {
    Err(AuraIoReadError::new(
        AuraIoRole::Root,
        AuraIoFailureReason::UnsupportedPlatform,
    ))
}

#[cfg(target_os = "linux")]
fn map_aura_io_os_error(role: AuraIoRole, error: rustix::io::Errno) -> AuraIoReadError {
    use rustix::io::Errno;

    let reason = match error {
        Errno::ACCESS | Errno::PERM => AuraIoFailureReason::Permission,
        Errno::STALE => AuraIoFailureReason::StaleHandle,
        Errno::LOOP => AuraIoFailureReason::Symlink,
        Errno::XDEV => AuraIoFailureReason::CrossDevice,
        Errno::NOSYS | Errno::INVAL | Errno::NOTDIR => AuraIoFailureReason::SafeOpen,
        _ => AuraIoFailureReason::Io,
    };
    AuraIoReadError::new(role, reason)
}

#[cfg(target_os = "linux")]
fn load_aura_io_snapshot(
    root: &OpaqueDirectoryHandle,
    limits: &AuraIoLimits,
    logical_sidecar: &RelativeAuraPath,
) -> std::result::Result<SanitizedAuraIoReport, AuraIoReadError> {
    verify_aura_io_directory(
        &root.fd,
        root.device,
        root.filesystem_magic,
        AuraIoRole::Root,
    )?;

    let sidecar = open_aura_io_regular_file(root, logical_sidecar, AuraIoRole::Sidecar)?;
    let sidecar_bytes = read_aura_io_bounded(
        sidecar.file,
        sidecar.metadata_size,
        AuraIoRole::Sidecar,
        AuraIoReadBound::Maximum(limits.sidecar_bytes),
    )?;
    let manifest: Value = serde_json::from_slice(&sidecar_bytes)
        .map_err(|_| AuraIoReadError::new(AuraIoRole::Sidecar, AuraIoFailureReason::Parse))?;
    let manifest_fields = parse_aura_io_manifest_fields(&manifest)?;

    let uniform_relative = parse_aura_io_logical_path(
        Path::new(manifest_fields.uniform_path),
        AuraIoRole::Uniform,
        limits.logical_path_bytes,
    )?;
    let digest_relative = parse_aura_io_logical_path(
        Path::new(manifest_fields.digest_path),
        AuraIoRole::Digest,
        limits.logical_path_bytes,
    )?;
    let sidecar_parent = &logical_sidecar.components[..logical_sidecar.components.len() - 1];
    let uniform_path = relative_aura_path_beneath(sidecar_parent, uniform_relative);
    let digest_path = relative_aura_path_beneath(sidecar_parent, digest_relative);

    let uniform = open_aura_io_regular_file(root, &uniform_path, AuraIoRole::Uniform)?;
    let uniform_bytes = read_aura_io_bounded(
        uniform.file,
        uniform.metadata_size,
        AuraIoRole::Uniform,
        AuraIoReadBound::Exact(limits.uniform_bytes),
    )?;
    let digest = open_aura_io_regular_file(root, &digest_path, AuraIoRole::Digest)?;
    let digest_bytes = read_aura_io_bounded(
        digest.file,
        digest.metadata_size,
        AuraIoRole::Digest,
        AuraIoReadBound::Maximum(limits.digest_bytes),
    )?;

    let uniform_sha256 = sha256_hex(&uniform_bytes);
    if uniform_sha256 != strip_sha256_prefix(manifest_fields.uniform_sha256) {
        return Err(AuraIoReadError::new(
            AuraIoRole::Uniform,
            AuraIoFailureReason::HashMismatch,
        ));
    }
    let digest_sha256 = sha256_hex(&digest_bytes);
    if digest_sha256 != strip_sha256_prefix(manifest_fields.digest_sha256) {
        return Err(AuraIoReadError::new(
            AuraIoRole::Digest,
            AuraIoFailureReason::HashMismatch,
        ));
    }

    Ok(SanitizedAuraIoReport {
        uniform_sha256,
        digest_sha256,
        digest_item_count: manifest_fields.digest_item_count,
    })
}

#[cfg(not(target_os = "linux"))]
fn load_aura_io_snapshot(
    _root: &OpaqueDirectoryHandle,
    _limits: &AuraIoLimits,
    _logical_sidecar: &RelativeAuraPath,
) -> std::result::Result<SanitizedAuraIoReport, AuraIoReadError> {
    Err(AuraIoReadError::new(
        AuraIoRole::Root,
        AuraIoFailureReason::UnsupportedPlatform,
    ))
}

fn relative_aura_path_beneath(parent: &[String], child: RelativeAuraPath) -> RelativeAuraPath {
    let mut components = Vec::with_capacity(parent.len() + child.components.len());
    components.extend(parent.iter().cloned());
    components.extend(child.components);
    RelativeAuraPath { components }
}

struct AuraIoManifestFields<'a> {
    uniform_path: &'a str,
    uniform_sha256: &'a str,
    digest_path: &'a str,
    digest_sha256: &'a str,
    digest_item_count: u64,
}

fn parse_aura_io_manifest_fields(
    manifest: &Value,
) -> std::result::Result<AuraIoManifestFields<'_>, AuraIoReadError> {
    let schema_error = || AuraIoReadError::new(AuraIoRole::Sidecar, AuraIoFailureReason::Schema);
    if manifest.get("schema_version").and_then(Value::as_str) != Some(LCC_AURA_IO_SCHEMA_VERSION) {
        return Err(schema_error());
    }
    let renderer_input = manifest
        .get("renderer_input")
        .and_then(Value::as_object)
        .ok_or_else(schema_error)?;
    let source_digest = manifest
        .get("source_digest")
        .and_then(Value::as_object)
        .ok_or_else(schema_error)?;
    let source_state = manifest
        .get("source_state")
        .filter(|value| value.is_object())
        .ok_or_else(schema_error)?;

    let exact_renderer_contract = renderer_input.get("kind").and_then(Value::as_str)
        == Some(LCC_AURA_RENDERER_INPUT_KIND)
        && renderer_input
            .get("contract_version")
            .and_then(Value::as_u64)
            == Some(LCC_AURA_UNIFORM_CONTRACT_VERSION)
        && renderer_input.get("uniform_len").and_then(Value::as_u64) == Some(LCC_AURA_UNIFORM_LEN)
        && renderer_input.get("bin_bytes").and_then(Value::as_u64) == Some(LCC_AURA_UNIFORM_BYTES)
        && renderer_input.get("encoding").and_then(Value::as_str)
            == Some(LCC_AURA_UNIFORM_ENCODING);
    if !exact_renderer_contract
        || manifest
            .get("visible_signal_source")
            .and_then(Value::as_str)
            != Some(LCC_AURA_VISIBLE_SIGNAL_SOURCE)
        || manifest.get("shadow_signal_policy").and_then(Value::as_str)
            != Some(LCC_AURA_SHADOW_SIGNAL_POLICY)
        || shadow_visible_key(source_state).is_some()
    {
        return Err(schema_error());
    }

    let uniform_path = renderer_input
        .get("path")
        .and_then(Value::as_str)
        .ok_or_else(schema_error)?;
    let uniform_sha256 = renderer_input
        .get("sha256")
        .and_then(Value::as_str)
        .filter(|value| !value.is_empty())
        .ok_or_else(schema_error)?;
    let digest_path = source_digest
        .get("json_path")
        .and_then(Value::as_str)
        .ok_or_else(schema_error)?;
    let digest_sha256 = source_digest
        .get("json_sha256")
        .and_then(Value::as_str)
        .filter(|value| !value.is_empty())
        .ok_or_else(schema_error)?;
    let digest_item_count = source_digest
        .get("item_count")
        .and_then(Value::as_u64)
        .ok_or_else(schema_error)?;

    Ok(AuraIoManifestFields {
        uniform_path,
        uniform_sha256,
        digest_path,
        digest_sha256,
        digest_item_count,
    })
}

#[cfg(target_os = "linux")]
struct OpenedAuraIoFile {
    file: fs::File,
    metadata_size: i64,
}

#[cfg(target_os = "linux")]
fn open_aura_io_regular_file(
    root: &OpaqueDirectoryHandle,
    logical_path: &RelativeAuraPath,
    role: AuraIoRole,
) -> std::result::Result<OpenedAuraIoFile, AuraIoReadError> {
    use rustix::fs::{fstat, openat2, Mode, OFlags, ResolveFlags};
    use rustix::io::fcntl_dupfd_cloexec;

    let resolve = ResolveFlags::BENEATH
        | ResolveFlags::NO_MAGICLINKS
        | ResolveFlags::NO_SYMLINKS
        | ResolveFlags::NO_XDEV;
    let mut directory = fcntl_dupfd_cloexec(&root.fd, 0)
        .map_err(|error| map_aura_io_os_error(AuraIoRole::Root, error))?;
    verify_aura_io_directory(
        &directory,
        root.device,
        root.filesystem_magic,
        AuraIoRole::Root,
    )?;

    let (file_name, parent_components) = logical_path
        .components
        .split_last()
        .ok_or_else(|| AuraIoReadError::new(role, AuraIoFailureReason::Empty))?;
    for component in parent_components {
        let next = openat2(
            &directory,
            component.as_str(),
            OFlags::RDONLY | OFlags::DIRECTORY | OFlags::NOFOLLOW | OFlags::CLOEXEC,
            Mode::empty(),
            resolve,
        )
        .map_err(|error| map_aura_io_os_error(AuraIoRole::Directory, error))?;
        verify_aura_io_directory(
            &next,
            root.device,
            root.filesystem_magic,
            AuraIoRole::Directory,
        )?;
        directory = next;
    }

    let fd = openat2(
        &directory,
        file_name.as_str(),
        OFlags::RDONLY | OFlags::NONBLOCK | OFlags::NOFOLLOW | OFlags::CLOEXEC,
        Mode::empty(),
        resolve,
    )
    .map_err(|error| map_aura_io_os_error(role, error))?;
    let stat = fstat(&fd).map_err(|error| map_aura_io_os_error(role, error))?;
    verify_aura_io_regular_stat(&fd, &stat, root.device, root.filesystem_magic, role)?;
    Ok(OpenedAuraIoFile {
        file: fs::File::from(fd),
        metadata_size: stat.st_size,
    })
}

#[cfg(target_os = "linux")]
fn verify_aura_io_directory<Fd: rustix::fd::AsFd>(
    fd: Fd,
    root_device: u64,
    root_filesystem_magic: u64,
    role: AuraIoRole,
) -> std::result::Result<(), AuraIoReadError> {
    let stat = rustix::fs::fstat(&fd).map_err(|error| map_aura_io_os_error(role, error))?;
    if stat.st_mode & libc::S_IFMT != libc::S_IFDIR {
        return Err(AuraIoReadError::new(
            role,
            AuraIoFailureReason::NotDirectory,
        ));
    }
    verify_aura_io_common_stat(fd, &stat, root_device, root_filesystem_magic, role)
}

#[cfg(target_os = "linux")]
fn verify_aura_io_regular_stat<Fd: rustix::fd::AsFd>(
    fd: Fd,
    stat: &rustix::fs::Stat,
    root_device: u64,
    root_filesystem_magic: u64,
    role: AuraIoRole,
) -> std::result::Result<(), AuraIoReadError> {
    if stat.st_mode & libc::S_IFMT != libc::S_IFREG {
        return Err(AuraIoReadError::new(role, AuraIoFailureReason::NotRegular));
    }
    if stat.st_nlink != 1 {
        return Err(AuraIoReadError::new(
            role,
            AuraIoFailureReason::MultipleLinks,
        ));
    }
    verify_aura_io_common_stat(fd, stat, root_device, root_filesystem_magic, role)
}

#[cfg(target_os = "linux")]
fn verify_aura_io_common_stat<Fd: rustix::fd::AsFd>(
    fd: Fd,
    stat: &rustix::fs::Stat,
    root_device: u64,
    root_filesystem_magic: u64,
    role: AuraIoRole,
) -> std::result::Result<(), AuraIoReadError> {
    use rustix::io::{fcntl_getfd, FdFlags};

    let filesystem = rustix::fs::fstatfs(&fd).map_err(|error| map_aura_io_os_error(role, error))?;
    let flags = fcntl_getfd(&fd).map_err(|error| map_aura_io_os_error(role, error))?;
    validate_aura_io_common_metadata(
        AuraIoCommonMetadata {
            device: stat.st_dev,
            filesystem_magic: filesystem.f_type as u64,
            uid: stat.st_uid,
            mode: stat.st_mode,
            cloexec: flags.contains(FdFlags::CLOEXEC),
        },
        root_device,
        root_filesystem_magic,
        rustix::process::geteuid().as_raw(),
        role,
    )
}

#[cfg(target_os = "linux")]
#[derive(Debug, Clone, Copy)]
struct AuraIoCommonMetadata {
    device: u64,
    filesystem_magic: u64,
    uid: u32,
    mode: u32,
    cloexec: bool,
}

#[cfg(target_os = "linux")]
fn validate_aura_io_common_metadata(
    metadata: AuraIoCommonMetadata,
    root_device: u64,
    root_filesystem_magic: u64,
    effective_uid: u32,
    role: AuraIoRole,
) -> std::result::Result<(), AuraIoReadError> {
    if metadata.device != root_device || metadata.filesystem_magic != root_filesystem_magic {
        return Err(AuraIoReadError::new(role, AuraIoFailureReason::CrossDevice));
    }
    if !aura_io_filesystem_allowed(metadata.filesystem_magic) {
        return Err(AuraIoReadError::new(
            role,
            AuraIoFailureReason::UnsupportedFilesystem,
        ));
    }
    if metadata.uid != effective_uid {
        return Err(AuraIoReadError::new(role, AuraIoFailureReason::WrongOwner));
    }
    if metadata.mode & 0o022 != 0 {
        return Err(AuraIoReadError::new(
            role,
            AuraIoFailureReason::WritableByUntrustedPrincipal,
        ));
    }
    if !metadata.cloexec {
        return Err(AuraIoReadError::new(role, AuraIoFailureReason::SafeOpen));
    }
    Ok(())
}

#[derive(Debug, Clone, Copy)]
enum AuraIoReadBound {
    Maximum(usize),
    Exact(usize),
}

fn read_aura_io_bounded<R: Read>(
    reader: R,
    metadata_size: i64,
    role: AuraIoRole,
    bound: AuraIoReadBound,
) -> std::result::Result<Vec<u8>, AuraIoReadError> {
    let limit = match bound {
        AuraIoReadBound::Maximum(limit) => {
            if metadata_size < 0 || metadata_size as u64 > limit as u64 {
                return Err(AuraIoReadError::new(role, AuraIoFailureReason::Oversize));
            }
            limit
        }
        AuraIoReadBound::Exact(exact) => {
            if metadata_size < 0 || metadata_size as u64 != exact as u64 {
                return Err(AuraIoReadError::new(role, AuraIoFailureReason::WrongSize));
            }
            exact
        }
    };
    let mut bytes = Vec::with_capacity(limit.saturating_add(1));
    reader
        .take(limit.saturating_add(1) as u64)
        .read_to_end(&mut bytes)
        .map_err(|_| AuraIoReadError::new(role, AuraIoFailureReason::Io))?;
    match bound {
        AuraIoReadBound::Maximum(_) if bytes.len() > limit => {
            Err(AuraIoReadError::new(role, AuraIoFailureReason::Oversize))
        }
        AuraIoReadBound::Exact(_) if bytes.len() != limit => {
            Err(AuraIoReadError::new(role, AuraIoFailureReason::WrongSize))
        }
        _ => Ok(bytes),
    }
}

#[cfg(target_os = "linux")]
fn aura_io_filesystem_allowed(magic: u64) -> bool {
    const EXT_SUPER_MAGIC: u64 = 0x0000_EF53;
    const TMPFS_MAGIC: u64 = 0x0102_1994;
    const XFS_SUPER_MAGIC: u64 = 0x5846_5342;
    const BTRFS_SUPER_MAGIC: u64 = 0x9123_683E;
    const OVERLAYFS_SUPER_MAGIC: u64 = 0x794C_7630;

    matches!(
        magic,
        EXT_SUPER_MAGIC | TMPFS_MAGIC | XFS_SUPER_MAGIC | BTRFS_SUPER_MAGIC | OVERLAYFS_SUPER_MAGIC
    )
}

#[cfg(all(test, target_os = "linux"))]
mod aura_io_capability_tests {
    use super::*;
    use std::io::Cursor;
    use std::os::unix::fs::PermissionsExt;

    const TMPFS_MAGIC: u64 = 0x0102_1994;

    fn valid_metadata() -> AuraIoCommonMetadata {
        AuraIoCommonMetadata {
            device: 7,
            filesystem_magic: TMPFS_MAGIC,
            uid: 1_000,
            mode: libc::S_IFREG | 0o600,
            cloexec: true,
        }
    }

    #[test]
    fn metadata_policy_rejects_cross_device_wrong_owner_permissions_and_missing_cloexec() {
        let cases = [
            (
                AuraIoCommonMetadata {
                    device: 8,
                    ..valid_metadata()
                },
                AuraIoFailureReason::CrossDevice,
            ),
            (
                AuraIoCommonMetadata {
                    filesystem_magic: 0x0000_EF53,
                    ..valid_metadata()
                },
                AuraIoFailureReason::CrossDevice,
            ),
            (
                AuraIoCommonMetadata {
                    uid: 1_001,
                    ..valid_metadata()
                },
                AuraIoFailureReason::WrongOwner,
            ),
            (
                AuraIoCommonMetadata {
                    mode: libc::S_IFREG | 0o620,
                    ..valid_metadata()
                },
                AuraIoFailureReason::WritableByUntrustedPrincipal,
            ),
            (
                AuraIoCommonMetadata {
                    mode: libc::S_IFREG | 0o602,
                    ..valid_metadata()
                },
                AuraIoFailureReason::WritableByUntrustedPrincipal,
            ),
            (
                AuraIoCommonMetadata {
                    cloexec: false,
                    ..valid_metadata()
                },
                AuraIoFailureReason::SafeOpen,
            ),
        ];
        for role in [
            AuraIoRole::Root,
            AuraIoRole::Directory,
            AuraIoRole::Sidecar,
            AuraIoRole::Uniform,
            AuraIoRole::Digest,
        ] {
            for (metadata, expected) in cases {
                let error = validate_aura_io_common_metadata(metadata, 7, TMPFS_MAGIC, 1_000, role)
                    .unwrap_err();
                assert_eq!(error.role(), role);
                assert_eq!(error.reason(), expected);
            }
        }
    }

    #[test]
    fn filesystem_classifier_rejects_network_fuse_and_unknown_magic() {
        const NFS_SUPER_MAGIC: u64 = 0x0000_6969;
        const FUSE_SUPER_MAGIC: u64 = 0x6573_5546;

        assert!(aura_io_filesystem_allowed(TMPFS_MAGIC));
        assert!(aura_io_filesystem_allowed(0x0000_EF53));
        assert!(!aura_io_filesystem_allowed(NFS_SUPER_MAGIC));
        assert!(!aura_io_filesystem_allowed(FUSE_SUPER_MAGIC));
        assert!(!aura_io_filesystem_allowed(0xDEAD_BEEF));

        for magic in [NFS_SUPER_MAGIC, FUSE_SUPER_MAGIC, 0xDEAD_BEEF] {
            let error = validate_aura_io_common_metadata(
                AuraIoCommonMetadata {
                    filesystem_magic: magic,
                    ..valid_metadata()
                },
                7,
                magic,
                1_000,
                AuraIoRole::Digest,
            )
            .unwrap_err();
            assert_eq!(error.reason(), AuraIoFailureReason::UnsupportedFilesystem);
        }
    }

    #[test]
    fn safe_open_errno_mapping_is_typed_and_redacted() {
        use rustix::io::Errno;

        let cases = [
            (Errno::ACCESS, AuraIoFailureReason::Permission),
            (Errno::PERM, AuraIoFailureReason::Permission),
            (Errno::STALE, AuraIoFailureReason::StaleHandle),
            (Errno::NOSYS, AuraIoFailureReason::SafeOpen),
            (Errno::INVAL, AuraIoFailureReason::SafeOpen),
            (Errno::NOTDIR, AuraIoFailureReason::SafeOpen),
            (Errno::LOOP, AuraIoFailureReason::Symlink),
            (Errno::XDEV, AuraIoFailureReason::CrossDevice),
            (Errno::NOENT, AuraIoFailureReason::Io),
        ];
        for (errno, expected) in cases {
            let error = map_aura_io_os_error(AuraIoRole::Sidecar, errno);
            assert_eq!(error.reason(), expected);
            assert_eq!(error.to_string(), error.code());
        }
    }

    #[test]
    fn bounded_reader_rejects_metadata_then_growth_at_ceiling_plus_one() {
        let maximum_error = read_aura_io_bounded(
            Cursor::new(vec![1_u8, 2, 3]),
            2,
            AuraIoRole::Digest,
            AuraIoReadBound::Maximum(2),
        )
        .unwrap_err();
        assert_eq!(maximum_error.reason(), AuraIoFailureReason::Oversize);

        let exact_error = read_aura_io_bounded(
            Cursor::new(vec![1_u8, 2, 3]),
            2,
            AuraIoRole::Uniform,
            AuraIoReadBound::Exact(2),
        )
        .unwrap_err();
        assert_eq!(exact_error.reason(), AuraIoFailureReason::WrongSize);
    }

    #[test]
    fn retained_root_handle_is_close_on_exec() {
        use rustix::io::{fcntl_getfd, FdFlags};

        let directory = tempfile::tempdir().expect("tempdir");
        fs::set_permissions(directory.path(), fs::Permissions::from_mode(0o700))
            .expect("trusted permissions");
        let capability = AuraIoReadCapability::open(directory.path()).expect("open capability");
        let flags = fcntl_getfd(&capability.root.fd).expect("fd flags");
        assert!(flags.contains(FdFlags::CLOEXEC));
    }
}
