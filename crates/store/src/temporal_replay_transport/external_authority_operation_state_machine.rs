//! S11 synthetic atomic authority-operation outbox preregistration.
//!
//! The protocol has two database linearization points. L1 atomically reserves
//! an operation and challenge, consumes one concrete replay identity, and
//! freezes the exact decision/signing bytes. L2 atomically persists a locally
//! verified exact-version signature. The signer call is deliberately outside
//! both transactions, so this module makes no database/KMS atomicity or
//! exactly-once-signing claim.
//!
//! Production code contains only private protocol shapes and verification. It
//! has no database, signer, provider, network, clock, cache, constructor,
//! `StateStore`, Bridge, or transport implementation. The in-process outbox,
//! signer, and injected cut points below are test-only sequence models, not
//! external durability, linearizability, rollback, fencing, or custody proof.

#![cfg_attr(not(test), allow(dead_code))]

use ring::signature::{UnparsedPublicKey, ED25519};
use sha2::{Digest, Sha256};
use std::fmt;

const POLICY_ID: &str = "agent-bridge/track-b/atomic-authority-operation/v1";
const PROFILE: &str = "DB_L1_ATOMIC_OUTBOX_EXACT_VERSION_RESIGN_DB_L2_VERIFIED_CAS_NO_KEY_FALLBACK";
const ALGORITHM: &str = "Ed25519";
const REQUEST_DOMAIN: &[u8] = b"agent-bridge/track-b/atomic-authority-operation/request/v1";
const PREPARED_RECORD_DOMAIN: &[u8] =
    b"agent-bridge/track-b/atomic-authority-operation/prepared-record/v1";
const SIGN_JOB_DOMAIN: &[u8] = b"agent-bridge/track-b/atomic-authority-operation/sign-job/v1";
const DECISION_MESSAGE_DOMAIN: &[u8] =
    b"agent-bridge/track-b/atomic-authority-operation/decision-message/v1";
const STABLE_RESULT_DOMAIN: &[u8] =
    b"agent-bridge/track-b/atomic-authority-operation/stable-result/v1";
const SYNTHETIC_L2_RECORD_DOMAIN: &[u8] =
    b"agent-bridge/track-b/atomic-authority-operation/synthetic-l2-record/v1";
const ZERO_COMMITMENT: [u8; 32] = [0; 32];
const S9_CONTRACT_SHA256: [u8; 32] = [
    0xd5, 0x37, 0xb8, 0x0c, 0xe0, 0xd2, 0xbb, 0xb3, 0xc4, 0xd0, 0x1a, 0x98, 0x8a, 0x96, 0x85, 0x43,
    0x26, 0x72, 0x07, 0x8e, 0xae, 0x07, 0xd0, 0xb9, 0x76, 0xb1, 0x26, 0x8a, 0x27, 0x52, 0x6f, 0xc4,
];
const S10_CONTRACT_SHA256: [u8; 32] = [
    0xda, 0x35, 0x66, 0xf1, 0x3d, 0xf5, 0x22, 0x95, 0x8f, 0x05, 0xc8, 0x71, 0xad, 0x46, 0x79, 0xd8,
    0x9c, 0xda, 0x9b, 0x88, 0x8b, 0xa8, 0xaa, 0x4e, 0xb4, 0xca, 0xae, 0xe4, 0xc4, 0x57, 0xfb, 0x88,
];

#[derive(Debug, thiserror::Error)]
#[error("{code}: {detail}")]
struct AtomicAuthorityOperationV1Error {
    code: &'static str,
    detail: &'static str,
}

impl AtomicAuthorityOperationV1Error {
    #[cfg(test)]
    fn code(&self) -> &'static str {
        self.code
    }
}

type OperationResult<T> = Result<T, AtomicAuthorityOperationV1Error>;

fn operation_error(code: &'static str, detail: &'static str) -> AtomicAuthorityOperationV1Error {
    AtomicAuthorityOperationV1Error { code, detail }
}

fn sha256_bytes(bytes: &[u8]) -> [u8; 32] {
    Sha256::digest(bytes).into()
}

fn nonzero(value: &[u8; 32]) -> bool {
    value.iter().any(|byte| *byte != 0)
}

fn valid_label(value: &str) -> bool {
    !value.is_empty()
        && value.len() <= 128
        && value.is_ascii()
        && value
            .bytes()
            .next()
            .is_some_and(|byte| byte.is_ascii_lowercase() || byte.is_ascii_digit())
        && value.bytes().all(|byte| {
            byte.is_ascii_lowercase()
                || byte.is_ascii_digit()
                || matches!(byte, b'.' | b'_' | b':' | b'-')
        })
}

fn append_frame(output: &mut Vec<u8>, value: &[u8]) {
    output.extend_from_slice(&(value.len() as u64).to_be_bytes());
    output.extend_from_slice(value);
}

fn framed_message(domain: &[u8], fields: &[&[u8]]) -> Vec<u8> {
    let mut message = Vec::new();
    append_frame(&mut message, domain);
    for field in fields {
        append_frame(&mut message, field);
    }
    message
}

fn framed_digest(domain: &[u8], fields: &[&[u8]]) -> [u8; 32] {
    sha256_bytes(&framed_message(domain, fields))
}

#[derive(Clone, PartialEq, Eq)]
struct AtomicAuthorityOperationRequestV1 {
    provider_profile_id: String,
    authority_namespace_id: String,
    tenant_id: String,
    audience: String,
    provider_cluster_id: String,
    provider_incarnation: [u8; 32],
    journal_generation_id: [u8; 32],
    operation_id: [u8; 32],
    original_challenge: [u8; 32],
    original_request_sha256: [u8; 32],
    concrete_replay_identity_sha256: [u8; 32],
    authority_snapshot_sha256: [u8; 32],
    canonical_decision_sha256: [u8; 32],
    trust_policy_sha256: [u8; 32],
    signer_key_id: String,
    signer_key_version: u64,
}

impl fmt::Debug for AtomicAuthorityOperationRequestV1 {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        formatter
            .debug_struct("AtomicAuthorityOperationRequestV1")
            .field("identity", &"[EXACT_OPERATION_REPLAY_DECISION_BINDING]")
            .finish_non_exhaustive()
    }
}

fn validate_request(request: &AtomicAuthorityOperationRequestV1) -> OperationResult<()> {
    if !valid_label(&request.provider_profile_id)
        || !valid_label(&request.authority_namespace_id)
        || !valid_label(&request.tenant_id)
        || !valid_label(&request.audience)
        || !valid_label(&request.provider_cluster_id)
        || !valid_label(&request.signer_key_id)
        || request.signer_key_version == 0
    {
        return Err(operation_error(
            "track_b_atomic_authority_operation_v1_request_scope",
            "scope labels and exact nonzero signer version must be canonical",
        ));
    }
    if ![
        request.provider_incarnation,
        request.journal_generation_id,
        request.operation_id,
        request.original_challenge,
        request.original_request_sha256,
        request.concrete_replay_identity_sha256,
        request.authority_snapshot_sha256,
        request.canonical_decision_sha256,
        request.trust_policy_sha256,
    ]
    .iter()
    .all(nonzero)
    {
        return Err(operation_error(
            "track_b_atomic_authority_operation_v1_request_commitment",
            "all exact operation, replay, decision, authority, and trust commitments are required",
        ));
    }
    Ok(())
}

fn request_digest(request: &AtomicAuthorityOperationRequestV1) -> OperationResult<[u8; 32]> {
    validate_request(request)?;
    let signer_key_version = request.signer_key_version.to_be_bytes();
    Ok(framed_digest(
        REQUEST_DOMAIN,
        &[
            POLICY_ID.as_bytes(),
            PROFILE.as_bytes(),
            ALGORITHM.as_bytes(),
            &S9_CONTRACT_SHA256,
            &S10_CONTRACT_SHA256,
            request.provider_profile_id.as_bytes(),
            request.authority_namespace_id.as_bytes(),
            request.tenant_id.as_bytes(),
            request.audience.as_bytes(),
            request.provider_cluster_id.as_bytes(),
            &request.provider_incarnation,
            &request.journal_generation_id,
            &request.operation_id,
            &request.original_challenge,
            &request.original_request_sha256,
            &request.concrete_replay_identity_sha256,
            &request.authority_snapshot_sha256,
            &request.canonical_decision_sha256,
            &request.trust_policy_sha256,
            request.signer_key_id.as_bytes(),
            &signer_key_version,
        ],
    ))
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
enum AtomicAuthorityOperationPersistentStateV1 {
    DecisionCommittedUnsigned,
    SignedCommitted,
}

impl AtomicAuthorityOperationPersistentStateV1 {
    fn label(self) -> &'static str {
        match self {
            Self::DecisionCommittedUnsigned => "DECISION_COMMITTED_UNSIGNED",
            Self::SignedCommitted => "SIGNED_COMMITTED",
        }
    }
}

#[derive(Clone)]
struct AtomicAuthorityOperationTrustPermitV1 {
    provider_profile_id: String,
    authority_namespace_id: String,
    tenant_id: String,
    audience: String,
    provider_cluster_id: String,
    provider_incarnation: [u8; 32],
    journal_generation_id: [u8; 32],
    signer_key_id: String,
    signer_key_version: u64,
    trust_policy_sha256: [u8; 32],
    minimum_leader_term: u64,
    minimum_operation_committed_revision: u64,
    ed25519_public_key: [u8; 32],
}

impl fmt::Debug for AtomicAuthorityOperationTrustPermitV1 {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        formatter
            .debug_struct("AtomicAuthorityOperationTrustPermitV1")
            .field("trust_anchor", &"[OWNER_PINNED_PUBLIC_KEY]")
            .finish_non_exhaustive()
    }
}

