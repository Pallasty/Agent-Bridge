# ab-memory-columnar

Read-only **columnar (Arrow/Parquet) archive** of the agent-bridge `memories`
table — the "long-term memory library" surface.

It projects each `memories` row into a typed columnar layout where the
embedding is a real Arrow `List<Float32>` (not an opaque BLOB), alongside the
cognitive metadata (kind, tags, scope, importance, status, lifecycle
timestamps), behind a **versioned schema contract**.

## Provenance (CascadeProjects scan 2026-06-28, borrow T5)

- **AQFH 技术实现规范** — "Arrow记忆引擎: Parquet存储 / Arrow缓存 / Flight传输"
  as the durable substrate of memory reload.
- **`Neon与Arrow+Parquet的记忆模型类比分析`** — Arrow+Parquet as the
  *long-term memory library* (大容量 / 组织化归档 / 压缩存储 / 持久保存),
  complementary to the live SQLite "working memory".

## Design

- **DB-agnostic codec** (`src/lib.rs`): `MemoryColumnarRow` + `arrow_schema()` +
  `rows_to_batch`/`batch_to_rows` + `write_parquet`/`read_parquet` +
  `fingerprint` + `summarize`. No SQLite dependency; fully unit-tested.
- **Read-only export** (`examples/memory_columnar_export.rs`): opens the live DB
  `SQLITE_OPEN_READ_ONLY`, decodes embeddings via `ab_store::decode_embedding`,
  writes a Parquet archive. The DB is never written — the f32 BLOBs stay the
  source of truth. Mirrors the read-only discipline of ab-store's
  `quant_drift_eval`.
- **Schema contract** `ab.memory_columnar.v1` is written into both the Arrow
  schema metadata and (footer-readable) the Parquet key-value metadata; readers
  reject an incompatible file without decoding it. Bump the major when the
  column set changes (locked by the `arrow_schema_is_stable` test).
- **`fingerprint`** is byte-canonical (NaN-stable, distinguishes ±0.0) — the
  cross-machine equivalence check, stricter than the row's derived `PartialEq`.

## Status: no runtime consumer yet

This crate currently has **no active consumer** in the agent-bridge runtime —
the export example is its sole driver, and `arrow`/`parquet` are intentionally
contained to this one crate (ab-store and the active BioCortex path are
untouched). It is a standalone shadow/archival surface. A future consumer would
likely be Arrow-native analytics over the archive, or a cross-machine
diff/equivalence check keyed on `fingerprint`.

## Run

```bash
cargo run -p ab-memory-columnar --example memory_columnar_export [DB_PATH] [OUT_PARQUET]
# DB_PATH      defaults to ab_store::default_db_path()
# OUT_PARQUET  defaults to $HOME/.local/share/agent-bridge/memories_columnar.parquet
```

Validation:

```bash
cargo test  -p ab-memory-columnar
cargo clippy -p ab-memory-columnar --lib -- -D warnings
```
