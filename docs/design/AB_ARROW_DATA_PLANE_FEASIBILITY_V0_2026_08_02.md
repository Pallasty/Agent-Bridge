# AB Arrow Data Plane Feasibility V0 — implementation contract

Date: 2026-08-02
State: A0 evaluation implementation; no runtime adoption authority
Durable memory: `decision_ab_arrow_data_plane_a0_goal_20260802`
Design forum: thread `#331`, start post `#5901`

## Decision being tested

The current `SqliteStore::codebase_index` extraction phase retains complete
`Vec<CodebaseSymbol>`, `Vec<CodebaseImport>`, and `Vec<CodebaseCall>` values
before the SQLite transaction begins. A0 tests whether bounded materialization
removes that visible whole-workload amplification and whether Arrow adds value
beyond the simpler native-Rust solution.

This is a feasibility experiment, not an authorization to change
`SqliteStore::codebase_index`.

## Chosen boundary

The harness lives at `scripts/eval/arrow-codebase-a0` as an independent nested
workspace with its own lock file. It depends on `ab-store` with
`default-features = false` and pins Arrow to `53.4.1`.

This location is deliberate:

- adding a root workspace member would change frozen member-count release and
  owned-lab gates;
- adding an `ab-store` feature would expose Arrow to a production storage crate;
- extending `ab-memory-columnar` would mix the codebase-index experiment with a
  stable memory-archive schema and data domain.

The root workspace, its lock file, default members, and production binaries are
unchanged.

## Evidence contract

The frozen workload generates a deterministic ordered manifest from four
language templates and unique canonical paths. Every mode calls the production
symbol/import/call extractors. Receipts bind:

- workload generator revision, document count, and manifest SHA-256;
- logical-table row counts and ordered field-complete SHA-256 values;
- three production-shaped Arrow table schemas and their fingerprints;
- configured typed-accumulator bound, observed accumulator/extractor/live-row
  maxima, and the declared logical live-row bound;
- elapsed nanoseconds and Linux process `VmHWM`;
- build-time Git revision/clean state/profile/lock SHA-256, runtime source
  identity, tracked Git-index content manifest, target/optimization/debug/
  rustflags/compiler identity, executable SHA-256, and host
  OS/architecture/kernel/CPU/RAM facts;
- `sqlite_accessed=false` and `production_write=false`.

Arrow equivalence is computed after downcasting and reading the `RecordBatch`
arrays. Hashing only the pre-conversion Rust inputs would not satisfy the gate.
All tracked repository paths invalidate the build-identity script; source and
executable identities are checked before and after the suite, and every child
must return the same executable digest. Each raw receipt is structurally
revalidated from its frozen workload row shape instead of trusting its labels.
The three Arrow schemas are cached and shared, so per-batch schema construction
does not bias Arrow elapsed time.

## Promotion rule

The only promotable configuration is 100,000 documents, a 4,096-row shared
typed accumulator, and nine fresh-process trials per mode. The rotation places
each mode in each order position exactly three times. Medians and per-trial
pairs are assessed with integer basis points:

- RSS reduction versus full Vec: at least 3000 basis points (30%);
- elapsed regression versus full Vec: at most 1000 basis points (10%);
- at least seven of nine paired trials pass both gates;
- canonical thresholds must be exactly the frozen 30%/10% values;
- semantic/workload/config/source/authority evidence must all be valid.

If only one bounded strategy qualifies, it is the candidate. If both qualify,
Arrow additionally needs a material advantage over native: at least one median
resource improves by 5% while the other does not regress, and the same rule
holds in at least seven paired trials. A cross-metric RSS/time trade-off is
explicitly `tradeoff_indeterminate`; a sub-material Arrow advantage defaults to
the simpler native candidate. If neither qualifies, the result is
`no_promotion_candidate`. Custom scale or trial counts use `diagnostic-suite`;
diagnostic measurements can be complete but are always ineligible and can
never emit a promotion recommendation.

## Non-goals

No SQLite transaction or schema change; no MCP, retrieval, ranking,
authorization, lease, replay, daemon, deployment, or current-client change; no
MI50, ROCm, power-policy, DataFusion, Flight, C Data FFI, C Device, or GPU
device-buffer work.

## Known residual boundary

The public extractors allocate one complete vector per row kind per file. A0
bounds cross-file accumulation but does not make a single unusually large file
strictly bounded. Any production follow-up must either accept that residual or
introduce streaming extractor APIs under a separate contract.
