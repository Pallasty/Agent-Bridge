//! S16 private deterministic recovered-envelope durability fault model.
//!
//! Every observation produced here is synthetic. The model has no production
//! or provider source implementation and grants no currentness, admission, or
//! side effect.

#![cfg_attr(not(test), allow(dead_code))]

use sha2::{Digest, Sha256};
use std::fmt;

const POLICY_ID: &str = "agent-bridge/track-b/recovered-envelope-durability-fault-model/v1";
const PROFILE: &str = "DETERMINISTIC_SYNTHETIC_OBJECT_RECEIPT_WITNESS_FAULT_MODEL_HISTORICAL_ONLY";
const RECEIPT_DOMAIN: &[u8] =
    b"agent-bridge/track-b/recovered-envelope-durability-fault-model/receipt/v1";
const WITNESS_DOMAIN: &[u8] =
    b"agent-bridge/track-b/recovered-envelope-durability-fault-model/witness/v1";
const REPLICA_VIEW_DOMAIN: &[u8] =
    b"agent-bridge/track-b/recovered-envelope-durability-fault-model/replica-view/v1";
const ABSENT_DOMAIN: &[u8] =
    b"agent-bridge/track-b/recovered-envelope-durability-fault-model/absent/v1";
const ROW_DOMAIN: &[u8] = b"agent-bridge/track-b/recovered-envelope-durability-fault-model/row/v1";
const CATALOG_DOMAIN: &[u8] =
    b"agent-bridge/track-b/recovered-envelope-durability-fault-model/catalog/v1";
const RECEIPT_SCHEMA_ID: &str = "agent-bridge/track-b/recovered-envelope-durability-receipt/v1";
const WITNESS_SCHEMA_ID: &str = "agent-bridge/track-b/recovered-envelope-durability-witness/v1";
const REPLICA_VIEW_SCHEMA_ID: &str = "agent-bridge/track-b/recovered-envelope-replica-view/v1";
const ROW_SCHEMA_ID: &str = "agent-bridge/track-b/recovered-envelope-durability-fault-row/v1";
const ROW_COUNT: usize = 5_639;
const CANONICAL_RECORD_LEN: usize = 5_494;
const DATA_STEP_BYTES: usize = 113;
const DATA_STEP_COUNT: usize = 49;

const S15_CONTRACT_SHA256: [u8; 32] = [
    0x07, 0xd7, 0xae, 0x5e, 0x73, 0x45, 0xbb, 0x50, 0x52, 0xaa, 0x13, 0x03, 0x49, 0xaf, 0x2e, 0x90,
    0xba, 0xe8, 0x53, 0xe5, 0xc7, 0x45, 0x60, 0x34, 0x6a, 0x41, 0x78, 0xb2, 0xb0, 0x39, 0x7c, 0xc7,
];
const LOOKUP_COMMITMENT_SHA256: [u8; 32] = [
    0x86, 0x6e, 0x01, 0x6c, 0xe6, 0x31, 0x43, 0x3e, 0x3e, 0x27, 0x2d, 0x08, 0x58, 0x90, 0x6f, 0x3c,
    0x76, 0xc6, 0x72, 0x04, 0xcd, 0x74, 0xb7, 0x3a, 0xb1, 0x1b, 0x73, 0x53, 0xe5, 0x7e, 0xae, 0x00,
];
const CANONICAL_RECORD_SHA256: [u8; 32] = [
    0xa7, 0x88, 0xec, 0x43, 0xfe, 0xfa, 0x76, 0xe3, 0x93, 0xd7, 0x7c, 0x86, 0xbb, 0xfa, 0xbe, 0xef,
    0x7d, 0x2a, 0xe8, 0xc5, 0x49, 0x9b, 0xb8, 0x34, 0xc1, 0x94, 0x5a, 0xf5, 0xcb, 0xb1, 0xb3, 0xcd,
];
const RECEIPT_KAT_SHA256: [u8; 32] = [
    0x12, 0xc8, 0x0f, 0x1b, 0x61, 0x0d, 0x48, 0x43, 0x8e, 0xc6, 0x94, 0x57, 0xa6, 0xf5, 0x53, 0xbf,
    0x48, 0xfd, 0x6a, 0x15, 0xa9, 0xc3, 0xff, 0xeb, 0xd7, 0xb2, 0x0c, 0x67, 0x89, 0x5b, 0x76, 0xa2,
];
const WITNESS_KAT_SHA256: [u8; 32] = [
    0xc3, 0x36, 0xca, 0xea, 0x64, 0x45, 0x48, 0xf2, 0x87, 0xdd, 0xc2, 0x85, 0xee, 0x3b, 0x94, 0x33,
    0xf8, 0x53, 0xf9, 0xb1, 0xf5, 0x62, 0xce, 0xe9, 0xf0, 0x55, 0xdf, 0x91, 0x34, 0x58, 0xbf, 0x99,
];
const SELECTED_VIEW_KAT_SHA256: [u8; 32] = [
    0x9a, 0x8f, 0x95, 0x9a, 0x01, 0xd3, 0xae, 0xad, 0x14, 0xb5, 0x27, 0xd5, 0x1b, 0xb1, 0xc7, 0x44,
    0x99, 0x9e, 0x8e, 0x1e, 0xe3, 0x3a, 0x56, 0x4c, 0xea, 0x72, 0xbb, 0x15, 0xb2, 0xb0, 0x0d, 0x6a,
];
const D00_ROW_KAT_SHA256: [u8; 32] = [
    0xb9, 0xe4, 0xf9, 0xab, 0x47, 0x0d, 0xe9, 0x85, 0xc9, 0x7b, 0x50, 0x29, 0x2d, 0xea, 0xe8, 0x98,
    0x18, 0x1c, 0x96, 0xe2, 0x18, 0x94, 0xb4, 0x3d, 0xe2, 0x3e, 0xc9, 0x8e, 0xc3, 0xfc, 0xed, 0x1a,
];
const CATALOG_KAT_SHA256: [u8; 32] = [
    0xc0, 0x9c, 0xdc, 0x64, 0x09, 0x57, 0x59, 0x4c, 0xc7, 0xac, 0xc2, 0xee, 0xea, 0x39, 0xcb, 0x4e,
    0x59, 0x99, 0x36, 0x31, 0xef, 0x04, 0xa1, 0xfa, 0x1e, 0x26, 0xa6, 0x9c, 0x28, 0x5a, 0xf8, 0x53,
];
const CATALOG_MESSAGE_LEN: usize = 225_852;

enum ModeledObjectPersistenceV1 {
    Absent,
    Partial,
    Committed,
}

impl ModeledObjectPersistenceV1 {
    fn as_str(&self) -> &'static str {
        match self {
            Self::Absent => "ABSENT",
            Self::Partial => "PARTIAL",
            Self::Committed => "COMMITTED",
        }
    }
}

struct ModeledObjectSlotV1 {
    persistence: ModeledObjectPersistenceV1,
    bytes: Box<[u8]>,
}

enum ModeledReceiptSlotV1 {
    Absent,
    Committed(ModeledDurableReceiptV1),
}

enum ModeledWitnessSlotV1 {
    Absent,
    Unavailable,
    Present(ModeledWitnessV1),
    Forked(ModeledWitnessV1, ModeledWitnessV1),
}

enum ModeledReplicaAuthorityV1 {
    ClaimsAuthoritative,
    NonAuthoritativeStale,
}

impl ModeledReplicaAuthorityV1 {
    fn as_str(&self) -> &'static str {
        match self {
            Self::ClaimsAuthoritative => "CLAIMS_AUTHORITATIVE",
            Self::NonAuthoritativeStale => "NON_AUTHORITATIVE_STALE",
        }
    }
}

struct ModeledDurableReceiptV1 {
    lookup_commitment_sha256: [u8; 32],
    source_incarnation: [u8; 32],
    source_generation_id: [u8; 32],
    object_id: [u8; 32],
    object_revision: u64,
    record_len: u64,
    record_sha256: [u8; 32],
    publish_sequence: u64,
    previous_receipt_sha256: [u8; 32],
    stored_receipt_sha256: [u8; 32],
}

struct ModeledWitnessV1 {
    witness_scope_id: [u8; 32],
    witness_incarnation: [u8; 32],
    witness_generation_id: [u8; 32],
    witness_sequence: u64,
    lookup_commitment_sha256: [u8; 32],
    source_incarnation: [u8; 32],
    source_generation_id: [u8; 32],
    object_id: [u8; 32],
    object_revision: u64,
    record_sha256: [u8; 32],
    receipt_sha256: [u8; 32],
    previous_witness_sha256: [u8; 32],
    stored_witness_sha256: [u8; 32],
}

struct ModeledReplicaViewV1 {
    replica_id: [u8; 32],
    authority: ModeledReplicaAuthorityV1,
    source_incarnation: [u8; 32],
    source_generation_id: [u8; 32],
    object_id: [u8; 32],
    object_revision: u64,
    record_len: u64,
    record_sha256: [u8; 32],
    receipt_sha256: [u8; 32],
}

struct ModeledDurableStateV1 {
    object: ModeledObjectSlotV1,
    receipt: ModeledReceiptSlotV1,
    witness: ModeledWitnessSlotV1,
    selected_view: Option<ModeledReplicaViewV1>,
    competing_view: Option<ModeledReplicaViewV1>,
}

enum ModeledPublisherPhaseV1 {
    Empty,
    ObjectPrefix,
    ObjectCommitted,
    ReceiptCommitted,
    WitnessCommitted,
    Acked,
}

impl ModeledPublisherPhaseV1 {
    fn as_str(&self) -> &'static str {
        match self {
            Self::Empty => "EMPTY",
            Self::ObjectPrefix => "OBJECT_PREFIX",
            Self::ObjectCommitted => "OBJECT_COMMITTED",
            Self::ReceiptCommitted => "RECEIPT_COMMITTED",
            Self::WitnessCommitted => "WITNESS_COMMITTED",
            Self::Acked => "ACKED",
        }
    }
}

enum ModeledAdapterPhaseV1 {
    Fresh,
    Streaming,
    Completed,
    TerminalFailed,
}

impl ModeledAdapterPhaseV1 {
    fn as_str(&self) -> &'static str {
        match self {
            Self::Fresh => "FRESH",
            Self::Streaming => "STREAMING",
            Self::Completed => "COMPLETED",
            Self::TerminalFailed => "TERMINAL_FAILED",
        }
    }
}

enum ModeledAckStateV1 {
    NotObserved,
    Observed {
        receipt_sha256: [u8; 32],
        witness_sha256: [u8; 32],
    },
}

impl ModeledAckStateV1 {
    fn as_str(&self) -> &'static str {
        match self {
            Self::NotObserved => "NOT_OBSERVED",
            Self::Observed { .. } => "OBSERVED",
        }
    }
}

enum ModeledCrashCutV1 {
    None,
    PublishAfterObjectPrefix,
    PublishAfterObjectCommit,
    PublishAfterReceiptCommit,
    PublishAfterWitnessCommit,
    PublishAfterAck,
    ReadBeforeOpen,
    ReadAfterOpen,
    ReadAfterData,
    ReadAfterCompleteBeforeS14,
    ReadAfterHistorical,
}

impl ModeledCrashCutV1 {
    fn as_str(&self) -> &'static str {
        match self {
            Self::None => "NONE",
            Self::PublishAfterObjectPrefix => "PUBLISH_AFTER_OBJECT_PREFIX",
            Self::PublishAfterObjectCommit => "PUBLISH_AFTER_OBJECT_COMMIT",
            Self::PublishAfterReceiptCommit => "PUBLISH_AFTER_RECEIPT_COMMIT",
            Self::PublishAfterWitnessCommit => "PUBLISH_AFTER_WITNESS_COMMIT",
            Self::PublishAfterAck => "PUBLISH_AFTER_ACK",
            Self::ReadBeforeOpen => "READ_BEFORE_OPEN",
            Self::ReadAfterOpen => "READ_AFTER_OPEN",
            Self::ReadAfterData => "READ_AFTER_DATA",
            Self::ReadAfterCompleteBeforeS14 => "READ_AFTER_COMPLETE_BEFORE_S14",
            Self::ReadAfterHistorical => "READ_AFTER_HISTORICAL",
        }
    }
}

enum ModeledSideEffectV1 {
    None,
    Observed,
}

impl ModeledSideEffectV1 {
    fn as_str(&self) -> &'static str {
        match self {
            Self::None => "NONE",
            Self::Observed => "OBSERVED",
        }
    }
}

struct ModeledVolatileStateV1 {
    publisher_phase: ModeledPublisherPhaseV1,
    adapter_phase: ModeledAdapterPhaseV1,
    adapter_post_phase: ModeledAdapterPhaseV1,
    observed_data_steps: u64,
    observed_len: u64,
    ack: ModeledAckStateV1,
    crash_cut: ModeledCrashCutV1,
    crash_cut_index: u64,
    restarted_after_crash: bool,
    external_durability_observation_count: u64,
    provider_durability_observation_count: u64,
    owned_lab_durability_observation_count: u64,
    side_effect: ModeledSideEffectV1,
}

enum ModelDispositionV1 {
    ExactHistoricalReadEligible,
    IncompleteFailClosed,
    AmbiguousQuarantined,
    IntegrityIncidentQuarantined,
}

impl ModelDispositionV1 {
    fn as_str(&self) -> &'static str {
        match self {
            Self::ExactHistoricalReadEligible => "MODEL_EXACT_HISTORICAL_READ_ELIGIBLE",
            Self::IncompleteFailClosed => "MODEL_INCOMPLETE_FAIL_CLOSED",
            Self::AmbiguousQuarantined => "MODEL_AMBIGUOUS_QUARANTINED",
            Self::IntegrityIncidentQuarantined => "MODEL_INTEGRITY_INCIDENT_QUARANTINED",
        }
    }
}

enum ModeledS15ExecutionResultV1 {
    NotInvoked,
    StreamExact,
    FailIndeterminate,
}

impl ModeledS15ExecutionResultV1 {
    fn as_str(&self) -> &'static str {
        match self {
            Self::NotInvoked => "NOT_INVOKED",
            Self::StreamExact => "STREAM_EXACT",
            Self::FailIndeterminate => "FAIL_INDETERMINATE",
        }
    }
}

enum MappedS15FailureV1 {
    None,
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

impl MappedS15FailureV1 {
    fn as_str(&self) -> &'static str {
        match self {
            Self::None => "NONE",
            Self::NotFound => "NOT_FOUND",
            Self::Pending => "PENDING",
            Self::Conflict => "CONFLICT",
            Self::Stale => "STALE",
            Self::Rollback => "ROLLBACK",
            Self::Unavailable => "UNAVAILABLE",
            Self::Unauthenticated => "UNAUTHENTICATED",
            Self::Malformed => "MALFORMED",
            Self::Indeterminate => "INDETERMINATE",
        }
    }
}

struct ModeledFaultRowV1 {
    case_id: &'static str,
    variant_id: Box<str>,
    variant_index: u64,
    publisher_phase: ModeledPublisherPhaseV1,
    object_persistence: ModeledObjectPersistenceV1,
    object_len: u64,
    observed_object_sha256: [u8; 32],
    receipt_state: &'static str,
    computed_receipt_sha256: [u8; 32],
    stored_receipt_sha256: [u8; 32],
    witness_state: &'static str,
    computed_witness_sha256: [u8; 32],
    stored_witness_sha256: [u8; 32],
    selected_view_sha256: [u8; 32],
    competing_view_sha256: [u8; 32],
    ack_state: ModeledAckStateV1,
    crash_cut: ModeledCrashCutV1,
    crash_cut_index: u64,
    adapter_pre_state: ModeledAdapterPhaseV1,
    adapter_post_state: ModeledAdapterPhaseV1,
    disposition: ModelDispositionV1,
    reason: &'static str,
    s15_execution_result: ModeledS15ExecutionResultV1,
    mapped_s15_failure: MappedS15FailureV1,
    external_durability_observation_count: u64,
    provider_durability_observation_count: u64,
    owned_lab_durability_observation_count: u64,
    side_effect: ModeledSideEffectV1,
}

impl fmt::Debug for ModeledDurableReceiptV1 {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        formatter
            .debug_struct("ModeledDurableReceiptV1")
            .field("scope", &"[SYNTHETIC_RECEIPT_REDACTED]")
            .finish_non_exhaustive()
    }
}

impl fmt::Debug for ModeledWitnessV1 {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        formatter
            .debug_struct("ModeledWitnessV1")
            .field("scope", &"[SYNTHETIC_WITNESS_REDACTED]")
            .finish_non_exhaustive()
    }
}

impl fmt::Debug for ModeledReplicaViewV1 {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        formatter
            .debug_struct("ModeledReplicaViewV1")
            .field("scope", &"[SYNTHETIC_REPLICA_VIEW_REDACTED]")
            .finish_non_exhaustive()
    }
}

