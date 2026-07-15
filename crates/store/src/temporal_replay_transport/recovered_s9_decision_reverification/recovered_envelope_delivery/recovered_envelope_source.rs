//! S14 private strict recovered-envelope source preregistration.
//!
//! A sealed exact-read contract streams one bounded raw record into this
//! module. The decoder accepts bytes only, verifies a source-signed capture
//! claim, strictly reconstructs the exact S9 and raw signed S10 messages, and
//! immediately consumes the unchanged S13 handoff. No production source,
//! runtime adapter, persistence implementation, currentness, admission, replay
//! fence, or downstream action exists here.

#![cfg_attr(not(test), allow(dead_code))]

use super::super::super::external_operation_recovery::{
    validated_lookup_query_message, validated_observation_message, ExternalOperationRecoveryStateV1,
};
use super::super::super::external_restore_authority::ExternalAuthorityStateV1;
use super::{
    AtomicAuthorityOperationRequestV1, AtomicAuthorityOperationTrustPermitV1,
    ExternalAuthorityTrustPermitV1, ExternalCurrentnessRequestV1, ExternalOperationRecoveryQueryV1,
    ExternalOperationRecoveryTrustPermitV1, PurelyReverifiedRecoveredS9DecisionV1,
    RecoveredEvidenceHandoffV1, RecoveredS9EnvelopeV1, SignedCommittedAuthorityOperationV1,
    SignedExternalCurrentnessDecisionV1, SignedExternalOperationRecoveryObservationV1,
};
use ring::signature::{UnparsedPublicKey, ED25519};
use sha2::{Digest, Sha256};
use std::fmt;

const POLICY_ID: &str = "agent-bridge/track-b/recovered-envelope-source/v1";
const PROFILE: &str =
    "STRICT_BYTE_ONLY_SOURCE_SIGNED_CAPTURE_RAW_S9_RAW_S10_LOCAL_REVERIFY_HISTORICAL_ONLY";
const SOURCE_RECORD_SCHEMA_ID: &str = "agent-bridge/track-b/recovered-envelope-source-record/v1";
const S9_WIRE_SCHEMA_ID: &str = "agent-bridge/track-b/recovered-s9-byte-wire/v1";
const S10_WIRE_SCHEMA_ID: &str = "agent-bridge/track-b/recovered-s10-byte-wire/v1";
const CAPTURE_PROVENANCE_SCHEMA_ID: &str =
    "agent-bridge/track-b/recovered-envelope-capture-provenance/v1";
const SOURCE_RECORD_DOMAIN: &[u8] =
    b"agent-bridge/track-b/recovered-envelope-source/source-record/v1";
const S9_WIRE_DOMAIN: &[u8] = b"agent-bridge/track-b/recovered-envelope-source/s9-wire/v1";
const S10_WIRE_DOMAIN: &[u8] = b"agent-bridge/track-b/recovered-envelope-source/s10-wire/v1";
const CAPTURE_PROVENANCE_DOMAIN: &[u8] =
    b"agent-bridge/track-b/recovered-envelope-source/capture-provenance/v1";
const RAW_OBJECT_DOMAIN: &[u8] = b"agent-bridge/track-b/recovered-envelope-source/raw-object/v1";
const HISTORICAL_SOURCE_CHAIN_DOMAIN: &[u8] =
    b"agent-bridge/track-b/recovered-envelope-source/historical-source-chain/v1";
const MAX_CANONICAL_MESSAGE_BYTES: usize = 64 * 1024;
const MAX_EVIDENCE_COMPONENT_BYTES: usize = 128 * 1024;
const MAX_S9_WIRE_BYTES: usize = 132 * 1024;
const MAX_S10_WIRE_BYTES: usize = 132 * 1024;
const MAX_PROVENANCE_MESSAGE_BYTES: usize = 4 * 1024;
const MAX_SOURCE_RECORD_BYTES: usize = 272 * 1024;
const MAX_LABEL_BYTES: usize = 128;
const ED25519_SIGNATURE_BYTES: usize = 64;

const SOURCE_RECORD_FRAME_COUNT: usize = 9;
const S9_WIRE_FRAME_COUNT: usize = 12;
const S10_WIRE_FRAME_COUNT: usize = 10;
const CAPTURE_PROVENANCE_FRAME_COUNT: usize = 32;
const S9_REQUEST_FRAME_COUNT: usize = 18;
const S9_DECISION_FRAME_COUNT: usize = 22;
const S10_QUERY_FRAME_COUNT: usize = 17;
const S10_OBSERVATION_FRAME_COUNT: usize = 21;

const S13_CONTRACT_SHA256: [u8; 32] = [
    0x6b, 0xb6, 0x17, 0x68, 0x22, 0xda, 0xc0, 0xbc, 0xf7, 0x2a, 0x63, 0x4a, 0xd4, 0xfc, 0x10, 0x9c,
    0xb7, 0xee, 0xd1, 0xd8, 0xb9, 0xd6, 0xe4, 0xb3, 0xd2, 0xe7, 0x74, 0x85, 0x20, 0x74, 0xb6, 0xa6,
];

#[derive(Debug, thiserror::Error)]
#[error("{code}: {detail}")]
struct RecoveredEnvelopeSourceV1Error {
    code: &'static str,
    detail: &'static str,
}

impl RecoveredEnvelopeSourceV1Error {
    #[cfg(test)]
    fn code(&self) -> &'static str {
        self.code
    }
}

type SourceResult<T> = Result<T, RecoveredEnvelopeSourceV1Error>;

fn source_error(code: &'static str, detail: &'static str) -> RecoveredEnvelopeSourceV1Error {
    RecoveredEnvelopeSourceV1Error { code, detail }
}

fn sha256_bytes(bytes: &[u8]) -> [u8; 32] {
    Sha256::digest(bytes).into()
}

fn append_frame(output: &mut Vec<u8>, value: &[u8]) {
    output.extend_from_slice(&(value.len() as u64).to_be_bytes());
    output.extend_from_slice(value);
}

fn framed_message(domain: &[u8], fields: &[&[u8]]) -> Vec<u8> {
    let mut output = Vec::new();
    append_frame(&mut output, domain);
    for field in fields {
        append_frame(&mut output, field);
    }
    output
}

fn framed_digest(domain: &[u8], fields: &[&[u8]]) -> [u8; 32] {
    sha256_bytes(&framed_message(domain, fields))
}

fn nonzero(value: &[u8; 32]) -> bool {
    value.iter().any(|byte| *byte != 0)
}

fn valid_label_bytes(value: &[u8]) -> bool {
    !value.is_empty()
        && value.len() <= MAX_LABEL_BYTES
        && value.is_ascii()
        && value
            .first()
            .is_some_and(|byte| byte.is_ascii_lowercase() || byte.is_ascii_digit())
        && value.iter().all(|byte| {
            byte.is_ascii_lowercase()
                || byte.is_ascii_digit()
                || matches!(byte, b'.' | b'_' | b':' | b'-')
        })
}

fn decode_label(value: &[u8], code: &'static str) -> SourceResult<String> {
    if !valid_label_bytes(value) {
        return Err(source_error(
            code,
            "label must be 1..=128 canonical ASCII bytes without aliases or normalization",
        ));
    }
    String::from_utf8(value.to_vec()).map_err(|_| {
        source_error(
            code,
            "canonical ASCII label unexpectedly failed exact UTF-8 construction",
        )
    })
}

fn decode_fixed<const N: usize>(value: &[u8], code: &'static str) -> SourceResult<[u8; N]> {
    value
        .try_into()
        .map_err(|_| source_error(code, "fixed-width field has a noncanonical byte length"))
}

fn decode_u64(value: &[u8], code: &'static str) -> SourceResult<u64> {
    Ok(u64::from_be_bytes(decode_fixed::<8>(value, code)?))
}

fn parse_framed_message<'a>(
    raw: &'a [u8],
    expected_frames: usize,
    max_bytes: usize,
    code: &'static str,
) -> SourceResult<Vec<&'a [u8]>> {
    if raw.is_empty() || raw.len() > max_bytes {
        return Err(source_error(
            code,
            "framed message is empty or exceeds its preregistered byte bound",
        ));
    }
    let mut cursor = 0usize;
    let mut frames = Vec::with_capacity(expected_frames);
    for _ in 0..expected_frames {
        let prefix_end = cursor
            .checked_add(8)
            .ok_or_else(|| source_error(code, "frame length-prefix offset overflowed"))?;
        let prefix = raw.get(cursor..prefix_end).ok_or_else(|| {
            source_error(code, "framed message is truncated before a length prefix")
        })?;
        let length_u64 = u64::from_be_bytes(prefix.try_into().expect("eight-byte prefix"));
        let length = usize::try_from(length_u64).map_err(|_| {
            source_error(code, "frame length cannot be represented on this platform")
        })?;
        if length == 0 {
            return Err(source_error(
                code,
                "zero-length frames and implicit defaults are forbidden",
            ));
        }
        let frame_end = prefix_end
            .checked_add(length)
            .ok_or_else(|| source_error(code, "frame end offset overflowed"))?;
        let frame = raw.get(prefix_end..frame_end).ok_or_else(|| {
            source_error(code, "declared frame length exceeds the remaining bytes")
        })?;
        frames.push(frame);
        cursor = frame_end;
    }
    if cursor != raw.len() {
        return Err(source_error(
            code,
            "unknown, duplicate, extra, or trailing frames are forbidden",
        ));
    }
    Ok(frames)
}

fn exact_message_identity(actual: &[u8], expected: &[u8], code: &'static str) -> SourceResult<()> {
    if actual != expected {
        return Err(source_error(
            code,
            "domain, schema, policy, profile, contract, order, or canonical bytes drifted",
        ));
    }
    Ok(())
}

#[must_use]
struct ExactRecoveredEnvelopeLookupV1 {
    source_profile_id: String,
    source_namespace_id: String,
    tenant_id: String,
    audience: String,
    source_cluster_id: String,
    source_incarnation: [u8; 32],
    source_generation_id: [u8; 32],
    object_id: [u8; 32],
    object_revision: u64,
    expected_record_sha256: [u8; 32],
}

impl fmt::Debug for ExactRecoveredEnvelopeLookupV1 {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        formatter
            .debug_struct("ExactRecoveredEnvelopeLookupV1")
            .field("scope", &"[EXACT_SOURCE_OBJECT_IDENTITY_REDACTED]")
            .finish_non_exhaustive()
    }
}

impl ExactRecoveredEnvelopeLookupV1 {
    #[allow(clippy::too_many_arguments)]
    fn try_new(
        source_profile_id: impl Into<String>,
        source_namespace_id: impl Into<String>,
        tenant_id: impl Into<String>,
        audience: impl Into<String>,
        source_cluster_id: impl Into<String>,
        source_incarnation: [u8; 32],
        source_generation_id: [u8; 32],
        object_id: [u8; 32],
        object_revision: u64,
        expected_record_sha256: [u8; 32],
    ) -> SourceResult<Self> {
        let source_profile_id = source_profile_id.into();
        let source_namespace_id = source_namespace_id.into();
        let tenant_id = tenant_id.into();
        let audience = audience.into();
        let source_cluster_id = source_cluster_id.into();
        if !valid_label_bytes(source_profile_id.as_bytes())
            || !valid_label_bytes(source_namespace_id.as_bytes())
            || !valid_label_bytes(tenant_id.as_bytes())
            || !valid_label_bytes(audience.as_bytes())
            || !valid_label_bytes(source_cluster_id.as_bytes())
            || ![
                source_incarnation,
                source_generation_id,
                object_id,
                expected_record_sha256,
            ]
            .iter()
            .all(nonzero)
            || object_revision == 0
        {
            return Err(source_error(
                "track_b_recovered_envelope_source_v1_lookup",
                "exact source scope, generation, object, revision, and record digest are required",
            ));
        }
        Ok(Self {
            source_profile_id,
            source_namespace_id,
            tenant_id,
            audience,
            source_cluster_id,
            source_incarnation,
            source_generation_id,
            object_id,
            object_revision,
            expected_record_sha256,
        })
    }
}

