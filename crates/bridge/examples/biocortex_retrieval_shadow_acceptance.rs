//! BioCortex retrieval shadow runtime acceptance.
//!
//! Small labeled harness for the review-only runtime shadow surface. It uses
//! explicit candidates, runs the optional BioCortex side-signal adapter, and
//! asserts that boundary fields stay read-only/default-order-preserving. This
//! is not an approval to alter `memory_search`.

#[cfg(feature = "biocortex-retrieval-shadow")]
use ab_bridge::biocortex_shadow::{
    biocortex_retrieval_shadow_report, BioCortexRetrievalCandidate,
    BioCortexRetrievalShadowOptions, BIOCORTEX_RETRIEVAL_DISABLE_ENV,
    BIOCORTEX_RETRIEVAL_SHADOW_ENABLE_ENV,
};
#[cfg(feature = "biocortex-retrieval-shadow")]
use anyhow::{anyhow, Context};
#[cfg(feature = "biocortex-retrieval-shadow")]
use serde::Deserialize;
#[cfg(feature = "biocortex-retrieval-shadow")]
use serde_json::{json, Value};
#[cfg(feature = "biocortex-retrieval-shadow")]
use std::path::PathBuf;

#[cfg(feature = "biocortex-retrieval-shadow")]
const DEFAULT_FIXTURE: &str =
    include_str!("../tests/fixtures/biocortex_retrieval_shadow_acceptance.jsonl");

#[cfg(feature = "biocortex-retrieval-shadow")]
#[derive(Debug, Deserialize)]
struct AcceptanceCase {
    id: String,
    intent: String,
    query: String,
    expected_key: String,
    expected_baseline_top: String,
    expected_advisory_top: String,
    expected_regressed: bool,
    candidates: Vec<BioCortexRetrievalCandidate>,
}

#[cfg(feature = "biocortex-retrieval-shadow")]
#[derive(Debug)]
struct CaseResult {
    id: String,
    intent: String,
    expected_key: String,
    baseline_top: String,
    advisory_top: String,
    regressed: bool,
    latency_ms: f64,
}

#[cfg(feature = "biocortex-retrieval-shadow")]
#[tokio::main]
async fn main() -> anyhow::Result<()> {
    let cases = load_cases()?;
    anyhow::ensure!(!cases.is_empty(), "acceptance corpus is empty");

    std::env::set_var(BIOCORTEX_RETRIEVAL_SHADOW_ENABLE_ENV, "1");
    std::env::remove_var(BIOCORTEX_RETRIEVAL_DISABLE_ENV);
    std::env::set_var("AB_BIOCORTEX_RETRIEVAL_ALPHA_POLICY", "candidate-strong");

    let checkout = std::env::var("AB_BIOCORTEX_RS")
        .ok()
        .filter(|path| !path.trim().is_empty())
        .map(PathBuf::from);

    let mut results = Vec::new();
    for case in cases {
        let payload = biocortex_retrieval_shadow_report(BioCortexRetrievalShadowOptions {
            query: case.query.clone(),
            candidates: case.candidates.clone(),
            expected_key: Some(case.expected_key.clone()),
            checkout: checkout.clone(),
            timeout_ms: 30_000,
            include_raw: false,
        })
        .await;

        verify_case(&case, &payload)?;
        results.push(CaseResult {
            id: case.id,
            intent: case.intent,
            expected_key: case.expected_key,
            baseline_top: string_field(&payload, "baseline_top_key")?,
            advisory_top: string_field(&payload, "advisory_top_key")?,
            regressed: payload
                .pointer("/expected/regressed")
                .and_then(Value::as_bool)
                .unwrap_or(false),
            latency_ms: payload
                .get("latency_ms")
                .and_then(Value::as_f64)
                .unwrap_or(0.0),
        });
    }

    print_report(&results);
    Ok(())
}

