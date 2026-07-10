//! SpecFormer memory shadow gate.
//!
//! Read-only offline gate for the side-signal rows emitted by
//! `specformer_memory_shadow`. The corpus stores only typed SHA-256 identifiers;
//! query and candidate contents are resolved in memory from Agent-Bridge
//! `state.db` via `SqliteStore::open_read_only`.
//!
//! Run:
//!   SPECFORMER_SHADOW_FORMAT=jsonl \
//!   SPECFORMER_SHADOW_MAX_NODES=350 \
//!   SPECFORMER_SHADOW_TOP_M=20 \
//!   SPECFORMER_SHADOW_SEEDS="$(jq -r '.query_id' crates/bridge/tests/fixtures/specformer_memory_shadow_gate_corpus.jsonl | paste -sd, -)" \
//!     target/debug/examples/specformer_memory_shadow > /tmp/specformer_side.jsonl
//!
//!   SPECFORMER_SHADOW_SIDE_SIGNAL=/tmp/specformer_side.jsonl \
//!     cargo run -q -p ab-bridge --no-default-features --example specformer_memory_shadow_gate

use ab_store::{
    cosine_similarity, default_db_path, embedding::default_backend, MemoryListSort, MemoryRecord,
    SqliteStore, StateStore,
};
use anyhow::Context;
use serde::Deserialize;
use std::collections::HashMap;
use std::path::PathBuf;

#[path = "specformer_support/opaque_ids.rs"]
mod opaque_ids;

use opaque_ids::{is_opaque_memory_id, opaque_ids_in_template, opaque_memory_id};

const DEFAULT_CORPUS_PATH: &str =
    "crates/bridge/tests/fixtures/specformer_memory_shadow_gate_corpus.jsonl";
const CONSERVATIVE_ALPHA: f32 = 0.20;
const CANDIDATE_STRONG_ALPHA: f32 = 0.80;
const DEFAULT_K: usize = 5;
const DEFAULT_CANDIDATE_K: usize = 20;
const DEFAULT_MIN_CASES: usize = 5;

#[derive(Debug, Deserialize, Clone)]
struct CorpusItem {
    query_id: String,
    #[serde(default)]
    query_literal: Option<String>,
    #[serde(default)]
    query_template: Option<String>,
    expected_key: String,
    candidate_keys: Vec<String>,
}

#[derive(Debug, Deserialize)]
struct SideSignalRow {
    query_id: String,
    candidate_key: String,
    score: f32,
}

#[derive(Debug, Default)]
struct SideSignals {
    scores: HashMap<(String, String), f32>,
    ranks: HashMap<(String, String), usize>,
    top_by_query: HashMap<String, String>,
}

#[derive(Debug, Clone)]
struct Candidate {
    key: String,
    content: String,
}

#[derive(Debug)]
struct ResolvedItem {
    query_id: String,
    query: String,
    expected_key: String,
    candidates: Vec<Candidate>,
}

#[derive(Debug)]
struct EvalRow {
    query_id: String,
    expected_key: String,
    baseline_rank: Option<usize>,
    blended_rank: Option<usize>,
    baseline_top: String,
    blended_top: String,
    side_rank: Option<usize>,
    side_top: String,
    side_coverage: usize,
    candidate_count: usize,
}

#[derive(Debug)]
struct AlphaConfig {
    policy: String,
    alpha: f32,
    explicit_alpha: bool,
}

#[tokio::main(flavor = "current_thread")]
async fn main() -> anyhow::Result<()> {
    let db_path = env_path("AGENT_BRIDGE_DB").unwrap_or_else(default_db_path);
    let store = SqliteStore::open_read_only(&db_path)
        .await
        .with_context(|| format!("open read-only state db {}", db_path.display()))?;
    let corpus = load_corpus()?;
    let items = resolve_items(&store, corpus).await?;
    let side = load_side_signals()?;
    let k = env_usize("SPECFORMER_SHADOW_GATE_K", DEFAULT_K).max(1);
    let candidate_k = env_usize("SPECFORMER_SHADOW_CANDIDATE_K", DEFAULT_CANDIDATE_K).max(1);
    let min_cases = env_usize("SPECFORMER_SHADOW_GATE_MIN_CASES", DEFAULT_MIN_CASES).max(1);
    let alpha = alpha_config()?;

    let backend = default_backend();
    let _ = backend.embed("warm-up probe - specformer memory shadow gate");

    let rows = items
        .iter()
        .map(|item| eval_item(item, &side, alpha.alpha, backend.as_ref()))
        .collect::<Vec<_>>();
    let summary = summarize(
        &rows,
        k,
        candidate_k,
        min_cases,
        !side.scores.is_empty(),
        &alpha,
        &db_path,
    );
    print_report(
        &rows,
        &summary,
        k,
        candidate_k,
        min_cases,
        &alpha,
        backend.name(),
    );
    Ok(())
}

