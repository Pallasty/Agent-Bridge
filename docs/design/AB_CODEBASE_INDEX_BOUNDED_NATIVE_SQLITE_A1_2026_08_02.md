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
  The legacy implementation was factored through a private timing seam for A1
  evidence, so the defensible claim is unchanged algorithm and dispatch, not
  byte-for-byte unchanged internal execution.
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

Each fault child is globally sequence/PID/cgroup/path bound to the same base
preflight. It records the whole three-table typed digest, target/other-root and
sentinel digests, `sqlite_sequence`, schema/page/freelist/integrity state, and
the main-file SHA. An injected rollback can leave an uncommitted WAL frame
(observed as 4,152 bytes at 4 KiB page size); that is not a logical commit. The
receipt retains the raw 32-byte header and validates SQLite magic, format
version, encoded page size, and frame-length layout before requiring a separate
`wal_checkpoint(TRUNCATE)` cleanup to prove zero WAL bytes. This deliberately
does not claim frame-checksum, commit-frame, torn-write, or crash-durability
validity. Cleanup may change only the physical main-file SHA; every logical and
schema field must stay equal.

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
  record its exact PID set, `memory.peak`, and `memory.stat` anon/file/shmem
  values;
- copy each trial database inside its transient child before opening SQLite, so
  trial-local database cache/setup contributes to that child's high-water mark;
- record process `VmHWM`, `getrusage` max RSS, `/proc/self/io`, page faults,
  staging bytes, and main DB/WAL/SHM bytes;
- keep staging I/O separate from authoritative WAL evidence;
- after base preflight, pass a 30-second/1-Hz quiet window for CPU39 and SMT
  sibling79 (both at least 95% overall idle and 90% in every bucket, CPU/memory/
  I/O `some` plus memory/I/O `full` PSI bounded, no cargo/rustc/rustdoc), then
  bind the sole PID and every cgroup thread to CPU39, set the default
  `CPUWeight=100` explicitly so direct CPU-controller counters exist, require a
  domain cgroup with no descendants or observed CPU throttling, and require at
  most 5% external activity on CPU39 and sibling79. The transient service applies
  `CPUAffinity=39`, native-architecture seccomp, `NoNewPrivileges`, and a deny
  rule for every later `sched_setaffinity`; both endpoints independently require
  every enumerated TID to retain exactly CPU39 affinity.
- At each endpoint, perform an absolute one-millisecond `CLOCK_MONOTONIC` sleep
  and prove a real depart by requiring `RUSAGE_THREAD.ru_nvcsw` to increase;
  then read direct-cgroup `cpu.stat before`, `/proc/schedstat` v17 CPU39,
  `/proc/stat` CPU39/79, and `cpu.stat after` in that order. The own-CPU lower
  bound is the inner `usage_usec` delta minus its 999-nanosecond floor error and
  the complete end sleep-deadline-to-schedstat wall upper bound. It is
  checked-subtracted from CPU39's scheduled-runtime outer bound. Operation time
  is independently bracketed by monotonic timestamps and its denominator loses
  two clock-resolution units; the assessor also mirrors the producer's rule
  that the enclosing Unix sample span cannot be shorter than that operation.
  Underflow or ordering drift fails closed; ratios use ceiling division and are
  never capped.
- Add the printed CPU39 IRQ/softirq/steal deltas with one `USER_HZ` tick per
  field as a deliberately conservative side charge. Keep CPU79 on a separate
  six-non-idle-field `delta+6` `/proc/stat` gate: CPU39's forced context switch
  cannot flush a continuously current CPU79 task. Because this host has no IRQ
  time accounting, these printed counters are not promoted into a claim about
  all short interrupt wall time. The entire contract remains frozen-host,
  evaluator-only interference control rather than general Linux isolation.

The explicit-parent boolean is only a routing fact; it is not disk-backed
proof by itself. Shared login-session cgroup counters are diagnostic only and
cannot admit a canonical result. A separately labelled fuseblk run may measure
live-substrate external validity, but is non-gating and cannot be combined with
the ext4 canonical estimates. The warm generated corpus is deliberately shared
between arms and may remain charged to the orchestrator cgroup; canonical
`memory.peak` custody covers each child's local database copy/staging work, and
process RSS is the primary decision metric. No total-host page-cache claim is
made.

## Canonical comparison

The workload is frozen to the A0 generator and semantic contract:

- 100,000 documents across Rust, Python, TypeScript, and Go;
- 500,000 symbols, 225,000 imports, and 675,000 calls;
- combined semantic digest
  `c26dd0d5f2b3844113f1030128cbfad1506b81cec2d13b585649c5b4057a3099`;
- batch size 4,096;
- ten paired blocks and twenty fresh child processes;
- eight additional fresh, isolated fault children, for 28 globally unique and
  non-overlapping child identities;
- exactly five FullVec-first and five staged-native-first blocks.

Every pair starts from equivalent preseeded authoritative databases. Canonical
admission is fail-closed on source/build/executable drift, missing measurements,
non-release builds, dirty tracked source, non-disk staging, semantic/schema/page
drift, or an invalid trial schedule.

Canonical output is also fail-closed: terminal and raw paths must be
create-new, absolute, already canonical `/home` ext4 paths outside both source
and trial roots. Raw evidence is file- and directory-synced before explicit
suite cleanup; only a successful cleanup permits the terminal receipt. A
retained `.raw.json` without the requested terminal file is therefore
nonterminal forensic evidence, not a canonical result.

A separate preflight child validates the frozen base database so its full-row
walk cannot contaminate a measured child's non-resettable high-water marks.
The same clean executable also runs all eight deterministic failpoints from
child-local copies of that base. Every failure receipt is bound to its frozen
case ordinal and must match its expected marker and
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
foreign-key invariants. A live canonical attempt additionally exposed the
non-atomic ordering of `/proc/stat` and `/proc/self/stat`; attempt11 then proved
that even a process-clock bracket cannot reconcile scheduler `sum_exec_runtime`
with CPU-state `/proc/stat` accounting for the dynamic multithreaded A1
workload. The former `+6/-8` proof covered `USER_HZ` serialization error, not
the error between those underlying kernel accounting domains, so no empirical
tolerance was added. Dedicated RED-to-GREEN contracts now guard the aligned
direct-cgroup/schedstat interval, absolute blocking-switch deadline, end-current
slice deduction, monotonic operation bracket, CPU79 fallback, upward rounding,
all-thread CPU39/seccomp/cgroup custody, no-throttle condition, and assessor
rejection of forged raw or derived evidence.

The final result, raw receipt identity, performance decision, and any A2
nomination will be appended only after a clean release build and the frozen
canonical suite.
