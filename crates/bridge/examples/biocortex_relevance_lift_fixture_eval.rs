//! BioCortex relevance-lift fixture diagnostics.
//!
//! Read-only local harness for T6 headroom fixtures. It runs the existing
//! relevance-lift evaluator against explicit `query_cases`, then prints the
//! per-case rank fields that the Codex-facing MCP summary intentionally strips.
//!
//! This example does not register an MCP tool, write memory, mutate retrieval,
//! or expose live production ordering. It is an operator diagnostic for
//! answering "why did the redacted T6 summary report no lift?"
//!
//! ```text
//! AB_BIOCORTEX_RS=/path/to/biocortex-rs \
//!   cargo run -p ab-bridge --example biocortex_relevance_lift_fixture_eval
//! ```

use ab_bridge::biocortex_shadow::{
    biocortex_retrieval_relevance_lift_eval, run_retrieval_side_signal,
    BioCortexRetrievalCandidate, RelevanceLiftEvalOptions, RelevanceLiftQueryCase,
};
use ab_store::{
    default_db_path, BioCortexRetrievalOptInSideSignal, MemoryEdge, MemoryListSort, SqliteStore,
    StateStore,
};
use anyhow::{Context, Result};
use serde::Deserialize;
use serde_json::Value;
use std::cmp::Ordering;
use std::collections::{BTreeMap, BTreeSet, HashMap, HashSet};
use std::path::{Path, PathBuf};

const DEFAULT_FIXTURE: &str =
    "docs/design/fixtures/memory-biocortex-relevance-lift-headroom-cases-2026-06-20.json";

#[derive(Debug, Deserialize)]
struct Fixture {
    schema: String,
    query_cases: Vec<FixtureCase>,
}

#[derive(Debug, Deserialize)]
struct FixtureCase {
    query: String,
    relevant_keys: Vec<String>,
    class_label: Option<String>,
    baseline_fts_rank_observed: Option<u64>,
}

#[tokio::main]
async fn main() -> Result<()> {
    let fixture_path = std::env::args()
        .nth(1)
        .map(PathBuf::from)
        .unwrap_or_else(|| PathBuf::from(DEFAULT_FIXTURE));
    let fixture = load_fixture(&fixture_path)?;
    let db_path = std::env::var("AB_BASELINE_DB")
        .ok()
        .map(PathBuf::from)
        .unwrap_or_else(default_db_path);
    let checkout = std::env::var("AB_BIOCORTEX_RS")
        .ok()
        .map(|value| value.trim().to_string())
        .filter(|s| !s.is_empty())
        .map(PathBuf::from);
    let limit = env_u32("AB_RELEVANCE_LIFT_LIMIT", 20).clamp(5, 100);
    let timeout_ms = env_u64("AB_RELEVANCE_LIFT_TIMEOUT_MS", 180_000).clamp(1_000, 600_000);
    let blend_alpha = env_f32("AB_RELEVANCE_LIFT_BLEND_ALPHA", 0.8).clamp(0.0, 1.0);

    let store = SqliteStore::open(&db_path)
        .await
        .with_context(|| format!("open {}", db_path.display()))?;
    let query_cases = fixture
        .query_cases
        .iter()
        .map(|case| RelevanceLiftQueryCase {
            query: case.query.clone(),
            relevant_keys: case.relevant_keys.clone(),
            class_label: case.class_label.clone(),
        })
        .collect::<Vec<_>>();

    let payload = biocortex_retrieval_relevance_lift_eval(
        &store,
        RelevanceLiftEvalOptions {
            sample_size: query_cases.len(),
            kind: None,
            query_cases,
            sort: MemoryListSort::ByImportance,
            limit,
            query_chars: 120,
            or_terms: 10,
            blend_alpha,
            coverage_threshold: 0.8,
            include_related: true,
            checkout: checkout.clone(),
            timeout_ms,
        },
    )
    .await;

    let side_rows = analyze_side_signal(
        &store,
        &fixture,
        checkout.as_deref(),
        limit,
        timeout_ms,
        blend_alpha,
    )
    .await?;
    let graph_rows = analyze_graph_evidence(&store, &fixture, limit).await?;

    print_report(
        &fixture_path,
        &fixture,
        &db_path,
        &payload,
        &side_rows,
        &graph_rows,
    );
    Ok(())
}

fn load_fixture(path: &PathBuf) -> Result<Fixture> {
    let raw = std::fs::read_to_string(path)
        .with_context(|| format!("read fixture {}", path.display()))?;
    let fixture: Fixture =
        serde_json::from_str(&raw).with_context(|| format!("parse fixture {}", path.display()))?;
    anyhow::ensure!(
        !fixture.query_cases.is_empty(),
        "fixture query_cases is empty"
    );
    for (idx, case) in fixture.query_cases.iter().enumerate() {
        anyhow::ensure!(
            !case.query.trim().is_empty(),
            "fixture case {} has empty query",
            idx
        );
        anyhow::ensure!(
            !case.relevant_keys.is_empty(),
            "fixture case {} has no relevant_keys",
            idx
        );
    }
    Ok(fixture)
}

