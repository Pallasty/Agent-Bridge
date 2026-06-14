//! **γ' wiring (2026-05-10) — surface coactivation neighbors at cold-start.**
//!
//! Vision §γ originally proposed a "predict next 3 steps + prefetch" engine.
//! Dogfood after β shipped (`design_gamma_scope_revision_after_beta_dogfood_20260510`)
//! revealed the engine is over-spec: α/β/P4 already deliver high-energy BFS
//! and summary buoyancy on demand. The real gap is **wiring** —
//! `session_bootstrap` doesn't auto-walk the graph, so the engine output
//! never reaches cold-start payload.
//!
//! This module fills that gap. Picks a few recently-accessed high-importance
//! seeds, runs `memory_neighbors_bfs` depth=2 on each, deduplicates by
//! neighbor key (max energy across seeds wins), and renders a compact
//! "Activated by recent context" section.
//!
//! Best-effort: errors are silently elided so a flaky graph never blocks
//! bootstrap.
use ab_store::{MemoryListSort, StateStore};
use anyhow::Result;
use std::collections::{HashMap, HashSet};

/// Pick seed memory keys for BFS expansion. Criteria:
/// - Recently accessed (sorted by `last_accessed_at DESC` via `Recent`).
/// - Non-skill (skills are 88% of store and rarely the right seed).
/// - Importance ≥ 0.4 (filters out auto-curated implicit observations).
async fn pick_seeds(store: &dyn StateStore, cwd: &str, seed_count: usize) -> Result<Vec<String>> {
    let rows = store
        .list_memories_in_scope(cwd, None, MemoryListSort::Recent, 60)
        .await?;
    Ok(rows
        .into_iter()
        .filter(|r| r.kind != "skill")
        .filter(|r| r.importance >= 0.4)
        .take(seed_count)
        .map(|r| r.key)
        .collect())
}

/// Compute the BFS neighbor section. Returns ready-to-extend lines (already
/// includes header, blank lines, and a trailing blank). Empty vec when no
/// useful signal — caller should `lines.extend(section)`.
pub async fn compute_section(
    store: &dyn StateStore,
    cwd: &str,
    is_compact: bool,
) -> Result<Vec<String>> {
    let seeds = pick_seeds(store, cwd, 3).await?;
    if seeds.is_empty() {
        return Ok(Vec::new());
    }
    let seed_set: HashSet<String> = seeds.iter().cloned().collect();

    // Walk depth=2 BFS from each seed; merge by neighbor key keeping max
    // energy and the edge_type that delivered it.
    let mut best: HashMap<String, (f64, String)> = HashMap::new();
    for seed in &seeds {
        let edges = match store.memory_neighbors_bfs(seed, 2, 0.7, 0.15).await {
            Ok(v) => v,
            Err(_) => continue,
        };
        for (edge, energy) in edges {
            let other = if edge.from_key == *seed {
                &edge.to_key
            } else {
                &edge.from_key
            };
            if seed_set.contains(other) {
                continue;
            }
            let entry = best
                .entry(other.clone())
                .or_insert((0.0, edge.edge_type.clone()));
            if energy > entry.0 {
                entry.0 = energy;
                entry.1 = edge.edge_type.clone();
            }
        }
    }
    if best.is_empty() {
        return Ok(Vec::new());
    }

    let mut ranked: Vec<(String, (f64, String))> = best.into_iter().collect();
    ranked.sort_by(|a, b| {
        b.1 .0
            .partial_cmp(&a.1 .0)
            .unwrap_or(std::cmp::Ordering::Equal)
    });
    let cap = if is_compact { 8 } else { 12 };
    ranked.truncate(cap);

    let mut out = Vec::new();
    out.push(if is_compact {
        "=== Activated by recent context ===".to_string()
    } else {
        "=== Activated by recent context (γ' wiring — α/β/P4 edges from recent seeds) ==="
            .to_string()
    });
    out.push(String::new());
    out.push(format!(
        "Seeds (last-accessed, importance≥0.4, non-skill): {}",
        seeds.join(", ")
    ));
    out.push(String::new());
    for (key, (energy, edge_type)) in ranked {
        out.push(format!("  • [{:.2} via {}] {}", energy, edge_type, key));
    }
    out.push(String::new());
    Ok(out)
}
