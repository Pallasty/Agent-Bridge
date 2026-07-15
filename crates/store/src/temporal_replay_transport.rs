//! Synthetic-only detached verification and replay-contract preregistration.
//!
//! This module deliberately has no public re-export and no runtime caller. It
//! accepts bytes already owned by its caller; it does not read, write, send, or
//! receive them. Its only replay registry implementation is process-local and
//! test-only. Consequently, this executable contract authorizes no transport
//! and satisfies no durable-replay or live-binding requirement.

#![cfg_attr(not(test), allow(dead_code))]

use ring::hmac;
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use std::collections::BTreeSet;
use std::fmt;

#[cfg(feature = "temporal-evidence-s7-durable-replay-synthetic")]
mod durable_replay_registry;

const S5_SOURCE_MANIFEST_SHA256: &str =
    "309f2533ef7b78d0c1f252325c0f79ab1300f8f68837a5a75ce7c14d8b011d6a";
const S5_SOURCE_COMMIT: &str = "8739b69fb59fd704dacfe1a44bfc411ed9ebb913";
const S5_SOURCE_TREE: &str = "d4ba782665fac2c55af60e1c0a988a327b3535dd";
const S5_SOURCE_PARENT: &str = "486f04fb9a967a9a6cf5272f82f36cc0d7e787ad";
const S5_SOURCE_ARTIFACT_COUNT: usize = 14;

#[cfg(test)]
const S5_SOURCE_MANIFEST_BYTES: &[u8] = include_bytes!(
    "../../../scripts/eval/fixtures/memory_temporal_replay_transport_s6_s5_source_manifest_v0.json"
);

const AUTHENTICATION_ALGORITHM: &str = "HMAC-SHA-256";
const AUTHENTICATION_CANONICALIZATION: &str = "serde_json_compact_struct_field_order_utf8_v1";
const AUTHENTICATION_DOMAIN: &str = "agent-bridge/track-b/candidate-evidence-envelope/v0";
const AUTHENTICATION_MESSAGE_PROFILE: &str =
    "u64be_len_domain_domain_u64be_len_key_id_key_id_exact_payload_json";
const CANDIDATE_ID: &str = "temporal_truth_projection_v1_synthetic_source_binding";
const MAX_ENVELOPE_BYTES: usize = 4 * 1024 * 1024;
const MAX_MANIFEST_BYTES: usize = 1024 * 1024;
const MAX_CLAIMS: usize = 1_023;
const MAX_ITEMS_PER_CLAIM: usize = 1_023;
const MAX_TTL_SECONDS: i64 = 3_599;
const CANDIDATE_EXACT_PAYLOAD_PROFILE_SHA256: &str =
    "fe3b66ad1d5711f38e790cf792a0db63bd7879ce9795c07f745ab9127575be23";
const REPLAY_KEY_DOMAIN: &[u8] = b"agent-bridge/track-b/replay-transport/replay-identity/v0";
const REPLAY_SCOPE_DOMAIN: &[u8] = b"agent-bridge/track-b/replay-transport/scope-commitment/v0";

#[derive(Debug, thiserror::Error)]
#[error("{code}: {detail}")]
pub(crate) struct TrackBDetachedVerifierV1Error {
    code: &'static str,
    detail: &'static str,
}

impl TrackBDetachedVerifierV1Error {
    #[cfg(test)]
    fn code(&self) -> &str {
        self.code
    }
}

type VerifierResult<T> = std::result::Result<T, TrackBDetachedVerifierV1Error>;

fn verifier_error(code: &'static str, detail: &'static str) -> TrackBDetachedVerifierV1Error {
    TrackBDetachedVerifierV1Error { code, detail }
}

fn sha256_bytes(bytes: &[u8]) -> [u8; 32] {
    Sha256::digest(bytes).into()
}

fn bytes_to_hex(bytes: &[u8]) -> String {
    let mut output = String::with_capacity(bytes.len() * 2);
    for byte in bytes {
        use std::fmt::Write as _;
        write!(&mut output, "{byte:02x}").expect("write to String cannot fail");
    }
    output
}

fn decode_lower_hex_32(value: &str) -> VerifierResult<[u8; 32]> {
    if value.len() != 64
        || !value
            .bytes()
            .all(|byte| byte.is_ascii_digit() || (b'a'..=b'f').contains(&byte))
    {
        return Err(verifier_error(
            "track_b_detached_v1_invalid_digest",
            "digest must be 64 lowercase hexadecimal characters",
        ));
    }
    let mut output = [0u8; 32];
    for (index, pair) in value.as_bytes().chunks_exact(2).enumerate() {
        let nibble = |byte: u8| match byte {
            b'0'..=b'9' => byte - b'0',
            b'a'..=b'f' => byte - b'a' + 10,
            _ => unreachable!("lowercase hexadecimal was checked"),
        };
        output[index] = (nibble(pair[0]) << 4) | nibble(pair[1]);
    }
    Ok(output)
}

fn detached_hmac_message(key_id: &str, exact_payload: &[u8]) -> Vec<u8> {
    let mut message =
        Vec::with_capacity(16 + AUTHENTICATION_DOMAIN.len() + key_id.len() + exact_payload.len());
    message.extend_from_slice(&(AUTHENTICATION_DOMAIN.len() as u64).to_be_bytes());
    message.extend_from_slice(AUTHENTICATION_DOMAIN.as_bytes());
    message.extend_from_slice(&(key_id.len() as u64).to_be_bytes());
    message.extend_from_slice(key_id.as_bytes());
    message.extend_from_slice(exact_payload);
    message
}

fn detached_hmac_tag(key_bytes: &[u8], key_id: &str, exact_payload: &[u8]) -> [u8; 32] {
    let key = hmac::Key::new(hmac::HMAC_SHA256, key_bytes);
    let message = detached_hmac_message(key_id, exact_payload);
    let tag = hmac::sign(&key, &message);
    let mut output = [0u8; 32];
    output.copy_from_slice(tag.as_ref());
    output
}

