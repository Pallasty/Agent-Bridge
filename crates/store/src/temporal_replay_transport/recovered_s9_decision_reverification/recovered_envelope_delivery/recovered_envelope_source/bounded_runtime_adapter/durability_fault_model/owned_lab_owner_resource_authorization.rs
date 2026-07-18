//! S18 private authenticated-unclaimed owned-lab authorization verifier.
//!
//! The verifier has no runner, filesystem, process, SQLite, network, clock,
//! state-store, or application wiring. A successful result authenticates only
//! an immutable `AUTHORIZED_UNCLAIMED` owner decision. It is deliberately not
//! an execution capability and cannot create a root or launch a child.

#![cfg_attr(not(test), allow(dead_code))]

use ring::signature::{UnparsedPublicKey, ED25519};
use serde_json::{Map, Value};
use sha2::{Digest, Sha256};
use std::collections::BTreeSet;
use std::fmt;

const MAX_DOCUMENT_BYTES: usize = 65_536;
const MAX_NESTING_DEPTH: usize = 16;
const CANONICAL_PROFILE: &str =
    "AB_RESTRICTED_CANONICAL_JSON_S18_V1_COMPACT_SORTED_KEYS_ASCII_VALUES_NO_FLOAT";
const MESSAGE_PROFILE: &str = "U32BE_DOMAIN_LENGTH_DOMAIN_U64BE_32_RAW_PAYLOAD_SHA256";
const MESSAGE_DOMAIN: &[u8] = b"agent-bridge/biocortex/owned-lab/owner-authorization/s18/v1";
const AUTHORIZATION_ID_DOMAIN: &[u8] =
    b"agent-bridge/biocortex/owned-lab/owner-authorization-id/s18/v1";
const FUTURE_TRANSITION: &str = "UNCLAIMED_TO_CONSUMED_FOR_EXACT_RUN";
const ENVELOPE_SCHEMA: &str =
    "agent_bridge.memory_temporal_owned_lab_owner_authorization_envelope_s18.v0";
const ANCHOR_SCHEMA: &str = "agent_bridge.memory_temporal_owned_lab_owner_trust_anchor_s18.v0";
const DECISION_STATE: &str = "AUTHORIZED_UNCLAIMED_OWNED_LAB_L1_OL00_OL04_OL05_CANARY";
const DECISION_REASON: &str = "OWNER_AUTHORIZES_EXACT_SCOPE_SUBJECT_TO_FUTURE_SINGLE_USE_CAS";
const S17_SOURCE_COMMIT: &str = "20368c626bf34c5a1edd07391014ab8716536e7e";
const S17_INTEGRATION_COMMIT: &str = "d0356dbdbd7239ffab972ee21da81891210a055b";
const S16_INTEGRATION_COMMIT: &str = "d7f3e206169227905dbd320f1876de46e3facfea";
const S17_PLAN_SHA256: &str = "ca9769ff2b79e474999df6bb5096a3e062b5acf78fa23788f76ae44295531650";
const S17_OBSERVATION_SCHEMA_SHA256: &str =
    "26a8cca9f9ca74ceb4b949a2e75d9282a6227623f5bd66cc3333fbff7441588d";
const S17_PENDING_OWNER_SCHEMA_SHA256: &str =
    "41426b240443672d7e83fc0a8781ddb79acd9beaab1c7f6e9eaf9270c1bdf608";
const S17_SUCCESSOR_GATE_SHA256: &str =
    "6c35fc3684f7262a7eca2b8405e2c3a21b5ce2f7d282731824ceb67b0ea7163e";

const ENVELOPE_KEYS: &[&str] = &[
    "authentication",
    "canonicalization",
    "packet_kind",
    "payload",
    "schema",
    "signature_message_profile",
];
const AUTHENTICATION_KEYS: &[&str] = &[
    "detached_signature_hex",
    "detached_signature_sha256",
    "public_key_carried_by_envelope",
    "self_asserted_signature_valid",
    "signature_algorithm",
    "signature_message_domain",
    "signed_payload_sha256",
];
const ANCHOR_KEYS: &[&str] = &[
    "anchor_state",
    "audience",
    "authorization_envelope_embedded",
    "authorized_claim_level",
    "authorized_family_namespace",
    "canonicalization",
    "ed25519_public_key_hex",
    "execution_capability_embedded",
    "installation_receipt_sha256",
    "installation_source",
    "minimum_revocation_epoch",
    "owner_identity_sha256",
    "owner_identity_verification_receipt_sha256",
    "owner_key_id",
    "owner_key_version",
    "owner_role",
    "packet_kind",
    "private_key_present",
    "provider_or_production_authority",
    "schema",
    "self_asserted_key_is_owner_authentication",
    "side_effects_unlocked",
    "signature_algorithm",
    "trust_policy_sha256",
];
const PAYLOAD_KEYS: &[&str] = &[
    "agent_bridge_application_side_effect_allowed",
    "assigned_attempt_count",
    "assignment_set_sha256",
    "atomic_claim_receipt_required_before_start",
    "audience",
    "authorization_id_sha256",
    "authorized_family_ids",
    "authorized_family_scenario_counts",
    "canary_batch_count",
    "capability_nonce_sha256",
    "cas_claim_receipt_sha256",
    "claim_key_sha256",
    "claim_level",
    "claim_namespace_sha256",
    "claimed_run_id_sha256",
    "classifier_binary_sha256",
    "classifier_source_sha256",
    "cleanup_policy_sha256",
    "control_protocol_sha256",
    "credential_access_allowed",
    "decision_expires_at_utc_audit_only",
    "decision_issued_at_utc_audit_only",
    "decision_nonce_sha256",
    "decision_reason",
    "decision_state",
    "direct_block_device_write_allowed",
    "execution_capability_sha256",
    "execution_start_permitted",
    "expected_oracle_sha256",
    "expected_unclaimed_revision",
    "family_id_namespace",
    "live_observation_validator_binary_sha256",
    "live_observation_validator_ruleset_sha256",
    "live_observation_validator_source_sha256",
    "live_observation_validator_toolchain_sha256",
    "maximum_successful_claims",
    "mount_or_unmount_allowed",
    "network_allowed",
    "owner_envelope_is_bearer_capability",
    "owner_authorization_validator_binary_sha256",
    "owner_authorization_validator_ruleset_sha256",
    "owner_authorization_validator_source_sha256",
    "owner_authorization_validator_toolchain_sha256",
    "owner_identity_sha256",
    "owner_key_id",
    "owner_key_version",
    "owner_role",
    "owner_scope_authorized",
    "owned_lab_execution_authorized",
    "paid_resource_allowed",
    "planned_distinct_fresh_exec_read_count",
    "planned_pidfd_sigkill_attempt_count",
    "planned_total_s16_mapping_phase_record_count",
    "positive_owner_schema_sha256",
    "post_run_cleanup_receipt_sha256",
    "post_run_custody_receipt_sha256",
    "preflight_policy_sha256",
    "process_crash_is_power_loss_proof",
    "production_access_allowed",
    "provider_access_allowed",
    "reboot_kernel_crash_or_power_fault_allowed",
    "resource_scope_sha256",
    "retention_policy_sha256",
    "retry_or_implicit_rerun_allowed",
    "revocation_epoch",
    "review_policy_sha256",
    "root_or_privilege_escalation_allowed",
    "runner_binary_sha256",
    "runner_source_commit",
    "runner_source_sha256",
    "runner_toolchain_sha256",
    "s16_integration_commit",
    "s17_integration_commit",
    "s17_observation_schema_sha256",
    "s17_pending_owner_schema_sha256",
    "s17_plan_sha256",
    "s17_source_commit",
    "s17_successor_gate_sha256",
    "s19_integration_commit",
    "s19_subject_manifest_schema_sha256",
    "s19_subject_manifest_sha256",
    "safety_policy_sha256",
    "schedule_sha256",
    "schema_conformance_alone_authorizes_execution",
    "side_effects_unlocked",
    "single_use_claim_required",
    "single_use_execution_capability_issued",
    "sqlite_profile_sha256",
    "sqlite_schema_sha256",
    "stop_control_policy_sha256",
    "stop_state_at_signing_audit_only",
    "timestamps_are_authorization_freshness",
    "trusted_time_receipt_sha256",
    "trust_anchor_document_sha256",
    "trust_policy_sha256",
    "use_time_current_revocation_epoch_check_required",
    "use_time_external_absorbing_stop_check_required",
    "validity_control",
];

