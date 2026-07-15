//! S13 private recovered-envelope delivery preregistration.
//!
//! The owned carrier below is structural input, not authenticated evidence. A
//! consuming handoff verifies its owned S10 observation, keeps the resulting
//! projection lexical to one call, and immediately invokes the S12 historical
//! verifier. It creates no transport, persistence, currentness, admission, or
//! downstream-action capability.

#![cfg_attr(not(test), allow(dead_code))]

use super::super::external_authority_operation_state_machine::{
    AtomicAuthorityOperationRequestV1, AtomicAuthorityOperationTrustPermitV1,
    SignedCommittedAuthorityOperationV1,
};
use super::super::external_operation_recovery::{
    verify_external_operation_recovery_observation_v1, ExternalOperationRecoveryQueryV1,
    ExternalOperationRecoveryTrustPermitV1, SignedExternalOperationRecoveryObservationV1,
};
use super::{
    framed_digest, s9_request_message, validated_s9_decision_message,
    verify_recovered_s9_decision_v1, ExternalAuthorityTrustPermitV1, ExternalCurrentnessRequestV1,
    PurelyReverifiedRecoveredS9DecisionV1, RecoveredS9DecisionBundleV1,
    SignedExternalCurrentnessDecisionV1, S10_CONTRACT_SHA256, S11_CONTRACT_SHA256,
    S9_CONTRACT_SHA256,
};
use std::fmt;

const POLICY_ID: &str = "agent-bridge/track-b/recovered-envelope-delivery/v1";
const PROFILE: &str =
    "OWNED_EXACT_S9_ENVELOPE_PLUS_LEXICAL_VERIFIED_S10_PROJECTION_HISTORICAL_ONLY";
const ENVELOPE_SCHEMA_ID: &str = "agent-bridge/track-b/recovered-s9-envelope/v1";
const ENVELOPE_DIGEST_DOMAIN: &[u8] =
    b"agent-bridge/track-b/recovered-envelope-delivery/envelope-digest/v1";
const MAX_MESSAGE_BYTES: usize = 64 * 1024;
const MAX_ENVELOPE_BYTES: usize = 128 * 1024;
const ED25519_SIGNATURE_BYTES: usize = 64;
const S12_CONTRACT_SHA256: [u8; 32] = [
    0x4e, 0xfa, 0x9d, 0xc5, 0x33, 0xcf, 0xca, 0x6c, 0x98, 0x47, 0x3a, 0xe2, 0x0c, 0xf8, 0xfc, 0x98,
    0x32, 0x92, 0x36, 0x2e, 0x92, 0xb6, 0x69, 0x57, 0x5a, 0x81, 0xe8, 0x0e, 0x18, 0x9b, 0x13, 0x03,
];

#[cfg(feature = "temporal-evidence-s14-recovered-envelope-source-synthetic")]
mod recovered_envelope_source;

#[derive(Debug, thiserror::Error)]
#[error("{code}: {detail}")]
struct RecoveredEnvelopeDeliveryV1Error {
    code: &'static str,
    detail: &'static str,
}

impl RecoveredEnvelopeDeliveryV1Error {
    #[cfg(test)]
    fn code(&self) -> &'static str {
        self.code
    }
}

type DeliveryResult<T> = Result<T, RecoveredEnvelopeDeliveryV1Error>;

fn delivery_error(code: &'static str, detail: &'static str) -> RecoveredEnvelopeDeliveryV1Error {
    RecoveredEnvelopeDeliveryV1Error { code, detail }
}

/// Owned but still untrusted structural input. Exact bytes and typed values
/// cannot be mutated after construction, and this carrier is deliberately not
/// cloneable or serializable.
#[must_use]
struct RecoveredS9EnvelopeV1 {
    request: ExternalCurrentnessRequestV1,
    canonical_request_bytes: Box<[u8]>,
    decision: SignedExternalCurrentnessDecisionV1,
    canonical_decision_message_bytes: Box<[u8]>,
    canonical_signature_bytes: Box<[u8]>,
    envelope_sha256: [u8; 32],
}

