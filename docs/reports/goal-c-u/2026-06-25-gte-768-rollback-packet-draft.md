# GTE 768 Rollback Packet Draft

Date: 2026-06-25

Status: `ROLLBACK_DRAFT_READY_FOR_OWNER_REVIEW / LIVE_CUTOVER_NO_GO`.

Scope: rollback plan draft for a future Agent-Bridge GTE 768 live maintenance
window. This draft does not approve live DB mutation, live reindex, deployment,
runtime env changes, production `memory_search` changes, or rollback execution.

## Decision Stub

```json
{
  "rollback_packet_status": "draft_only",
  "rollback_owner": null,
  "rollback_confirmed": false,
  "live_gte_reindex_authorized": false,
  "live_db_mutation_authorized": false,
  "deploy_authorized": false
}
```

## Rollback Rule

The hard rule:

```text
never start an old 384-era reader against a 768 live store
```

If rollback is needed after 768 vectors are written, stop all readers for the
node first, restore the 384-compatible DB files and matching old binary, then
restart readers.

## Current Binary Baseline

aio2 current installed binary is still the old live baseline:

```text
path=/home/pallasting/.local/bin/agent-bridge.real
sha256=cb76bf46963aa90dc496dad4ea7bd17e897be6525c9174e9449b40dacae147e7
bytes=67179000
doctor_ok=true
doctor_fails=0
doctor_warns=0
```

Mac current installed binary is now the migrated GTE-capable node baseline, not
a 384-era rollback baseline:

```text
path=/Users/pallasting/.local/bin/agent-bridge.real
sha256=886da427f62726472f67972b31bad960fc0d16a093a287a3dd068f9439eabf69
doctor_ok=true
doctor_fails=0
doctor_warns=2
mcp_servers=3 current .real, 0 stale
```

Candidate binary hashes are intentionally `TBD` until a final maintenance packet
builds or selects the exact binary artifacts.

## Mac Migrated-State Rollback Caveat

Mac direct SQL now verifies the live DB as a full GTE 768 store:

```text
active_total=3248
embedded=3248
backend=gte-multilingual-base
bytes=3072
dim=768
gte_good=3248
old_or_non_gte_active_embedded=0
```

Therefore the current Mac binary and current Mac live DB cannot be used as a
rollback target for old 384-era readers. A final rollback packet must identify
the exact pre-GTE Mac backup or snapshot, record its data-loss implications, and
verify that no current post-migration writes are silently discarded. The known
2026-06-23 Mac snapshots are pre-GTE evidence snapshots, but they are not
automatically a complete rollback target for post-2026-06-23 live state unless
the owner explicitly accepts that scope.

## Required Backup Packet Fields

The final rollback packet must fill every field below for each node:

```text
node_name=
host=
approved_commit=
old_binary_path=
old_binary_sha256=
candidate_binary_path=
candidate_binary_sha256=
live_db_path=
backup_dir=
backup_state_db=
backup_state_db_sha256=
backup_state_db_wal=
backup_state_db_wal_sha256=
backup_state_db_shm=
backup_state_db_shm_sha256=
pre_cutover_doctor_json=
pre_cutover_backend_distribution=
pre_cutover_reader_inventory=
post_reindex_backend_distribution=
post_reconnect_doctor_json=
rollback_owner=
rollback_decision_post=
```

Missing fields are a stop condition.

## Backup Procedure Template

Run only after the node is in a quiesced maintenance state and readers that can
write or attach to the live store have been stopped.

Linux/aio2 template:

```bash
set -euo pipefail
ts="$(date -u +%Y%m%dT%H%M%SZ)"
db="$HOME/.local/share/agent-bridge/state.db"
bin="$HOME/.local/bin/agent-bridge.real"
backup="$HOME/.local/share/agent-bridge/backups/gte-768-$ts"
mkdir -p "$backup"

cp -a "$db" "$backup/state.db"
[ -f "$db-wal" ] && cp -a "$db-wal" "$backup/state.db-wal" || true
[ -f "$db-shm" ] && cp -a "$db-shm" "$backup/state.db-shm" || true
cp -a "$bin" "$backup/agent-bridge.real"

sha256sum "$backup/state.db"
[ -f "$backup/state.db-wal" ] && sha256sum "$backup/state.db-wal" || true
[ -f "$backup/state.db-shm" ] && sha256sum "$backup/state.db-shm" || true
sha256sum "$backup/agent-bridge.real"
```

Mac template:

