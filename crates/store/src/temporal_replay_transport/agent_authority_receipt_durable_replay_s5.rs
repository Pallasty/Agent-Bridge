//! S5 test-only composition of exact S3 authority receipts with S7 replay.
//!
//! This module is registered only under `cfg(test)` plus an explicit synthetic
//! feature. It must never expose a runtime constructor or persistent path.

use super::durable_replay_registry::{
    open_for_test, open_with_result_loss_for_test, provision_and_open_for_test,
};
use super::{
    agent_authority_signed_trust_root_s3_adapter::{evaluate_frozen_cases, EvaluatedS3Case},
    CandidateReplayRegistryV1, ReplayConsumeReceiptV1, ReplayConsumeRequestV1, VerifierResult,
};
use anyhow::{bail, ensure, Context};
use serde::Deserialize;
use sha2::{Digest, Sha256};
use std::collections::{BTreeMap, BTreeSet};
use std::path::{Path, PathBuf};
use std::process::{Command, Stdio};
use std::time::Duration;

const GENERATION: [u8; 32] = [0xA5; 32];
const FIXTURE_SHA256: &str = "d9b091c93fb1606f55cf78f450785f87ea81c8c0fd8737fcf27252b565c65d3e";
const FIXTURE_SCHEMA: &str = "agent_bridge.agent_authority_receipt_durable_replay_s5_fixture.v0";
const TRANSACTION_IDENTITY_DOMAIN: &str =
    "agent_bridge.agent_authority.s5.receipt_transaction_identity.v0";
const SCOPE_COMMITMENT_DOMAIN: &str = "agent_bridge.agent_authority.s5.signed_scope_commitment.v0";
const LATEST_MASTER_COMMIT: &str = "0b95c231b4ac61743c297b45b0abf81690bd3fd6";
const S4_RESULT_COMMIT: &str = "17d106f21d4540b81c609eaaf8fca7ce9462faf6";
const S5_LINEAGE_MERGE_COMMIT: &str = "5335bab516dccd6706094ecd96544e2c19463b4d";
const S7_IMPLEMENTATION_COMMIT: &str = "21d16c64c00ca1ba66b6833cc018e2796e76b5ef";
const HELPER_DB_ENV: &str = "AB_AGENT_AUTHORITY_S5_HELPER_DB";
const PRECOMMIT_HELPER_ENV: &str = "AB_AGENT_AUTHORITY_S5_PRECOMMIT_HELPER";
const POSTCOMMIT_HELPER_ENV: &str = "AB_AGENT_AUTHORITY_S5_POSTCOMMIT_HELPER";
const PRIMARY_CASE: &str = "verified_primary_control";
const SECONDARY_CASE: &str = "verified_secondary_control";

const FIXTURE_BYTES: &[u8] = include_bytes!(
    "../../../../scripts/eval/fixtures/agent_authority_receipt_durable_replay_s5.expected.v0.json"
);
const S3_VERIFIER_BYTES: &[u8] =
    include_bytes!("../../../bridge/examples/agent_authority_signed_trust_root_s3.rs");
const S3_VERIFIER_ADAPTER_BYTES: &[u8] =
    include_bytes!("../../../bridge/examples/agent_authority_signed_trust_root_s3.rs.inc");
const S3_TRUST_REGISTRY_BYTES: &[u8] =
    include_bytes!("../../../bridge/tests/fixtures/agent_authority_trust_registry_s3.json");
const S3_SIGNED_RECEIPTS_BYTES: &[u8] =
    include_bytes!("../../../bridge/tests/fixtures/agent_authority_signed_receipts_s3.json");
const S4_REPLAY_SCHEDULES_BYTES: &[u8] = include_bytes!(
    "../../../bridge/tests/fixtures/agent_authority_atomic_replay_schedules_s4.json"
);
const S7_REGISTRY_SOURCE_BYTES: &[u8] = include_bytes!("durable_replay_registry.rs");
const S7_DESIGN_BYTES: &[u8] =
    include_bytes!("../../../../docs/design/MEMORY_TEMPORAL_DURABLE_REPLAY_S7_2026_07_14.md");

