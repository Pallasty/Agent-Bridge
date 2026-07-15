//! S12 synthetic recovered-S9 decision re-verification preregistration.
//!
//! This private, default-off module joins three already-frozen protocol
//! boundaries without adding a runtime carrier: an authenticated S10
//! `COMMITTED` recovery observation, an independently authenticated S11 L1
//! operation record, and the complete canonical S9 request/decision bytes.
//! The original S9 decision is verified by the shared detached verifier. No
//! provider, recovery lookup, signer, network, clock, cache, database,
//! `StateStore`, Bridge, retry, replay consumption, or downstream action is
//! called here.
//!
//! Success proves only that exact historical bytes authenticate and cross-bind
//! to one already-verified synthetic recovery observation. It neither revives
//! S9's one-attempt currentness token nor proves currentness at downstream use.
//! S11 synthetic L2 revision/checksum metadata is deliberately unread and is
//! excluded from the historical commitment.

#![cfg_attr(not(test), allow(dead_code))]

use super::external_authority_operation_state_machine::{
    verify_signed_committed_operation_l1_v1, AtomicAuthorityOperationRequestV1,
    AtomicAuthorityOperationTrustPermitV1, SignedCommittedAuthorityOperationV1,
    VerifiedAtomicAuthorityOperationObservationV1,
};
use super::external_operation_recovery::VerifiedExternalOperationRecoveryObservationV1;
use super::external_restore_authority::{
    request_message as s9_request_message,
    validated_decision_message as validated_s9_decision_message,
    verify_external_currentness_decision_v1, ExternalAuthorityTrustPermitV1,
    ExternalCurrentnessRequestV1, SignedExternalCurrentnessDecisionV1,
    VerifiedExternalCurrentnessDecisionV1,
};
use sha2::{Digest, Sha256};
use std::fmt;

const POLICY_ID: &str = "agent-bridge/track-b/recovered-s9-decision-reverification/v1";
const PROFILE: &str =
    "PURE_DETACHED_S9_PLUS_VERIFIED_S10_RECOVERY_PLUS_SIGNED_S11_L1_HISTORICAL_ONLY";
const AUTHORITY_SNAPSHOT_DOMAIN: &[u8] =
    b"agent-bridge/track-b/recovered-s9-decision-reverification/authority-snapshot/v1";
const HISTORICAL_CHAIN_DOMAIN: &[u8] =
    b"agent-bridge/track-b/recovered-s9-decision-reverification/historical-chain/v1";
const MAX_CANONICAL_MESSAGE_BYTES: usize = 64 * 1024;
const S9_CONTRACT_SHA256: [u8; 32] = [
    0xd5, 0x37, 0xb8, 0x0c, 0xe0, 0xd2, 0xbb, 0xb3, 0xc4, 0xd0, 0x1a, 0x98, 0x8a, 0x96, 0x85, 0x43,
    0x26, 0x72, 0x07, 0x8e, 0xae, 0x07, 0xd0, 0xb9, 0x76, 0xb1, 0x26, 0x8a, 0x27, 0x52, 0x6f, 0xc4,
];
const S10_CONTRACT_SHA256: [u8; 32] = [
    0xda, 0x35, 0x66, 0xf1, 0x3d, 0xf5, 0x22, 0x95, 0x8f, 0x05, 0xc8, 0x71, 0xad, 0x46, 0x79, 0xd8,
    0x9c, 0xda, 0x9b, 0x88, 0x8b, 0xa8, 0xaa, 0x4e, 0xb4, 0xca, 0xae, 0xe4, 0xc4, 0x57, 0xfb, 0x88,
];
const S11_CONTRACT_SHA256: [u8; 32] = [
    0xea, 0xca, 0x12, 0x80, 0x83, 0x6b, 0xb3, 0x1a, 0x3e, 0x1d, 0x0c, 0xe1, 0x11, 0x73, 0xc6, 0xe3,
    0x4d, 0xbd, 0xdf, 0x24, 0xa1, 0x9e, 0x27, 0x0a, 0xf2, 0x1d, 0x57, 0x94, 0x28, 0x32, 0x7d, 0xb2,
];

#[derive(Debug, thiserror::Error)]
#[error("{code}: {detail}")]
struct RecoveredS9DecisionReverificationV1Error {
    code: &'static str,
    detail: &'static str,
}

impl RecoveredS9DecisionReverificationV1Error {
    #[cfg(test)]
    fn code(&self) -> &'static str {
        self.code
    }
}

type ReverificationResult<T> = Result<T, RecoveredS9DecisionReverificationV1Error>;

fn reverification_error(
    code: &'static str,
    detail: &'static str,
) -> RecoveredS9DecisionReverificationV1Error {
    RecoveredS9DecisionReverificationV1Error { code, detail }
}

fn sha256_bytes(bytes: &[u8]) -> [u8; 32] {
    Sha256::digest(bytes).into()
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

/// Untrusted carried bytes plus their exact typed S9 interpretation. S12 has
/// no parser or transport; a future carrier must supply both without defaults,
/// aliases, duplicate fields, or ignored trailing bytes.
struct RecoveredS9DecisionBundleV1<'a> {
    request: &'a ExternalCurrentnessRequestV1,
    canonical_request_bytes: &'a [u8],
    decision: &'a SignedExternalCurrentnessDecisionV1,
    canonical_decision_message_bytes: &'a [u8],
}

impl fmt::Debug for RecoveredS9DecisionBundleV1<'_> {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        formatter
            .debug_struct("RecoveredS9DecisionBundleV1")
            .field("scope", &"[UNTRUSTED_EXACT_TYPED_AND_CANONICAL_BYTES]")
            .finish_non_exhaustive()
    }
}

/// A private local commitment to historical verification. It is intentionally
/// non-Clone and non-serializable and contains no S11 L2 metadata, raw bytes,
/// signatures, trust permits, or conversion into an S9 currentness token.
#[must_use]
struct PurelyReverifiedRecoveredS9DecisionV1 {
    historical_chain_sha256: [u8; 32],
    s9_request_sha256: [u8; 32],
    s9_decision_message_sha256: [u8; 32],
    s9_decision_id: [u8; 32],
    s10_recovery_result_id: [u8; 32],
    s11_stable_result_id: [u8; 32],
    authority_sequence: u64,
    s9_committed_revision: u64,
    active_epoch: u64,
    registry_generation_id: [u8; 32],
}

impl fmt::Debug for PurelyReverifiedRecoveredS9DecisionV1 {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        formatter
            .debug_struct("PurelyReverifiedRecoveredS9DecisionV1")
            .field("scope", &"[HISTORICAL_ONLY_NOT_CURRENTNESS_NOT_ADMISSION]")
            .field("authority_sequence", &self.authority_sequence)
            .field("s9_committed_revision", &self.s9_committed_revision)
            .finish_non_exhaustive()
    }
}

