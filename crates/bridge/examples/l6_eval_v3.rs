//! L6 v3 — Option E (LLM-as-relevance) evaluation harness.
//!
//! Reads `tests/l6_corpus.jsonl` (25 grounded + 25 fictional) and runs the
//! Option E Stage-2 LLM probe on top of the same Stage-1 cosine top-K used
//! by `l6_eval` (v0) and `l6_eval_v2`. Produces:
//!
//! - Per-class table: grounded vs fictional `probability_grounded` mean ± stddev
//! - Welch's t-test on `probability_grounded`
//! - Threshold sweep (0.10..=0.90 step 0.05): detect rate (fictional with
//!   `probability_grounded < t`) and FP rate (grounded with
//!   `probability_grounded < t`)
//! - Max Youden's J + best threshold
//! - L6-P1 verdict: max detect at FP ≤ 25% ≥ 60% ?
//! - L6-P2 verdict: max FP at detect ≥ 60% ≤ 25% ?
//! - Joint PASS criterion: same threshold yields detect ≥ 60% AND FP ≤ 25%
//! - Per-class `quote_verified_rate` diagnostic
//!
//! Run (release recommended):
//!   ANTHROPIC_API_KEY=... AB_INTROSPECT_LLM_MAX_PER_HOUR=200 \
//!     AGENT_BRIDGE_DB=/path/to/state.db \
//!     cargo run --release -p ab-bridge --example l6_eval_v3

use ab_store::{SqliteStore, StateStore};
use serde::Deserialize;
use std::path::PathBuf;
use std::sync::Arc;

use ab_bridge::llm_client::LlmClient;
use ab_bridge::mcp_tools::{option_e_run, OptionEResult};

#[derive(Debug, Deserialize, Clone)]
struct CorpusItem {
    id: String,
    label: String,
    query: String,
    #[allow(dead_code)]
    rationale: String,
}

#[derive(Clone)]
struct Row {
    item: CorpusItem,
    probability_grounded: f32,
    quote_verified_count: usize,
    top_k_count: usize,
    latency_ms: u128,
    llm_in_tokens: u32,
    llm_out_tokens: u32,
}

fn mean(xs: &[f32]) -> f32 {
    if xs.is_empty() {
        return 0.0;
    }
    xs.iter().sum::<f32>() / xs.len() as f32
}

fn stddev(xs: &[f32]) -> f32 {
    if xs.len() < 2 {
        return 0.0;
    }
    let m = mean(xs);
    let var = xs.iter().map(|x| (x - m).powi(2)).sum::<f32>() / (xs.len() - 1) as f32;
    var.sqrt()
}

/// Welch's t-test (returns t-statistic; df omitted — eval uses |t| > 2 as the
/// rough significance cue, consistent with v0/v2 reports).
fn welch_t(a: &[f32], b: &[f32]) -> f32 {
    let ma = mean(a);
    let mb = mean(b);
    let va = stddev(a).powi(2);
    let vb = stddev(b).powi(2);
    let denom = (va / a.len() as f32 + vb / b.len() as f32).sqrt();
    if denom == 0.0 {
        0.0
    } else {
        (ma - mb) / denom
    }
}

fn corpus_path() -> PathBuf {
    // 1. Explicit override
    if let Ok(p) = std::env::var("L6_CORPUS_PATH") {
        return PathBuf::from(p);
    }
    // 2. CARGO_MANIFEST_DIR (only when run via `cargo run`)
    if let Ok(m) = std::env::var("CARGO_MANIFEST_DIR") {
        let p = PathBuf::from(&m);
        if let (Some(a), Some(b)) = (p.parent(), p.parent().and_then(|x| x.parent())) {
            let candidate = b.join("tests/l6_corpus.jsonl");
            if candidate.exists() {
                return candidate;
            }
            let _ = a; // keep borrow checker quiet
        }
    }
    // 3. Walk up from current dir looking for `tests/l6_corpus.jsonl`.
    if let Ok(mut cwd) = std::env::current_dir() {
        loop {
            let candidate = cwd.join("tests/l6_corpus.jsonl");
            if candidate.exists() {
                return candidate;
            }
            if !cwd.pop() {
                break;
            }
        }
    }
    // 4. Final fallback (will fail open in `read_to_string` with a clear msg)
    PathBuf::from("tests/l6_corpus.jsonl")
}

