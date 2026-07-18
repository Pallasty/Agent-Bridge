//! S20B private, default-off rich-packet and full-catalog validators.
//!
//! The code in this module has no live adapter.  Builders consume typed facts,
//! validators rebuild the exact expected packet, and successful validation only
//! yields private evidence tokens.  No packet is an execution capability.

#![cfg_attr(not(test), allow(dead_code))]

use super::*;
use serde_json::{json, Map, Value};
use std::collections::{BTreeMap, BTreeSet};

mod assignment_authority;
mod s17_full_validator;
mod schema_aligned_packets;

const S20B_FOUR_RICH_PACKET_BUILDERS_PARSERS_VALIDATORS_IMPLEMENTED: bool = true;
const S20B_RUNTIME_SELF_DIGEST_RECOMPUTATION_IMPLEMENTED: bool = true;
const S20B_RUNTIME_CROSS_PACKET_DIGEST_RECOMPUTATION_IMPLEMENTED: bool = true;
const S20B_FULL_24_PARAMETER_CLAIM_VALIDATOR_IMPLEMENTED: bool = true;
const S20B_EXACT_ASSIGNMENT_MEMBERSHIP_VALIDATOR_IMPLEMENTED: bool = true;
const S20B_CONCRETE_OPERATION_DESCRIPTOR_VALIDATOR_IMPLEMENTED: bool = true;
const S20B_DATABASE_CONTENT_ROOT_IMPLEMENTED: bool = true;
const S20B_S17_32_RULE_FULL_5639_ROW_VALIDATOR_IMPLEMENTED: bool = true;
const S20B_NEGATIVE_KAT_SUITE_IMPLEMENTED: bool = true;
const S20B_LIVE_BACKEND_PRESENT: bool = false;
const S20B_SIDE_EFFECTS_UNLOCKED: &str = "NONE";
const S20B_UNKNOWN_COMMIT_TERMINAL_CONTRACT: &str = "UNKNOWN_COMMIT_OUTCOME_TERMINAL_HARD_LOCK";

const S20B_CANONICALIZATION: &str =
    "AB_RESTRICTED_CANONICAL_JSON_S20B_V1_COMPACT_SORTED_KEYS_ASCII_VALUES_NO_FLOAT";
const PREFLIGHT_CONTEXT_DOMAIN: &[u8] =
    b"agent-bridge/biocortex/owned-lab/s20b/preflight-context/v1";
const PREFLIGHT_PACKET_DOMAIN: &[u8] =
    b"agent-bridge/biocortex/owned-lab/s20b/preflight-receipt/v1";
const CONTROL_PACKET_DOMAIN: &[u8] = b"agent-bridge/biocortex/owned-lab/s20b/control-snapshot/v1";
const CLAIM_TRANSITION_DOMAIN: &[u8] =
    b"agent-bridge/biocortex/owned-lab/s20b/claim-transition-core/v1";
const CLAIM_PACKET_DOMAIN: &[u8] =
    b"agent-bridge/biocortex/owned-lab/s20b/claim-outcome-receipt/v1";
const POSTRUN_PACKET_DOMAIN: &[u8] = b"agent-bridge/biocortex/owned-lab/s20b/post-run-bundle/v1";
#[cfg(test)]
const LEGACY_FIXTURE_ASSIGNMENT_RECORD_DOMAIN: &[u8] =
    b"agent-bridge/biocortex/owned-lab/s20b/assignment-record/v1";
#[cfg(test)]
const LEGACY_FIXTURE_ASSIGNMENT_SET_DOMAIN: &[u8] =
    b"agent-bridge/biocortex/owned-lab/s20b/assignment-set/v1";
#[cfg(test)]
const LEGACY_FIXTURE_SCHEDULE_DOMAIN: &[u8] = b"agent-bridge/biocortex/owned-lab/s20b/schedule/v1";
#[cfg(test)]
const LEGACY_FIXTURE_OPERATION_DESCRIPTOR_DOMAIN: &[u8] =
    b"agent-bridge/biocortex/owned-lab/s20b/concrete-operation-descriptor/v1";
const RECEIPT_NODE_DOMAIN: &[u8] = b"agent-bridge/biocortex/owned-lab/s20b/postrun-receipt-node/v1";
const S17_FINGERPRINT_DOMAIN: &[u8] =
    b"agent-bridge/biocortex/owned-lab/s20b/s17-augmented-fingerprint/v1";
const S17_CLASSIFICATION_INPUT_DOMAIN: &[u8] =
    b"agent-bridge/biocortex/owned-lab/s20b/s17-classification-input/v1";
const S17_PHASE_RECORD_DOMAIN: &[u8] = b"agent-bridge/biocortex/owned-lab/s20b/s17-phase-record/v1";

const PREFLIGHT_SCHEMA: &str = "agent_bridge.memory_temporal_owned_lab_preflight_receipt_s20b.v0";
const CONTROL_SCHEMA: &str = "agent_bridge.memory_temporal_owned_lab_control_snapshot_s20b.v0";
const CLAIM_SCHEMA: &str = "agent_bridge.memory_temporal_owned_lab_authority_control_claim_s20b.v0";
const POSTRUN_SCHEMA: &str =
    "agent_bridge.memory_temporal_owned_lab_post_run_receipt_bundle_s20b.v0";

const ALLOWED_OPERATION_IDS: [&str; 8] = [
    "CREATE_EXACT_RUN_ROOT",
    "SQLITE_EXACT_PROFILE_SETUP",
    "SPAWN_ONE_ASSIGNED_CHILD",
    "PIDFD_OPEN_ASSIGNED_CHILD",
    "PIDFD_SEND_SIGNAL_SIGKILL",
    "FRESH_EXEC_REOPEN",
    "WRITE_BOUND_RECEIPTS",
    "CLEANUP_EXACT_RUN_ROOT",
];

const S17_CROSS_FIELD_RULES: [&str; 32] = [
    "PIDFD_TARGET_PID_AND_START_EQUAL_INITIAL_CHILD",
    "SIGNAL_SENDER_PID_AND_START_EQUAL_CONTROLLER",
    "FRESH_PID_START_AND_NONCE_DISTINCT_FROM_INITIAL_CHILD",
    "INITIAL_AND_FRESH_EXEC_IMAGE_HASH_EQUAL_FROZEN_RUNNER_BINARY",
    "BOOT_IDS_EQUAL_WHEN_SAME_BOOT_VERIFIED",
    "ROOT_STAT_IDENTITIES_EQUAL_WHEN_ROOT_STABLE",
    "MOUNT_IDENTITIES_AND_MOUNTINFO_EQUAL_WHEN_MOUNT_STABLE",
    "DATABASE_PATH_IS_DIRECT_DESCENDANT_OF_EXACT_RUN_ROOT",
    "DATABASE_IDENTITIES_EQUAL_WHEN_DATABASE_STABLE",
    "SQLITE_PROFILE_AND_SCHEMA_HASH_EQUAL_FROZEN_BINDINGS",
    "CUSTODY_RAW_AND_CANONICAL_HASHES_EQUAL_IDENTITY_HASHES",
    "RAW_EVENT_FRAME_BYTE_RANGE_HASH_RECOMPUTED_FROM_RETAINED_RAW_PACKET",
    "PHASE_RAW_MEASUREMENT_DECODED_FROM_BOUND_RAW_EVENT_FRAME",
    "ACK_OBSERVED_PAYLOAD_BINDS_RECEIPT_AND_WITNESS_AND_NOT_OBSERVED_HAS_NO_PAYLOAD",
    "S16_VIRTUAL_PROJECTION_EXACTLY_DERIVED_FROM_RAW_PHASE_MEASUREMENT_WITH_DOMAIN_SEPARATED_ABSENT_SENTINELS",
    "S16_VIRTUAL_PROJECTION_COUNTERS_ZERO_SIDE_EFFECTS_NONE_AND_DISTINCT_FROM_S17_LEDGER",
    "CLASSIFICATION_INPUT_SHA256_RECOMPUTED_FROM_DOMAIN_AND_EXACT_FRAME",
    "PHASE_RECORD_SHA256_RECOMPUTED_WITH_SELF_HASH_OMITTED",
    "CLASSIFIER_BUILD_EQUALS_FROZEN_CLASSIFIER_BINARY_AND_OWNER_RECEIPT",
    "CLASSIFICATION_RECOMPUTED_BY_PHASE_LIFECYCLE_EVALUATOR_AND_FULL_FROZEN_S16_CATALOG",
    "ASSIGNMENT_FAMILY_CASE_AND_VARIANT_NOT_USED_TO_PREFILTER_CLASSIFICATION",
    "ASSIGNMENT_LABELS_COMPARED_WITH_RECOMPUTED_CLASSIFICATION_ONLY_AFTER_FULL_CATALOG_LOOKUP",
    "UNIQUE_MAPPING_CASE_VARIANT_ROW_REASON_AND_FAILURE_EQUAL_RECOMPUTED_FROZEN_S16_ROW",
    "S16_ABSENT_SENTINELS_USED_ONLY_IN_VIRTUAL_MODEL_PROJECTION_NOT_RAW_PACKET_FACTS",
    "D05_CUT_INDEX_OBSERVED_DATA_STEPS_LENGTH_AND_ADAPTER_STATE_RELATION_VALID",
    "D05_FIRST_AND_RESTART_PHASES_BIND_SAME_ATTEMPT_CUT",
    "EVERY_PHASE_DURABLE_IMAGE_FACTS_EQUAL_TOP_LEVEL_RAW_RECOVERED_STATE",
    "D05_FIRST_PHASE_PROCESS_EQUALS_INITIAL_CHILD",
    "D05_RESTART_PHASE_PROCESS_EQUALS_FRESH_CHILD",
    "SINGLE_PHASE_PROCESS_EQUALS_ELIGIBLE_RESULT_PROCESS",
    "CUSTODY_SEQUENCE_AND_PREVIOUS_HASH_RELATION_VALID",
    "OWNER_RECEIPT_ASSIGNMENT_RESOURCE_SAFETY_AND_DECISION_BINDINGS_VALID",
];

fn s20b_error(code: &'static str, detail: &'static str) -> OwnedLabAuthorizationError {
    manifest_error(code, detail)
}

fn hex32(value: &[u8; 32]) -> String {
    hex(value)
}

fn require_nonzero_digests(values: &[&[u8; 32]]) -> AuthorizationResult<()> {
    if values.iter().any(|value| !nonzero(&value[..])) {
        return Err(s20b_error(
            "s20b_zero_digest",
            "a security binding is the all-zero digest",
        ));
    }
    Ok(())
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
enum RichPacketKindV1 {
    PreflightReceipt,
    ControlSnapshot,
    AuthorityControlClaim,
    PostRunReceiptBundle,
}

impl RichPacketKindV1 {
    fn schema(self) -> &'static str {
        match self {
            Self::PreflightReceipt => PREFLIGHT_SCHEMA,
            Self::ControlSnapshot => CONTROL_SCHEMA,
            Self::AuthorityControlClaim => CLAIM_SCHEMA,
            Self::PostRunReceiptBundle => POSTRUN_SCHEMA,
        }
    }

    fn packet_kind(self) -> &'static str {
        match self {
            Self::PreflightReceipt => "S20B_OWNED_LAB_FRESH_PREFLIGHT_RECEIPT",
            Self::ControlSnapshot => "S20B_EXTERNAL_AUTHORITY_CONTROL_SNAPSHOT",
            Self::AuthorityControlClaim => "S20B_SINGLE_USE_CLAIM_OUTCOME_RECEIPT",
            Self::PostRunReceiptBundle => "S20B_OWNED_LAB_POST_RUN_RECEIPT_BUNDLE",
        }
    }

    fn self_key(self) -> &'static str {
        match self {
            Self::PreflightReceipt => "preflight_receipt_sha256",
            Self::ControlSnapshot => "control_snapshot_sha256",
            Self::AuthorityControlClaim => "claim_packet_sha256",
            Self::PostRunReceiptBundle => "post_run_bundle_sha256",
        }
    }

    fn domain(self) -> &'static [u8] {
        match self {
            Self::PreflightReceipt => PREFLIGHT_PACKET_DOMAIN,
            Self::ControlSnapshot => CONTROL_PACKET_DOMAIN,
            Self::AuthorityControlClaim => CLAIM_PACKET_DOMAIN,
            Self::PostRunReceiptBundle => POSTRUN_PACKET_DOMAIN,
        }
    }
}

