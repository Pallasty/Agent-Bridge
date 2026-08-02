# AB codebase-index A1 evaluator

This nested Rust workspace is an evaluation-only gate for the default-off A1
`codebase_index` candidate. It compares the unchanged FullVec path with the
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
contract pins those services to logical CPU 39 while excluding SMT sibling 79,
and records kernel, microcode, libc/allocator, systemd, load, and pressure
context. Each service has a 1,800-second runtime cap, control-group kill mode,
a 30-second stop timeout, and collection enabled; a timeout must also prove the
unit is no longer active.

```bash
mkdir -p /home/pallasting/.cache/ab-codebase-index-a1-eval

"$AB_A1_EVAL_TARGET/release/ab-codebase-index-a1" canonical-suite \
  --trial-root /home/pallasting/.cache/ab-codebase-index-a1-eval \
  --output /home/pallasting/.cache/ab-codebase-index-a1-canonical.json
```

The output path must not already exist. Canonical JSON is written with
create-new semantics and `sync_all` before the terminal decision is returned.

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
performance children and all eight fault children. Each child receives a new
byte-for-byte copy; no measured child prepares the base fixture. This single
preflight also establishes the frozen warm-cache policy before pair 0.

Each run emits a raw evidence packet that includes:

- child PID, sequence, start/finish time, observed AB/BA order, elapsed time,
  `/proc/self/io`, minor/major faults, VmHWM, and `getrusage` RSS;
- transient-cgroup identity, process count, `memory.current`, `memory.peak`,
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
an independent resource guard, while exact before/after/delta reconciliation of
anon/file/shmem rejects an apparent RSS win built from inconsistent cache
accounting.

## Decision and failure atomicity

The assessor uses paired log-ratio medians, not a ratio of independently sorted
medians, so heteroscedastic pairs cannot produce a false green. A canonical
candidate requires:

- median process-RSS reduction of at least 30%, no more than 10% median elapsed
  regression, no more than 5% median cgroup-peak regression, and at least 8/10
  pairs passing all three;
- exact anon/file/shmem before/after/delta reconciliation for every canonical
  measurement, preventing unaccounted cache shifting;
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
an identical raw rollback snapshot, stable PRAGMAs, a successful post-fault
query on the same connection, and staging cleanup.

## Exit and retention contract

- `0`: diagnostic completed, or canonical evidence and thresholds passed;
- `1`: preflight/operational failure (no canonical decision claim);
- `2`: canonical raw receipt was durably written but evidence was invalid;
- `3`: canonical raw receipt was durably written and valid, but thresholds
  failed.

Canonical raw evidence is retained outside the temporary suite directory and
SHA-bound into the terminal receipt. The suite directory must close
successfully before the terminal receipt can claim cleanup; cleanup failure is
fail-closed rather than relabeled as a result.