fn framed_sha256(domain: &[u8], parts: &[&[u8]]) -> [u8; 32] {
    let mut hasher = Sha256::new();
    hasher.update((domain.len() as u64).to_be_bytes());
    hasher.update(domain);
    for part in parts {
        hasher.update((part.len() as u64).to_be_bytes());
        hasher.update(part);
    }
    hasher.finalize().into()
}

/// Proof that caller-supplied bytes match the frozen historical S5 source
/// manifest. This is source identity, not runtime or producer attestation.
#[must_use]
pub(crate) struct VerifiedS5SourceManifestTokenV1 {
    manifest_sha256: String,
}

impl fmt::Debug for VerifiedS5SourceManifestTokenV1 {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        formatter
            .debug_struct("VerifiedS5SourceManifestTokenV1")
            .field("source_commit", &S5_SOURCE_COMMIT)
            .field("source_tree", &S5_SOURCE_TREE)
            .field("source_parent", &S5_SOURCE_PARENT)
            .field("artifact_count", &S5_SOURCE_ARTIFACT_COUNT)
            .field("manifest_sha256", &self.manifest_sha256)
            .finish()
    }
}

pub(crate) fn verify_s5_source_manifest_v1(
    exact_manifest_bytes: Box<[u8]>,
) -> VerifierResult<VerifiedS5SourceManifestTokenV1> {
    if exact_manifest_bytes.is_empty() || exact_manifest_bytes.len() >= MAX_MANIFEST_BYTES {
        return Err(verifier_error(
            "track_b_detached_v1_source_manifest_capacity",
            "source manifest is empty or reached its byte sentinel",
        ));
    }
    let manifest_sha256 = bytes_to_hex(&sha256_bytes(&exact_manifest_bytes));
    if manifest_sha256 != S5_SOURCE_MANIFEST_SHA256 {
        return Err(verifier_error(
            "track_b_detached_v1_source_manifest_mismatch",
            "source manifest bytes do not match the frozen S5 manifest",
        ));
    }
    Ok(VerifiedS5SourceManifestTokenV1 { manifest_sha256 })
}

#[cfg(test)]
fn synthetic_source_manifest_token_v1() -> VerifiedS5SourceManifestTokenV1 {
    VerifiedS5SourceManifestTokenV1 {
        manifest_sha256: S5_SOURCE_MANIFEST_SHA256.to_string(),
    }
}

/// Detached authentication metadata. It is input, not authority; authority is
/// held only by the unforgeable verification permit below.
pub(crate) struct DetachedCandidateAuthenticationV1 {
    algorithm: String,
    canonicalization: String,
    domain: String,
    hmac_sha256: [u8; 32],
    key_id: String,
    message_profile: String,
    payload_sha256: [u8; 32],
}

impl DetachedCandidateAuthenticationV1 {
    #[allow(clippy::too_many_arguments)]
    pub(crate) fn try_new(
        algorithm: impl Into<String>,
        canonicalization: impl Into<String>,
        domain: impl Into<String>,
        hmac_sha256: &str,
        key_id: impl Into<String>,
        message_profile: impl Into<String>,
        payload_sha256: &str,
    ) -> VerifierResult<Self> {
        Ok(Self {
            algorithm: algorithm.into(),
            canonicalization: canonicalization.into(),
            domain: domain.into(),
            hmac_sha256: decode_lower_hex_32(hmac_sha256)?,
            key_id: key_id.into(),
            message_profile: message_profile.into(),
            payload_sha256: decode_lower_hex_32(payload_sha256)?,
        })
    }
}

impl fmt::Debug for DetachedCandidateAuthenticationV1 {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        formatter
            .debug_struct("DetachedCandidateAuthenticationV1")
            .field("key_id", &self.key_id)
            .field("cryptographic_material", &"[REDACTED]")
            .finish_non_exhaustive()
    }
}

struct ExpectedCandidateIdentityV1 {
    case_id: String,
    contract_sha256: String,
    expires_at_utc: i64,
    handle_key_id: String,
    issued_at_utc: i64,
    projection_binding_handle: String,
    request_id: String,
    request_nonce: String,
    trial_id: String,
}

/// Synthetic-only verification capability. Safe non-test code has no
/// constructor, and the key is best-effort cleared on drop.
pub(crate) struct SyntheticDetachedVerificationPermitV1 {
    expected: ExpectedCandidateIdentityV1,
    source_manifest: VerifiedS5SourceManifestTokenV1,
    transport_key: [u8; 32],
    transport_key_id: String,
}

impl fmt::Debug for SyntheticDetachedVerificationPermitV1 {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        formatter
            .debug_struct("SyntheticDetachedVerificationPermitV1")
            .field("key_material", &"[REDACTED]")
            .field("identity", &"[REDACTED]")
            .finish_non_exhaustive()
    }
}

impl Drop for SyntheticDetachedVerificationPermitV1 {
    fn drop(&mut self) {
        self.transport_key.fill(0);
    }
}

#[cfg(test)]
fn synthetic_detached_verification_permit_v1(
    source_manifest: VerifiedS5SourceManifestTokenV1,
    transport_key: [u8; 32],
    transport_key_id: impl Into<String>,
    expected: ExpectedCandidateIdentityV1,
) -> VerifierResult<SyntheticDetachedVerificationPermitV1> {
    let transport_key_id = transport_key_id.into();
    if transport_key.iter().all(|byte| *byte == 0) {
        return Err(verifier_error(
            "track_b_detached_v1_invalid_key",
            "transport key must not be all zero",
        ));
    }
    validate_label(&transport_key_id)?;
    validate_identity(&expected)?;
    if transport_key_id == expected.handle_key_id {
        return Err(verifier_error(
            "track_b_detached_v1_key_id_collision",
            "transport and handle key ids must remain distinct",
        ));
    }
    Ok(SyntheticDetachedVerificationPermitV1 {
        expected,
        source_manifest,
        transport_key,
        transport_key_id,
    })
}

#[derive(Debug, Deserialize, Serialize)]
#[serde(deny_unknown_fields)]
struct CandidateReferentWire {
    claim_handle: String,
    predicate_handle: String,
    referent_handle: String,
}