const SCOPE_FIELD_ORDER: [&str; 18] = [
    "claims_schema",
    "envelope_version",
    "issuer_id",
    "principal_id",
    "action_class",
    "target_digest",
    "scope_digest",
    "decision_source_digest",
    "session_epoch_digest",
    "resume_parent_digest",
    "adapter_id",
    "adapter_build_digest",
    "adapter_capabilities_digest",
    "evidence_digest",
    "verifier_id",
    "policy_version",
    "key_id",
    "algorithm",
];

#[derive(Debug, Deserialize)]
#[serde(deny_unknown_fields)]
struct S5Fixture {
    schema: String,
    source: SourcePins,
    contract: Contract,
    scope_field_order: Vec<String>,
    cases: Vec<ExpectedCase>,
    fault_expectations: Vec<FaultExpectation>,
    authority: Authority,
}

#[derive(Debug, Deserialize)]
#[serde(deny_unknown_fields)]
struct SourcePins {
    latest_master_commit: String,
    s4_result_commit: String,
    s5_lineage_merge_commit: String,
    s7_implementation_commit: String,
    s3_verifier_sha256: String,
    s3_trust_registry_sha256: String,
    s3_signed_receipts_sha256: String,
    s4_replay_schedules_sha256: String,
    s7_registry_source_sha256: String,
    s7_design_sha256: String,
}

#[derive(Debug, Deserialize)]
#[serde(deny_unknown_fields)]
struct Contract {
    transaction_identity_domain: String,
    scope_commitment_domain: String,
    framing: String,
    payload_commitment: String,
    consume_time_unix: u64,
    eligible_s3_case_ids: Vec<String>,
    s3_case_count: usize,
    s3_verified_case_count: usize,
    s4_referenced_verified_case_count: usize,
    composition_eligible_case_count: usize,
    s4_reviewable_step_count: usize,
    s4_end_to_end_identity_match_count: usize,
    s4_end_to_end_identity_mismatch_count: usize,
    s3_expected_labels_are_authority: bool,
    caller_supplied_transaction_identity_accepted: bool,
    caller_supplied_receipt_identity_accepted: bool,
    caller_supplied_nonce_accepted: bool,
    test_only: bool,
    default_off: bool,
    temporary_store_only: bool,
    live_state_db_allowed: bool,
    runtime_consumer_enabled: bool,
    production_authority_granted: bool,
}

#[derive(Debug, Deserialize)]
#[serde(deny_unknown_fields)]
struct ExpectedCase {
    case_id: String,
    receipt_id: String,
    nonce: String,
    consumed_at_unix: u64,
    expires_at_unix: u64,
    transaction_identity_sha256: String,
    scope_commitment_sha256: String,
    payload_sha256: String,
}

#[derive(Debug, Deserialize)]
#[serde(deny_unknown_fields)]
struct FaultExpectation {
    id: String,
    expected: String,
}

#[derive(Debug, Deserialize)]
#[serde(deny_unknown_fields)]
struct Authority {
    may_dispatch: bool,
    may_run_shadow: bool,
    may_enable_runtime: bool,
    may_run_executor: bool,
    may_write_memory: bool,
    may_write_graph: bool,
    may_change_retrieval: bool,
    may_change_session: bool,
    may_open_live_state_db: bool,
    may_create_production_replay_registry: bool,
    production_trust_root_proven: bool,
    production_atomicity_proven: bool,
    production_crash_durability_proven: bool,
    production_authority_granted: bool,
}

impl Authority {
    fn all_false(&self) -> bool {
        !self.may_dispatch
            && !self.may_run_shadow
            && !self.may_enable_runtime
            && !self.may_run_executor
            && !self.may_write_memory
            && !self.may_write_graph
            && !self.may_change_retrieval
            && !self.may_change_session
            && !self.may_open_live_state_db
            && !self.may_create_production_replay_registry
            && !self.production_trust_root_proven
            && !self.production_atomicity_proven
            && !self.production_crash_durability_proven
            && !self.production_authority_granted
    }
}

struct ComposedReceipt {
    receipt_id: String,
    nonce: String,
    consumed_at_unix: u64,
    expires_at_unix: u64,
    transaction_identity_sha256: [u8; 32],
    scope_commitment_sha256: [u8; 32],
    payload_sha256: [u8; 32],
}

