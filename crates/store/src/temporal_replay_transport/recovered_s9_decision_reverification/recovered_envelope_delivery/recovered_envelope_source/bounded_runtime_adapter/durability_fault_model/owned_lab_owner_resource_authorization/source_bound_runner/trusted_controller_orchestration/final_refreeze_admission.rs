//! S21A final-refreeze subject and external-input admission kernel.
//!
//! This module is private, default-off, and deliberately non-live. It only
//! validates canonical bytes and already-validated opaque facts. It has no
//! constructor for real external facts and returns no claim, permit, runner,
//! checkpoint port, executor, or side-effect capability.

#![cfg_attr(not(test), allow(dead_code))]

use super::*;
use ring::signature::{UnparsedPublicKey, ED25519};
use serde::{Deserialize, Serialize};
use serde_json::Value;

const S21A_FINAL_REFREEZE_SUBJECT_BUILDER_PARSER_VALIDATOR_IMPLEMENTED: bool = true;
const S21A_NEW_OWNER_SIGNATURE_VERIFIER_IMPLEMENTED: bool = true;
const S21A_OPAQUE_EXTERNAL_INPUT_ADMISSION_IMPLEMENTED: bool = true;
const S21A_EXTERNAL_INPUT_DIGEST_CROSS_BINDING_IMPLEMENTED: bool = true;
const S21A_TYPED_EXTERNAL_INPUT_PACKET_VALIDATOR_IMPLEMENTED: bool = true;
const S21A_REAL_EXTERNAL_FACT_CONSTRUCTOR_PRESENT: bool = false;
const S21A_LIVE_BACKEND_PRESENT: bool = false;
const S21A_SIDE_EFFECTS_UNLOCKED: &str = "NONE";

const S20B_INTEGRATION_COMMIT: &str = "33c2c4df78ef302fd0538986b95fa40a3711ba86";
const S20B_INTEGRATION_TREE: &str = "6f92c687b61e1433e693ca6cd1bc6390dda97f29";
const S20B_SOURCE_COMMIT: &str = "a1948daaf466563358fcbf054b2bebef8e966777";
const S20B_SOURCE_TREE: &str = "eca0de065221621fcc70941adaefac1f4315bd3e";
const S20B_INTEGRATED_ARCHIVE_SHA256: &str =
    "cde7d7e71591265cc26f57e378448fa066b0083ef4b32cbebd3ec8ca27a8b43e";
const S20B_SUCCESSOR_GATE_SHA256: &str =
    "4381feec604a16c99c87e95c6a81370fa138fe75a528855b71a52f9f911e23a7";
const S20B_GATE_SHA256: &str = "85453f80c4e095ceb39abecc8c654a3cc660261e957db7e00848502a099802d8";
const S20B_CHECKER_SHA256: &str =
    "d4e3b789f03fdfb1190006629fdf2acc17ebbddebf13ebb20cdf2e03d3ed2a6d";
const S20B_REPORT_SHA256: &str = "12bb0f4902c01564904b8b03633ba788bf7587f043c5fd8b82c7fc961ef36ff1";
const CARGO_LOCK_SHA256: &str = "408e0aa5e6bc3f2a318719c57419ece60b507df0a11c1738fd40dda66aac1f59";
const ASSIGNMENT_SET_SHA256: &str =
    "b3a7025a488e9aefc6724869f75ab76a482002224bee90c075e9379101ee7264";
const SCHEDULE_SHA256: &str = "8c0129d150d918523c122dbf3afb4e7c6abb3ce7ca957204252c115a7f1def15";
const ASSIGNMENT_RECORD_SET_SHA256: &str =
    "7a927eba7eb691990b32c7987bea5c0fdce15c51d37792f8ca45c3bddb556bc6";
const OPERATION_DESCRIPTOR_SET_SHA256: &str =
    "a00feb5745c83fc20d5ad84f66877289c9108b29371697ceb8cf13e3fb142db0";
const CATALOG_SHA256: &str = "44d9f48318e221d961819f9f189c2b355a4fce42351844d7cd5b4a84e72b1f0d";
const VALIDATOR_RULESET_SHA256: &str =
    "84b374eaadc65610fbfc660b5fe69f840229a03c39b196414b7300ec045b705d";
const S21A_REPOSITORY_PUBLIC_KAT_KEY_ID: &str = "s21a-synthetic-public-kat-v1";
const S21A_REPOSITORY_PUBLIC_KAT_KEY_HEX: &str =
    "d75a980182b10ab7d54bfed3c964073a0ee172f3daa62325af021a68f707511a";

const CANONICALIZATION: &str =
    "AB_RESTRICTED_CANONICAL_JSON_S21A_V1_COMPACT_SORTED_KEYS_ASCII_VALUES_NO_FLOAT";
const DIGEST_FRAMING: &str =
    "U32BE_DOMAIN_LENGTH_DOMAIN_U64BE_CANONICAL_PAYLOAD_LENGTH_CANONICAL_PAYLOAD";
const SUBJECT_SCHEMA: &str =
    "agent_bridge.memory_temporal_owned_lab_final_refreeze_subject_s21a.v0";
const SUBJECT_KIND: &str = "S21A_FINAL_REFREEZE_SUBJECT";
const SUBJECT_DOMAIN: &[u8] = b"agent-bridge/biocortex/owned-lab/s21a/final-refreeze-subject/v1";
const ANCHOR_SCHEMA: &str = "agent_bridge.memory_temporal_owned_lab_owner_trust_anchor_s21a.v0";
const ANCHOR_KIND: &str = "S21A_OWNER_TRUST_ANCHOR";
const ANCHOR_DOMAIN: &[u8] =
    b"agent-bridge/biocortex/owned-lab/s21a/owner-trust-anchor-document/v1";
const ENVELOPE_SCHEMA: &str =
    "agent_bridge.memory_temporal_owned_lab_owner_authorization_envelope_s21a.v0";
const ENVELOPE_KIND: &str = "S21A_OWNER_AUTHORIZATION_ENVELOPE";
const ENVELOPE_DOMAIN: &[u8] =
    b"agent-bridge/biocortex/owned-lab/s21a/owner-authorization-envelope/v1";
const OWNER_AUDIENCE: &str = "agent-bridge/biocortex/owned-lab/s21a/final-refreeze-owner-review/v1";
const SIGNED_PAYLOAD_DOMAIN: &[u8] =
    b"agent-bridge/biocortex/owned-lab/s21a/owner-authorization-signed-payload/v1";
const SIGNATURE_DOMAIN: &[u8] =
    b"agent-bridge/biocortex/owned-lab/s21a/owner-authorization-signature/v1";
const AUTHORIZATION_ID_DOMAIN: &[u8] =
    b"agent-bridge/biocortex/owned-lab/s21a/owner-authorization-id/v1";
const ADMISSION_SCHEMA: &str =
    "agent_bridge.memory_temporal_owned_lab_external_input_admission_s21a.v0";
const ADMISSION_KIND: &str = "S21A_EXTERNAL_INPUT_ADMISSION_RESULT";
const ADMISSION_DOMAIN: &[u8] =
    b"agent-bridge/biocortex/owned-lab/s21a/external-input-admission/v1";

fn s21a_error(code: &'static str, detail: &'static str) -> OwnedLabAuthorizationError {
    manifest_error(code, detail)
}

fn append_u64_frame(message: &mut Vec<u8>, value: &[u8]) -> AuthorizationResult<()> {
    let length = u64::try_from(value.len())
        .map_err(|_| s21a_error("s21a_frame", "frame length exceeds u64"))?;
    message.extend_from_slice(&length.to_be_bytes());
    message.extend_from_slice(value);
    Ok(())
}

fn framed_payload_digest(domain: &[u8], payload: &[u8]) -> AuthorizationResult<[u8; 32]> {
    let mut message = Vec::with_capacity(4 + domain.len() + 8 + payload.len());
    append_u32_frame(&mut message, domain)?;
    append_u64_frame(&mut message, payload)?;
    Ok(sha256_bytes(&message))
}

fn authorization_id(
    payload_sha256: &[u8; 32],
    signature_sha256: &[u8; 32],
    anchor_sha256: &[u8; 32],
) -> AuthorizationResult<[u8; 32]> {
    let mut message = Vec::with_capacity(4 + AUTHORIZATION_ID_DOMAIN.len() + 3 * 40);
    append_u32_frame(&mut message, AUTHORIZATION_ID_DOMAIN)?;
    append_u64_frame(&mut message, payload_sha256)?;
    append_u64_frame(&mut message, signature_sha256)?;
    append_u64_frame(&mut message, anchor_sha256)?;
    Ok(sha256_bytes(&message))
}

fn signature_message(payload_sha256: &[u8; 32]) -> AuthorizationResult<Vec<u8>> {
    let mut message = Vec::with_capacity(4 + SIGNATURE_DOMAIN.len() + 40);
    append_u32_frame(&mut message, SIGNATURE_DOMAIN)?;
    append_u64_frame(&mut message, payload_sha256)?;
    Ok(message)
}

fn canonical_typed<T: Serialize>(value: &T) -> AuthorizationResult<Vec<u8>> {
    let value = serde_json::to_value(value)
        .map_err(|_| s21a_error("s21a_encode", "typed packet cannot be encoded"))?;
    restricted_canonical_bytes(&value)
}

fn canonical_without_self<T: Serialize>(value: &T, key: &str) -> AuthorizationResult<Vec<u8>> {
    let value = serde_json::to_value(value)
        .map_err(|_| s21a_error("s21a_encode", "typed packet cannot be encoded"))?;
    let mut object = value
        .as_object()
        .cloned()
        .ok_or_else(|| s21a_error("s21a_object", "packet is not an object"))?;
    object
        .remove(key)
        .ok_or_else(|| s21a_error("s21a_self", "self digest field is missing"))?;
    restricted_canonical_bytes(&Value::Object(object))
}

fn packet_digest<T: Serialize>(
    value: &T,
    key: &str,
    domain: &[u8],
) -> AuthorizationResult<[u8; 32]> {
    framed_payload_digest(domain, &canonical_without_self(value, key)?)
}

fn repository_payload(raw: &[u8]) -> AuthorizationResult<&[u8]> {
    if raw.ends_with(b"\n") {
        let payload = &raw[..raw.len() - 1];
        if payload.is_empty() || payload.ends_with(b"\n") {
            return Err(s21a_error(
                "s21a_repository_lf",
                "repository framing must contain exactly one terminal LF",
            ));
        }
        Ok(payload)
    } else {
        Ok(raw)
    }
}

fn parse_typed<T: for<'de> Deserialize<'de>>(raw: &[u8]) -> AuthorizationResult<T> {
    let payload = repository_payload(raw)?;
    let value = parse_restricted_canonical(payload)?;
    serde_json::from_value(value)
        .map_err(|_| s21a_error("s21a_typed_parse", "closed typed packet rejected input"))
}

fn require_sha256(value: &str, code: &'static str) -> AuthorizationResult<[u8; 32]> {
    let digest = decode_hex_fixed::<32>(value)?;
    if !nonzero(&digest) {
        return Err(s21a_error(code, "security digest is all-zero"));
    }
    Ok(digest)
}

fn require_oid(value: &str, code: &'static str) -> AuthorizationResult<[u8; 20]> {
    let oid = decode_hex_fixed::<20>(value)?;
    if !nonzero(&oid) {
        return Err(s21a_error(code, "Git object identity is all-zero"));
    }
    Ok(oid)
}

fn valid_s21_owner_key_id(value: &str) -> bool {
    !value.is_empty()
        && value.len() <= 96
        && value
            .bytes()
            .all(|byte| byte.is_ascii_alphanumeric() || matches!(byte, b'.' | b'_' | b'-'))
}

#[derive(Clone, Debug, Eq, PartialEq, Serialize, Deserialize)]
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
    candidate_reported_matches_authoritative: bool,
}

impl HashingContractV1 {
    fn exact(domain: &[u8], scope: &str, self_field: &str) -> Self {
        Self {
            hash_algorithm: "SHA-256".into(),
            canonicalization: CANONICALIZATION.into(),
            digest_domain: std::str::from_utf8(domain).unwrap().into(),
            digest_framing: DIGEST_FRAMING.into(),
            hash_scope: scope.into(),
            self_hash_field: self_field.into(),
            self_hash_field_excluded: true,
            repository_framing_lf_excluded: true,
            cross_field_semantic_validation_required: true,
            candidate_reported_matches_authoritative: false,
        }
    }
}

#[derive(Clone, Debug, Eq, PartialEq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
struct ParentBindingsV1 {
    backward_edges_only: bool,
    s20b_integration_commit: String,
    s20b_integration_tree: String,
    s20b_source_commit: String,
    s20b_source_tree: String,
    s20b_integrated_archive_sha256: String,
    s20b_successor_gate_sha256: String,
}

#[derive(Clone, Debug, Eq, PartialEq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
struct PostIntegrationRefreezeV1 {
    generated_outside_repository_after_s21a_integration: bool,
    post_integration_refreeze_required: bool,
    s21a_source_commit: Option<String>,
    s21a_source_tree: Option<String>,
    s21a_integration_commit: Option<String>,
    s21a_integration_tree: Option<String>,
    any_post_freeze_change_requires_new_subject_and_owner_decision: bool,
}

#[derive(Clone, Debug, Eq, PartialEq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
struct BuildBindingsV1 {
    exact_integrated_archive_sha256: String,
    cargo_lock_sha256: String,
    controller_binary_sha256: String,
    observer_binary_sha256: String,
    runner_binary_sha256: String,
    validator_binary_sha256: String,
    toolchain_manifest_sha256: String,
    feature_set_sha256: String,
    candidate_supplied_expected_digest_used: bool,
}

#[derive(Clone, Debug, Eq, PartialEq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
struct ArtifactBindingsV1 {
    schema_set_sha256: String,
    assignment_set_sha256: String,
    schedule_sha256: String,
    assignment_record_set_sha256: String,
    operation_descriptor_set_sha256: String,
    catalog_row_count: u64,
    catalog_sha256: String,
    validator_rule_count: u64,
    validator_ruleset_sha256: String,
    target_phase_count: u64,
    s20b_gate_sha256: String,
    s20b_checker_sha256: String,
    s20b_report_sha256: String,
    s20b_source_delta_file_count: u64,
}

#[derive(Clone, Debug, Eq, PartialEq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
struct SubjectNonclaimsV1 {
    subject_is_owner_authority: bool,
    subject_is_owner_signature: bool,
    subject_is_execution_capability: bool,
    schema_conformance_authorizes_live_execution: bool,
    synthetic_fixture_is_signable_final_subject: bool,
    side_effects_unlocked: String,
}

#[derive(Clone, Debug, Eq, PartialEq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
struct S21RefreezeSubjectV1 {
    schema: String,
    packet_kind: String,
    canonicalization: String,
    hashing_contract: HashingContractV1,
    subject_state: String,
    test_only: bool,
    synthetic: bool,
    parent_bindings: ParentBindingsV1,
    post_integration_refreeze: PostIntegrationRefreezeV1,
    build_bindings: BuildBindingsV1,
    artifact_bindings: ArtifactBindingsV1,
    subject_sha256: String,
    nonclaims: SubjectNonclaimsV1,
}

struct IndependentS21RefreezeInputsV1 {
    test_only: bool,
    s21a_source_commit: Option<String>,
    s21a_source_tree: Option<String>,
    s21a_integration_commit: Option<String>,
    s21a_integration_tree: Option<String>,
    build_bindings: BuildBindingsV1,
    artifact_bindings: ArtifactBindingsV1,
}

#[must_use]
struct CanonicalBuiltS21SubjectV1 {
    canonical_bytes: Vec<u8>,
    digest: [u8; 32],
}

#[must_use]
struct VerifiedS21RefreezeSubjectV1 {
    packet: S21RefreezeSubjectV1,
    digest: [u8; 32],
}

fn exact_parent_bindings() -> ParentBindingsV1 {
    ParentBindingsV1 {
        backward_edges_only: true,
        s20b_integration_commit: S20B_INTEGRATION_COMMIT.into(),
        s20b_integration_tree: S20B_INTEGRATION_TREE.into(),
        s20b_source_commit: S20B_SOURCE_COMMIT.into(),
        s20b_source_tree: S20B_SOURCE_TREE.into(),
        s20b_integrated_archive_sha256: S20B_INTEGRATED_ARCHIVE_SHA256.into(),
        s20b_successor_gate_sha256: S20B_SUCCESSOR_GATE_SHA256.into(),
    }
}

