//! SpecFormer-inspired memory graph shadow probe.
//!
//! This is a read-only offline probe. It opens Agent-Bridge `state.db` with
//! SQLite query-only flags, builds a bounded memory graph, computes a dense
//! normalized-Laplacian spectrum, and emits either a markdown diagnostics report
//! or JSONL side-signal rows with opaque memory identifiers.
//!
//! It is not a full SpecFormer implementation: no Transformer is trained or run.
//! The probe tests the first measurable premise from SpecFormer for AB memory:
//! whether graph-frequency coordinates provide a useful side signal worth
//! feeding into the existing retrieval gate harness later.
//!
//! Run:
//!   cargo run -q -p ab-bridge --no-default-features --example specformer_memory_shadow
//!
//! Optional:
//!   SPECFORMER_SHADOW_SEEDS=abmkey:sha256:<digest>,abmkey:sha256:<digest> \
//!   SPECFORMER_SHADOW_FORMAT=jsonl \
//!   cargo run -q -p ab-bridge --no-default-features --example specformer_memory_shadow

use ab_store::{default_db_path, MemoryListSort, MemoryRecord, SqliteStore, StateStore};
use anyhow::Context;
use serde::Serialize;
use std::collections::{HashMap, HashSet, VecDeque};
use std::path::PathBuf;

#[path = "specformer_support/opaque_ids.rs"]
mod opaque_ids;

use opaque_ids::{is_opaque_memory_id, opaque_memory_id};

const DEFAULT_MAX_NODES: usize = 160;
const DEFAULT_EIGEN_K: usize = 8;
const DEFAULT_TOP_M: usize = 8;
const DEFAULT_RELATED_EDGE_WEIGHT: f64 = 1.5;
const SOURCE_MEMORY_EDGE: u8 = 0b01;
const SOURCE_RELATED_KEY: u8 = 0b10;
const ZERO_EIGEN_TOL: f64 = 1e-7;

#[derive(Debug, Clone)]
struct GraphNode {
    record: MemoryRecord,
    degree: f64,
    component: usize,
}

#[derive(Debug, Clone)]
struct GraphEdge {
    a: usize,
    b: usize,
    weight: f64,
    source_mask: u8,
}

#[derive(Debug, Clone)]
struct SpectralBasis {
    eigenvalues: Vec<f64>,
    coords: Vec<Vec<f64>>,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
enum GraphMode {
    EdgeOnly,
    RelatedHybrid,
    RelatedOnly,
}

impl GraphMode {
    fn as_str(self) -> &'static str {
        match self {
            GraphMode::EdgeOnly => "edge-only",
            GraphMode::RelatedHybrid => "related-hybrid",
            GraphMode::RelatedOnly => "related-only",
        }
    }

    fn includes_memory_edges(self) -> bool {
        matches!(self, GraphMode::EdgeOnly | GraphMode::RelatedHybrid)
    }

    fn includes_related_keys(self) -> bool {
        matches!(self, GraphMode::RelatedHybrid | GraphMode::RelatedOnly)
    }
}

#[derive(Debug, Clone, Copy)]
struct GraphConfig {
    mode: GraphMode,
    related_edge_weight: f64,
}

#[derive(Debug, Clone, Copy)]
struct PendingEdge {
    weight: f64,
    source_mask: u8,
}

#[derive(Debug, Serialize)]
struct SideSignalRow {
    query_id: String,
    candidate_key: String,
    score: f64,
}

