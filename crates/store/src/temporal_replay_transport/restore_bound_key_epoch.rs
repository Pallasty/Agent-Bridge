//! S8 synthetic controlled-restore key-epoch admission protocol.
//!
//! This private module turns the S7 restore-bound key-epoch rule into an
//! executable, fail-closed contract. It does not provide an authority, KMS,
//! keystore, receiver, or transport. Non-test code has no way to construct the
//! authority or admission permits. The synthetic online authority exists only
//! in tests and must not be confused with external custody or a monotonic
//! anti-rollback anchor.
//!
//! A currently active epoch binds three independent key roles, the S7 registry
//! generation, receiver/build/allowlist commitments, a restore-event
//! commitment, and a predecessor record. During a controlled restore the old
//! epoch is fenced before the next epoch can become active. This prevents old
//! epoch packets only when currentness and old-key revocation live outside the
//! restored backup domain, challenges are unique, and the old receiver is
//! quiesced. Same-epoch rollback and joint database/authority rollback remain
//! deliberately unresolved.

#![cfg_attr(not(test), allow(dead_code))]

use super::{
    durable_replay_registry::SyntheticDurableReplayRegistryV1, sha256_bytes, verifier_error,
    verify_synthetic_detached_candidate_durable_v1, DetachedCandidateAuthenticationV1,
    SyntheticDetachedVerificationPermitV1, TrackBDetachedVerifierV1Error,
    VerifiedDetachedCandidateV1, VerifierResult, MAX_ENVELOPE_BYTES,
};
use ring::hmac;

const POLICY_ID: &str = "agent-bridge/track-b/controlled-restore-key-epoch/v1";
const RECORD_DOMAIN: &[u8] = b"agent-bridge/track-b/controlled-restore-key-epoch/record/v1";
const CURRENTNESS_DOMAIN: &[u8] =
    b"agent-bridge/track-b/controlled-restore-key-epoch/currentness/v1";
const OUTER_AUTHENTICATION_DOMAIN: &str =
    "agent-bridge/track-b/controlled-restore-key-epoch/packet/v1";
const OUTER_AUTHENTICATION_ALGORITHM: &str = "HMAC-SHA-256";
const OUTER_AUTHENTICATION_MESSAGE_PROFILE: &str =
    "framed_epoch_record_identity_then_exact_s6_payload_bytes_v1";
const S7_DURABLE_CONTRACT_SHA256: &str =
    "8e4f895089f3085725988b50001ab77ec909b86b1dd203e304cc6b4a143a4c8c";
const S7_SCHEMA_MANIFEST_SHA256: &str =
    "686c22c3f4f3f696113a88a6d72bb292635a55020e00144ea2ef02f7eae35466";
const ZERO_COMMITMENT: [u8; 32] = [0; 32];

