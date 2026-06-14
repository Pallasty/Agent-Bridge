//! AutoResearch ⑤ — substrate vs flat-embedding recall probe (decoupled).
//!
//! Frozen falsifier: `docs/design/AUTORESEARCH_SUBSTRATE_RECALL_PROBE_2026_05_24.md`
//! Forum claim: thread 31 #1032.
//!
//! Runs ONE arm per process (`install_default` is a process-wide OnceLock, so
//! the two backends cannot coexist). A small in-memory corpus is embedded
//! fresh by the arm's backend — query = a memory's title (first content line),
//! document = the same memory's full content — so the cosine comparison stays
//! in one embedding space (no apples-to-oranges against ONNX-indexed rows).
//!
//! Run (gate-safe: point PROBE_DB at a COPY of state.db; read-only):
//!   PROBE_DB=/tmp/probe.db PROBE_ARM=onnx \
//!     cargo run --release -p ab-bridge --example substrate_recall_eval
//!   # Legacy Seed arm moved out of the AB runtime; build crates/seed-bridge
//!   # directly if this historical probe needs to be revived.

use ab_store::{MemoryListSort, SqliteStore, StateStore};
use std::sync::Arc;

fn cosine(a: &[f32], b: &[f32]) -> f32 {
    let n = a.len().min(b.len());
    let mut dot = 0.0f32;
    let mut na = 0.0f32;
    let mut nb = 0.0f32;
    for i in 0..n {
        dot += a[i] * b[i];
        na += a[i] * a[i];
        nb += b[i] * b[i];
    }
    if na == 0.0 || nb == 0.0 {
        return 0.0;
    }
    dot / (na.sqrt() * nb.sqrt())
}

/// First "meaningful" line of a memory body — strips markdown heading/list
/// sigils and takes the first line ≥ 8 chars. This is the de-facto title.
fn title_of(content: &str) -> String {
    content
        .lines()
        .map(|l| {
            l.trim_start_matches(|c| c == '#' || c == '*' || c == '-' || c == ' ')
                .trim()
        })
        .find(|l| l.chars().count() >= 8)
        .unwrap_or("")
        .chars()
        .take(120)
        .collect()
}

/// Document text = content with its first meaningful line (the title) removed,
/// so a title-query must match the BODY semantically rather than lexically
/// re-matching the echoed title. (v1 with full content ceilings R@5=1.0.)
fn body_minus_title(content: &str) -> String {
    let mut dropped = false;
    let mut out = String::new();
    for l in content.lines() {
        let stripped = l
            .trim_start_matches(|c| c == '#' || c == '*' || c == '-' || c == ' ')
            .trim();
        if !dropped && stripped.chars().count() >= 8 {
            dropped = true;
            continue; // drop the title line
        }
        out.push_str(l);
        out.push('\n');
    }
    out
}

#[tokio::main]
async fn main() -> anyhow::Result<()> {
    let arm = std::env::var("PROBE_ARM").unwrap_or_else(|_| "onnx".into());
    let db = std::env::var("PROBE_DB").expect("set PROBE_DB to a state.db COPY path");
    let n: usize = std::env::var("PROBE_N")
        .ok()
        .and_then(|s| s.parse().ok())
        .unwrap_or(50);

    if arm == "substrate" {
        anyhow::bail!(
            "PROBE_ARM=substrate moved out of ab-bridge; build the legacy crates/seed-bridge crate directly"
        );
    } else {
        eprintln!("[arm=onnx] default backend (no substrate install)");
    }
    let backend = ab_store::embedding::default_backend();
    let _ = backend.embed("warm-up probe — substrate recall eval"); // force lazy model load

    let store: Arc<dyn StateStore> = Arc::new(SqliteStore::open(std::path::Path::new(&db)).await?);
    let pool = store
        .list_memories(None, MemoryListSort::Newest, (n as u32) * 3 + 80)
        .await?;
    let corpus: Vec<(String, String, String)> = pool
        .into_iter()
        .filter(|m| m.kind != "skill" && m.status == "active" && m.content.trim().len() >= 160)
        .filter_map(|m| {
            let title = title_of(&m.content);
            let body = body_minus_title(&m.content); // doc = body WITHOUT the echoed title
            if title.chars().count() < 8 || body.trim().chars().count() < 60 {
                return None;
            }
            Some((m.key.clone(), title, body))
        })
        .take(n)
        .collect();
    eprintln!("corpus: {} memories", corpus.len());
    if corpus.len() < 10 {
        anyhow::bail!("corpus too small ({}) — need ≥10", corpus.len());
    }

    // Embed all docs + queries once, under this arm's backend (same space).
    let doc_vecs: Vec<Vec<f32>> = corpus
        .iter()
        .map(|(_, _, body)| backend.embed(body))
        .collect();
    let query_vecs: Vec<Vec<f32>> = corpus
        .iter()
        .map(|(_, title, _)| backend.embed(title))
        .collect();

    let mut recall5 = 0usize;
    let mut recall1 = 0usize;
    let mut mrr10 = 0.0f64;
    for i in 0..corpus.len() {
        let mut scored: Vec<(usize, f32)> = (0..corpus.len())
            .map(|j| (j, cosine(&query_vecs[i], &doc_vecs[j])))
            .collect();
        scored.sort_by(|a, b| b.1.partial_cmp(&a.1).unwrap_or(std::cmp::Ordering::Equal));
        let rank = scored
            .iter()
            .position(|(j, _)| *j == i)
            .unwrap_or(usize::MAX);
        if rank == 0 {
            recall1 += 1;
        }
        if rank < 5 {
            recall5 += 1;
        }
        if rank < 10 {
            mrr10 += 1.0 / ((rank + 1) as f64);
        }
    }
    let nf = corpus.len() as f64;
    let dim = doc_vecs.first().map(|v| v.len()).unwrap_or(0);
    let out = serde_json::json!({
        "arm": arm,
        "n": corpus.len(),
        "embed_dim": dim,
        "recall_at_1": recall1 as f64 / nf,
        "recall_at_5": recall5 as f64 / nf,
        "mrr_at_10": mrr10 / nf,
    });
    println!("{}", serde_json::to_string(&out)?);
    eprintln!(
        "arm={} N={} dim={} R@1={:.3} R@5={:.3} MRR@10={:.3}",
        arm,
        corpus.len(),
        dim,
        recall1 as f64 / nf,
        recall5 as f64 / nf,
        mrr10 / nf
    );
    Ok(())
}