fn authority_snapshot_digest(
    request: &ExternalCurrentnessRequestV1,
    decision: &SignedExternalCurrentnessDecisionV1,
    verified: &VerifiedExternalCurrentnessDecisionV1,
) -> [u8; 32] {
    let leader_term = decision.leader_term.to_be_bytes();
    let committed_revision = decision.committed_revision.to_be_bytes();
    let authority_sequence = decision.authority_sequence.to_be_bytes();
    let active_epoch = decision.active_epoch.to_be_bytes();
    let revoked_through_epoch = decision.revoked_through_epoch.to_be_bytes();
    let signer_key_version = decision.signer_key_version.to_be_bytes();
    framed_digest(
        AUTHORITY_SNAPSHOT_DOMAIN,
        &[
            POLICY_ID.as_bytes(),
            &S9_CONTRACT_SHA256,
            &verified.request_sha256(),
            &verified.decision_sha256(),
            request.provider_profile_id.as_bytes(),
            request.authority_namespace_id.as_bytes(),
            request.tenant_id.as_bytes(),
            request.audience.as_bytes(),
            &request.operation_id,
            &request.challenge,
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
            &request.trust_policy_sha256,
        ],
    )
}

fn historical_chain_digest(
    s9_request: &ExternalCurrentnessRequestV1,
    s9_decision: &SignedExternalCurrentnessDecisionV1,
    s9_verified: &VerifiedExternalCurrentnessDecisionV1,
    s10_verified: &VerifiedExternalOperationRecoveryObservationV1,
    s11_request: &AtomicAuthorityOperationRequestV1,
    s11_record: &SignedCommittedAuthorityOperationV1,
    s11_verified: &VerifiedAtomicAuthorityOperationObservationV1,
    authority_snapshot_sha256: &[u8; 32],
) -> [u8; 32] {
    let s9_authority_sequence = s9_verified.authority_sequence().to_be_bytes();
    let s9_committed_revision = s9_verified.committed_revision().to_be_bytes();
    let s9_active_epoch = s9_verified.active_epoch().to_be_bytes();
    let s10_leader_term = s10_verified.leader_term().to_be_bytes();
    let s10_operation_revision = s10_verified.operation_committed_revision().to_be_bytes();
    let s10_observed_revision = s10_verified.observed_journal_revision().to_be_bytes();
    let s10_record_sequence = s10_verified.journal_record_sequence().to_be_bytes();
    let s11_leader_term = s11_record.leader_term.to_be_bytes();
    let s11_operation_revision = s11_verified.operation_committed_revision().to_be_bytes();
    let s11_record_sequence = s11_verified.record_sequence().to_be_bytes();
    let s9_signer_version = s9_decision.signer_key_version.to_be_bytes();
    let s11_signer_version = s11_request.signer_key_version.to_be_bytes();
    framed_digest(
        HISTORICAL_CHAIN_DOMAIN,
        &[
            POLICY_ID.as_bytes(),
            PROFILE.as_bytes(),
            &S9_CONTRACT_SHA256,
            &S10_CONTRACT_SHA256,
            &S11_CONTRACT_SHA256,
            s9_request.provider_profile_id.as_bytes(),
            s9_request.authority_namespace_id.as_bytes(),
            s9_request.tenant_id.as_bytes(),
            s9_request.audience.as_bytes(),
            s9_decision.provider_cluster_id.as_bytes(),
            &s9_decision.provider_incarnation,
            &s9_request.operation_id,
            &s9_request.challenge,
            &s9_request.trust_policy_sha256,
            &s9_verified.request_sha256(),
            &s9_verified.decision_sha256(),
            &s9_verified.decision_id(),
            &s9_authority_sequence,
            &s9_committed_revision,
            &s9_active_epoch,
            &s9_verified.registry_generation_id(),
            authority_snapshot_sha256,
            &s10_verified.lookup_query_sha256(),
            &s10_verified.observation_sha256(),
            &s10_verified.result_id(),
            &s10_leader_term,
            &s10_operation_revision,
            &s10_observed_revision,
            &s10_verified.journal_generation_id(),
            &s10_record_sequence,
            &s11_request.concrete_replay_identity_sha256,
            &s11_record.request_sha256,
            &s11_record.prepared_record_sha256,
            &s11_record.sign_job_id,
            &s11_verified.stable_result_id(),
            &s11_verified.decision_message_sha256(),
            &s11_leader_term,
            &s11_operation_revision,
            &s11_record_sequence,
            s9_decision.signer_key_id.as_bytes(),
            &s9_signer_version,
            s11_request.signer_key_id.as_bytes(),
            &s11_signer_version,
        ],
    )
}