#[derive(Debug, Deserialize, Serialize)]
#[serde(deny_unknown_fields)]
struct CandidateClaimWire {
    claim_binding_hmac_sha256: String,
    evidence_count: usize,
    evidence_handles: Vec<String>,
    noncurrent_evidence_count: usize,
    referent: CandidateReferentWire,
    shadowed_evidence_count: usize,
    source_binding_handles: Vec<String>,
    supporting_evidence_handles: Vec<String>,
    temporal_state: String,
    truth_state: String,
    truth_tier: String,
    value_handles: Vec<String>,
}

#[derive(Debug, Deserialize, Serialize, PartialEq, Eq)]
#[serde(deny_unknown_fields)]
struct CandidateBoundaryWire {
    authority_custody_resolved: bool,
    biocortex_runtime_influence: bool,
    capture_provenance_attested: bool,
    contains_raw_evidence_ids: bool,
    contains_raw_predicate_ids: bool,
    contains_raw_provenance: bool,
    contains_raw_referent_ids: bool,
    contains_raw_source_bindings: bool,
    contains_raw_values: bool,
    cross_repository_transport_authorized: bool,
    live_binding_satisfied: bool,
    physical_privacy_deletion_resolved: bool,
    production_profile_active: bool,
    side_effects_unlocked: String,
}

#[derive(Debug, Deserialize, Serialize, PartialEq, Eq)]
#[serde(deny_unknown_fields)]
struct CandidateLimitsWire {
    max_claims: usize,
    max_envelope_bytes: usize,
    max_evidence_per_claim: usize,
    max_source_bindings_per_claim: usize,
    max_ttl_seconds: i64,
    max_values_per_claim: usize,
}

#[derive(Debug, Deserialize, Serialize)]
#[serde(deny_unknown_fields)]
struct CandidatePayloadWire {
    boundary: CandidateBoundaryWire,
    candidate_evidence_schema_sha256: String,
    candidate_id: String,
    case_id: String,
    claims: Vec<CandidateClaimWire>,
    contract_sha256: String,
    expires_at_utc: i64,
    foundational_schema_pack_manifest_sha256: String,
    handle_key_id: String,
    handle_profile_id: String,
    issued_at_utc: i64,
    limits: CandidateLimitsWire,
    projection_binding_handle: String,
    request_id: String,
    request_nonce: String,
    schema: String,
    trial_id: String,
    truth_referent_schema_sha256: String,
}

fn false_boundary() -> CandidateBoundaryWire {
    CandidateBoundaryWire {
        authority_custody_resolved: false,
        biocortex_runtime_influence: false,
        capture_provenance_attested: false,
        contains_raw_evidence_ids: false,
        contains_raw_predicate_ids: false,
        contains_raw_provenance: false,
        contains_raw_referent_ids: false,
        contains_raw_source_bindings: false,
        contains_raw_values: false,
        cross_repository_transport_authorized: false,
        live_binding_satisfied: false,
        physical_privacy_deletion_resolved: false,
        production_profile_active: false,
        side_effects_unlocked: "NONE".to_string(),
    }
}

fn exact_limits() -> CandidateLimitsWire {
    CandidateLimitsWire {
        max_claims: MAX_CLAIMS,
        max_envelope_bytes: MAX_ENVELOPE_BYTES - 1,
        max_evidence_per_claim: MAX_ITEMS_PER_CLAIM,
        max_source_bindings_per_claim: MAX_ITEMS_PER_CLAIM,
        max_ttl_seconds: MAX_TTL_SECONDS,
        max_values_per_claim: MAX_ITEMS_PER_CLAIM,
    }
}

fn validate_label(value: &str) -> VerifierResult<()> {
    if value.is_empty()
        || value.len() > 128
        || !value.is_ascii()
        || !value
            .bytes()
            .next()
            .is_some_and(|byte| byte.is_ascii_lowercase() || byte.is_ascii_digit())
        || !value.bytes().all(|byte| {
            byte.is_ascii_lowercase()
                || byte.is_ascii_digit()
                || matches!(byte, b'.' | b'_' | b':' | b'-')
        })
    {
        return Err(verifier_error(
            "track_b_detached_v1_invalid_label",
            "identity label is outside the closed Track B profile",
        ));
    }
    Ok(())
}

fn validate_prefixed_hex(value: &str, prefix: &str) -> VerifierResult<()> {
    if value.len() != prefix.len() + 32
        || !value.starts_with(prefix)
        || !value[prefix.len()..]
            .bytes()
            .all(|byte| byte.is_ascii_digit() || (b'a'..=b'f').contains(&byte))
    {
        return Err(verifier_error(
            "track_b_detached_v1_invalid_handle",
            "opaque handle is outside its closed prefix profile",
        ));
    }
    Ok(())
}

fn validate_identity(identity: &ExpectedCandidateIdentityV1) -> VerifierResult<()> {
    for value in [
        &identity.trial_id,
        &identity.request_id,
        &identity.handle_key_id,
    ] {
        validate_label(value)?;
    }
    if identity.case_id.len() != 37 || !identity.case_id.starts_with("case_") {
        return Err(verifier_error(
            "track_b_detached_v1_invalid_case",
            "case identity is outside the closed Track B profile",
        ));
    }
    validate_prefixed_hex(&identity.case_id, "case_")?;
    decode_lower_hex_32(&identity.contract_sha256)?;
    decode_lower_hex_32(&identity.request_nonce)?;
    validate_prefixed_hex(&identity.projection_binding_handle, "prj_")?;
    let ttl = identity
        .expires_at_utc
        .checked_sub(identity.issued_at_utc)
        .ok_or_else(|| {
            verifier_error(
                "track_b_detached_v1_invalid_time",
                "identity time window overflowed",
            )
        })?;
    if identity.issued_at_utc < 0 || ttl <= 0 || ttl > MAX_TTL_SECONDS {
        return Err(verifier_error(
            "track_b_detached_v1_invalid_time",
            "identity time window is outside the S5 profile",
        ));
    }
    Ok(())
}

fn strictly_sorted_unique(values: &[String]) -> bool {
    values.windows(2).all(|pair| pair[0] < pair[1])
}

