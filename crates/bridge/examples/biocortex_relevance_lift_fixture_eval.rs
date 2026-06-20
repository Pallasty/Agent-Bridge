//! BioCortex relevance-lift fixture diagnostics.
//!
//! Read-only local harness for T6 headroom fixtures. It runs the existing
//! relevance-lift evaluator against explicit `query_cases`, then prints the
//! per-case rank fields that the Codex-facing MCP summary intentionally strips.
//!
//! This example does not register an MCP tool, write memory, mutate retrieval,
//! or expose live production ordering. It is an operator diagnostic for
//! answering "why did the redacted T6 summary report no lift?"
//!
//! ```text
//! AB_BIOCORTEX_RS=/path/to/biocortex-rs \
//!   cargo run -p ab-bridge --example biocortex_relevance_lift_fixture_eval
//! ```

use ab_bridge::biocortex_shadow::{
    biocortex_retrieval_relevance_lift_eval, run_retrieval_side_signal,
    BioCortexRetrievalCandidate, RelevanceLiftEvalOptions, RelevanceLiftQueryCase,
};
use ab_store::{
    default_db_path, BioCortexRetrievalOptInSideSignal, MemoryListSort, SqliteStore, StateStore,
};
use anyhow::{Context, Result};
use serde::Deserialize;
use serde_json::Value;
use std::collections::{BTreeSet, HashMap};
use std::path::{Path, PathBuf};

const DEFAULT_FIXTURE: &str =
    "docs/design/fixtures/memory-biocortex-relevance-lift-headroom-cases-2026-06-20.json";

#[derive(Debug, Deserialize)]
struct Fixture {
    schema: String,
    query_cases: Vec<FixtureCase>,
}

#[derive(Debug, Deserialize)]
struct FixtureCase {
    query: String,
    relevant_keys: Vec<String>,
    class_label: Option<String>,
    baseline_fts_rank_observed: Option<u64>,
}

#[tokio::main]
async fn main() -> Result<()> {
    let fixture_path = std::env::args()
        .nth(1)
        .map(PathBuf::from)
        .unwrap_or_else(|| PathBuf::from(DEFAULT_FIXTURE));
    let fixture = load_fixture(&fixture_path)?;
    let db_path = std::env::var("AB_BASELINE_DB")
        .ok()
        .map(PathBuf::from)
        .unwrap_or_else(default_db_path);
    let checkout = std::env::var("AB_BIOCORTEX_RS")
        .ok()
        .map(|value| value.trim().to_string())
        .filter(|s| !s.is_empty())
        .map(PathBuf::from);
    let limit = env_u32("AB_RELEVANCE_LIFT_LIMIT", 20).clamp(5, 100);
    let timeout_ms = env_u64("AB_RELEVANCE_LIFT_TIMEOUT_MS", 180_000).clamp(1_000, 600_000);
    let blend_alpha = env_f32("AB_RELEVANCE_LIFT_BLEND_ALPHA", 0.8).clamp(0.0, 1.0);

    let store = SqliteStore::open(&db_path)
        .await
        .with_context(|| format!("open {}", db_path.display()))?;
    let query_cases = fixture
        .query_cases
        .iter()
        .map(|case| RelevanceLiftQueryCase {
            query: case.query.clone(),
            relevant_keys: case.relevant_keys.clone(),
            class_label: case.class_label.clone(),
        })
        .collect::<Vec<_>>();

    let payload = biocortex_retrieval_relevance_lift_eval(
        &store,
        RelevanceLiftEvalOptions {
            sample_size: query_cases.len(),
            kind: None,
            query_cases,
            sort: MemoryListSort::ByImportance,
            limit,
            query_chars: 120,
            or_terms: 10,
            blend_alpha,
            coverage_threshold: 0.8,
            include_related: true,
            checkout: checkout.clone(),
            timeout_ms,
        },
    )
    .await;

    let side_rows = analyze_side_signal(
        &store,
        &fixture,
        checkout.as_deref(),
        limit,
        timeout_ms,
        blend_alpha,
    )
    .await?;

    print_report(&fixture_path, &fixture, &db_path, &payload, &side_rows);
    Ok(())
}

