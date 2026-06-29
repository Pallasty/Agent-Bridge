//! Columnar memory export — Arrow/Parquet "long-term memory library" surface.
//!
//! Borrow provenance (CascadeProjects scan 2026-06-28, T5):
//! - **AQFH 技术实现规范** frames an "Arrow记忆引擎: Parquet存储 / Arrow缓存 /
//!   Flight传输" as the durable substrate of memory reload.
//! - **`Neon与Arrow+Parquet的记忆模型类比分析`** memo casts Arrow+Parquet as the
//!   *long-term memory library* (大容量 / 组织化归档 / 压缩存储 / 持久保存),
//!   complementary to the live SQLite "working memory".
//!
//! This crate turns the live `memories` table into a **typed columnar
//! snapshot**: each row carries its embedding as a real Arrow `List<Float32>`
//! instead of an opaque f32 BLOB, plus the cognitive metadata (kind, tags,
//! scope, importance, status, lifecycle timestamps). A columnar layout makes
//! the archive cheap to scan by column, compress, diff across machines, and
//! hand to Arrow-native analytics — exactly the "library" role above.
//!
//! ## Discipline
//! - **Read-only / shadow.** Nothing here mutates the live DB. The codec is
//!   DB-agnostic — it operates on plain [`MemoryColumnarRow`] values; the
//!   read-only SQLite read lives in `examples/memory_columnar_export.rs`.
//! - **Deterministic.** No clock, no RNG. [`fingerprint`] gives a canonical
//!   cross-machine equivalence hash.
//! - **Versioned schema contract.** [`MEMORY_COLUMNAR_SCHEMA_CONTRACT`] is
//!   embedded both in the Arrow schema metadata and (explicitly, footer-
//!   readable) in the Parquet key-value metadata — the nexus-style contract
//!   version that lets a reader reject an incompatible file without decoding
//!   it. Bump the major when the column set changes.

use std::collections::HashMap;
use std::path::Path;
use std::sync::Arc;

use arrow::array::{
    Array, Float32Array, Float32Builder, Float64Array, Int64Array, ListArray, ListBuilder,
    StringArray, StringBuilder,
};
use arrow::datatypes::{DataType, Field, Schema};
use arrow::record_batch::RecordBatch;
use parquet::arrow::arrow_reader::ParquetRecordBatchReaderBuilder;
use parquet::arrow::ArrowWriter;
use parquet::basic::{Compression, ZstdLevel};
use parquet::file::properties::WriterProperties;
use parquet::format::KeyValue;
use sha2::{Digest, Sha256};

/// Schema-contract version (nexus-style). Embedded in both the Arrow schema
/// metadata and the Parquet footer KV metadata. Bump the **major** (`vN`)
/// whenever the column set or an encoding changes incompatibly.
pub const MEMORY_COLUMNAR_SCHEMA_CONTRACT: &str = "ab.memory_columnar.v1";

/// Metadata key under which [`MEMORY_COLUMNAR_SCHEMA_CONTRACT`] is written.
pub const SCHEMA_CONTRACT_META_KEY: &str = "ab.schema_contract";

/// Metadata key recording the borrow provenance (AQFH / Neon memo).
pub const PROVENANCE_META_KEY: &str = "ab.provenance";

/// Human-readable provenance string written into the file metadata.
pub const PROVENANCE: &str =
    "AQFH Arrow记忆引擎 (Parquet长期记忆库) + Neon/Arrow+Parquet memo; read-only shadow export";

/// One row of the columnar memory archive — a typed projection of one
/// `memories` table row.
#[derive(Debug, Clone, PartialEq)]
pub struct MemoryColumnarRow {
    /// Primary key.
    pub key: String,
    /// Memory kind (decision / lesson / todo / fact / observation / ...).
    pub kind: String,
    /// Full textual content.
    pub content: String,
    /// Tags, exploded from the stored JSON array into a typed list.
    pub tags: Vec<String>,
    /// Related-memory keys, exploded from the stored JSON array.
    pub related_keys: Vec<String>,
    /// Visibility scope. `None` = global.
    pub scope: Option<String>,
    /// Creation unix seconds.
    pub created_at: i64,
    /// Last update unix seconds.
    pub updated_at: i64,
    /// Last access unix seconds.
    pub last_accessed_at: i64,
    /// Access count (DB `u64`, widened to `i64` for Arrow).
    pub access_count: i64,
    /// Cognitive importance (0.0–1.0).
    pub importance: f64,
    /// Lifecycle status: active / archived / superseded.
    pub status: String,
    /// Embedding vector. `None` = no embedding stored. Dimension varies by
    /// backend (e.g. 384 for the L3 contract, 192 for the seed substrate),
    /// which is why this is a variable-length `List<Float32>` not a
    /// `FixedSizeList`. Values round-trip **bit-exactly** through Parquet, but
    /// note IEEE-754: a `NaN` element makes derived `PartialEq` report the row
    /// as unequal to its bit-identical round-trip (`NaN != NaN`). Use
    /// [`fingerprint`] for equivalence — it is byte-canonical and NaN-stable.
    pub embedding: Option<Vec<f32>>,
    /// Embedding backend that produced [`Self::embedding`] (v26 column).
    pub embedding_backend: Option<String>,
}