impl fmt::Debug for ModeledDurableStateV1 {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        formatter
            .debug_struct("ModeledDurableStateV1")
            .field("scope", &"[SYNTHETIC_DURABLE_STATE_REDACTED]")
            .finish_non_exhaustive()
    }
}

impl fmt::Debug for ModeledVolatileStateV1 {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        formatter
            .debug_struct("ModeledVolatileStateV1")
            .field("scope", &"[SYNTHETIC_VOLATILE_STATE_REDACTED]")
            .finish_non_exhaustive()
    }
}

fn append_frame(output: &mut Vec<u8>, value: &[u8]) {
    output.extend_from_slice(&u64::try_from(value.len()).unwrap_or(u64::MAX).to_be_bytes());
    output.extend_from_slice(value);
}

fn framed_digest(domain: &[u8], fields: &[&[u8]]) -> [u8; 32] {
    let mut message = Vec::new();
    append_frame(&mut message, domain);
    for field in fields {
        append_frame(&mut message, field);
    }
    Sha256::digest(message).into()
}

fn sha256_bytes(bytes: &[u8]) -> [u8; 32] {
    Sha256::digest(bytes).into()
}

fn absent_commitment_v1(kind: &[u8]) -> [u8; 32] {
    framed_digest(ABSENT_DOMAIN, &[kind])
}

fn receipt_message_v1(receipt: &ModeledDurableReceiptV1) -> Vec<u8> {
    let revision = receipt.object_revision.to_be_bytes();
    let record_len = receipt.record_len.to_be_bytes();
    let publish_sequence = receipt.publish_sequence.to_be_bytes();
    let mut message = Vec::new();
    for frame in [
        RECEIPT_DOMAIN,
        POLICY_ID.as_bytes(),
        PROFILE.as_bytes(),
        RECEIPT_SCHEMA_ID.as_bytes(),
        &S15_CONTRACT_SHA256,
        &receipt.lookup_commitment_sha256,
        &receipt.source_incarnation,
        &receipt.source_generation_id,
        &receipt.object_id,
        &revision,
        &record_len,
        &receipt.record_sha256,
        &publish_sequence,
        &receipt.previous_receipt_sha256,
    ] {
        append_frame(&mut message, frame);
    }
    message
}

fn computed_receipt_sha256_v1(receipt: &ModeledDurableReceiptV1) -> [u8; 32] {
    sha256_bytes(&receipt_message_v1(receipt))
}

fn witness_message_v1(witness: &ModeledWitnessV1) -> Vec<u8> {
    let sequence = witness.witness_sequence.to_be_bytes();
    let revision = witness.object_revision.to_be_bytes();
    let mut message = Vec::new();
    for frame in [
        WITNESS_DOMAIN,
        POLICY_ID.as_bytes(),
        PROFILE.as_bytes(),
        WITNESS_SCHEMA_ID.as_bytes(),
        &S15_CONTRACT_SHA256,
        &witness.witness_scope_id,
        &witness.witness_incarnation,
        &witness.witness_generation_id,
        &sequence,
        &witness.lookup_commitment_sha256,
        &witness.source_incarnation,
        &witness.source_generation_id,
        &witness.object_id,
        &revision,
        &witness.record_sha256,
        &witness.receipt_sha256,
        &witness.previous_witness_sha256,
    ] {
        append_frame(&mut message, frame);
    }
    message
}

fn computed_witness_sha256_v1(witness: &ModeledWitnessV1) -> [u8; 32] {
    sha256_bytes(&witness_message_v1(witness))
}

fn replica_view_message_v1(view: &ModeledReplicaViewV1) -> Vec<u8> {
    let revision = view.object_revision.to_be_bytes();
    let record_len = view.record_len.to_be_bytes();
    let mut message = Vec::new();
    for frame in [
        REPLICA_VIEW_DOMAIN,
        POLICY_ID.as_bytes(),
        PROFILE.as_bytes(),
        REPLICA_VIEW_SCHEMA_ID.as_bytes(),
        &S15_CONTRACT_SHA256,
        &LOOKUP_COMMITMENT_SHA256,
        &view.replica_id,
        view.authority.as_str().as_bytes(),
        &view.source_incarnation,
        &view.source_generation_id,
        &view.object_id,
        &revision,
        &record_len,
        &view.record_sha256,
        &view.receipt_sha256,
    ] {
        append_frame(&mut message, frame);
    }
    message
}

fn computed_replica_view_sha256_v1(view: &ModeledReplicaViewV1) -> [u8; 32] {
    sha256_bytes(&replica_view_message_v1(view))
}

fn row_message_v1(row: &ModeledFaultRowV1) -> Vec<u8> {
    let variant_index = row.variant_index.to_be_bytes();
    let object_len = row.object_len.to_be_bytes();
    let crash_cut_index = row.crash_cut_index.to_be_bytes();
    let external = row.external_durability_observation_count.to_be_bytes();
    let provider = row.provider_durability_observation_count.to_be_bytes();
    let owned_lab = row.owned_lab_durability_observation_count.to_be_bytes();
    let mut message = Vec::new();
    for frame in [
        ROW_DOMAIN,
        POLICY_ID.as_bytes(),
        PROFILE.as_bytes(),
        ROW_SCHEMA_ID.as_bytes(),
        &S15_CONTRACT_SHA256,
        &LOOKUP_COMMITMENT_SHA256,
        row.case_id.as_bytes(),
        row.variant_id.as_bytes(),
        &variant_index,
        b"SIMULATED_MODEL",
        row.publisher_phase.as_str().as_bytes(),
        row.object_persistence.as_str().as_bytes(),
        &object_len,
        &row.observed_object_sha256,
        row.receipt_state.as_bytes(),
        &row.computed_receipt_sha256,
        &row.stored_receipt_sha256,
        row.witness_state.as_bytes(),
        &row.computed_witness_sha256,
        &row.stored_witness_sha256,
        &row.selected_view_sha256,
        &row.competing_view_sha256,
        row.ack_state.as_str().as_bytes(),
        row.crash_cut.as_str().as_bytes(),
        &crash_cut_index,
        row.adapter_pre_state.as_str().as_bytes(),
        row.adapter_post_state.as_str().as_bytes(),
        row.disposition.as_str().as_bytes(),
        row.reason.as_bytes(),
        row.s15_execution_result.as_str().as_bytes(),
        row.mapped_s15_failure.as_str().as_bytes(),
        &external,
        &provider,
        &owned_lab,
        row.side_effect.as_str().as_bytes(),
    ] {
        append_frame(&mut message, frame);
    }
    message
}

fn row_commitment_v1(row: &ModeledFaultRowV1) -> [u8; 32] {
    sha256_bytes(&row_message_v1(row))
}

fn catalog_message_v1(rows: &[ModeledFaultRowV1]) -> Vec<u8> {
    let row_count = u64::try_from(rows.len()).unwrap_or(u64::MAX).to_be_bytes();
    let mut message = Vec::new();
    for frame in [
        CATALOG_DOMAIN,
        POLICY_ID.as_bytes(),
        PROFILE.as_bytes(),
        &S15_CONTRACT_SHA256,
        &row_count,
    ] {
        append_frame(&mut message, frame);
    }
    for row in rows {
        append_frame(&mut message, &row_commitment_v1(row));
    }
    message
}

fn catalog_commitment_v1(rows: &[ModeledFaultRowV1]) -> [u8; 32] {
    sha256_bytes(&catalog_message_v1(rows))
}

fn legal_publish_transition_v1(
    current: &ModeledPublisherPhaseV1,
    next: &ModeledPublisherPhaseV1,
) -> bool {
    matches!(
        (current, next),
        (
            ModeledPublisherPhaseV1::Empty,
            ModeledPublisherPhaseV1::ObjectPrefix
        ) | (
            ModeledPublisherPhaseV1::ObjectPrefix,
            ModeledPublisherPhaseV1::ObjectCommitted
        ) | (
            ModeledPublisherPhaseV1::ObjectCommitted,
            ModeledPublisherPhaseV1::ReceiptCommitted
        ) | (
            ModeledPublisherPhaseV1::ReceiptCommitted,
            ModeledPublisherPhaseV1::WitnessCommitted
        ) | (
            ModeledPublisherPhaseV1::WitnessCommitted,
            ModeledPublisherPhaseV1::Acked
        )
    )
}

fn advance_publisher_phase_v1(
    current: &mut ModeledPublisherPhaseV1,
    next: ModeledPublisherPhaseV1,
) -> Result<(), &'static str> {
    if !legal_publish_transition_v1(current, &next) {
        return Err("publisher phase transition is outside the closed synthetic schedule");
    }
    *current = next;
    Ok(())
}

struct BaseCommitmentsV1 {
    object: [u8; 32],
    receipt: [u8; 32],
    witness: [u8; 32],
    selected_view: [u8; 32],
    absent_object: [u8; 32],
    absent_receipt: [u8; 32],
    absent_witness: [u8; 32],
    absent_view: [u8; 32],
}

struct RowImageV1 {
    object_persistence: ModeledObjectPersistenceV1,
    object_len: u64,
    observed_object_sha256: [u8; 32],
    receipt_state: &'static str,
    computed_receipt_sha256: [u8; 32],
    stored_receipt_sha256: [u8; 32],
    witness_state: &'static str,
    computed_witness_sha256: [u8; 32],
    stored_witness_sha256: [u8; 32],
    selected_view_sha256: [u8; 32],
    competing_view_sha256: [u8; 32],
}

struct ModeledEvaluationV1 {
    image: RowImageV1,
    disposition: ModelDispositionV1,
    reason: &'static str,
    s15_execution_result: ModeledS15ExecutionResultV1,
    mapped_s15_failure: MappedS15FailureV1,
}

fn receipt_for_v1(
    source_generation_id: [u8; 32],
    object_id: [u8; 32],
    object_revision: u64,
    record_len: u64,
    record_sha256: [u8; 32],
    previous_receipt_sha256: [u8; 32],
) -> ModeledDurableReceiptV1 {
    let mut receipt = ModeledDurableReceiptV1 {
        lookup_commitment_sha256: LOOKUP_COMMITMENT_SHA256,
        source_incarnation: [0x81; 32],
        source_generation_id,
        object_id,
        object_revision,
        record_len,
        record_sha256,
        publish_sequence: 23,
        previous_receipt_sha256,
        stored_receipt_sha256: [0; 32],
    };
    receipt.stored_receipt_sha256 = computed_receipt_sha256_v1(&receipt);
    receipt
}

fn witness_for_v1(
    source_generation_id: [u8; 32],
    object_id: [u8; 32],
    object_revision: u64,
    record_sha256: [u8; 32],
    receipt_sha256: [u8; 32],
    previous_witness_sha256: [u8; 32],
) -> ModeledWitnessV1 {
    let mut witness = ModeledWitnessV1 {
        witness_scope_id: [0x92; 32],
        witness_incarnation: [0x93; 32],
        witness_generation_id: [0x94; 32],
        witness_sequence: 31,
        lookup_commitment_sha256: LOOKUP_COMMITMENT_SHA256,
        source_incarnation: [0x81; 32],
        source_generation_id,
        object_id,
        object_revision,
        record_sha256,
        receipt_sha256,
        previous_witness_sha256,
        stored_witness_sha256: [0; 32],
    };
    witness.stored_witness_sha256 = computed_witness_sha256_v1(&witness);
    witness
}

fn view_for_v1(
    replica_id: [u8; 32],
    authority: ModeledReplicaAuthorityV1,
    source_generation_id: [u8; 32],
    object_id: [u8; 32],
    object_revision: u64,
    record_len: u64,
    record_sha256: [u8; 32],
    receipt_sha256: [u8; 32],
) -> ModeledReplicaViewV1 {
    ModeledReplicaViewV1 {
        replica_id,
        authority,
        source_incarnation: [0x81; 32],
        source_generation_id,
        object_id,
        object_revision,
        record_len,
        record_sha256,
        receipt_sha256,
    }
}

fn base_commitments_v1(record: &[u8]) -> Result<BaseCommitmentsV1, &'static str> {
    if record.len() != CANONICAL_RECORD_LEN || sha256_bytes(record) != CANONICAL_RECORD_SHA256 {
        return Err("catalog input is not the canonical S14 record");
    }
    let receipt = receipt_for_v1(
        [0x82; 32],
        [0x83; 32],
        17,
        CANONICAL_RECORD_LEN as u64,
        CANONICAL_RECORD_SHA256,
        [0x91; 32],
    );
    let receipt_sha256 = computed_receipt_sha256_v1(&receipt);
    let witness = witness_for_v1(
        [0x82; 32],
        [0x83; 32],
        17,
        CANONICAL_RECORD_SHA256,
        receipt_sha256,
        [0x95; 32],
    );
    let selected_view = view_for_v1(
        [0x96; 32],
        ModeledReplicaAuthorityV1::ClaimsAuthoritative,
        [0x82; 32],
        [0x83; 32],
        17,
        CANONICAL_RECORD_LEN as u64,
        CANONICAL_RECORD_SHA256,
        receipt_sha256,
    );
    Ok(BaseCommitmentsV1 {
        object: sha256_bytes(record),
        receipt: receipt_sha256,
        witness: computed_witness_sha256_v1(&witness),
        selected_view: computed_replica_view_sha256_v1(&selected_view),
        absent_object: absent_commitment_v1(b"OBJECT"),
        absent_receipt: absent_commitment_v1(b"RECEIPT"),
        absent_witness: absent_commitment_v1(b"WITNESS"),
        absent_view: absent_commitment_v1(b"REPLICA_VIEW"),
    })
}

fn canonical_receipt_v1() -> ModeledDurableReceiptV1 {
    receipt_for_v1(
        [0x82; 32],
        [0x83; 32],
        17,
        CANONICAL_RECORD_LEN as u64,
        CANONICAL_RECORD_SHA256,
        [0x91; 32],
    )
}

fn canonical_witness_v1(receipt_sha256: [u8; 32]) -> ModeledWitnessV1 {
    witness_for_v1(
        [0x82; 32],
        [0x83; 32],
        17,
        CANONICAL_RECORD_SHA256,
        receipt_sha256,
        [0x95; 32],
    )
}

fn canonical_selected_view_v1(receipt_sha256: [u8; 32]) -> ModeledReplicaViewV1 {
    view_for_v1(
        [0x96; 32],
        ModeledReplicaAuthorityV1::ClaimsAuthoritative,
        [0x82; 32],
        [0x83; 32],
        17,
        CANONICAL_RECORD_LEN as u64,
        CANONICAL_RECORD_SHA256,
        receipt_sha256,
    )
}

fn absent_state_v1() -> ModeledDurableStateV1 {
    ModeledDurableStateV1 {
        object: ModeledObjectSlotV1 {
            persistence: ModeledObjectPersistenceV1::Absent,
            bytes: Box::new([]),
        },
        receipt: ModeledReceiptSlotV1::Absent,
        witness: ModeledWitnessSlotV1::Absent,
        selected_view: None,
        competing_view: None,
    }
}

fn prefix_state_v1(record: &[u8], prefix_len: usize) -> ModeledDurableStateV1 {
    ModeledDurableStateV1 {
        object: ModeledObjectSlotV1 {
            persistence: ModeledObjectPersistenceV1::Partial,
            bytes: record[..prefix_len].into(),
        },
        receipt: ModeledReceiptSlotV1::Absent,
        witness: ModeledWitnessSlotV1::Absent,
        selected_view: None,
        competing_view: None,
    }
}

fn object_only_state_v1(record: &[u8]) -> ModeledDurableStateV1 {
    ModeledDurableStateV1 {
        object: ModeledObjectSlotV1 {
            persistence: ModeledObjectPersistenceV1::Committed,
            bytes: record.into(),
        },
        receipt: ModeledReceiptSlotV1::Absent,
        witness: ModeledWitnessSlotV1::Absent,
        selected_view: None,
        competing_view: None,
    }
}

fn object_receipt_state_v1(record: &[u8]) -> ModeledDurableStateV1 {
    ModeledDurableStateV1 {
        object: ModeledObjectSlotV1 {
            persistence: ModeledObjectPersistenceV1::Committed,
            bytes: record.into(),
        },
        receipt: ModeledReceiptSlotV1::Committed(canonical_receipt_v1()),
        witness: ModeledWitnessSlotV1::Absent,
        selected_view: None,
        competing_view: None,
    }
}

fn receipt_without_object_state_v1() -> ModeledDurableStateV1 {
    ModeledDurableStateV1 {
        object: ModeledObjectSlotV1 {
            persistence: ModeledObjectPersistenceV1::Absent,
            bytes: Box::new([]),
        },
        receipt: ModeledReceiptSlotV1::Committed(canonical_receipt_v1()),
        witness: ModeledWitnessSlotV1::Absent,
        selected_view: None,
        competing_view: None,
    }
}

