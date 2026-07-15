//! S10 lookup-only external operation-recovery protocol preregistration.
//!
//! This private, default-off module models how a caller could query an
//! immutable S9 operation identity after losing the original provider result.
//! It deliberately has no submit/currentness method: recovery is a read-only
//! lookup, never a retry of the one-attempt S9 request. A committed lookup can
//! produce only private non-admission evidence. It cannot produce an S9
//! currentness token, authorize transport, call Bridge, or mutate `StateStore`.
//!
//! Production code contains no provider implementation, trust-permit
//! constructor, signer, journal, network adapter, persistence, clock, or cache.
//! The deterministic signer, permit, provider, and in-memory journal used by
//! tests model protocol sequences only. Adapter reconstruction over a shared
//! test journal is not evidence of process-crash durability, externality,
//! linearizability, rollback protection, or resolved provider ambiguity.

#![cfg_attr(not(test), allow(dead_code))]

use ring::signature::{UnparsedPublicKey, ED25519};
use sha2::{Digest, Sha256};
use std::fmt;

const POLICY_ID: &str = "agent-bridge/track-b/external-operation-recovery/v1";
const LOOKUP_QUERY_DOMAIN: &[u8] =
    b"agent-bridge/track-b/external-operation-recovery/lookup-query/v1";
const LOOKUP_OBSERVATION_DOMAIN: &[u8] =
    b"agent-bridge/track-b/external-operation-recovery/lookup-observation/v1";
const RESULT_ID_DOMAIN: &[u8] = b"agent-bridge/track-b/external-operation-recovery/result-id/v1";
const ALGORITHM: &str = "Ed25519";
const LOOKUP_PROFILE: &str = "LOOKUP_ONLY_IDEMPOTENT_NO_SUBMIT_NO_RETRY_NO_CACHE_NO_WALL_CLOCK";
const COMMITTED_STATE: &str = "COMMITTED";
const ZERO_COMMITMENT: [u8; 32] = [0; 32];
const S9_CONTRACT_SHA256: [u8; 32] = [
    0xd5, 0x37, 0xb8, 0x0c, 0xe0, 0xd2, 0xbb, 0xb3, 0xc4, 0xd0, 0x1a, 0x98, 0x8a, 0x96, 0x85, 0x43,
    0x26, 0x72, 0x07, 0x8e, 0xae, 0x07, 0xd0, 0xb9, 0x76, 0xb1, 0x26, 0x8a, 0x27, 0x52, 0x6f, 0xc4,
];

#[derive(Debug, thiserror::Error)]
#[error("{code}: {detail}")]
pub(super) struct ExternalOperationRecoveryV1Error {
    code: &'static str,
    detail: &'static str,
}

impl ExternalOperationRecoveryV1Error {
    #[cfg(test)]
    fn code(&self) -> &'static str {
        self.code
    }
}

pub(super) type RecoveryResult<T> = Result<T, ExternalOperationRecoveryV1Error>;

fn recovery_error(code: &'static str, detail: &'static str) -> ExternalOperationRecoveryV1Error {
    ExternalOperationRecoveryV1Error { code, detail }
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

#[derive(Clone)]
pub(super) struct ExternalOperationRecoveryQueryV1 {
    pub(super) provider_profile_id: String,
    pub(super) authority_namespace_id: String,
    pub(super) tenant_id: String,
    pub(super) audience: String,
    pub(super) provider_cluster_id: String,
    pub(super) provider_incarnation: [u8; 32],
    pub(super) lookup_query_id: [u8; 32],
    pub(super) lookup_challenge: [u8; 32],
    pub(super) original_operation_id: [u8; 32],
    pub(super) original_challenge: [u8; 32],
    pub(super) original_request_sha256: [u8; 32],
    pub(super) trust_policy_sha256: [u8; 32],
}

impl fmt::Debug for ExternalOperationRecoveryQueryV1 {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        formatter
            .debug_struct("ExternalOperationRecoveryQueryV1")
            .field("identity", &"[EXACT_ORIGINAL_OPERATION_BINDING]")
            .finish_non_exhaustive()
    }
}

fn validate_query(query: &ExternalOperationRecoveryQueryV1) -> RecoveryResult<()> {
    if !valid_label(&query.provider_profile_id)
        || !valid_label(&query.authority_namespace_id)
        || !valid_label(&query.tenant_id)
        || !valid_label(&query.audience)
        || !valid_label(&query.provider_cluster_id)
    {
        return Err(recovery_error(
            "track_b_external_operation_recovery_v1_query_scope",
            "provider and authority scope labels must be canonical",
        ));
    }
    if ![
        query.provider_incarnation,
        query.lookup_query_id,
        query.lookup_challenge,
        query.original_operation_id,
        query.original_challenge,
        query.original_request_sha256,
        query.trust_policy_sha256,
    ]
    .iter()
    .all(nonzero)
    {
        return Err(recovery_error(
            "track_b_external_operation_recovery_v1_query_commitment",
            "lookup and exact original-operation commitments must be nonzero",
        ));
    }
    Ok(())
}

pub(super) fn lookup_query_digest(
    query: &ExternalOperationRecoveryQueryV1,
) -> RecoveryResult<[u8; 32]> {
    validate_query(query)?;
    Ok(framed_digest(
        LOOKUP_QUERY_DOMAIN,
        &[
            POLICY_ID.as_bytes(),
            ALGORITHM.as_bytes(),
            LOOKUP_PROFILE.as_bytes(),
            &S9_CONTRACT_SHA256,
            query.provider_profile_id.as_bytes(),
            query.authority_namespace_id.as_bytes(),
            query.tenant_id.as_bytes(),
            query.audience.as_bytes(),
            query.provider_cluster_id.as_bytes(),
            &query.provider_incarnation,
            &query.lookup_query_id,
            &query.lookup_challenge,
            &query.original_operation_id,
            &query.original_challenge,
            &query.original_request_sha256,
            &query.trust_policy_sha256,
        ],
    ))
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub(super) enum ExternalOperationRecoveryStateV1 {
    Committed,
    NotFound,
    Pending,
    Conflict,
    Indeterminate,
}

impl ExternalOperationRecoveryStateV1 {
    fn label(self) -> &'static str {
        match self {
            Self::Committed => COMMITTED_STATE,
            Self::NotFound => "NOT_FOUND",
            Self::Pending => "PENDING",
            Self::Conflict => "CONFLICT",
            Self::Indeterminate => "INDETERMINATE",
        }
    }
}

