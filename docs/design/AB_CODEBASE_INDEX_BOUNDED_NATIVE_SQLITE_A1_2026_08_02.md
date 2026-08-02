# AB codebase-index bounded native SQLite A1

Date: 2026-08-02

Status: implementation and canonical evaluation in progress

## Decision under test

Arrow A0 selected ordinary bounded Rust batches over Arrow for the current
`codebase_index` boundary. A1 tests whether that choice still wins after the
real SQLite replacement transaction, WAL, page cache, rollback, filesystem,
and end-to-end process memory are included.

The candidate is `native_chunk_staged_v0`:

1. the production file walker and extractors emit owned rows into one bounded
   `TypedBatch`;
2. batches are inserted into a private SQLite staging database with a monotonic
   sequence per logical table;
3. only after extraction and staging finish is the single `indexed_at` value
   sampled;
4. one authoritative savepoint deletes the exact root and replays symbols,
   imports, and calls in legacy table and row order;
5. the staging directory is removed after the authoritative commit.

The four constraints that force staging are: bounded whole-repository heap,
post-extraction timestamp sampling, a short authoritative write-lock window,
and exact replacement atomicity. Direct chunk writes to the authoritative DB
would retain a write transaction for the complete filesystem walk.

## Authority boundary

- The Cargo feature `codebase-index-bounded-native-a1` is off by default.
- The candidate and measured FullVec seam are Rust APIs only; there is no MCP,
  daemon, retrieval, deployment, or live-database caller.
- Normal builds retain the FullVec `StateStore::codebase_index` behavior.
- A successful benchmark is necessary but not sufficient for changing any
  dispatch path. A1 may only nominate a separately reviewed A2 candidate.
- A1 grants no GPU, MI50, ROCm, Arrow Flight, DataFusion, C Data, or C Device
  authority.

## Frozen semantics

| Property | Required evidence |
| --- | --- |
| Root replacement | three exact-root deletes and one successful authoritative commit |
| Atomicity | every injected staging/delete/partial-replay/pre-commit failure preserves the complete prior generation |
| Row values | field-complete, order-sensitive FullVec/native equality, including IDs, aliases and caller/callee values |
| Embedding | newly indexed symbols contain SQL `NULL`, distinct from an empty BLOB |
| Timestamp | extraction completes first; every row from one generation shares one value |
| Isolation | a second root remains byte-exact, including IDs, timestamp and BLOB bytes |
| Schema | normalized `sqlite_schema`, `schema_meta`, schema/user versions remain unchanged |
| Database attachment | staging is a separate connection and never appears in authoritative `database_list` |
| Connection policy | authoritative connection PRAGMAs are captured read-only before/after and remain exact |
| Health | `integrity_check=ok` and `foreign_key_check` is empty |

`batch_rows` must be in `1..=65,536`. The canonical batch size is 4,096.
The logical live-row declaration is `batch_rows + max_extractor_output_rows -
1`; it is not a byte-exact allocator bound.

## Failure model

The evaluation-only failpoints cover:

- a flushed staging batch;
- each of the three authoritative deletes;
- partial symbol, import, and call replay;
- the point immediately before commit.

These prove application-error rollback through SQLite savepoint semantics.
They do not simulate `xWrite`, `xSync`, torn writes, process kill, kernel crash,
or power loss. No durability claim beyond normal SQLite behavior is made
without a faulting VFS or equivalent owned laboratory.

Post-commit staging cleanup cannot truthfully turn the already committed index
operation into an error. Cleanup failure is therefore a warning plus
`staging_cleanup_succeeded=false`; it may leave a private staging directory and
is a residual operational risk.

## Filesystem and memory accounting

The system temporary directory on the evaluation host is tmpfs and `/Data` is
NTFS/FUSE. The apparent default AB path under `$HOME/.local` also resolves
through a symlink onto `/Media/...` fuseblk; `/home` ext4 is therefore a
controlled causal medium, not a claim about the current live persistence
stack. Moving rows into `/tmp` would shift pressure into shmem/page cache, and
mixing filesystems inside a pair would confound the algorithm comparison.
Canonical trials therefore must:

- place authoritative and staging databases under an isolated `/home` ext4
  directory on the same device;
- pass an explicit per-trial staging parent;
- capture the actual ephemeral staging file path, device, mount point, and
  filesystem type before cleanup rather than inferring them from the requested
  parent;
- reject tmpfs, fuseblk, unknown media, or a device mismatch;
- launch every measured child in a unique transient user-systemd cgroup and
  record its `memory.peak` plus `memory.stat` anon/file/shmem values;
- record process `VmHWM`, `getrusage` max RSS, `/proc/self/io`, page faults,
  staging bytes, and main DB/WAL/SHM bytes;
- keep staging I/O separate from authoritative WAL evidence.

The explicit-parent boolean is only a routing fact; it is not disk-backed
proof by itself. Shared login-session cgroup counters are diagnostic only and
cannot admit a canonical result. A separately labelled fuseblk run may measure
live-substrate external validity, but is non-gating and cannot be combined with
the ext4 canonical estimates.

## Canonical comparison

The workload is frozen to the A0 generator and semantic contract:

- 100,000 documents across Rust, Python, TypeScript, and Go;
- 500,000 symbols, 225,000 imports, and 675,000 calls;
- combined semantic digest
  `c26dd0d5f2b3844113f1030128cbfad1506b81cec2d13b585649c5b4057a3099`;
- batch size 4,096;
- ten paired blocks and twenty fresh child processes;
- exactly five FullVec-first and five staged-native-first blocks.

Every pair starts from equivalent preseeded authoritative databases. Canonical
admission is fail-closed on source/build/executable drift, missing measurements,
non-release builds, dirty tracked source, non-disk staging, semantic/schema/page
drift, or an invalid trial schedule.

A separate preflight child validates the frozen base database so its full-row
walk cannot contaminate a measured child's non-resettable high-water marks.
The same clean executable also runs all eight deterministic failpoints from
copies of that base. Every failure receipt must match its expected marker and
prove an exact full-field rollback, stable schema/PRAGMAs/page state, connection
usability, and staging cleanup. All preflight, performance, and fault receipts
bind to one base SHA-256. Trials use an explicitly labelled warm-cache protocol;
fresh process does not imply cold page cache.

Candidate thresholds are:

- median peak RSS reduction at least 30%;
- median isolated-cgroup total peak regression no worse than 5%, with the
  guardrail passing in at least 8 of 10 pairs;
- median end-to-end elapsed regression no worse than 10%;
- joint RSS and elapsed pass in at least 8 of 10 pairs;
- median authoritative-transaction regression no worse than 10%, and no worse
  than 20% in at least 8 of 10 pairs;
- median main-WAL byte/frame regression no worse than 5%, and the per-pair WAL
  gate passes in at least 8 of 10 pairs;
- exact semantic, schema, `page_count`, and `freelist_count` equality per pair.

Diagnostic runs may vary scale and batch size but can never authorize
promotion.

## Current verification

The implementation test ladder contains genuine RED-to-GREEN gates for the
candidate API, authoritative failpoints, explicit staging placement, and the
measured FullVec timing seam. It also characterizes field-complete FullVec
equivalence, root isolation, cleanup, schema, page/freelist, integrity, and
foreign-key invariants.

The final result, raw receipt identity, performance decision, and any A2
nomination will be appended only after a clean release build and the frozen
canonical suite.
