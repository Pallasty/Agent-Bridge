//! Read-only ArrowQuant V2 drift / footprint shadow eval (T2 borrow).
//!
//! Quantizes a snapshot of the stored embeddings to per-row symmetric INT8 **in memory**
//! and reports projected byte savings + recall-risk cosine drift. The store DB is opened
//! **read-only** (`SQLITE_OPEN_READ_ONLY`) and never written — `vector.rs` f32 BLOBs stay
//! the source of truth. This is the shadow measurement surface that must clear before any
//! real INT8 column is ever proposed (gated separately via the lswr admission ladder).
//!
//! Usage:
//!   cargo run -p ab-store --no-default-features --example quant_drift_eval [DB_PATH]
//! (DB_PATH defaults to `ab_store::default_db_path()`).

use ab_store::quant::measure_drift;
use ab_store::{decode_embedding, default_db_path};
use tokio_rusqlite::{rusqlite, Connection};

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    let db = std::env::args()
        .nth(1)
        .map(std::path::PathBuf::from)
        .unwrap_or_else(default_db_path);
    eprintln!("[quant-drift] read-only open: {}", db.display());

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
    let report = measure_drift(embeddings.iter().map(|v| v.as_slice()));

    let mb = |bytes: usize| bytes as f64 / (1024.0 * 1024.0);
    let saved = report.f32_bytes.saturating_sub(report.int8_bytes);
    println!("{{");
    println!("  \"schema\": \"agent_bridge.embedding_quant_drift_eval.v0\",");
    println!("  \"read_only\": true,");
    println!("  \"rows\": {},", report.rows);
    println!(
        "  \"f32_bytes\": {}, \"f32_mb\": {:.2},",
        report.f32_bytes,
        mb(report.f32_bytes)
    );
    println!(
        "  \"int8_bytes\": {}, \"int8_mb\": {:.2},",
        report.int8_bytes,
        mb(report.int8_bytes)
    );
    println!(
        "  \"compression_ratio\": {:.4},",
        report.compression_ratio()
    );
    println!("  \"bytes_saved_mb\": {:.2},", mb(saved));
    println!("  \"min_cosine\": {:.6},", report.min_cosine);
    println!("  \"mean_cosine\": {:.6},", report.mean_cosine);
    println!("  \"rows_below_0_999\": {},", report.rows_below_0_999);
    println!("  \"zero_rows\": {}", report.zero_rows);
    println!("}}");
    Ok(())
}