fn load_corpus() -> anyhow::Result<Vec<CorpusItem>> {
    let path = std::env::var("SPECFORMER_SHADOW_GATE_CORPUS")
        .ok()
        .map(PathBuf::from)
        .unwrap_or_else(|| PathBuf::from(DEFAULT_CORPUS_PATH));
    let raw = std::fs::read_to_string(&path).with_context(|| format!("read {}", path.display()))?;
    let items = raw
        .lines()
        .map(str::trim)
        .filter(|line| !line.is_empty())
        .map(|line| serde_json::from_str::<CorpusItem>(line).map_err(anyhow::Error::from))
        .collect::<Result<Vec<_>, _>>()?;
    anyhow::ensure!(!items.is_empty(), "specformer gate corpus is empty");
    for item in &items {
        anyhow::ensure!(
            is_opaque_memory_id(&item.query_id),
            "query_id must use the abmkey:sha256 opaque-id contract"
        );
        anyhow::ensure!(
            is_opaque_memory_id(&item.expected_key),
            "expected_key must use the abmkey:sha256 opaque-id contract"
        );
        anyhow::ensure!(
            item.candidate_keys.iter().all(|id| is_opaque_memory_id(id)),
            "candidate_keys must use the abmkey:sha256 opaque-id contract"
        );
        anyhow::ensure!(
            matches!(
                (&item.query_literal, &item.query_template),
                (Some(_), None) | (None, Some(_))
            ),
            "corpus row must contain exactly one of query_literal or query_template"
        );
        if let Some(template) = &item.query_template {
            anyhow::ensure!(
                !opaque_ids_in_template(template)?.is_empty(),
                "query_template must contain at least one opaque id token"
            );
        }
        anyhow::ensure!(
            item.candidate_keys
                .iter()
                .any(|key| key == &item.expected_key),
            "expected_key absent from candidate_keys for {}",
            item.query_id
        );
        anyhow::ensure!(
            item.candidate_keys.len() >= 3,
            "need at least 3 candidate_keys for {}",
            item.query_id
        );
    }
    Ok(items)
}

async fn resolve_items(
    store: &SqliteStore,
    items: Vec<CorpusItem>,
) -> anyhow::Result<Vec<ResolvedItem>> {
    let mut needed = std::collections::HashSet::new();
    for item in &items {
        needed.insert(item.query_id.clone());
        needed.extend(item.candidate_keys.iter().cloned());
        if let Some(template) = &item.query_template {
            needed.extend(opaque_ids_in_template(template)?);
        }
    }
    let fetch_limit = env_usize("SPECFORMER_SHADOW_GATE_FETCH_LIMIT", 10_000).max(needed.len());
    let records = store
        .list_memories(None, MemoryListSort::ByImportance, fetch_limit as u32)
        .await
        .context("list memories for opaque-id gate corpus")?;
    let mut by_id = HashMap::new();
    for record in records {
        let id = opaque_memory_id(&record.key);
        if needed.contains(&id) {
            anyhow::ensure!(
                by_id.insert(id.clone(), record).is_none(),
                "opaque memory id collision: {id}"
            );
        }
    }
    for id in &needed {
        anyhow::ensure!(
            by_id.contains_key(id),
            "opaque memory id not found in listed state.db snapshot: {id}"
        );
    }

    let mut resolved = Vec::with_capacity(items.len());
    for item in items {
        let query_record = by_id
            .get(&item.query_id)
            .context("query opaque id not found after resolution")?;
        anyhow::ensure!(
            query_record.status == "active",
            "query memory is not active for {} status={}",
            item.query_id,
            query_record.status
        );
        let query = resolve_query(&item, &by_id)?;
        let mut candidates = Vec::with_capacity(item.candidate_keys.len());
        for id in &item.candidate_keys {
            let record = by_id
                .get(id)
                .context("candidate opaque id not found after resolution")?;
            anyhow::ensure!(
                record.status == "active",
                "candidate key is not active: {} status={}",
                id,
                record.status
            );
            candidates.push(candidate_from_record(id, record));
        }
        resolved.push(ResolvedItem {
            query_id: item.query_id,
            query,
            expected_key: item.expected_key,
            candidates,
        });
    }
    Ok(resolved)
}