/// Arrow schema for the columnar memory archive. The schema metadata carries
/// the contract version + provenance. **Stable across releases** — any change
/// here must bump [`MEMORY_COLUMNAR_SCHEMA_CONTRACT`]; the
/// `arrow_schema_is_stable` test locks the column set.
pub fn arrow_schema() -> Arc<Schema> {
    let mut meta = HashMap::new();
    meta.insert(
        SCHEMA_CONTRACT_META_KEY.to_string(),
        MEMORY_COLUMNAR_SCHEMA_CONTRACT.to_string(),
    );
    meta.insert(PROVENANCE_META_KEY.to_string(), PROVENANCE.to_string());
    meta.insert(
        "ab.embedding_repr".to_string(),
        "List<Float32>, per-row; null = no embedding; dim varies by backend".to_string(),
    );
    meta.insert("ab.read_only".to_string(), "true".to_string());

    let str_item = || Arc::new(Field::new("item", DataType::Utf8, true));
    Arc::new(Schema::new_with_metadata(
        vec![
            Field::new("key", DataType::Utf8, false),
            Field::new("kind", DataType::Utf8, false),
            Field::new("content", DataType::Utf8, false),
            Field::new("tags", DataType::List(str_item()), false),
            Field::new("related_keys", DataType::List(str_item()), false),
            Field::new("scope", DataType::Utf8, true),
            Field::new("created_at", DataType::Int64, false),
            Field::new("updated_at", DataType::Int64, false),
            Field::new("last_accessed_at", DataType::Int64, false),
            Field::new("access_count", DataType::Int64, false),
            Field::new("importance", DataType::Float64, false),
            Field::new("status", DataType::Utf8, false),
            Field::new(
                "embedding",
                DataType::List(Arc::new(Field::new("item", DataType::Float32, true))),
                true,
            ),
            Field::new("embedding_backend", DataType::Utf8, true),
        ],
        meta,
    ))
}

/// Build a [`RecordBatch`] from a slice of rows.
pub fn rows_to_batch(rows: &[MemoryColumnarRow]) -> Result<RecordBatch, arrow::error::ArrowError> {
    let schema = arrow_schema();

    let key: StringArray = StringArray::from_iter_values(rows.iter().map(|r| r.key.as_str()));
    let kind: StringArray = StringArray::from_iter_values(rows.iter().map(|r| r.kind.as_str()));
    let content: StringArray =
        StringArray::from_iter_values(rows.iter().map(|r| r.content.as_str()));
    let scope: StringArray = rows.iter().map(|r| r.scope.as_deref()).collect();
    let created_at: Int64Array = Int64Array::from_iter_values(rows.iter().map(|r| r.created_at));
    let updated_at: Int64Array = Int64Array::from_iter_values(rows.iter().map(|r| r.updated_at));
    let last_accessed_at: Int64Array =
        Int64Array::from_iter_values(rows.iter().map(|r| r.last_accessed_at));
    let access_count: Int64Array =
        Int64Array::from_iter_values(rows.iter().map(|r| r.access_count));
    let importance: Float64Array =
        Float64Array::from_iter_values(rows.iter().map(|r| r.importance));
    let status: StringArray = StringArray::from_iter_values(rows.iter().map(|r| r.status.as_str()));
    let backend: StringArray = rows
        .iter()
        .map(|r| r.embedding_backend.as_deref())
        .collect();

    let tags = build_str_list(rows.iter().map(|r| r.tags.as_slice()));
    let related = build_str_list(rows.iter().map(|r| r.related_keys.as_slice()));
    let embedding = build_opt_f32_list(rows.iter().map(|r| r.embedding.as_deref()));

    RecordBatch::try_new(
        schema,
        vec![
            Arc::new(key),
            Arc::new(kind),
            Arc::new(content),
            Arc::new(tags),
            Arc::new(related),
            Arc::new(scope),
            Arc::new(created_at),
            Arc::new(updated_at),
            Arc::new(last_accessed_at),
            Arc::new(access_count),
            Arc::new(importance),
            Arc::new(status),
            Arc::new(embedding),
            Arc::new(backend),
        ],
    )
}