fn validate_permit(permit: &AtomicAuthorityOperationTrustPermitV1) -> OperationResult<()> {
    if !valid_label(&permit.provider_profile_id)
        || !valid_label(&permit.authority_namespace_id)
        || !valid_label(&permit.tenant_id)
        || !valid_label(&permit.audience)
        || !valid_label(&permit.provider_cluster_id)
        || !valid_label(&permit.signer_key_id)
        || permit.signer_key_version == 0
        || permit.minimum_leader_term == 0
        || permit.minimum_operation_committed_revision == 0
        || !nonzero(&permit.provider_incarnation)
        || !nonzero(&permit.journal_generation_id)
        || !nonzero(&permit.trust_policy_sha256)
        || !nonzero(&permit.ed25519_public_key)
    {
        return Err(operation_error(
            "track_b_atomic_authority_operation_v1_trust_permit",
            "owner-pinned scope, generation, signer, floors, and public key are required",
        ));
    }
    Ok(())
}

fn prepared_record_digest(
    request_sha256: &[u8; 32],
    leader_term: u64,
    operation_committed_revision: u64,
    record_sequence: u64,
) -> [u8; 32] {
    let leader_term = leader_term.to_be_bytes();
    let operation_committed_revision = operation_committed_revision.to_be_bytes();
    let record_sequence = record_sequence.to_be_bytes();
    framed_digest(
        PREPARED_RECORD_DOMAIN,
        &[
            POLICY_ID.as_bytes(),
            AtomicAuthorityOperationPersistentStateV1::DecisionCommittedUnsigned
                .label()
                .as_bytes(),
            request_sha256,
            &leader_term,
            &operation_committed_revision,
            &record_sequence,
        ],
    )
}

fn sign_job_id(
    prepared_record_sha256: &[u8; 32],
    signer_key_id: &str,
    signer_key_version: u64,
) -> [u8; 32] {
    let signer_key_version = signer_key_version.to_be_bytes();
    framed_digest(
        SIGN_JOB_DOMAIN,
        &[
            POLICY_ID.as_bytes(),
            prepared_record_sha256,
            signer_key_id.as_bytes(),
            &signer_key_version,
        ],
    )
}

fn stable_result_id(prepared_record_sha256: &[u8; 32], sign_job_id: &[u8; 32]) -> [u8; 32] {
    framed_digest(
        STABLE_RESULT_DOMAIN,
        &[POLICY_ID.as_bytes(), prepared_record_sha256, sign_job_id],
    )
}

fn decision_message(
    request: &AtomicAuthorityOperationRequestV1,
    request_sha256: &[u8; 32],
    leader_term: u64,
    operation_committed_revision: u64,
    record_sequence: u64,
    prepared_record_sha256: &[u8; 32],
    sign_job_id: &[u8; 32],
    stable_result_id: &[u8; 32],
) -> Vec<u8> {
    let leader_term = leader_term.to_be_bytes();
    let operation_committed_revision = operation_committed_revision.to_be_bytes();
    let record_sequence = record_sequence.to_be_bytes();
    let signer_key_version = request.signer_key_version.to_be_bytes();
    framed_message(
        DECISION_MESSAGE_DOMAIN,
        &[
            POLICY_ID.as_bytes(),
            PROFILE.as_bytes(),
            ALGORITHM.as_bytes(),
            &S9_CONTRACT_SHA256,
            &S10_CONTRACT_SHA256,
            request_sha256,
            &request.operation_id,
            &request.original_challenge,
            &request.original_request_sha256,
            &request.concrete_replay_identity_sha256,
            &request.authority_snapshot_sha256,
            &request.canonical_decision_sha256,
            request.provider_cluster_id.as_bytes(),
            &request.provider_incarnation,
            &request.journal_generation_id,
            &leader_term,
            &operation_committed_revision,
            &record_sequence,
            prepared_record_sha256,
            sign_job_id,
            stable_result_id,
            request.signer_key_id.as_bytes(),
            &signer_key_version,
            &request.trust_policy_sha256,
        ],
    )
}

/// A deterministic checksum of the synthetic journal's L2 row.
///
/// This value is deliberately not part of the Ed25519 message and is not an
/// authenticated database-persistence receipt. It exists only to make local
/// sequence-model drift visible in tests.
fn synthetic_l2_record_digest(
    stable_result_id: &[u8; 32],
    decision_message_sha256: &[u8; 32],
    signature: &[u8; 64],
    synthetic_l2_revision: u64,
) -> [u8; 32] {
    let synthetic_l2_revision = synthetic_l2_revision.to_be_bytes();
    framed_digest(
        SYNTHETIC_L2_RECORD_DOMAIN,
        &[
            POLICY_ID.as_bytes(),
            AtomicAuthorityOperationPersistentStateV1::SignedCommitted
                .label()
                .as_bytes(),
            stable_result_id,
            decision_message_sha256,
            signature,
            &synthetic_l2_revision,
        ],
    )
}

#[derive(Clone)]
struct SignedCommittedAuthorityOperationV1 {
    request_sha256: [u8; 32],
    state: AtomicAuthorityOperationPersistentStateV1,
    provider_cluster_id: String,
    provider_incarnation: [u8; 32],
    journal_generation_id: [u8; 32],
    leader_term: u64,
    operation_committed_revision: u64,
    record_sequence: u64,
    prepared_record_sha256: [u8; 32],
    sign_job_id: [u8; 32],
    stable_result_id: [u8; 32],
    decision_message_sha256: [u8; 32],
    signer_key_id: String,
    signer_key_version: u64,
    /// Unauthenticated metadata assigned by the synthetic journal at L2.
    synthetic_l2_revision: u64,
    ed25519_signature: [u8; 64],
    /// Public checksum, not an authenticated persistence receipt.
    synthetic_l2_record_sha256: [u8; 32],
}

impl fmt::Debug for SignedCommittedAuthorityOperationV1 {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        formatter
            .debug_struct("SignedCommittedAuthorityOperationV1")
            .field("state", &self.state)
            .field("authentication", &"[ED25519_REDACTED]")
            .finish_non_exhaustive()
    }
}

#[must_use]
struct VerifiedAtomicAuthorityOperationObservationV1 {
    stable_result_id: [u8; 32],
    decision_message_sha256: [u8; 32],
    operation_committed_revision: u64,
    record_sequence: u64,
}

impl fmt::Debug for VerifiedAtomicAuthorityOperationObservationV1 {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        formatter
            .debug_struct("VerifiedAtomicAuthorityOperationObservationV1")
            .field("scope", &"[PRIVATE_NON_ADMISSION_SEQUENCE_EVIDENCE]")
            .field(
                "operation_committed_revision",
                &self.operation_committed_revision,
            )
            .finish_non_exhaustive()
    }
}

fn verify_signed_committed_operation_v1(
    request: &AtomicAuthorityOperationRequestV1,
    permit: &AtomicAuthorityOperationTrustPermitV1,
    record: &SignedCommittedAuthorityOperationV1,
) -> OperationResult<VerifiedAtomicAuthorityOperationObservationV1> {
    validate_request(request)?;
    validate_permit(permit)?;
    if request.provider_profile_id != permit.provider_profile_id
        || request.authority_namespace_id != permit.authority_namespace_id
        || request.tenant_id != permit.tenant_id
        || request.audience != permit.audience
        || request.provider_cluster_id != permit.provider_cluster_id
        || request.provider_incarnation != permit.provider_incarnation
        || request.journal_generation_id != permit.journal_generation_id
        || request.signer_key_id != permit.signer_key_id
        || request.signer_key_version != permit.signer_key_version
        || request.trust_policy_sha256 != permit.trust_policy_sha256
    {
        return Err(operation_error(
            "track_b_atomic_authority_operation_v1_trust_scope",
            "request scope does not match independently pinned permit",
        ));
    }
    if !valid_label(&record.provider_cluster_id)
        || !valid_label(&record.signer_key_id)
        || record.state != AtomicAuthorityOperationPersistentStateV1::SignedCommitted
        || record.request_sha256 != request_digest(request)?
        || record.provider_cluster_id != request.provider_cluster_id
        || record.provider_incarnation != request.provider_incarnation
        || record.journal_generation_id != request.journal_generation_id
        || record.signer_key_id != request.signer_key_id
        || record.signer_key_version != request.signer_key_version
    {
        return Err(operation_error(
            "track_b_atomic_authority_operation_v1_record_binding",
            "signed record is not exactly bound to the request and persistent final state",
        ));
    }
    if record.leader_term < permit.minimum_leader_term
        || record.operation_committed_revision < permit.minimum_operation_committed_revision
        || record.operation_committed_revision == 0
        || record.record_sequence == 0
        || record.synthetic_l2_revision <= record.operation_committed_revision
    {
        return Err(operation_error(
            "track_b_atomic_authority_operation_v1_monotonic_floor",
            "provider term, L1 revision, sequence, and later L2 revision must be monotonic",
        ));
    }
    let expected_prepared = prepared_record_digest(
        &record.request_sha256,
        record.leader_term,
        record.operation_committed_revision,
        record.record_sequence,
    );
    let expected_sign_job = sign_job_id(
        &expected_prepared,
        &record.signer_key_id,
        record.signer_key_version,
    );
    let expected_stable_result = stable_result_id(&expected_prepared, &expected_sign_job);
    if record.prepared_record_sha256 != expected_prepared
        || record.sign_job_id != expected_sign_job
        || record.stable_result_id != expected_stable_result
    {
        return Err(operation_error(
            "track_b_atomic_authority_operation_v1_l1_binding",
            "L1 prepared record, sign job, or stable result identity drifted",
        ));
    }
    let message = decision_message(
        request,
        &record.request_sha256,
        record.leader_term,
        record.operation_committed_revision,
        record.record_sequence,
        &record.prepared_record_sha256,
        &record.sign_job_id,
        &record.stable_result_id,
    );
    if record.decision_message_sha256 != sha256_bytes(&message) {
        return Err(operation_error(
            "track_b_atomic_authority_operation_v1_message_binding",
            "stored decision message digest does not match exact frozen L1 bytes",
        ));
    }
    UnparsedPublicKey::new(&ED25519, permit.ed25519_public_key)
        .verify(&message, &record.ed25519_signature)
        .map_err(|_| {
            operation_error(
                "track_b_atomic_authority_operation_v1_signature",
                "exact-version signature does not authenticate frozen decision bytes",
            )
        })?;
    // This only checks internal checksum consistency. L2 revision and row
    // persistence are not authenticated by the L1 Ed25519 signature.
    let expected_l2_record = synthetic_l2_record_digest(
        &record.stable_result_id,
        &record.decision_message_sha256,
        &record.ed25519_signature,
        record.synthetic_l2_revision,
    );
    if record.synthetic_l2_record_sha256 != expected_l2_record {
        return Err(operation_error(
            "track_b_atomic_authority_operation_v1_synthetic_l2_record",
            "synthetic L2 checksum does not match its unauthenticated row metadata",
        ));
    }
    Ok(VerifiedAtomicAuthorityOperationObservationV1 {
        stable_result_id: record.stable_result_id,
        decision_message_sha256: record.decision_message_sha256,
        operation_committed_revision: record.operation_committed_revision,
        record_sequence: record.record_sequence,
    })
}