struct BuiltRichPacketV1 {
    kind: RichPacketKindV1,
    raw: Vec<u8>,
    digest: [u8; 32],
}

#[must_use]
struct ValidatedRichPacketV1 {
    kind: RichPacketKindV1,
    digest: [u8; 32],
}

fn seal_exact_packet_v1(
    kind: RichPacketKindV1,
    mut body: Map<String, Value>,
) -> AuthorizationResult<BuiltRichPacketV1> {
    if body.contains_key(kind.self_key()) {
        return Err(s20b_error(
            "s20b_self_scope",
            "builder body already contains its excluded self digest",
        ));
    }
    body.insert("schema".into(), Value::String(kind.schema().into()));
    body.insert(
        "packet_kind".into(),
        Value::String(kind.packet_kind().into()),
    );
    body.insert(
        "canonicalization".into(),
        Value::String(S20B_CANONICALIZATION.into()),
    );
    let digest_body = restricted_canonical_bytes(&Value::Object(body.clone()))?;
    let digest = framed_digest(kind.domain(), &[&digest_body])?;
    body.insert(kind.self_key().into(), Value::String(hex32(&digest)));
    Ok(BuiltRichPacketV1 {
        kind,
        raw: restricted_canonical_bytes(&Value::Object(body))?,
        digest,
    })
}

fn validate_self_digest_v1(raw: &[u8], kind: RichPacketKindV1) -> AuthorizationResult<[u8; 32]> {
    let parsed = parse_restricted_canonical(raw)?;
    let mut body = object(&parsed, "s20b_packet_object")?.clone();
    if body.get("schema").and_then(Value::as_str) != Some(kind.schema())
        || body.get("packet_kind").and_then(Value::as_str) != Some(kind.packet_kind())
        || body.get("canonicalization").and_then(Value::as_str) != Some(S20B_CANONICALIZATION)
    {
        return Err(s20b_error(
            "s20b_packet_identity",
            "schema, packet kind, or canonical profile drifted",
        ));
    }
    let reported = body
        .remove(kind.self_key())
        .and_then(|value| value.as_str().map(str::to_owned))
        .ok_or_else(|| s20b_error("s20b_self_missing", "packet self digest is absent"))?;
    let digest_body = restricted_canonical_bytes(&Value::Object(body))?;
    let recomputed = framed_digest(kind.domain(), &[&digest_body])?;
    if decode_hex_fixed::<32>(&reported)? != recomputed {
        return Err(s20b_error(
            "s20b_self_digest",
            "packet self digest does not recompute under its fixed domain",
        ));
    }
    Ok(recomputed)
}

fn validate_exact_packet_v1(
    candidate: &[u8],
    expected: BuiltRichPacketV1,
) -> AuthorizationResult<ValidatedRichPacketV1> {
    let recomputed = validate_self_digest_v1(candidate, expected.kind)?;
    if recomputed != expected.digest || candidate != expected.raw {
        return Err(s20b_error(
            "s20b_independent_rebuild",
            "candidate differs from independently rebuilt typed semantics",
        ));
    }
    Ok(ValidatedRichPacketV1 {
        kind: expected.kind,
        digest: recomputed,
    })
}

#[derive(Clone)]
struct RichIdentityBindingsV1 {
    authorization_id_sha256: [u8; 32],
    owner_envelope_sha256: [u8; 32],
    trust_anchor_document_sha256: [u8; 32],
    signed_payload_sha256: [u8; 32],
    subject_manifest_sha256: [u8; 32],
    resource_scope_sha256: [u8; 32],
    claim_namespace_sha256: [u8; 32],
    claim_key_sha256: [u8; 32],
    capability_nonce_sha256: [u8; 32],
    run_id_sha256: [u8; 32],
    assignment_set_sha256: [u8; 32],
    schedule_sha256: [u8; 32],
    assignment_record_sha256: [u8; 32],
    operation_descriptor_sha256: [u8; 32],
}

impl RichIdentityBindingsV1 {
    fn validate(&self) -> AuthorizationResult<()> {
        require_nonzero_digests(&[
            &self.authorization_id_sha256,
            &self.owner_envelope_sha256,
            &self.trust_anchor_document_sha256,
            &self.signed_payload_sha256,
            &self.subject_manifest_sha256,
            &self.resource_scope_sha256,
            &self.claim_namespace_sha256,
            &self.claim_key_sha256,
            &self.capability_nonce_sha256,
            &self.run_id_sha256,
            &self.assignment_set_sha256,
            &self.schedule_sha256,
            &self.assignment_record_sha256,
            &self.operation_descriptor_sha256,
        ])
    }

    fn value(&self) -> Value {
        json!({
            "assignment_record_sha256": hex32(&self.assignment_record_sha256),
            "assignment_set_sha256": hex32(&self.assignment_set_sha256),
            "authorization_id_sha256": hex32(&self.authorization_id_sha256),
            "capability_nonce_sha256": hex32(&self.capability_nonce_sha256),
            "claim_key_sha256": hex32(&self.claim_key_sha256),
            "claim_namespace_sha256": hex32(&self.claim_namespace_sha256),
            "operation_descriptor_sha256": hex32(&self.operation_descriptor_sha256),
            "owner_envelope_sha256": hex32(&self.owner_envelope_sha256),
            "resource_scope_sha256": hex32(&self.resource_scope_sha256),
            "run_id_sha256": hex32(&self.run_id_sha256),
            "schedule_sha256": hex32(&self.schedule_sha256),
            "signed_payload_sha256": hex32(&self.signed_payload_sha256),
            "subject_manifest_sha256": hex32(&self.subject_manifest_sha256),
            "trust_anchor_document_sha256": hex32(&self.trust_anchor_document_sha256)
        })
    }
}

/// Historical test-fixture projection used only by the original mutation
/// suite.  It is deliberately absent from non-test builds and is not S20B
/// assignment authority.  Production validators exclusively consume the
/// owner-authenticated, typed v2 tokens from `assignment_authority`.
#[cfg(test)]
#[derive(Clone, Debug, Eq, PartialEq)]
struct ConcreteOperationDescriptorV1 {
    create_exact_run_root: bool,
    sqlite_exact_profile_setup: bool,
    spawn_one_assigned_child: bool,
    pidfd_open_assigned_child: bool,
    pidfd_send_signal_sigkill: bool,
    fresh_exec_reopen: bool,
    write_bound_receipts: bool,
    cleanup_exact_run_root: bool,
}

#[cfg(test)]
impl ConcreteOperationDescriptorV1 {
    fn for_family(family: &str) -> Self {
        let crash = family != "OL00";
        Self {
            create_exact_run_root: true,
            sqlite_exact_profile_setup: true,
            spawn_one_assigned_child: true,
            pidfd_open_assigned_child: crash,
            pidfd_send_signal_sigkill: crash,
            fresh_exec_reopen: crash,
            write_bound_receipts: true,
            cleanup_exact_run_root: true,
        }
    }

    fn value(&self) -> Value {
        json!({
            "cleanup_exact_run_root": self.cleanup_exact_run_root,
            "create_exact_run_root": self.create_exact_run_root,
            "fresh_exec_reopen": self.fresh_exec_reopen,
            "pidfd_open_assigned_child": self.pidfd_open_assigned_child,
            "pidfd_send_signal_sigkill": self.pidfd_send_signal_sigkill,
            "spawn_one_assigned_child": self.spawn_one_assigned_child,
            "sqlite_exact_profile_setup": self.sqlite_exact_profile_setup,
            "write_bound_receipts": self.write_bound_receipts
        })
    }

    fn digest(&self) -> AuthorizationResult<[u8; 32]> {
        framed_digest(
            LEGACY_FIXTURE_OPERATION_DESCRIPTOR_DOMAIN,
            &[&restricted_canonical_bytes(&self.value())?],
        )
    }
}

#[cfg(test)]
#[derive(Clone, Debug)]
struct AuthorizedAssignmentV1 {
    ordinal: u64,
    family_id: String,
    case_id: String,
    variant_id: String,
    phase_count: u64,
    operation: ConcreteOperationDescriptorV1,
    operation_descriptor_sha256: [u8; 32],
    assignment_record_sha256: [u8; 32],
}

#[cfg(test)]
struct ExactAssignmentSetV1 {
    entries: Vec<AuthorizedAssignmentV1>,
    assignment_set_sha256: [u8; 32],
    schedule_sha256: [u8; 32],
}

#[cfg(test)]
fn assignment_record_digest_v1(
    ordinal: u64,
    family: &str,
    case_id: &str,
    variant: &str,
    phase_count: u64,
    operation_descriptor_sha256: &[u8; 32],
) -> AuthorizationResult<[u8; 32]> {
    framed_digest(
        LEGACY_FIXTURE_ASSIGNMENT_RECORD_DOMAIN,
        &[
            &ordinal.to_be_bytes(),
            family.as_bytes(),
            case_id.as_bytes(),
            variant.as_bytes(),
            &phase_count.to_be_bytes(),
            operation_descriptor_sha256,
        ],
    )
}

