//! S9 provider-neutral external currentness and key-custody contract.
//!
//! This private, default-off module preregisters the boundary that a future
//! owner-selected external authority must satisfy. Agent-Bridge verifies an
//! Ed25519 signature with an out-of-band pinned public key; the corresponding
//! signing key is never accepted by this module. Every decision is bound to a
//! one-attempt request and has no reusable lease. There is deliberately no
//! network adapter, production permit constructor, Bridge caller, StateStore
//! integration, or S8 admission hook.
//!
//! Ed25519 proves only that the holder of a private key signed exact bytes. It
//! does not prove that the signer is external, linearizable, rollback-safe, or
//! backed by a KMS/HSM. Durable challenge uniqueness, split-brain fencing,
//! signer rotation, old-key use denial, provider recovery, same-epoch rollback,
//! and the currentness-to-local-consume race all remain unresolved.

#![cfg_attr(not(test), allow(dead_code))]

use ring::signature::{UnparsedPublicKey, ED25519};
use sha2::{Digest, Sha256};
use std::fmt;

const POLICY_ID: &str = "agent-bridge/track-b/external-authority-provider/v1";
const REQUEST_DOMAIN: &[u8] =
    b"agent-bridge/track-b/external-authority-provider/currentness-request/v1";
const DECISION_DOMAIN: &[u8] =
    b"agent-bridge/track-b/external-authority-provider/currentness-decision/v1";
const KEY_REF_DOMAIN: &[u8] = b"agent-bridge/track-b/external-authority-provider/opaque-key-ref/v1";
const KEYSET_DOMAIN: &[u8] = b"agent-bridge/track-b/external-authority-provider/opaque-keyset/v1";
const KEY_STATE_REQUEST_DOMAIN: &[u8] =
    b"agent-bridge/track-b/external-authority-provider/key-state-request/v1";
const ALGORITHM: &str = "Ed25519";
const LEASE_PROFILE: &str = "ONE_ATTEMPT_NO_CACHE_NO_WALL_CLOCK";
const ACTIVE_STATE: &str = "ACTIVE";
const ZERO_COMMITMENT: [u8; 32] = [0; 32];

#[derive(Debug, thiserror::Error)]
#[error("{code}: {detail}")]
struct ExternalAuthorityContractV1Error {
    code: &'static str,
    detail: &'static str,
}

impl ExternalAuthorityContractV1Error {
    #[cfg(test)]
    fn code(&self) -> &'static str {
        self.code
    }
}

type ContractResult<T> = Result<T, ExternalAuthorityContractV1Error>;

fn contract_error(code: &'static str, detail: &'static str) -> ExternalAuthorityContractV1Error {
    ExternalAuthorityContractV1Error { code, detail }
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

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
enum OpaqueKeyRoleV1 {
    Handle,
    InnerTransport,
    OuterChannel,
}

impl OpaqueKeyRoleV1 {
    fn label(self) -> &'static str {
        match self {
            Self::Handle => "HANDLE",
            Self::InnerTransport => "INNER_TRANSPORT",
            Self::OuterChannel => "OUTER_CHANNEL",
        }
    }
}

/// An immutable provider-side key identity. It contains no key bytes and its
/// digest is an identity commitment, not a fingerprint of secret material.
#[derive(Clone, PartialEq, Eq)]
struct OpaqueKeyVersionRefV1 {
    provider_profile_id: String,
    authority_namespace_id: String,
    provider_cluster_id: String,
    provider_incarnation: [u8; 32],
    key_id: String,
    key_version: u64,
    role: OpaqueKeyRoleV1,
    algorithm: String,
    identity_sha256: [u8; 32],
}

impl fmt::Debug for OpaqueKeyVersionRefV1 {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        formatter
            .debug_struct("OpaqueKeyVersionRefV1")
            .field("role", &self.role)
            .field("identity", &"[OPAQUE_PROVIDER_IDENTITY]")
            .finish_non_exhaustive()
    }
}

impl OpaqueKeyVersionRefV1 {
    fn try_new(
        provider_profile_id: impl Into<String>,
        authority_namespace_id: impl Into<String>,
        provider_cluster_id: impl Into<String>,
        provider_incarnation: [u8; 32],
        key_id: impl Into<String>,
        key_version: u64,
        role: OpaqueKeyRoleV1,
        algorithm: impl Into<String>,
    ) -> ContractResult<Self> {
        let provider_profile_id = provider_profile_id.into();
        let authority_namespace_id = authority_namespace_id.into();
        let provider_cluster_id = provider_cluster_id.into();
        let key_id = key_id.into();
        let algorithm = algorithm.into();
        if !valid_label(&provider_profile_id)
            || !valid_label(&authority_namespace_id)
            || !valid_label(&provider_cluster_id)
            || !nonzero(&provider_incarnation)
            || !valid_label(&key_id)
            || !valid_label(&algorithm)
            || key_version == 0
        {
            return Err(contract_error(
                "track_b_external_authority_v1_opaque_key",
                "opaque key identifiers and immutable version must be canonical and nonzero",
            ));
        }
        let version = key_version.to_be_bytes();
        let identity_sha256 = framed_digest(
            KEY_REF_DOMAIN,
            &[
                POLICY_ID.as_bytes(),
                provider_profile_id.as_bytes(),
                authority_namespace_id.as_bytes(),
                provider_cluster_id.as_bytes(),
                &provider_incarnation,
                key_id.as_bytes(),
                &version,
                role.label().as_bytes(),
                algorithm.as_bytes(),
            ],
        );
        Ok(Self {
            provider_profile_id,
            authority_namespace_id,
            provider_cluster_id,
            provider_incarnation,
            key_id,
            key_version,
            role,
            algorithm,
            identity_sha256,
        })
    }
}

#[derive(Clone, PartialEq, Eq)]
struct ExternalKeysetIdentityV1 {
    handle: OpaqueKeyVersionRefV1,
    inner_transport: OpaqueKeyVersionRefV1,
    outer_channel: OpaqueKeyVersionRefV1,
    identity_sha256: [u8; 32],
}

