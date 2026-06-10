//! BioCortex retrieval gate eval.
//!
//! Read-only offline harness for deciding whether a future BioCortex side
//! signal is good enough to influence Agent-Bridge retrieval. It never calls
//! `memory_search`, writes memory, or registers a runtime embedding backend.

use ab_store::{cosine_similarity, embedding::default_backend};
use serde::Deserialize;
use std::collections::HashMap;
use std::path::PathBuf;

const DEFAULT_CORPUS_PATH: &str =
    "crates/bridge/tests/fixtures/biocortex_retrieval_gate_corpus.jsonl";
const CONSERVATIVE_ALPHA: f32 = 0.20;
const CANDIDATE_STRONG_ALPHA: f32 = 0.80;

const DEFAULT_CORPUS: &str = r#"
{"id":"q_shadow_digest","query":"Which BioCortex boundary keeps retrieval as read-only shadow telemetry without mutating AB memory, memory_search, or retrieval vectors?","expected_key":"decision_shadow_only","candidates":[{"key":"decision_shadow_only","content":"BioCortex is integrated as read-only shadow telemetry. AB does not link BioCortex into the runtime, mutate memory, or change retrieval vectors."},{"key":"substrate_replay","content":"The substrate replay plan maps AB shadow-cortex events into deterministic BioCortex input pulses."},{"key":"mcp_lifecycle","content":"MCP lifecycle digest separates tool readiness from daemon HTTP reachability."}]}
{"id":"q_substrate_plan","query":"What does substrate_replay_plan prove and what does it not prove for retrieval?","expected_key":"substrate_replay","candidates":[{"key":"substrate_replay","content":"substrate_replay_plan proves events can become deterministic open-loop pulses consumed by a temporary BioCortex circuit. It does not prove EmbeddingBackend replacement or cosine ranking lift."},{"key":"decision_shadow_only","content":"BioCortex shadow digest runs external examples and parses key value reports while keeping AB dependency graph clean."},{"key":"semantic_bus","content":"Semantic System Bus reports runtime conformance for daemon HTTP and Palace."}]}
{"id":"q_embedding_gate","query":"Why should BioCortex not be added to EmbeddingBackend yet?","expected_key":"embedding_gate","candidates":[{"key":"embedding_gate","content":"Do not add a runtime BioCortex EmbeddingBackend adapter yet. Current evidence supports read-only substrate telemetry, not stable vector shape, cosine ranking, or recall lift."},{"key":"substrate_replay","content":"The BioCortex fixture adapter consumes substrate_replay_plan and reports substrate_replay_consumed and adapter_demonstrated."},{"key":"work_memory","content":"Work memory scratchpads preserve active task state across compaction."}]}
{"id":"q_seed_disposition","query":"What happened to the old Seed bridge in Agent-Bridge?","expected_key":"seed_legacy","candidates":[{"key":"seed_legacy","content":"Seed remains as legacy reference source, but ab-bridge no longer depends on ab-seed-bridge by default. Seed surfaces use a disabled compatibility shim."},{"key":"embedding_gate","content":"A future BioCortex retrieval benchmark must compare baseline ranking against any side signal before runtime retrieval mutation."},{"key":"avatar_protocol","content":"Agent Avatar Protocol projects pet sidecar state into read-only avatar surfaces."}]}
{"id":"q_checkout","query":"Where is the durable biocortex-rs checkout used for fixture replay?","expected_key":"biocortex_checkout","candidates":[{"key":"biocortex_checkout","content":"The durable BioCortex checkout is /Programs/Users/Pallasting/Documents/CascadeProjects/biocortex-rs at HEAD 1f0184dcb299faf54cb639bc5f4c186a5cb3cb57."},{"key":"seed_legacy","content":"crates/seed-bridge remains in tree as legacy source but is excluded from the default workspace."},{"key":"desktop_verify","content":"desktop_verify re-observes AT-SPI and sway state after desktop actions."}]}
{"id":"q_benchmark_next","query":"What is the next safe step if we want BioCortex to influence retrieval later?","expected_key":"retrieval_benchmark","candidates":[{"key":"retrieval_benchmark","content":"Next embedding-related work is a separate retrieval benchmark over fixed memory query corpora. BioCortex stays a side signal until it proves measurable recall or ranking value without retrieval mutation."},{"key":"biocortex_checkout","content":"BioCortex durable checkout validation passed cargo fmt, cargo test, and cargo clippy."},{"key":"mcp_lifecycle","content":"mcp_lifecycle_digest reports profile and tool state independently from runtime health."}]}
"#;

#[derive(Debug, Deserialize, Clone)]
struct CorpusItem {
    id: String,
    query: String,
    expected_key: String,
    candidates: Vec<Candidate>,
}

#[derive(Debug, Deserialize, Clone)]
struct Candidate {
    key: String,
    content: String,
}

#[derive(Debug, Deserialize)]
struct SideSignalRow {
    query_id: String,
    candidate_key: String,
    score: f32,
}

#[derive(Debug)]
struct EvalRow {
    query_id: String,
    expected_key: String,
    baseline_rank: Option<usize>,
    blended_rank: Option<usize>,
    baseline_top: String,
    blended_top: String,
    side_coverage: usize,
    candidate_count: usize,
}