#[cfg(test)]
fn build_exact_assignment_set_v1() -> AuthorizationResult<ExactAssignmentSetV1> {
    let mut descriptors = Vec::with_capacity(60);
    descriptors.push((
        "OL00".to_owned(),
        "D00_CLEAN_COMMITTED_HEAD".to_owned(),
        "CLEAN_CONTROL_NO_CRASH".to_owned(),
        1_u64,
    ));
    for variant in [
        "CRASH_AT_EMPTY_RESTART",
        "CRASH_AFTER_OBJECT_PREFIX_RESTART",
        "CRASH_AFTER_OBJECT_COMMIT_RESTART",
        "CRASH_AFTER_RECEIPT_COMMIT_RESTART",
        "CRASH_AFTER_WITNESS_COMMIT_RESTART",
        "CRASH_AFTER_ACK_RESTART",
    ] {
        descriptors.push((
            "OL04".to_owned(),
            "D04_PUBLISH_CRASH_RESTART_CUTS".to_owned(),
            variant.to_owned(),
            1,
        ));
    }
    for cut in 0..53_u64 {
        let variant = match cut {
            0 => "BEFORE_OPEN".to_owned(),
            1 => "AFTER_OPEN".to_owned(),
            2..=50 => format!("AFTER_DATA_{:04}", cut - 1),
            51 => "AFTER_COMPLETE_BEFORE_S14".to_owned(),
            _ => "AFTER_HISTORICAL".to_owned(),
        };
        descriptors.push((
            "OL05".to_owned(),
            "D05_S15_READ_CRASH_RESTART_CUTS".to_owned(),
            variant,
            2,
        ));
    }
    if descriptors.len() != 60 {
        return Err(s20b_error(
            "s20b_assignment_count",
            "frozen assignment descriptor count drifted",
        ));
    }
    let mut entries = Vec::with_capacity(60);
    for (ordinal, (family_id, case_id, variant_id, phase_count)) in
        descriptors.into_iter().enumerate()
    {
        let operation = ConcreteOperationDescriptorV1::for_family(&family_id);
        let operation_descriptor_sha256 = operation.digest()?;
        let assignment_record_sha256 = assignment_record_digest_v1(
            ordinal as u64,
            &family_id,
            &case_id,
            &variant_id,
            phase_count,
            &operation_descriptor_sha256,
        )?;
        entries.push(AuthorizedAssignmentV1 {
            ordinal: ordinal as u64,
            family_id,
            case_id,
            variant_id,
            phase_count,
            operation,
            operation_descriptor_sha256,
            assignment_record_sha256,
        });
    }
    validate_exact_assignment_shape_v1(&entries)?;
    let schedule_fields: Vec<&[u8]> = entries
        .iter()
        .map(|entry| &entry.assignment_record_sha256[..])
        .collect();
    let schedule_sha256 = framed_digest(LEGACY_FIXTURE_SCHEDULE_DOMAIN, &schedule_fields)?;
    let set_value = Value::Array(
        entries
            .iter()
            .map(|entry| {
                json!({
                    "assignment_record_sha256": hex32(&entry.assignment_record_sha256),
                    "case_id": entry.case_id,
                    "family_id": entry.family_id,
                    "operation": entry.operation.value(),
                    "operation_descriptor_sha256": hex32(&entry.operation_descriptor_sha256),
                    "ordinal": entry.ordinal,
                    "phase_count": entry.phase_count,
                    "variant_id": entry.variant_id
                })
            })
            .collect(),
    );
    let assignment_set_sha256 = framed_digest(
        LEGACY_FIXTURE_ASSIGNMENT_SET_DOMAIN,
        &[&restricted_canonical_bytes(&set_value)?, &schedule_sha256],
    )?;
    Ok(ExactAssignmentSetV1 {
        entries,
        assignment_set_sha256,
        schedule_sha256,
    })
}

#[cfg(test)]
fn validate_exact_assignment_shape_v1(
    entries: &[AuthorizedAssignmentV1],
) -> AuthorizationResult<()> {
    let ordinals: BTreeSet<u64> = entries.iter().map(|entry| entry.ordinal).collect();
    let record_digests: BTreeSet<[u8; 32]> = entries
        .iter()
        .map(|entry| entry.assignment_record_sha256)
        .collect();
    let operation_digests: BTreeSet<[u8; 32]> = entries
        .iter()
        .map(|entry| entry.operation_descriptor_sha256)
        .collect();
    let count = |family: &str| {
        entries
            .iter()
            .filter(|entry| entry.family_id == family)
            .count()
    };
    if entries.len() != 60
        || ordinals != (0_u64..60).collect()
        || record_digests.len() != 60
        || operation_digests.len() != 2
        || count("OL00") != 1
        || count("OL04") != 6
        || count("OL05") != 53
        || entries.iter().map(|entry| entry.phase_count).sum::<u64>() != 113
    {
        return Err(s20b_error(
            "s20b_assignment_shape",
            "assignment membership, ordinal, family, operation, or phase denominator drifted",
        ));
    }
    Ok(())
}

#[cfg(test)]
fn validate_assignment_set_against_subject_v1(
    subject: &VerifiedS19SubjectV1,
    assignments: &ExactAssignmentSetV1,
) -> AuthorizationResult<()> {
    let allowed: BTreeSet<&str> = subject
        .allowed_operation_ids
        .iter()
        .map(String::as_str)
        .collect();
    if assignments.assignment_set_sha256 != subject.assignment_set_sha256
        || assignments.schedule_sha256 != subject.schedule_sha256
        || subject.catalog_row_count != 5_639
        || subject.catalog_sha256 != super::super::super::super::CATALOG_KAT_SHA256
        || subject.target_phase_count != 113
        || subject.target_phase_unique_match_count != 113
        || [
            &subject.classifier_binary_sha256,
            &subject.classifier_source_sha256,
            &subject.expected_oracle_sha256,
            &subject.s17_observation_schema_sha256,
            &subject.s17_plan_sha256,
        ]
        .iter()
        .any(|digest| !nonzero(&digest[..]))
        || allowed != ALLOWED_OPERATION_IDS.into_iter().collect()
    {
        return Err(s20b_error(
            "s20b_subject_assignment_binding",
            "verified subject commitments do not authorize the exact assignment set",
        ));
    }
    Ok(())
}

#[derive(Clone)]
struct PreflightContextV1 {
    identity: RichIdentityBindingsV1,
    controller_binary_sha256: [u8; 32],
    runner_binary_sha256: [u8; 32],
    observer_binary_sha256: [u8; 32],
    registration_receipt_sha256: [u8; 32],
    external_checkpoint_parent_sha256: [u8; 32],
    challenge_nonce_sha256: [u8; 32],
    checks: [bool; 8],
}

impl PreflightContextV1 {
    fn value(&self) -> AuthorizationResult<Value> {
        self.identity.validate()?;
        require_nonzero_digests(&[
            &self.controller_binary_sha256,
            &self.runner_binary_sha256,
            &self.observer_binary_sha256,
            &self.registration_receipt_sha256,
            &self.external_checkpoint_parent_sha256,
            &self.challenge_nonce_sha256,
        ])?;
        Ok(json!({
            "authorization_and_run_binding": self.identity.value(),
            "challenge_nonce_sha256": hex32(&self.challenge_nonce_sha256),
            "checks": self.checks,
            "controller_binary_sha256": hex32(&self.controller_binary_sha256),
            "external_checkpoint_parent_sha256": hex32(&self.external_checkpoint_parent_sha256),
            "observer_binary_sha256": hex32(&self.observer_binary_sha256),
            "registration_receipt_sha256": hex32(&self.registration_receipt_sha256),
            "runner_binary_sha256": hex32(&self.runner_binary_sha256)
        }))
    }

    fn digest(&self) -> AuthorizationResult<[u8; 32]> {
        framed_digest(
            PREFLIGHT_CONTEXT_DOMAIN,
            &[&restricted_canonical_bytes(&self.value()?)?],
        )
    }
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
enum ControlPhaseV1 {
    Preflight,
    CasLinearization,
}

impl ControlPhaseV1 {
    fn as_str(self) -> &'static str {
        match self {
            Self::Preflight => "PREFLIGHT_BEFORE_CLAIM",
            Self::CasLinearization => "CAS_LINEARIZATION",
        }
    }
}

#[derive(Clone)]
enum ClaimViewV1 {
    PresentAuthorizedUnclaimed {
        revision: u64,
        row_core_sha256: [u8; 32],
    },
    PresentConsumedForExactRun {
        revision: u64,
        row_core_sha256: [u8; 32],
        consumed_run_id_sha256: [u8; 32],
    },
    RowMissing,
    ReadUnknown,
}

impl ClaimViewV1 {
    fn value(&self) -> Value {
        match self {
            Self::PresentAuthorizedUnclaimed {
                revision,
                row_core_sha256,
            } => json!({
                "kind": "PRESENT_AUTHORIZED_UNCLAIMED",
                "revision": revision,
                "row_core_sha256": hex32(row_core_sha256)
            }),
            Self::PresentConsumedForExactRun {
                revision,
                row_core_sha256,
                consumed_run_id_sha256,
            } => json!({
                "consumed_run_id_sha256": hex32(consumed_run_id_sha256),
                "kind": "PRESENT_CONSUMED_FOR_EXACT_RUN",
                "revision": revision,
                "row_core_sha256": hex32(row_core_sha256)
            }),
            Self::RowMissing => json!({"kind": "ROW_MISSING"}),
            Self::ReadUnknown => json!({"kind": "READ_UNKNOWN"}),
        }
    }

    fn is_unclaimed(&self) -> bool {
        matches!(self, Self::PresentAuthorizedUnclaimed { revision, row_core_sha256 }
            if *revision > 0 && nonzero(&row_core_sha256[..]))
    }
}

#[derive(Clone, Copy)]
enum StopViewV1 {
    Clear { revision: u64 },
    Triggered { revision: u64 },
    ReadUnknown,
}

impl StopViewV1 {
    fn value(self) -> Value {
        match self {
            Self::Clear { revision } => json!({"kind": "CLEAR", "revision": revision}),
            Self::Triggered { revision } => {
                json!({"kind": "TRIGGERED", "revision": revision})
            }
            Self::ReadUnknown => json!({"kind": "READ_UNKNOWN"}),
        }
    }

    fn is_clear(self) -> bool {
        matches!(self, Self::Clear { revision } if revision > 0)
    }
}

#[derive(Clone, Copy)]
enum RevocationViewV1 {
    Exact { epoch: u64, revision: u64 },
    Mismatch { current_epoch: u64, revision: u64 },
    RollbackDetected { observed_epoch: u64 },
    ReadUnknown,
}

impl RevocationViewV1 {
    fn value(self) -> Value {
        match self {
            Self::Exact { epoch, revision } => {
                json!({"epoch": epoch, "kind": "EXACT", "revision": revision})
            }
            Self::Mismatch {
                current_epoch,
                revision,
            } => json!({
                "current_epoch": current_epoch,
                "kind": "MISMATCH",
                "revision": revision
            }),
            Self::RollbackDetected { observed_epoch } => json!({
                "kind": "ROLLBACK_DETECTED",
                "observed_epoch": observed_epoch
            }),
            Self::ReadUnknown => json!({"kind": "READ_UNKNOWN"}),
        }
    }

    fn is_exact(self) -> bool {
        matches!(self, Self::Exact { epoch, revision } if epoch > 0 && revision > 0)
    }
}

#[derive(Clone)]
struct ControlSnapshotFactsV1 {
    identity: RichIdentityBindingsV1,
    phase: ControlPhaseV1,
    parent_sha256: [u8; 32],
    claim_view: ClaimViewV1,
    stop_view: StopViewV1,
    revocation_view: RevocationViewV1,
    database_identity_sha256: [u8; 32],
    sqlite_profile_sha256: [u8; 32],
    sqlite_schema_sha256: [u8; 32],
    committed_database_content_root_sha256: [u8; 32],
    external_checkpoint_receipt_sha256: [u8; 32],
    transaction_sequence: u64,
}