impl fmt::Debug for ExternalKeysetIdentityV1 {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        formatter
            .debug_struct("ExternalKeysetIdentityV1")
            .field("identity", &"[THREE_OPAQUE_KEY_VERSIONS]")
            .finish_non_exhaustive()
    }
}

impl ExternalKeysetIdentityV1 {
    fn try_new(
        handle: OpaqueKeyVersionRefV1,
        inner_transport: OpaqueKeyVersionRefV1,
        outer_channel: OpaqueKeyVersionRefV1,
    ) -> ContractResult<Self> {
        let refs = [&handle, &inner_transport, &outer_channel];
        if handle.role != OpaqueKeyRoleV1::Handle
            || inner_transport.role != OpaqueKeyRoleV1::InnerTransport
            || outer_channel.role != OpaqueKeyRoleV1::OuterChannel
            || refs
                .iter()
                .any(|key_ref| key_ref.provider_profile_id != handle.provider_profile_id)
            || refs
                .iter()
                .any(|key_ref| key_ref.authority_namespace_id != handle.authority_namespace_id)
            || refs
                .iter()
                .any(|key_ref| key_ref.provider_cluster_id != handle.provider_cluster_id)
            || refs
                .iter()
                .any(|key_ref| key_ref.provider_incarnation != handle.provider_incarnation)
            || handle.key_id == inner_transport.key_id
            || handle.key_id == outer_channel.key_id
            || inner_transport.key_id == outer_channel.key_id
            || handle.identity_sha256 == inner_transport.identity_sha256
            || handle.identity_sha256 == outer_channel.identity_sha256
            || inner_transport.identity_sha256 == outer_channel.identity_sha256
        {
            return Err(contract_error(
                "track_b_external_authority_v1_keyset",
                "three immutable opaque key versions must be provider-aligned and role-distinct",
            ));
        }
        let identity_sha256 = framed_digest(
            KEYSET_DOMAIN,
            &[
                POLICY_ID.as_bytes(),
                &handle.identity_sha256,
                &inner_transport.identity_sha256,
                &outer_channel.identity_sha256,
            ],
        );
        Ok(Self {
            handle,
            inner_transport,
            outer_channel,
            identity_sha256,
        })
    }
}

#[derive(Clone)]
struct ExternalCurrentnessRequestV1 {
    provider_profile_id: String,
    authority_namespace_id: String,
    tenant_id: String,
    audience: String,
    operation_id: [u8; 32],
    challenge: [u8; 32],
    expected_epoch: u64,
    expected_epoch_record_sha256: [u8; 32],
    registry_generation_id: [u8; 32],
    receiver_identity_sha256: [u8; 32],
    build_identity_sha256: [u8; 32],
    allowlist_sha256: [u8; 32],
    keyset_identity_sha256: [u8; 32],
    trust_policy_sha256: [u8; 32],
}

impl fmt::Debug for ExternalCurrentnessRequestV1 {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        formatter
            .debug_struct("ExternalCurrentnessRequestV1")
            .field("expected_epoch", &self.expected_epoch)
            .field("scope", &"[COMMITMENT_BOUND]")
            .finish_non_exhaustive()
    }
}

fn validate_request(request: &ExternalCurrentnessRequestV1) -> ContractResult<()> {
    if !valid_label(&request.provider_profile_id)
        || !valid_label(&request.authority_namespace_id)
        || !valid_label(&request.tenant_id)
        || !valid_label(&request.audience)
        || request.expected_epoch == 0
    {
        return Err(contract_error(
            "track_b_external_authority_v1_request_scope",
            "request scope labels and expected epoch must be canonical and nonzero",
        ));
    }
    let commitments = [
        request.operation_id,
        request.challenge,
        request.expected_epoch_record_sha256,
        request.registry_generation_id,
        request.receiver_identity_sha256,
        request.build_identity_sha256,
        request.allowlist_sha256,
        request.keyset_identity_sha256,
        request.trust_policy_sha256,
    ];
    if !commitments.iter().all(nonzero) {
        return Err(contract_error(
            "track_b_external_authority_v1_request_commitment",
            "operation, challenge, record, generation, scope, keyset, and trust commitments are required",
        ));
    }
    Ok(())
}

fn request_digest(request: &ExternalCurrentnessRequestV1) -> ContractResult<[u8; 32]> {
    validate_request(request)?;
    let epoch = request.expected_epoch.to_be_bytes();
    Ok(framed_digest(
        REQUEST_DOMAIN,
        &[
            POLICY_ID.as_bytes(),
            ALGORITHM.as_bytes(),
            LEASE_PROFILE.as_bytes(),
            request.provider_profile_id.as_bytes(),
            request.authority_namespace_id.as_bytes(),
            request.tenant_id.as_bytes(),
            request.audience.as_bytes(),
            &request.operation_id,
            &request.challenge,
            &epoch,
            &request.expected_epoch_record_sha256,
            &request.registry_generation_id,
            &request.receiver_identity_sha256,
            &request.build_identity_sha256,
            &request.allowlist_sha256,
            &request.keyset_identity_sha256,
            &request.trust_policy_sha256,
        ],
    ))
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
enum ExternalAuthorityStateV1 {
    Active,
    Fencing,
    Pending,
    Revoked,
    Indeterminate,
}

impl ExternalAuthorityStateV1 {
    fn label(self) -> &'static str {
        match self {
            Self::Active => ACTIVE_STATE,
            Self::Fencing => "FENCING",
            Self::Pending => "PENDING",
            Self::Revoked => "REVOKED",
            Self::Indeterminate => "INDETERMINATE",
        }
    }
}

#[derive(Clone)]
struct SignedExternalCurrentnessDecisionV1 {
    request_sha256: [u8; 32],
    state: ExternalAuthorityStateV1,
    provider_cluster_id: String,
    provider_incarnation: [u8; 32],
    leader_term: u64,
    committed_revision: u64,
    authority_sequence: u64,
    active_epoch: u64,
    active_epoch_record_sha256: [u8; 32],
    active_registry_generation_id: [u8; 32],
    active_keyset_identity_sha256: [u8; 32],
    revocation_checkpoint_sha256: [u8; 32],
    revoked_through_epoch: u64,
    provider_custody_claim_sha256: [u8; 32],
    provider_old_key_use_denied_claim_sha256: [u8; 32],
    decision_id: [u8; 32],
    signer_key_id: String,
    signer_key_version: u64,
    ed25519_signature: [u8; 64],
}