#[derive(Debug)]
struct SideSignalCaseRow {
    sample_index: usize,
    class_label: String,
    query_term_count: usize,
    baseline_source_rank: Option<usize>,
    baseline_first_relevant_rank: Option<usize>,
    reordered_source_rank: Option<usize>,
    reordered_first_relevant_rank: Option<usize>,
    source_side_rank: Option<usize>,
    source_side_score: Option<f32>,
    best_relevant_side_rank: Option<usize>,
    best_relevant_side_score: Option<f32>,
    top_side_relevant: bool,
    top_side_score: Option<f32>,
    distinct_side_scores: usize,
    top_score_tie_count: usize,
    distinct_overlaps: usize,
    top_overlap_tie_count: usize,
    distinct_competition_spikes: usize,
    top_spike_tie_count: usize,
    matched: usize,
    coverage: f64,
}

#[derive(Debug)]
struct SideScoreRecord {
    candidate_key: String,
    score: f32,
    evidence: SideEvidence,
}

#[derive(Debug, Default)]
struct SideEvidence {
    overlap: Option<f32>,
    competition_spikes: Option<usize>,
}

#[derive(Debug)]
struct GraphEvidenceCaseRow {
    sample_index: usize,
    class_label: String,
    candidate_count: usize,
    induced_edge_count: usize,
    induced_node_count: usize,
    source_graph_rank: Option<usize>,
    source_graph_score: Option<f64>,
    best_relevant_graph_rank: Option<usize>,
    best_relevant_graph_score: Option<f64>,
    top_graph_relevant: bool,
    top_graph_score: Option<f64>,
    distinct_graph_scores: usize,
    edge_type_counts: BTreeMap<String, usize>,
    variants: Vec<GraphScoreVariantRow>,
}

#[derive(Debug)]
struct GraphScoreVariantRow {
    label: &'static str,
    scored_node_count: usize,
    source_rank: Option<usize>,
    source_score: Option<f64>,
    best_relevant_rank: Option<usize>,
    best_relevant_score: Option<f64>,
    top_relevant: bool,
    top_score: Option<f64>,
    distinct_scores: usize,
    blend_available: bool,
    blend_coverage: f64,
    baseline_first_relevant_rank: Option<usize>,
    blend_first_relevant_rank: Option<usize>,
    blend_rr_delta: f64,
    blend_order_changed: bool,
}

#[derive(Copy, Clone, Debug)]
enum GraphScoreVariant {
    AllIncident,
    IncomingOnly,
    OutgoingOnly,
    NonContinuityIncident,
    ContinuityIncident,
}

const GRAPH_SCORE_VARIANTS: &[GraphScoreVariant] = &[
    GraphScoreVariant::AllIncident,
    GraphScoreVariant::IncomingOnly,
    GraphScoreVariant::OutgoingOnly,
    GraphScoreVariant::NonContinuityIncident,
    GraphScoreVariant::ContinuityIncident,
];

impl GraphScoreVariant {
    fn label(self) -> &'static str {
        match self {
            GraphScoreVariant::AllIncident => "all",
            GraphScoreVariant::IncomingOnly => "incoming",
            GraphScoreVariant::OutgoingOnly => "outgoing",
            GraphScoreVariant::NonContinuityIncident => "non_cont",
            GraphScoreVariant::ContinuityIncident => "cont_only",
        }
    }

    fn includes_edge(self, edge: &MemoryEdge) -> bool {
        match self {
            GraphScoreVariant::AllIncident
            | GraphScoreVariant::IncomingOnly
            | GraphScoreVariant::OutgoingOnly => true,
            GraphScoreVariant::NonContinuityIncident => !is_continuity_edge_type(&edge.edge_type),
            GraphScoreVariant::ContinuityIncident => is_continuity_edge_type(&edge.edge_type),
        }
    }

    fn apply_edge(self, scores: &mut BTreeMap<String, f64>, edge: &MemoryEdge) {
        if !self.includes_edge(edge) {
            return;
        }
        match self {
            GraphScoreVariant::IncomingOnly => {
                if let Some(score) = scores.get_mut(&edge.to_key) {
                    *score += edge.weight;
                }
            }
            GraphScoreVariant::OutgoingOnly => {
                if let Some(score) = scores.get_mut(&edge.from_key) {
                    *score += edge.weight;
                }
            }
            GraphScoreVariant::AllIncident
            | GraphScoreVariant::NonContinuityIncident
            | GraphScoreVariant::ContinuityIncident => {
                if let Some(score) = scores.get_mut(&edge.from_key) {
                    *score += edge.weight;
                }
                if let Some(score) = scores.get_mut(&edge.to_key) {
                    *score += edge.weight;
                }
            }
        }
    }
}

