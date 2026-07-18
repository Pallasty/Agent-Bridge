//! Synthetic-only G1 authenticated-envelope implementation prerequisite.
//!
//! This module deliberately has no public export and is disabled by default.
//! It performs no filesystem, environment, clock, process, database, network,
//! key-loading, custody, replay-claim, capability-minting, or runtime work. A
//! successful result proves only that one synthetic envelope conforms to the
//! frozen canonicalization, trust-anchor, binding, and signature rules. It is
//! never corpus-freeze authority and cannot open G1.4.

#![cfg_attr(not(test), allow(dead_code))]

use ring::signature::{UnparsedPublicKey, ED25519};
use serde_json::{Map, Value};
use sha2::{Digest, Sha256};
use std::collections::BTreeSet;

const MAX_DOCUMENT_BYTES: usize = 65_536;
const MAX_NESTING_DEPTH: usize = 16;
const MAX_STRING_BYTES: usize = 4_096;
const MAX_KEY_BYTES: usize = 128;
const MAX_ARRAY_ITEMS: usize = 64;
const MAX_OBJECT_KEYS: usize = 64;
const MAX_SYNTHETIC_MANIFEST_BYTES: usize = 65_536;
const MAX_JCS_SAFE_INTEGER: u64 = 9_007_199_254_740_991;
const REQUIRED_SIGNATURE_COUNT: usize = 5;
const MAX_ENVELOPE_AGE_SECS: u64 = 86_400;

const ENVELOPE_SCHEMA: &str =
    "agent_bridge.engram_g1_authenticated_freeze_authority_synthetic_envelope.v0";
const ENVELOPE_KIND: &str = "synthetic_implementation_prerequisite_test_vector_only";
const CANONICAL_PROFILE: &str = "agent_bridge_rfc8785_compatible_ascii_safe_integer_subset_v1";
const MESSAGE_PROFILE: &str =
    "u32be_framed_profile_domain_role_key_id_u64be_epoch_and_canonical_envelope_frame_v1";
const ANCHOR_SET_COMMITMENT_DOMAIN: &str =
    "agent-bridge/engram/g1/authenticated-freeze-authority/synthetic-anchor-set-commitment/v0";
const STAGE: &str = "g1_authenticated_freeze_authority_envelope_shadow_synthetic_only";
const EVIDENCE_CLASS: &str = "synthetic_test_vector_only";
const IMPLEMENTATION_PROFILE: &str = "ab_store_engram_g1_auth_envelope_shadow_v0";
const ADAPTER_CONTRACT_VERSION: &str =
    "engram_g1_authenticated_freeze_authority_adapter_preregistration_v0";

const PREREGISTRATION_COMMIT: &str = "632918db75f65030d3ac15bc991b51a9c938cba6";
const PREREGISTRATION_CONTRACT_SHA256: &str =
    "a9d267056fac1662b478d929b011ef971b309db60182f0f1c7563624571945c0";
const PREREGISTRATION_VALIDATOR_SHA256: &str =
    "632f93b9c9bfcedeca81916ed34be6b4ce8b7b03b916c060b2d1999d06597fde";
const PREREGISTRATION_CHECKER_SHA256: &str =
    "ea8ac0126306de517175a3dffa2a3722439b93b10a3d9d112ca1732f553e6f29";
const G1_3_COMMIT: &str = "7062869196d1a3ff8bb72572a39700e65130cde4";
const G1_3_CONTRACT_SHA256: &str =
    "5657ac8f4b6fd4f154de7285fd4a62125bf4ea15cba787d25da40701a3ac1504";
const G1_3_VALIDATOR_SHA256: &str =
    "0b7cb3295bc3690bbfeee033de2ddf27a39eb71d0cec68f96e9b27b1a67ef089";
const G1_3_CHECKER_SHA256: &str =
    "e56a6f50a2c0372d0d59390e8792bc4269c4f63e282d49cf1a1bfe1fdd463e39";

const ENVELOPE_KEYS: &[&str] = &[
    "canonicalization",
    "envelope_kind",
    "payload",
    "schema",
    "signature_message_profile",
    "signatures",
];
const SIGNING_FRAME_KEYS: &[&str] = &[
    "canonicalization",
    "envelope_kind",
    "payload",
    "schema",
    "signature_message_profile",
];
const SIGNATURE_KEYS: &[&str] = &[
    "detached_signature_hex",
    "key_epoch",
    "key_id",
    "role",
    "signature_algorithm",
    "signature_domain",
    "signed_message_sha256",
];
const PAYLOAD_KEYS: &[&str] = &[
    "adapter_contract_version",
    "anchor_set_commitment_sha256",
    "boot_epoch_sha256",
    "capability_minted",
    "durable_replay_claim_verified",
    "durable_trust_ledger_verified",
    "evidence_class",
    "expires_at_unix",
    "freeze_authority_verified",
    "g1_3_checker_sha256",
    "g1_3_commit",
    "g1_3_contract_sha256",
    "g1_3_input_packet_sha256s_in_order",
    "g1_3_validator_sha256",
    "implementation_profile",
    "issued_at_unix",
    "nonce_hex",
    "preregistration_checker_sha256",
    "preregistration_commit",
    "preregistration_contract_sha256",
    "preregistration_validator_sha256",
    "private_manifest_byte_length",
    "private_manifest_sha256",
    "ready_for_g1_4_candidate_protocol_preregistration",
    "repository_identity_sha256",
    "runtime_authority",
    "scope_identity_sha256",
    "secure_custody_capture_verified",
    "sequence",
    "signed_time_checkpoint_sha256",
    "stage",
    "synthetic_test_vector_only",
    "trusted_time_verified",
    "trust_ledger_revision",
];

#[derive(Debug, thiserror::Error)]
#[error("{code}: {detail}")]
struct SyntheticEnvelopeError {
    code: &'static str,
    detail: &'static str,
}

impl SyntheticEnvelopeError {
    #[cfg(test)]
    fn code(&self) -> &'static str {
        self.code
    }
}

type EnvelopeResult<T> = Result<T, SyntheticEnvelopeError>;

fn envelope_error(code: &'static str, detail: &'static str) -> SyntheticEnvelopeError {
    SyntheticEnvelopeError { code, detail }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord)]
enum SignerRole {
    ApplicationOwner,
    IndependenceAuditor,
    FreezeReviewer1,
    FreezeReviewer2,
    SealedEvaluatorCustodian,
}

impl SignerRole {
    const REQUIRED: [Self; REQUIRED_SIGNATURE_COUNT] = [
        Self::ApplicationOwner,
        Self::IndependenceAuditor,
        Self::FreezeReviewer1,
        Self::FreezeReviewer2,
        Self::SealedEvaluatorCustodian,
    ];

    fn as_str(self) -> &'static str {
        match self {
            Self::ApplicationOwner => "application_owner",
            Self::IndependenceAuditor => "independence_auditor",
            Self::FreezeReviewer1 => "freeze_reviewer_1",
            Self::FreezeReviewer2 => "freeze_reviewer_2",
            Self::SealedEvaluatorCustodian => "sealed_evaluator_custodian",
        }
    }

    fn domain(self) -> &'static str {
        match self {
            Self::ApplicationOwner => {
                "agent-bridge/engram/g1/authenticated-freeze-authority/application-owner/v0"
            }
            Self::IndependenceAuditor => {
                "agent-bridge/engram/g1/authenticated-freeze-authority/independence-auditor/v0"
            }
            Self::FreezeReviewer1 => {
                "agent-bridge/engram/g1/authenticated-freeze-authority/freeze-reviewer-1/v0"
            }
            Self::FreezeReviewer2 => {
                "agent-bridge/engram/g1/authenticated-freeze-authority/freeze-reviewer-2/v0"
            }
            Self::SealedEvaluatorCustodian => {
                "agent-bridge/engram/g1/authenticated-freeze-authority/sealed-evaluator-custodian/v0"
            }
        }
    }
}