fn base_triple_state_v1(record: &[u8]) -> ModeledDurableStateV1 {
    let receipt = canonical_receipt_v1();
    let receipt_sha256 = computed_receipt_sha256_v1(&receipt);
    ModeledDurableStateV1 {
        object: ModeledObjectSlotV1 {
            persistence: ModeledObjectPersistenceV1::Committed,
            bytes: record.into(),
        },
        receipt: ModeledReceiptSlotV1::Committed(receipt),
        witness: ModeledWitnessSlotV1::Present(canonical_witness_v1(receipt_sha256)),
        selected_view: Some(canonical_selected_view_v1(receipt_sha256)),
        competing_view: None,
    }
}

fn volatile_state_v1(publisher_phase: ModeledPublisherPhaseV1) -> ModeledVolatileStateV1 {
    ModeledVolatileStateV1 {
        publisher_phase,
        adapter_phase: ModeledAdapterPhaseV1::Fresh,
        adapter_post_phase: ModeledAdapterPhaseV1::Fresh,
        observed_data_steps: 0,
        observed_len: 0,
        ack: ModeledAckStateV1::NotObserved,
        crash_cut: ModeledCrashCutV1::None,
        crash_cut_index: 0,
        restarted_after_crash: false,
        external_durability_observation_count: 0,
        provider_durability_observation_count: 0,
        owned_lab_durability_observation_count: 0,
        side_effect: ModeledSideEffectV1::None,
    }
}

fn row_image_from_raw_state_v1(
    durable: &ModeledDurableStateV1,
    base: &BaseCommitmentsV1,
) -> RowImageV1 {
    let (object_persistence, object_len, observed_object_sha256) = match &durable.object.persistence
    {
        ModeledObjectPersistenceV1::Absent => (
            ModeledObjectPersistenceV1::Absent,
            durable.object.bytes.len() as u64,
            if durable.object.bytes.is_empty() {
                base.absent_object
            } else {
                sha256_bytes(&durable.object.bytes)
            },
        ),
        ModeledObjectPersistenceV1::Partial => (
            ModeledObjectPersistenceV1::Partial,
            durable.object.bytes.len() as u64,
            sha256_bytes(&durable.object.bytes),
        ),
        ModeledObjectPersistenceV1::Committed => (
            ModeledObjectPersistenceV1::Committed,
            durable.object.bytes.len() as u64,
            sha256_bytes(&durable.object.bytes),
        ),
    };
    let (receipt_state, computed_receipt_sha256, stored_receipt_sha256) = match &durable.receipt {
        ModeledReceiptSlotV1::Absent => ("ABSENT", base.absent_receipt, base.absent_receipt),
        ModeledReceiptSlotV1::Committed(receipt) => (
            "COMMITTED",
            computed_receipt_sha256_v1(receipt),
            receipt.stored_receipt_sha256,
        ),
    };
    let (witness_state, computed_witness_sha256, stored_witness_sha256) = match &durable.witness {
        ModeledWitnessSlotV1::Absent => ("ABSENT", base.absent_witness, base.absent_witness),
        ModeledWitnessSlotV1::Unavailable => {
            ("UNAVAILABLE", base.absent_witness, base.absent_witness)
        }
        ModeledWitnessSlotV1::Present(witness) => (
            "PRESENT",
            computed_witness_sha256_v1(witness),
            witness.stored_witness_sha256,
        ),
        ModeledWitnessSlotV1::Forked(primary, competing) => (
            "FORKED",
            computed_witness_sha256_v1(primary),
            competing.stored_witness_sha256,
        ),
    };
    RowImageV1 {
        object_persistence,
        object_len,
        observed_object_sha256,
        receipt_state,
        computed_receipt_sha256,
        stored_receipt_sha256,
        witness_state,
        computed_witness_sha256,
        stored_witness_sha256,
        selected_view_sha256: durable
            .selected_view
            .as_ref()
            .map(computed_replica_view_sha256_v1)
            .unwrap_or(base.absent_view),
        competing_view_sha256: durable
            .competing_view
            .as_ref()
            .map(computed_replica_view_sha256_v1)
            .unwrap_or(base.absent_view),
    }
}

fn modeled_evaluation_v1(
    image: RowImageV1,
    disposition: ModelDispositionV1,
    reason: &'static str,
    s15_execution_result: ModeledS15ExecutionResultV1,
    mapped_s15_failure: MappedS15FailureV1,
) -> ModeledEvaluationV1 {
    ModeledEvaluationV1 {
        image,
        disposition,
        reason,
        s15_execution_result,
        mapped_s15_failure,
    }
}

fn unknown_modeled_evaluation_v1(image: RowImageV1) -> ModeledEvaluationV1 {
    modeled_evaluation_v1(
        image,
        ModelDispositionV1::AmbiguousQuarantined,
        "UNCLASSIFIED_MODELED_STATE",
        ModeledS15ExecutionResultV1::NotInvoked,
        MappedS15FailureV1::Indeterminate,
    )
}

fn claims_authority_v1(view: &ModeledReplicaViewV1) -> bool {
    matches!(
        &view.authority,
        ModeledReplicaAuthorityV1::ClaimsAuthoritative
    )
}

fn views_diverge_v1(selected: &ModeledReplicaViewV1, competing: &ModeledReplicaViewV1) -> bool {
    selected.source_incarnation != competing.source_incarnation
        || selected.source_generation_id != competing.source_generation_id
        || selected.object_id != competing.object_id
        || selected.object_revision != competing.object_revision
        || selected.record_len != competing.record_len
        || selected.record_sha256 != competing.record_sha256
        || selected.receipt_sha256 != competing.receipt_sha256
}

fn views_share_revision_identity_v1(
    selected: &ModeledReplicaViewV1,
    competing: &ModeledReplicaViewV1,
) -> bool {
    selected.source_incarnation == competing.source_incarnation
        && selected.source_generation_id == competing.source_generation_id
        && selected.object_id == competing.object_id
        && selected.object_revision == competing.object_revision
}

fn witness_proves_receipt_generation_rollback_v1(
    receipt: &ModeledDurableReceiptV1,
    witness: &ModeledWitnessV1,
) -> bool {
    receipt.lookup_commitment_sha256 == witness.lookup_commitment_sha256
        && receipt.source_incarnation == witness.source_incarnation
        && receipt.object_id == witness.object_id
        && receipt.source_generation_id != witness.source_generation_id
}

fn witness_proves_receipt_revision_rollback_v1(
    receipt: &ModeledDurableReceiptV1,
    witness: &ModeledWitnessV1,
) -> bool {
    receipt.lookup_commitment_sha256 == witness.lookup_commitment_sha256
        && receipt.source_incarnation == witness.source_incarnation
        && receipt.object_id == witness.object_id
        && receipt.source_generation_id == witness.source_generation_id
        && receipt.object_revision < witness.object_revision
}

fn well_formed_same_sequence_witness_fork_v1(
    primary: &ModeledWitnessV1,
    competing: &ModeledWitnessV1,
) -> bool {
    primary.stored_witness_sha256 == computed_witness_sha256_v1(primary)
        && competing.stored_witness_sha256 == computed_witness_sha256_v1(competing)
        && primary.witness_scope_id == competing.witness_scope_id
        && primary.witness_incarnation == competing.witness_incarnation
        && primary.witness_generation_id == competing.witness_generation_id
        && primary.witness_sequence == competing.witness_sequence
        && primary.lookup_commitment_sha256 == competing.lookup_commitment_sha256
        && primary.source_incarnation == competing.source_incarnation
        && primary.source_generation_id == competing.source_generation_id
        && primary.object_id == competing.object_id
        && primary.object_revision == competing.object_revision
        && primary.record_sha256 == competing.record_sha256
        && primary.receipt_sha256 == competing.receipt_sha256
        && primary.previous_witness_sha256 != competing.previous_witness_sha256
        && primary.stored_witness_sha256 != competing.stored_witness_sha256
}

fn exact_receipt_binding_v1(
    receipt: &ModeledDurableReceiptV1,
    object_sha256: [u8; 32],
    object_len: u64,
) -> bool {
    receipt.lookup_commitment_sha256 == LOOKUP_COMMITMENT_SHA256
        && receipt.source_incarnation == [0x81; 32]
        && receipt.source_generation_id == [0x82; 32]
        && receipt.object_id == [0x83; 32]
        && receipt.object_revision == 17
        && receipt.record_len == object_len
        && receipt.record_sha256 == object_sha256
        && receipt.publish_sequence == 23
        && receipt.previous_receipt_sha256 == [0x91; 32]
}

fn exact_witness_binding_v1(
    witness: &ModeledWitnessV1,
    receipt: &ModeledDurableReceiptV1,
    receipt_sha256: [u8; 32],
) -> bool {
    witness.witness_scope_id == [0x92; 32]
        && witness.witness_incarnation == [0x93; 32]
        && witness.witness_generation_id == [0x94; 32]
        && witness.witness_sequence == 31
        && witness.lookup_commitment_sha256 == receipt.lookup_commitment_sha256
        && witness.source_incarnation == receipt.source_incarnation
        && witness.source_generation_id == receipt.source_generation_id
        && witness.object_id == receipt.object_id
        && witness.object_revision == receipt.object_revision
        && witness.record_sha256 == receipt.record_sha256
        && witness.receipt_sha256 == receipt_sha256
        && witness.previous_witness_sha256 == [0x95; 32]
}

fn exact_canonical_witness_head_v1(witness: &ModeledWitnessV1, base: &BaseCommitmentsV1) -> bool {
    witness.witness_scope_id == [0x92; 32]
        && witness.witness_incarnation == [0x93; 32]
        && witness.witness_generation_id == [0x94; 32]
        && witness.witness_sequence == 31
        && witness.lookup_commitment_sha256 == LOOKUP_COMMITMENT_SHA256
        && witness.source_incarnation == [0x81; 32]
        && witness.source_generation_id == [0x82; 32]
        && witness.object_id == [0x83; 32]
        && witness.object_revision == 17
        && witness.record_sha256 == CANONICAL_RECORD_SHA256
        && witness.receipt_sha256 == base.receipt
        && witness.previous_witness_sha256 == [0x95; 32]
        && computed_witness_sha256_v1(witness) == base.witness
        && witness.stored_witness_sha256 == base.witness
}

fn exact_selected_view_binding_v1(
    selected: &ModeledReplicaViewV1,
    receipt: &ModeledDurableReceiptV1,
    receipt_sha256: [u8; 32],
) -> bool {
    claims_authority_v1(selected)
        && selected.replica_id == [0x96; 32]
        && selected.source_incarnation == receipt.source_incarnation
        && selected.source_generation_id == receipt.source_generation_id
        && selected.object_id == receipt.object_id
        && selected.object_revision == receipt.object_revision
        && selected.record_len == receipt.record_len
        && selected.record_sha256 == receipt.record_sha256
        && selected.receipt_sha256 == receipt_sha256
}

fn exact_ack_binding_v1(
    ack: &ModeledAckStateV1,
    receipt_sha256: [u8; 32],
    witness_sha256: [u8; 32],
) -> bool {
    match ack {
        ModeledAckStateV1::NotObserved => true,
        ModeledAckStateV1::Observed {
            receipt_sha256: observed_receipt,
            witness_sha256: observed_witness,
        } => *observed_receipt == receipt_sha256 && *observed_witness == witness_sha256,
    }
}

fn observed_len_for_data_steps_v1(data_steps: u64) -> u64 {
    data_steps
        .saturating_mul(DATA_STEP_BYTES as u64)
        .min(CANONICAL_RECORD_LEN as u64)
}

fn raw_lifecycle_tuple_is_known_v1(volatile: &ModeledVolatileStateV1) -> bool {
    let publisher = volatile.publisher_phase.as_str();
    let pre = volatile.adapter_phase.as_str();
    let post = volatile.adapter_post_phase.as_str();
    let ack = volatile.ack.as_str();
    let no_read_progress = volatile.observed_data_steps == 0 && volatile.observed_len == 0;

    match &volatile.crash_cut {
        ModeledCrashCutV1::None => {
            volatile.crash_cut_index == 0
                && no_read_progress
                && matches!(
                    (volatile.restarted_after_crash, publisher, pre, post, ack,),
                    (true, "EMPTY", "FRESH", "FRESH", "NOT_OBSERVED")
                        | (false, "OBJECT_COMMITTED", "FRESH", "FRESH", "NOT_OBSERVED")
                        | (false, "RECEIPT_COMMITTED", "FRESH", "FRESH", "NOT_OBSERVED")
                        | (
                            false,
                            "WITNESS_COMMITTED",
                            "FRESH",
                            "FRESH" | "COMPLETED",
                            "NOT_OBSERVED"
                        )
                        | (false, "ACKED", "FRESH", "FRESH" | "COMPLETED", "OBSERVED")
                )
        }
        ModeledCrashCutV1::PublishAfterObjectPrefix => {
            publisher == "OBJECT_PREFIX"
                && pre == "FRESH"
                && post == "FRESH"
                && ack == "NOT_OBSERVED"
                && no_read_progress
                && (1..CANONICAL_RECORD_LEN as u64).contains(&volatile.crash_cut_index)
        }
        ModeledCrashCutV1::PublishAfterObjectCommit => {
            volatile.restarted_after_crash
                && publisher == "OBJECT_COMMITTED"
                && pre == "FRESH"
                && post == "FRESH"
                && ack == "NOT_OBSERVED"
                && volatile.crash_cut_index == 0
                && no_read_progress
        }
        ModeledCrashCutV1::PublishAfterReceiptCommit => {
            volatile.restarted_after_crash
                && publisher == "RECEIPT_COMMITTED"
                && pre == "FRESH"
                && post == "FRESH"
                && ack == "NOT_OBSERVED"
                && volatile.crash_cut_index == 0
                && no_read_progress
        }
        ModeledCrashCutV1::PublishAfterWitnessCommit | ModeledCrashCutV1::PublishAfterAck => {
            let phase_matches_cut = matches!(
                (&volatile.crash_cut, publisher),
                (
                    ModeledCrashCutV1::PublishAfterWitnessCommit,
                    "WITNESS_COMMITTED"
                ) | (ModeledCrashCutV1::PublishAfterAck, "ACKED")
            );
            volatile.restarted_after_crash
                && phase_matches_cut
                && pre == "FRESH"
                && post == "COMPLETED"
                && ack == "NOT_OBSERVED"
                && volatile.crash_cut_index == 0
                && no_read_progress
        }
        ModeledCrashCutV1::ReadBeforeOpen
        | ModeledCrashCutV1::ReadAfterOpen
        | ModeledCrashCutV1::ReadAfterData
        | ModeledCrashCutV1::ReadAfterCompleteBeforeS14
        | ModeledCrashCutV1::ReadAfterHistorical => {
            if publisher != "ACKED" || ack != "NOT_OBSERVED" {
                return false;
            }
            if volatile.restarted_after_crash {
                let cut_index_is_valid = match &volatile.crash_cut {
                    ModeledCrashCutV1::ReadAfterData => {
                        (1..=DATA_STEP_COUNT as u64).contains(&volatile.crash_cut_index)
                    }
                    _ => volatile.crash_cut_index == 0,
                };
                return cut_index_is_valid
                    && pre == "FRESH"
                    && post == "COMPLETED"
                    && volatile.observed_data_steps == DATA_STEP_COUNT as u64
                    && volatile.observed_len == CANONICAL_RECORD_LEN as u64;
            }
            match &volatile.crash_cut {
                ModeledCrashCutV1::ReadBeforeOpen => {
                    volatile.crash_cut_index == 0
                        && pre == "FRESH"
                        && post == "FRESH"
                        && no_read_progress
                }
                ModeledCrashCutV1::ReadAfterOpen => {
                    volatile.crash_cut_index == 0
                        && pre == "STREAMING"
                        && post == "TERMINAL_FAILED"
                        && no_read_progress
                }
                ModeledCrashCutV1::ReadAfterData => {
                    (1..=DATA_STEP_COUNT as u64).contains(&volatile.crash_cut_index)
                        && volatile.observed_data_steps == volatile.crash_cut_index
                        && volatile.observed_len
                            == observed_len_for_data_steps_v1(volatile.crash_cut_index)
                        && pre == "STREAMING"
                        && post == "TERMINAL_FAILED"
                }
                ModeledCrashCutV1::ReadAfterCompleteBeforeS14 => {
                    volatile.crash_cut_index == 0
                        && volatile.observed_data_steps == DATA_STEP_COUNT as u64
                        && volatile.observed_len == CANONICAL_RECORD_LEN as u64
                        && pre == "STREAMING"
                        && post == "COMPLETED"
                }
                ModeledCrashCutV1::ReadAfterHistorical => {
                    volatile.crash_cut_index == 0
                        && volatile.observed_data_steps == DATA_STEP_COUNT as u64
                        && volatile.observed_len == CANONICAL_RECORD_LEN as u64
                        && pre == "COMPLETED"
                        && post == "COMPLETED"
                }
                _ => false,
            }
        }
    }
}

