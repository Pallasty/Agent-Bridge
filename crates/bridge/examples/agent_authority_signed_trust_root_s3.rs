//! Offline S3 verifier for canonical signed authority receipts.
//!
//! This example embeds public test roots and signed fixtures only. It does not
//! sign receipts, mutate replay state, invoke T6/MCP, or grant runtime authority.

use anyhow::{ensure, Context};
use base64::{engine::general_purpose::STANDARD, Engine as _};
use ring::signature::{UnparsedPublicKey, ED25519};
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use std::collections::{BTreeMap, BTreeSet};

const TRUST_REGISTRY_BYTES: &[u8] =
    include_bytes!("../tests/fixtures/agent_authority_trust_registry_s3.json");
const SIGNED_RECEIPTS_BYTES: &[u8] =
    include_bytes!("../tests/fixtures/agent_authority_signed_receipts_s3.json");
const S2_DESIGN_BYTES: &[u8] = include_bytes!(
    "../../../docs/design/AGENT_CONTROL_PLANE_AUTHORITY_PROVENANCE_ENVELOPE_S2_2026_07_16.md"
);
const S2_FIXTURE_BYTES: &[u8] =
    include_bytes!("../tests/fixtures/agent_authority_provenance_envelope_s2.json");
const S2_RESULT_BYTES: &[u8] = include_bytes!(
    "../../../docs/reports/goal-c-u/2026-07-16-agent-authority-provenance-envelope-s2-result.md"
);

const REGISTRY_SCHEMA: &str = "agent_bridge.agent_authority_trust_registry.s3.v0";
const CORPUS_SCHEMA: &str = "agent_bridge.agent_authority_signed_receipts.s3_fixture.v0";
const REPORT_SCHEMA: &str = "agent_bridge.agent_authority_signed_trust_root.s3_report.v0";
const CLAIMS_SCHEMA: &str = "agent_bridge.authority_signed_receipt_claims.s3.v0";
const ENVELOPE_VERSION: &str = "agent_bridge.authority_signed_receipt.v0";
const ACCEPTED_ALGORITHM: &str = "ed25519";
const POLICY_VERSION: &str = "ab.t6.signed_authority_review.v0";
const VERIFIER_ID: &str = "verifier:ring-ed25519-offline:v1";
const LATEST_MASTER_COMMIT: &str = "c9c50917687c7715b031a6bfe8dd7801bfd737ee";
const S2_RESULT_COMMIT: &str = "cdd426b846ff6c29bf008eba62a2d7bd57d09d4f";
const S3_LINEAGE_MERGE_COMMIT: &str = "c0267f617d1636e688cc3d6e12f326191574c198";
const TRUST_REGISTRY_SHA256: &str =
    "1e26edf7a5c71ac972d5c1c7e2496d8c1baa772d9571db995cfac04fe6c3d573";
const SIGNED_RECEIPTS_SHA256: &str =
    "1a15620e6dc16166d71b4458d5207eacf30579b8f631c48f85ac62fba2456d8d";
const EVALUATION_TIME_UNIX: u64 = 1_784_259_000;
const ALLOWED_CLOCK_SKEW_SECS: u64 = 30;
const CANONICAL_DOMAIN: &[u8] = b"agent_bridge.authority_signed_receipt.s3.claims.v0";

#[derive(Clone, Debug, Deserialize, Eq, PartialEq)]
#[serde(deny_unknown_fields)]
struct TrustRegistry {
    schema: String,
    registry_id: String,
    registry_version: String,
    algorithm_allowlist: Vec<String>,
    fixture_key_note: String,
    private_key_present: bool,
    production_trust_root: bool,
    keys: Vec<TrustKey>,
    read_only_snapshot: ReadOnlySnapshot,
}

#[derive(Clone, Debug, Deserialize, Eq, PartialEq)]
#[serde(deny_unknown_fields)]
struct TrustKey {
    key_id: String,
    algorithm: String,
    public_key_base64: String,
    allowed_issuer_id: String,
    allowed_principal_id: String,
    allowed_action_class: String,
    allowed_policy_version: String,
    not_before_unix: u64,
    not_after_unix: u64,
    revoked: bool,
}

#[derive(Clone, Debug, Deserialize, Eq, PartialEq)]
#[serde(deny_unknown_fields)]
struct ReadOnlySnapshot {
    snapshot_id: String,
    consumed_nonces: Vec<String>,
    revoked_receipt_ids: Vec<String>,
}

#[derive(Clone, Debug, Deserialize, Eq, PartialEq)]
#[serde(deny_unknown_fields)]
struct Corpus {
    schema: String,
    source: SourcePin,
    contract: Contract,
    fixture_signing_provenance: String,
    baseline_claims: Claims,
    cases: Vec<Case>,
}

#[derive(Clone, Debug, Deserialize, Eq, PartialEq)]
#[serde(deny_unknown_fields)]
struct SourcePin {
    latest_master_commit: String,
    s2_result_commit: String,
    s3_lineage_merge_commit: String,
    files: Vec<SourceFilePin>,
}

#[derive(Clone, Debug, Deserialize, Eq, PartialEq)]
#[serde(deny_unknown_fields)]
struct SourceFilePin {
    id: String,
    path: String,
    sha256: String,
}

#[derive(Clone, Debug, Deserialize, Eq, PartialEq)]
#[serde(deny_unknown_fields)]
struct Contract {
    claims_schema: String,
    accepted_envelope_version: String,
    accepted_algorithm: String,
    accepted_policy_version: String,
    expected_verifier_id: String,
    evaluation_time_unix: u64,
    allowed_clock_skew_secs: u64,
    expected_action_class: String,
    expected_target_digest: String,
    expected_scope_digest: String,
    expected_decision_source_digest: String,
    expected_session_epoch_digest: String,
    expected_resume_parent_digest: String,
    expected_adapter_id: String,
    expected_adapter_build_digest: String,
    expected_adapter_capabilities_digest: String,
    expected_evidence_digest: String,
    private_signing_material_embedded: bool,
    persistent_replay_state_mutation: bool,
    runtime_consumer_enabled: bool,
}

#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(deny_unknown_fields)]
struct Claims {
    claims_schema: String,
    envelope_version: String,
    receipt_id: String,
    issuer_id: String,
    principal_id: String,
    action_class: String,
    target_digest: String,
    scope_digest: String,
    decision_source_digest: String,
    session_epoch_digest: String,
    resume_parent_digest: String,
    adapter_id: String,
    adapter_build_digest: String,
    adapter_capabilities_digest: String,
    issued_at_unix: u64,
    expires_at_unix: u64,
    nonce: String,
    evidence_digest: String,
    verifier_id: String,
    policy_version: String,
    key_id: String,
    algorithm: String,
}

