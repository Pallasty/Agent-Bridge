//! Strict Unix client for the non-authoritative guardian candidate protocol.

use std::io;
use std::os::unix::fs::{FileTypeExt, MetadataExt};
use std::path::{Component, Path, PathBuf};
use std::time::Duration;

use ring::rand::{SecureRandom, SystemRandom};
use tokio::io::{AsyncReadExt, AsyncWriteExt};
use tokio::net::UnixStream;

use crate::invocation_guardian_protocol::{
    decode_response_body, encode_request, session_nonce, CommitReceipt, ExactOperation, FixedValue,
    GuardianRequest, GuardianResponse, OutcomeKind, ProtocolError, WitnessClass,
    MAX_FRAME_BODY_BYTES,
};

const IO_TIMEOUT: Duration = Duration::from_secs(10);
const GUARDIAN_SOCKET_MODE: u32 = 0o660;

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct GuardianClientConfig {
    pub socket_path: PathBuf,
    pub expected_guardian_uid: u32,
    pub expected_guardian_gid: u32,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct ExactLookup {
    pub operation_id: FixedValue,
    pub scope_commitment: FixedValue,
    pub expected_previous_head: FixedValue,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct VolatileLabObservation {
    pub kind: OutcomeKind,
    pub receipt: Option<CommitReceipt>,
}

impl VolatileLabObservation {
    pub const fn grants_authority(&self) -> bool {
        false
    }

    pub const fn witness_class(&self) -> WitnessClass {
        WitnessClass::VolatileLab
    }
}

#[derive(Debug, thiserror::Error)]
pub enum GuardianClientError {
    #[error("invalid guardian client configuration: {0}")]
    InvalidConfiguration(&'static str),
    #[error("guardian socket trust check failed: {0}")]
    UntrustedSocket(&'static str),
    #[error("guardian peer credential unavailable")]
    PeerCredentialUnavailable,
    #[error("guardian peer uid {actual} did not match configured uid {expected}")]
    WrongPeerUid { expected: u32, actual: u32 },
    #[error("guardian socket identity changed during connect")]
    SocketIdentityChanged,
    #[error("guardian protocol rejected: {0}")]
    Protocol(#[from] ProtocolError),
    #[error("guardian I/O failed: {0}")]
    Io(#[from] io::Error),
}

#[derive(Debug)]
pub struct GuardianClient {
    stream: UnixStream,
    session_nonce: FixedValue,
    provider_incarnation: FixedValue,
}

impl GuardianClient {
    /// Connects only to a non-root, different-UID guardian through a protected
    /// absolute path. Protocol v1 observations remain lab-only and cannot
    /// grant production authority.
    pub async fn connect(config: GuardianClientConfig) -> Result<Self, GuardianClientError> {
        let client_uid = effective_uid();
        if client_uid == 0 {
            return Err(GuardianClientError::InvalidConfiguration(
                "root client uid is forbidden",
            ));
        }
        if config.expected_guardian_uid == 0 {
            return Err(GuardianClientError::InvalidConfiguration(
                "root guardian uid is forbidden",
            ));
        }
        if config.expected_guardian_uid == client_uid {
            return Err(GuardianClientError::InvalidConfiguration(
                "guardian uid must differ from client uid",
            ));
        }
        if config.expected_guardian_gid == 0 {
            return Err(GuardianClientError::InvalidConfiguration(
                "root guardian group is forbidden",
            ));
        }
        validate_normalized_absolute(&config.socket_path)?;
        let before = inspect_socket_path(
            &config.socket_path,
            config.expected_guardian_uid,
            config.expected_guardian_gid,
        )?;
        let stream = UnixStream::connect(&config.socket_path).await?;
        validate_peer_uid(
            stream.peer_cred().map(|credential| credential.uid()),
            config.expected_guardian_uid,
        )?;
        let after = inspect_socket_path(
            &config.socket_path,
            config.expected_guardian_uid,
            config.expected_guardian_gid,
        )?;
        if before != after {
            return Err(GuardianClientError::SocketIdentityChanged);
        }
        Self::handshake(stream).await
    }

    pub fn provider_incarnation(&self) -> FixedValue {
        self.provider_incarnation
    }

    pub async fn consume_exact(
        &mut self,
        lookup: ExactLookup,
    ) -> Result<VolatileLabObservation, GuardianClientError> {
        self.exchange(GuardianRequest::ConsumeExact(self.exact(lookup)))
            .await
    }

    pub async fn lookup_exact(
        &mut self,
        lookup: ExactLookup,
    ) -> Result<VolatileLabObservation, GuardianClientError> {
        self.exchange(GuardianRequest::LookupExact(self.exact(lookup)))
            .await
    }

    async fn handshake(mut stream: UnixStream) -> Result<Self, GuardianClientError> {
        let client_nonce = random_nonzero()?;
        write_request_async(&mut stream, GuardianRequest::Hello { client_nonce }).await?;
        let response = read_response_async(&mut stream).await?;
        let GuardianResponse::Hello {
            client_nonce: echoed_client_nonce,
            guardian_nonce,
            provider_incarnation,
        } = response
        else {
            return Err(GuardianClientError::Protocol(ProtocolError::InvalidFrame));
        };
        if echoed_client_nonce != client_nonce {
            return Err(GuardianClientError::Protocol(ProtocolError::InvalidFrame));
        }
        let session_nonce = session_nonce(&client_nonce, &guardian_nonce, &provider_incarnation);
        Ok(Self {
            stream,
            session_nonce,
            provider_incarnation,
        })
    }

    fn exact(&self, lookup: ExactLookup) -> ExactOperation {
        ExactOperation {
            session_nonce: self.session_nonce,
            operation_id: lookup.operation_id,
            scope_commitment: lookup.scope_commitment,
            expected_previous_head: lookup.expected_previous_head,
        }
    }

    async fn exchange(
        &mut self,
        request: GuardianRequest,
    ) -> Result<VolatileLabObservation, GuardianClientError> {
        let expected = match request {
            GuardianRequest::ConsumeExact(exact) | GuardianRequest::LookupExact(exact) => exact,
            GuardianRequest::Hello { .. } => {
                return Err(GuardianClientError::Protocol(ProtocolError::InvalidFrame));
            }
        };
        write_request_async(&mut self.stream, request).await?;
        let response = read_response_async(&mut self.stream).await?;
        let GuardianResponse::Outcome(outcome) = response else {
            return Err(GuardianClientError::Protocol(ProtocolError::InvalidFrame));
        };
        if outcome.request != expected
            || outcome
                .receipt
                .is_some_and(|receipt| receipt.provider_incarnation != self.provider_incarnation)
        {
            return Err(GuardianClientError::Protocol(ProtocolError::InvalidFrame));
        }
        Ok(VolatileLabObservation {
            kind: outcome.kind,
            receipt: outcome.receipt,
        })
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
struct SocketIdentity {
    socket_device: u64,
    socket_inode: u64,
    socket_owner: u32,
    socket_group: u32,
    socket_mode: u32,
    parent_device: u64,
    parent_inode: u64,
    parent_owner: u32,
    parent_group: u32,
    parent_mode: u32,
}

fn inspect_socket_path(
    path: &Path,
    expected_guardian_uid: u32,
    expected_guardian_gid: u32,
) -> Result<SocketIdentity, GuardianClientError> {
    let parent = path.parent().ok_or(GuardianClientError::UntrustedSocket(
        "socket path has no parent",
    ))?;
    if std::fs::canonicalize(path)? != path || std::fs::canonicalize(parent)? != parent {
        return Err(GuardianClientError::UntrustedSocket(
            "socket path contains a symlinked ancestor",
        ));
    }
    let metadata = std::fs::symlink_metadata(path)?;
    if metadata.file_type().is_symlink() || !metadata.file_type().is_socket() {
        return Err(GuardianClientError::UntrustedSocket(
            "path is not a direct Unix socket node",
        ));
    }
    let socket_mode = metadata.mode() & 0o777;
    if metadata.uid() != expected_guardian_uid
        || metadata.gid() != expected_guardian_gid
        || socket_mode != GUARDIAN_SOCKET_MODE
    {
        return Err(GuardianClientError::UntrustedSocket(
            "socket owner or exact mode mismatch",
        ));
    }

    let parent_metadata = std::fs::symlink_metadata(parent)?;
    if parent_metadata.file_type().is_symlink() || !parent_metadata.file_type().is_dir() {
        return Err(GuardianClientError::UntrustedSocket(
            "socket parent is not a direct directory",
        ));
    }
    let parent_mode = parent_metadata.mode() & 0o7777;
    if parent_metadata.uid() != expected_guardian_uid
        || parent_metadata.gid() != expected_guardian_gid
        || expected_guardian_gid == 0
        || parent_mode & 0o2000 == 0
        || parent_mode & 0o010 == 0
        || parent_mode & 0o022 != 0
        || !current_process_in_group(expected_guardian_gid)?
    {
        return Err(GuardianClientError::UntrustedSocket(
            "socket parent/shared group is not protected",
        ));
    }
    Ok(SocketIdentity {
        socket_device: metadata.dev(),
        socket_inode: metadata.ino(),
        socket_owner: metadata.uid(),
        socket_group: metadata.gid(),
        socket_mode,
        parent_device: parent_metadata.dev(),
        parent_inode: parent_metadata.ino(),
        parent_owner: parent_metadata.uid(),
        parent_group: parent_metadata.gid(),
        parent_mode,
    })
}

fn validate_normalized_absolute(path: &Path) -> Result<(), GuardianClientError> {
    if !path.is_absolute()
        || path.components().any(|component| {
            matches!(
                component,
                Component::CurDir | Component::ParentDir | Component::Prefix(_)
            )
        })
    {
        return Err(GuardianClientError::InvalidConfiguration(
            "socket path must be normalized and absolute",
        ));
    }
    Ok(())
}

fn validate_peer_uid(
    peer_uid: io::Result<u32>,
    expected_guardian_uid: u32,
) -> Result<(), GuardianClientError> {
    let actual = peer_uid.map_err(|_| GuardianClientError::PeerCredentialUnavailable)?;
    if actual != expected_guardian_uid {
        return Err(GuardianClientError::WrongPeerUid {
            expected: expected_guardian_uid,
            actual,
        });
    }
    Ok(())
}

async fn write_request_async(
    stream: &mut UnixStream,
    request: GuardianRequest,
) -> Result<(), GuardianClientError> {
    let encoded = encode_request(request)?;
    match tokio::time::timeout(IO_TIMEOUT, stream.write_all(&encoded)).await {
        Ok(Ok(())) => Ok(()),
        Ok(Err(error)) => Err(GuardianClientError::Io(error)),
        Err(_) => Err(GuardianClientError::Protocol(ProtocolError::Io)),
    }
}

async fn read_response_async(
    stream: &mut UnixStream,
) -> Result<GuardianResponse, GuardianClientError> {
    let mut length = [0_u8; 4];
    timed_read_exact(stream, &mut length).await?;
    let length = usize::try_from(u32::from_be_bytes(length))
        .map_err(|_| GuardianClientError::Protocol(ProtocolError::Oversized))?;
    if length == 0 || length > MAX_FRAME_BODY_BYTES {
        return Err(GuardianClientError::Protocol(ProtocolError::Oversized));
    }
    let mut body = vec![0_u8; length];
    timed_read_exact(stream, &mut body).await?;
    decode_response_body(&body).map_err(GuardianClientError::Protocol)
}

async fn timed_read_exact(
    stream: &mut UnixStream,
    output: &mut [u8],
) -> Result<(), GuardianClientError> {
    match tokio::time::timeout(IO_TIMEOUT, stream.read_exact(output)).await {
        Ok(Ok(_)) => Ok(()),
        Ok(Err(error)) if error.kind() == io::ErrorKind::UnexpectedEof => {
            Err(GuardianClientError::Protocol(ProtocolError::UnexpectedEof))
        }
        Ok(Err(error)) => Err(GuardianClientError::Io(error)),
        Err(_) => Err(GuardianClientError::Protocol(ProtocolError::Io)),
    }
}

fn random_nonzero() -> Result<FixedValue, GuardianClientError> {
    let random = SystemRandom::new();
    for _ in 0..2 {
        let mut value = [0_u8; 32];
        random
            .fill(&mut value)
            .map_err(|_| GuardianClientError::InvalidConfiguration("secure randomness failed"))?;
        if value.iter().any(|byte| *byte != 0) {
            return Ok(value);
        }
    }
    Err(GuardianClientError::InvalidConfiguration(
        "secure randomness returned zero",
    ))
}

fn effective_uid() -> u32 {
    // SAFETY: geteuid has no preconditions and cannot fail.
    unsafe { libc::geteuid() }
}

fn effective_gid() -> u32 {
    // SAFETY: getegid has no preconditions and cannot fail.
    unsafe { libc::getegid() }
}

fn current_process_in_group(group: u32) -> Result<bool, GuardianClientError> {
    if effective_gid() == group {
        return Ok(true);
    }
    // SAFETY: the first call requests the required length. The second call is
    // given a buffer of exactly that length and getgroups writes at most it.
    let count = unsafe { libc::getgroups(0, std::ptr::null_mut()) };
    if count < 0 {
        return Err(GuardianClientError::UntrustedSocket(
            "cannot inspect client supplementary groups",
        ));
    }
    let mut groups = vec![0; count as usize];
    let filled = unsafe { libc::getgroups(count, groups.as_mut_ptr()) };
    if filled < 0 || filled != count {
        return Err(GuardianClientError::UntrustedSocket(
            "cannot inspect client supplementary groups",
        ));
    }
    Ok(groups.into_iter().any(|candidate| candidate == group))
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::os::unix::fs::{symlink, PermissionsExt};

    #[test]
    fn client_forbids_root_and_same_uid_guardians() {
        let same_uid = effective_uid();
        let same_uid_error = if same_uid == 0 {
            GuardianClientError::InvalidConfiguration("root client uid is forbidden")
        } else {
            GuardianClientError::InvalidConfiguration("guardian uid must differ from client uid")
        };
        let result = tokio_test_connect(GuardianClientConfig {
            socket_path: "/does/not/matter.sock".into(),
            expected_guardian_uid: same_uid,
            expected_guardian_gid: effective_gid().max(1),
        });
        assert_eq!(result.to_string(), same_uid_error.to_string());

        let root_result = tokio_test_connect(GuardianClientConfig {
            socket_path: "/does/not/matter.sock".into(),
            expected_guardian_uid: 0,
            expected_guardian_gid: effective_gid().max(1),
        });
        if same_uid == 0 {
            assert!(matches!(
                root_result,
                GuardianClientError::InvalidConfiguration("root client uid is forbidden")
            ));
        } else {
            assert!(matches!(
                root_result,
                GuardianClientError::InvalidConfiguration("root guardian uid is forbidden")
            ));
        }
    }

    fn tokio_test_connect(config: GuardianClientConfig) -> GuardianClientError {
        let runtime = tokio::runtime::Builder::new_current_thread()
            .enable_all()
            .build()
            .unwrap();
        runtime
            .block_on(GuardianClient::connect(config))
            .expect_err("connection must be rejected")
    }

    #[test]
    fn relative_and_parent_traversal_paths_are_rejected() {
        assert!(validate_normalized_absolute(Path::new("guardian.sock")).is_err());
        assert!(validate_normalized_absolute(Path::new("/run/../tmp/guardian.sock")).is_err());
        assert!(validate_normalized_absolute(Path::new("/run/guardian.sock")).is_ok());
    }

    #[test]
    fn peer_credential_failure_and_wrong_uid_are_rejected() {
        assert!(matches!(
            validate_peer_uid(Err(io::Error::other("missing")), 10),
            Err(GuardianClientError::PeerCredentialUnavailable)
        ));
        assert!(matches!(
            validate_peer_uid(Ok(11), 10),
            Err(GuardianClientError::WrongPeerUid {
                expected: 10,
                actual: 11
            })
        ));
    }

    #[test]
    fn observations_are_never_authoritative() {
        let observation = VolatileLabObservation {
            kind: OutcomeKind::Hold,
            receipt: None,
        };
        assert!(!observation.grants_authority());
        assert_eq!(observation.witness_class(), WitnessClass::VolatileLab);
    }

    #[test]
    fn socket_node_mode_and_parent_are_all_pinned() {
        if effective_uid() == 0 || effective_gid() == 0 {
            return;
        }
        let directory = tempfile::tempdir().expect("temp directory");
        let socket = directory.path().join("guardian.sock");
        let alias = directory.path().join("guardian-link.sock");
        let _listener = std::os::unix::net::UnixListener::bind(&socket).expect("bind socket");
        std::fs::set_permissions(
            &socket,
            std::fs::Permissions::from_mode(GUARDIAN_SOCKET_MODE),
        )
        .expect("set socket permissions");

        std::fs::set_permissions(directory.path(), std::fs::Permissions::from_mode(0o2750))
            .expect("protect shared-group parent");

        assert!(inspect_socket_path(&socket, effective_uid(), effective_gid()).is_ok());

        symlink(&socket, &alias).expect("create symlink");
        assert!(matches!(
            inspect_socket_path(&alias, effective_uid(), effective_gid()),
            Err(GuardianClientError::UntrustedSocket(_))
        ));

        std::fs::set_permissions(&socket, std::fs::Permissions::from_mode(0o600))
            .expect("set wrong socket permissions");
        assert!(matches!(
            inspect_socket_path(&socket, effective_uid(), effective_gid()),
            Err(GuardianClientError::UntrustedSocket(_))
        ));

        std::fs::set_permissions(
            &socket,
            std::fs::Permissions::from_mode(GUARDIAN_SOCKET_MODE),
        )
        .expect("restore socket permissions");
        std::fs::set_permissions(directory.path(), std::fs::Permissions::from_mode(0o2770))
            .expect("make parent replaceable");
        assert!(matches!(
            inspect_socket_path(&socket, effective_uid(), effective_gid()),
            Err(GuardianClientError::UntrustedSocket(_))
        ));
    }

    #[test]
    fn symlinked_ancestor_is_rejected_even_when_direct_parent_is_a_directory() {
        if effective_uid() == 0 || effective_gid() == 0 {
            return;
        }
        let directory = tempfile::tempdir().expect("temp directory");
        let real = directory.path().join("real");
        let nested = real.join("nested");
        let alias = directory.path().join("alias");
        std::fs::create_dir(&real).expect("real directory");
        std::fs::create_dir(&nested).expect("nested directory");
        std::fs::set_permissions(&nested, std::fs::Permissions::from_mode(0o2750))
            .expect("protect nested directory");
        symlink(&real, &alias).expect("ancestor symlink");
        let real_socket = nested.join("guardian.sock");
        let alias_socket = alias.join("nested/guardian.sock");
        let _listener = std::os::unix::net::UnixListener::bind(&real_socket).expect("bind socket");
        std::fs::set_permissions(
            &real_socket,
            std::fs::Permissions::from_mode(GUARDIAN_SOCKET_MODE),
        )
        .expect("set socket permissions");

        assert!(matches!(
            inspect_socket_path(&alias_socket, effective_uid(), effective_gid()),
            Err(GuardianClientError::UntrustedSocket(
                "socket path contains a symlinked ancestor"
            ))
        ));
    }
}