#[derive(Clone)]
pub(super) struct SignedExternalOperationRecoveryObservationV1 {
    pub(super) lookup_query_sha256: [u8; 32],
    pub(super) state: ExternalOperationRecoveryStateV1,
    pub(super) original_operation_id: [u8; 32],
    pub(super) original_challenge: [u8; 32],
    pub(super) original_request_sha256: [u8; 32],
    pub(super) provider_cluster_id: String,
    pub(super) provider_incarnation: [u8; 32],
    pub(super) leader_term: u64,
    pub(super) operation_committed_revision: u64,
    pub(super) observed_journal_revision: u64,
    pub(super) journal_generation_id: [u8; 32],
    pub(super) journal_record_sequence: u64,
    pub(super) original_decision_sha256: [u8; 32],
    pub(super) result_id: [u8; 32],
    pub(super) signer_key_id: String,
    pub(super) signer_key_version: u64,
    pub(super) ed25519_signature: [u8; 64],
}

impl fmt::Debug for SignedExternalOperationRecoveryObservationV1 {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        formatter
            .debug_struct("SignedExternalOperationRecoveryObservationV1")
            .field("state", &self.state)
            .field("authentication", &"[ED25519_REDACTED]")
            .finish_non_exhaustive()
    }
}

fn observation_message(observation: &SignedExternalOperationRecoveryObservationV1) -> Vec<u8> {
    let leader_term = observation.leader_term.to_be_bytes();
    let operation_committed_revision = observation.operation_committed_revision.to_be_bytes();
    let observed_journal_revision = observation.observed_journal_revision.to_be_bytes();
    let journal_record_sequence = observation.journal_record_sequence.to_be_bytes();
    let signer_key_version = observation.signer_key_version.to_be_bytes();
    framed_message(
        LOOKUP_OBSERVATION_DOMAIN,
        &[
            POLICY_ID.as_bytes(),
            ALGORITHM.as_bytes(),
            LOOKUP_PROFILE.as_bytes(),
            &S9_CONTRACT_SHA256,
            &observation.lookup_query_sha256,
            observation.state.label().as_bytes(),
            &observation.original_operation_id,
            &observation.original_challenge,
            &observation.original_request_sha256,
            observation.provider_cluster_id.as_bytes(),
            &observation.provider_incarnation,
            &leader_term,
            &operation_committed_revision,
            &observed_journal_revision,
            &observation.journal_generation_id,
            &journal_record_sequence,
            &observation.original_decision_sha256,
            &observation.result_id,
            observation.signer_key_id.as_bytes(),
            &signer_key_version,
        ],
    )
}

/// Canonically frame one S10 observation only after every attacker-controlled
/// variable-length label has passed the protocol's 128-byte bound. Keeping the
/// raw framer private prevents sibling modules from allocating directly from
/// an unvalidated carried observation.
pub(super) fn validated_observation_message(
    observation: &SignedExternalOperationRecoveryObservationV1,
) -> RecoveryResult<Vec<u8>> {
    validate_observation_labels(observation)?;
    Ok(observation_message(observation))
}

pub(super) fn result_id(
    query: &ExternalOperationRecoveryQueryV1,
    operation_committed_revision: u64,
    journal_generation_id: &[u8; 32],
    journal_record_sequence: u64,
    original_decision_sha256: &[u8; 32],
) -> [u8; 32] {
    let operation_committed_revision = operation_committed_revision.to_be_bytes();
    let journal_record_sequence = journal_record_sequence.to_be_bytes();
    framed_digest(
        RESULT_ID_DOMAIN,
        &[
            POLICY_ID.as_bytes(),
            &S9_CONTRACT_SHA256,
            &query.original_operation_id,
            &query.original_challenge,
            &query.original_request_sha256,
            &operation_committed_revision,
            journal_generation_id,
            &journal_record_sequence,
            original_decision_sha256,
        ],
    )
}

/// All trust material must eventually be selected and delivered by the owner.
/// S10 has no production constructor; tests alone construct this shape.
pub(super) struct ExternalOperationRecoveryTrustPermitV1 {
    provider_profile_id: String,
    authority_namespace_id: String,
    tenant_id: String,
    audience: String,
    provider_cluster_id: String,
    provider_incarnation: [u8; 32],
    signer_key_id: String,
    signer_key_version: u64,
    trust_policy_sha256: [u8; 32],
    minimum_leader_term: u64,
    minimum_observed_journal_revision: u64,
    expected_journal_generation_id: [u8; 32],
    ed25519_public_key: [u8; 32],
}

impl ExternalOperationRecoveryTrustPermitV1 {
    #[cfg(test)]
    #[allow(clippy::too_many_arguments)]
    pub(super) fn test_only_new(
        provider_profile_id: impl Into<String>,
        authority_namespace_id: impl Into<String>,
        tenant_id: impl Into<String>,
        audience: impl Into<String>,
        provider_cluster_id: impl Into<String>,
        provider_incarnation: [u8; 32],
        signer_key_id: impl Into<String>,
        signer_key_version: u64,
        trust_policy_sha256: [u8; 32],
        minimum_leader_term: u64,
        minimum_observed_journal_revision: u64,
        expected_journal_generation_id: [u8; 32],
        ed25519_public_key: [u8; 32],
    ) -> Self {
        Self {
            provider_profile_id: provider_profile_id.into(),
            authority_namespace_id: authority_namespace_id.into(),
            tenant_id: tenant_id.into(),
            audience: audience.into(),
            provider_cluster_id: provider_cluster_id.into(),
            provider_incarnation,
            signer_key_id: signer_key_id.into(),
            signer_key_version,
            trust_policy_sha256,
            minimum_leader_term,
            minimum_observed_journal_revision,
            expected_journal_generation_id,
            ed25519_public_key,
        }
    }
}

impl fmt::Debug for ExternalOperationRecoveryTrustPermitV1 {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        formatter
            .debug_struct("ExternalOperationRecoveryTrustPermitV1")
            .field("trust_anchor", &"[OWNER_PINNED_PUBLIC_KEY]")
            .finish_non_exhaustive()
    }
}

fn validate_permit(permit: &ExternalOperationRecoveryTrustPermitV1) -> RecoveryResult<()> {
    if !valid_label(&permit.provider_profile_id)
        || !valid_label(&permit.authority_namespace_id)
        || !valid_label(&permit.tenant_id)
        || !valid_label(&permit.audience)
        || !valid_label(&permit.provider_cluster_id)
        || !valid_label(&permit.signer_key_id)
        || permit.signer_key_version == 0
        || permit.minimum_leader_term == 0
        || permit.minimum_observed_journal_revision == 0
        || !nonzero(&permit.provider_incarnation)
        || !nonzero(&permit.trust_policy_sha256)
        || !nonzero(&permit.expected_journal_generation_id)
        || !nonzero(&permit.ed25519_public_key)
    {
        return Err(recovery_error(
            "track_b_external_operation_recovery_v1_trust_permit",
            "owner-pinned scope, signer, floors, journal generation, and public key are required",
        ));
    }
    Ok(())
}