fn resolve_query(
    item: &CorpusItem,
    records: &HashMap<String, MemoryRecord>,
) -> anyhow::Result<String> {
    if let Some(query) = &item.query_literal {
        return Ok(query.clone());
    }
    let template = item
        .query_template
        .as_ref()
        .context("query template missing after corpus validation")?;
    let mut query = template.clone();
    for id in opaque_ids_in_template(template)? {
        let record = records
            .get(&id)
            .context("query-template opaque id not found after resolution")?;
        let token = format!("{{{{{id}}}}}");
        query = query.replace(&token, &record.key);
    }
    Ok(query)
}

fn candidate_from_record(id: &str, record: &MemoryRecord) -> Candidate {
    Candidate {
        key: id.to_string(),
        content: record.content.clone(),
    }
}

fn load_side_signals() -> anyhow::Result<SideSignals> {
    let Some(path) = std::env::var("SPECFORMER_SHADOW_SIDE_SIGNAL")
        .ok()
        .map(PathBuf::from)
    else {
        return Ok(SideSignals::default());
    };
    let raw = std::fs::read_to_string(&path).with_context(|| format!("read {}", path.display()))?;
    let mut grouped: HashMap<String, Vec<(String, f32)>> = HashMap::new();
    for line in raw.lines().map(str::trim).filter(|line| !line.is_empty()) {
        let row: SideSignalRow = serde_json::from_str(line)?;
        anyhow::ensure!(
            is_opaque_memory_id(&row.query_id) && is_opaque_memory_id(&row.candidate_key),
            "side-signal ids must use the abmkey:sha256 opaque-id contract"
        );
        anyhow::ensure!(
            (-1.0..=1.0).contains(&row.score),
            "side score out of [-1,1] for {} / {}",
            row.query_id,
            row.candidate_key
        );
        grouped
            .entry(row.query_id)
            .or_default()
            .push((row.candidate_key, row.score));
    }
    let mut signals = SideSignals::default();
    for (query_id, mut rows) in grouped {
        // Stable sort keeps the frozen raw-key tie order without serializing raw keys.
        rows.sort_by(|left, right| {
            right
                .1
                .partial_cmp(&left.1)
                .unwrap_or(std::cmp::Ordering::Equal)
        });
        if let Some((top_key, _)) = rows.first() {
            signals
                .top_by_query
                .insert(query_id.clone(), top_key.clone());
        }
        for (idx, (candidate_key, score)) in rows.into_iter().enumerate() {
            signals
                .scores
                .insert((query_id.clone(), candidate_key.clone()), score);
            signals
                .ranks
                .insert((query_id.clone(), candidate_key), idx + 1);
        }
    }
    Ok(signals)
}

fn eval_item(
    item: &ResolvedItem,
    side: &SideSignals,
    alpha: f32,
    backend: &dyn ab_store::embedding::EmbeddingBackend,
) -> EvalRow {
    let query_vec = backend.embed(&item.query);
    let mut scored = item
        .candidates
        .iter()
        .map(|candidate| {
            let baseline = cosine_similarity(&query_vec, &backend.embed(&candidate.content));
            let side_score = side
                .scores
                .get(&(item.query_id.clone(), candidate.key.clone()))
                .copied();
            let blended = baseline + alpha * side_score.unwrap_or(0.0);
            (
                candidate.key.clone(),
                baseline,
                blended,
                side_score.is_some(),
            )
        })
        .collect::<Vec<_>>();

    scored.sort_by(|a, b| b.1.partial_cmp(&a.1).unwrap_or(std::cmp::Ordering::Equal));
    let baseline_rank = rank_of(&scored, &item.expected_key);
    let baseline_top = top_key(&scored);

    scored.sort_by(|a, b| b.2.partial_cmp(&a.2).unwrap_or(std::cmp::Ordering::Equal));
    let blended_rank = rank_of(&scored, &item.expected_key);
    let blended_top = top_key(&scored);
    let side_coverage = scored.iter().filter(|row| row.3).count();
    let candidate_count = scored.len();
    let side_rank = side
        .ranks
        .get(&(item.query_id.clone(), item.expected_key.clone()))
        .copied();
    let side_top = side
        .top_by_query
        .get(&item.query_id)
        .cloned()
        .unwrap_or_else(|| "<none>".to_string());

    EvalRow {
        query_id: item.query_id.clone(),
        expected_key: item.expected_key.clone(),
        baseline_rank,
        blended_rank,
        baseline_top,
        blended_top,
        side_rank,
        side_top,
        side_coverage,
        candidate_count,
    }
}