/// Owner-pinned source/capture verification material. There is deliberately no
/// production constructor; an S14 feature flag is not source authorization.
struct ExternalRecoveredEnvelopeSourceTrustPermitV1 {
    source_profile_id: String,
    source_namespace_id: String,
    tenant_id: String,
    audience: String,
    source_cluster_id: String,
    source_incarnation: [u8; 32],
    source_generation_id: [u8; 32],
    signer_key_id: String,
    signer_key_version: u64,
    capture_policy_sha256: [u8; 32],
    minimum_object_revision: u64,
    ed25519_public_key: [u8; 32],
}

impl fmt::Debug for ExternalRecoveredEnvelopeSourceTrustPermitV1 {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        formatter
            .debug_struct("ExternalRecoveredEnvelopeSourceTrustPermitV1")
            .field("scope", &"[OWNER_PINNED_SOURCE_TRUST_REDACTED]")
            .finish_non_exhaustive()
    }
}

impl ExternalRecoveredEnvelopeSourceTrustPermitV1 {
    #[cfg(test)]
    #[allow(clippy::too_many_arguments)]
    fn test_only_new(
        source_profile_id: impl Into<String>,
        source_namespace_id: impl Into<String>,
        tenant_id: impl Into<String>,
        audience: impl Into<String>,
        source_cluster_id: impl Into<String>,
        source_incarnation: [u8; 32],
        source_generation_id: [u8; 32],
        signer_key_id: impl Into<String>,
        signer_key_version: u64,
        capture_policy_sha256: [u8; 32],
        minimum_object_revision: u64,
        ed25519_public_key: [u8; 32],
    ) -> Self {
        Self {
            source_profile_id: source_profile_id.into(),
            source_namespace_id: source_namespace_id.into(),
            tenant_id: tenant_id.into(),
            audience: audience.into(),
            source_cluster_id: source_cluster_id.into(),
            source_incarnation,
            source_generation_id,
            signer_key_id: signer_key_id.into(),
            signer_key_version,
            capture_policy_sha256,
            minimum_object_revision,
            ed25519_public_key,
        }
    }
}

#[derive(Debug)]
enum ExternalRecoveredEnvelopeSourceFailureV1 {
    NotFound,
    Pending,
    Conflict,
    Stale,
    Rollback,
    Unavailable,
    Unauthenticated,
    Malformed,
    Indeterminate,
}

/// The only ingress allocation surface. A future source must stream into this
/// sink; it cannot hand S14 an already-unbounded allocation.
struct BoundedRecoveredSourceRecordV1 {
    bytes: Vec<u8>,
}

impl BoundedRecoveredSourceRecordV1 {
    fn new() -> Self {
        Self { bytes: Vec::new() }
    }

    fn push_chunk(&mut self, chunk: &[u8]) -> SourceResult<()> {
        let new_len = self.bytes.len().checked_add(chunk.len()).ok_or_else(|| {
            source_error(
                "track_b_recovered_envelope_source_v1_ingress_bounds",
                "streamed source record length overflowed",
            )
        })?;
        if new_len > MAX_SOURCE_RECORD_BYTES {
            return Err(source_error(
                "track_b_recovered_envelope_source_v1_ingress_bounds",
                "streamed source record exceeds the 272 KiB cap",
            ));
        }
        self.bytes.try_reserve(chunk.len()).map_err(|_| {
            source_error(
                "track_b_recovered_envelope_source_v1_ingress_allocation",
                "bounded source-record allocation failed",
            )
        })?;
        self.bytes.extend_from_slice(chunk);
        Ok(())
    }

    fn finish(self) -> SourceResult<Box<[u8]>> {
        if self.bytes.is_empty() {
            return Err(source_error(
                "track_b_recovered_envelope_source_v1_ingress_bounds",
                "source returned an empty exact object",
            ));
        }
        Ok(self.bytes.into_boxed_slice())
    }
}

mod recovered_source_seal {
    pub(super) trait Sealed {}
}

/// Private preregistered exact-object read only. There is no latest/list,
/// retry, fallback, cache, write, delete, or production implementation.
trait ExternalRecoveredEnvelopeSourceV1: recovered_source_seal::Sealed {
    fn read_exact(
        &self,
        lookup: &ExactRecoveredEnvelopeLookupV1,
        sink: &mut BoundedRecoveredSourceRecordV1,
    ) -> Result<(), ExternalRecoveredEnvelopeSourceFailureV1>;
}

struct CaptureProvenanceClaimV1 {
    source_profile_id: String,
    source_namespace_id: String,
    tenant_id: String,
    audience: String,
    source_cluster_id: String,
    source_incarnation: [u8; 32],
    source_generation_id: [u8; 32],
    object_id: [u8; 32],
    object_revision: u64,
    // These two fields bind the E9+E10 evidence payload, not the full outer
    // source record R: size is len(E9)+len(E10), while the digest uses the
    // RAW_OBJECT_DOMAIN frame. The exact R digest is independently pinned by
    // ExactRecoveredEnvelopeLookupV1::expected_record_sha256.
    object_size: u64,
    raw_object_sha256: [u8; 32],
    s9_wire_len: u64,
    s9_wire_sha256: [u8; 32],
    s10_wire_len: u64,
    s10_wire_sha256: [u8; 32],
    s13_envelope_sha256: [u8; 32],
    s9_request_sha256: [u8; 32],
    s9_decision_message_sha256: [u8; 32],
    s10_query_sha256: [u8; 32],
    s10_observation_message_sha256: [u8; 32],
    capture_id: [u8; 32],
    capture_sequence: u64,
    producer_identity_sha256: [u8; 32],
    build_identity_sha256: [u8; 32],
    capture_policy_sha256: [u8; 32],
    previous_receipt_sha256: [u8; 32],
    signer_key_id: String,
    signer_key_version: u64,
}

impl fmt::Debug for CaptureProvenanceClaimV1 {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        formatter
            .debug_struct("CaptureProvenanceClaimV1")
            .field("scope", &"[SOURCE_SIGNED_CAPTURE_CLAIM_REDACTED]")
            .finish_non_exhaustive()
    }
}

fn capture_provenance_message(claim: &CaptureProvenanceClaimV1) -> SourceResult<Vec<u8>> {
    if !valid_label_bytes(claim.source_profile_id.as_bytes())
        || !valid_label_bytes(claim.source_namespace_id.as_bytes())
        || !valid_label_bytes(claim.tenant_id.as_bytes())
        || !valid_label_bytes(claim.audience.as_bytes())
        || !valid_label_bytes(claim.source_cluster_id.as_bytes())
        || !valid_label_bytes(claim.signer_key_id.as_bytes())
    {
        return Err(source_error(
            "track_b_recovered_envelope_source_v1_provenance_label",
            "capture-provenance labels must be canonical ASCII",
        ));
    }
    let commitments = [
        claim.source_incarnation,
        claim.source_generation_id,
        claim.object_id,
        claim.raw_object_sha256,
        claim.s9_wire_sha256,
        claim.s10_wire_sha256,
        claim.s13_envelope_sha256,
        claim.s9_request_sha256,
        claim.s9_decision_message_sha256,
        claim.s10_query_sha256,
        claim.s10_observation_message_sha256,
        claim.capture_id,
        claim.producer_identity_sha256,
        claim.build_identity_sha256,
        claim.capture_policy_sha256,
    ];
    if !commitments.iter().all(nonzero)
        || claim.object_revision == 0
        || claim.object_size == 0
        || claim.s9_wire_len == 0
        || claim.s10_wire_len == 0
        || claim.capture_sequence == 0
        || claim.signer_key_version == 0
        || (claim.capture_sequence == 1 && nonzero(&claim.previous_receipt_sha256))
        || (claim.capture_sequence > 1 && !nonzero(&claim.previous_receipt_sha256))
    {
        return Err(source_error(
            "track_b_recovered_envelope_source_v1_provenance_commitment",
            "capture claim requires exact nonzero identities, sizes, revisions, and canonical predecessor semantics",
        ));
    }
    let object_revision = claim.object_revision.to_be_bytes();
    let object_size = claim.object_size.to_be_bytes();
    let s9_wire_len = claim.s9_wire_len.to_be_bytes();
    let s10_wire_len = claim.s10_wire_len.to_be_bytes();
    let capture_sequence = claim.capture_sequence.to_be_bytes();
    let signer_key_version = claim.signer_key_version.to_be_bytes();
    Ok(framed_message(
        CAPTURE_PROVENANCE_DOMAIN,
        &[
            POLICY_ID.as_bytes(),
            PROFILE.as_bytes(),
            CAPTURE_PROVENANCE_SCHEMA_ID.as_bytes(),
            claim.source_profile_id.as_bytes(),
            claim.source_namespace_id.as_bytes(),
            claim.tenant_id.as_bytes(),
            claim.audience.as_bytes(),
            claim.source_cluster_id.as_bytes(),
            &claim.source_incarnation,
            &claim.source_generation_id,
            &claim.object_id,
            &object_revision,
            &object_size,
            &claim.raw_object_sha256,
            &s9_wire_len,
            &claim.s9_wire_sha256,
            &s10_wire_len,
            &claim.s10_wire_sha256,
            &claim.s13_envelope_sha256,
            &claim.s9_request_sha256,
            &claim.s9_decision_message_sha256,
            &claim.s10_query_sha256,
            &claim.s10_observation_message_sha256,
            &claim.capture_id,
            &capture_sequence,
            &claim.producer_identity_sha256,
            &claim.build_identity_sha256,
            &claim.capture_policy_sha256,
            &claim.previous_receipt_sha256,
            claim.signer_key_id.as_bytes(),
            &signer_key_version,
        ],
    ))
}

fn decode_capture_provenance_message(raw: &[u8]) -> SourceResult<CaptureProvenanceClaimV1> {
    let frames = parse_framed_message(
        raw,
        CAPTURE_PROVENANCE_FRAME_COUNT,
        MAX_PROVENANCE_MESSAGE_BYTES,
        "track_b_recovered_envelope_source_v1_provenance_framing",
    )?;
    let claim = CaptureProvenanceClaimV1 {
        source_profile_id: decode_label(
            frames[4],
            "track_b_recovered_envelope_source_v1_provenance_label",
        )?,
        source_namespace_id: decode_label(
            frames[5],
            "track_b_recovered_envelope_source_v1_provenance_label",
        )?,
        tenant_id: decode_label(
            frames[6],
            "track_b_recovered_envelope_source_v1_provenance_label",
        )?,
        audience: decode_label(
            frames[7],
            "track_b_recovered_envelope_source_v1_provenance_label",
        )?,
        source_cluster_id: decode_label(
            frames[8],
            "track_b_recovered_envelope_source_v1_provenance_label",
        )?,
        source_incarnation: decode_fixed(
            frames[9],
            "track_b_recovered_envelope_source_v1_provenance_fixed",
        )?,
        source_generation_id: decode_fixed(
            frames[10],
            "track_b_recovered_envelope_source_v1_provenance_fixed",
        )?,
        object_id: decode_fixed(
            frames[11],
            "track_b_recovered_envelope_source_v1_provenance_fixed",
        )?,
        object_revision: decode_u64(
            frames[12],
            "track_b_recovered_envelope_source_v1_provenance_fixed",
        )?,
        object_size: decode_u64(
            frames[13],
            "track_b_recovered_envelope_source_v1_provenance_fixed",
        )?,
        raw_object_sha256: decode_fixed(
            frames[14],
            "track_b_recovered_envelope_source_v1_provenance_fixed",
        )?,
        s9_wire_len: decode_u64(
            frames[15],
            "track_b_recovered_envelope_source_v1_provenance_fixed",
        )?,
        s9_wire_sha256: decode_fixed(
            frames[16],
            "track_b_recovered_envelope_source_v1_provenance_fixed",
        )?,
        s10_wire_len: decode_u64(
            frames[17],
            "track_b_recovered_envelope_source_v1_provenance_fixed",
        )?,
        s10_wire_sha256: decode_fixed(
            frames[18],
            "track_b_recovered_envelope_source_v1_provenance_fixed",
        )?,
        s13_envelope_sha256: decode_fixed(
            frames[19],
            "track_b_recovered_envelope_source_v1_provenance_fixed",
        )?,
        s9_request_sha256: decode_fixed(
            frames[20],
            "track_b_recovered_envelope_source_v1_provenance_fixed",
        )?,
        s9_decision_message_sha256: decode_fixed(
            frames[21],
            "track_b_recovered_envelope_source_v1_provenance_fixed",
        )?,
        s10_query_sha256: decode_fixed(
            frames[22],
            "track_b_recovered_envelope_source_v1_provenance_fixed",
        )?,
        s10_observation_message_sha256: decode_fixed(
            frames[23],
            "track_b_recovered_envelope_source_v1_provenance_fixed",
        )?,
        capture_id: decode_fixed(
            frames[24],
            "track_b_recovered_envelope_source_v1_provenance_fixed",
        )?,
        capture_sequence: decode_u64(
            frames[25],
            "track_b_recovered_envelope_source_v1_provenance_fixed",
        )?,
        producer_identity_sha256: decode_fixed(
            frames[26],
            "track_b_recovered_envelope_source_v1_provenance_fixed",
        )?,
        build_identity_sha256: decode_fixed(
            frames[27],
            "track_b_recovered_envelope_source_v1_provenance_fixed",
        )?,
        capture_policy_sha256: decode_fixed(
            frames[28],
            "track_b_recovered_envelope_source_v1_provenance_fixed",
        )?,
        previous_receipt_sha256: decode_fixed(
            frames[29],
            "track_b_recovered_envelope_source_v1_provenance_fixed",
        )?,
        signer_key_id: decode_label(
            frames[30],
            "track_b_recovered_envelope_source_v1_provenance_label",
        )?,
        signer_key_version: decode_u64(
            frames[31],
            "track_b_recovered_envelope_source_v1_provenance_fixed",
        )?,
    };
    let exact = capture_provenance_message(&claim)?;
    exact_message_identity(
        raw,
        &exact,
        "track_b_recovered_envelope_source_v1_provenance_identity",
    )?;
    Ok(claim)
}

