//! v22 Phase 2.2 — substrate snapshot (Parquet, multi-cadence per §3.4).
//!
//! Two cadence tiers per memo §3.4:
//! - **Hot**: every [`HOT_EVERY_N_STEPS`] events; cheap row, omits the
//!   N×(N-1) connection_logits flat (~1 KB / row).
//! - **Long**: every [`LONG_EVERY_N_STEPS`] events OR every
//!   [`LONG_FLOOR_SECS`] seconds, whichever fires first; full row incl.
//!   connection_logits (~260 KB / row at N=256).
//!
//! Rotation: keep at most [`MAX_SNAPSHOTS`] rows. Rewrite-on-flush
//! (file is rewritten end-to-end each append); at ~7 snapshots/day this is
//! ~26 MB worst-case I/O / day, well under the §3.3 envelope.
//!
//! Snapshot SHA256 fingerprint serves as the cross-machine equivalence
//! check per §3.4 + P5.

use std::collections::HashMap;
use std::path::{Path, PathBuf};
use std::sync::Arc;

use arrow::array::{
    Array, Float32Array, Int32Array, Int64Array, ListArray, ListBuilder,
    Float32Builder, Int64Builder, StringArray, StringBuilder,
};
use arrow::datatypes::{DataType, Field, Schema};
use arrow::record_batch::RecordBatch;
use parquet::arrow::arrow_reader::ParquetRecordBatchReaderBuilder;
use parquet::arrow::ArrowWriter;
use parquet::file::properties::WriterProperties;
use parquet::format::KeyValue;
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};

/// Hot-tier cadence (events).
pub const HOT_EVERY_N_STEPS: u64 = 20;
/// Long-tier cadence (events).
pub const LONG_EVERY_N_STEPS: u64 = 100;
/// Long-tier wall-clock floor (seconds). 6 hours per memo §3.4.
pub const LONG_FLOOR_SECS: i64 = 6 * 3600;
/// Trailing-surprise short window (events) per memo §3.4 `trailing_surprise_mean_short`.
pub const SHORT_WINDOW: usize = 100;
/// Trailing-surprise long window (events) per memo §3.4 `trailing_surprise_mean_long`.
pub const LONG_WINDOW: usize = 1000;
/// Rotation cap — keep at most this many rows in the file.
pub const MAX_SNAPSHOTS: usize = 100;

/// Schema-contract version (nexus-style; mirrors `ab-memory-columnar`'s
/// `ab.memory_columnar.v1`). Embedded in BOTH the Arrow schema metadata and the
/// Parquet footer KV so a reader can detect schema drift before decoding a
/// single row group. Bump the **major** (`vN`) on any incompatible column-set
/// or encoding change. `v1` is the first *explicit* contract: pre-contract
/// substrate.parquet files carry no contract key and are accepted as legacy
/// (their 10-field schema is structurally identical to v1).
pub const SUBSTRATE_SNAPSHOT_SCHEMA_CONTRACT: &str = "ab.substrate_snapshot.v1";
/// Metadata key under which [`SUBSTRATE_SNAPSHOT_SCHEMA_CONTRACT`] is written.
pub const SCHEMA_CONTRACT_META_KEY: &str = "ab.schema_contract";
/// Metadata key recording the snapshot provenance.
pub const PROVENANCE_META_KEY: &str = "ab.provenance";
/// Human-readable provenance written into the file metadata.
pub const PROVENANCE: &str =
    "agent-bridge seed substrate snapshot (Parquet, multi-cadence per memo §3.4)";

/// Default substrate.parquet path: `$HOME/.local/share/agent-bridge/substrate.parquet`.
/// Returns `None` if `$HOME` is unset.
pub fn default_snapshot_path() -> Option<PathBuf> {
    std::env::var("HOME")
        .ok()
        .map(|h| PathBuf::from(h).join(".local/share/agent-bridge/substrate.parquet"))
}

/// Snapshot cadence tier.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum SnapshotTier {
    Hot,
    Long,
}

impl SnapshotTier {
    pub fn as_str(self) -> &'static str {
        match self {
            Self::Hot => "hot",
            Self::Long => "long",
        }
    }
    pub fn from_str(s: &str) -> Option<Self> {
        match s {
            "hot" => Some(Self::Hot),
            "long" => Some(Self::Long),
            _ => None,
        }
    }
}

