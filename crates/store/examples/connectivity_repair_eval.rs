//! Read-only connectivity-repair candidate eval (borrow T8/P4).
//!
//! Loads the live memory graph **read-only** (`SQLITE_OPEN_READ_ONLY`): active
//! non-skill memories as nodes (with importance + tags) and every `memory_edges`
//! row as an undirected edge. Runs the deterministic island→mainland bridge
//! proposer and prints the proposals as JSON. **Nothing is written** — these are
//! candidates for the `memory_related_keys_materialize` propose→review→materialize
//! ladder, not edges. Mirrors the read-only discipline of `quant_drift_eval`.
//!
//! Usage:
//!   cargo run -p ab-store --no-default-features --example connectivity_repair_eval [DB_PATH]
//! (DB_PATH defaults to `ab_store::default_db_path()`.)

use ab_store::connectivity_repair::{analyze, GraphEdge, GraphNode, RepairConfig};
use ab_store::default_db_path;
use tokio_rusqlite::{rusqlite, Connection};

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    let mut args = std::env::args().skip(1);
    let db = args
        .next()
        .map(std::path::PathBuf::from)
        .unwrap_or_else(default_db_path);
    eprintln!("[connectivity-repair] read-only open: {}", db.display());

    let conn = Connection::open_with_flags(&db, rusqlite::OpenFlags::SQLITE_OPEN_READ_ONLY).await?;

    let nodes: Vec<GraphNode> = conn
        .call(|c| -> rusqlite::Result<Vec<GraphNode>> {
            let mut stmt = c.prepare(
                "SELECT key, importance, tags FROM memories \
                 WHERE status = 'active' AND kind != 'skill'",
            )?;
            let rows = stmt
                .query_map([], |row| {
                    let tags_json: Option<String> = row.get(2)?;
                    let tags = tags_json
                        .and_then(|s| serde_json::from_str::<Vec<String>>(&s).ok())
                        .unwrap_or_default();
                    Ok(GraphNode {
                        key: row.get(0)?,
                        importance: row.get(1)?,
                        tags,
                    })
                })?
                .collect::<rusqlite::Result<Vec<_>>>()?;
            Ok(rows)
        })
        .await?;

    let edges: Vec<GraphEdge> = conn
        .call(|c| -> rusqlite::Result<Vec<GraphEdge>> {
            let mut stmt = c.prepare("SELECT from_key, to_key FROM memory_edges")?;
            let rows = stmt
                .query_map([], |row| {
                    Ok(GraphEdge {
                        from: row.get(0)?,
                        to: row.get(1)?,
                    })
                })?
                .collect::<rusqlite::Result<Vec<_>>>()?;
            Ok(rows)
        })
        .await?;

    let report = analyze(&nodes, &edges, &RepairConfig::default());

    // serde_json handles all escaping correctly — DB-sourced keys/tags may
    // contain control chars/newlines a hand-rolled escaper would miss.
    let out = serde_json::json!({
        "schema": "agent_bridge.connectivity_repair_eval.v0",
        "read_only": true,
        "candidate_count": report.candidates.len(),
        "report": report,
    });
    println!("{}", serde_json::to_string_pretty(&out)?);
    Ok(())
}
