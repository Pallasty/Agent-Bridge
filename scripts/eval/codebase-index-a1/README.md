# AB codebase-index A1 evaluator

This nested Rust workspace is an evaluation-only gate for the default-off A1
`codebase_index` candidate. It compares the legacy FullVec algorithm/dispatch with the
feature-gated staged-native path through production store seams. It never uses
the live Agent Bridge database, changes production dispatch, or authorizes
runtime adoption.

## Diagnostic evidence

The diagnostic executes real SQLite work in fresh child processes, but its
receipt is always non-promotable. `/Data` is acceptable here precisely because
the result cannot cross the canonical authority gate:

```bash
export AB_A1_EVAL_TARGET=/tmp/ab-codebase-index-a1-target

CARGO_TARGET_DIR="$AB_A1_EVAL_TARGET" \
  cargo test --manifest-path scripts/eval/codebase-index-a1/Cargo.toml \
  --features staged-native --all-targets --locked --offline

CARGO_TARGET_DIR="$AB_A1_EVAL_TARGET" \
  cargo build --manifest-path scripts/eval/codebase-index-a1/Cargo.toml \
  --features staged-native --release --locked --offline

"$AB_A1_EVAL_TARGET/release/ab-codebase-index-a1" diagnostic-suite \
  --documents 100 --batch-rows 128 --pairs 2 \
  --trial-root /Data/CascadeProjects
```

Diagnostic mode records shared-cgroup and storage facts as metadata rather
than silently treating them as controlled evidence. A successful diagnostic
exit means only that its bounded execution and receipt contract completed.

## Canonical controlled medium

Canonical trials must use an existing absolute directory under `/home` on
`ext4`. The copied database and the staged-native temporary database must be on
that same device. This is a controlled causal medium for comparison; it is not
the live/default AB persistence substrate. The evaluator resolves and records
the configured live database's path, mount, filesystem, and device as
non-gating host context and never opens it.

The canonical runner also requires a clean, release, `staged-native` build
whose Git revision, tracked-source digest, lockfile digest, executable digest,
target/profile, empty encoded rustflags, and runtime identities all agree. A
working per-user systemd manager is required because every measured child and
fault child runs in a uniquely named transient user service. The frozen host
contract pins the service process to logical CPU 39 and separately observes its
non-allocated SMT sibling 79. It records kernel, microcode, libc/allocator,
systemd, load, and pressure context. Each service has a 1,800-second runtime
cap, control-group kill mode, a 30-second stop timeout, and collection enabled.
It also enables `NoNewPrivileges`, limits the seccomp ABI to native syscalls,
and denies `sched_setaffinity` after systemd has applied `CPUAffinity=39`.
Every stop/show client is itself bounded; success or timeout must prove the unit
reached an inactive/dead state (or was collected) and that any retained cgroup
reports `populated=0` with no processes.

After base preflight, canonical execution requires a fresh 30-second, 1 Hz
host-quiet window on CPU 39 and sibling 79. Both CPUs require at least 95%
overall idle and 90% idle in every bucket. CPU/memory/I/O `some` PSI must be at
most 1%, memory/I/O `full` PSI at most 0.1%, and no `cargo`, `rustc`, or
`rustdoc` identity may appear. Every performance child then requires a sole
cgroup PID, a domain cgroup with no descendants, an explicit default
`CPUWeight=100` that activates direct CPU-controller evidence, no observed CPU
throttling, and both external CPU39 activity and sibling-79 activity at or below
5%. Both endpoints enumerate every cgroup TID and require its allowed CPU set to
be exactly `{39}`; a real transient smoke also proves that the seccomp contract
rejects a later affinity change.

The child endpoints retain the five raw host-wide `/proc/pressure/*` counters
and require monotonic, arithmetically valid deltas. Those operation-window PSI
values are observational rather than eligibility thresholds: the measured
database work contributes to the same global counters, so they cannot identify
external interference. The frozen PSI thresholds apply only to the 30-second
preflight window. CPU39, sibling79, cgroup ownership, throttling, affinity, and
seccomp remain the per-child interference gates.

