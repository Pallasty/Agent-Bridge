//! Schema-shaped S20B rich-packet adapters.
//!
//! This module deliberately stays private.  Parsing or validating a packet
//! yields evidence of a byte/semantic match only; no returned value is an
//! owner-authority, retry, execution, or side-effect capability.

#![cfg_attr(not(test), allow(dead_code))]

use super::assignment_authority::{
    ValidatedAuthorizedAssignmentMemberV1, ValidatedAuthorizedAssignmentSetV1,
};
use super::s17_full_validator::ValidatedS17BatchV1;
use super::*;
use serde::de::{self, DeserializeOwned};
use serde::{Deserialize, Deserializer, Serialize, Serializer};
#[cfg(test)]
use serde_json::Value;

const CANONICALIZATION_V1: &str =
    "AB_RESTRICTED_CANONICAL_JSON_S20B_V1_COMPACT_SORTED_KEYS_ASCII_VALUES_NO_FLOAT";
const DIGEST_FRAMING_V1: &str =
    "U32BE_DOMAIN_LENGTH_DOMAIN_U64BE_CANONICAL_PAYLOAD_LENGTH_CANONICAL_PAYLOAD";

const PREFLIGHT_SCHEMA_V1: &str =
    "agent_bridge.memory_temporal_owned_lab_preflight_receipt_s20b.v0";
const CONTROL_SCHEMA_V1: &str = "agent_bridge.memory_temporal_owned_lab_control_snapshot_s20b.v0";
const CLAIM_SCHEMA_V1: &str =
    "agent_bridge.memory_temporal_owned_lab_authority_control_claim_s20b.v0";
const POSTRUN_SCHEMA_V1: &str =
    "agent_bridge.memory_temporal_owned_lab_post_run_receipt_bundle_s20b.v0";

const PREFLIGHT_KIND_V1: &str = "S20B_OWNED_LAB_FRESH_PREFLIGHT_RECEIPT";
const CONTROL_KIND_V1: &str = "S20B_EXTERNAL_AUTHORITY_CONTROL_SNAPSHOT";
const POSTRUN_KIND_V1: &str = "S20B_OWNED_LAB_POST_RUN_RECEIPT_BUNDLE";

const PREFLIGHT_DOMAIN_V1: &[u8] = b"agent-bridge/biocortex/owned-lab/s20b/preflight-receipt/v1";
const CONTROL_DOMAIN_V1: &[u8] = b"agent-bridge/biocortex/owned-lab/s20b/control-snapshot/v1";
const CLAIM_REGISTRATION_DOMAIN_V1: &[u8] =
    b"agent-bridge/biocortex/owned-lab/s20b/authorization-registration-receipt/v1";
const CLAIM_LEDGER_ROW_DOMAIN_V1: &[u8] =
    b"agent-bridge/biocortex/owned-lab/s20b/authority-control-ledger-row/v1";
const CLAIM_OUTCOME_DOMAIN_V1: &[u8] =
    b"agent-bridge/biocortex/owned-lab/s20b/claim-outcome-receipt/v1";
const CLAIM_TRANSITION_CORE_DOMAIN_V1: &[u8] =
    b"agent-bridge/biocortex/owned-lab/s20b/claim-transition-core/v1";
const POSTRUN_DOMAIN_V1: &[u8] = b"agent-bridge/biocortex/owned-lab/s20b/post-run-bundle/v1";
const PREFLIGHT_CONTEXT_DOMAIN_V1: &[u8] =
    b"agent-bridge/biocortex/owned-lab/s20b/preflight-context/v1";

const PREFLIGHT_SELF_KEY_V1: &str = "preflight_receipt_sha256";
const CONTROL_SELF_KEY_V1: &str = "control_snapshot_sha256";
const CLAIM_SELF_KEY_V1: &str = "claim_packet_sha256";
const POSTRUN_SELF_KEY_V1: &str = "post_run_bundle_sha256";

const PREFLIGHT_SCOPE_V1: &str = "ENTIRE_PACKET_EXCEPT_PREFLIGHT_RECEIPT_SHA256";
const CONTROL_SCOPE_V1: &str = "ENTIRE_PACKET_EXCEPT_CONTROL_SNAPSHOT_SHA256";
const CLAIM_SCOPE_V1: &str = "ENTIRE_PACKET_EXCEPT_CLAIM_PACKET_SHA256";
const POSTRUN_SCOPE_V1: &str = "ENTIRE_PACKET_EXCEPT_POST_RUN_BUNDLE_SHA256";

const ASSIGNMENT_MEMBERSHIP_PROFILE_V1: &str =
    "EXACT_CANONICAL_60_RECORD_SET_RECOMPUTATION_NO_CALLER_ASSERTION";
const CONTENT_ROOT_PROFILE_V1: &str =
    "ORDERED_CANONICAL_BUSINESS_ROW_CORES_SCHEMA_DATABASE_IDENTITY_AND_GENERATION";
const CAS_PARAMETER_ORDER_PROFILE_V1: &str =
    "S20B_EXACT_S19_24_PARAMETER_CAS_WITH_TRANSITION_CORE_IN_P06";

fn aligned_error(code: &'static str, detail: &'static str) -> OwnedLabAuthorizationError {
    s20b_error(code, detail)
}

/// A parsed, lowercase, non-zero SHA-256 security binding.
#[derive(Clone, Copy, Debug, Eq, Ord, PartialEq, PartialOrd)]
struct SecurityDigestV1([u8; 32]);

impl SecurityDigestV1 {
    fn from_array(value: [u8; 32]) -> AuthorizationResult<Self> {
        if !nonzero(&value) {
            return Err(aligned_error(
                "s20b_aligned_zero_digest",
                "security digest must not be all zero",
            ));
        }
        Ok(Self(value))
    }

    fn bytes(&self) -> &[u8; 32] {
        &self.0
    }
}

impl Serialize for SecurityDigestV1 {
    fn serialize<S>(&self, serializer: S) -> Result<S::Ok, S::Error>
    where
        S: Serializer,
    {
        serializer.serialize_str(&hex32(&self.0))
    }
}

impl<'de> Deserialize<'de> for SecurityDigestV1 {
    fn deserialize<D>(deserializer: D) -> Result<Self, D::Error>
    where
        D: Deserializer<'de>,
    {
        let encoded = String::deserialize(deserializer)?;
        if encoded.len() != 64
            || !encoded
                .bytes()
                .all(|byte| byte.is_ascii_digit() || (b'a'..=b'f').contains(&byte))
        {
            return Err(de::Error::custom(
                "expected exactly 64 lowercase hexadecimal characters",
            ));
        }
        let mut decoded = [0_u8; 32];
        for (index, pair) in encoded.as_bytes().chunks_exact(2).enumerate() {
            let nibble = |byte: u8| match byte {
                b'0'..=b'9' => byte - b'0',
                b'a'..=b'f' => byte - b'a' + 10,
                _ => unreachable!(),
            };
            decoded[index] = (nibble(pair[0]) << 4) | nibble(pair[1]);
        }
        if !nonzero(&decoded) {
            return Err(de::Error::custom("all-zero security digest is forbidden"));
        }
        Ok(Self(decoded))
    }
}

#[derive(Clone, Debug, Eq, PartialEq)]
struct GitOidV1([u8; 20]);

impl Serialize for GitOidV1 {
    fn serialize<S>(&self, serializer: S) -> Result<S::Ok, S::Error>
    where
        S: Serializer,
    {
        serializer.serialize_str(&hex(&self.0))
    }
}

impl<'de> Deserialize<'de> for GitOidV1 {
    fn deserialize<D>(deserializer: D) -> Result<Self, D::Error>
    where
        D: Deserializer<'de>,
    {
        let encoded = String::deserialize(deserializer)?;
        if encoded.len() != 40
            || !encoded
                .bytes()
                .all(|byte| byte.is_ascii_digit() || (b'a'..=b'f').contains(&byte))
        {
            return Err(de::Error::custom(
                "expected exactly 40 lowercase hexadecimal characters",
            ));
        }
        let mut decoded = [0_u8; 20];
        for (index, pair) in encoded.as_bytes().chunks_exact(2).enumerate() {
            let nibble = |byte: u8| match byte {
                b'0'..=b'9' => byte - b'0',
                b'a'..=b'f' => byte - b'a' + 10,
                _ => unreachable!(),
            };
            decoded[index] = (nibble(pair[0]) << 4) | nibble(pair[1]);
        }
        Ok(Self(decoded))
    }
}

#[derive(Clone, Debug, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
struct HashingContractV1 {
    hash_algorithm: String,
    canonicalization: String,
    digest_domain: String,
    digest_framing: String,
    hash_scope: String,
    self_hash_field: String,
    self_hash_field_excluded: bool,
    repository_framing_lf_excluded: bool,
    cross_field_semantic_validation_required: bool,
    self_reported_match_fields_are_authoritative: bool,
}

impl HashingContractV1 {
    fn validate(
        &self,
        domain: &[u8],
        scope: &'static str,
        self_key: &'static str,
    ) -> AuthorizationResult<()> {
        let domain = std::str::from_utf8(domain).map_err(|_| {
            aligned_error(
                "s20b_aligned_domain",
                "compile-time packet domain is not ASCII",
            )
        })?;
        if self.hash_algorithm != "SHA-256"
            || self.canonicalization != CANONICALIZATION_V1
            || self.digest_domain != domain
            || self.digest_framing != DIGEST_FRAMING_V1
            || self.hash_scope != scope
            || self.self_hash_field != self_key
            || !self.self_hash_field_excluded
            || !self.repository_framing_lf_excluded
            || !self.cross_field_semantic_validation_required
            || self.self_reported_match_fields_are_authoritative
        {
            return Err(aligned_error(
                "s20b_aligned_hash_contract",
                "packet hashing contract drifted from the frozen schema",
            ));
        }
        Ok(())
    }
}

#[derive(Clone, Debug, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
struct SemanticValidationV1 {
    candidate_match_fields_authoritative: bool,
    independent_validator_required: bool,
    required_rules: Vec<String>,
}

impl SemanticValidationV1 {
    fn validate(&self, expected_rules: &[&str]) -> AuthorizationResult<()> {
        if self.candidate_match_fields_authoritative
            || !self.independent_validator_required
            || self
                .required_rules
                .iter()
                .map(String::as_str)
                .ne(expected_rules.iter().copied())
        {
            return Err(aligned_error(
                "s20b_aligned_semantic_contract",
                "semantic-validation rule list or trust direction drifted",
            ));
        }
        Ok(())
    }
}

#[derive(Clone, Debug)]
struct CanonicalBuiltPacketV1 {
    canonical_bytes: Vec<u8>,
    digest: SecurityDigestV1,
}

fn deserialize_closed_v1<T: DeserializeOwned>(raw: &[u8]) -> AuthorizationResult<T> {
    let value = parse_restricted_canonical(raw)?;
    serde_json::from_value(value).map_err(|_| {
        aligned_error(
            "s20b_aligned_closed_parse",
            "packet does not match the closed typed schema shape",
        )
    })
}

fn serialize_canonical_v1<T: Serialize>(value: &T) -> AuthorizationResult<Vec<u8>> {
    let value = serde_json::to_value(value).map_err(|_| {
        aligned_error(
            "s20b_aligned_typed_encode",
            "typed packet cannot be represented as canonical JSON",
        )
    })?;
    restricted_canonical_bytes(&value)
}

fn canonical_component_digest_v1<T: Serialize>(
    domain: &[u8],
    value: &T,
) -> AuthorizationResult<SecurityDigestV1> {
    SecurityDigestV1::from_array(framed_digest(domain, &[&serialize_canonical_v1(value)?])?)
}

fn recompute_top_level_self_v1<T: Serialize>(
    packet: &T,
    self_key: &'static str,
    domain: &[u8],
) -> AuthorizationResult<SecurityDigestV1> {
    let mut value = serde_json::to_value(packet).map_err(|_| {
        aligned_error(
            "s20b_aligned_typed_encode",
            "typed packet cannot be represented as canonical JSON",
        )
    })?;
    let body = value.as_object_mut().ok_or_else(|| {
        aligned_error(
            "s20b_aligned_top_object",
            "typed packet is not a top-level object",
        )
    })?;
    if body.remove(self_key).is_none() {
        return Err(aligned_error(
            "s20b_aligned_self_scope",
            "the exact named self field is absent from the packet",
        ));
    }
    let payload = restricted_canonical_bytes(&value)?;
    SecurityDigestV1::from_array(framed_digest(domain, &[&payload])?)
}

fn repository_payload_v1(raw: &[u8]) -> AuthorizationResult<&[u8]> {
    let payload = raw.strip_suffix(b"\n").ok_or_else(|| {
        aligned_error(
            "s20b_aligned_repository_lf",
            "repository fixture must end in exactly one excluded LF",
        )
    })?;
    if payload.contains(&b'\n') || payload.contains(&b'\r') {
        return Err(aligned_error(
            "s20b_aligned_repository_lf",
            "repository fixture must be compact and contain exactly one terminal LF",
        ));
    }
    Ok(payload)
}

fn require_nonzero_u64(value: u64, code: &'static str) -> AuthorizationResult<()> {
    if value == 0 {
        Err(aligned_error(code, "security counter must be nonzero"))
    } else {
        Ok(())
    }
}

#[derive(Clone, Debug, Eq, PartialEq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
struct AuthorizationBindingV1 {
    authorization_id_sha256: SecurityDigestV1,
    owner_envelope_sha256: SecurityDigestV1,
    resource_scope_sha256: SecurityDigestV1,
    signed_revocation_epoch: u64,
    signed_payload_sha256: SecurityDigestV1,
    subject_manifest_sha256: SecurityDigestV1,
    trust_anchor_document_sha256: SecurityDigestV1,
}

impl AuthorizationBindingV1 {
    fn validate(&self) -> AuthorizationResult<()> {
        require_nonzero_u64(
            self.signed_revocation_epoch,
            "s20b_aligned_revocation_epoch",
        )
    }
}

#[derive(Clone, Debug, Eq, PartialEq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
struct PreflightAuthorizationBindingV1 {
    authorization_id_sha256: SecurityDigestV1,
    owner_envelope_sha256: SecurityDigestV1,
    resource_scope_sha256: SecurityDigestV1,
    signed_revocation_epoch: u64,
    signed_payload_sha256: SecurityDigestV1,
    subject_manifest_schema_sha256: SecurityDigestV1,
    subject_manifest_sha256: SecurityDigestV1,
    trust_anchor_document_sha256: SecurityDigestV1,
}

impl PreflightAuthorizationBindingV1 {
    fn common(&self) -> AuthorizationBindingV1 {
        AuthorizationBindingV1 {
            authorization_id_sha256: self.authorization_id_sha256,
            owner_envelope_sha256: self.owner_envelope_sha256,
            resource_scope_sha256: self.resource_scope_sha256,
            signed_revocation_epoch: self.signed_revocation_epoch,
            signed_payload_sha256: self.signed_payload_sha256,
            subject_manifest_sha256: self.subject_manifest_sha256,
            trust_anchor_document_sha256: self.trust_anchor_document_sha256,
        }
    }
}

#[derive(Clone, Debug, Eq, PartialEq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
struct PreflightRunBindingV1 {
    attempt_id_sha256: SecurityDigestV1,
    attempt_tombstone_sha256: SecurityDigestV1,
    capability_nonce_sha256: SecurityDigestV1,
    claim_key_sha256: SecurityDigestV1,
    claim_namespace_sha256: SecurityDigestV1,
    controller_binary_sha256: SecurityDigestV1,
    expected_unclaimed_revision: u64,
    observer_binary_sha256: SecurityDigestV1,
    run_assignment_id_sha256: SecurityDigestV1,
    run_id_sha256: SecurityDigestV1,
    runner_binary_sha256: SecurityDigestV1,
}

#[derive(Clone, Debug, Eq, PartialEq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
struct OperationDescriptorBindingV1 {
    operation_sequence: u64,
    operation_id: String,
    scope: String,
    assignment_id_sha256: Option<SecurityDigestV1>,
    operands_sha256: SecurityDigestV1,
    descriptor_sha256: SecurityDigestV1,
}

impl OperationDescriptorBindingV1 {
    fn validate(&self, expected_sequence: usize) -> AuthorizationResult<()> {
        const ALLOWED: [&str; 8] = [
            "CREATE_EXACT_RUN_ROOT",
            "SQLITE_EXACT_PROFILE_SETUP",
            "SPAWN_ONE_ASSIGNED_CHILD",
            "PIDFD_OPEN_ASSIGNED_CHILD",
            "PIDFD_SEND_SIGNAL_SIGKILL",
            "FRESH_EXEC_REOPEN",
            "WRITE_BOUND_RECEIPTS",
            "CLEANUP_EXACT_RUN_ROOT",
        ];
        if self.operation_sequence != expected_sequence as u64
            || !(1..=64).contains(&self.operation_sequence)
            || !ALLOWED.contains(&self.operation_id.as_str())
            || !matches!(self.scope.as_str(), "RUN" | "ASSIGNMENT")
            || (self.scope == "RUN" && self.assignment_id_sha256.is_some())
            || (self.scope == "ASSIGNMENT" && self.assignment_id_sha256.is_none())
        {
            return Err(aligned_error(
                "s20b_aligned_operation_descriptor",
                "operation descriptor tag, sequence, identifier, or assignment scope drifted",
            ));
        }
        Ok(())
    }
}

#[derive(Clone, Debug, Eq, PartialEq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
struct PreflightAssignmentBindingV1 {
    assignment_set_sha256: SecurityDigestV1,
    schedule_sha256: SecurityDigestV1,
    assignment_record_sha256: SecurityDigestV1,
    assignment_ordinal: u64,
    family_id: String,
    case_id: String,
    variant_id: String,
    repetition: u64,
    membership_profile: String,
    membership_validated: bool,
    operation_descriptor_set_sha256: SecurityDigestV1,
    operation_descriptors: Vec<OperationDescriptorBindingV1>,
}

impl PreflightAssignmentBindingV1 {
    fn validate_shape(&self) -> AuthorizationResult<()> {
        let valid_label = |value: &str| {
            !value.is_empty()
                && value.len() <= 96
                && value
                    .bytes()
                    .all(|byte| byte.is_ascii_uppercase() || byte.is_ascii_digit() || byte == b'_')
        };
        if !(1..=60).contains(&self.assignment_ordinal)
            || !matches!(self.family_id.as_str(), "OL00" | "OL04" | "OL05")
            || !valid_label(&self.case_id)
            || !valid_label(&self.variant_id)
            || self.repetition != 1
            || self.membership_profile != ASSIGNMENT_MEMBERSHIP_PROFILE_V1
            || !(1..=64).contains(&self.operation_descriptors.len())
        {
            return Err(aligned_error(
                "s20b_aligned_assignment_shape",
                "assignment label, ordinal, profile, repetition, or descriptor count drifted",
            ));
        }
        for (index, descriptor) in self.operation_descriptors.iter().enumerate() {
            descriptor.validate(index + 1)?;
        }
        Ok(())
    }

    fn validate_authority(
        &self,
        set: &ValidatedAuthorizedAssignmentSetV1,
        member: &ValidatedAuthorizedAssignmentMemberV1,
    ) -> AuthorizationResult<()> {
        let operation_bindings = member.schema_operation_bindings_v1();
        let operations_match = self.operation_descriptors.len() == operation_bindings.len()
            && self
                .operation_descriptors
                .iter()
                .zip(operation_bindings)
                .all(|(reported, expected)| {
                    reported.operation_sequence == expected.operation_sequence
                        && reported.operation_id == expected.operation_id
                        && reported.scope == expected.scope
                        && reported
                            .assignment_id_sha256
                            .as_ref()
                            .map(SecurityDigestV1::bytes)
                            == expected.assignment_id_sha256.as_ref()
                        && reported.operands_sha256.bytes() == &expected.operands_sha256
                        && reported.descriptor_sha256.bytes() == &expected.descriptor_sha256
                });
        if self.assignment_set_sha256.bytes() != &set.assignment_set_sha256
            || self.schedule_sha256.bytes() != &set.schedule_sha256
            || self.assignment_ordinal != member.ordinal
            || self.family_id != member.family_id
            || self.case_id != member.case_id
            || self.variant_id != member.variant_id
            || self.assignment_record_sha256.bytes() != &member.assignment_record_sha256
            || self.operation_descriptor_set_sha256.bytes() != &member.operation_set_sha256
            || !operations_match
        {
            return Err(aligned_error(
                "s20b_aligned_assignment_authority",
                "packet assignment does not match the owner-bound set and member tokens",
            ));
        }
        // A caller-reported `membership_validated` boolean is never consulted.
        Ok(())
    }
}

#[derive(Clone, Debug, Eq, PartialEq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
struct BuildBindingV1 {
    controller_source_sha256: SecurityDigestV1,
    controller_toolchain_sha256: SecurityDigestV1,
    live_observation_validator_binary_sha256: SecurityDigestV1,
    owner_authorization_validator_binary_sha256: SecurityDigestV1,
    receipt_validator_binary_sha256: SecurityDigestV1,
    receipt_validator_ruleset_sha256: SecurityDigestV1,
    runner_source_sha256: SecurityDigestV1,
    runner_toolchain_sha256: SecurityDigestV1,
    s20b_source_commit: GitOidV1,
}

#[derive(Clone, Debug, Eq, PartialEq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
struct EnvironmentSnapshotV1 {
    boot_id_sha256: SecurityDigestV1,
    candidate_device_identity_sha256: SecurityDigestV1,
    candidate_filesystem: String,
    candidate_root: String,
    credential_state_absent: bool,
    effective_resource_limits_sha256: SecurityDigestV1,
    kernel_identity_sha256: SecurityDigestV1,
    mount_identity_sha256: SecurityDigestV1,
    mount_options_sha256: SecurityDigestV1,
    network_route_state_absent: bool,
    root_parent_device_inode_sha256: SecurityDigestV1,
    run_root_derived_path_sha256: SecurityDigestV1,
    run_root_preexisting: bool,
    same_boot_as_manifest: bool,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq, Serialize, Deserialize)]
enum RegistrationReadStateV1 {
    #[serde(rename = "PRESENT_AUTHORIZED_UNCLAIMED")]
    PresentAuthorizedUnclaimed,
    #[serde(rename = "ROW_MISSING")]
    RowMissing,
    #[serde(rename = "READ_UNKNOWN")]
    ReadUnknown,
}

#[derive(Clone, Debug, Eq, PartialEq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
struct ClaimRegistrationViewV1 {
    read_state: RegistrationReadStateV1,
    registration_receipt_sha256: Option<SecurityDigestV1>,
    row_revision: Option<u64>,
    row_core_sha256: Option<SecurityDigestV1>,
}