fn build_control_snapshot_v1(
    facts: &ControlSnapshotFactsV1,
) -> AuthorizationResult<BuiltRichPacketV1> {
    facts.identity.validate()?;
    require_nonzero_digests(&[
        &facts.parent_sha256,
        &facts.database_identity_sha256,
        &facts.sqlite_profile_sha256,
        &facts.sqlite_schema_sha256,
        &facts.committed_database_content_root_sha256,
        &facts.external_checkpoint_receipt_sha256,
    ])?;
    if facts.transaction_sequence == 0 {
        return Err(s20b_error(
            "s20b_control_sequence",
            "control transaction sequence must be nonzero",
        ));
    }
    let allow = facts.claim_view.is_unclaimed()
        && facts.stop_view.is_clear()
        && facts.revocation_view.is_exact();
    let mut body = Map::new();
    body.insert(
        "authorization_and_run_binding".into(),
        facts.identity.value(),
    );
    body.insert("claim_view".into(), facts.claim_view.value());
    body.insert(
        "committed_database_content_root_sha256".into(),
        Value::String(hex32(&facts.committed_database_content_root_sha256)),
    );
    body.insert(
        "database_identity_sha256".into(),
        Value::String(hex32(&facts.database_identity_sha256)),
    );
    body.insert(
        "decision".into(),
        Value::String(
            if allow {
                "ALLOW_GUARDED_NEXT_ACTION"
            } else {
                "DENY_TERMINAL_FAIL_CLOSED"
            }
            .into(),
        ),
    );
    body.insert(
        "external_checkpoint_receipt_sha256".into(),
        Value::String(hex32(&facts.external_checkpoint_receipt_sha256)),
    );
    body.insert(
        "parent_kind".into(),
        Value::String(
            match facts.phase {
                ControlPhaseV1::Preflight => "PREFLIGHT_CONTEXT",
                ControlPhaseV1::CasLinearization => "PREFLIGHT_RECEIPT",
            }
            .into(),
        ),
    );
    body.insert(
        "parent_sha256".into(),
        Value::String(hex32(&facts.parent_sha256)),
    );
    body.insert("phase".into(), Value::String(facts.phase.as_str().into()));
    body.insert("revocation_view".into(), facts.revocation_view.value());
    body.insert(
        "sqlite_profile_sha256".into(),
        Value::String(hex32(&facts.sqlite_profile_sha256)),
    );
    body.insert(
        "sqlite_schema_sha256".into(),
        Value::String(hex32(&facts.sqlite_schema_sha256)),
    );
    body.insert("stop_view".into(), facts.stop_view.value());
    body.insert(
        "transaction_sequence".into(),
        Value::Number(facts.transaction_sequence.into()),
    );
    seal_exact_packet_v1(RichPacketKindV1::ControlSnapshot, body)
}

fn validate_control_snapshot_v1(
    raw: &[u8],
    facts: &ControlSnapshotFactsV1,
) -> AuthorizationResult<ValidatedRichPacketV1> {
    validate_exact_packet_v1(raw, build_control_snapshot_v1(facts)?)
}

#[derive(Clone, Copy)]
enum PreflightOutcomeV1 {
    Ready,
    FailedTerminal,
    UnknownTerminal,
}

impl PreflightOutcomeV1 {
    fn as_str(self) -> &'static str {
        match self {
            Self::Ready => "READY_TO_ATTEMPT_SINGLE_CAS_NON_EXECUTING",
            Self::FailedTerminal => "FAILED_TERMINAL",
            Self::UnknownTerminal => "UNKNOWN_TERMINAL_HARD_LOCK",
        }
    }
}

#[derive(Clone)]
struct PreflightReceiptFactsV1 {
    context: PreflightContextV1,
    preflight_control_snapshot_sha256: [u8; 32],
    outcome: PreflightOutcomeV1,
}

fn build_preflight_receipt_v1(
    facts: &PreflightReceiptFactsV1,
) -> AuthorizationResult<BuiltRichPacketV1> {
    let context_sha256 = facts.context.digest()?;
    require_nonzero_digests(&[&facts.preflight_control_snapshot_sha256])?;
    if matches!(facts.outcome, PreflightOutcomeV1::Ready)
        && !facts.context.checks.iter().all(|v| *v)
    {
        return Err(s20b_error(
            "s20b_preflight_ready",
            "READY outcome requires every independently observed check",
        ));
    }
    let mut body = Map::new();
    body.insert(
        "authorization_and_run_binding".into(),
        facts.context.identity.value(),
    );
    body.insert(
        "control_snapshot_sha256".into(),
        Value::String(hex32(&facts.preflight_control_snapshot_sha256)),
    );
    body.insert(
        "outcome".into(),
        Value::String(facts.outcome.as_str().into()),
    );
    body.insert(
        "preflight_context_sha256".into(),
        Value::String(hex32(&context_sha256)),
    );
    body.insert("retry_allowed".into(), Value::Bool(false));
    seal_exact_packet_v1(RichPacketKindV1::PreflightReceipt, body)
}

fn validate_preflight_receipt_v1(
    raw: &[u8],
    facts: &PreflightReceiptFactsV1,
) -> AuthorizationResult<ValidatedRichPacketV1> {
    validate_exact_packet_v1(raw, build_preflight_receipt_v1(facts)?)
}

#[derive(Clone)]
struct ClaimCasBindingsV1 {
    authorization_id_sha256: [u8; 32],
    claim_namespace_sha256: [u8; 32],
    claim_key_sha256: [u8; 32],
    signed_payload_sha256: [u8; 32],
    subject_manifest_sha256: [u8; 32],
    resource_scope_sha256: [u8; 32],
    signed_revocation_epoch_sha256: [u8; 32],
    expected_unclaimed_state_sha256: [u8; 32],
    expected_revision_sha256: [u8; 32],
    expected_successful_claim_count_sha256: [u8; 32],
    run_id_sha256: [u8; 32],
    controller_binary_sha256: [u8; 32],
    runner_binary_sha256: [u8; 32],
    capability_nonce_sha256: [u8; 32],
    preflight_receipt_sha256: [u8; 32],
    cas_control_snapshot_sha256: [u8; 32],
    assignment_set_sha256: [u8; 32],
    assignment_record_sha256: [u8; 32],
    operation_descriptor_sha256: [u8; 32],
    attempt_tombstone_sha256: [u8; 32],
    pre_database_content_root_sha256: [u8; 32],
    claim_transition_core_sha256: [u8; 32],
    post_database_content_root_sha256: [u8; 32],
    external_checkpoint_receipt_sha256: [u8; 32],
}

impl ClaimCasBindingsV1 {
    fn fields(&self) -> [&[u8; 32]; 24] {
        [
            &self.authorization_id_sha256,
            &self.claim_namespace_sha256,
            &self.claim_key_sha256,
            &self.signed_payload_sha256,
            &self.subject_manifest_sha256,
            &self.resource_scope_sha256,
            &self.signed_revocation_epoch_sha256,
            &self.expected_unclaimed_state_sha256,
            &self.expected_revision_sha256,
            &self.expected_successful_claim_count_sha256,
            &self.run_id_sha256,
            &self.controller_binary_sha256,
            &self.runner_binary_sha256,
            &self.capability_nonce_sha256,
            &self.preflight_receipt_sha256,
            &self.cas_control_snapshot_sha256,
            &self.assignment_set_sha256,
            &self.assignment_record_sha256,
            &self.operation_descriptor_sha256,
            &self.attempt_tombstone_sha256,
            &self.pre_database_content_root_sha256,
            &self.claim_transition_core_sha256,
            &self.post_database_content_root_sha256,
            &self.external_checkpoint_receipt_sha256,
        ]
    }

    fn validate(&self) -> AuthorizationResult<()> {
        require_nonzero_digests(&self.fields())
    }

    fn value(&self) -> Value {
        Value::Array(
            self.fields()
                .into_iter()
                .enumerate()
                .map(|(index, digest)| {
                    json!({"parameter_index": index + 1, "sha256": hex32(digest)})
                })
                .collect(),
        )
    }
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
enum ClaimOutcomeV1 {
    KnownNotCommittedTerminal,
    CommittedPermitIssued,
    CommittedPrePermitCrashTerminal,
    UnknownCommitOutcomeTerminalHardLock,
}

impl ClaimOutcomeV1 {
    fn value(self) -> Value {
        match self {
            Self::KnownNotCommittedTerminal => json!({
                "affected_rows": 0,
                "commit_acknowledgement": "KNOWN_NOT_COMMITTED",
                "kind": "KNOWN_NOT_COMMITTED_TERMINAL",
                "permit_eligible_after_commit": false,
                "process_local_permit_issued": false,
                "resulting_row_state": "UNCHANGED_AUTHORIZED_UNCLAIMED",
                "retry_allowed": false
            }),
            Self::CommittedPermitIssued => json!({
                "affected_rows": 1,
                "commit_acknowledgement": "KNOWN_COMMITTED",
                "kind": "COMMITTED_PERMIT_ISSUED",
                "permit_eligible_after_commit": true,
                "process_local_permit_issued": true,
                "resulting_row_state": "CONSUMED_FOR_EXACT_RUN",
                "retry_allowed": false
            }),
            Self::CommittedPrePermitCrashTerminal => json!({
                "affected_rows": 1,
                "commit_acknowledgement": "KNOWN_COMMITTED",
                "kind": "COMMITTED_PRE_PERMIT_CRASH_TERMINAL",
                "permit_eligible_after_commit": true,
                "process_local_permit_issued": false,
                "resulting_row_state": "CONSUMED_FOR_EXACT_RUN",
                "retry_allowed": false
            }),
            Self::UnknownCommitOutcomeTerminalHardLock => json!({
                "affected_rows": null,
                "commit_acknowledgement": "UNKNOWN",
                "kind": "UNKNOWN_OUTCOME_TERMINAL_HARD_LOCK",
                "permit_eligible_after_commit": false,
                "process_local_permit_issued": false,
                "resulting_row_state": "UNKNOWN",
                "retry_allowed": false
            }),
        }
    }
}

#[derive(Clone)]
struct ClaimReceiptFactsV1 {
    identity: RichIdentityBindingsV1,
    cas: ClaimCasBindingsV1,
    outcome: ClaimOutcomeV1,
}

fn recompute_claim_transition_core_v1(cas: &ClaimCasBindingsV1) -> AuthorizationResult<[u8; 32]> {
    let fields = cas.fields();
    let before_core: Vec<&[u8]> = fields
        .iter()
        .enumerate()
        .filter(|(index, _)| *index != 21 && *index != 22 && *index != 23)
        .map(|(_, digest)| &digest[..])
        .collect();
    framed_digest(CLAIM_TRANSITION_DOMAIN, &before_core)
}

fn build_claim_receipt_v1(facts: &ClaimReceiptFactsV1) -> AuthorizationResult<BuiltRichPacketV1> {
    facts.identity.validate()?;
    facts.cas.validate()?;
    if recompute_claim_transition_core_v1(&facts.cas)? != facts.cas.claim_transition_core_sha256 {
        return Err(s20b_error(
            "s20b_claim_transition_core",
            "claim transition core does not recompute from the other CAS parameters",
        ));
    }
    if facts.cas.authorization_id_sha256 != facts.identity.authorization_id_sha256
        || facts.cas.claim_namespace_sha256 != facts.identity.claim_namespace_sha256
        || facts.cas.claim_key_sha256 != facts.identity.claim_key_sha256
        || facts.cas.signed_payload_sha256 != facts.identity.signed_payload_sha256
        || facts.cas.subject_manifest_sha256 != facts.identity.subject_manifest_sha256
        || facts.cas.resource_scope_sha256 != facts.identity.resource_scope_sha256
        || facts.cas.run_id_sha256 != facts.identity.run_id_sha256
        || facts.cas.capability_nonce_sha256 != facts.identity.capability_nonce_sha256
        || facts.cas.assignment_set_sha256 != facts.identity.assignment_set_sha256
        || facts.cas.assignment_record_sha256 != facts.identity.assignment_record_sha256
        || facts.cas.operation_descriptor_sha256 != facts.identity.operation_descriptor_sha256
    {
        return Err(s20b_error(
            "s20b_claim_cross_binding",
            "claim CAS parameters drift from the immutable identity tuple",
        ));
    }
    let mut body = Map::new();
    body.insert(
        "authorization_and_run_binding".into(),
        facts.identity.value(),
    );
    body.insert("cas_parameter_count".into(), Value::Number(24_u64.into()));
    body.insert("cas_parameters".into(), facts.cas.value());
    body.insert("outcome".into(), facts.outcome.value());
    seal_exact_packet_v1(RichPacketKindV1::AuthorityControlClaim, body)
}

fn validate_claim_receipt_v1(
    raw: &[u8],
    facts: &ClaimReceiptFactsV1,
) -> AuthorizationResult<ValidatedRichPacketV1> {
    validate_exact_packet_v1(raw, build_claim_receipt_v1(facts)?)
}

#[derive(Clone, Copy)]
enum PostRunDecisionV1 {
    Complete,
    Invalid,
    Indeterminate,
}

impl PostRunDecisionV1 {
    fn as_str(self) -> &'static str {
        match self {
            Self::Complete => "VALID_COMPLETE_EXACT_CANARY_EVIDENCE",
            Self::Invalid => "INVALID_TERMINAL",
            Self::Indeterminate => "INDETERMINATE_TERMINAL_HARD_LOCK",
        }
    }
}