impl fmt::Debug for SignedExternalCurrentnessDecisionV1 {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        formatter
            .debug_struct("SignedExternalCurrentnessDecisionV1")
            .field("state", &self.state)
            .field("authority_sequence", &self.authority_sequence)
            .field("authentication", &"[ED25519_REDACTED]")
            .finish_non_exhaustive()
    }
}

fn decision_message(decision: &SignedExternalCurrentnessDecisionV1) -> Vec<u8> {
    let leader_term = decision.leader_term.to_be_bytes();
    let committed_revision = decision.committed_revision.to_be_bytes();
    let authority_sequence = decision.authority_sequence.to_be_bytes();
    let active_epoch = decision.active_epoch.to_be_bytes();
    let revoked_through_epoch = decision.revoked_through_epoch.to_be_bytes();
    let signer_key_version = decision.signer_key_version.to_be_bytes();
    framed_message(
        DECISION_DOMAIN,
        &[
            POLICY_ID.as_bytes(),
            ALGORITHM.as_bytes(),
            LEASE_PROFILE.as_bytes(),
            &decision.request_sha256,
            decision.state.label().as_bytes(),
            decision.provider_cluster_id.as_bytes(),
            &decision.provider_incarnation,
            &leader_term,
            &committed_revision,
            &authority_sequence,
            &active_epoch,
            &decision.active_epoch_record_sha256,
            &decision.active_registry_generation_id,
            &decision.active_keyset_identity_sha256,
            &decision.revocation_checkpoint_sha256,
            &revoked_through_epoch,
            &decision.provider_custody_claim_sha256,
            &decision.provider_old_key_use_denied_claim_sha256,
            &decision.decision_id,
            decision.signer_key_id.as_bytes(),
            &signer_key_version,
        ],
    )
}

/// All trust-anchor material is expected to be owner-pinned out of band. The
/// only constructor in S9 is test-only, so repository contents cannot create a
/// production authority permit.
struct ExternalAuthorityTrustPermitV1 {
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
    minimum_committed_revision: u64,
    ed25519_public_key: [u8; 32],
}

impl fmt::Debug for ExternalAuthorityTrustPermitV1 {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        formatter
            .debug_struct("ExternalAuthorityTrustPermitV1")
            .field("provider_profile_id", &self.provider_profile_id)
            .field("trust_anchor", &"[OWNER_PINNED_PUBLIC_KEY]")
            .finish_non_exhaustive()
    }
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
enum ExternalProviderFailureV1 {
    Timeout,
    Unavailable,
    Unauthenticated,
    Unauthorized,
    Stale,
    Revoked,
    Conflict,
    RateLimited,
    Malformed,
    Indeterminate,
}

mod currentness_provider_seal {
    pub(super) trait Sealed {}
}

/// A future adapter must make one online request per attempted admission. No
/// cached receipt or local fallback satisfies this interface's contract.
trait ExternalCurrentnessProviderV1: currentness_provider_seal::Sealed {
    fn request_currentness(
        &self,
        request: &ExternalCurrentnessRequestV1,
    ) -> Result<SignedExternalCurrentnessDecisionV1, ExternalProviderFailureV1>;
}

#[allow(dead_code)]
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
enum ExternalKeyStateV1 {
    Enabled,
    UseDenied,
    PendingDeletion,
    Destroyed,
    Unknown,
}

#[allow(dead_code)]
struct ExternalKeyStateRequestV1 {
    operation_id: [u8; 32],
    challenge: [u8; 32],
    key_ref: OpaqueKeyVersionRefV1,
    epoch_record_sha256: [u8; 32],
    minimum_custody_revision: u64,
}

/// Untrusted provider observation shape. S9 intentionally has no independent
/// custodian trust permit or signature verifier; this value cannot contribute
/// authority until a later tranche adds and admits that separate mechanism.
#[allow(dead_code)]
struct ExternalKeyStateObservationV1 {
    request_sha256: [u8; 32],
    state: ExternalKeyStateV1,
    custody_revision: u64,
    provider_incarnation: [u8; 32],
}

fn key_state_request_digest(request: &ExternalKeyStateRequestV1) -> ContractResult<[u8; 32]> {
    if ![
        request.operation_id,
        request.challenge,
        request.key_ref.identity_sha256,
        request.epoch_record_sha256,
    ]
    .iter()
    .all(nonzero)
        || request.minimum_custody_revision == 0
    {
        return Err(contract_error(
            "track_b_external_authority_v1_key_state_request",
            "key-state request requires one-attempt identity, exact key, epoch, and revision",
        ));
    }
    let revision = request.minimum_custody_revision.to_be_bytes();
    Ok(framed_digest(
        KEY_STATE_REQUEST_DOMAIN,
        &[
            POLICY_ID.as_bytes(),
            LEASE_PROFILE.as_bytes(),
            &request.operation_id,
            &request.challenge,
            &request.key_ref.identity_sha256,
            &request.epoch_record_sha256,
            &revision,
        ],
    ))
}

mod key_custodian_seal {
    #[allow(dead_code)]
    pub(super) trait Sealed {}
}

/// This preregistered interface never returns raw key material. Its observation
/// is explicitly untrusted in S9: `PendingDeletion`, `Unknown`, provider
/// errors, and ambiguous mutations do not constitute destruction/use denial,
/// and no observation can affect a currentness token.
#[allow(dead_code)]
trait ExternalKeyCustodianV1: key_custodian_seal::Sealed {
    fn request_key_state(
        &self,
        request: &ExternalKeyStateRequestV1,
    ) -> Result<ExternalKeyStateObservationV1, ExternalProviderFailureV1>;
}

#[must_use]
struct VerifiedExternalCurrentnessV1 {
    request_sha256: [u8; 32],
    decision_sha256: [u8; 32],
    authority_sequence: u64,
    committed_revision: u64,
}