impl fmt::Debug for RecoveredS9EnvelopeV1 {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        formatter
            .debug_struct("RecoveredS9EnvelopeV1")
            .field(
                "scope",
                &"[OWNED_UNTRUSTED_STRUCTURAL_INPUT_BYTES_REDACTED]",
            )
            .finish_non_exhaustive()
    }
}

impl RecoveredS9EnvelopeV1 {
    fn try_new(
        request: ExternalCurrentnessRequestV1,
        canonical_request_bytes: Box<[u8]>,
        decision: SignedExternalCurrentnessDecisionV1,
        canonical_decision_message_bytes: Box<[u8]>,
        canonical_signature_bytes: Box<[u8]>,
    ) -> DeliveryResult<Self> {
        if canonical_request_bytes.is_empty()
            || canonical_request_bytes.len() > MAX_MESSAGE_BYTES
            || canonical_decision_message_bytes.is_empty()
            || canonical_decision_message_bytes.len() > MAX_MESSAGE_BYTES
        {
            return Err(delivery_error(
                "track_b_recovered_envelope_delivery_v1_component_bounds",
                "nonempty S9 request and decision messages must each fit the 64 KiB bound",
            ));
        }
        if canonical_signature_bytes.len() != ED25519_SIGNATURE_BYTES {
            return Err(delivery_error(
                "track_b_recovered_envelope_delivery_v1_signature_bounds",
                "the carried Ed25519 signature must be exactly 64 bytes",
            ));
        }
        let total_bytes = canonical_request_bytes
            .len()
            .checked_add(canonical_decision_message_bytes.len())
            .and_then(|size| size.checked_add(canonical_signature_bytes.len()))
            .ok_or_else(|| {
                delivery_error(
                    "track_b_recovered_envelope_delivery_v1_total_bounds",
                    "recovered-envelope byte count overflowed",
                )
            })?;
        if total_bytes > MAX_ENVELOPE_BYTES {
            return Err(delivery_error(
                "track_b_recovered_envelope_delivery_v1_total_bounds",
                "the complete recovered S9 envelope exceeds the 128 KiB bound",
            ));
        }

        let exact_request = s9_request_message(&request).map_err(|_| {
            delivery_error(
                "track_b_recovered_envelope_delivery_v1_typed_request",
                "the typed S9 request is malformed or noncanonical",
            )
        })?;
        if exact_request.as_slice() != canonical_request_bytes.as_ref() {
            return Err(delivery_error(
                "track_b_recovered_envelope_delivery_v1_request_bytes",
                "owned request bytes do not exactly equal the canonical typed S9 request",
            ));
        }
        let exact_decision = validated_s9_decision_message(&decision).map_err(|_| {
            delivery_error(
                "track_b_recovered_envelope_delivery_v1_typed_decision",
                "the typed S9 decision is malformed, oversized, or noncanonical",
            )
        })?;
        if exact_decision.as_slice() != canonical_decision_message_bytes.as_ref() {
            return Err(delivery_error(
                "track_b_recovered_envelope_delivery_v1_decision_bytes",
                "owned decision bytes do not exactly equal the canonical typed S9 decision message",
            ));
        }
        if &decision.ed25519_signature[..] != canonical_signature_bytes.as_ref() {
            return Err(delivery_error(
                "track_b_recovered_envelope_delivery_v1_signature_bytes",
                "owned signature bytes do not exactly equal the typed S9 signature",
            ));
        }

        let envelope_sha256 = framed_digest(
            ENVELOPE_DIGEST_DOMAIN,
            &[
                POLICY_ID.as_bytes(),
                PROFILE.as_bytes(),
                ENVELOPE_SCHEMA_ID.as_bytes(),
                &S9_CONTRACT_SHA256,
                &S10_CONTRACT_SHA256,
                &S11_CONTRACT_SHA256,
                &S12_CONTRACT_SHA256,
                canonical_request_bytes.as_ref(),
                canonical_decision_message_bytes.as_ref(),
                canonical_signature_bytes.as_ref(),
            ],
        );
        Ok(Self {
            request,
            canonical_request_bytes,
            decision,
            canonical_decision_message_bytes,
            canonical_signature_bytes,
            envelope_sha256,
        })
    }
}