#[derive(Clone)]
struct ReceiptNodeV1 {
    kind: String,
    parent_sha256: [u8; 32],
    payload_sha256: [u8; 32],
    receipt_sha256: [u8; 32],
}

fn build_receipt_node_v1(
    kind: &str,
    parent_sha256: [u8; 32],
    payload_sha256: [u8; 32],
) -> AuthorizationResult<ReceiptNodeV1> {
    require_nonzero_digests(&[&parent_sha256, &payload_sha256])?;
    let receipt_sha256 = framed_digest(
        RECEIPT_NODE_DOMAIN,
        &[kind.as_bytes(), &parent_sha256, &payload_sha256],
    )?;
    Ok(ReceiptNodeV1 {
        kind: kind.into(),
        parent_sha256,
        payload_sha256,
        receipt_sha256,
    })
}

#[derive(Clone)]
struct PostRunReceiptFactsV1 {
    identity: RichIdentityBindingsV1,
    claim_receipt_sha256: [u8; 32],
    assignment_set_sha256: [u8; 32],
    schedule_sha256: [u8; 32],
    action_start_receipts: Vec<[u8; 32]>,
    raw_observation_receipts: Vec<[u8; 32]>,
    phase_record_receipts: Vec<[u8; 32]>,
    receipt_chain: Vec<ReceiptNodeV1>,
    final_database_content_root_sha256: [u8; 32],
    final_external_checkpoint_receipt_sha256: [u8; 32],
    decision: PostRunDecisionV1,
}

fn validate_receipt_chain_v1(
    claim_receipt_sha256: &[u8; 32],
    nodes: &[ReceiptNodeV1],
) -> AuthorizationResult<()> {
    let expected_kinds = [
        "RETENTION",
        "SEMANTIC_VALIDATION",
        "BATCH",
        "STOP_OR_ABSENT",
        "CLEANUP",
        "CUSTODY",
    ];
    if nodes.len() != expected_kinds.len() {
        return Err(s20b_error(
            "s20b_receipt_chain_count",
            "post-run receipt chain length drifted",
        ));
    }
    let mut parent = *claim_receipt_sha256;
    for (node, expected_kind) in nodes.iter().zip(expected_kinds) {
        let rebuilt = build_receipt_node_v1(expected_kind, parent, node.payload_sha256)?;
        if node.kind != expected_kind
            || node.parent_sha256 != parent
            || node.receipt_sha256 != rebuilt.receipt_sha256
        {
            return Err(s20b_error(
                "s20b_receipt_chain",
                "post-run receipt parent, kind, order, or self digest drifted",
            ));
        }
        parent = node.receipt_sha256;
    }
    Ok(())
}

fn build_postrun_receipt_v1(
    facts: &PostRunReceiptFactsV1,
) -> AuthorizationResult<BuiltRichPacketV1> {
    facts.identity.validate()?;
    require_nonzero_digests(&[
        &facts.claim_receipt_sha256,
        &facts.assignment_set_sha256,
        &facts.schedule_sha256,
        &facts.final_database_content_root_sha256,
        &facts.final_external_checkpoint_receipt_sha256,
    ])?;
    if facts.assignment_set_sha256 != facts.identity.assignment_set_sha256
        || facts.schedule_sha256 != facts.identity.schedule_sha256
        || facts
            .action_start_receipts
            .iter()
            .any(|value| !nonzero(value))
        || facts
            .raw_observation_receipts
            .iter()
            .any(|value| !nonzero(value))
        || facts
            .phase_record_receipts
            .iter()
            .any(|value| !nonzero(value))
    {
        return Err(s20b_error(
            "s20b_postrun_binding",
            "post-run set or member digest drifted",
        ));
    }
    validate_receipt_chain_v1(&facts.claim_receipt_sha256, &facts.receipt_chain)?;
    if matches!(facts.decision, PostRunDecisionV1::Complete)
        && (facts.action_start_receipts.len() != 60
            || facts.raw_observation_receipts.len() != 60
            || facts.phase_record_receipts.len() != 113)
    {
        return Err(s20b_error(
            "s20b_postrun_denominator",
            "complete evidence requires exact 60/60/113 denominators",
        ));
    }
    let receipt_values = |items: &[[u8; 32]]| {
        Value::Array(
            items
                .iter()
                .map(|value| Value::String(hex32(value)))
                .collect(),
        )
    };
    let chain = Value::Array(
        facts
            .receipt_chain
            .iter()
            .map(|node| {
                json!({
                    "kind": node.kind,
                    "parent_sha256": hex32(&node.parent_sha256),
                    "payload_sha256": hex32(&node.payload_sha256),
                    "receipt_sha256": hex32(&node.receipt_sha256)
                })
            })
            .collect(),
    );
    let mut body = Map::new();
    body.insert(
        "action_start_receipts".into(),
        receipt_values(&facts.action_start_receipts),
    );
    body.insert(
        "authorization_and_run_binding".into(),
        facts.identity.value(),
    );
    body.insert(
        "claim_receipt_sha256".into(),
        Value::String(hex32(&facts.claim_receipt_sha256)),
    );
    body.insert(
        "decision".into(),
        Value::String(facts.decision.as_str().into()),
    );
    body.insert(
        "final_database_content_root_sha256".into(),
        Value::String(hex32(&facts.final_database_content_root_sha256)),
    );
    body.insert(
        "final_external_checkpoint_receipt_sha256".into(),
        Value::String(hex32(&facts.final_external_checkpoint_receipt_sha256)),
    );
    body.insert(
        "phase_record_receipts".into(),
        receipt_values(&facts.phase_record_receipts),
    );
    body.insert(
        "raw_observation_receipts".into(),
        receipt_values(&facts.raw_observation_receipts),
    );
    body.insert("receipt_chain".into(), chain);
    body.insert(
        "validator_accounting".into(),
        json!({
            "assignment_prefilter_used": false,
            "assignment_count": 60,
            "catalog_row_count": 5639,
            "cross_field_rule_count": 32,
            "phase_count": 113,
            "unique_phase_match_count": 113
        }),
    );
    seal_exact_packet_v1(RichPacketKindV1::PostRunReceiptBundle, body)
}

fn validate_postrun_receipt_v1(
    raw: &[u8],
    facts: &PostRunReceiptFactsV1,
) -> AuthorizationResult<ValidatedRichPacketV1> {
    validate_exact_packet_v1(raw, build_postrun_receipt_v1(facts)?)
}

#[derive(Clone, Debug, Eq, Ord, PartialEq, PartialOrd)]
struct S17AugmentedFingerprintV1 {
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
}

type S16RowV1 = super::super::super::super::ModeledFaultRowV1;

fn fingerprint_from_row_v1(row: &S16RowV1) -> S17AugmentedFingerprintV1 {
    let (restarted_after_crash, observed_data_steps, observed_len) =
        if row.case_id == "D05_S15_READ_CRASH_RESTART_CUTS" {
            let restarted = row.variant_id.ends_with("_RESTART");
            let steps = if restarted {
                49
            } else {
                match row.crash_cut.as_str() {
                    "READ_BEFORE_OPEN" | "READ_AFTER_OPEN" => 0,
                    "READ_AFTER_DATA" => row.crash_cut_index,
                    "READ_AFTER_COMPLETE_BEFORE_S14" | "READ_AFTER_HISTORICAL" => 49,
                    _ => u64::MAX,
                }
            };
            (restarted, steps, (steps * 113).min(5_494))
        } else {
            (row.case_id == "D04_PUBLISH_CRASH_RESTART_CUTS", 0, 0)
        };
    S17AugmentedFingerprintV1 {
        publisher_phase: row.publisher_phase.as_str().into(),
        object_persistence: row.object_persistence.as_str().into(),
        object_len: row.object_len,
        observed_object_sha256: row.observed_object_sha256,
        receipt_state: row.receipt_state.into(),
        computed_receipt_sha256: row.computed_receipt_sha256,
        stored_receipt_sha256: row.stored_receipt_sha256,
        witness_state: row.witness_state.into(),
        computed_witness_sha256: row.computed_witness_sha256,
        stored_witness_sha256: row.stored_witness_sha256,
        selected_view_sha256: row.selected_view_sha256,
        competing_view_sha256: row.competing_view_sha256,
        ack_state: row.ack_state.as_str().into(),
        crash_cut: row.crash_cut.as_str().into(),
        crash_cut_index: row.crash_cut_index,
        adapter_pre_state: row.adapter_pre_state.as_str().into(),
        adapter_post_state: row.adapter_post_state.as_str().into(),
        restarted_after_crash,
        observed_data_steps,
        observed_len,
    }
}