impl ComposedReceipt {
    fn request(&self) -> ReplayConsumeRequestV1 {
        ReplayConsumeRequestV1 {
            consumed_at_utc: i64::try_from(self.consumed_at_unix)
                .expect("frozen S5 consume time fits i64"),
            expires_at_utc: i64::try_from(self.expires_at_unix).expect("frozen S5 expiry fits i64"),
            payload_sha256: self.payload_sha256,
            replay_key_sha256: self.transaction_identity_sha256,
            scope_sha256: self.scope_commitment_sha256,
        }
    }
}

struct CompositionOutcome {
    composed: bool,
    reason: &'static str,
}

struct S4IdentityAudit {
    reviewable_step_count: usize,
    exact_identity_match_count: usize,
    exact_identity_mismatch_count: usize,
}

#[derive(Deserialize)]
struct S4Schedules {
    schedules: Vec<S4Schedule>,
}

#[derive(Deserialize)]
struct S4Schedule {
    expected_outcomes: Vec<String>,
    steps: Vec<S4Step>,
}

#[derive(Deserialize)]
struct S4Step {
    receipt_id: String,
    nonce: String,
    s3_case_id: String,
}

fn sha256(bytes: &[u8]) -> [u8; 32] {
    Sha256::digest(bytes).into()
}

fn hex(bytes: &[u8]) -> String {
    let mut output = String::with_capacity(bytes.len() * 2);
    for byte in bytes {
        use std::fmt::Write as _;
        write!(&mut output, "{byte:02x}").expect("write to String");
    }
    output
}

fn ensure_hash(label: &str, bytes: &[u8], expected: &str) -> anyhow::Result<()> {
    ensure!(
        hex(&sha256(bytes)) == expected,
        "{label} differs from its frozen SHA-256"
    );
    Ok(())
}

fn ensure_s3_adapter_mirrors_frozen_source() -> anyhow::Result<()> {
    let mut remainder = S3_VERIFIER_ADAPTER_BYTES;
    let mut normalized = Vec::with_capacity(S3_VERIFIER_ADAPTER_BYTES.len() + 4);
    for _ in 0..4 {
        let end = remainder
            .iter()
            .position(|byte| *byte == b'\n')
            .context("S3 adapter header line has no terminator")?
            + 1;
        let line = &remainder[..end];
        ensure!(
            line.starts_with(b"//") && !line.starts_with(b"//!"),
            "S3 adapter header is not the expected doc-comment projection"
        );
        normalized.extend_from_slice(b"//!");
        normalized.extend_from_slice(&line[2..]);
        remainder = &remainder[end..];
    }
    normalized.extend_from_slice(remainder);
    ensure!(
        normalized == S3_VERIFIER_BYTES,
        "S3 adapter executable source differs from the frozen verifier"
    );
    Ok(())
}