fn build_str_list<'a, I: Iterator<Item = &'a [String]>>(iter: I) -> ListArray {
    let mut builder = ListBuilder::new(StringBuilder::new());
    for slice in iter {
        for s in slice {
            builder.values().append_value(s.as_str());
        }
        builder.append(true);
    }
    builder.finish()
}

/// Build a **nullable** `List<Float32>`: `None` → a null list entry (distinct
/// from an empty list), `Some(vec)` → the values.
fn build_opt_f32_list<'a, I: Iterator<Item = Option<&'a [f32]>>>(iter: I) -> ListArray {
    let mut builder = ListBuilder::new(Float32Builder::new());
    for slot in iter {
        match slot {
            Some(slice) => {
                for &v in slice {
                    builder.values().append_value(v);
                }
                builder.append(true);
            }
            None => builder.append(false),
        }
    }
    builder.finish()
}

/// Decode rows from a [`RecordBatch`]. Inverse of [`rows_to_batch`].
pub fn batch_to_rows(
    batch: &RecordBatch,
) -> Result<Vec<MemoryColumnarRow>, arrow::error::ArrowError> {
    let n = batch.num_rows();
    let key = str_col(batch, 0, "key")?;
    let kind = str_col(batch, 1, "kind")?;
    let content = str_col(batch, 2, "content")?;
    let tags = list_col(batch, 3, "tags")?;
    let related = list_col(batch, 4, "related_keys")?;
    let scope = str_col(batch, 5, "scope")?;
    let created_at = i64_col(batch, 6, "created_at")?;
    let updated_at = i64_col(batch, 7, "updated_at")?;
    let last_accessed_at = i64_col(batch, 8, "last_accessed_at")?;
    let access_count = i64_col(batch, 9, "access_count")?;
    let importance = batch
        .column(10)
        .as_any()
        .downcast_ref::<Float64Array>()
        .ok_or_else(|| arrow::error::ArrowError::CastError("importance".into()))?;
    let status = str_col(batch, 11, "status")?;
    let embedding = list_col(batch, 12, "embedding")?;
    let backend = str_col(batch, 13, "embedding_backend")?;

    let mut out = Vec::with_capacity(n);
    for i in 0..n {
        out.push(MemoryColumnarRow {
            key: key.value(i).to_string(),
            kind: kind.value(i).to_string(),
            content: content.value(i).to_string(),
            tags: extract_str_list(tags, i)?,
            related_keys: extract_str_list(related, i)?,
            scope: opt_str(scope, i),
            created_at: created_at.value(i),
            updated_at: updated_at.value(i),
            last_accessed_at: last_accessed_at.value(i),
            access_count: access_count.value(i),
            importance: importance.value(i),
            status: status.value(i).to_string(),
            embedding: if embedding.is_null(i) {
                None
            } else {
                Some(extract_f32_list(embedding, i)?)
            },
            embedding_backend: opt_str(backend, i),
        });
    }
    Ok(out)
}

fn str_col<'a>(
    batch: &'a RecordBatch,
    idx: usize,
    name: &str,
) -> Result<&'a StringArray, arrow::error::ArrowError> {
    batch
        .column(idx)
        .as_any()
        .downcast_ref::<StringArray>()
        .ok_or_else(|| arrow::error::ArrowError::CastError(name.into()))
}

fn i64_col<'a>(
    batch: &'a RecordBatch,
    idx: usize,
    name: &str,
) -> Result<&'a Int64Array, arrow::error::ArrowError> {
    batch
        .column(idx)
        .as_any()
        .downcast_ref::<Int64Array>()
        .ok_or_else(|| arrow::error::ArrowError::CastError(name.into()))
}