fn exact_read_lifecycle_evaluation_v1(
    image: RowImageV1,
    volatile: &ModeledVolatileStateV1,
) -> ModeledEvaluationV1 {
    let pre = volatile.adapter_phase.as_str();
    let post = volatile.adapter_post_phase.as_str();
    match &volatile.crash_cut {
        ModeledCrashCutV1::ReadBeforeOpen => {
            if volatile.restarted_after_crash {
                if pre == "FRESH" && post == "COMPLETED" {
                    modeled_evaluation_v1(
                        image,
                        ModelDispositionV1::ExactHistoricalReadEligible,
                        "FRESH_ADAPTER_EXACT_REREAD",
                        ModeledS15ExecutionResultV1::StreamExact,
                        MappedS15FailureV1::None,
                    )
                } else {
                    unknown_modeled_evaluation_v1(image)
                }
            } else if pre == "FRESH" && post == "FRESH" {
                modeled_evaluation_v1(
                    image,
                    ModelDispositionV1::AmbiguousQuarantined,
                    "CRASH_BEFORE_OPEN_RESULT_UNKNOWN",
                    ModeledS15ExecutionResultV1::NotInvoked,
                    MappedS15FailureV1::Indeterminate,
                )
            } else {
                unknown_modeled_evaluation_v1(image)
            }
        }
        ModeledCrashCutV1::ReadAfterOpen | ModeledCrashCutV1::ReadAfterData => {
            if volatile.restarted_after_crash {
                if pre == "FRESH" && post == "COMPLETED" {
                    modeled_evaluation_v1(
                        image,
                        ModelDispositionV1::ExactHistoricalReadEligible,
                        "FRESH_ADAPTER_EXACT_REREAD",
                        ModeledS15ExecutionResultV1::StreamExact,
                        MappedS15FailureV1::None,
                    )
                } else {
                    unknown_modeled_evaluation_v1(image)
                }
            } else if pre == "STREAMING" && post == "TERMINAL_FAILED" {
                modeled_evaluation_v1(
                    image,
                    ModelDispositionV1::AmbiguousQuarantined,
                    "CRASH_DURING_STREAM_DISCARDED_PARTIAL_STATE",
                    ModeledS15ExecutionResultV1::FailIndeterminate,
                    MappedS15FailureV1::Indeterminate,
                )
            } else {
                unknown_modeled_evaluation_v1(image)
            }
        }
        ModeledCrashCutV1::ReadAfterCompleteBeforeS14 => {
            if volatile.restarted_after_crash {
                if pre == "FRESH" && post == "COMPLETED" {
                    modeled_evaluation_v1(
                        image,
                        ModelDispositionV1::ExactHistoricalReadEligible,
                        "FRESH_ADAPTER_EXACT_REREAD",
                        ModeledS15ExecutionResultV1::StreamExact,
                        MappedS15FailureV1::None,
                    )
                } else {
                    unknown_modeled_evaluation_v1(image)
                }
            } else if pre == "STREAMING" && post == "COMPLETED" {
                modeled_evaluation_v1(
                    image,
                    ModelDispositionV1::AmbiguousQuarantined,
                    "ADAPTER_COMPLETED_S14_RESULT_NOT_OBSERVED",
                    ModeledS15ExecutionResultV1::StreamExact,
                    MappedS15FailureV1::None,
                )
            } else {
                unknown_modeled_evaluation_v1(image)
            }
        }
        ModeledCrashCutV1::ReadAfterHistorical => {
            if volatile.restarted_after_crash {
                if pre == "FRESH" && post == "COMPLETED" {
                    modeled_evaluation_v1(
                        image,
                        ModelDispositionV1::ExactHistoricalReadEligible,
                        "REPEATED_HISTORICAL_REVERIFY_NO_REPLAY_FENCE",
                        ModeledS15ExecutionResultV1::StreamExact,
                        MappedS15FailureV1::None,
                    )
                } else {
                    unknown_modeled_evaluation_v1(image)
                }
            } else if pre == "COMPLETED" && post == "COMPLETED" {
                modeled_evaluation_v1(
                    image,
                    ModelDispositionV1::ExactHistoricalReadEligible,
                    "HISTORICAL_RESULT_OBSERVED_BEFORE_CRASH",
                    ModeledS15ExecutionResultV1::StreamExact,
                    MappedS15FailureV1::None,
                )
            } else {
                unknown_modeled_evaluation_v1(image)
            }
        }
        _ => unknown_modeled_evaluation_v1(image),
    }
}

fn evaluate_raw_modeled_state_v1(
    record: &[u8],
    durable: &ModeledDurableStateV1,
    volatile: &ModeledVolatileStateV1,
    base: &BaseCommitmentsV1,
) -> ModeledEvaluationV1 {
    let image = row_image_from_raw_state_v1(durable, base);

    if record.len() != CANONICAL_RECORD_LEN
        || sha256_bytes(record) != CANONICAL_RECORD_SHA256
        || volatile.observed_data_steps > DATA_STEP_COUNT as u64
        || volatile.observed_len > CANONICAL_RECORD_LEN as u64
        || !raw_lifecycle_tuple_is_known_v1(volatile)
    {
        return unknown_modeled_evaluation_v1(image);
    }
    if volatile.external_durability_observation_count != 0
        || volatile.provider_durability_observation_count != 0
        || volatile.owned_lab_durability_observation_count != 0
        || !matches!(&volatile.side_effect, ModeledSideEffectV1::None)
    {
        return unknown_modeled_evaluation_v1(image);
    }

    let object_shape_is_known = match &durable.object.persistence {
        ModeledObjectPersistenceV1::Absent => durable.object.bytes.is_empty(),
        ModeledObjectPersistenceV1::Partial => {
            !durable.object.bytes.is_empty()
                && durable.object.bytes.len() <= record.len()
                && record.get(..durable.object.bytes.len()) == Some(durable.object.bytes.as_ref())
        }
        ModeledObjectPersistenceV1::Committed => {
            !durable.object.bytes.is_empty() && durable.object.bytes.len() <= 272 * 1024
        }
    };
    if !object_shape_is_known {
        return unknown_modeled_evaluation_v1(image);
    }

    if let (Some(selected), Some(competing)) = (&durable.selected_view, &durable.competing_view) {
        if !claims_authority_v1(selected) || !claims_authority_v1(competing) {
            return unknown_modeled_evaluation_v1(image);
        }
        if views_diverge_v1(selected, competing) {
            return if views_share_revision_identity_v1(selected, competing) {
                modeled_evaluation_v1(
                    image,
                    ModelDispositionV1::IntegrityIncidentQuarantined,
                    "SAME_REVISION_EQUIVOCATION",
                    ModeledS15ExecutionResultV1::NotInvoked,
                    MappedS15FailureV1::Conflict,
                )
            } else {
                modeled_evaluation_v1(
                    image,
                    ModelDispositionV1::IntegrityIncidentQuarantined,
                    "DIVERGENT_AUTHORITATIVE_VIEWS",
                    ModeledS15ExecutionResultV1::NotInvoked,
                    MappedS15FailureV1::Conflict,
                )
            };
        }
        return unknown_modeled_evaluation_v1(image);
    }
    if durable.competing_view.is_some() {
        return unknown_modeled_evaluation_v1(image);
    }

    if matches!(&volatile.ack, ModeledAckStateV1::Observed { .. })
        && matches!(
            &durable.witness,
            ModeledWitnessSlotV1::Absent | ModeledWitnessSlotV1::Unavailable
        )
    {
        return modeled_evaluation_v1(
            image,
            ModelDispositionV1::AmbiguousQuarantined,
            "ACK_OUTRAN_MODELED_DURABILITY",
            ModeledS15ExecutionResultV1::NotInvoked,
            MappedS15FailureV1::Indeterminate,
        );
    }

    if matches!(&durable.receipt, ModeledReceiptSlotV1::Committed(_))
        && matches!(
            &durable.object.persistence,
            ModeledObjectPersistenceV1::Absent
        )
    {
        return modeled_evaluation_v1(
            image,
            ModelDispositionV1::IntegrityIncidentQuarantined,
            "RECEIPT_WITHOUT_OBJECT",
            ModeledS15ExecutionResultV1::NotInvoked,
            MappedS15FailureV1::Conflict,
        );
    }

    match &durable.object.persistence {
        ModeledObjectPersistenceV1::Absent => {
            if !matches!(&durable.receipt, ModeledReceiptSlotV1::Absent)
                || !matches!(&durable.witness, ModeledWitnessSlotV1::Absent)
                || durable.selected_view.is_some()
            {
                return unknown_modeled_evaluation_v1(image);
            }
            if volatile.restarted_after_crash
                && volatile.publisher_phase.as_str() == "EMPTY"
                && volatile.adapter_phase.as_str() == "FRESH"
                && volatile.adapter_post_phase.as_str() == "FRESH"
            {
                return modeled_evaluation_v1(
                    image,
                    ModelDispositionV1::IncompleteFailClosed,
                    "NO_DURABLE_OBJECT_AFTER_RESTART",
                    ModeledS15ExecutionResultV1::NotInvoked,
                    MappedS15FailureV1::NotFound,
                );
            }
            return unknown_modeled_evaluation_v1(image);
        }
        ModeledObjectPersistenceV1::Partial => {
            if !matches!(&durable.receipt, ModeledReceiptSlotV1::Absent)
                || !matches!(&durable.witness, ModeledWitnessSlotV1::Absent)
                || durable.selected_view.is_some()
                || volatile.publisher_phase.as_str() != "OBJECT_PREFIX"
                || !matches!(
                    &volatile.crash_cut,
                    ModeledCrashCutV1::PublishAfterObjectPrefix
                )
                || volatile.crash_cut_index != durable.object.bytes.len() as u64
            {
                return unknown_modeled_evaluation_v1(image);
            }
            return modeled_evaluation_v1(
                image,
                ModelDispositionV1::IncompleteFailClosed,
                if volatile.restarted_after_crash {
                    "PARTIAL_OBJECT_AFTER_RESTART"
                } else {
                    "PARTIAL_OBJECT_NOT_COMMITTED"
                },
                ModeledS15ExecutionResultV1::NotInvoked,
                MappedS15FailureV1::Malformed,
            );
        }
        ModeledObjectPersistenceV1::Committed => {}
    }

    if let ModeledReceiptSlotV1::Committed(receipt) = &durable.receipt {
        if computed_receipt_sha256_v1(receipt) != receipt.stored_receipt_sha256 {
            return modeled_evaluation_v1(
                image,
                ModelDispositionV1::IntegrityIncidentQuarantined,
                "POST_PERSISTENCE_RECEIPT_STORED_HASH_CORRUPTION",
                ModeledS15ExecutionResultV1::NotInvoked,
                MappedS15FailureV1::Malformed,
            );
        }
    }
    match &durable.witness {
        ModeledWitnessSlotV1::Present(witness)
            if computed_witness_sha256_v1(witness) != witness.stored_witness_sha256 =>
        {
            let d14_corruption = xor_digest_byte(computed_witness_sha256_v1(witness), 7)
                == witness.stored_witness_sha256;
            return modeled_evaluation_v1(
                image,
                ModelDispositionV1::IntegrityIncidentQuarantined,
                if d14_corruption {
                    "WITNESS_STORED_HASH_CORRUPT"
                } else {
                    "POST_PERSISTENCE_WITNESS_STORED_HASH_CORRUPTION"
                },
                ModeledS15ExecutionResultV1::NotInvoked,
                MappedS15FailureV1::Malformed,
            );
        }
        ModeledWitnessSlotV1::Forked(primary, competing) => {
            return if well_formed_same_sequence_witness_fork_v1(primary, competing) {
                modeled_evaluation_v1(
                    image,
                    ModelDispositionV1::IntegrityIncidentQuarantined,
                    "WITNESS_FORKED_SAME_SEQUENCE",
                    ModeledS15ExecutionResultV1::NotInvoked,
                    MappedS15FailureV1::Conflict,
                )
            } else {
                unknown_modeled_evaluation_v1(image)
            };
        }
        _ => {}
    }

    let observed_object_sha256 = sha256_bytes(&durable.object.bytes);
    if durable.object.bytes.len() != CANONICAL_RECORD_LEN
        || observed_object_sha256 != CANONICAL_RECORD_SHA256
    {
        return modeled_evaluation_v1(
            image,
            ModelDispositionV1::IntegrityIncidentQuarantined,
            "POST_PERSISTENCE_OBJECT_CORRUPTION",
            ModeledS15ExecutionResultV1::NotInvoked,
            MappedS15FailureV1::Malformed,
        );
    }

    let receipt = match &durable.receipt {
        ModeledReceiptSlotV1::Absent => {
            if !matches!(&durable.witness, ModeledWitnessSlotV1::Absent)
                || durable.selected_view.is_some()
            {
                return unknown_modeled_evaluation_v1(image);
            }
            let schedule_is_known = if volatile.restarted_after_crash {
                volatile.publisher_phase.as_str() == "OBJECT_COMMITTED"
                    && matches!(
                        &volatile.crash_cut,
                        ModeledCrashCutV1::PublishAfterObjectCommit
                    )
            } else {
                volatile.publisher_phase.as_str() == "OBJECT_COMMITTED"
                    && matches!(&volatile.crash_cut, ModeledCrashCutV1::None)
            };
            if !schedule_is_known {
                return unknown_modeled_evaluation_v1(image);
            }
            return modeled_evaluation_v1(
                image,
                ModelDispositionV1::IncompleteFailClosed,
                if volatile.restarted_after_crash {
                    "RECEIPT_MISSING_AFTER_RESTART"
                } else {
                    "RECEIPT_MISSING"
                },
                ModeledS15ExecutionResultV1::NotInvoked,
                MappedS15FailureV1::Pending,
            );
        }
        ModeledReceiptSlotV1::Committed(receipt) => receipt,
    };
    let receipt_sha256 = computed_receipt_sha256_v1(receipt);

    if receipt.record_len != durable.object.bytes.len() as u64 {
        return modeled_evaluation_v1(
            image,
            ModelDispositionV1::IntegrityIncidentQuarantined,
            "RECEIPT_LENGTH_MISMATCH",
            ModeledS15ExecutionResultV1::NotInvoked,
            MappedS15FailureV1::Conflict,
        );
    }
    if receipt.record_sha256 != observed_object_sha256 {
        return modeled_evaluation_v1(
            image,
            ModelDispositionV1::IntegrityIncidentQuarantined,
            "RECEIPT_RECORD_HASH_MISMATCH",
            ModeledS15ExecutionResultV1::NotInvoked,
            MappedS15FailureV1::Conflict,
        );
    }
    if receipt.lookup_commitment_sha256 != LOOKUP_COMMITMENT_SHA256 {
        return modeled_evaluation_v1(
            image,
            ModelDispositionV1::IntegrityIncidentQuarantined,
            "RECEIPT_LOOKUP_COMMITMENT_MISMATCH",
            ModeledS15ExecutionResultV1::NotInvoked,
            MappedS15FailureV1::Conflict,
        );
    }
    if receipt.source_incarnation != [0x81; 32] {
        return modeled_evaluation_v1(
            image,
            ModelDispositionV1::IntegrityIncidentQuarantined,
            "RECEIPT_SOURCE_INCARNATION_MISMATCH",
            ModeledS15ExecutionResultV1::NotInvoked,
            MappedS15FailureV1::Conflict,
        );
    }
    if receipt.object_id != [0x83; 32] {
        return modeled_evaluation_v1(
            image,
            ModelDispositionV1::IntegrityIncidentQuarantined,
            "RECEIPT_OBJECT_ID_MISMATCH",
            ModeledS15ExecutionResultV1::NotInvoked,
            MappedS15FailureV1::Conflict,
        );
    }
    if receipt.publish_sequence != 23 || receipt.previous_receipt_sha256 != [0x91; 32] {
        return modeled_evaluation_v1(
            image,
            ModelDispositionV1::IntegrityIncidentQuarantined,
            "RECEIPT_CHAIN_BINDING_MISMATCH",
            ModeledS15ExecutionResultV1::NotInvoked,
            MappedS15FailureV1::Conflict,
        );
    }

    let witness = match &durable.witness {
        ModeledWitnessSlotV1::Absent => {
            let schedule_is_known = if volatile.restarted_after_crash {
                volatile.publisher_phase.as_str() == "RECEIPT_COMMITTED"
                    && matches!(
                        &volatile.crash_cut,
                        ModeledCrashCutV1::PublishAfterReceiptCommit
                    )
            } else {
                volatile.publisher_phase.as_str() == "WITNESS_COMMITTED"
                    && matches!(&volatile.crash_cut, ModeledCrashCutV1::None)
            };
            if !schedule_is_known {
                return unknown_modeled_evaluation_v1(image);
            }
            return modeled_evaluation_v1(
                image,
                ModelDispositionV1::IncompleteFailClosed,
                if volatile.restarted_after_crash {
                    "WITNESS_MISSING_AFTER_RESTART"
                } else {
                    "WITNESS_MISSING"
                },
                ModeledS15ExecutionResultV1::NotInvoked,
                MappedS15FailureV1::Pending,
            );
        }
        ModeledWitnessSlotV1::Unavailable => {
            if volatile.restarted_after_crash
                || volatile.publisher_phase.as_str() != "WITNESS_COMMITTED"
                || !matches!(&volatile.crash_cut, ModeledCrashCutV1::None)
            {
                return unknown_modeled_evaluation_v1(image);
            }
            return modeled_evaluation_v1(
                image,
                ModelDispositionV1::IncompleteFailClosed,
                "WITNESS_UNAVAILABLE",
                ModeledS15ExecutionResultV1::NotInvoked,
                MappedS15FailureV1::Unavailable,
            );
        }
        ModeledWitnessSlotV1::Present(witness) => witness,
        ModeledWitnessSlotV1::Forked(_, _) => return unknown_modeled_evaluation_v1(image),
    };

    if exact_canonical_witness_head_v1(witness, base) {
        if let Some(selected) = &durable.selected_view {
            if exact_selected_view_binding_v1(selected, receipt, receipt_sha256) {
                if witness_proves_receipt_generation_rollback_v1(receipt, witness) {
                    return modeled_evaluation_v1(
                        image,
                        ModelDispositionV1::IntegrityIncidentQuarantined,
                        "WITNESS_HEAD_GENERATION_MISMATCH",
                        ModeledS15ExecutionResultV1::NotInvoked,
                        MappedS15FailureV1::Rollback,
                    );
                }
                if witness_proves_receipt_revision_rollback_v1(receipt, witness) {
                    return modeled_evaluation_v1(
                        image,
                        ModelDispositionV1::IntegrityIncidentQuarantined,
                        "WITNESS_HEAD_REVISION_ROLLBACK",
                        ModeledS15ExecutionResultV1::NotInvoked,
                        MappedS15FailureV1::Rollback,
                    );
                }
            }
        }
    }

    if receipt.source_generation_id != [0x82; 32] {
        return modeled_evaluation_v1(
            image,
            ModelDispositionV1::IntegrityIncidentQuarantined,
            "RECEIPT_SOURCE_GENERATION_MISMATCH",
            ModeledS15ExecutionResultV1::NotInvoked,
            MappedS15FailureV1::Conflict,
        );
    }
    if receipt.object_revision != 17 {
        return modeled_evaluation_v1(
            image,
            ModelDispositionV1::IntegrityIncidentQuarantined,
            "RECEIPT_OBJECT_REVISION_MISMATCH",
            ModeledS15ExecutionResultV1::NotInvoked,
            MappedS15FailureV1::Conflict,
        );
    }
    if !exact_receipt_binding_v1(
        receipt,
        observed_object_sha256,
        durable.object.bytes.len() as u64,
    ) {
        return unknown_modeled_evaluation_v1(image);
    }
    let witness_sha256 = computed_witness_sha256_v1(witness);
    if !exact_witness_binding_v1(witness, receipt, receipt_sha256) {
        return unknown_modeled_evaluation_v1(image);
    }

    let selected = match &durable.selected_view {
        Some(selected) => selected,
        None => return unknown_modeled_evaluation_v1(image),
    };
    if matches!(
        &selected.authority,
        ModeledReplicaAuthorityV1::NonAuthoritativeStale
    ) {
        if selected.source_incarnation == witness.source_incarnation
            && selected.source_generation_id == witness.source_generation_id
            && selected.object_id == witness.object_id
            && selected.object_revision < witness.object_revision
        {
            return modeled_evaluation_v1(
                image,
                ModelDispositionV1::IntegrityIncidentQuarantined,
                "SELECTED_REPLICA_STALE",
                ModeledS15ExecutionResultV1::NotInvoked,
                MappedS15FailureV1::Stale,
            );
        }
        return unknown_modeled_evaluation_v1(image);
    }
    if !exact_selected_view_binding_v1(selected, receipt, receipt_sha256) {
        return unknown_modeled_evaluation_v1(image);
    }
    if !exact_ack_binding_v1(&volatile.ack, receipt_sha256, witness_sha256) {
        return unknown_modeled_evaluation_v1(image);
    }

    if matches!(
        &volatile.crash_cut,
        ModeledCrashCutV1::ReadBeforeOpen
            | ModeledCrashCutV1::ReadAfterOpen
            | ModeledCrashCutV1::ReadAfterData
            | ModeledCrashCutV1::ReadAfterCompleteBeforeS14
            | ModeledCrashCutV1::ReadAfterHistorical
    ) {
        return exact_read_lifecycle_evaluation_v1(image, volatile);
    }
    if volatile.restarted_after_crash
        && matches!(
            &volatile.crash_cut,
            ModeledCrashCutV1::PublishAfterWitnessCommit | ModeledCrashCutV1::PublishAfterAck
        )
        && volatile.adapter_phase.as_str() == "FRESH"
        && volatile.adapter_post_phase.as_str() == "COMPLETED"
        && matches!(&volatile.ack, ModeledAckStateV1::NotObserved)
    {
        return modeled_evaluation_v1(
            image,
            ModelDispositionV1::ExactHistoricalReadEligible,
            "MODELED_DURABLE_TRIPLE_RECOVERED",
            ModeledS15ExecutionResultV1::StreamExact,
            MappedS15FailureV1::None,
        );
    }
    if !volatile.restarted_after_crash
        && matches!(&volatile.crash_cut, ModeledCrashCutV1::None)
        && volatile.adapter_phase.as_str() == "FRESH"
        && volatile.adapter_post_phase.as_str() == "COMPLETED"
    {
        return match (&volatile.publisher_phase, &volatile.ack) {
            (ModeledPublisherPhaseV1::Acked, ModeledAckStateV1::Observed { .. }) => {
                modeled_evaluation_v1(
                    image,
                    ModelDispositionV1::ExactHistoricalReadEligible,
                    "EXACT_MODELED_HEAD",
                    ModeledS15ExecutionResultV1::StreamExact,
                    MappedS15FailureV1::None,
                )
            }
            (ModeledPublisherPhaseV1::WitnessCommitted, ModeledAckStateV1::NotObserved) => {
                modeled_evaluation_v1(
                    image,
                    ModelDispositionV1::ExactHistoricalReadEligible,
                    "MODELED_DURABLE_TRIPLE_ACK_LOST",
                    ModeledS15ExecutionResultV1::StreamExact,
                    MappedS15FailureV1::None,
                )
            }
            _ => unknown_modeled_evaluation_v1(image),
        };
    }
    unknown_modeled_evaluation_v1(image)
}

