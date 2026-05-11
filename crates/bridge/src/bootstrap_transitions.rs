//! **δ-4 (2026-05-11) — PP-1 predicted-next-step in bootstrap.**
//!
//! Butlin et al.'s Predictive Processing indicator (PP-1) asks for a layered
//! predictive model whose lower levels are updated by prediction error. β
//! delivered the persistent layer (cofires + summarised clusters); γ' wired
//! the cold-start to walk that graph. This module adds the *temporal-asym
//! metric* signal: of all the recent `memory_get` events, which (X→Y) jumps
//! repeated themselves often enough to call a transition?
//!
//! Algorithm (deliberately minimal — design_gamma_scope_revision after β
//! dogfood: "wiring not engine"):
//!   1. Pull last N=200 `memory_get` events from `memory_query_log`.
//!   2. Sort by `at` ascending; for each adjacent (i, i+1) pair where
//!      `at_{i+1} - at_i ≤ window_secs` (default 600s = 10 min, same as the
//!      bash hook session window assumption), increment `count[A → B]`.
//!   3. Drop self-loops (A == B) and singletons (count == 1; we want
//!      repeated transitions to surface, not curiosity-walks).
//!   4. Return top-K formatted lines.
//!
//! Best-effort: empty log → empty section. Errors → empty section.

use ab_store::StateStore;
use anyhow::Result;
use std::collections::HashMap;

const DEFAULT_WINDOW_SECS: i64 = 600;
const DEFAULT_LIMIT_EVENTS: u32 = 200;
const DEFAULT_TOP_K: usize = 5;
const COMPACT_TOP_K: usize = 3;

/// Compute the predicted-next-step section. Ready-to-extend lines with
/// header + trailing blank, empty vec when there's no useful signal.
pub async fn compute_section(store: &dyn StateStore, is_compact: bool) -> Result<Vec<String>> {
    let mut events = match store.recent_memory_get_keys(DEFAULT_LIMIT_EVENTS).await {
        Ok(v) => v,
        Err(_) => return Ok(Vec::new()),
    };
    if events.len() < 2 {
        return Ok(Vec::new());
    }
    // recent_memory_get_keys returns DESC; we need ASC for adjacency.
    events.reverse();

    let mut counts: HashMap<(String, String), u32> = HashMap::new();
    for win in events.windows(2) {
        let (a_key, a_at) = &win[0];
        let (b_key, b_at) = &win[1];
        if a_key == b_key {
            continue;
        }
        if b_at - a_at > DEFAULT_WINDOW_SECS {
            continue;
        }
        *counts.entry((a_key.clone(), b_key.clone())).or_insert(0) += 1;
    }

    let mut ranked: Vec<((String, String), u32)> =
        counts.into_iter().filter(|(_, c)| *c >= 2).collect();
    if ranked.is_empty() {
        return Ok(Vec::new());
    }
    ranked.sort_by(|a, b| b.1.cmp(&a.1));
    let top_k = if is_compact { COMPACT_TOP_K } else { DEFAULT_TOP_K };
    ranked.truncate(top_k);

    let mut out = Vec::new();
    out.push(if is_compact {
        "=== Likely next-step (PP-1) ===".to_string()
    } else {
        "=== Likely next-step transitions (δ-4 PP-1 — repeated A→B in recent get-events) ==="
            .to_string()
    });
    out.push(String::new());
    for ((a, b), n) in ranked {
        out.push(format!("  • [×{n}] {a} → {b}"));
    }
    out.push(String::new());
    Ok(out)
}

#[cfg(test)]
mod tests {
    use super::*;
    use ab_store::{MemoryQueryRecord, SqliteStore};

    async fn fresh_store(tag: &str) -> (std::path::PathBuf, SqliteStore) {
        let temp_dir = std::env::temp_dir().join(format!(
            "ab-pp1-{tag}-{}",
            std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .unwrap_or_default()
                .as_nanos()
        ));
        let db_path = temp_dir.join("state.db");
        let store = SqliteStore::open(&db_path).await.expect("open");
        (temp_dir, store)
    }

    fn rec(key: &str, at: i64) -> MemoryQueryRecord {
        MemoryQueryRecord {
            kind: "get".into(),
            query: key.into(),
            tags_json: "[]".into(),
            hit_count: 1,
            top_hit_age_secs: None,
            top_hit_created_at: None,
            duration_us: 100,
            source: "test".into(),
            at,
        }
    }

    #[tokio::test]
    async fn repeated_transitions_surface_singletons_drop() {
        let (dir, store) = fresh_store("repeat").await;
        // A→B twice (within window), A→B once more (within window), A→C once,
        // self-loop B→B, and a B→D pair with too-wide gap.
        for r in [
            rec("A", 1_000),
            rec("B", 1_010), // A→B (1 of 3)
            rec("A", 1_100),
            rec("B", 1_110), // A→B (2)
            rec("A", 1_200),
            rec("B", 1_210), // A→B (3)
            rec("A", 1_300),
            rec("C", 1_310), // A→C singleton
            rec("B", 1_400),
            rec("B", 1_410), // self-loop ignored
            rec("B", 2_500),
            rec("D", 4_000), // gap 1500s > 600s → drop
        ] {
            store.record_memory_query(&r).await.expect("rec");
        }
        let lines = compute_section(&store, false).await.expect("section");
        let joined = lines.join("\n");
        assert!(joined.contains("A → B"), "should surface A→B: {joined}");
        assert!(joined.contains("[×3]"), "A→B count = 3: {joined}");
        assert!(!joined.contains("A → C"), "singleton dropped: {joined}");
        assert!(!joined.contains("B → D"), "wide-gap dropped: {joined}");
        assert!(!joined.contains("B → B"), "self-loop dropped: {joined}");
        let _ = tokio::fs::remove_dir_all(&dir).await;
    }

    #[tokio::test]
    async fn empty_log_yields_empty_section() {
        let (dir, store) = fresh_store("empty").await;
        let lines = compute_section(&store, false).await.expect("ok");
        assert!(lines.is_empty(), "no events → no section");
        let _ = tokio::fs::remove_dir_all(&dir).await;
    }

    #[tokio::test]
    async fn compact_mode_caps_at_three() {
        let (dir, store) = fresh_store("compact").await;
        // 4 distinct transitions A→B, C→D, E→F, G→H each with count 2.
        let mut t = 1_000i64;
        for (a, b) in [("A", "B"), ("C", "D"), ("E", "F"), ("G", "H")] {
            for _ in 0..2 {
                store.record_memory_query(&rec(a, t)).await.expect("rec");
                t += 10;
                store.record_memory_query(&rec(b, t)).await.expect("rec");
                t += 100; // next pair starts beyond window so it doesn't bleed
            }
        }
        let full = compute_section(&store, false).await.expect("full");
        let compact = compute_section(&store, true).await.expect("compact");
        // Count only bullet lines (data rows) — the section header text
        // itself includes the arrow glyph as a syntax example.
        let count_rows = |v: &[String]| v.iter().filter(|l| l.starts_with("  •")).count();
        assert_eq!(count_rows(&full), 4, "non-compact lists all 4");
        assert_eq!(count_rows(&compact), 3, "compact caps at 3");
        let _ = tokio::fs::remove_dir_all(&dir).await;
    }
}