#[derive(Debug, thiserror::Error)]
#[error("{code}: {detail}")]
struct OwnedLabAuthorizationError {
    code: &'static str,
    detail: &'static str,
}

impl OwnedLabAuthorizationError {
    #[cfg(test)]
    fn code(&self) -> &'static str {
        self.code
    }
}

type AuthorizationResult<T> = Result<T, OwnedLabAuthorizationError>;

fn authorization_error(code: &'static str, detail: &'static str) -> OwnedLabAuthorizationError {
    OwnedLabAuthorizationError { code, detail }
}

fn sha256_bytes(bytes: &[u8]) -> [u8; 32] {
    Sha256::digest(bytes).into()
}

fn nonzero(value: &[u8]) -> bool {
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

fn audit_time_key(value: &str) -> Option<(u64, u64, u64, u64, u64, u64, u64)> {
    let bytes = value.as_bytes();
    if !(20..=30).contains(&bytes.len())
        || bytes.last() != Some(&b'Z')
        || bytes.get(4) != Some(&b'-')
        || bytes.get(7) != Some(&b'-')
        || bytes.get(10) != Some(&b'T')
        || bytes.get(13) != Some(&b':')
        || bytes.get(16) != Some(&b':')
    {
        return None;
    }
    let whole_seconds = &bytes[..19];
    if whole_seconds
        .iter()
        .enumerate()
        .any(|(index, byte)| !matches!(index, 4 | 7 | 10 | 13 | 16) && !byte.is_ascii_digit())
    {
        return None;
    }
    let parse_digits = |start: usize, end: usize| -> Option<u64> {
        std::str::from_utf8(&bytes[start..end]).ok()?.parse().ok()
    };
    let year = parse_digits(0, 4)?;
    let month = parse_digits(5, 7)?;
    let day = parse_digits(8, 10)?;
    let hour = parse_digits(11, 13)?;
    let minute = parse_digits(14, 16)?;
    let second = parse_digits(17, 19)?;
    if !(1..=12).contains(&month)
        || !(1..=31).contains(&day)
        || hour > 23
        || minute > 59
        || second > 60
    {
        return None;
    }
    let nanosecond = if bytes.len() == 20 {
        0
    } else {
        let digits = bytes.len() - 21;
        if bytes.get(19) != Some(&b'.')
            || !(1..=9).contains(&digits)
            || !bytes[20..bytes.len() - 1].iter().all(u8::is_ascii_digit)
        {
            return None;
        }
        parse_digits(20, bytes.len() - 1)? * 10_u64.pow((9 - digits) as u32)
    };
    Some((year, month, day, hour, minute, second, nanosecond))
}

fn decode_hex_fixed<const N: usize>(value: &str) -> AuthorizationResult<[u8; N]> {
    if value.len() != N * 2
        || !value
            .bytes()
            .all(|byte| byte.is_ascii_digit() || (b'a'..=b'f').contains(&byte))
    {
        return Err(authorization_error(
            "s18_hex",
            "fixed-width lowercase hexadecimal field is malformed",
        ));
    }
    let mut output = [0_u8; N];
    for (index, byte) in output.iter_mut().enumerate() {
        let offset = index * 2;
        let high = value.as_bytes()[offset];
        let low = value.as_bytes()[offset + 1];
        let nibble = |input: u8| -> u8 {
            if input.is_ascii_digit() {
                input - b'0'
            } else {
                input - b'a' + 10
            }
        };
        *byte = (nibble(high) << 4) | nibble(low);
    }
    Ok(output)
}

fn validate_restricted_value(value: &Value, depth: usize) -> AuthorizationResult<()> {
    if depth > MAX_NESTING_DEPTH {
        return Err(authorization_error(
            "s18_canonical_depth",
            "restricted canonical JSON exceeds the nesting bound",
        ));
    }
    match value {
        Value::Null | Value::Bool(_) => Ok(()),
        Value::Number(number) if number.as_u64().is_some() => Ok(()),
        Value::Number(_) => Err(authorization_error(
            "s18_canonical_number",
            "only nonnegative u64 integers are allowed",
        )),
        Value::String(string) if string.is_ascii() => Ok(()),
        Value::String(_) => Err(authorization_error(
            "s18_canonical_string",
            "only ASCII string values are allowed",
        )),
        Value::Array(values) => {
            for item in values {
                validate_restricted_value(item, depth + 1)?;
            }
            Ok(())
        }
        Value::Object(values) => {
            for (key, item) in values {
                if !key.is_ascii() {
                    return Err(authorization_error(
                        "s18_canonical_key",
                        "only ASCII object keys are allowed",
                    ));
                }
                validate_restricted_value(item, depth + 1)?;
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

fn restricted_canonical_bytes(value: &Value) -> AuthorizationResult<Vec<u8>> {
    validate_restricted_value(value, 0)?;
    let mut sorted = value.clone();
    sort_object_keys(&mut sorted);
    let canonical = serde_json::to_vec(&sorted).map_err(|_| {
        authorization_error(
            "s18_canonical_encode",
            "restricted canonical JSON cannot be encoded",
        )
    })?;
    if canonical.len() > MAX_DOCUMENT_BYTES {
        return Err(authorization_error(
            "s18_canonical_size",
            "restricted canonical JSON exceeds 64 KiB",
        ));
    }
    Ok(canonical)
}

fn parse_restricted_canonical(raw: &[u8]) -> AuthorizationResult<Value> {
    if raw.len() > MAX_DOCUMENT_BYTES {
        return Err(authorization_error(
            "s18_canonical_size",
            "restricted canonical JSON exceeds 64 KiB",
        ));
    }
    let value: Value = serde_json::from_slice(raw).map_err(|_| {
        authorization_error(
            "s18_canonical_parse",
            "restricted canonical JSON cannot be parsed",
        )
    })?;
    let canonical = restricted_canonical_bytes(&value)?;
    if canonical != raw {
        return Err(authorization_error(
            "s18_canonical_bytes",
            "input is not exact compact sorted-key canonical bytes",
        ));
    }
    Ok(value)
}

fn object<'a>(value: &'a Value, code: &'static str) -> AuthorizationResult<&'a Map<String, Value>> {
    value
        .as_object()
        .ok_or_else(|| authorization_error(code, "expected a closed canonical JSON object"))
}

fn exact_keys(
    value: &Map<String, Value>,
    expected: &[&str],
    code: &'static str,
) -> AuthorizationResult<()> {
    let actual: BTreeSet<&str> = value.keys().map(String::as_str).collect();
    let expected: BTreeSet<&str> = expected.iter().copied().collect();
    if actual != expected {
        return Err(authorization_error(
            code,
            "closed object key set does not match the frozen contract",
        ));
    }
    Ok(())
}

fn string<'a>(value: &'a Map<String, Value>, key: &str) -> AuthorizationResult<&'a str> {
    value
        .get(key)
        .and_then(Value::as_str)
        .ok_or_else(|| authorization_error("s18_field_string", "required string field is missing"))
}

fn integer(value: &Map<String, Value>, key: &str) -> AuthorizationResult<u64> {
    value
        .get(key)
        .and_then(Value::as_u64)
        .ok_or_else(|| authorization_error("s18_field_integer", "required u64 field is missing"))
}

fn boolean(value: &Map<String, Value>, key: &str) -> AuthorizationResult<bool> {
    value.get(key).and_then(Value::as_bool).ok_or_else(|| {
        authorization_error("s18_field_boolean", "required boolean field is missing")
    })
}

fn require_string(
    value: &Map<String, Value>,
    key: &str,
    expected: &str,
) -> AuthorizationResult<()> {
    if string(value, key)? != expected {
        return Err(authorization_error(
            "s18_field_constant",
            "string field does not match the frozen constant",
        ));
    }
    Ok(())
}

fn require_bool(value: &Map<String, Value>, key: &str, expected: bool) -> AuthorizationResult<()> {
    if boolean(value, key)? != expected {
        return Err(authorization_error(
            "s18_field_constant",
            "boolean field does not match the frozen constant",
        ));
    }
    Ok(())
}

fn require_null(value: &Map<String, Value>, key: &str) -> AuthorizationResult<()> {
    if !value.get(key).is_some_and(Value::is_null) {
        return Err(authorization_error(
            "s18_lifecycle_null",
            "unclaimed envelope contains a later-lifecycle receipt or capability",
        ));
    }
    Ok(())
}

fn append_u32_frame(message: &mut Vec<u8>, value: &[u8]) -> AuthorizationResult<()> {
    let len = u32::try_from(value.len())
        .map_err(|_| authorization_error("s18_frame_length", "message frame exceeds u32"))?;
    message.extend_from_slice(&len.to_be_bytes());
    message.extend_from_slice(value);
    Ok(())
}

fn signed_message(payload_sha256: &[u8; 32]) -> AuthorizationResult<Vec<u8>> {
    let mut message = Vec::with_capacity(4 + MESSAGE_DOMAIN.len() + 8 + 32);
    append_u32_frame(&mut message, MESSAGE_DOMAIN)?;
    message.extend_from_slice(&(payload_sha256.len() as u64).to_be_bytes());
    message.extend_from_slice(payload_sha256);
    Ok(message)
}

fn authorization_id(payload: &Map<String, Value>) -> AuthorizationResult<[u8; 32]> {
    let mut without_id = payload.clone();
    without_id
        .remove("authorization_id_sha256")
        .ok_or_else(|| {
            authorization_error("s18_authorization_id", "authorization ID field is missing")
        })?;
    let bytes = restricted_canonical_bytes(&Value::Object(without_id))?;
    let digest = sha256_bytes(&bytes);
    let mut message = Vec::with_capacity(4 + AUTHORIZATION_ID_DOMAIN.len() + 8 + 32);
    append_u32_frame(&mut message, AUTHORIZATION_ID_DOMAIN)?;
    message.extend_from_slice(&(digest.len() as u64).to_be_bytes());
    message.extend_from_slice(&digest);
    Ok(sha256_bytes(&message))
}

#[derive(Clone)]
struct OwnerTrustAnchorV1 {
    document_sha256: [u8; 32],
    owner_identity_sha256: [u8; 32],
    owner_key_id: String,
    owner_key_version: u64,
    public_key: [u8; 32],
    trust_policy_sha256: [u8; 32],
    minimum_revocation_epoch: u64,
}

impl fmt::Debug for OwnerTrustAnchorV1 {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        formatter
            .debug_struct("OwnerTrustAnchorV1")
            .field("scope", &"[OWNER_PINNED_PUBLIC_KEY_REDACTED]")
            .finish_non_exhaustive()
    }
}

fn parse_anchor(
    raw: &[u8],
    expected_document_sha256: &[u8; 32],
) -> AuthorizationResult<OwnerTrustAnchorV1> {
    if raw.len() > MAX_DOCUMENT_BYTES {
        return Err(authorization_error(
            "s18_canonical_size",
            "anchor document exceeds 64 KiB",
        ));
    }
    let actual_document_sha256 = sha256_bytes(raw);
    if actual_document_sha256 != *expected_document_sha256 {
        return Err(authorization_error(
            "s18_anchor_pin",
            "anchor document does not match the independently pinned digest",
        ));
    }
    let value = parse_restricted_canonical(raw)?;
    let anchor = object(&value, "s18_anchor_object")?;
    exact_keys(anchor, ANCHOR_KEYS, "s18_anchor_keys")?;
    require_string(anchor, "schema", ANCHOR_SCHEMA)?;
    require_string(
        anchor,
        "packet_kind",
        "OUT_OF_BAND_OWNED_LAB_OWNER_TRUST_ANCHOR",
    )?;
    require_string(anchor, "canonicalization", CANONICAL_PROFILE)?;
    require_string(anchor, "anchor_state", "ACTIVE_OWNER_PINNED_PUBLIC_KEY")?;
    require_string(
        anchor,
        "installation_source",
        "OWNER_CONTROLLED_OUT_OF_BAND_PIN_NOT_AUTHORIZATION_ENVELOPE",
    )?;
    require_string(anchor, "owner_role", "OWNED_LAB_EXECUTION_OWNER")?;
    require_string(anchor, "signature_algorithm", "Ed25519")?;
    require_string(anchor, "audience", "AGENT_BRIDGE_S18_OWNED_LAB_L1_ONLY")?;
    require_string(
        anchor,
        "authorized_claim_level",
        "L1_PROCESS_CRASH_FRESH_PROCESS_RESTART_ONLY",
    )?;
    require_string(
        anchor,
        "authorized_family_namespace",
        "OL00_OL04_OL05_FIRST_BATCH",
    )?;
    require_string(anchor, "side_effects_unlocked", "NONE")?;
    for key in [
        "private_key_present",
        "self_asserted_key_is_owner_authentication",
        "authorization_envelope_embedded",
        "execution_capability_embedded",
        "provider_or_production_authority",
    ] {
        require_bool(anchor, key, false)?;
    }
    let owner_key_id = string(anchor, "owner_key_id")?;
    if !valid_label(owner_key_id) {
        return Err(authorization_error(
            "s18_anchor_key_id",
            "anchor key ID is not a canonical label",
        ));
    }
    let owner_identity_sha256 = decode_hex_fixed::<32>(string(anchor, "owner_identity_sha256")?)?;
    let public_key = decode_hex_fixed::<32>(string(anchor, "ed25519_public_key_hex")?)?;
    let trust_policy_sha256 = decode_hex_fixed::<32>(string(anchor, "trust_policy_sha256")?)?;
    let installation = decode_hex_fixed::<32>(string(anchor, "installation_receipt_sha256")?)?;
    let identity_receipt = decode_hex_fixed::<32>(string(
        anchor,
        "owner_identity_verification_receipt_sha256",
    )?)?;
    if ![
        &owner_identity_sha256[..],
        &public_key[..],
        &trust_policy_sha256[..],
        &installation[..],
        &identity_receipt[..],
    ]
    .iter()
    .all(|value| nonzero(value))
    {
        return Err(authorization_error(
            "s18_anchor_nonzero",
            "anchor identity, key, trust, and installation commitments must be nonzero",
        ));
    }
    let owner_key_version = integer(anchor, "owner_key_version")?;
    let minimum_revocation_epoch = integer(anchor, "minimum_revocation_epoch")?;
    if owner_key_version == 0 || minimum_revocation_epoch == 0 {
        return Err(authorization_error(
            "s18_anchor_version",
            "anchor key version and revocation floor must be nonzero",
        ));
    }
    Ok(OwnerTrustAnchorV1 {
        document_sha256: actual_document_sha256,
        owner_identity_sha256,
        owner_key_id: owner_key_id.to_owned(),
        owner_key_version,
        public_key,
        trust_policy_sha256,
        minimum_revocation_epoch,
    })
}

#[derive(Clone)]
struct ExpectedOwnedLabAuthorizationBindingV1 {
    trust_anchor_document_sha256: [u8; 32],
    payload: Value,
}

impl fmt::Debug for ExpectedOwnedLabAuthorizationBindingV1 {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        formatter
            .debug_struct("ExpectedOwnedLabAuthorizationBindingV1")
            .field("scope", &"[EXACT_SIGNED_SUBJECT_AND_RESOURCE_BINDING]")
            .finish_non_exhaustive()
    }
}

#[must_use]
struct VerifiedUnclaimedOwnedLabAuthorizationV1 {
    authorization_id_sha256: [u8; 32],
    payload_sha256: [u8; 32],
    revocation_epoch: u64,
}

impl fmt::Debug for VerifiedUnclaimedOwnedLabAuthorizationV1 {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        formatter
            .debug_struct("VerifiedUnclaimedOwnedLabAuthorizationV1")
            .field("state", &"[AUTHENTICATED_UNCLAIMED_NOT_CAPABILITY]")
            .field("revocation_epoch", &self.revocation_epoch)
            .finish_non_exhaustive()
    }
}

