//! Bounded candidate protocol for an invocation-consumption guardian.
//!
//! Version 1 is deliberately lab-only. Every decodable response carries
//! `grants_authority = false` and `witness_class = volatile_lab`; a future
//! production monotonic witness needs a new protocol version and review.

use std::io::{self, Read, Write};

use sha2::{Digest, Sha256};

pub const PROTOCOL_VERSION: u8 = 1;
pub const MAX_FRAME_BODY_BYTES: usize = 320;
pub const VALUE_BYTES: usize = 32;

const MAGIC: &[u8; 4] = b"ABIG";
const HEADER_BYTES: usize = 8;
const HELLO_REQUEST_TAG: u8 = 1;
const CONSUME_EXACT_REQUEST_TAG: u8 = 2;
const LOOKUP_EXACT_REQUEST_TAG: u8 = 3;
const HELLO_RESPONSE_TAG: u8 = 0x81;
const OUTCOME_RESPONSE_TAG: u8 = 0x82;
const HELLO_REQUEST_BYTES: usize = HEADER_BYTES + VALUE_BYTES;
const EXACT_REQUEST_BYTES: usize = HEADER_BYTES + (VALUE_BYTES * 4);
const HELLO_RESPONSE_BYTES: usize = HEADER_BYTES + (VALUE_BYTES * 3) + 4;
const RECEIPT_BYTES: usize = (VALUE_BYTES * 5) + 8;
const OUTCOME_RESPONSE_BYTES: usize = HEADER_BYTES + (VALUE_BYTES * 4) + 4 + RECEIPT_BYTES;