fn frozen_fixture() -> anyhow::Result<S5Fixture> {
    ensure_hash("S5 fixture", FIXTURE_BYTES, FIXTURE_SHA256)?;
    ensure_s3_adapter_mirrors_frozen_source()?;
    let fixture: S5Fixture =
        serde_json::from_slice(FIXTURE_BYTES).context("parse frozen S5 fixture")?;
    ensure!(
        fixture.schema == FIXTURE_SCHEMA,
        "unexpected S5 fixture schema"
    );
    ensure!(
        fixture.source.latest_master_commit == LATEST_MASTER_COMMIT,
        "latest-master source pin changed"
    );
    ensure!(
        fixture.source.s4_result_commit == S4_RESULT_COMMIT,
        "S4 result source pin changed"
    );
    ensure!(
        fixture.source.s5_lineage_merge_commit == S5_LINEAGE_MERGE_COMMIT,
        "S5 lineage source pin changed"
    );
    ensure!(
        fixture.source.s7_implementation_commit == S7_IMPLEMENTATION_COMMIT,
        "S7 implementation source pin changed"
    );
    for (label, bytes, expected) in [
        (
            "S3 verifier",
            S3_VERIFIER_BYTES,
            fixture.source.s3_verifier_sha256.as_str(),
        ),
        (
            "S3 trust registry",
            S3_TRUST_REGISTRY_BYTES,
            fixture.source.s3_trust_registry_sha256.as_str(),
        ),
        (
            "S3 signed receipts",
            S3_SIGNED_RECEIPTS_BYTES,
            fixture.source.s3_signed_receipts_sha256.as_str(),
        ),
        (
            "S4 replay schedules",
            S4_REPLAY_SCHEDULES_BYTES,
            fixture.source.s4_replay_schedules_sha256.as_str(),
        ),
        (
            "S7 registry source",
            S7_REGISTRY_SOURCE_BYTES,
            fixture.source.s7_registry_source_sha256.as_str(),
        ),
        (
            "S7 design",
            S7_DESIGN_BYTES,
            fixture.source.s7_design_sha256.as_str(),
        ),
    ] {
        ensure_hash(label, bytes, expected)?;
    }
    ensure!(
        fixture.contract.transaction_identity_domain == TRANSACTION_IDENTITY_DOMAIN
            && fixture.contract.scope_commitment_domain == SCOPE_COMMITMENT_DOMAIN,
        "S5 commitment domains changed"
    );
    ensure!(
        fixture.contract.framing == "u64be_length_prefixed_domain_then_ordered_utf8_parts"
            && fixture.contract.payload_commitment == "sha256_of_exact_s3_canonical_claims_bytes",
        "S5 commitment profile changed"
    );
    ensure!(
        fixture.contract.eligible_s3_case_ids == [PRIMARY_CASE, SECONDARY_CASE],
        "S5 eligibility allowlist changed"
    );
    ensure!(
        fixture.scope_field_order
            == SCOPE_FIELD_ORDER
                .iter()
                .map(|field| (*field).to_string())
                .collect::<Vec<_>>(),
        "S5 scope field order changed"
    );
    ensure!(
        !fixture.contract.s3_expected_labels_are_authority
            && !fixture
                .contract
                .caller_supplied_transaction_identity_accepted
            && !fixture.contract.caller_supplied_receipt_identity_accepted
            && !fixture.contract.caller_supplied_nonce_accepted
            && fixture.contract.test_only
            && fixture.contract.default_off
            && fixture.contract.temporary_store_only
            && !fixture.contract.live_state_db_allowed
            && !fixture.contract.runtime_consumer_enabled
            && !fixture.contract.production_authority_granted
            && fixture.authority.all_false(),
        "S5 authority boundary changed"
    );
    let case_ids = fixture
        .cases
        .iter()
        .map(|case| case.case_id.as_str())
        .collect::<BTreeSet<_>>();
    ensure!(
        case_ids == BTreeSet::from([PRIMARY_CASE, SECONDARY_CASE])
            && case_ids.len() == fixture.cases.len(),
        "S5 expected case identities changed or duplicate"
    );
    let fault_ids = fixture
        .fault_expectations
        .iter()
        .map(|fault| fault.id.as_str())
        .collect::<BTreeSet<_>>();
    ensure!(
        fault_ids.len() == fixture.fault_expectations.len(),
        "S5 fault expectation ids are duplicated"
    );
    ensure!(
        fixture
            .fault_expectations
            .iter()
            .all(|fault| !fault.expected.trim().is_empty()),
        "S5 fault expectation is empty"
    );
    Ok(fixture)
}

fn framed_sha256(domain: &str, parts: &[&str]) -> [u8; 32] {
    let mut bytes = Vec::new();
    bytes.extend_from_slice(&(domain.len() as u64).to_be_bytes());
    bytes.extend_from_slice(domain.as_bytes());
    for part in parts {
        bytes.extend_from_slice(&(part.len() as u64).to_be_bytes());
        bytes.extend_from_slice(part.as_bytes());
    }
    sha256(&bytes)
}

