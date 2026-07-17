//! Static S1 mapping from the S0 hostile-control-plane corpus to T6 guards.
//!
//! This example treats source files as inert bytes. It does not instantiate or
//! invoke an MCP tool, load live state, or grant runtime authority.

use anyhow::{ensure, Context};
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use std::collections::{BTreeMap, BTreeSet};

const MAPPING_BYTES: &[u8] =
    include_bytes!("../tests/fixtures/agent_compromise_resilience_s1_mapping.json");
const S0_CORPUS_BYTES: &[u8] =
    include_bytes!("../tests/fixtures/agent_compromise_resilience_s0.json");
const T6_SOURCE_BYTES: &[u8] = include_bytes!("../src/mcp_tools/memory_biocortex.rs");
const T6_TEST_BYTES: &[u8] = include_bytes!("../src/mcp_tools/tests.rs");

const MAPPING_SCHEMA: &str = "agent_bridge.agent_compromise_resilience.s1_mapping.v0";
const REPORT_SCHEMA: &str = "agent_bridge.agent_compromise_resilience.s1_report.v0";
const S0_SCHEMA: &str = "agent_bridge.agent_compromise_resilience.corpus.v0";
const T6_SOURCE_COMMIT: &str = "a1c9469e9a14cd73159d34974f0e99714ce5a1f0";
const S0_RESULT_COMMIT: &str = "69bd131499b6f1968bafc56da3247cf53a551698";
const S1_LINEAGE_MERGE_COMMIT: &str = "e216544255b2900e3d1a19fbda8571683592d96d";
const S0_CORPUS_SHA256: &str = "239d5ca7c823fdf8c946abb4d2563e51fc6732cc9dd9a40c8c57946715325849";

#[derive(Clone, Debug, Deserialize)]
#[serde(deny_unknown_fields)]
struct Mapping {
    schema: String,
    source: SourcePin,
    generic_containment: Vec<AnchorSet>,
    categories: Vec<CategoryMapping>,
}

#[derive(Clone, Debug, Deserialize)]
#[serde(deny_unknown_fields)]
struct SourcePin {
    t6_source_commit: String,
    s0_result_commit: String,
    s1_lineage_merge_commit: String,
    s0_corpus_sha256: String,
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
struct AnchorSet {
    id: String,
    source_id: String,
    anchors: Vec<String>,
}

#[derive(Clone, Debug, Deserialize)]
#[serde(deny_unknown_fields)]
struct CategoryMapping {
    category: Category,
    requirements: Vec<String>,
    evidence: Vec<GuardEvidence>,
    unanchored: Vec<UnanchoredGuard>,
    expected_status: MappingStatus,
    generic_containment_applies: bool,
}

#[derive(Clone, Debug, Deserialize)]
#[serde(deny_unknown_fields)]
struct GuardEvidence {
    guard: String,
    source_id: String,
    anchors: Vec<String>,
}

#[derive(Clone, Debug, Deserialize)]
#[serde(deny_unknown_fields)]
struct UnanchoredGuard {
    guard: String,
    note: String,
}

#[derive(Clone, Copy, Debug, Deserialize, Eq, Ord, PartialEq, PartialOrd, Serialize)]
#[serde(rename_all = "snake_case")]
enum Category {
    ForgedPreAuthorization,
    MissingScope,
    CrossTarget,
    PromptApproval,
    ModelInstructionOverride,
    AdapterInjection,
    EvidenceSelfCertification,
    SessionRewrite,
    ResumeReinjection,
    PseudoCompletion,
}

impl Category {
    fn as_str(self) -> &'static str {
        match self {
            Self::ForgedPreAuthorization => "forged_pre_authorization",
            Self::MissingScope => "missing_scope",
            Self::CrossTarget => "cross_target",
            Self::PromptApproval => "prompt_approval",
            Self::ModelInstructionOverride => "model_instruction_override",
            Self::AdapterInjection => "adapter_injection",
            Self::EvidenceSelfCertification => "evidence_self_certification",
            Self::SessionRewrite => "session_rewrite",
            Self::ResumeReinjection => "resume_reinjection",
            Self::PseudoCompletion => "pseudo_completion",
        }
    }
}

#[derive(Clone, Copy, Debug, Deserialize, Eq, Ord, PartialEq, PartialOrd, Serialize)]
#[serde(rename_all = "snake_case")]
enum MappingStatus {
    Covered,
    Partial,
    Gap,
}