impl ClaimRegistrationViewV1 {
    fn validate(&self) -> AuthorizationResult<()> {
        let observed = self.registration_receipt_sha256.is_some()
            && self.row_revision.is_some_and(|revision| revision > 0)
            && self.row_core_sha256.is_some();
        let absent = self.registration_receipt_sha256.is_none()
            && self.row_revision.is_none()
            && self.row_core_sha256.is_none();
        if !match self.read_state {
            RegistrationReadStateV1::PresentAuthorizedUnclaimed => observed,
            RegistrationReadStateV1::RowMissing | RegistrationReadStateV1::ReadUnknown => absent,
        } {
            return Err(aligned_error(
                "s20b_aligned_registration_tag",
                "registration tag and nullable observation fields are inconsistent",
            ));
        }
        Ok(())
    }
}

#[derive(Clone, Debug, Eq, PartialEq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
struct PreflightChecksV1 {
    concrete_operation_descriptors: bool,
    exact_assignment_membership: bool,
    exact_build_and_validator_bindings: bool,
    exact_environment: bool,
    exact_owner_authorization: bool,
    exact_resource_and_safety_policy: bool,
    external_checkpoint_current: bool,
    external_revocation_current: bool,
    external_stop_clear: bool,
    full_catalog_and_target_replay_passed: bool,
    no_side_effect_performed: bool,
    path_isolation_clear: bool,
}

impl PreflightChecksV1 {
    fn every_independent_check_passed(&self) -> bool {
        self.concrete_operation_descriptors
            && self.exact_assignment_membership
            && self.exact_build_and_validator_bindings
            && self.exact_environment
            && self.exact_owner_authorization
            && self.exact_resource_and_safety_policy
            && self.external_checkpoint_current
            && self.external_revocation_current
            && self.external_stop_clear
            && self.full_catalog_and_target_replay_passed
            && self.no_side_effect_performed
            && self.path_isolation_clear
    }
}

#[derive(Clone, Debug, Eq, PartialEq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
struct PreflightFreshnessV1 {
    boot_id_sha256: SecurityDigestV1,
    challenge_nonce_sha256: SecurityDigestV1,
    controller_pid: u64,
    controller_start_token_sha256: SecurityDigestV1,
    revocation_ledger_revision: u64,
    same_controller_required_for_cas: bool,
    stop_ledger_revision: u64,
    trusted_wall_clock_used_as_freshness: bool,
}

#[derive(Clone, Debug, Eq, PartialEq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
struct PreflightContextObjectV1 {
    assignment_binding_sha256: SecurityDigestV1,
    authorization_binding_sha256: SecurityDigestV1,
    build_binding_sha256: SecurityDigestV1,
    checks_sha256: SecurityDigestV1,
    claim_registration_sha256: SecurityDigestV1,
    component_digest_profile: String,
    context_version: String,
    environment_snapshot_sha256: SecurityDigestV1,
    freshness_sha256: SecurityDigestV1,
    run_binding_sha256: SecurityDigestV1,
}

#[derive(Clone, Debug, Eq, PartialEq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
struct PreflightPhaseBindingsV1 {
    automatic_retry_allowed: bool,
    cas_attempt_allowed: bool,
    control_snapshot_phase: String,
    control_snapshot_sha256: SecurityDigestV1,
    database_content_root_sha256: Option<SecurityDigestV1>,
    external_checkpoint_receipt_sha256: Option<SecurityDigestV1>,
    parent_graph_profile: String,
    preflight_context_digest_domain: String,
    preflight_context_sha256: SecurityDigestV1,
    terminal_hard_lock: bool,
}

#[derive(Clone, Debug, Eq, PartialEq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
struct PreflightNonclaimsV1 {
    affine_permit_issued: bool,
    cas_claimed: bool,
    execution_start_permitted: bool,
    preflight_is_owner_authority: bool,
    preflight_is_post_run_receipt: bool,
    schema_conformance_authorizes_live_execution: bool,
    side_effects_unlocked: String,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq, Serialize, Deserialize)]
enum PreflightStateV1 {
    #[serde(rename = "SYNTHETIC_KAT_NON_LIVE_PREFLIGHT")]
    SyntheticKatNonLive,
    #[serde(rename = "READY_TO_ATTEMPT_SINGLE_CAS_NON_EXECUTING")]
    ReadyToAttemptSingleCasNonExecuting,
    #[serde(rename = "FAILED_TERMINAL")]
    FailedTerminal,
    #[serde(rename = "UNKNOWN_OUTCOME_TERMINAL_HARD_LOCK")]
    UnknownOutcomeTerminalHardLock,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
struct PreflightReceiptPacketV1 {
    schema: String,
    packet_kind: String,
    canonicalization: String,
    hashing_contract: HashingContractV1,
    test_only: bool,
    synthetic: bool,
    preflight_state: PreflightStateV1,
    authorization_binding: PreflightAuthorizationBindingV1,
    run_binding: PreflightRunBindingV1,
    assignment_binding: PreflightAssignmentBindingV1,
    build_binding: BuildBindingV1,
    environment_snapshot: EnvironmentSnapshotV1,
    claim_registration: ClaimRegistrationViewV1,
    checks: PreflightChecksV1,
    freshness: PreflightFreshnessV1,
    preflight_context: PreflightContextObjectV1,
    phase_bindings: PreflightPhaseBindingsV1,
    preflight_receipt_sha256: SecurityDigestV1,
    semantic_validation: SemanticValidationV1,
    nonclaims: PreflightNonclaimsV1,
}

const PREFLIGHT_RULES_V1: [&str; 8] = [
    "PREFLIGHT_CONTEXT_RECOMPUTED_WITH_CONTROL_AND_FINAL_SELF_EXCLUDED",
    "CONTROL_SNAPSHOT_BINDS_CONTEXT_AND_NOT_FINAL_PREFLIGHT",
    "FINAL_PREFLIGHT_BINDS_CONTEXT_AND_CONTROL_SNAPSHOT",
    "IMMUTABLE_AUTHORIZATION_RUN_AND_BUILD_TUPLE_EXACT",
    "ASSIGNMENT_IS_MEMBER_OF_OWNER_BOUND_CANONICAL_60_RECORD_SET",
    "OPERATION_DESCRIPTORS_RECOMPUTED_AND_ASSIGNMENT_SCOPED",
    "REGISTRATION_ROW_AND_CONTENT_ROOT_RECOMPUTED",
    "READY_REQUIRES_ALL_INDEPENDENT_CHECKS",
];

fn preflight_component_domain_v1(component: &str) -> Vec<u8> {
    format!("agent-bridge/biocortex/owned-lab/s20b/preflight-context-component/{component}/v1")
        .into_bytes()
}

impl PreflightReceiptPacketV1 {
    fn rebuild_context_v1(&mut self) -> AuthorizationResult<SecurityDigestV1> {
        self.preflight_context = PreflightContextObjectV1 {
            assignment_binding_sha256: canonical_component_digest_v1(
                &preflight_component_domain_v1("assignment-binding"),
                &self.assignment_binding,
            )?,
            authorization_binding_sha256: canonical_component_digest_v1(
                &preflight_component_domain_v1("authorization-binding"),
                &self.authorization_binding,
            )?,
            build_binding_sha256: canonical_component_digest_v1(
                &preflight_component_domain_v1("build-binding"),
                &self.build_binding,
            )?,
            checks_sha256: canonical_component_digest_v1(
                &preflight_component_domain_v1("checks"),
                &self.checks,
            )?,
            claim_registration_sha256: canonical_component_digest_v1(
                &preflight_component_domain_v1("claim-registration"),
                &self.claim_registration,
            )?,
            component_digest_profile: "DOMAIN_SEPARATED_CANONICAL_TOP_LEVEL_COMPONENTS".into(),
            context_version: "S20B_PREFLIGHT_CONTEXT_V1".into(),
            environment_snapshot_sha256: canonical_component_digest_v1(
                &preflight_component_domain_v1("environment-snapshot"),
                &self.environment_snapshot,
            )?,
            freshness_sha256: canonical_component_digest_v1(
                &preflight_component_domain_v1("freshness"),
                &self.freshness,
            )?,
            run_binding_sha256: canonical_component_digest_v1(
                &preflight_component_domain_v1("run-binding"),
                &self.run_binding,
            )?,
        };
        let digest =
            canonical_component_digest_v1(PREFLIGHT_CONTEXT_DOMAIN_V1, &self.preflight_context)?;
        self.phase_bindings.preflight_context_sha256 = digest;
        Ok(digest)
    }

    fn validate_shape_v1(&self) -> AuthorizationResult<()> {
        self.hashing_contract.validate(
            PREFLIGHT_DOMAIN_V1,
            PREFLIGHT_SCOPE_V1,
            PREFLIGHT_SELF_KEY_V1,
        )?;
        self.semantic_validation.validate(&PREFLIGHT_RULES_V1)?;
        self.authorization_binding.common().validate()?;
        self.assignment_binding.validate_shape()?;
        self.claim_registration.validate()?;
        for value in [
            self.run_binding.expected_unclaimed_revision,
            self.freshness.controller_pid,
            self.freshness.revocation_ledger_revision,
            self.freshness.stop_ledger_revision,
        ] {
            require_nonzero_u64(value, "s20b_aligned_preflight_counter")?;
        }
        if self.schema != PREFLIGHT_SCHEMA_V1
            || self.packet_kind != PREFLIGHT_KIND_V1
            || self.canonicalization != CANONICALIZATION_V1
            || self.test_only != self.synthetic
            || self.environment_snapshot.candidate_filesystem != "f2fs"
            || self.environment_snapshot.candidate_root != "/Data/CascadeProjects/.ab-owned-lab"
            || !self.environment_snapshot.credential_state_absent
            || !self.environment_snapshot.network_route_state_absent
            || self.environment_snapshot.run_root_preexisting
            || !self.environment_snapshot.same_boot_as_manifest
            || !self.checks.no_side_effect_performed
            || !self.freshness.same_controller_required_for_cas
            || self.freshness.trusted_wall_clock_used_as_freshness
            || self.phase_bindings.parent_graph_profile
                != "PREFLIGHT_CONTEXT_THEN_CONTROL_SNAPSHOT_THEN_FINAL_PREFLIGHT_RECEIPT"
            || self.phase_bindings.preflight_context_digest_domain
                != std::str::from_utf8(PREFLIGHT_CONTEXT_DOMAIN_V1).unwrap()
            || self.phase_bindings.control_snapshot_phase != "PREFLIGHT_BEFORE_CLAIM"
            || self.phase_bindings.automatic_retry_allowed
            || self.nonclaims.affine_permit_issued
            || self.nonclaims.cas_claimed
            || self.nonclaims.execution_start_permitted
            || self.nonclaims.preflight_is_owner_authority
            || self.nonclaims.preflight_is_post_run_receipt
            || self.nonclaims.schema_conformance_authorizes_live_execution
            || self.nonclaims.side_effects_unlocked != "NONE"
        {
            return Err(aligned_error(
                "s20b_aligned_preflight_shape",
                "preflight schema constant, fail-closed field, or environment constant drifted",
            ));
        }
        let state_valid = match self.preflight_state {
            PreflightStateV1::SyntheticKatNonLive => {
                self.test_only
                    && self.synthetic
                    && self.phase_bindings.terminal_hard_lock
                    && !self.phase_bindings.cas_attempt_allowed
            }
            PreflightStateV1::ReadyToAttemptSingleCasNonExecuting => {
                !self.test_only
                    && !self.synthetic
                    && matches!(
                        self.claim_registration.read_state,
                        RegistrationReadStateV1::PresentAuthorizedUnclaimed
                    )
                    && self.checks.every_independent_check_passed()
                    && self
                        .phase_bindings
                        .external_checkpoint_receipt_sha256
                        .is_some()
                    && self.phase_bindings.database_content_root_sha256.is_some()
                    && !self.phase_bindings.terminal_hard_lock
                    && self.phase_bindings.cas_attempt_allowed
            }
            PreflightStateV1::FailedTerminal | PreflightStateV1::UnknownOutcomeTerminalHardLock => {
                !self.test_only
                    && !self.synthetic
                    && self.phase_bindings.terminal_hard_lock
                    && !self.phase_bindings.cas_attempt_allowed
            }
        };
        if !state_valid {
            return Err(aligned_error(
                "s20b_aligned_preflight_state",
                "preflight state is inconsistent with observations and fail-closed outcome",
            ));
        }
        Ok(())
    }
}

#[must_use]
struct ValidatedPreflightContextTokenV1 {
    digest: SecurityDigestV1,
    authorization_binding: AuthorizationBindingV1,
    run_binding: PreflightRunBindingV1,
    assignment_binding: PreflightAssignmentBindingV1,
}

#[must_use]
struct ValidatedPreflightReceiptTokenV1 {
    digest: SecurityDigestV1,
    context_digest: SecurityDigestV1,
    control_digest: SecurityDigestV1,
    authorization_binding: AuthorizationBindingV1,
    run_binding: PreflightRunBindingV1,
    assignment_binding: PreflightAssignmentBindingV1,
}

/// Evidence expected from a future closed observer/build verifier.  There is
/// deliberately no constructor in S20B: the current repository has no real
/// observer and the historical S19 owner signature does not bind S20B build
/// additions.  Requiring this token prevents a self-consistent candidate from
/// upgrading its own environment/check booleans into authority.
#[must_use]
struct ValidatedPreflightObservationFactsV1 {
    run_binding: PreflightRunBindingV1,
    build_binding: BuildBindingV1,
    environment_snapshot: EnvironmentSnapshotV1,
    claim_registration: ClaimRegistrationViewV1,
    checks: PreflightChecksV1,
    freshness: PreflightFreshnessV1,
    independent_failure_domain_proved: bool,
}

fn parse_preflight_packet_v1(raw: &[u8]) -> AuthorizationResult<PreflightReceiptPacketV1> {
    deserialize_closed_v1(raw)
}

fn build_preflight_packet_v1(
    mut packet: PreflightReceiptPacketV1,
) -> AuthorizationResult<CanonicalBuiltPacketV1> {
    packet.rebuild_context_v1()?;
    packet.validate_shape_v1()?;
    let digest = recompute_top_level_self_v1(&packet, PREFLIGHT_SELF_KEY_V1, PREFLIGHT_DOMAIN_V1)?;
    packet.preflight_receipt_sha256 = digest;
    Ok(CanonicalBuiltPacketV1 {
        canonical_bytes: serialize_canonical_v1(&packet)?,
        digest,
    })
}

fn validate_preflight_context_v1(
    packet: &PreflightReceiptPacketV1,
    authorized: &AuthorizedUnclaimedS19SubjectV1,
    observations: &ValidatedPreflightObservationFactsV1,
    committed: &ValidatedCommittedDatabaseStateV1,
    assignments: &ValidatedAuthorizedAssignmentSetV1,
    member: &ValidatedAuthorizedAssignmentMemberV1,
) -> AuthorizationResult<ValidatedPreflightContextTokenV1> {
    packet.validate_shape_v1()?;
    packet
        .assignment_binding
        .validate_authority(assignments, member)?;
    if packet.run_binding.run_assignment_id_sha256.bytes() != &member.assignment_id_sha256 {
        return Err(aligned_error(
            "s20b_aligned_run_assignment",
            "run-assignment identifier does not match the owner-bound assignment member",
        ));
    }
    let expected_authorization = AuthorizationBindingV1 {
        authorization_id_sha256: SecurityDigestV1::from_array(
            authorized.authorization.authorization_id_sha256,
        )?,
        owner_envelope_sha256: SecurityDigestV1::from_array(
            authorized.authorization.owner_envelope_sha256,
        )?,
        resource_scope_sha256: SecurityDigestV1::from_array(
            authorized.subject.resource_scope_sha256,
        )?,
        signed_revocation_epoch: authorized.authorization.revocation_epoch,
        signed_payload_sha256: SecurityDigestV1::from_array(
            authorized.authorization.payload_sha256,
        )?,
        subject_manifest_sha256: SecurityDigestV1::from_array(
            authorized.subject.canonical_manifest_sha256,
        )?,
        trust_anchor_document_sha256: SecurityDigestV1::from_array(
            authorized.authorization.trust_anchor_document_sha256,
        )?,
    };
    let phase_state_matches = match packet.preflight_state {
        PreflightStateV1::ReadyToAttemptSingleCasNonExecuting => {
            packet
                .phase_bindings
                .database_content_root_sha256
                .as_ref()
                .map(SecurityDigestV1::bytes)
                == Some(&committed.business_content_root_sha256)
                && packet
                    .phase_bindings
                    .external_checkpoint_receipt_sha256
                    .as_ref()
                    .map(SecurityDigestV1::bytes)
                    == Some(&committed.checkpoint_head_sha256)
                && observations.independent_failure_domain_proved
                && committed.independent_failure_domain_proved
        }
        _ => true,
    };
    if !assignments.matches_authorized_subject_v1(authorized)
        || !packet.assignment_binding.membership_validated
        || packet.authorization_binding.common() != expected_authorization
        || packet
            .authorization_binding
            .subject_manifest_schema_sha256
            .bytes()
            != &authorized.subject.schema_sha256
        || packet.run_binding != observations.run_binding
        || packet.build_binding != observations.build_binding
        || packet.environment_snapshot != observations.environment_snapshot
        || packet.claim_registration != observations.claim_registration
        || packet.checks != observations.checks
        || packet.freshness != observations.freshness
        || packet.run_binding.capability_nonce_sha256.bytes() != &authorized.capability_nonce_sha256
        || packet.run_binding.claim_namespace_sha256.bytes()
            != &authorized.subject.claim_namespace_sha256
        || packet.run_binding.claim_key_sha256.bytes() != &authorized.subject.claim_key_sha256
        || packet.run_binding.expected_unclaimed_revision
            != authorized.subject.expected_unclaimed_revision
        || packet.run_binding.controller_binary_sha256.bytes()
            != &authorized.subject.controller_binary_sha256
        || packet.run_binding.runner_binary_sha256.bytes()
            != &authorized.subject.runner_binary_sha256
        || packet.run_binding.observer_binary_sha256.bytes()
            != &authorized.subject.preflight_observer_binary_sha256
        || !phase_state_matches
    {
        return Err(aligned_error(
            "s20b_aligned_preflight_authority",
            "preflight candidate is not bound to owner, observer, build, environment, checks, or committed-state evidence",
        ));
    }
    let mut rebuilt = packet.clone();
    let context_digest = rebuilt.rebuild_context_v1()?;
    if rebuilt.preflight_context != packet.preflight_context
        || context_digest != packet.phase_bindings.preflight_context_sha256
    {
        return Err(aligned_error(
            "s20b_aligned_preflight_context",
            "preflight component or context digest does not independently recompute",
        ));
    }
    Ok(ValidatedPreflightContextTokenV1 {
        digest: context_digest,
        authorization_binding: packet.authorization_binding.common(),
        run_binding: packet.run_binding.clone(),
        assignment_binding: packet.assignment_binding.clone(),
    })
}

#[derive(Clone, Debug, Eq, PartialEq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
struct ControlRunBindingV1 {
    attempt_id_sha256: SecurityDigestV1,
    capability_nonce_sha256: SecurityDigestV1,
    claim_key_sha256: SecurityDigestV1,
    claim_namespace_sha256: SecurityDigestV1,
    controller_binary_sha256: SecurityDigestV1,
    run_assignment_id_sha256: SecurityDigestV1,
    run_id_sha256: SecurityDigestV1,
    runner_binary_sha256: SecurityDigestV1,
}

#[derive(Clone, Debug, Eq, PartialEq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
struct ControlAssignmentBindingV1 {
    assignment_record_sha256: SecurityDigestV1,
    assignment_set_sha256: SecurityDigestV1,
    operation_descriptor_set_sha256: SecurityDigestV1,
    schedule_sha256: SecurityDigestV1,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq, Serialize, Deserialize)]
enum ControlPhaseV2 {
    #[serde(rename = "PREFLIGHT_BEFORE_CLAIM")]
    PreflightBeforeClaim,
    #[serde(rename = "CAS_LINEARIZATION")]
    CasLinearization,
    #[serde(rename = "POST_CLAIM_PRE_START")]
    PostClaimPreStart,
    #[serde(rename = "RUNTIME_ACTION_BOUNDARY")]
    RuntimeActionBoundary,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq, Serialize, Deserialize)]
enum ParentKindV1 {
    #[serde(rename = "PREFLIGHT_CONTEXT")]
    PreflightContext,
    #[serde(rename = "PREFLIGHT_RECEIPT")]
    PreflightReceipt,
    #[serde(rename = "CLAIM_RECEIPT")]
    ClaimReceipt,
    #[serde(rename = "PREVIOUS_ACTION_START_RECEIPT")]
    PreviousActionStartReceipt,
}

#[derive(Clone, Debug, Eq, PartialEq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
struct PhaseParentV1 {
    backward_edge_only: bool,
    final_preflight_receipt_referenced: bool,
    parent_kind: ParentKindV1,
    parent_sha256: SecurityDigestV1,
}

#[derive(Clone, Debug, Eq, PartialEq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
struct ControlLedgerBindingV1 {
    authority_control_schema_sha256: SecurityDigestV1,
    checkpoint_monotonic_counter: u64,
    checkpoint_provider_identity_sha256: SecurityDigestV1,
    content_root_profile: String,
    database_content_root_sha256: SecurityDigestV1,
    database_identity_sha256: SecurityDigestV1,
    external_checkpoint_receipt_sha256: SecurityDigestV1,
    independent_checkpoint_current: bool,
    independent_failure_domain_proved: bool,
    sqlite_profile_sha256: SecurityDigestV1,
    transaction_sequence: u64,
}

impl ControlLedgerBindingV1 {
    fn validate_committed_state(
        &self,
        committed: &ValidatedCommittedDatabaseStateV1,
    ) -> AuthorizationResult<()> {
        if self.authority_control_schema_sha256.bytes() != &committed.schema_catalog_sha256
            || self.database_identity_sha256.bytes() != &committed.database_identity_sha256
            || self.database_content_root_sha256.bytes() != &committed.business_content_root_sha256
            || self.checkpoint_monotonic_counter != committed.generation
            || self.external_checkpoint_receipt_sha256.bytes() != &committed.checkpoint_head_sha256
            || self.checkpoint_provider_identity_sha256.bytes()
                != &committed.checkpoint_provider_identity_sha256
            || !self.independent_checkpoint_current
            || self.independent_failure_domain_proved != committed.independent_failure_domain_proved
        {
            return Err(aligned_error(
                "s20b_aligned_committed_control",
                "control binding mismatches committed evidence or overclaims independent checkpoint proof",
            ));
        }
        Ok(())
    }
}

