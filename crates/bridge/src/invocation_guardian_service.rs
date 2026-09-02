//! Independent invocation-guardian candidate service.
//!
//! The repository intentionally has no production monotonic witness. The only
//! runnable implementation is an explicitly selected, in-memory volatile lab
//! witness whose protocol responses can never grant invocation authority.

use std::io;
use std::os::unix::fs::{FileTypeExt, MetadataExt, PermissionsExt};
use std::path::{Component, Path, PathBuf};
use std::sync::Arc;
use std::time::Duration;

#[cfg(any(test, feature = "invocation-guardian-lab"))]
use std::collections::HashMap;
#[cfg(any(test, feature = "invocation-guardian-lab"))]
use std::sync::Mutex;

use ring::rand::{SecureRandom, SystemRandom};
use sha2::{Digest, Sha256};
use tokio::io::{AsyncReadExt, AsyncWriteExt};
use tokio::net::{UnixListener, UnixStream};
use tokio::sync::Semaphore;

use crate::invocation_guardian_protocol::{
    decode_request_body, encode_response, session_nonce, CommitReceipt, ExactOperation, FixedValue,
    GuardianRequest, GuardianResponse, OutcomeKind, OutcomeResponse, ProtocolError, WitnessClass,
    MAX_FRAME_BODY_BYTES,
};

const IO_TIMEOUT: Duration = Duration::from_secs(10);
const MAX_REQUESTS_PER_CONNECTION: usize = 64;
const MAX_CONCURRENT_CONNECTIONS: usize = 32;
#[cfg(any(test, feature = "invocation-guardian-lab"))]
const ZERO_HEAD: FixedValue = [0; 32];

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum WitnessDecision {
    Committed(CommitReceipt),
    AlreadyCommitted(CommitReceipt),
    Conflict,
    Indeterminate,
    Hold,
}