fn validate_payload_constants(
    payload: &Map<String, Value>,
    anchor: &OwnerTrustAnchorV1,
) -> AuthorizationResult<()> {
    exact_keys(payload, PAYLOAD_KEYS, "s18_payload_keys")?;
    require_string(payload, "decision_state", DECISION_STATE)?;
    require_string(payload, "decision_reason", DECISION_REASON)?;
    require_bool(payload, "owner_scope_authorized", true)?;
    for key in [
        "owned_lab_execution_authorized",
        "single_use_execution_capability_issued",
        "execution_start_permitted",
        "timestamps_are_authorization_freshness",
        "retry_or_implicit_rerun_allowed",
        "stop_state_at_signing_audit_only",
        "network_allowed",
        "provider_access_allowed",
        "production_access_allowed",
        "credential_access_allowed",
        "paid_resource_allowed",
        "root_or_privilege_escalation_allowed",
        "mount_or_unmount_allowed",
        "reboot_kernel_crash_or_power_fault_allowed",
        "direct_block_device_write_allowed",
        "agent_bridge_application_side_effect_allowed",
        "schema_conformance_alone_authorizes_execution",
        "owner_envelope_is_bearer_capability",
        "process_crash_is_power_loss_proof",
    ] {
        require_bool(payload, key, false)?;
    }
    require_bool(payload, "single_use_claim_required", true)?;
    require_bool(payload, "atomic_claim_receipt_required_before_start", true)?;
    require_bool(
        payload,
        "use_time_external_absorbing_stop_check_required",
        true,
    )?;
    require_bool(
        payload,
        "use_time_current_revocation_epoch_check_required",
        true,
    )?;
    for key in [
        "trusted_time_receipt_sha256",
        "cas_claim_receipt_sha256",
        "claimed_run_id_sha256",
        "execution_capability_sha256",
        "post_run_cleanup_receipt_sha256",
        "post_run_custody_receipt_sha256",
    ] {
        require_null(payload, key)?;
    }
    require_string(payload, "owner_role", "OWNED_LAB_EXECUTION_OWNER")?;
    require_string(payload, "audience", "AGENT_BRIDGE_S18_OWNED_LAB_L1_ONLY")?;
    require_string(
        payload,
        "validity_control",
        "SINGLE_USE_CAS_REVOCATION_EPOCH_AND_ABSORBING_STOP_NOT_WALL_CLOCK",
    )?;
    require_string(payload, "s17_source_commit", S17_SOURCE_COMMIT)?;
    require_string(payload, "s17_integration_commit", S17_INTEGRATION_COMMIT)?;
    require_string(payload, "s16_integration_commit", S16_INTEGRATION_COMMIT)?;
    require_string(payload, "s17_plan_sha256", S17_PLAN_SHA256)?;
    require_string(
        payload,
        "s17_observation_schema_sha256",
        S17_OBSERVATION_SCHEMA_SHA256,
    )?;
    require_string(
        payload,
        "s17_pending_owner_schema_sha256",
        S17_PENDING_OWNER_SCHEMA_SHA256,
    )?;
    require_string(
        payload,
        "s17_successor_gate_sha256",
        S17_SUCCESSOR_GATE_SHA256,
    )?;
    require_string(
        payload,
        "claim_level",
        "L1_PROCESS_CRASH_FRESH_PROCESS_RESTART_ONLY",
    )?;
    require_string(payload, "family_id_namespace", "OL00_OL04_OL05_FIRST_BATCH")?;
    require_string(payload, "side_effects_unlocked", "NONE")?;
    if payload.get("authorized_family_ids") != Some(&serde_json::json!(["OL00", "OL04", "OL05"]))
        || payload.get("authorized_family_scenario_counts")
            != Some(&serde_json::json!({"OL00": 1, "OL04": 6, "OL05": 53}))
        || integer(payload, "canary_batch_count")? != 1
        || integer(payload, "assigned_attempt_count")? != 60
        || integer(payload, "planned_pidfd_sigkill_attempt_count")? != 59
        || integer(payload, "planned_distinct_fresh_exec_read_count")? != 59
        || integer(payload, "planned_total_s16_mapping_phase_record_count")? != 113
        || integer(payload, "maximum_successful_claims")? != 1
        || integer(payload, "expected_unclaimed_revision")? == 0
    {
        return Err(authorization_error(
            "s18_canary_scope",
            "family, count, phase, claim, or revision scope drifted",
        ));
    }
    if string(payload, "owner_key_id")? != anchor.owner_key_id
        || integer(payload, "owner_key_version")? != anchor.owner_key_version
        || decode_hex_fixed::<32>(string(payload, "owner_identity_sha256")?)?
            != anchor.owner_identity_sha256
        || decode_hex_fixed::<32>(string(payload, "trust_anchor_document_sha256")?)?
            != anchor.document_sha256
        || decode_hex_fixed::<32>(string(payload, "trust_policy_sha256")?)?
            != anchor.trust_policy_sha256
        || integer(payload, "revocation_epoch")? < anchor.minimum_revocation_epoch
    {
        return Err(authorization_error(
            "s18_owner_binding",
            "payload does not match the independent owner trust anchor and revocation floor",
        ));
    }
    if !valid_label(string(payload, "owner_key_id")?) {
        return Err(authorization_error(
            "s18_owner_key_id",
            "payload owner key ID is not canonical",
        ));
    }
    let issued =
        audit_time_key(string(payload, "decision_issued_at_utc_audit_only")?).ok_or_else(|| {
            authorization_error(
                "s18_audit_time",
                "signed issue time is outside the frozen UTC audit form",
            )
        })?;
    let expires = audit_time_key(string(payload, "decision_expires_at_utc_audit_only")?)
        .ok_or_else(|| {
            authorization_error(
                "s18_audit_time",
                "signed expiry time is outside the frozen UTC audit form",
            )
        })?;
    if expires <= issued {
        return Err(authorization_error(
            "s18_audit_time_order",
            "signed audit expiry must be strictly after issue time",
        ));
    }
    for key in PAYLOAD_KEYS {
        if key.ends_with("_sha256")
            && ![
                "trusted_time_receipt_sha256",
                "cas_claim_receipt_sha256",
                "claimed_run_id_sha256",
                "execution_capability_sha256",
                "post_run_cleanup_receipt_sha256",
                "post_run_custody_receipt_sha256",
            ]
            .contains(key)
        {
            let digest = decode_hex_fixed::<32>(string(payload, key)?)?;
            if !nonzero(&digest) {
                return Err(authorization_error(
                    "s18_payload_nonzero",
                    "signed payload commitment must be nonzero",
                ));
            }
        }
    }
    let runner_source_commit = decode_hex_fixed::<20>(string(payload, "runner_source_commit")?)?;
    let s19_integration_commit =
        decode_hex_fixed::<20>(string(payload, "s19_integration_commit")?)?;
    if !nonzero(&runner_source_commit) || !nonzero(&s19_integration_commit) {
        return Err(authorization_error(
            "s18_runner_commit",
            "source-bound runner and S19 integration commits must be nonzero",
        ));
    }
    Ok(())
}

