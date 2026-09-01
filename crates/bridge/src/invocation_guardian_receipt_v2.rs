//! Canonical signed provider receipt for the Invocation Guardian v2 canary.
//!
//! A decoded receipt is only untrusted wire data. `verify` binds it to pinned
//! provider identity and to the exact live request. This module deliberately
//! exposes no dispatch permit or executable handle.

use ring::signature::{Ed25519KeyPair, UnparsedPublicKey, ED25519};

use crate::invocation_lease_scope::{domain_hash, Commitment, SIGNATURE_BYTES};

pub const MAX_CANONICAL_PROVIDER_RECEIPT_BYTES: usize = 2048;
const SCHEMA: &[u8] = b"agent_bridge.invocation_guardian.provider_receipt.v2";
const SIGNATURE_DOMAIN: &[u8] = b"agent_bridge.invocation_guardian.provider_receipt_signature.v2\0";
const PROVIDER_KEY_DOMAIN: &[u8] = b"agent_bridge.invocation_guardian.provider_verify_key.v2\0";

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
#[repr(u8)]
pub enum ReceiptDisposition {
    FreshCommitted = 1,
    AlreadyCommitted = 2,
}

impl ReceiptDisposition {
    fn decode(value: u8) -> Result<Self, ReceiptError> {
        match value {
            1 => Ok(Self::FreshCommitted),
            2 => Ok(Self::AlreadyCommitted),
            _ => Err(ReceiptError::InvalidEncoding),
        }
    }
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct ProviderReceipt {
    pub provider_key_generation: u64,
    pub provider_key_commitment: Commitment,
    pub provider_identity_commitment: Commitment,
    pub namespace: String,
    pub epoch: u64,
    pub revision: u64,
    pub previous_head: Commitment,
    pub new_head: Commitment,
    pub token_commitment: Commitment,
    pub use_index: u8,
    pub exact_scope_commitment: Commitment,
    pub request_challenge: Commitment,
    pub guardian_session_commitment: Commitment,
    pub provider_time_unix: i64,
    pub disposition: ReceiptDisposition,
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct SignedProviderReceipt {
    pub receipt: ProviderReceipt,
    pub signature: [u8; SIGNATURE_BYTES],
}

#[derive(Clone, Debug)]
pub struct ProviderTrustPins {
    pub provider_key_generation: u64,
    pub provider_verify_key: [u8; 32],
    pub provider_key_commitment: Commitment,
    pub provider_identity_commitment: Commitment,
    pub namespace: String,
    pub minimum_epoch: u64,
    pub minimum_revision: u64,
}

#[derive(Clone, Debug)]
pub struct ExpectedProviderReceipt {
    pub disposition: ReceiptDisposition,
    pub token_commitment: Commitment,
    pub exact_scope_commitment: Commitment,
    pub request_challenge: Commitment,
    pub guardian_session_commitment: Commitment,
}

/// Verification product, intentionally non-`Clone` and not a dispatch permit.
#[derive(Debug)]
pub struct VerifiedProviderReceipt {
    receipt: ProviderReceipt,
}

impl VerifiedProviderReceipt {
    pub fn disposition(&self) -> ReceiptDisposition {
        self.receipt.disposition
    }
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, thiserror::Error)]
pub enum ReceiptError {
    #[error("invalid_receipt")]
    InvalidReceipt,
    #[error("oversized_receipt")]
    Oversized,
    #[error("invalid_signature")]
    InvalidSignature,
    #[error("trust_pin_mismatch")]
    TrustPinMismatch,
    #[error("request_binding_mismatch")]
    RequestBindingMismatch,
    #[error("stale_provider_position")]
    StaleProviderPosition,
    #[error("invalid_encoding")]
    InvalidEncoding,
}

impl ProviderReceipt {
    pub fn canonical_bytes(&self) -> Result<Vec<u8>, ReceiptError> {
        validate_receipt(self)?;
        let mut out = Vec::with_capacity(512);
        field(&mut out, SCHEMA)?;
        out.extend_from_slice(&self.provider_key_generation.to_be_bytes());
        fixed_fields(
            &mut out,
            &[
                &self.provider_key_commitment,
                &self.provider_identity_commitment,
            ],
        );
        field(&mut out, self.namespace.as_bytes())?;
        out.extend_from_slice(&self.epoch.to_be_bytes());
        out.extend_from_slice(&self.revision.to_be_bytes());
        fixed_fields(
            &mut out,
            &[&self.previous_head, &self.new_head, &self.token_commitment],
        );
        out.push(self.use_index);
        fixed_fields(
            &mut out,
            &[
                &self.exact_scope_commitment,
                &self.request_challenge,
                &self.guardian_session_commitment,
            ],
        );
        out.extend_from_slice(&self.provider_time_unix.to_be_bytes());
        out.push(self.disposition as u8);
        if out.len() > MAX_CANONICAL_PROVIDER_RECEIPT_BYTES {
            return Err(ReceiptError::Oversized);
        }
        Ok(out)
    }