#[derive(Clone, Copy, Debug, Eq, PartialEq, Serialize, Deserialize)]
enum ClaimRowPresenceV1 {
    #[serde(rename = "PRESENT")]
    Present,
    #[serde(rename = "ROW_MISSING")]
    RowMissing,
    #[serde(rename = "READ_UNKNOWN")]
    ReadUnknown,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq, Serialize, Deserialize)]
enum ClaimRowStateV1 {
    #[serde(rename = "AUTHORIZED_UNCLAIMED")]
    AuthorizedUnclaimed,
    #[serde(rename = "CONSUMED_FOR_EXACT_RUN")]
    ConsumedForExactRun,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq, Serialize, Deserialize)]
enum ClaimReadErrorClassV1 {
    #[serde(rename = "MISSING")]
    Missing,
    #[serde(rename = "IO_OR_INTEGRITY_UNKNOWN")]
    IoOrIntegrityUnknown,
}

#[derive(Clone, Debug, Eq, PartialEq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
struct TaggedClaimViewV1 {
    read_error_class: Option<ClaimReadErrorClassV1>,
    revision: Option<u64>,
    row_core_sha256: Option<SecurityDigestV1>,
    row_presence: ClaimRowPresenceV1,
    state: Option<ClaimRowStateV1>,
}

impl TaggedClaimViewV1 {
    fn validate(&self) -> AuthorizationResult<()> {
        let valid = match self.row_presence {
            ClaimRowPresenceV1::Present => {
                self.state.is_some()
                    && self.revision.is_some_and(|value| value > 0)
                    && self.row_core_sha256.is_some()
                    && self.read_error_class.is_none()
            }
            ClaimRowPresenceV1::RowMissing => {
                self.state.is_none()
                    && self.revision.is_none()
                    && self.row_core_sha256.is_none()
                    && self.read_error_class == Some(ClaimReadErrorClassV1::Missing)
            }
            ClaimRowPresenceV1::ReadUnknown => {
                self.state.is_none()
                    && self.revision.is_none()
                    && self.row_core_sha256.is_none()
                    && self.read_error_class == Some(ClaimReadErrorClassV1::IoOrIntegrityUnknown)
            }
        };
        if !valid {
            return Err(aligned_error(
                "s20b_aligned_claim_view_tag",
                "claim row tag fabricates or omits tagged observation values",
            ));
        }
        Ok(())
    }
}

#[derive(Clone, Copy, Debug, Eq, PartialEq, Serialize, Deserialize)]
enum StopReadStateV1 {
    #[serde(rename = "CLEAR")]
    Clear,
    #[serde(rename = "TRIGGERED")]
    Triggered,
    #[serde(rename = "READ_UNKNOWN")]
    ReadUnknown,
}

#[derive(Clone, Debug, Eq, PartialEq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
struct TaggedStopViewV1 {
    ledger_revision: Option<u64>,
    policy_identity_sha256: Option<SecurityDigestV1>,
    read_state: StopReadStateV1,
    trigger_receipt_sha256: Option<SecurityDigestV1>,
}

impl TaggedStopViewV1 {
    fn validate(&self) -> AuthorizationResult<()> {
        let base_observed = self.ledger_revision.is_some_and(|value| value > 0)
            && self.policy_identity_sha256.is_some();
        let valid = match self.read_state {
            StopReadStateV1::Clear => base_observed && self.trigger_receipt_sha256.is_none(),
            StopReadStateV1::Triggered => base_observed && self.trigger_receipt_sha256.is_some(),
            StopReadStateV1::ReadUnknown => {
                self.ledger_revision.is_none()
                    && self.policy_identity_sha256.is_none()
                    && self.trigger_receipt_sha256.is_none()
            }
        };
        if !valid {
            return Err(aligned_error(
                "s20b_aligned_stop_view_tag",
                "STOP tag fabricates or omits tagged observation values",
            ));
        }
        Ok(())
    }
}

#[derive(Clone, Copy, Debug, Eq, PartialEq, Serialize, Deserialize)]
enum RevocationReadStateV1 {
    #[serde(rename = "EXACT")]
    Exact,
    #[serde(rename = "MISMATCH")]
    Mismatch,
    #[serde(rename = "ROLLBACK_DETECTED")]
    RollbackDetected,
    #[serde(rename = "READ_UNKNOWN")]
    ReadUnknown,
}

#[derive(Clone, Debug, Eq, PartialEq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
struct TaggedRevocationViewV1 {
    anchor_key_version: Option<u64>,
    current_active_epoch: Option<u64>,
    envelope_epoch: Option<u64>,
    ledger_revision: Option<u64>,
    policy_identity_sha256: Option<SecurityDigestV1>,
    read_state: RevocationReadStateV1,
    rollback_detected: Option<bool>,
}

impl TaggedRevocationViewV1 {
    fn validate(&self) -> AuthorizationResult<()> {
        let observed = self.anchor_key_version.is_some_and(|value| value > 0)
            && self.current_active_epoch.is_some_and(|value| value > 0)
            && self.envelope_epoch.is_some_and(|value| value > 0)
            && self.ledger_revision.is_some_and(|value| value > 0)
            && self.policy_identity_sha256.is_some()
            && self.rollback_detected.is_some();
        let absent = self.anchor_key_version.is_none()
            && self.current_active_epoch.is_none()
            && self.envelope_epoch.is_none()
            && self.ledger_revision.is_none()
            && self.policy_identity_sha256.is_none()
            && self.rollback_detected.is_none();
        let valid = match self.read_state {
            RevocationReadStateV1::Exact | RevocationReadStateV1::Mismatch => {
                observed && self.rollback_detected == Some(false)
            }
            RevocationReadStateV1::RollbackDetected => {
                observed && self.rollback_detected == Some(true)
            }
            RevocationReadStateV1::ReadUnknown => absent,
        };
        if !valid {
            return Err(aligned_error(
                "s20b_aligned_revocation_view_tag",
                "revocation tag fabricates, omits, or contradicts tagged observations",
            ));
        }
        Ok(())
    }
}

#[derive(Clone, Copy, Debug, Eq, PartialEq, Serialize, Deserialize)]
enum ControlReadOutcomeV1 {
    #[serde(rename = "COMPLETE")]
    Complete,
    #[serde(rename = "CLAIM_ROW_MISSING")]
    ClaimRowMissing,
    #[serde(rename = "ROLLBACK_DETECTED")]
    RollbackDetected,
    #[serde(rename = "READ_UNKNOWN")]
    ReadUnknown,
}

#[derive(Clone, Debug, Eq, PartialEq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
struct ControlFreshnessV1 {
    boot_id_sha256: SecurityDigestV1,
    challenge_nonce_sha256: SecurityDigestV1,
    controller_pid: u64,
    controller_start_token_sha256: SecurityDigestV1,
    trusted_wall_clock_used_as_freshness: bool,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq, Serialize, Deserialize)]
enum ControlDecisionV1 {
    #[serde(rename = "SYNTHETIC_VALIDATION_ONLY")]
    SyntheticValidationOnly,
    #[serde(rename = "ALLOW_GUARDED_NEXT_ACTION")]
    AllowGuardedNextAction,
    #[serde(rename = "DENY_STOP_TRIGGERED")]
    DenyStopTriggered,
    #[serde(rename = "DENY_REVOCATION_MISMATCH")]
    DenyRevocationMismatch,
    #[serde(rename = "DENY_CLAIM_STATE_MISMATCH")]
    DenyClaimStateMismatch,
    #[serde(rename = "DENY_ROLLBACK")]
    DenyRollback,
    #[serde(rename = "DENY_UNKNOWN")]
    DenyUnknown,
}

#[derive(Clone, Debug, Eq, PartialEq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
struct ControlResultV1 {
    automatic_retry_allowed: bool,
    control_decision: ControlDecisionV1,
    next_action_allowed: bool,
    terminal_hard_lock: bool,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq, Serialize, Deserialize)]
enum ControlSnapshotStateV1 {
    #[serde(rename = "SYNTHETIC_KAT_NON_LIVE_CONTROL_SNAPSHOT")]
    SyntheticKatNonLive,
    #[serde(rename = "COMPLETE_ALLOW")]
    CompleteAllow,
    #[serde(rename = "DENY_STOP_TRIGGERED")]
    DenyStopTriggered,
    #[serde(rename = "DENY_REVOCATION_MISMATCH")]
    DenyRevocationMismatch,
    #[serde(rename = "DENY_CLAIM_STATE_MISMATCH")]
    DenyClaimStateMismatch,
    #[serde(rename = "DENY_ROLLBACK_TERMINAL_HARD_LOCK")]
    DenyRollbackTerminalHardLock,
    #[serde(rename = "DENY_UNKNOWN_TERMINAL_HARD_LOCK")]
    DenyUnknownTerminalHardLock,
}

#[derive(Clone, Debug, Eq, PartialEq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
struct ControlNonclaimsV1 {
    schema_conformance_authorizes_live_execution: bool,
    side_effects_unlocked: String,
    snapshot_is_execution_capability: bool,
    snapshot_is_owner_authority: bool,
    snapshot_mutates_control_state: bool,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
struct ControlSnapshotPacketV1 {
    assignment_binding: ControlAssignmentBindingV1,
    authorization_binding: AuthorizationBindingV1,
    canonicalization: String,
    claim_view: TaggedClaimViewV1,
    control_snapshot_sha256: SecurityDigestV1,
    freshness: ControlFreshnessV1,
    hashing_contract: HashingContractV1,
    ledger_binding: ControlLedgerBindingV1,
    nonclaims: ControlNonclaimsV1,
    packet_kind: String,
    phase_parent: PhaseParentV1,
    read_outcome: ControlReadOutcomeV1,
    result: ControlResultV1,
    revocation_view: TaggedRevocationViewV1,
    run_binding: ControlRunBindingV1,
    schema: String,
    semantic_validation: SemanticValidationV1,
    snapshot_phase: ControlPhaseV2,
    snapshot_state: ControlSnapshotStateV1,
    stop_view: TaggedStopViewV1,
    synthetic: bool,
    test_only: bool,
}

const CONTROL_RULES_V1: [&str; 6] = [
    "PHASE_PARENT_DIGEST_RECOMPUTED_FROM_CANONICAL_PARENT_PACKET",
    "PREFLIGHT_PHASE_PARENT_IS_CONTEXT_AND_NEVER_FINAL_PREFLIGHT",
    "AUTHORIZATION_RUN_ASSIGNMENT_AND_OPERATION_BINDINGS_EXACT",
    "DATABASE_CONTENT_ROOT_AND_EXTERNAL_CHECKPOINT_RECOMPUTED",
    "MISSING_ROLLBACK_AND_UNKNOWN_VIEWS_HAVE_NO_FABRICATED_VALUES",
    "ALLOW_REQUIRES_COMPLETE_CURRENT_PRESENT_CLEAR_AND_EXACT_STATE",
];

impl ControlSnapshotPacketV1 {
    fn validate_shape_v1(&self) -> AuthorizationResult<()> {
        self.hashing_contract
            .validate(CONTROL_DOMAIN_V1, CONTROL_SCOPE_V1, CONTROL_SELF_KEY_V1)?;
        self.semantic_validation.validate(&CONTROL_RULES_V1)?;
        self.authorization_binding.validate()?;
        self.claim_view.validate()?;
        self.stop_view.validate()?;
        self.revocation_view.validate()?;
        for value in [
            self.ledger_binding.transaction_sequence,
            self.ledger_binding.checkpoint_monotonic_counter,
            self.freshness.controller_pid,
        ] {
            require_nonzero_u64(value, "s20b_aligned_control_counter")?;
        }
        let parent_valid = match self.snapshot_phase {
            ControlPhaseV2::PreflightBeforeClaim => {
                self.phase_parent.parent_kind == ParentKindV1::PreflightContext
                    && !self.phase_parent.final_preflight_receipt_referenced
            }
            ControlPhaseV2::CasLinearization => {
                self.phase_parent.parent_kind == ParentKindV1::PreflightReceipt
                    && self.phase_parent.final_preflight_receipt_referenced
            }
            ControlPhaseV2::PostClaimPreStart => {
                self.phase_parent.parent_kind == ParentKindV1::ClaimReceipt
                    && self.phase_parent.final_preflight_receipt_referenced
            }
            ControlPhaseV2::RuntimeActionBoundary => {
                matches!(
                    self.phase_parent.parent_kind,
                    ParentKindV1::ClaimReceipt | ParentKindV1::PreviousActionStartReceipt
                ) && self.phase_parent.final_preflight_receipt_referenced
            }
        };
        let read_valid = match self.read_outcome {
            ControlReadOutcomeV1::Complete => {
                self.claim_view.row_presence == ClaimRowPresenceV1::Present
                    && self.stop_view.read_state != StopReadStateV1::ReadUnknown
                    && !matches!(
                        self.revocation_view.read_state,
                        RevocationReadStateV1::RollbackDetected
                            | RevocationReadStateV1::ReadUnknown
                    )
            }
            ControlReadOutcomeV1::ClaimRowMissing => {
                self.claim_view.row_presence == ClaimRowPresenceV1::RowMissing
            }
            ControlReadOutcomeV1::RollbackDetected => {
                self.revocation_view.read_state == RevocationReadStateV1::RollbackDetected
            }
            ControlReadOutcomeV1::ReadUnknown => {
                self.claim_view.row_presence == ClaimRowPresenceV1::ReadUnknown
                    || self.stop_view.read_state == StopReadStateV1::ReadUnknown
                    || self.revocation_view.read_state == RevocationReadStateV1::ReadUnknown
            }
        };
        if self.schema != CONTROL_SCHEMA_V1
            || self.packet_kind != CONTROL_KIND_V1
            || self.canonicalization != CANONICALIZATION_V1
            || self.test_only != self.synthetic
            || !self.phase_parent.backward_edge_only
            || !parent_valid
            || !read_valid
            || self.ledger_binding.content_root_profile != CONTENT_ROOT_PROFILE_V1
            || self.freshness.trusted_wall_clock_used_as_freshness
            || self.result.automatic_retry_allowed
            || self.nonclaims.schema_conformance_authorizes_live_execution
            || self.nonclaims.snapshot_is_execution_capability
            || self.nonclaims.snapshot_is_owner_authority
            || self.nonclaims.snapshot_mutates_control_state
            || self.nonclaims.side_effects_unlocked != "NONE"
        {
            return Err(aligned_error(
                "s20b_aligned_control_shape",
                "control schema constant, phase parent, read tag, or nonclaim drifted",
            ));
        }
        let allow = self.read_outcome == ControlReadOutcomeV1::Complete
            && self.claim_view.row_presence == ClaimRowPresenceV1::Present
            && self.claim_view.state == Some(ClaimRowStateV1::AuthorizedUnclaimed)
            && self.stop_view.read_state == StopReadStateV1::Clear
            && self.revocation_view.read_state == RevocationReadStateV1::Exact
            && self.revocation_view.rollback_detected == Some(false)
            && self.ledger_binding.independent_checkpoint_current
            && self.ledger_binding.independent_failure_domain_proved;
        let state_valid = match self.snapshot_state {
            ControlSnapshotStateV1::SyntheticKatNonLive => {
                self.test_only
                    && self.synthetic
                    && self.result.control_decision == ControlDecisionV1::SyntheticValidationOnly
                    && !self.result.next_action_allowed
            }
            ControlSnapshotStateV1::CompleteAllow => {
                !self.test_only
                    && allow
                    && self.result.control_decision == ControlDecisionV1::AllowGuardedNextAction
                    && self.result.next_action_allowed
                    && !self.result.terminal_hard_lock
            }
            ControlSnapshotStateV1::DenyStopTriggered => {
                !self.test_only
                    && self.stop_view.read_state == StopReadStateV1::Triggered
                    && self.result.control_decision == ControlDecisionV1::DenyStopTriggered
                    && !self.result.next_action_allowed
            }
            ControlSnapshotStateV1::DenyRevocationMismatch => {
                !self.test_only
                    && self.revocation_view.read_state == RevocationReadStateV1::Mismatch
                    && self.result.control_decision == ControlDecisionV1::DenyRevocationMismatch
                    && !self.result.next_action_allowed
            }
            ControlSnapshotStateV1::DenyClaimStateMismatch => {
                !self.test_only
                    && (self.claim_view.row_presence != ClaimRowPresenceV1::Present
                        || self.claim_view.state != Some(ClaimRowStateV1::AuthorizedUnclaimed))
                    && self.result.control_decision == ControlDecisionV1::DenyClaimStateMismatch
                    && !self.result.next_action_allowed
            }
            ControlSnapshotStateV1::DenyRollbackTerminalHardLock => {
                !self.test_only
                    && self.read_outcome == ControlReadOutcomeV1::RollbackDetected
                    && self.result.control_decision == ControlDecisionV1::DenyRollback
                    && !self.result.next_action_allowed
                    && self.result.terminal_hard_lock
            }
            ControlSnapshotStateV1::DenyUnknownTerminalHardLock => {
                !self.test_only
                    && self.read_outcome == ControlReadOutcomeV1::ReadUnknown
                    && self.result.control_decision == ControlDecisionV1::DenyUnknown
                    && !self.result.next_action_allowed
                    && self.result.terminal_hard_lock
            }
        };
        if !state_valid {
            return Err(aligned_error(
                "s20b_aligned_control_state",
                "control state and fail-closed decision matrix are inconsistent",
            ));
        }
        Ok(())
    }
}

#[must_use]
struct ValidatedControlSnapshotTokenV1 {
    digest: SecurityDigestV1,
    phase: ControlPhaseV2,
    snapshot_state: ControlSnapshotStateV1,
    stop_state: StopReadStateV1,
    revocation_state: RevocationReadStateV1,
    authorization_binding: AuthorizationBindingV1,
    run_binding: ControlRunBindingV1,
    assignment_binding: ControlAssignmentBindingV1,
    database_content_root_sha256: SecurityDigestV1,
    external_checkpoint_receipt_sha256: SecurityDigestV1,
    claim_revision: Option<u64>,
    stop_revision: Option<u64>,
    revocation_revision: Option<u64>,
    transaction_sequence: u64,
}

fn parse_control_packet_v1(raw: &[u8]) -> AuthorizationResult<ControlSnapshotPacketV1> {
    deserialize_closed_v1(raw)
}

fn build_control_packet_v1(
    mut packet: ControlSnapshotPacketV1,
    committed: &ValidatedCommittedDatabaseStateV1,
) -> AuthorizationResult<CanonicalBuiltPacketV1> {
    if packet.test_only || packet.synthetic {
        return Err(aligned_error(
            "s20b_aligned_production_synthetic",
            "production builder cannot accept a synthetic control packet",
        ));
    }
    packet.validate_shape_v1()?;
    packet.ledger_binding.validate_committed_state(committed)?;
    let digest = recompute_top_level_self_v1(&packet, CONTROL_SELF_KEY_V1, CONTROL_DOMAIN_V1)?;
    packet.control_snapshot_sha256 = digest;
    Ok(CanonicalBuiltPacketV1 {
        canonical_bytes: serialize_canonical_v1(&packet)?,
        digest,
    })
}

fn validate_control_packet_v1(
    raw: &[u8],
    context: &ValidatedPreflightContextTokenV1,
    committed: &ValidatedCommittedDatabaseStateV1,
    assignments: &ValidatedAuthorizedAssignmentSetV1,
    member: &ValidatedAuthorizedAssignmentMemberV1,
) -> AuthorizationResult<ValidatedControlSnapshotTokenV1> {
    let packet = parse_control_packet_v1(raw)?;
    packet.validate_shape_v1()?;
    if packet.test_only || packet.synthetic {
        return Err(aligned_error(
            "s20b_aligned_production_synthetic",
            "production validator cannot accept a synthetic control packet",
        ));
    }
    packet.ledger_binding.validate_committed_state(committed)?;
    if packet.snapshot_phase != ControlPhaseV2::PreflightBeforeClaim
        || packet.phase_parent.parent_sha256 != context.digest
        || packet.authorization_binding != context.authorization_binding
        || packet.run_binding.attempt_id_sha256 != context.run_binding.attempt_id_sha256
        || packet.run_binding.capability_nonce_sha256 != context.run_binding.capability_nonce_sha256
        || packet.run_binding.claim_key_sha256 != context.run_binding.claim_key_sha256
        || packet.run_binding.claim_namespace_sha256 != context.run_binding.claim_namespace_sha256
        || packet.run_binding.controller_binary_sha256
            != context.run_binding.controller_binary_sha256
        || packet.run_binding.run_assignment_id_sha256
            != context.run_binding.run_assignment_id_sha256
        || packet.run_binding.run_id_sha256 != context.run_binding.run_id_sha256
        || packet.run_binding.runner_binary_sha256 != context.run_binding.runner_binary_sha256
        || packet.assignment_binding.assignment_set_sha256.bytes()
            != &assignments.assignment_set_sha256
        || packet.assignment_binding.schedule_sha256.bytes() != &assignments.schedule_sha256
        || packet.assignment_binding.assignment_record_sha256.bytes()
            != &member.assignment_record_sha256
        || packet
            .assignment_binding
            .operation_descriptor_set_sha256
            .bytes()
            != &member.operation_set_sha256
    {
        return Err(aligned_error(
            "s20b_aligned_control_parent",
            "control parent or immutable authority/run/assignment binding drifted",
        ));
    }
    let digest = recompute_top_level_self_v1(&packet, CONTROL_SELF_KEY_V1, CONTROL_DOMAIN_V1)?;
    if digest != packet.control_snapshot_sha256 {
        return Err(aligned_error(
            "s20b_aligned_control_self",
            "control self digest does not recompute",
        ));
    }
    Ok(ValidatedControlSnapshotTokenV1 {
        digest,
        phase: packet.snapshot_phase,
        snapshot_state: packet.snapshot_state,
        stop_state: packet.stop_view.read_state,
        revocation_state: packet.revocation_view.read_state,
        authorization_binding: packet.authorization_binding,
        run_binding: packet.run_binding,
        assignment_binding: packet.assignment_binding,
        database_content_root_sha256: packet.ledger_binding.database_content_root_sha256,
        external_checkpoint_receipt_sha256: packet
            .ledger_binding
            .external_checkpoint_receipt_sha256,
        claim_revision: packet.claim_view.revision,
        stop_revision: packet.stop_view.ledger_revision,
        revocation_revision: packet.revocation_view.ledger_revision,
        transaction_sequence: packet.ledger_binding.transaction_sequence,
    })
}

fn validate_final_preflight_v1(
    raw: &[u8],
    authorized: &AuthorizedUnclaimedS19SubjectV1,
    observations: &ValidatedPreflightObservationFactsV1,
    committed: &ValidatedCommittedDatabaseStateV1,
    assignments: &ValidatedAuthorizedAssignmentSetV1,
    member: &ValidatedAuthorizedAssignmentMemberV1,
    control: &ValidatedControlSnapshotTokenV1,
) -> AuthorizationResult<ValidatedPreflightReceiptTokenV1> {
    let packet = parse_preflight_packet_v1(raw)?;
    let context = validate_preflight_context_v1(
        &packet,
        authorized,
        observations,
        committed,
        assignments,
        member,
    )?;
    if control.phase != ControlPhaseV2::PreflightBeforeClaim
        || packet.phase_bindings.control_snapshot_sha256 != control.digest
        || packet.authorization_binding.common() != control.authorization_binding
        || packet.run_binding.attempt_id_sha256 != control.run_binding.attempt_id_sha256
        || packet.run_binding.capability_nonce_sha256 != control.run_binding.capability_nonce_sha256
        || packet.run_binding.claim_key_sha256 != control.run_binding.claim_key_sha256
        || packet.run_binding.claim_namespace_sha256 != control.run_binding.claim_namespace_sha256
        || packet.run_binding.controller_binary_sha256
            != control.run_binding.controller_binary_sha256
        || packet.run_binding.run_assignment_id_sha256
            != control.run_binding.run_assignment_id_sha256
        || packet.run_binding.run_id_sha256 != control.run_binding.run_id_sha256
        || packet.run_binding.runner_binary_sha256 != control.run_binding.runner_binary_sha256
        || packet.assignment_binding.assignment_set_sha256
            != control.assignment_binding.assignment_set_sha256
        || packet.assignment_binding.schedule_sha256 != control.assignment_binding.schedule_sha256
        || packet.assignment_binding.assignment_record_sha256
            != control.assignment_binding.assignment_record_sha256
        || packet.assignment_binding.operation_descriptor_set_sha256
            != control.assignment_binding.operation_descriptor_set_sha256
    {
        return Err(aligned_error(
            "s20b_aligned_preflight_control_parent",
            "final preflight does not bind the validated preflight-phase control snapshot",
        ));
    }
    let digest = recompute_top_level_self_v1(&packet, PREFLIGHT_SELF_KEY_V1, PREFLIGHT_DOMAIN_V1)?;
    if digest != packet.preflight_receipt_sha256 {
        return Err(aligned_error(
            "s20b_aligned_preflight_self",
            "preflight self digest does not recompute",
        ));
    }
    Ok(ValidatedPreflightReceiptTokenV1 {
        digest,
        context_digest: context.digest,
        control_digest: control.digest,
        authorization_binding: packet.authorization_binding.common(),
        run_binding: packet.run_binding,
        assignment_binding: packet.assignment_binding,
    })
}

fn build_final_preflight_v1(
    mut packet: PreflightReceiptPacketV1,
    authorized: &AuthorizedUnclaimedS19SubjectV1,
    observations: &ValidatedPreflightObservationFactsV1,
    committed: &ValidatedCommittedDatabaseStateV1,
    assignments: &ValidatedAuthorizedAssignmentSetV1,
    member: &ValidatedAuthorizedAssignmentMemberV1,
    control: &ValidatedControlSnapshotTokenV1,
) -> AuthorizationResult<CanonicalBuiltPacketV1> {
    if packet.test_only || packet.synthetic {
        return Err(aligned_error(
            "s20b_aligned_production_synthetic",
            "production builder cannot accept a synthetic preflight packet",
        ));
    }
    packet
        .assignment_binding
        .validate_authority(assignments, member)?;
    if packet.run_binding.run_assignment_id_sha256.bytes() != &member.assignment_id_sha256
        || control.phase != ControlPhaseV2::PreflightBeforeClaim
    {
        return Err(aligned_error(
            "s20b_aligned_preflight_authority",
            "preflight assignment or control phase is not owner-bound",
        ));
    }
    packet.phase_bindings.control_snapshot_sha256 = control.digest;
    let built = build_preflight_packet_v1(packet)?;
    let parsed = parse_preflight_packet_v1(&built.canonical_bytes)?;
    let _ = validate_preflight_context_v1(
        &parsed,
        authorized,
        observations,
        committed,
        assignments,
        member,
    )?;
    Ok(built)
}

fn validate_cas_control_packet_v1(
    raw: &[u8],
    preflight: &ValidatedPreflightReceiptTokenV1,
    committed: &ValidatedCommittedDatabaseStateV1,
    assignments: &ValidatedAuthorizedAssignmentSetV1,
    member: &ValidatedAuthorizedAssignmentMemberV1,
) -> AuthorizationResult<ValidatedControlSnapshotTokenV1> {
    let packet = parse_control_packet_v1(raw)?;
    packet.validate_shape_v1()?;
    packet.ledger_binding.validate_committed_state(committed)?;
    if packet.test_only
        || packet.synthetic
        || packet.snapshot_phase != ControlPhaseV2::CasLinearization
        || packet.phase_parent.parent_sha256 != preflight.digest
        || packet.authorization_binding != preflight.authorization_binding
        || packet.run_binding.attempt_id_sha256 != preflight.run_binding.attempt_id_sha256
        || packet.run_binding.capability_nonce_sha256
            != preflight.run_binding.capability_nonce_sha256
        || packet.run_binding.claim_key_sha256 != preflight.run_binding.claim_key_sha256
        || packet.run_binding.claim_namespace_sha256 != preflight.run_binding.claim_namespace_sha256
        || packet.run_binding.controller_binary_sha256
            != preflight.run_binding.controller_binary_sha256
        || packet.run_binding.run_assignment_id_sha256
            != preflight.run_binding.run_assignment_id_sha256
        || packet.run_binding.run_id_sha256 != preflight.run_binding.run_id_sha256
        || packet.run_binding.runner_binary_sha256 != preflight.run_binding.runner_binary_sha256
        || packet.assignment_binding.assignment_set_sha256.bytes()
            != &assignments.assignment_set_sha256
        || packet.assignment_binding.schedule_sha256.bytes() != &assignments.schedule_sha256
        || packet.assignment_binding.assignment_record_sha256.bytes()
            != &member.assignment_record_sha256
        || packet
            .assignment_binding
            .operation_descriptor_set_sha256
            .bytes()
            != &member.operation_set_sha256
        || packet.claim_view.state != Some(ClaimRowStateV1::AuthorizedUnclaimed)
        || packet.claim_view.revision != Some(preflight.run_binding.expected_unclaimed_revision)
        || packet.stop_view.read_state != StopReadStateV1::Clear
        || packet.revocation_view.read_state != RevocationReadStateV1::Exact
    {
        return Err(aligned_error(
            "s20b_aligned_cas_control",
            "CAS-linearization control is not an exact backward-bound clear/exact snapshot",
        ));
    }
    let digest = recompute_top_level_self_v1(&packet, CONTROL_SELF_KEY_V1, CONTROL_DOMAIN_V1)?;
    if digest != packet.control_snapshot_sha256 {
        return Err(aligned_error(
            "s20b_aligned_control_self",
            "CAS control self digest does not recompute",
        ));
    }
    Ok(ValidatedControlSnapshotTokenV1 {
        digest,
        phase: packet.snapshot_phase,
        snapshot_state: packet.snapshot_state,
        stop_state: packet.stop_view.read_state,
        revocation_state: packet.revocation_view.read_state,
        authorization_binding: packet.authorization_binding,
        run_binding: packet.run_binding,
        assignment_binding: packet.assignment_binding,
        database_content_root_sha256: packet.ledger_binding.database_content_root_sha256,
        external_checkpoint_receipt_sha256: packet
            .ledger_binding
            .external_checkpoint_receipt_sha256,
        claim_revision: packet.claim_view.revision,
        stop_revision: packet.stop_view.ledger_revision,
        revocation_revision: packet.revocation_view.ledger_revision,
        transaction_sequence: packet.ledger_binding.transaction_sequence,
    })
}

#[derive(Clone, Copy, Debug, Eq, PartialEq, Serialize, Deserialize)]
enum ClaimPacketKindV2 {
    #[serde(rename = "S20B_AUTHORIZATION_REGISTRATION_RECEIPT")]
    AuthorizationRegistrationReceipt,
    #[serde(rename = "S20B_AUTHORITY_CONTROL_LEDGER_ROW")]
    AuthorityControlLedgerRow,
    #[serde(rename = "S20B_SINGLE_USE_CLAIM_OUTCOME_RECEIPT")]
    SingleUseClaimOutcomeReceipt,
}

impl ClaimPacketKindV2 {
    fn domain(self) -> &'static [u8] {
        match self {
            Self::AuthorizationRegistrationReceipt => CLAIM_REGISTRATION_DOMAIN_V1,
            Self::AuthorityControlLedgerRow => CLAIM_LEDGER_ROW_DOMAIN_V1,
            Self::SingleUseClaimOutcomeReceipt => CLAIM_OUTCOME_DOMAIN_V1,
        }
    }
}