fn verify_unclaimed_owner_authorization_v1(
    anchor_raw: &[u8],
    envelope_raw: &[u8],
    expected: &ExpectedOwnedLabAuthorizationBindingV1,
) -> AuthorizationResult<VerifiedUnclaimedOwnedLabAuthorizationV1> {
    let anchor = parse_anchor(anchor_raw, &expected.trust_anchor_document_sha256)?;
    let envelope_value = parse_restricted_canonical(envelope_raw)?;
    let envelope = object(&envelope_value, "s18_envelope_object")?;
    exact_keys(envelope, ENVELOPE_KEYS, "s18_envelope_keys")?;
    require_string(envelope, "schema", ENVELOPE_SCHEMA)?;
    require_string(
        envelope,
        "packet_kind",
        "OWNER_SIGNED_OWNED_LAB_AUTHORIZATION_ENVELOPE",
    )?;
    require_string(envelope, "canonicalization", CANONICAL_PROFILE)?;
    require_string(envelope, "signature_message_profile", MESSAGE_PROFILE)?;
    let payload_value = envelope
        .get("payload")
        .ok_or_else(|| authorization_error("s18_payload", "signed payload is missing"))?;
    let payload = object(payload_value, "s18_payload_object")?;
    validate_payload_constants(payload, &anchor)?;
    if payload_value != &expected.payload {
        return Err(authorization_error(
            "s18_expected_binding",
            "signed payload does not equal the caller-pinned subject and resource binding",
        ));
    }
    let expected_authorization_id = authorization_id(payload)?;
    if decode_hex_fixed::<32>(string(payload, "authorization_id_sha256")?)?
        != expected_authorization_id
    {
        return Err(authorization_error(
            "s18_authorization_id",
            "authorization ID does not bind the exact payload without its self field",
        ));
    }
    let payload_raw = restricted_canonical_bytes(payload_value)?;
    let payload_sha256 = sha256_bytes(&payload_raw);

    let authentication_value = envelope.get("authentication").ok_or_else(|| {
        authorization_error("s18_authentication", "authentication object is missing")
    })?;
    let authentication = object(authentication_value, "s18_authentication_object")?;
    exact_keys(
        authentication,
        AUTHENTICATION_KEYS,
        "s18_authentication_keys",
    )?;
    require_string(authentication, "signature_algorithm", "Ed25519")?;
    require_string(
        authentication,
        "signature_message_domain",
        std::str::from_utf8(MESSAGE_DOMAIN).expect("ASCII domain"),
    )?;
    require_bool(authentication, "public_key_carried_by_envelope", false)?;
    require_bool(authentication, "self_asserted_signature_valid", false)?;
    if decode_hex_fixed::<32>(string(authentication, "signed_payload_sha256")?)? != payload_sha256 {
        return Err(authorization_error(
            "s18_payload_digest",
            "authentication payload digest does not match canonical payload bytes",
        ));
    }
    let signature = decode_hex_fixed::<64>(string(authentication, "detached_signature_hex")?)?;
    if decode_hex_fixed::<32>(string(authentication, "detached_signature_sha256")?)?
        != sha256_bytes(&signature)
    {
        return Err(authorization_error(
            "s18_signature_digest",
            "detached signature digest does not match signature bytes",
        ));
    }
    let message = signed_message(&payload_sha256)?;
    UnparsedPublicKey::new(&ED25519, anchor.public_key)
        .verify(&message, &signature)
        .map_err(|_| {
            authorization_error(
                "s18_signature",
                "owner-pinned Ed25519 key does not authenticate the exact signed payload",
            )
        })?;
    Ok(VerifiedUnclaimedOwnedLabAuthorizationV1 {
        authorization_id_sha256: expected_authorization_id,
        payload_sha256,
        revocation_epoch: integer(payload, "revocation_epoch")?,
    })
}