Each endpoint performs an absolute one-millisecond `CLOCK_MONOTONIC` sleep and
requires `RUSAGE_THREAD.ru_nvcsw` to advance before sampling. It then brackets
`/proc/schedstat` v17 CPU39 and `/proc/stat` with direct-cgroup `cpu.stat`
reads. The inner own-CPU lower bound uses `end.cpu_stat_before -
start.cpu_stat_after`, charges the one-microsecond output floor, and deducts the
entire end sleep-deadline-to-schedstat interval plus clock resolution. That
lower bound is checked-subtracted from the CPU39 scheduled-runtime outer bound;
contradictions fail instead of clamping. The ratio uses the measured operation
interval minus two monotonic-clock resolution units and always rounds upward.
The assessor independently requires the enclosing Unix sample span to be at
least that operation interval, preventing a coordinated denominator forgery.

On the frozen `USER_HZ=100` host, the printed `/proc/stat`
IRQ/softirq/steal deltas receive one tick per field as an additional,
potentially double-counted side charge. CPU79 remains a separate six-field
non-idle `delta+6` output-accounting gate because a CPU39 context switch cannot
flush CPU79 schedstat. The host has no IRQ-time accounting, so neither printed
side charge nor sibling gate is claimed as a strict upper bound for every short
interrupt or every Linux configuration. This is conservative evaluator-only
interference control for the frozen host, not host-wide CPU isolation.

```bash
mkdir -p /home/pallasting/.cache/ab-codebase-index-a1-eval

"$AB_A1_EVAL_TARGET/release/ab-codebase-index-a1" canonical-suite \
  --trial-root /home/pallasting/.cache/ab-codebase-index-a1-eval \
  --output /home/pallasting/.cache/ab-codebase-index-a1-canonical.json
```

The output must be an absolute, already-canonical `/home` ext4 path whose parent
already exists, outside both the source tree and trial root. Neither terminal
nor `.raw.json` path may already exist. Both use create-new semantics plus file
and parent-directory `sync_all`; raw evidence is written before suite cleanup,
and the terminal receipt only afterward.

## Frozen plan and custody

The canonical plan is 100,000 documents, 1,400,000 extracted rows, `B=4096`,
and ten alternating AB/BA pairs with exact 5/5 first-position balance. The
receipt binds both the frozen generator metadata and a digest of the actually
materialized corpus.

Before any measured pair, the evaluator performs one FullVec fixture build,
then seeds prior target rows with non-NULL embeddings, rows from another root,
and a non-codebase sentinel. It checkpoints and closes the database, requires
the WAL/SHM sidecars to be absent, and obtains a separate base-preflight
receipt. The same frozen base-file SHA and raw-state SHA must bind all 20
performance children and all eight fault children. Each child makes its own
byte-for-byte copy before opening the store, so trial-local database page-cache
charges contribute to that child's `memory.peak`; no measured child builds or
queries the shared base fixture. This single preflight also establishes the
frozen warm-corpus policy before pair 0.

The retained canonical raw packet contains the complete assessor `SuiteInput`
plus its assessment, so it can be deserialized and reassessed independently.
Its run evidence includes:

- child PID, sequence, start/finish time, observed AB/BA order, elapsed time,
  `/proc/self/io`, minor/major faults, VmHWM, and `getrusage` RSS;
- host-quiet bucket deltas for CPU39 and sibling79, plus per-child CPU/process,
  sibling, PSI, all-thread affinity/seccomp, cpuset, conservative counter
  bounds, and competing-build-process identities;
- transient-cgroup identity, exact process-ID set, `memory.current`, `memory.peak`,
  `memory.max`, and `memory.stat` anon/file/shmem components;
- database/WAL/SHM bytes, validated WAL layout and frames, checkpoint/reset
  state, page/freelist counts, schema and semantic digests, schema metadata,
  integrity and foreign-key checks, and SQLite build identity;
- connection-local production PRAGMAs read on the authoritative store
  connection before and after the operation;
- raw target, generation, other-root, and non-codebase-sentinel digests; and
- staged batch count, live-row bound, staging-file size/path/device/mount,
  commit/autocommit state, and cleanup result while the staging file exists.