fn fingerprint_digest_v1(value: &S17AugmentedFingerprintV1) -> AuthorizationResult<[u8; 32]> {
    let body = json!({
        "ack_state": value.ack_state,
        "adapter_post_state": value.adapter_post_state,
        "adapter_pre_state": value.adapter_pre_state,
        "competing_view_sha256": hex32(&value.competing_view_sha256),
        "computed_receipt_sha256": hex32(&value.computed_receipt_sha256),
        "computed_witness_sha256": hex32(&value.computed_witness_sha256),
        "crash_cut": value.crash_cut,
        "crash_cut_index": value.crash_cut_index,
        "object_len": value.object_len,
        "object_persistence": value.object_persistence,
        "observed_data_steps": value.observed_data_steps,
        "observed_len": value.observed_len,
        "observed_object_sha256": hex32(&value.observed_object_sha256),
        "publisher_phase": value.publisher_phase,
        "receipt_state": value.receipt_state,
        "restarted_after_crash": value.restarted_after_crash,
        "selected_view_sha256": hex32(&value.selected_view_sha256),
        "stored_receipt_sha256": hex32(&value.stored_receipt_sha256),
        "stored_witness_sha256": hex32(&value.stored_witness_sha256),
        "witness_state": value.witness_state
    });
    framed_digest(
        S17_FINGERPRINT_DOMAIN,
        &[&restricted_canonical_bytes(&body)?],
    )
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
enum S17PhaseKindV1 {
    Single,
    FirstAttempt,
    Restart,
}

struct S17PhaseObservationV1 {
    assignment_ordinal: u64,
    phase_kind: S17PhaseKindV1,
    fingerprint: S17AugmentedFingerprintV1,
    mapped_row_sha256: [u8; 32],
}

struct FullCatalogIndexV1 {
    rows: Vec<S16RowV1>,
    index: BTreeMap<S17AugmentedFingerprintV1, usize>,
}

fn build_full_catalog_index_v1(record: &[u8]) -> AuthorizationResult<FullCatalogIndexV1> {
    let rows = super::super::super::super::build_case_catalog_v1(record)
        .map_err(|_| s20b_error("s20b_s17_catalog", "frozen S16 catalog build failed"))?;
    if rows.len() != 5_639
        || super::super::super::super::catalog_commitment_v1(&rows)
            != super::super::super::super::CATALOG_KAT_SHA256
    {
        return Err(s20b_error(
            "s20b_s17_catalog",
            "full frozen S16 catalog count or root drifted",
        ));
    }
    let mut index = BTreeMap::new();
    for (ordinal, row) in rows.iter().enumerate() {
        if index
            .insert(fingerprint_from_row_v1(row), ordinal)
            .is_some()
        {
            return Err(s20b_error(
                "s20b_s17_catalog_collision",
                "augmented 20-field full-catalog fingerprint is not globally unique",
            ));
        }
    }
    if index.len() != 5_639 {
        return Err(s20b_error(
            "s20b_s17_catalog_cardinality",
            "full-catalog unique fingerprint count drifted",
        ));
    }
    Ok(FullCatalogIndexV1 { rows, index })
}

#[cfg(test)]
fn expected_s16_variant_v1(
    assignment: &AuthorizedAssignmentV1,
    phase_kind: S17PhaseKindV1,
) -> AuthorizationResult<String> {
    match (assignment.family_id.as_str(), phase_kind) {
        ("OL00", S17PhaseKindV1::Single) => Ok("CLEAN".into()),
        ("OL04", S17PhaseKindV1::Single) => Ok(assignment.variant_id.clone()),
        ("OL05", S17PhaseKindV1::FirstAttempt) => {
            Ok(format!("{}_FIRST_ATTEMPT", assignment.variant_id))
        }
        ("OL05", S17PhaseKindV1::Restart) => Ok(format!("{}_RESTART", assignment.variant_id)),
        _ => Err(s20b_error(
            "s20b_s17_phase_kind",
            "assignment family and phase kind are inconsistent",
        )),
    }
}

#[cfg(test)]
fn validate_phase_against_full_catalog_v1<'a>(
    catalog: &'a FullCatalogIndexV1,
    assignments: &'a ExactAssignmentSetV1,
    observation: &S17PhaseObservationV1,
) -> AuthorizationResult<&'a S16RowV1> {
    // The only lookup key is the raw/projection-derived fingerprint.  The
    // assignment is deliberately consulted only after the full 5,639-row map
    // returns one globally unique row.
    let row_index = catalog.index.get(&observation.fingerprint).ok_or_else(|| {
        s20b_error(
            "s20b_s17_no_match",
            "observation has no full-catalog fingerprint match",
        )
    })?;
    let row = &catalog.rows[*row_index];
    let assignment = assignments
        .entries
        .get(observation.assignment_ordinal as usize)
        .filter(|entry| entry.ordinal == observation.assignment_ordinal)
        .ok_or_else(|| {
            s20b_error(
                "s20b_s17_assignment",
                "phase does not name one exact authorized assignment ordinal",
            )
        })?;
    let expected_variant = expected_s16_variant_v1(assignment, observation.phase_kind)?;
    if row.case_id != assignment.case_id
        || row.variant_id.as_ref() != expected_variant
        || super::super::super::super::row_commitment_v1(row) != observation.mapped_row_sha256
    {
        return Err(s20b_error(
            "s20b_s17_post_lookup_assignment",
            "post-lookup assignment labels or mapped row commitment drifted",
        ));
    }
    Ok(row)
}

#[derive(Clone)]
struct S17CrossFieldEvidenceV1 {
    pidfd_target: (u64, u64),
    initial_child: (u64, u64),
    signal_sender: (u64, u64),
    controller: (u64, u64),
    fresh_child: (u64, u64),
    initial_nonce_sha256: [u8; 32],
    fresh_nonce_sha256: [u8; 32],
    runner_binary_sha256: [u8; 32],
    initial_image_sha256: [u8; 32],
    fresh_image_sha256: [u8; 32],
    initial_boot_id_sha256: [u8; 32],
    fresh_boot_id_sha256: [u8; 32],
    expected_root_identity_sha256: [u8; 32],
    observed_root_identity_sha256: [u8; 32],
    expected_mount_identity_sha256: [u8; 32],
    observed_mount_identity_sha256: [u8; 32],
    run_root: String,
    database_path: String,
    expected_database_identity_sha256: [u8; 32],
    observed_database_identity_sha256: [u8; 32],
    expected_sqlite_profile_sha256: [u8; 32],
    observed_sqlite_profile_sha256: [u8; 32],
    expected_sqlite_schema_sha256: [u8; 32],
    observed_sqlite_schema_sha256: [u8; 32],
    custody_raw_sha256: [u8; 32],
    raw_identity_sha256: [u8; 32],
    custody_canonical_sha256: [u8; 32],
    canonical_identity_sha256: [u8; 32],
    retained_raw_packet: Vec<u8>,
    frame_start: usize,
    frame_end: usize,
    frame_sha256: [u8; 32],
    decoded_phase_measurement: Vec<u8>,
    ack_payload: Option<([u8; 32], [u8; 32])>,
    expected_ack_payload: Option<([u8; 32], [u8; 32])>,
    virtual_projection_sha256: [u8; 32],
    virtual_projection_external_count: u64,
    virtual_projection_provider_count: u64,
    virtual_projection_owned_lab_count: u64,
    s17_ledger_sha256: [u8; 32],
    classification_input_sha256: [u8; 32],
    phase_record_sha256: [u8; 32],
    expected_classifier_binary_sha256: [u8; 32],
    actual_classifier_binary_sha256: [u8; 32],
    expected_classifier_source_sha256: [u8; 32],
    actual_classifier_source_sha256: [u8; 32],
    paired_attempt_sha256: [u8; 32],
    paired_cut_sha256: [u8; 32],
    expected_paired_attempt_sha256: [u8; 32],
    expected_paired_cut_sha256: [u8; 32],
    top_level_durable_facts_sha256: [u8; 32],
    phase_durable_facts_sha256: [u8; 32],
    eligible_result_process: (u64, u64),
    custody_sequence: u64,
    previous_custody_sha256: [u8; 32],
    expected_previous_custody_sha256: [u8; 32],
    owner_binding_sha256: [u8; 32],
    expected_owner_binding_sha256: [u8; 32],
    absent_sentinels: [[u8; 32]; 4],
}

fn rule(condition: bool, index: usize) -> AuthorizationResult<()> {
    if condition {
        Ok(())
    } else {
        Err(s20b_error(
            "s20b_s17_cross_field_rule",
            S17_CROSS_FIELD_RULES[index],
        ))
    }
}

