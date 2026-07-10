//! T0 recall baseline — read-only per-mode snapshot of `memory_query_log`.
//!
//! Part of the memory-continuity architecture (`docs/design/
//! MEMORY_CONTINUITY_COGNITIVE_ARCHITECTURE_2026_06_19.md`, forum #115).
//! T0 establishes the measured before-state every later track (T1-T7) is
//! judged against. This producer reports the recall baseline the deterministic
//! governance layer already records, split BY MODE — the dimension the blended
//! aggregate hides (the recall LEVER work showed `search_fts` and
//! `search_semantic` behave very differently).
//!
//! Surface-free + observability-only: it only SELECTs from the existing
//! `memory_query_stats`. NO new MCP tool, NO ranking change, NO writes.
//!
//!   # snapshot the live state.db over the default 7-day window:
//!   cargo run -p ab-bridge --example recall_baseline
//!   # custom window (days) and/or an explicit (e.g. copied) db:
//!   AB_BASELINE_DB=/tmp/state.copy.db \
//!     cargo run -p ab-bridge --example recall_baseline -- 14
//!
//! Gate-safe: `memory_query_stats` is read-only, so pointing at the live db is
//! safe; point `AB_BASELINE_DB` at a copy if you prefer total isolation.

use ab_store::{default_db_path, SqliteStore, StateStore};
use std::path::PathBuf;

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    let window_days: i64 = std::env::args()
        .nth(1)
        .and_then(|s| s.parse().ok())
        .unwrap_or(7);
    let window_secs = window_days * 86_400;

    let db_path: PathBuf = std::env::var("AB_BASELINE_DB")
        .ok()
        .map(PathBuf::from)
        .unwrap_or_else(default_db_path);

    let store = SqliteStore::open(&db_path).await?;
    let stats = store.memory_query_stats(window_secs).await?;

    println!("# T0 recall baseline");
    println!("db:      {}", db_path.display());
    println!(
        "window:  {window_days}d  ({} rows in window)",
        stats.total_queries
    );
    println!();

    if stats.total_queries == 0 {
        println!("(no memory queries logged in window — baseline is empty)");
        return Ok(());
    }

    println!("## Aggregate (blended across modes)");
    println!(
        "  total={}  hits={}  misses={}  hit_rate={:.3}",
        stats.total_queries, stats.hits, stats.misses, stats.hit_rate
    );
    println!(
        "  p50={}µs  p95={}µs  avg_top_hit_age={:.2}d",
        stats.p50_duration_us,
        stats.p95_duration_us,
        stats.avg_top_hit_age_secs / 86_400.0
    );
    println!();

    println!("## By mode (the detail the aggregate hides)");
    println!(
        "  {:<16} {:>6} {:>6} {:>9} {:>9} {:>9} {:>10}",
        "mode", "total", "hits", "hit_rate", "p50µs", "p95µs", "avg_age_d"
    );
    for m in &stats.by_mode {
        println!(
            "  {:<16} {:>6} {:>6} {:>9.3} {:>9} {:>9} {:>10.2}",
            m.kind,
            m.total,
            m.hits,
            m.hit_rate,
            m.p50_duration_us,
            m.p95_duration_us,
            m.avg_top_hit_age_secs / 86_400.0
        );
    }
    println!();

    if !stats.top_miss_queries.is_empty() {
        println!("## Top miss queries (hit_count=0, most-recurring)");
        for (q, n) in stats.top_miss_queries.iter().take(8) {
            println!("  {n:>4}×  {q}");
        }
        println!();
    }

    // Honest read of the baseline — no green-laundering, just what the numbers
    // say so the before-state is interpretable, not just dumped.
    let worst = stats
        .by_mode
        .iter()
        .filter(|m| m.total >= 3)
        .min_by(|a, b| {
            a.hit_rate
                .partial_cmp(&b.hit_rate)
                .unwrap_or(std::cmp::Ordering::Equal)
        });
    if let Some(m) = worst {
        println!(
            "note: lowest-hit-rate mode (n≥3) = {} at {:.3}; p95={}µs",
            m.kind, m.hit_rate, m.p95_duration_us
        );
    }

    Ok(())
}