async fn analyze_graph_evidence(
    store: &SqliteStore,
    fixture: &Fixture,
    limit: u32,
) -> Result<Vec<GraphEvidenceCaseRow>> {
    let mut out = Vec::new();
    for (idx, case) in fixture.query_cases.iter().enumerate() {
        let baseline_hits = store
            .memory_search(&case.query, &[], limit)
            .await
            .with_context(|| format!("baseline memory_search for graph case {}", idx + 1))?;
        let baseline_ranking = baseline_hits
            .iter()
            .map(|hit| hit.record.key.clone())
            .collect::<Vec<_>>();
        let candidate_keys = baseline_hits
            .iter()
            .map(|hit| hit.record.key.clone())
            .collect::<BTreeSet<_>>();
        let source_key = case.relevant_keys.first().map(String::as_str);
        let relevant = case.relevant_keys.iter().cloned().collect::<BTreeSet<_>>();
        let mut seen_edges = HashSet::<(String, String, String)>::new();
        let mut induced_edges = Vec::<MemoryEdge>::new();
        let mut induced_nodes = BTreeSet::<String>::new();
        let mut edge_type_counts = BTreeMap::<String, usize>::new();

        for key in &candidate_keys {
            let neighbors = store.memory_neighbors(key).await.with_context(|| {
                format!("memory_neighbors for graph case {} key {}", idx + 1, key)
            })?;
            for edge in neighbors {
                if !candidate_keys.contains(&edge.from_key)
                    || !candidate_keys.contains(&edge.to_key)
                {
                    continue;
                }
                let dedupe_key = (
                    edge.from_key.clone(),
                    edge.to_key.clone(),
                    edge.edge_type.clone(),
                );
                if !seen_edges.insert(dedupe_key) {
                    continue;
                }
                *edge_type_counts.entry(edge.edge_type.clone()).or_default() += 1;
                induced_nodes.insert(edge.from_key.clone());
                induced_nodes.insert(edge.to_key.clone());
                induced_edges.push(edge);
            }
        }

        let graph_scores = score_graph_candidates(
            &candidate_keys,
            &induced_edges,
            GraphScoreVariant::AllIncident,
        );
        let source_graph_rank = source_key
            .and_then(|source| graph_scores.iter().position(|(key, _)| key == source))
            .map(|pos| pos + 1);
        let source_graph_score = source_key.and_then(|source| {
            graph_scores
                .iter()
                .find(|(key, _)| key == source)
                .map(|(_, score)| *score)
        });
        let (best_relevant_graph_rank, best_relevant_graph_score) = graph_scores
            .iter()
            .enumerate()
            .find(|(_, (key, _))| relevant.contains(key.as_str()))
            .map(|(idx, (_, score))| (Some(idx + 1), Some(*score)))
            .unwrap_or((None, None));
        let top_graph_score = graph_scores.first().map(|(_, score)| *score);
        let top_graph_relevant = graph_scores
            .first()
            .map(|(key, score)| *score > 0.0 && relevant.contains(key.as_str()))
            .unwrap_or(false);
        let distinct_graph_scores =
            distinct_f64_values(graph_scores.iter().map(|(_, score)| Some(*score)));
        let variants = GRAPH_SCORE_VARIANTS
            .iter()
            .copied()
            .map(|variant| {
                let scores = score_graph_candidates(&candidate_keys, &induced_edges, variant);
                summarize_graph_variant(
                    variant,
                    &baseline_hits,
                    &baseline_ranking,
                    &scores,
                    source_key,
                    &relevant,
                )
            })
            .collect::<Vec<_>>();

        out.push(GraphEvidenceCaseRow {
            sample_index: idx,
            class_label: case
                .class_label
                .clone()
                .unwrap_or_else(|| "unlabelled".to_string()),
            candidate_count: candidate_keys.len(),
            induced_edge_count: induced_edges.len(),
            induced_node_count: induced_nodes.len(),
            source_graph_rank,
            source_graph_score,
            best_relevant_graph_rank,
            best_relevant_graph_score,
            top_graph_relevant,
            top_graph_score,
            distinct_graph_scores,
            edge_type_counts,
            variants,
        });
    }
    Ok(out)
}

fn score_graph_candidates(
    candidate_keys: &BTreeSet<String>,
    induced_edges: &[MemoryEdge],
    variant: GraphScoreVariant,
) -> Vec<(String, f64)> {
    let mut scores = candidate_keys
        .iter()
        .map(|key| (key.clone(), 0.0_f64))
        .collect::<BTreeMap<_, _>>();
    for edge in induced_edges {
        variant.apply_edge(&mut scores, edge);
    }
    let mut out = scores
        .into_iter()
        .filter(|(_, score)| *score > 0.0)
        .collect::<Vec<_>>();
    out.sort_by(|a, b| {
        b.1.partial_cmp(&a.1)
            .unwrap_or(Ordering::Equal)
            .then_with(|| a.0.cmp(&b.0))
    });
    out
}

