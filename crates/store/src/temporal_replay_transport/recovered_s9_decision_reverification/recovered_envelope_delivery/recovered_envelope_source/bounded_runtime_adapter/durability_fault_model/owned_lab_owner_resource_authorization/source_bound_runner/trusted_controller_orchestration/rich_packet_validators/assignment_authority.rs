//! Owner-bound S20B assignment and concrete-operation validation.
//!
//! This module deliberately has no live executor.  It turns an
//! owner-authenticated, authorized-unclaimed subject plus the frozen 60-record
//! schedule into private evidence tokens.  Labels supplied by a run request
//! are never lookup keys.

#![cfg_attr(not(test), allow(dead_code))]

use super::*;
use serde_json::{json, Value};
use std::collections::BTreeSet;

const ASSIGNMENT_RECORD_DOMAIN_V2: &[u8] =
    b"agent-bridge/biocortex/owned-lab/s20b/authorized-assignment-record/v2";
const ASSIGNMENT_SET_DOMAIN_V2: &[u8] =
    b"agent-bridge/biocortex/owned-lab/s20b/authorized-assignment-set/v2";
const ASSIGNMENT_RECORD_SET_DOMAIN_V2: &[u8] =
    b"agent-bridge/biocortex/owned-lab/s20b/authorized-assignment-record-set/v2";
const ASSIGNMENT_ID_DOMAIN_V2: &[u8] =
    b"agent-bridge/biocortex/owned-lab/s20b/authorized-assignment-id/v2";
const SCHEDULE_DOMAIN_V2: &[u8] = b"agent-bridge/biocortex/owned-lab/s20b/authorized-schedule/v2";
const OPERATION_DOMAIN_V2: &[u8] = b"agent-bridge/biocortex/owned-lab/s20b/concrete-operation/v2";
const OPERATION_OPERANDS_DOMAIN_V2: &[u8] =
    b"agent-bridge/biocortex/owned-lab/s20b/concrete-operation-operands/v2";
const OPERATION_SET_DOMAIN_V2: &[u8] =
    b"agent-bridge/biocortex/owned-lab/s20b/concrete-operation-set/v2";
const GLOBAL_OPERATION_SET_DOMAIN_V2: &[u8] =
    b"agent-bridge/biocortex/owned-lab/s20b/global-concrete-operation-set/v2";
const ASSIGNMENT_SET_SHA256_KAT_V2: &str =
    "b3a7025a488e9aefc6724869f75ab76a482002224bee90c075e9379101ee7264";
const SCHEDULE_SHA256_KAT_V2: &str =
    "8c0129d150d918523c122dbf3afb4e7c6abb3ce7ca957204252c115a7f1def15";
const ASSIGNMENT_RECORD_SET_SHA256_KAT_V2: &str =
    "7a927eba7eb691990b32c7987bea5c0fdce15c51d37792f8ca45c3bddb556bc6";
const GLOBAL_OPERATION_SET_SHA256_KAT_V2: &str =
    "a00feb5745c83fc20d5ad84f66877289c9108b29371697ceb8cf13e3fb142db0";
const FIRST_ASSIGNMENT_RECORD_SHA256_KAT_V2: &str =
    "b9e38d17c7d6974b7fb49e0840bf2e431f60dc8bc309c31b6202c3b5bcbf41fc";
const LAST_ASSIGNMENT_RECORD_SHA256_KAT_V2: &str =
    "6bd2c6e3648030d1de1a3be795a6ad221887fc8e273c9c771024d85b9866f135";
const OL00_OPERATION_SET_SHA256_KAT_V2: &str =
    "341fa260fcc7958e18891f4143fd33bcafb13efcfd6f4fd07a16058be16a654b";
const OL04_OPERATION_SET_SHA256_KAT_V2: &str =
    "e6cc4cfe754e3d3e9b0e670cfdfb38ce065e4bf2ec157c092ae8bf75da586e94";

const EXACT_ALLOWED_OPERATIONS: [&str; 8] = [
    "CREATE_EXACT_RUN_ROOT",
    "SQLITE_EXACT_PROFILE_SETUP",
    "SPAWN_ONE_ASSIGNED_CHILD",
    "PIDFD_OPEN_ASSIGNED_CHILD",
    "PIDFD_SEND_SIGNAL_SIGKILL",
    "FRESH_EXEC_REOPEN",
    "WRITE_BOUND_RECEIPTS",
    "CLEANUP_EXACT_RUN_ROOT",
];

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
enum OperationScopeV1 {
    RunRoot,
    StateDatabase,
    InitialChild,
    PidfdInitialChild,
    FreshExecChild,
    EvidenceDirectory,
}

