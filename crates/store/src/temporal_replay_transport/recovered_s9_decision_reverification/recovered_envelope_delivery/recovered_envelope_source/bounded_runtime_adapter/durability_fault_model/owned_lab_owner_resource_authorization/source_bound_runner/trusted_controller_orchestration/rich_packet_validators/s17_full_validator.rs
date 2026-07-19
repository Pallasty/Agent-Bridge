//! Full S17 raw-observation validator used by the S20B post-run gate.
//!
//! The classifier in this module never receives an assignment label.  It
//! decodes an independently retained raw lifecycle frame, derives the virtual
//! S16 projection, and linearly compares that projection with every one of the
//! 5,639 frozen S16 rows.  Owner-authorized assignment labels are consulted
//! only after the scan has produced an explicit zero/one/multiple result.

#![cfg_attr(not(test), allow(dead_code))]

use super::assignment_authority::{
    ValidatedAuthorizedAssignmentMemberV1, ValidatedAuthorizedAssignmentSetV1,
};
use super::*;
use serde_json::{json, Map, Value};
use sha2::{Digest, Sha256};
use std::collections::BTreeSet;

type FrozenS16RowV1 = super::super::super::super::super::ModeledFaultRowV1;

const S17_OBSERVATION_SCHEMA: &str =
    "agent_bridge.memory_temporal_recovered_envelope_owned_lab_process_crash_restart_observation_s17.v0";
const S17_PACKET_KIND: &str = "AUTHENTICATED_OWNED_LAB_RUNTIME_OBSERVATION";
const S17_CLASSIFICATION_DOMAIN: &[u8] = b"agent_bridge.s17.owned_lab.classification_input.v0";
const S17_PHASE_DOMAIN: &[u8] = b"agent_bridge.s17.owned_lab.mapping_phase_record.v0";
const S17_OBSERVATION_DOMAIN: &[u8] = b"agent_bridge.s17.owned_lab.observation.v0";
const S17_PHASE_SET_DOMAIN: &[u8] =
    b"agent-bridge/biocortex/owned-lab/s20b/validated-s17-phase-set/v1";
const S17_OBSERVATION_SET_DOMAIN: &[u8] =
    b"agent-bridge/biocortex/owned-lab/s20b/validated-s17-observation-set/v1";

const S17_OBSERVATION_SCHEMA_RAW_SHA256: [u8; 32] = [
    0x26, 0xa8, 0xcc, 0xa9, 0xf9, 0xca, 0x74, 0xce, 0xb4, 0xb9, 0x49, 0xa2, 0xe7, 0x5d, 0x92, 0x82,
    0xa6, 0x22, 0x76, 0x23, 0xf5, 0xbd, 0x66, 0xcc, 0x33, 0x3f, 0xbf, 0xf7, 0x44, 0x15, 0x88, 0x8d,
];
const S17_PLAN_RAW_SHA256: [u8; 32] = [
    0xca, 0x97, 0x69, 0xff, 0x2b, 0x79, 0xe4, 0x74, 0x99, 0x9d, 0xf6, 0xbb, 0x50, 0x96, 0xa3, 0xe0,
    0x62, 0xb5, 0xac, 0xf7, 0x8f, 0xa2, 0x37, 0x88, 0xf7, 0x6a, 0xe4, 0x42, 0x95, 0x53, 0x16, 0x50,
];
const S16_CATALOG_MESSAGE_LEN: u64 = 225_852;
const S16_BASE_RECORD_LEN: u64 = 5_494;
const S16_READ_QUANTUM: u64 = 113;
const S16_DATA_STEPS: u64 = 49;

const TOP_LEVEL_KEYS: [&str; 19] = [
    "schema",
    "packet_kind",
    "evidence_origin",
    "claim_level",
    "claim_ceiling",
    "hashing_contract",
    "semantic_validation_contract",
    "identity",
    "frozen_bindings",
    "assignment",
    "authorization",
    "storage_environment",
    "crash_observation",
    "restart_observation",
    "raw_recovered_state",
    "mapping_phase_records",
    "custody",
    "accounting",
    "nonclaims",
];

const RAW_LIFECYCLE_KEYS: [&str; 23] = [
    "publisher_phase",
    "object_state",
    "object_len",
    "object_sha256",
    "receipt_state",
    "computed_receipt_sha256",
    "stored_receipt_sha256",
    "witness_state",
    "computed_witness_sha256",
    "stored_witness_sha256",
    "selected_view_state",
    "selected_view_sha256",
    "competing_view_state",
    "competing_view_sha256",
    "ack_state",
    "ack_receipt_sha256",
    "ack_witness_sha256",
    "crash_cut",
    "crash_cut_index",
    "restarted_after_crash",
    "observed_data_steps",
    "observed_len",
    "adapter_pre_state",
    // adapter_post_state is checked separately below; keep the declaration
    // explicit instead of accepting a caller-created map.
];

const RAW_MEASUREMENT_KEYS: [&str; 29] = [
    "retained_raw_event_stream_sha256",
    "raw_event_frame_index",
    "raw_event_frame_offset_bytes",
    "raw_event_frame_length_bytes",
    "raw_event_frame_sha256",
    "measurement_decode_status",
    "publisher_phase",
    "object_state",
    "object_len",
    "object_sha256",
    "receipt_state",
    "computed_receipt_sha256",
    "stored_receipt_sha256",
    "witness_state",
    "computed_witness_sha256",
    "stored_witness_sha256",
    "selected_view_state",
    "selected_view_sha256",
    "competing_view_state",
    "competing_view_sha256",
    "ack_state",
    "ack_receipt_sha256",
    "ack_witness_sha256",
    "crash_cut",
    "crash_cut_index",
    "restarted_after_crash",
    "observed_data_steps",
    "observed_len",
    "adapter_pre_state",
    // adapter_post_state is appended by exact_raw_measurement_keys_v1().
];

fn validator_error(code: &'static str, detail: &'static str) -> OwnedLabAuthorizationError {
    s20b_error(code, detail)
}

fn checked_object<'a>(
    value: &'a Value,
    keys: &[&str],
    code: &'static str,
) -> AuthorizationResult<&'a Map<String, Value>> {
    let object = value.as_object().ok_or_else(|| {
        validator_error(
            code,
            "S17 value is not the required closed canonical object",
        )
    })?;
    let actual: BTreeSet<&str> = object.keys().map(String::as_str).collect();
    let expected: BTreeSet<&str> = keys.iter().copied().collect();
    if actual != expected {
        return Err(validator_error(
            code,
            "S17 closed object has a missing or additional field",
        ));
    }
    Ok(object)
}

fn field<'a>(
    object: &'a Map<String, Value>,
    key: &str,
    code: &'static str,
) -> AuthorizationResult<&'a Value> {
    object
        .get(key)
        .ok_or_else(|| validator_error(code, "S17 required field is absent"))
}

fn text_field<'a>(
    object: &'a Map<String, Value>,
    key: &str,
    code: &'static str,
) -> AuthorizationResult<&'a str> {
    field(object, key, code)?
        .as_str()
        .ok_or_else(|| validator_error(code, "S17 field is not a string"))
}

fn u64_field(
    object: &Map<String, Value>,
    key: &str,
    code: &'static str,
) -> AuthorizationResult<u64> {
    field(object, key, code)?
        .as_u64()
        .ok_or_else(|| validator_error(code, "S17 field is not a nonnegative u64"))
}

fn bool_field(
    object: &Map<String, Value>,
    key: &str,
    code: &'static str,
) -> AuthorizationResult<bool> {
    field(object, key, code)?
        .as_bool()
        .ok_or_else(|| validator_error(code, "S17 field is not a boolean"))
}

fn digest_field(
    object: &Map<String, Value>,
    key: &str,
    code: &'static str,
) -> AuthorizationResult<[u8; 32]> {
    let digest = decode_hex_fixed::<32>(text_field(object, key, code)?)?;
    if !nonzero(&digest) {
        return Err(validator_error(code, "S17 digest is the all-zero value"));
    }
    Ok(digest)
}

fn nullable_digest_field(
    object: &Map<String, Value>,
    key: &str,
    code: &'static str,
) -> AuthorizationResult<Option<[u8; 32]>> {
    match field(object, key, code)? {
        Value::Null => Ok(None),
        Value::String(value) => {
            let digest = decode_hex_fixed::<32>(value)?;
            if !nonzero(&digest) {
                return Err(validator_error(code, "S17 digest is the all-zero value"));
            }
            Ok(Some(digest))
        }
        _ => Err(validator_error(
            code,
            "S17 nullable digest is neither null nor a digest string",
        )),
    }
}

fn nullable_u64_field(
    object: &Map<String, Value>,
    key: &str,
    code: &'static str,
) -> AuthorizationResult<Option<u64>> {
    match field(object, key, code)? {
        Value::Null => Ok(None),
        Value::Number(value) => value
            .as_u64()
            .map(Some)
            .ok_or_else(|| validator_error(code, "S17 nullable integer is invalid")),
        _ => Err(validator_error(
            code,
            "S17 nullable integer is neither null nor an integer",
        )),
    }
}

fn start_ticks_field(
    object: &Map<String, Value>,
    key: &str,
    code: &'static str,
) -> AuthorizationResult<u64> {
    let text = text_field(object, key, code)?;
    if text.starts_with('0') || text.len() > 32 || !text.bytes().all(|byte| byte.is_ascii_digit()) {
        return Err(validator_error(
            code,
            "S17 process start identity is invalid",
        ));
    }
    text.parse::<u64>()
        .ok()
        .filter(|value| *value > 0)
        .ok_or_else(|| validator_error(code, "S17 process start identity is out of range"))
}

fn nullable_start_ticks_field(
    object: &Map<String, Value>,
    key: &str,
    code: &'static str,
) -> AuthorizationResult<Option<u64>> {
    if field(object, key, code)?.is_null() {
        Ok(None)
    } else {
        start_ticks_field(object, key, code).map(Some)
    }
}

fn require_text(
    object: &Map<String, Value>,
    key: &str,
    expected: &str,
    code: &'static str,
) -> AuthorizationResult<()> {
    if text_field(object, key, code)? != expected {
        return Err(validator_error(code, "S17 frozen string constant drifted"));
    }
    Ok(())
}

fn require_bool(
    object: &Map<String, Value>,
    key: &str,
    expected: bool,
    code: &'static str,
) -> AuthorizationResult<()> {
    if bool_field(object, key, code)? != expected {
        return Err(validator_error(code, "S17 frozen boolean constant drifted"));
    }
    Ok(())
}

fn require_u64(
    object: &Map<String, Value>,
    key: &str,
    expected: u64,
    code: &'static str,
) -> AuthorizationResult<()> {
    if u64_field(object, key, code)? != expected {
        return Err(validator_error(code, "S17 frozen integer constant drifted"));
    }
    Ok(())
}

fn jcs_domain_digest_v1(domain: &[u8], value: &Value) -> AuthorizationResult<[u8; 32]> {
    let encoded = restricted_canonical_bytes(value)?;
    let mut hasher = Sha256::new();
    hasher.update(domain);
    hasher.update([0]);
    hasher.update(encoded);
    Ok(hasher.finalize().into())
}

fn plain_jcs_digest_v1(value: &Value) -> AuthorizationResult<[u8; 32]> {
    Ok(Sha256::digest(restricted_canonical_bytes(value)?).into())
}

fn observation_id_v1(
    run_id_sha256: &[u8; 32],
    assignment_id_sha256: &[u8; 32],
    canonical_payload_sha256: &[u8; 32],
) -> [u8; 32] {
    let mut hasher = Sha256::new();
    hasher.update(S17_OBSERVATION_DOMAIN);
    hasher.update([0]);
    hasher.update(run_id_sha256);
    hasher.update(assignment_id_sha256);
    hasher.update(canonical_payload_sha256);
    hasher.finalize().into()
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
enum ParsedPhaseKindV1 {
    AttemptResult,
    FirstAttempt,
    Restart,
}

impl ParsedPhaseKindV1 {
    fn parse(value: &str) -> AuthorizationResult<Self> {
        match value {
            "ATTEMPT_RESULT" => Ok(Self::AttemptResult),
            "FIRST_ATTEMPT" => Ok(Self::FirstAttempt),
            "RESTART" => Ok(Self::Restart),
            _ => Err(validator_error(
                "s20b_s17_phase_kind",
                "S17 phase kind is outside the frozen lifecycle",
            )),
        }
    }

    fn as_str(self) -> &'static str {
        match self {
            Self::AttemptResult => "ATTEMPT_RESULT",
            Self::FirstAttempt => "FIRST_ATTEMPT",
            Self::Restart => "RESTART",
        }
    }
}

#[derive(Clone, Debug, Eq, PartialEq)]
struct RawLifecycleFrameV1 {
    publisher_phase: String,
    object_state: String,
    object_len: u64,
    object_sha256: Option<[u8; 32]>,
    receipt_state: String,
    computed_receipt_sha256: Option<[u8; 32]>,
    stored_receipt_sha256: Option<[u8; 32]>,
    witness_state: String,
    computed_witness_sha256: Option<[u8; 32]>,
    stored_witness_sha256: Option<[u8; 32]>,
    selected_view_state: String,
    selected_view_sha256: Option<[u8; 32]>,
    competing_view_state: String,
    competing_view_sha256: Option<[u8; 32]>,
    ack_state: String,
    ack_receipt_sha256: Option<[u8; 32]>,
    ack_witness_sha256: Option<[u8; 32]>,
    crash_cut: String,
    crash_cut_index: u64,
    restarted_after_crash: bool,
    observed_data_steps: u64,
    observed_len: u64,
    adapter_pre_state: String,
    adapter_post_state: String,
}

fn raw_lifecycle_keys_v1() -> Vec<&'static str> {
    let mut keys = RAW_LIFECYCLE_KEYS.to_vec();
    keys.push("adapter_post_state");
    keys
}

fn raw_measurement_keys_v1() -> Vec<&'static str> {
    let mut keys = RAW_MEASUREMENT_KEYS.to_vec();
    keys.push("adapter_post_state");
    keys
}

fn parse_raw_lifecycle_v1(value: &Value) -> AuthorizationResult<RawLifecycleFrameV1> {
    let keys = raw_lifecycle_keys_v1();
    let object = checked_object(value, &keys, "s20b_s17_raw_lifecycle")?;
    let parsed = RawLifecycleFrameV1 {
        publisher_phase: text_field(object, "publisher_phase", "s20b_s17_raw_lifecycle")?.into(),
        object_state: text_field(object, "object_state", "s20b_s17_raw_lifecycle")?.into(),
        object_len: u64_field(object, "object_len", "s20b_s17_raw_lifecycle")?,
        object_sha256: nullable_digest_field(object, "object_sha256", "s20b_s17_raw_lifecycle")?,
        receipt_state: text_field(object, "receipt_state", "s20b_s17_raw_lifecycle")?.into(),
        computed_receipt_sha256: nullable_digest_field(
            object,
            "computed_receipt_sha256",
            "s20b_s17_raw_lifecycle",
        )?,
        stored_receipt_sha256: nullable_digest_field(
            object,
            "stored_receipt_sha256",
            "s20b_s17_raw_lifecycle",
        )?,
        witness_state: text_field(object, "witness_state", "s20b_s17_raw_lifecycle")?.into(),
        computed_witness_sha256: nullable_digest_field(
            object,
            "computed_witness_sha256",
            "s20b_s17_raw_lifecycle",
        )?,
        stored_witness_sha256: nullable_digest_field(
            object,
            "stored_witness_sha256",
            "s20b_s17_raw_lifecycle",
        )?,
        selected_view_state: text_field(object, "selected_view_state", "s20b_s17_raw_lifecycle")?
            .into(),
        selected_view_sha256: nullable_digest_field(
            object,
            "selected_view_sha256",
            "s20b_s17_raw_lifecycle",
        )?,
        competing_view_state: text_field(object, "competing_view_state", "s20b_s17_raw_lifecycle")?
            .into(),
        competing_view_sha256: nullable_digest_field(
            object,
            "competing_view_sha256",
            "s20b_s17_raw_lifecycle",
        )?,
        ack_state: text_field(object, "ack_state", "s20b_s17_raw_lifecycle")?.into(),
        ack_receipt_sha256: nullable_digest_field(
            object,
            "ack_receipt_sha256",
            "s20b_s17_raw_lifecycle",
        )?,
        ack_witness_sha256: nullable_digest_field(
            object,
            "ack_witness_sha256",
            "s20b_s17_raw_lifecycle",
        )?,
        crash_cut: text_field(object, "crash_cut", "s20b_s17_raw_lifecycle")?.into(),
        crash_cut_index: u64_field(object, "crash_cut_index", "s20b_s17_raw_lifecycle")?,
        restarted_after_crash: bool_field(
            object,
            "restarted_after_crash",
            "s20b_s17_raw_lifecycle",
        )?,
        observed_data_steps: u64_field(object, "observed_data_steps", "s20b_s17_raw_lifecycle")?,
        observed_len: u64_field(object, "observed_len", "s20b_s17_raw_lifecycle")?,
        adapter_pre_state: text_field(object, "adapter_pre_state", "s20b_s17_raw_lifecycle")?
            .into(),
        adapter_post_state: text_field(object, "adapter_post_state", "s20b_s17_raw_lifecycle")?
            .into(),
    };
    validate_raw_state_shape_v1(&parsed)?;
    Ok(parsed)
}

fn validate_raw_state_shape_v1(raw: &RawLifecycleFrameV1) -> AuthorizationResult<()> {
    let allowed = |value: &str, values: &[&str]| values.contains(&value);
    let object_valid = match raw.object_state.as_str() {
        "ABSENT" => raw.object_len == 0 && raw.object_sha256.is_none(),
        "PARTIAL" | "COMMITTED" => {
            (1..=278_528).contains(&raw.object_len) && raw.object_sha256.is_some()
        }
        _ => false,
    };
    let receipt_valid = match raw.receipt_state.as_str() {
        "ABSENT" => raw.computed_receipt_sha256.is_none() && raw.stored_receipt_sha256.is_none(),
        "COMMITTED" => raw.computed_receipt_sha256.is_some() && raw.stored_receipt_sha256.is_some(),
        _ => false,
    };
    let witness_valid = match raw.witness_state.as_str() {
        "ABSENT" => raw.computed_witness_sha256.is_none() && raw.stored_witness_sha256.is_none(),
        "PRESENT" => raw.computed_witness_sha256.is_some() && raw.stored_witness_sha256.is_some(),
        _ => false,
    };
    let selected_valid = match raw.selected_view_state.as_str() {
        "ABSENT" => raw.selected_view_sha256.is_none(),
        "PRESENT" => raw.selected_view_sha256.is_some(),
        _ => false,
    };
    let competing_valid = match raw.competing_view_state.as_str() {
        "ABSENT" => raw.competing_view_sha256.is_none(),
        "PRESENT" => raw.competing_view_sha256.is_some(),
        _ => false,
    };
    let ack_valid = match raw.ack_state.as_str() {
        "NOT_OBSERVED" => raw.ack_receipt_sha256.is_none() && raw.ack_witness_sha256.is_none(),
        "OBSERVED" => raw.ack_receipt_sha256.is_some() && raw.ack_witness_sha256.is_some(),
        _ => false,
    };
    if !object_valid
        || !receipt_valid
        || !witness_valid
        || !selected_valid
        || !competing_valid
        || !ack_valid
        || !allowed(
            &raw.publisher_phase,
            &[
                "EMPTY",
                "OBJECT_PREFIX",
                "OBJECT_COMMITTED",
                "RECEIPT_COMMITTED",
                "WITNESS_COMMITTED",
                "ACKED",
            ],
        )
        || !allowed(
            &raw.crash_cut,
            &[
                "NONE",
                "PUBLISH_AFTER_OBJECT_PREFIX",
                "PUBLISH_AFTER_OBJECT_COMMIT",
                "PUBLISH_AFTER_RECEIPT_COMMIT",
                "PUBLISH_AFTER_WITNESS_COMMIT",
                "PUBLISH_AFTER_ACK",
                "READ_BEFORE_OPEN",
                "READ_AFTER_OPEN",
                "READ_AFTER_DATA",
                "READ_AFTER_COMPLETE_BEFORE_S14",
                "READ_AFTER_HISTORICAL",
            ],
        )
        || !allowed(&raw.adapter_pre_state, &["FRESH", "STREAMING", "COMPLETED"])
        || !allowed(
            &raw.adapter_post_state,
            &["FRESH", "TERMINAL_FAILED", "COMPLETED"],
        )
        || raw.crash_cut_index > 5_493
        || raw.observed_data_steps > S16_DATA_STEPS
        || raw.observed_len > S16_BASE_RECORD_LEN
    {
        return Err(validator_error(
            "s20b_s17_raw_lifecycle",
            "decoded raw lifecycle facts violate the frozen typed shape",
        ));
    }
    Ok(())
}