#[derive(Clone, Copy, PartialEq, Eq)]
struct AtomicAuthorityOperationL1WitnessV1 {
    operation_id: [u8; 32],
    request_sha256: [u8; 32],
    journal_generation_id: [u8; 32],
    prepared_record_sha256: [u8; 32],
    sign_job_id: [u8; 32],
    stable_result_id: [u8; 32],
    operation_committed_revision: u64,
    record_sequence: u64,
}

impl fmt::Debug for AtomicAuthorityOperationL1WitnessV1 {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        formatter
            .debug_struct("AtomicAuthorityOperationL1WitnessV1")
            .field("scope", &"[PRIVATE_EXACT_L1_WITNESS]")
            .field(
                "operation_committed_revision",
                &self.operation_committed_revision,
            )
            .field("record_sequence", &self.record_sequence)
            .finish_non_exhaustive()
    }
}

#[derive(Clone)]
enum AtomicAuthorityOperationLookupOutcomeV1 {
    NotFound,
    Pending(AtomicAuthorityOperationL1WitnessV1),
    Committed(SignedCommittedAuthorityOperationV1),
}

impl fmt::Debug for AtomicAuthorityOperationLookupOutcomeV1 {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        formatter.write_str(match self {
            Self::NotFound => "NotFound",
            Self::Pending(_) => "Pending([PRIVATE_L1_WITNESS])",
            Self::Committed(_) => "Committed([SIGNED_RECORD_REDACTED])",
        })
    }
}

mod atomic_operation_provider_seal {
    pub(super) trait Sealed {}
}

trait ExternalAtomicAuthorityOperationProviderV1: atomic_operation_provider_seal::Sealed {
    fn begin_exact_once(
        &self,
        request: &AtomicAuthorityOperationRequestV1,
    ) -> OperationResult<AtomicAuthorityOperationL1WitnessV1>;

    fn lookup_exact(
        &self,
        request: &AtomicAuthorityOperationRequestV1,
        permit: &AtomicAuthorityOperationTrustPermitV1,
    ) -> OperationResult<AtomicAuthorityOperationLookupOutcomeV1>;

    fn resume_exact_from_l1(
        &self,
        request: &AtomicAuthorityOperationRequestV1,
        witness: &AtomicAuthorityOperationL1WitnessV1,
        permit: &AtomicAuthorityOperationTrustPermitV1,
    ) -> OperationResult<VerifiedAtomicAuthorityOperationObservationV1>;
}

#[cfg(test)]
mod tests {
    use super::*;
    use ring::signature::{Ed25519KeyPair, KeyPair};
    use std::collections::BTreeMap;
    use std::sync::{Arc, Mutex};

    const RFC8032_SEED: [u8; 32] = [
        0x9d, 0x61, 0xb1, 0x9d, 0xef, 0xfd, 0x5a, 0x60, 0xba, 0x84, 0x4a, 0xf4, 0x92, 0xec, 0x2c,
        0xc4, 0x44, 0x49, 0xc5, 0x69, 0x7b, 0x32, 0x69, 0x19, 0x70, 0x3b, 0xac, 0x03, 0x1c, 0xae,
        0x7f, 0x60,
    ];
    const RFC8032_PUBLIC_KEY: [u8; 32] = [
        0xd7, 0x5a, 0x98, 0x01, 0x82, 0xb1, 0x0a, 0xb7, 0xd5, 0x4b, 0xfe, 0xd3, 0xc9, 0x64, 0x07,
        0x3a, 0x0e, 0xe1, 0x72, 0xf3, 0xda, 0xa6, 0x23, 0x25, 0xaf, 0x02, 0x1a, 0x68, 0xf7, 0x07,
        0x51, 0x1a,
    ];

    fn repeated(value: u8) -> [u8; 32] {
        [value; 32]
    }

    fn request() -> AtomicAuthorityOperationRequestV1 {
        AtomicAuthorityOperationRequestV1 {
            provider_profile_id: "owner-selected-provider-v1".into(),
            authority_namespace_id: "track-b-authority".into(),
            tenant_id: "tenant-a".into(),
            audience: "agent-bridge-store".into(),
            provider_cluster_id: "authority-cluster-a".into(),
            provider_incarnation: repeated(0x61),
            journal_generation_id: repeated(0x72),
            operation_id: repeated(0x21),
            original_challenge: repeated(0x22),
            original_request_sha256: repeated(0x23),
            concrete_replay_identity_sha256: repeated(0x25),
            authority_snapshot_sha256: repeated(0x26),
            canonical_decision_sha256: repeated(0x24),
            trust_policy_sha256: repeated(0x71),
            signer_key_id: "authority-signer".into(),
            signer_key_version: 3,
        }
    }

    fn key_pair() -> Ed25519KeyPair {
        Ed25519KeyPair::from_seed_unchecked(&RFC8032_SEED).expect("RFC8032 test key")
    }

    fn permit() -> AtomicAuthorityOperationTrustPermitV1 {
        AtomicAuthorityOperationTrustPermitV1 {
            provider_profile_id: "owner-selected-provider-v1".into(),
            authority_namespace_id: "track-b-authority".into(),
            tenant_id: "tenant-a".into(),
            audience: "agent-bridge-store".into(),
            provider_cluster_id: "authority-cluster-a".into(),
            provider_incarnation: repeated(0x61),
            journal_generation_id: repeated(0x72),
            signer_key_id: "authority-signer".into(),
            signer_key_version: 3,
            trust_policy_sha256: repeated(0x71),
            minimum_leader_term: 7,
            minimum_operation_committed_revision: 41,
            ed25519_public_key: RFC8032_PUBLIC_KEY,
        }
    }

    #[derive(Clone)]
    struct SyntheticRecordV1 {
        request: AtomicAuthorityOperationRequestV1,
        state: AtomicAuthorityOperationPersistentStateV1,
        request_sha256: [u8; 32],
        leader_term: u64,
        operation_committed_revision: u64,
        record_sequence: u64,
        prepared_record_sha256: [u8; 32],
        sign_job_id: [u8; 32],
        stable_result_id: [u8; 32],
        decision_message: Vec<u8>,
        signed: Option<SignedCommittedAuthorityOperationV1>,
    }

    #[derive(Clone)]
    struct SyntheticJournalV1 {
        generation_id: [u8; 32],
        provider_cluster_id: String,
        provider_incarnation: [u8; 32],
        authority_snapshot_sha256: [u8; 32],
        canonical_decision_sha256: [u8; 32],
        trust_policy_sha256: [u8; 32],
        signer_key_id: String,
        signer_key_version: u64,
        revision: u64,
        next_sequence: u64,
        leader_term: u64,
        revoked: bool,
        operations: BTreeMap<[u8; 32], SyntheticRecordV1>,
        challenges: BTreeMap<[u8; 32], [u8; 32]>,
        replay_identities: BTreeMap<[u8; 32], [u8; 32]>,
    }

    impl SyntheticJournalV1 {
        fn new() -> Self {
            Self {
                generation_id: repeated(0x72),
                provider_cluster_id: "authority-cluster-a".into(),
                provider_incarnation: repeated(0x61),
                authority_snapshot_sha256: repeated(0x26),
                canonical_decision_sha256: repeated(0x24),
                trust_policy_sha256: repeated(0x71),
                signer_key_id: "authority-signer".into(),
                signer_key_version: 3,
                revision: 40,
                next_sequence: 9,
                leader_term: 7,
                revoked: false,
                operations: BTreeMap::new(),
                challenges: BTreeMap::new(),
                replay_identities: BTreeMap::new(),
            }
        }
    }

    #[derive(Clone, Copy)]
    enum L1CutV1 {
        None,
        BeforeCommit,
        AckLostAfterCommit,
    }

    #[derive(Clone, Copy)]
    enum L2CutV1 {
        None,
        SignerTimeoutAfterExecution,
        AfterSignatureBeforeCommit,
        BeforeCommit,
        AckLostAfterCommit,
    }

    #[derive(Clone, Copy)]
    enum SyntheticSignerFaultV1 {
        None,
        WrongKeyId,
        WrongKeyVersion,
        WrongMessageDigest,
        InvalidSignature,
    }

    struct SyntheticSignerResponseV1 {
        signer_key_id: String,
        signer_key_version: u64,
        message_sha256: [u8; 32],
        signature: [u8; 64],
    }

    struct SyntheticSignerV1 {
        signer_key_id: String,
        signer_key_version: u64,
        key_pair: Ed25519KeyPair,
        calls: usize,
        next_fault: SyntheticSignerFaultV1,
    }