/// One row of `substrate.parquet`. Matches §3.4 schema with one
/// pragmatic deviation: `connection_logits` is always present as a list,
/// empty for Hot rows. This lets the Arrow schema stay non-nullable and
/// avoids a per-row Option dance — the tier column is the source of truth
/// for "this row has logits or not".
#[derive(Debug, Clone, PartialEq)]
pub struct SnapshotRow {
    /// Substrate step count at snapshot time.
    pub step: i64,
    /// Unix seconds at snapshot time.
    pub cycle_ts: i64,
    /// Cadence tier.
    pub tier: SnapshotTier,
    /// Live neuron count (Phase 1 = N constant; phase 4 spawn/death will diverge).
    pub n_alive: i32,
    /// Per-neuron in-strength (Hebbian incoming weight magnitude). Length N.
    pub in_strengths: Vec<f32>,
    /// Per-neuron last perceived memory key. Length N. Empty string = never.
    pub last_perceived_key: Vec<String>,
    /// Per-neuron last perceived unix seconds. Length N. 0 = never.
    pub last_perceived_ts: Vec<i64>,
    /// Mean surprise over last [`SHORT_WINDOW`] events.
    pub trailing_surprise_mean_short: f32,
    /// Mean surprise over last [`LONG_WINDOW`] events.
    pub trailing_surprise_mean_long: f32,
    /// Flat N×(N-1) connection_logits, row-major skipping diagonal.
    /// Empty for [`SnapshotTier::Hot`] rows.
    pub connection_logits: Vec<f32>,
}

/// Arrow schema matching [`SnapshotRow`]. The schema metadata carries the
/// contract version + provenance (mirrors `ab-memory-columnar`). **Stable
/// across releases** — any column-set change here must bump
/// [`SUBSTRATE_SNAPSHOT_SCHEMA_CONTRACT`]; the `arrow_schema_is_stable` test
/// locks the column set.
pub fn arrow_schema() -> Arc<Schema> {
    let mut meta = HashMap::new();
    meta.insert(
        SCHEMA_CONTRACT_META_KEY.to_string(),
        SUBSTRATE_SNAPSHOT_SCHEMA_CONTRACT.to_string(),
    );
    meta.insert(PROVENANCE_META_KEY.to_string(), PROVENANCE.to_string());
    Arc::new(Schema::new_with_metadata(
        vec![
            Field::new("step", DataType::Int64, false),
        Field::new("cycle_ts", DataType::Int64, false),
        Field::new("tier", DataType::Utf8, false),
        Field::new("n_alive", DataType::Int32, false),
        Field::new(
            "in_strengths",
            DataType::List(Arc::new(Field::new("item", DataType::Float32, true))),
            false,
        ),
        Field::new(
            "last_perceived_key",
            DataType::List(Arc::new(Field::new("item", DataType::Utf8, true))),
            false,
        ),
        Field::new(
            "last_perceived_ts",
            DataType::List(Arc::new(Field::new("item", DataType::Int64, true))),
            false,
        ),
        Field::new("trailing_surprise_mean_short", DataType::Float32, false),
        Field::new("trailing_surprise_mean_long", DataType::Float32, false),
        Field::new(
            "connection_logits",
            DataType::List(Arc::new(Field::new("item", DataType::Float32, true))),
            false,
        ),
        ],
        meta,
    ))
}