fn validate_claim(claim: &CandidateClaimWire) -> VerifierResult<()> {
    decode_lower_hex_32(&claim.claim_binding_hmac_sha256)?;
    validate_prefixed_hex(&claim.referent.claim_handle, "clm_")?;
    validate_prefixed_hex(&claim.referent.predicate_handle, "prd_")?;
    validate_prefixed_hex(&claim.referent.referent_handle, "ref_")?;
    for (values, prefix) in [
        (claim.evidence_handles.as_slice(), "evd_"),
        (claim.supporting_evidence_handles.as_slice(), "evd_"),
        (claim.source_binding_handles.as_slice(), "src_"),
        (claim.value_handles.as_slice(), "val_"),
    ] {
        if values.len() > MAX_ITEMS_PER_CLAIM || !strictly_sorted_unique(values) {
            return Err(verifier_error(
                "track_b_detached_v1_claim_order",
                "claim handle arrays must be bounded, strictly sorted, and unique",
            ));
        }
        for value in values {
            validate_prefixed_hex(value, prefix)?;
        }
    }
    if claim.evidence_count != claim.evidence_handles.len()
        || claim.noncurrent_evidence_count > MAX_ITEMS_PER_CLAIM
        || claim.shadowed_evidence_count > MAX_ITEMS_PER_CLAIM
    {
        return Err(verifier_error(
            "track_b_detached_v1_claim_cardinality",
            "claim counts do not match the closed S5 profile",
        ));
    }
    if !matches!(
        claim.temporal_state.as_str(),
        "current" | "future" | "historical" | "indeterminate"
    ) {
        return Err(verifier_error(
            "track_b_detached_v1_temporal_state",
            "temporal state is outside the closed S5 profile",
        ));
    }
    let tier_is_present = matches!(
        claim.truth_tier.as_str(),
        "authoritative" | "inferred" | "observed" | "verified"
    );
    let state_is_valid = match claim.truth_state.as_str() {
        "supported" => {
            tier_is_present && claim.value_handles.len() == 1 && claim.evidence_count > 0
        }
        "conflicted" => {
            tier_is_present && claim.value_handles.len() >= 2 && claim.evidence_count > 0
        }
        "unknown" => {
            claim.truth_tier == "none"
                && claim.value_handles.is_empty()
                && claim.evidence_handles.is_empty()
                && claim.supporting_evidence_handles.is_empty()
                && claim.source_binding_handles.is_empty()
                && claim.evidence_count == 0
                && claim.noncurrent_evidence_count == 0
                && claim.shadowed_evidence_count == 0
        }
        _ => false,
    };
    if !state_is_valid {
        return Err(verifier_error(
            "track_b_detached_v1_truth_state",
            "truth state, tier, counts, and handles are inconsistent",
        ));
    }
    let top: BTreeSet<&str> = claim.evidence_handles.iter().map(String::as_str).collect();
    if claim
        .supporting_evidence_handles
        .iter()
        .any(|handle| top.contains(handle.as_str()))
    {
        return Err(verifier_error(
            "track_b_detached_v1_evidence_overlap",
            "top and supporting evidence handles must remain disjoint",
        ));
    }
    Ok(())
}

fn validate_payload(
    payload: &CandidatePayloadWire,
    permit: &SyntheticDetachedVerificationPermitV1,
    evaluated_at_utc: i64,
) -> VerifierResult<[u8; 32]> {
    if payload.boundary != false_boundary() {
        return Err(verifier_error(
            "track_b_detached_v1_boundary",
            "candidate boundary must remain hard-false with side effects NONE",
        ));
    }
    if payload.schema != crate::TRACK_B_CANDIDATE_EVIDENCE_V1_SCHEMA
        || payload.candidate_evidence_schema_sha256
            != crate::TRACK_B_CANDIDATE_EVIDENCE_SCHEMA_SHA256
        || payload.candidate_id != CANDIDATE_ID
        || payload.foundational_schema_pack_manifest_sha256
            != crate::TRACK_B_FOUNDATIONAL_PACK_MANIFEST_SHA256
        || payload.handle_profile_id != crate::TRACK_B_CANDIDATE_HANDLE_PROFILE_V1
        || payload.truth_referent_schema_sha256 != crate::TRACK_B_TRUTH_REFERENT_SCHEMA_SHA256
        || payload.limits != exact_limits()
    {
        return Err(verifier_error(
            "track_b_detached_v1_schema_identity",
            "candidate schema, artifact, handle, or limit identity drifted",
        ));
    }
    let expected = &permit.expected;
    if payload.trial_id != expected.trial_id
        || payload.contract_sha256 != expected.contract_sha256
        || payload.case_id != expected.case_id
        || payload.request_id != expected.request_id
        || payload.request_nonce != expected.request_nonce
        || payload.handle_key_id != expected.handle_key_id
        || payload.projection_binding_handle != expected.projection_binding_handle
        || payload.issued_at_utc != expected.issued_at_utc
        || payload.expires_at_utc != expected.expires_at_utc
    {
        return Err(verifier_error(
            "track_b_detached_v1_identity_mix",
            "candidate identity differs from the permit-bound request scope",
        ));
    }
    validate_identity(expected)?;
    if evaluated_at_utc < payload.issued_at_utc || evaluated_at_utc >= payload.expires_at_utc {
        return Err(verifier_error(
            "track_b_detached_v1_expired",
            "candidate payload is outside its exclusive validity window",
        ));
    }
    if payload.claims.is_empty() || payload.claims.len() > MAX_CLAIMS {
        return Err(verifier_error(
            "track_b_detached_v1_claim_capacity",
            "candidate claims are empty or exceed the closed maximum",
        ));
    }
    let mut previous = None;
    let mut claim_handles = BTreeSet::new();
    for claim in &payload.claims {
        validate_claim(claim)?;
        let order = (
            claim.referent.referent_handle.as_str(),
            claim.referent.predicate_handle.as_str(),
            claim.referent.claim_handle.as_str(),
        );
        if previous.is_some_and(|prior| prior >= order)
            || !claim_handles.insert(claim.referent.claim_handle.as_str())
        {
            return Err(verifier_error(
                "track_b_detached_v1_claim_order",
                "candidate claims must be strictly ordered with unique claim handles",
            ));
        }
        previous = Some(order);
    }
    decode_lower_hex_32(&payload.request_nonce)
}