#[derive(Debug, Clone)]
struct SyntheticTrustAnchorV1 {
    role: SignerRole,
    key_id: String,
    key_epoch: u64,
    public_key: [u8; 32],
    signer_identity_commitment_sha256: [u8; 32],
    revoked: bool,
}

#[derive(Debug, Clone)]
struct SyntheticTrustLedgerV1 {
    revision: u64,
    rollback_floor_revision: u64,
    repository_identity_sha256: [u8; 32],
    scope_identity_sha256: [u8; 32],
    anchors: Vec<SyntheticTrustAnchorV1>,
    synthetic_in_memory_only: bool,
    supplied_outside_envelope: bool,
}

#[derive(Debug, Clone)]
struct ExpectedSyntheticEnvelopeBindingV1 {
    anchor_set_commitment_sha256: [u8; 32],
    repository_identity_sha256: [u8; 32],
    scope_identity_sha256: [u8; 32],
    g1_3_input_packet_sha256s_in_order: [[u8; 32]; REQUIRED_SIGNATURE_COUNT],
    private_manifest_sha256: [u8; 32],
    private_manifest_byte_length: u64,
    nonce: [u8; 32],
    sequence: u64,
    issued_at_unix: u64,
    expires_at_unix: u64,
    boot_epoch_sha256: [u8; 32],
    signed_time_checkpoint_sha256: [u8; 32],
    trust_ledger_revision: u64,
}

#[must_use = "synthetic conformance is not authority and must be inspected"]
#[derive(Debug, PartialEq, Eq)]
struct SyntheticEnvelopeConformanceV1 {
    envelope_sha256: [u8; 32],
    signing_frame_sha256: [u8; 32],
    verified_signature_count: usize,
    synthetic_signature_conformance_verified: bool,
    synthetic_packet_independent_anchor_match: bool,
    synthetic_manifest_bytes_hash_and_length_match: bool,
    secure_custody_capture_verified: bool,
    durable_trust_ledger_verified: bool,
    trusted_time_verified: bool,
    durable_replay_claim_verified: bool,
    capability_minted: bool,
    freeze_authority_verified: bool,
    ready_for_g1_4_candidate_protocol_preregistration: bool,
    runtime_authority: bool,
}

fn sha256_bytes(bytes: &[u8]) -> [u8; 32] {
    Sha256::digest(bytes).into()
}

fn encode_hex(bytes: &[u8]) -> String {
    const HEX: &[u8; 16] = b"0123456789abcdef";
    let mut output = String::with_capacity(bytes.len() * 2);
    for byte in bytes {
        output.push(HEX[(byte >> 4) as usize] as char);
        output.push(HEX[(byte & 0x0f) as usize] as char);
    }
    output
}

fn nonzero(bytes: &[u8]) -> bool {
    bytes.iter().any(|byte| *byte != 0)
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

fn decode_hex_fixed<const N: usize>(value: &str) -> EnvelopeResult<[u8; N]> {
    if value.len() != N * 2
        || !value
            .bytes()
            .all(|byte| byte.is_ascii_digit() || (b'a'..=b'f').contains(&byte))
    {
        return Err(envelope_error(
            "engram_shadow_hex",
            "fixed-width lowercase hexadecimal field is malformed",
        ));
    }
    let mut output = [0_u8; N];
    for (index, byte) in output.iter_mut().enumerate() {
        let offset = index * 2;
        let nibble = |input: u8| -> u8 {
            if input.is_ascii_digit() {
                input - b'0'
            } else {
                input - b'a' + 10
            }
        };
        *byte = (nibble(value.as_bytes()[offset]) << 4) | nibble(value.as_bytes()[offset + 1]);
    }
    Ok(output)
}

fn validate_restricted_jcs_value(value: &Value, depth: usize) -> EnvelopeResult<()> {
    if depth > MAX_NESTING_DEPTH {
        return Err(envelope_error(
            "engram_shadow_jcs_depth",
            "restricted JCS value exceeds the nesting bound",
        ));
    }
    match value {
        Value::Null | Value::Bool(_) => Ok(()),
        Value::Number(number)
            if number
                .as_u64()
                .is_some_and(|integer| integer <= MAX_JCS_SAFE_INTEGER) =>
        {
            Ok(())
        }
        Value::Number(_) => Err(envelope_error(
            "engram_shadow_jcs_number",
            "restricted JCS accepts only nonnegative IEEE-754 safe integers",
        )),
        Value::String(string) if string.is_ascii() && string.len() <= MAX_STRING_BYTES => Ok(()),
        Value::String(_) => Err(envelope_error(
            "engram_shadow_jcs_string",
            "restricted JCS accepts only bounded ASCII strings",
        )),
        Value::Array(values) => {
            if values.len() > MAX_ARRAY_ITEMS {
                return Err(envelope_error(
                    "engram_shadow_jcs_array",
                    "restricted JCS array exceeds the item bound",
                ));
            }
            for item in values {
                validate_restricted_jcs_value(item, depth + 1)?;
            }
            Ok(())
        }
        Value::Object(values) => {
            if values.len() > MAX_OBJECT_KEYS {
                return Err(envelope_error(
                    "engram_shadow_jcs_object",
                    "restricted JCS object exceeds the key-count bound",
                ));
            }
            for (key, item) in values {
                if !key.is_ascii() || key.len() > MAX_KEY_BYTES {
                    return Err(envelope_error(
                        "engram_shadow_jcs_key",
                        "restricted JCS accepts only bounded ASCII object keys",
                    ));
                }
                validate_restricted_jcs_value(item, depth + 1)?;
            }
            Ok(())
        }
    }
}

fn sort_object_keys(value: &mut Value) {
    match value {
        Value::Array(values) => {
            for item in values {
                sort_object_keys(item);
            }
        }
        Value::Object(values) => {
            for item in values.values_mut() {
                sort_object_keys(item);
            }
            values.sort_keys();
        }
        _ => {}
    }
}

fn restricted_jcs_bytes(value: &Value) -> EnvelopeResult<Vec<u8>> {
    validate_restricted_jcs_value(value, 0)?;
    let mut sorted = value.clone();
    sort_object_keys(&mut sorted);
    let bytes = serde_json::to_vec(&sorted).map_err(|_| {
        envelope_error(
            "engram_shadow_jcs_encode",
            "restricted JCS value cannot be encoded",
        )
    })?;
    if bytes.len() > MAX_DOCUMENT_BYTES {
        return Err(envelope_error(
            "engram_shadow_jcs_size",
            "restricted JCS document exceeds 64 KiB",
        ));
    }
    Ok(bytes)
}

fn parse_restricted_jcs(raw: &[u8]) -> EnvelopeResult<Value> {
    if raw.len() > MAX_DOCUMENT_BYTES {
        return Err(envelope_error(
            "engram_shadow_jcs_size",
            "restricted JCS document exceeds 64 KiB",
        ));
    }
    let value: Value = serde_json::from_slice(raw).map_err(|_| {
        envelope_error(
            "engram_shadow_jcs_parse",
            "restricted JCS document cannot be parsed",
        )
    })?;
    if restricted_jcs_bytes(&value)? != raw {
        return Err(envelope_error(
            "engram_shadow_jcs_bytes",
            "input is not exact RFC 8785-compatible restricted canonical bytes",
        ));
    }
    Ok(value)
}

fn object<'a>(value: &'a Value, code: &'static str) -> EnvelopeResult<&'a Map<String, Value>> {
    value
        .as_object()
        .ok_or_else(|| envelope_error(code, "expected a closed canonical JSON object"))
}

fn exact_keys(
    value: &Map<String, Value>,
    expected: &[&str],
    code: &'static str,
) -> EnvelopeResult<()> {
    let actual: BTreeSet<&str> = value.keys().map(String::as_str).collect();
    let expected: BTreeSet<&str> = expected.iter().copied().collect();
    if actual != expected {
        return Err(envelope_error(
            code,
            "closed object key set does not match the frozen contract",
        ));
    }
    Ok(())
}

fn string<'a>(value: &'a Map<String, Value>, key: &str) -> EnvelopeResult<&'a str> {
    value
        .get(key)
        .and_then(Value::as_str)
        .ok_or_else(|| envelope_error("engram_shadow_field_type", "required text field is absent"))
}