/// One-shot ownership boundary for untrusted S9 envelope material and the raw
/// typed S10 lookup evidence that must authenticate before S12 can observe it.
/// The handoff itself is neither cloneable nor serializable.
#[must_use]
struct RecoveredEvidenceHandoffV1 {
    envelope: RecoveredS9EnvelopeV1,
    s10_query: ExternalOperationRecoveryQueryV1,
    s10_observation: SignedExternalOperationRecoveryObservationV1,
}

impl fmt::Debug for RecoveredEvidenceHandoffV1 {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        formatter
            .debug_struct("RecoveredEvidenceHandoffV1")
            .field("scope", &"[ONE_SHOT_UNTRUSTED_EVIDENCE_REDACTED]")
            .finish_non_exhaustive()
    }
}

impl RecoveredEvidenceHandoffV1 {
    fn new(
        envelope: RecoveredS9EnvelopeV1,
        s10_query: ExternalOperationRecoveryQueryV1,
        s10_observation: SignedExternalOperationRecoveryObservationV1,
    ) -> Self {
        Self {
            envelope,
            s10_query,
            s10_observation,
        }
    }

    /// Consume all carried values, verify S10 into a lexical projection, and
    /// immediately hand that projection to S12. No verified S10 value is
    /// returned, stored, cloned, or serialized.
    fn consume(
        self,
        s9_permit: &ExternalAuthorityTrustPermitV1,
        s10_permit: &ExternalOperationRecoveryTrustPermitV1,
        s11_request: &AtomicAuthorityOperationRequestV1,
        s11_permit: &AtomicAuthorityOperationTrustPermitV1,
        s11_record: &SignedCommittedAuthorityOperationV1,
    ) -> DeliveryResult<PurelyReverifiedRecoveredS9DecisionV1> {
        if &self.envelope.decision.ed25519_signature[..]
            != self.envelope.canonical_signature_bytes.as_ref()
        {
            return Err(delivery_error(
                "track_b_recovered_envelope_delivery_v1_signature_bytes",
                "the consumed signature no longer matches the owned typed S9 decision",
            ));
        }
        let s10_verified = verify_external_operation_recovery_observation_v1(
            &self.s10_query,
            s10_permit,
            &self.s10_observation,
        )
        .map_err(|_| {
            delivery_error(
                "track_b_recovered_envelope_delivery_v1_s10_verification",
                "the owned S10 query or signed observation failed pure verification",
            )
        })?;
        verify_recovered_s9_decision_v1(
            &RecoveredS9DecisionBundleV1 {
                request: &self.envelope.request,
                canonical_request_bytes: &self.envelope.canonical_request_bytes,
                decision: &self.envelope.decision,
                canonical_decision_message_bytes: &self.envelope.canonical_decision_message_bytes,
            },
            s9_permit,
            &s10_verified,
            s11_request,
            s11_permit,
            s11_record,
        )
        .map_err(|_| {
            delivery_error(
                "track_b_recovered_envelope_delivery_v1_s12_reverification",
                "the structurally valid envelope failed historical S12 re-verification",
            )
        })
    }
}

#[cfg(test)]
mod tests {
    use super::super::super::external_operation_recovery::{
        ExternalOperationRecoveryStateV1, ExternalOperationRecoveryTrustPermitV1,
    };
    use super::super::tests::{fixture, resign_s10, s10_inputs, Fixture, S10InputFixture};
    use super::*;

    fn encode(value: &[u8]) -> String {
        value.iter().map(|byte| format!("{byte:02x}")).collect()
    }

    fn repeated(value: u8) -> [u8; 32] {
        [value; 32]
    }

    struct EnvelopeInputs {
        request: ExternalCurrentnessRequestV1,
        request_bytes: Box<[u8]>,
        decision: SignedExternalCurrentnessDecisionV1,
        decision_bytes: Box<[u8]>,
        signature_bytes: Box<[u8]>,
    }