    pub fn decode_canonical(bytes: &[u8]) -> Result<Self, ReceiptError> {
        if bytes.len() > MAX_CANONICAL_PROVIDER_RECEIPT_BYTES {
            return Err(ReceiptError::Oversized);
        }
        let mut input = Decoder::new(bytes);
        if input.field()? != SCHEMA {
            return Err(ReceiptError::InvalidEncoding);
        }
        let receipt = Self {
            provider_key_generation: input.u64()?,
            provider_key_commitment: input.fixed()?,
            provider_identity_commitment: input.fixed()?,
            namespace: input.string()?,
            epoch: input.u64()?,
            revision: input.u64()?,
            previous_head: input.fixed()?,
            new_head: input.fixed()?,
            token_commitment: input.fixed()?,
            use_index: input.u8()?,
            exact_scope_commitment: input.fixed()?,
            request_challenge: input.fixed()?,
            guardian_session_commitment: input.fixed()?,
            provider_time_unix: input.i64()?,
            disposition: ReceiptDisposition::decode(input.u8()?)?,
        };
        if !input.done() || receipt.canonical_bytes()?.as_slice() != bytes {
            return Err(ReceiptError::InvalidEncoding);
        }
        Ok(receipt)
    }
}

impl SignedProviderReceipt {
    pub fn sign(receipt: ProviderReceipt, key: &Ed25519KeyPair) -> Result<Self, ReceiptError> {
        let message = signature_message(&receipt.canonical_bytes()?);
        let raw = key.sign(&message);
        let mut signature = [0; SIGNATURE_BYTES];
        signature.copy_from_slice(raw.as_ref());
        Ok(Self { receipt, signature })
    }

    pub fn verify(
        self,
        pins: &ProviderTrustPins,
        expected: &ExpectedProviderReceipt,
    ) -> Result<VerifiedProviderReceipt, ReceiptError> {
        let canonical = self.receipt.canonical_bytes()?;
        let configured_key_commitment = domain_hash(PROVIDER_KEY_DOMAIN, &pins.provider_verify_key);
        if pins.provider_key_generation != self.receipt.provider_key_generation
            || pins.provider_key_commitment != configured_key_commitment
            || pins.provider_key_commitment != self.receipt.provider_key_commitment
            || pins.provider_identity_commitment != self.receipt.provider_identity_commitment
            || pins.namespace != self.receipt.namespace
        {
            return Err(ReceiptError::TrustPinMismatch);
        }
        if self.receipt.epoch < pins.minimum_epoch
            || (self.receipt.epoch == pins.minimum_epoch
                && self.receipt.revision < pins.minimum_revision)
        {
            return Err(ReceiptError::StaleProviderPosition);
        }
        if self.receipt.disposition != expected.disposition
            || self.receipt.token_commitment != expected.token_commitment
            || self.receipt.use_index != 1
            || self.receipt.exact_scope_commitment != expected.exact_scope_commitment
            || self.receipt.request_challenge != expected.request_challenge
            || self.receipt.guardian_session_commitment != expected.guardian_session_commitment
        {
            return Err(ReceiptError::RequestBindingMismatch);
        }
        UnparsedPublicKey::new(&ED25519, pins.provider_verify_key)
            .verify(&signature_message(&canonical), &self.signature)
            .map_err(|_| ReceiptError::InvalidSignature)?;
        Ok(VerifiedProviderReceipt {
            receipt: self.receipt,
        })
    }
}

pub fn provider_key_commitment(verify_key: &[u8; 32]) -> Commitment {
    domain_hash(PROVIDER_KEY_DOMAIN, verify_key)
}

fn signature_message(canonical: &[u8]) -> Vec<u8> {
    let mut message = Vec::with_capacity(SIGNATURE_DOMAIN.len() + canonical.len());
    message.extend_from_slice(SIGNATURE_DOMAIN);
    message.extend_from_slice(canonical);
    message
}

fn validate_receipt(receipt: &ProviderReceipt) -> Result<(), ReceiptError> {
    if receipt.provider_key_generation == 0
        || receipt.namespace.is_empty()
        || receipt.namespace.len() > 255
        || !receipt
            .namespace
            .bytes()
            .all(|byte| byte.is_ascii_alphanumeric() || b"._:-/".contains(&byte))
        || receipt.epoch == 0
        || receipt.revision == 0
        || receipt.use_index != 1
        || receipt.provider_time_unix < 0
        || receipt.previous_head == receipt.new_head
        || [
            receipt.provider_key_commitment,
            receipt.provider_identity_commitment,
            receipt.previous_head,
            receipt.new_head,
            receipt.token_commitment,
            receipt.exact_scope_commitment,
            receipt.request_challenge,
            receipt.guardian_session_commitment,
        ]
        .iter()
        .any(|value| value.iter().all(|byte| *byte == 0))
    {
        return Err(ReceiptError::InvalidReceipt);
    }
    Ok(())
}

fn field(out: &mut Vec<u8>, value: &[u8]) -> Result<(), ReceiptError> {
    let length = u16::try_from(value.len()).map_err(|_| ReceiptError::Oversized)?;
    out.extend_from_slice(&length.to_be_bytes());
    out.extend_from_slice(value);
    Ok(())
}

fn fixed_fields(out: &mut Vec<u8>, values: &[&Commitment]) {
    for value in values {
        out.extend_from_slice(value.as_slice());
    }
}

struct Decoder<'a> {
    bytes: &'a [u8],
    position: usize,
}

