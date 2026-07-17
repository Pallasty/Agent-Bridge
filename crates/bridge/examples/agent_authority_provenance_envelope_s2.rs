//! Static S2 authority/provenance envelope contract and offline verifier.
//!
//! This example uses only embedded synthetic fixtures and inert S1 source
//! bytes. It does not authenticate a real principal, invoke MCP/T6, or grant
//! runtime authority.

use anyhow::{ensure, Context};
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use std::collections::{BTreeMap, BTreeSet};

const FIXTURE_BYTES: &[u8] =
    include_bytes!("../tests/fixtures/agent_authority_provenance_envelope_s2.json");
const S1_DESIGN_BYTES: &[u8] = include_bytes!(
    "../../../docs/design/CODEX_REDTEAM_MODE_T6_AGENT_COMPROMISE_MAPPING_S1_2026_07_16.md"
);
const S1_MAPPING_BYTES: &[u8] =
    include_bytes!("../tests/fixtures/agent_compromise_resilience_s1_mapping.json");
const S1_RESULT_BYTES: &[u8] = include_bytes!(
    "../../../docs/reports/goal-c-u/2026-07-16-agent-compromise-resilience-s1-result.md"
);

const FIXTURE_SCHEMA: &str = "agent_bridge.agent_authority_provenance_envelope.s2_fixture.v0";
const REPORT_SCHEMA: &str = "agent_bridge.agent_authority_provenance_envelope.s2_report.v0";
const CLAIMS_SCHEMA: &str = "agent_bridge.authority_provenance_claims.v0";
const ENVELOPE_VERSION: &str = "agent_bridge.authority_envelope.v0";
const POLICY_VERSION: &str = "ab.t6.authority_review.v0";
const T6_SOURCE_COMMIT: &str = "a1c9469e9a14cd73159d34974f0e99714ce5a1f0";
const S1_RESULT_COMMIT: &str = "232cadaced8ac1ab6e18907d451fba9208d03079";
const EVALUATION_TIME_UNIX: u64 = 1_784_259_000;
const ALLOWED_CLOCK_SKEW_SECS: u64 = 30;
const CANONICAL_DOMAIN: &[u8] = b"agent_bridge.authority_provenance_envelope.s2.claims.v0";

#[derive(Clone, Debug, Deserialize)]
#[serde(deny_unknown_fields)]
struct Fixture {
    schema: String,
    source: SourcePin,
    contract: Contract,
    baseline_claims: Claims,
    trusted_receipts: Vec<TrustedReceipt>,
    cases: Vec<Case>,
}

#[derive(Clone, Debug, Deserialize)]
#[serde(deny_unknown_fields)]
struct SourcePin {
    t6_source_commit: String,
    s1_result_commit: String,
    files: Vec<SourceFilePin>,
}

#[derive(Clone, Debug, Deserialize)]
#[serde(deny_unknown_fields)]
struct SourceFilePin {
    id: String,
    path: String,
    sha256: String,
}

#[derive(Clone, Debug, Deserialize)]
#[serde(deny_unknown_fields)]
struct Contract {
    claims_schema: String,
    accepted_envelope_version: String,
    accepted_policy_version: String,
    evaluation_time_unix: u64,
    allowed_clock_skew_secs: u64,
    trusted_issuers: Vec<String>,
    trusted_principals: Vec<String>,
    trusted_verifiers: Vec<String>,
    used_nonces: Vec<String>,
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
}

#[derive(Clone, Debug, Default, Deserialize)]
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
    }
}

#[derive(Clone, Debug, Deserialize)]
#[serde(deny_unknown_fields)]
struct TrustedReceipt {
    receipt_id: String,
    synthetic_attestation: String,
    claims_overrides: ClaimsPatch,
}

