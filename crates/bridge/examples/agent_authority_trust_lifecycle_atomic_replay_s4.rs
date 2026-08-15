//! Offline S4 trust-lifecycle and atomic replay preflight.
//!
//! This example verifies public-test lifecycle signatures and computes replay
//! candidate states in memory. It does not sign, persist, invoke T6/MCP, or
//! grant runtime authority.

use anyhow::{ensure, Context};
use base64::{engine::general_purpose::STANDARD, Engine as _};
use ring::signature::{UnparsedPublicKey, ED25519};
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use std::collections::{BTreeMap, BTreeSet};

const ANCHOR_BYTES: &[u8] =
    include_bytes!("../tests/fixtures/agent_authority_trust_lifecycle_anchor_s4.json");
const JOURNAL_BYTES: &[u8] =
    include_bytes!("../tests/fixtures/agent_authority_trust_lifecycle_journals_s4.json");
const REPLAY_BYTES: &[u8] =
    include_bytes!("../tests/fixtures/agent_authority_atomic_replay_schedules_s4.json");
const S3_VERIFIER_BYTES: &[u8] = include_bytes!("agent_authority_signed_trust_root_s3.rs");
const S3_TRUST_REGISTRY_BYTES: &[u8] =
    include_bytes!("../tests/fixtures/agent_authority_trust_registry_s3.json");
const S3_SIGNED_RECEIPTS_BYTES: &[u8] =
    include_bytes!("../tests/fixtures/agent_authority_signed_receipts_s3.json");
const S3_DESIGN_BYTES: &[u8] =
    include_bytes!("../../../docs/design/AGENT_AUTHORITY_SIGNED_TRUST_ROOT_S3_2026_07_16.md");
const S3_RESULT_BYTES: &[u8] = include_bytes!(
    "../../../docs/reports/goal-c-u/2026-07-16-agent-authority-signed-trust-root-s3-result.md"
);

const ANCHOR_SCHEMA: &str = "agent_bridge.agent_authority_trust_lifecycle_anchor.s4.v0";
const JOURNAL_SCHEMA: &str = "agent_bridge.agent_authority_trust_lifecycle_journals.s4_fixture.v0";
const REPLAY_SCHEMA: &str = "agent_bridge.agent_authority_atomic_replay_schedules.s4_fixture.v0";
const EVENT_SCHEMA: &str = "agent_bridge.authority_trust_lifecycle_event.s4.v0";
const REPORT_SCHEMA: &str =
    "agent_bridge.agent_authority_trust_lifecycle_atomic_replay.s4_report.v0";
const ACCEPTED_ALGORITHM: &str = "ed25519";
const REQUIRED_SIGNER_ROLE: &str = "lifecycle_authority";
const ROOT_ID: &str = "root:owner-offline-fixture:v1";
const ROOT_EPOCH: u64 = 4;
const MINIMUM_REGISTRY_GENERATION: u64 = 9;
const LATEST_MASTER_COMMIT: &str = "c9c50917687c7715b031a6bfe8dd7801bfd737ee";
const S3_RESULT_COMMIT: &str = "149bafbc3a04126ea28f05a85c3e30d2748aceed";
const S4_LINEAGE_MERGE_COMMIT: &str = "72ba3dabd2569e651e05a90dfc1c898fa366c24e";
const ANCHOR_SHA256: &str = "daae7bea20842cd1f8116084f757843dcc9020aa2b3d40ab26ce3af9114f1fe5";
const JOURNAL_SHA256: &str = "b1ffd8c38060f6f39925fea97ac3c21f20a138ea1debb430c06f9fa44b7c4342";
const REPLAY_SHA256: &str = "dd24e1a8678205ce4f7ae6bae940eeb1e75136f7614b425b7989abe4e0d908d3";
const EVENT_DOMAIN: &[u8] = b"agent_bridge.authority_trust_lifecycle.s4.event.v0";
const SNAPSHOT_DOMAIN: &[u8] = b"agent_bridge.atomic_replay.s4.snapshot.v0";

#[derive(Clone, Debug, Deserialize, Eq, PartialEq)]
#[serde(deny_unknown_fields)]
struct TrustAnchor {
    schema: String,
    anchor_id: String,
    root_id: String,
    trusted_root_epoch: u64,
    minimum_registry_generation: u64,
    genesis_digest: String,
    accepted_event_schema: String,
    accepted_algorithm: String,
    required_signer_role: String,
    fixture_key_note: String,
    private_key_present: bool,
    production_trust_root: bool,
    root_rotation_proven: bool,
    signers: Vec<LifecycleSigner>,
    source: SourcePin,
}

#[derive(Clone, Debug, Deserialize, Eq, PartialEq)]
#[serde(deny_unknown_fields)]
struct LifecycleSigner {
    signer_id: String,
    role: String,
    algorithm: String,
    public_key_base64: String,
    revoked: bool,
}

#[derive(Clone, Debug, Deserialize, Eq, PartialEq)]
#[serde(deny_unknown_fields)]
struct SourcePin {
    latest_master_commit: String,
    s3_result_commit: String,
    s4_lineage_merge_commit: String,
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
struct LifecycleCorpus {
    schema: String,
    fixture_signing_provenance: String,
    source: SourcePin,
    expected_distribution: BTreeMap<LifecycleStatus, usize>,
    cases: Vec<LifecycleCase>,
}

#[derive(Clone, Debug, Deserialize, Eq, PartialEq)]
#[serde(deny_unknown_fields)]
struct LifecycleCase {
    id: String,
    control: bool,
    verifier_available: bool,
    trusted_checkpoint: TrustedCheckpoint,
    events: Vec<LifecycleEvent>,
    expected_status: LifecycleStatus,
    expected_reasons: Vec<String>,
}

#[derive(Clone, Debug, Deserialize, Eq, PartialEq)]
#[serde(deny_unknown_fields)]
struct TrustedCheckpoint {
    root_id: String,
    root_epoch: u64,
    registry_generation: u64,
    expected_head_digest: String,
    expected_active_key_id: String,
    evaluation_time_unix: u64,
}

#[derive(Clone, Debug, Deserialize, Eq, PartialEq)]
#[serde(deny_unknown_fields)]
struct LifecycleEvent {
    event_schema: String,
    root_id: String,
    root_epoch: u64,
    generation: u64,
    sequence: u64,
    previous_event_digest: String,
    action: String,
    target_key_id: String,
    replaces_key_id: String,
    target_not_before_unix: u64,
    target_not_after_unix: u64,
    effective_at_unix: u64,
    reason_code: String,
    signer_id: String,
    algorithm: String,
    event_digest: String,
    signature_base64: String,
}

#[derive(Clone, Copy, Debug, Deserialize, Eq, Ord, PartialEq, PartialOrd, Serialize)]
#[serde(rename_all = "snake_case")]
enum LifecycleStatus {
    Current,
    Invalid,
    Untrusted,
    Rollback,
    Forked,
    Revoked,
    Stale,
    Ambiguous,
    Unavailable,
}

#[derive(Clone, Debug, Deserialize, Eq, PartialEq)]
#[serde(deny_unknown_fields)]
struct ReplayCorpus {
    schema: String,
    source: SourcePin,
    contract: ReplayContract,
    initial_snapshot: ReplaySnapshot,
    expected_step_outcome_counts: BTreeMap<ReplayOutcome, usize>,
    schedules: Vec<ReplaySchedule>,
}

#[derive(Clone, Debug, Deserialize, Eq, PartialEq)]
#[serde(deny_unknown_fields)]
struct ReplayContract {
    eligible_s3_status: String,
    current_lifecycle_status: String,
    idempotency_precedes_version_check: bool,
    candidate_state_only: bool,
    persistent_state_mutation: bool,
    runtime_consumer_enabled: bool,
    receipt_identity_end_to_end_reverified: bool,
}

#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(deny_unknown_fields)]
struct ReplaySnapshot {
    snapshot_id: String,
    version: u64,
    consumed: Vec<ConsumedRecord>,
    snapshot_digest: String,
}

#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(deny_unknown_fields)]
struct ConsumedRecord {
    transaction_id: String,
    receipt_id: String,
    nonce: String,
    commit_version: u64,
}

#[derive(Clone, Debug, Deserialize, Eq, PartialEq)]
#[serde(deny_unknown_fields)]
struct ReplaySchedule {
    id: String,
    control: bool,
    lifecycle_case_id: String,
    steps: Vec<ReplayStep>,
    expected_outcomes: Vec<ReplayOutcome>,
    expected_final_version: u64,
    expected_consumed_count: usize,
    expected_reviewable_count: usize,
}

#[derive(Clone, Debug, Deserialize, Eq, PartialEq)]
#[serde(deny_unknown_fields)]
struct ReplayStep {
    worker_id: String,
    transaction_id: String,
    receipt_id: String,
    nonce: String,
    s3_case_id: String,
    expected_version: u64,
    mode: ReplayMode,
}

#[derive(Clone, Copy, Debug, Deserialize, Eq, Ord, PartialEq, PartialOrd, Serialize)]
#[serde(rename_all = "snake_case")]
enum ReplayMode {
    Commit,
    PrepareOnly,
    CrashBeforeCommit,
    CommitAckLost,
}

#[derive(Clone, Copy, Debug, Deserialize, Eq, Ord, PartialEq, PartialOrd, Serialize)]
#[serde(rename_all = "snake_case")]
enum ReplayOutcome {
    Committed,
    AlreadyCommitted,
    NonceReplayed,
    VersionConflict,
    PreparedNotCommitted,
    CrashedBeforeCommit,
    CommitAckLost,
    TransactionIdentityConflict,
    ReceiptIneligible,
    LifecycleBlocked,
}

#[derive(Clone, Copy, Debug, Deserialize, Eq, Ord, PartialEq, PartialOrd)]
#[serde(rename_all = "snake_case")]
enum S3Status {
    Verified,
    Invalid,
    Untrusted,
    Revoked,
    Stale,
    Replayed,
    OutOfScope,
    Unavailable,
}

#[derive(Debug, Deserialize)]
struct S3CorpusIndex {
    cases: Vec<S3CaseIndex>,
}

#[derive(Debug, Deserialize)]
struct S3CaseIndex {
    id: String,
    expected_status: S3Status,
}

type S3CaseMap = BTreeMap<String, S3Status>;

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
    may_run_executor: bool,
    may_write_memory: bool,
    may_write_graph: bool,
    may_change_retrieval: bool,
    may_change_session: bool,
    may_persist_replay_state: bool,
    may_mutate_trust_registry: bool,
    production_trust_root_proven: bool,
    root_rotation_proven: bool,
    production_atomicity_proven: bool,
    production_authority_granted: bool,
}

