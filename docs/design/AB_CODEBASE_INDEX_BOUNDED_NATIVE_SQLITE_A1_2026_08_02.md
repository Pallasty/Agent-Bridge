# AB codebase-index bounded native SQLite A1

Date: 2026-08-02

Status: canonical PASS; default-off A2 candidate nominated

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

### Runtime gate (default-off)

- `AB_CODEBASE_INDEX_A1_STRATEGY`
  - `native_chunk_staged_v0` or `native-chunk-staged-v0`: force the A1 staged-native
    experimental path.
  - `full_vec`, `fullvec`, `fullvec_a1`: force the legacy FullVec path (control).
  - Any other value: default-off (`None`), i.e. legacy `StateStore::codebase_index`.
- `AB_CODEBASE_INDEX_A1_BATCH_ROWS`
  - Integer in `1..=65_536` is accepted for the staged-native batch size.
  - Invalid, missing, or out-of-range values fall back to `4096`.
- `AB_CODEBASE_INDEX_A1_STAGING_PARENT`
  - Optional explicit directory for the private staging DB.
  - If unset, A1 chooses an internal temporary parent.

- `AB_CODEBASE_INDEX_A2_STRATEGY`
  - Default-off gate for the separately reviewed A2 dispatch candidate.
  - Current implementation keeps this on the same `native_chunk_staged_v0`
    implementation as A1 but uses a separate namespace and precedence.
    - `native_chunk_staged_v0` or `native-chunk-staged-v0`: force candidate
      staged-native dispatch path.
    - `full_vec`, `fullvec`, `fullvec_a1`: force baseline FullVec control.
    - Any other value: disabled (`None`).
- `AB_CODEBASE_INDEX_A2_BATCH_ROWS`
  - Integer in `1..=65_536` accepted for the candidate batch size.
  - Invalid, missing, or out-of-range values fall back to `4096`.
- `AB_CODEBASE_INDEX_A2_STAGING_PARENT`
  - Optional explicit directory for the private staging DB used by the
    candidate path.

- Precedence: A2 namespace is checked before A1. If `AB_CODEBASE_INDEX_A2_*`
  is set and decodes to a valid strategy, A1 values are ignored for that
  `codebase_index` call. If A2 is unset or cannot be decoded (including
  malformed/unknown strategy values), A1 namespace may still select behavior.

The feature-gated `SqliteStore::codebase_index_with_env_dispatch` seam returns
the normal stats together with a structured dispatch receipt. The receipt names
the selected namespace (`a2`, `a1`, or `default`), preserves the requested
strategy string, records the effective strategy and batch size, indicates
whether a staging parent was configured, and explains fallback causes such as
`a2_strategy_unknown`. The ordinary `StateStore::codebase_index` path uses the
same resolver but intentionally discards this receipt, so this unit adds
observability without changing default-off authority.

Package-level verification after the receipt change passed with the bounded
native feature enabled: 487 `ab-store` unit tests and 21 A1/A2 integration
tests passed; the single `ab-store` doc-test was ignored by its existing
annotation and no test failed. A default-feature `cargo check -p ab-store`
also passed. The package still emits two pre-existing warnings (a Greek
identifier confusable and an unnecessary `mut`); neither is in this unit.

## Change-boundary audit

The intended A1/A2 slice is limited to the dispatch/data-plane definitions in
`crates/store/src/lib.rs`, the SQLite implementation in
`crates/store/src/sqlite.rs`, its bounded-native integration test, and this
design record. The current worktree also contains unrelated edits under
`crates/bridge/`; those files are outside this unit and must not be included in
an A2 adoption change. `crates/store/src/lib.rs` also contains an existing
feature-module ordering/reformatting hunk unrelated to the dispatch receipt;
it remains unclaimed until ownership is explicitly resolved. Consequently,
this unit is validated but not yet represented by a clean, isolated commit.

## Non-promotable dogfood