#[derive(Clone, Debug, Default, Deserialize, Eq, PartialEq)]
#[serde(default, deny_unknown_fields)]
struct ClaimsPatch {
    claims_schema: Option<String>,
    envelope_version: Option<String>,
    issuer_id: Option<String>,
    principal_id: Option<String>,
    action_class: Option<String>,
    target_digest: Option<String>,
    scope_digest: Option<String>,
    decision_source_digest: Option<String>,
    session_epoch_digest: Option<String>,
    resume_parent_digest: Option<String>,
    adapter_id: Option<String>,
    adapter_build_digest: Option<String>,
    adapter_capabilities_digest: Option<String>,
    issued_at_unix: Option<u64>,
    expires_at_unix: Option<u64>,
    nonce: Option<String>,
    evidence_digest: Option<String>,
    verifier_id: Option<String>,
    policy_version: Option<String>,
    key_id: Option<String>,
    algorithm: Option<String>,
}

impl ClaimsPatch {
    fn apply_to(&self, claims: &mut Claims) {
        macro_rules! replace {
            ($field:ident) => {
                if let Some(value) = &self.$field {
                    claims.$field = value.clone();
                }
            };
        }
        replace!(claims_schema);
        replace!(envelope_version);
        replace!(issuer_id);
        replace!(principal_id);
        replace!(action_class);
        replace!(target_digest);
        replace!(scope_digest);
        replace!(decision_source_digest);
        replace!(session_epoch_digest);
        replace!(resume_parent_digest);
        replace!(adapter_id);
        replace!(adapter_build_digest);
        replace!(adapter_capabilities_digest);
        if let Some(value) = self.issued_at_unix {
            claims.issued_at_unix = value;
        }
        if let Some(value) = self.expires_at_unix {
            claims.expires_at_unix = value;
        }
        replace!(nonce);
        replace!(evidence_digest);
        replace!(verifier_id);
        replace!(policy_version);
        replace!(key_id);
        replace!(algorithm);
    }
}

#[derive(Clone, Debug, Deserialize, Eq, PartialEq)]
#[serde(deny_unknown_fields)]
struct Case {
    id: String,
    control: bool,
    receipt_id: String,
    claims_overrides: ClaimsPatch,
    signature_base64: String,
    verifier_available: bool,
    expected_status: VerificationStatus,
    expected_reasons: Vec<String>,
}

#[derive(Clone, Copy, Debug, Deserialize, Eq, Ord, PartialEq, PartialOrd, Serialize)]
#[serde(rename_all = "snake_case")]
enum VerificationStatus {
    Verified,
    Invalid,
    Untrusted,
    Revoked,
    Stale,
    Replayed,
    OutOfScope,
    Unavailable,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq, Serialize)]
#[serde(rename_all = "snake_case")]
enum SignatureOutcome {
    NotAttempted,
    Verified,
    Failed,
}

#[derive(Clone, Copy)]
struct EmbeddedSource {
    path: &'static str,
    bytes: &'static [u8],
}

type EmbeddedSources = BTreeMap<&'static str, EmbeddedSource>;

#[derive(Clone, Copy, Debug, Default, Eq, PartialEq, Serialize)]
struct Authority {
    may_dispatch: bool,
    may_run_shadow: bool,
    may_enable_runtime: bool,
    may_write_memory: bool,
    may_write_graph: bool,
    may_change_retrieval: bool,
    may_change_session: bool,
    may_persist_replay_state: bool,
    production_trust_root_proven: bool,
    production_authority_granted: bool,
}

#[derive(Clone, Debug, Eq, PartialEq, Serialize)]
struct CaseResult {
    id: String,
    control: bool,
    receipt_id: String,
    key_id: String,
    canonical_claims_sha256: String,
    signature_outcome: SignatureOutcome,
    derived_status: VerificationStatus,
    expected_status: VerificationStatus,
    reasons: Vec<String>,
    expected_reasons: Vec<String>,
    status_matches: bool,
    reasons_match: bool,
    receipt_usable_for_later_owner_review: bool,
}

#[derive(Clone, Debug, Eq, PartialEq, Serialize)]
struct Report {
    schema: &'static str,
    status: &'static str,
    latest_master_commit: &'static str,
    s2_result_commit: &'static str,
    s3_lineage_merge_commit: &'static str,
    trust_registry_sha256: String,
    signed_receipts_sha256: String,
    source_sha256: BTreeMap<String, String>,
    crypto_verifier: &'static str,
    public_test_keys_only: bool,
    private_signing_material_embedded: bool,
    replay_snapshot_mutated: bool,
    runtime_consumer_enabled: bool,
    case_count: usize,
    verified_count: usize,
    invalid_count: usize,
    untrusted_count: usize,
    revoked_count: usize,
    stale_count: usize,
    replayed_count: usize,
    out_of_scope_count: usize,
    unavailable_count: usize,
    signature_verification_attempt_count: usize,
    signature_verification_success_count: usize,
    signature_verification_failure_count: usize,
    false_accept_count: usize,
    control_false_reject_count: usize,
    status_mismatch_count: usize,
    reason_mismatch_count: usize,
    authority: Authority,
    results: Vec<CaseResult>,
}

fn load_registry(bytes: &[u8]) -> anyhow::Result<TrustRegistry> {
    serde_json::from_slice(bytes).context("parse S3 authority trust registry")
}

fn load_corpus(bytes: &[u8]) -> anyhow::Result<Corpus> {
    serde_json::from_slice(bytes).context("parse S3 signed receipt corpus")
}

fn embedded_sources(
    s2_design: &'static [u8],
    s2_fixture: &'static [u8],
    s2_result: &'static [u8],
    trust_registry: &'static [u8],
) -> EmbeddedSources {
    BTreeMap::from([
        (
            "s2_design",
            EmbeddedSource {
                path: "docs/design/AGENT_CONTROL_PLANE_AUTHORITY_PROVENANCE_ENVELOPE_S2_2026_07_16.md",
                bytes: s2_design,
            },
        ),
        (
            "s2_fixture",
            EmbeddedSource {
                path: "crates/bridge/tests/fixtures/agent_authority_provenance_envelope_s2.json",
                bytes: s2_fixture,
            },
        ),
        (
            "s2_result",
            EmbeddedSource {
                path: "docs/reports/goal-c-u/2026-07-16-agent-authority-provenance-envelope-s2-result.md",
                bytes: s2_result,
            },
        ),
        (
            "trust_registry",
            EmbeddedSource {
                path: "crates/bridge/tests/fixtures/agent_authority_trust_registry_s3.json",
                bytes: trust_registry,
            },
        ),
    ])
}