fn decode_s9_request_message(raw: &[u8]) -> SourceResult<ExternalCurrentnessRequestV1> {
    let frames = parse_framed_message(
        raw,
        S9_REQUEST_FRAME_COUNT,
        MAX_CANONICAL_MESSAGE_BYTES,
        "track_b_recovered_envelope_source_v1_s9_request_framing",
    )?;
    let request = ExternalCurrentnessRequestV1 {
        provider_profile_id: decode_label(
            frames[4],
            "track_b_recovered_envelope_source_v1_s9_request_label",
        )?,
        authority_namespace_id: decode_label(
            frames[5],
            "track_b_recovered_envelope_source_v1_s9_request_label",
        )?,
        tenant_id: decode_label(
            frames[6],
            "track_b_recovered_envelope_source_v1_s9_request_label",
        )?,
        audience: decode_label(
            frames[7],
            "track_b_recovered_envelope_source_v1_s9_request_label",
        )?,
        operation_id: decode_fixed(
            frames[8],
            "track_b_recovered_envelope_source_v1_s9_request_fixed",
        )?,
        challenge: decode_fixed(
            frames[9],
            "track_b_recovered_envelope_source_v1_s9_request_fixed",
        )?,
        expected_epoch: decode_u64(
            frames[10],
            "track_b_recovered_envelope_source_v1_s9_request_fixed",
        )?,
        expected_epoch_record_sha256: decode_fixed(
            frames[11],
            "track_b_recovered_envelope_source_v1_s9_request_fixed",
        )?,
        registry_generation_id: decode_fixed(
            frames[12],
            "track_b_recovered_envelope_source_v1_s9_request_fixed",
        )?,
        receiver_identity_sha256: decode_fixed(
            frames[13],
            "track_b_recovered_envelope_source_v1_s9_request_fixed",
        )?,
        build_identity_sha256: decode_fixed(
            frames[14],
            "track_b_recovered_envelope_source_v1_s9_request_fixed",
        )?,
        allowlist_sha256: decode_fixed(
            frames[15],
            "track_b_recovered_envelope_source_v1_s9_request_fixed",
        )?,
        keyset_identity_sha256: decode_fixed(
            frames[16],
            "track_b_recovered_envelope_source_v1_s9_request_fixed",
        )?,
        trust_policy_sha256: decode_fixed(
            frames[17],
            "track_b_recovered_envelope_source_v1_s9_request_fixed",
        )?,
    };
    let exact = super::s9_request_message(&request).map_err(|_| {
        source_error(
            "track_b_recovered_envelope_source_v1_s9_request_typed",
            "decoded S9 request is malformed or noncanonical",
        )
    })?;
    exact_message_identity(
        raw,
        &exact,
        "track_b_recovered_envelope_source_v1_s9_request_identity",
    )?;
    Ok(request)
}

fn decode_s9_decision_message(
    raw: &[u8],
    signature: [u8; 64],
) -> SourceResult<SignedExternalCurrentnessDecisionV1> {
    let frames = parse_framed_message(
        raw,
        S9_DECISION_FRAME_COUNT,
        MAX_CANONICAL_MESSAGE_BYTES,
        "track_b_recovered_envelope_source_v1_s9_decision_framing",
    )?;
    let state = match frames[5] {
        b"ACTIVE" => ExternalAuthorityStateV1::Active,
        b"FENCING" => ExternalAuthorityStateV1::Fencing,
        b"PENDING" => ExternalAuthorityStateV1::Pending,
        b"REVOKED" => ExternalAuthorityStateV1::Revoked,
        b"INDETERMINATE" => ExternalAuthorityStateV1::Indeterminate,
        _ => {
            return Err(source_error(
                "track_b_recovered_envelope_source_v1_s9_decision_state",
                "S9 authority state is not an exact canonical enum label",
            ))
        }
    };
    let decision = SignedExternalCurrentnessDecisionV1 {
        request_sha256: decode_fixed(
            frames[4],
            "track_b_recovered_envelope_source_v1_s9_decision_fixed",
        )?,
        state,
        provider_cluster_id: decode_label(
            frames[6],
            "track_b_recovered_envelope_source_v1_s9_decision_label",
        )?,
        provider_incarnation: decode_fixed(
            frames[7],
            "track_b_recovered_envelope_source_v1_s9_decision_fixed",
        )?,
        leader_term: decode_u64(
            frames[8],
            "track_b_recovered_envelope_source_v1_s9_decision_fixed",
        )?,
        committed_revision: decode_u64(
            frames[9],
            "track_b_recovered_envelope_source_v1_s9_decision_fixed",
        )?,
        authority_sequence: decode_u64(
            frames[10],
            "track_b_recovered_envelope_source_v1_s9_decision_fixed",
        )?,
        active_epoch: decode_u64(
            frames[11],
            "track_b_recovered_envelope_source_v1_s9_decision_fixed",
        )?,
        active_epoch_record_sha256: decode_fixed(
            frames[12],
            "track_b_recovered_envelope_source_v1_s9_decision_fixed",
        )?,
        active_registry_generation_id: decode_fixed(
            frames[13],
            "track_b_recovered_envelope_source_v1_s9_decision_fixed",
        )?,
        active_keyset_identity_sha256: decode_fixed(
            frames[14],
            "track_b_recovered_envelope_source_v1_s9_decision_fixed",
        )?,
        revocation_checkpoint_sha256: decode_fixed(
            frames[15],
            "track_b_recovered_envelope_source_v1_s9_decision_fixed",
        )?,
        revoked_through_epoch: decode_u64(
            frames[16],
            "track_b_recovered_envelope_source_v1_s9_decision_fixed",
        )?,
        provider_custody_claim_sha256: decode_fixed(
            frames[17],
            "track_b_recovered_envelope_source_v1_s9_decision_fixed",
        )?,
        provider_old_key_use_denied_claim_sha256: decode_fixed(
            frames[18],
            "track_b_recovered_envelope_source_v1_s9_decision_fixed",
        )?,
        decision_id: decode_fixed(
            frames[19],
            "track_b_recovered_envelope_source_v1_s9_decision_fixed",
        )?,
        signer_key_id: decode_label(
            frames[20],
            "track_b_recovered_envelope_source_v1_s9_decision_label",
        )?,
        signer_key_version: decode_u64(
            frames[21],
            "track_b_recovered_envelope_source_v1_s9_decision_fixed",
        )?,
        ed25519_signature: signature,
    };
    let exact = super::validated_s9_decision_message(&decision).map_err(|_| {
        source_error(
            "track_b_recovered_envelope_source_v1_s9_decision_typed",
            "decoded S9 decision is malformed or noncanonical",
        )
    })?;
    exact_message_identity(
        raw,
        &exact,
        "track_b_recovered_envelope_source_v1_s9_decision_identity",
    )?;
    Ok(decision)
}

fn decode_s10_query_message(raw: &[u8]) -> SourceResult<ExternalOperationRecoveryQueryV1> {
    let frames = parse_framed_message(
        raw,
        S10_QUERY_FRAME_COUNT,
        MAX_CANONICAL_MESSAGE_BYTES,
        "track_b_recovered_envelope_source_v1_s10_query_framing",
    )?;
    let query = ExternalOperationRecoveryQueryV1 {
        provider_profile_id: decode_label(
            frames[5],
            "track_b_recovered_envelope_source_v1_s10_query_label",
        )?,
        authority_namespace_id: decode_label(
            frames[6],
            "track_b_recovered_envelope_source_v1_s10_query_label",
        )?,
        tenant_id: decode_label(
            frames[7],
            "track_b_recovered_envelope_source_v1_s10_query_label",
        )?,
        audience: decode_label(
            frames[8],
            "track_b_recovered_envelope_source_v1_s10_query_label",
        )?,
        provider_cluster_id: decode_label(
            frames[9],
            "track_b_recovered_envelope_source_v1_s10_query_label",
        )?,
        provider_incarnation: decode_fixed(
            frames[10],
            "track_b_recovered_envelope_source_v1_s10_query_fixed",
        )?,
        lookup_query_id: decode_fixed(
            frames[11],
            "track_b_recovered_envelope_source_v1_s10_query_fixed",
        )?,
        lookup_challenge: decode_fixed(
            frames[12],
            "track_b_recovered_envelope_source_v1_s10_query_fixed",
        )?,
        original_operation_id: decode_fixed(
            frames[13],
            "track_b_recovered_envelope_source_v1_s10_query_fixed",
        )?,
        original_challenge: decode_fixed(
            frames[14],
            "track_b_recovered_envelope_source_v1_s10_query_fixed",
        )?,
        original_request_sha256: decode_fixed(
            frames[15],
            "track_b_recovered_envelope_source_v1_s10_query_fixed",
        )?,
        trust_policy_sha256: decode_fixed(
            frames[16],
            "track_b_recovered_envelope_source_v1_s10_query_fixed",
        )?,
    };
    let exact = validated_lookup_query_message(&query).map_err(|_| {
        source_error(
            "track_b_recovered_envelope_source_v1_s10_query_typed",
            "decoded S10 query is malformed or noncanonical",
        )
    })?;
    exact_message_identity(
        raw,
        &exact,
        "track_b_recovered_envelope_source_v1_s10_query_identity",
    )?;
    Ok(query)
}

