//! Goal C — STANDING continuity `U` surface (offline, read-only, host-correct).
//!
//! The continuity honest ledger flags memory-continuity as "missing a standing
//! continuity dashboard". Codex's `GOAL_C_REPORT_FIRST_UTILITY_SURFACE` defines
//! `U` as a manual 10-step runbook; the sibling probes produced point results.
//! This mechanizes the store-derivable half of `U` into ONE command: the
//! embedding-space health that decides whether semantic retrieval can serve
//! continuity at all — backend mix, stale-vector fraction, and anisotropy —
//! each row tagged with its external anchor, falsifier, and owner.
//!
//! It deliberately does NOT re-run or re-copy the held-out recall corpus: R@k is
//! owned by `recall_eval` (the board-agreed external falsifier anchor, #3774);
//! this surface cites it and refreshes the store-side signals around it. The
//! board converged (#3834/#3835/#3774) that FTS is the headline continuity
//! signal and semantic/whitening is a SECONDARY lever — so this report frames
//! the embedding-space health as a diagnostic, not as the continuity verdict.
//!
//! Read-only: SELECTs active embeddings, computes statistics, prints a report.
//! No MCP tool, no write, no ranking change. Host-correct: anisotropy is
//! measured on whichever backend the local store is actually dominated by
//! (Mac e5-small / aio2 para-ml), so the number is meaningful per host.
//!
//!   cargo run -p ab-bridge --example continuity_report --release
//!   cargo run -p ab-bridge --example continuity_report --release -- --json

use ab_store::default_db_path;
use ab_store::vector::{decode_embedding, VECTOR_DIM};
use std::collections::BTreeMap;
use std::path::PathBuf;
use tokio_rusqlite::Connection;

const HASH_BACKEND_NAME: &str = "fnv1a-hash-384";

struct Row {
    backend: String,
    vecs: Vec<Vec<f32>>,
}