fn compose_evaluated(
    fixture: &S5Fixture,
    evaluated: &EvaluatedS3Case,
) -> anyhow::Result<ComposedReceipt> {
    if !evaluated.derived_verified || !evaluated.signature_verified || !evaluated.reasons.is_empty()
    {
        bail!("s5_receipt_not_verified");
    }
    if !fixture
        .contract
        .eligible_s3_case_ids
        .iter()
        .any(|case_id| case_id == &evaluated.case_id)
    {
        bail!("s5_receipt_not_allowlisted");
    }
    let expected = fixture
        .cases
        .iter()
        .find(|expected| expected.case_id == evaluated.case_id)
        .with_context(|| format!("{} has no S5 expected commitment", evaluated.case_id))?;
    let consumed_at_unix = fixture.contract.consume_time_unix;
    ensure!(
        evaluated.issued_at_unix <= consumed_at_unix
            && consumed_at_unix < evaluated.expires_at_unix,
        "s5_receipt_outside_strict_consume_window"
    );
    ensure!(
        expected.receipt_id == evaluated.receipt_id
            && expected.nonce == evaluated.nonce
            && expected.consumed_at_unix == consumed_at_unix
            && expected.expires_at_unix == evaluated.expires_at_unix,
        "{} typed identity differs from the frozen expectation",
        evaluated.case_id
    );

    let transaction_identity_sha256 = framed_sha256(
        &fixture.contract.transaction_identity_domain,
        &[&evaluated.receipt_id, &evaluated.nonce],
    );
    let scope_parts = evaluated
        .scope_fields
        .iter()
        .map(String::as_str)
        .collect::<Vec<_>>();
    let scope_commitment_sha256 =
        framed_sha256(&fixture.contract.scope_commitment_domain, &scope_parts);
    let payload_sha256 = sha256(&evaluated.canonical_claims_bytes);
    ensure!(
        hex(&transaction_identity_sha256) == expected.transaction_identity_sha256
            && hex(&scope_commitment_sha256) == expected.scope_commitment_sha256
            && hex(&payload_sha256) == expected.payload_sha256,
        "{} derived commitment differs from the frozen expectation",
        evaluated.case_id
    );

    Ok(ComposedReceipt {
        receipt_id: evaluated.receipt_id.clone(),
        nonce: evaluated.nonce.clone(),
        consumed_at_unix,
        expires_at_unix: evaluated.expires_at_unix,
        transaction_identity_sha256,
        scope_commitment_sha256,
        payload_sha256,
    })
}

fn compose_case(fixture: &S5Fixture, case_id: &str) -> anyhow::Result<ComposedReceipt> {
    let cases = evaluate_frozen_cases().context("run frozen S3 verifier")?;
    let evaluated = cases
        .iter()
        .find(|case| case.case_id == case_id)
        .with_context(|| format!("unknown S3 case {case_id}"))?;
    compose_evaluated(fixture, evaluated)
}

fn composition_outcomes_for_all_s3_cases(
    fixture: &S5Fixture,
) -> anyhow::Result<Vec<CompositionOutcome>> {
    let cases = evaluate_frozen_cases().context("run frozen S3 verifier")?;
    cases
        .iter()
        .map(|evaluated| {
            if !evaluated.derived_verified
                || !evaluated.signature_verified
                || !evaluated.reasons.is_empty()
            {
                return Ok(CompositionOutcome {
                    composed: false,
                    reason: "s5_receipt_not_verified",
                });
            }
            if !fixture
                .contract
                .eligible_s3_case_ids
                .iter()
                .any(|case_id| case_id == &evaluated.case_id)
            {
                return Ok(CompositionOutcome {
                    composed: false,
                    reason: "s5_receipt_not_allowlisted",
                });
            }
            compose_evaluated(fixture, evaluated)?;
            Ok(CompositionOutcome {
                composed: true,
                reason: "s5_receipt_composed",
            })
        })
        .collect()
}