    impl SyntheticSignerV1 {
        fn new() -> Self {
            Self {
                signer_key_id: "authority-signer".into(),
                signer_key_version: 3,
                key_pair: key_pair(),
                calls: 0,
                next_fault: SyntheticSignerFaultV1::None,
            }
        }

        fn sign(&mut self, message: &[u8]) -> SyntheticSignerResponseV1 {
            self.calls += 1;
            let mut response = SyntheticSignerResponseV1 {
                signer_key_id: self.signer_key_id.clone(),
                signer_key_version: self.signer_key_version,
                message_sha256: sha256_bytes(message),
                signature: self
                    .key_pair
                    .sign(message)
                    .as_ref()
                    .try_into()
                    .expect("64 bytes"),
            };
            match self.next_fault {
                SyntheticSignerFaultV1::None => {}
                SyntheticSignerFaultV1::WrongKeyId => {
                    response.signer_key_id = "other-signer".into();
                }
                SyntheticSignerFaultV1::WrongKeyVersion => {
                    response.signer_key_version = response.signer_key_version.saturating_add(1);
                }
                SyntheticSignerFaultV1::WrongMessageDigest => {
                    response.message_sha256[0] ^= 1;
                }
                SyntheticSignerFaultV1::InvalidSignature => {
                    response.signature[0] ^= 1;
                }
            }
            self.next_fault = SyntheticSignerFaultV1::None;
            response
        }
    }

    #[derive(Clone)]
    struct SyntheticAtomicAuthorityOperationV1 {
        journal: Arc<Mutex<SyntheticJournalV1>>,
        signer: Arc<Mutex<SyntheticSignerV1>>,
    }

    impl atomic_operation_provider_seal::Sealed for SyntheticAtomicAuthorityOperationV1 {}

    impl SyntheticAtomicAuthorityOperationV1 {
        fn new() -> Self {
            Self {
                journal: Arc::new(Mutex::new(SyntheticJournalV1::new())),
                signer: Arc::new(Mutex::new(SyntheticSignerV1::new())),
            }
        }

        fn validate_journal_request(
            journal: &SyntheticJournalV1,
            request: &AtomicAuthorityOperationRequestV1,
        ) -> OperationResult<()> {
            if request.journal_generation_id != journal.generation_id
                || request.provider_cluster_id != journal.provider_cluster_id
                || request.provider_incarnation != journal.provider_incarnation
                || request.authority_snapshot_sha256 != journal.authority_snapshot_sha256
                || request.canonical_decision_sha256 != journal.canonical_decision_sha256
                || request.trust_policy_sha256 != journal.trust_policy_sha256
                || request.signer_key_id != journal.signer_key_id
                || request.signer_key_version != journal.signer_key_version
            {
                return Err(operation_error(
                    "track_b_atomic_authority_operation_v1_journal_identity",
                    "L1 request does not match the journal-owned generation, authority decision, trust policy, and immutable signer",
                ));
            }
            Ok(())
        }

        fn witness(record: &SyntheticRecordV1) -> AtomicAuthorityOperationL1WitnessV1 {
            AtomicAuthorityOperationL1WitnessV1 {
                operation_id: record.request.operation_id,
                request_sha256: record.request_sha256,
                journal_generation_id: record.request.journal_generation_id,
                prepared_record_sha256: record.prepared_record_sha256,
                sign_job_id: record.sign_job_id,
                stable_result_id: record.stable_result_id,
                operation_committed_revision: record.operation_committed_revision,
                record_sequence: record.record_sequence,
            }
        }

        fn validate_witness(
            record: &SyntheticRecordV1,
            witness: &AtomicAuthorityOperationL1WitnessV1,
        ) -> OperationResult<()> {
            if *witness != Self::witness(record) {
                return Err(operation_error(
                    "track_b_atomic_authority_operation_v1_l1_witness",
                    "resume-only witness does not bind the exact immutable L1 record",
                ));
            }
            Ok(())
        }

        fn validate_record_invariants(record: &SyntheticRecordV1) -> OperationResult<()> {
            let expected_request = request_digest(&record.request)?;
            let expected_prepared = prepared_record_digest(
                &expected_request,
                record.leader_term,
                record.operation_committed_revision,
                record.record_sequence,
            );
            let expected_job = sign_job_id(
                &expected_prepared,
                &record.request.signer_key_id,
                record.request.signer_key_version,
            );
            let expected_stable = stable_result_id(&expected_prepared, &expected_job);
            let expected_message = decision_message(
                &record.request,
                &expected_request,
                record.leader_term,
                record.operation_committed_revision,
                record.record_sequence,
                &expected_prepared,
                &expected_job,
                &expected_stable,
            );
            if record.request_sha256 != expected_request
                || record.prepared_record_sha256 != expected_prepared
                || record.sign_job_id != expected_job
                || record.stable_result_id != expected_stable
                || record.decision_message != expected_message
            {
                return Err(operation_error(
                    "track_b_atomic_authority_operation_v1_impossible_record",
                    "stored L1 fields are internally inconsistent",
                ));
            }
            match (record.state, record.signed.as_ref()) {
                (AtomicAuthorityOperationPersistentStateV1::DecisionCommittedUnsigned, None) => {
                    Ok(())
                }
                (AtomicAuthorityOperationPersistentStateV1::SignedCommitted, Some(signed))
                    if signed.request_sha256 == record.request_sha256
                        && signed.prepared_record_sha256 == record.prepared_record_sha256
                        && signed.sign_job_id == record.sign_job_id
                        && signed.stable_result_id == record.stable_result_id
                        && signed.operation_committed_revision
                            == record.operation_committed_revision
                        && signed.record_sequence == record.record_sequence =>
                {
                    Ok(())
                }
                _ => Err(operation_error(
                    "track_b_atomic_authority_operation_v1_impossible_state",
                    "persistent phase and signed payload violate the two-state invariant",
                )),
            }
        }

        fn validate_record_indexes(
            journal: &SyntheticJournalV1,
            record: &SyntheticRecordV1,
        ) -> OperationResult<()> {
            if journal.challenges.get(&record.request.original_challenge)
                != Some(&record.request.operation_id)
                || journal
                    .replay_identities
                    .get(&record.request.concrete_replay_identity_sha256)
                    != Some(&record.request.operation_id)
            {
                return Err(operation_error(
                    "track_b_atomic_authority_operation_v1_impossible_index",
                    "operation, challenge, and replay-consume indexes are not atomic",
                ));
            }
            Ok(())
        }

        fn verify_existing_signed(
            request: &AtomicAuthorityOperationRequestV1,
            permit: &AtomicAuthorityOperationTrustPermitV1,
            signed: &SignedCommittedAuthorityOperationV1,
        ) -> OperationResult<SignedCommittedAuthorityOperationV1> {
            let _ = verify_signed_committed_operation_v1(request, permit, signed)?;
            Ok(signed.clone())
        }

        fn register_with_cut(
            &self,
            request: &AtomicAuthorityOperationRequestV1,
            cut: L1CutV1,
        ) -> OperationResult<AtomicAuthorityOperationL1WitnessV1> {
            validate_request(request)?;
            let mut journal = self.journal.lock().expect("journal lock");
            Self::validate_journal_request(&journal, request)?;
            if let Some(existing) = journal.operations.get(&request.operation_id) {
                if existing.request == *request {
                    Self::validate_record_invariants(existing)?;
                    Self::validate_record_indexes(&journal, existing)?;
                    return Err(operation_error(
                        "track_b_atomic_authority_operation_v1_already_exists_use_lookup",
                        "begin is create-only; recover the exact existing record with lookup and its typed L1 witness",
                    ));
                }
                return Err(operation_error(
                    "track_b_atomic_authority_operation_v1_operation_conflict",
                    "operation ID is already bound to a different exact tuple",
                ));
            }
            if journal.revoked {
                return Err(operation_error(
                    "track_b_atomic_authority_operation_v1_revoked_before_l1",
                    "authority snapshot was revoked before L1",
                ));
            }
            if journal.challenges.contains_key(&request.original_challenge)
                || journal
                    .replay_identities
                    .contains_key(&request.concrete_replay_identity_sha256)
            {
                return Err(operation_error(
                    "track_b_atomic_authority_operation_v1_unique_consume_conflict",
                    "challenge or concrete replay identity is already consumed",
                ));
            }
            let mut staged = journal.clone();
            staged.revision = staged.revision.checked_add(1).ok_or_else(|| {
                operation_error(
                    "track_b_atomic_authority_operation_v1_revision_overflow",
                    "L1 revision overflowed",
                )
            })?;
            let sequence = staged.next_sequence;
            staged.next_sequence = staged.next_sequence.checked_add(1).ok_or_else(|| {
                operation_error(
                    "track_b_atomic_authority_operation_v1_sequence_overflow",
                    "record sequence overflowed",
                )
            })?;
            let request_sha256 = request_digest(request)?;
            let prepared = prepared_record_digest(
                &request_sha256,
                staged.leader_term,
                staged.revision,
                sequence,
            );
            let job = sign_job_id(
                &prepared,
                &request.signer_key_id,
                request.signer_key_version,
            );
            let stable = stable_result_id(&prepared, &job);
            let message = decision_message(
                request,
                &request_sha256,
                staged.leader_term,
                staged.revision,
                sequence,
                &prepared,
                &job,
                &stable,
            );
            staged
                .challenges
                .insert(request.original_challenge, request.operation_id);
            staged.replay_identities.insert(
                request.concrete_replay_identity_sha256,
                request.operation_id,
            );
            staged.operations.insert(
                request.operation_id,
                SyntheticRecordV1 {
                    request: request.clone(),
                    state: AtomicAuthorityOperationPersistentStateV1::DecisionCommittedUnsigned,
                    request_sha256,
                    leader_term: staged.leader_term,
                    operation_committed_revision: staged.revision,
                    record_sequence: sequence,
                    prepared_record_sha256: prepared,
                    sign_job_id: job,
                    stable_result_id: stable,
                    decision_message: message,
                    signed: None,
                },
            );
            if matches!(cut, L1CutV1::BeforeCommit) {
                return Err(operation_error(
                    "track_b_atomic_authority_operation_v1_l1_indeterminate",
                    "synthetic cut before L1 commit",
                ));
            }
            *journal = staged;
            if matches!(cut, L1CutV1::AckLostAfterCommit) {
                return Err(operation_error(
                    "track_b_atomic_authority_operation_v1_l1_ack_lost",
                    "synthetic L1 commit acknowledgement was lost",
                ));
            }
            Ok(Self::witness(
                journal
                    .operations
                    .get(&request.operation_id)
                    .ok_or_else(|| {
                        operation_error(
                            "track_b_atomic_authority_operation_v1_impossible_state",
                            "L1 commit completed without its operation record",
                        )
                    })?,
            ))
        }