fn integer(value: &Map<String, Value>, key: &str) -> EnvelopeResult<u64> {
    value
        .get(key)
        .and_then(Value::as_u64)
        .filter(|integer| *integer <= MAX_JCS_SAFE_INTEGER)
        .ok_or_else(|| {
            envelope_error(
                "engram_shadow_field_type",
                "required safe-integer field is absent",
            )
        })
}

fn boolean(value: &Map<String, Value>, key: &str) -> EnvelopeResult<bool> {
    value
        .get(key)
        .and_then(Value::as_bool)
        .ok_or_else(|| envelope_error("engram_shadow_field_type", "required bool field is absent"))
}

fn require_string(
    value: &Map<String, Value>,
    key: &str,
    expected: &str,
    code: &'static str,
) -> EnvelopeResult<()> {
    if string(value, key)? != expected {
        return Err(envelope_error(code, "frozen text binding drifted"));
    }
    Ok(())
}

fn require_bool(
    value: &Map<String, Value>,
    key: &str,
    expected: bool,
    code: &'static str,
) -> EnvelopeResult<()> {
    if boolean(value, key)? != expected {
        return Err(envelope_error(code, "frozen boolean boundary drifted"));
    }
    Ok(())
}

fn append_u32_frame(message: &mut Vec<u8>, value: &[u8]) -> EnvelopeResult<()> {
    let length = u32::try_from(value.len()).map_err(|_| {
        envelope_error(
            "engram_shadow_message_size",
            "signature message component exceeds u32 framing",
        )
    })?;
    message.extend_from_slice(&length.to_be_bytes());
    message.extend_from_slice(value);
    Ok(())
}

fn signed_message(
    role: SignerRole,
    key_id: &str,
    key_epoch: u64,
    canonical_signing_frame: &[u8],
) -> EnvelopeResult<Vec<u8>> {
    let mut message = Vec::with_capacity(canonical_signing_frame.len() + 256);
    append_u32_frame(&mut message, MESSAGE_PROFILE.as_bytes())?;
    append_u32_frame(&mut message, role.domain().as_bytes())?;
    append_u32_frame(&mut message, role.as_str().as_bytes())?;
    append_u32_frame(&mut message, key_id.as_bytes())?;
    message.extend_from_slice(&key_epoch.to_be_bytes());
    append_u32_frame(&mut message, canonical_signing_frame)?;
    Ok(message)
}

fn synthetic_anchor_set_commitment(ledger: &SyntheticTrustLedgerV1) -> EnvelopeResult<[u8; 32]> {
    let anchors = ledger
        .anchors
        .iter()
        .map(|anchor| {
            serde_json::json!({
                "ed25519_public_key_hex": encode_hex(&anchor.public_key),
                "key_epoch": anchor.key_epoch,
                "key_id": anchor.key_id,
                "role": anchor.role.as_str(),
                "signer_identity_commitment_sha256": encode_hex(
                    &anchor.signer_identity_commitment_sha256
                ),
            })
        })
        .collect::<Vec<_>>();
    let frame = serde_json::json!({
        "anchors_in_role_order": anchors,
        "repository_identity_sha256": encode_hex(&ledger.repository_identity_sha256),
        "scope_identity_sha256": encode_hex(&ledger.scope_identity_sha256),
        "trust_ledger_revision": ledger.revision,
    });
    let canonical = restricted_jcs_bytes(&frame)?;
    let mut message = Vec::with_capacity(canonical.len() + 128);
    append_u32_frame(&mut message, ANCHOR_SET_COMMITMENT_DOMAIN.as_bytes())?;
    append_u32_frame(&mut message, &canonical)?;
    Ok(sha256_bytes(&message))
}

fn signing_frame(envelope: &Map<String, Value>) -> EnvelopeResult<Value> {
    let mut frame = Map::new();
    for key in SIGNING_FRAME_KEYS {
        frame.insert(
            (*key).to_owned(),
            envelope.get(*key).cloned().ok_or_else(|| {
                envelope_error(
                    "engram_shadow_envelope_fields",
                    "signing-frame field is absent",
                )
            })?,
        );
    }
    Ok(Value::Object(frame))
}

fn validate_trust_ledger(
    ledger: &SyntheticTrustLedgerV1,
    expected: &ExpectedSyntheticEnvelopeBindingV1,
) -> EnvelopeResult<()> {
    if !ledger.synthetic_in_memory_only || !ledger.supplied_outside_envelope {
        return Err(envelope_error(
            "engram_shadow_trust_source",
            "shadow trust anchors must be synthetic, in memory, and supplied outside the envelope",
        ));
    }
    if ledger.revision == 0
        || ledger.revision != expected.trust_ledger_revision
        || ledger.revision < ledger.rollback_floor_revision
    {
        return Err(envelope_error(
            "engram_shadow_trust_revision",
            "synthetic trust revision is stale, zero, or mismatched",
        ));
    }
    if ledger.repository_identity_sha256 != expected.repository_identity_sha256
        || ledger.scope_identity_sha256 != expected.scope_identity_sha256
    {
        return Err(envelope_error(
            "engram_shadow_trust_scope",
            "synthetic trust anchor repository or scope binding mismatched",
        ));
    }
    if ledger.anchors.len() != REQUIRED_SIGNATURE_COUNT {
        return Err(envelope_error(
            "engram_shadow_trust_quorum",
            "synthetic trust ledger must contain exactly five anchors",
        ));
    }
    let mut roles = BTreeSet::new();
    let mut key_ids = BTreeSet::new();
    let mut public_keys = BTreeSet::new();
    let mut signer_identities = BTreeSet::new();
    for (index, anchor) in ledger.anchors.iter().enumerate() {
        if anchor.role != SignerRole::REQUIRED[index]
            || !roles.insert(anchor.role)
            || !valid_label(&anchor.key_id)
            || !key_ids.insert(anchor.key_id.as_str())
            || !nonzero(&anchor.public_key)
            || !public_keys.insert(anchor.public_key)
            || !nonzero(&anchor.signer_identity_commitment_sha256)
            || !signer_identities.insert(anchor.signer_identity_commitment_sha256)
            || anchor.key_epoch == 0
            || anchor.revoked
        {
            return Err(envelope_error(
                "engram_shadow_trust_anchor",
                "synthetic trust anchor role, key, epoch, order, or revocation state is invalid",
            ));
        }
    }
    if synthetic_anchor_set_commitment(ledger)? != expected.anchor_set_commitment_sha256 {
        return Err(envelope_error(
            "engram_shadow_anchor_set_commitment",
            "synthetic anchor set does not match the independently supplied commitment",
        ));
    }
    Ok(())
}