fn audit_s4_identity_gap(fixture: &S5Fixture) -> anyhow::Result<S4IdentityAudit> {
    let schedules: S4Schedules =
        serde_json::from_slice(S4_REPLAY_SCHEDULES_BYTES).context("parse frozen S4 schedules")?;
    let s3_cases = evaluate_frozen_cases().context("run frozen S3 verifier for S4 audit")?;
    let by_id = s3_cases
        .iter()
        .map(|case| (case.case_id.as_str(), case))
        .collect::<BTreeMap<_, _>>();
    let mut audit = S4IdentityAudit {
        reviewable_step_count: 0,
        exact_identity_match_count: 0,
        exact_identity_mismatch_count: 0,
    };

    for schedule in schedules.schedules {
        ensure!(
            schedule.expected_outcomes.len() == schedule.steps.len(),
            "S4 schedule step/outcome count differs"
        );
        for (outcome, step) in schedule.expected_outcomes.iter().zip(&schedule.steps) {
            if !matches!(outcome.as_str(), "committed" | "already_committed") {
                continue;
            }
            audit.reviewable_step_count += 1;
            let signed = by_id
                .get(step.s3_case_id.as_str())
                .with_context(|| format!("unknown S4-referenced S3 case {}", step.s3_case_id))?;
            if step.receipt_id == signed.receipt_id && step.nonce == signed.nonce {
                audit.exact_identity_match_count += 1;
            } else {
                audit.exact_identity_mismatch_count += 1;
            }
        }
    }
    ensure!(
        audit.reviewable_step_count == fixture.contract.s4_reviewable_step_count
            && audit.exact_identity_match_count
                == fixture.contract.s4_end_to_end_identity_match_count
            && audit.exact_identity_mismatch_count
                == fixture.contract.s4_end_to_end_identity_mismatch_count,
        "S4 end-to-end identity audit differs from the frozen S5 contract"
    );
    Ok(audit)
}

fn error_code(result: VerifierResult<ReplayConsumeReceiptV1>) -> Option<&'static str> {
    result.err().map(|error| error.code())
}

fn private_tempdir(label: &str) -> tempfile::TempDir {
    tempfile::Builder::new()
        .prefix(&format!("ab-agent-authority-s5-{label}-"))
        .tempdir()
        .expect("create S5 temporary directory")
}

fn database(directory: &tempfile::TempDir) -> PathBuf {
    directory.path().join("replay.db")
}

fn helper_command(test_name: &str, database: &Path) -> Command {
    let mut command = Command::new(std::env::current_exe().expect("current test executable"));
    command
        .arg("--ignored")
        .arg("--exact")
        .arg(test_name)
        .arg("--nocapture")
        .env(HELPER_DB_ENV, database)
        .stdout(Stdio::null())
        .stderr(Stdio::null());
    command
}

fn wait_for_marker(marker: &Path) {
    let deadline = std::time::Instant::now() + Duration::from_secs(10);
    while !marker.exists() {
        assert!(
            std::time::Instant::now() < deadline,
            "S5 helper marker timeout"
        );
        std::thread::sleep(Duration::from_millis(5));
    }
}

#[test]
fn s5_frozen_sources_commitments_counts_and_authority_are_exact() {
    let fixture = frozen_fixture().expect("S5 fixture parses and pins its sources");
    assert_eq!(fixture.contract.s3_case_count, 27);
    assert_eq!(fixture.contract.s3_verified_case_count, 4);
    assert_eq!(fixture.contract.s4_referenced_verified_case_count, 2);
    assert_eq!(fixture.contract.composition_eligible_case_count, 2);
    assert_eq!(fixture.contract.s4_reviewable_step_count, 7);
    assert_eq!(fixture.contract.s4_end_to_end_identity_match_count, 0);
    assert_eq!(fixture.contract.s4_end_to_end_identity_mismatch_count, 7);
    assert_eq!(fixture.cases.len(), 2);
    assert_eq!(fixture.fault_expectations.len(), 8);
    assert!(fixture.authority.all_false());

    for expected in &fixture.cases {
        let composed =
            compose_case(&fixture, &expected.case_id).expect("frozen eligible receipt composes");
        assert_eq!(composed.receipt_id, expected.receipt_id);
        assert_eq!(composed.nonce, expected.nonce);
        assert_eq!(
            hex(&composed.transaction_identity_sha256),
            expected.transaction_identity_sha256
        );
        assert_eq!(
            hex(&composed.scope_commitment_sha256),
            expected.scope_commitment_sha256
        );
        assert_eq!(hex(&composed.payload_sha256), expected.payload_sha256);
    }
}