fn summarize(
    rows: &[EvalRow],
    k: usize,
    candidate_k: usize,
    min_cases: usize,
    has_side: bool,
    alpha: &AlphaConfig,
    db_path: &PathBuf,
) -> serde_json::Value {
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
    let pass = has_side
        && rows.len() >= min_cases
        && coverage >= 0.80
        && regressions == 0
        && mrr_delta >= 0.03;
    let candidate_recall = recall_at(rows, candidate_k, |row| row.side_rank);
    let candidate_mrr = mrr(rows, |row| row.side_rank);
    let candidate_generation_pass = has_side && rows.len() >= min_cases && candidate_recall >= 0.80;

    serde_json::json!({
        "schema": "agent_bridge.specformer_memory_shadow_gate.v0",
        "status": if pass { "side_signal_passes_starter_gate" } else if has_side { "side_signal_fails_starter_gate" } else { "baseline_only_no_side_signal" },
        "checkpoint_decision": "no_go",
        "read_only": true,
        "db_path": db_path.display().to_string(),
        "side_signal_present": has_side,
        "side_signal_coverage": coverage,
        "case_count": rows.len(),
        "min_cases": min_cases,
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
        "candidate_generation": {
            "status": if candidate_generation_pass { "passes_candidate_generation_starter_gate" } else if has_side { "fails_candidate_generation_starter_gate" } else { "baseline_only_no_side_signal" },
            "candidate_k": candidate_k,
            "recall_at_candidate_k": candidate_recall,
            "mrr": candidate_mrr
        },
        "gate": {
            "runtime_adapter_approved": false,
            "default_search_order_changed": false,
            "requires_fixed_corpus_expansion_before_runtime_review": false,
            "reason": "offline checkpoint only; the completed 36-case and two-stage evaluations authorize no runtime influence"
        }
    })
}