#[tokio::main(flavor = "current_thread")]
async fn main() -> anyhow::Result<()> {
    let db_path = env_path("AGENT_BRIDGE_DB").unwrap_or_else(default_db_path);
    let max_nodes = env_usize("SPECFORMER_SHADOW_MAX_NODES", DEFAULT_MAX_NODES).clamp(16, 500);
    let eigen_k = env_usize("SPECFORMER_SHADOW_K", DEFAULT_EIGEN_K).clamp(2, 32);
    let top_m = env_usize("SPECFORMER_SHADOW_TOP_M", DEFAULT_TOP_M).clamp(1, 50);
    let graph_config = graph_config()?;
    let format = std::env::var("SPECFORMER_SHADOW_FORMAT")
        .unwrap_or_else(|_| "markdown".to_string())
        .trim()
        .to_ascii_lowercase();

    let store = SqliteStore::open_read_only(&db_path)
        .await
        .with_context(|| format!("open read-only state db {}", db_path.display()))?;
    let (nodes, edges) = load_graph(&store, max_nodes, graph_config).await?;
    anyhow::ensure!(
        nodes.len() >= 4,
        "memory graph sample too small after filters: {} nodes",
        nodes.len()
    );

    let adjacency = adjacency_matrix(nodes.len(), &edges);
    let degrees = degrees(&adjacency);
    let components = components(&adjacency);
    let nodes = nodes
        .into_iter()
        .enumerate()
        .map(|(idx, record)| GraphNode {
            record,
            degree: degrees[idx],
            component: components[idx],
        })
        .collect::<Vec<_>>();
    let basis = spectral_basis(&adjacency, eigen_k)?;

    match format.as_str() {
        "jsonl" => print_jsonl_side_signal(&nodes, &basis, top_m)?,
        "json" => print_json_report(&db_path, &nodes, &edges, &basis, top_m, graph_config)?,
        _ => print_markdown_report(&db_path, &nodes, &edges, &basis, top_m, graph_config)?,
    }
    Ok(())
}

async fn load_graph(
    store: &SqliteStore,
    max_nodes: usize,
    graph_config: GraphConfig,
) -> anyhow::Result<(Vec<MemoryRecord>, Vec<GraphEdge>)> {
    let skip_kinds = env_list(
        "SPECFORMER_SHADOW_SKIP_KINDS",
        &["skill", "work_memory", "session_handoff", "snapshot"],
    );
    let records = store
        .list_memories(None, MemoryListSort::ByImportance, (max_nodes as u32) * 5)
        .await
        .context("list memories")?
        .into_iter()
        .filter(|record| record.status == "active")
        .filter(|record| !skip_kinds.contains(&record.kind))
        .take(max_nodes)
        .collect::<Vec<_>>();
    let index = records
        .iter()
        .enumerate()
        .map(|(idx, record)| (record.key.clone(), idx))
        .collect::<HashMap<_, _>>();

    let mut edge_weights: HashMap<(usize, usize), PendingEdge> = HashMap::new();
    if graph_config.mode.includes_memory_edges() {
        for record in &records {
            let Some(&from_idx) = index.get(&record.key) else {
                continue;
            };
            for edge in store
                .memory_neighbors(&record.key)
                .await
                .unwrap_or_default()
            {
                let other_key = if edge.from_key == record.key {
                    &edge.to_key
                } else {
                    &edge.from_key
                };
                let Some(&to_idx) = index.get(other_key) else {
                    continue;
                };
                upsert_edge(
                    &mut edge_weights,
                    from_idx,
                    to_idx,
                    edge.weight.clamp(0.0, 2.0),
                    SOURCE_MEMORY_EDGE,
                );
            }
        }
    }

    if graph_config.mode.includes_related_keys() {
        for record in &records {
            let Some(&from_idx) = index.get(&record.key) else {
                continue;
            };
            for related_key in &record.related_keys {
                let Some(&to_idx) = index.get(related_key) else {
                    continue;
                };
                upsert_edge(
                    &mut edge_weights,
                    from_idx,
                    to_idx,
                    graph_config.related_edge_weight,
                    SOURCE_RELATED_KEY,
                );
            }
        }
    }

    let mut edges = edge_weights
        .into_iter()
        .map(|((a, b), edge)| GraphEdge {
            a,
            b,
            weight: edge.weight,
            source_mask: edge.source_mask,
        })
        .collect::<Vec<_>>();
    edges.sort_by(|left, right| {
        right
            .weight
            .partial_cmp(&left.weight)
            .unwrap_or(std::cmp::Ordering::Equal)
            .then_with(|| left.a.cmp(&right.a))
            .then_with(|| left.b.cmp(&right.b))
    });
    Ok((records, edges))
}

fn upsert_edge(
    edge_weights: &mut HashMap<(usize, usize), PendingEdge>,
    from_idx: usize,
    to_idx: usize,
    weight: f64,
    source_mask: u8,
) {
    if from_idx == to_idx || weight <= 0.0 {
        return;
    }
    let (a, b) = ordered_pair(from_idx, to_idx);
    edge_weights
        .entry((a, b))
        .and_modify(|current| {
            current.weight = current.weight.max(weight);
            current.source_mask |= source_mask;
        })
        .or_insert(PendingEdge {
            weight,
            source_mask,
        });
}