/// Candidate witness seam. Implementations must linearize `consume_exact` and
/// make a lost commit result recoverable through `lookup_exact`.
///
/// This trait alone makes no durability or anti-rollback claim.
pub trait InvocationWitness: Send + Sync {
    fn witness_class(&self) -> WitnessClass;
    fn provider_incarnation(&self) -> FixedValue;
    fn consume_exact(&self, request: &ExactOperation) -> WitnessDecision;
    fn lookup_exact(&self, request: &ExactOperation) -> WitnessDecision;
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct GuardianServiceConfig {
    pub expected_client_uid: u32,
    pub expected_socket_gid: u32,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct VolatileLabConfig {
    pub expected_client_uid: u32,
    pub expected_socket_gid: u32,
    pub allow_same_uid_lab: bool,
}

#[derive(Debug, thiserror::Error)]
pub enum GuardianServiceError {
    #[error("HOLD: no production monotonic invocation witness is available")]
    ProductionWitnessUnavailable,
    #[error("invalid guardian configuration: {0}")]
    InvalidConfiguration(&'static str),
    #[error("guardian peer credential unavailable")]
    PeerCredentialUnavailable,
    #[error("guardian rejected peer uid {actual}; expected {expected}")]
    WrongPeerUid { expected: u32, actual: u32 },
    #[error("guardian protocol rejected: {0}")]
    Protocol(#[from] ProtocolError),
    #[error("guardian I/O failed: {0}")]
    Io(#[from] io::Error),
}

pub struct GuardianService {
    expected_client_uid: u32,
    expected_socket_gid: u32,
    witness: Arc<dyn InvocationWitness>,
}

impl GuardianService {
    /// Production construction is a deliberate HOLD until an independently
    /// operated monotonic witness is implemented and reviewed.
    pub fn production(config: GuardianServiceConfig) -> Result<Self, GuardianServiceError> {
        validate_service_identity(
            effective_uid(),
            config.expected_client_uid,
            config.expected_socket_gid,
            false,
        )?;
        Err(GuardianServiceError::ProductionWitnessUnavailable)
    }

    #[cfg(any(test, feature = "invocation-guardian-lab"))]
    pub fn volatile_lab(config: VolatileLabConfig) -> Result<Self, GuardianServiceError> {
        validate_service_identity(
            effective_uid(),
            config.expected_client_uid,
            config.expected_socket_gid,
            config.allow_same_uid_lab,
        )?;
        Ok(Self {
            expected_client_uid: config.expected_client_uid,
            expected_socket_gid: config.expected_socket_gid,
            witness: Arc::new(VolatileLabWitness::new()?),
        })
    }

    pub async fn serve(self, socket_path: &Path) -> Result<(), GuardianServiceError> {
        let listener = bind_lab_socket(socket_path, self.expected_socket_gid)?;
        let _socket_guard = BoundSocketGuard::capture(socket_path)?;
        let witness = self.witness;
        let expected_client_uid = self.expected_client_uid;
        let permits = Arc::new(Semaphore::new(MAX_CONCURRENT_CONNECTIONS));

        loop {
            let (stream, _) = listener.accept().await?;
            let Ok(permit) = Arc::clone(&permits).try_acquire_owned() else {
                drop(stream);
                continue;
            };
            let witness = Arc::clone(&witness);
            tokio::spawn(async move {
                let _permit = permit;
                if let Err(error) = serve_connection(stream, expected_client_uid, witness).await {
                    tracing::warn!(%error, "invocation guardian rejected connection");
                }
            });
        }
    }
}

#[cfg(any(test, feature = "invocation-guardian-lab"))]
struct VolatileLabWitness {
    incarnation: FixedValue,
    state: Mutex<VolatileState>,
}

#[cfg(any(test, feature = "invocation-guardian-lab"))]
#[derive(Default)]
struct VolatileState {
    head: FixedValue,
    revision: u64,
    by_operation: HashMap<FixedValue, CommitReceipt>,
}

#[cfg(any(test, feature = "invocation-guardian-lab"))]
impl VolatileLabWitness {
    fn new() -> Result<Self, GuardianServiceError> {
        let incarnation = random_nonzero()?;
        Ok(Self::with_incarnation(incarnation))
    }

    fn with_incarnation(incarnation: FixedValue) -> Self {
        assert!(incarnation.iter().any(|byte| *byte != 0));
        Self {
            incarnation,
            state: Mutex::new(VolatileState {
                head: ZERO_HEAD,
                ..VolatileState::default()
            }),
        }
    }
}

#[cfg(any(test, feature = "invocation-guardian-lab"))]
impl InvocationWitness for VolatileLabWitness {
    fn witness_class(&self) -> WitnessClass {
        WitnessClass::VolatileLab
    }

    fn provider_incarnation(&self) -> FixedValue {
        self.incarnation
    }

    fn consume_exact(&self, request: &ExactOperation) -> WitnessDecision {
        let Ok(mut state) = self.state.lock() else {
            return WitnessDecision::Hold;
        };
        if let Some(receipt) = state.by_operation.get(&request.operation_id) {
            return if receipt.scope_commitment == request.scope_commitment
                && receipt.previous_head == request.expected_previous_head
            {
                WitnessDecision::AlreadyCommitted(*receipt)
            } else {
                WitnessDecision::Conflict
            };
        }
        if request.expected_previous_head != state.head {
            return WitnessDecision::Conflict;
        }
        let Some(revision) = state.revision.checked_add(1) else {
            return WitnessDecision::Hold;
        };
        let new_head = next_head(
            &self.incarnation,
            revision,
            &request.expected_previous_head,
            &request.operation_id,
            &request.scope_commitment,
        );
        let receipt = CommitReceipt {
            operation_id: request.operation_id,
            scope_commitment: request.scope_commitment,
            previous_head: request.expected_previous_head,
            new_head,
            revision,
            provider_incarnation: self.incarnation,
        };
        state.head = new_head;
        state.revision = revision;
        state.by_operation.insert(request.operation_id, receipt);
        WitnessDecision::Committed(receipt)
    }

    fn lookup_exact(&self, request: &ExactOperation) -> WitnessDecision {
        let Ok(state) = self.state.lock() else {
            return WitnessDecision::Hold;
        };
        match state.by_operation.get(&request.operation_id) {
            Some(receipt)
                if receipt.scope_commitment == request.scope_commitment
                    && receipt.previous_head == request.expected_previous_head =>
            {
                WitnessDecision::AlreadyCommitted(*receipt)
            }
            Some(_) => WitnessDecision::Conflict,
            None => WitnessDecision::Indeterminate,
        }
    }
}

async fn serve_connection(
    mut stream: UnixStream,
    expected_client_uid: u32,
    witness: Arc<dyn InvocationWitness>,
) -> Result<(), GuardianServiceError> {
    validate_peer_uid(
        stream.peer_cred().map(|credential| credential.uid()),
        expected_client_uid,
    )?;
    if witness.witness_class() != WitnessClass::VolatileLab {
        return Err(GuardianServiceError::InvalidConfiguration(
            "protocol v1 accepts only volatile_lab witnesses",
        ));
    }
    let provider_incarnation = witness.provider_incarnation();
    if provider_incarnation.iter().all(|byte| *byte == 0) {
        return Err(GuardianServiceError::InvalidConfiguration(
            "zero provider incarnation",
        ));
    }

    let hello = read_request_async(&mut stream).await?;
    let GuardianRequest::Hello { client_nonce } = hello else {
        return Err(GuardianServiceError::Protocol(ProtocolError::InvalidFrame));
    };
    let guardian_nonce = random_nonzero()?;
    let connection_nonce = session_nonce(&client_nonce, &guardian_nonce, &provider_incarnation);
    write_response_async(
        &mut stream,
        GuardianResponse::Hello {
            client_nonce,
            guardian_nonce,
            provider_incarnation,
        },
    )
    .await?;

    for _ in 0..MAX_REQUESTS_PER_CONNECTION {
        let request = match read_request_async(&mut stream).await {
            Ok(request) => request,
            Err(GuardianServiceError::Protocol(ProtocolError::UnexpectedEof)) => return Ok(()),
            Err(error) => return Err(error),
        };
        let (exact, decision) = match request {
            GuardianRequest::ConsumeExact(exact) if exact.session_nonce == connection_nonce => {
                let decision = witness.consume_exact(&exact);
                (exact, decision)
            }
            GuardianRequest::LookupExact(exact) if exact.session_nonce == connection_nonce => {
                let decision = witness.lookup_exact(&exact);
                (exact, decision)
            }
            _ => return Err(GuardianServiceError::Protocol(ProtocolError::InvalidFrame)),
        };
        let response = checked_outcome(exact, decision, provider_incarnation);
        write_response_async(&mut stream, GuardianResponse::Outcome(response)).await?;
    }
    Ok(())
}

fn checked_outcome(
    request: ExactOperation,
    decision: WitnessDecision,
    provider_incarnation: FixedValue,
) -> OutcomeResponse {
    let (kind, receipt) = match decision {
        WitnessDecision::Committed(receipt)
            if receipt_matches(&receipt, &request, &provider_incarnation) =>
        {
            (OutcomeKind::Committed, Some(receipt))
        }
        WitnessDecision::AlreadyCommitted(receipt)
            if receipt_matches(&receipt, &request, &provider_incarnation) =>
        {
            (OutcomeKind::AlreadyCommitted, Some(receipt))
        }
        WitnessDecision::Conflict => (OutcomeKind::Conflict, None),
        WitnessDecision::Indeterminate => (OutcomeKind::Indeterminate, None),
        WitnessDecision::Hold
        | WitnessDecision::Committed(_)
        | WitnessDecision::AlreadyCommitted(_) => (OutcomeKind::Hold, None),
    };
    OutcomeResponse {
        request,
        kind,
        receipt,
    }
}

fn receipt_matches(
    receipt: &CommitReceipt,
    request: &ExactOperation,
    provider_incarnation: &FixedValue,
) -> bool {
    receipt.operation_id == request.operation_id
        && receipt.scope_commitment == request.scope_commitment
        && receipt.previous_head == request.expected_previous_head
        && receipt.provider_incarnation == *provider_incarnation
        && receipt.revision > 0
        && receipt.new_head.iter().any(|byte| *byte != 0)
}

fn next_head(
    incarnation: &FixedValue,
    revision: u64,
    previous_head: &FixedValue,
    operation_id: &FixedValue,
    scope_commitment: &FixedValue,
) -> FixedValue {
    let mut digest = Sha256::new();
    digest.update(b"ab.invocation_guardian.volatile_head.v1\0");
    digest.update(incarnation);
    digest.update(revision.to_be_bytes());
    digest.update(previous_head);
    digest.update(operation_id);
    digest.update(scope_commitment);
    digest.finalize().into()
}

fn random_nonzero() -> Result<FixedValue, GuardianServiceError> {
    let random = SystemRandom::new();
    for _ in 0..2 {
        let mut value = [0_u8; 32];
        random
            .fill(&mut value)
            .map_err(|_| GuardianServiceError::InvalidConfiguration("secure randomness failed"))?;
        if value.iter().any(|byte| *byte != 0) {
            return Ok(value);
        }
    }
    Err(GuardianServiceError::InvalidConfiguration(
        "secure randomness returned zero",
    ))
}

async fn read_request_async(
    stream: &mut UnixStream,
) -> Result<GuardianRequest, GuardianServiceError> {
    let mut length = [0_u8; 4];
    timed_read_exact(stream, &mut length).await?;
    let length = usize::try_from(u32::from_be_bytes(length))
        .map_err(|_| GuardianServiceError::Protocol(ProtocolError::Oversized))?;
    if length == 0 || length > MAX_FRAME_BODY_BYTES {
        return Err(GuardianServiceError::Protocol(ProtocolError::Oversized));
    }
    let mut body = vec![0_u8; length];
    timed_read_exact(stream, &mut body).await?;
    decode_request_body(&body).map_err(GuardianServiceError::Protocol)
}

async fn timed_read_exact(
    stream: &mut UnixStream,
    output: &mut [u8],
) -> Result<(), GuardianServiceError> {
    match tokio::time::timeout(IO_TIMEOUT, stream.read_exact(output)).await {
        Ok(Ok(_)) => Ok(()),
        Ok(Err(error)) if error.kind() == io::ErrorKind::UnexpectedEof => {
            Err(GuardianServiceError::Protocol(ProtocolError::UnexpectedEof))
        }
        Ok(Err(error)) => Err(GuardianServiceError::Io(error)),
        Err(_) => Err(GuardianServiceError::Protocol(ProtocolError::Io)),
    }
}

async fn write_response_async(
    stream: &mut UnixStream,
    response: GuardianResponse,
) -> Result<(), GuardianServiceError> {
    let encoded = encode_response(response)?;
    match tokio::time::timeout(IO_TIMEOUT, stream.write_all(&encoded)).await {
        Ok(Ok(())) => Ok(()),
        Ok(Err(error)) => Err(GuardianServiceError::Io(error)),
        Err(_) => Err(GuardianServiceError::Protocol(ProtocolError::Io)),
    }
}

fn validate_peer_uid(
    peer_uid: io::Result<u32>,
    expected_client_uid: u32,
) -> Result<(), GuardianServiceError> {
    let actual = peer_uid.map_err(|_| GuardianServiceError::PeerCredentialUnavailable)?;
    if actual != expected_client_uid {
        return Err(GuardianServiceError::WrongPeerUid {
            expected: expected_client_uid,
            actual,
        });
    }
    Ok(())
}

fn bind_lab_socket(
    path: &Path,
    expected_socket_gid: u32,
) -> Result<UnixListener, GuardianServiceError> {
    validate_normalized_absolute(path)?;
    let parent = path
        .parent()
        .ok_or(GuardianServiceError::InvalidConfiguration(
            "socket path has no parent",
        ))?;
    if std::fs::canonicalize(parent)? != parent {
        return Err(GuardianServiceError::InvalidConfiguration(
            "socket parent contains a symlinked ancestor",
        ));
    }
    let parent_metadata = std::fs::symlink_metadata(parent)?;
    let guardian_uid = effective_uid();
    if !parent_metadata.file_type().is_dir()
        || parent_metadata.file_type().is_symlink()
        || parent_metadata.uid() != guardian_uid
        || parent_metadata.gid() != expected_socket_gid
        || expected_socket_gid == 0
        || parent_metadata.mode() & 0o2000 == 0
        || parent_metadata.mode() & 0o010 == 0
        || parent_metadata.mode() & 0o022 != 0
    {
        return Err(GuardianServiceError::InvalidConfiguration(
            "socket parent must be guardian-owned setgid shared-group storage without group/world write",
        ));
    }
    match std::fs::symlink_metadata(path) {
        Err(error) if error.kind() == io::ErrorKind::NotFound => {}
        Ok(_) => {
            return Err(GuardianServiceError::InvalidConfiguration(
                "refusing to replace an existing socket path",
            ));
        }
        Err(error) => return Err(GuardianServiceError::Io(error)),
    }
    let listener = UnixListener::bind(path)?;
    // The pre-created setgid parent pins the socket to the dedicated group.
    // Bridge must belong to that group; all other UIDs remain filesystem-denied.
    std::fs::set_permissions(path, std::fs::Permissions::from_mode(0o660))?;
    let metadata = std::fs::symlink_metadata(path)?;
    if !metadata.file_type().is_socket()
        || metadata.file_type().is_symlink()
        || metadata.uid() != guardian_uid
        || metadata.gid() != expected_socket_gid
        || metadata.mode() & 0o777 != 0o660
    {
        return Err(GuardianServiceError::InvalidConfiguration(
            "bound socket identity or mode validation failed",
        ));
    }
    Ok(listener)
}

fn validate_normalized_absolute(path: &Path) -> Result<(), GuardianServiceError> {
    if !path.is_absolute()
        || path.components().any(|component| {
            matches!(
                component,
                Component::CurDir | Component::ParentDir | Component::Prefix(_)
            )
        })
    {
        return Err(GuardianServiceError::InvalidConfiguration(
            "socket path must be normalized and absolute",
        ));
    }
    Ok(())
}

fn effective_uid() -> u32 {
    // SAFETY: geteuid has no preconditions and cannot fail.
    unsafe { libc::geteuid() }
}

fn validate_service_identity(
    guardian_uid: u32,
    expected_client_uid: u32,
    expected_socket_gid: u32,
    allow_same_uid_lab: bool,
) -> Result<(), GuardianServiceError> {
    if guardian_uid == 0 {
        return Err(GuardianServiceError::InvalidConfiguration(
            "root guardian uid is forbidden",
        ));
    }
    if expected_client_uid == 0 {
        return Err(GuardianServiceError::InvalidConfiguration(
            "root client uid is forbidden",
        ));
    }
    if expected_socket_gid == 0 {
        return Err(GuardianServiceError::InvalidConfiguration(
            "root socket group is forbidden",
        ));
    }
    if guardian_uid == expected_client_uid && !allow_same_uid_lab {
        return Err(GuardianServiceError::InvalidConfiguration(
            "same-uid lab requires --allow-same-uid-lab",
        ));
    }
    Ok(())
}

struct BoundSocketGuard {
    path: PathBuf,
    device: u64,
    inode: u64,
    owner: u32,
}

impl BoundSocketGuard {
    fn capture(path: &Path) -> Result<Self, GuardianServiceError> {
        let metadata = std::fs::symlink_metadata(path)?;
        Ok(Self {
            path: path.to_owned(),
            device: metadata.dev(),
            inode: metadata.ino(),
            owner: metadata.uid(),
        })
    }
}

impl Drop for BoundSocketGuard {
    fn drop(&mut self) {
        let Ok(metadata) = std::fs::symlink_metadata(&self.path) else {
            return;
        };
        if metadata.file_type().is_socket()
            && !metadata.file_type().is_symlink()
            && metadata.dev() == self.device
            && metadata.ino() == self.inode
            && metadata.uid() == self.owner
        {
            let _ = std::fs::remove_file(&self.path);
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn value(byte: u8) -> FixedValue {
        [byte; 32]
    }

    fn exact(operation: u8, scope: u8, previous: FixedValue) -> ExactOperation {
        ExactOperation {
            session_nonce: value(9),
            operation_id: value(operation),
            scope_commitment: value(scope),
            expected_previous_head: previous,
        }
    }

    #[test]
    fn production_constructor_holds_for_valid_nonroot_identity() {
        let actual_guardian_uid = effective_uid();
        let guardian_uid = actual_guardian_uid.max(1);
        let client_uid = if guardian_uid == u32::MAX {
            guardian_uid - 1
        } else {
            guardian_uid + 1
        };
        let result = GuardianService::production(GuardianServiceConfig {
            expected_client_uid: client_uid,
            expected_socket_gid: 1,
        });
        if actual_guardian_uid == 0 {
            assert!(matches!(
                result,
                Err(GuardianServiceError::InvalidConfiguration(
                    "root guardian uid is forbidden"
                ))
            ));
        } else {
            assert!(matches!(
                result,
                Err(GuardianServiceError::ProductionWitnessUnavailable)
            ));
        }
    }

    #[test]
    fn root_and_unapproved_same_uid_identities_are_rejected() {
        assert!(validate_service_identity(0, 1000, 1000, true).is_err());
        assert!(validate_service_identity(1000, 0, 1000, true).is_err());
        assert!(validate_service_identity(1000, 1001, 0, true).is_err());
        assert!(validate_service_identity(1000, 1000, 1000, false).is_err());
        assert!(validate_service_identity(1000, 1000, 1000, true).is_ok());
        assert!(validate_service_identity(1000, 1001, 1000, false).is_ok());
    }

    #[tokio::test]
    async fn lab_socket_inherits_pinned_group_and_mode() {
        use std::os::unix::fs::PermissionsExt;

        let guardian_uid = effective_uid();
        // Root guardian/group are intentionally unsupported; deterministic
        // identity validation above covers those rejection branches.
        let guardian_gid = unsafe { libc::getegid() };
        if guardian_uid == 0 || guardian_gid == 0 {
            return;
        }
        let directory = tempfile::tempdir().expect("temp directory");
        std::fs::set_permissions(directory.path(), std::fs::Permissions::from_mode(0o2750))
            .expect("protect setgid parent");
        let socket = directory.path().join("guardian.sock");
        let listener = bind_lab_socket(&socket, guardian_gid).expect("bind lab socket");
        let metadata = std::fs::symlink_metadata(&socket).expect("socket metadata");
        assert!(metadata.file_type().is_socket());
        assert_eq!(metadata.uid(), guardian_uid);
        assert_eq!(metadata.gid(), guardian_gid);
        assert_eq!(metadata.mode() & 0o777, 0o660);
        drop(listener);
    }

    #[test]
    fn lab_service_rejects_symlinked_parent_ancestor() {
        use std::os::unix::fs::{symlink, PermissionsExt};

        let guardian_uid = effective_uid();
        // SAFETY: getegid has no preconditions and cannot fail.
        let guardian_gid = unsafe { libc::getegid() };
        if guardian_uid == 0 || guardian_gid == 0 {
            return;
        }
        let directory = tempfile::tempdir().expect("temp directory");
        let real = directory.path().join("real");
        let nested = real.join("nested");
        let alias = directory.path().join("alias");
        std::fs::create_dir(&real).expect("real directory");
        std::fs::create_dir(&nested).expect("nested directory");
        std::fs::set_permissions(&nested, std::fs::Permissions::from_mode(0o2750))
            .expect("protect nested parent");
        symlink(&real, &alias).expect("ancestor symlink");

        assert!(matches!(
            bind_lab_socket(&alias.join("nested/guardian.sock"), guardian_gid),
            Err(GuardianServiceError::InvalidConfiguration(
                "socket parent contains a symlinked ancestor"
            ))
        ));
    }

    #[test]
    fn volatile_witness_is_exact_once_and_conflicts_on_drift() {
        let witness = VolatileLabWitness::with_incarnation(value(7));
        let request = exact(1, 2, ZERO_HEAD);
        let receipt = match witness.consume_exact(&request) {
            WitnessDecision::Committed(receipt) => receipt,
            other => panic!("unexpected first decision: {other:?}"),
        };
        assert_eq!(receipt.revision, 1);
        assert!(matches!(
            witness.consume_exact(&request),
            WitnessDecision::AlreadyCommitted(replayed) if replayed == receipt
        ));

        let drifted_scope = exact(1, 3, ZERO_HEAD);
        assert_eq!(
            witness.consume_exact(&drifted_scope),
            WitnessDecision::Conflict
        );
        let wrong_head = exact(2, 2, ZERO_HEAD);
        assert_eq!(
            witness.consume_exact(&wrong_head),
            WitnessDecision::Conflict
        );
    }

    #[test]
    fn lost_commit_result_is_recovered_by_exact_lookup() {
        let witness = VolatileLabWitness::with_incarnation(value(7));
        let request = exact(1, 2, ZERO_HEAD);

        let _lost_result = witness.consume_exact(&request);

        assert!(matches!(
            witness.lookup_exact(&request),
            WitnessDecision::AlreadyCommitted(receipt)
                if receipt.operation_id == request.operation_id
                    && receipt.scope_commitment == request.scope_commitment
                    && receipt.previous_head == request.expected_previous_head
                    && receipt.provider_incarnation == value(7)
        ));
        assert_eq!(
            witness.lookup_exact(&exact(1, 4, ZERO_HEAD)),
            WitnessDecision::Conflict
        );
        assert_eq!(
            witness.lookup_exact(&exact(8, 2, ZERO_HEAD)),
            WitnessDecision::Indeterminate
        );
    }

    #[test]
    fn peer_uid_failure_and_mismatch_are_hard_rejections() {
        assert!(matches!(
            validate_peer_uid(Err(io::Error::other("unavailable")), 10),
            Err(GuardianServiceError::PeerCredentialUnavailable)
        ));
        assert!(matches!(
            validate_peer_uid(Ok(11), 10),
            Err(GuardianServiceError::WrongPeerUid {
                expected: 10,
                actual: 11
            })
        ));
        assert!(validate_peer_uid(Ok(10), 10).is_ok());
    }

    #[test]
    fn malformed_witness_receipt_degrades_to_hold() {
        let request = exact(1, 2, ZERO_HEAD);
        let invalid = CommitReceipt {
            operation_id: value(99),
            scope_commitment: request.scope_commitment,
            previous_head: request.expected_previous_head,
            new_head: value(4),
            revision: 1,
            provider_incarnation: value(7),
        };
        let response = checked_outcome(request, WitnessDecision::Committed(invalid), value(7));
        assert_eq!(response.kind, OutcomeKind::Hold);
        assert_eq!(response.receipt, None);
    }
}