fn list_col<'a>(
    batch: &'a RecordBatch,
    idx: usize,
    name: &str,
) -> Result<&'a ListArray, arrow::error::ArrowError> {
    batch
        .column(idx)
        .as_any()
        .downcast_ref::<ListArray>()
        .ok_or_else(|| arrow::error::ArrowError::CastError(name.into()))
}

fn opt_str(arr: &StringArray, i: usize) -> Option<String> {
    if arr.is_null(i) {
        None
    } else {
        Some(arr.value(i).to_string())
    }
}

// NOTE: these return `Result` rather than panicking. A foreign/forged Parquet
// file can carry our contract string in its footer yet type an inner list
// element wrong (e.g. embedding as `List<Int64>`); the contract gate + the
// outer `ListArray` downcast both pass, so the inner-type mismatch must be a
// recoverable `Err`, never a panic — `read_parquet`/`batch_to_rows` are
// declared to return `Result`.
fn extract_f32_list(arr: &ListArray, i: usize) -> Result<Vec<f32>, arrow::error::ArrowError> {
    let v = arr.value(i);
    let f = v.as_any().downcast_ref::<Float32Array>().ok_or_else(|| {
        arrow::error::ArrowError::CastError("embedding inner: expected Float32".into())
    })?;
    Ok((0..f.len()).map(|k| f.value(k)).collect())
}

fn extract_str_list(arr: &ListArray, i: usize) -> Result<Vec<String>, arrow::error::ArrowError> {
    let v = arr.value(i);
    let f = v.as_any().downcast_ref::<StringArray>().ok_or_else(|| {
        arrow::error::ArrowError::CastError("string list inner: expected Utf8".into())
    })?;
    Ok((0..f.len()).map(|k| f.value(k).to_string()).collect())
}

/// Read all rows from an existing columnar file. Returns empty if the file
/// does not exist. Verifies the embedded schema contract before decoding.
pub fn read_parquet(path: &Path) -> Result<Vec<MemoryColumnarRow>, MemoryColumnarError> {
    if !path.exists() {
        return Ok(Vec::new());
    }
    let file = std::fs::File::open(path)?;
    let builder = ParquetRecordBatchReaderBuilder::try_new(file)?;
    verify_contract(builder.metadata().file_metadata().key_value_metadata())?;
    let reader = builder.build()?;
    let mut rows = Vec::new();
    for batch in reader {
        let batch = batch?;
        rows.extend(batch_to_rows(&batch)?);
    }
    Ok(rows)
}

/// Read the schema-contract version from a file's Parquet footer without
/// decoding any row groups. `None` if absent.
pub fn read_contract(path: &Path) -> Result<Option<String>, MemoryColumnarError> {
    let file = std::fs::File::open(path)?;
    let builder = ParquetRecordBatchReaderBuilder::try_new(file)?;
    let found = builder
        .metadata()
        .file_metadata()
        .key_value_metadata()
        .and_then(|kvs| {
            kvs.iter()
                .find(|kv| kv.key == SCHEMA_CONTRACT_META_KEY)
                .and_then(|kv| kv.value.clone())
        });
    Ok(found)
}

/// Total `(compressed, uncompressed)` column-chunk bytes, read from the Parquet
/// footer without decoding any row group. `uncompressed / compressed` is the
/// realized ZSTD archival ratio — the "compressed storage" claim, measured.
pub fn compression_stats(path: &Path) -> Result<(u64, u64), MemoryColumnarError> {
    let file = std::fs::File::open(path)?;
    let builder = ParquetRecordBatchReaderBuilder::try_new(file)?;
    let md = builder.metadata();
    let mut compressed = 0u64;
    let mut uncompressed = 0u64;
    for rg in 0..md.num_row_groups() {
        let rgm = md.row_group(rg);
        for c in 0..rgm.num_columns() {
            let col = rgm.column(c);
            compressed = compressed.saturating_add(col.compressed_size().max(0) as u64);
            uncompressed = uncompressed.saturating_add(col.uncompressed_size().max(0) as u64);
        }
    }
    Ok((compressed, uncompressed))
}

fn verify_contract(kvs: Option<&Vec<KeyValue>>) -> Result<(), MemoryColumnarError> {
    let found = kvs.and_then(|kvs| {
        kvs.iter()
            .find(|kv| kv.key == SCHEMA_CONTRACT_META_KEY)
            .and_then(|kv| kv.value.clone())
    });
    match found {
        Some(v) if v == MEMORY_COLUMNAR_SCHEMA_CONTRACT => Ok(()),
        Some(v) => Err(MemoryColumnarError::Contract {
            expected: MEMORY_COLUMNAR_SCHEMA_CONTRACT,
            found: v,
        }),
        None => Err(MemoryColumnarError::Contract {
            expected: MEMORY_COLUMNAR_SCHEMA_CONTRACT,
            found: "<absent>".to_string(),
        }),
    }
}

