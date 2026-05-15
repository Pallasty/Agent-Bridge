//! L6 v2 — three-signal comparison harness.
//!
//! Reads `tests/l6_corpus.jsonl` (25 grounded + 25 fictional) and computes
//! three candidate "grounding" signals side-by-side on the same top-K
//! cosine hits, then runs threshold sweeps + Youden's J for each:
//!
//! - **S0 cosine-novelty** (v0 from `l6_eval`):
//!   `1 − max_cosine` across top-K.
//! - **S-A entity-presence** (Option A):
//!   extract distinctive identifiers from the query and report the
//!   fraction of those identifiers NOT present verbatim in any top-K
//!   content body. No identifiers in query ⇒ signal is 0.5 (abstain).
//! - **S-B content-overlap** (Option B):
//!   tokenise + lowercase + stopword-strip query; compute
//!   `1 − max overlap_fraction across top-K`, where
//!   `overlap_fraction = |Q ∩ C| / |Q|`.
//!
//! Higher = more "ungrounded". Same P1 (detect ≥ 60% fictional) and
//! P2 (FP ≤ 25% grounded) gates as `l6_eval`.
//!
//! Run:
//!   AGENT_BRIDGE_DB=/path/to/state.db \
//!     cargo run --release -p ab-bridge --example l6_eval_v2

use ab_store::{MemoryCosineHit, SqliteStore, StateStore};
use serde::Deserialize;
use std::collections::HashSet;
use std::path::PathBuf;
use std::sync::Arc;

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
    s0: f32,
    sa: f32,
    sa_n: usize,
    sb: f32,
    sb_n: usize,
}

const STOPWORDS: &[&str] = &[
    "the", "a", "an", "of", "in", "on", "at", "to", "for", "with", "by",
    "from", "as", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "but", "or", "and", "if",
    "then", "else", "when", "where", "why", "how", "what", "which", "who",
    "whom", "this", "that", "these", "those", "it", "its", "they", "them",
    "their", "we", "us", "our", "you", "your", "i", "me", "my", "can",
    "could", "should", "would", "may", "might", "must", "shall", "will",
    "about", "into", "out", "up", "down", "over", "under", "again",
    "further", "more", "most", "other", "some", "such", "no", "nor",
    "not", "only", "own", "same", "so", "than", "too", "very", "just",
    "now", "use", "uses", "used", "using", "via", "between", "after",
    "before", "during",
];

fn is_stopword(t: &str) -> bool {
    STOPWORDS.contains(&t)
}

fn tokenize(s: &str) -> Vec<String> {
    let mut out = Vec::new();
    let mut cur = String::new();
    for c in s.chars() {
        if c.is_ascii_alphanumeric() || c == '_' {
            cur.push(c.to_ascii_lowercase());
        } else if !cur.is_empty() {
            out.push(std::mem::take(&mut cur));
        }
    }
    if !cur.is_empty() {
        out.push(cur);
    }
    out
}

fn is_distinctive(t: &str) -> bool {
    if t.len() < 3 {
        return false;
    }
    if t.contains('/') && !t.starts_with("//") {
        return true;
    }
    if t.len() >= 7
        && t.len() <= 40
        && t.chars().all(|c| c.is_ascii_digit() || ('a'..='f').contains(&c.to_ascii_lowercase()))
        && t.chars().any(|c| c.is_ascii_alphabetic())
    {
        return true;
    }
    if t.contains('_') && t.len() >= 4 {
        return true;
    }
    let chars: Vec<char> = t.chars().collect();
    if chars.len() >= 4
        && chars.iter().any(|c| c.is_uppercase())
        && chars.iter().any(|c| c.is_lowercase())
    {
        return true;
    }
    if t.len() >= 3
        && t.chars().all(|c| c.is_uppercase() || c.is_ascii_digit())
        && t.chars().any(|c| c.is_alphabetic())
    {
        return true;
    }
    false
}