/// Build a [`RecordBatch`] from a slice of rows.
pub fn rows_to_batch(rows: &[SnapshotRow]) -> Result<RecordBatch, arrow::error::ArrowError> {
    let schema = arrow_schema();
    let step: Int64Array = rows.iter().map(|r| Some(r.step)).collect();
    let cycle_ts: Int64Array = rows.iter().map(|r| Some(r.cycle_ts)).collect();
    let tier: StringArray = rows.iter().map(|r| Some(r.tier.as_str())).collect();
    let n_alive: Int32Array = rows.iter().map(|r| Some(r.n_alive)).collect();
    let trailing_short: Float32Array = rows
        .iter()
        .map(|r| Some(r.trailing_surprise_mean_short))
        .collect();
    let trailing_long: Float32Array = rows
        .iter()
        .map(|r| Some(r.trailing_surprise_mean_long))
        .collect();

    let in_strengths = build_f32_list(rows.iter().map(|r| r.in_strengths.as_slice()));
    let last_key = build_str_list(rows.iter().map(|r| r.last_perceived_key.as_slice()));
    let last_ts = build_i64_list(rows.iter().map(|r| r.last_perceived_ts.as_slice()));
    let conn = build_f32_list(rows.iter().map(|r| r.connection_logits.as_slice()));

    RecordBatch::try_new(
        schema,
        vec![
            Arc::new(step),
            Arc::new(cycle_ts),
            Arc::new(tier),
            Arc::new(n_alive),
            Arc::new(in_strengths),
            Arc::new(last_key),
            Arc::new(last_ts),
            Arc::new(trailing_short),
            Arc::new(trailing_long),
            Arc::new(conn),
        ],
    )
}

fn build_f32_list<'a, I: Iterator<Item = &'a [f32]>>(iter: I) -> ListArray {
    let mut builder = ListBuilder::new(Float32Builder::new());
    for slice in iter {
        for &v in slice {
            builder.values().append_value(v);
        }
        builder.append(true);
    }
    builder.finish()
}