fn summarize_graph_variant(
    variant: GraphScoreVariant,
    baseline_hits: &[ab_store::MemorySearchHit],
    baseline_ranking: &[String],
    scores: &[(String, f64)],
    source_key: Option<&str>,
    relevant: &BTreeSet<String>,
) -> GraphScoreVariantRow {
    let source_rank = source_key
        .and_then(|source| scores.iter().position(|(key, _)| key == source))
        .map(|pos| pos + 1);
    let source_score = source_key.and_then(|source| {
        scores
            .iter()
            .find(|(key, _)| key == source)
            .map(|(_, score)| *score)
    });
    let (best_relevant_rank, best_relevant_score) = scores
        .iter()
        .enumerate()
        .find(|(_, (key, _))| relevant.contains(key.as_str()))
        .map(|(idx, (_, score))| (Some(idx + 1), Some(*score)))
        .unwrap_or((None, None));
    let top_score = scores.first().map(|(_, score)| *score);
    let top_relevant = scores
        .first()
        .map(|(key, score)| *score > 0.0 && relevant.contains(key.as_str()))
        .unwrap_or(false);
    let distinct_scores = distinct_f64_values(scores.iter().map(|(_, score)| Some(*score)));
    let graph_signals = graph_scores_to_side_signal(scores);
    let (blend_hits, blend_summary, blend_available) =
        ab_store::biocortex_opt_in_apply_side_signal(baseline_hits, &graph_signals, 0.8, 0.0, true);
    let blend_ranking = blend_hits
        .iter()
        .map(|hit| hit.record.key.clone())
        .collect::<Vec<_>>();
    let baseline_first_relevant_rank = first_relevant_rank(baseline_ranking, relevant);
    let blend_first_relevant_rank = first_relevant_rank(&blend_ranking, relevant);
    let blend_rr_delta =
        reciprocal_rank(blend_first_relevant_rank) - reciprocal_rank(baseline_first_relevant_rank);
    let blend_order_changed = baseline_ranking != blend_ranking.as_slice();

    GraphScoreVariantRow {
        label: variant.label(),
        scored_node_count: scores.len(),
        source_rank,
        source_score,
        best_relevant_rank,
        best_relevant_score,
        top_relevant,
        top_score,
        distinct_scores,
        blend_available,
        blend_coverage: blend_summary.coverage,
        baseline_first_relevant_rank,
        blend_first_relevant_rank,
        blend_rr_delta,
        blend_order_changed,
    }
}

fn graph_scores_to_side_signal(scores: &[(String, f64)]) -> Vec<BioCortexRetrievalOptInSideSignal> {
    let max_score = scores
        .iter()
        .map(|(_, score)| *score)
        .filter(|score| score.is_finite() && *score > 0.0)
        .fold(0.0_f64, f64::max);
    if max_score <= 0.0 {
        return Vec::new();
    }
    scores
        .iter()
        .filter_map(|(key, score)| {
            if !score.is_finite() || *score <= 0.0 {
                return None;
            }
            Some(BioCortexRetrievalOptInSideSignal {
                candidate_key: key.clone(),
                score: (*score / max_score).clamp(0.0, 1.0) as f32,
            })
        })
        .collect()
}

fn reciprocal_rank(rank: Option<usize>) -> f64 {
    rank.map(|rank| 1.0 / rank as f64).unwrap_or(0.0)
}

fn is_continuity_edge_type(edge_type: &str) -> bool {
    matches!(
        edge_type,
        "evolved" | "derived_from" | "supersedes" | "updates" | "corrects" | "caused_by"
    )
}