impl MappingStatus {
    fn as_str(self) -> &'static str {
        match self {
            Self::Covered => "covered",
            Self::Partial => "partial",
            Self::Gap => "gap",
        }
    }
}

#[derive(Clone, Copy)]
struct EmbeddedSource {
    path: &'static str,
    bytes: &'static [u8],
}

type EmbeddedSources = BTreeMap<&'static str, EmbeddedSource>;

#[derive(Clone, Copy, Debug, Default, Eq, PartialEq, Serialize)]
struct Authority {
    may_dispatch_hostile_input: bool,
    may_run_shadow_mode: bool,
    may_enable_runtime: bool,
    may_write_memory: bool,
    may_write_graph: bool,
    may_change_retrieval: bool,
    may_change_session: bool,
    live_runtime_containment_proven: bool,
    production_security_claim: bool,
}

#[derive(Clone, Debug, Eq, PartialEq, Serialize)]
struct CategoryResult {
    category: Category,
    requirement_count: usize,
    anchored_guard_count: usize,
    unanchored_guard_count: usize,
    anchored_guards: Vec<String>,
    unanchored_guards: Vec<String>,
    derived_status: MappingStatus,
    expected_status: MappingStatus,
    generic_containment_applies: bool,
}

#[derive(Clone, Debug, Eq, PartialEq, Serialize)]
struct Report {
    schema: &'static str,
    status: &'static str,
    t6_source_commit: &'static str,
    s0_result_commit: &'static str,
    mapping_sha256: String,
    s0_corpus_sha256: String,
    source_sha256: BTreeMap<String, String>,
    category_count: usize,
    covered_count: usize,
    partial_count: usize,
    gap_count: usize,
    generic_containment_count: usize,
    source_anchor_count: usize,
    status_mismatch_count: usize,
    missing_anchor_count: usize,
    whole_repository_absence_proven: bool,
    authority: Authority,
    results: Vec<CategoryResult>,
}

fn main() -> anyhow::Result<()> {
    let mapping = load_mapping(MAPPING_BYTES)?;
    let sources = embedded_sources(T6_SOURCE_BYTES, T6_TEST_BYTES);
    let report = evaluate_mapping(&mapping, &sources, S0_CORPUS_BYTES, MAPPING_BYTES)?;
    println!("{}", serde_json::to_string_pretty(&report)?);
    Ok(())
}

fn load_mapping(bytes: &[u8]) -> anyhow::Result<Mapping> {
    serde_json::from_slice(bytes).context("parse S1 agent-compromise mapping")
}

fn embedded_sources(t6_source: &'static [u8], t6_tests: &'static [u8]) -> EmbeddedSources {
    BTreeMap::from([
        (
            "t6_source",
            EmbeddedSource {
                path: "crates/bridge/src/mcp_tools/memory_biocortex.rs",
                bytes: t6_source,
            },
        ),
        (
            "t6_tests",
            EmbeddedSource {
                path: "crates/bridge/src/mcp_tools/tests.rs",
                bytes: t6_tests,
            },
        ),
    ])
}