fn load_fixture(path: &PathBuf) -> Result<Fixture> {
    let raw = std::fs::read_to_string(path)
        .with_context(|| format!("read fixture {}", path.display()))?;
    let fixture: Fixture =
        serde_json::from_str(&raw).with_context(|| format!("parse fixture {}", path.display()))?;
    anyhow::ensure!(
        !fixture.query_cases.is_empty(),
        "fixture query_cases is empty"
    );
    for (idx, case) in fixture.query_cases.iter().enumerate() {
        anyhow::ensure!(
            !case.query.trim().is_empty(),
            "fixture case {} has empty query",
            idx
        );
        anyhow::ensure!(
            !case.relevant_keys.is_empty(),
            "fixture case {} has no relevant_keys",
            idx
        );
    }
    Ok(fixture)
}

#[derive(Debug)]
struct SideSignalCaseRow {
    sample_index: usize,
    class_label: String,
    baseline_source_rank: Option<usize>,
    baseline_first_relevant_rank: Option<usize>,
    reordered_source_rank: Option<usize>,
    reordered_first_relevant_rank: Option<usize>,
    source_side_rank: Option<usize>,
    source_side_score: Option<f32>,
    best_relevant_side_rank: Option<usize>,
    best_relevant_side_score: Option<f32>,
    top_side_relevant: bool,
    top_side_score: Option<f32>,
    distinct_side_scores: usize,
    top_score_tie_count: usize,
    matched: usize,
    coverage: f64,
}

async fn analyze_side_signal(
    store: &SqliteStore,
    fixture: &Fixture,
    checkout: Option<&Path>,
    limit: u32,
    timeout_ms: u64,
    blend_alpha: f32,
) -> Result<Vec<SideSignalCaseRow>> {
    let mut out = Vec::new();
    for (idx, case) in fixture.query_cases.iter().enumerate() {
        let baseline_hits = store
            .memory_search(&case.query, &[], limit)
            .await
            .with_context(|| format!("baseline memory_search for case {}", idx + 1))?;
        let baseline_ranking = baseline_hits
            .iter()
            .map(|hit| hit.record.key.clone())
            .collect::<Vec<_>>();
        let candidates = baseline_hits
            .iter()
            .map(|hit| BioCortexRetrievalCandidate {
                key: hit.record.key.clone(),
                content: hit.record.content.clone(),
            })
            .collect::<Vec<_>>();
        let source_key = case.relevant_keys.first().map(String::as_str);
        let relevant = case.relevant_keys.iter().cloned().collect::<BTreeSet<_>>();
        let run =
            run_retrieval_side_signal(&case.query, &candidates, source_key, checkout, timeout_ms)
                .await
                .map_err(|value| {
                    anyhow::anyhow!("side signal failed for case {}: {}", idx + 1, value)
                })?;
        let candidate_keys = candidates
            .iter()
            .map(|candidate| candidate.key.as_str())
            .collect::<BTreeSet<_>>();
        let mut side_scores = run
            .rows
            .into_iter()
            .filter(|row| row.query_id == "q_runtime_shadow")
            .filter(|row| candidate_keys.contains(row.candidate_key.as_str()))
            .map(|row| (row.candidate_key, row.score))
            .collect::<Vec<_>>();
        side_scores.sort_by(|a, b| {
            b.1.partial_cmp(&a.1)
                .unwrap_or(std::cmp::Ordering::Equal)
                .then_with(|| a.0.cmp(&b.0))
        });
        let side_by_key = side_scores
            .iter()
            .map(|(key, score)| (key.as_str(), *score))
            .collect::<HashMap<_, _>>();
        let side_signal_scores = side_scores
            .iter()
            .map(|(candidate_key, score)| BioCortexRetrievalOptInSideSignal {
                candidate_key: candidate_key.clone(),
                score: *score,
            })
            .collect::<Vec<_>>();
        let (reordered_hits, summary, _) = ab_store::biocortex_opt_in_apply_side_signal(
            &baseline_hits,
            &side_signal_scores,
            blend_alpha,
            0.8,
            true,
        );
        let reordered_ranking = reordered_hits
            .iter()
            .map(|hit| hit.record.key.clone())
            .collect::<Vec<_>>();

        let source_side_rank = source_key.and_then(|source| {
            side_scores
                .iter()
                .position(|(key, _)| key == source)
                .map(|pos| pos + 1)
        });
        let source_side_score = source_key.and_then(|source| side_by_key.get(source).copied());
        let (best_relevant_side_rank, best_relevant_side_score) = side_scores
            .iter()
            .enumerate()
            .find(|(_, (key, _))| relevant.contains(key))
            .map(|(idx, (_, score))| (Some(idx + 1), Some(*score)))
            .unwrap_or((None, None));
        let top_side_relevant = side_scores
            .first()
            .map(|(key, _)| relevant.contains(key))
            .unwrap_or(false);
        let top_side_score = side_scores.first().map(|(_, score)| *score);
        let distinct_side_scores = side_scores
            .iter()
            .fold(Vec::<f32>::new(), |mut acc, (_, score)| {
                if !acc
                    .iter()
                    .any(|existing| (*existing - *score).abs() < f32::EPSILON)
                {
                    acc.push(*score);
                }
                acc
            })
            .len();
        let top_score_tie_count = top_side_score
            .map(|top| {
                side_scores
                    .iter()
                    .filter(|(_, score)| (*score - top).abs() < f32::EPSILON)
                    .count()
            })
            .unwrap_or(0);

        out.push(SideSignalCaseRow {
            sample_index: idx,
            class_label: case
                .class_label
                .clone()
                .unwrap_or_else(|| "unlabelled".to_string()),
            baseline_source_rank: source_key.and_then(|source| rank_in(&baseline_ranking, source)),
            baseline_first_relevant_rank: first_relevant_rank(&baseline_ranking, &relevant),
            reordered_source_rank: source_key
                .and_then(|source| rank_in(&reordered_ranking, source)),
            reordered_first_relevant_rank: first_relevant_rank(&reordered_ranking, &relevant),
            source_side_rank,
            source_side_score,
            best_relevant_side_rank,
            best_relevant_side_score,
            top_side_relevant,
            top_side_score,
            distinct_side_scores,
            top_score_tie_count,
            matched: summary.matched_candidate_count,
            coverage: summary.coverage,
        });
    }
    Ok(out)
}