fn verify_recovered_s9_decision_v1(
    bundle: &RecoveredS9DecisionBundleV1<'_>,
    s9_permit: &ExternalAuthorityTrustPermitV1,
    s10_verified: &VerifiedExternalOperationRecoveryObservationV1,
    s11_request: &AtomicAuthorityOperationRequestV1,
    s11_permit: &AtomicAuthorityOperationTrustPermitV1,
    s11_record: &SignedCommittedAuthorityOperationV1,
) -> ReverificationResult<PurelyReverifiedRecoveredS9DecisionV1> {
    if bundle.canonical_request_bytes.is_empty()
        || bundle.canonical_request_bytes.len() > MAX_CANONICAL_MESSAGE_BYTES
        || bundle.canonical_decision_message_bytes.is_empty()
        || bundle.canonical_decision_message_bytes.len() > MAX_CANONICAL_MESSAGE_BYTES
    {
        return Err(reverification_error(
            "track_b_recovered_s9_decision_reverification_v1_carrier_bounds",
            "complete bounded canonical S9 request and decision bytes are required",
        ));
    }

    let exact_request_bytes = s9_request_message(bundle.request).map_err(|_| {
        reverification_error(
            "track_b_recovered_s9_decision_reverification_v1_s9_request",
            "typed S9 request is malformed or noncanonical",
        )
    })?;
    if exact_request_bytes.as_slice() != bundle.canonical_request_bytes {
        return Err(reverification_error(
            "track_b_recovered_s9_decision_reverification_v1_request_bytes",
            "carried request bytes do not exactly equal canonical typed S9 framing",
        ));
    }
    let exact_decision_bytes = validated_s9_decision_message(bundle.decision).map_err(|_| {
        reverification_error(
            "track_b_recovered_s9_decision_reverification_v1_s9_decision",
            "typed S9 decision labels are malformed, oversized, or noncanonical",
        )
    })?;
    if exact_decision_bytes.as_slice() != bundle.canonical_decision_message_bytes {
        return Err(reverification_error(
            "track_b_recovered_s9_decision_reverification_v1_decision_bytes",
            "carried decision bytes do not exactly equal canonical typed S9 framing",
        ));
    }

    let s9_verified =
        verify_external_currentness_decision_v1(bundle.request, s9_permit, bundle.decision)
            .map_err(|_| {
                reverification_error(
                    "track_b_recovered_s9_decision_reverification_v1_s9_verification",
                    "detached S9 signature, permit, state, floor, or identity verification failed",
                )
            })?;
    let s11_verified = verify_signed_committed_operation_l1_v1(s11_request, s11_permit, s11_record)
        .map_err(|_| {
            reverification_error(
                "track_b_recovered_s9_decision_reverification_v1_s11_l1_verification",
                "authenticated S11 L1 request, record, permit, or signature verification failed",
            )
        })?;

    if s9_permit.signer_key_id() == s11_permit.signer_key_id()
        || s9_permit.ed25519_public_key() == s11_permit.ed25519_public_key()
    {
        return Err(reverification_error(
            "track_b_recovered_s9_decision_reverification_v1_independent_signers",
            "S9 currentness and S11 operation authentication roles must be independently pinned",
        ));
    }

    if bundle.request.provider_profile_id != s10_verified.provider_profile_id()
        || bundle.request.authority_namespace_id != s10_verified.authority_namespace_id()
        || bundle.request.tenant_id != s10_verified.tenant_id()
        || bundle.request.audience != s10_verified.audience()
        || bundle.decision.provider_cluster_id != s10_verified.provider_cluster_id()
        || bundle.decision.provider_incarnation != s10_verified.provider_incarnation()
        || bundle.request.trust_policy_sha256 != s10_verified.trust_policy_sha256()
        || bundle.request.operation_id != s10_verified.original_operation_id()
        || bundle.request.challenge != s10_verified.original_challenge()
        || s9_verified.request_sha256() != s10_verified.original_request_sha256()
        || s9_verified.decision_sha256() != s10_verified.original_decision_sha256()
    {
        return Err(reverification_error(
            "track_b_recovered_s9_decision_reverification_v1_s10_binding",
            "verified S10 recovery projection does not exactly bind the carried S9 decision",
        ));
    }

    if bundle.request.provider_profile_id != s11_request.provider_profile_id
        || bundle.request.authority_namespace_id != s11_request.authority_namespace_id
        || bundle.request.tenant_id != s11_request.tenant_id
        || bundle.request.audience != s11_request.audience
        || bundle.decision.provider_cluster_id != s11_request.provider_cluster_id
        || bundle.decision.provider_incarnation != s11_request.provider_incarnation
        || bundle.request.trust_policy_sha256 != s11_request.trust_policy_sha256
        || bundle.request.operation_id != s11_request.operation_id
        || bundle.request.challenge != s11_request.original_challenge
        || s9_verified.request_sha256() != s11_request.original_request_sha256
        || s9_verified.decision_sha256() != s11_request.canonical_decision_sha256
        || s10_verified.journal_generation_id() != s11_request.journal_generation_id
    {
        return Err(reverification_error(
            "track_b_recovered_s9_decision_reverification_v1_s11_cross_binding",
            "authenticated S11 L1 wrapper does not exactly bind S9 and S10 identities",
        ));
    }
    if s11_verified.operation_committed_revision() != s10_verified.operation_committed_revision()
        || s11_verified.record_sequence() != s10_verified.journal_record_sequence()
        || s10_verified.leader_term() < s11_record.leader_term
        || s11_verified.operation_committed_revision() > s10_verified.observed_journal_revision()
    {
        return Err(reverification_error(
            "track_b_recovered_s9_decision_reverification_v1_recovered_record_identity",
            "S11 authenticated L1 term, revision, and sequence must be the exact non-regressing record observed by S10 at an equal-or-later high-water revision",
        ));
    }

    let expected_authority_snapshot =
        authority_snapshot_digest(bundle.request, bundle.decision, &s9_verified);
    if s11_request.authority_snapshot_sha256 != expected_authority_snapshot {
        return Err(reverification_error(
            "track_b_recovered_s9_decision_reverification_v1_authority_snapshot",
            "S11 authority snapshot does not recompute from the exact verified S9 decision",
        ));
    }

    let historical_chain_sha256 = historical_chain_digest(
        bundle.request,
        bundle.decision,
        &s9_verified,
        s10_verified,
        s11_request,
        s11_record,
        &s11_verified,
        &expected_authority_snapshot,
    );
    Ok(PurelyReverifiedRecoveredS9DecisionV1 {
        historical_chain_sha256,
        s9_request_sha256: s9_verified.request_sha256(),
        s9_decision_message_sha256: s9_verified.decision_sha256(),
        s9_decision_id: s9_verified.decision_id(),
        s10_recovery_result_id: s10_verified.result_id(),
        s11_stable_result_id: s11_verified.stable_result_id(),
        authority_sequence: s9_verified.authority_sequence(),
        s9_committed_revision: s9_verified.committed_revision(),
        active_epoch: s9_verified.active_epoch(),
        registry_generation_id: s9_verified.registry_generation_id(),
    })
}

#[cfg(feature = "temporal-evidence-s13-recovered-envelope-delivery-synthetic")]
mod recovered_envelope_delivery;

#[cfg(test)]
mod tests {
    use super::super::external_authority_operation_state_machine::{
        prepared_record_digest, request_digest, stable_result_id, synthetic_l2_record_digest,
        validated_decision_message as s11_decision_message,
        validated_sign_job_id as s11_sign_job_id, AtomicAuthorityOperationPersistentStateV1,
    };
    use super::super::external_operation_recovery::{
        lookup_query_digest, result_id, validated_observation_message,
        verify_external_operation_recovery_observation_v1, ExternalOperationRecoveryQueryV1,
        ExternalOperationRecoveryStateV1, ExternalOperationRecoveryTrustPermitV1,
        SignedExternalOperationRecoveryObservationV1,
    };
    use super::super::external_restore_authority::ExternalAuthorityStateV1;
    use super::*;
    use ring::signature::{Ed25519KeyPair, KeyPair};

    const S9_SEED: [u8; 32] = [
        0x9d, 0x61, 0xb1, 0x9d, 0xef, 0xfd, 0x5a, 0x60, 0xba, 0x84, 0x4a, 0xf4, 0x92, 0xec, 0x2c,
        0xc4, 0x44, 0x49, 0xc5, 0x69, 0x7b, 0x32, 0x69, 0x19, 0x70, 0x3b, 0xac, 0x03, 0x1c, 0xae,
        0x7f, 0x60,
    ];
    const S11_SEED: [u8; 32] = [
        0x4c, 0xcd, 0x08, 0x9b, 0x28, 0xff, 0x96, 0xda, 0x9d, 0xb6, 0xc3, 0x46, 0xec, 0x11, 0x4e,
        0x0f, 0x5b, 0x8a, 0x31, 0x9f, 0x35, 0xab, 0xa6, 0x24, 0xda, 0x8c, 0xf6, 0xed, 0x4f, 0xb8,
        0xa6, 0xfb,
    ];
    const S10_SEED: [u8; 32] = [
        0xc5, 0xaa, 0x8d, 0xf4, 0x3f, 0x9f, 0x83, 0x7b, 0xed, 0xb7, 0x44, 0x2f, 0x31, 0xdc, 0xb7,
        0xb1, 0x66, 0xd3, 0x85, 0x35, 0x07, 0x6f, 0x09, 0x4b, 0x85, 0xce, 0x3a, 0x2e, 0x0b, 0x44,
        0x58, 0xf7,
    ];

    fn repeated(value: u8) -> [u8; 32] {
        [value; 32]
    }

