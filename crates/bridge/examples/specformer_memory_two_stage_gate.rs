//! Two-stage gate for SpecFormer memory shadow candidates.
//!
//! This is read-only. Stage 1 consumes JSONL side-signal rows emitted by
//! `specformer_memory_shadow` as a graph candidate-expansion pool. Stage 2
//! reranks those candidates with the active embedding backend. It does not blend
//! spectral scores into ranking and does not mutate runtime retrieval.
//!
//! With no environment variables, it uses the fixed 36-case corpus plus the
//! frozen `related-only` top-50 side-signal fixture.
//!
//! Run:
//!   CORPUS=crates/bridge/tests/fixtures/specformer_memory_shadow_gate_graph_label_corpus.jsonl
//!   SEEDS="$(jq -r '.query_id' "$CORPUS" | paste -sd, -)"
//!   SPECFORMER_SHADOW_GRAPH_MODE=related-only \
//!   SPECFORMER_SHADOW_FORMAT=jsonl \
//!   SPECFORMER_SHADOW_MAX_NODES=350 \
//!   SPECFORMER_SHADOW_TOP_M=50 \
//!   SPECFORMER_SHADOW_SEEDS="$SEEDS" \
//!     target/debug/examples/specformer_memory_shadow > /tmp/specformer_related_top50.jsonl
//!
//!   SPECFORMER_TWO_STAGE_CORPUS="$CORPUS" \
//!   SPECFORMER_TWO_STAGE_SIDE_SIGNAL=/tmp/specformer_related_top50.jsonl \
//!     cargo run -q -p ab-bridge --no-default-features --example specformer_memory_two_stage_gate

use ab_store::{
    cosine_similarity, default_db_path, embedding::default_backend, embedding::EmbeddingBackend,
    MemoryListSort, MemoryRecord, SqliteStore, StateStore,
};
use anyhow::Context;
use serde::Deserialize;
use std::collections::{HashMap, HashSet};
use std::path::PathBuf;

#[path = "specformer_support/opaque_ids.rs"]
mod opaque_ids;

use opaque_ids::{is_opaque_memory_id, opaque_ids_in_template, opaque_memory_id};

const DEFAULT_CORPUS_PATH: &str =
    "crates/bridge/tests/fixtures/specformer_memory_shadow_gate_graph_label_corpus.jsonl";
const DEFAULT_SIDE_SIGNAL_PATH: &str =
    "crates/bridge/tests/fixtures/specformer_memory_shadow_related_only_top50_side_signal.jsonl";
const DEFAULT_CANDIDATE_K: usize = 50;
const DEFAULT_RERANK_K: usize = 5;
const DEFAULT_MIN_CASES: usize = 30;
const DEFAULT_MIN_GRAPH_RECALL: f64 = 0.80;
const DEFAULT_MIN_RERANK_RECALL: f64 = 0.50;
const DEFAULT_MAX_UNION_REGRESSIONS: usize = 0;

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
    by_query: HashMap<String, Vec<(String, f32)>>,
    ranks: HashMap<(String, String), usize>,
}

#[derive(Debug, Clone)]
struct Candidate {
    key: String,
    raw_sort_key: String,
    content: String,
}

#[derive(Debug)]
struct EvalRow {
    query_id: String,
    expected_key: String,
    graph_rank: Option<usize>,
    fixed_rank: Option<usize>,
    expansion_rank: Option<usize>,
    union_rank: Option<usize>,
    fixed_top: String,
    expansion_top: String,
    union_top: String,
    expansion_count: usize,
    union_count: usize,
}