/// Write all rows to `path`, overwriting prior contents. Embeds the schema
/// contract + provenance in the Parquet footer KV metadata, and ZSTD-compresses
/// the column chunks (the "compressed storage" half of the long-term-library
/// role). Atomic via tmp+rename so a crash mid-write can't truncate a prior
/// archive.
pub fn write_parquet(path: &Path, rows: &[MemoryColumnarRow]) -> Result<(), MemoryColumnarError> {
    if let Some(parent) = path.parent() {
        std::fs::create_dir_all(parent)?;
    }
    let kv = vec![
        KeyValue {
            key: SCHEMA_CONTRACT_META_KEY.to_string(),
            value: Some(MEMORY_COLUMNAR_SCHEMA_CONTRACT.to_string()),
        },
        KeyValue {
            key: PROVENANCE_META_KEY.to_string(),
            value: Some(PROVENANCE.to_string()),
        },
    ];
    // pid-suffixed tmp so concurrent exporters to the same target don't share
    // (and clobber) one in-flight file; the final rename is the atomic publish.
    let tmp = path.with_extension(format!("parquet.tmp.{}", std::process::id()));
    let result = (|| -> Result<(), MemoryColumnarError> {
        let file = std::fs::File::create(&tmp)?;
        let props = WriterProperties::builder()
            .set_key_value_metadata(Some(kv))
            // ZSTD column compression — the "compressed storage" half of the
            // long-term-library pitch. Deterministic for a fixed codec+level;
            // the cross-machine equivalence primitive is the per-row
            // `fingerprint` (row data, not file bytes), so compression never
            // affects equivalence.
            .set_compression(Compression::ZSTD(
                ZstdLevel::try_new(3).expect("3 is a valid zstd level"),
            ))
            .build();
        let mut writer = ArrowWriter::try_new(file, arrow_schema(), Some(props))?;
        if !rows.is_empty() {
            let batch = rows_to_batch(rows)?;
            writer.write(&batch)?;
        }
        writer.close()?;
        Ok(())
    })();
    if let Err(e) = result {
        // best-effort: don't leave an orphan .tmp behind on the error path.
        let _ = std::fs::remove_file(&tmp);
        return Err(e);
    }
    std::fs::rename(&tmp, path)?;
    Ok(())
}

/// SHA256 fingerprint of one row in a deterministic canonical form. Used as a
/// cross-machine equivalence check (same canonical-hash discipline as the
/// substrate snapshot in `ab-seed-bridge`).
///
/// This hash is **byte-canonical** over the raw f32/f64 little-endian bytes:
/// it is stable for a fixed `NaN` bit pattern, and it distinguishes `-0.0`
/// from `+0.0` (and distinct `NaN` payloads) — a strictly finer relation than
/// the derived `PartialEq` on [`MemoryColumnarRow`] (which treats `-0.0 ==
/// +0.0`, and any `NaN` as unequal). Prefer this over `==` for equivalence.
pub fn fingerprint(row: &MemoryColumnarRow) -> String {
    let mut h = Sha256::new();
    hash_str(&mut h, &row.key);
    hash_str(&mut h, &row.kind);
    hash_str(&mut h, &row.content);
    h.update((row.tags.len() as u32).to_le_bytes());
    for t in &row.tags {
        hash_str(&mut h, t);
    }
    h.update((row.related_keys.len() as u32).to_le_bytes());
    for r in &row.related_keys {
        hash_str(&mut h, r);
    }
    match &row.scope {
        Some(s) => {
            h.update([1u8]);
            hash_str(&mut h, s);
        }
        None => h.update([0u8]),
    }
    h.update(row.created_at.to_le_bytes());
    h.update(row.updated_at.to_le_bytes());
    h.update(row.last_accessed_at.to_le_bytes());
    h.update(row.access_count.to_le_bytes());
    h.update(row.importance.to_le_bytes());
    hash_str(&mut h, &row.status);
    match &row.embedding {
        Some(v) => {
            h.update([1u8]);
            h.update((v.len() as u32).to_le_bytes());
            for f in v {
                h.update(f.to_le_bytes());
            }
        }
        None => h.update([0u8]),
    }
    match &row.embedding_backend {
        Some(b) => {
            h.update([1u8]);
            hash_str(&mut h, b);
        }
        None => h.update([0u8]),
    }
    let digest = h.finalize();
    let mut out = String::with_capacity(64);
    for b in digest {
        out.push_str(&format!("{:02x}", b));
    }
    out
}