#[cfg(test)]
mod tests {
    use super::*;
    use ring::signature::{Ed25519KeyPair, KeyPair};

    // RFC8032 TEST_ONLY seed/public key. This public test identity is never owner authority.
    const RFC8032_TEST_ONLY_SEED: [u8; 32] = [
        0x9d, 0x61, 0xb1, 0x9d, 0xef, 0xfd, 0x5a, 0x60, 0xba, 0x84, 0x4a, 0xf4, 0x92, 0xec, 0x2c,
        0xc4, 0x44, 0x49, 0xc5, 0x69, 0x7b, 0x32, 0x69, 0x19, 0x70, 0x3b, 0xac, 0x03, 0x1c, 0xae,
        0x7f, 0x60,
    ];
    const RFC8032_TEST_ONLY_PUBLIC_KEY: [u8; 32] = [
        0xd7, 0x5a, 0x98, 0x01, 0x82, 0xb1, 0x0a, 0xb7, 0xd5, 0x4b, 0xfe, 0xd3, 0xc9, 0x64, 0x07,
        0x3a, 0x0e, 0xe1, 0x72, 0xf3, 0xda, 0xa6, 0x23, 0x25, 0xaf, 0x02, 0x1a, 0x68, 0xf7, 0x07,
        0x51, 0x1a,
    ];

    fn hex(bytes: &[u8]) -> String {
        let mut output = String::with_capacity(bytes.len() * 2);
        for byte in bytes {
            use std::fmt::Write as _;
            write!(&mut output, "{byte:02x}").unwrap();
        }
        output
    }

    fn repeated(value: u8) -> String {
        hex(&[value; 32])
    }

    fn key_pair() -> Ed25519KeyPair {
        Ed25519KeyPair::from_seed_unchecked(&RFC8032_TEST_ONLY_SEED).expect("RFC8032 TEST_ONLY key")
    }

    fn canonical(value: &Value) -> Vec<u8> {
        restricted_canonical_bytes(value).unwrap()
    }

    fn anchor_value() -> Value {
        serde_json::json!({
            "anchor_state": "ACTIVE_OWNER_PINNED_PUBLIC_KEY",
            "audience": "AGENT_BRIDGE_S18_OWNED_LAB_L1_ONLY",
            "authorization_envelope_embedded": false,
            "authorized_claim_level": "L1_PROCESS_CRASH_FRESH_PROCESS_RESTART_ONLY",
            "authorized_family_namespace": "OL00_OL04_OL05_FIRST_BATCH",
            "canonicalization": CANONICAL_PROFILE,
            "ed25519_public_key_hex": hex(&RFC8032_TEST_ONLY_PUBLIC_KEY),
            "execution_capability_embedded": false,
            "installation_receipt_sha256": repeated(0x91),
            "installation_source": "OWNER_CONTROLLED_OUT_OF_BAND_PIN_NOT_AUTHORIZATION_ENVELOPE",
            "minimum_revocation_epoch": 7,
            "owner_identity_sha256": repeated(0x81),
            "owner_identity_verification_receipt_sha256": repeated(0x92),
            "owner_key_id": "rfc8032-test-only-owner",
            "owner_key_version": 3,
            "owner_role": "OWNED_LAB_EXECUTION_OWNER",
            "packet_kind": "OUT_OF_BAND_OWNED_LAB_OWNER_TRUST_ANCHOR",
            "private_key_present": false,
            "provider_or_production_authority": false,
            "schema": ANCHOR_SCHEMA,
            "self_asserted_key_is_owner_authentication": false,
            "side_effects_unlocked": "NONE",
            "signature_algorithm": "Ed25519",
            "trust_policy_sha256": repeated(0x82)
        })
    }

