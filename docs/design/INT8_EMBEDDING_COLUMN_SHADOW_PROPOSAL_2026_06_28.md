> `docs/design/INT8_EMBEDDING_COLUMN_SHADOW_PROPOSAL_2026_06_28.md` — **PROPOSE-ONLY — not implemented; owner sign-off + lswr ladder required for any schema change.**

## 0. Status

> **PROPOSE-ONLY — NOT IMPLEMENTED — OWNER-GATED — REQUIRES lswr ADMISSION LADDER**
>
> This document proposes a future additive `v37` schema column. It does **not** change the schema, the store, or any runtime path. No code lands from this artifact. Advancing past PROPOSE requires the lswr outcome-admission ladder **and** explicit human owner sign-off (§8), even if every gate in §5 is green.

- **Author:** `claude-opus-4.8` (Data session, `borrowed-patterns` campaign), drafted for the Agent-Bridge memory-area owner's review. Grounded by 3 read-only code-survey agents + 3 adversarial review lenses (§11).
- **Date:** 2026-06-28.
- **Current max schema version:** `v36` (`crates/store/src/sqlite.rs:1437`, confirmed against the in-tree ladder). This proposal would introduce `v37` *only after* admission — `v37` does **not** exist yet.
- **What this artifact IS:** a written design + rollout + gate-threshold proposal for an *additive, shadow* INT8 embedding column, following the project's established read-only shadow-campaign discipline (boundary statements, a gate doc with numeric thresholds, "do not add to the runtime path yet", and a mandatory human review even when metrics pass).
- **What this artifact is NOT:**
  - It is **not** a schema change. The `v37` migration block is *described* here, not committed. The migration ladder in `sqlite.rs` is untouched.
  - It is **not** a retrieval-behavior change. The f32 `embedding` BLOB stays the source of truth (`crates/store/src/vector.rs` `encode_embedding`/`decode_embedding`) through all of Phases A and B.
  - It is **not** an autonomous mutation. Nothing here authorizes an agent to run a migration; the admission ladder + owner sign-off are prerequisites, not formalities.
  - It is **not** the sibling substrate step (§9), which is sequenced separately and explicitly out of scope for THIS proposal.

### 0.1 Provenance honesty note (folded-in correction)