#[derive(Clone, Copy, Debug, Eq, PartialEq, Serialize, Deserialize)]
enum ClaimPacketStateV2 {
    #[serde(rename = "SYNTHETIC_KAT_NON_LIVE_CLAIM_PACKET")]
    SyntheticKatNonLive,
    #[serde(rename = "REGISTERED_COMMITTED")]
    RegisteredCommitted,
    #[serde(rename = "LEDGER_AUTHORIZED_UNCLAIMED")]
    LedgerAuthorizedUnclaimed,
    #[serde(rename = "LEDGER_CONSUMED_FOR_EXACT_RUN")]
    LedgerConsumedForExactRun,
    #[serde(rename = "KNOWN_NOT_COMMITTED_TERMINAL")]
    KnownNotCommittedTerminal,
    #[serde(rename = "COMMITTED_PERMIT_ISSUED")]
    CommittedPermitIssued,
    #[serde(rename = "COMMITTED_PRE_PERMIT_CRASH_TERMINAL")]
    CommittedPrePermitCrashTerminal,
    #[serde(rename = "UNKNOWN_OUTCOME_TERMINAL_HARD_LOCK")]
    UnknownOutcomeTerminalHardLock,
}

#[derive(Clone, Debug, Eq, PartialEq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
struct ClaimKeyBindingV1 {
    claim_key_sha256: SecurityDigestV1,
    claim_namespace_sha256: SecurityDigestV1,
    expected_unclaimed_revision: u64,
    maximum_successful_claims: u64,
}

#[derive(Clone, Debug, Eq, PartialEq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
struct ClaimAssignmentBindingV1 {
    assignment_record_sha256: SecurityDigestV1,
    assignment_set_sha256: SecurityDigestV1,
    membership_profile: String,
    operation_descriptor_set_sha256: SecurityDigestV1,
    schedule_sha256: SecurityDigestV1,
}

impl ClaimAssignmentBindingV1 {
    fn validate_authority(
        &self,
        set: &ValidatedAuthorizedAssignmentSetV1,
        member: &ValidatedAuthorizedAssignmentMemberV1,
    ) -> AuthorizationResult<()> {
        if self.assignment_set_sha256.bytes() != &set.assignment_set_sha256
            || self.schedule_sha256.bytes() != &set.schedule_sha256
            || self.assignment_record_sha256.bytes() != &member.assignment_record_sha256
            || self.operation_descriptor_set_sha256.bytes() != &member.operation_set_sha256
            || self.membership_profile != ASSIGNMENT_MEMBERSHIP_PROFILE_V1
        {
            return Err(aligned_error(
                "s20b_aligned_claim_assignment",
                "claim assignment binding does not match owner-bound assignment evidence",
            ));
        }
        Ok(())
    }
}

#[derive(Clone, Debug, Eq, PartialEq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
struct ClaimRegistrationV1 {
    database_content_root_sha256: SecurityDigestV1,
    durable_commit_completed: bool,
    external_checkpoint_receipt_sha256: SecurityDigestV1,
    initial_row_revision: u64,
    initial_row_state: String,
    registered_by_independent_authority_control_plane: bool,
    registration_nonce_sha256: SecurityDigestV1,
    row_core_sha256: SecurityDigestV1,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq, Serialize, Deserialize)]
enum LedgerRowStateV1 {
    #[serde(rename = "AUTHORIZED_UNCLAIMED")]
    AuthorizedUnclaimed,
    #[serde(rename = "CONSUMED_FOR_EXACT_RUN")]
    ConsumedForExactRun,
}

#[derive(Clone, Debug, Eq, PartialEq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
struct ClaimLedgerRowV1 {
    consumed_capability_nonce_sha256: Option<SecurityDigestV1>,
    consumed_run_id_sha256: Option<SecurityDigestV1>,
    consumed_tombstone_absorbing: bool,
    database_content_root_sha256: SecurityDigestV1,
    row_revision: u64,
    row_state: LedgerRowStateV1,
    successful_claim_count: u64,
    transition_core_sha256: SecurityDigestV1,
}

impl ClaimLedgerRowV1 {
    fn validate(&self) -> AuthorizationResult<()> {
        require_nonzero_u64(self.row_revision, "s20b_aligned_ledger_revision")?;
        let valid = self.consumed_tombstone_absorbing
            && match self.row_state {
                LedgerRowStateV1::AuthorizedUnclaimed => {
                    self.successful_claim_count == 0
                        && self.consumed_run_id_sha256.is_none()
                        && self.consumed_capability_nonce_sha256.is_none()
                }
                LedgerRowStateV1::ConsumedForExactRun => {
                    self.successful_claim_count == 1
                        && self.consumed_run_id_sha256.is_some()
                        && self.consumed_capability_nonce_sha256.is_some()
                }
            };
        if !valid {
            return Err(aligned_error(
                "s20b_aligned_ledger_row_state",
                "ledger-row tag, count, or consumed bindings are inconsistent",
            ));
        }
        Ok(())
    }
}

/// Exact SQL binding order.  Scalars remain scalars; digests are never hidden
/// in a homogeneous caller-provided vector.
#[derive(Clone, Debug, Eq, PartialEq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
struct CasParameterBindingsV1 {
    p01_next_revision: u64,
    p02_run_id_sha256: SecurityDigestV1,
    p03_controller_binary_sha256: SecurityDigestV1,
    p04_preflight_receipt_sha256: SecurityDigestV1,
    p05_control_snapshot_sha256: SecurityDigestV1,
    p06_claim_transition_core_sha256: SecurityDigestV1,
    p07_authorization_id_sha256: SecurityDigestV1,
    p08_claim_namespace_sha256: SecurityDigestV1,
    p09_claim_key_sha256: SecurityDigestV1,
    p10_signed_payload_sha256: SecurityDigestV1,
    p11_subject_manifest_sha256: SecurityDigestV1,
    p12_resource_scope_sha256: SecurityDigestV1,
    p13_signed_revocation_epoch: u64,
    p14_expected_unclaimed_revision: u64,
    p15_runner_binary_sha256: SecurityDigestV1,
    p16_capability_nonce_sha256: SecurityDigestV1,
    p17_control_ledger_identity_sha256: SecurityDigestV1,
    p18_anti_rollback_policy_sha256: SecurityDigestV1,
    p19_stop_revision: u64,
    p20_revocation_revision: u64,
    p21_stop_policy_identity_sha256: SecurityDigestV1,
    p22_revocation_policy_identity_sha256: SecurityDigestV1,
    p23_sqlite_profile_sha256: SecurityDigestV1,
    p24_sqlite_schema_sha256: SecurityDigestV1,
    parameter_order_profile: String,
}

impl CasParameterBindingsV1 {
    fn transition_core_v1(&self) -> AuthorizationResult<SecurityDigestV1> {
        // Exactly 24 U64-length frames follow the U32 domain frame: the
        // profile, then p01..p24 in numeric order with p06 omitted.  The five
        // scalar SQL parameters are U64BE; digest parameters are raw 32-byte
        // values.  The final claim self digest is not a member of this type.
        let fields: Vec<Vec<u8>> = vec![
            self.parameter_order_profile.as_bytes().to_vec(),
            self.p01_next_revision.to_be_bytes().to_vec(),
            self.p02_run_id_sha256.bytes().to_vec(),
            self.p03_controller_binary_sha256.bytes().to_vec(),
            self.p04_preflight_receipt_sha256.bytes().to_vec(),
            self.p05_control_snapshot_sha256.bytes().to_vec(),
            self.p07_authorization_id_sha256.bytes().to_vec(),
            self.p08_claim_namespace_sha256.bytes().to_vec(),
            self.p09_claim_key_sha256.bytes().to_vec(),
            self.p10_signed_payload_sha256.bytes().to_vec(),
            self.p11_subject_manifest_sha256.bytes().to_vec(),
            self.p12_resource_scope_sha256.bytes().to_vec(),
            self.p13_signed_revocation_epoch.to_be_bytes().to_vec(),
            self.p14_expected_unclaimed_revision.to_be_bytes().to_vec(),
            self.p15_runner_binary_sha256.bytes().to_vec(),
            self.p16_capability_nonce_sha256.bytes().to_vec(),
            self.p17_control_ledger_identity_sha256.bytes().to_vec(),
            self.p18_anti_rollback_policy_sha256.bytes().to_vec(),
            self.p19_stop_revision.to_be_bytes().to_vec(),
            self.p20_revocation_revision.to_be_bytes().to_vec(),
            self.p21_stop_policy_identity_sha256.bytes().to_vec(),
            self.p22_revocation_policy_identity_sha256.bytes().to_vec(),
            self.p23_sqlite_profile_sha256.bytes().to_vec(),
            self.p24_sqlite_schema_sha256.bytes().to_vec(),
        ];
        if fields.len() != 24 {
            return Err(aligned_error(
                "s20b_aligned_cas_frame_count",
                "claim transition core must contain exactly 24 framed fields",
            ));
        }
        let refs: Vec<&[u8]> = fields.iter().map(Vec::as_slice).collect();
        SecurityDigestV1::from_array(framed_digest(CLAIM_TRANSITION_CORE_DOMAIN_V1, &refs)?)
    }

    fn validate_core_v1(&self) -> AuthorizationResult<()> {
        for value in [
            self.p01_next_revision,
            self.p13_signed_revocation_epoch,
            self.p14_expected_unclaimed_revision,
            self.p19_stop_revision,
            self.p20_revocation_revision,
        ] {
            require_nonzero_u64(value, "s20b_aligned_cas_scalar")?;
        }
        if self.parameter_order_profile != CAS_PARAMETER_ORDER_PROFILE_V1
            || self.p01_next_revision
                != self
                    .p14_expected_unclaimed_revision
                    .checked_add(1)
                    .ok_or_else(|| {
                        aligned_error(
                            "s20b_aligned_cas_revision",
                            "expected revision cannot advance without overflow",
                        )
                    })?
            || self.transition_core_v1()? != self.p06_claim_transition_core_sha256
        {
            return Err(aligned_error(
                "s20b_aligned_cas_core",
                "CAS order profile, next-revision relation, or transition core drifted",
            ));
        }
        Ok(())
    }
}

#[derive(Clone, Debug, Eq, PartialEq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
struct ClaimAttemptV1 {
    assignment_record_sha256: SecurityDigestV1,
    attempt_id_sha256: SecurityDigestV1,
    attempt_tombstone_sha256: SecurityDigestV1,
    cas_parameter_bindings: CasParameterBindingsV1,
    claim_opportunity_burn_receipt_sha256: SecurityDigestV1,
    operation_descriptor_set_sha256: SecurityDigestV1,
    pre_database_content_root_sha256: SecurityDigestV1,
    run_assignment_id_sha256: SecurityDigestV1,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq, Serialize, Deserialize)]
enum SameTransactionClaimReadV1 {
    #[serde(rename = "AUTHORIZED_UNCLAIMED")]
    AuthorizedUnclaimed,
    #[serde(rename = "ROW_MISSING")]
    RowMissing,
    #[serde(rename = "ALREADY_CONSUMED")]
    AlreadyConsumed,
    #[serde(rename = "READ_UNKNOWN")]
    ReadUnknown,
}

#[derive(Clone, Debug, Eq, PartialEq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
struct SameTransactionControlV1 {
    cas_and_control_reads_same_sqlite_transaction: bool,
    claim_row_read_state: SameTransactionClaimReadV1,
    database_identity_sha256: SecurityDigestV1,
    revocation_read_state: RevocationReadStateV1,
    rollback_detected: Option<bool>,
    stop_read_state: StopReadStateV1,
    transaction_sequence: u64,
}

impl SameTransactionControlV1 {
    fn validate(&self) -> AuthorizationResult<()> {
        require_nonzero_u64(
            self.transaction_sequence,
            "s20b_aligned_claim_transaction_sequence",
        )?;
        let rollback_valid = match self.revocation_read_state {
            RevocationReadStateV1::RollbackDetected => self.rollback_detected == Some(true),
            RevocationReadStateV1::ReadUnknown => self.rollback_detected.is_none(),
            RevocationReadStateV1::Exact | RevocationReadStateV1::Mismatch => {
                self.rollback_detected == Some(false)
            }
        };
        if !self.cas_and_control_reads_same_sqlite_transaction || !rollback_valid {
            return Err(aligned_error(
                "s20b_aligned_same_transaction",
                "CAS/control transaction or rollback tag is inconsistent",
            ));
        }
        Ok(())
    }
}

#[derive(Clone, Copy, Debug, Eq, PartialEq, Serialize, Deserialize)]
enum CommitAcknowledgementV1 {
    #[serde(rename = "NOT_ATTEMPTED")]
    NotAttempted,
    #[serde(rename = "KNOWN_NOT_COMMITTED")]
    KnownNotCommitted,
    #[serde(rename = "COMMITTED")]
    Committed,
    #[serde(rename = "UNKNOWN")]
    Unknown,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq, Serialize, Deserialize)]
enum RowMutationStateV1 {
    #[serde(rename = "NOT_ATTEMPTED")]
    NotAttempted,
    #[serde(rename = "UNCHANGED_AUTHORIZED_UNCLAIMED")]
    UnchangedAuthorizedUnclaimed,
    #[serde(rename = "CONSUMED_FOR_EXACT_RUN")]
    ConsumedForExactRun,
    #[serde(rename = "UNKNOWN")]
    Unknown,
}

#[derive(Clone, Debug, Eq, PartialEq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
struct CommitOutcomeV1 {
    acknowledgement_state: CommitAcknowledgementV1,
    affected_rows: Option<u64>,
    external_checkpoint_receipt_sha256: Option<SecurityDigestV1>,
    post_database_content_root_sha256: Option<SecurityDigestV1>,
    row_mutation_state: RowMutationStateV1,
    terminal_hard_lock: bool,
}

#[derive(Clone, Debug, Eq, PartialEq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
struct PermitOutcomeV1 {
    affine_permit_cloneable: bool,
    affine_permit_serializable: bool,
    automatic_retry_allowed: bool,
    permit_eligible_after_commit: bool,
    process_local_affine_permit_issued: bool,
}

