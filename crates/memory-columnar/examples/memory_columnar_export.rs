//! Read-only columnar memory export (T5 borrow).
//!
//! Reads the live `memories` table **read-only** (`SQLITE_OPEN_READ_ONLY`),
//! projects every row (the full active/archived/superseded lifecycle) into a
//! typed [`MemoryColumnarRow`] — embedding
//! decoded from its f32 BLOB into a real `List<Float32>` — and writes a
//! versioned Parquet "long-term memory library" archive. The SQLite DB is
//! never written; the f32 BLOBs in `memories.embedding` stay the source of
//! truth. This mirrors the read-only discipline of `quant_drift_eval`.
//!
//! Usage:
//!   cargo run -p ab-memory-columnar --example memory_columnar_export [DB_PATH] [OUT_PARQUET]
//! DB_PATH defaults to `ab_store::default_db_path()`;
//! OUT_PARQUET defaults to `$HOME/.local/share/agent-bridge/memories_columnar.parquet`.

use std::path::PathBuf;

use ab_memory_columnar::{
    summarize, write_parquet, MemoryColumnarRow, MEMORY_COLUMNAR_SCHEMA_CONTRACT,
};
use ab_store::{decode_embedding, default_db_path};
use tokio_rusqlite::{rusqlite, Connection};

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    let mut args = std::env::args().skip(1);
    let db = args
        .next()
        .map(PathBuf::from)
        .unwrap_or_else(default_db_path);
    let out = args.next().map(PathBuf::from).unwrap_or_else(|| {
        let home = std::env::var("HOME").unwrap_or_else(|_| ".".to_string());
        PathBuf::from(home).join(".local/share/agent-bridge/memories_columnar.parquet")
    });
    eprintln!("[mem-columnar] read-only open: {}", db.display());

    let conn = Connection::open_with_flags(&db, rusqlite::OpenFlags::SQLITE_OPEN_READ_ONLY).await?;
    let raw: Vec<RawRow> = conn
        .call(|c| -> rusqlite::Result<Vec<RawRow>> {
            // Full lifecycle: a "long-term memory library" archives archived /
            // superseded rows too, not just active ones — so `status` carries
            // real signal. Ordered by key for a stable, cross-run-comparable file.
            let mut stmt = c.prepare(
                "SELECT key, kind, content, tags, related_keys, scope, \
                        created_at, updated_at, last_accessed_at, access_count, \
                        importance, status, embedding, embedding_backend \
                 FROM memories ORDER BY key",
            )?;
            let rows = stmt
                .query_map([], |row| {
                    Ok(RawRow {
                        key: row.get(0)?,
                        kind: row.get(1)?,
                        content: row.get(2)?,
                        tags_json: row.get(3)?,
                        related_json: row.get(4)?,
                        scope: row.get(5)?,
                        created_at: row.get(6)?,
                        updated_at: row.get(7)?,
                        last_accessed_at: row.get(8)?,
                        access_count: row.get(9)?,
                        importance: row.get(10)?,
                        status: row.get(11)?,
                        embedding: row.get(12)?,
                        embedding_backend: row.get(13)?,
                    })
                })?
                .collect::<rusqlite::Result<Vec<_>>>()?;
            Ok(rows)
        })
        .await?;

    let rows: Vec<MemoryColumnarRow> = raw.into_iter().map(RawRow::into_columnar).collect();
    let footprint = summarize(&rows);
    write_parquet(&out, &rows)?;

    let mb = |b: usize| b as f64 / (1024.0 * 1024.0);
    println!("{{");
    println!("  \"schema_contract\": \"{MEMORY_COLUMNAR_SCHEMA_CONTRACT}\",");
    println!("  \"read_only\": true,");
    println!("  \"out\": \"{}\",", out.display());
    println!("  \"rows\": {},", footprint.rows);
    println!(
        "  \"rows_with_embedding\": {},",
        footprint.rows_with_embedding
    );
    println!("  \"embedding_dims\": {:?},", footprint.embedding_dims);
    println!(
        "  \"total_embedding_floats\": {},",
        footprint.total_embedding_floats
    );
    println!(
        "  \"f32_embedding_mb\": {:.3}",
        mb(footprint.f32_embedding_bytes)
    );
    println!("}}");
    Ok(())
}

struct RawRow {
    key: String,
    kind: String,
    content: String,
    tags_json: Option<String>,
    related_json: Option<String>,
    scope: Option<String>,
    created_at: i64,
    updated_at: i64,
    last_accessed_at: i64,
    access_count: i64,
    importance: f64,
    status: String,
    embedding: Option<Vec<u8>>,
    embedding_backend: Option<String>,
}

impl RawRow {
    fn into_columnar(self) -> MemoryColumnarRow {
        // Destructure so helpers can borrow `key` for warnings, then move it.
        let RawRow {
            key,
            kind,
            content,
            tags_json,
            related_json,
            scope,
            created_at,
            updated_at,
            last_accessed_at,
            access_count,
            importance,
            status,
            embedding,
            embedding_backend,
        } = self;
        let tags = parse_json_list(&key, "tags", tags_json);
        let related_keys = parse_json_list(&key, "related_keys", related_json);
        let embedding = decode_embedding_blob(&key, embedding);
        MemoryColumnarRow {
            key,
            kind,
            content,
            tags,
            related_keys,
            scope,
            created_at,
            updated_at,
            last_accessed_at,
            access_count,
            importance,
            status,
            embedding,
            embedding_backend,
        }
    }
}

/// Parse a stored JSON string array into a typed `Vec<String>`. Empty/absent →
/// empty; **present-but-unparseable → empty + a per-key warning**, so a silent
/// divergence between the SQLite source and the archive stays observable.
fn parse_json_list(key: &str, field: &str, j: Option<String>) -> Vec<String> {
    match j {
        None => Vec::new(),
        Some(s) if s.is_empty() => Vec::new(),
        Some(s) => match serde_json::from_str::<Vec<String>>(&s) {
            Ok(v) => v,
            Err(e) => {
                eprintln!(
                    "[mem-columnar] WARN: key {key}: unparseable {field} JSON ({e}); archiving empty"
                );
                Vec::new()
            }
        },
    }
}

/// Decode an embedding BLOB into `Option<Vec<f32>>`. A non-null BLOB whose
/// length isn't f32-aligned decodes to empty (per `ab_store::decode_embedding`);
/// surface that as `None` + a warning rather than laundering a corrupt
/// embedding into a benign-looking empty list (`null != empty` matters here).
fn decode_embedding_blob(key: &str, blob: Option<Vec<u8>>) -> Option<Vec<f32>> {
    let b = blob?;
    if b.is_empty() {
        return None;
    }
    let v = decode_embedding(&b);
    if v.is_empty() {
        eprintln!(
            "[mem-columnar] WARN: key {key}: malformed embedding BLOB ({} bytes, not f32-aligned); archiving null",
            b.len()
        );
        return None;
    }
    Some(v)
}