fn validate_mapping(
    mapping: &Mapping,
    sources: &EmbeddedSources,
    s0_corpus_bytes: &[u8],
) -> anyhow::Result<usize> {
    ensure!(
        mapping.schema == MAPPING_SCHEMA,
        "unexpected mapping schema"
    );
    ensure!(
        mapping.source.t6_source_commit == T6_SOURCE_COMMIT,
        "unexpected T6 source commit"
    );
    ensure!(
        mapping.source.s0_result_commit == S0_RESULT_COMMIT,
        "unexpected S0 result commit"
    );
    ensure!(
        mapping.source.s1_lineage_merge_commit == S1_LINEAGE_MERGE_COMMIT,
        "unexpected S1 lineage merge commit"
    );
    ensure!(
        mapping.source.s0_corpus_sha256 == S0_CORPUS_SHA256,
        "unexpected S0 corpus pin"
    );
    ensure!(
        sha256(s0_corpus_bytes) == S0_CORPUS_SHA256,
        "embedded S0 corpus hash differs from the frozen pin"
    );

    validate_source_pins(mapping, sources)?;
    validate_s0_category_set(mapping, s0_corpus_bytes)?;

    ensure!(
        mapping.generic_containment.len() == 7,
        "generic containment must contain 7 controls"
    );
    let mut containment_ids = BTreeSet::new();
    let mut source_anchor_count = 0usize;
    for control in &mapping.generic_containment {
        ensure!(
            !control.id.trim().is_empty() && containment_ids.insert(control.id.as_str()),
            "duplicate or empty generic-containment id {}",
            control.id
        );
        source_anchor_count += validate_anchors(
            &format!("generic containment {}", control.id),
            &control.source_id,
            &control.anchors,
            sources,
        )?;
    }

    ensure!(
        mapping.categories.len() == 10,
        "mapping must contain 10 categories"
    );
    let mut categories = BTreeSet::new();
    for category in &mapping.categories {
        ensure!(
            categories.insert(category.category),
            "duplicate category {}",
            category.category.as_str()
        );
        ensure!(
            category.generic_containment_applies,
            "{} must retain generic containment",
            category.category.as_str()
        );
        ensure!(
            category.requirements.len() >= 2,
            "{} must declare at least two threat-specific requirements",
            category.category.as_str()
        );

        let requirements = nonempty_unique_set(
            &category.requirements,
            &format!("{} requirements", category.category.as_str()),
        )?;
        let evidence_guards = category
            .evidence
            .iter()
            .map(|evidence| evidence.guard.as_str())
            .collect::<Vec<_>>();
        let evidence_guards = nonempty_unique_str_set(
            &evidence_guards,
            &format!("{} evidence", category.category.as_str()),
            true,
        )?;
        let unanchored_guards = category
            .unanchored
            .iter()
            .map(|guard| guard.guard.as_str())
            .collect::<Vec<_>>();
        let unanchored_guards = nonempty_unique_str_set(
            &unanchored_guards,
            &format!("{} unanchored", category.category.as_str()),
            true,
        )?;

        ensure!(
            evidence_guards.is_disjoint(&unanchored_guards),
            "{} guard appears as both evidence and unanchored",
            category.category.as_str()
        );
        ensure!(
            evidence_guards
                .union(&unanchored_guards)
                .copied()
                .collect::<BTreeSet<_>>()
                == requirements,
            "{} evidence/unanchored partition differs from requirements",
            category.category.as_str()
        );

        for evidence in &category.evidence {
            source_anchor_count += validate_anchors(
                &format!("{} guard {}", category.category.as_str(), evidence.guard),
                &evidence.source_id,
                &evidence.anchors,
                sources,
            )?;
        }
        for unanchored in &category.unanchored {
            ensure!(
                !unanchored.note.trim().is_empty(),
                "{} unanchored guard {} needs a note",
                category.category.as_str(),
                unanchored.guard
            );
        }

        let derived = derive_status(requirements.len(), evidence_guards.len());
        ensure!(
            derived == category.expected_status,
            "{} expected status {} differs from derived {}",
            category.category.as_str(),
            category.expected_status.as_str(),
            derived.as_str()
        );
    }

    Ok(source_anchor_count)
}

fn validate_source_pins(mapping: &Mapping, sources: &EmbeddedSources) -> anyhow::Result<()> {
    ensure!(
        mapping.source.files.len() == sources.len(),
        "source pin count differs from embedded source count"
    );
    let mut ids = BTreeSet::new();
    for pin in &mapping.source.files {
        ensure!(
            ids.insert(pin.id.as_str()),
            "duplicate source id {}",
            pin.id
        );
        let source = sources
            .get(pin.id.as_str())
            .with_context(|| format!("unknown source id {}", pin.id))?;
        ensure!(pin.path == source.path, "{} source path changed", pin.id);
        ensure!(
            pin.sha256 == sha256(source.bytes),
            "{} source hash changed",
            pin.id
        );
    }
    Ok(())
}