#[cfg(not(feature = "biocortex-retrieval-shadow"))]
fn main() {
    eprintln!(
        "biocortex_retrieval_shadow_acceptance requires --features biocortex-retrieval-shadow"
    );
    std::process::exit(2);
}

#[cfg(feature = "biocortex-retrieval-shadow")]
fn load_cases() -> anyhow::Result<Vec<AcceptanceCase>> {
    let raw = match std::env::var("BIOCORTEX_RETRIEVAL_SHADOW_ACCEPTANCE")
        .ok()
        .filter(|path| !path.trim().is_empty())
        .map(PathBuf::from)
    {
        Some(path) => {
            std::fs::read_to_string(&path).with_context(|| format!("read {}", path.display()))?
        }
        None => DEFAULT_FIXTURE.to_string(),
    };

    raw.lines()
        .map(str::trim)
        .filter(|line| !line.is_empty())
        .map(|line| serde_json::from_str::<AcceptanceCase>(line).map_err(anyhow::Error::from))
        .collect()
}

#[cfg(feature = "biocortex-retrieval-shadow")]
fn verify_case(case: &AcceptanceCase, payload: &Value) -> anyhow::Result<()> {
    let status = string_field(payload, "status")?;
    anyhow::ensure!(status == "ok", "{} status={status}", case.id);
    anyhow::ensure!(
        payload.get("read_only").and_then(Value::as_bool) == Some(true),
        "{} must stay read_only",
        case.id
    );
    anyhow::ensure!(
        payload
            .get("runtime_adapter_approved")
            .and_then(Value::as_bool)
            == Some(false),
        "{} must keep runtime_adapter_approved=false",
        case.id
    );
    anyhow::ensure!(
        payload
            .get("default_search_order_changed")
            .and_then(Value::as_bool)
            == Some(false),
        "{} must not change default search order",
        case.id
    );
    anyhow::ensure!(
        payload.get("side_signal_coverage").and_then(Value::as_f64) == Some(1.0),
        "{} must have full side-signal coverage",
        case.id
    );
    anyhow::ensure!(
        string_field(payload, "baseline_top_key")? == case.expected_baseline_top,
        "{} baseline top changed",
        case.id
    );
    anyhow::ensure!(
        string_field(payload, "advisory_top_key")? == case.expected_advisory_top,
        "{} advisory top changed",
        case.id
    );
    anyhow::ensure!(
        payload
            .pointer("/expected/regressed")
            .and_then(Value::as_bool)
            == Some(case.expected_regressed),
        "{} expected regression label changed",
        case.id
    );
    Ok(())
}

#[cfg(feature = "biocortex-retrieval-shadow")]
fn string_field(payload: &Value, key: &str) -> anyhow::Result<String> {
    payload
        .get(key)
        .and_then(Value::as_str)
        .map(str::to_string)
        .ok_or_else(|| anyhow!("missing string field {key}"))
}

#[cfg(feature = "biocortex-retrieval-shadow")]
fn print_report(results: &[CaseResult]) {
    println!("# BioCortex Retrieval Shadow Acceptance");
    println!();
    println!("| case | intent | expected | baseline_top | advisory_top | regressed | latency_ms |");
    println!("|---|---|---|---|---|---:|---:|");
    for row in results {
        println!(
            "| {} | {} | {} | {} | {} | {} | {:.3} |",
            row.id,
            row.intent,
            row.expected_key,
            row.baseline_top,
            row.advisory_top,
            row.regressed,
            row.latency_ms
        );
    }
    println!();
    println!("```json");
    println!(
        "{}",
        serde_json::to_string_pretty(&json!({
            "schema": "agent_bridge.biocortex_retrieval_shadow_acceptance.v0",
            "status": "pass",
            "read_only": true,
            "runtime_adapter_approved": false,
            "default_search_order_changed": false,
            "case_count": results.len(),
            "expected_regression_cases": results.iter().filter(|row| row.regressed).count(),
        }))
        .unwrap_or_default()
    );
    println!("```");
}
