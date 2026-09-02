//! Canonical, self-contained signed scope for the Invocation Guardian v2 canary.
//!
//! This module is the sole encoder and verifier. The guardian must compare the
//! signed scope with server-observed invocation material; caller-provided
//! commitments are never accepted as an attestation by themselves.

use ring::signature::{Ed25519KeyPair, UnparsedPublicKey, ED25519};
use sha2::{Digest, Sha256};

pub const COMMITMENT_BYTES: usize = 32;
pub const SIGNATURE_BYTES: usize = 64;
pub const MAX_CANARY_TTL_SECS: i64 = 60;
pub const MAX_CANONICAL_ENVELOPE_BYTES: usize = 2048;
pub const CANARY_ISSUANCE_LANE: &str = "protected-marker-canary-v2";
pub const CANARY_TOOL_NAME: &str = "invocation_guardian_canary_write";
pub const CANARY_TRANSPORT_KIND: &str = "stdio";
pub const CANARY_CONNECTION_CONTEXT_KIND: &str = "server-created-stdio-connection-v1";
pub const CANARY_PRINCIPAL_KIND: &str = "bridge-service";
const SCHEMA: &[u8] = b"agent_bridge.invocation_guardian.canary_lease.v2";
const SIGNATURE_DOMAIN: &[u8] = b"agent_bridge.invocation_guardian.canary_signature.v2\0";