async fn analyze_side_signal(
    store: &SqliteStore,
    fixture: &Fixture,
    checkout: Option<&Path>,
    limit: u32,
    timeout_ms: u64,
    blend_alpha: f32,
) -> Result<Vec<SideSignalCaseRow>> {
    let mut out = Vec::new();
    for (idx, case) in fixture.query_cases.iter().enumerate() {
        let baseline_hits = store
            .memory_search(&case.query, &[], limit)
            .await
            .with_context(|| format!("baseline memory_search for case {}", idx + 1))?;
        let baseline_ranking = baseline_hits
            .iter()
            .map(|hit| hit.record.key.clone())
            .collect::<Vec<_>>();
        let candidates = baseline_hits
            .iter()
            .map(|hit| BioCortexRetrievalCandidate {
                key: hit.record.key.clone(),
                content: hit.record.content.clone(),
            })
            .collect::<Vec<_>>();
        let source_key = case.relevant_keys.first().map(String::as_str);
        let relevant = case.relevant_keys.iter().cloned().collect::<BTreeSet<_>>();
        let run =
            run_retrieval_side_signal(&case.query, &candidates, source_key, checkout, timeout_ms)
                .await
                .map_err(|value| {
                    anyhow::anyhow!("side signal failed for case {}: {}", idx + 1, value)
                })?;
        let candidate_keys = candidates
            .iter()
            .map(|candidate| candidate.key.as_str())
            .collect::<BTreeSet<_>>();
        let mut side_scores = run
            .rows
            .into_iter()
            .filter(|row| row.query_id == "q_runtime_shadow")
            .filter(|row| candidate_keys.contains(row.candidate_key.as_str()))
            .map(|row| SideScoreRecord {
                candidate_key: row.candidate_key,
                score: row.score,
                evidence: parse_side_evidence(row.evidence.as_deref()),
            })
            .collect::<Vec<_>>();
        side_scores.sort_by(|a, b| {
            b.score
                .partial_cmp(&a.score)
                .unwrap_or(Ordering::Equal)
                .then_with(|| a.candidate_key.cmp(&b.candidate_key))
        });
        let side_by_key = side_scores
            .iter()
            .map(|row| (row.candidate_key.as_str(), row.score))
            .collect::<HashMap<_, _>>();
        let side_signal_scores = side_scores
            .iter()
            .map(|row| BioCortexRetrievalOptInSideSignal {
                candidate_key: row.candidate_key.clone(),
                score: row.score,
            })
            .collect::<Vec<_>>();
        let (reordered_hits, summary, _) = ab_store::biocortex_opt_in_apply_side_signal(
            &baseline_hits,
            &side_signal_scores,
            blend_alpha,
            0.8,
            true,
        );
        let reordered_ranking = reordered_hits
            .iter()
            .map(|hit| hit.record.key.clone())
            .collect::<Vec<_>>();

        let source_side_rank = source_key.and_then(|source| {
            side_scores
                .iter()
                .position(|row| row.candidate_key == source)
                .map(|pos| pos + 1)
        });
        let source_side_score = source_key.and_then(|source| side_by_key.get(source).copied());
        let (best_relevant_side_rank, best_relevant_side_score) = side_scores
            .iter()
            .enumerate()
            .find(|(_, row)| relevant.contains(&row.candidate_key))
            .map(|(idx, row)| (Some(idx + 1), Some(row.score)))
            .unwrap_or((None, None));
        let top_side_relevant = side_scores
            .first()
            .map(|row| relevant.contains(&row.candidate_key))
            .unwrap_or(false);
        let top_side_score = side_scores.first().map(|row| row.score);
        let distinct_side_scores =
            distinct_f32_values(side_scores.iter().map(|row| Some(row.score)));
        let top_score_tie_count = top_side_score
            .map(|top| {
                side_scores
                    .iter()
                    .filter(|row| (row.score - top).abs() < f32::EPSILON)
                    .count()
            })
            .unwrap_or(0);
        let distinct_overlaps =
            distinct_f32_values(side_scores.iter().map(|row| row.evidence.overlap));
        let top_overlap = side_scores
            .iter()
            .filter_map(|row| row.evidence.overlap)
            .max_by(|a, b| a.partial_cmp(b).unwrap_or(Ordering::Equal));
        let top_overlap_tie_count = top_overlap
            .map(|top| {
                side_scores
                    .iter()
                    .filter_map(|row| row.evidence.overlap)
                    .filter(|overlap| (*overlap - top).abs() < f32::EPSILON)
                    .count()
            })
            .unwrap_or(0);
        let distinct_competition_spikes = distinct_usize_values(
            side_scores
                .iter()
                .map(|row| row.evidence.competition_spikes),
        );
        let top_spikes = side_scores
            .iter()
            .filter_map(|row| row.evidence.competition_spikes)
            .max();
        let top_spike_tie_count = top_spikes
            .map(|top| {
                side_scores
                    .iter()
                    .filter_map(|row| row.evidence.competition_spikes)
                    .filter(|spikes| *spikes == top)
                    .count()
            })
            .unwrap_or(0);

        out.push(SideSignalCaseRow {
            sample_index: idx,
            class_label: case
                .class_label
                .clone()
                .unwrap_or_else(|| "unlabelled".to_string()),
            query_term_count: adapter_query_terms(&case.query).len(),
            baseline_source_rank: source_key.and_then(|source| rank_in(&baseline_ranking, source)),
            baseline_first_relevant_rank: first_relevant_rank(&baseline_ranking, &relevant),
            reordered_source_rank: source_key
                .and_then(|source| rank_in(&reordered_ranking, source)),
            reordered_first_relevant_rank: first_relevant_rank(&reordered_ranking, &relevant),
            source_side_rank,
            source_side_score,
            best_relevant_side_rank,
            best_relevant_side_score,
            top_side_relevant,
            top_side_score,
            distinct_side_scores,
            top_score_tie_count,
            distinct_overlaps,
            top_overlap_tie_count,
            distinct_competition_spikes,
            top_spike_tie_count,
            matched: summary.matched_candidate_count,
            coverage: summary.coverage,
        });
    }
    Ok(out)
}

fn first_relevant_rank(ranking: &[String], relevant: &BTreeSet<String>) -> Option<usize> {
    ranking
        .iter()
        .position(|key| relevant.contains(key))
        .map(|idx| idx + 1)
}

fn rank_in(ranking: &[String], key: &str) -> Option<usize> {
    ranking
        .iter()
        .position(|candidate| candidate == key)
        .map(|idx| idx + 1)
}

fn parse_side_evidence(raw: Option<&str>) -> SideEvidence {
    let mut evidence = SideEvidence::default();
    let Some(raw) = raw else {
        return evidence;
    };
    for part in raw.split(';') {
        let Some((key, value)) = part.split_once('=') else {
            continue;
        };
        match key {
            "overlap" => evidence.overlap = value.parse().ok(),
            "competition_spikes" => evidence.competition_spikes = value.parse().ok(),
            _ => {}
        }
    }
    evidence
}

fn distinct_f32_values(values: impl Iterator<Item = Option<f32>>) -> usize {
    values
        .flatten()
        .fold(Vec::<f32>::new(), |mut acc, value| {
            if !acc
                .iter()
                .any(|existing| (*existing - value).abs() < f32::EPSILON)
            {
                acc.push(value);
            }
            acc
        })
        .len()
}