    fn decode<const N: usize>(value: &str) -> [u8; N] {
        assert_eq!(value.len(), N * 2);
        let mut output = [0; N];
        for (index, byte) in output.iter_mut().enumerate() {
            *byte = u8::from_str_radix(&value[index * 2..index * 2 + 2], 16).unwrap();
        }
        output
    }

    fn encode(value: &[u8]) -> String {
        value.iter().map(|byte| format!("{byte:02x}")).collect()
    }

    fn s9_decision_message(decision: &SignedExternalCurrentnessDecisionV1) -> Vec<u8> {
        validated_s9_decision_message(decision).expect("valid synthetic S9 decision labels")
    }

    fn key_pair(seed: &[u8; 32]) -> Ed25519KeyPair {
        Ed25519KeyPair::from_seed_unchecked(seed).expect("RFC8032 test seed")
    }

    fn public_key(seed: &[u8; 32]) -> [u8; 32] {
        key_pair(seed).public_key().as_ref().try_into().unwrap()
    }

    fn s9_request() -> ExternalCurrentnessRequestV1 {
        ExternalCurrentnessRequestV1 {
            provider_profile_id: "owner-selected-provider-v1".into(),
            authority_namespace_id: "agent-bridge-research-prod".into(),
            tenant_id: "agent-bridge".into(),
            audience: "ab-store-restore-admission".into(),
            operation_id: repeated(0x21),
            challenge: repeated(0x31),
            expected_epoch: 2,
            expected_epoch_record_sha256: repeated(0x41),
            registry_generation_id: repeated(0x42),
            receiver_identity_sha256: repeated(0x43),
            build_identity_sha256: repeated(0x44),
            allowlist_sha256: repeated(0x45),
            keyset_identity_sha256: decode(
                "9c457bfc43b6dfd010c25f0564ae57e4d0725004eb59f1bea31763b9caa32674",
            ),
            trust_policy_sha256: repeated(0x71),
        }
    }

    fn s9_permit_with(
        tenant_id: &str,
        provider_incarnation: [u8; 32],
        trust_policy_sha256: [u8; 32],
        minimum_committed_revision: u64,
        ed25519_public_key: [u8; 32],
    ) -> ExternalAuthorityTrustPermitV1 {
        ExternalAuthorityTrustPermitV1::test_only_new(
            "owner-selected-provider-v1",
            "agent-bridge-research-prod",
            tenant_id,
            "ab-store-restore-admission",
            "authority-cluster-a",
            provider_incarnation,
            "currentness-signer-a",
            3,
            trust_policy_sha256,
            7,
            minimum_committed_revision,
            ed25519_public_key,
        )
    }

    fn s9_permit() -> ExternalAuthorityTrustPermitV1 {
        s9_permit_with(
            "agent-bridge",
            repeated(0x61),
            repeated(0x71),
            42,
            public_key(&S9_SEED),
        )
    }

    fn signed_s9_decision(
        request: &ExternalCurrentnessRequestV1,
    ) -> SignedExternalCurrentnessDecisionV1 {
        let mut decision = SignedExternalCurrentnessDecisionV1 {
            request_sha256: sha256_bytes(&s9_request_message(request).unwrap()),
            state: ExternalAuthorityStateV1::Active,
            provider_cluster_id: "authority-cluster-a".into(),
            provider_incarnation: repeated(0x61),
            leader_term: 7,
            committed_revision: 42,
            authority_sequence: 1,
            active_epoch: 2,
            active_epoch_record_sha256: repeated(0x41),
            active_registry_generation_id: repeated(0x42),
            active_keyset_identity_sha256: decode(
                "9c457bfc43b6dfd010c25f0564ae57e4d0725004eb59f1bea31763b9caa32674",
            ),
            revocation_checkpoint_sha256: decode(
                "7de88b53712a7cc3bd068aef5d08023cfe803864a03023bf3ba27707c1849f2a",
            ),
            revoked_through_epoch: 1,
            provider_custody_claim_sha256: decode(
                "b657851893471a671c341f7c22c8e1a883fef5e67d3ca48d7e13794cde76f34e",
            ),
            provider_old_key_use_denied_claim_sha256: decode(
                "b31cc3f4041e0fdd9c2e55269a0133f6d5e660a6228166976f7244d3c4a908af",
            ),
            decision_id: decode("78b269ddec8b4a8b1343eb7922bb6400f231fa3036c535ef8ae5aa9e0b81e2c3"),
            signer_key_id: "currentness-signer-a".into(),
            signer_key_version: 3,
            ed25519_signature: [0; 64],
        };
        decision.ed25519_signature = key_pair(&S9_SEED)
            .sign(&s9_decision_message(&decision))
            .as_ref()
            .try_into()
            .unwrap();
        decision
    }

    fn resign_s9(fixture: &mut Fixture) {
        fixture.s9_decision.request_sha256 =
            sha256_bytes(&s9_request_message(&fixture.s9_request).unwrap());
        fixture.s9_decision.ed25519_signature = [0; 64];
        fixture.s9_decision.ed25519_signature = key_pair(&S9_SEED)
            .sign(&s9_decision_message(&fixture.s9_decision))
            .as_ref()
            .try_into()
            .unwrap();
        fixture.s9_request_bytes = s9_request_message(&fixture.s9_request).unwrap();
        fixture.s9_decision_bytes = s9_decision_message(&fixture.s9_decision);
    }

    pub(super) struct S10InputFixture {
        pub(super) query: ExternalOperationRecoveryQueryV1,
        pub(super) observation: SignedExternalOperationRecoveryObservationV1,
        pub(super) permit: ExternalOperationRecoveryTrustPermitV1,
    }

    pub(super) fn resign_s10(observation: &mut SignedExternalOperationRecoveryObservationV1) {
        observation.ed25519_signature = [0; 64];
        observation.ed25519_signature = key_pair(&S10_SEED)
            .sign(&validated_observation_message(observation).unwrap())
            .as_ref()
            .try_into()
            .unwrap();
    }