```bash
set -euo pipefail
ts="$(date -u +%Y%m%dT%H%M%SZ)"
db="$HOME/Library/Application Support/agent-bridge/state.db"
bin="$HOME/.local/bin/agent-bridge.real"
backup="$HOME/Library/Application Support/agent-bridge/backups/gte-768-$ts"
mkdir -p "$backup"

cp -p "$db" "$backup/state.db"
[ -f "$db-wal" ] && cp -p "$db-wal" "$backup/state.db-wal" || true
[ -f "$db-shm" ] && cp -p "$db-shm" "$backup/state.db-shm" || true
cp -p "$bin" "$backup/agent-bridge.real"

shasum -a 256 "$backup/state.db"
[ -f "$backup/state.db-wal" ] && shasum -a 256 "$backup/state.db-wal" || true
[ -f "$backup/state.db-shm" ] && shasum -a 256 "$backup/state.db-shm" || true
shasum -a 256 "$backup/agent-bridge.real"
```

## Restore Procedure Template

Run only after rollback owner confirms rollback and all readers for the node are
stopped.

Linux/aio2 template:

```bash
set -euo pipefail
db="$HOME/.local/share/agent-bridge/state.db"
bin="$HOME/.local/bin/agent-bridge.real"
backup="/path/to/approved/backup"

cp -a "$backup/state.db" "$db"
if [ -f "$backup/state.db-wal" ]; then cp -a "$backup/state.db-wal" "$db-wal"; else rm -f "$db-wal"; fi
if [ -f "$backup/state.db-shm" ]; then cp -a "$backup/state.db-shm" "$db-shm"; else rm -f "$db-shm"; fi
cp -a "$backup/agent-bridge.real" "$bin"
chmod +x "$bin"
```

Mac template:

```bash
set -euo pipefail
db="$HOME/Library/Application Support/agent-bridge/state.db"
bin="$HOME/.local/bin/agent-bridge.real"
backup="/path/to/approved/backup"

cp -p "$backup/state.db" "$db"
if [ -f "$backup/state.db-wal" ]; then cp -p "$backup/state.db-wal" "$db-wal"; else rm -f "$db-wal"; fi
if [ -f "$backup/state.db-shm" ]; then cp -p "$backup/state.db-shm" "$db-shm"; else rm -f "$db-shm"; fi
cp -p "$backup/agent-bridge.real" "$bin"
chmod +x "$bin"
codesign --force --sign - "$bin"
```

## Post-Restore Verification

Run after restoring and before resuming normal memory writes:

```bash
/path/to/agent-bridge.real doctor --json
```

Then verify backend and byte-length distribution:

```bash
python3 - "$LIVE_DB" <<'PY'
import pathlib
import sqlite3
import sys

db = pathlib.Path(sys.argv[1]).resolve()
con = sqlite3.connect(db.as_uri() + "?mode=ro&immutable=1", uri=True)
con.execute("PRAGMA query_only=ON")
for backend, byte_len, n in con.execute("""
SELECT COALESCE(NULLIF(embedding_backend, ''), 'unknown') AS backend,
       LENGTH(embedding) AS bytes,
       COUNT(*) AS n
  FROM memories
 WHERE status='active'
   AND embedding IS NOT NULL
   AND LENGTH(embedding) > 0
 GROUP BY backend, bytes
 ORDER BY n DESC, bytes DESC, backend ASC
"""):
    print(f"backend={backend} bytes={byte_len} dim={byte_len // 4 if byte_len else 0} rows={n}")
PY
```

Rollback is accepted only if:

- doctor has `fails=0`;
- all active readers are on the restored old binary;
- restored DB distribution is 384-compatible or matches the accepted pre-cutover
  profile;
- no old reader is attached to a 768 store;
- memory writes remain frozen until verification is recorded.

## Emergency Stop Conditions

Immediately stop or roll back if any are true:

- reindex writes hash fallback vectors under `gte-multilingual-base`;
- post-reindex active GTE rows have byte length other than 3072;
- old 384-era MCP reader attaches to a 768 live store;
- `doctor --json` reports stale current-binary or direct-binary failures after
  reconnect;
- `recall_eval` cannot confirm real GTE semantic mode;
- hard-tier semantic R@10 drops below the accepted threshold without owner
  waiver;
- Mac live-store profile diverges from the final authorization packet.

## Open Items For Final Packet

The final rollback packet must still name:

- rollback owner;
- approved maintenance window;
- exact candidate binary path and hash for aio2;
- exact candidate binary path and hash for Mac;
- exact Mac pre-GTE rollback DB/binary source, or an explicit decision that Mac
  rollback is out of scope;
- final backup directories;
- final DB/WAL/SHM hashes;
- exact stop/restart mechanism per node;
- final owner decision post id.

## Recommendation

This rollback draft is good enough for owner review as a planning artifact. It
is not sufficient for live cut-over. The next packet should be a final
authorization record that copies this structure, fills all `TBD` fields, and
sets live authorization booleans explicitly.