fn distinct_f64_values(values: impl Iterator<Item = Option<f64>>) -> usize {
    values
        .flatten()
        .fold(Vec::<f64>::new(), |mut acc, value| {
            if !acc
                .iter()
                .any(|existing| (*existing - value).abs() < f64::EPSILON)
            {
                acc.push(value);
            }
            acc
        })
        .len()
}

fn distinct_usize_values(values: impl Iterator<Item = Option<usize>>) -> usize {
    values.flatten().collect::<BTreeSet<_>>().len()
}

fn adapter_query_terms(text: &str) -> BTreeSet<String> {
    let mut out = BTreeSet::new();
    let mut cur = String::new();
    for ch in text.chars() {
        if ch.is_ascii_alphanumeric() {
            cur.push(ch.to_ascii_lowercase());
        } else if !cur.is_empty() {
            push_adapter_term(&mut out, &mut cur);
        }
    }
    if !cur.is_empty() {
        push_adapter_term(&mut out, &mut cur);
    }
    out
}

fn push_adapter_term(out: &mut BTreeSet<String>, cur: &mut String) {
    if cur.len() >= 3 && !is_adapter_stopword(cur) {
        out.insert(normalize_adapter_term(cur));
    }
    cur.clear();
}

fn normalize_adapter_term(term: &str) -> String {
    let mut out = term.to_string();
    for (suffix, replacement, min_len) in [
        ("ies", "y", 6_usize),
        ("ing", "", 6),
        ("ed", "", 5),
        ("es", "", 5),
        ("s", "", 5),
    ] {
        if out.len() >= min_len && out.ends_with(suffix) {
            out.truncate(out.len() - suffix.len());
            out.push_str(replacement);
            break;
        }
    }
    out
}

fn is_adapter_stopword(term: &str) -> bool {
    matches!(
        term,
        "the"
            | "and"
            | "for"
            | "with"
            | "that"
            | "this"
            | "not"
            | "into"
            | "from"
            | "what"
            | "why"
            | "how"
            | "does"
            | "did"
            | "can"
            | "yet"
            | "before"
            | "after"
            | "agent"
            | "bridge"
            | "biocortex"
    )
}