fn decode_s10_observation_message(
    raw: &[u8],
    signature: [u8; 64],
) -> SourceResult<SignedExternalOperationRecoveryObservationV1> {
    let frames = parse_framed_message(
        raw,
        S10_OBSERVATION_FRAME_COUNT,
        MAX_CANONICAL_MESSAGE_BYTES,
        "track_b_recovered_envelope_source_v1_s10_observation_framing",
    )?;
    let state = match frames[6] {
        b"COMMITTED" => ExternalOperationRecoveryStateV1::Committed,
        b"NOT_FOUND" => ExternalOperationRecoveryStateV1::NotFound,
        b"PENDING" => ExternalOperationRecoveryStateV1::Pending,
        b"CONFLICT" => ExternalOperationRecoveryStateV1::Conflict,
        b"INDETERMINATE" => ExternalOperationRecoveryStateV1::Indeterminate,
        _ => {
            return Err(source_error(
                "track_b_recovered_envelope_source_v1_s10_observation_state",
                "S10 recovery state is not an exact canonical enum label",
            ))
        }
    };
    let observation = SignedExternalOperationRecoveryObservationV1 {
        lookup_query_sha256: decode_fixed(
            frames[5],
            "track_b_recovered_envelope_source_v1_s10_observation_fixed",
        )?,
        state,
        original_operation_id: decode_fixed(
            frames[7],
            "track_b_recovered_envelope_source_v1_s10_observation_fixed",
        )?,
        original_challenge: decode_fixed(
            frames[8],
            "track_b_recovered_envelope_source_v1_s10_observation_fixed",
        )?,
        original_request_sha256: decode_fixed(
            frames[9],
            "track_b_recovered_envelope_source_v1_s10_observation_fixed",
        )?,
        provider_cluster_id: decode_label(
            frames[10],
            "track_b_recovered_envelope_source_v1_s10_observation_label",
        )?,
        provider_incarnation: decode_fixed(
            frames[11],
            "track_b_recovered_envelope_source_v1_s10_observation_fixed",
        )?,
        leader_term: decode_u64(
            frames[12],
            "track_b_recovered_envelope_source_v1_s10_observation_fixed",
        )?,
        operation_committed_revision: decode_u64(
            frames[13],
            "track_b_recovered_envelope_source_v1_s10_observation_fixed",
        )?,
        observed_journal_revision: decode_u64(
            frames[14],
            "track_b_recovered_envelope_source_v1_s10_observation_fixed",
        )?,
        journal_generation_id: decode_fixed(
            frames[15],
            "track_b_recovered_envelope_source_v1_s10_observation_fixed",
        )?,
        journal_record_sequence: decode_u64(
            frames[16],
            "track_b_recovered_envelope_source_v1_s10_observation_fixed",
        )?,
        original_decision_sha256: decode_fixed(
            frames[17],
            "track_b_recovered_envelope_source_v1_s10_observation_fixed",
        )?,
        result_id: decode_fixed(
            frames[18],
            "track_b_recovered_envelope_source_v1_s10_observation_fixed",
        )?,
        signer_key_id: decode_label(
            frames[19],
            "track_b_recovered_envelope_source_v1_s10_observation_label",
        )?,
        signer_key_version: decode_u64(
            frames[20],
            "track_b_recovered_envelope_source_v1_s10_observation_fixed",
        )?,
        ed25519_signature: signature,
    };
    let exact = validated_observation_message(&observation).map_err(|_| {
        source_error(
            "track_b_recovered_envelope_source_v1_s10_observation_typed",
            "decoded S10 observation is malformed or noncanonical",
        )
    })?;
    exact_message_identity(
        raw,
        &exact,
        "track_b_recovered_envelope_source_v1_s10_observation_identity",
    )?;
    Ok(observation)
}

struct DecodedS9WireV1 {
    envelope: RecoveredS9EnvelopeV1,
    wire_sha256: [u8; 32],
    request_sha256: [u8; 32],
    decision_message_sha256: [u8; 32],
}

fn decode_s9_wire(raw: &[u8]) -> SourceResult<DecodedS9WireV1> {
    let frames = parse_framed_message(
        raw,
        S9_WIRE_FRAME_COUNT,
        MAX_S9_WIRE_BYTES,
        "track_b_recovered_envelope_source_v1_s9_wire_framing",
    )?;
    let expected_prefix = [
        S9_WIRE_DOMAIN,
        POLICY_ID.as_bytes(),
        PROFILE.as_bytes(),
        S9_WIRE_SCHEMA_ID.as_bytes(),
        &super::S9_CONTRACT_SHA256,
        &super::S10_CONTRACT_SHA256,
        &super::S11_CONTRACT_SHA256,
        &super::S12_CONTRACT_SHA256,
        &S13_CONTRACT_SHA256,
    ];
    for (actual, expected) in frames[..9].iter().zip(expected_prefix) {
        exact_message_identity(
            actual,
            expected,
            "track_b_recovered_envelope_source_v1_s9_wire_identity",
        )?;
    }
    let component_bytes = frames[9]
        .len()
        .checked_add(frames[10].len())
        .and_then(|value| value.checked_add(frames[11].len()))
        .ok_or_else(|| {
            source_error(
                "track_b_recovered_envelope_source_v1_s9_wire_bounds",
                "S9 component length overflowed",
            )
        })?;
    if component_bytes > MAX_EVIDENCE_COMPONENT_BYTES {
        return Err(source_error(
            "track_b_recovered_envelope_source_v1_s9_wire_bounds",
            "S9 request, decision, and signature exceed the 128 KiB aggregate cap",
        ));
    }
    let signature = decode_fixed::<ED25519_SIGNATURE_BYTES>(
        frames[11],
        "track_b_recovered_envelope_source_v1_s9_signature",
    )?;
    let request = decode_s9_request_message(frames[9])?;
    let decision = decode_s9_decision_message(frames[10], signature)?;
    let envelope = RecoveredS9EnvelopeV1::try_new(
        request,
        frames[9].to_vec().into_boxed_slice(),
        decision,
        frames[10].to_vec().into_boxed_slice(),
        frames[11].to_vec().into_boxed_slice(),
    )
    .map_err(|_| {
        source_error(
            "track_b_recovered_envelope_source_v1_s13_envelope",
            "strictly decoded S9 wire failed the unchanged S13 envelope constructor",
        )
    })?;
    Ok(DecodedS9WireV1 {
        envelope,
        wire_sha256: sha256_bytes(raw),
        request_sha256: sha256_bytes(frames[9]),
        decision_message_sha256: sha256_bytes(frames[10]),
    })
}

struct DecodedS10WireV1 {
    query: ExternalOperationRecoveryQueryV1,
    observation: SignedExternalOperationRecoveryObservationV1,
    wire_sha256: [u8; 32],
    query_sha256: [u8; 32],
    observation_message_sha256: [u8; 32],
}

fn decode_s10_wire(raw: &[u8]) -> SourceResult<DecodedS10WireV1> {
    let frames = parse_framed_message(
        raw,
        S10_WIRE_FRAME_COUNT,
        MAX_S10_WIRE_BYTES,
        "track_b_recovered_envelope_source_v1_s10_wire_framing",
    )?;
    let expected_prefix = [
        S10_WIRE_DOMAIN,
        POLICY_ID.as_bytes(),
        PROFILE.as_bytes(),
        S10_WIRE_SCHEMA_ID.as_bytes(),
        &super::S9_CONTRACT_SHA256,
        &super::S10_CONTRACT_SHA256,
        &S13_CONTRACT_SHA256,
    ];
    for (actual, expected) in frames[..7].iter().zip(expected_prefix) {
        exact_message_identity(
            actual,
            expected,
            "track_b_recovered_envelope_source_v1_s10_wire_identity",
        )?;
    }
    let component_bytes = frames[7]
        .len()
        .checked_add(frames[8].len())
        .and_then(|value| value.checked_add(frames[9].len()))
        .ok_or_else(|| {
            source_error(
                "track_b_recovered_envelope_source_v1_s10_wire_bounds",
                "S10 component length overflowed",
            )
        })?;
    if component_bytes > MAX_EVIDENCE_COMPONENT_BYTES {
        return Err(source_error(
            "track_b_recovered_envelope_source_v1_s10_wire_bounds",
            "S10 query, observation, and signature exceed the 128 KiB aggregate cap",
        ));
    }
    let signature = decode_fixed::<ED25519_SIGNATURE_BYTES>(
        frames[9],
        "track_b_recovered_envelope_source_v1_s10_signature",
    )?;
    let query = decode_s10_query_message(frames[7])?;
    let observation = decode_s10_observation_message(frames[8], signature)?;
    Ok(DecodedS10WireV1 {
        query,
        observation,
        wire_sha256: sha256_bytes(raw),
        query_sha256: sha256_bytes(frames[7]),
        observation_message_sha256: sha256_bytes(frames[8]),
    })
}

struct VerifiedRecoveredEnvelopeCaptureV1 {
    provenance_message_sha256: [u8; 32],
    s9_wire_sha256: [u8; 32],
    s10_wire_sha256: [u8; 32],
    raw_object_sha256: [u8; 32],
}

impl fmt::Debug for VerifiedRecoveredEnvelopeCaptureV1 {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        formatter
            .debug_struct("VerifiedRecoveredEnvelopeCaptureV1")
            .field("scope", &"[SIGNED_HISTORICAL_CAPTURE_CLAIM_NOT_DURABILITY]")
            .finish_non_exhaustive()
    }
}

fn validate_source_permit(
    permit: &ExternalRecoveredEnvelopeSourceTrustPermitV1,
) -> SourceResult<()> {
    if !valid_label_bytes(permit.source_profile_id.as_bytes())
        || !valid_label_bytes(permit.source_namespace_id.as_bytes())
        || !valid_label_bytes(permit.tenant_id.as_bytes())
        || !valid_label_bytes(permit.audience.as_bytes())
        || !valid_label_bytes(permit.source_cluster_id.as_bytes())
        || !valid_label_bytes(permit.signer_key_id.as_bytes())
        || !nonzero(&permit.source_incarnation)
        || !nonzero(&permit.source_generation_id)
        || !nonzero(&permit.capture_policy_sha256)
        || !nonzero(&permit.ed25519_public_key)
        || permit.signer_key_version == 0
        || permit.minimum_object_revision == 0
    {
        return Err(source_error(
            "track_b_recovered_envelope_source_v1_source_permit",
            "owner-pinned source permit requires canonical scope, nonzero identities, signer version, revision floor, policy, and public key",
        ));
    }
    Ok(())
}

#[allow(clippy::too_many_arguments)]
fn verify_capture_claim(
    claim: &CaptureProvenanceClaimV1,
    provenance_message: &[u8],
    source_signature: &[u8; 64],
    lookup: &ExactRecoveredEnvelopeLookupV1,
    permit: &ExternalRecoveredEnvelopeSourceTrustPermitV1,
    s9_wire: &[u8],
    s10_wire: &[u8],
    decoded_s9: &DecodedS9WireV1,
    decoded_s10: &DecodedS10WireV1,
) -> SourceResult<VerifiedRecoveredEnvelopeCaptureV1> {
    validate_source_permit(permit)?;
    let object_size = s9_wire.len().checked_add(s10_wire.len()).ok_or_else(|| {
        source_error(
            "track_b_recovered_envelope_source_v1_capture_binding",
            "raw evidence object size overflowed",
        )
    })?;
    let object_size_u64 = u64::try_from(object_size).map_err(|_| {
        source_error(
            "track_b_recovered_envelope_source_v1_capture_binding",
            "raw evidence object size cannot be represented canonically",
        )
    })?;
    let s9_len = u64::try_from(s9_wire.len()).map_err(|_| {
        source_error(
            "track_b_recovered_envelope_source_v1_capture_binding",
            "S9 wire length cannot be represented canonically",
        )
    })?;
    let s10_len = u64::try_from(s10_wire.len()).map_err(|_| {
        source_error(
            "track_b_recovered_envelope_source_v1_capture_binding",
            "S10 wire length cannot be represented canonically",
        )
    })?;
    let raw_object_sha256 = framed_digest(RAW_OBJECT_DOMAIN, &[s9_wire, s10_wire]);
    if claim.source_profile_id != lookup.source_profile_id
        || claim.source_namespace_id != lookup.source_namespace_id
        || claim.tenant_id != lookup.tenant_id
        || claim.audience != lookup.audience
        || claim.source_cluster_id != lookup.source_cluster_id
        || claim.source_incarnation != lookup.source_incarnation
        || claim.source_generation_id != lookup.source_generation_id
        || claim.object_id != lookup.object_id
        || claim.object_revision != lookup.object_revision
        || claim.source_profile_id != permit.source_profile_id
        || claim.source_namespace_id != permit.source_namespace_id
        || claim.tenant_id != permit.tenant_id
        || claim.audience != permit.audience
        || claim.source_cluster_id != permit.source_cluster_id
        || claim.source_incarnation != permit.source_incarnation
        || claim.source_generation_id != permit.source_generation_id
        || claim.object_revision < permit.minimum_object_revision
        || claim.signer_key_id != permit.signer_key_id
        || claim.signer_key_version != permit.signer_key_version
        || claim.capture_policy_sha256 != permit.capture_policy_sha256
    {
        return Err(source_error(
            "track_b_recovered_envelope_source_v1_source_scope",
            "capture claim, exact lookup, and owner-pinned source permit do not match",
        ));
    }
    if claim.object_size != object_size_u64
        || claim.raw_object_sha256 != raw_object_sha256
        || claim.s9_wire_len != s9_len
        || claim.s9_wire_sha256 != decoded_s9.wire_sha256
        || claim.s10_wire_len != s10_len
        || claim.s10_wire_sha256 != decoded_s10.wire_sha256
        || claim.s13_envelope_sha256 != decoded_s9.envelope.envelope_sha256
        || claim.s9_request_sha256 != decoded_s9.request_sha256
        || claim.s9_decision_message_sha256 != decoded_s9.decision_message_sha256
        || claim.s10_query_sha256 != decoded_s10.query_sha256
        || claim.s10_observation_message_sha256 != decoded_s10.observation_message_sha256
    {
        return Err(source_error(
            "track_b_recovered_envelope_source_v1_capture_binding",
            "signed provenance does not exactly bind the decoded S9 and raw signed S10 bytes",
        ));
    }
    UnparsedPublicKey::new(&ED25519, permit.ed25519_public_key)
        .verify(provenance_message, source_signature)
        .map_err(|_| {
            source_error(
                "track_b_recovered_envelope_source_v1_source_signature",
                "source/capture signature failed owner-pinned Ed25519 verification",
            )
        })?;
    Ok(VerifiedRecoveredEnvelopeCaptureV1 {
        provenance_message_sha256: sha256_bytes(provenance_message),
        s9_wire_sha256: decoded_s9.wire_sha256,
        s10_wire_sha256: decoded_s10.wire_sha256,
        raw_object_sha256,
    })
}