impl fmt::Debug for VerifiedExternalCurrentnessV1 {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        formatter
            .debug_struct("VerifiedExternalCurrentnessV1")
            .field("authority_sequence", &self.authority_sequence)
            .field("committed_revision", &self.committed_revision)
            .field("scope", &"[SINGLE_ATTEMPT_NON_SERIALIZABLE]")
            .finish_non_exhaustive()
    }
}

fn validate_permit(permit: &ExternalAuthorityTrustPermitV1) -> ContractResult<()> {
    if !valid_label(&permit.provider_profile_id)
        || !valid_label(&permit.authority_namespace_id)
        || !valid_label(&permit.tenant_id)
        || !valid_label(&permit.audience)
        || !valid_label(&permit.provider_cluster_id)
        || !valid_label(&permit.signer_key_id)
        || permit.signer_key_version == 0
        || permit.minimum_leader_term == 0
        || permit.minimum_committed_revision == 0
        || !nonzero(&permit.provider_incarnation)
        || !nonzero(&permit.trust_policy_sha256)
        || !nonzero(&permit.ed25519_public_key)
    {
        return Err(contract_error(
            "track_b_external_authority_v1_trust_permit",
            "owner-pinned provider, signer, policy, floor, and public-key identity are required",
        ));
    }
    Ok(())
}

fn verify_external_currentness_v1<P: ExternalCurrentnessProviderV1>(
    provider: &P,
    request: &ExternalCurrentnessRequestV1,
    permit: &ExternalAuthorityTrustPermitV1,
) -> ContractResult<VerifiedExternalCurrentnessV1> {
    validate_permit(permit)?;
    let expected_request_sha256 = request_digest(request)?;
    if request.provider_profile_id != permit.provider_profile_id
        || request.authority_namespace_id != permit.authority_namespace_id
        || request.tenant_id != permit.tenant_id
        || request.audience != permit.audience
        || request.trust_policy_sha256 != permit.trust_policy_sha256
    {
        return Err(contract_error(
            "track_b_external_authority_v1_trust_scope",
            "request scope does not match the owner-pinned permit",
        ));
    }

    let decision = provider.request_currentness(request).map_err(|failure| {
        let detail = match failure {
            ExternalProviderFailureV1::Timeout => "external provider timed out",
            ExternalProviderFailureV1::Unavailable => "external provider unavailable",
            ExternalProviderFailureV1::Unauthenticated => "provider channel unauthenticated",
            ExternalProviderFailureV1::Unauthorized => "provider denied the request",
            ExternalProviderFailureV1::Stale => "provider rejected stale state",
            ExternalProviderFailureV1::Revoked => "provider reports revoked state",
            ExternalProviderFailureV1::Conflict => "provider rejected a duplicate or conflict",
            ExternalProviderFailureV1::RateLimited => "provider rate limited the request",
            ExternalProviderFailureV1::Malformed => "provider returned malformed data",
            ExternalProviderFailureV1::Indeterminate => "provider result is indeterminate",
        };
        contract_error("track_b_external_authority_v1_provider_failure", detail)
    })?;

    if decision.request_sha256 != expected_request_sha256 {
        return Err(contract_error(
            "track_b_external_authority_v1_request_binding",
            "signed decision does not bind the exact one-attempt request",
        ));
    }

    let message = decision_message(&decision);
    UnparsedPublicKey::new(&ED25519, permit.ed25519_public_key)
        .verify(&message, &decision.ed25519_signature)
        .map_err(|_| {
            contract_error(
                "track_b_external_authority_v1_signature",
                "Ed25519 authentication of the exact decision failed",
            )
        })?;

    if decision.state != ExternalAuthorityStateV1::Active {
        return Err(contract_error(
            "track_b_external_authority_v1_not_active",
            "FENCING, PENDING, REVOKED, and INDETERMINATE never admit",
        ));
    }
    if decision.provider_cluster_id != permit.provider_cluster_id
        || decision.provider_incarnation != permit.provider_incarnation
        || decision.signer_key_id != permit.signer_key_id
        || decision.signer_key_version != permit.signer_key_version
    {
        return Err(contract_error(
            "track_b_external_authority_v1_provider_identity",
            "provider cluster/incarnation and immutable signer identity must match the pinned permit",
        ));
    }
    if decision.leader_term < permit.minimum_leader_term
        || decision.committed_revision < permit.minimum_committed_revision
        || decision.authority_sequence == 0
    {
        return Err(contract_error(
            "track_b_external_authority_v1_monotonic_floor",
            "leader term, committed revision, and authority sequence must satisfy pinned floors",
        ));
    }
    if decision.active_epoch != request.expected_epoch
        || decision.active_epoch_record_sha256 != request.expected_epoch_record_sha256
        || decision.active_registry_generation_id != request.registry_generation_id
        || decision.active_keyset_identity_sha256 != request.keyset_identity_sha256
    {
        return Err(contract_error(
            "track_b_external_authority_v1_active_identity",
            "ACTIVE decision does not match the exact expected epoch, record, generation, and keyset",
        ));
    }
    if decision
        .revoked_through_epoch
        .checked_add(1)
        .is_none_or(|next| next != decision.active_epoch)
        || ![
            decision.revocation_checkpoint_sha256,
            decision.provider_custody_claim_sha256,
            decision.provider_old_key_use_denied_claim_sha256,
            decision.decision_id,
        ]
        .iter()
        .all(nonzero)
    {
        return Err(contract_error(
            "track_b_external_authority_v1_revocation_custody",
            "ACTIVE requires predecessor fencing plus nonzero revocation and provider-claim commitments",
        ));
    }

    Ok(VerifiedExternalCurrentnessV1 {
        request_sha256: expected_request_sha256,
        decision_sha256: sha256_bytes(&message),
        authority_sequence: decision.authority_sequence,
        committed_revision: decision.committed_revision,
    })
}

#[cfg(test)]
mod tests {
    use super::*;
    use ring::signature::{Ed25519KeyPair, KeyPair};
    use std::collections::BTreeSet;
    use std::sync::Mutex;

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
    struct SyntheticProviderIdentityV1 {
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
    }

    fn commitment(byte: u8) -> [u8; 32] {
        [byte; 32]
    }