#[tokio::main(flavor = "current_thread")]
async fn main() -> anyhow::Result<()> {
    let db_path = env_path("AGENT_BRIDGE_DB").unwrap_or_else(default_db_path);
    let corpus = load_corpus()?;
    let side = load_side_signals()?;
    anyhow::ensure!(
        !side.by_query.is_empty(),
        "two-stage side-signal input is empty"
    );

    let candidate_k = env_usize_alias(
        "SPECFORMER_TWO_STAGE_CANDIDATE_K",
        "SPECFORMER_SHADOW_CANDIDATE_K",
        DEFAULT_CANDIDATE_K,
    )
    .max(1);
    let rerank_k = env_usize("SPECFORMER_TWO_STAGE_RERANK_K", DEFAULT_RERANK_K).max(1);
    let min_cases = env_usize("SPECFORMER_TWO_STAGE_MIN_CASES", DEFAULT_MIN_CASES).max(1);
    let min_graph_recall = env_f64(
        "SPECFORMER_TWO_STAGE_MIN_GRAPH_RECALL",
        DEFAULT_MIN_GRAPH_RECALL,
    )
    .clamp(0.0, 1.0);
    let min_rerank_recall = env_f64(
        "SPECFORMER_TWO_STAGE_MIN_RERANK_RECALL",
        DEFAULT_MIN_RERANK_RECALL,
    )
    .clamp(0.0, 1.0);
    let max_union_regressions = env_usize(
        "SPECFORMER_TWO_STAGE_MAX_UNION_REGRESSIONS",
        DEFAULT_MAX_UNION_REGRESSIONS,
    );

    let store = SqliteStore::open_read_only(&db_path)
        .await
        .with_context(|| format!("open read-only state db {}", db_path.display()))?;
    let records = load_needed_records(&store, &corpus, &side, candidate_k).await?;
    let backend = default_backend();
    let _ = backend.embed("warm-up probe - specformer memory two-stage gate");

    let rows = corpus
        .iter()
        .map(|item| eval_item(item, &side, candidate_k, &records, backend.as_ref()))
        .collect::<anyhow::Result<Vec<_>>>()?;
    let summary = summarize(
        &rows,
        candidate_k,
        rerank_k,
        min_cases,
        min_graph_recall,
        min_rerank_recall,
        max_union_regressions,
        &db_path,
    );
    print_report(&rows, &summary, candidate_k, rerank_k, backend.name());
    Ok(())
}

fn load_corpus() -> anyhow::Result<Vec<CorpusItem>> {
    let path = env_path_alias(
        "SPECFORMER_TWO_STAGE_CORPUS",
        "SPECFORMER_SHADOW_GATE_CORPUS",
    )
    .unwrap_or_else(|| PathBuf::from(DEFAULT_CORPUS_PATH));
    let raw = std::fs::read_to_string(&path).with_context(|| format!("read {}", path.display()))?;
    let items = raw
        .lines()
        .map(str::trim)
        .filter(|line| !line.is_empty())
        .map(|line| serde_json::from_str::<CorpusItem>(line).map_err(anyhow::Error::from))
        .collect::<Result<Vec<_>, _>>()?;
    anyhow::ensure!(!items.is_empty(), "two-stage corpus is empty");
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
            "expected_key absent from fixed candidate_keys for {}",
            item.query_id
        );
    }
    Ok(items)
}

fn load_side_signals() -> anyhow::Result<SideSignals> {
    let path = env_path_alias(
        "SPECFORMER_TWO_STAGE_SIDE_SIGNAL",
        "SPECFORMER_SHADOW_SIDE_SIGNAL",
    )
    .unwrap_or_else(|| PathBuf::from(DEFAULT_SIDE_SIGNAL_PATH));
    let raw = std::fs::read_to_string(&path).with_context(|| format!("read {}", path.display()))?;
    let mut by_query: HashMap<String, Vec<(String, f32)>> = HashMap::new();
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
        by_query
            .entry(row.query_id)
            .or_default()
            .push((row.candidate_key, row.score));
    }

    let mut signals = SideSignals::default();
    for (query_id, mut rows) in by_query {
        // Stable sort keeps the frozen raw-key tie order without serializing raw keys.
        rows.sort_by(|left, right| {
            right
                .1
                .partial_cmp(&left.1)
                .unwrap_or(std::cmp::Ordering::Equal)
        });
        rows.dedup_by(|left, right| left.0 == right.0);
        for (idx, (candidate_key, _)) in rows.iter().enumerate() {
            signals
                .ranks
                .insert((query_id.clone(), candidate_key.clone()), idx + 1);
        }
        signals.by_query.insert(query_id, rows);
    }
    Ok(signals)
}