fn first_relevant_rank(ranking: &[String], relevant: &BTreeSet<String>) -> Option<usize> {
    ranking
        .iter()
        .position(|key| relevant.contains(key))
        .map(|idx| idx + 1)
}

fn rank_in(ranking: &[String], key: &str) -> Option<usize> {
    ranking
        .iter()
        .position(|candidate| candidate == key)
        .map(|idx| idx + 1)
}

fn print_report(
    fixture_path: &PathBuf,
    fixture: &Fixture,
    db_path: &PathBuf,
    payload: &Value,
    side_rows: &[SideSignalCaseRow],
) {
    println!("# BioCortex relevance-lift fixture diagnostics");
    println!("fixture: {}", fixture_path.display());
    println!("fixture_schema: {}", fixture.schema);
    println!("db: {}", db_path.display());
    println!("status: {}", cell(&payload["status"]));
    println!("verdict: {}", cell(&payload["verdict"]));
    println!(
        "sampling: evaluated={} side_signal_unavailable={} source={}",
        cell(&payload["sampling"]["evaluated_count"]),
        cell(&payload["sampling"]["side_signal_unavailable"]),
        cell(&payload["sampling"]["query_source"])
    );
    println!(
        "metrics: mrr_baseline={} mrr_reordered={} mrr_lift={} improved={} worsened={} unchanged={} source_found_count={}",
        cell(&payload["metrics"]["mrr_baseline"]),
        cell(&payload["metrics"]["mrr_reordered"]),
        cell(&payload["metrics"]["mrr_lift"]),
        cell(&payload["metrics"]["improved"]),
        cell(&payload["metrics"]["worsened"]),
        cell(&payload["metrics"]["unchanged"]),
        cell(&payload["metrics"]["source_found_count"]),
    );
    println!();
    println!("## Per-case rank rows");
    println!(
        "{:<4} {:<34} {:>8} {:>8} {:>9} {:>7} {:>7} {:>7} {:>7} {:>8}",
        "#", "class_label", "obs_fts", "base", "reorder", "delta", "rr", "match", "cov", "changed"
    );

    for sample in payload["samples"].as_array().into_iter().flatten() {
        let idx = sample["sample_index"].as_u64().unwrap_or(0) as usize;
        let fixture_case = fixture.query_cases.get(idx);
        let class_label = sample["class_label"]
            .as_str()
            .or_else(|| fixture_case.and_then(|case| case.class_label.as_deref()))
            .unwrap_or("unlabelled");
        println!(
            "{:<4} {:<34} {:>8} {:>8} {:>9} {:>7} {:>7} {:>7} {:>7} {:>8}",
            idx + 1,
            truncate(class_label, 34),
            fixture_case
                .and_then(|case| case.baseline_fts_rank_observed)
                .map(|rank| rank.to_string())
                .unwrap_or_else(|| "-".to_string()),
            rank_cell(&sample["baseline_rank_of_source"]),
            rank_cell(&sample["reordered_rank_of_source"]),
            cell(&sample["rank_delta"]),
            cell(&sample["rr_delta"]),
            cell(&sample["side_signal_matched"]),
            cell(&sample["side_signal_coverage"]),
            cell(&sample["order_changed"]),
        );
    }
    println!();
    println!("## Per-case side-signal scoring rows");
    println!(
        "{:<4} {:<34} {:>8} {:>8} {:>8} {:>8} {:>9} {:>9} {:>8} {:>8} {:>8} {:>7} {:>7} {:>7}",
        "#",
        "class_label",
        "src_b",
        "rel_b",
        "src_r",
        "rel_r",
        "src_side",
        "rel_side",
        "top_rel",
        "top_score",
        "distinct",
        "top_tie",
        "match",
        "cov"
    );
    for row in side_rows {
        println!(
            "{:<4} {:<34} {:>8} {:>8} {:>8} {:>8} {:>9} {:>9} {:>8} {:>8} {:>8} {:>7} {:>7} {:>7}",
            row.sample_index + 1,
            truncate(&row.class_label, 34),
            opt_usize(row.baseline_source_rank),
            opt_usize(row.baseline_first_relevant_rank),
            opt_usize(row.reordered_source_rank),
            opt_usize(row.reordered_first_relevant_rank),
            side_rank_score(row.source_side_rank, row.source_side_score),
            side_rank_score(row.best_relevant_side_rank, row.best_relevant_side_score),
            row.top_side_relevant,
            opt_f32(row.top_side_score),
            row.distinct_side_scores,
            row.top_score_tie_count,
            row.matched,
            format!("{:.3}", row.coverage),
        );
    }
    println!();
    println!("## Interpretation");
    println!(
        "- If `match` is low or `cov` is below the threshold, fix side-signal coverage before tuning rank blend."
    );
    println!(
        "- If `changed=true` but `delta=0`, the side-signal is moving distractors without lifting labelled relevant memory."
    );
    println!(
        "- If observed FTS rank differs from current `base`, the live store drifted; refresh the fixture observation before comparing lift."
    );
    println!(
        "- `src_side` is the primary source key's side-signal rank/score; `rel_side` is the best accept-set member's side-signal rank/score."
    );
    println!(
        "- If `top_rel=false` while coverage is high, BioCortex is scoring a distractor above every labelled relevant key."
    );
    println!(
        "- If `top_tie` is large or `distinct` is tiny, the side-signal is saturated and cannot reliably discriminate candidates."
    );
}