fn extract_identifiers(q: &str) -> Vec<String> {
    let mut out: Vec<String> = Vec::new();
    let mut seen: HashSet<String> = HashSet::new();

    // Back-tick spans first.
    let mut in_tick = false;
    let mut tick_buf = String::new();
    for c in q.chars() {
        if c == '`' {
            if in_tick && !tick_buf.is_empty() {
                let t = std::mem::take(&mut tick_buf);
                if t.len() >= 3 && seen.insert(t.clone()) {
                    out.push(t);
                }
            }
            in_tick = !in_tick;
        } else if in_tick {
            tick_buf.push(c);
        }
    }

    // #NNN post numbers.
    let bytes = q.as_bytes();
    let mut i = 0;
    while i < bytes.len() {
        if bytes[i] == b'#' && i + 1 < bytes.len() && bytes[i + 1].is_ascii_digit() {
            let mut j = i + 1;
            while j < bytes.len() && bytes[j].is_ascii_digit() {
                j += 1;
            }
            let tok = std::str::from_utf8(&bytes[i..j]).unwrap_or("").to_string();
            if tok.len() >= 2 && seen.insert(tok.clone()) {
                out.push(tok);
            }
            i = j;
            continue;
        }
        i += 1;
    }

    // Word-shape scan.
    let mut cur = String::new();
    for c in q.chars() {
        if c.is_alphanumeric() || c == '_' || c == '-' || c == '/' || c == '.' {
            cur.push(c);
        } else {
            if !cur.is_empty() {
                let cand = std::mem::take(&mut cur);
                if is_distinctive(&cand) && seen.insert(cand.clone()) {
                    out.push(cand);
                }
            }
        }
    }
    if !cur.is_empty() && is_distinctive(&cur) && seen.insert(cur.clone()) {
        out.push(cur);
    }

    out
}

fn signal_cosine_novelty(hits: &[MemoryCosineHit]) -> f32 {
    if hits.is_empty() {
        return 1.0;
    }
    let max_cos = hits.iter().map(|h| h.cosine).fold(f32::NEG_INFINITY, f32::max);
    (1.0 - max_cos).clamp(0.0, 1.0)
}

fn signal_entity_presence(query: &str, hits: &[MemoryCosineHit]) -> (f32, usize) {
    let ids = extract_identifiers(query);
    let n = ids.len();
    if n == 0 {
        return (0.5, 0);
    }
    let mut absent = 0;
    for id in &ids {
        let lower = id.to_lowercase();
        let any = hits.iter().any(|h| h.record.content.to_lowercase().contains(&lower));
        if !any {
            absent += 1;
        }
    }
    (absent as f32 / n as f32, n)
}

fn signal_content_overlap(query: &str, hits: &[MemoryCosineHit]) -> (f32, usize) {
    let q_terms: HashSet<String> = tokenize(query)
        .into_iter()
        .filter(|t| t.len() > 2 && !is_stopword(t))
        .collect();
    let q_size = q_terms.len();
    if q_size == 0 || hits.is_empty() {
        return (1.0, q_size);
    }
    let mut max_overlap = 0.0_f32;
    for h in hits {
        let c_terms: HashSet<String> = tokenize(&h.record.content)
            .into_iter()
            .filter(|t| t.len() > 2 && !is_stopword(t))
            .collect();
        let inter = q_terms.iter().filter(|t| c_terms.contains(*t)).count();
        let frac = inter as f32 / q_size as f32;
        if frac > max_overlap {
            max_overlap = frac;
        }
    }
    ((1.0 - max_overlap).clamp(0.0, 1.0), q_size)
}

fn sweep(name: &str, rows: &[Row], get: impl Fn(&Row) -> f32, total_g: usize, total_f: usize) {
    println!("## {} threshold sweep", name);
    println!();
    println!("| thr | detect | FP | Youden J | P1 ≥60% | P2 ≤25% |");
    println!("|---|---|---|---|---|---|");
    for thr_pct in (5..=95).step_by(5) {
        let thr = thr_pct as f32 / 100.0;
        let mut tp = 0usize;
        let mut fp = 0usize;
        for r in rows {
            let v = get(r);
            let above = v >= thr;
            match r.item.label.as_str() {
                "fictional" if above => tp += 1,
                "grounded" if above => fp += 1,
                _ => (),
            }
        }
        let sens = tp as f32 / total_f.max(1) as f32;
        let spec = 1.0 - fp as f32 / total_g.max(1) as f32;
        let j = sens + spec - 1.0;
        println!(
            "| {:.2} | {:.0}% ({}/{}) | {:.0}% ({}/{}) | {:+.3} | {} | {} |",
            thr,
            sens * 100.0, tp, total_f,
            (1.0 - spec) * 100.0, fp, total_g,
            j,
            if sens >= 0.60 { "✓" } else { "✗" },
            if (1.0 - spec) <= 0.25 { "✓" } else { "✗" }
        );
    }
    println!();
}