fn validate_observation_labels(
    observation: &SignedExternalOperationRecoveryObservationV1,
) -> RecoveryResult<()> {
    if !valid_label(&observation.provider_cluster_id) || !valid_label(&observation.signer_key_id) {
        return Err(recovery_error(
            "track_b_external_operation_recovery_v1_response_label",
            "response provider and signer labels must be canonical and at most 128 bytes",
        ));
    }
    Ok(())
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
enum ExternalOperationRecoveryFailureV1 {
    Timeout,
    Unavailable,
    Unauthenticated,
    Unauthorized,
    Conflict,
    RateLimited,
    Malformed,
    Indeterminate,
}

mod recovery_provider_seal {
    pub(super) trait Sealed {}
}

/// The protocol permits only a read-only lookup and forbids submit,
/// retry-currentness, and local fallback semantics. The seal limits the current
/// implementation surface; any future implementation still requires separate
/// review and audit against those protocol prohibitions.
trait ExternalOperationRecoveryProviderV1: recovery_provider_seal::Sealed {
    fn lookup_operation(
        &self,
        query: &ExternalOperationRecoveryQueryV1,
    ) -> Result<SignedExternalOperationRecoveryObservationV1, ExternalOperationRecoveryFailureV1>;
}

/// Private proof that one synthetic lookup observation was authenticated and
/// exactly bound. It is deliberately not an admission/currentness capability.
#[must_use]
pub(super) struct VerifiedExternalOperationRecoveryObservationV1 {
    provider_profile_id: String,
    authority_namespace_id: String,
    tenant_id: String,
    audience: String,
    provider_cluster_id: String,
    provider_incarnation: [u8; 32],
    trust_policy_sha256: [u8; 32],
    original_operation_id: [u8; 32],
    original_challenge: [u8; 32],
    original_request_sha256: [u8; 32],
    lookup_query_sha256: [u8; 32],
    observation_sha256: [u8; 32],
    original_decision_sha256: [u8; 32],
    result_id: [u8; 32],
    leader_term: u64,
    operation_committed_revision: u64,
    observed_journal_revision: u64,
    journal_generation_id: [u8; 32],
    journal_record_sequence: u64,
}

impl VerifiedExternalOperationRecoveryObservationV1 {
    pub(super) fn provider_profile_id(&self) -> &str {
        &self.provider_profile_id
    }

    pub(super) fn authority_namespace_id(&self) -> &str {
        &self.authority_namespace_id
    }

    pub(super) fn tenant_id(&self) -> &str {
        &self.tenant_id
    }

    pub(super) fn audience(&self) -> &str {
        &self.audience
    }

    pub(super) fn provider_cluster_id(&self) -> &str {
        &self.provider_cluster_id
    }

    pub(super) fn provider_incarnation(&self) -> [u8; 32] {
        self.provider_incarnation
    }

    pub(super) fn trust_policy_sha256(&self) -> [u8; 32] {
        self.trust_policy_sha256
    }

    pub(super) fn original_operation_id(&self) -> [u8; 32] {
        self.original_operation_id
    }

    pub(super) fn original_challenge(&self) -> [u8; 32] {
        self.original_challenge
    }

    pub(super) fn original_request_sha256(&self) -> [u8; 32] {
        self.original_request_sha256
    }

    pub(super) fn lookup_query_sha256(&self) -> [u8; 32] {
        self.lookup_query_sha256
    }

    pub(super) fn observation_sha256(&self) -> [u8; 32] {
        self.observation_sha256
    }

    pub(super) fn original_decision_sha256(&self) -> [u8; 32] {
        self.original_decision_sha256
    }

    pub(super) fn result_id(&self) -> [u8; 32] {
        self.result_id
    }

    pub(super) fn leader_term(&self) -> u64 {
        self.leader_term
    }

    pub(super) fn operation_committed_revision(&self) -> u64 {
        self.operation_committed_revision
    }

    pub(super) fn observed_journal_revision(&self) -> u64 {
        self.observed_journal_revision
    }

    pub(super) fn journal_generation_id(&self) -> [u8; 32] {
        self.journal_generation_id
    }

    pub(super) fn journal_record_sequence(&self) -> u64 {
        self.journal_record_sequence
    }
}

impl fmt::Debug for VerifiedExternalOperationRecoveryObservationV1 {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        formatter
            .debug_struct("VerifiedExternalOperationRecoveryObservationV1")
            .field("scope", &"[NON_ADMISSION_EVIDENCE]")
            .field(
                "operation_committed_revision",
                &self.operation_committed_revision,
            )
            .field("observed_journal_revision", &self.observed_journal_revision)
            .field("journal_record_sequence", &self.journal_record_sequence)
            .finish_non_exhaustive()
    }
}

fn verify_external_operation_recovery_v1<P: ExternalOperationRecoveryProviderV1>(
    provider: &P,
    query: &ExternalOperationRecoveryQueryV1,
    permit: &ExternalOperationRecoveryTrustPermitV1,
) -> RecoveryResult<VerifiedExternalOperationRecoveryObservationV1> {
    validate_permit(permit)?;
    lookup_query_digest(query)?;
    if query.provider_profile_id != permit.provider_profile_id
        || query.authority_namespace_id != permit.authority_namespace_id
        || query.tenant_id != permit.tenant_id
        || query.audience != permit.audience
        || query.provider_cluster_id != permit.provider_cluster_id
        || query.provider_incarnation != permit.provider_incarnation
        || query.trust_policy_sha256 != permit.trust_policy_sha256
    {
        return Err(recovery_error(
            "track_b_external_operation_recovery_v1_trust_scope",
            "lookup query scope does not match the owner-pinned permit",
        ));
    }

    let observation = provider.lookup_operation(query).map_err(|failure| {
        let detail = match failure {
            ExternalOperationRecoveryFailureV1::Timeout => "recovery lookup timed out",
            ExternalOperationRecoveryFailureV1::Unavailable => "recovery provider unavailable",
            ExternalOperationRecoveryFailureV1::Unauthenticated => {
                "recovery channel unauthenticated"
            }
            ExternalOperationRecoveryFailureV1::Unauthorized => "recovery lookup unauthorized",
            ExternalOperationRecoveryFailureV1::Conflict => "recovery identity conflicts",
            ExternalOperationRecoveryFailureV1::RateLimited => "recovery lookup rate limited",
            ExternalOperationRecoveryFailureV1::Malformed => "recovery response malformed",
            ExternalOperationRecoveryFailureV1::Indeterminate => "recovery result indeterminate",
        };
        recovery_error(
            "track_b_external_operation_recovery_v1_provider_failure",
            detail,
        )
    })?;

    verify_external_operation_recovery_observation_v1(query, permit, &observation)
}

