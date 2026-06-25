# GTE 768 Reader Compatibility Probe

Date: 2026-06-25

Status: `READY_FOR_ATOMIC_NODE_CUTOVER_PROPOSAL / LIVE_CUTOVER_NO_GO`.

Scope: read-only copied-DB evidence for GTE 768 reader compatibility planning.
This probe inspects a pre-reindex canonical snapshot copy and a post-reindex
scratch copy. It does not prove mixed-reader support, does not run live reindex,
does not mutate any live DB, does not deploy binaries, and does not change
runtime reader environments.

## Script

Added:

```text
scripts/verify-gte-768-reader-compatibility-probe.sh
```

Contract:

```text
read_only=true
writes_db=false
runs_reindex=false
starts_or_stops_readers=false
mixed_readers_supported=false
recommendation=atomic_node_cutover_only_unless_separately_proven
```

The script refuses the live DB as input and opens inspected DBs through SQLite
read-only immutable URI mode.

## Inputs

Pre-reindex copied DB:

```text
/home/pallasting/.cache/agent-bridge/inbox/state.snapshot.20260623.checkpointed-for-aio2.db
```

Post-reindex scratch DB:

```text
/home/pallasting/.cache/agent-bridge/gte-rehearsal/2026-06-25T130030Z-canonical-snapshot-gate/state.db
```

Target:

```text
backend=gte-multilingual-base
dim=768
bytes=3072
```

Log:

```text
/home/pallasting/.cache/agent-bridge/gte-rehearsal/2026-06-25T130030Z-canonical-snapshot-gate/reader_compatibility_probe.log
```

## Command

```bash
scripts/verify-gte-768-reader-compatibility-probe.sh \
  --pre-db /home/pallasting/.cache/agent-bridge/inbox/state.snapshot.20260623.checkpointed-for-aio2.db \
  --post-db /home/pallasting/.cache/agent-bridge/gte-rehearsal/2026-06-25T130030Z-canonical-snapshot-gate/state.db \
  --strict
```

## Evidence

Pre-reindex profile:

```text
active_total=3022
embedded=3022
null_or_empty=0
dominant=backend=multilingual-e5-small dim=384 rows=1628
target_good=0
target_bad_dim=0
stale_for_target=3022

buckets:
  - backend=multilingual-e5-small bytes=1536 dim=384 rows=1628
  - backend=unknown bytes=1536 dim=384 rows=1343
  - backend=all-MiniLM-L6-v2 bytes=1536 dim=384 rows=45
  - backend=fnv1a-hash-384 bytes=1536 dim=384 rows=6
```

Post-reindex scratch profile:

```text
active_total=3022
embedded=3022
null_or_empty=0
dominant=backend=gte-multilingual-base dim=768 rows=3022
target_good=3022
target_bad_dim=0
stale_for_target=0

buckets:
  - backend=gte-multilingual-base bytes=3072 dim=768 rows=3022
```

Probe verdict:

```text
post_reindex_invariant=pass
mixed_reader_support=not_proven
recommended_mode=atomic_node_cutover_only
probe_result=READY_FOR_ATOMIC_NODE_CUTOVER_PROPOSAL
status=READY_FOR_ATOMIC_NODE_CUTOVER_PROPOSAL warnings=0
```

## Decision

The copied-DB evidence is coherent enough to draft an atomic node cut-over
proposal:

- the pre-reindex snapshot is entirely stale for the GTE target, as expected;
- the post-reindex scratch DB has all 3022 active embeddings on
  `gte-multilingual-base`;
- all post-reindex active embeddings have the expected 3072-byte width;
- no target-backend wrong-dimension rows were found.

This does not prove mixed-reader compatibility. No old 384-era reader was
started against the 768 scratch DB, and no current live reader was changed.

Therefore the safe default remains:

```text
reader_compatibility_mode=atomic_node_cutover_only
```

## Remaining Gates

Still required before any live mutation:

- owner accepts or rejects the evidence packet;
- owner names an exact implementation commit and maintenance window;
- Mac and aio2 model artifact hashes are compared;
- live DB/WAL/SHM and binary backups are named;
- rollback packet is written;
- clients are stopped or reconnected according to the chosen compatibility mode;
- post-cutover `doctor`, backend/dimension distribution, and `recall_eval`
  checks are run.

## Verification

Commands:

```bash
bash -n scripts/verify-gte-768-reader-compatibility-probe.sh
scripts/verify-gte-768-reader-compatibility-probe.sh \
  --pre-db /home/pallasting/.cache/agent-bridge/inbox/state.snapshot.20260623.checkpointed-for-aio2.db \
  --post-db /home/pallasting/.cache/agent-bridge/gte-rehearsal/2026-06-25T130030Z-canonical-snapshot-gate/state.db \
  --strict
```

Results:

- syntax check passed;
- strict copied-DB probe exited 0;
- final status was `READY_FOR_ATOMIC_NODE_CUTOVER_PROPOSAL`;
- warnings were `0`.