fn validate_s0_category_set(mapping: &Mapping, s0_corpus_bytes: &[u8]) -> anyhow::Result<()> {
    let s0: serde_json::Value =
        serde_json::from_slice(s0_corpus_bytes).context("parse S0 corpus projection")?;
    ensure!(
        s0.get("schema").and_then(serde_json::Value::as_str) == Some(S0_SCHEMA),
        "unexpected S0 corpus schema"
    );
    let cases = s0
        .get("cases")
        .and_then(serde_json::Value::as_array)
        .context("S0 corpus cases missing")?;
    ensure!(cases.len() == 34, "S0 corpus must contain 34 cases");
    let s0_categories = cases
        .iter()
        .filter_map(|case| case.get("category").and_then(serde_json::Value::as_str))
        .filter(|category| *category != "safe_inert_control")
        .collect::<BTreeSet<_>>();
    let mapping_categories = mapping
        .categories
        .iter()
        .map(|mapping| mapping.category.as_str())
        .collect::<BTreeSet<_>>();
    ensure!(
        s0_categories == mapping_categories,
        "S1 categories differ from S0 hostile categories"
    );
    Ok(())
}

fn validate_anchors(
    label: &str,
    source_id: &str,
    anchors: &[String],
    sources: &EmbeddedSources,
) -> anyhow::Result<usize> {
    ensure!(!anchors.is_empty(), "{label} has no source anchors");
    let source = sources
        .get(source_id)
        .with_context(|| format!("{label} uses unknown source id {source_id}"))?;
    let source_text = std::str::from_utf8(source.bytes)
        .with_context(|| format!("{} is not UTF-8", source.path))?;
    let mut unique = BTreeSet::new();
    for anchor in anchors {
        ensure!(
            !anchor.trim().is_empty() && unique.insert(anchor.as_str()),
            "{label} has an empty or duplicate anchor"
        );
        ensure!(
            source_text.contains(anchor),
            "{label} anchor missing from {}: {}",
            source.path,
            anchor
        );
    }
    Ok(anchors.len())
}

fn nonempty_unique_set<'a>(values: &'a [String], label: &str) -> anyhow::Result<BTreeSet<&'a str>> {
    let refs = values.iter().map(String::as_str).collect::<Vec<_>>();
    nonempty_unique_str_set(&refs, label, false)
}

fn nonempty_unique_str_set<'a>(
    values: &[&'a str],
    label: &str,
    allow_empty_collection: bool,
) -> anyhow::Result<BTreeSet<&'a str>> {
    if !allow_empty_collection {
        ensure!(!values.is_empty(), "{label} is empty");
    }
    let mut set = BTreeSet::new();
    for value in values {
        ensure!(!value.trim().is_empty(), "{label} contains an empty value");
        ensure!(set.insert(*value), "{label} contains duplicate {value}");
    }
    Ok(set)
}

fn derive_status(requirement_count: usize, evidence_count: usize) -> MappingStatus {
    if evidence_count == 0 {
        MappingStatus::Gap
    } else if evidence_count == requirement_count {
        MappingStatus::Covered
    } else {
        MappingStatus::Partial
    }
}

fn evaluate_mapping(
    mapping: &Mapping,
    sources: &EmbeddedSources,
    s0_corpus_bytes: &[u8],
    mapping_bytes: &[u8],
) -> anyhow::Result<Report> {
    let source_anchor_count = validate_mapping(mapping, sources, s0_corpus_bytes)?;

    let mut covered_count = 0usize;
    let mut partial_count = 0usize;
    let mut gap_count = 0usize;
    let mut results = Vec::with_capacity(mapping.categories.len());
    for category in &mapping.categories {
        let derived = derive_status(category.requirements.len(), category.evidence.len());
        match derived {
            MappingStatus::Covered => covered_count += 1,
            MappingStatus::Partial => partial_count += 1,
            MappingStatus::Gap => gap_count += 1,
        }
        results.push(CategoryResult {
            category: category.category,
            requirement_count: category.requirements.len(),
            anchored_guard_count: category.evidence.len(),
            unanchored_guard_count: category.unanchored.len(),
            anchored_guards: category
                .evidence
                .iter()
                .map(|guard| guard.guard.clone())
                .collect(),
            unanchored_guards: category
                .unanchored
                .iter()
                .map(|guard| guard.guard.clone())
                .collect(),
            derived_status: derived,
            expected_status: category.expected_status,
            generic_containment_applies: category.generic_containment_applies,
        });
    }

    let source_sha256 = mapping
        .source
        .files
        .iter()
        .map(|pin| (pin.path.clone(), pin.sha256.clone()))
        .collect();

    Ok(Report {
        schema: REPORT_SCHEMA,
        status: "pass_with_explicit_gaps",
        t6_source_commit: T6_SOURCE_COMMIT,
        s0_result_commit: S0_RESULT_COMMIT,
        mapping_sha256: sha256(mapping_bytes),
        s0_corpus_sha256: sha256(s0_corpus_bytes),
        source_sha256,
        category_count: mapping.categories.len(),
        covered_count,
        partial_count,
        gap_count,
        generic_containment_count: mapping.generic_containment.len(),
        source_anchor_count,
        status_mismatch_count: 0,
        missing_anchor_count: 0,
        whole_repository_absence_proven: false,
        authority: Authority::default(),
        results,
    })
}