fn claims_for_case(corpus: &Corpus, case: &Case) -> Claims {
    let mut claims = corpus.baseline_claims.clone();
    claims.receipt_id = case.receipt_id.clone();
    case.claims_overrides.apply_to(&mut claims);
    claims
}

fn canonical_claims_bytes(claims: &Claims) -> Vec<u8> {
    let mut bytes = Vec::with_capacity(2300);
    bytes.extend_from_slice(&(CANONICAL_DOMAIN.len() as u32).to_be_bytes());
    bytes.extend_from_slice(CANONICAL_DOMAIN);
    push_string_field(&mut bytes, "claims_schema", &claims.claims_schema);
    push_string_field(&mut bytes, "envelope_version", &claims.envelope_version);
    push_string_field(&mut bytes, "receipt_id", &claims.receipt_id);
    push_string_field(&mut bytes, "issuer_id", &claims.issuer_id);
    push_string_field(&mut bytes, "principal_id", &claims.principal_id);
    push_string_field(&mut bytes, "action_class", &claims.action_class);
    push_string_field(&mut bytes, "target_digest", &claims.target_digest);
    push_string_field(&mut bytes, "scope_digest", &claims.scope_digest);
    push_string_field(
        &mut bytes,
        "decision_source_digest",
        &claims.decision_source_digest,
    );
    push_string_field(
        &mut bytes,
        "session_epoch_digest",
        &claims.session_epoch_digest,
    );
    push_string_field(
        &mut bytes,
        "resume_parent_digest",
        &claims.resume_parent_digest,
    );
    push_string_field(&mut bytes, "adapter_id", &claims.adapter_id);
    push_string_field(
        &mut bytes,
        "adapter_build_digest",
        &claims.adapter_build_digest,
    );
    push_string_field(
        &mut bytes,
        "adapter_capabilities_digest",
        &claims.adapter_capabilities_digest,
    );
    push_u64_field(&mut bytes, "issued_at_unix", claims.issued_at_unix);
    push_u64_field(&mut bytes, "expires_at_unix", claims.expires_at_unix);
    push_string_field(&mut bytes, "nonce", &claims.nonce);
    push_string_field(&mut bytes, "evidence_digest", &claims.evidence_digest);
    push_string_field(&mut bytes, "verifier_id", &claims.verifier_id);
    push_string_field(&mut bytes, "policy_version", &claims.policy_version);
    push_string_field(&mut bytes, "key_id", &claims.key_id);
    push_string_field(&mut bytes, "algorithm", &claims.algorithm);
    bytes
}

fn push_field_name(bytes: &mut Vec<u8>, field: &str) {
    let length = u16::try_from(field.len()).expect("canonical field name fits u16");
    bytes.extend_from_slice(&length.to_be_bytes());
    bytes.extend_from_slice(field.as_bytes());
}

fn push_string_field(bytes: &mut Vec<u8>, field: &str, value: &str) {
    push_field_name(bytes, field);
    bytes.push(1);
    let length = u32::try_from(value.len()).expect("canonical string value fits u32");
    bytes.extend_from_slice(&length.to_be_bytes());
    bytes.extend_from_slice(value.as_bytes());
}

fn push_u64_field(bytes: &mut Vec<u8>, field: &str, value: u64) {
    push_field_name(bytes, field);
    bytes.push(2);
    bytes.extend_from_slice(&value.to_be_bytes());
}

fn validate_inputs(
    registry: &TrustRegistry,
    corpus: &Corpus,
    sources: &EmbeddedSources,
) -> anyhow::Result<()> {
    ensure!(
        registry.schema == REGISTRY_SCHEMA,
        "unexpected registry schema"
    );
    ensure!(
        !registry.registry_id.trim().is_empty(),
        "registry id is empty"
    );
    ensure!(
        !registry.registry_version.trim().is_empty(),
        "registry version is empty"
    );
    ensure!(
        !registry.fixture_key_note.trim().is_empty(),
        "fixture key note is empty"
    );
    ensure!(
        !registry.private_key_present,
        "registry must not contain a private key"
    );
    ensure!(
        !registry.production_trust_root,
        "fixture must not claim a production trust root"
    );
    validate_unique_nonempty(&registry.algorithm_allowlist, "algorithm allowlist")?;
    ensure!(
        registry.algorithm_allowlist == vec![ACCEPTED_ALGORITHM],
        "algorithm allowlist differs from frozen policy"
    );
    ensure!(registry.keys.len() == 6, "registry must contain six keys");

    let mut key_ids = BTreeSet::new();
    for key in &registry.keys {
        ensure!(
            !key.key_id.trim().is_empty() && key_ids.insert(key.key_id.as_str()),
            "duplicate or empty key id {}",
            key.key_id
        );
        ensure!(
            registry.algorithm_allowlist.contains(&key.algorithm),
            "{} uses an algorithm outside the registry allowlist",
            key.key_id
        );
        for (name, value) in [
            ("allowed_issuer_id", key.allowed_issuer_id.as_str()),
            ("allowed_principal_id", key.allowed_principal_id.as_str()),
            ("allowed_action_class", key.allowed_action_class.as_str()),
            (
                "allowed_policy_version",
                key.allowed_policy_version.as_str(),
            ),
        ] {
            ensure!(!value.trim().is_empty(), "{} {name} is empty", key.key_id);
        }
        ensure!(
            key.not_before_unix < key.not_after_unix,
            "{} has an invalid validity window",
            key.key_id
        );
        let public_key = STANDARD
            .decode(&key.public_key_base64)
            .with_context(|| format!("{} public key is not Base64", key.key_id))?;
        ensure!(
            public_key.len() == 32,
            "{} public key length is not 32 bytes",
            key.key_id
        );
    }

    ensure!(
        !registry.read_only_snapshot.snapshot_id.trim().is_empty(),
        "snapshot id is empty"
    );
    validate_unique_nonempty(
        &registry.read_only_snapshot.consumed_nonces,
        "consumed nonces",
    )?;
    validate_unique_nonempty(
        &registry.read_only_snapshot.revoked_receipt_ids,
        "revoked receipt ids",
    )?;

    ensure!(corpus.schema == CORPUS_SCHEMA, "unexpected corpus schema");
    ensure!(
        corpus.source.latest_master_commit == LATEST_MASTER_COMMIT,
        "unexpected latest-master commit"
    );
    ensure!(
        corpus.source.s2_result_commit == S2_RESULT_COMMIT,
        "unexpected S2 result commit"
    );
    ensure!(
        corpus.source.s3_lineage_merge_commit == S3_LINEAGE_MERGE_COMMIT,
        "unexpected S3 lineage merge commit"
    );
    validate_source_pins(&corpus.source, sources)?;
    validate_contract(&corpus.contract)?;
    ensure!(
        !corpus.fixture_signing_provenance.trim().is_empty(),
        "fixture signing provenance is empty"
    );

    let baseline_reasons = structural_reasons(&corpus.baseline_claims, &corpus.contract);
    ensure!(
        baseline_reasons.is_empty(),
        "baseline claims are structurally invalid: {}",
        baseline_reasons.into_iter().collect::<Vec<_>>().join(",")
    );

    ensure!(corpus.cases.len() == 27, "corpus must contain 27 cases");
    let mut case_ids = BTreeSet::new();
    let mut receipt_ids = BTreeSet::new();
    let mut nonces = BTreeSet::new();
    let mut control_count = 0usize;
    for case in &corpus.cases {
        ensure!(
            !case.id.trim().is_empty() && case_ids.insert(case.id.as_str()),
            "duplicate or empty case id {}",
            case.id
        );
        ensure!(
            !case.receipt_id.trim().is_empty() && receipt_ids.insert(case.receipt_id.as_str()),
            "duplicate or empty receipt id {}",
            case.receipt_id
        );
        ensure!(
            !case.signature_base64.trim().is_empty(),
            "{} has an empty signature",
            case.id
        );
        let claims = claims_for_case(corpus, case);
        ensure!(
            nonces.insert(claims.nonce.clone()),
            "duplicate case nonce {}",
            claims.nonce
        );
        validate_sorted_unique(&case.expected_reasons, &format!("{} reasons", case.id))?;
        control_count += usize::from(case.control);
    }
    ensure!(control_count == 4, "corpus must contain four controls");
    Ok(())
}

