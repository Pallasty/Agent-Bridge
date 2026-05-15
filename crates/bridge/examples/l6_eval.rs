//! L6-P1/P2 evaluation harness for `introspect_recall`.
//!
//! Reads `tests/l6_corpus.jsonl` (25 grounded + 25 fictional queries with
//! expected `label`), runs `memory_top_k_cosine` against a state.db, and
//! computes detection-rate (recall on fictional → novelty>thr) and
//! false-positive rate (grounded → novelty>thr) across a threshold sweep.
//!
//! Run:
//!   AGENT_BRIDGE_DB=/path/to/state.db \
//!     cargo run --release -p ab-bridge --example l6_eval
//!
//! Defaults to `~/.local/share/agent-bridge/state.db`. Outputs a markdown
//! table to stdout for direct paste into the design memo.

use ab_store::{SqliteStore, StateStore};
use serde::Deserialize;
use std::path::PathBuf;
use std::sync::Arc;

#[derive(Debug, Deserialize, Clone)]
struct CorpusItem {
    id: String,
    label: String, // "grounded" | "fictional"
    query: String,
    #[allow(dead_code)]
    rationale: String,
}

#[tokio::main]
async fn main() -> anyhow::Result<()> {
    // ── Locate inputs ────────────────────────────────────────────────────
    let db_path = std::env::var("AGENT_BRIDGE_DB")
        .map(PathBuf::from)
        .unwrap_or_else(|_| {
            let home = std::env::var("HOME").expect("HOME");
            PathBuf::from(home).join(".local/share/agent-bridge/state.db")
        });
    let corpus_path = std::env::var("L6_CORPUS")
        .map(PathBuf::from)
        .unwrap_or_else(|_| PathBuf::from("tests/l6_corpus.jsonl"));
    let k: u32 = std::env::var("L6_K")
        .ok()
        .and_then(|s| s.parse().ok())
        .unwrap_or(5);

    eprintln!("L6 eval — db={} corpus={} k={}", db_path.display(), corpus_path.display(), k);

    let corpus_raw = std::fs::read_to_string(&corpus_path)?;
    let items: Vec<CorpusItem> = corpus_raw
        .lines()
        .filter(|l| !l.trim().is_empty())
        .map(|l| serde_json::from_str::<CorpusItem>(l).map_err(anyhow::Error::from))
        .collect::<Result<_, _>>()?;
    let total_grounded = items.iter().filter(|i| i.label == "grounded").count();
    let total_fictional = items.iter().filter(|i| i.label == "fictional").count();
    eprintln!("corpus: {} grounded + {} fictional", total_grounded, total_fictional);

    // ── Open store + warm embedding backend ──────────────────────────────
    let store_concrete = SqliteStore::open(&db_path).await?;
    let store: Arc<dyn StateStore> = Arc::new(store_concrete);

    // Probe-call once so ONNX model (if any) finishes loading before
    // timing-sensitive sections.
    let _ = store
        .memory_top_k_cosine("warm-up probe — agent-bridge L6 eval", k)
        .await?;

    // ── Run all items, collect novelty per item ──────────────────────────
    let mut rows: Vec<(CorpusItem, f32, usize)> = Vec::with_capacity(items.len());
    for item in &items {
        let hits = store.memory_top_k_cosine(&item.query, k).await?;
        let max_cos = hits.iter().map(|h| h.cosine).fold(f32::NEG_INFINITY, f32::max);
        let novelty = if hits.is_empty() {
            1.0_f32
        } else {
            (1.0 - max_cos).clamp(0.0, 1.0)
        };
        rows.push((item.clone(), novelty, hits.len()));
    }

    // ── Per-item table ───────────────────────────────────────────────────
    println!("# L6-P1 / L6-P2 evaluation");
    println!();
    println!("Backend: {} | k={} | corpus={} items", embedding_name(), k, items.len());
    println!();
    println!("## Per-item novelty");
    println!();
    println!("| id | label | novelty | top1_cos | hits | query (≤80c) |");
    println!("|---|---|---|---|---|---|");
    for (item, novelty, n_hits) in &rows {
        let q_preview: String = item.query.chars().take(80).collect();
        let top1 = 1.0 - novelty;
        println!(
            "| {} | {} | {:.3} | {:.3} | {} | {} |",
            item.id, item.label, novelty, top1, n_hits, q_preview
        );
    }
    println!();

    // ── Threshold sweep ──────────────────────────────────────────────────
    println!("## Threshold sweep");
    println!();
    println!("| threshold | detect (fictional≥thr) | FP (grounded≥thr) | P1 PASS≥60% | P2 PASS≤25% |");
    println!("|---|---|---|---|---|");
    let mut best_threshold: Option<(f32, f32, f32)> = None;
    for thr_pct in (40..=90).step_by(5) {
        let thr = thr_pct as f32 / 100.0;
        let mut tp = 0usize;
        let mut fp = 0usize;
        for (item, novelty, _) in &rows {
            let above = *novelty >= thr;
            match item.label.as_str() {
                "fictional" if above => tp += 1,
                "grounded" if above => fp += 1,
                _ => (),
            }
        }
        let detect = tp as f32 / total_fictional.max(1) as f32;
        let fpr = fp as f32 / total_grounded.max(1) as f32;
        let p1_ok = detect >= 0.60;
        let p2_ok = fpr <= 0.25;
        println!(
            "| {:.2} | {}/{} = {:.1}% | {}/{} = {:.1}% | {} | {} |",
            thr,
            tp, total_fictional, detect * 100.0,
            fp, total_grounded, fpr * 100.0,
            if p1_ok { "✓" } else { "✗" },
            if p2_ok { "✓" } else { "✗" }
        );
        // Track joint-pass threshold with best (detect - fpr) margin.
        if p1_ok && p2_ok {
            let margin = detect - fpr;
            match &best_threshold {
                None => best_threshold = Some((thr, detect, fpr)),
                Some((_, d, f)) if margin > (*d - *f) => {
                    best_threshold = Some((thr, detect, fpr));
                }
                _ => (),
            }
        }
    }
    println!();

    // ── Summary verdict ──────────────────────────────────────────────────
    println!("## Verdict");
    match best_threshold {
        Some((thr, det, fp)) => {
            println!(
                "**L6-P1 + L6-P2 jointly PASS at threshold {:.2}** — detect {:.1}% (≥60%), FP {:.1}% (≤25%).",
                thr, det * 100.0, fp * 100.0
            );
            println!();
            println!("Recommended default threshold = {:.2}.", thr);
        }
        None => {
            println!("**No threshold jointly satisfies P1 (≥60%) and P2 (≤25%).** L6 introspect_recall as currently implemented does NOT meet the falsifiability gate — redesign required before L5/L7 can build on it.");
            println!();
            println!("Possible causes to investigate:");
            println!("- Embedding backend lacks discrimination (hash fallback active?)");
            println!("- Corpus design: fictional queries share too many tokens with stored content");
            println!("- k too small or too large for the novelty signal");
        }
    }

    Ok(())
}

fn embedding_name() -> &'static str {
    #[cfg(feature = "onnx-embed")]
    {
        "all-MiniLM-L6-v2 (ONNX)"
    }
    #[cfg(not(feature = "onnx-embed"))]
    {
        "fnv1a-hash-384"
    }
}