fn raw_lifecycle_value_v1(raw: &RawLifecycleFrameV1) -> Value {
    let optional = |digest: Option<[u8; 32]>| {
        digest
            .map(|value| Value::String(hex32(&value)))
            .unwrap_or(Value::Null)
    };
    json!({
        "ack_receipt_sha256": optional(raw.ack_receipt_sha256),
        "ack_state": raw.ack_state,
        "ack_witness_sha256": optional(raw.ack_witness_sha256),
        "adapter_post_state": raw.adapter_post_state,
        "adapter_pre_state": raw.adapter_pre_state,
        "competing_view_sha256": optional(raw.competing_view_sha256),
        "competing_view_state": raw.competing_view_state,
        "computed_receipt_sha256": optional(raw.computed_receipt_sha256),
        "computed_witness_sha256": optional(raw.computed_witness_sha256),
        "crash_cut": raw.crash_cut,
        "crash_cut_index": raw.crash_cut_index,
        "object_len": raw.object_len,
        "object_sha256": optional(raw.object_sha256),
        "object_state": raw.object_state,
        "observed_data_steps": raw.observed_data_steps,
        "observed_len": raw.observed_len,
        "publisher_phase": raw.publisher_phase,
        "receipt_state": raw.receipt_state,
        "restarted_after_crash": raw.restarted_after_crash,
        "selected_view_sha256": optional(raw.selected_view_sha256),
        "selected_view_state": raw.selected_view_state,
        "stored_receipt_sha256": optional(raw.stored_receipt_sha256),
        "stored_witness_sha256": optional(raw.stored_witness_sha256),
        "witness_state": raw.witness_state
    })
}

#[derive(Clone, Debug, Eq, PartialEq)]
struct S16ProjectionV1 {
    publisher_phase: String,
    object_persistence: String,
    object_len: u64,
    observed_object_sha256: [u8; 32],
    receipt_state: String,
    computed_receipt_sha256: [u8; 32],
    stored_receipt_sha256: [u8; 32],
    witness_state: String,
    computed_witness_sha256: [u8; 32],
    stored_witness_sha256: [u8; 32],
    selected_view_sha256: [u8; 32],
    competing_view_sha256: [u8; 32],
    ack_state: String,
    crash_cut: String,
    crash_cut_index: u64,
    adapter_pre_state: String,
    adapter_post_state: String,
    restarted_after_crash: bool,
    observed_data_steps: u64,
    observed_len: u64,
    ack_receipt_sha256: Option<[u8; 32]>,
    ack_witness_sha256: Option<[u8; 32]>,
    external_durability_observation_count: u64,
    provider_durability_observation_count: u64,
    owned_lab_durability_observation_count: u64,
    side_effects_unlocked: String,
}

fn absent_sentinels_v1() -> [[u8; 32]; 4] {
    [
        super::super::super::super::super::absent_commitment_v1(b"OBJECT"),
        super::super::super::super::super::absent_commitment_v1(b"RECEIPT"),
        super::super::super::super::super::absent_commitment_v1(b"WITNESS"),
        super::super::super::super::super::absent_commitment_v1(b"REPLICA_VIEW"),
    ]
}

fn derive_projection_v1(raw: &RawLifecycleFrameV1) -> S16ProjectionV1 {
    let [absent_object, absent_receipt, absent_witness, absent_view] = absent_sentinels_v1();
    S16ProjectionV1 {
        publisher_phase: raw.publisher_phase.clone(),
        object_persistence: raw.object_state.clone(),
        object_len: raw.object_len,
        observed_object_sha256: raw.object_sha256.unwrap_or(absent_object),
        receipt_state: raw.receipt_state.clone(),
        computed_receipt_sha256: raw.computed_receipt_sha256.unwrap_or(absent_receipt),
        stored_receipt_sha256: raw.stored_receipt_sha256.unwrap_or(absent_receipt),
        witness_state: raw.witness_state.clone(),
        computed_witness_sha256: raw.computed_witness_sha256.unwrap_or(absent_witness),
        stored_witness_sha256: raw.stored_witness_sha256.unwrap_or(absent_witness),
        selected_view_sha256: raw.selected_view_sha256.unwrap_or(absent_view),
        competing_view_sha256: raw.competing_view_sha256.unwrap_or(absent_view),
        ack_state: raw.ack_state.clone(),
        crash_cut: raw.crash_cut.clone(),
        crash_cut_index: raw.crash_cut_index,
        adapter_pre_state: raw.adapter_pre_state.clone(),
        adapter_post_state: raw.adapter_post_state.clone(),
        restarted_after_crash: raw.restarted_after_crash,
        observed_data_steps: raw.observed_data_steps,
        observed_len: raw.observed_len,
        ack_receipt_sha256: raw.ack_receipt_sha256,
        ack_witness_sha256: raw.ack_witness_sha256,
        external_durability_observation_count: 0,
        provider_durability_observation_count: 0,
        owned_lab_durability_observation_count: 0,
        side_effects_unlocked: "NONE".into(),
    }
}

fn projection_keys_v1() -> [&'static str; 27] {
    [
        "projection_kind",
        "publisher_phase",
        "object_persistence",
        "object_len",
        "observed_object_sha256",
        "receipt_state",
        "computed_receipt_sha256",
        "stored_receipt_sha256",
        "witness_state",
        "computed_witness_sha256",
        "stored_witness_sha256",
        "selected_view_sha256",
        "competing_view_sha256",
        "ack_state",
        "crash_cut",
        "crash_cut_index",
        "adapter_pre_state",
        "adapter_post_state",
        "restarted_after_crash",
        "observed_data_steps",
        "observed_len",
        "ack_receipt_sha256",
        "ack_witness_sha256",
        "external_durability_observation_count",
        "provider_durability_observation_count",
        "owned_lab_durability_observation_count",
        "side_effects_unlocked",
    ]
}

fn parse_projection_v1(value: &Value) -> AuthorizationResult<S16ProjectionV1> {
    let object = checked_object(value, &projection_keys_v1(), "s20b_s17_projection")?;
    require_text(
        object,
        "projection_kind",
        "FROZEN_S16_EVALUATOR_INPUT_V0",
        "s20b_s17_projection",
    )?;
    let projection = S16ProjectionV1 {
        publisher_phase: text_field(object, "publisher_phase", "s20b_s17_projection")?.into(),
        object_persistence: text_field(object, "object_persistence", "s20b_s17_projection")?.into(),
        object_len: u64_field(object, "object_len", "s20b_s17_projection")?,
        observed_object_sha256: digest_field(
            object,
            "observed_object_sha256",
            "s20b_s17_projection",
        )?,
        receipt_state: text_field(object, "receipt_state", "s20b_s17_projection")?.into(),
        computed_receipt_sha256: digest_field(
            object,
            "computed_receipt_sha256",
            "s20b_s17_projection",
        )?,
        stored_receipt_sha256: digest_field(
            object,
            "stored_receipt_sha256",
            "s20b_s17_projection",
        )?,
        witness_state: text_field(object, "witness_state", "s20b_s17_projection")?.into(),
        computed_witness_sha256: digest_field(
            object,
            "computed_witness_sha256",
            "s20b_s17_projection",
        )?,
        stored_witness_sha256: digest_field(
            object,
            "stored_witness_sha256",
            "s20b_s17_projection",
        )?,
        selected_view_sha256: digest_field(object, "selected_view_sha256", "s20b_s17_projection")?,
        competing_view_sha256: digest_field(
            object,
            "competing_view_sha256",
            "s20b_s17_projection",
        )?,
        ack_state: text_field(object, "ack_state", "s20b_s17_projection")?.into(),
        crash_cut: text_field(object, "crash_cut", "s20b_s17_projection")?.into(),
        crash_cut_index: u64_field(object, "crash_cut_index", "s20b_s17_projection")?,
        adapter_pre_state: text_field(object, "adapter_pre_state", "s20b_s17_projection")?.into(),
        adapter_post_state: text_field(object, "adapter_post_state", "s20b_s17_projection")?.into(),
        restarted_after_crash: bool_field(object, "restarted_after_crash", "s20b_s17_projection")?,
        observed_data_steps: u64_field(object, "observed_data_steps", "s20b_s17_projection")?,
        observed_len: u64_field(object, "observed_len", "s20b_s17_projection")?,
        ack_receipt_sha256: nullable_digest_field(
            object,
            "ack_receipt_sha256",
            "s20b_s17_projection",
        )?,
        ack_witness_sha256: nullable_digest_field(
            object,
            "ack_witness_sha256",
            "s20b_s17_projection",
        )?,
        external_durability_observation_count: u64_field(
            object,
            "external_durability_observation_count",
            "s20b_s17_projection",
        )?,
        provider_durability_observation_count: u64_field(
            object,
            "provider_durability_observation_count",
            "s20b_s17_projection",
        )?,
        owned_lab_durability_observation_count: u64_field(
            object,
            "owned_lab_durability_observation_count",
            "s20b_s17_projection",
        )?,
        side_effects_unlocked: text_field(object, "side_effects_unlocked", "s20b_s17_projection")?
            .into(),
    };
    Ok(projection)
}

fn projection_value_v1(projection: &S16ProjectionV1) -> Value {
    let optional = |digest: Option<[u8; 32]>| {
        digest
            .map(|value| Value::String(hex32(&value)))
            .unwrap_or(Value::Null)
    };
    json!({
        "ack_receipt_sha256": optional(projection.ack_receipt_sha256),
        "ack_state": projection.ack_state,
        "ack_witness_sha256": optional(projection.ack_witness_sha256),
        "adapter_post_state": projection.adapter_post_state,
        "adapter_pre_state": projection.adapter_pre_state,
        "competing_view_sha256": hex32(&projection.competing_view_sha256),
        "computed_receipt_sha256": hex32(&projection.computed_receipt_sha256),
        "computed_witness_sha256": hex32(&projection.computed_witness_sha256),
        "crash_cut": projection.crash_cut,
        "crash_cut_index": projection.crash_cut_index,
        "external_durability_observation_count": projection.external_durability_observation_count,
        "object_len": projection.object_len,
        "object_persistence": projection.object_persistence,
        "observed_data_steps": projection.observed_data_steps,
        "observed_len": projection.observed_len,
        "observed_object_sha256": hex32(&projection.observed_object_sha256),
        "owned_lab_durability_observation_count": projection.owned_lab_durability_observation_count,
        "projection_kind": "FROZEN_S16_EVALUATOR_INPUT_V0",
        "provider_durability_observation_count": projection.provider_durability_observation_count,
        "publisher_phase": projection.publisher_phase,
        "receipt_state": projection.receipt_state,
        "restarted_after_crash": projection.restarted_after_crash,
        "selected_view_sha256": hex32(&projection.selected_view_sha256),
        "side_effects_unlocked": projection.side_effects_unlocked,
        "stored_receipt_sha256": hex32(&projection.stored_receipt_sha256),
        "stored_witness_sha256": hex32(&projection.stored_witness_sha256),
        "witness_state": projection.witness_state
    })
}

fn raw_contains_absent_sentinel_v1(raw: &RawLifecycleFrameV1) -> bool {
    let sentinels: BTreeSet<[u8; 32]> = absent_sentinels_v1().into_iter().collect();
    [
        raw.object_sha256,
        raw.computed_receipt_sha256,
        raw.stored_receipt_sha256,
        raw.computed_witness_sha256,
        raw.stored_witness_sha256,
        raw.selected_view_sha256,
        raw.competing_view_sha256,
        raw.ack_receipt_sha256,
        raw.ack_witness_sha256,
    ]
    .into_iter()
    .flatten()
    .any(|digest| sentinels.contains(&digest))
}

fn row_matches_projection_v1(row: &FrozenS16RowV1, projection: &S16ProjectionV1) -> bool {
    row.publisher_phase.as_str() == projection.publisher_phase
        && row.object_persistence.as_str() == projection.object_persistence
        && row.object_len == projection.object_len
        && row.observed_object_sha256 == projection.observed_object_sha256
        && row.receipt_state == projection.receipt_state
        && row.computed_receipt_sha256 == projection.computed_receipt_sha256
        && row.stored_receipt_sha256 == projection.stored_receipt_sha256
        && row.witness_state == projection.witness_state
        && row.computed_witness_sha256 == projection.computed_witness_sha256
        && row.stored_witness_sha256 == projection.stored_witness_sha256
        && row.selected_view_sha256 == projection.selected_view_sha256
        && row.competing_view_sha256 == projection.competing_view_sha256
        && row.ack_state.as_str() == projection.ack_state
        && row.crash_cut.as_str() == projection.crash_cut
        && row.crash_cut_index == projection.crash_cut_index
        && row.adapter_pre_state.as_str() == projection.adapter_pre_state
        && row.adapter_post_state.as_str() == projection.adapter_post_state
        && lifecycle_for_row_v1(row)
            == (
                projection.restarted_after_crash,
                projection.observed_data_steps,
                projection.observed_len,
            )
}

fn lifecycle_for_row_v1(row: &FrozenS16RowV1) -> (bool, u64, u64) {
    if row.case_id != "D05_S15_READ_CRASH_RESTART_CUTS" {
        return (row.case_id == "D04_PUBLISH_CRASH_RESTART_CUTS", 0, 0);
    }
    if row.variant_id.ends_with("_RESTART") {
        return (true, S16_DATA_STEPS, S16_BASE_RECORD_LEN);
    }
    let steps = match row.crash_cut.as_str() {
        "READ_BEFORE_OPEN" | "READ_AFTER_OPEN" => 0,
        "READ_AFTER_DATA" => row.crash_cut_index,
        "READ_AFTER_COMPLETE_BEFORE_S14" | "READ_AFTER_HISTORICAL" => S16_DATA_STEPS,
        _ => u64::MAX,
    };
    (
        false,
        steps,
        (steps * S16_READ_QUANTUM).min(S16_BASE_RECORD_LEN),
    )
}

enum FullCatalogScanV1<'a> {
    Zero {
        scanned: usize,
    },
    One {
        scanned: usize,
        row: &'a FrozenS16RowV1,
    },
    Multiple {
        scanned: usize,
        multiplicity: usize,
    },
}

impl FullCatalogScanV1<'_> {
    fn scanned(&self) -> usize {
        match self {
            Self::Zero { scanned } | Self::One { scanned, .. } | Self::Multiple { scanned, .. } => {
                *scanned
            }
        }
    }
}

fn scan_full_catalog_v1<'a>(
    rows: &'a [FrozenS16RowV1],
    projection: &S16ProjectionV1,
) -> FullCatalogScanV1<'a> {
    // Deliberately linear and deliberately label-free.  Do not replace this
    // with a case/variant map: every classification must inspect all rows.
    let mut first = None;
    let mut multiplicity = 0_usize;
    let mut scanned = 0_usize;
    for row in rows {
        scanned += 1;
        if row_matches_projection_v1(row, projection) {
            multiplicity += 1;
            if first.is_none() {
                first = Some(row);
            }
        }
    }
    match (multiplicity, first) {
        (0, _) => FullCatalogScanV1::Zero { scanned },
        (1, Some(row)) => FullCatalogScanV1::One { scanned, row },
        (count, _) => FullCatalogScanV1::Multiple {
            scanned,
            multiplicity: count,
        },
    }
}

#[derive(Clone, Debug)]
struct ReportedClassificationV1 {
    classifier_build_sha256: [u8; 32],
    mapping_cardinality: u64,
    mapped_s16_case_id: Option<String>,
    mapped_s16_variant_id: Option<String>,
    mapped_s16_row_sha256: Option<[u8; 32]>,
    mapped_reason: String,
    mapped_failure: String,
    mapping_status: String,
}

fn classification_keys_v1() -> [&'static str; 10] {
    [
        "classifier_build_sha256",
        "classification_derived_from_raw_state",
        "planned_label_used_as_outcome_oracle",
        "mapping_cardinality",
        "mapped_s16_case_id",
        "mapped_s16_variant_id",
        "mapped_s16_row_sha256",
        "mapped_reason",
        "mapped_failure",
        "mapping_status",
    ]
}

fn nullable_text_field(
    object: &Map<String, Value>,
    key: &str,
    code: &'static str,
) -> AuthorizationResult<Option<String>> {
    match field(object, key, code)? {
        Value::Null => Ok(None),
        Value::String(value) if !value.is_empty() && value.is_ascii() => Ok(Some(value.clone())),
        _ => Err(validator_error(
            code,
            "S17 nullable text field is malformed",
        )),
    }
}

fn parse_reported_classification_v1(
    value: &Value,
) -> AuthorizationResult<ReportedClassificationV1> {
    let object = checked_object(value, &classification_keys_v1(), "s20b_s17_classification")?;
    require_bool(
        object,
        "classification_derived_from_raw_state",
        true,
        "s20b_s17_classification",
    )?;
    require_bool(
        object,
        "planned_label_used_as_outcome_oracle",
        false,
        "s20b_s17_classification",
    )?;
    let result = ReportedClassificationV1 {
        classifier_build_sha256: digest_field(
            object,
            "classifier_build_sha256",
            "s20b_s17_classification",
        )?,
        mapping_cardinality: u64_field(object, "mapping_cardinality", "s20b_s17_classification")?,
        mapped_s16_case_id: nullable_text_field(
            object,
            "mapped_s16_case_id",
            "s20b_s17_classification",
        )?,
        mapped_s16_variant_id: nullable_text_field(
            object,
            "mapped_s16_variant_id",
            "s20b_s17_classification",
        )?,
        mapped_s16_row_sha256: nullable_digest_field(
            object,
            "mapped_s16_row_sha256",
            "s20b_s17_classification",
        )?,
        mapped_reason: text_field(object, "mapped_reason", "s20b_s17_classification")?.into(),
        mapped_failure: text_field(object, "mapped_failure", "s20b_s17_classification")?.into(),
        mapping_status: text_field(object, "mapping_status", "s20b_s17_classification")?.into(),
    };
    if result.mapped_reason.is_empty()
        || result.mapping_cardinality > 1
        || ![
            "NONE",
            "NOT_FOUND",
            "PENDING",
            "CONFLICT",
            "STALE",
            "ROLLBACK",
            "UNAVAILABLE",
            "UNAUTHENTICATED",
            "MALFORMED",
            "INDETERMINATE",
        ]
        .contains(&result.mapped_failure.as_str())
    {
        return Err(validator_error(
            "s20b_s17_classification",
            "reported S17 classification is outside the closed result shape",
        ));
    }
    Ok(result)
}

struct ParsedRawMeasurementV1 {
    retained_raw_event_stream_sha256: [u8; 32],
    raw_event_frame_index: u64,
    raw_event_frame_offset_bytes: u64,
    raw_event_frame_length_bytes: u64,
    raw_event_frame_sha256: [u8; 32],
    lifecycle: RawLifecycleFrameV1,
}

fn lifecycle_value_from_measurement_v1(object: &Map<String, Value>) -> AuthorizationResult<Value> {
    let mut lifecycle = Map::new();
    for key in raw_lifecycle_keys_v1() {
        lifecycle.insert(
            key.into(),
            field(object, key, "s20b_s17_raw_measurement")?.clone(),
        );
    }
    Ok(Value::Object(lifecycle))
}

fn parse_raw_measurement_v1(value: &Value) -> AuthorizationResult<ParsedRawMeasurementV1> {
    let keys = raw_measurement_keys_v1();
    let object = checked_object(value, &keys, "s20b_s17_raw_measurement")?;
    require_text(
        object,
        "measurement_decode_status",
        "EXACT_BOUND_FRAME_DECODED",
        "s20b_s17_raw_measurement",
    )?;
    let frame_length = u64_field(
        object,
        "raw_event_frame_length_bytes",
        "s20b_s17_raw_measurement",
    )?;
    if frame_length == 0 {
        return Err(validator_error(
            "s20b_s17_raw_measurement",
            "S17 retained raw frame length is zero",
        ));
    }
    Ok(ParsedRawMeasurementV1 {
        retained_raw_event_stream_sha256: digest_field(
            object,
            "retained_raw_event_stream_sha256",
            "s20b_s17_raw_measurement",
        )?,
        raw_event_frame_index: u64_field(
            object,
            "raw_event_frame_index",
            "s20b_s17_raw_measurement",
        )?,
        raw_event_frame_offset_bytes: u64_field(
            object,
            "raw_event_frame_offset_bytes",
            "s20b_s17_raw_measurement",
        )?,
        raw_event_frame_length_bytes: frame_length,
        raw_event_frame_sha256: digest_field(
            object,
            "raw_event_frame_sha256",
            "s20b_s17_raw_measurement",
        )?,
        lifecycle: parse_raw_lifecycle_v1(&lifecycle_value_from_measurement_v1(object)?)?,
    })
}