#[test]
fn s5_real_s3_verification_and_allowlist_precede_commitment_derivation() {
    let fixture = frozen_fixture().expect("S5 fixture");
    let outcomes = composition_outcomes_for_all_s3_cases(&fixture)
        .expect("all S3 cases are independently evaluated");
    assert_eq!(outcomes.len(), 27);
    assert_eq!(
        outcomes.iter().filter(|outcome| outcome.composed).count(),
        2
    );
    assert_eq!(
        outcomes
            .iter()
            .filter(|outcome| outcome.reason == "s5_receipt_not_allowlisted")
            .count(),
        2
    );
    assert_eq!(
        outcomes
            .iter()
            .filter(|outcome| outcome.reason == "s5_receipt_not_verified")
            .count(),
        23
    );
}

#[test]
fn s5_s4_reviewable_steps_have_zero_end_to_end_identity_matches() {
    let fixture = frozen_fixture().expect("S5 fixture");
    let audit = audit_s4_identity_gap(&fixture).expect("S4 identity audit");
    assert_eq!(audit.reviewable_step_count, 7);
    assert_eq!(audit.exact_identity_match_count, 0);
    assert_eq!(audit.exact_identity_mismatch_count, 7);
}

#[test]
fn s5_exact_receipts_commit_once_and_restart_rejects_replay() {
    let fixture = frozen_fixture().expect("S5 fixture");
    let directory = private_tempdir("restart");
    let path = database(&directory);
    let registry =
        provision_and_open_for_test(&path, GENERATION).expect("provision test-only S7 registry");

    for case_id in [PRIMARY_CASE, SECONDARY_CASE] {
        let composed = compose_case(&fixture, case_id).expect("compose exact S3 receipt");
        let receipt = registry
            .consume_once(composed.request())
            .expect("first exact consume succeeds");
        assert!(receipt.durable);
    }
    drop(registry);

    let reopened = open_for_test(&path, GENERATION).expect("reopen pinned S7 registry");
    for case_id in [PRIMARY_CASE, SECONDARY_CASE] {
        let composed = compose_case(&fixture, case_id).expect("recompose exact S3 receipt");
        assert_eq!(
            error_code(reopened.consume_once(composed.request())),
            Some("track_b_detached_v1_replay")
        );
    }
}

#[test]
fn s5_scope_and_payload_substitution_collide_without_overwrite() {
    let fixture = frozen_fixture().expect("S5 fixture");
    let directory = private_tempdir("collision");
    let path = database(&directory);
    let registry =
        provision_and_open_for_test(&path, GENERATION).expect("provision test-only S7 registry");
    let composed = compose_case(&fixture, PRIMARY_CASE).expect("compose exact S3 receipt");
    registry
        .consume_once(composed.request())
        .expect("first exact consume succeeds");

    let mut scope_substitution = composed.request();
    scope_substitution.scope_sha256[0] ^= 0x01;
    assert_eq!(
        error_code(registry.consume_once(scope_substitution)),
        Some("track_b_detached_v1_scope_collision")
    );

    let mut payload_substitution = composed.request();
    payload_substitution.payload_sha256[0] ^= 0x01;
    assert_eq!(
        error_code(registry.consume_once(payload_substitution)),
        Some("track_b_detached_v1_scope_collision")
    );
    assert_eq!(
        error_code(registry.consume_once(composed.request())),
        Some("track_b_detached_v1_replay")
    );
}

#[test]
fn s5_post_commit_result_loss_is_indeterminate_then_replay() {
    let fixture = frozen_fixture().expect("S5 fixture");
    let directory = private_tempdir("result-loss");
    let path = database(&directory);
    drop(provision_and_open_for_test(&path, GENERATION).expect("provision registry"));
    let registry =
        open_with_result_loss_for_test(&path, GENERATION).expect("fault-injected registry");
    let composed = compose_case(&fixture, PRIMARY_CASE).expect("compose exact S3 receipt");
    assert_eq!(
        error_code(registry.consume_once(composed.request())),
        Some("track_b_detached_v1_registry_indeterminate")
    );
    drop(registry);

    let reopened = open_for_test(&path, GENERATION).expect("reopen after result loss");
    assert_eq!(
        error_code(reopened.consume_once(composed.request())),
        Some("track_b_detached_v1_replay")
    );
}