fn print_report(
    fixture_path: &PathBuf,
    fixture: &Fixture,
    db_path: &PathBuf,
    payload: &Value,
    side_rows: &[SideSignalCaseRow],
    graph_rows: &[GraphEvidenceCaseRow],
) {
    println!("# BioCortex relevance-lift fixture diagnostics");
    println!("fixture: {}", fixture_path.display());
    println!("fixture_schema: {}", fixture.schema);
    println!("db: {}", db_path.display());
    println!("status: {}", cell(&payload["status"]));
    println!("verdict: {}", cell(&payload["verdict"]));
    println!(
        "sampling: evaluated={} side_signal_unavailable={} source={}",
        cell(&payload["sampling"]["evaluated_count"]),
        cell(&payload["sampling"]["side_signal_unavailable"]),
        cell(&payload["sampling"]["query_source"])
    );
    println!(
        "metrics: mrr_baseline={} mrr_reordered={} mrr_lift={} improved={} worsened={} unchanged={} source_found_count={}",
        cell(&payload["metrics"]["mrr_baseline"]),
        cell(&payload["metrics"]["mrr_reordered"]),
        cell(&payload["metrics"]["mrr_lift"]),
        cell(&payload["metrics"]["improved"]),
        cell(&payload["metrics"]["worsened"]),
        cell(&payload["metrics"]["unchanged"]),
        cell(&payload["metrics"]["source_found_count"]),
    );
    println!();
    println!("## Per-case rank rows");
    println!(
        "{:<4} {:<34} {:>8} {:>8} {:>9} {:>7} {:>7} {:>7} {:>7} {:>8}",
        "#", "class_label", "obs_fts", "base", "reorder", "delta", "rr", "match", "cov", "changed"
    );

    for sample in payload["samples"].as_array().into_iter().flatten() {
        let idx = sample["sample_index"].as_u64().unwrap_or(0) as usize;
        let fixture_case = fixture.query_cases.get(idx);
        let class_label = sample["class_label"]
            .as_str()
            .or_else(|| fixture_case.and_then(|case| case.class_label.as_deref()))
            .unwrap_or("unlabelled");
        println!(
            "{:<4} {:<34} {:>8} {:>8} {:>9} {:>7} {:>7} {:>7} {:>7} {:>8}",
            idx + 1,
            truncate(class_label, 34),
            fixture_case
                .and_then(|case| case.baseline_fts_rank_observed)
                .map(|rank| rank.to_string())
                .unwrap_or_else(|| "-".to_string()),
            rank_cell(&sample["baseline_rank_of_source"]),
            rank_cell(&sample["reordered_rank_of_source"]),
            cell(&sample["rank_delta"]),
            cell(&sample["rr_delta"]),
            cell(&sample["side_signal_matched"]),
            cell(&sample["side_signal_coverage"]),
            cell(&sample["order_changed"]),
        );
    }
    println!();
    println!("## Per-case side-signal scoring rows");
    println!(
        "{:<4} {:<34} {:>5} {:>8} {:>8} {:>8} {:>8} {:>9} {:>9} {:>8} {:>8} {:>8} {:>7} {:>7} {:>7}",
        "#",
        "class_label",
        "qterm",
        "src_b",
        "rel_b",
        "src_r",
        "rel_r",
        "src_side",
        "rel_side",
        "top_rel",
        "top_score",
        "distinct",
        "top_tie",
        "match",
        "cov"
    );
    for row in side_rows {
        println!(
            "{:<4} {:<34} {:>5} {:>8} {:>8} {:>8} {:>8} {:>9} {:>9} {:>8} {:>8} {:>8} {:>7} {:>7} {:>7}",
            row.sample_index + 1,
            truncate(&row.class_label, 34),
            row.query_term_count,
            opt_usize(row.baseline_source_rank),
            opt_usize(row.baseline_first_relevant_rank),
            opt_usize(row.reordered_source_rank),
            opt_usize(row.reordered_first_relevant_rank),
            side_rank_score(row.source_side_rank, row.source_side_score),
            side_rank_score(row.best_relevant_side_rank, row.best_relevant_side_score),
            row.top_side_relevant,
            opt_f32(row.top_side_score),
            row.distinct_side_scores,
            row.top_score_tie_count,
            row.matched,
            format!("{:.3}", row.coverage),
        );
    }
    println!();
    println!("## Per-case adapter saturation rows");
    println!(
        "{:<4} {:<34} {:>5} {:>12} {:>13} {:>13} {:>12}",
        "#", "class_label", "qterm", "overlap_dist", "overlap_tie", "spike_dist", "spike_tie"
    );
    for row in side_rows {
        println!(
            "{:<4} {:<34} {:>5} {:>12} {:>13} {:>13} {:>12}",
            row.sample_index + 1,
            truncate(&row.class_label, 34),
            row.query_term_count,
            row.distinct_overlaps,
            row.top_overlap_tie_count,
            row.distinct_competition_spikes,
            row.top_spike_tie_count,
        );
    }
    println!();
    println!("## Per-case memory graph evidence rows");
    println!(
        "{:<4} {:<34} {:>5} {:>5} {:>5} {:>10} {:>10} {:>8} {:>8} {:>8} {:<24}",
        "#",
        "class_label",
        "cand",
        "edge",
        "node",
        "src_graph",
        "rel_graph",
        "top_rel",
        "top_g",
        "distinct",
        "edge_types"
    );
    for row in graph_rows {
        println!(
            "{:<4} {:<34} {:>5} {:>5} {:>5} {:>10} {:>10} {:>8} {:>8} {:>8} {:<24}",
            row.sample_index + 1,
            truncate(&row.class_label, 34),
            row.candidate_count,
            row.induced_edge_count,
            row.induced_node_count,
            graph_rank_score(row.source_graph_rank, row.source_graph_score),
            graph_rank_score(row.best_relevant_graph_rank, row.best_relevant_graph_score),
            row.top_graph_relevant,
            opt_f64(row.top_graph_score),
            row.distinct_graph_scores,
            truncate(&edge_type_summary(&row.edge_type_counts), 24),
        );
    }
    println!();
    println!("## Per-case memory graph scoring variant rows");
    println!(
        "{:<4} {:<34} {:<10} {:>6} {:>10} {:>10} {:>8} {:>8} {:>8} {:>6} {:>6} {:>7} {:>6} {:>7}",
        "#",
        "class_label",
        "variant",
        "scored",
        "src",
        "rel",
        "top_rel",
        "top_g",
        "distinct",
        "base",
        "blend",
        "rr_d",
        "avail",
        "cov"
    );
    for row in graph_rows {
        for variant in &row.variants {
            println!(
                "{:<4} {:<34} {:<10} {:>6} {:>10} {:>10} {:>8} {:>8} {:>8} {:>6} {:>6} {:>7} {:>6} {:>7}",
                row.sample_index + 1,
                truncate(&row.class_label, 34),
                variant.label,
                variant.scored_node_count,
                graph_rank_score(variant.source_rank, variant.source_score),
                graph_rank_score(variant.best_relevant_rank, variant.best_relevant_score),
                variant.top_relevant,
                opt_f64(variant.top_score),
                variant.distinct_scores,
                opt_usize(variant.baseline_first_relevant_rank),
                opt_usize(variant.blend_first_relevant_rank),
                format!("{:.3}", variant.blend_rr_delta),
                variant.blend_available,
                format!("{:.3}", variant.blend_coverage),
            );
        }
    }
    println!();
    println!("## Graph side-signal blend simulation summary");
    println!(
        "{:<10} {:>5} {:>7} {:>8} {:>9} {:>8} {:>8} {:>9}",
        "variant", "avail", "changed", "improved", "worsened", "same", "mrr_d", "avg_cov"
    );
    for variant in GRAPH_SCORE_VARIANTS {
        let label = variant.label();
        let rows = graph_rows
            .iter()
            .filter_map(|row| {
                row.variants
                    .iter()
                    .find(|candidate| candidate.label == label)
            })
            .collect::<Vec<_>>();
        let available = rows.iter().filter(|row| row.blend_available).count();
        let changed = rows.iter().filter(|row| row.blend_order_changed).count();
        let improved = rows
            .iter()
            .filter(|row| row.blend_rr_delta > f64::EPSILON)
            .count();
        let worsened = rows
            .iter()
            .filter(|row| row.blend_rr_delta < -f64::EPSILON)
            .count();
        let same = rows.len().saturating_sub(improved + worsened);
        let mrr_delta = if rows.is_empty() {
            0.0
        } else {
            rows.iter().map(|row| row.blend_rr_delta).sum::<f64>() / rows.len() as f64
        };
        let avg_coverage = if rows.is_empty() {
            0.0
        } else {
            rows.iter().map(|row| row.blend_coverage).sum::<f64>() / rows.len() as f64
        };
        println!(
            "{:<10} {:>5} {:>7} {:>8} {:>9} {:>8} {:>8} {:>9}",
            label,
            available,
            changed,
            improved,
            worsened,
            same,
            format!("{:.3}", mrr_delta),
            format!("{:.3}", avg_coverage),
        );
    }
    println!();
    println!("## Interpretation");
    println!(
        "- If `match` is low or `cov` is below the threshold, fix side-signal coverage before tuning rank blend."
    );
    println!(
        "- If `changed=true` but `delta=0`, the side-signal is moving distractors without lifting labelled relevant memory."
    );
    println!(
        "- If observed FTS rank differs from current `base`, the live store drifted; refresh the fixture observation before comparing lift."
    );
    println!(
        "- `src_side` is the primary source key's side-signal rank/score; `rel_side` is the best accept-set member's side-signal rank/score."
    );
    println!(
        "- If `top_rel=false` while coverage is high, BioCortex is scoring a distractor above every labelled relevant key."
    );
    println!(
        "- If `top_tie` is large or `distinct` is tiny, the side-signal is saturated and cannot reliably discriminate candidates."
    );
    println!(
        "- If `qterm` is tiny, the current adapter tokenization has collapsed the query before substrate scoring."
    );
    println!(
        "- If `overlap_tie` or `spike_tie` is large, saturation is happening inside the adapter before AB blending."
    );
    println!(
        "- If graph `edge`/`node` coverage is tiny, Track B needs graph materialization or better co-retrieval edges before adapter integration."
    );
    println!(
        "- If graph evidence exists but `top_rel=false`, the store has usable edge signal but needs better weighting, edge-type filtering, or directionality before it can influence ranking."
    );
    println!(
        "- Compare graph variants: `incoming` and `outgoing` test directionality, while `non_cont` excludes continuity/provenance edge types and `cont_only` isolates them."
    );
    println!(
        "- If only `cont_only` scores many nodes and still misses relevant keys, continuity edges are useful context but too noisy for direct rank influence."
    );
    println!(
        "- Graph blend simulation normalizes graph scores to `0..1`, applies the existing side-signal blend with alpha `0.8`, and uses threshold `0.0` so sparse graph signals can be tested."
    );
    println!(
        "- Treat positive `mrr_d` as a design hint only: this example is read-only and does not approve production graph influence."
    );
}