struct ParsedPhaseV1 {
    phase_ordinal: u64,
    phase_kind: ParsedPhaseKindV1,
    process_identity_sha256: [u8; 32],
    raw: ParsedRawMeasurementV1,
    reported_projection: S16ProjectionV1,
    classification_input_sha256: [u8; 32],
    reported_classification: ReportedClassificationV1,
    phase_record_sha256: [u8; 32],
    value: Value,
}

fn phase_keys_v1() -> [&'static str; 8] {
    [
        "phase_ordinal",
        "phase_kind",
        "process_identity_sha256",
        "raw_phase_measurement",
        "s16_virtual_projection",
        "classification_input_sha256",
        "classification",
        "phase_record_sha256",
    ]
}

fn parse_phase_v1(value: &Value) -> AuthorizationResult<ParsedPhaseV1> {
    let object = checked_object(value, &phase_keys_v1(), "s20b_s17_phase")?;
    let phase_ordinal = u64_field(object, "phase_ordinal", "s20b_s17_phase")?;
    if !(1..=2).contains(&phase_ordinal) {
        return Err(validator_error(
            "s20b_s17_phase",
            "S17 phase ordinal is outside 1..=2",
        ));
    }
    Ok(ParsedPhaseV1 {
        phase_ordinal,
        phase_kind: ParsedPhaseKindV1::parse(text_field(object, "phase_kind", "s20b_s17_phase")?)?,
        process_identity_sha256: digest_field(object, "process_identity_sha256", "s20b_s17_phase")?,
        raw: parse_raw_measurement_v1(field(object, "raw_phase_measurement", "s20b_s17_phase")?)?,
        reported_projection: parse_projection_v1(field(
            object,
            "s16_virtual_projection",
            "s20b_s17_phase",
        )?)?,
        classification_input_sha256: digest_field(
            object,
            "classification_input_sha256",
            "s20b_s17_phase",
        )?,
        reported_classification: parse_reported_classification_v1(field(
            object,
            "classification",
            "s20b_s17_phase",
        )?)?,
        phase_record_sha256: digest_field(object, "phase_record_sha256", "s20b_s17_phase")?,
        value: value.clone(),
    })
}

fn classification_input_value_v1(
    raw_packet_sha256: [u8; 32],
    assignment_id_sha256: [u8; 32],
    phase: &ParsedPhaseV1,
) -> AuthorizationResult<Value> {
    let phase_object = phase
        .value
        .as_object()
        .ok_or_else(|| validator_error("s20b_s17_phase", "parsed phase object was lost"))?;
    Ok(json!({
        "assignment_id": hex32(&assignment_id_sha256),
        "phase_kind": phase.phase_kind.as_str(),
        "phase_ordinal": phase.phase_ordinal,
        "process_identity_sha256": hex32(&phase.process_identity_sha256),
        "raw_packet_sha256": hex32(&raw_packet_sha256),
        "raw_phase_measurement": field(
            phase_object,
            "raw_phase_measurement",
            "s20b_s17_phase",
        )?,
        "s16_virtual_projection": field(
            phase_object,
            "s16_virtual_projection",
            "s20b_s17_phase",
        )?
    }))
}

fn recompute_phase_record_v1(phase: &ParsedPhaseV1) -> AuthorizationResult<[u8; 32]> {
    let mut object = phase
        .value
        .as_object()
        .cloned()
        .ok_or_else(|| validator_error("s20b_s17_phase", "parsed phase object was lost"))?;
    object.remove("phase_record_sha256").ok_or_else(|| {
        validator_error(
            "s20b_s17_phase",
            "phase record self digest was absent before exclusion",
        )
    })?;
    jcs_domain_digest_v1(S17_PHASE_DOMAIN, &Value::Object(object))
}

fn expected_ack_payload_from_row_v1(row: &FrozenS16RowV1) -> (Option<[u8; 32]>, Option<[u8; 32]>) {
    match &row.ack_state {
        super::super::super::super::super::ModeledAckStateV1::NotObserved => (None, None),
        super::super::super::super::super::ModeledAckStateV1::Observed {
            receipt_sha256,
            witness_sha256,
        } => (Some(*receipt_sha256), Some(*witness_sha256)),
    }
}

fn reported_unique_equals_row_v1(
    reported: &ReportedClassificationV1,
    row: &FrozenS16RowV1,
) -> bool {
    reported.mapping_cardinality == 1
        && reported.mapping_status == "UNIQUE_FROZEN_S16_REFERENCE"
        && reported.mapped_s16_case_id.as_deref() == Some(row.case_id)
        && reported.mapped_s16_variant_id.as_deref() == Some(row.variant_id.as_ref())
        && reported.mapped_s16_row_sha256
            == Some(super::super::super::super::super::row_commitment_v1(row))
        && reported.mapped_reason == row.reason
        && reported.mapped_failure == row.mapped_s15_failure.as_str()
}

fn reported_indeterminate_v1(
    reported: &ReportedClassificationV1,
    scan: &FullCatalogScanV1<'_>,
) -> bool {
    let expected_reason = match scan {
        FullCatalogScanV1::Zero { .. } => "FULL_FROZEN_S16_CATALOG_NO_MATCH",
        FullCatalogScanV1::Multiple { multiplicity, .. } if *multiplicity > 1 => {
            "FULL_FROZEN_S16_CATALOG_MULTIPLE_MATCHES"
        }
        _ => return false,
    };
    reported.mapping_cardinality == 0
        && reported.mapping_status == "OBSERVED_OUT_OF_MODEL_INDETERMINATE"
        && reported.mapped_s16_case_id.is_none()
        && reported.mapped_s16_variant_id.is_none()
        && reported.mapped_s16_row_sha256.is_none()
        && reported.mapped_reason == expected_reason
        && reported.mapped_failure == "INDETERMINATE"
}

fn build_verified_catalog_v1(
    canonical_base_record: &[u8],
    subject: &VerifiedS19SubjectV1,
) -> AuthorizationResult<Vec<FrozenS16RowV1>> {
    let base_record_sha256: [u8; 32] = Sha256::digest(canonical_base_record).into();
    if canonical_base_record.len() != S16_BASE_RECORD_LEN as usize
        || base_record_sha256 != super::super::super::super::super::CANONICAL_RECORD_SHA256
    {
        return Err(validator_error(
            "s20b_s17_base_record",
            "independent base record does not match the frozen S16 image",
        ));
    }
    let rows = super::super::super::super::super::build_case_catalog_v1(canonical_base_record)
        .map_err(|_| {
            validator_error(
                "s20b_s17_catalog",
                "frozen S16 full-catalog construction failed",
            )
        })?;
    if rows.len() != 5_639
        || subject.catalog_row_count != 5_639
        || super::super::super::super::super::catalog_commitment_v1(&rows)
            != super::super::super::super::super::CATALOG_KAT_SHA256
        || subject.catalog_sha256 != super::super::super::super::super::CATALOG_KAT_SHA256
    {
        return Err(validator_error(
            "s20b_s17_catalog",
            "frozen S16 catalog count or commitment drifted",
        ));
    }
    Ok(rows)
}

fn cross_rule_v1(index: usize, condition: bool) -> AuthorizationResult<()> {
    if condition {
        Ok(())
    } else {
        Err(validator_error(
            "s20b_s17_cross_field_rule",
            S17_CROSS_FIELD_RULES[index],
        ))
    }
}

struct ParsedIdentityV1 {
    observation_id_sha256: [u8; 32],
    run_id_sha256: [u8; 32],
    assignment_id_sha256: [u8; 32],
    raw_packet_sha256: [u8; 32],
    canonical_payload_sha256: [u8; 32],
}

struct ParsedFrozenBindingsV1 {
    s16_catalog_sha256: [u8; 32],
    s16_catalog_message_len: u64,
    base_record_sha256: [u8; 32],
    base_record_len: u64,
    lookup_commitment_sha256: [u8; 32],
    plan_sha256: [u8; 32],
    runner_binary_sha256: [u8; 32],
    classifier_source_sha256: [u8; 32],
    classifier_binary_sha256: [u8; 32],
    expected_oracle_sha256: [u8; 32],
    toolchain_sha256: [u8; 32],
    sqlite_profile_sha256: [u8; 32],
    sqlite_schema_sha256: [u8; 32],
}

struct ParsedAssignmentLabelsV1 {
    family_id: String,
    case_id: String,
    variant_id: String,
    read_quantum_bytes: Option<u64>,
}

struct ParsedStorageV1 {
    canonical_root: String,
    root_before_sha256: [u8; 32],
    root_after_sha256: [u8; 32],
    mountinfo_before_sha256: [u8; 32],
    mountinfo_after_sha256: [u8; 32],
    boot_id_before_sha256: [u8; 32],
    boot_id_after_sha256: [u8; 32],
    database_canonical_path: String,
    database_relative_path: String,
    sqlite_profile_sha256: [u8; 32],
    sqlite_schema_sha256: [u8; 32],
    database_identity_before_sha256: [u8; 32],
    database_identity_after_sha256: [u8; 32],
}

struct ParsedCrashV1 {
    controller_process_identity_sha256: [u8; 32],
    controller_pid: u64,
    controller_start: u64,
    child_process_identity_sha256: [u8; 32],
    child_nonce_sha256: [u8; 32],
    child_pid: u64,
    child_start: u64,
    child_image_sha256: [u8; 32],
    pidfd_target_pid: Option<u64>,
    pidfd_target_start: Option<u64>,
    signal_sender_pid: Option<u64>,
    signal_sender_start: Option<u64>,
    control_shape_valid: bool,
    pidfd_shape_valid: bool,
}

struct ParsedRestartV1 {
    fresh_process_identity_sha256: [u8; 32],
    fresh_nonce_sha256: [u8; 32],
    fresh_pid: u64,
    fresh_start: u64,
    fresh_image_sha256: [u8; 32],
}

#[derive(Clone, Debug, Eq, PartialEq)]
struct DurableImageV1 {
    object_state: String,
    object_len: Option<u64>,
    object_sha256: Option<[u8; 32]>,
    receipt_state: String,
    receipt_sha256: Option<[u8; 32]>,
    witness_state: String,
    witness_sha256: Option<[u8; 32]>,
    selected_view_state: String,
    selected_view_sha256: Option<[u8; 32]>,
    competing_view_state: String,
    competing_view_sha256: Option<[u8; 32]>,
}

struct ParsedCustodyV1 {
    raw_evidence_sha256: [u8; 32],
    canonical_evidence_sha256: [u8; 32],
    sequence: u64,
    previous_sha256: Option<[u8; 32]>,
    entry_sha256: [u8; 32],
    value: Value,
}

struct ParsedAccountingV1 {
    sigkill_count: u64,
    fresh_restart_count: u64,
    phase_count: u64,
    value: Value,
}

struct ParsedObservationV1 {
    identity: ParsedIdentityV1,
    frozen: ParsedFrozenBindingsV1,
    assignment: ParsedAssignmentLabelsV1,
    owner_resource_decision_sha256: [u8; 32],
    storage: ParsedStorageV1,
    crash: ParsedCrashV1,
    restart: Option<ParsedRestartV1>,
    recovered: DurableImageV1,
    phases: Vec<ParsedPhaseV1>,
    custody: ParsedCustodyV1,
    accounting: ParsedAccountingV1,
}

fn identity_keys_v1() -> [&'static str; 6] {
    [
        "observation_id",
        "run_id",
        "assignment_id",
        "repetition",
        "raw_packet_sha256",
        "canonical_payload_sha256",
    ]
}

fn parse_identity_v1(value: &Value) -> AuthorizationResult<ParsedIdentityV1> {
    let object = checked_object(value, &identity_keys_v1(), "s20b_s17_identity")?;
    require_u64(object, "repetition", 1, "s20b_s17_identity")?;
    Ok(ParsedIdentityV1 {
        observation_id_sha256: digest_field(object, "observation_id", "s20b_s17_identity")?,
        run_id_sha256: digest_field(object, "run_id", "s20b_s17_identity")?,
        assignment_id_sha256: digest_field(object, "assignment_id", "s20b_s17_identity")?,
        raw_packet_sha256: digest_field(object, "raw_packet_sha256", "s20b_s17_identity")?,
        canonical_payload_sha256: digest_field(
            object,
            "canonical_payload_sha256",
            "s20b_s17_identity",
        )?,
    })
}

fn frozen_binding_keys_v1() -> [&'static str; 20] {
    [
        "source_parent_commit",
        "s16_source_commit",
        "s16_integration_commit",
        "s15_contract_sha256",
        "s16_contract_sha256",
        "s16_catalog_sha256",
        "s16_catalog_message_len",
        "base_record_sha256",
        "base_record_len",
        "lookup_commitment_sha256",
        "plan_sha256",
        "runner_source_sha256",
        "runner_binary_sha256",
        "classifier_source_sha256",
        "classifier_binary_sha256",
        "expected_oracle_sha256",
        "toolchain_sha256",
        "sqlite_profile_sha256",
        "sqlite_schema_sha256",
        "control_protocol_sha256",
    ]
}

fn parse_frozen_bindings_v1(value: &Value) -> AuthorizationResult<ParsedFrozenBindingsV1> {
    let object = checked_object(value, &frozen_binding_keys_v1(), "s20b_s17_frozen_bindings")?;
    require_text(
        object,
        "source_parent_commit",
        "d5bbe55d5d95b1163e287415f437cf77c594135d",
        "s20b_s17_frozen_bindings",
    )?;
    require_text(
        object,
        "s16_source_commit",
        "dca7436a9d9df990355d67e374184202332f0354",
        "s20b_s17_frozen_bindings",
    )?;
    require_text(
        object,
        "s16_integration_commit",
        "d7f3e206169227905dbd320f1876de46e3facfea",
        "s20b_s17_frozen_bindings",
    )?;
    for (key, expected) in [
        (
            "s15_contract_sha256",
            "07d7ae5e7345bb5052aa130349af2e90bae853e5c74560346a4178b2b0397cc7",
        ),
        (
            "s16_contract_sha256",
            "2500ae0651025434392b87d5a151487faa4b6e60a6523e083c1987446c3bdb66",
        ),
        (
            "s16_catalog_sha256",
            "c09cdc640957594cc7acc2eeea39cb4e59993631ef04a1fa1e26a69c285af853",
        ),
        (
            "base_record_sha256",
            "a788ec43fefa76e393d77c86bbfabeef7d2ae8c5499bb834c1945af5cbb1b3cd",
        ),
        (
            "lookup_commitment_sha256",
            "866e016ce631433e3e272d0858906f3c76c67204cd74b73ab11b7353e57eae00",
        ),
    ] {
        require_text(object, key, expected, "s20b_s17_frozen_bindings")?;
    }
    let bindings = ParsedFrozenBindingsV1 {
        s16_catalog_sha256: digest_field(object, "s16_catalog_sha256", "s20b_s17_frozen_bindings")?,
        s16_catalog_message_len: u64_field(
            object,
            "s16_catalog_message_len",
            "s20b_s17_frozen_bindings",
        )?,
        base_record_sha256: digest_field(object, "base_record_sha256", "s20b_s17_frozen_bindings")?,
        base_record_len: u64_field(object, "base_record_len", "s20b_s17_frozen_bindings")?,
        lookup_commitment_sha256: digest_field(
            object,
            "lookup_commitment_sha256",
            "s20b_s17_frozen_bindings",
        )?,
        plan_sha256: digest_field(object, "plan_sha256", "s20b_s17_frozen_bindings")?,
        runner_binary_sha256: digest_field(
            object,
            "runner_binary_sha256",
            "s20b_s17_frozen_bindings",
        )?,
        classifier_source_sha256: digest_field(
            object,
            "classifier_source_sha256",
            "s20b_s17_frozen_bindings",
        )?,
        classifier_binary_sha256: digest_field(
            object,
            "classifier_binary_sha256",
            "s20b_s17_frozen_bindings",
        )?,
        expected_oracle_sha256: digest_field(
            object,
            "expected_oracle_sha256",
            "s20b_s17_frozen_bindings",
        )?,
        toolchain_sha256: digest_field(object, "toolchain_sha256", "s20b_s17_frozen_bindings")?,
        sqlite_profile_sha256: digest_field(
            object,
            "sqlite_profile_sha256",
            "s20b_s17_frozen_bindings",
        )?,
        sqlite_schema_sha256: digest_field(
            object,
            "sqlite_schema_sha256",
            "s20b_s17_frozen_bindings",
        )?,
    };
    for key in ["runner_source_sha256", "control_protocol_sha256"] {
        digest_field(object, key, "s20b_s17_frozen_bindings")?;
    }
    if bindings.s16_catalog_message_len != S16_CATALOG_MESSAGE_LEN
        || bindings.base_record_len != S16_BASE_RECORD_LEN
    {
        return Err(validator_error(
            "s20b_s17_frozen_bindings",
            "S17 frozen S16 length commitment drifted",
        ));
    }
    Ok(bindings)
}

fn assignment_keys_v1() -> [&'static str; 5] {
    [
        "owned_lab_family_id",
        "planned_s16_case_id",
        "planned_variant_id",
        "read_quantum_bytes",
        "planned_label_is_outcome_oracle",
    ]
}

fn parse_assignment_labels_v1(value: &Value) -> AuthorizationResult<ParsedAssignmentLabelsV1> {
    let object = checked_object(value, &assignment_keys_v1(), "s20b_s17_assignment")?;
    require_bool(
        object,
        "planned_label_is_outcome_oracle",
        false,
        "s20b_s17_assignment",
    )?;
    Ok(ParsedAssignmentLabelsV1 {
        family_id: text_field(object, "owned_lab_family_id", "s20b_s17_assignment")?.into(),
        case_id: text_field(object, "planned_s16_case_id", "s20b_s17_assignment")?.into(),
        variant_id: text_field(object, "planned_variant_id", "s20b_s17_assignment")?.into(),
        read_quantum_bytes: nullable_u64_field(
            object,
            "read_quantum_bytes",
            "s20b_s17_assignment",
        )?,
    })
}

fn authorization_keys_v1() -> [&'static str; 6] {
    [
        "owner_resource_decision_sha256",
        "owner_identity_authenticated",
        "decision_authorizes_exact_assignment",
        "single_use_replay_cas_committed",
        "production_authorized",
        "provider_authorized",
    ]
}

fn parse_authorization_v1(value: &Value) -> AuthorizationResult<[u8; 32]> {
    let object = checked_object(value, &authorization_keys_v1(), "s20b_s17_authorization")?;
    for key in [
        "owner_identity_authenticated",
        "decision_authorizes_exact_assignment",
        "single_use_replay_cas_committed",
    ] {
        require_bool(object, key, true, "s20b_s17_authorization")?;
    }
    for key in ["production_authorized", "provider_authorized"] {
        require_bool(object, key, false, "s20b_s17_authorization")?;
    }
    digest_field(
        object,
        "owner_resource_decision_sha256",
        "s20b_s17_authorization",
    )
}

fn storage_keys_v1() -> [&'static str; 36] {
    [
        "profile",
        "canonical_root",
        "root_is_unique_per_run",
        "root_created_exclusively",
        "root_mode_octal",
        "root_symlink_observed",
        "root_stat_identity_before_sha256",
        "root_stat_identity_after_sha256",
        "root_identity_stable_across_observation",
        "root_device_major_minor",
        "root_mount_id",
        "device",
        "filesystem",
        "mountinfo_entry_before_sha256",
        "mountinfo_entry_after_sha256",
        "mount_identity_stable_across_observation",
        "mount_options_sha256",
        "filesystem_verified_from_mountinfo",
        "persistent_filesystem_verified",
        "tmpfs_overlay_or_fuse_detected",
        "kernel_identity_sha256",
        "boot_id_before_sha256",
        "boot_id_after_sha256",
        "same_boot_verified",
        "database_canonical_path",
        "database_relative_path",
        "database_regular_file",
        "database_mode_octal",
        "database_symlink_observed",
        "database_hardlink_count",
        "sqlite_runtime_profile",
        "network_disabled",
        "root_privilege_used",
        "drop_caches_used",
        "reboot_used",
        "block_device_fault_used",
    ]
}