    fn payload_value(anchor_sha256: [u8; 32]) -> Value {
        let parts = [
            serde_json::json!({
                "agent_bridge_application_side_effect_allowed": false,
                "assigned_attempt_count": 60,
                "assignment_set_sha256": repeated(0x11),
                "atomic_claim_receipt_required_before_start": true,
                "audience": "AGENT_BRIDGE_S18_OWNED_LAB_L1_ONLY",
                "authorization_id_sha256": repeated(0xff),
                "authorized_family_ids": ["OL00", "OL04", "OL05"],
                "authorized_family_scenario_counts": {"OL00": 1, "OL04": 6, "OL05": 53},
                "canary_batch_count": 1,
                "capability_nonce_sha256": repeated(0x12),
                "cas_claim_receipt_sha256": null,
                "claim_key_sha256": repeated(0x13),
                "claim_level": "L1_PROCESS_CRASH_FRESH_PROCESS_RESTART_ONLY",
                "claim_namespace_sha256": repeated(0x14),
                "claimed_run_id_sha256": null,
                "classifier_binary_sha256": repeated(0x15),
                "classifier_source_sha256": repeated(0x16),
                "cleanup_policy_sha256": repeated(0x17),
                "control_protocol_sha256": repeated(0x18),
                "credential_access_allowed": false,
                "decision_expires_at_utc_audit_only": "2026-07-17T00:15:00Z",
                "decision_issued_at_utc_audit_only": "2026-07-17T00:00:00Z",
                "decision_nonce_sha256": repeated(0x19)
            }),
            serde_json::json!({
                "decision_reason": DECISION_REASON,
                "decision_state": DECISION_STATE,
                "direct_block_device_write_allowed": false,
                "execution_capability_sha256": null,
                "execution_start_permitted": false,
                "expected_oracle_sha256": repeated(0x1a),
                "expected_unclaimed_revision": 41,
                "family_id_namespace": "OL00_OL04_OL05_FIRST_BATCH",
                "live_observation_validator_binary_sha256": repeated(0x2c),
                "live_observation_validator_ruleset_sha256": repeated(0x2d),
                "live_observation_validator_source_sha256": repeated(0x2e),
                "live_observation_validator_toolchain_sha256": repeated(0x2f),
                "maximum_successful_claims": 1,
                "mount_or_unmount_allowed": false,
                "network_allowed": false,
                "owner_authorization_validator_binary_sha256": repeated(0x26),
                "owner_authorization_validator_ruleset_sha256": repeated(0x25),
                "owner_authorization_validator_source_sha256": repeated(0x27),
                "owner_authorization_validator_toolchain_sha256": repeated(0x28),
                "owner_envelope_is_bearer_capability": false,
                "owner_identity_sha256": repeated(0x81),
                "owner_key_id": "rfc8032-test-only-owner",
                "owner_key_version": 3,
                "owner_role": "OWNED_LAB_EXECUTION_OWNER",
                "owner_scope_authorized": true,
                "owned_lab_execution_authorized": false,
                "paid_resource_allowed": false,
                "planned_distinct_fresh_exec_read_count": 59,
                "planned_pidfd_sigkill_attempt_count": 59,
                "planned_total_s16_mapping_phase_record_count": 113,
                "positive_owner_schema_sha256": repeated(0x1b)
            }),
            serde_json::json!({
                "post_run_cleanup_receipt_sha256": null,
                "post_run_custody_receipt_sha256": null,
                "preflight_policy_sha256": repeated(0x1c),
                "process_crash_is_power_loss_proof": false,
                "production_access_allowed": false,
                "provider_access_allowed": false,
                "reboot_kernel_crash_or_power_fault_allowed": false,
                "resource_scope_sha256": repeated(0x1d),
                "retention_policy_sha256": repeated(0x1e),
                "retry_or_implicit_rerun_allowed": false,
                "revocation_epoch": 7,
                "review_policy_sha256": repeated(0x1f),
                "root_or_privilege_escalation_allowed": false,
                "runner_binary_sha256": repeated(0x20),
                "runner_source_commit": "1111111111111111111111111111111111111111",
                "runner_source_sha256": repeated(0x21),
                "runner_toolchain_sha256": repeated(0x22),
                "s16_integration_commit": S16_INTEGRATION_COMMIT,
                "s17_integration_commit": S17_INTEGRATION_COMMIT,
                "s17_observation_schema_sha256": S17_OBSERVATION_SCHEMA_SHA256,
                "s17_pending_owner_schema_sha256": S17_PENDING_OWNER_SCHEMA_SHA256,
                "s17_plan_sha256": S17_PLAN_SHA256,
                "s17_source_commit": S17_SOURCE_COMMIT,
                "s17_successor_gate_sha256": S17_SUCCESSOR_GATE_SHA256,
                "s19_integration_commit": "2222222222222222222222222222222222222222",
                "s19_subject_manifest_schema_sha256": repeated(0x30),
                "s19_subject_manifest_sha256": repeated(0x31)
            }),
            serde_json::json!({
                "safety_policy_sha256": repeated(0x23),
                "schedule_sha256": repeated(0x24),
                "schema_conformance_alone_authorizes_execution": false,
                "side_effects_unlocked": "NONE",
                "single_use_claim_required": true,
                "single_use_execution_capability_issued": false,
                "sqlite_profile_sha256": repeated(0x29),
                "sqlite_schema_sha256": repeated(0x2a),
                "stop_control_policy_sha256": repeated(0x2b),
                "stop_state_at_signing_audit_only": false,
                "timestamps_are_authorization_freshness": false,
                "trusted_time_receipt_sha256": null,
                "trust_anchor_document_sha256": hex(&anchor_sha256),
                "trust_policy_sha256": repeated(0x82),
                "use_time_current_revocation_epoch_check_required": true,
                "use_time_external_absorbing_stop_check_required": true,
                "validity_control": "SINGLE_USE_CAS_REVOCATION_EPOCH_AND_ABSORBING_STOP_NOT_WALL_CLOCK"
            }),
        ];
        let mut payload = Map::new();
        for part in parts {
            payload.extend(part.as_object().expect("test payload part").clone());
        }
        let id = authorization_id(&payload).unwrap();
        payload.insert("authorization_id_sha256".into(), Value::String(hex(&id)));
        Value::Object(payload)
    }

    fn resign(payload: Value, key: &Ed25519KeyPair) -> Value {
        let payload_raw = canonical(&payload);
        let payload_sha = sha256_bytes(&payload_raw);
        let signature: [u8; 64] = key
            .sign(&signed_message(&payload_sha).unwrap())
            .as_ref()
            .try_into()
            .unwrap();
        serde_json::json!({
            "authentication": {
                "detached_signature_hex": hex(&signature),
                "detached_signature_sha256": hex(&sha256_bytes(&signature)),
                "public_key_carried_by_envelope": false,
                "self_asserted_signature_valid": false,
                "signature_algorithm": "Ed25519",
                "signature_message_domain": std::str::from_utf8(MESSAGE_DOMAIN).unwrap(),
                "signed_payload_sha256": hex(&payload_sha)
            },
            "canonicalization": CANONICAL_PROFILE,
            "packet_kind": "OWNER_SIGNED_OWNED_LAB_AUTHORIZATION_ENVELOPE",
            "payload": payload,
            "schema": ENVELOPE_SCHEMA,
            "signature_message_profile": MESSAGE_PROFILE
        })
    }

    fn fixture() -> (Vec<u8>, Vec<u8>, ExpectedOwnedLabAuthorizationBindingV1) {
        let anchor = anchor_value();
        let anchor_raw = canonical(&anchor);
        let anchor_sha = sha256_bytes(&anchor_raw);
        let payload = payload_value(anchor_sha);
        let envelope = resign(payload.clone(), &key_pair());
        (
            anchor_raw,
            canonical(&envelope),
            ExpectedOwnedLabAuthorizationBindingV1 {
                trust_anchor_document_sha256: anchor_sha,
                payload,
            },
        )
    }

    fn mutate_payload_and_resign(
        envelope_raw: &[u8],
        mutate: impl FnOnce(&mut Map<String, Value>),
    ) -> Vec<u8> {
        let mut envelope: Value = serde_json::from_slice(envelope_raw).unwrap();
        let payload = envelope
            .get_mut("payload")
            .and_then(Value::as_object_mut)
            .unwrap();
        mutate(payload);
        if payload.contains_key("authorization_id_sha256") {
            let id = authorization_id(payload).unwrap();
            payload.insert("authorization_id_sha256".into(), Value::String(hex(&id)));
        }
        let payload = envelope.get("payload").unwrap().clone();
        canonical(&resign(payload, &key_pair()))
    }

    #[test]
    fn s18_rfc8032_test_only_authenticated_unclaimed_accepts_without_capability() {
        assert_eq!(
            hex(key_pair().sign(b"").as_ref()),
            concat!(
                "e5564300c360ac729086e2cc806e828a84877f1eb8e5d974d873e06522490155",
                "5fb8821590a33bacc61e39701cf9b46bd25bf5f0595bbe24655141438e7a100b"
            )
        );
        assert_eq!(
            hex(&signed_message(&[0x42; 32]).unwrap()),
            concat!(
                "0000003b6167656e742d6272696467652f62696f636f727465782f6f776e6564",
                "2d6c61622f6f776e65722d617574686f72697a6174696f6e2f7331382f7631",
                "0000000000000020424242424242424242424242424242424242424242424242",
                "4242424242424242"
            )
        );
        let mut authorization_id_kat = Map::new();
        authorization_id_kat.insert("audience".into(), Value::String("kat".into()));
        authorization_id_kat.insert(
            "authorization_id_sha256".into(),
            Value::String("0".repeat(64)),
        );
        authorization_id_kat.insert("revision".into(), Value::from(7));
        assert_eq!(
            hex(&authorization_id(&authorization_id_kat).unwrap()),
            "7c614e15d0aeaf93efb313e2857fb5b9664d4b913c063c2a30ca0e11a2295f5b"
        );
        let (anchor, envelope, expected) = fixture();
        let verified = verify_unclaimed_owner_authorization_v1(&anchor, &envelope, &expected)
            .expect("synthetic authenticated-unclaimed fixture");
        assert!(nonzero(&verified.authorization_id_sha256));
        assert!(nonzero(&verified.payload_sha256));
        assert_eq!(verified.revocation_epoch, 7);
        assert!(format!("{verified:?}").contains("NOT_CAPABILITY"));
        assert_eq!(FUTURE_TRANSITION, "UNCLAIMED_TO_CONSUMED_FOR_EXACT_RUN");
    }

