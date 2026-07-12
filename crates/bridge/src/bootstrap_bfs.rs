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
use ab_store::{memory_scope_visible_in_context, MemoryListSort, MemoryPeekResult, StateStore};
use anyhow::Result;
use std::collections::{HashMap, HashSet};

/// Exact, side-effect-free endpoint admission for bootstrap graph output.
/// Missing/tombstoned/retired rows and backends that cannot prove the current
/// envelope all fail closed. The cache bounds exact reads to once per key even
/// when several seeds or parallel edge types reach the same endpoint.
async fn endpoint_is_visible(
    store: &dyn StateStore,
    key: &str,
    cwd: &str,
    cache: &mut HashMap<String, bool>,
) -> bool {
    if let Some(visible) = cache.get(key) {
        return *visible;
    }
    let visible = match store.memory_peek(key).await {
        Ok(MemoryPeekResult::Present { record }) => {
            record.status == "active"
                && memory_scope_visible_in_context(record.scope.as_deref(), cwd)
        }
        Ok(MemoryPeekResult::Missing | MemoryPeekResult::Tombstoned { .. }) | Err(_) => false,
    };
    cache.insert(key.to_string(), visible);
    visible
}

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
    let mut endpoint_visibility: HashMap<String, bool> = HashMap::new();
    for seed in &seeds {
        let edges = match store.memory_neighbors_bfs(seed, 2, 0.7, 0.15).await {
            Ok(v) => v,
            Err(_) => continue,
        };
        for (edge, energy) in edges {
            // `memory_neighbors_bfs` deliberately walks the store-wide graph.
            // Bootstrap is cwd-scoped, so admit an emitted edge only when both
            // exact endpoint envelopes are active and visible. Checking both
            // sides also blocks a visible key reached through an out-of-scope
            // intermediate edge. Unknown/unreadable endpoints fail closed.
            if !endpoint_is_visible(store, &edge.from_key, cwd, &mut endpoint_visibility).await
                || !endpoint_is_visible(store, &edge.to_key, cwd, &mut endpoint_visibility).await
            {
                continue;
            }
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

#[cfg(test)]
mod tests {
    use super::*;
    use ab_store::{MemoryRecord, SqliteStore};

    async fn fresh_store(tag: &str) -> (std::path::PathBuf, SqliteStore) {
        let temp_dir = std::env::temp_dir().join(format!(
            "ab-bootstrap-bfs-{tag}-{}",
            std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .unwrap_or_default()
                .as_nanos()
        ));
        let db_path = temp_dir.join("state.db");
        let store = SqliteStore::open(&db_path).await.expect("open");
        (temp_dir, store)
    }

    fn memory(key: &str, scope: Option<&str>, importance: f64) -> MemoryRecord {
        MemoryRecord {
            key: key.to_string(),
            // `memory_save` reconsolidates high-overlap rows of the same kind.
            // Keep fixtures independent so only the explicit test edges exist.
            kind: format!("test_{key}"),
            content: format!("content unique to {key}"),
            tags: Vec::new(),
            related_keys: Vec::new(),
            scope: scope.map(str::to_string),
            created_at: 0,
            updated_at: 0,
            last_accessed_at: 0,
            access_count: 0,
            importance,
            status: "active".to_string(),
            trigger_pattern: None,
            superseded_by: None,
        }
    }

    async fn save(store: &SqliteStore, record: MemoryRecord) {
        store.memory_save(&record).await.expect("save memory");
    }

    #[test]
    fn scope_visibility_matches_scoped_list_contract() {
        let cwd = "/work/project/subdir";
        assert!(memory_scope_visible_in_context(None, cwd));
        assert!(memory_scope_visible_in_context(Some("global"), cwd));
        assert!(memory_scope_visible_in_context(
            Some("project:/work/project"),
            cwd
        ));
        assert!(memory_scope_visible_in_context(Some(cwd), cwd));
        assert!(!memory_scope_visible_in_context(
            Some("project:/work/other"),
            cwd
        ));
        assert!(!memory_scope_visible_in_context(Some("domain:rust"), cwd));
        assert!(memory_scope_visible_in_context(
            Some("domain:rust"),
            "domain:rust"
        ));
        assert!(!memory_scope_visible_in_context(
            Some("project:/work/project"),
            "/work/project-other"
        ));
        assert!(memory_scope_visible_in_context(
            Some("project:/work/project"),
            "project:/work/project/subdir"
        ));
        assert!(memory_scope_visible_in_context(
            Some("project:/work/other"),
            ""
        ));
    }

    #[tokio::test]
    async fn scoped_bfs_only_renders_active_cwd_visible_closed_edges() {
        let (dir, store) = fresh_store("scope-closure").await;
        // The cwd intentionally shares a string prefix with another project;
        // visibility must use a path-segment boundary, not raw starts_with.
        let cwd = "/work/project-other/subdir";

        // Only this row qualifies as a bootstrap seed. Neighbours stay below
        // the seed importance threshold so the test exercises one traversal.
        save(
            &store,
            memory("seed", Some("project:/work/project-other"), 0.9),
        )
        .await;
        for record in [
            memory("same-project", Some("project:/work/project-other"), 0.3),
            memory("global-neighbour", Some("global"), 0.3),
            memory("unscoped-neighbour", None, 0.3),
            memory("other-project", Some("project:/work/project"), 0.3),
            memory("hidden-hop", Some("project:/work/project"), 0.3),
            memory("visible-via-hidden", Some("global"), 0.3),
            memory("tombstoned-neighbour", Some("global"), 0.3),
            {
                let mut archived = memory("archived-neighbour", Some("global"), 0.3);
                archived.status = "archived".to_string();
                archived
            },
        ] {
            save(&store, record).await;
        }

        for (from, to, edge_type) in [
            ("seed", "same-project", "same_scope"),
            ("seed", "global-neighbour", "global_scope"),
            ("unscoped-neighbour", "seed", "unscoped_scope"),
            ("seed", "other-project", "cross_project"),
            ("seed", "missing-neighbour", "missing_endpoint"),
            ("seed", "tombstoned-neighbour", "tombstoned_endpoint"),
            ("seed", "archived-neighbour", "retired_endpoint"),
            ("seed", "hidden-hop", "hidden_first_hop"),
            // Orient the second edge this way so the pre-fix `other` branch
            // would have rendered the global key reached via a hidden node.
            ("visible-via-hidden", "hidden-hop", "hidden_second_hop"),
        ] {
            store
                .memory_link(from, to, edge_type, 1.0)
                .await
                .expect("link");
        }
        assert!(store
            .memory_delete("tombstoned-neighbour")
            .await
            .expect("tombstone"));

        let joined = compute_section(&store, cwd, false)
            .await
            .expect("section")
            .join("\n");
        for visible in ["same-project", "global-neighbour", "unscoped-neighbour"] {
            assert!(
                joined.contains(visible),
                "missing visible key {visible}: {joined}"
            );
        }
        for hidden in [
            "other-project",
            "missing-neighbour",
            "tombstoned-neighbour",
            "archived-neighbour",
            "hidden-hop",
            "visible-via-hidden",
        ] {
            assert!(
                !joined.contains(hidden),
                "leaked hidden key {hidden}: {joined}"
            );
        }

        let _ = tokio::fs::remove_dir_all(&dir).await;
    }
}