fn validate_payload(
    payload: &Map<String, Value>,
    expected: &ExpectedSyntheticEnvelopeBindingV1,
    synthetic_manifest_bytes: &[u8],
) -> EnvelopeResult<Vec<[u8; 32]>> {
    exact_keys(payload, PAYLOAD_KEYS, "engram_shadow_payload_fields")?;
    require_string(
        payload,
        "adapter_contract_version",
        ADAPTER_CONTRACT_VERSION,
        "engram_shadow_adapter_version",
    )?;
    require_string(
        payload,
        "evidence_class",
        EVIDENCE_CLASS,
        "engram_shadow_evidence_class",
    )?;
    require_string(
        payload,
        "implementation_profile",
        IMPLEMENTATION_PROFILE,
        "engram_shadow_implementation_profile",
    )?;
    require_string(payload, "stage", STAGE, "engram_shadow_stage")?;
    require_string(
        payload,
        "preregistration_commit",
        PREREGISTRATION_COMMIT,
        "engram_shadow_preregistration",
    )?;
    require_string(
        payload,
        "preregistration_contract_sha256",
        PREREGISTRATION_CONTRACT_SHA256,
        "engram_shadow_preregistration",
    )?;
    require_string(
        payload,
        "preregistration_validator_sha256",
        PREREGISTRATION_VALIDATOR_SHA256,
        "engram_shadow_preregistration",
    )?;
    require_string(
        payload,
        "preregistration_checker_sha256",
        PREREGISTRATION_CHECKER_SHA256,
        "engram_shadow_preregistration",
    )?;
    require_string(payload, "g1_3_commit", G1_3_COMMIT, "engram_shadow_g1_3")?;
    require_string(
        payload,
        "g1_3_contract_sha256",
        G1_3_CONTRACT_SHA256,
        "engram_shadow_g1_3",
    )?;
    require_string(
        payload,
        "g1_3_validator_sha256",
        G1_3_VALIDATOR_SHA256,
        "engram_shadow_g1_3",
    )?;
    require_string(
        payload,
        "g1_3_checker_sha256",
        G1_3_CHECKER_SHA256,
        "engram_shadow_g1_3",
    )?;

    for key in [
        "capability_minted",
        "durable_replay_claim_verified",
        "durable_trust_ledger_verified",
        "freeze_authority_verified",
        "ready_for_g1_4_candidate_protocol_preregistration",
        "runtime_authority",
        "secure_custody_capture_verified",
        "trusted_time_verified",
    ] {
        require_bool(payload, key, false, "engram_shadow_authority_boundary")?;
    }
    require_bool(
        payload,
        "synthetic_test_vector_only",
        true,
        "engram_shadow_synthetic_boundary",
    )?;

    let anchor_set_commitment =
        decode_hex_fixed::<32>(string(payload, "anchor_set_commitment_sha256")?)?;
    let repository = decode_hex_fixed::<32>(string(payload, "repository_identity_sha256")?)?;
    let scope = decode_hex_fixed::<32>(string(payload, "scope_identity_sha256")?)?;
    let manifest = decode_hex_fixed::<32>(string(payload, "private_manifest_sha256")?)?;
    let nonce = decode_hex_fixed::<32>(string(payload, "nonce_hex")?)?;
    let boot_epoch = decode_hex_fixed::<32>(string(payload, "boot_epoch_sha256")?)?;
    let time_checkpoint =
        decode_hex_fixed::<32>(string(payload, "signed_time_checkpoint_sha256")?)?;
    if !nonzero(&anchor_set_commitment)
        || !nonzero(&repository)
        || !nonzero(&scope)
        || !nonzero(&manifest)
        || !nonzero(&nonce)
        || !nonzero(&boot_epoch)
        || !nonzero(&time_checkpoint)
    {
        return Err(envelope_error(
            "engram_shadow_zero_binding",
            "opaque synthetic binding values must be nonzero",
        ));
    }
    if anchor_set_commitment != expected.anchor_set_commitment_sha256
        || repository != expected.repository_identity_sha256
        || scope != expected.scope_identity_sha256
        || manifest != expected.private_manifest_sha256
        || nonce != expected.nonce
        || boot_epoch != expected.boot_epoch_sha256
        || time_checkpoint != expected.signed_time_checkpoint_sha256
    {
        return Err(envelope_error(
            "engram_shadow_expected_binding",
            "synthetic envelope does not match caller-supplied expected bindings",
        ));
    }

    let packet_values = payload
        .get("g1_3_input_packet_sha256s_in_order")
        .and_then(Value::as_array)
        .ok_or_else(|| {
            envelope_error(
                "engram_shadow_packet_digests",
                "G1.3 packet digest array is absent",
            )
        })?;
    if packet_values.len() != REQUIRED_SIGNATURE_COUNT {
        return Err(envelope_error(
            "engram_shadow_packet_digests",
            "exactly five ordered G1.3 packet digests are required",
        ));
    }
    let mut private_digests = Vec::with_capacity(REQUIRED_SIGNATURE_COUNT + 1);
    for (index, value) in packet_values.iter().enumerate() {
        let digest = decode_hex_fixed::<32>(value.as_str().ok_or_else(|| {
            envelope_error(
                "engram_shadow_packet_digests",
                "G1.3 packet digest is not text",
            )
        })?)?;
        if !nonzero(&digest) || digest != expected.g1_3_input_packet_sha256s_in_order[index] {
            return Err(envelope_error(
                "engram_shadow_packet_digests",
                "G1.3 packet digest is zero or mismatched",
            ));
        }
        private_digests.push(digest);
    }
    private_digests.push(manifest);
    let distinct: BTreeSet<[u8; 32]> = private_digests.iter().copied().collect();
    if distinct.len() != private_digests.len() {
        return Err(envelope_error(
            "engram_shadow_private_digest_alias",
            "private packet and manifest digest namespaces must be disjoint",
        ));
    }

    if synthetic_manifest_bytes.len() > MAX_SYNTHETIC_MANIFEST_BYTES
        || u64::try_from(synthetic_manifest_bytes.len()).ok()
            != Some(expected.private_manifest_byte_length)
        || sha256_bytes(synthetic_manifest_bytes) != expected.private_manifest_sha256
    {
        return Err(envelope_error(
            "engram_shadow_manifest_bytes",
            "bounded synthetic manifest bytes do not match the expected digest and length",
        ));
    }
    if integer(payload, "private_manifest_byte_length")? != expected.private_manifest_byte_length
        || expected.private_manifest_byte_length == 0
        || integer(payload, "sequence")? != expected.sequence
        || expected.sequence == 0
        || integer(payload, "issued_at_unix")? != expected.issued_at_unix
        || integer(payload, "expires_at_unix")? != expected.expires_at_unix
        || integer(payload, "trust_ledger_revision")? != expected.trust_ledger_revision
    {
        return Err(envelope_error(
            "engram_shadow_expected_scalar",
            "synthetic manifest, sequence, time, or trust revision binding mismatched",
        ));
    }
    if expected.expires_at_unix <= expected.issued_at_unix
        || expected.expires_at_unix - expected.issued_at_unix > MAX_ENVELOPE_AGE_SECS
    {
        return Err(envelope_error(
            "engram_shadow_time_shape",
            "signed synthetic issue and expiry metadata exceed the frozen shape",
        ));
    }
    Ok(private_digests)
}

fn reject_private_digest_aliases(
    private_digests: &[[u8; 32]],
    additional_public_digests: &[[u8; 32]],
) -> EnvelopeResult<()> {
    let mut public = vec![
        decode_hex_fixed::<32>(PREREGISTRATION_CONTRACT_SHA256)?,
        decode_hex_fixed::<32>(PREREGISTRATION_VALIDATOR_SHA256)?,
        decode_hex_fixed::<32>(PREREGISTRATION_CHECKER_SHA256)?,
        decode_hex_fixed::<32>(G1_3_CONTRACT_SHA256)?,
        decode_hex_fixed::<32>(G1_3_VALIDATOR_SHA256)?,
        decode_hex_fixed::<32>(G1_3_CHECKER_SHA256)?,
    ];
    public.extend_from_slice(additional_public_digests);
    if private_digests
        .iter()
        .any(|private| public.iter().any(|public| private == public))
    {
        return Err(envelope_error(
            "engram_shadow_private_public_digest_alias",
            "private digest aliases a public artifact or emitted receipt digest",
        ));
    }
    Ok(())
}