pub(crate) struct ReplayConsumeRequestV1 {
    consumed_at_utc: i64,
    expires_at_utc: i64,
    payload_sha256: [u8; 32],
    replay_key_sha256: [u8; 32],
    scope_sha256: [u8; 32],
}

pub(crate) struct ReplayConsumeReceiptV1 {
    durable: bool,
    replay_key_sha256: [u8; 32],
    scope_sha256: [u8; 32],
}

mod replay_registry_seal {
    pub(crate) trait Sealed {}
}

/// Future durable implementations must make this one method a linearizable,
/// crash-consistent conditional insert. There is intentionally no separate
/// contains/insert API and no durable implementation in S6.
pub(crate) trait CandidateReplayRegistryV1: replay_registry_seal::Sealed {
    fn consume_once(
        &self,
        request: ReplayConsumeRequestV1,
    ) -> VerifierResult<ReplayConsumeReceiptV1>;
}

/// Verified detached input. Exact bytes remain owned and inaccessible so a
/// later consumer cannot substitute bytes after verification.
#[must_use]
pub(crate) struct VerifiedDetachedCandidateV1 {
    exact_payload: Box<[u8]>,
    payload_sha256: [u8; 32],
    replay_receipt: ReplayConsumeReceiptV1,
    source_manifest_sha256: String,
}

impl fmt::Debug for VerifiedDetachedCandidateV1 {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        formatter
            .debug_struct("VerifiedDetachedCandidateV1")
            .field("payload_bytes", &self.exact_payload.len())
            .field("payload_sha256", &bytes_to_hex(&self.payload_sha256))
            .field("durable_replay", &self.replay_receipt.durable)
            .finish_non_exhaustive()
    }
}

#[allow(clippy::too_many_lines)]
pub(crate) fn verify_synthetic_detached_candidate_v1<R: CandidateReplayRegistryV1>(
    permit: SyntheticDetachedVerificationPermitV1,
    authentication: DetachedCandidateAuthenticationV1,
    exact_payload: Box<[u8]>,
    registry: &R,
    evaluated_at_utc: i64,
) -> VerifierResult<VerifiedDetachedCandidateV1> {
    // The cap is checked before hashing or parsing untrusted input.
    if exact_payload.is_empty() || exact_payload.len() >= MAX_ENVELOPE_BYTES {
        return Err(verifier_error(
            "track_b_detached_v1_payload_capacity",
            "exact payload is empty or reached its byte sentinel",
        ));
    }
    if authentication.algorithm != AUTHENTICATION_ALGORITHM
        || authentication.canonicalization != AUTHENTICATION_CANONICALIZATION
        || authentication.domain != AUTHENTICATION_DOMAIN
        || authentication.message_profile != AUTHENTICATION_MESSAGE_PROFILE
        || authentication.key_id != permit.transport_key_id
    {
        return Err(verifier_error(
            "track_b_detached_v1_authentication_profile",
            "detached authentication profile or key id drifted",
        ));
    }

    // Cryptographic identity is over the caller-owned exact bytes, before any
    // parsing or canonical reconstruction.
    let payload_sha256 = sha256_bytes(&exact_payload);
    if payload_sha256 != authentication.payload_sha256 {
        return Err(verifier_error(
            "track_b_detached_v1_payload_digest",
            "exact payload SHA-256 did not match detached authentication",
        ));
    }
    let verification_key = hmac::Key::new(hmac::HMAC_SHA256, &permit.transport_key);
    let authentication_message = detached_hmac_message(&permit.transport_key_id, &exact_payload);
    hmac::verify(
        &verification_key,
        &authentication_message,
        &authentication.hmac_sha256,
    )
    .map_err(|_| {
        verifier_error(
            "track_b_detached_v1_hmac",
            "exact payload HMAC did not match the permit-bound transport key",
        )
    })?;

    let payload: CandidatePayloadWire = serde_json::from_slice(&exact_payload).map_err(|_| {
        verifier_error(
            "track_b_detached_v1_payload_parse",
            "exact payload is not one closed candidate payload object",
        )
    })?;
    let canonical = serde_json::to_vec(&payload).map_err(|_| {
        verifier_error(
            "track_b_detached_v1_payload_canonical",
            "candidate payload canonical reconstruction failed",
        )
    })?;
    if canonical.as_slice() != exact_payload.as_ref() {
        return Err(verifier_error(
            "track_b_detached_v1_payload_canonical",
            "received bytes differ from the exact compact canonical profile",
        ));
    }
    validate_payload(&payload, &permit, evaluated_at_utc)?;

    if permit.source_manifest.manifest_sha256 != S5_SOURCE_MANIFEST_SHA256 {
        return Err(verifier_error(
            "track_b_detached_v1_source_manifest_mismatch",
            "permit source token does not match the frozen S5 manifest",
        ));
    }
    let replay_key_sha256 = framed_sha256(
        REPLAY_KEY_DOMAIN,
        &[
            permit.transport_key_id.as_bytes(),
            payload.request_nonce.as_bytes(),
        ],
    );
    let issued_at = payload.issued_at_utc.to_string();
    let expires_at = payload.expires_at_utc.to_string();
    let payload_sha256_hex = bytes_to_hex(&payload_sha256);
    let scope_sha256 = framed_sha256(
        REPLAY_SCOPE_DOMAIN,
        &[
            permit.source_manifest.manifest_sha256.as_bytes(),
            CANDIDATE_EXACT_PAYLOAD_PROFILE_SHA256.as_bytes(),
            payload.handle_key_id.as_bytes(),
            payload.trial_id.as_bytes(),
            payload.contract_sha256.as_bytes(),
            payload.case_id.as_bytes(),
            payload.request_id.as_bytes(),
            payload.projection_binding_handle.as_bytes(),
            issued_at.as_bytes(),
            expires_at.as_bytes(),
            payload_sha256_hex.as_bytes(),
        ],
    );
    let source_manifest_sha256 = permit.source_manifest.manifest_sha256.clone();

    // All validation and allocations are complete before the sole atomic
    // replay operation. The only post-consume check compares fixed-size receipt
    // commitments. A mismatch fails closed without releasing the private token;
    // the nonce may remain burned, which is safer than accepting an ambiguous
    // registry result.
    let replay_receipt = registry.consume_once(ReplayConsumeRequestV1 {
        consumed_at_utc: evaluated_at_utc,
        expires_at_utc: payload.expires_at_utc,
        payload_sha256,
        replay_key_sha256,
        scope_sha256,
    })?;
    if replay_receipt.replay_key_sha256 != replay_key_sha256
        || replay_receipt.scope_sha256 != scope_sha256
    {
        return Err(verifier_error(
            "track_b_detached_v1_registry_indeterminate",
            "replay registry receipt did not match the consumed request commitments",
        ));
    }
    Ok(VerifiedDetachedCandidateV1 {
        exact_payload,
        payload_sha256,
        replay_receipt,
        source_manifest_sha256,
    })
}