fn adjacency_matrix(n: usize, edges: &[GraphEdge]) -> Vec<Vec<f64>> {
    let mut a = vec![vec![0.0; n]; n];
    for edge in edges {
        a[edge.a][edge.b] += edge.weight;
        a[edge.b][edge.a] += edge.weight;
    }
    a
}

fn degrees(adjacency: &[Vec<f64>]) -> Vec<f64> {
    adjacency
        .iter()
        .map(|row| row.iter().copied().sum::<f64>())
        .collect()
}

fn components(adjacency: &[Vec<f64>]) -> Vec<usize> {
    let n = adjacency.len();
    let mut labels = vec![usize::MAX; n];
    let mut next_label = 0usize;
    for start in 0..n {
        if labels[start] != usize::MAX {
            continue;
        }
        let mut queue = VecDeque::from([start]);
        labels[start] = next_label;
        while let Some(node) = queue.pop_front() {
            for (next, weight) in adjacency[node].iter().enumerate() {
                if *weight > 0.0 && labels[next] == usize::MAX {
                    labels[next] = next_label;
                    queue.push_back(next);
                }
            }
        }
        next_label += 1;
    }
    labels
}

fn spectral_basis(adjacency: &[Vec<f64>], eigen_k: usize) -> anyhow::Result<SpectralBasis> {
    let n = adjacency.len();
    let degree = degrees(adjacency);
    let mut laplacian = vec![vec![0.0; n]; n];
    for i in 0..n {
        laplacian[i][i] = if degree[i] > 0.0 { 1.0 } else { 0.0 };
    }
    for i in 0..n {
        if degree[i] <= 0.0 {
            continue;
        }
        for j in 0..n {
            if i == j || adjacency[i][j] <= 0.0 || degree[j] <= 0.0 {
                continue;
            }
            laplacian[i][j] = -adjacency[i][j] / (degree[i].sqrt() * degree[j].sqrt());
        }
    }

    let (eigenvalues, eigenvectors) = jacobi_eigen(laplacian, 20_000, 1e-10);
    let mut pairs = eigenvalues
        .into_iter()
        .enumerate()
        .map(|(idx, value)| (idx, value.max(0.0)))
        .collect::<Vec<_>>();
    pairs.sort_by(|left, right| {
        left.1
            .partial_cmp(&right.1)
            .unwrap_or(std::cmp::Ordering::Equal)
    });

    let selected = pairs
        .iter()
        .filter(|(_, value)| *value > ZERO_EIGEN_TOL)
        .take(eigen_k)
        .copied()
        .collect::<Vec<_>>();
    anyhow::ensure!(
        !selected.is_empty(),
        "no non-trivial eigenvectors found in graph sample"
    );

    let eigenvalues = selected.iter().map(|(_, value)| *value).collect::<Vec<_>>();
    let mut coords = vec![vec![0.0; selected.len()]; n];
    for (dim, (eigen_idx, value)) in selected.iter().enumerate() {
        let scale = 1.0 / value.max(1e-6).sqrt();
        for node in 0..n {
            coords[node][dim] = eigenvectors[node][*eigen_idx] * scale;
        }
    }
    Ok(SpectralBasis {
        eigenvalues,
        coords,
    })
}

fn jacobi_eigen(
    mut a: Vec<Vec<f64>>,
    max_rotations: usize,
    tolerance: f64,
) -> (Vec<f64>, Vec<Vec<f64>>) {
    let n = a.len();
    let mut v = vec![vec![0.0; n]; n];
    for i in 0..n {
        v[i][i] = 1.0;
    }

    for _ in 0..max_rotations {
        let mut p = 0usize;
        let mut q = 1usize.min(n.saturating_sub(1));
        let mut max_offdiag = 0.0f64;
        for i in 0..n {
            for j in (i + 1)..n {
                let value = a[i][j].abs();
                if value > max_offdiag {
                    max_offdiag = value;
                    p = i;
                    q = j;
                }
            }
        }
        if max_offdiag < tolerance || p == q {
            break;
        }

        let app = a[p][p];
        let aqq = a[q][q];
        let apq = a[p][q];
        if apq.abs() < tolerance {
            continue;
        }
        let tau = (aqq - app) / (2.0 * apq);
        let t = tau.signum() / (tau.abs() + (1.0 + tau * tau).sqrt());
        let c = 1.0 / (1.0 + t * t).sqrt();
        let s = t * c;

        for i in 0..n {
            if i == p || i == q {
                continue;
            }
            let aip = a[i][p];
            let aiq = a[i][q];
            let new_ip = c * aip - s * aiq;
            let new_iq = s * aip + c * aiq;
            a[i][p] = new_ip;
            a[p][i] = new_ip;
            a[i][q] = new_iq;
            a[q][i] = new_iq;
        }

        a[p][p] = c * c * app - 2.0 * s * c * apq + s * s * aqq;
        a[q][q] = s * s * app + 2.0 * s * c * apq + c * c * aqq;
        a[p][q] = 0.0;
        a[q][p] = 0.0;

        for row in &mut v {
            let vip = row[p];
            let viq = row[q];
            row[p] = c * vip - s * viq;
            row[q] = s * vip + c * viq;
        }
    }

    let eigenvalues = (0..n).map(|i| a[i][i]).collect::<Vec<_>>();
    (eigenvalues, v)
}