Canonical children must be alone in their transient cgroup. Primary process
RSS is accepted only when it equals `max(VmHWM, getrusage)`. The cgroup peak is
an independent resource guard and includes child-local database-copy plus
staging/database work. Exact before/after/delta reconciliation of
anon/file/shmem rejects internally inconsistent evidence. The generated corpus
is intentionally warm and shared; pages first charged to the orchestrator are
common to both arms and are not claimed as child-private page-cache evidence.
Process RSS remains the primary memory decision metric, and this gate does not
claim complete host page-cache attribution.

## Decision and failure atomicity

The assessor uses paired log-ratio medians, not a ratio of independently sorted
medians, so heteroscedastic pairs cannot produce a false green. A canonical
candidate requires:

- median process-RSS reduction of at least 30%, no more than 10% median elapsed
  regression, no more than 5% median cgroup-peak regression, and at least 8/10
  pairs passing all three;
- exact anon/file/shmem before/after/delta reconciliation for every canonical
  measurement, preventing arithmetic or self-inconsistent cache false-greens;
- authoritative transaction median regression no more than 10%, with at least
  8/10 pairs no worse than 20%; and
- WAL byte and frame median regressions no more than 5%, with at least 8/10
  pairs passing both.

Schema, semantic, generation, page/freelist, SQLite, base-fixture, sentinel,
and authoritative-PRAGMA custody must also match exactly within each pair.

The canonical run executes the same staged-native binary through eight injected
failure points: after staging batch 1, after each of the three deletes, after
one symbol/import/call replay row, and immediately before commit. Every case
starts from a fresh base copy and must observe the exact expected error marker,
an identical raw rollback snapshot across all codebase tables and
`sqlite_sequence`, stable PRAGMAs, a successful post-fault query on the same
connection, and staging cleanup. Fault children prove an empty WAL start. A
rollback may leave an uncommitted WAL. The receipt retains its raw 32-byte
header and independently checks SQLite magic, format version, encoded page
size, and frame-length layout before a separate TRUNCATE cleanup proves a
zero-length WAL. The transient WAL-index sidecar is checked structurally rather
than required to remain at its initial size: it begins at 32 KiB and must occupy
exactly the regions implied by the observed WAL frame count (4,062 frames in the
first region and 4,096 in each later region). It may retain that exact size
while the connection remains open after WAL truncation. This is header/layout
evidence, not frame-checksum,
commit-frame, torn-write, or crash-durability proof. Cleanup may change only the
main-file physical SHA; logical rows, schema metadata, page/freelist state,
integrity, and foreign-key evidence must remain identical.

## Exit and retention contract

- `0`: diagnostic completed, or canonical evidence and thresholds passed;
- `1`: preflight/operational failure (no canonical decision claim);
- `2`: canonical raw receipt was durably written but evidence was invalid;
- `3`: canonical raw receipt was durably written and valid, but thresholds
  failed.

Canonical raw evidence is retained outside the temporary suite directory and
SHA-bound into the terminal receipt. The suite directory must close
successfully before the terminal receipt can claim cleanup; cleanup failure is
fail-closed rather than relabeled as a result. The suite body and explicit close
are both observed even on error. If raw evidence was already synced but cleanup
or terminal write then fails, the `.raw.json` file is deliberately recognizable
as raw-only/nonterminal evidence while the requested terminal path remains
absent.

## Accepted canonical packet

Attempt23 is the accepted packet for revision
`72ee0c93a53705a9aa544b9c495e6ec483d6e971`. It returned valid, eligible PASS
with no reasons and all five pair counters at 10/10. The paired-ratio medians
were 0.0303848877 for process RSS, 0.8812315456 for isolated-cgroup peak,
0.9146710844 for elapsed time, 0.9424897767 for authoritative transaction time,
and exactly 1.0 for both WAL bytes and frames. All eight failure receipts passed
the exact rollback and frame-derived WAL-index checks.

The terminal receipt SHA-256 is
`f2d1d754657ba56c666de93c52f622d4c932cad219b68d842053285890c87a02`.
Its retained raw packet SHA-256 is
`a92e565a4de804a266984e0267da2aa229a5c1378020c354127bacee7170d4f6`,
which exactly matches the terminal declaration. Suite cleanup succeeded and
left no trial artifacts. This PASS nominates a separate default-off A2 review;
it does not itself change normal dispatch or authorize runtime adoption.