    impl EnvelopeInputs {
        fn from_fixture(base: &Fixture) -> Self {
            Self {
                request: base.s9_request.clone(),
                request_bytes: base.s9_request_bytes.clone().into_boxed_slice(),
                decision: base.s9_decision.clone(),
                decision_bytes: base.s9_decision_bytes.clone().into_boxed_slice(),
                signature_bytes: base
                    .s9_decision
                    .ed25519_signature
                    .to_vec()
                    .into_boxed_slice(),
            }
        }

        fn build(self) -> DeliveryResult<RecoveredS9EnvelopeV1> {
            RecoveredS9EnvelopeV1::try_new(
                self.request,
                self.request_bytes,
                self.decision,
                self.decision_bytes,
                self.signature_bytes,
            )
        }
    }

    fn envelope_inputs() -> (Fixture, EnvelopeInputs, S10InputFixture) {
        let base = fixture();
        let s10 = s10_inputs(&base.s9_request, &base.s9_decision);
        let input = EnvelopeInputs::from_fixture(&base);
        (base, input, s10)
    }

    struct DeliveryFixture {
        handoff: RecoveredEvidenceHandoffV1,
        s9_permit: ExternalAuthorityTrustPermitV1,
        s10_permit: ExternalOperationRecoveryTrustPermitV1,
        s11_request: AtomicAuthorityOperationRequestV1,
        s11_permit: AtomicAuthorityOperationTrustPermitV1,
        s11_record: SignedCommittedAuthorityOperationV1,
    }

    impl DeliveryFixture {
        fn consume(self) -> DeliveryResult<PurelyReverifiedRecoveredS9DecisionV1> {
            let Self {
                handoff,
                s9_permit,
                s10_permit,
                s11_request,
                s11_permit,
                s11_record,
            } = self;
            handoff.consume(
                &s9_permit,
                &s10_permit,
                &s11_request,
                &s11_permit,
                &s11_record,
            )
        }
    }

    fn delivery_fixture() -> DeliveryFixture {
        let (base, input, s10) = envelope_inputs();
        DeliveryFixture {
            handoff: RecoveredEvidenceHandoffV1::new(
                input.build().unwrap(),
                s10.query,
                s10.observation,
            ),
            s9_permit: base.s9_permit,
            s10_permit: s10.permit,
            s11_request: base.s11_request,
            s11_permit: base.s11_permit,
            s11_record: base.s11_record,
        }
    }

    #[test]
    fn s13_known_answer_owned_envelope_and_historical_chain_are_stable() {
        let fixture = delivery_fixture();
        let envelope_sha256 = fixture.handoff.envelope.envelope_sha256;
        let verified = fixture.consume().unwrap();
        assert_eq!(
            encode(&envelope_sha256),
            "5d74c7a300abe503b9a79c796394faa23de0c64f22fb80902294fa0654ee15d9"
        );
        assert_eq!(
            encode(&verified.historical_chain_sha256),
            "afb8aa4945f0e491937f75233c621d52f1bcc1307e6d497352fd9d0fc79b7204"
        );
    }

    #[test]
    fn s13_repeated_envelope_digest_and_delivery_are_deterministic() {
        let first = delivery_fixture();
        let second = delivery_fixture();
        assert_eq!(
            first.handoff.envelope.envelope_sha256,
            second.handoff.envelope.envelope_sha256
        );
        assert_eq!(
            first.consume().unwrap().historical_chain_sha256,
            second.consume().unwrap().historical_chain_sha256
        );
    }

    #[test]
    fn s13_empty_request_or_decision_rejects() {
        let (_, mut request_empty, _) = envelope_inputs();
        request_empty.request_bytes = Box::default();
        assert_eq!(
            request_empty.build().unwrap_err().code(),
            "track_b_recovered_envelope_delivery_v1_component_bounds"
        );

        let (_, mut decision_empty, _) = envelope_inputs();
        decision_empty.decision_bytes = Box::default();
        assert_eq!(
            decision_empty.build().unwrap_err().code(),
            "track_b_recovered_envelope_delivery_v1_component_bounds"
        );
    }