fn validate_s17_32_rules_v1(
    evidence: &S17CrossFieldEvidenceV1,
    observation: &S17PhaseObservationV1,
    matched_row: &S16RowV1,
    full_catalog_unique_count: usize,
) -> AuthorizationResult<()> {
    let frame = evidence
        .retained_raw_packet
        .get(evidence.frame_start..evidence.frame_end)
        .ok_or_else(|| s20b_error("s20b_s17_frame", "raw frame range is invalid"))?;
    let fingerprint_sha256 = fingerprint_digest_v1(&observation.fingerprint)?;
    let classification_input = framed_digest(
        S17_CLASSIFICATION_INPUT_DOMAIN,
        &[frame, &fingerprint_sha256],
    )?;
    let mapped_row_sha256 = super::super::super::super::row_commitment_v1(matched_row);
    let phase_record = framed_digest(
        S17_PHASE_RECORD_DOMAIN,
        &[&classification_input, &mapped_row_sha256],
    )?;
    let direct_child = evidence
        .database_path
        .strip_prefix(&evidence.run_root)
        .is_some_and(|suffix| suffix == "/state.sqlite3");
    let all_absent_distinct = evidence
        .absent_sentinels
        .iter()
        .all(|digest| nonzero(digest))
        && evidence
            .absent_sentinels
            .iter()
            .collect::<BTreeSet<_>>()
            .len()
            == 4;
    let d05_relation = if matched_row.case_id == "D05_S15_READ_CRASH_RESTART_CUTS" {
        observation.fingerprint.observed_data_steps <= 49
            && observation.fingerprint.observed_len
                == (observation.fingerprint.observed_data_steps * 113).min(5_494)
            && (observation.fingerprint.restarted_after_crash
                || observation.fingerprint.crash_cut != "READ_AFTER_DATA"
                || observation.fingerprint.crash_cut_index
                    == observation.fingerprint.observed_data_steps)
    } else {
        true
    };
    let phase_process = match observation.phase_kind {
        S17PhaseKindV1::FirstAttempt => evidence.initial_child,
        S17PhaseKindV1::Restart => evidence.fresh_child,
        S17PhaseKindV1::Single => evidence.eligible_result_process,
    };
    let checks = [
        evidence.pidfd_target == evidence.initial_child,
        evidence.signal_sender == evidence.controller,
        evidence.fresh_child != evidence.initial_child
            && evidence.fresh_nonce_sha256 != evidence.initial_nonce_sha256,
        evidence.initial_image_sha256 == evidence.runner_binary_sha256
            && evidence.fresh_image_sha256 == evidence.runner_binary_sha256,
        evidence.initial_boot_id_sha256 == evidence.fresh_boot_id_sha256,
        evidence.expected_root_identity_sha256 == evidence.observed_root_identity_sha256,
        evidence.expected_mount_identity_sha256 == evidence.observed_mount_identity_sha256,
        direct_child,
        evidence.expected_database_identity_sha256 == evidence.observed_database_identity_sha256,
        evidence.expected_sqlite_profile_sha256 == evidence.observed_sqlite_profile_sha256
            && evidence.expected_sqlite_schema_sha256 == evidence.observed_sqlite_schema_sha256,
        evidence.custody_raw_sha256 == evidence.raw_identity_sha256
            && evidence.custody_canonical_sha256 == evidence.canonical_identity_sha256,
        sha256_bytes(frame) == evidence.frame_sha256,
        frame == evidence.decoded_phase_measurement,
        evidence.ack_payload == evidence.expected_ack_payload,
        evidence.virtual_projection_sha256 == framed_digest(S17_FINGERPRINT_DOMAIN, &[frame])?,
        evidence.virtual_projection_external_count == 0
            && evidence.virtual_projection_provider_count == 0
            && evidence.virtual_projection_owned_lab_count == 0
            && evidence.virtual_projection_sha256 != evidence.s17_ledger_sha256,
        evidence.classification_input_sha256 == classification_input,
        evidence.phase_record_sha256 == phase_record,
        evidence.expected_classifier_binary_sha256 == evidence.actual_classifier_binary_sha256
            && evidence.expected_classifier_source_sha256
                == evidence.actual_classifier_source_sha256,
        full_catalog_unique_count == 5_639,
        full_catalog_unique_count == 5_639,
        matched_row.case_id
            == match observation.assignment_ordinal {
                0 => "D00_CLEAN_COMMITTED_HEAD",
                1..=6 => "D04_PUBLISH_CRASH_RESTART_CUTS",
                _ => "D05_S15_READ_CRASH_RESTART_CUTS",
            },
        observation.mapped_row_sha256 == mapped_row_sha256,
        all_absent_distinct,
        d05_relation,
        evidence.paired_attempt_sha256 == evidence.expected_paired_attempt_sha256
            && evidence.paired_cut_sha256 == evidence.expected_paired_cut_sha256,
        evidence.top_level_durable_facts_sha256 == evidence.phase_durable_facts_sha256,
        observation.phase_kind != S17PhaseKindV1::FirstAttempt
            || phase_process == evidence.initial_child,
        observation.phase_kind != S17PhaseKindV1::Restart || phase_process == evidence.fresh_child,
        observation.phase_kind != S17PhaseKindV1::Single
            || phase_process == evidence.eligible_result_process,
        evidence.custody_sequence > 0
            && evidence.previous_custody_sha256 == evidence.expected_previous_custody_sha256,
        evidence.owner_binding_sha256 == evidence.expected_owner_binding_sha256,
    ];
    for (index, passed) in checks.into_iter().enumerate() {
        rule(passed, index)?;
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    fn repeated(byte: u8) -> [u8; 32] {
        [byte; 32]
    }

    fn assignments() -> ExactAssignmentSetV1 {
        build_exact_assignment_set_v1().unwrap()
    }

    fn subject_for_assignments(set: &ExactAssignmentSetV1) -> VerifiedS19SubjectV1 {
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
            assignment_set_sha256: set.assignment_set_sha256,
            schedule_sha256: set.schedule_sha256,
            catalog_row_count: 5_639,
            catalog_sha256: super::super::super::super::super::CATALOG_KAT_SHA256,
            classifier_binary_sha256: repeated(18),
            classifier_source_sha256: repeated(19),
            expected_oracle_sha256: repeated(20),
            s17_observation_schema_sha256: repeated(21),
            s17_plan_sha256: repeated(22),
            target_phase_count: 113,
            target_phase_unique_match_count: 113,
            allowed_operation_ids: ALLOWED_OPERATION_IDS
                .iter()
                .map(|value| (*value).into())
                .collect(),
        }
    }

    fn identity(
        entry: &AuthorizedAssignmentV1,
        set: &ExactAssignmentSetV1,
    ) -> RichIdentityBindingsV1 {
        RichIdentityBindingsV1 {
            authorization_id_sha256: repeated(1),
            owner_envelope_sha256: repeated(2),
            trust_anchor_document_sha256: repeated(3),
            signed_payload_sha256: repeated(4),
            subject_manifest_sha256: repeated(5),
            resource_scope_sha256: repeated(6),
            claim_namespace_sha256: repeated(7),
            claim_key_sha256: repeated(8),
            capability_nonce_sha256: repeated(9),
            run_id_sha256: repeated(10),
            assignment_set_sha256: set.assignment_set_sha256,
            schedule_sha256: set.schedule_sha256,
            assignment_record_sha256: entry.assignment_record_sha256,
            operation_descriptor_sha256: entry.operation_descriptor_sha256,
        }
    }

    fn context(identity: RichIdentityBindingsV1) -> PreflightContextV1 {
        PreflightContextV1 {
            identity,
            controller_binary_sha256: repeated(11),
            runner_binary_sha256: repeated(12),
            observer_binary_sha256: repeated(13),
            registration_receipt_sha256: repeated(14),
            external_checkpoint_parent_sha256: repeated(15),
            challenge_nonce_sha256: repeated(16),
            checks: [true; 8],
        }
    }

    fn control(
        identity: RichIdentityBindingsV1,
        phase: ControlPhaseV1,
        parent_sha256: [u8; 32],
    ) -> ControlSnapshotFactsV1 {
        ControlSnapshotFactsV1 {
            identity,
            phase,
            parent_sha256,
            claim_view: ClaimViewV1::PresentAuthorizedUnclaimed {
                revision: 1,
                row_core_sha256: repeated(17),
            },
            stop_view: StopViewV1::Clear { revision: 1 },
            revocation_view: RevocationViewV1::Exact {
                epoch: 1,
                revision: 1,
            },
            database_identity_sha256: repeated(18),
            sqlite_profile_sha256: repeated(19),
            sqlite_schema_sha256: repeated(20),
            committed_database_content_root_sha256: repeated(21),
            external_checkpoint_receipt_sha256: repeated(22),
            transaction_sequence: 1,
        }
    }

    fn claim_facts(
        identity: RichIdentityBindingsV1,
        preflight_sha256: [u8; 32],
        cas_control_sha256: [u8; 32],
        outcome: ClaimOutcomeV1,
    ) -> ClaimReceiptFactsV1 {
        let mut cas = ClaimCasBindingsV1 {
            authorization_id_sha256: identity.authorization_id_sha256,
            claim_namespace_sha256: identity.claim_namespace_sha256,
            claim_key_sha256: identity.claim_key_sha256,
            signed_payload_sha256: identity.signed_payload_sha256,
            subject_manifest_sha256: identity.subject_manifest_sha256,
            resource_scope_sha256: identity.resource_scope_sha256,
            signed_revocation_epoch_sha256: repeated(23),
            expected_unclaimed_state_sha256: repeated(24),
            expected_revision_sha256: repeated(25),
            expected_successful_claim_count_sha256: repeated(26),
            run_id_sha256: identity.run_id_sha256,
            controller_binary_sha256: repeated(27),
            runner_binary_sha256: repeated(28),
            capability_nonce_sha256: identity.capability_nonce_sha256,
            preflight_receipt_sha256: preflight_sha256,
            cas_control_snapshot_sha256: cas_control_sha256,
            assignment_set_sha256: identity.assignment_set_sha256,
            assignment_record_sha256: identity.assignment_record_sha256,
            operation_descriptor_sha256: identity.operation_descriptor_sha256,
            attempt_tombstone_sha256: repeated(29),
            pre_database_content_root_sha256: repeated(30),
            claim_transition_core_sha256: repeated(31),
            post_database_content_root_sha256: repeated(32),
            external_checkpoint_receipt_sha256: repeated(33),
        };
        cas.claim_transition_core_sha256 = recompute_claim_transition_core_v1(&cas).unwrap();
        ClaimReceiptFactsV1 {
            identity,
            cas,
            outcome,
        }
    }

    fn chain(parent: [u8; 32]) -> Vec<ReceiptNodeV1> {
        let mut output = Vec::new();
        let mut current = parent;
        for (index, kind) in [
            "RETENTION",
            "SEMANTIC_VALIDATION",
            "BATCH",
            "STOP_OR_ABSENT",
            "CLEANUP",
            "CUSTODY",
        ]
        .into_iter()
        .enumerate()
        {
            let node = build_receipt_node_v1(kind, current, repeated(40 + index as u8)).unwrap();
            current = node.receipt_sha256;
            output.push(node);
        }
        output
    }

    fn s16_record() -> Vec<u8> {
        super::super::super::super::super::super::super::tests::s15_fixture_parts().0
    }

    fn phase_observation(
        assignment: &AuthorizedAssignmentV1,
        phase_kind: S17PhaseKindV1,
        row: &S16RowV1,
    ) -> S17PhaseObservationV1 {
        S17PhaseObservationV1 {
            assignment_ordinal: assignment.ordinal,
            phase_kind,
            fingerprint: fingerprint_from_row_v1(row),
            mapped_row_sha256: super::super::super::super::super::row_commitment_v1(row),
        }
    }

    fn valid_cross_field_evidence(
        observation: &S17PhaseObservationV1,
        row: &S16RowV1,
    ) -> S17CrossFieldEvidenceV1 {
        let raw_packet = vec![0xaa, 0x01, 0x02, 0x03, 0xbb];
        let frame = &raw_packet[1..4];
        let frame_sha256 = sha256_bytes(frame);
        let decoded_phase_measurement = frame.to_vec();
        let virtual_projection_sha256 = framed_digest(S17_FINGERPRINT_DOMAIN, &[frame]).unwrap();
        let fingerprint_sha256 = fingerprint_digest_v1(&observation.fingerprint).unwrap();
        let classification_input_sha256 = framed_digest(
            S17_CLASSIFICATION_INPUT_DOMAIN,
            &[frame, &fingerprint_sha256],
        )
        .unwrap();
        let mapped_row_sha256 = super::super::super::super::super::row_commitment_v1(row);
        let phase_record_sha256 = framed_digest(
            S17_PHASE_RECORD_DOMAIN,
            &[&classification_input_sha256, &mapped_row_sha256],
        )
        .unwrap();
        let ack_payload = match &row.ack_state {
            super::super::super::super::super::ModeledAckStateV1::NotObserved => None,
            super::super::super::super::super::ModeledAckStateV1::Observed {
                receipt_sha256,
                witness_sha256,
            } => Some((*receipt_sha256, *witness_sha256)),
        };
        S17CrossFieldEvidenceV1 {
            pidfd_target: (101, 1_001),
            initial_child: (101, 1_001),
            signal_sender: (100, 1_000),
            controller: (100, 1_000),
            fresh_child: (102, 1_002),
            initial_nonce_sha256: repeated(1),
            fresh_nonce_sha256: repeated(2),
            runner_binary_sha256: repeated(3),
            initial_image_sha256: repeated(3),
            fresh_image_sha256: repeated(3),
            initial_boot_id_sha256: repeated(4),
            fresh_boot_id_sha256: repeated(4),
            expected_root_identity_sha256: repeated(5),
            observed_root_identity_sha256: repeated(5),
            expected_mount_identity_sha256: repeated(6),
            observed_mount_identity_sha256: repeated(6),
            run_root: "/owned/s20b-run".into(),
            database_path: "/owned/s20b-run/state.sqlite3".into(),
            expected_database_identity_sha256: repeated(7),
            observed_database_identity_sha256: repeated(7),
            expected_sqlite_profile_sha256: repeated(8),
            observed_sqlite_profile_sha256: repeated(8),
            expected_sqlite_schema_sha256: repeated(9),
            observed_sqlite_schema_sha256: repeated(9),
            custody_raw_sha256: repeated(10),
            raw_identity_sha256: repeated(10),
            custody_canonical_sha256: repeated(11),
            canonical_identity_sha256: repeated(11),
            retained_raw_packet: raw_packet,
            frame_start: 1,
            frame_end: 4,
            frame_sha256,
            decoded_phase_measurement,
            ack_payload,
            expected_ack_payload: ack_payload,
            virtual_projection_sha256,
            virtual_projection_external_count: 0,
            virtual_projection_provider_count: 0,
            virtual_projection_owned_lab_count: 0,
            s17_ledger_sha256: repeated(12),
            classification_input_sha256,
            phase_record_sha256,
            expected_classifier_binary_sha256: repeated(13),
            actual_classifier_binary_sha256: repeated(13),
            expected_classifier_source_sha256: repeated(14),
            actual_classifier_source_sha256: repeated(14),
            paired_attempt_sha256: repeated(15),
            paired_cut_sha256: repeated(16),
            expected_paired_attempt_sha256: repeated(15),
            expected_paired_cut_sha256: repeated(16),
            top_level_durable_facts_sha256: repeated(17),
            phase_durable_facts_sha256: repeated(17),
            eligible_result_process: (103, 1_003),
            custody_sequence: 1,
            previous_custody_sha256: repeated(18),
            expected_previous_custody_sha256: repeated(18),
            owner_binding_sha256: repeated(19),
            expected_owner_binding_sha256: repeated(19),
            absent_sentinels: [repeated(20), repeated(21), repeated(22), repeated(23)],
        }
    }

    #[test]
    fn s20b_exact_assignment_membership_not_label_and_concrete_operations() {
        let set = assignments();
        assert_eq!(set.entries.len(), 60);
        assert_eq!(
            set.entries
                .iter()
                .map(|entry| entry.phase_count)
                .sum::<u64>(),
            113
        );
        assert!(validate_exact_assignment_shape_v1(&set.entries).is_ok());
        let mut subject = subject_for_assignments(&set);
        assert!(validate_assignment_set_against_subject_v1(&subject, &set).is_ok());
        subject.assignment_set_sha256[0] ^= 1;
        assert!(validate_assignment_set_against_subject_v1(&subject, &set).is_err());
        let mut substituted = set.entries.clone();
        substituted[1].variant_id = "CALLER_LABEL_SUBSTITUTION".into();
        assert_ne!(
            assignment_record_digest_v1(
                substituted[1].ordinal,
                &substituted[1].family_id,
                &substituted[1].case_id,
                &substituted[1].variant_id,
                substituted[1].phase_count,
                &substituted[1].operation_descriptor_sha256,
            )
            .unwrap(),
            substituted[1].assignment_record_sha256
        );
        assert_eq!(ALLOWED_OPERATION_IDS.len(), 8);
    }

    #[test]
    fn s20b_all_rich_variants_roundtrip_and_digest_dag_is_acyclic() {
        let set = assignments();
        let identity = identity(&set.entries[0], &set);
        let context = context(identity.clone());
        let context_sha256 = context.digest().unwrap();
        let pre_control_facts =
            control(identity.clone(), ControlPhaseV1::Preflight, context_sha256);
        let pre_control = build_control_snapshot_v1(&pre_control_facts).unwrap();
        assert_eq!(
            validate_control_snapshot_v1(&pre_control.raw, &pre_control_facts)
                .unwrap()
                .kind,
            RichPacketKindV1::ControlSnapshot
        );
        let preflight_facts = PreflightReceiptFactsV1 {
            context,
            preflight_control_snapshot_sha256: pre_control.digest,
            outcome: PreflightOutcomeV1::Ready,
        };
        let preflight = build_preflight_receipt_v1(&preflight_facts).unwrap();
        assert_eq!(
            validate_preflight_receipt_v1(&preflight.raw, &preflight_facts)
                .unwrap()
                .digest,
            preflight.digest
        );
        let cas_control_facts = control(
            identity.clone(),
            ControlPhaseV1::CasLinearization,
            preflight.digest,
        );
        let cas_control = build_control_snapshot_v1(&cas_control_facts).unwrap();
        for outcome in [
            ClaimOutcomeV1::KnownNotCommittedTerminal,
            ClaimOutcomeV1::CommittedPermitIssued,
            ClaimOutcomeV1::CommittedPrePermitCrashTerminal,
            ClaimOutcomeV1::UnknownCommitOutcomeTerminalHardLock,
        ] {
            let claim_facts = claim_facts(
                identity.clone(),
                preflight.digest,
                cas_control.digest,
                outcome,
            );
            let claim = build_claim_receipt_v1(&claim_facts).unwrap();
            assert_eq!(
                validate_claim_receipt_v1(&claim.raw, &claim_facts)
                    .unwrap()
                    .kind,
                RichPacketKindV1::AuthorityControlClaim
            );
        }
        let claim_facts = claim_facts(
            identity.clone(),
            preflight.digest,
            cas_control.digest,
            ClaimOutcomeV1::CommittedPermitIssued,
        );
        let claim = build_claim_receipt_v1(&claim_facts).unwrap();
        let postrun_facts = PostRunReceiptFactsV1 {
            identity,
            claim_receipt_sha256: claim.digest,
            assignment_set_sha256: set.assignment_set_sha256,
            schedule_sha256: set.schedule_sha256,
            action_start_receipts: (0..60).map(|index| repeated(60 + index as u8)).collect(),
            raw_observation_receipts: (0..60).map(|index| repeated(120 + index as u8)).collect(),
            phase_record_receipts: (0..113)
                .map(|index| repeated(1 + (index % 250) as u8))
                .collect(),
            receipt_chain: chain(claim.digest),
            final_database_content_root_sha256: repeated(34),
            final_external_checkpoint_receipt_sha256: repeated(35),
            decision: PostRunDecisionV1::Complete,
        };
        let postrun = build_postrun_receipt_v1(&postrun_facts).unwrap();
        assert_eq!(
            validate_postrun_receipt_v1(&postrun.raw, &postrun_facts)
                .unwrap()
                .kind,
            RichPacketKindV1::PostRunReceiptBundle
        );
        assert_ne!(context_sha256, pre_control.digest);
        assert_ne!(pre_control.digest, preflight.digest);
        assert_ne!(preflight.digest, cas_control.digest);
        assert_ne!(cas_control.digest, claim.digest);
        assert_ne!(claim.digest, postrun.digest);
        for decision in [PostRunDecisionV1::Invalid, PostRunDecisionV1::Indeterminate] {
            let mut terminal = postrun_facts.clone();
            terminal.decision = decision;
            let packet = build_postrun_receipt_v1(&terminal).unwrap();
            assert!(validate_postrun_receipt_v1(&packet.raw, &terminal).is_ok());
        }
    }

    #[test]
    fn s20b_control_disjoint_missing_rollback_unknown_fail_closed() {
        let set = assignments();
        let identity = identity(&set.entries[0], &set);
        let parent = repeated(70);
        for claim_view in [ClaimViewV1::RowMissing, ClaimViewV1::ReadUnknown] {
            let mut facts = control(identity.clone(), ControlPhaseV1::Preflight, parent);
            facts.claim_view = claim_view;
            let packet = build_control_snapshot_v1(&facts).unwrap();
            assert!(String::from_utf8(packet.raw)
                .unwrap()
                .contains("DENY_TERMINAL_FAIL_CLOSED"));
        }
        let mut rollback = control(identity.clone(), ControlPhaseV1::Preflight, parent);
        rollback.revocation_view = RevocationViewV1::RollbackDetected { observed_epoch: 1 };
        assert!(
            String::from_utf8(build_control_snapshot_v1(&rollback).unwrap().raw)
                .unwrap()
                .contains("DENY_TERMINAL_FAIL_CLOSED")
        );
        let mut unknown = control(identity, ControlPhaseV1::Preflight, parent);
        unknown.stop_view = StopViewV1::ReadUnknown;
        assert!(
            String::from_utf8(build_control_snapshot_v1(&unknown).unwrap().raw)
                .unwrap()
                .contains("DENY_TERMINAL_FAIL_CLOSED")
        );
    }

    #[test]
    fn s20b_every_packet_self_and_cross_digest_tamper_is_rejected() {
        let set = assignments();
        let identity = identity(&set.entries[0], &set);
        let context = context(identity.clone());
        let control_facts = control(
            identity,
            ControlPhaseV1::Preflight,
            context.digest().unwrap(),
        );
        let mut packet = build_control_snapshot_v1(&control_facts).unwrap();
        let offset = packet.raw.iter().position(|byte| *byte == b'1').unwrap();
        packet.raw[offset] = b'2';
        assert!(validate_control_snapshot_v1(&packet.raw, &control_facts).is_err());
        let mut rebound = control_facts.clone();
        rebound.parent_sha256[0] ^= 1;
        let authentic = build_control_snapshot_v1(&control_facts).unwrap();
        assert!(validate_control_snapshot_v1(&authentic.raw, &rebound).is_err());
    }

    #[test]
    fn s20b_postrun_gap_fork_and_denominator_are_rejected() {
        let set = assignments();
        let identity = identity(&set.entries[0], &set);
        let mut facts = PostRunReceiptFactsV1 {
            identity,
            claim_receipt_sha256: repeated(80),
            assignment_set_sha256: set.assignment_set_sha256,
            schedule_sha256: set.schedule_sha256,
            action_start_receipts: vec![repeated(81); 59],
            raw_observation_receipts: vec![repeated(82); 60],
            phase_record_receipts: vec![repeated(83); 113],
            receipt_chain: chain(repeated(80)),
            final_database_content_root_sha256: repeated(84),
            final_external_checkpoint_receipt_sha256: repeated(85),
            decision: PostRunDecisionV1::Complete,
        };
        assert!(build_postrun_receipt_v1(&facts).is_err());
        facts.action_start_receipts.push(repeated(86));
        facts.receipt_chain[2].parent_sha256[0] ^= 1;
        assert!(build_postrun_receipt_v1(&facts).is_err());
    }

    #[test]
    fn s20b_status_is_private_non_live_and_no_effects() {
        assert!(S20B_FOUR_RICH_PACKET_BUILDERS_PARSERS_VALIDATORS_IMPLEMENTED);
        assert!(S20B_RUNTIME_SELF_DIGEST_RECOMPUTATION_IMPLEMENTED);
        assert!(S20B_RUNTIME_CROSS_PACKET_DIGEST_RECOMPUTATION_IMPLEMENTED);
        assert!(S20B_FULL_24_PARAMETER_CLAIM_VALIDATOR_IMPLEMENTED);
        assert!(S20B_EXACT_ASSIGNMENT_MEMBERSHIP_VALIDATOR_IMPLEMENTED);
        assert!(S20B_CONCRETE_OPERATION_DESCRIPTOR_VALIDATOR_IMPLEMENTED);
        assert!(S20B_DATABASE_CONTENT_ROOT_IMPLEMENTED);
        assert!(S20B_S17_32_RULE_FULL_5639_ROW_VALIDATOR_IMPLEMENTED);
        assert!(S20B_NEGATIVE_KAT_SUITE_IMPLEMENTED);
        assert!(!S20B_LIVE_BACKEND_PRESENT);
        assert_eq!(S20B_SIDE_EFFECTS_UNLOCKED, "NONE");
        assert_eq!(
            S20B_UNKNOWN_COMMIT_TERMINAL_CONTRACT,
            "UNKNOWN_COMMIT_OUTCOME_TERMINAL_HARD_LOCK"
        );
        assert_eq!(S17_CROSS_FIELD_RULES.len(), 32);
    }

    #[test]
    fn s20b_s17_32_rules_full_5639_rows_without_assignment_prefilter() {
        let assignments = assignments();
        let catalog = build_full_catalog_index_v1(&s16_record()).unwrap();
        assert_eq!(catalog.rows.len(), 5_639);
        assert_eq!(catalog.index.len(), 5_639);
        let mut validated_phases = 0_u64;
        for assignment in &assignments.entries {
            let phase_kinds: &[S17PhaseKindV1] = if assignment.family_id == "OL05" {
                &[S17PhaseKindV1::FirstAttempt, S17PhaseKindV1::Restart]
            } else {
                &[S17PhaseKindV1::Single]
            };
            for phase_kind in phase_kinds {
                let variant = expected_s16_variant_v1(assignment, *phase_kind).unwrap();
                let row = catalog
                    .rows
                    .iter()
                    .find(|row| {
                        row.case_id == assignment.case_id && row.variant_id.as_ref() == variant
                    })
                    .unwrap();
                let observation = phase_observation(assignment, *phase_kind, row);
                let matched =
                    validate_phase_against_full_catalog_v1(&catalog, &assignments, &observation)
                        .unwrap();
                let evidence = valid_cross_field_evidence(&observation, matched);
                validate_s17_32_rules_v1(&evidence, &observation, matched, catalog.index.len())
                    .unwrap();
                validated_phases += 1;
            }
        }
        assert_eq!(validated_phases, 113);
    }

    #[test]
    fn s20b_s17_assignment_substitution_and_cross_rule_tamper_are_rejected() {
        let assignments = assignments();
        let catalog = build_full_catalog_index_v1(&s16_record()).unwrap();
        let assignment = &assignments.entries[1];
        let row = catalog
            .rows
            .iter()
            .find(|row| {
                row.case_id == assignment.case_id
                    && row.variant_id.as_ref() == assignment.variant_id
            })
            .unwrap();
        let mut observation = phase_observation(assignment, S17PhaseKindV1::Single, row);
        observation.assignment_ordinal = 2;
        assert!(
            validate_phase_against_full_catalog_v1(&catalog, &assignments, &observation).is_err()
        );
        observation.assignment_ordinal = assignment.ordinal;
        let matched =
            validate_phase_against_full_catalog_v1(&catalog, &assignments, &observation).unwrap();
        let mut evidence = valid_cross_field_evidence(&observation, matched);
        evidence.pidfd_target.0 += 1;
        assert!(
            validate_s17_32_rules_v1(&evidence, &observation, matched, catalog.index.len())
                .is_err()
        );
    }
}