#[derive(Clone, Debug, Eq, PartialEq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
struct ClaimParentBindingsV1 {
    attempt_tombstone_sha256: Option<SecurityDigestV1>,
    control_snapshot_sha256: Option<SecurityDigestV1>,
    parent_graph_profile: String,
    pre_database_content_root_sha256: Option<SecurityDigestV1>,
    preflight_receipt_sha256: Option<SecurityDigestV1>,
    registration_receipt_sha256: Option<SecurityDigestV1>,
}

#[derive(Clone, Debug, Eq, PartialEq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
struct ClaimNonclaimsV1 {
    packet_is_bearer_capability: bool,
    packet_is_owner_authority: bool,
    packet_permits_automatic_retry: bool,
    provider_or_production_authority: bool,
    schema_conformance_authorizes_live_execution: bool,
    side_effects_unlocked: String,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
struct AuthorityControlClaimPacketV1 {
    assignment_binding: ClaimAssignmentBindingV1,
    authorization_binding: AuthorizationBindingV1,
    canonicalization: String,
    claim_attempt: Option<ClaimAttemptV1>,
    claim_key_binding: ClaimKeyBindingV1,
    claim_packet_sha256: SecurityDigestV1,
    claim_packet_state: ClaimPacketStateV2,
    commit_outcome: Option<CommitOutcomeV1>,
    hashing_contract: HashingContractV1,
    ledger_row: Option<ClaimLedgerRowV1>,
    nonclaims: ClaimNonclaimsV1,
    packet_kind: ClaimPacketKindV2,
    parent_bindings: ClaimParentBindingsV1,
    permit_outcome: Option<PermitOutcomeV1>,
    registration: Option<ClaimRegistrationV1>,
    same_transaction_control: Option<SameTransactionControlV1>,
    schema: String,
    semantic_validation: SemanticValidationV1,
    synthetic: bool,
    test_only: bool,
}

const CLAIM_RULES_V1: [&str; 8] = [
    "PACKET_VARIANT_AND_DIGEST_DOMAIN_EXACT",
    "ALL_24_CAS_PARAMETERS_RECOMPUTED_IN_DECLARED_ORDER",
    "AUTHORIZATION_ASSIGNMENT_OPERATION_PREFLIGHT_AND_CONTROL_BINDINGS_EXACT",
    "CLAIM_TRANSITION_CORE_EXCLUDES_FINAL_CLAIM_SELF_DIGEST",
    "DATABASE_CONTENT_ROOT_RECOMPUTED_FROM_ORDERED_ROW_CORES",
    "UNKNOWN_COMMIT_HAS_NULL_AFFECTED_ROWS_AND_UNKNOWN_MUTATION",
    "COMMITTED_ROW_DISTINCT_FROM_PROCESS_LOCAL_PERMIT_ISSUANCE",
    "EVERY_NON_SUCCESS_OR_CRASH_STATE_FORBIDS_RETRY",
];

impl AuthorityControlClaimPacketV1 {
    fn validate_shape_v1(&self) -> AuthorizationResult<()> {
        self.hashing_contract.validate(
            self.packet_kind.domain(),
            CLAIM_SCOPE_V1,
            CLAIM_SELF_KEY_V1,
        )?;
        self.semantic_validation.validate(&CLAIM_RULES_V1)?;
        self.authorization_binding.validate()?;
        for value in [
            self.claim_key_binding.expected_unclaimed_revision,
            self.claim_key_binding.maximum_successful_claims,
        ] {
            require_nonzero_u64(value, "s20b_aligned_claim_key_counter")?;
        }
        if self.schema != CLAIM_SCHEMA_V1
            || self.canonicalization != CANONICALIZATION_V1
            || self.test_only != self.synthetic
            || self.claim_key_binding.maximum_successful_claims != 1
            || self.assignment_binding.membership_profile != ASSIGNMENT_MEMBERSHIP_PROFILE_V1
            || self.parent_bindings.parent_graph_profile
                != "BACKWARD_ONLY_NO_FINAL_CLAIM_DIGEST_IN_REFERENCED_CONTENT_ROOT"
            || self.nonclaims.packet_is_bearer_capability
            || self.nonclaims.packet_is_owner_authority
            || self.nonclaims.packet_permits_automatic_retry
            || self.nonclaims.provider_or_production_authority
            || self.nonclaims.schema_conformance_authorizes_live_execution
            || self.nonclaims.side_effects_unlocked != "NONE"
        {
            return Err(aligned_error(
                "s20b_aligned_claim_shape",
                "claim schema constant, one-shot policy, parent profile, or nonclaim drifted",
            ));
        }
        let body_valid = match self.packet_kind {
            ClaimPacketKindV2::AuthorizationRegistrationReceipt => {
                self.registration.is_some()
                    && self.ledger_row.is_none()
                    && self.claim_attempt.is_none()
                    && self.same_transaction_control.is_none()
                    && self.commit_outcome.is_none()
                    && self.permit_outcome.is_none()
            }
            ClaimPacketKindV2::AuthorityControlLedgerRow => {
                self.registration.is_none()
                    && self.ledger_row.is_some()
                    && self.claim_attempt.is_none()
                    && self.same_transaction_control.is_none()
                    && self.commit_outcome.is_none()
                    && self.permit_outcome.is_none()
            }
            ClaimPacketKindV2::SingleUseClaimOutcomeReceipt => {
                self.registration.is_none()
                    && self.ledger_row.is_none()
                    && self.claim_attempt.is_some()
                    && self.same_transaction_control.is_some()
                    && self.commit_outcome.is_some()
                    && self.permit_outcome.is_some()
            }
        };
        if !body_valid {
            return Err(aligned_error(
                "s20b_aligned_claim_variant",
                "claim variant and nullable phase bodies are inconsistent",
            ));
        }
        if let Some(registration) = &self.registration {
            if registration.initial_row_state != "AUTHORIZED_UNCLAIMED"
                || registration.initial_row_revision == 0
                || !registration.registered_by_independent_authority_control_plane
                || !registration.durable_commit_completed
            {
                return Err(aligned_error(
                    "s20b_aligned_registration_state",
                    "registration packet is not a committed independent unclaimed registration",
                ));
            }
        }
        if let Some(row) = &self.ledger_row {
            row.validate()?;
        }
        if let Some(attempt) = &self.claim_attempt {
            attempt.cas_parameter_bindings.validate_core_v1()?;
            if attempt
                .cas_parameter_bindings
                .p06_claim_transition_core_sha256
                == self.claim_packet_sha256
            {
                return Err(aligned_error(
                    "s20b_aligned_claim_cycle",
                    "transition core must exclude and differ from the final claim self digest",
                ));
            }
        }
        if let Some(control) = &self.same_transaction_control {
            control.validate()?;
        }
        if let Some(outcome) = &self.commit_outcome {
            if outcome.affected_rows.is_some_and(|rows| rows > 1) {
                return Err(aligned_error(
                    "s20b_aligned_affected_rows",
                    "claim affected-row count must be zero, one, or unknown",
                ));
            }
        }
        if let Some(permit) = &self.permit_outcome {
            if permit.affine_permit_cloneable
                || permit.affine_permit_serializable
                || permit.automatic_retry_allowed
            {
                return Err(aligned_error(
                    "s20b_aligned_permit_noncapability",
                    "affine permit cannot be cloneable, serializable, or automatically retried",
                ));
            }
        }
        if !self.validate_state_matrix_v1()? {
            return Err(aligned_error(
                "s20b_aligned_claim_state",
                "claim packet kind, state, commit acknowledgement, mutation, or permit drifted",
            ));
        }
        Ok(())
    }

    fn validate_state_matrix_v1(&self) -> AuthorizationResult<bool> {
        let result = match self.claim_packet_state {
            ClaimPacketStateV2::SyntheticKatNonLive => {
                let (commit, permit) = self.outcome_pair_v1()?;
                self.test_only
                    && self.synthetic
                    && self.packet_kind == ClaimPacketKindV2::SingleUseClaimOutcomeReceipt
                    && commit.acknowledgement_state == CommitAcknowledgementV1::NotAttempted
                    && commit.affected_rows == Some(0)
                    && commit.row_mutation_state == RowMutationStateV1::NotAttempted
                    && commit.post_database_content_root_sha256.is_none()
                    && commit.external_checkpoint_receipt_sha256.is_none()
                    && commit.terminal_hard_lock
                    && !permit.permit_eligible_after_commit
                    && !permit.process_local_affine_permit_issued
            }
            ClaimPacketStateV2::RegisteredCommitted => {
                !self.test_only
                    && self.packet_kind == ClaimPacketKindV2::AuthorizationRegistrationReceipt
            }
            ClaimPacketStateV2::LedgerAuthorizedUnclaimed => {
                !self.test_only
                    && self.packet_kind == ClaimPacketKindV2::AuthorityControlLedgerRow
                    && self
                        .ledger_row
                        .as_ref()
                        .is_some_and(|row| row.row_state == LedgerRowStateV1::AuthorizedUnclaimed)
            }
            ClaimPacketStateV2::LedgerConsumedForExactRun => {
                !self.test_only
                    && self.packet_kind == ClaimPacketKindV2::AuthorityControlLedgerRow
                    && self
                        .ledger_row
                        .as_ref()
                        .is_some_and(|row| row.row_state == LedgerRowStateV1::ConsumedForExactRun)
            }
            ClaimPacketStateV2::KnownNotCommittedTerminal => {
                let (commit, permit) = self.outcome_pair_v1()?;
                !self.test_only
                    && self.packet_kind == ClaimPacketKindV2::SingleUseClaimOutcomeReceipt
                    && commit.acknowledgement_state == CommitAcknowledgementV1::KnownNotCommitted
                    && commit.affected_rows == Some(0)
                    && commit.row_mutation_state == RowMutationStateV1::UnchangedAuthorizedUnclaimed
                    && commit.post_database_content_root_sha256.is_none()
                    && commit.external_checkpoint_receipt_sha256.is_none()
                    && commit.terminal_hard_lock
                    && !permit.permit_eligible_after_commit
                    && !permit.process_local_affine_permit_issued
            }
            ClaimPacketStateV2::CommittedPermitIssued => {
                let (commit, permit) = self.outcome_pair_v1()?;
                !self.test_only
                    && self.packet_kind == ClaimPacketKindV2::SingleUseClaimOutcomeReceipt
                    && commit.acknowledgement_state == CommitAcknowledgementV1::Committed
                    && commit.affected_rows == Some(1)
                    && commit.row_mutation_state == RowMutationStateV1::ConsumedForExactRun
                    && commit.post_database_content_root_sha256.is_some()
                    && commit.external_checkpoint_receipt_sha256.is_some()
                    && !commit.terminal_hard_lock
                    && permit.permit_eligible_after_commit
                    && permit.process_local_affine_permit_issued
            }
            ClaimPacketStateV2::CommittedPrePermitCrashTerminal => {
                let (commit, permit) = self.outcome_pair_v1()?;
                !self.test_only
                    && self.packet_kind == ClaimPacketKindV2::SingleUseClaimOutcomeReceipt
                    && commit.acknowledgement_state == CommitAcknowledgementV1::Committed
                    && commit.affected_rows == Some(1)
                    && commit.row_mutation_state == RowMutationStateV1::ConsumedForExactRun
                    && commit.post_database_content_root_sha256.is_some()
                    && commit.external_checkpoint_receipt_sha256.is_some()
                    && commit.terminal_hard_lock
                    && permit.permit_eligible_after_commit
                    && !permit.process_local_affine_permit_issued
            }
            ClaimPacketStateV2::UnknownOutcomeTerminalHardLock => {
                let (commit, permit) = self.outcome_pair_v1()?;
                !self.test_only
                    && self.packet_kind == ClaimPacketKindV2::SingleUseClaimOutcomeReceipt
                    && commit.acknowledgement_state == CommitAcknowledgementV1::Unknown
                    && commit.affected_rows.is_none()
                    && commit.row_mutation_state == RowMutationStateV1::Unknown
                    && commit.post_database_content_root_sha256.is_none()
                    && commit.external_checkpoint_receipt_sha256.is_none()
                    && commit.terminal_hard_lock
                    && !permit.permit_eligible_after_commit
                    && !permit.process_local_affine_permit_issued
            }
        };
        Ok(result)
    }