impl<'a> Decoder<'a> {
    fn new(bytes: &'a [u8]) -> Self {
        Self { bytes, position: 0 }
    }

    fn take(&mut self, length: usize) -> Result<&'a [u8], ReceiptError> {
        let end = self
            .position
            .checked_add(length)
            .ok_or(ReceiptError::InvalidEncoding)?;
        let value = self
            .bytes
            .get(self.position..end)
            .ok_or(ReceiptError::InvalidEncoding)?;
        self.position = end;
        Ok(value)
    }

    fn field(&mut self) -> Result<&'a [u8], ReceiptError> {
        let length = u16::from_be_bytes(
            self.take(2)?
                .try_into()
                .map_err(|_| ReceiptError::InvalidEncoding)?,
        ) as usize;
        self.take(length)
    }

    fn string(&mut self) -> Result<String, ReceiptError> {
        String::from_utf8(self.field()?.to_vec()).map_err(|_| ReceiptError::InvalidEncoding)
    }

    fn fixed(&mut self) -> Result<Commitment, ReceiptError> {
        self.take(32)?
            .try_into()
            .map_err(|_| ReceiptError::InvalidEncoding)
    }

    fn u64(&mut self) -> Result<u64, ReceiptError> {
        Ok(u64::from_be_bytes(
            self.take(8)?
                .try_into()
                .map_err(|_| ReceiptError::InvalidEncoding)?,
        ))
    }

    fn i64(&mut self) -> Result<i64, ReceiptError> {
        Ok(i64::from_be_bytes(
            self.take(8)?
                .try_into()
                .map_err(|_| ReceiptError::InvalidEncoding)?,
        ))
    }

    fn u8(&mut self) -> Result<u8, ReceiptError> {
        Ok(*self.take(1)?.first().ok_or(ReceiptError::InvalidEncoding)?)
    }

    fn done(&self) -> bool {
        self.position == self.bytes.len()
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use ring::signature::{Ed25519KeyPair, KeyPair as _};
    use sha2::{Digest, Sha256};

    fn key(seed: u8) -> Ed25519KeyPair {
        Ed25519KeyPair::from_seed_unchecked(&[seed; 32]).unwrap()
    }

    fn fixture(
        disposition: ReceiptDisposition,
    ) -> (
        SignedProviderReceipt,
        ProviderTrustPins,
        ExpectedProviderReceipt,
    ) {
        let key = key(11);
        let public: [u8; 32] = key.public_key().as_ref().try_into().unwrap();
        let receipt = ProviderReceipt {
            provider_key_generation: 3,
            provider_key_commitment: provider_key_commitment(&public),
            provider_identity_commitment: [2; 32],
            namespace: "canary/test".into(),
            epoch: 7,
            revision: 19,
            previous_head: [3; 32],
            new_head: [4; 32],
            token_commitment: [5; 32],
            use_index: 1,
            exact_scope_commitment: [6; 32],
            request_challenge: [7; 32],
            guardian_session_commitment: [8; 32],
            provider_time_unix: 1_788_261_200,
            disposition,
        };
        let pins = ProviderTrustPins {
            provider_key_generation: 3,
            provider_verify_key: public,
            provider_key_commitment: provider_key_commitment(&public),
            provider_identity_commitment: [2; 32],
            namespace: "canary/test".into(),
            minimum_epoch: 7,
            minimum_revision: 18,
        };
        let expected = ExpectedProviderReceipt {
            disposition,
            token_commitment: [5; 32],
            exact_scope_commitment: [6; 32],
            request_challenge: [7; 32],
            guardian_session_commitment: [8; 32],
        };
        (
            SignedProviderReceipt::sign(receipt, &key).unwrap(),
            pins,
            expected,
        )
    }

    #[test]
    fn canonical_round_trip_signature_and_golden_digest() {
        let (signed, pins, expected) = fixture(ReceiptDisposition::FreshCommitted);
        let canonical = signed.receipt.canonical_bytes().unwrap();
        assert_eq!(
            ProviderReceipt::decode_canonical(&canonical).unwrap(),
            signed.receipt
        );
        let digest: [u8; 32] = Sha256::digest(&canonical).into();
        assert_eq!(
            digest,
            [
                246, 110, 124, 114, 134, 157, 187, 153, 30, 200, 72, 50, 42, 154, 67, 210, 179, 22,
                69, 185, 54, 217, 45, 145, 90, 86, 110, 62, 204, 108, 220, 206,
            ]
        );
        assert_eq!(
            signed.verify(&pins, &expected).unwrap().disposition(),
            ReceiptDisposition::FreshCommitted
        );
    }

    #[test]
    fn every_request_binding_and_pin_fails_closed() {
        let (signed, pins, expected) = fixture(ReceiptDisposition::FreshCommitted);
        let mut expected_cases = Vec::new();
        let mut changed = expected.clone();
        changed.disposition = ReceiptDisposition::AlreadyCommitted;
        expected_cases.push(changed);
        let mut changed = expected.clone();
        changed.token_commitment[0] ^= 1;
        expected_cases.push(changed);
        let mut changed = expected.clone();
        changed.exact_scope_commitment[0] ^= 1;
        expected_cases.push(changed);
        let mut changed = expected.clone();
        changed.request_challenge[0] ^= 1;
        expected_cases.push(changed);
        let mut changed = expected;
        changed.guardian_session_commitment[0] ^= 1;
        expected_cases.push(changed);
        for changed in expected_cases {
            assert_eq!(
                signed.clone().verify(&pins, &changed).unwrap_err(),
                ReceiptError::RequestBindingMismatch
            );
        }

        let mut wrong = pins.clone();
        wrong.namespace.push('x');
        assert_eq!(
            signed
                .clone()
                .verify(&wrong, &fixture(ReceiptDisposition::FreshCommitted).2)
                .unwrap_err(),
            ReceiptError::TrustPinMismatch
        );
        let mut stale = pins;
        stale.minimum_revision = 20;
        assert_eq!(
            signed
                .verify(&stale, &fixture(ReceiptDisposition::FreshCommitted).2)
                .unwrap_err(),
            ReceiptError::StaleProviderPosition
        );
    }

    #[test]
    fn signature_field_mutation_and_noncanonical_bytes_are_rejected() {
        let (signed, pins, expected) = fixture(ReceiptDisposition::FreshCommitted);
        let mut wrong_key = signed.clone();
        wrong_key.signature[0] ^= 1;
        assert_eq!(
            wrong_key.verify(&pins, &expected).unwrap_err(),
            ReceiptError::InvalidSignature
        );

        let mut cases = Vec::new();
        let mut changed = signed.clone();
        changed.receipt.provider_key_generation += 1;
        cases.push(changed);
        let mut changed = signed.clone();
        changed.receipt.provider_key_commitment[0] ^= 1;
        cases.push(changed);
        let mut changed = signed.clone();
        changed.receipt.provider_identity_commitment[0] ^= 1;
        cases.push(changed);
        let mut changed = signed.clone();
        changed.receipt.namespace.push('x');
        cases.push(changed);
        let mut changed = signed.clone();
        changed.receipt.epoch += 1;
        cases.push(changed);
        let mut changed = signed.clone();
        changed.receipt.revision += 1;
        cases.push(changed);
        let mut changed = signed.clone();
        changed.receipt.previous_head[0] ^= 1;
        cases.push(changed);
        let mut changed = signed.clone();
        changed.receipt.new_head[0] ^= 1;
        cases.push(changed);
        let mut changed = signed.clone();
        changed.receipt.token_commitment[0] ^= 1;
        cases.push(changed);
        let mut changed = signed.clone();
        changed.receipt.use_index = 2;
        cases.push(changed);
        let mut changed = signed.clone();
        changed.receipt.exact_scope_commitment[0] ^= 1;
        cases.push(changed);
        let mut changed = signed.clone();
        changed.receipt.request_challenge[0] ^= 1;
        cases.push(changed);
        let mut changed = signed.clone();
        changed.receipt.guardian_session_commitment[0] ^= 1;
        cases.push(changed);
        let mut changed = signed.clone();
        changed.receipt.provider_time_unix += 1;
        cases.push(changed);
        let mut changed = signed.clone();
        changed.receipt.disposition = ReceiptDisposition::AlreadyCommitted;
        cases.push(changed);
        for changed in cases {
            assert!(changed.verify(&pins, &expected).is_err());
        }

        let mut bytes = signed.receipt.canonical_bytes().unwrap();
        bytes.push(0);
        assert_eq!(
            ProviderReceipt::decode_canonical(&bytes),
            Err(ReceiptError::InvalidEncoding)
        );
    }
}