#[allow(clippy::too_many_arguments)]
fn row_from_raw_state_v1(
    case_id: &'static str,
    variant_id: impl Into<Box<str>>,
    variant_index: u64,
    durable: ModeledDurableStateV1,
    volatile: ModeledVolatileStateV1,
    record: &[u8],
    base: &BaseCommitmentsV1,
) -> ModeledFaultRowV1 {
    let evaluation = evaluate_raw_modeled_state_v1(record, &durable, &volatile, base);
    let ModeledEvaluationV1 {
        image,
        disposition,
        reason,
        s15_execution_result,
        mapped_s15_failure,
    } = evaluation;
    let ModeledVolatileStateV1 {
        publisher_phase,
        adapter_phase,
        adapter_post_phase,
        ack,
        crash_cut,
        crash_cut_index,
        external_durability_observation_count,
        provider_durability_observation_count,
        owned_lab_durability_observation_count,
        side_effect,
        ..
    } = volatile;
    ModeledFaultRowV1 {
        case_id,
        variant_id: variant_id.into(),
        variant_index,
        publisher_phase,
        object_persistence: image.object_persistence,
        object_len: image.object_len,
        observed_object_sha256: image.observed_object_sha256,
        receipt_state: image.receipt_state,
        computed_receipt_sha256: image.computed_receipt_sha256,
        stored_receipt_sha256: image.stored_receipt_sha256,
        witness_state: image.witness_state,
        computed_witness_sha256: image.computed_witness_sha256,
        stored_witness_sha256: image.stored_witness_sha256,
        selected_view_sha256: image.selected_view_sha256,
        competing_view_sha256: image.competing_view_sha256,
        ack_state: ack,
        crash_cut,
        crash_cut_index,
        adapter_pre_state: adapter_phase,
        adapter_post_state: adapter_post_phase,
        disposition,
        reason,
        s15_execution_result,
        mapped_s15_failure,
        external_durability_observation_count,
        provider_durability_observation_count,
        owned_lab_durability_observation_count,
        side_effect,
    }
}

fn observed_ack_v1(base: &BaseCommitmentsV1) -> ModeledAckStateV1 {
    ModeledAckStateV1::Observed {
        receipt_sha256: base.receipt,
        witness_sha256: base.witness,
    }
}

fn xor_digest_byte(mut digest: [u8; 32], index: usize) -> [u8; 32] {
    digest[index] ^= 0x01;
    digest
}