    fn outcome_pair_v1(&self) -> AuthorizationResult<(&CommitOutcomeV1, &PermitOutcomeV1)> {
        match (&self.commit_outcome, &self.permit_outcome) {
            (Some(commit), Some(permit)) => Ok((commit, permit)),
            _ => Err(aligned_error(
                "s20b_aligned_claim_outcome_body",
                "claim outcome state lacks commit or permit body",
            )),
        }
    }
}

#[must_use]
struct ValidatedClaimPacketTokenV1 {
    digest: SecurityDigestV1,
    state: ClaimPacketStateV2,
    authorization_binding: AuthorizationBindingV1,
    run_id_sha256: SecurityDigestV1,
    attempt_id_sha256: SecurityDigestV1,
    run_assignment_id_sha256: SecurityDigestV1,
    capability_nonce_sha256: SecurityDigestV1,
    controller_binary_sha256: SecurityDigestV1,
    runner_binary_sha256: SecurityDigestV1,
    attempt_tombstone_sha256: SecurityDigestV1,
    assignment_binding: ClaimAssignmentBindingV1,
    post_database_identity_sha256: Option<[u8; 32]>,
    post_schema_catalog_sha256: Option<[u8; 32]>,
    post_generation: Option<u64>,
    post_database_content_root_sha256: Option<SecurityDigestV1>,
    external_checkpoint_receipt_sha256: Option<SecurityDigestV1>,
}

/// Opaque proof that the exact claim CAS was durably committed.  A generic
/// post-commit database snapshot is insufficient: it could describe a legal
/// but unrelated transition.  The future CAS adapter must construct this
/// token only after validating the row mutation and its pre/post database
/// states as one atomic transition.  S20B deliberately provides no
/// constructor while that adapter does not exist.
#[must_use]
struct ValidatedCommittedClaimTransitionV1 {
    pre_database_identity_sha256: [u8; 32],
    pre_schema_catalog_sha256: [u8; 32],
    pre_database_content_root_sha256: [u8; 32],
    pre_checkpoint_head_sha256: [u8; 32],
    pre_generation: u64,
    post_database_identity_sha256: [u8; 32],
    post_schema_catalog_sha256: [u8; 32],
    post_database_content_root_sha256: [u8; 32],
    post_checkpoint_head_sha256: [u8; 32],
    post_generation: u64,
    transition_core_sha256: [u8; 32],
    row_revision: u64,
    row_state: LedgerRowStateV1,
    consumed_run_id_sha256: [u8; 32],
    consumed_capability_nonce_sha256: [u8; 32],
    consumed_tombstone_absorbing: bool,
    successful_claim_count: u64,
}

fn parse_claim_packet_v1(raw: &[u8]) -> AuthorizationResult<AuthorityControlClaimPacketV1> {
    deserialize_closed_v1(raw)
}

fn seal_claim_packet_v1(
    mut packet: AuthorityControlClaimPacketV1,
) -> AuthorizationResult<CanonicalBuiltPacketV1> {
    if let Some(attempt) = packet.claim_attempt.as_mut() {
        attempt
            .cas_parameter_bindings
            .p06_claim_transition_core_sha256 =
            attempt.cas_parameter_bindings.transition_core_v1()?;
    }
    packet.validate_shape_v1()?;
    let digest =
        recompute_top_level_self_v1(&packet, CLAIM_SELF_KEY_V1, packet.packet_kind.domain())?;
    packet.claim_packet_sha256 = digest;
    Ok(CanonicalBuiltPacketV1 {
        canonical_bytes: serialize_canonical_v1(&packet)?,
        digest,
    })
}

fn claim_authority_matches_v1(
    packet: &AuthorityControlClaimPacketV1,
    authorized: &AuthorizedUnclaimedS19SubjectV1,
    assignments: &ValidatedAuthorizedAssignmentSetV1,
    member: &ValidatedAuthorizedAssignmentMemberV1,
    preflight: &ValidatedPreflightReceiptTokenV1,
    cas_control: &ValidatedControlSnapshotTokenV1,
    pre_state: &ValidatedCommittedDatabaseStateV1,
    committed_transition: Option<&ValidatedCommittedClaimTransitionV1>,
) -> AuthorizationResult<()> {
    packet
        .assignment_binding
        .validate_authority(assignments, member)?;
    let attempt = packet.claim_attempt.as_ref().ok_or_else(|| {
        aligned_error(
            "s20b_aligned_claim_attempt",
            "production outcome packet lacks its claim-attempt body",
        )
    })?;
    let same = packet.same_transaction_control.as_ref().ok_or_else(|| {
        aligned_error(
            "s20b_aligned_same_transaction",
            "production outcome packet lacks same-transaction control evidence",
        )
    })?;
    let cas = &attempt.cas_parameter_bindings;
    let stop_revision = cas_control.stop_revision.ok_or_else(|| {
        aligned_error(
            "s20b_aligned_cas_stop",
            "CAS control token lacks an observed STOP revision",
        )
    })?;
    let revocation_revision = cas_control.revocation_revision.ok_or_else(|| {
        aligned_error(
            "s20b_aligned_cas_revocation",
            "CAS control token lacks an observed revocation revision",
        )
    })?;
    let expected_authorization = AuthorizationBindingV1 {
        authorization_id_sha256: SecurityDigestV1::from_array(
            authorized.authorization.authorization_id_sha256,
        )?,
        owner_envelope_sha256: SecurityDigestV1::from_array(
            authorized.authorization.owner_envelope_sha256,
        )?,
        resource_scope_sha256: SecurityDigestV1::from_array(
            authorized.subject.resource_scope_sha256,
        )?,
        signed_revocation_epoch: authorized.authorization.revocation_epoch,
        signed_payload_sha256: SecurityDigestV1::from_array(
            authorized.authorization.payload_sha256,
        )?,
        subject_manifest_sha256: SecurityDigestV1::from_array(
            authorized.subject.canonical_manifest_sha256,
        )?,
        trust_anchor_document_sha256: SecurityDigestV1::from_array(
            authorized.authorization.trust_anchor_document_sha256,
        )?,
    };
    let roots_match = attempt.pre_database_content_root_sha256.bytes()
        == &pre_state.business_content_root_sha256
        && packet.parent_bindings.pre_database_content_root_sha256
            == Some(attempt.pre_database_content_root_sha256)
        && same.database_identity_sha256.bytes() == &pre_state.database_identity_sha256
        && cas_control.database_content_root_sha256.bytes()
            == &pre_state.business_content_root_sha256
        && cas_control.external_checkpoint_receipt_sha256.bytes()
            == &pre_state.checkpoint_head_sha256;
    let post_matches = match (packet.commit_outcome.as_ref(), committed_transition) {
        (Some(commit), Some(transition)) => {
            commit
                .post_database_content_root_sha256
                .as_ref()
                .map(SecurityDigestV1::bytes)
                == Some(&transition.post_database_content_root_sha256)
                && commit
                    .external_checkpoint_receipt_sha256
                    .as_ref()
                    .map(SecurityDigestV1::bytes)
                    == Some(&transition.post_checkpoint_head_sha256)
                && commit.acknowledgement_state == CommitAcknowledgementV1::Committed
                && transition.pre_database_identity_sha256 == pre_state.database_identity_sha256
                && transition.pre_schema_catalog_sha256 == pre_state.schema_catalog_sha256
                && transition.pre_database_content_root_sha256
                    == pre_state.business_content_root_sha256
                && transition.pre_checkpoint_head_sha256 == pre_state.checkpoint_head_sha256
                && transition.pre_generation == pre_state.generation
                && transition.post_database_identity_sha256
                    == transition.pre_database_identity_sha256
                && transition.post_schema_catalog_sha256 == transition.pre_schema_catalog_sha256
                && transition.pre_generation.checked_add(1) == Some(transition.post_generation)
                && transition.transition_core_sha256
                    == *cas.p06_claim_transition_core_sha256.bytes()
                && transition.row_revision == cas.p01_next_revision
                && transition.row_state == LedgerRowStateV1::ConsumedForExactRun
                && transition.consumed_run_id_sha256 == *cas.p02_run_id_sha256.bytes()
                && transition.consumed_capability_nonce_sha256
                    == *cas.p16_capability_nonce_sha256.bytes()
                && transition.consumed_tombstone_absorbing
                && transition.successful_claim_count == 1
        }
        (Some(commit), None) => {
            commit.post_database_content_root_sha256.is_none()
                && commit.external_checkpoint_receipt_sha256.is_none()
                && !matches!(
                    commit.acknowledgement_state,
                    CommitAcknowledgementV1::Committed
                )
        }
        _ => false,
    };
    let cas_matches = cas.p01_next_revision
        == packet
            .claim_key_binding
            .expected_unclaimed_revision
            .checked_add(1)
            .unwrap_or(0)
        && cas.p02_run_id_sha256 == preflight.run_binding.run_id_sha256
        && cas.p03_controller_binary_sha256 == preflight.run_binding.controller_binary_sha256
        && cas.p04_preflight_receipt_sha256 == preflight.digest
        && cas.p05_control_snapshot_sha256 == cas_control.digest
        && cas.p07_authorization_id_sha256 == expected_authorization.authorization_id_sha256
        && cas.p08_claim_namespace_sha256 == preflight.run_binding.claim_namespace_sha256
        && cas.p09_claim_key_sha256 == preflight.run_binding.claim_key_sha256
        && cas.p10_signed_payload_sha256 == expected_authorization.signed_payload_sha256
        && cas.p11_subject_manifest_sha256 == expected_authorization.subject_manifest_sha256
        && cas.p12_resource_scope_sha256 == expected_authorization.resource_scope_sha256
        && cas.p13_signed_revocation_epoch == expected_authorization.signed_revocation_epoch
        && cas.p14_expected_unclaimed_revision
            == packet.claim_key_binding.expected_unclaimed_revision
        && cas.p15_runner_binary_sha256 == preflight.run_binding.runner_binary_sha256
        && cas.p16_capability_nonce_sha256 == preflight.run_binding.capability_nonce_sha256
        && cas.p17_control_ledger_identity_sha256.bytes()
            == &authorized.subject.control_ledger_identity_sha256
        && cas.p18_anti_rollback_policy_sha256.bytes()
            == &authorized.subject.anti_rollback_policy_sha256
        && cas.p19_stop_revision == stop_revision
        && cas.p20_revocation_revision == revocation_revision
        && cas.p21_stop_policy_identity_sha256.bytes()
            == &authorized.subject.stop_control_policy_sha256
        && cas.p22_revocation_policy_identity_sha256.bytes()
            == &authorized.revocation_policy_sha256
        && cas.p23_sqlite_profile_sha256.bytes() == &authorized.subject.sqlite_profile_sha256
        && cas.p24_sqlite_schema_sha256.bytes() == &authorized.subject.sqlite_schema_sha256;
    if packet.packet_kind != ClaimPacketKindV2::SingleUseClaimOutcomeReceipt
        || packet.test_only
        || packet.synthetic
        || !assignments.matches_authorized_subject_v1(authorized)
        || packet.authorization_binding != expected_authorization
        || preflight.authorization_binding != expected_authorization
        || cas_control.authorization_binding != expected_authorization
        || packet.claim_key_binding.claim_namespace_sha256
            != preflight.run_binding.claim_namespace_sha256
        || packet.claim_key_binding.claim_key_sha256 != preflight.run_binding.claim_key_sha256
        || packet.claim_key_binding.expected_unclaimed_revision
            != authorized.subject.expected_unclaimed_revision
        || preflight.run_binding.capability_nonce_sha256.bytes()
            != &authorized.capability_nonce_sha256
        || preflight.run_binding.controller_binary_sha256.bytes()
            != &authorized.subject.controller_binary_sha256
        || preflight.run_binding.runner_binary_sha256.bytes()
            != &authorized.subject.runner_binary_sha256
        || preflight.run_binding.observer_binary_sha256.bytes()
            != &authorized.subject.preflight_observer_binary_sha256
        || preflight.run_binding.run_assignment_id_sha256.bytes() != &member.assignment_id_sha256
        || attempt.attempt_id_sha256 != preflight.run_binding.attempt_id_sha256
        || attempt.attempt_tombstone_sha256 != preflight.run_binding.attempt_tombstone_sha256
        || attempt.run_assignment_id_sha256 != preflight.run_binding.run_assignment_id_sha256
        || attempt.assignment_record_sha256.bytes() != &member.assignment_record_sha256
        || attempt.operation_descriptor_set_sha256.bytes() != &member.operation_set_sha256
        || packet.parent_bindings.attempt_tombstone_sha256 != Some(attempt.attempt_tombstone_sha256)
        || packet.parent_bindings.preflight_receipt_sha256 != Some(preflight.digest)
        || packet.parent_bindings.control_snapshot_sha256 != Some(cas_control.digest)
        || cas_control.phase != ControlPhaseV2::CasLinearization
        || cas_control.claim_revision != Some(packet.claim_key_binding.expected_unclaimed_revision)
        || same.transaction_sequence != cas_control.transaction_sequence
        || same.claim_row_read_state != SameTransactionClaimReadV1::AuthorizedUnclaimed
        || same.stop_read_state != StopReadStateV1::Clear
        || same.revocation_read_state != RevocationReadStateV1::Exact
        || !roots_match
        || !post_matches
        || !cas_matches
    {
        return Err(aligned_error(
            "s20b_aligned_claim_authority",
            "claim does not match owner, assignment, parent, control, CAS, or committed-state evidence",
        ));
    }
    Ok(())
}

fn validate_claim_outcome_packet_v1(
    raw: &[u8],
    authorized: &AuthorizedUnclaimedS19SubjectV1,
    assignments: &ValidatedAuthorizedAssignmentSetV1,
    member: &ValidatedAuthorizedAssignmentMemberV1,
    preflight: &ValidatedPreflightReceiptTokenV1,
    cas_control: &ValidatedControlSnapshotTokenV1,
    pre_state: &ValidatedCommittedDatabaseStateV1,
    committed_transition: Option<&ValidatedCommittedClaimTransitionV1>,
) -> AuthorizationResult<ValidatedClaimPacketTokenV1> {
    let packet = parse_claim_packet_v1(raw)?;
    packet.validate_shape_v1()?;
    claim_authority_matches_v1(
        &packet,
        authorized,
        assignments,
        member,
        preflight,
        cas_control,
        pre_state,
        committed_transition,
    )?;
    let digest = recompute_top_level_self_v1(&packet, CLAIM_SELF_KEY_V1, CLAIM_OUTCOME_DOMAIN_V1)?;
    if digest != packet.claim_packet_sha256 {
        return Err(aligned_error(
            "s20b_aligned_claim_self",
            "claim self digest does not recompute under its exact variant domain",
        ));
    }
    let attempt = packet.claim_attempt.as_ref().unwrap();
    let commit = packet.commit_outcome.as_ref().unwrap();
    Ok(ValidatedClaimPacketTokenV1 {
        digest,
        state: packet.claim_packet_state,
        authorization_binding: packet.authorization_binding.clone(),
        run_id_sha256: attempt.cas_parameter_bindings.p02_run_id_sha256,
        attempt_id_sha256: attempt.attempt_id_sha256,
        run_assignment_id_sha256: attempt.run_assignment_id_sha256,
        capability_nonce_sha256: attempt.cas_parameter_bindings.p16_capability_nonce_sha256,
        controller_binary_sha256: attempt.cas_parameter_bindings.p03_controller_binary_sha256,
        runner_binary_sha256: attempt.cas_parameter_bindings.p15_runner_binary_sha256,
        attempt_tombstone_sha256: attempt.attempt_tombstone_sha256,
        assignment_binding: packet.assignment_binding,
        post_database_identity_sha256: committed_transition
            .map(|transition| transition.post_database_identity_sha256),
        post_schema_catalog_sha256: committed_transition
            .map(|transition| transition.post_schema_catalog_sha256),
        post_generation: committed_transition.map(|transition| transition.post_generation),
        post_database_content_root_sha256: commit.post_database_content_root_sha256,
        external_checkpoint_receipt_sha256: commit.external_checkpoint_receipt_sha256,
    })
}

fn build_claim_outcome_packet_v1(
    mut packet: AuthorityControlClaimPacketV1,
    authorized: &AuthorizedUnclaimedS19SubjectV1,
    assignments: &ValidatedAuthorizedAssignmentSetV1,
    member: &ValidatedAuthorizedAssignmentMemberV1,
    preflight: &ValidatedPreflightReceiptTokenV1,
    cas_control: &ValidatedControlSnapshotTokenV1,
    pre_state: &ValidatedCommittedDatabaseStateV1,
    committed_transition: Option<&ValidatedCommittedClaimTransitionV1>,
) -> AuthorizationResult<CanonicalBuiltPacketV1> {
    if packet.packet_kind != ClaimPacketKindV2::SingleUseClaimOutcomeReceipt
        || packet.test_only
        || packet.synthetic
    {
        return Err(aligned_error(
            "s20b_aligned_production_synthetic",
            "production outcome builder requires a non-synthetic outcome variant",
        ));
    }
    let stop_revision = cas_control.stop_revision.ok_or_else(|| {
        aligned_error(
            "s20b_aligned_cas_stop",
            "CAS control token lacks STOP revision",
        )
    })?;
    let revocation_revision = cas_control.revocation_revision.ok_or_else(|| {
        aligned_error(
            "s20b_aligned_cas_revocation",
            "CAS control token lacks revocation revision",
        )
    })?;
    let attempt = packet.claim_attempt.as_mut().ok_or_else(|| {
        aligned_error(
            "s20b_aligned_claim_attempt",
            "outcome builder lacks claim attempt",
        )
    })?;
    let cas = &mut attempt.cas_parameter_bindings;
    cas.p01_next_revision = packet
        .claim_key_binding
        .expected_unclaimed_revision
        .checked_add(1)
        .ok_or_else(|| aligned_error("s20b_aligned_cas_revision", "expected revision overflows"))?;
    cas.p02_run_id_sha256 = preflight.run_binding.run_id_sha256;
    cas.p03_controller_binary_sha256 = preflight.run_binding.controller_binary_sha256;
    cas.p04_preflight_receipt_sha256 = preflight.digest;
    cas.p05_control_snapshot_sha256 = cas_control.digest;
    cas.p07_authorization_id_sha256 = packet.authorization_binding.authorization_id_sha256;
    cas.p08_claim_namespace_sha256 = packet.claim_key_binding.claim_namespace_sha256;
    cas.p09_claim_key_sha256 = packet.claim_key_binding.claim_key_sha256;
    cas.p10_signed_payload_sha256 = packet.authorization_binding.signed_payload_sha256;
    cas.p11_subject_manifest_sha256 = packet.authorization_binding.subject_manifest_sha256;
    cas.p12_resource_scope_sha256 = packet.authorization_binding.resource_scope_sha256;
    cas.p13_signed_revocation_epoch = packet.authorization_binding.signed_revocation_epoch;
    cas.p14_expected_unclaimed_revision = packet.claim_key_binding.expected_unclaimed_revision;
    cas.p15_runner_binary_sha256 = preflight.run_binding.runner_binary_sha256;
    cas.p16_capability_nonce_sha256 = preflight.run_binding.capability_nonce_sha256;
    cas.p17_control_ledger_identity_sha256 =
        SecurityDigestV1::from_array(authorized.subject.control_ledger_identity_sha256)?;
    cas.p18_anti_rollback_policy_sha256 =
        SecurityDigestV1::from_array(authorized.subject.anti_rollback_policy_sha256)?;
    cas.p19_stop_revision = stop_revision;
    cas.p20_revocation_revision = revocation_revision;
    cas.p21_stop_policy_identity_sha256 =
        SecurityDigestV1::from_array(authorized.subject.stop_control_policy_sha256)?;
    cas.p22_revocation_policy_identity_sha256 =
        SecurityDigestV1::from_array(authorized.revocation_policy_sha256)?;
    cas.p23_sqlite_profile_sha256 =
        SecurityDigestV1::from_array(authorized.subject.sqlite_profile_sha256)?;
    cas.p24_sqlite_schema_sha256 =
        SecurityDigestV1::from_array(authorized.subject.sqlite_schema_sha256)?;
    cas.p06_claim_transition_core_sha256 = cas.transition_core_v1()?;
    attempt.pre_database_content_root_sha256 =
        SecurityDigestV1::from_array(pre_state.business_content_root_sha256)?;
    packet.parent_bindings.pre_database_content_root_sha256 =
        Some(attempt.pre_database_content_root_sha256);
    packet.parent_bindings.preflight_receipt_sha256 = Some(preflight.digest);
    packet.parent_bindings.control_snapshot_sha256 = Some(cas_control.digest);
    if let (Some(commit), Some(transition)) = (packet.commit_outcome.as_mut(), committed_transition)
    {
        commit.post_database_content_root_sha256 = Some(SecurityDigestV1::from_array(
            transition.post_database_content_root_sha256,
        )?);
        commit.external_checkpoint_receipt_sha256 = Some(SecurityDigestV1::from_array(
            transition.post_checkpoint_head_sha256,
        )?);
    }
    claim_authority_matches_v1(
        &packet,
        authorized,
        assignments,
        member,
        preflight,
        cas_control,
        pre_state,
        committed_transition,
    )?;
    seal_claim_packet_v1(packet)
}

#[derive(Clone, Debug, Eq, PartialEq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
struct PostRunExecutionBindingV1 {
    attempt_id_sha256: SecurityDigestV1,
    attempt_tombstone_sha256: SecurityDigestV1,
    capability_nonce_sha256: SecurityDigestV1,
    claim_packet_sha256: SecurityDigestV1,
    controller_binary_sha256: SecurityDigestV1,
    external_checkpoint_receipt_sha256: Option<SecurityDigestV1>,
    final_database_content_root_sha256: Option<SecurityDigestV1>,
    run_assignment_id_sha256: SecurityDigestV1,
    run_id_sha256: SecurityDigestV1,
    runner_binary_sha256: SecurityDigestV1,
}

#[derive(Clone, Debug, Eq, PartialEq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
struct PostRunAssignmentBindingV1 {
    assignment_record_count: u64,
    assignment_record_set_sha256: SecurityDigestV1,
    assignment_set_sha256: SecurityDigestV1,
    membership_profile: String,
    operation_descriptor_set_sha256: SecurityDigestV1,
    schedule_sha256: SecurityDigestV1,
}

#[derive(Clone, Debug, Eq, PartialEq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
struct AssignedDenominatorV1 {
    ol00_count: u64,
    ol04_count: u64,
    ol05_count: u64,
    total_count: u64,
}

#[derive(Clone, Debug, Eq, PartialEq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
struct ObservedCountsV1 {
    action_start_receipts: u64,
    assigned_attempts: u64,
    automatic_retries: u64,
    claim_commits: u64,
    fresh_exec_reads: u64,
    phase_records: u64,
    pidfd_sigkill_attempts: u64,
    raw_observations: u64,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq, Serialize, Deserialize)]
enum S17ValidationStateV1 {
    #[serde(rename = "SYNTHETIC_KAT_NOT_RUN")]
    SyntheticKatNotRun,
    #[serde(rename = "PASS_FULL_CATALOG")]
    PassFullCatalog,
    #[serde(rename = "FAIL_OR_INDETERMINATE")]
    FailOrIndeterminate,
}

#[derive(Clone, Debug, Eq, PartialEq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
struct ValidatorBindingV1 {
    assignment_prefilter_allowed: bool,
    expected_phase_record_count: u64,
    frozen_catalog_row_count: u64,
    frozen_catalog_sha256: SecurityDigestV1,
    ruleset_sha256: SecurityDigestV1,
    s17_rule_count: u64,
    validation_state: S17ValidationStateV1,
    validator_binary_sha256: SecurityDigestV1,
    validator_source_sha256: SecurityDigestV1,
    validator_toolchain_sha256: SecurityDigestV1,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq, Serialize, Deserialize)]
enum PostRunControlStateV1 {
    #[serde(rename = "SYNTHETIC_NOT_READ")]
    SyntheticNotRead,
    #[serde(rename = "CLEAR")]
    Clear,
    #[serde(rename = "STOP_TRIGGERED")]
    StopTriggered,
    #[serde(rename = "REVOCATION_MISMATCH")]
    RevocationMismatch,
    #[serde(rename = "ROLLBACK_DETECTED")]
    RollbackDetected,
    #[serde(rename = "READ_UNKNOWN")]
    ReadUnknown,
}

#[derive(Clone, Debug, Eq, PartialEq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
struct PostRunControlOutcomeV1 {
    revocation_ledger_revision: Option<u64>,
    state: PostRunControlStateV1,
    stop_ledger_revision: Option<u64>,
    terminal_hard_lock: bool,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq, Serialize, Deserialize)]
enum ReceiptKindV1 {
    #[serde(rename = "ACTION_START")]
    ActionStart,
    #[serde(rename = "RAW_OBSERVATION")]
    RawObservation,
    #[serde(rename = "RETENTION")]
    Retention,
    #[serde(rename = "SEMANTIC")]
    Semantic,
    #[serde(rename = "BATCH")]
    Batch,
    #[serde(rename = "STOP")]
    Stop,
    #[serde(rename = "CLEANUP")]
    Cleanup,
    #[serde(rename = "CUSTODY")]
    Custody,
}

#[derive(Clone, Debug, Eq, PartialEq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
struct ReceiptNodeSummaryV1 {
    authorization_id_sha256: SecurityDigestV1,
    digest_domain: String,
    hash_scope: String,
    parent_sha256: SecurityDigestV1,
    receipt_kind: ReceiptKindV1,
    receipt_sha256: SecurityDigestV1,
    run_id_sha256: SecurityDigestV1,
    subject_sha256: SecurityDigestV1,
}

impl ReceiptNodeSummaryV1 {
    fn validate_shape(&self) -> AuthorizationResult<()> {
        let domain = self.digest_domain.as_bytes();
        let valid_domain = self
            .digest_domain
            .strip_prefix("agent-bridge/biocortex/owned-lab/s20b/")
            .and_then(|rest| rest.strip_suffix("/v1"))
            .is_some_and(|middle| {
                !middle.is_empty()
                    && middle.bytes().all(|byte| {
                        byte.is_ascii_lowercase() || byte.is_ascii_digit() || byte == b'-'
                    })
            });
        if !valid_domain
            || !domain.is_ascii()
            || self.hash_scope != "ENTIRE_RECEIPT_EXCEPT_RECEIPT_SHA256"
        {
            return Err(aligned_error(
                "s20b_aligned_nested_receipt_shape",
                "nested receipt domain or self-hash scope drifted",
            ));
        }
        Ok(())
    }
}

#[derive(Clone, Debug, Eq, PartialEq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
struct ReceiptChainV1 {
    action_start_receipt_count: u64,
    action_start_receipt_set_sha256: Option<SecurityDigestV1>,
    all_parent_links_recomputed: bool,
    claim_packet_sha256: SecurityDigestV1,
    control_snapshot_sha256: SecurityDigestV1,
    nested_receipts: Vec<ReceiptNodeSummaryV1>,
    preflight_receipt_sha256: SecurityDigestV1,
    raw_observation_set_sha256: Option<SecurityDigestV1>,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq, Serialize, Deserialize)]
enum EvidenceStateV1 {
    #[serde(rename = "SYNTHETIC_KAT_NO_SCIENTIFIC_EVIDENCE")]
    SyntheticKatNoScientificEvidence,
    #[serde(rename = "VALID_COMPLETE_EXACT_CANARY_EVIDENCE")]
    ValidCompleteExactCanaryEvidence,
    #[serde(rename = "INVALID_OR_INCOMPLETE")]
    InvalidOrIncomplete,
    #[serde(rename = "INDETERMINATE")]
    Indeterminate,
}

#[derive(Clone, Debug, Eq, PartialEq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
struct EvidenceOutcomeV1 {
    evidence_state: EvidenceStateV1,
    favorable_result_claimed: bool,
    scientific_result_claimed: bool,
    zero_or_multiple_catalog_matches_indeterminate: bool,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq, Serialize, Deserialize)]
enum PostRunBundleStateV1 {
    #[serde(rename = "SYNTHETIC_KAT_NON_LIVE_POST_RUN_BUNDLE")]
    SyntheticKatNonLive,
    #[serde(rename = "VALID_COMPLETE_EXACT_CANARY_EVIDENCE")]
    ValidCompleteExactCanaryEvidence,
    #[serde(rename = "INVALID_OR_INCOMPLETE_TERMINAL")]
    InvalidOrIncompleteTerminal,
    #[serde(rename = "UNKNOWN_OUTCOME_TERMINAL_HARD_LOCK")]
    UnknownOutcomeTerminalHardLock,
}