fn sha256(bytes: &[u8]) -> String {
    format!("{:x}", Sha256::digest(bytes))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn frozen_mapping_derives_five_partial_and_five_gaps() {
        let mapping = load_mapping(MAPPING_BYTES).expect("mapping parses");
        let sources = embedded_sources(T6_SOURCE_BYTES, T6_TEST_BYTES);
        let report = evaluate_mapping(&mapping, &sources, S0_CORPUS_BYTES, MAPPING_BYTES)
            .expect("mapping evaluates");

        assert_eq!(report.category_count, 10);
        assert_eq!(report.covered_count, 0);
        assert_eq!(report.partial_count, 5);
        assert_eq!(report.gap_count, 5);
        assert_eq!(report.generic_containment_count, 7);
        assert_eq!(report.status_mismatch_count, 0);
        assert_eq!(report.missing_anchor_count, 0);
    }

    #[test]
    fn stale_hash_and_missing_anchor_fail_closed() {
        let mapping = load_mapping(MAPPING_BYTES).expect("mapping parses");
        let sources = embedded_sources(T6_SOURCE_BYTES, T6_TEST_BYTES);

        let mut stale = mapping.clone();
        stale.source.files[0].sha256 = "0".repeat(64);
        assert!(validate_mapping(&stale, &sources, S0_CORPUS_BYTES).is_err());

        let mut missing = mapping;
        missing.generic_containment[0]
            .anchors
            .push("anchor_that_does_not_exist".to_string());
        assert!(validate_mapping(&missing, &sources, S0_CORPUS_BYTES).is_err());
    }

    #[test]
    fn malformed_guard_partitions_and_statuses_fail_closed() {
        let mapping = load_mapping(MAPPING_BYTES).expect("mapping parses");
        let sources = embedded_sources(T6_SOURCE_BYTES, T6_TEST_BYTES);

        let mut duplicate = mapping.clone();
        duplicate.categories.push(duplicate.categories[0].clone());
        assert!(validate_mapping(&duplicate, &sources, S0_CORPUS_BYTES).is_err());

        let mut outside = mapping.clone();
        outside.categories[0].evidence[0].guard = "not_a_requirement".to_string();
        assert!(validate_mapping(&outside, &sources, S0_CORPUS_BYTES).is_err());

        let mut overlap = mapping.clone();
        overlap.categories[0].unanchored[0].guard = "explicit_owner_decision".to_string();
        assert!(validate_mapping(&overlap, &sources, S0_CORPUS_BYTES).is_err());

        let mut wrong_status = mapping;
        wrong_status.categories[0].expected_status = MappingStatus::Covered;
        assert!(validate_mapping(&wrong_status, &sources, S0_CORPUS_BYTES).is_err());
    }

    #[test]
    fn report_is_deterministic_and_non_authorizing() {
        let mapping = load_mapping(MAPPING_BYTES).expect("mapping parses");
        let sources = embedded_sources(T6_SOURCE_BYTES, T6_TEST_BYTES);
        let first = evaluate_mapping(&mapping, &sources, S0_CORPUS_BYTES, MAPPING_BYTES)
            .expect("first evaluation");
        let second = evaluate_mapping(&mapping, &sources, S0_CORPUS_BYTES, MAPPING_BYTES)
            .expect("second evaluation");

        assert_eq!(first, second);
        assert_eq!(first.status, "pass_with_explicit_gaps");
        assert!(!first.authority.may_dispatch_hostile_input);
        assert!(!first.authority.may_run_shadow_mode);
        assert!(!first.authority.may_enable_runtime);
        assert!(!first.authority.may_write_memory);
        assert!(!first.authority.may_write_graph);
        assert!(!first.authority.may_change_retrieval);
        assert!(!first.authority.may_change_session);
        assert!(!first.authority.live_runtime_containment_proven);
        assert!(!first.authority.production_security_claim);
    }
}