#[cfg(feature = "temporal-evidence-s7-durable-replay-synthetic")]
fn verify_synthetic_detached_candidate_durable_v1(
    permit: SyntheticDetachedVerificationPermitV1,
    authentication: DetachedCandidateAuthenticationV1,
    exact_payload: Box<[u8]>,
    registry: &durable_replay_registry::SyntheticDurableReplayRegistryV1,
    evaluated_at_utc: i64,
) -> VerifierResult<VerifiedDetachedCandidateV1> {
    let verified = verify_synthetic_detached_candidate_v1(
        permit,
        authentication,
        exact_payload,
        registry,
        evaluated_at_utc,
    )?;
    if !verified.replay_receipt.durable {
        return Err(verifier_error(
            "track_b_detached_v1_registry_indeterminate",
            "S7 durable verification received a non-durable replay receipt",
        ));
    }
    Ok(verified)
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::collections::BTreeMap;
    use std::sync::Mutex;

    const KEY: [u8; 32] = [0x31; 32];
    const KEY_ID: &str = "transport-key-s6";

    #[derive(Clone)]
    struct StoredReplay {
        payload_sha256: [u8; 32],
        scope_sha256: [u8; 32],
    }

    struct SyntheticProcessLocalReplayRegistryV1 {
        entries: Mutex<BTreeMap<[u8; 32], StoredReplay>>,
    }

    impl SyntheticProcessLocalReplayRegistryV1 {
        fn new() -> Self {
            Self {
                entries: Mutex::new(BTreeMap::new()),
            }
        }

        fn len(&self) -> usize {
            self.entries.lock().expect("synthetic registry lock").len()
        }
    }

    impl replay_registry_seal::Sealed for SyntheticProcessLocalReplayRegistryV1 {}

    impl CandidateReplayRegistryV1 for SyntheticProcessLocalReplayRegistryV1 {
        fn consume_once(
            &self,
            request: ReplayConsumeRequestV1,
        ) -> VerifierResult<ReplayConsumeReceiptV1> {
            if request.consumed_at_utc < 0 || request.consumed_at_utc >= request.expires_at_utc {
                return Err(verifier_error(
                    "track_b_detached_v1_registry_time",
                    "registry request is outside its retention window",
                ));
            }
            let mut entries = self.entries.lock().map_err(|_| {
                verifier_error(
                    "track_b_detached_v1_registry_indeterminate",
                    "replay registry outcome is indeterminate",
                )
            })?;
            if let Some(previous) = entries.get(&request.replay_key_sha256) {
                if previous.scope_sha256 == request.scope_sha256
                    && previous.payload_sha256 == request.payload_sha256
                {
                    return Err(verifier_error(
                        "track_b_detached_v1_replay",
                        "candidate request nonce was already consumed",
                    ));
                }
                return Err(verifier_error(
                    "track_b_detached_v1_scope_collision",
                    "transport key and nonce were reused for a different scope",
                ));
            }
            entries.insert(
                request.replay_key_sha256,
                StoredReplay {
                    payload_sha256: request.payload_sha256,
                    scope_sha256: request.scope_sha256,
                },
            );
            Ok(ReplayConsumeReceiptV1 {
                durable: false,
                replay_key_sha256: request.replay_key_sha256,
                scope_sha256: request.scope_sha256,
            })
        }
    }

    pub(super) fn sample_payload(trial_id: &str) -> CandidatePayloadWire {
        CandidatePayloadWire {
            boundary: false_boundary(),
            candidate_evidence_schema_sha256: crate::TRACK_B_CANDIDATE_EVIDENCE_SCHEMA_SHA256
                .to_string(),
            candidate_id: CANDIDATE_ID.to_string(),
            case_id: format!("case_{}", "a".repeat(32)),
            claims: vec![CandidateClaimWire {
                claim_binding_hmac_sha256: "7".repeat(64),
                evidence_count: 1,
                evidence_handles: vec![format!("evd_{}", "4".repeat(32))],
                noncurrent_evidence_count: 0,
                referent: CandidateReferentWire {
                    claim_handle: format!("clm_{}", "1".repeat(32)),
                    predicate_handle: format!("prd_{}", "2".repeat(32)),
                    referent_handle: format!("ref_{}", "3".repeat(32)),
                },
                shadowed_evidence_count: 0,
                source_binding_handles: vec![format!("src_{}", "5".repeat(32))],
                supporting_evidence_handles: vec![format!("evd_{}", "6".repeat(32))],
                temporal_state: "current".to_string(),
                truth_state: "supported".to_string(),
                truth_tier: "verified".to_string(),
                value_handles: vec![format!("val_{}", "8".repeat(32))],
            }],
            contract_sha256: "b".repeat(64),
            expires_at_utc: 200,
            foundational_schema_pack_manifest_sha256:
                crate::TRACK_B_FOUNDATIONAL_PACK_MANIFEST_SHA256.to_string(),
            handle_key_id: "handle-key-s6".to_string(),
            handle_profile_id: crate::TRACK_B_CANDIDATE_HANDLE_PROFILE_V1.to_string(),
            issued_at_utc: 100,
            limits: exact_limits(),
            projection_binding_handle: format!("prj_{}", "d".repeat(32)),
            request_id: "request-s6".to_string(),
            request_nonce: "c".repeat(64),
            schema: crate::TRACK_B_CANDIDATE_EVIDENCE_V1_SCHEMA.to_string(),
            trial_id: trial_id.to_string(),
            truth_referent_schema_sha256: crate::TRACK_B_TRUTH_REFERENT_SCHEMA_SHA256.to_string(),
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

    pub(super) fn permit(payload: &CandidatePayloadWire) -> SyntheticDetachedVerificationPermitV1 {
        synthetic_detached_verification_permit_v1(
            synthetic_source_manifest_token_v1(),
            KEY,
            KEY_ID,
            expected(payload),
        )
        .expect("synthetic S6 permit")
    }

    fn authentication_with_profile(
        exact_payload: &[u8],
        key: &[u8],
        key_id: &str,
        domain: &str,
    ) -> DetachedCandidateAuthenticationV1 {
        DetachedCandidateAuthenticationV1::try_new(
            AUTHENTICATION_ALGORITHM,
            AUTHENTICATION_CANONICALIZATION,
            domain,
            &bytes_to_hex(&detached_hmac_tag(key, key_id, exact_payload)),
            key_id,
            AUTHENTICATION_MESSAGE_PROFILE,
            &bytes_to_hex(&sha256_bytes(exact_payload)),
        )
        .expect("well-formed detached authentication")
    }

    pub(super) fn authentication(exact_payload: &[u8]) -> DetachedCandidateAuthenticationV1 {
        authentication_with_profile(exact_payload, &KEY, KEY_ID, AUTHENTICATION_DOMAIN)
    }

    pub(super) fn canonical(payload: &CandidatePayloadWire) -> Box<[u8]> {
        serde_json::to_vec(payload)
            .expect("serialize synthetic candidate")
            .into_boxed_slice()
    }

    #[test]
    fn temporal_truth_replay_transport_s6_exact_bytes_verify_without_exposure() {
        assert_eq!(
            bytes_to_hex(&detached_hmac_tag(&[0x0b; 20], "key-1", br#"{"a":1}"#)),
            "fe573e5da170443718fc116432f7b34abae80582d29d84ca6af03fa24068e9e8",
            "S6 detached verifier must retain the independently derived candidate-domain vector"
        );
        let payload = sample_payload("trial-s6-exact");
        let exact = canonical(&payload);
        let digest = sha256_bytes(&exact);
        let verified = verify_synthetic_detached_candidate_v1(
            permit(&payload),
            authentication(&exact),
            exact,
            &SyntheticProcessLocalReplayRegistryV1::new(),
            150,
        )
        .expect("exact detached payload verifies");
        assert_eq!(verified.payload_sha256, digest);
        assert!(!verified.replay_receipt.durable);
        assert_ne!(verified.replay_receipt.replay_key_sha256, [0; 32]);
        assert_ne!(verified.replay_receipt.scope_sha256, [0; 32]);
        assert_eq!(verified.source_manifest_sha256, S5_SOURCE_MANIFEST_SHA256);
        assert_eq!(verified.exact_payload.len(), canonical(&payload).len());
        let debug = format!("{verified:?}");
        assert!(!debug.contains("clm_"));
        assert!(!debug.contains("request-s6"));
    }

    #[test]
    fn temporal_truth_replay_transport_s6_rejects_key_domain_and_byte_tamper() {
        let payload = sample_payload("trial-s6-auth");
        let exact = canonical(&payload);
        let registry = SyntheticProcessLocalReplayRegistryV1::new();

        let wrong_domain = authentication_with_profile(&exact, &KEY, KEY_ID, "wrong-domain");
        let error = verify_synthetic_detached_candidate_v1(
            permit(&payload),
            wrong_domain,
            exact.clone(),
            &registry,
            150,
        )
        .expect_err("domain substitution must reject");
        assert_eq!(error.code(), "track_b_detached_v1_authentication_profile");

        let wrong_key =
            authentication_with_profile(&exact, &[0x32; 32], KEY_ID, AUTHENTICATION_DOMAIN);
        let error = verify_synthetic_detached_candidate_v1(
            permit(&payload),
            wrong_key,
            exact.clone(),
            &registry,
            150,
        )
        .expect_err("key substitution must reject");
        assert_eq!(error.code(), "track_b_detached_v1_hmac");

        let mut tampered = exact.to_vec();
        let offset = tampered
            .iter()
            .position(|byte| *byte == b'b')
            .expect("payload contains a mutable byte");
        tampered[offset] = b'c';
        let error = verify_synthetic_detached_candidate_v1(
            permit(&payload),
            authentication(&exact),
            tampered.into_boxed_slice(),
            &registry,
            150,
        )
        .expect_err("one-byte substitution must reject");
        assert_eq!(error.code(), "track_b_detached_v1_payload_digest");
        assert_eq!(registry.len(), 0);
    }

    #[test]
    fn temporal_truth_replay_transport_s6_rejects_identity_mix() {
        let expected_payload = sample_payload("trial-s6-identity-a");
        let mut replacement = sample_payload("trial-s6-identity-b");
        replacement.request_id = "request-replacement".to_string();
        let exact = canonical(&replacement);
        let error = verify_synthetic_detached_candidate_v1(
            permit(&expected_payload),
            authentication(&exact),
            exact,
            &SyntheticProcessLocalReplayRegistryV1::new(),
            150,
        )
        .expect_err("validly authenticated replacement identity must reject");
        assert_eq!(error.code(), "track_b_detached_v1_identity_mix");
    }

    #[test]
    fn temporal_truth_replay_transport_s6_enforces_exclusive_time_window() {
        let payload = sample_payload("trial-s6-time");
        let exact = canonical(&payload);
        for evaluated_at in [99, 200] {
            let error = verify_synthetic_detached_candidate_v1(
                permit(&payload),
                authentication(&exact),
                exact.clone(),
                &SyntheticProcessLocalReplayRegistryV1::new(),
                evaluated_at,
            )
            .expect_err("outside/equal expiry time must reject");
            assert_eq!(error.code(), "track_b_detached_v1_expired");
        }
        let _ = verify_synthetic_detached_candidate_v1(
            permit(&payload),
            authentication(&exact),
            exact,
            &SyntheticProcessLocalReplayRegistryV1::new(),
            199,
        )
        .expect("last valid second remains accepted");
    }

    #[test]
    fn temporal_truth_replay_transport_s6_atomic_replay_and_scope_collision() {
        let first = sample_payload("trial-s6-replay-a");
        let first_exact = canonical(&first);
        let registry = SyntheticProcessLocalReplayRegistryV1::new();
        let _ = verify_synthetic_detached_candidate_v1(
            permit(&first),
            authentication(&first_exact),
            first_exact.clone(),
            &registry,
            150,
        )
        .expect("first atomic consumption succeeds");
        let replay = verify_synthetic_detached_candidate_v1(
            permit(&first),
            authentication(&first_exact),
            first_exact,
            &registry,
            150,
        )
        .expect_err("same request must not be idempotently accepted");
        assert_eq!(replay.code(), "track_b_detached_v1_replay");

        let replacement = sample_payload("trial-s6-replay-b");
        let replacement_exact = canonical(&replacement);
        let collision = verify_synthetic_detached_candidate_v1(
            permit(&replacement),
            authentication(&replacement_exact),
            replacement_exact,
            &registry,
            150,
        )
        .expect_err("same key and nonce under another trial must collide");
        assert_eq!(collision.code(), "track_b_detached_v1_scope_collision");
        assert_eq!(registry.len(), 1);
    }

    #[test]
    fn temporal_truth_replay_transport_s6_rejects_noncanonical_unknown_boundary_and_cap() {
        let payload = sample_payload("trial-s6-canonical");
        let exact = canonical(&payload);
        let registry = SyntheticProcessLocalReplayRegistryV1::new();

        let mut spaced = Vec::with_capacity(exact.len() + 1);
        spaced.push(b'{');
        spaced.push(b' ');
        spaced.extend_from_slice(&exact[1..]);
        let spaced_auth = authentication(&spaced);
        let error = verify_synthetic_detached_candidate_v1(
            permit(&payload),
            spaced_auth,
            spaced.into_boxed_slice(),
            &registry,
            150,
        )
        .expect_err("authenticated noncanonical bytes must reject");
        assert_eq!(error.code(), "track_b_detached_v1_payload_canonical");

        let mut value: serde_json::Value = serde_json::from_slice(&exact).unwrap();
        value
            .as_object_mut()
            .unwrap()
            .insert("unknown_field".to_string(), serde_json::json!(0));
        let unknown = serde_json::to_vec(&value).unwrap();
        let unknown_auth = authentication(&unknown);
        let error = verify_synthetic_detached_candidate_v1(
            permit(&payload),
            unknown_auth,
            unknown.into_boxed_slice(),
            &registry,
            150,
        )
        .expect_err("closed payload rejects unknown fields");
        assert_eq!(error.code(), "track_b_detached_v1_payload_parse");

        let mut elevated = sample_payload("trial-s6-canonical");
        elevated.boundary.cross_repository_transport_authorized = true;
        let elevated_exact = canonical(&elevated);
        let error = verify_synthetic_detached_candidate_v1(
            permit(&payload),
            authentication(&elevated_exact),
            elevated_exact,
            &registry,
            150,
        )
        .expect_err("transport authorization cannot be raised by input");
        assert_eq!(error.code(), "track_b_detached_v1_boundary");

        let oversized = vec![b' '; MAX_ENVELOPE_BYTES].into_boxed_slice();
        let error = verify_synthetic_detached_candidate_v1(
            permit(&payload),
            authentication(&exact),
            oversized,
            &registry,
            150,
        )
        .expect_err("byte sentinel rejects before hashing or parsing");
        assert_eq!(error.code(), "track_b_detached_v1_payload_capacity");
        assert_eq!(registry.len(), 0);
    }

    #[test]
    fn temporal_truth_replay_transport_s6_source_manifest_token_rejects_arbitrary_bytes() {
        let verified =
            verify_s5_source_manifest_v1(S5_SOURCE_MANIFEST_BYTES.to_vec().into_boxed_slice())
                .expect("the exact frozen historical S5 manifest must mint a local source token");
        assert_eq!(verified.manifest_sha256, S5_SOURCE_MANIFEST_SHA256);

        let error =
            verify_s5_source_manifest_v1(b"not-the-frozen-manifest".to_vec().into_boxed_slice())
                .expect_err("arbitrary manifest bytes cannot mint the source token");
        assert_eq!(error.code(), "track_b_detached_v1_source_manifest_mismatch");
    }

    #[cfg(feature = "temporal-evidence-s7-durable-replay-synthetic")]
    struct SyntheticMismatchedReceiptRegistryV1;

    #[cfg(feature = "temporal-evidence-s7-durable-replay-synthetic")]
    impl replay_registry_seal::Sealed for SyntheticMismatchedReceiptRegistryV1 {}

    #[cfg(feature = "temporal-evidence-s7-durable-replay-synthetic")]
    impl CandidateReplayRegistryV1 for SyntheticMismatchedReceiptRegistryV1 {
        fn consume_once(
            &self,
            request: ReplayConsumeRequestV1,
        ) -> VerifierResult<ReplayConsumeReceiptV1> {
            Ok(ReplayConsumeReceiptV1 {
                durable: true,
                replay_key_sha256: [0xff; 32],
                scope_sha256: request.scope_sha256,
            })
        }
    }

    #[cfg(feature = "temporal-evidence-s7-durable-replay-synthetic")]
    #[test]
    fn temporal_truth_replay_transport_s7_rejects_mismatched_registry_receipt() {
        let payload = sample_payload("trial-s7-mismatched-receipt");
        let exact = canonical(&payload);
        let error = verify_synthetic_detached_candidate_v1(
            permit(&payload),
            authentication(&exact),
            exact,
            &SyntheticMismatchedReceiptRegistryV1,
            150,
        )
        .expect_err("a registry cannot substitute replay receipt identity");
        assert_eq!(error.code(), "track_b_detached_v1_registry_indeterminate");
    }
}
