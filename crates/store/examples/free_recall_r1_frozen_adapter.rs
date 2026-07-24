//! Evaluation-only frozen-clock adapter for the R1 free-recall replay.
//!
//! This is deliberately a store example, not an MCP tool or runtime switch.
//! It opens only a caller-selected disposable SQLite clone in query-only mode.

use ab_store::{SqliteStore, StateStore};
use serde::Deserialize;
use std::path::Path;

#[derive(Debug, Deserialize)]
#[serde(deny_unknown_fields)]
struct Request {
    db_path: String,
    query: String,
    mode: String,
    limit: u32,
    as_of_secs: i64,
    #[serde(default)]
    tags_any: Vec<String>,
    #[serde(default = "default_rrf_k")]
    rrf_k: f64,
    #[serde(default = "default_expand_top")]
    expand_top: u32,
    #[serde(default = "default_threshold")]
    threshold: f32,
}

fn default_rrf_k() -> f64 {
    60.0
}

fn default_expand_top() -> u32 {
    10
}

fn default_threshold() -> f32 {
    0.3
}

fn validate(request: &Request) -> Result<(), String> {
    if request.db_path.trim().is_empty() {
        return Err("db_path must be non-empty".into());
    }
    if request.query.trim().is_empty() {
        return Err("query must be non-empty".into());
    }
    if request.as_of_secs < 0 {
        return Err("as_of_secs must be non-negative".into());
    }
    if request.limit != 20 {
        return Err("limit must equal the preregistered R1 budget of 20".into());
    }
    if !matches!(request.mode.as_str(), "fts" | "hybrid" | "semantic") {
        return Err("mode must be exactly fts, hybrid, or semantic".into());
    }
    if request.rrf_k != 60.0 || request.expand_top != 10 {
        return Err("Hybrid constants must remain rrf_k=60 and expand_top=10".into());
    }
    if request.threshold != 0.3 {
        return Err("Semantic threshold must remain 0.3".into());
    }
    Ok(())
}

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    let request_path = std::env::args()
        .nth(1)
        .ok_or("usage: free_recall_r1_frozen_adapter <request.json>")?;
    let request: Request = serde_json::from_str(&std::fs::read_to_string(&request_path)?)?;
    validate(&request).map_err(|error| format!("invalid frozen request: {error}"))?;

    let store = SqliteStore::open_read_only(Path::new(&request.db_path)).await?;
    let hits = match request.mode.as_str() {
        "fts" => {
            store
                .memory_search_as_of(
                    &request.query,
                    &request.tags_any,
                    request.limit,
                    request.as_of_secs,
                )
                .await?
        }
        "hybrid" => {
            store
                .memory_search_hybrid_as_of(
                    &request.query,
                    &request.tags_any,
                    request.limit,
                    request.rrf_k,
                    request.expand_top,
                    request.as_of_secs,
                    256,
                    false,
                )
                .await?
        }
        "semantic" => {
            if !request.tags_any.is_empty() {
                return Err("semantic mode does not accept tags_any".into());
            }
            store
                .memory_search_semantic_as_of(
                    &request.query,
                    request.limit,
                    request.threshold,
                    request.as_of_secs,
                )
                .await?
        }
        _ => unreachable!("validated mode"),
    };
    let keys: Vec<&str> = hits.iter().map(|hit| hit.record.key.as_str()).collect();
    let payload = serde_json::json!({
        "schema": "agent_bridge.eval.free_recall_r1_frozen_adapter.v0",
        "evaluation_only": true,
        "query_only_connection": true,
        "as_of_secs": request.as_of_secs,
        "mode": request.mode,
        "keys": keys,
    });
    println!("{}", serde_json::to_string(&payload)?);
    Ok(())
}