        fn finalize_with_cut(
            &self,
            request: &AtomicAuthorityOperationRequestV1,
            witness: &AtomicAuthorityOperationL1WitnessV1,
            permit: &AtomicAuthorityOperationTrustPermitV1,
            cut: L2CutV1,
        ) -> OperationResult<SignedCommittedAuthorityOperationV1> {
            validate_request(request)?;
            validate_permit(permit)?;
            if request.provider_profile_id != permit.provider_profile_id
                || request.authority_namespace_id != permit.authority_namespace_id
                || request.tenant_id != permit.tenant_id
                || request.audience != permit.audience
                || request.provider_cluster_id != permit.provider_cluster_id
                || request.provider_incarnation != permit.provider_incarnation
                || request.journal_generation_id != permit.journal_generation_id
                || request.signer_key_id != permit.signer_key_id
                || request.signer_key_version != permit.signer_key_version
                || request.trust_policy_sha256 != permit.trust_policy_sha256
            {
                return Err(operation_error(
                    "track_b_atomic_authority_operation_v1_trust_scope",
                    "signing resume cannot change provider scope, trust, or exact key version",
                ));
            }
            let snapshot = {
                let journal = self.journal.lock().expect("journal lock");
                Self::validate_journal_request(&journal, request)?;
                let record = journal
                    .operations
                    .get(&request.operation_id)
                    .ok_or_else(|| {
                        operation_error(
                            "track_b_atomic_authority_operation_v1_rollback_indeterminate",
                            "resume-only L1 witness became NOT_FOUND; rollback or journal loss is possible",
                        )
                    })?;
                if record.request != *request {
                    return Err(operation_error(
                        "track_b_atomic_authority_operation_v1_operation_conflict",
                        "stored operation tuple differs",
                    ));
                }
                Self::validate_record_invariants(record)?;
                Self::validate_record_indexes(&journal, record)?;
                Self::validate_witness(record, witness)?;
                if let Some(signed) = &record.signed {
                    return Self::verify_existing_signed(request, permit, signed);
                }
                record.clone()
            };
            let signer_response = self
                .signer
                .lock()
                .expect("signer lock")
                .sign(&snapshot.decision_message);
            if matches!(cut, L2CutV1::SignerTimeoutAfterExecution) {
                return Err(operation_error(
                    "track_b_atomic_authority_operation_v1_signer_indeterminate",
                    "signer may have executed but its response was lost",
                ));
            }
            if signer_response.signer_key_id != request.signer_key_id
                || signer_response.signer_key_version != request.signer_key_version
                || signer_response.message_sha256 != sha256_bytes(&snapshot.decision_message)
            {
                return Err(operation_error(
                    "track_b_atomic_authority_operation_v1_signer_binding",
                    "signer response changed immutable key identity, version, or exact message digest",
                ));
            }
            UnparsedPublicKey::new(&ED25519, permit.ed25519_public_key)
                .verify(&snapshot.decision_message, &signer_response.signature)
                .map_err(|_| {
                    operation_error(
                        "track_b_atomic_authority_operation_v1_signature",
                        "signer response failed local exact-message verification",
                    )
                })?;
            if matches!(cut, L2CutV1::AfterSignatureBeforeCommit) {
                return Err(operation_error(
                    "track_b_atomic_authority_operation_v1_signature_not_persisted",
                    "verified signature was lost before L2",
                ));
            }
            let mut journal = self.journal.lock().expect("journal lock");
            Self::validate_journal_request(&journal, request)?;
            if let Some(existing_record) = journal.operations.get(&request.operation_id) {
                Self::validate_record_invariants(existing_record)?;
                Self::validate_record_indexes(&journal, existing_record)?;
                Self::validate_witness(existing_record, witness)?;
                if let Some(existing) = &existing_record.signed {
                    let existing = Self::verify_existing_signed(request, permit, existing)?;
                    if existing.ed25519_signature != signer_response.signature {
                        return Err(operation_error(
                            "track_b_atomic_authority_operation_v1_signer_equivocation",
                            "concurrent exact sign jobs returned different canonical signatures",
                        ));
                    }
                    return Ok(existing);
                }
            }
            let mut staged = journal.clone();
            staged.revision = staged.revision.checked_add(1).ok_or_else(|| {
                operation_error(
                    "track_b_atomic_authority_operation_v1_revision_overflow",
                    "L2 revision overflowed",
                )
            })?;
            let l2_revision = staged.revision;
            let current = staged
                .operations
                .get_mut(&request.operation_id)
                .ok_or_else(|| {
                    operation_error(
                        "track_b_atomic_authority_operation_v1_rollback_indeterminate",
                        "L1 record disappeared before L2 CAS",
                    )
                })?;
            Self::validate_record_invariants(current)?;
            Self::validate_witness(current, witness)?;
            if current.request != snapshot.request
                || current.state
                    != AtomicAuthorityOperationPersistentStateV1::DecisionCommittedUnsigned
                || current.prepared_record_sha256 != snapshot.prepared_record_sha256
                || current.sign_job_id != snapshot.sign_job_id
                || current.decision_message != snapshot.decision_message
                || current.request.signer_key_version != request.signer_key_version
            {
                return Err(operation_error(
                    "track_b_atomic_authority_operation_v1_l2_cas_conflict",
                    "L2 exact prepared-record CAS failed",
                ));
            }
            let decision_message_sha256 = sha256_bytes(&snapshot.decision_message);
            let synthetic_l2_record_sha256 = synthetic_l2_record_digest(
                &snapshot.stable_result_id,
                &decision_message_sha256,
                &signer_response.signature,
                l2_revision,
            );
            let signed = SignedCommittedAuthorityOperationV1 {
                request_sha256: snapshot.request_sha256,
                state: AtomicAuthorityOperationPersistentStateV1::SignedCommitted,
                provider_cluster_id: request.provider_cluster_id.clone(),
                provider_incarnation: request.provider_incarnation,
                journal_generation_id: request.journal_generation_id,
                leader_term: snapshot.leader_term,
                operation_committed_revision: snapshot.operation_committed_revision,
                record_sequence: snapshot.record_sequence,
                prepared_record_sha256: snapshot.prepared_record_sha256,
                sign_job_id: snapshot.sign_job_id,
                stable_result_id: snapshot.stable_result_id,
                decision_message_sha256,
                signer_key_id: request.signer_key_id.clone(),
                signer_key_version: request.signer_key_version,
                synthetic_l2_revision: l2_revision,
                ed25519_signature: signer_response.signature,
                synthetic_l2_record_sha256,
            };
            current.state = AtomicAuthorityOperationPersistentStateV1::SignedCommitted;
            current.signed = Some(signed.clone());
            if matches!(cut, L2CutV1::BeforeCommit) {
                return Err(operation_error(
                    "track_b_atomic_authority_operation_v1_l2_indeterminate",
                    "synthetic cut before L2 commit",
                ));
            }
            *journal = staged;
            if matches!(cut, L2CutV1::AckLostAfterCommit) {
                return Err(operation_error(
                    "track_b_atomic_authority_operation_v1_l2_ack_lost",
                    "synthetic L2 commit acknowledgement was lost",
                ));
            }
            Ok(signed)
        }

        fn lookup_exact_outcome(
            &self,
            request: &AtomicAuthorityOperationRequestV1,
            permit: &AtomicAuthorityOperationTrustPermitV1,
        ) -> OperationResult<AtomicAuthorityOperationLookupOutcomeV1> {
            validate_request(request)?;
            validate_permit(permit)?;
            if request.provider_profile_id != permit.provider_profile_id
                || request.authority_namespace_id != permit.authority_namespace_id
                || request.tenant_id != permit.tenant_id
                || request.audience != permit.audience
                || request.provider_cluster_id != permit.provider_cluster_id
                || request.provider_incarnation != permit.provider_incarnation
                || request.journal_generation_id != permit.journal_generation_id
                || request.signer_key_id != permit.signer_key_id
                || request.signer_key_version != permit.signer_key_version
                || request.trust_policy_sha256 != permit.trust_policy_sha256
            {
                return Err(operation_error(
                    "track_b_atomic_authority_operation_v1_trust_scope",
                    "lookup scope does not match independently pinned permit",
                ));
            }
            let journal = self.journal.lock().expect("journal lock");
            Self::validate_journal_request(&journal, request)?;
            let Some(record) = journal.operations.get(&request.operation_id) else {
                return Ok(AtomicAuthorityOperationLookupOutcomeV1::NotFound);
            };
            if record.request != *request {
                return Err(operation_error(
                    "track_b_atomic_authority_operation_v1_operation_conflict",
                    "lookup tuple differs from stored operation",
                ));
            }
            Self::validate_record_invariants(record)?;
            Self::validate_record_indexes(&journal, record)?;
            match &record.signed {
                None => Ok(AtomicAuthorityOperationLookupOutcomeV1::Pending(
                    Self::witness(record),
                )),
                Some(signed) => Ok(AtomicAuthorityOperationLookupOutcomeV1::Committed(
                    Self::verify_existing_signed(request, permit, signed)?,
                )),
            }
        }