#[derive(Clone, Debug, Eq, PartialEq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
struct PostRunNonclaimsV1 {
    bundle_authorizes_retry: bool,
    bundle_is_bearer_capability: bool,
    bundle_is_owner_authority: bool,
    provider_or_production_authority: bool,
    s21_admitted: bool,
    schema_conformance_authorizes_live_execution: bool,
    side_effects_unlocked: String,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
struct PostRunReceiptBundlePacketV1 {
    assigned_denominator: AssignedDenominatorV1,
    assignment_binding: PostRunAssignmentBindingV1,
    authorization_binding: AuthorizationBindingV1,
    bundle_state: PostRunBundleStateV1,
    canonicalization: String,
    control_outcome: PostRunControlOutcomeV1,
    evidence_outcome: EvidenceOutcomeV1,
    execution_binding: PostRunExecutionBindingV1,
    hashing_contract: HashingContractV1,
    nonclaims: PostRunNonclaimsV1,
    observed_counts: ObservedCountsV1,
    packet_kind: String,
    post_run_bundle_sha256: SecurityDigestV1,
    receipt_chain: ReceiptChainV1,
    schema: String,
    semantic_validation: SemanticValidationV1,
    synthetic: bool,
    test_only: bool,
    validator_binding: ValidatorBindingV1,
}

const POSTRUN_RULES_V1: [&str; 7] = [
    "SELF_AND_ALL_PARENT_DIGESTS_RECOMPUTED_FROM_CANONICAL_BYTES",
    "AUTHORIZATION_RUN_ASSIGNMENT_OPERATION_AND_CLAIM_BINDINGS_EXACT",
    "RECEIPT_CHAIN_IS_BACKWARD_ONLY_AND_DOMAIN_SEPARATED",
    "VALID_COMPLETE_REQUIRES_EXACT_DENOMINATOR_AND_OBSERVED_COUNTS",
    "S17_32_RULE_CLASSIFICATION_SEARCHES_ALL_5639_ROWS_WITHOUT_ASSIGNMENT_PREFILTER",
    "ZERO_OR_MULTIPLE_CATALOG_MATCHES_REMAIN_INDETERMINATE",
    "VALID_EVIDENCE_DOES_NOT_IMPLY_FAVORABLE_SCIENTIFIC_RESULT",
];

impl PostRunReceiptBundlePacketV1 {
    fn validate_shape_v1(&self) -> AuthorizationResult<()> {
        self.hashing_contract
            .validate(POSTRUN_DOMAIN_V1, POSTRUN_SCOPE_V1, POSTRUN_SELF_KEY_V1)?;
        self.semantic_validation.validate(&POSTRUN_RULES_V1)?;
        self.authorization_binding.validate()?;
        for node in &self.receipt_chain.nested_receipts {
            node.validate_shape()?;
        }
        let counts_in_range = self.assigned_denominator.ol00_count <= 1
            && self.assigned_denominator.ol04_count <= 6
            && self.assigned_denominator.ol05_count <= 53
            && self.assigned_denominator.total_count <= 60
            && self.observed_counts.claim_commits <= 1
            && self.observed_counts.assigned_attempts <= 60
            && self.observed_counts.pidfd_sigkill_attempts <= 59
            && self.observed_counts.fresh_exec_reads <= 59
            && self.observed_counts.phase_records <= 113
            && self.observed_counts.raw_observations <= 60
            && self.observed_counts.action_start_receipts <= 60
            && self.receipt_chain.action_start_receipt_count <= 60
            && self.receipt_chain.nested_receipts.len() <= 127;
        let control_tag_valid = match self.control_outcome.state {
            PostRunControlStateV1::SyntheticNotRead | PostRunControlStateV1::ReadUnknown => {
                self.control_outcome.stop_ledger_revision.is_none()
                    && self.control_outcome.revocation_ledger_revision.is_none()
                    && self.control_outcome.terminal_hard_lock
            }
            PostRunControlStateV1::Clear => {
                self.control_outcome
                    .stop_ledger_revision
                    .is_some_and(|value| value > 0)
                    && self
                        .control_outcome
                        .revocation_ledger_revision
                        .is_some_and(|value| value > 0)
                    && !self.control_outcome.terminal_hard_lock
            }
            PostRunControlStateV1::StopTriggered
            | PostRunControlStateV1::RevocationMismatch
            | PostRunControlStateV1::RollbackDetected => {
                self.control_outcome
                    .stop_ledger_revision
                    .is_some_and(|value| value > 0)
                    && self
                        .control_outcome
                        .revocation_ledger_revision
                        .is_some_and(|value| value > 0)
                    && self.control_outcome.terminal_hard_lock
            }
        };
        if self.schema != POSTRUN_SCHEMA_V1
            || self.packet_kind != POSTRUN_KIND_V1
            || self.canonicalization != CANONICALIZATION_V1
            || self.test_only != self.synthetic
            || self.assignment_binding.assignment_record_count != 60
            || self.assignment_binding.membership_profile != ASSIGNMENT_MEMBERSHIP_PROFILE_V1
            || self.validator_binding.s17_rule_count != 32
            || self.validator_binding.frozen_catalog_row_count != 5_639
            || self.validator_binding.expected_phase_record_count != 113
            || self.validator_binding.assignment_prefilter_allowed
            || self.observed_counts.automatic_retries != 0
            || !counts_in_range
            || !control_tag_valid
            || self.evidence_outcome.scientific_result_claimed
            || self.evidence_outcome.favorable_result_claimed
            || !self
                .evidence_outcome
                .zero_or_multiple_catalog_matches_indeterminate
            || self.nonclaims.bundle_authorizes_retry
            || self.nonclaims.bundle_is_bearer_capability
            || self.nonclaims.bundle_is_owner_authority
            || self.nonclaims.provider_or_production_authority
            || self.nonclaims.s21_admitted
            || self.nonclaims.schema_conformance_authorizes_live_execution
            || self.nonclaims.side_effects_unlocked != "NONE"
        {
            return Err(aligned_error(
                "s20b_aligned_postrun_shape",
                "post-run constant, count range, control tag, evidence nonclaim, or validator contract drifted",
            ));
        }
        let exact_denominator = self.assigned_denominator.ol00_count == 1
            && self.assigned_denominator.ol04_count == 6
            && self.assigned_denominator.ol05_count == 53
            && self.assigned_denominator.total_count == 60;
        let exact_observations = self.observed_counts.claim_commits == 1
            && self.observed_counts.assigned_attempts == 60
            && self.observed_counts.pidfd_sigkill_attempts == 59
            && self.observed_counts.fresh_exec_reads == 59
            && self.observed_counts.phase_records == 113
            && self.observed_counts.raw_observations == 60
            && self.observed_counts.action_start_receipts == 60
            && self.receipt_chain.action_start_receipt_count == 60;
        let state_valid = match self.bundle_state {
            PostRunBundleStateV1::SyntheticKatNonLive => {
                self.test_only
                    && self.synthetic
                    && self.assigned_denominator.ol00_count == 0
                    && self.assigned_denominator.ol04_count == 0
                    && self.assigned_denominator.ol05_count == 0
                    && self.assigned_denominator.total_count == 0
                    && self.observed_counts.claim_commits == 0
                    && self.observed_counts.assigned_attempts == 0
                    && self.observed_counts.pidfd_sigkill_attempts == 0
                    && self.observed_counts.fresh_exec_reads == 0
                    && self.observed_counts.phase_records == 0
                    && self.observed_counts.raw_observations == 0
                    && self.observed_counts.action_start_receipts == 0
                    && self
                        .execution_binding
                        .final_database_content_root_sha256
                        .is_none()
                    && self
                        .execution_binding
                        .external_checkpoint_receipt_sha256
                        .is_none()
                    && self.receipt_chain.raw_observation_set_sha256.is_none()
                    && self.receipt_chain.action_start_receipt_set_sha256.is_none()
                    && self.receipt_chain.action_start_receipt_count == 0
                    && self.receipt_chain.nested_receipts.is_empty()
                    && self.receipt_chain.all_parent_links_recomputed
                    && self.validator_binding.validation_state
                        == S17ValidationStateV1::SyntheticKatNotRun
                    && self.control_outcome.state == PostRunControlStateV1::SyntheticNotRead
                    && self.evidence_outcome.evidence_state
                        == EvidenceStateV1::SyntheticKatNoScientificEvidence
            }
            PostRunBundleStateV1::ValidCompleteExactCanaryEvidence => {
                !self.test_only
                    && exact_denominator
                    && exact_observations
                    && self
                        .execution_binding
                        .final_database_content_root_sha256
                        .is_some()
                    && self
                        .execution_binding
                        .external_checkpoint_receipt_sha256
                        .is_some()
                    && self.receipt_chain.raw_observation_set_sha256.is_some()
                    && self.receipt_chain.action_start_receipt_set_sha256.is_some()
                    && self.receipt_chain.all_parent_links_recomputed
                    && self.validator_binding.validation_state
                        == S17ValidationStateV1::PassFullCatalog
                    && self.control_outcome.state == PostRunControlStateV1::Clear
                    && self.evidence_outcome.evidence_state
                        == EvidenceStateV1::ValidCompleteExactCanaryEvidence
            }
            PostRunBundleStateV1::InvalidOrIncompleteTerminal => {
                !self.test_only
                    && self.validator_binding.validation_state
                        == S17ValidationStateV1::FailOrIndeterminate
                    && matches!(
                        self.evidence_outcome.evidence_state,
                        EvidenceStateV1::InvalidOrIncomplete | EvidenceStateV1::Indeterminate
                    )
                    && self.control_outcome.terminal_hard_lock
            }
            PostRunBundleStateV1::UnknownOutcomeTerminalHardLock => {
                !self.test_only
                    && self.control_outcome.state == PostRunControlStateV1::ReadUnknown
                    && self.control_outcome.terminal_hard_lock
                    && self.evidence_outcome.evidence_state == EvidenceStateV1::Indeterminate
            }
        };
        if !state_valid {
            return Err(aligned_error(
                "s20b_aligned_postrun_state",
                "post-run state is inconsistent with denominator, observations, validator, or evidence outcome",
            ));
        }
        Ok(())
    }
}

#[must_use]
struct ValidatedPostRunBundleTokenV1 {
    digest: SecurityDigestV1,
    state: PostRunBundleStateV1,
}

fn parse_postrun_packet_v1(raw: &[u8]) -> AuthorizationResult<PostRunReceiptBundlePacketV1> {
    deserialize_closed_v1(raw)
}

fn seal_postrun_packet_v1(
    mut packet: PostRunReceiptBundlePacketV1,
) -> AuthorizationResult<CanonicalBuiltPacketV1> {
    packet.validate_shape_v1()?;
    let digest = recompute_top_level_self_v1(&packet, POSTRUN_SELF_KEY_V1, POSTRUN_DOMAIN_V1)?;
    packet.post_run_bundle_sha256 = digest;
    Ok(CanonicalBuiltPacketV1 {
        canonical_bytes: serialize_canonical_v1(&packet)?,
        digest,
    })
}

/// Opaque result of the still-future nested-receipt byte validators.  The
/// summary fields inside a post-run packet are insufficient to recompute a
/// nested receipt self digest, so this token intentionally has no constructor
/// in the current non-live module.
#[must_use]
struct ValidatedPostRunReceiptFactsV1 {
    receipt_chain: ReceiptChainV1,
    observation_count: u64,
    observation_set_sha256: [u8; 32],
    phase_record_set_count: u64,
    phase_record_set_sha256: [u8; 32],
}

#[derive(Clone, Copy)]
struct S17PostRunCommitmentsV1 {
    assignment_record_set_sha256: [u8; 32],
    operation_descriptor_set_sha256: [u8; 32],
    observation_count: u64,
    observation_set_sha256: [u8; 32],
    phase_record_set_count: u64,
    phase_record_set_sha256: [u8; 32],
}

fn postrun_s17_commitments_match_v1(
    packet: &PostRunReceiptBundlePacketV1,
    receipts: &ValidatedPostRunReceiptFactsV1,
    commitments: S17PostRunCommitmentsV1,
) -> bool {
    packet
        .assignment_binding
        .assignment_record_set_sha256
        .bytes()
        == &commitments.assignment_record_set_sha256
        && packet
            .assignment_binding
            .operation_descriptor_set_sha256
            .bytes()
            == &commitments.operation_descriptor_set_sha256
        && packet.observed_counts.raw_observations == commitments.observation_count
        && packet
            .receipt_chain
            .raw_observation_set_sha256
            .as_ref()
            .map(SecurityDigestV1::bytes)
            == Some(&commitments.observation_set_sha256)
        && packet.observed_counts.phase_records == commitments.phase_record_set_count
        && packet.validator_binding.expected_phase_record_count
            == commitments.phase_record_set_count
        && receipts.observation_count == commitments.observation_count
        && receipts.observation_set_sha256 == commitments.observation_set_sha256
        && receipts.phase_record_set_count == commitments.phase_record_set_count
        && receipts.phase_record_set_sha256 == commitments.phase_record_set_sha256
}

fn complete_postrun_authority_matches_v1(
    packet: &PostRunReceiptBundlePacketV1,
    authorized: &AuthorizedUnclaimedS19SubjectV1,
    assignments: &ValidatedAuthorizedAssignmentSetV1,
    preflight: &ValidatedPreflightReceiptTokenV1,
    final_control: &ValidatedControlSnapshotTokenV1,
    claim: &ValidatedClaimPacketTokenV1,
    final_state: &ValidatedCommittedDatabaseStateV1,
    s17: &ValidatedS17BatchV1,
    receipts: &ValidatedPostRunReceiptFactsV1,
) -> AuthorizationResult<()> {
    let accounting = s17.accounting();
    let s17_commitments = S17PostRunCommitmentsV1 {
        assignment_record_set_sha256: accounting.assignment_record_set_sha256,
        operation_descriptor_set_sha256: accounting.operation_descriptor_set_sha256,
        observation_count: accounting.observation_count,
        observation_set_sha256: accounting.observation_set_sha256,
        phase_record_set_count: accounting.phase_record_set_count,
        phase_record_set_sha256: accounting.phase_record_set_sha256,
    };
    let expected_authorization = AuthorizationBindingV1 {
        authorization_id_sha256: SecurityDigestV1::from_array(
            authorized.authorization.authorization_id_sha256,
        )?,
        owner_envelope_sha256: SecurityDigestV1::from_array(
            authorized.authorization.owner_envelope_sha256,
        )?,
        resource_scope_sha256: SecurityDigestV1::from_array(
            authorized.subject.resource_scope_sha256,
        )?,
        signed_revocation_epoch: authorized.authorization.revocation_epoch,
        signed_payload_sha256: SecurityDigestV1::from_array(
            authorized.authorization.payload_sha256,
        )?,
        subject_manifest_sha256: SecurityDigestV1::from_array(
            authorized.subject.canonical_manifest_sha256,
        )?,
        trust_anchor_document_sha256: SecurityDigestV1::from_array(
            authorized.authorization.trust_anchor_document_sha256,
        )?,
    };
    if packet.test_only
        || packet.synthetic
        || packet.bundle_state != PostRunBundleStateV1::ValidCompleteExactCanaryEvidence
        || !assignments.matches_authorized_subject_v1(authorized)
        || packet.authorization_binding != expected_authorization
        || preflight.authorization_binding != expected_authorization
        || final_control.authorization_binding != expected_authorization
        || claim.authorization_binding != expected_authorization
        || claim.state != ClaimPacketStateV2::CommittedPermitIssued
        || !matches!(
            final_control.phase,
            ControlPhaseV2::PostClaimPreStart | ControlPhaseV2::RuntimeActionBoundary
        )
        || final_control.snapshot_state != ControlSnapshotStateV1::CompleteAllow
        || final_control.stop_state != StopReadStateV1::Clear
        || final_control.revocation_state != RevocationReadStateV1::Exact
        || packet.execution_binding.claim_packet_sha256 != claim.digest
        || packet.execution_binding.run_id_sha256 != claim.run_id_sha256
        || packet.execution_binding.attempt_id_sha256 != claim.attempt_id_sha256
        || packet.execution_binding.run_assignment_id_sha256 != claim.run_assignment_id_sha256
        || packet.execution_binding.capability_nonce_sha256 != claim.capability_nonce_sha256
        || packet.execution_binding.controller_binary_sha256 != claim.controller_binary_sha256
        || packet.execution_binding.runner_binary_sha256 != claim.runner_binary_sha256
        || packet.execution_binding.attempt_tombstone_sha256 != claim.attempt_tombstone_sha256
        || packet
            .execution_binding
            .final_database_content_root_sha256
            .as_ref()
            .map(SecurityDigestV1::bytes)
            != Some(&final_state.business_content_root_sha256)
        || packet
            .execution_binding
            .external_checkpoint_receipt_sha256
            .as_ref()
            .map(SecurityDigestV1::bytes)
            != Some(&final_state.checkpoint_head_sha256)
        || claim
            .post_database_content_root_sha256
            .as_ref()
            .map(SecurityDigestV1::bytes)
            != Some(&final_state.business_content_root_sha256)
        || claim
            .external_checkpoint_receipt_sha256
            .as_ref()
            .map(SecurityDigestV1::bytes)
            != Some(&final_state.checkpoint_head_sha256)
        || claim.post_database_identity_sha256 != Some(final_state.database_identity_sha256)
        || claim.post_schema_catalog_sha256 != Some(final_state.schema_catalog_sha256)
        || claim.post_generation != Some(final_state.generation)
        || packet.assignment_binding.assignment_set_sha256.bytes()
            != &assignments.assignment_set_sha256
        || packet.assignment_binding.schedule_sha256.bytes() != &assignments.schedule_sha256
        || packet
            .assignment_binding
            .assignment_record_set_sha256
            .bytes()
            != &assignments.assignment_record_set_sha256
        || packet
            .assignment_binding
            .operation_descriptor_set_sha256
            .bytes()
            != &assignments.operation_descriptor_set_sha256
        || packet.assignment_binding
            != (PostRunAssignmentBindingV1 {
                assignment_record_count: 60,
                assignment_record_set_sha256: SecurityDigestV1::from_array(
                    assignments.assignment_record_set_sha256,
                )?,
                assignment_set_sha256: SecurityDigestV1::from_array(
                    assignments.assignment_set_sha256,
                )?,
                membership_profile: ASSIGNMENT_MEMBERSHIP_PROFILE_V1.into(),
                operation_descriptor_set_sha256: SecurityDigestV1::from_array(
                    assignments.operation_descriptor_set_sha256,
                )?,
                schedule_sha256: SecurityDigestV1::from_array(assignments.schedule_sha256)?,
            })
        || claim.assignment_binding.assignment_set_sha256.bytes()
            != &assignments.assignment_set_sha256
        || claim.assignment_binding.schedule_sha256.bytes() != &assignments.schedule_sha256
        || accounting.assignment_set_sha256 != assignments.assignment_set_sha256
        || accounting.schedule_sha256 != assignments.schedule_sha256
        || accounting.assignment_record_set_sha256 != assignments.assignment_record_set_sha256
        || accounting.operation_descriptor_set_sha256 != assignments.operation_descriptor_set_sha256
        || accounting.catalog_sha256 != authorized.subject.catalog_sha256
        || accounting.classifier_source_sha256 != authorized.subject.classifier_source_sha256
        || accounting.classifier_binary_sha256 != authorized.subject.classifier_binary_sha256
        || accounting.expected_oracle_sha256 != authorized.subject.expected_oracle_sha256
        || accounting.observation_schema_sha256 != authorized.subject.s17_observation_schema_sha256
        || accounting.plan_sha256 != authorized.subject.s17_plan_sha256
        || accounting.full_catalog_row_count != 5_639
        || accounting.cross_field_rule_count != 32
        || accounting.assignment_count != 60
        || accounting.ol00_assignment_count != 1
        || accounting.ol04_assignment_count != 6
        || accounting.ol05_assignment_count != 53
        || accounting.pidfd_sigkill_count != 59
        || accounting.fresh_exec_count != 59
        || accounting.validated_phase_count != 113
        || accounting.unique_match_count != 113
        || accounting.zero_match_count != 0
        || accounting.multiple_match_count != 0
        || accounting.successful_claim_count != 1
        || accounting.retry_count != 0
        || accounting.assignment_prefilter_used
        || packet.assigned_denominator.ol00_count != accounting.ol00_assignment_count
        || packet.assigned_denominator.ol04_count != accounting.ol04_assignment_count
        || packet.assigned_denominator.ol05_count != accounting.ol05_assignment_count
        || packet.assigned_denominator.total_count != accounting.assignment_count
        || packet.observed_counts.claim_commits != accounting.successful_claim_count
        || packet.observed_counts.assigned_attempts != accounting.assignment_count
        || packet.observed_counts.pidfd_sigkill_attempts != accounting.pidfd_sigkill_count
        || packet.observed_counts.fresh_exec_reads != accounting.fresh_exec_count
        || packet.observed_counts.phase_records != accounting.phase_record_set_count
        || accounting.phase_record_set_count != accounting.validated_phase_count
        || packet.observed_counts.raw_observations != accounting.observation_count
        || accounting.observation_count != accounting.assignment_count
        || packet.observed_counts.action_start_receipts != accounting.assignment_count
        || packet.observed_counts.automatic_retries != accounting.retry_count
        || packet.validator_binding.expected_phase_record_count != accounting.phase_record_set_count
        || packet.validator_binding.frozen_catalog_sha256.bytes() != &accounting.catalog_sha256
        || packet.validator_binding.ruleset_sha256.bytes() != &accounting.validator_ruleset_sha256
        || packet.validator_binding.validator_source_sha256.bytes()
            != &accounting.classifier_source_sha256
        || packet.validator_binding.validator_binary_sha256.bytes()
            != &accounting.classifier_binary_sha256
        || packet.validator_binding.validator_toolchain_sha256.bytes()
            != &accounting.validator_toolchain_sha256
        || packet.receipt_chain != receipts.receipt_chain
        || !postrun_s17_commitments_match_v1(packet, receipts, s17_commitments)
        || packet.receipt_chain.control_snapshot_sha256 != final_control.digest
        || packet.receipt_chain.preflight_receipt_sha256 != preflight.digest
        || packet.receipt_chain.claim_packet_sha256 != claim.digest
        || packet
            .receipt_chain
            .raw_observation_set_sha256
            .as_ref()
            .map(SecurityDigestV1::bytes)
            != Some(&accounting.observation_set_sha256)
    {
        return Err(aligned_error(
            "s20b_aligned_postrun_authority",
            "post-run bundle does not match owner, assignment, claim, committed-state, receipt, or S17 evidence",
        ));
    }
    Ok(())
}

fn validate_complete_postrun_packet_v1(
    raw: &[u8],
    authorized: &AuthorizedUnclaimedS19SubjectV1,
    assignments: &ValidatedAuthorizedAssignmentSetV1,
    preflight: &ValidatedPreflightReceiptTokenV1,
    final_control: &ValidatedControlSnapshotTokenV1,
    claim: &ValidatedClaimPacketTokenV1,
    final_state: &ValidatedCommittedDatabaseStateV1,
    s17: &ValidatedS17BatchV1,
    receipts: &ValidatedPostRunReceiptFactsV1,
) -> AuthorizationResult<ValidatedPostRunBundleTokenV1> {
    let packet = parse_postrun_packet_v1(raw)?;
    packet.validate_shape_v1()?;
    complete_postrun_authority_matches_v1(
        &packet,
        authorized,
        assignments,
        preflight,
        final_control,
        claim,
        final_state,
        s17,
        receipts,
    )?;
    let digest = recompute_top_level_self_v1(&packet, POSTRUN_SELF_KEY_V1, POSTRUN_DOMAIN_V1)?;
    if digest != packet.post_run_bundle_sha256 {
        return Err(aligned_error(
            "s20b_aligned_postrun_self",
            "post-run bundle self digest does not recompute",
        ));
    }
    Ok(ValidatedPostRunBundleTokenV1 {
        digest,
        state: packet.bundle_state,
    })
}

fn build_complete_postrun_packet_v1(
    packet: PostRunReceiptBundlePacketV1,
    authorized: &AuthorizedUnclaimedS19SubjectV1,
    assignments: &ValidatedAuthorizedAssignmentSetV1,
    preflight: &ValidatedPreflightReceiptTokenV1,
    final_control: &ValidatedControlSnapshotTokenV1,
    claim: &ValidatedClaimPacketTokenV1,
    final_state: &ValidatedCommittedDatabaseStateV1,
    s17: &ValidatedS17BatchV1,
    receipts: &ValidatedPostRunReceiptFactsV1,
) -> AuthorizationResult<CanonicalBuiltPacketV1> {
    complete_postrun_authority_matches_v1(
        &packet,
        authorized,
        assignments,
        preflight,
        final_control,
        claim,
        final_state,
        s17,
        receipts,
    )?;
    seal_postrun_packet_v1(packet)
}

#[cfg(test)]
fn seal_synthetic_control_fixture_v1(
    mut packet: ControlSnapshotPacketV1,
) -> AuthorizationResult<CanonicalBuiltPacketV1> {
    packet.validate_shape_v1()?;
    if !packet.test_only || !packet.synthetic {
        return Err(aligned_error(
            "s20b_aligned_fixture_only",
            "fixture-only control constructor accepts only explicit synthetic packets",
        ));
    }
    let digest = recompute_top_level_self_v1(&packet, CONTROL_SELF_KEY_V1, CONTROL_DOMAIN_V1)?;
    packet.control_snapshot_sha256 = digest;
    Ok(CanonicalBuiltPacketV1 {
        canonical_bytes: serialize_canonical_v1(&packet)?,
        digest,
    })
}

#[cfg(test)]
fn fixture_committed_database_state_v1(
    control: &ControlSnapshotPacketV1,
) -> ValidatedCommittedDatabaseStateV1 {
    // Construction is intentionally test-only.  Production callers can obtain
    // this opaque ancestor token only from validate_committed_database_state_v1.
    ValidatedCommittedDatabaseStateV1 {
        database_identity_sha256: *control.ledger_binding.database_identity_sha256.bytes(),
        schema_catalog_sha256: *control
            .ledger_binding
            .authority_control_schema_sha256
            .bytes(),
        business_content_root_sha256: *control.ledger_binding.database_content_root_sha256.bytes(),
        generation: control.ledger_binding.checkpoint_monotonic_counter,
        checkpoint_head_sha256: *control
            .ledger_binding
            .external_checkpoint_receipt_sha256
            .bytes(),
        checkpoint_provider_identity_sha256: *control
            .ledger_binding
            .checkpoint_provider_identity_sha256
            .bytes(),
        independent_failure_domain_proved: false,
    }
}

#[cfg(test)]
struct ValidatedSyntheticFixtureChainV1 {
    context_sha256: SecurityDigestV1,
    control_sha256: SecurityDigestV1,
    preflight_sha256: SecurityDigestV1,
    claim_sha256: SecurityDigestV1,
    postrun_sha256: SecurityDigestV1,
}

#[cfg(test)]
fn validate_synthetic_fixture_chain_v1(
    control_repository: &[u8],
    preflight_repository: &[u8],
    claim_repository: &[u8],
    postrun_repository: &[u8],
) -> AuthorizationResult<ValidatedSyntheticFixtureChainV1> {
    let control_raw = repository_payload_v1(control_repository)?;
    let preflight_raw = repository_payload_v1(preflight_repository)?;
    let claim_raw = repository_payload_v1(claim_repository)?;
    let postrun_raw = repository_payload_v1(postrun_repository)?;
    let control = parse_control_packet_v1(control_raw)?;
    let preflight = parse_preflight_packet_v1(preflight_raw)?;
    let claim = parse_claim_packet_v1(claim_raw)?;
    let postrun = parse_postrun_packet_v1(postrun_raw)?;
    control.validate_shape_v1()?;
    preflight.validate_shape_v1()?;
    claim.validate_shape_v1()?;
    postrun.validate_shape_v1()?;
    if !control.test_only || !preflight.test_only || !claim.test_only || !postrun.test_only {
        return Err(aligned_error(
            "s20b_aligned_fixture_only",
            "synthetic chain validator accepts only explicit test-only packets",
        ));
    }

    let mut rebuilt_preflight = preflight.clone();
    let context_sha256 = rebuilt_preflight.rebuild_context_v1()?;
    if rebuilt_preflight.preflight_context != preflight.preflight_context
        || rebuilt_preflight.phase_bindings.preflight_context_sha256
            != preflight.phase_bindings.preflight_context_sha256
    {
        return Err(aligned_error(
            "s20b_aligned_fixture_context",
            "fixture preflight component or context digest drifted",
        ));
    }
    let control_sha256 =
        recompute_top_level_self_v1(&control, CONTROL_SELF_KEY_V1, CONTROL_DOMAIN_V1)?;
    let preflight_sha256 =
        recompute_top_level_self_v1(&preflight, PREFLIGHT_SELF_KEY_V1, PREFLIGHT_DOMAIN_V1)?;
    let claim_sha256 = recompute_top_level_self_v1(
        &claim,
        CLAIM_SELF_KEY_V1,
        ClaimPacketKindV2::SingleUseClaimOutcomeReceipt.domain(),
    )?;
    let postrun_sha256 =
        recompute_top_level_self_v1(&postrun, POSTRUN_SELF_KEY_V1, POSTRUN_DOMAIN_V1)?;
    if control.control_snapshot_sha256 != control_sha256
        || preflight.preflight_receipt_sha256 != preflight_sha256
        || claim.claim_packet_sha256 != claim_sha256
        || postrun.post_run_bundle_sha256 != postrun_sha256
    {
        return Err(aligned_error(
            "s20b_aligned_fixture_self",
            "one fixture top-level self digest does not recompute",
        ));
    }
    let claim_attempt = claim.claim_attempt.as_ref().unwrap();
    if control.snapshot_phase != ControlPhaseV2::PreflightBeforeClaim
        || control.phase_parent.parent_kind != ParentKindV1::PreflightContext
        || control.phase_parent.parent_sha256 != context_sha256
        || preflight.phase_bindings.control_snapshot_sha256 != control_sha256
        || claim.parent_bindings.preflight_receipt_sha256 != Some(preflight_sha256)
        || claim.parent_bindings.control_snapshot_sha256 != Some(control_sha256)
        || claim_attempt
            .cas_parameter_bindings
            .p04_preflight_receipt_sha256
            != preflight_sha256
        || claim_attempt
            .cas_parameter_bindings
            .p05_control_snapshot_sha256
            != control_sha256
        || postrun.execution_binding.claim_packet_sha256 != claim_sha256
        || postrun.receipt_chain.preflight_receipt_sha256 != preflight_sha256
        || postrun.receipt_chain.control_snapshot_sha256 != control_sha256
        || postrun.receipt_chain.claim_packet_sha256 != claim_sha256
    {
        return Err(aligned_error(
            "s20b_aligned_fixture_parent",
            "fixture parent DAG does not recompute in context-control-preflight-claim-postrun order",
        ));
    }
    if control.authorization_binding != preflight.authorization_binding.common()
        || claim.authorization_binding != control.authorization_binding
        || postrun.authorization_binding != claim.authorization_binding
        || control.run_binding.attempt_id_sha256 != preflight.run_binding.attempt_id_sha256
        || control.run_binding.run_id_sha256 != preflight.run_binding.run_id_sha256
        || control.run_binding.run_assignment_id_sha256
            != preflight.run_binding.run_assignment_id_sha256
        || control.run_binding.capability_nonce_sha256
            != preflight.run_binding.capability_nonce_sha256
        || control.run_binding.controller_binary_sha256
            != preflight.run_binding.controller_binary_sha256
        || control.run_binding.runner_binary_sha256 != preflight.run_binding.runner_binary_sha256
        || claim_attempt.attempt_id_sha256 != preflight.run_binding.attempt_id_sha256
        || claim_attempt.attempt_tombstone_sha256 != preflight.run_binding.attempt_tombstone_sha256
        || claim_attempt.run_assignment_id_sha256 != preflight.run_binding.run_assignment_id_sha256
        || postrun.execution_binding.attempt_id_sha256 != preflight.run_binding.attempt_id_sha256
        || postrun.execution_binding.attempt_tombstone_sha256
            != preflight.run_binding.attempt_tombstone_sha256
        || postrun.execution_binding.run_id_sha256 != preflight.run_binding.run_id_sha256
        || postrun.execution_binding.run_assignment_id_sha256
            != preflight.run_binding.run_assignment_id_sha256
        || postrun.execution_binding.capability_nonce_sha256
            != preflight.run_binding.capability_nonce_sha256
        || postrun.execution_binding.controller_binary_sha256
            != preflight.run_binding.controller_binary_sha256
        || postrun.execution_binding.runner_binary_sha256
            != preflight.run_binding.runner_binary_sha256
        || claim_attempt.cas_parameter_bindings.p02_run_id_sha256
            != preflight.run_binding.run_id_sha256
        || claim_attempt
            .cas_parameter_bindings
            .p03_controller_binary_sha256
            != preflight.run_binding.controller_binary_sha256
        || claim_attempt
            .cas_parameter_bindings
            .p15_runner_binary_sha256
            != preflight.run_binding.runner_binary_sha256
        || claim_attempt
            .cas_parameter_bindings
            .p16_capability_nonce_sha256
            != preflight.run_binding.capability_nonce_sha256
    {
        return Err(aligned_error(
            "s20b_aligned_fixture_identity",
            "fixture immutable authorization or run tuple drifted across packets",
        ));
    }
    let control_assignment = &control.assignment_binding;
    if preflight.assignment_binding.assignment_set_sha256
        != control_assignment.assignment_set_sha256
        || preflight.assignment_binding.schedule_sha256 != control_assignment.schedule_sha256
        || preflight.assignment_binding.assignment_record_sha256
            != control_assignment.assignment_record_sha256
        || preflight.assignment_binding.operation_descriptor_set_sha256
            != control_assignment.operation_descriptor_set_sha256
        || claim.assignment_binding.assignment_set_sha256
            != control_assignment.assignment_set_sha256
        || claim.assignment_binding.schedule_sha256 != control_assignment.schedule_sha256
        || claim.assignment_binding.assignment_record_sha256
            != control_assignment.assignment_record_sha256
        || claim.assignment_binding.operation_descriptor_set_sha256
            != control_assignment.operation_descriptor_set_sha256
        || postrun.assignment_binding.assignment_set_sha256
            != control_assignment.assignment_set_sha256
        || postrun.assignment_binding.schedule_sha256 != control_assignment.schedule_sha256
        || postrun.assignment_binding.operation_descriptor_set_sha256
            != control_assignment.operation_descriptor_set_sha256
    {
        return Err(aligned_error(
            "s20b_aligned_fixture_assignment",
            "fixture assignment or operation-set tuple drifted across packets",
        ));
    }
    Ok(ValidatedSyntheticFixtureChainV1 {
        context_sha256,
        control_sha256,
        preflight_sha256,
        claim_sha256,
        postrun_sha256,
    })
}

#[cfg(test)]
mod tests {
    use super::*;