#[derive(Debug)]
struct AlphaConfig {
    policy: String,
    alpha: f32,
    explicit_alpha: bool,
}

#[tokio::main]
async fn main() -> anyhow::Result<()> {
    let corpus = load_corpus()?;
    let side = load_side_signals()?;
    let k = env_usize("BIOCORTEX_RETRIEVAL_K", 3).max(1);
    let alpha = alpha_config()?;
    let backend = default_backend();
    let _ = backend.embed("warm-up probe - biocortex retrieval gate");

    let mut rows = Vec::new();
    for item in &corpus {
        rows.push(eval_item(item, &side, alpha.alpha, backend.as_ref()));
    }
    let summary = summarize(&rows, k, !side.is_empty(), &alpha);
    print_report(&rows, &summary, k, &alpha, backend.name());
    Ok(())
}

fn load_corpus() -> anyhow::Result<Vec<CorpusItem>> {
    let raw = match std::env::var("BIOCORTEX_RETRIEVAL_CORPUS")
        .ok()
        .map(PathBuf::from)
    {
        Some(path) => std::fs::read_to_string(path)?,
        None if PathBuf::from(DEFAULT_CORPUS_PATH).is_file() => {
            std::fs::read_to_string(DEFAULT_CORPUS_PATH)?
        }
        None => DEFAULT_CORPUS.to_string(),
    };
    let items: Vec<CorpusItem> = raw
        .lines()
        .map(str::trim)
        .filter(|line| !line.is_empty())
        .map(|line| serde_json::from_str::<CorpusItem>(line).map_err(anyhow::Error::from))
        .collect::<Result<_, _>>()?;
    anyhow::ensure!(!items.is_empty(), "retrieval corpus is empty");
    for item in &items {
        anyhow::ensure!(
            item.candidates.iter().any(|c| c.key == item.expected_key),
            "expected_key absent from candidates for {}",
            item.id
        );
    }
    Ok(items)
}

fn load_side_signals() -> anyhow::Result<HashMap<(String, String), f32>> {
    let Some(path) = std::env::var("BIOCORTEX_RETRIEVAL_SIDE_SIGNAL")
        .ok()
        .map(PathBuf::from)
    else {
        return Ok(HashMap::new());
    };
    let raw = std::fs::read_to_string(path)?;
    let mut out = HashMap::new();
    for line in raw.lines().map(str::trim).filter(|line| !line.is_empty()) {
        let row: SideSignalRow = serde_json::from_str(line)?;
        anyhow::ensure!(
            (-1.0..=1.0).contains(&row.score),
            "side score out of [-1,1] for {} / {}",
            row.query_id,
            row.candidate_key
        );
        out.insert((row.query_id, row.candidate_key), row.score);
    }
    Ok(out)
}

fn eval_item(
    item: &CorpusItem,
    side: &HashMap<(String, String), f32>,
    alpha: f32,
    backend: &dyn ab_store::embedding::EmbeddingBackend,
) -> EvalRow {
    let query_vec = backend.embed(&item.query);
    let mut scored: Vec<_> = item
        .candidates
        .iter()
        .map(|candidate| {
            let baseline = cosine_similarity(&query_vec, &backend.embed(&candidate.content));
            let side_score = side.get(&(item.id.clone(), candidate.key.clone())).copied();
            let blended = baseline + alpha * side_score.unwrap_or(0.0);
            (
                candidate.key.clone(),
                baseline,
                blended,
                side_score.is_some(),
            )
        })
        .collect();

    scored.sort_by(|a, b| b.1.partial_cmp(&a.1).unwrap_or(std::cmp::Ordering::Equal));
    let baseline_rank = rank_of(&scored, &item.expected_key);
    let baseline_top = top_key(&scored);

    scored.sort_by(|a, b| b.2.partial_cmp(&a.2).unwrap_or(std::cmp::Ordering::Equal));
    let blended_rank = rank_of(&scored, &item.expected_key);
    let blended_top = top_key(&scored);
    let side_coverage = scored.iter().filter(|row| row.3).count();
    let candidate_count = scored.len();

    EvalRow {
        query_id: item.id.clone(),
        expected_key: item.expected_key.clone(),
        baseline_rank,
        blended_rank,
        baseline_top,
        blended_top,
        side_coverage,
        candidate_count,
    }
}

fn rank_of(scored: &[(String, f32, f32, bool)], key: &str) -> Option<usize> {
    scored
        .iter()
        .position(|candidate| candidate.0 == key)
        .map(|idx| idx + 1)
}

fn top_key(scored: &[(String, f32, f32, bool)]) -> String {
    scored
        .first()
        .map(|row| row.0.clone())
        .unwrap_or_else(|| "<none>".to_string())
}