Headline numbers (`recall@10 = 0.9966`, `mean cosine = 0.99996`) were recorded during the T2/ArrowQuant borrow in the **live Agent-Bridge forum** (borrowed-patterns kanban thread #102, posts #2577/#2583) and the session decision memories. Those are **runtime artifacts of the forum / decision-memory databases, not part of this repository's source tree** — a future reader of this committed doc cannot verify them from the repo alone (a source grep returns zero hits, by design: the forum is a DB, not a checked-in file). They are therefore **not** treated as established fact *within this document*. Throughout, such figures are presented as **illustrative / to-be-measured at admission**: the read-only evals (`quant_recall_gate_eval`, `quant_drift_eval`) emit them at runtime, but no frozen baseline artifact is attached. The *provenance contract* for admission (§8) is that the **actual stdout JSON of a dated eval run** (with DB path, row count, and the `corpus`/`k`/dimension fields from `RecallGateReport`) is the evidence — not a quoted number. The discipline precedent (read-only shadow, numeric gate, human-review-required) is mirrored from the in-tree read-only shadow design docs and the `coactivation_latch` "lswr-gated step" comment (§9); the precedent claim is anchored to those in-repo, reader-verifiable artifacts rather than to the out-of-repo forum/decision-memory record.

## 1. Motivation & Evidence

### 1.1 Footprint math

The default embedding model is `gte-multilingual-base` at **768-dim** (`crates/store/src/vector.rs:23-28`, `vector_dim_for_model_name` → `768`; default flip recorded since 2026-06-26). Each stored row is raw little-endian `f32` (`encode_embedding`, `vector.rs:410-416`), so:

| Representation | Per-row size (768-dim) | Formula |
| --- | --- | --- |
| f32 `embedding` BLOB (today, source of truth) | **3072 B** | `768 × 4` |
| Per-row symmetric INT8 (`i8[768]` codes + one `f32` scale) | **772 B** | `768 × 1 + 4` |
| **Ratio** | **≈ 3.98×** | `3072 / 772` |

The `+4 B` is the per-row absmax `scale` that the symmetric-absmax codec carries so dequantization can reconstruct f32 (`quant.rs:31-42`, `QuantizedRow { codes: Vec<i8>, scale: f32 }`; `encoded_len = codes.len() + size_of::<f32>()` at `quant.rs:39-41`). The exact ratio is `3072 / 772 = 3.9793 ≈ 3.98×`, matching the codec's `compression_ratio_matches_gte768` test. This is an *additive* cost in Phase A (we store INT8 *alongside* f32, so footprint temporarily grows); the 3.98× is the savings available *only after* a future Phase C cutover that drops f32 — which this proposal does NOT authorize.

### 1.2 Recall / drift evidence (illustrative — to be re-measured at admission)

The plan requires a **recall-regression gate to be green before any INT8 column is proposed**. The read-only evals make that check runnable:

- **recall@K** — computed by the read-only `quant_recall_gate_eval` example over the live active corpus. The gate uses asymmetric retrieval (fresh **f32 query** vector vs **dequantized-INT8 corpus** neighbors) — exactly the production retrieval contract this proposal preserves through Phases A/B. Verdict reported via `RecallGateReport.passed` (`recall_regression_gate`, `quant.rs:199`). **Important framing correction:** `recall_regression_gate` does **not** use every corpus row as a query — with the eval defaults (`MAX_QUERIES=200`, corpus ≈530) it evaluates a *deterministic stride subsample* of queries (`q_count = clamp(200,1,n)`, `stride = max(n/q_count,1)`), so "corpus ≈530 rows; recall measured over a deterministic stride sample of those rows as queries" is the honest phrasing. Output emitted under JSON schema **`agent_bridge.embedding_quant_recall_gate.v0`** (`quant_recall_gate_eval.rs:53`).
- **Drift** — mean round-trip cosine, `min_cosine`, `rows_below_0_999`, `zero_rows`, and the compression ratio, computed by `quant_drift_eval` (`measure_drift`, `quant.rs:132`; report fields at `quant.rs` `QuantDriftReport`). `measure_drift` skips empty rows, so the drift corpus (≈523 non-empty) differs from the recall corpus (≈530 active). Output emitted under JSON schema **`agent_bridge.embedding_quant_drift_eval.v0`** (`quant_drift_eval.rs:45`).

**Provenance discipline:** any number reported to the owner MUST be the attached stdout of a dated eval run (DB path, row count, and the `corpus`/`k`/dimension fields), not a quoted constant (see §0.1). Numbers are evidence that the gates *can* pass on a given store; they are not authorization.

The sub-1% cosine error is structurally expected, not luck: gte rows are L2-normalized, and per-row symmetric INT8 keeps the error bounded. The `QUANT_EPS = 1e-5` absmax floor (`quant.rs:28`; applied at `:51` as `scale = absmax.max(QUANT_EPS) / 127.0`) protects all-zero hash-fallback rows from divide-by-zero, so degenerate rows are handled honestly rather than crashing the codec.

### 1.3 Dimension honesty (folded-in correction)

The recall/drift evals apply **no dimension filter**: they `SELECT embedding FROM memories WHERE status='active' AND embedding IS NOT NULL` (`quant_recall_gate_eval.rs:29-36`, `quant_drift_eval.rs:25-32`), and `recall_regression_gate` (`quant.rs:207-212`) silently keeps only rows whose length matches the **first non-empty row** and drops the rest. On a store that has held 512/384/768 vectors across the v16 flip and the 2026-06-26 768 default, the measured corpus dimension is "whatever the first non-empty row is," not provably 768. Therefore this document does **not** assert "768-dim measurement" as fact. The honest admission-time procedure: report the actual `corpus`/`k` from `RecallGateReport`, and confirm the dimension spread with `SELECT DISTINCT LENGTH(embedding) FROM memories WHERE embedding IS NOT NULL` *before* attaching any 768-dim claim. The §6.2 / §5 length invariants below are written against `vector_dim()` (768 for gte, 384 otherwise), not a hardcoded 768.

The single precondition the plan set ("recall gate green") can be demonstrated on the **live local store**, read-only. Honesty about substrate: both eval surfaces open the DB with `SQLITE_OPEN_READ_ONLY` (`quant_recall_gate_eval.rs:18-28`, `quant_drift_eval.rs:17-24`) and quantize **in memory only** — they never write a byte and never touch a real INT8 column (there is none). The corpus is *this machine's* active rows, not a cross-machine or worst-case adversarial corpus. The numbers justify *proposing* the column and entering the admission ladder; they do **not** authorize the migration, and they do not generalize beyond the rows actually measured. §7 treats the residual risks (small corpus, single substrate, tail behavior, mixed-dim corpus) adversarially.

## 2. Boundary (what this does and does NOT do)

The scope below is the contract for Phases A and B. Anything not explicitly listed under "DOES" is out of scope and requires a fresh gate.

**This proposal DOES (within Phases A/B, after admission + sign-off):**

- Add **one additive shadow** in a future `v37` migration — two nullable columns `embedding_i8 BLOB` + `embedding_i8_scale REAL` (per-row INT8 codes + scale), following the post-v26 idempotent migration idiom (`pragma_table_info` COUNT guard before `ALTER TABLE ADD COLUMN`, e.g. v27/v31; `sqlite.rs:1196-1227`, `:1309-1336`), never the bare-batch v26 style.
- **Dual-write**: on `memory_save`, alongside the existing f32 `embedding` BLOB, compute and store the INT8 projection of the *same* vector. f32 remains written and authoritative.
- **i8↔BLOB serialization helper** (§3.1) — **landed as Phase-A groundwork** (`codes_to_blob`/`blob_to_codes` free fns + `QuantizedRow::to_blob`/`from_blob`, with round-trip / `LENGTH==dim` / sign-endpoint tests in `quant::tests`). Codec only — it adds no `embedding_i8` column and is not wired into the store write path.
- **Shadow measurement**: keep producing the read-only drift / recall-gate reports (`quant.rs` `measure_drift`, `recall_regression_gate`) against real stored rows to confirm in-store fidelity matches the in-memory eval.

**This proposal DOES NOT:**

- **No f32 removal in A/B.** The f32 `embedding` BLOB stays the **source of truth** through Phases A and B; `encode_embedding`/`decode_embedding` (raw little-endian f32, `vector.rs:410-427`) remain the live read path. Dropping f32 is a Phase-C cutover, gated separately and not authorized here.
- **No retrieval-contract change.** Live retrieval keeps reading f32 and keeps the **f32 query vector** (asymmetric: fresh f32 query vs corpus), unchanged. The INT8 column is not wired into any query path in A/B. The dim-guard invariant (v16 precedent, `sqlite.rs:1021-1039`) is untouched.
- **No sync-payload change.** `memory_export` selects a fixed 15-field set (`sqlite.rs:5343-5430`); `embedding`/`embedding_backend` are already excluded, and `embedding_i8` would likewise be **local-only**, never entering `memory.jsonl`. Conflict resolution reads only `(key, updated_at, version_vector)` (`sqlite.rs:5540-5555`, `:5715-5755`), `dedupe_key` derivation (`:1119-1150`), and FTS5 indexing (see §7d for the precise trigger semantics) are independent of any added BLOB column. `stabilise_sync_metadata` (`sqlite.rs:2167-2174`) only strips volatile local-state fields and adds none.
- **No autonomous schema mutation.** No agent may run the `v37` migration on its own. The lswr admission ladder (§8) plus explicit human owner sign-off are hard prerequisites — green metrics are necessary but **not sufficient**.
- **No write to `memory_save` in A/B beyond the dual-write hook itself.** No quantize-on-reuse self-heal inside `memory_save` (the self-heal/backfill is a batch-path concern, §3.3 / §7e).
- **No sibling-substrate work.** The deferred substrate step (§9) is sequenced after, and is not part of, this proposal.

## 3. Design — additive schema (v37)

This proposal adds **two nullable columns** to `memories`, behind the project's standard idempotent migration idiom. No existing column is altered or dropped in v37; `embedding` (the f32 BLOB) remains untouched and authoritative.

### 3.1 Columns and the serialization contract

| Column | Type | Nullability | Meaning |
|---|---|---|---|
| `embedding_i8` | `BLOB` | nullable (`NULL` = not yet quantized) | per-row INT8 codes (`Vec<i8>`), serialized under the byte contract below, produced by `quantize_row_i8` (`quant.rs:49-57`) |
| `embedding_i8_scale` | `REAL` | nullable (`NULL` = not yet quantized) | per-row absmax dequant scale: `max(|x_i|).max(QUANT_EPS) / 127.0` (`quant.rs:50-51`; `QUANT_EPS = 1e-5` at `quant.rs:28`) |

**Serialization contract (pin it — load-bearing for §6.2):** `embedding_i8` stores the `Vec<i8>` codes as **raw bytes, one byte per code, no length prefix, no framing** — i.e. a reinterpret of `&[i8]` as `&[u8]` (e.g. per-element `c as u8`, or a `bytemuck`/transmute of the slice). Therefore `LENGTH(embedding_i8) == vector_dim()` for a populated row (768 at the gte default, 384 otherwise). No serde/bincode/length-prefixed encoding is permitted, or §6.2's length invariant would false-positive on every healthy row.

**This serialization helper is now LANDED (codec-only — Phase-A groundwork).** Originally `quant.rs` shipped only the read-only quantize/dequantize half (`codes: Vec<i8>`, `scale: f32`, `encoded_len()`); the codec described here has since been added to `quant.rs`:
- encoder `fn codes_to_blob(codes: &[i8]) -> Vec<u8>` (per-byte `as u8`, raw layout above), and
- the inverse `fn blob_to_codes(bytes: &[u8]) -> Vec<i8>`,
- plus `QuantizedRow::to_blob(&self) -> (Vec<u8>, f32)` / `QuantizedRow::from_blob(&[u8], f32) -> QuantizedRow` mapping 1:1 onto the proposed `(embedding_i8, embedding_i8_scale)` pair,
- with round-trip (`blob_to_codes(codes_to_blob(c)) == c`), `LENGTH == dim`, sign-endpoint (`-128`→`0x80`, `127`→`0x7F`), and bit-exact `QuantizedRow` round-trip tests in `quant::tests`.

It remains **codec only**: no `embedding_i8` column exists and nothing is wired into the store write path. The remaining Phase-A work (still un-landed, owner-gated) is the v37 migration (§3.2) and the `memory_save` dual-write hook (§3.3). This satisfies the lswr `write_preflight` precondition (§8) that "the i8↔BLOB serializer + its round-trip test exist" — by pointer, not by quoted line number.

The read/dequant path is `dequantize_row_i8(&QuantizedRow) -> Vec<f32>` (single struct argument) — **not** `dequantize_row_i8(codes, scale)`. It is symmetric absmax; no zero-point column is needed.

`NULL`/`NULL` is the explicit "shadow not yet populated" state for a row — a legal, queryable steady state for any row whose f32 `embedding` predates dual-write or was reused (see §3.3).

A column index is **not** proposed in v37. Phase A/B never read these columns in a `WHERE`/`ORDER BY` (the corpus is loaded sequentially and quantized/compared in memory by the eval examples — `quant_recall_gate_eval.rs:29-36`), so an index would be dead weight. If Phase C ever needs one, `CREATE INDEX IF NOT EXISTS` is idempotent by default and can be added in that migration without a pragma guard.

### 3.2 The proposed v37 migration block

This is **PROPOSE-ONLY** — the snippet below is the design, not landed code. It follows the **v27/v31/v36 pragma-guarded idiom**, NOT the raw-batch v26 template. v26 (`sqlite.rs:1183-1195`) executes `SCHEMA_V26` as an unguarded `execute_batch`, which re-running on a store already at that schema would error on `ALTER TABLE ... ADD COLUMN` (SQLite has no `ADD COLUMN IF NOT EXISTS`). The idempotent `pragma_table_info` COUNT guard standardized at v27 (`sqlite.rs:1196-1227`) is the correct template; v36 (`sqlite.rs:1437`) is the most recent in-tree example.

It is appended after the v36 block, immediately before the closing `Ok(())`, inside the same `conn.call(|c| -> RusqliteResult<()> { ... })` migration closure that wraps the whole ladder (`sqlite.rs:760` region). Failures propagate via `?` and are mapped to `Error::Backend` at `sqlite.rs:1485-1487`, giving the migration transactional atomicity.

```rust
            // ── v37: shadow INT8 embedding projection (PROPOSE-ONLY; owner-gated).
            //    Additive + idempotent. embedding_i8 (raw i8 codes, 1 byte/code,
            //    no framing) + embedding_i8_scale (per-row absmax dequant scale).
            //    NULL/NULL = "not yet quantized"; a legal steady state for
            //    pre-v37 / reused-embedding rows. The f32 `embedding` BLOB stays
            //    SOURCE OF TRUTH through phases A and B — these columns are never
            //    read on the runtime retrieval path until Phase C cutover, which
            //    is a separate, gated proposal.
            let cur: String = c
                .query_row(
                    "SELECT value FROM schema_meta WHERE key='version'",
                    [],
                    |r| r.get(0),
                )
                // NB: this default mirrors the GATE value (v37 fires when cur=='36'),
                // not the literal "prior rung" convention some earlier rungs use.
                // It is internally correct; flagged so a reviewer comparing rungs
                // does not mistake it for a copy error.
                .unwrap_or_else(|_| "36".to_string());
            if cur.as_str() == "36" {
                for (name, ddl_type) in [
                    ("embedding_i8", "BLOB"),
                    ("embedding_i8_scale", "REAL"),
                ] {
                    let col_exists: i64 = c
                        .query_row(
                            "SELECT COUNT(*) FROM pragma_table_info('memories') \
                             WHERE name=?1",
                            params![name],
                            |r| r.get(0),
                        )
                        .unwrap_or(0);
                    if col_exists == 0 {
                        c.execute(
                            &format!("ALTER TABLE memories ADD COLUMN {name} {ddl_type}"),
                            [],
                        )?;
                    }
                }
                // NO backfill in v37. Existing rows stay NULL/NULL until they are
                // next (re)saved (§3.3) or an explicit, owner-invoked batch shadow
                // backfill is run. This keeps the migration O(1) and the column
                // genuinely additive — opening an old store does not rewrite it.
                let _ = c.execute("UPDATE schema_meta SET value='37' WHERE key='version'", []);
            }
```

Notes that make this faithful to the established pattern:
- The guard query is character-for-character the v27 idiom (`SELECT COUNT(*) FROM pragma_table_info('memories') WHERE name=?1`, `sqlite.rs:1209-1215`), so re-running v37 on a v37 store is a no-op (`col_exists == 1` → ALTER skipped).
- The version stamp is the last statement and uses the exact `UPDATE schema_meta SET value='37'` form used by every prior rung.
- `params!` is already in scope in this closure (used by v27/v28/v36).
- The `unwrap_or_else(|_| "36")` default is correct for a v37 gate; the inline comment flags that it mirrors the gate value rather than the "prior rung" default a few earlier rungs use, so it is not mistaken for a copy error.

### 3.3 Dual-write hook point inside `memory_save`

`memory_save` (`sqlite.rs:3053`) already resolves the f32 embedding through a single reuse-vs-recompute `match` that yields `(embedding_bytes, fresh_backend_name)` at **`sqlite.rs:3132-3160`**. That match is the *one* place where it is known whether a fresh f32 vector was just produced. The dual-write hook attaches there, so the INT8 shadow is computed from the **same `Vec<f32>`** that produced `embedding_bytes` — no second perceive, no re-decode.

Proposed shape (PROPOSE-ONLY) — extend the existing match to also yield the INT8 pair `(Option<Vec<u8>>, Option<f32>)`:

- **Fresh-compute arm** (`sqlite.rs:3138-3160`, the `_ =>` branch that calls `perceive_with_cold_fallback_retry` then `encode_embedding`): after `let (vec, actual_name) = ...`, also compute `let q = quant::quantize_row_i8(&vec);` and carry `(Some(quant::codes_to_blob(&q.codes)), Some(q.scale))` out alongside `(encode_embedding(&vec), Some(actual_name))`. `codes_to_blob` is the **new** serializer defined in §3.1 (it does not exist today). Because the fresh f32 vector is in hand, the codes and scale are exact (no round-trip through the BLOB).
- **Reuse arm** (`sqlite.rs:3133-3137`, the guard `existing_content == content && existing_emb.len() == expected_embed_bytes`): the f32 embedding is reused unchanged, so the INT8 shadow is **left untouched** — emit `None` for both `embedding_i8` and `embedding_i8_scale`, mirroring how `fresh_backend_name` already emits `None` here. The INSERT then preserves the prior shadow via `COALESCE(excluded.embedding_i8, memories.embedding_i8)`, exactly as `embedding_backend` is preserved today (`sqlite.rs:3205`).

> **Scope correction (folded in):** the previously-described "self-heal" sub-case — quantizing the reused f32 bytes *inside* the reuse arm to backfill a `NULL` shadow — is **removed from Phase A**. It contradicts this document's own invariant that "Phases A/B do not add a quantize to `memory_save`'s reuse path" (§2, §4 Phase A "Read: none," §7e). Lazy/bulk acquisition of shadows for pre-v37 or sync-imported rows is handled **only** by the batch reindex path (modeled on `memory_reindex_embeddings`, `sqlite.rs:6822-6920`), never by `memory_save`. If a future phase wants in-`memory_save` self-heal, it is a Phase-C decision with its own benchmark and gate. Note further that any such batch re-derivation MUST guard on `existing_emb.len() == expected_embed_bytes` before calling `decode_embedding`, because `decode_embedding` returns an **empty `Vec`** when `bytes.len() % 4 != 0` (`vector.rs:419-427`) — an unguarded re-derive on a wrong-length legacy/sync BLOB would silently produce a degenerate empty shadow instead of leaving it `NULL`.

The INSERT/ON-CONFLICT statement (`sqlite.rs:3182-3214`) gains two bound params and two `COALESCE` clauses, structurally identical to the existing `embedding_backend = COALESCE(excluded.embedding_backend, memories.embedding_backend)` line at `sqlite.rs:3205`:

```sql
    embedding_i8       = COALESCE(excluded.embedding_i8,       memories.embedding_i8),
    embedding_i8_scale = COALESCE(excluded.embedding_i8_scale, memories.embedding_i8_scale),
```

`COALESCE(excluded.x, memories.x)` means "fresh compute (Some) overwrites; reuse (None) preserves" — the same semantics the codebase already relies on for the backend tag.

### 3.4 Dim-flip rule (hard invariant)

The INT8 shadow MUST obey the same dimension invariant the f32 `embedding` already obeys. The v16 precedent (`sqlite.rs:1021-1039`) is the rule: when `vector_dim()` changes (e.g. the 512→384 flip, or the present 768 `gte-multilingual-base` default at `vector.rs:23-28`), stored vectors of the old dimension are uncomparable and are CLEARed to `NULL` to force a re-embed (production `cosine_similarity` returns `0.0` on dim mismatch, `vector.rs:396-397`).

Because `embedding_i8` is a strict projection of `embedding`, **any migration or operation that NULLs `embedding` for a dim change MUST NULL `embedding_i8` and `embedding_i8_scale` in the same statement.** A future dim-flip migration modeled on v16 becomes:

```sql
UPDATE memories SET embedding = NULL, embedding_i8 = NULL, embedding_i8_scale = NULL;
UPDATE codebase_symbols SET embedding = NULL;   -- codebase_symbols has no i8 shadow in this proposal
```

Rationale, stated honestly: a 768-dim INT8 blob is meaningless against a freshly re-embedded 384-dim (or new-dim) f32 corpus; leaving a stale-dim `embedding_i8` would silently feed garbage codes to any Phase C reader. Clearing them to `NULL` returns the row to the legal "not yet quantized" state, and the dual-write hook (§3.3) re-populates the shadow when the row is next re-embedded by `memory_reindex_embeddings` (`sqlite.rs:6822-6920`) or re-saved. The INT8 derivation must also ride the same dim-guard gate the reindex sweep uses — `reindex_should_sweep_mismatched_dims` (`sqlite.rs:2408-2414`), which gates same-backend wrong-dim sweeps on `dominant_dim == expected_dim` — so a misconfigured process cannot mass-rewrite a healthy store at the wrong dim. This proposal does **not** add a new dim-flip migration; it states the invariant the *next* dim flip must honor.

## 4. Three-phase rollout (A shadow / B measured read / C cutover)

The rollout follows the read-only shadow-campaign discipline: land structure first, measure in a read-only path with numeric gates, and require explicit human sign-off before anything irreversible. **Phases A and B are fully reversible with zero data loss because the f32 `embedding` BLOB remains the source of truth throughout.** Only Phase C is irreversible, and Phase C is therefore the only phase gated by the full lswr admission ladder + owner sign-off.

### Phase A — additive columns + dual-write (NO read change) — REVERSIBLE

- **Schema:** land the v37 migration (§3.2). Two nullable columns; existing rows are `NULL`/`NULL`.
- **Codec:** add the i8↔BLOB serializer + round-trip test (§3.1). This is new code, not an existing API.
- **Write:** wire the dual-write hook (§3.3). Newly saved/re-embedded rows acquire an `embedding_i8` shadow computed from the same f32 vector. Old rows stay `NULL` until next save or an explicit batch backfill — never via an in-`memory_save` self-heal.
- **Read:** **none.** The retrieval path continues to read `embedding` (f32) exclusively. `embedding_i8` is never consulted at query time. This is the literal "do not add to runtime path yet" boundary.
- **Measurement:** only the read-only eval examples touch the column, and only off the hot path: `quant_drift_eval.rs` (`SQLITE_OPEN_READ_ONLY`, `:17-24`) and `quant_recall_gate_eval.rs` (`:18-28`). They can also quantize the live f32 corpus in memory independent of the stored shadow, so they work even on a store with mostly-`NULL` shadows.
- **Reversibility:** total. Source of truth (f32) is unchanged. Roll back by (a) reverting the dual-write hook, leaving the columns dormant, or (b) dropping the two columns (§6). No re-embed needed; no row loses retrieval capability.

### Phase B — measured read (CI recall gate + footprint) — REVERSIBLE

- **What changes:** nothing on the *production runtime* retrieval path. Phase B promotes the eval examples into a **CI gate** that runs on representative store snapshots and must pass the §5 thresholds before Phase C may even be proposed for sign-off.
- **Query stays f32 (asymmetric retrieval):** the gate measures the *intended Phase C semantics* — a fresh **f32 query vector** scored against a **dequantized-INT8 corpus** (`dequantize_row_i8` → cosine). This is exactly what `recall_regression_gate` / `quant_recall_gate_eval.rs` compute (`quant.rs:199`). The query is never quantized.
- **Footprint:** `quant_drift_eval.rs` reports compression via the versioned JSON schema `agent_bridge.embedding_quant_drift_eval.v0`; recall via `agent_bridge.embedding_quant_recall_gate.v0`.
- **Reversibility:** total, identical to Phase A. Phase B adds *observation*, not a runtime read switch. Roll back by removing the CI gate and/or the columns; no data loss.

### Phase C — cutover: drop f32 column — IRREVERSIBLE — FULL GATE REQUIRED

- **What changes:** the retrieval path switches to reading `embedding_i8` + `embedding_i8_scale` (dequantize on read, f32 query), and the f32 `embedding` column is dropped to realize the footprint win. **Dropping `embedding` destroys the source of truth.** Once dropped, the only path back to f32 fidelity is a full re-embed of the corpus through the model (`memory_reindex_embeddings`), which is expensive, model-availability-dependent, and *not* a true rollback (INT8→f32 is lossy; you recompute *new* vectors, you do not recover the originals).
- **Therefore Phase C is the only phase that requires the full lswr admission ladder + owner sign-off** (§8). Metrics passing the §5 gate is **necessary but not sufficient** — a human owner must review and approve even when every gate is green.
- **Reversibility:** **none for the f32 drop.** Any intermediate "read INT8 but keep f32" step (recommended) is reversible and should precede the actual `DROP COLUMN`; the irreversible boundary is precisely the `embedding` drop.

| Phase | Schema change | Runtime read path | Source of truth | Reversible? |
|---|---|---|---|---|
| A | + 2 nullable columns | unchanged (f32) | f32 `embedding` | Yes — drop columns / stop dual-write |
| B | none beyond A | unchanged (f32); INT8 read only in CI/eval | f32 `embedding` | Yes — remove gate / drop columns |
| C | drop f32 `embedding` | reads INT8 (f32 query, dequant corpus) | INT8 `embedding_i8` | **No** — f32 destroyed; only lossy re-embed |

## 5. Gate thresholds

This is a gate doc: explicit numeric thresholds, every one testable from a named **read-only** eval, and a hard rule that **passing metrics do not auto-promote** — human review is required regardless. No threshold below is wired into any runtime decision; they are pre-flight acceptance criteria for *proposing* a Phase C cutover, nothing more.

The query vector stays **f32** for every measurement. All recall numbers are asymmetric: a fresh f32 query ranked against a dequantized-INT8 corpus — exactly what `recall_regression_gate` (`quant.rs:199`) computes, so the gate measures the production retrieval geometry, not an idealized symmetric one. Each recorded value MUST be backed by attached eval stdout (§0.1), and each must report the actual `corpus`/`k`/dimension it was measured at (§1.3).

| # | Gate | Threshold | Eval surface (read-only) + schema | Pass condition |
|---|------|-----------|-----------------------------------|----------------|
| G1 | Recall@10 on a frozen corpus | `mean_recall_at_k >= 0.98` | `quant_recall_gate_eval.rs` (`SQLITE_OPEN_READ_ONLY`), schema `agent_bridge.embedding_quant_recall_gate.v0` | `RecallGateReport.passed == true` at k=10, threshold 0.98 |
| G2 | Expected-doc rank regressions | **0** queries below threshold | `quant_recall_gate_eval.rs`, same schema | `RecallGateReport.queries_below_threshold == 0` |
| G3 | Footprint reduction (f32 → INT8) | measured `>= 3.5x` | `quant_drift_eval.rs`, schema `agent_bridge.embedding_quant_drift_eval.v0` | `f32_bytes / int8_bytes >= 3.5` in `QuantDriftReport` |
| G4 | Mean round-trip cosine fidelity | `mean_cosine >= 0.999`, with **0 rows below 0.999** | `quant_drift_eval.rs`, same schema | `mean_cosine >= 0.999` AND `rows_below_0_999 == 0` |
| G5 | Query path stays f32 | invariant, not a number | `recall_regression_gate` (asymmetric f32-query design) | retrieval code path unchanged; INT8 corpus only |
| G6 | Human review | **REQUIRED even if G1–G5 all pass** | owner review (see §8) | explicit owner sign-off recorded |

Threshold rationale and honesty notes:

- **G1 is a frozen-corpus, stride-sampled gate.** The corpus is snapshotted before measurement; the queries are a *deterministic stride subsample* of that corpus (not all rows — see §1.2), so the number is reproducible run-to-run (`recall_regression_gate` is deterministic). The 0.98 floor sits below any plausibly-healthy value so the gate tolerates corpus growth and minority-dim rows without an auto-fail, while still catching a real collapse.
- **G2 is the tie-break tripwire.** `queries_below_threshold == 0` surfaces the rank-flip failure mode in §7(b). One regressed query fails G2 even if the G1 mean still looks healthy.
- **G3 ceiling is ~4×, not more.** Per-row absmax INT8 stores 1 byte/component + one f32 scale/row → `768 + 4` vs `3072` ≈ `3.98×`. The floor is set at 3.5× for headroom; 3.98× is the honest exact figure, 3.5× the conservative gate.
- **G4 is a per-row gate, not just an average.** A high mean can hide a few catastrophic rows; `rows_below_0_999 == 0` forbids that.
- **G5 is structural.** Asymmetric retrieval (f32 query vs dequantized-INT8 corpus) is the only configuration measured. Symmetrizing the query is explicitly **out of scope** and would invalidate every number above.

All recorded numbers are evidence that the gates *can* pass on the measured store — they are **not** authorization to proceed, and they do not assert a dimension the eval cannot prove (§1.3).

## 6. Migration & rollback runbook

All statements below are **proposed**; this doc changes no code. SQL is shown as it would run inside the v37 closure (§3.2) or via an admin/eval connection.

### 6.1 Forward migration (Phase A apply)

Executed automatically by the v37 rung on next `SqliteStore::open` (`sqlite.rs:760` region). Effective statements, each guarded by the `pragma_table_info` COUNT check so they are idempotent:

```sql
-- only runs if pragma_table_info('memories') has no 'embedding_i8'
ALTER TABLE memories ADD COLUMN embedding_i8 BLOB;
-- only runs if pragma_table_info('memories') has no 'embedding_i8_scale'
ALTER TABLE memories ADD COLUMN embedding_i8_scale REAL;
UPDATE schema_meta SET value='37' WHERE key='version';
```

No backfill statement runs in v37 (§3.2): existing rows stay `NULL`/`NULL`. The migration is O(1) in row count.

### 6.2 Verification

```sql
-- 1. version stamped
SELECT value FROM schema_meta WHERE key='version';            -- expect '37'

-- 2. both columns exist (the exact idiom the guard uses)
SELECT name, type FROM pragma_table_info('memories')
 WHERE name IN ('embedding_i8','embedding_i8_scale');         -- expect 2 rows: BLOB, REAL

-- 3. additive proof — no f32 row was touched by the migration
SELECT COUNT(*) FROM memories WHERE embedding IS NOT NULL;    -- unchanged vs pre-migration

-- 4. shadow population (grows only as rows are saved under dual-write)
SELECT
  SUM(embedding_i8 IS NOT NULL)  AS shadowed,
  SUM(embedding_i8 IS NULL)      AS unshadowed
FROM memories WHERE status='active';

-- 5. shadow byte-length sanity for populated rows.
--    Per the §3.1 serialization contract (raw i8, 1 byte/code, no framing),
--    LENGTH(embedding_i8) == vector_dim(). Bind the *active* dim (768 for gte,
--    384 otherwise) as :dim rather than hardcoding 768 (§1.3).
SELECT COUNT(*) FROM memories
 WHERE embedding_i8 IS NOT NULL
   AND LENGTH(embedding_i8) != :dim;                          -- expect 0
```

Re-running the migration (re-opening the store) must be a no-op: step 2 still returns exactly 2 rows and `ALTER` is skipped because `col_exists == 1`.

### 6.3 Rollback per phase

**Phase A / Phase B rollback — zero data loss (f32 retained):**

Two equivalent levers; pick by how clean a revert is wanted.

1. *Stop dual-write only* (soft revert): revert the `memory_save` hook (§3.3). The columns remain but go stale. The f32 `embedding` path is unaffected; retrieval is byte-for-byte what it was. No SQL needed.
2. *Drop the columns* (hard revert). The project pins `tokio-rusqlite = { version = "0.6", features = ["bundled"] }` (`Cargo.toml:78`), which bundles SQLite ≥ 3.44 — comfortably past the 3.35 floor where `ALTER TABLE ... DROP COLUMN` landed — so the direct form is the fast path:
   ```sql
   ALTER TABLE memories DROP COLUMN embedding_i8;
   ALTER TABLE memories DROP COLUMN embedding_i8_scale;
   ```
   The **guaranteed-portable fallback** (use if the pin ever regresses below 3.35) is the table-rebuild form: `CREATE TABLE memories_new AS SELECT <all columns except the two>; DROP TABLE memories; ALTER TABLE memories_new RENAME TO memories;` then recreate indexes/triggers. Either way **`embedding` is preserved**, retrieval quality is unchanged, and no re-embed is required.
   Optionally roll the version stamp back: `UPDATE schema_meta SET value='36' WHERE key='version';` (only if the v37 rung is also removed from the binary; otherwise a v37 binary re-adds the columns on next open — the intended idempotent behavior).

**Phase C rollback — NONE (this is why the gate exists):**

Once `ALTER TABLE memories DROP COLUMN embedding;` executes, the f32 source of truth is gone. No statement restores it. The only recovery is a full re-embed (`memory_reindex_embeddings`, `sqlite.rs:6822-6920`) which produces *new* f32 vectors from current model state — not the originals — and depends on model availability and the dim invariant (§3.4). This is forward recovery, not rollback. Accordingly Phase C requires owner sign-off + the lswr ladder (§8), and a fresh DB-file backup taken immediately before the `DROP` is mandatory so a file-level restore is the real fallback.

### 6.4 Data-loss analysis (per phase)

| Phase | Operation | f32 `embedding` | INT8 shadow | Worst-case data loss | Recovery |
|---|---|---|---|---|---|
| A apply | `ADD COLUMN` ×2 (guarded) | untouched | created empty (`NULL`) | **none** — additive, O(1), idempotent | n/a |
| A dual-write | compute INT8 on fresh f32 | untouched | populated from same vector | **none** — shadow derived, f32 authoritative | n/a |
| A rollback | stop hook / drop columns | **retained** | discarded (re-derivable) | **none** — INT8 is a lossy projection of retained f32 | re-derive shadow by re-save / batch backfill |
| B (CI gate) | read-only eval | untouched (`READ_ONLY` open) | read-only | **none** — examples never write (`quant_drift_eval.rs:17-24`) | n/a |
| B rollback | remove gate / drop columns | **retained** | discarded | **none** | same as A rollback |
| Dim flip (any phase) | `UPDATE ... SET embedding=NULL, embedding_i8=NULL, embedding_i8_scale=NULL` (§3.4) | cleared by design (v16 precedent) | cleared by design | f32 vectors cleared **intentionally** to force re-embed; pre-flip vectors not recoverable from DB | re-embed via `memory_reindex_embeddings` |
| **C cutover** | `DROP COLUMN embedding` | **DESTROYED** | becomes sole source | **IRREVERSIBLE** loss of original f32 fidelity (INT8 is lossy: cosine < 1.0) | **none in-DB**; only file-level backup restore or lossy re-embed → **owner sign-off + lswr ladder required** |

## 7. Risks & adversarial analysis

Each risk lists a likelihood, the concrete failure, and a mitigation grounded in existing code. The framing is adversarial: assume the INT8 column *will* be wrong unless a named mechanism prevents it.

### (a) Model-dim flip silently corrupts the INT8 column — Likelihood: Medium

`vector_dim()` is model-aware and resolved at runtime (`vector.rs:29-45` via `onnx::active_model_name()`): gte → 768, the 384-dim models (all-MiniLM-L6-v2, e5-small, para-ml) → 384 (`vector.rs:23-28`). If the active model flips, every existing `embedding_i8` row is the wrong dimension, and `dequantize_row_i8` would reconstruct a vector that `cosine_similarity` cannot compare (returns 0.0 on dim mismatch, `vector.rs:396-397`; the same hazard the v16 comment calls out at `sqlite.rs:1021-1039`). This risk is *live now* because the store has held 512/384/768 vectors across the v16 flip and the 2026-06-26 768 default (§1.3).

**Mitigation:** the INT8 column MUST obey the v16 invariant — any path that NULLs `embedding` for a dim change NULLs `embedding_i8`/`embedding_i8_scale` in lockstep (§3.4). Because f32 stays source of truth through A/B, a NULLed INT8 column simply means "re-derive from f32 later" — no data loss, no stale comparison. The derivation rides the same `reindex_should_sweep_mismatched_dims` gate (`sqlite.rs:2408-2414`, `dominant_dim == expected_dim`) so a misconfigured process cannot mass-rewrite a healthy store at the wrong dim.

### (b) Tie-break instability flips top-1 under quantization — Likelihood: Medium

This is the sharpest correctness risk and it is already demonstrated. The test `recall_gate_detects_neighbor_regression` (`quant.rs`) constructs a query whose true f32 nearest neighbor is `b`, but a large-absmax dimension forces the discriminating components of `a` and `b` to round to 0, collapsing both rows to the same INT8 codes; the tie-break then flips the INT8 top-1 to `a`, driving `recall@1` to 0 and failing the gate. Per-row absmax means a single large component compresses the dynamic range of all other components in that row — exactly the rows where neighbors are close are the rows most likely to flip.

**Mitigation:** the gate catches it by design. G2 (`queries_below_threshold == 0`) fails on the first flipped query even when the G1 mean stays high, and the test above is the regression proof. No data-path mitigation is proposed for A/B because f32 remains source of truth — the INT8 ranking is only ever *measured*, never *served*, until Phase C clears all gates and passes owner review.

### (c) All-zero / hash-fallback rows divide by zero — Likelihood: Low

Cold or short-lived embed contexts fall back to the hash backend, and some rows legitimately quantize to an all-zero (or near-zero) vector. Symmetric absmax computes `scale = absmax / 127`, which is `0` for an all-zero row, making `dequantize` divide by zero.

**Mitigation:** already handled. `quantize_row_i8` floors the scale at `QUANT_EPS = 1e-5` (`quant.rs:28`, applied at `:51`): `scale = absmax.max(QUANT_EPS) / 127`. The zero row encodes to all-zero codes with a tiny non-zero scale and round-trips back to zero without a NaN. The drift eval reports such rows via `zero_rows` in `QuantDriftReport`, so they are visible, not hidden.

### (d) Sync/export perturbation — INT8 leaks into `memory.jsonl` — Likelihood: Low

If `embedding_i8` ever entered the sync transport it would bloat `memory.jsonl`, churn diffs, and pollute conflict resolution.

**Mitigation:** it cannot leak by default. `memory_export` selects a hardcoded **15-field** set (`sqlite.rs:5343-5430`) — `embedding`/`embedding_backend` are already *not* among them, and a new `embedding_i8` column would likewise be invisible unless someone explicitly adds it to that SELECT. Conflict resolution reads only `(key, updated_at, version_vector)` (`sqlite.rs:5540-5555`, `:5715-5755`) — no BLOB influences the `ImportAction`. `dedupe_key` is pure tag parsing (`sqlite.rs:1119-1150`); `stabilise_sync_metadata` (`sqlite.rs:2167-2174`) only zeroes volatile local-state fields and adds none.

**FTS precision correction (folded in):** it is **not** accurate to say a new BLOB "does not trigger FTS re-indexing." The v36 FTS triggers are *whole-row*: `memories_au AFTER UPDATE ON memories` (and the ON-CONFLICT update path) fire on **any** column change and re-index the row by re-inserting `COALESCE(new.fts_content, new.content)` (`sqlite.rs:135-165`). So a dual-write that writes `embedding_i8` via §3.3's `ON CONFLICT DO UPDATE` **will** fire the AFTER-UPDATE trigger and re-index the row. However, the *indexed text* is `COALESCE(fts_content, content)` — neither of which `embedding_i8` touches — so the indexed tokens, search results, and ranking are byte-identical. The only cost is one redundant FTS delete+reinsert per dual-write, which is **the same cost every existing `embedding`/`embedding_backend` write already pays** and is negligible. The load-bearing conclusion (no sync/retrieval perturbation) holds; only the categorical "does not trigger FTS" phrasing was wrong. The boundary rule stands: **`embedding_i8` is local-only and must never be added to the `memory_export` SELECT.**

### (e) Write-path cost & races — Likelihood: Low–Medium

If a future phase derives `embedding_i8` inline in `memory_save` (`sqlite.rs:3053`) beyond the simple dual-write, it adds per-row quantize on the hot write path and a second BLOB write inside the same `ON CONFLICT DO UPDATE`. The reuse-vs-compute branch (`sqlite.rs:3132-3160`) must keep INT8 consistent with whatever f32 it stamps — a reused f32 (returns `None` backend, preserves prior tag) must also preserve the prior INT8, while a fresh compute re-derives both, or the two columns desync.

**Mitigation:** the Phase-A dual-write is exactly the COALESCE-preserve discipline already proven for `embedding_backend` (`sqlite.rs:3205`): fresh → `Some`, reuse → `None`. No quantize-on-reuse self-heal runs in `memory_save` (§3.3 scope correction). Bulk/lazy shadow acquisition for old rows is a read-then-write batch path modeled on `memory_reindex_embeddings` (`sqlite.rs:6822-6920`), all inside the single async `conn.call` tx (`sqlite.rs:760`) with the 5 s busy-timeout, so atomicity and writer races are already covered. Any heavier inline derivation is a Phase-C decision needing its own benchmark and the full lswr ladder (§8).

### (f) `codebase_symbols.embedding` is also a candidate — OUT OF SCOPE — Likelihood: n/a

`codebase_symbols` also stores f32 embeddings and was cleared alongside `memories` in v16 (`sqlite.rs:1021-1039`), so it is a natural second target. **It is explicitly out of scope.** This doc covers `memories.embedding_i8` only. Extending INT8 to `codebase_symbols` would be a separate proposal with its own gates and owner review; bundling it here would widen the blast radius and the eval surface beyond what the measured numbers cover.

## 8. lswr admission-ladder mapping & owner sign-off

Phase C (cutover — making INT8 a live, served or write-path artifact) is an **outcome that mutates store behavior**, so it maps onto the `lswr_outcome_admissions*` admission ladder, not an ad-hoc merge:

1. **`lswr_outcome_admissions_dry_run`** — run the read-only evals (`quant_recall_gate_eval`, `quant_drift_eval`) against the frozen corpus and produce the §5 gate report with no writes. The "would it pass?" stage; 1:1 with the read-only eval surfaces already built.
2. **`lswr_outcome_admissions_write_preflight`** — preflight the actual write: confirm the v37 migration is additive and idempotent (pragma guard, v27/v31 idiom — §3/§6), confirm the i8↔BLOB serializer + its round-trip test exist (§3.1), confirm the derivation path is the batch reindex model (not an in-`memory_save` self-heal), and confirm `embedding_i8` is absent from the `memory_export` SELECT (§7d). No live write yet.
3. **`lswr_outcome_admissions_approval_packet`** — assemble the evidence bundle: the §5 gate table backed by **attached dated eval stdout** (with `corpus`/`k`/measured-dimension, per §0.1/§1.3), the §7 risk register, the migration/rollback runbook (§6), and the explicit statement that f32 stays source of truth through A/B. This packet is what the owner reviews.
4. **`lswr_outcome_admissions_ingest`** — only after recorded owner approval does the cutover ingest. The single point at which INT8 may influence a runtime path.

**Owner sign-off is mandatory and non-bypassable.** *Human review is required even if every metric passes.* G6 in §5 encodes this. Green gates produce an approval packet; they do not produce an automatic ingest.

**A/B vs C split:**

- **Phases A (shadow) and B (measured read)** are additive and fully reversible — the v37 columns are NULL-able, never read by the runtime, and droppable/clearable without data loss because f32 remains source of truth. These need a **design review** (this doc) but **not** the full admission ladder.
- **Phase C (cutover)** changes served/written behavior and therefore requires the **complete ladder** (dry_run → write_preflight → approval_packet → ingest) plus the mandatory owner sign-off above.

## 9. Sibling deferred substrate step & sequencing

There is a second column-wiring already parked behind the same gate. The `coactivation_latch` module documents (`crates/store/src/coactivation_latch.rs:12-14`) that wiring a **`consolidated` column** into the live prune path was deferred to *"the lswr-gated step"* — the module is the offline, no-I/O, no-schema kernel (`decide(count, consolidated)`) that *justifies* a future `consolidated` column but does not create it. (The `coactivation_latch.rs:12-14` source comment is the verifiable provenance for this deferral; no forum-post citation is attached, per §0.1.)

Both are the same shape: a substrate-level additive column (`memories.embedding_i8`, `coactivation_latch`'s `consolidated`) whose offline kernel is already proven read-only and whose live wiring is explicitly parked behind owner-gated lswr admission.

**Recommendation — sequence both column-wirings as one owner review.** Rather than two uncoordinated v3x migrations (a v37 for INT8 and a separate v38 for `consolidated`), the lswr ladder should carry both into a **single owner review and a single coordinated migration window**:

- Both are additive, idempotent, NULL-defaulted columns following the v27/v31 guard idiom, so they migrate identically and can share one migration block.
- One owner review amortizes the human cost and gives the owner a single, coherent picture of the substrate's pending schema debt.
- Two uncoordinated migrations risk version-ladder churn and a half-migrated store between windows; one window avoids the intermediate state.

This is a sequencing recommendation, not a coupling: gates stay per-column (INT8 has §5's recall/drift gates; `consolidated` has the latch's prune-correctness tests). The proposal is only to *batch the owner review and the migration*, not to make one column's approval depend on the other's metrics.

## 10. Definition of done (for THIS proposal)

This is a **PROPOSE-ONLY** document. Its Definition of Done is documentary, not implementational.

**This proposal is DONE when:**

1. It is committed to `docs/design/` (this file), alongside the existing read-only shadow-campaign design docs that set the precedent.
2. It is posted for owner review, with the §5 gate table and — per the provenance discipline (§0.1) — **attached dated eval stdout** from `quant_recall_gate_eval` (schema `agent_bridge.embedding_quant_recall_gate.v0`) and `quant_drift_eval` (schema `agent_bridge.embedding_quant_drift_eval.v0`), each reporting its actual `corpus`/`k`/measured dimension rather than a quoted constant.

**This proposal explicitly does NOT:**

- authorize any schema change — there is **no v37 migration landed** by this doc;
- add INT8 to any runtime read, write, or sync path;
- modify `memory_save`, `memory_export`, or the migration ladder;
- add the i8↔BLOB serializer (it is *specified* here as Phase-A work, not landed);
- pre-approve Phase C — green gates produce an approval packet, not an ingest (§8).

**The next action is owner review, not implementation.** Per the discipline mirrored throughout: *do not add to the runtime path yet; human review is required even if the metrics pass.* If and only if the owner approves does work proceed onto the lswr admission ladder (§8), ideally co-sequenced with the deferred `coactivation_latch` `consolidated` column (§9).

## 11. Adversarial review record

This document was assembled from a draft and then hardened against three adversarial review lenses. Every blocker/major finding was folded in; minor/nit findings were applied where they improve correctness or honesty.

- **Lens 1 — Repo-correctness / API-surface (5 findings: 1 major, 2 minor, 2 nit, no blockers).** Major: the §3.3 sketch invented a non-existent `q.codes_as_bytes` and overstated how much of the write path already exists — **folded in** by removing it, stating explicitly that an i8↔BLOB serializer must be ADDED in Phase A with a round-trip test (§3.1, §10), and re-anchoring quant.rs line citations (`quantize_row_i8` `:49-57`, `dequantize_row_i8` `:60`, `QUANT_EPS` `:28`, struct `:31-42`). Minor/nit: corpus-vs-query-count phrasing (§1.2), the unguarded `decode_embedding` self-heal hazard (§3.3 scope correction), and the v16 range standardized to `1021-1039` throughout — all folded in.
- **Lens 2 — Sync/substrate-corruption (5 findings: 0 blocker/major, all minor/nit). PASS.** Folded in: the FTS "whole-row trigger fires but indexed text unchanged" precision correction (§7d), the corrected `dequantize_row_i8(&QuantizedRow)` signature and pinned raw-i8 serialization contract feeding §6.2's length check (§3.1), the `stabilise_sync_metadata` anchor fix to `sqlite.rs:2167-2174` (§2), and the quant.rs line re-anchoring.
- **Lens 3 — Evidence honesty (8 findings: 3 major, 3 minor, 2 nit; verdict REQUEST CHANGES on the evidence layer).** Three majors **folded in**: (1) unverifiable headline numbers and `#2577/#2583` forum citations are demoted to illustrative/to-be-measured with an attached-stdout provenance contract and the precedent re-anchored to verifiable in-tree artifacts (§0.1, §1.2, §5, §8, §10); (2) the unproven "768-dim" attribution is replaced with an honest "first-non-empty-row dimension, confirm with `SELECT DISTINCT LENGTH(embedding)`" procedure and `vector_dim()`-relative length checks (§1.3, §6.2); (3) the in-`memory_save` self-heal scope slip is removed and pushed to the batch reindex path (§3.3, §7e). Minor/nit on the recall-vs-drift schema split, the v37 default-version comment, and the `#2577` drop in §9 — all folded in. The PROPOSE-ONLY posture, owner-gating, and lswr mapping were affirmed sound and left intact.