fn validate_build_and_artifacts(
    build: &BuildBindingsV1,
    artifacts: &ArtifactBindingsV1,
) -> AuthorizationResult<()> {
    for value in [
        &build.exact_integrated_archive_sha256,
        &build.controller_binary_sha256,
        &build.observer_binary_sha256,
        &build.runner_binary_sha256,
        &build.validator_binary_sha256,
        &build.toolchain_manifest_sha256,
        &build.feature_set_sha256,
        &artifacts.schema_set_sha256,
        &artifacts.catalog_sha256,
        &artifacts.validator_ruleset_sha256,
    ] {
        require_sha256(value, "s21a_subject_digest")?;
    }
    if build.cargo_lock_sha256 != CARGO_LOCK_SHA256
        || build.candidate_supplied_expected_digest_used
        || artifacts.assignment_set_sha256 != ASSIGNMENT_SET_SHA256
        || artifacts.schedule_sha256 != SCHEDULE_SHA256
        || artifacts.assignment_record_set_sha256 != ASSIGNMENT_RECORD_SET_SHA256
        || artifacts.operation_descriptor_set_sha256 != OPERATION_DESCRIPTOR_SET_SHA256
        || artifacts.catalog_row_count != 5_639
        || artifacts.catalog_sha256 != CATALOG_SHA256
        || artifacts.validator_rule_count != 32
        || artifacts.validator_ruleset_sha256 != VALIDATOR_RULESET_SHA256
        || artifacts.target_phase_count != 113
        || artifacts.s20b_gate_sha256 != S20B_GATE_SHA256
        || artifacts.s20b_checker_sha256 != S20B_CHECKER_SHA256
        || artifacts.s20b_report_sha256 != S20B_REPORT_SHA256
        || artifacts.s20b_source_delta_file_count != 23
    {
        return Err(s21a_error(
            "s21a_subject_build_binding",
            "build, assignment, validator, or predecessor artifact binding drifted",
        ));
    }
    Ok(())
}

fn build_s21_refreeze_subject_v1(
    inputs: &IndependentS21RefreezeInputsV1,
) -> AuthorizationResult<CanonicalBuiltS21SubjectV1> {
    validate_build_and_artifacts(&inputs.build_bindings, &inputs.artifact_bindings)?;
    let post = PostIntegrationRefreezeV1 {
        generated_outside_repository_after_s21a_integration: !inputs.test_only,
        post_integration_refreeze_required: true,
        s21a_source_commit: inputs.s21a_source_commit.clone(),
        s21a_source_tree: inputs.s21a_source_tree.clone(),
        s21a_integration_commit: inputs.s21a_integration_commit.clone(),
        s21a_integration_tree: inputs.s21a_integration_tree.clone(),
        any_post_freeze_change_requires_new_subject_and_owner_decision: true,
    };
    let post_identity_valid = if inputs.test_only {
        [
            &post.s21a_source_commit,
            &post.s21a_source_tree,
            &post.s21a_integration_commit,
            &post.s21a_integration_tree,
        ]
        .iter()
        .all(|value| value.is_none())
    } else {
        post.s21a_source_commit
            .as_deref()
            .and_then(|value| require_oid(value, "s21a_source_commit").ok())
            .is_some()
            && post
                .s21a_source_tree
                .as_deref()
                .and_then(|value| require_oid(value, "s21a_source_tree").ok())
                .is_some()
            && post
                .s21a_integration_commit
                .as_deref()
                .and_then(|value| require_oid(value, "s21a_integration_commit").ok())
                .is_some()
            && post
                .s21a_integration_tree
                .as_deref()
                .and_then(|value| require_oid(value, "s21a_integration_tree").ok())
                .is_some()
    };
    if !post_identity_valid {
        return Err(s21a_error(
            "s21a_post_integration_identity",
            "post-integration identities are incomplete or present in a repository KAT",
        ));
    }
    let mut packet = S21RefreezeSubjectV1 {
        schema: SUBJECT_SCHEMA.into(),
        packet_kind: SUBJECT_KIND.into(),
        canonicalization: CANONICALIZATION.into(),
        hashing_contract: HashingContractV1::exact(
            SUBJECT_DOMAIN,
            "ENTIRE_PACKET_EXCEPT_SUBJECT_SHA256",
            "subject_sha256",
        ),
        subject_state: if inputs.test_only {
            "SYNTHETIC_KAT_NON_LIVE_UNSIGNED_NOT_FINAL"
        } else {
            "FINAL_POST_INTEGRATION_UNSIGNED_SUBJECT"
        }
        .into(),
        test_only: inputs.test_only,
        synthetic: inputs.test_only,
        parent_bindings: exact_parent_bindings(),
        post_integration_refreeze: post,
        build_bindings: inputs.build_bindings.clone(),
        artifact_bindings: inputs.artifact_bindings.clone(),
        subject_sha256: "0".repeat(64),
        nonclaims: SubjectNonclaimsV1 {
            subject_is_owner_authority: false,
            subject_is_owner_signature: false,
            subject_is_execution_capability: false,
            schema_conformance_authorizes_live_execution: false,
            synthetic_fixture_is_signable_final_subject: false,
            side_effects_unlocked: S21A_SIDE_EFFECTS_UNLOCKED.into(),
        },
    };
    let digest = packet_digest(&packet, "subject_sha256", SUBJECT_DOMAIN)?;
    packet.subject_sha256 = hex(&digest);
    Ok(CanonicalBuiltS21SubjectV1 {
        canonical_bytes: canonical_typed(&packet)?,
        digest,
    })
}

fn validate_subject_shape(packet: &S21RefreezeSubjectV1) -> AuthorizationResult<()> {
    validate_build_and_artifacts(&packet.build_bindings, &packet.artifact_bindings)?;
    if packet.schema != SUBJECT_SCHEMA
        || packet.packet_kind != SUBJECT_KIND
        || packet.canonicalization != CANONICALIZATION
        || packet.hashing_contract
            != HashingContractV1::exact(
                SUBJECT_DOMAIN,
                "ENTIRE_PACKET_EXCEPT_SUBJECT_SHA256",
                "subject_sha256",
            )
        || packet.parent_bindings != exact_parent_bindings()
        || !packet
            .post_integration_refreeze
            .post_integration_refreeze_required
        || !packet
            .post_integration_refreeze
            .any_post_freeze_change_requires_new_subject_and_owner_decision
        || packet.nonclaims.subject_is_owner_authority
        || packet.nonclaims.subject_is_owner_signature
        || packet.nonclaims.subject_is_execution_capability
        || packet
            .nonclaims
            .schema_conformance_authorizes_live_execution
        || packet.nonclaims.synthetic_fixture_is_signable_final_subject
        || packet.nonclaims.side_effects_unlocked != S21A_SIDE_EFFECTS_UNLOCKED
    {
        return Err(s21a_error(
            "s21a_subject_shape",
            "subject contract, predecessor, or nonclaim boundary drifted",
        ));
    }
    let post = &packet.post_integration_refreeze;
    let state_valid = if packet.test_only {
        packet.synthetic
            && packet.subject_state == "SYNTHETIC_KAT_NON_LIVE_UNSIGNED_NOT_FINAL"
            && !post.generated_outside_repository_after_s21a_integration
            && post.s21a_source_commit.is_none()
            && post.s21a_source_tree.is_none()
            && post.s21a_integration_commit.is_none()
            && post.s21a_integration_tree.is_none()
    } else {
        !packet.synthetic
            && packet.subject_state == "FINAL_POST_INTEGRATION_UNSIGNED_SUBJECT"
            && post.generated_outside_repository_after_s21a_integration
            && post
                .s21a_source_commit
                .as_deref()
                .is_some_and(|value| require_oid(value, "s21a_source_commit").is_ok())
            && post
                .s21a_source_tree
                .as_deref()
                .is_some_and(|value| require_oid(value, "s21a_source_tree").is_ok())
            && post
                .s21a_integration_commit
                .as_deref()
                .is_some_and(|value| require_oid(value, "s21a_integration_commit").is_ok())
            && post
                .s21a_integration_tree
                .as_deref()
                .is_some_and(|value| require_oid(value, "s21a_integration_tree").is_ok())
    };
    if !state_valid {
        return Err(s21a_error(
            "s21a_subject_state",
            "synthetic or post-integration subject state is inconsistent",
        ));
    }
    Ok(())
}

fn parse_s21_refreeze_subject_v1(raw: &[u8]) -> AuthorizationResult<S21RefreezeSubjectV1> {
    let packet: S21RefreezeSubjectV1 = parse_typed(raw)?;
    validate_subject_shape(&packet)?;
    let digest = packet_digest(&packet, "subject_sha256", SUBJECT_DOMAIN)?;
    if packet.subject_sha256 != hex(&digest) {
        return Err(s21a_error(
            "s21a_subject_self",
            "subject self digest does not recompute",
        ));
    }
    Ok(packet)
}

fn verify_s21_refreeze_subject_v1(
    candidate_raw: &[u8],
    independent: &IndependentS21RefreezeInputsV1,
) -> AuthorizationResult<VerifiedS21RefreezeSubjectV1> {
    let candidate = parse_s21_refreeze_subject_v1(candidate_raw)?;
    let expected = build_s21_refreeze_subject_v1(independent)?;
    let payload = repository_payload(candidate_raw)?;
    if payload != expected.canonical_bytes || candidate.subject_sha256 != hex(&expected.digest) {
        return Err(s21a_error(
            "s21a_subject_independent_expected",
            "candidate subject differs from independently rebuilt final refreeze",
        ));
    }
    Ok(VerifiedS21RefreezeSubjectV1 {
        packet: candidate,
        digest: expected.digest,
    })
}

#[derive(Clone, Debug, Eq, PartialEq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
struct OwnerIdentityV1 {
    owner_identity_sha256: String,
    owner_role: String,
    identity_verified_out_of_band: bool,
    owner_identity_verification_receipt_sha256: Option<String>,
}

#[derive(Clone, Debug, Eq, PartialEq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
struct OwnerKeyBindingV1 {
    algorithm: String,
    key_id: String,
    key_version: u64,
    public_key_hex: String,
    legacy_s19_key_reuse_allowed: bool,
    private_key_present_in_repository: bool,
}

#[derive(Clone, Debug, Eq, PartialEq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
struct OwnerTrustPolicyV1 {
    trust_policy_sha256: String,
    minimum_revocation_epoch: u64,
    installed_out_of_band: bool,
    pinned_by_independent_caller: bool,
    installation_receipt_sha256: Option<String>,
    candidate_carried_key_is_trusted: bool,
}

#[derive(Clone, Debug, Eq, PartialEq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
struct AnchorNonclaimsV1 {
    anchor_is_owner_signature: bool,
    anchor_is_execution_capability: bool,
    public_kat_is_installed_anchor: bool,
    schema_conformance_establishes_trust: bool,
    side_effects_unlocked: String,
}

#[derive(Clone, Debug, Eq, PartialEq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
struct S21OwnerTrustAnchorV1 {
    schema: String,
    packet_kind: String,
    canonicalization: String,
    hashing_contract: HashingContractV1,
    anchor_state: String,
    test_only: bool,
    synthetic: bool,
    audience: String,
    owner_identity: OwnerIdentityV1,
    key_binding: OwnerKeyBindingV1,
    trust_policy: OwnerTrustPolicyV1,
    anchor_document_sha256: String,
    nonclaims: AnchorNonclaimsV1,
}

/// Expectations injected independently from the candidate anchor or envelope.
/// This type intentionally has no non-test constructor in S21A.
struct PinnedS21OwnerTrustExpectationsV1 {
    anchor_document_sha256: [u8; 32],
    owner_identity_sha256: [u8; 32],
    key_id: String,
    key_version: u64,
    public_key: [u8; 32],
    trust_policy_sha256: [u8; 32],
    installation_receipt_sha256: [u8; 32],
    owner_identity_verification_receipt_sha256: [u8; 32],
    minimum_revocation_epoch: u64,
    independent_installation_confirmed: bool,
    independent_pin_confirmed: bool,
    expected_current_revocation_epoch: u64,
}

#[must_use]
struct VerifiedInstalledOwnerAnchorV1 {
    document_sha256: [u8; 32],
    owner_identity_sha256: [u8; 32],
    key_id: String,
    key_version: u64,
    public_key: [u8; 32],
    trust_policy_sha256: [u8; 32],
    minimum_revocation_epoch: u64,
}

fn parse_and_verify_owner_anchor_v1(
    raw: &[u8],
    pinned: &PinnedS21OwnerTrustExpectationsV1,
) -> AuthorizationResult<VerifiedInstalledOwnerAnchorV1> {
    if !pinned.independent_installation_confirmed || !pinned.independent_pin_confirmed {
        return Err(s21a_error(
            "s21a_anchor_independent_pin",
            "anchor was not independently installed and pinned",
        ));
    }
    let anchor: S21OwnerTrustAnchorV1 = parse_typed(raw)?;
    let actual = packet_digest(&anchor, "anchor_document_sha256", ANCHOR_DOMAIN)?;
    let owner_identity = require_sha256(
        &anchor.owner_identity.owner_identity_sha256,
        "s21a_owner_identity",
    )?;
    let public_key = decode_hex_fixed::<32>(&anchor.key_binding.public_key_hex)?;
    let repository_public_kat_key = decode_hex_fixed::<32>(S21A_REPOSITORY_PUBLIC_KAT_KEY_HEX)?;
    if anchor.key_binding.key_id == S21A_REPOSITORY_PUBLIC_KAT_KEY_ID
        || public_key == repository_public_kat_key
    {
        return Err(s21a_error(
            "s21a_repository_public_kat_key",
            "repository public KAT key material can never become a real installed owner key",
        ));
    }
    let trust_policy = require_sha256(
        &anchor.trust_policy.trust_policy_sha256,
        "s21a_trust_policy",
    )?;
    let installation = anchor
        .trust_policy
        .installation_receipt_sha256
        .as_deref()
        .ok_or_else(|| {
            s21a_error(
                "s21a_anchor_installation",
                "installed anchor lacks an installation receipt",
            )
        })
        .and_then(|value| require_sha256(value, "s21a_anchor_installation"))?;
    let identity_receipt = anchor
        .owner_identity
        .owner_identity_verification_receipt_sha256
        .as_deref()
        .ok_or_else(|| {
            s21a_error(
                "s21a_owner_identity_receipt",
                "installed anchor lacks independent owner-identity verification receipt",
            )
        })
        .and_then(|value| require_sha256(value, "s21a_owner_identity_receipt"))?;
    if anchor.schema != ANCHOR_SCHEMA
        || anchor.packet_kind != ANCHOR_KIND
        || anchor.canonicalization != CANONICALIZATION
        || anchor.hashing_contract
            != HashingContractV1::exact(
                ANCHOR_DOMAIN,
                "ENTIRE_PACKET_EXCEPT_ANCHOR_DOCUMENT_SHA256",
                "anchor_document_sha256",
            )
        || anchor.anchor_state != "INSTALLED_OUT_OF_BAND_CALLER_PINNED"
        || anchor.test_only
        || anchor.synthetic
        || anchor.audience != OWNER_AUDIENCE
        || anchor.owner_identity.owner_role != "AGENT_BRIDGE_OWNED_LAB_EXECUTION_OWNER"
        || !anchor.owner_identity.identity_verified_out_of_band
        || anchor.key_binding.algorithm != "Ed25519"
        || !valid_s21_owner_key_id(&anchor.key_binding.key_id)
        || anchor.key_binding.key_version == 0
        || anchor.key_binding.key_version > u64::from(u32::MAX)
        || anchor.key_binding.legacy_s19_key_reuse_allowed
        || anchor.key_binding.private_key_present_in_repository
        || !nonzero(&public_key)
        || anchor.trust_policy.minimum_revocation_epoch == 0
        || anchor.trust_policy.minimum_revocation_epoch > u64::from(u32::MAX)
        || !anchor.trust_policy.installed_out_of_band
        || !anchor.trust_policy.pinned_by_independent_caller
        || anchor.trust_policy.candidate_carried_key_is_trusted
        || anchor.nonclaims.anchor_is_owner_signature
        || anchor.nonclaims.anchor_is_execution_capability
        || anchor.nonclaims.public_kat_is_installed_anchor
        || anchor.nonclaims.schema_conformance_establishes_trust
        || anchor.nonclaims.side_effects_unlocked != S21A_SIDE_EFFECTS_UNLOCKED
        || anchor.anchor_document_sha256 != hex(&actual)
        || actual != pinned.anchor_document_sha256
        || owner_identity != pinned.owner_identity_sha256
        || anchor.key_binding.key_id != pinned.key_id
        || anchor.key_binding.key_version != pinned.key_version
        || public_key != pinned.public_key
        || trust_policy != pinned.trust_policy_sha256
        || installation != pinned.installation_receipt_sha256
        || identity_receipt != pinned.owner_identity_verification_receipt_sha256
        || anchor.trust_policy.minimum_revocation_epoch != pinned.minimum_revocation_epoch
        || pinned.key_version == 0
        || pinned.key_version > u64::from(u32::MAX)
        || pinned.minimum_revocation_epoch == 0
        || pinned.minimum_revocation_epoch > u64::from(u32::MAX)
        || pinned.expected_current_revocation_epoch == 0
        || pinned.expected_current_revocation_epoch > u64::from(u32::MAX)
        || pinned.expected_current_revocation_epoch < pinned.minimum_revocation_epoch
    {
        return Err(s21a_error(
            "s21a_anchor_binding",
            "anchor is synthetic, self-authenticated, stale, or differs from independent trust expectations",
        ));
    }
    Ok(VerifiedInstalledOwnerAnchorV1 {
        document_sha256: actual,
        owner_identity_sha256: owner_identity,
        key_id: anchor.key_binding.key_id,
        key_version: anchor.key_binding.key_version,
        public_key,
        trust_policy_sha256: trust_policy,
        minimum_revocation_epoch: anchor.trust_policy.minimum_revocation_epoch,
    })
}