fn verify_synthetic_envelope_v1(
    ledger: &SyntheticTrustLedgerV1,
    raw_envelope: &[u8],
    expected: &ExpectedSyntheticEnvelopeBindingV1,
    synthetic_manifest_bytes: &[u8],
) -> EnvelopeResult<SyntheticEnvelopeConformanceV1> {
    validate_trust_ledger(ledger, expected)?;
    let value = parse_restricted_jcs(raw_envelope)?;
    let envelope = object(&value, "engram_shadow_envelope_type")?;
    exact_keys(envelope, ENVELOPE_KEYS, "engram_shadow_envelope_fields")?;
    require_string(
        envelope,
        "schema",
        ENVELOPE_SCHEMA,
        "engram_shadow_envelope_schema",
    )?;
    require_string(
        envelope,
        "envelope_kind",
        ENVELOPE_KIND,
        "engram_shadow_envelope_kind",
    )?;
    require_string(
        envelope,
        "canonicalization",
        CANONICAL_PROFILE,
        "engram_shadow_canonical_profile",
    )?;
    require_string(
        envelope,
        "signature_message_profile",
        MESSAGE_PROFILE,
        "engram_shadow_message_profile",
    )?;
    let payload = object(
        envelope
            .get("payload")
            .ok_or_else(|| envelope_error("engram_shadow_payload_type", "payload is absent"))?,
        "engram_shadow_payload_type",
    )?;
    let private_digests = validate_payload(payload, expected, synthetic_manifest_bytes)?;

    let frame_value = signing_frame(envelope)?;
    let frame_bytes = restricted_jcs_bytes(&frame_value)?;
    let signing_frame_sha256 = sha256_bytes(&frame_bytes);
    let envelope_sha256 = sha256_bytes(raw_envelope);

    let signatures = envelope
        .get("signatures")
        .and_then(Value::as_array)
        .ok_or_else(|| {
            envelope_error(
                "engram_shadow_signature_quorum",
                "signature array is absent",
            )
        })?;
    if signatures.len() != REQUIRED_SIGNATURE_COUNT {
        return Err(envelope_error(
            "engram_shadow_signature_quorum",
            "exactly five role signatures are required",
        ));
    }

    let mut message_digests = Vec::with_capacity(REQUIRED_SIGNATURE_COUNT);
    for (index, signature_value) in signatures.iter().enumerate() {
        let role = SignerRole::REQUIRED[index];
        let signature = object(signature_value, "engram_shadow_signature_type")?;
        exact_keys(signature, SIGNATURE_KEYS, "engram_shadow_signature_fields")?;
        let anchor = &ledger.anchors[index];
        require_string(
            signature,
            "role",
            role.as_str(),
            "engram_shadow_signature_role",
        )?;
        require_string(
            signature,
            "key_id",
            &anchor.key_id,
            "engram_shadow_signature_key",
        )?;
        if integer(signature, "key_epoch")? != anchor.key_epoch {
            return Err(envelope_error(
                "engram_shadow_signature_key",
                "signature key epoch does not match packet-independent anchor",
            ));
        }
        require_string(
            signature,
            "signature_algorithm",
            "ed25519",
            "engram_shadow_signature_algorithm",
        )?;
        require_string(
            signature,
            "signature_domain",
            role.domain(),
            "engram_shadow_signature_domain",
        )?;
        let message = signed_message(role, &anchor.key_id, anchor.key_epoch, &frame_bytes)?;
        let message_sha256 = sha256_bytes(&message);
        if decode_hex_fixed::<32>(string(signature, "signed_message_sha256")?)? != message_sha256 {
            return Err(envelope_error(
                "engram_shadow_signature_message",
                "signature message digest does not match the frozen framed bytes",
            ));
        }
        let detached = decode_hex_fixed::<64>(string(signature, "detached_signature_hex")?)?;
        UnparsedPublicKey::new(&ED25519, anchor.public_key)
            .verify(&message, &detached)
            .map_err(|_| {
                envelope_error(
                    "engram_shadow_signature_verify",
                    "detached Ed25519 signature failed",
                )
            })?;
        message_digests.push(message_sha256);
    }

    let mut public_receipt_digests = vec![
        signing_frame_sha256,
        envelope_sha256,
        expected.repository_identity_sha256,
        expected.scope_identity_sha256,
        expected.anchor_set_commitment_sha256,
    ];
    public_receipt_digests.extend(message_digests);
    reject_private_digest_aliases(&private_digests, &public_receipt_digests)?;

    Ok(SyntheticEnvelopeConformanceV1 {
        envelope_sha256,
        signing_frame_sha256,
        verified_signature_count: REQUIRED_SIGNATURE_COUNT,
        synthetic_signature_conformance_verified: true,
        synthetic_packet_independent_anchor_match: true,
        synthetic_manifest_bytes_hash_and_length_match: true,
        secure_custody_capture_verified: false,
        durable_trust_ledger_verified: false,
        trusted_time_verified: false,
        durable_replay_claim_verified: false,
        capability_minted: false,
        freeze_authority_verified: false,
        ready_for_g1_4_candidate_protocol_preregistration: false,
        runtime_authority: false,
    })
}

#[cfg(test)]
mod tests {
    use super::*;
    use ring::signature::{Ed25519KeyPair, KeyPair};
    use serde_json::json;

    const SYNTHETIC_MANIFEST_BYTES: &[u8] = b"synthetic-only-engram-g1-manifest-bytes-v0";

    fn hex(bytes: &[u8]) -> String {
        const HEX: &[u8; 16] = b"0123456789abcdef";
        let mut output = String::with_capacity(bytes.len() * 2);
        for byte in bytes {
            output.push(HEX[(byte >> 4) as usize] as char);
            output.push(HEX[(byte & 0x0f) as usize] as char);
        }
        output
    }

    fn repeated(byte: u8) -> String {
        hex(&[byte; 32])
    }

    fn test_keys() -> Vec<Ed25519KeyPair> {
        (1_u8..=REQUIRED_SIGNATURE_COUNT as u8)
            .map(|byte| Ed25519KeyPair::from_seed_unchecked(&[byte; 32]).unwrap())
            .collect()
    }

    fn expected() -> ExpectedSyntheticEnvelopeBindingV1 {
        let mut expected = ExpectedSyntheticEnvelopeBindingV1 {
            anchor_set_commitment_sha256: [0_u8; 32],
            repository_identity_sha256: [0x31; 32],
            scope_identity_sha256: [0x32; 32],
            g1_3_input_packet_sha256s_in_order: [
                [0x41; 32], [0x42; 32], [0x43; 32], [0x44; 32], [0x45; 32],
            ],
            private_manifest_sha256: sha256_bytes(SYNTHETIC_MANIFEST_BYTES),
            private_manifest_byte_length: SYNTHETIC_MANIFEST_BYTES.len() as u64,
            nonce: [0x51; 32],
            sequence: 7,
            issued_at_unix: 1_800_000_000,
            expires_at_unix: 1_800_003_600,
            boot_epoch_sha256: [0x52; 32],
            signed_time_checkpoint_sha256: [0x53; 32],
            trust_ledger_revision: 11,
        };
        expected.anchor_set_commitment_sha256 =
            synthetic_anchor_set_commitment(&ledger(&expected)).unwrap();
        expected
    }

    fn ledger(expected: &ExpectedSyntheticEnvelopeBindingV1) -> SyntheticTrustLedgerV1 {
        let keys = test_keys();
        SyntheticTrustLedgerV1 {
            revision: expected.trust_ledger_revision,
            rollback_floor_revision: expected.trust_ledger_revision,
            repository_identity_sha256: expected.repository_identity_sha256,
            scope_identity_sha256: expected.scope_identity_sha256,
            anchors: SignerRole::REQUIRED
                .iter()
                .enumerate()
                .map(|(index, role)| SyntheticTrustAnchorV1 {
                    role: *role,
                    key_id: format!("synthetic-{}-key-v1", role.as_str()),
                    key_epoch: 1,
                    public_key: keys[index].public_key().as_ref().try_into().unwrap(),
                    signer_identity_commitment_sha256: [0x61 + index as u8; 32],
                    revoked: false,
                })
                .collect(),
            synthetic_in_memory_only: true,
            supplied_outside_envelope: true,
        }
    }