fn validate_source_pins(source: &SourcePin, sources: &EmbeddedSources) -> anyhow::Result<()> {
    ensure!(
        source.files.len() == sources.len(),
        "source pin count differs from embedded sources"
    );
    let mut ids = BTreeSet::new();
    for pin in &source.files {
        ensure!(
            ids.insert(pin.id.as_str()),
            "duplicate source id {}",
            pin.id
        );
        let embedded = sources
            .get(pin.id.as_str())
            .with_context(|| format!("unknown source id {}", pin.id))?;
        ensure!(pin.path == embedded.path, "{} source path changed", pin.id);
        ensure!(
            pin.sha256 == sha256(embedded.bytes),
            "{} source hash changed",
            pin.id
        );
    }
    Ok(())
}

fn validate_contract(contract: &Contract) -> anyhow::Result<()> {
    ensure!(
        contract.claims_schema == CLAIMS_SCHEMA,
        "unexpected claims schema"
    );
    ensure!(
        contract.accepted_envelope_version == ENVELOPE_VERSION,
        "unexpected envelope version"
    );
    ensure!(
        contract.accepted_algorithm == ACCEPTED_ALGORITHM,
        "unexpected accepted algorithm"
    );
    ensure!(
        contract.accepted_policy_version == POLICY_VERSION,
        "unexpected accepted policy version"
    );
    ensure!(
        contract.expected_verifier_id == VERIFIER_ID,
        "unexpected verifier id"
    );
    ensure!(
        contract.evaluation_time_unix == EVALUATION_TIME_UNIX,
        "unexpected evaluation time"
    );
    ensure!(
        contract.allowed_clock_skew_secs == ALLOWED_CLOCK_SKEW_SECS,
        "unexpected clock skew"
    );
    ensure!(
        !contract.private_signing_material_embedded,
        "private signing material must remain absent"
    );
    ensure!(
        !contract.persistent_replay_state_mutation,
        "persistent replay mutation must remain false"
    );
    ensure!(
        !contract.runtime_consumer_enabled,
        "runtime consumer must remain disabled"
    );
    for (name, value) in [
        (
            "expected_action_class",
            contract.expected_action_class.as_str(),
        ),
        ("expected_adapter_id", contract.expected_adapter_id.as_str()),
    ] {
        ensure!(!value.trim().is_empty(), "{name} is empty");
    }
    for (name, value) in [
        (
            "expected_target_digest",
            contract.expected_target_digest.as_str(),
        ),
        (
            "expected_scope_digest",
            contract.expected_scope_digest.as_str(),
        ),
        (
            "expected_decision_source_digest",
            contract.expected_decision_source_digest.as_str(),
        ),
        (
            "expected_session_epoch_digest",
            contract.expected_session_epoch_digest.as_str(),
        ),
        (
            "expected_resume_parent_digest",
            contract.expected_resume_parent_digest.as_str(),
        ),
        (
            "expected_adapter_build_digest",
            contract.expected_adapter_build_digest.as_str(),
        ),
        (
            "expected_adapter_capabilities_digest",
            contract.expected_adapter_capabilities_digest.as_str(),
        ),
        (
            "expected_evidence_digest",
            contract.expected_evidence_digest.as_str(),
        ),
    ] {
        ensure!(is_sha256_digest(value), "{name} has invalid digest shape");
    }
    Ok(())
}

fn validate_unique_nonempty(values: &[String], label: &str) -> anyhow::Result<()> {
    ensure!(!values.is_empty(), "{label} is empty");
    let mut unique = BTreeSet::new();
    for value in values {
        ensure!(
            !value.trim().is_empty() && unique.insert(value.as_str()),
            "{label} contains an empty or duplicate value"
        );
    }
    Ok(())
}

fn validate_sorted_unique(values: &[String], label: &str) -> anyhow::Result<()> {
    let sorted = values
        .iter()
        .cloned()
        .collect::<BTreeSet<_>>()
        .into_iter()
        .collect::<Vec<_>>();
    ensure!(sorted == values, "{label} must be sorted and unique");
    Ok(())
}