#[derive(Clone, Debug, Deserialize)]
#[serde(deny_unknown_fields)]
struct Case {
    id: String,
    control: bool,
    receipt_id: String,
    synthetic_attestation: String,
    claims_overrides: ClaimsPatch,
    verifier_available: bool,
    expected_status: VerificationStatus,
    expected_reasons: Vec<String>,
}

#[derive(Clone, Copy, Debug, Deserialize, Eq, Ord, PartialEq, PartialOrd, Serialize)]
#[serde(rename_all = "snake_case")]
enum VerificationStatus {
    Verified,
    Invalid,
    Stale,
    OutOfScope,
    Replayed,
    Unavailable,
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
    cryptographic_authenticity_proven: bool,
    production_authority_granted: bool,
}

#[derive(Clone, Debug, Eq, PartialEq, Serialize)]
struct CaseResult {
    id: String,
    control: bool,
    receipt_id: String,
    presented_claims_digest: String,
    trusted_claims_digest: Option<String>,
    derived_status: VerificationStatus,
    expected_status: VerificationStatus,
    reasons: Vec<String>,
    expected_reasons: Vec<String>,
    status_matches: bool,
    reasons_match: bool,
    receipt_usable_for_later_t6_review: bool,
}

#[derive(Clone, Debug, Eq, PartialEq, Serialize)]
struct Report {
    schema: &'static str,
    status: &'static str,
    t6_source_commit: &'static str,
    s1_result_commit: &'static str,
    fixture_sha256: String,
    source_sha256: BTreeMap<String, String>,
    case_count: usize,
    trusted_receipt_count: usize,
    verified_count: usize,
    invalid_count: usize,
    stale_count: usize,
    out_of_scope_count: usize,
    replayed_count: usize,
    unavailable_count: usize,
    false_accept_count: usize,
    control_false_reject_count: usize,
    status_mismatch_count: usize,
    reason_mismatch_count: usize,
    synthetic_attestation_only: bool,
    real_cryptographic_verifier_used: bool,
    live_runtime_checked: bool,
    authority: Authority,
    results: Vec<CaseResult>,
}

fn load_fixture(bytes: &[u8]) -> anyhow::Result<Fixture> {
    serde_json::from_slice(bytes).context("parse S2 authority/provenance fixture")
}

fn embedded_sources(
    s1_design: &'static [u8],
    s1_mapping: &'static [u8],
    s1_result: &'static [u8],
) -> EmbeddedSources {
    BTreeMap::from([
        (
            "s1_design",
            EmbeddedSource {
                path: "docs/design/CODEX_REDTEAM_MODE_T6_AGENT_COMPROMISE_MAPPING_S1_2026_07_16.md",
                bytes: s1_design,
            },
        ),
        (
            "s1_mapping",
            EmbeddedSource {
                path: "crates/bridge/tests/fixtures/agent_compromise_resilience_s1_mapping.json",
                bytes: s1_mapping,
            },
        ),
        (
            "s1_result",
            EmbeddedSource {
                path: "docs/reports/goal-c-u/2026-07-16-agent-compromise-resilience-s1-result.md",
                bytes: s1_result,
            },
        ),
    ])
}

fn claims_from_baseline(baseline: &Claims, receipt_id: &str, patch: &ClaimsPatch) -> Claims {
    let mut claims = baseline.clone();
    claims.receipt_id = receipt_id.to_string();
    patch.apply_to(&mut claims);
    claims
}