    fn payload(expected: &ExpectedSyntheticEnvelopeBindingV1) -> Value {
        json!({
            "adapter_contract_version": ADAPTER_CONTRACT_VERSION,
            "anchor_set_commitment_sha256": hex(&expected.anchor_set_commitment_sha256),
            "boot_epoch_sha256": hex(&expected.boot_epoch_sha256),
            "capability_minted": false,
            "durable_replay_claim_verified": false,
            "durable_trust_ledger_verified": false,
            "evidence_class": EVIDENCE_CLASS,
            "expires_at_unix": expected.expires_at_unix,
            "freeze_authority_verified": false,
            "g1_3_checker_sha256": G1_3_CHECKER_SHA256,
            "g1_3_commit": G1_3_COMMIT,
            "g1_3_contract_sha256": G1_3_CONTRACT_SHA256,
            "g1_3_input_packet_sha256s_in_order": expected
                .g1_3_input_packet_sha256s_in_order
                .iter()
                .map(|digest| hex(digest))
                .collect::<Vec<_>>(),
            "g1_3_validator_sha256": G1_3_VALIDATOR_SHA256,
            "implementation_profile": IMPLEMENTATION_PROFILE,
            "issued_at_unix": expected.issued_at_unix,
            "nonce_hex": hex(&expected.nonce),
            "preregistration_checker_sha256": PREREGISTRATION_CHECKER_SHA256,
            "preregistration_commit": PREREGISTRATION_COMMIT,
            "preregistration_contract_sha256": PREREGISTRATION_CONTRACT_SHA256,
            "preregistration_validator_sha256": PREREGISTRATION_VALIDATOR_SHA256,
            "private_manifest_byte_length": expected.private_manifest_byte_length,
            "private_manifest_sha256": hex(&expected.private_manifest_sha256),
            "ready_for_g1_4_candidate_protocol_preregistration": false,
            "repository_identity_sha256": hex(&expected.repository_identity_sha256),
            "runtime_authority": false,
            "scope_identity_sha256": hex(&expected.scope_identity_sha256),
            "secure_custody_capture_verified": false,
            "sequence": expected.sequence,
            "signed_time_checkpoint_sha256": hex(&expected.signed_time_checkpoint_sha256),
            "stage": STAGE,
            "synthetic_test_vector_only": true,
            "trusted_time_verified": false,
            "trust_ledger_revision": expected.trust_ledger_revision,
        })
    }

    fn unsigned_envelope(payload: Value) -> Value {
        json!({
            "canonicalization": CANONICAL_PROFILE,
            "envelope_kind": ENVELOPE_KIND,
            "payload": payload,
            "schema": ENVELOPE_SCHEMA,
            "signature_message_profile": MESSAGE_PROFILE,
            "signatures": [],
        })
    }

    fn sign_envelope(payload: Value, ledger: &SyntheticTrustLedgerV1) -> Vec<u8> {
        let keys = test_keys();
        let mut envelope = unsigned_envelope(payload);
        let envelope_object = envelope.as_object().unwrap();
        let frame = restricted_jcs_bytes(&signing_frame(envelope_object).unwrap()).unwrap();
        let signatures = SignerRole::REQUIRED
            .iter()
            .enumerate()
            .map(|(index, role)| {
                let anchor = &ledger.anchors[index];
                let message =
                    signed_message(*role, &anchor.key_id, anchor.key_epoch, &frame).unwrap();
                let signature = keys[index].sign(&message);
                json!({
                    "detached_signature_hex": hex(signature.as_ref()),
                    "key_epoch": anchor.key_epoch,
                    "key_id": anchor.key_id,
                    "role": role.as_str(),
                    "signature_algorithm": "ed25519",
                    "signature_domain": role.domain(),
                    "signed_message_sha256": hex(&sha256_bytes(&message)),
                })
            })
            .collect();
        envelope["signatures"] = Value::Array(signatures);
        restricted_jcs_bytes(&envelope).unwrap()
    }

    fn fixture() -> (
        ExpectedSyntheticEnvelopeBindingV1,
        SyntheticTrustLedgerV1,
        Vec<u8>,
    ) {
        let expected = expected();
        let ledger = ledger(&expected);
        let raw = sign_envelope(payload(&expected), &ledger);
        (expected, ledger, raw)
    }

    fn verify_fixture(
        ledger: &SyntheticTrustLedgerV1,
        raw: &[u8],
        expected: &ExpectedSyntheticEnvelopeBindingV1,
    ) -> EnvelopeResult<SyntheticEnvelopeConformanceV1> {
        verify_synthetic_envelope_v1(ledger, raw, expected, SYNTHETIC_MANIFEST_BYTES)
    }

    fn parse(raw: &[u8]) -> Value {
        serde_json::from_slice(raw).unwrap()
    }

    #[test]
    fn engram_g1_auth_envelope_shadow_valid_synthetic_quorum_is_no_authority() {
        let (expected, ledger, raw) = fixture();
        let receipt = verify_fixture(&ledger, &raw, &expected).unwrap();
        assert_eq!(receipt.verified_signature_count, 5);
        assert!(receipt.synthetic_signature_conformance_verified);
        assert!(receipt.synthetic_packet_independent_anchor_match);
        assert!(receipt.synthetic_manifest_bytes_hash_and_length_match);
        assert!(!receipt.secure_custody_capture_verified);
        assert!(!receipt.durable_trust_ledger_verified);
        assert!(!receipt.trusted_time_verified);
        assert!(!receipt.durable_replay_claim_verified);
        assert!(!receipt.capability_minted);
        assert!(!receipt.freeze_authority_verified);
        assert!(!receipt.ready_for_g1_4_candidate_protocol_preregistration);
        assert!(!receipt.runtime_authority);
        let debug = format!("{receipt:?}");
        for secret_like in [
            repeated(0x41),
            hex(&expected.private_manifest_sha256),
            repeated(0x31),
            repeated(0x32),
            hex(&expected.anchor_set_commitment_sha256),
        ] {
            assert!(!debug.contains(&secret_like));
        }
    }

    #[test]
    fn engram_g1_auth_envelope_shadow_signature_message_and_domain_tamper_reject() {
        let (expected, ledger, raw) = fixture();
        for (label, mutation, expected_code) in [
            (
                "signature",
                ("detached_signature_hex", repeated(0x99)),
                "engram_shadow_hex",
            ),
            (
                "message",
                ("signed_message_sha256", repeated(0x98)),
                "engram_shadow_signature_message",
            ),
            (
                "domain",
                (
                    "signature_domain",
                    SignerRole::FreezeReviewer1.domain().to_owned(),
                ),
                "engram_shadow_signature_domain",
            ),
        ] {
            let mut value = parse(&raw);
            value["signatures"][0][mutation.0] = Value::String(mutation.1);
            let mutated = restricted_jcs_bytes(&value).unwrap();
            let error = verify_fixture(&ledger, &mutated, &expected).unwrap_err();
            assert_eq!(error.code(), expected_code, "{label}");
        }
        let mut one_bit = parse(&raw);
        let mut signature = decode_hex_fixed::<64>(
            one_bit["signatures"][0]["detached_signature_hex"]
                .as_str()
                .unwrap(),
        )
        .unwrap();
        signature[0] ^= 1;
        one_bit["signatures"][0]["detached_signature_hex"] = Value::String(encode_hex(&signature));
        let mutated = restricted_jcs_bytes(&one_bit).unwrap();
        assert_eq!(
            verify_fixture(&ledger, &mutated, &expected)
                .unwrap_err()
                .code(),
            "engram_shadow_signature_verify"
        );
    }

    #[test]
    fn engram_g1_auth_envelope_shadow_quorum_role_key_and_anchor_substitution_reject() {
        let (expected, ledger, raw) = fixture();
        let mut cases = Vec::new();
        let mut missing = parse(&raw);
        missing["signatures"].as_array_mut().unwrap().pop();
        cases.push((missing, "engram_shadow_signature_quorum"));
        let mut duplicate = parse(&raw);
        duplicate["signatures"][1] = duplicate["signatures"][0].clone();
        cases.push((duplicate, "engram_shadow_signature_role"));
        let mut key_id = parse(&raw);
        key_id["signatures"][0]["key_id"] = json!("synthetic-substitute-key-v1");
        cases.push((key_id, "engram_shadow_signature_key"));
        for (value, code) in cases {
            let mutated = restricted_jcs_bytes(&value).unwrap();
            assert_eq!(
                verify_fixture(&ledger, &mutated, &expected)
                    .unwrap_err()
                    .code(),
                code
            );
        }

        let mut substituted = ledger.clone();
        substituted.anchors[0].public_key =
            test_keys()[1].public_key().as_ref().try_into().unwrap();
        assert_eq!(
            verify_fixture(&substituted, &raw, &expected)
                .unwrap_err()
                .code(),
            "engram_shadow_trust_anchor"
        );
        let mut packet_sourced = ledger.clone();
        packet_sourced.supplied_outside_envelope = false;
        assert_eq!(
            verify_fixture(&packet_sourced, &raw, &expected)
                .unwrap_err()
                .code(),
            "engram_shadow_trust_source"
        );
        let mut alternate = ledger.clone();
        alternate.anchors[0].key_id = "synthetic-alternate-owner-key-v1".to_owned();
        let resigned = sign_envelope(payload(&expected), &alternate);
        assert_eq!(
            verify_fixture(&alternate, &resigned, &expected)
                .unwrap_err()
                .code(),
            "engram_shadow_anchor_set_commitment"
        );
    }