async fn load_needed_records(
    store: &SqliteStore,
    corpus: &[CorpusItem],
    side: &SideSignals,
    candidate_k: usize,
) -> anyhow::Result<HashMap<String, MemoryRecord>> {
    let mut needed = HashSet::<String>::new();
    for item in corpus {
        needed.insert(item.query_id.clone());
        needed.extend(item.candidate_keys.iter().cloned());
        needed.extend(top_side_keys(side, &item.query_id, candidate_k));
        if let Some(template) = &item.query_template {
            needed.extend(opaque_ids_in_template(template)?);
        }
    }
    let fetch_limit = env_usize("SPECFORMER_TWO_STAGE_FETCH_LIMIT", 10_000).max(needed.len());
    let records = store
        .list_memories(None, MemoryListSort::ByImportance, fetch_limit as u32)
        .await
        .context("list memories for two-stage gate")?;
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
    Ok(by_id)
}

fn eval_item(
    item: &CorpusItem,
    side: &SideSignals,
    candidate_k: usize,
    records: &HashMap<String, MemoryRecord>,
    backend: &dyn EmbeddingBackend,
) -> anyhow::Result<EvalRow> {
    let query_record = records
        .get(&item.query_id)
        .context("query opaque id not found after resolution")?;
    anyhow::ensure!(
        query_record.status == "active",
        "query memory is not active for {} status={}",
        item.query_id,
        query_record.status
    );
    let query = resolve_query(item, records)?;
    let fixed_keys = dedup_preserve_order(item.candidate_keys.iter().cloned());
    let expansion_keys = top_side_keys(side, &item.query_id, candidate_k);
    let union_keys = dedup_preserve_order(fixed_keys.iter().chain(expansion_keys.iter()).cloned());

    let fixed = candidates_for(&fixed_keys, records)?;
    let expansion = candidates_for(&expansion_keys, records)?;
    let union = candidates_for(&union_keys, records)?;

    let fixed_ranking = semantic_ranking(&query, &fixed, backend);
    let expansion_ranking = semantic_ranking(&query, &expansion, backend);
    let union_ranking = semantic_ranking(&query, &union, backend);

    Ok(EvalRow {
        query_id: item.query_id.clone(),
        expected_key: item.expected_key.clone(),
        graph_rank: side
            .ranks
            .get(&(item.query_id.clone(), item.expected_key.clone()))
            .copied(),
        fixed_rank: rank_of(&fixed_ranking, &item.expected_key),
        expansion_rank: rank_of(&expansion_ranking, &item.expected_key),
        union_rank: rank_of(&union_ranking, &item.expected_key),
        fixed_top: top_key(&fixed_ranking),
        expansion_top: top_key(&expansion_ranking),
        union_top: top_key(&union_ranking),
        expansion_count: expansion.len(),
        union_count: union.len(),
    })
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

fn candidates_for(
    keys: &[String],
    records: &HashMap<String, MemoryRecord>,
) -> anyhow::Result<Vec<Candidate>> {
    keys.iter()
        .map(|key| {
            let record = records
                .get(key)
                .context("candidate opaque id missing after load")?;
            anyhow::ensure!(
                record.status == "active",
                "candidate key is not active: {} status={}",
                key,
                record.status
            );
            Ok(Candidate {
                key: key.clone(),
                raw_sort_key: record.key.clone(),
                content: record.content.clone(),
            })
        })
        .collect()
}

fn semantic_ranking(
    query: &str,
    candidates: &[Candidate],
    backend: &dyn EmbeddingBackend,
) -> Vec<(String, f32)> {
    let query_vec = backend.embed(query);
    let mut ranked = candidates
        .iter()
        .map(|candidate| {
            (
                candidate,
                cosine_similarity(&query_vec, &backend.embed(&candidate.content)),
            )
        })
        .collect::<Vec<_>>();
    ranked.sort_by(|left, right| {
        right
            .1
            .partial_cmp(&left.1)
            .unwrap_or(std::cmp::Ordering::Equal)
            .then_with(|| left.0.raw_sort_key.cmp(&right.0.raw_sort_key))
    });
    ranked
        .into_iter()
        .map(|(candidate, score)| (candidate.key.clone(), score))
        .collect()
}

fn summarize(
    rows: &[EvalRow],
    candidate_k: usize,
    rerank_k: usize,
    min_cases: usize,
    min_graph_recall: f64,
    min_rerank_recall: f64,
    max_union_regressions: usize,
    db_path: &PathBuf,
) -> serde_json::Value {
    let graph_recall = recall_at(rows, candidate_k, |row| row.graph_rank);
    let expansion_rerank_recall = recall_at(rows, rerank_k, |row| row.expansion_rank);
    let union_regressions = union_regressions(rows);
    let pass = rows.len() >= min_cases
        && graph_recall >= min_graph_recall
        && expansion_rerank_recall >= min_rerank_recall
        && union_regressions <= max_union_regressions;

    serde_json::json!({
        "schema": "agent_bridge.specformer_memory_two_stage_gate.v0",
        "status": if pass { "two_stage_passes_shadow_gate" } else { "two_stage_fails_shadow_gate" },
        "checkpoint_decision": "no_go",
        "read_only": true,
        "db_path": db_path.display().to_string(),
        "runtime_adapter_approved": false,
        "default_search_order_changed": false,
        "case_count": rows.len(),
        "min_cases": min_cases,
        "candidate_k": candidate_k,
        "rerank_k": rerank_k,
        "thresholds": {
            "min_graph_recall": min_graph_recall,
            "min_rerank_recall": min_rerank_recall,
            "max_union_regressions": max_union_regressions
        },
        "fixed_semantic": {
            "recall_at_1": recall_at(rows, 1, |row| row.fixed_rank),
            "recall_at_rerank_k": recall_at(rows, rerank_k, |row| row.fixed_rank),
            "mrr": mrr(rows, |row| row.fixed_rank)
        },
        "graph_candidate_stage": {
            "recall_at_candidate_k": graph_recall,
            "mrr": mrr(rows, |row| row.graph_rank),
            "missing_expected_at_candidate_k": rows
                .iter()
                .filter(|row| row.graph_rank.map(|rank| rank > candidate_k).unwrap_or(true))
                .count()
        },
        "expansion_semantic_rerank": {
            "recall_at_1": recall_at(rows, 1, |row| row.expansion_rank),
            "recall_at_rerank_k": expansion_rerank_recall,
            "mrr": mrr(rows, |row| row.expansion_rank)
        },
        "union_semantic_rerank": {
            "recall_at_1": recall_at(rows, 1, |row| row.union_rank),
            "recall_at_rerank_k": recall_at(rows, rerank_k, |row| row.union_rank),
            "mrr": mrr(rows, |row| row.union_rank),
            "regressions_vs_fixed": union_regressions
        },
        "gate": {
            "reason": "frozen offline checkpoint only; this two-stage shape is rejected and authorizes no runtime influence"
        }
    })
}

fn print_report(
    rows: &[EvalRow],
    summary: &serde_json::Value,
    candidate_k: usize,
    rerank_k: usize,
    backend: &str,
) {
    println!("# SpecFormer Memory Two-Stage Gate");
    println!("backend={backend} candidate_k={candidate_k} rerank_k={rerank_k}");
    println!();
    println!(
        "| query_id | expected | graph_rank | fixed_rank | expansion_rank | union_rank | fixed_top | expansion_top | union_top | sizes |"
    );
    println!("|---|---|---:|---:|---:|---:|---|---|---|---:|");
    for row in rows {
        println!(
            "| {} | {} | {} | {} | {} | {} | {} | {} | {} | {}/{} |",
            row.query_id,
            row.expected_key,
            display_rank(row.graph_rank),
            display_rank(row.fixed_rank),
            display_rank(row.expansion_rank),
            display_rank(row.union_rank),
            row.fixed_top,
            row.expansion_top,
            row.union_top,
            row.expansion_count,
            row.union_count
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

fn top_side_keys(side: &SideSignals, query_id: &str, candidate_k: usize) -> Vec<String> {
    side.by_query
        .get(query_id)
        .map(|rows| {
            rows.iter()
                .take(candidate_k)
                .map(|(key, _)| key.clone())
                .collect::<Vec<_>>()
        })
        .unwrap_or_default()
}

fn dedup_preserve_order(keys: impl IntoIterator<Item = String>) -> Vec<String> {
    let mut seen = HashSet::new();
    let mut out = Vec::new();
    for key in keys {
        if seen.insert(key.clone()) {
            out.push(key);
        }
    }
    out
}

fn rank_of(ranked: &[(String, f32)], key: &str) -> Option<usize> {
    ranked
        .iter()
        .position(|candidate| candidate.0 == key)
        .map(|idx| idx + 1)
}

fn top_key(ranked: &[(String, f32)]) -> String {
    ranked
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

fn union_regressions(rows: &[EvalRow]) -> usize {
    rows.iter()
        .filter(|row| match (row.fixed_rank, row.union_rank) {
            (Some(fixed), Some(union)) => union > fixed,
            (Some(_), None) => true,
            _ => false,
        })
        .count()
}

fn display_rank(rank: Option<usize>) -> String {
    rank.map(|value| value.to_string())
        .unwrap_or_else(|| "-".to_string())
}

fn env_path(key: &str) -> Option<PathBuf> {
    std::env::var_os(key).map(PathBuf::from)
}

fn env_path_alias(primary: &str, fallback: &str) -> Option<PathBuf> {
    env_path(primary).or_else(|| env_path(fallback))
}

fn env_usize(key: &str, default: usize) -> usize {
    std::env::var(key)
        .ok()
        .and_then(|value| value.parse().ok())
        .unwrap_or(default)
}

fn env_usize_alias(primary: &str, fallback: &str, default: usize) -> usize {
    std::env::var(primary)
        .ok()
        .or_else(|| std::env::var(fallback).ok())
        .and_then(|value| value.parse().ok())
        .unwrap_or(default)
}

fn env_f64(key: &str, default: f64) -> f64 {
    std::env::var(key)
        .ok()
        .and_then(|value| value.parse().ok())
        .unwrap_or(default)
}

#[cfg(test)]
mod tests {
    use super::*;

    fn row(graph: Option<usize>, fixed: Option<usize>, union: Option<usize>) -> EvalRow {
        EvalRow {
            query_id: "q".to_string(),
            expected_key: "e".to_string(),
            graph_rank: graph,
            fixed_rank: fixed,
            expansion_rank: None,
            union_rank: union,
            fixed_top: "a".to_string(),
            expansion_top: "b".to_string(),
            union_top: "c".to_string(),
            expansion_count: 0,
            union_count: 0,
        }
    }

    #[test]
    fn dedup_preserves_first_seen_order() {
        let keys = ["a", "b", "a", "c", "b"].into_iter().map(ToOwned::to_owned);
        assert_eq!(dedup_preserve_order(keys), vec!["a", "b", "c"]);
    }

    #[test]
    fn rank_of_is_one_based() {
        let ranked = vec![("a".to_string(), 1.0), ("b".to_string(), 0.5)];
        assert_eq!(rank_of(&ranked, "b"), Some(2));
        assert_eq!(rank_of(&ranked, "c"), None);
    }

    #[test]
    fn recall_at_treats_missing_as_miss() {
        let rows = vec![row(Some(1), None, None), row(None, None, None)];
        assert_eq!(recall_at(&rows, 1, |row| row.graph_rank), 0.5);
    }

    #[test]
    fn union_regression_counts_rank_drop_and_missing() {
        let rows = vec![
            row(None, Some(1), Some(2)),
            row(None, Some(2), Some(1)),
            row(None, Some(3), None),
        ];
        assert_eq!(union_regressions(&rows), 2);
    }
}
