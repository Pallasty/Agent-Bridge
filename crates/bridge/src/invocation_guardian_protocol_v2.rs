//! Independent bounded wire protocol for the Invocation Guardian v2 canary.
//!
//! It intentionally shares neither magic nor disposition bits with the v1
//! volatile-lab protocol. Only `FreshCommitted` can carry a live grant.

use crate::invocation_lease_scope::{
    CanaryLeaseScope, Commitment, ObservedCanaryInvocation, ScopeError, SignedCanaryLease,
    SIGNATURE_BYTES,
};

pub const PROTOCOL_VERSION_V2: u8 = 2;
pub const MAX_V2_FRAME_BODY_BYTES: usize = 4096;
const MAGIC: &[u8; 4] = b"ABI2";
const HEADER_BYTES: usize = 8;
const CONSUME_TAG: u8 = 1;
const OUTCOME_TAG: u8 = 0x81;

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct ConsumeCanaryRequest {
    pub request_challenge: Commitment,
    pub observed: ObservedCanaryInvocation,
    pub lease: SignedCanaryLease,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
#[repr(u8)]
pub enum CanaryOutcomeKind {
    FreshCommitted = 1,
    AlreadyCommitted = 2,
    Conflict = 3,
    Expired = 4,
    Indeterminate = 5,
    Hold = 6,
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct CanaryOutcomeResponse {
    pub request_challenge: Commitment,
    pub kind: CanaryOutcomeKind,
    pub exact_scope_commitment: Commitment,
    pub provider_receipt: Vec<u8>,
}

impl CanaryOutcomeResponse {
    pub fn grants_current_dispatch(&self) -> bool {
        self.kind == CanaryOutcomeKind::FreshCommitted
            && nonzero(&self.request_challenge)
            && nonzero(&self.exact_scope_commitment)
            && !self.provider_receipt.is_empty()
    }
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, thiserror::Error)]
pub enum ProtocolV2Error {
    #[error("unexpected_eof")]
    UnexpectedEof,
    #[error("oversized_frame")]
    Oversized,
    #[error("invalid_frame")]
    InvalidFrame,
    #[error("invalid_scope")]
    InvalidScope,
}

impl From<ScopeError> for ProtocolV2Error {
    fn from(_: ScopeError) -> Self {
        Self::InvalidScope
    }
}

pub fn encode_consume(request: &ConsumeCanaryRequest) -> Result<Vec<u8>, ProtocolV2Error> {
    if !nonzero(&request.request_challenge) || request.observed.transport_kind != "stdio" {
        return Err(ProtocolV2Error::InvalidFrame);
    }
    let scope = request.lease.scope.canonical_bytes()?;
    let mut body = header(CONSUME_TAG);
    body.extend_from_slice(&request.request_challenge);
    string(&mut body, &request.observed.tool_name)?;
    body.extend_from_slice(&request.observed.arguments_jcs_sha256);
    body.extend_from_slice(&request.observed.target_sha256);
    body.extend_from_slice(&request.observed.registry_sha256);
    string(&mut body, &request.observed.namespace)?;
    string(&mut body, &request.observed.principal_kind)?;
    body.extend_from_slice(&request.observed.principal_commitment);
    string(&mut body, &request.observed.transport_kind)?;
    body.extend_from_slice(&request.observed.connection_commitment);
    bytes(&mut body, &scope)?;
    body.extend_from_slice(&request.lease.signature);
    frame(body)
}

pub fn decode_consume_body(body: &[u8]) -> Result<ConsumeCanaryRequest, ProtocolV2Error> {
    validate_header(body, CONSUME_TAG)?;
    let mut decoder = Decoder::new(&body[HEADER_BYTES..]);
    let request = ConsumeCanaryRequest {
        request_challenge: decoder.fixed()?,
        observed: ObservedCanaryInvocation {
            tool_name: decoder.string()?,
            arguments_jcs_sha256: decoder.fixed()?,
            target_sha256: decoder.fixed()?,
            registry_sha256: decoder.fixed()?,
            namespace: decoder.string()?,
            principal_kind: decoder.string()?,
            principal_commitment: decoder.fixed()?,
            transport_kind: decoder.string()?,
            connection_commitment: decoder.fixed()?,
        },
        lease: SignedCanaryLease {
            scope: CanaryLeaseScope::decode_canonical(decoder.bytes()?)?,
            signature: decoder.signature()?,
        },
    };
    if !decoder.done() || encode_consume(&request)?.get(4..) != Some(body) {
        return Err(ProtocolV2Error::InvalidFrame);
    }
    Ok(request)
}

pub fn encode_outcome(response: &CanaryOutcomeResponse) -> Result<Vec<u8>, ProtocolV2Error> {
    if !nonzero(&response.request_challenge)
        || (matches!(
            response.kind,
            CanaryOutcomeKind::FreshCommitted | CanaryOutcomeKind::AlreadyCommitted
        ) && (!nonzero(&response.exact_scope_commitment)
            || response.provider_receipt.is_empty()))
        || (!matches!(
            response.kind,
            CanaryOutcomeKind::FreshCommitted | CanaryOutcomeKind::AlreadyCommitted
        ) && !response.provider_receipt.is_empty())
    {
        return Err(ProtocolV2Error::InvalidFrame);
    }
    let mut body = header(OUTCOME_TAG);
    body.extend_from_slice(&response.request_challenge);
    body.push(response.kind as u8);
    body.push(match response.kind {
        CanaryOutcomeKind::FreshCommitted => 1,
        CanaryOutcomeKind::AlreadyCommitted => 2,
        _ => 0,
    });
    body.extend_from_slice(&response.exact_scope_commitment);
    bytes(&mut body, &response.provider_receipt)?;
    frame(body)
}

pub fn decode_outcome_body(body: &[u8]) -> Result<CanaryOutcomeResponse, ProtocolV2Error> {
    validate_header(body, OUTCOME_TAG)?;
    let mut decoder = Decoder::new(&body[HEADER_BYTES..]);
    let request_challenge = decoder.fixed()?;
    let kind = match decoder.u8()? {
        1 => CanaryOutcomeKind::FreshCommitted,
        2 => CanaryOutcomeKind::AlreadyCommitted,
        3 => CanaryOutcomeKind::Conflict,
        4 => CanaryOutcomeKind::Expired,
        5 => CanaryOutcomeKind::Indeterminate,
        6 => CanaryOutcomeKind::Hold,
        _ => return Err(ProtocolV2Error::InvalidFrame),
    };
    let receipt_disposition = decoder.u8()?;
    let expected_disposition = match kind {
        CanaryOutcomeKind::FreshCommitted => 1,
        CanaryOutcomeKind::AlreadyCommitted => 2,
        _ => 0,
    };
    if receipt_disposition != expected_disposition {
        return Err(ProtocolV2Error::InvalidFrame);
    }
    let exact_scope_commitment = decoder.fixed()?;
    let provider_receipt = decoder.bytes()?.to_vec();
    let response = CanaryOutcomeResponse {
        request_challenge,
        kind,
        exact_scope_commitment,
        provider_receipt,
    };
    if !decoder.done() || encode_outcome(&response)?.get(4..) != Some(body) {
        return Err(ProtocolV2Error::InvalidFrame);
    }
    Ok(response)
}

pub fn decode_frame_prefix(frame: &[u8]) -> Result<&[u8], ProtocolV2Error> {
    if frame.len() < 4 {
        return Err(ProtocolV2Error::UnexpectedEof);
    }
    let length = u32::from_be_bytes(
        frame[..4]
            .try_into()
            .map_err(|_| ProtocolV2Error::InvalidFrame)?,
    ) as usize;
    if length > MAX_V2_FRAME_BODY_BYTES {
        return Err(ProtocolV2Error::Oversized);
    }
    if frame.len() != length + 4 {
        return Err(ProtocolV2Error::UnexpectedEof);
    }
    Ok(&frame[4..])
}

fn header(tag: u8) -> Vec<u8> {
    let mut body = Vec::with_capacity(512);
    body.extend_from_slice(MAGIC);
    body.extend_from_slice(&[PROTOCOL_VERSION_V2, tag, 0, 0]);
    body
}

fn validate_header(body: &[u8], tag: u8) -> Result<(), ProtocolV2Error> {
    if body.len() < HEADER_BYTES
        || &body[..4] != MAGIC
        || body[4] != PROTOCOL_VERSION_V2
        || body[5] != tag
        || body[6] != 0
        || body[7] != 0
    {
        return Err(ProtocolV2Error::InvalidFrame);
    }
    Ok(())
}

fn frame(body: Vec<u8>) -> Result<Vec<u8>, ProtocolV2Error> {
    if body.len() > MAX_V2_FRAME_BODY_BYTES {
        return Err(ProtocolV2Error::Oversized);
    }
    let mut framed = Vec::with_capacity(body.len() + 4);
    framed.extend_from_slice(&(body.len() as u32).to_be_bytes());
    framed.extend_from_slice(&body);
    Ok(framed)
}

fn string(out: &mut Vec<u8>, value: &str) -> Result<(), ProtocolV2Error> {
    bytes(out, value.as_bytes())
}

fn bytes(out: &mut Vec<u8>, value: &[u8]) -> Result<(), ProtocolV2Error> {
    let length = u16::try_from(value.len()).map_err(|_| ProtocolV2Error::Oversized)?;
    out.extend_from_slice(&length.to_be_bytes());
    out.extend_from_slice(value);
    Ok(())
}

fn nonzero(value: &Commitment) -> bool {
    value.iter().any(|byte| *byte != 0)
}

struct Decoder<'a> {
    bytes: &'a [u8],
    position: usize,
}
impl<'a> Decoder<'a> {
    fn new(bytes: &'a [u8]) -> Self {
        Self { bytes, position: 0 }
    }
    fn take(&mut self, n: usize) -> Result<&'a [u8], ProtocolV2Error> {
        let end = self
            .position
            .checked_add(n)
            .ok_or(ProtocolV2Error::InvalidFrame)?;
        let value = self
            .bytes
            .get(self.position..end)
            .ok_or(ProtocolV2Error::UnexpectedEof)?;
        self.position = end;
        Ok(value)
    }
    fn u8(&mut self) -> Result<u8, ProtocolV2Error> {
        Ok(self.take(1)?[0])
    }
    fn fixed(&mut self) -> Result<Commitment, ProtocolV2Error> {
        self.take(32)?
            .try_into()
            .map_err(|_| ProtocolV2Error::InvalidFrame)
    }
    fn signature(&mut self) -> Result<[u8; SIGNATURE_BYTES], ProtocolV2Error> {
        self.take(SIGNATURE_BYTES)?
            .try_into()
            .map_err(|_| ProtocolV2Error::InvalidFrame)
    }
    fn bytes(&mut self) -> Result<&'a [u8], ProtocolV2Error> {
        let length = u16::from_be_bytes(
            self.take(2)?
                .try_into()
                .map_err(|_| ProtocolV2Error::InvalidFrame)?,
        ) as usize;
        self.take(length)
    }
    fn string(&mut self) -> Result<String, ProtocolV2Error> {
        String::from_utf8(self.bytes()?.to_vec()).map_err(|_| ProtocolV2Error::InvalidFrame)
    }
    fn done(&self) -> bool {
        self.position == self.bytes.len()
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::invocation_guardian_protocol::{
        decode_request_body as decode_v1, encode_request as encode_v1, GuardianRequest,
    };
    use crate::invocation_lease_scope::{domain_hash, CanaryLeaseScope};
    use ring::rand::SystemRandom;
    use ring::signature::{Ed25519KeyPair, KeyPair as _};

    fn request() -> ConsumeCanaryRequest {
        let doc = Ed25519KeyPair::generate_pkcs8(&SystemRandom::new()).unwrap();
        let key = Ed25519KeyPair::from_pkcs8(doc.as_ref()).unwrap();
        let public: [u8; 32] = key.public_key().as_ref().try_into().unwrap();
        let scope = CanaryLeaseScope {
            key_generation: 1,
            issuer_key_commitment: domain_hash(
                b"agent_bridge.invocation_guardian.issuer_key.v2\0",
                &public,
            ),
            ledger_generation: [2; 32],
            token_commitment: [3; 32],
            lease_id: "lease-1".into(),
            tool_name: "invocation_guardian_canary_write".into(),
            arguments_jcs_sha256: [4; 32],
            target_sha256: [5; 32],
            registry_sha256: [6; 32],
            namespace: "canary/test".into(),
            principal_kind: "service".into(),
            principal_commitment: [7; 32],
            connection_commitment: [8; 32],
            issued_at_unix: 10,
            not_before_unix: 10,
            expires_at_unix: 70,
            max_uses: 1,
        };
        let observed = ObservedCanaryInvocation {
            tool_name: scope.tool_name.clone(),
            arguments_jcs_sha256: [4; 32],
            target_sha256: [5; 32],
            registry_sha256: [6; 32],
            namespace: scope.namespace.clone(),
            principal_kind: scope.principal_kind.clone(),
            principal_commitment: [7; 32],
            transport_kind: "stdio".into(),
            connection_commitment: [8; 32],
        };
        ConsumeCanaryRequest {
            request_challenge: [9; 32],
            observed,
            lease: SignedCanaryLease::sign(scope, &key).unwrap(),
        }
    }

    #[test]
    fn v2_round_trip_is_canonical_and_bounded() {
        let request = request();
        let frame = encode_consume(&request).unwrap();
        assert_eq!(
            decode_consume_body(decode_frame_prefix(&frame).unwrap()).unwrap(),
            request
        );
        let mut trailing = frame;
        trailing.push(0);
        assert_eq!(
            decode_frame_prefix(&trailing),
            Err(ProtocolV2Error::UnexpectedEof)
        );
    }

    #[test]
    fn v1_and_v2_cross_decode_is_impossible() {
        let v2 = encode_consume(&request()).unwrap();
        assert!(decode_v1(decode_frame_prefix(&v2).unwrap()).is_err());
        let v1 = encode_v1(GuardianRequest::Hello {
            client_nonce: [1; 32],
        })
        .unwrap();
        assert!(decode_consume_body(&v1[4..]).is_err());
    }

    #[test]
    fn only_fresh_committed_can_grant_and_disposition_cannot_flip() {
        let already = CanaryOutcomeResponse {
            request_challenge: [1; 32],
            kind: CanaryOutcomeKind::AlreadyCommitted,
            exact_scope_commitment: [2; 32],
            provider_receipt: vec![3],
        };
        assert!(!decode_outcome_body(
            decode_frame_prefix(&encode_outcome(&already).unwrap()).unwrap()
        )
        .unwrap()
        .grants_current_dispatch());
        for kind in [
            CanaryOutcomeKind::Conflict,
            CanaryOutcomeKind::Expired,
            CanaryOutcomeKind::Indeterminate,
            CanaryOutcomeKind::Hold,
        ] {
            let response = CanaryOutcomeResponse {
                request_challenge: [1; 32],
                kind,
                exact_scope_commitment: [2; 32],
                provider_receipt: Vec::new(),
            };
            assert!(!decode_outcome_body(
                decode_frame_prefix(&encode_outcome(&response).unwrap()).unwrap()
            )
            .unwrap()
            .grants_current_dispatch());
        }
        let fresh = CanaryOutcomeResponse {
            request_challenge: [1; 32],
            kind: CanaryOutcomeKind::FreshCommitted,
            exact_scope_commitment: [2; 32],
            provider_receipt: vec![3],
        };
        assert!(decode_outcome_body(
            decode_frame_prefix(&encode_outcome(&fresh).unwrap()).unwrap()
        )
        .unwrap()
        .grants_current_dispatch());
        let mut frame = encode_outcome(&fresh).unwrap();
        frame[4 + HEADER_BYTES + 32] = CanaryOutcomeKind::AlreadyCommitted as u8;
        assert!(decode_outcome_body(decode_frame_prefix(&frame).unwrap()).is_err());
    }

    #[test]
    fn unknown_tags_reserved_bits_truncation_and_oversize_fail_closed() {
        let frame = encode_consume(&request()).unwrap();
        for index in [4 + 5, 4 + 6, 4 + 7] {
            let mut changed = frame.clone();
            changed[index] = 0xff;
            assert!(decode_consume_body(decode_frame_prefix(&changed).unwrap()).is_err());
        }
        assert_eq!(
            decode_frame_prefix(&frame[..frame.len() - 1]),
            Err(ProtocolV2Error::UnexpectedEof)
        );
        let mut huge = vec![0; 4];
        huge.copy_from_slice(&((MAX_V2_FRAME_BODY_BYTES + 1) as u32).to_be_bytes());
        assert_eq!(decode_frame_prefix(&huge), Err(ProtocolV2Error::Oversized));
    }
}