fn build_case_catalog_v1(record: &[u8]) -> Result<Vec<ModeledFaultRowV1>, &'static str> {
    let base = base_commitments_v1(record)?;
    let mut rows = Vec::with_capacity(ROW_COUNT);

    let mut d00_volatile = volatile_state_v1(ModeledPublisherPhaseV1::Acked);
    d00_volatile.ack = observed_ack_v1(&base);
    d00_volatile.adapter_post_phase = ModeledAdapterPhaseV1::Completed;
    rows.push(row_from_raw_state_v1(
        "D00_CLEAN_COMMITTED_HEAD",
        "CLEAN",
        0,
        base_triple_state_v1(record),
        d00_volatile,
        record,
        &base,
    ));

    for prefix_len in 1..CANONICAL_RECORD_LEN {
        let mut volatile = volatile_state_v1(ModeledPublisherPhaseV1::ObjectPrefix);
        volatile.crash_cut = ModeledCrashCutV1::PublishAfterObjectPrefix;
        volatile.crash_cut_index = prefix_len as u64;
        rows.push(row_from_raw_state_v1(
            "D01_TORN_OR_PARTIAL_OBJECT",
            format!("PREFIX_CUT_{prefix_len:04}"),
            (prefix_len - 1) as u64,
            prefix_state_v1(record, prefix_len),
            volatile,
            record,
            &base,
        ));
    }

    let d02_variants = [
        ("ACK_AT_EMPTY", 0usize),
        ("ACK_AT_OBJECT_PARTIAL", 1),
        ("ACK_AT_OBJECT_COMMITTED", 2),
        ("ACK_AT_RECEIPT_COMMITTED", 3),
    ];
    for (variant_id, variant_index) in d02_variants {
        let durable = match variant_index {
            0 => absent_state_v1(),
            1 => prefix_state_v1(record, 2_747),
            2 => object_only_state_v1(record),
            _ => object_receipt_state_v1(record),
        };
        let mut volatile = volatile_state_v1(ModeledPublisherPhaseV1::Acked);
        volatile.ack = observed_ack_v1(&base);
        rows.push(row_from_raw_state_v1(
            "D02_ACK_BEFORE_DURABLE_COMMIT",
            variant_id,
            variant_index as u64,
            durable,
            volatile,
            record,
            &base,
        ));
    }

    let mut d03_volatile = volatile_state_v1(ModeledPublisherPhaseV1::WitnessCommitted);
    d03_volatile.adapter_post_phase = ModeledAdapterPhaseV1::Completed;
    rows.push(row_from_raw_state_v1(
        "D03_DURABLE_HEAD_ACK_LOST",
        "ACK_NOT_OBSERVED_AFTER_WITNESS",
        0,
        base_triple_state_v1(record),
        d03_volatile,
        record,
        &base,
    ));

    let d04 = [
        (
            "CRASH_AT_EMPTY_RESTART",
            absent_state_v1(),
            ModeledPublisherPhaseV1::Empty,
            ModeledCrashCutV1::None,
            0,
            false,
        ),
        (
            "CRASH_AFTER_OBJECT_PREFIX_RESTART",
            prefix_state_v1(record, 2_747),
            ModeledPublisherPhaseV1::ObjectPrefix,
            ModeledCrashCutV1::PublishAfterObjectPrefix,
            2_747,
            false,
        ),
        (
            "CRASH_AFTER_OBJECT_COMMIT_RESTART",
            object_only_state_v1(record),
            ModeledPublisherPhaseV1::ObjectCommitted,
            ModeledCrashCutV1::PublishAfterObjectCommit,
            0,
            false,
        ),
        (
            "CRASH_AFTER_RECEIPT_COMMIT_RESTART",
            object_receipt_state_v1(record),
            ModeledPublisherPhaseV1::ReceiptCommitted,
            ModeledCrashCutV1::PublishAfterReceiptCommit,
            0,
            false,
        ),
        (
            "CRASH_AFTER_WITNESS_COMMIT_RESTART",
            base_triple_state_v1(record),
            ModeledPublisherPhaseV1::WitnessCommitted,
            ModeledCrashCutV1::PublishAfterWitnessCommit,
            0,
            true,
        ),
        (
            "CRASH_AFTER_ACK_RESTART",
            base_triple_state_v1(record),
            ModeledPublisherPhaseV1::Acked,
            ModeledCrashCutV1::PublishAfterAck,
            0,
            true,
        ),
    ];
    for (variant_index, (variant_id, durable, phase, cut, cut_index, completes)) in
        d04.into_iter().enumerate()
    {
        let mut volatile = volatile_state_v1(phase);
        volatile.crash_cut = cut;
        volatile.crash_cut_index = cut_index;
        volatile.restarted_after_crash = true;
        if completes {
            volatile.adapter_post_phase = ModeledAdapterPhaseV1::Completed;
        }
        rows.push(row_from_raw_state_v1(
            "D04_PUBLISH_CRASH_RESTART_CUTS",
            variant_id,
            variant_index as u64,
            durable,
            volatile,
            record,
            &base,
        ));
    }

    for cut_ordinal in 0..53usize {
        let (cut_id, data_ordinal) = match cut_ordinal {
            0 => ("BEFORE_OPEN".to_owned(), 0usize),
            1 => ("AFTER_OPEN".to_owned(), 0),
            2..=50 => (
                format!("AFTER_DATA_{:04}", cut_ordinal - 1),
                cut_ordinal - 1,
            ),
            51 => ("AFTER_COMPLETE_BEFORE_S14".to_owned(), 0),
            _ => ("AFTER_HISTORICAL".to_owned(), 0),
        };
        for phase_ordinal in 0..2usize {
            let restart = phase_ordinal == 1;
            let variant_id = format!(
                "{cut_id}_{}",
                if restart { "RESTART" } else { "FIRST_ATTEMPT" }
            );
            let (cut, cut_index) = match cut_ordinal {
                0 => (ModeledCrashCutV1::ReadBeforeOpen, 0),
                1 => (ModeledCrashCutV1::ReadAfterOpen, 0),
                2..=50 => (ModeledCrashCutV1::ReadAfterData, data_ordinal as u64),
                51 => (ModeledCrashCutV1::ReadAfterCompleteBeforeS14, 0),
                _ => (ModeledCrashCutV1::ReadAfterHistorical, 0),
            };
            let (adapter_pre, adapter_post) = if restart {
                (
                    ModeledAdapterPhaseV1::Fresh,
                    ModeledAdapterPhaseV1::Completed,
                )
            } else {
                match cut_ordinal {
                    0 => (ModeledAdapterPhaseV1::Fresh, ModeledAdapterPhaseV1::Fresh),
                    1..=50 => (
                        ModeledAdapterPhaseV1::Streaming,
                        ModeledAdapterPhaseV1::TerminalFailed,
                    ),
                    51 => (
                        ModeledAdapterPhaseV1::Streaming,
                        ModeledAdapterPhaseV1::Completed,
                    ),
                    _ => (
                        ModeledAdapterPhaseV1::Completed,
                        ModeledAdapterPhaseV1::Completed,
                    ),
                }
            };
            let observed_data_steps = if restart || cut_ordinal >= 51 {
                DATA_STEP_COUNT as u64
            } else if (2..=50).contains(&cut_ordinal) {
                data_ordinal as u64
            } else {
                0
            };
            let mut volatile = volatile_state_v1(ModeledPublisherPhaseV1::Acked);
            volatile.crash_cut = cut;
            volatile.crash_cut_index = cut_index;
            volatile.adapter_phase = adapter_pre;
            volatile.adapter_post_phase = adapter_post;
            volatile.observed_data_steps = observed_data_steps;
            volatile.observed_len =
                (observed_data_steps * DATA_STEP_BYTES as u64).min(CANONICAL_RECORD_LEN as u64);
            volatile.restarted_after_crash = restart;
            rows.push(row_from_raw_state_v1(
                "D05_S15_READ_CRASH_RESTART_CUTS",
                variant_id,
                (2 * cut_ordinal + phase_ordinal) as u64,
                base_triple_state_v1(record),
                volatile,
                record,
                &base,
            ));
        }
    }

    rows.push(row_from_raw_state_v1(
        "D06_OBJECT_PRESENT_RECEIPT_ABSENT",
        "COMMITTED_OBJECT_NO_RECEIPT",
        0,
        object_only_state_v1(record),
        volatile_state_v1(ModeledPublisherPhaseV1::ObjectCommitted),
        record,
        &base,
    ));
    rows.push(row_from_raw_state_v1(
        "D07_RECEIPT_PRESENT_OBJECT_ABSENT",
        "COMMITTED_RECEIPT_NO_OBJECT",
        0,
        receipt_without_object_state_v1(),
        volatile_state_v1(ModeledPublisherPhaseV1::ReceiptCommitted),
        record,
        &base,
    ));

    let d08_variants = ["LENGTH", "HASH", "GENERATION", "OBJECT_ID", "REVISION"];
    for (variant_index, variant_id) in d08_variants.into_iter().enumerate() {
        let generation = if variant_index == 2 {
            [0xa2; 32]
        } else {
            [0x82; 32]
        };
        let object_id = if variant_index == 3 {
            [0xa3; 32]
        } else {
            [0x83; 32]
        };
        let revision = if variant_index == 4 { 18 } else { 17 };
        let record_len = if variant_index == 0 { 5_495 } else { 5_494 };
        let record_sha256 = if variant_index == 1 {
            xor_digest_byte(CANONICAL_RECORD_SHA256, 0)
        } else {
            CANONICAL_RECORD_SHA256
        };
        let receipt = receipt_for_v1(
            generation,
            object_id,
            revision,
            record_len,
            record_sha256,
            [0x91; 32],
        );
        let receipt_sha256 = computed_receipt_sha256_v1(&receipt);
        let witness = witness_for_v1(
            generation,
            object_id,
            revision,
            record_sha256,
            receipt_sha256,
            [0x95; 32],
        );
        let view = view_for_v1(
            [0x96; 32],
            ModeledReplicaAuthorityV1::ClaimsAuthoritative,
            generation,
            object_id,
            revision,
            record_len,
            record_sha256,
            receipt_sha256,
        );
        let durable = ModeledDurableStateV1 {
            object: ModeledObjectSlotV1 {
                persistence: ModeledObjectPersistenceV1::Committed,
                bytes: record.into(),
            },
            receipt: ModeledReceiptSlotV1::Committed(receipt),
            witness: ModeledWitnessSlotV1::Present(witness),
            selected_view: Some(view),
            competing_view: None,
        };
        rows.push(row_from_raw_state_v1(
            "D08_RECEIPT_OBJECT_BINDING_MISMATCH",
            variant_id,
            variant_index as u64,
            durable,
            volatile_state_v1(ModeledPublisherPhaseV1::WitnessCommitted),
            record,
            &base,
        ));
    }

    let old_receipt = receipt_for_v1(
        [0x80; 32],
        [0x83; 32],
        17,
        5_494,
        CANONICAL_RECORD_SHA256,
        [0x91; 32],
    );
    let old_receipt_sha = computed_receipt_sha256_v1(&old_receipt);
    let old_view = view_for_v1(
        [0x96; 32],
        ModeledReplicaAuthorityV1::ClaimsAuthoritative,
        [0x80; 32],
        [0x83; 32],
        17,
        5_494,
        CANONICAL_RECORD_SHA256,
        old_receipt_sha,
    );
    let mut old_state = base_triple_state_v1(record);
    old_state.receipt = ModeledReceiptSlotV1::Committed(old_receipt);
    old_state.selected_view = Some(old_view);
    rows.push(row_from_raw_state_v1(
        "D09_OLD_GENERATION_SNAPSHOT",
        "OLD_GENERATION_EXACT_OBJECT",
        0,
        old_state,
        volatile_state_v1(ModeledPublisherPhaseV1::WitnessCommitted),
        record,
        &base,
    ));

    let lower_receipt = receipt_for_v1(
        [0x82; 32],
        [0x83; 32],
        16,
        5_494,
        CANONICAL_RECORD_SHA256,
        [0x91; 32],
    );
    let lower_receipt_sha = computed_receipt_sha256_v1(&lower_receipt);
    let lower_view = view_for_v1(
        [0x96; 32],
        ModeledReplicaAuthorityV1::ClaimsAuthoritative,
        [0x82; 32],
        [0x83; 32],
        16,
        5_494,
        CANONICAL_RECORD_SHA256,
        lower_receipt_sha,
    );
    let mut lower_state = base_triple_state_v1(record);
    lower_state.receipt = ModeledReceiptSlotV1::Committed(lower_receipt);
    lower_state.selected_view = Some(lower_view);
    rows.push(row_from_raw_state_v1(
        "D10_SAME_GENERATION_LOWER_REVISION",
        "LOWER_REVISION_EXACT_OBJECT",
        0,
        lower_state,
        volatile_state_v1(ModeledPublisherPhaseV1::WitnessCommitted),
        record,
        &base,
    ));

    for variant_index in 0..2usize {
        let record_sha256 = if variant_index == 0 {
            xor_digest_byte(CANONICAL_RECORD_SHA256, 0)
        } else {
            CANONICAL_RECORD_SHA256
        };
        let previous_receipt = if variant_index == 1 {
            [0x99; 32]
        } else {
            [0x91; 32]
        };
        let receipt = receipt_for_v1(
            [0x82; 32],
            [0x83; 32],
            17,
            5_494,
            record_sha256,
            previous_receipt,
        );
        let receipt_sha = computed_receipt_sha256_v1(&receipt);
        let competing = view_for_v1(
            [0x97; 32],
            ModeledReplicaAuthorityV1::ClaimsAuthoritative,
            [0x82; 32],
            [0x83; 32],
            17,
            5_494,
            record_sha256,
            receipt_sha,
        );
        let mut durable = base_triple_state_v1(record);
        durable.competing_view = Some(competing);
        rows.push(row_from_raw_state_v1(
            "D11_SAME_REVISION_EQUIVOCATION",
            if variant_index == 0 {
                "DIVERGENT_RECORD_HASH"
            } else {
                "DIVERGENT_RECEIPT_HASH"
            },
            variant_index as u64,
            durable,
            volatile_state_v1(ModeledPublisherPhaseV1::WitnessCommitted),
            record,
            &base,
        ));
    }

    let stale_view = view_for_v1(
        [0x96; 32],
        ModeledReplicaAuthorityV1::NonAuthoritativeStale,
        [0x82; 32],
        [0x83; 32],
        16,
        5_494,
        CANONICAL_RECORD_SHA256,
        lower_receipt_sha,
    );
    let mut stale_state = base_triple_state_v1(record);
    stale_state.selected_view = Some(stale_view);
    rows.push(row_from_raw_state_v1(
        "D12_SELECTED_STALE_REPLICA",
        "NON_AUTHORITATIVE_STALE_VIEW",
        0,
        stale_state,
        volatile_state_v1(ModeledPublisherPhaseV1::WitnessCommitted),
        record,
        &base,
    ));

    for variant_index in 0..3usize {
        let generation = if variant_index == 0 {
            [0xa2; 32]
        } else {
            [0x82; 32]
        };
        let revision = if variant_index == 0 { 17 } else { 18 };
        let record_sha256 = if variant_index == 2 {
            xor_digest_byte(CANONICAL_RECORD_SHA256, 16)
        } else {
            CANONICAL_RECORD_SHA256
        };
        let receipt = receipt_for_v1(
            generation,
            [0x83; 32],
            revision,
            5_494,
            record_sha256,
            [0x91; 32],
        );
        let competing = view_for_v1(
            [0x97; 32],
            ModeledReplicaAuthorityV1::ClaimsAuthoritative,
            generation,
            [0x83; 32],
            revision,
            5_494,
            record_sha256,
            computed_receipt_sha256_v1(&receipt),
        );
        let mut durable = base_triple_state_v1(record);
        durable.competing_view = Some(competing);
        rows.push(row_from_raw_state_v1(
            "D13_DIVERGENT_AUTHORITATIVE_VIEWS",
            match variant_index {
                0 => "DIVERGENT_GENERATION",
                1 => "DIVERGENT_REVISION",
                _ => "DIVERGENT_RECORD",
            },
            variant_index as u64,
            durable,
            volatile_state_v1(ModeledPublisherPhaseV1::WitnessCommitted),
            record,
            &base,
        ));
    }

    let d14_variants = [
        "MISSING",
        "UNAVAILABLE",
        "CORRUPT_STORED_HASH",
        "FORKED_SAME_SEQUENCE",
    ];
    for variant_index in 0..4usize {
        let mut durable = base_triple_state_v1(record);
        match variant_index {
            0 => durable.witness = ModeledWitnessSlotV1::Absent,
            1 => durable.witness = ModeledWitnessSlotV1::Unavailable,
            2 => match &mut durable.witness {
                ModeledWitnessSlotV1::Present(witness) => {
                    witness.stored_witness_sha256 = xor_digest_byte(base.witness, 7);
                }
                _ => return Err("base witness state drifted"),
            },
            _ => {
                let fork = witness_for_v1(
                    [0x82; 32],
                    [0x83; 32],
                    17,
                    CANONICAL_RECORD_SHA256,
                    base.receipt,
                    [0x9a; 32],
                );
                durable.witness =
                    ModeledWitnessSlotV1::Forked(canonical_witness_v1(base.receipt), fork);
            }
        }
        rows.push(row_from_raw_state_v1(
            "D14_WITNESS_FAILURES",
            d14_variants[variant_index],
            variant_index as u64,
            durable,
            volatile_state_v1(ModeledPublisherPhaseV1::WitnessCommitted),
            record,
            &base,
        ));
    }

    let components = ["OBJECT", "RECEIPT_STORED_HASH", "WITNESS_STORED_HASH"];
    let positions = ["FIRST", "MIDDLE", "LAST"];
    for (component_ordinal, component) in components.into_iter().enumerate() {
        for (position_ordinal, position) in positions.into_iter().enumerate() {
            let mut durable = base_triple_state_v1(record);
            let digest_index = [0usize, 16, 31][position_ordinal];
            match component_ordinal {
                0 => {
                    let object_index = [0usize, 2_747, 5_493][position_ordinal];
                    durable.object.bytes[object_index] ^= 0x01;
                }
                1 => match &mut durable.receipt {
                    ModeledReceiptSlotV1::Committed(receipt) => {
                        receipt.stored_receipt_sha256 = xor_digest_byte(base.receipt, digest_index);
                    }
                    ModeledReceiptSlotV1::Absent => return Err("base receipt state drifted"),
                },
                _ => match &mut durable.witness {
                    ModeledWitnessSlotV1::Present(witness) => {
                        witness.stored_witness_sha256 = xor_digest_byte(base.witness, digest_index);
                    }
                    _ => return Err("base witness state drifted"),
                },
            }
            rows.push(row_from_raw_state_v1(
                "D15_POST_PERSISTENCE_CORRUPTION",
                format!("{component}_BIT_{position}"),
                (3 * component_ordinal + position_ordinal) as u64,
                durable,
                volatile_state_v1(ModeledPublisherPhaseV1::WitnessCommitted),
                record,
                &base,
            ));
        }
    }

    if rows.len() != ROW_COUNT {
        return Err("closed catalog cardinality drifted");
    }
    Ok(rows)
}

#[cfg(test)]
mod tests {
    use super::super::super::{
        BoundedRecoveredSourceRecordV1, ExactRecoveredEnvelopeLookupV1,
        ExternalRecoveredEnvelopeSourceV1,
    };
    use super::super::{
        exact_lookup_commitment_v1, runtime_transport_seal, AdapterStateV1,
        BoundedRuntimeRecoveredEnvelopeAdapterV1, RuntimeExactReadCompletionV1,
        RuntimeExactReadFailureV1, RuntimeExactReadStepV1,
        RuntimeExactRecoveredEnvelopeTransportV1,
    };
    use super::*;
    use std::collections::{HashMap, HashSet};

    struct ModelTransport {
        bytes: Box<[u8]>,
        cursor: usize,
        emitted_data_steps: usize,
        fail_after_data_steps: Option<usize>,
        expected_lookup_sha256: [u8; 32],
        opens: usize,
        completions: usize,
    }

    impl ModelTransport {
        fn exact(lookup: &ExactRecoveredEnvelopeLookupV1, bytes: &[u8]) -> Self {
            Self {
                bytes: bytes.into(),
                cursor: 0,
                emitted_data_steps: 0,
                fail_after_data_steps: None,
                expected_lookup_sha256: exact_lookup_commitment_v1(lookup),
                opens: 0,
                completions: 0,
            }
        }

        fn crash_after_data_steps(
            lookup: &ExactRecoveredEnvelopeLookupV1,
            bytes: &[u8],
            data_steps: usize,
        ) -> Self {
            let mut transport = Self::exact(lookup, bytes);
            transport.fail_after_data_steps = Some(data_steps);
            transport
        }
    }

    impl runtime_transport_seal::Sealed for ModelTransport {}

    impl RuntimeExactRecoveredEnvelopeTransportV1 for ModelTransport {
        fn open_exact(
            &mut self,
            lookup: &ExactRecoveredEnvelopeLookupV1,
        ) -> Result<(), RuntimeExactReadFailureV1> {
            self.opens += 1;
            if exact_lookup_commitment_v1(lookup) != self.expected_lookup_sha256 {
                return Err(RuntimeExactReadFailureV1::Conflict);
            }
            Ok(())
        }

        fn read_into(
            &mut self,
            destination: &mut [u8],
        ) -> Result<RuntimeExactReadStepV1, RuntimeExactReadFailureV1> {
            if self.fail_after_data_steps == Some(self.emitted_data_steps) {
                self.fail_after_data_steps = None;
                return Err(RuntimeExactReadFailureV1::Indeterminate);
            }
            if self.cursor == self.bytes.len() {
                self.completions += 1;
                return Ok(RuntimeExactReadStepV1::Complete(
                    RuntimeExactReadCompletionV1 {
                        lookup_commitment_sha256: self.expected_lookup_sha256,
                        object_revision: 17,
                        record_len: self.bytes.len() as u64,
                        record_sha256: sha256_bytes(&self.bytes),
                    },
                ));
            }
            let written = (self.bytes.len() - self.cursor)
                .min(DATA_STEP_BYTES)
                .min(destination.len());
            destination[..written].copy_from_slice(&self.bytes[self.cursor..self.cursor + written]);
            self.cursor += written;
            self.emitted_data_steps += 1;
            Ok(RuntimeExactReadStepV1::Data(written))
        }
    }

    fn fixture_record() -> Vec<u8> {
        super::super::super::tests::s15_fixture_parts().0
    }

    fn catalog() -> Vec<ModeledFaultRowV1> {
        let record = fixture_record();
        build_case_catalog_v1(&record).unwrap()
    }