impl OperationScopeV1 {
    fn schema_scope(self) -> &'static str {
        match self {
            Self::RunRoot | Self::StateDatabase => "RUN",
            Self::InitialChild
            | Self::PidfdInitialChild
            | Self::FreshExecChild
            | Self::EvidenceDirectory => "ASSIGNMENT",
        }
    }
}

#[derive(Clone, Debug, Eq, PartialEq)]
struct ConcreteOperationV1 {
    sequence: u64,
    operation_id: &'static str,
    scope: OperationScopeV1,
    operands: Vec<(&'static str, OperationOperandValueV1)>,
    assignment_id_sha256: Option<[u8; 32]>,
    operands_sha256: [u8; 32],
    descriptor_sha256: [u8; 32],
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
enum OperationOperandValueV1 {
    Boolean(bool),
    Unsigned(u64),
    OctalMode(&'static str),
    RelativePath(&'static str),
    Symbol(&'static str),
}

impl OperationOperandValueV1 {
    fn typed_json_v1(self) -> (&'static str, Value) {
        match self {
            Self::Boolean(value) => ("BOOLEAN", Value::Bool(value)),
            Self::Unsigned(value) => ("UNSIGNED_INTEGER", Value::Number(value.into())),
            Self::OctalMode(value) => ("OCTAL_MODE", Value::String(value.into())),
            Self::RelativePath(value) => ("RELATIVE_PATH", Value::String(value.into())),
            Self::Symbol(value) => ("SYMBOL", Value::String(value.into())),
        }
    }
}

fn operation_operands_value_v1(operands: &[(&str, OperationOperandValueV1)]) -> Value {
    Value::Array(
        operands
            .iter()
            .map(|(name, value)| {
                let (value_type, value) = value.typed_json_v1();
                json!({
                    "name": name,
                    "type": value_type,
                    "value": value
                })
            })
            .collect(),
    )
}

fn operation_descriptor_value_v1(
    sequence: u64,
    operation_id: &str,
    schema_scope: &str,
    assignment_id_sha256: Option<[u8; 32]>,
    operands_sha256: [u8; 32],
) -> Value {
    json!({
        "assignment_id_sha256": assignment_id_sha256.map(|value| hex32(&value)),
        "operands_sha256": hex32(&operands_sha256),
        "operation_id": operation_id,
        "operation_sequence": sequence,
        "scope": schema_scope
    })
}

fn concrete_operation_v1(
    sequence: u64,
    operation_id: &'static str,
    scope: OperationScopeV1,
    operands: Vec<(&'static str, OperationOperandValueV1)>,
    assignment_id_sha256: [u8; 32],
) -> AuthorizationResult<ConcreteOperationV1> {
    let assignment_id_sha256 = match scope.schema_scope() {
        "RUN" => None,
        "ASSIGNMENT" => Some(assignment_id_sha256),
        _ => {
            return Err(s20b_error(
                "s20b_operation_scope",
                "operation did not project to one closed schema scope",
            ))
        }
    };
    let operands_sha256 = framed_digest(
        OPERATION_OPERANDS_DOMAIN_V2,
        &[&restricted_canonical_bytes(&operation_operands_value_v1(
            &operands,
        ))?],
    )?;
    let descriptor_sha256 = framed_digest(
        OPERATION_DOMAIN_V2,
        &[&restricted_canonical_bytes(
            &operation_descriptor_value_v1(
                sequence,
                operation_id,
                scope.schema_scope(),
                assignment_id_sha256,
                operands_sha256,
            ),
        )?],
    )?;
    Ok(ConcreteOperationV1 {
        sequence,
        operation_id,
        scope,
        operands,
        assignment_id_sha256,
        operands_sha256,
        descriptor_sha256,
    })
}

fn operations_for_family_v1(
    family_id: &str,
    assignment_id_sha256: [u8; 32],
) -> AuthorizationResult<Vec<ConcreteOperationV1>> {
    let crash = family_id != "OL00";
    let mut operations = vec![
        concrete_operation_v1(
            1,
            EXACT_ALLOWED_OPERATIONS[0],
            OperationScopeV1::RunRoot,
            vec![
                (
                    "creation",
                    OperationOperandValueV1::Symbol("CREATE_NEW_ONLY"),
                ),
                ("mode", OperationOperandValueV1::OctalMode("0700")),
                (
                    "preexisting_allowed",
                    OperationOperandValueV1::Boolean(false),
                ),
            ],
            assignment_id_sha256,
        )?,
        concrete_operation_v1(
            2,
            EXACT_ALLOWED_OPERATIONS[1],
            OperationScopeV1::StateDatabase,
            vec![
                (
                    "relative_path",
                    OperationOperandValueV1::RelativePath("state.sqlite3"),
                ),
                ("journal_mode", OperationOperandValueV1::Symbol("DELETE")),
                ("synchronous", OperationOperandValueV1::Symbol("EXTRA")),
                ("mmap_size", OperationOperandValueV1::Unsigned(0)),
            ],
            assignment_id_sha256,
        )?,
        concrete_operation_v1(
            3,
            EXACT_ALLOWED_OPERATIONS[2],
            OperationScopeV1::InitialChild,
            vec![
                ("child_count", OperationOperandValueV1::Unsigned(1)),
                (
                    "descendants_allowed",
                    OperationOperandValueV1::Boolean(false),
                ),
                (
                    "exec_image",
                    OperationOperandValueV1::Symbol("FROZEN_RUNNER_BINARY"),
                ),
            ],
            assignment_id_sha256,
        )?,
    ];
    if crash {
        operations.extend([
            concrete_operation_v1(
                4,
                EXACT_ALLOWED_OPERATIONS[3],
                OperationScopeV1::PidfdInitialChild,
                vec![
                    (
                        "numeric_pid_fallback",
                        OperationOperandValueV1::Boolean(false),
                    ),
                    (
                        "pid_start_recheck",
                        OperationOperandValueV1::Symbol("required"),
                    ),
                ],
                assignment_id_sha256,
            )?,
            concrete_operation_v1(
                5,
                EXACT_ALLOWED_OPERATIONS[4],
                OperationScopeV1::PidfdInitialChild,
                vec![
                    ("signal", OperationOperandValueV1::Symbol("SIGKILL")),
                    ("sender", OperationOperandValueV1::Symbol("CONTROLLER_ONLY")),
                ],
                assignment_id_sha256,
            )?,
            concrete_operation_v1(
                6,
                EXACT_ALLOWED_OPERATIONS[5],
                OperationScopeV1::FreshExecChild,
                vec![
                    ("same_boot", OperationOperandValueV1::Symbol("required")),
                    (
                        "distinct_pid_start_nonce",
                        OperationOperandValueV1::Symbol("required"),
                    ),
                    (
                        "resume_old_process",
                        OperationOperandValueV1::Boolean(false),
                    ),
                ],
                assignment_id_sha256,
            )?,
        ]);
    }
    let next = operations.len() as u64 + 1;
    operations.push(concrete_operation_v1(
        next,
        EXACT_ALLOWED_OPERATIONS[6],
        OperationScopeV1::EvidenceDirectory,
        vec![
            (
                "canonical_receipts",
                OperationOperandValueV1::Symbol("required"),
            ),
            (
                "parent_chain",
                OperationOperandValueV1::Symbol("backward_only"),
            ),
        ],
        assignment_id_sha256,
    )?);
    operations.push(concrete_operation_v1(
        next + 1,
        EXACT_ALLOWED_OPERATIONS[7],
        OperationScopeV1::RunRoot,
        vec![
            (
                "scope",
                OperationOperandValueV1::Symbol("EXACT_RUN_ROOT_ONLY"),
            ),
            (
                "parent_or_sibling_delete",
                OperationOperandValueV1::Boolean(false),
            ),
        ],
        assignment_id_sha256,
    )?);
    for (index, operation) in operations.iter().enumerate() {
        if operation.sequence != index as u64 + 1
            || !EXACT_ALLOWED_OPERATIONS.contains(&operation.operation_id)
        {
            return Err(s20b_error(
                "s20b_operation_order",
                "concrete operation sequence or identifier drifted",
            ));
        }
    }
    Ok(operations)
}

fn operation_set_digest_v1(operations: &[ConcreteOperationV1]) -> AuthorizationResult<[u8; 32]> {
    let fields: Vec<&[u8]> = operations
        .iter()
        .map(|operation| &operation.descriptor_sha256[..])
        .collect();
    framed_digest(OPERATION_SET_DOMAIN_V2, &fields)
}

#[derive(Clone, Debug)]
struct AssignmentRecordV1 {
    ordinal: u64,
    assignment_id_sha256: [u8; 32],
    family_id: String,
    case_id: String,
    variant_id: String,
    phase_count: u64,
    operations: Vec<ConcreteOperationV1>,
    operation_set_sha256: [u8; 32],
    assignment_record_sha256: [u8; 32],
}

fn assignment_record_v1(
    ordinal: u64,
    family_id: String,
    case_id: String,
    variant_id: String,
    phase_count: u64,
) -> AuthorizationResult<AssignmentRecordV1> {
    let assignment_id_sha256 = framed_digest(
        ASSIGNMENT_ID_DOMAIN_V2,
        &[
            &ordinal.to_be_bytes(),
            family_id.as_bytes(),
            case_id.as_bytes(),
            variant_id.as_bytes(),
            &phase_count.to_be_bytes(),
        ],
    )?;
    let operations = operations_for_family_v1(&family_id, assignment_id_sha256)?;
    let operation_set_sha256 = operation_set_digest_v1(&operations)?;
    let assignment_record_sha256 = framed_digest(
        ASSIGNMENT_RECORD_DOMAIN_V2,
        &[
            &ordinal.to_be_bytes(),
            family_id.as_bytes(),
            case_id.as_bytes(),
            variant_id.as_bytes(),
            &phase_count.to_be_bytes(),
            &operation_set_sha256,
        ],
    )?;
    Ok(AssignmentRecordV1 {
        ordinal,
        assignment_id_sha256,
        family_id,
        case_id,
        variant_id,
        phase_count,
        operations,
        operation_set_sha256,
        assignment_record_sha256,
    })
}

fn build_frozen_assignment_records_v1() -> AuthorizationResult<Vec<AssignmentRecordV1>> {
    let mut records = vec![assignment_record_v1(
        1,
        "OL00".into(),
        "D00_CLEAN_COMMITTED_HEAD".into(),
        "CLEAN_CONTROL_NO_CRASH".into(),
        1,
    )?];
    for variant in [
        "CRASH_AT_EMPTY_RESTART",
        "CRASH_AFTER_OBJECT_PREFIX_RESTART",
        "CRASH_AFTER_OBJECT_COMMIT_RESTART",
        "CRASH_AFTER_RECEIPT_COMMIT_RESTART",
        "CRASH_AFTER_WITNESS_COMMIT_RESTART",
        "CRASH_AFTER_ACK_RESTART",
    ] {
        records.push(assignment_record_v1(
            records.len() as u64 + 1,
            "OL04".into(),
            "D04_PUBLISH_CRASH_RESTART_CUTS".into(),
            variant.into(),
            1,
        )?);
    }
    for cut in 0..53_u64 {
        let variant = match cut {
            0 => "BEFORE_OPEN".into(),
            1 => "AFTER_OPEN".into(),
            2..=50 => format!("AFTER_DATA_{:04}", cut - 1),
            51 => "AFTER_COMPLETE_BEFORE_S14".into(),
            _ => "AFTER_HISTORICAL".into(),
        };
        records.push(assignment_record_v1(
            records.len() as u64 + 1,
            "OL05".into(),
            "D05_S15_READ_CRASH_RESTART_CUTS".into(),
            variant,
            2,
        )?);
    }
    let ordinal_set: BTreeSet<u64> = records.iter().map(|record| record.ordinal).collect();
    let digest_set: BTreeSet<[u8; 32]> = records
        .iter()
        .map(|record| record.assignment_record_sha256)
        .collect();
    let family_count = |family: &str| {
        records
            .iter()
            .filter(|record| record.family_id == family)
            .count()
    };
    let operation_ids: BTreeSet<&str> = records
        .iter()
        .flat_map(|record| {
            record
                .operations
                .iter()
                .map(|operation| operation.operation_id)
        })
        .collect();
    let expected_operation_ids: BTreeSet<&str> = EXACT_ALLOWED_OPERATIONS.into_iter().collect();
    if records.len() != 60
        || ordinal_set != (1..=60).collect()
        || digest_set.len() != 60
        || family_count("OL00") != 1
        || family_count("OL04") != 6
        || family_count("OL05") != 53
        || records.iter().map(|record| record.phase_count).sum::<u64>() != 113
        || operation_ids != expected_operation_ids
    {
        return Err(s20b_error(
            "s20b_assignment_catalog",
            "frozen assignment count, ordinal, family, operation, digest, or phase total drifted",
        ));
    }
    Ok(records)
}

fn assignment_set_roots_v1(
    records: &[AssignmentRecordV1],
) -> AuthorizationResult<([u8; 32], [u8; 32], [u8; 32], [u8; 32])> {
    let record_fields: Vec<&[u8]> = records
        .iter()
        .map(|record| &record.assignment_record_sha256[..])
        .collect();
    let schedule_sha256 = framed_digest(SCHEDULE_DOMAIN_V2, &record_fields)?;
    let assignment_record_set_sha256 =
        framed_digest(ASSIGNMENT_RECORD_SET_DOMAIN_V2, &record_fields)?;
    let operation_fields: Vec<&[u8]> = records
        .iter()
        .map(|record| &record.operation_set_sha256[..])
        .collect();
    let operation_descriptor_set_sha256 =
        framed_digest(GLOBAL_OPERATION_SET_DOMAIN_V2, &operation_fields)?;
    let assignment_set_sha256 = framed_digest(
        ASSIGNMENT_SET_DOMAIN_V2,
        &[
            &schedule_sha256,
            &assignment_record_set_sha256,
            &operation_descriptor_set_sha256,
            &60_u64.to_be_bytes(),
            &113_u64.to_be_bytes(),
        ],
    )?;
    Ok((
        assignment_set_sha256,
        schedule_sha256,
        assignment_record_set_sha256,
        operation_descriptor_set_sha256,
    ))
}

fn roots_match_frozen_kats_v2(
    assignment_set_sha256: &[u8; 32],
    schedule_sha256: &[u8; 32],
    assignment_record_set_sha256: &[u8; 32],
    operation_descriptor_set_sha256: &[u8; 32],
) -> bool {
    hex32(assignment_set_sha256) == ASSIGNMENT_SET_SHA256_KAT_V2
        && hex32(schedule_sha256) == SCHEDULE_SHA256_KAT_V2
        && hex32(assignment_record_set_sha256) == ASSIGNMENT_RECORD_SET_SHA256_KAT_V2
        && hex32(operation_descriptor_set_sha256) == GLOBAL_OPERATION_SET_SHA256_KAT_V2
}

fn boundary_records_match_frozen_kats_v2(records: &[AssignmentRecordV1]) -> bool {
    records.len() == 60
        && hex32(&records[0].assignment_record_sha256) == FIRST_ASSIGNMENT_RECORD_SHA256_KAT_V2
        && hex32(&records[59].assignment_record_sha256) == LAST_ASSIGNMENT_RECORD_SHA256_KAT_V2
        && hex32(&records[0].operation_set_sha256) == OL00_OPERATION_SET_SHA256_KAT_V2
        && hex32(&records[1].operation_set_sha256) == OL04_OPERATION_SET_SHA256_KAT_V2
}

/// A mechanically validated future-owner assignment set.  Existing S19
/// synthetic placeholder commitments intentionally cannot construct it.
#[must_use]
pub(super) struct ValidatedAuthorizedAssignmentSetV1 {
    records: Vec<AssignmentRecordV1>,
    pub(super) authorization_id_sha256: [u8; 32],
    pub(super) owner_envelope_sha256: [u8; 32],
    pub(super) subject_manifest_sha256: [u8; 32],
    pub(super) resource_scope_sha256: [u8; 32],
    pub(super) capability_nonce_sha256: [u8; 32],
    pub(super) assignment_set_sha256: [u8; 32],
    pub(super) schedule_sha256: [u8; 32],
    pub(super) assignment_record_set_sha256: [u8; 32],
    pub(super) operation_descriptor_set_sha256: [u8; 32],
}

#[must_use]
pub(super) struct ValidatedAuthorizedAssignmentMemberV1 {
    pub(super) ordinal: u64,
    pub(super) assignment_id_sha256: [u8; 32],
    pub(super) family_id: String,
    pub(super) case_id: String,
    pub(super) variant_id: String,
    pub(super) phase_count: u64,
    pub(super) operation_set_sha256: [u8; 32],
    pub(super) assignment_record_sha256: [u8; 32],
    operation_bindings: Vec<SchemaOperationBindingV1>,
}

#[derive(Clone, Debug, Eq, PartialEq)]
pub(super) struct SchemaOperationBindingV1 {
    pub(super) operation_sequence: u64,
    pub(super) operation_id: &'static str,
    pub(super) scope: &'static str,
    pub(super) assignment_id_sha256: Option<[u8; 32]>,
    pub(super) operands_sha256: [u8; 32],
    pub(super) descriptor_sha256: [u8; 32],
}

fn exact_allowed_operation_order_v1(subject: &VerifiedS19SubjectV1) -> bool {
    subject.allowed_operation_ids.len() == EXACT_ALLOWED_OPERATIONS.len()
        && subject
            .allowed_operation_ids
            .iter()
            .map(String::as_str)
            .eq(EXACT_ALLOWED_OPERATIONS)
        && subject
            .allowed_operation_ids
            .iter()
            .collect::<BTreeSet<_>>()
            .len()
            == EXACT_ALLOWED_OPERATIONS.len()
}

pub(super) fn validate_authorized_assignment_set_v1(
    authorized: &AuthorizedUnclaimedS19SubjectV1,
) -> AuthorizationResult<ValidatedAuthorizedAssignmentSetV1> {
    let subject = &authorized.subject;
    let records = build_frozen_assignment_records_v1()?;
    let (
        assignment_set_sha256,
        schedule_sha256,
        assignment_record_set_sha256,
        operation_descriptor_set_sha256,
    ) = assignment_set_roots_v1(&records)?;
    if !boundary_records_match_frozen_kats_v2(&records)
        || !roots_match_frozen_kats_v2(
            &assignment_set_sha256,
            &schedule_sha256,
            &assignment_record_set_sha256,
            &operation_descriptor_set_sha256,
        )
        || assignment_set_sha256 != subject.assignment_set_sha256
        || schedule_sha256 != subject.schedule_sha256
        || subject.catalog_row_count != 5_639
        || subject.catalog_sha256 != super::super::super::super::super::CATALOG_KAT_SHA256
        || subject.target_phase_count != 113
        || subject.target_phase_unique_match_count != 113
        || !exact_allowed_operation_order_v1(subject)
        || [
            &subject.classifier_binary_sha256,
            &subject.classifier_source_sha256,
            &subject.expected_oracle_sha256,
            &subject.s17_observation_schema_sha256,
            &subject.s17_plan_sha256,
        ]
        .iter()
        .any(|digest| !nonzero(&digest[..]))
        || authorized.authorization.revocation_epoch == 0
        || [
            &authorized.authorization.authorization_id_sha256,
            &authorized.authorization.owner_envelope_sha256,
            &authorized.authorization.payload_sha256,
            &authorized.authorization.trust_anchor_document_sha256,
            &authorized.capability_nonce_sha256,
            &authorized.revocation_policy_sha256,
        ]
        .iter()
        .any(|digest| !nonzero(&digest[..]))
    {
        return Err(s20b_error(
            "s20b_owner_assignment_binding",
            "verified subject does not bind the exact assignment, operation, catalog, and validator tuple",
        ));
    }
    Ok(ValidatedAuthorizedAssignmentSetV1 {
        records,
        authorization_id_sha256: authorized.authorization.authorization_id_sha256,
        owner_envelope_sha256: authorized.authorization.owner_envelope_sha256,
        subject_manifest_sha256: subject.canonical_manifest_sha256,
        resource_scope_sha256: subject.resource_scope_sha256,
        capability_nonce_sha256: authorized.capability_nonce_sha256,
        assignment_set_sha256,
        schedule_sha256,
        assignment_record_set_sha256,
        operation_descriptor_set_sha256,
    })
}

#[cfg(test)]
pub(super) fn frozen_assignment_roots_for_tests_v1() -> AuthorizationResult<([u8; 32], [u8; 32])> {
    let records = build_frozen_assignment_records_v1()?;
    let (assignment_set_sha256, schedule_sha256, _, _) = assignment_set_roots_v1(&records)?;
    Ok((assignment_set_sha256, schedule_sha256))
}

impl ValidatedAuthorizedAssignmentSetV1 {
    pub(super) fn matches_authorized_subject_v1(
        &self,
        authorized: &AuthorizedUnclaimedS19SubjectV1,
    ) -> bool {
        self.authorization_id_sha256 == authorized.authorization.authorization_id_sha256
            && self.owner_envelope_sha256 == authorized.authorization.owner_envelope_sha256
            && self.subject_manifest_sha256 == authorized.subject.canonical_manifest_sha256
            && self.resource_scope_sha256 == authorized.subject.resource_scope_sha256
            && self.capability_nonce_sha256 == authorized.capability_nonce_sha256
            && self.assignment_set_sha256 == authorized.subject.assignment_set_sha256
            && self.schedule_sha256 == authorized.subject.schedule_sha256
    }

    pub(super) fn member(
        &self,
        ordinal: u64,
        assignment_record_sha256: [u8; 32],
    ) -> AuthorizationResult<ValidatedAuthorizedAssignmentMemberV1> {
        let record = self
            .records
            .get(ordinal.checked_sub(1).unwrap_or(u64::MAX) as usize)
            .filter(|record| {
                record.ordinal == ordinal
                    && record.assignment_record_sha256 == assignment_record_sha256
            })
            .ok_or_else(|| {
                s20b_error(
                    "s20b_assignment_member",
                    "ordinal and owner-bound assignment record digest are not one exact member",
                )
            })?;
        Ok(ValidatedAuthorizedAssignmentMemberV1 {
            ordinal: record.ordinal,
            assignment_id_sha256: record.assignment_id_sha256,
            family_id: record.family_id.clone(),
            case_id: record.case_id.clone(),
            variant_id: record.variant_id.clone(),
            phase_count: record.phase_count,
            operation_set_sha256: record.operation_set_sha256,
            assignment_record_sha256: record.assignment_record_sha256,
            operation_bindings: record
                .operations
                .iter()
                .map(|operation| SchemaOperationBindingV1 {
                    operation_sequence: operation.sequence,
                    operation_id: operation.operation_id,
                    scope: operation.scope.schema_scope(),
                    assignment_id_sha256: operation.assignment_id_sha256,
                    operands_sha256: operation.operands_sha256,
                    descriptor_sha256: operation.descriptor_sha256,
                })
                .collect(),
        })
    }

    pub(super) fn exact_record_digests(&self) -> impl Iterator<Item = [u8; 32]> + '_ {
        self.records
            .iter()
            .map(|record| record.assignment_record_sha256)
    }
}

impl ValidatedAuthorizedAssignmentMemberV1 {
    pub(super) fn schema_operation_bindings_v1(&self) -> &[SchemaOperationBindingV1] {
        &self.operation_bindings
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn repeated(byte: u8) -> [u8; 32] {
        [byte; 32]
    }

    fn subject_for_roots(
        assignment_set_sha256: [u8; 32],
        schedule_sha256: [u8; 32],
    ) -> VerifiedS19SubjectV1 {
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
            assignment_set_sha256,
            schedule_sha256,
            catalog_row_count: 5_639,
            catalog_sha256: super::super::super::super::super::super::CATALOG_KAT_SHA256,
            classifier_binary_sha256: repeated(18),
            classifier_source_sha256: repeated(19),
            expected_oracle_sha256: repeated(20),
            s17_observation_schema_sha256: repeated(21),
            s17_plan_sha256: repeated(22),
            target_phase_count: 113,
            target_phase_unique_match_count: 113,
            allowed_operation_ids: EXACT_ALLOWED_OPERATIONS
                .iter()
                .map(|value| (*value).into())
                .collect(),
        }
    }

    fn authorized_for_roots(
        assignment_set_sha256: [u8; 32],
        schedule_sha256: [u8; 32],
    ) -> AuthorizedUnclaimedS19SubjectV1 {
        AuthorizedUnclaimedS19SubjectV1 {
            authorization: VerifiedUnclaimedOwnedLabAuthorizationV1 {
                authorization_id_sha256: repeated(23),
                payload_sha256: repeated(24),
                owner_envelope_sha256: repeated(25),
                trust_anchor_document_sha256: repeated(26),
                owner_identity_sha256: repeated(27),
                owner_key_id: "S20B_SYNTHETIC_TEST_OWNER".into(),
                owner_key_version: 1,
                revocation_epoch: 1,
            },
            subject: subject_for_roots(assignment_set_sha256, schedule_sha256),
            capability_nonce_sha256: repeated(28),
            revocation_policy_sha256: repeated(29),
        }
    }

    #[test]
    fn s20b_owner_bound_assignment_and_operation_sequence_is_exact() {
        let records = build_frozen_assignment_records_v1().unwrap();
        let (set_root, schedule_root, record_set_root, operation_set_root) =
            assignment_set_roots_v1(&records).unwrap();
        assert!(boundary_records_match_frozen_kats_v2(&records));
        assert!(roots_match_frozen_kats_v2(
            &set_root,
            &schedule_root,
            &record_set_root,
            &operation_set_root,
        ));
        let authorized = authorized_for_roots(set_root, schedule_root);
        let validated = validate_authorized_assignment_set_v1(&authorized).unwrap();
        assert_eq!(validated.exact_record_digests().count(), 60);
        assert_eq!(validated.assignment_record_set_sha256, record_set_root);
        assert_eq!(
            validated.operation_descriptor_set_sha256,
            operation_set_root
        );
        let member = validated
            .member(8, records[7].assignment_record_sha256)
            .unwrap();
        assert_eq!(member.family_id, "OL05");
        assert_eq!(member.phase_count, 2);
        assert_ne!(member.operation_set_sha256, [0; 32]);
        assert_eq!(member.schema_operation_bindings_v1().len(), 8);
        for operation in member.schema_operation_bindings_v1() {
            match operation.scope {
                "RUN" => assert_eq!(operation.assignment_id_sha256, None),
                "ASSIGNMENT" => {
                    assert_eq!(
                        operation.assignment_id_sha256,
                        Some(member.assignment_id_sha256)
                    )
                }
                _ => panic!("unexpected schema operation scope"),
            }
            assert_ne!(operation.operands_sha256, [0; 32]);
            assert_ne!(operation.descriptor_sha256, [0; 32]);
        }
    }

    #[test]
    fn s20b_assignment_digest_order_label_and_operation_substitution_reject() {
        let mut records = build_frozen_assignment_records_v1().unwrap();
        let (set_root, schedule_root, _, _) = assignment_set_roots_v1(&records).unwrap();
        let mut authorized = authorized_for_roots(set_root, schedule_root);
        authorized.subject.allowed_operation_ids.swap(0, 1);
        assert!(validate_authorized_assignment_set_v1(&authorized).is_err());
        let authorized = authorized_for_roots(set_root, schedule_root);
        let validated = validate_authorized_assignment_set_v1(&authorized).unwrap();
        let mut wrong_digest = records[1].assignment_record_sha256;
        wrong_digest[0] ^= 1;
        assert!(validated.member(2, wrong_digest).is_err());

        records[1].variant_id = "CALLER_LABEL_SUBSTITUTION".into();
        assert_ne!(
            assignment_record_v1(
                records[1].ordinal,
                records[1].family_id.clone(),
                records[1].case_id.clone(),
                records[1].variant_id.clone(),
                records[1].phase_count,
            )
            .unwrap()
            .assignment_record_sha256,
            records[1].assignment_record_sha256
        );
        records[1].operations[0].operands[0].1 = OperationOperandValueV1::Symbol("MUTATED");
        assert_ne!(
            concrete_operation_v1(
                records[1].operations[0].sequence,
                records[1].operations[0].operation_id,
                records[1].operations[0].scope,
                records[1].operations[0].operands.clone(),
                records[1].assignment_id_sha256,
            )
            .unwrap()
            .descriptor_sha256,
            records[1].operations[0].descriptor_sha256
        );
    }

    #[test]
    fn s20b_existing_s19_placeholder_assignment_is_not_authority() {
        let authorized = authorized_for_roots(repeated(0x39), repeated(0x3e));
        assert!(validate_authorized_assignment_set_v1(&authorized).is_err());
    }

    #[test]
    fn s20b_assignment_token_cannot_cross_owner_or_manifest_boundary() {
        let records = build_frozen_assignment_records_v1().unwrap();
        let (set_root, schedule_root, _, _) = assignment_set_roots_v1(&records).unwrap();
        let authorized = authorized_for_roots(set_root, schedule_root);
        let validated = validate_authorized_assignment_set_v1(&authorized).unwrap();
        assert!(validated.matches_authorized_subject_v1(&authorized));

        let mut another_owner = authorized_for_roots(set_root, schedule_root);
        another_owner.authorization.owner_envelope_sha256[0] ^= 1;
        assert!(!validated.matches_authorized_subject_v1(&another_owner));
        let mut another_manifest = authorized_for_roots(set_root, schedule_root);
        another_manifest.subject.canonical_manifest_sha256[0] ^= 1;
        assert!(!validated.matches_authorized_subject_v1(&another_manifest));
    }
}