fn structural_reasons(claims: &Claims, contract: &Contract) -> BTreeSet<String> {
    let mut reasons = BTreeSet::new();
    for (name, value) in [
        ("claims_schema", claims.claims_schema.as_str()),
        ("envelope_version", claims.envelope_version.as_str()),
        ("receipt_id", claims.receipt_id.as_str()),
        ("issuer_id", claims.issuer_id.as_str()),
        ("principal_id", claims.principal_id.as_str()),
        ("action_class", claims.action_class.as_str()),
        ("target_digest", claims.target_digest.as_str()),
        ("scope_digest", claims.scope_digest.as_str()),
        (
            "decision_source_digest",
            claims.decision_source_digest.as_str(),
        ),
        ("session_epoch_digest", claims.session_epoch_digest.as_str()),
        ("resume_parent_digest", claims.resume_parent_digest.as_str()),
        ("adapter_id", claims.adapter_id.as_str()),
        ("adapter_build_digest", claims.adapter_build_digest.as_str()),
        (
            "adapter_capabilities_digest",
            claims.adapter_capabilities_digest.as_str(),
        ),
        ("nonce", claims.nonce.as_str()),
        ("evidence_digest", claims.evidence_digest.as_str()),
        ("verifier_id", claims.verifier_id.as_str()),
        ("policy_version", claims.policy_version.as_str()),
        ("key_id", claims.key_id.as_str()),
        ("algorithm", claims.algorithm.as_str()),
    ] {
        if value.trim().is_empty() {
            reasons.insert(format!("required_field_empty:{name}"));
        }
    }
    for (name, value) in [
        ("target_digest", claims.target_digest.as_str()),
        ("scope_digest", claims.scope_digest.as_str()),
        (
            "decision_source_digest",
            claims.decision_source_digest.as_str(),
        ),
        ("session_epoch_digest", claims.session_epoch_digest.as_str()),
        ("resume_parent_digest", claims.resume_parent_digest.as_str()),
        ("adapter_build_digest", claims.adapter_build_digest.as_str()),
        (
            "adapter_capabilities_digest",
            claims.adapter_capabilities_digest.as_str(),
        ),
        ("evidence_digest", claims.evidence_digest.as_str()),
    ] {
        if !value.is_empty() && !is_sha256_digest(value) {
            reasons.insert(format!("invalid_digest_shape:{name}"));
        }
    }
    if claims.claims_schema != contract.claims_schema {
        reasons.insert("claims_schema_not_accepted".to_string());
    }
    if claims.envelope_version != contract.accepted_envelope_version {
        reasons.insert("envelope_version_not_accepted".to_string());
    }
    if claims.verifier_id != contract.expected_verifier_id {
        reasons.insert("verifier_id_not_accepted".to_string());
    }
    if claims.policy_version != contract.accepted_policy_version {
        reasons.insert("policy_version_not_accepted".to_string());
    }
    if claims.expires_at_unix <= claims.issued_at_unix {
        reasons.insert("expires_not_after_issue".to_string());
    }
    reasons
}

fn is_sha256_digest(value: &str) -> bool {
    value.len() == 71
        && value.starts_with("sha256:")
        && value[7..]
            .bytes()
            .all(|byte| byte.is_ascii_digit() || (b'a'..=b'f').contains(&byte))
}

fn evaluate_case(
    registry: &TrustRegistry,
    corpus: &Corpus,
    case: &Case,
) -> anyhow::Result<CaseResult> {
    let claims = claims_for_case(corpus, case);
    let canonical_bytes = canonical_claims_bytes(&claims);
    let canonical_claims_sha256 = sha256(&canonical_bytes);
    let (derived_status, reasons, signature_outcome) =
        derive_case(registry, corpus, case, &claims, &canonical_bytes)?;

    Ok(CaseResult {
        id: case.id.clone(),
        control: case.control,
        receipt_id: claims.receipt_id,
        key_id: claims.key_id,
        canonical_claims_sha256,
        signature_outcome,
        derived_status,
        expected_status: case.expected_status,
        reasons: reasons.clone(),
        expected_reasons: case.expected_reasons.clone(),
        status_matches: derived_status == case.expected_status,
        reasons_match: reasons == case.expected_reasons,
        receipt_usable_for_later_owner_review: derived_status == VerificationStatus::Verified,
    })
}