#[derive(Clone, Debug, Eq, PartialEq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
struct EnvelopeAnchorBindingV1 {
    anchor_document_sha256: String,
    anchor_key_id: String,
    anchor_key_version: u64,
    anchor_installed_out_of_band: bool,
    anchor_pinned_by_independent_caller: bool,
    candidate_carried_key_used: bool,
}

#[derive(Clone, Debug, Eq, PartialEq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
struct SignedOwnerPayloadV1 {
    audience: String,
    final_refreeze_subject_sha256: String,
    anchor_document_sha256: String,
    s20b_integration_commit: String,
    s20b_integration_tree: String,
    challenge_nonce_sha256: String,
    capability_nonce_sha256: String,
    revocation_epoch: u64,
    single_use: bool,
    automatic_retry_allowed: bool,
}

#[derive(Clone, Debug, Eq, PartialEq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
struct SignatureBindingV1 {
    algorithm: String,
    signed_payload_digest_domain: String,
    signed_payload_digest_framing: String,
    signature_domain: String,
    message_framing: String,
    signed_payload_sha256: String,
    signature_hex: String,
    detached_signature_sha256: String,
    detached_signature_digest_profile: String,
    signature_verified: bool,
    legacy_s19_signature_or_envelope_reuse_allowed: bool,
}

#[derive(Clone, Debug, Eq, PartialEq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
struct OwnerDecisionV1 {
    authorization_id_sha256: String,
    authorization_id_domain: String,
    authorization_id_framing: String,
    decision: String,
    owner_authority_established: bool,
    execution_start_permitted: bool,
    single_use_execution_capability_issued: bool,
    separate_external_input_review_required: bool,
}

#[derive(Clone, Debug, Eq, PartialEq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
struct EnvelopeNonclaimsV1 {
    envelope_is_execution_capability: bool,
    envelope_preapproves_s21b: bool,
    schema_conformance_proves_signature: bool,
    synthetic_envelope_is_owner_authority: bool,
    old_s19_signature_authorizes_s21a: bool,
    side_effects_unlocked: String,
}

#[derive(Clone, Debug, Eq, PartialEq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
struct S21OwnerAuthorizationEnvelopeV1 {
    schema: String,
    packet_kind: String,
    canonicalization: String,
    hashing_contract: HashingContractV1,
    envelope_state: String,
    test_only: bool,
    synthetic: bool,
    audience: String,
    anchor_binding: EnvelopeAnchorBindingV1,
    signed_payload: SignedOwnerPayloadV1,
    signature_binding: SignatureBindingV1,
    owner_decision: OwnerDecisionV1,
    owner_envelope_sha256: String,
    nonclaims: EnvelopeNonclaimsV1,
}

#[must_use]
struct VerifiedS21OwnerBoundSubjectV1 {
    subject: VerifiedS21RefreezeSubjectV1,
    anchor: VerifiedInstalledOwnerAnchorV1,
    owner_envelope_sha256: [u8; 32],
    authorization_id_sha256: [u8; 32],
    challenge_nonce_sha256: [u8; 32],
    capability_nonce_sha256: [u8; 32],
    revocation_epoch: u64,
}