fn hash_str(h: &mut Sha256, s: &str) {
    h.update((s.len() as u32).to_le_bytes());
    h.update(s.as_bytes());
}

/// Footprint summary of a columnar memory set — the read-only measurement
/// surface for the export example.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct MemoryColumnarFootprint {
    /// Total rows.
    pub rows: usize,
    /// Rows carrying a non-null embedding.
    pub rows_with_embedding: usize,
    /// Distinct embedding dimensions observed (sorted ascending).
    pub embedding_dims: Vec<usize>,
    /// Sum of all embedding lengths across rows.
    pub total_embedding_floats: usize,
    /// Raw f32 byte footprint of the embeddings (`total_embedding_floats * 4`).
    pub f32_embedding_bytes: usize,
}

/// Summarize a row set into a [`MemoryColumnarFootprint`].
pub fn summarize(rows: &[MemoryColumnarRow]) -> MemoryColumnarFootprint {
    let mut dims = Vec::new();
    let mut rows_with_embedding = 0;
    let mut total = 0usize;
    for r in rows {
        if let Some(v) = &r.embedding {
            rows_with_embedding += 1;
            total += v.len();
            if !dims.contains(&v.len()) {
                dims.push(v.len());
            }
        }
    }
    dims.sort_unstable();
    MemoryColumnarFootprint {
        rows: rows.len(),
        rows_with_embedding,
        embedding_dims: dims,
        total_embedding_floats: total,
        f32_embedding_bytes: total * 4,
    }
}