struct DecodedRecoveredEvidenceRecordV1 {
    handoff: RecoveredEvidenceHandoffV1,
    capture: VerifiedRecoveredEnvelopeCaptureV1,
    record_sha256: [u8; 32],
}

impl fmt::Debug for DecodedRecoveredEvidenceRecordV1 {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        formatter
            .debug_struct("DecodedRecoveredEvidenceRecordV1")
            .field("scope", &"[STRICTLY_DECODED_MOVE_ONLY_RECORD_REDACTED]")
            .finish_non_exhaustive()
    }
}

fn decode_and_verify_source_record_v1(
    raw: &[u8],
    lookup: &ExactRecoveredEnvelopeLookupV1,
    permit: &ExternalRecoveredEnvelopeSourceTrustPermitV1,
) -> SourceResult<DecodedRecoveredEvidenceRecordV1> {
    if raw.is_empty() || raw.len() > MAX_SOURCE_RECORD_BYTES {
        return Err(source_error(
            "track_b_recovered_envelope_source_v1_record_bounds",
            "source record is empty or exceeds the 272 KiB cap",
        ));
    }
    let record_sha256 = sha256_bytes(raw);
    if record_sha256 != lookup.expected_record_sha256 {
        return Err(source_error(
            "track_b_recovered_envelope_source_v1_record_digest",
            "exact source record digest differs from the lookup commitment",
        ));
    }
    let frames = parse_framed_message(
        raw,
        SOURCE_RECORD_FRAME_COUNT,
        MAX_SOURCE_RECORD_BYTES,
        "track_b_recovered_envelope_source_v1_record_framing",
    )?;
    let expected_prefix = [
        SOURCE_RECORD_DOMAIN,
        POLICY_ID.as_bytes(),
        PROFILE.as_bytes(),
        SOURCE_RECORD_SCHEMA_ID.as_bytes(),
        &S13_CONTRACT_SHA256,
    ];
    for (actual, expected) in frames[..5].iter().zip(expected_prefix) {
        exact_message_identity(
            actual,
            expected,
            "track_b_recovered_envelope_source_v1_record_identity",
        )?;
    }
    let source_signature = decode_fixed::<ED25519_SIGNATURE_BYTES>(
        frames[8],
        "track_b_recovered_envelope_source_v1_source_signature_bounds",
    )?;
    let decoded_s9 = decode_s9_wire(frames[5])?;
    let decoded_s10 = decode_s10_wire(frames[6])?;
    let claim = decode_capture_provenance_message(frames[7])?;
    let capture = verify_capture_claim(
        &claim,
        frames[7],
        &source_signature,
        lookup,
        permit,
        frames[5],
        frames[6],
        &decoded_s9,
        &decoded_s10,
    )?;
    Ok(DecodedRecoveredEvidenceRecordV1 {
        handoff: RecoveredEvidenceHandoffV1::new(
            decoded_s9.envelope,
            decoded_s10.query,
            decoded_s10.observation,
        ),
        capture,
        record_sha256,
    })
}

#[must_use]
struct SourcedHistoricalRecoveredEnvelopeV1 {
    historical_source_chain_sha256: [u8; 32],
    historical_chain_sha256: [u8; 32],
    record_sha256: [u8; 32],
    provenance_message_sha256: [u8; 32],
}

impl fmt::Debug for SourcedHistoricalRecoveredEnvelopeV1 {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        formatter
            .debug_struct("SourcedHistoricalRecoveredEnvelopeV1")
            .field("scope", &"[HISTORICAL_ONLY_NOT_CURRENTNESS_NOT_ADMISSION]")
            .finish_non_exhaustive()
    }
}

impl DecodedRecoveredEvidenceRecordV1 {
    #[allow(clippy::too_many_arguments)]
    fn consume_historical(
        self,
        s9_permit: &ExternalAuthorityTrustPermitV1,
        s10_permit: &ExternalOperationRecoveryTrustPermitV1,
        s11_request: &AtomicAuthorityOperationRequestV1,
        s11_permit: &AtomicAuthorityOperationTrustPermitV1,
        s11_record: &SignedCommittedAuthorityOperationV1,
    ) -> SourceResult<SourcedHistoricalRecoveredEnvelopeV1> {
        let historical: PurelyReverifiedRecoveredS9DecisionV1 = self
            .handoff
            .consume(s9_permit, s10_permit, s11_request, s11_permit, s11_record)
            .map_err(|_| {
                source_error(
                    "track_b_recovered_envelope_source_v1_local_reverification",
                    "decoded raw S9/S10 evidence failed unchanged local S13/S12 verification",
                )
            })?;
        let historical_source_chain_sha256 = framed_digest(
            HISTORICAL_SOURCE_CHAIN_DOMAIN,
            &[
                POLICY_ID.as_bytes(),
                PROFILE.as_bytes(),
                SOURCE_RECORD_SCHEMA_ID.as_bytes(),
                &S13_CONTRACT_SHA256,
                &self.record_sha256,
                &self.capture.provenance_message_sha256,
                &self.capture.s9_wire_sha256,
                &self.capture.s10_wire_sha256,
                &self.capture.raw_object_sha256,
                &historical.historical_chain_sha256,
            ],
        );
        Ok(SourcedHistoricalRecoveredEnvelopeV1 {
            historical_source_chain_sha256,
            historical_chain_sha256: historical.historical_chain_sha256,
            record_sha256: self.record_sha256,
            provenance_message_sha256: self.capture.provenance_message_sha256,
        })
    }
}

#[allow(clippy::too_many_arguments)]
fn recover_historical_from_external_source_v1<S: ExternalRecoveredEnvelopeSourceV1>(
    source: &S,
    lookup: ExactRecoveredEnvelopeLookupV1,
    source_permit: &ExternalRecoveredEnvelopeSourceTrustPermitV1,
    s9_permit: &ExternalAuthorityTrustPermitV1,
    s10_permit: &ExternalOperationRecoveryTrustPermitV1,
    s11_request: &AtomicAuthorityOperationRequestV1,
    s11_permit: &AtomicAuthorityOperationTrustPermitV1,
    s11_record: &SignedCommittedAuthorityOperationV1,
) -> SourceResult<SourcedHistoricalRecoveredEnvelopeV1> {
    let mut sink = BoundedRecoveredSourceRecordV1::new();
    source.read_exact(&lookup, &mut sink).map_err(|_| {
        source_error(
            "track_b_recovered_envelope_source_v1_source_read",
            "exact external source read failed closed without retry, cache, or fallback",
        )
    })?;
    let raw = sink.finish()?;
    decode_and_verify_source_record_v1(&raw, &lookup, source_permit)?.consume_historical(
        s9_permit,
        s10_permit,
        s11_request,
        s11_permit,
        s11_record,
    )
}

#[cfg(test)]
mod tests {
    use super::super::super::tests::{fixture as s12_fixture, resign_s10, s10_inputs, Fixture};
    use super::*;
    use crate::temporal_replay_transport::external_operation_recovery::{
        lookup_query_digest, result_id, verify_external_operation_recovery_observation_v1,
    };
    use crate::temporal_replay_transport::external_restore_authority::verify_external_currentness_decision_v1;
    use ring::signature::{Ed25519KeyPair, KeyPair};
    use std::cell::{Cell, RefCell};

    const SOURCE_SEED: [u8; 32] = [
        0xf5, 0xe5, 0x76, 0x7c, 0xf1, 0x53, 0x31, 0x95, 0x17, 0x63, 0x0f, 0x22, 0x68, 0x76, 0xb8,
        0x6c, 0x81, 0x60, 0xcc, 0x58, 0x3b, 0xc0, 0x13, 0x74, 0x4c, 0x6b, 0xf2, 0x55, 0xf5, 0xcc,
        0x0e, 0xe5,
    ];

    fn repeated(value: u8) -> [u8; 32] {
        [value; 32]
    }

    fn encode(value: &[u8]) -> String {
        value.iter().map(|byte| format!("{byte:02x}")).collect()
    }

    fn source_key_pair() -> Ed25519KeyPair {
        Ed25519KeyPair::from_seed_unchecked(&SOURCE_SEED).unwrap()
    }

    fn source_public_key() -> [u8; 32] {
        source_key_pair().public_key().as_ref().try_into().unwrap()
    }

    fn s9_wire(request: &[u8], decision: &[u8], signature: &[u8; 64]) -> Vec<u8> {
        framed_message(
            S9_WIRE_DOMAIN,
            &[
                POLICY_ID.as_bytes(),
                PROFILE.as_bytes(),
                S9_WIRE_SCHEMA_ID.as_bytes(),
                &super::super::S9_CONTRACT_SHA256,
                &super::super::S10_CONTRACT_SHA256,
                &super::super::S11_CONTRACT_SHA256,
                &super::super::S12_CONTRACT_SHA256,
                &S13_CONTRACT_SHA256,
                request,
                decision,
                signature,
            ],
        )
    }

    fn s10_wire(
        query: &ExternalOperationRecoveryQueryV1,
        observation: &SignedExternalOperationRecoveryObservationV1,
    ) -> Vec<u8> {
        let query_message = validated_lookup_query_message(query).unwrap();
        let observation_message = validated_observation_message(observation).unwrap();
        framed_message(
            S10_WIRE_DOMAIN,
            &[
                POLICY_ID.as_bytes(),
                PROFILE.as_bytes(),
                S10_WIRE_SCHEMA_ID.as_bytes(),
                &super::super::S9_CONTRACT_SHA256,
                &super::super::S10_CONTRACT_SHA256,
                &S13_CONTRACT_SHA256,
                &query_message,
                &observation_message,
                &observation.ed25519_signature,
            ],
        )
    }

    fn replace_frame(
        raw: &[u8],
        frame_count: usize,
        max_bytes: usize,
        index: usize,
        replacement: Vec<u8>,
    ) -> Vec<u8> {
        let mut frames = parse_framed_message(raw, frame_count, max_bytes, "test").unwrap();
        let mut owned = frames.drain(..).map(ToOwned::to_owned).collect::<Vec<_>>();
        owned[index] = replacement;
        let fields = owned[1..].iter().map(Vec::as_slice).collect::<Vec<_>>();
        framed_message(&owned[0], &fields)
    }

    struct SyntheticRecord {
        s9_wire: Vec<u8>,
        s10_wire: Vec<u8>,
        claim: CaptureProvenanceClaimV1,
    }

    impl SyntheticRecord {
        fn refresh_bindings(&mut self) {
            let decoded_s9 = decode_s9_wire(&self.s9_wire).unwrap();
            let decoded_s10 = decode_s10_wire(&self.s10_wire).unwrap();
            self.claim.object_size =
                u64::try_from(self.s9_wire.len() + self.s10_wire.len()).unwrap();
            self.claim.raw_object_sha256 =
                framed_digest(RAW_OBJECT_DOMAIN, &[&self.s9_wire, &self.s10_wire]);
            self.claim.s9_wire_len = u64::try_from(self.s9_wire.len()).unwrap();
            self.claim.s9_wire_sha256 = decoded_s9.wire_sha256;
            self.claim.s10_wire_len = u64::try_from(self.s10_wire.len()).unwrap();
            self.claim.s10_wire_sha256 = decoded_s10.wire_sha256;
            self.claim.s13_envelope_sha256 = decoded_s9.envelope.envelope_sha256;
            self.claim.s9_request_sha256 = decoded_s9.request_sha256;
            self.claim.s9_decision_message_sha256 = decoded_s9.decision_message_sha256;
            self.claim.s10_query_sha256 = decoded_s10.query_sha256;
            self.claim.s10_observation_message_sha256 = decoded_s10.observation_message_sha256;
        }