fn verify_s21_owner_envelope_v1(
    subject: VerifiedS21RefreezeSubjectV1,
    anchor_raw: &[u8],
    envelope_raw: &[u8],
    pinned: &PinnedS21OwnerTrustExpectationsV1,
) -> AuthorizationResult<VerifiedS21OwnerBoundSubjectV1> {
    if subject.packet.test_only || subject.packet.synthetic {
        return Err(s21a_error(
            "s21a_owner_subject_state",
            "owner signature cannot authorize a repository synthetic subject",
        ));
    }
    let anchor = parse_and_verify_owner_anchor_v1(anchor_raw, pinned)?;
    let envelope: S21OwnerAuthorizationEnvelopeV1 = parse_typed(envelope_raw)?;
    let payload_bytes = canonical_typed(&envelope.signed_payload)?;
    let payload_sha256 = framed_payload_digest(SIGNED_PAYLOAD_DOMAIN, &payload_bytes)?;
    let signature = decode_hex_fixed::<64>(&envelope.signature_binding.signature_hex)?;
    let signature_sha256 = sha256_bytes(&signature);
    let expected_authorization_id =
        authorization_id(&payload_sha256, &signature_sha256, &anchor.document_sha256)?;
    let challenge = require_sha256(
        &envelope.signed_payload.challenge_nonce_sha256,
        "s21a_challenge_nonce",
    )?;
    let capability = require_sha256(
        &envelope.signed_payload.capability_nonce_sha256,
        "s21a_capability_nonce",
    )?;
    let envelope_digest = packet_digest(&envelope, "owner_envelope_sha256", ENVELOPE_DOMAIN)?;
    let anchor_binding_valid = envelope.anchor_binding.anchor_document_sha256
        == hex(&anchor.document_sha256)
        && envelope.anchor_binding.anchor_key_id == anchor.key_id
        && envelope.anchor_binding.anchor_key_version == anchor.key_version
        && envelope.anchor_binding.anchor_installed_out_of_band
        && envelope.anchor_binding.anchor_pinned_by_independent_caller
        && !envelope.anchor_binding.candidate_carried_key_used;
    let payload_valid = envelope.signed_payload.audience == OWNER_AUDIENCE
        && envelope.signed_payload.final_refreeze_subject_sha256 == hex(&subject.digest)
        && envelope.signed_payload.anchor_document_sha256 == hex(&anchor.document_sha256)
        && envelope.signed_payload.s20b_integration_commit == S20B_INTEGRATION_COMMIT
        && envelope.signed_payload.s20b_integration_tree == S20B_INTEGRATION_TREE
        && challenge != capability
        && envelope.signed_payload.revocation_epoch == pinned.expected_current_revocation_epoch
        && envelope.signed_payload.revocation_epoch >= anchor.minimum_revocation_epoch
        && envelope.signed_payload.revocation_epoch <= u64::from(u32::MAX)
        && envelope.signed_payload.single_use
        && !envelope.signed_payload.automatic_retry_allowed;
    let signature_contract_valid = envelope.signature_binding.algorithm == "Ed25519"
        && envelope.signature_binding.signed_payload_digest_domain
            == std::str::from_utf8(SIGNED_PAYLOAD_DOMAIN).unwrap()
        && envelope.signature_binding.signed_payload_digest_framing == DIGEST_FRAMING
        && envelope.signature_binding.signature_domain
            == std::str::from_utf8(SIGNATURE_DOMAIN).unwrap()
        && envelope.signature_binding.message_framing
            == "U32BE_DOMAIN_LENGTH_DOMAIN_U64BE_32_RAW_SIGNED_PAYLOAD_SHA256"
        && envelope.signature_binding.signed_payload_sha256 == hex(&payload_sha256)
        && envelope.signature_binding.detached_signature_sha256 == hex(&signature_sha256)
        && envelope.signature_binding.detached_signature_digest_profile
            == "SHA256_RAW_64_BYTE_ED25519_SIGNATURE"
        && envelope.signature_binding.signature_verified
        && !envelope
            .signature_binding
            .legacy_s19_signature_or_envelope_reuse_allowed;
    let decision_valid = envelope.owner_decision.authorization_id_sha256
        == hex(&expected_authorization_id)
        && envelope.owner_decision.authorization_id_domain
            == std::str::from_utf8(AUTHORIZATION_ID_DOMAIN).unwrap()
        && envelope.owner_decision.authorization_id_framing
            == "U32BE_DOMAIN_LENGTH_DOMAIN_THREE_U64BE_32_RAW_SHA256"
        && envelope.owner_decision.decision
            == "OWNER_SIGNED_FINAL_SUBJECT_PENDING_EXTERNAL_INPUT_REVIEW"
        && envelope.owner_decision.owner_authority_established
        && !envelope.owner_decision.execution_start_permitted
        && !envelope
            .owner_decision
            .single_use_execution_capability_issued
        && envelope
            .owner_decision
            .separate_external_input_review_required;
    let nonclaims_valid = !envelope.nonclaims.envelope_is_execution_capability
        && !envelope.nonclaims.envelope_preapproves_s21b
        && !envelope.nonclaims.schema_conformance_proves_signature
        && !envelope.nonclaims.synthetic_envelope_is_owner_authority
        && !envelope.nonclaims.old_s19_signature_authorizes_s21a
        && envelope.nonclaims.side_effects_unlocked == S21A_SIDE_EFFECTS_UNLOCKED;
    if envelope.schema != ENVELOPE_SCHEMA
        || envelope.packet_kind != ENVELOPE_KIND
        || envelope.canonicalization != CANONICALIZATION
        || envelope.hashing_contract
            != HashingContractV1::exact(
                ENVELOPE_DOMAIN,
                "ENTIRE_PACKET_EXCEPT_OWNER_ENVELOPE_SHA256",
                "owner_envelope_sha256",
            )
        || envelope.envelope_state != "OWNER_SIGNED_FINAL_SUBJECT_PENDING_EXTERNAL_INPUT_REVIEW"
        || envelope.test_only
        || envelope.synthetic
        || envelope.audience != OWNER_AUDIENCE
        || !anchor_binding_valid
        || !payload_valid
        || !signature_contract_valid
        || !decision_valid
        || !nonclaims_valid
        || envelope.owner_envelope_sha256 != hex(&envelope_digest)
    {
        return Err(s21a_error(
            "s21a_owner_envelope_binding",
            "owner envelope is stale, legacy, self-authenticated, retryable, or cross-bound to different inputs",
        ));
    }
    UnparsedPublicKey::new(&ED25519, anchor.public_key)
        .verify(&signature_message(&payload_sha256)?, &signature)
        .map_err(|_| {
            s21a_error(
                "s21a_owner_signature",
                "new S21A detached owner signature verification failed",
            )
        })?;
    Ok(VerifiedS21OwnerBoundSubjectV1 {
        subject,
        anchor,
        owner_envelope_sha256: envelope_digest,
        authorization_id_sha256: expected_authorization_id,
        challenge_nonce_sha256: challenge,
        capability_nonce_sha256: capability,
        revocation_epoch: envelope.signed_payload.revocation_epoch,
    })
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
enum ExternalCheckpointStateV1 {
    CommittedCurrent,
    Prepared,
    Stale,
    Forked,
    Unknown,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
enum ExternalAcknowledgementV1 {
    KnownCommitted,
    Unknown,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
enum ExternalRegistrationStateV1 {
    AuthorizedUnclaimed,
    Consumed,
    Missing,
    Unknown,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
enum ExternalStopStateV1 {
    ClearCurrent,
    Triggered,
    Unknown,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
enum ExternalRevocationStateV1 {
    ExactCurrent,
    RollbackDetected,
    Stale,
    Unknown,
}

/// Exact values supplied by an independent S21B control-plane integration.
/// S21A defines no constructor for this type.
struct PinnedExternalAdmissionExpectationsV1 {
    checkpoint_provider_identity_sha256: [u8; 32],
    checkpoint_provider_trust_anchor_sha256: [u8; 32],
    checkpoint_provider_policy_sha256: [u8; 32],
    checkpoint_provider_failure_domain_sha256: [u8; 32],
    database_failure_domain_sha256: [u8; 32],
    checkpoint_receipt_sha256: [u8; 32],
    checkpoint_head_sha256: [u8; 32],
    previous_checkpoint_head_sha256: Option<[u8; 32]>,
    database_content_root_sha256: [u8; 32],
    expected_checkpoint_counter: u64,
    registration_receipt_sha256: [u8; 32],
    registrar_identity_sha256: [u8; 32],
    external_control_plane_identity_sha256: [u8; 32],
    registration_provenance_receipt_sha256: [u8; 32],
    registration_creator_binary_sha256: [u8; 32],
    expected_registration_revision: u64,
    expected_previous_registration_revision: u64,
    observer_source_sha256: [u8; 32],
    observer_binary_sha256: [u8; 32],
    observer_toolchain_sha256: [u8; 32],
    observer_measurement_receipt_sha256: [u8; 32],
    runner_source_sha256: [u8; 32],
    runner_binary_sha256: [u8; 32],
    runner_toolchain_sha256: [u8; 32],
    runner_operation_manifest_sha256: [u8; 32],
    environment_receipt_sha256: [u8; 32],
    canary_input_pack_sha256: [u8; 32],
    lab_environment_sha256: [u8; 32],
    stop_policy_sha256: [u8; 32],
    revocation_policy_sha256: [u8; 32],
    stop_snapshot_sha256: [u8; 32],
    revocation_snapshot_sha256: [u8; 32],
    retention_policy_sha256: [u8; 32],
    cleanup_policy_sha256: [u8; 32],
    custody_policy_sha256: [u8; 32],
    review_policy_sha256: [u8; 32],
    independent_review_receipt_sha256: [u8; 32],
}

struct ExternalFactBindingV1 {
    subject_sha256: [u8; 32],
    owner_envelope_sha256: [u8; 32],
    authorization_id_sha256: [u8; 32],
    challenge_nonce_sha256: [u8; 32],
    capability_nonce_sha256: [u8; 32],
}

/// Opaque result expected from a future independently authenticated checkpoint
/// adapter. No non-test constructor exists in S21A.
struct ValidatedIndependentCheckpointFactsV1 {
    binding: ExternalFactBindingV1,
    provider_identity_sha256: [u8; 32],
    provider_trust_anchor_sha256: [u8; 32],
    provider_policy_sha256: [u8; 32],
    provider_failure_domain_sha256: [u8; 32],
    database_failure_domain_sha256: [u8; 32],
    checkpoint_receipt_sha256: [u8; 32],
    checkpoint_head_sha256: [u8; 32],
    previous_checkpoint_head_sha256: Option<[u8; 32]>,
    database_content_root_sha256: [u8; 32],
    monotonic_counter: u64,
    observed_revocation_epoch: u64,
    state: ExternalCheckpointStateV1,
    acknowledgement: ExternalAcknowledgementV1,
}

/// Opaque result expected from a future external registrar verifier. No
/// non-test constructor exists in S21A.
struct ValidatedExternalRegistrationFactsV1 {
    binding: ExternalFactBindingV1,
    registration_receipt_sha256: [u8; 32],
    registrar_identity_sha256: [u8; 32],
    external_control_plane_identity_sha256: [u8; 32],
    provenance_receipt_sha256: [u8; 32],
    creator_binary_sha256: [u8; 32],
    revision: u64,
    previous_revision: u64,
    state: ExternalRegistrationStateV1,
    successful_claim_count: u64,
    claimed_run_id_sha256: Option<[u8; 32]>,
    created_by_runner: bool,
}

/// Opaque result expected from future build and environment attestation
/// verifiers. No non-test constructor exists in S21A.
struct ValidatedObserverRunnerFactsV1 {
    binding: ExternalFactBindingV1,
    controller_binary_sha256: [u8; 32],
    observer_source_sha256: [u8; 32],
    observer_binary_sha256: [u8; 32],
    observer_toolchain_sha256: [u8; 32],
    observer_measurement_receipt_sha256: [u8; 32],
    runner_source_sha256: [u8; 32],
    runner_binary_sha256: [u8; 32],
    runner_toolchain_sha256: [u8; 32],
    runner_operation_manifest_sha256: [u8; 32],
    environment_receipt_sha256: [u8; 32],
    canary_input_pack_sha256: [u8; 32],
    observer_fresh: bool,
    build_recomputed_from_independent_receipts: bool,
    runner_launch_count: u64,
}

/// Opaque result expected from future current-control and custody verifiers. No
/// non-test constructor exists in S21A.
struct ValidatedControlReviewFactsV1 {
    binding: ExternalFactBindingV1,
    lab_environment_sha256: [u8; 32],
    stop_policy_sha256: [u8; 32],
    revocation_policy_sha256: [u8; 32],
    stop_snapshot_sha256: [u8; 32],
    revocation_snapshot_sha256: [u8; 32],
    retention_policy_sha256: [u8; 32],
    cleanup_policy_sha256: [u8; 32],
    custody_policy_sha256: [u8; 32],
    review_policy_sha256: [u8; 32],
    independent_review_receipt_sha256: [u8; 32],
    current_revocation_epoch: u64,
    stop_state: ExternalStopStateV1,
    revocation_state: ExternalRevocationStateV1,
    automatic_retry_allowed: bool,
    prior_attempt_count: u64,
    live_side_effect_count: u64,
    side_effects_unlocked: String,
}

struct ExternalAdmissionFactsV1 {
    checkpoint: ValidatedIndependentCheckpointFactsV1,
    registration: ValidatedExternalRegistrationFactsV1,
    runtime: ValidatedObserverRunnerFactsV1,
    control: ValidatedControlReviewFactsV1,
}

#[derive(Clone, Debug, Eq, PartialEq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
struct AdmissionSubjectBindingV1 {
    final_refreeze_subject_sha256: String,
    final_post_integration_subject_validated: bool,
    exact_s21a_commit_tree_and_build_bound: bool,
    any_post_freeze_change_observed: bool,
}

#[derive(Clone, Debug, Eq, PartialEq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
struct AdmissionOwnerBindingV1 {
    anchor_document_sha256: String,
    owner_envelope_sha256: String,
    audience: String,
    signature_domain: String,
    new_owner_signature_valid: bool,
    trust_anchor_installed_and_pinned: bool,
    legacy_s19_signature_or_envelope_reused: bool,
}

#[derive(Clone, Debug, Eq, PartialEq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
struct AdmissionCheckpointInputV1 {
    authorization_id_sha256: String,
    final_refreeze_subject_sha256: String,
    owner_envelope_sha256: String,
    provider_identity_sha256: String,
    provider_trust_anchor_sha256: String,
    provider_policy_sha256: String,
    provider_failure_domain_sha256: String,
    database_failure_domain_sha256: String,
    checkpoint_receipt_sha256: String,
    checkpoint_head_sha256: String,
    committed_content_root_sha256: String,
    monotonic_counter: u64,
    previous_checkpoint_sha256: Option<String>,
    observed_revocation_epoch: u64,
    checkpoint_state: String,
    provider_present: bool,
    independent_failure_domain_proved: bool,
    same_failure_domain_as_database: bool,
    acknowledgement_semantics_validated: bool,
}

#[derive(Clone, Debug, Eq, PartialEq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
struct AdmissionExternalRegistrationV1 {
    authorization_id_sha256: String,
    final_refreeze_subject_sha256: String,
    owner_envelope_sha256: String,
    capability_nonce_sha256: String,
    expected_unclaimed_revision: u64,
    registration_revision: u64,
    previous_revision: u64,
    registration_receipt_sha256: String,
    registrar_identity_sha256: String,
    external_control_plane_identity_sha256: String,
    provenance_receipt_sha256: String,
    creator_binary_sha256: String,
    registration_state: String,
    binding_validated: bool,
    registered_by_external_control_plane: bool,
    created_by_runner: bool,
    successful_claim_count: u64,
    claimed_run_id_sha256: Option<String>,
}

#[derive(Clone, Debug, Eq, PartialEq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
struct AdmissionRuntimeInputsV1 {
    controller_binary_sha256: String,
    observer_source_sha256: String,
    observer_binary_sha256: String,
    observer_toolchain_sha256: String,
    observer_measurement_receipt_sha256: String,
    runner_source_sha256: String,
    runner_binary_sha256: String,
    runner_toolchain_sha256: String,
    runner_operation_manifest_sha256: String,
    environment_observation_receipt_sha256: String,
    canary_input_pack_sha256: String,
    stop_snapshot_sha256: String,
    revocation_snapshot_sha256: String,
    fresh_observer_present_and_bound: bool,
    real_runner_present_and_bound: bool,
    exact_environment_present_and_bound: bool,
    exact_canary_inputs_present_and_bound: bool,
    stop_and_revocation_fresh_and_exact: bool,
    live_action_count: u64,
}

#[derive(Clone, Debug, Eq, PartialEq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
struct AdmissionPolicyBindingsV1 {
    lab_environment_sha256: String,
    stop_policy_sha256: String,
    revocation_policy_sha256: String,
    retention_policy_sha256: String,
    cleanup_policy_sha256: String,
    custody_policy_sha256: String,
    review_policy_sha256: String,
    independent_review_receipt_sha256: String,
    current_revocation_epoch: u64,
    automatic_or_implicit_retry_allowed: bool,
}

#[derive(Clone, Debug, Eq, PartialEq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
struct AdmissionResultV1 {
    all_external_inputs_validated: bool,
    terminal_hard_lock: bool,
    separate_review_required: bool,
    may_execute_live: bool,
    execution_capability_issued: bool,
    side_effects_unlocked: String,
}

#[derive(Clone, Debug, Eq, PartialEq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
struct AdmissionNonclaimsV1 {
    admission_packet_is_owner_authority: bool,
    admission_packet_is_execution_capability: bool,
    complete_inputs_preapprove_s21b: bool,
    synthetic_fixture_is_live_input: bool,
    valid_evidence_implies_favorable_result: bool,
    side_effects_unlocked: String,
}

#[derive(Clone, Debug, Eq, PartialEq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
struct S21ExternalInputAdmissionV1 {
    schema: String,
    packet_kind: String,
    canonicalization: String,
    hashing_contract: HashingContractV1,
    admission_state: String,
    test_only: bool,
    synthetic: bool,
    subject_binding: AdmissionSubjectBindingV1,
    owner_binding: AdmissionOwnerBindingV1,
    checkpoint_input: AdmissionCheckpointInputV1,
    external_registration: AdmissionExternalRegistrationV1,
    runtime_inputs: AdmissionRuntimeInputsV1,
    policy_bindings: AdmissionPolicyBindingsV1,
    result: AdmissionResultV1,
    admission_packet_sha256: String,
    nonclaims: AdmissionNonclaimsV1,
}

#[must_use]
struct CanonicalBuiltS21ExternalInputAdmissionV1 {
    canonical_bytes: Vec<u8>,
    digest: [u8; 32],
}

/// Affine non-executing readiness evidence. Its fields are private, it is not
/// serializable or clonable, and it cannot start or authorize an action.
#[must_use]
struct ValidatedS21ExternalInputReadinessV1 {
    _owner: VerifiedS21OwnerBoundSubjectV1,
    admission_packet_sha256: [u8; 32],
    readiness_sha256: [u8; 32],
}

fn binding_matches_owner(
    binding: &ExternalFactBindingV1,
    owner: &VerifiedS21OwnerBoundSubjectV1,
) -> bool {
    binding.subject_sha256 == owner.subject.digest
        && binding.owner_envelope_sha256 == owner.owner_envelope_sha256
        && binding.authorization_id_sha256 == owner.authorization_id_sha256
        && binding.challenge_nonce_sha256 == owner.challenge_nonce_sha256
        && binding.capability_nonce_sha256 == owner.capability_nonce_sha256
}

fn security_digests_nonzero(values: &[&[u8; 32]]) -> bool {
    values.iter().all(|value| nonzero(*value))
}

fn checkpoint_predecessor_valid(
    counter: u64,
    checkpoint_head_sha256: &[u8; 32],
    previous_checkpoint_head_sha256: Option<[u8; 32]>,
) -> bool {
    match (counter, previous_checkpoint_head_sha256) {
        (1, None) => true,
        (counter, Some(previous)) if counter > 1 => {
            nonzero(&previous) && previous != *checkpoint_head_sha256
        }
        _ => false,
    }
}

fn external_binding_security_digests_nonzero(binding: &ExternalFactBindingV1) -> bool {
    security_digests_nonzero(&[
        &binding.subject_sha256,
        &binding.owner_envelope_sha256,
        &binding.authorization_id_sha256,
        &binding.challenge_nonce_sha256,
        &binding.capability_nonce_sha256,
    ])
}

fn pinned_external_security_digests_nonzero(
    expected: &PinnedExternalAdmissionExpectationsV1,
) -> bool {
    security_digests_nonzero(&[
        &expected.checkpoint_provider_identity_sha256,
        &expected.checkpoint_provider_trust_anchor_sha256,
        &expected.checkpoint_provider_policy_sha256,
        &expected.checkpoint_provider_failure_domain_sha256,
        &expected.database_failure_domain_sha256,
        &expected.checkpoint_receipt_sha256,
        &expected.checkpoint_head_sha256,
        &expected.database_content_root_sha256,
        &expected.registration_receipt_sha256,
        &expected.registrar_identity_sha256,
        &expected.external_control_plane_identity_sha256,
        &expected.registration_provenance_receipt_sha256,
        &expected.registration_creator_binary_sha256,
        &expected.observer_source_sha256,
        &expected.observer_binary_sha256,
        &expected.observer_toolchain_sha256,
        &expected.observer_measurement_receipt_sha256,
        &expected.runner_source_sha256,
        &expected.runner_binary_sha256,
        &expected.runner_toolchain_sha256,
        &expected.runner_operation_manifest_sha256,
        &expected.environment_receipt_sha256,
        &expected.canary_input_pack_sha256,
        &expected.lab_environment_sha256,
        &expected.stop_policy_sha256,
        &expected.revocation_policy_sha256,
        &expected.stop_snapshot_sha256,
        &expected.revocation_snapshot_sha256,
        &expected.retention_policy_sha256,
        &expected.cleanup_policy_sha256,
        &expected.custody_policy_sha256,
        &expected.review_policy_sha256,
        &expected.independent_review_receipt_sha256,
    ]) && expected
        .previous_checkpoint_head_sha256
        .as_ref()
        .map(|value| nonzero(value))
        .unwrap_or(true)
}

fn external_fact_security_digests_nonzero(facts: &ExternalAdmissionFactsV1) -> bool {
    let bindings_nonzero = [
        &facts.checkpoint.binding,
        &facts.registration.binding,
        &facts.runtime.binding,
        &facts.control.binding,
    ]
    .into_iter()
    .all(external_binding_security_digests_nonzero);
    bindings_nonzero
        && security_digests_nonzero(&[
            &facts.checkpoint.provider_identity_sha256,
            &facts.checkpoint.provider_trust_anchor_sha256,
            &facts.checkpoint.provider_policy_sha256,
            &facts.checkpoint.provider_failure_domain_sha256,
            &facts.checkpoint.database_failure_domain_sha256,
            &facts.checkpoint.checkpoint_receipt_sha256,
            &facts.checkpoint.checkpoint_head_sha256,
            &facts.checkpoint.database_content_root_sha256,
            &facts.registration.registration_receipt_sha256,
            &facts.registration.registrar_identity_sha256,
            &facts.registration.external_control_plane_identity_sha256,
            &facts.registration.provenance_receipt_sha256,
            &facts.registration.creator_binary_sha256,
            &facts.runtime.controller_binary_sha256,
            &facts.runtime.observer_source_sha256,
            &facts.runtime.observer_binary_sha256,
            &facts.runtime.observer_toolchain_sha256,
            &facts.runtime.observer_measurement_receipt_sha256,
            &facts.runtime.runner_source_sha256,
            &facts.runtime.runner_binary_sha256,
            &facts.runtime.runner_toolchain_sha256,
            &facts.runtime.runner_operation_manifest_sha256,
            &facts.runtime.environment_receipt_sha256,
            &facts.runtime.canary_input_pack_sha256,
            &facts.control.lab_environment_sha256,
            &facts.control.stop_policy_sha256,
            &facts.control.revocation_policy_sha256,
            &facts.control.stop_snapshot_sha256,
            &facts.control.revocation_snapshot_sha256,
            &facts.control.retention_policy_sha256,
            &facts.control.cleanup_policy_sha256,
            &facts.control.custody_policy_sha256,
            &facts.control.review_policy_sha256,
            &facts.control.independent_review_receipt_sha256,
        ])
        && facts
            .checkpoint
            .previous_checkpoint_head_sha256
            .as_ref()
            .map(|value| nonzero(value))
            .unwrap_or(true)
        && facts
            .registration
            .claimed_run_id_sha256
            .as_ref()
            .map(|value| nonzero(value))
            .unwrap_or(true)
}

fn validate_s21_external_fact_contract_v1(
    owner: &VerifiedS21OwnerBoundSubjectV1,
    facts: &ExternalAdmissionFactsV1,
    expected: &PinnedExternalAdmissionExpectationsV1,
) -> AuthorizationResult<[u8; 32]> {
    let all_bindings_match = [
        &facts.checkpoint.binding,
        &facts.registration.binding,
        &facts.runtime.binding,
        &facts.control.binding,
    ]
    .into_iter()
    .all(|binding| binding_matches_owner(binding, owner));
    let security_digests_valid = pinned_external_security_digests_nonzero(expected)
        && external_fact_security_digests_nonzero(facts);
    let checkpoint_valid = facts.checkpoint.state == ExternalCheckpointStateV1::CommittedCurrent
        && facts.checkpoint.acknowledgement == ExternalAcknowledgementV1::KnownCommitted
        && facts.checkpoint.provider_identity_sha256
            == expected.checkpoint_provider_identity_sha256
        && facts.checkpoint.provider_trust_anchor_sha256
            == expected.checkpoint_provider_trust_anchor_sha256
        && facts.checkpoint.provider_policy_sha256 == expected.checkpoint_provider_policy_sha256
        && facts.checkpoint.provider_failure_domain_sha256
            == expected.checkpoint_provider_failure_domain_sha256
        && facts.checkpoint.database_failure_domain_sha256
            == expected.database_failure_domain_sha256
        && facts.checkpoint.provider_failure_domain_sha256
            != facts.checkpoint.database_failure_domain_sha256
        && facts.checkpoint.checkpoint_receipt_sha256 == expected.checkpoint_receipt_sha256
        && facts.checkpoint.checkpoint_head_sha256 == expected.checkpoint_head_sha256
        && facts.checkpoint.previous_checkpoint_head_sha256
            == expected.previous_checkpoint_head_sha256
        && facts.checkpoint.database_content_root_sha256 == expected.database_content_root_sha256
        && facts.checkpoint.monotonic_counter == expected.expected_checkpoint_counter
        && checkpoint_predecessor_valid(
            expected.expected_checkpoint_counter,
            &expected.checkpoint_head_sha256,
            expected.previous_checkpoint_head_sha256,
        )
        && checkpoint_predecessor_valid(
            facts.checkpoint.monotonic_counter,
            &facts.checkpoint.checkpoint_head_sha256,
            facts.checkpoint.previous_checkpoint_head_sha256,
        )
        && facts.checkpoint.observed_revocation_epoch == owner.revocation_epoch
        && facts.checkpoint.observed_revocation_epoch <= u64::from(u32::MAX);
    let registration_valid = facts.registration.state
        == ExternalRegistrationStateV1::AuthorizedUnclaimed
        && facts.registration.registration_receipt_sha256 == expected.registration_receipt_sha256
        && facts.registration.registrar_identity_sha256 == expected.registrar_identity_sha256
        && facts.registration.external_control_plane_identity_sha256
            == expected.external_control_plane_identity_sha256
        && facts.registration.provenance_receipt_sha256
            == expected.registration_provenance_receipt_sha256
        && facts.registration.creator_binary_sha256 == expected.registration_creator_binary_sha256
        && facts.registration.creator_binary_sha256 != facts.runtime.runner_binary_sha256
        && facts.registration.revision == expected.expected_registration_revision
        && facts.registration.previous_revision == expected.expected_previous_registration_revision
        && expected
            .expected_previous_registration_revision
            .checked_add(1)
            == Some(expected.expected_registration_revision)
        && facts.registration.previous_revision.checked_add(1) == Some(facts.registration.revision)
        && facts.registration.successful_claim_count == 0
        && facts.registration.claimed_run_id_sha256.is_none()
        && !facts.registration.created_by_runner;
    let subject_build = &owner.subject.packet.build_bindings;
    let runtime_valid = facts.runtime.controller_binary_sha256
        == require_sha256(
            &subject_build.controller_binary_sha256,
            "s21a_controller_build",
        )?
        && facts.runtime.observer_binary_sha256
            == require_sha256(&subject_build.observer_binary_sha256, "s21a_observer_build")?
        && facts.runtime.runner_binary_sha256
            == require_sha256(&subject_build.runner_binary_sha256, "s21a_runner_build")?
        && facts.runtime.observer_source_sha256 == expected.observer_source_sha256
        && facts.runtime.observer_binary_sha256 == expected.observer_binary_sha256
        && facts.runtime.observer_toolchain_sha256 == expected.observer_toolchain_sha256
        && facts.runtime.observer_measurement_receipt_sha256
            == expected.observer_measurement_receipt_sha256
        && facts.runtime.runner_source_sha256 == expected.runner_source_sha256
        && facts.runtime.runner_binary_sha256 == expected.runner_binary_sha256
        && facts.runtime.runner_toolchain_sha256 == expected.runner_toolchain_sha256
        && facts.runtime.runner_operation_manifest_sha256
            == expected.runner_operation_manifest_sha256
        && facts.runtime.environment_receipt_sha256 == expected.environment_receipt_sha256
        && facts.runtime.canary_input_pack_sha256 == expected.canary_input_pack_sha256
        && facts.runtime.observer_fresh
        && facts.runtime.build_recomputed_from_independent_receipts
        && facts.runtime.runner_launch_count == 0;
    let control_valid = facts.control.lab_environment_sha256 == expected.lab_environment_sha256
        && facts.control.stop_policy_sha256 == expected.stop_policy_sha256
        && facts.control.revocation_policy_sha256 == expected.revocation_policy_sha256
        && facts.control.stop_snapshot_sha256 == expected.stop_snapshot_sha256
        && facts.control.revocation_snapshot_sha256 == expected.revocation_snapshot_sha256
        && facts.control.retention_policy_sha256 == expected.retention_policy_sha256
        && facts.control.cleanup_policy_sha256 == expected.cleanup_policy_sha256
        && facts.control.custody_policy_sha256 == expected.custody_policy_sha256
        && facts.control.review_policy_sha256 == expected.review_policy_sha256
        && facts.control.independent_review_receipt_sha256
            == expected.independent_review_receipt_sha256
        && facts.control.current_revocation_epoch == owner.revocation_epoch
        && facts.control.current_revocation_epoch <= u64::from(u32::MAX)
        && facts.control.stop_state == ExternalStopStateV1::ClearCurrent
        && facts.control.revocation_state == ExternalRevocationStateV1::ExactCurrent
        && !facts.control.automatic_retry_allowed
        && facts.control.prior_attempt_count == 0
        && facts.control.live_side_effect_count == 0
        && facts.control.side_effects_unlocked == S21A_SIDE_EFFECTS_UNLOCKED;
    if !all_bindings_match
        || !security_digests_valid
        || !checkpoint_valid
        || !registration_valid
        || !runtime_valid
        || !control_valid
    {
        return Err(s21a_error(
            "s21a_external_input_admission",
            "external facts are missing, stale, forked, same-domain, runner-created, build-drifted, retryable, or side-effecting",
        ));
    }
    let mut readiness = Vec::new();
    append_u32_frame(
        &mut readiness,
        b"agent-bridge/biocortex/owned-lab/s21a/non-executing-external-input-readiness/v1",
    )?;
    for value in [
        &owner.subject.digest,
        &owner.owner_envelope_sha256,
        &owner.authorization_id_sha256,
        &facts.checkpoint.checkpoint_receipt_sha256,
        &facts.registration.registration_receipt_sha256,
        &facts.runtime.observer_measurement_receipt_sha256,
        &facts.runtime.runner_operation_manifest_sha256,
        &facts.control.independent_review_receipt_sha256,
    ] {
        append_u64_frame(&mut readiness, value)?;
    }
    Ok(sha256_bytes(&readiness))
}

fn validate_external_admission_packet_shape(
    packet: &S21ExternalInputAdmissionV1,
) -> AuthorizationResult<()> {
    let checkpoint_head = require_sha256(
        &packet.checkpoint_input.checkpoint_head_sha256,
        "s21a_admission_checkpoint_head",
    )?;
    let previous_checkpoint = packet
        .checkpoint_input
        .previous_checkpoint_sha256
        .as_deref()
        .map(|value| require_sha256(value, "s21a_admission_previous_checkpoint"))
        .transpose()?;
    let claimed_run = packet
        .external_registration
        .claimed_run_id_sha256
        .as_deref()
        .map(|value| require_sha256(value, "s21a_admission_claimed_run"))
        .transpose()?;
    for value in [
        &packet.subject_binding.final_refreeze_subject_sha256,
        &packet.owner_binding.anchor_document_sha256,
        &packet.owner_binding.owner_envelope_sha256,
        &packet.checkpoint_input.authorization_id_sha256,
        &packet.checkpoint_input.final_refreeze_subject_sha256,
        &packet.checkpoint_input.owner_envelope_sha256,
        &packet.checkpoint_input.provider_identity_sha256,
        &packet.checkpoint_input.provider_trust_anchor_sha256,
        &packet.checkpoint_input.provider_policy_sha256,
        &packet.checkpoint_input.provider_failure_domain_sha256,
        &packet.checkpoint_input.database_failure_domain_sha256,
        &packet.checkpoint_input.checkpoint_receipt_sha256,
        &packet.checkpoint_input.committed_content_root_sha256,
        &packet.external_registration.authorization_id_sha256,
        &packet.external_registration.final_refreeze_subject_sha256,
        &packet.external_registration.owner_envelope_sha256,
        &packet.external_registration.capability_nonce_sha256,
        &packet.external_registration.registration_receipt_sha256,
        &packet.external_registration.registrar_identity_sha256,
        &packet
            .external_registration
            .external_control_plane_identity_sha256,
        &packet.external_registration.provenance_receipt_sha256,
        &packet.external_registration.creator_binary_sha256,
        &packet.runtime_inputs.controller_binary_sha256,
        &packet.runtime_inputs.observer_source_sha256,
        &packet.runtime_inputs.observer_binary_sha256,
        &packet.runtime_inputs.observer_toolchain_sha256,
        &packet.runtime_inputs.observer_measurement_receipt_sha256,
        &packet.runtime_inputs.runner_source_sha256,
        &packet.runtime_inputs.runner_binary_sha256,
        &packet.runtime_inputs.runner_toolchain_sha256,
        &packet.runtime_inputs.runner_operation_manifest_sha256,
        &packet.runtime_inputs.environment_observation_receipt_sha256,
        &packet.runtime_inputs.canary_input_pack_sha256,
        &packet.runtime_inputs.stop_snapshot_sha256,
        &packet.runtime_inputs.revocation_snapshot_sha256,
        &packet.policy_bindings.lab_environment_sha256,
        &packet.policy_bindings.stop_policy_sha256,
        &packet.policy_bindings.revocation_policy_sha256,
        &packet.policy_bindings.retention_policy_sha256,
        &packet.policy_bindings.cleanup_policy_sha256,
        &packet.policy_bindings.custody_policy_sha256,
        &packet.policy_bindings.review_policy_sha256,
        &packet.policy_bindings.independent_review_receipt_sha256,
    ] {
        require_sha256(value, "s21a_admission_security_digest")?;
    }
    let checkpoint_provider_failure_domain = require_sha256(
        &packet.checkpoint_input.provider_failure_domain_sha256,
        "s21a_admission_provider_failure_domain",
    )?;
    let database_failure_domain = require_sha256(
        &packet.checkpoint_input.database_failure_domain_sha256,
        "s21a_admission_database_failure_domain",
    )?;
    let registration_revision_exact = packet.external_registration.expected_unclaimed_revision
        == packet.external_registration.registration_revision
        && packet
            .external_registration
            .previous_revision
            .checked_add(1)
            == Some(packet.external_registration.registration_revision);
    let unclaimed_projection =
        packet.external_registration.successful_claim_count == 0 && claimed_run.is_none();
    let registration_claim_state_valid =
        match packet.external_registration.registration_state.as_str() {
            "CONSUMED" => {
                packet.external_registration.successful_claim_count > 0 && claimed_run.is_some()
            }
            "AUTHORIZED_UNCLAIMED_PRESENT" | "MISSING" => unclaimed_projection,
            "UNKNOWN" => true,
            _ => false,
        };
    let revocation_epoch_exact = packet.checkpoint_input.observed_revocation_epoch
        == packet.policy_bindings.current_revocation_epoch;
    let common_valid = packet.schema == ADMISSION_SCHEMA
        && packet.packet_kind == ADMISSION_KIND
        && packet.canonicalization == CANONICALIZATION
        && packet.hashing_contract
            == HashingContractV1::exact(
                ADMISSION_DOMAIN,
                "ENTIRE_PACKET_EXCEPT_ADMISSION_PACKET_SHA256",
                "admission_packet_sha256",
            )
        && packet.subject_binding.final_refreeze_subject_sha256
            == packet.checkpoint_input.final_refreeze_subject_sha256
        && packet.subject_binding.final_refreeze_subject_sha256
            == packet.external_registration.final_refreeze_subject_sha256
        && packet.owner_binding.owner_envelope_sha256
            == packet.checkpoint_input.owner_envelope_sha256
        && packet.owner_binding.owner_envelope_sha256
            == packet.external_registration.owner_envelope_sha256
        && packet.checkpoint_input.authorization_id_sha256
            == packet.external_registration.authorization_id_sha256
        && packet.owner_binding.audience == OWNER_AUDIENCE
        && packet.owner_binding.signature_domain == std::str::from_utf8(SIGNATURE_DOMAIN).unwrap()
        && !packet.owner_binding.legacy_s19_signature_or_envelope_reused
        && !packet.subject_binding.any_post_freeze_change_observed
        && packet.checkpoint_input.same_failure_domain_as_database
            == (checkpoint_provider_failure_domain == database_failure_domain)
        && matches!(
            packet.checkpoint_input.checkpoint_state.as_str(),
            "MISSING"
                | "PREPARED"
                | "COMMITTED_CURRENT"
                | "STALE"
                | "FORKED"
                | "ROLLBACK_DETECTED"
                | "ACKNOWLEDGEMENT_UNKNOWN"
        )
        && registration_claim_state_valid
        && packet.external_registration.expected_unclaimed_revision > 0
        && packet.external_registration.registration_revision > 0
        && checkpoint_predecessor_valid(
            packet.checkpoint_input.monotonic_counter,
            &checkpoint_head,
            previous_checkpoint,
        )
        && packet.checkpoint_input.observed_revocation_epoch > 0
        && packet.checkpoint_input.observed_revocation_epoch <= u64::from(u32::MAX)
        && packet.policy_bindings.current_revocation_epoch > 0
        && packet.policy_bindings.current_revocation_epoch <= u64::from(u32::MAX)
        && !packet.policy_bindings.automatic_or_implicit_retry_allowed
        && packet.runtime_inputs.live_action_count == 0
        && packet.result.separate_review_required
        && !packet.result.may_execute_live
        && !packet.result.execution_capability_issued
        && packet.result.side_effects_unlocked == S21A_SIDE_EFFECTS_UNLOCKED
        && !packet.nonclaims.admission_packet_is_owner_authority
        && !packet.nonclaims.admission_packet_is_execution_capability
        && !packet.nonclaims.complete_inputs_preapprove_s21b
        && !packet.nonclaims.synthetic_fixture_is_live_input
        && !packet.nonclaims.valid_evidence_implies_favorable_result
        && packet.nonclaims.side_effects_unlocked == S21A_SIDE_EFFECTS_UNLOCKED;
    let complete_valid = !packet.test_only
        && !packet.synthetic
        && packet
            .subject_binding
            .final_post_integration_subject_validated
        && packet
            .subject_binding
            .exact_s21a_commit_tree_and_build_bound
        && packet.owner_binding.new_owner_signature_valid
        && packet.owner_binding.trust_anchor_installed_and_pinned
        && packet.checkpoint_input.checkpoint_state == "COMMITTED_CURRENT"
        && packet.checkpoint_input.provider_present
        && packet.checkpoint_input.independent_failure_domain_proved
        && !packet.checkpoint_input.same_failure_domain_as_database
        && packet.checkpoint_input.acknowledgement_semantics_validated
        && packet.external_registration.registration_state == "AUTHORIZED_UNCLAIMED_PRESENT"
        && registration_revision_exact
        && unclaimed_projection
        && packet.external_registration.binding_validated
        && packet
            .external_registration
            .registered_by_external_control_plane
        && !packet.external_registration.created_by_runner
        && packet.runtime_inputs.fresh_observer_present_and_bound
        && packet.runtime_inputs.real_runner_present_and_bound
        && packet.runtime_inputs.exact_environment_present_and_bound
        && packet.runtime_inputs.exact_canary_inputs_present_and_bound
        && packet.runtime_inputs.stop_and_revocation_fresh_and_exact
        && revocation_epoch_exact
        && packet.result.all_external_inputs_validated
        && !packet.result.terminal_hard_lock;
    let hard_locked_projection_valid = !packet
        .subject_binding
        .final_post_integration_subject_validated
        && !packet
            .subject_binding
            .exact_s21a_commit_tree_and_build_bound
        && !packet.owner_binding.new_owner_signature_valid
        && !packet.owner_binding.trust_anchor_installed_and_pinned
        && packet.checkpoint_input.checkpoint_state == "MISSING"
        && !packet.checkpoint_input.provider_present
        && !packet.checkpoint_input.independent_failure_domain_proved
        && !packet.checkpoint_input.same_failure_domain_as_database
        && !packet.checkpoint_input.acknowledgement_semantics_validated
        && packet.external_registration.registration_state == "MISSING"
        && registration_revision_exact
        && unclaimed_projection
        && !packet.external_registration.binding_validated
        && !packet
            .external_registration
            .registered_by_external_control_plane
        && !packet.external_registration.created_by_runner
        && !packet.runtime_inputs.fresh_observer_present_and_bound
        && !packet.runtime_inputs.real_runner_present_and_bound
        && !packet.runtime_inputs.exact_environment_present_and_bound
        && !packet.runtime_inputs.exact_canary_inputs_present_and_bound
        && !packet.runtime_inputs.stop_and_revocation_fresh_and_exact
        && revocation_epoch_exact;
    let blocked_valid = !packet.test_only
        && !packet.synthetic
        && !packet.result.all_external_inputs_validated
        && packet.result.terminal_hard_lock;
    let synthetic_valid = packet.test_only
        && packet.synthetic
        && !packet.result.all_external_inputs_validated
        && packet.result.terminal_hard_lock
        && hard_locked_projection_valid;
    let state_valid = match packet.admission_state.as_str() {
        "INPUTS_COMPLETE_PENDING_SEPARATE_REVIEW_NON_EXECUTING" => complete_valid,
        "BLOCKED_FAIL_CLOSED" => blocked_valid,
        "SYNTHETIC_KAT_BLOCKED_NON_LIVE" => synthetic_valid,
        _ => false,
    };
    if !common_valid || !state_valid {
        return Err(s21a_error(
            "s21a_admission_packet_shape",
            "typed admission packet is noncanonical, cross-inconsistent, executable, or state-invalid",
        ));
    }
    Ok(())
}

fn parse_s21_external_input_admission_v1(
    raw: &[u8],
) -> AuthorizationResult<S21ExternalInputAdmissionV1> {
    let packet: S21ExternalInputAdmissionV1 = parse_typed(raw)?;
    validate_external_admission_packet_shape(&packet)?;
    let digest = packet_digest(&packet, "admission_packet_sha256", ADMISSION_DOMAIN)?;
    if packet.admission_packet_sha256 != hex(&digest) {
        return Err(s21a_error(
            "s21a_admission_packet_self",
            "admission packet self digest does not recompute",
        ));
    }
    Ok(packet)
}

fn build_s21_external_input_admission_v1(
    owner: &VerifiedS21OwnerBoundSubjectV1,
    facts: &ExternalAdmissionFactsV1,
    expected: &PinnedExternalAdmissionExpectationsV1,
) -> AuthorizationResult<CanonicalBuiltS21ExternalInputAdmissionV1> {
    validate_s21_external_fact_contract_v1(owner, facts, expected)?;
    let mut packet = S21ExternalInputAdmissionV1 {
        schema: ADMISSION_SCHEMA.into(),
        packet_kind: ADMISSION_KIND.into(),
        canonicalization: CANONICALIZATION.into(),
        hashing_contract: HashingContractV1::exact(
            ADMISSION_DOMAIN,
            "ENTIRE_PACKET_EXCEPT_ADMISSION_PACKET_SHA256",
            "admission_packet_sha256",
        ),
        admission_state: "INPUTS_COMPLETE_PENDING_SEPARATE_REVIEW_NON_EXECUTING".into(),
        test_only: false,
        synthetic: false,
        subject_binding: AdmissionSubjectBindingV1 {
            final_refreeze_subject_sha256: hex(&owner.subject.digest),
            final_post_integration_subject_validated: true,
            exact_s21a_commit_tree_and_build_bound: true,
            any_post_freeze_change_observed: false,
        },
        owner_binding: AdmissionOwnerBindingV1 {
            anchor_document_sha256: hex(&owner.anchor.document_sha256),
            owner_envelope_sha256: hex(&owner.owner_envelope_sha256),
            audience: OWNER_AUDIENCE.into(),
            signature_domain: std::str::from_utf8(SIGNATURE_DOMAIN).unwrap().into(),
            new_owner_signature_valid: true,
            trust_anchor_installed_and_pinned: true,
            legacy_s19_signature_or_envelope_reused: false,
        },
        checkpoint_input: AdmissionCheckpointInputV1 {
            authorization_id_sha256: hex(&owner.authorization_id_sha256),
            final_refreeze_subject_sha256: hex(&owner.subject.digest),
            owner_envelope_sha256: hex(&owner.owner_envelope_sha256),
            provider_identity_sha256: hex(&facts.checkpoint.provider_identity_sha256),
            provider_trust_anchor_sha256: hex(&facts.checkpoint.provider_trust_anchor_sha256),
            provider_policy_sha256: hex(&facts.checkpoint.provider_policy_sha256),
            provider_failure_domain_sha256: hex(&facts.checkpoint.provider_failure_domain_sha256),
            database_failure_domain_sha256: hex(&facts.checkpoint.database_failure_domain_sha256),
            checkpoint_receipt_sha256: hex(&facts.checkpoint.checkpoint_receipt_sha256),
            checkpoint_head_sha256: hex(&facts.checkpoint.checkpoint_head_sha256),
            committed_content_root_sha256: hex(&facts.checkpoint.database_content_root_sha256),
            monotonic_counter: facts.checkpoint.monotonic_counter,
            previous_checkpoint_sha256: facts
                .checkpoint
                .previous_checkpoint_head_sha256
                .as_ref()
                .map(|value| hex(value)),
            observed_revocation_epoch: facts.checkpoint.observed_revocation_epoch,
            checkpoint_state: "COMMITTED_CURRENT".into(),
            provider_present: true,
            independent_failure_domain_proved: true,
            same_failure_domain_as_database: false,
            acknowledgement_semantics_validated: true,
        },
        external_registration: AdmissionExternalRegistrationV1 {
            authorization_id_sha256: hex(&owner.authorization_id_sha256),
            final_refreeze_subject_sha256: hex(&owner.subject.digest),
            owner_envelope_sha256: hex(&owner.owner_envelope_sha256),
            capability_nonce_sha256: hex(&owner.capability_nonce_sha256),
            expected_unclaimed_revision: facts.registration.revision,
            registration_revision: facts.registration.revision,
            previous_revision: facts.registration.previous_revision,
            registration_receipt_sha256: hex(&facts.registration.registration_receipt_sha256),
            registrar_identity_sha256: hex(&facts.registration.registrar_identity_sha256),
            external_control_plane_identity_sha256: hex(&facts
                .registration
                .external_control_plane_identity_sha256),
            provenance_receipt_sha256: hex(&facts.registration.provenance_receipt_sha256),
            creator_binary_sha256: hex(&facts.registration.creator_binary_sha256),
            registration_state: "AUTHORIZED_UNCLAIMED_PRESENT".into(),
            binding_validated: true,
            registered_by_external_control_plane: true,
            created_by_runner: false,
            successful_claim_count: 0,
            claimed_run_id_sha256: None,
        },
        runtime_inputs: AdmissionRuntimeInputsV1 {
            controller_binary_sha256: hex(&facts.runtime.controller_binary_sha256),
            observer_source_sha256: hex(&facts.runtime.observer_source_sha256),
            observer_binary_sha256: hex(&facts.runtime.observer_binary_sha256),
            observer_toolchain_sha256: hex(&facts.runtime.observer_toolchain_sha256),
            observer_measurement_receipt_sha256: hex(&facts
                .runtime
                .observer_measurement_receipt_sha256),
            runner_source_sha256: hex(&facts.runtime.runner_source_sha256),
            runner_binary_sha256: hex(&facts.runtime.runner_binary_sha256),
            runner_toolchain_sha256: hex(&facts.runtime.runner_toolchain_sha256),
            runner_operation_manifest_sha256: hex(&facts.runtime.runner_operation_manifest_sha256),
            environment_observation_receipt_sha256: hex(&facts.runtime.environment_receipt_sha256),
            canary_input_pack_sha256: hex(&facts.runtime.canary_input_pack_sha256),
            stop_snapshot_sha256: hex(&facts.control.stop_snapshot_sha256),
            revocation_snapshot_sha256: hex(&facts.control.revocation_snapshot_sha256),
            fresh_observer_present_and_bound: true,
            real_runner_present_and_bound: true,
            exact_environment_present_and_bound: true,
            exact_canary_inputs_present_and_bound: true,
            stop_and_revocation_fresh_and_exact: true,
            live_action_count: 0,
        },
        policy_bindings: AdmissionPolicyBindingsV1 {
            lab_environment_sha256: hex(&facts.control.lab_environment_sha256),
            stop_policy_sha256: hex(&facts.control.stop_policy_sha256),
            revocation_policy_sha256: hex(&facts.control.revocation_policy_sha256),
            retention_policy_sha256: hex(&facts.control.retention_policy_sha256),
            cleanup_policy_sha256: hex(&facts.control.cleanup_policy_sha256),
            custody_policy_sha256: hex(&facts.control.custody_policy_sha256),
            review_policy_sha256: hex(&facts.control.review_policy_sha256),
            independent_review_receipt_sha256: hex(&facts
                .control
                .independent_review_receipt_sha256),
            current_revocation_epoch: facts.control.current_revocation_epoch,
            automatic_or_implicit_retry_allowed: false,
        },
        result: AdmissionResultV1 {
            all_external_inputs_validated: true,
            terminal_hard_lock: false,
            separate_review_required: true,
            may_execute_live: false,
            execution_capability_issued: false,
            side_effects_unlocked: S21A_SIDE_EFFECTS_UNLOCKED.into(),
        },
        admission_packet_sha256: "0".repeat(64),
        nonclaims: AdmissionNonclaimsV1 {
            admission_packet_is_owner_authority: false,
            admission_packet_is_execution_capability: false,
            complete_inputs_preapprove_s21b: false,
            synthetic_fixture_is_live_input: false,
            valid_evidence_implies_favorable_result: false,
            side_effects_unlocked: S21A_SIDE_EFFECTS_UNLOCKED.into(),
        },
    };
    validate_external_admission_packet_shape(&packet)?;
    let digest = packet_digest(&packet, "admission_packet_sha256", ADMISSION_DOMAIN)?;
    packet.admission_packet_sha256 = hex(&digest);
    Ok(CanonicalBuiltS21ExternalInputAdmissionV1 {
        canonical_bytes: canonical_typed(&packet)?,
        digest,
    })
}

fn verify_s21_external_input_admission_v1(
    candidate_raw: &[u8],
    owner: VerifiedS21OwnerBoundSubjectV1,
    facts: ExternalAdmissionFactsV1,
    expected: &PinnedExternalAdmissionExpectationsV1,
) -> AuthorizationResult<ValidatedS21ExternalInputReadinessV1> {
    let candidate = parse_s21_external_input_admission_v1(candidate_raw)?;
    if candidate.admission_state != "INPUTS_COMPLETE_PENDING_SEPARATE_REVIEW_NON_EXECUTING" {
        return Err(s21a_error(
            "s21a_admission_candidate_state",
            "only a complete non-executing candidate can enter exact verification",
        ));
    }
    let rebuilt = build_s21_external_input_admission_v1(&owner, &facts, expected)?;
    if repository_payload(candidate_raw)? != rebuilt.canonical_bytes
        || candidate.admission_packet_sha256 != hex(&rebuilt.digest)
    {
        return Err(s21a_error(
            "s21a_admission_independent_expected",
            "candidate admission packet differs from independently rebuilt trusted facts",
        ));
    }
    let fact_readiness = validate_s21_external_fact_contract_v1(&owner, &facts, expected)?;
    let mut readiness = Vec::new();
    append_u32_frame(
        &mut readiness,
        b"agent-bridge/biocortex/owned-lab/s21a/typed-non-executing-readiness/v1",
    )?;
    append_u64_frame(&mut readiness, &rebuilt.digest)?;
    append_u64_frame(&mut readiness, &fact_readiness)?;
    Ok(ValidatedS21ExternalInputReadinessV1 {
        _owner: owner,
        admission_packet_sha256: rebuilt.digest,
        readiness_sha256: sha256_bytes(&readiness),
    })
}

#[cfg(test)]
mod tests {
    use super::*;
    use ring::rand::SystemRandom;
    use ring::signature::{Ed25519KeyPair, KeyPair};

    fn digest(byte: u8) -> [u8; 32] {
        [byte; 32]
    }

    fn digest_hex(byte: u8) -> String {
        hex(&digest(byte))
    }

    fn oid_hex(byte: u8) -> String {
        hex(&[byte; 20])
    }

    fn real_subject_inputs() -> IndependentS21RefreezeInputsV1 {
        IndependentS21RefreezeInputsV1 {
            test_only: false,
            s21a_source_commit: Some(oid_hex(0x21)),
            s21a_source_tree: Some(oid_hex(0x22)),
            s21a_integration_commit: Some(oid_hex(0x23)),
            s21a_integration_tree: Some(oid_hex(0x24)),
            build_bindings: BuildBindingsV1 {
                exact_integrated_archive_sha256: digest_hex(0x25),
                cargo_lock_sha256: CARGO_LOCK_SHA256.into(),
                controller_binary_sha256: digest_hex(0x26),
                observer_binary_sha256: digest_hex(0x27),
                runner_binary_sha256: digest_hex(0x28),
                validator_binary_sha256: digest_hex(0x29),
                toolchain_manifest_sha256: digest_hex(0x2a),
                feature_set_sha256: digest_hex(0x2b),
                candidate_supplied_expected_digest_used: false,
            },
            artifact_bindings: ArtifactBindingsV1 {
                schema_set_sha256: digest_hex(0x2c),
                assignment_set_sha256: ASSIGNMENT_SET_SHA256.into(),
                schedule_sha256: SCHEDULE_SHA256.into(),
                assignment_record_set_sha256: ASSIGNMENT_RECORD_SET_SHA256.into(),
                operation_descriptor_set_sha256: OPERATION_DESCRIPTOR_SET_SHA256.into(),
                catalog_row_count: 5_639,
                catalog_sha256: CATALOG_SHA256.into(),
                validator_rule_count: 32,
                validator_ruleset_sha256: VALIDATOR_RULESET_SHA256.into(),
                target_phase_count: 113,
                s20b_gate_sha256: S20B_GATE_SHA256.into(),
                s20b_checker_sha256: S20B_CHECKER_SHA256.into(),
                s20b_report_sha256: S20B_REPORT_SHA256.into(),
                s20b_source_delta_file_count: 23,
            },
        }
    }

    fn synthetic_subject_inputs() -> IndependentS21RefreezeInputsV1 {
        let mut inputs = real_subject_inputs();
        inputs.test_only = true;
        inputs.s21a_source_commit = None;
        inputs.s21a_source_tree = None;
        inputs.s21a_integration_commit = None;
        inputs.s21a_integration_tree = None;
        inputs
    }

    fn ephemeral_key_pair() -> Ed25519KeyPair {
        let pkcs8 = Ed25519KeyPair::generate_pkcs8(&SystemRandom::new()).unwrap();
        Ed25519KeyPair::from_pkcs8(pkcs8.as_ref()).unwrap()
    }

    fn seal_anchor(mut anchor: S21OwnerTrustAnchorV1) -> Vec<u8> {
        let digest = packet_digest(&anchor, "anchor_document_sha256", ANCHOR_DOMAIN).unwrap();
        anchor.anchor_document_sha256 = hex(&digest);
        canonical_typed(&anchor).unwrap()
    }

    fn installed_anchor(key_pair: &Ed25519KeyPair) -> (Vec<u8>, PinnedS21OwnerTrustExpectationsV1) {
        let owner_identity = digest(0x31);
        let trust_policy = digest(0x32);
        let installation = digest(0x33);
        let identity_receipt = digest(0x34);
        let anchor = S21OwnerTrustAnchorV1 {
            schema: ANCHOR_SCHEMA.into(),
            packet_kind: ANCHOR_KIND.into(),
            canonicalization: CANONICALIZATION.into(),
            hashing_contract: HashingContractV1::exact(
                ANCHOR_DOMAIN,
                "ENTIRE_PACKET_EXCEPT_ANCHOR_DOCUMENT_SHA256",
                "anchor_document_sha256",
            ),
            anchor_state: "INSTALLED_OUT_OF_BAND_CALLER_PINNED".into(),
            test_only: false,
            synthetic: false,
            audience: OWNER_AUDIENCE.into(),
            owner_identity: OwnerIdentityV1 {
                owner_identity_sha256: hex(&owner_identity),
                owner_role: "AGENT_BRIDGE_OWNED_LAB_EXECUTION_OWNER".into(),
                identity_verified_out_of_band: true,
                owner_identity_verification_receipt_sha256: Some(hex(&identity_receipt)),
            },
            key_binding: OwnerKeyBindingV1 {
                algorithm: "Ed25519".into(),
                key_id: "s21a-test-owner-v1".into(),
                key_version: 9,
                public_key_hex: hex(key_pair.public_key().as_ref()),
                legacy_s19_key_reuse_allowed: false,
                private_key_present_in_repository: false,
            },
            trust_policy: OwnerTrustPolicyV1 {
                trust_policy_sha256: hex(&trust_policy),
                minimum_revocation_epoch: 7,
                installed_out_of_band: true,
                pinned_by_independent_caller: true,
                installation_receipt_sha256: Some(hex(&installation)),
                candidate_carried_key_is_trusted: false,
            },
            anchor_document_sha256: "0".repeat(64),
            nonclaims: AnchorNonclaimsV1 {
                anchor_is_owner_signature: false,
                anchor_is_execution_capability: false,
                public_kat_is_installed_anchor: false,
                schema_conformance_establishes_trust: false,
                side_effects_unlocked: S21A_SIDE_EFFECTS_UNLOCKED.into(),
            },
        };
        let raw = seal_anchor(anchor);
        let parsed: S21OwnerTrustAnchorV1 = parse_typed(&raw).unwrap();
        let anchor_sha256 =
            require_sha256(&parsed.anchor_document_sha256, "s21a_test_anchor_digest").unwrap();
        (
            raw,
            PinnedS21OwnerTrustExpectationsV1 {
                anchor_document_sha256: anchor_sha256,
                owner_identity_sha256: owner_identity,
                key_id: "s21a-test-owner-v1".into(),
                key_version: 9,
                public_key: key_pair.public_key().as_ref().try_into().unwrap(),
                trust_policy_sha256: trust_policy,
                installation_receipt_sha256: installation,
                owner_identity_verification_receipt_sha256: identity_receipt,
                minimum_revocation_epoch: 7,
                independent_installation_confirmed: true,
                independent_pin_confirmed: true,
                expected_current_revocation_epoch: 9,
            },
        )
    }

    fn seal_envelope(mut envelope: S21OwnerAuthorizationEnvelopeV1) -> Vec<u8> {
        let digest = packet_digest(&envelope, "owner_envelope_sha256", ENVELOPE_DOMAIN).unwrap();
        envelope.owner_envelope_sha256 = hex(&digest);
        canonical_typed(&envelope).unwrap()
    }

    fn seal_admission(mut packet: S21ExternalInputAdmissionV1) -> Vec<u8> {
        let digest = packet_digest(&packet, "admission_packet_sha256", ADMISSION_DOMAIN).unwrap();
        packet.admission_packet_sha256 = hex(&digest);
        canonical_typed(&packet).unwrap()
    }

    fn owner_envelope(
        subject_sha256: [u8; 32],
        anchor_sha256: [u8; 32],
        key_pair: &Ed25519KeyPair,
    ) -> Vec<u8> {
        let payload = SignedOwnerPayloadV1 {
            audience: OWNER_AUDIENCE.into(),
            final_refreeze_subject_sha256: hex(&subject_sha256),
            anchor_document_sha256: hex(&anchor_sha256),
            s20b_integration_commit: S20B_INTEGRATION_COMMIT.into(),
            s20b_integration_tree: S20B_INTEGRATION_TREE.into(),
            challenge_nonce_sha256: digest_hex(0x41),
            capability_nonce_sha256: digest_hex(0x42),
            revocation_epoch: 9,
            single_use: true,
            automatic_retry_allowed: false,
        };
        let payload_sha256 =
            framed_payload_digest(SIGNED_PAYLOAD_DOMAIN, &canonical_typed(&payload).unwrap())
                .unwrap();
        let signature = key_pair.sign(&signature_message(&payload_sha256).unwrap());
        let signature_sha256 = sha256_bytes(signature.as_ref());
        let authorization =
            authorization_id(&payload_sha256, &signature_sha256, &anchor_sha256).unwrap();
        seal_envelope(S21OwnerAuthorizationEnvelopeV1 {
            schema: ENVELOPE_SCHEMA.into(),
            packet_kind: ENVELOPE_KIND.into(),
            canonicalization: CANONICALIZATION.into(),
            hashing_contract: HashingContractV1::exact(
                ENVELOPE_DOMAIN,
                "ENTIRE_PACKET_EXCEPT_OWNER_ENVELOPE_SHA256",
                "owner_envelope_sha256",
            ),
            envelope_state: "OWNER_SIGNED_FINAL_SUBJECT_PENDING_EXTERNAL_INPUT_REVIEW".into(),
            test_only: false,
            synthetic: false,
            audience: OWNER_AUDIENCE.into(),
            anchor_binding: EnvelopeAnchorBindingV1 {
                anchor_document_sha256: hex(&anchor_sha256),
                anchor_key_id: "s21a-test-owner-v1".into(),
                anchor_key_version: 9,
                anchor_installed_out_of_band: true,
                anchor_pinned_by_independent_caller: true,
                candidate_carried_key_used: false,
            },
            signed_payload: payload,
            signature_binding: SignatureBindingV1 {
                algorithm: "Ed25519".into(),
                signed_payload_digest_domain: std::str::from_utf8(SIGNED_PAYLOAD_DOMAIN)
                    .unwrap()
                    .into(),
                signed_payload_digest_framing: DIGEST_FRAMING.into(),
                signature_domain: std::str::from_utf8(SIGNATURE_DOMAIN).unwrap().into(),
                message_framing: "U32BE_DOMAIN_LENGTH_DOMAIN_U64BE_32_RAW_SIGNED_PAYLOAD_SHA256"
                    .into(),
                signed_payload_sha256: hex(&payload_sha256),
                signature_hex: hex(signature.as_ref()),
                detached_signature_sha256: hex(&signature_sha256),
                detached_signature_digest_profile: "SHA256_RAW_64_BYTE_ED25519_SIGNATURE".into(),
                signature_verified: true,
                legacy_s19_signature_or_envelope_reuse_allowed: false,
            },
            owner_decision: OwnerDecisionV1 {
                authorization_id_sha256: hex(&authorization),
                authorization_id_domain: std::str::from_utf8(AUTHORIZATION_ID_DOMAIN)
                    .unwrap()
                    .into(),
                authorization_id_framing: "U32BE_DOMAIN_LENGTH_DOMAIN_THREE_U64BE_32_RAW_SHA256"
                    .into(),
                decision: "OWNER_SIGNED_FINAL_SUBJECT_PENDING_EXTERNAL_INPUT_REVIEW".into(),
                owner_authority_established: true,
                execution_start_permitted: false,
                single_use_execution_capability_issued: false,
                separate_external_input_review_required: true,
            },
            owner_envelope_sha256: "0".repeat(64),
            nonclaims: EnvelopeNonclaimsV1 {
                envelope_is_execution_capability: false,
                envelope_preapproves_s21b: false,
                schema_conformance_proves_signature: false,
                synthetic_envelope_is_owner_authority: false,
                old_s19_signature_authorizes_s21a: false,
                side_effects_unlocked: S21A_SIDE_EFFECTS_UNLOCKED.into(),
            },
        })
    }

    struct OwnerFixture {
        subject_inputs: IndependentS21RefreezeInputsV1,
        subject_raw: Vec<u8>,
        anchor_raw: Vec<u8>,
        envelope_raw: Vec<u8>,
        pinned: PinnedS21OwnerTrustExpectationsV1,
    }

    fn owner_fixture() -> OwnerFixture {
        let inputs = real_subject_inputs();
        let subject = build_s21_refreeze_subject_v1(&inputs).unwrap();
        let key_pair = ephemeral_key_pair();
        let (anchor_raw, pinned) = installed_anchor(&key_pair);
        let envelope_raw = owner_envelope(subject.digest, pinned.anchor_document_sha256, &key_pair);
        OwnerFixture {
            subject_inputs: inputs,
            subject_raw: subject.canonical_bytes,
            anchor_raw,
            envelope_raw,
            pinned,
        }
    }

    fn verified_owner(fixture: OwnerFixture) -> VerifiedS21OwnerBoundSubjectV1 {
        let subject =
            verify_s21_refreeze_subject_v1(&fixture.subject_raw, &fixture.subject_inputs).unwrap();
        verify_s21_owner_envelope_v1(
            subject,
            &fixture.anchor_raw,
            &fixture.envelope_raw,
            &fixture.pinned,
        )
        .unwrap()
    }

    fn binding(owner: &VerifiedS21OwnerBoundSubjectV1) -> ExternalFactBindingV1 {
        ExternalFactBindingV1 {
            subject_sha256: owner.subject.digest,
            owner_envelope_sha256: owner.owner_envelope_sha256,
            authorization_id_sha256: owner.authorization_id_sha256,
            challenge_nonce_sha256: owner.challenge_nonce_sha256,
            capability_nonce_sha256: owner.capability_nonce_sha256,
        }
    }

    fn external_facts(
        owner: &VerifiedS21OwnerBoundSubjectV1,
    ) -> (
        ExternalAdmissionFactsV1,
        PinnedExternalAdmissionExpectationsV1,
    ) {
        let controller = digest(0x26);
        let observer_binary = digest(0x27);
        let runner_binary = digest(0x28);
        let expected = PinnedExternalAdmissionExpectationsV1 {
            checkpoint_provider_identity_sha256: digest(0x51),
            checkpoint_provider_trust_anchor_sha256: digest(0x52),
            checkpoint_provider_policy_sha256: digest(0x53),
            checkpoint_provider_failure_domain_sha256: digest(0x54),
            database_failure_domain_sha256: digest(0x55),
            checkpoint_receipt_sha256: digest(0x56),
            checkpoint_head_sha256: digest(0x57),
            previous_checkpoint_head_sha256: Some(digest(0x58)),
            database_content_root_sha256: digest(0x59),
            expected_checkpoint_counter: 11,
            registration_receipt_sha256: digest(0x5a),
            registrar_identity_sha256: digest(0x5b),
            external_control_plane_identity_sha256: digest(0x5c),
            registration_provenance_receipt_sha256: digest(0x5d),
            registration_creator_binary_sha256: digest(0x5e),
            expected_registration_revision: 13,
            expected_previous_registration_revision: 12,
            observer_source_sha256: digest(0x61),
            observer_binary_sha256: observer_binary,
            observer_toolchain_sha256: digest(0x62),
            observer_measurement_receipt_sha256: digest(0x63),
            runner_source_sha256: digest(0x64),
            runner_binary_sha256: runner_binary,
            runner_toolchain_sha256: digest(0x65),
            runner_operation_manifest_sha256: digest(0x66),
            environment_receipt_sha256: digest(0x67),
            canary_input_pack_sha256: digest(0x68),
            lab_environment_sha256: digest(0x6f),
            stop_policy_sha256: digest(0x70),
            revocation_policy_sha256: digest(0x71),
            stop_snapshot_sha256: digest(0x69),
            revocation_snapshot_sha256: digest(0x6a),
            retention_policy_sha256: digest(0x6b),
            cleanup_policy_sha256: digest(0x6c),
            custody_policy_sha256: digest(0x6d),
            review_policy_sha256: digest(0x72),
            independent_review_receipt_sha256: digest(0x6e),
        };
        let facts = ExternalAdmissionFactsV1 {
            checkpoint: ValidatedIndependentCheckpointFactsV1 {
                binding: binding(owner),
                provider_identity_sha256: expected.checkpoint_provider_identity_sha256,
                provider_trust_anchor_sha256: expected.checkpoint_provider_trust_anchor_sha256,
                provider_policy_sha256: expected.checkpoint_provider_policy_sha256,
                provider_failure_domain_sha256: expected.checkpoint_provider_failure_domain_sha256,
                database_failure_domain_sha256: expected.database_failure_domain_sha256,
                checkpoint_receipt_sha256: expected.checkpoint_receipt_sha256,
                checkpoint_head_sha256: expected.checkpoint_head_sha256,
                previous_checkpoint_head_sha256: expected.previous_checkpoint_head_sha256,
                database_content_root_sha256: expected.database_content_root_sha256,
                monotonic_counter: 11,
                observed_revocation_epoch: owner.revocation_epoch,
                state: ExternalCheckpointStateV1::CommittedCurrent,
                acknowledgement: ExternalAcknowledgementV1::KnownCommitted,
            },
            registration: ValidatedExternalRegistrationFactsV1 {
                binding: binding(owner),
                registration_receipt_sha256: expected.registration_receipt_sha256,
                registrar_identity_sha256: expected.registrar_identity_sha256,
                external_control_plane_identity_sha256: expected
                    .external_control_plane_identity_sha256,
                provenance_receipt_sha256: expected.registration_provenance_receipt_sha256,
                creator_binary_sha256: expected.registration_creator_binary_sha256,
                revision: 13,
                previous_revision: 12,
                state: ExternalRegistrationStateV1::AuthorizedUnclaimed,
                successful_claim_count: 0,
                claimed_run_id_sha256: None,
                created_by_runner: false,
            },
            runtime: ValidatedObserverRunnerFactsV1 {
                binding: binding(owner),
                controller_binary_sha256: controller,
                observer_source_sha256: expected.observer_source_sha256,
                observer_binary_sha256: observer_binary,
                observer_toolchain_sha256: expected.observer_toolchain_sha256,
                observer_measurement_receipt_sha256: expected.observer_measurement_receipt_sha256,
                runner_source_sha256: expected.runner_source_sha256,
                runner_binary_sha256: runner_binary,
                runner_toolchain_sha256: expected.runner_toolchain_sha256,
                runner_operation_manifest_sha256: expected.runner_operation_manifest_sha256,
                environment_receipt_sha256: expected.environment_receipt_sha256,
                canary_input_pack_sha256: expected.canary_input_pack_sha256,
                observer_fresh: true,
                build_recomputed_from_independent_receipts: true,
                runner_launch_count: 0,
            },
            control: ValidatedControlReviewFactsV1 {
                binding: binding(owner),
                lab_environment_sha256: expected.lab_environment_sha256,
                stop_policy_sha256: expected.stop_policy_sha256,
                revocation_policy_sha256: expected.revocation_policy_sha256,
                stop_snapshot_sha256: expected.stop_snapshot_sha256,
                revocation_snapshot_sha256: expected.revocation_snapshot_sha256,
                retention_policy_sha256: expected.retention_policy_sha256,
                cleanup_policy_sha256: expected.cleanup_policy_sha256,
                custody_policy_sha256: expected.custody_policy_sha256,
                review_policy_sha256: expected.review_policy_sha256,
                independent_review_receipt_sha256: expected.independent_review_receipt_sha256,
                current_revocation_epoch: owner.revocation_epoch,
                stop_state: ExternalStopStateV1::ClearCurrent,
                revocation_state: ExternalRevocationStateV1::ExactCurrent,
                automatic_retry_allowed: false,
                prior_attempt_count: 0,
                live_side_effect_count: 0,
                side_effects_unlocked: S21A_SIDE_EFFECTS_UNLOCKED.into(),
            },
        };
        (facts, expected)
    }

    fn assert_external_fact_mutation_rejects(
        mutate: impl FnOnce(&mut ExternalAdmissionFactsV1, &mut PinnedExternalAdmissionExpectationsV1),
    ) {
        let owner = verified_owner(owner_fixture());
        let (mut facts, mut expected) = external_facts(&owner);
        mutate(&mut facts, &mut expected);
        assert!(validate_s21_external_fact_contract_v1(&owner, &facts, &expected).is_err());
    }

    #[test]
    fn s21a_final_subject_roundtrip_freezes_exact_predecessor_and_lf_contract() {
        let inputs = real_subject_inputs();
        let built = build_s21_refreeze_subject_v1(&inputs).unwrap();
        let parsed = parse_s21_refreeze_subject_v1(&built.canonical_bytes).unwrap();
        assert_eq!(parsed.parent_bindings, exact_parent_bindings());
        let mut repository = built.canonical_bytes.clone();
        repository.push(b'\n');
        let verified = verify_s21_refreeze_subject_v1(&repository, &inputs).unwrap();
        assert_eq!(verified.digest, built.digest);
    }

    #[test]
    fn s21a_subject_noncanonical_duplicate_self_and_independent_build_drift_reject() {
        let inputs = real_subject_inputs();
        let built = build_s21_refreeze_subject_v1(&inputs).unwrap();
        let mut spaced = built.canonical_bytes.clone();
        spaced.insert(1, b' ');
        assert!(parse_s21_refreeze_subject_v1(&spaced).is_err());
        let mut value: Value = serde_json::from_slice(&built.canonical_bytes).unwrap();
        value["subject_sha256"] = Value::String("f".repeat(64));
        assert!(parse_s21_refreeze_subject_v1(&canonical_typed(&value).unwrap()).is_err());
        let mut drifted = real_subject_inputs();
        drifted.build_bindings.controller_binary_sha256 = digest_hex(0xee);
        assert!(verify_s21_refreeze_subject_v1(&built.canonical_bytes, &drifted).is_err());
    }

    #[test]
    fn s21a_repository_synthetic_subject_cannot_be_owner_authorized() {
        let inputs = synthetic_subject_inputs();
        let built = build_s21_refreeze_subject_v1(&inputs).unwrap();
        let subject = verify_s21_refreeze_subject_v1(&built.canonical_bytes, &inputs).unwrap();
        let key_pair = ephemeral_key_pair();
        let (anchor, pinned) = installed_anchor(&key_pair);
        let envelope = owner_envelope(subject.digest, pinned.anchor_document_sha256, &key_pair);
        assert!(verify_s21_owner_envelope_v1(subject, &anchor, &envelope, &pinned).is_err());
    }

    #[test]
    fn s21a_new_domain_detached_owner_signature_accepts_only_nonexecuting_review() {
        let owner = verified_owner(owner_fixture());
        assert!(nonzero(&owner.authorization_id_sha256));
        assert_eq!(owner.anchor.trust_policy_sha256, digest(0x32));
    }

    #[test]
    fn s21a_old_s19_signature_domain_and_legacy_reuse_reject() {
        let fixture = owner_fixture();
        let subject =
            verify_s21_refreeze_subject_v1(&fixture.subject_raw, &fixture.subject_inputs).unwrap();
        let mut envelope: S21OwnerAuthorizationEnvelopeV1 =
            parse_typed(&fixture.envelope_raw).unwrap();
        envelope.signature_binding.signature_domain =
            "agent-bridge/biocortex/owned-lab/s19/owner-signature/v1".into();
        envelope
            .signature_binding
            .legacy_s19_signature_or_envelope_reuse_allowed = true;
        let mutated = seal_envelope(envelope);
        assert!(verify_s21_owner_envelope_v1(
            subject,
            &fixture.anchor_raw,
            &mutated,
            &fixture.pinned,
        )
        .is_err());
    }

    #[test]
    fn s21a_self_authenticated_or_uninstalled_anchor_rejects() {
        let mut fixture = owner_fixture();
        fixture.pinned.independent_pin_confirmed = false;
        let subject =
            verify_s21_refreeze_subject_v1(&fixture.subject_raw, &fixture.subject_inputs).unwrap();
        assert!(verify_s21_owner_envelope_v1(
            subject,
            &fixture.anchor_raw,
            &fixture.envelope_raw,
            &fixture.pinned,
        )
        .is_err());
    }

    #[test]
    fn s21a_repository_public_kat_key_rejects_even_if_pinned() {
        let key_pair = ephemeral_key_pair();
        let (raw, mut pinned) = installed_anchor(&key_pair);
        let mut anchor: S21OwnerTrustAnchorV1 = parse_typed(&raw).unwrap();
        anchor.key_binding.key_id = S21A_REPOSITORY_PUBLIC_KAT_KEY_ID.into();
        let raw = seal_anchor(anchor);
        let parsed: S21OwnerTrustAnchorV1 = parse_typed(&raw).unwrap();
        pinned.key_id = S21A_REPOSITORY_PUBLIC_KAT_KEY_ID.into();
        pinned.anchor_document_sha256 = require_sha256(
            &parsed.anchor_document_sha256,
            "s21a_test_repository_kat_anchor",
        )
        .unwrap();
        assert!(parse_and_verify_owner_anchor_v1(&raw, &pinned).is_err());

        let key_pair = ephemeral_key_pair();
        let (raw, mut pinned) = installed_anchor(&key_pair);
        let mut anchor: S21OwnerTrustAnchorV1 = parse_typed(&raw).unwrap();
        anchor.key_binding.public_key_hex = S21A_REPOSITORY_PUBLIC_KAT_KEY_HEX.into();
        let raw = seal_anchor(anchor);
        let parsed: S21OwnerTrustAnchorV1 = parse_typed(&raw).unwrap();
        pinned.public_key = decode_hex_fixed::<32>(S21A_REPOSITORY_PUBLIC_KAT_KEY_HEX).unwrap();
        pinned.anchor_document_sha256 = require_sha256(
            &parsed.anchor_document_sha256,
            "s21a_test_repository_kat_anchor",
        )
        .unwrap();
        assert!(parse_and_verify_owner_anchor_v1(&raw, &pinned).is_err());
    }

    #[test]
    fn s21a_owner_identity_receipt_build_and_retry_drift_reject() {
        let fixture = owner_fixture();
        let subject =
            verify_s21_refreeze_subject_v1(&fixture.subject_raw, &fixture.subject_inputs).unwrap();
        let mut envelope: S21OwnerAuthorizationEnvelopeV1 =
            parse_typed(&fixture.envelope_raw).unwrap();
        envelope.signed_payload.automatic_retry_allowed = true;
        let mutated = seal_envelope(envelope);
        assert!(verify_s21_owner_envelope_v1(
            subject,
            &fixture.anchor_raw,
            &mutated,
            &fixture.pinned,
        )
        .is_err());

        let mut anchor: S21OwnerTrustAnchorV1 = parse_typed(&fixture.anchor_raw).unwrap();
        anchor
            .owner_identity
            .owner_identity_verification_receipt_sha256 = Some(digest_hex(0xee));
        let anchor = seal_anchor(anchor);
        assert!(parse_and_verify_owner_anchor_v1(&anchor, &fixture.pinned).is_err());
    }

    #[test]
    fn s21a_external_exact_digest_cross_bind_returns_nonpermit_readiness() {
        let owner = verified_owner(owner_fixture());
        let (facts, expected) = external_facts(&owner);
        let candidate = build_s21_external_input_admission_v1(&owner, &facts, &expected).unwrap();
        let readiness = verify_s21_external_input_admission_v1(
            &candidate.canonical_bytes,
            owner,
            facts,
            &expected,
        )
        .unwrap();
        assert_eq!(readiness.admission_packet_sha256, candidate.digest);
        assert!(nonzero(&readiness.readiness_sha256));
    }

    #[test]
    fn s21a_same_failure_domain_checkpoint_rejects() {
        let owner = verified_owner(owner_fixture());
        let (mut facts, expected) = external_facts(&owner);
        facts.checkpoint.provider_failure_domain_sha256 =
            facts.checkpoint.database_failure_domain_sha256;
        assert!(validate_s21_external_fact_contract_v1(&owner, &facts, &expected).is_err());
    }

    #[test]
    fn s21a_stale_forked_prepared_and_unknown_checkpoint_reject() {
        for state in [
            ExternalCheckpointStateV1::Stale,
            ExternalCheckpointStateV1::Forked,
            ExternalCheckpointStateV1::Prepared,
            ExternalCheckpointStateV1::Unknown,
        ] {
            let owner = verified_owner(owner_fixture());
            let (mut facts, expected) = external_facts(&owner);
            facts.checkpoint.state = state;
            assert!(validate_s21_external_fact_contract_v1(&owner, &facts, &expected).is_err());
        }
        let owner = verified_owner(owner_fixture());
        let (mut facts, expected) = external_facts(&owner);
        facts.checkpoint.acknowledgement = ExternalAcknowledgementV1::Unknown;
        assert!(validate_s21_external_fact_contract_v1(&owner, &facts, &expected).is_err());
    }

    #[test]
    fn s21a_runner_created_or_consumed_registration_rejects() {
        let owner = verified_owner(owner_fixture());
        let (mut facts, expected) = external_facts(&owner);
        facts.registration.created_by_runner = true;
        facts.registration.creator_binary_sha256 = facts.runtime.runner_binary_sha256;
        assert!(validate_s21_external_fact_contract_v1(&owner, &facts, &expected).is_err());

        let owner = verified_owner(owner_fixture());
        let (mut facts, expected) = external_facts(&owner);
        facts.registration.state = ExternalRegistrationStateV1::Consumed;
        assert!(validate_s21_external_fact_contract_v1(&owner, &facts, &expected).is_err());
    }

    #[test]
    fn s21a_observer_runner_build_and_environment_drift_reject() {
        let owner = verified_owner(owner_fixture());
        let (mut facts, expected) = external_facts(&owner);
        facts.runtime.runner_binary_sha256 = digest(0xee);
        assert!(validate_s21_external_fact_contract_v1(&owner, &facts, &expected).is_err());

        let owner = verified_owner(owner_fixture());
        let (mut facts, expected) = external_facts(&owner);
        facts.runtime.environment_receipt_sha256 = digest(0xef);
        assert!(validate_s21_external_fact_contract_v1(&owner, &facts, &expected).is_err());
    }

    #[test]
    fn s21a_retry_stop_revocation_and_side_effect_inputs_reject() {
        let owner = verified_owner(owner_fixture());
        let (mut facts, expected) = external_facts(&owner);
        facts.control.automatic_retry_allowed = true;
        facts.control.prior_attempt_count = 1;
        facts.control.side_effects_unlocked = "LIVE".into();
        assert!(validate_s21_external_fact_contract_v1(&owner, &facts, &expected).is_err());

        let owner = verified_owner(owner_fixture());
        let (mut facts, expected) = external_facts(&owner);
        facts.control.stop_state = ExternalStopStateV1::Triggered;
        facts.control.revocation_state = ExternalRevocationStateV1::RollbackDetected;
        assert!(validate_s21_external_fact_contract_v1(&owner, &facts, &expected).is_err());
    }

    #[test]
    fn s21a_subject_catalog_and_validator_ruleset_are_exactly_pinned() {
        let mut catalog_drift = real_subject_inputs();
        catalog_drift.artifact_bindings.catalog_sha256 = digest_hex(0xee);
        assert!(build_s21_refreeze_subject_v1(&catalog_drift).is_err());

        let mut ruleset_drift = real_subject_inputs();
        ruleset_drift.artifact_bindings.validator_ruleset_sha256 = digest_hex(0xef);
        assert!(build_s21_refreeze_subject_v1(&ruleset_drift).is_err());
        assert_eq!(
            real_subject_inputs().artifact_bindings.catalog_sha256,
            CATALOG_SHA256
        );
        assert_eq!(
            real_subject_inputs()
                .artifact_bindings
                .validator_ruleset_sha256,
            VALIDATOR_RULESET_SHA256
        );
    }

    #[test]
    fn s21a_owner_key_id_and_u32_revision_boundaries_are_exact() {
        assert!(valid_s21_owner_key_id("Owner.Key_9-v1"));
        assert!(valid_s21_owner_key_id(&"A".repeat(96)));
        assert!(!valid_s21_owner_key_id("owner:key"));
        assert!(!valid_s21_owner_key_id(&"A".repeat(97)));

        let mut fixture = owner_fixture();
        fixture.pinned.key_version = u64::from(u32::MAX) + 1;
        let subject =
            verify_s21_refreeze_subject_v1(&fixture.subject_raw, &fixture.subject_inputs).unwrap();
        assert!(verify_s21_owner_envelope_v1(
            subject,
            &fixture.anchor_raw,
            &fixture.envelope_raw,
            &fixture.pinned,
        )
        .is_err());

        let mut fixture = owner_fixture();
        fixture.pinned.expected_current_revocation_epoch = u64::from(u32::MAX) + 1;
        let subject =
            verify_s21_refreeze_subject_v1(&fixture.subject_raw, &fixture.subject_inputs).unwrap();
        assert!(verify_s21_owner_envelope_v1(
            subject,
            &fixture.anchor_raw,
            &fixture.envelope_raw,
            &fixture.pinned,
        )
        .is_err());
    }

    #[test]
    fn s21a_typed_admission_parser_and_exact_rebuild_reject_resealed_drift() {
        let owner = verified_owner(owner_fixture());
        let (facts, expected) = external_facts(&owner);
        let built = build_s21_external_input_admission_v1(&owner, &facts, &expected).unwrap();
        let mut candidate = parse_s21_external_input_admission_v1(&built.canonical_bytes).unwrap();
        candidate.external_registration.provenance_receipt_sha256 = digest_hex(0xee);
        let resealed = seal_admission(candidate);
        assert!(parse_s21_external_input_admission_v1(&resealed).is_ok());
        assert!(
            verify_s21_external_input_admission_v1(&resealed, owner, facts, &expected,).is_err()
        );
    }

    #[test]
    fn s21a_typed_synthetic_packet_requires_all_fail_closed_booleans() {
        let owner = verified_owner(owner_fixture());
        let (facts, expected) = external_facts(&owner);
        let built = build_s21_external_input_admission_v1(&owner, &facts, &expected).unwrap();
        let mut packet: S21ExternalInputAdmissionV1 = parse_typed(&built.canonical_bytes).unwrap();
        packet.admission_state = "SYNTHETIC_KAT_BLOCKED_NON_LIVE".into();
        packet.test_only = true;
        packet.synthetic = true;
        packet
            .subject_binding
            .final_post_integration_subject_validated = false;
        packet
            .subject_binding
            .exact_s21a_commit_tree_and_build_bound = false;
        packet.owner_binding.new_owner_signature_valid = false;
        packet.owner_binding.trust_anchor_installed_and_pinned = false;
        packet.checkpoint_input.checkpoint_state = "MISSING".into();
        packet.checkpoint_input.provider_present = false;
        packet.checkpoint_input.independent_failure_domain_proved = false;
        packet.checkpoint_input.acknowledgement_semantics_validated = false;
        packet.external_registration.registration_state = "MISSING".into();
        packet.external_registration.binding_validated = false;
        packet
            .external_registration
            .registered_by_external_control_plane = false;
        packet.runtime_inputs.fresh_observer_present_and_bound = false;
        packet.runtime_inputs.real_runner_present_and_bound = false;
        packet.runtime_inputs.exact_environment_present_and_bound = false;
        packet.runtime_inputs.exact_canary_inputs_present_and_bound = false;
        packet.runtime_inputs.stop_and_revocation_fresh_and_exact = false;
        packet.result.all_external_inputs_validated = false;
        packet.result.terminal_hard_lock = true;
        let synthetic = seal_admission(packet);
        let parsed = parse_s21_external_input_admission_v1(&synthetic).unwrap();
        assert!(parsed.test_only && parsed.synthetic);

        let mut misleading: S21ExternalInputAdmissionV1 = parse_typed(&synthetic).unwrap();
        misleading.owner_binding.new_owner_signature_valid = true;
        assert!(parse_s21_external_input_admission_v1(&seal_admission(misleading)).is_err());
    }

    #[test]
    fn s21a_repository_synthetic_admission_kat_parses_and_roundtrips_exactly() {
        let raw = include_bytes!(concat!(
            env!("CARGO_MANIFEST_DIR"),
            "/../../docs/design/fixtures/biocortex-ab-track-b-owned-lab-external-input-admission-synthetic-s21a-v0.json"
        ));
        let packet = parse_s21_external_input_admission_v1(raw).unwrap();
        assert!(packet.test_only && packet.synthetic);
        assert_eq!(
            repository_payload(raw).unwrap(),
            canonical_typed(&packet).unwrap()
        );
    }

    #[test]
    fn s21a_checkpoint_counter_and_optional_predecessor_are_exact() {
        let owner = verified_owner(owner_fixture());
        let (mut facts, mut expected) = external_facts(&owner);
        facts.checkpoint.monotonic_counter = 1;
        facts.checkpoint.previous_checkpoint_head_sha256 = None;
        expected.expected_checkpoint_counter = 1;
        expected.previous_checkpoint_head_sha256 = None;
        assert!(validate_s21_external_fact_contract_v1(&owner, &facts, &expected).is_ok());

        assert_external_fact_mutation_rejects(|facts, _| {
            facts.checkpoint.monotonic_counter += 1;
        });
        assert_external_fact_mutation_rejects(|facts, expected| {
            facts.checkpoint.monotonic_counter = 1;
            expected.expected_checkpoint_counter = 1;
        });
        assert_external_fact_mutation_rejects(|facts, expected| {
            facts.checkpoint.monotonic_counter = 2;
            expected.expected_checkpoint_counter = 2;
            facts.checkpoint.previous_checkpoint_head_sha256 = None;
            expected.previous_checkpoint_head_sha256 = None;
        });
    }

    #[test]
    fn s21a_policy_bindings_and_matching_all_zero_digests_reject() {
        assert_external_fact_mutation_rejects(|facts, _| {
            facts.control.lab_environment_sha256 = digest(0xe1);
        });
        assert_external_fact_mutation_rejects(|facts, _| {
            facts.control.stop_policy_sha256 = digest(0xe2);
        });
        assert_external_fact_mutation_rejects(|facts, _| {
            facts.control.revocation_policy_sha256 = digest(0xe3);
        });
        assert_external_fact_mutation_rejects(|facts, _| {
            facts.control.review_policy_sha256 = digest(0xe4);
        });
        assert_external_fact_mutation_rejects(|facts, expected| {
            facts.checkpoint.provider_identity_sha256 = [0; 32];
            expected.checkpoint_provider_identity_sha256 = [0; 32];
        });
        assert_external_fact_mutation_rejects(|facts, expected| {
            facts.control.review_policy_sha256 = [0; 32];
            expected.review_policy_sha256 = [0; 32];
        });
        assert_external_fact_mutation_rejects(|facts, _| {
            facts.registration.binding.authorization_id_sha256 = [0; 32];
        });
    }

    #[test]
    fn s21a_registration_revision_provenance_control_plane_and_claims_reject() {
        assert_external_fact_mutation_rejects(|facts, _| {
            facts.registration.provenance_receipt_sha256 = digest(0xe1);
        });
        assert_external_fact_mutation_rejects(|facts, _| {
            facts.registration.external_control_plane_identity_sha256 = digest(0xe2);
        });
        assert_external_fact_mutation_rejects(|facts, expected| {
            facts.registration.previous_revision = 11;
            expected.expected_previous_registration_revision = 11;
        });
        assert_external_fact_mutation_rejects(|facts, _| {
            facts.registration.successful_claim_count = 1;
            facts.registration.claimed_run_id_sha256 = Some(digest(0xe3));
        });

        let owner = verified_owner(owner_fixture());
        let (facts, expected) = external_facts(&owner);
        let built = build_s21_external_input_admission_v1(&owner, &facts, &expected).unwrap();
        let mut packet: S21ExternalInputAdmissionV1 = parse_typed(&built.canonical_bytes).unwrap();
        packet.external_registration.expected_unclaimed_revision += 1;
        assert!(parse_s21_external_input_admission_v1(&seal_admission(packet)).is_err());
    }

    #[test]
    fn s21a_no_real_external_constructor_live_backend_or_public_permit_exists() {
        assert!(S21A_TYPED_EXTERNAL_INPUT_PACKET_VALIDATOR_IMPLEMENTED);
        assert!(!S21A_REAL_EXTERNAL_FACT_CONSTRUCTOR_PRESENT);
        assert!(!S21A_LIVE_BACKEND_PRESENT);
        assert_eq!(S21A_SIDE_EFFECTS_UNLOCKED, "NONE");
    }
}
