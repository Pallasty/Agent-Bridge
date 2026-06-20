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
//! AB_BIOCORTEX_RS=/path/to/biocortex-rs \
//!   cargo run -p ab-bridge --example biocortex_relevance_lift_fixture_eval -- \
//!   docs/design/fixtures/memory-biocortex-relevance-lift-missing-graph-cases-2026-06-20.json \
//!   --packet-json
//! ```

use ab_bridge::biocortex_shadow::{
    BioCortexRetrievalCandidate, RelevanceLiftEvalOptions, RelevanceLiftQueryCase,
    biocortex_retrieval_relevance_lift_eval, run_retrieval_side_signal,
};
use ab_store::{
    BioCortexRetrievalOptInSideSignal, CoactivationEdge, MemoryEdge, MemoryListSort, MemoryRecord,
    SqliteStore, StateStore, cosine_similarity, default_db_path, embed_text,
};
use anyhow::{Context, Result};
use serde::Deserialize;
use serde_json::{Value, json};
use std::cmp::Ordering;
use std::collections::{BTreeMap, BTreeSet, HashMap, HashSet};
use std::path::{Path, PathBuf};
use std::time::{SystemTime, UNIX_EPOCH};

const DEFAULT_FIXTURE: &str =
    "docs/design/fixtures/memory-biocortex-relevance-lift-headroom-cases-2026-06-20.json";
const MATERIALIZATION_REVIEW_PACKET_SCHEMA: &str =
    "agent_bridge.biocortex_retrieval.materialization_review_packet.v0";

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
    review_intent: Option<String>,
    #[serde(default)]
    materialization_reason_packets: Vec<MaterializationReasonPacket>,
}

#[derive(Debug, Deserialize)]
struct MaterializationReasonPacket {
    from_key: String,
    to_key: String,
    edge_type: String,
    reason_kind: String,
    rationale: String,
    #[serde(default = "default_reason_packet_status")]
    status: String,
}

fn default_reason_packet_status() -> String {
    "active".to_string()
}

#[derive(Debug)]
struct CliOptions {
    fixture_path: PathBuf,
    emit_packet_json: bool,
}

#[tokio::main]
async fn main() -> Result<()> {
    let cli = parse_args()?;
    let fixture = load_fixture(&cli.fixture_path)?;
    let db_path = std::env::var("AB_BASELINE_DB")
        .ok()
        .map(PathBuf::from)
        .unwrap_or_else(default_db_path);
    let limit = env_u32("AB_RELEVANCE_LIFT_LIMIT", 20).clamp(5, 100);

    let store = SqliteStore::open(&db_path)
        .await
        .with_context(|| format!("open {}", db_path.display()))?;
    let graph_rows = analyze_graph_evidence(&store, &fixture, limit).await?;
    if cli.emit_packet_json {
        let packet = materialization_review_packet(&cli.fixture_path, &fixture, &graph_rows);
        println!(
            "{}",
            serde_json::to_string_pretty(&packet).context("serialize packet json")?
        );
        return Ok(());
    }

    let checkout = std::env::var("AB_BIOCORTEX_RS")
        .ok()
        .map(|value| value.trim().to_string())
        .filter(|s| !s.is_empty())
        .map(PathBuf::from);
    let timeout_ms = env_u64("AB_RELEVANCE_LIFT_TIMEOUT_MS", 180_000).clamp(1_000, 600_000);
    let blend_alpha = env_f32("AB_RELEVANCE_LIFT_BLEND_ALPHA", 0.8).clamp(0.0, 1.0);
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
    let preflight_rows = analyze_graph_preflight(&store, &fixture, limit).await?;

    print_report(
        &cli.fixture_path,
        &fixture,
        &db_path,
        &payload,
        &side_rows,
        &graph_rows,
        &preflight_rows,
    );
    Ok(())
}