#[derive(Clone, Debug, Eq, PartialEq, Serialize)]
struct LifecycleCaseResult {
    id: String,
    control: bool,
    derived_status: LifecycleStatus,
    expected_status: LifecycleStatus,
    reasons: Vec<String>,
    expected_reasons: Vec<String>,
    status_matches: bool,
    reasons_match: bool,
    signature_verification_attempt_count: usize,
    signature_verification_success_count: usize,
    signature_verification_failure_count: usize,
    active_key_id: Option<String>,
}

#[derive(Clone, Debug, Eq, PartialEq, Serialize)]
struct LifecycleSuite {
    status: &'static str,
    case_count: usize,
    current_count: usize,
    invalid_count: usize,
    untrusted_count: usize,
    rollback_count: usize,
    forked_count: usize,
    revoked_count: usize,
    stale_count: usize,
    ambiguous_count: usize,
    unavailable_count: usize,
    signature_verification_attempt_count: usize,
    signature_verification_success_count: usize,
    signature_verification_failure_count: usize,
    false_current_count: usize,
    control_false_reject_count: usize,
    status_mismatch_count: usize,
    reason_mismatch_count: usize,
    results: Vec<LifecycleCaseResult>,
}

#[derive(Clone, Debug, Eq, PartialEq, Serialize)]
struct ReplayStepResult {
    worker_id: String,
    transaction_id: String,
    receipt_id: String,
    nonce: String,
    s3_case_id: String,
    version_before: u64,
    version_after: u64,
    outcome: ReplayOutcome,
    expected_outcome: ReplayOutcome,
    outcome_matches: bool,
    reviewable_after_atomic_consume: bool,
}

#[derive(Clone, Debug, Eq, PartialEq, Serialize)]
struct ReplayScheduleResult {
    id: String,
    control: bool,
    lifecycle_case_id: String,
    steps: Vec<ReplayStepResult>,
    final_version: u64,
    expected_final_version: u64,
    final_consumed_count: usize,
    expected_consumed_count: usize,
    reviewable_count: usize,
    expected_reviewable_count: usize,
    final_snapshot_digest: String,
    final_state_matches: bool,
}

#[derive(Clone, Debug, Eq, PartialEq, Serialize)]
struct ReplaySuite {
    status: &'static str,
    schedule_count: usize,
    step_count: usize,
    committed_count: usize,
    already_committed_count: usize,
    nonce_replayed_count: usize,
    version_conflict_count: usize,
    prepared_not_committed_count: usize,
    crashed_before_commit_count: usize,
    commit_ack_lost_count: usize,
    transaction_identity_conflict_count: usize,
    receipt_ineligible_count: usize,
    lifecycle_blocked_count: usize,
    reviewable_count: usize,
    outcome_mismatch_count: usize,
    final_state_mismatch_count: usize,
    false_reviewable_count: usize,
    results: Vec<ReplayScheduleResult>,
}

#[derive(Clone, Debug, Eq, PartialEq, Serialize)]
struct Report {
    schema: &'static str,
    status: &'static str,
    latest_master_commit: &'static str,
    s3_result_commit: &'static str,
    s4_lineage_merge_commit: &'static str,
    anchor_sha256: String,
    journal_sha256: String,
    replay_sha256: String,
    source_sha256: BTreeMap<String, String>,
    crypto_verifier: &'static str,
    public_test_keys_only: bool,
    private_signing_material_embedded: bool,
    root_anchor_fixture_only: bool,
    candidate_state_persisted: bool,
    runtime_consumer_enabled: bool,
    receipt_identity_end_to_end_reverified: bool,
    lifecycle: LifecycleSuite,
    replay: ReplaySuite,
    authority: Authority,
}

fn load_anchor(bytes: &[u8]) -> anyhow::Result<TrustAnchor> {
    serde_json::from_slice(bytes).context("parse S4 trust lifecycle anchor")
}

fn load_journals(bytes: &[u8]) -> anyhow::Result<LifecycleCorpus> {
    serde_json::from_slice(bytes).context("parse S4 lifecycle journal corpus")
}

fn load_replay(bytes: &[u8]) -> anyhow::Result<ReplayCorpus> {
    serde_json::from_slice(bytes).context("parse S4 atomic replay corpus")
}

fn load_s3_case_index(bytes: &[u8]) -> anyhow::Result<S3CaseMap> {
    let corpus: S3CorpusIndex =
        serde_json::from_slice(bytes).context("parse source-bound S3 case index")?;
    let mut cases = BTreeMap::new();
    for case in corpus.cases {
        ensure!(
            !case.id.trim().is_empty()
                && cases
                    .insert(case.id.clone(), case.expected_status)
                    .is_none(),
            "duplicate or empty S3 case id {}",
            case.id
        );
    }
    ensure!(cases.len() == 27, "S3 case index must contain 27 cases");
    Ok(cases)
}