fn print_jsonl_side_signal(
    nodes: &[GraphNode],
    basis: &SpectralBasis,
    top_m: usize,
) -> anyhow::Result<()> {
    let seeds = seed_indices(nodes)?;
    for seed in seeds {
        for candidate in spectral_neighbors(seed, nodes, basis, top_m) {
            let row = SideSignalRow {
                query_id: opaque_memory_id(&nodes[seed].record.key),
                candidate_key: opaque_memory_id(&nodes[candidate.0].record.key),
                score: candidate.1,
            };
            println!("{}", serde_json::to_string(&row)?);
        }
    }
    Ok(())
}

fn print_json_report(
    db_path: &PathBuf,
    nodes: &[GraphNode],
    edges: &[GraphEdge],
    basis: &SpectralBasis,
    top_m: usize,
    graph_config: GraphConfig,
) -> anyhow::Result<()> {
    let seeds = seed_indices(nodes)?;
    let side_signal_preview = seeds
        .iter()
        .flat_map(|seed| {
            spectral_neighbors(*seed, nodes, basis, top_m)
                .into_iter()
                .map(move |(idx, score)| {
                    serde_json::json!({
                        "query_id": opaque_memory_id(&nodes[*seed].record.key),
                        "candidate_key": opaque_memory_id(&nodes[idx].record.key),
                        "score": score,
                    })
                })
        })
        .collect::<Vec<_>>();
    let summary = report_summary(db_path, nodes, edges, basis, graph_config);
    println!(
        "{}",
        serde_json::to_string_pretty(&serde_json::json!({
            "summary": summary,
            "side_signal_preview": side_signal_preview,
        }))?
    );
    Ok(())
}

fn print_markdown_report(
    db_path: &PathBuf,
    nodes: &[GraphNode],
    edges: &[GraphEdge],
    basis: &SpectralBasis,
    top_m: usize,
    graph_config: GraphConfig,
) -> anyhow::Result<()> {
    let seeds = seed_indices(nodes)?;
    let summary = report_summary(db_path, nodes, edges, basis, graph_config);
    println!("# SpecFormer Memory Shadow");
    println!();
    println!("```json");
    println!("{}", serde_json::to_string_pretty(&summary)?);
    println!("```");
    println!();
    println!("## Low-Frequency Spectrum");
    println!();
    println!("| rank | lambda |");
    println!("|---:|---:|");
    for (idx, value) in basis.eigenvalues.iter().enumerate() {
        println!("| {} | {:.6} |", idx + 1, value);
    }
    println!();

    println!("## Spectral Side-Signal Preview");
    println!();
    for seed in seeds {
        println!("### `{}`", opaque_memory_id(&nodes[seed].record.key));
        println!();
        println!("| candidate | score | kind | component |");
        println!("|---|---:|---|---:|");
        for (idx, score) in spectral_neighbors(seed, nodes, basis, top_m) {
            println!(
                "| `{}` | {:.4} | {} | {} |",
                opaque_memory_id(&nodes[idx].record.key),
                score,
                nodes[idx].record.kind,
                nodes[idx].component
            );
        }
        println!();
    }
    Ok(())
}