    pub(super) fn s10_inputs(
        request: &ExternalCurrentnessRequestV1,
        decision: &SignedExternalCurrentnessDecisionV1,
    ) -> S10InputFixture {
        let query = ExternalOperationRecoveryQueryV1 {
            provider_profile_id: request.provider_profile_id.clone(),
            authority_namespace_id: request.authority_namespace_id.clone(),
            tenant_id: request.tenant_id.clone(),
            audience: request.audience.clone(),
            provider_cluster_id: decision.provider_cluster_id.clone(),
            provider_incarnation: decision.provider_incarnation,
            lookup_query_id: repeated(0x51),
            lookup_challenge: repeated(0x52),
            original_operation_id: request.operation_id,
            original_challenge: request.challenge,
            original_request_sha256: decision.request_sha256,
            trust_policy_sha256: request.trust_policy_sha256,
        };
        let original_decision_sha256 = sha256_bytes(&s9_decision_message(decision));
        let mut observation = SignedExternalOperationRecoveryObservationV1 {
            lookup_query_sha256: lookup_query_digest(&query).unwrap(),
            state: ExternalOperationRecoveryStateV1::Committed,
            original_operation_id: request.operation_id,
            original_challenge: request.challenge,
            original_request_sha256: decision.request_sha256,
            provider_cluster_id: decision.provider_cluster_id.clone(),
            provider_incarnation: decision.provider_incarnation,
            leader_term: 7,
            operation_committed_revision: 43,
            observed_journal_revision: 50,
            journal_generation_id: repeated(0x72),
            journal_record_sequence: 10,
            original_decision_sha256,
            result_id: result_id(&query, 43, &repeated(0x72), 10, &original_decision_sha256),
            signer_key_id: "recovery-signer-a".into(),
            signer_key_version: 4,
            ed25519_signature: [0; 64],
        };
        resign_s10(&mut observation);
        let permit = ExternalOperationRecoveryTrustPermitV1::test_only_new(
            request.provider_profile_id.clone(),
            request.authority_namespace_id.clone(),
            request.tenant_id.clone(),
            request.audience.clone(),
            decision.provider_cluster_id.clone(),
            decision.provider_incarnation,
            "recovery-signer-a",
            4,
            request.trust_policy_sha256,
            7,
            50,
            repeated(0x72),
            public_key(&S10_SEED),
        );
        S10InputFixture {
            query,
            observation,
            permit,
        }
    }

    fn verified_s10(
        request: &ExternalCurrentnessRequestV1,
        decision: &SignedExternalCurrentnessDecisionV1,
    ) -> VerifiedExternalOperationRecoveryObservationV1 {
        let input = s10_inputs(request, decision);
        verify_external_operation_recovery_observation_v1(
            &input.query,
            &input.permit,
            &input.observation,
        )
        .unwrap()
    }

    fn s11_permit_with(
        audience: &str,
        journal_generation_id: [u8; 32],
        signer_key_id: &str,
        minimum_operation_committed_revision: u64,
        ed25519_public_key: [u8; 32],
    ) -> AtomicAuthorityOperationTrustPermitV1 {
        AtomicAuthorityOperationTrustPermitV1::test_only_new(
            "owner-selected-provider-v1",
            "agent-bridge-research-prod",
            "agent-bridge",
            audience,
            "authority-cluster-a",
            repeated(0x61),
            journal_generation_id,
            signer_key_id,
            5,
            repeated(0x71),
            7,
            minimum_operation_committed_revision,
            ed25519_public_key,
        )
    }

    fn s11_permit() -> AtomicAuthorityOperationTrustPermitV1 {
        s11_permit_with(
            "ab-store-restore-admission",
            repeated(0x72),
            "authority-operation-signer-a",
            43,
            public_key(&S11_SEED),
        )
    }

    fn rebuild_s11_record_with_seed(fixture: &mut Fixture, seed: &[u8; 32]) {
        let request_sha256 = request_digest(&fixture.s11_request).unwrap();
        let prepared_record_sha256 = prepared_record_digest(
            &request_sha256,
            fixture.s11_record.leader_term,
            fixture.s11_record.operation_committed_revision,
            fixture.s11_record.record_sequence,
        );
        let sign_job_id = s11_sign_job_id(
            &prepared_record_sha256,
            &fixture.s11_request.signer_key_id,
            fixture.s11_request.signer_key_version,
        )
        .unwrap();
        let stable_result_id = stable_result_id(&prepared_record_sha256, &sign_job_id);
        let message = s11_decision_message(
            &fixture.s11_request,
            &request_sha256,
            fixture.s11_record.leader_term,
            fixture.s11_record.operation_committed_revision,
            fixture.s11_record.record_sequence,
            &prepared_record_sha256,
            &sign_job_id,
            &stable_result_id,
        )
        .unwrap();
        let signature: [u8; 64] = key_pair(seed).sign(&message).as_ref().try_into().unwrap();
        fixture.s11_record.request_sha256 = request_sha256;
        fixture.s11_record.state = AtomicAuthorityOperationPersistentStateV1::SignedCommitted;
        fixture.s11_record.provider_cluster_id = fixture.s11_request.provider_cluster_id.clone();
        fixture.s11_record.provider_incarnation = fixture.s11_request.provider_incarnation;
        fixture.s11_record.journal_generation_id = fixture.s11_request.journal_generation_id;
        fixture.s11_record.prepared_record_sha256 = prepared_record_sha256;
        fixture.s11_record.sign_job_id = sign_job_id;
        fixture.s11_record.stable_result_id = stable_result_id;
        fixture.s11_record.decision_message_sha256 = sha256_bytes(&message);
        fixture.s11_record.signer_key_id = fixture.s11_request.signer_key_id.clone();
        fixture.s11_record.signer_key_version = fixture.s11_request.signer_key_version;
        fixture.s11_record.ed25519_signature = signature;
        fixture.s11_record.synthetic_l2_record_sha256 = synthetic_l2_record_digest(
            &stable_result_id,
            &fixture.s11_record.decision_message_sha256,
            &signature,
            fixture.s11_record.synthetic_l2_revision,
        );
    }

    fn rebuild_s11_record(fixture: &mut Fixture) {
        rebuild_s11_record_with_seed(fixture, &S11_SEED);
    }

    pub(super) struct Fixture {
        pub(super) s9_request: ExternalCurrentnessRequestV1,
        pub(super) s9_request_bytes: Vec<u8>,
        pub(super) s9_decision: SignedExternalCurrentnessDecisionV1,
        pub(super) s9_decision_bytes: Vec<u8>,
        pub(super) s9_permit: ExternalAuthorityTrustPermitV1,
        pub(super) s10_verified: VerifiedExternalOperationRecoveryObservationV1,
        pub(super) s11_request: AtomicAuthorityOperationRequestV1,
        pub(super) s11_permit: AtomicAuthorityOperationTrustPermitV1,
        pub(super) s11_record: SignedCommittedAuthorityOperationV1,
    }

    impl Fixture {
        fn verify(&self) -> ReverificationResult<PurelyReverifiedRecoveredS9DecisionV1> {
            verify_recovered_s9_decision_v1(
                &RecoveredS9DecisionBundleV1 {
                    request: &self.s9_request,
                    canonical_request_bytes: &self.s9_request_bytes,
                    decision: &self.s9_decision,
                    canonical_decision_message_bytes: &self.s9_decision_bytes,
                },
                &self.s9_permit,
                &self.s10_verified,
                &self.s11_request,
                &self.s11_permit,
                &self.s11_record,
            )
        }
    }