        fn materialize(&self) -> (Vec<u8>, Vec<u8>, [u8; 64]) {
            let provenance = capture_provenance_message(&self.claim).unwrap();
            let source_signature: [u8; 64] = source_key_pair()
                .sign(&provenance)
                .as_ref()
                .try_into()
                .unwrap();
            let record = framed_message(
                SOURCE_RECORD_DOMAIN,
                &[
                    POLICY_ID.as_bytes(),
                    PROFILE.as_bytes(),
                    SOURCE_RECORD_SCHEMA_ID.as_bytes(),
                    &S13_CONTRACT_SHA256,
                    &self.s9_wire,
                    &self.s10_wire,
                    &provenance,
                    &source_signature,
                ],
            );
            (record, provenance, source_signature)
        }
    }

    struct SourceFixture {
        base: Fixture,
        s10_permit: ExternalOperationRecoveryTrustPermitV1,
        record: SyntheticRecord,
    }

    fn source_fixture() -> SourceFixture {
        let base = s12_fixture();
        let s10 = s10_inputs(&base.s9_request, &base.s9_decision);
        let s9_wire = s9_wire(
            &base.s9_request_bytes,
            &base.s9_decision_bytes,
            &base.s9_decision.ed25519_signature,
        );
        let s10_wire = s10_wire(&s10.query, &s10.observation);
        let decoded_s9 = decode_s9_wire(&s9_wire).unwrap();
        let decoded_s10 = decode_s10_wire(&s10_wire).unwrap();
        let claim = CaptureProvenanceClaimV1 {
            source_profile_id: "durable-source-profile-a".into(),
            source_namespace_id: "durable-source-namespace-a".into(),
            tenant_id: base.s9_request.tenant_id.clone(),
            audience: base.s9_request.audience.clone(),
            source_cluster_id: "durable-source-cluster-a".into(),
            source_incarnation: repeated(0x81),
            source_generation_id: repeated(0x82),
            object_id: repeated(0x83),
            object_revision: 17,
            object_size: u64::try_from(s9_wire.len() + s10_wire.len()).unwrap(),
            raw_object_sha256: framed_digest(RAW_OBJECT_DOMAIN, &[&s9_wire, &s10_wire]),
            s9_wire_len: u64::try_from(s9_wire.len()).unwrap(),
            s9_wire_sha256: decoded_s9.wire_sha256,
            s10_wire_len: u64::try_from(s10_wire.len()).unwrap(),
            s10_wire_sha256: decoded_s10.wire_sha256,
            s13_envelope_sha256: decoded_s9.envelope.envelope_sha256,
            s9_request_sha256: decoded_s9.request_sha256,
            s9_decision_message_sha256: decoded_s9.decision_message_sha256,
            s10_query_sha256: decoded_s10.query_sha256,
            s10_observation_message_sha256: decoded_s10.observation_message_sha256,
            capture_id: repeated(0x84),
            capture_sequence: 1,
            producer_identity_sha256: repeated(0x85),
            build_identity_sha256: repeated(0x86),
            capture_policy_sha256: repeated(0x87),
            previous_receipt_sha256: [0; 32],
            signer_key_id: "capture-signer-a".into(),
            signer_key_version: 2,
        };
        SourceFixture {
            base,
            s10_permit: s10.permit,
            record: SyntheticRecord {
                s9_wire,
                s10_wire,
                claim,
            },
        }
    }

    fn lookup_for(
        claim: &CaptureProvenanceClaimV1,
        record_sha256: [u8; 32],
    ) -> ExactRecoveredEnvelopeLookupV1 {
        ExactRecoveredEnvelopeLookupV1::try_new(
            claim.source_profile_id.clone(),
            claim.source_namespace_id.clone(),
            claim.tenant_id.clone(),
            claim.audience.clone(),
            claim.source_cluster_id.clone(),
            claim.source_incarnation,
            claim.source_generation_id,
            claim.object_id,
            claim.object_revision,
            record_sha256,
        )
        .unwrap()
    }

    fn source_permit_for(
        claim: &CaptureProvenanceClaimV1,
    ) -> ExternalRecoveredEnvelopeSourceTrustPermitV1 {
        ExternalRecoveredEnvelopeSourceTrustPermitV1::test_only_new(
            claim.source_profile_id.clone(),
            claim.source_namespace_id.clone(),
            claim.tenant_id.clone(),
            claim.audience.clone(),
            claim.source_cluster_id.clone(),
            claim.source_incarnation,
            claim.source_generation_id,
            claim.signer_key_id.clone(),
            claim.signer_key_version,
            claim.capture_policy_sha256,
            claim.object_revision,
            source_public_key(),
        )
    }

    struct SyntheticSource {
        bytes: RefCell<Option<Vec<u8>>>,
        reads: Cell<usize>,
        chunk_size: usize,
    }

    impl SyntheticSource {
        fn new(bytes: Vec<u8>, chunk_size: usize) -> Self {
            Self {
                bytes: RefCell::new(Some(bytes)),
                reads: Cell::new(0),
                chunk_size,
            }
        }
    }

    impl recovered_source_seal::Sealed for SyntheticSource {}

    impl ExternalRecoveredEnvelopeSourceV1 for SyntheticSource {
        fn read_exact(
            &self,
            _lookup: &ExactRecoveredEnvelopeLookupV1,
            sink: &mut BoundedRecoveredSourceRecordV1,
        ) -> Result<(), ExternalRecoveredEnvelopeSourceFailureV1> {
            self.reads.set(self.reads.get() + 1);
            let bytes = self
                .bytes
                .borrow_mut()
                .take()
                .ok_or(ExternalRecoveredEnvelopeSourceFailureV1::NotFound)?;
            for chunk in bytes.chunks(self.chunk_size.max(1)) {
                sink.push_chunk(chunk)
                    .map_err(|_| ExternalRecoveredEnvelopeSourceFailureV1::Malformed)?;
            }
            Ok(())
        }
    }

    fn run_fixture(
        fixture: &SourceFixture,
    ) -> (SourceResult<SourcedHistoricalRecoveredEnvelopeV1>, usize) {
        let (record, _, _) = fixture.record.materialize();
        let lookup = lookup_for(&fixture.record.claim, sha256_bytes(&record));
        let permit = source_permit_for(&fixture.record.claim);
        let source = SyntheticSource::new(record, 113);
        let result = recover_historical_from_external_source_v1(
            &source,
            lookup,
            &permit,
            &fixture.base.s9_permit,
            &fixture.s10_permit,
            &fixture.base.s11_request,
            &fixture.base.s11_permit,
            &fixture.base.s11_record,
        );
        (result, source.reads.get())
    }

    #[test]
    fn s14_known_answer_record_provenance_and_historical_chains_are_stable() {
        let fixture = source_fixture();
        let (record, provenance, signature) = fixture.record.materialize();
        let (result, reads) = run_fixture(&fixture);
        let result = result.unwrap();
        assert_eq!(reads, 1);
        assert_eq!(
            encode(&source_public_key()),
            "278117fc144c72340f67d0f2316e8386ceffbf2b2428c9c51fef7c597f1d426e"
        );
        assert_eq!(
            encode(&fixture.record.claim.s13_envelope_sha256),
            "5d74c7a300abe503b9a79c796394faa23de0c64f22fb80902294fa0654ee15d9"
        );
        assert_eq!(
            encode(&result.historical_chain_sha256),
            "afb8aa4945f0e491937f75233c621d52f1bcc1307e6d497352fd9d0fc79b7204"
        );
        assert_eq!(fixture.record.s9_wire.len(), 1_970);
        assert_eq!(
            encode(&sha256_bytes(&fixture.record.s9_wire)),
            "c850a905563c7f67d8cf145b65619deb89780cfca12baa8a70b8a1856e27bfcd"
        );
        assert_eq!(fixture.record.s10_wire.len(), 1_898);
        assert_eq!(
            encode(&sha256_bytes(&fixture.record.s10_wire)),
            "61e4decbd7bb4cc6025f459e41c451d30124b084a2afaa20b2fe356eb259808e"
        );
        let s10_frames = parse_framed_message(
            &fixture.record.s10_wire,
            S10_WIRE_FRAME_COUNT,
            MAX_S10_WIRE_BYTES,
            "test",
        )
        .unwrap();
        assert_eq!(s10_frames[7].len(), 687);
        assert_eq!(
            encode(&sha256_bytes(s10_frames[7])),
            "18c188cbab81cb121582ffc509344400948009b65f1bb5dd148e35f5e9f33bdc"
        );
        assert_eq!(s10_frames[8].len(), 733);
        assert_eq!(
            encode(&sha256_bytes(s10_frames[8])),
            "22e256669c2be1b4ebfe49a20157be7fd76c4156a685b920eda30894222c219f"
        );
        assert_eq!(provenance.len(), 1_206);
        assert_eq!(
            encode(&sha256_bytes(&provenance)),
            "e7a90fa8f378e8d8dfa1d3cedf9d8db73167f729357aecb003ffac93138ab52e"
        );
        assert_eq!(
            encode(&signature),
            "04dcefbc132d5b018334d841056171845db0c6070e4eb7159646ba99d3346ba1784ff7b9acf30b9737c82643961cd505cf9d15dfce055c0748e6124594bb340e"
        );
        assert_eq!(record.len(), 5_494);
        assert_eq!(
            encode(&sha256_bytes(&record)),
            "a788ec43fefa76e393d77c86bbfabeef7d2ae8c5499bb834c1945af5cbb1b3cd"
        );
        assert_eq!(result.record_sha256, sha256_bytes(&record));
        assert_eq!(result.provenance_message_sha256, sha256_bytes(&provenance));
        assert_eq!(
            encode(&result.historical_source_chain_sha256),
            "d29da2a081b09b2b124298eae40b15ada555196cc5e3fd52d8e4dfadf3f2149b"
        );
    }

    #[test]
    fn s14_exact_source_is_read_once_into_one_owned_snapshot() {
        let fixture = source_fixture();
        let (record, _, _) = fixture.record.materialize();
        let lookup = lookup_for(&fixture.record.claim, sha256_bytes(&record));
        let permit = source_permit_for(&fixture.record.claim);
        let source = SyntheticSource::new(record, 1);
        let result = recover_historical_from_external_source_v1(
            &source,
            lookup,
            &permit,
            &fixture.base.s9_permit,
            &fixture.s10_permit,
            &fixture.base.s11_request,
            &fixture.base.s11_permit,
            &fixture.base.s11_record,
        );
        assert!(result.is_ok());
        assert_eq!(source.reads.get(), 1);
    }

    #[test]
    fn s14_repeated_record_can_be_reverified_and_is_not_a_replay_fence() {
        let fixture = source_fixture();
        let first = run_fixture(&fixture).0.unwrap();
        let second = run_fixture(&fixture).0.unwrap();
        assert_eq!(
            first.historical_source_chain_sha256,
            second.historical_source_chain_sha256
        );
        assert_eq!(
            first.historical_chain_sha256,
            second.historical_chain_sha256
        );
    }

    #[test]
    fn s14_ingress_accepts_exact_cap_and_rejects_max_plus_one_before_extend() {
        let mut sink = BoundedRecoveredSourceRecordV1::new();
        sink.push_chunk(&vec![0x55; MAX_SOURCE_RECORD_BYTES])
            .unwrap();
        assert_eq!(sink.bytes.len(), MAX_SOURCE_RECORD_BYTES);
        assert_eq!(
            sink.push_chunk(&[0]).unwrap_err().code(),
            "track_b_recovered_envelope_source_v1_ingress_bounds"
        );
        assert_eq!(sink.bytes.len(), MAX_SOURCE_RECORD_BYTES);
    }

    struct FailureSource {
        mode: usize,
        reads: Cell<usize>,
    }

    impl recovered_source_seal::Sealed for FailureSource {}