        fn lookup_with_l1_witness(
            &self,
            request: &AtomicAuthorityOperationRequestV1,
            permit: &AtomicAuthorityOperationTrustPermitV1,
            witness: &AtomicAuthorityOperationL1WitnessV1,
        ) -> OperationResult<AtomicAuthorityOperationLookupOutcomeV1> {
            let result = self.lookup_exact_outcome(request, permit)?;
            match &result {
                AtomicAuthorityOperationLookupOutcomeV1::NotFound => Err(operation_error(
                    "track_b_atomic_authority_operation_v1_rollback_indeterminate",
                    "a retained L1 witness became NOT_FOUND; rollback or journal loss is possible",
                )),
                AtomicAuthorityOperationLookupOutcomeV1::Pending(current) if current != witness => {
                    Err(operation_error(
                        "track_b_atomic_authority_operation_v1_l1_witness",
                        "pending lookup returned a different immutable L1 witness",
                    ))
                }
                AtomicAuthorityOperationLookupOutcomeV1::Committed(signed) => {
                    let current = AtomicAuthorityOperationL1WitnessV1 {
                        operation_id: request.operation_id,
                        request_sha256: signed.request_sha256,
                        journal_generation_id: signed.journal_generation_id,
                        prepared_record_sha256: signed.prepared_record_sha256,
                        sign_job_id: signed.sign_job_id,
                        stable_result_id: signed.stable_result_id,
                        operation_committed_revision: signed.operation_committed_revision,
                        record_sequence: signed.record_sequence,
                    };
                    if current != *witness {
                        return Err(operation_error(
                            "track_b_atomic_authority_operation_v1_l1_witness",
                            "committed lookup returned a different immutable L1 witness",
                        ));
                    }
                    Ok(result)
                }
                _ => Ok(result),
            }
        }

        fn signer_calls(&self) -> usize {
            self.signer.lock().expect("signer lock").calls
        }

        fn set_next_signer_fault(&self, fault: SyntheticSignerFaultV1) {
            self.signer.lock().expect("signer lock").next_fault = fault;
        }
    }

    impl ExternalAtomicAuthorityOperationProviderV1 for SyntheticAtomicAuthorityOperationV1 {
        fn begin_exact_once(
            &self,
            request: &AtomicAuthorityOperationRequestV1,
        ) -> OperationResult<AtomicAuthorityOperationL1WitnessV1> {
            self.register_with_cut(request, L1CutV1::None)
        }

        fn lookup_exact(
            &self,
            request: &AtomicAuthorityOperationRequestV1,
            permit: &AtomicAuthorityOperationTrustPermitV1,
        ) -> OperationResult<AtomicAuthorityOperationLookupOutcomeV1> {
            self.lookup_exact_outcome(request, permit)
        }

        fn resume_exact_from_l1(
            &self,
            request: &AtomicAuthorityOperationRequestV1,
            witness: &AtomicAuthorityOperationL1WitnessV1,
            permit: &AtomicAuthorityOperationTrustPermitV1,
        ) -> OperationResult<VerifiedAtomicAuthorityOperationObservationV1> {
            let signed = self.finalize_with_cut(request, witness, permit, L2CutV1::None)?;
            verify_signed_committed_operation_v1(request, permit, &signed)
        }
    }

    fn prepare(
        provider: &SyntheticAtomicAuthorityOperationV1,
    ) -> AtomicAuthorityOperationL1WitnessV1 {
        provider
            .register_with_cut(&request(), L1CutV1::None)
            .expect("L1")
    }

    fn hex(bytes: &[u8]) -> String {
        bytes.iter().map(|byte| format!("{byte:02x}")).collect()
    }

    #[test]
    fn s11_known_answer_framing_and_ed25519_are_deterministic() {
        let provider = SyntheticAtomicAuthorityOperationV1::new();
        prepare(&provider);
        let record = provider
            .journal
            .lock()
            .expect("journal")
            .operations
            .get(&request().operation_id)
            .expect("prepared")
            .clone();
        assert_eq!(key_pair().public_key().as_ref(), RFC8032_PUBLIC_KEY);
        let one = key_pair().sign(&record.decision_message);
        let two = key_pair().sign(&record.decision_message);
        assert_eq!(one.as_ref(), two.as_ref());
        assert_ne!(record.prepared_record_sha256, ZERO_COMMITMENT);
        assert_ne!(record.sign_job_id, ZERO_COMMITMENT);
        assert_ne!(sha256_bytes(&record.decision_message), ZERO_COMMITMENT);
        let signed = provider
            .finalize_with_cut(
                &request(),
                &SyntheticAtomicAuthorityOperationV1::witness(&record),
                &permit(),
                L2CutV1::None,
            )
            .expect("signed vector");
        assert_eq!(
            hex(&record.request_sha256),
            "fcb700d5ae175ffdc4ee69a32fb08a18d5d006c5b6dc7ae82aaf00672c7c1ef9"
        );
        assert_eq!(
            hex(&record.prepared_record_sha256),
            "4a1233c6612d56c12aaa814b8e096e094a42d9fa274030491aa4a2e2c80e71b1"
        );
        assert_eq!(
            hex(&record.sign_job_id),
            "d1a3d0bdb760505d8b2bada0cb65b1e67bb66b2af9a8ff4c0dd520e980e471f3"
        );
        assert_eq!(
            hex(&record.stable_result_id),
            "b88ce460d478843d732e4e364879c6f25001f5ba7fadfea3e00f4e20f455d5a2"
        );
        assert_eq!(
            hex(&sha256_bytes(&record.decision_message)),
            "30118775cea7d550e7475d33e5dd6c6bc01914cf692a6661a65fed61234700f8"
        );
        assert_eq!(
            hex(&signed.ed25519_signature),
            "f27f0528e75303027b00e8bacc7098d54f9de3aa1b1510179398a337d136d5ae1b72e579b0482b5d30722dc5a33425b54f4edecf165320c3862cae98c01b3303"
        );
        assert_eq!(
            hex(&signed.synthetic_l2_record_sha256),
            "cc44eae74a55863acf469fa941478a35f086a085d44435e0472a991b1136020c"
        );
    }

    #[test]
    fn s11_l1_atomically_reserves_operation_challenge_and_replay_identity() {
        let provider = SyntheticAtomicAuthorityOperationV1::new();
        prepare(&provider);
        let journal = provider.journal.lock().expect("journal");
        assert_eq!(journal.operations.len(), 1);
        assert_eq!(journal.challenges.len(), 1);
        assert_eq!(journal.replay_identities.len(), 1);
        assert_eq!(journal.revision, 41);
    }

    #[test]
    fn s11_l1_precommit_cut_leaves_every_index_absent() {
        let provider = SyntheticAtomicAuthorityOperationV1::new();
        assert_eq!(
            provider
                .register_with_cut(&request(), L1CutV1::BeforeCommit)
                .expect_err("cut")
                .code(),
            "track_b_atomic_authority_operation_v1_l1_indeterminate"
        );
        let journal = provider.journal.lock().expect("journal");
        assert!(journal.operations.is_empty());
        assert!(journal.challenges.is_empty());
        assert!(journal.replay_identities.is_empty());
    }

    #[test]
    fn s11_l1_ack_loss_is_recovered_by_exact_resume_without_second_consume() {
        let provider = SyntheticAtomicAuthorityOperationV1::new();
        provider
            .register_with_cut(&request(), L1CutV1::AckLostAfterCommit)
            .expect_err("ack lost");
        let witness = match provider
            .lookup_exact(&request(), &permit())
            .expect("lookup")
        {
            AtomicAuthorityOperationLookupOutcomeV1::Pending(witness) => witness,
            _ => panic!("L1 ack loss must recover the explicit pending record"),
        };
        assert_ne!(witness.prepared_record_sha256, ZERO_COMMITMENT);
        assert_eq!(
            provider
                .begin_exact_once(&request())
                .expect_err("begin is not a recovery API")
                .code(),
            "track_b_atomic_authority_operation_v1_already_exists_use_lookup"
        );
        let journal = provider.journal.lock().expect("journal");
        assert_eq!(journal.revision, 41);
        assert_eq!(journal.operations.len(), 1);
    }

    #[test]
    fn s11_signed_commit_requires_local_verification_and_synthetic_l2_row() {
        let provider = SyntheticAtomicAuthorityOperationV1::new();
        let witness = prepare(&provider);
        let signed = provider
            .finalize_with_cut(&request(), &witness, &permit(), L2CutV1::None)
            .expect("L2");
        let verified = verify_signed_committed_operation_v1(&request(), &permit(), &signed)
            .expect("verified private observation");
        assert_eq!(verified.stable_result_id, signed.stable_result_id);
        assert_eq!(
            verified.decision_message_sha256,
            signed.decision_message_sha256
        );
        assert_eq!(verified.record_sequence, 9);
        assert_eq!(provider.signer_calls(), 1);
    }

    #[test]
    fn s11_exact_duplicate_signed_lookup_is_read_only_and_never_resigns() {
        let provider = SyntheticAtomicAuthorityOperationV1::new();
        let witness = prepare(&provider);
        let signed = provider
            .finalize_with_cut(&request(), &witness, &permit(), L2CutV1::None)
            .expect("signed");
        let revision = provider.journal.lock().expect("journal").revision;
        let again = provider
            .finalize_with_cut(&request(), &witness, &permit(), L2CutV1::None)
            .expect("duplicate");
        assert_eq!(
            again.synthetic_l2_record_sha256,
            signed.synthetic_l2_record_sha256
        );
        assert_eq!(provider.signer_calls(), 1);
        assert_eq!(provider.journal.lock().expect("journal").revision, revision);
    }