pub type Commitment = [u8; COMMITMENT_BYTES];

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct CanaryLeaseScope {
    pub issuance_lane: String,
    pub key_generation: u64,
    pub issuer_key_commitment: Commitment,
    pub ledger_generation: Commitment,
    pub token_commitment: Commitment,
    pub lease_id: String,
    pub tool_name: String,
    pub arguments_jcs_sha256: Commitment,
    pub target_sha256: Commitment,
    pub registry_sha256: Commitment,
    pub namespace: String,
    pub principal_kind: String,
    pub principal_commitment: Commitment,
    pub transport_kind: String,
    pub connection_context_kind: String,
    pub connection_commitment: Commitment,
    pub issued_at_unix: i64,
    pub not_before_unix: i64,
    pub expires_at_unix: i64,
    pub max_uses: u8,
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct SignedCanaryLease {
    pub scope: CanaryLeaseScope,
    pub signature: [u8; SIGNATURE_BYTES],
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct ObservedCanaryInvocation {
    pub tool_name: String,
    pub arguments_jcs_sha256: Commitment,
    pub target_sha256: Commitment,
    pub registry_sha256: Commitment,
    pub namespace: String,
    pub principal_kind: String,
    pub principal_commitment: Commitment,
    pub transport_kind: String,
    pub connection_context_kind: String,
    pub connection_commitment: Commitment,
}

#[derive(Clone, Debug)]
pub struct CanaryTrustPins {
    pub key_generation: u64,
    pub issuer_verify_key: [u8; 32],
    pub issuer_key_commitment: Commitment,
    pub ledger_generation: Commitment,
    pub namespace: String,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, thiserror::Error)]
pub enum ScopeError {
    #[error("invalid_scope")]
    InvalidScope,
    #[error("oversized_scope")]
    Oversized,
    #[error("invalid_signature")]
    InvalidSignature,
    #[error("trust_pin_mismatch")]
    TrustPinMismatch,
    #[error("invocation_mismatch")]
    InvocationMismatch,
    #[error("outside_time_window")]
    OutsideTimeWindow,
    #[error("invalid_encoding")]
    InvalidEncoding,
}

impl CanaryLeaseScope {
    pub fn canonical_bytes(&self) -> Result<Vec<u8>, ScopeError> {
        validate_scope(self)?;
        let mut out = Vec::with_capacity(512);
        field(&mut out, SCHEMA)?;
        field(&mut out, self.issuance_lane.as_bytes())?;
        out.extend_from_slice(&self.key_generation.to_be_bytes());
        fixed_fields(
            &mut out,
            &[
                &self.issuer_key_commitment,
                &self.ledger_generation,
                &self.token_commitment,
            ],
        );
        field(&mut out, self.lease_id.as_bytes())?;
        field(&mut out, self.tool_name.as_bytes())?;
        fixed_fields(
            &mut out,
            &[
                &self.arguments_jcs_sha256,
                &self.target_sha256,
                &self.registry_sha256,
            ],
        );
        field(&mut out, self.namespace.as_bytes())?;
        field(&mut out, self.principal_kind.as_bytes())?;
        out.extend_from_slice(&self.principal_commitment);
        field(&mut out, self.transport_kind.as_bytes())?;
        field(&mut out, self.connection_context_kind.as_bytes())?;
        out.extend_from_slice(&self.connection_commitment);
        out.extend_from_slice(&self.issued_at_unix.to_be_bytes());
        out.extend_from_slice(&self.not_before_unix.to_be_bytes());
        out.extend_from_slice(&self.expires_at_unix.to_be_bytes());
        out.push(self.max_uses);
        if out.len() > MAX_CANONICAL_ENVELOPE_BYTES {
            return Err(ScopeError::Oversized);
        }
        Ok(out)
    }

    pub fn decode_canonical(bytes: &[u8]) -> Result<Self, ScopeError> {
        if bytes.len() > MAX_CANONICAL_ENVELOPE_BYTES {
            return Err(ScopeError::Oversized);
        }
        let mut input = Decoder::new(bytes);
        if input.field()? != SCHEMA {
            return Err(ScopeError::InvalidEncoding);
        }
        let scope = Self {
            issuance_lane: input.string()?,
            key_generation: input.u64()?,
            issuer_key_commitment: input.fixed()?,
            ledger_generation: input.fixed()?,
            token_commitment: input.fixed()?,
            lease_id: input.string()?,
            tool_name: input.string()?,
            arguments_jcs_sha256: input.fixed()?,
            target_sha256: input.fixed()?,
            registry_sha256: input.fixed()?,
            namespace: input.string()?,
            principal_kind: input.string()?,
            principal_commitment: input.fixed()?,
            transport_kind: input.string()?,
            connection_context_kind: input.string()?,
            connection_commitment: input.fixed()?,
            issued_at_unix: input.i64()?,
            not_before_unix: input.i64()?,
            expires_at_unix: input.i64()?,
            max_uses: input.u8()?,
        };
        if !input.done() || scope.canonical_bytes()?.as_slice() != bytes {
            return Err(ScopeError::InvalidEncoding);
        }
        Ok(scope)
    }
}

impl SignedCanaryLease {
    pub fn sign(scope: CanaryLeaseScope, key: &Ed25519KeyPair) -> Result<Self, ScopeError> {
        let message = signature_message(&scope.canonical_bytes()?);
        let raw = key.sign(&message);
        let mut signature = [0; SIGNATURE_BYTES];
        signature.copy_from_slice(raw.as_ref());
        Ok(Self { scope, signature })
    }

    pub fn verify(
        &self,
        pins: &CanaryTrustPins,
        observed: &ObservedCanaryInvocation,
        now_unix: i64,
    ) -> Result<Commitment, ScopeError> {
        let canonical = self.scope.canonical_bytes()?;
        let configured_key_commitment = domain_hash(
            b"agent_bridge.invocation_guardian.issuer_key.v2\0",
            &pins.issuer_verify_key,
        );
        if pins.key_generation != self.scope.key_generation
            || pins.issuer_key_commitment != configured_key_commitment
            || pins.issuer_key_commitment != self.scope.issuer_key_commitment
            || pins.ledger_generation != self.scope.ledger_generation
            || pins.namespace != self.scope.namespace
        {
            return Err(ScopeError::TrustPinMismatch);
        }
        UnparsedPublicKey::new(&ED25519, pins.issuer_verify_key)
            .verify(&signature_message(&canonical), &self.signature)
            .map_err(|_| ScopeError::InvalidSignature)?;
        if now_unix < self.scope.not_before_unix || now_unix >= self.scope.expires_at_unix {
            return Err(ScopeError::OutsideTimeWindow);
        }
        if observed.transport_kind != self.scope.transport_kind
            || observed.connection_context_kind != self.scope.connection_context_kind
            || observed.tool_name != self.scope.tool_name
            || observed.arguments_jcs_sha256 != self.scope.arguments_jcs_sha256
            || observed.target_sha256 != self.scope.target_sha256
            || observed.registry_sha256 != self.scope.registry_sha256
            || observed.namespace != self.scope.namespace
            || observed.principal_kind != self.scope.principal_kind
            || observed.principal_commitment != self.scope.principal_commitment
            || observed.connection_commitment != self.scope.connection_commitment
        {
            return Err(ScopeError::InvocationMismatch);
        }
        Ok(domain_hash(
            b"agent_bridge.invocation_guardian.exact_scope.v2\0",
            &canonical,
        ))
    }
}

pub fn domain_hash(domain: &[u8], value: &[u8]) -> Commitment {
    let mut digest = Sha256::new();
    digest.update(domain);
    digest.update(value);
    digest.finalize().into()
}

fn signature_message(canonical: &[u8]) -> Vec<u8> {
    let mut message = Vec::with_capacity(SIGNATURE_DOMAIN.len() + canonical.len());
    message.extend_from_slice(SIGNATURE_DOMAIN);
    message.extend_from_slice(canonical);
    message
}

fn validate_scope(scope: &CanaryLeaseScope) -> Result<(), ScopeError> {
    let strings = [
        scope.issuance_lane.as_str(),
        scope.lease_id.as_str(),
        scope.tool_name.as_str(),
        scope.namespace.as_str(),
        scope.principal_kind.as_str(),
        scope.transport_kind.as_str(),
        scope.connection_context_kind.as_str(),
    ];
    if scope.key_generation == 0
        || scope.max_uses != 1
        || scope.issuance_lane != CANARY_ISSUANCE_LANE
        || scope.tool_name != CANARY_TOOL_NAME
        || scope.principal_kind != CANARY_PRINCIPAL_KIND
        || scope.transport_kind != CANARY_TRANSPORT_KIND
        || scope.connection_context_kind != CANARY_CONNECTION_CONTEXT_KIND
        || scope.issued_at_unix < 0
        || scope.not_before_unix < scope.issued_at_unix
        || scope.expires_at_unix <= scope.not_before_unix
        || scope.expires_at_unix - scope.not_before_unix > MAX_CANARY_TTL_SECS
        || strings.iter().any(|value| {
            value.is_empty()
                || value.len() > 255
                || !value
                    .bytes()
                    .all(|byte| byte.is_ascii_alphanumeric() || b"._:-/".contains(&byte))
        })
        || [
            scope.issuer_key_commitment,
            scope.ledger_generation,
            scope.token_commitment,
            scope.arguments_jcs_sha256,
            scope.target_sha256,
            scope.registry_sha256,
            scope.principal_commitment,
            scope.connection_commitment,
        ]
        .iter()
        .any(|value| value.iter().all(|byte| *byte == 0))
    {
        return Err(ScopeError::InvalidScope);
    }
    Ok(())
}

fn field(out: &mut Vec<u8>, value: &[u8]) -> Result<(), ScopeError> {
    let length = u16::try_from(value.len()).map_err(|_| ScopeError::Oversized)?;
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
    fn take(&mut self, length: usize) -> Result<&'a [u8], ScopeError> {
        let end = self
            .position
            .checked_add(length)
            .ok_or(ScopeError::InvalidEncoding)?;
        let value = self
            .bytes
            .get(self.position..end)
            .ok_or(ScopeError::InvalidEncoding)?;
        self.position = end;
        Ok(value)
    }
    fn field(&mut self) -> Result<&'a [u8], ScopeError> {
        let length = u16::from_be_bytes(
            self.take(2)?
                .try_into()
                .map_err(|_| ScopeError::InvalidEncoding)?,
        ) as usize;
        self.take(length)
    }
    fn string(&mut self) -> Result<String, ScopeError> {
        String::from_utf8(self.field()?.to_vec()).map_err(|_| ScopeError::InvalidEncoding)
    }
    fn fixed(&mut self) -> Result<Commitment, ScopeError> {
        self.take(COMMITMENT_BYTES)?
            .try_into()
            .map_err(|_| ScopeError::InvalidEncoding)
    }
    fn u64(&mut self) -> Result<u64, ScopeError> {
        Ok(u64::from_be_bytes(
            self.take(8)?
                .try_into()
                .map_err(|_| ScopeError::InvalidEncoding)?,
        ))
    }
    fn i64(&mut self) -> Result<i64, ScopeError> {
        Ok(i64::from_be_bytes(
            self.take(8)?
                .try_into()
                .map_err(|_| ScopeError::InvalidEncoding)?,
        ))
    }
    fn u8(&mut self) -> Result<u8, ScopeError> {
        Ok(*self.take(1)?.first().ok_or(ScopeError::InvalidEncoding)?)
    }
    fn done(&self) -> bool {
        self.position == self.bytes.len()
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use ring::signature::KeyPair as _;
    use sha2::{Digest, Sha256};

    fn key(seed: u8) -> Ed25519KeyPair {
        Ed25519KeyPair::from_seed_unchecked(&[seed; 32]).unwrap()
    }

    fn fixture(
        key: &Ed25519KeyPair,
    ) -> (CanaryLeaseScope, CanaryTrustPins, ObservedCanaryInvocation) {
        let public: [u8; 32] = key.public_key().as_ref().try_into().unwrap();
        let key_commitment =
            domain_hash(b"agent_bridge.invocation_guardian.issuer_key.v2\0", &public);
        let scope = CanaryLeaseScope {
            issuance_lane: CANARY_ISSUANCE_LANE.into(),
            key_generation: 7,
            issuer_key_commitment: key_commitment,
            ledger_generation: [2; 32],
            token_commitment: [3; 32],
            lease_id: "lease-1".into(),
            tool_name: CANARY_TOOL_NAME.into(),
            arguments_jcs_sha256: [4; 32],
            target_sha256: [5; 32],
            registry_sha256: [6; 32],
            namespace: "canary/test".into(),
            principal_kind: CANARY_PRINCIPAL_KIND.into(),
            principal_commitment: [7; 32],
            transport_kind: CANARY_TRANSPORT_KIND.into(),
            connection_context_kind: CANARY_CONNECTION_CONTEXT_KIND.into(),
            connection_commitment: [8; 32],
            issued_at_unix: 100,
            not_before_unix: 101,
            expires_at_unix: 160,
            max_uses: 1,
        };
        let pins = CanaryTrustPins {
            key_generation: 7,
            issuer_verify_key: public,
            issuer_key_commitment: key_commitment,
            ledger_generation: [2; 32],
            namespace: "canary/test".into(),
        };
        let observed = ObservedCanaryInvocation {
            tool_name: scope.tool_name.clone(),
            arguments_jcs_sha256: [4; 32],
            target_sha256: [5; 32],
            registry_sha256: [6; 32],
            namespace: scope.namespace.clone(),
            principal_kind: scope.principal_kind.clone(),
            principal_commitment: [7; 32],
            transport_kind: scope.transport_kind.clone(),
            connection_context_kind: scope.connection_context_kind.clone(),
            connection_commitment: [8; 32],
        };
        (scope, pins, observed)
    }

    #[test]
    fn canonical_round_trip_and_exact_verification() {
        let key = key(31);
        let (scope, pins, observed) = fixture(&key);
        let bytes = scope.canonical_bytes().unwrap();
        assert_eq!(CanaryLeaseScope::decode_canonical(&bytes).unwrap(), scope);
        let digest: [u8; 32] = Sha256::digest(&bytes).into();
        assert_eq!(
            digest,
            [
                88, 97, 194, 102, 240, 54, 66, 246, 226, 229, 220, 147, 183, 55, 149, 83, 25, 163,
                43, 127, 214, 37, 42, 142, 247, 141, 154, 244, 116, 46, 188, 41,
            ]
        );
        assert_ne!(
            SignedCanaryLease::sign(scope, &key)
                .unwrap()
                .verify(&pins, &observed, 120)
                .unwrap(),
            [0; 32]
        );
    }

    #[test]
    fn every_observed_binding_and_trust_pin_fails_closed() {
        let key = key(31);
        let (scope, pins, observed) = fixture(&key);
        let signed = SignedCanaryLease::sign(scope, &key).unwrap();
        let mut cases = Vec::new();
        let mut changed = observed.clone();
        changed.tool_name.push('x');
        cases.push(changed);
        let mut changed = observed.clone();
        changed.arguments_jcs_sha256[0] ^= 1;
        cases.push(changed);
        let mut changed = observed.clone();
        changed.target_sha256[0] ^= 1;
        cases.push(changed);
        let mut changed = observed.clone();
        changed.registry_sha256[0] ^= 1;
        cases.push(changed);
        let mut changed = observed.clone();
        changed.namespace.push('x');
        cases.push(changed);
        let mut changed = observed.clone();
        changed.principal_kind.push('x');
        cases.push(changed);
        let mut changed = observed.clone();
        changed.principal_commitment[0] ^= 1;
        cases.push(changed);
        let mut changed = observed.clone();
        changed.transport_kind = "unix".into();
        cases.push(changed);
        let mut changed = observed.clone();
        changed.connection_context_kind.push('x');
        cases.push(changed);
        let mut changed = observed;
        changed.connection_commitment[0] ^= 1;
        cases.push(changed);
        for changed in cases {
            assert_eq!(
                signed.verify(&pins, &changed, 120),
                Err(ScopeError::InvocationMismatch)
            );
        }
        let mut wrong = pins;
        wrong.namespace.push('x');
        assert_eq!(
            signed.verify(&wrong, &fixture(&key).2, 120),
            Err(ScopeError::TrustPinMismatch)
        );
    }

    #[test]
    fn wrong_key_signature_time_and_noncanonical_bytes_are_rejected() {
        let signing_key = key(31);
        let wrong = key(32);
        let (scope, pins, observed) = fixture(&signing_key);
        let signed = SignedCanaryLease::sign(scope.clone(), &wrong).unwrap();
        assert_eq!(
            signed.verify(&pins, &observed, 120),
            Err(ScopeError::InvalidSignature)
        );
        let signed = SignedCanaryLease::sign(scope, &signing_key).unwrap();
        assert_eq!(
            signed.verify(&pins, &observed, 99),
            Err(ScopeError::OutsideTimeWindow)
        );
        assert_eq!(
            signed.verify(&pins, &observed, 160),
            Err(ScopeError::OutsideTimeWindow)
        );
        let mut bytes = signed.scope.canonical_bytes().unwrap();
        bytes.push(0);
        assert_eq!(
            CanaryLeaseScope::decode_canonical(&bytes),
            Err(ScopeError::InvalidEncoding)
        );

        let (mut zero_ttl, _, _) = fixture(&signing_key);
        zero_ttl.expires_at_unix = zero_ttl.not_before_unix;
        assert_eq!(zero_ttl.canonical_bytes(), Err(ScopeError::InvalidScope));
    }

    #[test]
    fn every_signed_scope_field_is_load_bearing() {
        let key = key(31);
        let (scope, pins, observed) = fixture(&key);
        let signed = SignedCanaryLease::sign(scope, &key).unwrap();
        let mut cases = Vec::new();
        let mut changed = signed.clone();
        changed.scope.issuance_lane.push('x');
        cases.push(changed);
        let mut changed = signed.clone();
        changed.scope.key_generation += 1;
        cases.push(changed);
        let mut changed = signed.clone();
        changed.scope.issuer_key_commitment[0] ^= 1;
        cases.push(changed);
        let mut changed = signed.clone();
        changed.scope.ledger_generation[0] ^= 1;
        cases.push(changed);
        let mut changed = signed.clone();
        changed.scope.token_commitment[0] ^= 1;
        cases.push(changed);
        let mut changed = signed.clone();
        changed.scope.lease_id.push('x');
        cases.push(changed);
        let mut changed = signed.clone();
        changed.scope.tool_name.push('x');
        cases.push(changed);
        let mut changed = signed.clone();
        changed.scope.arguments_jcs_sha256[0] ^= 1;
        cases.push(changed);
        let mut changed = signed.clone();
        changed.scope.target_sha256[0] ^= 1;
        cases.push(changed);
        let mut changed = signed.clone();
        changed.scope.registry_sha256[0] ^= 1;
        cases.push(changed);
        let mut changed = signed.clone();
        changed.scope.namespace.push('x');
        cases.push(changed);
        let mut changed = signed.clone();
        changed.scope.principal_kind.push('x');
        cases.push(changed);
        let mut changed = signed.clone();
        changed.scope.principal_commitment[0] ^= 1;
        cases.push(changed);
        let mut changed = signed.clone();
        changed.scope.transport_kind.push('x');
        cases.push(changed);
        let mut changed = signed.clone();
        changed.scope.connection_context_kind.push('x');
        cases.push(changed);
        let mut changed = signed.clone();
        changed.scope.connection_commitment[0] ^= 1;
        cases.push(changed);
        let mut changed = signed.clone();
        changed.scope.issued_at_unix += 1;
        cases.push(changed);
        let mut changed = signed.clone();
        changed.scope.not_before_unix += 1;
        cases.push(changed);
        let mut changed = signed.clone();
        changed.scope.expires_at_unix -= 1;
        cases.push(changed);
        let mut changed = signed;
        changed.scope.max_uses = 2;
        cases.push(changed);

        for changed in cases {
            assert!(changed.verify(&pins, &observed, 120).is_err());
        }
    }
}