/// Pure verification of a previously carried S10 lookup observation. It does
/// not call the recovery provider and returns only non-admission evidence.
pub(super) fn verify_external_operation_recovery_observation_v1(
    query: &ExternalOperationRecoveryQueryV1,
    permit: &ExternalOperationRecoveryTrustPermitV1,
    observation: &SignedExternalOperationRecoveryObservationV1,
) -> RecoveryResult<VerifiedExternalOperationRecoveryObservationV1> {
    validate_permit(permit)?;
    let expected_lookup_query_sha256 = lookup_query_digest(query)?;
    if query.provider_profile_id != permit.provider_profile_id
        || query.authority_namespace_id != permit.authority_namespace_id
        || query.tenant_id != permit.tenant_id
        || query.audience != permit.audience
        || query.provider_cluster_id != permit.provider_cluster_id
        || query.provider_incarnation != permit.provider_incarnation
        || query.trust_policy_sha256 != permit.trust_policy_sha256
    {
        return Err(recovery_error(
            "track_b_external_operation_recovery_v1_trust_scope",
            "lookup query scope does not match the owner-pinned permit",
        ));
    }

    let message = validated_observation_message(observation)?;
    UnparsedPublicKey::new(&ED25519, permit.ed25519_public_key)
        .verify(&message, &observation.ed25519_signature)
        .map_err(|_| {
            recovery_error(
                "track_b_external_operation_recovery_v1_signature",
                "Ed25519 authentication of the exact recovery observation failed",
            )
        })?;

    if observation.lookup_query_sha256 != expected_lookup_query_sha256 {
        return Err(recovery_error(
            "track_b_external_operation_recovery_v1_query_binding",
            "signed recovery observation does not bind the exact lookup query",
        ));
    }
    if observation.state != ExternalOperationRecoveryStateV1::Committed {
        return Err(recovery_error(
            "track_b_external_operation_recovery_v1_not_committed",
            "NOT_FOUND, PENDING, CONFLICT, and INDETERMINATE never produce evidence",
        ));
    }
    if observation.provider_cluster_id != permit.provider_cluster_id
        || observation.provider_incarnation != permit.provider_incarnation
        || observation.signer_key_id != permit.signer_key_id
        || observation.signer_key_version != permit.signer_key_version
    {
        return Err(recovery_error(
            "track_b_external_operation_recovery_v1_provider_identity",
            "provider cluster, incarnation, and immutable signer must match the pinned permit",
        ));
    }
    if observation.original_operation_id != query.original_operation_id
        || observation.original_challenge != query.original_challenge
        || observation.original_request_sha256 != query.original_request_sha256
    {
        return Err(recovery_error(
            "track_b_external_operation_recovery_v1_original_binding",
            "committed result does not match the exact original operation identity",
        ));
    }
    if observation.leader_term < permit.minimum_leader_term
        || observation.observed_journal_revision < permit.minimum_observed_journal_revision
        || observation.journal_generation_id != permit.expected_journal_generation_id
        || observation.journal_record_sequence == 0
        || observation.operation_committed_revision == 0
        || observation.operation_committed_revision > observation.observed_journal_revision
    {
        return Err(recovery_error(
            "track_b_external_operation_recovery_v1_journal_floor",
            "term, observed revision, exact journal generation, record sequence, and operation revision ordering must satisfy pinned floors",
        ));
    }
    let expected_result_id = result_id(
        query,
        observation.operation_committed_revision,
        &observation.journal_generation_id,
        observation.journal_record_sequence,
        &observation.original_decision_sha256,
    );
    if !nonzero(&observation.original_decision_sha256)
        || observation.result_id != expected_result_id
    {
        return Err(recovery_error(
            "track_b_external_operation_recovery_v1_result_binding",
            "COMMITTED requires one exact nonzero decision digest and canonical result identity",
        ));
    }

    Ok(VerifiedExternalOperationRecoveryObservationV1 {
        provider_profile_id: query.provider_profile_id.clone(),
        authority_namespace_id: query.authority_namespace_id.clone(),
        tenant_id: query.tenant_id.clone(),
        audience: query.audience.clone(),
        provider_cluster_id: query.provider_cluster_id.clone(),
        provider_incarnation: query.provider_incarnation,
        trust_policy_sha256: query.trust_policy_sha256,
        original_operation_id: query.original_operation_id,
        original_challenge: query.original_challenge,
        original_request_sha256: query.original_request_sha256,
        lookup_query_sha256: expected_lookup_query_sha256,
        observation_sha256: sha256_bytes(&message),
        original_decision_sha256: observation.original_decision_sha256,
        result_id: observation.result_id,
        leader_term: observation.leader_term,
        operation_committed_revision: observation.operation_committed_revision,
        observed_journal_revision: observation.observed_journal_revision,
        journal_generation_id: observation.journal_generation_id,
        journal_record_sequence: observation.journal_record_sequence,
    })
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

    #[derive(Clone)]
    struct SyntheticIdentityV1 {
        provider_profile_id: String,
        authority_namespace_id: String,
        tenant_id: String,
        audience: String,
        provider_cluster_id: String,
        provider_incarnation: [u8; 32],
        signer_key_id: String,
        signer_key_version: u64,
        trust_policy_sha256: [u8; 32],
        leader_term: u64,
        journal_generation_id: [u8; 32],
    }

    fn commitment(byte: u8) -> [u8; 32] {
        [byte; 32]
    }

    fn identity() -> SyntheticIdentityV1 {
        SyntheticIdentityV1 {
            provider_profile_id: "owner-selected-provider-v1".to_string(),
            authority_namespace_id: "track-b-authority".to_string(),
            tenant_id: "tenant-a".to_string(),
            audience: "agent-bridge-store".to_string(),
            provider_cluster_id: "authority-cluster-a".to_string(),
            provider_incarnation: commitment(0x61),
            signer_key_id: "authority-signer".to_string(),
            signer_key_version: 3,
            trust_policy_sha256: commitment(0x71),
            leader_term: 7,
            journal_generation_id: commitment(0x72),
        }
    }

    fn query() -> ExternalOperationRecoveryQueryV1 {
        let identity = identity();
        ExternalOperationRecoveryQueryV1 {
            provider_profile_id: identity.provider_profile_id,
            authority_namespace_id: identity.authority_namespace_id,
            tenant_id: identity.tenant_id,
            audience: identity.audience,
            provider_cluster_id: identity.provider_cluster_id,
            provider_incarnation: identity.provider_incarnation,
            lookup_query_id: commitment(0x31),
            lookup_challenge: commitment(0x32),
            original_operation_id: commitment(0x21),
            original_challenge: commitment(0x22),
            original_request_sha256: commitment(0x23),
            trust_policy_sha256: identity.trust_policy_sha256,
        }
    }

    fn permit_for(
        identity: &SyntheticIdentityV1,
        public_key: [u8; 32],
    ) -> ExternalOperationRecoveryTrustPermitV1 {
        ExternalOperationRecoveryTrustPermitV1 {
            provider_profile_id: identity.provider_profile_id.clone(),
            authority_namespace_id: identity.authority_namespace_id.clone(),
            tenant_id: identity.tenant_id.clone(),
            audience: identity.audience.clone(),
            provider_cluster_id: identity.provider_cluster_id.clone(),
            provider_incarnation: identity.provider_incarnation,
            signer_key_id: identity.signer_key_id.clone(),
            signer_key_version: identity.signer_key_version,
            trust_policy_sha256: identity.trust_policy_sha256,
            minimum_leader_term: identity.leader_term,
            minimum_observed_journal_revision: 42,
            expected_journal_generation_id: identity.journal_generation_id,
            ed25519_public_key: public_key,
        }
    }

    fn key_pair(seed: &[u8; 32]) -> Ed25519KeyPair {
        Ed25519KeyPair::from_seed_unchecked(seed).expect("RFC 8032 seed")
    }

    fn provider_public_key(seed: &[u8; 32]) -> [u8; 32] {
        key_pair(seed)
            .public_key()
            .as_ref()
            .try_into()
            .expect("Ed25519 public key is 32 bytes")
    }

    fn sign_observation(
        seed: &[u8; 32],
        identity: &SyntheticIdentityV1,
        query: &ExternalOperationRecoveryQueryV1,
        state: ExternalOperationRecoveryStateV1,
        operation_committed_revision: u64,
        observed_journal_revision: u64,
        journal_record_sequence: u64,
        original_decision_sha256: [u8; 32],
    ) -> SignedExternalOperationRecoveryObservationV1 {
        let mut observation = SignedExternalOperationRecoveryObservationV1 {
            lookup_query_sha256: lookup_query_digest(query).expect("valid lookup query"),
            state,
            original_operation_id: query.original_operation_id,
            original_challenge: query.original_challenge,
            original_request_sha256: query.original_request_sha256,
            provider_cluster_id: identity.provider_cluster_id.clone(),
            provider_incarnation: identity.provider_incarnation,
            leader_term: identity.leader_term,
            operation_committed_revision,
            observed_journal_revision,
            journal_generation_id: identity.journal_generation_id,
            journal_record_sequence,
            original_decision_sha256,
            result_id: result_id(
                query,
                operation_committed_revision,
                &identity.journal_generation_id,
                journal_record_sequence,
                &original_decision_sha256,
            ),
            signer_key_id: identity.signer_key_id.clone(),
            signer_key_version: identity.signer_key_version,
            ed25519_signature: [0; 64],
        };
        observation.ed25519_signature = key_pair(seed)
            .sign(
                &validated_observation_message(&observation)
                    .expect("synthetic observation labels are canonical"),
            )
            .as_ref()
            .try_into()
            .expect("Ed25519 signature is 64 bytes");
        observation
    }

    fn resign_observation(
        observation: &mut SignedExternalOperationRecoveryObservationV1,
        seed: &[u8; 32],
    ) {
        // This test-only helper deliberately signs malformed-label fixtures so
        // the production validated seam can prove that it rejects them before
        // framing. The raw framer is private to this module.
        observation.ed25519_signature = key_pair(seed)
            .sign(&observation_message(observation))
            .as_ref()
            .try_into()
            .expect("Ed25519 signature is 64 bytes");
    }

    #[derive(Clone, Debug, PartialEq, Eq)]
    struct SyntheticJournalRecordV1 {
        original_challenge: [u8; 32],
        original_request_sha256: [u8; 32],
        state: ExternalOperationRecoveryStateV1,
        original_decision_sha256: [u8; 32],
        record_sequence: u64,
        operation_committed_revision: u64,
    }

    #[derive(Debug, PartialEq, Eq)]
    struct SyntheticJournalV1 {
        generation_id: [u8; 32],
        observed_revision: u64,
        records: BTreeMap<[u8; 32], SyntheticJournalRecordV1>,
    }

    type SharedSyntheticJournalV1 = Arc<Mutex<SyntheticJournalV1>>;

    fn committed_journal() -> SharedSyntheticJournalV1 {
        let query = query();
        let mut records = BTreeMap::new();
        records.insert(
            query.original_operation_id,
            SyntheticJournalRecordV1 {
                original_challenge: query.original_challenge,
                original_request_sha256: query.original_request_sha256,
                state: ExternalOperationRecoveryStateV1::Committed,
                original_decision_sha256: commitment(0x24),
                record_sequence: 9,
                operation_committed_revision: 43,
            },
        );
        Arc::new(Mutex::new(SyntheticJournalV1 {
            generation_id: identity().journal_generation_id,
            observed_revision: 43,
            records,
        }))
    }

    fn empty_journal() -> SharedSyntheticJournalV1 {
        Arc::new(Mutex::new(SyntheticJournalV1 {
            generation_id: identity().journal_generation_id,
            observed_revision: 42,
            records: BTreeMap::new(),
        }))
    }

    struct SyntheticLookupOnlyProviderV1 {
        seed: [u8; 32],
        identity: SyntheticIdentityV1,
        journal: SharedSyntheticJournalV1,
    }

    impl SyntheticLookupOnlyProviderV1 {
        fn new(journal: SharedSyntheticJournalV1) -> Self {
            Self {
                seed: RFC8032_SEED,
                identity: identity(),
                journal,
            }
        }
    }

    impl Drop for SyntheticLookupOnlyProviderV1 {
        fn drop(&mut self) {
            self.seed.fill(0);
        }
    }

    impl recovery_provider_seal::Sealed for SyntheticLookupOnlyProviderV1 {}

    impl ExternalOperationRecoveryProviderV1 for SyntheticLookupOnlyProviderV1 {
        fn lookup_operation(
            &self,
            query: &ExternalOperationRecoveryQueryV1,
        ) -> Result<SignedExternalOperationRecoveryObservationV1, ExternalOperationRecoveryFailureV1>
        {
            validate_query(query).map_err(|_| ExternalOperationRecoveryFailureV1::Malformed)?;
            let journal = self
                .journal
                .lock()
                .map_err(|_| ExternalOperationRecoveryFailureV1::Indeterminate)?;
            if journal.generation_id != self.identity.journal_generation_id {
                return Err(ExternalOperationRecoveryFailureV1::Indeterminate);
            }
            let (state, operation_committed_revision, record_sequence, original_decision_sha256) =
                match journal.records.get(&query.original_operation_id) {
                    Some(record)
                        if record.original_challenge != query.original_challenge
                            || record.original_request_sha256 != query.original_request_sha256 =>
                    {
                        (
                            ExternalOperationRecoveryStateV1::Conflict,
                            0,
                            1,
                            ZERO_COMMITMENT,
                        )
                    }
                    Some(record) => (
                        record.state,
                        record.operation_committed_revision,
                        record.record_sequence,
                        record.original_decision_sha256,
                    ),
                    None => (
                        ExternalOperationRecoveryStateV1::NotFound,
                        0,
                        1,
                        ZERO_COMMITMENT,
                    ),
                };
            Ok(sign_observation(
                &self.seed,
                &self.identity,
                query,
                state,
                operation_committed_revision,
                journal.observed_revision,
                record_sequence,
                original_decision_sha256,
            ))
        }
    }

    struct StaticRecoveryProviderV1 {
        result: Result<
            SignedExternalOperationRecoveryObservationV1,
            ExternalOperationRecoveryFailureV1,
        >,
    }

    impl recovery_provider_seal::Sealed for StaticRecoveryProviderV1 {}

    impl ExternalOperationRecoveryProviderV1 for StaticRecoveryProviderV1 {
        fn lookup_operation(
            &self,
            _query: &ExternalOperationRecoveryQueryV1,
        ) -> Result<SignedExternalOperationRecoveryObservationV1, ExternalOperationRecoveryFailureV1>
        {
            self.result.clone()
        }
    }

    fn static_provider(
        observation: SignedExternalOperationRecoveryObservationV1,
    ) -> StaticRecoveryProviderV1 {
        StaticRecoveryProviderV1 {
            result: Ok(observation),
        }
    }

    fn committed_observation() -> SignedExternalOperationRecoveryObservationV1 {
        sign_observation(
            &RFC8032_SEED,
            &identity(),
            &query(),
            ExternalOperationRecoveryStateV1::Committed,
            43,
            43,
            9,
            commitment(0x24),
        )
    }

    fn hex(bytes: &[u8]) -> String {
        bytes.iter().map(|byte| format!("{byte:02x}")).collect()
    }

    #[test]
    fn s10_known_answer_ed25519_and_exact_framing_are_stable() {
        assert_eq!(provider_public_key(&RFC8032_SEED), RFC8032_PUBLIC_KEY);
        let query = query();
        let observation = committed_observation();
        assert_eq!(
            hex(&lookup_query_digest(&query).unwrap()),
            "df2aeb766e996f83eb24bf1cef78f421f62c8a3691cf0bd41f0277a0ffda1f3d"
        );
        assert_eq!(
            hex(&sha256_bytes(
                &validated_observation_message(&observation).unwrap()
            )),
            "1fb08add6ebbd5102e665190ccc721ef9bda30d02450da53f0561f9bf5c71a70"
        );
        assert_eq!(
            hex(&observation.ed25519_signature),
            "fb02e9df3a801dacd0d0dd8c24ad2c13636d90cf436c082046a40265b8a58e55862a2df3dfcba8af079a39366a75911bcd359420cf4b63a1d2141248596b5e0a"
        );
    }

    #[test]
    fn s10_validated_observation_framer_bounds_labels_before_allocation() {
        let mut boundary = committed_observation();
        boundary.provider_cluster_id = "a".repeat(128);
        boundary.signer_key_id = "b".repeat(128);
        assert!(!validated_observation_message(&boundary).unwrap().is_empty());

        let mut oversized_provider = boundary.clone();
        oversized_provider.provider_cluster_id = "a".repeat(129);
        assert_eq!(
            validated_observation_message(&oversized_provider)
                .unwrap_err()
                .code(),
            "track_b_external_operation_recovery_v1_response_label"
        );

        let mut oversized_signer = boundary;
        oversized_signer.signer_key_id = "b".repeat(129);
        assert_eq!(
            validated_observation_message(&oversized_signer)
                .unwrap_err()
                .code(),
            "track_b_external_operation_recovery_v1_response_label"
        );
    }

    #[test]
    fn s10_exact_committed_lookup_produces_private_non_admission_evidence() {
        let query = query();
        let evidence = verify_external_operation_recovery_v1(
            &static_provider(committed_observation()),
            &query,
            &permit_for(&identity(), RFC8032_PUBLIC_KEY),
        )
        .expect("exact COMMITTED observation verifies");
        assert_eq!(
            evidence.lookup_query_sha256,
            lookup_query_digest(&query).unwrap()
        );
        assert_eq!(evidence.original_decision_sha256, commitment(0x24));
        assert_eq!(evidence.result_id, committed_observation().result_id);
        assert_eq!(evidence.operation_committed_revision, 43);
        assert_eq!(evidence.observed_journal_revision, 43);
        assert_eq!(
            evidence.journal_generation_id,
            identity().journal_generation_id
        );
        assert!(nonzero(&evidence.observation_sha256));
        assert!(format!("{evidence:?}").contains("NON_ADMISSION_EVIDENCE"));
    }

    #[test]
    fn s10_lookup_only_interface_never_submits_or_mutates_journal() {
        let journal = committed_journal();
        let before_revision = journal.lock().unwrap().observed_revision;
        let before_records = journal.lock().unwrap().records.clone();
        let provider = SyntheticLookupOnlyProviderV1::new(Arc::clone(&journal));
        let _ = provider
            .lookup_operation(&query())
            .expect("read-only lookup");
        let after = journal.lock().unwrap();
        assert_eq!(after.observed_revision, before_revision);
        assert_eq!(after.records, before_records);
    }

    #[test]
    fn s10_duplicate_lookup_keeps_result_stable_across_unrelated_journal_advance() {
        let journal = committed_journal();
        let provider = SyntheticLookupOnlyProviderV1::new(Arc::clone(&journal));
        let first = provider.lookup_operation(&query()).unwrap();
        journal.lock().unwrap().observed_revision = 44;
        let second = provider.lookup_operation(&query()).unwrap();
        assert_eq!(first.operation_committed_revision, 43);
        assert_eq!(second.operation_committed_revision, 43);
        assert_eq!(first.journal_generation_id, second.journal_generation_id);
        assert_eq!(
            first.journal_record_sequence,
            second.journal_record_sequence
        );
        assert_eq!(
            first.original_decision_sha256,
            second.original_decision_sha256
        );
        assert_eq!(first.result_id, second.result_id);
        assert_eq!(first.observed_journal_revision, 43);
        assert_eq!(second.observed_journal_revision, 44);
        assert_ne!(
            validated_observation_message(&first).unwrap(),
            validated_observation_message(&second).unwrap()
        );
        let first_evidence = verify_external_operation_recovery_v1(
            &static_provider(first),
            &query(),
            &permit_for(&identity(), RFC8032_PUBLIC_KEY),
        )
        .expect("first lookup");
        let second_evidence = verify_external_operation_recovery_v1(
            &static_provider(second),
            &query(),
            &permit_for(&identity(), RFC8032_PUBLIC_KEY),
        )
        .expect("later lookup");
        assert_eq!(first_evidence.result_id, second_evidence.result_id);
        assert_eq!(first_evidence.operation_committed_revision, 43);
        assert_eq!(second_evidence.operation_committed_revision, 43);
        assert_eq!(first_evidence.observed_journal_revision, 43);
        assert_eq!(second_evidence.observed_journal_revision, 44);
    }

    #[test]
    fn s10_operation_id_with_different_request_or_challenge_conflicts() {
        let provider = SyntheticLookupOnlyProviderV1::new(committed_journal());
        let mut mismatch = query();
        mismatch.original_request_sha256 = commitment(0x91);
        let observation = provider.lookup_operation(&mismatch).unwrap();
        assert_eq!(
            observation.state,
            ExternalOperationRecoveryStateV1::Conflict
        );
        assert_eq!(
            verify_external_operation_recovery_v1(
                &static_provider(observation),
                &mismatch,
                &permit_for(&identity(), RFC8032_PUBLIC_KEY)
            )
            .unwrap_err()
            .code(),
            "track_b_external_operation_recovery_v1_not_committed"
        );

        let mut challenge_mismatch = query();
        challenge_mismatch.original_challenge = commitment(0x92);
        let observation = provider.lookup_operation(&challenge_mismatch).unwrap();
        assert_eq!(
            observation.state,
            ExternalOperationRecoveryStateV1::Conflict
        );
        assert_eq!(
            verify_external_operation_recovery_v1(
                &static_provider(observation),
                &challenge_mismatch,
                &permit_for(&identity(), RFC8032_PUBLIC_KEY)
            )
            .unwrap_err()
            .code(),
            "track_b_external_operation_recovery_v1_not_committed"
        );
    }

    #[test]
    fn s10_every_lookup_query_field_substitution_rejects() {
        let original = query();
        let observation = committed_observation();
        let permit = permit_for(&identity(), RFC8032_PUBLIC_KEY);
        let mut mutations = Vec::new();
        macro_rules! changed {
            ($field:ident, $value:expr) => {{
                let mut value = original.clone();
                value.$field = $value;
                mutations.push(value);
            }};
        }
        changed!(provider_profile_id, "other-provider".to_string());
        changed!(authority_namespace_id, "other-authority".to_string());
        changed!(tenant_id, "other-tenant".to_string());
        changed!(audience, "other-audience".to_string());
        changed!(provider_cluster_id, "other-cluster".to_string());
        changed!(provider_incarnation, commitment(0x81));
        changed!(lookup_query_id, commitment(0x82));
        changed!(lookup_challenge, commitment(0x83));
        changed!(original_operation_id, commitment(0x84));
        changed!(original_challenge, commitment(0x85));
        changed!(original_request_sha256, commitment(0x86));
        changed!(trust_policy_sha256, commitment(0x87));
        for mutation in mutations {
            assert!(verify_external_operation_recovery_v1(
                &static_provider(observation.clone()),
                &mutation,
                &permit
            )
            .is_err());
        }
    }

    #[test]
    fn s10_every_signed_observation_field_or_signature_tamper_rejects() {
        let query = query();
        let original = committed_observation();
        let permit = permit_for(&identity(), RFC8032_PUBLIC_KEY);
        let mut mutations = Vec::new();
        macro_rules! changed {
            ($field:ident, $value:expr) => {{
                let mut value = original.clone();
                value.$field = $value;
                resign_observation(&mut value, &RFC8032_SEED);
                mutations.push(value);
            }};
        }
        changed!(lookup_query_sha256, commitment(0xa1));
        changed!(state, ExternalOperationRecoveryStateV1::Pending);
        changed!(original_operation_id, commitment(0xa2));
        changed!(original_challenge, commitment(0xa3));
        changed!(original_request_sha256, commitment(0xa4));
        changed!(provider_cluster_id, "other-cluster".to_string());
        changed!(provider_incarnation, commitment(0xa5));
        changed!(leader_term, 6);
        changed!(operation_committed_revision, 0);
        changed!(observed_journal_revision, 41);
        changed!(journal_generation_id, commitment(0xa6));
        changed!(journal_record_sequence, 0);
        changed!(original_decision_sha256, commitment(0xa7));
        changed!(result_id, commitment(0xa8));
        changed!(signer_key_id, "other-signer".to_string());
        changed!(signer_key_version, 4);
        let mut noncanonical_provider = original.clone();
        noncanonical_provider.provider_cluster_id = "Upper Case".to_string();
        resign_observation(&mut noncanonical_provider, &RFC8032_SEED);
        assert_eq!(
            verify_external_operation_recovery_v1(
                &static_provider(noncanonical_provider),
                &query,
                &permit
            )
            .unwrap_err()
            .code(),
            "track_b_external_operation_recovery_v1_response_label"
        );
        let mut oversized_signer = original.clone();
        oversized_signer.signer_key_id = "x".repeat(129);
        resign_observation(&mut oversized_signer, &RFC8032_SEED);
        assert_eq!(
            verify_external_operation_recovery_v1(
                &static_provider(oversized_signer),
                &query,
                &permit
            )
            .unwrap_err()
            .code(),
            "track_b_external_operation_recovery_v1_response_label"
        );
        for mutation in mutations {
            let error =
                verify_external_operation_recovery_v1(&static_provider(mutation), &query, &permit)
                    .unwrap_err();
            assert_ne!(
                error.code(),
                "track_b_external_operation_recovery_v1_signature"
            );
        }

        let mut signature = original.clone();
        signature.ed25519_signature[0] ^= 1;
        assert_eq!(
            verify_external_operation_recovery_v1(&static_provider(signature), &query, &permit)
                .unwrap_err()
                .code(),
            "track_b_external_operation_recovery_v1_signature"
        );

        let mut signature_priority = original;
        signature_priority.state = ExternalOperationRecoveryStateV1::Pending;
        signature_priority.lookup_query_sha256 = commitment(0xaf);
        signature_priority.ed25519_signature[0] ^= 1;
        assert_eq!(
            verify_external_operation_recovery_v1(
                &static_provider(signature_priority),
                &query,
                &permit
            )
            .unwrap_err()
            .code(),
            "track_b_external_operation_recovery_v1_signature"
        );
    }

    #[test]
    fn s10_wrong_pin_signer_version_and_provider_incarnation_reject() {
        let query = query();
        let observation = committed_observation();
        let mut wrong_key = permit_for(&identity(), commitment(0xb1));
        assert_eq!(
            verify_external_operation_recovery_v1(
                &static_provider(observation.clone()),
                &query,
                &wrong_key
            )
            .unwrap_err()
            .code(),
            "track_b_external_operation_recovery_v1_signature"
        );
        wrong_key.ed25519_public_key = RFC8032_PUBLIC_KEY;
        wrong_key.signer_key_version = 4;
        assert!(verify_external_operation_recovery_v1(
            &static_provider(observation.clone()),
            &query,
            &wrong_key
        )
        .is_err());
        let mut wrong_incarnation = permit_for(&identity(), RFC8032_PUBLIC_KEY);
        wrong_incarnation.provider_incarnation = commitment(0xb2);
        assert!(verify_external_operation_recovery_v1(
            &static_provider(observation),
            &query,
            &wrong_incarnation
        )
        .is_err());
    }

    #[test]
    fn s10_all_non_committed_states_produce_no_evidence() {
        let query = query();
        let permit = permit_for(&identity(), RFC8032_PUBLIC_KEY);
        for state in [
            ExternalOperationRecoveryStateV1::NotFound,
            ExternalOperationRecoveryStateV1::Pending,
            ExternalOperationRecoveryStateV1::Conflict,
            ExternalOperationRecoveryStateV1::Indeterminate,
        ] {
            let observation = sign_observation(
                &RFC8032_SEED,
                &identity(),
                &query,
                state,
                0,
                43,
                9,
                ZERO_COMMITMENT,
            );
            assert_eq!(
                verify_external_operation_recovery_v1(
                    &static_provider(observation),
                    &query,
                    &permit
                )
                .unwrap_err()
                .code(),
                "track_b_external_operation_recovery_v1_not_committed"
            );
        }
    }

    #[test]
    fn s10_all_provider_failures_have_no_local_fallback() {
        let query = query();
        let permit = permit_for(&identity(), RFC8032_PUBLIC_KEY);
        for failure in [
            ExternalOperationRecoveryFailureV1::Timeout,
            ExternalOperationRecoveryFailureV1::Unavailable,
            ExternalOperationRecoveryFailureV1::Unauthenticated,
            ExternalOperationRecoveryFailureV1::Unauthorized,
            ExternalOperationRecoveryFailureV1::Conflict,
            ExternalOperationRecoveryFailureV1::RateLimited,
            ExternalOperationRecoveryFailureV1::Malformed,
            ExternalOperationRecoveryFailureV1::Indeterminate,
        ] {
            let provider = StaticRecoveryProviderV1 {
                result: Err(failure),
            };
            assert_eq!(
                verify_external_operation_recovery_v1(&provider, &query, &permit)
                    .unwrap_err()
                    .code(),
                "track_b_external_operation_recovery_v1_provider_failure"
            );
        }
    }

    #[test]
    fn s10_adapter_reconstruction_over_shared_test_journal_finds_same_result() {
        let journal = committed_journal();
        let first = {
            let provider = SyntheticLookupOnlyProviderV1::new(Arc::clone(&journal));
            provider.lookup_operation(&query()).unwrap()
        };
        let second = {
            let reconstructed = SyntheticLookupOnlyProviderV1::new(Arc::clone(&journal));
            reconstructed.lookup_operation(&query()).unwrap()
        };
        assert_eq!(
            validated_observation_message(&first).unwrap(),
            validated_observation_message(&second).unwrap()
        );
        assert_eq!(first.ed25519_signature, second.ed25519_signature);
        let _evidence = verify_external_operation_recovery_v1(
            &static_provider(second),
            &query(),
            &permit_for(&identity(), RFC8032_PUBLIC_KEY),
        )
        .expect("sequence-model reconstruction finds the same committed result");
    }

    #[test]
    fn s10_lost_journal_cannot_distinguish_absence_from_rollback_negative_evidence() {
        let query = query();
        let committed = SyntheticLookupOnlyProviderV1::new(committed_journal())
            .lookup_operation(&query)
            .unwrap();
        let _evidence = verify_external_operation_recovery_v1(
            &static_provider(committed),
            &query,
            &permit_for(&identity(), RFC8032_PUBLIC_KEY),
        )
        .expect("committed synthetic record");

        let reconstructed_without_journal = SyntheticLookupOnlyProviderV1::new(empty_journal());
        let lost = reconstructed_without_journal
            .lookup_operation(&query)
            .expect("signed NOT_FOUND observation");
        assert_eq!(lost.state, ExternalOperationRecoveryStateV1::NotFound);
        assert!(verify_external_operation_recovery_v1(
            &static_provider(lost),
            &query,
            &permit_for(&identity(), RFC8032_PUBLIC_KEY)
        )
        .is_err());
        // UNRESOLVED: synthetic journal loss cannot distinguish absence from rollback.
    }

    #[test]
    fn s10_recovery_vocabulary_and_evidence_exclude_revocation_or_consume_semantics() {
        let query = query();
        let permit = permit_for(&identity(), RFC8032_PUBLIC_KEY);
        let evidence = verify_external_operation_recovery_v1(
            &static_provider(committed_observation()),
            &query,
            &permit,
        )
        .expect("committed snapshot");
        let vocabulary = [
            ExternalOperationRecoveryStateV1::Committed,
            ExternalOperationRecoveryStateV1::NotFound,
            ExternalOperationRecoveryStateV1::Pending,
            ExternalOperationRecoveryStateV1::Conflict,
            ExternalOperationRecoveryStateV1::Indeterminate,
        ]
        .map(ExternalOperationRecoveryStateV1::label);
        assert_eq!(
            vocabulary,
            [
                "COMMITTED",
                "NOT_FOUND",
                "PENDING",
                "CONFLICT",
                "INDETERMINATE"
            ]
        );
        assert!(!vocabulary.contains(&"ACTIVE"));
        assert!(!vocabulary.contains(&"REVOKED"));
        assert_eq!(evidence.original_decision_sha256, commitment(0x24));
        assert!(format!("{evidence:?}").contains("NON_ADMISSION_EVIDENCE"));
        // UNRESOLVED: returned observational evidence has no recall/consume API;
        // currentness and revocation deliberately remain outside this protocol.
    }

    #[test]
    fn s10_profile_has_no_submit_clock_cache_lease_or_serializable_capability() {
        assert_eq!(
            LOOKUP_PROFILE,
            "LOOKUP_ONLY_IDEMPOTENT_NO_SUBMIT_NO_RETRY_NO_CACHE_NO_WALL_CLOCK"
        );
        for forbidden in ["TTL", "LEASE", "SUBMIT_ALLOWED", "CACHE_ALLOWED"] {
            assert!(!LOOKUP_PROFILE.contains(forbidden));
        }
        assert_eq!(ALGORITHM, "Ed25519");
        assert_eq!(COMMITTED_STATE, "COMMITTED");
        assert!(nonzero(&S9_CONTRACT_SHA256));
    }
}
