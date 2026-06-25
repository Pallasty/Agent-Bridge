# GTE 768 Canonical Snapshot Acquisition Request

Date: 2026-06-25

Status: `FULFILLED_BY_SSH_READY_FOR_OWNER_REVIEW_PACKET`.

Scope: request the exact pinned Mac snapshot needed before Agent-Bridge can
continue the GTE/768 cut-over evidence lane. This is a transfer/request packet
only. It does not authorize live reindex, live DB mutation, deploy, runtime env
changes, or production `memory_search` changes.

## Fulfillment Update

2026-06-25: SMB was unavailable, so the snapshot was exported and transferred
over SSH from `pallasting@100.91.146.24` (`maxiaodeMac-Pro.local`) to aio2.

Received artifact:

```text
/home/pallasting/.cache/agent-bridge/inbox/state.snapshot.20260623.checkpointed-for-aio2.db
sha256=21b218ddc5d9d9a868520d2441df5bb0b7d3546dba68a28a4db509f0d34189ae
fingerprint=active=3022 edges=5527 newest=1782205313
```

The scratch-only rehearsal completed with:

```text
status=REHEARSAL_COMPLETED_REVIEW_METRICS warnings=0
hard-tier R@10: fts=0.375 fts+graph=0.375 hybrid=0.375 semantic=0.750
```

Current report:

```text
docs/reports/goal-c-u/2026-06-25-gte-768-canonical-snapshot-rehearsal.md
```

## Why This Packet Exists

The local aio2 node now has:

- GTE ONNX assets;
- a verified GTE loader smoke;
- a verified scratch-copy reindex path;
- a guard script:
  `scripts/verify-gte-768-canonical-snapshot-gate.sh`.

But the local node does not have the canonical frozen Mac snapshot that produced
the earlier positive evidence. The latest expanded search ended with:

```text
status=NO_GO_CANONICAL_SNAPSHOT_MISSING
```

Therefore the next safe action is not live migration. It is to obtain the exact
snapshot and replay the GTE rehearsal against a scratch copy.

## Required Snapshot

Accepted snapshot from
`docs/reports/goal-c-u/2026-06-23-main-recall-frozen-baseline-anchor.md`:

```text
/Users/pallasting/.local/share/agent-bridge/snapshots/state.snapshot.20260623.db
```

On the Mac, that path resolves through the symlink:

```text
~/.local/share/agent-bridge
  -> /Users/pallasting/Library/Application Support/agent-bridge
```

Equivalent concrete path:

```text
/Users/pallasting/Library/Application Support/agent-bridge/snapshots/state.snapshot.20260623.db
```

Expected logical fingerprint:

```text
active=3022
edges=5527
newest_created_at=1782205313
```

Reference metadata from the original anchor report:

```text
baseline db bytes: 1150271488
sha256 before old harness run:
  de9a969823156d442cb60ef69b8eef9e6c4b55cd31fde83d1c8f80abdc886bb2
```

Important caveat: the original 2026-06-23 harness used the older writable store
open path and could create a WAL sidecar or change the DB file hash while
preserving the logical fingerprint. For this request, the logical fingerprint is
the primary identity. The transferred artifact should be a checkpointed copy
with no non-empty `-wal` sidecar.

## Preferred Mac-Side Export

Run on the Mac:

```bash
set -euo pipefail

SNAP="$HOME/Library/Application Support/agent-bridge/snapshots/state.snapshot.20260623.db"
OUT="$HOME/Library/Application Support/agent-bridge/snapshots/state.snapshot.20260623.checkpointed-for-aio2.db"

test -f "$SNAP"
rm -f "$OUT" "$OUT-wal" "$OUT-shm" "$OUT.tar.gz"

sqlite3 -readonly "$SNAP" ".backup \"$OUT\""

sqlite3 -readonly "$OUT" "PRAGMA integrity_check;"
sqlite3 -readonly "$OUT" "SELECT count(*) FROM memories WHERE status = 'active';"
sqlite3 -readonly "$OUT" "SELECT count(*) FROM memory_edges;"
sqlite3 -readonly "$OUT" "SELECT coalesce(max(created_at), 0) FROM memories;"

shasum -a 256 "$OUT"
tar -C "$(dirname "$OUT")" -czf "$OUT.tar.gz" "$(basename "$OUT")"
shasum -a 256 "$OUT.tar.gz"
```

Expected query output:

```text
ok
3022
5527
1782205313
```

If `sqlite3 -readonly ... .backup` is unavailable, use a copied snapshot only if
the source has no non-empty WAL sidecar and the copied artifact passes the same
integrity and fingerprint checks.

## Aio2 Receive Path

Suggested local receive path:

```text
/home/pallasting/.cache/agent-bridge/inbox/state.snapshot.20260623.checkpointed-for-aio2.db
```

After copying or extracting the artifact onto aio2, run:

```bash
scripts/verify-gte-768-canonical-snapshot-gate.sh \
  --snapshot /home/pallasting/.cache/agent-bridge/inbox/state.snapshot.20260623.checkpointed-for-aio2.db \
  --expect-active 3022 \
  --expect-edges 5527 \
  --expect-newest 1782205313
```

Only if that reports `READY_FOR_CANONICAL_REHEARSAL`, run the scratch rehearsal:

```bash
scripts/verify-gte-768-canonical-snapshot-gate.sh \
  --snapshot /home/pallasting/.cache/agent-bridge/inbox/state.snapshot.20260623.checkpointed-for-aio2.db \
  --expect-active 3022 \
  --expect-edges 5527 \
  --expect-newest 1782205313 \
  --run-rehearsal
```

That command copies the artifact into `~/.cache/agent-bridge/gte-rehearsal/...`,
reindexes only the scratch copy, and runs `recall_eval` against the copy through
`AB_BASELINE_DB`.

## Acceptance Boundary

This packet authorizes none of the following:

- live DB reindex;
- live DB mutation;
- deployment or runtime env switch;
- production `memory_search` behavior, ranking, schema, or MCP surface changes;
- graph writes or memory writes;
- mixed-reader production mode.

The next possible evidence step is only:

```text
READY_FOR_CANONICAL_REHEARSAL -> scratch-copy GTE replay -> metrics review
```

If the replay reproduces #4016's positive direction, a later owner-review packet
must still name:

- exact snapshot sha256 and logical fingerprint;
- exact GTE model artifact hashes;
- exact candidate commit;
- reader compatibility mode;
- rollback packet;
- minimum acceptance thresholds;
- final owner greenlight for any live mutation.