    fn identity() -> SyntheticProviderIdentityV1 {
        SyntheticProviderIdentityV1 {
            provider_profile_id: "owner-selected-provider-v1".to_string(),
            authority_namespace_id: "agent-bridge-research-prod".to_string(),
            tenant_id: "agent-bridge".to_string(),
            audience: "ab-store-restore-admission".to_string(),
            provider_cluster_id: "authority-cluster-a".to_string(),
            provider_incarnation: commitment(0x61),
            signer_key_id: "currentness-signer-a".to_string(),
            signer_key_version: 3,
            trust_policy_sha256: commitment(0x71),
            leader_term: 7,
        }
    }

    fn keyset() -> ExternalKeysetIdentityV1 {
        let identity = identity();
        ExternalKeysetIdentityV1::try_new(
            OpaqueKeyVersionRefV1::try_new(
                &identity.provider_profile_id,
                &identity.authority_namespace_id,
                &identity.provider_cluster_id,
                identity.provider_incarnation,
                "handle-key",
                11,
                OpaqueKeyRoleV1::Handle,
                "hmac-sha-256",
            )
            .expect("valid handle ref"),
            OpaqueKeyVersionRefV1::try_new(
                &identity.provider_profile_id,
                &identity.authority_namespace_id,
                &identity.provider_cluster_id,
                identity.provider_incarnation,
                "inner-key",
                12,
                OpaqueKeyRoleV1::InnerTransport,
                "hmac-sha-256",
            )
            .expect("valid inner ref"),
            OpaqueKeyVersionRefV1::try_new(
                &identity.provider_profile_id,
                &identity.authority_namespace_id,
                &identity.provider_cluster_id,
                identity.provider_incarnation,
                "outer-key",
                13,
                OpaqueKeyRoleV1::OuterChannel,
                "hmac-sha-256",
            )
            .expect("valid outer ref"),
        )
        .expect("valid keyset")
    }

    fn request() -> ExternalCurrentnessRequestV1 {
        let identity = identity();
        ExternalCurrentnessRequestV1 {
            provider_profile_id: identity.provider_profile_id,
            authority_namespace_id: identity.authority_namespace_id,
            tenant_id: identity.tenant_id,
            audience: identity.audience,
            operation_id: commitment(0x21),
            challenge: commitment(0x31),
            expected_epoch: 2,
            expected_epoch_record_sha256: commitment(0x41),
            registry_generation_id: commitment(0x42),
            receiver_identity_sha256: commitment(0x43),
            build_identity_sha256: commitment(0x44),
            allowlist_sha256: commitment(0x45),
            keyset_identity_sha256: keyset().identity_sha256,
            trust_policy_sha256: identity.trust_policy_sha256,
        }
    }

    fn permit_for(
        identity: &SyntheticProviderIdentityV1,
        public_key: [u8; 32],
        minimum_revision: u64,
    ) -> ExternalAuthorityTrustPermitV1 {
        ExternalAuthorityTrustPermitV1 {
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
            minimum_committed_revision: minimum_revision,
            ed25519_public_key: public_key,
        }
    }

    fn key_pair(seed: &[u8; 32]) -> Ed25519KeyPair {
        Ed25519KeyPair::from_seed_unchecked(seed).expect("fixed Ed25519 seed")
    }

    fn provider_public_key(seed: &[u8; 32]) -> [u8; 32] {
        key_pair(seed)
            .public_key()
            .as_ref()
            .try_into()
            .expect("Ed25519 public key is 32 bytes")
    }

    fn sign_decision(
        seed: &[u8; 32],
        identity: &SyntheticProviderIdentityV1,
        request: &ExternalCurrentnessRequestV1,
        state: ExternalAuthorityStateV1,
        authority_sequence: u64,
        committed_revision: u64,
    ) -> SignedExternalCurrentnessDecisionV1 {
        let request_sha256 = request_digest(request).expect("valid request");
        let epoch = request.expected_epoch.to_be_bytes();
        let revision = committed_revision.to_be_bytes();
        let revocation_checkpoint_sha256 = framed_digest(
            b"agent-bridge/track-b/external-authority-provider/revocation-checkpoint/v1",
            &[&request_sha256, &revision],
        );
        let provider_custody_claim_sha256 = framed_digest(
            b"agent-bridge/track-b/external-authority-provider/custody-claim/v1",
            &[&request.keyset_identity_sha256, &epoch, &revision],
        );
        let provider_old_key_use_denied_claim_sha256 = framed_digest(
            b"agent-bridge/track-b/external-authority-provider/use-denied-claim/v1",
            &[&request.expected_epoch_record_sha256, &epoch, &revision],
        );
        let decision_id = framed_digest(
            b"agent-bridge/track-b/external-authority-provider/decision-id/v1",
            &[&request.operation_id, &request.challenge, &revision],
        );
        let mut decision = SignedExternalCurrentnessDecisionV1 {
            request_sha256,
            state,
            provider_cluster_id: identity.provider_cluster_id.clone(),
            provider_incarnation: identity.provider_incarnation,
            leader_term: identity.leader_term,
            committed_revision,
            authority_sequence,
            active_epoch: request.expected_epoch,
            active_epoch_record_sha256: request.expected_epoch_record_sha256,
            active_registry_generation_id: request.registry_generation_id,
            active_keyset_identity_sha256: request.keyset_identity_sha256,
            revocation_checkpoint_sha256,
            revoked_through_epoch: request.expected_epoch - 1,
            provider_custody_claim_sha256,
            provider_old_key_use_denied_claim_sha256,
            decision_id,
            signer_key_id: identity.signer_key_id.clone(),
            signer_key_version: identity.signer_key_version,
            ed25519_signature: [0; 64],
        };
        decision.ed25519_signature = key_pair(seed)
            .sign(&decision_message(&decision))
            .as_ref()
            .try_into()
            .expect("Ed25519 signature is 64 bytes");
        decision
    }

    struct SyntheticProviderStateV1 {
        used_operation_ids: BTreeSet<[u8; 32]>,
        used_challenges: BTreeSet<[u8; 32]>,
        authority_sequence: u64,
        committed_revision: u64,
    }

    struct SyntheticConformingExternalProviderV1 {
        seed: [u8; 32],
        identity: SyntheticProviderIdentityV1,
        state: ExternalAuthorityStateV1,
        inner: Mutex<SyntheticProviderStateV1>,
    }