pub type FixedValue = [u8; VALUE_BYTES];

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct ExactOperation {
    pub session_nonce: FixedValue,
    pub operation_id: FixedValue,
    pub scope_commitment: FixedValue,
    pub expected_previous_head: FixedValue,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum GuardianRequest {
    Hello { client_nonce: FixedValue },
    ConsumeExact(ExactOperation),
    LookupExact(ExactOperation),
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
#[repr(u8)]
pub enum WitnessClass {
    VolatileLab = 1,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
#[repr(u8)]
pub enum OutcomeKind {
    Committed = 1,
    AlreadyCommitted = 2,
    Conflict = 3,
    Indeterminate = 4,
    Hold = 5,
}

impl OutcomeKind {
    fn from_u8(value: u8) -> Option<Self> {
        match value {
            1 => Some(Self::Committed),
            2 => Some(Self::AlreadyCommitted),
            3 => Some(Self::Conflict),
            4 => Some(Self::Indeterminate),
            5 => Some(Self::Hold),
            _ => None,
        }
    }

    fn has_receipt(self) -> bool {
        matches!(self, Self::Committed | Self::AlreadyCommitted)
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct CommitReceipt {
    pub operation_id: FixedValue,
    pub scope_commitment: FixedValue,
    pub previous_head: FixedValue,
    pub new_head: FixedValue,
    pub revision: u64,
    pub provider_incarnation: FixedValue,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct OutcomeResponse {
    pub request: ExactOperation,
    pub kind: OutcomeKind,
    pub receipt: Option<CommitReceipt>,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum GuardianResponse {
    Hello {
        client_nonce: FixedValue,
        guardian_nonce: FixedValue,
        provider_incarnation: FixedValue,
    },
    Outcome(OutcomeResponse),
}

impl GuardianResponse {
    pub const fn grants_authority(&self) -> bool {
        false
    }

    pub const fn witness_class(&self) -> WitnessClass {
        WitnessClass::VolatileLab
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, thiserror::Error)]
pub enum ProtocolError {
    #[error("unexpected_eof")]
    UnexpectedEof,
    #[error("oversized_frame")]
    Oversized,
    #[error("invalid_frame")]
    InvalidFrame,
    #[error("io")]
    Io,
}

pub fn session_nonce(
    client_nonce: &FixedValue,
    guardian_nonce: &FixedValue,
    provider_incarnation: &FixedValue,
) -> FixedValue {
    let mut digest = Sha256::new();
    digest.update(b"ab.invocation_guardian.session.v1\0");
    digest.update(client_nonce);
    digest.update(guardian_nonce);
    digest.update(provider_incarnation);
    digest.finalize().into()
}

pub fn encode_request(request: GuardianRequest) -> Result<Vec<u8>, ProtocolError> {
    let mut body = Vec::with_capacity(EXACT_REQUEST_BYTES);
    match request {
        GuardianRequest::Hello { client_nonce } if nonzero(&client_nonce) => {
            push_header(&mut body, HELLO_REQUEST_TAG);
            body.extend_from_slice(&client_nonce);
        }
        GuardianRequest::ConsumeExact(exact) if valid_exact(&exact) => {
            push_header(&mut body, CONSUME_EXACT_REQUEST_TAG);
            push_exact(&mut body, &exact);
        }
        GuardianRequest::LookupExact(exact) if valid_exact(&exact) => {
            push_header(&mut body, LOOKUP_EXACT_REQUEST_TAG);
            push_exact(&mut body, &exact);
        }
        _ => return Err(ProtocolError::InvalidFrame),
    }
    encode_body(body)
}

pub fn decode_request_body(body: &[u8]) -> Result<GuardianRequest, ProtocolError> {
    validate_header(body)?;
    let request = match (body[5], body.len()) {
        (HELLO_REQUEST_TAG, HELLO_REQUEST_BYTES) => GuardianRequest::Hello {
            client_nonce: fixed_at(body, HEADER_BYTES)?,
        },
        (CONSUME_EXACT_REQUEST_TAG, EXACT_REQUEST_BYTES) => {
            GuardianRequest::ConsumeExact(exact_at(body)?)
        }
        (LOOKUP_EXACT_REQUEST_TAG, EXACT_REQUEST_BYTES) => {
            GuardianRequest::LookupExact(exact_at(body)?)
        }
        _ => return Err(ProtocolError::InvalidFrame),
    };
    encode_request(request)?;
    Ok(request)
}

pub fn encode_response(response: GuardianResponse) -> Result<Vec<u8>, ProtocolError> {
    let mut body = Vec::with_capacity(OUTCOME_RESPONSE_BYTES);
    match response {
        GuardianResponse::Hello {
            client_nonce,
            guardian_nonce,
            provider_incarnation,
        } if nonzero(&client_nonce)
            && nonzero(&guardian_nonce)
            && nonzero(&provider_incarnation) =>
        {
            push_header(&mut body, HELLO_RESPONSE_TAG);
            body.extend_from_slice(&client_nonce);
            body.extend_from_slice(&guardian_nonce);
            body.extend_from_slice(&provider_incarnation);
            push_lab_disposition(&mut body);
        }
        GuardianResponse::Outcome(outcome) if valid_outcome(&outcome) => {
            push_header(&mut body, OUTCOME_RESPONSE_TAG);
            push_exact(&mut body, &outcome.request);
            body.extend_from_slice(&[
                outcome.kind as u8,
                0, // grants_authority: false
                WitnessClass::VolatileLab as u8,
                u8::from(outcome.receipt.is_some()),
            ]);
            if let Some(receipt) = outcome.receipt {
                push_receipt(&mut body, &receipt);
            } else {
                body.resize(body.len() + RECEIPT_BYTES, 0);
            }
        }
        _ => return Err(ProtocolError::InvalidFrame),
    }
    encode_body(body)
}

pub fn decode_response_body(body: &[u8]) -> Result<GuardianResponse, ProtocolError> {
    validate_header(body)?;
    let response = match (body[5], body.len()) {
        (HELLO_RESPONSE_TAG, HELLO_RESPONSE_BYTES) if lab_disposition_at(body, 104) => {
            GuardianResponse::Hello {
                client_nonce: fixed_at(body, 8)?,
                guardian_nonce: fixed_at(body, 40)?,
                provider_incarnation: fixed_at(body, 72)?,
            }
        }
        (OUTCOME_RESPONSE_TAG, OUTCOME_RESPONSE_BYTES)
            if body[137] == 0 && body[138] == WitnessClass::VolatileLab as u8 =>
        {
            let request = exact_at(body)?;
            let kind = OutcomeKind::from_u8(body[136]).ok_or(ProtocolError::InvalidFrame)?;
            let receipt = match body[139] {
                0 if !kind.has_receipt() && body[140..].iter().all(|byte| *byte == 0) => None,
                1 if kind.has_receipt() => Some(receipt_at(body, 140)?),
                _ => return Err(ProtocolError::InvalidFrame),
            };
            GuardianResponse::Outcome(OutcomeResponse {
                request,
                kind,
                receipt,
            })
        }
        _ => return Err(ProtocolError::InvalidFrame),
    };
    encode_response(response)?;
    Ok(response)
}

pub fn read_request(reader: &mut impl Read) -> Result<GuardianRequest, ProtocolError> {
    let body = read_body(reader)?;
    decode_request_body(&body)
}

pub fn read_response(reader: &mut impl Read) -> Result<GuardianResponse, ProtocolError> {
    let body = read_body(reader)?;
    decode_response_body(&body)
}

pub fn write_request(
    writer: &mut impl Write,
    request: GuardianRequest,
) -> Result<(), ProtocolError> {
    writer
        .write_all(&encode_request(request)?)
        .map_err(|_| ProtocolError::Io)
}

pub fn write_response(
    writer: &mut impl Write,
    response: GuardianResponse,
) -> Result<(), ProtocolError> {
    writer
        .write_all(&encode_response(response)?)
        .map_err(|_| ProtocolError::Io)
}

fn push_header(body: &mut Vec<u8>, tag: u8) {
    body.extend_from_slice(MAGIC);
    body.extend_from_slice(&[PROTOCOL_VERSION, tag, 0, 0]);
}

fn push_lab_disposition(body: &mut Vec<u8>) {
    body.extend_from_slice(&[0, WitnessClass::VolatileLab as u8, 0, 0]);
}

fn push_exact(body: &mut Vec<u8>, exact: &ExactOperation) {
    body.extend_from_slice(&exact.session_nonce);
    body.extend_from_slice(&exact.operation_id);
    body.extend_from_slice(&exact.scope_commitment);
    body.extend_from_slice(&exact.expected_previous_head);
}

fn push_receipt(body: &mut Vec<u8>, receipt: &CommitReceipt) {
    body.extend_from_slice(&receipt.operation_id);
    body.extend_from_slice(&receipt.scope_commitment);
    body.extend_from_slice(&receipt.previous_head);
    body.extend_from_slice(&receipt.new_head);
    body.extend_from_slice(&receipt.revision.to_be_bytes());
    body.extend_from_slice(&receipt.provider_incarnation);
}

fn encode_body(body: Vec<u8>) -> Result<Vec<u8>, ProtocolError> {
    if body.is_empty() || body.len() > MAX_FRAME_BODY_BYTES {
        return Err(ProtocolError::Oversized);
    }
    let length = u32::try_from(body.len()).map_err(|_| ProtocolError::Oversized)?;
    let mut frame = Vec::with_capacity(body.len() + 4);
    frame.extend_from_slice(&length.to_be_bytes());
    frame.extend_from_slice(&body);
    Ok(frame)
}

fn read_body(reader: &mut impl Read) -> Result<Vec<u8>, ProtocolError> {
    let mut length = [0_u8; 4];
    read_exact(reader, &mut length)?;
    let length =
        usize::try_from(u32::from_be_bytes(length)).map_err(|_| ProtocolError::Oversized)?;
    if length == 0 || length > MAX_FRAME_BODY_BYTES {
        return Err(ProtocolError::Oversized);
    }
    let mut body = vec![0_u8; length];
    read_exact(reader, &mut body)?;
    Ok(body)
}

fn read_exact(reader: &mut impl Read, output: &mut [u8]) -> Result<(), ProtocolError> {
    match reader.read_exact(output) {
        Ok(()) => Ok(()),
        Err(error) if error.kind() == io::ErrorKind::UnexpectedEof => {
            Err(ProtocolError::UnexpectedEof)
        }
        Err(_) => Err(ProtocolError::Io),
    }
}

fn validate_header(body: &[u8]) -> Result<(), ProtocolError> {
    if body.len() < HEADER_BYTES
        || body.get(..4) != Some(MAGIC)
        || body[4] != PROTOCOL_VERSION
        || body[6..8] != [0, 0]
    {
        return Err(ProtocolError::InvalidFrame);
    }
    Ok(())
}

fn lab_disposition_at(body: &[u8], offset: usize) -> bool {
    body.get(offset..offset + 4) == Some(&[0, WitnessClass::VolatileLab as u8, 0, 0])
}

fn fixed_at(body: &[u8], offset: usize) -> Result<FixedValue, ProtocolError> {
    body.get(offset..offset + VALUE_BYTES)
        .and_then(|bytes| bytes.try_into().ok())
        .ok_or(ProtocolError::InvalidFrame)
}

fn exact_at(body: &[u8]) -> Result<ExactOperation, ProtocolError> {
    Ok(ExactOperation {
        session_nonce: fixed_at(body, 8)?,
        operation_id: fixed_at(body, 40)?,
        scope_commitment: fixed_at(body, 72)?,
        expected_previous_head: fixed_at(body, 104)?,
    })
}

fn receipt_at(body: &[u8], offset: usize) -> Result<CommitReceipt, ProtocolError> {
    let revision = body
        .get(offset + 128..offset + 136)
        .and_then(|bytes| bytes.try_into().ok())
        .map(u64::from_be_bytes)
        .ok_or(ProtocolError::InvalidFrame)?;
    Ok(CommitReceipt {
        operation_id: fixed_at(body, offset)?,
        scope_commitment: fixed_at(body, offset + 32)?,
        previous_head: fixed_at(body, offset + 64)?,
        new_head: fixed_at(body, offset + 96)?,
        revision,
        provider_incarnation: fixed_at(body, offset + 136)?,
    })
}

fn nonzero(value: &FixedValue) -> bool {
    value.iter().any(|byte| *byte != 0)
}

fn valid_exact(exact: &ExactOperation) -> bool {
    nonzero(&exact.session_nonce)
        && nonzero(&exact.operation_id)
        && nonzero(&exact.scope_commitment)
}

fn valid_receipt(receipt: &CommitReceipt, request: &ExactOperation) -> bool {
    receipt.operation_id == request.operation_id
        && receipt.scope_commitment == request.scope_commitment
        && receipt.previous_head == request.expected_previous_head
        && nonzero(&receipt.new_head)
        && receipt.revision > 0
        && nonzero(&receipt.provider_incarnation)
}

fn valid_outcome(outcome: &OutcomeResponse) -> bool {
    valid_exact(&outcome.request)
        && match (outcome.kind.has_receipt(), outcome.receipt.as_ref()) {
            (true, Some(receipt)) => valid_receipt(receipt, &outcome.request),
            (false, None) => true,
            _ => false,
        }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn value(byte: u8) -> FixedValue {
        [byte; VALUE_BYTES]
    }

    fn exact() -> ExactOperation {
        ExactOperation {
            session_nonce: value(1),
            operation_id: value(2),
            scope_commitment: value(3),
            expected_previous_head: [0; VALUE_BYTES],
        }
    }

    #[test]
    fn request_round_trip_and_closed_schema() {
        for request in [
            GuardianRequest::Hello {
                client_nonce: value(9),
            },
            GuardianRequest::ConsumeExact(exact()),
            GuardianRequest::LookupExact(exact()),
        ] {
            let encoded = encode_request(request).expect("encode request");
            assert_eq!(read_request(&mut encoded.as_slice()), Ok(request));
        }

        let mut encoded = encode_request(GuardianRequest::ConsumeExact(exact())).unwrap();
        encoded.push(0);
        let body_length = u32::from_be_bytes(encoded[..4].try_into().unwrap()) + 1;
        encoded[..4].copy_from_slice(&body_length.to_be_bytes());
        assert_eq!(
            read_request(&mut encoded.as_slice()),
            Err(ProtocolError::InvalidFrame)
        );

        let oversized = ((MAX_FRAME_BODY_BYTES + 1) as u32).to_be_bytes();
        assert_eq!(
            read_request(&mut oversized.as_slice()),
            Err(ProtocolError::Oversized)
        );
    }

    #[test]
    fn response_round_trip_is_permanently_non_authoritative() {
        let receipt = CommitReceipt {
            operation_id: value(2),
            scope_commitment: value(3),
            previous_head: [0; VALUE_BYTES],
            new_head: value(4),
            revision: 1,
            provider_incarnation: value(5),
        };
        let response = GuardianResponse::Outcome(OutcomeResponse {
            request: exact(),
            kind: OutcomeKind::Committed,
            receipt: Some(receipt),
        });
        let encoded = encode_response(response).expect("encode response");
        let decoded = read_response(&mut encoded.as_slice()).expect("decode response");
        assert_eq!(decoded, response);
        assert!(!decoded.grants_authority());
        assert_eq!(decoded.witness_class(), WitnessClass::VolatileLab);

        let mut authority_flip = encoded;
        authority_flip[4 + 137] = 1;
        assert_eq!(
            read_response(&mut authority_flip.as_slice()),
            Err(ProtocolError::InvalidFrame)
        );
    }

    #[test]
    fn session_nonce_binds_both_nonces_and_incarnation() {
        let first = session_nonce(&value(1), &value(2), &value(3));
        assert_ne!(first, session_nonce(&value(9), &value(2), &value(3)));
        assert_ne!(first, session_nonce(&value(1), &value(9), &value(3)));
        assert_ne!(first, session_nonce(&value(1), &value(2), &value(9)));
    }
}