fn canonical_claims_digest(claims: &Claims) -> String {
    let mut bytes = Vec::with_capacity(2048);
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
    sha256(&bytes)
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

fn validate_fixture(fixture: &Fixture, sources: &EmbeddedSources) -> anyhow::Result<()> {
    ensure!(
        fixture.schema == FIXTURE_SCHEMA,
        "unexpected fixture schema"
    );
    ensure!(
        fixture.source.t6_source_commit == T6_SOURCE_COMMIT,
        "unexpected T6 source commit"
    );
    ensure!(
        fixture.source.s1_result_commit == S1_RESULT_COMMIT,
        "unexpected S1 result commit"
    );
    validate_source_pins(&fixture.source, sources)?;

    let contract = &fixture.contract;
    ensure!(
        contract.claims_schema == CLAIMS_SCHEMA,
        "unexpected claims schema"
    );
    ensure!(
        contract.accepted_envelope_version == ENVELOPE_VERSION,
        "unexpected envelope version"
    );
    ensure!(
        contract.accepted_policy_version == POLICY_VERSION,
        "unexpected policy version"
    );
    ensure!(
        contract.evaluation_time_unix == EVALUATION_TIME_UNIX,
        "unexpected evaluation time"
    );
    ensure!(
        contract.allowed_clock_skew_secs == ALLOWED_CLOCK_SKEW_SECS,
        "unexpected clock skew"
    );
    validate_unique_nonempty(&contract.trusted_issuers, "trusted issuers")?;
    validate_unique_nonempty(&contract.trusted_principals, "trusted principals")?;
    validate_unique_nonempty(&contract.trusted_verifiers, "trusted verifiers")?;
    validate_unique_nonempty(&contract.used_nonces, "used nonces")?;
    validate_contract_context(contract)?;

    let baseline_reasons = structural_reasons(&fixture.baseline_claims, contract);
    ensure!(
        baseline_reasons.is_empty(),
        "baseline claims are structurally invalid: {}",
        baseline_reasons.into_iter().collect::<Vec<_>>().join(",")
    );

    ensure!(
        fixture.trusted_receipts.len() == 22,
        "fixture must contain 22 trusted receipts"
    );
    let mut trusted_ids = BTreeSet::new();
    let mut attestations = BTreeSet::new();
    let mut trusted_nonces = BTreeSet::new();
    for receipt in &fixture.trusted_receipts {
        ensure!(
            !receipt.receipt_id.trim().is_empty()
                && trusted_ids.insert(receipt.receipt_id.as_str()),
            "duplicate or empty trusted receipt id {}",
            receipt.receipt_id
        );
        ensure!(
            !receipt.synthetic_attestation.trim().is_empty()
                && attestations.insert(receipt.synthetic_attestation.as_str()),
            "duplicate or empty synthetic attestation for {}",
            receipt.receipt_id
        );
        let claims = claims_from_baseline(
            &fixture.baseline_claims,
            &receipt.receipt_id,
            &receipt.claims_overrides,
        );
        ensure!(
            trusted_nonces.insert(claims.nonce.clone()),
            "duplicate trusted nonce {}",
            claims.nonce
        );
    }

    ensure!(fixture.cases.len() == 23, "fixture must contain 23 cases");
    let mut case_ids = BTreeSet::new();
    let mut case_receipt_ids = BTreeSet::new();
    let mut case_nonces = BTreeSet::new();
    let mut control_count = 0usize;
    let mut missing_trusted_receipt_count = 0usize;
    for case in &fixture.cases {
        ensure!(
            !case.id.trim().is_empty() && case_ids.insert(case.id.as_str()),
            "duplicate or empty case id {}",
            case.id
        );
        ensure!(
            !case.receipt_id.trim().is_empty() && case_receipt_ids.insert(case.receipt_id.as_str()),
            "duplicate or empty case receipt id {}",
            case.receipt_id
        );
        ensure!(
            !case.synthetic_attestation.trim().is_empty(),
            "{} has empty synthetic attestation",
            case.id
        );
        let claims = claims_from_baseline(
            &fixture.baseline_claims,
            &case.receipt_id,
            &case.claims_overrides,
        );
        ensure!(
            case_nonces.insert(claims.nonce.clone()),
            "duplicate case nonce {}",
            claims.nonce
        );
        validate_sorted_unique(&case.expected_reasons, &format!("{} reasons", case.id))?;
        control_count += usize::from(case.control);
        missing_trusted_receipt_count +=
            usize::from(!trusted_ids.contains(case.receipt_id.as_str()));
    }
    ensure!(control_count == 4, "fixture must contain four controls");
    ensure!(
        missing_trusted_receipt_count == 1,
        "fixture must contain one unknown-receipt case"
    );
    ensure!(
        trusted_ids
            .iter()
            .all(|receipt_id| case_receipt_ids.contains(receipt_id)),
        "every trusted receipt must be exercised by a case"
    );
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

fn validate_contract_context(contract: &Contract) -> anyhow::Result<()> {
    let plain_fields = [
        (
            "expected_action_class",
            contract.expected_action_class.as_str(),
        ),
        ("expected_adapter_id", contract.expected_adapter_id.as_str()),
    ];
    for (name, value) in plain_fields {
        ensure!(!value.trim().is_empty(), "{name} is empty");
    }
    let digests = [
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
    ];
    for (name, value) in digests {
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
    let required = [
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
    ];
    for (name, value) in required {
        if value.trim().is_empty() {
            reasons.insert(format!("required_field_empty:{name}"));
        }
    }

    let digests = [
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
    ];
    for (name, value) in digests {
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

fn evaluate_case(fixture: &Fixture, case: &Case) -> anyhow::Result<CaseResult> {
    let presented = claims_from_baseline(
        &fixture.baseline_claims,
        &case.receipt_id,
        &case.claims_overrides,
    );
    let presented_digest = canonical_claims_digest(&presented);
    let mut trusted_digest = None;

    let (derived_status, reasons) = if !case.verifier_available {
        (
            VerificationStatus::Unavailable,
            vec!["independent_verifier_unavailable".to_string()],
        )
    } else {
        let trusted = fixture
            .trusted_receipts
            .iter()
            .find(|receipt| receipt.receipt_id == case.receipt_id);
        match trusted {
            None => (
                VerificationStatus::Invalid,
                vec!["trusted_receipt_not_found".to_string()],
            ),
            Some(trusted) => {
                let trusted_claims = claims_from_baseline(
                    &fixture.baseline_claims,
                    &trusted.receipt_id,
                    &trusted.claims_overrides,
                );
                let digest = canonical_claims_digest(&trusted_claims);
                trusted_digest = Some(digest.clone());

                let mut invalid = structural_reasons(&presented, &fixture.contract);
                if case.synthetic_attestation != trusted.synthetic_attestation {
                    invalid.insert("synthetic_attestation_mismatch".to_string());
                }
                if presented_digest != digest {
                    invalid.insert("trusted_claims_digest_mismatch".to_string());
                }
                if !fixture
                    .contract
                    .trusted_issuers
                    .contains(&presented.issuer_id)
                {
                    invalid.insert("issuer_not_trusted".to_string());
                }
                if !fixture
                    .contract
                    .trusted_principals
                    .contains(&presented.principal_id)
                {
                    invalid.insert("principal_not_trusted".to_string());
                }
                if !fixture
                    .contract
                    .trusted_verifiers
                    .contains(&presented.verifier_id)
                {
                    invalid.insert("verifier_not_trusted".to_string());
                }
                if presented.policy_version != fixture.contract.accepted_policy_version {
                    invalid.insert("policy_version_not_accepted".to_string());
                }

                if !invalid.is_empty() {
                    (VerificationStatus::Invalid, invalid.into_iter().collect())
                } else {
                    let mut stale = BTreeSet::new();
                    let latest_issue = fixture
                        .contract
                        .evaluation_time_unix
                        .saturating_add(fixture.contract.allowed_clock_skew_secs);
                    let earliest_expiry = fixture
                        .contract
                        .evaluation_time_unix
                        .saturating_sub(fixture.contract.allowed_clock_skew_secs);
                    if presented.issued_at_unix > latest_issue {
                        stale.insert("receipt_not_yet_valid".to_string());
                    }
                    if presented.expires_at_unix < earliest_expiry {
                        stale.insert("receipt_expired".to_string());
                    }

                    if !stale.is_empty() {
                        (VerificationStatus::Stale, stale.into_iter().collect())
                    } else if fixture.contract.used_nonces.contains(&presented.nonce) {
                        (
                            VerificationStatus::Replayed,
                            vec!["nonce_already_consumed".to_string()],
                        )
                    } else {
                        let scope = scope_reasons(&presented, &fixture.contract);
                        if scope.is_empty() {
                            (VerificationStatus::Verified, Vec::new())
                        } else {
                            (VerificationStatus::OutOfScope, scope.into_iter().collect())
                        }
                    }
                }
            }
        }
    };

    Ok(CaseResult {
        id: case.id.clone(),
        control: case.control,
        receipt_id: case.receipt_id.clone(),
        presented_claims_digest: presented_digest,
        trusted_claims_digest: trusted_digest,
        derived_status,
        expected_status: case.expected_status,
        reasons: reasons.clone(),
        expected_reasons: case.expected_reasons.clone(),
        status_matches: derived_status == case.expected_status,
        reasons_match: reasons == case.expected_reasons,
        receipt_usable_for_later_t6_review: derived_status == VerificationStatus::Verified,
    })
}

fn scope_reasons(claims: &Claims, contract: &Contract) -> BTreeSet<String> {
    let mut reasons = BTreeSet::new();
    let comparisons = [
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
    ];
    for (actual, expected, reason) in comparisons {
        if actual != expected {
            reasons.insert(reason.to_string());
        }
    }
    reasons
}

fn evaluate_suite(
    fixture: &Fixture,
    sources: &EmbeddedSources,
    fixture_bytes: &[u8],
) -> anyhow::Result<Report> {
    validate_fixture(fixture, sources)?;
    let results = fixture
        .cases
        .iter()
        .map(|case| evaluate_case(fixture, case))
        .collect::<anyhow::Result<Vec<_>>>()?;

    let count = |status| {
        results
            .iter()
            .filter(|result| result.derived_status == status)
            .count()
    };
    let verified_count = count(VerificationStatus::Verified);
    let invalid_count = count(VerificationStatus::Invalid);
    let stale_count = count(VerificationStatus::Stale);
    let out_of_scope_count = count(VerificationStatus::OutOfScope);
    let replayed_count = count(VerificationStatus::Replayed);
    let unavailable_count = count(VerificationStatus::Unavailable);
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
        && invalid_count == 7
        && stale_count == 2
        && out_of_scope_count == 8
        && replayed_count == 1
        && unavailable_count == 1;
    let passed = expected_distribution
        && false_accept_count == 0
        && control_false_reject_count == 0
        && status_mismatch_count == 0
        && reason_mismatch_count == 0;
    let source_sha256 = fixture
        .source
        .files
        .iter()
        .map(|pin| (pin.path.clone(), pin.sha256.clone()))
        .collect();

    Ok(Report {
        schema: REPORT_SCHEMA,
        status: if passed {
            "pass_static_contract_only"
        } else {
            "fail_closed"
        },
        t6_source_commit: T6_SOURCE_COMMIT,
        s1_result_commit: S1_RESULT_COMMIT,
        fixture_sha256: sha256(fixture_bytes),
        source_sha256,
        case_count: results.len(),
        trusted_receipt_count: fixture.trusted_receipts.len(),
        verified_count,
        invalid_count,
        stale_count,
        out_of_scope_count,
        replayed_count,
        unavailable_count,
        false_accept_count,
        control_false_reject_count,
        status_mismatch_count,
        reason_mismatch_count,
        synthetic_attestation_only: true,
        real_cryptographic_verifier_used: false,
        live_runtime_checked: false,
        authority: Authority::default(),
        results,
    })
}

fn sha256(bytes: &[u8]) -> String {
    format!("{:x}", Sha256::digest(bytes))
}

fn main() -> anyhow::Result<()> {
    let fixture = load_fixture(FIXTURE_BYTES)?;
    let sources = embedded_sources(S1_DESIGN_BYTES, S1_MAPPING_BYTES, S1_RESULT_BYTES);
    let report = evaluate_suite(&fixture, &sources, FIXTURE_BYTES)?;
    println!("{}", serde_json::to_string_pretty(&report)?);
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    fn frozen_fixture() -> Fixture {
        load_fixture(FIXTURE_BYTES).expect("fixture parses")
    }

    fn frozen_sources() -> EmbeddedSources {
        embedded_sources(S1_DESIGN_BYTES, S1_MAPPING_BYTES, S1_RESULT_BYTES)
    }

    #[test]
    fn frozen_suite_matches_preregistered_distribution() {
        let fixture = frozen_fixture();
        let report =
            evaluate_suite(&fixture, &frozen_sources(), FIXTURE_BYTES).expect("suite evaluates");

        assert_eq!(report.case_count, 23);
        assert_eq!(report.verified_count, 4);
        assert_eq!(report.invalid_count, 7);
        assert_eq!(report.stale_count, 2);
        assert_eq!(report.replayed_count, 1);
        assert_eq!(report.out_of_scope_count, 8);
        assert_eq!(report.unavailable_count, 1);
        assert_eq!(report.status_mismatch_count, 0);
        assert_eq!(report.reason_mismatch_count, 0);
    }

    #[test]
    fn controls_pass_and_every_adversarial_case_fails_closed() {
        let fixture = frozen_fixture();
        let report =
            evaluate_suite(&fixture, &frozen_sources(), FIXTURE_BYTES).expect("suite evaluates");

        assert_eq!(report.false_accept_count, 0);
        assert_eq!(report.control_false_reject_count, 0);
        assert!(report
            .results
            .iter()
            .filter(|result| result.control)
            .all(|result| result.derived_status == VerificationStatus::Verified));
        assert!(report
            .results
            .iter()
            .filter(|result| !result.control)
            .all(|result| result.derived_status != VerificationStatus::Verified));
    }

    #[test]
    fn expected_labels_are_comparison_data_not_classifier_input() {
        let fixture = frozen_fixture();
        let baseline = evaluate_case(&fixture, &fixture.cases[0]).expect("baseline evaluates");

        let mut relabeled = fixture.clone();
        relabeled.cases[0].expected_status = VerificationStatus::Invalid;
        relabeled.cases[0].expected_reasons = vec!["invented_expected_reason".to_string()];
        let relabeled_case =
            evaluate_case(&relabeled, &relabeled.cases[0]).expect("relabeled case evaluates");
        let report = evaluate_suite(&relabeled, &frozen_sources(), FIXTURE_BYTES)
            .expect("relabeled suite evaluates");

        assert_eq!(baseline.derived_status, VerificationStatus::Verified);
        assert_eq!(relabeled_case.derived_status, baseline.derived_status);
        assert_eq!(relabeled_case.reasons, baseline.reasons);
        assert_eq!(report.status_mismatch_count, 1);
        assert_eq!(report.reason_mismatch_count, 1);
    }

    #[test]
    fn malformed_fixture_identity_and_source_pins_fail_closed() {
        let fixture = frozen_fixture();
        let sources = frozen_sources();

        let mut duplicate_case = fixture.clone();
        duplicate_case.cases[1].id = duplicate_case.cases[0].id.clone();
        assert!(validate_fixture(&duplicate_case, &sources).is_err());

        let mut duplicate_receipt = fixture.clone();
        duplicate_receipt.trusted_receipts[1].receipt_id =
            duplicate_receipt.trusted_receipts[0].receipt_id.clone();
        assert!(validate_fixture(&duplicate_receipt, &sources).is_err());

        let mut stale_source = fixture;
        stale_source.source.files[0].sha256 = "0".repeat(64);
        assert!(validate_fixture(&stale_source, &sources).is_err());
    }

    #[test]
    fn every_claim_field_participates_in_the_canonical_digest() {
        let fixture = frozen_fixture();
        let baseline = fixture.baseline_claims;
        let baseline_digest = canonical_claims_digest(&baseline);

        let mut mutations = Vec::new();
        let mut claims = baseline.clone();
        claims.claims_schema.push_str(":changed");
        mutations.push(claims);
        let mut claims = baseline.clone();
        claims.envelope_version.push_str(":changed");
        mutations.push(claims);
        let mut claims = baseline.clone();
        claims.receipt_id.push_str(":changed");
        mutations.push(claims);
        let mut claims = baseline.clone();
        claims.issuer_id.push_str(":changed");
        mutations.push(claims);
        let mut claims = baseline.clone();
        claims.principal_id.push_str(":changed");
        mutations.push(claims);
        let mut claims = baseline.clone();
        claims.action_class.push_str(":changed");
        mutations.push(claims);
        let mut claims = baseline.clone();
        claims.target_digest.replace_range(7..8, "a");
        mutations.push(claims);
        let mut claims = baseline.clone();
        claims.scope_digest.replace_range(7..8, "a");
        mutations.push(claims);
        let mut claims = baseline.clone();
        claims.decision_source_digest.replace_range(7..8, "a");
        mutations.push(claims);
        let mut claims = baseline.clone();
        claims.session_epoch_digest.replace_range(7..8, "a");
        mutations.push(claims);
        let mut claims = baseline.clone();
        claims.resume_parent_digest.replace_range(7..8, "a");
        mutations.push(claims);
        let mut claims = baseline.clone();
        claims.adapter_id.push_str(":changed");
        mutations.push(claims);
        let mut claims = baseline.clone();
        claims.adapter_build_digest.replace_range(7..8, "a");
        mutations.push(claims);
        let mut claims = baseline.clone();
        claims.adapter_capabilities_digest.replace_range(7..8, "a");
        mutations.push(claims);
        let mut claims = baseline.clone();
        claims.issued_at_unix += 1;
        mutations.push(claims);
        let mut claims = baseline.clone();
        claims.expires_at_unix += 1;
        mutations.push(claims);
        let mut claims = baseline.clone();
        claims.nonce.push_str(":changed");
        mutations.push(claims);
        let mut claims = baseline.clone();
        claims.evidence_digest.replace_range(7..8, "a");
        mutations.push(claims);
        let mut claims = baseline.clone();
        claims.verifier_id.push_str(":changed");
        mutations.push(claims);
        let mut claims = baseline;
        claims.policy_version.push_str(":changed");
        mutations.push(claims);

        assert_eq!(mutations.len(), 20);
        assert!(mutations
            .iter()
            .all(|claims| canonical_claims_digest(claims) != baseline_digest));
    }

    #[test]
    fn report_is_deterministic_and_explicitly_non_authorizing() {
        let fixture = frozen_fixture();
        let sources = frozen_sources();
        let first = evaluate_suite(&fixture, &sources, FIXTURE_BYTES).expect("first evaluation");
        let second = evaluate_suite(&fixture, &sources, FIXTURE_BYTES).expect("second evaluation");
        let first_bytes = serde_json::to_vec_pretty(&first).expect("first serializes");
        let second_bytes = serde_json::to_vec_pretty(&second).expect("second serializes");

        assert_eq!(first, second);
        assert_eq!(first_bytes, second_bytes);
        assert!(!first.authority.may_dispatch);
        assert!(!first.authority.may_run_shadow);
        assert!(!first.authority.may_enable_runtime);
        assert!(!first.authority.may_write_memory);
        assert!(!first.authority.may_write_graph);
        assert!(!first.authority.may_change_retrieval);
        assert!(!first.authority.may_change_session);
        assert!(!first.authority.cryptographic_authenticity_proven);
        assert!(!first.authority.production_authority_granted);
    }
}