    #[test]
    fn s18_signature_message_digest_and_signature_tamper_reject() {
        let (anchor, envelope, expected) = fixture();
        let mut value: Value = serde_json::from_slice(&envelope).unwrap();
        value["authentication"]["signed_payload_sha256"] = Value::String(repeated(0x55));
        assert_eq!(
            verify_unclaimed_owner_authorization_v1(&anchor, &canonical(&value), &expected)
                .unwrap_err()
                .code(),
            "s18_payload_digest"
        );
        let mut value: Value = serde_json::from_slice(&envelope).unwrap();
        value["authentication"]["detached_signature_sha256"] = Value::String(repeated(0x56));
        assert_eq!(
            verify_unclaimed_owner_authorization_v1(&anchor, &canonical(&value), &expected)
                .unwrap_err()
                .code(),
            "s18_signature_digest"
        );
        let mut value: Value = serde_json::from_slice(&envelope).unwrap();
        let signature = value["authentication"]["detached_signature_hex"]
            .as_str()
            .unwrap();
        let replacement = format!(
            "{}{}",
            if &signature[..2] == "00" { "01" } else { "00" },
            &signature[2..]
        );
        value["authentication"]["detached_signature_hex"] = Value::String(replacement);
        let signature = decode_hex_fixed::<64>(
            value["authentication"]["detached_signature_hex"]
                .as_str()
                .unwrap(),
        )
        .unwrap();
        value["authentication"]["detached_signature_sha256"] =
            Value::String(hex(&sha256_bytes(&signature)));
        assert_eq!(
            verify_unclaimed_owner_authorization_v1(&anchor, &canonical(&value), &expected)
                .unwrap_err()
                .code(),
            "s18_signature"
        );

        let mut wrong_authorization_id: Value = serde_json::from_slice(&envelope).unwrap();
        wrong_authorization_id["payload"]["authorization_id_sha256"] =
            Value::String(repeated(0x77));
        let wrong_payload = wrong_authorization_id["payload"].clone();
        let wrong_authorization_id = canonical(&resign(wrong_payload.clone(), &key_pair()));
        let mut wrong_expected = expected.clone();
        wrong_expected.payload = wrong_payload;
        assert_eq!(
            verify_unclaimed_owner_authorization_v1(
                &anchor,
                &wrong_authorization_id,
                &wrong_expected,
            )
            .unwrap_err()
            .code(),
            "s18_authorization_id"
        );
    }

    #[test]
    fn s18_anchor_substitution_and_envelope_carried_key_reject() {
        let (anchor, envelope, expected) = fixture();
        let mut anchor_value: Value = serde_json::from_slice(&anchor).unwrap();
        anchor_value["ed25519_public_key_hex"] = Value::String(repeated(0x66));
        assert_eq!(
            verify_unclaimed_owner_authorization_v1(
                &canonical(&anchor_value),
                &envelope,
                &expected
            )
            .unwrap_err()
            .code(),
            "s18_anchor_pin"
        );
        let mut envelope_value: Value = serde_json::from_slice(&envelope).unwrap();
        envelope_value["authentication"]["public_key_carried_by_envelope"] = Value::Bool(true);
        assert!(verify_unclaimed_owner_authorization_v1(
            &anchor,
            &canonical(&envelope_value),
            &expected
        )
        .is_err());

        let second_key =
            Ed25519KeyPair::from_seed_unchecked(&[0x42; 32]).expect("second TEST_ONLY key");
        let mut second_anchor: Value = serde_json::from_slice(&anchor).unwrap();
        second_anchor["ed25519_public_key_hex"] =
            Value::String(hex(second_key.public_key().as_ref()));
        let second_anchor = canonical(&second_anchor);
        let second_anchor_sha256 = sha256_bytes(&second_anchor);
        let mut second_payload = expected.payload.clone();
        second_payload["trust_anchor_document_sha256"] = Value::String(hex(&second_anchor_sha256));
        let second_payload_object = second_payload.as_object_mut().unwrap();
        let second_authorization_id = authorization_id(second_payload_object).unwrap();
        second_payload_object.insert(
            "authorization_id_sha256".into(),
            Value::String(hex(&second_authorization_id)),
        );
        let first_key_signature = canonical(&resign(second_payload.clone(), &key_pair()));
        let second_expected = ExpectedOwnedLabAuthorizationBindingV1 {
            trust_anchor_document_sha256: second_anchor_sha256,
            payload: second_payload,
        };
        assert_eq!(
            verify_unclaimed_owner_authorization_v1(
                &second_anchor,
                &first_key_signature,
                &second_expected,
            )
            .unwrap_err()
            .code(),
            "s18_signature"
        );
    }

    #[test]
    fn s18_resigned_subject_resource_and_count_drift_reject() {
        let (anchor, envelope, expected) = fixture();
        for mutated in [
            mutate_payload_and_resign(&envelope, |payload| {
                payload.insert(
                    "resource_scope_sha256".into(),
                    Value::String(repeated(0x44)),
                );
            }),
            mutate_payload_and_resign(&envelope, |payload| {
                payload.insert("runner_binary_sha256".into(), Value::String(repeated(0x45)));
            }),
        ] {
            assert!(verify_unclaimed_owner_authorization_v1(&anchor, &mutated, &expected).is_err());
        }
        let wrong_count = mutate_payload_and_resign(&envelope, |payload| {
            payload.insert("assigned_attempt_count".into(), Value::from(61));
        });
        let mut wrong_count_expected = expected.clone();
        wrong_count_expected.payload =
            serde_json::from_slice::<Value>(&wrong_count).unwrap()["payload"].clone();
        assert_eq!(
            verify_unclaimed_owner_authorization_v1(&anchor, &wrong_count, &wrong_count_expected,)
                .unwrap_err()
                .code(),
            "s18_canary_scope"
        );
        for mutated in [
            mutate_payload_and_resign(&envelope, |payload| {
                payload.insert("runner_source_commit".into(), Value::String("0".repeat(40)));
            }),
            mutate_payload_and_resign(&envelope, |payload| {
                payload.insert(
                    "decision_issued_at_utc_audit_only".into(),
                    Value::String("xxxxxxxxxxxxxxxxxxxZ".into()),
                );
            }),
            mutate_payload_and_resign(&envelope, |payload| {
                payload.insert(
                    "decision_expires_at_utc_audit_only".into(),
                    Value::String("2026-07-16T23:59:59Z".into()),
                );
            }),
        ] {
            let mut mutated_expected = expected.clone();
            mutated_expected.payload =
                serde_json::from_slice::<Value>(&mutated).unwrap()["payload"].clone();
            assert!(
                verify_unclaimed_owner_authorization_v1(&anchor, &mutated, &mutated_expected)
                    .is_err()
            );
        }
    }

    #[test]
    fn s18_lifecycle_claim_capability_and_retry_mutations_reject_even_when_resigned() {
        let (anchor, envelope, expected) = fixture();
        for mutated in [
            mutate_payload_and_resign(&envelope, |payload| {
                payload.insert("owned_lab_execution_authorized".into(), Value::Bool(true));
            }),
            mutate_payload_and_resign(&envelope, |payload| {
                payload.insert(
                    "single_use_execution_capability_issued".into(),
                    Value::Bool(true),
                );
            }),
            mutate_payload_and_resign(&envelope, |payload| {
                payload.insert("execution_start_permitted".into(), Value::Bool(true));
            }),
            mutate_payload_and_resign(&envelope, |payload| {
                payload.insert(
                    "cas_claim_receipt_sha256".into(),
                    Value::String(repeated(0x46)),
                );
            }),
            mutate_payload_and_resign(&envelope, |payload| {
                payload.insert(
                    "claimed_run_id_sha256".into(),
                    Value::String(repeated(0x47)),
                );
            }),
            mutate_payload_and_resign(&envelope, |payload| {
                payload.insert(
                    "execution_capability_sha256".into(),
                    Value::String(repeated(0x48)),
                );
            }),
            mutate_payload_and_resign(&envelope, |payload| {
                payload.insert(
                    "post_run_cleanup_receipt_sha256".into(),
                    Value::String(repeated(0x49)),
                );
            }),
            mutate_payload_and_resign(&envelope, |payload| {
                payload.insert(
                    "post_run_custody_receipt_sha256".into(),
                    Value::String(repeated(0x4a)),
                );
            }),
            mutate_payload_and_resign(&envelope, |payload| {
                payload.insert("retry_or_implicit_rerun_allowed".into(), Value::Bool(true));
            }),
            mutate_payload_and_resign(&envelope, |payload| {
                payload.insert("stop_state_at_signing_audit_only".into(), Value::Bool(true));
            }),
            mutate_payload_and_resign(&envelope, |payload| {
                payload.insert(
                    "use_time_external_absorbing_stop_check_required".into(),
                    Value::Bool(false),
                );
            }),
            mutate_payload_and_resign(&envelope, |payload| {
                payload.insert(
                    "use_time_current_revocation_epoch_check_required".into(),
                    Value::Bool(false),
                );
            }),
        ] {
            let mut mutated_expected = expected.clone();
            mutated_expected.payload =
                serde_json::from_slice::<Value>(&mutated).unwrap()["payload"].clone();
            assert!(
                verify_unclaimed_owner_authorization_v1(&anchor, &mutated, &mutated_expected)
                    .is_err()
            );
        }
    }