fn frozen_sources() -> EmbeddedSources {
    BTreeMap::from([
        (
            "s4_anchor",
            EmbeddedSource {
                path: "crates/bridge/tests/fixtures/agent_authority_trust_lifecycle_anchor_s4.json",
                bytes: ANCHOR_BYTES,
            },
        ),
        (
            "s4_lifecycle_journals",
            EmbeddedSource {
                path: "crates/bridge/tests/fixtures/agent_authority_trust_lifecycle_journals_s4.json",
                bytes: JOURNAL_BYTES,
            },
        ),
        (
            "s3_verifier",
            EmbeddedSource {
                path: "crates/bridge/examples/agent_authority_signed_trust_root_s3.rs",
                bytes: S3_VERIFIER_BYTES,
            },
        ),
        (
            "s3_trust_registry",
            EmbeddedSource {
                path: "crates/bridge/tests/fixtures/agent_authority_trust_registry_s3.json",
                bytes: S3_TRUST_REGISTRY_BYTES,
            },
        ),
        (
            "s3_signed_receipts",
            EmbeddedSource {
                path: "crates/bridge/tests/fixtures/agent_authority_signed_receipts_s3.json",
                bytes: S3_SIGNED_RECEIPTS_BYTES,
            },
        ),
        (
            "s3_design",
            EmbeddedSource {
                path: "docs/design/AGENT_AUTHORITY_SIGNED_TRUST_ROOT_S3_2026_07_16.md",
                bytes: S3_DESIGN_BYTES,
            },
        ),
        (
            "s3_result",
            EmbeddedSource {
                path: "docs/reports/goal-c-u/2026-07-16-agent-authority-signed-trust-root-s3-result.md",
                bytes: S3_RESULT_BYTES,
            },
        ),
    ])
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

fn canonical_event_bytes(event: &LifecycleEvent) -> Vec<u8> {
    let mut bytes = Vec::with_capacity(1500);
    bytes.extend_from_slice(&(EVENT_DOMAIN.len() as u32).to_be_bytes());
    bytes.extend_from_slice(EVENT_DOMAIN);
    push_string_field(&mut bytes, "event_schema", &event.event_schema);
    push_string_field(&mut bytes, "root_id", &event.root_id);
    push_u64_field(&mut bytes, "root_epoch", event.root_epoch);
    push_u64_field(&mut bytes, "generation", event.generation);
    push_u64_field(&mut bytes, "sequence", event.sequence);
    push_string_field(
        &mut bytes,
        "previous_event_digest",
        &event.previous_event_digest,
    );
    push_string_field(&mut bytes, "action", &event.action);
    push_string_field(&mut bytes, "target_key_id", &event.target_key_id);
    push_string_field(&mut bytes, "replaces_key_id", &event.replaces_key_id);
    push_u64_field(
        &mut bytes,
        "target_not_before_unix",
        event.target_not_before_unix,
    );
    push_u64_field(
        &mut bytes,
        "target_not_after_unix",
        event.target_not_after_unix,
    );
    push_u64_field(&mut bytes, "effective_at_unix", event.effective_at_unix);
    push_string_field(&mut bytes, "reason_code", &event.reason_code);
    push_string_field(&mut bytes, "signer_id", &event.signer_id);
    push_string_field(&mut bytes, "algorithm", &event.algorithm);
    bytes
}

fn canonical_snapshot_bytes(snapshot: &ReplaySnapshot) -> Vec<u8> {
    let mut bytes = Vec::with_capacity(1000);
    bytes.extend_from_slice(&(SNAPSHOT_DOMAIN.len() as u32).to_be_bytes());
    bytes.extend_from_slice(SNAPSHOT_DOMAIN);
    push_string_field(&mut bytes, "snapshot_id", &snapshot.snapshot_id);
    push_u64_field(&mut bytes, "version", snapshot.version);
    let mut records = snapshot.consumed.iter().collect::<Vec<_>>();
    records.sort_by(|left, right| left.nonce.cmp(&right.nonce));
    push_u64_field(
        &mut bytes,
        "record_count",
        u64::try_from(records.len()).expect("record count fits u64"),
    );
    for record in records {
        push_string_field(&mut bytes, "transaction_id", &record.transaction_id);
        push_string_field(&mut bytes, "receipt_id", &record.receipt_id);
        push_string_field(&mut bytes, "nonce", &record.nonce);
        push_u64_field(&mut bytes, "commit_version", record.commit_version);
    }
    bytes
}

fn snapshot_digest(snapshot: &ReplaySnapshot) -> String {
    format!("sha256:{}", sha256(&canonical_snapshot_bytes(snapshot)))
}

fn sha256(bytes: &[u8]) -> String {
    format!("{:x}", Sha256::digest(bytes))
}

fn sha256_digest(bytes: &[u8]) -> String {
    format!("sha256:{}", sha256(bytes))
}

fn is_sha256_digest(value: &str) -> bool {
    value.len() == 71
        && value.starts_with("sha256:")
        && value[7..]
            .bytes()
            .all(|byte| byte.is_ascii_digit() || (b'a'..=b'f').contains(&byte))
}

fn is_sha256_hex(value: &str) -> bool {
    value.len() == 64
        && value
            .bytes()
            .all(|byte| byte.is_ascii_digit() || (b'a'..=b'f').contains(&byte))
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

fn expected_lifecycle_distribution() -> BTreeMap<LifecycleStatus, usize> {
    BTreeMap::from([
        (LifecycleStatus::Current, 2),
        (LifecycleStatus::Invalid, 3),
        (LifecycleStatus::Untrusted, 3),
        (LifecycleStatus::Rollback, 2),
        (LifecycleStatus::Forked, 5),
        (LifecycleStatus::Revoked, 2),
        (LifecycleStatus::Stale, 2),
        (LifecycleStatus::Ambiguous, 1),
        (LifecycleStatus::Unavailable, 1),
    ])
}

fn expected_replay_outcomes() -> BTreeMap<ReplayOutcome, usize> {
    BTreeMap::from([
        (ReplayOutcome::Committed, 4),
        (ReplayOutcome::AlreadyCommitted, 3),
        (ReplayOutcome::NonceReplayed, 3),
        (ReplayOutcome::VersionConflict, 1),
        (ReplayOutcome::PreparedNotCommitted, 1),
        (ReplayOutcome::CrashedBeforeCommit, 1),
        (ReplayOutcome::CommitAckLost, 1),
        (ReplayOutcome::TransactionIdentityConflict, 1),
        (ReplayOutcome::ReceiptIneligible, 7),
        (ReplayOutcome::LifecycleBlocked, 8),
    ])
}

fn validate_lineage(source: &SourcePin) -> anyhow::Result<()> {
    ensure!(
        source.latest_master_commit == LATEST_MASTER_COMMIT,
        "unexpected latest-master commit"
    );
    ensure!(
        source.s3_result_commit == S3_RESULT_COMMIT,
        "unexpected S3 result commit"
    );
    ensure!(
        source.s4_lineage_merge_commit == S4_LINEAGE_MERGE_COMMIT,
        "unexpected S4 lineage merge commit"
    );
    Ok(())
}

fn validate_source_pins(
    source: &SourcePin,
    expected_ids: &[&str],
    sources: &EmbeddedSources,
) -> anyhow::Result<()> {
    validate_lineage(source)?;
    ensure!(
        source.files.len() == expected_ids.len(),
        "source pin count differs from frozen contract"
    );
    let expected = expected_ids.iter().copied().collect::<BTreeSet<_>>();
    let mut seen = BTreeSet::new();
    for pin in &source.files {
        ensure!(
            !pin.id.trim().is_empty() && seen.insert(pin.id.as_str()),
            "duplicate or empty source id {}",
            pin.id
        );
        ensure!(
            expected.contains(pin.id.as_str()),
            "unexpected source id {}",
            pin.id
        );
        ensure!(
            is_sha256_hex(&pin.sha256),
            "{} source hash shape is invalid",
            pin.id
        );
        let embedded = sources
            .get(pin.id.as_str())
            .with_context(|| format!("missing embedded source {}", pin.id))?;
        ensure!(pin.path == embedded.path, "{} source path changed", pin.id);
        ensure!(
            pin.sha256 == sha256(embedded.bytes),
            "{} source hash changed",
            pin.id
        );
    }
    ensure!(seen == expected, "source ids differ from frozen contract");
    Ok(())
}

fn validate_inputs(
    anchor: &TrustAnchor,
    journals: &LifecycleCorpus,
    replay: &ReplayCorpus,
    sources: &EmbeddedSources,
    s3: &S3CaseMap,
) -> anyhow::Result<()> {
    ensure!(anchor.schema == ANCHOR_SCHEMA, "unexpected anchor schema");
    ensure!(!anchor.anchor_id.trim().is_empty(), "anchor id is empty");
    ensure!(anchor.root_id == ROOT_ID, "unexpected root id");
    ensure!(
        anchor.trusted_root_epoch == ROOT_EPOCH,
        "unexpected root epoch"
    );
    ensure!(
        anchor.minimum_registry_generation == MINIMUM_REGISTRY_GENERATION,
        "unexpected minimum registry generation"
    );
    ensure!(
        is_sha256_digest(&anchor.genesis_digest),
        "invalid genesis digest"
    );
    ensure!(
        anchor.accepted_event_schema == EVENT_SCHEMA,
        "unexpected event schema"
    );
    ensure!(
        anchor.accepted_algorithm == ACCEPTED_ALGORITHM,
        "unexpected lifecycle algorithm"
    );
    ensure!(
        anchor.required_signer_role == REQUIRED_SIGNER_ROLE,
        "unexpected signer role"
    );
    ensure!(
        !anchor.fixture_key_note.trim().is_empty(),
        "fixture key note is empty"
    );
    ensure!(
        !anchor.private_key_present,
        "anchor must not contain private keys"
    );
    ensure!(
        !anchor.production_trust_root,
        "fixture must not claim production trust"
    );
    ensure!(
        !anchor.root_rotation_proven,
        "fixture must not claim root rotation"
    );
    ensure!(
        anchor.signers.len() == 3,
        "anchor must contain three signers"
    );
    let mut signer_ids = BTreeSet::new();
    for signer in &anchor.signers {
        ensure!(
            !signer.signer_id.trim().is_empty() && signer_ids.insert(signer.signer_id.as_str()),
            "duplicate or empty signer id {}",
            signer.signer_id
        );
        ensure!(
            !signer.role.trim().is_empty(),
            "{} role is empty",
            signer.signer_id
        );
        ensure!(
            signer.algorithm == ACCEPTED_ALGORITHM,
            "{} algorithm differs from anchor",
            signer.signer_id
        );
        let public_key = STANDARD
            .decode(&signer.public_key_base64)
            .with_context(|| format!("{} public key is not Base64", signer.signer_id))?;
        ensure!(
            public_key.len() == 32,
            "{} public key length is not 32 bytes",
            signer.signer_id
        );
    }
    ensure!(
        anchor
            .signers
            .iter()
            .any(|signer| signer.role == REQUIRED_SIGNER_ROLE && !signer.revoked),
        "anchor has no active lifecycle authority"
    );
    validate_source_pins(
        &anchor.source,
        &[
            "s3_verifier",
            "s3_trust_registry",
            "s3_signed_receipts",
            "s3_design",
            "s3_result",
        ],
        sources,
    )?;

    ensure!(
        journals.schema == JOURNAL_SCHEMA,
        "unexpected journal schema"
    );
    ensure!(
        !journals.fixture_signing_provenance.trim().is_empty(),
        "journal signing provenance is empty"
    );
    ensure!(
        journals.expected_distribution == expected_lifecycle_distribution(),
        "lifecycle expected distribution differs from freeze"
    );
    validate_source_pins(
        &journals.source,
        &[
            "s4_anchor",
            "s3_verifier",
            "s3_trust_registry",
            "s3_signed_receipts",
            "s3_design",
            "s3_result",
        ],
        sources,
    )?;
    ensure!(
        journals.cases.len() == 21,
        "journal corpus must contain 21 cases"
    );
    let mut case_ids = BTreeSet::new();
    let mut control_count = 0usize;
    let mut event_count = 0usize;
    let mut expected_counts = BTreeMap::new();
    for case in &journals.cases {
        ensure!(
            !case.id.trim().is_empty() && case_ids.insert(case.id.as_str()),
            "duplicate or empty lifecycle case id {}",
            case.id
        );
        ensure!(
            !case.events.is_empty(),
            "{} has no lifecycle events",
            case.id
        );
        ensure!(
            !case.trusted_checkpoint.root_id.trim().is_empty(),
            "{} checkpoint root id is empty",
            case.id
        );
        ensure!(
            is_sha256_digest(&case.trusted_checkpoint.expected_head_digest),
            "{} checkpoint head digest is invalid",
            case.id
        );
        ensure!(
            !case
                .trusted_checkpoint
                .expected_active_key_id
                .trim()
                .is_empty(),
            "{} checkpoint active key id is empty",
            case.id
        );
        validate_sorted_unique(&case.expected_reasons, &format!("{} reasons", case.id))?;
        control_count += usize::from(case.control);
        event_count += case.events.len();
        *expected_counts
            .entry(case.expected_status)
            .or_insert(0usize) += 1;
        for event in &case.events {
            for (name, value) in [
                ("event_schema", event.event_schema.as_str()),
                ("root_id", event.root_id.as_str()),
                (
                    "previous_event_digest",
                    event.previous_event_digest.as_str(),
                ),
                ("action", event.action.as_str()),
                ("target_key_id", event.target_key_id.as_str()),
                ("reason_code", event.reason_code.as_str()),
                ("signer_id", event.signer_id.as_str()),
                ("algorithm", event.algorithm.as_str()),
                ("event_digest", event.event_digest.as_str()),
                ("signature_base64", event.signature_base64.as_str()),
            ] {
                ensure!(
                    !value.trim().is_empty(),
                    "{} event {name} is empty",
                    case.id
                );
            }
            ensure!(
                event.event_schema == EVENT_SCHEMA,
                "{} event schema changed",
                case.id
            );
            ensure!(
                event.algorithm == ACCEPTED_ALGORITHM,
                "{} event algorithm changed",
                case.id
            );
            ensure!(
                event.sequence > 0 && event.generation > 0,
                "{} event position is zero",
                case.id
            );
            ensure!(
                event.target_not_before_unix < event.target_not_after_unix,
                "{} event key validity window is invalid",
                case.id
            );
            ensure!(
                is_sha256_digest(&event.previous_event_digest)
                    && is_sha256_digest(&event.event_digest),
                "{} event digest shape is invalid",
                case.id
            );
            let signature = STANDARD
                .decode(&event.signature_base64)
                .with_context(|| format!("{} event signature is not Base64", case.id))?;
            ensure!(
                signature.len() == 64,
                "{} event signature length is invalid",
                case.id
            );
        }
    }
    ensure!(
        control_count == 2,
        "journal corpus must contain two controls"
    );
    ensure!(
        event_count == 190,
        "journal corpus must contain 190 event instances"
    );
    ensure!(
        expected_counts == journals.expected_distribution,
        "lifecycle labels do not match expected distribution"
    );

    ensure!(replay.schema == REPLAY_SCHEMA, "unexpected replay schema");
    validate_source_pins(
        &replay.source,
        &[
            "s4_anchor",
            "s4_lifecycle_journals",
            "s3_signed_receipts",
            "s3_result",
        ],
        sources,
    )?;
    ensure!(
        replay.contract.eligible_s3_status == "verified",
        "unexpected S3 eligibility"
    );
    ensure!(
        replay.contract.current_lifecycle_status == "current",
        "unexpected lifecycle eligibility"
    );
    ensure!(
        replay.contract.idempotency_precedes_version_check,
        "idempotency precedence must remain explicit"
    );
    ensure!(
        replay.contract.candidate_state_only,
        "replay must remain candidate-only"
    );
    ensure!(
        !replay.contract.persistent_state_mutation,
        "replay persistence must remain false"
    );
    ensure!(
        !replay.contract.runtime_consumer_enabled,
        "runtime consumer must remain false"
    );
    ensure!(
        !replay.contract.receipt_identity_end_to_end_reverified,
        "S4 must not claim end-to-end receipt composition"
    );
    ensure!(
        replay.expected_step_outcome_counts == expected_replay_outcomes(),
        "replay outcome distribution differs from freeze"
    );
    validate_snapshot(&replay.initial_snapshot)?;
    ensure!(
        replay.initial_snapshot.version == 41,
        "initial snapshot version changed"
    );
    ensure!(
        replay.schedules.len() == 26,
        "replay must contain 26 schedules"
    );
    let mut schedule_ids = BTreeSet::new();
    let mut replay_control_count = 0usize;
    let mut step_count = 0usize;
    let mut outcome_counts = BTreeMap::new();
    for schedule in &replay.schedules {
        ensure!(
            !schedule.id.trim().is_empty() && schedule_ids.insert(schedule.id.as_str()),
            "duplicate or empty replay schedule id {}",
            schedule.id
        );
        ensure!(
            case_ids.contains(schedule.lifecycle_case_id.as_str()),
            "{} references unknown lifecycle case",
            schedule.id
        );
        ensure!(
            !schedule.steps.is_empty(),
            "{} has no replay steps",
            schedule.id
        );
        ensure!(
            schedule.steps.len() == schedule.expected_outcomes.len(),
            "{} expected outcome count differs from steps",
            schedule.id
        );
        replay_control_count += usize::from(schedule.control);
        step_count += schedule.steps.len();
        for expected in &schedule.expected_outcomes {
            *outcome_counts.entry(*expected).or_insert(0usize) += 1;
        }
        for step in &schedule.steps {
            for (name, value) in [
                ("worker_id", step.worker_id.as_str()),
                ("transaction_id", step.transaction_id.as_str()),
                ("receipt_id", step.receipt_id.as_str()),
                ("nonce", step.nonce.as_str()),
                ("s3_case_id", step.s3_case_id.as_str()),
            ] {
                ensure!(
                    !value.trim().is_empty(),
                    "{} step {name} is empty",
                    schedule.id
                );
            }
            ensure!(
                s3.contains_key(&step.s3_case_id),
                "{} references unknown S3 case {}",
                schedule.id,
                step.s3_case_id
            );
        }
    }
    ensure!(
        replay_control_count == 2,
        "replay corpus must contain two controls"
    );
    ensure!(step_count == 30, "replay corpus must contain 30 steps");
    ensure!(
        outcome_counts == replay.expected_step_outcome_counts,
        "replay labels do not match expected outcome counts"
    );
    Ok(())
}

fn validate_snapshot(snapshot: &ReplaySnapshot) -> anyhow::Result<()> {
    ensure!(
        !snapshot.snapshot_id.trim().is_empty(),
        "snapshot id is empty"
    );
    ensure!(snapshot.version > 0, "snapshot version is zero");
    ensure!(
        !snapshot.consumed.is_empty(),
        "snapshot has no committed records"
    );
    let mut nonces = BTreeSet::new();
    let mut transactions = BTreeSet::new();
    for record in &snapshot.consumed {
        ensure!(
            !record.transaction_id.trim().is_empty()
                && !record.receipt_id.trim().is_empty()
                && !record.nonce.trim().is_empty(),
            "snapshot contains an empty committed identity"
        );
        ensure!(
            nonces.insert(record.nonce.as_str()),
            "snapshot contains duplicate nonce"
        );
        ensure!(
            transactions.insert(record.transaction_id.as_str()),
            "snapshot contains duplicate transaction id"
        );
        ensure!(
            record.commit_version > 0 && record.commit_version <= snapshot.version,
            "snapshot commit version is invalid"
        );
    }
    ensure!(
        snapshot.snapshot_digest == snapshot_digest(snapshot),
        "snapshot digest differs from canonical state"
    );
    Ok(())
}

#[cfg(test)]
fn mutate_every_signed_event_field(event: &LifecycleEvent) -> Vec<LifecycleEvent> {
    let mut mutations = Vec::new();
    macro_rules! mutate_string {
        ($field:ident) => {{
            let mut changed = event.clone();
            changed.$field.push_str(":changed");
            mutations.push(changed);
        }};
    }
    macro_rules! mutate_u64 {
        ($field:ident) => {{
            let mut changed = event.clone();
            changed.$field += 1;
            mutations.push(changed);
        }};
    }
    mutate_string!(event_schema);
    mutate_string!(root_id);
    mutate_u64!(root_epoch);
    mutate_u64!(generation);
    mutate_u64!(sequence);
    mutate_string!(previous_event_digest);
    mutate_string!(action);
    mutate_string!(target_key_id);
    mutate_string!(replaces_key_id);
    mutate_u64!(target_not_before_unix);
    mutate_u64!(target_not_after_unix);
    mutate_u64!(effective_at_unix);
    mutate_string!(reason_code);
    mutate_string!(signer_id);
    mutate_string!(algorithm);
    mutations
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
enum KeyLifecycleState {
    Registered,
    Active,
    RotatedOut,
    Revoked,
    Compromised,
    Retired,
}

#[derive(Clone, Debug, Eq, PartialEq)]
struct KeyLifecycleRecord {
    state: KeyLifecycleState,
    not_before_unix: u64,
    not_after_unix: u64,
}

fn lifecycle_case_result(
    case: &LifecycleCase,
    derived_status: LifecycleStatus,
    reasons: impl IntoIterator<Item = &'static str>,
    signature_attempts: usize,
    signature_successes: usize,
    signature_failures: usize,
    active_key_id: Option<String>,
) -> LifecycleCaseResult {
    let mut reasons = reasons.into_iter().map(str::to_string).collect::<Vec<_>>();
    reasons.sort();
    reasons.dedup();
    LifecycleCaseResult {
        id: case.id.clone(),
        control: case.control,
        derived_status,
        expected_status: case.expected_status,
        status_matches: derived_status == case.expected_status,
        reasons_match: reasons == case.expected_reasons,
        reasons,
        expected_reasons: case.expected_reasons.clone(),
        signature_verification_attempt_count: signature_attempts,
        signature_verification_success_count: signature_successes,
        signature_verification_failure_count: signature_failures,
        active_key_id,
    }
}

fn event_metadata_matches(record: &KeyLifecycleRecord, event: &LifecycleEvent) -> bool {
    record.not_before_unix == event.target_not_before_unix
        && record.not_after_unix == event.target_not_after_unix
}

fn activation_validity_failure(event: &LifecycleEvent) -> Option<&'static str> {
    if event.effective_at_unix < event.target_not_before_unix {
        Some("activation_before_key_validity")
    } else if event.effective_at_unix > event.target_not_after_unix {
        Some("activation_after_key_validity")
    } else {
        None
    }
}

fn evaluate_lifecycle_case(
    anchor: &TrustAnchor,
    case: &LifecycleCase,
) -> anyhow::Result<LifecycleCaseResult> {
    if !case.verifier_available {
        return Ok(lifecycle_case_result(
            case,
            LifecycleStatus::Unavailable,
            ["independent_lifecycle_verifier_unavailable"],
            0,
            0,
            0,
            None,
        ));
    }

    let root_id_mismatch = case.trusted_checkpoint.root_id != anchor.root_id
        || case
            .events
            .iter()
            .any(|event| event.root_id != anchor.root_id);
    if root_id_mismatch {
        return Ok(lifecycle_case_result(
            case,
            LifecycleStatus::Untrusted,
            ["root_id_not_anchored"],
            0,
            0,
            0,
            None,
        ));
    }

    let future_root_epoch = case.trusted_checkpoint.root_epoch > anchor.trusted_root_epoch
        || case
            .events
            .iter()
            .any(|event| event.root_epoch > anchor.trusted_root_epoch);
    if future_root_epoch {
        return Ok(lifecycle_case_result(
            case,
            LifecycleStatus::Untrusted,
            ["root_epoch_not_anchored"],
            0,
            0,
            0,
            None,
        ));
    }

    let old_root_epoch = case.trusted_checkpoint.root_epoch < anchor.trusted_root_epoch
        || case
            .events
            .iter()
            .any(|event| event.root_epoch < anchor.trusted_root_epoch);
    if old_root_epoch {
        return Ok(lifecycle_case_result(
            case,
            LifecycleStatus::Rollback,
            ["root_epoch_rollback"],
            0,
            0,
            0,
            None,
        ));
    }

    if case.trusted_checkpoint.registry_generation < anchor.minimum_registry_generation {
        return Ok(lifecycle_case_result(
            case,
            LifecycleStatus::Rollback,
            ["registry_generation_rollback"],
            0,
            0,
            0,
            None,
        ));
    }

    let position_discontinuity = case.events.iter().enumerate().any(|(index, event)| {
        let expected = u64::try_from(index + 1).expect("fixture event position fits u64");
        event.sequence != expected || event.generation != expected
    }) || case
        .events
        .last()
        .is_none_or(|event| event.generation != case.trusted_checkpoint.registry_generation);
    if position_discontinuity {
        return Ok(lifecycle_case_result(
            case,
            LifecycleStatus::Forked,
            ["journal_sequence_discontinuity"],
            0,
            0,
            0,
            None,
        ));
    }

    let mut previous_digest = anchor.genesis_digest.clone();
    let mut computed_digests = Vec::with_capacity(case.events.len());
    for event in &case.events {
        if event.previous_event_digest != previous_digest {
            return Ok(lifecycle_case_result(
                case,
                LifecycleStatus::Forked,
                ["previous_event_digest_mismatch"],
                0,
                0,
                0,
                None,
            ));
        }
        previous_digest = sha256_digest(&canonical_event_bytes(event));
        computed_digests.push(previous_digest.clone());
    }
    if case.trusted_checkpoint.expected_head_digest != previous_digest {
        return Ok(lifecycle_case_result(
            case,
            LifecycleStatus::Forked,
            ["checkpoint_head_digest_mismatch"],
            0,
            0,
            0,
            None,
        ));
    }

    let mut invalid_reasons = BTreeSet::new();
    for (event, computed_digest) in case.events.iter().zip(&computed_digests) {
        if event.event_schema != anchor.accepted_event_schema {
            invalid_reasons.insert("event_schema_mismatch");
        }
        if !is_sha256_digest(&event.event_digest) {
            invalid_reasons.insert("event_digest_encoding_invalid");
        } else if event.event_digest != *computed_digest {
            invalid_reasons.insert("event_digest_mismatch");
        }
        if STANDARD.decode(&event.signature_base64).is_err() {
            invalid_reasons.insert("event_signature_encoding_invalid");
        }
        if event.target_not_before_unix >= event.target_not_after_unix {
            invalid_reasons.insert("invalid_key_metadata");
        }
    }
    if !invalid_reasons.is_empty() {
        return Ok(lifecycle_case_result(
            case,
            LifecycleStatus::Invalid,
            invalid_reasons,
            0,
            0,
            0,
            None,
        ));
    }

    let signers = anchor
        .signers
        .iter()
        .map(|signer| (signer.signer_id.as_str(), signer))
        .collect::<BTreeMap<_, _>>();
    let mut untrusted_reasons = BTreeSet::new();
    for event in &case.events {
        match signers.get(event.signer_id.as_str()) {
            None => {
                untrusted_reasons.insert("signer_not_anchored");
            }
            Some(signer) => {
                if event.algorithm != anchor.accepted_algorithm
                    || signer.algorithm != anchor.accepted_algorithm
                {
                    untrusted_reasons.insert("signer_algorithm_not_accepted");
                }
                if signer.role != anchor.required_signer_role {
                    untrusted_reasons.insert("signer_role_not_authorized");
                }
            }
        }
    }
    if !untrusted_reasons.is_empty() {
        return Ok(lifecycle_case_result(
            case,
            LifecycleStatus::Untrusted,
            untrusted_reasons,
            0,
            0,
            0,
            None,
        ));
    }

    let mut signature_attempts = 0usize;
    let mut signature_successes = 0usize;
    let mut signature_failures = 0usize;
    let mut revoked_signer_used = false;
    for event in &case.events {
        let signer = signers
            .get(event.signer_id.as_str())
            .context("validated signer disappeared")?;
        let public_key = STANDARD
            .decode(&signer.public_key_base64)
            .context("validated signer public key became malformed")?;
        let signature = STANDARD
            .decode(&event.signature_base64)
            .context("validated event signature became malformed")?;
        signature_attempts += 1;
        if UnparsedPublicKey::new(&ED25519, public_key)
            .verify(&canonical_event_bytes(event), &signature)
            .is_ok()
        {
            signature_successes += 1;
            revoked_signer_used |= signer.revoked;
        } else {
            signature_failures += 1;
        }
    }
    if signature_failures > 0 {
        return Ok(lifecycle_case_result(
            case,
            LifecycleStatus::Invalid,
            ["event_signature_verification_failed"],
            signature_attempts,
            signature_successes,
            signature_failures,
            None,
        ));
    }
    if revoked_signer_used {
        return Ok(lifecycle_case_result(
            case,
            LifecycleStatus::Revoked,
            ["lifecycle_signer_revoked"],
            signature_attempts,
            signature_successes,
            signature_failures,
            None,
        ));
    }

    let mut keys = BTreeMap::<String, KeyLifecycleRecord>::new();
    for event in &case.events {
        let rejection = match event.action.as_str() {
            "register" => {
                if !event.replaces_key_id.is_empty() || keys.contains_key(&event.target_key_id) {
                    Some((LifecycleStatus::Invalid, "invalid_key_transition"))
                } else {
                    keys.insert(
                        event.target_key_id.clone(),
                        KeyLifecycleRecord {
                            state: KeyLifecycleState::Registered,
                            not_before_unix: event.target_not_before_unix,
                            not_after_unix: event.target_not_after_unix,
                        },
                    );
                    None
                }
            }
            "activate" => match keys.get(&event.target_key_id).cloned() {
                None => Some((LifecycleStatus::Invalid, "invalid_key_transition")),
                Some(record) if !event_metadata_matches(&record, event) => {
                    Some((LifecycleStatus::Invalid, "invalid_key_metadata"))
                }
                Some(record)
                    if matches!(
                        record.state,
                        KeyLifecycleState::Revoked
                            | KeyLifecycleState::Compromised
                            | KeyLifecycleState::Retired
                            | KeyLifecycleState::RotatedOut
                    ) =>
                {
                    Some((
                        LifecycleStatus::Revoked,
                        "retired_or_revoked_key_resurrection",
                    ))
                }
                Some(record) if record.state != KeyLifecycleState::Registered => {
                    Some((LifecycleStatus::Invalid, "invalid_key_transition"))
                }
                Some(_) if !event.replaces_key_id.is_empty() => {
                    Some((LifecycleStatus::Invalid, "invalid_key_transition"))
                }
                Some(_) => {
                    if let Some(reason) = activation_validity_failure(event) {
                        Some((LifecycleStatus::Stale, reason))
                    } else if keys
                        .values()
                        .any(|key| key.state == KeyLifecycleState::Active)
                    {
                        Some((LifecycleStatus::Ambiguous, "active_key_overlap"))
                    } else {
                        keys.get_mut(&event.target_key_id)
                            .context("activation target disappeared")?
                            .state = KeyLifecycleState::Active;
                        None
                    }
                }
            },
            "rotate" => match keys.get(&event.target_key_id).cloned() {
                None => Some((LifecycleStatus::Invalid, "invalid_key_transition")),
                Some(record) if !event_metadata_matches(&record, event) => {
                    Some((LifecycleStatus::Invalid, "invalid_key_metadata"))
                }
                Some(record)
                    if matches!(
                        record.state,
                        KeyLifecycleState::Revoked
                            | KeyLifecycleState::Compromised
                            | KeyLifecycleState::Retired
                            | KeyLifecycleState::RotatedOut
                    ) =>
                {
                    Some((
                        LifecycleStatus::Revoked,
                        "retired_or_revoked_key_resurrection",
                    ))
                }
                Some(record) if record.state != KeyLifecycleState::Registered => {
                    Some((LifecycleStatus::Invalid, "invalid_key_transition"))
                }
                Some(_)
                    if event.replaces_key_id.is_empty()
                        || event.replaces_key_id == event.target_key_id =>
                {
                    Some((LifecycleStatus::Invalid, "invalid_key_transition"))
                }
                Some(_) => match keys.get(&event.replaces_key_id).cloned() {
                    None => Some((LifecycleStatus::Invalid, "invalid_key_transition")),
                    Some(predecessor)
                        if !matches!(
                            predecessor.state,
                            KeyLifecycleState::Active | KeyLifecycleState::Compromised
                        ) =>
                    {
                        Some((LifecycleStatus::Invalid, "invalid_key_transition"))
                    }
                    Some(_) => {
                        if let Some(reason) = activation_validity_failure(event) {
                            Some((LifecycleStatus::Stale, reason))
                        } else if keys.iter().any(|(key_id, key)| {
                            key_id != &event.replaces_key_id
                                && key.state == KeyLifecycleState::Active
                        }) {
                            Some((LifecycleStatus::Ambiguous, "active_key_overlap"))
                        } else {
                            let predecessor = keys
                                .get_mut(&event.replaces_key_id)
                                .context("rotation predecessor disappeared")?;
                            if predecessor.state == KeyLifecycleState::Active {
                                predecessor.state = KeyLifecycleState::RotatedOut;
                            }
                            keys.get_mut(&event.target_key_id)
                                .context("rotation target disappeared")?
                                .state = KeyLifecycleState::Active;
                            None
                        }
                    }
                },
            },
            "revoke" => match keys.get(&event.target_key_id).cloned() {
                None => Some((LifecycleStatus::Invalid, "invalid_key_transition")),
                Some(record) if !event_metadata_matches(&record, event) => {
                    Some((LifecycleStatus::Invalid, "invalid_key_metadata"))
                }
                Some(record)
                    if matches!(
                        record.state,
                        KeyLifecycleState::Revoked | KeyLifecycleState::Retired
                    ) =>
                {
                    Some((LifecycleStatus::Invalid, "invalid_key_transition"))
                }
                Some(_) if !event.replaces_key_id.is_empty() => {
                    Some((LifecycleStatus::Invalid, "invalid_key_transition"))
                }
                Some(_) => {
                    keys.get_mut(&event.target_key_id)
                        .context("revocation target disappeared")?
                        .state = KeyLifecycleState::Revoked;
                    None
                }
            },
            "quarantine" => match keys.get(&event.target_key_id).cloned() {
                None => Some((LifecycleStatus::Invalid, "invalid_key_transition")),
                Some(record) if !event_metadata_matches(&record, event) => {
                    Some((LifecycleStatus::Invalid, "invalid_key_metadata"))
                }
                Some(record) if record.state != KeyLifecycleState::Active => {
                    Some((LifecycleStatus::Invalid, "invalid_key_transition"))
                }
                Some(_) if !event.replaces_key_id.is_empty() => {
                    Some((LifecycleStatus::Invalid, "invalid_key_transition"))
                }
                Some(_) => {
                    keys.get_mut(&event.target_key_id)
                        .context("quarantine target disappeared")?
                        .state = KeyLifecycleState::Compromised;
                    None
                }
            },
            "retire" => match keys.get(&event.target_key_id).cloned() {
                None => Some((LifecycleStatus::Invalid, "invalid_key_transition")),
                Some(record) if !event_metadata_matches(&record, event) => {
                    Some((LifecycleStatus::Invalid, "invalid_key_metadata"))
                }
                Some(record)
                    if !matches!(
                        record.state,
                        KeyLifecycleState::Revoked | KeyLifecycleState::Compromised
                    ) =>
                {
                    Some((LifecycleStatus::Invalid, "invalid_key_transition"))
                }
                Some(_) if !event.replaces_key_id.is_empty() => {
                    Some((LifecycleStatus::Invalid, "invalid_key_transition"))
                }
                Some(_) => {
                    keys.get_mut(&event.target_key_id)
                        .context("retirement target disappeared")?
                        .state = KeyLifecycleState::Retired;
                    None
                }
            },
            _ => Some((LifecycleStatus::Invalid, "invalid_key_transition")),
        };

        if let Some((status, reason)) = rejection {
            return Ok(lifecycle_case_result(
                case,
                status,
                [reason],
                signature_attempts,
                signature_successes,
                signature_failures,
                None,
            ));
        }
    }

    let active_keys = keys
        .iter()
        .filter(|(_, record)| record.state == KeyLifecycleState::Active)
        .map(|(key_id, _)| key_id.clone())
        .collect::<Vec<_>>();
    if active_keys.len() > 1 {
        return Ok(lifecycle_case_result(
            case,
            LifecycleStatus::Ambiguous,
            ["active_key_overlap"],
            signature_attempts,
            signature_successes,
            signature_failures,
            None,
        ));
    }
    let Some(active_key_id) = active_keys.first().cloned() else {
        return Ok(lifecycle_case_result(
            case,
            LifecycleStatus::Invalid,
            ["invalid_key_transition"],
            signature_attempts,
            signature_successes,
            signature_failures,
            None,
        ));
    };
    if active_key_id != case.trusted_checkpoint.expected_active_key_id {
        return Ok(lifecycle_case_result(
            case,
            LifecycleStatus::Invalid,
            ["checkpoint_active_key_mismatch"],
            signature_attempts,
            signature_successes,
            signature_failures,
            Some(active_key_id),
        ));
    }
    let active_key = keys
        .get(&active_key_id)
        .context("derived active key disappeared")?;
    if case.trusted_checkpoint.evaluation_time_unix < active_key.not_before_unix {
        return Ok(lifecycle_case_result(
            case,
            LifecycleStatus::Stale,
            ["active_key_before_validity"],
            signature_attempts,
            signature_successes,
            signature_failures,
            Some(active_key_id),
        ));
    }
    if case.trusted_checkpoint.evaluation_time_unix > active_key.not_after_unix {
        return Ok(lifecycle_case_result(
            case,
            LifecycleStatus::Stale,
            ["active_key_after_validity"],
            signature_attempts,
            signature_successes,
            signature_failures,
            Some(active_key_id),
        ));
    }

    Ok(lifecycle_case_result(
        case,
        LifecycleStatus::Current,
        [],
        signature_attempts,
        signature_successes,
        signature_failures,
        Some(active_key_id),
    ))
}

fn evaluate_lifecycle_suite(
    anchor: &TrustAnchor,
    journals: &LifecycleCorpus,
) -> anyhow::Result<LifecycleSuite> {
    let results = journals
        .cases
        .iter()
        .map(|case| evaluate_lifecycle_case(anchor, case))
        .collect::<anyhow::Result<Vec<_>>>()?;
    let mut counts = BTreeMap::new();
    for result in &results {
        *counts.entry(result.derived_status).or_insert(0usize) += 1;
    }
    let count = |status| counts.get(&status).copied().unwrap_or(0);
    let signature_verification_attempt_count = results
        .iter()
        .map(|result| result.signature_verification_attempt_count)
        .sum();
    let signature_verification_success_count = results
        .iter()
        .map(|result| result.signature_verification_success_count)
        .sum();
    let signature_verification_failure_count = results
        .iter()
        .map(|result| result.signature_verification_failure_count)
        .sum();
    let false_current_count = results
        .iter()
        .filter(|result| !result.control && result.derived_status == LifecycleStatus::Current)
        .count();
    let control_false_reject_count = results
        .iter()
        .filter(|result| result.control && result.derived_status != LifecycleStatus::Current)
        .count();
    let status_mismatch_count = results
        .iter()
        .filter(|result| !result.status_matches)
        .count();
    let reason_mismatch_count = results
        .iter()
        .filter(|result| !result.reasons_match)
        .count();
    let passed = counts == journals.expected_distribution
        && false_current_count == 0
        && control_false_reject_count == 0
        && status_mismatch_count == 0
        && reason_mismatch_count == 0;

    Ok(LifecycleSuite {
        status: if passed {
            "pass_offline_lifecycle_preflight_only"
        } else {
            "fail_closed_offline_lifecycle_preflight"
        },
        case_count: results.len(),
        current_count: count(LifecycleStatus::Current),
        invalid_count: count(LifecycleStatus::Invalid),
        untrusted_count: count(LifecycleStatus::Untrusted),
        rollback_count: count(LifecycleStatus::Rollback),
        forked_count: count(LifecycleStatus::Forked),
        revoked_count: count(LifecycleStatus::Revoked),
        stale_count: count(LifecycleStatus::Stale),
        ambiguous_count: count(LifecycleStatus::Ambiguous),
        unavailable_count: count(LifecycleStatus::Unavailable),
        signature_verification_attempt_count,
        signature_verification_success_count,
        signature_verification_failure_count,
        false_current_count,
        control_false_reject_count,
        status_mismatch_count,
        reason_mismatch_count,
        results,
    })
}

fn evaluate_replay_schedule(
    replay: &ReplayCorpus,
    schedule: &ReplaySchedule,
    lifecycle: &LifecycleSuite,
    s3: &S3CaseMap,
) -> anyhow::Result<ReplayScheduleResult> {
    let lifecycle_current = lifecycle
        .results
        .iter()
        .find(|result| result.id == schedule.lifecycle_case_id)
        .with_context(|| format!("missing lifecycle case {}", schedule.lifecycle_case_id))?
        .derived_status
        == LifecycleStatus::Current;
    let mut candidate = replay.initial_snapshot.clone();
    let mut steps = Vec::with_capacity(schedule.steps.len());

    for (index, step) in schedule.steps.iter().enumerate() {
        let version_before = candidate.version;
        let expected_outcome = schedule
            .expected_outcomes
            .get(index)
            .copied()
            .context("replay expected outcome disappeared")?;
        let mut reviewable = false;
        let outcome = if !lifecycle_current {
            ReplayOutcome::LifecycleBlocked
        } else if s3.get(&step.s3_case_id) != Some(&S3Status::Verified) {
            ReplayOutcome::ReceiptIneligible
        } else if candidate.consumed.iter().any(|record| {
            record.nonce == step.nonce
                && record.transaction_id == step.transaction_id
                && record.receipt_id == step.receipt_id
        }) {
            reviewable = true;
            ReplayOutcome::AlreadyCommitted
        } else if candidate
            .consumed
            .iter()
            .any(|record| record.nonce == step.nonce)
        {
            ReplayOutcome::NonceReplayed
        } else if candidate
            .consumed
            .iter()
            .any(|record| record.transaction_id == step.transaction_id)
        {
            ReplayOutcome::TransactionIdentityConflict
        } else if step.expected_version != candidate.version {
            ReplayOutcome::VersionConflict
        } else {
            match step.mode {
                ReplayMode::PrepareOnly => ReplayOutcome::PreparedNotCommitted,
                ReplayMode::CrashBeforeCommit => ReplayOutcome::CrashedBeforeCommit,
                ReplayMode::Commit | ReplayMode::CommitAckLost => {
                    candidate.version += 1;
                    candidate.consumed.push(ConsumedRecord {
                        transaction_id: step.transaction_id.clone(),
                        receipt_id: step.receipt_id.clone(),
                        nonce: step.nonce.clone(),
                        commit_version: candidate.version,
                    });
                    candidate
                        .consumed
                        .sort_by(|left, right| left.nonce.cmp(&right.nonce));
                    candidate.snapshot_digest = snapshot_digest(&candidate);
                    if step.mode == ReplayMode::Commit {
                        reviewable = true;
                        ReplayOutcome::Committed
                    } else {
                        ReplayOutcome::CommitAckLost
                    }
                }
            }
        };
        steps.push(ReplayStepResult {
            worker_id: step.worker_id.clone(),
            transaction_id: step.transaction_id.clone(),
            receipt_id: step.receipt_id.clone(),
            nonce: step.nonce.clone(),
            s3_case_id: step.s3_case_id.clone(),
            version_before,
            version_after: candidate.version,
            outcome,
            expected_outcome,
            outcome_matches: outcome == expected_outcome,
            reviewable_after_atomic_consume: reviewable,
        });
    }
    validate_snapshot(&candidate)?;
    let reviewable_count = steps
        .iter()
        .filter(|step| step.reviewable_after_atomic_consume)
        .count();
    let final_state_matches = candidate.version == schedule.expected_final_version
        && candidate.consumed.len() == schedule.expected_consumed_count
        && reviewable_count == schedule.expected_reviewable_count;

    Ok(ReplayScheduleResult {
        id: schedule.id.clone(),
        control: schedule.control,
        lifecycle_case_id: schedule.lifecycle_case_id.clone(),
        steps,
        final_version: candidate.version,
        expected_final_version: schedule.expected_final_version,
        final_consumed_count: candidate.consumed.len(),
        expected_consumed_count: schedule.expected_consumed_count,
        reviewable_count,
        expected_reviewable_count: schedule.expected_reviewable_count,
        final_snapshot_digest: candidate.snapshot_digest,
        final_state_matches,
    })
}

fn evaluate_replay_suite(
    replay: &ReplayCorpus,
    lifecycle: &LifecycleSuite,
    s3: &S3CaseMap,
) -> anyhow::Result<ReplaySuite> {
    let results = replay
        .schedules
        .iter()
        .map(|schedule| evaluate_replay_schedule(replay, schedule, lifecycle, s3))
        .collect::<anyhow::Result<Vec<_>>>()?;
    let mut counts = BTreeMap::new();
    for step in results.iter().flat_map(|result| &result.steps) {
        *counts.entry(step.outcome).or_insert(0usize) += 1;
    }
    let count = |outcome| counts.get(&outcome).copied().unwrap_or(0);
    let step_count = results.iter().map(|result| result.steps.len()).sum();
    let reviewable_count = results.iter().map(|result| result.reviewable_count).sum();
    let outcome_mismatch_count = results
        .iter()
        .flat_map(|result| &result.steps)
        .filter(|step| !step.outcome_matches)
        .count();
    let final_state_mismatch_count = results
        .iter()
        .filter(|result| !result.final_state_matches)
        .count();
    let false_reviewable_count = results
        .iter()
        .flat_map(|result| &result.steps)
        .filter(|step| {
            step.reviewable_after_atomic_consume
                && !matches!(
                    step.outcome,
                    ReplayOutcome::Committed | ReplayOutcome::AlreadyCommitted
                )
        })
        .count();
    let passed = counts == replay.expected_step_outcome_counts
        && reviewable_count == 7
        && outcome_mismatch_count == 0
        && final_state_mismatch_count == 0
        && false_reviewable_count == 0;

    Ok(ReplaySuite {
        status: if passed {
            "pass_offline_atomic_replay_preflight_only"
        } else {
            "fail_closed_offline_atomic_replay_preflight"
        },
        schedule_count: results.len(),
        step_count,
        committed_count: count(ReplayOutcome::Committed),
        already_committed_count: count(ReplayOutcome::AlreadyCommitted),
        nonce_replayed_count: count(ReplayOutcome::NonceReplayed),
        version_conflict_count: count(ReplayOutcome::VersionConflict),
        prepared_not_committed_count: count(ReplayOutcome::PreparedNotCommitted),
        crashed_before_commit_count: count(ReplayOutcome::CrashedBeforeCommit),
        commit_ack_lost_count: count(ReplayOutcome::CommitAckLost),
        transaction_identity_conflict_count: count(ReplayOutcome::TransactionIdentityConflict),
        receipt_ineligible_count: count(ReplayOutcome::ReceiptIneligible),
        lifecycle_blocked_count: count(ReplayOutcome::LifecycleBlocked),
        reviewable_count,
        outcome_mismatch_count,
        final_state_mismatch_count,
        false_reviewable_count,
        results,
    })
}

fn evaluate_suite(
    anchor: &TrustAnchor,
    journals: &LifecycleCorpus,
    replay: &ReplayCorpus,
    sources: &EmbeddedSources,
    anchor_bytes: &[u8],
    journal_bytes: &[u8],
    replay_bytes: &[u8],
    s3_receipt_bytes: &[u8],
) -> anyhow::Result<Report> {
    ensure!(
        sha256(anchor_bytes) == ANCHOR_SHA256,
        "S4 anchor hash changed"
    );
    ensure!(
        sha256(journal_bytes) == JOURNAL_SHA256,
        "S4 journal hash changed"
    );
    ensure!(
        sha256(replay_bytes) == REPLAY_SHA256,
        "S4 replay hash changed"
    );
    let s3 = load_s3_case_index(s3_receipt_bytes)?;
    validate_inputs(anchor, journals, replay, sources, &s3)?;
    let lifecycle = evaluate_lifecycle_suite(anchor, journals)?;
    let replay_suite = evaluate_replay_suite(replay, &lifecycle, &s3)?;
    let passed = lifecycle.status == "pass_offline_lifecycle_preflight_only"
        && replay_suite.status == "pass_offline_atomic_replay_preflight_only"
        && !anchor.private_key_present
        && !anchor.production_trust_root
        && !anchor.root_rotation_proven
        && replay.contract.candidate_state_only
        && !replay.contract.persistent_state_mutation
        && !replay.contract.runtime_consumer_enabled
        && !replay.contract.receipt_identity_end_to_end_reverified;
    let source_sha256 = sources
        .iter()
        .map(|(id, source)| ((*id).to_string(), sha256(source.bytes)))
        .collect();

    Ok(Report {
        schema: REPORT_SCHEMA,
        status: if passed {
            "pass_offline_lifecycle_and_atomic_replay_preflight_only"
        } else {
            "fail_closed_offline_lifecycle_and_atomic_replay_preflight"
        },
        latest_master_commit: LATEST_MASTER_COMMIT,
        s3_result_commit: S3_RESULT_COMMIT,
        s4_lineage_merge_commit: S4_LINEAGE_MERGE_COMMIT,
        anchor_sha256: sha256(anchor_bytes),
        journal_sha256: sha256(journal_bytes),
        replay_sha256: sha256(replay_bytes),
        source_sha256,
        crypto_verifier: "ring 0.17.14 Ed25519 verification only",
        public_test_keys_only: true,
        private_signing_material_embedded: false,
        root_anchor_fixture_only: true,
        candidate_state_persisted: false,
        runtime_consumer_enabled: false,
        receipt_identity_end_to_end_reverified: false,
        lifecycle,
        replay: replay_suite,
        authority: Authority::default(),
    })
}

fn main() -> anyhow::Result<()> {
    let anchor = load_anchor(ANCHOR_BYTES)?;
    let journals = load_journals(JOURNAL_BYTES)?;
    let replay = load_replay(REPLAY_BYTES)?;
    let sources = frozen_sources();
    let report = evaluate_suite(
        &anchor,
        &journals,
        &replay,
        &sources,
        ANCHOR_BYTES,
        JOURNAL_BYTES,
        REPLAY_BYTES,
        S3_SIGNED_RECEIPTS_BYTES,
    )?;
    println!("{}", serde_json::to_string_pretty(&report)?);
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    fn frozen_anchor() -> TrustAnchor {
        load_anchor(ANCHOR_BYTES).expect("anchor parses")
    }

    fn frozen_journals() -> LifecycleCorpus {
        load_journals(JOURNAL_BYTES).expect("journals parse")
    }

    fn frozen_replay() -> ReplayCorpus {
        load_replay(REPLAY_BYTES).expect("replay parses")
    }

    #[test]
    fn frozen_lifecycle_distribution_and_reasons_are_exact() {
        let suite = evaluate_lifecycle_suite(&frozen_anchor(), &frozen_journals())
            .expect("lifecycle suite evaluates");

        assert_eq!(suite.case_count, 21);
        assert_eq!(suite.current_count, 2);
        assert_eq!(suite.invalid_count, 3);
        assert_eq!(suite.untrusted_count, 3);
        assert_eq!(suite.rollback_count, 2);
        assert_eq!(suite.forked_count, 5);
        assert_eq!(suite.revoked_count, 2);
        assert_eq!(suite.stale_count, 2);
        assert_eq!(suite.ambiguous_count, 1);
        assert_eq!(suite.unavailable_count, 1);
        assert_eq!(suite.status_mismatch_count, 0);
        assert_eq!(suite.reason_mismatch_count, 0);
        assert_eq!(suite.false_current_count, 0);
        assert_eq!(suite.control_false_reject_count, 0);
    }

    #[test]
    fn real_signature_path_and_lifecycle_boundaries_are_exact() {
        let suite = evaluate_lifecycle_suite(&frozen_anchor(), &frozen_journals())
            .expect("lifecycle suite evaluates");

        for (id, status, reason) in [
            (
                "event_signature_tamper_rejected",
                LifecycleStatus::Invalid,
                "event_signature_verification_failed",
            ),
            (
                "audit_only_signer_rejected",
                LifecycleStatus::Untrusted,
                "signer_role_not_authorized",
            ),
            (
                "revoked_lifecycle_signer_rejected",
                LifecycleStatus::Revoked,
                "lifecycle_signer_revoked",
            ),
            (
                "retired_key_resurrection_rejected",
                LifecycleStatus::Revoked,
                "retired_or_revoked_key_resurrection",
            ),
            (
                "overlapping_active_keys_rejected",
                LifecycleStatus::Ambiguous,
                "active_key_overlap",
            ),
        ] {
            let result = suite
                .results
                .iter()
                .find(|result| result.id == id)
                .expect("case exists");
            assert_eq!(result.derived_status, status);
            assert_eq!(result.reasons, vec![reason]);
        }

        assert!(suite
            .results
            .iter()
            .filter(|result| result.control)
            .all(|result| {
                result.derived_status == LifecycleStatus::Current
                    && result.signature_verification_success_count > 0
            }));
    }

    #[test]
    fn frozen_replay_schedules_are_exact_and_single_winner() {
        let anchor = frozen_anchor();
        let journals = frozen_journals();
        let lifecycle = evaluate_lifecycle_suite(&anchor, &journals).expect("lifecycle evaluates");
        let replay = frozen_replay();
        let s3 = load_s3_case_index(S3_SIGNED_RECEIPTS_BYTES).expect("S3 index parses");
        let suite = evaluate_replay_suite(&replay, &lifecycle, &s3).expect("replay evaluates");

        assert_eq!(suite.schedule_count, 26);
        assert_eq!(suite.step_count, 30);
        assert_eq!(suite.committed_count, 4);
        assert_eq!(suite.already_committed_count, 3);
        assert_eq!(suite.nonce_replayed_count, 3);
        assert_eq!(suite.version_conflict_count, 1);
        assert_eq!(suite.prepared_not_committed_count, 1);
        assert_eq!(suite.crashed_before_commit_count, 1);
        assert_eq!(suite.commit_ack_lost_count, 1);
        assert_eq!(suite.transaction_identity_conflict_count, 1);
        assert_eq!(suite.receipt_ineligible_count, 7);
        assert_eq!(suite.lifecycle_blocked_count, 8);
        assert_eq!(suite.reviewable_count, 7);
        assert_eq!(suite.outcome_mismatch_count, 0);
        assert_eq!(suite.final_state_mismatch_count, 0);
        assert_eq!(suite.false_reviewable_count, 0);

        for id in [
            "competing_receipts_first_wins",
            "competing_receipts_reverse_wins",
        ] {
            let schedule = suite
                .results
                .iter()
                .find(|result| result.id == id)
                .expect("competition schedule exists");
            assert_eq!(
                schedule
                    .steps
                    .iter()
                    .filter(|step| step.outcome == ReplayOutcome::Committed)
                    .count(),
                1
            );
            assert_eq!(
                schedule
                    .steps
                    .iter()
                    .filter(|step| step.outcome == ReplayOutcome::NonceReplayed)
                    .count(),
                1
            );
        }
    }

    #[test]
    fn expected_labels_are_comparison_only() {
        let anchor = frozen_anchor();
        let journals = frozen_journals();
        let baseline =
            evaluate_lifecycle_case(&anchor, &journals.cases[0]).expect("baseline evaluates");
        let mut relabeled_journals = journals.clone();
        relabeled_journals.cases[0].expected_status = LifecycleStatus::Invalid;
        relabeled_journals.cases[0].expected_reasons = vec!["invented_reason".to_string()];
        let relabeled = evaluate_lifecycle_case(&anchor, &relabeled_journals.cases[0])
            .expect("relabeled case evaluates");
        assert_eq!(baseline.derived_status, relabeled.derived_status);
        assert_eq!(baseline.reasons, relabeled.reasons);

        let lifecycle = evaluate_lifecycle_suite(&anchor, &journals).expect("lifecycle evaluates");
        let s3 = load_s3_case_index(S3_SIGNED_RECEIPTS_BYTES).expect("S3 index parses");
        let replay = frozen_replay();
        let original = evaluate_replay_schedule(&replay, &replay.schedules[0], &lifecycle, &s3)
            .expect("schedule evaluates");
        let mut relabeled_replay = replay.clone();
        relabeled_replay.schedules[0].expected_outcomes = vec![ReplayOutcome::NonceReplayed];
        let changed = evaluate_replay_schedule(
            &relabeled_replay,
            &relabeled_replay.schedules[0],
            &lifecycle,
            &s3,
        )
        .expect("relabeled schedule evaluates");
        assert_eq!(original.steps[0].outcome, changed.steps[0].outcome);
        assert_ne!(changed.steps[0].outcome, changed.steps[0].expected_outcome);
    }

    #[test]
    fn all_fifteen_event_fields_change_canonical_bytes() {
        let baseline = frozen_journals().cases[0].events[0].clone();
        let baseline_bytes = canonical_event_bytes(&baseline);
        let mutations = mutate_every_signed_event_field(&baseline);

        assert_eq!(mutations.len(), 15);
        assert!(mutations
            .iter()
            .all(|event| canonical_event_bytes(event) != baseline_bytes));
    }

    #[test]
    fn malformed_sources_journals_and_snapshots_fail_closed() {
        let anchor = frozen_anchor();
        let journals = frozen_journals();
        let replay = frozen_replay();
        let sources = frozen_sources();
        let s3 = load_s3_case_index(S3_SIGNED_RECEIPTS_BYTES).expect("S3 index parses");

        let mut duplicate_signer = anchor.clone();
        duplicate_signer.signers[1].signer_id = duplicate_signer.signers[0].signer_id.clone();
        assert!(validate_inputs(&duplicate_signer, &journals, &replay, &sources, &s3).is_err());

        let mut invalid_public_key = anchor.clone();
        invalid_public_key.signers[0].public_key_base64 = "not-base64".to_string();
        assert!(validate_inputs(&invalid_public_key, &journals, &replay, &sources, &s3).is_err());

        let mut duplicate_case = journals.clone();
        duplicate_case.cases[1].id = duplicate_case.cases[0].id.clone();
        assert!(validate_inputs(&anchor, &duplicate_case, &replay, &sources, &s3).is_err());

        let mut stale_source = journals.clone();
        stale_source.source.files[0].sha256 = "0".repeat(64);
        assert!(validate_inputs(&anchor, &stale_source, &replay, &sources, &s3).is_err());

        let mut duplicate_nonce = replay.clone();
        duplicate_nonce
            .initial_snapshot
            .consumed
            .push(duplicate_nonce.initial_snapshot.consumed[0].clone());
        assert!(validate_inputs(&anchor, &journals, &duplicate_nonce, &sources, &s3).is_err());

        let mut stale_digest = replay.clone();
        stale_digest.initial_snapshot.snapshot_digest = "sha256:".to_string() + &"0".repeat(64);
        assert!(validate_inputs(&anchor, &journals, &stale_digest, &sources, &s3).is_err());

        let mut duplicate_schedule = replay.clone();
        duplicate_schedule.schedules[1].id = duplicate_schedule.schedules[0].id.clone();
        assert!(validate_inputs(&anchor, &journals, &duplicate_schedule, &sources, &s3).is_err());
    }

    #[test]
    fn crash_windows_and_composition_boundary_are_explicit() {
        let anchor = frozen_anchor();
        let journals = frozen_journals();
        let lifecycle = evaluate_lifecycle_suite(&anchor, &journals).expect("lifecycle evaluates");
        let replay = frozen_replay();
        let s3 = load_s3_case_index(S3_SIGNED_RECEIPTS_BYTES).expect("S3 index parses");
        let suite = evaluate_replay_suite(&replay, &lifecycle, &s3).expect("replay evaluates");

        let before = suite
            .results
            .iter()
            .find(|result| result.id == "crash_before_commit_not_consumed")
            .expect("before-commit crash exists");
        assert_eq!(before.final_version, 41);
        assert_eq!(before.final_consumed_count, 1);
        assert!(!before.steps[0].reviewable_after_atomic_consume);

        let recovered = suite
            .results
            .iter()
            .find(|result| result.id == "ack_lost_then_idempotent_recovery")
            .expect("ack-loss schedule exists");
        assert_eq!(recovered.steps[0].outcome, ReplayOutcome::CommitAckLost);
        assert!(!recovered.steps[0].reviewable_after_atomic_consume);
        assert_eq!(recovered.steps[1].outcome, ReplayOutcome::AlreadyCommitted);
        assert!(recovered.steps[1].reviewable_after_atomic_consume);
        assert!(!replay.contract.receipt_identity_end_to_end_reverified);
    }

    #[test]
    fn report_is_deterministic_immutable_and_non_authorizing() {
        let anchor = frozen_anchor();
        let journals = frozen_journals();
        let replay = frozen_replay();
        let sources = frozen_sources();
        let anchor_before = anchor.clone();
        let journals_before = journals.clone();
        let replay_before = replay.clone();

        let first = evaluate_suite(
            &anchor,
            &journals,
            &replay,
            &sources,
            ANCHOR_BYTES,
            JOURNAL_BYTES,
            REPLAY_BYTES,
            S3_SIGNED_RECEIPTS_BYTES,
        )
        .expect("first evaluation");
        let second = evaluate_suite(
            &anchor,
            &journals,
            &replay,
            &sources,
            ANCHOR_BYTES,
            JOURNAL_BYTES,
            REPLAY_BYTES,
            S3_SIGNED_RECEIPTS_BYTES,
        )
        .expect("second evaluation");

        assert_eq!(first, second);
        assert_eq!(
            serde_json::to_vec_pretty(&first).expect("first serializes"),
            serde_json::to_vec_pretty(&second).expect("second serializes")
        );
        assert_eq!(anchor, anchor_before);
        assert_eq!(journals, journals_before);
        assert_eq!(replay, replay_before);
        assert!(first.public_test_keys_only);
        assert!(!first.private_signing_material_embedded);
        assert!(!first.candidate_state_persisted);
        assert!(!first.runtime_consumer_enabled);
        assert!(!first.receipt_identity_end_to_end_reverified);
        assert!(!first.authority.may_dispatch);
        assert!(!first.authority.may_run_shadow);
        assert!(!first.authority.may_enable_runtime);
        assert!(!first.authority.may_run_executor);
        assert!(!first.authority.may_write_memory);
        assert!(!first.authority.may_write_graph);
        assert!(!first.authority.may_change_retrieval);
        assert!(!first.authority.may_change_session);
        assert!(!first.authority.may_persist_replay_state);
        assert!(!first.authority.may_mutate_trust_registry);
        assert!(!first.authority.production_trust_root_proven);
        assert!(!first.authority.root_rotation_proven);
        assert!(!first.authority.production_atomicity_proven);
        assert!(!first.authority.production_authority_granted);
    }
}
