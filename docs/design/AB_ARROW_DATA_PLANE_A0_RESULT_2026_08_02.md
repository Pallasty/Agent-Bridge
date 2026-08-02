# AB Arrow Data Plane A0 — result and decision

Date: 2026-08-02
Status: complete canonical evidence; native chunk selected for an A1 candidate
Implementation revision: `229a88436f9928919343f4bbfffe382f6d8b3127`
Base revision: `1e6009d7eb41d60ef6fa0fe20249e2055964f989`

## Decision

Promote the bounded native `TypedBatch` design, not Arrow, as the only A1
integration candidate for the current `codebase_index` accumulation boundary.

Both bounded strategies eliminate the measured whole-workload memory
amplification and pass the absolute 30% RSS / 10% elapsed gates in all nine
paired trials. Arrow does not add incremental value over the simpler native
path: at the canonical batch size, Native has both lower median RSS and lower
median elapsed time. The 1,024- and 16,384-row diagnostics preserve that
direction.

This result does not authorize a production storage change. A1 must separately
test bounded SQLite insertion and transaction behavior. It also does not make a
claim about other AB memory walls or about an Arrow consumer that was not
present in this experiment.

## Canonical evidence

Frozen configuration: 100,000 generated documents, 1,400,000 extracted rows,
4,096-row shared typed accumulator, nine trials per mode, and a balanced
three-position rotation. Every trial ran in a fresh process.

| Mode | Median peak RSS | Median elapsed | RSS vs FullVec | Elapsed vs FullVec | Paired absolute gate |
| --- | ---: | ---: | ---: | ---: | ---: |
| FullVec | 387,308 KiB | 6.994 s | baseline | baseline | n/a |
| NativeChunk | 4,064 KiB | 3.625 s | -98.95% | -48.17% | 9/9 |
| ArrowRecordBatch | 4,236 KiB | 3.716 s | -98.90% | -46.87% | 9/9 |

Arrow uses 4.23% more median RSS and 2.50% more median elapsed time than
Native. It passes the Arrow-vs-Native material-value rule in 0/9 paired trials,
so `arrow_incremental_value=false`. The canonical terminal result is:

- `measurement_complete=true`
- `evidence_complete=true`
- `receipt_contracts_valid=true`
- `post_run_identity_stable=true`
- `recommendation=native_chunk`
- `status=native_chunk_preferred`

## Correctness and bounds

All 27 receipts have one exact workload identity, semantic receipt, build
identity, and executable digest. The semantic result is:

- symbols: 500,000
- imports: 225,000
- calls: 675,000
- combined semantic SHA-256:
  `c26dd0d5f2b3844113f1030128cbfad1506b81cec2d13b585649c5b4057a3099`

Both bounded paths emitted 342 typed flushes. Observed logical-row bounds were:

| Mode | Max accumulator | Max extractor output | Max estimated live | Declared bound |
| --- | ---: | ---: | ---: | ---: |
| FullVec | 1,400,000 | 18 | 1,400,000 | 1,400,000 |
| NativeChunk | 4,096 | 18 | 4,106 | 4,113 |
| ArrowRecordBatch | 4,096 | 18 | 8,202 | 8,209 |

Arrow emitted 342 batches for each of the three logical tables. Its largest
single table batch contained 1,978 rows. The three cached schema fingerprints
match the frozen combined fingerprint
`76db54f5f3a2938c88aa6a82b378503d5919293a08d24c4ff5e7297e78f84cda`.

## Sensitivity evidence

Sensitivity runs use three trials per mode and are deliberately
`diagnostic_only`: they can validate direction but cannot emit a promotion
candidate.

| Batch rows | Native RSS / elapsed | Arrow RSS / elapsed | Arrow vs Native | Direction |
| ---: | ---: | ---: | ---: | --- |
| 1,024 | 3,668 KiB / 4.043 s | 3,856 KiB / 4.051 s | +5.13% RSS, +0.21% elapsed | Native |
| 4,096 canonical | 4,064 KiB / 3.625 s | 4,236 KiB / 3.716 s | +4.23% RSS, +2.50% elapsed | Native |
| 16,384 | 6,448 KiB / 4.096 s | 7,768 KiB / 4.321 s | +20.47% RSS, +5.48% elapsed | Native |

There is no observed batch-size reversal and Arrow's material-value paired
count is zero in both diagnostic suites.

## Provenance

The clean release binary recorded:

- Git revision: `229a88436f9928919343f4bbfffe382f6d8b3127`
- nested `Cargo.lock` SHA-256:
  `c7cdda913655b2aa29320184ab82554da2dbdd496cf858ac1ed37dc706154811`
- tracked Git-index manifest SHA-256:
  `b341acf4ccd807a759bdbe24313e80d984ef7aaaadfa3aef12e4b8bc83fe2cfe`
- executable SHA-256:
  `6dc55248554aeee3a35b3bc2e50926b99097d1d97e7091582a12f7ab674632c2`
- Rust: `rustc 1.96.0 (ac68faa20 2026-05-25)`
- target/profile: `x86_64-unknown-linux-gnu`, release, opt-level 3,
  debug assertions false, empty encoded rustflags, no profile override
- host: Linux `7.0.0-27-generic`, Xeon Gold 6138, 80 logical CPUs,
  588,894,720 KiB physical memory

Raw receipts and their file SHA-256 values:

- `arrow_data_plane_a0_canonical_receipt_20260802.json`:
  `556f78a1e0806c068b687d0b33400526382b8992fc42464f8daa1c8cc3f30ab8`
- `arrow_data_plane_a0_diagnostic_b1024_20260802.json`:
  `90a67895e17b33f8f8a61863139fecce5bdfc44631a22d14dc9faa76d79a464b`
- `arrow_data_plane_a0_diagnostic_b16384_20260802.json`:
  `4dec5299d341e3b7220ef9602dbf3933b92f16674e3d741d516f9f6d4f5e164d`

## A1 boundary

The next unit should implement a default-off bounded native insertion path
inside `codebase_index`, preserving one SQLite transaction and exact existing
row semantics. It must compare production-equivalent insertion, rollback,
failure atomicity, WAL/page-cache behavior, and end-to-end RSS/time against the
current path before any default change.

Arrow remains available for reconsideration only when a concrete downstream
consumer can eliminate a measured copy or enable a measured cross-language,
query, or device-buffer benefit. This A0 result is not evidence against Arrow
for those different boundaries.

## Honest limits

- The workload is deterministic and extractor-representative, not a live-tree
  replay.
- The public extractors still allocate complete per-file vectors.
- Logical-row bounds do not model retained Vec capacity, allocator retention,
  string bytes, Arrow offsets, or schema bytes; Linux `VmHWM` is the physical
  high-water evidence.
- SQLite insertion, transactions, WAL, indexes, and page cache were not
  measured.
- This is single-host CPU evidence with no MI50, ROCm, GPU-buffer, Flight,
  DataFusion, or C Data/C Device consumer.
- The source/artifact chain detects drift; it is not a signed reproducible-build
  attestation.