    #[test]
    fn s18_revoked_epoch_wrong_owner_and_wrong_domain_reject() {
        let (anchor, envelope, expected) = fixture();
        let stale = mutate_payload_and_resign(&envelope, |payload| {
            payload.insert("revocation_epoch".into(), Value::from(6));
        });
        let mut stale_expected = expected.clone();
        stale_expected.payload =
            serde_json::from_slice::<Value>(&stale).unwrap()["payload"].clone();
        assert!(verify_unclaimed_owner_authorization_v1(&anchor, &stale, &stale_expected).is_err());
        let wrong_owner = mutate_payload_and_resign(&envelope, |payload| {
            payload.insert("owner_key_id".into(), Value::String("other-owner".into()));
        });
        let mut wrong_owner_expected = expected.clone();
        wrong_owner_expected.payload =
            serde_json::from_slice::<Value>(&wrong_owner).unwrap()["payload"].clone();
        assert_eq!(
            verify_unclaimed_owner_authorization_v1(&anchor, &wrong_owner, &wrong_owner_expected,)
                .unwrap_err()
                .code(),
            "s18_owner_binding"
        );
        let mut wrong_domain: Value = serde_json::from_slice(&envelope).unwrap();
        wrong_domain["authentication"]["signature_message_domain"] =
            Value::String("other-domain".into());
        assert!(verify_unclaimed_owner_authorization_v1(
            &anchor,
            &canonical(&wrong_domain),
            &expected
        )
        .is_err());
    }

    #[test]
    fn s18_canonical_whitespace_duplicate_float_negative_and_nonascii_reject() {
        let (anchor, mut envelope, expected) = fixture();
        envelope.push(b'\n');
        assert_eq!(
            verify_unclaimed_owner_authorization_v1(&anchor, &envelope, &expected)
                .unwrap_err()
                .code(),
            "s18_canonical_bytes"
        );
        for raw in [
            br#"{"a":1,"a":1}"#.as_slice(),
            br#"{"b":1,"a":2}"#.as_slice(),
            br#"{"a":1.5}"#.as_slice(),
            br#"{"a":-1}"#.as_slice(),
            br#"{"a":18446744073709551616}"#.as_slice(),
            "{\"a\":\"λ\"}".as_bytes(),
            "{\"λ\":1}".as_bytes(),
        ] {
            assert!(parse_restricted_canonical(raw).is_err());
        }
        assert!(parse_restricted_canonical(br#"{"a":18446744073709551615}"#).is_ok());
    }

    #[test]
    fn s18_canonical_unknown_missing_depth_and_size_reject() {
        let (anchor, envelope, expected) = fixture();
        let mut unknown: Value = serde_json::from_slice(&envelope).unwrap();
        unknown["unexpected"] = Value::Bool(false);
        assert!(
            verify_unclaimed_owner_authorization_v1(&anchor, &canonical(&unknown), &expected)
                .is_err()
        );
        let mut missing: Value = serde_json::from_slice(&envelope).unwrap();
        missing.as_object_mut().unwrap().remove("authentication");
        assert!(
            verify_unclaimed_owner_authorization_v1(&anchor, &canonical(&missing), &expected)
                .is_err()
        );
        let mut accepted_depth = Value::Null;
        for _ in 0..16 {
            accepted_depth = Value::Array(vec![accepted_depth]);
        }
        assert!(parse_restricted_canonical(&serde_json::to_vec(&accepted_depth).unwrap()).is_ok());
        let rejected_depth = Value::Array(vec![accepted_depth]);
        assert!(parse_restricted_canonical(&serde_json::to_vec(&rejected_depth).unwrap()).is_err());
        let exact_size = serde_json::json!({"a": "a".repeat(MAX_DOCUMENT_BYTES - 8)});
        let exact_size_raw = serde_json::to_vec(&exact_size).unwrap();
        assert_eq!(exact_size_raw.len(), MAX_DOCUMENT_BYTES);
        assert!(parse_restricted_canonical(&exact_size_raw).is_ok());
        let oversized = serde_json::json!({"a": "a".repeat(MAX_DOCUMENT_BYTES - 7)});
        let oversized_raw = serde_json::to_vec(&oversized).unwrap();
        assert_eq!(oversized_raw.len(), MAX_DOCUMENT_BYTES + 1);
        assert!(parse_restricted_canonical(&oversized_raw).is_err());
        let oversized_anchor = vec![b'a'; MAX_DOCUMENT_BYTES + 1];
        assert_eq!(
            parse_anchor(&oversized_anchor, &sha256_bytes(&oversized_anchor))
                .unwrap_err()
                .code(),
            "s18_canonical_size"
        );

        let unknown_payload_raw = mutate_payload_and_resign(&envelope, |payload| {
            payload.insert("unexpected".into(), Value::Bool(false));
        });
        let mut unknown_payload_expected = expected.clone();
        unknown_payload_expected.payload =
            serde_json::from_slice::<Value>(&unknown_payload_raw).unwrap()["payload"].clone();
        assert_eq!(
            verify_unclaimed_owner_authorization_v1(
                &anchor,
                &unknown_payload_raw,
                &unknown_payload_expected,
            )
            .unwrap_err()
            .code(),
            "s18_payload_keys"
        );
        let mut unknown_authentication: Value = serde_json::from_slice(&envelope).unwrap();
        unknown_authentication["authentication"]["unexpected"] = Value::Bool(false);
        assert_eq!(
            verify_unclaimed_owner_authorization_v1(
                &anchor,
                &canonical(&unknown_authentication),
                &expected,
            )
            .unwrap_err()
            .code(),
            "s18_authentication_keys"
        );
        let mut unknown_anchor = anchor_value();
        unknown_anchor["unexpected"] = Value::Bool(false);
        let unknown_anchor = canonical(&unknown_anchor);
        let unknown_anchor_sha256 = sha256_bytes(&unknown_anchor);
        let mut unknown_anchor_payload = expected.payload.clone();
        unknown_anchor_payload["trust_anchor_document_sha256"] =
            Value::String(hex(&unknown_anchor_sha256));
        let unknown_anchor_payload_object = unknown_anchor_payload.as_object_mut().unwrap();
        let unknown_anchor_authorization_id =
            authorization_id(unknown_anchor_payload_object).unwrap();
        unknown_anchor_payload_object.insert(
            "authorization_id_sha256".into(),
            Value::String(hex(&unknown_anchor_authorization_id)),
        );
        let unknown_anchor_envelope =
            canonical(&resign(unknown_anchor_payload.clone(), &key_pair()));
        let unknown_anchor_expected = ExpectedOwnedLabAuthorizationBindingV1 {
            trust_anchor_document_sha256: unknown_anchor_sha256,
            payload: unknown_anchor_payload,
        };
        assert_eq!(
            verify_unclaimed_owner_authorization_v1(
                &unknown_anchor,
                &unknown_anchor_envelope,
                &unknown_anchor_expected,
            )
            .unwrap_err()
            .code(),
            "s18_anchor_keys"
        );
    }

    #[test]
    fn s18_v0_pending_and_claimed_states_reject() {
        let (anchor, envelope, expected) = fixture();
        for state in [
            "PENDING_AUTHENTICATED_OWNER_RESOURCE_BINDING",
            "CONSUMED_FOR_EXACT_RUN",
        ] {
            let mutated = mutate_payload_and_resign(&envelope, |payload| {
                payload.insert("decision_state".into(), Value::String(state.into()));
            });
            let mut mutated_expected = expected.clone();
            mutated_expected.payload =
                serde_json::from_slice::<Value>(&mutated).unwrap()["payload"].clone();
            assert!(
                verify_unclaimed_owner_authorization_v1(&anchor, &mutated, &mutated_expected)
                    .is_err()
            );
        }
    }

    #[test]
    fn s18_verified_output_is_redacted_and_contains_no_serializable_capability() {
        let (anchor, envelope, expected) = fixture();
        let verified =
            verify_unclaimed_owner_authorization_v1(&anchor, &envelope, &expected).unwrap();
        let debug = format!("{verified:?}");
        assert!(debug.contains("AUTHENTICATED_UNCLAIMED_NOT_CAPABILITY"));
        assert!(!debug.contains("rfc8032-test-only-owner"));
        assert!(!debug.contains(&hex(&RFC8032_TEST_ONLY_PUBLIC_KEY)));
    }
}