fn parse_args() -> Result<CliOptions> {
    let mut fixture_path: Option<PathBuf> = None;
    let mut emit_packet_json = false;
    for arg in std::env::args().skip(1) {
        match arg.as_str() {
            "--packet-json" => emit_packet_json = true,
            "-h" | "--help" => {
                println!(
                    "usage: cargo run -p ab-bridge --example biocortex_relevance_lift_fixture_eval -- [fixture.json] [--packet-json]"
                );
                std::process::exit(0);
            }
            _ if arg.starts_with('-') => anyhow::bail!("unknown argument: {arg}"),
            _ => {
                anyhow::ensure!(fixture_path.is_none(), "multiple fixture paths provided");
                fixture_path = Some(PathBuf::from(arg));
            }
        }
    }
    Ok(CliOptions {
        fixture_path: fixture_path.unwrap_or_else(|| PathBuf::from(DEFAULT_FIXTURE)),
        emit_packet_json,
    })
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
    missing_edge_candidate_count: usize,
    missing_edge_candidate_relevant_count: usize,
    gated_edge_selected_count: usize,
    gated_edge_relevant_count: usize,
    gated_edge_blocked_label_count: usize,
    gated_edge_blocked_harm_count: usize,
    label_free_edge_selected_count: usize,
    label_free_edge_relevant_count: usize,
    label_free_edge_blocked_metadata_count: usize,
    label_free_edge_blocked_scope_count: usize,
    label_free_edge_blocked_temporal_count: usize,
    label_free_edge_blocked_shadow_count: usize,
    coretrieval_edge_selected_count: usize,
    coretrieval_edge_relevant_count: usize,
    coretrieval_edge_blocked_signal_count: usize,
    coretrieval_edge_blocked_shadow_count: usize,
    reason_packet_edge_selected_count: usize,
    reason_packet_edge_relevant_count: usize,
    reason_packet_blocked_packet_count: usize,
    reason_packet_blocked_shadow_count: usize,
    source_graph_rank: Option<usize>,
    source_graph_score: Option<f64>,
    best_relevant_graph_rank: Option<usize>,
    best_relevant_graph_score: Option<f64>,
    top_graph_relevant: bool,
    top_graph_score: Option<f64>,
    distinct_graph_scores: usize,
    edge_type_counts: BTreeMap<String, usize>,
    variants: Vec<GraphScoreVariantRow>,
    materialization_previews: Vec<MaterializationPreviewRow>,
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

#[derive(Clone, Debug)]
struct MaterializationPreviewRow {
    candidate_source: &'static str,
    gate: &'static str,
    from_key: String,
    to_key: String,
    edge_type: String,
    reason_kind: String,
    rationale: String,
    shadow_aligned: bool,
    baseline_top3: Vec<String>,
    preview_top3: Vec<String>,
    baseline_from_rank: Option<usize>,
    preview_from_rank: Option<usize>,
    baseline_to_rank: Option<usize>,
    preview_to_rank: Option<usize>,
    preview_order_changed: bool,
    blend_coverage: f64,
    writes_memory: bool,
    changes_search_order: bool,
}

#[derive(Debug)]
struct ReasonPacketShadowEvidence {
    aligned: bool,
    baseline_top3: Vec<String>,
    preview_top3: Vec<String>,
    baseline_from_rank: Option<usize>,
    preview_from_rank: Option<usize>,
    baseline_to_rank: Option<usize>,
    preview_to_rank: Option<usize>,
    preview_order_changed: bool,
    blend_coverage: f64,
}

#[derive(Debug)]
struct GraphPreflightCaseRow {
    sample_index: usize,
    class_label: String,
    candidate_count: usize,
    relevant_count: usize,
    relevant_in_candidates: usize,
    direct_relevant_edge_count: usize,
    direct_relevant_edge_types: BTreeMap<String, usize>,
    bfs_relevant_reached: usize,
    best_bfs_energy: Option<f64>,
    coactivation_edge_count: usize,
    coactivation_relevant_edge_count: usize,
    best_relevant_coactivation_count: Option<u64>,
    semantic_embedding_count: usize,
    semantic_relevant_rank: Option<usize>,
    semantic_relevant_cosine: Option<f32>,
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

async fn analyze_graph_preflight(
    store: &SqliteStore,
    fixture: &Fixture,
    limit: u32,
) -> Result<Vec<GraphPreflightCaseRow>> {
    let embedding_rows = store
        .memory_load_embeddings()
        .await
        .context("memory_load_embeddings for graph preflight")?;
    let mut out = Vec::new();
    for (idx, case) in fixture.query_cases.iter().enumerate() {
        let baseline_hits = store
            .memory_search(&case.query, &[], limit)
            .await
            .with_context(|| format!("baseline memory_search for preflight case {}", idx + 1))?;
        let candidate_keys = baseline_hits
            .iter()
            .map(|hit| hit.record.key.clone())
            .collect::<BTreeSet<_>>();
        let relevant = case.relevant_keys.iter().cloned().collect::<BTreeSet<_>>();
        let induced_edges = collect_candidate_induced_edges(store, &candidate_keys)
            .await
            .with_context(|| format!("candidate induced edges for preflight case {}", idx + 1))?;
        let graph_scores = score_graph_candidates(
            &candidate_keys,
            &induced_edges,
            GraphScoreVariant::AllIncident,
        );
        let relevant_in_candidates = relevant
            .iter()
            .filter(|key| candidate_keys.contains(*key))
            .count();
        let mut direct_relevant_edge_types = BTreeMap::<String, usize>::new();
        let direct_relevant_edge_count = induced_edges
            .iter()
            .filter(|edge| relevant.contains(&edge.from_key) || relevant.contains(&edge.to_key))
            .inspect(|edge| {
                *direct_relevant_edge_types
                    .entry(edge.edge_type.clone())
                    .or_default() += 1;
            })
            .count();
        let (bfs_relevant_reached, best_bfs_energy) =
            graph_hub_bfs_relevance(store, &graph_scores, &relevant).await?;
        let candidate_key_vec = candidate_keys.iter().cloned().collect::<Vec<_>>();
        let coactivation_edges = store
            .coactivation_among(&candidate_key_vec)
            .await
            .with_context(|| format!("coactivation_among for preflight case {}", idx + 1))?;
        let coactivation_relevant_edges = coactivation_edges
            .iter()
            .filter(|edge| relevant.contains(&edge.key_a) || relevant.contains(&edge.key_b))
            .count();
        let best_relevant_coactivation_count =
            best_relevant_coactivation_count(&coactivation_edges, &relevant);
        let (semantic_relevant_rank, semantic_relevant_cosine) =
            semantic_relevant_position(&case.query, &embedding_rows, &relevant);

        out.push(GraphPreflightCaseRow {
            sample_index: idx,
            class_label: case
                .class_label
                .clone()
                .unwrap_or_else(|| "unlabelled".to_string()),
            candidate_count: candidate_keys.len(),
            relevant_count: relevant.len(),
            relevant_in_candidates,
            direct_relevant_edge_count,
            direct_relevant_edge_types,
            bfs_relevant_reached,
            best_bfs_energy,
            coactivation_edge_count: coactivation_edges.len(),
            coactivation_relevant_edge_count: coactivation_relevant_edges,
            best_relevant_coactivation_count,
            semantic_embedding_count: embedding_rows.len(),
            semantic_relevant_rank,
            semantic_relevant_cosine,
        });
    }
    Ok(out)
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
        let induced_edges = collect_candidate_induced_edges(store, &candidate_keys)
            .await
            .with_context(|| format!("candidate induced edges for graph case {}", idx + 1))?;
        let candidate_key_vec = candidate_keys.iter().cloned().collect::<Vec<_>>();
        let coactivation_edges = store
            .coactivation_among(&candidate_key_vec)
            .await
            .with_context(|| format!("coactivation_among for graph case {}", idx + 1))?;
        let missing_edge_candidates =
            collect_related_key_missing_edges(&baseline_hits, &candidate_keys, &induced_edges);
        let missing_edge_candidate_count = missing_edge_candidates.len();
        let missing_edge_candidate_relevant_count = missing_edge_candidates
            .iter()
            .filter(|edge| relevant.contains(&edge.from_key) || relevant.contains(&edge.to_key))
            .count();
        let gate = select_quality_gated_edges(
            &baseline_hits,
            &baseline_ranking,
            &candidate_keys,
            &induced_edges,
            &missing_edge_candidates,
            source_key,
            &relevant,
        );
        let label_free_gate = select_label_free_quality_edges(
            &baseline_hits,
            &baseline_ranking,
            &candidate_keys,
            &induced_edges,
            &missing_edge_candidates,
        );
        let label_free_edge_relevant_count = label_free_gate
            .selected_edges
            .iter()
            .filter(|edge| relevant.contains(&edge.from_key) || relevant.contains(&edge.to_key))
            .count();
        let coretrieval_gate = select_coretrieval_quality_edges(
            &baseline_hits,
            &baseline_ranking,
            &candidate_keys,
            &induced_edges,
            &missing_edge_candidates,
            &coactivation_edges,
        );
        let coretrieval_edge_relevant_count = coretrieval_gate
            .selected_edges
            .iter()
            .filter(|edge| relevant.contains(&edge.from_key) || relevant.contains(&edge.to_key))
            .count();
        let reason_packet_gate = select_reason_packet_quality_edges(
            &baseline_hits,
            &baseline_ranking,
            &candidate_keys,
            &induced_edges,
            &missing_edge_candidates,
            &case.materialization_reason_packets,
        );
        let reason_packet_edge_relevant_count = reason_packet_gate
            .selected_edges
            .iter()
            .filter(|edge| relevant.contains(&edge.from_key) || relevant.contains(&edge.to_key))
            .count();
        let mut induced_nodes = BTreeSet::<String>::new();
        let mut edge_type_counts = BTreeMap::<String, usize>::new();
        for edge in &induced_edges {
            *edge_type_counts.entry(edge.edge_type.clone()).or_default() += 1;
            induced_nodes.insert(edge.from_key.clone());
            induced_nodes.insert(edge.to_key.clone());
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
        let mut variants = GRAPH_SCORE_VARIANTS
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
        let bounded_proximity_scores =
            score_bounded_graph_proximity(store, &candidate_keys, &induced_edges)
                .await
                .with_context(|| {
                    format!("bounded graph proximity scores for graph case {}", idx + 1)
                })?;
        variants.push(summarize_graph_scores(
            "bounded_prox",
            &baseline_hits,
            &baseline_ranking,
            &bounded_proximity_scores,
            source_key,
            &relevant,
        ));
        if !missing_edge_candidates.is_empty() {
            let mut materialized_edges = induced_edges.clone();
            materialized_edges.extend(missing_edge_candidates.iter().cloned());
            let related_materialized_scores = score_graph_candidates(
                &candidate_keys,
                &materialized_edges,
                GraphScoreVariant::NonContinuityIncident,
            );
            variants.push(summarize_graph_scores(
                "related_mat",
                &baseline_hits,
                &baseline_ranking,
                &related_materialized_scores,
                source_key,
                &relevant,
            ));
            let bounded_materialized_scores =
                score_bounded_graph_proximity(store, &candidate_keys, &materialized_edges)
                    .await
                    .with_context(|| {
                        format!(
                            "bounded materialized graph scores for graph case {}",
                            idx + 1
                        )
                    })?;
            variants.push(summarize_graph_scores(
                "bounded_mat",
                &baseline_hits,
                &baseline_ranking,
                &bounded_materialized_scores,
                source_key,
                &relevant,
            ));
        }
        if !gate.selected_edges.is_empty() {
            let mut gated_edges = induced_edges.clone();
            gated_edges.extend(gate.selected_edges.iter().cloned());
            let gated_scores = score_graph_candidates(
                &candidate_keys,
                &gated_edges,
                GraphScoreVariant::NonContinuityIncident,
            );
            variants.push(summarize_graph_scores(
                "gated_rel",
                &baseline_hits,
                &baseline_ranking,
                &gated_scores,
                source_key,
                &relevant,
            ));
        }
        if !label_free_gate.selected_edges.is_empty() {
            let mut label_free_edges = induced_edges.clone();
            label_free_edges.extend(label_free_gate.selected_edges.iter().cloned());
            let label_free_scores = score_graph_candidates(
                &candidate_keys,
                &label_free_edges,
                GraphScoreVariant::NonContinuityIncident,
            );
            variants.push(summarize_graph_scores(
                "prod_gate",
                &baseline_hits,
                &baseline_ranking,
                &label_free_scores,
                source_key,
                &relevant,
            ));
        }
        if !coretrieval_gate.selected_edges.is_empty() {
            let mut coretrieval_edges = induced_edges.clone();
            coretrieval_edges.extend(coretrieval_gate.selected_edges.iter().cloned());
            let coretrieval_scores = score_graph_candidates(
                &candidate_keys,
                &coretrieval_edges,
                GraphScoreVariant::NonContinuityIncident,
            );
            variants.push(summarize_graph_scores(
                "co_ret_gate",
                &baseline_hits,
                &baseline_ranking,
                &coretrieval_scores,
                source_key,
                &relevant,
            ));
        }
        if !reason_packet_gate.selected_edges.is_empty() {
            let mut reason_packet_edges = induced_edges.clone();
            reason_packet_edges.extend(reason_packet_gate.selected_edges.iter().cloned());
            let reason_packet_scores = score_graph_candidates(
                &candidate_keys,
                &reason_packet_edges,
                GraphScoreVariant::NonContinuityIncident,
            );
            variants.push(summarize_graph_scores(
                "reason_pkt",
                &baseline_hits,
                &baseline_ranking,
                &reason_packet_scores,
                source_key,
                &relevant,
            ));
        }

        out.push(GraphEvidenceCaseRow {
            sample_index: idx,
            class_label: case
                .class_label
                .clone()
                .unwrap_or_else(|| "unlabelled".to_string()),
            candidate_count: candidate_keys.len(),
            induced_edge_count: induced_edges.len(),
            induced_node_count: induced_nodes.len(),
            missing_edge_candidate_count,
            missing_edge_candidate_relevant_count,
            gated_edge_selected_count: gate.selected_edges.len(),
            gated_edge_relevant_count: gate.relevant_selected_count,
            gated_edge_blocked_label_count: gate.blocked_no_relevance_count,
            gated_edge_blocked_harm_count: gate.blocked_harm_count,
            label_free_edge_selected_count: label_free_gate.selected_edges.len(),
            label_free_edge_relevant_count,
            label_free_edge_blocked_metadata_count: label_free_gate.blocked_metadata_count,
            label_free_edge_blocked_scope_count: label_free_gate.blocked_scope_count,
            label_free_edge_blocked_temporal_count: label_free_gate.blocked_temporal_count,
            label_free_edge_blocked_shadow_count: label_free_gate.blocked_shadow_count,
            coretrieval_edge_selected_count: coretrieval_gate.selected_edges.len(),
            coretrieval_edge_relevant_count,
            coretrieval_edge_blocked_signal_count: coretrieval_gate.blocked_signal_count,
            coretrieval_edge_blocked_shadow_count: coretrieval_gate.blocked_shadow_count,
            reason_packet_edge_selected_count: reason_packet_gate.selected_edges.len(),
            reason_packet_edge_relevant_count,
            reason_packet_blocked_packet_count: reason_packet_gate.blocked_packet_count,
            reason_packet_blocked_shadow_count: reason_packet_gate.blocked_shadow_count,
            source_graph_rank,
            source_graph_score,
            best_relevant_graph_rank,
            best_relevant_graph_score,
            top_graph_relevant,
            top_graph_score,
            distinct_graph_scores,
            edge_type_counts,
            variants,
            materialization_previews: reason_packet_gate.preview_rows.clone(),
        });
    }
    Ok(out)
}

#[derive(Debug, Default)]
struct CandidateQualityGate {
    selected_edges: Vec<MemoryEdge>,
    relevant_selected_count: usize,
    blocked_no_relevance_count: usize,
    blocked_harm_count: usize,
}

#[derive(Debug, Default)]
struct LabelFreeCandidateQualityGate {
    selected_edges: Vec<MemoryEdge>,
    blocked_metadata_count: usize,
    blocked_scope_count: usize,
    blocked_temporal_count: usize,
    blocked_shadow_count: usize,
}

#[derive(Debug, Default)]
struct CoretrievalCandidateQualityGate {
    selected_edges: Vec<MemoryEdge>,
    blocked_signal_count: usize,
    blocked_shadow_count: usize,
}

#[derive(Debug, Default)]
struct ReasonPacketCandidateQualityGate {
    selected_edges: Vec<MemoryEdge>,
    preview_rows: Vec<MaterializationPreviewRow>,
    blocked_packet_count: usize,
    blocked_shadow_count: usize,
}

fn select_quality_gated_edges(
    baseline_hits: &[ab_store::MemorySearchHit],
    baseline_ranking: &[String],
    candidate_keys: &BTreeSet<String>,
    induced_edges: &[MemoryEdge],
    missing_edge_candidates: &[MemoryEdge],
    source_key: Option<&str>,
    relevant: &BTreeSet<String>,
) -> CandidateQualityGate {
    let mut out = CandidateQualityGate::default();
    for candidate in missing_edge_candidates {
        if !relevant.contains(&candidate.from_key) && !relevant.contains(&candidate.to_key) {
            out.blocked_no_relevance_count += 1;
            continue;
        }
        let mut trial_edges = induced_edges.to_vec();
        trial_edges.push(candidate.clone());
        let trial_scores = score_graph_candidates(
            candidate_keys,
            &trial_edges,
            GraphScoreVariant::NonContinuityIncident,
        );
        let trial = summarize_graph_scores(
            "single_edge_trial",
            baseline_hits,
            baseline_ranking,
            &trial_scores,
            source_key,
            relevant,
        );
        if trial.blend_rr_delta < -f64::EPSILON {
            out.blocked_harm_count += 1;
            continue;
        }
        out.relevant_selected_count += 1;
        out.selected_edges.push(candidate.clone());
    }
    out
}

fn select_label_free_quality_edges(
    baseline_hits: &[ab_store::MemorySearchHit],
    baseline_ranking: &[String],
    candidate_keys: &BTreeSet<String>,
    induced_edges: &[MemoryEdge],
    missing_edge_candidates: &[MemoryEdge],
) -> LabelFreeCandidateQualityGate {
    let records = baseline_hits
        .iter()
        .map(|hit| (hit.record.key.as_str(), &hit.record))
        .collect::<HashMap<_, _>>();
    let mut out = LabelFreeCandidateQualityGate::default();
    for candidate in missing_edge_candidates {
        let Some(from) = records.get(candidate.from_key.as_str()).copied() else {
            out.blocked_metadata_count += 1;
            continue;
        };
        let Some(to) = records.get(candidate.to_key.as_str()).copied() else {
            out.blocked_metadata_count += 1;
            continue;
        };
        if !label_free_endpoint_metadata_allowed(from) || !label_free_endpoint_metadata_allowed(to)
        {
            out.blocked_metadata_count += 1;
            continue;
        }
        if !label_free_scopes_compatible(from.scope.as_deref(), to.scope.as_deref()) {
            out.blocked_scope_count += 1;
            continue;
        }
        if !label_free_temporal_proximity(from.updated_at, to.updated_at) {
            out.blocked_temporal_count += 1;
            continue;
        }
        if !label_free_shadow_top3_preserved(
            baseline_hits,
            baseline_ranking,
            candidate_keys,
            induced_edges,
            candidate,
        ) {
            out.blocked_shadow_count += 1;
            continue;
        }
        out.selected_edges.push(candidate.clone());
    }
    out
}

fn select_coretrieval_quality_edges(
    baseline_hits: &[ab_store::MemorySearchHit],
    baseline_ranking: &[String],
    candidate_keys: &BTreeSet<String>,
    induced_edges: &[MemoryEdge],
    missing_edge_candidates: &[MemoryEdge],
    coactivation_edges: &[CoactivationEdge],
) -> CoretrievalCandidateQualityGate {
    const MIN_CORETRIEVAL_COUNT: u64 = 2;
    let coactivation_by_pair = coactivation_edges
        .iter()
        .map(|edge| (undirected_pair_key(&edge.key_a, &edge.key_b), edge.count))
        .collect::<HashMap<_, _>>();
    let mut out = CoretrievalCandidateQualityGate::default();
    for candidate in missing_edge_candidates {
        let pair_key = undirected_pair_key(&candidate.from_key, &candidate.to_key);
        let count = coactivation_by_pair.get(&pair_key).copied().unwrap_or(0);
        if count < MIN_CORETRIEVAL_COUNT {
            out.blocked_signal_count += 1;
            continue;
        }
        if !label_free_shadow_top3_preserved(
            baseline_hits,
            baseline_ranking,
            candidate_keys,
            induced_edges,
            candidate,
        ) {
            out.blocked_shadow_count += 1;
            continue;
        }
        out.selected_edges.push(candidate.clone());
    }
    out
}

fn select_reason_packet_quality_edges(
    baseline_hits: &[ab_store::MemorySearchHit],
    baseline_ranking: &[String],
    candidate_keys: &BTreeSet<String>,
    induced_edges: &[MemoryEdge],
    missing_edge_candidates: &[MemoryEdge],
    reason_packets: &[MaterializationReasonPacket],
) -> ReasonPacketCandidateQualityGate {
    let active_packets = reason_packets
        .iter()
        .filter(|packet| reason_packet_valid(packet))
        .map(|packet| {
            (
                undirected_pair_key(&packet.from_key, &packet.to_key),
                packet,
            )
        })
        .collect::<HashMap<_, _>>();
    let mut out = ReasonPacketCandidateQualityGate::default();
    for candidate in missing_edge_candidates {
        let pair_key = undirected_pair_key(&candidate.from_key, &candidate.to_key);
        let Some(packet) = active_packets.get(&pair_key) else {
            out.blocked_packet_count += 1;
            continue;
        };
        if packet.edge_type != candidate.edge_type {
            out.blocked_packet_count += 1;
            continue;
        }
        let Some(shadow) = reason_packet_shadow_evidence(
            baseline_hits,
            baseline_ranking,
            candidate_keys,
            induced_edges,
            candidate,
            packet,
        ) else {
            out.blocked_shadow_count += 1;
            continue;
        };
        if !shadow.aligned {
            out.blocked_shadow_count += 1;
            continue;
        }
        out.preview_rows
            .push(materialization_preview_row(candidate, packet, shadow));
        out.selected_edges.push(candidate.clone());
    }
    out
}

fn reason_packet_valid(packet: &MaterializationReasonPacket) -> bool {
    packet.status == "active"
        && reason_packet_edge_type_allowed(&packet.edge_type)
        && !packet.reason_kind.trim().is_empty()
        && !packet.rationale.trim().is_empty()
        && !packet.from_key.trim().is_empty()
        && !packet.to_key.trim().is_empty()
        && packet.from_key != packet.to_key
}

fn reason_packet_edge_type_allowed(edge_type: &str) -> bool {
    matches!(edge_type, "relates" | "implements" | "derived_from")
}

fn reason_packet_shadow_evidence(
    baseline_hits: &[ab_store::MemorySearchHit],
    baseline_ranking: &[String],
    candidate_keys: &BTreeSet<String>,
    induced_edges: &[MemoryEdge],
    candidate: &MemoryEdge,
    packet: &MaterializationReasonPacket,
) -> Option<ReasonPacketShadowEvidence> {
    let baseline_prefix = baseline_ranking.iter().take(3).cloned().collect::<Vec<_>>();
    if baseline_prefix.is_empty() {
        return None;
    }
    let mut trial_edges = induced_edges.to_vec();
    trial_edges.push(candidate.clone());
    let trial_scores = score_graph_candidates(
        candidate_keys,
        &trial_edges,
        GraphScoreVariant::NonContinuityIncident,
    );
    let graph_signals = graph_scores_to_side_signal(&trial_scores);
    let (blend_hits, blend_summary, blend_available) =
        ab_store::biocortex_opt_in_apply_side_signal(baseline_hits, &graph_signals, 0.8, 0.0, true);
    if !blend_available {
        return None;
    }
    let blend_ranking = blend_hits
        .iter()
        .map(|hit| hit.record.key.clone())
        .collect::<Vec<_>>();
    let blend_prefix = blend_hits
        .iter()
        .take(baseline_prefix.len())
        .map(|hit| hit.record.key.clone())
        .collect::<Vec<_>>();
    let aligned = blend_prefix == baseline_prefix
        || blend_prefix.iter().all(|key| {
            baseline_prefix.contains(key) || key == &packet.from_key || key == &packet.to_key
        });
    Some(ReasonPacketShadowEvidence {
        aligned,
        baseline_top3: baseline_prefix,
        preview_top3: blend_prefix,
        baseline_from_rank: rank_of_key(baseline_ranking, &packet.from_key),
        preview_from_rank: rank_of_key(&blend_ranking, &packet.from_key),
        baseline_to_rank: rank_of_key(baseline_ranking, &packet.to_key),
        preview_to_rank: rank_of_key(&blend_ranking, &packet.to_key),
        preview_order_changed: baseline_ranking != blend_ranking.as_slice(),
        blend_coverage: blend_summary.coverage,
    })
}

fn materialization_preview_row(
    candidate: &MemoryEdge,
    packet: &MaterializationReasonPacket,
    shadow: ReasonPacketShadowEvidence,
) -> MaterializationPreviewRow {
    MaterializationPreviewRow {
        candidate_source: "explicit_related_keys",
        gate: "reason_packet",
        from_key: candidate.from_key.clone(),
        to_key: candidate.to_key.clone(),
        edge_type: candidate.edge_type.clone(),
        reason_kind: packet.reason_kind.clone(),
        rationale: packet.rationale.clone(),
        shadow_aligned: shadow.aligned,
        baseline_top3: shadow.baseline_top3,
        preview_top3: shadow.preview_top3,
        baseline_from_rank: shadow.baseline_from_rank,
        preview_from_rank: shadow.preview_from_rank,
        baseline_to_rank: shadow.baseline_to_rank,
        preview_to_rank: shadow.preview_to_rank,
        preview_order_changed: shadow.preview_order_changed,
        blend_coverage: shadow.blend_coverage,
        writes_memory: false,
        changes_search_order: false,
    }
}

fn materialization_review_packet(
    fixture_path: &Path,
    fixture: &Fixture,
    graph_rows: &[GraphEvidenceCaseRow],
) -> Value {
    let preview_case_count = graph_rows
        .iter()
        .filter(|row| !row.materialization_previews.is_empty())
        .count();
    let preview_candidate_count = graph_rows
        .iter()
        .map(|row| row.materialization_previews.len())
        .sum::<usize>();
    let reason_packet_selected_edge_count = graph_rows
        .iter()
        .map(|row| row.reason_packet_edge_selected_count)
        .sum::<usize>();
    let reason_packet_relevant_edge_count = graph_rows
        .iter()
        .map(|row| row.reason_packet_edge_relevant_count)
        .sum::<usize>();
    let reason_packet_blocked_packet_count = graph_rows
        .iter()
        .map(|row| row.reason_packet_blocked_packet_count)
        .sum::<usize>();
    let reason_packet_blocked_shadow_count = graph_rows
        .iter()
        .map(|row| row.reason_packet_blocked_shadow_count)
        .sum::<usize>();
    let candidates = graph_rows
        .iter()
        .flat_map(|row| {
            let fixture_case = fixture.query_cases.get(row.sample_index);
            row.materialization_previews.iter().map(move |preview| {
                json!({
                    "case_index": row.sample_index + 1,
                    "class_label": row.class_label,
                    "baseline_fts_rank_observed": fixture_case.and_then(|case| case.baseline_fts_rank_observed),
                    "review_intent": fixture_case.and_then(|case| case.review_intent.clone()),
                    "candidate_source": preview.candidate_source,
                    "gate": preview.gate,
                    "from_key": preview.from_key,
                    "to_key": preview.to_key,
                    "edge_type": preview.edge_type,
                    "reason_kind": preview.reason_kind,
                    "rationale": preview.rationale,
                    "shadow_aligned": preview.shadow_aligned,
                    "baseline_top3": preview.baseline_top3,
                    "preview_top3": preview.preview_top3,
                    "baseline_from_rank": preview.baseline_from_rank,
                    "preview_from_rank": preview.preview_from_rank,
                    "baseline_to_rank": preview.baseline_to_rank,
                    "preview_to_rank": preview.preview_to_rank,
                    "preview_order_changed": preview.preview_order_changed,
                    "blend_coverage": preview.blend_coverage,
                    "writes_memory": preview.writes_memory,
                    "changes_search_order": preview.changes_search_order,
                })
            })
        })
        .collect::<Vec<_>>();

    json!({
        "schema": MATERIALIZATION_REVIEW_PACKET_SCHEMA,
        "generated_at": now_secs(),
        "purpose": "Read-only materialization review packet for human review; this is not approval state.",
        "review_state": "needs_human_review",
        "approval_state": "not_approved",
        "default_decision": "keep_preview_only",
        "read_only": true,
        "writes_memory": false,
        "writes_edges": false,
        "changes_search_order": false,
        "approval_writes_allowed": false,
        "can_materialize_edges": false,
        "can_change_retrieval_order": false,
        "input_contract": {
            "raw_queries_included": false,
            "raw_relevant_keys_included": false,
            "content_included": false,
            "query_cases_included": false,
        },
        "packet_source": {
            "generator": "biocortex_relevance_lift_fixture_eval",
            "fixture_path": fixture_path.display().to_string(),
            "fixture_schema": fixture.schema,
            "query_case_count": fixture.query_cases.len(),
        },
        "summary": {
            "preview_case_count": preview_case_count,
            "preview_candidate_count": preview_candidate_count,
            "reason_packet_selected_edge_count": reason_packet_selected_edge_count,
            "reason_packet_relevant_edge_count": reason_packet_relevant_edge_count,
            "reason_packet_blocked_packet_count": reason_packet_blocked_packet_count,
            "reason_packet_blocked_shadow_count": reason_packet_blocked_shadow_count,
        },
        "review_questions": [
            "Does the reason packet justify the proposed edge?",
            "Do the rank movements support keeping this candidate in preview-only review?",
            "Should this candidate remain non-materialized until a separate write path is explicitly approved?"
        ],
        "candidates": candidates,
    })
}

fn rank_of_key(ranking: &[String], key: &str) -> Option<usize> {
    ranking
        .iter()
        .position(|candidate| candidate == key)
        .map(|idx| idx + 1)
}

fn label_free_endpoint_metadata_allowed(record: &MemoryRecord) -> bool {
    if record.status != "active" {
        return false;
    }
    if record.importance >= 0.6 || record.access_count > 0 {
        return true;
    }
    matches!(
        record.kind.as_str(),
        "decision" | "lesson" | "session_handoff" | "context"
    )
}

fn label_free_scopes_compatible(a: Option<&str>, b: Option<&str>) -> bool {
    match (normalize_memory_scope(a), normalize_memory_scope(b)) {
        (None, _) | (_, None) => true,
        (Some(a), Some(b)) => a == b,
    }
}

fn normalize_memory_scope(scope: Option<&str>) -> Option<&str> {
    match scope.map(str::trim).filter(|scope| !scope.is_empty()) {
        None | Some("global") => None,
        Some(scope) => Some(scope),
    }
}

fn label_free_temporal_proximity(a_updated_at: i64, b_updated_at: i64) -> bool {
    const MAX_UPDATED_AT_DISTANCE_SECS: i64 = 30 * 24 * 60 * 60;
    a_updated_at
        .checked_sub(b_updated_at)
        .map(i64::abs)
        .is_some_and(|distance| distance <= MAX_UPDATED_AT_DISTANCE_SECS)
}

fn label_free_shadow_top3_preserved(
    baseline_hits: &[ab_store::MemorySearchHit],
    baseline_ranking: &[String],
    candidate_keys: &BTreeSet<String>,
    induced_edges: &[MemoryEdge],
    candidate: &MemoryEdge,
) -> bool {
    let baseline_prefix = baseline_ranking.iter().take(3).collect::<Vec<_>>();
    if baseline_prefix.is_empty() {
        return false;
    }
    let mut trial_edges = induced_edges.to_vec();
    trial_edges.push(candidate.clone());
    let trial_scores = score_graph_candidates(
        candidate_keys,
        &trial_edges,
        GraphScoreVariant::NonContinuityIncident,
    );
    let graph_signals = graph_scores_to_side_signal(&trial_scores);
    let (blend_hits, _, blend_available) =
        ab_store::biocortex_opt_in_apply_side_signal(baseline_hits, &graph_signals, 0.8, 0.0, true);
    if !blend_available {
        return false;
    }
    let blend_prefix = blend_hits
        .iter()
        .take(baseline_prefix.len())
        .map(|hit| &hit.record.key)
        .collect::<Vec<_>>();
    blend_prefix == baseline_prefix
}

fn collect_related_key_missing_edges(
    baseline_hits: &[ab_store::MemorySearchHit],
    candidate_keys: &BTreeSet<String>,
    induced_edges: &[MemoryEdge],
) -> Vec<MemoryEdge> {
    let existing_pairs = induced_edges
        .iter()
        .map(|edge| undirected_pair_key(&edge.from_key, &edge.to_key))
        .collect::<HashSet<_>>();
    let mut seen_pairs = existing_pairs.clone();
    let mut out = Vec::new();
    for hit in baseline_hits {
        let from_key = hit.record.key.trim();
        if !candidate_keys.contains(from_key) {
            continue;
        }
        for raw_target in &hit.record.related_keys {
            let to_key = raw_target.trim();
            if to_key.is_empty() || from_key == to_key || !candidate_keys.contains(to_key) {
                continue;
            }
            let pair_key = undirected_pair_key(from_key, to_key);
            if !seen_pairs.insert(pair_key) {
                continue;
            }
            out.push(MemoryEdge {
                from_key: from_key.to_string(),
                to_key: to_key.to_string(),
                edge_type: "relates".to_string(),
                weight: 1.0,
            });
        }
    }
    out
}

fn undirected_pair_key(a: &str, b: &str) -> (String, String) {
    if a <= b {
        (a.to_string(), b.to_string())
    } else {
        (b.to_string(), a.to_string())
    }
}

async fn collect_candidate_induced_edges(
    store: &SqliteStore,
    candidate_keys: &BTreeSet<String>,
) -> Result<Vec<MemoryEdge>> {
    let mut seen_edges = HashSet::<(String, String, String)>::new();
    let mut induced_edges = Vec::<MemoryEdge>::new();
    for key in candidate_keys {
        let neighbors = store
            .memory_neighbors(key)
            .await
            .with_context(|| format!("memory_neighbors for key {}", key))?;
        for edge in neighbors {
            if !candidate_keys.contains(&edge.from_key) || !candidate_keys.contains(&edge.to_key) {
                continue;
            }
            let dedupe_key = (
                edge.from_key.clone(),
                edge.to_key.clone(),
                edge.edge_type.clone(),
            );
            if seen_edges.insert(dedupe_key) {
                induced_edges.push(edge);
            }
        }
    }
    Ok(induced_edges)
}

async fn graph_hub_bfs_relevance(
    store: &SqliteStore,
    graph_scores: &[(String, f64)],
    relevant: &BTreeSet<String>,
) -> Result<(usize, Option<f64>)> {
    let mut reached = BTreeSet::<String>::new();
    let mut best_energy: Option<f64> = None;
    for (hub, _) in graph_scores.iter().take(5) {
        let rows = store
            .memory_neighbors_bfs(hub, 2, 0.7, 0.01)
            .await
            .with_context(|| format!("memory_neighbors_bfs for graph hub {}", hub))?;
        for (edge, energy) in rows {
            for endpoint in [&edge.from_key, &edge.to_key] {
                if relevant.contains(endpoint) {
                    reached.insert(endpoint.clone());
                    best_energy = Some(best_energy.map_or(energy, |best| best.max(energy)));
                }
            }
        }
    }
    Ok((reached.len(), best_energy))
}

fn best_relevant_coactivation_count(
    edges: &[CoactivationEdge],
    relevant: &BTreeSet<String>,
) -> Option<u64> {
    edges
        .iter()
        .filter(|edge| relevant.contains(&edge.key_a) || relevant.contains(&edge.key_b))
        .map(|edge| edge.count)
        .max()
}

fn semantic_relevant_position(
    query: &str,
    embedding_rows: &[(MemoryRecord, Vec<f32>)],
    relevant: &BTreeSet<String>,
) -> (Option<usize>, Option<f32>) {
    if query.trim().is_empty() || embedding_rows.is_empty() {
        return (None, None);
    }
    let query_vec = embed_text(query);
    if query_vec.is_empty() {
        return (None, None);
    }
    let mut rows = embedding_rows
        .iter()
        .map(|(record, embedding)| (record.key.clone(), cosine_similarity(&query_vec, embedding)))
        .collect::<Vec<_>>();
    rows.sort_by(|a, b| {
        b.1.partial_cmp(&a.1)
            .unwrap_or(Ordering::Equal)
            .then_with(|| a.0.cmp(&b.0))
    });
    rows.iter()
        .enumerate()
        .find(|(_, (key, _))| relevant.contains(key.as_str()))
        .map(|(idx, (_, cosine))| (Some(idx + 1), Some(*cosine)))
        .unwrap_or((None, None))
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
    summarize_graph_scores(
        variant.label(),
        baseline_hits,
        baseline_ranking,
        scores,
        source_key,
        relevant,
    )
}

fn summarize_graph_scores(
    label: &'static str,
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
        label,
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

async fn score_bounded_graph_proximity(
    store: &SqliteStore,
    candidate_keys: &BTreeSet<String>,
    induced_edges: &[MemoryEdge],
) -> Result<Vec<(String, f64)>> {
    let mut scores = candidate_keys
        .iter()
        .map(|key| (key.clone(), 0.0_f64))
        .collect::<BTreeMap<_, _>>();

    for edge in induced_edges {
        let cap = graph_edge_type_cap(&edge.edge_type);
        if cap <= 0.0 || !edge.weight.is_finite() || edge.weight <= 0.0 {
            continue;
        }
        let contribution = edge.weight.min(cap);
        if let Some(score) = scores.get_mut(&edge.to_key) {
            *score = (*score + contribution).min(1.0);
        }
        if let Some(score) = scores.get_mut(&edge.from_key) {
            *score = (*score + contribution * 0.7).min(1.0);
        }
    }

    let mut hubs = score_graph_candidates(
        candidate_keys,
        induced_edges,
        GraphScoreVariant::NonContinuityIncident,
    );
    if hubs.is_empty() {
        hubs = score_graph_candidates(
            candidate_keys,
            induced_edges,
            GraphScoreVariant::AllIncident,
        );
    }
    let mut seen_hub_endpoint = HashSet::<(String, String, String)>::new();
    for (hub, _) in hubs.iter().take(5) {
        let rows = store.memory_neighbors_bfs(hub, 2, 0.7, 0.01).await?;
        for (edge, energy) in rows {
            if !energy.is_finite() || energy <= 0.0 {
                continue;
            }
            let cap = graph_edge_type_cap(&edge.edge_type);
            if cap <= 0.0 {
                continue;
            }
            for endpoint in [&edge.from_key, &edge.to_key] {
                if endpoint == hub || !candidate_keys.contains(endpoint) {
                    continue;
                }
                let dedupe_key = (hub.clone(), endpoint.clone(), edge.edge_type.clone());
                if !seen_hub_endpoint.insert(dedupe_key) {
                    continue;
                }
                if let Some(score) = scores.get_mut(endpoint) {
                    *score = (*score + (energy * cap).min(0.35)).min(1.0);
                }
            }
        }
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
    Ok(out)
}

fn graph_edge_type_cap(edge_type: &str) -> f64 {
    if is_continuity_edge_type(edge_type) {
        0.10
    } else if matches!(edge_type, "conflicts" | "conflict" | "contradicts") {
        0.20
    } else {
        0.45
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
    preflight_rows: &[GraphPreflightCaseRow],
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
    println!("## Per-case missing-edge materialization candidate rows");
    println!(
        "{:<4} {:<34} {:>5} {:>8} {:>8}",
        "#", "class_label", "cand", "miss_e", "rel_hit"
    );
    for row in graph_rows {
        println!(
            "{:<4} {:<34} {:>5} {:>8} {:>8}",
            row.sample_index + 1,
            truncate(&row.class_label, 34),
            row.candidate_count,
            row.missing_edge_candidate_count,
            row.missing_edge_candidate_relevant_count,
        );
    }
    println!();
    println!("## Missing-edge materialization candidate summary");
    let candidate_cases = graph_rows
        .iter()
        .filter(|row| row.missing_edge_candidate_count > 0)
        .count();
    let relevant_candidate_cases = graph_rows
        .iter()
        .filter(|row| row.missing_edge_candidate_relevant_count > 0)
        .count();
    let total_candidates = graph_rows
        .iter()
        .map(|row| row.missing_edge_candidate_count)
        .sum::<usize>();
    let total_relevant_candidates = graph_rows
        .iter()
        .map(|row| row.missing_edge_candidate_relevant_count)
        .sum::<usize>();
    println!(
        "cases={} candidate_cases={} total_candidates={} relevant_candidate_cases={} total_relevant_candidates={}",
        graph_rows.len(),
        candidate_cases,
        total_candidates,
        relevant_candidate_cases,
        total_relevant_candidates,
    );
    println!();
    println!("## Per-case missing-edge quality gate rows");
    println!(
        "{:<4} {:<34} {:>7} {:>7} {:>9} {:>9}",
        "#", "class_label", "sel", "sel_rel", "blk_lbl", "blk_harm"
    );
    for row in graph_rows {
        println!(
            "{:<4} {:<34} {:>7} {:>7} {:>9} {:>9}",
            row.sample_index + 1,
            truncate(&row.class_label, 34),
            row.gated_edge_selected_count,
            row.gated_edge_relevant_count,
            row.gated_edge_blocked_label_count,
            row.gated_edge_blocked_harm_count,
        );
    }
    println!();
    println!("## Missing-edge quality gate summary");
    let selected_cases = graph_rows
        .iter()
        .filter(|row| row.gated_edge_selected_count > 0)
        .count();
    let total_selected = graph_rows
        .iter()
        .map(|row| row.gated_edge_selected_count)
        .sum::<usize>();
    let total_blocked_label = graph_rows
        .iter()
        .map(|row| row.gated_edge_blocked_label_count)
        .sum::<usize>();
    let total_blocked_harm = graph_rows
        .iter()
        .map(|row| row.gated_edge_blocked_harm_count)
        .sum::<usize>();
    println!(
        "cases={} selected_cases={} selected_edges={} blocked_no_relevance={} blocked_harm={}",
        graph_rows.len(),
        selected_cases,
        total_selected,
        total_blocked_label,
        total_blocked_harm,
    );
    println!();
    println!("## Per-case label-free missing-edge gate rows");
    println!(
        "{:<4} {:<34} {:>7} {:>7} {:>8} {:>7} {:>7} {:>8}",
        "#", "class_label", "sel", "sel_rel", "blk_meta", "blk_sc", "blk_tm", "blk_top3"
    );
    for row in graph_rows {
        println!(
            "{:<4} {:<34} {:>7} {:>7} {:>8} {:>7} {:>7} {:>8}",
            row.sample_index + 1,
            truncate(&row.class_label, 34),
            row.label_free_edge_selected_count,
            row.label_free_edge_relevant_count,
            row.label_free_edge_blocked_metadata_count,
            row.label_free_edge_blocked_scope_count,
            row.label_free_edge_blocked_temporal_count,
            row.label_free_edge_blocked_shadow_count,
        );
    }
    println!();
    println!("## Label-free missing-edge gate summary");
    let label_free_selected_cases = graph_rows
        .iter()
        .filter(|row| row.label_free_edge_selected_count > 0)
        .count();
    let label_free_relevant_cases = graph_rows
        .iter()
        .filter(|row| row.label_free_edge_relevant_count > 0)
        .count();
    let label_free_selected = graph_rows
        .iter()
        .map(|row| row.label_free_edge_selected_count)
        .sum::<usize>();
    let label_free_relevant = graph_rows
        .iter()
        .map(|row| row.label_free_edge_relevant_count)
        .sum::<usize>();
    let label_free_blocked_metadata = graph_rows
        .iter()
        .map(|row| row.label_free_edge_blocked_metadata_count)
        .sum::<usize>();
    let label_free_blocked_scope = graph_rows
        .iter()
        .map(|row| row.label_free_edge_blocked_scope_count)
        .sum::<usize>();
    let label_free_blocked_temporal = graph_rows
        .iter()
        .map(|row| row.label_free_edge_blocked_temporal_count)
        .sum::<usize>();
    let label_free_blocked_shadow = graph_rows
        .iter()
        .map(|row| row.label_free_edge_blocked_shadow_count)
        .sum::<usize>();
    println!(
        "cases={} selected_cases={} selected_edges={} relevant_cases={} relevant_edges={} blocked_metadata={} blocked_scope={} blocked_temporal={} blocked_top3={}",
        graph_rows.len(),
        label_free_selected_cases,
        label_free_selected,
        label_free_relevant_cases,
        label_free_relevant,
        label_free_blocked_metadata,
        label_free_blocked_scope,
        label_free_blocked_temporal,
        label_free_blocked_shadow,
    );
    println!();
    println!("## Per-case co-retrieval missing-edge gate rows");
    println!(
        "{:<4} {:<34} {:>7} {:>7} {:>9} {:>8}",
        "#", "class_label", "sel", "sel_rel", "blk_sig", "blk_top3"
    );
    for row in graph_rows {
        println!(
            "{:<4} {:<34} {:>7} {:>7} {:>9} {:>8}",
            row.sample_index + 1,
            truncate(&row.class_label, 34),
            row.coretrieval_edge_selected_count,
            row.coretrieval_edge_relevant_count,
            row.coretrieval_edge_blocked_signal_count,
            row.coretrieval_edge_blocked_shadow_count,
        );
    }
    println!();
    println!("## Co-retrieval missing-edge gate summary");
    let coretrieval_selected_cases = graph_rows
        .iter()
        .filter(|row| row.coretrieval_edge_selected_count > 0)
        .count();
    let coretrieval_relevant_cases = graph_rows
        .iter()
        .filter(|row| row.coretrieval_edge_relevant_count > 0)
        .count();
    let coretrieval_selected = graph_rows
        .iter()
        .map(|row| row.coretrieval_edge_selected_count)
        .sum::<usize>();
    let coretrieval_relevant = graph_rows
        .iter()
        .map(|row| row.coretrieval_edge_relevant_count)
        .sum::<usize>();
    let coretrieval_blocked_signal = graph_rows
        .iter()
        .map(|row| row.coretrieval_edge_blocked_signal_count)
        .sum::<usize>();
    let coretrieval_blocked_shadow = graph_rows
        .iter()
        .map(|row| row.coretrieval_edge_blocked_shadow_count)
        .sum::<usize>();
    println!(
        "cases={} selected_cases={} selected_edges={} relevant_cases={} relevant_edges={} blocked_signal={} blocked_top3={}",
        graph_rows.len(),
        coretrieval_selected_cases,
        coretrieval_selected,
        coretrieval_relevant_cases,
        coretrieval_relevant,
        coretrieval_blocked_signal,
        coretrieval_blocked_shadow,
    );
    println!();
    println!("## Per-case reason-packet missing-edge gate rows");
    println!(
        "{:<4} {:<34} {:>7} {:>7} {:>9} {:>8}",
        "#", "class_label", "sel", "sel_rel", "blk_pkt", "blk_align"
    );
    for row in graph_rows {
        println!(
            "{:<4} {:<34} {:>7} {:>7} {:>9} {:>8}",
            row.sample_index + 1,
            truncate(&row.class_label, 34),
            row.reason_packet_edge_selected_count,
            row.reason_packet_edge_relevant_count,
            row.reason_packet_blocked_packet_count,
            row.reason_packet_blocked_shadow_count,
        );
    }
    println!();
    println!("## Reason-packet missing-edge gate summary");
    let reason_packet_selected_cases = graph_rows
        .iter()
        .filter(|row| row.reason_packet_edge_selected_count > 0)
        .count();
    let reason_packet_relevant_cases = graph_rows
        .iter()
        .filter(|row| row.reason_packet_edge_relevant_count > 0)
        .count();
    let reason_packet_selected = graph_rows
        .iter()
        .map(|row| row.reason_packet_edge_selected_count)
        .sum::<usize>();
    let reason_packet_relevant = graph_rows
        .iter()
        .map(|row| row.reason_packet_edge_relevant_count)
        .sum::<usize>();
    let reason_packet_blocked_packet = graph_rows
        .iter()
        .map(|row| row.reason_packet_blocked_packet_count)
        .sum::<usize>();
    let reason_packet_blocked_shadow = graph_rows
        .iter()
        .map(|row| row.reason_packet_blocked_shadow_count)
        .sum::<usize>();
    println!(
        "cases={} selected_cases={} selected_edges={} relevant_cases={} relevant_edges={} blocked_packet={} blocked_align={}",
        graph_rows.len(),
        reason_packet_selected_cases,
        reason_packet_selected,
        reason_packet_relevant_cases,
        reason_packet_relevant,
        reason_packet_blocked_packet,
        reason_packet_blocked_shadow,
    );
    println!();
    println!("## Read-only reason-packet materialization preview artifact");
    let preview_count = graph_rows
        .iter()
        .map(|row| row.materialization_previews.len())
        .sum::<usize>();
    println!(
        "previews={} writes_memory=false changes_search_order=false",
        preview_count
    );
    for row in graph_rows {
        for preview in &row.materialization_previews {
            println!(
                "- case={} class={} gate={} source={} edge={} -> {} type={} reason_kind={} aligned={} from_rank={} to_rank={} top3={}=>{} preview_changed={} coverage={} writes_memory={} changes_search_order={} rationale={}",
                row.sample_index + 1,
                truncate(&row.class_label, 34),
                preview.gate,
                preview.candidate_source,
                truncate(&preview.from_key, 36),
                truncate(&preview.to_key, 36),
                preview.edge_type,
                preview.reason_kind,
                preview.shadow_aligned,
                rank_transition(preview.baseline_from_rank, preview.preview_from_rank),
                rank_transition(preview.baseline_to_rank, preview.preview_to_rank),
                top3_summary(&preview.baseline_top3),
                top3_summary(&preview.preview_top3),
                preview.preview_order_changed,
                format!("{:.3}", preview.blend_coverage),
                preview.writes_memory,
                preview.changes_search_order,
                truncate(&preview.rationale, 96),
            );
        }
    }
    println!();
    println!("## Graph side-signal blend simulation summary");
    println!(
        "{:<10} {:>5} {:>7} {:>8} {:>9} {:>8} {:>8} {:>9}",
        "variant", "avail", "changed", "improved", "worsened", "same", "mrr_d", "avg_cov"
    );
    let variant_labels = graph_rows
        .iter()
        .flat_map(|row| row.variants.iter().map(|variant| variant.label))
        .collect::<BTreeSet<_>>();
    for label in variant_labels {
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
    println!("## Graph proximity/materialization preflight rows");
    println!(
        "{:<4} {:<34} {:>5} {:>5} {:>7} {:>6} {:<18} {:>7} {:>7} {:>6} {:>8} {:>8} {:>8} {:>7}",
        "#",
        "class_label",
        "cand",
        "rel",
        "in_cand",
        "dir_e",
        "dir_types",
        "bfs_rel",
        "bfs_e",
        "coact",
        "coact_r",
        "coact_n",
        "sem_rank",
        "sem_cos"
    );
    for row in preflight_rows {
        println!(
            "{:<4} {:<34} {:>5} {:>5} {:>7} {:>6} {:<18} {:>7} {:>7} {:>6} {:>8} {:>8} {:>8} {:>7}",
            row.sample_index + 1,
            truncate(&row.class_label, 34),
            row.candidate_count,
            row.relevant_count,
            row.relevant_in_candidates,
            row.direct_relevant_edge_count,
            truncate(&edge_type_summary(&row.direct_relevant_edge_types), 18),
            row.bfs_relevant_reached,
            opt_f64(row.best_bfs_energy),
            row.coactivation_edge_count,
            row.coactivation_relevant_edge_count,
            opt_u64(row.best_relevant_coactivation_count),
            opt_usize(row.semantic_relevant_rank),
            opt_f32(row.semantic_relevant_cosine),
        );
    }
    println!();
    println!("## Graph proximity/materialization preflight summary");
    let total_cases = preflight_rows.len();
    let relevant_missing_from_candidates = preflight_rows
        .iter()
        .filter(|row| row.relevant_in_candidates == 0)
        .count();
    let direct_edge_cases = preflight_rows
        .iter()
        .filter(|row| row.direct_relevant_edge_count > 0)
        .count();
    let bfs_reachable_cases = preflight_rows
        .iter()
        .filter(|row| row.bfs_relevant_reached > 0)
        .count();
    let coactivation_cases = preflight_rows
        .iter()
        .filter(|row| row.coactivation_relevant_edge_count > 0)
        .count();
    let semantic_top20_cases = preflight_rows
        .iter()
        .filter(|row| row.semantic_relevant_rank.is_some_and(|rank| rank <= 20))
        .count();
    let semantic_rows = preflight_rows
        .first()
        .map(|row| row.semantic_embedding_count)
        .unwrap_or(0);
    println!(
        "cases={} missing_candidate={} direct_edge={} bfs_reachable={} coactivation={} semantic_top20={} embedding_rows={}",
        total_cases,
        relevant_missing_from_candidates,
        direct_edge_cases,
        bfs_reachable_cases,
        coactivation_cases,
        semantic_top20_cases,
        semantic_rows,
    );
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
        "- Compare graph variants: `incoming` and `outgoing` test directionality, `non_cont` excludes continuity/provenance edge types, `cont_only` isolates them, and `bounded_prox` applies edge-type caps plus hub BFS energy."
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
    println!(
        "- Missing-edge candidates come only from explicit `related_keys` among baseline candidates. `rel_hit` is post-hoc label evaluation, not an input to candidate generation."
    );
    println!(
        "- Compare `related_mat` and `bounded_mat` with their non-materialized baselines before considering any write-capable edge materializer."
    );
    println!(
        "- In the preflight table, `in_cand=0` points to candidate-generation limits; `dir_e=0` with strong `sem_rank` points to missing materialized graph edges."
    );
    println!(
        "- `bfs_rel` and `coact_r` distinguish graph-proximity evidence from semantic-only evidence before deciding whether to materialize new edges."
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

fn now_secs() -> u64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|duration| duration.as_secs())
        .unwrap_or(0)
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

fn opt_u64(value: Option<u64>) -> String {
    value
        .map(|value| value.to_string())
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

fn rank_transition(before: Option<usize>, after: Option<usize>) -> String {
    format!("{}->{}", opt_usize(before), opt_usize(after))
}

fn top3_summary(keys: &[String]) -> String {
    if keys.is_empty() {
        return "-".to_string();
    }
    keys.iter()
        .map(|key| truncate(key, 18))
        .collect::<Vec<_>>()
        .join(">")
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

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn reason_packet_gate_emits_read_only_materialization_preview() {
        let baseline_hits = vec![
            test_hit("anchor_a", 1.00),
            test_hit("anchor_b", 0.95),
            test_hit("from_key", 0.40),
            test_hit("to_key", 0.35),
        ];
        let baseline_ranking = baseline_hits
            .iter()
            .map(|hit| hit.record.key.clone())
            .collect::<Vec<_>>();
        let candidate_keys = baseline_ranking.iter().cloned().collect::<BTreeSet<_>>();
        let candidate = MemoryEdge {
            from_key: "from_key".to_string(),
            to_key: "to_key".to_string(),
            edge_type: "relates".to_string(),
            weight: 1.0,
        };
        let packet = MaterializationReasonPacket {
            from_key: "from_key".to_string(),
            to_key: "to_key".to_string(),
            edge_type: "relates".to_string(),
            reason_kind: "operator_review_intent".to_string(),
            rationale: "reviewer supplied provenance rationale".to_string(),
            status: "active".to_string(),
        };

        let gate = select_reason_packet_quality_edges(
            &baseline_hits,
            &baseline_ranking,
            &candidate_keys,
            &[],
            &[candidate],
            &[packet],
        );

        assert_eq!(gate.selected_edges.len(), 1);
        assert_eq!(gate.preview_rows.len(), 1);
        let preview = &gate.preview_rows[0];
        assert_eq!(preview.candidate_source, "explicit_related_keys");
        assert_eq!(preview.gate, "reason_packet");
        assert_eq!(preview.from_key, "from_key");
        assert_eq!(preview.to_key, "to_key");
        assert_eq!(preview.edge_type, "relates");
        assert_eq!(preview.reason_kind, "operator_review_intent");
        assert_eq!(preview.rationale, "reviewer supplied provenance rationale");
        assert!(preview.shadow_aligned);
        assert_eq!(
            preview.baseline_top3,
            vec![
                "anchor_a".to_string(),
                "anchor_b".to_string(),
                "from_key".to_string()
            ]
        );
        assert_eq!(
            preview.preview_top3,
            vec![
                "from_key".to_string(),
                "to_key".to_string(),
                "anchor_a".to_string()
            ]
        );
        assert_eq!(preview.baseline_from_rank, Some(3));
        assert_eq!(preview.preview_from_rank, Some(1));
        assert_eq!(preview.baseline_to_rank, Some(4));
        assert_eq!(preview.preview_to_rank, Some(2));
        assert!(!preview.writes_memory);
        assert!(!preview.changes_search_order);
    }

    #[test]
    fn materialization_review_packet_is_read_only_and_redacted() {
        let fixture = Fixture {
            schema: "agent_bridge.memory_biocortex.relevance_lift_missing_graph_cases.v0"
                .to_string(),
            query_cases: vec![FixtureCase {
                query: "secret packet query".to_string(),
                relevant_keys: vec!["secret_relevant_key".to_string()],
                class_label: Some("packet_case".to_string()),
                baseline_fts_rank_observed: Some(4),
                review_intent: None,
                materialization_reason_packets: Vec::new(),
            }],
        };
        let graph_rows = vec![GraphEvidenceCaseRow {
            sample_index: 0,
            class_label: "packet_case".to_string(),
            candidate_count: 4,
            induced_edge_count: 0,
            induced_node_count: 0,
            missing_edge_candidate_count: 1,
            missing_edge_candidate_relevant_count: 1,
            gated_edge_selected_count: 0,
            gated_edge_relevant_count: 0,
            gated_edge_blocked_label_count: 0,
            gated_edge_blocked_harm_count: 0,
            label_free_edge_selected_count: 0,
            label_free_edge_relevant_count: 0,
            label_free_edge_blocked_metadata_count: 0,
            label_free_edge_blocked_scope_count: 0,
            label_free_edge_blocked_temporal_count: 0,
            label_free_edge_blocked_shadow_count: 0,
            coretrieval_edge_selected_count: 0,
            coretrieval_edge_relevant_count: 0,
            coretrieval_edge_blocked_signal_count: 0,
            coretrieval_edge_blocked_shadow_count: 0,
            reason_packet_edge_selected_count: 1,
            reason_packet_edge_relevant_count: 1,
            reason_packet_blocked_packet_count: 0,
            reason_packet_blocked_shadow_count: 0,
            source_graph_rank: None,
            source_graph_score: None,
            best_relevant_graph_rank: None,
            best_relevant_graph_score: None,
            top_graph_relevant: false,
            top_graph_score: None,
            distinct_graph_scores: 0,
            edge_type_counts: BTreeMap::new(),
            variants: Vec::new(),
            materialization_previews: vec![MaterializationPreviewRow {
                candidate_source: "explicit_related_keys",
                gate: "reason_packet",
                from_key: "preview_from".to_string(),
                to_key: "preview_to".to_string(),
                edge_type: "relates".to_string(),
                reason_kind: "operator_review_intent".to_string(),
                rationale: "preview-only rationale".to_string(),
                shadow_aligned: true,
                baseline_top3: vec!["anchor_a".to_string(), "anchor_b".to_string()],
                preview_top3: vec!["preview_from".to_string(), "preview_to".to_string()],
                baseline_from_rank: Some(3),
                preview_from_rank: Some(1),
                baseline_to_rank: Some(4),
                preview_to_rank: Some(2),
                preview_order_changed: true,
                blend_coverage: 0.2,
                writes_memory: false,
                changes_search_order: false,
            }],
        }];

        let packet = materialization_review_packet(
            &PathBuf::from("docs/design/fixtures/example.json"),
            &fixture,
            &graph_rows,
        );

        assert_eq!(
            packet["schema"],
            Value::String(
                "agent_bridge.biocortex_retrieval.materialization_review_packet.v0".to_string()
            )
        );
        assert_eq!(packet["read_only"], Value::Bool(true));
        assert_eq!(packet["approval_writes_allowed"], Value::Bool(false));
        assert_eq!(packet["can_materialize_edges"], Value::Bool(false));
        assert_eq!(packet["changes_search_order"], Value::Bool(false));
        assert_eq!(packet["summary"]["preview_candidate_count"], Value::from(1));
        assert_eq!(packet["summary"]["preview_case_count"], Value::from(1));
        assert_eq!(
            packet["candidates"][0]["from_key"],
            Value::String("preview_from".to_string())
        );
        assert_eq!(
            packet["candidates"][0]["baseline_from_rank"],
            Value::from(3)
        );
        assert_eq!(packet["candidates"][0]["writes_memory"], Value::Bool(false));

        let serialized = serde_json::to_string(&packet).expect("serialize");
        assert!(!serialized.contains("secret packet query"));
        assert!(!serialized.contains("secret_relevant_key"));
        assert!(!serialized.contains("\"query_cases\""));
    }

    fn test_hit(key: &str, score: f64) -> ab_store::MemorySearchHit {
        ab_store::MemorySearchHit {
            record: MemoryRecord {
                key: key.to_string(),
                kind: "lesson".to_string(),
                content: String::new(),
                tags: Vec::new(),
                related_keys: Vec::new(),
                scope: None,
                created_at: 0,
                updated_at: 0,
                last_accessed_at: 0,
                access_count: 0,
                importance: 0.5,
                status: "active".to_string(),
                trigger_pattern: None,
                superseded_by: None,
            },
            score,
            cosine: None,
        }
    }
}