#[tokio::main]
async fn main() -> anyhow::Result<()> {
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

    eprintln!("L6 eval v2 — db={} corpus={} k={}", db_path.display(), corpus_path.display(), k);
    let corpus_raw = std::fs::read_to_string(&corpus_path)?;
    let items: Vec<CorpusItem> = corpus_raw
        .lines()
        .filter(|l| !l.trim().is_empty())
        .map(|l| serde_json::from_str::<CorpusItem>(l).map_err(anyhow::Error::from))
        .collect::<Result<_, _>>()?;
    let total_g = items.iter().filter(|i| i.label == "grounded").count();
    let total_f = items.iter().filter(|i| i.label == "fictional").count();
    eprintln!("corpus: {} grounded + {} fictional", total_g, total_f);

    let store: Arc<dyn StateStore> = Arc::new(SqliteStore::open(&db_path).await?);
    let _ = store.memory_top_k_cosine("warm-up", k).await?;

    let mut rows: Vec<Row> = Vec::with_capacity(items.len());
    for item in &items {
        let hits = store.memory_top_k_cosine(&item.query, k).await?;
        let s0 = signal_cosine_novelty(&hits);
        let (sa, sa_n) = signal_entity_presence(&item.query, &hits);
        let (sb, sb_n) = signal_content_overlap(&item.query, &hits);
        rows.push(Row { item: item.clone(), s0, sa, sa_n, sb, sb_n });
    }

    println!("# L6 v2 — three-signal comparison");
    println!();
    println!("Backend: all-MiniLM-L6-v2 (ONNX) | k={} | corpus={} items", k, items.len());
    println!();
    println!("## Per-item, all three signals");
    println!();
    println!("| id | label | S0 cosine-nov | S-A entity (n_ids) | S-B content-ovr (n_terms) | query (≤72c) |");
    println!("|---|---|---|---|---|---|");
    for r in &rows {
        let q: String = r.item.query.chars().take(72).collect();
        println!(
            "| {} | {} | {:.3} | {:.3} ({}) | {:.3} ({}) | {} |",
            r.item.id, r.item.label, r.s0, r.sa, r.sa_n, r.sb, r.sb_n, q
        );
    }
    println!();

    sweep("S0 cosine-novelty", &rows, |r| r.s0, total_g, total_f);
    sweep("S-A entity-presence", &rows, |r| r.sa, total_g, total_f);
    sweep("S-B content-overlap", &rows, |r| r.sb, total_g, total_f);

    // Best joint pass across all (signal, threshold) pairs.
    let mut best: Option<(String, f32, f32, f32, f32)> = None;
    for (name, get) in [
        ("S0 cosine-novelty", Box::new(|r: &Row| r.s0) as Box<dyn Fn(&Row) -> f32>),
        ("S-A entity-presence", Box::new(|r: &Row| r.sa)),
        ("S-B content-overlap", Box::new(|r: &Row| r.sb)),
    ] {
        for thr_pct in (5..=95).step_by(5) {
            let thr = thr_pct as f32 / 100.0;
            let mut tp = 0usize;
            let mut fp = 0usize;
            for r in &rows {
                let v = get(r);
                let above = v >= thr;
                match r.item.label.as_str() {
                    "fictional" if above => tp += 1,
                    "grounded" if above => fp += 1,
                    _ => (),
                }
            }
            let sens = tp as f32 / total_f.max(1) as f32;
            let spec = 1.0 - fp as f32 / total_g.max(1) as f32;
            let j = sens + spec - 1.0;
            let p1_ok = sens >= 0.60;
            let p2_ok = (1.0 - spec) <= 0.25;
            if p1_ok && p2_ok {
                let cand = (name.to_string(), thr, sens, 1.0 - spec, j);
                match &best {
                    None => best = Some(cand),
                    Some(prev) if j > prev.4 => best = Some(cand),
                    _ => (),
                }
            }
        }
    }

    println!();
    println!("## Verdict (best joint P1+P2 PASS)");
    println!();
    match best {
        Some((name, thr, sens, fpr, j)) => {
            println!(
                "**{} at threshold {:.2}** — detect {:.1}% / FP {:.1}% / J={:.3}",
                name, thr, sens * 100.0, fpr * 100.0, j
            );
        }
        None => {
            println!("**No (signal, threshold) jointly satisfies P1 ≥60% and P2 ≤25%.** All three candidate signals fail the gate on this corpus.");
        }
    }
    Ok(())
}