    #[test]
    fn s13_request_or_decision_max_plus_one_rejects() {
        let (_, mut request_large, _) = envelope_inputs();
        request_large.request_bytes = vec![0x41; MAX_MESSAGE_BYTES + 1].into_boxed_slice();
        assert_eq!(
            request_large.build().unwrap_err().code(),
            "track_b_recovered_envelope_delivery_v1_component_bounds"
        );

        let (_, mut decision_large, _) = envelope_inputs();
        decision_large.decision_bytes = vec![0x42; MAX_MESSAGE_BYTES + 1].into_boxed_slice();
        assert_eq!(
            decision_large.build().unwrap_err().code(),
            "track_b_recovered_envelope_delivery_v1_component_bounds"
        );
    }

    #[test]
    fn s13_aggregate_limit_rejects_before_canonicalization() {
        let (_, mut input, _) = envelope_inputs();
        input.request_bytes = vec![0x41; MAX_MESSAGE_BYTES].into_boxed_slice();
        input.decision_bytes = vec![0x42; MAX_MESSAGE_BYTES].into_boxed_slice();
        assert_eq!(
            input.build().unwrap_err().code(),
            "track_b_recovered_envelope_delivery_v1_total_bounds"
        );
    }

    #[test]
    fn s13_signature_must_be_exactly_64_bytes() {
        for size in [0, ED25519_SIGNATURE_BYTES - 1, ED25519_SIGNATURE_BYTES + 1] {
            let (_, mut input, _) = envelope_inputs();
            input.signature_bytes = vec![0x55; size].into_boxed_slice();
            assert_eq!(
                input.build().unwrap_err().code(),
                "track_b_recovered_envelope_delivery_v1_signature_bounds"
            );
        }
    }

    #[test]
    fn s13_truncated_or_appended_request_rejects() {
        let (_, mut truncated, _) = envelope_inputs();
        truncated.request_bytes = truncated.request_bytes[..truncated.request_bytes.len() - 1]
            .to_vec()
            .into_boxed_slice();
        assert_eq!(
            truncated.build().unwrap_err().code(),
            "track_b_recovered_envelope_delivery_v1_request_bytes"
        );

        let (_, mut appended, _) = envelope_inputs();
        appended.request_bytes = appended
            .request_bytes
            .iter()
            .copied()
            .chain([0])
            .collect::<Vec<_>>()
            .into_boxed_slice();
        assert_eq!(
            appended.build().unwrap_err().code(),
            "track_b_recovered_envelope_delivery_v1_request_bytes"
        );
    }

    #[test]
    fn s13_truncated_or_appended_decision_rejects() {
        let (_, mut truncated, _) = envelope_inputs();
        truncated.decision_bytes = truncated.decision_bytes[..truncated.decision_bytes.len() - 1]
            .to_vec()
            .into_boxed_slice();
        assert_eq!(
            truncated.build().unwrap_err().code(),
            "track_b_recovered_envelope_delivery_v1_decision_bytes"
        );

        let (_, mut appended, _) = envelope_inputs();
        appended.decision_bytes = appended
            .decision_bytes
            .iter()
            .copied()
            .chain([0])
            .collect::<Vec<_>>()
            .into_boxed_slice();
        assert_eq!(
            appended.build().unwrap_err().code(),
            "track_b_recovered_envelope_delivery_v1_decision_bytes"
        );
    }

    #[test]
    fn s13_typed_raw_request_or_decision_mismatch_rejects() {
        let (_, mut request_mismatch, _) = envelope_inputs();
        request_mismatch.request.operation_id[0] ^= 1;
        assert_eq!(
            request_mismatch.build().unwrap_err().code(),
            "track_b_recovered_envelope_delivery_v1_request_bytes"
        );

        let (_, mut decision_mismatch, _) = envelope_inputs();
        decision_mismatch.decision.decision_id[0] ^= 1;
        assert_eq!(
            decision_mismatch.build().unwrap_err().code(),
            "track_b_recovered_envelope_delivery_v1_decision_bytes"
        );
    }

