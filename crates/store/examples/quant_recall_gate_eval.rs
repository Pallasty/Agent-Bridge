//! Read-only INT8 **recall-regression gate** over the stored embeddings (T2 borrow).
//!
//! Loads a snapshot of the active embeddings **read-only** (`SQLITE_OPEN_READ_ONLY`),
//! quantizes a copy to per-row symmetric INT8 in memory, and measures whether the f32
//! top-`k` retrieval neighbors survive — `recall@k` of the dequantized-INT8 corpus against
//! the still-`f32` query (the realistic "fresh query vs INT8 store" path). Prints a JSON
//! verdict and exits non-zero when the gate does NOT pass, so it can be wired into CI / a
//! pre-flight before any real INT8 column is ever proposed (which then goes through the lswr
//! admission ladder — this surface writes nothing).
//!
//! Usage:
//!   cargo run -p ab-store --no-default-features --example quant_recall_gate_eval -- \
//!     [DB_PATH] [K] [MAX_QUERIES] [THRESHOLD]
//! Defaults: DB = `ab_store::default_db_path()`, K = 10, MAX_QUERIES = 200, THRESHOLD = 0.98.

use ab_store::quant::recall_regression_gate;
use ab_store::{decode_embedding, default_db_path};
use tokio_rusqlite::{rusqlite, Connection};

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    let mut args = std::env::args().skip(1);
    let db = args
        .next()
        .map(std::path::PathBuf::from)
        .unwrap_or_else(default_db_path);
    let k: usize = args.next().and_then(|s| s.parse().ok()).unwrap_or(10);
    let max_queries: usize = args.next().and_then(|s| s.parse().ok()).unwrap_or(200);
    let threshold: f64 = args.next().and_then(|s| s.parse().ok()).unwrap_or(0.98);

    eprintln!("[recall-gate] read-only open: {}", db.display());
    let conn = Connection::open_with_flags(&db, rusqlite::OpenFlags::SQLITE_OPEN_READ_ONLY).await?;
    let blobs: Vec<Vec<u8>> = conn
        .call(|c| -> rusqlite::Result<Vec<Vec<u8>>> {
            let mut stmt = c.prepare(
                "SELECT embedding FROM memories \
                 WHERE status = 'active' AND embedding IS NOT NULL",
            )?;
            let rows = stmt
                .query_map([], |row| row.get::<_, Vec<u8>>(0))?
                .collect::<rusqlite::Result<Vec<_>>>()?;
            Ok(rows)
        })
        .await?;

    let embeddings: Vec<Vec<f32>> = blobs.iter().map(|b| decode_embedding(b)).collect();
    let rows: Vec<&[f32]> = embeddings.iter().map(|v| v.as_slice()).collect();
    eprintln!("[recall-gate] {} active embeddings loaded", rows.len());

    let rep = recall_regression_gate(&rows, k, max_queries, threshold);

    println!("{{");
    println!("  \"schema\": \"agent_bridge.embedding_quant_recall_gate.v0\",");
    println!("  \"read_only\": true,");
    println!("  \"corpus\": {},", rep.corpus);
    println!("  \"queries\": {},", rep.queries);
    println!("  \"k\": {},", rep.k);
    println!("  \"mean_recall_at_k\": {:.6},", rep.mean_recall_at_k);
    println!("  \"min_recall_at_k\": {:.6},", rep.min_recall_at_k);
    println!(
        "  \"queries_below_threshold\": {},",
        rep.queries_below_threshold
    );
    println!("  \"threshold\": {:.6},", rep.threshold);
    println!("  \"passed\": {}", rep.passed);
    println!("}}");

    if rep.passed {
        eprintln!(
            "[recall-gate] PASS — INT8 preserves top-{} retrieval neighbors",
            rep.k
        );
        Ok(())
    } else {
        eprintln!(
            "[recall-gate] FAIL — mean recall@{} {:.4} < threshold {:.4} ({} queries below)",
            rep.k, rep.mean_recall_at_k, rep.threshold, rep.queries_below_threshold
        );
        std::process::exit(1);
    }
}
