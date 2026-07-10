//! Generate a fixed opaque-id corpus for the SpecFormer memory shadow gate.
//!
//! This is read-only: it opens Agent-Bridge `state.db` with query-only flags,
//! samples active memory rows, and emits JSONL rows that can be checked into a
//! fixture after review. Labels are real relationships:
//! - prefer explicit `related_keys`;
//! - fall back to strongest existing memory graph edge inside the sampled graph.
//!
//! Run:
//!   cargo run -q -p ab-bridge --no-default-features --example specformer_memory_shadow_corpus \
//!     > /tmp/specformer_corpus.jsonl

use ab_store::{default_db_path, MemoryListSort, MemoryRecord, SqliteStore, StateStore};
use anyhow::Context;
use serde::Serialize;
use std::collections::{HashMap, HashSet};
use std::path::PathBuf;

#[path = "specformer_support/opaque_ids.rs"]
mod opaque_ids;

use opaque_ids::{corpus_query, opaque_memory_id, redact_memory_keys};
#[cfg(test)]
use opaque_ids::{is_opaque_memory_id, opaque_ids_in_template, title_of};

const DEFAULT_MAX_NODES: usize = 350;
const DEFAULT_CASE_LIMIT: usize = 36;
const DEFAULT_CANDIDATES: usize = 5;
const DEFAULT_REDACTION_SCAN_LIMIT: usize = 10_000;

#[derive(Debug, Serialize)]
struct CorpusRow {
    query_id: String,
    query_template: String,
    expected_key: String,
    candidate_keys: Vec<String>,
    label_source: String,
}

#[tokio::main(flavor = "current_thread")]
async fn main() -> anyhow::Result<()> {
    let db_path = env_path("AGENT_BRIDGE_DB").unwrap_or_else(default_db_path);
    let max_nodes =
        env_usize("SPECFORMER_SHADOW_CORPUS_MAX_NODES", DEFAULT_MAX_NODES).clamp(16, 500);
    let case_limit = env_usize("SPECFORMER_SHADOW_CORPUS_CASES", DEFAULT_CASE_LIMIT).max(1);
    let candidate_count =
        env_usize("SPECFORMER_SHADOW_CORPUS_CANDIDATES", DEFAULT_CANDIDATES).clamp(3, 12);
    let redaction_scan_limit = env_usize(
        "SPECFORMER_SHADOW_REDACTION_SCAN_LIMIT",
        DEFAULT_REDACTION_SCAN_LIMIT,
    )
    .max(max_nodes);

    let store = SqliteStore::open_read_only(&db_path)
        .await
        .with_context(|| format!("open read-only state db {}", db_path.display()))?;
    let rows = build_corpus(
        &store,
        max_nodes,
        case_limit,
        candidate_count,
        redaction_scan_limit,
    )
    .await?;
    anyhow::ensure!(
        rows.len() >= case_limit.min(5),
        "only generated {} cases",
        rows.len()
    );
    for row in rows {
        println!("{}", serde_json::to_string(&row)?);
    }
    Ok(())
}

async fn build_corpus(
    store: &SqliteStore,
    max_nodes: usize,
    case_limit: usize,
    candidate_count: usize,
    redaction_scan_limit: usize,
) -> anyhow::Result<Vec<CorpusRow>> {
    let skip_kinds = env_list(
        "SPECFORMER_SHADOW_SKIP_KINDS",
        &["skill", "work_memory", "session_handoff", "snapshot"],
    );
    let all_records = store
        .list_memories(
            None,
            MemoryListSort::ByImportance,
            redaction_scan_limit as u32,
        )
        .await
        .context("list memories")?;
    let known_keys = all_records
        .iter()
        .map(|record| record.key.clone())
        .collect::<Vec<_>>();
    let records = all_records
        .into_iter()
        .filter(|record| record.status == "active")
        .filter(|record| !skip_kinds.contains(&record.kind))
        .take(max_nodes)
        .collect::<Vec<_>>();
    let by_key = records
        .iter()
        .map(|record| (record.key.as_str(), record))
        .collect::<HashMap<_, _>>();
    let node_keys = records
        .iter()
        .map(|record| record.key.as_str())
        .collect::<HashSet<_>>();
    let mut out = Vec::new();
    let mut used_expected = HashSet::<String>::new();
    for record in &records {
        let Some((expected_key, label_source)) =
            choose_expected(store, record, &by_key, &node_keys).await?
        else {
            continue;
        };
        if !used_expected.insert(expected_key.clone()) {
            continue;
        }
        let candidate_keys = choose_candidates(
            store,
            record,
            &expected_key,
            &records,
            &by_key,
            &node_keys,
            candidate_count,
        )
        .await?;
        if candidate_keys.len() < candidate_count || !candidate_keys.contains(&expected_key) {
            continue;
        }
        let query_template =
            redact_memory_keys(&corpus_query(&record.key, &record.content), &known_keys);
        anyhow::ensure!(
            known_keys.iter().all(|key| !query_template.contains(key)),
            "query template still contains a listed memory key"
        );
        out.push(CorpusRow {
            query_id: opaque_memory_id(&record.key),
            query_template,
            expected_key: opaque_memory_id(&expected_key),
            candidate_keys: candidate_keys
                .iter()
                .map(|key| opaque_memory_id(key))
                .collect(),
            label_source,
        });
        if out.len() >= case_limit {
            break;
        }
    }
    Ok(out)
}