fn sqlite_keys_v1() -> [&'static str; 29] {
    [
        "profile_sha256",
        "schema_sha256",
        "profile_matches_frozen_binding",
        "schema_matches_frozen_binding",
        "journal_mode",
        "pragma_journal_mode_observed",
        "synchronous",
        "pragma_synchronous_observed",
        "application_id",
        "application_id_matches_frozen_profile",
        "user_version",
        "user_version_matches_frozen_profile",
        "database_created_exclusively",
        "normal_reopen_may_create",
        "normal_open_opened_existing_regular_file",
        "database_identity_before_sha256",
        "database_identity_after_sha256",
        "database_identity_stable_across_observation",
        "declared_durable_stage_requires_database_fsync",
        "declared_durable_stage_requires_parent_directory_fsync",
        "database_fsync_attempted_before_kill",
        "database_fsync_return_code",
        "parent_directory_fsync_attempted_before_kill",
        "parent_directory_fsync_return_code",
        "fsync_event_log_sha256",
        "quick_check_result",
        "unexpected_schema_object_count",
        "unexpected_temp_object_count",
        "unexpected_sidecar_count",
    ]
}

fn parse_storage_v1(value: &Value) -> AuthorizationResult<ParsedStorageV1> {
    let object = checked_object(value, &storage_keys_v1(), "s20b_s17_storage")?;
    for (key, expected) in [
        (
            "profile",
            "ISOLATED_OWNED_LAB_F2FS_PROCESS_SIGKILL_FRESH_PROCESS_RESTART_HISTORICAL_ONLY",
        ),
        ("root_mode_octal", "0700"),
        ("device", "/dev/nvme0n1p7"),
        ("filesystem", "f2fs"),
        ("database_mode_octal", "0600"),
    ] {
        require_text(object, key, expected, "s20b_s17_storage")?;
    }
    for key in [
        "root_is_unique_per_run",
        "root_created_exclusively",
        "root_identity_stable_across_observation",
        "mount_identity_stable_across_observation",
        "filesystem_verified_from_mountinfo",
        "persistent_filesystem_verified",
        "same_boot_verified",
        "database_regular_file",
        "network_disabled",
    ] {
        require_bool(object, key, true, "s20b_s17_storage")?;
    }
    for key in [
        "root_symlink_observed",
        "tmpfs_overlay_or_fuse_detected",
        "database_symlink_observed",
        "root_privilege_used",
        "drop_caches_used",
        "reboot_used",
        "block_device_fault_used",
    ] {
        require_bool(object, key, false, "s20b_s17_storage")?;
    }
    require_u64(object, "database_hardlink_count", 1, "s20b_s17_storage")?;
    if u64_field(object, "root_mount_id", "s20b_s17_storage")? == 0 {
        return Err(validator_error(
            "s20b_s17_storage",
            "S17 root mount identifier is zero",
        ));
    }
    let device = text_field(object, "root_device_major_minor", "s20b_s17_storage")?;
    if device.split_once(':').is_none()
        || !device
            .bytes()
            .all(|byte| byte.is_ascii_digit() || byte == b':')
    {
        return Err(validator_error(
            "s20b_s17_storage",
            "S17 root device major/minor is malformed",
        ));
    }
    for key in ["mount_options_sha256", "kernel_identity_sha256"] {
        digest_field(object, key, "s20b_s17_storage")?;
    }
    let sqlite_value = field(object, "sqlite_runtime_profile", "s20b_s17_storage")?;
    let sqlite = checked_object(sqlite_value, &sqlite_keys_v1(), "s20b_s17_sqlite")?;
    for key in [
        "profile_matches_frozen_binding",
        "schema_matches_frozen_binding",
        "application_id_matches_frozen_profile",
        "user_version_matches_frozen_profile",
        "database_created_exclusively",
        "normal_open_opened_existing_regular_file",
        "database_identity_stable_across_observation",
        "declared_durable_stage_requires_database_fsync",
        "declared_durable_stage_requires_parent_directory_fsync",
    ] {
        require_bool(sqlite, key, true, "s20b_s17_sqlite")?;
    }
    require_bool(sqlite, "normal_reopen_may_create", false, "s20b_s17_sqlite")?;
    for (key, expected) in [
        ("journal_mode", "DELETE"),
        ("pragma_journal_mode_observed", "delete"),
        ("synchronous", "EXTRA"),
        ("quick_check_result", "ok"),
    ] {
        require_text(sqlite, key, expected, "s20b_s17_sqlite")?;
    }
    require_u64(sqlite, "pragma_synchronous_observed", 3, "s20b_s17_sqlite")?;
    if u64_field(sqlite, "application_id", "s20b_s17_sqlite")? == 0
        || u64_field(sqlite, "user_version", "s20b_s17_sqlite")? == 0
    {
        return Err(validator_error(
            "s20b_s17_sqlite",
            "S17 SQLite application or user version is zero",
        ));
    }
    for (attempt_key, result_key) in [
        (
            "database_fsync_attempted_before_kill",
            "database_fsync_return_code",
        ),
        (
            "parent_directory_fsync_attempted_before_kill",
            "parent_directory_fsync_return_code",
        ),
    ] {
        let attempted = bool_field(sqlite, attempt_key, "s20b_s17_sqlite")?;
        let result = nullable_u64_field(sqlite, result_key, "s20b_s17_sqlite")?;
        if (attempted && result != Some(0)) || (!attempted && result.is_some()) {
            return Err(validator_error(
                "s20b_s17_sqlite",
                "S17 SQLite durability-call result contradicts its attempt state",
            ));
        }
    }
    digest_field(sqlite, "fsync_event_log_sha256", "s20b_s17_sqlite")?;
    for key in [
        "unexpected_schema_object_count",
        "unexpected_temp_object_count",
        "unexpected_sidecar_count",
    ] {
        require_u64(sqlite, key, 0, "s20b_s17_sqlite")?;
    }
    Ok(ParsedStorageV1 {
        canonical_root: text_field(object, "canonical_root", "s20b_s17_storage")?.into(),
        root_before_sha256: digest_field(
            object,
            "root_stat_identity_before_sha256",
            "s20b_s17_storage",
        )?,
        root_after_sha256: digest_field(
            object,
            "root_stat_identity_after_sha256",
            "s20b_s17_storage",
        )?,
        mountinfo_before_sha256: digest_field(
            object,
            "mountinfo_entry_before_sha256",
            "s20b_s17_storage",
        )?,
        mountinfo_after_sha256: digest_field(
            object,
            "mountinfo_entry_after_sha256",
            "s20b_s17_storage",
        )?,
        boot_id_before_sha256: digest_field(object, "boot_id_before_sha256", "s20b_s17_storage")?,
        boot_id_after_sha256: digest_field(object, "boot_id_after_sha256", "s20b_s17_storage")?,
        database_canonical_path: text_field(object, "database_canonical_path", "s20b_s17_storage")?
            .into(),
        database_relative_path: text_field(object, "database_relative_path", "s20b_s17_storage")?
            .into(),
        sqlite_profile_sha256: digest_field(sqlite, "profile_sha256", "s20b_s17_sqlite")?,
        sqlite_schema_sha256: digest_field(sqlite, "schema_sha256", "s20b_s17_sqlite")?,
        database_identity_before_sha256: digest_field(
            sqlite,
            "database_identity_before_sha256",
            "s20b_s17_sqlite",
        )?,
        database_identity_after_sha256: digest_field(
            sqlite,
            "database_identity_after_sha256",
            "s20b_s17_sqlite",
        )?,
    })
}

fn crash_keys_v1() -> [&'static str; 36] {
    [
        "control_sequence",
        "controller_process_identity_sha256",
        "controller_pid",
        "controller_start_identity",
        "controller_distinct_from_child",
        "child_process_identity_sha256",
        "child_process_nonce_sha256",
        "child_pid",
        "child_start_identity",
        "child_exec_image_sha256",
        "child_exec_image_matches_frozen_runner",
        "cut_ready_channel",
        "cut_ready_frame_sha256",
        "cut_ready_persisted_before_kill",
        "kill_method",
        "pidfd_open_succeeded",
        "pidfd_open_errno",
        "pidfd_fd_number",
        "pidfd_fdinfo_sha256",
        "pidfd_target_pid",
        "pidfd_target_start_identity",
        "pidfd_target_matches_child",
        "kill_target_identity_rechecked",
        "pidfd_send_signal_return_code",
        "pidfd_send_signal_errno",
        "signal_sender_pid",
        "signal_sender_start_identity",
        "signal_sender_matches_controller",
        "child_descendant_count_before_kill",
        "pidfd_became_readable",
        "wait_status_kind",
        "terminating_signal",
        "observed_exit_signal_number",
        "child_reaped",
        "post_reap_original_proc_identity_present",
        "graceful_exit_observed",
        // process_crash_observed is appended by crash_keys_complete_v1().
    ]
}

fn crash_keys_complete_v1() -> Vec<&'static str> {
    let mut keys = crash_keys_v1().to_vec();
    keys.push("process_crash_observed");
    keys
}

fn parse_crash_v1(value: &Value) -> AuthorizationResult<ParsedCrashV1> {
    let keys = crash_keys_complete_v1();
    let object = checked_object(value, &keys, "s20b_s17_crash")?;
    if u64_field(object, "control_sequence", "s20b_s17_crash")? == 0 {
        return Err(validator_error(
            "s20b_s17_crash",
            "S17 control sequence is zero",
        ));
    }
    let controller_process_identity_sha256 = digest_field(
        object,
        "controller_process_identity_sha256",
        "s20b_s17_crash",
    )?;
    let controller_pid = u64_field(object, "controller_pid", "s20b_s17_crash")?;
    let controller_start =
        start_ticks_field(object, "controller_start_identity", "s20b_s17_crash")?;
    let child_process_identity_sha256 =
        digest_field(object, "child_process_identity_sha256", "s20b_s17_crash")?;
    let child_nonce_sha256 = digest_field(object, "child_process_nonce_sha256", "s20b_s17_crash")?;
    let child_pid = u64_field(object, "child_pid", "s20b_s17_crash")?;
    let child_start = start_ticks_field(object, "child_start_identity", "s20b_s17_crash")?;
    let child_image_sha256 = digest_field(object, "child_exec_image_sha256", "s20b_s17_crash")?;
    if controller_pid == 0 || child_pid == 0 {
        return Err(validator_error(
            "s20b_s17_crash",
            "S17 controller or child pid is zero",
        ));
    }
    for key in [
        "controller_distinct_from_child",
        "child_exec_image_matches_frozen_runner",
    ] {
        require_bool(object, key, true, "s20b_s17_crash")?;
    }
    require_text(
        object,
        "cut_ready_channel",
        "ANONYMOUS_PIPE",
        "s20b_s17_crash",
    )?;
    require_bool(
        object,
        "cut_ready_persisted_before_kill",
        false,
        "s20b_s17_crash",
    )?;
    digest_field(object, "cut_ready_frame_sha256", "s20b_s17_crash")?;

    let kill_method = text_field(object, "kill_method", "s20b_s17_crash")?.to_owned();
    let pidfd_open_succeeded = bool_field(object, "pidfd_open_succeeded", "s20b_s17_crash")?;
    let pidfd_open_errno = nullable_u64_field(object, "pidfd_open_errno", "s20b_s17_crash")?;
    let pidfd_fd_number = nullable_u64_field(object, "pidfd_fd_number", "s20b_s17_crash")?;
    let pidfd_fdinfo = nullable_digest_field(object, "pidfd_fdinfo_sha256", "s20b_s17_crash")?;
    let pidfd_target_pid = nullable_u64_field(object, "pidfd_target_pid", "s20b_s17_crash")?;
    let pidfd_target_start =
        nullable_start_ticks_field(object, "pidfd_target_start_identity", "s20b_s17_crash")?;
    let pidfd_target_matches = bool_field(object, "pidfd_target_matches_child", "s20b_s17_crash")?;
    let kill_rechecked = bool_field(object, "kill_target_identity_rechecked", "s20b_s17_crash")?;
    let signal_result =
        nullable_u64_field(object, "pidfd_send_signal_return_code", "s20b_s17_crash")?;
    let signal_errno = nullable_u64_field(object, "pidfd_send_signal_errno", "s20b_s17_crash")?;
    let signal_sender_pid = nullable_u64_field(object, "signal_sender_pid", "s20b_s17_crash")?;
    let signal_sender_start =
        nullable_start_ticks_field(object, "signal_sender_start_identity", "s20b_s17_crash")?;
    let signal_sender_matches =
        bool_field(object, "signal_sender_matches_controller", "s20b_s17_crash")?;
    let descendant_count = u64_field(
        object,
        "child_descendant_count_before_kill",
        "s20b_s17_crash",
    )?;
    let became_readable = bool_field(object, "pidfd_became_readable", "s20b_s17_crash")?;
    let wait_kind = text_field(object, "wait_status_kind", "s20b_s17_crash")?;
    let terminating_signal = text_field(object, "terminating_signal", "s20b_s17_crash")?;
    let exit_signal = nullable_u64_field(object, "observed_exit_signal_number", "s20b_s17_crash")?;
    let child_reaped = bool_field(object, "child_reaped", "s20b_s17_crash")?;
    let proc_present = bool_field(
        object,
        "post_reap_original_proc_identity_present",
        "s20b_s17_crash",
    )?;
    let graceful = bool_field(object, "graceful_exit_observed", "s20b_s17_crash")?;
    let process_crash = bool_field(object, "process_crash_observed", "s20b_s17_crash")?;
    let control_shape_valid = kill_method == "NONE_CONTROL"
        && !pidfd_open_succeeded
        && pidfd_open_errno.is_none()
        && pidfd_fd_number.is_none()
        && pidfd_fdinfo.is_none()
        && pidfd_target_pid.is_none()
        && pidfd_target_start.is_none()
        && !pidfd_target_matches
        && !kill_rechecked
        && signal_result.is_none()
        && signal_errno.is_none()
        && signal_sender_pid.is_none()
        && signal_sender_start.is_none()
        && !signal_sender_matches
        && descendant_count == 0
        && !became_readable
        && wait_kind == "CLEAN_CONTROL_EXIT"
        && terminating_signal == "NONE"
        && exit_signal.is_none()
        && child_reaped
        && !proc_present
        && graceful
        && !process_crash;
    let pidfd_shape_valid = kill_method == "CONTROLLER_PIDFD_SEND_SIGNAL_SIGKILL"
        && pidfd_open_succeeded
        && pidfd_open_errno.is_none()
        && pidfd_fd_number.is_some()
        && pidfd_fdinfo.is_some()
        && pidfd_target_pid.is_some_and(|value| value > 0)
        && pidfd_target_start.is_some()
        && pidfd_target_matches
        && kill_rechecked
        && signal_result == Some(0)
        && signal_errno.is_none()
        && signal_sender_pid.is_some_and(|value| value > 0)
        && signal_sender_start.is_some()
        && signal_sender_matches
        && descendant_count == 0
        && became_readable
        && wait_kind == "SIGNALED"
        && terminating_signal == "SIGKILL"
        && exit_signal == Some(9)
        && child_reaped
        && !proc_present
        && !graceful
        && process_crash;
    Ok(ParsedCrashV1 {
        controller_process_identity_sha256,
        controller_pid,
        controller_start,
        child_process_identity_sha256,
        child_nonce_sha256,
        child_pid,
        child_start,
        child_image_sha256,
        pidfd_target_pid,
        pidfd_target_start,
        signal_sender_pid,
        signal_sender_start,
        control_shape_valid,
        pidfd_shape_valid,
    })
}

fn restart_keys_v1() -> [&'static str; 22] {
    [
        "fresh_process_started",
        "spawn_method",
        "fresh_child_process_identity_sha256",
        "fresh_process_nonce_sha256",
        "fresh_child_pid",
        "fresh_child_start_identity",
        "fresh_exec_image_sha256",
        "fresh_exec_image_matches_frozen_runner",
        "fresh_pid_and_start_identity_distinct_from_initial_child",
        "fresh_process_nonce_distinct_from_initial_child",
        "fresh_process_parent_matches_controller",
        "same_process_reused",
        "same_boot_verified",
        "target_fds_closed_before_exec",
        "inherited_target_file_descriptor_used",
        "inherited_adapter_sink_or_cache_used",
        "exact_path_reopened",
        "fresh_process_reaped",
        "fresh_process_exit_status",
        "read_result",
        "observed_record_len",
        "observed_record_sha256",
    ]
}

fn parse_restart_v1(value: &Value) -> AuthorizationResult<Option<ParsedRestartV1>> {
    if value.is_null() {
        return Ok(None);
    }
    let object = checked_object(value, &restart_keys_v1(), "s20b_s17_restart")?;
    for key in [
        "fresh_process_started",
        "fresh_exec_image_matches_frozen_runner",
        "fresh_pid_and_start_identity_distinct_from_initial_child",
        "fresh_process_nonce_distinct_from_initial_child",
        "fresh_process_parent_matches_controller",
        "same_boot_verified",
        "target_fds_closed_before_exec",
        "exact_path_reopened",
        "fresh_process_reaped",
    ] {
        require_bool(object, key, true, "s20b_s17_restart")?;
    }
    for key in [
        "same_process_reused",
        "inherited_target_file_descriptor_used",
        "inherited_adapter_sink_or_cache_used",
    ] {
        require_bool(object, key, false, "s20b_s17_restart")?;
    }
    require_text(object, "spawn_method", "NEW_EXEC", "s20b_s17_restart")?;
    require_text(
        object,
        "fresh_process_exit_status",
        "CLEAN_EXIT_ZERO",
        "s20b_s17_restart",
    )?;
    let read_result = text_field(object, "read_result", "s20b_s17_restart")?;
    let observed_len = u64_field(object, "observed_record_len", "s20b_s17_restart")?;
    let observed_sha = nullable_digest_field(object, "observed_record_sha256", "s20b_s17_restart")?;
    if ![
        "STREAM_EXACT",
        "NOT_FOUND",
        "PENDING",
        "CONFLICT",
        "STALE",
        "ROLLBACK",
        "UNAVAILABLE",
        "UNAUTHENTICATED",
        "MALFORMED",
        "INDETERMINATE",
    ]
    .contains(&read_result)
        || observed_len > 278_528
        || (read_result == "STREAM_EXACT" && (observed_len == 0 || observed_sha.is_none()))
        || (read_result != "STREAM_EXACT" && (observed_len != 0 || observed_sha.is_some()))
    {
        return Err(validator_error(
            "s20b_s17_restart",
            "S17 restart read result contradicts its observed record",
        ));
    }
    let fresh_process_identity_sha256 = digest_field(
        object,
        "fresh_child_process_identity_sha256",
        "s20b_s17_restart",
    )?;
    let fresh_nonce_sha256 =
        digest_field(object, "fresh_process_nonce_sha256", "s20b_s17_restart")?;
    let fresh_pid = u64_field(object, "fresh_child_pid", "s20b_s17_restart")?;
    let fresh_start = start_ticks_field(object, "fresh_child_start_identity", "s20b_s17_restart")?;
    let fresh_image_sha256 = digest_field(object, "fresh_exec_image_sha256", "s20b_s17_restart")?;
    if fresh_pid == 0 {
        return Err(validator_error(
            "s20b_s17_restart",
            "S17 fresh child pid is zero",
        ));
    }
    Ok(Some(ParsedRestartV1 {
        fresh_process_identity_sha256,
        fresh_nonce_sha256,
        fresh_pid,
        fresh_start,
        fresh_image_sha256,
    }))
}

fn recovered_keys_v1() -> [&'static str; 16] {
    [
        "event_log_sha256",
        "write_sync_receipt_state",
        "write_sync_receipt_sha256",
        "object_state",
        "object_len",
        "object_sha256",
        "receipt_state",
        "receipt_sha256",
        "witness_state",
        "witness_sha256",
        "selected_view_state",
        "selected_view_sha256",
        "competing_view_state",
        "competing_view_sha256",
        "pre_crash_ack_state",
        "post_restart_local_ack_state",
    ]
}