fn summarize(rows: &[EvalRow], k: usize, has_side: bool, alpha: &AlphaConfig) -> serde_json::Value {
    let baseline_mrr = mrr(rows, |row| row.baseline_rank);
    let blended_mrr = mrr(rows, |row| row.blended_rank);
    let regressions = rows
        .iter()
        .filter(|row| match (row.baseline_rank, row.blended_rank) {
            (Some(base), Some(blended)) => blended > base,
            (Some(_), None) => true,
            _ => false,
        })
        .count();
    let coverage = rows.iter().map(|row| row.side_coverage).sum::<usize>() as f64
        / rows
            .iter()
            .map(|row| row.candidate_count)
            .sum::<usize>()
            .max(1) as f64;
    let mrr_delta = blended_mrr - baseline_mrr;
    let pass = has_side && coverage >= 0.80 && regressions == 0 && mrr_delta >= 0.03;

    serde_json::json!({
        "schema": "agent_bridge.biocortex_retrieval_gate_eval.v0",
        "status": if pass { "side_signal_passes_offline_gate" } else if has_side { "side_signal_fails_offline_gate" } else { "baseline_only_no_side_signal" },
        "read_only": true,
        "side_signal_present": has_side,
        "side_signal_coverage": coverage,
        "alpha_policy": alpha.policy.as_str(),
        "blend_alpha": alpha.alpha,
        "explicit_alpha": alpha.explicit_alpha,
        "baseline": {
            "recall_at_1": recall_at(rows, 1, |row| row.baseline_rank),
            "recall_at_k": recall_at(rows, k, |row| row.baseline_rank),
            "mrr": baseline_mrr
        },
        "blended": {
            "recall_at_1": recall_at(rows, 1, |row| row.blended_rank),
            "recall_at_k": recall_at(rows, k, |row| row.blended_rank),
            "mrr": blended_mrr
        },
        "mrr_delta": mrr_delta,
        "regressions": regressions,
        "gate": {
            "runtime_adapter_approved": false,
            "requires_human_review": true,
            "reason": "offline gate only; runtime retrieval mutation remains forbidden"
        }
    })
}

fn recall_at(rows: &[EvalRow], k: usize, get: impl Fn(&EvalRow) -> Option<usize>) -> f64 {
    rows.iter()
        .filter(|row| get(row).map(|rank| rank <= k).unwrap_or(false))
        .count() as f64
        / rows.len().max(1) as f64
}

fn mrr(rows: &[EvalRow], get: impl Fn(&EvalRow) -> Option<usize>) -> f64 {
    rows.iter()
        .map(|row| get(row).map(|rank| 1.0 / rank as f64).unwrap_or(0.0))
        .sum::<f64>()
        / rows.len().max(1) as f64
}

fn print_report(
    rows: &[EvalRow],
    summary: &serde_json::Value,
    k: usize,
    alpha: &AlphaConfig,
    backend: &str,
) {
    println!("# BioCortex Retrieval Gate Eval");
    println!(
        "backend={backend} k={k} alpha_policy={} blend_alpha={:.2}",
        alpha.policy, alpha.alpha
    );
    println!();
    println!(
        "| query | expected | base_rank | blended_rank | base_top | blended_top | side_rows |"
    );
    println!("|---|---|---:|---:|---|---|---:|");
    for row in rows {
        println!(
            "| {} | {} | {} | {} | {} | {} | {} |",
            row.query_id,
            row.expected_key,
            display_rank(row.baseline_rank),
            display_rank(row.blended_rank),
            row.baseline_top,
            row.blended_top,
            format!("{}/{}", row.side_coverage, row.candidate_count)
        );
    }
    println!();
    println!("```json");
    println!(
        "{}",
        serde_json::to_string_pretty(summary).unwrap_or_default()
    );
    println!("```");
}

fn display_rank(rank: Option<usize>) -> String {
    rank.map(|rank| rank.to_string())
        .unwrap_or_else(|| "-".to_string())
}

fn env_usize(key: &str, default: usize) -> usize {
    std::env::var(key)
        .ok()
        .and_then(|value| value.parse().ok())
        .unwrap_or(default)
}

fn alpha_config() -> anyhow::Result<AlphaConfig> {
    if let Ok(raw) = std::env::var("BIOCORTEX_RETRIEVAL_BLEND_ALPHA") {
        let alpha = raw
            .parse::<f32>()
            .map_err(|err| anyhow::anyhow!("parse BIOCORTEX_RETRIEVAL_BLEND_ALPHA: {err}"))?
            .clamp(0.0, 1.0);
        return Ok(AlphaConfig {
            policy: "manual".to_string(),
            alpha,
            explicit_alpha: true,
        });
    }

    let policy = std::env::var("BIOCORTEX_RETRIEVAL_ALPHA_POLICY")
        .unwrap_or_else(|_| "conservative".to_string());
    let normalized = policy.trim().to_ascii_lowercase().replace('_', "-");
    let alpha = match normalized.as_str() {
        "" | "conservative" => CONSERVATIVE_ALPHA,
        "candidate-strong" => CANDIDATE_STRONG_ALPHA,
        other => {
            anyhow::bail!(
                "unknown BIOCORTEX_RETRIEVAL_ALPHA_POLICY {other:?}; expected conservative or candidate-strong"
            )
        }
    };
    Ok(AlphaConfig {
        policy: normalized,
        alpha,
        explicit_alpha: false,
    })
}