/// Columnar module errors.
#[derive(Debug, thiserror::Error)]
pub enum MemoryColumnarError {
    #[error("memory-columnar IO error: {0}")]
    Io(#[from] std::io::Error),
    #[error("memory-columnar arrow error: {0}")]
    Arrow(#[from] arrow::error::ArrowError),
    #[error("memory-columnar parquet error: {0}")]
    Parquet(#[from] parquet::errors::ParquetError),
    #[error("schema contract mismatch: expected {expected}, found {found}")]
    Contract {
        expected: &'static str,
        found: String,
    },
}

#[cfg(test)]
mod tests {
    use super::*;
    use tempfile::tempdir;

    fn sample(key: &str, dim: Option<usize>) -> MemoryColumnarRow {
        MemoryColumnarRow {
            key: key.to_string(),
            kind: "decision".to_string(),
            content: format!("content for {key} — 你好"),
            tags: vec!["a".to_string(), "b".to_string()],
            related_keys: vec![format!("{key}-rel")],
            scope: Some("project:/x".to_string()),
            created_at: 1_700_000_000,
            updated_at: 1_700_000_100,
            last_accessed_at: 1_700_000_200,
            access_count: 7,
            importance: 0.8,
            status: "active".to_string(),
            embedding: dim.map(|d| (0..d).map(|i| 0.01 * i as f32).collect()),
            embedding_backend: dim.map(|_| "onnx".to_string()),
        }
    }

    #[test]
    fn roundtrip_preserves_all_fields_mixed_dims_and_nulls() {
        let dir = tempdir().unwrap();
        let path = dir.path().join("mem.parquet");
        let rows = vec![
            sample("k384", Some(384)),
            sample("k192", Some(192)),
            // no-embedding row + null scope/backend
            MemoryColumnarRow {
                scope: None,
                embedding: None,
                embedding_backend: None,
                tags: vec![],
                related_keys: vec![],
                ..sample("k-none", None)
            },
        ];
        write_parquet(&path, &rows).unwrap();
        let back = read_parquet(&path).unwrap();
        assert_eq!(back, rows);
        // null list entry must round-trip as None, not Some(vec![])
        assert!(back[2].embedding.is_none());
        assert!(back[2].scope.is_none());
        assert!(back[2].tags.is_empty());
    }

    #[test]
    fn embedding_is_typed_float32_list() {
        let rows = vec![sample("k", Some(4))];
        let batch = rows_to_batch(&rows).unwrap();
        let col = batch
            .column(12)
            .as_any()
            .downcast_ref::<ListArray>()
            .unwrap();
        assert_eq!(col.value_type(), DataType::Float32);
        let v = col.value(0);
        let f = v.as_any().downcast_ref::<Float32Array>().unwrap();
        assert_eq!(f.len(), 4);
        assert!((f.value(1) - 0.01).abs() < 1e-6);
    }

    #[test]
    fn contract_is_embedded_and_readable_from_footer() {
        let dir = tempdir().unwrap();
        let path = dir.path().join("mem.parquet");
        write_parquet(&path, &[sample("k", Some(8))]).unwrap();
        let c = read_contract(&path).unwrap();
        assert_eq!(c.as_deref(), Some(MEMORY_COLUMNAR_SCHEMA_CONTRACT));
    }

    #[test]
    fn parquet_column_chunks_are_zstd_compressed() {
        // The "compressed storage" half of the long-term-library pitch: every
        // column chunk must be written with the ZSTD codec. (Parquet records the
        // codec, not the zstd level, so match only the variant.) This also
        // confirms the parquet `zstd` feature is actually compiled in — without
        // it, write_parquet would error before this read.
        use parquet::basic::Compression;
        let dir = tempdir().unwrap();
        let path = dir.path().join("z.parquet");
        let rows: Vec<MemoryColumnarRow> = (0..64)
            .map(|i| sample(&format!("k{i:03}"), Some(384)))
            .collect();
        write_parquet(&path, &rows).unwrap();
        let file = std::fs::File::open(&path).unwrap();
        let builder = ParquetRecordBatchReaderBuilder::try_new(file).unwrap();
        let md = builder.metadata();
        assert!(md.num_row_groups() >= 1);
        for rg in 0..md.num_row_groups() {
            let rgm = md.row_group(rg);
            for c in 0..rgm.num_columns() {
                assert!(
                    matches!(rgm.column(c).compression(), Compression::ZSTD(_)),
                    "column {c} in row group {rg} is not ZSTD-compressed"
                );
            }
        }
        // and the compressed archive still round-trips bit-exactly
        assert_eq!(read_parquet(&path).unwrap(), rows);
    }

    #[test]
    fn compression_stats_reports_zstd_shrink_on_compressible_data() {
        let dir = tempdir().unwrap();
        let path = dir.path().join("c.parquet");
        // Highly compressible: repeated content prefix + smooth embeddings.
        let rows: Vec<MemoryColumnarRow> = (0..256)
            .map(|i| sample(&format!("k{i:04}"), Some(384)))
            .collect();
        write_parquet(&path, &rows).unwrap();
        let (compressed, uncompressed) = compression_stats(&path).unwrap();
        assert!(compressed > 0 && uncompressed > 0);
        assert!(
            compressed < uncompressed,
            "zstd should shrink column chunks: {uncompressed} -> {compressed}"
        );
    }

    #[test]
    fn read_rejects_mismatched_contract() {
        // A file written with a different (future) contract must be refused.
        let dir = tempdir().unwrap();
        let path = dir.path().join("mem.parquet");
        {
            let file = std::fs::File::create(&path).unwrap();
            let kv = vec![KeyValue {
                key: SCHEMA_CONTRACT_META_KEY.to_string(),
                value: Some("ab.memory_columnar.v2".to_string()),
            }];
            let props = WriterProperties::builder()
                .set_key_value_metadata(Some(kv))
                .build();
            let mut w = ArrowWriter::try_new(file, arrow_schema(), Some(props)).unwrap();
            w.write(&rows_to_batch(&[sample("k", Some(4))]).unwrap())
                .unwrap();
            w.close().unwrap();
        }
        let err = read_parquet(&path).unwrap_err();
        assert!(matches!(err, MemoryColumnarError::Contract { .. }));
    }

    #[test]
    fn fingerprint_is_deterministic_and_field_sensitive() {
        let a = sample("k", Some(4));
        let b = sample("k", Some(4));
        assert_eq!(fingerprint(&a), fingerprint(&b));

        // embedding present vs absent must differ
        let mut c = sample("k", Some(4));
        c.embedding = None;
        assert_ne!(fingerprint(&a), fingerprint(&c));

        // empty embedding vs absent embedding must differ (null ≠ empty)
        let mut d = sample("k", Some(4));
        d.embedding = Some(vec![]);
        assert_ne!(fingerprint(&c), fingerprint(&d));

        // different content → different fp
        let mut e = sample("k", Some(4));
        e.content = "other".to_string();
        assert_ne!(fingerprint(&a), fingerprint(&e));
    }

    #[test]
    fn summarize_reports_dims_and_footprint() {
        let rows = vec![
            sample("a", Some(384)),
            sample("b", Some(384)),
            sample("c", Some(192)),
            MemoryColumnarRow {
                embedding: None,
                ..sample("d", None)
            },
        ];
        let f = summarize(&rows);
        assert_eq!(f.rows, 4);
        assert_eq!(f.rows_with_embedding, 3);
        assert_eq!(f.embedding_dims, vec![192, 384]);
        assert_eq!(f.total_embedding_floats, 384 + 384 + 192);
        assert_eq!(f.f32_embedding_bytes, (384 + 384 + 192) * 4);
    }

    #[test]
    fn read_missing_file_returns_empty() {
        let dir = tempdir().unwrap();
        let back = read_parquet(&dir.path().join("nope.parquet")).unwrap();
        assert!(back.is_empty());
    }

    #[test]
    fn empty_rows_write_read_roundtrip() {
        let dir = tempdir().unwrap();
        let path = dir.path().join("empty.parquet");
        write_parquet(&path, &[]).unwrap();
        // contract still present on an empty file
        assert_eq!(
            read_contract(&path).unwrap().as_deref(),
            Some(MEMORY_COLUMNAR_SCHEMA_CONTRACT)
        );
        assert!(read_parquet(&path).unwrap().is_empty());
    }

    #[test]
    fn arrow_schema_is_stable() {
        // Lock the column set: any change forces a contract bump conversation.
        let s = arrow_schema();
        let names: Vec<&str> = s.fields().iter().map(|f| f.name().as_str()).collect();
        assert_eq!(
            names,
            vec![
                "key",
                "kind",
                "content",
                "tags",
                "related_keys",
                "scope",
                "created_at",
                "updated_at",
                "last_accessed_at",
                "access_count",
                "importance",
                "status",
                "embedding",
                "embedding_backend",
            ]
        );
        assert_eq!(
            s.metadata()
                .get(SCHEMA_CONTRACT_META_KEY)
                .map(|s| s.as_str()),
            Some(MEMORY_COLUMNAR_SCHEMA_CONTRACT)
        );
    }

    #[test]
    fn fingerprint_is_byte_canonical_for_nan_and_signed_zero() {
        // NaN: fingerprint stays deterministic for a fixed bit pattern, even
        // though derived PartialEq calls two NaN-bearing rows unequal.
        let mut a = sample("k", Some(3));
        a.embedding = Some(vec![f32::NAN, 1.0, 2.0]);
        let mut b = sample("k", Some(3));
        b.embedding = Some(vec![f32::NAN, 1.0, 2.0]);
        assert_eq!(fingerprint(&a), fingerprint(&b)); // NaN-stable
        assert_ne!(a, b); // ...while PartialEq disagrees (NaN != NaN)

        // -0.0 vs +0.0: PartialEq-equal but byte-distinct → different fingerprints.
        let mut p = sample("k", Some(1));
        p.embedding = Some(vec![0.0f32]);
        let mut m = sample("k", Some(1));
        m.embedding = Some(vec![-0.0f32]);
        assert_eq!(p, m); // PartialEq: -0.0 == +0.0
        assert_ne!(fingerprint(&p), fingerprint(&m)); // fingerprint is byte-canonical
    }

    #[test]
    fn multi_batch_roundtrip_preserves_order_over_1024_boundary() {
        // arrow's ParquetRecordBatchReader yields ~1024-row batches; write
        // >2 batches' worth and assert read_parquet stitches them back in
        // order, exercising the cross-batch `rows.extend` path.
        let dir = tempdir().unwrap();
        let path = dir.path().join("big.parquet");
        let n = 2500usize;
        let rows: Vec<MemoryColumnarRow> = (0..n)
            .map(|i| {
                // vary null vs present + dim so both list paths span batches
                let dim = if i % 7 == 0 { None } else { Some((i % 5) + 1) };
                sample(&format!("k{i:04}"), dim)
            })
            .collect();
        write_parquet(&path, &rows).unwrap();
        let back = read_parquet(&path).unwrap();
        assert_eq!(back.len(), n);
        assert_eq!(back, rows);
        assert_eq!(back[1500].key, "k1500"); // a row well past the first batch
    }
}