fn parse_recovered_v1(value: &Value) -> AuthorizationResult<DurableImageV1> {
    let object = checked_object(value, &recovered_keys_v1(), "s20b_s17_recovered")?;
    digest_field(object, "event_log_sha256", "s20b_s17_recovered")?;
    let sync_state = text_field(object, "write_sync_receipt_state", "s20b_s17_recovered")?;
    let sync_sha =
        nullable_digest_field(object, "write_sync_receipt_sha256", "s20b_s17_recovered")?;
    if (sync_state == "PRESENT") != sync_sha.is_some()
        || !["ABSENT", "PRESENT", "UNKNOWN"].contains(&sync_state)
    {
        return Err(validator_error(
            "s20b_s17_recovered",
            "S17 write-sync receipt state is inconsistent",
        ));
    }
    let object_state = text_field(object, "object_state", "s20b_s17_recovered")?.to_owned();
    let object_len = nullable_u64_field(object, "object_len", "s20b_s17_recovered")?;
    let object_sha256 = nullable_digest_field(object, "object_sha256", "s20b_s17_recovered")?;
    let object_valid = match object_state.as_str() {
        "ABSENT" => object_len == Some(0) && object_sha256.is_none(),
        "PARTIAL" | "COMMITTED" => {
            object_len.is_some_and(|length| (1..=278_528).contains(&length))
                && object_sha256.is_some()
        }
        "UNKNOWN" => object_len.is_none() && object_sha256.is_none(),
        _ => false,
    };
    let receipt_state = text_field(object, "receipt_state", "s20b_s17_recovered")?.to_owned();
    let receipt_sha256 = nullable_digest_field(object, "receipt_sha256", "s20b_s17_recovered")?;
    let receipt_valid = match receipt_state.as_str() {
        "COMMITTED" => receipt_sha256.is_some(),
        "ABSENT" | "UNKNOWN" => receipt_sha256.is_none(),
        _ => false,
    };
    let witness_state = text_field(object, "witness_state", "s20b_s17_recovered")?.to_owned();
    let witness_sha256 = nullable_digest_field(object, "witness_sha256", "s20b_s17_recovered")?;
    let witness_valid = match witness_state.as_str() {
        "PRESENT" | "FORKED" => witness_sha256.is_some(),
        "ABSENT" | "UNAVAILABLE" | "UNKNOWN" => witness_sha256.is_none(),
        _ => false,
    };
    let selected_view_state =
        text_field(object, "selected_view_state", "s20b_s17_recovered")?.to_owned();
    let selected_view_sha256 =
        nullable_digest_field(object, "selected_view_sha256", "s20b_s17_recovered")?;
    let selected_valid = match selected_view_state.as_str() {
        "PRESENT" => selected_view_sha256.is_some(),
        "ABSENT" | "UNKNOWN" => selected_view_sha256.is_none(),
        _ => false,
    };
    let competing_view_state =
        text_field(object, "competing_view_state", "s20b_s17_recovered")?.to_owned();
    let competing_view_sha256 =
        nullable_digest_field(object, "competing_view_sha256", "s20b_s17_recovered")?;
    let competing_valid = match competing_view_state.as_str() {
        "PRESENT" => competing_view_sha256.is_some(),
        "ABSENT" | "UNKNOWN" => competing_view_sha256.is_none(),
        _ => false,
    };
    if !object_valid || !receipt_valid || !witness_valid || !selected_valid || !competing_valid {
        return Err(validator_error(
            "s20b_s17_recovered",
            "S17 top-level recovered durable image is inconsistent",
        ));
    }
    let pre_ack = text_field(object, "pre_crash_ack_state", "s20b_s17_recovered")?;
    let post_ack = text_field(object, "post_restart_local_ack_state", "s20b_s17_recovered")?;
    if !["NOT_OBSERVED", "OBSERVED", "UNKNOWN"].contains(&pre_ack)
        || !["NOT_OBSERVED", "UNKNOWN"].contains(&post_ack)
    {
        return Err(validator_error(
            "s20b_s17_recovered",
            "S17 acknowledgement recovery state is outside the closed schema",
        ));
    }
    Ok(DurableImageV1 {
        object_state,
        object_len,
        object_sha256,
        receipt_state,
        receipt_sha256,
        witness_state,
        witness_sha256,
        selected_view_state,
        selected_view_sha256,
        competing_view_state,
        competing_view_sha256,
    })
}

fn custody_keys_v1() -> [&'static str; 12] {
    [
        "raw_evidence_sha256",
        "canonical_evidence_sha256",
        "raw_evidence_matches_identity_raw_packet",
        "canonical_evidence_matches_identity_payload",
        "custody_sequence",
        "previous_custody_entry_sha256",
        "custody_entry_sha256",
        "custodian_identity_sha256",
        "trusted_time_obtained",
        "trusted_time_receipt_sha256",
        "retained_before_cleanup",
        "independent_failure_domain_proved",
    ]
}

fn parse_custody_v1(value: &Value) -> AuthorizationResult<ParsedCustodyV1> {
    let object = checked_object(value, &custody_keys_v1(), "s20b_s17_custody")?;
    for key in [
        "raw_evidence_matches_identity_raw_packet",
        "canonical_evidence_matches_identity_payload",
        "retained_before_cleanup",
    ] {
        require_bool(object, key, true, "s20b_s17_custody")?;
    }
    for key in ["trusted_time_obtained", "independent_failure_domain_proved"] {
        require_bool(object, key, false, "s20b_s17_custody")?;
    }
    if !field(object, "trusted_time_receipt_sha256", "s20b_s17_custody")?.is_null() {
        return Err(validator_error(
            "s20b_s17_custody",
            "S17 custody fabricated a trusted-time receipt",
        ));
    }
    let sequence = u64_field(object, "custody_sequence", "s20b_s17_custody")?;
    if sequence == 0 {
        return Err(validator_error(
            "s20b_s17_custody",
            "S17 custody sequence is zero",
        ));
    }
    Ok(ParsedCustodyV1 {
        raw_evidence_sha256: digest_field(object, "raw_evidence_sha256", "s20b_s17_custody")?,
        canonical_evidence_sha256: digest_field(
            object,
            "canonical_evidence_sha256",
            "s20b_s17_custody",
        )?,
        sequence,
        previous_sha256: nullable_digest_field(
            object,
            "previous_custody_entry_sha256",
            "s20b_s17_custody",
        )?,
        entry_sha256: digest_field(object, "custody_entry_sha256", "s20b_s17_custody")?,
        value: value.clone(),
    })
}

fn accounting_keys_v1() -> [&'static str; 9] {
    [
        "assigned_attempt_denominator_increment",
        "provider_observation_count",
        "owned_lab_process_sigkill_observation_count",
        "owned_lab_fresh_process_restart_observation_count",
        "s16_mapping_phase_record_count",
        "guest_reboot_observation_count",
        "host_reboot_observation_count",
        "power_loss_observation_count",
        "application_side_effects_unlocked",
    ]
}

fn parse_accounting_v1(value: &Value) -> AuthorizationResult<ParsedAccountingV1> {
    let object = checked_object(value, &accounting_keys_v1(), "s20b_s17_accounting")?;
    require_u64(
        object,
        "assigned_attempt_denominator_increment",
        1,
        "s20b_s17_accounting",
    )?;
    for key in [
        "provider_observation_count",
        "guest_reboot_observation_count",
        "host_reboot_observation_count",
        "power_loss_observation_count",
    ] {
        require_u64(object, key, 0, "s20b_s17_accounting")?;
    }
    require_text(
        object,
        "application_side_effects_unlocked",
        "NONE",
        "s20b_s17_accounting",
    )?;
    let result = ParsedAccountingV1 {
        sigkill_count: u64_field(
            object,
            "owned_lab_process_sigkill_observation_count",
            "s20b_s17_accounting",
        )?,
        fresh_restart_count: u64_field(
            object,
            "owned_lab_fresh_process_restart_observation_count",
            "s20b_s17_accounting",
        )?,
        phase_count: u64_field(
            object,
            "s16_mapping_phase_record_count",
            "s20b_s17_accounting",
        )?,
        value: value.clone(),
    };
    if result.sigkill_count > 1
        || result.fresh_restart_count > 1
        || !(1..=2).contains(&result.phase_count)
    {
        return Err(validator_error(
            "s20b_s17_accounting",
            "S17 per-assignment accounting is outside its frozen bounds",
        ));
    }
    Ok(result)
}

fn validate_nonclaims_v1(value: &Value) -> AuthorizationResult<()> {
    let keys = [
        "schema_conformance_is_evidence",
        "schema_conformance_alone_proves_cross_field_identity",
        "process_restart_is_service_or_container_restart_proof",
        "process_restart_is_guest_kernel_crash_or_reboot_proof",
        "process_restart_is_host_or_power_loss_proof",
        "same_kernel_read_bypasses_page_cache",
        "kernel_page_cache_loss_proved",
        "host_crash_or_reboot_proved",
        "power_loss_proved",
        "storage_controller_failure_or_flush_proved",
        "storage_device_durability_proved",
        "filesystem_general_durability_proved",
        "database_general_durability_proved",
        "provider_durability_proved",
        "provider_linearizability_or_quorum_proved",
        "witness_independence_proved_by_same_host",
        "rollback_resistance_proved",
        "equivocation_or_split_brain_resistance_proved",
        "currentness_issued",
        "production_admission_granted",
        "production_readiness_proved",
        "bridge_or_state_store_enabled",
        "output_permit_issued",
        "side_effects_unlocked",
    ];
    let object = checked_object(value, &keys, "s20b_s17_nonclaims")?;
    for key in &keys[..keys.len() - 1] {
        require_bool(object, key, false, "s20b_s17_nonclaims")?;
    }
    require_text(
        object,
        "side_effects_unlocked",
        "NONE",
        "s20b_s17_nonclaims",
    )
}

fn expected_hashing_contract_v1() -> Value {
    json!({
        "canonical_json": "RFC8785_JCS",
        "canonical_payload_excludes_identity_and_custody": true,
        "canonical_payload_top_level_fields": [
            "schema",
            "packet_kind",
            "evidence_origin",
            "claim_level",
            "claim_ceiling",
            "hashing_contract",
            "semantic_validation_contract",
            "frozen_bindings",
            "assignment",
            "authorization",
            "storage_environment",
            "crash_observation",
            "restart_observation",
            "raw_recovered_state",
            "mapping_phase_records",
            "accounting",
            "nonclaims"
        ],
        "classification_input_domain_separator": "agent_bridge.s17.owned_lab.classification_input.v0",
        "classification_input_frame_encoding": "RFC8785_OBJECT_WITH_TERMINAL_SOURCE_PATH_COMPONENTS_AS_KEYS",
        "classification_input_frame_fields": [
            "identity.raw_packet_sha256",
            "identity.assignment_id",
            "mapping_phase_record.phase_ordinal",
            "mapping_phase_record.phase_kind",
            "mapping_phase_record.process_identity_sha256",
            "mapping_phase_record.raw_phase_measurement",
            "mapping_phase_record.s16_virtual_projection"
        ],
        "classification_input_hash_scope": "SHA256_UTF8_DOMAIN_NUL_RFC8785_JCS_OF_EXACT_CLASSIFICATION_INPUT_FRAME",
        "custody_entry_hash_scope": "RFC8785_JCS_OF_CUSTODY_OBJECT_WITH_CUSTODY_ENTRY_SHA256_OMITTED",
        "domain_separator": "agent_bridge.s17.owned_lab.observation.v0",
        "hash_algorithm": "SHA-256",
        "observation_id_derivation": "SHA256_DOMAIN_SEPARATOR_RUN_ID_ASSIGNMENT_ID_CANONICAL_PAYLOAD_SHA256",
        "phase_record_domain_separator": "agent_bridge.s17.owned_lab.mapping_phase_record.v0",
        "phase_record_hash_scope": "SHA256_UTF8_DOMAIN_NUL_RFC8785_JCS_OF_MAPPING_PHASE_RECORD_WITH_PHASE_RECORD_SHA256_OMITTED",
        "phase_record_self_hash_excluded": true,
        "raw_packet_hash_scope": "EXTERNAL_RAW_EVENT_STREAM_BYTES_NOT_CONTAINING_THIS_OBSERVATION_JSON",
        "retained_raw_event_frame_hash_scope": "SHA256_OF_EXACT_BYTE_RANGE_AT_OFFSET_AND_LENGTH_IN_EXTERNAL_RAW_EVENT_STREAM",
        "self_referential_fields_excluded": true
    })
}

fn validate_semantic_contract_v1(value: &Value) -> AuthorizationResult<()> {
    let keys = [
        "schema_conformance_alone_proves_cross_field_identity",
        "independent_semantic_validator_required",
        "validator_build_bound_by_owner_decision",
        "required_cross_field_rules",
    ];
    let object = checked_object(value, &keys, "s20b_s17_semantic_contract")?;
    require_bool(
        object,
        "schema_conformance_alone_proves_cross_field_identity",
        false,
        "s20b_s17_semantic_contract",
    )?;
    for key in [
        "independent_semantic_validator_required",
        "validator_build_bound_by_owner_decision",
    ] {
        require_bool(object, key, true, "s20b_s17_semantic_contract")?;
    }
    let reported = field(
        object,
        "required_cross_field_rules",
        "s20b_s17_semantic_contract",
    )?
    .as_array()
    .ok_or_else(|| {
        validator_error(
            "s20b_s17_semantic_contract",
            "S17 semantic rule declaration is not an array",
        )
    })?;
    if reported.len() != S17_CROSS_FIELD_RULES.len()
        || !reported
            .iter()
            .zip(S17_CROSS_FIELD_RULES)
            .all(|(actual, expected)| actual.as_str() == Some(expected))
    {
        return Err(validator_error(
            "s20b_s17_semantic_contract",
            "S17 frozen 32-rule declaration drifted",
        ));
    }
    Ok(())
}

fn canonical_payload_value_v1(root: &Map<String, Value>) -> AuthorizationResult<Value> {
    let mut payload = Map::new();
    for key in [
        "schema",
        "packet_kind",
        "evidence_origin",
        "claim_level",
        "claim_ceiling",
        "hashing_contract",
        "semantic_validation_contract",
        "frozen_bindings",
        "assignment",
        "authorization",
        "storage_environment",
        "crash_observation",
        "restart_observation",
        "raw_recovered_state",
        "mapping_phase_records",
        "accounting",
        "nonclaims",
    ] {
        payload.insert(
            key.into(),
            field(root, key, "s20b_s17_canonical_payload")?.clone(),
        );
    }
    Ok(Value::Object(payload))
}

fn parse_observation_v1(
    canonical_packet: &[u8],
    retained_raw_event_stream: &[u8],
) -> AuthorizationResult<ParsedObservationV1> {
    let value = parse_restricted_canonical(canonical_packet)?;
    let root = checked_object(&value, &TOP_LEVEL_KEYS, "s20b_s17_packet")?;
    for (key, expected) in [
        ("schema", S17_OBSERVATION_SCHEMA),
        ("packet_kind", S17_PACKET_KIND),
        ("evidence_origin", "OWNED_LAB_OBSERVED_RUNTIME"),
        ("claim_level", "L1_PROCESS_CRASH_FRESH_PROCESS_RESTART_ONLY"),
        (
            "claim_ceiling",
            "OWNED_LAB_LOCAL_PROCESS_DEATH_RECOVERY_L1_ONLY_NOT_HOST_POWER_LOSS_NOT_STORAGE_DEVICE_DURABILITY_NOT_PROVIDER_DURABILITY_NOT_ROLLBACK_RESISTANCE",
        ),
    ] {
        require_text(root, key, expected, "s20b_s17_packet")?;
    }
    if field(root, "hashing_contract", "s20b_s17_packet")? != &expected_hashing_contract_v1() {
        return Err(validator_error(
            "s20b_s17_hashing_contract",
            "S17 frozen hash and canonicalization contract drifted",
        ));
    }
    validate_semantic_contract_v1(field(
        root,
        "semantic_validation_contract",
        "s20b_s17_packet",
    )?)?;
    validate_nonclaims_v1(field(root, "nonclaims", "s20b_s17_packet")?)?;
    let identity = parse_identity_v1(field(root, "identity", "s20b_s17_packet")?)?;
    let retained_digest: [u8; 32] = Sha256::digest(retained_raw_event_stream).into();
    if identity.raw_packet_sha256 != retained_digest {
        return Err(validator_error(
            "s20b_s17_raw_packet_digest",
            "retained external raw event stream does not match S17 identity",
        ));
    }
    let canonical_payload_sha256 =
        jcs_domain_digest_v1(S17_OBSERVATION_DOMAIN, &canonical_payload_value_v1(root)?)?;
    if identity.canonical_payload_sha256 != canonical_payload_sha256 {
        return Err(validator_error(
            "s20b_s17_canonical_payload",
            "S17 canonical payload identity does not recompute",
        ));
    }
    if identity.observation_id_sha256
        != observation_id_v1(
            &identity.run_id_sha256,
            &identity.assignment_id_sha256,
            &identity.canonical_payload_sha256,
        )
    {
        return Err(validator_error(
            "s20b_s17_observation_id",
            "S17 observation identifier does not recompute from its frozen domain and identities",
        ));
    }
    let phase_values = field(root, "mapping_phase_records", "s20b_s17_packet")?
        .as_array()
        .ok_or_else(|| {
            validator_error(
                "s20b_s17_phases",
                "S17 mapping phase records are not an array",
            )
        })?;
    if !(1..=2).contains(&phase_values.len()) {
        return Err(validator_error(
            "s20b_s17_phases",
            "S17 observation must contain one or two phases",
        ));
    }
    let phases = phase_values
        .iter()
        .map(parse_phase_v1)
        .collect::<AuthorizationResult<Vec<_>>>()?;
    let accounting = parse_accounting_v1(field(root, "accounting", "s20b_s17_packet")?)?;
    if accounting.phase_count != phases.len() as u64 {
        return Err(validator_error(
            "s20b_s17_accounting",
            "S17 phase-array and accounting denominators differ",
        ));
    }
    Ok(ParsedObservationV1 {
        identity,
        frozen: parse_frozen_bindings_v1(field(root, "frozen_bindings", "s20b_s17_packet")?)?,
        assignment: parse_assignment_labels_v1(field(root, "assignment", "s20b_s17_packet")?)?,
        owner_resource_decision_sha256: parse_authorization_v1(field(
            root,
            "authorization",
            "s20b_s17_packet",
        )?)?,
        storage: parse_storage_v1(field(root, "storage_environment", "s20b_s17_packet")?)?,
        crash: parse_crash_v1(field(root, "crash_observation", "s20b_s17_packet")?)?,
        restart: parse_restart_v1(field(root, "restart_observation", "s20b_s17_packet")?)?,
        recovered: parse_recovered_v1(field(root, "raw_recovered_state", "s20b_s17_packet")?)?,
        phases,
        custody: parse_custody_v1(field(root, "custody", "s20b_s17_packet")?)?,
        accounting,
    })
}

/// Bindings extracted from the independently verified owner/claim receipt.
/// This is data, not authority; only a validated assignment-set member plus
/// the verified S19 subject can turn it into S17 evidence.
pub(super) struct S17OwnerReceiptBindingsV1 {
    pub(super) run_id_sha256: [u8; 32],
    pub(super) assignment_id_sha256: [u8; 32],
    pub(super) owner_resource_decision_sha256: [u8; 32],
    pub(super) assignment_record_sha256: [u8; 32],
    pub(super) operation_set_sha256: [u8; 32],
    pub(super) assignment_set_sha256: [u8; 32],
    pub(super) schedule_sha256: [u8; 32],
    pub(super) assignment_record_set_sha256: [u8; 32],
    pub(super) operation_descriptor_set_sha256: [u8; 32],
    pub(super) resource_scope_sha256: [u8; 32],
    pub(super) classifier_source_sha256: [u8; 32],
    pub(super) classifier_binary_sha256: [u8; 32],
    pub(super) expected_oracle_sha256: [u8; 32],
    pub(super) validator_toolchain_sha256: [u8; 32],
    pub(super) observation_schema_sha256: [u8; 32],
    pub(super) plan_sha256: [u8; 32],
    pub(super) expected_previous_custody_entry_sha256: Option<[u8; 32]>,
}

pub(super) struct S17AssignmentObservationInputV1<'a> {
    pub(super) assignment_ordinal: u64,
    pub(super) owner: S17OwnerReceiptBindingsV1,
    pub(super) canonical_observation_packet: &'a [u8],
    pub(super) retained_raw_event_stream: &'a [u8],
}