    pub(super) fn fixture() -> Fixture {
        let s9_request = s9_request();
        let s9_request_bytes = s9_request_message(&s9_request).unwrap();
        let s9_decision = signed_s9_decision(&s9_request);
        let s9_decision_bytes = s9_decision_message(&s9_decision);
        let s9_permit = s9_permit();
        let s10_verified = verified_s10(&s9_request, &s9_decision);
        let s9_verified =
            verify_external_currentness_decision_v1(&s9_request, &s9_permit, &s9_decision).unwrap();
        let authority_snapshot_sha256 =
            authority_snapshot_digest(&s9_request, &s9_decision, &s9_verified);
        let s11_request = AtomicAuthorityOperationRequestV1 {
            provider_profile_id: s9_request.provider_profile_id.clone(),
            authority_namespace_id: s9_request.authority_namespace_id.clone(),
            tenant_id: s9_request.tenant_id.clone(),
            audience: s9_request.audience.clone(),
            provider_cluster_id: s9_decision.provider_cluster_id.clone(),
            provider_incarnation: s9_decision.provider_incarnation,
            journal_generation_id: repeated(0x72),
            operation_id: s9_request.operation_id,
            original_challenge: s9_request.challenge,
            original_request_sha256: s9_verified.request_sha256(),
            concrete_replay_identity_sha256: repeated(0x25),
            authority_snapshot_sha256,
            canonical_decision_sha256: s9_verified.decision_sha256(),
            trust_policy_sha256: s9_request.trust_policy_sha256,
            signer_key_id: "authority-operation-signer-a".into(),
            signer_key_version: 5,
        };
        let s11_permit = s11_permit();
        let mut output = Fixture {
            s9_request,
            s9_request_bytes,
            s9_decision,
            s9_decision_bytes,
            s9_permit,
            s10_verified,
            s11_request,
            s11_permit,
            s11_record: SignedCommittedAuthorityOperationV1 {
                request_sha256: [0; 32],
                state: AtomicAuthorityOperationPersistentStateV1::SignedCommitted,
                provider_cluster_id: String::new(),
                provider_incarnation: [0; 32],
                journal_generation_id: [0; 32],
                leader_term: 7,
                operation_committed_revision: 43,
                record_sequence: 10,
                prepared_record_sha256: [0; 32],
                sign_job_id: [0; 32],
                stable_result_id: [0; 32],
                decision_message_sha256: [0; 32],
                signer_key_id: String::new(),
                signer_key_version: 0,
                synthetic_l2_revision: 52,
                ed25519_signature: [0; 64],
                synthetic_l2_record_sha256: [0; 32],
            },
        };
        rebuild_s11_record(&mut output);
        output
    }

    #[test]
    fn s12_known_answer_three_link_historical_chain_is_stable() {
        let fixture = fixture();
        let verified = fixture.verify().unwrap();
        assert_eq!(
            encode(&verified.s9_request_sha256),
            "01d433a73bee905b5d65556b9ba4165716a87cf6142f61ef4147198e390077f1"
        );
        assert_eq!(
            encode(&verified.s9_decision_message_sha256),
            "e35d9917772887d0ffdbd17f8c8781d93e42e79250483139d400ea46392daab1"
        );
        assert_eq!(
            encode(&fixture.s9_decision.ed25519_signature),
            "0f530350eb467fd7d10f3a6df04cbb988397d323633244e139f09ec5d33e79a62fb667a312fb495bc76f23a068a779c78aca8ae9ce88b8a3e77bbcd42496600f"
        );
        assert_eq!(
            encode(&fixture.s10_verified.lookup_query_sha256()),
            "18c188cbab81cb121582ffc509344400948009b65f1bb5dd148e35f5e9f33bdc"
        );
        assert_eq!(
            encode(&fixture.s10_verified.observation_sha256()),
            "22e256669c2be1b4ebfe49a20157be7fd76c4156a685b920eda30894222c219f"
        );
        assert_eq!(
            encode(&verified.s10_recovery_result_id),
            "1d2e649278fa6000a2a3a743721b1991c68e6c33eafbe17ff8da7580d96252cd"
        );
        assert_eq!(
            encode(&fixture.s11_request.authority_snapshot_sha256),
            "f45f52e439dc247132c26cba67980a938cdcd7684026581177acd03a5ffff557"
        );
        assert_eq!(
            encode(&fixture.s11_record.request_sha256),
            "00fe042d28827f5c3c0e722a397ce3533cadbdacd9a2de6782ed414783ff79f1"
        );
        assert_eq!(
            encode(&fixture.s11_record.prepared_record_sha256),
            "198f31e075b72d4041b965b5eb026f4a797b885399b83de1a501817d78a91d12"
        );
        assert_eq!(
            encode(&fixture.s11_record.sign_job_id),
            "67f8c9f856b143dccec7e7dd27353a7d51cb90f00801eb95d9e65aa3ff8f5c68"
        );
        assert_eq!(
            encode(&verified.s11_stable_result_id),
            "ae429756bd7a7b999c83bdeeb5018333fb5ee6a3f630d16405fe1e05fdd804be"
        );
        assert_eq!(
            encode(&fixture.s11_record.decision_message_sha256),
            "330dded03657288687a5c0538a52d5bd2ed1ddee4cc560d70c3b103f8f3d917f"
        );
        assert_eq!(
            encode(&fixture.s11_record.ed25519_signature),
            "25eebbdcd752b72e2f74ac919f10b2a778a4cf1e07794e0f647f57790eec5e08d1e2f4f58e8c2be45ecce56f6cd7a462b31d8ff48e9093425d820e2b4c23eb06"
        );
        assert_eq!(
            encode(&fixture.s11_record.synthetic_l2_record_sha256),
            "92093e5e337c6b78fdc457cea56ef39de335868f2e5228db6d0526f86ad509e1"
        );
        assert_eq!(
            encode(&verified.historical_chain_sha256),
            "afb8aa4945f0e491937f75233c621d52f1bcc1307e6d497352fd9d0fc79b7204"
        );
    }

    #[test]
    fn s12_repeated_pure_verification_is_deterministic_and_stateless() {
        let fixture = fixture();
        let first = fixture.verify().unwrap();
        let second = fixture.verify().unwrap();
        assert_eq!(
            first.historical_chain_sha256,
            second.historical_chain_sha256
        );
        assert_eq!(first.s9_decision_id, second.s9_decision_id);
    }

    #[test]
    fn s12_truncated_canonical_request_bytes_reject() {
        let mut fixture = fixture();
        fixture.s9_request_bytes.pop();
        assert_eq!(
            fixture.verify().unwrap_err().code(),
            "track_b_recovered_s9_decision_reverification_v1_request_bytes"
        );
    }

    #[test]
    fn s12_appended_canonical_request_bytes_reject() {
        let mut fixture = fixture();
        fixture.s9_request_bytes.push(0);
        assert!(fixture.verify().is_err());
    }

    #[test]
    fn s12_truncated_canonical_decision_bytes_reject() {
        let mut fixture = fixture();
        fixture.s9_decision_bytes.pop();
        assert_eq!(
            fixture.verify().unwrap_err().code(),
            "track_b_recovered_s9_decision_reverification_v1_decision_bytes"
        );
    }

    #[test]
    fn s12_appended_canonical_decision_bytes_reject() {
        let mut fixture = fixture();
        fixture.s9_decision_bytes.push(0);
        assert!(fixture.verify().is_err());
    }

    #[test]
    fn s12_empty_or_oversized_carrier_bytes_reject() {
        let mut empty = fixture();
        empty.s9_request_bytes.clear();
        assert_eq!(
            empty.verify().unwrap_err().code(),
            "track_b_recovered_s9_decision_reverification_v1_carrier_bounds"
        );
        let mut oversized = fixture();
        oversized.s9_decision_bytes = vec![0; MAX_CANONICAL_MESSAGE_BYTES + 1];
        assert!(oversized.verify().is_err());
    }