The evaluation-only diagnostic suite was run from a fresh temporary target with
100 generated documents, `B=128`, and two FullVec/staged-native pairs. The
evaluator tests passed, the diagnostic receipt was internally valid, and both
arms executed through fresh child processes against isolated SQLite copies.
The receipt also proved `live_database_touched=false`, `production_write=false`,
and `runtime_adoption_authorized=false`; staged-native cleanup and authoritative
transaction invariants held for the diagnostic cases.

The result remains deliberately non-promotable: the trial used `/tmp` tmpfs,
the shared login-session cgroup, a dirty tracked tree, and a diagnostic-scale
workload. The assessor therefore returned `eligible=false` solely under the
diagnostic evidence rule. This is dogfood of the execution path, not a new
canonical performance result and not permission to enable A2.

If `AB_CODEBASE_INDEX_A1_STRATEGY` is unset/unknown, the staged-native path is not
reachable from the production `codebase_index` seam, even when batch/staging options
are present. To run a staged-native path, either set the strategy env var (for
evaluation) or call `codebase_index_with_a1_strategy` explicitly.

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
validity. The WAL-index is transient and may grow while the connection remains
open. Its receipt must start at one 32 KiB region and then match the exact
frame-derived layout: the first region covers 4,062 WAL frames and every later
region covers 4,096. WAL truncation may therefore leave this structurally exact
SHM allocation in place. Cleanup may change only the physical main-file SHA;
every logical and schema field must stay equal.

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
- Retain operation-window `/proc/pressure/*` start/end counters and require
  monotonic, recomputable deltas, but treat them as observations rather than
  per-child eligibility thresholds. They are host-wide and include pressure
  caused by the measured workload itself. The preregistered PSI bounds remain
  attached to the 30-second preflight; per-child external-interference gates
  remain CPU39, sibling79, cgroup ownership/throttling, affinity, and seccomp.
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

Canonical attempt15 is retained as nonterminal diagnostic evidence. All ten
pairs and every aggregate RSS, cgroup-peak, elapsed, transaction, and WAL gate
were green, but the assessor correctly withheld eligibility because three
evaluator contracts were misbound: runtime provenance invoked a nonexistent
`systemd` executable instead of the installed `systemctl`; failure receipts
mistook normal frame-derived WAL-index region growth for rollback drift; and
operation-window global PSI thresholds attempted to classify workload-created
I/O pressure as external noise. RED-to-GREEN regressions now bind the installed
systemd version, the exact SQLite WAL-index region boundaries, high monotonic
operation PSI as observational, and counter reversal as invalid. A fresh release
canonical run is still required; attempt15 cannot authorize promotion.

## Canonical result

Canonical attempt23 completed on the frozen plan with exit code 0. The
assessor returned `evidence_valid=true`, `eligible=true`,
`decision_pass=true`, and no reasons. The result therefore passes A1 and
nominates `native_chunk_staged_v0` for a separately reviewed, still default-off
A2 integration candidate. It does not change production dispatch or grant
runtime adoption authority.

Identity and custody:

- source revision:
  `72ee0c93a53705a9aa544b9c495e6ec483d6e971`;
- release binary SHA-256:
  `cd164119dffd7dd56f467f2799f8af72232b0eb78670b671734b55c9c2257b82`;
- terminal receipt SHA-256:
  `f2d1d754657ba56c666de93c52f622d4c932cad219b68d842053285890c87a02`;
- raw receipt SHA-256:
  `a92e565a4de804a266984e0267da2aa229a5c1378020c354127bacee7170d4f6`;
- terminal receipt:
  `/home/pallasting/.cache/ab-a1-canonical-72ee0c93-bqbe9l/results/canonical-attempt23.json`;
- retained raw receipt: the same path with `.raw.json`; its actual digest
  exactly matches the terminal declaration, and terminal/raw `input` plus
  `assessment` are equal;