    const CONTROL_FIXTURE: &[u8] = include_bytes!(concat!(
        env!("CARGO_MANIFEST_DIR"),
        "/../../docs/design/fixtures/biocortex-ab-track-b-owned-lab-control-snapshot-synthetic-s20b-v0.json"
    ));
    const PREFLIGHT_FIXTURE: &[u8] = include_bytes!(concat!(
        env!("CARGO_MANIFEST_DIR"),
        "/../../docs/design/fixtures/biocortex-ab-track-b-owned-lab-preflight-receipt-synthetic-s20b-v0.json"
    ));
    const CLAIM_FIXTURE: &[u8] = include_bytes!(concat!(
        env!("CARGO_MANIFEST_DIR"),
        "/../../docs/design/fixtures/biocortex-ab-track-b-owned-lab-authority-control-claim-synthetic-s20b-v0.json"
    ));
    const POSTRUN_FIXTURE: &[u8] = include_bytes!(concat!(
        env!("CARGO_MANIFEST_DIR"),
        "/../../docs/design/fixtures/biocortex-ab-track-b-owned-lab-post-run-receipt-bundle-synthetic-s20b-v0.json"
    ));

    fn repository_bytes(canonical: &[u8]) -> Vec<u8> {
        let mut output = canonical.to_vec();
        output.push(b'\n');
        output
    }

    fn reseal_top_level_mutation(
        repository: &[u8],
        self_key: &'static str,
        domain: &[u8],
        mutate: impl FnOnce(&mut Value),
    ) -> Vec<u8> {
        let raw = repository_payload_v1(repository).unwrap();
        let mut value = parse_restricted_canonical(raw).unwrap();
        mutate(&mut value);
        value.as_object_mut().unwrap().remove(self_key).unwrap();
        let payload = restricted_canonical_bytes(&value).unwrap();
        let digest = framed_digest(domain, &[&payload]).unwrap();
        value
            .as_object_mut()
            .unwrap()
            .insert(self_key.into(), Value::String(hex32(&digest)));
        repository_bytes(&restricted_canonical_bytes(&value).unwrap())
    }

    #[test]
    fn s20b_schema_aligned_four_repository_fixtures_roundtrip_exactly() {
        let chain = validate_synthetic_fixture_chain_v1(
            CONTROL_FIXTURE,
            PREFLIGHT_FIXTURE,
            CLAIM_FIXTURE,
            POSTRUN_FIXTURE,
        )
        .unwrap();
        let control =
            parse_control_packet_v1(repository_payload_v1(CONTROL_FIXTURE).unwrap()).unwrap();
        let preflight =
            parse_preflight_packet_v1(repository_payload_v1(PREFLIGHT_FIXTURE).unwrap()).unwrap();
        let claim = parse_claim_packet_v1(repository_payload_v1(CLAIM_FIXTURE).unwrap()).unwrap();
        let postrun =
            parse_postrun_packet_v1(repository_payload_v1(POSTRUN_FIXTURE).unwrap()).unwrap();
        let fixture_state = fixture_committed_database_state_v1(&control);
        assert_eq!(
            fixture_state.business_content_root_sha256,
            *control.ledger_binding.database_content_root_sha256.bytes()
        );
        let rebuilt_control = seal_synthetic_control_fixture_v1(control).unwrap();
        let rebuilt_preflight = build_preflight_packet_v1(preflight).unwrap();
        let rebuilt_claim = seal_claim_packet_v1(claim).unwrap();
        let rebuilt_postrun = seal_postrun_packet_v1(postrun).unwrap();
        assert_eq!(
            repository_bytes(&rebuilt_control.canonical_bytes),
            CONTROL_FIXTURE
        );
        assert_eq!(
            repository_bytes(&rebuilt_preflight.canonical_bytes),
            PREFLIGHT_FIXTURE
        );
        assert_eq!(
            repository_bytes(&rebuilt_claim.canonical_bytes),
            CLAIM_FIXTURE
        );
        assert_eq!(
            repository_bytes(&rebuilt_postrun.canonical_bytes),
            POSTRUN_FIXTURE
        );
        assert_eq!(chain.control_sha256, rebuilt_control.digest);
        assert_eq!(chain.preflight_sha256, rebuilt_preflight.digest);
        assert_eq!(chain.claim_sha256, rebuilt_claim.digest);
        assert_eq!(chain.postrun_sha256, rebuilt_postrun.digest);
        assert_ne!(chain.context_sha256, chain.control_sha256);
    }

    #[test]
    fn s20b_schema_aligned_p01_and_p24_cas_mutations_reject() {
        let p01 = reseal_top_level_mutation(
            CLAIM_FIXTURE,
            CLAIM_SELF_KEY_V1,
            CLAIM_OUTCOME_DOMAIN_V1,
            |value| {
                value["claim_attempt"]["cas_parameter_bindings"]["p01_next_revision"] =
                    Value::Number(13_u64.into());
            },
        );
        let parsed = parse_claim_packet_v1(repository_payload_v1(&p01).unwrap()).unwrap();
        assert!(parsed.validate_shape_v1().is_err());

        let p24 = reseal_top_level_mutation(
            CLAIM_FIXTURE,
            CLAIM_SELF_KEY_V1,
            CLAIM_OUTCOME_DOMAIN_V1,
            |value| {
                value["claim_attempt"]["cas_parameter_bindings"]["p24_sqlite_schema_sha256"] =
                    Value::String("f".repeat(64));
            },
        );
        let parsed = parse_claim_packet_v1(repository_payload_v1(&p24).unwrap()).unwrap();
        assert!(parsed.validate_shape_v1().is_err());
    }

    #[test]
    fn s20b_schema_aligned_parent_and_self_mutations_reject_after_reseal() {
        let parent = reseal_top_level_mutation(
            POSTRUN_FIXTURE,
            POSTRUN_SELF_KEY_V1,
            POSTRUN_DOMAIN_V1,
            |value| {
                value["receipt_chain"]["claim_packet_sha256"] = Value::String("f".repeat(64));
            },
        );
        assert!(validate_synthetic_fixture_chain_v1(
            CONTROL_FIXTURE,
            PREFLIGHT_FIXTURE,
            CLAIM_FIXTURE,
            &parent,
        )
        .is_err());

        let mut self_value =
            parse_restricted_canonical(repository_payload_v1(CLAIM_FIXTURE).unwrap()).unwrap();
        self_value[CLAIM_SELF_KEY_V1] = Value::String("f".repeat(64));
        let self_mutation = repository_bytes(&restricted_canonical_bytes(&self_value).unwrap());
        assert!(validate_synthetic_fixture_chain_v1(
            CONTROL_FIXTURE,
            PREFLIGHT_FIXTURE,
            &self_mutation,
            POSTRUN_FIXTURE,
        )
        .is_err());
    }

    #[test]
    fn s20b_schema_aligned_missing_rollback_and_unknown_reads_are_tagged() {
        let control =
            parse_control_packet_v1(repository_payload_v1(CONTROL_FIXTURE).unwrap()).unwrap();
        let mut missing = control.clone();
        missing.read_outcome = ControlReadOutcomeV1::ClaimRowMissing;
        missing.claim_view = TaggedClaimViewV1 {
            read_error_class: Some(ClaimReadErrorClassV1::Missing),
            revision: None,
            row_core_sha256: None,
            row_presence: ClaimRowPresenceV1::RowMissing,
            state: None,
        };
        assert!(missing.validate_shape_v1().is_ok());
        missing.claim_view.revision = Some(1);
        assert!(missing.validate_shape_v1().is_err());

        let mut rollback = control.clone();
        rollback.read_outcome = ControlReadOutcomeV1::RollbackDetected;
        rollback.revocation_view.read_state = RevocationReadStateV1::RollbackDetected;
        rollback.revocation_view.rollback_detected = Some(true);
        assert!(rollback.validate_shape_v1().is_ok());
        rollback.revocation_view.rollback_detected = Some(false);
        assert!(rollback.validate_shape_v1().is_err());

        let mut unknown = control;
        unknown.read_outcome = ControlReadOutcomeV1::ReadUnknown;
        unknown.stop_view = TaggedStopViewV1 {
            ledger_revision: None,
            policy_identity_sha256: None,
            read_state: StopReadStateV1::ReadUnknown,
            trigger_receipt_sha256: None,
        };
        assert!(unknown.validate_shape_v1().is_ok());
        unknown.stop_view.ledger_revision = Some(1);
        assert!(unknown.validate_shape_v1().is_err());
    }

    #[test]
    fn s20b_schema_aligned_unknown_commit_never_fabricates_zero_rows() {
        let mut claim =
            parse_claim_packet_v1(repository_payload_v1(CLAIM_FIXTURE).unwrap()).unwrap();
        claim.test_only = false;
        claim.synthetic = false;
        claim.claim_packet_state = ClaimPacketStateV2::UnknownOutcomeTerminalHardLock;
        let commit = claim.commit_outcome.as_mut().unwrap();
        commit.acknowledgement_state = CommitAcknowledgementV1::Unknown;
        commit.affected_rows = None;
        commit.row_mutation_state = RowMutationStateV1::Unknown;
        commit.post_database_content_root_sha256 = None;
        commit.external_checkpoint_receipt_sha256 = None;
        commit.terminal_hard_lock = true;
        let permit = claim.permit_outcome.as_mut().unwrap();
        permit.permit_eligible_after_commit = false;
        permit.process_local_affine_permit_issued = false;
        assert!(claim.validate_shape_v1().is_ok());
        claim.commit_outcome.as_mut().unwrap().affected_rows = Some(0);
        assert!(claim.validate_shape_v1().is_err());
    }

    #[test]
    fn s20b_schema_aligned_postcommit_prepermit_crash_is_distinct() {
        let mut claim =
            parse_claim_packet_v1(repository_payload_v1(CLAIM_FIXTURE).unwrap()).unwrap();
        claim.test_only = false;
        claim.synthetic = false;
        claim.claim_packet_state = ClaimPacketStateV2::CommittedPrePermitCrashTerminal;
        let binding = claim.authorization_binding.authorization_id_sha256;
        let commit = claim.commit_outcome.as_mut().unwrap();
        commit.acknowledgement_state = CommitAcknowledgementV1::Committed;
        commit.affected_rows = Some(1);
        commit.row_mutation_state = RowMutationStateV1::ConsumedForExactRun;
        commit.post_database_content_root_sha256 = Some(binding);
        commit.external_checkpoint_receipt_sha256 = Some(binding);
        commit.terminal_hard_lock = true;
        let permit = claim.permit_outcome.as_mut().unwrap();
        permit.permit_eligible_after_commit = true;
        permit.process_local_affine_permit_issued = false;
        assert!(claim.validate_shape_v1().is_ok());
        claim
            .permit_outcome
            .as_mut()
            .unwrap()
            .process_local_affine_permit_issued = true;
        assert!(claim.validate_shape_v1().is_err());
    }

    #[test]
    fn s20b_schema_aligned_repository_lf_is_excluded_exactly_once() {
        assert!(repository_payload_v1(CONTROL_FIXTURE).is_ok());
        let without_lf = &CONTROL_FIXTURE[..CONTROL_FIXTURE.len() - 1];
        assert!(repository_payload_v1(without_lf).is_err());
        let mut double_lf = CONTROL_FIXTURE.to_vec();
        double_lf.push(b'\n');
        assert!(repository_payload_v1(&double_lf).is_err());
    }

    #[test]
    fn s20b_schema_aligned_s17_exposed_commitment_mutations_reject() {
        let mut packet =
            parse_postrun_packet_v1(repository_payload_v1(POSTRUN_FIXTURE).unwrap()).unwrap();
        let observation_set = packet.assignment_binding.assignment_set_sha256;
        packet.receipt_chain.raw_observation_set_sha256 = Some(observation_set);
        packet.observed_counts.raw_observations = 60;
        packet.observed_counts.phase_records = 113;
        let receipts = ValidatedPostRunReceiptFactsV1 {
            receipt_chain: packet.receipt_chain.clone(),
            observation_count: 60,
            observation_set_sha256: *observation_set.bytes(),
            phase_record_set_count: 113,
            phase_record_set_sha256: [0x3c; 32],
        };
        let commitments = S17PostRunCommitmentsV1 {
            assignment_record_set_sha256: *packet
                .assignment_binding
                .assignment_record_set_sha256
                .bytes(),
            operation_descriptor_set_sha256: *packet
                .assignment_binding
                .operation_descriptor_set_sha256
                .bytes(),
            observation_count: 60,
            observation_set_sha256: *observation_set.bytes(),
            phase_record_set_count: 113,
            phase_record_set_sha256: receipts.phase_record_set_sha256,
        };
        assert!(postrun_s17_commitments_match_v1(
            &packet,
            &receipts,
            commitments,
        ));

        let mut mutation = commitments;
        mutation.assignment_record_set_sha256 = [0xfe; 32];
        assert!(!postrun_s17_commitments_match_v1(
            &packet, &receipts, mutation,
        ));
        mutation = commitments;
        mutation.operation_descriptor_set_sha256 = [0xfd; 32];
        assert!(!postrun_s17_commitments_match_v1(
            &packet, &receipts, mutation,
        ));
        mutation = commitments;
        mutation.observation_count += 1;
        assert!(!postrun_s17_commitments_match_v1(
            &packet, &receipts, mutation,
        ));
        mutation = commitments;
        mutation.observation_set_sha256 = [0xfc; 32];
        assert!(!postrun_s17_commitments_match_v1(
            &packet, &receipts, mutation,
        ));
        mutation = commitments;
        mutation.phase_record_set_count += 1;
        assert!(!postrun_s17_commitments_match_v1(
            &packet, &receipts, mutation,
        ));
        mutation = commitments;
        mutation.phase_record_set_sha256 = [0xfb; 32];
        assert!(!postrun_s17_commitments_match_v1(
            &packet, &receipts, mutation,
        ));
    }

    #[test]
    fn s20b_schema_aligned_schema_and_semantic_contract_mutations_reject() {
        let schema = reseal_top_level_mutation(
            CONTROL_FIXTURE,
            CONTROL_SELF_KEY_V1,
            CONTROL_DOMAIN_V1,
            |value| value["schema"] = Value::String("wrong.schema".into()),
        );
        let parsed = parse_control_packet_v1(repository_payload_v1(&schema).unwrap()).unwrap();
        assert!(parsed.validate_shape_v1().is_err());

        let semantic = reseal_top_level_mutation(
            PREFLIGHT_FIXTURE,
            PREFLIGHT_SELF_KEY_V1,
            PREFLIGHT_DOMAIN_V1,
            |value| {
                value["semantic_validation"]["required_rules"][0] =
                    Value::String("CALLER_REPORTED_MATCH_IS_AUTHORITY".into());
            },
        );
        let parsed = parse_preflight_packet_v1(repository_payload_v1(&semantic).unwrap()).unwrap();
        assert!(parsed.validate_shape_v1().is_err());
    }
}