    #[test]
    fn s12_oversized_typed_decision_label_rejects_before_canonical_framing() {
        let mut fixture = fixture();
        fixture.s9_decision.provider_cluster_id = "a".repeat(129);
        assert_eq!(
            fixture.verify().unwrap_err().code(),
            "track_b_recovered_s9_decision_reverification_v1_s9_decision"
        );
    }

    #[test]
    fn s12_typed_request_scope_substitution_rejects_after_valid_s9_resign() {
        let mut fixture = fixture();
        fixture.s9_request.tenant_id = "agent-bridge-other".into();
        fixture.s9_permit = s9_permit_with(
            "agent-bridge-other",
            repeated(0x61),
            repeated(0x71),
            42,
            public_key(&S9_SEED),
        );
        resign_s9(&mut fixture);
        assert_eq!(
            fixture.verify().unwrap_err().code(),
            "track_b_recovered_s9_decision_reverification_v1_s10_binding"
        );
    }

    #[test]
    fn s12_typed_request_operation_substitution_rejects_after_valid_s9_resign() {
        let mut fixture = fixture();
        fixture.s9_request.operation_id = repeated(0x91);
        resign_s9(&mut fixture);
        assert!(fixture.verify().is_err());
    }

    #[test]
    fn s12_s9_signature_substitution_rejects() {
        let mut fixture = fixture();
        fixture.s9_decision.ed25519_signature[0] ^= 1;
        fixture.s9_decision_bytes = s9_decision_message(&fixture.s9_decision);
        assert_eq!(
            fixture.verify().unwrap_err().code(),
            "track_b_recovered_s9_decision_reverification_v1_s9_verification"
        );
    }

    #[test]
    fn s12_s9_wrong_owner_pin_rejects() {
        let mut fixture = fixture();
        fixture.s9_permit = s9_permit_with(
            "agent-bridge",
            repeated(0x61),
            repeated(0x71),
            42,
            public_key(&S11_SEED),
        );
        assert!(fixture.verify().is_err());
    }

    #[test]
    fn s12_every_non_active_s9_state_rejects() {
        for state in [
            ExternalAuthorityStateV1::Fencing,
            ExternalAuthorityStateV1::Pending,
            ExternalAuthorityStateV1::Revoked,
            ExternalAuthorityStateV1::Indeterminate,
        ] {
            let mut fixture = fixture();
            fixture.s9_decision.state = state;
            resign_s9(&mut fixture);
            assert!(fixture.verify().is_err());
        }
    }

    #[test]
    fn s12_s9_floor_epoch_generation_keyset_and_revocation_substitutions_reject() {
        let mut floor = fixture();
        floor.s9_permit = s9_permit_with(
            "agent-bridge",
            repeated(0x61),
            repeated(0x71),
            43,
            public_key(&S9_SEED),
        );
        assert!(floor.verify().is_err());
        let mut epoch = fixture();
        epoch.s9_decision.active_epoch = 3;
        resign_s9(&mut epoch);
        assert!(epoch.verify().is_err());
        let mut generation = fixture();
        generation.s9_decision.active_registry_generation_id = repeated(0x92);
        resign_s9(&mut generation);
        assert!(generation.verify().is_err());
        let mut keyset = fixture();
        keyset.s9_decision.active_keyset_identity_sha256 = repeated(0x93);
        resign_s9(&mut keyset);
        assert!(keyset.verify().is_err());
        let mut revocation = fixture();
        revocation.s9_decision.revoked_through_epoch = u64::MAX;
        resign_s9(&mut revocation);
        assert!(revocation.verify().is_err());
    }

    #[test]
    fn s12_verified_s10_request_and_decision_digests_are_required() {
        let mut request = fixture();
        request.s9_request.receiver_identity_sha256 = repeated(0xa0);
        resign_s9(&mut request);
        assert_eq!(
            request.verify().unwrap_err().code(),
            "track_b_recovered_s9_decision_reverification_v1_s10_binding"
        );
        let mut decision = fixture();
        decision.s9_decision.decision_id = repeated(0xa1);
        resign_s9(&mut decision);
        assert!(decision.verify().is_err());
    }

    #[test]
    fn s12_verified_s10_operation_and_challenge_are_required() {
        let mut operation = fixture();
        operation.s9_request.operation_id = repeated(0xa2);
        resign_s9(&mut operation);
        assert!(operation.verify().is_err());
        let mut challenge = fixture();
        challenge.s9_request.challenge = repeated(0xa3);
        resign_s9(&mut challenge);
        assert!(challenge.verify().is_err());
    }

    #[test]
    fn s12_verified_s10_scope_provider_and_trust_are_required() {
        let mut tenant = fixture();
        tenant.s9_request.tenant_id = "other-tenant".into();
        tenant.s9_permit = s9_permit_with(
            "other-tenant",
            repeated(0x61),
            repeated(0x71),
            42,
            public_key(&S9_SEED),
        );
        resign_s9(&mut tenant);
        assert!(tenant.verify().is_err());
        let mut provider = fixture();
        provider.s9_decision.provider_incarnation = repeated(0xa4);
        provider.s9_permit = s9_permit_with(
            "agent-bridge",
            repeated(0xa4),
            repeated(0x71),
            42,
            public_key(&S9_SEED),
        );
        resign_s9(&mut provider);
        assert!(provider.verify().is_err());
        let mut trust = fixture();
        trust.s9_request.trust_policy_sha256 = repeated(0xa5);
        trust.s9_permit = s9_permit_with(
            "agent-bridge",
            repeated(0x61),
            repeated(0xa5),
            42,
            public_key(&S9_SEED),
        );
        resign_s9(&mut trust);
        assert!(trust.verify().is_err());
    }

    #[test]
    fn s12_s11_signature_substitution_rejects() {
        let mut fixture = fixture();
        fixture.s11_record.ed25519_signature[0] ^= 1;
        assert_eq!(
            fixture.verify().unwrap_err().code(),
            "track_b_recovered_s9_decision_reverification_v1_s11_l1_verification"
        );
    }

    #[test]
    fn s12_s11_wrong_owner_pin_rejects() {
        let mut fixture = fixture();
        fixture.s11_permit = s11_permit_with(
            "ab-store-restore-admission",
            repeated(0x72),
            "authority-operation-signer-a",
            43,
            public_key(&S9_SEED),
        );
        assert!(fixture.verify().is_err());
    }

    #[test]
    fn s12_s11_operation_and_challenge_cross_substitution_rejects_even_when_resigned() {
        let mut operation = fixture();
        operation.s11_request.operation_id = repeated(0xb1);
        rebuild_s11_record(&mut operation);
        assert_eq!(
            operation.verify().unwrap_err().code(),
            "track_b_recovered_s9_decision_reverification_v1_s11_cross_binding"
        );
        let mut challenge = fixture();
        challenge.s11_request.original_challenge = repeated(0xb2);
        rebuild_s11_record(&mut challenge);
        assert!(challenge.verify().is_err());
    }