    #[test]
    fn s11_signer_timeout_keeps_unsigned_then_exact_resign_converges() {
        let provider = SyntheticAtomicAuthorityOperationV1::new();
        let witness = prepare(&provider);
        provider
            .finalize_with_cut(
                &request(),
                &witness,
                &permit(),
                L2CutV1::SignerTimeoutAfterExecution,
            )
            .expect_err("ambiguous sign");
        assert!(matches!(
            provider
                .lookup_exact(&request(), &permit())
                .expect("lookup"),
            AtomicAuthorityOperationLookupOutcomeV1::Pending(_)
        ));
        let signed = provider
            .finalize_with_cut(&request(), &witness, &permit(), L2CutV1::None)
            .expect("resign");
        assert_eq!(provider.signer_calls(), 2);
        let _observation =
            verify_signed_committed_operation_v1(&request(), &permit(), &signed).expect("verify");
    }

    #[test]
    fn s11_signature_loss_before_l2_keeps_unsigned_then_exact_resume() {
        let provider = SyntheticAtomicAuthorityOperationV1::new();
        let witness = prepare(&provider);
        provider
            .finalize_with_cut(
                &request(),
                &witness,
                &permit(),
                L2CutV1::AfterSignatureBeforeCommit,
            )
            .expect_err("lost signature");
        assert!(matches!(
            provider
                .lookup_exact(&request(), &permit())
                .expect("lookup"),
            AtomicAuthorityOperationLookupOutcomeV1::Pending(_)
        ));
        let _observation = provider
            .resume_exact_from_l1(&request(), &witness, &permit())
            .expect("resume");
        assert_eq!(provider.signer_calls(), 2);
    }

    #[test]
    fn s11_l2_precommit_cut_persists_neither_signature_nor_synthetic_checksum() {
        let provider = SyntheticAtomicAuthorityOperationV1::new();
        let witness = prepare(&provider);
        provider
            .finalize_with_cut(&request(), &witness, &permit(), L2CutV1::BeforeCommit)
            .expect_err("L2 cut");
        let journal = provider.journal.lock().expect("journal");
        let record = journal
            .operations
            .get(&request().operation_id)
            .expect("record");
        assert_eq!(
            record.state,
            AtomicAuthorityOperationPersistentStateV1::DecisionCommittedUnsigned
        );
        assert!(record.signed.is_none());
        assert_eq!(journal.revision, 41);
    }

    #[test]
    fn s11_l2_ack_loss_is_recovered_by_lookup_without_resign() {
        let provider = SyntheticAtomicAuthorityOperationV1::new();
        let witness = prepare(&provider);
        provider
            .finalize_with_cut(&request(), &witness, &permit(), L2CutV1::AckLostAfterCommit)
            .expect_err("ack lost");
        let stored = match provider
            .lookup_exact(&request(), &permit())
            .expect("lookup")
        {
            AtomicAuthorityOperationLookupOutcomeV1::Committed(stored) => stored,
            _ => panic!("L2 ack loss must recover committed"),
        };
        assert_eq!(provider.signer_calls(), 1);
        let _observation =
            verify_signed_committed_operation_v1(&request(), &permit(), &stored).expect("verify");
    }

    #[test]
    fn s11_operation_tuple_conflict_does_not_mutate_winner() {
        let provider = SyntheticAtomicAuthorityOperationV1::new();
        prepare(&provider);
        let before = provider.journal.lock().expect("journal").revision;
        let mut conflicting = request();
        conflicting.original_request_sha256 = repeated(0x91);
        assert_eq!(
            provider
                .begin_exact_once(&conflicting)
                .expect_err("conflict")
                .code(),
            "track_b_atomic_authority_operation_v1_operation_conflict"
        );
        assert_eq!(provider.journal.lock().expect("journal").revision, before);
    }

    #[test]
    fn s11_challenge_or_replay_reuse_by_new_operation_conflicts() {
        let provider = SyntheticAtomicAuthorityOperationV1::new();
        prepare(&provider);
        for mutate in [0_u8, 1] {
            let mut other = request();
            other.operation_id = repeated(0x92 + mutate);
            if mutate == 0 {
                other.concrete_replay_identity_sha256 = repeated(0x93);
            } else {
                other.original_challenge = repeated(0x94);
            }
            assert_eq!(
                provider
                    .begin_exact_once(&other)
                    .expect_err("unique consume conflict")
                    .code(),
                "track_b_atomic_authority_operation_v1_unique_consume_conflict"
            );
        }
    }

    #[test]
    fn s11_wrong_key_version_has_no_fallback_and_no_l2_row() {
        let provider = SyntheticAtomicAuthorityOperationV1::new();
        let witness = prepare(&provider);
        let mut wrong = permit();
        wrong.signer_key_version = 4;
        assert_eq!(
            provider
                .finalize_with_cut(&request(), &witness, &wrong, L2CutV1::None)
                .expect_err("wrong permit")
                .code(),
            "track_b_atomic_authority_operation_v1_trust_scope"
        );
        assert!(matches!(
            provider
                .lookup_exact(&request(), &permit())
                .expect("lookup"),
            AtomicAuthorityOperationLookupOutcomeV1::Pending(_)
        ));
    }

    #[test]
    fn s11_signed_record_field_and_signature_substitutions_reject() {
        let provider = SyntheticAtomicAuthorityOperationV1::new();
        let witness = prepare(&provider);
        let signed = provider
            .finalize_with_cut(&request(), &witness, &permit(), L2CutV1::None)
            .expect("signed");
        let mut cases = Vec::new();
        let mut changed = signed.clone();
        changed.request_sha256[0] ^= 1;
        cases.push(changed);
        let mut changed = signed.clone();
        changed.prepared_record_sha256[0] ^= 1;
        cases.push(changed);
        let mut changed = signed.clone();
        changed.sign_job_id[0] ^= 1;
        cases.push(changed);
        let mut changed = signed.clone();
        changed.decision_message_sha256[0] ^= 1;
        cases.push(changed);
        let mut changed = signed.clone();
        changed.ed25519_signature[0] ^= 1;
        cases.push(changed);
        let mut changed = signed.clone();
        changed.synthetic_l2_record_sha256[0] ^= 1;
        cases.push(changed);
        for changed in cases {
            assert!(verify_signed_committed_operation_v1(&request(), &permit(), &changed).is_err());
        }
    }

    #[test]
    fn s11_revision_generation_and_provider_floors_reject_regression() {
        let provider = SyntheticAtomicAuthorityOperationV1::new();
        let witness = prepare(&provider);
        let signed = provider
            .finalize_with_cut(&request(), &witness, &permit(), L2CutV1::None)
            .expect("signed");
        let mut strict = permit();
        strict.minimum_operation_committed_revision = 42;
        assert_eq!(
            verify_signed_committed_operation_v1(&request(), &strict, &signed)
                .expect_err("low revision")
                .code(),
            "track_b_atomic_authority_operation_v1_monotonic_floor"
        );
        let mut wrong_request = request();
        wrong_request.journal_generation_id = repeated(0x99);
        assert!(verify_signed_committed_operation_v1(&wrong_request, &permit(), &signed).is_err());
    }

    #[test]
    fn s11_revocation_before_l1_rejects_while_after_l1_cannot_release_consume() {
        let before = SyntheticAtomicAuthorityOperationV1::new();
        before.journal.lock().expect("journal").revoked = true;
        assert_eq!(
            before
                .begin_exact_once(&request())
                .expect_err("revoked")
                .code(),
            "track_b_atomic_authority_operation_v1_revoked_before_l1"
        );
        let after = SyntheticAtomicAuthorityOperationV1::new();
        let witness = prepare(&after);
        after.journal.lock().expect("journal").revoked = true;
        assert!(matches!(
            after
                .lookup_with_l1_witness(&request(), &permit(), &witness)
                .expect("historical L1 lookup"),
            AtomicAuthorityOperationLookupOutcomeV1::Pending(_)
        ));
        assert_eq!(
            after
                .journal
                .lock()
                .expect("journal")
                .replay_identities
                .len(),
            1
        );
    }

    #[test]
    fn s11_retained_witness_treats_post_l1_not_found_as_rollback_indeterminate() {
        let provider = SyntheticAtomicAuthorityOperationV1::new();
        let witness = prepare(&provider);
        provider.journal.lock().expect("journal").operations.clear();
        assert_eq!(
            provider
                .lookup_with_l1_witness(&request(), &permit(), &witness)
                .expect_err("rollback must be indeterminate")
                .code(),
            "track_b_atomic_authority_operation_v1_rollback_indeterminate"
        );
        // UNRESOLVED: without the retained witness, rollback is indistinguishable from absence.
    }

    #[test]
    fn s11_concurrent_exact_signers_have_one_persisted_canonical_winner() {
        let provider = SyntheticAtomicAuthorityOperationV1::new();
        let witness = prepare(&provider);
        let left = provider.clone();
        let right = provider.clone();
        let a = std::thread::spawn(move || {
            left.finalize_with_cut(&request(), &witness, &permit(), L2CutV1::None)
        });
        let b = std::thread::spawn(move || {
            right.finalize_with_cut(&request(), &witness, &permit(), L2CutV1::None)
        });
        let first = a.join().expect("thread").expect("first");
        let second = b.join().expect("thread").expect("second");
        assert_eq!(
            first.synthetic_l2_record_sha256,
            second.synthetic_l2_record_sha256
        );
        assert!(provider.signer_calls() == 1 || provider.signer_calls() == 2);
        assert_eq!(provider.journal.lock().expect("journal").revision, 42);
    }

    #[test]
    fn s11_only_two_persistent_states_and_no_noncommitted_observation() {
        let provider = SyntheticAtomicAuthorityOperationV1::new();
        assert!(matches!(
            provider
                .lookup_exact(&request(), &permit())
                .expect("absent"),
            AtomicAuthorityOperationLookupOutcomeV1::NotFound
        ));
        let witness = prepare(&provider);
        assert!(matches!(
            provider
                .lookup_with_l1_witness(&request(), &permit(), &witness)
                .expect("pending"),
            AtomicAuthorityOperationLookupOutcomeV1::Pending(_)
        ));
        assert_eq!(
            [
                AtomicAuthorityOperationPersistentStateV1::DecisionCommittedUnsigned,
                AtomicAuthorityOperationPersistentStateV1::SignedCommitted,
            ]
            .len(),
            2
        );
    }

