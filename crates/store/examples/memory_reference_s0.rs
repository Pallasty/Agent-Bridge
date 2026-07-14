//! Clean, read-only runner for the BioCortex/AB Track B reference surface.
//!
//! The runner consumes one JSON request, opens the supplied SQLite snapshot in
//! query-only mode, binds one frozen `as_of_secs`, and emits the bounded,
//! telemetry-free reference projection. It is intentionally a store example,
//! not an MCP tool and not a production retrieval switch.

use ab_store::{MemorySearchReferenceOptions, SqliteStore, StateStore};
use serde::Deserialize;
use std::path::Path;

#[derive(Debug, Deserialize)]
#[serde(deny_unknown_fields)]
struct Request {
    db_path: String,
    query: String,
    #[serde(default)]
    tags_any: Vec<String>,
    #[serde(default = "default_limit")]
    limit: u32,
    #[serde(default = "default_rrf_k")]
    rrf_k: f64,
    #[serde(default = "default_expand_top")]
    expand_top: u32,
    as_of_secs: i64,
    #[serde(default = "default_graph_fanout")]
    graph_fanout: usize,
    #[serde(default = "default_context_bytes")]
    max_context_bytes: usize,
    #[serde(default = "default_exclude_kinds")]
    exclude_kinds: Vec<String>,
}

fn default_limit() -> u32 {
    10
}

fn default_rrf_k() -> f64 {
    60.0
}

fn default_expand_top() -> u32 {
    10
}

fn default_graph_fanout() -> usize {
    ab_store::MEMORY_REFERENCE_GRAPH_FANOUT
}

fn default_context_bytes() -> usize {
    ab_store::MEMORY_REFERENCE_MAX_CONTEXT_BYTES
}

fn default_exclude_kinds() -> Vec<String> {
    vec!["skill".to_string()]
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
    if !(1..=40).contains(&request.limit) {
        return Err("limit must be in 1..=40".into());
    }
    if !(1..=20).contains(&request.expand_top) {
        return Err("expand_top must be in 1..=20".into());
    }
    if request.graph_fanout == 0 || request.graph_fanout > 256 {
        return Err("graph_fanout must be in 1..=256".into());
    }
    if !request.rrf_k.is_finite() || request.rrf_k < 1.0 || request.rrf_k > 200.0 {
        return Err("rrf_k must be finite and in 1..=200".into());
    }
    if request.max_context_bytes < 2 || request.max_context_bytes > 16 * 1024 * 1024 {
        return Err("max_context_bytes must be in 2..=16777216".into());
    }
    if request.exclude_kinds.iter().any(|kind| kind.trim().is_empty()) {
        return Err("exclude_kinds must contain non-empty values".into());
    }
    Ok(())
}

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    let request_path = std::env::args()
        .nth(1)
        .ok_or("usage: memory_reference_s0 <request.json>")?;
    let request: Request = serde_json::from_str(&std::fs::read_to_string(&request_path)?)?;
    validate(&request).map_err(|e| format!("invalid reference request: {e}"))?;

    let store = SqliteStore::open_read_only(Path::new(&request.db_path)).await?;
    let options = MemorySearchReferenceOptions {
        as_of_secs: request.as_of_secs,
        graph_fanout: request.graph_fanout,
        max_context_bytes: request.max_context_bytes,
        exclude_kinds: request.exclude_kinds.clone(),
    };
    let context = store
        .memory_search_reference(
            &request.query,
            &request.tags_any,
            request.limit,
            request.rrf_k,
            request.expand_top,
            options,
        )
        .await?;
    let payload = serde_json::json!({
        "schema": "agent_bridge.store.memory_search.reference.v0",
        "reference_only": true,
        "read_only_snapshot": true,
        "context_budget_basis": "UTF8_BYTES_V0",
        "model_tokenizer_bound": false,
        "access_telemetry_in_context": false,
        "as_of_secs": request.as_of_secs,
        "graph_fanout": request.graph_fanout,
        "max_context_bytes": request.max_context_bytes,
        "exclude_kinds": request.exclude_kinds,
        "context_bytes": context.context_bytes,
        "context_json": context.context_json,
        "hits": context.hits,
    });
    println!("{}", serde_json::to_string(&payload)?);
    Ok(())
}