fn derive_case(
    registry: &TrustRegistry,
    corpus: &Corpus,
    case: &Case,
    claims: &Claims,
    canonical_bytes: &[u8],
) -> anyhow::Result<(VerificationStatus, Vec<String>, SignatureOutcome)> {
    if !case.verifier_available {
        return Ok((
            VerificationStatus::Unavailable,
            vec!["independent_verifier_unavailable".to_string()],
            SignatureOutcome::NotAttempted,
        ));
    }

    let signature = match STANDARD.decode(&case.signature_base64) {
        Ok(signature) => signature,
        Err(_) => {
            return Ok((
                VerificationStatus::Invalid,
                vec!["signature_base64_invalid".to_string()],
                SignatureOutcome::NotAttempted,
            ));
        }
    };
    if signature.len() != 64 {
        return Ok((
            VerificationStatus::Invalid,
            vec!["signature_length_invalid".to_string()],
            SignatureOutcome::NotAttempted,
        ));
    }

    let structural = structural_reasons(claims, &corpus.contract);
    if !structural.is_empty() {
        return Ok((
            VerificationStatus::Invalid,
            structural.into_iter().collect(),
            SignatureOutcome::NotAttempted,
        ));
    }

    let Some(key) = registry.keys.iter().find(|key| key.key_id == claims.key_id) else {
        return Ok((
            VerificationStatus::Untrusted,
            vec!["key_id_not_trusted".to_string()],
            SignatureOutcome::NotAttempted,
        ));
    };

    let mut untrusted = BTreeSet::new();
    if !registry.algorithm_allowlist.contains(&claims.algorithm) {
        untrusted.insert("algorithm_not_allowed".to_string());
    }
    if claims.algorithm != key.algorithm {
        untrusted.insert("algorithm_key_mismatch".to_string());
    }
    if claims.issuer_id != key.allowed_issuer_id {
        untrusted.insert("issuer_not_authorized_by_key".to_string());
    }
    if claims.principal_id != key.allowed_principal_id {
        untrusted.insert("principal_not_authorized_by_key".to_string());
    }
    if claims.action_class != key.allowed_action_class {
        untrusted.insert("action_not_authorized_by_key".to_string());
    }
    if claims.policy_version != key.allowed_policy_version {
        untrusted.insert("policy_not_authorized_by_key".to_string());
    }
    if !untrusted.is_empty() {
        return Ok((
            VerificationStatus::Untrusted,
            untrusted.into_iter().collect(),
            SignatureOutcome::NotAttempted,
        ));
    }

    let public_key = STANDARD
        .decode(&key.public_key_base64)
        .with_context(|| format!("{} public key stopped decoding", key.key_id))?;
    if UnparsedPublicKey::new(&ED25519, public_key)
        .verify(canonical_bytes, &signature)
        .is_err()
    {
        return Ok((
            VerificationStatus::Invalid,
            vec!["signature_verification_failed".to_string()],
            SignatureOutcome::Failed,
        ));
    }

    let mut revoked = BTreeSet::new();
    if key.revoked {
        revoked.insert("signing_key_revoked".to_string());
    }
    if registry
        .read_only_snapshot
        .revoked_receipt_ids
        .contains(&claims.receipt_id)
    {
        revoked.insert("receipt_id_revoked".to_string());
    }
    if !revoked.is_empty() {
        return Ok((
            VerificationStatus::Revoked,
            revoked.into_iter().collect(),
            SignatureOutcome::Verified,
        ));
    }

    let latest = corpus
        .contract
        .evaluation_time_unix
        .saturating_add(corpus.contract.allowed_clock_skew_secs);
    let earliest = corpus
        .contract
        .evaluation_time_unix
        .saturating_sub(corpus.contract.allowed_clock_skew_secs);
    let mut stale = BTreeSet::new();
    if claims.issued_at_unix < key.not_before_unix {
        stale.insert("receipt_issued_before_key_validity".to_string());
    }
    if claims.issued_at_unix > key.not_after_unix {
        stale.insert("receipt_issued_after_key_validity".to_string());
    }
    if key.not_before_unix > latest {
        stale.insert("signing_key_not_yet_valid".to_string());
    }
    if key.not_after_unix < earliest {
        stale.insert("signing_key_expired".to_string());
    }
    if claims.issued_at_unix > latest {
        stale.insert("receipt_not_yet_valid".to_string());
    }
    if claims.expires_at_unix < earliest {
        stale.insert("receipt_expired".to_string());
    }
    if !stale.is_empty() {
        return Ok((
            VerificationStatus::Stale,
            stale.into_iter().collect(),
            SignatureOutcome::Verified,
        ));
    }

    if registry
        .read_only_snapshot
        .consumed_nonces
        .contains(&claims.nonce)
    {
        return Ok((
            VerificationStatus::Replayed,
            vec!["nonce_already_consumed".to_string()],
            SignatureOutcome::Verified,
        ));
    }

    let scope = scope_reasons(claims, &corpus.contract);
    if !scope.is_empty() {
        return Ok((
            VerificationStatus::OutOfScope,
            scope.into_iter().collect(),
            SignatureOutcome::Verified,
        ));
    }

    Ok((
        VerificationStatus::Verified,
        Vec::new(),
        SignatureOutcome::Verified,
    ))
}

fn scope_reasons(claims: &Claims, contract: &Contract) -> BTreeSet<String> {
    let mut reasons = BTreeSet::new();
    for (actual, expected, reason) in [
        (
            claims.action_class.as_str(),
            contract.expected_action_class.as_str(),
            "action_class_mismatch",
        ),
        (
            claims.target_digest.as_str(),
            contract.expected_target_digest.as_str(),
            "target_digest_mismatch",
        ),
        (
            claims.scope_digest.as_str(),
            contract.expected_scope_digest.as_str(),
            "scope_digest_mismatch",
        ),
        (
            claims.decision_source_digest.as_str(),
            contract.expected_decision_source_digest.as_str(),
            "decision_source_digest_mismatch",
        ),
        (
            claims.session_epoch_digest.as_str(),
            contract.expected_session_epoch_digest.as_str(),
            "session_epoch_digest_mismatch",
        ),
        (
            claims.resume_parent_digest.as_str(),
            contract.expected_resume_parent_digest.as_str(),
            "resume_parent_digest_mismatch",
        ),
        (
            claims.adapter_id.as_str(),
            contract.expected_adapter_id.as_str(),
            "adapter_id_mismatch",
        ),
        (
            claims.adapter_build_digest.as_str(),
            contract.expected_adapter_build_digest.as_str(),
            "adapter_build_digest_mismatch",
        ),
        (
            claims.adapter_capabilities_digest.as_str(),
            contract.expected_adapter_capabilities_digest.as_str(),
            "adapter_capabilities_digest_mismatch",
        ),
        (
            claims.evidence_digest.as_str(),
            contract.expected_evidence_digest.as_str(),
            "evidence_digest_mismatch",
        ),
    ] {
        if actual != expected {
            reasons.insert(reason.to_string());
        }
    }
    reasons
}