    impl ExternalRecoveredEnvelopeSourceV1 for FailureSource {
        fn read_exact(
            &self,
            _lookup: &ExactRecoveredEnvelopeLookupV1,
            _sink: &mut BoundedRecoveredSourceRecordV1,
        ) -> Result<(), ExternalRecoveredEnvelopeSourceFailureV1> {
            self.reads.set(self.reads.get() + 1);
            Err(match self.mode {
                0 => ExternalRecoveredEnvelopeSourceFailureV1::NotFound,
                1 => ExternalRecoveredEnvelopeSourceFailureV1::Pending,
                2 => ExternalRecoveredEnvelopeSourceFailureV1::Conflict,
                3 => ExternalRecoveredEnvelopeSourceFailureV1::Stale,
                4 => ExternalRecoveredEnvelopeSourceFailureV1::Rollback,
                5 => ExternalRecoveredEnvelopeSourceFailureV1::Unavailable,
                6 => ExternalRecoveredEnvelopeSourceFailureV1::Unauthenticated,
                7 => ExternalRecoveredEnvelopeSourceFailureV1::Malformed,
                _ => ExternalRecoveredEnvelopeSourceFailureV1::Indeterminate,
            })
        }
    }

    #[test]
    fn s14_every_source_failure_is_one_read_no_retry_no_fallback() {
        for mode in 0..9 {
            let fixture = source_fixture();
            let (record, _, _) = fixture.record.materialize();
            let lookup = lookup_for(&fixture.record.claim, sha256_bytes(&record));
            let permit = source_permit_for(&fixture.record.claim);
            let source = FailureSource {
                mode,
                reads: Cell::new(0),
            };
            let error = recover_historical_from_external_source_v1(
                &source,
                lookup,
                &permit,
                &fixture.base.s9_permit,
                &fixture.s10_permit,
                &fixture.base.s11_request,
                &fixture.base.s11_permit,
                &fixture.base.s11_record,
            )
            .unwrap_err();
            assert_eq!(
                error.code(),
                "track_b_recovered_envelope_source_v1_source_read"
            );
            assert_eq!(source.reads.get(), 1);
        }
    }

    #[test]
    fn s14_record_digest_mismatch_rejects_before_decode() {
        let fixture = source_fixture();
        let (record, _, _) = fixture.record.materialize();
        let mut wrong = sha256_bytes(&record);
        wrong[0] ^= 1;
        let lookup = lookup_for(&fixture.record.claim, wrong);
        let permit = source_permit_for(&fixture.record.claim);
        assert_eq!(
            decode_and_verify_source_record_v1(&record, &lookup, &permit)
                .unwrap_err()
                .code(),
            "track_b_recovered_envelope_source_v1_record_digest"
        );
    }

    #[test]
    fn s14_every_record_truncation_and_trailing_byte_rejects() {
        let fixture = source_fixture();
        let (record, _, _) = fixture.record.materialize();
        let permit = source_permit_for(&fixture.record.claim);
        for end in 0..record.len() {
            let truncated = &record[..end];
            if truncated.is_empty() {
                continue;
            }
            let lookup = lookup_for(&fixture.record.claim, sha256_bytes(truncated));
            assert!(decode_and_verify_source_record_v1(truncated, &lookup, &permit).is_err());
        }
        let mut trailing = record;
        trailing.push(0);
        let lookup = lookup_for(&fixture.record.claim, sha256_bytes(&trailing));
        assert_eq!(
            decode_and_verify_source_record_v1(&trailing, &lookup, &permit)
                .unwrap_err()
                .code(),
            "track_b_recovered_envelope_source_v1_record_framing"
        );
    }

    #[test]
    fn s14_record_duplicate_reordered_or_unknown_frame_rejects() {
        let fixture = source_fixture();
        let (record, _, _) = fixture.record.materialize();
        let permit = source_permit_for(&fixture.record.claim);
        let duplicate = replace_frame(
            &record,
            SOURCE_RECORD_FRAME_COUNT,
            MAX_SOURCE_RECORD_BYTES,
            6,
            fixture.record.s9_wire.clone(),
        );
        let lookup = lookup_for(&fixture.record.claim, sha256_bytes(&duplicate));
        assert!(decode_and_verify_source_record_v1(&duplicate, &lookup, &permit).is_err());

        let frames = parse_framed_message(
            &record,
            SOURCE_RECORD_FRAME_COUNT,
            MAX_SOURCE_RECORD_BYTES,
            "test",
        )
        .unwrap();
        let reordered = framed_message(
            frames[0],
            &[
                frames[1], frames[2], frames[3], frames[4], frames[6], frames[5], frames[7],
                frames[8],
            ],
        );
        let lookup = lookup_for(&fixture.record.claim, sha256_bytes(&reordered));
        assert!(decode_and_verify_source_record_v1(&reordered, &lookup, &permit).is_err());

        let mut unknown = record;
        append_frame(&mut unknown, b"UNKNOWN");
        let lookup = lookup_for(&fixture.record.claim, sha256_bytes(&unknown));
        assert!(decode_and_verify_source_record_v1(&unknown, &lookup, &permit).is_err());
    }

    #[test]
    fn s14_length_prefix_overflow_zero_and_remaining_bounds_reject() {
        for length in [0u64, u64::MAX, 1024] {
            let mut raw = Vec::new();
            raw.extend_from_slice(&length.to_be_bytes());
            if length == 1024 {
                raw.push(1);
            }
            assert!(parse_framed_message(&raw, 1, 2048, "test").is_err());
        }
    }

    #[test]
    fn s14_label_128_passes_and_129_or_nonascii_rejects_before_string_allocation() {
        let valid = [b'a'; MAX_LABEL_BYTES];
        assert_eq!(decode_label(&valid, "test").unwrap().len(), MAX_LABEL_BYTES);
        assert!(decode_label(&[b'a'; MAX_LABEL_BYTES + 1], "test").is_err());
        assert!(decode_label(&[0xff], "test").is_err());
        assert!(decode_label(b"Uppercase", "test").is_err());
    }

    #[test]
    fn s14_fixed_width_and_signature_63_65_reject() {
        assert!(decode_fixed::<32>(&[0; 31], "test").is_err());
        assert!(decode_fixed::<32>(&[0; 33], "test").is_err());
        assert!(decode_fixed::<64>(&[0; 63], "test").is_err());
        assert!(decode_fixed::<64>(&[0; 65], "test").is_err());
        assert!(decode_u64(&[0; 7], "test").is_err());
        assert!(decode_u64(&[0; 9], "test").is_err());
    }

    #[test]
    fn s14_s9_and_s10_inner_truncation_or_append_rejects() {
        let fixture = source_fixture();
        let frames = parse_framed_message(
            &fixture.record.s9_wire,
            S9_WIRE_FRAME_COUNT,
            MAX_S9_WIRE_BYTES,
            "test",
        )
        .unwrap();
        let s9_signature = decode_fixed(frames[11], "test").unwrap();
        assert!(decode_s9_request_message(&frames[9][..frames[9].len() - 1]).is_err());
        assert!(
            decode_s9_decision_message(&frames[10][..frames[10].len() - 1], s9_signature).is_err()
        );
        let mut appended_request = frames[9].to_vec();
        appended_request.push(0);
        assert!(decode_s9_request_message(&appended_request).is_err());
        let mut appended_decision = frames[10].to_vec();
        appended_decision.push(0);
        assert!(decode_s9_decision_message(&appended_decision, s9_signature).is_err());

        let aliased_s9_schema = replace_frame(
            &fixture.record.s9_wire,
            S9_WIRE_FRAME_COUNT,
            MAX_S9_WIRE_BYTES,
            3,
            b"alias".to_vec(),
        );
        assert!(decode_s9_wire(&aliased_s9_schema).is_err());
        let lowercase_s9_state = replace_frame(
            frames[10],
            S9_DECISION_FRAME_COUNT,
            MAX_CANONICAL_MESSAGE_BYTES,
            5,
            b"active".to_vec(),
        );
        assert!(decode_s9_decision_message(&lowercase_s9_state, s9_signature).is_err());
        let s10_frames = parse_framed_message(
            &fixture.record.s10_wire,
            S10_WIRE_FRAME_COUNT,
            MAX_S10_WIRE_BYTES,
            "test",
        )
        .unwrap();
        assert!(decode_s10_query_message(&s10_frames[7][..s10_frames[7].len() - 1]).is_err());
        let s10_signature = decode_fixed(s10_frames[9], "test").unwrap();
        assert!(decode_s10_observation_message(
            &s10_frames[8][..s10_frames[8].len() - 1],
            s10_signature
        )
        .is_err());
        let mut appended_query = s10_frames[7].to_vec();
        appended_query.push(0);
        assert!(decode_s10_query_message(&appended_query).is_err());
        let mut appended_observation = s10_frames[8].to_vec();
        appended_observation.push(0);
        assert!(decode_s10_observation_message(&appended_observation, s10_signature).is_err());

        let aliased_s10_schema = replace_frame(
            &fixture.record.s10_wire,
            S10_WIRE_FRAME_COUNT,
            MAX_S10_WIRE_BYTES,
            3,
            b"alias".to_vec(),
        );
        assert!(decode_s10_wire(&aliased_s10_schema).is_err());
        let lowercase_s10_state = replace_frame(
            s10_frames[8],
            S10_OBSERVATION_FRAME_COUNT,
            MAX_CANONICAL_MESSAGE_BYTES,
            6,
            b"committed".to_vec(),
        );
        assert!(decode_s10_observation_message(&lowercase_s10_state, s10_signature).is_err());
    }

    #[test]
    fn s14_invalid_source_permit_metadata_and_revision_floor_reject() {
        let fixture = source_fixture();
        let (record, _, _) = fixture.record.materialize();
        let lookup = lookup_for(&fixture.record.claim, sha256_bytes(&record));

        let mut invalid_permits = Vec::new();
        let mut permit = source_permit_for(&fixture.record.claim);
        permit.source_profile_id.clear();
        invalid_permits.push(permit);
        let mut permit = source_permit_for(&fixture.record.claim);
        permit.source_incarnation = [0; 32];
        invalid_permits.push(permit);
        let mut permit = source_permit_for(&fixture.record.claim);
        permit.source_generation_id = [0; 32];
        invalid_permits.push(permit);
        let mut permit = source_permit_for(&fixture.record.claim);
        permit.signer_key_version = 0;
        invalid_permits.push(permit);
        let mut permit = source_permit_for(&fixture.record.claim);
        permit.capture_policy_sha256 = [0; 32];
        invalid_permits.push(permit);
        let mut permit = source_permit_for(&fixture.record.claim);
        permit.minimum_object_revision = 0;
        invalid_permits.push(permit);
        let mut permit = source_permit_for(&fixture.record.claim);
        permit.ed25519_public_key = [0; 32];
        invalid_permits.push(permit);

        for permit in invalid_permits {
            assert_eq!(
                decode_and_verify_source_record_v1(&record, &lookup, &permit)
                    .unwrap_err()
                    .code(),
                "track_b_recovered_envelope_source_v1_source_permit"
            );
        }

        let mut permit = source_permit_for(&fixture.record.claim);
        permit.minimum_object_revision = fixture.record.claim.object_revision + 1;
        assert_eq!(
            decode_and_verify_source_record_v1(&record, &lookup, &permit)
                .unwrap_err()
                .code(),
            "track_b_recovered_envelope_source_v1_source_scope"
        );
    }

    #[test]
    fn s14_provenance_exact_framing_sequence_and_evidence_caps_reject() {
        let fixture = source_fixture();
        let (_, provenance, _) = fixture.record.materialize();

        assert!(decode_capture_provenance_message(&provenance[..provenance.len() - 1]).is_err());
        let mut trailing = provenance.clone();
        trailing.push(0);
        assert!(decode_capture_provenance_message(&trailing).is_err());
        let mut extra_frame = provenance.clone();
        append_frame(&mut extra_frame, b"extra");
        assert!(decode_capture_provenance_message(&extra_frame).is_err());
        let aliased_schema = replace_frame(
            &provenance,
            CAPTURE_PROVENANCE_FRAME_COUNT,
            MAX_PROVENANCE_MESSAGE_BYTES,
            3,
            b"alias".to_vec(),
        );
        assert!(decode_capture_provenance_message(&aliased_schema).is_err());

        let mut invalid_sequence = fixture.record.claim;
        invalid_sequence.previous_receipt_sha256 = repeated(0x99);
        assert!(capture_provenance_message(&invalid_sequence).is_err());
        invalid_sequence.capture_sequence = 2;
        invalid_sequence.previous_receipt_sha256 = [0; 32];
        assert!(capture_provenance_message(&invalid_sequence).is_err());

        let oversized_s9_component = replace_frame(
            &fixture.record.s9_wire,
            S9_WIRE_FRAME_COUNT,
            MAX_S9_WIRE_BYTES,
            9,
            vec![b'a'; MAX_EVIDENCE_COMPONENT_BYTES],
        );
        assert_eq!(
            decode_s9_wire(&oversized_s9_component)
                .err()
                .unwrap()
                .code(),
            "track_b_recovered_envelope_source_v1_s9_wire_bounds"
        );
        let oversized_s10_component = replace_frame(
            &fixture.record.s10_wire,
            S10_WIRE_FRAME_COUNT,
            MAX_S10_WIRE_BYTES,
            7,
            vec![b'a'; MAX_EVIDENCE_COMPONENT_BYTES],
        );
        assert_eq!(
            decode_s10_wire(&oversized_s10_component)
                .err()
                .unwrap()
                .code(),
            "track_b_recovered_envelope_source_v1_s10_wire_bounds"
        );
    }