#[tokio::main(flavor = "current_thread")]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    let db_path = std::env::var("AGENT_BRIDGE_DB").unwrap_or_else(|_| {
        std::env::var("HOME")
            .map(|h| format!("{h}/.local/share/agent-bridge/state.db"))
            .unwrap_or_else(|_| "./state.db".into())
    });
    eprintln!("# L6 v3 — Option E (LLM-as-relevance) eval");
    eprintln!("- DB: {db_path}");

    let store: Arc<dyn StateStore> =
        Arc::new(SqliteStore::open(std::path::Path::new(&db_path)).await?);
    let llm = LlmClient::from_env().map_err(|e| format!("LlmClient::from_env: {e}"))?;
    eprintln!("- LLM provider: {}", llm.provider());

    let corpus_p = corpus_path();
    eprintln!("- Corpus: {}", corpus_p.display());
    let raw = std::fs::read_to_string(&corpus_p)?;
    let items: Vec<CorpusItem> = raw
        .lines()
        .filter(|l| !l.trim().is_empty())
        .map(|l| serde_json::from_str::<CorpusItem>(l).expect("bad corpus row"))
        .collect();
    eprintln!(
        "- {} items ({} grounded / {} fictional)",
        items.len(),
        items.iter().filter(|i| i.label == "grounded").count(),
        items.iter().filter(|i| i.label == "fictional").count(),
    );

    let mut rows: Vec<Row> = Vec::with_capacity(items.len());
    for (i, item) in items.iter().enumerate() {
        // Stage 1: top-K cosine
        let hits = store.memory_top_k_cosine(&item.query, 5).await?;
        if hits.is_empty() {
            eprintln!("  [{i}] {} — NO hits, skipping", item.id);
            continue;
        }
        // Stage 2: Option E LLM probe
        let res: OptionEResult = match option_e_run(&item.query, &hits, &llm).await {
            Ok(r) => r,
            Err(e) => {
                eprintln!(
                    "  [{i}] {} — Option E error: {e}; falling back probability=0.5",
                    item.id
                );
                continue;
            }
        };
        let verified = res.per_doc.iter().filter(|d| d.quote_verified).count();
        let score_sum_raw: u32 = res.per_doc.iter().map(|d| d.score_raw as u32).sum();
        let score_sum_verified: u32 = res
            .per_doc
            .iter()
            .map(|d| d.score_after_verify as u32)
            .sum();
        rows.push(Row {
            item: item.clone(),
            probability_grounded: res.probability_grounded,
            quote_verified_count: verified,
            top_k_count: res.per_doc.len(),
            latency_ms: res.llm_latency_ms,
            llm_in_tokens: res.llm_input_tokens,
            llm_out_tokens: res.llm_output_tokens,
        });
        eprintln!(
            "  [{i:>2}] {} {} p={:.3} verified={}/{} sum_raw={} sum_ver={} latency={}ms",
            item.id,
            item.label,
            res.probability_grounded,
            verified,
            res.per_doc.len(),
            score_sum_raw,
            score_sum_verified,
            res.llm_latency_ms,
        );
    }

    println!();
    println!("# Result");
    println!();

    let grounded: Vec<f32> = rows
        .iter()
        .filter(|r| r.item.label == "grounded")
        .map(|r| r.probability_grounded)
        .collect();
    let fictional: Vec<f32> = rows
        .iter()
        .filter(|r| r.item.label == "fictional")
        .map(|r| r.probability_grounded)
        .collect();

    println!("## Per-class summary");
    println!();
    println!("| Class | n | mean prob_grounded | stddev | min | max |");
    println!("|---|---|---|---|---|---|");
    for (label, xs) in [("grounded", &grounded), ("fictional", &fictional)] {
        let mn = xs.iter().cloned().fold(f32::INFINITY, f32::min);
        let mx = xs.iter().cloned().fold(f32::NEG_INFINITY, f32::max);
        println!(
            "| {} | {} | {:.3} | {:.3} | {:.3} | {:.3} |",
            label,
            xs.len(),
            mean(xs),
            stddev(xs),
            mn,
            mx,
        );
    }
    println!();
    let t = welch_t(&grounded, &fictional);
    println!("- Welch's t (grounded − fictional) = {t:.3}");
    println!("- Note: positive t means grounded probability > fictional, expected sign for a working signal.");
    println!();

    println!("## Threshold sweep");
    println!();
    println!("| Threshold | Detect (fictional < t) | FP (grounded < t) | Youden's J |");
    println!("|---|---|---|---|");
    let mut best_j = -1.0_f32;
    let mut best_t = 0.0_f32;
    let mut best_detect = 0.0_f32;
    let mut best_fp = 0.0_f32;
    let mut p1_p2_pass: Option<(f32, f32, f32)> = None; // (t, detect, fp)
    let mut thr = 0.10_f32;
    while thr <= 0.901 {
        let detect = if fictional.is_empty() {
            0.0
        } else {
            fictional.iter().filter(|p| **p < thr).count() as f32 / fictional.len() as f32
        };
        let fp = if grounded.is_empty() {
            0.0
        } else {
            grounded.iter().filter(|p| **p < thr).count() as f32 / grounded.len() as f32
        };
        let j = detect - fp;
        println!(
            "| {thr:.2} | {:.1}% | {:.1}% | {j:+.3} |",
            detect * 100.0,
            fp * 100.0
        );
        if j > best_j {
            best_j = j;
            best_t = thr;
            best_detect = detect;
            best_fp = fp;
        }
        if detect >= 0.60 && fp <= 0.25 && p1_p2_pass.is_none() {
            p1_p2_pass = Some((thr, detect, fp));
        }
        thr += 0.05;
    }
    println!();
    println!(
        "**Max Youden's J = {best_j:+.3} at threshold {best_t:.2} (detect {:.1}%, FP {:.1}%)**",
        best_detect * 100.0,
        best_fp * 100.0,
    );
    println!();

    println!("## L6-P1 + L6-P2 verdict (rule 2 thresholds unchanged)");
    println!();
    match p1_p2_pass {
        Some((t, d, fp)) => println!(
            "✅ **PASS** at threshold {t:.2}: detect {:.1}% (≥ 60%), FP {:.1}% (≤ 25%).",
            d * 100.0,
            fp * 100.0,
        ),
        None => println!(
            "❌ **FAIL**: no threshold satisfies detect ≥ 60% AND FP ≤ 25% jointly. Best J was {best_j:+.3} at {best_t:.2}.",
        ),
    }
    println!();

    println!("## Verbatim-quote verification diagnostic");
    println!();
    let mut gv = 0usize;
    let mut gt = 0usize;
    let mut fv = 0usize;
    let mut ft = 0usize;
    for r in &rows {
        if r.item.label == "grounded" {
            gv += r.quote_verified_count;
            gt += r.top_k_count;
        } else {
            fv += r.quote_verified_count;
            ft += r.top_k_count;
        }
    }
    if gt > 0 {
        println!(
            "- grounded class: {gv}/{gt} quotes verified ({:.1}%)",
            gv as f32 / gt as f32 * 100.0
        );
    }
    if ft > 0 {
        println!(
            "- fictional class: {fv}/{ft} quotes verified ({:.1}%)",
            fv as f32 / ft as f32 * 100.0
        );
    }
    println!();

    println!("## LLM cost diagnostic");
    println!();
    let total_in: u64 = rows.iter().map(|r| r.llm_in_tokens as u64).sum();
    let total_out: u64 = rows.iter().map(|r| r.llm_out_tokens as u64).sum();
    let total_latency: u128 = rows.iter().map(|r| r.latency_ms).sum();
    println!(
        "- {} calls, input tokens {total_in}, output tokens {total_out}, total LLM wallclock {:.1}s, mean latency {}ms",
        rows.len(),
        total_latency as f32 / 1000.0,
        if rows.is_empty() { 0 } else { (total_latency / rows.len() as u128) as u128 },
    );

    Ok(())
}