async fn choose_expected(
    store: &SqliteStore,
    record: &MemoryRecord,
    by_key: &HashMap<&str, &MemoryRecord>,
    node_keys: &HashSet<&str>,
) -> anyhow::Result<Option<(String, String)>> {
    for related in &record.related_keys {
        if related == &record.key {
            continue;
        }
        if by_key
            .get(related.as_str())
            .map(|target| target.status == "active")
            .unwrap_or(false)
        {
            return Ok(Some((related.clone(), "related_keys".to_string())));
        }
    }

    for edge in store
        .memory_neighbors(&record.key)
        .await
        .unwrap_or_default()
    {
        let other = if edge.from_key == record.key {
            edge.to_key
        } else {
            edge.from_key
        };
        if other != record.key && node_keys.contains(other.as_str()) {
            return Ok(Some((other, format!("memory_edge:{}", edge.edge_type))));
        }
    }
    Ok(None)
}

async fn choose_candidates(
    store: &SqliteStore,
    record: &MemoryRecord,
    expected_key: &str,
    records: &[MemoryRecord],
    by_key: &HashMap<&str, &MemoryRecord>,
    node_keys: &HashSet<&str>,
    candidate_count: usize,
) -> anyhow::Result<Vec<String>> {
    let mut out = Vec::<String>::from([expected_key.to_string()]);
    let mut seen = HashSet::<String>::from([record.key.clone(), expected_key.to_string()]);

    for related in &record.related_keys {
        push_candidate(&mut out, &mut seen, related, by_key, candidate_count);
    }
    for edge in store
        .memory_neighbors(&record.key)
        .await
        .unwrap_or_default()
    {
        let other = if edge.from_key == record.key {
            edge.to_key
        } else {
            edge.from_key
        };
        if node_keys.contains(other.as_str()) {
            push_candidate(&mut out, &mut seen, &other, by_key, candidate_count);
        }
    }
    for candidate in records {
        if candidate.kind == record.kind || shares_tag(record, candidate) {
            push_candidate(&mut out, &mut seen, &candidate.key, by_key, candidate_count);
        }
        if out.len() >= candidate_count {
            break;
        }
    }
    for candidate in records {
        push_candidate(&mut out, &mut seen, &candidate.key, by_key, candidate_count);
        if out.len() >= candidate_count {
            break;
        }
    }
    out.sort();
    Ok(out)
}

fn push_candidate(
    out: &mut Vec<String>,
    seen: &mut HashSet<String>,
    key: &str,
    by_key: &HashMap<&str, &MemoryRecord>,
    candidate_count: usize,
) {
    if out.len() >= candidate_count || !seen.insert(key.to_string()) {
        return;
    }
    if by_key
        .get(key)
        .map(|record| record.status == "active")
        .unwrap_or(false)
    {
        out.push(key.to_string());
    }
}

fn shares_tag(left: &MemoryRecord, right: &MemoryRecord) -> bool {
    left.tags.iter().any(|tag| right.tags.contains(tag))
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

fn env_list(key: &str, default: &[&str]) -> HashSet<String> {
    let raw = std::env::var(key).unwrap_or_else(|_| default.join(","));
    raw.split(',')
        .map(str::trim)
        .filter(|value| !value.is_empty())
        .map(ToOwned::to_owned)
        .collect()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn title_of_strips_markdown_marker() {
        assert_eq!(
            title_of("# Useful memory title\nbody"),
            "Useful memory title"
        );
        let id = opaque_memory_id("synthetic-memory-key");
        assert!(is_opaque_memory_id(&id));
        assert_eq!(id, opaque_memory_id("synthetic-memory-key"));
        let template = redact_memory_keys(
            "recall synthetic-memory-key with related-memory-key",
            &[
                "synthetic-memory-key".to_string(),
                "related-memory-key".to_string(),
            ],
        );
        assert_eq!(opaque_ids_in_template(&template).unwrap().len(), 2);
        assert!(!template.contains("synthetic-memory-key"));
    }
}