fn build_i64_list<'a, I: Iterator<Item = &'a [i64]>>(iter: I) -> ListArray {
    let mut builder = ListBuilder::new(Int64Builder::new());
    for slice in iter {
        for &v in slice {
            builder.values().append_value(v);
        }
        builder.append(true);
    }
    builder.finish()
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

/// Decode rows from a [`RecordBatch`]. Inverse of [`rows_to_batch`].
pub fn batch_to_rows(batch: &RecordBatch) -> Result<Vec<SnapshotRow>, arrow::error::ArrowError> {
    let n = batch.num_rows();
    let step = batch
        .column(0)
        .as_any()
        .downcast_ref::<Int64Array>()
        .ok_or_else(|| arrow::error::ArrowError::CastError("step".into()))?;
    let cycle_ts = batch
        .column(1)
        .as_any()
        .downcast_ref::<Int64Array>()
        .ok_or_else(|| arrow::error::ArrowError::CastError("cycle_ts".into()))?;
    let tier = batch
        .column(2)
        .as_any()
        .downcast_ref::<StringArray>()
        .ok_or_else(|| arrow::error::ArrowError::CastError("tier".into()))?;
    let n_alive = batch
        .column(3)
        .as_any()
        .downcast_ref::<Int32Array>()
        .ok_or_else(|| arrow::error::ArrowError::CastError("n_alive".into()))?;
    let in_strengths = batch
        .column(4)
        .as_any()
        .downcast_ref::<ListArray>()
        .ok_or_else(|| arrow::error::ArrowError::CastError("in_strengths".into()))?;
    let last_key = batch
        .column(5)
        .as_any()
        .downcast_ref::<ListArray>()
        .ok_or_else(|| arrow::error::ArrowError::CastError("last_perceived_key".into()))?;
    let last_ts = batch
        .column(6)
        .as_any()
        .downcast_ref::<ListArray>()
        .ok_or_else(|| arrow::error::ArrowError::CastError("last_perceived_ts".into()))?;
    let trailing_short = batch
        .column(7)
        .as_any()
        .downcast_ref::<Float32Array>()
        .ok_or_else(|| arrow::error::ArrowError::CastError("trailing_surprise_mean_short".into()))?;
    let trailing_long = batch
        .column(8)
        .as_any()
        .downcast_ref::<Float32Array>()
        .ok_or_else(|| arrow::error::ArrowError::CastError("trailing_surprise_mean_long".into()))?;
    let conn = batch
        .column(9)
        .as_any()
        .downcast_ref::<ListArray>()
        .ok_or_else(|| arrow::error::ArrowError::CastError("connection_logits".into()))?;

    let mut out = Vec::with_capacity(n);
    for i in 0..n {
        let tier_str = tier.value(i);
        let tier_enum = SnapshotTier::from_str(tier_str).ok_or_else(|| {
            arrow::error::ArrowError::ParseError(format!("unknown tier '{tier_str}'"))
        })?;
        let row = SnapshotRow {
            step: step.value(i),
            cycle_ts: cycle_ts.value(i),
            tier: tier_enum,
            n_alive: n_alive.value(i),
            in_strengths: extract_f32_list(in_strengths, i),
            last_perceived_key: extract_str_list(last_key, i),
            last_perceived_ts: extract_i64_list(last_ts, i),
            trailing_surprise_mean_short: trailing_short.value(i),
            trailing_surprise_mean_long: trailing_long.value(i),
            connection_logits: extract_f32_list(conn, i),
        };
        out.push(row);
    }
    Ok(out)
}

fn extract_f32_list(arr: &ListArray, i: usize) -> Vec<f32> {
    let v = arr.value(i);
    let f = v
        .as_any()
        .downcast_ref::<Float32Array>()
        .expect("float32 list");
    (0..f.len()).map(|k| f.value(k)).collect()
}

fn extract_i64_list(arr: &ListArray, i: usize) -> Vec<i64> {
    let v = arr.value(i);
    let f = v.as_any().downcast_ref::<Int64Array>().expect("int64 list");
    (0..f.len()).map(|k| f.value(k)).collect()
}

fn extract_str_list(arr: &ListArray, i: usize) -> Vec<String> {
    let v = arr.value(i);
    let f = v
        .as_any()
        .downcast_ref::<StringArray>()
        .expect("string list");
    (0..f.len()).map(|k| f.value(k).to_string()).collect()
}

/// Read all rows from an existing snapshot file. Returns empty Vec if the
/// file doesn't exist; bubbles other IO/parquet errors.
pub fn read_all(path: &Path) -> Result<Vec<SnapshotRow>, SnapshotError> {
    if !path.exists() {
        return Ok(Vec::new());
    }
    let file = std::fs::File::open(path)?;
    let builder = ParquetRecordBatchReaderBuilder::try_new(file)?;
    // Detect schema drift before decoding (legacy files without a contract key
    // are accepted as v1; only an explicit version mismatch is refused).
    verify_contract(builder.metadata().file_metadata().key_value_metadata())?;
    let reader = builder.build()?;
    let mut rows = Vec::new();
    for batch in reader {
        let batch = batch?;
        rows.extend(batch_to_rows(&batch)?);
    }
    Ok(rows)
}

/// Read the schema-contract version from a snapshot's Parquet footer without
/// decoding any row groups. `None` for a legacy (pre-contract) file.
pub fn read_contract(path: &Path) -> Result<Option<String>, SnapshotError> {
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

/// Verify the embedded schema contract before decoding row groups. Tolerant of
/// LEGACY files: a substrate.parquet written before the contract existed has no
/// contract key — its 10-field schema is structurally identical to v1, so it is
/// accepted (the f32 source of truth is unchanged). Only an EXPLICIT, different
/// `vN` is refused, so a v1 reader never silently mis-decodes a future v2 file.
fn verify_contract(kvs: Option<&Vec<KeyValue>>) -> Result<(), SnapshotError> {
    let found = kvs.and_then(|kvs| {
        kvs.iter()
            .find(|kv| kv.key == SCHEMA_CONTRACT_META_KEY)
            .and_then(|kv| kv.value.clone())
    });
    match found {
        Some(v) if v == SUBSTRATE_SNAPSHOT_SCHEMA_CONTRACT => Ok(()),
        // Legacy pre-contract file: structurally v1, accept.
        None => Ok(()),
        // Explicit, different version: refuse rather than mis-decode.
        Some(v) => Err(SnapshotError::Contract {
            expected: SUBSTRATE_SNAPSHOT_SCHEMA_CONTRACT,
            found: v,
        }),
    }
}

/// Write all rows to the file, overwriting any prior contents. Creates
/// parent directories as needed. Atomic via tmp+rename so a crash mid-write
/// can't truncate the prior snapshot.
pub fn write_all(path: &Path, rows: &[SnapshotRow]) -> Result<(), SnapshotError> {
    if let Some(parent) = path.parent() {
        std::fs::create_dir_all(parent)?;
    }
    let tmp = path.with_extension("parquet.tmp");
    {
        let file = std::fs::File::create(&tmp)?;
        let props = WriterProperties::builder()
            .set_key_value_metadata(Some(vec![
                KeyValue {
                    key: SCHEMA_CONTRACT_META_KEY.to_string(),
                    value: Some(SUBSTRATE_SNAPSHOT_SCHEMA_CONTRACT.to_string()),
                },
                KeyValue {
                    key: PROVENANCE_META_KEY.to_string(),
                    value: Some(PROVENANCE.to_string()),
                },
            ]))
            .build();
        let mut writer = ArrowWriter::try_new(file, arrow_schema(), Some(props))?;
        if !rows.is_empty() {
            let batch = rows_to_batch(rows)?;
            writer.write(&batch)?;
        }
        writer.close()?;
    }
    std::fs::rename(&tmp, path)?;
    Ok(())
}

/// Append one row, applying rotation (rows beyond [`MAX_SNAPSHOTS`] from the
/// front are dropped). Returns the SHA256 fingerprint of the appended row.
pub fn append_row(path: &Path, row: SnapshotRow) -> Result<String, SnapshotError> {
    let mut rows = read_all(path).unwrap_or_default();
    let fp = fingerprint(&row);
    rows.push(row);
    while rows.len() > MAX_SNAPSHOTS {
        rows.remove(0);
    }
    write_all(path, &rows)?;
    Ok(fp)
}

/// SHA256 fingerprint of a single row in a deterministic canonical form.
/// Used as cross-machine equivalence check per §3.4 + P5.
pub fn fingerprint(row: &SnapshotRow) -> String {
    let mut h = Sha256::new();
    h.update(row.step.to_le_bytes());
    h.update(row.cycle_ts.to_le_bytes());
    h.update(row.tier.as_str().as_bytes());
    h.update(row.n_alive.to_le_bytes());
    for v in &row.in_strengths {
        h.update(v.to_le_bytes());
    }
    for s in &row.last_perceived_key {
        h.update((s.len() as u32).to_le_bytes());
        h.update(s.as_bytes());
    }
    for v in &row.last_perceived_ts {
        h.update(v.to_le_bytes());
    }
    h.update(row.trailing_surprise_mean_short.to_le_bytes());
    h.update(row.trailing_surprise_mean_long.to_le_bytes());
    for v in &row.connection_logits {
        h.update(v.to_le_bytes());
    }
    let digest = h.finalize();
    let mut out = String::with_capacity(64);
    for b in digest {
        out.push_str(&format!("{:02x}", b));
    }
    out
}

/// Hot-cadence predicate. Fires on non-zero multiples of [`HOT_EVERY_N_STEPS`].
pub fn should_write_hot(step: u64) -> bool {
    step > 0 && step % HOT_EVERY_N_STEPS == 0
}

/// Long-cadence predicate. Fires on (a) non-zero multiples of
/// [`LONG_EVERY_N_STEPS`], or (b) wall-clock distance from `last_long_ts`
/// ≥ [`LONG_FLOOR_SECS`].
pub fn should_write_long(step: u64, last_long_ts: i64, now: i64) -> bool {
    if step > 0 && step % LONG_EVERY_N_STEPS == 0 {
        return true;
    }
    if last_long_ts > 0 && now - last_long_ts >= LONG_FLOOR_SECS {
        return true;
    }
    false
}

/// Snapshot module errors.
#[derive(Debug, thiserror::Error)]
pub enum SnapshotError {
    #[error("snapshot IO error: {0}")]
    Io(#[from] std::io::Error),
    #[error("snapshot arrow error: {0}")]
    Arrow(#[from] arrow::error::ArrowError),
    #[error("snapshot parquet error: {0}")]
    Parquet(#[from] parquet::errors::ParquetError),
    #[error("snapshot schema-contract mismatch: expected {expected}, found {found}")]
    Contract {
        expected: &'static str,
        found: String,
    },
}

// thiserror is a sibling-of-anyhow lightweight derive; we need it pulled
// from workspace. It's already in `workspace.dependencies` via the agent-
// bridge root Cargo.toml.

#[cfg(test)]
mod tests {
    use super::*;
    use tempfile::tempdir;

    fn sample_row(step: i64, tier: SnapshotTier, n: usize) -> SnapshotRow {
        let in_strengths = (0..n).map(|i| 0.1 + i as f32 * 0.01).collect();
        let last_perceived_key = (0..n).map(|i| format!("key-{i}")).collect();
        let last_perceived_ts = (0..n).map(|i| 1700000000 + i as i64).collect();
        let connection_logits = if matches!(tier, SnapshotTier::Long) {
            (0..n * (n - 1)).map(|i| (i as f32) * 0.001).collect()
        } else {
            Vec::new()
        };
        SnapshotRow {
            step,
            cycle_ts: 1700000000 + step,
            tier,
            n_alive: n as i32,
            in_strengths,
            last_perceived_key,
            last_perceived_ts,
            trailing_surprise_mean_short: 0.42,
            trailing_surprise_mean_long: 0.31,
            connection_logits,
        }
    }

    #[test]
    fn cadence_hot_fires_on_multiples_of_20() {
        assert!(!should_write_hot(0));
        assert!(!should_write_hot(1));
        assert!(!should_write_hot(19));
        assert!(should_write_hot(20));
        assert!(!should_write_hot(21));
        assert!(should_write_hot(40));
        assert!(should_write_hot(100));
    }

    #[test]
    fn cadence_long_fires_on_count_or_wallclock() {
        // by event count
        assert!(!should_write_long(50, 1000, 5000));
        assert!(should_write_long(100, 1000, 5000));
        assert!(should_write_long(200, 0, 0));

        // by wall-clock (6h = 21600s)
        let now = 100000;
        assert!(!should_write_long(50, now - 21599, now));
        assert!(should_write_long(50, now - 21600, now));

        // last_long_ts==0 (no prior long) does NOT auto-fire on wallclock;
        // it must wait for an event-count fire to bootstrap.
        assert!(!should_write_long(1, 0, 99999999));
    }

    #[test]
    fn roundtrip_long_row_preserves_all_fields() {
        // Schema correctness: write → read → equal.
        let dir = tempdir().unwrap();
        let path = dir.path().join("substrate.parquet");
        let row = sample_row(100, SnapshotTier::Long, 4);
        let fp = append_row(&path, row.clone()).unwrap();
        assert_eq!(fp.len(), 64);
        let back = read_all(&path).unwrap();
        assert_eq!(back.len(), 1);
        assert_eq!(back[0], row);
        // connection_logits should be N×(N-1) = 12 entries for n=4.
        assert_eq!(back[0].connection_logits.len(), 12);
    }

    #[test]
    fn hot_row_omits_connection_logits() {
        let dir = tempdir().unwrap();
        let path = dir.path().join("substrate.parquet");
        let row = sample_row(20, SnapshotTier::Hot, 8);
        append_row(&path, row.clone()).unwrap();
        let back = read_all(&path).unwrap();
        assert_eq!(back.len(), 1);
        assert_eq!(back[0].tier, SnapshotTier::Hot);
        assert!(back[0].connection_logits.is_empty());
        // Hot tier still carries in_strengths + last_perceived (cheap).
        assert_eq!(back[0].in_strengths.len(), 8);
        assert_eq!(back[0].last_perceived_key.len(), 8);
    }

    #[test]
    fn append_grows_then_rotates_at_max() {
        // Push MAX_SNAPSHOTS+5 rows; expect file to settle at MAX_SNAPSHOTS,
        // with the oldest rows pruned (front-drop).
        let dir = tempdir().unwrap();
        let path = dir.path().join("substrate.parquet");
        let extra = 5;
        for i in 0..(MAX_SNAPSHOTS + extra) {
            let row = sample_row(i as i64, SnapshotTier::Hot, 2);
            append_row(&path, row).unwrap();
        }
        let back = read_all(&path).unwrap();
        assert_eq!(back.len(), MAX_SNAPSHOTS);
        // The oldest surviving row should have step == extra (front-dropped).
        assert_eq!(back[0].step, extra as i64);
        assert_eq!(back[MAX_SNAPSHOTS - 1].step, (MAX_SNAPSHOTS + extra - 1) as i64);
    }

    #[test]
    fn fingerprint_is_deterministic_and_field_sensitive() {
        let row1 = sample_row(42, SnapshotTier::Long, 3);
        let row2 = sample_row(42, SnapshotTier::Long, 3);
        assert_eq!(fingerprint(&row1), fingerprint(&row2));

        // Same shape, different step → different fp.
        let row3 = sample_row(43, SnapshotTier::Long, 3);
        assert_ne!(fingerprint(&row1), fingerprint(&row3));

        // Same step, different tier → different fp (Hot has empty logits).
        let row4 = sample_row(42, SnapshotTier::Hot, 3);
        assert_ne!(fingerprint(&row1), fingerprint(&row4));
    }

    #[test]
    fn read_all_on_missing_file_returns_empty() {
        let dir = tempdir().unwrap();
        let path = dir.path().join("does-not-exist.parquet");
        let back = read_all(&path).unwrap();
        assert!(back.is_empty());
    }

    #[test]
    fn arrow_schema_is_stable() {
        // Lock the schema: any unintended change breaks this test, forcing a
        // bump of SUBSTRATE_SNAPSHOT_SCHEMA_CONTRACT.
        let s = arrow_schema();
        assert_eq!(s.fields().len(), 10);
        assert_eq!(s.field(0).name(), "step");
        assert_eq!(s.field(1).name(), "cycle_ts");
        assert_eq!(s.field(2).name(), "tier");
        assert_eq!(s.field(3).name(), "n_alive");
        assert_eq!(s.field(4).name(), "in_strengths");
        assert_eq!(s.field(5).name(), "last_perceived_key");
        assert_eq!(s.field(6).name(), "last_perceived_ts");
        assert_eq!(s.field(7).name(), "trailing_surprise_mean_short");
        assert_eq!(s.field(8).name(), "trailing_surprise_mean_long");
        assert_eq!(s.field(9).name(), "connection_logits");
        // The schema metadata carries the explicit contract version + provenance.
        assert_eq!(
            s.metadata().get(SCHEMA_CONTRACT_META_KEY).map(String::as_str),
            Some(SUBSTRATE_SNAPSHOT_SCHEMA_CONTRACT)
        );
        assert!(s.metadata().contains_key(PROVENANCE_META_KEY));
    }

    #[test]
    fn written_file_carries_schema_contract() {
        let dir = tempdir().unwrap();
        let path = dir.path().join("substrate.parquet");
        append_row(&path, sample_row(1, SnapshotTier::Hot, 3)).unwrap();
        // Footer-readable contract without decoding rows.
        assert_eq!(
            read_contract(&path).unwrap().as_deref(),
            Some(SUBSTRATE_SNAPSHOT_SCHEMA_CONTRACT)
        );
        // read_all (which calls verify_contract) still round-trips.
        assert_eq!(read_all(&path).unwrap().len(), 1);
    }

    #[test]
    fn verify_contract_accepts_current_and_legacy_rejects_mismatch() {
        // Current version → Ok.
        let current = vec![parquet::format::KeyValue {
            key: SCHEMA_CONTRACT_META_KEY.to_string(),
            value: Some(SUBSTRATE_SNAPSHOT_SCHEMA_CONTRACT.to_string()),
        }];
        assert!(verify_contract(Some(&current)).is_ok());

        // Legacy file: no KV at all, or contract key absent among others → Ok.
        assert!(verify_contract(None).is_ok());
        let other_only = vec![parquet::format::KeyValue {
            key: PROVENANCE_META_KEY.to_string(),
            value: Some("x".to_string()),
        }];
        assert!(verify_contract(Some(&other_only)).is_ok());

        // Explicit different version → refused (no silent mis-decode).
        let future = vec![parquet::format::KeyValue {
            key: SCHEMA_CONTRACT_META_KEY.to_string(),
            value: Some("ab.substrate_snapshot.v2".to_string()),
        }];
        assert!(matches!(
            verify_contract(Some(&future)).unwrap_err(),
            SnapshotError::Contract { .. }
        ));
    }

    #[test]
    fn default_snapshot_path_is_under_local_share() {
        // We can't assume HOME but at minimum the suffix is stable.
        if let Some(p) = default_snapshot_path() {
            let s = p.to_string_lossy().to_string();
            assert!(s.ends_with("/.local/share/agent-bridge/substrate.parquet"));
        }
    }
}