/// ‖μ‖ / mean‖v‖ over a backend's vectors; →1.0 means severe anisotropy
/// (all vectors share one dominant direction, so cosine ranking is near-random).
fn anisotropy_ratio(vecs: &[Vec<f32>]) -> f32 {
    if vecs.is_empty() {
        return 0.0;
    }
    let mut mu = vec![0f32; VECTOR_DIM];
    for v in vecs {
        for (m, x) in mu.iter_mut().zip(v) {
            *m += x;
        }
    }
    for m in mu.iter_mut() {
        *m /= vecs.len() as f32;
    }
    let mu_norm: f32 = mu.iter().map(|x| x * x).sum::<f32>().sqrt();
    let mean_vnorm: f32 = vecs
        .iter()
        .map(|v| v.iter().map(|x| x * x).sum::<f32>().sqrt())
        .sum::<f32>()
        / vecs.len() as f32;
    if mean_vnorm < 1e-6 {
        0.0
    } else {
        mu_norm / mean_vnorm
    }
}

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    let as_json = std::env::args().any(|a| a == "--json");
    let db_path: PathBuf = std::env::var("AB_BASELINE_DB")
        .ok()
        .map(PathBuf::from)
        .unwrap_or_else(default_db_path);

    // ── load active embeddings grouped by backend (read-only) ───────────────
    let conn = Connection::open(&db_path).await?;
    let raw: Vec<(Option<String>, Vec<u8>)> = conn
        .call(|c| {
            let mut stmt = c.prepare(
                "SELECT embedding_backend, embedding FROM memories \
                 WHERE status='active' AND embedding IS NOT NULL",
            )?;
            let out = stmt
                .query_map([], |row| {
                    Ok((row.get::<_, Option<String>>(0)?, row.get::<_, Vec<u8>>(1)?))
                })?
                .collect::<Result<Vec<_>, _>>()?;
            Ok::<_, tokio_rusqlite::rusqlite::Error>(out)
        })
        .await?;
    let active_total: i64 = conn
        .call(|c| {
            let v = c.query_row("SELECT COUNT(*) FROM memories WHERE status='active'", [], |r| {
                r.get::<_, i64>(0)
            })?;
            Ok::<_, tokio_rusqlite::rusqlite::Error>(v)
        })
        .await?;

    // ── group by backend ────────────────────────────────────────────────────
    let mut by_backend: BTreeMap<String, Row> = BTreeMap::new();
    for (be, bytes) in raw {
        let name = be.unwrap_or_else(|| "<null pre-v26>".to_string());
        let v = decode_embedding(&bytes);
        if v.len() != VECTOR_DIM {
            continue;
        }
        by_backend
            .entry(name.clone())
            .or_insert_with(|| Row {
                backend: name,
                vecs: Vec::new(),
            })
            .vecs
            .push(v);
    }

    let total_embedded: usize = by_backend.values().map(|r| r.vecs.len()).sum();
    // dominant tagged backend = the model the store is "indexed with" (host-correct).
    let dominant = by_backend
        .values()
        .filter(|r| r.backend != "<null pre-v26>" && r.backend != HASH_BACKEND_NAME)
        .max_by_key(|r| r.vecs.len());
    let dominant_name = dominant.map(|r| r.backend.clone()).unwrap_or_default();
    let dominant_count = dominant.map(|r| r.vecs.len()).unwrap_or(0);
    let aniso = dominant.map(|r| anisotropy_ratio(&r.vecs)).unwrap_or(0.0);
    // stale = embedded vectors NOT in the dominant (current) space.
    let stale = total_embedded.saturating_sub(dominant_count);
    let stale_frac = if total_embedded > 0 {
        stale as f64 / total_embedded as f64
    } else {
        0.0
    };

    if as_json {
        let backends: Vec<String> = by_backend
            .values()
            .map(|r| format!("{{\"backend\":\"{}\",\"n\":{}}}", r.backend, r.vecs.len()))
            .collect();
        println!(
            "{{\"db\":\"{}\",\"active_total\":{},\"embedded\":{},\"dominant_backend\":\"{}\",\"dominant_count\":{},\"anisotropy_ratio\":{:.3},\"stale_vectors\":{},\"stale_frac\":{:.3},\"backends\":[{}]}}",
            db_path.display(),
            active_total,
            total_embedded,
            dominant_name,
            dominant_count,
            aniso,
            stale,
            stale_frac,
            backends.join(",")
        );
        return Ok(());
    }

    // ── standing U report (markdown) ────────────────────────────────────────
    println!("# Continuity U — standing report (store-side embedding-space health)");
    println!("db:               {}", db_path.display());
    println!("active memories:  {active_total}  ({total_embedded} embedded)");
    println!("host backend:     {dominant_name} (dominant tagged, {dominant_count} vectors)\n");

    println!("## Embedding backend mix (active, embedded)");
    println!("  {:<32} {:>7} {:>7}", "backend", "n", "%");
    for r in by_backend.values() {
        println!(
            "  {:<32} {:>7} {:>6.1}%",
            r.backend,
            r.vecs.len(),
            100.0 * r.vecs.len() as f64 / total_embedded.max(1) as f64
        );
    }
    println!();

    println!("## Continuity signals (each: value · external anchor · falsifier · owner)");
    let aniso_state = if aniso >= 0.85 {
        "SEVERE (cosine near-random)"
    } else if aniso >= 0.5 {
        "elevated"
    } else {
        "healthy"
    };
    println!(
        "  - anisotropy({dominant_name})  ratio={aniso:.3}  [{aniso_state}]\n      anchor: ‖μ‖/mean‖v‖ over live store · falsifier: ratio<0.5 would mean cosine is usable · owner: memory-continuity lane"
    );
    println!(
        "  - stale vectors          {stale}/{total_embedded} ({:.0}%) not in {dominant_name} space\n      anchor: embedding_backend tags · falsifier: reindex drops this to ~0 · owner: @mac hygiene (Goal B)",
        100.0 * stale_frac
    );
    println!(
        "  - recall R@k             SEE `recall_eval` (host-correct, Action A)\n      anchor: 18-case held-out paraphrase corpus, FTS R@10 = headline · falsifier: hard-tier R@k unchanged ⇒ a gate is decorative (#3774) · owner: memory-continuity lane"
    );
    println!(
        "  - L6 hallucination gate  falsified_shelved (rule-3, 3/3)\n      anchor: docs/L6-OPTION-E-RESULT · falsifier: a NEW design beats P1≥60%/P2≤25% on held-out · owner: shelved"
    );
    println!();

    println!("## Read");
    println!(
        "  Board verdict (#3834/#3835/#3774): semantic/whitening is a SECONDARY lever —"
    );
    println!(
        "  anisotropy is a sentence-transformer family disease (e5 0.906 / para-ml 0.773),"
    );
    println!(
        "  and even whitened, semantic recall stays below FTS. So FTS R@10 is the headline"
    );
    println!(
        "  continuity number; this embedding-space report is a DIAGNOSTIC for why semantic"
    );
    println!(
        "  underperforms, not the continuity verdict. Stale-vector reindex is hygiene, not a"
    );
    println!("  recall lever (#3834 falsified poisoning). Refresh R@k via `recall_eval`.");

    Ok(())
}