    fn family<'a>(rows: &'a [ModeledFaultRowV1], case_id: &str) -> Vec<&'a ModeledFaultRowV1> {
        rows.iter().filter(|row| row.case_id == case_id).collect()
    }

    fn assert_outcome(row: &ModeledFaultRowV1, disposition: &str, result: &str, failure: &str) {
        assert_eq!(row.disposition.as_str(), disposition);
        assert_eq!(row.s15_execution_result.as_str(), result);
        assert_eq!(row.mapped_s15_failure.as_str(), failure);
    }

    fn direct_exact_read(
        record: &[u8],
        lookup: &ExactRecoveredEnvelopeLookupV1,
    ) -> BoundedRuntimeRecoveredEnvelopeAdapterV1<ModelTransport> {
        let adapter =
            BoundedRuntimeRecoveredEnvelopeAdapterV1::new(ModelTransport::exact(lookup, record));
        let mut sink = BoundedRecoveredSourceRecordV1::new();
        assert!(adapter.read_exact(lookup, &mut sink).is_ok());
        assert_eq!(sink.finish().unwrap().as_ref(), record);
        adapter
    }

    fn hex(value: &[u8]) -> String {
        value.iter().map(|byte| format!("{byte:02x}")).collect()
    }

    #[test]
    fn s16_known_answer_receipt_witness_row_and_full_historical_chain_are_stable() {
        let (record, lookup, source_permit, base, s10_permit) =
            super::super::super::tests::s15_fixture_parts();
        assert_eq!(
            exact_lookup_commitment_v1(&lookup),
            LOOKUP_COMMITMENT_SHA256
        );
        assert_eq!(sha256_bytes(&record), CANONICAL_RECORD_SHA256);

        let receipt = receipt_for_v1(
            [0x82; 32],
            [0x83; 32],
            17,
            5_494,
            CANONICAL_RECORD_SHA256,
            [0x91; 32],
        );
        let receipt_message = receipt_message_v1(&receipt);
        assert_eq!(receipt_message.len(), 633);
        assert_eq!(sha256_bytes(&receipt_message), RECEIPT_KAT_SHA256);
        assert_eq!(
            hex(&sha256_bytes(&receipt_message)),
            "12c80f1b610d48438ec69457a6f553bf48fd6a15a9c3ffebd7b20c67895b76a2"
        );
        let witness = witness_for_v1(
            [0x82; 32],
            [0x83; 32],
            17,
            CANONICAL_RECORD_SHA256,
            computed_receipt_sha256_v1(&receipt),
            [0x95; 32],
        );
        let witness_message = witness_message_v1(&witness);
        assert_eq!(witness_message.len(), 777);
        assert_eq!(sha256_bytes(&witness_message), WITNESS_KAT_SHA256);
        assert_eq!(
            hex(&sha256_bytes(&witness_message)),
            "c336caea644548f287ddc285ee3b9433f853f9b1f562cee9f055df913458bf99"
        );
        let view = view_for_v1(
            [0x96; 32],
            ModeledReplicaAuthorityV1::ClaimsAuthoritative,
            [0x82; 32],
            [0x83; 32],
            17,
            5_494,
            CANONICAL_RECORD_SHA256,
            computed_receipt_sha256_v1(&receipt),
        );
        let view_message = replica_view_message_v1(&view);
        assert_eq!(view_message.len(), 684);
        assert_eq!(sha256_bytes(&view_message), SELECTED_VIEW_KAT_SHA256);
        assert_eq!(
            hex(&sha256_bytes(&view_message)),
            "9a8f959a01d3aead14b527d51bb1c744999e8e1ee33a564cea72bb15b2b00d6a"
        );
        let mut absent_message = Vec::new();
        append_frame(&mut absent_message, ABSENT_DOMAIN);
        append_frame(&mut absent_message, b"REPLICA_VIEW");
        assert_eq!(absent_message.len(), 100);
        assert_eq!(
            hex(&sha256_bytes(&absent_message)),
            "7d506bb223224db017103509af3ce278291bc82d53fc6c450376b57c1c4331cc"
        );
        let rows = build_case_catalog_v1(&record).unwrap();
        let clean_message = row_message_v1(&rows[0]);
        assert_eq!(clean_message.len(), 1_061);
        assert_eq!(sha256_bytes(&clean_message), D00_ROW_KAT_SHA256);
        assert_eq!(
            hex(&sha256_bytes(&clean_message)),
            "b9e4f9ab470de985c97b50292deae898181c96e21894b43de23ec98ec3fced1a"
        );

        let adapter =
            BoundedRuntimeRecoveredEnvelopeAdapterV1::new(ModelTransport::exact(&lookup, &record));
        let historical = super::super::super::recover_historical_from_external_source_v1(
            &adapter,
            lookup,
            &source_permit,
            &base.s9_permit,
            &s10_permit,
            &base.s11_request,
            &base.s11_permit,
            &base.s11_record,
        )
        .unwrap();
        assert_eq!(
            hex(&historical.historical_source_chain_sha256),
            "d29da2a081b09b2b124298eae40b15ada555196cc5e3fd52d8e4dfadf3f2149b"
        );
        assert_eq!(adapter.state.get(), AdapterStateV1::Completed);
        assert_eq!(adapter.transport.borrow().opens, 1);
    }

    #[test]
    fn s16_legal_publish_transition_order_is_closed_and_wrong_order_rejects() {
        let mut phase = ModeledPublisherPhaseV1::Empty;
        for next in [
            ModeledPublisherPhaseV1::ObjectPrefix,
            ModeledPublisherPhaseV1::ObjectCommitted,
            ModeledPublisherPhaseV1::ReceiptCommitted,
            ModeledPublisherPhaseV1::WitnessCommitted,
            ModeledPublisherPhaseV1::Acked,
        ] {
            assert!(advance_publisher_phase_v1(&mut phase, next).is_ok());
        }
        assert!(
            advance_publisher_phase_v1(&mut phase, ModeledPublisherPhaseV1::ObjectPrefix).is_err()
        );
        let mut wrong = ModeledPublisherPhaseV1::Empty;
        assert!(
            advance_publisher_phase_v1(&mut wrong, ModeledPublisherPhaseV1::ReceiptCommitted)
                .is_err()
        );
        assert_eq!(wrong.as_str(), "EMPTY");
    }

    #[test]
    fn s16_case_catalog_is_closed_unique_and_5639_row_commitments_are_deterministic() {
        let record = fixture_record();
        let base = base_commitments_v1(&record).unwrap();
        let rows = build_case_catalog_v1(&record).unwrap();
        assert_eq!(rows.len(), ROW_COUNT);
        let expected_counts = [
            ("D00_CLEAN_COMMITTED_HEAD", 1usize),
            ("D01_TORN_OR_PARTIAL_OBJECT", 5_493),
            ("D02_ACK_BEFORE_DURABLE_COMMIT", 4),
            ("D03_DURABLE_HEAD_ACK_LOST", 1),
            ("D04_PUBLISH_CRASH_RESTART_CUTS", 6),
            ("D05_S15_READ_CRASH_RESTART_CUTS", 106),
            ("D06_OBJECT_PRESENT_RECEIPT_ABSENT", 1),
            ("D07_RECEIPT_PRESENT_OBJECT_ABSENT", 1),
            ("D08_RECEIPT_OBJECT_BINDING_MISMATCH", 5),
            ("D09_OLD_GENERATION_SNAPSHOT", 1),
            ("D10_SAME_GENERATION_LOWER_REVISION", 1),
            ("D11_SAME_REVISION_EQUIVOCATION", 2),
            ("D12_SELECTED_STALE_REPLICA", 1),
            ("D13_DIVERGENT_AUTHORITATIVE_VIEWS", 3),
            ("D14_WITNESS_FAILURES", 4),
            ("D15_POST_PERSISTENCE_CORRUPTION", 9),
        ];
        let mut counts = HashMap::new();
        let mut keys = HashSet::new();
        let mut commitments = HashSet::new();
        let mut previous: Option<(&str, u64)> = None;
        for row in &rows {
            *counts.entry(row.case_id).or_insert(0usize) += 1;
            assert!(keys.insert((row.case_id, row.variant_index)));
            assert!(commitments.insert(row_commitment_v1(row)));
            if let Some((case_id, index)) = previous {
                assert!(
                    case_id < row.case_id || (case_id == row.case_id && index < row.variant_index)
                );
            }
            previous = Some((row.case_id, row.variant_index));
        }
        for (case_id, expected) in expected_counts {
            assert_eq!(counts.get(case_id), Some(&expected));
        }
        let message = catalog_message_v1(&rows);
        assert_eq!(message.len(), CATALOG_MESSAGE_LEN);
        assert_eq!(catalog_commitment_v1(&rows), CATALOG_KAT_SHA256);

        let mut alpha_volatile = volatile_state_v1(ModeledPublisherPhaseV1::Acked);
        alpha_volatile.ack = observed_ack_v1(&base);
        alpha_volatile.adapter_post_phase = ModeledAdapterPhaseV1::Completed;
        let alpha = row_from_raw_state_v1(
            "LABEL_ALPHA_IS_NOT_AN_ORACLE",
            "VARIANT_ALPHA",
            7,
            base_triple_state_v1(&record),
            alpha_volatile,
            &record,
            &base,
        );
        let mut beta_volatile = volatile_state_v1(ModeledPublisherPhaseV1::Acked);
        beta_volatile.ack = observed_ack_v1(&base);
        beta_volatile.adapter_post_phase = ModeledAdapterPhaseV1::Completed;
        let beta = row_from_raw_state_v1(
            "LABEL_BETA_IS_NOT_AN_ORACLE",
            "VARIANT_BETA",
            99,
            base_triple_state_v1(&record),
            beta_volatile,
            &record,
            &base,
        );
        assert_ne!(alpha.case_id, beta.case_id);
        assert_ne!(alpha.variant_id, beta.variant_id);
        assert_eq!(alpha.disposition.as_str(), beta.disposition.as_str());
        assert_eq!(alpha.reason, beta.reason);
        assert_eq!(
            alpha.s15_execution_result.as_str(),
            beta.s15_execution_result.as_str()
        );
        assert_eq!(
            alpha.mapped_s15_failure.as_str(),
            beta.mapped_s15_failure.as_str()
        );
        drop(rows);
        assert_eq!(catalog_commitment_v1(&catalog()), CATALOG_KAT_SHA256);
    }

    #[test]
    fn s16_every_partial_object_prefix_fails_closed_without_open() {
        let record = fixture_record();
        let rows = catalog();
        let partial = family(&rows, "D01_TORN_OR_PARTIAL_OBJECT");
        assert_eq!(partial.len(), CANONICAL_RECORD_LEN - 1);
        for (offset, row) in partial.into_iter().enumerate() {
            let prefix_len = offset + 1;
            let expected_variant = format!("PREFIX_CUT_{prefix_len:04}");
            assert_eq!(row.variant_id.as_ref(), expected_variant.as_str());
            assert_eq!(row.variant_index, offset as u64);
            assert_eq!(row.object_len, prefix_len as u64);
            assert_eq!(
                row.observed_object_sha256,
                sha256_bytes(&record[..prefix_len])
            );
            assert_eq!(row.crash_cut.as_str(), "PUBLISH_AFTER_OBJECT_PREFIX");
            assert_eq!(row.crash_cut_index, prefix_len as u64);
            assert_outcome(
                row,
                "MODEL_INCOMPLETE_FAIL_CLOSED",
                "NOT_INVOKED",
                "MALFORMED",
            );
        }
    }

    #[test]
    fn s16_premature_ack_variants_are_ambiguous_and_indeterminate() {
        let record = fixture_record();
        let base = base_commitments_v1(&record).unwrap();
        let rows = catalog();
        let family = family(&rows, "D02_ACK_BEFORE_DURABLE_COMMIT");
        assert_eq!(family.len(), 4);
        for row in family {
            assert_eq!(row.ack_state.as_str(), "OBSERVED");
            assert_eq!(row.publisher_phase.as_str(), "ACKED");
            assert_eq!(row.reason, "ACK_OUTRAN_MODELED_DURABILITY");
            assert_outcome(
                row,
                "MODEL_AMBIGUOUS_QUARANTINED",
                "NOT_INVOKED",
                "INDETERMINATE",
            );
        }

        let mut wrong_ack = volatile_state_v1(ModeledPublisherPhaseV1::Acked);
        wrong_ack.ack = ModeledAckStateV1::Observed {
            receipt_sha256: xor_digest_byte(base.receipt, 0),
            witness_sha256: base.witness,
        };
        wrong_ack.adapter_post_phase = ModeledAdapterPhaseV1::Completed;
        let evaluation = evaluate_raw_modeled_state_v1(
            &record,
            &base_triple_state_v1(&record),
            &wrong_ack,
            &base,
        );
        assert_eq!(
            evaluation.disposition.as_str(),
            "MODEL_AMBIGUOUS_QUARANTINED"
        );
        assert_eq!(evaluation.reason, "UNCLASSIFIED_MODELED_STATE");
        assert_eq!(evaluation.mapped_s15_failure.as_str(), "INDETERMINATE");
    }

    #[test]
    fn s16_durable_triple_with_lost_ack_uses_fresh_exact_read() {
        let (record, lookup, ..) = super::super::super::tests::s15_fixture_parts();
        let rows = catalog();
        let row = family(&rows, "D03_DURABLE_HEAD_ACK_LOST")[0];
        assert_eq!(row.ack_state.as_str(), "NOT_OBSERVED");
        assert_eq!(row.adapter_pre_state.as_str(), "FRESH");
        assert_eq!(row.adapter_post_state.as_str(), "COMPLETED");
        assert_outcome(
            row,
            "MODEL_EXACT_HISTORICAL_READ_ELIGIBLE",
            "STREAM_EXACT",
            "NONE",
        );
        let adapter = direct_exact_read(&record, &lookup);
        assert_eq!(adapter.transport.borrow().opens, 1);
    }

    #[test]
    fn s16_every_publish_crash_cut_restarts_from_modeled_persisted_image_only() {
        let rows = catalog();
        let family = family(&rows, "D04_PUBLISH_CRASH_RESTART_CUTS");
        assert_eq!(family.len(), 6);
        let expected = [
            ("NONE", 0, "NOT_FOUND"),
            ("PUBLISH_AFTER_OBJECT_PREFIX", 2_747, "MALFORMED"),
            ("PUBLISH_AFTER_OBJECT_COMMIT", 0, "PENDING"),
            ("PUBLISH_AFTER_RECEIPT_COMMIT", 0, "PENDING"),
            ("PUBLISH_AFTER_WITNESS_COMMIT", 0, "NONE"),
            ("PUBLISH_AFTER_ACK", 0, "NONE"),
        ];
        for (row, (cut, index, failure)) in family.into_iter().zip(expected) {
            assert_eq!(row.ack_state.as_str(), "NOT_OBSERVED");
            assert_eq!(row.crash_cut.as_str(), cut);
            assert_eq!(row.crash_cut_index, index);
            assert_eq!(row.mapped_s15_failure.as_str(), failure);
            if failure == "NONE" {
                assert_eq!(row.adapter_post_state.as_str(), "COMPLETED");
            } else {
                assert_eq!(row.s15_execution_result.as_str(), "NOT_INVOKED");
            }
        }
    }

    #[test]
    fn s16_every_s15_read_crash_cut_discards_partial_state_and_uses_fresh_adapter() {
        let (record, lookup, ..) = super::super::super::tests::s15_fixture_parts();
        let rows = catalog();
        let family = family(&rows, "D05_S15_READ_CRASH_RESTART_CUTS");
        assert_eq!(family.len(), 106);
        assert_eq!(DATA_STEP_COUNT, record.chunks(DATA_STEP_BYTES).count());
        // All 53 cut positions below are synthetic model rows, not observed
        // durability or runtime evidence.
        for cut in 0..53usize {
            let first = family[2 * cut];
            let restart = family[2 * cut + 1];
            assert_eq!(first.variant_index, (2 * cut) as u64);
            assert_eq!(restart.variant_index, (2 * cut + 1) as u64);
            assert!(first.variant_id.ends_with("FIRST_ATTEMPT"));
            assert!(restart.variant_id.ends_with("RESTART"));
            assert_outcome(
                restart,
                "MODEL_EXACT_HISTORICAL_READ_ELIGIBLE",
                "STREAM_EXACT",
                "NONE",
            );
            assert_eq!(restart.adapter_pre_state.as_str(), "FRESH");
            assert_eq!(restart.adapter_post_state.as_str(), "COMPLETED");
            assert_eq!(restart.external_durability_observation_count, 0);
        }
        // Only data-step interruption is exercised through the test-only
        // ModelTransport. The other cut positions remain explicitly modeled.
        for data_steps in 0..=DATA_STEP_COUNT {
            let adapter = BoundedRuntimeRecoveredEnvelopeAdapterV1::new(
                ModelTransport::crash_after_data_steps(&lookup, &record, data_steps),
            );
            let mut sink = BoundedRecoveredSourceRecordV1::new();
            assert!(adapter.read_exact(&lookup, &mut sink).is_err());
            assert_eq!(adapter.state.get(), AdapterStateV1::TerminalFailed);
            let fresh = direct_exact_read(&record, &lookup);
            assert_eq!(fresh.state.get(), AdapterStateV1::Completed);
        }
    }

    #[test]
    fn s16_object_present_receipt_absent_is_pending_without_open() {
        let rows = catalog();
        let row = family(&rows, "D06_OBJECT_PRESENT_RECEIPT_ABSENT")[0];
        assert_eq!(row.object_persistence.as_str(), "COMMITTED");
        assert_eq!(row.receipt_state, "ABSENT");
        assert_outcome(
            row,
            "MODEL_INCOMPLETE_FAIL_CLOSED",
            "NOT_INVOKED",
            "PENDING",
        );
    }

    #[test]
    fn s16_receipt_present_object_absent_is_integrity_conflict() {
        let rows = catalog();
        let row = family(&rows, "D07_RECEIPT_PRESENT_OBJECT_ABSENT")[0];
        assert_eq!(row.object_persistence.as_str(), "ABSENT");
        assert_eq!(row.receipt_state, "COMMITTED");
        assert_outcome(
            row,
            "MODEL_INTEGRITY_INCIDENT_QUARANTINED",
            "NOT_INVOKED",
            "CONFLICT",
        );
    }

    #[test]
    fn s16_each_receipt_object_binding_mismatch_is_integrity_conflict() {
        let rows = catalog();
        let family = family(&rows, "D08_RECEIPT_OBJECT_BINDING_MISMATCH");
        assert_eq!(family.len(), 5);
        for row in family {
            assert_eq!(row.computed_receipt_sha256, row.stored_receipt_sha256);
            assert_outcome(
                row,
                "MODEL_INTEGRITY_INCIDENT_QUARANTINED",
                "NOT_INVOKED",
                "CONFLICT",
            );
        }
    }

    #[test]
    fn s16_old_generation_snapshot_is_rollback_without_generation_ordering() {
        let record = fixture_record();
        let rows = catalog();
        let row = family(&rows, "D09_OLD_GENERATION_SNAPSHOT")[0];
        assert_eq!(row.reason, "WITNESS_HEAD_GENERATION_MISMATCH");
        assert_ne!(
            row.computed_receipt_sha256,
            base_commitments_v1(&record).unwrap().receipt
        );
        assert_outcome(
            row,
            "MODEL_INTEGRITY_INCIDENT_QUARANTINED",
            "NOT_INVOKED",
            "ROLLBACK",
        );
        assert_ne!([0x80; 32], [0x82; 32]);

        let base = base_commitments_v1(&record).unwrap();
        let conflicting_receipt = receipt_for_v1(
            [0x80; 32],
            [0x83; 32],
            17,
            CANONICAL_RECORD_LEN as u64,
            xor_digest_byte(CANONICAL_RECORD_SHA256, 0),
            [0x91; 32],
        );
        let conflicting_receipt_sha256 = computed_receipt_sha256_v1(&conflicting_receipt);
        let mut binding_collision = base_triple_state_v1(&record);
        binding_collision.receipt = ModeledReceiptSlotV1::Committed(conflicting_receipt);
        binding_collision.selected_view = Some(view_for_v1(
            [0x96; 32],
            ModeledReplicaAuthorityV1::ClaimsAuthoritative,
            [0x80; 32],
            [0x83; 32],
            17,
            CANONICAL_RECORD_LEN as u64,
            xor_digest_byte(CANONICAL_RECORD_SHA256, 0),
            conflicting_receipt_sha256,
        ));
        let binding_evaluation = evaluate_raw_modeled_state_v1(
            &record,
            &binding_collision,
            &volatile_state_v1(ModeledPublisherPhaseV1::WitnessCommitted),
            &base,
        );
        assert_eq!(binding_evaluation.reason, "RECEIPT_RECORD_HASH_MISMATCH");
        assert_eq!(binding_evaluation.mapped_s15_failure.as_str(), "CONFLICT");

        let old_receipt = receipt_for_v1(
            [0x80; 32],
            [0x83; 32],
            17,
            CANONICAL_RECORD_LEN as u64,
            CANONICAL_RECORD_SHA256,
            [0x91; 32],
        );
        let old_receipt_sha256 = computed_receipt_sha256_v1(&old_receipt);
        let mut noncanonical_witness = canonical_witness_v1(base.receipt);
        noncanonical_witness.witness_sequence = 32;
        noncanonical_witness.stored_witness_sha256 =
            computed_witness_sha256_v1(&noncanonical_witness);
        let mut witness_collision = base_triple_state_v1(&record);
        witness_collision.receipt = ModeledReceiptSlotV1::Committed(old_receipt);
        witness_collision.witness = ModeledWitnessSlotV1::Present(noncanonical_witness);
        witness_collision.selected_view = Some(view_for_v1(
            [0x96; 32],
            ModeledReplicaAuthorityV1::ClaimsAuthoritative,
            [0x80; 32],
            [0x83; 32],
            17,
            CANONICAL_RECORD_LEN as u64,
            CANONICAL_RECORD_SHA256,
            old_receipt_sha256,
        ));
        let witness_evaluation = evaluate_raw_modeled_state_v1(
            &record,
            &witness_collision,
            &volatile_state_v1(ModeledPublisherPhaseV1::WitnessCommitted),
            &base,
        );
        assert_eq!(
            witness_evaluation.reason,
            "RECEIPT_SOURCE_GENERATION_MISMATCH"
        );
        assert_eq!(witness_evaluation.mapped_s15_failure.as_str(), "CONFLICT");
    }

    #[test]
    fn s16_same_generation_lower_revision_is_rollback() {
        let rows = catalog();
        let row = family(&rows, "D10_SAME_GENERATION_LOWER_REVISION")[0];
        assert_eq!(row.reason, "WITNESS_HEAD_REVISION_ROLLBACK");
        assert_outcome(
            row,
            "MODEL_INTEGRITY_INCIDENT_QUARANTINED",
            "NOT_INVOKED",
            "ROLLBACK",
        );
        assert!(16u64 < 17u64);
    }

    #[test]
    fn s16_same_revision_divergent_head_is_equivocation_conflict() {
        let record = fixture_record();
        let rows = catalog();
        let base = base_commitments_v1(&record).unwrap();
        let family = family(&rows, "D11_SAME_REVISION_EQUIVOCATION");
        assert_eq!(family.len(), 2);
        for row in family {
            assert_ne!(row.competing_view_sha256, base.absent_view);
            assert_eq!(row.reason, "SAME_REVISION_EQUIVOCATION");
            assert_outcome(
                row,
                "MODEL_INTEGRITY_INCIDENT_QUARANTINED",
                "NOT_INVOKED",
                "CONFLICT",
            );
        }

        let divergent_receipt = receipt_for_v1(
            [0x82; 32],
            [0x83; 32],
            17,
            CANONICAL_RECORD_LEN as u64,
            xor_digest_byte(CANONICAL_RECORD_SHA256, 0),
            [0x91; 32],
        );
        let mut collision = base_triple_state_v1(&record);
        collision.competing_view = Some(view_for_v1(
            [0x97; 32],
            ModeledReplicaAuthorityV1::ClaimsAuthoritative,
            [0x82; 32],
            [0x83; 32],
            17,
            CANONICAL_RECORD_LEN as u64,
            xor_digest_byte(CANONICAL_RECORD_SHA256, 0),
            computed_receipt_sha256_v1(&divergent_receipt),
        ));
        match &mut collision.receipt {
            ModeledReceiptSlotV1::Committed(receipt) => {
                receipt.stored_receipt_sha256 = xor_digest_byte(base.receipt, 31);
            }
            ModeledReceiptSlotV1::Absent => panic!("base receipt state drifted"),
        }
        let collision_evaluation = evaluate_raw_modeled_state_v1(
            &record,
            &collision,
            &volatile_state_v1(ModeledPublisherPhaseV1::WitnessCommitted),
            &base,
        );
        assert_eq!(collision_evaluation.reason, "SAME_REVISION_EQUIVOCATION");
        assert_eq!(collision_evaluation.mapped_s15_failure.as_str(), "CONFLICT");
    }

    #[test]
    fn s16_selected_stale_replica_is_stale_without_replica_switch() {
        let record = fixture_record();
        let rows = catalog();
        let base = base_commitments_v1(&record).unwrap();
        let row = family(&rows, "D12_SELECTED_STALE_REPLICA")[0];
        assert_ne!(row.selected_view_sha256, base.selected_view);
        assert_eq!(row.competing_view_sha256, base.absent_view);
        assert_outcome(
            row,
            "MODEL_INTEGRITY_INCIDENT_QUARANTINED",
            "NOT_INVOKED",
            "STALE",
        );

        let mut unbound_authoritative = base_triple_state_v1(&record);
        unbound_authoritative.selected_view = Some(view_for_v1(
            [0x96; 32],
            ModeledReplicaAuthorityV1::ClaimsAuthoritative,
            [0x80; 32],
            [0x83; 32],
            16,
            CANONICAL_RECORD_LEN as u64,
            CANONICAL_RECORD_SHA256,
            base.receipt,
        ));
        let evaluation = evaluate_raw_modeled_state_v1(
            &record,
            &unbound_authoritative,
            &volatile_state_v1(ModeledPublisherPhaseV1::WitnessCommitted),
            &base,
        );
        assert_eq!(evaluation.reason, "UNCLASSIFIED_MODELED_STATE");
        assert_eq!(
            evaluation.disposition.as_str(),
            "MODEL_AMBIGUOUS_QUARANTINED"
        );
        assert_eq!(evaluation.mapped_s15_failure.as_str(), "INDETERMINATE");
    }

    #[test]
    fn s16_divergent_authoritative_views_are_split_brain_conflict() {
        let record = fixture_record();
        let rows = catalog();
        let base = base_commitments_v1(&record).unwrap();
        let family = family(&rows, "D13_DIVERGENT_AUTHORITATIVE_VIEWS");
        assert_eq!(family.len(), 3);
        for row in family {
            assert_ne!(row.competing_view_sha256, base.absent_view);
            assert_eq!(row.reason, "DIVERGENT_AUTHORITATIVE_VIEWS");
            assert_outcome(
                row,
                "MODEL_INTEGRITY_INCIDENT_QUARANTINED",
                "NOT_INVOKED",
                "CONFLICT",
            );
        }

        let mut unknown = base_triple_state_v1(&record);
        unknown.competing_view = Some(view_for_v1(
            [0x97; 32],
            ModeledReplicaAuthorityV1::NonAuthoritativeStale,
            [0xa2; 32],
            [0x83; 32],
            18,
            CANONICAL_RECORD_LEN as u64,
            xor_digest_byte(CANONICAL_RECORD_SHA256, 16),
            [0xa4; 32],
        ));
        let unknown_evaluation = evaluate_raw_modeled_state_v1(
            &record,
            &unknown,
            &volatile_state_v1(ModeledPublisherPhaseV1::WitnessCommitted),
            &base,
        );
        assert_eq!(
            unknown_evaluation.disposition.as_str(),
            "MODEL_AMBIGUOUS_QUARANTINED"
        );
        assert_eq!(unknown_evaluation.reason, "UNCLASSIFIED_MODELED_STATE");
        assert_eq!(
            unknown_evaluation.mapped_s15_failure.as_str(),
            "INDETERMINATE"
        );
    }

    #[test]
    fn s16_witness_missing_unavailable_corrupt_and_forked_map_exactly() {
        let rows = catalog();
        let base = base_commitments_v1(&fixture_record()).unwrap();
        let family = family(&rows, "D14_WITNESS_FAILURES");
        assert_eq!(family.len(), 4);
        assert_eq!(family[0].witness_state, "ABSENT");
        assert_outcome(
            family[0],
            "MODEL_INCOMPLETE_FAIL_CLOSED",
            "NOT_INVOKED",
            "PENDING",
        );
        assert_eq!(family[1].witness_state, "UNAVAILABLE");
        assert_outcome(
            family[1],
            "MODEL_INCOMPLETE_FAIL_CLOSED",
            "NOT_INVOKED",
            "UNAVAILABLE",
        );
        assert_eq!(family[2].computed_witness_sha256, base.witness);
        assert_ne!(family[2].stored_witness_sha256, base.witness);
        assert_eq!(family[2].mapped_s15_failure.as_str(), "MALFORMED");
        assert_eq!(family[3].witness_state, "FORKED");
        assert_ne!(family[3].stored_witness_sha256, base.witness);
        assert_eq!(family[3].mapped_s15_failure.as_str(), "CONFLICT");
    }

    #[test]
    fn s16_post_persistence_object_receipt_and_witness_corruption_is_malformed() {
        let rows = catalog();
        let base = base_commitments_v1(&fixture_record()).unwrap();
        let family = family(&rows, "D15_POST_PERSISTENCE_CORRUPTION");
        assert_eq!(family.len(), 9);
        for (index, row) in family.into_iter().enumerate() {
            assert_outcome(
                row,
                "MODEL_INTEGRITY_INCIDENT_QUARANTINED",
                "NOT_INVOKED",
                "MALFORMED",
            );
            match index / 3 {
                0 => assert_ne!(row.observed_object_sha256, base.object),
                1 => assert_ne!(row.stored_receipt_sha256, base.receipt),
                _ => assert_ne!(row.stored_witness_sha256, base.witness),
            }
        }
    }

    #[test]
    fn s16_all_rows_are_simulated_with_zero_external_evidence_and_no_side_effects() {
        for row in catalog() {
            assert_eq!(row.external_durability_observation_count, 0);
            assert_eq!(row.provider_durability_observation_count, 0);
            assert_eq!(row.owned_lab_durability_observation_count, 0);
            assert_eq!(row.side_effect.as_str(), "NONE");
            assert!(!row_message_v1(&row).is_empty());
            assert_ne!(row.mapped_s15_failure.as_str(), "UNAUTHENTICATED");
        }

        let record = fixture_record();
        let base = base_commitments_v1(&record).unwrap();
        let mut observed_boundary = volatile_state_v1(ModeledPublisherPhaseV1::Acked);
        observed_boundary.ack = observed_ack_v1(&base);
        observed_boundary.adapter_post_phase = ModeledAdapterPhaseV1::Completed;
        observed_boundary.external_durability_observation_count = 1;
        observed_boundary.side_effect = ModeledSideEffectV1::Observed;
        let evaluation = evaluate_raw_modeled_state_v1(
            &record,
            &base_triple_state_v1(&record),
            &observed_boundary,
            &base,
        );
        assert_eq!(
            evaluation.disposition.as_str(),
            "MODEL_AMBIGUOUS_QUARANTINED"
        );
        assert_eq!(evaluation.mapped_s15_failure.as_str(), "INDETERMINATE");

        let assert_unknown_lifecycle = |volatile| {
            let evaluation = evaluate_raw_modeled_state_v1(
                &record,
                &base_triple_state_v1(&record),
                &volatile,
                &base,
            );
            assert_eq!(evaluation.reason, "UNCLASSIFIED_MODELED_STATE");
            assert_eq!(
                evaluation.disposition.as_str(),
                "MODEL_AMBIGUOUS_QUARANTINED"
            );
            assert_eq!(evaluation.mapped_s15_failure.as_str(), "INDETERMINATE");
        };

        let mut invalid_d00 = volatile_state_v1(ModeledPublisherPhaseV1::Acked);
        invalid_d00.ack = observed_ack_v1(&base);
        invalid_d00.adapter_post_phase = ModeledAdapterPhaseV1::Completed;
        invalid_d00.crash_cut_index = 1;
        assert_unknown_lifecycle(invalid_d00);

        let mut invalid_d03 = volatile_state_v1(ModeledPublisherPhaseV1::WitnessCommitted);
        invalid_d03.adapter_post_phase = ModeledAdapterPhaseV1::Completed;
        invalid_d03.observed_data_steps = 1;
        invalid_d03.observed_len = DATA_STEP_BYTES as u64;
        assert_unknown_lifecycle(invalid_d03);

        let mut invalid_d04 = volatile_state_v1(ModeledPublisherPhaseV1::Empty);
        invalid_d04.crash_cut = ModeledCrashCutV1::PublishAfterWitnessCommit;
        invalid_d04.restarted_after_crash = true;
        invalid_d04.adapter_post_phase = ModeledAdapterPhaseV1::Completed;
        assert_unknown_lifecycle(invalid_d04);

        let mut invalid_d05 = volatile_state_v1(ModeledPublisherPhaseV1::Acked);
        invalid_d05.crash_cut = ModeledCrashCutV1::ReadAfterData;
        invalid_d05.crash_cut_index = 1;
        invalid_d05.adapter_phase = ModeledAdapterPhaseV1::Streaming;
        invalid_d05.adapter_post_phase = ModeledAdapterPhaseV1::TerminalFailed;
        invalid_d05.observed_data_steps = DATA_STEP_COUNT as u64;
        invalid_d05.observed_len = 0;
        assert_unknown_lifecycle(invalid_d05);

        let mut object_at_witness_cut =
            volatile_state_v1(ModeledPublisherPhaseV1::WitnessCommitted);
        object_at_witness_cut.crash_cut = ModeledCrashCutV1::PublishAfterWitnessCommit;
        object_at_witness_cut.restarted_after_crash = true;
        object_at_witness_cut.adapter_post_phase = ModeledAdapterPhaseV1::Completed;
        let object_evaluation = evaluate_raw_modeled_state_v1(
            &record,
            &object_only_state_v1(&record),
            &object_at_witness_cut,
            &base,
        );
        assert_eq!(object_evaluation.reason, "UNCLASSIFIED_MODELED_STATE");
        assert_eq!(
            object_evaluation.mapped_s15_failure.as_str(),
            "INDETERMINATE"
        );

        let mut receipt_at_ack_cut = volatile_state_v1(ModeledPublisherPhaseV1::Acked);
        receipt_at_ack_cut.crash_cut = ModeledCrashCutV1::PublishAfterAck;
        receipt_at_ack_cut.restarted_after_crash = true;
        receipt_at_ack_cut.adapter_post_phase = ModeledAdapterPhaseV1::Completed;
        let receipt_evaluation = evaluate_raw_modeled_state_v1(
            &record,
            &object_receipt_state_v1(&record),
            &receipt_at_ack_cut,
            &base,
        );
        assert_eq!(receipt_evaluation.reason, "UNCLASSIFIED_MODELED_STATE");
        assert_eq!(
            receipt_evaluation.mapped_s15_failure.as_str(),
            "INDETERMINATE"
        );
    }

    #[test]
    fn s16_private_surface_has_no_production_transport_persistence_runtime_or_admission_wiring() {
        let durable = ModeledDurableStateV1 {
            object: ModeledObjectSlotV1 {
                persistence: ModeledObjectPersistenceV1::Absent,
                bytes: Box::new([]),
            },
            receipt: ModeledReceiptSlotV1::Absent,
            witness: ModeledWitnessSlotV1::Absent,
            selected_view: None,
            competing_view: None,
        };
        let volatile = volatile_state_v1(ModeledPublisherPhaseV1::Empty);
        assert!(format!("{durable:?}").contains("SYNTHETIC_DURABLE_STATE_REDACTED"));
        assert!(format!("{volatile:?}").contains("SYNTHETIC_VOLATILE_STATE_REDACTED"));
        assert_eq!(ROW_COUNT, 5_639);
        assert_eq!(
            POLICY_ID,
            "agent-bridge/track-b/recovered-envelope-durability-fault-model/v1"
        );
    }
}