pub(super) struct S17BatchInputV1<'a> {
    pub(super) observations: Vec<S17AssignmentObservationInputV1<'a>>,
    pub(super) successful_claim_count: u64,
    pub(super) retry_count: u64,
}

enum ValidatedCatalogMappingV1 {
    Zero,
    Unique {
        case_id: String,
        variant_id: String,
        row_sha256: [u8; 32],
    },
    Multiple {
        multiplicity: usize,
    },
}

/// Private affine semantic evidence.  Intentionally no Clone, Copy, Serialize,
/// Deserialize, public constructor, or public fields.
#[must_use]
struct ValidatedS17PhaseV1 {
    assignment_ordinal: u64,
    assignment_id_sha256: [u8; 32],
    observation_id_sha256: [u8; 32],
    phase_ordinal: u64,
    phase_kind: ParsedPhaseKindV1,
    phase_record_sha256: [u8; 32],
    mapping: ValidatedCatalogMappingV1,
}

struct PhaseScanContextV1<'a> {
    derived_projection: S16ProjectionV1,
    decoded_raw_frame: RawLifecycleFrameV1,
    exact_frame_sha256: [u8; 32],
    scan: FullCatalogScanV1<'a>,
}

fn scan_phase_from_retained_raw_v1<'a>(
    phase: &ParsedPhaseV1,
    retained_raw_event_stream: &[u8],
    rows: &'a [FrozenS16RowV1],
) -> AuthorizationResult<PhaseScanContextV1<'a>> {
    let start = usize::try_from(phase.raw.raw_event_frame_offset_bytes).map_err(|_| {
        validator_error(
            "s20b_s17_raw_frame_range",
            "S17 raw frame offset is not representable",
        )
    })?;
    let length = usize::try_from(phase.raw.raw_event_frame_length_bytes).map_err(|_| {
        validator_error(
            "s20b_s17_raw_frame_range",
            "S17 raw frame length is not representable",
        )
    })?;
    let end = start.checked_add(length).ok_or_else(|| {
        validator_error(
            "s20b_s17_raw_frame_range",
            "S17 raw frame byte range overflows",
        )
    })?;
    let frame = retained_raw_event_stream.get(start..end).ok_or_else(|| {
        validator_error(
            "s20b_s17_raw_frame_range",
            "S17 raw frame byte range is outside the retained stream",
        )
    })?;
    let exact_frame_sha256: [u8; 32] = Sha256::digest(frame).into();
    let decoded_value = parse_restricted_canonical(frame).map_err(|_| {
        validator_error(
            "s20b_s17_raw_frame_decode",
            "retained S17 raw lifecycle frame is not exact canonical JSON",
        )
    })?;
    let decoded_raw_frame = parse_raw_lifecycle_v1(&decoded_value)?;
    let derived_projection = derive_projection_v1(&decoded_raw_frame);
    let scan = scan_full_catalog_v1(rows, &derived_projection);
    Ok(PhaseScanContextV1 {
        derived_projection,
        decoded_raw_frame,
        exact_frame_sha256,
        scan,
    })
}

fn direct_database_child_v1(storage: &ParsedStorageV1) -> bool {
    !storage.database_relative_path.is_empty()
        && !storage.database_relative_path.contains('/')
        && storage.database_relative_path.ends_with(".sqlite3")
        && storage.database_canonical_path
            == format!(
                "{}/{}",
                storage.canonical_root, storage.database_relative_path
            )
}

fn raw_durable_image_v1(raw: &RawLifecycleFrameV1) -> DurableImageV1 {
    DurableImageV1 {
        object_state: raw.object_state.clone(),
        object_len: Some(raw.object_len),
        object_sha256: raw.object_sha256,
        receipt_state: raw.receipt_state.clone(),
        receipt_sha256: raw.stored_receipt_sha256,
        witness_state: raw.witness_state.clone(),
        witness_sha256: raw.stored_witness_sha256,
        selected_view_state: raw.selected_view_state.clone(),
        selected_view_sha256: raw.selected_view_sha256,
        competing_view_state: raw.competing_view_state.clone(),
        competing_view_sha256: raw.competing_view_sha256,
    }
}

fn custody_entry_recomputes_v1(custody: &ParsedCustodyV1) -> AuthorizationResult<bool> {
    let mut value = custody
        .value
        .as_object()
        .cloned()
        .ok_or_else(|| validator_error("s20b_s17_custody", "parsed custody object was lost"))?;
    value.remove("custody_entry_sha256").ok_or_else(|| {
        validator_error(
            "s20b_s17_custody",
            "custody self digest was absent before exclusion",
        )
    })?;
    Ok(plain_jcs_digest_v1(&Value::Object(value))? == custody.entry_sha256)
}

fn owner_binding_valid_v1(
    observation: &ParsedObservationV1,
    member: &ValidatedAuthorizedAssignmentMemberV1,
    owner: &S17OwnerReceiptBindingsV1,
    authorized_set: &ValidatedAuthorizedAssignmentSetV1,
    subject: &VerifiedS19SubjectV1,
) -> bool {
    observation.identity.run_id_sha256 == owner.run_id_sha256
        && observation.identity.assignment_id_sha256 == owner.assignment_id_sha256
        && owner.assignment_id_sha256 == member.assignment_id_sha256
        && observation.owner_resource_decision_sha256 == owner.owner_resource_decision_sha256
        && owner.assignment_record_sha256 == member.assignment_record_sha256
        && owner.operation_set_sha256 == member.operation_set_sha256
        && owner.assignment_set_sha256 == authorized_set.assignment_set_sha256
        && owner.schedule_sha256 == authorized_set.schedule_sha256
        && owner.assignment_set_sha256 == subject.assignment_set_sha256
        && owner.schedule_sha256 == subject.schedule_sha256
        && owner.assignment_record_set_sha256 == authorized_set.assignment_record_set_sha256
        && owner.operation_descriptor_set_sha256 == authorized_set.operation_descriptor_set_sha256
        && owner.resource_scope_sha256 == subject.resource_scope_sha256
        && owner.classifier_source_sha256 == subject.classifier_source_sha256
        && owner.classifier_binary_sha256 == subject.classifier_binary_sha256
        && owner.expected_oracle_sha256 == subject.expected_oracle_sha256
        && owner.validator_toolchain_sha256 == observation.frozen.toolchain_sha256
        && owner.observation_schema_sha256 == subject.s17_observation_schema_sha256
        && owner.plan_sha256 == subject.s17_plan_sha256
}

fn frozen_subject_bindings_valid_v1(
    observation: &ParsedObservationV1,
    owner: &S17OwnerReceiptBindingsV1,
    subject: &VerifiedS19SubjectV1,
) -> bool {
    observation.frozen.s16_catalog_sha256 == subject.catalog_sha256
        && observation.frozen.s16_catalog_message_len == S16_CATALOG_MESSAGE_LEN
        && observation.frozen.base_record_sha256
            == super::super::super::super::super::CANONICAL_RECORD_SHA256
        && observation.frozen.base_record_len == S16_BASE_RECORD_LEN
        && observation.frozen.lookup_commitment_sha256
            == super::super::super::super::super::LOOKUP_COMMITMENT_SHA256
        && observation.frozen.plan_sha256 == subject.s17_plan_sha256
        && observation.frozen.plan_sha256 == owner.plan_sha256
        && subject.s17_plan_sha256 == S17_PLAN_RAW_SHA256
        && subject.s17_observation_schema_sha256 == S17_OBSERVATION_SCHEMA_RAW_SHA256
        && observation.frozen.runner_binary_sha256 == subject.runner_binary_sha256
        && observation.frozen.classifier_source_sha256 == subject.classifier_source_sha256
        && observation.frozen.classifier_binary_sha256 == subject.classifier_binary_sha256
        && observation.frozen.expected_oracle_sha256 == subject.expected_oracle_sha256
        && observation.frozen.sqlite_profile_sha256 == subject.sqlite_profile_sha256
        && observation.frozen.sqlite_schema_sha256 == subject.sqlite_schema_sha256
}

fn expected_row_identity_v1(
    member: &ValidatedAuthorizedAssignmentMemberV1,
    phase_kind: ParsedPhaseKindV1,
) -> AuthorizationResult<(&str, String)> {
    match (member.family_id.as_str(), phase_kind) {
        ("OL00", ParsedPhaseKindV1::AttemptResult) => Ok((member.case_id.as_str(), "CLEAN".into())),
        ("OL04", ParsedPhaseKindV1::AttemptResult) => {
            Ok((member.case_id.as_str(), member.variant_id.clone()))
        }
        ("OL05", ParsedPhaseKindV1::FirstAttempt) => Ok((
            member.case_id.as_str(),
            format!("{}_FIRST_ATTEMPT", member.variant_id),
        )),
        ("OL05", ParsedPhaseKindV1::Restart) => Ok((
            member.case_id.as_str(),
            format!("{}_RESTART", member.variant_id),
        )),
        _ => Err(validator_error(
            "s20b_s17_assignment_phase",
            "owner-bound assignment and observed phase kind are inconsistent",
        )),
    }
}

fn assignment_labels_match_after_scan_v1(
    observation: &ParsedObservationV1,
    member: &ValidatedAuthorizedAssignmentMemberV1,
    phase: &ParsedPhaseV1,
    scan: &FullCatalogScanV1<'_>,
) -> AuthorizationResult<bool> {
    let FullCatalogScanV1::One { row, .. } = scan else {
        // There is no row identity to compare for a retained indeterminate
        // classification.  This is intentionally not a successful match.
        return Ok(false);
    };
    let (expected_case, expected_variant) = expected_row_identity_v1(member, phase.phase_kind)?;
    Ok(observation.assignment.family_id == member.family_id
        && observation.assignment.case_id == member.case_id
        && observation.assignment.variant_id == member.variant_id
        && observation.assignment.read_quantum_bytes
            == if member.family_id == "OL05" {
                Some(S16_READ_QUANTUM)
            } else {
                None
            }
        && row.case_id == expected_case
        && row.variant_id.as_ref() == expected_variant)
}

fn d05_lifecycle_relation_v1(raw: &RawLifecycleFrameV1, phase: ParsedPhaseKindV1) -> bool {
    let expected_length = (raw.observed_data_steps * S16_READ_QUANTUM).min(S16_BASE_RECORD_LEN);
    if raw.observed_len != expected_length || raw.publisher_phase != "ACKED" {
        return false;
    }
    if phase == ParsedPhaseKindV1::Restart {
        return raw.restarted_after_crash
            && raw.observed_data_steps == S16_DATA_STEPS
            && raw.observed_len == S16_BASE_RECORD_LEN
            && raw.adapter_pre_state == "FRESH"
            && raw.adapter_post_state == "COMPLETED";
    }
    if phase != ParsedPhaseKindV1::FirstAttempt || raw.restarted_after_crash {
        return false;
    }
    match raw.crash_cut.as_str() {
        "READ_BEFORE_OPEN" => {
            raw.crash_cut_index == 0
                && raw.observed_data_steps == 0
                && raw.adapter_pre_state == "FRESH"
                && raw.adapter_post_state == "FRESH"
        }
        "READ_AFTER_OPEN" => {
            raw.crash_cut_index == 0
                && raw.observed_data_steps == 0
                && raw.adapter_pre_state == "STREAMING"
                && raw.adapter_post_state == "TERMINAL_FAILED"
        }
        "READ_AFTER_DATA" => {
            (1..=S16_DATA_STEPS).contains(&raw.crash_cut_index)
                && raw.observed_data_steps == raw.crash_cut_index
                && raw.adapter_pre_state == "STREAMING"
                && raw.adapter_post_state == "TERMINAL_FAILED"
        }
        "READ_AFTER_COMPLETE_BEFORE_S14" => {
            raw.crash_cut_index == 0
                && raw.observed_data_steps == S16_DATA_STEPS
                && raw.adapter_pre_state == "STREAMING"
                && raw.adapter_post_state == "COMPLETED"
        }
        "READ_AFTER_HISTORICAL" => {
            raw.crash_cut_index == 0
                && raw.observed_data_steps == S16_DATA_STEPS
                && raw.adapter_pre_state == "COMPLETED"
                && raw.adapter_post_state == "COMPLETED"
        }
        _ => false,
    }
}