    impl currentness_provider_seal::Sealed for SyntheticConformingExternalProviderV1 {}

    impl SyntheticConformingExternalProviderV1 {
        fn new(seed: [u8; 32], state: ExternalAuthorityStateV1, initial_revision: u64) -> Self {
            Self {
                seed,
                identity: identity(),
                state,
                inner: Mutex::new(SyntheticProviderStateV1 {
                    used_operation_ids: BTreeSet::new(),
                    used_challenges: BTreeSet::new(),
                    authority_sequence: 0,
                    committed_revision: initial_revision,
                }),
            }
        }
    }

    impl Drop for SyntheticConformingExternalProviderV1 {
        fn drop(&mut self) {
            self.seed.fill(0);
        }
    }

    impl ExternalCurrentnessProviderV1 for SyntheticConformingExternalProviderV1 {
        fn request_currentness(
            &self,
            request: &ExternalCurrentnessRequestV1,
        ) -> Result<SignedExternalCurrentnessDecisionV1, ExternalProviderFailureV1> {
            validate_request(request).map_err(|_| ExternalProviderFailureV1::Malformed)?;
            let mut inner = self
                .inner
                .lock()
                .map_err(|_| ExternalProviderFailureV1::Indeterminate)?;
            if inner.used_operation_ids.contains(&request.operation_id)
                || inner.used_challenges.contains(&request.challenge)
            {
                return Err(ExternalProviderFailureV1::Conflict);
            }
            inner.used_operation_ids.insert(request.operation_id);
            inner.used_challenges.insert(request.challenge);
            inner.authority_sequence = inner
                .authority_sequence
                .checked_add(1)
                .ok_or(ExternalProviderFailureV1::Indeterminate)?;
            inner.committed_revision = inner
                .committed_revision
                .checked_add(1)
                .ok_or(ExternalProviderFailureV1::Indeterminate)?;
            Ok(sign_decision(
                &self.seed,
                &self.identity,
                request,
                self.state,
                inner.authority_sequence,
                inner.committed_revision,
            ))
        }
    }

    struct StaticExternalProviderV1 {
        result: Result<SignedExternalCurrentnessDecisionV1, ExternalProviderFailureV1>,
    }

    impl currentness_provider_seal::Sealed for StaticExternalProviderV1 {}

    impl ExternalCurrentnessProviderV1 for StaticExternalProviderV1 {
        fn request_currentness(
            &self,
            _request: &ExternalCurrentnessRequestV1,
        ) -> Result<SignedExternalCurrentnessDecisionV1, ExternalProviderFailureV1> {
            self.result.clone()
        }
    }

    fn static_provider(decision: SignedExternalCurrentnessDecisionV1) -> StaticExternalProviderV1 {
        StaticExternalProviderV1 {
            result: Ok(decision),
        }
    }

    fn hex(bytes: &[u8]) -> String {
        bytes.iter().map(|byte| format!("{byte:02x}")).collect()
    }

    #[test]
    fn s9_known_answer_ed25519_and_framing_are_stable() {
        assert_eq!(provider_public_key(&RFC8032_SEED), RFC8032_PUBLIC_KEY);
        let request = request();
        let decision = sign_decision(
            &RFC8032_SEED,
            &identity(),
            &request,
            ExternalAuthorityStateV1::Active,
            1,
            42,
        );
        assert_eq!(
            hex(&request_digest(&request).expect("request digest")),
            "01d433a73bee905b5d65556b9ba4165716a87cf6142f61ef4147198e390077f1"
        );
        assert_eq!(
            hex(&sha256_bytes(&decision_message(&decision))),
            "e35d9917772887d0ffdbd17f8c8781d93e42e79250483139d400ea46392daab1"
        );
        assert_eq!(
            hex(&decision.ed25519_signature),
            "0f530350eb467fd7d10f3a6df04cbb988397d323633244e139f09ec5d33e79a62fb667a312fb495bc76f23a068a779c78aca8ae9ce88b8a3e77bbcd42496600f"
        );
    }

    #[test]
    fn s9_exact_scope_and_active_decision_produce_private_single_attempt_token() {
        let provider = SyntheticConformingExternalProviderV1::new(
            RFC8032_SEED,
            ExternalAuthorityStateV1::Active,
            41,
        );
        let request = request();
        let permit = permit_for(&identity(), RFC8032_PUBLIC_KEY, 42);
        let token = verify_external_currentness_v1(&provider, &request, &permit)
            .expect("exact ACTIVE response should verify");
        assert_eq!(token.request_sha256, request_digest(&request).unwrap());
        assert_eq!(token.authority_sequence, 1);
        assert_eq!(token.committed_revision, 42);
        assert!(nonzero(&token.decision_sha256));
        assert!(format!("{token:?}").contains("SINGLE_ATTEMPT_NON_SERIALIZABLE"));
    }

    #[test]
    fn s9_every_request_scope_field_tamper_rejects() {
        let original = request();
        let decision = sign_decision(
            &RFC8032_SEED,
            &identity(),
            &original,
            ExternalAuthorityStateV1::Active,
            1,
            42,
        );
        let permit = permit_for(&identity(), RFC8032_PUBLIC_KEY, 42);
        let mut mutations = Vec::new();
        macro_rules! mutated {
            ($field:ident, $value:expr) => {{
                let mut value = original.clone();
                value.$field = $value;
                mutations.push(value);
            }};
        }
        mutated!(provider_profile_id, "other-provider".to_string());
        mutated!(authority_namespace_id, "other-namespace".to_string());
        mutated!(tenant_id, "other-tenant".to_string());
        mutated!(audience, "other-audience".to_string());
        mutated!(operation_id, commitment(0x91));
        mutated!(challenge, commitment(0x92));
        mutated!(expected_epoch, 3);
        mutated!(expected_epoch_record_sha256, commitment(0x93));
        mutated!(registry_generation_id, commitment(0x94));
        mutated!(receiver_identity_sha256, commitment(0x95));
        mutated!(build_identity_sha256, commitment(0x96));
        mutated!(allowlist_sha256, commitment(0x97));
        mutated!(keyset_identity_sha256, commitment(0x98));
        mutated!(trust_policy_sha256, commitment(0x99));
        for mutation in mutations {
            assert!(verify_external_currentness_v1(
                &static_provider(decision.clone()),
                &mutation,
                &permit
            )
            .is_err());
        }
    }