- raw evidence was file- and directory-synced before suite cleanup;
  `suite_cleanup_succeeded=true`, retained suite artifacts are false, and the
  trial root is empty.

The build, runtime-before, and runtime-after identities agree on the clean
release revision, tracked-source/lockfile/executable digests, Rust 1.96.0,
`staged-native`, empty encoded rustflags, and no profile override. Runtime
provenance binds Linux 7.0.0-27, Xeon Gold 6138, glibc 2.43, and
`systemd 259 (259.5-0ubuntu3)`. The inner quiet-window gate passed with CPU39
at 99.16% overall/95.00% worst-bucket idle and sibling79 at 98.20%/91.91%; no
competing Cargo/Rust process was observed. Across all twenty measured arms,
the conservative external-activity maxima were 0.58% on CPU39 and 3.01% on
sibling79, both below the frozen 5% bound.

All five pair counters are 10/10: joint RSS/elapsed/cgroup peak, isolated
cgroup peak, cache reconciliation, authoritative transaction, and WAL. Every
individual pair assessment is green. The decision statistic is the geometric
median of paired ratios; ordinary arm medians below are descriptive only.

| Metric | FullVec ordinary median | Staged-native ordinary median | Paired-ratio median | Candidate change |
| --- | ---: | ---: | ---: | ---: |
| Process peak RSS | 548,759,552 B | 16,672,768 B | 0.0303848877 | -96.9615% |
| Isolated cgroup peak | 2,231,975,936 B | 1,966,872,576 B | 0.8812315456 | -11.8768% |
| End-to-end elapsed | 46.069841421 s | 42.174792092 s | 0.9146710844 | -8.5329% |
| Authoritative transaction | 37.263682350 s | 35.344984234 s | 0.9424897767 | -5.7510% |
| Main WAL bytes | 821,045,992 B | 821,045,992 B | 1.0000000000 | 0.0000% |
| Main WAL frames | 199,283 | 199,283 | 1.0000000000 | 0.0000% |

The bounded path emitted 342 batches for 1,400,000 rows at `B=4096`, retained
at most 4,096 accumulator rows with a declared live-row bound of 4,113, and
used a 260,976,640-byte same-device ext4 staging database. All ten staged arms
proved explicit staging placement, committed the staging and authoritative
transactions, restored authoritative autocommit, and removed staging state.

All eight injected application failures were observed at their exact marker.
Every receipt preserved the complete logical rollback snapshot, schema,
PRAGMAs, page/freelist state, other root, non-codebase sentinel, connection
usability, and staging cleanup. Post-fault WAL cleanup reached zero bytes in
every case. The observed WAL frame/structurally exact SHM pairs were:

| Failpoint | WAL frames | SHM bytes before -> retained after cleanup |
| --- | ---: | ---: |
| after staging batch | 0 | 32,768 -> 32,768 |
| after symbol delete | 49,702 | 32,768 -> 425,984 |
| after import delete | 83,263 | 32,768 -> 688,128 |
| after call delete | 176,413 | 32,768 -> 1,441,792 |
| after symbol rows | 176,414 | 32,768 -> 1,441,792 |
| after import rows | 185,476 | 32,768 -> 1,507,328 |
| after call rows | 187,193 | 32,768 -> 1,507,328 |
| before commit | 199,178 | 32,768 -> 1,605,632 |

This result selects bounded native SQLite staging over FullVec for the current
`codebase_index` replacement boundary: it removes the whole-repository row
heap while also improving the measured end-to-end, transaction, and isolated
cgroup peaks without changing WAL work or row semantics. Its authority remains
narrow. The evidence is a warm-cache, controlled `/home` ext4 comparison; it
does not prove complete host page-cache attribution, live fuseblk behavior,
crash durability, Arrow-wide infrastructure value, GPU behavior, or any
MI50/ROCm runtime path. Those require separate units and gates.