fn validate_post_scan_assignment_shape_v1(
    observation: &ParsedObservationV1,
    member: &ValidatedAuthorizedAssignmentMemberV1,
    scans: &[PhaseScanContextV1<'_>],
) -> AuthorizationResult<()> {
    // This function is called only after all label-free scans have completed.
    if observation.phases.len() != member.phase_count as usize
        || scans.len() != observation.phases.len()
    {
        return Err(validator_error(
            "s20b_s17_assignment_shape",
            "owner-bound assignment phase denominator drifted",
        ));
    }
    let expected_kinds: &[ParsedPhaseKindV1] = match member.family_id.as_str() {
        "OL00" | "OL04" => &[ParsedPhaseKindV1::AttemptResult],
        "OL05" => &[ParsedPhaseKindV1::FirstAttempt, ParsedPhaseKindV1::Restart],
        _ => {
            return Err(validator_error(
                "s20b_s17_assignment_shape",
                "owner-bound assignment family is outside OL00/OL04/OL05",
            ))
        }
    };
    if !observation
        .phases
        .iter()
        .zip(expected_kinds)
        .enumerate()
        .all(|(index, (phase, expected_kind))| {
            phase.phase_ordinal == index as u64 + 1
                && phase.phase_kind == *expected_kind
                && phase.raw.raw_event_frame_index == index as u64
        })
    {
        return Err(validator_error(
            "s20b_s17_assignment_shape",
            "S17 phase ordinal, kind, or raw-frame index drifted",
        ));
    }
    for adjacent in observation.phases.windows(2) {
        let first_end = adjacent[0]
            .raw
            .raw_event_frame_offset_bytes
            .checked_add(adjacent[0].raw.raw_event_frame_length_bytes);
        if first_end.is_none_or(|end| end > adjacent[1].raw.raw_event_frame_offset_bytes) {
            return Err(validator_error(
                "s20b_s17_raw_frame_order",
                "S17 phase raw frames overlap or are out of order",
            ));
        }
    }
    let family_shape = match member.family_id.as_str() {
        "OL00" => {
            observation.crash.control_shape_valid
                && observation.restart.is_none()
                && observation.accounting.sigkill_count == 0
                && observation.accounting.fresh_restart_count == 0
                && observation.accounting.phase_count == 1
        }
        "OL04" => {
            observation.crash.pidfd_shape_valid
                && observation.restart.is_some()
                && observation.accounting.sigkill_count == 1
                && observation.accounting.fresh_restart_count == 1
                && observation.accounting.phase_count == 1
        }
        "OL05" => {
            observation.crash.pidfd_shape_valid
                && observation.restart.is_some()
                && observation.accounting.sigkill_count == 1
                && observation.accounting.fresh_restart_count == 1
                && observation.accounting.phase_count == 2
        }
        _ => false,
    };
    if !family_shape {
        return Err(validator_error(
            "s20b_s17_assignment_shape",
            "S17 crash/restart/accounting shape contradicts the owner-bound family",
        ));
    }
    Ok(())
}

fn paired_cut_valid_v1(
    observation: &ParsedObservationV1,
    member: &ValidatedAuthorizedAssignmentMemberV1,
) -> bool {
    if member.family_id != "OL05" {
        return true;
    }
    observation.phases.len() == 2
        && observation.phases[0].raw.lifecycle.crash_cut
            == observation.phases[1].raw.lifecycle.crash_cut
        && observation.phases[0].raw.lifecycle.crash_cut_index
            == observation.phases[1].raw.lifecycle.crash_cut_index
        && observation.phases[0].raw.retained_raw_event_stream_sha256
            == observation.phases[1].raw.retained_raw_event_stream_sha256
}

fn validate_phase_32_rules_v1(
    observation: &ParsedObservationV1,
    phase: &ParsedPhaseV1,
    context: &PhaseScanContextV1<'_>,
    member: &ValidatedAuthorizedAssignmentMemberV1,
    owner: &S17OwnerReceiptBindingsV1,
    authorized_set: &ValidatedAuthorizedAssignmentSetV1,
    subject: &VerifiedS19SubjectV1,
    paired_cut_valid: bool,
) -> AuthorizationResult<ValidatedS17PhaseV1> {
    let initial_process = (observation.crash.child_pid, observation.crash.child_start);
    let controller_process = (
        observation.crash.controller_pid,
        observation.crash.controller_start,
    );

    // 1. pidfd target identity.
    cross_rule_v1(
        0,
        if member.family_id == "OL00" {
            observation.crash.pidfd_target_pid.is_none()
                && observation.crash.pidfd_target_start.is_none()
        } else {
            observation
                .crash
                .pidfd_target_pid
                .zip(observation.crash.pidfd_target_start)
                == Some(initial_process)
        },
    )?;
    // 2. signal sender identity.
    let controller_distinct_from_child = controller_process != initial_process
        && observation.crash.controller_process_identity_sha256
            != observation.crash.child_process_identity_sha256;
    cross_rule_v1(
        1,
        controller_distinct_from_child
            && if member.family_id == "OL00" {
                observation.crash.signal_sender_pid.is_none()
                    && observation.crash.signal_sender_start.is_none()
            } else {
                observation
                    .crash
                    .signal_sender_pid
                    .zip(observation.crash.signal_sender_start)
                    == Some(controller_process)
            },
    )?;
    // 3. fresh process and nonce are distinct.
    cross_rule_v1(
        2,
        match &observation.restart {
            None => member.family_id == "OL00",
            Some(restart) => {
                (restart.fresh_pid, restart.fresh_start) != initial_process
                    && restart.fresh_process_identity_sha256
                        != observation.crash.child_process_identity_sha256
                    && restart.fresh_nonce_sha256 != observation.crash.child_nonce_sha256
            }
        },
    )?;
    // 4. both exec images bind the frozen runner.
    cross_rule_v1(
        3,
        observation.crash.child_image_sha256 == observation.frozen.runner_binary_sha256
            && observation.crash.child_image_sha256 == subject.runner_binary_sha256
            && observation.restart.as_ref().is_none_or(|restart| {
                restart.fresh_image_sha256 == observation.frozen.runner_binary_sha256
            }),
    )?;
    // 5. same-boot proof is equality, not a candidate boolean.
    cross_rule_v1(
        4,
        observation.storage.boot_id_before_sha256 == observation.storage.boot_id_after_sha256
            && observation.storage.boot_id_before_sha256 == subject.boot_id_sha256,
    )?;
    // 6. run-root identity stability.
    cross_rule_v1(
        5,
        observation.storage.root_before_sha256 == observation.storage.root_after_sha256,
    )?;
    // 7. mountinfo identity stability.
    cross_rule_v1(
        6,
        observation.storage.mountinfo_before_sha256 == observation.storage.mountinfo_after_sha256,
    )?;
    // 8. exact direct-child database path.
    cross_rule_v1(7, direct_database_child_v1(&observation.storage))?;
    // 9. database identity stability.
    cross_rule_v1(
        8,
        observation.storage.database_identity_before_sha256
            == observation.storage.database_identity_after_sha256,
    )?;
    // 10. SQLite profile and schema bind the verified subject.
    cross_rule_v1(
        9,
        observation.storage.sqlite_profile_sha256 == observation.frozen.sqlite_profile_sha256
            && observation.storage.sqlite_profile_sha256 == subject.sqlite_profile_sha256
            && observation.storage.sqlite_schema_sha256 == observation.frozen.sqlite_schema_sha256
            && observation.storage.sqlite_schema_sha256 == subject.sqlite_schema_sha256,
    )?;
    // 11. custody identities bind independently recomputed packet identities.
    cross_rule_v1(
        10,
        observation.custody.raw_evidence_sha256 == observation.identity.raw_packet_sha256
            && observation.custody.canonical_evidence_sha256
                == observation.identity.canonical_payload_sha256,
    )?;
    // 12. exact retained byte-range hash.
    cross_rule_v1(
        11,
        phase.raw.retained_raw_event_stream_sha256 == observation.identity.raw_packet_sha256
            && context.exact_frame_sha256 == phase.raw.raw_event_frame_sha256,
    )?;
    // 13. typed packet measurement was decoded from that frame.
    cross_rule_v1(12, context.decoded_raw_frame == phase.raw.lifecycle)?;
    // 14. acknowledgement payload binds the independently matched row.
    let ack_binding = match &context.scan {
        FullCatalogScanV1::One { row, .. } => {
            (
                context.decoded_raw_frame.ack_receipt_sha256,
                context.decoded_raw_frame.ack_witness_sha256,
            ) == expected_ack_payload_from_row_v1(row)
        }
        FullCatalogScanV1::Zero { .. } | FullCatalogScanV1::Multiple { .. } => {
            (context.decoded_raw_frame.ack_state == "OBSERVED")
                == (context.decoded_raw_frame.ack_receipt_sha256.is_some()
                    && context.decoded_raw_frame.ack_witness_sha256.is_some())
        }
    };
    cross_rule_v1(13, ack_binding)?;
    // 15. projection is derived, never accepted as an oracle.
    cross_rule_v1(14, phase.reported_projection == context.derived_projection)?;
    // 16. virtual counters stay zero and are a distinct domain from S17 accounting.
    let projection_digest = plain_jcs_digest_v1(&projection_value_v1(&context.derived_projection))?;
    let accounting_digest = plain_jcs_digest_v1(&observation.accounting.value)?;
    cross_rule_v1(
        15,
        context
            .derived_projection
            .external_durability_observation_count
            == 0
            && context
                .derived_projection
                .provider_durability_observation_count
                == 0
            && context
                .derived_projection
                .owned_lab_durability_observation_count
                == 0
            && context.derived_projection.side_effects_unlocked == "NONE"
            && projection_digest != accounting_digest,
    )?;
    // 17. classification input uses the exact frozen JCS/NUL frame.
    let classification_input = jcs_domain_digest_v1(
        S17_CLASSIFICATION_DOMAIN,
        &classification_input_value_v1(
            observation.identity.raw_packet_sha256,
            observation.identity.assignment_id_sha256,
            phase,
        )?,
    )?;
    cross_rule_v1(
        16,
        phase.classification_input_sha256 == classification_input,
    )?;
    // 18. phase self hash is omitted and recomputed under a separate domain.
    cross_rule_v1(
        17,
        phase.phase_record_sha256 == recompute_phase_record_v1(phase)?,
    )?;
    // 19. classifier source/build/oracle bind both subject and owner receipt.
    cross_rule_v1(
        18,
        phase.reported_classification.classifier_build_sha256
            == observation.frozen.classifier_binary_sha256
            && observation.frozen.classifier_binary_sha256 == subject.classifier_binary_sha256
            && observation.frozen.classifier_binary_sha256 == owner.classifier_binary_sha256
            && observation.frozen.classifier_source_sha256 == subject.classifier_source_sha256
            && observation.frozen.classifier_source_sha256 == owner.classifier_source_sha256
            && observation.frozen.expected_oracle_sha256 == subject.expected_oracle_sha256
            && observation.frozen.expected_oracle_sha256 == owner.expected_oracle_sha256,
    )?;
    // 20. exact lifecycle evaluator plus complete catalog result.
    let reported_scan_valid = match &context.scan {
        FullCatalogScanV1::One { row, .. } => {
            reported_unique_equals_row_v1(&phase.reported_classification, row)
        }
        scan @ (FullCatalogScanV1::Zero { .. } | FullCatalogScanV1::Multiple { .. }) => {
            reported_indeterminate_v1(&phase.reported_classification, scan)
        }
    };
    cross_rule_v1(19, context.scan.scanned() == 5_639 && reported_scan_valid)?;
    // 21. the scan API has no assignment fields; its mechanically checked
    // guarantee is that every row was visited.
    cross_rule_v1(20, context.scan.scanned() == 5_639)?;
    // 22. only now, after the scan, consult owner-authorized labels.
    let post_scan_label_match =
        assignment_labels_match_after_scan_v1(observation, member, phase, &context.scan)?;
    cross_rule_v1(
        21,
        !matches!(context.scan, FullCatalogScanV1::One { .. }) || post_scan_label_match,
    )?;
    // 23. unique row identity, reason, failure and commitment are recomputed.
    cross_rule_v1(22, reported_scan_valid)?;
    // 24. domain-separated S16 absent sentinels never appear as raw facts.
    cross_rule_v1(23, !raw_contains_absent_sentinel_v1(&phase.raw.lifecycle))?;
    // 25. lifecycle relation for the bound family.
    let lifecycle_valid = match member.family_id.as_str() {
        "OL05" => d05_lifecycle_relation_v1(&phase.raw.lifecycle, phase.phase_kind),
        "OL04" => {
            phase.raw.lifecycle.restarted_after_crash
                && phase.raw.lifecycle.observed_data_steps == 0
                && phase.raw.lifecycle.observed_len == 0
        }
        "OL00" => {
            !phase.raw.lifecycle.restarted_after_crash
                && phase.raw.lifecycle.observed_data_steps == 0
                && phase.raw.lifecycle.observed_len == 0
        }
        _ => false,
    };
    cross_rule_v1(24, lifecycle_valid)?;
    // 26. D05 phase pair binds one attempt/cut.
    cross_rule_v1(25, paired_cut_valid)?;
    // 27. every phase durable image binds the packet top-level image.
    cross_rule_v1(
        26,
        raw_durable_image_v1(&phase.raw.lifecycle) == observation.recovered,
    )?;
    // 28. first-attempt process is the killed child.
    cross_rule_v1(
        27,
        phase.phase_kind != ParsedPhaseKindV1::FirstAttempt
            || phase.process_identity_sha256 == observation.crash.child_process_identity_sha256,
    )?;
    // 29. restart process is the fresh exec child.
    cross_rule_v1(
        28,
        phase.phase_kind != ParsedPhaseKindV1::Restart
            || observation.restart.as_ref().is_some_and(|restart| {
                phase.process_identity_sha256 == restart.fresh_process_identity_sha256
            }),
    )?;
    // 30. single phase process is the independently eligible result process.
    let eligible_result_process = match member.family_id.as_str() {
        "OL00" => Some(observation.crash.child_process_identity_sha256),
        "OL04" => observation
            .restart
            .as_ref()
            .map(|restart| restart.fresh_process_identity_sha256),
        _ => None,
    };
    cross_rule_v1(
        29,
        phase.phase_kind != ParsedPhaseKindV1::AttemptResult
            || eligible_result_process == Some(phase.process_identity_sha256),
    )?;
    // 31. custody entry and predecessor relation recompute.
    cross_rule_v1(
        30,
        custody_entry_recomputes_v1(&observation.custody)?
            && observation.custody.previous_sha256 == owner.expected_previous_custody_entry_sha256
            && ((observation.custody.sequence == 1
                && observation.custody.previous_sha256.is_none())
                || (observation.custody.sequence > 1
                    && observation.custody.previous_sha256.is_some())),
    )?;
    // 32. verified owner receipt, assignment, resources and safety tuple.
    cross_rule_v1(
        31,
        owner_binding_valid_v1(observation, member, owner, authorized_set, subject)
            && frozen_subject_bindings_valid_v1(observation, owner, subject),
    )?;

    let mapping = match &context.scan {
        FullCatalogScanV1::Zero { .. } => ValidatedCatalogMappingV1::Zero,
        FullCatalogScanV1::One { row, .. } => ValidatedCatalogMappingV1::Unique {
            case_id: row.case_id.into(),
            variant_id: row.variant_id.to_string(),
            row_sha256: super::super::super::super::super::row_commitment_v1(row),
        },
        FullCatalogScanV1::Multiple { multiplicity, .. } => ValidatedCatalogMappingV1::Multiple {
            multiplicity: *multiplicity,
        },
    };
    Ok(ValidatedS17PhaseV1 {
        assignment_ordinal: member.ordinal,
        assignment_id_sha256: member.assignment_id_sha256,
        observation_id_sha256: observation.identity.observation_id_sha256,
        phase_ordinal: phase.phase_ordinal,
        phase_kind: phase.phase_kind,
        phase_record_sha256: phase.phase_record_sha256,
        mapping,
    })
}

struct ValidatedAssignmentObservationV1 {
    assignment_ordinal: u64,
    assignment_record_sha256: [u8; 32],
    family_id: String,
    observation_id_sha256: [u8; 32],
    custody_sequence: u64,
    custody_entry_sha256: [u8; 32],
    sigkill_count: u64,
    fresh_restart_count: u64,
    phases: Vec<ValidatedS17PhaseV1>,
}

fn validate_assignment_observation_v1(
    input: &S17AssignmentObservationInputV1<'_>,
    member: ValidatedAuthorizedAssignmentMemberV1,
    authorized_set: &ValidatedAuthorizedAssignmentSetV1,
    subject: &VerifiedS19SubjectV1,
    rows: &[FrozenS16RowV1],
) -> AuthorizationResult<ValidatedAssignmentObservationV1> {
    let observation = parse_observation_v1(
        input.canonical_observation_packet,
        input.retained_raw_event_stream,
    )?;
    // The complete label-free scan of every phase happens before the member's
    // family/case/variant is read by any comparison.
    let scans = observation
        .phases
        .iter()
        .map(|phase| scan_phase_from_retained_raw_v1(phase, input.retained_raw_event_stream, rows))
        .collect::<AuthorizationResult<Vec<_>>>()?;
    validate_post_scan_assignment_shape_v1(&observation, &member, &scans)?;
    let paired_cut_valid = paired_cut_valid_v1(&observation, &member);
    let phases = observation
        .phases
        .iter()
        .zip(&scans)
        .map(|(phase, scan)| {
            validate_phase_32_rules_v1(
                &observation,
                phase,
                scan,
                &member,
                &input.owner,
                authorized_set,
                subject,
                paired_cut_valid,
            )
        })
        .collect::<AuthorizationResult<Vec<_>>>()?;
    Ok(ValidatedAssignmentObservationV1 {
        assignment_ordinal: member.ordinal,
        assignment_record_sha256: member.assignment_record_sha256,
        family_id: member.family_id,
        observation_id_sha256: observation.identity.observation_id_sha256,
        custody_sequence: observation.custody.sequence,
        custody_entry_sha256: observation.custody.entry_sha256,
        sigkill_count: observation.accounting.sigkill_count,
        fresh_restart_count: observation.accounting.fresh_restart_count,
        phases,
    })
}

#[must_use]
pub(super) struct S17PostRunAccountingV1 {
    pub(super) catalog_sha256: [u8; 32],
    pub(super) classifier_source_sha256: [u8; 32],
    pub(super) classifier_binary_sha256: [u8; 32],
    pub(super) expected_oracle_sha256: [u8; 32],
    pub(super) validator_toolchain_sha256: [u8; 32],
    pub(super) observation_schema_sha256: [u8; 32],
    pub(super) plan_sha256: [u8; 32],
    pub(super) validator_ruleset_sha256: [u8; 32],
    pub(super) full_catalog_row_count: u64,
    pub(super) cross_field_rule_count: u64,
    pub(super) assignment_count: u64,
    pub(super) ol00_assignment_count: u64,
    pub(super) ol04_assignment_count: u64,
    pub(super) ol05_assignment_count: u64,
    pub(super) pidfd_sigkill_count: u64,
    pub(super) fresh_exec_count: u64,
    pub(super) validated_phase_count: u64,
    pub(super) unique_match_count: u64,
    pub(super) zero_match_count: u64,
    pub(super) multiple_match_count: u64,
    pub(super) successful_claim_count: u64,
    pub(super) retry_count: u64,
    pub(super) assignment_prefilter_used: bool,
    pub(super) assignment_set_sha256: [u8; 32],
    pub(super) schedule_sha256: [u8; 32],
    pub(super) assignment_record_set_sha256: [u8; 32],
    pub(super) operation_descriptor_set_sha256: [u8; 32],
    pub(super) observation_count: u64,
    pub(super) observation_set_sha256: [u8; 32],
    pub(super) phase_record_set_count: u64,
    pub(super) phase_record_set_sha256: [u8; 32],
}

/// Private batch evidence for the post-run packet adapter.  It is affine and
/// has no serialization surface.
#[must_use]
pub(super) struct ValidatedS17BatchV1 {
    accounting: S17PostRunAccountingV1,
}

impl ValidatedS17BatchV1 {
    pub(super) fn accounting(&self) -> &S17PostRunAccountingV1 {
        &self.accounting
    }
}

fn validator_ruleset_digest_v1() -> AuthorizationResult<[u8; 32]> {
    let fields: Vec<&[u8]> = S17_CROSS_FIELD_RULES
        .iter()
        .map(|rule| rule.as_bytes())
        .collect();
    framed_digest(
        b"agent-bridge/biocortex/owned-lab/s20b/s17-32-rule-set/v1",
        &fields,
    )
}

fn exact_batch_header_v1(
    assignment_count: usize,
    successful_claim_count: u64,
    retry_count: u64,
    assignment_set_sha256: [u8; 32],
    schedule_sha256: [u8; 32],
    authorized: &AuthorizedUnclaimedS19SubjectV1,
) -> bool {
    let subject = &authorized.subject;
    assignment_count == 60
        && successful_claim_count == 1
        && retry_count == 0
        && assignment_set_sha256 == subject.assignment_set_sha256
        && schedule_sha256 == subject.schedule_sha256
}

pub(super) fn validate_s17_batch_v1(
    authorized: &AuthorizedUnclaimedS19SubjectV1,
    authorized_set: &ValidatedAuthorizedAssignmentSetV1,
    canonical_base_record: &[u8],
    input: S17BatchInputV1<'_>,
) -> AuthorizationResult<ValidatedS17BatchV1> {
    if !authorized_set.matches_authorized_subject_v1(authorized) {
        return Err(validator_error(
            "s20b_s17_authorized_subject_binding",
            "S17 assignment authority token belongs to a different owner authorization or subject",
        ));
    }
    let subject = &authorized.subject;
    if !exact_batch_header_v1(
        input.observations.len(),
        input.successful_claim_count,
        input.retry_count,
        authorized_set.assignment_set_sha256,
        authorized_set.schedule_sha256,
        authorized,
    ) {
        return Err(validator_error(
            "s20b_s17_batch_cardinality",
            "S17 batch assignment, claim, retry, or owner-root cardinality drifted",
        ));
    }
    let exact_record_digests: Vec<[u8; 32]> = authorized_set.exact_record_digests().collect();
    if !input
        .observations
        .iter()
        .enumerate()
        .zip(&exact_record_digests)
        .all(|((index, observation), expected_record)| {
            observation.assignment_ordinal == index as u64 + 1
                && observation.owner.assignment_record_sha256 == *expected_record
        })
    {
        return Err(validator_error(
            "s20b_s17_batch_assignment_order",
            "S17 batch is not the exact ordered 1..=60 owner-bound assignment set",
        ));
    }
    let run_ids: BTreeSet<[u8; 32]> = input
        .observations
        .iter()
        .map(|observation| observation.owner.run_id_sha256)
        .collect();
    if run_ids.len() != 1 {
        return Err(validator_error(
            "s20b_s17_batch_run",
            "S17 batch observations do not bind one exact run",
        ));
    }
    let validator_toolchains: BTreeSet<[u8; 32]> = input
        .observations
        .iter()
        .map(|observation| observation.owner.validator_toolchain_sha256)
        .collect();
    if validator_toolchains.len() != 1 {
        return Err(validator_error(
            "s20b_s17_batch_toolchain",
            "S17 batch does not bind one owner-frozen validator toolchain",
        ));
    }
    let rows = build_verified_catalog_v1(canonical_base_record, subject)?;
    let mut validated = Vec::with_capacity(60);
    for observation in &input.observations {
        let member = authorized_set.member(
            observation.assignment_ordinal,
            observation.owner.assignment_record_sha256,
        )?;
        validated.push(validate_assignment_observation_v1(
            observation,
            member,
            authorized_set,
            subject,
            &rows,
        )?);
    }
    let mut previous_custody = None;
    for (index, observation) in validated.iter().enumerate() {
        if observation.assignment_ordinal != index as u64 + 1
            || observation.custody_sequence != index as u64 + 1
            || input.observations[index]
                .owner
                .expected_previous_custody_entry_sha256
                != previous_custody
        {
            return Err(validator_error(
                "s20b_s17_batch_custody_order",
                "S17 batch custody or assignment sequence has a gap/fork/reorder",
            ));
        }
        previous_custody = Some(observation.custody_entry_sha256);
    }

    let family_count = |family: &str| {
        validated
            .iter()
            .filter(|observation| observation.family_id == family)
            .count() as u64
    };
    let assignment_ids: BTreeSet<[u8; 32]> = validated
        .iter()
        .flat_map(|observation| {
            observation
                .phases
                .first()
                .map(|phase| phase.assignment_id_sha256)
        })
        .collect();
    let assignment_records: BTreeSet<[u8; 32]> = validated
        .iter()
        .map(|observation| observation.assignment_record_sha256)
        .collect();
    let observation_ids: BTreeSet<[u8; 32]> = validated
        .iter()
        .map(|observation| observation.observation_id_sha256)
        .collect();
    let phases: Vec<&ValidatedS17PhaseV1> = validated
        .iter()
        .flat_map(|observation| observation.phases.iter())
        .collect();
    let phase_records: BTreeSet<[u8; 32]> = phases
        .iter()
        .map(|phase| phase.phase_record_sha256)
        .collect();
    let ordered_phase_shape = phases.iter().enumerate().all(|(phase_index, phase)| {
        let expected_assignment = if phase_index < 7 {
            phase_index as u64 + 1
        } else {
            8 + ((phase_index - 7) / 2) as u64
        };
        let expected_phase_ordinal = if phase_index < 7 {
            1
        } else {
            ((phase_index - 7) % 2) as u64 + 1
        };
        phase.assignment_ordinal == expected_assignment
            && phase.phase_ordinal == expected_phase_ordinal
            && phase.assignment_id_sha256
                == input.observations[(expected_assignment - 1) as usize]
                    .owner
                    .assignment_id_sha256
            && phase.observation_id_sha256
                == validated[(expected_assignment - 1) as usize].observation_id_sha256
            && match (
                expected_assignment,
                expected_phase_ordinal,
                phase.phase_kind,
            ) {
                (1..=7, 1, ParsedPhaseKindV1::AttemptResult) => true,
                (8..=60, 1, ParsedPhaseKindV1::FirstAttempt) => true,
                (8..=60, 2, ParsedPhaseKindV1::Restart) => true,
                _ => false,
            }
    });
    let mut unique_match_count = 0_u64;
    let mut zero_match_count = 0_u64;
    let mut multiple_match_count = 0_u64;
    for phase in &phases {
        match &phase.mapping {
            ValidatedCatalogMappingV1::Zero => zero_match_count += 1,
            ValidatedCatalogMappingV1::Unique {
                case_id,
                variant_id,
                row_sha256,
            } => {
                if case_id.is_empty() || variant_id.is_empty() || !nonzero(row_sha256) {
                    return Err(validator_error(
                        "s20b_s17_batch_mapping",
                        "S17 unique mapping token lost its row identity",
                    ));
                }
                unique_match_count += 1;
            }
            ValidatedCatalogMappingV1::Multiple { multiplicity } => {
                if *multiplicity < 2 {
                    return Err(validator_error(
                        "s20b_s17_batch_mapping",
                        "S17 multiple mapping token has invalid multiplicity",
                    ));
                }
                multiple_match_count += 1;
            }
        }
    }
    let pidfd_sigkill_count: u64 = validated
        .iter()
        .map(|observation| observation.sigkill_count)
        .sum();
    let fresh_exec_count: u64 = validated
        .iter()
        .map(|observation| observation.fresh_restart_count)
        .sum();
    if family_count("OL00") != 1
        || family_count("OL04") != 6
        || family_count("OL05") != 53
        || assignment_ids.len() != 60
        || assignment_records.len() != 60
        || observation_ids.len() != 60
        || phases.len() != 113
        || phase_records.len() != 113
        || !ordered_phase_shape
        || pidfd_sigkill_count != 59
        || fresh_exec_count != 59
        || unique_match_count != 113
        || zero_match_count != 0
        || multiple_match_count != 0
    {
        return Err(validator_error(
            "s20b_s17_batch_exactness",
            "S17 batch family/count/order/uniqueness/full-match denominator drifted",
        ));
    }
    let phase_fields: Vec<&[u8]> = phases
        .iter()
        .map(|phase| &phase.phase_record_sha256[..])
        .collect();
    let ordered_phase_digest = framed_digest(S17_PHASE_SET_DOMAIN, &phase_fields)?;
    let phase_record_set_sha256 = framed_digest(
        S17_PHASE_SET_DOMAIN,
        &[
            &authorized_set.assignment_set_sha256,
            &authorized_set.schedule_sha256,
            &ordered_phase_digest,
        ],
    )?;
    let observation_values: Vec<[u8; 32]> = validated
        .iter()
        .map(|observation| observation.observation_id_sha256)
        .collect();
    let observation_fields: Vec<&[u8]> = observation_values
        .iter()
        .map(|digest| &digest[..])
        .collect();
    let observation_set_sha256 = framed_digest(S17_OBSERVATION_SET_DOMAIN, &observation_fields)?;
    Ok(ValidatedS17BatchV1 {
        accounting: S17PostRunAccountingV1 {
            catalog_sha256: subject.catalog_sha256,
            classifier_source_sha256: subject.classifier_source_sha256,
            classifier_binary_sha256: subject.classifier_binary_sha256,
            expected_oracle_sha256: subject.expected_oracle_sha256,
            validator_toolchain_sha256: *validator_toolchains.iter().next().ok_or_else(|| {
                validator_error(
                    "s20b_s17_batch_toolchain",
                    "S17 validator toolchain binding is absent",
                )
            })?,
            observation_schema_sha256: subject.s17_observation_schema_sha256,
            plan_sha256: subject.s17_plan_sha256,
            validator_ruleset_sha256: validator_ruleset_digest_v1()?,
            full_catalog_row_count: rows.len() as u64,
            cross_field_rule_count: S17_CROSS_FIELD_RULES.len() as u64,
            assignment_count: validated.len() as u64,
            ol00_assignment_count: family_count("OL00"),
            ol04_assignment_count: family_count("OL04"),
            ol05_assignment_count: family_count("OL05"),
            pidfd_sigkill_count,
            fresh_exec_count,
            validated_phase_count: phases.len() as u64,
            unique_match_count,
            zero_match_count,
            multiple_match_count,
            successful_claim_count: input.successful_claim_count,
            retry_count: input.retry_count,
            assignment_prefilter_used: false,
            assignment_set_sha256: authorized_set.assignment_set_sha256,
            schedule_sha256: authorized_set.schedule_sha256,
            assignment_record_set_sha256: authorized_set.assignment_record_set_sha256,
            operation_descriptor_set_sha256: authorized_set.operation_descriptor_set_sha256,
            observation_count: observation_values.len() as u64,
            observation_set_sha256,
            phase_record_set_count: phases.len() as u64,
            phase_record_set_sha256,
        },
    })
}

#[cfg(test)]
mod tests {
    use super::*;

    fn digest(text: &str) -> [u8; 32] {
        decode_hex_fixed::<32>(text).unwrap()
    }

    fn repeated(byte: u8) -> [u8; 32] {
        [byte; 32]
    }

    fn s16_record() -> Vec<u8> {
        super::super::super::super::super::super::super::super::tests::s15_fixture_parts().0
    }

    fn catalog(record: &[u8]) -> Vec<FrozenS16RowV1> {
        let rows = super::super::super::super::super::super::build_case_catalog_v1(record).unwrap();
        assert_eq!(rows.len(), 5_639);
        assert_eq!(
            super::super::super::super::super::super::catalog_commitment_v1(&rows),
            super::super::super::super::super::super::CATALOG_KAT_SHA256
        );
        rows
    }

    fn base_raw(record: &[u8], ack_observed: bool) -> RawLifecycleFrameV1 {
        let receipt = digest("12c80f1b610d48438ec69457a6f553bf48fd6a15a9c3ffebd7b20c67895b76a2");
        let witness = digest("c336caea644548f287ddc285ee3b9433f853f9b1f562cee9f055df913458bf99");
        RawLifecycleFrameV1 {
            publisher_phase: "ACKED".into(),
            object_state: "COMMITTED".into(),
            object_len: record.len() as u64,
            object_sha256: Some(Sha256::digest(record).into()),
            receipt_state: "COMMITTED".into(),
            computed_receipt_sha256: Some(receipt),
            stored_receipt_sha256: Some(receipt),
            witness_state: "PRESENT".into(),
            computed_witness_sha256: Some(witness),
            stored_witness_sha256: Some(witness),
            selected_view_state: "PRESENT".into(),
            selected_view_sha256: Some(digest(
                "9a8f959a01d3aead14b527d51bb1c744999e8e1ee33a564cea72bb15b2b00d6a",
            )),
            competing_view_state: "ABSENT".into(),
            competing_view_sha256: None,
            ack_state: if ack_observed {
                "OBSERVED".into()
            } else {
                "NOT_OBSERVED".into()
            },
            ack_receipt_sha256: ack_observed.then_some(receipt),
            ack_witness_sha256: ack_observed.then_some(witness),
            crash_cut: "NONE".into(),
            crash_cut_index: 0,
            restarted_after_crash: false,
            observed_data_steps: 0,
            observed_len: 0,
            adapter_pre_state: "FRESH".into(),
            adapter_post_state: "COMPLETED".into(),
        }
    }

    fn absent_raw() -> RawLifecycleFrameV1 {
        RawLifecycleFrameV1 {
            publisher_phase: "EMPTY".into(),
            object_state: "ABSENT".into(),
            object_len: 0,
            object_sha256: None,
            receipt_state: "ABSENT".into(),
            computed_receipt_sha256: None,
            stored_receipt_sha256: None,
            witness_state: "ABSENT".into(),
            computed_witness_sha256: None,
            stored_witness_sha256: None,
            selected_view_state: "ABSENT".into(),
            selected_view_sha256: None,
            competing_view_state: "ABSENT".into(),
            competing_view_sha256: None,
            ack_state: "NOT_OBSERVED".into(),
            ack_receipt_sha256: None,
            ack_witness_sha256: None,
            crash_cut: "NONE".into(),
            crash_cut_index: 0,
            restarted_after_crash: false,
            observed_data_steps: 0,
            observed_len: 0,
            adapter_pre_state: "FRESH".into(),
            adapter_post_state: "FRESH".into(),
        }
    }

    fn d04_raw(record: &[u8], cut: usize) -> RawLifecycleFrameV1 {
        let receipt = digest("12c80f1b610d48438ec69457a6f553bf48fd6a15a9c3ffebd7b20c67895b76a2");
        let witness = digest("c336caea644548f287ddc285ee3b9433f853f9b1f562cee9f055df913458bf99");
        let selected = digest("9a8f959a01d3aead14b527d51bb1c744999e8e1ee33a564cea72bb15b2b00d6a");
        let mut raw = absent_raw();
        raw.restarted_after_crash = true;
        match cut {
            0 => {}
            1 => {
                raw.publisher_phase = "OBJECT_PREFIX".into();
                raw.object_state = "PARTIAL".into();
                raw.object_len = 2_747;
                raw.object_sha256 = Some(Sha256::digest(&record[..2_747]).into());
                raw.crash_cut = "PUBLISH_AFTER_OBJECT_PREFIX".into();
                raw.crash_cut_index = 2_747;
            }
            2 => {
                raw.publisher_phase = "OBJECT_COMMITTED".into();
                raw.object_state = "COMMITTED".into();
                raw.object_len = record.len() as u64;
                raw.object_sha256 = Some(Sha256::digest(record).into());
                raw.crash_cut = "PUBLISH_AFTER_OBJECT_COMMIT".into();
            }
            3 => {
                raw.publisher_phase = "RECEIPT_COMMITTED".into();
                raw.object_state = "COMMITTED".into();
                raw.object_len = record.len() as u64;
                raw.object_sha256 = Some(Sha256::digest(record).into());
                raw.receipt_state = "COMMITTED".into();
                raw.computed_receipt_sha256 = Some(receipt);
                raw.stored_receipt_sha256 = Some(receipt);
                raw.crash_cut = "PUBLISH_AFTER_RECEIPT_COMMIT".into();
            }
            4 | 5 => {
                // The frozen D04 post-crash row retains no observed ACK
                // payload even at the PUBLISH_AFTER_ACK cut; ACK observation
                // belongs to D00's clean control row, not this restart row.
                raw = base_raw(record, false);
                raw.restarted_after_crash = true;
                raw.publisher_phase = if cut == 4 {
                    "WITNESS_COMMITTED".into()
                } else {
                    "ACKED".into()
                };
                raw.crash_cut = if cut == 4 {
                    "PUBLISH_AFTER_WITNESS_COMMIT".into()
                } else {
                    "PUBLISH_AFTER_ACK".into()
                };
                raw.selected_view_sha256 = Some(selected);
                raw.computed_witness_sha256 = Some(witness);
                raw.stored_witness_sha256 = Some(witness);
            }
            _ => unreachable!(),
        }
        raw
    }

    fn d05_raw(record: &[u8], cut_ordinal: usize, restart: bool) -> RawLifecycleFrameV1 {
        let mut raw = base_raw(record, false);
        let (cut, cut_index) = match cut_ordinal {
            0 => ("READ_BEFORE_OPEN", 0),
            1 => ("READ_AFTER_OPEN", 0),
            2..=50 => ("READ_AFTER_DATA", cut_ordinal as u64 - 1),
            51 => ("READ_AFTER_COMPLETE_BEFORE_S14", 0),
            52 => ("READ_AFTER_HISTORICAL", 0),
            _ => unreachable!(),
        };
        raw.crash_cut = cut.into();
        raw.crash_cut_index = cut_index;
        raw.restarted_after_crash = restart;
        if restart {
            raw.adapter_pre_state = "FRESH".into();
            raw.adapter_post_state = "COMPLETED".into();
            raw.observed_data_steps = 49;
        } else {
            match cut_ordinal {
                0 => {
                    raw.adapter_pre_state = "FRESH".into();
                    raw.adapter_post_state = "FRESH".into();
                    raw.observed_data_steps = 0;
                }
                1 => {
                    raw.adapter_pre_state = "STREAMING".into();
                    raw.adapter_post_state = "TERMINAL_FAILED".into();
                    raw.observed_data_steps = 0;
                }
                2..=50 => {
                    raw.adapter_pre_state = "STREAMING".into();
                    raw.adapter_post_state = "TERMINAL_FAILED".into();
                    raw.observed_data_steps = cut_ordinal as u64 - 1;
                }
                51 => {
                    raw.adapter_pre_state = "STREAMING".into();
                    raw.adapter_post_state = "COMPLETED".into();
                    raw.observed_data_steps = 49;
                }
                52 => {
                    raw.adapter_pre_state = "COMPLETED".into();
                    raw.adapter_post_state = "COMPLETED".into();
                    raw.observed_data_steps = 49;
                }
                _ => unreachable!(),
            }
        }
        raw.observed_len = (raw.observed_data_steps * 113).min(5_494);
        raw
    }

    fn independent_target_lifecycles(record: &[u8]) -> Vec<RawLifecycleFrameV1> {
        let mut raw = vec![base_raw(record, true)];
        raw.extend((0..6).map(|cut| d04_raw(record, cut)));
        for cut in 0..53 {
            raw.push(d05_raw(record, cut, false));
            raw.push(d05_raw(record, cut, true));
        }
        assert_eq!(raw.len(), 113);
        raw
    }

    fn subject(set_root: [u8; 32], schedule_root: [u8; 32]) -> VerifiedS19SubjectV1 {
        VerifiedS19SubjectV1 {
            canonical_manifest_sha256: repeated(1),
            schema_sha256: repeated(2),
            source_commit: [3; 20],
            integration_commit: [4; 20],
            controller_binary_sha256: repeated(5),
            runner_binary_sha256: repeated(6),
            preflight_observer_binary_sha256: repeated(7),
            boot_id_sha256: repeated(8),
            root_parent_identity_sha256: repeated(9),
            resource_scope_sha256: repeated(10),
            control_ledger_identity_sha256: repeated(11),
            anti_rollback_policy_sha256: repeated(12),
            stop_control_policy_sha256: repeated(13),
            sqlite_profile_sha256: repeated(14),
            sqlite_schema_sha256: repeated(15),
            claim_namespace_sha256: repeated(16),
            claim_key_sha256: repeated(17),
            expected_unclaimed_revision: 1,
            assignment_set_sha256: set_root,
            schedule_sha256: schedule_root,
            catalog_row_count: 5_639,
            catalog_sha256: super::super::super::super::super::super::CATALOG_KAT_SHA256,
            classifier_binary_sha256: repeated(18),
            classifier_source_sha256: repeated(19),
            expected_oracle_sha256: repeated(20),
            s17_observation_schema_sha256: S17_OBSERVATION_SCHEMA_RAW_SHA256,
            s17_plan_sha256: S17_PLAN_RAW_SHA256,
            target_phase_count: 113,
            target_phase_unique_match_count: 113,
            allowed_operation_ids: ALLOWED_OPERATION_IDS
                .iter()
                .map(|operation| (*operation).into())
                .collect(),
        }
    }

    fn authorized_subject(
        set_root: [u8; 32],
        schedule_root: [u8; 32],
    ) -> AuthorizedUnclaimedS19SubjectV1 {
        AuthorizedUnclaimedS19SubjectV1 {
            authorization: VerifiedUnclaimedOwnedLabAuthorizationV1 {
                authorization_id_sha256: repeated(0x31),
                payload_sha256: repeated(0x32),
                owner_envelope_sha256: repeated(0x33),
                trust_anchor_document_sha256: repeated(0x34),
                owner_identity_sha256: repeated(0x35),
                owner_key_id: "s17-test-owner-key".into(),
                owner_key_version: 1,
                revocation_epoch: 1,
            },
            subject: subject(set_root, schedule_root),
            capability_nonce_sha256: repeated(0x36),
            revocation_policy_sha256: repeated(0x37),
        }
    }

    #[test]
    fn s20b_s17_independent_raw_lifecycle_full_5639_scan_covers_113_targets() {
        let record = s16_record();
        let rows = catalog(&record);
        let mut cases = std::collections::BTreeMap::<&str, usize>::new();
        for (index, raw) in independent_target_lifecycles(&record)
            .into_iter()
            .enumerate()
        {
            let projection = derive_projection_v1(&raw);
            match scan_full_catalog_v1(&rows, &projection) {
                FullCatalogScanV1::One { scanned, row } => {
                    assert_eq!(scanned, 5_639);
                    *cases.entry(row.case_id).or_default() += 1;
                }
                FullCatalogScanV1::Zero { scanned } => {
                    panic!(
                        "independent raw lifecycle {index} ({}/{}/{}) scanned {scanned} rows with zero matches",
                        raw.publisher_phase, raw.crash_cut, raw.restarted_after_crash
                    )
                }
                FullCatalogScanV1::Multiple {
                    scanned,
                    multiplicity,
                } => {
                    panic!(
                        "independent raw lifecycle {index} ({}/{}/{}) scanned {scanned} rows with {multiplicity} matches",
                        raw.publisher_phase, raw.crash_cut, raw.restarted_after_crash
                    )
                }
            }
        }
        assert_eq!(cases.get("D00_CLEAN_COMMITTED_HEAD"), Some(&1));
        assert_eq!(cases.get("D04_PUBLISH_CRASH_RESTART_CUTS"), Some(&6));
        assert_eq!(cases.get("D05_S15_READ_CRASH_RESTART_CUTS"), Some(&106));
    }

    #[test]
    fn s20b_s17_zero_and_multiple_catalog_cardinality_are_explicit() {
        let record = s16_record();
        let mut rows = catalog(&record);
        let mut raw = base_raw(&record, true);
        raw.observed_len = 1;
        assert!(matches!(
            scan_full_catalog_v1(&rows, &derive_projection_v1(&raw)),
            FullCatalogScanV1::Zero { scanned: 5_639 }
        ));

        // Construct an actual 5,639-row ambiguity without adding an API that
        // can manufacture model rows: move a matching row from a second
        // independently built catalog over one unrelated row.
        let projection = derive_projection_v1(&base_raw(&record, true));
        let replace_index = rows
            .iter()
            .position(|row| !row_matches_projection_v1(row, &projection))
            .unwrap();
        let mut second_catalog = catalog(&record);
        let duplicate_index = second_catalog
            .iter()
            .position(|row| row_matches_projection_v1(row, &projection))
            .unwrap();
        rows[replace_index] = second_catalog.swap_remove(duplicate_index);
        let multiple = scan_full_catalog_v1(&rows, &projection);
        assert!(matches!(
            &multiple,
            FullCatalogScanV1::Multiple {
                scanned: 5_639,
                multiplicity: 2
            }
        ));
        let reported = ReportedClassificationV1 {
            classifier_build_sha256: repeated(1),
            mapping_cardinality: 0,
            mapped_s16_case_id: None,
            mapped_s16_variant_id: None,
            mapped_s16_row_sha256: None,
            mapped_reason: "FULL_FROZEN_S16_CATALOG_MULTIPLE_MATCHES".into(),
            mapped_failure: "INDETERMINATE".into(),
            mapping_status: "OBSERVED_OUT_OF_MODEL_INDETERMINATE".into(),
        };
        assert!(reported_indeterminate_v1(&reported, &multiple));
    }

    #[test]
    fn s20b_s17_assignment_label_substitution_cannot_prefilter_scan() {
        let record = s16_record();
        let rows = catalog(&record);
        let projection = derive_projection_v1(&d04_raw(&record, 1));
        let classify =
            |_untrusted_assignment_label: &str| match scan_full_catalog_v1(&rows, &projection) {
                FullCatalogScanV1::One { scanned, row } => {
                    assert_eq!(scanned, 5_639);
                    super::super::super::super::super::super::row_commitment_v1(row)
                }
                _ => panic!("independent projection stopped mapping uniquely"),
            };
        assert_eq!(
            classify("D04_CRASH_AFTER_OBJECT_PREFIX_RESTART"),
            classify("CALLER_SUBSTITUTED_D00_CLEAN")
        );
    }

    #[test]
    fn s20b_s17_raw_frame_hash_and_typed_decode_tamper_are_rejected() {
        let record = s16_record();
        let raw = d05_raw(&record, 17, false);
        let encoded = restricted_canonical_bytes(&raw_lifecycle_value_v1(&raw)).unwrap();
        let parsed =
            parse_raw_lifecycle_v1(&parse_restricted_canonical(&encoded).unwrap()).unwrap();
        assert_eq!(parsed, raw);
        let expected_hash: [u8; 32] = Sha256::digest(&encoded).into();
        let mut tampered = encoded.clone();
        *tampered.last_mut().unwrap() = b']';
        let tampered_hash: [u8; 32] = Sha256::digest(&tampered).into();
        assert_ne!(tampered_hash, expected_hash);
        assert!(parse_restricted_canonical(&tampered).is_err());
    }

    #[test]
    fn s20b_s17_d05_lifecycle_and_numbered_rule_tamper_are_rejected() {
        let record = s16_record();
        let mut raw = d05_raw(&record, 23, false);
        assert!(d05_lifecycle_relation_v1(
            &raw,
            ParsedPhaseKindV1::FirstAttempt
        ));
        raw.observed_data_steps += 1;
        assert!(!d05_lifecycle_relation_v1(
            &raw,
            ParsedPhaseKindV1::FirstAttempt
        ));
        assert!(cross_rule_v1(24, false).is_err());
        assert!(cross_rule_v1(24, true).is_ok());
    }

    #[test]
    fn s20b_s17_batch_cardinality_claim_retry_and_roots_are_exact() {
        let (set_root, schedule_root) =
            super::super::assignment_authority::frozen_assignment_roots_for_tests_v1().unwrap();
        let authorized = authorized_subject(set_root, schedule_root);
        let authorized_set =
            super::super::assignment_authority::validate_authorized_assignment_set_v1(&authorized)
                .unwrap();
        assert!(authorized_set.matches_authorized_subject_v1(&authorized));
        assert!(exact_batch_header_v1(
            60,
            1,
            0,
            set_root,
            schedule_root,
            &authorized
        ));
        for (assignments, claims, retries) in [(59, 1, 0), (61, 1, 0), (60, 0, 0), (60, 1, 1)] {
            assert!(!exact_batch_header_v1(
                assignments,
                claims,
                retries,
                set_root,
                schedule_root,
                &authorized
            ));
        }
        let mut wrong_root = set_root;
        wrong_root[0] ^= 1;
        assert!(!exact_batch_header_v1(
            60,
            1,
            0,
            wrong_root,
            schedule_root,
            &authorized
        ));

        let mut wrong_authorized = authorized_subject(set_root, schedule_root);
        wrong_authorized.capability_nonce_sha256[0] ^= 1;
        assert!(!authorized_set.matches_authorized_subject_v1(&wrong_authorized));
        assert!(validate_s17_batch_v1(
            &wrong_authorized,
            &authorized_set,
            &[],
            S17BatchInputV1 {
                observations: Vec::new(),
                successful_claim_count: 1,
                retry_count: 0,
            },
        )
        .is_err());
    }
}