    #[test]
    fn s9_every_signed_decision_field_tamper_rejects() {
        let request = request();
        let original = sign_decision(
            &RFC8032_SEED,
            &identity(),
            &request,
            ExternalAuthorityStateV1::Active,
            1,
            42,
        );
        let permit = permit_for(&identity(), RFC8032_PUBLIC_KEY, 42);
        let mut mutations = Vec::new();
        macro_rules! changed {
            ($field:ident, $value:expr) => {{
                let mut value = original.clone();
                value.$field = $value;
                mutations.push(value);
            }};
        }
        changed!(request_sha256, commitment(0xa1));
        changed!(provider_cluster_id, "other-cluster".to_string());
        changed!(provider_incarnation, commitment(0xa2));
        changed!(leader_term, 8);
        changed!(committed_revision, 43);
        changed!(authority_sequence, 2);
        changed!(active_epoch, 3);
        changed!(active_epoch_record_sha256, commitment(0xa3));
        changed!(active_registry_generation_id, commitment(0xa4));
        changed!(active_keyset_identity_sha256, commitment(0xa5));
        changed!(revocation_checkpoint_sha256, commitment(0xa6));
        changed!(revoked_through_epoch, 0);
        changed!(provider_custody_claim_sha256, commitment(0xa7));
        changed!(provider_old_key_use_denied_claim_sha256, commitment(0xa8));
        changed!(decision_id, commitment(0xa9));
        changed!(signer_key_id, "other-signer".to_string());
        changed!(signer_key_version, 4);
        let mut signature = original.clone();
        signature.ed25519_signature[0] ^= 1;
        mutations.push(signature);
        for mutation in mutations {
            assert!(
                verify_external_currentness_v1(&static_provider(mutation), &request, &permit)
                    .is_err()
            );
        }
    }

    #[test]
    fn s9_wrong_trust_key_signer_identity_and_rotation_require_new_permit() {
        let request = request();
        let decision = sign_decision(
            &RFC8032_SEED,
            &identity(),
            &request,
            ExternalAuthorityStateV1::Active,
            1,
            42,
        );
        let mut wrong_key = permit_for(&identity(), commitment(0xb1), 42);
        assert_eq!(
            verify_external_currentness_v1(
                &static_provider(decision.clone()),
                &request,
                &wrong_key
            )
            .unwrap_err()
            .code(),
            "track_b_external_authority_v1_signature"
        );
        wrong_key.ed25519_public_key = RFC8032_PUBLIC_KEY;
        wrong_key.signer_key_version = 4;
        assert_eq!(
            verify_external_currentness_v1(&static_provider(decision), &request, &wrong_key)
                .unwrap_err()
                .code(),
            "track_b_external_authority_v1_provider_identity"
        );
    }

    #[test]
    fn s9_duplicate_challenge_and_request_are_rejected_by_one_provider_instance() {
        let provider = SyntheticConformingExternalProviderV1::new(
            RFC8032_SEED,
            ExternalAuthorityStateV1::Active,
            41,
        );
        let request = request();
        let permit = permit_for(&identity(), RFC8032_PUBLIC_KEY, 42);
        let _token =
            verify_external_currentness_v1(&provider, &request, &permit).expect("first use");
        assert_eq!(
            verify_external_currentness_v1(&provider, &request, &permit)
                .unwrap_err()
                .code(),
            "track_b_external_authority_v1_provider_failure"
        );
        let mut repeated_challenge = request.clone();
        repeated_challenge.operation_id = commitment(0xb2);
        assert!(verify_external_currentness_v1(&provider, &repeated_challenge, &permit).is_err());
    }

    #[test]
    fn s9_provider_reconstruction_can_replay_reused_challenge_unresolved_negative_evidence() {
        let request = request();
        let permit = permit_for(&identity(), RFC8032_PUBLIC_KEY, 42);
        for _provider_reconstruction in 0..2 {
            let provider = SyntheticConformingExternalProviderV1::new(
                RFC8032_SEED,
                ExternalAuthorityStateV1::Active,
                41,
            );
            let _token = verify_external_currentness_v1(&provider, &request, &permit).expect(
                "UNRESOLVED: in-memory challenge history is lost on provider reconstruction",
            );
        }
    }

    #[test]
    fn s9_non_active_states_never_issue_token() {
        let request = request();
        let permit = permit_for(&identity(), RFC8032_PUBLIC_KEY, 42);
        for state in [
            ExternalAuthorityStateV1::Fencing,
            ExternalAuthorityStateV1::Pending,
            ExternalAuthorityStateV1::Revoked,
            ExternalAuthorityStateV1::Indeterminate,
        ] {
            let decision = sign_decision(&RFC8032_SEED, &identity(), &request, state, 1, 42);
            assert_eq!(
                verify_external_currentness_v1(&static_provider(decision), &request, &permit)
                    .unwrap_err()
                    .code(),
                "track_b_external_authority_v1_not_active"
            );
        }
    }

    #[test]
    fn s9_all_provider_failures_have_no_fallback() {
        let request = request();
        let permit = permit_for(&identity(), RFC8032_PUBLIC_KEY, 42);
        for failure in [
            ExternalProviderFailureV1::Timeout,
            ExternalProviderFailureV1::Unavailable,
            ExternalProviderFailureV1::Unauthenticated,
            ExternalProviderFailureV1::Unauthorized,
            ExternalProviderFailureV1::Stale,
            ExternalProviderFailureV1::Revoked,
            ExternalProviderFailureV1::Conflict,
            ExternalProviderFailureV1::RateLimited,
            ExternalProviderFailureV1::Malformed,
            ExternalProviderFailureV1::Indeterminate,
        ] {
            let provider = StaticExternalProviderV1 {
                result: Err(failure),
            };
            assert_eq!(
                verify_external_currentness_v1(&provider, &request, &permit)
                    .unwrap_err()
                    .code(),
                "track_b_external_authority_v1_provider_failure"
            );
        }
    }

