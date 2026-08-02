# AB codebase-index Arrow A0

`ab-codebase-arrow-a0` is an evaluation-only nested Rust workspace. It asks one
bounded question: does Arrow `RecordBatch` materialization improve the visible
full-repository accumulation cost in `SqliteStore::codebase_index`, and does it
add enough value beyond ordinary bounded Rust chunks to justify promotion?

It is not a production `ab-store` feature, is not a root-workspace member, and
has no SQLite, MCP, retrieval, daemon, GPU, ROCm, or MI50 consumer.

## Frozen comparison

All modes consume the same deterministic sequence of generated Rust, Python,
TypeScript, and Go documents through the public production extractors:

- `ab_store::codebase::extract_symbols`
- `ab_store::codebase::extract_imports`
- `ab_store::codebase::extract_calls`

The three paths are:

1. `full-vec`: retain complete symbol, import, and call vectors before hashing;
2. `native-chunk`: consume one shared `TypedBatch` containing bounded symbol,
   import, and call vectors;
3. `arrow-record-batch`: convert that same typed accumulator into up to three
   production-shaped `RecordBatch` values, then compute semantics from the
   decoded Arrow arrays.

Semantic equality is field-complete and order-sensitive within each logical
table. Every string uses length framing, numeric fields use big-endian bytes,
and optional fields retain their null/present distinction.

## Reproduce

Keep build artifacts outside this nested workspace:

```bash
export AB_A0_TARGET=/tmp/ab-arrow-codebase-a0-target

CARGO_TARGET_DIR="$AB_A0_TARGET" \
  cargo test \
  --manifest-path scripts/eval/arrow-codebase-a0/Cargo.toml \
  --all-targets --locked --offline

CARGO_TARGET_DIR="$AB_A0_TARGET" \
  cargo build \
  --manifest-path scripts/eval/arrow-codebase-a0/Cargo.toml \
  --release --locked --offline
```

Only `suite` can request promotion evidence. Its scale, batching, trial count,
thresholds, and mode rotation are compiled into the contract:

```bash
"$AB_A0_TARGET/release/ab-codebase-arrow-a0" suite \
  --output /tmp/ab-arrow-data-plane-a0-canonical.json
```

Use the explicitly non-promotable command for smoke or sensitivity work:

```bash
"$AB_A0_TARGET/release/ab-codebase-arrow-a0" diagnostic-suite \
  --documents 1000 \
  --batch-rows 1024 \
  --trials 3
```

The suite launches one fresh child process per mode/trial. This prevents a
previous allocator high-water mark from contaminating the next mode. The JSON
receipt carries all raw trials, median metrics, workload/schema identities,
non-authority flags, environment facts, and the final gate decision.
`diagnostic-suite` may report a complete measurement and provisional resource
gate results, but its strategies always remain ineligible, its recommendation
is always `no_candidate`, and its status is `diagnostic_only`.
`--output` uses create-new semantics and refuses to overwrite an existing
receipt.

## Frozen decision gates

- exact semantic digest/count equality across every trial;
- canonical evidence is exactly 100,000 documents, 4,096 accumulated rows,
  and nine trials per mode;
- each mode occupies each order position exactly three times;
- bounded paths never exceed `batch_rows` in their shared typed accumulator,
  and reported live logical rows include extractor output plus overlapping
  native/Arrow representations;
- build-time Git revision, clean state, release profile, nested `Cargo.lock`
  SHA-256, tracked Git-index content manifest, target, actual optimization
  level, debug assertions, rustflags, compiler version, runtime worktree
  identity, child build identity, and executable SHA-256 are bound
  automatically; all tracked files invalidate the build identity cache;
- source and executable identities must remain unchanged before and after the
  full suite, and each child must report the same executable SHA-256;
- each receipt's row totals, flush count, declared bound, table batch counts,
  maximum Arrow batch rows, positive timing, and non-authority flags are
  recomputed and checked rather than trusted as labels;
- Linux peak RSS reduction is at least 30% versus `full-vec`;
- elapsed-time regression is at most 10% versus `full-vec`;
- a candidate must pass both gates in at least seven of nine paired trials;
- when both bounded candidates qualify, Arrow must improve RSS or elapsed time
  by at least 5% without regressing the other metric, in the median and at
  least seven Arrow-vs-native paired trials;
- if both candidates qualify, a material Arrow advantage is selected, a
  sub-material advantage defaults to native, and a genuine RSS/time trade-off
  is reported as `tradeoff_indeterminate`.

If Arrow does not add incremental value, `native_chunk` is the preferred
candidate when it passes the two resource gates. A negative result is a valid
A0 outcome; it is not an implementation failure.

## Honest limits

- The frozen generator is deterministic and extractor-representative, but it
  is not a replay of the mutable live `/Data/CascadeProjects` tree.
- Each production extractor still returns a complete `Vec` for one file. The
  receipt therefore reports `max_extractor_output_rows` separately; A0 proves
  removal of whole-workload accumulation, not a strict per-file bound.
- `peak_rss_kib` uses Linux `/proc/self/status` `VmHWM`. Other operating systems
  compile and run semantic tests but produce no promotion-grade RSS evidence.
- The harness models extraction/materialization only. It never opens SQLite and
  does not measure transaction insertion, page cache, WAL, or index rebuilds.
- Arrow interoperability is not counted as incremental value without a measured
  consumer. Flight, DataFusion, C Data FFI, C Device, and GPU buffers remain out
  of scope.
- Arrow currently copies strings from Rust-owned extractor rows. The live-row
  bound is a logical-row bound, not a byte-exact allocator proof.
- Results are single-host CPU evidence and do not authorize MI50/ROCm work.
- The identity chain is provenance and drift detection, not a signed or fully
  reproducible-build attestation.