fn evaluate_suite(
    registry: &TrustRegistry,
    corpus: &Corpus,
    sources: &EmbeddedSources,
    registry_bytes: &[u8],
    corpus_bytes: &[u8],
) -> anyhow::Result<Report> {
    ensure!(
        sha256(registry_bytes) == TRUST_REGISTRY_SHA256,
        "trust registry differs from frozen hash"
    );
    ensure!(
        sha256(corpus_bytes) == SIGNED_RECEIPTS_SHA256,
        "signed receipt corpus differs from frozen hash"
    );
    validate_inputs(registry, corpus, sources)?;
    let results = corpus
        .cases
        .iter()
        .map(|case| evaluate_case(registry, corpus, case))
        .collect::<anyhow::Result<Vec<_>>>()?;

    let count = |status| {
        results
            .iter()
            .filter(|result| result.derived_status == status)
            .count()
    };
    let verified_count = count(VerificationStatus::Verified);
    let invalid_count = count(VerificationStatus::Invalid);
    let untrusted_count = count(VerificationStatus::Untrusted);
    let revoked_count = count(VerificationStatus::Revoked);
    let stale_count = count(VerificationStatus::Stale);
    let replayed_count = count(VerificationStatus::Replayed);
    let out_of_scope_count = count(VerificationStatus::OutOfScope);
    let unavailable_count = count(VerificationStatus::Unavailable);
    let signature_verification_attempt_count = results
        .iter()
        .filter(|result| result.signature_outcome != SignatureOutcome::NotAttempted)
        .count();
    let signature_verification_success_count = results
        .iter()
        .filter(|result| result.signature_outcome == SignatureOutcome::Verified)
        .count();
    let signature_verification_failure_count = results
        .iter()
        .filter(|result| result.signature_outcome == SignatureOutcome::Failed)
        .count();
    let false_accept_count = results
        .iter()
        .filter(|result| !result.control && result.derived_status == VerificationStatus::Verified)
        .count();
    let control_false_reject_count = results
        .iter()
        .filter(|result| result.control && result.derived_status != VerificationStatus::Verified)
        .count();
    let status_mismatch_count = results
        .iter()
        .filter(|result| !result.status_matches)
        .count();
    let reason_mismatch_count = results
        .iter()
        .filter(|result| !result.reasons_match)
        .count();
    let expected_distribution = verified_count == 4
        && invalid_count == 4
        && untrusted_count == 3
        && revoked_count == 2
        && stale_count == 4
        && replayed_count == 1
        && out_of_scope_count == 8
        && unavailable_count == 1;
    let expected_signature_counts = signature_verification_attempt_count == 21
        && signature_verification_success_count == 19
        && signature_verification_failure_count == 2;
    let passed = expected_distribution
        && expected_signature_counts
        && false_accept_count == 0
        && control_false_reject_count == 0
        && status_mismatch_count == 0
        && reason_mismatch_count == 0;
    let source_sha256 = corpus
        .source
        .files
        .iter()
        .map(|pin| (pin.path.clone(), pin.sha256.clone()))
        .collect();

    Ok(Report {
        schema: REPORT_SCHEMA,
        status: if passed {
            "pass_offline_signed_preflight_only"
        } else {
            "fail_closed"
        },
        latest_master_commit: LATEST_MASTER_COMMIT,
        s2_result_commit: S2_RESULT_COMMIT,
        s3_lineage_merge_commit: S3_LINEAGE_MERGE_COMMIT,
        trust_registry_sha256: sha256(registry_bytes),
        signed_receipts_sha256: sha256(corpus_bytes),
        source_sha256,
        crypto_verifier: "ring 0.17.14 Ed25519 verification only",
        public_test_keys_only: true,
        private_signing_material_embedded: false,
        replay_snapshot_mutated: false,
        runtime_consumer_enabled: false,
        case_count: results.len(),
        verified_count,
        invalid_count,
        untrusted_count,
        revoked_count,
        stale_count,
        replayed_count,
        out_of_scope_count,
        unavailable_count,
        signature_verification_attempt_count,
        signature_verification_success_count,
        signature_verification_failure_count,
        false_accept_count,
        control_false_reject_count,
        status_mismatch_count,
        reason_mismatch_count,
        authority: Authority::default(),
        results,
    })
}

fn sha256(bytes: &[u8]) -> String {
    format!("{:x}", Sha256::digest(bytes))
}