fn env_u32(name: &str, default: u32) -> u32 {
    std::env::var(name)
        .ok()
        .and_then(|v| v.parse().ok())
        .unwrap_or(default)
}

fn env_u64(name: &str, default: u64) -> u64 {
    std::env::var(name)
        .ok()
        .and_then(|v| v.parse().ok())
        .unwrap_or(default)
}

fn env_f32(name: &str, default: f32) -> f32 {
    std::env::var(name)
        .ok()
        .and_then(|v| v.parse().ok())
        .unwrap_or(default)
}

fn rank_cell(value: &Value) -> String {
    if value.is_null() {
        "-".to_string()
    } else {
        cell(value)
    }
}

fn cell(value: &Value) -> String {
    match value {
        Value::String(s) => s.clone(),
        Value::Null => "-".to_string(),
        other => other.to_string(),
    }
}

fn opt_usize(value: Option<usize>) -> String {
    value
        .map(|value| value.to_string())
        .unwrap_or_else(|| "-".to_string())
}

fn opt_f32(value: Option<f32>) -> String {
    value
        .map(|value| format!("{value:.3}"))
        .unwrap_or_else(|| "-".to_string())
}

fn side_rank_score(rank: Option<usize>, score: Option<f32>) -> String {
    match (rank, score) {
        (Some(rank), Some(score)) => format!("{rank}/{score:.3}"),
        _ => "-".to_string(),
    }
}

fn truncate(value: &str, max_chars: usize) -> String {
    let mut out = value.chars().take(max_chars).collect::<String>();
    if value.chars().count() > max_chars {
        out.push_str("...");
    }
    out
}