#[test]
#[ignore]
fn s5_precommit_sigkill_helper() {
    if std::env::var_os(PRECOMMIT_HELPER_ENV).is_none() {
        return;
    }
    let fixture = frozen_fixture().expect("S5 fixture in child");
    let path = PathBuf::from(std::env::var_os(HELPER_DB_ENV).expect("S5 helper database"));
    let registry = open_for_test(&path, GENERATION).expect("child opens registry");
    let composed = compose_case(&fixture, PRIMARY_CASE).expect("child composes S3 receipt");
    let _ = registry.consume_once(composed.request());
    std::process::exit(32);
}

#[test]
fn s5_sigkill_before_commit_rolls_back_then_first_consume_succeeds() {
    let fixture = frozen_fixture().expect("S5 fixture");
    let directory = private_tempdir("precommit-sigkill");
    let path = database(&directory);
    let inserted = directory.path().join("inserted");
    drop(provision_and_open_for_test(&path, GENERATION).expect("provision registry"));
    const HELPER: &str = "temporal_replay_transport::agent_authority_receipt_durable_replay_s5::s5_precommit_sigkill_helper";
    let mut command = helper_command(HELPER, &path);
    command
        .env(PRECOMMIT_HELPER_ENV, "1")
        .env("AB_S7_PAUSE_BEFORE_COMMIT_MARKER", &inserted);
    let mut child = command.spawn().expect("spawn S5 pre-commit helper");
    wait_for_marker(&inserted);
    child.kill().expect("SIGKILL S5 pre-commit helper");
    assert!(!child.wait().expect("reap S5 pre-commit helper").success());

    let reopened = open_for_test(&path, GENERATION).expect("reopen after pre-commit SIGKILL");
    let composed = compose_case(&fixture, PRIMARY_CASE).expect("compose exact S3 receipt");
    let receipt = reopened
        .consume_once(composed.request())
        .expect("rolled-back insert permits one first consume");
    assert!(receipt.durable);
}

#[test]
#[ignore]
fn s5_postcommit_sigkill_helper() {
    if std::env::var_os(POSTCOMMIT_HELPER_ENV).is_none() {
        return;
    }
    let fixture = frozen_fixture().expect("S5 fixture in child");
    let path = PathBuf::from(std::env::var_os(HELPER_DB_ENV).expect("S5 helper database"));
    let committed =
        PathBuf::from(std::env::var_os("AB_AGENT_AUTHORITY_S5_COMMITTED").expect("marker"));
    let registry = open_for_test(&path, GENERATION).expect("child opens registry");
    let composed = compose_case(&fixture, PRIMARY_CASE).expect("child composes S3 receipt");
    registry
        .consume_once(composed.request())
        .expect("child durable commit");
    std::fs::write(&committed, b"committed").expect("write S5 commit marker");
    loop {
        std::thread::park_timeout(Duration::from_secs(1));
    }
}

#[test]
fn s5_sigkill_after_commit_preserves_tombstone_and_rejects_replay() {
    let fixture = frozen_fixture().expect("S5 fixture");
    let directory = private_tempdir("postcommit-sigkill");
    let path = database(&directory);
    let committed = directory.path().join("committed");
    drop(provision_and_open_for_test(&path, GENERATION).expect("provision registry"));
    const HELPER: &str = "temporal_replay_transport::agent_authority_receipt_durable_replay_s5::s5_postcommit_sigkill_helper";
    let mut command = helper_command(HELPER, &path);
    command
        .env(POSTCOMMIT_HELPER_ENV, "1")
        .env("AB_AGENT_AUTHORITY_S5_COMMITTED", &committed);
    let mut child = command.spawn().expect("spawn S5 post-commit helper");
    wait_for_marker(&committed);
    child.kill().expect("SIGKILL S5 post-commit helper");
    assert!(!child.wait().expect("reap S5 post-commit helper").success());

    let reopened = open_for_test(&path, GENERATION).expect("reopen after post-commit SIGKILL");
    let composed = compose_case(&fixture, PRIMARY_CASE).expect("compose exact S3 receipt");
    assert_eq!(
        error_code(reopened.consume_once(composed.request())),
        Some("track_b_detached_v1_replay")
    );
}