    #[test]
    fn s9_sequence_revision_epoch_and_floor_rules_fail_closed() {
        let request = request();
        let permit = permit_for(&identity(), RFC8032_PUBLIC_KEY, 42);
        for (sequence, revision) in [(0, 42), (1, 41)] {
            let decision = sign_decision(
                &RFC8032_SEED,
                &identity(),
                &request,
                ExternalAuthorityStateV1::Active,
                sequence,
                revision,
            );
            assert!(
                verify_external_currentness_v1(&static_provider(decision), &request, &permit)
                    .is_err()
            );
        }
        let overflow = SyntheticConformingExternalProviderV1 {
            seed: RFC8032_SEED,
            identity: identity(),
            state: ExternalAuthorityStateV1::Active,
            inner: Mutex::new(SyntheticProviderStateV1 {
                used_operation_ids: BTreeSet::new(),
                used_challenges: BTreeSet::new(),
                authority_sequence: u64::MAX,
                committed_revision: 41,
            }),
        };
        assert!(verify_external_currentness_v1(&overflow, &request, &permit).is_err());
        let revision_overflow = SyntheticConformingExternalProviderV1 {
            seed: RFC8032_SEED,
            identity: identity(),
            state: ExternalAuthorityStateV1::Active,
            inner: Mutex::new(SyntheticProviderStateV1 {
                used_operation_ids: BTreeSet::new(),
                used_challenges: BTreeSet::new(),
                authority_sequence: 0,
                committed_revision: u64::MAX,
            }),
        };
        assert!(verify_external_currentness_v1(&revision_overflow, &request, &permit).is_err());
    }

    #[test]
    fn s9_opaque_key_versions_bind_role_version_and_never_raw_key_material() {
        let set = keyset();
        assert_ne!(
            set.handle.identity_sha256,
            set.inner_transport.identity_sha256
        );
        assert_ne!(
            set.inner_transport.identity_sha256,
            set.outer_channel.identity_sha256
        );
        let changed_version = OpaqueKeyVersionRefV1::try_new(
            &set.handle.provider_profile_id,
            &set.handle.authority_namespace_id,
            &set.handle.provider_cluster_id,
            set.handle.provider_incarnation,
            &set.handle.key_id,
            set.handle.key_version + 1,
            OpaqueKeyRoleV1::Handle,
            &set.handle.algorithm,
        )
        .expect("changed immutable version");
        assert_ne!(changed_version.identity_sha256, set.handle.identity_sha256);
        assert!(format!("{set:?}").contains("THREE_OPAQUE_KEY_VERSIONS"));
        assert!(ExternalKeysetIdentityV1::try_new(
            set.inner_transport.clone(),
            set.handle.clone(),
            set.outer_channel.clone()
        )
        .is_err());
        let mut cross_cluster = set.outer_channel.clone();
        cross_cluster.provider_cluster_id = "other-cluster".to_string();
        assert!(ExternalKeysetIdentityV1::try_new(
            set.handle.clone(),
            set.inner_transport.clone(),
            cross_cluster
        )
        .is_err());

        let key_state = ExternalKeyStateRequestV1 {
            operation_id: commitment(0xc1),
            challenge: commitment(0xc2),
            key_ref: set.handle.clone(),
            epoch_record_sha256: commitment(0xc3),
            minimum_custody_revision: 9,
        };
        let key_state_request_sha256 = key_state_request_digest(&key_state).unwrap();
        assert!(nonzero(&key_state_request_sha256));
    }

    #[test]
    fn s9_malformed_zero_and_noncanonical_inputs_reject() {
        let mut malformed = request();
        malformed.challenge = ZERO_COMMITMENT;
        assert!(request_digest(&malformed).is_err());
        malformed = request();
        malformed.provider_profile_id = "Upper Case".to_string();
        assert!(request_digest(&malformed).is_err());
        assert!(OpaqueKeyVersionRefV1::try_new(
            "provider",
            "namespace",
            "cluster",
            commitment(0xd1),
            "key",
            0,
            OpaqueKeyRoleV1::Handle,
            "hmac-sha-256"
        )
        .is_err());
        let mut permit = permit_for(&identity(), RFC8032_PUBLIC_KEY, 42);
        permit.provider_incarnation = ZERO_COMMITMENT;
        assert!(validate_permit(&permit).is_err());
    }

    #[test]
    fn s9_revocation_after_verified_snapshot_cannot_recall_token_negative_evidence() {
        let request = request();
        let permit = permit_for(&identity(), RFC8032_PUBLIC_KEY, 42);
        let active_snapshot = sign_decision(
            &RFC8032_SEED,
            &identity(),
            &request,
            ExternalAuthorityStateV1::Active,
            1,
            42,
        );
        let token =
            verify_external_currentness_v1(&static_provider(active_snapshot), &request, &permit)
                .expect("snapshot was ACTIVE at signing time");
        let mut revocation_query = request.clone();
        revocation_query.operation_id = commitment(0xe1);
        revocation_query.challenge = commitment(0xe2);
        let revoked = sign_decision(
            &RFC8032_SEED,
            &identity(),
            &revocation_query,
            ExternalAuthorityStateV1::Revoked,
            2,
            43,
        );
        assert_eq!(
            verify_external_currentness_v1(
                &static_provider(revoked),
                &revocation_query,
                &permit_for(&identity(), RFC8032_PUBLIC_KEY, 42)
            )
            .unwrap_err()
            .code(),
            "track_b_external_authority_v1_not_active"
        );
        assert_eq!(token.authority_sequence, 1);
        assert!(nonzero(&token.decision_sha256));
        // UNRESOLVED: a later REVOKED response cannot recall an already returned token.
    }

    #[test]
    fn s9_contract_has_zero_reusable_lease_and_no_clock_or_cache() {
        assert_eq!(LEASE_PROFILE, "ONE_ATTEMPT_NO_CACHE_NO_WALL_CLOCK");
        assert!(!LEASE_PROFILE.contains("TTL"));
        assert!(!LEASE_PROFILE.contains("REUSE"));
        assert_eq!(ALGORITHM, "Ed25519");
        assert_eq!(ACTIVE_STATE, "ACTIVE");
    }
}