fn report_summary(
    db_path: &PathBuf,
    nodes: &[GraphNode],
    edges: &[GraphEdge],
    basis: &SpectralBasis,
    graph_config: GraphConfig,
) -> serde_json::Value {
    let mut component_sizes = HashMap::<usize, usize>::new();
    for node in nodes {
        *component_sizes.entry(node.component).or_default() += 1;
    }
    let largest_component = component_sizes.values().copied().max().unwrap_or(0);
    let isolate_count = nodes.iter().filter(|node| node.degree == 0.0).count();
    let spectral_gap = basis.eigenvalues.first().copied().unwrap_or(0.0);
    let memory_edge_count = edges
        .iter()
        .filter(|edge| edge.source_mask & SOURCE_MEMORY_EDGE != 0)
        .count();
    let related_edge_count = edges
        .iter()
        .filter(|edge| edge.source_mask & SOURCE_RELATED_KEY != 0)
        .count();
    let hybrid_edge_count = edges
        .iter()
        .filter(|edge| edge.source_mask == (SOURCE_MEMORY_EDGE | SOURCE_RELATED_KEY))
        .count();
    serde_json::json!({
        "schema": "agent_bridge.specformer_memory_shadow.v0",
        "db_path": db_path.display().to_string(),
        "read_only": true,
        "default_search_order_changed": false,
        "runtime_adapter_approved": false,
        "model_claim": "spectral-token shadow probe only; no Transformer is trained or run",
        "graph_mode": graph_config.mode.as_str(),
        "related_edge_weight": graph_config.related_edge_weight,
        "node_count": nodes.len(),
        "edge_count": edges.len(),
        "memory_edge_count": memory_edge_count,
        "related_edge_count": related_edge_count,
        "hybrid_edge_count": hybrid_edge_count,
        "component_count": component_sizes.len(),
        "largest_component": largest_component,
        "isolate_count": isolate_count,
        "spectral_gap_proxy": spectral_gap,
        "eigen_k": basis.eigenvalues.len(),
    })
}

fn seed_indices(nodes: &[GraphNode]) -> anyhow::Result<Vec<usize>> {
    let by_id = nodes
        .iter()
        .enumerate()
        .map(|(idx, node)| (opaque_memory_id(&node.record.key), idx))
        .collect::<HashMap<_, _>>();
    if let Ok(raw) = std::env::var("SPECFORMER_SHADOW_SEEDS") {
        let mut seeds = Vec::new();
        for id in raw.split(',').map(str::trim).filter(|id| !id.is_empty()) {
            anyhow::ensure!(
                is_opaque_memory_id(id),
                "seed must use the abmkey:sha256 opaque-id contract"
            );
            let Some(&idx) = by_id.get(id) else {
                anyhow::bail!("opaque seed id not present in sampled graph: {id}");
            };
            seeds.push(idx);
        }
        anyhow::ensure!(!seeds.is_empty(), "no seed keys provided");
        return Ok(seeds);
    }

    Ok(nodes
        .iter()
        .enumerate()
        .filter(|(_, node)| node.degree > 0.0)
        .take(3)
        .map(|(idx, _)| idx)
        .collect())
}

fn spectral_neighbors(
    seed: usize,
    nodes: &[GraphNode],
    basis: &SpectralBasis,
    top_m: usize,
) -> Vec<(usize, f64)> {
    let mut scored = Vec::new();
    for idx in 0..nodes.len() {
        if idx == seed || nodes[idx].degree == 0.0 {
            continue;
        }
        let distance = squared_distance(&basis.coords[seed], &basis.coords[idx]).sqrt();
        let component_bonus = if nodes[idx].component == nodes[seed].component {
            1.0
        } else {
            0.65
        };
        let score = (component_bonus / (1.0 + distance)).clamp(0.0, 1.0);
        scored.push((idx, round4(score)));
    }
    scored.sort_by(|left, right| {
        right
            .1
            .partial_cmp(&left.1)
            .unwrap_or(std::cmp::Ordering::Equal)
            .then_with(|| nodes[left.0].record.key.cmp(&nodes[right.0].record.key))
    });
    scored.truncate(top_m);
    scored
}

fn squared_distance(a: &[f64], b: &[f64]) -> f64 {
    a.iter()
        .zip(b.iter())
        .map(|(left, right)| (left - right).powi(2))
        .sum()
}

fn env_path(key: &str) -> Option<PathBuf> {
    std::env::var_os(key).map(PathBuf::from)
}