    #[test]
    fn s14_schema_policy_profile_or_contract_drift_rejects() {
        let fixture = source_fixture();
        for index in 1..=4 {
            let tampered = replace_frame(
                &fixture.record.materialize().0,
                SOURCE_RECORD_FRAME_COUNT,
                MAX_SOURCE_RECORD_BYTES,
                index,
                b"drift".to_vec(),
            );
            let lookup = lookup_for(&fixture.record.claim, sha256_bytes(&tampered));
            let permit = source_permit_for(&fixture.record.claim);
            assert_eq!(
                decode_and_verify_source_record_v1(&tampered, &lookup, &permit)
                    .unwrap_err()
                    .code(),
                "track_b_recovered_envelope_source_v1_record_identity"
            );
        }
    }

    #[test]
    fn s14_source_signature_tamper_and_wrong_public_key_reject() {
        let fixture = source_fixture();
        let (record, _, mut signature) = fixture.record.materialize();
        signature[0] ^= 1;
        let tampered = replace_frame(
            &record,
            SOURCE_RECORD_FRAME_COUNT,
            MAX_SOURCE_RECORD_BYTES,
            8,
            signature.to_vec(),
        );
        let lookup = lookup_for(&fixture.record.claim, sha256_bytes(&tampered));
        let permit = source_permit_for(&fixture.record.claim);
        assert_eq!(
            decode_and_verify_source_record_v1(&tampered, &lookup, &permit)
                .unwrap_err()
                .code(),
            "track_b_recovered_envelope_source_v1_source_signature"
        );

        let (record, _, _) = fixture.record.materialize();
        let lookup = lookup_for(&fixture.record.claim, sha256_bytes(&record));
        let mut wrong_permit = source_permit_for(&fixture.record.claim);
        wrong_permit.ed25519_public_key[0] ^= 1;
        assert_eq!(
            decode_and_verify_source_record_v1(&record, &lookup, &wrong_permit)
                .unwrap_err()
                .code(),
            "track_b_recovered_envelope_source_v1_source_signature"
        );
    }

    #[test]
    fn s14_lookup_or_source_permit_scope_substitution_rejects() {
        let fixture = source_fixture();
        let (record, _, _) = fixture.record.materialize();
        let mut lookup = lookup_for(&fixture.record.claim, sha256_bytes(&record));
        lookup.object_id[0] ^= 1;
        let permit = source_permit_for(&fixture.record.claim);
        assert_eq!(
            decode_and_verify_source_record_v1(&record, &lookup, &permit)
                .unwrap_err()
                .code(),
            "track_b_recovered_envelope_source_v1_source_scope"
        );

        let lookup = lookup_for(&fixture.record.claim, sha256_bytes(&record));
        let mut permit = source_permit_for(&fixture.record.claim);
        permit.signer_key_version += 1;
        assert_eq!(
            decode_and_verify_source_record_v1(&record, &lookup, &permit)
                .unwrap_err()
                .code(),
            "track_b_recovered_envelope_source_v1_source_scope"
        );
    }

    #[test]
    fn s14_resigned_provenance_semantic_mismatch_still_rejects() {
        let mut fixture = source_fixture();
        fixture.record.claim.s9_request_sha256[0] ^= 1;
        let (record, _, _) = fixture.record.materialize();
        let lookup = lookup_for(&fixture.record.claim, sha256_bytes(&record));
        let permit = source_permit_for(&fixture.record.claim);
        assert_eq!(
            decode_and_verify_source_record_v1(&record, &lookup, &permit)
                .unwrap_err()
                .code(),
            "track_b_recovered_envelope_source_v1_capture_binding"
        );
    }

    #[test]
    fn s14_validly_resigned_cross_fixture_s9_s10_mix_fails_final_cross_binding() {
        let mut mixed = source_fixture();
        assert!(verify_external_currentness_decision_v1(
            &mixed.base.s9_request,
            &mixed.base.s9_permit,
            &mixed.base.s9_decision
        )
        .is_ok());

        let mut independent_s10 = s10_inputs(&mixed.base.s9_request, &mixed.base.s9_decision);
        independent_s10.query.original_operation_id = repeated(0x91);
        independent_s10.observation.original_operation_id = repeated(0x91);
        independent_s10.observation.lookup_query_sha256 =
            lookup_query_digest(&independent_s10.query).unwrap();
        independent_s10.observation.result_id = result_id(
            &independent_s10.query,
            independent_s10.observation.operation_committed_revision,
            &independent_s10.observation.journal_generation_id,
            independent_s10.observation.journal_record_sequence,
            &independent_s10.observation.original_decision_sha256,
        );
        resign_s10(&mut independent_s10.observation);
        assert!(verify_external_operation_recovery_observation_v1(
            &independent_s10.query,
            &independent_s10.permit,
            &independent_s10.observation
        )
        .is_ok());

        mixed.record.s10_wire = s10_wire(&independent_s10.query, &independent_s10.observation);
        mixed.record.refresh_bindings();
        mixed.s10_permit = independent_s10.permit;

        let (record, _, _) = mixed.record.materialize();
        let lookup = lookup_for(&mixed.record.claim, sha256_bytes(&record));
        let permit = source_permit_for(&mixed.record.claim);
        let decoded = decode_and_verify_source_record_v1(&record, &lookup, &permit).unwrap();
        assert_eq!(
            decoded
                .consume_historical(
                    &mixed.base.s9_permit,
                    &mixed.s10_permit,
                    &mixed.base.s11_request,
                    &mixed.base.s11_permit,
                    &mixed.base.s11_record,
                )
                .unwrap_err()
                .code(),
            "track_b_recovered_envelope_source_v1_local_reverification"
        );
    }

    #[test]
    fn s14_s9_or_s10_signature_tamper_can_be_captured_but_not_locally_verified() {
        let mut s9_fixture = source_fixture();
        let s9_frames = parse_framed_message(
            &s9_fixture.record.s9_wire,
            S9_WIRE_FRAME_COUNT,
            MAX_S9_WIRE_BYTES,
            "test",
        )
        .unwrap();
        let mut s9_signature = s9_frames[11].to_vec();
        s9_signature[0] ^= 1;
        s9_fixture.record.s9_wire = replace_frame(
            &s9_fixture.record.s9_wire,
            S9_WIRE_FRAME_COUNT,
            MAX_S9_WIRE_BYTES,
            11,
            s9_signature,
        );
        s9_fixture.record.refresh_bindings();
        assert_eq!(
            run_fixture(&s9_fixture).0.unwrap_err().code(),
            "track_b_recovered_envelope_source_v1_local_reverification"
        );

        let mut s10_fixture = source_fixture();
        let s10_frames = parse_framed_message(
            &s10_fixture.record.s10_wire,
            S10_WIRE_FRAME_COUNT,
            MAX_S10_WIRE_BYTES,
            "test",
        )
        .unwrap();
        let mut s10_signature = s10_frames[9].to_vec();
        s10_signature[0] ^= 1;
        s10_fixture.record.s10_wire = replace_frame(
            &s10_fixture.record.s10_wire,
            S10_WIRE_FRAME_COUNT,
            MAX_S10_WIRE_BYTES,
            9,
            s10_signature,
        );
        s10_fixture.record.refresh_bindings();
        assert_eq!(
            run_fixture(&s10_fixture).0.unwrap_err().code(),
            "track_b_recovered_envelope_source_v1_local_reverification"
        );
    }

    #[test]
    fn s14_noncommitted_s10_is_strictly_decodable_but_fails_local_reverification() {
        let mut fixture = source_fixture();
        let decoded = decode_s10_wire(&fixture.record.s10_wire).unwrap();
        let mut observation = decoded.observation;
        observation.state = ExternalOperationRecoveryStateV1::Pending;
        resign_s10(&mut observation);
        fixture.record.s10_wire = s10_wire(&decoded.query, &observation);
        fixture.record.refresh_bindings();
        assert_eq!(
            run_fixture(&fixture).0.unwrap_err().code(),
            "track_b_recovered_envelope_source_v1_local_reverification"
        );
    }

    #[test]
    fn s14_two_signed_same_revision_objects_show_no_equivocation_or_rollback_proof() {
        let first = source_fixture();
        let first_result = run_fixture(&first).0.unwrap();
        let mut second = source_fixture();
        second.record.claim.capture_id[0] ^= 1;
        let second_result = run_fixture(&second).0.unwrap();
        assert_eq!(
            first_result.historical_chain_sha256,
            second_result.historical_chain_sha256
        );
        assert_ne!(
            first_result.historical_source_chain_sha256,
            second_result.historical_source_chain_sha256
        );

        let mut later = source_fixture();
        later.record.claim.object_revision += 1;
        later.record.claim.capture_sequence = 2;
        later.record.claim.previous_receipt_sha256 = repeated(0x91);
        assert_eq!(
            run_fixture(&later).0.unwrap().historical_chain_sha256,
            first_result.historical_chain_sha256
        );
    }

    #[test]
    fn s14_mixed_snapshot_toctou_bytes_reject() {
        let first = source_fixture();
        let mut second = source_fixture();
        second.record.claim.capture_id[0] ^= 1;
        let (first_record, _, _) = first.record.materialize();
        let (second_record, _, _) = second.record.materialize();
        let split = first_record.len() / 2;
        let mut mixed = first_record[..split].to_vec();
        mixed.extend_from_slice(&second_record[split..]);
        let lookup = lookup_for(&first.record.claim, sha256_bytes(&first_record));
        let permit = source_permit_for(&first.record.claim);
        assert_eq!(
            decode_and_verify_source_record_v1(&mixed, &lookup, &permit)
                .unwrap_err()
                .code(),
            "track_b_recovered_envelope_source_v1_record_digest"
        );
    }

    #[test]
    fn s14_debug_and_source_keep_every_capability_private_and_detached() {
        let fixture = source_fixture();
        let (record, _, _) = fixture.record.materialize();
        let lookup = lookup_for(&fixture.record.claim, sha256_bytes(&record));
        let permit = source_permit_for(&fixture.record.claim);
        let decoded = decode_and_verify_source_record_v1(&record, &lookup, &permit).unwrap();
        for debug in [
            format!("{lookup:?}"),
            format!("{permit:?}"),
            format!("{:?}", fixture.record.claim),
            format!("{decoded:?}"),
        ] {
            assert!(!debug.contains("durable-source-profile-a"));
            assert!(!debug.contains("capture-signer-a"));
            assert!(!debug.contains(&encode(&fixture.record.claim.capture_id)));
        }

        let source = include_str!("recovered_envelope_source.rs");
        let production = source.split("\n#[cfg(test)]\nmod tests").next().unwrap();
        assert!(!production.contains("serde::"));
        assert!(!production.contains("Serialize"));
        assert!(!production.contains("Deserialize"));
        assert!(!production.contains("#[derive(Clone"));
        assert!(!production.contains("std::fs"));
        assert!(!production.contains("reqwest"));
        assert!(!production.contains("tokio"));
        assert!(!production.contains("StateStore"));
        assert!(!production.contains("Bridge"));
        assert!(!production.contains("SystemTime"));
        assert!(!production.contains(".lookup_operation("));
        assert!(!production.contains(".request_currentness("));
        assert!(!production.contains("fn latest"));
        assert!(!production.contains(".latest("));
        assert!(!production.contains("fn retry"));
        assert!(!production.contains(".retry("));
    }
}