fn epoch_error(code: &'static str, detail: &'static str) -> TrackBDetachedVerifierV1Error {
    verifier_error(code, detail)
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

fn framed_digest(domain: &[u8], fields: &[&[u8]]) -> [u8; 32] {
    let mut message = Vec::new();
    append_frame(&mut message, domain);
    for field in fields {
        append_frame(&mut message, field);
    }
    sha256_bytes(&message)
}

#[derive(Clone, PartialEq, Eq)]
struct RestoreEpochRecordV1 {
    epoch: u64,
    predecessor_record_sha256: [u8; 32],
    registry_generation_id: [u8; 32],
    restore_event_sha256: [u8; 32],
    receiver_identity_sha256: [u8; 32],
    build_identity_sha256: [u8; 32],
    allowlist_sha256: [u8; 32],
    revocation_checkpoint_sha256: [u8; 32],
    policy_sha256: [u8; 32],
    handle_key_id: String,
    handle_key_fingerprint_sha256: [u8; 32],
    inner_transport_key_id: String,
    inner_transport_key_fingerprint_sha256: [u8; 32],
    outer_channel_key_id: String,
    outer_channel_key_fingerprint_sha256: [u8; 32],
    record_sha256: [u8; 32],
}

impl std::fmt::Debug for RestoreEpochRecordV1 {
    fn fmt(&self, formatter: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        formatter
            .debug_struct("RestoreEpochRecordV1")
            .field("epoch", &self.epoch)
            .field("identity", &"[COMMITMENT_BOUND]")
            .finish_non_exhaustive()
    }
}

#[cfg(test)]
#[derive(Clone)]
struct SyntheticActivationInputV1 {
    epoch: u64,
    predecessor_record_sha256: [u8; 32],
    registry_generation_id: [u8; 32],
    restore_event_sha256: [u8; 32],
    receiver_identity_sha256: [u8; 32],
    build_identity_sha256: [u8; 32],
    allowlist_sha256: [u8; 32],
    revocation_checkpoint_sha256: [u8; 32],
    handle_key_id: String,
    handle_key_fingerprint_sha256: [u8; 32],
    inner_transport_key_id: String,
    inner_transport_key_fingerprint_sha256: [u8; 32],
    outer_channel_key_id: String,
    outer_channel_key_fingerprint_sha256: [u8; 32],
}

fn record_digest(record: &RestoreEpochRecordV1) -> [u8; 32] {
    let epoch = record.epoch.to_be_bytes();
    framed_digest(
        RECORD_DOMAIN,
        &[
            POLICY_ID.as_bytes(),
            S7_DURABLE_CONTRACT_SHA256.as_bytes(),
            S7_SCHEMA_MANIFEST_SHA256.as_bytes(),
            &epoch,
            &record.predecessor_record_sha256,
            &record.registry_generation_id,
            &record.restore_event_sha256,
            &record.receiver_identity_sha256,
            &record.build_identity_sha256,
            &record.allowlist_sha256,
            &record.revocation_checkpoint_sha256,
            &record.policy_sha256,
            record.handle_key_id.as_bytes(),
            &record.handle_key_fingerprint_sha256,
            record.inner_transport_key_id.as_bytes(),
            &record.inner_transport_key_fingerprint_sha256,
            record.outer_channel_key_id.as_bytes(),
            &record.outer_channel_key_fingerprint_sha256,
        ],
    )
}

fn validate_record(record: &RestoreEpochRecordV1) -> VerifierResult<()> {
    let ids = [
        record.handle_key_id.as_str(),
        record.inner_transport_key_id.as_str(),
        record.outer_channel_key_id.as_str(),
    ];
    if record.epoch == 0
        || !ids.iter().all(|value| valid_label(value))
        || ids[0] == ids[1]
        || ids[0] == ids[2]
        || ids[1] == ids[2]
    {
        return Err(epoch_error(
            "track_b_restore_epoch_v1_key_role",
            "epoch and all three key-role identifiers must be valid and distinct",
        ));
    }
    let commitments = [
        record.registry_generation_id,
        record.restore_event_sha256,
        record.receiver_identity_sha256,
        record.build_identity_sha256,
        record.allowlist_sha256,
        record.revocation_checkpoint_sha256,
        record.policy_sha256,
        record.handle_key_fingerprint_sha256,
        record.inner_transport_key_fingerprint_sha256,
        record.outer_channel_key_fingerprint_sha256,
    ];
    let zero_key_fingerprint = sha256_bytes(&ZERO_COMMITMENT);
    if !commitments.iter().all(nonzero)
        || [
            record.handle_key_fingerprint_sha256,
            record.inner_transport_key_fingerprint_sha256,
            record.outer_channel_key_fingerprint_sha256,
        ]
        .contains(&zero_key_fingerprint)
        || record.handle_key_fingerprint_sha256 == record.inner_transport_key_fingerprint_sha256
        || record.handle_key_fingerprint_sha256 == record.outer_channel_key_fingerprint_sha256
        || record.inner_transport_key_fingerprint_sha256
            == record.outer_channel_key_fingerprint_sha256
    {
        return Err(epoch_error(
            "track_b_restore_epoch_v1_key_material",
            "epoch commitments and all three key fingerprints must be nonzero and distinct",
        ));
    }
    if record.policy_sha256 != sha256_bytes(POLICY_ID.as_bytes()) {
        return Err(epoch_error(
            "track_b_restore_epoch_v1_policy",
            "epoch record is not bound to the closed S8 policy",
        ));
    }
    if (record.epoch == 1) != (record.predecessor_record_sha256 == ZERO_COMMITMENT) {
        return Err(epoch_error(
            "track_b_restore_epoch_v1_predecessor",
            "only epoch one may use the genesis predecessor sentinel",
        ));
    }
    if record.record_sha256 != record_digest(record) {
        return Err(epoch_error(
            "track_b_restore_epoch_v1_record_digest",
            "epoch record digest does not match its exact closed identity",
        ));
    }
    Ok(())
}

#[cfg(test)]
fn build_record(input: SyntheticActivationInputV1) -> VerifierResult<RestoreEpochRecordV1> {
    let mut record = RestoreEpochRecordV1 {
        epoch: input.epoch,
        predecessor_record_sha256: input.predecessor_record_sha256,
        registry_generation_id: input.registry_generation_id,
        restore_event_sha256: input.restore_event_sha256,
        receiver_identity_sha256: input.receiver_identity_sha256,
        build_identity_sha256: input.build_identity_sha256,
        allowlist_sha256: input.allowlist_sha256,
        revocation_checkpoint_sha256: input.revocation_checkpoint_sha256,
        policy_sha256: sha256_bytes(POLICY_ID.as_bytes()),
        handle_key_id: input.handle_key_id,
        handle_key_fingerprint_sha256: input.handle_key_fingerprint_sha256,
        inner_transport_key_id: input.inner_transport_key_id,
        inner_transport_key_fingerprint_sha256: input.inner_transport_key_fingerprint_sha256,
        outer_channel_key_id: input.outer_channel_key_id,
        outer_channel_key_fingerprint_sha256: input.outer_channel_key_fingerprint_sha256,
        record_sha256: ZERO_COMMITMENT,
    };
    record.record_sha256 = record_digest(&record);
    validate_record(&record)?;
    Ok(record)
}

fn checked_next_epoch(current: u64) -> VerifierResult<u64> {
    current.checked_add(1).ok_or_else(|| {
        epoch_error(
            "track_b_restore_epoch_v1_sequence",
            "epoch sequence overflowed and must remain permanently closed",
        )
    })
}

#[derive(Clone)]
struct AuthenticatedCurrentnessV1 {
    challenge: [u8; 32],
    authority_sequence: u64,
    record: RestoreEpochRecordV1,
    hmac_sha256: [u8; 32],
}

mod authority_seal {
    pub(super) trait Sealed {}
}

/// A call to this trait is deliberately required for every S8 admission.
/// There is no implementation outside tests. A cached/self-contained receipt
/// is therefore not accepted as currentness by this module.
trait OnlineRestoreEpochAuthorityV1: authority_seal::Sealed {
    fn request_currentness(
        &self,
        challenge: [u8; 32],
    ) -> VerifierResult<AuthenticatedCurrentnessV1>;
}

fn currentness_message(
    challenge: &[u8; 32],
    authority_sequence: u64,
    record_sha256: &[u8; 32],
) -> Vec<u8> {
    let sequence = authority_sequence.to_be_bytes();
    let mut message = Vec::new();
    append_frame(&mut message, CURRENTNESS_DOMAIN);
    append_frame(&mut message, challenge);
    append_frame(&mut message, &sequence);
    append_frame(&mut message, b"ACTIVE");
    append_frame(&mut message, record_sha256);
    message
}

fn hmac_tag(key: &[u8; 32], message: &[u8]) -> [u8; 32] {
    let key = hmac::Key::new(hmac::HMAC_SHA256, key);
    let tag = hmac::sign(&key, message);
    let mut output = [0; 32];
    output.copy_from_slice(tag.as_ref());
    output
}

#[cfg(test)]
enum SyntheticAuthorityStateV1 {
    Closed,
    Active(RestoreEpochRecordV1),
    Pending(RestoreEpochRecordV1),
    Revoked,
}

#[cfg(test)]
struct SyntheticAuthorityInnerV1 {
    state: SyntheticAuthorityStateV1,
    authority_sequence: u64,
    used_key_ids: std::collections::BTreeSet<String>,
    used_key_fingerprints: std::collections::BTreeSet<[u8; 32]>,
    used_registry_generations: std::collections::BTreeSet<[u8; 32]>,
    used_restore_events: std::collections::BTreeSet<[u8; 32]>,
    used_revocation_checkpoints: std::collections::BTreeSet<[u8; 32]>,
}

#[cfg(test)]
struct SyntheticOnlineRestoreEpochAuthorityV1 {
    authority_key: [u8; 32],
    inner: std::sync::Mutex<SyntheticAuthorityInnerV1>,
}

#[cfg(test)]
impl Drop for SyntheticOnlineRestoreEpochAuthorityV1 {
    fn drop(&mut self) {
        self.authority_key.fill(0);
    }
}

#[cfg(test)]
impl authority_seal::Sealed for SyntheticOnlineRestoreEpochAuthorityV1 {}

#[cfg(test)]
impl SyntheticOnlineRestoreEpochAuthorityV1 {
    fn new(authority_key: [u8; 32]) -> VerifierResult<Self> {
        if !nonzero(&authority_key) {
            return Err(epoch_error(
                "track_b_restore_epoch_v1_authority_key",
                "synthetic authority key must not be the zero sentinel",
            ));
        }
        Ok(Self {
            authority_key,
            inner: std::sync::Mutex::new(SyntheticAuthorityInnerV1 {
                state: SyntheticAuthorityStateV1::Closed,
                authority_sequence: 0,
                used_key_ids: std::collections::BTreeSet::new(),
                used_key_fingerprints: std::collections::BTreeSet::new(),
                used_registry_generations: std::collections::BTreeSet::new(),
                used_restore_events: std::collections::BTreeSet::new(),
                used_revocation_checkpoints: std::collections::BTreeSet::new(),
            }),
        })
    }

    fn ensure_unused(
        inner: &SyntheticAuthorityInnerV1,
        record: &RestoreEpochRecordV1,
    ) -> VerifierResult<()> {
        let key_ids = [
            record.handle_key_id.as_str(),
            record.inner_transport_key_id.as_str(),
            record.outer_channel_key_id.as_str(),
        ];
        let fingerprints = [
            record.handle_key_fingerprint_sha256,
            record.inner_transport_key_fingerprint_sha256,
            record.outer_channel_key_fingerprint_sha256,
        ];
        if key_ids
            .iter()
            .any(|value| inner.used_key_ids.contains(*value))
            || fingerprints
                .iter()
                .any(|value| inner.used_key_fingerprints.contains(value))
            || inner
                .used_registry_generations
                .contains(&record.registry_generation_id)
            || inner
                .used_restore_events
                .contains(&record.restore_event_sha256)
            || inner
                .used_revocation_checkpoints
                .contains(&record.revocation_checkpoint_sha256)
        {
            return Err(epoch_error(
                "track_b_restore_epoch_v1_reuse",
                "key id, fingerprint, registry generation, restore event, or revocation checkpoint was reused",
            ));
        }
        Ok(())
    }

    fn burn_identity(inner: &mut SyntheticAuthorityInnerV1, record: &RestoreEpochRecordV1) {
        inner.used_key_ids.extend([
            record.handle_key_id.clone(),
            record.inner_transport_key_id.clone(),
            record.outer_channel_key_id.clone(),
        ]);
        inner.used_key_fingerprints.extend([
            record.handle_key_fingerprint_sha256,
            record.inner_transport_key_fingerprint_sha256,
            record.outer_channel_key_fingerprint_sha256,
        ]);
        inner
            .used_registry_generations
            .insert(record.registry_generation_id);
        inner
            .used_restore_events
            .insert(record.restore_event_sha256);
        inner
            .used_revocation_checkpoints
            .insert(record.revocation_checkpoint_sha256);
    }

    fn activate_genesis(
        &self,
        input: SyntheticActivationInputV1,
    ) -> VerifierResult<RestoreEpochRecordV1> {
        let record = build_record(input)?;
        if record.epoch != 1 || record.predecessor_record_sha256 != ZERO_COMMITMENT {
            return Err(epoch_error(
                "track_b_restore_epoch_v1_sequence",
                "genesis must be exactly epoch one",
            ));
        }
        let mut inner = self.inner.lock().map_err(|_| {
            epoch_error(
                "track_b_restore_epoch_v1_authority_indeterminate",
                "synthetic authority lock is indeterminate",
            )
        })?;
        if !matches!(inner.state, SyntheticAuthorityStateV1::Closed) {
            return Err(epoch_error(
                "track_b_restore_epoch_v1_sequence",
                "genesis is allowed only from the closed state",
            ));
        }
        Self::ensure_unused(&inner, &record)?;
        Self::burn_identity(&mut inner, &record);
        inner.authority_sequence = 1;
        inner.state = SyntheticAuthorityStateV1::Active(record.clone());
        Ok(record)
    }

    /// Fences the current epoch before making the next one pending. Once this
    /// succeeds, the old epoch has no currentness response and there is no
    /// local fallback path.
    fn begin_controlled_restore(
        &self,
        expected_current_record_sha256: [u8; 32],
        input: SyntheticActivationInputV1,
    ) -> VerifierResult<RestoreEpochRecordV1> {
        let next = build_record(input)?;
        let mut inner = self.inner.lock().map_err(|_| {
            epoch_error(
                "track_b_restore_epoch_v1_authority_indeterminate",
                "synthetic authority lock is indeterminate",
            )
        })?;
        let current = match &inner.state {
            SyntheticAuthorityStateV1::Active(record) => record,
            _ => {
                return Err(epoch_error(
                    "track_b_restore_epoch_v1_not_active",
                    "controlled restore requires one exact active predecessor",
                ));
            }
        };
        if current.record_sha256 != expected_current_record_sha256
            || next.epoch != checked_next_epoch(current.epoch)?
            || next.predecessor_record_sha256 != current.record_sha256
        {
            return Err(epoch_error(
                "track_b_restore_epoch_v1_sequence",
                "next epoch must be the exact successor of the active record",
            ));
        }
        Self::ensure_unused(&inner, &next)?;
        let Some(next_authority_sequence) = inner.authority_sequence.checked_add(1) else {
            inner.state = SyntheticAuthorityStateV1::Revoked;
            return Err(epoch_error(
                "track_b_restore_epoch_v1_sequence",
                "authority sequence overflow fenced the active epoch closed",
            ));
        };
        Self::burn_identity(&mut inner, &next);
        inner.authority_sequence = next_authority_sequence;
        inner.state = SyntheticAuthorityStateV1::Pending(next.clone());
        Ok(next)
    }

    fn activate_pending(
        &self,
        expected_pending_record_sha256: [u8; 32],
    ) -> VerifierResult<RestoreEpochRecordV1> {
        let mut inner = self.inner.lock().map_err(|_| {
            epoch_error(
                "track_b_restore_epoch_v1_authority_indeterminate",
                "synthetic authority lock is indeterminate",
            )
        })?;
        let pending = match &inner.state {
            SyntheticAuthorityStateV1::Pending(record)
                if record.record_sha256 == expected_pending_record_sha256 =>
            {
                record.clone()
            }
            _ => {
                return Err(epoch_error(
                    "track_b_restore_epoch_v1_not_active",
                    "only the exact pending epoch can become active",
                ));
            }
        };
        let Some(next_authority_sequence) = inner.authority_sequence.checked_add(1) else {
            inner.state = SyntheticAuthorityStateV1::Revoked;
            return Err(epoch_error(
                "track_b_restore_epoch_v1_sequence",
                "authority sequence overflow kept the pending epoch closed",
            ));
        };
        inner.authority_sequence = next_authority_sequence;
        inner.state = SyntheticAuthorityStateV1::Active(pending.clone());
        Ok(pending)
    }

    fn revoke_current(&self, expected_current_record_sha256: [u8; 32]) -> VerifierResult<()> {
        let mut inner = self.inner.lock().map_err(|_| {
            epoch_error(
                "track_b_restore_epoch_v1_authority_indeterminate",
                "synthetic authority lock is indeterminate",
            )
        })?;
        let matches = matches!(
            &inner.state,
            SyntheticAuthorityStateV1::Active(record)
                if record.record_sha256 == expected_current_record_sha256
        );
        if !matches {
            return Err(epoch_error(
                "track_b_restore_epoch_v1_stale",
                "revocation target is not the exact active epoch",
            ));
        }
        let Some(next_authority_sequence) = inner.authority_sequence.checked_add(1) else {
            inner.state = SyntheticAuthorityStateV1::Revoked;
            return Err(epoch_error(
                "track_b_restore_epoch_v1_sequence",
                "authority sequence overflow fenced the active epoch closed",
            ));
        };
        inner.authority_sequence = next_authority_sequence;
        inner.state = SyntheticAuthorityStateV1::Revoked;
        Ok(())
    }
}

#[cfg(test)]
impl OnlineRestoreEpochAuthorityV1 for SyntheticOnlineRestoreEpochAuthorityV1 {
    fn request_currentness(
        &self,
        challenge: [u8; 32],
    ) -> VerifierResult<AuthenticatedCurrentnessV1> {
        if !nonzero(&challenge) {
            return Err(epoch_error(
                "track_b_restore_epoch_v1_challenge",
                "currentness challenge must not be the zero sentinel",
            ));
        }
        let inner = self.inner.lock().map_err(|_| {
            epoch_error(
                "track_b_restore_epoch_v1_authority_indeterminate",
                "synthetic authority lock is indeterminate",
            )
        })?;
        let record = match &inner.state {
            SyntheticAuthorityStateV1::Active(record) => record.clone(),
            SyntheticAuthorityStateV1::Closed
            | SyntheticAuthorityStateV1::Pending(_)
            | SyntheticAuthorityStateV1::Revoked => {
                return Err(epoch_error(
                    "track_b_restore_epoch_v1_not_active",
                    "online authority has no active epoch and local fallback is forbidden",
                ));
            }
        };
        let message =
            currentness_message(&challenge, inner.authority_sequence, &record.record_sha256);
        Ok(AuthenticatedCurrentnessV1 {
            challenge,
            authority_sequence: inner.authority_sequence,
            record,
            hmac_sha256: hmac_tag(&self.authority_key, &message),
        })
    }
}

/// Synthetic capability for one expected epoch. Construction is test-only;
/// the shared HMAC key is a test stand-in for an online external verifier, not
/// evidence of asymmetric signatures, KMS custody, or production authority.
struct SyntheticRestoreEpochAdmissionPermitV1 {
    expected: RestoreEpochRecordV1,
    authority_key: [u8; 32],
    handle_key: [u8; 32],
    outer_channel_key: [u8; 32],
}

impl Drop for SyntheticRestoreEpochAdmissionPermitV1 {
    fn drop(&mut self) {
        self.authority_key.fill(0);
        self.handle_key.fill(0);
        self.outer_channel_key.fill(0);
    }
}

impl std::fmt::Debug for SyntheticRestoreEpochAdmissionPermitV1 {
    fn fmt(&self, formatter: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        formatter
            .debug_struct("SyntheticRestoreEpochAdmissionPermitV1")
            .field("epoch", &self.expected.epoch)
            .field("key_material", &"[REDACTED]")
            .finish_non_exhaustive()
    }
}

#[cfg(test)]
fn synthetic_epoch_permit_for_test(
    expected: RestoreEpochRecordV1,
    authority_key: [u8; 32],
    handle_key: [u8; 32],
    outer_channel_key: [u8; 32],
) -> VerifierResult<SyntheticRestoreEpochAdmissionPermitV1> {
    validate_record(&expected)?;
    let authority_key_fingerprint = sha256_bytes(&authority_key);
    if !nonzero(&authority_key)
        || !nonzero(&handle_key)
        || !nonzero(&outer_channel_key)
        || authority_key_fingerprint == expected.handle_key_fingerprint_sha256
        || authority_key_fingerprint == expected.inner_transport_key_fingerprint_sha256
        || authority_key_fingerprint == expected.outer_channel_key_fingerprint_sha256
        || sha256_bytes(&handle_key) != expected.handle_key_fingerprint_sha256
        || sha256_bytes(&outer_channel_key) != expected.outer_channel_key_fingerprint_sha256
    {
        return Err(epoch_error(
            "track_b_restore_epoch_v1_permit",
            "synthetic authority and role keys must be nonzero, distinct, and record-bound",
        ));
    }
    Ok(SyntheticRestoreEpochAdmissionPermitV1 {
        expected,
        authority_key,
        handle_key,
        outer_channel_key,
    })
}

struct RestoreEpochPacketAuthenticationV1 {
    algorithm: String,
    domain: String,
    message_profile: String,
    epoch: u64,
    record_sha256: [u8; 32],
    outer_channel_key_id: String,
    payload_sha256: [u8; 32],
    hmac_sha256: [u8; 32],
}

fn outer_authentication_message(record: &RestoreEpochRecordV1, exact_payload: &[u8]) -> Vec<u8> {
    let epoch = record.epoch.to_be_bytes();
    let mut message = Vec::new();
    append_frame(&mut message, OUTER_AUTHENTICATION_DOMAIN.as_bytes());
    for field in [
        epoch.as_slice(),
        record.record_sha256.as_slice(),
        record.predecessor_record_sha256.as_slice(),
        record.registry_generation_id.as_slice(),
        record.restore_event_sha256.as_slice(),
        record.receiver_identity_sha256.as_slice(),
        record.build_identity_sha256.as_slice(),
        record.allowlist_sha256.as_slice(),
        record.revocation_checkpoint_sha256.as_slice(),
        record.policy_sha256.as_slice(),
        record.handle_key_id.as_bytes(),
        record.handle_key_fingerprint_sha256.as_slice(),
        record.inner_transport_key_id.as_bytes(),
        record.inner_transport_key_fingerprint_sha256.as_slice(),
        record.outer_channel_key_id.as_bytes(),
        record.outer_channel_key_fingerprint_sha256.as_slice(),
    ] {
        append_frame(&mut message, field);
    }
    append_frame(&mut message, exact_payload);
    message
}

#[cfg(test)]
fn packet_authentication_for_test(
    record: &RestoreEpochRecordV1,
    outer_channel_key: &[u8; 32],
    exact_payload: &[u8],
) -> RestoreEpochPacketAuthenticationV1 {
    let message = outer_authentication_message(record, exact_payload);
    RestoreEpochPacketAuthenticationV1 {
        algorithm: OUTER_AUTHENTICATION_ALGORITHM.to_string(),
        domain: OUTER_AUTHENTICATION_DOMAIN.to_string(),
        message_profile: OUTER_AUTHENTICATION_MESSAGE_PROFILE.to_string(),
        epoch: record.epoch,
        record_sha256: record.record_sha256,
        outer_channel_key_id: record.outer_channel_key_id.clone(),
        payload_sha256: sha256_bytes(exact_payload),
        hmac_sha256: hmac_tag(outer_channel_key, &message),
    }
}

fn verify_currentness(
    permit: &SyntheticRestoreEpochAdmissionPermitV1,
    response: &AuthenticatedCurrentnessV1,
    challenge: &[u8; 32],
) -> VerifierResult<()> {
    if response.challenge != *challenge
        || response.authority_sequence == 0
        || response.record != permit.expected
    {
        return Err(epoch_error(
            "track_b_restore_epoch_v1_stale",
            "online currentness response does not match the expected active epoch",
        ));
    }
    let message = currentness_message(
        challenge,
        response.authority_sequence,
        &response.record.record_sha256,
    );
    let key = hmac::Key::new(hmac::HMAC_SHA256, &permit.authority_key);
    hmac::verify(&key, &message, &response.hmac_sha256).map_err(|_| {
        epoch_error(
            "track_b_restore_epoch_v1_currentness_authentication",
            "online currentness authentication failed",
        )
    })
}

#[must_use]
struct VerifiedRestoreEpochCandidateV1 {
    inner: VerifiedDetachedCandidateV1,
    epoch: u64,
    epoch_record_sha256: [u8; 32],
}

impl std::fmt::Debug for VerifiedRestoreEpochCandidateV1 {
    fn fmt(&self, formatter: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        formatter
            .debug_struct("VerifiedRestoreEpochCandidateV1")
            .field("epoch", &self.epoch)
            .field("inner", &self.inner)
            .field("epoch_record", &"[COMMITMENT_BOUND]")
            .finish_non_exhaustive()
    }
}

/// Verifies an epoch-bound outer authentication, online currentness, exact
/// three-key-role binding, S7 generation, S6 exact-byte authentication, and
/// the durable S7 replay consume. No token is returned on any uncertainty.
#[allow(clippy::too_many_arguments)]
fn verify_synthetic_restore_epoch_candidate_v1<A: OnlineRestoreEpochAuthorityV1>(
    epoch_permit: SyntheticRestoreEpochAdmissionPermitV1,
    detached_permit: SyntheticDetachedVerificationPermitV1,
    epoch_authentication: RestoreEpochPacketAuthenticationV1,
    detached_authentication: DetachedCandidateAuthenticationV1,
    exact_payload: Box<[u8]>,
    registry: &SyntheticDurableReplayRegistryV1,
    authority: &A,
    currentness_challenge: [u8; 32],
    evaluated_at_utc: i64,
) -> VerifierResult<VerifiedRestoreEpochCandidateV1> {
    validate_record(&epoch_permit.expected)?;
    if exact_payload.is_empty()
        || exact_payload.len() >= MAX_ENVELOPE_BYTES
        || !nonzero(&currentness_challenge)
    {
        return Err(epoch_error(
            "track_b_restore_epoch_v1_capacity_or_challenge",
            "payload must remain below the S6 cap and currentness challenge must be present",
        ));
    }
    if epoch_authentication.algorithm != OUTER_AUTHENTICATION_ALGORITHM
        || epoch_authentication.domain != OUTER_AUTHENTICATION_DOMAIN
        || epoch_authentication.message_profile != OUTER_AUTHENTICATION_MESSAGE_PROFILE
        || epoch_authentication.epoch != epoch_permit.expected.epoch
        || epoch_authentication.record_sha256 != epoch_permit.expected.record_sha256
        || epoch_authentication.outer_channel_key_id != epoch_permit.expected.outer_channel_key_id
        || epoch_authentication.payload_sha256 != sha256_bytes(&exact_payload)
    {
        return Err(epoch_error(
            "track_b_restore_epoch_v1_packet_profile",
            "epoch-bound packet authentication identity drifted",
        ));
    }
    let outer_message = outer_authentication_message(&epoch_permit.expected, &exact_payload);
    let outer_key = hmac::Key::new(hmac::HMAC_SHA256, &epoch_permit.outer_channel_key);
    hmac::verify(
        &outer_key,
        &outer_message,
        &epoch_authentication.hmac_sha256,
    )
    .map_err(|_| {
        epoch_error(
            "track_b_restore_epoch_v1_packet_authentication",
            "epoch-bound exact payload authentication failed",
        )
    })?;
    drop(outer_message);

    if detached_permit.transport_key_id != epoch_permit.expected.inner_transport_key_id
        || sha256_bytes(&detached_permit.transport_key)
            != epoch_permit.expected.inner_transport_key_fingerprint_sha256
        || sha256_bytes(&epoch_permit.handle_key)
            != epoch_permit.expected.handle_key_fingerprint_sha256
        || sha256_bytes(&epoch_permit.outer_channel_key)
            != epoch_permit.expected.outer_channel_key_fingerprint_sha256
    {
        return Err(epoch_error(
            "track_b_restore_epoch_v1_key_binding",
            "permit material does not match all epoch key-role commitments",
        ));
    }
    if detached_permit.expected.handle_key_id != epoch_permit.expected.handle_key_id {
        return Err(epoch_error(
            "track_b_restore_epoch_v1_handle_binding",
            "S6 permit handle key id does not match the active epoch",
        ));
    }
    if registry.generation_id_for_restore_epoch() != epoch_permit.expected.registry_generation_id {
        return Err(epoch_error(
            "track_b_restore_epoch_v1_registry_generation",
            "S7 registry generation does not match the active restore epoch",
        ));
    }

    let currentness = authority.request_currentness(currentness_challenge)?;
    verify_currentness(&epoch_permit, &currentness, &currentness_challenge)?;

    let epoch = epoch_permit.expected.epoch;
    let epoch_record_sha256 = epoch_permit.expected.record_sha256;
    let inner = verify_synthetic_detached_candidate_durable_v1(
        detached_permit,
        detached_authentication,
        exact_payload,
        registry,
        evaluated_at_utc,
    )?;
    Ok(VerifiedRestoreEpochCandidateV1 {
        inner,
        epoch,
        epoch_record_sha256,
    })
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::temporal_replay_transport::{
        bytes_to_hex, detached_hmac_tag, synthetic_detached_verification_permit_v1,
        synthetic_source_manifest_token_v1, CandidatePayloadWire,
        DetachedCandidateAuthenticationV1, ExpectedCandidateIdentityV1, AUTHENTICATION_ALGORITHM,
        AUTHENTICATION_CANONICALIZATION, AUTHENTICATION_DOMAIN, AUTHENTICATION_MESSAGE_PROFILE,
    };
    use std::path::PathBuf;
    use std::sync::Arc;

    const AUTHORITY_KEY: [u8; 32] = [0xa8; 32];

    #[derive(Clone)]
    struct EpochKeys {
        handle: [u8; 32],
        inner: [u8; 32],
        outer: [u8; 32],
        handle_id: String,
        inner_id: String,
        outer_id: String,
    }

    impl EpochKeys {
        fn new(epoch: u8) -> Self {
            Self {
                handle: [epoch.wrapping_add(0x10); 32],
                inner: [epoch.wrapping_add(0x30); 32],
                outer: [epoch.wrapping_add(0x50); 32],
                handle_id: format!("handle-key-s8-e{epoch}"),
                inner_id: format!("inner-key-s8-e{epoch}"),
                outer_id: format!("outer-key-s8-e{epoch}"),
            }
        }
    }

    struct TestDirectory {
        path: PathBuf,
    }

    impl TestDirectory {
        fn new(label: &str) -> Self {
            let path = std::env::temp_dir().join(format!(
                "ab-s8-{label}-{}-{}",
                std::process::id(),
                std::time::SystemTime::now()
                    .duration_since(std::time::UNIX_EPOCH)
                    .expect("system clock")
                    .as_nanos()
            ));
            std::fs::create_dir(&path).expect("create isolated S8 directory");
            Self { path }
        }

        fn database(&self, name: &str) -> PathBuf {
            self.path.join(name)
        }
    }

    impl Drop for TestDirectory {
        fn drop(&mut self) {
            let _ = std::fs::remove_dir_all(&self.path);
        }
    }

    fn activation(
        epoch: u64,
        generation_byte: u8,
        restore_byte: u8,
        predecessor: [u8; 32],
        keys: &EpochKeys,
    ) -> SyntheticActivationInputV1 {
        SyntheticActivationInputV1 {
            epoch,
            predecessor_record_sha256: predecessor,
            registry_generation_id: [generation_byte; 32],
            restore_event_sha256: [restore_byte; 32],
            receiver_identity_sha256: [0x81; 32],
            build_identity_sha256: [0x82; 32],
            allowlist_sha256: [0x83; 32],
            revocation_checkpoint_sha256: [restore_byte.wrapping_add(1); 32],
            handle_key_id: keys.handle_id.clone(),
            handle_key_fingerprint_sha256: sha256_bytes(&keys.handle),
            inner_transport_key_id: keys.inner_id.clone(),
            inner_transport_key_fingerprint_sha256: sha256_bytes(&keys.inner),
            outer_channel_key_id: keys.outer_id.clone(),
            outer_channel_key_fingerprint_sha256: sha256_bytes(&keys.outer),
        }
    }

    fn expected(payload: &CandidatePayloadWire) -> ExpectedCandidateIdentityV1 {
        ExpectedCandidateIdentityV1 {
            case_id: payload.case_id.clone(),
            contract_sha256: payload.contract_sha256.clone(),
            expires_at_utc: payload.expires_at_utc,
            handle_key_id: payload.handle_key_id.clone(),
            issued_at_utc: payload.issued_at_utc,
            projection_binding_handle: payload.projection_binding_handle.clone(),
            request_id: payload.request_id.clone(),
            request_nonce: payload.request_nonce.clone(),
            trial_id: payload.trial_id.clone(),
        }
    }

    fn inner_permit(
        payload: &CandidatePayloadWire,
        keys: &EpochKeys,
    ) -> SyntheticDetachedVerificationPermitV1 {
        synthetic_detached_verification_permit_v1(
            synthetic_source_manifest_token_v1(),
            keys.inner,
            keys.inner_id.clone(),
            expected(payload),
        )
        .expect("synthetic inner permit")
    }

    fn inner_authentication(
        exact_payload: &[u8],
        keys: &EpochKeys,
    ) -> DetachedCandidateAuthenticationV1 {
        DetachedCandidateAuthenticationV1::try_new(
            AUTHENTICATION_ALGORITHM,
            AUTHENTICATION_CANONICALIZATION,
            AUTHENTICATION_DOMAIN,
            &bytes_to_hex(&detached_hmac_tag(
                &keys.inner,
                &keys.inner_id,
                exact_payload,
            )),
            keys.inner_id.clone(),
            AUTHENTICATION_MESSAGE_PROFILE,
            &bytes_to_hex(&sha256_bytes(exact_payload)),
        )
        .expect("synthetic inner authentication")
    }

    fn packet(
        trial: &str,
        nonce_byte: char,
        keys: &EpochKeys,
    ) -> (CandidatePayloadWire, Box<[u8]>) {
        let mut payload = super::super::tests::sample_payload(trial);
        payload.handle_key_id = keys.handle_id.clone();
        payload.request_id = format!("request-{trial}");
        payload.request_nonce = nonce_byte.to_string().repeat(64);
        let exact = super::super::tests::canonical(&payload);
        (payload, exact)
    }

    #[allow(clippy::too_many_arguments)]
    fn admit<A: OnlineRestoreEpochAuthorityV1>(
        record: &RestoreEpochRecordV1,
        keys: &EpochKeys,
        payload: &CandidatePayloadWire,
        exact: Box<[u8]>,
        registry: &SyntheticDurableReplayRegistryV1,
        authority: &A,
        challenge_byte: u8,
    ) -> VerifierResult<VerifiedRestoreEpochCandidateV1> {
        verify_synthetic_restore_epoch_candidate_v1(
            synthetic_epoch_permit_for_test(
                record.clone(),
                AUTHORITY_KEY,
                keys.handle,
                keys.outer,
            )?,
            inner_permit(payload, keys),
            packet_authentication_for_test(record, &keys.outer, &exact),
            inner_authentication(&exact, keys),
            exact,
            registry,
            authority,
            [challenge_byte; 32],
            150,
        )
    }

    fn genesis(
        authority: &SyntheticOnlineRestoreEpochAuthorityV1,
        keys: &EpochKeys,
        generation: u8,
    ) -> RestoreEpochRecordV1 {
        authority
            .activate_genesis(activation(1, generation, 0x91, ZERO_COMMITMENT, keys))
            .expect("activate synthetic genesis")
    }

    #[test]
    fn s8_record_outer_authentication_and_currentness_known_vectors_are_stable() {
        let authority = SyntheticOnlineRestoreEpochAuthorityV1::new(AUTHORITY_KEY).unwrap();
        let keys = EpochKeys::new(1);
        let record = genesis(&authority, &keys, 0x71);
        assert_eq!(
            bytes_to_hex(&record.policy_sha256),
            "82dd7ee0cd71897d8cc274db05fb8ae4f88bfe8dfcd7f17b5622b731a72cde7c"
        );
        assert_eq!(
            bytes_to_hex(&record.record_sha256),
            "19c19488aa3826bbea780bdf93c04f711b0c154a9a493f2d0359ddec9fab236f"
        );
        let exact = br#"{"synthetic":"s8-known-vector"}"#;
        let packet_authentication = packet_authentication_for_test(&record, &keys.outer, exact);
        assert_eq!(
            bytes_to_hex(&packet_authentication.payload_sha256),
            "0e1b61ab401e0156d162b59e02d122c19b2a3a9f118c187b4fffaeb54441ba27"
        );
        assert_eq!(
            bytes_to_hex(&packet_authentication.hmac_sha256),
            "cfc4aa32f0b131c75d9e0b0565f256eb3ceca239e22bbbc6577e56f1acfa47ab"
        );
        let currentness = authority.request_currentness([0xc1; 32]).unwrap();
        assert_eq!(
            bytes_to_hex(&currentness.hmac_sha256),
            "a8668b2c6e7f55aa46c551c7c9d1ee0190b4074b4765bc69781b2a10d3adbb11"
        );
    }

    #[test]
    fn s8_active_epoch_binds_three_keys_currentness_and_durable_replay() {
        let directory = TestDirectory::new("active");
        let authority = SyntheticOnlineRestoreEpochAuthorityV1::new(AUTHORITY_KEY).unwrap();
        let keys = EpochKeys::new(1);
        let record = genesis(&authority, &keys, 0x71);
        let registry = super::super::durable_replay_registry::provision_and_open_for_test(
            &directory.database("replay.db"),
            record.registry_generation_id,
        )
        .unwrap();
        let (payload, exact) = packet("s8-active", '1', &keys);
        let verified = admit(&record, &keys, &payload, exact, &registry, &authority, 0x11)
            .expect("active epoch admits exact packet once");
        assert_eq!(verified.epoch, 1);
        assert_eq!(verified.epoch_record_sha256, record.record_sha256);
        drop(verified);
        let (_, replay_exact) = packet("s8-active", '1', &keys);
        let replay = admit(
            &record,
            &keys,
            &payload,
            replay_exact,
            &registry,
            &authority,
            0x12,
        )
        .expect_err("durable replay must remain rejected");
        assert_eq!(replay.code(), "track_b_detached_v1_replay");
    }

    #[test]
    fn s8_restore_fences_old_epoch_before_next_activation() {
        let directory = TestDirectory::new("fence-before-active");
        let authority = SyntheticOnlineRestoreEpochAuthorityV1::new(AUTHORITY_KEY).unwrap();
        let keys1 = EpochKeys::new(1);
        let record1 = genesis(&authority, &keys1, 0x71);
        let registry1 = super::super::durable_replay_registry::provision_and_open_for_test(
            &directory.database("epoch1.db"),
            record1.registry_generation_id,
        )
        .unwrap();
        let keys2 = EpochKeys::new(2);
        let pending = authority
            .begin_controlled_restore(
                record1.record_sha256,
                activation(2, 0x72, 0x92, record1.record_sha256, &keys2),
            )
            .unwrap();
        let (old_payload, old_exact) = packet("s8-old-pending", '2', &keys1);
        let error = admit(
            &record1,
            &keys1,
            &old_payload,
            old_exact,
            &registry1,
            &authority,
            0x21,
        )
        .expect_err("pending transition has no old-epoch fallback");
        assert_eq!(error.code(), "track_b_restore_epoch_v1_not_active");

        let record2 = authority.activate_pending(pending.record_sha256).unwrap();
        let registry2 = super::super::durable_replay_registry::provision_and_open_for_test(
            &directory.database("epoch2.db"),
            record2.registry_generation_id,
        )
        .unwrap();
        let (new_payload, new_exact) = packet("s8-new-active", '3', &keys2);
        let _verified = admit(
            &record2,
            &keys2,
            &new_payload,
            new_exact,
            &registry2,
            &authority,
            0x22,
        )
        .expect("new epoch admits only after explicit activation");
    }

    #[test]
    fn s8_new_epoch_rejects_old_database_and_old_packet() {
        let directory = TestDirectory::new("old-db-packet");
        let authority = SyntheticOnlineRestoreEpochAuthorityV1::new(AUTHORITY_KEY).unwrap();
        let keys1 = EpochKeys::new(1);
        let record1 = genesis(&authority, &keys1, 0x71);
        let old_path = directory.database("old.db");
        let old_registry = super::super::durable_replay_registry::provision_and_open_for_test(
            &old_path,
            record1.registry_generation_id,
        )
        .unwrap();
        let keys2 = EpochKeys::new(2);
        let pending = authority
            .begin_controlled_restore(
                record1.record_sha256,
                activation(2, 0x72, 0x92, record1.record_sha256, &keys2),
            )
            .unwrap();
        let record2 = authority.activate_pending(pending.record_sha256).unwrap();

        let (new_payload, new_exact) = packet("s8-new-over-old-db", '4', &keys2);
        let error = admit(
            &record2,
            &keys2,
            &new_payload,
            new_exact,
            &old_registry,
            &authority,
            0x31,
        )
        .expect_err("new epoch cannot consume in an old-generation registry");
        assert_eq!(error.code(), "track_b_restore_epoch_v1_registry_generation");

        let (old_payload, old_exact) = packet("s8-old-after-rotate", '5', &keys1);
        let error = admit(
            &record1,
            &keys1,
            &old_payload,
            old_exact,
            &old_registry,
            &authority,
            0x32,
        )
        .expect_err("online currentness rejects an old epoch packet");
        assert_eq!(error.code(), "track_b_restore_epoch_v1_stale");
        assert!(
            super::super::durable_replay_registry::open_for_test(
                &old_path,
                record2.registry_generation_id
            )
            .is_err(),
            "S7 generation pin independently rejects the old database"
        );
    }

    #[test]
    fn s8_same_epoch_backup_restore_is_explicitly_undetected_negative_evidence() {
        let directory = TestDirectory::new("same-epoch-negative-evidence");
        let authority = SyntheticOnlineRestoreEpochAuthorityV1::new(AUTHORITY_KEY).unwrap();
        let keys = EpochKeys::new(1);
        let record = genesis(&authority, &keys, 0x71);
        let path = directory.database("live.db");
        let backup = directory.database("same-epoch-backup.db");
        let registry = super::super::durable_replay_registry::provision_and_open_for_test(
            &path,
            record.registry_generation_id,
        )
        .unwrap();
        std::fs::copy(&path, &backup).expect("copy pre-consume same-epoch backup");
        let (payload, exact) = packet("s8-same-epoch-gap", '6', &keys);
        let _first = admit(&record, &keys, &payload, exact, &registry, &authority, 0x41)
            .expect("first consume");
        drop(registry);

        std::fs::remove_file(&path).expect("remove current sidecar");
        std::fs::copy(&backup, &path).expect("restore same-epoch backup");
        let restored = super::super::durable_replay_registry::open_for_test(
            &path,
            record.registry_generation_id,
        )
        .expect("same generation remains locally indistinguishable");
        let (_, replay_after_restore) = packet("s8-same-epoch-gap", '6', &keys);
        let _negative_evidence = admit(
            &record,
            &keys,
            &payload,
            replay_after_restore,
            &restored,
            &authority,
            0x42,
        )
        .expect("UNRESOLVED: same-epoch rollback can erase a local tombstone");
    }

    #[test]
    fn s8_sequence_skip_decrement_and_identity_reuse_leave_current_active() {
        let authority = SyntheticOnlineRestoreEpochAuthorityV1::new(AUTHORITY_KEY).unwrap();
        let keys1 = EpochKeys::new(1);
        let record1 = genesis(&authority, &keys1, 0x71);
        let keys2 = EpochKeys::new(2);

        for (invalid_epoch, expected_code) in [
            (1, "track_b_restore_epoch_v1_predecessor"),
            (3, "track_b_restore_epoch_v1_sequence"),
        ] {
            let error = authority
                .begin_controlled_restore(
                    record1.record_sha256,
                    activation(invalid_epoch, 0x72, 0x92, record1.record_sha256, &keys2),
                )
                .expect_err("decrement/repeat/skip must reject");
            assert_eq!(error.code(), expected_code);
        }

        let mut reused = activation(2, 0x71, 0x91, record1.record_sha256, &keys2);
        reused.handle_key_id = keys1.handle_id.clone();
        let error = authority
            .begin_controlled_restore(record1.record_sha256, reused)
            .expect_err("any historical id/generation/restore reuse rejects");
        assert_eq!(error.code(), "track_b_restore_epoch_v1_reuse");
        authority
            .request_currentness([0x51; 32])
            .expect("failed rotations must leave the exact predecessor active");
    }

    #[test]
    fn s8_cross_role_collision_and_key_fingerprint_reuse_reject() {
        let authority = SyntheticOnlineRestoreEpochAuthorityV1::new(AUTHORITY_KEY).unwrap();
        let keys1 = EpochKeys::new(1);
        let record1 = genesis(&authority, &keys1, 0x71);
        let keys2 = EpochKeys::new(2);
        let mut collision = activation(2, 0x72, 0x92, record1.record_sha256, &keys2);
        collision.outer_channel_key_id = collision.inner_transport_key_id.clone();
        let error = authority
            .begin_controlled_restore(record1.record_sha256, collision)
            .expect_err("same-epoch role IDs must remain distinct");
        assert_eq!(error.code(), "track_b_restore_epoch_v1_key_role");

        let mut reused_fingerprint = activation(2, 0x72, 0x92, record1.record_sha256, &keys2);
        reused_fingerprint.outer_channel_key_fingerprint_sha256 =
            record1.handle_key_fingerprint_sha256;
        let error = authority
            .begin_controlled_restore(record1.record_sha256, reused_fingerprint)
            .expect_err("historical fingerprint reuse must reject");
        assert_eq!(error.code(), "track_b_restore_epoch_v1_reuse");

        let mut zero_key = activation(2, 0x72, 0x92, record1.record_sha256, &keys2);
        zero_key.handle_key_fingerprint_sha256 = sha256_bytes(&ZERO_COMMITMENT);
        let error = authority
            .begin_controlled_restore(record1.record_sha256, zero_key)
            .expect_err("all-zero role key material must be forbidden by fingerprint");
        assert_eq!(error.code(), "track_b_restore_epoch_v1_key_material");
        let error = synthetic_epoch_permit_for_test(
            record1.clone(),
            keys1.handle,
            keys1.handle,
            keys1.outer,
        )
        .expect_err("synthetic authority key must be separate from every data-role key");
        assert_eq!(error.code(), "track_b_restore_epoch_v1_permit");
        assert_eq!(
            checked_next_epoch(u64::MAX)
                .expect_err("epoch overflow closes permanently")
                .code(),
            "track_b_restore_epoch_v1_sequence"
        );
    }

    #[test]
    fn s8_currentness_is_challenge_bound_and_unavailable_has_no_fallback() {
        struct FrozenResponseProvider(AuthenticatedCurrentnessV1);
        impl authority_seal::Sealed for FrozenResponseProvider {}
        impl OnlineRestoreEpochAuthorityV1 for FrozenResponseProvider {
            fn request_currentness(
                &self,
                _challenge: [u8; 32],
            ) -> VerifierResult<AuthenticatedCurrentnessV1> {
                Ok(self.0.clone())
            }
        }
        struct UnavailableProvider;
        impl authority_seal::Sealed for UnavailableProvider {}
        impl OnlineRestoreEpochAuthorityV1 for UnavailableProvider {
            fn request_currentness(
                &self,
                _challenge: [u8; 32],
            ) -> VerifierResult<AuthenticatedCurrentnessV1> {
                Err(epoch_error(
                    "track_b_restore_epoch_v1_authority_unavailable",
                    "synthetic authority unavailable",
                ))
            }
        }

        let directory = TestDirectory::new("currentness");
        let authority = SyntheticOnlineRestoreEpochAuthorityV1::new(AUTHORITY_KEY).unwrap();
        let keys = EpochKeys::new(1);
        let record = genesis(&authority, &keys, 0x71);
        let registry = super::super::durable_replay_registry::provision_and_open_for_test(
            &directory.database("replay.db"),
            record.registry_generation_id,
        )
        .unwrap();
        let frozen = FrozenResponseProvider(authority.request_currentness([0x61; 32]).unwrap());
        let (payload, exact) = packet("s8-stale-response", '7', &keys);
        let error = admit(&record, &keys, &payload, exact, &registry, &frozen, 0x62)
            .expect_err("a response for another challenge is stale");
        assert_eq!(error.code(), "track_b_restore_epoch_v1_stale");

        let mut forged_response = authority.request_currentness([0x64; 32]).unwrap();
        forged_response.hmac_sha256[0] ^= 1;
        let forged = FrozenResponseProvider(forged_response);
        let (payload, exact) = packet("s8-forged-currentness", 'c', &keys);
        let error = admit(&record, &keys, &payload, exact, &registry, &forged, 0x64)
            .expect_err("a correct-identity response with a changed tag must reject");
        assert_eq!(
            error.code(),
            "track_b_restore_epoch_v1_currentness_authentication"
        );

        let reused_response = authority.request_currentness([0x65; 32]).unwrap();
        authority.revoke_current(record.record_sha256).unwrap();
        let reused = FrozenResponseProvider(reused_response);
        let (payload, exact) = packet("s8-reused-challenge-gap", 'e', &keys);
        let _negative_evidence = admit(&record, &keys, &payload, exact, &registry, &reused, 0x65)
            .expect("UNRESOLVED: a reused challenge can replay stale currentness");

        let (payload, exact) = packet("s8-unavailable", '8', &keys);
        let error = admit(
            &record,
            &keys,
            &payload,
            exact,
            &registry,
            &UnavailableProvider,
            0x63,
        )
        .expect_err("authority failure must never fall back to local S7");
        assert_eq!(
            error.code(),
            "track_b_restore_epoch_v1_authority_unavailable"
        );
    }

    #[test]
    fn s8_packet_epoch_and_exact_byte_tamper_reject_before_consume() {
        let directory = TestDirectory::new("tamper");
        let authority = SyntheticOnlineRestoreEpochAuthorityV1::new(AUTHORITY_KEY).unwrap();
        let keys = EpochKeys::new(1);
        let record = genesis(&authority, &keys, 0x71);
        let registry = super::super::durable_replay_registry::provision_and_open_for_test(
            &directory.database("replay.db"),
            record.registry_generation_id,
        )
        .unwrap();
        let (payload, exact) = packet("s8-tamper", '9', &keys);
        let mut forged_outer = packet_authentication_for_test(&record, &keys.outer, &exact);
        forged_outer.hmac_sha256[0] ^= 1;
        let error = verify_synthetic_restore_epoch_candidate_v1(
            synthetic_epoch_permit_for_test(record.clone(), AUTHORITY_KEY, keys.handle, keys.outer)
                .unwrap(),
            inner_permit(&payload, &keys),
            forged_outer,
            inner_authentication(&exact, &keys),
            exact.clone(),
            &registry,
            &authority,
            [0x70; 32],
            150,
        )
        .expect_err("correct-identity outer authentication with a changed tag must reject");
        assert_eq!(
            error.code(),
            "track_b_restore_epoch_v1_packet_authentication"
        );

        let mut outer = packet_authentication_for_test(&record, &keys.outer, &exact);
        outer.epoch = 2;
        let error = verify_synthetic_restore_epoch_candidate_v1(
            synthetic_epoch_permit_for_test(record.clone(), AUTHORITY_KEY, keys.handle, keys.outer)
                .unwrap(),
            inner_permit(&payload, &keys),
            outer,
            inner_authentication(&exact, &keys),
            exact.clone(),
            &registry,
            &authority,
            [0x71; 32],
            150,
        )
        .expect_err("epoch substitution must reject");
        assert_eq!(error.code(), "track_b_restore_epoch_v1_packet_profile");

        let mut tampered = exact.to_vec();
        let last = tampered.last_mut().expect("nonempty packet");
        *last ^= 1;
        let error = verify_synthetic_restore_epoch_candidate_v1(
            synthetic_epoch_permit_for_test(record.clone(), AUTHORITY_KEY, keys.handle, keys.outer)
                .unwrap(),
            inner_permit(&payload, &keys),
            packet_authentication_for_test(&record, &keys.outer, &exact),
            inner_authentication(&exact, &keys),
            tampered.into_boxed_slice(),
            &registry,
            &authority,
            [0x72; 32],
            150,
        )
        .expect_err("exact byte substitution must reject before replay consumption");
        assert_eq!(error.code(), "track_b_restore_epoch_v1_packet_profile");

        let error = verify_synthetic_restore_epoch_candidate_v1(
            synthetic_epoch_permit_for_test(record.clone(), AUTHORITY_KEY, keys.handle, keys.outer)
                .unwrap(),
            inner_permit(&payload, &keys),
            packet_authentication_for_test(&record, &keys.outer, &exact),
            inner_authentication(&exact, &keys),
            vec![b'x'; MAX_ENVELOPE_BYTES].into_boxed_slice(),
            &registry,
            &authority,
            [0x73; 32],
            150,
        )
        .expect_err("S8 must enforce the S6 byte sentinel before outer hashing");
        assert_eq!(
            error.code(),
            "track_b_restore_epoch_v1_capacity_or_challenge"
        );

        let _verified = admit(&record, &keys, &payload, exact, &registry, &authority, 0x74)
            .expect("failed pre-consume tampering must not burn the nonce");
    }

    #[test]
    fn s8_old_inner_packet_cannot_be_relabelled_into_new_epoch() {
        let directory = TestDirectory::new("old-inner");
        let authority = SyntheticOnlineRestoreEpochAuthorityV1::new(AUTHORITY_KEY).unwrap();
        let keys1 = EpochKeys::new(1);
        let record1 = genesis(&authority, &keys1, 0x71);
        let keys2 = EpochKeys::new(2);
        let pending = authority
            .begin_controlled_restore(
                record1.record_sha256,
                activation(2, 0x72, 0x92, record1.record_sha256, &keys2),
            )
            .unwrap();
        let record2 = authority.activate_pending(pending.record_sha256).unwrap();
        let registry = super::super::durable_replay_registry::provision_and_open_for_test(
            &directory.database("replay.db"),
            record2.registry_generation_id,
        )
        .unwrap();
        let (old_payload, old_exact) = packet("s8-old-inner", 'a', &keys1);
        let error = verify_synthetic_restore_epoch_candidate_v1(
            synthetic_epoch_permit_for_test(
                record2.clone(),
                AUTHORITY_KEY,
                keys2.handle,
                keys2.outer,
            )
            .unwrap(),
            inner_permit(&old_payload, &keys1),
            packet_authentication_for_test(&record2, &keys2.outer, &old_exact),
            inner_authentication(&old_exact, &keys1),
            old_exact,
            &registry,
            &authority,
            [0x81; 32],
            150,
        )
        .expect_err("old inner key id cannot be relabelled by a new outer epoch");
        assert_eq!(error.code(), "track_b_restore_epoch_v1_key_binding");
    }

    #[test]
    fn s8_revocation_persists_as_no_active_epoch() {
        let directory = TestDirectory::new("revoked");
        let authority = SyntheticOnlineRestoreEpochAuthorityV1::new(AUTHORITY_KEY).unwrap();
        let keys = EpochKeys::new(1);
        let record = genesis(&authority, &keys, 0x71);
        let registry = super::super::durable_replay_registry::provision_and_open_for_test(
            &directory.database("replay.db"),
            record.registry_generation_id,
        )
        .unwrap();
        authority.revoke_current(record.record_sha256).unwrap();
        let (payload, exact) = packet("s8-revoked", 'b', &keys);
        let error = admit(&record, &keys, &payload, exact, &registry, &authority, 0x91)
            .expect_err("revoked epoch cannot emit a currentness proof");
        assert_eq!(error.code(), "track_b_restore_epoch_v1_not_active");
        assert!(authority.request_currentness([0x92; 32]).is_err());
    }

    #[test]
    fn s8_revocation_after_currentness_is_explicitly_lease_bounded_negative_evidence() {
        struct RevokeAfterResponseProvider<'a> {
            authority: &'a SyntheticOnlineRestoreEpochAuthorityV1,
            record_sha256: [u8; 32],
        }
        impl authority_seal::Sealed for RevokeAfterResponseProvider<'_> {}
        impl OnlineRestoreEpochAuthorityV1 for RevokeAfterResponseProvider<'_> {
            fn request_currentness(
                &self,
                challenge: [u8; 32],
            ) -> VerifierResult<AuthenticatedCurrentnessV1> {
                let response = self.authority.request_currentness(challenge)?;
                self.authority.revoke_current(self.record_sha256)?;
                Ok(response)
            }
        }

        let directory = TestDirectory::new("revocation-race-negative-evidence");
        let authority = SyntheticOnlineRestoreEpochAuthorityV1::new(AUTHORITY_KEY).unwrap();
        let keys = EpochKeys::new(1);
        let record = genesis(&authority, &keys, 0x71);
        let registry = super::super::durable_replay_registry::provision_and_open_for_test(
            &directory.database("replay.db"),
            record.registry_generation_id,
        )
        .unwrap();
        let provider = RevokeAfterResponseProvider {
            authority: &authority,
            record_sha256: record.record_sha256,
        };
        let (payload, exact) = packet("s8-revocation-race-gap", 'd', &keys);
        let _negative_evidence = admit(&record, &keys, &payload, exact, &registry, &provider, 0x93)
            .expect("UNRESOLVED: revocation after currentness can race local consume");
        assert!(
            authority.request_currentness([0x94; 32]).is_err(),
            "the epoch is revoked even though one lease-bounded admission completed"
        );
    }

    #[test]
    fn s8_concurrent_restore_transition_has_one_fencing_winner() {
        let authority =
            Arc::new(SyntheticOnlineRestoreEpochAuthorityV1::new(AUTHORITY_KEY).unwrap());
        let keys1 = EpochKeys::new(1);
        let record1 = genesis(&authority, &keys1, 0x71);
        let keys2 = EpochKeys::new(2);
        let next = activation(2, 0x72, 0x92, record1.record_sha256, &keys2);
        let barrier = Arc::new(std::sync::Barrier::new(3));
        let mut workers = Vec::new();
        for _ in 0..2 {
            let authority = Arc::clone(&authority);
            let barrier = Arc::clone(&barrier);
            let next = next.clone();
            workers.push(std::thread::spawn(move || {
                barrier.wait();
                authority.begin_controlled_restore(record1.record_sha256, next)
            }));
        }
        barrier.wait();
        let successes = workers
            .into_iter()
            .map(|worker| worker.join().expect("restore worker").is_ok())
            .filter(|succeeded| *succeeded)
            .count();
        assert_eq!(successes, 1, "only one transition may fence the epoch");
        assert!(
            authority.request_currentness([0xa1; 32]).is_err(),
            "winner leaves authority pending with no active fallback"
        );
    }

    #[test]
    fn s8_pending_result_loss_is_recoverable_only_by_exact_external_query() {
        let authority = SyntheticOnlineRestoreEpochAuthorityV1::new(AUTHORITY_KEY).unwrap();
        let keys1 = EpochKeys::new(1);
        let record1 = genesis(&authority, &keys1, 0x71);
        let keys2 = EpochKeys::new(2);
        let precomputed =
            build_record(activation(2, 0x72, 0x92, record1.record_sha256, &keys2)).unwrap();
        let committed_pending = authority
            .begin_controlled_restore(
                record1.record_sha256,
                activation(2, 0x72, 0x92, record1.record_sha256, &keys2),
            )
            .expect("simulate result loss after this transition");
        assert_eq!(committed_pending, precomputed);
        assert!(
            authority.request_currentness([0xb1; 32]).is_err(),
            "ambiguous pending transition must not revive the predecessor"
        );
        let active = authority
            .activate_pending(precomputed.record_sha256)
            .expect("exact precomputed identity resolves the pending transition");
        let response = authority.request_currentness([0xb2; 32]).unwrap();
        assert_eq!(response.record, active);
    }
}