fn env_u32(name: &str, default: u32) -> u32 {
    std::env::var(name)
        .ok()
        .and_then(|v| v.parse().ok())
        .unwrap_or(default)
}

fn env_u64(name: &str, default: u64) -> u64 {
    std::env::var(name)
        .ok()
        .and_then(|v| v.parse().ok())
        .unwrap_or(default)
}

fn env_f32(name: &str, default: f32) -> f32 {
    std::env::var(name)
        .ok()
        .and_then(|v| v.parse().ok())
        .unwrap_or(default)
}

fn rank_cell(value: &Value) -> String {
    if value.is_null() {
        "-".to_string()
    } else {
        cell(value)
    }
}

fn cell(value: &Value) -> String {
    match value {
        Value::String(s) => s.clone(),
        Value::Null => "-".to_string(),
        other => other.to_string(),
    }
}

fn opt_usize(value: Option<usize>) -> String {
    value
        .map(|value| value.to_string())
        .unwrap_or_else(|| "-".to_string())
}

fn opt_f32(value: Option<f32>) -> String {
    value
        .map(|value| format!("{value:.3}"))
        .unwrap_or_else(|| "-".to_string())
}

fn opt_f64(value: Option<f64>) -> String {
    value
        .map(|value| format!("{value:.3}"))
        .unwrap_or_else(|| "-".to_string())
}

fn side_rank_score(rank: Option<usize>, score: Option<f32>) -> String {
    match (rank, score) {
        (Some(rank), Some(score)) => format!("{rank}/{score:.3}"),
        _ => "-".to_string(),
    }
}

fn graph_rank_score(rank: Option<usize>, score: Option<f64>) -> String {
    match (rank, score) {
        (Some(rank), Some(score)) => format!("{rank}/{score:.3}"),
        _ => "-".to_string(),
    }
}

fn edge_type_summary(counts: &BTreeMap<String, usize>) -> String {
    if counts.is_empty() {
        return "-".to_string();
    }
    counts
        .iter()
        .map(|(kind, count)| format!("{kind}:{count}"))
        .collect::<Vec<_>>()
        .join(",")
}

fn truncate(value: &str, max_chars: usize) -> String {
    let mut out = value.chars().take(max_chars).collect::<String>();
    if value.chars().count() > max_chars {
        out.push_str("...");
    }
    out
}