    #[test]
    fn s11_pending_lookup_with_exact_witness_is_not_rollback() {
        let provider = SyntheticAtomicAuthorityOperationV1::new();
        let witness = prepare(&provider);
        assert!(matches!(
            provider
                .lookup_with_l1_witness(&request(), &permit(), &witness)
                .expect("pending is a first-class lookup outcome"),
            AtomicAuthorityOperationLookupOutcomeV1::Pending(current) if current == witness
        ));
        assert_eq!(provider.signer_calls(), 0);
    }

    #[test]
    fn s11_journal_owned_identity_rejects_every_l1_commitment_substitution() {
        let original = request();
        let mut mutations = Vec::new();
        macro_rules! changed {
            ($field:ident, $value:expr) => {{
                let mut value = original.clone();
                value.$field = $value;
                mutations.push(value);
            }};
        }
        changed!(journal_generation_id, repeated(0x81));
        changed!(provider_cluster_id, "other-cluster".into());
        changed!(provider_incarnation, repeated(0x82));
        changed!(authority_snapshot_sha256, repeated(0x83));
        changed!(canonical_decision_sha256, repeated(0x84));
        changed!(trust_policy_sha256, repeated(0x85));
        changed!(signer_key_id, "other-signer".into());
        changed!(signer_key_version, 4);
        for mutation in mutations {
            let provider = SyntheticAtomicAuthorityOperationV1::new();
            assert_eq!(
                provider
                    .begin_exact_once(&mutation)
                    .expect_err("journal identity substitution")
                    .code(),
                "track_b_atomic_authority_operation_v1_journal_identity"
            );
            let journal = provider.journal.lock().expect("journal");
            assert!(journal.operations.is_empty());
            assert!(journal.challenges.is_empty());
            assert!(journal.replay_identities.is_empty());
        }
    }

    #[test]
    fn s11_signer_metadata_or_invalid_signature_never_reaches_l2() {
        let provider = SyntheticAtomicAuthorityOperationV1::new();
        let witness = prepare(&provider);
        for (fault, expected_code) in [
            (
                SyntheticSignerFaultV1::WrongKeyId,
                "track_b_atomic_authority_operation_v1_signer_binding",
            ),
            (
                SyntheticSignerFaultV1::WrongKeyVersion,
                "track_b_atomic_authority_operation_v1_signer_binding",
            ),
            (
                SyntheticSignerFaultV1::WrongMessageDigest,
                "track_b_atomic_authority_operation_v1_signer_binding",
            ),
            (
                SyntheticSignerFaultV1::InvalidSignature,
                "track_b_atomic_authority_operation_v1_signature",
            ),
        ] {
            provider.set_next_signer_fault(fault);
            assert_eq!(
                provider
                    .finalize_with_cut(&request(), &witness, &permit(), L2CutV1::None)
                    .expect_err("bad signer response")
                    .code(),
                expected_code
            );
            assert!(matches!(
                provider
                    .lookup_exact(&request(), &permit())
                    .expect("lookup"),
                AtomicAuthorityOperationLookupOutcomeV1::Pending(_)
            ));
            assert_eq!(provider.journal.lock().expect("journal").revision, 41);
        }
    }

    #[test]
    fn s11_wrong_public_key_cannot_use_existing_signed_fast_paths() {
        let provider = SyntheticAtomicAuthorityOperationV1::new();
        let witness = prepare(&provider);
        provider
            .finalize_with_cut(&request(), &witness, &permit(), L2CutV1::None)
            .expect("signed");
        let mut wrong = permit();
        wrong.ed25519_public_key = repeated(0xb1);
        assert_eq!(
            provider
                .finalize_with_cut(&request(), &witness, &wrong, L2CutV1::None)
                .expect_err("existing signed row must be reverified")
                .code(),
            "track_b_atomic_authority_operation_v1_signature"
        );
        assert_eq!(
            provider
                .lookup_exact(&request(), &wrong)
                .expect_err("lookup must also reverify")
                .code(),
            "track_b_atomic_authority_operation_v1_signature"
        );
        assert_eq!(provider.signer_calls(), 1);
    }

    #[test]
    fn s11_impossible_phase_or_split_indexes_fail_closed() {
        let impossible = SyntheticAtomicAuthorityOperationV1::new();
        prepare(&impossible);
        impossible
            .journal
            .lock()
            .expect("journal")
            .operations
            .get_mut(&request().operation_id)
            .expect("record")
            .state = AtomicAuthorityOperationPersistentStateV1::SignedCommitted;
        assert_eq!(
            impossible
                .lookup_exact(&request(), &permit())
                .expect_err("signed state without signed payload")
                .code(),
            "track_b_atomic_authority_operation_v1_impossible_state"
        );

        let split = SyntheticAtomicAuthorityOperationV1::new();
        prepare(&split);
        split
            .journal
            .lock()
            .expect("journal")
            .replay_identities
            .clear();
        assert_eq!(
            split
                .lookup_exact(&request(), &permit())
                .expect_err("split replay index")
                .code(),
            "track_b_atomic_authority_operation_v1_impossible_index"
        );
    }

    #[test]
    fn s11_l2_checksum_is_explicitly_not_authenticated_persistence_evidence() {
        let provider = SyntheticAtomicAuthorityOperationV1::new();
        let witness = prepare(&provider);
        let signed = provider
            .finalize_with_cut(&request(), &witness, &permit(), L2CutV1::None)
            .expect("signed");
        let original = verify_signed_committed_operation_v1(&request(), &permit(), &signed)
            .expect("authenticated L1 decision");
        let mut rewritten_metadata = signed.clone();
        rewritten_metadata.synthetic_l2_revision += 7;
        rewritten_metadata.synthetic_l2_record_sha256 = synthetic_l2_record_digest(
            &rewritten_metadata.stable_result_id,
            &rewritten_metadata.decision_message_sha256,
            &rewritten_metadata.ed25519_signature,
            rewritten_metadata.synthetic_l2_revision,
        );
        let still_only_l1 =
            verify_signed_committed_operation_v1(&request(), &permit(), &rewritten_metadata)
                .expect("public L2 checksum is not signer authentication");
        assert_eq!(still_only_l1.stable_result_id, original.stable_result_id);
        assert_eq!(
            still_only_l1.decision_message_sha256,
            original.decision_message_sha256
        );
        // Negative evidence: neither verified observation exposes L2 metadata.
    }

    #[test]
    fn s11_concurrent_l1_begin_has_one_create_only_winner() {
        let provider = SyntheticAtomicAuthorityOperationV1::new();
        let left = provider.clone();
        let right = provider.clone();
        let a = std::thread::spawn(move || left.begin_exact_once(&request()));
        let b = std::thread::spawn(move || right.begin_exact_once(&request()));
        let results = [a.join().expect("thread"), b.join().expect("thread")];
        assert_eq!(results.iter().filter(|result| result.is_ok()).count(), 1);
        assert_eq!(
            results
                .iter()
                .filter_map(|result| result.as_ref().err())
                .next()
                .expect("one create-only loser")
                .code(),
            "track_b_atomic_authority_operation_v1_already_exists_use_lookup"
        );
        let journal = provider.journal.lock().expect("journal");
        assert_eq!(journal.revision, 41);
        assert_eq!(journal.operations.len(), 1);
        assert_eq!(journal.challenges.len(), 1);
        assert_eq!(journal.replay_identities.len(), 1);
    }

    #[test]
    fn s11_resume_requires_exact_witness_and_never_recreates_rollback() {
        let provider = SyntheticAtomicAuthorityOperationV1::new();
        let witness = prepare(&provider);
        let mut substituted = witness;
        substituted.stable_result_id[0] ^= 1;
        assert_eq!(
            provider
                .finalize_with_cut(&request(), &substituted, &permit(), L2CutV1::None)
                .expect_err("wrong witness")
                .code(),
            "track_b_atomic_authority_operation_v1_l1_witness"
        );
        {
            let mut journal = provider.journal.lock().expect("journal");
            journal.operations.clear();
            journal.challenges.clear();
            journal.replay_identities.clear();
        }
        assert_eq!(
            provider
                .finalize_with_cut(&request(), &witness, &permit(), L2CutV1::None)
                .expect_err("rollback must not invoke begin")
                .code(),
            "track_b_atomic_authority_operation_v1_rollback_indeterminate"
        );
        assert_eq!(provider.signer_calls(), 0);
        assert!(provider
            .journal
            .lock()
            .expect("journal")
            .operations
            .is_empty());
    }

    #[test]
    fn s11_response_delivery_loss_recovers_committed_without_resign() {
        let provider = SyntheticAtomicAuthorityOperationV1::new();
        let witness = prepare(&provider);
        let delivered = provider
            .resume_exact_from_l1(&request(), &witness, &permit())
            .expect("synthetic delivery");
        drop(delivered);
        assert!(matches!(
            provider
                .lookup_with_l1_witness(&request(), &permit(), &witness)
                .expect("delivery recovery lookup"),
            AtomicAuthorityOperationLookupOutcomeV1::Committed(_)
        ));
        assert_eq!(provider.signer_calls(), 1);
    }

    #[test]
    fn s11_profile_has_no_network_clock_cache_lease_or_serializable_capability() {
        assert!(PROFILE.contains("NO_KEY_FALLBACK"));
        assert!(!PROFILE.contains("LEASE"));
        assert!(!PROFILE.contains("CLOCK"));
        let debug = format!("{:?}", request());
        assert!(!debug.contains("212121"));
    }
}