    #[test]
    fn s13_signature_box_must_match_typed_decision() {
        let (_, mut input, _) = envelope_inputs();
        input.signature_bytes[0] ^= 1;
        assert_eq!(
            input.build().unwrap_err().code(),
            "track_b_recovered_envelope_delivery_v1_signature_bytes"
        );
    }

    #[test]
    fn s13_s10_signature_tamper_rejects() {
        let mut fixture = delivery_fixture();
        fixture.handoff.s10_observation.ed25519_signature[0] ^= 1;
        assert_eq!(
            fixture.consume().unwrap_err().code(),
            "track_b_recovered_envelope_delivery_v1_s10_verification"
        );
    }

    #[test]
    fn s13_s10_wrong_permit_rejects() {
        let DeliveryFixture {
            handoff,
            s9_permit,
            s10_permit: _,
            s11_request,
            s11_permit,
            s11_record,
        } = delivery_fixture();
        let wrong_permit = ExternalOperationRecoveryTrustPermitV1::test_only_new(
            handoff.envelope.request.provider_profile_id.clone(),
            handoff.envelope.request.authority_namespace_id.clone(),
            handoff.envelope.request.tenant_id.clone(),
            handoff.envelope.request.audience.clone(),
            handoff.envelope.decision.provider_cluster_id.clone(),
            handoff.envelope.decision.provider_incarnation,
            "recovery-signer-a",
            4,
            handoff.envelope.request.trust_policy_sha256,
            7,
            50,
            repeated(0x72),
            repeated(0x99),
        );
        assert_eq!(
            handoff
                .consume(
                    &s9_permit,
                    &wrong_permit,
                    &s11_request,
                    &s11_permit,
                    &s11_record,
                )
                .unwrap_err()
                .code(),
            "track_b_recovered_envelope_delivery_v1_s10_verification"
        );
    }

    #[test]
    fn s13_s10_noncommitted_signed_observation_rejects() {
        let mut fixture = delivery_fixture();
        fixture.handoff.s10_observation.state = ExternalOperationRecoveryStateV1::Pending;
        resign_s10(&mut fixture.handoff.s10_observation);
        assert_eq!(
            fixture.consume().unwrap_err().code(),
            "track_b_recovered_envelope_delivery_v1_s10_verification"
        );
    }

    #[test]
    fn s13_s11_l2_metadata_is_unread_by_consuming_handoff() {
        let first = delivery_fixture();
        let mut second = delivery_fixture();
        second.s11_record.synthetic_l2_revision = 99;
        second.s11_record.synthetic_l2_record_sha256 = [0; 32];
        assert_eq!(
            first.consume().unwrap().historical_chain_sha256,
            second.consume().unwrap().historical_chain_sha256
        );
    }

    #[test]
    fn s13_debug_and_source_keep_carrier_private_nonserializable_and_detached() {
        let fixture = delivery_fixture();
        let debug = format!("{:?}", fixture.handoff.envelope);
        let handoff_debug = format!("{:?}", fixture.handoff);
        assert!(debug.contains("OWNED_UNTRUSTED_STRUCTURAL_INPUT_BYTES_REDACTED"));
        assert!(handoff_debug.contains("ONE_SHOT_UNTRUSTED_EVIDENCE_REDACTED"));
        assert!(!debug.contains("agent-bridge-research-prod"));
        assert!(!debug.contains("currentness-signer-a"));

        let source = include_str!("recovered_envelope_delivery.rs");
        let production = source.split("\n#[cfg(test)]\nmod tests").next().unwrap();
        assert!(!production.contains("serde::"));
        assert!(!production.contains("Serialize"));
        assert!(!production.contains("#[derive(Clone"));
        assert!(!production.contains("pub(super)"));
        assert!(!production.contains("pub(crate)"));
        assert!(!production.contains(".lookup_operation("));
        assert!(!production.contains(".request_currentness("));
    }
}