    #[test]
    fn s12_s11_scope_cross_substitution_rejects_even_when_permitted_and_resigned() {
        let mut fixture = fixture();
        fixture.s11_request.audience = "other-audience".into();
        fixture.s11_permit = s11_permit_with(
            "other-audience",
            repeated(0x72),
            "authority-operation-signer-a",
            43,
            public_key(&S11_SEED),
        );
        rebuild_s11_record(&mut fixture);
        assert!(fixture.verify().is_err());
    }

    #[test]
    fn s12_s11_request_and_decision_digest_cross_substitutions_reject_when_resigned() {
        let mut request = fixture();
        request.s11_request.original_request_sha256 = repeated(0xb3);
        rebuild_s11_record(&mut request);
        assert!(request.verify().is_err());
        let mut decision = fixture();
        decision.s11_request.canonical_decision_sha256 = repeated(0xb4);
        rebuild_s11_record(&mut decision);
        assert!(decision.verify().is_err());
    }

    #[test]
    fn s12_s10_and_s11_journal_generation_cross_binding_is_required() {
        let mut fixture = fixture();
        fixture.s11_request.journal_generation_id = repeated(0xb5);
        fixture.s11_permit = s11_permit_with(
            "ab-store-restore-admission",
            repeated(0xb5),
            "authority-operation-signer-a",
            43,
            public_key(&S11_SEED),
        );
        rebuild_s11_record(&mut fixture);
        assert!(fixture.verify().is_err());
    }

    #[test]
    fn s12_recomputed_authority_snapshot_is_required_even_when_s11_is_resigned() {
        let mut fixture = fixture();
        fixture.s11_request.authority_snapshot_sha256 = repeated(0xb6);
        rebuild_s11_record(&mut fixture);
        assert_eq!(
            fixture.verify().unwrap_err().code(),
            "track_b_recovered_s9_decision_reverification_v1_authority_snapshot"
        );
    }

    #[test]
    fn s12_s11_l1_term_revision_and_sequence_must_match_the_s10_observation() {
        let mut revision = fixture();
        revision.s11_record.operation_committed_revision = 44;
        rebuild_s11_record(&mut revision);
        assert_eq!(
            revision.verify().unwrap_err().code(),
            "track_b_recovered_s9_decision_reverification_v1_recovered_record_identity"
        );
        let mut sequence = fixture();
        sequence.s11_record.record_sequence = 11;
        rebuild_s11_record(&mut sequence);
        assert!(sequence.verify().is_err());
        let mut term = fixture();
        term.s11_record.leader_term = 8;
        rebuild_s11_record(&mut term);
        assert_eq!(
            term.verify().unwrap_err().code(),
            "track_b_recovered_s9_decision_reverification_v1_recovered_record_identity"
        );
    }

    #[test]
    fn s12_s9_and_s11_key_ids_must_be_independent() {
        let mut fixture = fixture();
        fixture.s11_request.signer_key_id = fixture.s9_permit.signer_key_id().into();
        fixture.s11_permit = s11_permit_with(
            "ab-store-restore-admission",
            repeated(0x72),
            "currentness-signer-a",
            43,
            public_key(&S11_SEED),
        );
        rebuild_s11_record(&mut fixture);
        assert_eq!(
            fixture.verify().unwrap_err().code(),
            "track_b_recovered_s9_decision_reverification_v1_independent_signers"
        );
    }

    #[test]
    fn s12_s9_and_s11_public_keys_must_be_independent() {
        let mut fixture = fixture();
        fixture.s11_permit = s11_permit_with(
            "ab-store-restore-admission",
            repeated(0x72),
            "authority-operation-signer-a",
            43,
            fixture.s9_permit.ed25519_public_key(),
        );
        rebuild_s11_record_with_seed(&mut fixture, &S9_SEED);
        assert_eq!(
            fixture.verify().unwrap_err().code(),
            "track_b_recovered_s9_decision_reverification_v1_independent_signers"
        );
    }

    #[test]
    fn s12_swapped_signature_permits_reject() {
        let mut fixture = fixture();
        fixture.s9_permit = s9_permit_with(
            "agent-bridge",
            repeated(0x61),
            repeated(0x71),
            42,
            public_key(&S11_SEED),
        );
        fixture.s11_permit = s11_permit_with(
            "ab-store-restore-admission",
            repeated(0x72),
            "authority-operation-signer-a",
            43,
            public_key(&S9_SEED),
        );
        assert!(fixture.verify().is_err());
    }

    #[test]
    fn s12_l2_revision_and_recomputed_checksum_do_not_change_historical_chain() {
        let mut fixture = fixture();
        let original = fixture.verify().unwrap().historical_chain_sha256;
        fixture.s11_record.synthetic_l2_revision = 99;
        fixture.s11_record.synthetic_l2_record_sha256 = synthetic_l2_record_digest(
            &fixture.s11_record.stable_result_id,
            &fixture.s11_record.decision_message_sha256,
            &fixture.s11_record.ed25519_signature,
            99,
        );
        assert_eq!(
            encode(&fixture.s11_record.synthetic_l2_record_sha256),
            "023337c30e39a53e88284c7532e5cfe34d8baa3f43f981294c4dfbac0e6c6089"
        );
        assert_eq!(fixture.verify().unwrap().historical_chain_sha256, original);
    }

    #[test]
    fn s12_even_corrupt_l2_metadata_is_not_read_by_l1_historical_verification() {
        let mut fixture = fixture();
        let original = fixture.verify().unwrap().historical_chain_sha256;
        fixture.s11_record.synthetic_l2_revision = 0;
        fixture.s11_record.synthetic_l2_record_sha256 = repeated(0xff);
        assert_eq!(fixture.verify().unwrap().historical_chain_sha256, original);
    }

    #[test]
    fn s12_historical_output_contains_no_currentness_or_admission_semantics() {
        let verified = fixture().verify().unwrap();
        let debug = format!("{verified:?}");
        assert!(debug.contains("HISTORICAL_ONLY_NOT_CURRENTNESS_NOT_ADMISSION"));
        assert_eq!(verified.authority_sequence, 1);
        assert_eq!(verified.s9_committed_revision, 42);
        assert_eq!(verified.active_epoch, 2);
        assert_eq!(verified.registry_generation_id, repeated(0x42));
    }

    #[test]
    fn s12_later_revocation_cannot_recall_or_upgrade_prior_historical_observation() {
        let fixture = fixture();
        let prior = fixture.verify().unwrap();
        let mut later = fixture.s9_decision.clone();
        later.state = ExternalAuthorityStateV1::Revoked;
        later.ed25519_signature = [0; 64];
        later.ed25519_signature = key_pair(&S9_SEED)
            .sign(&s9_decision_message(&later))
            .as_ref()
            .try_into()
            .unwrap();
        assert!(verify_external_currentness_decision_v1(
            &fixture.s9_request,
            &fixture.s9_permit,
            &later
        )
        .is_err());
        assert_eq!(
            fixture.verify().unwrap().historical_chain_sha256,
            prior.historical_chain_sha256
        );
    }
}
