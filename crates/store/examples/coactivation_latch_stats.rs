//! Read-only coactivation-latch immune-set telemetry (v38 bounded-latch).
//!
//! Reports the live `memory_coactivation` latch metrics that the v38 bounded
//! coactivation-latch promised to validate from real data before its starting
//! defaults (`stale_window_secs`, `max_latched_edges`) are treated as final —
//! see §5(A)/§7 of `docs/design/BOUNDED_COACTIVATION_LATCH_2026_06_28.md`.
//!
//! The store DB is opened **read-only** (`SQLITE_OPEN_READ_ONLY`) and never
//! written. It reuses the EXACT v38 immunity predicate
//! (`consolidated = 1 AND last_cofire_at >= now - stale_window_secs`, inclusive)
//! and the same `LatchConfig::default()` thresholds the runtime uses, so the
//! snapshot it reports matches what decay/prune actually see.
//!
//! Sampling this over time yields the §5(A) immune-set-size time series: a
//! plateau with `immune_edges ≤ max_latched_edges` confirms boundedness, and the
//! last-co-fire age histogram says whether `stale_window_secs` should move.
//!
//! Usage:
//!   cargo run -p ab-store --no-default-features --example coactivation_latch_stats [DB_PATH]
//! (DB_PATH defaults to `ab_store::default_db_path()`).

use ab_store::coactivation_latch::LatchConfig;
use ab_store::default_db_path;
use tokio_rusqlite::{rusqlite, Connection};

fn now_unix_secs() -> i64 {
    // `sqlite::now_secs()` is private; mirror it (decay/prune use the same form).
    std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .map(|d| d.as_secs() as i64)
        .unwrap_or(0)
}

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    let db = std::env::args()
        .nth(1)
        .map(std::path::PathBuf::from)
        .unwrap_or_else(default_db_path);
    eprintln!("[latch-stats] read-only open: {}", db.display());

    let conn = Connection::open_with_flags(&db, rusqlite::OpenFlags::SQLITE_OPEN_READ_ONLY).await?;
    // (count, consolidated, last_cofire_at) for every edge; everything else is
    // derived in-process so we touch the table exactly once, read-only.
    let rows: Vec<(i64, i64, i64)> = conn
        .call(|c| -> rusqlite::Result<Vec<(i64, i64, i64)>> {
            let mut stmt =
                c.prepare("SELECT count, consolidated, last_cofire_at FROM memory_coactivation")?;
            let rows = stmt
                .query_map([], |row| Ok((row.get(0)?, row.get(1)?, row.get(2)?)))?
                .collect::<rusqlite::Result<Vec<_>>>()?;
            Ok(rows)
        })
        .await?;

    let cfg = LatchConfig::default();
    let now = now_unix_secs();
    let stale = cfg.stale_window_secs;
    let threshold = cfg.consolidate_at_count as i64;
    let cap = cfg.max_latched_edges as i64;
    const D: i64 = 86_400;

    let total = rows.len() as i64;
    let mut consolidated = 0i64; // latched set (consolidated=1)
    let mut immune = 0i64; // consolidated AND warm — the §5(A) bounded quantity
    let mut at_or_above_threshold = 0i64; // count>=threshold regardless of flag (latent latch)
    let mut below_threshold_latched = 0i64; // sticky-but-decayed (expected, healthy)
    let mut consolidated_counts: Vec<i64> = Vec::new();
    // last-co-fire age histogram (age = now - last_cofire_at) over consolidated edges.
    // immune ≈ zero-excluded buckets up to `stale`; immune is still computed EXACTLY
    // below via the predicate, the histogram only shows the recency shape.
    let mut h_zero = 0i64; // last_cofire_at == 0 (legacy / never stamped post-v38)
    let mut h_lt1d = 0i64;
    let mut h_d1_4 = 0i64;
    let mut h_d4_7 = 0i64;
    let mut h_d7_30 = 0i64;
    let mut h_gt30d = 0i64;

    for &(count, cons, lcf) in &rows {
        if count >= threshold {
            at_or_above_threshold += 1;
        }
        if cons != 1 {
            continue;
        }
        consolidated += 1;
        consolidated_counts.push(count);
        if count < threshold {
            below_threshold_latched += 1;
        }
        if lcf >= now - stale {
            // EXACT v38 immunity predicate (inclusive boundary).
            immune += 1;
        }
        if lcf == 0 {
            h_zero += 1;
        } else {
            let age = (now - lcf).max(0);
            if age < D {
                h_lt1d += 1;
            } else if age < 4 * D {
                h_d1_4 += 1;
            } else if age < 7 * D {
                h_d4_7 += 1;
            } else if age < 30 * D {
                h_d7_30 += 1;
            } else {
                h_gt30d += 1;
            }
        }
    }

    consolidated_counts.sort_unstable();
    let (cnt_min, cnt_med, cnt_max) = if consolidated_counts.is_empty() {
        (0, 0, 0)
    } else {
        let n = consolidated_counts.len();
        (
            consolidated_counts[0],
            consolidated_counts[n / 2],
            consolidated_counts[n - 1],
        )
    };
    let stale_latched = consolidated - immune; // cold latched: reclaimable, not immune
    let over_cap = (consolidated - cap).max(0); // §5.1 un-consolidates this many next sweep
    let frac = |x: i64| {
        if total > 0 {
            x as f64 / total as f64
        } else {
            0.0
        }
    };

    println!("{{");
    println!("  \"schema\": \"agent_bridge.coactivation_latch_stats.v0\",");
    println!("  \"read_only\": true,");
    println!("  \"now\": {},", now);
    println!("  \"config\": {{");
    println!("    \"consolidate_at_count\": {},", threshold);
    println!(
        "    \"stale_window_secs\": {}, \"stale_window_days\": {:.2},",
        stale,
        stale as f64 / D as f64
    );
    println!("    \"max_latched_edges\": {}", cap);
    println!("  }},");
    println!("  \"total_edges\": {},", total);
    println!("  \"at_or_above_threshold\": {},", at_or_above_threshold);
    println!("  \"consolidated_edges\": {},", consolidated);
    println!("  \"immune_edges\": {},", immune);
    println!("  \"stale_latched_edges\": {},", stale_latched);
    println!(
        "  \"below_threshold_latched\": {},",
        below_threshold_latched
    );
    println!("  \"latched_fraction\": {:.4},", frac(consolidated));
    println!("  \"immune_fraction\": {:.4},", frac(immune));
    println!("  \"over_cap_now\": {},", over_cap);
    println!("  \"cap_headroom\": {},", cap - consolidated);
    println!(
        "  \"consolidated_count_dist\": {{ \"min\": {}, \"median\": {}, \"max\": {} }},",
        cnt_min, cnt_med, cnt_max
    );
    println!("  \"consolidated_last_cofire_age_buckets\": {{");
    println!("    \"zero\": {},", h_zero);
    println!("    \"lt_1d\": {},", h_lt1d);
    println!("    \"d1_4\": {},", h_d1_4);
    println!("    \"d4_7\": {},", h_d4_7);
    println!("    \"d7_30\": {},", h_d7_30);
    println!("    \"gt_30d\": {}", h_gt30d);
    println!("  }}");
    println!("}}");
    Ok(())
}