    #[test]
    fn engram_g1_auth_envelope_shadow_resigned_binding_and_authority_drift_reject() {
        let (expected, ledger, _) = fixture();
        let base = payload(&expected);
        let cases: &[(&str, &str, Value)] = &[
            ("stage", "stage", json!("g1_4")),
            ("repo", "repository_identity_sha256", json!(repeated(0x91))),
            ("scope", "scope_identity_sha256", json!(repeated(0x92))),
            ("manifest", "private_manifest_sha256", json!(repeated(0x93))),
            ("nonce", "nonce_hex", json!(repeated(0x94))),
            ("sequence", "sequence", json!(8)),
            ("issued", "issued_at_unix", json!(1_800_000_001_u64)),
            ("expiry", "expires_at_unix", json!(1_800_003_601_u64)),
            ("trust", "trust_ledger_revision", json!(12)),
            ("custody", "secure_custody_capture_verified", json!(true)),
            ("replay", "durable_replay_claim_verified", json!(true)),
            ("capability", "capability_minted", json!(true)),
            ("freeze", "freeze_authority_verified", json!(true)),
            (
                "g1.4",
                "ready_for_g1_4_candidate_protocol_preregistration",
                json!(true),
            ),
            ("runtime", "runtime_authority", json!(true)),
        ];
        for (label, field, replacement) in cases {
            let mut mutated = base.clone();
            mutated[*field] = replacement.clone();
            let raw = sign_envelope(mutated, &ledger);
            assert!(
                verify_fixture(&ledger, &raw, &expected).is_err(),
                "resigned drift accepted: {label}"
            );
        }
        for index in 0..REQUIRED_SIGNATURE_COUNT {
            let mut mutated = base.clone();
            mutated["g1_3_input_packet_sha256s_in_order"][index] =
                json!(repeated(0xa0 + index as u8));
            let raw = sign_envelope(mutated, &ledger);
            assert_eq!(
                verify_fixture(&ledger, &raw, &expected).unwrap_err().code(),
                "engram_shadow_packet_digests"
            );
        }

        let payload_object = base.as_object().unwrap();
        let mut scalar_count = 0;
        for (field, original) in payload_object {
            if original.is_array() {
                continue;
            }
            scalar_count += 1;
            let replacement = match original {
                Value::Bool(value) => Value::Bool(!value),
                Value::Number(value) => json!(value.as_u64().unwrap() + 1),
                Value::String(value) => Value::String(format!("{value}_drift")),
                _ => panic!("unexpected payload scalar: {field}"),
            };
            let mut mutated = base.clone();
            mutated[field] = replacement;
            let raw = sign_envelope(mutated, &ledger);
            assert!(
                verify_fixture(&ledger, &raw, &expected).is_err(),
                "resigned scalar drift accepted: {field}"
            );
        }
        assert_eq!(scalar_count, PAYLOAD_KEYS.len() - 1);

        let mut unsigned = parse(&sign_envelope(base.clone(), &ledger));
        unsigned["payload"]["sequence"] = json!(expected.sequence + 1);
        let unsigned_raw = restricted_jcs_bytes(&unsigned).unwrap();
        let mut changed_expected = expected.clone();
        changed_expected.sequence += 1;
        assert_eq!(
            verify_fixture(&ledger, &unsigned_raw, &changed_expected)
                .unwrap_err()
                .code(),
            "engram_shadow_signature_message"
        );
    }

    #[test]
    fn engram_g1_auth_envelope_shadow_rfc8032_verification_known_answer() {
        let public_key = decode_hex_fixed::<32>(
            "d75a980182b10ab7d54bfed3c964073a0ee172f3daa62325af021a68f707511a",
        )
        .unwrap();
        let signature = decode_hex_fixed::<64>(
            "e5564300c360ac729086e2cc806e828a84877f1eb8e5d974d873e06522490155\
             5fb8821590a33bacc61e39701cf9b46bd25bf5f0595bbe24655141438e7a100b"
                .replace(' ', "")
                .as_str(),
        )
        .unwrap();
        assert!(UnparsedPublicKey::new(&ED25519, public_key)
            .verify(b"", &signature)
            .is_ok());
        let mut tampered = signature;
        tampered[63] ^= 1;
        assert!(UnparsedPublicKey::new(&ED25519, public_key)
            .verify(b"", &tampered)
            .is_err());
    }

    #[test]
    fn engram_g1_auth_envelope_shadow_manifest_bytes_and_repeat_calls_remain_non_authorizing() {
        let (expected, ledger, raw) = fixture();
        let first = verify_fixture(&ledger, &raw, &expected).unwrap();
        let second = verify_fixture(&ledger, &raw, &expected).unwrap();
        assert_eq!(first, second);
        assert!(!first.trusted_time_verified);
        assert!(!first.durable_replay_claim_verified);
        assert!(!first.capability_minted);
        assert!(!first.freeze_authority_verified);

        assert_eq!(
            verify_synthetic_envelope_v1(
                &ledger,
                &raw,
                &expected,
                b"different-synthetic-manifest",
            )
            .unwrap_err()
            .code(),
            "engram_shadow_manifest_bytes"
        );
        let oversized = vec![b'x'; MAX_SYNTHETIC_MANIFEST_BYTES + 1];
        assert_eq!(
            verify_synthetic_envelope_v1(&ledger, &raw, &expected, &oversized)
                .unwrap_err()
                .code(),
            "engram_shadow_manifest_bytes"
        );
    }

    #[test]
    fn engram_g1_auth_envelope_shadow_trust_revision_revocation_and_scope_reject() {
        let (expected, ledger, raw) = fixture();
        let mut stale = ledger.clone();
        stale.rollback_floor_revision += 1;
        let mut revoked = ledger.clone();
        revoked.anchors[2].revoked = true;
        let mut wrong_epoch = ledger.clone();
        wrong_epoch.anchors[3].key_epoch = 2;
        let mut wrong_scope = ledger.clone();
        wrong_scope.scope_identity_sha256 = [0x77; 32];
        for (candidate, code) in [
            (stale, "engram_shadow_trust_revision"),
            (revoked, "engram_shadow_trust_anchor"),
            (wrong_epoch, "engram_shadow_anchor_set_commitment"),
            (wrong_scope, "engram_shadow_trust_scope"),
        ] {
            assert_eq!(
                verify_fixture(&candidate, &raw, &expected)
                    .unwrap_err()
                    .code(),
                code
            );
        }
    }

    #[test]
    fn engram_g1_auth_envelope_shadow_private_public_digest_alias_rejects_after_resign() {
        let (expected, _base_ledger, _) = fixture();
        let public = [
            PREREGISTRATION_CONTRACT_SHA256,
            PREREGISTRATION_VALIDATOR_SHA256,
            PREREGISTRATION_CHECKER_SHA256,
            G1_3_CONTRACT_SHA256,
            G1_3_VALIDATOR_SHA256,
            G1_3_CHECKER_SHA256,
        ];
        for (index, public_digest) in public.iter().enumerate() {
            let mut expected_alias = expected.clone();
            let digest = decode_hex_fixed::<32>(public_digest).unwrap();
            expected_alias.g1_3_input_packet_sha256s_in_order[index % REQUIRED_SIGNATURE_COUNT] =
                digest;
            let alias_ledger = ledger(&expected_alias);
            let raw = sign_envelope(payload(&expected_alias), &alias_ledger);
            assert_eq!(
                verify_fixture(&alias_ledger, &raw, &expected_alias)
                    .unwrap_err()
                    .code(),
                "engram_shadow_private_public_digest_alias"
            );
            assert_eq!(
                reject_private_digest_aliases(&[digest], &[])
                    .unwrap_err()
                    .code(),
                "engram_shadow_private_public_digest_alias"
            );
        }
    }