fn env_usize(key: &str, default: usize) -> usize {
    std::env::var(key)
        .ok()
        .and_then(|value| value.parse().ok())
        .unwrap_or(default)
}

fn env_f64(key: &str, default: f64) -> f64 {
    std::env::var(key)
        .ok()
        .and_then(|value| value.parse().ok())
        .unwrap_or(default)
}

fn env_list(key: &str, default: &[&str]) -> HashSet<String> {
    let raw = std::env::var(key).unwrap_or_else(|_| default.join(","));
    raw.split(',')
        .map(str::trim)
        .filter(|value| !value.is_empty())
        .map(ToOwned::to_owned)
        .collect()
}

fn ordered_pair(left: usize, right: usize) -> (usize, usize) {
    if left <= right {
        (left, right)
    } else {
        (right, left)
    }
}

fn graph_config() -> anyhow::Result<GraphConfig> {
    let mode = parse_graph_mode(
        &std::env::var("SPECFORMER_SHADOW_GRAPH_MODE").unwrap_or_else(|_| "edge-only".to_string()),
    )?;
    let related_edge_weight = env_f64(
        "SPECFORMER_SHADOW_RELATED_WEIGHT",
        DEFAULT_RELATED_EDGE_WEIGHT,
    )
    .clamp(0.0, 2.0);
    Ok(GraphConfig {
        mode,
        related_edge_weight,
    })
}

fn parse_graph_mode(raw: &str) -> anyhow::Result<GraphMode> {
    match raw.trim().to_ascii_lowercase().as_str() {
        "edge-only" | "edges" | "memory" | "memory-only" => Ok(GraphMode::EdgeOnly),
        "related-hybrid" | "hybrid" | "memory+related" | "edges+related" => {
            Ok(GraphMode::RelatedHybrid)
        }
        "related-only" | "related" => Ok(GraphMode::RelatedOnly),
        other => anyhow::bail!(
            "unsupported SPECFORMER_SHADOW_GRAPH_MODE={other}; use edge-only, related-hybrid, or related-only"
        ),
    }
}

fn round4(value: f64) -> f64 {
    (value * 10_000.0).round() / 10_000.0
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn jacobi_eigen_recovers_simple_diagonal() {
        let matrix = vec![vec![2.0, 0.0], vec![0.0, 5.0]];
        let (mut values, _) = jacobi_eigen(matrix, 10, 1e-12);
        values.sort_by(|a, b| a.partial_cmp(b).unwrap());
        assert!((values[0] - 2.0).abs() < 1e-9);
        assert!((values[1] - 5.0).abs() < 1e-9);
    }

    #[test]
    fn two_node_connected_graph_has_one_nontrivial_frequency() {
        let adjacency = vec![vec![0.0, 1.0], vec![1.0, 0.0]];
        let basis = spectral_basis(&adjacency, 4).expect("basis");
        assert_eq!(basis.eigenvalues.len(), 1);
        assert!((basis.eigenvalues[0] - 2.0).abs() < 1e-6);
    }

    #[test]
    fn components_labels_isolates_separately() {
        let adjacency = vec![
            vec![0.0, 1.0, 0.0],
            vec![1.0, 0.0, 0.0],
            vec![0.0, 0.0, 0.0],
        ];
        let labels = components(&adjacency);
        assert_eq!(labels[0], labels[1]);
        assert_ne!(labels[0], labels[2]);
    }

    #[test]
    fn graph_mode_parses_supported_aliases() {
        assert_eq!(parse_graph_mode("edge-only").unwrap(), GraphMode::EdgeOnly);
        assert_eq!(
            parse_graph_mode("memory+related").unwrap(),
            GraphMode::RelatedHybrid
        );
        assert_eq!(parse_graph_mode("related").unwrap(), GraphMode::RelatedOnly);
    }

    #[test]
    fn upsert_edge_merges_weight_and_source_mask() {
        let mut edges = HashMap::new();
        upsert_edge(&mut edges, 2, 1, 0.4, SOURCE_MEMORY_EDGE);
        upsert_edge(&mut edges, 1, 2, 1.5, SOURCE_RELATED_KEY);
        let edge = edges.get(&(1, 2)).expect("merged edge");
        assert_eq!(edge.source_mask, SOURCE_MEMORY_EDGE | SOURCE_RELATED_KEY);
        assert!((edge.weight - 1.5).abs() < 1e-9);
    }
}