fn main() -> anyhow::Result<()> {
    let registry = load_registry(TRUST_REGISTRY_BYTES)?;
    let corpus = load_corpus(SIGNED_RECEIPTS_BYTES)?;
    let sources = embedded_sources(
        S2_DESIGN_BYTES,
        S2_FIXTURE_BYTES,
        S2_RESULT_BYTES,
        TRUST_REGISTRY_BYTES,
    );
    let report = evaluate_suite(
        &registry,
        &corpus,
        &sources,
        TRUST_REGISTRY_BYTES,
        SIGNED_RECEIPTS_BYTES,
    )?;
    println!("{}", serde_json::to_string_pretty(&report)?);
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    fn frozen_registry() -> TrustRegistry {
        load_registry(TRUST_REGISTRY_BYTES).expect("registry parses")
    }

    fn frozen_corpus() -> Corpus {
        load_corpus(SIGNED_RECEIPTS_BYTES).expect("corpus parses")
    }

    fn frozen_sources() -> EmbeddedSources {
        embedded_sources(
            S2_DESIGN_BYTES,
            S2_FIXTURE_BYTES,
            S2_RESULT_BYTES,
            TRUST_REGISTRY_BYTES,
        )
    }

    #[test]
    fn frozen_suite_matches_preregistered_distribution() {
        let report = evaluate_suite(
            &frozen_registry(),
            &frozen_corpus(),
            &frozen_sources(),
            TRUST_REGISTRY_BYTES,
            SIGNED_RECEIPTS_BYTES,
        )
        .expect("suite evaluates");

        assert_eq!(report.case_count, 27);
        assert_eq!(report.verified_count, 4);
        assert_eq!(report.invalid_count, 4);
        assert_eq!(report.untrusted_count, 3);
        assert_eq!(report.revoked_count, 2);
        assert_eq!(report.stale_count, 4);
        assert_eq!(report.replayed_count, 1);
        assert_eq!(report.out_of_scope_count, 8);
        assert_eq!(report.unavailable_count, 1);
        assert_eq!(report.status_mismatch_count, 0);
        assert_eq!(report.reason_mismatch_count, 0);
    }

    #[test]
    fn real_signature_path_and_adversarial_boundaries_are_exact() {
        let report = evaluate_suite(
            &frozen_registry(),
            &frozen_corpus(),
            &frozen_sources(),
            TRUST_REGISTRY_BYTES,
            SIGNED_RECEIPTS_BYTES,
        )
        .expect("suite evaluates");

        assert_eq!(report.signature_verification_attempt_count, 21);
        assert_eq!(report.signature_verification_success_count, 19);
        assert_eq!(report.signature_verification_failure_count, 2);
        assert_eq!(report.false_accept_count, 0);
        assert_eq!(report.control_false_reject_count, 0);
        assert!(report
            .results
            .iter()
            .filter(|result| result.control)
            .all(|result| {
                result.derived_status == VerificationStatus::Verified
                    && result.signature_outcome == SignatureOutcome::Verified
            }));

        for id in ["bit_flipped_signature_rejected", "payload_tamper_rejected"] {
            let result = report
                .results
                .iter()
                .find(|result| result.id == id)
                .expect("signature failure case exists");
            assert_eq!(result.derived_status, VerificationStatus::Invalid);
            assert_eq!(result.signature_outcome, SignatureOutcome::Failed);
            assert_eq!(result.reasons, vec!["signature_verification_failed"]);
        }
    }

    #[test]
    fn expected_labels_are_comparison_only() {
        let registry = frozen_registry();
        let corpus = frozen_corpus();
        let baseline =
            evaluate_case(&registry, &corpus, &corpus.cases[0]).expect("baseline evaluates");

        let mut relabeled = corpus;
        relabeled.cases[0].expected_status = VerificationStatus::Invalid;
        relabeled.cases[0].expected_reasons = vec!["invented_expected_reason".to_string()];
        let changed =
            evaluate_case(&registry, &relabeled, &relabeled.cases[0]).expect("case evaluates");
        let report = evaluate_suite(
            &registry,
            &relabeled,
            &frozen_sources(),
            TRUST_REGISTRY_BYTES,
            SIGNED_RECEIPTS_BYTES,
        )
        .expect("relabeled suite evaluates");

        assert_eq!(baseline.derived_status, VerificationStatus::Verified);
        assert_eq!(changed.derived_status, baseline.derived_status);
        assert_eq!(changed.reasons, baseline.reasons);
        assert_eq!(report.status_mismatch_count, 1);
        assert_eq!(report.reason_mismatch_count, 1);
    }

    #[test]
    fn malformed_registry_corpus_and_source_pins_fail_closed() {
        let registry = frozen_registry();
        let corpus = frozen_corpus();
        let sources = frozen_sources();

        let mut duplicate_key = registry.clone();
        duplicate_key.keys[1].key_id = duplicate_key.keys[0].key_id.clone();
        assert!(validate_inputs(&duplicate_key, &corpus, &sources).is_err());

        let mut invalid_key = registry.clone();
        invalid_key.keys[0].public_key_base64 = "not-base64".to_string();
        assert!(validate_inputs(&invalid_key, &corpus, &sources).is_err());

        let mut duplicate_case = corpus.clone();
        duplicate_case.cases[1].id = duplicate_case.cases[0].id.clone();
        assert!(validate_inputs(&registry, &duplicate_case, &sources).is_err());

        let mut duplicate_nonce = corpus.clone();
        duplicate_nonce.cases[1].claims_overrides.nonce =
            duplicate_nonce.cases[0].claims_overrides.nonce.clone();
        assert!(validate_inputs(&registry, &duplicate_nonce, &sources).is_err());

        let mut stale_source = corpus.clone();
        stale_source.source.files[0].sha256 = "0".repeat(64);
        assert!(validate_inputs(&registry, &stale_source, &sources).is_err());

        let mut unsorted_reasons = corpus;
        unsorted_reasons.cases[10].expected_reasons.reverse();
        assert!(validate_inputs(&registry, &unsorted_reasons, &sources).is_err());
    }

    #[test]
    fn all_twenty_two_signed_fields_change_canonical_bytes() {
        let baseline = frozen_corpus().baseline_claims;
        let baseline_bytes = canonical_claims_bytes(&baseline);
        let mut mutations = Vec::new();

        macro_rules! mutate_string {
            ($field:ident) => {{
                let mut claims = baseline.clone();
                claims.$field.push_str(":changed");
                mutations.push(claims);
            }};
        }
        macro_rules! mutate_digest {
            ($field:ident) => {{
                let mut claims = baseline.clone();
                claims.$field.replace_range(7..8, "a");
                mutations.push(claims);
            }};
        }

        mutate_string!(claims_schema);
        mutate_string!(envelope_version);
        mutate_string!(receipt_id);
        mutate_string!(issuer_id);
        mutate_string!(principal_id);
        mutate_string!(action_class);
        mutate_digest!(target_digest);
        mutate_digest!(scope_digest);
        mutate_digest!(decision_source_digest);
        mutate_digest!(session_epoch_digest);
        mutate_digest!(resume_parent_digest);
        mutate_string!(adapter_id);
        mutate_digest!(adapter_build_digest);
        mutate_digest!(adapter_capabilities_digest);
        let mut claims = baseline.clone();
        claims.issued_at_unix += 1;
        mutations.push(claims);
        let mut claims = baseline.clone();
        claims.expires_at_unix += 1;
        mutations.push(claims);
        mutate_string!(nonce);
        mutate_digest!(evidence_digest);
        mutate_string!(verifier_id);
        mutate_string!(policy_version);
        mutate_string!(key_id);
        mutate_string!(algorithm);

        assert_eq!(mutations.len(), 22);
        assert!(mutations
            .iter()
            .all(|claims| canonical_claims_bytes(claims) != baseline_bytes));
    }

    #[test]
    fn evaluation_does_not_mutate_registry_or_replay_snapshot() {
        let registry = frozen_registry();
        let corpus = frozen_corpus();
        let registry_before = registry.clone();
        let corpus_before = corpus.clone();

        evaluate_suite(
            &registry,
            &corpus,
            &frozen_sources(),
            TRUST_REGISTRY_BYTES,
            SIGNED_RECEIPTS_BYTES,
        )
        .expect("suite evaluates");

        assert_eq!(registry, registry_before);
        assert_eq!(corpus, corpus_before);
    }

    #[test]
    fn report_is_deterministic_and_non_authorizing() {
        let registry = frozen_registry();
        let corpus = frozen_corpus();
        let sources = frozen_sources();
        let first = evaluate_suite(
            &registry,
            &corpus,
            &sources,
            TRUST_REGISTRY_BYTES,
            SIGNED_RECEIPTS_BYTES,
        )
        .expect("first evaluation");
        let second = evaluate_suite(
            &registry,
            &corpus,
            &sources,
            TRUST_REGISTRY_BYTES,
            SIGNED_RECEIPTS_BYTES,
        )
        .expect("second evaluation");

        assert_eq!(first, second);
        assert_eq!(
            serde_json::to_vec_pretty(&first).expect("first serializes"),
            serde_json::to_vec_pretty(&second).expect("second serializes")
        );
        assert!(first.public_test_keys_only);
        assert!(!first.private_signing_material_embedded);
        assert!(!first.replay_snapshot_mutated);
        assert!(!first.runtime_consumer_enabled);
        assert!(first.results.iter().all(|result| {
            result.receipt_usable_for_later_owner_review
                == (result.derived_status == VerificationStatus::Verified)
        }));
        assert!(!first.authority.may_dispatch);
        assert!(!first.authority.may_run_shadow);
        assert!(!first.authority.may_enable_runtime);
        assert!(!first.authority.may_write_memory);
        assert!(!first.authority.may_write_graph);
        assert!(!first.authority.may_change_retrieval);
        assert!(!first.authority.may_change_session);
        assert!(!first.authority.may_persist_replay_state);
        assert!(!first.authority.production_trust_root_proven);
        assert!(!first.authority.production_authority_granted);
    }
}