fn print_report(
    rows: &[EvalRow],
    summary: &serde_json::Value,
    k: usize,
    candidate_k: usize,
    min_cases: usize,
    alpha: &AlphaConfig,
    backend: &str,
) {
    println!("# SpecFormer Memory Shadow Gate");
    println!(
        "backend={backend} k={k} candidate_k={candidate_k} min_cases={min_cases} alpha_policy={} blend_alpha={:.2}",
        alpha.policy, alpha.alpha
    );
    println!();
    println!(
        "| query_id | expected | base_rank | blended_rank | side_rank | base_top | blended_top | side_top | side_rows |"
    );
    println!("|---|---|---:|---:|---:|---|---|---|---:|");
    for row in rows {
        println!(
            "| {} | {} | {} | {} | {} | {} | {} | {} | {}/{} |",
            row.query_id,
            row.expected_key,
            display_rank(row.baseline_rank),
            display_rank(row.blended_rank),
            display_rank(row.side_rank),
            row.baseline_top,
            row.blended_top,
            row.side_top,
            row.side_coverage,
            row.candidate_count
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

fn display_rank(rank: Option<usize>) -> String {
    rank.map(|rank| rank.to_string())
        .unwrap_or_else(|| "-".to_string())
}

fn alpha_config() -> anyhow::Result<AlphaConfig> {
    if let Ok(raw) = std::env::var("SPECFORMER_SHADOW_BLEND_ALPHA") {
        let alpha = raw
            .parse::<f32>()
            .map_err(|err| anyhow::anyhow!("parse SPECFORMER_SHADOW_BLEND_ALPHA: {err}"))?
            .clamp(0.0, 1.0);
        return Ok(AlphaConfig {
            policy: "manual".to_string(),
            alpha,
            explicit_alpha: true,
        });
    }

    let policy =
        std::env::var("SPECFORMER_SHADOW_ALPHA_POLICY").unwrap_or_else(|_| "conservative".into());
    let normalized = policy.trim().to_ascii_lowercase().replace('_', "-");
    let alpha = match normalized.as_str() {
        "" | "conservative" => CONSERVATIVE_ALPHA,
        "candidate-strong" => CANDIDATE_STRONG_ALPHA,
        other => anyhow::bail!(
            "unknown SPECFORMER_SHADOW_ALPHA_POLICY {other:?}; expected conservative or candidate-strong"
        ),
    };
    Ok(AlphaConfig {
        policy: normalized,
        alpha,
        explicit_alpha: false,
    })
}

fn env_path(key: &str) -> Option<PathBuf> {
    std::env::var_os(key).map(PathBuf::from)
}

fn env_usize(key: &str, default: usize) -> usize {
    std::env::var(key)
        .ok()
        .and_then(|value| value.parse().ok())
        .unwrap_or(default)
}

#[cfg(test)]
mod tests {
    use super::*;

    fn row(base: usize, blended: usize) -> EvalRow {
        EvalRow {
            query_id: "q".to_string(),
            expected_key: "e".to_string(),
            baseline_rank: Some(base),
            blended_rank: Some(blended),
            baseline_top: "b".to_string(),
            blended_top: "c".to_string(),
            side_rank: Some(blended),
            side_top: "c".to_string(),
            side_coverage: 1,
            candidate_count: 1,
        }
    }

    #[test]
    fn mrr_improves_when_rank_moves_up() {
        let rows = vec![row(3, 1), row(1, 1)];
        assert!(mrr(&rows, |r| r.blended_rank) > mrr(&rows, |r| r.baseline_rank));
    }

    #[test]
    fn alpha_policy_accepts_candidate_strong() {
        std::env::set_var("SPECFORMER_SHADOW_ALPHA_POLICY", "candidate_strong");
        std::env::remove_var("SPECFORMER_SHADOW_BLEND_ALPHA");
        let alpha = alpha_config().expect("alpha");
        assert_eq!(alpha.policy, "candidate-strong");
        assert!((alpha.alpha - 0.80).abs() < f32::EPSILON);
        std::env::remove_var("SPECFORMER_SHADOW_ALPHA_POLICY");
    }

    #[test]
    fn side_signal_loader_ranks_by_score_desc() {
        let dir = tempfile::tempdir().expect("tempdir");
        let path = dir.path().join("side.jsonl");
        let query_id = opaque_memory_id("synthetic-query");
        let candidate_a = opaque_memory_id("synthetic-candidate-a");
        let candidate_b = opaque_memory_id("synthetic-candidate-b");
        let candidate_c = opaque_memory_id("synthetic-candidate-c");
        let raw = format!(
            "{{\"query_id\":\"{query_id}\",\"candidate_key\":\"{candidate_b}\",\"score\":0.5}}\n\
             {{\"query_id\":\"{query_id}\",\"candidate_key\":\"{candidate_a}\",\"score\":0.8}}\n\
             {{\"query_id\":\"{query_id}\",\"candidate_key\":\"{candidate_c}\",\"score\":0.5}}\n"
        );
        std::fs::write(&path, raw).expect("write opaque side signal");
        std::env::set_var("SPECFORMER_SHADOW_SIDE_SIGNAL", &path);
        let signals = load_side_signals().expect("load side signal");
        assert_eq!(
            signals.top_by_query.get(&query_id).map(String::as_str),
            Some(candidate_a.as_str())
        );
        assert_eq!(
            signals.ranks.get(&(query_id.clone(), candidate_a)).copied(),
            Some(1)
        );
        assert_eq!(
            signals.ranks.get(&(query_id.clone(), candidate_b)).copied(),
            Some(2)
        );
        assert_eq!(
            signals.ranks.get(&(query_id, candidate_c)).copied(),
            Some(3)
        );
        std::env::remove_var("SPECFORMER_SHADOW_SIDE_SIGNAL");
    }
}