    #[test]
    fn engram_g1_auth_envelope_shadow_noncanonical_duplicate_and_out_of_subset_reject() {
        let (expected, ledger, raw) = fixture();
        let mut whitespace = vec![b' '];
        whitespace.extend_from_slice(&raw);
        assert_eq!(
            verify_fixture(&ledger, &whitespace, &expected)
                .unwrap_err()
                .code(),
            "engram_shadow_jcs_bytes"
        );
        let text = String::from_utf8(raw.clone()).unwrap();
        let duplicate = text.replacen(
            &format!("\"canonicalization\":\"{CANONICAL_PROFILE}\","),
            &format!(
                "\"canonicalization\":\"{CANONICAL_PROFILE}\",\"canonicalization\":\"{CANONICAL_PROFILE}\","
            ),
            1,
        );
        assert_eq!(
            verify_fixture(&ledger, duplicate.as_bytes(), &expected)
                .unwrap_err()
                .code(),
            "engram_shadow_jcs_bytes"
        );

        let canonical_text = String::from_utf8(raw.clone()).unwrap();
        let nested_duplicate = canonical_text.replacen(
            &format!("\"stage\":\"{STAGE}\","),
            &format!("\"stage\":\"{STAGE}\",\"stage\":\"{STAGE}\","),
            1,
        );
        assert_eq!(
            verify_fixture(&ledger, nested_duplicate.as_bytes(), &expected)
                .unwrap_err()
                .code(),
            "engram_shadow_jcs_bytes"
        );

        for (label, mutated) in [
            ("bom", [&[0xef, 0xbb, 0xbf][..], &raw].concat()),
            ("trailing-lf", [&raw[..], b"\n"].concat()),
            ("invalid-utf8", [&raw[..], &[0xff][..]].concat()),
            (
                "escaped-slash",
                canonical_text
                    .replacen("agent-bridge/", "agent-bridge\\/", 1)
                    .into_bytes(),
            ),
            (
                "unicode-escape",
                canonical_text
                    .replacen("\"schema\"", "\"\\u0073chema\"", 1)
                    .into_bytes(),
            ),
            (
                "lone-surrogate",
                canonical_text
                    .replacen(
                        &format!("\"stage\":\"{STAGE}\""),
                        "\"stage\":\"\\ud800\"",
                        1,
                    )
                    .into_bytes(),
            ),
            (
                "unsorted-nested",
                canonical_text
                    .replacen(
                        &format!(
                            "\"adapter_contract_version\":\"{ADAPTER_CONTRACT_VERSION}\",\"anchor_set_commitment_sha256\":\"{}\"",
                            hex(&expected.anchor_set_commitment_sha256)
                        ),
                        &format!(
                            "\"anchor_set_commitment_sha256\":\"{}\",\"adapter_contract_version\":\"{ADAPTER_CONTRACT_VERSION}\"",
                            hex(&expected.anchor_set_commitment_sha256)
                        ),
                        1,
                    )
                    .into_bytes(),
            ),
        ] {
            assert!(
                verify_fixture(&ledger, &mutated, &expected).is_err(),
                "noncanonical case accepted: {label}"
            );
        }

        for replacement in [json!(-1), json!(1.5), json!(MAX_JCS_SAFE_INTEGER + 1)] {
            let mut value = parse(&raw);
            value["payload"]["sequence"] = replacement;
            let encoded = serde_json::to_vec(&value).unwrap();
            assert_eq!(
                verify_fixture(&ledger, &encoded, &expected)
                    .unwrap_err()
                    .code(),
                "engram_shadow_jcs_number"
            );
        }
        let mut non_ascii = parse(&raw);
        non_ascii["payload"]["stage"] = json!("synthetic-测试");
        let encoded = serde_json::to_vec(&non_ascii).unwrap();
        assert_eq!(
            verify_fixture(&ledger, &encoded, &expected)
                .unwrap_err()
                .code(),
            "engram_shadow_jcs_string"
        );
        assert_eq!(
            restricted_jcs_bytes(&json!(MAX_JCS_SAFE_INTEGER)).unwrap(),
            MAX_JCS_SAFE_INTEGER.to_string().into_bytes()
        );
        for numeric in [
            "1.0",
            "1e0",
            "-1",
            "9007199254740992",
            "18446744073709551615",
        ] {
            let mutated =
                canonical_text.replacen("\"sequence\":7", &format!("\"sequence\":{numeric}"), 1);
            assert!(
                verify_fixture(&ledger, mutated.as_bytes(), &expected).is_err(),
                "numeric spelling accepted: {numeric}"
            );
        }
    }

    #[test]
    fn engram_g1_auth_envelope_shadow_unknown_missing_depth_and_size_reject() {
        let (expected, ledger, raw) = fixture();
        let mut unknown = parse(&raw);
        unknown["packet_public_key"] = json!(repeated(0x90));
        let encoded = restricted_jcs_bytes(&unknown).unwrap();
        assert_eq!(
            verify_fixture(&ledger, &encoded, &expected)
                .unwrap_err()
                .code(),
            "engram_shadow_envelope_fields"
        );
        let mut missing = parse(&raw);
        missing.as_object_mut().unwrap().remove("signatures");
        let encoded = restricted_jcs_bytes(&missing).unwrap();
        assert_eq!(
            verify_fixture(&ledger, &encoded, &expected)
                .unwrap_err()
                .code(),
            "engram_shadow_envelope_fields"
        );
        let mut nested = Value::Null;
        for _ in 0..=MAX_NESTING_DEPTH + 1 {
            nested = Value::Array(vec![nested]);
        }
        let encoded = serde_json::to_vec(&nested).unwrap();
        assert_eq!(
            verify_fixture(&ledger, &encoded, &expected)
                .unwrap_err()
                .code(),
            "engram_shadow_jcs_depth"
        );
        let long_string =
            serde_json::to_vec(&Value::String("a".repeat(MAX_STRING_BYTES + 1))).unwrap();
        assert_eq!(
            verify_fixture(&ledger, &long_string, &expected)
                .unwrap_err()
                .code(),
            "engram_shadow_jcs_string"
        );
        let long_key = serde_json::to_vec(&json!({"a".repeat(MAX_KEY_BYTES + 1): true})).unwrap();
        assert_eq!(
            verify_fixture(&ledger, &long_key, &expected)
                .unwrap_err()
                .code(),
            "engram_shadow_jcs_key"
        );
        let too_many_items = serde_json::to_vec(&Value::Array(
            (0..=MAX_ARRAY_ITEMS).map(|_| Value::Null).collect(),
        ))
        .unwrap();
        assert_eq!(
            verify_fixture(&ledger, &too_many_items, &expected)
                .unwrap_err()
                .code(),
            "engram_shadow_jcs_array"
        );
        let mut too_many_keys = Map::new();
        for index in 0..=MAX_OBJECT_KEYS {
            too_many_keys.insert(format!("k{index:03}"), Value::Null);
        }
        let encoded = serde_json::to_vec(&Value::Object(too_many_keys)).unwrap();
        assert_eq!(
            verify_fixture(&ledger, &encoded, &expected)
                .unwrap_err()
                .code(),
            "engram_shadow_jcs_object"
        );
        let oversized = format!("\"{}\"", "a".repeat(MAX_DOCUMENT_BYTES));
        assert_eq!(
            verify_fixture(&ledger, oversized.as_bytes(), &expected)
                .unwrap_err()
                .code(),
            "engram_shadow_jcs_size"
        );
    }
}
