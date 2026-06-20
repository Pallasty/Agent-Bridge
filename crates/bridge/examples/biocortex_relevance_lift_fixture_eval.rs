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
    biocortex_retrieval_relevance_lift_eval, RelevanceLiftEvalOptions, RelevanceLiftQueryCase,
};
use ab_store::{default_db_path, MemoryListSort, SqliteStore};
use anyhow::{Context, Result};
use serde::Deserialize;
use serde_json::Value;
use std::path::PathBuf;

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
            checkout,
            timeout_ms,
        },
    )
    .await;

    print_report(&fixture_path, &fixture, &db_path, &payload);
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

fn print_report(fixture_path: &PathBuf, fixture: &Fixture, db_path: &PathBuf, payload: &Value) {
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

fn truncate(value: &str, max_chars: usize) -> String {
    let mut out = value.chars().take(max_chars).collect::<String>();
    if value.chars().count() > max_chars {
        out.push_str("...");
    }
    out
}
